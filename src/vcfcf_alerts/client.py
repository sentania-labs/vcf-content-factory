"""VCF Operations Suite API client for alert definition management.

Alert definitions use direct REST (not content-zip) because they are
identified by name; the server assigns id on create.

Endpoints used:
  GET    /api/alertdefinitions            list (paged)
  GET    /api/alertdefinitions/{id}       fetch one
  POST   /api/alertdefinitions            create
  PUT    /api/alertdefinitions            update (id in body)
  DELETE /api/alertdefinitions/{id}       delete
  PUT    /api/alertdefinitions/{id}/enable   enable
  PUT    /api/alertdefinitions/{id}/disable  disable

Symptom name resolution:
  GET    /api/symptomdefinitions          used to build name→id map at sync time
"""
from __future__ import annotations

from typing import Dict, Iterator, Optional

from vcfops_common.client import VCFOpsClient, VCFOpsError


class VCFOpsAlertsError(VCFOpsError):
    pass


class VCFOpsAlertsClient(VCFOpsClient):
    """VCFOpsClient subclass with alert definition helpers."""

    def list_alerts(self, page_size: int = 1000) -> Iterator[dict]:
        page = 0
        while True:
            r = self._request(
                "GET",
                "/api/alertdefinitions",
                params={"page": page, "pageSize": page_size},
            )
            if r.status_code != 200:
                raise VCFOpsAlertsError(
                    f"list failed ({r.status_code}): {r.text}"
                )
            body = r.json()
            items = body.get("alertDefinitions") or []
            for item in items:
                yield item
            info = body.get("pageInfo") or {}
            total = info.get("totalCount", len(items))
            if (page + 1) * page_size >= total or not items:
                return
            page += 1

    def find_by_name(self, name: str) -> Optional[dict]:
        """Return the first alert definition with matching name, or None."""
        for ad in self.list_alerts():
            if ad.get("name") == name:
                return ad
        return None

    def get_symptom_name_to_id_map(self, page_size: int = 1000) -> Dict[str, str]:
        """Fetch all symptom definitions and return a name→id mapping.

        Used at alert sync time to resolve YAML symptom name references
        to the server-assigned IDs that the alert definition wire format
        requires.
        """
        result: Dict[str, str] = {}
        page = 0
        while True:
            r = self._request(
                "GET",
                "/api/symptomdefinitions",
                params={"page": page, "pageSize": page_size},
            )
            if r.status_code != 200:
                raise VCFOpsAlertsError(
                    f"symptom list failed ({r.status_code}): {r.text}"
                )
            body = r.json()
            items = body.get("symptomDefinitions") or []
            for sd in items:
                sid = sd.get("id")
                sname = sd.get("name")
                if sid and sname:
                    result[sname] = sid
            info = body.get("pageInfo") or {}
            total = info.get("totalCount", len(items))
            if (page + 1) * page_size >= total or not items:
                return result
            page += 1

    def create_alert(self, body: dict) -> dict:
        """POST a new alert definition. id must be absent or null."""
        r = self._request("POST", "/api/alertdefinitions", json=body)
        if r.status_code not in (200, 201):
            raise VCFOpsAlertsError(
                f"create alert failed ({r.status_code}): {r.text}"
            )
        return r.json()

    def update_alert(self, alert_id: str, body: dict) -> dict:
        """PUT an existing alert definition. id must be set in body."""
        body = dict(body)
        body["id"] = alert_id
        r = self._request("PUT", "/api/alertdefinitions", json=body)
        if r.status_code != 200:
            raise VCFOpsAlertsError(
                f"update alert failed ({r.status_code}): {r.text}"
            )
        return r.json()

    def upsert_alert(
        self, body: dict
    ) -> tuple[str, dict]:
        """Create or update by name. Returns ('created'|'updated', alert_dict)."""
        existing = self.find_by_name(body["name"])
        if existing:
            updated = self.update_alert(existing["id"], body)
            return ("updated", updated)
        created = self.create_alert(body)
        return ("created", created)

    def delete_alert(self, alert_id: str) -> None:
        r = self._request("DELETE", f"/api/alertdefinitions/{alert_id}")
        if r.status_code not in (200, 204):
            raise VCFOpsAlertsError(
                f"delete failed ({r.status_code}): {r.text}"
            )

    def enable_alert(self, alert_id: str) -> None:
        r = self._request("PUT", f"/api/alertdefinitions/{alert_id}/enable")
        if r.status_code != 200:
            raise VCFOpsAlertsError(
                f"enable failed ({r.status_code}): {r.text}"
            )

    def disable_alert(self, alert_id: str) -> None:
        r = self._request("PUT", f"/api/alertdefinitions/{alert_id}/disable")
        if r.status_code != 200:
            raise VCFOpsAlertsError(
                f"disable failed ({r.status_code}): {r.text}"
            )
