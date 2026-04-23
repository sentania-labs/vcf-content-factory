"""Dependency walker and YAML writer for vcfops_extractor.

Given a dashboard UUID (or name), walks the full dependency graph using BFS:

  dashboard  ->  views  ->  super metrics  ->  (transitive SM references)

Emits factory-shape YAML under bundles/third_party/<slug>/ and a bundle
manifest at bundles/third_party/<slug>.yaml.

Design decisions:
- BFS keyed on (kind, uuid) to prevent cycles and repeated work.
- Seen-set prevents duplicate writes for diamonds (SM referenced by
  multiple views).
- Non-overwrite invariant: if a resolved UUID matches an existing id:
  in the factory repo's supermetrics/ or views/ directories, the file
  is SKIPPED with a WARN, not overwritten.
- Missing deps (404 on a referenced UUID) abort the walk with a clear
  error naming the parent.
- Custom groups: Phase 1 emits WARN only; no extraction attempted.
- Network clients are reused (single auth session per client type).
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

# Repo root: two levels above bundles/third_party/<slug>
_REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _warn(msg: str) -> None:
    print(f"  WARN: {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"  {msg}")


def _build_sm_client(host: str, user: str, password: str, verify_ssl: bool):
    """Build an authenticated VCFOpsClient (suite-api) for super metric calls."""
    from vcfops_supermetrics.client import VCFOpsClient
    return VCFOpsClient(
        host=host, username=user, password=password, verify_ssl=verify_ssl
    )


def _build_ui_client(host: str, user: str, password: str, verify_ssl: bool):
    """Build an authenticated /ui/ Struts session for dashboard calls.

    Uses the three-step /ui/ login pattern documented in
    context/pak_ui_upload_investigation.md and implemented in
    vcfops_managementpacks/installer.py _UISession.login():

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
    /ui/ Struts pattern documented in context/pak_ui_upload_investigation.md.
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

def _scan_existing_ids(kind: str) -> dict[str, Path]:
    """Return a mapping of uuid -> file path for existing repo YAML files.

    Scans the factory repo's canonical directories (supermetrics/, views/,
    dashboards/) for YAML files that already carry an `id:` field, so the
    extractor can skip instead of overwrite.
    """
    import re as _re
    uuid_re = _re.compile(
        r"^id:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s*$",
        _re.MULTILINE,
    )
    dir_map = {
        "supermetric": _REPO_ROOT / "supermetrics",
        "view": _REPO_ROOT / "views",
        "dashboard": _REPO_ROOT / "dashboards",
    }
    result: dict[str, Path] = {}
    target_dir = dir_map.get(kind)
    if target_dir and target_dir.exists():
        for p in target_dir.rglob("*.y*ml"):
            text = p.read_text(errors="replace")
            for m in uuid_re.finditer(text):
                result[m.group(1).lower()] = p
    return result


# ---------------------------------------------------------------------------
# Formula UUID -> name rewriting
# ---------------------------------------------------------------------------

_SM_UUID_TOKEN_RE = re.compile(r"sm_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")


def _rewrite_formula(formula: str, name_cache: _SMNameCache) -> tuple[str, set[str]]:
    """Rewrite sm_<uuid> tokens in a formula to @supermetric:"<name>".

    Returns (rewritten_formula, set_of_referenced_uuids).
    """
    referenced_uuids: set[str] = set()
    result = formula

    def _replace(m: re.Match) -> str:
        uuid = m.group(1)
        referenced_uuids.add(uuid)
        name = name_cache.name_for_uuid(uuid)
        if name:
            return f'@supermetric:"{name}"'
        _warn(f"could not resolve SM UUID {uuid} to a name; keeping raw token")
        return m.group(0)

    result = _SM_UUID_TOKEN_RE.sub(_replace, result)
    return result, referenced_uuids


# ---------------------------------------------------------------------------
# View XML parsing
# ---------------------------------------------------------------------------

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
    from vcfops_common.client import VCFOpsError

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


def _export_dashboard_json(sm_client, dashboard_uuid: str) -> Optional[dict]:
    """Export all dashboards via content-zip and return the dict for dashboard_uuid.

    The content-zip ``dashboard/dashboard.json`` format contains a ``dashboards[]``
    array where each element has ``id``, ``name``, ``widgets[]`` (with ``config``,
    ``gridsterCoords``, ``type``, ``widgetInteractions``), and ``entries``
    (resourceKind lookup table).  This is the authoritative format that
    ``parse_dashboard_json()`` was designed for.

    The getDashboardConfig UI endpoint returns a completely different format
    (tabConfigs[], no widget config) and should not be used for parsing.

    Returns the matching dashboard dict (with top-level ``entries`` merged in),
    or None if the UUID is not found in the export.
    """
    import json as _json
    from vcfops_common.client import VCFOpsError

    outer_zip = _run_content_export(sm_client, ["DASHBOARDS"])

    # The outer zip contains: dashboards/<uuid> (each is an inner zip)
    # Each inner zip contains dashboard/dashboard.json which has:
    #   {"entries": {...}, "dashboards": [...], "uuid": "..."}
    # We search all inner zips for our target UUID.
    try:
        with zipfile.ZipFile(io.BytesIO(outer_zip)) as zf:
            for name in zf.namelist():
                if not name.startswith("dashboards/") or name.endswith("/"):
                    continue
                inner_bytes = zf.read(name)
                try:
                    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner_zf:
                        if "dashboard/dashboard.json" not in inner_zf.namelist():
                            continue
                        dj = _json.loads(inner_zf.read("dashboard/dashboard.json"))
                except Exception:
                    continue

                entries = dj.get("entries") or {}
                for dash in (dj.get("dashboards") or []):
                    if (dash.get("id") or "").lower() == dashboard_uuid.lower():
                        # Merge entries into the dashboard dict so that
                        # _build_kind_lookup() (called by parse_dashboard_json) can
                        # find the resourceKind synthetic-ref table.
                        result = dict(dash)
                        if entries and "entries" not in result:
                            result["entries"] = entries
                        return result
    except Exception as e:
        raise VCFOpsError(f"failed to parse dashboard export zip: {e}") from e

    return None


