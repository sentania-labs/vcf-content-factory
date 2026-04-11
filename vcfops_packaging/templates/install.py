#!/usr/bin/env python3
"""VCF Operations content installer/uninstaller.

Installs or uninstalls one or more content bundles found in the bundles/
subdirectory (or a legacy top-level content/ directory).  When multiple
bundles are present, an interactive checklist is shown so the operator can
select which bundles to install or uninstall.

Usage (install, fully interactive -- prompts for all credentials):
    python3 install.py
    python3 install.py --install

Usage (uninstall):
    python3 install.py --uninstall
    python3 install.py --uninstall --force   # skip dependency checks

Note: Uninstall requires the 'admin' account for dashboard/view cleanup.

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


def _load_json_from_path(p: Path) -> Any:
    return json.loads(p.read_text())


# ---------------------------------------------------------------------------
# Bundle discovery and selection
# ---------------------------------------------------------------------------
def _discover_bundles() -> List[Dict]:
    """Discover bundle entries from the bundles/ subtree.

    Returns a list of dicts:
        {"slug": str, "dir": Path, "manifest": dict}

    Fallback: if no bundles/ subtree exists but a legacy top-level bundle.json
    + content/ exist, synthesise a single in-memory entry for backwards
    compatibility (one-release transition; removable later).
    """
    bundles_root = SCRIPT_DIR / "bundles"
    entries: List[Dict] = []

    if bundles_root.exists():
        for bundle_json_path in sorted(bundles_root.glob("*/bundle.json")):
            slug = bundle_json_path.parent.name
            try:
                manifest = json.loads(bundle_json_path.read_text())
            except Exception as exc:
                print(f"  WARN  Could not parse {bundle_json_path}: {exc} -- skipping")
                continue
            entries.append({
                "slug": slug,
                "dir": bundle_json_path.parent,
                "manifest": manifest,
            })

    if not entries:
        # Legacy fallback: flat content/ layout with top-level bundle.json.
        legacy_manifest_path = SCRIPT_DIR / "bundle.json"
        legacy_content_dir = SCRIPT_DIR / "content"
        if legacy_manifest_path.exists() and legacy_content_dir.exists():
            try:
                manifest = json.loads(legacy_manifest_path.read_text())
            except Exception:
                manifest = {"name": "bundle", "description": "", "content": {}}
            # Synthesise a content map pointing to the legacy content/ directory.
            # Rewrite file paths to be relative to SCRIPT_DIR so the install
            # handlers can resolve them via bundle_dir / file.
            content = manifest.get("content") or {}
            for key, section in content.items():
                rel = section.get("file", "")
                if rel and not rel.startswith("content/"):
                    section["file"] = f"content/{rel}"
            entries.append({
                "slug": manifest.get("name", "bundle"),
                "dir": SCRIPT_DIR,
                "manifest": manifest,
            })
        elif legacy_content_dir.exists():
            # Minimal fallback with no manifest at all — synthesise from files.
            manifest = {"name": "bundle", "description": "", "content": {}}
            legacy_files = {
                "supermetrics": "supermetrics.json",
                "views": "views_content.xml",
                "dashboards": "dashboard.json",
                "customgroups": "customgroup.json",
                "symptoms": "symptoms.json",
                "alerts": "alerts.json",
                "reports": "reports_content.xml",
            }
            content: dict = {}
            for key, fname in legacy_files.items():
                if (legacy_content_dir / fname).exists():
                    content[key] = {"file": f"content/{fname}", "items": []}
            manifest["content"] = content
            entries.append({
                "slug": "bundle",
                "dir": SCRIPT_DIR,
                "manifest": manifest,
            })

    return entries


def _select_bundles(bundles: List[Dict], mode: str) -> List[Dict]:
    """Interactive multi-select checklist for bundles.

    Single bundle: auto-select and return it without prompting.
    Multiple bundles: print checklist (all checked by default),
    accept comma-separated toggle indices, 'all', 'none', or empty to proceed.

    Returns the list of selected bundle dicts.
    """
    if len(bundles) == 1:
        b = bundles[0]
        name = b["manifest"].get("name", b["slug"])
        desc = b["manifest"].get("description", "")
        print(f"\n  Bundle: {name}" + (f" -- {desc}" if desc else ""))
        return bundles

    print(f"\nSelect bundles to {mode} (all selected by default):")
    print("  Toggle: enter comma-separated numbers (e.g. '2' or '1,3')")
    print("  Commands: 'all' to select all, 'none' to deselect all, Enter to proceed")
    print()

    selected = [True] * len(bundles)

    while True:
        for i, b in enumerate(bundles, 1):
            mark = "*" if selected[i - 1] else " "
            name = b["manifest"].get("name", b["slug"])
            desc = b["manifest"].get("description", "")
            n_items = sum(
                len(s.get("items", []))
                for s in b["manifest"].get("content", {}).values()
            )
            detail = f"{n_items} items" if n_items else "no items"
            suffix = f" ({detail})" + (f" -- {desc}" if desc else "")
            print(f"  [{mark}] {i}. {name}{suffix}")

        raw = input("\nToggle [1..N / all / none / Enter to proceed]: ").strip().lower()
        if raw == "":
            break
        elif raw == "all":
            selected = [True] * len(bundles)
        elif raw == "none":
            selected = [False] * len(bundles)
        else:
            for tok in raw.split(","):
                tok = tok.strip()
                if tok.isdigit():
                    idx = int(tok) - 1
                    if 0 <= idx < len(bundles):
                        selected[idx] = not selected[idx]
                    else:
                        print(f"  (ignoring out-of-range index {tok})")
                elif tok:
                    print(f"  (unrecognised token {tok!r} -- ignored)")
        print()

    chosen = [b for b, s in zip(bundles, selected) if s]
    if not chosen:
        print("  No bundles selected. Exiting.")
        sys.exit(0)
    return chosen


def _print_selection_summary(bundles: List[Dict], mode: str) -> None:
    """Print a summary of selected bundles before install/uninstall."""
    print(f"\nWill {mode} {len(bundles)} bundle(s):")
    for b in bundles:
        name = b["manifest"].get("name", b["slug"])
        desc = b["manifest"].get("description", "")
        content = b["manifest"].get("content", {})
        parts: List[str] = []
        for key, section in content.items():
            count = len(section.get("items", []))
            if count:
                parts.append(f"{count} {key}")
        summary = ", ".join(parts) if parts else "no items"
        print(f"  - {name}" + (f" -- {desc}" if desc else ""))
        print(f"    Contents: {summary}")


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def _verify_supermetrics_enabled(policy_xml: str, sm_ids: list) -> dict:
    """Check which SM IDs appear as enabled in policy XML."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(policy_xml)
    enabled_ids = set()
    for elem in root.iter("SuperMetric"):
        if elem.get("enabled", "").lower() == "true":
            enabled_ids.add(elem.get("id", ""))
    return {sm_id: sm_id in enabled_ids for sm_id in sm_ids}


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
        """Assign a super metric to resource kinds and enable it in the
        Default Policy.

        Two-step approach required for content-zip-imported SMs:

        Step 1 — resource-kind assignment via PUT /internal/supermetrics/assign
          (without policyIds).  Wires the SM to adapter/resource kind so it
          appears in views.  The policyIds variant does NOT enable content-zip
          SMs on any policy — it is a no-op for this import path.

        Step 2 — policy enablement via policy export -> edit XML -> re-import.
          Stale entries for this SM are removed from ALL <SuperMetrics> blocks
          before injecting fresh ones, making this call idempotent/self-healing.
        """
        import xml.etree.ElementTree as ET
        import re as _re

        policy_id = self.get_default_policy_id()

        # Step 1: resource-kind assignment (no policyIds).
        normalised_rks = [
            {
                "adapterKind": rk.get("adapterKindKey") or rk.get("adapterKind"),
                "resourceKind": rk.get("resourceKindKey") or rk.get("resourceKind"),
            }
            for rk in resource_kinds
        ]
        body = {
            "superMetricId": sm_id,
            "resourceKindKeys": normalised_rks,
        }
        r = self._req(
            "PUT",
            "/internal/supermetrics/assign",
            json=body,
            headers={"X-Ops-API-use-unsupported": "true"},
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"Resource-kind assignment for SM '{sm_name}' failed "
                f"({r.status_code}): {r.text}"
            )

        # Step 2: policy export -> edit XML -> re-import.
        r = self._req(
            "GET", "/api/policies/export",
            params={"id": policy_id},
            headers={"Accept": "application/zip"},
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"Policy export failed ({r.status_code}): {r.text}"
            )

        zip_bytes = r.content
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xml_names = [n for n in zf.namelist() if n.endswith(".xml")]
            if not xml_names:
                raise RuntimeError("Policy export ZIP contained no XML file")
            xml_name = xml_names[0]
            raw_xml = zf.read(xml_name)
            other_files = {n: zf.read(n) for n in zf.namelist() if n != xml_name}

        # Register namespaces so round-trip preserves prefixes.
        for prefix, uri in _re.findall(
            r'xmlns(?::([A-Za-z_][A-Za-z0-9_.-]*))?=["\']([^"\']+)["\']',
            raw_xml.decode("utf-8"),
        ):
            ET.register_namespace(prefix if prefix else "", uri)

        root = ET.fromstring(raw_xml)

        # Locate <PackageSettings>.
        pkg_settings = root.find(".//{*}PackageSettings")
        if pkg_settings is None:
            pkg_settings = root.find(".//PackageSettings")
        if pkg_settings is None:
            policy_elem = root.find(".//{*}Policy")
            if policy_elem is None:
                policy_elem = root.find(".//Policy")
            if policy_elem is None:
                raise RuntimeError(
                    f"Policy XML has no <Policy> element — cannot inject SM '{sm_name}'"
                )
            pkg_settings = ET.SubElement(policy_elem, "PackageSettings")

        # Purge stale entries for this SM from ALL SuperMetrics blocks.
        all_sm_blocks = (
            pkg_settings.findall("{*}SuperMetrics")
            or pkg_settings.findall("SuperMetrics")
        )
        for block in all_sm_blocks:
            for entry in list(block):
                entry_tag = (
                    entry.tag.split("}")[-1] if "}" in entry.tag else entry.tag
                )
                if entry_tag == "SuperMetric" and entry.get("id") == sm_id:
                    block.remove(entry)

        # Inject fresh enabled entries for each resource kind.
        for rk in normalised_rks:
            adapter_kind = rk["adapterKind"]
            resource_kind = rk["resourceKind"]

            sm_block = None
            for candidate in (
                pkg_settings.findall("{*}SuperMetrics")
                or pkg_settings.findall("SuperMetrics")
            ):
                if (
                    candidate.get("adapterKind") == adapter_kind
                    and candidate.get("resourceKind") == resource_kind
                ):
                    sm_block = candidate
                    break

            if sm_block is None:
                sm_block = ET.SubElement(
                    pkg_settings,
                    "SuperMetrics",
                    {"adapterKind": adapter_kind, "resourceKind": resource_kind},
                )

            ET.SubElement(sm_block, "SuperMetric", {"enabled": "true", "id": sm_id})

        # Serialise and rebuild ZIP.
        edited_xml = ET.tostring(root, encoding="unicode", xml_declaration=False)
        if not edited_xml.startswith("<?xml"):
            edited_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + edited_xml
        edited_xml_bytes = edited_xml.encode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(xml_name, edited_xml_bytes)
            for name, data in other_files.items():
                zf.writestr(name, data)
        zip_out = buf.getvalue()

        # POST the rebuilt ZIP to /api/policies/import?forceImport=true.
        # Must not send Content-Type: application/json for multipart uploads.
        saved_ct = self._session.headers.pop("Content-Type", None)
        try:
            r = self._session.post(
                f"{self.base}/api/policies/import",
                params={"forceImport": "true"},
                files={"policy": ("exportedPolicies.zip", zip_out, "application/zip")},
            )
        finally:
            if saved_ct is not None:
                self._session.headers["Content-Type"] = saved_ct
        if r.status_code not in (200, 201, 204):
            raise RuntimeError(
                f"Policy import failed for SM '{sm_name}' ({r.status_code}): {r.text}"
            )

    def export_default_policy_xml(self, policy_id: str) -> str:
        """Export a policy and return the raw XML from the ZIP."""
        r = self._req(
            "GET", "/api/policies/export",
            params={"id": policy_id},
            headers={"Accept": "application/zip"},
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"Policy export failed ({r.status_code}): {r.text}")
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    return zf.read(name).decode("utf-8")
        raise RuntimeError("Policy export ZIP contained no XML file")

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
            if r.status_code == 500:
                # The custom group PUT endpoint sometimes returns 500 even when
                # the update was applied. Verify by fetching the group before
                # treating it as fatal.
                chk = self._req("GET", "/api/resources/groups",
                                params={"name": name, "pageSize": 100})
                found = any(
                    (g.get("resourceKey") or {}).get("name") == name
                    for g in (chk.json().get("groups") or [])
                ) if chk.status_code == 200 else False
                if found:
                    _warn(f"Custom group PUT returned 500 but group exists — treating as success: {name}")
                else:
                    _die(f"Custom group PUT failed ({r.status_code}): {r.text}")
            elif r.status_code not in (200, 201, 204):
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

    def _ext_direct_url(self) -> str:
        """Return the Ext.Direct router URL.

        Empirically verified 2026-04-11: /ui/vcops/services/router is the
        correct working URL. The SPA context at
        /vcf-operations/plug/ops/vcops/services/router returns HTTP 400
        because the session JSESSIONID cookie is scoped to /ui, not to the
        /vcf-operations/ path.

        The real fix for the prior "everything returns 500" bug was the
        data shape for deleteView: the old code sent a bare UUID string;
        the correct shape uses viewDefIds with a JSON-stringified [{id,name}]
        array. See context/dashboard_delete_api.md §2026-04-11 update.
        """
        return f"https://{self._host}/ui/vcops/services/router"

    def list_views(self) -> List[Dict[str, Any]]:
        """List all view definitions via Ext.Direct RPC."""
        assert self._session and self._csrf_token
        tid = self._next_tid()
        resp = self._session.post(
            self._ext_direct_url(),
            json=[{
                "action": "viewServiceController",
                "method": "getGroupedViewDefinitionThumbnails",
                "data": [{"start": 0, "limit": 500}],
                "type": "rpc",
                "tid": tid,
            }],
            headers={"secureToken": self._csrf_token},
        )
        resp.raise_for_status()
        result = resp.json()
        if result[0].get("type") == "exception":
            _die(f"View list failed: {result[0].get('message')}")
        grouped = result[0].get("result") or {}
        views: List[Dict[str, Any]] = []
        # API returns a dict keyed by view type (LIST, IMAGE, etc.),
        # each value is a dict keyed by subject name (HostSystem, etc.),
        # each subject value is a list of view objects.
        if isinstance(grouped, dict):
            for view_type_group in grouped.values():
                if isinstance(view_type_group, dict):
                    for subject_views in view_type_group.values():
                        if isinstance(subject_views, list):
                            views.extend(subject_views)
        return views

    def delete_view(self, view_uuid: str, view_name: str) -> None:
        """Delete a view by UUID + name via Ext.Direct RPC.

        The data shape for deleteView is an array containing one dict whose
        'viewDefIds' value is a JSON-stringified array of {id, name} objects:
            "data": [{"viewDefIds": "[{\"id\":\"...\",\"name\":\"...\"}]"}]
        Both id and name are required. Sending a bare UUID (old shape) causes
        the handler to return type:exception "Internal server error."
        See context/dashboard_delete_api.md §2026-04-11 update.
        """
        assert self._session and self._csrf_token
        tid = self._next_tid()
        json_payload = json.dumps([{"id": view_uuid, "name": view_name}])
        resp = self._session.post(
            self._ext_direct_url(),
            json=[{
                "action": "viewServiceController",
                "method": "deleteView",
                "data": [{"viewDefIds": json_payload}],
                "type": "rpc",
                "tid": tid,
            }],
            headers={"secureToken": self._csrf_token},
        )
        resp.raise_for_status()
        result = resp.json()
        if result[0].get("type") == "exception":
            raise RuntimeError(f"deleteView {view_uuid!r} failed: {result[0].get('message')}")

    def list_reports(self) -> List[Dict[str, Any]]:
        """List all report definitions via Ext.Direct RPC.

        Uses getReportDefinitionThumbnails. Returns a flat list of report
        dicts, each containing at least 'id' and 'name'. Response structure
        is {"records": [...], "total": N, ...} inside the result field.
        """
        assert self._session and self._csrf_token
        tid = self._next_tid()
        resp = self._session.post(
            self._ext_direct_url(),
            json=[{
                "action": "reportServiceController",
                "method": "getReportDefinitionThumbnails",
                "data": [{
                    "contentFilter": {"isTenant": False},
                    "resourceContext": None,
                    "page": 1,
                    "start": 0,
                    "limit": 500,
                    "sort": [{"property": "creationTime", "direction": "DESC"}],
                }],
                "type": "rpc",
                "tid": tid,
            }],
            headers={"secureToken": self._csrf_token},
        )
        resp.raise_for_status()
        result = resp.json()
        if result[0].get("type") == "exception":
            _die(f"Report list failed: {result[0].get('message')}")
        raw = result[0].get("result") or {}
        # getReportDefinitionThumbnails returns:
        #   {"records": [...], "total": N, "metaData": {...}, "success": true}
        # Walk common shapes in priority order.
        if isinstance(raw, list):
            return raw
        for key in ("records", "data", "items", "reportDefinitions", "reports"):
            if isinstance(raw.get(key), list):
                return raw[key]
        # Fallback: flatten any lists found one level deep
        report_items: List[Dict[str, Any]] = []
        if isinstance(raw, dict):
            for v in raw.values():
                if isinstance(v, list):
                    report_items.extend(v)
        return report_items

    def delete_reports(self, reports: List[Tuple[str, str]]) -> None:
        """Delete report definitions by (uuid, name) tuples via Ext.Direct RPC.

        The data shape for deleteReportDefinitions is a BARE DICT (not an
        array) whose 'reportDefIds' value is a JSON-stringified array of
        {id, name} objects:
            "data": {"reportDefIds": "[{\"id\":\"...\",\"name\":\"...\"}]"}
        This differs from deleteView which wraps data in an array of one dict.
        Success response is {"type":"rpc"} with no "result" key.
        See context/dashboard_delete_api.md §2026-04-11 update.
        """
        assert self._session and self._csrf_token
        tid = self._next_tid()
        json_payload = json.dumps([{"id": uid, "name": name} for uid, name in reports])
        resp = self._session.post(
            self._ext_direct_url(),
            json=[{
                "action": "reportServiceController",
                "method": "deleteReportDefinitions",
                "data": {"reportDefIds": json_payload},  # BARE DICT, not array
                "type": "rpc",
                "tid": tid,
            }],
            headers={"secureToken": self._csrf_token},
        )
        resp.raise_for_status()
        result = resp.json()
        if result[0].get("type") == "exception":
            raise RuntimeError(
                f"deleteReportDefinitions failed: {result[0].get('message')}"
            )

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
                         marker: str, owner_id: str, username: str,
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
                    "users": [{"userName": username, "userId": owner_id}],
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
    print(f"VCF Content Factory -- {mode}")
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
#   content_type   str   key in bundle.json content map (e.g. "supermetrics")
#   manifest_key   str   same as content_type; key in manifest["content"]
#   install_fn     callable(ctx) -> None   runs the install step
#   uninstall_fn   callable(ctx) -> None  runs the uninstall step
#   install_label  str   human-readable step label for install
#   uninstall_label str  human-readable step label for uninstall
#   install_order  int   lower runs first (install)
#   uninstall_order int  lower runs first (uninstall = reverse install order)
#   needs_ui       bool  True if this type requires UIClient
#
# Detection predicate (install): manifest["content"].get(manifest_key) exists
#   AND its file resolves on disk under bundle_dir.
# Detection predicate (uninstall): manifest["content"].get(content_type) has
#   items with names.
#
# The "ctx" object passed to each function is a plain dict with:
#   client        Client            authenticated Suite API client
#   ui_client     UIClient | None   authenticated UI session client (or None)
#   marker        str               instance marker filename
#   owner_id      str               current user UUID
#   args          argparse.Namespace
#   warnings      List[str]         accumulate WARN strings here
#   bundle_dir    Path              resolved bundle directory
#   manifest      dict              the bundle's manifest (bundle.json)
# ---------------------------------------------------------------------------

