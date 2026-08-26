"""Self-provider View pins bind by resource DISPLAY NAME, not kind key.

Live-verified 2026-08-26 on devel 9.1.1 (two throwaway dashboards pinned to
NSXTAdapter/NSXT World: name "NSX World" materialized and bound to the real
resource UUID, name "NSXT World" never materialized). Evidence and method:
knowledge/context/wire-formats/dashboard_view_pin_resolution.md.

Covers:
  A. render: NSXT World / CAS World / LICENSE_USAGE_WORLD pins get their
     display names in entries.resource[].name and config.resource.resourceName.
  B. `pin.name` override wins; non-string rejected.
  C. vSphere World / ComplianceWorld / HostSystem->vSphere World unchanged.
  D. reverse emits pin.name only when the export name differs from what the
     renderer derives; round-trips.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

OWNER = "00000000-0000-0000-0000-000000000001"


def _render(tmp_path, pin: dict, subject=("VMWARE", "vSphere World")):
    from vcfops_dashboards.loader import load_dashboard, load_view
    from vcfops_dashboards.render import render_dashboards_bundle_json

    vp = tmp_path / "v.yaml"
    vp.write_text(yaml.dump({"name": "[VCF Content Factory] Pin Probe View",
                             "subject": {"adapter_kind": subject[0], "resource_kind": subject[1]},
                             "columns": [{"attribute": "cpu|usage_average", "display_name": "x"}]}))
    view = load_view(vp)
    dp = tmp_path / "d.yaml"
    dp.write_text(yaml.dump({"name": "[VCF Content Factory] Pin Probe", "widgets": [{
        "id": "v", "type": "View", "title": "V", "coords": {"x": 1, "y": 1, "w": 12, "h": 6},
        "view": view.name, "self_provider": True, "pin": pin}]}))
    out = json.loads(render_dashboards_bundle_json([load_dashboard(dp)], {view.name: view}, OWNER))
    res = out["dashboards"][0]["widgets"][0]["config"]["resource"]
    return out["entries"]["resource"], res


@pytest.mark.parametrize("ak, rk, expected", [
    ("NSXTAdapter", "NSXT World", "NSX World"),
    ("CASAdapter", "CAS World", "Automation World"),
    ("VMWARE_INFRA_HEALTH", "LICENSE_USAGE_WORLD", "License Usage"),
])
def test_world_display_name_table(tmp_path, ak, rk, expected):
    entries, res = _render(tmp_path, {"adapter_kind": ak, "resource_kind": rk}, subject=(ak, rk))
    assert entries == [{"resourceKindKey": rk, "internalId": "resource:id:0_::_", "adapterKindKey": ak,
                        "identifiers": [], "name": expected}]
    assert res["resourceName"] == expected
    assert res["resourceKindId"].endswith(f"{ak}{rk}")


def test_pin_name_override_wins(tmp_path):
    entries, res = _render(tmp_path, {"adapter_kind": "NSXTAdapter", "resource_kind": "NSXT World",
                                      "name": "NSX-T World"}, subject=("NSXTAdapter", "NSXT World"))
    assert entries[0]["name"] == "NSX-T World" and res["resourceName"] == "NSX-T World"
    assert entries[0]["resourceKindKey"] == "NSXT World"


def test_pin_name_on_leaf_kind_is_rejected(tmp_path):
    """Pinning a single leaf resource by name is not live-verified (only
    world-singleton pins by display name are); the loader rejects it and
    points at the wire doc rather than emitting an unproven shape."""
    from vcfops_dashboards.loader import DashboardValidationError

    with pytest.raises(DashboardValidationError,
                       match=r"pin.name is not supported on leaf kind VMWARE/HostSystem.*"
                             r"dashboard_view_pin_resolution\.md"):
        _render(tmp_path, {"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                           "name": "esx01.lab"}, subject=("VMWARE", "HostSystem"))


def test_pin_name_must_be_string(tmp_path):
    from vcfops_dashboards.loader import DashboardValidationError

    with pytest.raises(DashboardValidationError, match="pin.name must be a string"):
        _render(tmp_path, {"adapter_kind": "NSXTAdapter", "resource_kind": "NSXT World", "name": 7})


@pytest.mark.parametrize("ak, rk, c_rk, expected", [
    ("VMWARE", "vSphere World", "vSphere World", "vSphere World"),
    ("VMWARE", "HostSystem", "vSphere World", "vSphere World"),
])
def test_existing_pins_unchanged(tmp_path, ak, rk, c_rk, expected):
    entries, res = _render(tmp_path, {"adapter_kind": ak, "resource_kind": rk}, subject=(ak, rk))
    assert entries[0]["name"] == expected and entries[0]["resourceKindKey"] == c_rk
    assert res["resourceName"] == expected


def test_resolve_view_pin_order():
    from vcfops_dashboards.render import _resolve_view_pin

    assert _resolve_view_pin("NSXTAdapter", "NSXT World") == ("NSXTAdapter", "NSXT World", "NSX World")
    assert _resolve_view_pin("NSXTAdapter", "NSXT World", "X") == ("NSXTAdapter", "NSXT World", "X")
    assert _resolve_view_pin("VMWARE", "HostSystem") == ("VMWARE", "vSphere World", "vSphere World")
    assert _resolve_view_pin("Foo", "Bar World") == ("Foo", "Bar World", "Bar World")


def _dash_json(name):
    return {"id": "0488a094-01f7-417a-80a8-ca2e7fb2d748", "name": "Rev", "widgets": [{
        "id": "94dc7128-775b-4299-8595-7c566a1d4815", "type": "View", "title": "V",
        "gridsterCoords": {"x": 1, "y": 1, "w": 6, "h": 6},
        "config": {"selfProvider": {"selfProvider": True}, "viewDefinitionId": "e27925b5-1cf1-4fde-a835-41c84577be35",
                   "resource": {"resourceId": "resource:id:0_::_", "resourceName": name,
                                "resourceKindId": "002011NSXTAdapterNSXT World"}}}],
        "entries": {"resourceKind": [], "resource": [{"resourceKindKey": "NSXT World", "internalId": "resource:id:0_::_",
                                                      "adapterKindKey": "NSXTAdapter", "identifiers": [], "name": name}]}}


def test_reverse_emits_pin_name_only_when_it_differs():
    from vcfops_dashboards.reverse import parse_dashboard_json
    from vcfops_extractor.extractor import _widget_to_yaml_dict

    w = parse_dashboard_json(_dash_json("NSX World"), {}).widgets[0]
    assert w.pin.name == ""
    assert "name" not in _widget_to_yaml_dict(w, {})["pin"]
    w = parse_dashboard_json(_dash_json("NSX-T World"), {}).widgets[0]
    assert w.pin.name == "NSX-T World"
    assert _widget_to_yaml_dict(w, {})["pin"] == {"adapter_kind": "NSXTAdapter", "resource_kind": "NSXT World",
                                                  "name": "NSX-T World"}


def test_license_export_pins_resolve_to_display_names():
    """The public export's three View pins reverse without a name: override
    (the table derives them) and re-render with the export's display names."""
    from vcfops_dashboards.reverse import parse_dashboard_json
    from vcfops_dashboards.render import _resolve_view_pin

    fx = json.loads((REPO_ROOT / "tests/fixtures/dashboards/license_consumption_widgets.json").read_text())
    dj = dict(fx["dashboards"][0]); dj["entries"] = fx["entries"]
    by_ref = {e["internalId"]: e["name"] for e in fx["entries"]["resource"]}
    for w in parse_dashboard_json(dj, {}).widgets:
        if w.type != "View":
            continue
        assert w.pin.name == ""
        src = next(x for x in dj["widgets"] if x["title"] == w.title)["config"]["resource"]
        assert _resolve_view_pin(w.pin.adapter_kind, w.pin.resource_kind)[2] == by_ref[src["resourceId"]]


