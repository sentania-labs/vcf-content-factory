"""Content handler for views and dashboards (vcfcf_packaging sync integration).

Views and dashboards are always synced together (they share a single
content-import zip). This handler's content_type is "views" because views
must be imported before dashboards can reference them, but the sync call
also imports all dashboards whose YAML files are passed alongside views.

For the bundle sync orchestrator, the convention is:
  - views handler (sync_order=3): sync yaml_paths of view YAMLs
  - dashboards handler (sync_order=4): sync yaml_paths of dashboard YAMLs

Each handler only imports its own type. The shared marker/owner discovery
is done once in the handler using the session passed in.

Delete uses the UI session (Ext.Direct RPC for views,
dashboard.action for dashboards).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from vcfcf_packaging.handler import (
    ContentHandler,
    DeleteResult,
    ItemResult,
    SyncResult,
    ValidateResult,
)
from vcfcf_supermetrics.client import VCFOpsClient, VCFOpsError

from .client import (
    all_skipped_content_types,
    check_dashboard_materialization,
    discover_marker_filename,
    get_current_user,
    import_content_zip,
)
from .loader import DashboardValidationError, load_view, load_dashboard
from .packager import build_import_zip
from . import sm_columns
from .ui_client import UIClientError, VCFOpsUIClient


def _sm_resolver_or_fail(views, items, result: SyncResult):
    """The ``supermetric:"<name>"`` column resolver for ``views`` (issue
    #270): each column binds to the SM of its view's own content set, then
    the factory, from the same corpus ``vcfcf_dashboards sync`` reads.

    Returns the renderer callable, or None after marking every one of
    ``items`` failed with the column errors (ambiguous, unresolved, or an
    id-less SM), so nothing is imported with a column bound to the wrong SM
    or to none.
    """
    resolver = sm_columns.load_sm_corpus().resolver()
    errors = resolver.column_errors(views)
    if not errors:
        return resolver.uuid_for
    message = "; ".join(errors)
    for item in items:
        result.items.append(
            ItemResult(name=item.name, status="failed", message=message)
        )
    return None


def _all_skipped_message(api_result: dict, content_type: str) -> str:
    """WARN text when THIS content type imported nothing, else "".

    ``state == FINISHED`` on its own used to be reported as ok, so an
    import that skipped every object (existing content left untouched)
    looked like a successful sync.

    The content-type filter is not optional. Every zip these handlers
    send carries two content types (the dashboards handler deliberately
    re-imports the views the views handler just imported), so an
    unfiltered check reports a dashboard that imported fine as "changed
    nothing" whenever the co-shipped views were skipped. Each handler
    speaks only for its own type.
    """
    flagged = all_skipped_content_types(api_result, (content_type,))
    if content_type not in flagged:
        return ""
    imported, skipped = flagged[content_type]
    return (
        f"import finished but changed nothing for {content_type} "
        f"(imported={imported} skipped={skipped}); the existing object on "
        f"the instance was NOT updated. Verify on the instance, or delete "
        f"and re-sync to force an update."
    )


def _materialization_by_id(session, dashboards) -> dict:
    """``{dashboard id: MaterializationStatus}`` after a FINISHED import (#167).

    ``{"__error__": message}`` when the check itself failed, so every
    dashboard says it is unverified instead of a bare ok.
    """
    def _on_wait(count: int, seconds: int) -> None:
        print(
            f"  WAIT  MATERIALIZATION WAIT: {count} dashboard(s) still building; "
            f"re-checking once in {seconds} s",
            flush=True,
        )

    try:
        statuses = check_dashboard_materialization(
            session, dashboards, on_wait=_on_wait
        )
    except Exception as exc:  # noqa: BLE001  advisory check; never fail the import over it
        return {"__error__": str(exc)}
    return {st.id: st for st in statuses}


def _materialization_item(d, status) -> ItemResult:
    """ItemResult for one dashboard from its phase-2 status.

    Waiting on an adapter kind the target lacks is a failure (it never
    completes on its own). Still building after the re-check, or absent
    from the instance, is a warn with the reason, so bundle sync counts it
    in its "need attention" trailer. Only complete is a bare ok.
    """
    from vcfcf_core.dashboards.materialization import (
        COMPLETE,
        STALLED,
        describe_status,
    )

    if status is None or status.state == COMPLETE:
        return ItemResult(name=d.name, status="ok")
    message = f"MATERIALIZATION {status.state.upper()}: {describe_status(status)}"
    if status.state == STALLED:
        return ItemResult(name=d.name, status="failed", message=message)
    return ItemResult(name=d.name, status="warn", message=message)


class ViewsHandler(ContentHandler):
    content_type = "views"
    sync_order = 3

    def validate(self, yaml_paths: List[str]) -> ValidateResult:
        result = ValidateResult(content_type=self.content_type)
        for p in yaml_paths:
            try:
                v = load_view(Path(p))
                result.items.append(ItemResult(name=v.name, status="ok"))
            except (DashboardValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )
        return result

    def sync(self, yaml_paths: List[str], session: VCFOpsClient) -> SyncResult:
        result = SyncResult(content_type=self.content_type)
        views = []
        for p in yaml_paths:
            try:
                v = load_view(Path(p))
                views.append(v)
            except (DashboardValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )

        if not views:
            return result

        sm_resolver = _sm_resolver_or_fail(views, views, result)
        if sm_resolver is None:
            return result

        try:
            user = get_current_user(session)
            marker = discover_marker_filename(session)
            # Import views-only (no dashboards)
            blob = build_import_zip(
                views, [],
                owner_user_id=user["id"],
                owner_username=user.get("userName", "admin"),
                marker_filename=marker,
                sm_resolver=sm_resolver,
            )
            api_result = import_content_zip(session, blob)
        except VCFOpsError as exc:
            for v in views:
                result.items.append(
                    ItemResult(name=v.name, status="failed", message=str(exc))
                )
            return result

        state = api_result.get("state", "")
        all_skipped = _all_skipped_message(api_result, "VIEW_DEFINITIONS")
        for v in views:
            if state == "FINISHED" and all_skipped:
                result.items.append(
                    ItemResult(name=v.name, status="warn", message=all_skipped)
                )
            elif state == "FINISHED":
                result.items.append(ItemResult(name=v.name, status="ok"))
            else:
                result.items.append(
                    ItemResult(name=v.name, status="warn",
                               message=f"import state={state}")
                )
        return result

    def delete(
        self,
        names: List[str],
        session: VCFOpsClient,
        force: bool = False,
    ) -> DeleteResult:
        result = DeleteResult(content_type=self.content_type)
        try:
            ui = VCFOpsUIClient.from_env()
            ui.login()
        except (UIClientError, Exception) as exc:
            for name in names:
                result.items.append(
                    ItemResult(name=name, status="failed",
                               message=f"UI login failed: {exc}")
                )
            return result

        try:
            groups = ui.list_views()
            all_views: list = []
            for item in groups:
                if isinstance(item, dict):
                    for key in ("viewDefinitions", "views", "items"):
                        sub = item.get(key)
                        if isinstance(sub, list):
                            all_views.extend(sub)
                            break
                    else:
                        if "id" in item:
                            all_views.append(item)
                elif isinstance(item, list):
                    all_views.extend(item)

            by_name = {
                v.get("name", ""): v["id"]
                for v in all_views
                if "id" in v and v.get("name")
            }

            for name in names:
                view_id = by_name.get(name)
                if not view_id:
                    result.items.append(
                        ItemResult(name=name, status="skipped",
                                   message="not found on instance")
                    )
                    continue
                try:
                    ui.delete_view(view_id, name)
                    result.items.append(ItemResult(name=name, status="ok"))
                except (UIClientError, Exception) as exc:
                    result.items.append(
                        ItemResult(name=name, status="failed", message=str(exc))
                    )
        finally:
            try:
                ui.logout()
            except Exception:
                pass

        return result


class DashboardsHandler(ContentHandler):
    content_type = "dashboards"
    sync_order = 4

    def validate(self, yaml_paths: List[str]) -> ValidateResult:
        result = ValidateResult(content_type=self.content_type)
        for p in yaml_paths:
            try:
                d = load_dashboard(Path(p))
                result.items.append(ItemResult(name=d.name, status="ok"))
            except (DashboardValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )
        return result

    def sync(self, yaml_paths: List[str], session: VCFOpsClient) -> SyncResult:
        result = SyncResult(content_type=self.content_type)
        dashboards = []
        for p in yaml_paths:
            try:
                d = load_dashboard(Path(p))
                dashboards.append(d)
            except (DashboardValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )

        if not dashboards:
            return result

        # Collect view names referenced by View widgets across all dashboards.
        # The renderer needs ViewDef objects (for their UUIDs) even though views
        # are not re-imported alongside dashboards. Resolve them by scanning the
        # repo's views/ directory, which lives at the same level as dashboards/.
        # Dashboard YAML paths are absolute (e.g. /repo/dashboards/foo.yaml),
        # so repo root = Path(yaml_paths[0]).parent.parent.
        referenced_view_names = {
            w.view_name
            for d in dashboards
            for w in d.widgets
            if w.type == "View" and w.view_name
        }
        views_by_name = {}
        if referenced_view_names:
            repo_root = Path(yaml_paths[0]).parent.parent
            views_dir = repo_root / "views"
            if views_dir.is_dir():
                for vp in sorted(views_dir.rglob("*.y*ml")):
                    try:
                        v = load_view(vp)
                        if v.name in referenced_view_names:
                            views_by_name[v.name] = v
                    except Exception:  # noqa: BLE001
                        pass
            missing = referenced_view_names - set(views_by_name)
            if missing:
                for d in dashboards:
                    result.items.append(
                        ItemResult(
                            name=d.name,
                            status="failed",
                            message=(
                                f"view(s) referenced but not found in views/: "
                                f"{', '.join(sorted(missing))}"
                            ),
                        )
                    )
                return result

        sm_resolver = _sm_resolver_or_fail(
            list(views_by_name.values()), dashboards, result)
        if sm_resolver is None:
            return result

        try:
            user = get_current_user(session)
            marker = discover_marker_filename(session)
            # Pass resolved views alongside dashboards so the renderer can
            # look up viewDefinitionId for each View widget. The views are
            # already installed from the views sync step; re-importing them
            # here is idempotent and harmless.
            blob = build_import_zip(
                list(views_by_name.values()),
                dashboards,
                owner_user_id=user["id"],
                owner_username=user.get("userName", "admin"),
                marker_filename=marker,
                sm_resolver=sm_resolver,
            )
            api_result = import_content_zip(session, blob)
        except VCFOpsError as exc:
            for d in dashboards:
                result.items.append(
                    ItemResult(name=d.name, status="failed", message=str(exc))
                )
            return result

        state = api_result.get("state", "")
        all_skipped = _all_skipped_message(api_result, "DASHBOARDS")
        materialization = {}
        if state == "FINISHED" and not all_skipped:
            materialization = _materialization_by_id(session, dashboards)
        for d in dashboards:
            if state == "FINISHED" and all_skipped:
                result.items.append(
                    ItemResult(name=d.name, status="warn", message=all_skipped)
                )
            elif state == "FINISHED" and "__error__" in materialization:
                result.items.append(ItemResult(
                    name=d.name, status="warn",
                    message=(
                        "MATERIALIZATION UNCHECKED: imported, but could not check whether it finished "
                        f"building: {materialization['__error__']}"
                    ),
                ))
            elif state == "FINISHED":
                result.items.append(
                    _materialization_item(
                        d, materialization.get(str(getattr(d, "id", "") or "").lower())
                    )
                )
            else:
                result.items.append(
                    ItemResult(name=d.name, status="warn",
                               message=f"import state={state}")
                )
        return result

    def delete(
        self,
        names: List[str],
        session: VCFOpsClient,
        force: bool = False,
    ) -> DeleteResult:
        result = DeleteResult(content_type=self.content_type)
        try:
            ui = VCFOpsUIClient.from_env()
            ui.login()
        except (UIClientError, Exception) as exc:
            for name in names:
                result.items.append(
                    ItemResult(name=name, status="failed",
                               message=f"UI login failed: {exc}")
                )
            return result

        try:
            all_dashboards = ui.list_dashboards()
            by_name = {
                d["name"]: d["id"]
                for d in all_dashboards
                if d.get("name") and d.get("id")
            }

            to_delete = []
            for name in names:
                dash_id = by_name.get(name)
                if not dash_id:
                    result.items.append(
                        ItemResult(name=name, status="skipped",
                                   message="not found on instance")
                    )
                    continue
                to_delete.append((dash_id, name))

            if to_delete:
                try:
                    ui.delete_dashboards(to_delete)
                    for _, name in to_delete:
                        result.items.append(ItemResult(name=name, status="ok"))
                except (UIClientError, Exception) as exc:
                    for _, name in to_delete:
                        result.items.append(
                            ItemResult(name=name, status="failed", message=str(exc))
                        )
        finally:
            try:
                ui.logout()
            except Exception:
                pass

        return result


HANDLERS = [ViewsHandler(), DashboardsHandler()]