def _install_supermetrics(ctx: Dict) -> None:
    bundle_dir = ctx["bundle_dir"]
    manifest = ctx["manifest"]
    sm_file = bundle_dir / manifest["content"]["supermetrics"]["file"]
    sm_dict = _load_json_from_path(sm_file)
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
    bundle_dir = ctx["bundle_dir"]
    manifest = ctx["manifest"]
    dash_file = bundle_dir / manifest["content"]["dashboards"]["file"]
    dash_json = dash_file.read_text()

    # Views XML (in same bundle content dir, via views manifest key if present)
    views_xml = ""
    if "views" in manifest.get("content", {}):
        views_file = bundle_dir / manifest["content"]["views"]["file"]
        if views_file.exists():
            views_xml = views_file.read_text()

    owner_id = ctx["owner_id"]
    dash_ids = _extract_dashboard_ids(dash_json.replace("PLACEHOLDER_USER_ID", owner_id))
    n_views = 1 if views_xml else 0
    dash_zip = _build_dashboard_zip(
        views_xml, dash_json, ctx["marker"], owner_id, ctx["username"],
        n_views=n_views, n_dashboards=1, dashboard_ids=dash_ids,
    )
    ctx["client"].import_content_zip(dash_zip, "dashboard + view")
    _ok(f"Imported {n_views} view(s) + 1 dashboard")


