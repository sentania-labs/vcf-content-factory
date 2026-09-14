"""Content-export parsers and factory-shape YAML writers (M2 row 4).

The location-agnostic half of the extractor: everything here takes bytes,
dicts or dataclasses in and writes only to a path it was handed.

- ``_parse_view_xml`` and its helpers: a VIEW_DEFINITIONS export zip (or
  its ``content.xml``) to a view dict the YAML writer accepts.
- ``_rewrite_formula``: ``sm_<uuid>`` tokens to ``@supermetric:"<name>"``
  through any object with ``name_for_uuid``.
- ``_resource_kinds_from_formula``, ``_metric_spec_to_yaml``,
  ``_widget_to_yaml_dict``, ``_emit_view_extras``: wire shapes to YAML dicts.
- ``_write_sm_yaml`` / ``_write_view_yaml`` / ``_write_dashboard_yaml`` /
  ``_write_manifest``: explicit output path in, factory-shape YAML out.
- ``_collect_enablement_entries``: metric refs through a describe cache the
  caller built.

What stays in the factory (``vcfcf_extractor.extractor``): the live suite
API and UI clients, the content-export calls, the SM name cache backed by
the instance, the existing-id scan of the repo (which is why the repo root
is bound there and never here), and the ``extract_dashboard`` walk itself.
The factory module re-exports every name below, so the old import path
keeps working; patch this module, not the wrapper, to affect a running
extraction.
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from ..dashboards.reverse import _parse_controls_meta, _trend_transformations_to_emit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _warn(msg: str) -> None:
    print(f"  WARN: {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"  {msg}")


# ---------------------------------------------------------------------------
# Formula UUID -> name rewriting
# ---------------------------------------------------------------------------

_SM_UUID_TOKEN_RE = re.compile(r"sm_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")


def _rewrite_formula(formula: str, name_cache) -> tuple[str, set[str]]:
    """Rewrite sm_<uuid> tokens in a formula to @supermetric:"<name>".

    ``name_cache`` is anything with a ``name_for_uuid(uuid) -> Optional[str]``
    method: the factory's live ``_SMNameCache`` (backed by the suite API) or
    a plain in-memory map. Returns (rewritten_formula, set_of_referenced_uuids).
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
    subject_pairs: list[tuple[str, str]] = []
    columns = []
    data_type = "list"
    presentation = "list"

    time_window: Optional[dict] = None
    meta = {"hide_object_name": False, "forecast_days": 0, "transformations": None}

    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "Title":
            title = child.text or ""
        elif tag == "Description":
            description = child.text or ""
        elif tag == "SubjectType":
            # One ViewDef may carry several subject kinds, each as a
            # descendant+self pair, in sequence (wire evidence:
            # reference/docs/extracted/view-multi-subject/). Keep every
            # distinct pair in document order; the first stays the scalar.
            pair = (child.get("adapterKind", ""), child.get("resourceKind", ""))
            if pair not in subject_pairs:
                subject_pairs.append(pair)
            if not adapter_kind:
                adapter_kind = pair[0]
            if not resource_kind:
                resource_kind = pair[1]
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
            meta = _parse_controls_meta(child)

    if len(subject_pairs) <= 1:
        # Single-subject view: per-column binding is implied by the one
        # SubjectType and the loader rejects `subject:` on a column.
        for col in columns:
            col.pop("subject", None)

    return {
        "id": view_id,
        "name": title,
        "description": description,
        "adapter_kind": adapter_kind,
        "resource_kind": resource_kind,
        "subjects": (
            [{"adapter_kind": ak, "resource_kind": rk} for ak, rk in subject_pairs]
            if len(subject_pairs) > 1 else []
        ),
        "columns": columns,
        "data_type": data_type,
        "presentation": presentation,
        "time_window": time_window,
        "hide_object_name": meta["hide_object_name"],
        "forecast_days": meta["forecast_days"] if data_type == "trend" else 0,
        "transformations": _trend_transformations_to_emit(
            data_type, meta["forecast_days"], meta["transformations"]
        ),
    }

# _parse_controls_meta / _trend_transformations_to_emit are shared with the
# dashboards reverse path; one definition lives in vcfcf_core.dashboards.reverse.



