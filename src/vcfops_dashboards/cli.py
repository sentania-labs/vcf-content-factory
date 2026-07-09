"""CLI: validate / package / sync / delete dashboards and view definitions."""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

from vcfops_common._profile_cli import add_profile_arg, validate_profile_arg, resolve_profile_from_args
from vcfops_supermetrics.client import VCFOpsClient, VCFOpsError

from .client import discover_marker_filename, get_current_user, import_content_zip
from .loader import DashboardValidationError, load_all
from .packager import build_import_zip
from .ui_client import UIClientError, VCFOpsUIClient

DEFAULT_VIEWS = Path("content/views")
DEFAULT_DASHBOARDS = Path("content/dashboards")


def _load(args) -> tuple[list, list]:
    return load_all(Path(args.views_dir), Path(args.dashboards_dir))


_TIME_WINDOW_WARNING_PREFIX = "view "
_TIME_WINDOW_WARNING_FRAGMENT = "no time_window is set"


def _is_time_window_warning(msg: str) -> bool:
    """Return True if the warning message is the aggregating-column-no-window warning."""
    return _TIME_WINDOW_WARNING_FRAGMENT in str(msg)


def _extract_view_name_from_time_window_warning(msg: str) -> str:
    """Extract the view name from a time_window warning message string.

    The message format is:
        view '<name>': one or more columns use an aggregating ...
    Returns the name between the first pair of single-quotes, or '' on parse failure.
    """
    s = str(msg)
    start = s.find("'")
    if start == -1:
        return ""
    end = s.find("'", start + 1)
    if end == -1:
        return ""
    return s[start + 1:end]