def _parse_view_xml(xml_bytes: bytes, target_uuid: str) -> Optional[dict]:
    """Parse a <ViewDef id="..."> entry from the content.xml in a views export zip.

    Returns a dict with keys needed to reconstruct a factory ViewDef, or None
    if the UUID is not found in the XML.

    This is a best-effort reverse parser; it handles the minimum shape
    that render.py's _render_view_def_fragment() produces.  Unknown XML
    elements trigger WARN rather than abort.
    """
    import xml.etree.ElementTree as ET

    def _parse_inner_zip(outer: bytes) -> Optional[bytes]:
        """Extract content.xml from either a bare zip or a zip-in-zip."""
        try:
            with zipfile.ZipFile(io.BytesIO(outer)) as zf:
                names = zf.namelist()
                # Direct content.xml
                if "content.xml" in names:
                    return zf.read("content.xml")
                # Nested zip (views.zip or similar)
                for name in names:
                    if name.lower().endswith(".zip"):
                        inner = zf.read(name)
                        try:
                            with zipfile.ZipFile(io.BytesIO(inner)) as inner_zf:
                                if "content.xml" in inner_zf.namelist():
                                    return inner_zf.read("content.xml")
                        except Exception:
                            pass
                # Direct XML bytes check (some exports embed xml directly)
                for name in names:
                    if name.lower().endswith(".xml"):
                        data = zf.read(name)
                        if b"<ViewDef" in data:
                            return data
        except Exception:
            pass
        return None

    xml_content = _parse_inner_zip(xml_bytes)
    if xml_content is None:
        _warn("could not extract content.xml from views export zip")
        return None

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        _warn(f"failed to parse view XML: {e}")
        return None

    # Find the ViewDef with our target UUID
    target_uuid_lower = target_uuid.lower()
    view_def_elem = None
    # Scope to <Views> block if present
    for elem in root.iter("ViewDef"):
        if (elem.get("id") or "").lower() == target_uuid_lower:
            view_def_elem = elem
            break

    if view_def_elem is None:
        return None

    return _parse_view_def_element(view_def_elem)



def _parse_view_def_element(elem) -> dict:
    """Parse a <ViewDef> XML element into a dict for YAML writing."""
    import xml.etree.ElementTree as ET

    view_id = elem.get("id", "")
    title = ""
    description = ""
    adapter_kind = ""
    resource_kind = ""
    columns = []
    data_type = "list"
    presentation = "list"

    time_window: Optional[dict] = None

    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "Title":
            title = child.text or ""
        elif tag == "Description":
            description = child.text or ""
        elif tag == "SubjectType":
            if not adapter_kind:
                adapter_kind = child.get("adapterKind", "")
            if not resource_kind:
                resource_kind = child.get("resourceKind", "")
        elif tag == "DataProviders":
            for dp in child:
                dp_tag = dp.tag.split("}")[-1] if "}" in dp.tag else dp.tag
                if dp_tag == "DataProvider":
                    dt_raw = dp.get("dataType", "list-view")
                    if "distribution" in dt_raw:
                        data_type = "distribution"
                        presentation = "bar-chart"
                    elif "trend" in dt_raw:
                        data_type = "trend"
                        presentation = "line-chart"
        elif tag == "Presentation":
            ptype = child.get("type", "")
            if ptype:
                presentation = ptype
        elif tag == "Controls":
            columns = _parse_controls_columns(child)
            time_window = _parse_time_window(child)

    return {
        "id": view_id,
        "name": title,
        "description": description,
        "adapter_kind": adapter_kind,
        "resource_kind": resource_kind,
        "columns": columns,
        "data_type": data_type,
        "presentation": presentation,
        "time_window": time_window,
    }


def _parse_time_window(controls_elem) -> Optional[dict]:
    """Parse the time-interval-selector Control from a <Controls> element.

    Returns a dict {unit, count, advanced_time_mode} if the control is present
    with both ``unit`` and ``count`` properties, else None.

    Wire format (from context/view_column_wire_format.md):
        <Control id="..." type="time-interval-selector" visible="false">
          <Property name="advancedTimeMode" value="false"/>
          <Property name="unit" value="MONTHS"/>
          <Property name="count" value="6"/>
        </Control>
    """
    for ctrl in controls_elem:
        ctrl_tag = ctrl.tag.split("}")[-1] if "}" in ctrl.tag else ctrl.tag
        if ctrl_tag != "Control":
            continue
        if ctrl.get("type") != "time-interval-selector":
            continue

        props: dict[str, str] = {}
        for prop in ctrl:
            prop_tag = prop.tag.split("}")[-1] if "}" in prop.tag else prop.tag
            if prop_tag == "Property":
                props[prop.get("name", "")] = prop.get("value", "")

        unit = props.get("unit", "").strip().upper()
        count_raw = props.get("count", "").strip()
        if not unit or not count_raw:
            continue
        try:
            count = int(count_raw)
        except ValueError:
            continue
        if count <= 0:
            continue

        advanced_raw = props.get("advancedTimeMode", "false").strip().lower()
        return {
            "unit": unit,
            "count": count,
            "advanced_time_mode": advanced_raw == "true",
        }

    return None


def _parse_controls_columns(controls_elem) -> list[dict]:
    """Parse <Controls> to extract column definitions from attributes-selector."""
    import xml.etree.ElementTree as ET
    columns = []

    for ctrl in controls_elem:
        ctrl_tag = ctrl.tag.split("}")[-1] if "}" in ctrl.tag else ctrl.tag
        if ctrl_tag != "Control":
            continue
        if ctrl.get("type") != "attributes-selector":
            continue

        # Find attributeInfos List
        for prop in ctrl:
            ptag = prop.tag.split("}")[-1] if "}" in prop.tag else prop.tag
            if ptag != "Property" or prop.get("name") != "attributeInfos":
                continue
            for lst in prop:
                ltag = lst.tag.split("}")[-1] if "}" in lst.tag else lst.tag
                if ltag != "List":
                    continue
                for item in lst:
                    itag = item.tag.split("}")[-1] if "}" in item.tag else item.tag
                    if itag != "Item":
                        continue
                    for val in item:
                        vtag = val.tag.split("}")[-1] if "}" in val.tag else val.tag
                        if vtag != "Value":
                            continue
                        col = _parse_column_value(val)
                        if col:
                            columns.append(col)

    return columns