def _install_sm_enable(ctx: Dict) -> None:
    args = ctx["args"]
    if args.skip_enable:
        print("  (--skip-enable set: skipping)")
        return
    bundle_dir = ctx["bundle_dir"]
    manifest = ctx["manifest"]
    sm_file = bundle_dir / manifest["content"]["supermetrics"]["file"]
    sm_dict = _load_json_from_path(sm_file)
    # sm_dict is keyed by UUID: {uuid: {name, formula, description, unitId, resourceKinds}}
    sm_entries = list(sm_dict.values())
    names = [sm["name"] for sm in sm_entries]
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

    # Build unverified map: {server_id: (name, resource_kinds)}
    unverified = {}
    for sm in sm_entries:
        name = sm["name"]
        sm_id = server_ids.get(name)
        if not sm_id:
            warn = f"Could not resolve ID for '{name}' -- skipping enable"
            _warn(warn)
            ctx["warnings"].append(warn)
            continue
        unverified[sm_id] = (name, sm["resourceKinds"])

    if not unverified:
        return

    SM_ENABLE_ATTEMPTS = 3
    SM_ENABLE_VERIFY_DELAY = 2
    policy_id = ctx["client"].get_default_policy_id()

    for attempt in range(1, SM_ENABLE_ATTEMPTS + 1):
        assign_errors = {}
        for sm_id, (name, rk) in list(unverified.items()):
            try:
                ctx["client"].enable_sm_on_default_policy(sm_id, name, rk)
            except RuntimeError as exc:
                assign_errors[sm_id] = str(exc)

        time.sleep(SM_ENABLE_VERIFY_DELAY)

        try:
            policy_xml = ctx["client"].export_default_policy_xml(policy_id)
            status = _verify_supermetrics_enabled(
                policy_xml, list(unverified.keys()))
        except RuntimeError as exc:
            _warn(f"Policy export failed on attempt {attempt}: {exc}")
            if attempt < SM_ENABLE_ATTEMPTS:
                continue
            for sm_id, (name, _) in unverified.items():
                warn = f"Enable FAILED for '{name}': could not verify"
                _warn(warn)
                ctx["warnings"].append(warn)
            break

        still_pending = {}
        for sm_id, (name, rk) in list(unverified.items()):
            if sm_id in assign_errors:
                warn = assign_errors[sm_id]
                _warn(warn)
                ctx["warnings"].append(warn)
            elif status.get(sm_id):
                _ok(f"Enabled: {name}")
            else:
                if attempt < SM_ENABLE_ATTEMPTS:
                    still_pending[sm_id] = (name, rk)
                else:
                    warn = (f"Enable FAILED for '{name}': assign returned 200 "
                            f"but SM not in Default Policy after "
                            f"{SM_ENABLE_ATTEMPTS} attempts")
                    _warn(warn)
                    ctx["warnings"].append(warn)

        unverified = still_pending
        if not unverified:
            break
        print(f"    [enable-verify {attempt}/{SM_ENABLE_ATTEMPTS}] "
              f"{len(unverified)} SM(s) not verified, retrying...")


