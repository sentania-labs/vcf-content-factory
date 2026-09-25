"""Framework-general VCF Operations Suite API base client.

Provides VCFOpsClient and VCFOpsError — the single source of truth for:
  - Constructor (host / username / password / auth_source / verify_ssl)
  - authenticate()  — POST /api/auth/token/acquire
  - _request(method, path, ...)  — session request with 401 re-auth
  - from_env() classmethod

Supermetric-specific helpers (policy enable/export/import, SM enable,
built-in metric enable) live in vcfcf_supermetrics.client and operate
on a VCFOpsClient instance.

All other package clients (dashboards, reports, customgroups, symptoms,
alerts) import VCFOpsClient from here rather than from
vcfcf_supermetrics.client, removing the "supermetrics happens to own
the base" coupling.
"""
from __future__ import annotations

from typing import Optional

import requests

from ._env import load_dotenv, resolve_profile_credentials


class VCFOpsError(RuntimeError):
    pass


class VerifyRespectingSession(requests.Session):
    """A ``requests.Session`` whose ``verify=False`` survives the environment.

    Plain ``requests`` lets ``REQUESTS_CA_BUNDLE`` / ``CURL_CA_BUNDLE`` override
    ``Session.verify = False``: when a request does not pass ``verify=`` itself,
    ``merge_environment_settings`` swaps in the env bundle path before it merges
    the session value, so the session's ``False`` loses (issue #174). A profile
    with ``VERIFY_SSL=false`` then fails against a private-CA appliance whenever
    the shell exports a CA bundle.

    Here, a session set to ``verify=False`` with no per-request ``verify``
    stays ``False``. Everything else is unchanged: ``verify=True`` still picks
    up the env CA bundle, a per-request ``verify=`` still wins, and proxy
    handling (``trust_env``) is untouched.
    """

    def merge_environment_settings(self, url, proxies, stream, verify, cert):
        if verify is None and self.verify is False:
            verify = False
        return super().merge_environment_settings(url, proxies, stream, verify, cert)


def new_session(verify_ssl: bool = True) -> requests.Session:
    """Return a :class:`VerifyRespectingSession` with ``verify`` set.

    Use this for every Suite API / UI session in ``src/vcfcf_*`` so an explicit
    ``VERIFY_SSL=false`` always wins over ``REQUESTS_CA_BUNDLE``.
    """
    s = VerifyRespectingSession()
    s.verify = verify_ssl
    return s


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
        self._session = new_session(verify_ssl)
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
    def from_env(cls, profile: Optional[str] = None, *, default_profile: str = "prod") -> "VCFOpsClient":
        """Construct a client from the active credential profile.

        Profile resolution order:
          1. ``profile`` argument if non-None/non-empty.
          2. ``VCFOPS_PROFILE`` env var.
          3. ``default_profile`` argument (caller sets per-command default).
          4. ``"prod"`` as the hard fallback.

        Raises ``VCFOpsError`` if required env vars for the resolved profile
        are missing (includes a list of available profiles in the message).
        """
        try:
            creds = resolve_profile_credentials(profile, default=default_profile)
        except ValueError as e:
            raise VCFOpsError(str(e)) from None
        return cls(
            host=creds.host,
            username=creds.user,
            password=creds.password,
            auth_source=creds.auth_source,
            verify_ssl=creds.verify_ssl,
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
