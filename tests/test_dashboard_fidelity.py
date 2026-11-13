"""Dashboard fidelity fields (2026-11-12).

Synthetic fixtures only. Wire format:
knowledge/context/wire-formats/dashboard_fidelity_wire_format.md.

Each feature: a load + render test asserting the emitted wire value, and
negative tests for the load errors. The defaults group proves a widget with
none of the new fields renders exactly the historical keys, and the walker
group proves the two new metric surfaces reach every dependency walker.
"""
from __future__ import annotations

import dataclasses
import json
import sys
import warnings
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.dashboards.loader import (  # noqa: E402
    DASHBOARD_TIME_RANGES,
    DashboardValidationError,
    load_dashboard,
    widget_extra_metric_refs,
)
from vcfcf_core.dashboards.render import render_dashboards_bundle_json  # noqa: E402

DASH_ID = "6a1d2e3f-4b5c-4d6e-8f70-819a2b3c4d5e"
VIEW_ID = "0f1e2d3c-4b5a-4968-8776-655443322110"
OTHER_DASH = "11111111-2222-4333-8444-555555555555"
OTHER_WIDGET = "99999999-8888-4777-8666-555555555555"
SM_KEY = "Super Metric|sm_12345678-1234-4234-8234-123456789abc"


def _dash(widgets, **extra):
    return {"id": DASH_ID, "name": "Fidelity Probe", "description": "", "widgets": widgets, **extra}


