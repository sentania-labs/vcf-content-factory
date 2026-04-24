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
    if not args.manifests:
        print("Specify one or more manifest files", file=sys.stderr)
        return 1

    rc = 0
    for p in args.manifests:
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

    pv = sub.add_parser("validate", help="validate bundle manifest(s) without building")
    pv.add_argument("manifests", nargs="+",
                    help="path(s) to bundle manifest YAML files")
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

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
