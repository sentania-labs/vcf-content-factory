"""Dependency walker and YAML writer for vcfcf_extractor.

Given a dashboard UUID (or name), walks the full dependency graph using BFS:

  dashboard  ->  views  ->  super metrics  ->  (transitive SM references)

Emits factory-shape YAML under bundles/third_party/<slug>/ and a bundle
manifest at bundles/third_party/<slug>.yaml.

Design decisions:
- BFS keyed on (kind, uuid) to prevent cycles and repeated work.
- Seen-set prevents duplicate writes for diamonds (SM referenced by
  multiple views).
- Non-overwrite invariant: if a resolved UUID matches an existing id:
  under the factory repo's content/supermetrics, content/views or
  content/dashboards, the file is SKIPPED with a WARN, not overwritten.
- Missing deps (404 on a referenced UUID) abort the walk with a clear
  error naming the parent.
- Custom groups: Phase 1 emits WARN only; no extraction attempted.
- Network clients are reused (single auth session per client type).

M2 row 4 split: the pure parsers and YAML writers live in
``vcfcf_core.extractor.extractor``. This module keeps the live half (suite
API and UI clients, content-export calls, the instance-backed SM name
cache, ``_scan_existing_ids`` over the repo root, ``list_dashboards``,
``extract_dashboard``) and the ``${this}`` audit helpers that print the
extractor's WARNs. The core names it calls are imported by name below;
every other core name (``_parse_view_def_element``, ``_widget_to_yaml_dict``,
``_to_yaml_str``, ...) is served by module ``__getattr__`` and reads back the
identical core object. That is a read-only view: a monkeypatch on this
module binds a new attribute here and the core parsers keep calling their
own. To affect a running extraction, patch ``vcfcf_core.extractor.extractor``.
"""
from __future__ import annotations

import re
import sys
from collections import deque
from pathlib import Path
from typing import Optional

from vcfcf_core.extractor import extractor as _core
from vcfcf_core.extractor.extractor import (
    _collect_enablement_entries,
    _dashboards_from_export_zip,
    _info,
    _parse_view_xml,
    _resource_kinds_from_formula,
    _rewrite_formula,
    _safe_filename,
    _supermetrics_from_export_zip,
    _warn,
    _write_dashboard_yaml,
    _write_manifest,
    _write_sm_yaml,
    _write_view_yaml,
)

# Repo root: three levels above (src/vcfcf_extractor/extractor.py -> repo root).
# Factory-side by design: the library never binds one (M2 row 4).
_REPO_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Live clients
# ---------------------------------------------------------------------------

def _build_sm_client(host: str, user: str, password: str, verify_ssl: bool):
    """Build an authenticated VCFOpsClient (suite-api) for super metric calls."""
    from vcfcf_supermetrics.client import VCFOpsClient
    return VCFOpsClient(
        host=host, username=user, password=password, verify_ssl=verify_ssl
    )


def _build_ui_client(host: str, user: str, password: str, verify_ssl: bool):
    """Build an authenticated /ui/ Struts session for dashboard calls.

    Uses the three-step /ui/ login pattern documented in
    knowledge/context/api-surface/pak_ui_upload_investigation.md and implemented in
    vcfcf_managementpacks/installer.py _UISession.login():

      Step 1: GET /ui/login.action?vcf=1      -- seed JSESSIONID
      Step 2: POST /ui/login.action (form)    -- authenticate
      Step 3: GET /ui/index.action (no redir) -- receive OPS_SESSION cookie;
                                                 decode to get csrfToken

    IMPORTANT: Do NOT follow the 302 redirect from index.action.
    Following it invalidates OPS_SESSION.

    Returns (session, host, csrf_token).
    """
    import base64
    import json as _json
    import requests
    import urllib3

    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    s = requests.Session()
    s.verify = verify_ssl

    # Step 1: seed JSESSIONID
    try:
        s.get(f"https://{host}/ui/login.action", params={"vcf": "1"})
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to https://{host}: {e}. "
            "Check VCFOPS_HOST and network connectivity."
        ) from e

    # Step 2: authenticate with form fields (not JSON)
    r = s.post(
        f"https://{host}/ui/login.action",
        data={
            "mainAction": "login",
            "userName": user,
            "password": password,
            "authSourceId": "localItem",
            "authSourceName": "Local Account",
            "authSourceType": "",
            "forceLogin": "false",
            "timezone": "0",
            "languageCode": "us",
        },
    )
    if r.text.strip() != "ok":
        raise RuntimeError(
            f"UI login failed for user '{user}': {r.text!r}. "
            "Check VCFOPS_USER and VCFOPS_PASSWORD."
        )

    # Step 3: receive OPS_SESSION cookie (do NOT follow redirect)
    r = s.get(
        f"https://{host}/ui/index.action",
        allow_redirects=False,
    )
    ops_cookie = r.cookies.get("OPS_SESSION") or s.cookies.get("OPS_SESSION")
    if not ops_cookie:
        raise RuntimeError(
            "OPS_SESSION cookie not received from /ui/index.action. "
            "Check credentials and that the account has UI access."
        )
    try:
        ops_data = _json.loads(base64.b64decode(ops_cookie))
    except Exception as e:
        raise RuntimeError(f"Failed to decode OPS_SESSION cookie: {e}") from e

    csrf_token = ops_data.get("csrfToken")
    if not csrf_token:
        raise RuntimeError(
            f"csrfToken not found in OPS_SESSION payload. "
            f"Keys present: {list(ops_data.keys())}"
        )

    return s, host, csrf_token


def _dashboard_action(session, host: str, csrf_token: Optional[str], main_action: str, extra_params: dict = None) -> dict:
    """POST to /ui/dashboard.action with a mainAction and optional params.

    CSRF is injected as a form field (secureToken=<csrf>) matching the
    /ui/ Struts pattern documented in knowledge/context/api-surface/pak_ui_upload_investigation.md.
    The response is expected to be JSON; a non-200 status raises RuntimeError.
    """
    form_data: dict = {"mainAction": main_action}
    if csrf_token:
        form_data["secureToken"] = csrf_token
    if extra_params:
        form_data.update(extra_params)
    r = session.post(
        f"https://{host}/ui/dashboard.action",
        data=form_data,
        headers={"Accept": "application/json"},
    )
    if r.status_code != 200:
        raise RuntimeError(
            f"dashboard.action mainAction={main_action} failed "
            f"({r.status_code}): {r.text[:500]}"
        )
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------------------------------------------------------
# SM UUID -> name resolution cache
# ---------------------------------------------------------------------------