def _load_one(p, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            d = load_dashboard(p, enforce_framework_prefix=False, **kw)
            d.validate({}, enforce_framework_prefix=False)
            return d
        except DashboardValidationError as exc:
            return exc


def _load(tmp_path, data, name="d.yaml"):
    """Load under both folder defaults the production callers pass: ""
    (third-party bundles, the corpus walkers) and the loader's own
    "VCF Content Factory" (factory validate, a factory bundle file, a pak's
    _load_bundled_content). Every fidelity case must come out the same under
    both, apart from the folder an absent name_path takes (Codex P2 on PR
    356: a test that only passes under the convenient default hides a pak
    failure)."""
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    bundle, production = _load_one(p, default_name_path=""), _load_one(p)
    if isinstance(bundle, Exception) or isinstance(production, Exception):
        assert type(bundle) is type(production) and str(bundle) == str(production), (bundle, production)
        raise bundle
    if not isinstance(data.get("name_path"), str):
        assert bundle.name_path == "" and production.name_path == "VCF Content Factory"
        production = dataclasses.replace(production, name_path="")
    assert production == bundle
    return bundle


def _render(tmp_path, data):
    d = _load(tmp_path, data)
    return d, json.loads(render_dashboards_bundle_json([d], {}, "0", known_dashboards=[d]))


def _widget(doc, i=0):
    return doc["dashboards"][0]["widgets"][i]


def _view(**kw):
    return {"id": "v", "type": "View", "title": "V", "coords": {"x": 1, "y": 1, "w": 6, "h": 4},
            "view": VIEW_ID, **kw}


def _sb(metrics=None, **kw):
    return {"id": "s", "type": "Scoreboard", "title": "S", "coords": {"x": 1, "y": 1, "w": 6, "h": 3},
            "metrics": metrics or [{"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                                    "metric_key": "cpu|usage_average", "metric_name": "CPU"}], **kw}


def _hc(**kw):
    return {"id": "h", "type": "HealthChart", "title": "H", "coords": {"x": 1, "y": 1, "w": 6, "h": 4},
            "adapter_kind": "VMWARE", "resource_kind": "HostSystem", "metric_key": "cpu|usage_average", **kw}


def _pareto(**kw):
    return {"id": "p", "type": "ParetoAnalysis", "title": "P", "coords": {"x": 1, "y": 1, "w": 6, "h": 4},
            "adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource",
            "metric_key": "cpu|demandmhz", "metric_name": "CPU|Demand", **kw}


def _heat(tab=None, **kw):
    t = {"name": "Tab", "adapter_kind": "VMWARE", "resource_kind": "VirtualMachine",
         "color_by": {"metric_key": "cpu|usage_average", "label": "CPU"},
         "group_by": {"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource", "text": "Cluster"}}
    t.update(tab or {})
    return {"id": "m", "type": "Heatmap", "title": "M", "coords": {"x": 1, "y": 1, "w": 6, "h": 6},
            "configs": [t], **kw}


def _rra(**kw):
    return {"id": "r", "type": "ResourceRelationshipAdvanced", "title": "R",
            "coords": {"x": 1, "y": 1, "w": 4, "h": 4}, **kw}


# --- dashboard level -------------------------------------------------------

@pytest.mark.parametrize("value", sorted(DASHBOARD_TIME_RANGES))
def test_time_range_renders_the_product_state(tmp_path, value):
    _, doc = _render(tmp_path, _dash([_view()], time_range=value))
    states = doc["dashboards"][0]["states"]
    assert states == [{"key": f"permDashboardTime_dashboard_{DASH_ID}", "value": DASHBOARD_TIME_RANGES[value]}]


def test_time_range_last7days_wire_value_is_the_product_bytes(tmp_path):
    _, doc = _render(tmp_path, _dash([_view()], time_range="last7Days"))
    assert doc["dashboards"][0]["states"][0]["value"] == \
        "o%3AdateRange%3Ds%253Alast7Days%5EdateRangeText%3Ds%253A7D"


@pytest.mark.parametrize("bad", ["last8Days", "7D", "custom"])
def test_time_range_rejects_unexported_values(tmp_path, bad):
    with pytest.raises(DashboardValidationError, match="time_range"):
        _load(tmp_path, _dash([_view()], time_range=bad))


def test_dashboard_level_fields_render(tmp_path):
    _, doc = _render(tmp_path, _dash(
        [_view()], disabled=True, edit_allowed=True, doc_center_key="vcom_522",
        column_proportion="1-1", column_count=0, omit=["temporary", "widget_interactions"],
    ))
    db = doc["dashboards"][0]
    assert db["disabled"] is True and db["editAllowed"] is True and db["docCenterKey"] == "vcom_522"
    assert db["columnProportion"] == "1-1" and db["columnCount"] == 0
    assert "temporary" not in db and "widgetInteractions" not in db


def test_name_path_omit_and_folder_in_name(tmp_path):
    _, doc = _render(tmp_path, _dash([_view()], name_path="", omit=["name_path"]))
    assert "namePath" not in doc["dashboards"][0] and doc["dashboards"][0]["name"] == "Fidelity Probe"
    # name_path: "" alone is no folder too, with the key kept.
    _, doc = _render(tmp_path, _dash([_view()], name_path=""))
    assert doc["dashboards"][0]["namePath"] == "" and doc["dashboards"][0]["name"] == "Fidelity Probe"
    _, doc = _render(tmp_path, _dash([_view()], name_path="Folder", omit=["folder_in_name"]))
    assert doc["dashboards"][0]["name"] == "Fidelity Probe"
    assert doc["dashboards"][0]["namePath"] == "Folder"


@pytest.mark.parametrize("extra,match", [
    ({"disabled": "yes"}, "disabled must be a bool"),
    ({"edit_allowed": False}, "edit_allowed accepts only true"),
    ({"doc_center_key": "help_1"}, "doc_center_key"),
    ({"column_proportion": "2-1"}, "column_proportion"),
    ({"column_count": 7}, "column_count"),
    ({"omit": ["shared"]}, "not supported here"),
    ({"omit": ["name_path"], "name_path": "Folder"}, "omit name_path needs an empty folder"),
    ({"omit": ["name_path"]}, "omit name_path needs an empty folder"),
    ({"omit": ["name_path"], "name_path": None}, "omit name_path needs an empty folder"),
    ({"omit": ["folder_in_name"]}, "omit folder_in_name needs a name_path"),
    ({"omit": ["folder_in_name"], "name_path": ""}, "omit folder_in_name needs a name_path"),
    ({"omit": ["folder_in_name", "name_path"], "name_path": ""}, "together is meaningless"),
    ({"omit": ["widget_interactions"], "interactions": [{"from": "v", "to": "v"}]}, "contradicts interactions"),
])
def test_dashboard_level_negatives(tmp_path, extra, match):
    with pytest.raises(DashboardValidationError, match=match):
        _load(tmp_path, _dash([_view()], **extra))


# --- widget common: description, title_localized, collapsed, ui ------------

def test_description_and_title_localized(tmp_path):
    _, doc = _render(tmp_path, _dash([_view(description="Why", title_localized="V (loc)")]))
    cfg = _widget(doc)["config"]
    assert cfg["description"] == "Why" and cfg["titleLocalized"] == "V (loc)"


def test_collapsed_on_an_evidenced_type(tmp_path):
    _, doc = _render(tmp_path, _dash([_sb(collapsed=True)]))
    assert _widget(doc)["collapsed"] is True


def test_collapsed_rejected_on_an_unevidenced_type(tmp_path):
    with pytest.raises(DashboardValidationError, match="only supported on Section"):
        _load(tmp_path, _dash([_heat(collapsed=True)]))


def test_ui_states_compose_the_key_and_expand_self(tmp_path):
    d, doc = _render(tmp_path, _dash([_view(ui={"states": [
        {"key": "perm_toolbarVisible_", "value": "b%3A0"},
        {"key": "permTableView_", "value": "o%3Acolumns%3Da%253Ao%25253Aid%25253Ds%2525253ApermTableView_{self}-column-0"},
    ]})]))
    w = _widget(doc)
    own = f"widget_{DASH_ID}_{d.widgets[0].widget_id}"
    assert w["states"][0] == {"value": "b%3A0", "key": f"perm_toolbarVisible_{own}"}
    assert w["states"][1]["value"].endswith(f"permTableView_{own}-column-0")


@pytest.mark.parametrize("ui,match", [
    ({"states": [{"key": "permResGrid_", "value": "b%3A0"}]}, "not a View state"),
    ({"states": [{"key": "perm_toolbarVisible_", "value": "b:0"}]}, "URL-encoded"),
    ({"states": [{"key": "perm_toolbarVisible_", "value": "b%3A0"}, {"key": "perm_toolbarVisible_", "value": "b%3A1"}]}, "twice"),
    ({"height": -1}, "ui.height"),
    ({"state": "x"}, "ui.state accepts only"),
    ({"tab_id": False}, "accepts only true"),
    ({"legacy_xy": {"x": 1}}, "legacy_xy"),
    ({"view_type": "PIE"}, "view_type accepts only LIST"),
    ({"undefined": []}, "not supported on View"),
    ({"custom_filter_mode": "tagPicker"}, "not seen on View"),
    ({"bogus": 1}, "not supported on View"),
])
def test_ui_negatives(tmp_path, ui, match):
    with pytest.raises(DashboardValidationError, match=match):
        _load(tmp_path, _dash([_view(ui=ui)]))


def test_ui_flags_render(tmp_path):
    d, doc = _render(tmp_path, _dash([_view(ui={
        "height": 324, "state": "", "tab_id": True, "widget_id": True, "config_key": True,
        "legacy_xy": {"x": 1, "y": 2}, "view_type": "LIST"})]))
    w = _widget(doc)
    assert w["height"] == 324 and w["state"] == "" and w["tabId"] == DASH_ID
    assert (w["x"], w["y"]) == (1, 2)
    assert w["config"]["widgetId"] == d.widgets[0].widget_id
    assert w["config"]["key"] == "View" and w["config"]["viewType"] == "LIST"


def test_config_key_is_the_wire_type(tmp_path):
    av = {"id": "a", "type": "AlertVolume", "title": "A", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
          "ui": {"config_key": True}}
    _, doc = _render(tmp_path, _dash([av]))
    assert _widget(doc)["config"]["key"] == "IntSummaryAlertVolume"


def test_ui_states_join_a_column_preset_state(tmp_path):
    rl = {"id": "l", "type": "ResourceList", "title": "L", "coords": {"x": 1, "y": 1, "w": 6, "h": 4},
          "resource_kinds": [{"adapter_kind": "VMWARE", "resource_kind": "HostSystem"}],
          "column_preset": "name-only", "ui": {"states": [{"key": "perm_toolbarVisible_", "value": "b%3A1"}]}}
    _, doc = _render(tmp_path, _dash([rl]))
    keys = [s["key"] for s in _widget(doc)["states"]]
    assert keys[0].startswith("permResGrid_widget_") and keys[1].startswith("perm_toolbarVisible_widget_")
    rl["ui"] = {"states": [{"key": "permResGrid_", "value": "b%3A1"}]}
    with pytest.raises(DashboardValidationError, match="contradicts column_preset"):
        _load(tmp_path, _dash([rl]))


def test_view_type_rejected_beside_a_non_list_factory_view(tmp_path):
    from types import SimpleNamespace
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump(_dash([{**_view(ui={"view_type": "LIST"}), "view": "Trend V"}])))
    d = load_dashboard(p, enforce_framework_prefix=False)
    with pytest.raises(DashboardValidationError, match="names a trend view"):
        d.validate({"Trend V": SimpleNamespace(data_type="trend", usage=None)}, enforce_framework_prefix=False)


def test_healthchart_undefined_and_custom_filter_mode(tmp_path):
    _, doc = _render(tmp_path, _dash([_hc(ui={"undefined": [{"id": "percent", "name": "%"}],
                                             "custom_filter_mode": "tagPicker"})]))
    cfg = _widget(doc)["config"]
    assert cfg["undefined"] == [{"id": "percent", "name": "%"}]
    assert cfg["customFilter"]["filterMode"] == "tagPicker"


# --- View --------------------------------------------------------------------

def test_view_traversal_specs(tmp_path):
    _, doc = _render(tmp_path, _dash([_view(
        traversal_spec_id="", self_provider=True,
        pin={"adapter_kind": "VMWARE", "resource_kind": "vSphere World",
             "traversal_spec": "vSphere Hosts and Clusters-VMWARE-vSphere World"})]))
    cfg = _widget(doc)["config"]
    assert cfg["traversalSpecId"] == ""
    assert cfg["resource"]["traversalSpecId"] == "vSphere Hosts and Clusters-VMWARE-vSphere World"


def test_pin_traversal_spec_needs_a_self_provider_view(tmp_path):
    with pytest.raises(DashboardValidationError, match="self_provider View"):
        _load(tmp_path, _dash([_view(pin={"adapter_kind": "VMWARE", "resource_kind": "vSphere World",
                                          "traversal_spec": "x"})]))
    with pytest.raises(DashboardValidationError, match="only rendered on View"):
        _load(tmp_path, _dash([_hc(traversal_spec_id="")]))


# --- Scoreboard / MetricChart ------------------------------------------------

def test_scoreboard_fields(tmp_path):
    _, doc = _render(tmp_path, _dash([_sb(old_metric_values=False, layout_mode="fixedSize",
                                          visual_theme=8, show_remaining=False, show_percent_text=False,
                                          focus_on_percent=False, ui={"gauge_switches": True})]))
    cfg = _widget(doc)["config"]
    assert cfg["oldMetricValues"] is False and cfg["mode"] == {"layoutMode": "fixedSize"}
    assert cfg["showRemaining"] is False and "focusOnPercent" in cfg


def test_gauge_switches_flag_rejected_on_a_gauge(tmp_path):
    with pytest.raises(DashboardValidationError, match="non-gauge"):
        _load(tmp_path, _dash([_sb(visual_theme=9, ui={"gauge_switches": True})]))


def test_scoreboard_pin_resource(tmp_path):
    _, doc = _render(tmp_path, _dash([_sb(self_provider=True, pin_resource=True,
                                          pin={"adapter_kind": "VMWARE", "resource_kind": "vSphere World"})]))
    cfg = _widget(doc)["config"]
    assert cfg["resource"] == [{"name": "vSphere World", "id": "resource:id:0_::_"}]
    assert doc["entries"]["resource"][0]["name"] == "vSphere World"


@pytest.mark.parametrize("kw", [
    {"pin_resource": True},
    {"pin_resource": True, "pin": {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"}},
    {"pin_resource": "yes", "self_provider": True,
     "pin": {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"}},
])
def test_scoreboard_pin_resource_negatives(tmp_path, kw):
    with pytest.raises(DashboardValidationError, match="pin_resource"):
        _load(tmp_path, _dash([_sb(**kw)]))


def test_scoreboard_pin_without_pin_resource_keeps_historical_output(tmp_path):
    _, doc = _render(tmp_path, _dash([_sb(self_provider=True,
                                          pin={"adapter_kind": "VMWARE", "resource_kind": "vSphere World"})]))
    assert _widget(doc)["config"]["resource"] == []
    assert "resource" not in doc["entries"]


def test_metric_entry_fields_and_omit(tmp_path):
    m = {"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource", "metric_key": "cpu|usage_average",
         "metric_name": "CPU", "link": "/vcf-operations/ui/operate/dashboards/dashboards;tabId=" + OTHER_DASH,
         "label_localized": "", "label_orig": "", "metric_unit": "Auto", "def_unit": "%",
         "resource_kind_name": "Cluster Compute Resource", "unit_id": -1, "unit": "",
         "omit": ["label", "max_value", "handle_old_coloring"]}
    _, doc = _render(tmp_path, _dash([_sb([m])]))
    e = _widget(doc)["config"]["metric"]["resourceKindMetrics"][0]
    assert e["link"].endswith(OTHER_DASH) and e["labelLocalized"] == "" and e["labelOrig"] == ""
    assert e["metricUnit"] == "Auto" and e["defUnit"] == "%" and e["resourceKindName"] == "Cluster Compute Resource"
    assert e["metricUnitId"] == -1 and e["unit"] == ""
    assert not {"label", "maxValue", "handleOldColoring"} & set(e)


def test_metric_omit_unit_and_link(tmp_path):
    m = {"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "metric_key": "k", "omit": ["unit", "link"]}
    _, doc = _render(tmp_path, _dash([{**_sb([m]), "type": "MetricChart"}]))
    e = _widget(doc)["config"]["metric"]["resourceKindMetrics"][0]
    assert not {"unit", "metricUnitId", "link"} & set(e)


@pytest.mark.parametrize("m,match", [
    ({"label": "L", "omit": ["label"]}, "omit label contradicts"),
    ({"max_value": 5, "omit": ["max_value"]}, "omit max_value contradicts"),
    ({"unit": "", "omit": ["unit"]}, "omit unit contradicts"),
    ({"link": "", "omit": ["link"]}, "omit link contradicts"),
    ({"omit": ["color_method"]}, "not supported here"),
    ({"link": 5}, "link must be a string"),
])
def test_metric_entry_negatives(tmp_path, m, match):
    base = {"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "metric_key": "k"}
    with pytest.raises(DashboardValidationError, match=match):
        _load(tmp_path, _dash([_sb([{**base, **m}])]))


def test_string_bounds_on_a_string_metric(tmp_path):
    m = {"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource", "metric_key": "configuration|drsconfig|enabled",
         "is_string_metric": True, "color_method": 0, "yellow_bound": "1", "orange_bound": "1", "red_bound": "false"}
    _, doc = _render(tmp_path, _dash([_sb([m])]))
    e = _widget(doc)["config"]["metric"]["resourceKindMetrics"][0]
    assert (e["yellowBound"], e["orangeBound"], e["redBound"]) == ("1", "1", "false")


@pytest.mark.parametrize("m,match", [
    ({"yellow_bound": "1", "orange_bound": "1", "red_bound": "false"}, "need is_string_metric"),
    ({"is_string_metric": True, "yellow_bound": 1, "orange_bound": "1", "red_bound": "false"}, "not a mix"),
])
def test_string_bound_negatives(tmp_path, m, match):
    base = {"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "metric_key": "k", "color_method": 0}
    with pytest.raises(DashboardValidationError, match=match):
        _load(tmp_path, _dash([_sb([{**base, **m}])]))


def test_metric_chart_refresh_content(tmp_path):
    _, doc = _render(tmp_path, _dash([{**_sb(), "type": "MetricChart", "refresh_content": False}]))
    assert _widget(doc)["config"]["refreshContent"] == {"refreshContent": False}


@pytest.mark.parametrize("omit", [["sub_mode"]])
def test_scoreboard_omit_sub_mode(tmp_path, omit):
    _, doc = _render(tmp_path, _dash([_sb(omit=omit)]))
    assert "subMode" not in _widget(doc)["config"]["metric"]


# --- HealthChart -------------------------------------------------------------

def test_healthchart_relationship_and_tag_filter(tmp_path):
    _, doc = _render(tmp_path, _dash([_hc(relationship_mode="children", tag_filter={
        "resource_kinds": [{"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource"}],
        "states": ["2"], "statuses": ["4"]})]))
    cfg = _widget(doc)["config"]
    assert cfg["relationshipMode"] == {"relationshipMode": -1}
    kinds = {e["internalId"]: e["resourceKindKey"] for e in doc["entries"]["resourceKind"]}
    (k,) = cfg["tagFilter"]["value"]["kind"]
    assert kinds[k] == "ClusterComputeResource"
    assert cfg["tagFilter"]["path"] == [f"/source/kind/kind:{k}", "/source/state/state:2", "/source/status/status:4"]
    assert cfg["tagFilter"]["value"]["state"] == ["2"] and cfg["tagFilter"]["value"]["status"] == ["4"]


@pytest.mark.parametrize("kw,match", [
    ({"relationship_mode": "parents"}, "accepts only children"),
    ({"tag_filter": {"states": ["3"]}}, "only \\['2'\\]"),
    ({"tag_filter": {}}, "at least one"),
    ({"tag_filter": None}, "null is not supported"),
    ({"tag_filter": {"kinds": []}}, "unknown key"),
])
def test_healthchart_negatives(tmp_path, kw, match):
    with pytest.raises(DashboardValidationError, match=match):
        _load(tmp_path, _dash([_hc(**kw)]))


# --- ParetoAnalysis ----------------------------------------------------------

def test_pareto_fields(tmp_path):
    _, doc = _render(tmp_path, _dash([_pareto(
        refresh_content=False, relationship_mode="children", max_value=100, metric_label="Demand",
        metric_unit={"id": "percent", "name": "%"}, yellow_bound=70, orange_bound=80, red_bound=90,
        top_option="percentile", percentile_value=99,
        additional_columns=[{"metric_key": "summary|total_number_vms", "metric_name": "Summary|VMs", "label": "VMs"},
                            {"metric_key": "summary|total_number_hosts", "metric_name": "Hosts", "label": "ESXi",
                             "adapter_kind": "VMWARE", "resource_kind": "Datacenter"}])]))
    cfg = _widget(doc)["config"]
    assert cfg["refreshContent"] == {"refreshContent": False}
    assert cfg["relationshipMode"] == {"relationshipMode": -1}
    assert cfg["maxValue"] == 100 and cfg["metricName"] == "Demand" and cfg["metric"]["name"] == "CPU|Demand"
    assert cfg["metricUnit"] == {"metricUnitId": "percent", "metricUnitName": "%"}
    assert (cfg["yellowBound"], cfg["orangeBound"], cfg["redBound"]) == (70, 80, 90)
    assert cfg["percentileValue"] == 99 and cfg["topOption"] == "percentile"
    kinds = {e["internalId"]: e["resourceKindKey"] for e in doc["entries"]["resourceKind"]}
    cols = cfg["additionalColumns"]
    assert [c["boxLabel"] for c in cols] == ["VMs", "ESXi"]
    assert kinds[cols[0]["resourceKindId"]] == "ClusterComputeResource"
    assert kinds[cols[1]["resourceKindId"]] == "Datacenter"


def test_pareto_max_value_null_is_emitted(tmp_path):
    _, doc = _render(tmp_path, _dash([_pareto(max_value=None)]))
    assert "maxValue" in _widget(doc)["config"] and _widget(doc)["config"]["maxValue"] is None


@pytest.mark.parametrize("kw,match", [
    ({"yellow_bound": 1}, "all three together"),
    ({"percentile_value": 99}, "needs top_option: percentile"),
    ({"top_option": "percentile", "percentile_value": 0}, "percentile_value"),
    ({"metric_unit": {"id": "percent"}}, "metric_unit"),
    ({"max_value": "100"}, "max_value"),
    ({"refresh_content": "no"}, "refresh_content"),
    ({"additional_columns": [{"metric_name": "x"}]}, "additional_columns"),
])
def test_pareto_negatives(tmp_path, kw, match):
    with pytest.raises(DashboardValidationError, match=match):
        _load(tmp_path, _dash([_pareto(**kw)]))


# --- Heatmap -----------------------------------------------------------------

def test_heatmap_fields(tmp_path):
    _, doc = _render(tmp_path, _dash([_heat(
        tab={"name_localized": "Tab", "name_orig": "Tab", "model_id": True, "filter_mode": "customFilter",
             "tag_filter": {"resource_kinds": [{"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"}]},
             "group_by": {"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource",
                          "text": "Cluster Compute Resource", "parent_text": "vCenter Adapter"},
             "custom_filter": [{"adapter_kind": "VMWARE", "resource_kind": "Datastore", "conditions": [
                 {"filter_type": "properties", "metric_key": "summary|isLocal", "metric_name": "Summary|Is Local",
                  "condition": "EQUALS", "value": "false", "string_metric": True, "metric_unit": None}]}],
             "omit": ["group_by_kind_keys", "color_min_value"]},
        relationship_mode="children")]))
    cfg = _widget(doc)["config"]
    tab = cfg["configs"][0]
    assert cfg["relationshipMode"] == {"relationshipMode": -1}
    assert tab["nameLocalized"] == "Tab" and tab["nameOrig"] == "Tab" and tab["id"].startswith("extModel")
    assert tab["filterMode"] == "customFilter" and tab["tagFilter"]["value"]["kind"]
    assert tab["groupBy"]["parentText"] == "vCenter Adapter"
    assert "adapterKind" not in tab["groupBy"] and "resourceKind" not in tab["groupBy"]
    assert "minValue" not in tab["color"]
    (f,) = tab["customFilter"]["filter"]
    assert f["resourceKind"] == f["resourceKindId"] == "002006VMWAREDatastore"
    assert f["filterTypes"][0]["metricValue"] == {"isStringMetric": True, "value": "false"}


def test_heatmap_selected_tab_and_null_filters(tmp_path):
    second = {"name": "Two", "adapter_kind": "VMWARE", "resource_kind": "HostSystem",
              "color_by": {"metric_key": "cpu|usage_average"}, "custom_filter": None, "omit": ["tag_filter"]}
    w = _heat(selected_tab=1)
    w["configs"].append(second)
    _, doc = _render(tmp_path, _dash([w]))
    cfg = _widget(doc)["config"]
    assert cfg["value"] == 1
    assert cfg["configs"][1]["customFilter"] is None and "tagFilter" not in cfg["configs"][1]


@pytest.mark.parametrize("tab,kw,match", [
    ({"filter_mode": "other"}, {}, "filter_mode"),
    ({"model_id": False}, {}, "model_id accepts only true"),
    ({"omit": ["tag_filter"], "tag_filter": {"states": ["2"]}}, {}, "contradicts tag_filter"),
    ({"omit": ["custom_filter"], "custom_filter": None}, {}, "contradicts custom_filter"),
    ({"omit": ["group_by_kind_keys"], "group_by": {}}, {}, "group_by_kind_keys needs"),
    ({"custom_filter": [{"adapter_kind": "VMWARE", "resource_kind": "Datastore", "conditions": [
        {"filter_type": "properties", "metric_key": "k", "condition": "LIKE", "value": "x",
         "string_metric": True}]}]}, {}, "condition must be one of"),
    ({}, {"selected_tab": 3}, "selected_tab"),
    ({}, {"relationship_mode": "self"}, "accepts only children"),
])
def test_heatmap_negatives(tmp_path, tab, kw, match):
    with pytest.raises(DashboardValidationError, match=match):
        _load(tmp_path, _dash([_heat(tab=tab, **kw)]))


# --- ResourceRelationshipAdvanced / AlertList / Section ----------------------

def test_rra_fields(tmp_path):
    _, doc = _render(tmp_path, _dash([_rra(tag_filter=None, omit=["pagination_number", "select_first_row"],
                                           ui={"blank_relationship_mode": True, "visual_theme_false": True})]))
    cfg = _widget(doc)["config"]
    assert cfg["tagFilter"] is None and "paginationNumber" not in cfg and "selectFirstRow" not in cfg
    assert cfg["relationshipMode"] == "" and cfg["visualTheme"] is False


@pytest.mark.parametrize("kw,match", [
    ({"tag_filter": {"states": ["2"]}}, "only tag_filter: null"),
    ({"tag_filter": None, "resource_relationship_advanced": {"resource_kinds": [
        {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"}]}}, "contradicts resource_kinds"),
    ({"omit": ["select_first_row"], "select_first_row": True}, "contradicts select_first_row"),
])
def test_rra_negatives(tmp_path, kw, match):
    with pytest.raises(DashboardValidationError, match=match):
        _load(tmp_path, _dash([_rra(**kw)]))


def test_alertlist_omit_alert_definitions(tmp_path):
    al = {"id": "a", "type": "AlertList", "title": "A", "coords": {"x": 1, "y": 1, "w": 4, "h": 4}}
    _, doc = _render(tmp_path, _dash([{**al, "omit": ["alert_definitions"]}]))
    assert "alertDefinitions" not in _widget(doc)["config"]
    with pytest.raises(DashboardValidationError, match="contradicts alert_definitions"):
        _load(tmp_path, _dash([{**al, "omit": ["alert_definitions"], "alert_definitions": ["AlertDefinition-x"]}]))


def test_section_description_and_widget_id(tmp_path):
    sec = {"id": "sec", "type": "Section", "title": "HEAD", "coords": {"x": 1, "y": 1},
           "description": "About this row", "ui": {"widget_id": True}}
    d, doc = _render(tmp_path, _dash([sec, {**_view(), "coords": {"x": 1, "y": 2, "w": 6, "h": 4}}]))
    cfg = _widget(doc)["config"]
    assert cfg["description"] == "About this row" and cfg["widgetId"] == d.widgets[0].widget_id


# --- navigations -------------------------------------------------------------

def test_navigation_to_a_foreign_dashboard_widget(tmp_path):
    d, doc = _render(tmp_path, _dash([_view(navigations=[{"dashboard_id": OTHER_DASH, "widget_ids": [OTHER_WIDGET]}])]))
    navs = doc["dashboards"][0]["dashboardNavigations"]
    assert navs == {d.widgets[0].widget_id: [
        {"id": OTHER_DASH, "widgets": [{"interactionType": "resourceId", "id": OTHER_WIDGET}]}]}


def test_ui_empty_navigations(tmp_path):
    d, doc = _render(tmp_path, _dash([_view(ui={"empty_navigations": True})]))
    assert doc["dashboards"][0]["dashboardNavigations"] == {d.widgets[0].widget_id: []}
    # `navigations: []` keeps its historical meaning (no entry).
    _, doc = _render(tmp_path, _dash([_view(navigations=[])]))
    assert doc["dashboards"][0]["dashboardNavigations"] == {}
    with pytest.raises(DashboardValidationError, match="contradicts navigations"):
        _load(tmp_path, _dash([_view(ui={"empty_navigations": True},
                                     navigations=[{"dashboard_id": OTHER_DASH}])]))


@pytest.mark.parametrize("nav,match", [
    ({"dashboard": "Fidelity Probe", "widget_ids": [OTHER_WIDGET]}, "only for a dashboard_id target"),
    ({"dashboard_id": OTHER_DASH, "widget_ids": ["w1"]}, "widget_ids must be a list of widget UUIDs"),
])
def test_navigation_negatives(tmp_path, nav, match):
    with pytest.raises(DashboardValidationError, match=match):
        _load(tmp_path, _dash([_view(navigations=[nav])]))


# --- omit vocabulary ---------------------------------------------------------

@pytest.mark.parametrize("w", [_view(omit=["sub_mode"]), _hc(omit=["alert_definitions"])])
def test_widget_omit_is_per_type(tmp_path, w):
    with pytest.raises(DashboardValidationError, match="not supported here"):
        _load(tmp_path, _dash([w]))


# --- defaults ----------------------------------------------------------------

def test_no_fidelity_field_adds_no_key(tmp_path):
    """A widget of each touched type with no new field emits none of the new keys."""
    _, doc = _render(tmp_path, _dash([
        _view(), {**_sb(), "coords": {"x": 1, "y": 5, "w": 6, "h": 3}},
        {**_hc(), "coords": {"x": 7, "y": 1, "w": 6, "h": 4}},
        {**_pareto(), "coords": {"x": 7, "y": 5, "w": 6, "h": 4}},
        {**_heat(), "coords": {"x": 1, "y": 9, "w": 6, "h": 6}},
        {**_rra(), "coords": {"x": 7, "y": 9, "w": 6, "h": 4}},
    ]))
    db = doc["dashboards"][0]
    assert db["states"] == [] and db["disabled"] is False and "editAllowed" not in db
    new_keys = {"description", "titleLocalized", "widgetId", "key", "viewType", "undefined"}
    for w in db["widgets"]:
        assert not new_keys & set(w["config"]), w["type"]
        assert w["height"] == 600 and "states" not in w and "tabId" not in w and "state" not in w
    by_type = {w["type"]: w["config"] for w in db["widgets"]}
    assert by_type["View"]["traversalSpecId"] is None
    assert by_type["Scoreboard"]["oldMetricValues"] is True
    assert "showRemaining" not in by_type["Scoreboard"]
    assert by_type["HealthChart"]["relationshipMode"] == {"relationshipMode": 0}
    assert by_type["HealthChart"]["tagFilter"] is None
    assert by_type["ParetoAnalysis"]["relationshipMode"] == {"relationshipMode": [-1, 0]}
    assert by_type["ParetoAnalysis"]["refreshContent"] == {"refreshContent": True}
    assert "maxValue" not in by_type["ParetoAnalysis"] and "yellowBound" not in by_type["ParetoAnalysis"]
    assert by_type["ParetoAnalysis"]["additionalColumns"] == []
    assert by_type["Heatmap"]["value"] == 0
    assert by_type["Heatmap"]["relationshipMode"] == {"relationshipMode": [1, -1, 0]}
    tab = by_type["Heatmap"]["configs"][0]
    assert "id" not in tab and tab["customFilter"]["filter"] == [] and tab["groupBy"]["parentText"] == "VMWARE"
    entry = by_type["Scoreboard"]["metric"]["resourceKindMetrics"][0]
    assert entry["link"] == "" and entry["unit"] is None and entry["resourceKindName"] == "HostSystem"
    assert "metricUnit" not in entry and "labelLocalized" not in entry


# --- dependency walkers see the two new metric surfaces -----------------------

def _walker_dash(tmp_path):
    return _load(tmp_path, _dash([
        _pareto(additional_columns=[{"metric_key": SM_KEY, "label": "SM"},
                                    {"metric_key": "summary|total_number_vms", "label": "VMs"}]),
        {**_heat(tab={"custom_filter": [{"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine", "conditions": [
            {"filter_type": "metrics", "metric_key": "cpu|corecount_provisioned", "condition": "GREATER_THAN",
             "value": 8, "string_metric": False}]}]}), "coords": {"x": 7, "y": 1, "w": 6, "h": 6}},
    ]))


def test_widget_extra_metric_refs(tmp_path):
    d = _walker_dash(tmp_path)
    keys = [k for w in d.widgets for k, *_ in widget_extra_metric_refs(w)]
    assert keys == [SM_KEY, "summary|total_number_vms", "cpu|corecount_provisioned"]


def test_dep_walker_sees_extra_refs(tmp_path):
    from vcfcf_core.common.dep_walker import extract_refs_from_dashboards
    d = _walker_dash(tmp_path)
    sm_refs, metric_refs = extract_refs_from_dashboards([d])
    assert any(r.sm_id == SM_KEY.split("sm_")[1] for r in sm_refs)
    assert {"summary|total_number_vms", "cpu|corecount_provisioned"} <= {r.metric_key for r in metric_refs}


def test_build_audit_walker_sees_extra_refs(tmp_path):
    from vcfcf_core.packaging.deps import _refs_from_widgets
    d = _walker_dash(tmp_path)
    keys = {r.metric_key for r in _refs_from_widgets(d)}
    assert {"summary|total_number_vms", "cpu|corecount_provisioned"} <= keys
    assert not any("sm_" in k for k in keys)


def test_collect_deps_bundles_an_sm_named_only_in_an_additional_column(tmp_path):
    from types import SimpleNamespace
    from vcfcf_core.common import dep_walker
    d = _walker_dash(tmp_path)
    sm = SimpleNamespace(id=SM_KEY.split("sm_")[1], name="Probe SM", formula="1",
                         source_path=None, provenance="")
    graph = dep_walker.collect_deps([d], [], [sm], [])
    assert sm.id in {s.id for s in graph.supermetrics}, graph.errors
