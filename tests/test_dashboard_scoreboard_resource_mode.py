"""Resource-mode Scoreboard (`metric_mode: resource`).

Wire evidence: the `License Overview` widget of Scott's public VCF License
Consumption Overview export (six super metrics pinned to the single
`License Usage` resource), trimmed to
tests/fixtures/dashboards/license_overview_resource_mode.json. Digest in
knowledge/context/wire-formats/wire_formats.md §Scoreboard resource mode.

Before this change the loader/renderer only knew `resourceKindMetrics[]`,
both reverse tools silently produced `metrics: []` for the widget, and the
reverse-local round-trip verdict said MATCH on the empty widget because it
compared only type/coords/viewDefinitionId.

Covers:
  A. render: resourceMetrics[] entries, entries.resource[] by display name,
     no entries.resourceKind[] slot, no subMode.
  B. loader: resource block required/complete, kind mismatch, resource
     without metric_mode rejected; metric kinds default to the resource.
  C. reverse.py parses the fixture into metric_mode/resource/6 specs, and
     the extractor's YAML dict carries them; full reverse-local port of the
     fixture re-renders the same six metric keys and labels.
  D. _structural_key: metric loss is a divergence (PARTIAL), not MATCH.
  E. kind-mode Scoreboard output unchanged (no new keys).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURE = REPO_ROOT / "tests/fixtures/dashboards/license_overview_resource_mode.json"
OWNER = "00000000-0000-0000-0000-000000000001"
RESOURCE = {"adapter_kind": "VMWARE_INFRA_HEALTH", "resource_kind": "LICENSE_USAGE_WORLD", "name": "License Usage"}


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def _source_widget() -> dict:
    return _fixture()["dashboards"][0]["widgets"][0]


def _dash(tmp_path: Path, widget: dict) -> Path:
    p = tmp_path / "dash.yaml"
    p.write_text(yaml.dump({
        "name": "[VCF Content Factory] Resource Mode Probe",
        "widgets": [widget],
    }, default_flow_style=False))
    return p


def _resource_widget(**extra) -> dict:
    w = {
        "id": "license_overview",
        "type": "Scoreboard",
        "title": "License Overview",
        "coords": {"x": 1, "y": 1, "w": 6, "h": 5},
        "self_provider": True,
        "metric_mode": "resource",
        "resource": dict(RESOURCE),
        "metrics": [
            {"metric_key": "Super Metric|sm_76801377-1807-4a46-93d4-9b9dc0f0c54b",
             "metric_name": "VCF Total License Usage", "label": "VCF Consumed Cores", "color_method": 1},
            {"metric_key": "Super Metric|sm_dc0b1bc5-478a-4be9-8442-6afa8fb4b4f8",
             "metric_name": "VCF Total License Usage Percent", "label": "VCF License Usage %",
             "color_method": 1, "unit_id": "-1", "unit": "Auto"},
        ],
        "visual_theme": 5, "box_columns": 2, "round_decimals": 0, "label_size": 16,
    }
    w.update(extra)
    return w


def _render(tmp_path: Path, widget: dict) -> dict:
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    d = load_dashboard(_dash(tmp_path, widget))
    return json.loads(render_dashboards_bundle_json([d], {}, OWNER))


# A. render ------------------------------------------------------------------

def test_render_resource_mode_matches_export_shape(tmp_path):
    out = _render(tmp_path, _resource_widget())
    assert out["entries"]["resource"] == [{
        "resourceKindKey": "LICENSE_USAGE_WORLD",
        "internalId": "resource:id:0_::_",
        "adapterKindKey": "VMWARE_INFRA_HEALTH",
        "identifiers": [],
        "name": "License Usage",
    }]
    # The pinned kind gets no entries.resourceKind[] slot (matches export).
    assert out["entries"]["resourceKind"] == []
    metric = out["dashboards"][0]["widgets"][0]["config"]["metric"]
    assert metric["mode"] == "resource"
    assert metric["resourceKindMetrics"] == []
    assert "subMode" not in metric
    assert len(metric["resourceMetrics"]) == 2
    e0 = metric["resourceMetrics"][0]
    assert e0["resourceId"] == "resource:id:0_::_"
    assert e0["resourceName"] == "License Usage"
    assert e0["resourceKindId"] == "002019VMWARE_INFRA_HEALTHLICENSE_USAGE_WORLD"
    assert "resourceKindName" not in e0
    assert e0["label"] == "VCF Consumed Cores" and e0["colorMethod"] == 1
    e1 = metric["resourceMetrics"][1]
    assert e1["metricUnitId"] == "-1" and e1["unit"] == "Auto"


def test_render_entry_fields_equal_export_except_known_cosmetics(tmp_path):
    """Every field of every entry equals the export, except the three
    cosmetic conventions kind mode already has (maxValue, empty unit, id)."""
    src = _source_widget()
    src_entries = src["config"]["metric"]["resourceMetrics"]
    metrics = []
    for e in src_entries:
        m = {"metric_key": e["metricKey"], "metric_name": e["metricName"], "label": e["label"],
             "color_method": e["colorMethod"]}
        if e.get("metricUnitId") is not None:
            m["unit_id"] = str(e["metricUnitId"])
        if e.get("unit"):
            m["unit"] = e["unit"]
        metrics.append(m)
    out = _render(tmp_path, _resource_widget(metrics=metrics))
    rendered = out["dashboards"][0]["widgets"][0]["config"]["metric"]["resourceMetrics"]
    assert len(rendered) == len(src_entries) == 6
    ignore = {"id", "maxValue"}
    for r, s in zip(rendered, src_entries):
        for k in set(r) | set(s):
            if k in ignore:
                continue
            rv, sv = r.get(k), s.get(k)
            if k == "unit" and (rv, sv) == (None, ""):
                continue
            if k == "metricUnitId" and str(rv) == str(sv):
                continue
            assert rv == sv, (s["label"], k, rv, sv)


def test_render_resource_mode_shares_slot_by_display_name_not_kind(tmp_path):
    """A View pinned to the same kind under a DIFFERENT display name must
    not collide with the Scoreboard's entry (slots are keyed by name)."""
    from vcfops_dashboards.loader import load_dashboard, load_view
    from vcfops_dashboards.render import render_dashboards_bundle_json

    vp = tmp_path / "view.yaml"
    vp.write_text(yaml.dump({
        "name": "[VCF Content Factory] Probe View",
        "subject": {"adapter_kind": "VMWARE_INFRA_HEALTH", "resource_kind": "LICENSE_USAGE_WORLD"},
        "columns": [{"attribute": "cpu|usage_average", "display_name": "x"}],
    }))
    view = load_view(vp)
    dp = tmp_path / "dash.yaml"
    dp.write_text(yaml.dump({
        "name": "[VCF Content Factory] Two Pins",
        "widgets": [
            _resource_widget(),
            {"id": "v", "type": "View", "title": "V", "coords": {"x": 7, "y": 1, "w": 6, "h": 5},
             "view": view.name, "self_provider": True,
             "pin": {"adapter_kind": "VMWARE_INFRA_HEALTH", "resource_kind": "LICENSE_USAGE_WORLD",
                     "name": "License Usage (DC2)"}},
        ],
    }))
    out = json.loads(render_dashboards_bundle_json([load_dashboard(dp)], {view.name: view}, OWNER))
    names = [(e["internalId"], e["name"]) for e in out["entries"]["resource"]]
    assert len(names) == 2 and len({n for _, n in names}) == 2
    widgets = out["dashboards"][0]["widgets"]
    sb_ref = widgets[0]["config"]["metric"]["resourceMetrics"][0]["resourceId"]
    view_ref = widgets[1]["config"]["resource"]["resourceId"]
    assert sb_ref != view_ref
    assert dict(names)[sb_ref] == "License Usage"


