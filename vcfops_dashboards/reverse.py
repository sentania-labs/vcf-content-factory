"""Reverse parser: wire format -> factory dataclasses.

Inverts the forward render path (render.py) for content received from
a live VCF Ops instance.

Dashboard JSON:
  getDashboardConfig returns a JSON shape matching dashboard/dashboard.json
  in the content-zip export.  _parse_dashboard_json() strips the
  ``locked``/``owner`` stamps that the importer adds at install time
  (the packager re-adds them at build time).

View XML:
  The VIEW_DEFINITIONS content-zip export contains a content.xml whose
  structure mirrors what render_views_xml() produces.  parse_view_xml()
  reads a single <ViewDef> by UUID and returns a ViewDef dataclass.

WARN is emitted (not raised) for XML elements/widget types the forward
renderer doesn't support (render.py "minimum viable shape" comment,
line 11).  The caller continues with partial results.

Phase 1 scope:
  - Dashboard JSON parsing: structural extraction (id, name, description,
    name_path, shared).  Widget graph reconstruction requires widget-type
    reverse parsers (Phase 2 for unsupported types, Phase 1 for the 10
    supported types where we can map backwards).
  - View XML parsing: full column extraction including SM UUID resolution.

Both parsers are called by vcfops_extractor.extractor; the dataclasses
returned are compatible with loader.py (same fields).
"""
from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path
from typing import Optional

from .loader import (
    AlertListConfig,
    Dashboard,
    HeatmapColorThreshold,
    HeatmapConfig,
    HeatmapTab,
    HealthChartConfig,
    Interaction,
    MetricChartConfig,
    MetricSpec,
    ParetoAnalysisConfig,
    ProblemAlertsListConfig,
    ScoreboardConfig,
    TextDisplayConfig,
    ViewDef,
    ViewColumn,
    ViewTimeWindow,
    Widget,
    WidgetResourceKindRef,
)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _warn(msg: str) -> None:
    warnings.warn(f"vcfops_dashboards.reverse: {msg}", UserWarning, stacklevel=3)


# ---------------------------------------------------------------------------
# Synthetic resourceKind:id:N_::_ lookup helpers
# ---------------------------------------------------------------------------

_SYNTHETIC_RK_RE = re.compile(r"^resourceKind:id:(\d+)_::_$")
_SYNTHETIC_RES_RE = re.compile(r"^resource:id:(\d+)_::_$")


def _build_resource_lookup(dashboard_json: dict) -> dict[int, dict]:
    """Build an index → {adapter_kind, resource_kind} map from entries.resource[].

    The forward renderer (render.py) populates entries.resource[] with entries
    shaped as::

        {
            "resourceKindKey": "<ResourceKindName>",
            "internalId": "resource:id:<N>_::_",
            "adapterKindKey": "<AdapterKindName>",
            "name": "<ResourceKindName>",
            "identifiers": [],
        }

    Self-provider View and ProblemAlertsList widget configs reference their
    pinned container resource via ``config.resource.resourceId`` using the same
    ``resource:id:N_::_`` synthetic form.  This function inverts the table so
    reverse parsers can recover the real adapter/resource kind from a synthetic
    ref.

    Returns an empty dict if the entries block is absent or malformed.
    """
    lookup: dict[int, dict] = {}
    entries = dashboard_json.get("entries") or {}
    res_entries = entries.get("resource") or []
    for entry in res_entries:
        internal_id = str(entry.get("internalId") or "")
        m = _SYNTHETIC_RES_RE.match(internal_id)
        if not m:
            continue
        idx = int(m.group(1))
        lookup[idx] = {
            "adapter_kind": str(entry.get("adapterKindKey") or "").strip(),
            "resource_kind": str(entry.get("resourceKindKey") or entry.get("name") or "").strip(),
        }
    return lookup


def _resolve_res_id(
    res_id: str,
    resource_lookup: dict[int, dict],
    context: str,
) -> "tuple[Optional[str], Optional[str]]":
    """Resolve a synthetic ``resource:id:N_::_`` string to (adapter_kind, resource_kind).

    Returns ``(adapter_kind, resource_kind)`` when resolved, or ``(None, None)``
    when the input is not a synthetic ref.  Emits WARN only when the ref IS
    synthetic but the index is not present in resource_lookup.
    """
    res_id = res_id.strip()
    m = _SYNTHETIC_RES_RE.match(res_id)
    if not m:
        return None, None
    idx = int(m.group(1))
    entry = resource_lookup.get(idx)
    if entry is None:
        _warn(
            f"{context}: synthetic ref {res_id!r} points to index {idx} which is "
            "not present in entries.resource[]; pin will not be emitted"
        )
        return "", ""
    return entry["adapter_kind"], entry["resource_kind"]