def test_kind_mode_resource_kind_name_uses_display_name(tmp_path):
    """Kind-mode Scoreboard entries carry the kind's display name in the
    cosmetic ``resourceKindName`` (export: "NSX World"), from the same table
    the View pin resolver uses; unlisted kinds keep the kind key."""
    import json

    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    p = tmp_path / "kind_mode.yaml"
    p.write_text(yaml.dump({
        "name": "[VCF Content Factory] Kind Mode Probe",
        "widgets": [{
            "id": "sb", "type": "Scoreboard", "title": "Probe",
            "coords": {"x": 1, "y": 1, "w": 6, "h": 5},
            "metrics": [
                {"adapter_kind": "NSXTAdapter", "resource_kind": "NSXT World",
                 "metric_key": "Super Metric|sm_00000000-0000-0000-0000-000000000001",
                 "metric_name": "A"},
                {"adapter_kind": "VMWARE", "resource_kind": "vSphere World",
                 "metric_key": "Super Metric|sm_00000000-0000-0000-0000-000000000002",
                 "metric_name": "B"},
            ],
        }],
    }, default_flow_style=False))
    out = json.loads(render_dashboards_bundle_json([load_dashboard(p)], {}, OWNER))
    ents = out["dashboards"][0]["widgets"][0]["config"]["metric"]["resourceKindMetrics"]
    assert [e["resourceKindName"] for e in ents] == ["NSX World", "vSphere World"]
    # The binding field is untouched: entries.resourceKind[] still keys on the kind key.
    assert [r["resourceKindKey"] for r in out["entries"]["resourceKind"]] == ["NSXT World", "vSphere World"]
