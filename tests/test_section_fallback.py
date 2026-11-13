"""section_fallback: omit, one YAML source and two variants (2026-11-13).

A dashboard that sets ``section_fallback: omit`` ships without its Section
widgets where the target cannot import Section (8.18.7 and 9.0.x measured,
9.1.0 unmeasured) and with them from 9.1.1. Covered here through the entry
points: the loader and validate, the transform and its row closing, the
renderer (both variants from one source, byte-identical output for
everything else), the Tier 2 pak build at a low and a high floor and with
the ``--sections`` override (factory CLI and buildkit __main__), live sync
by instance version (CLI, dashboards handler, bundle preflight), the local
``package`` command, and the offline importer (never emits the key).
"""
from __future__ import annotations

import io
import json
import sys
import textwrap
import types
import warnings
import zipfile
from pathlib import Path

import pytest
import yaml

from vcfcf_core.dashboards import widget_versions as wv
from vcfcf_core.dashboards.loader import (
    DashboardValidationError,
    apply_section_fallback,
    load_all as core_load_all,
    load_dashboard as core_load_dashboard,
)
from vcfcf_core.dashboards.render import render_dashboards_bundle_json
from vcfcf_dashboards import cli as dash_cli
from vcfcf_dashboards import client as dash_client
from vcfcf_dashboards import handler as dash_handler
from vcfcf_dashboards.client import VERSION_UNREADABLE_NOTE

REPO_ROOT = Path(__file__).resolve().parents[1]
OWNER = "00000000-0000-0000-0000-000000000000"

_D_ID = "3c1d2e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f"
_PLAIN_ID = "4d2e3f50-6b7c-4d8e-9fa0-1b2c3d4e5f60"
_BARE_ID = "5e3f4061-7c8d-4e9f-a0b1-2c3d4e5f6071"


def _text(wid, x, y, w, h):
    return {"id": wid, "type": "TextDisplay", "title": wid.upper(),
            "coords": {"x": x, "y": y, "w": w, "h": h}, "text": wid}


def _section(wid, y, **extra):
    return {"id": wid, "type": "Section", "title": f"Section {wid}",
            "coords": {"x": 1, "y": y}, **extra}


#: intro (row 1-2), s1 (row 3), a|b (rows 4-6), s2 (row 7), c (rows 8-9).
SOURCE_WIDGETS = [
    _text("intro", 1, 1, 12, 2),
    _section("s1", 3),
    _text("a", 1, 4, 6, 3),
    _text("b", 7, 4, 6, 3),
    _section("s2", 7),
    _text("c", 1, 8, 12, 2),
]
#: The same dashboard written by hand without Sections, rows closed up.
EXPECTED_WITHOUT = [
    _text("intro", 1, 1, 12, 2),
    _text("a", 1, 3, 6, 3),
    _text("b", 7, 3, 6, 3),
    _text("c", 1, 6, 12, 2),
]
INTERACTIONS = [{"from": "a", "to": "b"}]