def _build_kind_lookup(dashboard_json: dict) -> dict[int, dict]:
    """Build an index → {adapter_kind, resource_kind} map from entries.resourceKind[].

    The forward renderer (render.py) populates entries.resourceKind[] with entries
    shaped as::

        {
            "resourceKindKey": "<ResourceKindName>",
            "internalId": "resourceKind:id:<N>_::_",
            "adapterKindKey": "<AdapterKindName>",
        }

    Widget configs reference these by ``resourceKind:id:N_::_``.  We invert
    the table here so that reverse parsers can recover the real adapter/resource
    kind strings from a synthetic ref.

    Returns an empty dict if the entries block is absent or malformed.
    """
    lookup: dict[int, dict] = {}
    entries = dashboard_json.get("entries") or {}
    rk_entries = entries.get("resourceKind") or []
    for entry in rk_entries:
        internal_id = str(entry.get("internalId") or "")
        m = _SYNTHETIC_RK_RE.match(internal_id)
        if not m:
            continue
        idx = int(m.group(1))
        lookup[idx] = {
            "adapter_kind": str(entry.get("adapterKindKey") or "").strip(),
            "resource_kind": str(entry.get("resourceKindKey") or "").strip(),
        }
    return lookup


def _resolve_rk_id(
    rk_id: str,
    kind_lookup: dict[int, dict],
    context: str,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve a synthetic ``resourceKind:id:N_::_`` string to (adapter_kind, resource_kind).

    Returns ``(adapter_kind, resource_kind)`` when resolved, or ``(None, None)``
    when the input is not a synthetic ref.  Emits WARN only when the ref IS
    synthetic but the index is not present in kind_lookup (genuine wire-data error).
    """
    rk_id = rk_id.strip()
    m = _SYNTHETIC_RK_RE.match(rk_id)
    if not m:
        # Not a synthetic ref — caller handles non-synthetic forms directly.
        return None, None
    idx = int(m.group(1))
    entry = kind_lookup.get(idx)
    if entry is None:
        _warn(
            f"{context}: synthetic ref {rk_id!r} points to index {idx} which is "
            "not present in entries.resourceKind[]; adapter_kind and resource_kind "
            "will be empty"
        )
        return "", ""
    return entry["adapter_kind"], entry["resource_kind"]


# ---------------------------------------------------------------------------
# View XML -> ViewDef
# ---------------------------------------------------------------------------

def parse_view_xml_element(elem) -> Optional[ViewDef]:
    """Parse a <ViewDef> XML element (from content.xml) into a ViewDef dataclass.

    Returns None and emits WARN for unrecognised shapes.
    This is the dataclass-level API; callers that only need a dict should
    use vcfops_extractor.extractor._parse_view_def_element() instead.
    """
    import xml.etree.ElementTree as ET

    view_id = elem.get("id", "")
    title = ""
    description = ""
    adapter_kind = ""
    resource_kind = ""
    data_type = "list"
    presentation = "list"
    columns: list[ViewColumn] = []

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
            columns = _parse_controls_to_columns(child)

    if not title:
        _warn(f"ViewDef {view_id} has no Title element")

    vd = ViewDef(
        id=view_id,
        name=title,
        description=description,
        adapter_kind=adapter_kind,
        resource_kind=resource_kind,
        columns=columns,
        data_type=data_type,
        presentation=presentation,
    )
    return vd


def _parse_controls_to_columns(controls_elem) -> list[ViewColumn]:
    """Parse <Controls> block into ViewColumn dataclasses."""
    columns: list[ViewColumn] = []

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
                        col = _parse_column_value_to_dataclass(val)
                        if col is not None:
                            columns.append(col)

    return columns


def _parse_column_value_to_dataclass(value_elem) -> Optional[ViewColumn]:
    """Parse a <Value> element into a ViewColumn dataclass."""

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

    # Normalise super metric column keys
    if attribute_key.startswith("Super Metric|sm_"):
        attr_yaml = attribute_key[len("Super Metric|"):]
    else:
        attr_yaml = attribute_key

    unit = props.get("preferredUnitId", "") or ""

    # Transformation
    transform = transform_list[0] if transform_list else "CURRENT"
    transformation: Optional[str] = None
    if transform and transform not in ("CURRENT", "NONE"):
        transformation = transform

    # Percentile
    percentile: Optional[int] = None
    p_raw = props.get("percentile")
    if p_raw is not None:
        try:
            percentile = int(p_raw)
        except ValueError:
            pass

    # Transform expression
    transform_expression: Optional[str] = props.get("transformExpression") or None

    # Color bounds
    def _parse_bound(key: str):
        v = props.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except ValueError:
            return v

    yellow = _parse_bound("yellowBound")
    orange = _parse_bound("orangeBound")
    red = _parse_bound("redBound")

    ascending_raw = props.get("ascendingRange")
    ascending: Optional[bool] = None
    if ascending_raw is not None:
        # Suppress ascending_range for property-match coloring (string-only red_bound
        # with no yellow/orange bounds).  This mirrors the forward renderer logic in
        # render.py which skips ascendingRange emission for this case, and the validator
        # which rejects ascending_range in this configuration.
        red_is_string = red is not None and not isinstance(red, (int, float))
        if not (red_is_string and yellow is None and orange is None):
            ascending = ascending_raw.lower() == "true"

    return ViewColumn(
        attribute=attr_yaml,
        display_name=display_name,
        unit=unit,
        transformation=transformation,
        percentile=percentile,
        transform_expression=transform_expression,
        yellow_bound=yellow,
        orange_bound=orange,
        red_bound=red,
        ascending_range=ascending,
    )


def parse_view_from_content_xml(xml_bytes: bytes, view_uuid: str) -> Optional[ViewDef]:
    """Find and parse a ViewDef by UUID from a content.xml byte string.

    Returns a ViewDef dataclass, or None with WARN if not found.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        _warn(f"failed to parse content.xml: {e}")
        return None

    view_uuid_lower = view_uuid.lower()
    for elem in root.iter("ViewDef"):
        if (elem.get("id") or "").lower() == view_uuid_lower:
            return parse_view_xml_element(elem)

    _warn(f"ViewDef id={view_uuid} not found in content.xml")
    return None


# ---------------------------------------------------------------------------
# Widget config reverse parsers (wire JSON -> dataclasses)
# ---------------------------------------------------------------------------

def _parse_metric_specs_from_wire(
    raw_metric: dict,
    widget_label: str,
    kind_lookup: dict[int, dict] | None = None,
) -> list[MetricSpec]:
    """Parse a config.metric object (resourceKindMetrics[] form) to MetricSpec list.

    ``kind_lookup`` is the entries.resourceKind[] index built by
    ``_build_kind_lookup()``.  When provided, the ``resourceKindId`` synthetic
    ref is resolved to real adapter_kind + resource_kind strings rather than
    falling back to VMWARE / resourceKindName.
    """
    specs: list[MetricSpec] = []
    if not raw_metric:
        return specs
    if kind_lookup is None:
        kind_lookup = {}
    for entry in (raw_metric.get("resourceKindMetrics") or []):
        metric_key = str(entry.get("metricKey") or "").strip()
        if not metric_key:
            continue
        rk_id_raw = str(entry.get("resourceKindId") or "").strip()
        ak, rk = _resolve_rk_id(
            rk_id_raw,
            kind_lookup,
            f"widget '{widget_label}' MetricSpec",
        )
        if ak is not None:
            # Resolved from synthetic ref — use the lookup values.
            adapter_kind = ak
            resource_kind = rk
        else:
            # Not a synthetic ref or no ref at all — fall back to resourceKindName.
            # adapter_kind cannot be recovered from the wire without the lookup;
            # retain VMWARE as the default for non-synthetic refs (e.g. live-instance
            # forms that embed the full kind string directly).
            resource_kind = str(entry.get("resourceKindName") or "").strip()
            adapter_kind = "VMWARE"
        color_method_raw = entry.get("colorMethod", 2)
        try:
            color_method = int(color_method_raw)
        except (TypeError, ValueError):
            color_method = 2
        yellow = entry.get("yellowBound")
        orange = entry.get("orangeBound")
        red = entry.get("redBound")
        specs.append(MetricSpec(
            adapter_kind=adapter_kind,
            resource_kind=resource_kind,
            metric_key=metric_key,
            metric_name=str(entry.get("metricName") or metric_key).strip(),
            unit_id=str(entry.get("metricUnitId") or "").strip() if entry.get("metricUnitId") else "",
            unit=str(entry.get("unit") or "").strip() if entry.get("unit") else "",
            color_method=color_method,
            yellow_bound=float(yellow) if yellow is not None else None,
            orange_bound=float(orange) if orange is not None else None,
            red_bound=float(red) if red is not None else None,
            label=str(entry.get("label") or "").strip(),
        ))
    return specs


def _parse_text_display_config(cfg: dict, dash_name: str, local_id: str) -> TextDisplayConfig:
    html = str(cfg.get("editorData") or cfg.get("locationUrl") or "<br>").strip()
    return TextDisplayConfig(html=html)


def _parse_scoreboard_config(
    cfg: dict,
    dash_name: str,
    local_id: str,
    kind_lookup: dict[int, dict] | None = None,
) -> ScoreboardConfig:
    specs = _parse_metric_specs_from_wire(cfg.get("metric") or {}, local_id, kind_lookup)
    if not specs:
        _warn(f"dashboard '{dash_name}': Scoreboard widget '{local_id}' has no parseable metrics")
    visual_theme = cfg.get("visualTheme", 8)
    try:
        visual_theme = int(visual_theme)
    except (TypeError, ValueError):
        visual_theme = 8
    show_sparkline = bool((cfg.get("showSparkline") or {}).get("showSparkline", False))
    period_length = cfg.get("periodLength") or None
    show_resource_name = bool((cfg.get("showResourceName") or {}).get("showResourceName", False))
    show_metric_name = bool((cfg.get("showMetricName") or {}).get("showMetricName", True))
    show_metric_unit = bool((cfg.get("showMetricUnit") or {}).get("showMetricUnit", True))
    box_columns_raw = cfg.get("boxColumns", 4)
    try:
        box_columns = int(box_columns_raw)
    except (TypeError, ValueError):
        box_columns = 4
    box_height_raw = cfg.get("boxHeight")
    box_height = float(box_height_raw) if box_height_raw is not None else None
    value_size_raw = cfg.get("valueSize", 24)
    try:
        value_size = int(value_size_raw)
    except (TypeError, ValueError):
        value_size = 24
    label_size_raw = cfg.get("labelSize", 12)
    try:
        label_size = int(label_size_raw)
    except (TypeError, ValueError):
        label_size = 12
    round_decimals_raw = cfg.get("roundDecimals")
    round_decimals = float(round_decimals_raw) if round_decimals_raw is not None else 1.0
    max_cell_count_raw = cfg.get("maxCellCount", 100)
    try:
        max_cell_count = int(max_cell_count_raw)
    except (TypeError, ValueError):
        max_cell_count = 100
    return ScoreboardConfig(
        metrics=specs,
        visual_theme=visual_theme,
        show_sparkline=show_sparkline,
        period_length=period_length,
        show_resource_name=show_resource_name,
        show_metric_name=show_metric_name,
        show_metric_unit=show_metric_unit,
        box_columns=box_columns,
        box_height=box_height,
        value_size=value_size,
        label_size=label_size,
        round_decimals=round_decimals,
        max_cell_count=max_cell_count,
    )


def _parse_metric_chart_config(
    cfg: dict,
    dash_name: str,
    local_id: str,
    kind_lookup: dict[int, dict] | None = None,
) -> MetricChartConfig:
    specs = _parse_metric_specs_from_wire(cfg.get("metric") or {}, local_id, kind_lookup)
    if not specs:
        _warn(f"dashboard '{dash_name}': MetricChart widget '{local_id}' has no parseable metrics")
    return MetricChartConfig(metrics=specs)


def _parse_health_chart_config(
    cfg: dict,
    dash_name: str,
    local_id: str,
    kind_lookup: dict[int, dict] | None = None,
) -> HealthChartConfig:
    metric_key = str(cfg.get("metricKey") or "").strip()
    metric_name = str(cfg.get("metricName") or metric_key).strip()
    metric_full_name = str(cfg.get("metricFullName") or metric_name).strip()
    rk_id = str(cfg.get("resourceKindId") or "").strip()
    context = f"dashboard '{dash_name}': HealthChart widget '{local_id}'"
    ak, rk = _resolve_rk_id(rk_id, kind_lookup or {}, context)
    if ak is not None:
        # Resolved from synthetic ref.
        adapter_kind = ak
        resource_kind = rk
    elif rk_id:
        # Non-synthetic form (e.g. "002006VMWAREVirtualMachine") — keep as-is.
        resource_kind = rk_id
        adapter_kind = "VMWARE"
    else:
        resource_kind = ""
        adapter_kind = "VMWARE"
    mode = str(cfg.get("mode") or "all").strip()
    depth = int(cfg.get("depth") or 1)
    chart_height = int(cfg.get("chartHeight") or 135)
    pagination_number = int(cfg.get("paginationNumber") or 15)
    sort_by_dir_raw = cfg.get("sortByDir") or {}
    if isinstance(sort_by_dir_raw, dict):
        sort_by_dir = str(sort_by_dir_raw.get("orderByDir") or "asc").strip()
    else:
        sort_by_dir = str(sort_by_dir_raw).strip() or "asc"
    yellow_bound = float(cfg.get("yellowBound") or -2)
    orange_bound = float(cfg.get("orangeBound") or -2)
    red_bound = float(cfg.get("redBound") or -2)
    show_resource_name_raw = cfg.get("showResourceName") or {}
    if isinstance(show_resource_name_raw, dict):
        show_resource_name = bool(show_resource_name_raw.get("showResourceName", True))
    else:
        show_resource_name = bool(show_resource_name_raw)
    return HealthChartConfig(
        adapter_kind=adapter_kind,
        resource_kind=resource_kind,
        metric_key=metric_key,
        metric_name=metric_name,
        metric_full_name=metric_full_name,
        mode=mode,
        depth=depth,
        chart_height=chart_height,
        pagination_number=pagination_number,
        sort_by_dir=sort_by_dir,
        yellow_bound=yellow_bound,
        orange_bound=orange_bound,
        red_bound=red_bound,
        show_resource_name=show_resource_name,
    )


def _parse_pareto_analysis_config(
    cfg: dict,
    dash_name: str,
    local_id: str,
    kind_lookup: dict[int, dict] | None = None,
) -> ParetoAnalysisConfig:
    raw_metric = cfg.get("metric") or {}
    metric_key = str(raw_metric.get("metricKey") or "").strip()
    metric_name = str(raw_metric.get("name") or cfg.get("metricName") or metric_key).strip()
    # resource kind from resourceKind[0].id — may be a synthetic ref.
    rk_list = cfg.get("resourceKind") or []
    resource_kind = ""
    adapter_kind = "VMWARE"
    if rk_list:
        rk_id = str((rk_list[0] or {}).get("id") or "").strip()
        context = f"dashboard '{dash_name}': ParetoAnalysis widget '{local_id}'"
        ak, rk = _resolve_rk_id(rk_id, kind_lookup or {}, context)
        if ak is not None:
            adapter_kind = ak
            resource_kind = rk
        elif rk_id:
            # Non-synthetic form — keep as-is.
            resource_kind = rk_id
    mode = str(cfg.get("mode") or "all").strip()
    bars_count = int(cfg.get("barsCount") or 10)
    top_option = str(cfg.get("topOption") or "metricsHighestUtilization").strip()
    bottom_n = bars_count if top_option == "metricsLowestUtilization" else 0
    top_n = bars_count if top_option != "metricsLowestUtilization" else 10
    depth = int(cfg.get("depth") or 10)
    regeneration_time = int(cfg.get("regenerationTime") or 15)
    round_decimals_raw = cfg.get("roundDecimals")
    round_decimals = float(round_decimals_raw) if round_decimals_raw is not None else 1.0
    return ParetoAnalysisConfig(
        adapter_kind=adapter_kind,
        resource_kind=resource_kind,
        metric_key=metric_key,
        metric_name=metric_name,
        mode=mode,
        top_n=top_n,
        bottom_n=bottom_n,
        top_option=top_option,
        depth=depth,
        regeneration_time=regeneration_time,
        round_decimals=round_decimals,
    )


def _parse_alert_list_config(cfg: dict, dash_name: str, local_id: str) -> AlertListConfig:
    criticality_raw = cfg.get("criticalityLevel") or [2, 3, 4]
    try:
        criticality = [int(c) for c in criticality_raw]
    except (TypeError, ValueError):
        criticality = [2, 3, 4]
    alert_types = [str(t).strip() for t in (cfg.get("type") or [])]
    status_raw = cfg.get("status") or []
    try:
        status = [int(s) for s in status_raw]
    except (TypeError, ValueError):
        status = []
    state = list(cfg.get("state") or [])
    alert_impact = [str(a).strip() for a in (cfg.get("alertImpact") or [])]
    alert_action = list(cfg.get("alertAction") or [])
    mode = str(cfg.get("mode") or "all").strip()
    depth = int(cfg.get("depth") or 1)
    return AlertListConfig(
        criticality=criticality,
        alert_types=alert_types,
        status=status,
        state=state,
        alert_impact=alert_impact,
        alert_action=alert_action,
        mode=mode,
        depth=depth,
    )


def _parse_problem_alerts_list_config(cfg: dict, dash_name: str, local_id: str) -> ProblemAlertsListConfig:
    impacted_badge = str(cfg.get("impactedBadge") or "health").strip()
    triggered_object_raw = cfg.get("triggeredObject") or {}
    if isinstance(triggered_object_raw, dict):
        triggered_object = str(triggered_object_raw.get("triggeredObject") or "children").strip()
    else:
        triggered_object = str(triggered_object_raw).strip() or "children"
    top_issues_limit = int(cfg.get("topIssuesDisplayLimit") or 0)
    return ProblemAlertsListConfig(
        impacted_badge=impacted_badge,
        triggered_object=triggered_object,
        top_issues_limit=top_issues_limit,
    )


def _parse_heatmap_config(
    cfg: dict,
    dash_name: str,
    local_id: str,
    kind_lookup: dict[int, dict] | None = None,
) -> HeatmapConfig:
    mode = str(cfg.get("mode") or "all").strip()
    depth = int(cfg.get("depth") or 10)
    tabs: list[HeatmapTab] = []
    for raw_tab in (cfg.get("configs") or []):
        name = str(raw_tab.get("name") or "").strip()
        rk_id = str(raw_tab.get("resourceKind") or "").strip()
        context = f"dashboard '{dash_name}': Heatmap widget '{local_id}' tab '{name}'"
        ak, rk = _resolve_rk_id(rk_id, kind_lookup or {}, context)
        if ak is not None:
            adapter_kind = ak
            resource_kind = rk
        elif rk_id:
            # Non-synthetic form — keep as-is.
            resource_kind = rk_id
            adapter_kind = "VMWARE"
        else:
            resource_kind = ""
            adapter_kind = "VMWARE"

        raw_cb = raw_tab.get("colorBy") or {}
        color_by_key = str(raw_cb.get("metricKey") or "").strip()
        color_by_label = str(raw_cb.get("value") or color_by_key).strip()

        raw_sb = raw_tab.get("sizeBy") or {}
        size_by_key_raw = raw_sb.get("metricKey")
        size_by_key = str(size_by_key_raw).strip() if size_by_key_raw else None
        size_by_label = str(raw_sb.get("value") or "").strip()

        raw_gb = raw_tab.get("groupBy") or {}
        group_by_kind = str(raw_gb.get("resourceKind") or "").strip()
        group_by_adapter = str(raw_gb.get("adapterKind") or "").strip()
        group_by_text = str(raw_gb.get("text") or "").strip()

        raw_color = raw_tab.get("color") or {}
        raw_thresholds = raw_color.get("thresholds") or {}
        max_value_raw = raw_color.get("maxValue")
        color = HeatmapColorThreshold(
            min_value=float(raw_color.get("minValue", 0)),
            max_value=float(max_value_raw) if max_value_raw is not None else None,
            values=list(raw_thresholds.get("values") or [0, 50, 100]),
            colors=list(raw_thresholds.get("colors") or ["#74B43B", "#ECC33E", "#DE3F30"]),
        )

        solid_coloring = bool(raw_tab.get("solidColoring", False))
        focus_on_groups = bool(raw_tab.get("focusOnGroups", True))

        tabs.append(HeatmapTab(
            name=name,
            adapter_kind=adapter_kind,
            resource_kind=resource_kind,
            color_by_key=color_by_key,
            color_by_label=color_by_label,
            size_by_key=size_by_key,
            size_by_label=size_by_label,
            group_by_adapter=group_by_adapter or adapter_kind,
            group_by_kind=group_by_kind,
            group_by_text=group_by_text,
            color=color,
            solid_coloring=solid_coloring,
            focus_on_groups=focus_on_groups,
        ))
    if not tabs:
        _warn(f"dashboard '{dash_name}': Heatmap widget '{local_id}' has no parseable configs/tabs")
    return HeatmapConfig(tabs=tabs, mode=mode, depth=depth)


# ---------------------------------------------------------------------------
# Dashboard JSON -> Dashboard dataclass (Phase 1: structural only)
# ---------------------------------------------------------------------------

# Widget types the forward renderer supports.
_SUPPORTED_WIDGET_TYPES = frozenset({
    "ResourceList", "View", "TextDisplay", "Scoreboard", "MetricChart",
    "HealthChart", "ParetoAnalysis", "AlertList", "ProblemAlertsList", "Heatmap",
})


def parse_dashboard_json(dash_json: dict, views_by_id: dict[str, ViewDef]) -> Dashboard:
    """Parse a dashboard.json widget graph into a Dashboard dataclass.

    ``dash_json`` is the dict from getDashboardConfig (or the entries in
    ``dashboards[]`` in the content-zip dashboard/dashboard.json).

    ``views_by_id`` maps view UUID -> ViewDef for View widget resolution.
    View widgets whose UUID is not in ``views_by_id`` are included with an
    empty view_name and a WARN (missing view reference).

    Widget types not in _SUPPORTED_WIDGET_TYPES emit WARN and are skipped
    (not included in the returned widget list).  This matches the "minimum
    viable shape" contract in render.py line 11.

    The ``locked``/``userId``/``lastUpdateUserId`` stamps added by the
    importer are stripped -- the packager re-adds them at build time.
    """
    # Strip folder prefix from name
    raw_name = dash_json.get("name") or ""
    name_path = dash_json.get("namePath") or ""
    if "/" in raw_name:
        parts = raw_name.split("/", 1)
        name_path = name_path or parts[0].strip()
        display_name = parts[1].strip()
    else:
        display_name = raw_name.strip()

    dash_id = str(dash_json.get("id") or "").strip()
    description = str(dash_json.get("description") or "").strip()
    shared = bool(dash_json.get("shared", True))

    # Build lookup tables from entries so widget parsers can resolve synthetic refs.
    # kind_lookup: entries.resourceKind[] — resolves "resourceKind:id:N_::_" refs
    #   used by ResourceList, Heatmap, Scoreboard, MetricChart, HealthChart,
    #   ParetoAnalysis widget configs.
    # resource_lookup: entries.resource[] — resolves "resource:id:N_::_" refs
    #   used by self-provider View and ProblemAlertsList pin configs.
    kind_lookup = _build_kind_lookup(dash_json)
    resource_lookup = _build_resource_lookup(dash_json)

    # Interactions
    interactions: list[Interaction] = []
    # widget-id -> local-id map built during widget parsing
    widget_id_to_local: dict[str, str] = {}

    raw_widgets = dash_json.get("widgets") or []
    widgets: list[Widget] = []

    # Build a views_by_uuid -> name map for View widget resolution
    views_by_uuid = {vd.id.lower(): vd for vd in views_by_id.values()}

    for seq, w in enumerate(raw_widgets):
        wtype = w.get("type") or ""
        if wtype not in _SUPPORTED_WIDGET_TYPES:
            _warn(
                f"dashboard '{display_name}': widget type '{wtype}' is not supported "
                "by the forward renderer; skipping (WARN only, not fatal)"
            )
            continue

        raw_id = str(w.get("id") or seq)
        # Use a sanitised short local_id
        local_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw_id)[:40] or f"widget_{seq}"

        grid = w.get("gridsterCoords") or {}
        coords = {
            "x": int(grid.get("x", 1)),
            "y": int(grid.get("y", 1)),
            "w": int(grid.get("w", 6)),
            "h": int(grid.get("h", 6)),
        }

        title = str(w.get("title") or "").strip()
        cfg = w.get("config") or {}

        view_name = ""
        resource_kinds: list[WidgetResourceKindRef] = []

        scoreboard_config = None
        metric_chart_config = None
        text_display_config = None
        health_chart_config = None
        pareto_analysis_config = None
        alert_list_config = None
        problems_alerts_list_config = None
        heatmap_config = None
        self_provider = bool((cfg.get("selfProvider") or {}).get("selfProvider", False))
        pin = None

        if wtype == "View":
            view_def_id = str(cfg.get("viewDefinitionId") or "").strip().lower()
            vd = views_by_uuid.get(view_def_id)
            if vd:
                view_name = vd.name
            else:
                _warn(
                    f"dashboard '{display_name}': View widget references "
                    f"viewDefinitionId={view_def_id!r} not in extracted views; "
                    "view_name will be empty"
                )
                view_name = view_def_id  # preserve UUID as best effort
            # Self-provider View widgets carry a pinned container resource in
            # config.resource.resourceId (a synthetic "resource:id:N_::_" ref).
            # Resolve it against entries.resource[] to recover adapter_kind +
            # resource_kind and emit a pin: block in the YAML.
            if self_provider:
                res_cfg = cfg.get("resource") or {}
                res_id_raw = str(res_cfg.get("resourceId") or "").strip() if isinstance(res_cfg, dict) else ""
                if res_id_raw:
                    context = f"dashboard '{display_name}': View widget '{local_id}'"
                    ak, rk = _resolve_res_id(res_id_raw, resource_lookup, context)
                    if ak is not None and ak and rk:
                        pin = WidgetResourceKindRef(adapter_kind=ak, resource_kind=rk)
                    elif ak is None:
                        # Not a synthetic ref — try to recover from resourceKindId or resourceName
                        # in the config.resource block (live-instance export may embed real values).
                        rk_from_cfg = str(res_cfg.get("resourceName") or "").strip()
                        if rk_from_cfg:
                            pin = WidgetResourceKindRef(adapter_kind="VMWARE", resource_kind=rk_from_cfg)
                        else:
                            _warn(
                                f"dashboard '{display_name}': self-provider View widget '{local_id}' "
                                f"has config.resource.resourceId={res_id_raw!r} which is not a "
                                "synthetic ref and has no resourceName fallback; pin will be omitted"
                            )
                else:
                    _warn(
                        f"dashboard '{display_name}': self-provider View widget '{local_id}' "
                        "has no config.resource.resourceId; pin will be omitted"
                    )

        elif wtype == "ResourceList":
            # Extract resource kinds from tagFilter.value.kind[].
            # Each element is a synthetic "resourceKind:id:N_::_" ref that maps
            # to entries.resourceKind[N] via kind_lookup.
            tag_filter = cfg.get("tagFilter") or {}
            tv = tag_filter.get("value") or {}
            kinds = tv.get("kind") or []
            seen_rk_keys: set[tuple[str, str]] = set()
            for k in kinds:
                context = f"dashboard '{display_name}': ResourceList widget '{local_id}'"
                ak, rk = _resolve_rk_id(str(k), kind_lookup, context)
                if ak is not None and (ak, rk) not in seen_rk_keys:
                    seen_rk_keys.add((ak, rk))
                    resource_kinds.append(WidgetResourceKindRef(
                        adapter_kind=ak,
                        resource_kind=rk,
                    ))
            # If kind[] was empty or had non-synthetic forms, also scan path[]
            # for entries like "/source/kind/kind:resourceKind:id:N_::_"
            if not resource_kinds:
                for p in (tag_filter.get("path") or []):
                    pm = re.search(r"kind:resourceKind:id:(\d+)_::_", p)
                    if pm:
                        idx = int(pm.group(1))
                        entry = kind_lookup.get(idx)
                        if entry:
                            key = (entry["adapter_kind"], entry["resource_kind"])
                            if key not in seen_rk_keys:
                                seen_rk_keys.add(key)
                                resource_kinds.append(WidgetResourceKindRef(
                                    adapter_kind=entry["adapter_kind"],
                                    resource_kind=entry["resource_kind"],
                                ))
                        else:
                            _warn(
                                f"dashboard '{display_name}': ResourceList widget '{local_id}' "
                                f"path ref index {idx} not present in entries.resourceKind[]"
                            )
            # Only WARN if we genuinely could not resolve any kinds AND
            # there were kinds/paths present to attempt resolution on.
            if not resource_kinds and (kinds or (tag_filter.get("path") or [])):
                _warn(
                    f"dashboard '{display_name}': ResourceList widget '{local_id}' "
                    "could not resolve any resource kind refs — "
                    "check that entries.resourceKind[] is populated"
                )

        elif wtype == "TextDisplay":
            text_display_config = _parse_text_display_config(cfg, display_name, local_id)

        elif wtype == "Scoreboard":
            scoreboard_config = _parse_scoreboard_config(cfg, display_name, local_id, kind_lookup)

        elif wtype == "MetricChart":
            metric_chart_config = _parse_metric_chart_config(cfg, display_name, local_id, kind_lookup)

        elif wtype == "HealthChart":
            health_chart_config = _parse_health_chart_config(cfg, display_name, local_id, kind_lookup)

        elif wtype == "ParetoAnalysis":
            pareto_analysis_config = _parse_pareto_analysis_config(cfg, display_name, local_id, kind_lookup)

        elif wtype == "AlertList":
            alert_list_config = _parse_alert_list_config(cfg, display_name, local_id)

        elif wtype == "ProblemAlertsList":
            problems_alerts_list_config = _parse_problem_alerts_list_config(cfg, display_name, local_id)
            # ProblemAlertsList can also be self-provider with a pinned container resource.
            # Extract pin from config.resource.resourceId the same way as View widgets.
            if self_provider and pin is None:
                res_cfg = cfg.get("resource") or {}
                res_id_raw = str(res_cfg.get("resourceId") or "").strip() if isinstance(res_cfg, dict) else ""
                if res_id_raw:
                    context = f"dashboard '{display_name}': ProblemAlertsList widget '{local_id}'"
                    ak, rk = _resolve_res_id(res_id_raw, resource_lookup, context)
                    if ak is not None and ak and rk:
                        pin = WidgetResourceKindRef(adapter_kind=ak, resource_kind=rk)
                    elif ak is None:
                        rk_from_cfg = str(res_cfg.get("resourceName") or "").strip()
                        if rk_from_cfg:
                            pin = WidgetResourceKindRef(adapter_kind="VMWARE", resource_kind=rk_from_cfg)

        elif wtype == "Heatmap":
            heatmap_config = _parse_heatmap_config(cfg, display_name, local_id, kind_lookup)

        widget = Widget(
            local_id=local_id,
            type=wtype,
            title=title,
            coords=coords,
            resource_kinds=resource_kinds,
            view_name=view_name,
            self_provider=self_provider,
            pin=pin,
            scoreboard_config=scoreboard_config,
            metric_chart_config=metric_chart_config,
            text_display_config=text_display_config,
            health_chart_config=health_chart_config,
            pareto_analysis_config=pareto_analysis_config,
            alert_list_config=alert_list_config,
            problems_alerts_list_config=problems_alerts_list_config,
            heatmap_config=heatmap_config,
            dashboard_name=display_name,
        )
        widgets.append(widget)
        widget_id_to_local[raw_id] = local_id

    # Interactions
    for ix in (dash_json.get("widgetInteractions") or []):
        provider_id = str(ix.get("widgetIdProvider") or "")
        receiver_id = str(ix.get("widgetIdReceiver") or "")
        ix_type = str(ix.get("type") or "resourceId")
        # Only include interactions where both widgets were included
        from_local = widget_id_to_local.get(provider_id)
        to_local = widget_id_to_local.get(receiver_id)
        if from_local and to_local:
            interactions.append(Interaction(
                from_local_id=from_local,
                to_local_id=to_local,
                type=ix_type,
            ))

    return Dashboard(
        id=dash_id,
        name=display_name,
        description=description,
        widgets=widgets,
        interactions=interactions,
        name_path=name_path or "",
        shared=shared,
    )
