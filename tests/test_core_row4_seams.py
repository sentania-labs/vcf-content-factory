"""M2 row 4 seams: the extractor's pure half and reverse_local in vcfcf_core.

Design: ``knowledge/designs/tooling-core-carveout-v1.md`` row 4. Each test
pins one contract the library now exposes and the factory keeps on top:

- the repo root stays in the factory: core binds none, ``_scan_existing_ids``
  takes it as a required argument, joins the v3 ``content/`` trees (so the
  skip-with-WARN non-overwrite invariant is live again, review W1) and
  ``extract_dashboard`` passes its own;
- the export-zip readers (views ``content.xml``, dashboards with ``entries``
  merged, super metrics with ids injected) are library code and the live
  ``_export_*`` functions only run the export (review W3);
- ``_rewrite_formula`` needs only ``name_for_uuid``: a plain map works in
  the library, the live ``_SMNameCache`` still fits in the factory;
- the round-trip check in reverse_local loads the emitted YAML through the
  core loader with no minting callback: a source dashboard with no id gets
  an ERROR verdict and its YAML is left exactly as written (on main the
  factory loader minted a uuid into the file, leaving two ``id:`` lines);
- the migrator gate: from a scratch site-packages holding only the built
  wheel, with the environment cleared and an empty working directory, the
  offline read path turns a content-export zip into the same YAML the
  factory path produces for the same zip.
"""
from __future__ import annotations

import inspect
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
VIEWS_XML = FIXTURES / "license_consumption_views.xml"
DASH_JSON = FIXTURES / "dashboards" / "license_consumption_widgets.json"

_UUID = "6e8310ed-1753-45a4-aacc-7f1025c03d11"


# ---------------------------------------------------------------------------
# The repo root stays in the factory
# ---------------------------------------------------------------------------

class TestRepoRootStaysInTheFactory:
    def test_core_extractor_modules_bind_no_root(self):
        for name in ("extractor.py", "reverse_local.py"):
            text = (SRC / "vcfcf_core" / "extractor" / name).read_text(encoding="utf-8")
            assert "__file__" not in text, name
            assert "_REPO_ROOT" not in text, name
        import vcfcf_core.extractor.extractor as core_ex
        assert not hasattr(core_ex, "_scan_existing_ids")

    def test_scan_existing_ids_takes_an_explicit_root(self, tmp_path):
        from vcfcf_extractor.extractor import _REPO_ROOT, _scan_existing_ids

        assert _REPO_ROOT == REPO_ROOT
        with pytest.raises(TypeError):
            _scan_existing_ids("supermetric")  # type: ignore[call-arg]
        # v3 layout: the trees live under content/ (review W1: the pre-row-4
        # join off the root matched nothing).
        (tmp_path / "content" / "supermetrics").mkdir(parents=True)
        (tmp_path / "supermetrics").mkdir()
        target = tmp_path / "content" / "supermetrics" / "x.yaml"
        target.write_text(f"id: {_UUID}\nname: x\n", encoding="utf-8")
        (tmp_path / "supermetrics" / "stale.yaml").write_text("id: 11111111-1111-4111-8111-111111111111\n", encoding="utf-8")
        assert _scan_existing_ids("supermetric", tmp_path) == {_UUID: target}
        assert _scan_existing_ids("view", tmp_path) == {}
        assert _scan_existing_ids("supermetric", tmp_path / "absent") == {}

    def test_scan_existing_ids_finds_the_real_first_party_trees(self):
        """The skip-with-WARN non-overwrite invariant is live again: against
        the real checkout every kind resolves to files under content/."""
        from vcfcf_extractor.extractor import _REPO_ROOT, _scan_existing_ids

        for kind, subdir in (("supermetric", "supermetrics"), ("view", "views"), ("dashboard", "dashboards")):
            found = _scan_existing_ids(kind, _REPO_ROOT)
            assert found, f"{kind}: nothing found under {_REPO_ROOT / 'content' / subdir}"
            assert all(path.is_relative_to(_REPO_ROOT / "content" / subdir) for path in found.values())

    def test_extract_dashboard_passes_the_factory_root(self):
        text = (SRC / "vcfcf_extractor" / "extractor.py").read_text(encoding="utf-8")
        calls = re.findall(r"= _scan_existing_ids\((.*?)\)", text)
        assert len(calls) == 3, "extract_dashboard no longer scans existing ids at its three sites"
        assert all(c.endswith(", _REPO_ROOT") for c in calls), calls


