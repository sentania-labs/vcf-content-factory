#!/usr/bin/env python3
"""VCF Operations content installer/uninstaller -- {{PACKAGE_NAME}}.

{{PACKAGE_DESCRIPTION}}

Usage (install, fully interactive -- prompts for all credentials):
    python3 install.py
    python3 install.py --install

Usage (uninstall):
    python3 install.py --uninstall
    python3 install.py --uninstall --force   # skip dependency checks

Usage (explicit flags):
    python3 install.py --host ops.example.com --user admin --password secret
    python3 install.py --uninstall --host ops.example.com --user admin --password secret

Usage (env vars):
    VCFOPS_HOST=ops.example.com VCFOPS_USER=admin VCFOPS_PASSWORD=secret python3 install.py

Args take precedence over env vars; env vars take precedence over interactive prompts.

Exit codes:
    0 -- success (all content installed/removed)
    1 -- fatal error (auth failure, unexpected API error)
    2 -- partial failure (some items skipped or failed; others succeeded)

Requires Python 3.8+. Uses only stdlib plus `requests` (auto-installed
into a temporary venv if not already available).
"""
from __future__ import annotations

import argparse
import base64
import getpass
import io
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: ensure `requests` is available. If not, create a temp venv,
# install it, and re-exec this script inside the venv with all original args.
# ---------------------------------------------------------------------------
def _bootstrap_requests() -> None:
    try:
        import requests  # noqa: F401
        return
    except ImportError:
        pass

    import tempfile, venv
    venv_dir = Path(tempfile.mkdtemp(prefix="vcfops_install_venv_"))
    print(f"[bootstrap] Creating venv at {venv_dir} to install requests...")
    venv.create(str(venv_dir), with_pip=True)
    pip = venv_dir / "bin" / "pip"
    if not pip.exists():
        pip = venv_dir / "Scripts" / "pip.exe"
    subprocess.check_call([str(pip), "install", "--quiet", "requests"])
    python = venv_dir / "bin" / "python3"
    if not python.exists():
        python = venv_dir / "Scripts" / "python.exe"
    # Pass all original args through to the re-exec'd interpreter so flags
    # and env vars survive the bootstrap boundary.
    os.execv(str(python), [str(python)] + sys.argv)

_bootstrap_requests()

import requests  # noqa: E402 -- after bootstrap
import urllib3   # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent

# Template variables (replaced by builder at build time):
PACKAGE_NAME = "{{PACKAGE_NAME}}"
PACKAGE_DESCRIPTION = "{{PACKAGE_DESCRIPTION}}"
DASHBOARD_UUID = "{{DASHBOARD_UUID}}"  # empty string if no dashboard in bundle

# Content manifest: all names to uninstall, keyed by type.
# Built by the packager; never edited by hand.
# Shape: {"dashboards": [...], "views": [...], "supermetrics": [...], "customgroups": [...]}
CONTENT_MANIFEST: Dict[str, List[str]] = {{CONTENT_MANIFEST}}


def _load_json(name: str) -> Any:
    return json.loads((SCRIPT_DIR / "content" / name).read_text())


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def _step(n: int, total: int, msg: str) -> None:
    print(f"\n[{n}/{total}] {msg}")


def _resolve_auth_source(raw: str) -> str:
    """Normalise the user-supplied auth source string.

    'local' (case-insensitive) or empty -> 'Local' (Suite API canonical value).
    Anything else (e.g. 'int.sentania.net') -> returned as-is.

    Each client is responsible for translating 'Local' to the value its own
    API endpoint expects:
      - Suite API (/suite-api/api/auth/token/acquire): authSource = "Local"
      - UI login (/ui/login.action): authSourceId = "localItem"
    """
    if not raw or raw.strip().lower() == "local":
        return "Local"
    return raw.strip()


