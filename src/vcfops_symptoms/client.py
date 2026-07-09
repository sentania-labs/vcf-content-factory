"""VCF Operations Suite API client for symptom definition management.

Symptom definitions use direct REST, not the content-zip import path,
because they are identified by name (server assigns id on create) and
have no UUID stability requirement.

Endpoints used:
  GET    /api/symptomdefinitions            list (paged)
  GET    /api/symptomdefinitions/{id}       fetch one
  POST   /api/symptomdefinitions            create
  PUT    /api/symptomdefinitions            update (id in body)
  DELETE /api/symptomdefinitions/{id}       delete
"""
from __future__ import annotations

from typing import Iterator, Optional

from vcfops_common.client import VCFOpsClient, VCFOpsError


class VCFOpsSymptomsError(VCFOpsError):
    pass


class VCFOpsSymptomsClient(VCFOpsClient):
    """VCFOpsClient subclass with symptom definition helpers."""

    def list_symptoms(self, page_size: int = 1000) -> Iterator[dict]:
        page = 0
        while True:
            r = self._request(
                "GET",
                "/api/symptomdefinitions",
                params={"page": page, "pageSize": page_size},
            )
            if r.status_code != 200:
                raise VCFOpsSymptomsError(
                    f"list failed ({r.status_code}): {r.text}"
                )
            body = r.json()
            items = body.get("symptomDefinitions") or []
            for item in items:
                yield item
            info = body.get("pageInfo") or {}
            total = info.get("totalCount", len(items))
            if (page + 1) * page_size >= total or not items:
                return
            page += 1

    def find_by_name(self, name: str) -> Optional[dict]:
        """Return the first symptom definition with matching name, or None."""
        for sd in self.list_symptoms():
            if sd.get("name") == name:
                return sd
        return None

    def create_symptom(self, body: dict) -> dict:
        """POST a new symptom definition. id must be absent or null."""
        r = self._request("POST", "/api/symptomdefinitions", json=body)
        if r.status_code not in (200, 201):
            raise VCFOpsSymptomsError(
                f"create symptom failed ({r.status_code}): {r.text}"
            )
        return r.json()

    def update_symptom(self, symptom_id: str, body: dict) -> dict:
        """PUT an existing symptom definition. id must be set in body."""
        body = dict(body)
        body["id"] = symptom_id
        r = self._request("PUT", "/api/symptomdefinitions", json=body)
        if r.status_code != 200:
            raise VCFOpsSymptomsError(
                f"update symptom failed ({r.status_code}): {r.text}"
            )
        return r.json()

    def upsert_symptom(self, body: dict) -> tuple[str, dict]:
        """Create or update by name. Returns ('created'|'updated', symptom_dict)."""
        existing = self.find_by_name(body["name"])
        if existing:
            updated = self.update_symptom(existing["id"], body)
            return ("updated", updated)
        created = self.create_symptom(body)
        return ("created", created)

    def delete_symptom(self, symptom_id: str) -> None:
        r = self._request("DELETE", f"/api/symptomdefinitions/{symptom_id}")
        if r.status_code not in (200, 204):
            raise VCFOpsSymptomsError(
                f"delete failed ({r.status_code}): {r.text}"
            )
