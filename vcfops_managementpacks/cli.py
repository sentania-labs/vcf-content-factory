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


def cmd_validate(args) -> int:
    validate_profile_arg(args)  # validate --profile name if supplied; exits on unknown profile
    try:
        defs = _collect(args.paths)
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not defs:
        print("OK: no management pack definitions found")
        return 0
    print(f"OK: {len(defs)} management pack definition(s) valid")
    for d in defs:
        obj_count = len(d.object_types)
        rel_count = len(d.relationships)
        print(
            f"  - {d.name}  v{d.version}  "
            f"adapter_kind={d.adapter_kind}  "
            f"objects={obj_count}  relationships={rel_count}  "
            f"({d.source_path})"
        )

    # Slug-uniqueness check across content/ and third_party/*/
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
                return 1
        except ImportError:
            pass  # vcfops_packaging not available — skip cross-provenance check

    return 0


def cmd_list(args) -> int:
    try:
        defs = _collect([])
    except ManagementPackValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not defs:
        print("no management pack definitions found")
        return 0
    for d in defs:
        print(f"{d.adapter_kind}  {d.name}  v{d.version}  ({d.source_path})")
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