def _dash_yaml(widgets, *, name="[VCF CF] Section Fallback Probe", dash_id=_D_ID,
               fallback="omit", interactions=INTERACTIONS):
    data = {"id": dash_id, "name": name, "description": "probe"}
    if fallback is not None:
        data["section_fallback"] = fallback
    data["widgets"] = widgets
    if interactions:
        data["interactions"] = interactions
    return yaml.safe_dump(data, sort_keys=False)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _load(path: Path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = core_load_dashboard(path)
        d.validate({})
    return d


def _render(d) -> str:
    return render_dashboards_bundle_json([d], {}, OWNER)


def _widget_types(rendered: str):
    return [w["type"] for w in json.loads(rendered)["dashboards"][0]["widgets"]]


@pytest.fixture
def source(tmp_path):
    return _write(tmp_path / "content" / "dashboards" / "probe.yaml", _dash_yaml(SOURCE_WIDGETS))


# --- 1. the YAML key -----------------------------------------------------------

def test_key_loads(source):
    d = _load(source)
    assert d.section_fallback == "omit" and d.section_count == 2


@pytest.mark.parametrize("bad", ["drop", "", "OMIT", True, 1, ["omit"]])
def test_bad_value_names_the_allowed_values(tmp_path, bad):
    p = _write(tmp_path / "d.yaml", _dash_yaml(SOURCE_WIDGETS, fallback=bad))
    with pytest.raises(DashboardValidationError) as exc:
        core_load_dashboard(p)
    assert "section_fallback must be one of omit" in str(exc.value)
    assert str(p) in str(exc.value)


def test_key_without_a_section_is_an_error(tmp_path):
    """Precedent: an omit: entry meaningless for the YAML is a load error."""
    p = _write(tmp_path / "d.yaml", _dash_yaml(EXPECTED_WITHOUT))
    with pytest.raises(DashboardValidationError, match="has none; remove the key"):
        core_load_dashboard(p)


def test_collapsed_section_whose_members_would_overlap_is_rejected(tmp_path):
    widgets = [
        _section("s1", 1, collapsed=True),
        _text("a", 1, 2, 12, 4),     # rows 2-5, hidden while s1 is collapsed
        _section("s2", 3),           # the UI floats s2 up under a collapsed s1
        _text("c", 1, 4, 12, 2),     # rows 4-5: under a once s1 is gone
    ]
    p = _write(tmp_path / "d.yaml", _dash_yaml(widgets, interactions=None))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = core_load_dashboard(p)
        with pytest.raises(DashboardValidationError) as exc:
            d.validate({})
    assert "widgets 'a' and 'c' overlap" in str(exc.value)
    assert "collapsed Section 's1'" in str(exc.value)
    # The same layout without the key is the Section variant only: fine.
    p2 = _write(tmp_path / "d2.yaml", _dash_yaml(widgets, interactions=None, fallback=None))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        core_load_dashboard(p2).validate({})


def test_validate_warning_says_where_the_key_applies(source):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        core_load_all(source.parent.parent / "views", source.parent)
    hits = [str(w.message) for w in caught if "issue #199" in str(w.message)]
    assert len(hits) == 1
    assert "section_fallback: omit applies where a target version is known" in hits[0]
    assert "their installers still refuse" in hits[0]


# --- 2. the transform ----------------------------------------------------------

def test_both_variants_from_one_source(source, tmp_path):
    d = _load(source)
    shipped = _render(d)
    assert _widget_types(shipped).count("Section") == 2
    without = d.without_sections()
    assert d.section_count == 2, "the source object is not changed"
    expected = _load(_write(tmp_path / "expected.yaml",
                            _dash_yaml(EXPECTED_WITHOUT, fallback=None)))
    # Byte for byte the hand-written Section-less dashboard: widget ids
    # (dashboard name + local id), coords closed up, interactions kept.
    assert _render(without) == _render(expected)
    assert "Section" not in _widget_types(_render(without))


def test_interactions_and_ids_survive(source):
    d = _load(source)
    without = d.without_sections()
    ids = {w.local_id: w.widget_id for w in d.widgets}
    assert {w.local_id: w.widget_id for w in without.widgets} == {
        k: v for k, v in ids.items() if k not in ("s1", "s2")}
    obj = json.loads(_render(without))["dashboards"][0]
    assert obj["widgetInteractions"] == [{"widgetIdProvider": ids["a"], "type": "resourceId",
                                          "widgetIdReceiver": ids["b"]}]
    # No member list of a removed Section is left anywhere.
    assert ids["s1"] not in _render(without) and ids["s2"] not in _render(without)


def test_a_row_still_covered_is_not_closed(tmp_path):
    widgets = [
        _text("tall", 1, 1, 3, 6),   # rows 1-6 cover the Section's row 3
        _section("s1", 3),
        _text("low", 1, 7, 12, 2),
    ]
    p = _write(tmp_path / "d.yaml", _dash_yaml(widgets, interactions=None))
    without = _load(p).without_sections()
    assert {w.local_id: w.coords["y"] for w in without.widgets} == {"tall": 1, "low": 7}


def _rows_after(tmp_path, widgets):
    p = _write(tmp_path / "d.yaml", _dash_yaml(widgets, interactions=None))
    return {w.local_id: w.coords["y"] for w in _load(p).without_sections().widgets}


def test_two_adjacent_sections_close_both_rows(tmp_path):
    widgets = [_text("top", 1, 1, 12, 2), _section("s1", 3), _section("s2", 4),
               _text("a", 1, 5, 12, 2)]
    assert _rows_after(tmp_path, widgets) == {"top": 1, "a": 3}


def test_section_on_the_last_row_moves_nothing_further(tmp_path):
    """s1's row closes (a rises one); the trailing Section has nothing below."""
    widgets = [_text("top", 1, 1, 12, 2), _section("s1", 3), _text("a", 1, 4, 12, 2),
               _section("tail", 6)]
    assert _rows_after(tmp_path, widgets) == {"top": 1, "a": 3}


def test_y_below_one_is_counted_as_the_rendered_row(tmp_path):
    """DEF-013: the renderer clamps y to at least 1, so a 0-based Section
    renders on a's row 1; that row is covered and not closed, and a and b
    do not overlap on the wire after the omission (review NIT 1)."""
    widgets = [_section("s1", 0), _text("a", 1, 1, 12, 2), _text("b", 1, 3, 12, 2)]
    p = _write(tmp_path / "d.yaml", _dash_yaml(widgets, interactions=None))
    without = _load(p).without_sections()
    wire = json.loads(_render(without))["dashboards"][0]["widgets"]
    spans = sorted((w["gridsterCoords"]["y"], w["gridsterCoords"]["h"]) for w in wire)
    assert spans == [(1, 2), (3, 2)]
    for (y1, h1), (y2, _h2) in zip(spans, spans[1:]):
        assert y1 + h1 <= y2


def test_without_sections_is_identity_without_a_section(tmp_path):
    d = _load(_write(tmp_path / "d.yaml", _dash_yaml(EXPECTED_WITHOUT, fallback=None)))
    assert d.without_sections() is d


# --- 3. the decision ------------------------------------------------------------

@pytest.mark.parametrize("target,omitted", [
    ("8.18.7", True), ("9.0.2", True), ("9.0.9", True),
    ("9.1.0", True),      # unmeasured: omitting is the conservative choice
    ("9.1.1", False), ("9.1.1.0100", False), ("9.2", False),
])
def test_auto_decision_by_target(source, target, omitted):
    d = _load(source)
    out, notes = apply_section_fallback([d], target)
    assert (out[0].section_count == 0) is omitted
    if omitted:
        assert len(notes) == 1 and notes[0].startswith("SECTIONS OMITTED: ")
        assert f"'{d.name}': 2 Section widget(s) left out (section_fallback: omit)" in notes[0]
        assert f"the target is VCF Operations {wv.format_ops_version(wv.parse_ops_version(target))}" in notes[0]
        assert "below 9.1.1, the first VCF Operations build proven to import Section" in notes[0]
        assert "measured not to import below 9.1.0" in notes[0]
    else:
        assert notes == [] and out[0] is d


def test_the_governing_constant_is_the_proven_floor():
    assert wv.section_ship_floor() == wv.parse_ops_version(wv.WIDGET_TYPE_MIN_OPS_VERSION["Section"])
    assert wv.section_ship_floor() > wv.parse_ops_version(wv.WIDGET_TYPE_REFUSE_BELOW_OPS_VERSION["Section"])


def test_unknown_target(source):
    d = _load(source)
    out, notes = apply_section_fallback([d], None)
    assert out[0] is d and notes == []                     # no target declared: as authored
    out, notes = apply_section_fallback([d], None, unknown_target="omit")
    assert out[0].section_count == 0
    assert "the target version could not be read" in notes[0]


def test_overrides(source):
    d = _load(source)
    out, notes = apply_section_fallback([d], "9.2", sections="omit")
    assert out[0].section_count == 0 and "--sections omit was given" in notes[0]
    out, notes = apply_section_fallback([d], "8.18.7", sections="ship")
    assert out[0] is d
    assert notes[0].startswith("SECTIONS KEPT BELOW FLOOR (--sections ship)")
    assert "loses EVERY dashboard in the same import" in notes[0]
    assert apply_section_fallback([d], "9.1.1", sections="ship") == ([d], [])
    with pytest.raises(ValueError, match="auto, ship, omit"):
        apply_section_fallback([d], "9.1.1", sections="never")


def test_without_the_key_nothing_changes(tmp_path):
    d = _load(_write(tmp_path / "d.yaml", _dash_yaml(SOURCE_WIDGETS, fallback=None)))
    for target in ("8.18.7", "9.0.2", None):
        for sections in ("auto", "omit"):
            out, notes = apply_section_fallback([d], target, sections=sections, unknown_target="omit")
            assert out[0] is d and notes == []


def test_cli_choices_match_the_core_table():
    from vcfcf_managementpacks.buildkit import _KIT_MAIN
    from vcfcf_managementpacks import cli as mp_cli
    assert wv.SECTIONS_CHOICES == ("auto", "ship", "omit")
    for parser in (mp_cli.build_parser(), dash_cli.build_parser()):
        sub = next(a for a in parser._actions if a.dest in ("command", "cmd"))
        for name in ("build-sdk", "package"):
            if name in sub.choices:
                act = next(a for a in sub.choices[name]._actions if a.dest == "sections")
                assert tuple(act.choices) == wv.SECTIONS_CHOICES and act.default == "auto"
    assert '"--sections"' in _KIT_MAIN and 'choices=("auto", "ship", "omit")' in _KIT_MAIN


# --- 4. byte-identical output for everything without the key ------------------

def _repo_dashboard_dirs():
    dirs = [REPO_ROOT / "content" / "dashboards", REPO_ROOT / "tests" / "fixtures"]
    dirs += sorted((REPO_ROOT / "third_party").glob("*/dashboards"))
    return [d for d in dirs if d.is_dir()]


def test_no_repo_dashboard_sets_the_key_and_none_is_changed():
    """Every dashboard YAML in the repo loads unchanged through
    apply_section_fallback at every target: the same objects come back, so
    the renderer sees exactly what it saw before."""
    seen = 0
    for base in _repo_dashboard_dirs():
        for p in sorted(base.rglob("*.y*ml")):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    d = core_load_dashboard(p, enforce_framework_prefix=False)
            except Exception:  # noqa: BLE001  not a dashboard YAML
                continue
            seen += 1
            assert d.section_fallback is None, p
            for target in ("8.18.7", "9.0.2", "9.1.0", "9.1.1", None):
                out, notes = apply_section_fallback([d], target, unknown_target="omit")
                assert out[0] is d and notes == [], p
    assert seen > 10


def test_key_set_and_shipped_renders_like_no_key(source, tmp_path):
    with_key = _load(source)
    no_key = _load(_write(tmp_path / "nokey.yaml", _dash_yaml(SOURCE_WIDGETS, fallback=None)))
    out, _notes = apply_section_fallback([with_key], "9.1.1")
    assert _render(out[0]) == _render(no_key)


# --- 5. Tier 2 pak build ---------------------------------------------------------

def _sdk_project(base: Path, *, fallback="omit", second=None) -> Path:
    project = base / "probe_adapter"
    dashboards = ["dashboards/probe.yaml"] + ([second] if second else [])
    _write(project / "adapter.yaml", textwrap.dedent("""\
        name: "Probe Adapter"
        version: "1.0.0"
        build_number: 1
        adapter_kind: "probe_kind"
        tier: 2
        content_naming: unprefixed
        bundled_content:
          dashboards:
        """) + "".join(f"    - {d}\n" for d in dashboards))
    _write(project / "describe.xml",
           '<?xml version="1.0" encoding="UTF-8"?>\n<AdapterKind key="probe_kind" nameKey="1" version="1">'
           '<ResourceKinds><ResourceKind key="probe_world" nameKey="2" type="1"/></ResourceKinds></AdapterKind>\n')
    _write(project / "dashboards" / "probe.yaml",
           _dash_yaml(SOURCE_WIDGETS, name="Section Fallback Probe", fallback=fallback))
    return project


class _ReachedCompile(Exception):
    pass


@pytest.fixture
def sb(monkeypatch):
    """build_sdk_pak up to the JDK step: the bundled dashboards it would ship
    are captured from the last content check before the compile."""
    from vcfcf_managementpacks import sdk_builder
    shipped = {}
    real = sdk_builder.check_stock_ids

    def _capture(project, bundled):
        shipped["dashboards"] = list(bundled[1])
        return real(project, bundled)

    def _stop(*_a, **_k):
        raise _ReachedCompile()

    monkeypatch.setattr(sdk_builder, "check_stock_ids", _capture)
    monkeypatch.setattr(sdk_builder, "_detect_jdk", _stop)
    monkeypatch.delenv("VCFCF_RELEASE_BUILD", raising=False)
    sdk_builder._shipped = shipped
    yield sdk_builder
    del sdk_builder._shipped


def _pak_dashboard_json(sb, project, dashboards, out: Path) -> dict:
    """Render the captured dashboards through the pak writer and read the
    dashboard.json back out of the written .pak."""
    from vcfcf_managementpacks.sdk_project import load_sdk_project
    proj = load_sdk_project(project / "adapter.yaml")
    pak = sb._write_outer_pak(proj, b"", out, project, dashboards=dashboards,
                              owning_adapter_kind="probe_kind")
    with zipfile.ZipFile(pak) as z:
        name = next(n for n in z.namelist() if n.endswith("/dashboard.json"))
        return json.loads(z.read(name))["dashboards"][0]


def test_pak_low_floor_ships_the_section_less_variant(sb, tmp_path, capsys):
    assert sb._oldest_supported_line() == "8.18.7"
    project = _sdk_project(tmp_path)
    with pytest.raises(_ReachedCompile):
        sb.build_sdk_pak(project, tmp_path / "out")
    err = capsys.readouterr().err
    assert ("build-sdk: SECTIONS OMITTED: dashboard 'Section Fallback Probe': 2 Section "
            "widget(s) left out (section_fallback: omit): the target is VCF Operations 8.18.7") in err
    (d,) = sb._shipped["dashboards"]
    assert d.section_count == 0
    obj = _pak_dashboard_json(sb, project, [d], tmp_path / "pak")
    assert [w["type"] for w in obj["widgets"]] == ["TextDisplay"] * 4
    assert [w["gridsterCoords"]["y"] for w in obj["widgets"]] == [1, 3, 3, 6]


def test_pak_high_floor_ships_the_sections(sb, tmp_path, capsys, monkeypatch):
    """When 8.x and 9.0 leave RULE-019, the oldest line rises and the same
    source ships its Sections, with no content edit."""
    monkeypatch.setattr(sb, "_SDK_COMPAT_LINES",
                        tuple(l for l in sb._SDK_COMPAT_LINES if l.key == "9.1.1.0100"))
    assert sb._oldest_supported_line() == "9.1.1.0100"
    project = _sdk_project(tmp_path)
    with pytest.raises(_ReachedCompile):
        sb.build_sdk_pak(project, tmp_path / "out")
    assert "SECTIONS OMITTED" not in capsys.readouterr().err
    (d,) = sb._shipped["dashboards"]
    assert d.section_count == 2
    obj = _pak_dashboard_json(sb, project, [d], tmp_path / "pak")
    assert [w["type"] for w in obj["widgets"]].count("Section") == 2


def test_pak_without_the_key_below_the_floor_fails(sb, tmp_path):
    project = _sdk_project(tmp_path, fallback=None)
    with pytest.raises(sb.SdkBuildError) as exc:
        sb.build_sdk_pak(project, tmp_path / "out")
    msg = str(exc.value)
    assert "dashboard 'Section Fallback Probe'" in msg and "widget type Section" in msg
    assert "8.18.7" in msg and "set section_fallback: omit on the dashboard" in msg
    assert "dashboards" not in sb._shipped


def test_pak_without_the_key_at_a_high_floor_builds(sb, tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "_SDK_COMPAT_LINES",
                        tuple(l for l in sb._SDK_COMPAT_LINES if l.key == "9.1.1.0100"))
    project = _sdk_project(tmp_path, fallback=None)
    with pytest.raises(_ReachedCompile):
        sb.build_sdk_pak(project, tmp_path / "out")
    assert sb._shipped["dashboards"][0].section_count == 2


def test_pak_sections_override(sb, tmp_path, capsys, monkeypatch):
    project = _sdk_project(tmp_path)
    with pytest.raises(_ReachedCompile):
        sb.build_sdk_pak(project, tmp_path / "out", sections="ship")
    assert "SECTIONS KEPT BELOW FLOOR (--sections ship)" in capsys.readouterr().err
    assert sb._shipped["dashboards"][0].section_count == 2
    monkeypatch.setattr(sb, "_SDK_COMPAT_LINES",
                        tuple(l for l in sb._SDK_COMPAT_LINES if l.key == "9.1.1.0100"))
    with pytest.raises(_ReachedCompile):
        sb.build_sdk_pak(project, tmp_path / "out", sections="omit")
    assert "--sections omit was given" in capsys.readouterr().err
    assert sb._shipped["dashboards"][0].section_count == 0


def test_validate_sdk_follows_the_floor(tmp_path, capsys):
    from vcfcf_managementpacks.sdk_builder import validate_sdk_project
    errors = validate_sdk_project(_sdk_project(tmp_path / "a"))
    assert not [e for e in errors if e.startswith("version floor")]
    assert "validate-sdk: SECTIONS OMITTED" in capsys.readouterr().err
    errors = validate_sdk_project(_sdk_project(tmp_path / "b", fallback=None))
    assert [e for e in errors if e.startswith("version floor") and "section_fallback: omit" in e]


@pytest.mark.parametrize("sections", ["ship", "omit"])
def test_release_build_refuses_a_forced_variant_factory_cli(tmp_path, capsys, monkeypatch, sections):
    from vcfcf_managementpacks import cli as mp_cli
    monkeypatch.setenv("VCFCF_RELEASE_BUILD", "0")
    monkeypatch.delenv("VCFCF_RELEASE_BUILD")
    rc = mp_cli.main(["build-sdk", str(_sdk_project(tmp_path)), "--release",
                      "--sections", sections, "--output", str(tmp_path / "dist")])
    assert rc == 1
    assert f"--sections {sections} is not allowed on a release build" in capsys.readouterr().err


def test_release_build_refuses_a_forced_variant_buildkit(tmp_path, capsys, monkeypatch):
    """The CI entry: the kit's __main__ (exec'd as the kit test does)."""
    from vcfcf_managementpacks.buildkit import _KIT_MAIN
    ns = {"__name__": "vcfcf_managementpacks._kit_main_probe",
          "__package__": "vcfcf_managementpacks"}
    exec(compile(_KIT_MAIN, "sdk_buildkit/__main__.py", "exec"), ns)
    monkeypatch.setenv("VCFCF_RELEASE_BUILD", "0")
    monkeypatch.delenv("VCFCF_RELEASE_BUILD")
    monkeypatch.setattr(sys, "argv", ["sdk_buildkit", "build-sdk", str(_sdk_project(tmp_path)),
                                      "--release", "--sections", "ship",
                                      "--output", str(tmp_path / "dist")])
    assert ns["main"]() == 1
    assert "--sections ship is not allowed on a release build" in capsys.readouterr().err


def test_buildkit_rewrites_the_new_import():
    from vcfcf_managementpacks.buildkit import _IMPORT_REWRITES, _apply_rewrites
    src = (REPO_ROOT / "src" / "vcfcf_managementpacks" / "sdk_builder.py").read_text(encoding="utf-8")
    out = _apply_rewrites(src, _IMPORT_REWRITES["sdk_builder.py"])
    assert "from .dashboard_loader import apply_section_fallback" in out
    assert "vcfcf_dashboards.loader import apply_section_fallback" not in out
    loader_src = (REPO_ROOT / "src" / "vcfcf_core" / "dashboards" / "loader.py").read_text(encoding="utf-8")
    kit_loader = _apply_rewrites(loader_src, _IMPORT_REWRITES["dashboard_loader.py"])
    assert "from . import widget_versions as _wv" not in kit_loader


# --- 6. live sync by instance version ------------------------------------------

class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class _VersionSession:
    def __init__(self, release_name="VCF Operations 9.0.2.0", status=200):
        self.release_name, self.status, self.calls = release_name, status, []

    def _request(self, method, path, **kw):
        self.calls.append((method, path))
        assert path == "/api/versions/current", path
        return _Resp(self.status, {"releaseName": self.release_name})


def _clean_envelope(n):
    return {"state": "FINISHED", "errorCode": "NONE", "errorMessages": [], "type": "IMPORT",
            "operationSummaries": [{"contentType": "DASHBOARDS", "total": n, "imported": n,
                                    "skipped": 0, "failed": 0, "state": "FINISHED",
                                    "errorMessages": []}]}


def _sync_tree(root: Path, *, bare_section=False):
    """d.yaml: opted in (Sections); plain.yaml: no Section; optionally
    bare.yaml: a Section dashboard without the key."""
    d = root / "content" / "dashboards"
    _write(d / "d.yaml", _dash_yaml(SOURCE_WIDGETS))
    _write(d / "plain.yaml", _dash_yaml(EXPECTED_WITHOUT, name="[VCF CF] Plain Probe",
                                        dash_id=_PLAIN_ID, fallback=None))
    if bare_section:
        _write(d / "bare.yaml", _dash_yaml(SOURCE_WIDGETS, name="[VCF CF] Bare Section Probe",
                                           dash_id=_BARE_ID, fallback=None))
    (root / "content" / "views").mkdir(parents=True, exist_ok=True)
    return d


def _run_cmd_sync(monkeypatch, tmp_path, session, *, bare_section=False):
    _sync_tree(tmp_path, bare_section=bare_section)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dashboards = core_load_all(tmp_path / "content" / "views", tmp_path / "content" / "dashboards")[1]
    sent = []
    monkeypatch.setattr(dash_cli, "_load", lambda args: ([], dashboards))
    monkeypatch.setattr(dash_cli.VCFOpsClient, "from_env", classmethod(lambda cls, **kw: session))
    monkeypatch.setattr(dash_cli, "get_current_user", lambda c: {"id": "u1", "username": "admin"})
    monkeypatch.setattr(dash_cli, "discover_marker_filename", lambda c: "1L.v1")
    monkeypatch.setattr(dash_cli, "_run_dep_walker", lambda *a, **k: 0)
    monkeypatch.setattr(dash_cli, "_report_materialization", lambda *a, **k: 0)

    def _zip(views, ds, **kw):
        sent.append({d.name: d.section_count for d in ds})
        return b"zip"
    monkeypatch.setattr(dash_cli, "build_import_zip", _zip)
    monkeypatch.setattr(dash_cli, "import_content_zip", lambda c, b: _clean_envelope(len(dashboards)))
    args = types.SimpleNamespace(
        views_dir=str(tmp_path / "content" / "views"),
        dashboards_dir=str(tmp_path / "content" / "dashboards"),
        profile=None, supermetrics_dir=str(tmp_path / "supermetrics"),
        auto_enable_metrics=False, skip_metric_check=True)
    return dash_cli.cmd_sync(args), sent


NAME = "[VCF CF] Section Fallback Probe"


@pytest.mark.parametrize("release,status,sections_sent,note", [
    ("Aria Operations 8.18.7", 200, 0, "the target is VCF Operations 8.18.7"),
    ("VCF Operations 9.0.2.0", 200, 0, "the target is VCF Operations 9.0.2"),
    ("VCF Operations 9.1.0.0", 200, 0, "the target is VCF Operations 9.1.0"),
    ("VCF Operations 9.1.1.0", 200, 2, None),
    ("VCF Operations 9.2.0.0", 200, 2, None),
    ("", 500, 0, "the target version could not be read"),
])
def test_cmd_sync_decision_table(monkeypatch, tmp_path, capsys, release, status, sections_sent, note):
    rc, sent = _run_cmd_sync(monkeypatch, tmp_path, _VersionSession(release, status))
    err = capsys.readouterr().err
    assert rc == 0, err
    assert sent == [{NAME: sections_sent, "[VCF CF] Plain Probe": 0}]
    assert "REFUSED" not in err and "unverified" not in err
    assert VERSION_UNREADABLE_NOTE not in err      # nothing floored is left to check
    if note:
        assert f"WARNING: SECTIONS OMITTED: dashboard '{NAME}': 2 Section widget(s) left out" in err
        assert note in err
    else:
        assert "SECTIONS OMITTED" not in err


@pytest.mark.parametrize("release,refused,unverified", [
    ("VCF Operations 9.0.2.0", True, False),
    ("VCF Operations 9.1.0.0", False, True),
    ("VCF Operations 9.1.1.0", False, False),
])
def test_cmd_sync_without_the_key_is_unchanged(monkeypatch, tmp_path, capsys, release, refused, unverified):
    """A Section dashboard without the key keeps today's refuse/warn, and
    the refusal names only it, not the opted-in dashboard."""
    rc, sent = _run_cmd_sync(monkeypatch, tmp_path, _VersionSession(release), bare_section=True)
    err = capsys.readouterr().err
    if refused:
        assert rc == 1 and sent == []
        line = next(l for l in err.splitlines() if l.startswith("REFUSED:"))
        assert "'[VCF CF] Bare Section Probe'" in line and NAME not in line
    else:
        assert rc == 0 and sent and sent[0]["[VCF CF] Bare Section Probe"] == 2
    assert ("is unverified" in err) is unverified


def test_cmd_sync_unreadable_version_without_the_key_still_warns(monkeypatch, tmp_path, capsys):
    rc, sent = _run_cmd_sync(monkeypatch, tmp_path, _VersionSession(status=500), bare_section=True)
    err = capsys.readouterr().err
    assert rc == 0 and sent[0] == {NAME: 0, "[VCF CF] Plain Probe": 0, "[VCF CF] Bare Section Probe": 2}
    assert VERSION_UNREADABLE_NOTE in err and "SECTIONS OMITTED" in err


def test_plan_makes_no_request_without_a_floored_widget(tmp_path):
    session = _VersionSession()
    d = _load(_write(tmp_path / "plain.yaml", _dash_yaml(EXPECTED_WITHOUT, fallback=None)))
    assert dash_client.plan_dashboard_import(session, [d]) == ([d], None, [])
    assert session.calls == []


def test_dashboards_handler_imports_the_section_less_variant(monkeypatch, tmp_path, capsys):
    d = _sync_tree(tmp_path)
    sent = []
    monkeypatch.setattr(dash_handler, "get_current_user", lambda s: {"id": "u1", "username": "admin"})
    monkeypatch.setattr(dash_handler, "discover_marker_filename", lambda s: "1L.v1")
    monkeypatch.setattr(dash_handler, "build_import_zip",
                        lambda views, ds, **kw: sent.append([x.section_count for x in ds]) or b"zip")
    monkeypatch.setattr(dash_handler, "import_content_zip", lambda s, b: _clean_envelope(2))
    monkeypatch.setattr(dash_handler, "_materialization_by_id", lambda s, ds: {})
    paths = sorted(str(p) for p in d.glob("*.yaml"))
    result = dash_handler.DashboardsHandler().sync(paths, _VersionSession("VCF Operations 9.0.2.0"))
    assert sent == [[0, 0]]
    assert not [i for i in result.items if i.status == "failed"]
    assert "SECTIONS OMITTED" in capsys.readouterr().err


def test_bundle_preflight_does_not_refuse_an_opted_in_dashboard(monkeypatch, tmp_path, capsys):
    import vcfcf_core.packaging.loader as core_bundle
    from vcfcf_packaging import syncer
    _sync_tree(tmp_path)
    manifest = _write(tmp_path / "bundles" / "probe.yaml",
                      "name: probe\ndashboards:\n  - content/dashboards/d.yaml\n"
                      "  - content/dashboards/plain.yaml\n")
    monkeypatch.setattr(syncer, "load_bundle",
                        lambda p: core_bundle.load_bundle(Path(p), repo_root=tmp_path))
    ran = []

    class _Handler:
        content_type = "dashboards"
        sync_order = 4

        def sync(self, yaml_paths, session):
            ran.append(yaml_paths)
            return types.SimpleNamespace(items=[])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rc = syncer.sync_bundle(str(manifest), handlers=[_Handler()],
                                session=_VersionSession("VCF Operations 9.0.2.0"))
    cap = capsys.readouterr()
    assert ran and "FATAL" not in cap.err
    # The preflight only checks; the handler that imports says the omission.
    assert "SECTIONS OMITTED" not in cap.out + cap.err
    assert rc == 0


def test_bundle_sync_says_each_omission_once(monkeypatch, tmp_path, capsys):
    """Preflight plus the real dashboards handler: one SECTIONS OMITTED line
    (review NIT 3)."""
    import vcfcf_core.packaging.loader as core_bundle
    from vcfcf_packaging import syncer
    _sync_tree(tmp_path)
    manifest = _write(tmp_path / "bundles" / "probe.yaml",
                      "name: probe\ndashboards:\n  - content/dashboards/d.yaml\n"
                      "  - content/dashboards/plain.yaml\n")
    monkeypatch.setattr(syncer, "load_bundle",
                        lambda p: core_bundle.load_bundle(Path(p), repo_root=tmp_path))
    sent = []
    monkeypatch.setattr(dash_handler, "get_current_user", lambda s: {"id": "u1", "username": "admin"})
    monkeypatch.setattr(dash_handler, "discover_marker_filename", lambda s: "1L.v1")
    monkeypatch.setattr(dash_handler, "build_import_zip",
                        lambda views, ds, **kw: sent.append(sorted(x.section_count for x in ds)) or b"zip")
    monkeypatch.setattr(dash_handler, "import_content_zip", lambda s, b: _clean_envelope(2))
    monkeypatch.setattr(dash_handler, "_materialization_by_id", lambda s, ds: {})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        syncer.sync_bundle(str(manifest), handlers=[dash_handler.DashboardsHandler()],
                           session=_VersionSession("VCF Operations 9.0.2.0"))
    cap = capsys.readouterr()
    assert sent == [[0, 0]]
    assert (cap.out + cap.err).count("SECTIONS OMITTED") == 1


# --- 7. local package ----------------------------------------------------------

def _zip_dashboards(blob: bytes) -> list:
    outer = zipfile.ZipFile(io.BytesIO(blob))
    for n in outer.namelist():
        if n.startswith("dashboards/") and n != "dashboards/":
            inner = zipfile.ZipFile(io.BytesIO(outer.read(n)))
            return json.loads(inner.read("dashboard/dashboard.json"))["dashboards"]
    raise AssertionError("no dashboards entry")


def test_package_writes_either_variant(tmp_path, monkeypatch, capsys):
    d = _sync_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    base = ["--views-dir", str(tmp_path / "content" / "views"), "--dashboards-dir", str(d), "package"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert dash_cli.main(base + ["-o", "auto.zip"]) == 0
        assert dash_cli.main(base + ["-o", "omit.zip", "--sections", "omit"]) == 0
    err = capsys.readouterr().err
    assert err.count("SECTIONS OMITTED") == 1 and "--sections omit was given" in err
    by_name = lambda blob: {x["name"].split("/", 1)[-1]: [w["type"] for w in x["widgets"]]
                            for x in _zip_dashboards(blob)}
    auto = by_name((tmp_path / "auto.zip").read_bytes())
    omit = by_name((tmp_path / "omit.zip").read_bytes())
    assert auto[NAME].count("Section") == 2 and "Section" not in omit[NAME]
    assert auto["[VCF CF] Plain Probe"] == omit["[VCF CF] Plain Probe"]


# --- 8. importer -----------------------------------------------------------------

def test_importer_never_emits_the_key():
    """import-local writes YAML from wire keys only; section_fallback has no
    wire counterpart, so no emitter may produce it."""
    src = "".join(p.read_text(encoding="utf-8")
                  for p in (REPO_ROOT / "src" / "vcfcf_core" / "importer").glob("*.py"))
    assert 'y["section_fallback"]' not in src and "'section_fallback'" not in src
