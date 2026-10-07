"""Dashboard Navigation (dashboard-to-dashboard drill-down).

Design of record: knowledge/designs/dashboard-navigations-v1.md. Wire format:
knowledge/context/wire-formats/dashboard_navigations.md.

Covers the per-widget ``navigations:`` YAML surface (loader), the
``dashboardNavigations`` block (renderer), cross-dashboard resolution
(validate chain), the bundle-must-carry-targets rule (packaging), and both
extractor paths (live writer and reverse_local).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

OWNER = "00000000-0000-0000-0000-000000000001"
SRC = "[VCF Content Factory] Nav Source"
DST = "[VCF Content Factory] Nav Target"
SRC_ID = "11111111-1111-4111-8111-111111111111"
DST_ID = "22222222-2222-4222-8222-222222222222"
STOCK_ID = "533e14ed-2796-4ead-a644-468beb6396f8"  # vendor Cluster Performance


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _rl(wid: str, x: int = 1, y: int = 1, **extra) -> dict:
    w = {
        "id": wid, "type": "ResourceList", "title": wid,
        "coords": {"x": x, "y": y, "w": 4, "h": 4},
        "resource_kinds": [{"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource"}],
    }
    w.update(extra)
    return w


def _txt(wid: str, x: int = 5, y: int = 1, **extra) -> dict:
    w = {"id": wid, "type": "TextDisplay", "title": wid,
         "coords": {"x": x, "y": y, "w": 4, "h": 4}, "html": "<b>x</b>"}
    w.update(extra)
    return w


def _dash(name: str, dash_id: str, widgets: list, **extra) -> dict:
    d = {"id": dash_id, "name": name, "description": "d", "widgets": widgets, "interactions": []}
    d.update(extra)
    return d


def _target_doc() -> dict:
    return _dash(DST, DST_ID, [_rl("cluster_picker"), _txt("cluster_metrics")])


def _load(path: Path):
    from vcfcf_core.dashboards.loader import load_dashboard
    return load_dashboard(path, enforce_framework_prefix=False)


def _load_doc(tmp_path: Path, doc: dict, fname: str = "d.yaml"):
    return _load(_write(tmp_path / fname, doc))


def _render(dashboards, known=None) -> dict:
    from vcfcf_core.dashboards.render import render_dashboards_bundle_json
    return json.loads(render_dashboards_bundle_json(dashboards, {}, OWNER, known_dashboards=known))


# ---------------------------------------------------------------------------
# Loader: YAML surface
# ---------------------------------------------------------------------------


class TestLoader:
    def test_all_three_entry_forms_parse(self, tmp_path):
        doc = _dash(SRC, SRC_ID, [_rl("src_list", navigations=[
            {"dashboard": DST, "widgets": ["cluster_picker", "cluster_metrics"]},
            {"dashboard": DST},
            {"dashboard_id": STOCK_ID.upper(), "label": "Cluster Performance"},
        ])])
        d = _load_doc(tmp_path, doc)
        navs = d.widgets[0].navigations
        assert [(n.dashboard, n.dashboard_id, n.widgets, n.label) for n in navs] == [
            (DST, "", ["cluster_picker", "cluster_metrics"], ""),
            (DST, "", [], ""),
            ("", STOCK_ID, [], "Cluster Performance"),
        ]

    def test_absent_and_empty_list_mean_no_navigations(self, tmp_path):
        d = _load_doc(tmp_path, _dash(SRC, SRC_ID, [_rl("a"), _txt("b", navigations=[])]))
        assert [w.navigations for w in d.widgets] == [[], []]

    @pytest.mark.parametrize("entry", [
        {"dashboard": DST, "dashboard_id": STOCK_ID},
        {"label": "neither"},
        {},
    ])
    def test_xor_dashboard_and_dashboard_id(self, tmp_path, entry):
        from vcfcf_core.dashboards.loader import DashboardValidationError
        doc = _dash(SRC, SRC_ID, [_rl("src_list", navigations=[entry])])
        with pytest.raises(DashboardValidationError, match="exactly one of 'dashboard'"):
            _load_doc(tmp_path, doc)

    @pytest.mark.parametrize("widgets", [[], ["cluster_picker"]])
    def test_widgets_rejected_on_dashboard_id_entry(self, tmp_path, widgets):
        from vcfcf_core.dashboards.loader import DashboardValidationError
        doc = _dash(SRC, SRC_ID, [_rl("src_list", navigations=[
            {"dashboard_id": STOCK_ID, "widgets": widgets},
        ])])
        with pytest.raises(DashboardValidationError, match="widgets is not allowed on a dashboard_id"):
            _load_doc(tmp_path, doc)

    def test_section_rejects_navigations(self, tmp_path):
        from vcfcf_core.dashboards.loader import DashboardValidationError
        doc = _dash(SRC, SRC_ID, [
            {"id": "sec", "type": "Section", "title": "S", "coords": {"x": 1, "y": 1},
             "navigations": [{"dashboard": DST}]},
            _rl("a", y=2),
        ])
        with pytest.raises(DashboardValidationError, match="Section must not carry navigations"):
            _load_doc(tmp_path, doc)

    def test_section_rejects_programmatic_navigations_in_validate(self, tmp_path):
        from vcfcf_core.dashboards.loader import DashboardValidationError, Navigation
        doc = _dash(SRC, SRC_ID, [
            {"id": "sec", "type": "Section", "title": "S", "coords": {"x": 1, "y": 1}},
            _rl("a", y=2),
        ])
        d = _load_doc(tmp_path, doc)
        d.widgets[0].navigations = [Navigation(dashboard=DST)]
        with pytest.raises(DashboardValidationError, match="navigations"):
            d.validate({}, enforce_framework_prefix=False)

    @pytest.mark.parametrize("nav, msg", [
        ({"dashboard": DST}, "navigations must be a list"),
        ([{"dashbaord": DST}], "unknown key"),
        (["just a name"], "must be a mapping"),
        ([{"dashboard": ""}], "non-empty string"),
        ([{"dashboard_id": "not-a-uuid"}], "dashboard_id must be a dashboard UUID"),
        ([{"dashboard": DST, "widgets": "cluster_picker"}], "widgets must be a list"),
        ([{"dashboard": DST, "widgets": ["a", "a"]}], "more than once"),
        ([{"dashboard": DST, "label": 3}], "label must be a string"),
    ])
    def test_shape_errors(self, tmp_path, nav, msg):
        from vcfcf_core.dashboards.loader import DashboardValidationError
        doc = _dash(SRC, SRC_ID, [_rl("src_list", navigations=nav)])
        with pytest.raises(DashboardValidationError, match=msg):
            _load_doc(tmp_path, doc)

    def test_self_target_allowed_but_not_self_receiver(self, tmp_path):
        from vcfcf_core.dashboards.loader import DashboardValidationError
        ok = _dash(SRC, SRC_ID, [_rl("a", navigations=[{"dashboard": SRC, "widgets": ["b"]}]), _txt("b")])
        _load_doc(tmp_path, ok, "ok.yaml").validate({}, enforce_framework_prefix=False)
        bad = _dash(SRC, SRC_ID, [_rl("a", navigations=[{"dashboard": SRC, "widgets": ["a"]}]), _txt("b")])
        with pytest.raises(DashboardValidationError, match="names the widget itself as a receiver"):
            _load_doc(tmp_path, bad, "bad.yaml").validate({}, enforce_framework_prefix=False)


# ---------------------------------------------------------------------------
# Cross-dashboard resolution (the validate chain's check)
# ---------------------------------------------------------------------------


class TestCheck:
    def _pair(self, tmp_path, navs):
        src = _load_doc(tmp_path, _dash(SRC, SRC_ID, [_rl("src_list", navigations=navs)]), "s.yaml")
        dst = _load_doc(tmp_path, _target_doc(), "t.yaml")
        return src, dst

    def test_resolving_references_pass(self, tmp_path):
        from vcfcf_core.dashboards.loader import check_dashboard_navigations
        src, dst = self._pair(tmp_path, [
            {"dashboard": DST, "widgets": ["cluster_picker"]},
            {"dashboard_id": STOCK_ID},
            {"dashboard": SRC},
        ])
        assert check_dashboard_navigations([src, dst]) == []
        # target supplied through the corpus only
        assert check_dashboard_navigations([src], corpus=[dst]) == []

    def test_unresolved_name_names_dashboard_widget_and_reference(self, tmp_path):
        from vcfcf_core.dashboards.loader import check_dashboard_navigations
        src, _ = self._pair(tmp_path, [{"dashboard": "[VCF Content Factory] Nope"}])
        errs = check_dashboard_navigations([src])
        assert len(errs) == 1
        assert SRC in errs[0] and "'src_list'" in errs[0] and "[VCF Content Factory] Nope" in errs[0]

    def test_unknown_receiving_widget(self, tmp_path):
        from vcfcf_core.dashboards.loader import check_dashboard_navigations
        src, dst = self._pair(tmp_path, [{"dashboard": DST, "widgets": ["cluster_picker", "ghost"]}])
        errs = check_dashboard_navigations([src, dst])
        assert len(errs) == 1
        assert SRC in errs[0] and "'src_list'" in errs[0] and "'ghost'" in errs[0] and DST in errs[0]

    def test_section_is_not_a_receiver(self, tmp_path):
        from vcfcf_core.dashboards.loader import check_dashboard_navigations
        dst_doc = _dash(DST, DST_ID, [
            {"id": "hdr", "type": "Section", "title": "H", "coords": {"x": 1, "y": 1}},
            _rl("cluster_picker", y=2),
        ])
        dst = _load_doc(tmp_path, dst_doc, "t.yaml")
        src = _load_doc(tmp_path, _dash(SRC, SRC_ID, [_rl("s", navigations=[
            {"dashboard": DST, "widgets": ["hdr"]}])]), "s.yaml")
        assert any("'hdr'" in e for e in check_dashboard_navigations([src, dst]))

    def test_ambiguous_name(self, tmp_path):
        from vcfcf_core.dashboards.loader import check_dashboard_navigations
        src, dst = self._pair(tmp_path, [{"dashboard": DST}])
        twin_doc = _target_doc()
        twin_doc["id"] = "33333333-3333-4333-8333-333333333333"
        twin = _load_doc(tmp_path, twin_doc, "twin.yaml")
        errs = check_dashboard_navigations([src], corpus=[dst, twin])
        assert len(errs) == 1 and "ambiguous" in errs[0]


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class TestRender:
    def test_wire_shape(self, tmp_path):
        src = _load_doc(tmp_path, _dash(SRC, SRC_ID, [
            _rl("src_list", navigations=[
                {"dashboard": DST, "widgets": ["cluster_picker", "cluster_metrics"]},
                {"dashboard": DST, "widgets": []},
                {"dashboard_id": STOCK_ID, "label": "Cluster Performance"},
            ]),
            _txt("no_nav"),
        ]), "s.yaml")
        dst = _load_doc(tmp_path, _target_doc(), "t.yaml")
        out = _render([src, dst])
        by_id = {d["id"]: d for d in out["dashboards"]}
        navs = by_id[SRC_ID]["dashboardNavigations"]
        tw = {w.local_id: w.widget_id for w in dst.widgets}
        assert list(navs) == [src.widgets[0].widget_id]
        assert navs[src.widgets[0].widget_id] == [
            {"id": DST_ID, "widgets": [
                {"interactionType": "resourceId", "id": tw["cluster_picker"]},
                {"interactionType": "resourceId", "id": tw["cluster_metrics"]},
            ]},
            {"id": DST_ID, "widgets": []},
            {"id": STOCK_ID, "widgets": []},
        ]
        # receiver ids are real widget ids on the rendered target
        rendered_target_ids = {w["id"] for w in by_id[DST_ID]["widgets"]}
        assert {tw["cluster_picker"], tw["cluster_metrics"]} <= rendered_target_ids
        # a dashboard without navigations keeps the historical {}
        assert by_id[DST_ID]["dashboardNavigations"] == {}
        # label is documentation only
        assert "Cluster Performance" not in json.dumps(navs)

    def test_self_target(self, tmp_path):
        d = _load_doc(tmp_path, _dash(SRC, SRC_ID, [
            _rl("a", navigations=[{"dashboard": SRC, "widgets": ["b"]}]), _txt("b"),
        ]))
        navs = _render([d])["dashboards"][0]["dashboardNavigations"]
        assert navs == {d.widgets[0].widget_id: [
            {"id": SRC_ID, "widgets": [{"interactionType": "resourceId", "id": d.widgets[1].widget_id}]},
        ]}

    def test_target_resolves_through_known_dashboards(self, tmp_path):
        src = _load_doc(tmp_path, _dash(SRC, SRC_ID, [_rl("s", navigations=[
            {"dashboard": DST, "widgets": ["cluster_picker"]}])]), "s.yaml")
        dst = _load_doc(tmp_path, _target_doc(), "t.yaml")
        out = _render([src], known=[dst])
        assert len(out["dashboards"]) == 1  # the target is not rendered, only resolved
        entry = out["dashboards"][0]["dashboardNavigations"][src.widgets[0].widget_id][0]
        assert entry["id"] == DST_ID

    def test_unresolved_target_raises(self, tmp_path):
        from vcfcf_core.dashboards.render import UnresolvedDashboardNavigationError
        src = _load_doc(tmp_path, _dash(SRC, SRC_ID, [_rl("s", navigations=[{"dashboard": DST}])]))
        with pytest.raises(UnresolvedDashboardNavigationError, match=DST.replace("[", r"\[").replace("]", r"\]")):
            _render([src])

    def test_unknown_receiver_raises(self, tmp_path):
        from vcfcf_core.dashboards.render import UnresolvedDashboardNavigationError
        src = _load_doc(tmp_path, _dash(SRC, SRC_ID, [_rl("s", navigations=[
            {"dashboard": DST, "widgets": ["ghost"]}])]), "s.yaml")
        dst = _load_doc(tmp_path, _target_doc(), "t.yaml")
        with pytest.raises(UnresolvedDashboardNavigationError, match="ghost"):
            _render([src, dst])

    def test_empty_navigations_list_is_byte_identical(self, tmp_path):
        from vcfcf_core.dashboards.render import render_dashboards_bundle_json
        plain = _load_doc(tmp_path, _dash(SRC, SRC_ID, [_rl("a"), _txt("b")]), "p.yaml")
        empty = _load_doc(tmp_path, _dash(SRC, SRC_ID, [_rl("a", navigations=[]), _txt("b")]), "e.yaml")
        assert (render_dashboards_bundle_json([plain], {}, OWNER)
                == render_dashboards_bundle_json([empty], {}, OWNER))


# ---------------------------------------------------------------------------
# Byte-identical regression over every dashboard YAML in the repo
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent


def _repo_dashboard_trees():
    trees = [(_REPO / "content" / "dashboards", [_REPO / "content" / "views"])]
    tp = _REPO / "third_party"
    if tp.is_dir():
        for proj in sorted(tp.iterdir()):
            if (proj / "dashboards").is_dir():
                trees.append((proj / "dashboards", [proj / "views", _REPO / "content" / "views"]))
    return trees


def _load_repo_corpus():
    import warnings
    from vcfcf_core.dashboards.loader import load_dashboard, load_view

    def _no_mint(p):
        raise AssertionError(f"repo YAML without id: {p}")

    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for ddir, vdirs in _repo_dashboard_trees():
            views = {}
            for vd in vdirs:
                for vp in sorted(vd.rglob("*.y*ml")) if vd.is_dir() else []:
                    v = load_view(vp, enforce_framework_prefix=False, on_missing_id=_no_mint)
                    views.setdefault(v.name, v)
            for dp in sorted(ddir.rglob("*.y*ml")):
                out.append((load_dashboard(dp, enforce_framework_prefix=False, on_missing_id=_no_mint), views))
    return out


def test_repo_dashboards_render_byte_identically_with_navigation_support(capsys):
    """No repo dashboard declares navigations today, so each must keep the
    historical ``"dashboardNavigations": {}`` and render to the same bytes
    whether or not the renderer is handed the whole repo as navigation
    targets. (The before/after diff against the pre-change renderer is in
    the PR description; this guards the contract going forward.)"""
    from vcfcf_core.dashboards.render import render_dashboards_bundle_json

    corpus = _load_repo_corpus()
    assert corpus, "expected dashboards under content/dashboards"
    all_dashes = [d for d, _ in corpus]
    for d, views in corpus:
        if any(w.navigations for w in d.widgets):
            continue  # authored navigations are covered by TestRender
        alone = render_dashboards_bundle_json([d], views, OWNER)
        with_corpus = render_dashboards_bundle_json([d], views, OWNER, known_dashboards=all_dashes)
        assert alone == with_corpus, d.name
        assert '"dashboardNavigations": {}' in alone, d.name
    capsys.readouterr()


# ---------------------------------------------------------------------------
# Validate chain (python3 -m vcfcf_dashboards validate)
# ---------------------------------------------------------------------------


def _validate_explicit(tmp_path: Path) -> int:
    from vcfcf_dashboards.cli import main
    return main([
        "--views-dir", str(tmp_path / "content" / "views"),
        "--dashboards-dir", str(tmp_path / "content" / "dashboards"),
        "validate",
    ])


class TestValidateChain:
    def test_unresolved_name_fails_validate(self, tmp_path, capsys):
        _write(tmp_path / "content" / "dashboards" / "s.yaml",
               _dash(SRC, SRC_ID, [_rl("src_list", navigations=[{"dashboard": DST}])]))
        assert _validate_explicit(tmp_path) == 1
        err = capsys.readouterr().err
        assert "INVALID" in err and SRC in err and "'src_list'" in err and DST in err

    def test_unknown_receiver_fails_validate(self, tmp_path, capsys):
        _write(tmp_path / "content" / "dashboards" / "s.yaml",
               _dash(SRC, SRC_ID, [_rl("src_list", navigations=[
                   {"dashboard": DST, "widgets": ["ghost"]}])]))
        _write(tmp_path / "content" / "dashboards" / "t.yaml", _target_doc())
        assert _validate_explicit(tmp_path) == 1
        err = capsys.readouterr().err
        assert SRC in err and "'src_list'" in err and "'ghost'" in err

    def test_resolving_navigation_passes_validate(self, tmp_path, capsys):
        _write(tmp_path / "content" / "dashboards" / "s.yaml",
               _dash(SRC, SRC_ID, [_rl("src_list", navigations=[
                   {"dashboard": DST, "widgets": ["cluster_picker"]},
                   {"dashboard_id": STOCK_ID}])]))
        _write(tmp_path / "content" / "dashboards" / "t.yaml", _target_doc())
        assert _validate_explicit(tmp_path) == 0
        capsys.readouterr()

    def test_full_corpus_validate_resolves_third_party_targets(self, tmp_path, monkeypatch, capsys):
        """Default-path validate resolves names against content/dashboards/
        plus third_party/*/dashboards/, and checks third-party sources too."""
        from vcfcf_dashboards.cli import main
        tp_name = "Third Party Target"
        _write(tmp_path / "content" / "dashboards" / "s.yaml",
               _dash(SRC, SRC_ID, [_rl("src_list", navigations=[
                   {"dashboard": tp_name, "widgets": ["tp_list"]}])]))
        _write(tmp_path / "third_party" / "proj" / "dashboards" / "tp.yaml",
               _dash(tp_name, DST_ID, [_rl("tp_list")]))
        monkeypatch.chdir(tmp_path)
        assert main(["validate"]) == 0, capsys.readouterr().err
        # a broken third-party source fails the same chain
        _write(tmp_path / "third_party" / "proj" / "dashboards" / "tp2.yaml",
               _dash("Third Party Source", "44444444-4444-4444-8444-444444444444",
                     [_rl("x", navigations=[{"dashboard": "Missing Thing"}])]))
        assert main(["validate"]) == 1
        err = capsys.readouterr().err
        assert "Third Party Source" in err and "Missing Thing" in err


# ---------------------------------------------------------------------------
# Packaging: bundle must carry every named target
# ---------------------------------------------------------------------------


def _bundle_repo(tmp_path: Path, include_target: bool, extra_navs=None) -> Path:
    navs = [{"dashboard": DST, "widgets": ["cluster_picker"]}] + list(extra_navs or [])
    _write(tmp_path / "content" / "dashboards" / "s.yaml",
           _dash(SRC, SRC_ID, [_rl("src_list", navigations=navs)]))
    _write(tmp_path / "content" / "dashboards" / "t.yaml", _target_doc())
    dashboards = ["content/dashboards/s.yaml"] + (["content/dashboards/t.yaml"] if include_target else [])
    return _write(tmp_path / "bundles" / "nav.yaml", {
        "name": "nav", "description": "nav bundle", "dashboards": dashboards,
    })


class TestPackaging:
    def test_bundle_missing_named_target_fails_naming_it(self, tmp_path):
        from vcfcf_core.packaging.loader import BundleValidationError, load_bundle
        manifest = _bundle_repo(tmp_path, include_target=False)
        with pytest.raises(BundleValidationError) as ei:
            load_bundle(manifest, repo_root=tmp_path)
        assert DST in str(ei.value) and "not in this bundle" in str(ei.value)

    def test_bundle_carrying_target_renders_and_lists_prerequisites(self, tmp_path):
        from vcfcf_core.packaging.assembly import render_bundle_payloads
        from vcfcf_core.packaging.loader import check_bundle_dashboard_navigations, load_bundle
        manifest = _bundle_repo(tmp_path, include_target=True, extra_navs=[
            {"dashboard_id": STOCK_ID, "label": "Cluster Performance"}])
        bundle = load_bundle(manifest, repo_root=tmp_path)
        payloads = render_bundle_payloads(bundle, sm_map={}, bundle_context="nav")
        rendered = json.loads(payloads.dashboard_json)
        src = next(d for d in rendered["dashboards"] if d["id"] == SRC_ID)
        assert [e["id"] for e in next(iter(src["dashboardNavigations"].values()))] == [DST_ID, STOCK_ID]
        prereqs = check_bundle_dashboard_navigations(bundle.dashboards, "nav")
        assert len(prereqs) == 1
        assert STOCK_ID in prereqs[0] and "Cluster Performance" in prereqs[0] and SRC in prereqs[0]

    def test_synthetic_bundle_missing_target_fails_in_render(self, tmp_path):
        """Discrete builds assemble a Bundle without load_bundle; the rule
        must hold in render_bundle_payloads too."""
        from vcfcf_core.packaging.assembly import render_bundle_payloads
        from vcfcf_core.packaging.loader import Bundle, BundleValidationError
        src = _load_doc(tmp_path, _dash(SRC, SRC_ID, [_rl("s", navigations=[{"dashboard": DST}])]))
        bundle = Bundle(name="x", description="", sync_enabled=True, supermetrics=[],
                        views=[], dashboards=[src], customgroups=[])
        with pytest.raises(BundleValidationError, match="not in this bundle"):
            render_bundle_payloads(bundle, sm_map={}, bundle_context="discrete:dashboard:x")

    def test_builder_prints_prerequisites(self, tmp_path, capsys):
        from vcfcf_core.packaging.loader import load_bundle
        from vcfcf_packaging.builder import _print_navigation_prerequisites
        manifest = _bundle_repo(tmp_path, include_target=True, extra_navs=[{"dashboard_id": STOCK_ID}])
        _print_navigation_prerequisites(load_bundle(manifest, repo_root=tmp_path), "nav")
        err = capsys.readouterr().err
        assert "PREREQUISITE" in err and STOCK_ID in err


# ---------------------------------------------------------------------------
# Extract: reverse_local (multi-dashboard) and the live writer
# ---------------------------------------------------------------------------

# Source-side wire ids (what an export carries). Local ids after reversal are
# these same strings (reverse_local_id keeps a UUID intact).
W_SRC_LIST = "aaaaaaaa-0000-4000-8000-000000000001"
W_SRC_TXT = "aaaaaaaa-0000-4000-8000-000000000002"
W_DST_LIST = "bbbbbbbb-0000-4000-8000-000000000001"
W_DST_TXT = "bbbbbbbb-0000-4000-8000-000000000002"
FOREIGN_ID = "d503b4dc-ecb4-4df5-9039-4509a9ae741b"


def _wire_widget(wid, wtype, x):
    w = {"id": wid, "type": wtype, "title": wid,
         "gridsterCoords": {"x": x, "y": 1, "w": 4, "h": 4}, "config": {}}
    if wtype == "TextDisplay":
        w["config"] = {"html": "<b>x</b>"}
    return w


def _export_json() -> dict:
    src = {
        "id": SRC_ID, "name": "Vendor/Source Dash", "namePath": "Vendor",
        "widgets": [_wire_widget(W_SRC_LIST, "TextDisplay", 1), _wire_widget(W_SRC_TXT, "TextDisplay", 5)],
        "widgetInteractions": [],
        "dashboardNavigations": {
            W_SRC_LIST: [
                {"id": DST_ID, "widgets": [{"interactionType": "resourceId", "id": W_DST_LIST},
                                           {"interactionType": "resourceId", "id": "gone-widget"}]},
                {"id": FOREIGN_ID, "widgets": [{"interactionType": "resourceId", "id": "x"}]},
                {"id": SRC_ID, "widgets": [{"interactionType": "resourceId", "id": W_SRC_TXT}]},
            ],
            # stale key: vendor exports carry entries for widgets no longer on the dashboard
            "cccccccc-0000-4000-8000-000000000009": [{"id": DST_ID, "widgets": []}],
        },
    }
    dst = {
        "id": DST_ID, "name": "Vendor/Target Dash", "namePath": "Vendor",
        "widgets": [_wire_widget(W_DST_LIST, "TextDisplay", 1), _wire_widget(W_DST_TXT, "TextDisplay", 5)],
        "widgetInteractions": [],
        "dashboardNavigations": {W_DST_TXT: [{"id": SRC_ID, "widgets": []}]},
    }
    return {"entries": {"resourceKind": []}, "dashboards": [src, dst]}


class TestExtract:
    def test_reverse_local_round_trip(self, tmp_path, capsys):
        from vcfcf_core.dashboards.loader import check_dashboard_navigations
        from vcfcf_core.extractor.reverse_local import reverse_local_port

        src_json = tmp_path / "export.json"
        src_json.write_text(json.dumps(_export_json()))
        empty = tmp_path / "empty"
        empty.mkdir()
        out_d = tmp_path / "out" / "dashboards"
        # reverse_local records the parser's UserWarnings itself (stale key)
        rc = reverse_local_port(
            source_dashboard_json=src_json, source_view_xml_dir=empty, sm_yaml_dir=empty,
            output_views_dir=tmp_path / "out" / "views", output_dashboards_dir=out_d,
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "2 MATCH" in captured.out

        src_doc = yaml.safe_load((out_d / "Source Dash.yaml").read_text())
        navs = {w["id"]: w.get("navigations") for w in src_doc["widgets"]}
        assert navs[W_SRC_LIST] == [
            {"dashboard": "Target Dash", "widgets": [W_DST_LIST]},  # gone-widget dropped
            {"dashboard_id": FOREIGN_ID},                            # outside the extraction
            {"dashboard": "Source Dash", "widgets": [W_SRC_TXT]},   # self-target
        ]
        assert navs[W_SRC_TXT] is None
        assert "gone-widget" in captured.err and FOREIGN_ID in captured.err
        dst_doc = yaml.safe_load((out_d / "Target Dash.yaml").read_text())
        assert {w["id"]: w.get("navigations") for w in dst_doc["widgets"]}[W_DST_TXT] == [
            {"dashboard": "Source Dash"}]

        # The written YAML loads, validates, resolves, and renders back to the
        # source graph (receivers are the re-derived widget ids of the target).
        src_d = _load(out_d / "Source Dash.yaml")
        dst_d = _load(out_d / "Target Dash.yaml")
        assert check_dashboard_navigations([src_d, dst_d]) == []
        out = _render([src_d, dst_d])
        by_id = {d["id"]: d for d in out["dashboards"]}
        src_w = {w.local_id: w.widget_id for w in src_d.widgets}
        dst_w = {w.local_id: w.widget_id for w in dst_d.widgets}
        assert by_id[SRC_ID]["dashboardNavigations"] == {src_w[W_SRC_LIST]: [
            {"id": DST_ID, "widgets": [{"interactionType": "resourceId", "id": dst_w[W_DST_LIST]}]},
            {"id": FOREIGN_ID, "widgets": []},
            {"id": SRC_ID, "widgets": [{"interactionType": "resourceId", "id": src_w[W_SRC_TXT]}]},
        ]}
        assert by_id[DST_ID]["dashboardNavigations"] == {dst_w[W_DST_TXT]: [{"id": SRC_ID, "widgets": []}]}

    def test_live_writer_labels_external_targets_and_resolves_self(self, tmp_path, capsys):
        from vcfcf_core.extractor.extractor import _write_dashboard_yaml
        src = _export_json()["dashboards"][0]
        path = tmp_path / "dash.yaml"
        with pytest.warns(UserWarning):  # stale source key
            _write_dashboard_yaml(path, src, SRC_ID, {}, factory_native=False,
                                  dashboard_names_by_id={DST_ID: "Target Dash"})
        doc = yaml.safe_load(path.read_text())
        navs = {w["id"]: w.get("navigations") for w in doc["widgets"]}
        # one dashboard per live extraction: only the self-target resolves by name
        assert navs[W_SRC_LIST] == [
            {"dashboard_id": DST_ID, "label": "Target Dash"},
            {"dashboard_id": FOREIGN_ID},
            {"dashboard": "Source Dash", "widgets": [W_SRC_TXT]},
        ]
        d = _load(path)  # the written YAML is loader-valid
        d.validate({}, enforce_framework_prefix=False)
        capsys.readouterr()

    def test_reverse_parser_keeps_raw_form(self):
        from vcfcf_core.dashboards.reverse import parse_dashboard_json
        with pytest.warns(UserWarning, match="not a parsed widget"):
            d = parse_dashboard_json(_export_json()["dashboards"][0], {})
        nav = d.widgets[0].navigations
        assert [(n.dashboard, n.dashboard_id, n.widgets) for n in nav] == [
            ("", DST_ID, [W_DST_LIST, "gone-widget"]),
            ("", FOREIGN_ID, ["x"]),
            ("", SRC_ID, [W_SRC_TXT]),
        ]
