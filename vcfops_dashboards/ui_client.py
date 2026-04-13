"""UI session client for VCF Ops dashboard/view delete operations.

These operations use the Struts/.action + Ext.Direct RPC layer that backs
the VCF Operations web console — NOT the Suite API. The two session systems
are completely independent; a Suite API bearer token cannot authenticate to
*.action endpoints.

AUTH FLOW
---------
1. GET /ui/login.action?vcf=1  →  initial JSESSIONID cookie
2. POST /ui/login.action (form-encoded creds)  →  updated JSESSIONID, body "ok"
3. GET /ui/index.action (do NOT follow 302)  →  OPS_SESSION cookie (base64 JSON)
   Extract csrfToken (== secureToken) from the decoded JSON.

SUPPORTABILITY CAVEAT
---------------------
These are **unsupported internal UI endpoints** — not part of any public API
contract. They can change between VCF Ops releases without notice. Tested
against VCF Operations 9.0.2.0 build 25137838.

Credentials are read from environment variables:
  VCFOPS_HOST       — hostname (no scheme)
  VCFOPS_USER       — username
  VCFOPS_PASSWORD   — password
  VCFOPS_AUTH_SOURCE — auth source id (default: localItem for local accounts)
  VCFOPS_VERIFY_SSL — set to "true" to enable SSL verification (default: false)
"""
from __future__ import annotations

import base64
import json
import os

import requests

from vcfops_supermetrics._env import load_dotenv


class UIClientError(RuntimeError):
    pass


