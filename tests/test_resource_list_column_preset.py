"""ResourceList `column_preset` — typed "Show Columns" grid-state support.

Wire-format investigation:
knowledge/context/api-surface/resourcelist_column_state_wire_format.md

Covers:
  - `column_preset` absent -> no top-level `states` key on the widget
    (byte-identical to pre-change behavior).
  - `column_preset: name-only` -> a `states` array with exactly one entry,
    `key` templated as `permResGrid_widget_<dashUuid>_<widgetUuid>`, and
    `value` equal to the verbatim captured constant from the investigation
    doc.
  - An unsupported `column_preset` value is rejected at validate time.

All fixtures are tmp_path-local; no content YAML, network, or install touched.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import yaml


OWNER_USER_ID = "00000000-0000-0000-0000-000000000001"

# Same verbatim constant as knowledge/context/api-surface/
# resourcelist_column_state_wire_format.md §2 — copied here (not imported
# from the renderer) so this test independently guards against silent
# corruption of the pasted blob.
EXPECTED_NAME_ONLY_VALUE = (
    "o%3Acolumns%3Da%253Ao%25253Aid%25253Ds%2525253Ah1%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah2%255Eo%25253Aid%25253Ds%2525253Ah3%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah4%255Eo%25253Aid%25253Ds%2525253Ah5%255Eo%25253Aid%25253Ds%2525253Ah6%255Eo%25253Aid%25253Ds%2525253Ah7%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah8%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah9%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah10%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah11%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah12%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah13%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah14%255Eo%25253Aid%25253Ds%2525253Ah15%25255Ehidden%25253Db%2525253A0%255Eo%25253Aid%25253Ds%2525253Ah16%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253AresourceRating%25255Ehidden%25253Db%2525253A1%255Eo%25253Aid%25253Ds%2525253Ah18%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah19%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah20%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah21%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah22%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah23%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah24%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah25%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah26%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah27%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah28%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah29%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah30%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah31%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah32%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah33%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah34%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah35%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah36%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah37%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah38%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah39%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah40%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah41%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah42%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah43%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah44%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah45%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah46%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah47%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100"
)

# 4244 bytes per the investigation doc's TL;DR.
EXPECTED_VALUE_LENGTH = 4244


def _write_yaml(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False))
    return path


def _dashboard_yaml(widget_id: str, column_preset: str | None = None) -> dict:
    widget = {
        "id": widget_id,
        "type": "ResourceList",
        "title": "Probe List",
        "coords": {"x": 1, "y": 1, "w": 6, "h": 6},
        "resource_kinds": [
            {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"}
        ],
    }
    if column_preset is not None:
        widget["column_preset"] = column_preset
    return {
        "name": "Column Preset Probe Dashboard",
        "widgets": [widget],
    }


def _render(tmp_path: Path, column_preset: str | None):
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    widget_id = str(uuid.uuid4())
    dash_path = _write_yaml(
        tmp_path / "dashboards" / "column_preset_probe.yaml",
        _dashboard_yaml(widget_id, column_preset),
    )
    dashboard = load_dashboard(dash_path, enforce_framework_prefix=False)
    bundle = json.loads(
        render_dashboards_bundle_json([dashboard], {}, OWNER_USER_ID)
    )
    dash_obj = bundle["dashboards"][0]
    widget_obj = dash_obj["widgets"][0]
    return dashboard, dash_obj, widget_obj


class TestColumnPresetAbsent:
    """No `column_preset` in YAML -> no top-level `states` key on the
    rendered widget (current/unchanged behavior, byte-identical corpus)."""

    def test_no_states_key_when_absent(self, tmp_path):
        _, _, widget_obj = self._render(tmp_path)
        assert "states" not in widget_obj, (
            f"ResourceList widget without column_preset must not carry a "
            f"top-level 'states' key, got: {widget_obj.get('states')!r}"
        )

    def _render(self, tmp_path):
        return _render(tmp_path, None)


class TestColumnPresetNameOnly:
    """`column_preset: name-only` -> a states[] array with the templated
    key and the verbatim captured constant value."""

    def test_states_key_present_with_one_entry(self, tmp_path):
        dashboard, dash_obj, widget_obj = _render(tmp_path, "name-only")
        assert "states" in widget_obj, "expected top-level 'states' key on the widget"
        assert isinstance(widget_obj["states"], list)
        assert len(widget_obj["states"]) == 1

    def test_states_key_templated_correctly(self, tmp_path):
        dashboard, dash_obj, widget_obj = _render(tmp_path, "name-only")
        state = widget_obj["states"][0]
        expected_key = f"permResGrid_widget_{dash_obj['id']}_{widget_obj['id']}"
        assert state["key"] == expected_key, (
            f"states[].key must be permResGrid_widget_<dashUuid>_<widgetUuid>, "
            f"got {state['key']!r}"
        )

    def test_states_value_matches_verbatim_constant(self, tmp_path):
        dashboard, dash_obj, widget_obj = _render(tmp_path, "name-only")
        state = widget_obj["states"][0]
        assert len(state["value"]) == EXPECTED_VALUE_LENGTH, (
            f"states[].value length mismatch: expected {EXPECTED_VALUE_LENGTH} "
            f"bytes per the investigation doc, got {len(state['value'])}"
        )
        assert state["value"] == EXPECTED_NAME_ONLY_VALUE, (
            "states[].value must be byte-identical to the captured Name-only "
            "constant in knowledge/context/api-surface/"
            "resourcelist_column_state_wire_format.md §2"
        )


class TestColumnPresetInvalid:
    """An unsupported column_preset value is a validation error, not a
    silently-passed-through raw value."""

    def test_invalid_preset_raises_validation_error(self, tmp_path):
        from vcfops_dashboards.loader import load_dashboard, DashboardValidationError

        widget_id = str(uuid.uuid4())
        dash_path = _write_yaml(
            tmp_path / "dashboards" / "column_preset_invalid.yaml",
            _dashboard_yaml(widget_id, "everything"),
        )
        dashboard = load_dashboard(dash_path, enforce_framework_prefix=False)
        with pytest.raises(DashboardValidationError, match="column_preset"):
            dashboard.validate({}, enforce_framework_prefix=False)

    def test_column_preset_on_non_resource_list_rejected(self, tmp_path):
        from vcfops_dashboards.loader import load_dashboard, DashboardValidationError

        dash_path = _write_yaml(
            tmp_path / "dashboards" / "column_preset_wrong_widget.yaml",
            {
                "name": "Column Preset Wrong Widget Dashboard",
                "widgets": [
                    {
                        "id": str(uuid.uuid4()),
                        "type": "TextDisplay",
                        "title": "Not A List",
                        "coords": {"x": 1, "y": 1, "w": 6, "h": 4},
                        "text": "n/a",
                        "column_preset": "name-only",
                    }
                ],
            },
        )
        dashboard = load_dashboard(dash_path, enforce_framework_prefix=False)
        with pytest.raises(DashboardValidationError, match="column_preset"):
            dashboard.validate({}, enforce_framework_prefix=False)
