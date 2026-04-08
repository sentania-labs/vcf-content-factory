"""Minimal VCF Operations Suite API client for super metric management.

Auth: POST /api/auth/token/acquire returns a token. Subsequent calls send
`Authorization: vRealizeOpsToken <token>`. Token TTL is sliding (6h from
last call).

SuperMetric endpoints used:
  GET    /api/supermetrics              list (paged)
  POST   /api/supermetrics              create
  PUT    /api/supermetrics              update (id required)
  GET    /api/supermetrics/{id}         fetch one
  DELETE /api/supermetrics/{id}         delete
"""
from __future__ import annotations

import os
from typing import Iterator, Optional

import requests


class VCFOpsError(RuntimeError):
    pass


class VCFOpsClient:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        auth_source: str = "Local",
        verify_ssl: bool = True,
    ):
        self.base = f"https://{host}/suite-api"
        self._username = username
        self._password = password
        self._auth_source = auth_source
        self._session = requests.Session()
        self._session.verify = verify_ssl
        self._session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )
        self._token: Optional[str] = None

    # ---- env constructor ------------------------------------------------
    @classmethod
    def from_env(cls) -> "VCFOpsClient":
        try:
            host = os.environ["VCFOPS_HOST"]
            user = os.environ["VCFOPS_USER"]
            pw = os.environ["VCFOPS_PASSWORD"]
        except KeyError as e:
            raise VCFOpsError(f"Missing env var: {e.args[0]}") from None
        return cls(
            host=host,
            username=user,
            password=pw,
            auth_source=os.environ.get("VCFOPS_AUTH_SOURCE", "Local"),
            verify_ssl=os.environ.get("VCFOPS_VERIFY_SSL", "true").lower() != "false",
        )

    # ---- auth -----------------------------------------------------------
    def authenticate(self) -> None:
        r = self._session.post(
            f"{self.base}/api/auth/token/acquire",
            json={
                "username": self._username,
                "password": self._password,
                "authSource": self._auth_source,
            },
        )
        if r.status_code != 200:
            raise VCFOpsError(f"auth failed ({r.status_code}): {r.text}")
        self._token = r.json()["token"]
        self._session.headers["Authorization"] = f"vRealizeOpsToken {self._token}"

    def _ensure_auth(self) -> None:
        if not self._token:
            self.authenticate()

    def _request(self, method: str, path: str, **kw) -> requests.Response:
        self._ensure_auth()
        r = self._session.request(method, f"{self.base}{path}", **kw)
        if r.status_code == 401:  # token expired -> reauth once
            self._token = None
            self._ensure_auth()
            r = self._session.request(method, f"{self.base}{path}", **kw)
        return r

    # ---- super metrics --------------------------------------------------
    def list_supermetrics(self, page_size: int = 1000) -> Iterator[dict]:
        page = 0
        while True:
            r = self._request(
                "GET",
                "/api/supermetrics",
                params={"page": page, "pageSize": page_size},
            )
            if r.status_code != 200:
                raise VCFOpsError(f"list failed ({r.status_code}): {r.text}")
            body = r.json()
            items = body.get("superMetrics") or []
            for it in items:
                yield it
            info = body.get("pageInfo") or {}
            total = info.get("totalCount", len(items))
            if (page + 1) * page_size >= total or not items:
                return
            page += 1

    def get_supermetric(self, sm_id: str) -> dict:
        r = self._request("GET", f"/api/supermetrics/{sm_id}")
        if r.status_code != 200:
            raise VCFOpsError(f"get failed ({r.status_code}): {r.text}")
        return r.json()

    def find_by_name(self, name: str) -> Optional[dict]:
        r = self._request("GET", "/api/supermetrics", params={"name": name})
        if r.status_code != 200:
            raise VCFOpsError(f"find failed ({r.status_code}): {r.text}")
        for sm in r.json().get("superMetrics") or []:
            if sm.get("name") == name:
                return sm
        return None

    @staticmethod
    def _normalize_formula(formula: str) -> str:
        # API rejects newlines / multi-line formulas: collapse all whitespace.
        return " ".join(formula.split())

    def create_supermetric(
        self,
        name: str,
        formula: str,
        description: str = "",
        resource_kinds: list | None = None,
    ) -> dict:
        body = {
            "name": name,
            "formula": self._normalize_formula(formula),
            "description": description,
            "resourceKinds": resource_kinds or [],
        }
        r = self._request("POST", "/api/supermetrics", json=body)
        if r.status_code not in (200, 201):
            raise VCFOpsError(f"create failed ({r.status_code}): {r.text}")
        return r.json()

    def update_supermetric(
        self,
        sm_id: str,
        name: str,
        formula: str,
        description: str = "",
        resource_kinds: list | None = None,
    ) -> dict:
        body = {
            "id": sm_id,
            "name": name,
            "formula": self._normalize_formula(formula),
            "description": description,
            "resourceKinds": resource_kinds or [],
        }
        r = self._request("PUT", "/api/supermetrics", json=body)
        if r.status_code != 200:
            raise VCFOpsError(f"update failed ({r.status_code}): {r.text}")
        return r.json()

    # ---- policies -------------------------------------------------------
    def get_default_policy_id(self) -> str:
        r = self._request("GET", "/api/policies")
        if r.status_code != 200:
            raise VCFOpsError(f"policy list failed ({r.status_code}): {r.text}")
        for p in r.json().get("policySummaries") or []:
            if p.get("defaultPolicy"):
                return p["id"]
        raise VCFOpsError("no default policy found in /api/policies response")

    def enable_supermetric_on_default_policy(
        self,
        sm_id: str,
        resource_kinds: list,
    ) -> None:
        """Assign a super metric to resource kinds and enable it in the
        Default Policy via the internal assign endpoint.

        See context/internal_supermetrics_assign.md. This endpoint only
        accepts the Default Policy id in its policyIds query param —
        non-default policies return 400 apiErrorCode 1501.
        """
        if not resource_kinds:
            raise VCFOpsError("enable requires at least one resource kind")
        policy_id = self.get_default_policy_id()
        body = {
            "superMetricId": sm_id,
            "resourceKindKeys": [
                {
                    "adapterKind": rk.get("adapterKindKey") or rk.get("adapterKind"),
                    "resourceKind": rk.get("resourceKindKey") or rk.get("resourceKind"),
                }
                for rk in resource_kinds
            ],
        }
        r = self._request(
            "PUT",
            "/internal/supermetrics/assign",
            params=[("policyIds", policy_id)],
            json=body,
            headers={"X-Ops-API-use-unsupported": "true"},
        )
        if r.status_code != 200:
            raise VCFOpsError(f"enable failed ({r.status_code}): {r.text}")

    def delete_supermetric(self, sm_id: str) -> None:
        r = self._request("DELETE", f"/api/supermetrics/{sm_id}")
        if r.status_code not in (200, 204):
            raise VCFOpsError(f"delete failed ({r.status_code}): {r.text}")

    def upsert(
        self,
        name: str,
        formula: str,
        description: str = "",
        resource_kinds: list | None = None,
    ) -> tuple[str, dict]:
        """Create or update by name. Returns (action, supermetric)."""
        existing = self.find_by_name(name)
        if existing:
            sm = self.update_supermetric(
                existing["id"], name, formula, description, resource_kinds
            )
            return ("updated", sm)
        sm = self.create_supermetric(name, formula, description, resource_kinds)
        return ("created", sm)