def _parse_column_value(value_elem) -> Optional[dict]:
    """Parse a <Value> element (attribute info) into a column dict."""

    props: dict[str, str] = {}
    for child in value_elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "Property":
            name = child.get("name", "")
            val = child.get("value")
            if val is not None:
                props[name] = val
            else:
                # List-valued property — build string representation
                vals = []
                for sub in child:
                    sub_tag = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if sub_tag == "List":
                        for item in sub:
                            item_tag = item.tag.split("}")[-1] if "}" in item.tag else item.tag
                            if item_tag == "Item":
                                v = item.get("value")
                                if v:
                                    vals.append(v)
                if name == "transformations" and vals:
                    props["_transformations"] = vals[0] if len(vals) == 1 else ",".join(vals)

    attribute_key = props.get("attributeKey", "")
    if not attribute_key:
        return None

    display_name = props.get("displayName", attribute_key)

    # Detect super metric columns (warn, preserve verbatim)
    if attribute_key.startswith("Super Metric|sm_"):
        # Strip the "Super Metric|" prefix — the YAML attribute for SM cols
        # uses the sm_<uuid> form; render.py auto-prefixes.
        attr_yaml = attribute_key[len("Super Metric|"):]
    elif attribute_key.startswith("Super Metric|"):
        attr_yaml = attribute_key
    else:
        attr_yaml = attribute_key

    col: dict = {
        "attribute": attr_yaml,
        "display_name": display_name,
    }

    unit = props.get("preferredUnitId", "")
    if unit:
        col["unit"] = unit

    transform = props.get("_transformations", "CURRENT")
    if transform and transform not in ("CURRENT", "NONE"):
        col["transformation"] = transform

    # Percentile: emit when transformation is PERCENTILE
    if transform and transform.upper() == "PERCENTILE":
        p_raw = props.get("percentile")
        if p_raw is not None:
            try:
                col["percentile"] = int(p_raw)
            except (ValueError, TypeError):
                pass

    for bound_key, yaml_key in (
        ("yellowBound", "yellow_bound"),
        ("orangeBound", "orange_bound"),
        ("redBound", "red_bound"),
    ):
        v = props.get(bound_key)
        if v is not None:
            try:
                col[yaml_key] = float(v)
            except ValueError:
                col[yaml_key] = v

    ascending = props.get("ascendingRange")
    if ascending is not None:
        # Suppress ascending_range for property-match coloring (string-only red_bound
        # with no yellow/orange bounds).  This mirrors the forward renderer logic in
        # render.py which skips ascendingRange emission for this case.
        has_yellow = col.get("yellow_bound") is not None
        has_orange = col.get("orange_bound") is not None
        red_val = col.get("red_bound")
        red_is_string = red_val is not None and not isinstance(red_val, (int, float))
        if not (red_is_string and not has_yellow and not has_orange):
            col["ascending_range"] = ascending.lower() == "true"

    return col


# ---------------------------------------------------------------------------
# YAML writing helpers
# ---------------------------------------------------------------------------

def _to_yaml_str(data: dict) -> str:
    """Dump a dict to YAML string with sensible defaults."""
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _safe_filename(name: str) -> str:
    """Convert a content object name to a safe filename stem.

    Brackets and parentheses are stripped (not replaced with underscores) so
    that ``[IDPS] Net Usage (All VMs)`` becomes ``IDPS Net Usage All VMs``
    rather than ``_IDPS_ Net Usage _All VMs_``.  All other characters that
    are unsafe in filenames are replaced with underscores.  Leading/trailing
    whitespace and underscores are stripped.
    """
    # Drop bracket/paren characters entirely
    name = re.sub(r'[\[\]()]', '', name)
    # Replace remaining unsafe characters with underscore
    name = re.sub(r'[^\w\-. ]', '_', name)
    # Collapse runs of whitespace/underscores at edges
    return name.strip('_ ')


def _resource_kinds_from_formula(formula: str) -> list[dict]:
    """Parse a SM formula and return resource_kinds inferred from ${adaptertype=X, objecttype=Y} entries.

    Used as a fallback when GET /api/supermetrics/{id} returns an empty
    resourceKinds list.  Extracts all unique (adaptertype, objecttype) pairs
    referenced in the formula and returns them as resource_kinds dicts.

    Returns an empty list if no parseable entries are found, or if all
    entries are ${this, ...} self-references (no explicit adaptertype).
    """
    # Match ${...} resource entries in the formula
    entry_re = re.compile(r"\$\{([^}]*)\}", re.DOTALL)
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for m in entry_re.finditer(formula):
        inner = m.group(1).strip()
        head = inner.split(",", 1)[0].strip().lower()
        if head == "this":
            continue
        # Parse key=value pairs
        kv: dict[str, str] = {}
        depth = 0
        current = ""
        for ch in inner:
            if ch in ("(", "{", "["):
                depth += 1
                current += ch
            elif ch in (")", "}", "]"):
                depth -= 1
                current += ch
            elif ch == "," and depth == 0:
                part = current.strip()
                if "=" in part:
                    k, _, v = part.partition("=")
                    kv[k.strip().lower()] = v.strip()
                current = ""
            else:
                current += ch
        part = current.strip()
        if part and "=" in part:
            k, _, v = part.partition("=")
            kv[k.strip().lower()] = v.strip()

        adapter_kind = kv.get("adaptertype", "").strip()
        resource_kind = kv.get("objecttype", "").strip()
        if not adapter_kind or not resource_kind:
            continue
        key = (adapter_kind, resource_kind)
        if key not in seen:
            seen.add(key)
            result.append({
                "adapter_kind_key": adapter_kind,
                "resource_kind_key": resource_kind,
            })
    return result