class _SMNameCache:
    """Lazy-loaded cache of SM UUID -> name from the live instance."""

    def __init__(self, sm_client):
        self._client = sm_client
        self._uuid_to_name: dict[str, str] = {}
        self._name_to_uuid: dict[str, str] = {}
        self._loaded_all = False

    def _load_all(self) -> None:
        if self._loaded_all:
            return
        for sm in self._client.list_supermetrics(page_size=2000):
            uid = sm.get("id", "")
            name = sm.get("name", "")
            if uid and name:
                self._uuid_to_name[uid] = name
                self._name_to_uuid[name] = uid
        self._loaded_all = True

    def name_for_uuid(self, uuid: str) -> Optional[str]:
        if uuid in self._uuid_to_name:
            return self._uuid_to_name[uuid]
        # Try direct get
        try:
            sm = self._client.get_supermetric(uuid)
            name = sm.get("name", "")
            if name:
                self._uuid_to_name[uuid] = name
                self._name_to_uuid[name] = uuid
                return name
        except Exception:
            pass
        return None

    def uuid_for_name(self, name: str) -> Optional[str]:
        if name in self._name_to_uuid:
            return self._name_to_uuid[name]
        self._load_all()
        return self._name_to_uuid.get(name)


# ---------------------------------------------------------------------------
# Existing-id scan (non-overwrite invariant)
# ---------------------------------------------------------------------------

def _scan_existing_ids(kind: str, repo_root: Path) -> dict[str, Path]:
    """Return a mapping of uuid -> file path for existing repo YAML files.

    Scans the factory's first-party trees (``content/supermetrics``,
    ``content/views``, ``content/dashboards``) under ``repo_root`` for YAML
    files that already carry an `id:` field, so the extractor can skip
    instead of overwrite. The root is an explicit argument (M2 row 4): the
    factory passes its own ``_REPO_ROOT``. The ``content/`` segment is the
    v3 layout (lesson: knowledge/lessons/content-root-is-content-dir.md);
    the pre-row-4 join off the root matched nothing.
    """
    import re as _re
    uuid_re = _re.compile(
        r"^id:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s*$",
        _re.MULTILINE,
    )
    dir_map = {
        "supermetric": repo_root / "content" / "supermetrics",
        "view": repo_root / "content" / "views",
        "dashboard": repo_root / "content" / "dashboards",
    }
    result: dict[str, Path] = {}
    target_dir = dir_map.get(kind)
    if target_dir and target_dir.exists():
        for p in target_dir.rglob("*.y*ml"):
            text = p.read_text(errors="replace")
            for m in uuid_re.finditer(text):
                result[m.group(1).lower()] = p
    return result


def _run_content_export(sm_client, content_types: list[str]) -> bytes:
    """Trigger a content-zip export and return the outer zip bytes.

    Waits for any running export to finish before triggering a new one,
    then polls until the new export completes.  Returns the raw bytes of
    the outer zip (which may contain inner zips per content type).

    ``content_types`` must be valid API content type strings, e.g.:
      ["VIEW_DEFINITIONS"]
      ["DASHBOARDS"]
      ["VIEW_DEFINITIONS", "DASHBOARDS"]
    """
    import time
    from vcfcf_common.client import VCFOpsError

    # Wait for any running export to finish first
    deadline = time.monotonic() + 120
    while True:
        g = sm_client._request("GET", "/api/content/operations/export")
        if g.status_code == 200:
            st = (g.json() or {}).get("state", "")
            if st not in ("RUNNING", "INITIALIZED"):
                break
        if time.monotonic() > deadline:
            raise VCFOpsError("timed out waiting for prior export to finish")
        time.sleep(2)

    prior_start_time = 0
    g = sm_client._request("GET", "/api/content/operations/export")
    if g.status_code == 200:
        prior_start_time = (g.json() or {}).get("startTime") or 0

    r = sm_client._request(
        "POST",
        "/api/content/operations/export",
        json={"scope": "CUSTOM", "contentTypes": content_types},
    )
    if r.status_code not in (200, 202):
        raise VCFOpsError(f"export failed ({r.status_code}): {r.text}")

    # Poll for completion
    deadline = time.monotonic() + 180
    while True:
        g = sm_client._request("GET", "/api/content/operations/export")
        if g.status_code != 200:
            raise VCFOpsError(f"export status failed ({g.status_code})")
        body = g.json() or {}
        st = body.get("state", "")
        start_time = body.get("startTime") or 0
        if start_time > prior_start_time and st.startswith("FINI"):
            break
        if time.monotonic() > deadline:
            raise VCFOpsError(f"export timed out; state={st}")
        time.sleep(2)

    z = sm_client._session.get(f"{sm_client.base}/api/content/operations/export/zip")
    if z.status_code != 200:
        raise VCFOpsError(f"export zip download failed ({z.status_code})")
    return z.content


def _export_views_zip(sm_client, view_uuids: list[str]) -> bytes:
    """Export a VIEW_DEFINITIONS content zip from the live instance.

    Returns the raw bytes of the outer zip.  The inner content.xml is
    parsed by the caller.
    """
    return _run_content_export(sm_client, ["VIEW_DEFINITIONS"])


def _export_supermetrics_full(sm_client) -> dict[str, dict]:
    """Export all custom super metrics via content-zip and return a UUID->dict map.

    The content-zip SUPER_METRICS export carries the full wire shape for each
    SM including ``unitId``, ``resourceKinds``, and ``modifiedBy``: fields
    that the public REST ``GET /api/supermetrics/{id}`` endpoint strips.
    The parse is ``vcfcf_core.extractor.extractor._supermetrics_from_export_zip``
    (wire format documented there); this function only runs the export.

    Returns a mapping of uuid_lower -> full SM dict (with ``id`` injected).
    On error raises VCFOpsError.
    """
    from vcfcf_common.client import VCFOpsError

    outer_zip = _run_content_export(sm_client, ["SUPER_METRICS"])
    try:
        return _supermetrics_from_export_zip(outer_zip)
    except ValueError as e:
        raise VCFOpsError(str(e)) from e


