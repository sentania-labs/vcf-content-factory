"""CLI entry point for vcfops_packaging.

Commands:
    build   bundles/*.yaml       Build one bundle into dist/<name>.zip
    build   --all                Build all bundles/*.yaml
    build-discrete <type> <name> Build a self-contained discrete artifact zip
    validate bundles/*.yaml      Validate without building
    list                         List available bundle manifests
    sync bundles/*.yaml          Sync one bundle to the instance
    sync --all                   Sync all bundles where sync != false
    sync --uninstall bundles/..  Uninstall one bundle from the instance
    sync --uninstall --force ..  Force-uninstall (skip sharing checks)
    refresh-describe             Refresh adapter describe-surface cache
    analyze  <bundle-dir>        Analyze a staged bundle directory for deps
    release <type> <name>        Materialize a release manifest + flip released flag
    publish                      Build released items and push to distribution repo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .builder import build_bundle
from .loader import BundleValidationError, load_bundle, load_all_bundles

DEFAULT_BUNDLES_DIR = "bundles"
DEFAULT_OUTPUT_DIR = "dist"


def cmd_build(args) -> int:
    from .audit import AuditError
    from .describe import DescribeCacheError

    if args.all:
        bundles_dir = Path(DEFAULT_BUNDLES_DIR)
        manifests = sorted(bundles_dir.rglob("*.y*ml")) if bundles_dir.exists() else []
        if not manifests:
            print(f"No bundle manifests found in {DEFAULT_BUNDLES_DIR}/", file=sys.stderr)
            return 1
    elif args.manifests:
        manifests = [Path(p) for p in args.manifests]
    else:
        print("Specify a manifest file or --all", file=sys.stderr)
        return 1

    # Resolve audit mode from flags.
    audit_mode = "auto"
    if getattr(args, "strict_deps", False):
        audit_mode = "strict"
    elif getattr(args, "lax_deps", False):
        audit_mode = "lax"

    live_describe = not getattr(args, "no_live_describe", False)
    skip_audit = getattr(args, "skip_audit", False)

    rc = 0
    for manifest in manifests:
        try:
            out = build_bundle(
                manifest,
                output_dir=DEFAULT_OUTPUT_DIR,
                audit_mode=audit_mode,
                live_describe=live_describe,
                skip_audit=skip_audit,
            )
            print(f"built  {out}")
        except (AuditError, DescribeCacheError) as e:
            print(f"AUDIT FAILED  {manifest}:\n{e}", file=sys.stderr)
            rc = 1
        except BundleValidationError as e:
            print(f"INVALID  {manifest}: {e}", file=sys.stderr)
            rc = 1
        except Exception as e:
            print(f"FAILED   {manifest}: {e}", file=sys.stderr)
            rc = 1
    return rc


def cmd_validate(args) -> int:
    from .releases import (
        load_all_releases,
        validate_flag_state,
        check_bundle_release_collision,
        check_release_naming_convention,
        ReleaseValidationError,
    )

    rc = 0

    # --- Bundle manifest validation ---
    # When no manifests are given on the command line, auto-scan bundles/.
    manifests = list(args.manifests or [])
    if not manifests:
        bundles_dir = Path(DEFAULT_BUNDLES_DIR)
        if bundles_dir.exists():
            manifests = sorted(str(p) for p in bundles_dir.rglob("*.y*ml"))
        if not manifests:
            print("(no bundle manifests found)")

    for p in manifests:
        try:
            bundle = load_bundle(p)
            sync_note = "" if bundle.sync_enabled else "  [sync: false]"
            print(f"OK  {p}{sync_note}")
            parts = []
            if bundle.supermetrics:
                parts.append(f"{len(bundle.supermetrics)} super metric(s)")
            if bundle.views:
                parts.append(f"{len(bundle.views)} view(s)")
            if bundle.dashboards:
                parts.append(f"{len(bundle.dashboards)} dashboard(s)")
            if bundle.customgroups:
                parts.append(f"{len(bundle.customgroups)} custom group(s)")
            if bundle.symptoms:
                parts.append(f"{len(bundle.symptoms)} symptom(s)")
            if bundle.alerts:
                parts.append(f"{len(bundle.alerts)} alert(s)")
            print(f"    {', '.join(parts) if parts else '(empty bundle)'}")
        except BundleValidationError as e:
            print(f"INVALID  {p}: {e}", file=sys.stderr)
            rc = 1

    # --- Release manifest validation ---
    # Scan releases/ if it exists; graceful no-op if it doesn't.
    releases_dir = Path("releases")
    if not releases_dir.exists():
        return rc

    print()
    print("Release manifests:")

    repo_root = Path.cwd()
    try:
        releases = load_all_releases(releases_dir, repo_root=repo_root)
    except ReleaseValidationError as e:
        print(f"FAIL  releases/: {e}")
        return 1

    if not releases:
        print("  (no release manifests found in releases/)")
        return rc

    for r in releases:
        artifact_summary = ", ".join(
            f"{a.source}" + (" [headline]" if a.headline else "")
            for a in r.artifacts
        )
        print(f"  OK  {r.manifest_path.name}  ({r.name} v{r.version})")
        print(f"      {artifact_summary}")

    # Flag-state consistency check.
    flag_errors = validate_flag_state(releases, repo_root)
    if flag_errors:
        print()
        for err in flag_errors:
            print(f"  FAIL  {err}")
        print(f"FAIL  {len(flag_errors)} flag-state error(s) in release manifests")
        rc = 1
    else:
        print(f"  OK  {len(releases)} release manifest(s) valid, flag-state clean")

    # --- Slug collision check: bundles/ vs releases/ ---
    bundles_dir = Path(DEFAULT_BUNDLES_DIR)
    collision_errors = check_bundle_release_collision(bundles_dir, releases)
    if collision_errors:
        print()
        for err in collision_errors:
            print(f"  FAIL  {err}")
        print(f"FAIL  {len(collision_errors)} bundle/release slug collision(s)")
        rc = 1

    # --- Naming convention WARN ---
    naming_warnings = check_release_naming_convention(releases)
    if naming_warnings:
        print()
        for w in naming_warnings:
            print(f"  {w}")

    # --- PROJECT.yaml validation (third_party/) ---
    third_party_dir = Path("third_party")
    if third_party_dir.exists():
        from .project import load_all_projects, ProjectValidationError
        print()
        print("Third-party PROJECT.yaml files:")
        try:
            projects = load_all_projects(third_party_dir)
            if not projects:
                print("  (no third-party projects found)")
            else:
                for proj in projects:
                    print(f"  OK  {proj.source_path.parent.name}/PROJECT.yaml  "
                          f"({proj.display_name}, license={proj.license})")
                print(f"  OK  {len(projects)} project(s) valid")
        except ProjectValidationError as e:
            print(f"  FAIL  {e}")
            rc = 1

    return rc


def cmd_list(args) -> int:
    bundles_dir = Path(DEFAULT_BUNDLES_DIR)
    if not bundles_dir.exists():
        print(f"No {DEFAULT_BUNDLES_DIR}/ directory found.")
        return 0

    manifests = sorted(bundles_dir.rglob("*.y*ml"))
    if not manifests:
        print(f"No bundle manifests found in {DEFAULT_BUNDLES_DIR}/")
        return 0

    for p in manifests:
        try:
            bundle = load_bundle(p)
            sync_tag = "" if bundle.sync_enabled else "  [sync: false]"
            print(f"{bundle.name}{sync_tag}")
            print(f"  manifest: {p}")
            parts = []
            if bundle.supermetrics:
                parts.append(f"SMs:{len(bundle.supermetrics)}")
            if bundle.views:
                parts.append(f"views:{len(bundle.views)}")
            if bundle.dashboards:
                parts.append(f"dashboards:{len(bundle.dashboards)}")
            if bundle.customgroups:
                parts.append(f"groups:{len(bundle.customgroups)}")
            if bundle.symptoms:
                parts.append(f"symptoms:{len(bundle.symptoms)}")
            if bundle.alerts:
                parts.append(f"alerts:{len(bundle.alerts)}")
            print(f"  {', '.join(parts) if parts else '(empty)'}")
            if bundle.description:
                desc = bundle.description.strip().splitlines()[0]
                print(f"  description: {desc}")
        except BundleValidationError as e:
            print(f"  [INVALID: {e}]")
    return 0


def cmd_refresh_describe(args) -> int:
    """Refresh the adapter describe-surface cache against the live instance."""
    from .describe import make_cache, DescribeCacheError

    kinds_arg = getattr(args, "kind", None) or []
    kinds: list[tuple[str, str]] | None = None
    if kinds_arg:
        kinds = []
        for kv in kinds_arg:
            if ":" not in kv:
                print(f"--kind must be in ADAPTER:RESOURCE format, got {kv!r}", file=sys.stderr)
                return 1
            ak, _, rk = kv.partition(":")
            kinds.append((ak.strip(), rk.strip()))

    cache = make_cache(live=True)
    if cache._client is None:
        print(
            "ERROR: VCFOPS_HOST, VCFOPS_USER, and VCFOPS_PASSWORD env vars are required "
            "for refresh-describe.",
            file=sys.stderr,
        )
        return 1

    try:
        cache.refresh_all(kinds=kinds)
    except DescribeCacheError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_analyze(args) -> int:
    """Analyze a staged bundle directory for metric dependencies."""
    import json as _json
    from .audit import analyze_staged_bundle, AuditError, print_audit_summary
    from .describe import make_cache, DescribeCacheError

    bundle_dir = Path(args.bundle_dir)
    if not bundle_dir.exists():
        print(f"ERROR: bundle directory not found: {bundle_dir}", file=sys.stderr)
        return 1

    live_describe = not getattr(args, "no_live_describe", False)
    cache = make_cache(live=live_describe)

    # Auto-refresh relevant pairs if live mode.
    if live_describe and cache._client is not None:
        content_dir = bundle_dir / "content"
        # Parse supermetrics.json to discover kind pairs needed
        sm_path = content_dir / "supermetrics.json"
        pairs: set[tuple[str, str]] = set()
        if sm_path.exists():
            from .deps import _refs_from_formula
            sm_data: dict = _json.loads(sm_path.read_text(encoding="utf-8"))
            for sm_obj in sm_data.values():
                for ref in _refs_from_formula(sm_obj.get("formula", ""), ""):
                    pairs.add((ref.adapter_kind, ref.resource_kind))
        for ak, rk in sorted(pairs):
            try:
                cache.refresh(ak, rk)
            except DescribeCacheError as exc:
                print(f"  WARN: {exc}", file=sys.stderr)

    try:
        result = analyze_staged_bundle(bundle_dir, cache)
    except (AuditError, DescribeCacheError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Print human-readable summary to stderr.
    print_audit_summary(result, "analyze")

    # Emit JSON to stdout — shaped as builtin_metric_enables items list.
    output_items = []
    for r in result.needs_enable:
        output_items.append({
            "adapter_kind": r.adapter_kind,
            "resource_kind": r.resource_kind,
            "metric_key": r.metric_key,
            "reason": f"Auto-detected: referenced by {r.source_desc}, defaultMonitored=false",
        })

    print(_json.dumps(output_items, indent=2))

    return 0 if not result.unknown else 1


def cmd_update_readme(args) -> int:
    """Regenerate AUTO sections in a distribution repo README.md."""
    from .readme_gen import update_readme
    readme_path = Path(args.readme_path)
    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else None
    try:
        changed = update_readme(readme_path, repo_root=repo_root)
        if changed:
            print(f"updated  {readme_path}")
        else:
            print(f"no changes  {readme_path}")
        return 0
    except FileNotFoundError as e:
        print(f"ERROR  {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAILED  {e}", file=sys.stderr)
        return 1


def cmd_build_discrete(args) -> int:
    """Build a self-contained discrete artifact zip for a single released content item."""
    from .discrete_builder import build_discrete, DiscreteBuilderError

    output_dir = getattr(args, "output_dir", "dist/discrete") or "dist/discrete"
    try:
        out = build_discrete(
            content_type=args.content_type,
            item_name=args.item_name,
            output_dir=output_dir,
        )
        print(f"built  {out}")
        return 0
    except DiscreteBuilderError as e:
        print(f"ERROR  {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAILED  {e}", file=sys.stderr)
        return 1


def cmd_check_staleness(args) -> int:
    """Check whether a distribution zip's template version matches current."""
    import json as _json
    import zipfile as _zf
    from .template_version import CURRENT_TEMPLATE_VERSION

    zip_path = Path(args.zip_path)
    if not zip_path.exists():
        print(f"ERROR: file not found: {zip_path}", file=sys.stderr)
        return 1

    try:
        with _zf.ZipFile(zip_path, "r") as z:
            if "vcfops_manifest.json" not in z.namelist():
                print(
                    f"UNKNOWN -- bundle zip has no template version marker "
                    f"(pre-versioning era): {zip_path}"
                )
                return 0
            manifest_data = _json.loads(z.read("vcfops_manifest.json").decode("utf-8"))
    except _zf.BadZipFile as exc:
        print(f"ERROR: not a valid zip file: {zip_path}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: could not read zip: {zip_path}: {exc}", file=sys.stderr)
        return 1

    bundle_version = manifest_data.get("template_version")
    if not bundle_version:
        print(
            f"UNKNOWN -- bundle zip has no template version marker "
            f"(pre-versioning era): {zip_path}"
        )
        return 0

    if bundle_version == CURRENT_TEMPLATE_VERSION:
        print(
            f"OK -- bundle template version matches current "
            f"({CURRENT_TEMPLATE_VERSION}): {zip_path}"
        )
        return 0
    else:
        print(
            f"STALE -- bundle template is {bundle_version}, "
            f"current is {CURRENT_TEMPLATE_VERSION}. "
            f"Rebuild to pick up framework hardening: {zip_path}"
        )
        return 1