# ---------------------------------------------------------------------------
# _rewrite_formula is duck-typed on name_for_uuid
# ---------------------------------------------------------------------------

class _PlainNameMap:
    def __init__(self, mapping: dict[str, str]):
        self._m = mapping

    def name_for_uuid(self, uuid: str):
        return self._m.get(uuid)


class TestRewriteFormulaIsDuckTyped:
    def test_plain_map_resolves_in_the_library(self):
        from vcfcf_core.extractor.extractor import _rewrite_formula

        out, refs = _rewrite_formula(f"sm_{_UUID} + 1", _PlainNameMap({_UUID: "Host CPU"}))
        assert out == '@supermetric:"Host CPU" + 1'
        assert refs == {_UUID}

    def test_unresolved_token_is_kept_and_warned(self, capsys):
        from vcfcf_core.extractor.extractor import _rewrite_formula

        out, refs = _rewrite_formula(f"sm_{_UUID}", _PlainNameMap({}))
        assert out == f"sm_{_UUID}" and refs == {_UUID}
        assert f"could not resolve SM UUID {_UUID}" in capsys.readouterr().err

    def test_factory_name_cache_still_fits(self):
        from vcfcf_extractor.extractor import _SMNameCache, _rewrite_formula
        import vcfcf_core.extractor.extractor as core_ex

        assert _rewrite_formula is core_ex._rewrite_formula

        class _Client:
            def get_supermetric(self, uuid):
                return {"name": "Live SM"}

            def list_supermetrics(self, page_size=2000):
                return []

        cache = _SMNameCache(_Client())
        out, _ = _rewrite_formula(f"sm_{_UUID}", cache)
        assert out == '@supermetric:"Live SM"'
        assert cache.uuid_for_name("Live SM") == _UUID


# ---------------------------------------------------------------------------
# reverse_local: the round-trip check never mints into the emitted YAML
# ---------------------------------------------------------------------------