def cmd_validate(args) -> int:
    validate_profile_arg(args)  # validate --profile name if supplied; exits on unknown profile
    # Determine whether this is a full-corpus validate (no explicit path overrides).
    # Only the full-corpus path does dashboard-embedding suppression of the
    # time_window warning — single-file / explicit-path invocations keep the
    # warning live since there is no dashboard context to consult.
    using_defaults = (
        args.views_dir == str(DEFAULT_VIEWS)
        and args.dashboards_dir == str(DEFAULT_DASHBOARDS)
    )

    if using_defaults:
        # Full-corpus validate: capture time_window warnings during loading so
        # we can suppress them for dashboard-embedded views after the full
        # corpus (including third-party dashboards) is loaded.
        captured_warnings: list = []
        with warnings.catch_warnings(record=True) as _w:
            warnings.simplefilter("always")
            try:
                views, dashboards = _load(args)
            except DashboardValidationError as e:
                print(f"INVALID: {e}", file=sys.stderr)
                return 1
            # Collect all captured warnings; separate time_window ones for
            # deferred re-emit after we know the embedded set.
            for w in _w:
                captured_warnings.append(w)
    else:
        # Single-file / explicit-path validate: let warnings flow normally.
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

    rc = 0

    if using_defaults:
        try:
            from vcfops_packaging.project import check_slug_uniqueness, check_project_membership
        except ImportError:
            # vcfops_packaging not available — re-emit captured warnings and exit
            _replay_non_time_window_warnings(captured_warnings)
            _replay_time_window_warnings_for_standalone_views(captured_warnings, dashboards)
            return rc  # vcfops_packaging not available — skip checks

        # Slug uniqueness for views and dashboards
        for content_type, default_dir in (
            ("views", DEFAULT_VIEWS),
            ("dashboards", DEFAULT_DASHBOARDS),
        ):
            slug_errors = check_slug_uniqueness(
                content_type=content_type,
                content_type_dir=default_dir,
            )
            if slug_errors:
                for err in slug_errors:
                    print(f"SLUG-COLLISION: {err}", file=sys.stderr)
                rc = 1

        # Project-membership boundary check.
        # Build a full cross-provenance corpus for the dep walker:
        # factory-native content (already loaded) + all third-party content.
        # Use separate lists so the printed output above is unaffected.
        all_views_corpus = list(views)
        all_dashboards_corpus = list(dashboards)
        all_sms: list = []
        all_cgs: list = []

        _third_party = Path("third_party")
        if _third_party.exists():
            try:
                from vcfops_dashboards.loader import (
                    load_view as _load_view,
                    load_dashboard as _load_dash,
                )
                with warnings.catch_warnings(record=True) as _w2:
                    warnings.simplefilter("always")
                    for _proj_dir in sorted(_third_party.iterdir()):
                        if not _proj_dir.is_dir():
                            continue
                        _tp_views_dir = _proj_dir / "views"
                        if _tp_views_dir.exists():
                            for _vp in sorted(_tp_views_dir.rglob("*.y*ml")):
                                try:
                                    all_views_corpus.append(
                                        _load_view(_vp, enforce_framework_prefix=False)
                                    )
                                except Exception:
                                    pass
                        _tp_dash_dir = _proj_dir / "dashboards"
                        if _tp_dash_dir.exists():
                            for _dp in sorted(_tp_dash_dir.rglob("*.y*ml")):
                                try:
                                    all_dashboards_corpus.append(
                                        _load_dash(
                                            _dp,
                                            enforce_framework_prefix=False,
                                            default_name_path="",
                                        )
                                    )
                                except Exception:
                                    pass
                    captured_warnings.extend(_w2)
            except ImportError:
                pass

            try:
                from vcfops_supermetrics.loader import load_dir as _sm_load_dir
                for _proj_dir in sorted(_third_party.iterdir()):
                    if not _proj_dir.is_dir():
                        continue
                    _tp_sm_dir = _proj_dir / "supermetrics"
                    if _tp_sm_dir.exists():
                        try:
                            all_sms.extend(
                                _sm_load_dir(_tp_sm_dir, enforce_framework_prefix=False)
                            )
                        except Exception:
                            pass
            except ImportError:
                pass

            try:
                from vcfops_customgroups.loader import load_dir as _cg_load_dir
                for _proj_dir in sorted(_third_party.iterdir()):
                    if not _proj_dir.is_dir():
                        continue
                    _tp_cg_dir = _proj_dir / "customgroups"
                    if _tp_cg_dir.exists():
                        try:
                            all_cgs.extend(
                                _cg_load_dir(_tp_cg_dir, enforce_framework_prefix=False)
                            )
                        except Exception:
                            pass
            except ImportError:
                pass

        # Also include factory-native SMs and CGs in the corpus
        try:
            from vcfops_supermetrics.loader import load_dir as _sm_load_dir
            _sm_dir = Path("content/supermetrics")
            if _sm_dir.exists():
                try:
                    all_sms.extend(_sm_load_dir(_sm_dir))
                except Exception:
                    pass
        except ImportError:
            pass

        try:
            from vcfops_customgroups.loader import load_dir as _cg_load_dir
            _cg_dir = Path("content/customgroups")
            if _cg_dir.exists():
                try:
                    all_cgs.extend(_cg_load_dir(_cg_dir))
                except Exception:
                    pass
        except ImportError:
            pass

        membership_errors = check_project_membership(
            dashboards=all_dashboards_corpus,
            all_views=all_views_corpus,
            all_supermetrics=all_sms,
            all_customgroups=all_cgs,
        )
        if membership_errors:
            for err in membership_errors:
                print(f"PROJECT-BOUNDARY: {err}", file=sys.stderr)
            rc = 1

        # Now that all dashboards are loaded, build the embedded-view set and
        # selectively re-emit time_window warnings for non-embedded views.
        _replay_non_time_window_warnings(captured_warnings)
        _replay_time_window_warnings_for_standalone_views(captured_warnings, all_dashboards_corpus)

    return rc


