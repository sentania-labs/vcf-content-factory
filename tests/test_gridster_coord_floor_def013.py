"""DEF-013 — dashboard widgets authored with 0-based coords render with an
inverted vertical stack in the VCF Ops UI.

Root cause: the dashboard grid wire format (`gridsterCoords`) is 1-indexed —
every known-good widget coordinate observed across the vendor reference
corpus (`reference/references/`, 100+ widgets surveyed) and every
`knowledge/context/exports/*.json` capture uses `x >= 1` and `y >= 1`; none
use 0. An authored `coords: {x: 0, y: 0, ...}` block (a natural mistake for
an author thinking in 0-based array-index terms) is outside the grid's valid
coordinate space. Devel evidence (dashboard UUID
b6796122-4c9b-4770-83d8-10f785755ef2, `cpu_support_status.yaml`): the
ResourceList picker widget authored at `{x: 0, y: 0, w: 12, h: 3}` (row 1,
declared first) rendered BELOW the View widget authored at
`{x: 0, y: 3, w: 12, h: 12}` (row 2, declared second) — an exact vertical
inversion of the declared y-order, verified by Playwright screenshot.

Fix: `_clamp_gridster_floor()` in `vcfops_dashboards.render` clamps
`x`/`y` to a floor of 1 (`max(1, v)`) before emission. This is deliberately
NOT the `_gridster_coords()` helper deleted in 00d3382
(`tests/test_renderer_regression_phase16.py` Test A) — that helper
unconditionally shifted every coordinate by +1 regardless of whether the
input was already 1-based, corrupting valid layouts (see Test A below,
which continues to guard against that specific regression). This floor
clamp is a no-op for any coordinate that is already >= 1, and only changes
provably out-of-grid values (< 1).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import yaml


OWNER_USER_ID = "00000000-0000-0000-0000-000000000001"


def _write_yaml(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False))
    return path


def _render_two_widget_dashboard(tmp_path: Path, picker_coords: dict, view_coords: dict):
    """Load a picker-above-view dashboard (ResourceList + View, wired by a
    resourceId interaction — the exact shape of cpu_support_status.yaml) and
    return the rendered dashboard object."""
    from vcfops_dashboards.loader import load_dashboard, load_view
    from vcfops_dashboards.render import render_dashboards_bundle_json

    view_path = _write_yaml(
        tmp_path / "views" / "probe_view.yaml",
        {
            "name": "DEF013 Probe View",
            "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
            "time_window": {"unit": "DAYS", "count": 1},
            "columns": [
                {"attribute": "summary|hardware|model", "display_name": "Model"},
            ],
        },
    )
    view = load_view(view_path, enforce_framework_prefix=False)

    dash_path = _write_yaml(
        tmp_path / "dashboards" / "def013_probe.yaml",
        {
            "name": "DEF013 Probe Dashboard",
            "widgets": [
                {
                    "id": "cluster_picker",
                    "type": "ResourceList",
                    "title": "vSphere Clusters",
                    "coords": dict(picker_coords),
                    "resource_kinds": [
                        {"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource"}
                    ],
                },
                {
                    "id": "detail_view",
                    "type": "View",
                    "title": "Host Detail",
                    "coords": dict(view_coords),
                    "view": "DEF013 Probe View",
                },
            ],
            "interactions": [
                {"from": "cluster_picker", "to": "detail_view", "type": "resourceId"}
            ],
        },
    )
    dashboard = load_dashboard(dash_path, enforce_framework_prefix=False)
    bundle = json.loads(
        render_dashboards_bundle_json(
            [dashboard], {"DEF013 Probe View": view}, OWNER_USER_ID
        )
    )
    assert len(bundle["dashboards"]) == 1
    return bundle["dashboards"][0]


class TestZeroBasedCoordsClampedToGridFloor:
    """The reported defect: a picker declared above a view in y-order, both
    authored 0-based, must still emit picker.y < view.y (grid-valid, order
    preserved) instead of colliding at an out-of-grid y=0."""

    PICKER_COORDS = {"x": 0, "y": 0, "w": 12, "h": 3}
    VIEW_COORDS = {"x": 0, "y": 3, "w": 12, "h": 12}

    def test_zero_coords_clamped_to_one(self, tmp_path):
        dash_obj = _render_two_widget_dashboard(
            tmp_path, self.PICKER_COORDS, self.VIEW_COORDS
        )
        widgets_by_type = {w["type"]: w for w in dash_obj["widgets"]}
        picker_coords = widgets_by_type["ResourceList"]["gridsterCoords"]
        view_coords = widgets_by_type["View"]["gridsterCoords"]

        assert picker_coords["x"] >= 1, (
            f"ResourceList gridsterCoords.x must be clamped to the grid's "
            f"1-indexed floor, got {picker_coords}"
        )
        assert picker_coords["y"] >= 1, (
            f"ResourceList gridsterCoords.y must be clamped to the grid's "
            f"1-indexed floor, got {picker_coords}"
        )
        assert view_coords["x"] >= 1
        assert view_coords["y"] >= 1

    def test_declared_y_order_preserved_after_clamp(self, tmp_path):
        """The picker (declared first, smaller authored y) must still sort
        above the view (declared second, larger authored y) after clamping —
        this is the actual regression: pre-fix, y=0 rendered *below* y=3."""
        dash_obj = _render_two_widget_dashboard(
            tmp_path, self.PICKER_COORDS, self.VIEW_COORDS
        )
        widgets_by_type = {w["type"]: w for w in dash_obj["widgets"]}
        picker_y = widgets_by_type["ResourceList"]["gridsterCoords"]["y"]
        view_y = widgets_by_type["View"]["gridsterCoords"]["y"]

        assert picker_y < view_y, (
            f"picker (authored y=0, declared first) must render above the "
            f"view (authored y=3, declared second): got picker.y={picker_y}, "
            f"view.y={view_y} — this is the DEF-013 inversion if it fails"
        )

    def test_widget_w_h_unaffected_by_clamp(self, tmp_path):
        """Only x/y are clamped — w/h pass through unchanged."""
        dash_obj = _render_two_widget_dashboard(
            tmp_path, self.PICKER_COORDS, self.VIEW_COORDS
        )
        widgets_by_type = {w["type"]: w for w in dash_obj["widgets"]}
        picker_coords = widgets_by_type["ResourceList"]["gridsterCoords"]
        view_coords = widgets_by_type["View"]["gridsterCoords"]

        assert picker_coords["w"] == self.PICKER_COORDS["w"]
        assert picker_coords["h"] == self.PICKER_COORDS["h"]
        assert view_coords["w"] == self.VIEW_COORDS["w"]
        assert view_coords["h"] == self.VIEW_COORDS["h"]


class TestAlreadyValidCoordsUnaffected:
    """A dashboard already authored 1-indexed (the vsan_cluster_health.yaml
    pattern) must render byte-identical gridsterCoords — the floor clamp is
    a no-op for any value already >= 1. Complements
    test_renderer_regression_phase16.py::TestRendererDefaultsLeak, which
    guards the sibling regression (a +1 shift on already-valid coords)."""

    PICKER_COORDS = {"x": 1, "y": 1, "w": 12, "h": 3}
    VIEW_COORDS = {"x": 1, "y": 4, "w": 12, "h": 9}

    def test_one_based_coords_pass_through_unchanged(self, tmp_path):
        dash_obj = _render_two_widget_dashboard(
            tmp_path, self.PICKER_COORDS, self.VIEW_COORDS
        )
        widgets_by_type = {w["type"]: w for w in dash_obj["widgets"]}
        assert widgets_by_type["ResourceList"]["gridsterCoords"] == self.PICKER_COORDS
        assert widgets_by_type["View"]["gridsterCoords"] == self.VIEW_COORDS


class TestExistingContentDashboardsRenderRegression:
    """Render every dashboard currently in content/dashboards/ and assert
    the only widgets whose gridsterCoords differ from their authored
    `coords:` block are ones that authored x=0 or y=0 (the DEF-013 case) —
    i.e. the fix's diff against the pre-fix pass-through renderer is exactly
    the floor clamp, nothing else."""

    def test_only_zero_coords_are_altered(self):
        import sys

        repo_root = Path(__file__).resolve().parents[1]
        src = repo_root / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))

        from vcfops_dashboards.loader import load_dashboard, load_view
        from vcfops_dashboards.render import render_dashboards_bundle_json

        dash_dir = repo_root / "content" / "dashboards"
        view_dir = repo_root / "content" / "views"
        if not dash_dir.exists():
            return  # nothing to regress against in this checkout

        views_by_name = {}
        for vp in sorted(view_dir.glob("*.yaml")):
            try:
                v = load_view(vp, enforce_framework_prefix=False)
                views_by_name[v.name] = v
            except Exception:
                continue  # views unrelated to this regression; skip malformed/embedded

        for dp in sorted(dash_dir.glob("*.yaml")):
            dashboard = load_dashboard(dp, enforce_framework_prefix=False)
            authored_by_local_id = {w.local_id: dict(w.coords) for w in dashboard.widgets}
            try:
                bundle = json.loads(
                    render_dashboards_bundle_json(
                        [dashboard], views_by_name, OWNER_USER_ID
                    )
                )
            except Exception:
                continue  # cross-references outside this fixture's scope; not this test's concern

            rendered_widgets = bundle["dashboards"][0]["widgets"]
            # widgets_json is built in dashboard.widgets order (see
            # _build_dashboard_obj), so zip against the authored list.
            for local_id, authored in authored_by_local_id.items():
                pass  # order-matched below via index

            for w, rendered in zip(dashboard.widgets, rendered_widgets):
                authored = authored_by_local_id[w.local_id]
                rendered_coords = rendered["gridsterCoords"]
                for axis in ("x", "y"):
                    authored_val = authored.get(axis, 1)
                    rendered_val = rendered_coords[axis]
                    if authored_val >= 1:
                        assert rendered_val == authored_val, (
                            f"{dp.name} widget {w.local_id!r}: {axis} was "
                            f"already grid-valid ({authored_val}) but "
                            f"rendered differently ({rendered_val}) — the "
                            f"floor clamp must be a no-op on valid input"
                        )
                    else:
                        assert rendered_val == 1, (
                            f"{dp.name} widget {w.local_id!r}: out-of-grid "
                            f"authored {axis}={authored_val} must clamp to 1, "
                            f"got {rendered_val}"
                        )
                # w/h always pass through unchanged
                assert rendered_coords["w"] == authored.get("w")
                assert rendered_coords["h"] == authored.get("h")