def _export_dashboard_json(sm_client, dashboard_uuid: str) -> Optional[dict]:
    """Export all dashboards via content-zip and return the dict for dashboard_uuid.

    The walk over ``dashboards/<owner>`` inner zips and the ``entries`` merge
    is ``vcfcf_core.extractor.extractor._dashboards_from_export_zip`` (wire
    format documented there); this function runs the export and picks the
    target. The getDashboardConfig UI endpoint returns a completely different
    format (tabConfigs[], no widget config) and should not be used for parsing.

    Returns the matching dashboard dict (with top-level ``entries`` merged in),
    or None if the UUID is not found in the export.
    """
    from vcfcf_common.client import VCFOpsError

    outer_zip = _run_content_export(sm_client, ["DASHBOARDS"])
    try:
        dashboards = _dashboards_from_export_zip(outer_zip)
    except ValueError as e:
        raise VCFOpsError(str(e)) from e
    for dash in dashboards:
        if (dash.get("id") or "").lower() == dashboard_uuid.lower():
            return dash
    return None


# Matches a whole ${this, ...} formula entry (case-insensitive head).
_THIS_ENTRY_RE = re.compile(r"\$\{\s*this\b[^}]*\}", re.IGNORECASE | re.DOTALL)


def _sm_kinds_for_audit(
    sm_data: dict, suuid: str, formula: str, policy_assignments: Optional[dict]
) -> list[dict]:
    """Resolve the resource-kind assignment used to audit ``${this, metric=...}``
    refs in an extracted SM formula.

    Mirrors ``_write_sm_yaml``'s resolution order: Default Policy assignment
    (authoritative host scope), then the REST ``resourceKinds`` field, then the
    formula-parse fallback.  Returns snake_case
    ``{"adapter_kind_key", "resource_kind_key"}`` entries (the shape
    ``vcfcf_packaging.deps._refs_from_formula`` accepts), or ``[]`` when
    nothing resolves.
    """
    sm_id_lower = (sm_data.get("id") or suuid).lower()
    rks = (policy_assignments or {}).get(sm_id_lower)
    if rks:
        return list(rks)
    out: list[dict] = []
    for rk in (sm_data.get("resourceKinds") or []):
        if not isinstance(rk, dict):
            continue
        rk_key = (
            rk.get("resourceKindKey") or rk.get("resourceKind")
            or rk.get("resource_kind_key") or ""
        )
        ak_key = (
            rk.get("adapterKindKey") or rk.get("adapterKind")
            or rk.get("adapter_kind_key") or "VMWARE"
        )
        if rk_key:
            out.append({"resource_kind_key": rk_key, "adapter_kind_key": ak_key})
    if out:
        return out
    return _resource_kinds_from_formula(formula)


def _sm_formula_refs_for_audit(formula: str, sm_name: str, resource_kinds: list):
    """Extract built-in metric refs from an extracted SM formula, never raising.

    ``deps._refs_from_formula`` hard-fails (AuditError) on a ``${this,
    metric=...}`` ref with no usable resource_kinds, which is right for the
    packaging audit but must not abort a whole live-lab extraction over one
    SM's assignment metadata (PR #137 Codex P1).  Extractor convention is a
    loud per-SM WARN and carry on: warn, strip only the unauditable
    ``${this, ...}`` entries, and still return every explicit
    ``${adaptertype=..., objecttype=...}`` reference from the same formula.
    The written YAML's empty/incorrect resource_kinds is separately WARNed by
    ``_write_sm_yaml`` and rejected by the validator, so the gap is surfaced
    twice, never silently dropped.
    """
    from vcfcf_packaging.audit import AuditError
    from vcfcf_packaging.deps import _refs_from_formula

    try:
        return _refs_from_formula(formula or "", sm_name, resource_kinds)
    except AuditError as exc:
        print(
            f"  WARN: super metric {sm_name!r}: a ${{this, metric=...}} reference "
            f"cannot be audited: {exc}\n"
            "  The extraction continues; correct resource_kinds: in the written "
            "YAML before packaging (the packaging-time audit will then check "
            "this reference).",
            file=sys.stderr,
        )
        return _refs_from_formula(
            _THIS_ENTRY_RE.sub("0", formula or ""), sm_name, resource_kinds
        )


# ---------------------------------------------------------------------------
# Public API: list_dashboards
# ---------------------------------------------------------------------------

def list_dashboards(
    *,
    host: str,
    user: str,
    password: str,
    verify_ssl: bool,
    folder_filter: str = "",
) -> int:
    """List dashboards on the live instance. Returns exit code."""
    print(f"Connecting to https://{host} ...")
    try:
        session, host, csrf_token = _build_ui_client(host, user, password, verify_ssl)
    except Exception as e:
        print(f"ERROR: could not connect: {e}", file=sys.stderr)
        return 1

    try:
        body = _dashboard_action(session, host, csrf_token, "getDashboardList")
    except Exception as e:
        print(f"ERROR: getDashboardList failed: {e}", file=sys.stderr)
        return 1

    dashboards = body.get("dashboards") or body.get("result") or []
    if not dashboards:
        # Some versions return the list at the top level
        if isinstance(body, list):
            dashboards = body

    if not dashboards:
        print("No dashboards found (or unexpected response shape).")
        print(f"Raw response keys: {list(body.keys()) if isinstance(body, dict) else type(body)}")
        return 0

    filtered = []
    for d in dashboards:
        name = d.get("name") or d.get("title") or ""
        uid = d.get("id") or d.get("uuid") or ""
        if folder_filter and folder_filter.lower() not in name.lower():
            continue
        filtered.append((uid, name))

    if not filtered:
        print(f"No dashboards matching filter '{folder_filter}'.")
        return 0

    print(f"\n{'UUID':<38}  Name")
    print("-" * 80)
    for uid, name in sorted(filtered, key=lambda x: x[1].lower()):
        print(f"{uid:<38}  {name}")
    print(f"\nTotal: {len(filtered)} dashboard(s)")
    return 0


# ---------------------------------------------------------------------------
# Public API: extract_dashboard
# ---------------------------------------------------------------------------

