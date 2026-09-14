"""Content handler for super metrics (vcfops_packaging sync integration).

Exposes a module-level HANDLER instance that the vcfops_packaging sync
orchestrator discovers automatically.
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

from .client import VCFOpsClient, VCFOpsError
from .loader import SuperMetricValidationError, load_file


class SuperMetricsHandler(ContentHandler):
    content_type = "supermetrics"
    sync_order = 1

    def validate(self, yaml_paths: List[str]) -> ValidateResult:
        result = ValidateResult(content_type=self.content_type)
        for p in yaml_paths:
            try:
                sm = load_file(Path(p))
                result.items.append(ItemResult(name=sm.name, status="ok"))
            except (SuperMetricValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )
        return result

    def sync(self, yaml_paths: List[str], session: VCFOpsClient) -> SyncResult:
        result = SyncResult(content_type=self.content_type)
        bundle = []
        for p in yaml_paths:
            try:
                sm = load_file(Path(p))
                bundle.append({
                    "id": sm.id,
                    "name": sm.name,
                    "formula": sm.formula,
                    "description": sm.description,
                    "unitId": sm.unit_id,
                    "resourceKinds": sm.resource_kinds,
                })
            except (SuperMetricValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )

        if not bundle:
            return result

        try:
            api_result = session.import_supermetrics_bundle(bundle)
        except VCFOpsError as exc:
            for entry in bundle:
                result.items.append(
                    ItemResult(name=entry["name"], status="failed", message=str(exc))
                )
            return result

        # Report per-item results based on import summary
        summaries = api_result.get("operationSummaries") or []
        imported = sum(int(s.get("imported") or 0) for s in summaries)
        failed = sum(int(s.get("failed") or 0) for s in summaries)
        errors = [
            msg
            for s in summaries
            for msg in (s.get("errorMessages") or [])
        ]

        for entry in bundle:
            if failed > 0 and errors:
                result.items.append(
                    ItemResult(
                        name=entry["name"],
                        status="warn",
                        message="; ".join(errors[:2]),
                    )
                )
            else:
                result.items.append(
                    ItemResult(name=entry["name"], status="ok")
                )
        return result

    def delete(
        self,
        names: List[str],
        session: VCFOpsClient,
        force: bool = False,
    ) -> DeleteResult:
        result = DeleteResult(content_type=self.content_type)
        for name in names:
            try:
                sm = session.find_by_name(name)
                if sm is None:
                    result.items.append(
                        ItemResult(name=name, status="skipped",
                                   message="not found on instance")
                    )
                    continue
                # DELETE returns 409 when SM is still referenced by a view/formula
                r = session._request("DELETE", f"/api/supermetrics/{sm['id']}")
                if r.status_code in (200, 204):
                    result.items.append(ItemResult(name=name, status="ok"))
                elif r.status_code == 409:
                    if force:
                        # Force: still can't delete a referenced SM via the API.
                        # Report as warn — the caller may want to clean up views first.
                        result.items.append(
                            ItemResult(
                                name=name,
                                status="warn",
                                message="409 Conflict: still referenced by other content; "
                                        "delete dependents first",
                            )
                        )
                    else:
                        result.items.append(
                            ItemResult(
                                name=name,
                                status="skipped",
                                message="referenced by other content (use --force to attempt deletion)",
                            )
                        )
                else:
                    result.items.append(
                        ItemResult(
                            name=name,
                            status="failed",
                            message=f"HTTP {r.status_code}: {r.text[:120]}",
                        )
                    )
            except VCFOpsError as exc:
                result.items.append(
                    ItemResult(name=name, status="failed", message=str(exc))
                )
        return result


HANDLER = SuperMetricsHandler()