def _parse_time_window(controls_elem) -> Optional[dict]:
    """Parse the time-interval-selector Control from a <Controls> element.

    Returns a dict {unit, count, advanced_time_mode, start_period, end_period}
    if the control is present with both ``unit`` and ``count`` properties,
    else None. ``start_period``/``end_period`` are None when absent (the
    common case: advanced_time_mode false).

    Wire format (from knowledge/context/wire-formats/view_column_wire_format.md):
        <Control id="..." type="time-interval-selector" visible="false">
          <Property name="advancedTimeMode" value="false"/>
          <Property name="unit" value="MONTHS"/>
          <Property name="count" value="6"/>
        </Control>

    Advanced-mode wire format (FB-011) additionally carries a range:
        <Control id="..." type="time-interval-selector" visible="false">
          <Property name="advancedTimeMode" value="true"/>
          <Property name="unit" value="DAYS"/>
          <Property name="count" value="7"/>
          <Property name="startPeriod" value="PREVIOUS"/>
          <Property name="endPeriod" value="NOW"/>
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
        start_period = props.get("startPeriod", "").strip().upper() or None
        end_period = props.get("endPeriod", "").strip().upper() or None
        return {
            "unit": unit,
            "count": count,
            "advanced_time_mode": advanced_raw == "true",
            "start_period": start_period,
            "end_period": end_period,
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
                # List-valued property: build string representation
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
                    # Per-column transformation is the first item; a
                    # multi-item list (NONE, TREND, FORECAST on trend
                    # views) is view-level and handled by
                    # _parse_controls_meta, not a per-column value.
                    props["_transformations"] = vals[0]

    attribute_key = props.get("attributeKey", "")
    if not attribute_key:
        return None

    display_name = props.get("displayName", attribute_key)

    # Time-segment ("Interval Breakdown") pseudo-column: not a metric column.
    # See TimeSegmentSpec in vcfcf_core/dashboards/loader.py for the wire shape.
    if props.get("isTimeSegment", "").strip().lower() == "true":
        try:
            _soc = int(props.get("startingOnCount", "1") or 1)
        except ValueError:
            _soc = 1
        return {
            "display_name": display_name,
            "time_segment": {
                "breakdown_by": props.get("breakdownBy", "").strip().upper(),
                "starting_on_unit": (props.get("startingOnUnit", "WEEKS") or "WEEKS").strip().upper(),
                "starting_on_count": _soc,
            },
        }

    # Detect super metric columns (warn, preserve verbatim)
    if attribute_key.startswith("Super Metric|sm_"):
        # Strip the "Super Metric|" prefix: the YAML attribute for SM cols
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

    # Per-column kind binding (adapterKind/resourceKind Properties).
    # _parse_view_def_element drops it on single-subject views (implied by
    # the one SubjectType); on multi-subject views a bound column keeps it
    # as `subject:` and an unbound column has none. See
    # knowledge/context/api-surface/view_multi_subject_column_binding.md.
    if props.get("adapterKind") and props.get("resourceKind"):
        col["subject"] = {
            "adapter_kind": props["adapterKind"],
            "resource_kind": props["resourceKind"],
        }

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
      1. policy_resource_kinds: authoritative policy assignment from the
         Default Policy export (adapter, kind) tuples where the SM is enabled.
         This is the host type the SM is evaluated against, NOT the formula
         input type.
      2. sm_data["resourceKinds"]: the REST API field.  Present on some SMs
         but encodes the formula's input-metric scope, which can differ from
         the policy assignment (e.g. IDPS Planner SMs: formula references
         VirtualMachine metrics but the SM is hosted on HostSystem).
      3. Formula parse fallback: last resort, with a WARN.
      4. Empty list: if nothing works; validator will reject.
    """
    resource_kinds: list = []

    if policy_resource_kinds is not None:
        # Authoritative source: use policy assignment directly.
        resource_kinds = list(policy_resource_kinds)
        if not resource_kinds:
            print(
                f"  WARN: super metric '{sm_data.get('name')}' is not enabled in the "
                "Default Policy for any (adapter, kind) scope; writing resource_kinds: [] "
                "(edit YAML to add the correct scope before installing).",
                file=sys.stderr,
            )
    else:
        # policy_resource_kinds not supplied: fall back to REST API field.
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
                    "from formula (INPUT type: may be wrong host scope): "
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
                    "writing resource_kinds: [] (validator will reject: "
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


def _emit_view_extras(doc: dict, view_data: dict) -> None:
    """Emit hide_object_name / forecast_days / transformations when the
    source carried them (all three default-off in the loader)."""
    if view_data.get("hide_object_name"):
        doc["hide_object_name"] = True
    fd = int(view_data.get("forecast_days") or 0)
    if fd > 0:
        doc["forecast_days"] = fd
    tr = view_data.get("transformations")
    if tr:
        doc["transformations"] = list(tr)


def _write_view_yaml(path: Path, view_data: dict) -> None:
    """Write a view YAML file in factory shape."""
    doc: dict = {
        "id": view_data.get("id", ""),
        "name": view_data.get("name", ""),
    }
    desc = view_data.get("description", "") or ""
    if desc:
        doc["description"] = desc

    if view_data.get("subjects"):
        # Multi-subject ViewDef: `subjects:` (authored order = document
        # order) replaces the scalar pair, which mirrors subjects[0].
        doc["subjects"] = [dict(sub) for sub in view_data["subjects"]]
    else:
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
    _emit_view_extras(doc, view_data)

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
    if spec.is_string_metric:
        d["is_string_metric"] = True
    # Gauge full-scale ceiling; without it a re-render emits maxValue: "" and
    # the component falls back to its own default instead of the authored one.
    if getattr(spec, "max_value", None) is not None:
        d["max_value"] = spec.max_value
    return d


