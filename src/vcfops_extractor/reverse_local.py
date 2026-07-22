"""Local-file reverse-port for vcfops_extractor.

Converts original MP source files (local dashboard JSON + view XML) into
factory-shape YAML without touching a live VCF Ops instance.

Entry point: ``reverse_local_port()``

Design:
  - View XMLs: each file in the source reports/ directory may contain many
    ``<ViewDef>`` elements.  All are parsed into a UUID-keyed map so that
    dashboard View widgets can be resolved by ``viewDefinitionId``.
  - Dashboard JSON: follows the same ``{entries, dashboards[]}`` shape that
    the live extractor pulls from a content-zip export, so
    ``parse_dashboard_json()`` (reverse.py) accepts it unchanged.
  - SM UUID->name: built from SM YAML files in the ported SM directory
    (``id:`` field = UUID, ``name:`` = human name). Used to rewrite
    ``sm_<uuid>`` column attributes to ``supermetric:"<name>"`` (no ``@``).
  - SM name->UUID: the inverse map; used to rewrite column attributes in
    view YAML (``sm_<uuid>`` → ``supermetric:"<name>"``).
  - Unsupported widget types (PropertyList, ResourceRelationshipAdvanced, etc.):
    emit WARN naming dashboard + widget type; widget is skipped (not fatal).
  - Missing views (UUID in dashboard JSON but no matching <ViewDef> in any
    XML file): emit WARN naming dashboard + UUID; View widget uses UUID as
    fallback name and continues.
  - Round-trip diff check: after emitting YAML, render forward and compare
    the rendered JSON structure to the source JSON.  Reports per-dashboard:
    MATCH / PARTIAL (<N> widget structural divergences) / UNSUPPORTED (no
    widgets parsed due to all-unsupported types).

This module DOES NOT:
  - Touch a live instance.
  - Install, sync, or enable content.
  - Overwrite existing YAML that already carries the same UUID.
"""
from __future__ import annotations

