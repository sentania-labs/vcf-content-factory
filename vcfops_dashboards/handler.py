"""Content handler for views and dashboards (vcfops_packaging sync integration).

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

from vcfops_packaging.handler import (
    ContentHandler,
    DeleteResult,
    ItemResult,
    SyncResult,
    ValidateResult,
)
from vcfops_supermetrics.client import VCFOpsClient, VCFOpsError

from .client import discover_marker_filename, get_current_user, import_content_zip
from .loader import DashboardValidationError, load_view, load_dashboard
from .packager import build_import_zip
from .ui_client import UIClientError, VCFOpsUIClient


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

        try:
            user = get_current_user(session)
            marker = discover_marker_filename(session)
            # Import views-only (no dashboards)
            blob = build_import_zip(
                views, [], owner_user_id=user["id"], marker_filename=marker
            )
            api_result = import_content_zip(session, blob)
        except VCFOpsError as exc:
            for v in views:
                result.items.append(
                    ItemResult(name=v.name, status="failed", message=str(exc))
                )
            return result

        state = api_result.get("state", "")
        for v in views:
            if state == "FINISHED":
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
                    ui.delete_view(view_id)
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
                marker_filename=marker,
            )
            api_result = import_content_zip(session, blob)
        except VCFOpsError as exc:
            for d in dashboards:
                result.items.append(
                    ItemResult(name=d.name, status="failed", message=str(exc))
                )
            return result

        state = api_result.get("state", "")
        for d in dashboards:
            if state == "FINISHED":
                result.items.append(ItemResult(name=d.name, status="ok"))
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
