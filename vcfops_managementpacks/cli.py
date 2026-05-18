"""CLI: validate / list / render / build / install / uninstall management packs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from vcfops_common._profile_cli import add_profile_arg, validate_profile_arg

from .loader import ManagementPackDef, ManagementPackValidationError, load_dir, load_file

DEFAULT_DIR = "content/managementpacks"


def _collect(paths: List[str]) -> List[ManagementPackDef]:
    if not paths:
        return load_dir(DEFAULT_DIR)
    defs: List[ManagementPackDef] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            defs.extend(load_dir(path))
        else:
            defs.append(load_file(path))
    return defs


_SDK_ADAPTERS_DIR = "content/sdk-adapters"


def _validate_tier2_projects() -> tuple[int, int]:
    """Validate all Tier 2 SDK adapter projects under content/sdk-adapters/.

    Returns (valid_count, error_count).
    """
    from .sdk_builder import validate_sdk_project

    sdk_dir = Path(_SDK_ADAPTERS_DIR)
    if not sdk_dir.is_dir():
        return 0, 0

    valid = 0
    errors_total = 0
    for project_dir in sorted(sdk_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        adapter_yaml = project_dir / "adapter.yaml"
        if not adapter_yaml.is_file():
            continue
        errors = validate_sdk_project(project_dir)
        if errors:
            errors_total += 1
            print(
                f"  INVALID (Tier 2): {project_dir.name} — "
                f"{len(errors)} error(s):",
                file=sys.stderr,
            )
            for err in errors:
                print(f"    {err}", file=sys.stderr)
        else:
            valid += 1
            print(f"  OK (Tier 2): {project_dir.name}")
    return valid, errors_total


def cmd_validate(args) -> int:
    import warnings as _warnings

    validate_profile_arg(args)  # validate --profile name if supplied; exits on unknown profile

    # Capture label-lint and key-drift warnings emitted during load/validate.
    # Python's default warning filter de-duplicates identical messages; use
    # "always" so every occurrence is captured regardless of repetition.
    captured_warnings: List[str] = []
    with _warnings.catch_warnings(record=True) as _warn_list:
        _warnings.simplefilter("always")
        try:
            defs = _collect(args.paths)
        except ManagementPackValidationError as e:
            print(f"INVALID: {e}", file=sys.stderr)
            return 1

    # Surface captured warnings to stderr
    for w in _warn_list:
        msg = str(w.message)
        if msg.startswith("[label-lint]") or msg.startswith("[key-drift]"):
            captured_warnings.append(msg)
            print(f"WARN: {msg}", file=sys.stderr)

    if not defs:
        print("OK: no Tier 1 management pack definitions found")
    else:
        print(f"OK: {len(defs)} Tier 1 management pack definition(s) valid")
        for d in defs:
            obj_count = len(d.object_types)
            rel_count = len(d.relationships)
            print(
                f"  - [Tier 1] {d.name}  v{d.version}  "
                f"adapter_kind={d.adapter_kind}  "
                f"objects={obj_count}  relationships={rel_count}  "
                f"({d.source_path})"
            )

    # Warning summary
    label_lint_count = sum(1 for w in captured_warnings if w.startswith("[label-lint]"))
    key_drift_count = sum(1 for w in captured_warnings if w.startswith("[key-drift]"))
    if label_lint_count or key_drift_count:
        print(
            f"  warnings: {label_lint_count} label-lint, {key_drift_count} key-drift "
            f"(see WARN lines above; these are advisory, not errors)",
            file=sys.stderr,
        )

    # Slug-uniqueness check across content/ and third_party/*/
    tier1_error = 0
    if not args.paths:
        try:
            from vcfops_packaging.project import check_slug_uniqueness
            errors = check_slug_uniqueness(
                content_type="managementpacks",
                content_type_dir=DEFAULT_DIR,
            )
            if errors:
                for err in errors:
                    print(f"SLUG-COLLISION: {err}", file=sys.stderr)
                tier1_error = 1
        except ImportError:
            pass  # vcfops_packaging not available — skip cross-provenance check

    # Tier 2 validation (only when doing a full repo sweep, not path-specific)
    tier2_error = 0
    if not args.paths:
        t2_valid, t2_errors = _validate_tier2_projects()
        if t2_errors > 0:
            tier2_error = 1
        elif t2_valid > 0:
            print(f"OK: {t2_valid} Tier 2 SDK adapter project(s) valid")

    return 1 if (tier1_error or tier2_error) else 0


def cmd_list(args) -> int:
    # Tier 1 MPs
    try:
        defs = _collect([])
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1

    for d in defs:
        print(f"[Tier 1]  {d.adapter_kind}  {d.name}  v{d.version}  ({d.source_path})")

    # Tier 2 SDK adapters
    sdk_dir = Path(_SDK_ADAPTERS_DIR)
    if sdk_dir.is_dir():
        from .sdk_project import load_sdk_project, SdkProjectError
        for project_dir in sorted(sdk_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            adapter_yaml = project_dir / "adapter.yaml"
            if not adapter_yaml.is_file():
                continue
            try:
                proj = load_sdk_project(adapter_yaml)
                print(
                    f"[Tier 2]  {proj.adapter_kind}  {proj.name}  "
                    f"v{proj.version}.{proj.build_number}  ({adapter_yaml})"
                )
            except SdkProjectError as exc:
                print(
                    f"[Tier 2]  INVALID: {adapter_yaml} — {exc}",
                    file=sys.stderr,
                )

    if not defs and not sdk_dir.is_dir():
        print("no management pack definitions found")
    return 0


def cmd_render(args) -> int:
    from .render import render_mp_design_json

    try:
        mp = load_file(args.path)
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1

    strategy = args.relationship_strategy
    valid_strategies = {
        "world_implicit", "synthetic_adapter_instance",
        "shared_constant_property", "test_all",
    }
    if strategy not in valid_strategies:
        print(
            f"ERROR: --relationship-strategy must be one of "
            f"{sorted(valid_strategies)}; got {strategy!r}",
            file=sys.stderr,
        )
        return 1

    rendered = render_mp_design_json(mp, relationship_strategy=strategy)
    output_str = json.dumps(rendered, indent=2)

    if args.output:
        Path(args.output).write_text(output_str)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(output_str)

    return 0


def cmd_render_export(args) -> int:
    from .render_export import render_mpb_exchange_json

    try:
        mp = load_file(args.path)
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1

    strategy = args.relationship_strategy
    valid_strategies = {
        "world_implicit", "synthetic_adapter_instance",
        "shared_constant_property", "test_all",
    }
    if strategy not in valid_strategies:
        print(
            f"ERROR: --relationship-strategy must be one of "
            f"{sorted(valid_strategies)}; got {strategy!r}",
            file=sys.stderr,
        )
        return 1

    rendered = render_mpb_exchange_json(
        mp,
        relationship_strategy=strategy,
        no_events=args.no_events,
    )
    output_str = json.dumps(rendered, indent=2)

    out_path = args.out
    if out_path:
        Path(out_path).write_text(output_str)
        byte_size = len(output_str.encode("utf-8"))
        top_keys = list(rendered.keys())
        print(f"Wrote {out_path}  ({byte_size:,} bytes, top-level keys: {top_keys})",
              file=sys.stderr)
    else:
        print(output_str)

    return 0


def cmd_extract(args) -> int:
    """Extract an MPB UI exchange-format JSON back to a factory YAML.

    Reads an MPB exchange-format JSON (as exported from MPB UI or unpacked
    from a .pak's adapters.zip/conf/export.json) and produces a YAML
    definition that round-trips through render-export to a semantically
    equivalent design.

    Semantic equivalence is the bar — byte-for-byte match is a non-goal
    because UUIDs minted by MPB (UUID4) will differ from the factory's
    UUID5-derived IDs.
    """
    from .extract import extract_to_yaml

    src = args.from_path
    out = args.out

    try:
        yaml_text = extract_to_yaml(src)
    except FileNotFoundError:
        print(f"ERROR: file not found: {src}", file=sys.stderr)
        return 1
    except (KeyError, TypeError, ValueError) as exc:
        print(f"ERROR extracting {src}: {exc}", file=sys.stderr)
        return 1

    if out:
        Path(out).write_text(yaml_text)
        print(f"Extracted {src} → {out}", file=sys.stderr)
    else:
        print(yaml_text)

    return 0


def cmd_pak_validate(args) -> int:
    """Cross-validate rendered template.json against describe.xml key-sets."""
    from .pak_validator import validate_pak

    try:
        mp = load_file(args.path)
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1

    errors = validate_pak(mp)
    if errors:
        print(f"PAK-VALIDATE FAIL: {len(errors)} error(s) in {mp.name}:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print(f"OK: pak artifacts are internally consistent for {mp.name} v{mp.version}")
    return 0


def cmd_build(args) -> int:
    """Auto-routing build command.

    Routes to Tier 1 (MPB) if arg ends in .yaml;
    routes to Tier 2 (SDK) if arg is a directory with adapter.yaml.
    """
    path = Path(args.path)

    # Auto-detect Tier 2: directory with adapter.yaml
    if path.is_dir() and (path / "adapter.yaml").is_file():
        return _cmd_build_sdk_inner(path, Path(args.output))

    # Tier 1: YAML file path
    from .builder import build_pak
    from .pak_validator import validate_pak

    try:
        mp = load_file(args.path)
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1

    strategy = args.relationship_strategy
    valid_strategies = {
        "world_implicit", "synthetic_adapter_instance",
        "shared_constant_property", "test_all",
    }
    if strategy not in valid_strategies:
        print(
            f"ERROR: --relationship-strategy must be one of "
            f"{sorted(valid_strategies)}; got {strategy!r}",
            file=sys.stderr,
        )
        return 1

    # Run pak-validate before building; refuse to build if errors are found
    # unless --force is passed.
    force = getattr(args, "force", False)
    errors = validate_pak(mp)
    if errors:
        print(f"PAK-VALIDATE FAIL: {len(errors)} error(s) found:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        if not force:
            print(
                "Refusing to build. Fix the errors above or pass --force to override.",
                file=sys.stderr,
            )
            return 1
        print("WARNING: --force passed; building despite validation errors.", file=sys.stderr)
    else:
        print(f"pak-validate: OK", file=sys.stderr)

    output_dir = Path(args.output)
    try:
        pak_path = build_pak(
            mp,
            output_dir=output_dir,
            relationship_strategy=strategy,
            skip_validation=True,  # CLI already ran validate_pak above with --force handling
        )
    except Exception as exc:
        print(f"ERROR building .pak: {exc}", file=sys.stderr)
        return 1

    print(f"Built: {pak_path}")
    return 0


def _cmd_build_sdk_inner(project_dir: Path, output_dir: Path) -> int:
    """Inner helper: build a Tier 2 SDK adapter pak from project_dir."""
    from .sdk_builder import build_sdk_pak, SdkBuildError
    from .sdk_project import SdkProjectError

    try:
        pak_path = build_sdk_pak(project_dir, output_dir)
        print(f"Built: {pak_path}")
        return 0
    except (SdkBuildError, SdkProjectError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR building SDK pak: {exc}", file=sys.stderr)
        return 1


def cmd_build_sdk(args) -> int:
    """build-sdk <dir> — compile and package a Tier 2 SDK adapter project."""
    return _cmd_build_sdk_inner(Path(args.project_dir), Path(args.output))


def cmd_validate_sdk(args) -> int:
    """validate-sdk <dir> — validate adapter.yaml schema and compile-check source."""
    from .sdk_builder import validate_sdk_project, SdkBuildError
    from .sdk_project import SdkProjectError

    project_dir = Path(args.project_dir)
    try:
        errors = validate_sdk_project(project_dir)
    except Exception as exc:
        print(f"ERROR during validate-sdk: {exc}", file=sys.stderr)
        return 1

    if errors:
        print(f"INVALID: {len(errors)} error(s) in {project_dir}:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print(f"OK: {project_dir} is a valid Tier 2 SDK adapter project")
    return 0


def cmd_scaffold_sdk(args) -> int:
    """scaffold-sdk <name> — generate an empty Tier 2 adapter project skeleton."""
    from .sdk_builder import scaffold_sdk_project, SdkBuildError

    output_base = Path(args.output)
    try:
        project_dir = scaffold_sdk_project(args.name, output_base)
        print(f"Scaffolded: {project_dir}")
        return 0
    except SdkBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def cmd_install(args) -> int:
    """Install a .pak file onto a live VCF Ops instance.

    Uses the /ui/ SPA Struts layer for the full install lifecycle —
    no /admin/ session required.  Documented in
    context/pak_ui_upload_investigation.md §"Live-source findings".

    Credentials are read from env vars (VCFOPS_HOST, VCFOPS_USER,
    VCFOPS_PASSWORD) or from CLI flags.  The legacy VCFOPS_ADMIN /
    VCFOPS_ADMINPASSWORD env var names are accepted as fallbacks
    (with a deprecation warning).  Interactive prompts are NOT used.
    """
    from .installer import install_pak

    # installer.install_pak calls sys.exit() on fatal errors; return code
    # from this function is only reached on success.
    install_pak(
        pak_path=args.pak_path,
        host=args.host,
        user=args.user,
        password=args.password,
        skip_ssl_verify=args.skip_ssl_verify,
        wait=args.wait,
        profile=getattr(args, "profile", None),
    )
    return 0


def cmd_pak_compare(args) -> int:
    """Structurally compare a factory-built .pak against one or more reference paks."""
    from .pak_compare import compare_paks, compare_pak_directory, format_report

    factory = Path(args.factory_pak)
    if not factory.exists():
        print(f"ERROR: factory pak not found: {factory}", file=sys.stderr)
        return 1

    output_file = getattr(args, "output", None)
    out_lines: list[str] = []

    def _emit(text: str) -> None:
        print(text, end="")
        if output_file:
            out_lines.append(text)

    if args.reference_dir:
        ref_dir = Path(args.reference_dir)
        if not ref_dir.is_dir():
            print(f"ERROR: --reference-dir is not a directory: {ref_dir}", file=sys.stderr)
            return 1
        results = compare_pak_directory(factory, ref_dir)
        if not results:
            print(f"No .pak files found in {ref_dir}", file=sys.stderr)
            return 1
        _emit(f"\n=== PAK COMPARE (directory mode): {factory.name} vs {ref_dir} ===\n")
        _emit(f"Compared against {len(results)} reference pak(s), sorted by score (closest match first):\n\n")
        for ref_path, result in results:
            _emit(format_report(result))
    else:
        ref = Path(args.reference_pak)
        if not ref.exists():
            print(f"ERROR: reference pak not found: {ref}", file=sys.stderr)
            return 1
        result = compare_paks(factory, ref)
        _emit(format_report(result))

    if output_file:
        Path(output_file).write_text("".join(out_lines))
        print(f"Report written to: {output_file}", file=sys.stderr)

    return 0


def cmd_push_design(args) -> int:
    """Upload an MPB exchange-format JSON (or render one from YAML) and POST it
    to POST /suite-api/internal/mpbuilder/designs/import on a live VCF Ops instance.

    Accepts either:
      - A pre-rendered exchange-format JSON file (produced by render-export).
      - An MP YAML file — it is rendered to a temporary exchange JSON first.

    File type is auto-detected by extension (.json vs .yaml/.yml).

    On success prints the server-minted design UUID and a URL the user can
    paste into a browser to land on the design in the MPB UI.

    Exit codes: 0 = success, 1 = error.
    """
    import json as _json
    import tempfile
    import os as _os

    from .client import MPBClient
    from vcfops_common.client import VCFOpsError
    from vcfops_common._profile_cli import resolve_profile_from_args

    input_path = Path(args.path)
    if not input_path.exists():
        print(f"ERROR: file not found: {input_path}", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Step 1: obtain the exchange-format envelope dict
    # ------------------------------------------------------------------
    suffix = input_path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        # Render MP YAML to exchange JSON in memory
        from .loader import ManagementPackValidationError
        from .render_export import render_mpb_exchange_json

        try:
            mp = load_file(str(input_path))
        except ManagementPackValidationError as e:
            print(f"INVALID: {e}", file=sys.stderr)
            return 1

        strategy = getattr(args, "relationship_strategy", "synthetic_adapter_instance")
        no_events = getattr(args, "no_events", False)

        envelope = render_mpb_exchange_json(
            mp,
            relationship_strategy=strategy,
            no_events=no_events,
        )
        design_name = mp.name

        # Apply --name-override if supplied
        name_override = getattr(args, "name_override", None)
        if name_override:
            try:
                envelope["design"]["design"]["name"] = name_override
                design_name = name_override
            except (KeyError, TypeError):
                print(
                    "WARN: --name-override could not be applied "
                    "(design.design.name path missing from envelope).",
                    file=sys.stderr,
                )

    elif suffix == ".json":
        # Load pre-rendered exchange JSON directly
        try:
            raw = input_path.read_text(encoding="utf-8")
            envelope = _json.loads(raw)
        except Exception as e:
            print(f"ERROR reading {input_path}: {e}", file=sys.stderr)
            return 1

        # Extract design name for display; tolerate any envelope shape
        try:
            design_name = envelope["design"]["design"]["name"]
        except (KeyError, TypeError):
            design_name = input_path.stem

        # Apply --name-override if supplied
        name_override = getattr(args, "name_override", None)
        if name_override:
            try:
                envelope["design"]["design"]["name"] = name_override
                design_name = name_override
            except (KeyError, TypeError):
                print(
                    "WARN: --name-override could not be applied "
                    "(design.design.name path missing from envelope).",
                    file=sys.stderr,
                )

    else:
        print(
            f"ERROR: unrecognised file extension {suffix!r}. "
            f"Expected .yaml/.yml (MP definition) or .json (exchange format).",
            file=sys.stderr,
        )
        return 1

    # ------------------------------------------------------------------
    # Step 2: build the MPBClient from the active credential profile
    # ------------------------------------------------------------------
    profile, default = resolve_profile_from_args(args)
    try:
        client = MPBClient.from_env(profile=profile, default_profile=default)
    except VCFOpsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Step 3: POST to import endpoint
    # ------------------------------------------------------------------
    print(
        f"Importing design {design_name!r} to "
        f"https://{client.host}/suite-api/internal/mpbuilder/designs/import ...",
        file=sys.stderr,
    )
    try:
        result = client.post_design_import(envelope)
    except VCFOpsError as e:
        status_hint = ""
        msg = str(e)
        if "HTTP 400" in msg:
            status_hint = (
                "  Hint: HTTP 400 usually means the envelope body is malformed. "
                "Re-render with 'render-export' and check the exchange format."
            )
        elif "HTTP 401" in msg:
            status_hint = (
                "  Hint: HTTP 401 — authentication failed. "
                "Check --profile / VCFOPS_<PROFILE>_USER and _PASSWORD in .env."
            )
        elif "HTTP 404" in msg:
            status_hint = (
                "  Hint: HTTP 404 on the MPB endpoint usually means the "
                "X-Ops-API-use-unsupported header was rejected or the host "
                "is not a VCF Ops 9.x instance."
            )
        print(f"ERROR: {e}", file=sys.stderr)
        if status_hint:
            print(status_hint, file=sys.stderr)
        return 1

    design_id = result.get("id", "(unknown)")
    host = client.host
    # MPB UI design edit URL — confirmed path from context/mpb_api_surface.md
    # §"Auth / session notes" (MPB UI lives under /vcf-operations/... behind SSO,
    # but the direct /ui/mpbuilder/ path is what most admins bookmark).
    # The exact deep-link to a specific design is not documented in mpb_api_surface.md;
    # the admin-landing URL for the MPB section is used as the closest confirmed path.
    # Update this when a confirmed per-design deep-link is established.
    ui_url = f"https://{host}/ui/index.action#/mpbuilder/designs/{design_id}"

    print(f"Design imported: name={design_name!r}  id={design_id}")
    print(f"  URL: {ui_url}")
    return 0


def cmd_uninstall(args) -> int:
    """Uninstall a management pack from a live VCF Ops instance.

    Follows the recommended uninstall flow documented in
    context/pak_uninstall_api_exploration.md.

    The isUnremovable guard is mandatory and defaults to on.
    Built-in paks (vSAN, vCenter, NSX, etc.) will be refused unless
    --allow-builtin is explicitly passed.

    Credentials are read from env vars (VCFOPS_HOST, VCFOPS_USER,
    VCFOPS_PASSWORD) or from CLI flags.  The legacy VCFOPS_ADMIN /
    VCFOPS_ADMINPASSWORD env var names are accepted as fallbacks
    (with a deprecation warning).
    """
    from .installer import uninstall_pak

    uninstall_pak(
        adapter_kind_or_pak_name=args.name,
        host=args.host,
        user=args.user,
        password=args.password,
        skip_ssl_verify=args.skip_ssl_verify,
        wait=args.wait,
        allow_builtin=args.allow_builtin,
        profile=getattr(args, "profile", None),
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfops_managementpacks")
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate MP YAML definitions")
    pv.add_argument("paths", nargs="*")
    add_profile_arg(pv, default="prod")
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser("list", help="list management pack definitions")
    pl.add_argument("paths", nargs="*")
    pl.set_defaults(func=cmd_list)

    pr = sub.add_parser("render", help="render MP YAML to MPB design JSON")
    pr.add_argument("path", help="path to MP YAML file")
    pr.add_argument("--output", "-o", help="output file path (default: stdout)")
    pr.add_argument(
        "--relationship-strategy",
        default="synthetic_adapter_instance",
        choices=[
            "world_implicit",
            "synthetic_adapter_instance",
            "shared_constant_property",
            "test_all",
        ],
        help="strategy for adapter-instance-trivial (null-expression) relationships (default: synthetic_adapter_instance)",
    )
    pr.set_defaults(func=cmd_render)

    pre = sub.add_parser(
        "render-export",
        help="render MP YAML to MPB UI exchange format (for MPB UI Import Design)",
    )
    pre.add_argument("path", help="path to MP YAML file")
    pre.add_argument(
        "--out", "--output", "-o",
        dest="out",
        default=None,
        help="output file path (default: stdout)",
    )
    pre.add_argument(
        "--relationship-strategy",
        default="synthetic_adapter_instance",
        choices=[
            "world_implicit",
            "synthetic_adapter_instance",
            "shared_constant_property",
            "test_all",
        ],
        help="strategy for adapter-instance-trivial relationships (default: synthetic_adapter_instance)",
    )
    pre.add_argument(
        "--no-events",
        action="store_true",
        dest="no_events",
        default=False,
        help=(
            "emit events: [] in output (empty list, key preserved). "
            "Use until a ground-truth MPB event export is available to "
            "establish the correct wire format."
        ),
    )
    pre.set_defaults(func=cmd_render_export)

    pex = sub.add_parser(
        "extract",
        help=(
            "reverse-extract an MPB UI exchange-format JSON to a factory YAML. "
            "Reads an MPB design JSON (from MPB UI export or .pak/adapters.zip/conf/export.json) "
            "and produces a YAML suitable for the factory pipeline."
        ),
    )
    pex.add_argument(
        "--from",
        dest="from_path",
        required=True,
        metavar="EXCHANGE_JSON",
        help="path to the MPB exchange-format JSON file to extract from",
    )
    pex.add_argument(
        "--out",
        default=None,
        metavar="OUTPUT_YAML",
        help="output YAML file path (default: stdout)",
    )
    pex.set_defaults(func=cmd_extract)

    ppv = sub.add_parser(
        "pak-validate",
        help="cross-validate rendered template.json against describe.xml key-sets (no build)",
    )
    ppv.add_argument("path", help="path to MP YAML file")
    ppv.set_defaults(func=cmd_pak_validate)

    pb = sub.add_parser("build", help="build a .pak file from MP YAML")
    pb.add_argument("path", help="path to MP YAML file")
    pb.add_argument(
        "--output", "-o",
        default="dist",
        help="output directory for the .pak file (default: dist/)",
    )
    pb.add_argument(
        "--relationship-strategy",
        default="synthetic_adapter_instance",
        choices=[
            "world_implicit",
            "synthetic_adapter_instance",
            "shared_constant_property",
            "test_all",
        ],
        help="strategy for adapter-instance-trivial relationships (default: synthetic_adapter_instance)",
    )
    pb.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="build even if pak-validate reports errors (use for debugging only)",
    )
    pb.set_defaults(func=cmd_build)

    # ------------------------------------------------------------------
    # Tier 2 SDK subcommands
    # ------------------------------------------------------------------
    pbsdk = sub.add_parser(
        "build-sdk",
        help="compile and package a Tier 2 SDK adapter project into a .pak",
    )
    pbsdk.add_argument(
        "project_dir",
        metavar="PROJECT_DIR",
        help="path to the Tier 2 adapter project directory (contains adapter.yaml)",
    )
    pbsdk.add_argument(
        "--output", "-o",
        default="dist",
        help="output directory for the .pak file (default: dist/)",
    )
    pbsdk.set_defaults(func=cmd_build_sdk)

    pvsdk = sub.add_parser(
        "validate-sdk",
        help="validate adapter.yaml schema and compile-check a Tier 2 SDK adapter",
    )
    pvsdk.add_argument(
        "project_dir",
        metavar="PROJECT_DIR",
        help="path to the Tier 2 adapter project directory",
    )
    pvsdk.set_defaults(func=cmd_validate_sdk)

    pssdk = sub.add_parser(
        "scaffold-sdk",
        help="generate an empty Tier 2 SDK adapter project skeleton",
    )
    pssdk.add_argument(
        "name",
        metavar="NAME",
        help="human-friendly adapter name (e.g. 'My Custom Monitor')",
    )
    pssdk.add_argument(
        "--output", "-o",
        default="content/sdk-adapters",
        help="base directory for the new project (default: content/sdk-adapters/)",
    )
    pssdk.set_defaults(func=cmd_scaffold_sdk)

    # ------------------------------------------------------------------
    # pak-compare subcommand
    # ------------------------------------------------------------------
    ppc = sub.add_parser(
        "pak-compare",
        help=(
            "structurally compare a factory-built .pak against a reference .pak "
            "and report BLOCKING/WARNING/INFO divergences"
        ),
    )
    ppc.add_argument(
        "factory_pak",
        metavar="FACTORY_PAK",
        help="path to the factory-built .pak file",
    )
    # Mutually-exclusive: single reference OR directory mode
    ref_group = ppc.add_mutually_exclusive_group(required=True)
    ref_group.add_argument(
        "reference_pak",
        metavar="REFERENCE_PAK",
        nargs="?",
        default=None,
        help="path to the reference .pak file to compare against",
    )
    ref_group.add_argument(
        "--reference-dir",
        dest="reference_dir",
        default=None,
        metavar="DIR",
        help=(
            "compare against all .pak files in DIR; "
            "results sorted by score (closest match first)"
        ),
    )
    ppc.add_argument(
        "--output", "-o",
        default=None,
        metavar="FILE",
        help="write the full report to FILE in addition to stdout",
    )
    ppc.set_defaults(func=cmd_pak_compare)

    # ------------------------------------------------------------------
    # install subcommand
    # ------------------------------------------------------------------
    _creds_help = (
        "Credentials resolve order: CLI flag > env var > (no prompt). "
        "Required: --host / VCFOPS_HOST, --user / VCFOPS_USER (or deprecated "
        "VCFOPS_ADMIN), --password / VCFOPS_PASSWORD (or deprecated "
        "VCFOPS_ADMINPASSWORD)."
    )
    pi = sub.add_parser(
        "install",
        help="install a .pak file onto a VCF Ops instance (admin-privileged user required)",
    )
    pi.add_argument(
        "pak_path",
        metavar="PAK_PATH",
        help="path to the .pak file to install",
    )
    pi.add_argument(
        "--host",
        default=None,
        help="VCF Ops hostname or IP (overrides VCFOPS_HOST env var)",
    )
    # Primary credential flags
    pi.add_argument(
        "--user",
        default=None,
        dest="user",
        help="admin-privileged username (overrides VCFOPS_USER env var)",
    )
    pi.add_argument(
        "--password",
        default=None,
        dest="password",
        help="password (overrides VCFOPS_PASSWORD env var)",
    )
    # Backward-compat aliases — kept so existing scripts don't break
    pi.add_argument(
        "--admin-user",
        default=None,
        dest="user",
        help=argparse.SUPPRESS,  # hidden; use --user instead
    )
    pi.add_argument(
        "--admin-password",
        default=None,
        dest="admin_password_compat",
        help=argparse.SUPPRESS,  # hidden; use --password instead
    )
    pi.add_argument(
        "--skip-ssl-verify",
        action="store_true",
        dest="skip_ssl_verify",
        default=False,
        help="disable SSL certificate verification (for lab/self-signed certs)",
    )
    pi.add_argument(
        "--no-wait",
        action="store_false",
        dest="wait",
        default=True,
        help="trigger install and return immediately without polling for completion",
    )
    pi.epilog = _creds_help
    add_profile_arg(pi, default="devel")
    pi.set_defaults(func=cmd_install)

    # ------------------------------------------------------------------
    # uninstall subcommand
    # ------------------------------------------------------------------
    pu = sub.add_parser(
        "uninstall",
        help=(
            "uninstall a management pack from a VCF Ops instance. "
            "Built-in paks (isUnremovable=true) are refused unless "
            "--allow-builtin is passed."
        ),
    )
    pu.add_argument(
        "name",
        metavar="NAME_OR_ADAPTER_KIND",
        help=(
            "display name, UI pakId, or adapter_kind of the pak to remove "
            "(e.g. 'Broadcom Security Advisories' or 'mpb_broadcom_security_advisories')"
        ),
    )
    pu.add_argument(
        "--host",
        default=None,
        help="VCF Ops hostname or IP (overrides VCFOPS_HOST env var)",
    )
    # Primary credential flags
    pu.add_argument(
        "--user",
        default=None,
        dest="user",
        help="admin-privileged username (overrides VCFOPS_USER env var)",
    )
    pu.add_argument(
        "--password",
        default=None,
        dest="password",
        help="password (overrides VCFOPS_PASSWORD env var)",
    )
    # Backward-compat aliases
    pu.add_argument(
        "--admin-user",
        default=None,
        dest="user",
        help=argparse.SUPPRESS,  # hidden; use --user instead
    )
    pu.add_argument(
        "--admin-password",
        default=None,
        dest="admin_password_compat",
        help=argparse.SUPPRESS,  # hidden; use --password instead
    )
    pu.add_argument(
        "--skip-ssl-verify",
        action="store_true",
        dest="skip_ssl_verify",
        default=False,
        help="disable SSL certificate verification (for lab/self-signed certs)",
    )
    pu.add_argument(
        "--no-wait",
        action="store_false",
        dest="wait",
        default=True,
        help="trigger remove and return immediately without polling for completion",
    )
    pu.add_argument(
        "--allow-builtin",
        action="store_true",
        dest="allow_builtin",
        default=False,
        help=(
            "DANGER: override the isUnremovable guard and uninstall a built-in pak. "
            "Only use after a known-good snapshot when you need to reinstall a "
            "built-in. The server will not protect you — a stuck instance requires "
            "manual recovery."
        ),
    )
    pu.epilog = _creds_help
    add_profile_arg(pu, default="devel")
    pu.set_defaults(func=cmd_uninstall)

    # ------------------------------------------------------------------
    # push-design subcommand
    # ------------------------------------------------------------------
    ppd = sub.add_parser(
        "push-design",
        help=(
            "upload an MPB exchange-format JSON (or render from YAML) to "
            "POST /suite-api/internal/mpbuilder/designs/import on a live "
            "VCF Ops instance. Replaces the prior manual curl workflow. "
            "See context/mpb_api_surface.md for endpoint documentation."
        ),
    )
    ppd.add_argument(
        "path",
        metavar="PATH",
        help=(
            "path to either: (a) an MPB exchange-format JSON file "
            "(.json, produced by render-export), or (b) an MP YAML file "
            "(.yaml/.yml, rendered to exchange format automatically before pushing). "
            "File type is auto-detected by extension."
        ),
    )
    ppd.add_argument(
        "--name-override",
        dest="name_override",
        default=None,
        metavar="NAME",
        help=(
            "override the design name before importing "
            "(sets design.design.name in the envelope). "
            "Useful for creating a separate probe design without editing source YAML."
        ),
    )
    ppd.add_argument(
        "--relationship-strategy",
        default="synthetic_adapter_instance",
        dest="relationship_strategy",
        choices=[
            "world_implicit",
            "synthetic_adapter_instance",
            "shared_constant_property",
            "test_all",
        ],
        help=(
            "relationship strategy when rendering from YAML "
            "(ignored for pre-rendered .json input; default: synthetic_adapter_instance)"
        ),
    )
    ppd.add_argument(
        "--no-events",
        action="store_true",
        dest="no_events",
        default=False,
        help=(
            "emit events: [] when rendering from YAML "
            "(ignored for pre-rendered .json input)"
        ),
    )
    add_profile_arg(ppd, default="devel")
    ppd.set_defaults(func=cmd_push_design)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    # Handle the hidden --admin-password compat alias: if set and --password
    # was not set, copy it across.  argparse can't share dest between flags
    # that have different actions, so we do it manually here.
    if hasattr(args, "admin_password_compat") and args.admin_password_compat:
        if not args.password:
            import sys as _sys
            print(
                "WARN: --admin-password is deprecated; use --password instead.",
                file=_sys.stderr,
            )
            args.password = args.admin_password_compat
    return args.func(args)