def _write_sm_yaml(
    path: Path,
    sm_data: dict,
    formula_rewritten: str,
    policy_resource_kinds: Optional[list] = None,
) -> None:
    """Write a super metric YAML file in factory shape.

    resource_kinds resolution order:
      1. policy_resource_kinds — authoritative policy assignment from the
         Default Policy export (adapter, kind) tuples where the SM is enabled.
         This is the host type the SM is evaluated against, NOT the formula
         input type.
      2. sm_data["resourceKinds"] — the REST API field.  Present on some SMs
         but encodes the formula's input-metric scope, which can differ from
         the policy assignment (e.g. IDPS Planner SMs: formula references
         VirtualMachine metrics but the SM is hosted on HostSystem).
      3. Formula parse fallback — last resort, with a WARN.
      4. Empty list — if nothing works; validator will reject.
    """
    resource_kinds: list = []

    if policy_resource_kinds is not None:
        # Authoritative source: use policy assignment directly.
        resource_kinds = list(policy_resource_kinds)
        if not resource_kinds:
            print(
                f"  WARN: super metric '{sm_data.get('name')}' is not enabled in the "
                "Default Policy for any (adapter, kind) scope; writing resource_kinds: [] "
                "— edit YAML to add the correct scope before installing.",
                file=sys.stderr,
            )
    else:
        # policy_resource_kinds not supplied — fall back to REST API field.
        for rk in (sm_data.get("resourceKinds") or []):
            entry = {}
            rk_key = rk.get("resourceKindKey") or rk.get("resourceKind", "")
            ak_key = rk.get("adapterKindKey") or rk.get("adapterKind", "VMWARE")
            if rk_key:
                entry["resource_kind_key"] = rk_key
            if ak_key:
                entry["adapter_kind_key"] = ak_key
            if entry:
                resource_kinds.append(entry)

        if not resource_kinds:
            # Fallback: parse the formula for ${adaptertype=X, objecttype=Y} pairs.
            # NOTE: this reflects the formula INPUT type, not the policy host type.
            # Prefer fetching policy assignments at call-site to avoid this path.
            formula_rks = _resource_kinds_from_formula(formula_rewritten)
            if formula_rks:
                resource_kinds = formula_rks
                print(
                    f"  WARN: super metric '{sm_data.get('name')}' had no policy "
                    "assignment data and no resourceKinds in API response; inferred "
                    "from formula (INPUT type — may be wrong host scope): "
                    + ", ".join(
                        f"{rk.get('adapter_kind_key')}/{rk.get('resource_kind_key')}"
                        for rk in resource_kinds
                    ),
                    file=sys.stderr,
                )
            else:
                print(
                    f"  WARN: super metric '{sm_data.get('name')}' has no resourceKinds "
                    "in API response and none could be inferred from the formula; "
                    "writing resource_kinds: [] (validator will reject — "
                    "edit YAML to add the correct resource_kind_key/adapter_kind_key)",
                    file=sys.stderr,
                )

    doc: dict = {
        "id": sm_data.get("id", ""),
        "name": sm_data.get("name", ""),
        "formula": formula_rewritten,
    }
    desc = sm_data.get("description", "") or ""
    if desc:
        doc["description"] = desc
    unit = sm_data.get("unitId", "") or ""
    if unit:
        doc["unit_id"] = unit
    doc["resource_kinds"] = resource_kinds

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_yaml_str(doc), encoding="utf-8")


def _write_view_yaml(path: Path, view_data: dict) -> None:
    """Write a view YAML file in factory shape."""
    doc: dict = {
        "id": view_data.get("id", ""),
        "name": view_data.get("name", ""),
    }
    desc = view_data.get("description", "") or ""
    if desc:
        doc["description"] = desc

    doc["subject"] = {
        "adapter_kind": view_data.get("adapter_kind", ""),
        "resource_kind": view_data.get("resource_kind", ""),
    }

    data_type = view_data.get("data_type", "list")
    if data_type != "list":
        doc["data_type"] = data_type
    pres = view_data.get("presentation", "list")
    default_pres = {"list": "list", "distribution": "bar-chart", "trend": "line-chart"}
    if pres != default_pres.get(data_type, "list"):
        doc["presentation"] = pres

    doc["columns"] = view_data.get("columns", [])

    tw = view_data.get("time_window")
    if tw and tw.get("unit") and tw.get("count"):
        tw_doc: dict = {"unit": tw["unit"], "count": tw["count"]}
        if tw.get("advanced_time_mode"):
            tw_doc["advanced_time_mode"] = True
        doc["time_window"] = tw_doc

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_yaml_str(doc), encoding="utf-8")


def _metric_spec_to_yaml(spec) -> dict:
    """Serialize a MetricSpec dataclass to a YAML-ready dict."""
    d: dict = {
        "adapter_kind": spec.adapter_kind,
        "resource_kind": spec.resource_kind,
        "metric_key": spec.metric_key,
        "metric_name": spec.metric_name,
    }
    if spec.unit_id:
        d["unit_id"] = spec.unit_id
    if spec.unit:
        d["unit"] = spec.unit
    if spec.color_method != 2:
        d["color_method"] = spec.color_method
    if spec.color_method == 0:
        if spec.yellow_bound is not None:
            d["yellow_bound"] = spec.yellow_bound
        if spec.orange_bound is not None:
            d["orange_bound"] = spec.orange_bound
        if spec.red_bound is not None:
            d["red_bound"] = spec.red_bound
    if spec.label:
        d["label"] = spec.label
    return d