def cmd_sync(args) -> int:
    # Import here to avoid pulling in requests at module import time
    from .syncer import sync_bundle, sync_all_bundles, uninstall_bundle
    from .handler import discover_handlers
    from .loader import load_all_bundles as _load_all

    force = getattr(args, "force", False)
    uninstall = getattr(args, "uninstall", False)

    if args.all:
        if uninstall:
            print("--uninstall --all is not supported. "
                  "Specify a manifest path to uninstall.", file=sys.stderr)
            return 1
        return sync_all_bundles(DEFAULT_BUNDLES_DIR)

    if not args.manifests:
        print("Specify a manifest file or --all", file=sys.stderr)
        return 1

    if len(args.manifests) > 1:
        print("Specify exactly one manifest file (or --all)", file=sys.stderr)
        return 1

    manifest_path = args.manifests[0]

    if uninstall:
        # Load all bundles for cross-bundle sharing awareness
        all_bundles = None
        if not force:
            try:
                all_bundles = _load_all(DEFAULT_BUNDLES_DIR)
            except Exception:
                all_bundles = None
        handlers = discover_handlers()
        return uninstall_bundle(
            manifest_path,
            force=force,
            handlers=handlers,
            all_bundles=all_bundles,
        )

    handlers = discover_handlers()
    return sync_bundle(manifest_path, handlers=handlers)


