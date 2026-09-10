"""Scoreboard bound contract: color_method 0 needs all three bounds or none.

A partial set makes the server answer value "?" / state Unknown for the
tile (lesson scoreboard-partial-bounds-render-unknown; wire notes in
knowledge/context/wire-formats/dashboard_section_gauge_viewdetails.md).
Fixture: tests/fixtures/dashboards/gauge_scoreboard.yaml (public VMWARE kinds).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

OWNER = "00000000-0000-0000-0000-000000000001"
FIXTURE = Path(__file__).parent / "fixtures" / "dashboards" / "gauge_scoreboard.yaml"
BOUND_LINES = {
    "yellow_bound": "        yellow_bound: 70\n",
    "orange_bound": "        orange_bound: 85\n",
    "red_bound": "        red_bound: 95\n",
}


def _load(tmp_path: Path, text: str):
    from vcfops_dashboards.loader import load_dashboard

    p = tmp_path / "bounds.yaml"
    p.write_text(text)
    return load_dashboard(p)


def _first_metric(d) -> dict:
    from vcfops_dashboards.render import render_dashboards_bundle_json

    out = json.loads(render_dashboards_bundle_json([d], {}, OWNER))
    return out["dashboards"][0]["widgets"][0]["config"]["metric"]["resourceKindMetrics"][0]


@pytest.mark.parametrize("missing", sorted(BOUND_LINES))
def test_partial_bound_set_is_rejected(tmp_path, missing):
    from vcfops_dashboards.loader import DashboardValidationError

    text = FIXTURE.read_text().replace(BOUND_LINES[missing], "", 1)
    with pytest.raises(DashboardValidationError) as ei:
        _load(tmp_path, text)
    msg = str(ei.value)
    assert "'cpu_gauge'" in msg
    assert "'cpu|usage_average'" in msg
    assert re.search(rf"missing {missing}\b", msg)
    for other in BOUND_LINES:
        if other != missing:
            assert other not in msg.split("missing", 1)[1].split(".")[0]


def test_only_one_bound_names_both_missing(tmp_path):
    from vcfops_dashboards.loader import DashboardValidationError

    text = (FIXTURE.read_text()
            .replace(BOUND_LINES["yellow_bound"], "", 1)
            .replace(BOUND_LINES["orange_bound"], "", 1))
    with pytest.raises(DashboardValidationError, match="missing yellow_bound, orange_bound"):
        _load(tmp_path, text)


def test_full_bound_set_accepted_and_emitted(tmp_path):
    d = _load(tmp_path, FIXTURE.read_text())
    d.validate({})
    m = _first_metric(d)
    assert m["colorMethod"] == 0
    assert (m["yellowBound"], m["orangeBound"], m["redBound"]) == (70.0, 85.0, 95.0)


def test_no_bounds_accepted_as_uncolored(tmp_path):
    text = FIXTURE.read_text()
    for line in BOUND_LINES.values():
        text = text.replace(line, "", 1)
    d = _load(tmp_path, text)
    d.validate({})
    m = _first_metric(d)
    assert m["colorMethod"] == 0
    assert (m["yellowBound"], m["orangeBound"], m["redBound"]) == (None, None, None)


def test_partial_set_allowed_when_not_color_method_0(tmp_path):
    # Other color methods ignore the bounds; the renderer emits nulls.
    text = (FIXTURE.read_text()
            .replace("        color_method: 0\n", "        color_method: 2\n", 1)
            .replace(BOUND_LINES["red_bound"], "", 1))
    d = _load(tmp_path, text)
    d.validate({})
    m = _first_metric(d)
    assert m["colorMethod"] == 2
    assert (m["yellowBound"], m["orangeBound"], m["redBound"]) == (None, None, None)


@pytest.mark.parametrize("supplied", ["red_bound", "all"])
def test_bounds_with_color_method_3_are_rejected(tmp_path, supplied):
    # The factory only emits bounds for color_method 0; 3 is a reading
    # note for vendor exports. Bounds on 3 must error, not vanish.
    from vcfops_dashboards.loader import DashboardValidationError

    text = FIXTURE.read_text().replace("        color_method: 0\n", "        color_method: 3\n", 1)
    if supplied == "red_bound":
        text = (text.replace(BOUND_LINES["yellow_bound"], "", 1)
                    .replace(BOUND_LINES["orange_bound"], "", 1))
    with pytest.raises(DashboardValidationError) as ei:
        _load(tmp_path, text)
    msg = str(ei.value)
    assert "'cpu_gauge'" in msg
    assert "'cpu|usage_average'" in msg
    assert "color_method 3" in msg
    assert "red_bound" in msg
    if supplied == "red_bound":
        assert "yellow_bound" not in msg and "orange_bound" not in msg
    else:
        assert "yellow_bound, orange_bound, red_bound" in msg


def test_color_method_3_without_bounds_is_accepted(tmp_path):
    text = FIXTURE.read_text().replace("        color_method: 0\n", "        color_method: 3\n", 1)
    for line in BOUND_LINES.values():
        text = text.replace(line, "", 1)
    d = _load(tmp_path, text)
    d.validate({})
    m = _first_metric(d)
    assert m["colorMethod"] == 3
    assert (m["yellowBound"], m["orangeBound"], m["redBound"]) == (None, None, None)


# The bound check lives in the shared _parse_metric_specs helper, so it
# fires for MetricChart and PropertyList exactly as for Scoreboard.
# PropertyList nests its entries under property_list.properties.
_OTHER_WIDGET_HEAD = """id: 7d1c5a2e-3b4f-4c6d-8e9f-0a1b2c3d4e60
name: "[VCF Content Factory] {wtype} Bound Fixture"
description: One {wtype} widget over public VMWARE kinds.
widgets:
  - id: other_widget
    type: {wtype}
    title: CPU Usage
    coords: {{x: 1, y: 1, w: 6, h: 4}}
"""
_PARTIAL_ENTRY = """      - adapter_kind: VMWARE
        resource_kind: VirtualMachine
        metric_key: cpu|usage_average
        metric_name: CPU Usage
        color_method: 0
        yellow_bound: 70
        orange_bound: 85
"""
_OTHER_WIDGET = {
    "MetricChart": _OTHER_WIDGET_HEAD + "    metrics:\n" + _PARTIAL_ENTRY + "interactions: []\n",
    "PropertyList": (_OTHER_WIDGET_HEAD + "    property_list:\n      properties:\n"
                     + _PARTIAL_ENTRY.replace("\n      ", "\n        ").replace("      - ", "        - ", 1)
                     + "interactions: []\n"),
}


@pytest.mark.parametrize("wtype", sorted(_OTHER_WIDGET))
def test_partial_bound_set_is_rejected_for_other_widgets(tmp_path, wtype):
    from vcfops_dashboards.loader import DashboardValidationError

    with pytest.raises(DashboardValidationError) as ei:
        _load(tmp_path, _OTHER_WIDGET[wtype].format(wtype=wtype))
    msg = str(ei.value)
    assert "'other_widget'" in msg
    assert "'cpu|usage_average'" in msg
    assert re.search(r"missing red_bound\b", msg)
