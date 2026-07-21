"""FB-011 — advancedTimeMode views were missing startPeriod/endPeriod.

Root cause: the vendor wire format pairs `advancedTimeMode=true` with a
`startPeriod`/`endPeriod` range on the time-interval-selector Control. Our
loader had no fields for this and the renderer emitted only
advancedTimeMode/unit/count, leaving advanced-mode queries with an
undefined range — the leading suspect for the "View request timed out"
symptom on "vSphere Cluster HA Admission Control status"
(knowledge/context/feedback_queue.md FB-011).

Vendor evidence: across the full reference corpus (250+ time-interval-
selector controls surveyed, reference/references/**), exactly one control
has advancedTimeMode=true, and it carries startPeriod=PREVIOUS /
endPeriod=NOW (View - Set 3.xml, ViewDef
fc64c67a-d5b0-4a03-a10b-767b9b247120). No other value pairing is attested.

These tests cover:
  T1 — loader parses start_period/end_period from time_window: YAML.
  T2 — renderer emits startPeriod/endPeriod Properties when set explicitly.
  T3 — renderer defaults to PREVIOUS/NOW when advanced_time_mode is true
       and start_period/end_period are left unset (the FB-011 fix).
  T4 — renderer omits startPeriod/endPeriod entirely when
       advanced_time_mode is false (existing/simple views must render
       byte-identically — no regression).
  T5 — extractor round-trip (XML -> YAML dict) captures start_period/
       end_period.
  T6 — reverse_local round-trip (XML -> YAML dict) captures
       start_period/end_period.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


def _write_yaml(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _make_view_yaml(tmp_path: Path, time_window: dict) -> Path:
    return _write_yaml(
        tmp_path / "views" / "fb011_view.yaml",
        {
            "name": "FB011 Advanced Time Mode View",
            "subject": {
                "adapter_kind": "VMWARE",
                "resource_kind": "ClusterComputeResource",
            },
            "time_window": time_window,
            "columns": [
                {
                    "attribute": "summary|admissionControlEnabled",
                    "display_name": "HA Admission Control Enabled",
                },
            ],
        },
    )


def _time_control(xml_text: str) -> ET.Element:
    root = ET.fromstring(xml_text)
    for ctrl in root.iter("Control"):
        if ctrl.get("type") == "time-interval-selector":
            return ctrl
    raise AssertionError("no time-interval-selector Control found in rendered XML")


def _props(ctrl: ET.Element) -> dict:
    return {p.get("name"): p.get("value") for p in ctrl.iter("Property")}


class TestLoaderParsesStartEndPeriod:
    def test_explicit_start_end_period_parsed(self, tmp_path):
        from vcfops_dashboards.loader import load_view

        view_path = _make_view_yaml(
            tmp_path,
            {
                "unit": "DAYS",
                "count": 7,
                "advanced_time_mode": True,
                "start_period": "PREVIOUS",
                "end_period": "NOW",
            },
        )
        view = load_view(view_path, enforce_framework_prefix=False)
        assert view.time_window.start_period == "PREVIOUS"
        assert view.time_window.end_period == "NOW"

    def test_no_start_end_period_defaults_to_none(self, tmp_path):
        from vcfops_dashboards.loader import load_view

        view_path = _make_view_yaml(
            tmp_path,
            {"unit": "DAYS", "count": 7, "advanced_time_mode": True},
        )
        view = load_view(view_path, enforce_framework_prefix=False)
        assert view.time_window.start_period is None
        assert view.time_window.end_period is None


class TestRendererStartEndPeriod:
    def test_explicit_values_are_emitted(self, tmp_path):
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        view_path = _make_view_yaml(
            tmp_path,
            {
                "unit": "DAYS",
                "count": 7,
                "advanced_time_mode": True,
                "start_period": "PREVIOUS",
                "end_period": "NOW",
            },
        )
        view = load_view(view_path, enforce_framework_prefix=False)
        xml_text = render_views_xml([view], sm_scope=[])
        props = _props(_time_control(xml_text))
        assert props["advancedTimeMode"] == "true"
        assert props["startPeriod"] == "PREVIOUS"
        assert props["endPeriod"] == "NOW"

    def test_advanced_mode_without_range_defaults_to_previous_now(self, tmp_path):
        """FB-011 fix: advanced_time_mode true + no explicit range must still
        emit startPeriod=PREVIOUS/endPeriod=NOW — the only pairing ever
        observed in the vendor corpus, and the fix for the shipped
        "View request timed out" view."""
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        view_path = _make_view_yaml(
            tmp_path,
            {"unit": "DAYS", "count": 7, "advanced_time_mode": True},
        )
        view = load_view(view_path, enforce_framework_prefix=False)
        xml_text = render_views_xml([view], sm_scope=[])
        props = _props(_time_control(xml_text))
        assert props["advancedTimeMode"] == "true"
        assert props["startPeriod"] == "PREVIOUS"
        assert props["endPeriod"] == "NOW"

    def test_non_advanced_mode_omits_period_properties(self, tmp_path):
        """Regression guard: simple (non-advanced) views — the overwhelming
        majority of the corpus — must render byte-identically to before this
        fix: no startPeriod/endPeriod Properties at all."""
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        view_path = _make_view_yaml(tmp_path, {"unit": "DAYS", "count": 7})
        view = load_view(view_path, enforce_framework_prefix=False)
        xml_text = render_views_xml([view], sm_scope=[])
        props = _props(_time_control(xml_text))
        assert props["advancedTimeMode"] == "false"
        assert "startPeriod" not in props
        assert "endPeriod" not in props

    def test_no_time_window_omits_period_properties(self, tmp_path):
        """Views with no time_window: at all (the default fallback path)
        must also omit startPeriod/endPeriod."""
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        view_path = _write_yaml(
            tmp_path / "views" / "fb011_no_window.yaml",
            {
                "name": "FB011 No Window View",
                "subject": {
                    "adapter_kind": "VMWARE",
                    "resource_kind": "ClusterComputeResource",
                },
                "columns": [
                    {
                        "attribute": "summary|admissionControlEnabled",
                        "display_name": "HA Admission Control Enabled",
                    },
                ],
            },
        )
        view = load_view(view_path, enforce_framework_prefix=False)
        xml_text = render_views_xml([view], sm_scope=[])
        props = _props(_time_control(xml_text))
        assert props["advancedTimeMode"] == "false"
        assert "startPeriod" not in props
        assert "endPeriod" not in props


class TestExtractorRoundTrip:
    def test_extractor_parse_time_window_captures_period(self):
        from vcfops_extractor.extractor import _parse_time_window

        controls_xml = (
            '<Controls>'
            '<Control id="time-interval-selector_id_1" type="time-interval-selector" visible="false">'
            '<Property name="advancedTimeMode" value="true"/>'
            '<Property name="unit" value="DAYS"/>'
            '<Property name="count" value="7"/>'
            '<Property name="startPeriod" value="PREVIOUS"/>'
            '<Property name="endPeriod" value="NOW"/>'
            '</Control>'
            '</Controls>'
        )
        controls_elem = ET.fromstring(controls_xml)
        result = _parse_time_window(controls_elem)
        assert result == {
            "unit": "DAYS",
            "count": 7,
            "advanced_time_mode": True,
            "start_period": "PREVIOUS",
            "end_period": "NOW",
        }

    def test_extractor_parse_time_window_no_period_is_none(self):
        from vcfops_extractor.extractor import _parse_time_window

        controls_xml = (
            '<Controls>'
            '<Control id="time-interval-selector_id_1" type="time-interval-selector" visible="false">'
            '<Property name="advancedTimeMode" value="false"/>'
            '<Property name="unit" value="DAYS"/>'
            '<Property name="count" value="7"/>'
            '</Control>'
            '</Controls>'
        )
        controls_elem = ET.fromstring(controls_xml)
        result = _parse_time_window(controls_elem)
        assert result["start_period"] is None
        assert result["end_period"] is None


class TestReverseLocalRoundTrip:
    def test_reverse_local_parse_time_window_captures_period(self):
        from vcfops_extractor.reverse_local import _parse_time_window

        controls_xml = (
            '<Controls>'
            '<Control id="time-interval-selector_id_1" type="time-interval-selector" visible="false">'
            '<Property name="advancedTimeMode" value="true"/>'
            '<Property name="unit" value="DAYS"/>'
            '<Property name="count" value="7"/>'
            '<Property name="startPeriod" value="PREVIOUS"/>'
            '<Property name="endPeriod" value="NOW"/>'
            '</Control>'
            '</Controls>'
        )
        controls_elem = ET.fromstring(controls_xml)
        result = _parse_time_window(controls_elem)
        assert result == {
            "unit": "DAYS",
            "count": 7,
            "advanced_time_mode": True,
            "start_period": "PREVIOUS",
            "end_period": "NOW",
        }