# B. loader -------------------------------------------------------------------

def test_loader_defaults_metric_kinds_to_resource(tmp_path):
    from vcfops_dashboards.loader import load_dashboard

    d = load_dashboard(_dash(tmp_path, _resource_widget()))
    cfg = d.widgets[0].scoreboard_config
    assert cfg.metric_mode == "resource"
    assert (cfg.resource.adapter_kind, cfg.resource.resource_kind, cfg.resource.name) == (
        "VMWARE_INFRA_HEALTH", "LICENSE_USAGE_WORLD", "License Usage")
    assert {(m.adapter_kind, m.resource_kind) for m in cfg.metrics} == {
        ("VMWARE_INFRA_HEALTH", "LICENSE_USAGE_WORLD")}


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda w: w.pop("resource"), "requires a resource:"),
        (lambda w: w["resource"].pop("name"), "missing name"),
        (lambda w: w.update({"metric_mode": "bogus"}), "metric_mode must be one of"),
        (lambda w: w.pop("metric_mode"), "only valid with metric_mode: resource"),
        (lambda w: w.update({"self_provider": False}), "requires self_provider: true"),
        (lambda w: w.pop("self_provider"), "requires self_provider: true"),
        (lambda w: w["metrics"][0].update({"adapter_kind": "VMWARE", "resource_kind": "vSphere World"}),
         "pins every metric to the widget's resource"),
    ],
)
def test_loader_rejects(tmp_path, mutate, needle):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    w = _resource_widget()
    mutate(w)
    with pytest.raises(DashboardValidationError, match=re.escape(needle)):
        load_dashboard(_dash(tmp_path, w))


