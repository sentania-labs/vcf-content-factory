"""Section widget: loader, validation, and wire shape.

Wire shape is the Suite API export form (see ``SectionConfig`` in
``vcfops_dashboards/loader.py`` and
knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md
§3): a full-width (12 col), one-row, ``height: 0`` header entry with
``collapsed``, plus a config block whose ``widgets[]`` list is the
membership (member widget UUIDs), authoritative at load. Membership is
inferred by row order (every widget below the Section until the next
Section) unless authored. Fixtures use public VMWARE kinds only;
tmp_path-local, no network.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

OWNER = "00000000-0000-0000-0000-000000000001"


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _rl(local_id: str, y: int, title: str = "VMs") -> dict:
    return {
        "id": local_id,
        "type": "ResourceList",
        "title": title,
        "coords": {"x": 1, "y": y, "w": 6, "h": 4},
        "resource_kinds": [{"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"}],
    }


def _render(tmp_path: Path, dash: dict) -> dict:
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    d = load_dashboard(_write(tmp_path / "dashboards" / "d.yaml", dash))
    d.validate({})
    bundle = json.loads(render_dashboards_bundle_json([d], {}, OWNER))
    return bundle["dashboards"][0]


def _base(widgets: list, **extra) -> dict:
    return {
        "name": "[VCF Content Factory] Section Test",
        "description": "",
        "widgets": widgets,
        "interactions": [],
        **extra,
    }


class TestSectionWire:
    def test_section_wire_shape(self, tmp_path):
        obj = _render(tmp_path, _base([
            _rl("top", 1),
            {"id": "sec_a", "type": "Section", "title": "Capacity",
             "coords": {"x": 1, "y": 5}, "collapsed": True},
            _rl("a1", 6),
            _rl("a2", 6),
            {"id": "sec_b", "type": "Section", "title": "Health", "coords": {"x": 1, "y": 10}},
            _rl("b1", 11),
        ]))
        by_title = {w["title"]: w for w in obj["widgets"]}
        sec = by_title["Capacity"]
        assert sec["type"] == "Section"
        assert sec["collapsed"] is True
        assert sec["height"] == 0
        assert "isLoading" not in sec and "description" not in sec
        assert sec["gridsterCoords"] == {"x": 1, "y": 5, "w": 12, "h": 1}
        assert sec["config"]["title"] == "Capacity"
        assert sec["config"]["titleLocalized"] == "Capacity"
        assert sec["config"]["description"] == ""
        assert set(sec["config"]) == {"title", "titleLocalized", "description", "widgets"}
        # membership inferred by row order: a1, a2 only (top is above)
        a_members = sec["config"]["widgets"]
        assert len(a_members) == 2
        expected = [w["id"] for w in obj["widgets"] if w["type"] == "ResourceList"][1:3]
        assert a_members == expected
        # second section owns only b1; default collapsed is False
        sec_b = by_title["Health"]
        assert sec_b["collapsed"] is False
        assert sec_b["config"]["widgets"] == [obj["widgets"][-1]["id"]]
        # no viewDetails on a Section
        assert "viewDetails" not in sec["config"]

    def test_membership_is_row_order_not_declaration_order(self, tmp_path):
        """Computed child list follows gridster rows until the next Section,
        exactly as the UI recomputes it, regardless of YAML order."""
        rows = {"above": 1, "b_low": 30, "a_right": 11, "a_left": 11, "a_next": 15, "b_top": 21}
        obj = _render(tmp_path, _base([
            _rl("b_low", rows["b_low"], "b_low"),
            {"id": "sec_b", "type": "Section", "title": "B", "coords": {"x": 1, "y": 20}},
            {**_rl("a_right", rows["a_right"], "a_right"), "coords": {"x": 7, "y": 11, "w": 6, "h": 4}},
            _rl("a_next", rows["a_next"], "a_next"),
            {"id": "sec_a", "type": "Section", "title": "A", "coords": {"x": 1, "y": 10}},
            _rl("above", rows["above"], "above"),
            _rl("a_left", rows["a_left"], "a_left"),
            _rl("b_top", rows["b_top"], "b_top"),
        ]))
        by_title = {w["title"]: w for w in obj["widgets"]}
        ids = lambda *titles: [by_title[t]["id"] for t in titles]
        # A owns rows 11..19, ordered (y, x): a_left (x=1), a_right (x=7), a_next
        assert by_title["A"]["config"]["widgets"] == ids("a_left", "a_right", "a_next")
        # B owns everything below row 20
        assert by_title["B"]["config"]["widgets"] == ids("b_top", "b_low")
        # a widget above the first Section belongs to none
        assert by_title["above"]["id"] not in (
            by_title["A"]["config"]["widgets"] + by_title["B"]["config"]["widgets"]
        )

    def test_section_width_and_height_forced(self, tmp_path):
        obj = _render(tmp_path, _base([
            {"id": "s", "type": "Section", "title": "S",
             "coords": {"x": 1, "y": 2, "w": 4, "h": 9}},
            _rl("r", 3),
        ]))
        sec = obj["widgets"][0]
        assert sec["gridsterCoords"] == {"x": 1, "y": 2, "w": 12, "h": 1}

    def test_section_y_only_coords(self, tmp_path):
        obj = _render(tmp_path, _base([
            {"id": "s", "type": "Section", "title": "S", "coords": {"y": 2}},
            _rl("r", 3),
        ]))
        assert obj["widgets"][0]["gridsterCoords"] == {"x": 1, "y": 2, "w": 12, "h": 1}

    @pytest.mark.parametrize("x", [0, 2, 5, 12])
    def test_section_x_other_than_one_rejected(self, tmp_path, x):
        """w is forced to 12, so any other x overflows the 12-column grid."""
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        with pytest.raises(DashboardValidationError, match="starts at x: 1"):
            load_dashboard(_write(tmp_path / "d.yaml", _base([
                {"id": "s", "type": "Section", "title": "S", "coords": {"x": x, "y": 2}},
                _rl("r", 3),
            ])))

    def test_widget_on_section_row_rejected(self, tmp_path):
        """A data widget on a Section's row would belong to no Section."""
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        with pytest.raises(DashboardValidationError, match="shares row y: 2 with Section 's'"):
            load_dashboard(_write(tmp_path / "d.yaml", _base([
                {"id": "s", "type": "Section", "title": "S", "coords": {"x": 1, "y": 2}},
                {**_rl("r", 2), "coords": {"x": 7, "y": 2, "w": 6, "h": 4}},
            ])))

    def test_two_sections_on_one_row_rejected(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        with pytest.raises(DashboardValidationError, match="shares row y: 1 with Section"):
            load_dashboard(_write(tmp_path / "d.yaml", _base([
                {"id": "s1", "type": "Section", "title": "A", "coords": {"x": 1, "y": 1}},
                {"id": "s2", "type": "Section", "title": "B", "coords": {"x": 1, "y": 1}},
                _rl("r", 2),
            ])))

    def test_explicit_membership(self, tmp_path):
        obj = _render(tmp_path, _base([
            {"id": "s", "type": "Section", "title": "S", "coords": {"x": 1, "y": 1},
             "widgets": ["r2"]},
            _rl("r1", 2),
            _rl("r2", 2),
        ]))
        sec = obj["widgets"][0]
        assert sec["config"]["widgets"] == [obj["widgets"][2]["id"]]

    def test_section_absent_output_unchanged(self, tmp_path):
        """A dashboard with no Section renders no Section-specific keys."""
        obj = _render(tmp_path, _base([_rl("r1", 1)]))
        assert all(w["type"] != "Section" for w in obj["widgets"])
        assert "widgets" not in obj["widgets"][0]["config"]


class TestSectionValidation:
    @pytest.mark.parametrize("bad_key,bad_val", [
        ("metrics", [{"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine",
                      "metric_key": "cpu|usage_average"}]),
        ("view", "[VCF Content Factory] Some View"),
        ("resource_kinds", [{"adapter_kind": "VMWARE", "resource_kind": "HostSystem"}]),
        ("pin", {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"}),
        ("self_provider", True),
    ])
    def test_section_rejects_data_keys(self, tmp_path, bad_key, bad_val):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        path = _write(tmp_path / "d.yaml", _base([
            {"id": "s", "type": "Section", "title": "S", "coords": {"x": 1, "y": 1},
             bad_key: bad_val},
        ]))
        with pytest.raises(DashboardValidationError, match="Section must not carry"):
            load_dashboard(path)

    def test_section_rejects_interactions(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        d = load_dashboard(_write(tmp_path / "d.yaml", _base(
            [
                {"id": "s", "type": "Section", "title": "S", "coords": {"x": 1, "y": 1}},
                _rl("r", 2),
            ],
            interactions=[{"from": "r", "to": "s"}],
        )))
        with pytest.raises(DashboardValidationError, match="Sections carry no interactions"):
            d.validate({})

    def test_unknown_member_rejected(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        d = load_dashboard(_write(tmp_path / "d.yaml", _base([
            {"id": "s", "type": "Section", "title": "S", "coords": {"x": 1, "y": 1},
             "widgets": ["nope"]},
            _rl("r", 2),
        ])))
        with pytest.raises(DashboardValidationError, match="not a widget on this dashboard"):
            d.validate({})

    def test_nested_section_rejected(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        d = load_dashboard(_write(tmp_path / "d.yaml", _base([
            {"id": "s1", "type": "Section", "title": "S1", "coords": {"x": 1, "y": 1},
             "widgets": ["s2"]},
            {"id": "s2", "type": "Section", "title": "S2", "coords": {"x": 1, "y": 2}},
        ])))
        with pytest.raises(DashboardValidationError, match="Sections do not nest"):
            d.validate({})

    def test_collapsed_must_be_bool(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        path = _write(tmp_path / "d.yaml", _base([
            {"id": "s", "type": "Section", "title": "S", "coords": {"x": 1, "y": 1},
             "collapsed": "true"},
        ]))
        with pytest.raises(DashboardValidationError, match="collapsed must be a bool"):
            load_dashboard(path)

    def test_collapsed_only_on_section(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        path = _write(tmp_path / "d.yaml", _base([
            {**_rl("r", 1), "collapsed": True},
        ]))
        with pytest.raises(DashboardValidationError, match="only supported on Section"):
            load_dashboard(path)