def _widget_to_yaml_dict(widget, view_name_map: dict) -> dict:
    """Serialize a Widget dataclass to a YAML-ready dict that load_dashboard() can round-trip.

    ``view_name_map`` is not currently used (view_name is already resolved
    in parse_dashboard_json), but is accepted for future use.

    Returns a dict whose keys match what load_dashboard() expects per
    vcfops_dashboards/loader.py.

    Emits a WARN for widget types where config reconstruction is incomplete
    (e.g. HealthChart/ParetoAnalysis where resource_kind may be empty due
    to synthetic resourceKindId in the wire format).
    """
    w = widget
    d: dict = {
        "id": w.local_id,
        "type": w.type,
        "title": w.title,
        "coords": w.coords,
    }

    if w.self_provider:
        d["self_provider"] = True
    if w.pin:
        d["pin"] = {
            "adapter_kind": w.pin.adapter_kind,
            "resource_kind": w.pin.resource_kind,
        }

    if w.type == "View":
        d["view"] = w.view_name
        if w.self_provider:
            d["self_provider"] = True

    elif w.type == "ResourceList":
        d["resource_kinds"] = [
            {"adapter_kind": rk.adapter_kind, "resource_kind": rk.resource_kind}
            for rk in (w.resource_kinds or [])
        ]

    elif w.type == "TextDisplay":
        cfg = w.text_display_config
        if cfg:
            d["html"] = cfg.html
        else:
            _warn(f"widget '{w.local_id}' (TextDisplay): no config; emitting placeholder html")
            d["html"] = "<br>"

    elif w.type == "Scoreboard":
        cfg = w.scoreboard_config
        if cfg:
            d["metrics"] = [_metric_spec_to_yaml(s) for s in cfg.metrics]
            d["visual_theme"] = cfg.visual_theme
            d["show_sparkline"] = cfg.show_sparkline
            if cfg.period_length is not None:
                d["period_length"] = cfg.period_length
            d["show_resource_name"] = cfg.show_resource_name
            d["show_metric_name"] = cfg.show_metric_name
            d["show_metric_unit"] = cfg.show_metric_unit
            d["box_columns"] = cfg.box_columns
            if cfg.box_height is not None:
                d["box_height"] = cfg.box_height
            d["value_size"] = cfg.value_size
            d["label_size"] = cfg.label_size
            d["round_decimals"] = cfg.round_decimals
            d["max_cell_count"] = cfg.max_cell_count
        else:
            _warn(f"widget '{w.local_id}' (Scoreboard): no config; emitting best-effort shape")
            d["metrics"] = []

    elif w.type == "MetricChart":
        cfg = w.metric_chart_config
        if cfg:
            d["metrics"] = [_metric_spec_to_yaml(s) for s in cfg.metrics]
        else:
            _warn(f"widget '{w.local_id}' (MetricChart): no config; emitting best-effort shape")
            d["metrics"] = []

    elif w.type == "HealthChart":
        cfg = w.health_chart_config
        if cfg:
            if not cfg.resource_kind:
                _warn(
                    f"widget type 'HealthChart' at coords {w.coords} emitted with best-effort shape; "
                    "review before re-install (resource_kind is empty due to synthetic resourceKindId)"
                )
            d["adapter_kind"] = cfg.adapter_kind
            d["resource_kind"] = cfg.resource_kind
            d["metric_key"] = cfg.metric_key
            d["metric_name"] = cfg.metric_name
            if cfg.metric_full_name and cfg.metric_full_name != cfg.metric_name:
                d["metric_full_name"] = cfg.metric_full_name
            d["mode"] = cfg.mode
            d["depth"] = cfg.depth
            if cfg.chart_height != 135:
                d["chart_height"] = cfg.chart_height
            if cfg.pagination_number != 15:
                d["pagination_number"] = cfg.pagination_number
            if cfg.sort_by_dir != "asc":
                d["sort_by_dir"] = cfg.sort_by_dir
            if cfg.yellow_bound != -2:
                d["yellow_bound"] = cfg.yellow_bound
            if cfg.orange_bound != -2:
                d["orange_bound"] = cfg.orange_bound
            if cfg.red_bound != -2:
                d["red_bound"] = cfg.red_bound
            d["show_resource_name"] = cfg.show_resource_name
        else:
            _warn(
                f"widget type 'HealthChart' at coords {w.coords} emitted with best-effort shape; "
                "review before re-install"
            )
            d["adapter_kind"] = "VMWARE"
            d["resource_kind"] = ""
            d["metric_key"] = ""
            d["metric_name"] = ""

    elif w.type == "ParetoAnalysis":
        cfg = w.pareto_analysis_config
        if cfg:
            if not cfg.resource_kind:
                _warn(
                    f"widget type 'ParetoAnalysis' at coords {w.coords} emitted with best-effort shape; "
                    "review before re-install (resource_kind is empty due to synthetic resourceKindId)"
                )
            d["adapter_kind"] = cfg.adapter_kind
            d["resource_kind"] = cfg.resource_kind
            d["metric_key"] = cfg.metric_key
            d["metric_name"] = cfg.metric_name
            d["mode"] = cfg.mode
            d["top_n"] = cfg.top_n
            if cfg.bottom_n > 0:
                d["bottom_n"] = cfg.bottom_n
            d["top_option"] = cfg.top_option
            d["depth"] = cfg.depth
            d["regeneration_time"] = cfg.regeneration_time
            d["round_decimals"] = cfg.round_decimals
        else:
            _warn(
                f"widget type 'ParetoAnalysis' at coords {w.coords} emitted with best-effort shape; "
                "review before re-install"
            )
            d["adapter_kind"] = "VMWARE"
            d["resource_kind"] = ""
            d["metric_key"] = ""
            d["metric_name"] = ""

    elif w.type == "AlertList":
        cfg = w.alert_list_config
        if cfg:
            d["criticality"] = cfg.criticality
            if cfg.alert_types:
                d["alert_types"] = cfg.alert_types
            if cfg.status:
                d["status"] = cfg.status
            d["mode"] = cfg.mode
            d["depth"] = cfg.depth
        else:
            _warn(f"widget '{w.local_id}' (AlertList): no config; emitting best-effort shape")

    elif w.type == "ProblemAlertsList":
        cfg = w.problems_alerts_list_config
        if cfg:
            d["impacted_badge"] = cfg.impacted_badge
            d["triggered_object"] = cfg.triggered_object
            if cfg.top_issues_limit > 0:
                d["top_issues_limit"] = cfg.top_issues_limit
        else:
            _warn(f"widget '{w.local_id}' (ProblemAlertsList): no config; emitting best-effort shape")

    elif w.type == "Heatmap":
        cfg = w.heatmap_config
        if cfg:
            d["mode"] = cfg.mode
            d["depth"] = cfg.depth
            tabs_yaml = []
            for tab in cfg.tabs:
                if not tab.resource_kind:
                    _warn(
                        f"widget type 'Heatmap' at coords {w.coords} emitted with best-effort shape; "
                        f"review before re-install (tab '{tab.name}' resource_kind is empty)"
                    )
                tab_d: dict = {
                    "name": tab.name,
                    "adapter_kind": tab.adapter_kind,
                    "resource_kind": tab.resource_kind,
                    "color_by": {
                        "metric_key": tab.color_by_key,
                        "label": tab.color_by_label,
                    },
                }
                if tab.size_by_key is not None:
                    tab_d["size_by"] = {
                        "metric_key": tab.size_by_key,
                        "label": tab.size_by_label,
                    }
                if tab.group_by_kind:
                    tab_d["group_by"] = {
                        "adapter_kind": tab.group_by_adapter,
                        "resource_kind": tab.group_by_kind,
                        "text": tab.group_by_text,
                    }
                tab_d["color"] = {
                    "min_value": tab.color.min_value,
                    "thresholds": {
                        "values": tab.color.values,
                        "colors": tab.color.colors,
                    },
                }
                if tab.color.max_value is not None:
                    tab_d["color"]["max_value"] = tab.color.max_value
                if tab.solid_coloring:
                    tab_d["solid_coloring"] = tab.solid_coloring
                if not tab.focus_on_groups:
                    tab_d["focus_on_groups"] = tab.focus_on_groups
                tabs_yaml.append(tab_d)
            d["configs"] = tabs_yaml
        else:
            _warn(
                f"widget type 'Heatmap' at coords {w.coords} emitted with best-effort shape; "
                "review before re-install"
            )
            d["configs"] = []

    else:
        # Unknown/unsupported widget type — best-effort passthrough
        _warn(
            f"widget type '{w.type}' at coords {w.coords} emitted with best-effort shape; "
            "review before re-install"
        )

    return d