# ---------------------------------------------------------------------------
# VCF Ops Suite API client (thin wrapper around requests.Session)
# ---------------------------------------------------------------------------
class Client:
    def __init__(self, host: str, user: str, password: str,
                 auth_source: str = "Local", verify_ssl: bool = True):
        self.base = f"https://{host}/suite-api"
        self._user = user
        self._password = password
        self._auth_source = auth_source
        self._session = requests.Session()
        self._session.verify = verify_ssl
        self._session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        self._token: Optional[str] = None

    def authenticate(self) -> None:
        r = self._session.post(
            f"{self.base}/api/auth/token/acquire",
            json={"username": self._user, "password": self._password,
                  "authSource": self._auth_source},
        )
        if r.status_code != 200:
            _die(f"Authentication failed ({r.status_code}): {r.text}")
        self._token = r.json()["token"]
        self._session.headers["Authorization"] = f"vRealizeOpsToken {self._token}"

    def _req(self, method: str, path: str, **kw) -> requests.Response:
        if not self._token:
            self.authenticate()
        r = self._session.request(method, f"{self.base}{path}", **kw)
        if r.status_code == 401:
            self._token = None
            self.authenticate()
            r = self._session.request(method, f"{self.base}{path}", **kw)
        return r

    def get_current_user(self) -> dict:
        r = self._req("GET", "/api/auth/currentuser")
        if r.status_code != 200:
            _die(f"currentuser failed ({r.status_code}): {r.text}")
        return r.json()

    def discover_marker_filename(self, timeout_s: int = 120) -> str:
        """Discover the per-instance *L.v1 marker filename via a throwaway export.

        The importer rejects bundles whose marker filename does not match
        the server's own value. Snapshot startTime before POST so a stale
        FINISHED state from a prior export isn't mistaken for our new one.
        """
        deadline = time.monotonic() + timeout_s
        while True:
            g = self._req("GET", "/api/content/operations/export")
            if g.status_code == 200:
                st = (g.json() or {}).get("state", "")
                if st not in ("RUNNING", "INITIALIZED"):
                    break
            if time.monotonic() > deadline:
                _die("Timed out waiting for prior export to finish")
            time.sleep(2)

        prior_start = 0
        g = self._req("GET", "/api/content/operations/export")
        if g.status_code == 200:
            prior_start = (g.json() or {}).get("startTime") or 0

        r = self._req("POST", "/api/content/operations/export",
                      json={"scope": "CUSTOM", "contentTypes": ["SUPER_METRICS"]})
        if r.status_code not in (200, 202):
            _die(f"Marker-probe export failed ({r.status_code}): {r.text}")

        deadline = time.monotonic() + timeout_s
        while True:
            g = self._req("GET", "/api/content/operations/export")
            if g.status_code != 200:
                _die(f"Export status check failed ({g.status_code}): {g.text}")
            body = g.json() or {}
            st = body.get("state", "")
            start_time = body.get("startTime") or 0
            if start_time > prior_start and st.startswith("FINI"):
                break
            if time.monotonic() > deadline:
                _die(f"Marker-probe export timed out; state={st}")
            time.sleep(2)

        z = self._session.get(f"{self.base}/api/content/operations/export/zip")
        if z.status_code != 200:
            _die(f"Export zip download failed ({z.status_code})")
        with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
            for name in zf.namelist():
                if name.endswith("L.v1"):
                    return name
        _die("Export zip did not contain a *L.v1 marker file")
        return ""  # unreachable

    def import_content_zip(self, zip_bytes: bytes, label: str,
                           timeout_s: int = 180, retries: int = 4) -> None:
        """POST a content-zip to the import endpoint and poll until done.

        A 403 'task already running' is retried with exponential backoff.
        endTime is snapshotted before POST so the poll can distinguish our
        import from a prior already-FINISHED one.
        """
        pre = self._req("GET", "/api/content/operations/import")
        prior_end = 0
        if pre.status_code == 200:
            prior_end = (pre.json() or {}).get("endTime") or 0

        for attempt in range(1, retries + 1):
            r = self._session.post(
                f"{self.base}/api/content/operations/import",
                headers={"Content-Type": None},
                params={"force": "true"},
                files={"contentFile": ("content.zip", zip_bytes, "application/zip")},
            )
            if r.status_code == 403:
                wait = 2 ** attempt
                print(f"    [retry {attempt}/{retries}] 403 task busy, waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code not in (200, 202):
                _die(f"Import POST failed for {label} ({r.status_code}): {r.text}")
            break
        else:
            _die(f"Import POST for {label} failed after {retries} retries (task busy)")

        deadline = time.monotonic() + timeout_s
        while True:
            s = self._req("GET", "/api/content/operations/import")
            if s.status_code != 200:
                _die(f"Import status check failed ({s.status_code}): {s.text}")
            body = s.json()
            state = body.get("state", "")
            end_time = body.get("endTime") or 0
            if end_time > prior_end and state not in ("RUNNING", "INITIALIZED"):
                if "FAIL" in state.upper():
                    _die(f"Import of {label} finished with state={state}")
                return body
            if time.monotonic() > deadline:
                _die(f"Import of {label} did not finish in {timeout_s}s; state={state}")
            time.sleep(2)
        return {}  # unreachable; satisfies type checkers

    def get_default_policy_id(self) -> str:
        r = self._req("GET", "/api/policies")
        if r.status_code != 200:
            _die(f"Policy list failed ({r.status_code}): {r.text}")
        for p in r.json().get("policySummaries") or []:
            if p.get("defaultPolicy"):
                return p["id"]
        _die("No default policy found in /api/policies")
        return ""

    def list_supermetrics_by_name(self, names: List[str]) -> Dict[str, str]:
        """Return {name: id} for the given SM names (case-sensitive exact match).

        Uses the server-resolved ID for the enable step — the content-zip
        importer may assign a different server-side ID than the UUID in the
        YAML, so we resolve by name after import rather than trusting the
        pre-import UUID.
        """
        found: Dict[str, str] = {}
        page, page_size = 0, 1000
        target = set(names)
        while True:
            r = self._req("GET", "/api/supermetrics",
                          params={"page": page, "pageSize": page_size})
            if r.status_code != 200:
                _die(f"Super metric list failed ({r.status_code}): {r.text}")
            body = r.json()
            items = body.get("superMetrics") or []
            for sm in items:
                if sm.get("name") in target:
                    found[sm["name"]] = sm["id"]
            info = body.get("pageInfo") or {}
            total = info.get("totalCount", len(items))
            if (page + 1) * page_size >= total or not items:
                break
            page += 1
        return found

    def enable_sm_on_default_policy(self, sm_id: str, sm_name: str,
                                    resource_kinds: list) -> None:
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
        # Use /assign/default (no policyIds lookup needed) rather than
        # /assign?policyIds=... to avoid a silent-success failure mode where
        # the policy ID resolves but the assignment is not actually applied.
        r = self._req(
            "PUT",
            "/internal/supermetrics/assign/default",
            json=body,
            headers={"X-Ops-API-use-unsupported": "true"},
        )
        if r.status_code != 200:
            raise RuntimeError(f"Enable SM '{sm_name}' failed ({r.status_code}): {r.text}")

    def upsert_custom_group(self, payload: dict) -> None:
        name = payload["resourceKey"]["name"]
        r = self._req("GET", "/api/resources/groups",
                      params={"name": name, "pageSize": 100})
        if r.status_code != 200:
            _die(f"Custom group list failed ({r.status_code}): {r.text}")
        existing_id = None
        for g in r.json().get("groups") or []:
            if (g.get("resourceKey") or {}).get("name") == name:
                existing_id = g["id"]
                break
        if existing_id:
            r = self._req("PUT", f"/api/resources/groups/{existing_id}", json=payload)
            if r.status_code not in (200, 201, 204):
                _die(f"Custom group PUT failed ({r.status_code}): {r.text}")
        else:
            r = self._req("POST", "/api/resources/groups", json=payload)
            if r.status_code not in (200, 201):
                _die(f"Custom group POST failed ({r.status_code}): {r.text}")

    # ------------------------------------------------------------------
    # Uninstall helpers
    # ------------------------------------------------------------------

    def find_supermetric_ids(self, names: List[str]) -> Dict[str, str]:
        """Return {name: id} for super metrics matching any of the given names."""
        return self.list_supermetrics_by_name(names)

    def delete_supermetric(self, sm_id: str) -> int:
        """DELETE /api/supermetrics/{id}. Returns HTTP status code."""
        r = self._req("DELETE", f"/api/supermetrics/{sm_id}")
        return r.status_code

    def find_customgroup_ids(self, names: List[str]) -> Dict[str, str]:
        """Return {name: id} for custom groups matching any of the given names."""
        found: Dict[str, str] = {}
        target = set(names)
        page, page_size = 0, 1000
        while True:
            r = self._req("GET", "/api/resources/groups",
                          params={"page": page, "pageSize": page_size})
            if r.status_code != 200:
                _die(f"Custom group list failed ({r.status_code}): {r.text}")
            body = r.json()
            groups = body.get("groups") or []
            for g in groups:
                n = (g.get("resourceKey") or {}).get("name", "")
                if n in target:
                    found[n] = g["id"]
            info = body.get("pageInfo") or {}
            total = info.get("totalCount", len(groups))
            if (page + 1) * page_size >= total or not groups:
                break
            page += 1
        return found

    def delete_customgroup(self, group_id: str) -> int:
        """DELETE /api/resources/groups/{groupId}. Returns HTTP status code."""
        r = self._req("DELETE", f"/api/resources/groups/{group_id}")
        return r.status_code


# ---------------------------------------------------------------------------
# UI session client (dashboards + views delete)
# ---------------------------------------------------------------------------
class UIClient:
    """Minimal UI-session client for dashboard and view delete.

    Authentication flow (three steps):
      1. GET /ui/login.action?vcf=1  -- seeds JSESSIONID
      2. POST /ui/login.action (form creds) -- validates credentials
      3. GET /ui/index.action (no redirect) -- OPS_SESSION with csrfToken

    See context/dashboard_delete_api.md for full protocol documentation.
    """

    def __init__(self, host: str, user: str, password: str,
                 auth_source: str = "Local", verify_ssl: bool = True):
        self._host = host
        self._user = user
        self._password = password
        # The UI login form expects "localItem"; Suite API uses "Local".
        # Accept the canonical "Local" value and translate here.
        self._auth_source = "localItem" if auth_source == "Local" else auth_source
        self._verify_ssl = verify_ssl
        self._session: Optional[requests.Session] = None
        self._csrf_token: Optional[str] = None
        self._tid = 1

    def login(self) -> None:
        s = requests.Session()
        s.verify = self._verify_ssl

        # Step 1: seed JSESSIONID
        s.get(f"https://{self._host}/ui/login.action", params={"vcf": "1"})

        # Step 2: login with credentials
        resp = s.post(
            f"https://{self._host}/ui/login.action",
            data={
                "mainAction": "login",
                "userName": self._user,
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
            _die(f"UI authentication failed: {resp.text!r}")

        # Step 3: hit index.action WITHOUT following the 302 redirect.
        # OPS_SESSION cookie is set on the 302 response and cleared if
        # the redirect is followed.
        resp = s.get(
            f"https://{self._host}/ui/index.action",
            allow_redirects=False,
        )
        ops_cookie = resp.cookies.get("OPS_SESSION") or s.cookies.get("OPS_SESSION")
        if not ops_cookie:
            _die("OPS_SESSION cookie not received -- check credentials and auth source")
        try:
            ops_data = json.loads(base64.b64decode(ops_cookie))
        except Exception as exc:
            _die(f"Failed to decode OPS_SESSION cookie: {exc}")
        csrf_token = ops_data.get("csrfToken")
        if not csrf_token:
            _die("csrfToken not found in OPS_SESSION payload")

        self._session = s
        self._csrf_token = csrf_token

    def logout(self) -> None:
        if self._session is None:
            return
        try:
            self._session.get(
                f"https://{self._host}/ui/login.action",
                params={"mainAction": "logout"},
                allow_redirects=False,
            )
        except Exception:
            pass
        finally:
            self._session = None
            self._csrf_token = None

    def list_dashboards(self) -> List[Dict[str, Any]]:
        """Return all dashboards visible to the authenticated user."""
        assert self._session and self._csrf_token
        resp = self._session.post(
            f"https://{self._host}/ui/dashboard.action",
            data={
                "mainAction": "getDashboardList",
                "secureToken": self._csrf_token,
                "currentComponentInfo": "TODO",
                "globalDate": json.dumps({"dateRange": "last6Hour"}),
            },
        )
        resp.raise_for_status()
        return resp.json().get("dashboards") or []

    def delete_dashboards(self, dashboards: List[Tuple[str, str]]) -> None:
        """Delete dashboards by (uuid, name) tuples."""
        assert self._session and self._csrf_token
        tab_ids = [{"tabId": uid, "tabName": name} for uid, name in dashboards]
        resp = self._session.post(
            f"https://{self._host}/ui/dashboard.action",
            data={
                "mainAction": "deleteTab",
                "tabIds": json.dumps(tab_ids),
                "secureToken": self._csrf_token,
                "currentComponentInfo": "TODO",
                "globalDate": json.dumps({"dateRange": "last6Hour"}),
            },
        )
        resp.raise_for_status()

    def list_views(self) -> List[Dict[str, Any]]:
        """List all view definitions via Ext.Direct RPC."""
        assert self._session and self._csrf_token
        tid = self._next_tid()
        resp = self._session.post(
            f"https://{self._host}/ui/vcops/services/router",
            json=[{
                "action": "viewServiceController",
                "method": "getGroupedViewDefinitionThumbnails",
                "data": [],
                "type": "rpc",
                "tid": tid,
            }],
            headers={"secureToken": self._csrf_token},
        )
        resp.raise_for_status()
        result = resp.json()
        if result[0].get("type") == "exception":
            _die(f"View list failed: {result[0].get('message')}")
        grouped = result[0].get("result") or []
        views: List[Dict[str, Any]] = []
        for group in grouped:
            views.extend(group.get("views") or [])
        return views

    def delete_view(self, view_uuid: str) -> None:
        """Delete a view by UUID via Ext.Direct RPC."""
        assert self._session and self._csrf_token
        tid = self._next_tid()
        resp = self._session.post(
            f"https://{self._host}/ui/vcops/services/router",
            json=[{
                "action": "viewServiceController",
                "method": "deleteView",
                "data": [view_uuid],
                "type": "rpc",
                "tid": tid,
            }],
            headers={"secureToken": self._csrf_token},
        )
        resp.raise_for_status()
        result = resp.json()
        if result[0].get("type") == "exception":
            raise RuntimeError(f"deleteView {view_uuid!r} failed: {result[0].get('message')}")

    def _next_tid(self) -> int:
        tid = self._tid
        self._tid += 1
        return tid


# ---------------------------------------------------------------------------
# Content-zip builders (install mode)
# ---------------------------------------------------------------------------
def _build_sm_zip(supermetrics_dict: dict, marker: str, owner_id: str) -> bytes:
    """Build SM content-zip from a dict keyed by UUID (wire format)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(marker, owner_id)
        z.writestr("supermetrics.json", json.dumps(supermetrics_dict, indent=2))
        z.writestr(
            "configuration.json",
            json.dumps({"superMetrics": len(supermetrics_dict), "type": "ALL"}, indent=2),
        )
    return buf.getvalue()


def _build_views_inner_zip(xml_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", xml_text)
    return buf.getvalue()


def _build_dashboard_inner_zip(dashboard_json: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dashboard/dashboard.json", dashboard_json)
        for lang in ("", "_es", "_fr", "_ja"):
            z.writestr(f"dashboard/resources/resources{lang}.properties", "")
    return buf.getvalue()


def _build_dashboard_zip(views_xml: str, dashboard_json: str,
                         marker: str, owner_id: str,
                         n_views: int, n_dashboards: int,
                         dashboard_ids: list) -> bytes:
    """Build combined views+dashboard content-zip with correct wire format."""
    config: dict = {"type": "CUSTOM"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as outer:
        outer.writestr(marker, owner_id)

        if views_xml:
            outer.writestr("views.zip", _build_views_inner_zip(views_xml))
            config["views"] = n_views

        if dashboard_json:
            outer.writestr(zipfile.ZipInfo("dashboards/"), b"")
            outer.writestr(zipfile.ZipInfo("dashboardsharings/"), b"")

            patched_json = dashboard_json.replace("PLACEHOLDER_USER_ID", owner_id)
            outer.writestr(
                f"dashboards/{owner_id}",
                _build_dashboard_inner_zip(patched_json),
            )
            outer.writestr(
                f"dashboardsharings/{owner_id}",
                json.dumps([
                    {
                        "groupName": "Everyone",
                        "sourceType": "LOCAL",
                        "dashboards": [{"dashboardId": did} for did in dashboard_ids],
                    }
                ]),
            )
            outer.writestr(
                "usermappings.json",
                json.dumps({
                    "sources": [],
                    "users": [{"userName": "admin", "userId": owner_id}],
                }, indent=2),
            )
            config["dashboards"] = n_dashboards
            config["dashboardsByOwner"] = [{"owner": owner_id, "count": n_dashboards}]

        outer.writestr("configuration.json", json.dumps(config, indent=2))

    return buf.getvalue()


def _extract_dashboard_ids(dashboard_json: str) -> list:
    data = json.loads(dashboard_json)
    return [d["id"] for d in (data.get("dashboards") or []) if d.get("id")]


# ---------------------------------------------------------------------------
# Interactive credential prompts (shared by install and uninstall)
# ---------------------------------------------------------------------------
def _prompt_credentials(args: argparse.Namespace, mode: str) -> tuple:
    """Resolve host, user, auth_source, and password.

    Priority order: CLI arg > env var > interactive prompt.
    Returns (host, user, auth_source, password) as plain strings.
    """
    print()
    print(f"VCF Content Factory -- {PACKAGE_NAME} {mode}")
    print("Press Enter to accept [defaults] shown in brackets.")
    print()

    host = args.host
    if not host:
        host = input("VCF Operations host: ").strip()
        if not host:
            _die("Host is required.")

    user = args.user
    if not user:
        user = input("Username [admin]: ").strip() or "admin"

    auth_source_raw = args.auth_source
    if not auth_source_raw:
        auth_source_raw = input(
            "Auth source (local, or domain like int.sentania.net) [local]: "
        ).strip()
    auth_source = _resolve_auth_source(auth_source_raw)

    password = args.password
    if not password:
        password = getpass.getpass("Password: ")
        if not password:
            _die("Password is required.")

    return host, user, auth_source, password


# ---------------------------------------------------------------------------
# Content type registry
#
# Each entry describes one content type.  The registry drives BOTH install and
# uninstall iteration, replacing the previous hard-coded if/elif chains.
#
# Adding a new content type (e.g. "symptoms") means adding a single entry
# here — the install/uninstall loops below require no changes.
#
# Registry entry keys:
#   content_type  str   key in CONTENT_MANIFEST (used for uninstall names)
#   install_file  str   filename under content/ that signals this type is present
#   install_fn    callable(ctx) -> None   runs the install step
#   uninstall_fn  callable(ctx) -> None  runs the uninstall step
#   install_label str   human-readable step label for install
#   uninstall_label str human-readable step label for uninstall
#   install_order int   lower runs first (install)
#   uninstall_order int lower runs first (uninstall = reverse install order)
#
# The "ctx" object passed to each function is a plain dict with:
#   client        Client            authenticated Suite API client
#   ui_client     UIClient | None   authenticated UI session client (or None)
#   marker        str               instance marker filename
#   owner_id      str               current user UUID
#   args          argparse.Namespace
#   warnings      List[str]         accumulate WARN strings here
#   content_dir   Path
# ---------------------------------------------------------------------------

def _install_supermetrics(ctx: Dict) -> None:
    sm_dict = _load_json("supermetrics.json")
    sm_zip = _build_sm_zip(sm_dict, ctx["marker"], ctx["owner_id"])
    result = ctx["client"].import_content_zip(sm_zip, "super metrics") or {}

    # Ghost-state recovery: the content-zip importer will "skip" an SM that
    # already exists in the DB but failed to fully register in the internal SM
    # catalog (e.g. from a previous partial import).  Such SMs are queryable by
    # GET /{id} but absent from the list API and invisible to the assign endpoint,
    # so a subsequent enable call returns 404.  A second import re-registers the
    # SM fully.  Detect the all-skipped signal and retry once automatically.
    summaries = result.get("operationSummaries") or []
    sm_summaries = [s for s in summaries if s.get("contentType") == "SUPER_METRICS"]
    if sm_summaries:
        total_imported = sum(int(s.get("imported") or 0) for s in sm_summaries)
        total_skipped = sum(int(s.get("skipped") or 0) for s in sm_summaries)
        if total_imported == 0 and total_skipped > 0:
            print(f"    [ghost-state recovery] all {total_skipped} SM(s) skipped on first "
                  f"import — retrying to re-register in SM catalog...")
            ctx["client"].import_content_zip(sm_zip, "super metrics (retry)")

    _ok(f"Imported {len(sm_dict)} super metric(s)")


def _install_dashboards(ctx: Dict) -> None:
    content_dir = ctx["content_dir"]
    views_xml = (
        (content_dir / "views_content.xml").read_text()
        if (content_dir / "views_content.xml").exists()
        else ""
    )
    dash_json = (content_dir / "dashboard.json").read_text()
    owner_id = ctx["owner_id"]
    dash_ids = _extract_dashboard_ids(dash_json.replace("PLACEHOLDER_USER_ID", owner_id))
    n_views = 1 if views_xml else 0
    dash_zip = _build_dashboard_zip(
        views_xml, dash_json, ctx["marker"], owner_id,
        n_views=n_views, n_dashboards=1, dashboard_ids=dash_ids,
    )
    ctx["client"].import_content_zip(dash_zip, "dashboard + view")
    _ok(f"Imported {n_views} view(s) + 1 dashboard")


def _install_sm_enable(ctx: Dict) -> None:
    args = ctx["args"]
    if args.skip_enable:
        print("  (--skip-enable set: skipping)")
        return
    sm_meta = _load_json("sm_metadata.json")
    names = [sm["name"] for sm in sm_meta]
    SM_RESOLVE_ATTEMPTS = 3
    SM_RESOLVE_DELAY = 5
    server_ids: Dict[str, str] = {}
    for attempt in range(1, SM_RESOLVE_ATTEMPTS + 1):
        server_ids = ctx["client"].list_supermetrics_by_name(names)
        missing = [n for n in names if n not in server_ids]
        if not missing:
            break
        if attempt < SM_RESOLVE_ATTEMPTS:
            print(f"    [resolve {attempt}/{SM_RESOLVE_ATTEMPTS}] "
                  f"{len(missing)} SM(s) not queryable yet, "
                  f"waiting {SM_RESOLVE_DELAY}s...")
            time.sleep(SM_RESOLVE_DELAY)
    for sm in sm_meta:
        name = sm["name"]
        sm_id = server_ids.get(name)
        if not sm_id:
            warn = f"Could not resolve ID for '{name}' -- skipping enable"
            _warn(warn)
            ctx["warnings"].append(warn)
            continue
        try:
            ctx["client"].enable_sm_on_default_policy(sm_id, name, sm["resourceKinds"])
            _ok(f"Enabled: {name}")
        except RuntimeError as exc:
            warn = str(exc)
            _warn(warn)
            ctx["warnings"].append(warn)


def _install_customgroups(ctx: Dict) -> None:
    cg_data = _load_json("customgroup.json")
    if isinstance(cg_data, dict):
        cg_data = [cg_data]
    for cg_payload in cg_data:
        cg_name = cg_payload["resourceKey"]["name"]
        ctx["client"].upsert_custom_group(cg_payload)
        _ok(f"Upserted: {cg_name}")


def _uninstall_dashboards(ctx: Dict) -> None:
    ui_client = ctx["ui_client"]
    names: List[str] = ctx["names"]
    warnings = ctx["warnings"]
    all_dashboards = ui_client.list_dashboards()
    dash_by_name: Dict[str, str] = {
        d["name"]: d["id"] for d in all_dashboards if d.get("name") and d.get("id")
    }
    to_delete: List[Tuple[str, str]] = []
    for name in names:
        if name in dash_by_name:
            to_delete.append((dash_by_name[name], name))
        else:
            _warn(f"Dashboard not found (already removed?): {name}")
            warnings.append(f"Dashboard not found: {name}")
    if to_delete:
        try:
            ui_client.delete_dashboards(to_delete)
            for _, name in to_delete:
                _ok(f"Deleted: {name}")
        except Exception as exc:
            warn = f"Dashboard batch delete failed: {exc}"
            _warn(warn)
            warnings.append(warn)


def _uninstall_views(ctx: Dict) -> None:
    ui_client = ctx["ui_client"]
    names: List[str] = ctx["names"]
    warnings = ctx["warnings"]
    all_views = ui_client.list_views()
    view_by_name: Dict[str, str] = {
        v.get("name", ""): v.get("id", "") for v in all_views
        if v.get("name") and v.get("id")
    }
    for name in names:
        view_id = view_by_name.get(name)
        if not view_id:
            _warn(f"View not found (already removed?): {name}")
            warnings.append(f"View not found: {name}")
            continue
        try:
            ui_client.delete_view(view_id)
            _ok(f"Deleted: {name}")
        except RuntimeError as exc:
            warn = f"View delete failed for '{name}': {exc}"
            _warn(warn)
            warnings.append(warn)


def _uninstall_supermetrics(ctx: Dict) -> None:
    names: List[str] = ctx["names"]
    warnings = ctx["warnings"]
    force: bool = ctx["force"]
    sm_ids = ctx["client"].find_supermetric_ids(names)
    for name in names:
        sm_id = sm_ids.get(name)
        if not sm_id:
            _warn(f"Super metric not found (already removed?): {name}")
            warnings.append(f"Super metric not found: {name}")
            continue
        sc = ctx["client"].delete_supermetric(sm_id)
        if sc in (200, 204):
            _ok(f"Deleted: {name}")
        elif sc == 409:
            warn = f"Skipped: {name} (referenced by other content; use --force to override)"
            _warn(warn)
            warnings.append(warn)
        else:
            warn = f"Super metric delete returned HTTP {sc} for '{name}'"
            _warn(warn)
            warnings.append(warn)


def _uninstall_customgroups(ctx: Dict) -> None:
    names: List[str] = ctx["names"]
    warnings = ctx["warnings"]
    cg_ids = ctx["client"].find_customgroup_ids(names)
    for name in names:
        cg_id = cg_ids.get(name)
        if not cg_id:
            _warn(f"Custom group not found (already removed?): {name}")
            warnings.append(f"Custom group not found: {name}")
            continue
        sc = ctx["client"].delete_customgroup(cg_id)
        if sc in (200, 204):
            _ok(f"Deleted: {name}")
        else:
            warn = f"Custom group delete returned HTTP {sc} for '{name}'"
            _warn(warn)
            warnings.append(warn)


# Registry: ordered by install_order.
# To add a new content type, append an entry here.  No other changes needed.
_CONTENT_REGISTRY: List[Dict] = [
    {
        "content_type": "supermetrics",
        "install_file": "supermetrics.json",
        "install_label": "Importing super metrics...",
        "install_fn": _install_supermetrics,
        "install_order": 1,
        # uninstall handled via ui=False entry below
        "uninstall_label": "Deleting super metric(s)...",
        "uninstall_fn": _uninstall_supermetrics,
        "uninstall_order": 40,   # after views (which depend on SMs)
        "needs_ui": False,
    },
    {
        "content_type": "views_and_dashboards",  # synthetic key: install file = dashboard.json
        "install_file": "dashboard.json",
        "install_label": "Importing view + dashboard...",
        "install_fn": _install_dashboards,
        "install_order": 2,
        "uninstall_label": None,  # handled separately via dashboards/views entries
        "uninstall_fn": None,
        "uninstall_order": None,
        "needs_ui": False,
    },
    {
        "content_type": "sm_enable",  # synthetic key: uses sm_metadata.json
        "install_file": "sm_metadata.json",
        "install_label": "Enabling super metrics on Default Policy...",
        "install_fn": _install_sm_enable,
        "install_order": 3,
        "uninstall_label": None,
        "uninstall_fn": None,
        "uninstall_order": None,
        "needs_ui": False,
    },
    {
        "content_type": "customgroups",
        "install_file": "customgroup.json",
        "install_label": "Upserting custom group(s)...",
        "install_fn": _install_customgroups,
        "install_order": 4,
        "uninstall_label": "Deleting custom group(s)...",
        "uninstall_fn": _uninstall_customgroups,
        "uninstall_order": 50,
        "needs_ui": False,
    },
    # Uninstall-only entries for dashboards and views (reverse of install):
    {
        "content_type": "dashboards",
        "install_file": None,    # not used for install (handled by views_and_dashboards)
        "install_label": None,
        "install_fn": None,
        "install_order": None,
        "uninstall_label": "Deleting dashboard(s)...",
        "uninstall_fn": _uninstall_dashboards,
        "uninstall_order": 10,   # first: dashboards depend on views
        "needs_ui": True,
    },
    {
        "content_type": "views",
        "install_file": None,
        "install_label": None,
        "install_fn": None,
        "install_order": None,
        "uninstall_label": "Deleting view(s)...",
        "uninstall_fn": _uninstall_views,
        "uninstall_order": 20,   # after dashboards are gone
        "needs_ui": True,
    },
]


# ---------------------------------------------------------------------------
# Install flow (registry-driven)
# ---------------------------------------------------------------------------
def _run_install(args: argparse.Namespace, host: str, user: str,
                 auth_source: str, password: str, verify_ssl: bool) -> None:
    content_dir = SCRIPT_DIR / "content"

    # Determine which registry entries are active for this bundle
    active = [
        e for e in _CONTENT_REGISTRY
        if e["install_fn"] is not None
        and e["install_file"] is not None
        and (content_dir / e["install_file"]).exists()
    ]
    active.sort(key=lambda e: e["install_order"])

    TOTAL_STEPS = 3 + len(active)   # auth + marker + owner + content steps
    print(f"\nInstalling {PACKAGE_NAME} onto {host}...")

    client = Client(host, user, password, auth_source, verify_ssl)
    step = 0

    step += 1
    _step(step, TOTAL_STEPS,
          f"Authenticating as {user}@{host} (auth: {auth_source}) ...")
    client.authenticate()
    _ok("Authenticated")

    step += 1
    _step(step, TOTAL_STEPS, "Discovering instance marker filename...")
    marker = client.discover_marker_filename()
    _ok(f"Marker: {marker}")

    step += 1
    _step(step, TOTAL_STEPS, "Resolving current user ID...")
    owner_id = client.get_current_user()["id"]
    _ok(f"Owner user ID: {owner_id}")

    warnings: List[str] = []
    ctx: Dict = {
        "client": client,
        "ui_client": None,
        "marker": marker,
        "owner_id": owner_id,
        "args": args,
        "warnings": warnings,
        "content_dir": content_dir,
        "force": False,
        "names": [],
    }

    for entry in active:
        step += 1
        _step(step, TOTAL_STEPS, entry["install_label"])
        entry["install_fn"](ctx)

    print()
    # Separate SM-enable warnings from other failures for UX clarity
    enable_warnings = [w for w in warnings if "enable" in w.lower() or "resolve" in w.lower()]
    other_warnings = [w for w in warnings if w not in enable_warnings]
    if enable_warnings or other_warnings:
        total = len(enable_warnings) + len(other_warnings)
        print(f"Done with {total} warning(s):")
        for w in enable_warnings + other_warnings:
            print(f"  WARN  {w}")
        if enable_warnings:
            print("Content was imported but one or more super metrics could not be enabled.")
        sys.exit(2)
    else:
        print("Done. All content installed successfully.")


# ---------------------------------------------------------------------------
# Uninstall flow (registry-driven)
# ---------------------------------------------------------------------------
def _run_uninstall(args: argparse.Namespace, host: str, user: str,
                   auth_source: str, password: str, verify_ssl: bool) -> None:
    force = args.force

    # Determine which registry entries are active for this bundle's uninstall
    active_uninstall = [
        e for e in _CONTENT_REGISTRY
        if e["uninstall_fn"] is not None
        and e["uninstall_order"] is not None
        and (CONTENT_MANIFEST.get(e["content_type"]) or [])
    ]
    active_uninstall.sort(key=lambda e: e["uninstall_order"])

    needs_ui = any(e["needs_ui"] for e in active_uninstall)
    needs_suite = any(not e["needs_ui"] for e in active_uninstall)

    # Count steps: auth + [ui_auth] + content steps + [ui_logout]
    n_steps = 1 + len(active_uninstall)
    if needs_ui:
        n_steps += 2  # ui_auth + ui_logout

    print(f"\nUninstalling {PACKAGE_NAME} from {host}...")
    if force:
        print("(--force: skipping dependency checks)")
    print("Content to remove:")
    for e in active_uninstall:
        names = CONTENT_MANIFEST.get(e["content_type"]) or []
        if names:
            print(f"  {e['content_type'].capitalize()} ({len(names)}): {', '.join(names)}")
    if not active_uninstall:
        print("  (nothing to remove -- bundle contains no content)")
        sys.exit(0)

    warnings: List[str] = []
    step = 0
    TOTAL_STEPS = n_steps

    suite_client = Client(host, user, password, auth_source, verify_ssl)
    ui_client = UIClient(host, user, password, auth_source, verify_ssl)

    step += 1
    _step(step, TOTAL_STEPS, f"Authenticating as {user}@{host} (auth: {auth_source}) ...")
    if needs_suite:
        suite_client.authenticate()
    _ok("Authenticated")

    if needs_ui:
        step += 1
        _step(step, TOTAL_STEPS, "Starting UI session (for dashboard/view delete)...")
        ui_client.login()
        _ok("UI session established")

    ctx: Dict = {
        "client": suite_client,
        "ui_client": ui_client if needs_ui else None,
        "marker": None,
        "owner_id": None,
        "args": args,
        "warnings": warnings,
        "content_dir": SCRIPT_DIR / "content",
        "force": force,
        "names": [],
    }

    for entry in active_uninstall:
        names = list(CONTENT_MANIFEST.get(entry["content_type"]) or [])
        if not names:
            continue
        step += 1
        label = entry["uninstall_label"].replace("...", f" ({len(names)})...")
        _step(step, TOTAL_STEPS, label)
        ctx["names"] = names
        entry["uninstall_fn"](ctx)

    if needs_ui:
        step += 1
        _step(step, TOTAL_STEPS, "Closing UI session...")
        ui_client.logout()
        _ok("UI session closed")

    print()
    if warnings:
        not_found = [w for w in warnings if "not found" in w]
        real_failures = [w for w in warnings if "not found" not in w]
        if real_failures:
            print(f"Done with errors ({len(real_failures)} delete failure(s)):")
            for w in real_failures:
                print(f"  WARN  {w}")
            if not_found:
                print(f"  ({len(not_found)} item(s) were already absent)")
            sys.exit(2)
        else:
            print(f"Done. All targeted content was already absent ({len(not_found)} item(s) not found).")
    else:
        print("Done. All content removed successfully.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(
        description=f"Install or uninstall VCF Content Factory {PACKAGE_NAME} package.\n"
                    "Run with no arguments for interactive install prompts.\n"
                    "Use --uninstall to remove all content this package installed.")
    ap.add_argument("--install", action="store_true",
                    help="Install mode (default when no mode flag is given)")
    ap.add_argument("--uninstall", action="store_true",
                    help="Uninstall mode: delete all content in this bundle from the instance")
    ap.add_argument("--force", action="store_true",
                    help="With --uninstall: skip dependency checks and delete unconditionally")
    ap.add_argument("--host",
                    default=os.environ.get("VCFOPS_HOST"),
                    help="VCF Ops hostname or IP (env: VCFOPS_HOST)")
    ap.add_argument("--user",
                    default=os.environ.get("VCFOPS_USER"),
                    help="VCF Ops username (env: VCFOPS_USER)")
    ap.add_argument("--password",
                    default=os.environ.get("VCFOPS_PASSWORD"),
                    help="VCF Ops password (env: VCFOPS_PASSWORD)")
    ap.add_argument("--auth-source",
                    default=os.environ.get("VCFOPS_AUTH_SOURCE", ""),
                    help="Auth source: 'local' or a domain name like int.sentania.net "
                         "(env: VCFOPS_AUTH_SOURCE, default: Local)")
    ap.add_argument("--skip-ssl-verify", action="store_true",
                    default=(os.environ.get("VCFOPS_VERIFY_SSL", "true").lower() == "false"),
                    help="Disable TLS certificate verification (lab use only)")
    ap.add_argument("--skip-enable", action="store_true",
                    help="(install mode) Skip enabling super metrics on Default Policy")
    args = ap.parse_args()

    if args.uninstall and args.install:
        _die("--install and --uninstall are mutually exclusive.")
    if args.force and not args.uninstall:
        _die("--force is only valid with --uninstall.")

    mode = "uninstaller" if args.uninstall else "installer"
    host, user, auth_source, password = _prompt_credentials(args, mode)

    if args.skip_ssl_verify:
        print("WARNING: TLS certificate verification disabled.")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    verify_ssl = not args.skip_ssl_verify

    if args.uninstall:
        _run_uninstall(args, host, user, auth_source, password, verify_ssl)
    else:
        _run_install(args, host, user, auth_source, password, verify_ssl)


if __name__ == "__main__":
    main()