def _install_customgroups(ctx: Dict) -> None:
    bundle_dir = ctx["bundle_dir"]
    manifest = ctx["manifest"]
    cg_file = bundle_dir / manifest["content"]["customgroups"]["file"]
    cg_data = _load_json_from_path(cg_file)
    if isinstance(cg_data, dict):
        cg_data = [cg_data]
    for cg_payload in cg_data:
        cg_name = cg_payload["resourceKey"]["name"]
        ctx["client"].upsert_custom_group(cg_payload)
        _ok(f"Upserted: {cg_name}")


def _install_symptoms(ctx: Dict) -> None:
    bundle_dir = ctx["bundle_dir"]
    manifest = ctx["manifest"]
    sym_file = bundle_dir / manifest["content"]["symptoms"]["file"]
    symptoms = _load_json_from_path(sym_file)
    for payload in symptoms:
        name = payload.get("name", "unknown")
        existing = None
        # Search by name
        page, page_size = 0, 1000
        while True:
            r = ctx["client"]._req("GET", "/api/symptomdefinitions",
                                   params={"page": page, "pageSize": page_size})
            if r.status_code != 200:
                _warn(f"Symptom list failed ({r.status_code})")
                break
            body = r.json()
            for sd in body.get("symptomDefinitions") or []:
                if sd.get("name") == name:
                    existing = sd
                    break
            if existing:
                break
            info = body.get("pageInfo") or {}
            total = info.get("totalCount", 0)
            if (page + 1) * page_size >= total:
                break
            page += 1

        if existing:
            payload["id"] = existing["id"]
            r = ctx["client"]._req("PUT", "/api/symptomdefinitions", json=payload)
            if r.status_code != 200:
                warn = f"Symptom update failed for '{name}' ({r.status_code}): {r.text}"
                _warn(warn)
                ctx["warnings"].append(warn)
                continue
            _ok(f"Updated: {name}")
        else:
            r = ctx["client"]._req("POST", "/api/symptomdefinitions", json=payload)
            if r.status_code not in (200, 201):
                warn = f"Symptom create failed for '{name}' ({r.status_code}): {r.text}"
                _warn(warn)
                ctx["warnings"].append(warn)
                continue
            _ok(f"Created: {name}")


