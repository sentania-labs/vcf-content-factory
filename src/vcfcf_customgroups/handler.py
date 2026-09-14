"""Content handler for custom groups (vcfops_packaging sync integration).

Exposes a module-level HANDLER instance that the vcfops_packaging sync
orchestrator discovers automatically.
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

from .client import VCFOpsCustomGroupClient, VCFOpsCustomGroupError
from .loader import CustomGroupValidationError, collect_required_types, load_file


class CustomGroupsHandler(ContentHandler):
    content_type = "customgroups"
    sync_order = 2

    def validate(self, yaml_paths: List[str]) -> ValidateResult:
        result = ValidateResult(content_type=self.content_type)
        for p in yaml_paths:
            try:
                cg = load_file(Path(p))
                result.items.append(ItemResult(name=cg.name, status="ok"))
            except (CustomGroupValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )
        return result

    def sync(self, yaml_paths: List[str], session) -> SyncResult:  # noqa: ANN001
        # Custom groups use their own client (not the SM client session)
        result = SyncResult(content_type=self.content_type)
        defs = []
        for p in yaml_paths:
            try:
                cg = load_file(Path(p))
                defs.append(cg)
            except (CustomGroupValidationError, Exception) as exc:
                result.items.append(
                    ItemResult(name=p, status="failed", message=str(exc))
                )

        if not defs:
            return result

        try:
            client = VCFOpsCustomGroupClient.from_env()
        except VCFOpsCustomGroupError as exc:
            for d in defs:
                result.items.append(
                    ItemResult(name=d.name, status="failed", message=str(exc))
                )
            return result

        # Step 1: ensure required group types exist
        try:
            for type_key in collect_required_types(defs):
                client.ensure_group_type(type_key)
        except VCFOpsCustomGroupError as exc:
            for d in defs:
                result.items.append(
                    ItemResult(name=d.name, status="failed",
                               message=f"group type error: {exc}")
                )
            return result

        # Step 2: upsert each group
        for d in defs:
            try:
                client.upsert_group(d.to_wire())
                result.items.append(ItemResult(name=d.name, status="ok"))
            except VCFOpsCustomGroupError as exc:
                result.items.append(
                    ItemResult(name=d.name, status="failed", message=str(exc))
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
            client = VCFOpsCustomGroupClient.from_env()
        except VCFOpsCustomGroupError as exc:
            for name in names:
                result.items.append(
                    ItemResult(name=name, status="failed", message=str(exc))
                )
            return result

        for name in names:
            try:
                g = client.find_group_by_name(name)
                if g is None:
                    result.items.append(
                        ItemResult(name=name, status="skipped",
                                   message="not found on instance")
                    )
                    continue
                client.delete_group(g["id"])
                result.items.append(ItemResult(name=name, status="ok"))
            except VCFOpsCustomGroupError as exc:
                result.items.append(
                    ItemResult(name=name, status="failed", message=str(exc))
                )
        return result


HANDLER = CustomGroupsHandler()
