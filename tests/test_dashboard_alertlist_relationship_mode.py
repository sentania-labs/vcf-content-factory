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
])
def test_relationship_mode_rejected(tmp_path, raw, needle):
    from vcfcf_core.dashboards.loader import DashboardValidationError

    with pytest.raises(DashboardValidationError, match=needle):
        _load(tmp_path, _alert_widget(relationship_mode=raw))


def test_metric_chart_relationship_mode_unchanged(tmp_path):
    """The MetricChart scalar form and its other-type rejection still hold."""
    from vcfcf_core.dashboards.loader import DashboardValidationError

    with pytest.raises(DashboardValidationError, match="MetricChart and AlertList"):
        _load(tmp_path, {
            "id": "txt", "type": "TextDisplay", "title": "t",
            "coords": {"x": 1, "y": 1, "w": 4, "h": 4}, "html": "x",
            "relationship_mode": "children",
        })


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


@pytest.mark.parametrize("depth", ["two", True, 1.5, None])
def test_depth_non_integer_rejected(tmp_path, depth):
    from vcfcf_core.dashboards.loader import DashboardValidationError

    with pytest.raises(DashboardValidationError, match="must be an integer from 1 to 10"):
        _load(tmp_path, _alert_widget(depth=depth))


# ---------------------------------------------------------------------------
# Reverse (extractor) round trip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("wire, expected", [
    ([-1, 0], [-1, 0]),
    ([0], [0]),
    ([0, -1], [-1, 0]),
    ([1, -1], [1, -1]),
    ([1, 0], [-1, 0]),       # editor cannot produce it; falls back to default
    (None, [-1, 0]),
])
def test_reverse_parses_relationship_mode(wire, expected):
    import warnings

    from vcfcf_core.dashboards.reverse import _parse_alert_list_config

    cfg = {"depth": 1}
    if wire is not None:
        cfg["relationshipMode"] = {"relationshipMode": wire}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert _parse_alert_list_config(cfg, "d", "w").relationship_mode == expected


# ---------------------------------------------------------------------------
# Every in-repo AlertList still loads and renders the old default
# ---------------------------------------------------------------------------

def _repo_alertlist_dashboards() -> list[Path]:
    roots = [REPO / "content", REPO / "third_party"]
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("dashboards/*.yaml")):
            if "worktrees" in p.parts:
                continue
            try:
                data = yaml.safe_load(p.read_text()) or {}
            except yaml.YAMLError:
                continue
            ws = data.get("widgets") if isinstance(data, dict) else None
            if isinstance(ws, list) and any(
                isinstance(w, dict) and w.get("type") == "AlertList" for w in ws
            ):
                found.append(p)
    return found


_REPO_DASHES = _repo_alertlist_dashboards()


@pytest.mark.skipif(not _REPO_DASHES, reason="no AlertList dashboards in this checkout")
@pytest.mark.parametrize("path", _REPO_DASHES, ids=lambda p: p.name)
def test_repo_alertlists_render_default_mode(path):
    """Content written before the option still loads and keeps [-1, 0]."""
    from vcfcf_core.dashboards.loader import load_dashboard

    d = load_dashboard(path, enforce_framework_prefix=False)
    raw = {w.get("id"): w for w in (yaml.safe_load(path.read_text()) or {})["widgets"]}
    for w in d.widgets:
        if w.type != "AlertList":
            continue
        src = raw.get(w.local_id, {})
        if "relationship_mode" not in src:
            assert w.alert_list_config.relationship_mode == [-1, 0]
        assert 1 <= w.alert_list_config.depth <= 10
