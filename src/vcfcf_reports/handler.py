"""Content handler for report definitions (vcfcf_packaging sync integration).

Exposes a module-level HANDLER instance that the vcfcf_packaging sync
orchestrator discovers automatically.

Sync order 7 — after alerts (6).  Reports may reference views (3) and
dashboards (4), so they must sync after both of those are in place.

Delete is not supported via the API.  The handler surfaces this as a
'skipped' status with an explanatory message rather than a hard failure,
so bundle uninstall does not abort on reports.
"""
from __future__ import annotations

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
    VCFOpsReportsError,
    discover_marker_filename,
    get_current_user,
    import_reports_zip,
)
from .loader import ReportValidationError, load_file
from .render import build_import_zip


class ReportsHandler(ContentHandler):
    content_type = "reports"
    sync_order = 7

    def validate(self, yaml_paths: List[str]) -> ValidateResult:
        result = ValidateResult(content_type=self.content_type)
        for p in yaml_paths:
            try:
                rd = load_file(Path(p))
                result.items.append(ItemResult(name=rd.name, status="ok"))
            except (ReportValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )
        return result

    def sync(self, yaml_paths: List[str], session: VCFOpsClient) -> SyncResult:
        result = SyncResult(content_type=self.content_type)
        reports = []
        for p in yaml_paths:
            try:
                rd = load_file(Path(p))
                reports.append(rd)
            except (ReportValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )
        return self._import(reports, result, session)

    def sync_loaded(self, reports: list, yaml_paths: List[str],
                    session: VCFOpsClient) -> SyncResult:
        """Bundle sync entry: import the ReportDefs load_bundle already built.

        load_bundle validated them with the bundle's own context (its
        factory_native prefix rule and its report view/dashboard dirs), so
        reloading the files here with factory defaults would reject a
        third-party bundle's report that its build accepts (#232 review W4).
        Falls back to :meth:`sync` when no loaded objects are handed in.
        """
        if not reports:
            return self.sync(yaml_paths, session)
        return self._import(list(reports), SyncResult(content_type=self.content_type), session)

    def _import(self, reports: list, result: SyncResult,
                session: VCFOpsClient) -> SyncResult:
        if not reports:
            return result

        try:
            user = get_current_user(session)
            marker = discover_marker_filename(session)
            blob = build_import_zip(
                reports,
                owner_user_id=user["id"],
                marker_filename=marker,
            )
            api_result = import_reports_zip(session, blob)
        except (VCFOpsError, VCFOpsReportsError) as exc:
            for rd in reports:
                result.items.append(
                    ItemResult(name=rd.name, status="failed", message=str(exc))
                )
            return result

        state = api_result.get("state", "")
        for rd in reports:
            if state == "FINISHED":
                result.items.append(ItemResult(name=rd.name, status="ok"))
            else:
                result.items.append(
                    ItemResult(
                        name=rd.name,
                        status="warn",
                        message=f"import state={state}",
                    )
                )
        return result

    def delete(
        self,
        names: List[str],
        session: VCFOpsClient,
        force: bool = False,
    ) -> DeleteResult:
        """Report definitions cannot be deleted via the API.

        The public REST API has no DELETE on /api/reportdefinitions and the
        internal API has no equivalent endpoint.  This handler marks every
        requested deletion as 'skipped' with a guidance message so bundle
        uninstall does not abort, while clearly informing the caller that
        manual action is required.
        """
        result = DeleteResult(content_type=self.content_type)
        for name in names:
            result.items.append(
                ItemResult(
                    name=name,
                    status="skipped",
                    message=(
                        "Report definitions cannot be deleted via the API. "
                        "Remove via Ops UI: Administration > Content > Reports."
                    ),
                )
            )
        return result


HANDLER = ReportsHandler()
