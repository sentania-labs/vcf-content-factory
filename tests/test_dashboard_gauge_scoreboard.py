"""Gauge scoreboard (visual_theme 9) wire check.

Field survey: knowledge/context/wire-formats/dashboard_section_gauge_viewdetails.md.
Fixture: tests/fixtures/dashboards/gauge_scoreboard.yaml (public VMWARE kinds).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

OWNER = "00000000-0000-0000-0000-000000000001"
FIXTURE = Path(__file__).parent / "fixtures" / "dashboards" / "gauge_scoreboard.yaml"


def _render_fixture(tmp_path: Path) -> dict:
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    # Copy so the loader's id-minting can never touch the checked-in file.
    src = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, src)
    d = load_dashboard(src)
    d.validate({})
    return json.loads(render_dashboards_bundle_json([d], {}, OWNER))["dashboards"][0]


def test_gauge_fixture_wire_shape(tmp_path):
    w = _render_fixture(tmp_path)["widgets"][0]
    cfg = w["config"]
    assert w["type"] == "Scoreboard"
    assert cfg["visualTheme"] == 9
    assert cfg["mode"] == {"layoutMode": "floatingView"}
    assert cfg["showMetricName"] == {"showMetricName": True}
    assert cfg["boxColumns"] == 1
    # gauge switches ride top-level, only on a gauge
    assert cfg["showRemaining"] is True
    assert cfg["showPercentText"] is False
    assert cfg["focusOnPercent"] is False
    m = cfg["metric"]["resourceKindMetrics"]
    assert len(m) == 2
    assert m[0]["maxValue"] == "100"
    assert m[0]["colorMethod"] == 0
    assert (m[0]["yellowBound"], m[0]["orangeBound"], m[0]["redBound"]) == (70.0, 85.0, 95.0)
    assert m[0]["unit"] == "%"
    # non-integral max_value keeps its fraction
    assert m[1]["maxValue"] == "99.5"


def test_max_value_unset_keeps_empty_string(tmp_path):
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    text = FIXTURE.read_text().replace("        max_value: 100\n", "").replace("        max_value: 99.5\n", "")
    p = tmp_path / "no_max.yaml"
    p.write_text(text)
    d = load_dashboard(p)
    d.validate({})
    out = json.loads(render_dashboards_bundle_json([d], {}, OWNER))
    for m in out["dashboards"][0]["widgets"][0]["config"]["metric"]["resourceKindMetrics"]:
        assert m["maxValue"] == ""


def test_non_gauge_omits_gauge_switches_and_defaults_fixed_view(tmp_path):
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    text = (FIXTURE.read_text()
            .replace("visual_theme: 9", "visual_theme: 8")
            .replace("    layout_mode: floatingView\n", ""))
    p = tmp_path / "score.yaml"
    p.write_text(text)
    d = load_dashboard(p)
    d.validate({})
    cfg = json.loads(render_dashboards_bundle_json([d], {}, OWNER))["dashboards"][0]["widgets"][0]["config"]
    assert cfg["visualTheme"] == 8
    assert cfg["mode"] == {"layoutMode": "fixedView"}
    for k in ("showRemaining", "showPercentText", "focusOnPercent"):
        assert k not in cfg


@pytest.mark.parametrize("theme", [0, 10, -1])
def test_visual_theme_range(tmp_path, theme):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    p = tmp_path / "theme.yaml"
    p.write_text(FIXTURE.read_text().replace("visual_theme: 9", f"visual_theme: {theme}"))
    with pytest.raises(DashboardValidationError, match="visual_theme must be 1..9"):
        load_dashboard(p)


def test_layout_mode_enum(tmp_path):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    p = tmp_path / "lm.yaml"
    p.write_text(FIXTURE.read_text().replace("layout_mode: floatingView", "layout_mode: sideways"))
    with pytest.raises(DashboardValidationError, match="layout_mode must be one of"):
        load_dashboard(p)


def test_max_value_must_be_numeric(tmp_path):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    p = tmp_path / "bad.yaml"
    p.write_text(FIXTURE.read_text().replace("max_value: 100", 'max_value: "100"'))
    with pytest.raises(DashboardValidationError, match="max_value must be a number"):
        load_dashboard(p)
