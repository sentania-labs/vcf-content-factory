"""Reverse-path field drops (2026-08-26).

Reversing Scott's public VCF License Consumption Overview export dropped
seven fields that re-rendered differently from the source:

  dashboard widgets: selectFirstRow=false (all View widgets), chartViewItems
    ["legend"] (trend View widgets), showDT=true, roundDecimals=null and
    refreshContent=false (Scoreboards)
  views: forecastDays=90 + FORECAST transformation (trend views),
    hideObjectNameColumn=true (list views)

Fixtures (trimmed from the export, public content):
  tests/fixtures/dashboards/license_consumption_widgets.json  (3 widgets)
  tests/fixtures/license_consumption_views.xml                (1 trend, 1 list)

Each test reverses the fixture, loads the YAML back through the factory
loader, renders, and asserts the field equals the source. Loader defaults
are the historical hardcoded values so untouched content is byte-identical.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DASH_FX = REPO_ROOT / "tests/fixtures/dashboards/license_consumption_widgets.json"
VIEWS_FX = REPO_ROOT / "tests/fixtures/license_consumption_views.xml"
OWNER = "00000000-0000-0000-0000-000000000001"
TREND_ID = "e27925b5-1cf1-4fde-a835-41c84577be35"
LIST_ID = "6b512229-ff2c-490b-8cfb-ae70f3008de0"


@pytest.fixture
def ported(tmp_path):
    """Run reverse-local on the fixtures; return (source json, rendered
    bundle json, rendered views xml root, view yaml docs)."""
    from vcfops_extractor.reverse_local import reverse_local_port
    from vcfops_dashboards.loader import load_dashboard, load_view
    from vcfops_dashboards.render import render_dashboards_bundle_json, render_views_xml

    (tmp_path / "xml").mkdir(); (tmp_path / "sm").mkdir()
    (tmp_path / "xml" / "content.xml").write_text(VIEWS_FX.read_text())
    src_path = tmp_path / "dashboard.json"; src_path.write_text(DASH_FX.read_text())
    rc = reverse_local_port(
        source_dashboard_json=src_path, source_view_xml_dir=tmp_path / "xml",
        sm_yaml_dir=tmp_path / "sm", output_views_dir=tmp_path / "views",
        output_dashboards_dir=tmp_path / "dash", name_path_override="",
    )
    assert rc == 0
    views = [load_view(p, enforce_framework_prefix=False) for p in sorted((tmp_path / "views").glob("*.yaml"))]
    dash = load_dashboard(next((tmp_path / "dash").glob("*.yaml")), enforce_framework_prefix=False)
    rendered = json.loads(render_dashboards_bundle_json([dash], {v.name: v for v in views}, OWNER))
    xml_root = ET.fromstring(render_views_xml(views).encode())
    docs = {yaml.safe_load(p.read_text())["id"]: yaml.safe_load(p.read_text()) for p in (tmp_path / "views").glob("*.yaml")}
    return json.loads(DASH_FX.read_text()), rendered, xml_root, docs


def _widgets(bundle):
    return {w["title"]: w for w in bundle["dashboards"][0]["widgets"]}


# --- dashboard widgets --------------------------------------------------------

def test_view_widget_select_first_row_and_legend_round_trip(ported):
    src, out, _, _ = ported
    for title in ("VCF License Usage Over Time", "VCF Consumption Overtime"):
        s, r = _widgets(src)[title]["config"], _widgets(out)[title]["config"]
        assert s["selectFirstRow"] == {"selectFirstRow": False}
        assert r["selectFirstRow"] == s["selectFirstRow"]
        assert r["chartViewItems"] == s["chartViewItems"]
    assert _widgets(out)["VCF License Usage Over Time"]["config"]["chartViewItems"] == ["legend"]
    assert _widgets(out)["VCF Consumption Overtime"]["config"]["chartViewItems"] == []


def test_scoreboard_showdt_rounddecimals_refreshcontent_round_trip(ported):
    src, out, _, _ = ported
    s, r = _widgets(src)["NSX Usage Insights"]["config"], _widgets(out)["NSX Usage Insights"]["config"]
    assert (s["showDT"], s["roundDecimals"], s["refreshContent"]) == (
        {"showDT": True}, None, {"refreshContent": False})
    assert r["showDT"] == s["showDT"]
    assert r["roundDecimals"] is None
    assert r["refreshContent"] == s["refreshContent"]
    assert len(r["metric"]["resourceKindMetrics"]) == 4


def test_reverse_yaml_carries_the_fields(tmp_path):
    from vcfops_dashboards.reverse import parse_dashboard_json
    from vcfops_extractor.extractor import _widget_to_yaml_dict

    fx = json.loads(DASH_FX.read_text())
    dj = dict(fx["dashboards"][0]); dj["entries"] = fx["entries"]
    by_title = {w.title: _widget_to_yaml_dict(w, {}) for w in parse_dashboard_json(dj, {}).widgets}
    assert by_title["VCF License Usage Over Time"]["select_first_row"] is False
    assert by_title["VCF License Usage Over Time"]["chart_view_items"] == ["legend"]
    assert "chart_view_items" not in by_title["VCF Consumption Overtime"]
    sb = by_title["NSX Usage Insights"]
    assert sb["show_dt"] is True and sb["refresh_content"] is False
    assert "round_decimals" in sb and sb["round_decimals"] is None


def test_loader_round_decimals_null_vs_absent(tmp_path):
    from vcfops_dashboards.loader import load_dashboard

    def _load(extra):
        p = tmp_path / f"{len(extra)}.yaml"
        p.write_text(yaml.dump({"name": "[VCF Content Factory] RD", "widgets": [{
            "id": "sb", "type": "Scoreboard", "title": "t", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
            "metrics": [{"adapter_kind": "VMWARE", "resource_kind": "vSphere World",
                         "metric_key": "cpu|usage_average", "metric_name": "cpu"}], **extra}]}))
        return load_dashboard(p).widgets[0].scoreboard_config

    assert _load({}).round_decimals == 1
    assert _load({"round_decimals": None}).round_decimals is None
    assert _load({"round_decimals": 0}).round_decimals == 0.0


def test_chart_view_items_rejected_off_view(tmp_path):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    p = tmp_path / "d.yaml"
    p.write_text(yaml.dump({"name": "[VCF Content Factory] X", "widgets": [{
        "id": "t", "type": "TextDisplay", "title": "t", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
        "html": "<br>", "chart_view_items": ["legend"]}]}))
    with pytest.raises(DashboardValidationError, match="only valid on View widgets"):
        load_dashboard(p)


# --- views ---------------------------------------------------------------------

def _viewdef(root, vid):
    return next(e for e in root.iter() if e.tag.endswith("ViewDef") and e.get("id") == vid)


def _props(elem, name):
    return [p.get("value") for p in elem.iter() if p.tag.endswith("Property") and p.get("name") == name]


def test_trend_view_forecast_round_trip(ported):
    _, _, root, docs = ported
    assert docs[TREND_ID]["forecast_days"] == 90
    assert "transformations" not in docs[TREND_ID]  # renderer derives NONE/TREND/FORECAST
    vd = _viewdef(root, TREND_ID)
    assert _props(vd, "forecastDays") == ["90"]
    tr = next(p for p in vd.iter() if p.tag.endswith("Property") and p.get("name") == "transformations")
    assert [i.get("value") for i in tr.iter() if i.tag.endswith("Item")] == ["NONE", "TREND", "FORECAST"]


def test_list_view_hide_object_name_round_trip(ported):
    _, _, root, docs = ported
    assert docs[LIST_ID]["hide_object_name"] is True
    assert "forecast_days" not in docs[LIST_ID]
    assert _props(_viewdef(root, LIST_ID), "hideObjectNameColumn") == ["true"]
    assert _props(_viewdef(root, TREND_ID), "hideObjectNameColumn") == ["false"]


def test_reverse_py_viewdef_carries_forecast_and_hide():
    from vcfops_dashboards.reverse import parse_view_from_content_xml

    raw = VIEWS_FX.read_bytes()
    trend = parse_view_from_content_xml(raw, TREND_ID)
    assert trend.data_type == "trend" and trend.forecast_days == 90 and trend.transformations is None
    assert trend.hide_object_name is False
    lst = parse_view_from_content_xml(raw, LIST_ID)
    assert lst.hide_object_name is True and lst.forecast_days == 0


def test_extractor_trend_column_has_no_joined_transformation():
    """Regression: the extractor used to join a multi-item transformations
    list into "NONE,TREND,FORECAST" and write it as a per-column value."""
    from vcfops_extractor.extractor import _parse_view_def_element

    root = ET.fromstring(VIEWS_FX.read_bytes())
    d = _parse_view_def_element(_viewdef(root, TREND_ID))
    assert d["forecast_days"] == 90 and d["transformations"] is None
    assert all("transformation" not in c for c in d["columns"])
    lst = _parse_view_def_element(_viewdef(root, LIST_ID))
    assert lst["hide_object_name"] is True


def test_defaults_unchanged(tmp_path):
    from vcfops_dashboards.loader import load_view
    from vcfops_dashboards.render import _render_view_def_fragment

    p = tmp_path / "v.yaml"
    p.write_text(yaml.dump({"name": "[VCF Content Factory] V", "data_type": "trend",
                            "subject": {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
                            "columns": [{"attribute": "cpu|usage_average", "display_name": "c"}]}))
    frag = _render_view_def_fragment(load_view(p), {})
    assert 'hideObjectNameColumn" value="false"' in frag and "forecastDays" not in frag