def _install_alerts(ctx: Dict) -> None:
    bundle_dir = ctx["bundle_dir"]
    manifest = ctx["manifest"]
    alert_file = bundle_dir / manifest["content"]["alerts"]["file"]
    alerts = _load_json_from_path(alert_file)

    # Resolve symptom name → server ID map
    symptom_map: Dict[str, str] = {}
    page, page_size = 0, 1000
    while True:
        r = ctx["client"]._req("GET", "/api/symptomdefinitions",
                               params={"page": page, "pageSize": page_size})
        if r.status_code != 200:
            _warn(f"Symptom list for alert resolution failed ({r.status_code})")
            break
        body = r.json()
        for sd in body.get("symptomDefinitions") or []:
            if sd.get("name") and sd.get("id"):
                symptom_map[sd["name"]] = sd["id"]
        info = body.get("pageInfo") or {}
        total = info.get("totalCount", 0)
        if (page + 1) * page_size >= total:
            break
        page += 1

    for alert_data in alerts:
        name = alert_data.get("name", "unknown")

        # Build wire format with resolved symptom IDs
        try:
            wire = _alert_to_wire(alert_data, symptom_map)
        except Exception as exc:
            warn = f"Alert '{name}' wire conversion failed: {exc}"
            _warn(warn)
            ctx["warnings"].append(warn)
            continue

        # Upsert by name
        existing = None
        page = 0
        while True:
            r = ctx["client"]._req("GET", "/api/alertdefinitions",
                                   params={"page": page, "pageSize": 1000})
            if r.status_code != 200:
                break
            body = r.json()
            for ad in body.get("alertDefinitions") or []:
                if ad.get("name") == name:
                    existing = ad
                    break
            if existing:
                break
            info = body.get("pageInfo") or {}
            total = info.get("totalCount", 0)
            if (page + 1) * 1000 >= total:
                break
            page += 1

        if existing:
            wire["id"] = existing["id"]
            r = ctx["client"]._req("PUT", "/api/alertdefinitions", json=wire)
            if r.status_code != 200:
                warn = f"Alert update failed for '{name}' ({r.status_code}): {r.text}"
                _warn(warn)
                ctx["warnings"].append(warn)
                continue
            _ok(f"Updated: {name}")
        else:
            r = ctx["client"]._req("POST", "/api/alertdefinitions", json=wire)
            if r.status_code not in (200, 201):
                warn = f"Alert create failed for '{name}' ({r.status_code}): {r.text}"
                _warn(warn)
                ctx["warnings"].append(warn)
                continue
            _ok(f"Created: {name}")


def _alert_to_wire(alert_data: dict, symptom_map: Dict[str, str]) -> dict:
    """Convert the stored alert payload to API wire format with resolved symptom IDs."""
    ss = alert_data.get("symptom_sets") or {}
    top_op = (ss.get("operator") or "ALL").upper()
    sets = ss.get("sets") or []

    wire_sets = []
    for s in sets:
        defined_on = (s.get("defined_on") or "SELF").upper()
        op = (s.get("operator") or "ALL").upper()
        symptom_ids = []
        for sym in s.get("symptoms") or []:
            sym_name = sym.get("name", "")
            sid = symptom_map.get(sym_name)
            if not sid:
                raise RuntimeError(f"symptom '{sym_name}' not found on instance")
            symptom_ids.append(sid)
        wire_set: dict = {
            "type": "SYMPTOM_SET",
            "relation": defined_on,
            "symptomSetOperator": "AND" if op == "ALL" else "OR",
            "symptomDefinitionIds": symptom_ids,
        }
        tt = s.get("threshold_type")
        tv = s.get("threshold_value")
        if defined_on != "SELF" and tt:
            wire_set["aggregation"] = tt
            if tv is not None:
                wire_set["value"] = float(tv)
        wire_sets.append(wire_set)

    if len(wire_sets) == 1:
        base_ss = wire_sets[0]
    else:
        base_ss = {
            "type": "SYMPTOM_SET_COMPOSITE",
            "operator": "AND" if top_op == "ALL" else "OR",
            "symptom-sets": wire_sets,
        }

    state = {
        "severity": alert_data.get("criticality", "AUTO"),
        "base-symptom-set": base_ss,
        "impact": {
            "impactType": "BADGE",
            "detail": alert_data.get("impact_badge", "HEALTH"),
        },
    }

    return {
        "name": alert_data["name"],
        "description": alert_data.get("description", ""),
        "adapterKindKey": alert_data.get("adapter_kind", ""),
        "resourceKindKey": alert_data.get("resource_kind", ""),
        "waitCycles": alert_data.get("wait_cycles", 1),
        "cancelCycles": alert_data.get("cancel_cycles", 1),
        "type": alert_data.get("type", 16),
        "subType": alert_data.get("sub_type", 3),
        "states": [state],
    }