def test_round_trip_check_never_mints_into_the_emitted_yaml(tmp_path, capsys):
    from vcfcf_extractor.reverse_local import reverse_local_port

    (tmp_path / "xml").mkdir()
    (tmp_path / "sm").mkdir()
    src = {"name": "NoId Dash", "widgets": [{
        "id": "w1", "type": "TextDisplay", "title": "t",
        "gridsterCoords": {"x": 0, "y": 0, "w": 2, "h": 2}, "config": {"html": "<b>x</b>"},
    }]}
    (tmp_path / "d.json").write_text(json.dumps(src), encoding="utf-8")
    rc = reverse_local_port(
        source_dashboard_json=tmp_path / "d.json", source_view_xml_dir=tmp_path / "xml",
        sm_yaml_dir=tmp_path / "sm", output_views_dir=tmp_path / "views",
        output_dashboards_dir=tmp_path / "dash", name_path_override="",
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "ERROR      'NoId Dash': load_dashboard failed" in out and "missing id" in out
    text = (tmp_path / "dash" / "NoId Dash.yaml").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "id: ''" and lines[1] == "name: NoId Dash"
    assert sum(1 for ln in lines if ln.startswith("id:")) == 1


# ---------------------------------------------------------------------------
# The migrator gate: offline read path from the wheel alone
# ---------------------------------------------------------------------------

_OWNER = "b58a71ee-e909-5b40-a355-9e199e6f0f53"


def _export_zip_bytes() -> bytes:
    """A content-export-shaped zip built from the two export-derived text
    fixtures, with every member a real dashboards+views export carries per
    ``.claude/skills/vcfops-api/references/wire-formats.md`` (Dashboards +
    views zip): the ``<digits>L.v1`` marker (owner uuid inside),
    ``configuration.json``, ``views.zip`` holding ``content.xml``,
    ``usermappings.json``, ``dashboards/<ownerUserId>`` (inner zip with
    ``dashboard/dashboard.json``) and ``dashboardsharings/<ownerUserId>``
    (``[]``); plus the SUPER_METRICS export's ``supermetrics.json`` keyed by
    UUID naming the six SMs the views reference. The readers must ignore
    the marker, the manifest, the user mapping and the sharing list."""
    views_inner = io.BytesIO()
    with zipfile.ZipFile(views_inner, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", VIEWS_XML.read_bytes())
    dash_doc = json.loads(DASH_JSON.read_text(encoding="utf-8"))
    dash_inner = io.BytesIO()
    with zipfile.ZipFile(dash_inner, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dashboard/dashboard.json", json.dumps(dash_doc))
        z.writestr("dashboard/resources/resources.properties", "")
    sm_uuids = sorted(set(re.findall(r"Super Metric\|sm_([0-9a-f-]{36})", VIEWS_XML.read_text(encoding="utf-8"))))
    sms = {u: {"name": f"[Fixture] SM {i}", "formula": "1", "resourceKinds": []} for i, u in enumerate(sm_uuids, 1)}
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("1757800000000000000L.v1", _OWNER)
        z.writestr("configuration.json", json.dumps({"dashboards": 1, "views": 2, "superMetrics": len(sms), "type": "CUSTOM"}))
        z.writestr("views.zip", views_inner.getvalue())
        z.writestr("usermappings.json", json.dumps({_OWNER: {"userName": "admin", "userId": _OWNER}}))
        z.writestr(f"dashboards/{_OWNER}", dash_inner.getvalue())
        z.writestr(f"dashboardsharings/{_OWNER}", "[]")
        z.writestr("supermetrics.json", json.dumps(sms))
    return outer.getvalue()


def unpack_export_zip(zip_path, dest):
    """Lay a content-export zip out as reverse_local's inputs, through the
    library's own readers (review W3): ``_content_xml_from_export_zip``,
    ``_dashboards_from_export_zip``, ``_supermetrics_from_export_zip`` and
    ``_write_sm_yaml`` from ``vcfcf_core.extractor.extractor``; the stdlib
    only writes the files. Returns (dashboard_json_path, view_xml_dir,
    sm_yaml_dir). Shared by the bare-venv subprocess and the factory run, so
    both read identical inputs and both exercise the wheel's readers.
    """
    import json as _json
    from pathlib import Path as _Path
    from vcfcf_core.extractor.extractor import (
        _content_xml_from_export_zip, _dashboards_from_export_zip, _supermetrics_from_export_zip, _write_sm_yaml,
    )

    dest = _Path(dest)
    xml_dir = dest / "xml"
    sm_dir = dest / "sm"
    xml_dir.mkdir(parents=True)
    sm_dir.mkdir()
    outer = _Path(zip_path).read_bytes()
    content_xml = _content_xml_from_export_zip(outer)
    assert content_xml is not None, "no content.xml in the export"
    (xml_dir / "content.xml").write_bytes(content_xml)
    dashboards = _dashboards_from_export_zip(outer)
    assert len(dashboards) == 1, [d.get("name") for d in dashboards]
    dash_path = dest / "dashboard.json"
    dash_path.write_text(_json.dumps({"dashboards": dashboards}), encoding="utf-8")
    for uid, sm in _supermetrics_from_export_zip(outer).items():
        assert sm["id"] == uid
        _write_sm_yaml(sm_dir / f"{uid}.yaml", sm, sm["formula"], policy_resource_kinds=[])
    return dash_path, xml_dir, sm_dir


class TestExportZipReaders:
    """Review W3: the export-zip readers are library code, the live export
    functions only run the export and hand the bytes over."""

    def test_dashboards_reader_merges_entries_and_skips_the_other_members(self):
        from vcfcf_core.extractor.extractor import _dashboards_from_export_zip

        dashboards = _dashboards_from_export_zip(_export_zip_bytes())
        src = json.loads(DASH_JSON.read_text(encoding="utf-8"))
        assert [d["name"] for d in dashboards] == [d["name"] for d in src["dashboards"]]
        assert dashboards[0]["entries"] == src["entries"]
        assert len(dashboards[0]["widgets"]) == 3

    def test_supermetrics_reader_injects_ids_and_skips_configuration(self):
        from vcfcf_core.extractor.extractor import _supermetrics_from_export_zip

        sms = _supermetrics_from_export_zip(_export_zip_bytes())
        assert len(sms) == 6
        assert all(sm["id"] == uid and sm["name"].startswith("[Fixture] SM ") for uid, sm in sms.items())
        assert "superMetrics" not in {k for sm in sms.values() for k in sm}

    def test_content_xml_reader_finds_the_nested_views_zip(self):
        from vcfcf_core.extractor.extractor import _content_xml_from_export_zip

        assert _content_xml_from_export_zip(_export_zip_bytes()) == VIEWS_XML.read_bytes()
        assert _content_xml_from_export_zip(b"not a zip") is None

    def test_readers_raise_value_error_on_unreadable_bytes(self):
        from vcfcf_core.extractor.extractor import _dashboards_from_export_zip, _supermetrics_from_export_zip

        with pytest.raises(ValueError, match="failed to parse dashboard export zip"):
            _dashboards_from_export_zip(b"not a zip")
        with pytest.raises(ValueError, match="failed to parse super metrics export zip"):
            _supermetrics_from_export_zip(b"not a zip")

    def test_live_export_functions_call_the_core_readers(self):
        import vcfcf_extractor.extractor as fac
        import vcfcf_core.extractor.extractor as core

        assert fac._dashboards_from_export_zip is core._dashboards_from_export_zip
        assert fac._supermetrics_from_export_zip is core._supermetrics_from_export_zip
        src = inspect.getsource(fac._export_dashboard_json)
        assert "_dashboards_from_export_zip(outer_zip)" in src and "zipfile" not in src
        src = inspect.getsource(fac._export_supermetrics_full)
        assert "_supermetrics_from_export_zip(outer_zip)" in src and "zipfile" not in src

        class _Client:
            pass

        calls = []

        def fake_export(client, types):
            calls.append(types)
            return _export_zip_bytes()

        import pytest as _pytest
        mp = _pytest.MonkeyPatch()
        try:
            mp.setattr(fac, "_run_content_export", fake_export)
            got = fac._export_dashboard_json(_Client(), "b1c1c0a5-2bc8-4d5a-9b6c-000000000000")
            assert got is None
            want = json.loads(DASH_JSON.read_text(encoding="utf-8"))["dashboards"][0]["id"]
            assert fac._export_dashboard_json(_Client(), want.upper())["id"] == want
            assert len(fac._export_supermetrics_full(_Client())) == 6
        finally:
            mp.undo()
        assert calls == [["DASHBOARDS"], ["DASHBOARDS"], ["SUPER_METRICS"]]


def _run_factory_reverse(zip_path: Path, work: Path) -> tuple[dict[str, bytes], str]:
    from vcfcf_extractor.reverse_local import reverse_local_port

    dash_path, xml_dir, sm_dir = unpack_export_zip(zip_path, work / "in")
    rc = reverse_local_port(
        source_dashboard_json=dash_path, source_view_xml_dir=xml_dir, sm_yaml_dir=sm_dir,
        output_views_dir=work / "out" / "views", output_dashboards_dir=work / "out" / "dashboards",
        name_path_override="", run_diff=True,
    )
    assert rc == 0
    return _tree(work / "out"), ""


def _tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture(scope="session")
def core_wheel_site(tmp_path_factory) -> Path:
    """Build the vcf-cf-tooling-core wheel from this tree and install it,
    with no dependencies, into a scratch site directory that holds nothing
    else. PyYAML comes from the interpreter's own site-packages, as it does
    for the contract test; no factory package is reachable."""
    base = tmp_path_factory.mktemp("core-wheel")
    wheel_dir = base / "wheel"
    site = base / "site"
    build = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(REPO_ROOT), "--no-deps", "-w", str(wheel_dir), "--quiet"],
        capture_output=True, text=True, timeout=600,
    )
    assert build.returncode == 0, f"pip wheel failed (the wheel build needs the build backend):\n{build.stderr[-2000:]}"
    wheels = sorted(wheel_dir.glob("vcf_cf_tooling_core-*.whl"))
    assert len(wheels) == 1, wheels
    with zipfile.ZipFile(wheels[0]) as z:
        bad = [n for n in z.namelist() if not (n.startswith("vcfcf_core/") or ".dist-info/" in n)]
        assert not bad, f"wheel carries files outside vcfcf_core: {bad[:10]}"
        assert "vcfcf_core/extractor/reverse_local.py" in z.namelist()
        assert "vcfcf_core/extractor/extractor.py" in z.namelist()
        # Review W2: tie the wheel to the tree under test. setuptools reuses
        # build/lib by mtime, so a module deleted from src/ could still ride
        # in the wheel; every .py must be byte-equal to src/ and none absent.
        py_members = [n for n in z.namelist() if n.endswith(".py")]
        absent = [n for n in py_members if not (SRC / n).is_file()]
        assert not absent, f"wheel carries modules src/ no longer has: {absent}"
        stale = [n for n in py_members if z.read(n) != (SRC / n).read_bytes()]
        assert not stale, f"wheel modules differ from src/: {stale}"
        on_disk = {str(p.relative_to(SRC)) for p in (SRC / "vcfcf_core").rglob("*.py")}
        assert set(py_members) == on_disk, f"missing from wheel: {sorted(on_disk - set(py_members))}"
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--no-deps", "--target", str(site), str(wheels[0])],
        capture_output=True, text=True, timeout=600,
    )
    assert install.returncode == 0, install.stderr[-2000:]
    assert sorted(p.name for p in site.iterdir() if not p.name.endswith(".dist-info")) == ["vcfcf_core"]
    return site


