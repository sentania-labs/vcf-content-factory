"""Phase 16 — renderer regression tests for the two known real-world escapes.

Both bugs shipped in commit 201f44c (compliance build 26) era renderer changes
and were caught in Codex review (PR-14 / PR-15) after corrupting standalone
content-import zips:

  Test A — renderer-defaults leak (fixed by 00d3382):
      _gridster_coords() shifted every widget's (x, y) by +1, treating
      author-facing coords as 0-based when factory YAML is 1-based (matching
      platform exports). The same commit also flipped the global `hidden`
      default to true, so dashboards imported invisible on the content-import
      path. The fix deleted _gridster_coords (coords pass through unchanged)
      and restored hidden default false.

  Test B — localizationKey collision (fixed by 6c59f6b):
      _xml_attribute_item() emitted a localizationKey on the displayName
      Property, derived from the attribute path with no transform awareness.
      Transformed columns of the same metric (AVG / MAX / P95 of
      cpu|demandPct) all shared one key, so key-resolving environments showed
      identical labels. The fix dropped localizationKey from displayName
      entirely — 80+ reference pack views carry plain displayName, zero
      exceptions.

These tests must fail if either pre-fix behavior is re-introduced.
All fixtures are tmp_path-local; no content YAML, network, or install touched.
"""
from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


OWNER_USER_ID = "00000000-0000-0000-0000-000000000001"


def _write_yaml(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False))
    return path


# ---------------------------------------------------------------------------
# Test A — gridsterCoords pass through unchanged; hidden defaults to false
# (regression for 00d3382)
# ---------------------------------------------------------------------------

class TestRendererDefaultsLeak:
    """Coords authored 1-based must reach the wire 1-based (no +1 shift),
    and a dashboard that does not set `hidden:` must render hidden=false."""

    AUTHORED_COORDS = {"x": 1, "y": 1, "w": 6, "h": 4}

    def _render_minimal_dashboard(self, tmp_path: Path) -> dict:
        """Load a one-widget dashboard YAML and return the rendered
        dashboard object from the bundle JSON."""
        from vcfops_dashboards.loader import load_dashboard
        from vcfops_dashboards.render import render_dashboards_bundle_json

        dash_path = _write_yaml(
            tmp_path / "dashboards" / "regression_dash.yaml",
            {
                "name": "Phase16 Regression Dashboard",
                # No `hidden:` key on purpose — the loader default is under test.
                "widgets": [
                    {
                        "id": str(uuid.uuid4()),
                        "type": "TextDisplay",
                        "title": "Coords Probe",
                        "coords": dict(self.AUTHORED_COORDS),
                        "text": "phase16 coords probe",
                    }
                ],
            },
        )
        dashboard = load_dashboard(dash_path, enforce_framework_prefix=False)
        bundle = json.loads(
            render_dashboards_bundle_json([dashboard], {}, OWNER_USER_ID)
        )
        assert len(bundle["dashboards"]) == 1
        return bundle["dashboards"][0]

    def test_gridster_coords_pass_through_unchanged(self, tmp_path):
        """A widget authored at 1-based (1, 1, 6, 4) must render with
        gridsterCoords exactly (1, 1, 6, 4). The pre-fix _gridster_coords
        shifted x and y by +1, overflowing the 12-column grid."""
        dash_obj = self._render_minimal_dashboard(tmp_path)
        widget = dash_obj["widgets"][0]
        assert widget["gridsterCoords"] == self.AUTHORED_COORDS, (
            f"gridsterCoords must pass through unchanged "
            f"(authored {self.AUTHORED_COORDS}), got {widget['gridsterCoords']} "
            f"— a +1 shift means _gridster_coords is back (see 00d3382)"
        )

    def test_hidden_defaults_to_false(self, tmp_path):
        """A dashboard whose YAML does not set `hidden:` must render
        hidden=false. The pre-fix global hidden=true default made dashboards
        import invisible on the content-import path."""
        dash_obj = self._render_minimal_dashboard(tmp_path)
        assert dash_obj["hidden"] is False, (
            "Rendered dashboard 'hidden' must default to false; hidden=true "
            "dashboards import invisible via content-import (see 00d3382)"
        )


# ---------------------------------------------------------------------------
# Test B — no localizationKey on displayName for transformed columns
# (regression for 6c59f6b)
# ---------------------------------------------------------------------------

class TestLocalizationKeyCollision:
    """Two transforms of the same attribute must render distinct plain
    displayName Properties with no localizationKey attribute."""

    DISPLAY_NAMES = ("CPU Demand (Avg)", "CPU Demand (Max)")

    def _render_two_transform_view(self, tmp_path: Path) -> str:
        """Load a view with AVG and MAX columns of the same attribute and
        return the rendered views content.xml."""
        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        view_path = _write_yaml(
            tmp_path / "views" / "regression_view.yaml",
            {
                "name": "Phase16 Regression View",
                "subject": {
                    "adapter_kind": "VMWARE",
                    "resource_kind": "VirtualMachine",
                },
                "time_window": {"unit": "DAYS", "count": 7},
                "columns": [
                    {
                        "attribute": "cpu|demandPct",
                        "display_name": self.DISPLAY_NAMES[0],
                        "transformation": "AVG",
                    },
                    {
                        "attribute": "cpu|demandPct",
                        "display_name": self.DISPLAY_NAMES[1],
                        "transformation": "MAX",
                    },
                ],
            },
        )
        view = load_view(view_path, enforce_framework_prefix=False)
        # sm_scope=[] keeps the render hermetic: no scan of content/supermetrics.
        return render_views_xml([view], sm_scope=[])

    @staticmethod
    def _display_name_properties(xml_text: str) -> list:
        root = ET.fromstring(xml_text)
        return [
            el for el in root.iter("Property")
            if el.get("name") == "displayName"
        ]

    def test_no_localization_key_on_display_name(self, tmp_path):
        """Neither column's displayName Property may carry a localizationKey.
        Pre-fix, both AVG and MAX columns of cpu|demandPct shared the derived
        key 'cpu_demandPct', colliding in key-resolving environments."""
        xml_text = self._render_two_transform_view(tmp_path)
        props = self._display_name_properties(xml_text)
        assert len(props) >= 2, (
            f"Expected displayName Properties for both columns, found "
            f"{len(props)} in rendered XML"
        )
        offenders = [
            (el.get("value"), el.get("localizationKey"))
            for el in props
            if el.get("localizationKey") is not None
        ]
        assert offenders == [], (
            f"displayName Properties must not carry localizationKey "
            f"(reference exports never do; shared keys collide across "
            f"transforms — see 6c59f6b), got: {offenders}"
        )

    def test_both_transformed_columns_present_and_distinct(self, tmp_path):
        """Both transform columns must render, with distinct displayName
        values — the user-visible symptom of the collision was identical
        labels."""
        xml_text = self._render_two_transform_view(tmp_path)
        values = [el.get("value") for el in self._display_name_properties(xml_text)]
        for expected in self.DISPLAY_NAMES:
            assert expected in values, (
                f"Column displayName {expected!r} missing from rendered XML; "
                f"got {values}"
            )
        assert len(set(values)) == len(values), (
            f"displayName values must be distinct across transformed columns, "
            f"got duplicates in {values}"
        )