# C. reverse ------------------------------------------------------------------

def test_reverse_parses_resource_mode_from_fixture():
    from vcfops_dashboards.reverse import parse_dashboard_json
    from vcfops_extractor.extractor import _widget_to_yaml_dict

    fx = _fixture()
    dj = dict(fx["dashboards"][0]); dj["entries"] = fx["entries"]
    dash = parse_dashboard_json(dj, {})
    cfg = dash.widgets[0].scoreboard_config
    assert cfg.metric_mode == "resource"
    assert cfg.resource.name == "License Usage"
    assert cfg.resource.resource_kind == "LICENSE_USAGE_WORLD"
    assert [m.label for m in cfg.metrics] == [
        "VCF Consumed Cores", "vSAN Consumed TiB", "Total VCF License Capacity",
        "Total vSAN License Capacity (TiB)", "VCF License Usage %", "vSAN License Usage %"]
    assert cfg.metrics[4].unit_id == "-1" and cfg.metrics[4].unit == "Auto"
    d = _widget_to_yaml_dict(dash.widgets[0], {})
    assert d["metric_mode"] == "resource"
    assert d["resource"] == RESOURCE
    assert len(d["metrics"]) == 6


def test_reverse_local_port_round_trips_fixture(tmp_path, capsys):
    from vcfops_extractor.reverse_local import reverse_local_port
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    src = tmp_path / "dashboard.json"; src.write_text(FIXTURE.read_text())
    (tmp_path / "xml").mkdir(); (tmp_path / "sm").mkdir()
    rc = reverse_local_port(
        source_dashboard_json=src, source_view_xml_dir=tmp_path / "xml",
        sm_yaml_dir=tmp_path / "sm", output_views_dir=tmp_path / "views",
        output_dashboards_dir=tmp_path / "dash", name_path_override="",
    )
    assert rc == 0
    assert "MATCH      'VCF Consumption Overview v2'" in capsys.readouterr().out
    out_yaml = next((tmp_path / "dash").glob("*.yaml"))
    rendered = json.loads(render_dashboards_bundle_json(
        [load_dashboard(out_yaml, enforce_framework_prefix=False)], {}, OWNER))
    src_m = _source_widget()["config"]["metric"]["resourceMetrics"]
    ren_m = rendered["dashboards"][0]["widgets"][0]["config"]["metric"]["resourceMetrics"]
    assert [(e["metricKey"], e["label"]) for e in ren_m] == [(e["metricKey"], e["label"]) for e in src_m]


# D. verdict ------------------------------------------------------------------

def test_structural_key_notices_lost_metrics():
    from vcfops_extractor.reverse_local import _structural_key

    src = _source_widget()
    empty = json.loads(json.dumps(src))
    empty["config"]["metric"] = {"mode": "resourceKind", "resourceMetrics": [], "resourceKindMetrics": [],
                                 "subMode": "resourceKindAll"}
    assert _structural_key(src) != _structural_key(empty)
    assert _structural_key(src)[:3] == _structural_key(empty)[:3]
    assert _structural_key(src)[3][0] == "resource" and len(_structural_key(src)[3][1]) == 6


# E. no-regression ------------------------------------------------------------

def test_kind_mode_scoreboard_unchanged(tmp_path):
    w = _resource_widget()
    w.pop("metric_mode"); w.pop("resource")
    for m in w["metrics"]:
        m.update({"adapter_kind": "VMWARE", "resource_kind": "vSphere World"})
    out = _render(tmp_path, w)
    metric = out["dashboards"][0]["widgets"][0]["config"]["metric"]
    assert metric["mode"] == "resourceKind" and metric["subMode"] == "resourceKindAll"
    assert metric["resourceMetrics"] == [] and len(metric["resourceKindMetrics"]) == 2
    assert "resource" not in out["entries"]
    assert out["entries"]["resourceKind"] == [
        {"resourceKindKey": "vSphere World", "internalId": "resourceKind:id:0_::_", "adapterKindKey": "VMWARE"}]