def _write_dashboard_yaml(path: Path, dash_data: dict, dashboard_uuid: str, view_results: dict, factory_native: bool = False) -> None:
    """Write a dashboard YAML file in factory shape with real widget + interaction graph.

    ``dash_data`` is the raw dict from getDashboardConfig.
    ``dashboard_uuid`` is the resolved dashboard UUID.
    ``view_results`` is a mapping of uuid_lower -> view dict (used to build
    views_by_id for parse_dashboard_json view resolution).

    Uses vcfops_dashboards.reverse.parse_dashboard_json() to parse the full
    widget graph, then serializes each Widget dataclass to YAML.
    """
    from vcfops_dashboards.reverse import parse_dashboard_json
    from vcfops_dashboards.loader import ViewDef

    # Build a views_by_id dict for View widget resolution.
    # view_results maps uuid_lower -> {'id': ..., 'name': ..., ...} dicts.
    views_by_id: dict[str, ViewDef] = {}
    for vuuid, vdata in view_results.items():
        vid = vdata.get("id") or vuuid
        vname = vdata.get("name") or vuuid
        # Construct a minimal ViewDef for name resolution only
        vd = ViewDef(
            id=vid,
            name=vname,
            description="",
            adapter_kind=vdata.get("adapter_kind", ""),
            resource_kind=vdata.get("resource_kind", ""),
            columns=[],
        )
        views_by_id[vid.lower()] = vd

    # Ensure id is set
    dash_data_copy = dict(dash_data)
    dash_data_copy["id"] = dashboard_uuid

    # Parse the full widget graph
    try:
        dashboard = parse_dashboard_json(dash_data_copy, views_by_id)
    except Exception as e:
        _warn(f"parse_dashboard_json failed ({e}); falling back to empty widget list")
        dashboard = None

    # Determine name_path and display_name
    name = dash_data.get("name", "")
    name_path_raw = dash_data.get("namePath") or ""
    if "/" in name:
        parts = name.split("/", 1)
        name_path = name_path_raw or parts[0].strip()
        display_name = parts[1].strip()
    else:
        name_path = name_path_raw
        display_name = name.strip()

    doc: dict = {
        "id": dashboard_uuid,
        "name": display_name,
    }
    if dashboard and dashboard.description:
        doc["description"] = dashboard.description
    elif dash_data.get("description"):
        doc["description"] = dash_data.get("description", "") or ""
    # For third-party (factory_native=False) extracts, suppress the factory
    # folder name so extracted dashboards don't install into "VCF Content Factory".
    # A non-factory source dashboard may legitimately be in its own folder; only
    # suppress the factory-reserved name.
    if name_path and (factory_native or name_path != "VCF Content Factory"):
        doc["name_path"] = name_path

    doc["shared"] = bool(dash_data.get("shared", True))

    # Serialize widget graph
    if dashboard and dashboard.widgets:
        widgets_yaml = []
        for w in dashboard.widgets:
            try:
                wd = _widget_to_yaml_dict(w, {})
                widgets_yaml.append(wd)
            except Exception as e:
                _warn(
                    f"widget type '{w.type}' at coords {w.coords} emitted with best-effort shape; "
                    f"review before re-install (serialization error: {e})"
                )
                # Best-effort fallback: emit bare widget skeleton
                widgets_yaml.append({
                    "id": w.local_id,
                    "type": w.type,
                    "title": w.title,
                    "coords": w.coords,
                })
        doc["widgets"] = widgets_yaml
    else:
        _warn("dashboard has no widgets or parse failed; writing empty widget list")
        doc["widgets"] = []

    # Serialize interactions
    if dashboard and dashboard.interactions:
        doc["interactions"] = [
            {
                "from": ix.from_local_id,
                "to": ix.to_local_id,
                "type": ix.type,
            }
            for ix in dashboard.interactions
        ]
    else:
        doc["interactions"] = []

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_yaml_str(doc), encoding="utf-8")