def _replay_non_time_window_warnings(captured: list) -> None:
    """Re-emit all captured warnings that are NOT the time_window advisory."""
    for w in captured:
        if not (issubclass(w.category, UserWarning) and _is_time_window_warning(str(w.message))):
            warnings.warn_explicit(
                message=w.message,
                category=w.category,
                filename=w.filename,
                lineno=w.lineno,
                source=w.source,
            )


def _replay_time_window_warnings_for_standalone_views(captured: list, all_dashboards: list) -> None:
    """Re-emit time_window warnings only for views NOT embedded in any dashboard.

    Uses extract_view_names_from_dashboards to build the embedded set, then
    suppresses the warning for views whose names appear in that set.
    """
    try:
        from vcfops_common.dep_walker import extract_view_names_from_dashboards
    except ImportError:
        # dep_walker unavailable — re-emit all time_window warnings unchanged
        for w in captured:
            if issubclass(w.category, UserWarning) and _is_time_window_warning(str(w.message)):
                warnings.warn_explicit(
                    message=w.message,
                    category=w.category,
                    filename=w.filename,
                    lineno=w.lineno,
                    source=w.source,
                )
        return

    embedded_names: set = set(extract_view_names_from_dashboards(all_dashboards))

    for w in captured:
        if not (issubclass(w.category, UserWarning) and _is_time_window_warning(str(w.message))):
            continue
        view_name = _extract_view_name_from_time_window_warning(str(w.message))
        if view_name and view_name in embedded_names:
            # Suppress: view is embedded in a dashboard; time selector drives aggregation.
            continue
        # Re-emit: view is standalone or name could not be extracted.
        warnings.warn_explicit(
            message=w.message,
            category=w.category,
            filename=w.filename,
            lineno=w.lineno,
            source=w.source,
        )


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
    profile, default = resolve_profile_from_args(args)
    client = VCFOpsClient.from_env(profile=profile, default_profile=default)
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
    if result.get("state") != "FINISHED":
        return 1

    # --- Dependency walker: check SM enablement + OOTB metric collection state ---
    dep_rc = _run_dep_walker(
        client,
        views=views,
        dashboards=dashboards,
        supermetrics_dir=getattr(args, "supermetrics_dir", "supermetrics"),
        auto_enable_metrics=getattr(args, "auto_enable_metrics", False),
        skip_metric_check=getattr(args, "skip_metric_check", False),
    )
    return dep_rc