def _uninstall_symptoms(ctx: Dict) -> None:
    names: List[str] = ctx["names"]
    warnings = ctx["warnings"]
    # Build name→id map
    sym_ids: Dict[str, str] = {}
    page, page_size = 0, 1000
    while True:
        r = ctx["client"]._req("GET", "/api/symptomdefinitions",
                               params={"page": page, "pageSize": page_size})
        if r.status_code != 200:
            break
        body = r.json()
        for sd in body.get("symptomDefinitions") or []:
            if sd.get("name") in names and sd.get("id"):
                sym_ids[sd["name"]] = sd["id"]
        info = body.get("pageInfo") or {}
        total = info.get("totalCount", 0)
        if (page + 1) * page_size >= total:
            break
        page += 1
    for name in names:
        sid = sym_ids.get(name)
        if not sid:
            _warn(f"Symptom not found (already removed?): {name}")
            warnings.append(f"Symptom not found: {name}")
            continue
        r = ctx["client"]._req("DELETE", f"/api/symptomdefinitions/{sid}")
        if r.status_code in (200, 204):
            _ok(f"Deleted: {name}")
        else:
            warn = f"Symptom delete failed for '{name}' ({r.status_code})"
            _warn(warn)
            warnings.append(warn)


def _uninstall_alerts(ctx: Dict) -> None:
    names: List[str] = ctx["names"]
    warnings = ctx["warnings"]
    alert_ids: Dict[str, str] = {}
    page = 0
    while True:
        r = ctx["client"]._req("GET", "/api/alertdefinitions",
                               params={"page": page, "pageSize": 1000})
        if r.status_code != 200:
            break
        body = r.json()
        for ad in body.get("alertDefinitions") or []:
            if ad.get("name") in names and ad.get("id"):
                alert_ids[ad["name"]] = ad["id"]
        info = body.get("pageInfo") or {}
        total = info.get("totalCount", 0)
        if (page + 1) * 1000 >= total:
            break
        page += 1
    for name in names:
        aid = alert_ids.get(name)
        if not aid:
            _warn(f"Alert not found (already removed?): {name}")
            warnings.append(f"Alert not found: {name}")
            continue
        r = ctx["client"]._req("DELETE", f"/api/alertdefinitions/{aid}")
        if r.status_code in (200, 204):
            _ok(f"Deleted: {name}")
        else:
            warn = f"Alert delete failed for '{name}' ({r.status_code})"
            _warn(warn)
            warnings.append(warn)


def _build_reports_zip(reports_xml: str, marker: str, owner_id: str) -> bytes:
    """Build a reports content-zip from the reports XML string."""
    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w", zipfile.ZIP_DEFLATED) as inner:
        inner.writestr("content.xml", reports_xml)
    inner_bytes = inner_buf.getvalue()

    n_reports = reports_xml.count("<ReportDef ")

    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w", zipfile.ZIP_DEFLATED) as outer:
        outer.writestr(marker, owner_id)
        outer.writestr("reports.zip", inner_bytes)
        outer.writestr(
            "configuration.json",
            json.dumps({"reports": n_reports, "type": "CUSTOM"}, indent=2),
        )
    return outer_buf.getvalue()


def _install_reports(ctx: Dict) -> None:
    bundle_dir = ctx["bundle_dir"]
    manifest = ctx["manifest"]
    reports_file = bundle_dir / manifest["content"]["reports"]["file"]
    reports_xml = reports_file.read_text(encoding="utf-8")
    reports_zip = _build_reports_zip(reports_xml, ctx["marker"], ctx["owner_id"])
    ctx["client"].import_content_zip(reports_zip, "reports")
    n_reports = reports_xml.count("<ReportDef ")
    _ok(f"Imported {n_reports} report definition(s)")
    # Note: report uninstall (like view and dashboard uninstall) requires the
    # admin UI session via the SPA Ext.Direct path. Run --uninstall as admin.


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
        v.get("name", ""): v.get("viewDefinitionKey", v.get("id", ""))
        for v in all_views
        if v.get("name") and (v.get("viewDefinitionKey") or v.get("id"))
    }
    for name in names:
        view_id = view_by_name.get(name)
        if not view_id:
            _warn(f"View not found (already removed?): {name}")
            warnings.append(f"View not found: {name}")
            continue
        try:
            ui_client.delete_view(view_id, name)
            _ok(f"Deleted: {name}")
        except RuntimeError as exc:
            warn = f"View delete failed for '{name}': {exc}"
            _warn(warn)
            warnings.append(warn)


def _uninstall_reports(ctx: Dict) -> None:
    """Delete report definitions via the UI session (SPA Ext.Direct path).

    Report delete requires admin UI session (same constraint as dashboards
    and views -- the needs_ui guard in the registry enforces this).
    """
    ui_client = ctx["ui_client"]
    names: List[str] = ctx["names"]
    warnings = ctx["warnings"]
    all_reports = ui_client.list_reports()
    report_by_name: Dict[str, str] = {
        r.get("name", ""): r.get("id", "")
        for r in all_reports
        if r.get("name") and r.get("id")
    }
    to_delete: List[Tuple[str, str]] = []
    for name in names:
        report_id = report_by_name.get(name)
        if not report_id:
            _warn(f"Report not found (already removed?): {name}")
            warnings.append(f"Report not found: {name}")
            continue
        to_delete.append((report_id, name))
    if to_delete:
        try:
            ui_client.delete_reports(to_delete)
            for _, name in to_delete:
                _ok(f"Deleted: {name}")
        except RuntimeError as exc:
            warn = f"Report batch delete failed: {exc}"
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


# ---------------------------------------------------------------------------
# Registry helpers: detection predicates using the new manifest_key pattern
# ---------------------------------------------------------------------------

def _bundle_has_key(bundle: Dict, manifest_key: str) -> bool:
    """True if the bundle manifest has the given content key AND its file exists."""
    manifest = bundle["manifest"]
    content = manifest.get("content") or {}
    section = content.get(manifest_key)
    if not section:
        return False
    rel = section.get("file", "")
    if not rel:
        return False
    return (bundle["dir"] / rel).exists()


def _bundle_uninstall_names(bundle: Dict, content_type: str) -> List[str]:
    """Return the list of names to uninstall for a given content type."""
    content = bundle["manifest"].get("content") or {}
    section = content.get(content_type) or {}
    return [item["name"] for item in (section.get("items") or []) if item.get("name")]