def _collect_enablement_entries(
    metric_refs: list,
    describe_cache,
) -> list[dict]:
    """Walk metric refs through the describe cache and return enablement entries.

    For each MetricReference where defaultMonitored=False, emits a dict
    suitable for the manifest's builtin_metric_enables list.  Entries are
    de-duplicated by (adapter_kind, resource_kind, metric_key) — the first
    source_desc wins for the reason string.  Refs not in the cache (stale or
    missing) emit a WARN and are skipped.

    Args:
        metric_refs: List of MetricReference objects (from deps.py).
        describe_cache: A DescribeCache instance (may be offline).

    Returns:
        List of dicts with keys adapter_kind, resource_kind, metric_key, reason.
    """
    from vcfops_packaging.describe import DescribeCache as _DC

    seen: set[tuple[str, str, str]] = set()
    entries: list[dict] = []

    for ref in metric_refs:
        key_triple = (ref.adapter_kind, ref.resource_kind, ref.metric_key)
        if key_triple in seen:
            continue
        try:
            info = describe_cache.resolve_metric(
                ref.adapter_kind, ref.resource_kind, ref.metric_key
            )
        except Exception as e:
            _warn(
                f"describe cache lookup failed for "
                f"{ref.adapter_kind}/{ref.resource_kind} {ref.metric_key}: {e}; "
                "skipping enablement entry"
            )
            continue

        if info is None:
            _warn(
                f"metric key not in describe cache: "
                f"{ref.adapter_kind}/{ref.resource_kind} {ref.metric_key} "
                f"(referenced by {ref.source_desc}); "
                "refresh-describe and re-extract to populate builtin_metric_enables"
            )
            continue

        seen.add(key_triple)
        if not info.default_monitored:
            entry = {
                "adapter_kind": ref.adapter_kind,
                "resource_kind": ref.resource_kind,
                "metric_key": ref.metric_key,
                "reason": f"required by {ref.source_desc}",
            }
            entries.append(entry)
            _info(
                f"builtin_metric_enables: {ref.adapter_kind}/{ref.resource_kind} "
                f"{ref.metric_key} (defaultMonitored=false, from {ref.source_desc})"
            )

    return entries


