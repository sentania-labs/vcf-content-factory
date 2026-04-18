"""REST client for VCF Operations report definition management.

Report definitions are created/updated exclusively via content-zip import
(POST /api/content/operations/import).  There is no POST or PUT on
/api/reportdefinitions — the public API is read-only for definitions.

The internal API has no relevant report-definition endpoints either
(confirmed by grepping docs/internal-api.json for "report").

Delete limitation:
    There is no DELETE on /api/reportdefinitions and no internal API
    equivalent.  Report definitions can only be deleted through the Ops UI.
    The delete() method on this client therefore raises NotImplementedError
    and the CLI surfaces this as an informational message.

The import flow reuses the polling logic from vcfops_dashboards.client —
both use the same /api/content/operations/import endpoint.
"""
from __future__ import annotations

from typing import Iterator, Optional

from vcfops_dashboards.client import (
    discover_marker_filename,
    get_current_user,
    import_content_zip,
)
from vcfops_common.client import VCFOpsClient, VCFOpsError


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


def import_reports_zip(
    client: VCFOpsClient,
    zip_bytes: bytes,
    timeout_s: int = 180,
) -> dict:
    """POST a reports content-zip to the import endpoint and poll for completion.

    This is a thin wrapper over the shared import_content_zip helper from
    vcfops_dashboards.client — both reports and dashboards use the same
    /api/content/operations/import endpoint and the same polling protocol.
    """
    return import_content_zip(client, zip_bytes, timeout_s=timeout_s)


def delete_report(client: VCFOpsClient, report_id: str) -> None:
    """Delete a report definition.

    NOTE: Neither the public API nor the internal API exposes a DELETE endpoint
    for /api/reportdefinitions.  This method raises NotImplementedError.
    Report definitions can only be removed through the VCF Operations web UI
    (Admin > Content > Reports).

    This limitation is documented in context/reports_api_surface.md.
    """
    raise NotImplementedError(
        "The VCF Operations API has no DELETE endpoint for report definitions. "
        "Remove report definitions via the Ops web UI: "
        "Administration > Content > Reports."
    )