# Registry: ordered by install_order.
# To add a new content type, append an entry here.  No other changes needed.
_CONTENT_REGISTRY: List[Dict] = [
    {
        "content_type": "supermetrics",
        "manifest_key": "supermetrics",
        "install_label": "Importing super metrics...",
        "install_fn": _install_supermetrics,
        "install_order": 1,
        "uninstall_label": "Deleting super metric(s)...",
        "uninstall_fn": _uninstall_supermetrics,
        "uninstall_order": 40,
        "needs_ui": False,
    },
    {
        "content_type": "views_and_dashboards",  # synthetic: triggered by dashboards key
        "manifest_key": "dashboards",
        "install_label": "Importing view + dashboard...",
        "install_fn": _install_dashboards,
        "install_order": 2,
        "uninstall_label": None,
        "uninstall_fn": None,
        "uninstall_order": None,
        "needs_ui": False,
    },
    {
        "content_type": "sm_enable",  # synthetic: triggered by supermetrics key
        "manifest_key": "supermetrics",
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
        "manifest_key": "customgroups",
        "install_label": "Upserting custom group(s)...",
        "install_fn": _install_customgroups,
        "install_order": 4,
        "uninstall_label": "Deleting custom group(s)...",
        "uninstall_fn": _uninstall_customgroups,
        "uninstall_order": 50,
        "needs_ui": False,
    },
    {
        "content_type": "reports",
        "manifest_key": "reports",
        "install_label": "Importing report definition(s)...",
        "install_fn": _install_reports,
        "install_order": 5,
        "uninstall_label": None,
        "uninstall_fn": None,
        "uninstall_order": None,
        "needs_ui": False,
        # Uninstall is handled by a separate uninstall-only registry entry below.
    },
    {
        "content_type": "symptoms",
        "manifest_key": "symptoms",
        "install_label": "Upserting symptom definition(s)...",
        "install_fn": _install_symptoms,
        "install_order": 6,
        "uninstall_label": "Deleting symptom definition(s)...",
        "uninstall_fn": _uninstall_symptoms,
        "uninstall_order": 55,
        "needs_ui": False,
    },
    {
        "content_type": "alerts",
        "manifest_key": "alerts",
        "install_label": "Upserting alert definition(s)...",
        "install_fn": _install_alerts,
        "install_order": 7,
        "uninstall_label": "Deleting alert definition(s)...",
        "uninstall_fn": _uninstall_alerts,
        "uninstall_order": 35,
        "needs_ui": False,
    },
    # Uninstall-only entries for dashboards, reports, and views (reverse of install):
    # Order: dashboards first (10), then reports (15, since reports reference views),
    # then views (20). All require the admin UI session via SPA Ext.Direct.
    {
        "content_type": "dashboards",
        "manifest_key": None,    # uninstall-only; no install predicate
        "install_label": None,
        "install_fn": None,
        "install_order": None,
        "uninstall_label": "Deleting dashboard(s)...",
        "uninstall_fn": _uninstall_dashboards,
        "uninstall_order": 10,
        "needs_ui": True,
    },
    {
        "content_type": "reports",
        "manifest_key": None,    # uninstall-only; install is handled above
        "install_label": None,
        "install_fn": None,
        "install_order": None,
        "uninstall_label": "Deleting report definition(s)...",
        "uninstall_fn": _uninstall_reports,
        "uninstall_order": 15,
        "needs_ui": True,
    },
    {
        "content_type": "views",
        "manifest_key": None,
        "install_label": None,
        "install_fn": None,
        "install_order": None,
        "uninstall_label": "Deleting view(s)...",
        "uninstall_fn": _uninstall_views,
        "uninstall_order": 20,
        "needs_ui": True,
    },
]


# ---------------------------------------------------------------------------
# Per-bundle install / uninstall
# ---------------------------------------------------------------------------

def _install_one_bundle(bundle: Dict, global_ctx: Dict, step_base: int,
                        total_steps: int) -> Tuple[int, List[str]]:
    """Install one bundle.  Returns (steps_used, warnings)."""
    manifest = bundle["manifest"]
    bundle_dir = bundle["dir"]
    name = manifest.get("name", bundle["slug"])

    active = [
        e for e in _CONTENT_REGISTRY
        if e["install_fn"] is not None
        and e["manifest_key"] is not None
        and _bundle_has_key(bundle, e["manifest_key"])
    ]
    active.sort(key=lambda e: e["install_order"])

    warnings: List[str] = []
    ctx: Dict = {
        **global_ctx,
        "bundle_dir": bundle_dir,
        "manifest": manifest,
        "warnings": warnings,
        "names": [],
    }

    step = step_base
    for entry in active:
        step += 1
        _step(step, total_steps, f"[{name}] {entry['install_label']}")
        entry["install_fn"](ctx)

    return step - step_base, warnings


def _uninstall_one_bundle(bundle: Dict, global_ctx: Dict, step_base: int,
                          total_steps: int) -> Tuple[int, List[str]]:
    """Uninstall one bundle.  Returns (steps_used, warnings)."""
    manifest = bundle["manifest"]
    name = manifest.get("name", bundle["slug"])

    active = [
        e for e in _CONTENT_REGISTRY
        if e["uninstall_fn"] is not None
        and e["uninstall_order"] is not None
        and _bundle_uninstall_names(bundle, e["content_type"])
    ]
    active.sort(key=lambda e: e["uninstall_order"])

    warnings: List[str] = []
    ctx: Dict = {
        **global_ctx,
        "bundle_dir": bundle["dir"],
        "manifest": manifest,
        "warnings": warnings,
        "names": [],
    }

    step = step_base
    for entry in active:
        names = _bundle_uninstall_names(bundle, entry["content_type"])
        if not names:
            continue
        step += 1
        label = entry["uninstall_label"].replace("...", f" ({len(names)})...")
        _step(step, total_steps, f"[{name}] {label}")
        ctx["names"] = names
        entry["uninstall_fn"](ctx)

    return step - step_base, warnings


