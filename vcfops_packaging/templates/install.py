#!/usr/bin/env python3
"""VCF Operations content installer -- {{PACKAGE_NAME}}.

{{PACKAGE_DESCRIPTION}}

Usage (fully interactive -- prompts for all credentials):
    python3 install.py

Usage (explicit flags):
    python3 install.py --host ops.example.com --user admin --password secret

Usage (env vars):
    VCFOPS_HOST=ops.example.com VCFOPS_USER=admin VCFOPS_PASSWORD=secret python3 install.py

Args take precedence over env vars; env vars take precedence over interactive prompts.

Requires Python 3.8+. Uses only stdlib plus `requests` (auto-installed
into a temporary venv if not already available).
"""
from __future__ import annotations

import argparse
import getpass
import io
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def _load_json(name: str) -> Any:
    return json.loads((SCRIPT_DIR / "content" / name).read_text())


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _step(n: int, total: int, msg: str) -> None:
    print(f"\n[{n}/{total}] {msg}")


def _resolve_auth_source(raw: str) -> str:
    """Normalise the user-supplied auth source string.

    'local' (case-insensitive) or empty -> 'Local'
    Anything else (e.g. 'int.sentania.net') -> returned as-is.
    """
    if not raw or raw.strip().lower() == "local":
        return "Local"
    return raw.strip()


# ---------------------------------------------------------------------------
# VCF Ops API client (thin wrapper around requests.Session)
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
                return
            if time.monotonic() > deadline:
                _die(f"Import of {label} did not finish in {timeout_s}s; state={state}")
            time.sleep(2)

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
        r = self._req(
            "PUT",
            "/internal/supermetrics/assign",
            params=[("policyIds", policy_id)],
            json=body,
            headers={"X-Ops-API-use-unsupported": "true"},
        )
        if r.status_code != 200:
            _die(f"Enable SM '{sm_name}' failed ({r.status_code}): {r.text}")

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


# ---------------------------------------------------------------------------
# Content-zip builders
# ---------------------------------------------------------------------------
def _build_sm_zip(supermetrics_dict: dict, marker: str, owner_id: str) -> bytes:
    """Build SM content-zip from a dict keyed by UUID (wire format).

    supermetrics_dict: {uuid: {name, formula, description, unitId, resourceKinds}}
    This is the format vcfops_supermetrics/client.py produces and the
    content importer expects (verified against live VCF Ops 9 instance).
    """
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
    """Build combined views+dashboard content-zip with correct wire format.

    Explicit directory entries (dashboards/, dashboardsharings/) mirror
    the real export shape. The sharing entry is required — without it the
    dashboard imports as private to the API user only.
    """
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
# Interactive credential prompts
# ---------------------------------------------------------------------------
def _prompt_credentials(args: argparse.Namespace) -> tuple:
    """Resolve host, user, auth_source, and password.

    Priority order: CLI arg > env var > interactive prompt.
    Returns (host, user, auth_source, password) as plain strings.
    """
    print()
    print(f"VCF Content Factory -- {PACKAGE_NAME} installer")
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
# Main install flow
# ---------------------------------------------------------------------------
def main() -> None:
    # Count steps: auth(1) + marker(2) + owner(3) + SM import(4) +
    # dashboard import(5, if dashboard) + SM enable(6) + custom groups(7+)
    content_dir = SCRIPT_DIR / "content"
    has_sm = (content_dir / "supermetrics.json").exists()
    has_dashboard = (content_dir / "dashboard.json").exists()
    has_cg = (content_dir / "customgroup.json").exists()
    has_sm_meta = (content_dir / "sm_metadata.json").exists()

    steps = ["auth", "marker", "owner"]
    if has_sm:
        steps.append("sm_import")
    if has_dashboard:
        steps.append("dash_import")
    if has_sm_meta:
        steps.append("sm_enable")
    if has_cg:
        steps.append("cg_upsert")
    TOTAL_STEPS = len(steps)

    ap = argparse.ArgumentParser(
        description=f"Install VCF Content Factory {PACKAGE_NAME} package.\n"
                    "Run with no arguments for interactive prompts.")
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
                    help="Skip enabling super metrics on Default Policy")
    args = ap.parse_args()

    host, user, auth_source, password = _prompt_credentials(args)

    if args.skip_ssl_verify:
        print("WARNING: TLS certificate verification disabled.")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    verify_ssl = not args.skip_ssl_verify

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

    if has_sm:
        step += 1
        _step(step, TOTAL_STEPS, "Importing super metrics...")
        sm_dict = _load_json("supermetrics.json")
        sm_zip = _build_sm_zip(sm_dict, marker, owner_id)
        client.import_content_zip(sm_zip, "super metrics")
        _ok(f"Imported {len(sm_dict)} super metric(s)")

    if has_dashboard:
        step += 1
        _step(step, TOTAL_STEPS, "Importing view + dashboard...")
        views_xml = (content_dir / "views_content.xml").read_text() if (content_dir / "views_content.xml").exists() else ""
        dash_json = (content_dir / "dashboard.json").read_text()
        dash_ids = _extract_dashboard_ids(dash_json.replace("PLACEHOLDER_USER_ID", owner_id))
        n_views = 1 if views_xml else 0
        dash_zip = _build_dashboard_zip(
            views_xml, dash_json, marker, owner_id,
            n_views=n_views, n_dashboards=1, dashboard_ids=dash_ids,
        )
        client.import_content_zip(dash_zip, "dashboard + view")
        _ok(f"Imported {n_views} view(s) + 1 dashboard")

    if has_sm_meta and not args.skip_enable:
        step += 1
        _step(step, TOTAL_STEPS, "Enabling super metrics on Default Policy...")
        sm_meta = _load_json("sm_metadata.json")
        names = [sm["name"] for sm in sm_meta]
        server_ids = client.list_supermetrics_by_name(names)
        for sm in sm_meta:
            name = sm["name"]
            sm_id = server_ids.get(name)
            if not sm_id:
                print(f"  WARN  Could not resolve ID for '{name}' -- skipping enable")
                continue
            client.enable_sm_on_default_policy(sm_id, name, sm["resourceKinds"])
            _ok(f"Enabled: {name}")
    elif has_sm_meta and args.skip_enable:
        step += 1
        print(f"\n[{step}/{TOTAL_STEPS}] Skipping super metric enable (--skip-enable set)")

    if has_cg:
        step += 1
        _step(step, TOTAL_STEPS, "Upserting custom group(s)...")
        cg_data = _load_json("customgroup.json")
        # customgroup.json may be a single object or a list
        if isinstance(cg_data, dict):
            cg_data = [cg_data]
        for cg_payload in cg_data:
            cg_name = cg_payload["resourceKey"]["name"]
            client.upsert_custom_group(cg_payload)
            _ok(f"Upserted: {cg_name}")

    print("\nDone. All content installed successfully.")


if __name__ == "__main__":
    main()