import json
import re
import sys
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import yaml


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _warn(msg: str) -> None:
    print(f"  WARN: {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"  {msg}")


def _to_yaml_str(data: dict) -> str:
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _safe_filename(name: str) -> str:
    """Convert a content-object name to a safe filename stem.

    Brackets and parentheses are stripped; all other unsafe characters
    become underscores.  Leading/trailing whitespace and underscores are
    stripped.  Mirrors ``extractor._safe_filename``.
    """
    name = re.sub(r"[\[\]()]", "", name)
    name = re.sub(r"[^\w\-. ]", "_", name)
    return name.strip("_ ")


# ---------------------------------------------------------------------------
# SM YAML -> UUID/name maps
# ---------------------------------------------------------------------------

def _build_sm_maps(sm_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Scan SM YAML files and return (uuid_lower->name, name->uuid_lower).

    Reads every ``*.yaml`` / ``*.yml`` under *sm_dir*.  Each file must have
    an ``id:`` key (UUID) and a ``name:`` key.  Files missing either key emit
    a WARN and are skipped.
    """
    uuid_to_name: dict[str, str] = {}
    name_to_uuid: dict[str, str] = {}

    if not sm_dir.exists():
        _warn(f"SM directory not found: {sm_dir}; SM UUID->name resolution will be empty")
        return uuid_to_name, name_to_uuid

    for p in sorted(sm_dir.rglob("*.y*ml")):
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as e:
            _warn(f"could not parse {p}: {e}; skipping")
            continue
        if not isinstance(doc, dict):
            continue
        uid = str(doc.get("id") or "").strip()
        name = str(doc.get("name") or "").strip()
        if not uid or not name:
            _warn(f"{p}: missing 'id' or 'name' field; skipping SM map entry")
            continue
        uuid_to_name[uid.lower()] = name
        name_to_uuid[name] = uid.lower()

    _info(f"SM map built: {len(uuid_to_name)} super metric(s) from {sm_dir}")
    return uuid_to_name, name_to_uuid


# ---------------------------------------------------------------------------
# View XML -> per-UUID ViewDef map
# ---------------------------------------------------------------------------

_SM_ATTR_UUID_RE = re.compile(
    r"^Super Metric\|sm_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)
_SM_BARE_UUID_RE = re.compile(
    r"^sm_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)


def _rewrite_sm_attr(attribute: str, uuid_to_name: dict[str, str]) -> str:
    """Rewrite a column ``attribute`` value:

    ``Super Metric|sm_<uuid>``  ->  ``supermetric:"<name>"``   (if resolved)
    ``sm_<uuid>``               ->  ``supermetric:"<name>"``   (if resolved)

    The VIEW-COLUMN cross-reference form is ``supermetric:"<name>"`` (no ``@``
    prefix).  The ``@supermetric:"<name>"`` form (with ``@``) is the SM-FORMULA
    form used inside supermetric YAML formula strings and must NOT be emitted
    here.  The forward renderer's ``_xml_attribute_item`` dispatches on the
    ``supermetric:"`` prefix (no ``@``) to resolve to ``Super Metric|sm_<uuid>``.

    If the UUID cannot be resolved (not in uuid_to_name), the value is kept
    in ``sm_<uuid>`` form (same as the live extractor) and a WARN is emitted.
    """
    m = _SM_ATTR_UUID_RE.match(attribute) or _SM_BARE_UUID_RE.match(attribute)
    if not m:
        return attribute
    uid = m.group(1).lower()
    name = uuid_to_name.get(uid)
    if name:
        return f'supermetric:"{name}"'
    _warn(f"could not resolve SM UUID {uid} to a name; keeping sm_<uuid> form")
    return f"sm_{uid}"


def _parse_view_xml_to_dict(elem) -> dict:
    """Parse a <ViewDef> XML element to a dict compatible with _write_view_yaml.

    Mirrors ``extractor._parse_view_def_element`` closely; kept separate to
    avoid coupling to the live-extractor internals.
    """
    view_id = elem.get("id", "")
    title = ""
    description = ""
    adapter_kind = ""
    resource_kind = ""
    data_type = "list"
    presentation = "list"
    columns: list[dict] = []
    time_window: Optional[dict] = None

    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "Title":
            title = (child.text or "").strip()
        elif tag == "Description":
            description = (child.text or "").strip()
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
            columns = _parse_controls_to_column_dicts(child)
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


def _parse_controls_to_column_dicts(controls_elem) -> list[dict]:
    """Parse <Controls> block into column dicts (mirroring extractor logic)."""
    columns: list[dict] = []
    for ctrl in controls_elem:
        ctrl_tag = ctrl.tag.split("}")[-1] if "}" in ctrl.tag else ctrl.tag
        if ctrl_tag != "Control":
            continue
        if ctrl.get("type") != "attributes-selector":
            continue
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
                        col = _parse_column_value_dict(val)
                        if col is not None:
                            columns.append(col)
    return columns


def _parse_time_window(controls_elem) -> Optional[dict]:
    """Parse the time-interval-selector Control from <Controls>."""
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
        adv = props.get("advancedTimeMode", "false").strip().lower() == "true"
        start_period = props.get("startPeriod", "").strip().upper() or None
        end_period = props.get("endPeriod", "").strip().upper() or None
        return {
            "unit": unit,
            "count": count,
            "advanced_time_mode": adv,
            "start_period": start_period,
            "end_period": end_period,
        }
    return None


def _parse_column_value_dict(value_elem) -> Optional[dict]:
    """Parse a <Value> element into a column dict."""
    props: dict[str, str] = {}
    transform_list: list[str] = []

    for child in value_elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag != "Property":
            continue
        name = child.get("name", "")
        val = child.get("value")
        if val is not None:
            props[name] = val
        elif name == "transformations":
            for sub in child:
                sub_tag = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                if sub_tag == "List":
                    for item in sub:
                        item_tag = item.tag.split("}")[-1] if "}" in item.tag else item.tag
                        if item_tag == "Item":
                            v = item.get("value")
                            if v:
                                transform_list.append(v)

    attribute_key = props.get("attributeKey", "")
    if not attribute_key:
        return None

    display_name = props.get("displayName", attribute_key)

    # Strip "Super Metric|" prefix — YAML attribute uses sm_<uuid> form
    if attribute_key.startswith("Super Metric|sm_"):
        attr_yaml = attribute_key[len("Super Metric|"):]
    else:
        attr_yaml = attribute_key

    col: dict = {
        "attribute": attr_yaml,
        "display_name": display_name,
    }

    unit = props.get("preferredUnitId", "")
    if unit:
        col["unit"] = unit

    transform = transform_list[0] if transform_list else "CURRENT"
    if transform and transform not in ("CURRENT", "NONE"):
        col["transformation"] = transform

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
    has_yellow = col.get("yellow_bound") is not None
    has_orange = col.get("orange_bound") is not None
    red_val = col.get("red_bound")
    red_is_string = red_val is not None and not isinstance(red_val, (int, float))
    if ascending is not None:
        if not (red_is_string and not has_yellow and not has_orange):
            col["ascending_range"] = ascending.lower() == "true"
    else:
        # ascendingRange is absent from the wire.  When all three numeric bounds are
        # present the loader requires ascending_range — derive it from bound ordering,
        # which is the same signal the forward renderer encodes:
        #   yellow < orange < red  →  False  (higher-is-worse: CPU %, latency)
        #   yellow > orange > red  →  True   (lower-is-worse: free capacity, headroom)
        # See knowledge/context/wire-formats/view_column_wire_format.md §ascending_range derivation.
        y_val = col.get("yellow_bound")
        o_val = col.get("orange_bound")
        all_numeric = (
            has_yellow and has_orange and red_val is not None
            and not red_is_string
            and isinstance(y_val, (int, float))
            and isinstance(o_val, (int, float))
            and isinstance(red_val, (int, float))
        )
        if all_numeric:
            y, o, r = float(y_val), float(o_val), float(red_val)  # type: ignore[arg-type]
            if y < o and o < r:
                col["ascending_range"] = False
            elif y > o and o > r:
                col["ascending_range"] = True
            else:
                # Ambiguous ordering — default to higher-is-worse.
                import warnings as _warnings
                _warnings.warn(
                    f"column {display_name!r}: all three numeric bounds set but "
                    f"ascendingRange absent and ordering is ambiguous "
                    f"(yellow={y}, orange={o}, red={r}); defaulting to "
                    "ascending_range=False (higher-is-worse) — review reversed YAML",
                    UserWarning,
                    stacklevel=3,
                )
                col["ascending_range"] = False

    return col


def build_view_uuid_map(xml_dir: Path) -> dict[str, dict]:
    """Scan all *.xml files under xml_dir for <ViewDef> elements.

    Returns a mapping of uuid_lower -> view_dict.  Multiple XML files are
    merged; if the same UUID appears twice the last file wins (with a WARN).
    """
    result: dict[str, dict] = {}
    if not xml_dir.exists():
        _warn(f"view XML directory not found: {xml_dir}")
        return result

    xml_files = sorted(xml_dir.glob("*.xml"))
    _info(f"Scanning {len(xml_files)} XML file(s) in {xml_dir}")

    for p in xml_files:
        try:
            root = ET.fromstring(p.read_bytes())
        except ET.ParseError as e:
            _warn(f"XML parse error in {p.name}: {e}; skipping file")
            continue

        view_count = 0
        new_count = 0
        for elem in root.iter("ViewDef"):
            uid = (elem.get("id") or "").lower().strip()
            if not uid:
                continue
            is_new = uid not in result
            vd = _parse_view_xml_to_dict(elem)
            result[uid] = vd
            view_count += 1
            if is_new:
                new_count += 1
        # Duplicates across XML files are normal (Collection01.xml is a
        # superset that the Set-*.xml files repeat).  Log net-new only.

        dup_count = view_count - new_count
        dup_note = f" ({dup_count} already seen from prior files, skipped)" if dup_count else ""
        _info(f"  {p.name}: {new_count} new ViewDef(s){dup_note}")

    _info(f"View map total: {len(result)} ViewDef(s)")
    return result


# ---------------------------------------------------------------------------
# View YAML writing
# ---------------------------------------------------------------------------

def _write_view_yaml(path: Path, view_data: dict, uuid_to_name: dict[str, str]) -> None:
    """Write a view YAML file in factory shape, rewriting SM UUID refs."""
    doc: dict = {
        "id": view_data.get("id", ""),
        "name": view_data.get("name", ""),
    }
    desc = (view_data.get("description") or "").strip()
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

    # Rewrite column SM refs
    columns_out: list[dict] = []
    for col in (view_data.get("columns") or []):
        col_out = dict(col)
        col_out["attribute"] = _rewrite_sm_attr(col.get("attribute", ""), uuid_to_name)
        columns_out.append(col_out)
    doc["columns"] = columns_out

    tw = view_data.get("time_window")
    if tw and tw.get("unit") and tw.get("count"):
        tw_doc: dict = {"unit": tw["unit"], "count": tw["count"]}
        if tw.get("advanced_time_mode"):
            tw_doc["advanced_time_mode"] = True
        if tw.get("start_period"):
            tw_doc["start_period"] = tw["start_period"]
        if tw.get("end_period"):
            tw_doc["end_period"] = tw["end_period"]
        doc["time_window"] = tw_doc

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_yaml_str(doc), encoding="utf-8")


# ---------------------------------------------------------------------------
# Dashboard JSON -> YAML writing (reuses reverse.py + extractor helpers)
# ---------------------------------------------------------------------------

def _merge_entries(dash_json: dict, top_entries: dict) -> dict:
    """Merge top-level entries into a per-dashboard dict if not already there."""
    if top_entries and "entries" not in dash_json:
        result = dict(dash_json)
        result["entries"] = top_entries
        return result
    return dash_json


def _write_dashboard_yaml(
    path: Path,
    dash_json: dict,
    view_uuid_map: dict[str, dict],
    name_path_override: Optional[str] = None,
) -> list[str]:
    """Parse a dashboard JSON dict and write factory-shape YAML.

    Returns list of WARN messages emitted for unsupported widget types.
    """
    import warnings as _warnings

    from vcfops_dashboards.reverse import parse_dashboard_json, _SUPPORTED_WIDGET_TYPES
    from vcfops_dashboards.loader import ViewDef

    # Build views_by_id for View widget resolution
    views_by_id: dict[str, ViewDef] = {}
    for uid, vdata in view_uuid_map.items():
        vid = vdata.get("id") or uid
        vname = vdata.get("name") or uid
        vd = ViewDef(
            id=vid,
            name=vname,
            description="",
            adapter_kind=vdata.get("adapter_kind", ""),
            resource_kind=vdata.get("resource_kind", ""),
            columns=[],
        )
        views_by_id[vid.lower()] = vd

    # Collect unsupported widget types before parsing (for WARN)
    raw_widgets = dash_json.get("widgets") or []
    unsupported_types: list[str] = []
    for w in raw_widgets:
        wtype = w.get("type") or ""
        if wtype and wtype not in _SUPPORTED_WIDGET_TYPES:
            unsupported_types.append(wtype)

    caught_warnings: list[str] = []
    with _warnings.catch_warnings(record=True) as wlist:
        _warnings.simplefilter("always")
        try:
            dashboard = parse_dashboard_json(dash_json, views_by_id)
        except Exception as e:
            _warn(f"parse_dashboard_json failed: {e}; writing empty widget list")
            dashboard = None
        caught_warnings = [str(w.message) for w in wlist]

    # Determine display name and name_path from the raw JSON
    raw_name = (dash_json.get("name") or "").strip()
    raw_name_path = (dash_json.get("namePath") or "").strip()
    if "/" in raw_name:
        parts = raw_name.split("/", 1)
        source_name_path = raw_name_path or parts[0].strip()
        display_name = parts[1].strip()
    else:
        source_name_path = raw_name_path
        display_name = raw_name

    # Use override if provided
    effective_name_path = name_path_override if name_path_override is not None else source_name_path

    doc: dict = {
        "id": str(dash_json.get("id") or ""),
        "name": display_name,
    }
    desc = (dash_json.get("description") or "").strip()
    if desc:
        doc["description"] = desc
    if effective_name_path:
        doc["name_path"] = effective_name_path
    doc["shared"] = bool(dash_json.get("shared", True))

    # Import widget serializer from extractor (reuse existing code)
    from vcfops_extractor.extractor import _widget_to_yaml_dict

    if dashboard and dashboard.widgets:
        widgets_yaml = []
        for w in dashboard.widgets:
            try:
                wd = _widget_to_yaml_dict(w, {})
                widgets_yaml.append(wd)
            except Exception as e:
                _warn(
                    f"widget '{w.local_id}' ({w.type}) at coords {w.coords}: "
                    f"serialization error: {e}"
                )
                widgets_yaml.append({
                    "id": w.local_id,
                    "type": w.type,
                    "title": w.title,
                    "coords": w.coords,
                })
        doc["widgets"] = widgets_yaml
    else:
        doc["widgets"] = []

    if dashboard and dashboard.interactions:
        doc["interactions"] = [
            {"from": ix.from_local_id, "to": ix.to_local_id, "type": ix.type}
            for ix in dashboard.interactions
        ]
    else:
        doc["interactions"] = []

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_yaml_str(doc), encoding="utf-8")

    return unsupported_types


# ---------------------------------------------------------------------------
# Round-trip diff check
# ---------------------------------------------------------------------------

def _structural_key(widget_json: dict) -> tuple:
    """Extract a structural key from a rendered widget for comparison.

    Compares: type, gridsterCoords (x,y,w,h), config keys (viewDefinitionId,
    metricKey, etc.).  Ignores install-time stamps (locked, owner, userId).
    """
    wtype = widget_json.get("type", "")
    coords = widget_json.get("gridsterCoords") or {}
    coord_key = (
        coords.get("x"),
        coords.get("y"),
        coords.get("w"),
        coords.get("h"),
    )
    cfg = widget_json.get("config") or {}
    view_id = cfg.get("viewDefinitionId", "")
    return (wtype, coord_key, view_id)


def _compare_dashboard_round_trip(
    source_json: dict,
    yaml_path: Path,
    view_yaml_dir: Path,
    sm_yaml_dir: Path,
) -> dict:
    """Render the YAML forward and compare structure to the source JSON.

    Returns a result dict:
      {
        "status": "MATCH" | "PARTIAL" | "UNSUPPORTED" | "ERROR",
        "dashboard_name": str,
        "rendered_widgets": int,
        "source_widgets": int,
        "divergences": [str],  # list of structural divergence descriptions
        "error": str | None,
      }
    """
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    raw_name = (source_json.get("name") or "").strip()
    display_name = raw_name.split("/", 1)[-1].strip() if "/" in raw_name else raw_name

    result: dict = {
        "dashboard_name": display_name,
        "status": "ERROR",
        "rendered_widgets": 0,
        "source_widgets": len(source_json.get("widgets") or []),
        "divergences": [],
        "error": None,
    }

    # Load the YAML back through the factory loader
    try:
        dashboard = load_dashboard(yaml_path, enforce_framework_prefix=False)
    except Exception as e:
        result["error"] = f"load_dashboard failed: {e}"
        return result

    # Gather SM YAML paths for the scoped renderer
    sm_yaml_paths = list(sm_yaml_dir.rglob("*.y*ml")) if sm_yaml_dir.exists() else []

    # Gather view YAML paths (in the sibling views/ directory)
    view_yaml_paths = list(view_yaml_dir.rglob("*.y*ml")) if view_yaml_dir.exists() else []

    # Build views_by_name for render
    from vcfops_dashboards.loader import load_view
    views_by_name: dict = {}
    for vp in view_yaml_paths:
        try:
            vd = load_view(vp, enforce_framework_prefix=False)
            if vd:
                views_by_name[vd.name] = vd
        except Exception:
            pass

    try:
        rendered_json_str = render_dashboards_bundle_json(
            dashboards=[dashboard],
            views_by_name=views_by_name,
            owner_user_id="00000000-0000-0000-0000-000000000001",
        )
        rendered = json.loads(rendered_json_str)
    except KeyError as e:
        # A View widget references a view name that wasn't emitted (either a
        # missing source view or a UUID-fallback name).  This is an expected
        # gap when source views are absent from the reference tree.
        result["status"] = "PARTIAL"
        result["divergences"].append(
            f"render skipped: missing view reference {e} "
            "(source view XML not in reference tree)"
        )
        return result
    except Exception as e:
        result["error"] = f"render failed: {e}"
        return result

    # Extract the rendered dashboard from the bundle
    rendered_dashboards = rendered.get("dashboards") or []
    if not rendered_dashboards:
        result["error"] = "rendered bundle has no dashboards[]"
        return result
    rendered_dash = rendered_dashboards[0]

    rendered_widgets = rendered_dash.get("widgets") or []
    source_widgets = source_json.get("widgets") or []

    result["rendered_widgets"] = len(rendered_widgets)

    if not rendered_widgets and not source_widgets:
        result["status"] = "MATCH"
        return result

    if not rendered_widgets:
        result["status"] = "UNSUPPORTED"
        result["divergences"].append(
            f"0 widgets rendered (source has {len(source_widgets)})"
        )
        return result

    # Compare structurally: match rendered widgets to source widgets by type+coords
    source_keys = [_structural_key(w) for w in source_widgets]
    rendered_keys = [_structural_key(w) for w in rendered_widgets]

    divergences: list[str] = []

    if len(rendered_widgets) != len(source_widgets):
        # Count which source types are present vs rendered
        from vcfops_dashboards.reverse import _SUPPORTED_WIDGET_TYPES as _SUPP
        source_unsupported = [
            w.get("type") for w in source_widgets
            if w.get("type") and w.get("type") not in _SUPP
        ]
        if source_unsupported:
            divergences.append(
                f"widget count: rendered={len(rendered_widgets)}, "
                f"source={len(source_widgets)} "
                f"(source has unsupported types: {sorted(set(source_unsupported))})"
            )
        else:
            divergences.append(
                f"widget count: rendered={len(rendered_widgets)}, "
                f"source={len(source_widgets)}"
            )

    # Compare type+coords keys that ARE present in both
    rendered_key_set = set(rendered_keys)
    for sk in source_keys:
        wtype = sk[0]
        from vcfops_dashboards.reverse import _SUPPORTED_WIDGET_TYPES as _SUPP
        if wtype not in _SUPP:
            continue  # expected missing
        if sk not in rendered_key_set:
            divergences.append(
                f"source widget type={wtype} coords={sk[1]} view_id={sk[2]!r} "
                "not found in rendered output"
            )

    if divergences:
        result["status"] = "PARTIAL"
        result["divergences"] = divergences
    else:
        result["status"] = "MATCH"

    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def reverse_local_port(
    *,
    source_dashboard_json: Path,
    source_view_xml_dir: Path,
    sm_yaml_dir: Path,
    output_views_dir: Path,
    output_dashboards_dir: Path,
    name_path_override: Optional[str] = None,
    dry_run: bool = False,
    run_diff: bool = True,
) -> int:
    """Reverse-port local MP source files to factory YAML.

    Args:
        source_dashboard_json: Path to a dashboard JSON file (may contain
            multiple dashboards in ``dashboards[]``).
        source_view_xml_dir: Directory containing source view XML files
            (each may have many <ViewDef> elements).
        sm_yaml_dir: Directory of ported SM YAML files for UUID->name resolution.
        output_views_dir: Where to write emitted view YAML files.
        output_dashboards_dir: Where to write emitted dashboard YAML files.
        name_path_override: If set, use this as the ``name_path`` in emitted
            dashboard YAML (overrides the source JSON's namePath / folder prefix).
            Pass ``""`` to suppress the name_path field entirely.
        dry_run: If True, parse and plan but do not write any files.
        run_diff: If True, perform the round-trip diff check after writing.

    Returns:
        0 on success, 1 on fatal error.
    """
    print(f"\n{'=' * 60}")
    print("reverse-local: LOCAL-FILE REVERSE PORT")
    print(f"{'=' * 60}")
    print(f"  Source dashboards: {source_dashboard_json}")
    print(f"  Source views dir:  {source_view_xml_dir}")
    print(f"  SM YAML dir:       {sm_yaml_dir}")
    print(f"  Output views:      {output_views_dir}")
    print(f"  Output dashboards: {output_dashboards_dir}")
    if dry_run:
        print("  DRY RUN — no files will be written")
    print()

    # 1. Build SM UUID -> name map
    uuid_to_name, name_to_uuid = _build_sm_maps(sm_yaml_dir)

    # 2. Build view UUID map from all XML files in the source dir
    view_uuid_map = build_view_uuid_map(source_view_xml_dir)

    # 3. Load the source dashboard JSON
    if not source_dashboard_json.exists():
        print(f"ERROR: dashboard JSON not found: {source_dashboard_json}", file=sys.stderr)
        return 1

    try:
        raw = json.loads(source_dashboard_json.read_bytes())
    except Exception as e:
        print(f"ERROR: could not parse {source_dashboard_json}: {e}", file=sys.stderr)
        return 1

    # The file may follow the content-zip format {entries, dashboards[]}
    # or be a bare dashboard object.
    top_entries = raw.get("entries") or {}
    source_dashboards: list[dict] = raw.get("dashboards") or []
    if not source_dashboards:
        # Bare single-dashboard format (some reference files)
        if "widgets" in raw or "id" in raw:
            source_dashboards = [raw]
        else:
            print(
                f"ERROR: {source_dashboard_json} has no 'dashboards' array and "
                "no 'widgets'/'id' key — cannot determine dashboard format",
                file=sys.stderr,
            )
            return 1

    print(f"Found {len(source_dashboards)} dashboard(s) in source file")

    # 4. For each dashboard: identify referenced views
    all_view_uuids: set[str] = set()
    for dash in source_dashboards:
        for w in (dash.get("widgets") or []):
            cfg = w.get("config") or {}
            vid = cfg.get("viewDefinitionId")
            if vid:
                all_view_uuids.add(vid.lower())

    found_views = {uid: view_uuid_map[uid] for uid in all_view_uuids if uid in view_uuid_map}
    missing_views = {uid for uid in all_view_uuids if uid not in view_uuid_map}

    print(f"\nViews referenced: {len(all_view_uuids)}")
    print(f"  Found in XML:  {len(found_views)}")
    if missing_views:
        print(f"  Missing:       {len(missing_views)}")
        for uid in sorted(missing_views):
            _warn(f"view UUID {uid} not found in any source XML; View widgets will use UUID as name")

    # 5. Plan: collect widget types
    all_types: set[str] = set()
    from vcfops_dashboards.reverse import _SUPPORTED_WIDGET_TYPES
    unsupported_in_source: set[str] = set()
    for dash in source_dashboards:
        for w in (dash.get("widgets") or []):
            wtype = w.get("type") or ""
            if wtype:
                all_types.add(wtype)
                if wtype not in _SUPPORTED_WIDGET_TYPES:
                    unsupported_in_source.add(wtype)

    if unsupported_in_source:
        print(f"\nUnsupported widget types (will WARN per dashboard, not fatal):")
        for t in sorted(unsupported_in_source):
            print(f"  - {t}")

    print(f"\nAll widget types in source: {sorted(all_types)}")

    if dry_run:
        print("\nDRY RUN — would emit:")
        print(f"  {len(found_views)} view YAML(s) -> {output_views_dir}/")
        print(f"  {len(source_dashboards)} dashboard YAML(s) -> {output_dashboards_dir}/")
        return 0

    # 6. Write view YAMLs
    print(f"\n--- Writing {len(found_views)} view YAML(s) ---")
    written_views: list[Path] = []
    for uid, vdata in sorted(found_views.items(), key=lambda kv: kv[1].get("name", kv[0])):
        vname = vdata.get("name") or uid
        fname = _safe_filename(vname) + ".yaml"
        out_path = output_views_dir / fname
        _write_view_yaml(out_path, vdata, uuid_to_name)
        _info(f"wrote view: {out_path}")
        written_views.append(out_path)

    # 7. Write dashboard YAMLs
    print(f"\n--- Writing {len(source_dashboards)} dashboard YAML(s) ---")
    written_dashboards: list[Path] = []
    all_unsupported_seen: dict[str, list[str]] = {}  # dash_name -> [types]

    for dash in source_dashboards:
        # Merge top-level entries into per-dashboard dict
        dash_with_entries = _merge_entries(dash, top_entries)

        raw_name = (dash.get("name") or "").strip()
        if "/" in raw_name:
            display_name = raw_name.split("/", 1)[1].strip()
        else:
            display_name = raw_name

        fname = _safe_filename(display_name) + ".yaml"
        out_path = output_dashboards_dir / fname

        unsupported_types = _write_dashboard_yaml(
            out_path,
            dash_with_entries,
            view_uuid_map=found_views,
            name_path_override=name_path_override,
        )
        _info(f"wrote dashboard: {out_path}")
        written_dashboards.append(out_path)

        if unsupported_types:
            unique_types = sorted(set(unsupported_types))
            all_unsupported_seen[display_name] = unique_types
            for t in unique_types:
                _warn(
                    f"dashboard '{display_name}': widget type '{t}' is not supported "
                    "by the forward renderer — widget skipped in YAML output"
                )

    # 8. Round-trip diff check
    diff_results: list[dict] = []
    if run_diff:
        print(f"\n--- Round-trip diff check ---")
        for i, (dash, out_path) in enumerate(zip(source_dashboards, written_dashboards)):
            # Merge entries for diff source
            dash_with_entries = _merge_entries(dash, top_entries)
            diff = _compare_dashboard_round_trip(
                source_json=dash_with_entries,
                yaml_path=out_path,
                view_yaml_dir=output_views_dir,
                sm_yaml_dir=sm_yaml_dir,
            )
            diff_results.append(diff)
            status = diff["status"]
            name = diff["dashboard_name"]
            r = diff.get("rendered_widgets", 0)
            s = diff.get("source_widgets", 0)
            if status == "MATCH":
                print(f"  MATCH      '{name}'  ({r}/{s} widgets)")
            elif status == "PARTIAL":
                print(f"  PARTIAL    '{name}'  ({r}/{s} widgets)")
                for d in diff.get("divergences", []):
                    print(f"               divergence: {d}")
            elif status == "UNSUPPORTED":
                print(f"  UNSUPPORTED '{name}'  (no supported widgets to render)")
            elif status == "ERROR":
                print(f"  ERROR      '{name}': {diff.get('error')}")
            else:
                print(f"  {status}  '{name}'")

    # 9. Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Views written:      {len(written_views)}")
    print(f"  Dashboards written: {len(written_dashboards)}")
    if all_unsupported_seen:
        print(f"  Unsupported widget types encountered:")
        for dname, types in sorted(all_unsupported_seen.items()):
            print(f"    '{dname}': {types}")
    if diff_results:
        match_count = sum(1 for r in diff_results if r["status"] == "MATCH")
        partial_count = sum(1 for r in diff_results if r["status"] == "PARTIAL")
        error_count = sum(1 for r in diff_results if r["status"] in ("ERROR", "UNSUPPORTED"))
        print(f"  Round-trip: {match_count} MATCH, {partial_count} PARTIAL, {error_count} UNSUPPORTED/ERROR")
    print()
    print("Next steps:")
    print("  1. Review emitted YAML files")
    print("  2. Validate: python3 -m vcfops_dashboards validate")
    print("  3. Address any PARTIAL/WARN items manually")
    return 0
