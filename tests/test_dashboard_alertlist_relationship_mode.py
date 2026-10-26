"""AlertList `relationship_mode` and `depth` bounds.

Wire facts (knowledge/context/investigations/2026-10-26-alertlist-depth-semantics.md,
live replay on 9.0.2 and 8.18 plus the 9.0.2 widget editor JS):

- `config.relationshipMode.relationshipMode` is an int array:
  parents=1, children=-1, self=0. The editor makes self and parents
  mutually exclusive.
- `config.depth` must be 1 to 10; the server throws
  "depth should be between 1 and 10" on 0 and the widget shows no list.

Omitting `relationship_mode` must keep the rendered bundle byte-identical
to the pre-option renderer, which hard-coded `[-1, 0]`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

OWNER = "00000000-0000-0000-0000-000000000001"
REPO = Path(__file__).resolve().parent.parent


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _alert_widget(**extra) -> dict:
    w = {
        "id": "alerts", "type": "AlertList", "title": "Alerts",
        "coords": {"x": 1, "y": 1, "w": 12, "h": 6},
        "self_provider": True,
    }
    w.update(extra)
    return w


def _load(tmp_path: Path, widget: dict, name: str = "d"):
    from vcfcf_dashboards.loader import load_dashboard

    return load_dashboard(_write(tmp_path / f"{name}.yaml", {
        "id": "11111111-2222-4333-8444-555555555555",
        "name": "[VCF Content Factory] AlertList Mode Test",
        "description": "",
        "widgets": [widget],
    }))


def _render(tmp_path: Path, widget: dict, name: str = "d") -> str:
    from vcfcf_dashboards.render import render_dashboards_bundle_json

    d = _load(tmp_path, widget, name)
    d.validate({})
    return render_dashboards_bundle_json([d], {}, OWNER)


def _alert_cfg(bundle: str) -> dict:
    data = json.loads(bundle)
    for dash in data["dashboards"]:
        for w in dash["widgets"]:
            if w["type"] == "AlertList":
                return w["config"]
    raise AssertionError("no AlertList widget rendered")


# ---------------------------------------------------------------------------
# Default: byte-identical to the hard-coded renderer
# ---------------------------------------------------------------------------

def test_default_relationship_mode_is_children_plus_self(tmp_path):
    cfg = _alert_cfg(_render(tmp_path, _alert_widget()))
    assert cfg["relationshipMode"] == {"relationshipMode": [-1, 0]}
    assert cfg["depth"] == 1


def test_explicit_default_is_byte_identical_to_omitted(tmp_path):
    omitted = _render(tmp_path, _alert_widget(), "a")
    explicit = _render(tmp_path, _alert_widget(relationship_mode=["self", "children"]), "b")
    reordered = _render(tmp_path, _alert_widget(relationship_mode=["children", "self"]), "c")
    assert omitted == explicit == reordered


def test_default_config_golden(tmp_path):
    """Pin the whole AlertList config as the pre-option renderer emitted it."""
    cfg = _alert_cfg(_render(tmp_path, _alert_widget(depth=4, status=[0])))
    assert cfg == {
        "refreshInterval": 300,
        "resource": [],
        "refreshContent": {"refreshContent": False},
        "relationshipMode": {"relationshipMode": [-1, 0]},
        "selfProvider": {"selfProvider": True},
        "title": "Alerts",
        "mode": "all",
        "filterMode": "tagPicker",
        "tagFilter": None,
        "depth": 4,
        "customFilter": {"filter": [], "excludedResources": None, "includedResources": None},
        "criticalityLevel": [2, 3, 4],
        "type": [],
        "status": [0],
        "state": [],
        "alertImpact": [],
        "alertAction": [],
        "alertDefinitions": [],
    }


# ---------------------------------------------------------------------------
# relationship_mode values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, wire", [
    ("self", [0]),
    (["self"], [0]),
    ("children", [-1]),
    ("parents", [1]),
    (["parents", "children"], [1, -1]),
    (["children", "parents"], [1, -1]),
    (["Self", "CHILDREN"], [-1, 0]),
])
def test_relationship_mode_renders(tmp_path, raw, wire):
    cfg = _alert_cfg(_render(tmp_path, _alert_widget(relationship_mode=raw)))
    assert cfg["relationshipMode"] == {"relationshipMode": wire}


@pytest.mark.parametrize("raw, needle", [
    (["self", "parents"], "cannot combine 'self' and 'parents'"),
    (["parents", "children", "self"], "cannot combine 'self' and 'parents'"),
    ([], "non-empty list"),
    ("none", "is not one of"),
    ([-1, 0], "is not one of"),
    (["children", "children"], "twice"),
    ({"children": True}, "non-empty list"),
    ([{"self": 1}], "is not one of"),
    ([0], "is not one of"),
])
def test_relationship_mode_rejected(tmp_path, raw, needle):
    from vcfcf_core.dashboards.loader import DashboardValidationError

    with pytest.raises(DashboardValidationError, match=needle):
        _load(tmp_path, _alert_widget(relationship_mode=raw))




# ---------------------------------------------------------------------------
# MetricChart relationship_mode: scalar form unchanged
# ---------------------------------------------------------------------------

def _metric_chart(**extra) -> dict:
    w = {
        "id": "chart", "type": "MetricChart", "title": "CPU",
        "coords": {"x": 1, "y": 1, "w": 12, "h": 6},
        "self_provider": True,
        "pin": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "metrics": [{"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine",
                     "metric_key": "cpu|usage_average", "metric_name": "CPU Usage"}],
    }
    w.update(extra)
    return w


@pytest.mark.parametrize("raw, wire", [
    ("children", -1),
    ("parents", 1),
    (None, 0),
])
def test_metric_chart_relationship_mode_renders_scalar(tmp_path, raw, wire):
    """MetricChart takes a scalar; an array here is a 500 on dashboard load."""
    extra = {} if raw is None else {"relationship_mode": raw}
    data = json.loads(_render(tmp_path, _metric_chart(**extra)))
    (w,) = [w for w in data["dashboards"][0]["widgets"] if w["type"] == "MetricChart"]
    assert w["config"]["relationshipMode"] == {"relationshipMode": wire}


@pytest.mark.parametrize("raw", ["self", ["children"], ["self", "children"]])
def test_metric_chart_rejects_alertlist_forms(tmp_path, raw):
    from vcfcf_core.dashboards.loader import DashboardValidationError

    with pytest.raises(DashboardValidationError, match="'children', 'parents', or omitted"):
        _load(tmp_path, _metric_chart(relationship_mode=raw))


@pytest.mark.parametrize("wtype, extra", [
    ("TextDisplay", {"html": "x"}),
    ("Heatmap", {}),
])
def test_other_types_reject_relationship_mode_by_type(tmp_path, wtype, extra):
    """The type check comes first, so `self` on a Heatmap names the type."""
    from vcfcf_core.dashboards.loader import DashboardValidationError

    w = {"id": "w", "type": wtype, "title": "t",
         "coords": {"x": 1, "y": 1, "w": 4, "h": 4}, "relationship_mode": "self", **extra}
    with pytest.raises(DashboardValidationError, match="MetricChart and AlertList widgets"):
        _load(tmp_path, w)


# ---------------------------------------------------------------------------
# depth bounds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("depth", [1, 5, 10])
def test_depth_in_range_renders(tmp_path, depth):
    cfg = _alert_cfg(_render(tmp_path, _alert_widget(depth=depth)))
    assert cfg["depth"] == depth


@pytest.mark.parametrize("depth", [0, -1, 11, 100])
def test_depth_out_of_range_rejected(tmp_path, depth):
    from vcfcf_core.dashboards.loader import DashboardValidationError

    with pytest.raises(DashboardValidationError, match="depth should be between 1 and 10"):
        _load(tmp_path, _alert_widget(depth=depth))


@pytest.mark.parametrize("depth", ["two", "5", True, 1.5, 3.0, None])
def test_depth_non_integer_rejected(tmp_path, depth):
    from vcfcf_core.dashboards.loader import DashboardValidationError

    with pytest.raises(DashboardValidationError, match="must be an integer from 1 to 10"):
        _load(tmp_path, _alert_widget(depth=depth))


# ---------------------------------------------------------------------------
# Extraction: wire -> reverse -> YAML is faithful, never repaired
# ---------------------------------------------------------------------------

def _wire_dashboard(config: dict) -> dict:
    return {
        "id": "bbbbbbbb-0000-4000-8000-000000000001",
        "name": "Extract Test",
        "widgets": [{
            "id": "aaaaaaaa-0000-4000-8000-000000000001",
            "type": "AlertList", "title": "Alerts",
            "gridsterCoords": {"x": 1, "y": 1, "w": 12, "h": 6},
            "config": {"selfProvider": {"selfProvider": True}, "mode": "all", **config},
        }],
    }


def _extract_widget_yaml(config: dict) -> dict:
    """Wire AlertList config -> reverse parser -> extractor YAML dict."""
    import warnings

    from vcfcf_core.dashboards.reverse import parse_dashboard_json
    from vcfcf_core.extractor.extractor import _widget_to_yaml_dict

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dash = parse_dashboard_json(_wire_dashboard(config), {})
    (w,) = dash.widgets
    return _widget_to_yaml_dict(w, {})


def _reload(tmp_path: Path, wyaml: dict):
    wyaml = dict(wyaml)
    wyaml["id"] = "alerts"
    return _load(tmp_path, wyaml, "rt")


@pytest.mark.parametrize("wire, yaml_rm, rendered", [
    ([-1, 0], None, [-1, 0]),
    ([0, -1], None, [-1, 0]),
    ([0], ["self"], [0]),
    ([-1], ["children"], [-1]),
    ([1], ["parents"], [1]),
    ([1, -1], ["parents", "children"], [1, -1]),
    ([-1, 1], ["children", "parents"], [1, -1]),
])
def test_representable_relationship_mode_round_trips(tmp_path, wire, yaml_rm, rendered):
    """Every value the editor can produce survives wire -> YAML -> load -> wire."""
    wyaml = _extract_widget_yaml({"depth": 3, "relationshipMode": {"relationshipMode": wire}})
    assert wyaml.get("relationship_mode") == yaml_rm
    assert wyaml["depth"] == 3
    d = _reload(tmp_path, wyaml)
    d.validate({})
    from vcfcf_dashboards.render import render_dashboards_bundle_json
    cfg = _alert_cfg(render_dashboards_bundle_json([d], {}, OWNER))
    assert cfg["relationshipMode"] == {"relationshipMode": rendered}
    assert cfg["depth"] == 3


@pytest.mark.parametrize("rm_cfg, yaml_rm, needle", [
    ({"relationshipMode": [1, 0]}, ["parents", "self"], "cannot combine 'self' and 'parents'"),
    ({"relationshipMode": [1, -1, 0]}, ["parents", "children", "self"],
     "cannot combine 'self' and 'parents'"),
    ({"relationshipMode": [-1, -1]}, ["children", "children"], "twice"),
    ({"relationshipMode": []}, [], "non-empty list"),
    ({"relationshipMode": [2]}, [2], "is not one of"),
    ({"relationshipMode": [True]}, [True], "is not one of"),
    ({"relationshipMode": [0.0]}, [0.0], "is not one of"),
    ({"relationshipMode": ["0"]}, ["0"], "is not one of"),
    ({"relationshipMode": 0}, 0, "non-empty list"),
])
def test_unrepresentable_relationship_mode_fails_validate(tmp_path, rm_cfg, yaml_rm, needle):
    """Carried raw into YAML so the loader rejects it; never defaulted."""
    from vcfcf_core.dashboards.loader import DashboardValidationError

    wyaml = _extract_widget_yaml({"depth": 1, "relationshipMode": rm_cfg})
    assert wyaml["relationship_mode"] == yaml_rm
    with pytest.raises(DashboardValidationError, match=needle):
        _reload(tmp_path, wyaml)


def test_unwrapped_relationship_mode_is_carried_and_warned():
    import warnings

    from vcfcf_core.dashboards.reverse import _parse_alert_list_config

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg = _parse_alert_list_config({"relationshipMode": [0]}, "d", "w")
    assert cfg.relationship_mode == [0]
    assert any("not wrapped" in str(c.message) for c in caught)


def test_missing_relationship_mode_is_omitted_and_warned():
    import warnings

    from vcfcf_core.dashboards.reverse import _parse_alert_list_config
    from vcfcf_core.extractor.extractor import _alert_list_relationship_mode_yaml

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg = _parse_alert_list_config({}, "d", "w")
    assert cfg.relationship_mode is None
    assert cfg.depth is None
    assert _alert_list_relationship_mode_yaml(cfg.relationship_mode) is None
    assert any("no relationshipMode" in str(c.message) for c in caught)


@pytest.mark.parametrize("depth, needle", [
    (0, "depth should be between 1 and 10"),
    (11, "depth should be between 1 and 10"),
    ("0", "must be an integer from 1 to 10"),
    ("abc", "must be an integer from 1 to 10"),
])
def test_source_depth_carried_faithfully(tmp_path, depth, needle):
    """A broken source depth reaches validate instead of being repaired."""
    from vcfcf_core.dashboards.loader import DashboardValidationError

    wyaml = _extract_widget_yaml({"depth": depth,
                                  "relationshipMode": {"relationshipMode": [-1, 0]}})
    assert wyaml["depth"] == depth
    with pytest.raises(DashboardValidationError, match=needle):
        _reload(tmp_path, wyaml)


def test_absent_source_depth_is_omitted(tmp_path):
    wyaml = _extract_widget_yaml({"relationshipMode": {"relationshipMode": [-1, 0]}})
    assert "depth" not in wyaml
    assert _reload(tmp_path, wyaml).widgets[0].alert_list_config.depth == 1


# ---------------------------------------------------------------------------
# Corpus regression: committed copy of every managed-pak AlertList widget,
# rendered byte-for-byte as origin/main rendered it before this option.
# ---------------------------------------------------------------------------

_FIXTURES = REPO / "tests" / "fixtures" / "dashboards"


def test_corpus_alertlists_render_unchanged():
    from vcfcf_core.dashboards.loader import load_dashboard
    from vcfcf_dashboards.render import render_dashboards_bundle_json

    d = load_dashboard(_FIXTURES / "alertlist_corpus.yaml")
    d.validate({})
    bundle = json.loads(render_dashboards_bundle_json([d], {}, OWNER))
    got = [
        {"title": w["title"], "config": w["config"]}
        for w in bundle["dashboards"][0]["widgets"] if w["type"] == "AlertList"
    ]
    golden = json.loads((_FIXTURES / "alertlist_corpus_golden.json").read_text())
    assert len(got) == len(golden) == 9
    assert got == golden