def _widget_to_yaml_dict(widget, view_name_map: dict) -> dict:
    """Serialize a Widget dataclass to a YAML-ready dict that load_dashboard() can round-trip.

    ``view_name_map`` is not currently used (view_name is already resolved
    in parse_dashboard_json), but is accepted for future use.

    Returns a dict whose keys match what load_dashboard() expects per
    vcfcf_core/dashboards/loader.py.

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
        if getattr(w.pin, "name", ""):
            d["pin"]["name"] = w.pin.name

    if w.type == "View":
        d["view"] = w.view_name
        if w.self_provider:
            d["self_provider"] = True
        if not w.select_first_row:
            d["select_first_row"] = False
        if w.chart_view_items:
            d["chart_view_items"] = list(w.chart_view_items)

    elif w.type == "ResourceList":
        d["resource_kinds"] = [
            {"adapter_kind": rk.adapter_kind, "resource_kind": rk.resource_kind}
            for rk in (w.resource_kinds or [])
        ]
        if not w.select_first_row:
            d["select_first_row"] = False

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
            if getattr(cfg, "metric_mode", "resourceKind") == "resource" and cfg.resource is not None:
                d["metric_mode"] = "resource"
                d["resource"] = {
                    "adapter_kind": cfg.resource.adapter_kind,
                    "resource_kind": cfg.resource.resource_kind,
                    "name": cfg.resource.name,
                }
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
            # None round-trips as `round_decimals: null` (a real wire value).
            d["round_decimals"] = cfg.round_decimals
            d["max_cell_count"] = cfg.max_cell_count
            if getattr(cfg, "show_dt", False):
                d["show_dt"] = True
            if not getattr(cfg, "refresh_content", True):
                d["refresh_content"] = False
            # Gauge layout settings.  Emitted only when non-default so existing
            # extracted YAML is unchanged; the loader supplies the same
            # defaults, so the re-rendered wire payload round-trips either way.
            if getattr(cfg, "layout_mode", "fixedView") != "fixedView":
                d["layout_mode"] = cfg.layout_mode
            if getattr(cfg, "show_remaining", False):
                d["show_remaining"] = True
            if getattr(cfg, "show_percent_text", False):
                d["show_percent_text"] = True
            if getattr(cfg, "focus_on_percent", False):
                d["focus_on_percent"] = True
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

    elif w.type == "PropertyList":
        cfg = w.property_list_config
        if cfg:
            d["property_list"] = {
                "properties": [_metric_spec_to_yaml(s) for s in cfg.properties],
                "visual_theme": cfg.visual_theme,
                "depth": cfg.depth,
                "show_metric_full_name": cfg.show_metric_full_name,
            }
        else:
            _warn(f"widget '{w.local_id}' (PropertyList): no config; emitting empty property_list")
            d["property_list"] = {"properties": []}

    elif w.type == "ResourceRelationshipAdvanced":
        cfg = w.resource_relationship_advanced_config
        if cfg:
            d["resource_relationship_advanced"] = {
                "resource_kinds": [
                    {"adapter_kind": rk.adapter_kind, "resource_kind": rk.resource_kind}
                    for rk in cfg.resource_kinds
                ],
                "depth": cfg.depth,
                "pagination_number": cfg.pagination_number,
                "self_provider": cfg.self_provider,
            }
        else:
            _warn(
                f"widget '{w.local_id}' (ResourceRelationshipAdvanced): no config; "
                "emitting empty resource_relationship_advanced"
            )
            d["resource_relationship_advanced"] = {"resource_kinds": [], "depth": "2,1"}

    else:
        # Unknown/unsupported widget type: best-effort passthrough
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

    Uses vcfcf_core.dashboards.reverse.parse_dashboard_json() to parse the full
    widget graph, then serializes each Widget dataclass to YAML.
    """
    from ..dashboards.reverse import parse_dashboard_json
    from ..dashboards.loader import ViewDef

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
    de-duplicated by (adapter_kind, resource_kind, metric_key): the first
    source_desc wins for the reason string.  Refs not in the cache (stale or
    missing) emit a WARN and are skipped.

    Args:
        metric_refs: List of MetricReference objects (from deps.py).
        describe_cache: A DescribeCache instance (may be offline).

    Returns:
        List of dicts with keys adapter_kind, resource_kind, metric_key, reason.
    """
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
    builtin_metric_enables: list[dict] = None,
) -> None:
    """Write the bundle PROJECT.yaml at third_party/<slug>/PROJECT.yaml.

    Uses the v3 layout: PROJECT.yaml lives inside the slug directory alongside
    supermetrics/, views/, dashboards/ subdirs.  No explicit content lists are
    written: vcfcf_packaging/loader.py auto-discovers content from subdirs
    when the manifest is named PROJECT.yaml and carries no explicit lists.
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

    # No explicit supermetrics/views/dashboards lists: the loader auto-discovers
    # content from subdirs when the file is named PROJECT.yaml.

    if builtin_metric_enables:
        doc["builtin_metric_enables"] = builtin_metric_enables

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(_to_yaml_str(doc), encoding="utf-8")
