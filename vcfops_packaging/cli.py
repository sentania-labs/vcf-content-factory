"""CLI entry point for vcfops_packaging.

Commands:
    build   bundles/*.yaml       Build one bundle into dist/<name>.zip
    build   --all                Build all bundles/*.yaml
    validate bundles/*.yaml      Validate without building
    list                         List available bundle manifests
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
            print(f"OK  {p}")
            print(f"    {len(bundle.supermetrics)} super metric(s), "
                  f"{len(bundle.views)} view(s), "
                  f"{len(bundle.dashboards)} dashboard(s), "
                  f"{len(bundle.customgroups)} custom group(s)")
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
            print(f"{bundle.name}")
            print(f"  manifest: {p}")
            print(f"  SMs: {len(bundle.supermetrics)}, "
                  f"views: {len(bundle.views)}, "
                  f"dashboards: {len(bundle.dashboards)}, "
                  f"groups: {len(bundle.customgroups)}")
            if bundle.description:
                desc = bundle.description.strip().splitlines()[0]
                print(f"  description: {desc}")
        except BundleValidationError as e:
            print(f"  [INVALID: {e}]")
    return 0


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

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
