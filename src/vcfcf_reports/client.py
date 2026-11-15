"""REST client for VCF Operations report definition management.

Report definitions are created/updated exclusively via content-zip import
(POST /api/content/operations/import).  There is no POST or PUT on
/api/reportdefinitions — the public API is read-only for definitions.

The internal API has no relevant report-definition endpoints either
(confirmed by grepping reference/docs/internal-api.json for "report").

Delete limitation:
    There is no DELETE on /api/reportdefinitions and no internal API
    equivalent.  Report definitions can only be deleted through the Ops UI.
    The delete() method on this client therefore raises NotImplementedError
    and the CLI surfaces this as an informational message.

The import flow reuses the polling logic from vcfcf_dashboards.client —
both use the same /api/content/operations/import endpoint.
"""
from __future__ import annotations

from typing import Iterator, Optional

from vcfcf_dashboards.client import (
    discover_marker_filename,
    get_current_user,
    import_content_zip,
)
from vcfcf_common.client import VCFOpsClient, VCFOpsError


class VCFOpsReportsError(RuntimeError):
    pass


def list_reports(client: VCFOpsClient, page_size: int = 1000) -> Iterator[dict]:
    """Iterate over all report definitions via GET /api/reportdefinitions (paged)."""
    page = 0
    while True:
        r = client._request(
            "GET",
            "/api/reportdefinitions",
            params={"page": page, "pageSize": page_size},
        )
        if r.status_code != 200:
            raise VCFOpsReportsError(
                f"list reportdefinitions failed ({r.status_code}): {r.text}"
            )
        body = r.json()
        # The API wraps items under "reportDefinitions"
        items = body.get("reportDefinitions") or []
        for item in items:
            yield item
        page_info = body.get("pageInfo") or {}
        total = page_info.get("totalCount", len(items))
        if (page + 1) * page_size >= total or not items:
            return
        page += 1


def find_by_name(client: VCFOpsClient, name: str) -> Optional[dict]:
    """Return the first report definition with the given name, or None."""
    for rd in list_reports(client):
        if rd.get("name") == name:
            return rd
    return None


def plan_report_import(client: VCFOpsClient, reports, *, omission_notes: bool = True) -> "tuple":
    """``(reports, refusal, notes)`` for a content import of ``reports`` on
    ``client``, the report counterpart of
    ``vcfcf_dashboards.client.plan_dashboard_import``.

    ``reports``: the input, except that each report listing a feature in
    ``feature_fallback`` is its variant without it when the instance is
    below the feature's floor (CoverPage ``font_color``: 9.0.2) or its
    version cannot be read (``unknown_target="omit"``, as for Section).
    ``refusal``: a report keeps a feature on a build measured to refuse it
    (8.18.7 for font_color); the caller must not import.
    ``notes``: one ``FEATURE OMITTED`` line per omission (unless
    ``omission_notes=False``), then any WARNING under which the import goes
    ahead. No request is made and nothing changes when no report carries a
    floored feature.
    """
    from vcfcf_core.reports.loader import apply_feature_fallback, feature_import_check
    from vcfcf_dashboards.client import get_ops_version
    reports = list(reports)
    if not any(r.features_used() for r in reports):
        return reports, None, []
    version = get_ops_version(client)
    planned, notes = apply_feature_fallback(reports, version, unknown_target="omit")
    if not omission_notes:
        notes = []
    refusal, warning = feature_import_check(planned, version)
    return planned, refusal, notes + ([warning] if warning else [])


def import_reports_zip(
    client: VCFOpsClient,
    zip_bytes: bytes,
    timeout_s: int = 180,
) -> dict:
    """POST a reports content-zip to the import endpoint and poll for completion.

    This is a thin wrapper over the shared import_content_zip helper from
    vcfcf_dashboards.client — both reports and dashboards use the same
    /api/content/operations/import endpoint and the same polling protocol.
    """
    return import_content_zip(client, zip_bytes, timeout_s=timeout_s)


def delete_report(client: VCFOpsClient, report_id: str) -> None:
    """Delete a report definition.

    NOTE: Neither the public API nor the internal API exposes a DELETE endpoint
    for /api/reportdefinitions.  This method raises NotImplementedError.
    Report definitions can only be removed through the VCF Operations web UI
    (Admin > Content > Reports).

    This limitation is documented in knowledge/context/api-surface/reports_api_surface.md.
    """
    raise NotImplementedError(
        "The VCF Operations API has no DELETE endpoint for report definitions. "
        "Remove report definitions via the Ops web UI: "
        "Administration > Content > Reports."
    )
