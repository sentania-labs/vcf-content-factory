"""CLI: validate / package / sync dashboards and view definitions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vcfops_supermetrics.client import VCFOpsClient, VCFOpsError

from .client import discover_marker_filename, get_current_user, import_content_zip
from .loader import DashboardValidationError, load_all
from .packager import build_import_zip

DEFAULT_VIEWS = Path("views")
DEFAULT_DASHBOARDS = Path("dashboards")


def _load(args) -> tuple[list, list]:
    return load_all(Path(args.views_dir), Path(args.dashboards_dir))


def cmd_validate(args) -> int:
    try:
        views, dashboards = _load(args)
    except DashboardValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(f"OK: {len(views)} view definition(s), {len(dashboards)} dashboard(s) valid")
    for v in views:
        print(f"  view       {v.id}  {v.name}")
    for d in dashboards:
        print(f"  dashboard  {d.id}  {d.name}")
    return 0


def cmd_package(args) -> int:
    try:
        views, dashboards = _load(args)
    except DashboardValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    blob = build_import_zip(views, dashboards)
    out = Path(args.output)
    out.write_bytes(blob)
    print(f"wrote {out} ({len(blob)} bytes)")
    return 0


def cmd_sync(args) -> int:
    try:
        views, dashboards = _load(args)
    except DashboardValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not views and not dashboards:
        print("nothing to sync", file=sys.stderr)
        return 1
    client = VCFOpsClient.from_env()
    try:
        user = get_current_user(client)
        marker = discover_marker_filename(client)
        blob = build_import_zip(
            views, dashboards, owner_user_id=user["id"], marker_filename=marker
        )
        result = import_content_zip(client, blob)
    except VCFOpsError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 2
    print(f"state: {result.get('state')}")
    for s in result.get("operationSummaries", []):
        print(
            f"  {s.get('contentType','?'):20s} "
            f"imported={s.get('imported',0)} "
            f"skipped={s.get('skipped',0)} "
            f"failed={s.get('failed',0)} "
            f"state={s.get('state','?')}"
        )
        for msg in s.get("errorMessages", []) or []:
            print(f"    ERROR: {msg}")
    return 0 if result.get("state") == "FINISHED" else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfops_dashboards")
    p.add_argument("--views-dir", default=str(DEFAULT_VIEWS))
    p.add_argument("--dashboards-dir", default=str(DEFAULT_DASHBOARDS))
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate YAML")
    pv.set_defaults(func=cmd_validate)

    pp = sub.add_parser("package", help="build the import ZIP locally")
    pp.add_argument("-o", "--output", default="dashboards-content.zip")
    pp.set_defaults(func=cmd_package)

    ps = sub.add_parser("sync", help="build and import to VCF Ops")
    ps.set_defaults(func=cmd_sync)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
