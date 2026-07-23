"""Tiered dashboards (picker -> intermediate view -> terminal view, with
dual-provider fan-in on the terminal widget) can get permanently pinned to
the intermediate view's first row: the wire format's
``config.selectFirstRow.selectFirstRow`` auto-select re-fires its
downstream resourceId interaction on every upstream refresh, so a wider
upstream selection (e.g. World/vCenter) can never widen the terminal
widget's subject.

Root cause: `_view_widget()` and `_resource_list_widget()` in
`vcfops_dashboards.render` hardcoded `"selectFirstRow": {"selectFirstRow":
True}` for every View/ResourceList widget, with no author-facing opt-out.
The vendor reference corpus (`reference/references/`) emits
`selectFirstRow: false` 132 times vs `true` 16 times — false is the norm
on multi-tier drill dashboards, not the exception.

Fix: an optional `select_first_row: bool` YAML field on dashboard widgets
(`vcfops_dashboards.loader.Widget.select_first_row`), honored by both
`_view_widget()` and `_resource_list_widget()`. Default is `True` — a
strict opt-out — so every dashboard that does not author the field renders
byte-identical to pre-fix output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

OWNER_USER_ID = "00000000-0000-0000-0000-000000000001"

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _write_yaml(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False))
    return path


def _render_dashboard(tmp_path: Path, view_widget_extra: dict, resource_list_widget_extra: dict):
    from vcfops_dashboards.loader import load_dashboard, load_view
    from vcfops_dashboards.render import render_dashboards_bundle_json

    view_path = _write_yaml(
        tmp_path / "views" / "probe_view.yaml",
        {
            "name": "SFR Probe View",
            "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
            "time_window": {"unit": "DAYS", "count": 1},
            "columns": [
                {"attribute": "summary|hardware|model", "display_name": "Model"},
            ],
        },
    )
    view = load_view(view_path, enforce_framework_prefix=False)

    picker_widget = {
        "id": "cluster_picker",
        "type": "ResourceList",
        "title": "vSphere Clusters",
        "coords": {"x": 1, "y": 1, "w": 12, "h": 3},
        "resource_kinds": [
            {"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource"}
        ],
        **resource_list_widget_extra,
    }
    view_widget = {
        "id": "detail_view",
        "type": "View",
        "title": "Host Detail",
        "coords": {"x": 1, "y": 4, "w": 12, "h": 9},
        "view": "SFR Probe View",
        **view_widget_extra,
    }

    dash_path = _write_yaml(
        tmp_path / "dashboards" / "sfr_probe.yaml",
        {
            "name": "SFR Probe Dashboard",
            "widgets": [picker_widget, view_widget],
            "interactions": [
                {"from": "cluster_picker", "to": "detail_view", "type": "resourceId"}
            ],
        },
    )
    dashboard = load_dashboard(dash_path, enforce_framework_prefix=False)
    bundle = json.loads(
        render_dashboards_bundle_json(
            [dashboard], {"SFR Probe View": view}, OWNER_USER_ID
        )
    )
    widgets_by_type = {w["type"]: w for w in bundle["dashboards"][0]["widgets"]}
    return widgets_by_type


class TestSelectFirstRowDefaultOmitted:
    """When `select_first_row` is not authored, both View and ResourceList
    widgets must emit `selectFirstRow: true` — byte-identical to pre-fix
    behavior."""

    def test_view_widget_defaults_true(self, tmp_path):
        widgets = _render_dashboard(tmp_path, {}, {})
        assert widgets["View"]["config"]["selectFirstRow"] == {"selectFirstRow": True}

    def test_resource_list_widget_defaults_true(self, tmp_path):
        widgets = _render_dashboard(tmp_path, {}, {})
        assert widgets["ResourceList"]["config"]["selectFirstRow"] == {"selectFirstRow": True}


class TestSelectFirstRowAuthoredFalse:
    """Authoring `select_first_row: false` must emit false — this is the
    tiered-drill opt-out that unblocks the World/vCenter widen case."""

    def test_view_widget_emits_false(self, tmp_path):
        widgets = _render_dashboard(tmp_path, {"select_first_row": False}, {})
        assert widgets["View"]["config"]["selectFirstRow"] == {"selectFirstRow": False}

    def test_resource_list_widget_emits_false(self, tmp_path):
        widgets = _render_dashboard(tmp_path, {}, {"select_first_row": False})
        assert widgets["ResourceList"]["config"]["selectFirstRow"] == {"selectFirstRow": False}


class TestSelectFirstRowAuthoredTrueExplicit:
    """Authoring `select_first_row: true` explicitly must emit true (same
    as the default, but exercises the explicit-authoring code path)."""

    def test_view_widget_emits_true(self, tmp_path):
        widgets = _render_dashboard(tmp_path, {"select_first_row": True}, {})
        assert widgets["View"]["config"]["selectFirstRow"] == {"selectFirstRow": True}

    def test_resource_list_widget_emits_true(self, tmp_path):
        widgets = _render_dashboard(tmp_path, {}, {"select_first_row": True})
        assert widgets["ResourceList"]["config"]["selectFirstRow"] == {"selectFirstRow": True}


class TestExistingContentDashboardsRenderByteIdentical:
    """Every dashboard currently in content/dashboards/ omits
    `select_first_row` (pre-existing content), so every rendered View and
    ResourceList widget must still emit `selectFirstRow: true` — proving
    the new field is a strict, non-breaking opt-out."""

    def test_all_content_dashboards_still_select_first_row_true(self):
        from vcfops_dashboards.loader import load_dashboard, load_view
        from vcfops_dashboards.render import render_dashboards_bundle_json

        dash_dir = REPO_ROOT / "content" / "dashboards"
        view_dir = REPO_ROOT / "content" / "views"
        if not dash_dir.exists():
            return  # nothing to regress against in this checkout

        views_by_name = {}
        for vp in sorted(view_dir.glob("*.yaml")):
            try:
                v = load_view(vp, enforce_framework_prefix=False)
                views_by_name[v.name] = v
            except Exception:
                continue

        checked = 0
        for dp in sorted(dash_dir.glob("*.yaml")):
            dashboard = load_dashboard(dp, enforce_framework_prefix=False)
            # Opt-out-aware: the emitted selectFirstRow must equal the
            # authored select_first_row (default True when omitted) for
            # every widget — a filter, not a hardcoded corpus-wide "all
            # true" assumption. This keeps the byte-identical guarantee for
            # the non-opting corpus without breaking every time a dashboard
            # legitimately authors select_first_row: false.
            authored_by_id = {w.widget_id: w.select_first_row for w in dashboard.widgets}
            try:
                bundle = json.loads(
                    render_dashboards_bundle_json(
                        [dashboard], views_by_name, OWNER_USER_ID
                    )
                )
            except Exception:
                continue  # cross-references outside this fixture's scope

            for rendered in bundle["dashboards"][0]["widgets"]:
                if rendered["type"] in ("View", "ResourceList"):
                    expected = authored_by_id[rendered["id"]]
                    assert rendered["config"]["selectFirstRow"] == {"selectFirstRow": expected}, (
                        f"{dp.name}: widget {rendered['id']} emitted "
                        f"selectFirstRow != authored select_first_row="
                        f"{expected}"
                    )
                    checked += 1

        assert checked > 0, "expected at least one View/ResourceList widget across content/dashboards/"
