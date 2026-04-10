"""CLI: validate / package / sync / delete dashboards and view definitions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vcfops_supermetrics.client import VCFOpsClient, VCFOpsError

from .client import discover_marker_filename, get_current_user, import_content_zip
from .loader import DashboardValidationError, load_all
from .packager import build_import_zip
from .ui_client import UIClientError, VCFOpsUIClient

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


def _resolve_dashboard_ids(
    ui: VCFOpsUIClient, targets: list[str]
) -> list[tuple[str, str]]:
    """Resolve a mixed list of UUIDs and display names to (uuid, name) pairs.

    For entries that look like UUIDs (contain hyphens), the name is looked
    up from the server list. Entries that don't look like UUIDs are matched
    by name. Raises SystemExit if any target cannot be resolved.
    """
    import re
    uuid_pat = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
    )
    server_list = ui.list_dashboards()
    by_id = {d["id"]: d["name"] for d in server_list}
    by_name = {d["name"]: d["id"] for d in server_list}

    resolved: list[tuple[str, str]] = []
    errors: list[str] = []
    for t in targets:
        if uuid_pat.match(t):
            name = by_id.get(t, t)  # if not found, use uuid as name (silent no-op)
            resolved.append((t, name))
        else:
            uid = by_name.get(t)
            if uid is None:
                errors.append(f"  dashboard not found by name: {t!r}")
            else:
                resolved.append((uid, t))
    if errors:
        print("ERROR: could not resolve the following targets:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    return resolved


def _resolve_view_ids(
    ui: VCFOpsUIClient, targets: list[str]
) -> list[tuple[str, str]]:
    """Resolve a mixed list of view UUIDs and names to (uuid, name) pairs.

    View list comes from Ext.Direct getGroupedViewDefinitionThumbnails.
    The response is a grouped structure; we flatten it to find all views.
    Raises SystemExit if any target cannot be resolved.
    """
    import re
    uuid_pat = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
    )

    groups = ui.list_views()
    # getGroupedViewDefinitionThumbnails returns a list of group objects,
    # each with a "viewDefinitions" (or similar) sub-list. Flatten defensively.
    all_views: list[dict] = []
    for item in groups:
        if isinstance(item, dict):
            # Group object: may have viewDefinitions or similar key
            for key in ("viewDefinitions", "views", "items"):
                sub = item.get(key)
                if isinstance(sub, list):
                    all_views.extend(sub)
                    break
            else:
                # If no known sub-key, treat item itself as a view entry
                if "id" in item:
                    all_views.append(item)
        elif isinstance(item, list):
            all_views.extend(item)

    by_id = {v["id"]: v.get("name", v["id"]) for v in all_views if "id" in v}
    by_name = {v.get("name", ""): v["id"] for v in all_views if "id" in v and v.get("name")}

    resolved: list[tuple[str, str]] = []
    errors: list[str] = []
    for t in targets:
        if uuid_pat.match(t):
            name = by_id.get(t, t)
            resolved.append((t, name))
        else:
            uid = by_name.get(t)
            if uid is None:
                errors.append(f"  view not found by name: {t!r}")
            else:
                resolved.append((uid, t))
    if errors:
        print("ERROR: could not resolve the following targets:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    return resolved


def cmd_delete_dashboard(args) -> int:
    """Delete one or more dashboards by UUID or display name.

    Uses the unsupported VCF Ops UI session (Struts action layer), not the
    Suite API. Credentials come from the standard VCFOPS_* env vars.
    Deleting a non-existent UUID is a silent no-op.
    """
    try:
        ui = VCFOpsUIClient.from_env()
        ui.login()
    except UIClientError as e:
        print(f"FAILED (UI login): {e}", file=sys.stderr)
        return 2
    try:
        targets = _resolve_dashboard_ids(ui, args.targets)
        if not targets:
            print("nothing to delete", file=sys.stderr)
            return 1
        print(f"{'Would delete' if args.dry_run else 'Deleting'} "
              f"{len(targets)} dashboard(s):")
        for uid, name in targets:
            print(f"  {uid}  {name}")
        if args.dry_run:
            return 0
        ui.delete_dashboards(targets)
        print("done")
        return 0
    except UIClientError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 2
    finally:
        ui.logout()


def cmd_delete_view(args) -> int:
    """Delete one or more view definitions by UUID or display name.

    Uses the unsupported VCF Ops UI session (Ext.Direct RPC layer), not the
    Suite API. Credentials come from the standard VCFOPS_* env vars.
    Unlike dashboard delete, deleting a non-existent view UUID raises an
    error — this command surfaces that as a non-zero exit.
    """
    try:
        ui = VCFOpsUIClient.from_env()
        ui.login()
    except UIClientError as e:
        print(f"FAILED (UI login): {e}", file=sys.stderr)
        return 2
    try:
        targets = _resolve_view_ids(ui, args.targets)
        if not targets:
            print("nothing to delete", file=sys.stderr)
            return 1
        print(f"{'Would delete' if args.dry_run else 'Deleting'} "
              f"{len(targets)} view(s):")
        for uid, name in targets:
            print(f"  {uid}  {name}")
        if args.dry_run:
            return 0
        failed = 0
        for uid, name in targets:
            try:
                ui.delete_view(uid)
                print(f"  deleted {uid}  {name}")
            except UIClientError as e:
                print(f"  FAILED {uid}  {name}: {e}", file=sys.stderr)
                failed += 1
        return 0 if failed == 0 else 2
    except UIClientError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 2
    finally:
        ui.logout()


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

    pdd = sub.add_parser(
        "delete-dashboard",
        help="delete dashboard(s) by UUID or name via UI session",
    )
    pdd.add_argument(
        "targets",
        nargs="+",
        metavar="UUID-OR-NAME",
        help="dashboard UUID(s) or display name(s) to delete",
    )
    pdd.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be deleted without deleting",
    )
    pdd.set_defaults(func=cmd_delete_dashboard)

    pdv = sub.add_parser(
        "delete-view",
        help="delete view definition(s) by UUID or name via UI session",
    )
    pdv.add_argument(
        "targets",
        nargs="+",
        metavar="UUID-OR-NAME",
        help="view UUID(s) or display name(s) to delete",
    )
    pdv.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be deleted without deleting",
    )
    pdv.set_defaults(func=cmd_delete_view)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