class VCFOpsUIClient:
    """Thin UI-session client for dashboard and view delete operations.

    Instantiate via :meth:`from_env` or pass credentials directly. Call
    :meth:`login` before any operation; call :meth:`logout` when done (or
    use as a context manager).

    Example::

        with VCFOpsUIClient.from_env() as ui:
            dashboards = ui.list_dashboards()
            ui.delete_dashboards([("uuid-1", "My Dashboard")])
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        auth_source: str = "localItem",
        verify_ssl: bool = False,
    ):
        self._host = host
        self._username = username
        self._password = password
        self._auth_source = auth_source
        self._verify_ssl = verify_ssl
        self._session: requests.Session | None = None
        self._csrf_token: str | None = None
        self._tid = 1  # monotonically increasing Ext.Direct transaction id

    @classmethod
    def from_env(cls) -> "VCFOpsUIClient":
        """Construct from VCFOPS_* environment variables."""
        load_dotenv()
        try:
            host = os.environ["VCFOPS_HOST"]
            user = os.environ["VCFOPS_USER"]
            pw = os.environ["VCFOPS_PASSWORD"]
        except KeyError as e:
            raise UIClientError(f"Missing env var: {e.args[0]}") from None
        # VCFOPS_AUTH_SOURCE for Suite API is a display name ("Local");
        # for the UI form it must be the authSourceId value ("localItem" for
        # local accounts, or a UUID for SSO/LDAP). Map the common Suite API
        # display name to the UI form value.
        raw_source = os.environ.get("VCFOPS_AUTH_SOURCE", "").strip()
        if not raw_source or raw_source.lower() == "local":
            auth_source = "localItem"
        else:
            auth_source = raw_source
        verify_ssl = os.environ.get("VCFOPS_VERIFY_SSL", "false").lower() == "true"
        return cls(
            host=host,
            username=user,
            password=pw,
            auth_source=auth_source,
            verify_ssl=verify_ssl,
        )

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------
    def __enter__(self) -> "VCFOpsUIClient":
        self.login()
        return self

    def __exit__(self, *_) -> None:
        self.logout()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Authenticate to the VCF Ops UI and capture the CSRF token.

        Three-step flow documented in context/dashboard_delete_api.md:
        1. GET /ui/login.action?vcf=1 — seeds JSESSIONID
        2. POST /ui/login.action (form creds) — validates credentials
        3. GET /ui/index.action (no redirect) — OPS_SESSION cookie with csrfToken

        The OPS_SESSION cookie is base64-encoded JSON. It is set on the 302
        response from step 3 but CLEARED if the redirect is followed — so we
        must capture it without following the redirect.
        """
        s = requests.Session()
        s.verify = self._verify_ssl

        # Step 1: seed JSESSIONID
        s.get(f"https://{self._host}/ui/login.action", params={"vcf": "1"})

        # Step 2: login with credentials
        resp = s.post(
            f"https://{self._host}/ui/login.action",
            data={
                "mainAction": "login",
                "userName": self._username,
                "password": self._password,
                "authSourceId": self._auth_source,
                "authSourceName": "Local Account",
                "authSourceType": "",
                "forceLogin": "false",
                "timezone": "0",
                "languageCode": "us",
            },
        )
        if resp.text.strip() != "ok":
            raise UIClientError(f"UI login failed: {resp.text!r}")

        # Step 3: hit index.action WITHOUT following the 302 redirect.
        # The OPS_SESSION cookie is set on the 302 response and cleared on
        # the redirect target response.
        resp = s.get(
            f"https://{self._host}/ui/index.action",
            allow_redirects=False,
        )
        ops_cookie = resp.cookies.get("OPS_SESSION") or s.cookies.get("OPS_SESSION")
        if not ops_cookie:
            raise UIClientError(
                "OPS_SESSION cookie not received after /ui/index.action — "
                "check credentials and auth source"
            )
        try:
            ops_data = json.loads(base64.b64decode(ops_cookie))
        except Exception as exc:
            raise UIClientError(f"Failed to decode OPS_SESSION cookie: {exc}") from exc
        csrf_token = ops_data.get("csrfToken")
        if not csrf_token:
            raise UIClientError("csrfToken not found in OPS_SESSION payload")

        self._session = s
        self._csrf_token = csrf_token

    def logout(self) -> None:
        """Invalidate the UI session. Safe to call even if not logged in."""
        if self._session is None:
            return
        try:
            self._session.get(
                f"https://{self._host}/ui/login.action",
                params={"mainAction": "logout"},
                allow_redirects=False,
            )
        except Exception:
            pass  # best-effort
        finally:
            self._session = None
            self._csrf_token = None

    def _require_auth(self) -> tuple[requests.Session, str]:
        if self._session is None or self._csrf_token is None:
            raise UIClientError("Not logged in — call login() first")
        return self._session, self._csrf_token

    # ------------------------------------------------------------------
    # Dashboard operations
    # ------------------------------------------------------------------
    def list_dashboards(self) -> list[dict]:
        """Return all dashboards visible to the authenticated user.

        Uses unsupported UI endpoint POST /ui/dashboard.action with
        mainAction=getDashboardList. Each entry has at minimum:
          id, name, description, locked, owner, shared, editable.

        WARNING: unsupported internal endpoint; may change between releases.
        """
        s, csrf = self._require_auth()
        resp = s.post(
            f"https://{self._host}/ui/dashboard.action",
            data={
                "mainAction": "getDashboardList",
                "secureToken": csrf,
                "currentComponentInfo": "TODO",
                "globalDate": json.dumps({"dateRange": "last6Hour"}),
            },
        )
        resp.raise_for_status()
        return resp.json().get("dashboards") or []

    def delete_dashboards(self, dashboards: list[tuple[str, str]]) -> dict:
        """Delete one or more dashboards by (uuid, name) tuples.

        Multiple dashboards can be deleted in a single call. Deleting a
        non-existent UUID is a silent no-op (returns HTTP 200 with the
        full dashboard config).

        WARNING: unsupported internal endpoint; may change between releases.

        Args:
            dashboards: list of (uuid, display_name) tuples.

        Returns:
            The raw JSON response body (full dashboard configuration).
        """
        s, csrf = self._require_auth()
        tab_ids = [{"tabId": uid, "tabName": name} for uid, name in dashboards]
        resp = s.post(
            f"https://{self._host}/ui/dashboard.action",
            data={
                "mainAction": "deleteTab",
                "tabIds": json.dumps(tab_ids),
                "secureToken": csrf,
                "currentComponentInfo": "TODO",
                "globalDate": json.dumps({"dateRange": "last6Hour"}),
            },
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # View operations
    # ------------------------------------------------------------------
    def list_views(self) -> list[dict]:
        """List all view definitions via Ext.Direct RPC.

        Uses viewServiceController.getGroupedViewDefinitionThumbnails
        (no parameters) — returns a grouped list of all views the user
        can see.

        WARNING: unsupported internal endpoint; may change between releases.
        """
        s, csrf = self._require_auth()
        tid = self._next_tid()
        resp = s.post(
            f"https://{self._host}/ui/vcops/services/router",
            json=[{
                "action": "viewServiceController",
                "method": "getGroupedViewDefinitionThumbnails",
                "data": [],
                "type": "rpc",
                "tid": tid,
            }],
            headers={"secureToken": csrf},
        )
        resp.raise_for_status()
        result = resp.json()
        if result[0].get("type") == "exception":
            raise UIClientError(
                f"getGroupedViewDefinitionThumbnails failed: {result[0].get('message')}"
            )
        return result[0].get("result") or []

    def delete_view(self, view_uuid: str, view_name: str) -> None:
        """Delete a single view by UUID+name via Ext.Direct RPC.

        Unlike dashboard delete, non-existent view UUIDs return an exception
        response (HTTP 200 with type=exception in body). This method raises
        UIClientError in that case.

        NOTE: secureToken is sent as an HTTP *header* for Ext.Direct
        endpoints, NOT as a form/body param (unlike Struts .action endpoints).

        WIRE FORMAT: data must be an array containing one dict whose
        ``viewDefIds`` value is a JSON-stringified array of {id, name} objects.
        Sending a bare UUID string (the old shape) causes the handler to crash
        and return {"type":"exception","message":"Internal server error."}.
        See context/dashboard_delete_api.md "2026-04-11 correction".

        WARNING: unsupported internal endpoint; may change between releases.

        Args:
            view_uuid: the UUID of the view definition to delete.
            view_name: the display name of the view (required by the handler).

        Raises:
            UIClientError: if the server returns an exception (e.g. view does
                not exist or is a system view that cannot be deleted).
        """
        s, csrf = self._require_auth()
        tid = self._next_tid()
        view_def_ids = json.dumps([{"id": view_uuid, "name": view_name}])
        resp = s.post(
            f"https://{self._host}/ui/vcops/services/router",
            json=[{
                "action": "viewServiceController",
                "method": "deleteView",
                "data": [{"viewDefIds": view_def_ids}],
                "type": "rpc",
                "tid": tid,
            }],
            headers={"secureToken": csrf},
        )
        resp.raise_for_status()
        result = resp.json()
        if result[0].get("type") == "exception":
            raise UIClientError(
                f"deleteView {view_uuid!r} failed: {result[0].get('message')}"
            )

    def _next_tid(self) -> int:
        tid = self._tid
        self._tid += 1
        return tid
