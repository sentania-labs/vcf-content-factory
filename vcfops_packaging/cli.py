"""CLI entry point for vcfops_packaging.

Commands:
    build   bundles/*.yaml       Build one bundle into dist/<name>.zip
    build   --all                Build all bundles/*.yaml
    validate bundles/*.yaml      Validate without building
    list                         List available bundle manifests
    sync bundles/*.yaml          Sync one bundle to the instance
    sync --all                   Sync all bundles where sync != false
    sync --uninstall bundles/..  Uninstall one bundle from the instance
    sync --uninstall --force ..  Force-uninstall (skip sharing checks)
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

    rc = 0
    for manifest in manifests:
        try:
            out = build_bundle(manifest, output_dir=DEFAULT_OUTPUT_DIR)
            print(f"built  {out}")
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
            if bundle.symptom_paths:
                parts.append(f"{len(bundle.symptom_paths)} symptom(s)")
            if bundle.alert_paths:
                parts.append(f"{len(bundle.alert_paths)} alert(s)")
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
            if bundle.symptom_paths:
                parts.append(f"symptoms:{len(bundle.symptom_paths)}")
            if bundle.alert_paths:
                parts.append(f"alerts:{len(bundle.alert_paths)}")
            print(f"  {', '.join(parts) if parts else '(empty)'}")
            if bundle.description:
                desc = bundle.description.strip().splitlines()[0]
                print(f"  description: {desc}")
        except BundleValidationError as e:
            print(f"  [INVALID: {e}]")
    return 0


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
    pb.set_defaults(func=cmd_build)

    pv = sub.add_parser("validate", help="validate bundle manifest(s) without building")
    pv.add_argument("manifests", nargs="+",
                    help="path(s) to bundle manifest YAML files")
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser("list", help="list available bundle manifests")
    pl.set_defaults(func=cmd_list)

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