def _write_manifest(
    manifest_path: Path,
    slug: str,
    bundle_name: str,
    author: str,
    license_: str,
    source_url: str,
    source_version: str,
    description_file: Path,
    sm_paths: list[str],
    view_paths: list[str],
    dashboard_paths: list[str],
    output_dir: Path,
    builtin_metric_enables: list[dict] = None,
) -> None:
    """Write the bundle manifest YAML at bundles/third_party/<slug>.yaml.

    All content file paths are written relative to the repo root so
    ``vcfops_packaging/loader.py::_resolve()`` can find them.
    The manifest itself lives at bundles/third_party/<slug>.yaml, so the
    loader's repo_root = path.parent.parent correctly resolves to the repo root.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Description: read from file as folded scalar
    desc_text = ""
    if description_file.exists():
        desc_text = description_file.read_text(encoding="utf-8").strip()

    doc: dict = {
        "name": slug,
        "display_name": bundle_name,
        "description": desc_text or f"Extracted bundle: {bundle_name}",
        "factory_native": False,
        "author": author,
        "license": license_,
    }

    source: dict = {}
    if source_url:
        source["url"] = source_url
    if source_version:
        source["version"] = source_version
    source["captured_at"] = now
    if source:
        doc["source"] = source

    # Path strategy: the manifest lives at bundles/third_party/<slug>.yaml.
    # load_bundle calculates repo_root = path.parent.parent = bundles/ (not
    # the actual repo root!), so repo-relative paths like
    # "bundles/third_party/<slug>/supermetrics/foo.yaml" won't resolve.
    #
    # Use manifest-relative paths instead: "<slug>/supermetrics/foo.yaml".
    # load_bundle's fallback is path.parent / ref = bundles/third_party/<slug>/supermetrics/foo.yaml
    # which is exactly where the extractor writes the files.

    def _rel(p: str) -> str:
        return str(Path(slug) / p)

    if sm_paths:
        doc["supermetrics"] = [_rel(p) for p in sm_paths]
    if view_paths:
        doc["views"] = [_rel(p) for p in view_paths]
    if dashboard_paths:
        doc["dashboards"] = [_rel(p) for p in dashboard_paths]

    if builtin_metric_enables:
        doc["builtin_metric_enables"] = builtin_metric_enables

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(_to_yaml_str(doc), encoding="utf-8")


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
                "  Run 'python -m vcfops_extractor list-dashboards' to see available dashboards.",
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
    # metric specs, etc.) — only widget shells (id, title, key, gridster coords).
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
            "  Verify the UUID with: python -m vcfops_extractor list-dashboards",
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

    # Collect view UUIDs referenced by widgets
    widgets = dash_data.get("widgets") or []
    view_uuids: list[str] = []
    for w in widgets:
        cfg = w.get("config") or {}
        view_id = cfg.get("viewDefinitionId")
        if view_id and view_id not in view_uuids:
            view_uuids.append(view_id)

    print(f"  Found {len(widgets)} widget(s), {len(view_uuids)} view reference(s)")

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
    existing_sm_ids = _scan_existing_ids("supermetric")
    existing_view_ids = _scan_existing_ids("view")
    existing_dash_ids = _scan_existing_ids("dashboard")

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
        from vcfops_supermetrics.client import VCFOpsClient as _VCFOpsClient
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

    # BFS over super metrics (with transitive SM->SM via formula rewriting)
    sm_queue: deque[tuple[str, str]] = deque()
    sm_seen: set[str] = set()

    for suuid in sm_uuids_from_views:
        if suuid not in sm_seen:
            sm_seen.add(suuid)
            sm_queue.append((suuid, "view column"))

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

        # Fetch SM
        try:
            sm_data = sm_client.get_supermetric(suuid)
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
            scope_str = "NOT IN DEFAULT POLICY — resource_kinds will be empty"
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
        print(f"and a manifest at {output_path / (bundle_slug + '.yaml')}.")
        print()
        print("Re-run with --yes to proceed, or --dry-run to preview without writing.")
        return 0

    # -----------------------------------------------------------------------
    # Write YAML files
    # -----------------------------------------------------------------------
    sm_file_paths: list[str] = []
    view_file_paths: list[str] = []
    dash_file_paths: list[str] = []

    # Super metrics — orphan check before writing
    # An orphan SM is one whose formula references metric keys that are absent
    # from the describe cache entirely (not merely defaultMonitored=false).
    # "Ships broken" is a build error: refuse to write the file and surface
    # the unresolved keys on stdout.  This mirrors the packaging dependency
    # audit principle from context/feedback_packaging_dependency_audit.md.
    sm_subdir = slug_dir / "supermetrics"
    orphan_check_cache = DescribeCache()
    orphaned_sms: list[str] = []

    for suuid, sm_data in sm_results.items():
        sm_name_display = sm_data.get("name", suuid)
        formula = sm_formulas.get(sm_data.get("id", suuid), sm_data.get("formula", ""))

        # Collect built-in metric refs from the (rewritten) formula
        from vcfops_packaging.deps import _refs_from_formula, _is_sm_ref
        formula_refs = [r for r in _refs_from_formula(formula, sm_name_display) if not _is_sm_ref(r.metric_key)]

        unresolved: list[str] = []
        for ref in formula_refs:
            try:
                info = orphan_check_cache.resolve_metric(ref.adapter_kind, ref.resource_kind, ref.metric_key)
            except Exception:
                info = None  # cache miss or offline; skip orphan check for this key
            if info is None:
                # Could be a cache miss (stale cache) or a genuinely missing metric.
                # Only flag as orphan if the cache has entries for this adapter/kind
                # (i.e., the cache file exists) — avoids false-positives on cold caches.
                try:
                    has_cache = orphan_check_cache.has_cache_file(ref.adapter_kind, ref.resource_kind)
                except Exception:
                    has_cache = False
                if has_cache:
                    unresolved.append(f"{ref.adapter_kind}/{ref.resource_kind}  {ref.metric_key}")

        if unresolved:
            print(
                f"  ORPHAN: super metric '{sm_name_display}' references metric keys not in "
                "describe cache — skipping write.",
                file=sys.stderr,
            )
            for key_str in unresolved:
                print(f"    unresolved: {key_str}", file=sys.stderr)
            print(
                "  Possible cause: source metric was removed from the live instance after "
                "the SM was authored. Remove the SM from the source dashboard or update "
                "the describe cache (python3 -m vcfops_packaging refresh-describe) "
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
    from vcfops_packaging.deps import (
        MetricReference,
        _refs_from_formula,
        _normalize_metric_key,
        _is_sm_ref,
    )
    from vcfops_packaging.describe import DescribeCache

    all_metric_refs: dict[tuple[str, str, str], MetricReference] = {}

    def _add_ref(ref: MetricReference) -> None:
        k = (ref.adapter_kind, ref.resource_kind, ref.metric_key)
        if k not in all_metric_refs:
            all_metric_refs[k] = ref

    # Super metric formula refs
    for suuid, sm_data in sm_results.items():
        formula = sm_formulas.get(sm_data.get("id", suuid), sm_data.get("formula", ""))
        sm_name = sm_data.get("name", suuid)
        for ref in _refs_from_formula(formula, sm_name):
            _add_ref(ref)

    # View column refs (raw dict form — mirrors deps._refs_from_view logic)
    for vuuid, view_data in view_results.items():
        ak = view_data.get("adapter_kind", "")
        rk = view_data.get("resource_kind", "")
        view_name = view_data.get("name", vuuid)
        if ak and rk:
            for col in view_data.get("columns", []):
                attr = (col.get("attribute") or "").strip()
                if not attr or _is_sm_ref(attr):
                    continue
                attr = _normalize_metric_key(attr)
                _add_ref(MetricReference(
                    adapter_kind=ak,
                    resource_kind=rk,
                    metric_key=attr,
                    source_desc=f"view {view_name!r}",
                ))

    # Dashboard widget refs via parse_dashboard_json
    try:
        from vcfops_dashboards.reverse import parse_dashboard_json
        from vcfops_dashboards.loader import ViewDef as _ViewDef
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

    # Resolve against offline describe cache (no live call — user refreshes describe separately)
    offline_cache = DescribeCache()
    bme_list = _collect_enablement_entries(list(all_metric_refs.values()), offline_cache)
    if not bme_list:
        _info("enablement walk: all referenced metrics are defaultMonitored=true (or cache miss); no builtin_metric_enables entries needed")

    # Bundle manifest
    manifest_path = output_path / f"{bundle_slug}.yaml"
    _write_manifest(
        manifest_path=manifest_path,
        slug=bundle_slug,
        bundle_name=display_name,
        author=author,
        license_=license_,
        source_url=source_url,
        source_version=source_version,
        description_file=description_file,
        sm_paths=sm_file_paths,
        view_paths=view_file_paths,
        dashboard_paths=dash_file_paths,
        output_dir=output_path,
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
    print(f"  2. Validate:  python -m vcfops_packaging validate {manifest_path}")
    print(f"  3. Build:     python -m vcfops_packaging build {manifest_path}")
    return 0
