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
# resourcelist_column_state_wire_format.md §2 (post §1-CORRECTION fix) —
# copied here (not imported from the renderer) so this test independently
# guards against silent corruption of the pasted blob. This is the raw
# capture with an explicit `hidden=b:1^width=n:100` patched onto h2, h4,
# h5, h6, h14 (which the raw capture left unflagged, and an unflagged
# column defaults to VISIBLE — see the doc's §1 CORRECTION). Every other
# byte is identical to the raw capture.
EXPECTED_NAME_ONLY_VALUE = (
    "o%2525253Acolumns%2525253Da%2525253Ao%2525253Aid%2525253Ds%2525253Ah1%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah2%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah3%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah4%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah5%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah6%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah7%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah8%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah9%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah10%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah11%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah12%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah13%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah14%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah15%2525255Ehidden%2525253Db%2525253A0%2525255Eo%2525253Aid%2525253Ds%2525253Ah16%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253AresourceRating%2525255Ehidden%2525253Db%2525253A1%2525255Eo%2525253Aid%2525253Ds%2525253Ah18%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah19%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah20%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah21%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah22%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah23%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah24%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah25%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah26%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah27%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah28%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah29%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah30%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah31%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah32%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah33%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah34%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah35%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah36%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah37%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah38%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah39%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah40%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah41%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah42%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah43%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah44%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah45%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah46%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100%2525255Eo%2525253Aid%2525253Ds%2525253Ah47%2525255Ehidden%2525253Db%2525253A1%2525255Ewidth%2525253Dn%2525253A100"
)

# 5315 bytes: the raw-capture 4244-byte blob plus 5 patched columns
# (h2, h4, h5, h6, h14), each gaining `^hidden=b:1^width=n:100`, re-encoded
# through the same 4-pass depth encoding.
EXPECTED_VALUE_LENGTH = 5315


def _decode_grid_state(value: str) -> str:
    """Undo the ExtJS grid-state depth encoding.

    Per knowledge/context/api-surface/resourcelist_column_state_wire_format.md
    §1's "Encoding note": the blob is `urllib.parse.quote`d 4x on the way
    out, so 4 passes of `urllib.parse.unquote` recover the flat
    `o:columns=a:o:id=s:h1^hidden=b:1^width=n:100^...` grammar.
    """
    import urllib.parse

    decoded = value
    for _ in range(4):
        decoded = urllib.parse.unquote(decoded)
    return decoded


def _decode_columns(value: str) -> dict[str, dict[str, str]]:
    """Parse the decoded grid-state string into {colId: {field: value}}."""
    decoded = _decode_grid_state(value)
    assert decoded.startswith("o:columns=a:")
    body = decoded[len("o:columns=a:"):]
    records = body.split("^o:id=s:")
    records[1:] = [r for r in records[1:]]  # already stripped by split
    columns: dict[str, dict[str, str]] = {}
    for i, rec in enumerate(records):
        rec = rec if i == 0 and rec.startswith("o:id=s:") else rec
        fields = rec.split("^")
        # first field is either "o:id=s:<id>" (i==0) or "<id>" (i>0, since
        # the split already consumed "o:id=s:")
        col_id = fields[0][len("o:id=s:"):] if fields[0].startswith("o:id=s:") else fields[0]
        attrs: dict[str, str] = {}
        for f in fields[1:]:
            if "=" in f:
                key, val = f.split("=", 1)
                attrs[key] = val
        columns[col_id] = attrs
    return columns


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

    def test_every_column_except_h15_is_explicitly_hidden(self, tmp_path):
        """Decode the blob and assert no column relies on an implicit
        default. Per the doc's §1 CORRECTION, an unflagged column defaults
        to VISIBLE, so a true Name-only preset must carry an explicit
        `hidden=b:1` on every column except h15 (Name)."""
        dashboard, dash_obj, widget_obj = _render(tmp_path, "name-only")
        state = widget_obj["states"][0]
        columns = _decode_columns(state["value"])

        assert set(columns) == {f"h{i}" for i in range(1, 48) if i != 17} | {
            "resourceRating"
        }, "unexpected column roster in decoded blob"

        for col_id, attrs in columns.items():
            if col_id == "h15":
                assert attrs.get("hidden") == "b:0", (
                    f"h15 (Name) must be the sole visible column, got "
                    f"hidden={attrs.get('hidden')!r}"
                )
                continue
            assert attrs.get("hidden") == "b:1", (
                f"{col_id} must carry an explicit hidden=b:1 — an unflagged "
                f"column defaults to VISIBLE (see the doc's §1 CORRECTION), "
                f"got attrs={attrs!r}"
            )

    def test_round_trip_only_five_columns_changed_from_raw_capture(self, tmp_path):
        """Decoding the shipped constant must equal the raw-capture decode
        plus exactly the five added hidden flags on h2, h4, h5, h6, h14 —
        every other byte identical."""
        dashboard, dash_obj, widget_obj = _render(tmp_path, "name-only")
        state = widget_obj["states"][0]
        new_columns = _decode_columns(state["value"])

        # The raw capture (pre-fix): h2, h4, h5, h6, h14 carry no `hidden`
        # attribute at all.
        raw_capture_columns = dict(new_columns)
        patched = {"h2", "h4", "h5", "h6", "h14"}
        for col_id in patched:
            raw_capture_columns[col_id] = {}

        # Reconstructing the "old" form (no hidden/width on the 5 columns)
        # and comparing to the new form: only those 5 keys should differ.
        differing = {
            col_id
            for col_id in new_columns
            if raw_capture_columns[col_id] != new_columns[col_id]
        }
        assert differing == patched, (
            f"expected exactly {patched} to differ from the raw capture, "
            f"got {differing}"
        )
        for col_id in patched:
            assert new_columns[col_id] == {"hidden": "b:1", "width": "n:100"}, (
                f"{col_id} must gain exactly hidden=b:1^width=n:100, got "
                f"{new_columns[col_id]!r}"
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