def cmd_release(args) -> int:
    """Materialize a release manifest and flip released: true on the source YAML."""
    import re
    import subprocess
    import yaml

    repo_root = Path.cwd()

    # -----------------------------------------------------------------------
    # Validate type argument — symptoms and alerts unsupported in v1.
    # -----------------------------------------------------------------------
    content_type = args.content_type
    _SUPPORTED = {"dashboard", "view", "supermetric", "customgroup", "report", "bundle"}
    _UNSUPPORTED_V1 = {"symptom", "symptoms", "alert", "alerts"}
    if content_type in _UNSUPPORTED_V1:
        print(
            f"ERROR: '{content_type}' is not supported as a standalone release type in v1.\n"
            f"  Symptoms and alerts ship inside bundles.  Use a bundle headline instead.",
            file=sys.stderr,
        )
        return 1
    if content_type not in _SUPPORTED:
        print(
            f"ERROR: unknown content type {content_type!r}.  "
            f"Supported: {', '.join(sorted(_SUPPORTED))}",
            file=sys.stderr,
        )
        return 1

    # -----------------------------------------------------------------------
    # Resolve <name> to source YAML path.
    #   Priority: exact path -> filename stem -> display name match.
    # -----------------------------------------------------------------------
    name_arg = args.name

    # Map type -> directory
    _TYPE_TO_DIR = {
        "dashboard":   "content/dashboards",
        "view":        "content/views",
        "supermetric": "content/supermetrics",
        "customgroup": "content/customgroups",
        "report":      "content/reports",
        "bundle":      "bundles",
    }
    content_dir = _TYPE_TO_DIR[content_type]

    source_path: Path | None = None

    # 1. Exact path given (absolute or relative)
    candidate = Path(name_arg)
    if candidate.is_absolute() and candidate.exists():
        source_path = candidate
    elif not candidate.is_absolute():
        # Could be a relative path like dashboards/foo.yaml
        rel = repo_root / candidate
        if rel.exists() and rel.suffix in (".yaml", ".yml"):
            source_path = rel

    # 2. Filename stem (e.g. "demand_driven_capacity_v2" -> dashboards/demand_driven_capacity_v2.yaml)
    if source_path is None:
        stem_candidate = repo_root / content_dir / (name_arg + ".yaml")
        if stem_candidate.exists():
            source_path = stem_candidate
        else:
            stem_candidate_yml = repo_root / content_dir / (name_arg + ".yml")
            if stem_candidate_yml.exists():
                source_path = stem_candidate_yml

    # 3. Display name match — scan all YAMLs in the directory for matching name: field
    if source_path is None:
        search_dir = repo_root / content_dir
        if search_dir.exists():
            for yaml_file in sorted(search_dir.glob("*.y*ml")):
                try:
                    data = yaml.safe_load(yaml_file.read_text()) or {}
                    if isinstance(data, dict):
                        file_name = str(data.get("name", "")).strip()
                        if file_name == name_arg:
                            source_path = yaml_file
                            break
                except Exception:
                    continue

    # 4. Third-party project search — scan third_party/*/<type>/ directories.
    #    Only for discrete content types (not bundles — those still use bundles/ or PROJECT.yaml).
    _THIRD_PARTY_TYPE_DIR = {
        "dashboard":   "dashboards",
        "view":        "views",
        "supermetric": "supermetrics",
        "customgroup": "customgroups",
        "report":      "reports",
    }
    if source_path is None and content_type in _THIRD_PARTY_TYPE_DIR:
        tp_type_subdir = _THIRD_PARTY_TYPE_DIR[content_type]
        tp_root = repo_root / "third_party"
        if tp_root.exists():
            # Iterate over project directories in sorted order for determinism.
            for project_dir in sorted(p for p in tp_root.iterdir() if p.is_dir()):
                type_dir = project_dir / tp_type_subdir
                if not type_dir.exists():
                    continue
                # Filename stem match
                if source_path is None:
                    sc = type_dir / (name_arg + ".yaml")
                    if sc.exists():
                        source_path = sc
                        break
                    sc_yml = type_dir / (name_arg + ".yml")
                    if sc_yml.exists():
                        source_path = sc_yml
                        break
                # Display name match
                if source_path is None:
                    for yaml_file in sorted(type_dir.glob("*.y*ml")):
                        try:
                            data = yaml.safe_load(yaml_file.read_text()) or {}
                            if isinstance(data, dict):
                                file_name = str(data.get("name", "")).strip()
                                if file_name == name_arg:
                                    source_path = yaml_file
                                    break
                        except Exception:
                            continue
                if source_path is not None:
                    break

    if source_path is None:
        print(
            f"ERROR: could not resolve '{name_arg}' to a {content_type} YAML file.\n"
            f"  Tried: path, {content_dir}/{name_arg}.yaml, display name match in {content_dir}/",
            file=sys.stderr,
        )
        return 1

    source_path = source_path.resolve()
    if not source_path.exists():
        print(f"ERROR: source file not found: {source_path}", file=sys.stderr)
        return 1

    # -----------------------------------------------------------------------
    # Compute release slug.
    #
    # Convention: <content-stem>-<type>  (snake_case → kebab, lowercase).
    # Exception:  for `bundle` type the source slug already encodes identity;
    #             we do NOT add a -bundle suffix automatically.
    # Override:   --slug <name> bypasses the default entirely.
    # -----------------------------------------------------------------------
    explicit_slug = getattr(args, "slug", None)
    if explicit_slug:
        slug = explicit_slug
    else:
        stem_kebab = source_path.stem.replace("_", "-").lower()
        if content_type == "bundle":
            # Bundles: use the stem as-is (user authors them as foo-bundle.yaml
            # if they want the convention; we don't auto-add the suffix here).
            slug = stem_kebab
        else:
            slug = f"{stem_kebab}-{content_type}"

    # -----------------------------------------------------------------------
    # Compute version.
    # -----------------------------------------------------------------------
    releases_dir = repo_root / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = releases_dir / f"{slug}.yaml"

    explicit_version = getattr(args, "version", None)
    if explicit_version:
        version = explicit_version
    elif manifest_path.exists():
        # Auto-bump minor from existing manifest.
        try:
            existing = yaml.safe_load(manifest_path.read_text()) or {}
            existing_version = str(existing.get("version", "1.0")).strip()
            major, minor = existing_version.split(".")
            version = f"{major}.{int(minor) + 1}"
        except Exception:
            version = "1.0"
    else:
        version = "1.0"

    # -----------------------------------------------------------------------
    # No-op guard: if --version given and manifest already has that exact version.
    # -----------------------------------------------------------------------
    if explicit_version and manifest_path.exists():
        try:
            existing = yaml.safe_load(manifest_path.read_text()) or {}
            if (
                str(existing.get("name", "")).strip() == slug
                and str(existing.get("version", "")).strip() == version
            ):
                print(
                    f"ERROR: release manifest {manifest_path} already at version {version}. "
                    f"No-op release attempt.",
                    file=sys.stderr,
                )
                return 1
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Load description from source YAML (fall back to stub).
    # -----------------------------------------------------------------------
    try:
        source_data = yaml.safe_load(source_path.read_text()) or {}
        description = str(source_data.get("description", "")).strip()
    except Exception:
        description = ""
    if not description:
        description = f"Discrete release of {slug}"

    # -----------------------------------------------------------------------
    # Load release notes from --notes file if provided.
    # -----------------------------------------------------------------------
    release_notes = ""
    notes_file = getattr(args, "notes", None)
    if notes_file:
        notes_path = Path(notes_file)
        if not notes_path.exists():
            print(f"ERROR: --notes file not found: {notes_path}", file=sys.stderr)
            return 1
        release_notes = notes_path.read_text(encoding="utf-8")

    # -----------------------------------------------------------------------
    # Validate --deprecates targets.
    # -----------------------------------------------------------------------
    deprecates_slugs = list(getattr(args, "deprecates", None) or [])
    deprecates_paths: list[str] = []
    for dep_slug in deprecates_slugs:
        dep_path = releases_dir / f"{dep_slug}.yaml"
        if not dep_path.exists():
            print(
                f"ERROR: --deprecates target not found: releases/{dep_slug}.yaml",
                file=sys.stderr,
            )
            return 1
        deprecates_paths.append(f"releases/{dep_slug}.yaml")

    # -----------------------------------------------------------------------
    # Build release manifest dict.
    # -----------------------------------------------------------------------
    # Compute source path relative to repo root for the manifest.
    try:
        source_rel = str(source_path.relative_to(repo_root))
    except ValueError:
        source_rel = str(source_path)

    manifest_data = {
        "name": slug,
        "version": version,
        "description": description,
        "release_notes": release_notes,
        "artifacts": [
            {
                "source": source_rel,
                "headline": True,
            }
        ],
        "deprecates": deprecates_paths,
    }

    # -----------------------------------------------------------------------
    # Write release manifest.
    # -----------------------------------------------------------------------
    manifest_path.write_text(
        yaml.dump(manifest_data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    # -----------------------------------------------------------------------
    # Flip released: true on source YAML.
    # -----------------------------------------------------------------------
    try:
        raw_source = source_path.read_text(encoding="utf-8")
        source_loaded = yaml.safe_load(raw_source) or {}
    except Exception as e:
        print(f"ERROR: could not read source YAML {source_path}: {e}", file=sys.stderr)
        return 1

    source_loaded["released"] = True
    source_path.write_text(
        yaml.dump(source_loaded, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    # -----------------------------------------------------------------------
    # Run validators to confirm both files load cleanly.
    # -----------------------------------------------------------------------
    validate_result = subprocess.run(
        [sys.executable, "-m", "vcfops_packaging", "validate"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    if validate_result.returncode != 0:
        print(
            f"ERROR: validation failed after writing release manifest.\n"
            f"stdout:\n{validate_result.stdout}\n"
            f"stderr:\n{validate_result.stderr}",
            file=sys.stderr,
        )
        return 1

    # -----------------------------------------------------------------------
    # Commit (unless --no-commit).
    # -----------------------------------------------------------------------
    commit_sha = None
    no_commit = getattr(args, "no_commit", False)
    if not no_commit:
        # Stage the two files.
        r = subprocess.run(
            ["git", "add", str(manifest_path), str(source_path)],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
        if r.returncode != 0:
            print(f"ERROR: git add failed: {r.stderr.strip()}", file=sys.stderr)
            return 1

        commit_msg = f"release: {slug} {version}"
        r = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
        if r.returncode != 0:
            if "nothing to commit" in r.stdout + r.stderr:
                pass  # Already committed — that's fine.
            else:
                print(f"ERROR: git commit failed: {r.stdout.strip()} {r.stderr.strip()}", file=sys.stderr)
                return 1
        else:
            # Grab the new HEAD SHA.
            r2 = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=str(repo_root),
            )
            commit_sha = r2.stdout.strip() if r2.returncode == 0 else None

    # -----------------------------------------------------------------------
    # Summary.
    # -----------------------------------------------------------------------
    print(f"release manifest : {manifest_path.relative_to(repo_root)}")
    print(f"source flagged   : {source_rel}  (released: true)")
    print(f"version          : {version}")
    if deprecates_paths:
        print(f"deprecates       : {', '.join(deprecates_paths)}")
    if commit_sha:
        print(f"commit           : {commit_sha}")
    elif no_commit:
        print("commit           : skipped (--no-commit)")

    return 0


def cmd_bundle(args) -> int:
    """Interactive bundle composer — produces bundles/<slug>.yaml."""
    from .composer import compose_bundle

    slug = getattr(args, "name", None) or None
    dry_run = getattr(args, "dry_run", False)
    force = getattr(args, "force", False)

    return compose_bundle(
        slug=slug,
        dry_run=dry_run,
        force=force,
    )


def cmd_publish(args) -> int:
    """Run the publish orchestrator."""
    from .publish import publish, PublishError, PublishResult

    factory_repo = Path.cwd().resolve()

    dist_repo_arg = getattr(args, "dist_repo", None)
    if dist_repo_arg:
        dist_repo = Path(dist_repo_arg).resolve()
    else:
        dist_repo = (factory_repo / ".." / "vcf-content-factory-bundles").resolve()

    dry_run = getattr(args, "dry_run", False)
    force = getattr(args, "force", False)
    no_push = getattr(args, "no_push", False)
    push_direct = getattr(args, "push", False)   # --push flag: direct push to main
    auto_merge = getattr(args, "auto_merge", False)

    # --push and --auto-merge are mutually exclusive.
    if push_direct and auto_merge:
        print("ERROR: --push and --auto-merge are mutually exclusive.", file=sys.stderr)
        return 1

    # use_pr=True unless --push was explicitly requested.
    use_pr = not push_direct

    try:
        result = publish(
            factory_repo=factory_repo,
            dist_repo=dist_repo,
            dry_run=dry_run,
            force=force,
            no_push=no_push,
            use_pr=use_pr,
            auto_merge=auto_merge,
        )
    except PublishError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1

    # Print human-readable summary.
    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}Publish complete.")
    print(f"  built   : {len(result.built)}")
    for p in result.built:
        print(f"    {p}")
    print(f"  skipped : {len(result.skipped)}")
    for p in result.skipped:
        print(f"    {p}")
    print(f"  retired : {len(result.retired)}")
    for p in result.retired:
        print(f"    {p}")
    if result.readme_path:
        print(f"  readme  : {result.readme_path}")
    if result.commit_sha:
        print(f"  commit  : {result.commit_sha}")
    else:
        print(f"  commit  : {'none (dry-run)' if dry_run else 'none (nothing changed)'}")
    print(f"  pushed  : {result.pushed}")
    if result.release_branch:
        print(f"  branch  : {result.release_branch}")
    if result.pr_url:
        print(f"  pr      : {result.pr_url}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfops_packaging")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="build bundle(s) into distributable zips")
    pb.add_argument("manifests", nargs="*",
                    help="path(s) to bundle manifest YAML files")
    pb.add_argument("--all", action="store_true",
                    help=f"build all manifests in {DEFAULT_BUNDLES_DIR}/")
    _dep_group = pb.add_mutually_exclusive_group()
    _dep_group.add_argument(
        "--strict-deps", action="store_true",
        help="fail build if any defaultMonitored=false metric is not declared in manifest",
    )
    _dep_group.add_argument(
        "--lax-deps", action="store_true",
        help="log defaultMonitored=false metrics but do not fail or auto-add",
    )
    pb.add_argument(
        "--no-live-describe", action="store_true",
        help="use describe cache only; do not refresh against live instance",
    )
    pb.add_argument(
        "--skip-audit", action="store_true",
        help="skip dependency audit entirely; metric references are NOT validated. "
             "Use only when describe cache cannot be refreshed and content is known correct.",
    )
    pb.set_defaults(func=cmd_build)

    pur = sub.add_parser(
        "update-readme",
        help="regenerate AUTO:START/END sections in a distribution repo README.md",
    )
    pur.add_argument(
        "readme_path",
        help="path to the README.md file to update",
    )
    pur.add_argument(
        "--repo-root",
        default=None,
        help="path to the factory repo root (default: auto-detected from package location)",
    )
    pur.set_defaults(func=cmd_update_readme)

    pbd = sub.add_parser(
        "build-discrete",
        help="build a self-contained discrete artifact zip for a single released content item",
    )
    pbd.add_argument(
        "content_type",
        choices=["supermetric", "dashboard", "view", "report", "alert", "customgroup"],
        help="type of content item to package",
    )
    pbd.add_argument(
        "item_name",
        help="exact name of the content item (the 'name:' field in its YAML)",
    )
    pbd.add_argument(
        "--output-dir",
        default="dist/discrete",
        help="output directory for the built zip (default: dist/discrete)",
    )
    pbd.set_defaults(func=cmd_build_discrete)

    pv = sub.add_parser("validate", help="validate bundle manifest(s) and release manifests")
    pv.add_argument("manifests", nargs="*",
                    help="path(s) to bundle manifest YAML files; "
                         "omit to auto-scan bundles/ and releases/")
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser("list", help="list available bundle manifests")
    pl.set_defaults(func=cmd_list)

    prd = sub.add_parser(
        "refresh-describe",
        help="refresh adapter describe-surface cache from live VCF Ops instance",
    )
    prd.add_argument(
        "--kind",
        action="append",
        metavar="ADAPTER:RESOURCE",
        help="refresh a specific adapter/resource-kind pair (repeatable); "
             "default: refresh all cached pairs",
    )
    prd.set_defaults(func=cmd_refresh_describe)

    pa = sub.add_parser(
        "analyze",
        help="analyze a staged bundle directory for metric dependencies",
    )
    pa.add_argument(
        "bundle_dir",
        help="path to a staged bundle directory (containing content/ subdirectory)",
    )
    pa.add_argument(
        "--no-live-describe", action="store_true",
        help="use describe cache only; do not refresh against live instance",
    )
    pa.set_defaults(func=cmd_analyze)

    pcs = sub.add_parser(
        "check-staleness",
        help="check whether a distribution zip's template version matches current",
    )
    pcs.add_argument(
        "zip_path",
        help="path to a distribution zip file built by vcfops_packaging",
    )
    pcs.set_defaults(func=cmd_check_staleness)

    ps = sub.add_parser(
        "sync",
        help="sync bundle content to a VCF Ops instance, or uninstall it",
    )
    ps.add_argument(
        "manifests",
        nargs="*",
        metavar="MANIFEST",
        help="path to a bundle manifest YAML file",
    )
    ps.add_argument(
        "--all",
        action="store_true",
        help=f"sync all manifests in {DEFAULT_BUNDLES_DIR}/ where sync != false",
    )
    ps.add_argument(
        "--uninstall",
        action="store_true",
        help="uninstall (delete) the bundle's content from the instance",
    )
    ps.add_argument(
        "--force",
        action="store_true",
        help="with --uninstall: skip cross-bundle sharing checks and delete unconditionally",
    )
    ps.set_defaults(func=cmd_sync)

    # -----------------------------------------------------------------------
    # release <type> <name>
    # -----------------------------------------------------------------------
    pr = sub.add_parser(
        "release",
        help="materialize a release manifest and flip the source's released flag",
    )
    pr.add_argument(
        "content_type",
        metavar="type",
        help=(
            "content type: dashboard, view, supermetric, customgroup, report, bundle. "
            "(symptoms and alerts are not supported in v1)"
        ),
    )
    pr.add_argument(
        "name",
        help=(
            "the slug (filename stem), display name, or path to the source YAML. "
            "Examples: demand_driven_capacity_v2 | "
            "\"[VCF Content Factory] Demand-Driven Capacity Planning v2\" | "
            "dashboards/demand_driven_capacity_v2.yaml"
        ),
    )
    pr.add_argument(
        "--version",
        default=None,
        metavar="X.Y",
        help=(
            "release version (major.minor format, e.g. 1.0). "
            "If omitted, auto-bumps minor from existing manifest, or defaults to 1.0."
        ),
    )
    pr.add_argument(
        "--notes",
        default=None,
        metavar="FILE",
        help="path to a markdown file whose contents become the release_notes field",
    )
    pr.add_argument(
        "--deprecates",
        action="append",
        default=None,
        metavar="SLUG",
        help=(
            "slug of a prior release manifest to mark deprecated (repeatable). "
            "Each slug must match an existing releases/<slug>.yaml file."
        ),
    )
    pr.add_argument(
        "--slug",
        default=None,
        metavar="SLUG",
        help=(
            "explicit release manifest slug (overrides the default "
            "<content-stem>-<type> naming convention). "
            "Use for grandfathering existing names or one-off overrides."
        ),
    )
    pr.add_argument(
        "--no-commit",
        action="store_true",
        help="stage files but do not commit (default is to commit)",
    )
    pr.set_defaults(func=cmd_release)

    # -----------------------------------------------------------------------
    # bundle <name>
    # -----------------------------------------------------------------------
    pbun = sub.add_parser(
        "bundle",
        help="interactive bundle composer — walks you through picking components and writes bundles/<name>.yaml",
    )
    pbun.add_argument(
        "name",
        nargs="?",
        default=None,
        help="bundle slug (kebab-case filename stem, e.g. 'my-bundle'). Prompts if omitted.",
    )
    pbun.add_argument(
        "--dry-run",
        action="store_true",
        help="print proposed YAML to stdout without writing to disk",
    )
    pbun.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing bundles/<name>.yaml if it already exists",
    )
    pbun.set_defaults(func=cmd_bundle)

    # -----------------------------------------------------------------------
    # publish
    # -----------------------------------------------------------------------
    ppub = sub.add_parser(
        "publish",
        help="build all released items and publish to the distribution repo via PR (default) or direct push",
    )
    ppub.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be built/published without writing anything",
    )
    ppub.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing zip at the same release name but different version",
    )
    ppub.add_argument(
        "--no-push",
        action="store_true",
        help=(
            "build and commit to a release branch locally but do not push "
            "and do not open a PR (lets you inspect the branch before publishing)"
        ),
    )

    # PR-mode flags (--pr / --push are mutually exclusive).
    _pr_group = ppub.add_mutually_exclusive_group()
    _pr_group.add_argument(
        "--pr",
        action="store_true",
        default=False,
        dest="pr",
        help=(
            "open a PR against the dist repo's main branch (default behaviour; "
            "this flag is a no-op provided for explicitness)"
        ),
    )
    _pr_group.add_argument(
        "--push",
        action="store_true",
        default=False,
        dest="push",
        help=(
            "direct push to main (legacy/owner fast-path). "
            "Skips PR creation. Mutually exclusive with --pr and --auto-merge."
        ),
    )

    ppub.add_argument(
        "--auto-merge",
        action="store_true",
        dest="auto_merge",
        help=(
            "after opening the PR, immediately enable auto-merge "
            "(gh pr merge --auto --merge). "
            "Implies PR mode. Mutually exclusive with --push."
        ),
    )
    ppub.add_argument(
        "--dist-repo",
        default=None,
        metavar="PATH",
        help=(
            "path to the distribution repo root "
            "(default: ../vcf-content-factory-bundles/ relative to factory repo)"
        ),
    )
    ppub.set_defaults(func=cmd_publish)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
