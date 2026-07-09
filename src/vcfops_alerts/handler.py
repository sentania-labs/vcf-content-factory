"""Content handler for alert definitions (vcfops_packaging sync integration).

Exposes a module-level HANDLER instance that the vcfops_packaging sync
orchestrator discovers automatically.

Sync order 6 — after symptoms (5).  Alerts reference symptoms by name
so symptoms must be synced first to ensure all ids are resolvable.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from vcfops_packaging.handler import (
    ContentHandler,
    DeleteResult,
    ItemResult,
    SyncResult,
    ValidateResult,
)

from .client import VCFOpsAlertsClient, VCFOpsAlertsError
from .loader import AlertDef, AlertValidationError, load_file


class AlertsHandler(ContentHandler):
    content_type = "alerts"
    sync_order = 6

    def validate(self, yaml_paths: List[str]) -> ValidateResult:
        result = ValidateResult(content_type=self.content_type)
        for p in yaml_paths:
            try:
                ad = load_file(Path(p))
                result.items.append(ItemResult(name=ad.name, status="ok"))
            except (AlertValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )
        return result

    def sync(self, yaml_paths: List[str], session) -> SyncResult:  # noqa: ANN001
        result = SyncResult(content_type=self.content_type)
        try:
            client = VCFOpsAlertsClient.from_env()
        except VCFOpsAlertsError as exc:
            result.items.append(
                ItemResult(name="(auth)", status="failed", message=str(exc))
            )
            return result

        # Resolve symptom names to ids once for the whole batch.
        try:
            sym_map = client.get_symptom_name_to_id_map()
        except VCFOpsAlertsError as exc:
            result.items.append(
                ItemResult(
                    name="(symptom-resolution)",
                    status="failed",
                    message=str(exc),
                )
            )
            return result

        for p in yaml_paths:
            try:
                ad = load_file(Path(p))
            except (AlertValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )
                continue
            try:
                wire = ad.to_wire(sym_map)
                action, _ = client.upsert_alert(wire)
                result.items.append(
                    ItemResult(name=ad.name, status="ok", message=action)
                )
            except (AlertValidationError, VCFOpsAlertsError) as exc:
                result.items.append(
                    ItemResult(name=ad.name, status="failed", message=str(exc))
                )
        return result

    def delete(
        self,
        names: List[str],
        session,  # noqa: ANN001
        force: bool = False,
    ) -> DeleteResult:
        result = DeleteResult(content_type=self.content_type)
        try:
            client = VCFOpsAlertsClient.from_env()
        except VCFOpsAlertsError as exc:
            result.items.append(
                ItemResult(name="(auth)", status="failed", message=str(exc))
            )
            return result

        for name in names:
            try:
                ad = client.find_by_name(name)
                if ad is None:
                    result.items.append(
                        ItemResult(
                            name=name,
                            status="skipped",
                            message="not found on instance",
                        )
                    )
                    continue
                client.delete_alert(ad["id"])
                result.items.append(ItemResult(name=name, status="ok"))
            except VCFOpsAlertsError as exc:
                result.items.append(
                    ItemResult(name=name, status="failed", message=str(exc))
                )
        return result


HANDLER = AlertsHandler()
