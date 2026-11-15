"""Report-template feature floors: CoverPage ``font_color`` (2026-11-15).

8.18.7 refuses ``<FontColor>`` in a CoverPage ``<ContentFormatting>``
(``cvc-complex-type.2.4.d``, the template is dropped, the pak install
reports success); 9.0.2 and 9.1.1 import it. One table
(``vcfcf_core.reports.loader.REPORT_FEATURE_MEASURED``), four doors: the
load warning, ``import-local --target-min``, the Tier 2 pak floor gate with
the ``feature_fallback: {font_color: omit}`` opt-in, and live sync by the
instance version. Synthetic fixtures only.
Wire format and evidence:
knowledge/context/wire-formats/template_fidelity_wire_format.md §Feature version floors.
"""
from __future__ import annotations

import io
import json
import sys
import textwrap
import types
import warnings
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
import yaml

from vcfcf_core.reports import loader as rl
from vcfcf_core.reports.loader import (
    ReportValidationError,
    apply_feature_fallback,
    feature_import_check,
    load_file,
)
from vcfcf_core.reports.render import render_report_xml

REPO_ROOT = Path(__file__).resolve().parents[1]
R_ID = "6a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
R_PLAIN = "6a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4e"
R_ONLY = "6a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4f"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _report_yaml(*, name="Probe Cover Report", rid=R_ID, font_color="1A2B3C", colorize=False,
                 fallback="omit") -> str:
    cover = {"type": "CoverPage"}
    if colorize is not None:
        cover["colorize"] = colorize
    if font_color is not None:
        cover["font_color"] = font_color
    data = {"id": rid, "name": name, "description": "probe", "subject_types": [],
            "sections": [cover, {"type": "TableOfContents"}],
            "settings": {"show_page_footer": True, "output_formats": ["pdf"]}}
    if fallback is not None:
        data["feature_fallback"] = {"font_color": fallback}
    return yaml.safe_dump(data, sort_keys=False)