# ---------------------------------------------------------------------------
# Install flow
# ---------------------------------------------------------------------------
def _run_install(args: argparse.Namespace, host: str, user: str,
                 auth_source: str, password: str, verify_ssl: bool,
                 selected_bundles: List[Dict]) -> None:

    # Count active entries per bundle for total step count
    total_content_steps = 0
    for bundle in selected_bundles:
        total_content_steps += sum(
            1 for e in _CONTENT_REGISTRY
            if e["install_fn"] is not None
            and e["manifest_key"] is not None
            and _bundle_has_key(bundle, e["manifest_key"])
        )

    TOTAL_STEPS = 3 + total_content_steps   # auth + marker + owner + content
    print(f"\nInstalling {len(selected_bundles)} bundle(s) onto {host}...")

    client = Client(host, user, password, auth_source, verify_ssl)
    step = 0

    step += 1
    _step(step, TOTAL_STEPS, f"Authenticating as {user}@{host} (auth: {auth_source}) ...")
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

    global_ctx: Dict = {
        "client": client,
        "ui_client": None,
        "marker": marker,
        "owner_id": owner_id,
        "username": client._user,
        "args": args,
        "force": False,
    }

    all_warnings: List[str] = []
    for bundle in selected_bundles:
        used, warnings = _install_one_bundle(bundle, global_ctx, step, TOTAL_STEPS)
        step += used
        all_warnings.extend(warnings)

    print()
    enable_warnings = [w for w in all_warnings if "enable" in w.lower() or "resolve" in w.lower()]
    other_warnings = [w for w in all_warnings if w not in enable_warnings]
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
# Uninstall flow
# ---------------------------------------------------------------------------
def _run_uninstall(args: argparse.Namespace, host: str, user: str,
                   auth_source: str, password: str, verify_ssl: bool,
                   selected_bundles: List[Dict]) -> None:
    force = args.force

    # Determine if any bundle needs UI session (dashboards/views/reports).
    needs_ui = any(
        e["needs_ui"] and e["uninstall_fn"] is not None
        and _bundle_uninstall_names(bundle, e["content_type"])
        for bundle in selected_bundles
        for e in _CONTENT_REGISTRY
    )

    # Admin guard is enforced in main() before credentials are prompted.
    # _run_uninstall trusts that user=="admin" when needs_ui is True.

    # Count total uninstall steps
    total_content_steps = 0
    for bundle in selected_bundles:
        for e in _CONTENT_REGISTRY:
            if e["uninstall_fn"] is not None and e["uninstall_order"] is not None:
                if _bundle_uninstall_names(bundle, e["content_type"]):
                    total_content_steps += 1

    n_steps = 1 + total_content_steps
    if needs_ui:
        n_steps += 2  # ui_auth + ui_logout

    print(f"\nUninstalling {len(selected_bundles)} bundle(s) from {host}...")
    if force:
        print("(--force: skipping dependency checks)")
    print("Content to remove:")
    for bundle in selected_bundles:
        bname = bundle["manifest"].get("name", bundle["slug"])
        print(f"  Bundle: {bname}")
        for e in _CONTENT_REGISTRY:
            if e["uninstall_fn"] is not None and e["uninstall_order"] is not None:
                names = _bundle_uninstall_names(bundle, e["content_type"])
                if names:
                    print(f"    {e['content_type'].capitalize()} ({len(names)}): {', '.join(names)}")

    # Check that any bundle has something to remove
    has_anything = any(
        _bundle_uninstall_names(bundle, e["content_type"])
        for bundle in selected_bundles
        for e in _CONTENT_REGISTRY
        if e["uninstall_fn"] is not None
    )
    if not has_anything:
        print("  (nothing to remove -- bundles contain no removable content)")
        sys.exit(0)

    warnings_all: List[str] = []
    step = 0

    suite_client = Client(host, user, password, auth_source, verify_ssl)
    ui_client = UIClient(host, user, password, auth_source, verify_ssl)

    step += 1
    _step(step, n_steps, f"Authenticating as {user}@{host} (auth: {auth_source}) ...")
    suite_client.authenticate()
    _ok("Authenticated")

    if needs_ui:
        step += 1
        _step(step, n_steps, "Starting UI session (for dashboard/view/report delete)...")
        ui_client.login()
        _ok("UI session established")

    global_ctx: Dict = {
        "client": suite_client,
        "ui_client": ui_client if needs_ui else None,
        "marker": None,
        "owner_id": None,
        "args": args,
        "force": force,
    }

    for bundle in selected_bundles:
        used, warnings = _uninstall_one_bundle(bundle, global_ctx, step, n_steps)
        step += used
        warnings_all.extend(warnings)

    if needs_ui:
        step += 1
        _step(step, n_steps, "Closing UI session...")
        ui_client.logout()
        _ok("UI session closed")

    print()
    if warnings_all:
        not_found = [w for w in warnings_all if "not found" in w]
        real_failures = [w for w in warnings_all if "not found" not in w]
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
        description="Install or uninstall VCF Content Factory bundles.\n"
                    "Run with no arguments for interactive install prompts.\n"
                    "Use --uninstall to remove all content these bundles installed.\n"
                    "Note: Uninstall requires the 'admin' account for dashboard/view cleanup.")
    ap.add_argument("--install", action="store_true",
                    help="Install mode (default when no mode flag is given)")
    ap.add_argument("--uninstall", action="store_true",
                    help="Uninstall mode: delete all content in selected bundles from the instance")
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

    # Discover bundles before prompting for credentials.
    bundles = _discover_bundles()
    if not bundles:
        _die("No bundles found. Expected bundles/<slug>/bundle.json or a legacy content/ directory.")

    mode = "uninstall" if args.uninstall else "install"
    selected = _select_bundles(bundles, mode)
    _print_selection_summary(selected, mode)

    # Early admin-guard: if any selected bundle requires the UI session
    # (dashboards/views/reports), check the user before prompting for
    # credentials or printing any further output.  When the user is already
    # known from --user / VCFOPS_USER, this fires immediately after bundle
    # selection so the operator sees the error before any credential prompts.
    # When the user is not yet known (interactive), the check is deferred to
    # after _prompt_credentials below.
    if args.uninstall:
        _ui_needed = any(
            e["needs_ui"] and e["uninstall_fn"] is not None
            and _bundle_uninstall_names(bundle, e["content_type"])
            for bundle in selected
            for e in _CONTENT_REGISTRY
        )
        if _ui_needed and args.user and args.user != "admin":
            print(
                "ERROR: Dashboard, view, and report uninstall requires the 'admin' account.\n"
                "       VCF Ops locks imported content to admin ownership. Only the\n"
                "       admin user's UI session can delete them.\n"
                "       Re-run with --user admin (or set VCFOPS_USER=admin).",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        _ui_needed = False

    cred_mode = "uninstaller" if args.uninstall else "installer"
    host, user, auth_source, password = _prompt_credentials(args, cred_mode)

    # Post-credentials admin guard: covers the interactive case where user
    # was not set via --user / VCFOPS_USER and was entered at the prompt.
    if args.uninstall and _ui_needed and user != "admin":
        print(
            "ERROR: Dashboard, view, and report uninstall requires the 'admin' account.\n"
            "       VCF Ops locks imported content to admin ownership. Only the\n"
            "       admin user's UI session can delete them.\n"
            "       Re-run with --user admin (or set VCFOPS_USER=admin).",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.skip_ssl_verify:
        print("WARNING: TLS certificate verification disabled.")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    verify_ssl = not args.skip_ssl_verify

    if args.uninstall:
        _run_uninstall(args, host, user, auth_source, password, verify_ssl, selected)
    else:
        _run_install(args, host, user, auth_source, password, verify_ssl, selected)


if __name__ == "__main__":
    main()
