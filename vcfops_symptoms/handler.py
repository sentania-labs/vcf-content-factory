"""Content handler for symptom definitions (vcfops_packaging sync integration).

Exposes a module-level HANDLER instance that the vcfops_packaging sync
orchestrator discovers automatically.

Sync order 5 — after supermetrics (1), customgroups (2), views (3),
dashboards (4); before alerts (6).
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

from .client import VCFOpsSymptomsClient, VCFOpsSymptomsError
from .loader import SymptomValidationError, load_file


class SymptomsHandler(ContentHandler):
    content_type = "symptoms"
    sync_order = 5

    def validate(self, yaml_paths: List[str]) -> ValidateResult:
        result = ValidateResult(content_type=self.content_type)
        for p in yaml_paths:
            try:
                sd = load_file(Path(p))
                result.items.append(ItemResult(name=sd.name, status="ok"))
            except (SymptomValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )
        return result

    def sync(self, yaml_paths: List[str], session) -> SyncResult:  # noqa: ANN001
        result = SyncResult(content_type=self.content_type)
        # Use a fresh symptoms client — the session object is a VCFOpsClient
        # and is not compatible with this package's client type.
        try:
            client = VCFOpsSymptomsClient.from_env()
        except VCFOpsSymptomsError as exc:
            result.items.append(
                ItemResult(name="(auth)", status="failed", message=str(exc))
            )
            return result

        for p in yaml_paths:
            try:
                sd = load_file(Path(p))
            except (SymptomValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )
                continue
            try:
                action, _ = client.upsert_symptom(sd.to_wire())
                result.items.append(
                    ItemResult(name=sd.name, status="ok", message=action)
                )
            except VCFOpsSymptomsError as exc:
                result.items.append(
                    ItemResult(name=sd.name, status="failed", message=str(exc))
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
            client = VCFOpsSymptomsClient.from_env()
        except VCFOpsSymptomsError as exc:
            result.items.append(
                ItemResult(name="(auth)", status="failed", message=str(exc))
            )
            return result

        for name in names:
            try:
                sd = client.find_by_name(name)
                if sd is None:
                    result.items.append(
                        ItemResult(
                            name=name,
                            status="skipped",
                            message="not found on instance",
                        )
                    )
                    continue
                client.delete_symptom(sd["id"])
                result.items.append(ItemResult(name=name, status="ok"))
            except VCFOpsSymptomsError as exc:
                result.items.append(
                    ItemResult(name=name, status="failed", message=str(exc))
                )
        return result


HANDLER = SymptomsHandler()