def _load(path: Path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_file(path, path.parent / "views", path.parent / "dashboards",
                         enforce_framework_prefix=False)


def _cover_formatting(xml: str):
    root = ET.fromstring(xml)
    sec = root.find("Reports/ReportDef/Sections/Section")
    fmt = sec.find("ContentFormatting")
    return None if fmt is None else [(c.tag, c.text) for c in fmt]


# --- 1. the table --------------------------------------------------------------

def test_floor_is_the_lowest_measured_import_and_8_18_7_refuses():
    assert rl.REPORT_FEATURE_MEASURED["font_color"] == {
        "imported": ((9, 0, 2), (9, 1, 1)), "refused": ((8, 18, 7),)}
    assert rl.REPORT_FEATURE_MIN_OPS_VERSION == {"font_color": (9, 0, 2)}
    assert set(rl.REPORT_FEATURE_WIRE_PATH) == set(rl.REPORT_FEATURE_WIRE) == set(rl.REPORT_FEATURE_MEASURED)
    assert rl.REPORT_FEATURE_WIRE_PATH["font_color"] == "ContentFormatting/FontColor"
    assert rl.feature_refused_on("font_color", "8.18.7")
    assert rl.feature_refused_on("font_color", "8.18.6")
    assert not rl.feature_refused_on("font_color", "9.0.1")  # unmeasured, not refused
    assert not rl.feature_refused_on("font_color", "9.0.2")


# --- 2. the key ----------------------------------------------------------------

@pytest.mark.parametrize("raw,needle", [
    ("feature_fallback: [font_color]\n", "must be a mapping"),
    ("feature_fallback: {font_color: drop}\n", "must be one of omit"),
    ("feature_fallback: {colorize: omit}\n", "is not a floored report feature"),
])
def test_bad_key_is_a_load_error(tmp_path, raw, needle):
    p = _write(tmp_path / "r.yaml", _report_yaml(fallback=None) + raw)
    with pytest.raises(ReportValidationError, match=needle):
        _load(p)


def test_load_warning_names_report_element_floor_and_the_way_out(tmp_path):
    for fallback, tail in ((None, "set feature_fallback: {font_color: omit}"),
                           ("omit", "content bundles declare no target, so they ship it")):
        p = _write(tmp_path / f"{fallback}.yaml", _report_yaml(fallback=fallback))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            load_file(p, tmp_path / "v", tmp_path / "d", enforce_framework_prefix=False)
        (w,) = [str(x.message) for x in caught]
        assert "report 'Probe Cover Report': sections[0] (CoverPage): font_color" in w
        assert "<FontColor>" in w and "9.0.2" in w and "refused on 8.18.7" in w
        assert tail in w


def test_no_warning_without_the_element(tmp_path):
    p = _write(tmp_path / "r.yaml", _report_yaml(font_color=None, fallback=None))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_file(p, tmp_path / "v", tmp_path / "d", enforce_framework_prefix=False)
    assert not caught


# --- 3. the decision table -------------------------------------------------------

@pytest.mark.parametrize("target,unknown,omitted", [
    ("8.18.7", "ship", True),
    ("9.0.1", "ship", True),     # below the proven floor, unmeasured: omit when opted in
    ("9.0", "ship", True),       # the 9.0 platform line reads as 9.0.0: below 9.0.2
    ("9.0.2", "ship", False),
    ("9.1.1", "ship", False),
    (None, "ship", False),       # no target declared: a content bundle ships it
    (None, "omit", True),        # live sync with the version unreadable
])
def test_variant_by_target(tmp_path, target, unknown, omitted):
    rd = _load(_write(tmp_path / "r.yaml", _report_yaml()))
    out, notes = apply_feature_fallback([rd], target, unknown)
    fmt = _cover_formatting(render_report_xml(out))
    if omitted:
        assert fmt == [("ColorizeListView", "false")]   # colorize kept, FontColor gone
        (note,) = notes
        assert note.startswith("FEATURE OMITTED: report 'Probe Cover Report': font_color")
        assert "(feature_fallback: font_color: omit)" in note
    else:
        assert fmt == [("ColorizeListView", "false"), ("FontColor", "1A2B3C")]
        assert notes == [] and out[0] is rd
    assert rd.sections[0].font_color == "1A2B3C"  # the source object is never changed


def test_font_color_only_cover_page_loses_its_formatting_element(tmp_path):
    rd = _load(_write(tmp_path / "r.yaml", _report_yaml(colorize=None)))
    out, _ = apply_feature_fallback([rd], "8.18.7")
    assert _cover_formatting(render_report_xml(out)) is None
    assert _cover_formatting(render_report_xml([rd])) == [("FontColor", "1A2B3C")]


def test_without_the_key_nothing_is_removed(tmp_path):
    rd = _load(_write(tmp_path / "r.yaml", _report_yaml(fallback=None)))
    for target in ("8.18.7", None):
        out, notes = apply_feature_fallback([rd], target, "omit")
        assert out[0] is rd and notes == []


def test_the_key_on_a_report_without_the_element_is_a_load_error(tmp_path):
    """As section_fallback on a dashboard without a Section: the key says
    what to do with an element no section sets, so remove it."""
    p = _write(tmp_path / "a.yaml", _report_yaml(font_color=None))
    with pytest.raises(ReportValidationError,
                       match="feature_fallback: font_color: omit says what to do with this report's "
                             "font_color, and no section sets it; remove the key"):
        _load(p)


def test_a_report_without_the_element_renders_byte_identical_at_every_target(tmp_path):
    no_key = _load(_write(tmp_path / "b.yaml", _report_yaml(font_color=None, fallback=None)))
    before = render_report_xml([no_key])
    for target in ("8.18.7", "9.0.2", None):
        out, notes = apply_feature_fallback([no_key], target, "omit")
        assert out[0] is no_key and notes == [] and render_report_xml(out) == before


def test_shipped_variant_renders_like_no_key(tmp_path):
    with_key = _load(_write(tmp_path / "a.yaml", _report_yaml()))
    no_key = _load(_write(tmp_path / "b.yaml", _report_yaml(fallback=None)))
    out, _ = apply_feature_fallback([with_key], "9.1.1")
    assert render_report_xml(out) == render_report_xml([no_key])


def _repo_report_dirs():
    yield REPO_ROOT / "content" / "reports", REPO_ROOT / "content" / "views", REPO_ROOT / "content" / "dashboards"
    for p in sorted((REPO_ROOT / "third_party").glob("*")):
        if (p / "reports").is_dir():
            yield p / "reports", p / "views", p / "dashboards"
    for p in sorted((REPO_ROOT / "content" / "sdk-adapters").glob("*")):
        if (p / "reports").is_dir():
            yield p / "reports", p / "views", p / "dashboards"


def test_every_repo_report_without_the_key_renders_unchanged_at_every_target():
    """A report that does not set feature_fallback is never altered, at any
    target: its render is the same bytes as before the floors existed."""
    seen = 0
    for rdir, vdir, ddir in _repo_report_dirs():
        for y in sorted(rdir.rglob("*.y*ml")):
            raw = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
            if not raw.get("id") or "feature_fallback" in raw:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                rd = load_file(y, vdir, ddir, enforce_framework_prefix=False)
            before = render_report_xml([rd])
            for target in ("8.18.7", "9.0.2", "9.1.1", None):
                out, notes = apply_feature_fallback([rd], target, "omit")
                assert out[0] is rd and notes == [], y
                assert render_report_xml(out) == before
            seen += 1
    assert seen >= 1


# --- 4. live import check ---------------------------------------------------------

def test_import_check(tmp_path):
    rd = _load(_write(tmp_path / "r.yaml", _report_yaml(fallback=None)))
    refusal, warning = feature_import_check([rd], "8.18.7")
    assert warning is None and "VCF Operations 8.18.7, which refuses report 'Probe Cover Report'" in refusal
    assert "Nothing was imported" in refusal and "feature_fallback: {font_color: omit}" in refusal
    # a build-suffixed version is compared on its first three components
    refusal, warning = feature_import_check([rd], (8, 18, 7, 24000))
    assert warning is None and "VCF Operations 8.18.7.24000, which refuses" in refusal
    assert rl.feature_refused_on("font_color", "8.18.7.24000")
    refusal, warning = feature_import_check([rd], "9.0.1")
    assert refusal is None and "unmeasured" in warning
    assert feature_import_check([rd], "9.0.2") == (None, None)
    refusal, warning = feature_import_check([rd], None)
    assert refusal is None and "could not read the instance version" in warning
    plain = _load(_write(tmp_path / "p.yaml", _report_yaml(rid=R_PLAIN, font_color=None, fallback=None)))
    assert feature_import_check([plain], "8.18.7") == (None, None)


# --- 5. import-local --target-min -------------------------------------------------

_SOURCE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Content><Reports>
<ReportDef id="{rid}"><isTenant>false</isTenant><Title>Probe Cover Report</Title><Description>probe</Description><Sections><Section><ContentType>CoverPage</ContentType><ContentKey>COVER_PAGE</ContentKey><ContentFormatting><ColorizeListView>false</ColorizeListView><FontColor>1A2B3C</FontColor></ContentFormatting></Section><Section><ContentType>TableOfContents</ContentType><ContentKey>TABLE_OF_CONTENTS</ContentKey></Section></Sections><Settings><ShowPageFooter>true</ShowPageFooter><OutputFormat>pdf</OutputFormat></Settings></ReportDef>
<ReportDef id="{only}"><isTenant>false</isTenant><Title>Probe Color Only</Title><Description>probe</Description><Sections><Section><ContentType>CoverPage</ContentType><ContentKey>COVER_PAGE</ContentKey><ContentFormatting><FontColor>000000</FontColor></ContentFormatting></Section></Sections><Settings><ShowPageFooter>true</ShowPageFooter><OutputFormat>pdf</OutputFormat></Settings></ReportDef>
<ReportDef id="{plain}"><isTenant>false</isTenant><Title>Probe Plain Report</Title><Description>probe</Description><Sections><Section><ContentType>CoverPage</ContentType><ContentKey>COVER_PAGE</ContentKey></Section></Sections><Settings><ShowPageFooter>true</ShowPageFooter><OutputFormat>pdf</OutputFormat></Settings></ReportDef>
</Reports></Content>
"""


@pytest.fixture(scope="module")
def xml_source(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("feature_src")
    _write(root / "reports" / "content.xml", _SOURCE_XML.format(rid=R_ID, only=R_ONLY, plain=R_PLAIN))
    return root


def _cli(argv, capsys):
    from vcfcf_extractor.cli import main
    old = sys.argv
    sys.argv = ["vcfcf_extractor"] + [str(a) for a in argv]
    try:
        with pytest.raises(SystemExit) as exc:
            main()
    finally:
        sys.argv = old
    cap = capsys.readouterr()
    return exc.value.code, cap.out + cap.err


def _import(src, out, capsys, *extra, layout="third-party"):
    args = ["import-local", src, "--out", out, "--layout", layout, "--ids", "mint",
            "--mint-namespace", "probe-ns", "--naming", "unprefixed", *extra]
    if layout == "third-party":
        args += ["--project-name", "probe"]
    return _cli(args, capsys)


def _y(out: Path, rel: str) -> dict:
    return yaml.safe_load((out / rel).read_text())


def _statuses(out: Path) -> dict:
    rep = json.loads((out / "import-report" / "report.json").read_text())
    return {d["name"]: d["status"] for d in rep["verify"]["objects_detail"]}


@pytest.mark.parametrize("target", ["8.18.7", "9.0.2", "9.1.1", None])
def test_import_local_by_target(xml_source, tmp_path, capsys, target):
    out = tmp_path / "out"
    rc, text = _import(xml_source, out, capsys, *(("--target-min", target) if target else ()))
    assert rc == 0, text
    cover = _y(out, "reports/probe-cover-report.yaml")["sections"][0]
    only = _y(out, "reports/probe-color-only.yaml")["sections"][0]
    plain = _y(out, "reports/probe-plain-report.yaml")
    assert plain["sections"] == [{"type": "CoverPage"}]
    st = _statuses(out)
    assert st["Probe Plain Report"] == "identical"
    for y in (_y(out, "reports/probe-cover-report.yaml"), _y(out, "reports/probe-color-only.yaml")):
        assert "feature_fallback" not in y  # never added by the importer
    if target == "8.18.7":
        assert cover == {"type": "CoverPage", "colorize": False}
        assert only == {"type": "CoverPage"}
        for name, rel in (("Probe Cover Report", "probe-cover-report"), ("Probe Color Only", "probe-color-only")):
            assert st[name] == "identical apart from forced target keys"
            assert f"TARGET 8.18.7: reports/{rel}.yaml: report {name!r} section 0 (CoverPage): font_color not emitted" in text
        assert "set aside only at ReportDef/Sections/Section[0]/ContentFormatting/FontColor" in text
        assert 'restore font_color: "1A2B3C" on that section' in text
        assert "report: ReportDef/Sections/Section[]/ContentFormatting/FontColor#text [missing]" in text
    else:
        assert cover == {"type": "CoverPage", "colorize": False, "font_color": "1A2B3C"}
        assert only == {"type": "CoverPage", "font_color": "000000"}
        assert st["Probe Cover Report"] == st["Probe Color Only"] == "identical"
        assert "font_color not emitted" not in text
        if target is None:
            assert ("VERSION: reports/probe-cover-report.yaml: report 'Probe Cover Report' section 0 "
                    "(CoverPage): font_color reproduces") in text
            assert "pass --target-min 8.18.7 to leave it out" in text
        else:
            assert "font_color reproduces" not in text


def test_import_local_minted_ids_do_not_depend_on_the_target(xml_source, tmp_path, capsys):
    maps = []
    for target in ("8.18.7", "9.1.1"):
        out = tmp_path / target
        rc, text = _import(xml_source, out, capsys, "--target-min", target)
        assert rc == 0, text
        maps.append((out / "import-report" / "id_map.tsv").read_text())
    assert maps[0] == maps[1]


def test_import_local_pak_layout(xml_source, tmp_path, capsys):
    """At 8.18.7 the pak tree passes the pak floor check; at 9.0.2 the
    element is carried and the pak check (oldest line 8.18.7) refuses it,
    naming the report, the element and the opt-in."""
    out = tmp_path / "low"
    rc, text = _import(xml_source, out, capsys, "--target-min", "8.18.7", layout="pak")
    assert rc == 0, text
    assert "PAK CHECK" not in text
    out = tmp_path / "high"
    rc, text = _import(xml_source, out, capsys, "--target-min", "9.0.2", "--allow-partial", layout="pak")
    assert rc == 1 and not out.exists()
    line = next(l for l in text.splitlines() if "PAK CHECK" in l and "Probe Cover Report" in l)
    assert "font_color renders <FontColor>" in line and "9.0.2" in line
    assert "set feature_fallback: {font_color: omit} on the report" in line
    assert ("PAK CHECK, what to do: this tree is not written, so the key cannot be set on it here. "
            "Convert at --target-min 8.18.7") in text
    assert "a PAK CHECK failure is never accepted by --allow-partial" in text
    assert "or pass --allow-partial to accept what it accepts" not in text


# --- 6. Tier 2 pak build ----------------------------------------------------------

def _sdk_project(base: Path, *, fallback="omit") -> Path:
    project = base / "probe_adapter"
    _write(project / "adapter.yaml", textwrap.dedent("""\
        name: "Probe Adapter"
        version: "1.0.0"
        build_number: 1
        adapter_kind: "probe_kind"
        tier: 2
        content_naming: unprefixed
        bundled_content:
          reports:
            - reports/probe.yaml
            - reports/plain.yaml
        """))
    _write(project / "describe.xml",
           '<?xml version="1.0" encoding="UTF-8"?>\n<AdapterKind key="probe_kind" nameKey="1" version="1">'
           '<ResourceKinds><ResourceKind key="probe_world" nameKey="2" type="1"/></ResourceKinds></AdapterKind>\n')
    _write(project / "reports" / "probe.yaml", _report_yaml(fallback=fallback))
    _write(project / "reports" / "plain.yaml",
           _report_yaml(name="Probe Plain Report", rid=R_PLAIN, font_color=None, colorize=None,
                        fallback=None))
    return project


class _ReachedCompile(Exception):
    pass


@pytest.fixture
def sb(monkeypatch):
    """build_sdk_pak up to the JDK step; the reports it would ship are
    captured from the last content check before the compile."""
    from vcfcf_managementpacks import sdk_builder
    shipped = {}
    real = sdk_builder.check_stock_ids

    def _capture(project, bundled):
        shipped["reports"] = list(bundled[5])
        return real(project, bundled)

    def _stop(*_a, **_k):
        raise _ReachedCompile()

    monkeypatch.setattr(sdk_builder, "check_stock_ids", _capture)
    monkeypatch.setattr(sdk_builder, "_detect_jdk", _stop)
    monkeypatch.delenv("VCFCF_RELEASE_BUILD", raising=False)
    sdk_builder._shipped = shipped
    yield sdk_builder
    del sdk_builder._shipped


def _pak_report_xml(sb, project, reports, out: Path) -> dict:
    """The report content.xml files of a pak written from ``reports``."""
    from vcfcf_managementpacks.sdk_project import load_sdk_project
    proj = load_sdk_project(project / "adapter.yaml")
    pak = sb._write_outer_pak(proj, b"", out, project, reports=reports, owning_adapter_kind="probe_kind")
    found = {}
    with zipfile.ZipFile(pak) as z:
        for n in z.namelist():
            if n.startswith("content/reports/") and n.endswith("/content.xml"):
                root = ET.fromstring(z.read(n))
                for rd in root.iter("ReportDef"):
                    found[rd.findtext("Title")] = z.read(n).decode("utf-8")
    return found


def _high_floor(sb, monkeypatch):
    monkeypatch.setattr(sb, "_SDK_COMPAT_LINES",
                        tuple(l for l in sb._SDK_COMPAT_LINES if l.key == "9.1.1.0100"))


def test_pak_low_floor_with_the_key_ships_without_font_color(sb, tmp_path, capsys):
    assert sb._oldest_supported_line() == "8.18.7"
    project = _sdk_project(tmp_path)
    with pytest.raises(_ReachedCompile):
        sb.build_sdk_pak(project, tmp_path / "out")
    err = capsys.readouterr().err
    assert ("build-sdk: FEATURE OMITTED: report 'Probe Cover Report': font_color (<FontColor> in the "
            "CoverPage <ContentFormatting>, 1 section(s)) left out (feature_fallback: font_color: omit): "
            "the target is VCF Operations 8.18.7, below 9.0.2") in err
    probe, plain = sb._shipped["reports"]
    assert probe.sections[0].font_color is None and probe.sections[0].cover_colorize is False
    xml = _pak_report_xml(sb, project, [probe, plain], tmp_path / "pak")
    assert "FontColor" not in xml["Probe Cover Report"]
    assert "<ContentFormatting><ColorizeListView>false</ColorizeListView></ContentFormatting>" in xml["Probe Cover Report"]
    assert "ContentFormatting" not in xml["Probe Plain Report"]


def test_pak_high_floor_with_the_key_ships_font_color(sb, tmp_path, capsys, monkeypatch):
    """When 8.18 and 9.0 leave RULE-019 the same source ships the element."""
    _high_floor(sb, monkeypatch)
    project = _sdk_project(tmp_path)
    with pytest.raises(_ReachedCompile):
        sb.build_sdk_pak(project, tmp_path / "out")
    assert "FEATURE OMITTED" not in capsys.readouterr().err
    probe, plain = sb._shipped["reports"]
    assert probe.sections[0].font_color == "1A2B3C"
    xml = _pak_report_xml(sb, project, [probe, plain], tmp_path / "pak")
    assert "<FontColor>1A2B3C</FontColor>" in xml["Probe Cover Report"]


def test_pak_low_floor_without_the_key_fails_naming_report_element_and_floor(sb, tmp_path):
    project = _sdk_project(tmp_path, fallback=None)
    with pytest.raises(sb.SdkBuildError) as exc:
        sb.build_sdk_pak(project, tmp_path / "out")
    msg = str(exc.value)
    assert "bundled_content.reports:" in msg and "report 'Probe Cover Report': sections[0] (CoverPage)" in msg
    assert "font_color renders <FontColor> in the CoverPage <ContentFormatting>" in msg
    assert "whose floor is 9.0.2" in msg and "the target VCF Operations 8.18.7 is below it" in msg
    assert "set feature_fallback: {font_color: omit} on the report" in msg
    assert "Probe Plain Report" not in msg
    assert "reports" not in sb._shipped


def test_pak_high_floor_without_the_key_builds(sb, tmp_path, monkeypatch):
    _high_floor(sb, monkeypatch)
    project = _sdk_project(tmp_path, fallback=None)
    with pytest.raises(_ReachedCompile):
        sb.build_sdk_pak(project, tmp_path / "out")
    assert sb._shipped["reports"][0].sections[0].font_color == "1A2B3C"


def test_validate_sdk_follows_the_floor(tmp_path, capsys):
    from vcfcf_managementpacks.sdk_builder import validate_sdk_project
    errors = validate_sdk_project(_sdk_project(tmp_path / "a"))
    assert not [e for e in errors if e.startswith("version floor")]
    assert "validate-sdk: FEATURE OMITTED: report 'Probe Cover Report'" in capsys.readouterr().err
    errors = validate_sdk_project(_sdk_project(tmp_path / "b", fallback=None))
    assert [e for e in errors
            if e.startswith("version floor") and "feature_fallback: {font_color: omit}" in e]


def test_kit_report_loader_needs_no_new_rewrite():
    """The pak gate calls ReportDef methods only, and the kit's
    reports_loader.py is a copy of the core loader: the floors travel with
    it and sdk_builder gains no import the kit would have to rewrite."""
    from vcfcf_managementpacks.buildkit import _IMPORT_REWRITES, _apply_rewrites
    src = (REPO_ROOT / "src" / "vcfcf_managementpacks" / "sdk_builder.py").read_text(encoding="utf-8")
    out = _apply_rewrites(src, _IMPORT_REWRITES["sdk_builder.py"])
    assert "apply_feature_fallback" not in out and "feature_fallback_variant(" in out
    loader = (REPO_ROOT / "src" / "vcfcf_core" / "reports" / "loader.py").read_text(encoding="utf-8")
    kit_loader = _apply_rewrites(loader, _IMPORT_REWRITES["reports_loader.py"])
    assert "from vcfcf_core" not in kit_loader and "REPORT_FEATURE_MEASURED" in kit_loader


# --- 7. live sync by instance version ----------------------------------------------

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
            "operationSummaries": [{"contentType": "REPORT_DEFINITIONS", "total": n, "imported": n,
                                    "skipped": 0, "failed": 0, "state": "FINISHED",
                                    "errorMessages": []}]}


def _sync_reports(tmp_path, *, fallback="omit"):
    probe = _load(_write(tmp_path / "r" / "probe.yaml", _report_yaml(fallback=fallback)))
    plain = _load(_write(tmp_path / "r" / "plain.yaml",
                         _report_yaml(name="Probe Plain Report", rid=R_PLAIN, font_color=None, fallback=None)))
    return [probe, plain]


def _run_cmd_sync(monkeypatch, tmp_path, session, *, fallback="omit"):
    from vcfcf_reports import cli as rep_cli
    reports = _sync_reports(tmp_path, fallback=fallback)
    sent = []
    monkeypatch.setattr(rep_cli, "_collect", lambda args: list(reports))
    monkeypatch.setattr(rep_cli.VCFOpsClient, "from_env", classmethod(lambda cls, **kw: session))
    monkeypatch.setattr(rep_cli, "get_current_user", lambda c: {"id": "u1", "username": "admin"})
    monkeypatch.setattr(rep_cli, "discover_marker_filename", lambda c: "1L.v1")

    def _zip(rs, **kw):
        sent.append({r.name: r.sections[0].font_color for r in rs})
        return b"zip"
    monkeypatch.setattr(rep_cli, "build_import_zip", _zip)
    monkeypatch.setattr(rep_cli, "import_reports_zip", lambda c, b: _clean_envelope(len(reports)))
    return rep_cli.cmd_sync(types.SimpleNamespace(paths=[], profile=None)), sent


@pytest.mark.parametrize("release,status,font_sent,note", [
    ("Aria Operations 8.18.7", 200, None, "the target is VCF Operations 8.18.7"),
    ("VCF Operations 9.0.1.0", 200, None, "the target is VCF Operations 9.0.1"),
    ("VCF Operations 9.0.2.0", 200, "1A2B3C", None),
    ("VCF Operations 9.1.1.0", 200, "1A2B3C", None),
    ("", 500, None, "the target version could not be read"),
])
def test_cmd_sync_decision_table(monkeypatch, tmp_path, capsys, release, status, font_sent, note):
    rc, sent = _run_cmd_sync(monkeypatch, tmp_path, _VersionSession(release, status))
    err = capsys.readouterr().err
    assert rc == 0, err
    assert sent == [{"Probe Cover Report": font_sent, "Probe Plain Report": None}]
    assert "FATAL" not in err
    if note:
        assert "FEATURE OMITTED: report 'Probe Cover Report': font_color" in err and note in err
    else:
        assert "FEATURE OMITTED" not in err


@pytest.mark.parametrize("release,refused,unmeasured", [
    ("Aria Operations 8.18.7", True, False),
    ("VCF Operations 9.0.1.0", False, True),
    ("VCF Operations 9.0.2.0", False, False),
])
def test_cmd_sync_without_the_key(monkeypatch, tmp_path, capsys, release, refused, unmeasured):
    rc, sent = _run_cmd_sync(monkeypatch, tmp_path, _VersionSession(release), fallback=None)
    err = capsys.readouterr().err
    if refused:
        assert rc == 1 and sent == []
        line = next(l for l in err.splitlines() if l.startswith("FATAL:"))
        assert "report 'Probe Cover Report'" in line and "Probe Plain Report" not in line
        assert "Nothing was imported" in line
    else:
        assert rc == 0 and sent[0]["Probe Cover Report"] == "1A2B3C"
    assert ("whether this build imports it is unmeasured" in err) is unmeasured


def test_plan_makes_no_request_without_a_floored_feature(tmp_path):
    from vcfcf_reports.client import plan_report_import
    session = _VersionSession()
    plain = _sync_reports(tmp_path)[1]
    assert plan_report_import(session, [plain]) == ([plain], None, [])
    assert session.calls == []


def test_reports_handler_imports_the_variant_and_refuses_before_sending(monkeypatch, tmp_path, capsys):
    from vcfcf_reports import handler as rep_handler
    sent = []
    monkeypatch.setattr(rep_handler, "get_current_user", lambda s: {"id": "u1", "username": "admin"})
    monkeypatch.setattr(rep_handler, "discover_marker_filename", lambda s: "1L.v1")
    monkeypatch.setattr(rep_handler, "build_import_zip",
                        lambda rs, **kw: sent.append([r.sections[0].font_color for r in rs]) or b"zip")
    monkeypatch.setattr(rep_handler, "import_reports_zip", lambda s, b: _clean_envelope(2))
    h = rep_handler.ReportsHandler()
    result = h.sync_loaded(_sync_reports(tmp_path / "a"), [], _VersionSession("Aria Operations 8.18.7"))
    assert sent == [[None, None]] and not [i for i in result.items if i.status == "failed"]
    assert "FEATURE OMITTED" in capsys.readouterr().err
    result = h.sync_loaded(_sync_reports(tmp_path / "b", fallback=None), [],
                           _VersionSession("Aria Operations 8.18.7"))
    assert sent == [[None, None]]  # nothing more sent
    assert [i.status for i in result.items] == ["failed", "failed"]
    assert "refuses report 'Probe Cover Report'" in result.items[0].message


def test_bundle_preflight_refuses_before_anything_is_imported(tmp_path, capsys):
    from vcfcf_packaging import syncer
    bundle = types.SimpleNamespace(reports=_sync_reports(tmp_path / "a", fallback=None))
    assert syncer._refuse_unimportable_reports(bundle, _VersionSession("Aria Operations 8.18.7")) is True
    assert "FATAL: this instance is VCF Operations 8.18.7, which refuses" in capsys.readouterr().err
    bundle = types.SimpleNamespace(reports=_sync_reports(tmp_path / "b"))
    assert syncer._refuse_unimportable_reports(bundle, _VersionSession("Aria Operations 8.18.7")) is False
    assert "FEATURE OMITTED" not in capsys.readouterr().err  # the handler says it, once
    assert syncer._refuse_unimportable_reports(types.SimpleNamespace(reports=[]), None) is False