@pytest.mark.slow
def test_offline_reverse_from_the_wheel_alone_matches_the_factory_path(core_wheel_site, tmp_path):
    """The 'migrator installs it by URL' gate (design §Gates): nothing from
    the factory on the path, environment cleared, empty cwd; the wheel turns
    the export zip into YAML byte-identical to the factory path's output."""
    zip_path = tmp_path / "export.zip"
    zip_path.write_bytes(_export_zip_bytes())
    bare = tmp_path / "bare"
    cwd = bare / "cwd"
    cwd.mkdir(parents=True)
    script = inspect.getsource(unpack_export_zip) + (
        "\nimport importlib, sys\n"
        "for name in ('vcfcf_common', 'vcfcf_extractor', 'vcfcf_dashboards', 'vcfcf_packaging'):\n"
        "    try:\n        importlib.import_module(name)\n    except ImportError:\n        pass\n"
        "    else:\n        sys.exit('factory package %s is importable; isolation broken' % name)\n"
        f"dash_path, xml_dir, sm_dir = unpack_export_zip({str(zip_path)!r}, {str(bare / 'in')!r})\n"
        "from vcfcf_core.extractor.reverse_local import reverse_local_port\n"
        "from pathlib import Path\n"
        f"rc = reverse_local_port(source_dashboard_json=dash_path, source_view_xml_dir=xml_dir, sm_yaml_dir=sm_dir,\n"
        f"    output_views_dir=Path({str(bare / 'out' / 'views')!r}), output_dashboards_dir=Path({str(bare / 'out' / 'dashboards')!r}),\n"
        "    name_path_override='', run_diff=True)\n"
        "leaked = sorted(m for m in sys.modules if m.startswith('vcfcf_') and not m.startswith('vcfcf_core'))\n"
        "if leaked:\n    sys.exit('non-core modules loaded: %s' % leaked)\n"
        "sys.exit(rc)\n"
    )
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(core_wheel_site)}
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=str(cwd), env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"bare-wheel reverse failed:\nstdout:\n{result.stdout[-3000:]}\nstderr:\n{result.stderr[-3000:]}"
    assert "MATCH      'VCF Consumption Overview v2'" in result.stdout, result.stdout
    assert not list(cwd.iterdir()), "the library wrote into the working directory"

    bare_out = _tree(bare / "out")
    factory_out, _ = _run_factory_reverse(zip_path, tmp_path / "factory")
    assert sorted(bare_out) == sorted(factory_out)
    assert {"views", "dashboards"} == {Path(p).parts[0] for p in bare_out}
    assert len([p for p in bare_out if p.startswith("views/")]) == 2
    for rel in bare_out:
        assert bare_out[rel] == factory_out[rel], f"{rel} differs between the wheel and the factory path"
    # The SM references resolved through the fixture's supermetrics.json, so the
    # wheel run rewrote sm_<uuid> columns rather than passing them through.
    views_text = b"".join(v for k, v in bare_out.items() if k.startswith("views/")).decode("utf-8")
    assert 'supermetric:"[Fixture] SM ' in views_text
    assert "sm_" not in views_text