def _run_dep_walker(
    client,
    views: list,
    dashboards: list,
    supermetrics_dir: str = "supermetrics",
    customgroups_dir: str = "customgroups",
    auto_enable_metrics: bool = False,
    skip_metric_check: bool = False,
) -> int:
    """Run the dependency walker after a successful views/dashboards sync.

    Loads the SM YAML from supermetrics_dir (if it exists) to build the
    sm_name_map so SM refs discovered by UUID can be annotated with names.
    The SM definitions themselves are NOT re-synced here — they're passed
    to the walker only for the name map and to tell the walker which SMs
    are in the current sync batch (the walker skips those for the enable
    check, since the SM sync+enable flow handles them).

    Loads the customgroups corpus from customgroups_dir so the walker can
    validate customgroup references found in view ``customgroup:`` fields.
    """
    try:
        from vcfops_common.dep_walker import walk_and_check
    except ImportError as e:
        print(f"WARN  dep walker unavailable: {e}", file=sys.stderr)
        return 0

    # Load SM defs for name map (optional — walker degrades gracefully if absent)
    sm_defs: list = []
    sm_dir = Path(supermetrics_dir)
    if sm_dir.exists():
        try:
            from vcfops_supermetrics.loader import load_dir as _sm_load_dir
            sm_defs = _sm_load_dir(sm_dir)
        except Exception:
            pass  # non-fatal: walker will annotate SMs by UUID only

    sm_name_map = {d.name: d.id for d in sm_defs}

    # Load customgroup defs for ref validation (optional — walker degrades gracefully)
    cg_defs: list = []
    cg_dir = Path(customgroups_dir)
    if cg_dir.exists():
        try:
            from vcfops_customgroups.loader import load_dir as _cg_load_dir
            cg_defs = _cg_load_dir(cg_dir)
        except Exception:
            pass  # non-fatal: customgroup validation will be skipped

    # For dashboard-only syncs, supermetrics list is empty — the walker
    # will still check pre-existing SM refs from views/dashboards.
    walk = walk_and_check(
        client=client,
        supermetrics=[],  # not syncing SMs here; pass empty list
        views=views,
        dashboards=dashboards,
        customgroups=cg_defs,
        auto_enable_metrics=auto_enable_metrics,
        skip_metric_check=skip_metric_check,
        sm_name_map=sm_name_map,
    )
    for level, msg in walk.messages:
        if level == "ERROR":
            print(f"DEP-{level}  {msg}", file=sys.stderr)
        else:
            print(f"DEP-{level}  {msg}")
    if not walk.ok:
        print("sync incomplete: dependency check found errors (see DEP-ERROR above)",
              file=sys.stderr)
        return 1
    return 0


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
    # getGroupedViewDefinitionThumbnails returns a two-level nested dict:
    #   result[viewType][resourceKind] = [view dicts]
    # e.g. {"LIST": {"VirtualMachine": [...], "HostSystem": [...]}, ...}
    # Iterating a dict yields string keys, not dicts or lists, so the old
    # flat-list traversal silently produced an empty result.  Flatten both
    # levels explicitly, with a list-of-dicts fallback for older API shapes.
    all_views: list[dict] = []
    if isinstance(groups, dict):
        # Nested-dict shape: viewType -> resourceKind -> [views]
        for resource_map in groups.values():
            if isinstance(resource_map, dict):
                for view_list in resource_map.values():
                    if isinstance(view_list, list):
                        all_views.extend(view_list)
            elif isinstance(resource_map, list):
                # One level of nesting only
                all_views.extend(resource_map)
    elif isinstance(groups, list):
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
        profile, default = resolve_profile_from_args(args)
        ui = VCFOpsUIClient.from_env(profile=profile, default_profile=default)
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
        profile, default = resolve_profile_from_args(args)
        ui = VCFOpsUIClient.from_env(profile=profile, default_profile=default)
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
                ui.delete_view(uid, name)
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
    p.add_argument("--views-dir", default=str(DEFAULT_VIEWS),
                   help=f"Path to views YAML directory (default: {DEFAULT_VIEWS})")
    p.add_argument("--dashboards-dir", default=str(DEFAULT_DASHBOARDS),
                   help=f"Path to dashboards YAML directory (default: {DEFAULT_DASHBOARDS})")
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate YAML")
    add_profile_arg(pv, default="prod")
    pv.set_defaults(func=cmd_validate)

    pp = sub.add_parser("package", help="build the import ZIP locally")
    pp.add_argument("-o", "--output", default="dashboards-content.zip")
    pp.set_defaults(func=cmd_package)

    ps = sub.add_parser("sync", help="build and import to VCF Ops")
    ps.add_argument(
        "--supermetrics-dir",
        default="content/supermetrics",
        metavar="DIR",
        help=(
            "Path to the supermetrics/ YAML directory. Used to build the SM name map "
            "for dependency check annotations. Default: supermetrics"
        ),
    )
    ps.add_argument(
        "--auto-enable-metrics",
        action="store_true",
        default=False,
        help=(
            "Enable OOTB metrics with defaultMonitored=false on the Default Policy. "
            "Default: warn and flag, but do not modify the policy."
        ),
    )
    ps.add_argument(
        "--skip-metric-check",
        action="store_true",
        default=False,
        help=(
            "Skip the OOTB metric defaultMonitored check entirely. "
            "Use when you know the target policy already covers these metrics."
        ),
    )
    add_profile_arg(ps, default="devel")
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
    add_profile_arg(pdd, default="devel")
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
    add_profile_arg(pdv, default="devel")
    pdv.set_defaults(func=cmd_delete_view)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
