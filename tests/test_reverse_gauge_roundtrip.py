"""Reverse extraction must preserve gauge layout settings and per-metric maxValue.

Two silent-loss bugs in vcfops_dashboards/reverse.py:

  Fix 4 — ``_parse_scoreboard_config()`` never read ``mode.layoutMode``
  (``floatingView``) nor the three bare top-level gauge switches
  (``showRemaining`` / ``showPercentText`` / ``focusOnPercent``), and the
  extractor's ``_widget_to_yaml_dict()`` never serialized them.  An
  extract/re-render cycle silently reset a gauge's scrolling and display
  behaviour to the renderer defaults.

  Fix 5 — a resource-mode Scoreboard metric's non-empty ``maxValue`` never
  reached ``MetricSpec.max_value`` and the YAML serializer omitted
  ``max_value``.  Re-rendering then emitted ``maxValue: ""``, changing a
  non-percentage gauge's full scale to the component fallback rather than the
  authored ceiling.

Each test is a full round trip: authored YAML -> wire JSON (the "original wire
values") -> reverse -> YAML -> re-render -> compare wire to wire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

OWNER = "00000000-0000-0000-0000-000000000001"


def _render(tmp_path: Path, widget: dict, stem: str) -> dict:
    """Author a one-widget dashboard and return its rendered wire dict."""
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    p = tmp_path / f"{stem}.yaml"
    p.write_text(yaml.dump(
        {"name": "[VCF Content Factory] Gauge Round Trip", "widgets": [widget]},
        default_flow_style=False, sort_keys=False,
    ))
    d = load_dashboard(p)
    d.validate({})
    bundle = json.loads(render_dashboards_bundle_json([d], {}, OWNER))
    # entries.resourceKind[] / entries.resource[] live at bundle level; the
    # reverse parser resolves synthetic refs against them, so fold them in.
    dash = dict(bundle["dashboards"][0])
    dash["entries"] = bundle["entries"]
    return dash


def _round_trip(tmp_path: Path, widget: dict) -> tuple[dict, dict]:
    """Return (original_wire_dashboard, re_rendered_wire_dashboard)."""
    from vcfops_dashboards.reverse import parse_dashboard_json
    from vcfops_extractor.extractor import _widget_to_yaml_dict

    original = _render(tmp_path, widget, "original")
    parsed = parse_dashboard_json(original, {})
    assert parsed.widgets, "reverse dropped the widget entirely"
    reversed_widget = _widget_to_yaml_dict(parsed.widgets[0], {})
    re_rendered = _render(tmp_path, reversed_widget, "reversed")
    return original, re_rendered


# --- Fix 4: gauge layout settings -------------------------------------------

_KIND_MODE_GAUGE = {
    "id": "cpu_gauge",
    "type": "Scoreboard",
    "title": "CPU Usage",
    "coords": {"x": 1, "y": 1, "w": 3, "h": 4},
    "visual_theme": 9,
    "box_columns": 1,
    "layout_mode": "floatingView",
    "show_remaining": True,
    "show_percent_text": True,
    "focus_on_percent": True,
    "metrics": [{
        "adapter_kind": "VMWARE",
        "resource_kind": "VirtualMachine",
        "metric_key": "cpu|usage_average",
        "metric_name": "CPU Usage",
        "unit": "%",
        "max_value": 100,
    }],
}


def test_reverse_parses_gauge_layout_settings(tmp_path):
    """All four gauge layout fields land on the reversed ScoreboardConfig."""
    from vcfops_dashboards.reverse import parse_dashboard_json

    original = _render(tmp_path, _KIND_MODE_GAUGE, "original")
    cfg = original["widgets"][0]["config"]
    # Guard: the wire payload really does carry the four fields.
    assert cfg["mode"] == {"layoutMode": "floatingView"}
    assert cfg["showRemaining"] is True
    assert cfg["showPercentText"] is True
    assert cfg["focusOnPercent"] is True

    sb = parse_dashboard_json(original, {}).widgets[0].scoreboard_config
    assert sb.layout_mode == "floatingView"
    assert sb.show_remaining is True
    assert sb.show_percent_text is True
    assert sb.focus_on_percent is True


def test_gauge_layout_settings_survive_round_trip(tmp_path):
    original, re_rendered = _round_trip(tmp_path, _KIND_MODE_GAUGE)
    before = original["widgets"][0]["config"]
    after = re_rendered["widgets"][0]["config"]
    for key in ("mode", "showRemaining", "showPercentText", "focusOnPercent"):
        assert after[key] == before[key], (
            f"gauge layout key {key!r} changed across reverse/re-render: "
            f"{before[key]!r} -> {after[key]!r}"
        )


def test_gauge_layout_defaults_round_trip_unchanged(tmp_path):
    """A gauge left at the defaults round-trips without gaining stray keys."""
    widget = dict(_KIND_MODE_GAUGE)
    for k in ("layout_mode", "show_remaining", "show_percent_text", "focus_on_percent"):
        widget.pop(k, None)
    original, re_rendered = _round_trip(tmp_path, widget)
    before = original["widgets"][0]["config"]
    after = re_rendered["widgets"][0]["config"]
    assert before["mode"] == {"layoutMode": "fixedView"}
    for key in ("mode", "showRemaining", "showPercentText", "focusOnPercent"):
        assert after[key] == before[key]


# --- Fix 5: resource-mode maxValue ------------------------------------------

_RESOURCE_MODE_GAUGE = {
    "id": "license_gauge",
    "type": "Scoreboard",
    "title": "Licenses In Use",
    "coords": {"x": 1, "y": 1, "w": 3, "h": 4},
    "visual_theme": 9,
    "box_columns": 1,
    "layout_mode": "floatingView",
    "show_percent_text": True,
    "self_provider": True,
    "metric_mode": "resource",
    "resource": {
        "adapter_kind": "VMWARE",
        "resource_kind": "VirtualMachine",
        "name": "Probe VM",
    },
    "metrics": [
        {
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "metric_key": "cpu|usage_average",
            "metric_name": "CPU Usage",
            # Deliberately NOT a percentage: the component fallback would be
            # wrong here, which is exactly what the dropped field caused.
            "max_value": 512,
        },
        {
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "metric_key": "mem|usage_average",
            "metric_name": "Memory Usage",
            "max_value": 99.5,
        },
        {
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "metric_key": "sys|uptime",
            "metric_name": "Uptime",
            # No max_value: must stay "" on the wire, not become a number.
        },
    ],
}


def test_reverse_parses_resource_mode_max_value(tmp_path):
    from vcfops_dashboards.reverse import parse_dashboard_json

    original = _render(tmp_path, _RESOURCE_MODE_GAUGE, "original")
    wire_metrics = original["widgets"][0]["config"]["metric"]["resourceMetrics"]
    assert [m["maxValue"] for m in wire_metrics] == ["512", "99.5", ""]

    specs = parse_dashboard_json(original, {}).widgets[0].scoreboard_config.metrics
    assert [s.max_value for s in specs] == [512.0, 99.5, None]


def test_resource_mode_max_value_survives_round_trip(tmp_path):
    original, re_rendered = _round_trip(tmp_path, _RESOURCE_MODE_GAUGE)
    before = original["widgets"][0]["config"]["metric"]["resourceMetrics"]
    after = re_rendered["widgets"][0]["config"]["metric"]["resourceMetrics"]
    assert [m["maxValue"] for m in after] == [m["maxValue"] for m in before]
    # And the gauge layout keys on the same widget survive too.
    assert (re_rendered["widgets"][0]["config"]["mode"]
            == original["widgets"][0]["config"]["mode"])
