"""Minimal VCF Operations Suite API client for super metric management.

Auth: POST /api/auth/token/acquire returns a token. Subsequent calls send
`Authorization: vRealizeOpsToken <token>`. Token TTL is sliding (6h from
last call).

SuperMetric endpoints used:
  GET    /api/supermetrics              list (paged)
  GET    /api/supermetrics/{id}         fetch one
  DELETE /api/supermetrics/{id}         delete
  POST   /api/content/operations/import install bundle (UUID-preserving)

Install goes through the content-import zip path, not POST
/api/supermetrics, because the latter reassigns UUIDs server-side and
breaks sm_<uuid> cross-references. See import_supermetrics_bundle.
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from typing import Iterable, Iterator, Optional

import requests

from ._env import load_dotenv


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
        # Cached per-instance content marker filename (discovered via a
        # throwaway export). Re-probing it triggers export<->import task
        # contention, so discover once per client lifetime.
        self._marker_filename: Optional[str] = None

    # ---- env constructor ------------------------------------------------
    @classmethod
    def from_env(cls) -> "VCFOpsClient":
        load_dotenv()
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

    # ---- content-zip import (UUID-preserving) ---------------------------
    def import_supermetrics_bundle(self, supermetrics: Iterable[dict]) -> dict:
        """Install super metrics via the content import endpoint, which
        preserves caller-supplied UUIDs verbatim.

        Each dict must carry: id, name, formula, description, unitId,
        resourceKinds=[{resourceKindKey, adapterKindKey}, ...]. Unlike
        POST /api/supermetrics, this path keeps ``sm_<uuid>`` formula
        cross-references stable across re-installs and across instances.

        Wire format verified by api-explorer against a live instance —
        see context/wire_formats.md §"Super metrics zip".
        """
        # Imported lazily to avoid a hard package dep at import time.
        from vcfops_dashboards.client import (
            discover_marker_filename,
            get_current_user,
            import_content_zip,
        )

        sms = list(supermetrics)
        if not sms:
            raise VCFOpsError("import_supermetrics_bundle: empty bundle")

        owner = get_current_user(self)["id"]
        if self._marker_filename is None:
            self._marker_filename = discover_marker_filename(self)
        marker = self._marker_filename

        sm_dict: dict = {}
        for sm in sms:
            sm_id = sm.get("id")
            if not sm_id:
                raise VCFOpsError(
                    f"super metric '{sm.get('name')}' has no id — cannot "
                    f"round-trip via content-zip import"
                )
            sm_dict[sm_id] = {
                "name": sm["name"],
                "formula": self._normalize_formula(sm["formula"]),
                "description": sm.get("description", "") or "",
                "unitId": sm.get("unitId", "") or "",
                "resourceKinds": sm.get("resourceKinds") or [],
            }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(marker, owner)
            z.writestr("supermetrics.json", json.dumps(sm_dict, indent=3))
            z.writestr(
                "configuration.json",
                json.dumps({"superMetrics": len(sm_dict), "type": "ALL"}, indent=3),
            )
        return import_content_zip(self, buf.getvalue())

    def delete_supermetric(self, sm_id: str) -> None:
        r = self._request("DELETE", f"/api/supermetrics/{sm_id}")
        if r.status_code not in (200, 204):
            raise VCFOpsError(f"delete failed ({r.status_code}): {r.text}")
