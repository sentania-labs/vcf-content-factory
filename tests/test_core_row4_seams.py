"""M2 row 4 seams: the extractor's pure half and reverse_local in vcfcf_core.

Design: ``knowledge/designs/tooling-core-carveout-v1.md`` row 4. Each test
pins one contract the library now exposes and the factory keeps on top:

- the repo root stays in the factory: core binds none, ``_scan_existing_ids``
  takes it as a required argument and ``extract_dashboard`` passes its own;
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
        (tmp_path / "supermetrics").mkdir()
        target = tmp_path / "supermetrics" / "x.yaml"
        target.write_text(f"id: {_UUID}\nname: x\n", encoding="utf-8")
        assert _scan_existing_ids("supermetric", tmp_path) == {_UUID: target}
        assert _scan_existing_ids("view", tmp_path) == {}
        assert _scan_existing_ids("supermetric", tmp_path / "absent") == {}

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

def _export_zip_bytes() -> bytes:
    """A content-export-shaped zip built from the two export-derived text
    fixtures: ``views.zip`` holding ``content.xml`` (VIEW_DEFINITIONS shape,
    the nested form ``_parse_view_xml`` accepts), ``dashboards/<uuid>`` inner
    zips holding ``dashboard/dashboard.json`` (DASHBOARDS shape, what
    ``_export_dashboard_json`` walks), and a ``supermetrics.json`` keyed by
    UUID (SUPER_METRICS shape) naming the six SMs the views reference."""
    views_inner = io.BytesIO()
    with zipfile.ZipFile(views_inner, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", VIEWS_XML.read_bytes())
    dash_doc = json.loads(DASH_JSON.read_text(encoding="utf-8"))
    dash_inner = io.BytesIO()
    with zipfile.ZipFile(dash_inner, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dashboard/dashboard.json", json.dumps(dash_doc))
    sm_uuids = sorted(set(re.findall(r"Super Metric\|sm_([0-9a-f-]{36})", VIEWS_XML.read_text(encoding="utf-8"))))
    sms = {u: {"name": f"[Fixture] SM {i}", "formula": "1", "resourceKinds": []} for i, u in enumerate(sm_uuids, 1)}
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("views.zip", views_inner.getvalue())
        z.writestr(f"dashboards/{dash_doc.get('uuid') or 'export'}", dash_inner.getvalue())
        z.writestr("supermetrics.json", json.dumps(sms))
    return outer.getvalue()


def unpack_export_zip(zip_path, dest):
    """Stdlib-only: lay a content-export zip out as reverse_local's inputs.

    Returns (dashboard_json_path, view_xml_dir, sm_yaml_dir). Shared by the
    bare-venv subprocess and the factory run, so both read identical inputs.
    """
    import io as _io
    import json as _json
    import zipfile as _zipfile
    from pathlib import Path as _Path

    dest = _Path(dest)
    xml_dir = dest / "xml"
    sm_dir = dest / "sm"
    xml_dir.mkdir(parents=True)
    sm_dir.mkdir()
    dash_path = dest / "dashboard.json"
    with _zipfile.ZipFile(zip_path) as outer:
        for name in outer.namelist():
            data = outer.read(name)
            if name.startswith("dashboards/"):
                with _zipfile.ZipFile(_io.BytesIO(data)) as inner:
                    dash_path.write_bytes(inner.read("dashboard/dashboard.json"))
            elif name.lower().endswith(".zip"):
                with _zipfile.ZipFile(_io.BytesIO(data)) as inner:
                    if "content.xml" in inner.namelist():
                        (xml_dir / "content.xml").write_bytes(inner.read("content.xml"))
            elif name == "supermetrics.json":
                for uid, sm in _json.loads(data).items():
                    (sm_dir / f"{uid}.yaml").write_text(f"id: {uid}\nname: \"{sm['name']}\"\n", encoding="utf-8")
    return dash_path, xml_dir, sm_dir


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
