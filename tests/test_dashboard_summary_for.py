"""`summary_for` declaration, validation, resource kind id, and bind flow.

Mechanism: knowledge/context/api-surface/summary_dashboard_assignment.md
(UI association; binding is a template COPY) and
summary_dashboard_pak_binding.md (pak route). The bind flow is exercised
against a fake UI client only; nothing here touches a live instance.
Public VMWARE kinds only.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _summary_dash(name="[VCF Content Factory] Host Summary", summary_for="VMWARE:HostSystem",
                  widgets=None, dash_id="0f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a4b") -> dict:
    return {
        "id": dash_id,
        "name": name,
        "description": "",
        "summary_for": summary_for,
        "widgets": widgets if widgets is not None else [
            {"id": "kpi", "type": "Scoreboard", "title": "CPU",
             "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
             "metrics": [{"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                          "metric_key": "cpu|usage_average", "metric_name": "CPU"}]},
            {"id": "av", "type": "AlertVolume", "title": "Alerts",
             "coords": {"x": 5, "y": 1, "w": 4, "h": 4}},
        ],
        "interactions": [],
    }


# ---------------------------------------------------------------------------
# Loader / validation
# ---------------------------------------------------------------------------

class TestSummaryForLoader:
    def test_loads_and_parses(self, tmp_path):
        from vcfops_dashboards.loader import load_dashboard

        d = load_dashboard(_write(tmp_path / "d.yaml", _summary_dash()))
        d.validate({})
        assert d.summary_for == ["VMWARE:HostSystem"]
        assert d.summary_kinds == [("VMWARE", "HostSystem")]

    @pytest.mark.parametrize("raw", ["VMWARE : HostSystem", " VMWARE:HostSystem ", "VMWARE:  HostSystem"])
    def test_stored_normalized(self, tmp_path, raw):
        """Inner whitespace is stripped before storage: the pak installer
        splits dashboards.properties on ':' without trimming."""
        from vcfops_dashboards.loader import load_dashboard

        d = load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(summary_for=raw)))
        assert d.summary_for == ["VMWARE:HostSystem"]

    def test_duplicate_target_rejected_by_load_all(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError, load_all

        _write(tmp_path / "dashboards" / "a.yaml", _summary_dash(name="[VCF Content Factory] A"))
        _write(tmp_path / "dashboards" / "b.yaml", _summary_dash(
            name="[VCF Content Factory] B", summary_for="VMWARE : HostSystem",
            dash_id="1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"))
        (tmp_path / "views").mkdir()
        with pytest.raises(DashboardValidationError, match="claimed by both"):
            load_all(tmp_path / "views", tmp_path / "dashboards")

    def test_distinct_targets_load(self, tmp_path):
        from vcfops_dashboards.loader import load_all

        _write(tmp_path / "dashboards" / "a.yaml", _summary_dash(name="[VCF Content Factory] A"))
        _write(tmp_path / "dashboards" / "b.yaml", _summary_dash(
            name="[VCF Content Factory] B", summary_for="VMWARE:VirtualMachine",
            dash_id="1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"))
        (tmp_path / "views").mkdir()
        _views, dashboards = load_all(tmp_path / "views", tmp_path / "dashboards")
        assert sorted(d.summary_for[0] for d in dashboards) == ["VMWARE:HostSystem", "VMWARE:VirtualMachine"]

    def test_absent_is_none(self, tmp_path):
        from vcfops_dashboards.loader import load_dashboard

        data = _summary_dash()
        del data["summary_for"]
        d = load_dashboard(_write(tmp_path / "d.yaml", data))
        d.validate({})
        assert d.summary_for is None and d.summary_kinds == []

    @pytest.mark.parametrize("bad", ["VMWARE", "VMWARE:Host:System", ":HostSystem", "VMWARE:", " : ",
                                     "VMWARE:HostSystem,VMWARE", ["VMWARE:HostSystem", "VMWARE:Host:System"]])
    def test_token_count_enforced(self, tmp_path, bad):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        with pytest.raises(DashboardValidationError, match="two non-empty colon-separated tokens"):
            load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(summary_for=bad)))

    def test_non_string_rejected(self, tmp_path):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        with pytest.raises(DashboardValidationError, match="summary_for must be a string"):
            load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(summary_for=42)))
        with pytest.raises(DashboardValidationError, match="summary_for must be a string"):
            load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(summary_for={"a": "b"})))
        # a list of bare tokens is a list of malformed entries, not a pair
        with pytest.raises(DashboardValidationError, match="two non-empty colon-separated tokens"):
            load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(summary_for=["VMWARE", "HostSystem"])))

    # -- many kinds on one dashboard ----------------------------------------

    THREE = ["VMWARE:HostSystem", "VMWARE:VirtualMachine", "VMWARE:Datastore"]

    def test_list_form(self, tmp_path):
        from vcfops_dashboards.loader import load_dashboard

        d = load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(summary_for=list(self.THREE))))
        d.validate({})
        assert d.summary_for == self.THREE
        assert d.summary_kinds == [("VMWARE", "HostSystem"), ("VMWARE", "VirtualMachine"),
                                   ("VMWARE", "Datastore")]

    def test_comma_string_normalizes_to_list(self, tmp_path):
        """The same shape the pak installer parses; whitespace around
        commas and colons is stripped, order preserved."""
        from vcfops_dashboards.loader import load_dashboard

        d = load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(
            summary_for="VMWARE:HostSystem, VMWARE : VirtualMachine ,VMWARE:Datastore")))
        assert d.summary_for == self.THREE

    @pytest.mark.parametrize("dup", [
        "VMWARE:HostSystem,VMWARE:HostSystem",
        ["VMWARE:HostSystem", "VMWARE:VirtualMachine", "VMWARE : HostSystem"],
    ])
    def test_duplicate_within_dashboard_rejected(self, tmp_path, dup):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        with pytest.raises(DashboardValidationError, match="more than once"):
            load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(summary_for=dup)))

    def test_duplicate_across_dashboards_is_per_kind(self, tmp_path):
        """A kind buried in one dashboard's list collides with another
        dashboard's single string; the check is per kind."""
        from vcfops_dashboards.loader import DashboardValidationError, load_all

        _write(tmp_path / "dashboards" / "a.yaml", _summary_dash(
            name="[VCF Content Factory] A", summary_for=list(self.THREE)))
        _write(tmp_path / "dashboards" / "b.yaml", _summary_dash(
            name="[VCF Content Factory] B", summary_for="VMWARE:Datastore",
            dash_id="1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"))
        (tmp_path / "views").mkdir()
        with pytest.raises(DashboardValidationError, match="'VMWARE:Datastore' is claimed by both"):
            load_all(tmp_path / "views", tmp_path / "dashboards")

    @pytest.mark.parametrize("empty", ["", ",", [], [""]])
    def test_empty_rejected(self, tmp_path, empty):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        with pytest.raises(DashboardValidationError, match="summary_for must"):
            load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(summary_for=empty)))

    @pytest.mark.parametrize("widget", [
        {"id": "v", "type": "AlertVolume", "title": "AV", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
         "self_provider": True, "pin": {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"}},
        {"id": "v", "type": "Scoreboard", "title": "S", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
         "self_provider": True,
         "metrics": [{"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                      "metric_key": "cpu|usage_average"}]},
        {"id": "v", "type": "AlertList", "title": "AL", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
         "pin_to_world": True},
        {"id": "v", "type": "ResourceRelationshipAdvanced", "title": "R",
         "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
         "resource_relationship_advanced": {"self_provider": True}},
    ])
    def test_pinned_widgets_rejected(self, tmp_path, widget):
        from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

        d = load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(widgets=[widget])))
        with pytest.raises(DashboardValidationError, match="summary_for dashboards inherit the page object"):
            d.validate({})

    def test_same_pins_allowed_without_summary_for(self, tmp_path):
        from vcfops_dashboards.loader import load_dashboard

        data = _summary_dash(widgets=[
            {"id": "v", "type": "AlertVolume", "title": "AV", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
             "self_provider": True, "pin": {"adapter_kind": "VMWARE", "resource_kind": "vSphere World"}},
        ])
        del data["summary_for"]
        load_dashboard(_write(tmp_path / "d.yaml", data)).validate({})

    def test_section_is_exempt(self, tmp_path):
        from vcfops_dashboards.loader import load_dashboard

        data = _summary_dash(widgets=[
            {"id": "s", "type": "Section", "title": "S", "coords": {"x": 1, "y": 1}},
            {"id": "kpi", "type": "Scoreboard", "title": "CPU", "coords": {"x": 1, "y": 2, "w": 4, "h": 4},
             "metrics": [{"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                          "metric_key": "cpu|usage_average"}]},
        ])
        load_dashboard(_write(tmp_path / "d.yaml", data)).validate({})


# ---------------------------------------------------------------------------
# resource kind id
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ak,rk,expected", [
    ("VMWARE", "VirtualMachine", "002006VMWAREVirtualMachine"),
    ("VMWARE", "HostSystem", "002006VMWAREHostSystem"),
    ("SupervisorAdapter", "GuestCluster", "002017SupervisorAdapterGuestCluster"),
    ("synology_diskstation", "Volume", "002020synology_diskstationVolume"),
])
def test_resource_kind_id(ak, rk, expected):
    from vcfops_dashboards.summary_bind import resource_kind_id

    assert resource_kind_id(ak, rk) == expected


# ---------------------------------------------------------------------------
# multi-kind fan-out of resourceKindMetrics (render)
# ---------------------------------------------------------------------------
# Live-proven: with self-provider off the server keeps only the entries whose
# resourceKindId matches the page object's kind and hides the rest; there is
# no wildcard. See dashboard_widgets_alertvolume_section_viewdetails.md
# "Widgets bound to many resource kinds".

_OWNER = "11111111-2222-4333-8444-555555555555"
_TWO = ["VMWARE:HostSystem", "VMWARE:VirtualMachine"]


def _render(tmp_path, data):
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    d = load_dashboard(_write(tmp_path / "d.yaml", data))
    d.validate({})
    return json.loads(render_dashboards_bundle_json([d], {}, _OWNER))


def _kind_slot(bundle, ak, rk):
    for e in bundle["entries"]["resourceKind"]:
        if e["adapterKindKey"] == ak and e["resourceKindKey"] == rk:
            return e["internalId"]
    raise AssertionError(f"{ak}:{rk} missing from entries.resourceKind")


def _entries(bundle, widget_idx=0):
    return bundle["dashboards"][0]["widgets"][widget_idx]["config"]["metric"]["resourceKindMetrics"]


class TestSummaryFanOut:
    def test_scoreboard_two_kinds(self, tmp_path):
        data = _summary_dash(summary_for=_TWO, widgets=[
            {"id": "kpi", "type": "Scoreboard", "title": "CPU", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
             "metrics": [
                 {"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                  "metric_key": "cpu|usage_average", "metric_name": "CPU", "label": "CPU"},
                 {"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                  "metric_key": "mem|usage_average", "metric_name": "Mem", "label": "Mem"},
             ]},
        ])
        b = _render(tmp_path, data)
        ents = _entries(b)
        # two metrics x two kinds, metric-major, summary_for order within a metric
        assert [(e["metricKey"], e["resourceKindName"]) for e in ents] == [
            ("cpu|usage_average", "HostSystem"), ("cpu|usage_average", "VirtualMachine"),
            ("mem|usage_average", "HostSystem"), ("mem|usage_average", "VirtualMachine"),
        ]
        assert [e["resourceKindId"] for e in ents] == [
            _kind_slot(b, "VMWARE", "HostSystem"), _kind_slot(b, "VMWARE", "VirtualMachine"),
            _kind_slot(b, "VMWARE", "HostSystem"), _kind_slot(b, "VMWARE", "VirtualMachine"),
        ]
        assert [e["label"] for e in ents] == ["CPU", "CPU", "Mem", "Mem"]
        ids = [e["id"] for e in ents]
        assert len(set(ids)) == 4 and [i.rsplit("-", 1)[1] for i in ids] == ["1", "2", "3", "4"]

    def test_property_list_two_kinds(self, tmp_path):
        data = _summary_dash(summary_for=_TWO, widgets=[
            {"id": "facts", "type": "PropertyList", "title": "Facts", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
             "property_list": {"properties": [
                 {"adapter_kind": "VMWARE", "resource_kind": "HostSystem",
                  "metric_key": "summary|version", "metric_name": "Version", "is_string_metric": True},
             ]}},
        ])
        b = _render(tmp_path, data)
        ents = _entries(b)
        assert [e["resourceKindName"] for e in ents] == ["HostSystem", "VirtualMachine"]
        assert [e["resourceKindId"] for e in ents] == [
            _kind_slot(b, "VMWARE", "HostSystem"), _kind_slot(b, "VMWARE", "VirtualMachine")]
        assert all(e["isStringMetric"] for e in ents)
        assert len({e["id"] for e in ents}) == 2

    def test_pinned_child_kind_untouched(self, tmp_path):
        """A spec on a kind that is not in summary_for is author-pinned and
        is neither fanned out nor dropped; the listed kind next to it is."""
        data = _summary_dash(summary_for=_TWO, widgets=[
            {"id": "kpi", "type": "Scoreboard", "title": "CPU", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
             "metrics": [
                 {"adapter_kind": "VMWARE", "resource_kind": "Datastore",
                  "metric_key": "capacity|used_space", "metric_name": "Used"},
                 {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine",
                  "metric_key": "cpu|usage_average", "metric_name": "CPU"},
             ]},
        ])
        b = _render(tmp_path, data)
        ents = _entries(b)
        assert [(e["metricKey"], e["resourceKindName"]) for e in ents] == [
            ("capacity|used_space", "Datastore"),
            ("cpu|usage_average", "HostSystem"), ("cpu|usage_average", "VirtualMachine"),
        ]
        assert ents[0]["resourceKindId"] == _kind_slot(b, "VMWARE", "Datastore")

    def test_metric_chart_mixed_adapter_kinds(self, tmp_path):
        """A summary_for list mixing adapter kinds: each listed spec fans only
        over the listed kinds of its own adapter kind, in summary_for order;
        an unlisted (pinned) kind passes through untouched. Exercised on a
        MetricChart, the third emitter sharing _fan_out_summary_specs."""
        mixed = ["VMWARE:HostSystem", "NSXTAdapter:TransportNode", "VMWARE:VirtualMachine"]
        data = _summary_dash(summary_for=mixed, widgets=[
            {"id": "trend", "type": "MetricChart", "title": "Trend", "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
             "metrics": [
                 {"adapter_kind": "NSXTAdapter", "resource_kind": "TransportNode",
                  "metric_key": "cpu|usage", "metric_name": "Node CPU"},
                 {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine",
                  "metric_key": "cpu|usage_average", "metric_name": "CPU"},
                 {"adapter_kind": "VMWARE", "resource_kind": "Datastore",
                  "metric_key": "capacity|used_space", "metric_name": "Used"},
             ]},
        ])
        b = _render(tmp_path, data)
        ents = _entries(b)
        assert [(e["metricKey"], e["resourceKindName"]) for e in ents] == [
            ("cpu|usage", "TransportNode"),
            ("cpu|usage_average", "HostSystem"), ("cpu|usage_average", "VirtualMachine"),
            ("capacity|used_space", "Datastore"),
        ]
        assert [e["resourceKindId"] for e in ents] == [
            _kind_slot(b, "NSXTAdapter", "TransportNode"),
            _kind_slot(b, "VMWARE", "HostSystem"), _kind_slot(b, "VMWARE", "VirtualMachine"),
            _kind_slot(b, "VMWARE", "Datastore"),
        ]
        assert len({e["id"] for e in ents}) == 4

    def test_single_kind_unchanged(self, tmp_path):
        """One kind in summary_for renders exactly like no summary_for."""
        data = _summary_dash(summary_for="VMWARE:HostSystem")
        with_sf = _render(tmp_path / "a", data)
        data2 = dict(data)
        del data2["summary_for"]
        without = _render(tmp_path / "b", data2)
        assert with_sf == without
        assert len(_entries(with_sf)) == 1


def test_corpus_render_unchanged_by_fan_out():
    """Regression: every dashboard under content/ and third_party/idps-planner/
    renders byte-identical with and without its summary_for (none of them
    lists more than one kind, so the fan-out must be a no-op)."""
    from vcfops_dashboards.loader import load_all
    from vcfops_dashboards.render import render_dashboards_bundle_json

    root = Path(__file__).resolve().parents[1]
    for sub, enforce in (("content", True), ("third_party/idps-planner", False)):
        base = root / sub
        if not base.exists():
            continue
        views, dashes = load_all(base / "views", base / "dashboards", enforce_framework_prefix=enforce)
        by_name = {v.name: v for v in views}
        before = render_dashboards_bundle_json(dashes, by_name, _OWNER)
        for d in dashes:
            d.summary_for = None
        after = render_dashboards_bundle_json(dashes, by_name, _OWNER)
        assert before == after, sub


# ---------------------------------------------------------------------------
# bind flow against a fake UI client
# ---------------------------------------------------------------------------

_EXTRACT = (
    Path(__file__).resolve().parents[1]
    / "reference/docs/extracted/summary-dashboard-assignment/getResourceKindList-9.1.0-redacted.json"
)
_CAPTURED = json.loads(_EXTRACT.read_text())


def test_captured_shape_has_no_legacy_keys():
    """The fixture is the live shape: entries carry resourceKindId /
    resourceKind / adapterKind and none of id / key / resourceKindKey."""
    entries = _CAPTURED["resourceKindList"]
    assert entries and "defaultTemplateName" in _CAPTURED
    for e in entries:
        assert {"resourceKindId", "resourceKind", "adapterKind", "resourceKindTemplate"} <= e.keys()
        assert not {"id", "key", "resourceKindKey"} & e.keys()


def test_find_kind_entry_against_captured_shape():
    from vcfops_dashboards.summary_bind import KindTarget, _find_kind_entry

    plan = KindTarget(adapter_kind="VMWARE", resource_kind="HostSystem")
    entry = _find_kind_entry(_CAPTURED, plan)
    assert entry is not None and entry["resourceKindId"] == "002006VMWAREHostSystem"
    assert entry["name"] == "Host System"
    # fallback pair match when the id is absent
    stripped = {"resourceKindList": [
        {k: v for k, v in e.items() if k != "resourceKindId"} for e in _CAPTURED["resourceKindList"]
    ]}
    assert _find_kind_entry(stripped, plan)["resourceKind"] == "HostSystem"
    # same resourceKind under another adapter kind is not a match
    other = KindTarget(adapter_kind="Container", resource_kind="HostSystem")
    assert _find_kind_entry(_CAPTURED, other) is None


class FakeUI:
    """Records every call; answers with the captured Struts-layer shape.

    Wire contract (summary_dashboard_assignment.md, 2026-08-25 note):
    ``associate_resource_kind_dashboards(assigned, reset)`` carries the two
    maps the server reads as ``assignedAssociations`` / ``resetAssociations``;
    a bind materializes a copy whose UUID ``getSummaryTabId`` then returns
    with ``isDashboard: true``; an unbind (or no association) answers
    ``{"isDashboard": false}`` with NO ``tabId`` key at all.
    """

    def __init__(self, *, installed=None, current_template=None,
                 tab_after_bind="aaaaaaaa-1111-4222-8333-444444444444",
                 associate_error=None, tab_answer=None):
        self.installed = installed if installed is not None else {}
        self.current_template = current_template
        self.tab_after_bind = tab_after_bind
        self.associate_error = associate_error
        # forced getSummaryTabId answer (overrides the bound/unbound logic)
        self.tab_answer = tab_answer
        self.calls: list[tuple] = []
        # kind -> template UUID currently materialized for it
        self.templates: dict[str, str] = {}
        if current_template is not None:
            self.templates["resourceKind_002006VMWAREHostSystem"] = "old-copy-uuid"

    def list_dashboards(self):
        self.calls.append(("list_dashboards",))
        return [{"id": uid, "name": name} for name, uid in self.installed.items()]

    def get_resource_kind_list(self, adapter_kind):
        """The captured wire shape, filtered by adapter kind the way the
        server does; ``HostSystem`` reports ``current_template`` when set."""
        self.calls.append(("get_resource_kind_list", adapter_kind))
        entries = []
        for e in _CAPTURED["resourceKindList"]:
            if adapter_kind and e["adapterKind"] != adapter_kind:
                continue
            e = dict(e)
            if e["resourceKindId"] == "002006VMWAREHostSystem" and self.current_template:
                e["resourceKindTemplate"] = self.current_template
            entries.append(e)
        return {
            "resourceKindList": entries,
            "totalCount": len(entries),
            "defaultTemplateName": _CAPTURED["defaultTemplateName"],
        }

    def associate_resource_kind_dashboards(self, assigned, reset=None, **legacy):
        # the server reads exactly these two parameters; anything else NPEs
        assert not legacy, f"unknown parameters {sorted(legacy)} (dashboardAssociations is dead)"
        assert isinstance(assigned, dict) and isinstance(reset, dict), "both maps must be sent"
        self.calls.append(("associate", dict(assigned), dict(reset)))
        if self.associate_error is not None:
            raise self.associate_error
        for key, value in assigned.items():
            assert "_::_" in value and not value.endswith("_::_null"), value
            # saveDashboardAsTemplate + deleteDashboardTemplate(old): replace
            self.templates[key] = self.tab_after_bind
        for key, value in reset.items():
            assert "_::_" not in value, f"reset value is the plain default name, got {value!r}"
            self.templates.pop(key, None)

    def get_summary_tab_id(self, resource_kind_id):
        self.calls.append(("get_summary_tab_id", resource_kind_id))
        if self.tab_answer is not None:
            return dict(self.tab_answer)
        tab = self.templates.get(f"resourceKind_{resource_kind_id}")
        if not tab:
            return {"isDashboard": False}  # org.json drops the null tabId key
        return {"tabId": tab, "isDashboard": True}


def _load(tmp_path, **kw):
    from vcfops_dashboards.loader import load_dashboard

    d = load_dashboard(_write(tmp_path / "d.yaml", _summary_dash(**kw)))
    d.validate({})
    return d


class TestBindFlow:
    NAME = "[VCF Content Factory] Host Summary"
    UUID = "12345678-1234-4123-8123-123456789abc"
    KEY = "resourceKind_002006VMWAREHostSystem"

    def test_first_bind(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID})
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path)], out=lines.append)
        assert rc == 0
        assert ("associate", {self.KEY: f"{self.NAME}_::_{self.UUID}"}, {}) in ui.calls
        assert ("get_summary_tab_id", "002006VMWAREHostSystem") in ui.calls
        joined = "\n".join(lines)
        assert "wrote assignedAssociations" in joined
        assert "LIVE tabId: aaaaaaaa-1111-4222-8333-444444444444" in joined
        assert "template UUID: aaaaaaaa-1111-4222-8333-444444444444" in joined

    def test_rebind_is_a_plain_reassign(self, tmp_path):
        """Update story: assign again; the server replaces the kind's prior
        copy in the same call. The client sends nothing else."""
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID}, current_template=f"{self.NAME} 2")
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path)], out=lines.append)
        assert rc == 0
        kinds = [c[0] for c in ui.calls]
        assert kinds == ["get_resource_kind_list", "list_dashboards", "associate", "get_summary_tab_id"]
        assert ui.templates[self.KEY] == "aaaaaaaa-1111-4222-8333-444444444444"
        assert any(f"current assignment: {self.NAME} 2" in l for l in lines)

    def test_failed_associate_propagates(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary
        from vcfops_dashboards.ui_client import UIClientError

        ui = FakeUI(installed={self.NAME: self.UUID}, current_template=self.NAME,
                    associate_error=UIClientError("associateResourceKindDashboards failed"))
        with pytest.raises(UIClientError):
            bind_summary(ui, [_load(tmp_path)], out=lambda s: None)
        assert not any(c[0] == "get_summary_tab_id" for c in ui.calls)
        assert ui.templates[self.KEY] == "old-copy-uuid"

    def test_unbind_resets_with_the_kinds_own_default(self, tmp_path):
        """--unbind goes through resetAssociations with the per-entry
        defaultTemplateName (HostSystem -> "Host System Summary", not the
        top-level "Summary Detail"), plain name, no _::_null."""
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID}, current_template=self.NAME)
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path)], unbind=True, out=lines.append)
        assert rc == 0
        assert ("associate", {}, {self.KEY: "Host System Summary"}) in ui.calls
        assert not any(c[0] == "list_dashboards" for c in ui.calls)
        assert self.KEY not in ui.templates
        assert any("wrote resetAssociations" in l for l in lines)
        assert any("LIVE tabId: None" in l for l in lines)

    def test_unbind_falls_back_to_top_level_default(self, tmp_path):
        from vcfops_dashboards.summary_bind import _default_template_name

        kinds = {"defaultTemplateName": "Summary Detail"}
        assert _default_template_name(kinds, {"defaultTemplateName": "Host System Summary"}) == "Host System Summary"
        assert _default_template_name(kinds, {}) == "Summary Detail"
        assert _default_template_name({}, {}) == ""

    def test_unbind_that_leaves_a_tab_is_a_failure(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID}, current_template=self.NAME,
                    tab_answer={"tabId": "still-there", "isDashboard": True})
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path)], unbind=True, out=lines.append)
        assert rc == 2
        assert any("expected isDashboard: false after unbind" in l for l in lines)

    def test_unbind_accepts_native_page_with_non_uuid_tab_id(self, tmp_path):
        """Third documented getSummaryTabId shape: a native page answers a
        non-uuid tabId with isDashboard: false and pluginExist. That is the
        expected post-unbind state; success keys on isDashboard, symmetric
        with the bind branch."""
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID}, current_template=self.NAME,
                    tab_answer={"tabId": "hostSummaryTab", "isDashboard": False,
                                "pluginExist": True})
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path)], unbind=True, out=lines.append)
        assert rc == 0
        assert not any("WARNING" in l for l in lines)

    def test_missing_tab_id_key_is_null(self, tmp_path):
        """The server encodes a null tabId by omitting the key entirely."""
        from vcfops_dashboards.summary_bind import _live_tab_id, bind_summary

        assert _live_tab_id({"isDashboard": False}) is None
        assert _live_tab_id({"tabId": None, "isDashboard": False}) is None
        assert _live_tab_id({"tabId": "x", "isDashboard": True}) == "x"
        assert _live_tab_id("not json") is None

        ui = FakeUI(installed={self.NAME: self.UUID}, tab_answer={"isDashboard": False})
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path)], out=lines.append)
        assert rc == 2
        assert any("LIVE tabId: None" in l for l in lines)
        assert any("did not take" in l for l in lines)

    def test_bind_readback_needs_is_dashboard_true(self, tmp_path):
        """A non-uuid legacy plugin id comes back with isDashboard false;
        that is not a successful bind."""
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID},
                    tab_answer={"tabId": "legacyPlugin", "isDashboard": False, "pluginExist": True})
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path)], out=lines.append)
        assert rc == 2
        assert any("did not take" in l for l in lines)

    def test_not_installed_fails_without_writing(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={"[VCF Content Factory] Other": "x"})
        rc = bind_summary(ui, [_load(tmp_path)], out=lambda s: None)
        assert rc == 2
        assert not any(c[0] == "associate" for c in ui.calls)

    def test_folder_prefixed_name_resolves(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={f"VCF Content Factory/{self.NAME}": self.UUID})
        rc = bind_summary(ui, [_load(tmp_path)], out=lambda s: None)
        assert rc == 0

    def test_dry_run_needs_no_client(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        lines: list[str] = []
        rc = bind_summary(None, [_load(tmp_path)], dry_run=True, out=lines.append)
        assert rc == 0
        assert any("assignedAssociations" in l and self.KEY in l for l in lines)
        lines = []
        rc = bind_summary(None, [_load(tmp_path)], dry_run=True, unbind=True, out=lines.append)
        assert rc == 0
        assert any("resetAssociations" in l and self.KEY in l for l in lines)

    def test_only_filter_and_nothing_to_do(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        lines: list[str] = []
        rc = bind_summary(None, [_load(tmp_path)], only="nope", dry_run=True, out=lines.append)
        assert rc == 1
        assert "no dashboard carries summary_for" in lines[0]


class TestBindFlowManyKinds:
    """One dashboard, three kinds: one association call carrying the whole
    map, one readback line per kind, unbind resets every kind."""
    NAME = "[VCF Content Factory] Host Summary"
    UUID = "12345678-1234-4123-8123-123456789abc"
    THREE = ["VMWARE:HostSystem", "VMWARE:VirtualMachine", "VMWARE:Datastore"]
    KEYS = ["resourceKind_002006VMWAREHostSystem", "resourceKind_002006VMWAREVirtualMachine",
            "resourceKind_002006VMWAREDatastore"]

    def test_plan_carries_every_kind(self, tmp_path):
        from vcfops_dashboards.summary_bind import plan_bindings

        plans = plan_bindings([_load(tmp_path, summary_for=list(self.THREE))])
        assert len(plans) == 1
        assert [k.association_key for k in plans[0].kinds] == self.KEYS
        # first-kind shorthand still answers
        assert plans[0].association_key == self.KEYS[0]

    def test_bind_three_kinds_in_one_call(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID})
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path, summary_for=list(self.THREE))], out=lines.append)
        assert rc == 0
        associates = [c for c in ui.calls if c[0] == "associate"]
        assert associates == [("associate", {k: f"{self.NAME}_::_{self.UUID}" for k in self.KEYS}, {})]
        # one adapter-kind listing, one dashboard listing, three readbacks
        assert [c for c in ui.calls if c[0] == "get_resource_kind_list"] == [("get_resource_kind_list", "VMWARE")]
        assert [c[1] for c in ui.calls if c[0] == "get_summary_tab_id"] == [
            "002006VMWAREHostSystem", "002006VMWAREVirtualMachine", "002006VMWAREDatastore"]
        joined = "\n".join(lines)
        for label in self.THREE:
            assert f"{label}  LIVE tabId: aaaaaaaa-1111-4222-8333-444444444444" in joined
            assert f"{label}  template UUID:" in joined
        assert joined.count("wrote assignedAssociations") == 3

    def test_unbind_three_kinds_in_one_call(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID}, current_template=self.NAME)
        for k in self.KEYS:
            ui.templates[k] = "old-copy-uuid"
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path, summary_for=list(self.THREE))], unbind=True,
                          out=lines.append)
        assert rc == 0
        associates = [c for c in ui.calls if c[0] == "associate"]
        assert len(associates) == 1
        _, assigned, reset = associates[0]
        assert assigned == {}
        assert set(reset) == set(self.KEYS)
        assert reset[self.KEYS[0]] == "Host System Summary"
        assert all(v for v in reset.values())
        assert not any(k in ui.templates for k in self.KEYS)
        assert "\n".join(lines).count("wrote resetAssociations") == 3

    def test_unknown_kind_binds_the_rest_and_exits_2(self, tmp_path):
        """One of three kinds absent on the instance: the two that resolve
        are bound in one call, the miss is an ERROR naming dashboard and
        kind, and the run exits 2 (mirrors the pak installer's per-kind
        association; a partial map is not a corrupt state)."""
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID})
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path, summary_for=[
            "VMWARE:HostSystem", "VMWARE:NoSuchKind", "VMWARE:Datastore"])], out=lines.append)
        assert rc == 2
        associates = [c for c in ui.calls if c[0] == "associate"]
        assert associates == [("associate", {
            self.KEYS[0]: f"{self.NAME}_::_{self.UUID}",
            self.KEYS[2]: f"{self.NAME}_::_{self.UUID}"}, {})]
        assert [c[1] for c in ui.calls if c[0] == "get_summary_tab_id"] == [
            "002006VMWAREHostSystem", "002006VMWAREDatastore"]
        assert any(l.startswith("   ERROR: ") and self.NAME in l and "'NoSuchKind' not found" in l
                   for l in lines)
        joined = "\n".join(lines)
        assert joined.count("wrote assignedAssociations") == 2
        assert "VMWARE:NoSuchKind  LIVE tabId" not in joined

    def test_all_kinds_unknown_writes_nothing(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID})
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path, summary_for=["VMWARE:NoSuchKind", "VMWARE:NorThis"])],
                          out=lines.append)
        assert rc == 2
        assert not any(c[0] in ("associate", "list_dashboards", "get_summary_tab_id") for c in ui.calls)
        assert sum("not found" in l for l in lines) == 2
        assert any("no listed kind resolves" in l and self.NAME in l for l in lines)

    def test_unbind_unknown_kind_resets_the_rest_and_exits_2(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        ui = FakeUI(installed={self.NAME: self.UUID}, current_template=self.NAME)
        for k in self.KEYS:
            ui.templates[k] = "old-copy-uuid"
        lines: list[str] = []
        rc = bind_summary(ui, [_load(tmp_path, summary_for=[
            "VMWARE:HostSystem", "VMWARE:NoSuchKind", "VMWARE:Datastore"])], unbind=True,
            out=lines.append)
        assert rc == 2
        associates = [c for c in ui.calls if c[0] == "associate"]
        assert len(associates) == 1
        _, assigned, reset = associates[0]
        assert assigned == {}
        assert set(reset) == {self.KEYS[0], self.KEYS[2]}
        assert reset[self.KEYS[0]] == "Host System Summary"
        assert self.KEYS[0] not in ui.templates and self.KEYS[2] not in ui.templates
        assert ui.templates[self.KEYS[1]] == "old-copy-uuid"
        assert any("ERROR" in l and self.NAME in l and "'NoSuchKind' not found" in l for l in lines)
        assert "\n".join(lines).count("wrote resetAssociations") == 2

    def test_dry_run_prints_full_map(self, tmp_path):
        from vcfops_dashboards.summary_bind import bind_summary

        lines: list[str] = []
        rc = bind_summary(None, [_load(tmp_path, summary_for=list(self.THREE))], dry_run=True,
                          out=lines.append)
        assert rc == 0
        for k in self.KEYS:
            assert any("assignedAssociations" in l and k in l for l in lines)
        lines = []
        bind_summary(None, [_load(tmp_path, summary_for=list(self.THREE))], dry_run=True, unbind=True,
                     out=lines.append)
        for k in self.KEYS:
            assert any("resetAssociations" in l and k in l for l in lines)


class TestUIClientWire:
    """The real client posts exactly the two parameter names the server
    reads, and never the dead ``dashboardAssociations``."""

    @staticmethod
    def _client():
        from vcfops_dashboards.ui_client import VCFOpsUIClient

        class _Resp:
            status_code = 200
            text = "ok"

            def raise_for_status(self):
                pass

        class _Session:
            def __init__(self):
                self.posts = []

            def post(self, url, data=None, headers=None, **kw):
                self.posts.append((url, dict(data), dict(headers or {})))
                return _Resp()

        c = VCFOpsUIClient(host="ops.example", username="u", password="p")
        c._session = _Session()
        c._csrf_token = "tok"
        return c

    def test_associate_sends_two_maps(self):
        c = self._client()
        c.associate_resource_kind_dashboards({"resourceKind_x": "N_::_u"}, {"resourceKind_y": "Default"})
        url, data, headers = c._session.posts[-1]
        assert url.endswith("/ui/dashboard.action")
        assert data["mainAction"] == "associateResourceKindDashboards"
        assert json.loads(data["assignedAssociations"]) == {"resourceKind_x": "N_::_u"}
        assert json.loads(data["resetAssociations"]) == {"resourceKind_y": "Default"}
        assert data["secureToken"] == "tok"
        assert headers.get("X-Requested-With") == "XMLHttpRequest"
        assert "dashboardAssociations" not in data

    def test_associate_always_sends_both_maps(self):
        c = self._client()
        c.associate_resource_kind_dashboards({"resourceKind_x": "N_::_u"})
        _, data, _ = c._session.posts[-1]
        assert data["assignedAssociations"] == '{"resourceKind_x": "N_::_u"}'
        assert data["resetAssociations"] == "{}"
        c.associate_resource_kind_dashboards({}, {})
        _, data, _ = c._session.posts[-1]
        assert (data["assignedAssociations"], data["resetAssociations"]) == ("{}", "{}")

    def test_template_actions_are_gone(self):
        from vcfops_dashboards.ui_client import VCFOpsUIClient

        assert not hasattr(VCFOpsUIClient, "get_template_list")
        assert not hasattr(VCFOpsUIClient, "delete_template")


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def test_cli_bind_summary_dry_run(tmp_path, capsys, monkeypatch):
    from vcfops_dashboards.cli import main

    _write(tmp_path / "dashboards" / "d.yaml", _summary_dash())
    (tmp_path / "views").mkdir()
    rc = main([
        "--views-dir", str(tmp_path / "views"),
        "--dashboards-dir", str(tmp_path / "dashboards"),
        "bind-summary", "--dry-run",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "resourceKind_002006VMWAREHostSystem" in out
    assert "nothing written" in out


def test_cli_bind_summary_parser_flags():
    from vcfops_dashboards.cli import build_parser

    args = build_parser().parse_args(["bind-summary", "--dashboard", "X", "--unbind", "--dry-run"])
    assert args.dashboard == "X" and args.unbind and args.dry_run


# ---------------------------------------------------------------------------
# Pak route: content/dashboards/dashboards.properties
# ---------------------------------------------------------------------------

class TestPakDashboardsProperties:
    def _project(self, tmp_path):
        from vcfops_managementpacks.sdk_project import SdkProjectDef, _derive_entry_class

        return SdkProjectDef(
            name="Test Adapter", version="1.0.0", build_number=1,
            adapter_kind="test_adapter", description="Test", tier=2,
            dependencies=[], entry_class=_derive_entry_class("test_adapter"),
            source_path=tmp_path / "adapter.yaml",
        )

    def _build(self, tmp_path, dashboards):
        import io
        import zipfile
        from vcfops_managementpacks.sdk_builder import _write_outer_pak

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w"):
            pass
        out = tmp_path / "dist"
        out.mkdir(exist_ok=True)
        pak = _write_outer_pak(
            project=self._project(tmp_path), output_dir=out,
            adapters_zip_bytes=buf.getvalue(), dashboards=dashboards,
            owning_adapter_kind="test_adapter",
        )
        return zipfile.ZipFile(pak, "r")

    def test_bound_dashboard_emits_properties(self, tmp_path):
        from vcfops_dashboards.loader import load_dashboard

        bound = load_dashboard(_write(tmp_path / "bound.yaml", _summary_dash(
            name="Host Summary", summary_for="VMWARE:HostSystem")), enforce_framework_prefix=False)
        plain = load_dashboard(_write(tmp_path / "plain.yaml", {
            **_summary_dash(name="Plain One", dash_id="1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"),
            "summary_for": None,
        }), enforce_framework_prefix=False)
        with self._build(tmp_path, [bound, plain]) as zf:
            names = zf.namelist()
            assert "content/dashboards/dashboards.properties" in names
            props = zf.read("content/dashboards/dashboards.properties").decode()
            lines = [l for l in props.splitlines() if l and not l.startswith("#")]
            assert lines == ["Host_Summary=VMWARE:HostSystem"]
            # the key is the directory that holds the dashboard json
            assert "content/dashboards/Host_Summary/dashboard.json" in names
            assert "content/dashboards/Plain_One/dashboard.json" in names

    def test_many_kinds_emit_comma_joined_value(self, tmp_path):
        """dashboards.properties value is the installer's own shape:
        comma-separated AdapterKind:ResourceKind, two colon tokens each."""
        from vcfops_dashboards.loader import load_dashboard

        bound = load_dashboard(_write(tmp_path / "bound.yaml", _summary_dash(
            name="Host Summary",
            summary_for=["VMWARE:HostSystem", "VMWARE:VirtualMachine", "VMWARE:Datastore"])),
            enforce_framework_prefix=False)
        with self._build(tmp_path, [bound]) as zf:
            props = zf.read("content/dashboards/dashboards.properties").decode()
            lines = [l for l in props.splitlines() if l and not l.startswith("#")]
            assert lines == ["Host_Summary=VMWARE:HostSystem,VMWARE:VirtualMachine,VMWARE:Datastore"]
            value = lines[0].split("=", 1)[1]
            assert all(len(part.split(":")) == 2 for part in value.split(","))

    def test_duplicate_target_rejected_by_pak_builder(self, tmp_path):
        """The pak route loads per file (not load_all); the same guard applies."""
        from vcfops_managementpacks.sdk_builder import SdkBuildError, _load_bundled_content

        _write(tmp_path / "a.yaml", _summary_dash(name="A"))
        _write(tmp_path / "b.yaml", _summary_dash(name="B", dash_id="1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"))
        raw = {"bundled_content": {"dashboards": ["a.yaml", "b.yaml"]}}
        with pytest.raises(SdkBuildError, match="claimed by both"):
            _load_bundled_content(raw, tmp_path, tmp_path)

    def test_no_binding_no_file(self, tmp_path):
        from vcfops_dashboards.loader import load_dashboard

        plain = load_dashboard(_write(tmp_path / "plain.yaml", {
            **_summary_dash(name="Plain One"), "summary_for": None,
        }), enforce_framework_prefix=False)
        with self._build(tmp_path, [plain]) as zf:
            assert "content/dashboards/dashboards.properties" not in zf.namelist()