def extract_dashboard(
    *,
    host: str,
    user: str,
    password: str,
    verify_ssl: bool,
    dashboard_id: Optional[str],
    dashboard_name: Optional[str],
    bundle_slug: str,
    author: str,
    license_: str,
    description_file: Path,
    source_url: str,
    source_version: str,
    output_dir: str,
    skip_supermetrics: set[str],
    include_customgroups: list[str],
    prefix: str = "",
    dry_run: bool = False,
    yes: bool = False,
) -> int:
    """Walk a dashboard's dependency graph and emit YAML + manifest.

    Returns exit code (0 = success, non-zero = failure).
    """
    from vcfcf_packaging.describe import DescribeCache
    output_path = Path(output_dir)
    slug_dir = output_path / bundle_slug

    print(f"\nConnecting to https://{host} ...")

    # Build clients
    try:
        sm_client = _build_sm_client(host, user, password, verify_ssl)
        sm_client.authenticate()
    except Exception as e:
        print(f"ERROR: could not authenticate to suite-api: {e}", file=sys.stderr)
        return 1

    # UI session is only needed for name-based resolution (--dashboard-name).
    # If --dashboard-id is provided we skip the UI login entirely.
    ui_session = None
    csrf_token = None
    if not dashboard_id:
        try:
            ui_session, _, csrf_token = _build_ui_client(host, user, password, verify_ssl)
        except Exception as e:
            print(f"ERROR: could not authenticate to UI: {e}", file=sys.stderr)
            return 1

    # Resolve dashboard UUID if only name was given
    if not dashboard_id:
        print(f"Resolving dashboard name '{dashboard_name}' ...")
        try:
            body = _dashboard_action(ui_session, host, csrf_token, "getDashboardList")
        except Exception as e:
            print(f"ERROR: getDashboardList failed: {e}", file=sys.stderr)
            return 1

        dashboards = body.get("dashboards") or body.get("result") or []
        if isinstance(body, list):
            dashboards = body

        matches = [
            d for d in dashboards
            if (d.get("name") or d.get("title") or "").lower().strip()
            == dashboard_name.lower().strip()
        ]
        if not matches:
            # Try substring match as fallback
            matches = [
                d for d in dashboards
                if dashboard_name.lower() in (d.get("name") or d.get("title") or "").lower()
            ]
        if not matches:
            print(
                f"ERROR: no dashboard found matching name '{dashboard_name}'.",
                file=sys.stderr,
            )
            print(
                "  Run 'python -m vcfcf_extractor list-dashboards' to see available dashboards.",
                file=sys.stderr,
            )
            return 1
        if len(matches) > 1:
            print(
                f"ERROR: multiple dashboards match '{dashboard_name}':",
                file=sys.stderr,
            )
            for d in matches:
                print(f"  {d.get('id')}  {d.get('name')}", file=sys.stderr)
            print("  Use --dashboard-id to specify exactly.", file=sys.stderr)
            return 1
        dashboard_id = matches[0].get("id") or matches[0].get("uuid") or ""
        if not dashboard_id:
            print("ERROR: matched dashboard has no id field.", file=sys.stderr)
            return 1
        print(f"  Resolved to UUID: {dashboard_id}")

    # Fetch dashboard config via content-zip export.
    #
    # The /ui/dashboard.action getDashboardConfig endpoint returns a compact
    # "tabConfigs[]" format that does NOT include widget config (viewDefinitionId,
    # metric specs, etc.): only widget shells (id, title, key, gridster coords).
    # The authoritative source with full config is the content-zip export
    # (dashboard/dashboard.json).  We use _export_dashboard_json() to export and
    # locate our target dashboard.
    print(f"\nExporting dashboard {dashboard_id} via content-zip ...")
    try:
        dash_data = _export_dashboard_json(sm_client, dashboard_id)
    except Exception as e:
        print(f"ERROR: dashboard export failed: {e}", file=sys.stderr)
        return 1

    if dash_data is None:
        print(
            f"ERROR: dashboard UUID {dashboard_id} not found in content-zip export.",
            file=sys.stderr,
        )
        print(
            "  Possible causes: the dashboard was deleted, or it is a system-owned\n"
            "  dashboard that the API excludes from export.\n"
            "  Verify the UUID with: python -m vcfcf_extractor list-dashboards",
            file=sys.stderr,
        )
        return 1

    # Debug capture: always write the resolved dash_data to debug/ for inspection.
    import json as _json_debug
    debug_dir = Path(output_dir) / bundle_slug / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_path = debug_dir / f"dashboard_{dashboard_id}_from_export.json"
    debug_path.write_text(_json_debug.dumps(dash_data, indent=2), encoding="utf-8")
    print(f"  [debug] dashboard dict from content-zip -> {debug_path}")

    dash_name_raw = dash_data.get("name") or dashboard_name or dashboard_id
    # Strip folder prefix for display
    if "/" in dash_name_raw:
        display_name = dash_name_raw.split("/", 1)[-1].strip()
    else:
        display_name = dash_name_raw.strip()

    print(f"  Dashboard: '{display_name}'  id={dashboard_id}")

    # Collect view UUIDs and direct SM UUIDs referenced by widgets.
    # View widgets reference views by viewDefinitionId.
    # Scoreboard/MetricChart/Heatmap widgets reference SMs directly via metricKey
    # values like "Super Metric|sm_<uuid>" anywhere in the widget config JSON.
    # These bypass the view-column walk and must be collected here.
    import json as _json
    _SM_METRIC_KEY_RE = re.compile(
        r"Super Metric\|sm_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        re.IGNORECASE,
    )
    widgets = dash_data.get("widgets") or []
    view_uuids: list[str] = []
    direct_sm_uuids: set[str] = set()
    for w in widgets:
        cfg = w.get("config") or {}
        view_id = cfg.get("viewDefinitionId")
        if view_id and view_id not in view_uuids:
            view_uuids.append(view_id)
        # Scan the entire widget config JSON string for SM metric key references.
        # The path varies by widget type (Scoreboard uses config.metric.resourceKindMetrics,
        # Heatmap uses config.configs, etc.): string scan is the simplest invariant.
        cfg_str = _json.dumps(cfg)
        for m in _SM_METRIC_KEY_RE.finditer(cfg_str):
            direct_sm_uuids.add(m.group(1).lower())

    print(f"  Found {len(widgets)} widget(s), {len(view_uuids)} view reference(s), {len(direct_sm_uuids)} direct SM reference(s)")

    # Warn about custom groups (Phase 1 gap)
    if include_customgroups:
        _warn(
            f"--include-customgroup flags are set ({', '.join(include_customgroups)}) "
            "but custom group extraction is not yet implemented in Phase 1."
        )
    _warn(
        "no custom groups discovered -- verify manually on source dashboard "
        "(custom group extraction is a Phase 2 feature)"
    )

    # Build SM name cache
    sm_name_cache = _SMNameCache(sm_client)

    # Scan existing IDs to enforce non-overwrite invariant
    existing_sm_ids = _scan_existing_ids("supermetric", _REPO_ROOT)
    existing_view_ids = _scan_existing_ids("view", _REPO_ROOT)
    existing_dash_ids = _scan_existing_ids("dashboard", _REPO_ROOT)

    # -----------------------------------------------------------------------
    # BFS dependency walk
    # -----------------------------------------------------------------------
    # Queue items: (kind, uuid, parent_description)
    queue: deque = deque()
    seen: set[tuple[str, str]] = set()

    # Seed with the dashboard itself
    seen.add(("dashboard", dashboard_id.lower()))

    # Seed with views
    for vuuid in view_uuids:
        key = ("view", vuuid.lower())
        if key not in seen:
            seen.add(key)
            queue.append(("view", vuuid, f"dashboard '{display_name}'"))

    # Results
    sm_results: dict[str, dict] = {}       # uuid -> sm_data (raw)
    sm_formulas: dict[str, str] = {}       # uuid -> rewritten formula
    view_results: dict[str, dict] = {}     # uuid -> parsed view dict
    skipped_sms: list[tuple[str, str]] = []  # (uuid, reason)
    skipped_views: list[tuple[str, str]] = []

    # We need to export views before we can parse them.
    # Collect all view UUIDs first, then do a single export.
    pending_view_uuids: list[str] = list(view_uuids)
    pending_sm_uuids: list[str] = []

    # Identify SM UUIDs from view columns (pre-scan before export)
    # We'll collect these during view XML parsing; for now just track views.

    # Phase 1 BFS: process views -> extract SM refs from formulas
    # Since we can't parse view XML without the export, we do:
    #   1. Export all views
    #   2. Parse each view -> collect SM UUIDs from columns
    #   3. Fetch each SM -> rewrite formula -> collect transitive SM UUIDs
    #   4. Repeat step 3 until no new SMs

    print(f"\nExporting {len(pending_view_uuids)} view definition(s) ...")

    view_xml_bytes = None
    if pending_view_uuids:
        try:
            view_xml_bytes = _export_views_zip(sm_client, pending_view_uuids)
            print(f"  Export complete ({len(view_xml_bytes):,} bytes)")
        except Exception as e:
            print(f"ERROR: view export failed: {e}", file=sys.stderr)
            return 1

    # Parse view XMLs
    sm_uuids_from_views: set[str] = set()

    for vuuid in pending_view_uuids:
        vuuid_lower = vuuid.lower()
        if vuuid_lower in existing_view_ids:
            existing_path = existing_view_ids[vuuid_lower]
            _warn(f"view {vuuid} already exists at {existing_path}; skipping")
            skipped_views.append((vuuid, str(existing_path)))
            continue

        view_data = None
        if view_xml_bytes:
            view_data = _parse_view_xml(view_xml_bytes, vuuid)

        if view_data is None:
            _warn(f"view {vuuid} not found in export XML; skipping")
            skipped_views.append((vuuid, "not found in export"))
            continue

        view_results[vuuid_lower] = view_data

        # Collect SM UUIDs from view columns
        for col in view_data.get("columns", []):
            attr = col.get("attribute", "")
            m = re.match(r"sm_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", attr)
            if m:
                sm_uuids_from_views.add(m.group(1))

    # Fetch Default Policy XML once (cached across all SM writes).
    # This is the authoritative source for resource_kinds: it tells us which
    # (adapter, kind) scopes each SM is actually enabled on in the policy,
    # which is the host type the SM evaluates against.  The SM REST API's
    # resourceKinds field encodes the formula INPUT type, which can differ.
    print("\nFetching Default Policy export for SM scope resolution ...")
    _policy_sm_assignments: dict = {}
    try:
        from vcfcf_supermetrics.client import VCFOpsClient as _VCFOpsClient
        _policy_xml = sm_client.export_default_policy_xml()
        _policy_sm_assignments = _VCFOpsClient.get_sm_policy_assignments(_policy_xml)
        print(
            f"  Policy parsed: {len(_policy_sm_assignments)} SM(s) have enabled scopes."
        )
    except Exception as _e:
        _warn(
            f"could not fetch Default Policy XML: {_e}; "
            "falling back to SM API resourceKinds field (may be wrong scope)"
        )

    # Export all custom super metrics via content-zip once (authoritative: carries unitId,
    # resourceKinds, modifiedBy: fields stripped by GET /api/supermetrics/{id}).
    print("\nExporting super metrics via content-zip ...")
    _sm_export_cache: dict[str, dict] = {}
    try:
        _sm_export_cache = _export_supermetrics_full(sm_client)
        print(f"  SM export complete ({len(_sm_export_cache)} super metric(s) in export)")
    except Exception as _sm_export_err:
        _warn(
            f"could not export super metrics via content-zip ({_sm_export_err}); "
            "falling back to GET /api/supermetrics/{id} (unitId will be missing)"
        )

    # BFS over super metrics (with transitive SM->SM via formula rewriting).
    # Seeds: SMs from view columns + SMs directly referenced in widget metric configs.
    sm_queue: deque[tuple[str, str]] = deque()
    sm_seen: set[str] = set()

    for suuid in sm_uuids_from_views:
        if suuid not in sm_seen:
            sm_seen.add(suuid)
            sm_queue.append((suuid, "view column"))

    for suuid in direct_sm_uuids:
        if suuid not in sm_seen:
            sm_seen.add(suuid)
            sm_queue.append((suuid, "dashboard widget metric config"))

    while sm_queue:
        suuid, parent_desc = sm_queue.popleft()
        suuid_lower = suuid.lower()

        # Check existing
        if suuid_lower in existing_sm_ids:
            existing_path = existing_sm_ids[suuid_lower]
            _warn(f"super metric {suuid} already exists at {existing_path}; skipping")
            skipped_sms.append((suuid, str(existing_path)))
            continue

        # Check skip list
        sm_name = sm_name_cache.name_for_uuid(suuid)
        if sm_name and sm_name in skip_supermetrics:
            _warn(f"super metric '{sm_name}' ({suuid}) is in --skip-supermetric list; skipping")
            skipped_sms.append((suuid, "skipped by flag"))
            continue

        # Look up SM from the content-zip export cache (carries unitId).
        # Fall back to the public REST endpoint if the SM was missing from
        # the export (e.g. system-owned SMs that the export omits).
        sm_data = _sm_export_cache.get(suuid_lower)
        if sm_data is None:
            try:
                sm_data = sm_client.get_supermetric(suuid)
                _warn(
                    f"super metric {suuid} not in content-zip export; "
                    "fell back to GET /api/supermetrics/{id} (unitId may be absent)"
                )
            except Exception as e:
                print(
                    f"ERROR: could not fetch super metric {suuid} (referenced by {parent_desc}): {e}",
                    file=sys.stderr,
                )
                return 1

        sm_id = sm_data.get("id", suuid)
        sm_data["id"] = sm_id

        # Rewrite formula (UUID -> @supermetric:"name")
        raw_formula = sm_data.get("formula", "") or ""
        rewritten, referenced_uuids = _rewrite_formula(raw_formula, sm_name_cache)
        sm_formulas[sm_id] = rewritten

        sm_name_resolved = sm_data.get("name", suuid)
        sm_results[suuid_lower] = sm_data

        # Enqueue transitive SM dependencies
        for ref_uuid in referenced_uuids:
            if ref_uuid not in sm_seen:
                sm_seen.add(ref_uuid)
                sm_queue.append((ref_uuid, f"SM '{sm_name_resolved}'"))

    # -----------------------------------------------------------------------
    # Prefix application (if --prefix was supplied)
    # -----------------------------------------------------------------------
    # Apply the prefix to every SM name, view name, and dashboard display name.
    # Rewrite cross-references so they still resolve after renaming:
    #   SM formulas:  @supermetric:"<old>"  ->  @supermetric:"<new>"
    #   Dashboard widget view: references are rewritten via view_results name map.
    # UUIDs (id: fields) and filenames on disk are left unchanged.
    if prefix:
        _info(f"Applying prefix '{prefix}' to all extracted content names ...")

        # Build old->new name maps before mutating anything
        sm_name_map: dict[str, str] = {}  # old SM name -> new SM name
        for suuid, sm_data in sm_results.items():
            old_name = sm_data.get("name", "")
            if old_name:
                sm_name_map[old_name] = prefix + old_name

        view_name_map: dict[str, str] = {}  # old view name -> new view name
        for vuuid, view_data in view_results.items():
            old_name = view_data.get("name", "")
            if old_name:
                view_name_map[old_name] = prefix + old_name

        # Apply to SM names in sm_results
        for suuid, sm_data in sm_results.items():
            old_name = sm_data.get("name", "")
            if old_name and old_name in sm_name_map:
                sm_data["name"] = sm_name_map[old_name]

        # Rewrite SM formulas: @supermetric:"<old>" -> @supermetric:"<new>"
        if sm_name_map:
            _sm_ref_rewrite_re = re.compile(r'@supermetric:"([^"]+)"')

            def _rewrite_sm_refs(formula: str) -> str:
                def _sub(m: re.Match) -> str:
                    old = m.group(1)
                    return f'@supermetric:"{sm_name_map.get(old, old)}"'
                return _sm_ref_rewrite_re.sub(_sub, formula)

            sm_formulas = {k: _rewrite_sm_refs(v) for k, v in sm_formulas.items()}

        # Apply to view names in view_results
        for vuuid, view_data in view_results.items():
            old_name = view_data.get("name", "")
            if old_name and old_name in view_name_map:
                view_data["name"] = view_name_map[old_name]

        # Apply to dashboard display name
        display_name = prefix + display_name

        _info(
            f"  Renamed {len(sm_name_map)} SM(s), {len(view_name_map)} view(s), "
            "1 dashboard."
        )
        if view_name_map:
            _info(
                "  Dashboard widget view: references will be written using prefixed names "
                "(resolved at write time via view_results)."
            )

    # -----------------------------------------------------------------------
    # Dry-run report
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("EXTRACTION PLAN")
    print(f"{'=' * 60}")
    print(f"Dashboard:      {display_name}  ({dashboard_id})")
    print(f"Bundle slug:    {bundle_slug}")
    print(f"Author:         {author}")
    print(f"License:        {license_}")
    print(f"Output dir:     {output_path / bundle_slug}")
    print()

    print(f"Views to extract ({len(view_results)}):")
    for vuuid, vdata in view_results.items():
        print(f"  + {vdata.get('name', vuuid)}  ({vuuid})")
    for vuuid, reason in skipped_views:
        print(f"  - SKIP {vuuid}: {reason}")
    print()

    print(f"Super metrics to extract ({len(sm_results)}):")
    for suuid, smdata in sm_results.items():
        sm_id_lower = (smdata.get("id") or suuid).lower()
        rks = _policy_sm_assignments.get(sm_id_lower)
        if rks:
            scope_str = ", ".join(
                f"{r['adapter_kind_key']}:{r['resource_kind_key']}" for r in rks
            )
        else:
            scope_str = "NOT IN DEFAULT POLICY: resource_kinds will be empty"
        print(f"  + {smdata.get('name', suuid)}  ({smdata.get('id', suuid)})  scope={scope_str}")
    for suuid, reason in skipped_sms:
        print(f"  - SKIP {suuid}: {reason}")
    print()

    print(f"Dashboard YAML (widget graph extracted from getDashboardConfig):")
    print(f"  + {display_name}  ({dashboard_id})")
    print()

    if dry_run:
        print("DRY RUN -- no files written.")
        return 0

    # -----------------------------------------------------------------------
    # Confirmation (no interactive prompts -- require --yes flag)
    # -----------------------------------------------------------------------
    if not yes:
        total_files = len(sm_results) + len(view_results) + 1  # +1 for dashboard
        print(
            f"\nWould write {total_files} YAML file(s) under {slug_dir}"
        )
        print(f"and a manifest at {slug_dir / 'PROJECT.yaml'}.")
        print()
        print("Re-run with --yes to proceed, or --dry-run to preview without writing.")
        return 0

    # -----------------------------------------------------------------------
    # Write YAML files
    # -----------------------------------------------------------------------
    sm_file_paths: list[str] = []
    view_file_paths: list[str] = []
    dash_file_paths: list[str] = []

    # Super metrics: orphan check before writing
    # An orphan SM is one whose formula references metric keys that are absent
    # from the describe cache entirely (not merely defaultMonitored=false).
    # "Ships broken" is a build error: refuse to write the file and surface
    # the unresolved keys on stdout.  This mirrors a packaging dependency
    # audit principle (original citation, context/feedback_packaging_dependency_audit.md,
    # no longer exists in the corpus and no direct successor was found during
    # the reorg-v2 phase 2 citation sweep: the principle itself is preserved
    # here verbatim).
    sm_subdir = slug_dir / "supermetrics"
    orphan_check_cache = DescribeCache()
    orphaned_sms: list[str] = []

    for suuid, sm_data in sm_results.items():
        sm_name_display = sm_data.get("name", suuid)
        formula = sm_formulas.get(sm_data.get("id", suuid), sm_data.get("formula", ""))

        # Collect built-in metric refs from the (rewritten) formula.
        # ${this, metric=...} refs resolve against the SM's own assignment
        # (policy scope preferred), same shape the packaging audit checks.
        from vcfcf_packaging.deps import _is_sm_ref
        _audit_kinds = _sm_kinds_for_audit(sm_data, suuid, formula, _policy_sm_assignments)
        formula_refs = [
            r for r in _sm_formula_refs_for_audit(formula, sm_name_display, _audit_kinds)
            if not _is_sm_ref(r.metric_key)
        ]

        unresolved: list[str] = []
        for ref in formula_refs:
            try:
                info = orphan_check_cache.resolve_metric(ref.adapter_kind, ref.resource_kind, ref.metric_key)
            except Exception:
                info = None  # cache miss or offline; skip orphan check for this key
            if info is None:
                # Could be a cache miss (stale cache) or a genuinely missing metric.
                # Only flag as orphan if the cache has entries for this adapter/kind
                # (i.e., the cache file exists): avoids false-positives on cold caches.
                try:
                    has_cache = orphan_check_cache.has_cache_file(ref.adapter_kind, ref.resource_kind)
                except Exception:
                    has_cache = False
                if has_cache:
                    unresolved.append(f"{ref.adapter_kind}/{ref.resource_kind}  {ref.metric_key}")

        if unresolved:
            print(
                f"  ORPHAN: super metric '{sm_name_display}' references metric keys not in "
                "describe cache: skipping write.",
                file=sys.stderr,
            )
            for key_str in unresolved:
                print(f"    unresolved: {key_str}", file=sys.stderr)
            print(
                "  Possible cause: source metric was removed from the live instance after "
                "the SM was authored. Remove the SM from the source dashboard or update "
                "the describe cache (python3 -m vcfcf_packaging refresh-describe) "
                "and re-extract.",
                file=sys.stderr,
            )
            orphaned_sms.append(sm_name_display)
            continue

        sm_name_safe = _safe_filename(sm_name_display)
        filename = f"{sm_name_safe}.yaml"
        path = sm_subdir / filename
        sm_id_lower = (sm_data.get("id") or suuid).lower()
        policy_rks = _policy_sm_assignments.get(sm_id_lower)  # None if policy fetch failed
        _write_sm_yaml(
            path,
            sm_data,
            formula,
            policy_resource_kinds=policy_rks,
        )
        rel = f"supermetrics/{filename}"
        sm_file_paths.append(rel)
        _info(f"wrote {path}")

    if orphaned_sms:
        print(
            f"\n  WARN: {len(orphaned_sms)} orphan super metric(s) were skipped: "
            + ", ".join(f"'{n}'" for n in orphaned_sms),
            file=sys.stderr,
        )

    # Views
    view_subdir = slug_dir / "views"
    for vuuid, view_data in view_results.items():
        vname_safe = _safe_filename(view_data.get("name", vuuid))
        filename = f"{vname_safe}.yaml"
        path = view_subdir / filename
        _write_view_yaml(path, view_data)
        rel = f"views/{filename}"
        view_file_paths.append(rel)
        _info(f"wrote {path}")

    # Dashboard
    dash_subdir = slug_dir / "dashboards"
    dash_name_safe = _safe_filename(display_name)
    dash_filename = f"{dash_name_safe}.yaml"
    dash_path = dash_subdir / dash_filename
    dash_data["id"] = dashboard_id
    _write_dashboard_yaml(dash_path, dash_data, dashboard_id, view_results, factory_native=False)
    dash_file_paths.append(f"dashboards/{dash_filename}")
    _info(f"wrote {dash_path}")

    # -----------------------------------------------------------------------
    # Enablement walk: collect all metric refs and check defaultMonitored
    # -----------------------------------------------------------------------
    # Import deps helpers inline to avoid circular-import at module level.
    from vcfcf_packaging.deps import (
        MetricReference,
        _normalize_metric_key,
        _is_sm_ref,
    )

    all_metric_refs: dict[tuple[str, str, str], MetricReference] = {}

    def _add_ref(ref: MetricReference) -> None:
        k = (ref.adapter_kind, ref.resource_kind, ref.metric_key)
        if k not in all_metric_refs:
            all_metric_refs[k] = ref

    # Super metric formula refs
    for suuid, sm_data in sm_results.items():
        formula = sm_formulas.get(sm_data.get("id", suuid), sm_data.get("formula", ""))
        sm_name = sm_data.get("name", suuid)
        _audit_kinds = _sm_kinds_for_audit(sm_data, suuid, formula, _policy_sm_assignments)
        for ref in _sm_formula_refs_for_audit(formula, sm_name, _audit_kinds):
            _add_ref(ref)

    # View column refs (raw dict form: mirrors deps._refs_from_view logic)
    for vuuid, view_data in view_results.items():
        view_name = view_data.get("name", vuuid)
        kinds = [
            (sub.get("adapter_kind", ""), sub.get("resource_kind", ""))
            for sub in (view_data.get("subjects") or [])
        ] or [(view_data.get("adapter_kind", ""), view_data.get("resource_kind", ""))]
        for col in view_data.get("columns", []):
            attr = (col.get("attribute") or "").strip()
            if not attr or _is_sm_ref(attr):
                continue
            attr = _normalize_metric_key(attr)
            # A column bound to one kind (`subject:`) only resolves against
            # that kind on the product; audit it there only, same rule as
            # deps._refs_from_view. Unbound columns fan out to every kind.
            sub = col.get("subject") or {}
            col_kinds = (
                [(sub.get("adapter_kind", ""), sub.get("resource_kind", ""))]
                if sub else kinds
            )
            for ak, rk in col_kinds:
                if not (ak and rk):
                    continue
                _add_ref(MetricReference(
                    adapter_kind=ak,
                    resource_kind=rk,
                    metric_key=attr,
                    source_desc=f"view {view_name!r}",
                ))

    # Dashboard widget refs via parse_dashboard_json
    try:
        from vcfcf_dashboards.reverse import parse_dashboard_json
        from vcfcf_dashboards.loader import ViewDef as _ViewDef
        _views_by_id: dict = {}
        for vuuid, vdata in view_results.items():
            vid = vdata.get("id") or vuuid
            vname = vdata.get("name") or vuuid
            _views_by_id[vid.lower()] = _ViewDef(
                id=vid, name=vname, description="",
                adapter_kind=vdata.get("adapter_kind", ""),
                resource_kind=vdata.get("resource_kind", ""),
                columns=[],
            )
        _dash_copy = dict(dash_data)
        _dash_copy["id"] = dashboard_id
        _parsed_dash = parse_dashboard_json(_dash_copy, _views_by_id)
        if _parsed_dash:
            for w in _parsed_dash.widgets:
                wsrc = f"dashboard {display_name!r} widget {w.local_id!r} ({w.type})"
                wt = w.type
                if wt == "Scoreboard" and w.scoreboard_config is not None:
                    for ms in w.scoreboard_config.metrics:
                        if ms.metric_key and not _is_sm_ref(ms.metric_key):
                            _add_ref(MetricReference(
                                adapter_kind=ms.adapter_kind,
                                resource_kind=ms.resource_kind,
                                metric_key=_normalize_metric_key(ms.metric_key),
                                source_desc=wsrc,
                            ))
                elif wt == "MetricChart" and w.metric_chart_config is not None:
                    for ms in w.metric_chart_config.metrics:
                        if ms.metric_key and not _is_sm_ref(ms.metric_key):
                            _add_ref(MetricReference(
                                adapter_kind=ms.adapter_kind,
                                resource_kind=ms.resource_kind,
                                metric_key=_normalize_metric_key(ms.metric_key),
                                source_desc=wsrc,
                            ))
                elif wt == "HealthChart" and w.health_chart_config is not None:
                    hc = w.health_chart_config
                    if hc.metric_key and not _is_sm_ref(hc.metric_key):
                        _add_ref(MetricReference(
                            adapter_kind=hc.adapter_kind,
                            resource_kind=hc.resource_kind,
                            metric_key=_normalize_metric_key(hc.metric_key),
                            source_desc=wsrc,
                        ))
                elif wt == "ParetoAnalysis" and w.pareto_analysis_config is not None:
                    pa = w.pareto_analysis_config
                    if pa.metric_key and not _is_sm_ref(pa.metric_key):
                        _add_ref(MetricReference(
                            adapter_kind=pa.adapter_kind,
                            resource_kind=pa.resource_kind,
                            metric_key=_normalize_metric_key(pa.metric_key),
                            source_desc=wsrc,
                        ))
                elif wt == "Heatmap" and w.heatmap_config is not None:
                    for tab in w.heatmap_config.tabs:
                        if tab.color_by_key and not _is_sm_ref(tab.color_by_key):
                            _add_ref(MetricReference(
                                adapter_kind=tab.adapter_kind,
                                resource_kind=tab.resource_kind,
                                metric_key=_normalize_metric_key(tab.color_by_key),
                                source_desc=f"{wsrc} tab {tab.name!r} colorBy",
                            ))
                        if tab.size_by_key and not _is_sm_ref(tab.size_by_key):
                            _add_ref(MetricReference(
                                adapter_kind=tab.adapter_kind,
                                resource_kind=tab.resource_kind,
                                metric_key=_normalize_metric_key(tab.size_by_key),
                                source_desc=f"{wsrc} tab {tab.name!r} sizeBy",
                            ))
    except Exception as e:
        _warn(f"dashboard widget metric-ref walk failed ({e}); widget refs omitted from enablement walk")

    # Resolve against offline describe cache (no live call: user refreshes describe separately)
    offline_cache = DescribeCache()
    bme_list = _collect_enablement_entries(list(all_metric_refs.values()), offline_cache)
    if not bme_list:
        _info("enablement walk: all referenced metrics are defaultMonitored=true (or cache miss); no builtin_metric_enables entries needed")

    # Bundle manifest (v3 layout: PROJECT.yaml lives inside the slug dir)
    manifest_path = slug_dir / "PROJECT.yaml"
    _write_manifest(
        manifest_path=manifest_path,
        slug=bundle_slug,
        bundle_name=display_name,
        author=author,
        license_=license_,
        source_url=source_url,
        source_version=source_version,
        description_file=description_file,
        builtin_metric_enables=bme_list if bme_list else None,
    )
    _info(f"wrote manifest: {manifest_path}")

    print(f"\nOK: extraction complete.")
    print(f"  Bundle slug:    {bundle_slug}")
    print(f"  Output:         {slug_dir}")
    print(f"  Manifest:       {manifest_path}")
    print()
    print("Next steps:")
    print(f"  1. Review YAML files under {slug_dir}")
    print(f"  2. Validate:  python3 -m vcfcf_supermetrics validate && python3 -m vcfcf_dashboards validate")
    print(f"  3. Build:     python3 -m vcfcf_packaging build {manifest_path}")
    return 0


def __getattr__(name: str):
    """Every name this module does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
