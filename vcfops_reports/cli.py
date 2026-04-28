"""CLI: validate / list / sync / delete report definitions."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vcfops_supermetrics.client import VCFOpsClient, VCFOpsError

from .client import (
    VCFOpsReportsError,
    find_by_name,
    import_reports_zip,
    list_reports,
    discover_marker_filename,
    get_current_user,
)
from .loader import ReportDef, ReportValidationError, load_dir, load_file
from .render import build_import_zip

DEFAULT_DIR = "content/reports"
DEFAULT_VIEWS_DIR = "content/views"
DEFAULT_DASHBOARDS_DIR = "content/dashboards"


def _collect(args) -> list[ReportDef]:
    """Load report definitions from the paths/directory given in args."""
    paths = getattr(args, "paths", [])
    views_dir = getattr(args, "views_dir", DEFAULT_VIEWS_DIR)
    dashboards_dir = getattr(args, "dashboards_dir", DEFAULT_DASHBOARDS_DIR)
    if not paths:
        return load_dir(
            DEFAULT_DIR,
            views_dir=views_dir,
            dashboards_dir=dashboards_dir,
        )
    defs: list[ReportDef] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            defs.extend(load_dir(path, views_dir=views_dir, dashboards_dir=dashboards_dir))
        else:
            defs.append(load_file(path, views_dir=views_dir, dashboards_dir=dashboards_dir))
    return defs


def cmd_validate(args) -> int:
    try:
        defs = _collect(args)
    except ReportValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(f"OK: {len(defs)} report definition(s) valid")
    for rd in defs:
        sections_summary = ", ".join(s.type for s in rd.sections)
        print(f"  {rd.id}  {rd.name}")
        print(f"    sections: {sections_summary}")

    # Slug-uniqueness check across content/ and third_party/*/
    if not getattr(args, "paths", None):
        try:
            from vcfops_packaging.project import check_slug_uniqueness
            errors = check_slug_uniqueness(
                content_type="reports",
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
    client = VCFOpsClient.from_env()
    try:
        count = 0
        for rd in list_reports(client):
            print(f"{rd.get('id')}  {rd.get('name')}")
            count += 1
        if count == 0:
            print("(no report definitions found)")
    except (VCFOpsError, VCFOpsReportsError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    return 0


def cmd_sync(args) -> int:
    try:
        defs = _collect(args)
    except ReportValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    if not defs:
        print("nothing to sync", file=sys.stderr)
        return 1
    client = VCFOpsClient.from_env()
    try:
        user = get_current_user(client)
        marker = discover_marker_filename(client)
        blob = build_import_zip(
            defs,
            owner_user_id=user["id"],
            marker_filename=marker,
        )
        result = import_reports_zip(client, blob)
    except (VCFOpsError, VCFOpsReportsError) as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 2
    print(f"state: {result.get('state')}")
    for s in result.get("operationSummaries", []):
        print(
            f"  {s.get('contentType', '?'):25s} "
            f"imported={s.get('imported', 0)} "
            f"skipped={s.get('skipped', 0)} "
            f"failed={s.get('failed', 0)} "
            f"state={s.get('state', '?')}"
        )
        for msg in s.get("errorMessages", []) or []:
            print(f"    ERROR: {msg}")
    return 0 if result.get("state") == "FINISHED" else 1


def cmd_delete(args) -> int:
    """Delete is not supported via the API — inform the user."""
    print(
        "ERROR: The VCF Operations API has no DELETE endpoint for report "
        "definitions.  Remove report definitions via the Ops web UI:\n"
        "  Administration > Content > Reports\n"
        "Locate the report by name and use the UI's delete action.",
        file=sys.stderr,
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vcfops_reports")
    p.add_argument(
        "--views-dir",
        default=DEFAULT_VIEWS_DIR,
        help="directory containing view definition YAMLs (default: views/)",
    )
    p.add_argument(
        "--dashboards-dir",
        default=DEFAULT_DASHBOARDS_DIR,
        help="directory containing dashboard definition YAMLs (default: dashboards/)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate report YAML definitions")
    pv.add_argument(
        "paths",
        nargs="*",
        help="report YAML files or directories (default: reports/)",
    )
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser("list", help="list report definitions on the instance")
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("sync", help="import report definitions to VCF Ops")
    ps.add_argument(
        "paths",
        nargs="*",
        help="report YAML files or directories (default: reports/)",
    )
    ps.set_defaults(func=cmd_sync)

    pd = sub.add_parser(
        "delete",
        help="delete a report definition (NOTE: not supported via API)",
    )
    pd.add_argument(
        "name",
        nargs="?",
        help="report definition name (informational only; delete uses the UI)",
    )
    pd.set_defaults(func=cmd_delete)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (VCFOpsError, VCFOpsReportsError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
