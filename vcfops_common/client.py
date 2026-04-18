"""Framework-general VCF Operations Suite API base client.

Provides VCFOpsClient and VCFOpsError — the single source of truth for:
  - Constructor (host / username / password / auth_source / verify_ssl)
  - authenticate()  — POST /api/auth/token/acquire
  - _request(method, path, ...)  — session request with 401 re-auth
  - from_env() classmethod

Supermetric-specific helpers (policy enable/export/import, SM enable,
built-in metric enable) live in vcfops_supermetrics.client and operate
on a VCFOpsClient instance.

All other package clients (dashboards, reports, customgroups, symptoms,
alerts) import VCFOpsClient from here rather than from
vcfops_supermetrics.client, removing the "supermetrics happens to own
the base" coupling.
"""
from __future__ import annotations

import os
from typing import Optional

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
