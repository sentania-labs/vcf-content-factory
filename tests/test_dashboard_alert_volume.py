"""AlertVolume widget (wire type IntSummaryAlertVolume).

Shape per knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md
§1 and the export samples under reference/docs/extracted/dashboard-widgets/.
Public VMWARE kinds only; tmp_path-local, no network.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

OWNER = "00000000-0000-0000-0000-000000000001"


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _dash(widgets: list, interactions: list | None = None) -> dict:
    return {
        "name": "[VCF Content Factory] Alert Volume Test",
        "description": "",
        "widgets": widgets,
        "interactions": interactions or [],
    }


def _picker() -> dict:
    return {
        "id": "picker", "type": "ResourceList", "title": "DCs",
        "coords": {"x": 1, "y": 1, "w": 4, "h": 5},
        "resource_kinds": [{"adapter_kind": "VMWARE", "resource_kind": "Datacenter"}],
    }


def _render(tmp_path: Path, dash: dict) -> dict:
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    d = load_dashboard(_write(tmp_path / "d.yaml", dash))
    d.validate({})
    return json.loads(render_dashboards_bundle_json([d], {}, OWNER))


def test_interaction_driven_shape(tmp_path):
    out = _render(tmp_path, _dash(
        [_picker(), {"id": "av", "type": "AlertVolume", "title": "Alert Volume (selected DC)",
                     "coords": {"x": 5, "y": 1, "w": 2, "h": 5}}],
        [{"from": "picker", "to": "av"}],
    ))
    w = out["dashboards"][0]["widgets"][1]
    assert w["type"] == "IntSummaryAlertVolume"
    assert w["title"] == "Alert Volume (selected DC)"
    assert w["gridsterCoords"] == {"x": 5, "y": 1, "w": 2, "h": 5}
    assert w["config"] == {
        "refreshInterval": 300,
        "refreshContent": {"refreshContent": False},
        "selfProvider": {"selfProvider": False},
        "title": "Alert Volume (selected DC)",
    }
    assert "resource" not in w["config"]
    assert "resource" not in out["entries"]
    ix = out["dashboards"][0]["widgetInteractions"][0]
    assert ix["type"] == "resourceId" and ix["widgetIdReceiver"] == w["id"]


def test_self_provider_pinned_shape(tmp_path):
    out = _render(tmp_path, _dash([
        {"id": "av", "type": "AlertVolume", "title": "Alert Volume in the Environment",
         "coords": {"x": 1, "y": 1, "w": 12, "h": 10},
         "self_provider": True, "refresh_content": True,
         "pin": {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"}},
    ]))
    w = out["dashboards"][0]["widgets"][0]
    cfg = w["config"]
    assert list(cfg) == ["refreshInterval", "resource", "refreshContent", "selfProvider", "title"]
    # single object with exactly two keys, not an array
    assert cfg["resource"] == {"resourceId": "resource:id:0_::_", "resourceName": "vSphere World"}
    assert cfg["selfProvider"] == {"selfProvider": True}
    assert cfg["refreshContent"] == {"refreshContent": True}
    res = out["entries"]["resource"]
    assert res[0]["internalId"] == "resource:id:0_::_"
    assert res[0]["name"] == "vSphere World"
    assert res[0]["adapterKindKey"] == "VMWARE"


def test_self_provider_requires_pin(tmp_path):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    d = load_dashboard(_write(tmp_path / "np.yaml", _dash([
        {"id": "av", "type": "AlertVolume", "title": "AV",
         "coords": {"x": 1, "y": 1, "w": 2, "h": 5}, "self_provider": True},
    ])))
    with pytest.raises(DashboardValidationError, match="requires a 'pin'"):
        d.validate({})


@pytest.mark.parametrize("key,val", [
    ("criticality", [4]),
    ("severity", "critical"),
    ("time_window", {"unit": "DAYS", "count": 30}),
    ("date_range", "last7Days"),
    ("alert_types", ["15_19"]),
    ("metrics", [{"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine",
                  "metric_key": "cpu|usage_average"}]),
])
def test_unsupported_options_rejected(tmp_path, key, val):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    path = _write(tmp_path / "bad.yaml", _dash([
        {"id": "av", "type": "AlertVolume", "title": "AV",
         "coords": {"x": 1, "y": 1, "w": 2, "h": 5}, key: val},
    ]))
    with pytest.raises(DashboardValidationError, match="AlertVolume does not support"):
        load_dashboard(path)


def test_refresh_content_must_be_bool(tmp_path):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    path = _write(tmp_path / "rc.yaml", _dash([
        {"id": "av", "type": "AlertVolume", "title": "AV",
         "coords": {"x": 1, "y": 1, "w": 2, "h": 5}, "refresh_content": "yes"},
    ]))
    with pytest.raises(DashboardValidationError, match="refresh_content must be a bool"):
        load_dashboard(path)
