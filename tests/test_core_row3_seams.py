"""M2 row 3 seams: every leak the row fixed has a named test here.

Design: ``knowledge/designs/tooling-core-carveout-v1.md`` row 3. Each test
pins one contract the library now exposes and the factory wrapper keeps on
top of it:

- provenance: core requires the root, the wrapper sniffs it;
- super metric / report loaders: core refuses to mint, the wrapper mints;
  custom group loader: provenance is a callback; ``load_dir`` defaults;
- ``sm_id_map``: core ``None`` is an empty map, the wrapper scans the cwd;
- bundle loader: core resolves against the root it is handed, the wrapper
  sniffs one; report sections resolve where the caller says;
- dependency walker: the offline walk is core, ``walk_and_check`` is not;
- assembly: ``vcfops_manifest.json`` format, member order, payload render;
- ``vcfcf_common`` imports nothing eagerly;
- the sdk buildkit copies the core loaders, not the wrappers.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"

_SM_UUID = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"


def _sm_yaml(name: str, sm_id: str = "") -> str:
    head = f"id: {sm_id}\n" if sm_id else ""
    return (
        f"{head}name: \"{name}\"\n"
        "formula: \"avg(${this, metric=cpu|usage_average})\"\n"
        "resource_kinds:\n  - {adapter_kind_key: VMWARE, resource_kind_key: HostSystem}\n"
    )


def _report_yaml(name: str, rid: str = "") -> str:
    head = f"id: {rid}\n" if rid else ""
    return (
        f"{head}name: \"{name}\"\n"
        "subject_types:\n  - {adapter_kind: VMWARE, resource_kind: HostSystem, type: self}\n"
        "sections:\n  - type: CoverPage\n"
    )


def _cg_yaml(name: str) -> str:
    return (
        f"name: \"{name}\"\n"
        "rules:\n  - resource_kind: HostSystem\n    adapter_kind: VMWARE\n"
        "    property:\n      - {key: \"summary|version\", op: EQ, value: \"8\"}\n"
    )


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_core_requires_the_root(self, tmp_path):
        from vcfcf_core.common.provenance import provenance_from_path
        f = tmp_path / "content" / "supermetrics" / "x.yaml"
        f.parent.mkdir(parents=True)
        f.write_text("name: x\n")
        assert provenance_from_path(f, tmp_path) == "factory"
        tp = tmp_path / "third_party" / "acme" / "views" / "v.yaml"
        tp.parent.mkdir(parents=True)
        tp.write_text("name: v\n")
        assert provenance_from_path(tp, tmp_path) == "acme"
        assert provenance_from_path(tmp_path / "elsewhere.yaml", tmp_path) == ""
        assert provenance_from_path("", tmp_path) == ""
        with pytest.raises(TypeError, match="repo_root is required"):
            provenance_from_path(f, None)  # type: ignore[arg-type]

    def test_wrapper_sniffs_the_root_and_delegates(self, tmp_path):
        import vcfcf_common.provenance as old
        # No content/ or third_party/ ancestor yet: the sniff finds nothing, "".
        lone = tmp_path / "lone" / "x.yaml"
        lone.parent.mkdir()
        lone.write_text("name: x\n")
        assert old._find_repo_root(lone) is None
        assert old.provenance_from_path(lone) == ""
        f = tmp_path / "third_party" / "acme" / "views" / "v.yaml"
        f.parent.mkdir(parents=True)
        f.write_text("name: v\n")
        assert old._find_repo_root(f) == tmp_path
        assert old.provenance_from_path(f) == "acme"
        assert old.provenance_from_path(f, repo_root=tmp_path) == "acme"

    def test_factory_paths_still_classify_from_a_foreign_cwd(self, tmp_path, monkeypatch):
        """The repo's own content classifies as factory from any cwd, as before."""
        monkeypatch.chdir(tmp_path)
        from vcfcf_common.provenance import provenance_from_path
        sm = sorted((REPO_ROOT / "content" / "supermetrics").glob("*.yaml"))[0]
        assert provenance_from_path(sm) == "factory"
        tp = sorted((REPO_ROOT / "third_party" / "idps-planner").rglob("*.yaml"))[0]
        assert provenance_from_path(tp) == "idps-planner"


# ---------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------

class TestSuperMetricLoader:
    def test_core_refuses_to_mint_and_writes_nothing(self, tmp_path):
        import vcfcf_core.supermetrics.loader as core
        f = tmp_path / "sm.yaml"
        f.write_text(_sm_yaml("[VCF Content Factory] Row3 SM"), encoding="utf-8")
        before = f.read_text(encoding="utf-8")
        with pytest.raises(core.SuperMetricValidationError, match="missing id .* on_missing_id"):
            core.load_file(f)
        assert f.read_text(encoding="utf-8") == before
        loaded = core.load_file(f, on_missing_id=lambda p: _SM_UUID.upper())
        assert loaded.id == _SM_UUID
        assert loaded.provenance == ""
        assert f.read_text(encoding="utf-8") == before

    @pytest.mark.parametrize("garbage", ["", "nope", None])
    def test_core_validates_the_callback_return(self, tmp_path, garbage):
        import vcfcf_core.supermetrics.loader as core
        f = tmp_path / "sm.yaml"
        f.write_text(_sm_yaml("[VCF Content Factory] Row3 SM"), encoding="utf-8")

        def bad(path):
            return garbage

        with pytest.raises(core.SuperMetricValidationError, match=r"on_missing_id \(bad\).*not a valid uuid4"):
            core.load_file(f, on_missing_id=bad)

    def test_wrapper_mints_and_derives_provenance(self, tmp_path):
        import vcfcf_core.supermetrics.loader as core
        import vcfcf_supermetrics.loader as old
        f = tmp_path / "content" / "supermetrics" / "sm.yaml"
        f.parent.mkdir(parents=True)
        f.write_text(_sm_yaml("[VCF Content Factory] Row3 SM"), encoding="utf-8")
        loaded = old.load_file(f)
        assert f.read_text(encoding="utf-8").startswith(f"id: {loaded.id}\n")
        assert core._UUID_RE.match(loaded.id)
        assert loaded.provenance == "factory"
        # The minted file now loads through core without a callback.
        assert core.load_file(f).id == loaded.id

    def test_core_load_dir_requires_a_directory(self, tmp_path):
        import vcfcf_core.supermetrics.loader as core
        import vcfcf_supermetrics.loader as old
        with pytest.raises(TypeError):
            core.load_dir()  # type: ignore[call-arg]
        assert core.load_dir(tmp_path / "absent") == []
        assert old.load_dir.__defaults__[0] == "supermetrics"


class TestSmIdMap:
    def test_core_none_is_an_empty_map_even_with_a_cwd_tree(self, tmp_path, monkeypatch):
        import vcfcf_core.supermetrics.loader as core
        d = tmp_path / "content" / "supermetrics"
        d.mkdir(parents=True)
        (d / "a.yaml").write_text(_sm_yaml("[VCF Content Factory] Map A", _SM_UUID), encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert core.sm_id_map(None) == {}
        assert core.sm_id_map([]) == {}
        assert core.sm_id_map([d / "a.yaml"]) == {"[VCF Content Factory] Map A": _SM_UUID}

    def test_core_scoped_load_failure_names_the_bundle(self, tmp_path):
        import vcfcf_core.supermetrics.loader as core
        with pytest.raises(ValueError, match=r'^sm_id_map: failed to load scoped SM for bundle \'probe\''):
            core.sm_id_map([tmp_path / "nope.yaml"], "probe")

    def test_core_scoped_refuses_an_id_less_file_the_wrapper_mints(self, tmp_path):
        import vcfcf_core.supermetrics.loader as core
        import vcfcf_supermetrics.loader as old
        f = tmp_path / "noid.yaml"
        f.write_text(_sm_yaml("Third Party Map"), encoding="utf-8")
        with pytest.raises(ValueError, match="missing id"):
            core.sm_id_map([f], "probe")
        assert not f.read_text(encoding="utf-8").startswith("id:")
        mapped = old.sm_id_map([f], "probe")
        assert f.read_text(encoding="utf-8").startswith(f"id: {mapped['Third Party Map']}\n")

    def test_wrapper_none_still_scans_the_cwd(self, tmp_path, monkeypatch):
        import vcfcf_supermetrics.loader as old
        d = tmp_path / "content" / "supermetrics"
        d.mkdir(parents=True)
        (d / "a.yaml").write_text(_sm_yaml("[VCF Content Factory] Map A", _SM_UUID), encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert old.sm_id_map() == {"[VCF Content Factory] Map A": _SM_UUID}


class TestCustomGroupLoader:
    def test_core_provenance_is_a_callback(self, tmp_path):
        import vcfcf_core.customgroups.loader as core
        f = tmp_path / "cg.yaml"
        f.write_text(_cg_yaml("[VCF Content Factory] Row3 CG"), encoding="utf-8")
        assert core.load_file(f).provenance == ""
        assert core.load_file(f, provenance_of=lambda p: "acme").provenance == "acme"
        with pytest.raises(TypeError):
            core.load_dir()  # type: ignore[call-arg]

    def test_wrapper_keeps_the_default_and_the_layout_provenance(self, tmp_path):
        import vcfcf_customgroups.loader as old
        f = tmp_path / "content" / "customgroups" / "cg.yaml"
        f.parent.mkdir(parents=True)
        f.write_text(_cg_yaml("[VCF Content Factory] Row3 CG"), encoding="utf-8")
        assert old.load_file(f).provenance == "factory"
        assert old.load_dir.__defaults__[0] == "customgroups"
        assert [c.name for c in old.load_dir(f.parent)] == ["[VCF Content Factory] Row3 CG"]


class TestReportLoader:
    def test_core_requires_dirs_and_refuses_to_mint(self, tmp_path):
        import vcfcf_core.reports.loader as core
        f = tmp_path / "r.yaml"
        f.write_text(_report_yaml("[VCF Content Factory] Row3 Report"), encoding="utf-8")
        before = f.read_text(encoding="utf-8")
        with pytest.raises(TypeError):
            core.load_file(f)  # type: ignore[call-arg]
        with pytest.raises(core.ReportValidationError, match="missing id .* on_missing_id"):
            core.load_file(f, tmp_path / "v", tmp_path / "d")
        assert f.read_text(encoding="utf-8") == before
        rid = str(uuid.uuid4())
        loaded = core.load_file(f, tmp_path / "v", tmp_path / "d", on_missing_id=lambda p: rid)
        assert loaded.id == rid
        assert f.read_text(encoding="utf-8") == before
        with pytest.raises(TypeError):
            core.load_dir(tmp_path)  # type: ignore[call-arg]

    def test_wrapper_mints_and_keeps_the_content_defaults(self, tmp_path):
        import vcfcf_reports.loader as old
        f = tmp_path / "r.yaml"
        f.write_text(_report_yaml("[VCF Content Factory] Row3 Report"), encoding="utf-8")
        loaded = old.load_file(f)
        assert f.read_text(encoding="utf-8").startswith(f"id: {loaded.id}\n")
        assert old.load_file.__defaults__ == ("content/views", "content/dashboards", True)
        assert old.load_dir.__defaults__ == ("content/reports", "content/views", "content/dashboards", True)

    def test_view_reference_resolves_where_the_caller_says(self, tmp_path):
        import vcfcf_core.reports.loader as core
        views = tmp_path / "myviews"
        views.mkdir()
        vid = str(uuid.uuid4())
        (views / "v.yaml").write_text(f"id: {vid}\nname: \"[VCF Content Factory] Row3 View\"\n", encoding="utf-8")
        f = tmp_path / "r.yaml"
        f.write_text(
            f"id: {uuid.uuid4()}\nname: \"[VCF Content Factory] Row3 Report\"\n"
            "subject_types:\n  - {adapter_kind: VMWARE, resource_kind: HostSystem, type: self}\n"
            "sections:\n  - {type: View, view: \"[VCF Content Factory] Row3 View\"}\n",
            encoding="utf-8",
        )
        assert core.load_file(f, views, tmp_path / "d").sections[0].view_id == vid
        with pytest.raises(core.ReportValidationError, match="could not be resolved"):
            core.load_file(f, tmp_path / "absent", tmp_path / "d")


# ---------------------------------------------------------------------------
# bundle loader
# ---------------------------------------------------------------------------

def _bundle_tree(root: Path, *, sm_id: str = _SM_UUID) -> Path:
    (root / "content" / "supermetrics").mkdir(parents=True)
    (root / "content" / "supermetrics" / "a.yaml").write_text(
        _sm_yaml("[VCF Content Factory] Bundle SM", sm_id), encoding="utf-8")
    (root / "bundles").mkdir()
    manifest = root / "bundles" / "probe.yaml"
    manifest.write_text(
        "name: probe\nsupermetrics:\n  - content/supermetrics/a.yaml\n", encoding="utf-8")
    return manifest


class TestBundleLoader:
    def test_core_resolves_against_the_root_it_is_handed(self, tmp_path):
        import vcfcf_core.packaging.loader as core
        manifest = _bundle_tree(tmp_path)
        b = core.load_bundle(manifest, repo_root=tmp_path)
        assert [sm.name for sm in b.supermetrics] == ["[VCF Content Factory] Bundle SM"]
        assert b.supermetrics[0].provenance == ""
        # No root: only manifest-relative references resolve, and the error
        # names the one candidate tried.
        with pytest.raises(core.BundleValidationError) as exc:
            core.load_bundle(manifest)
        assert "referenced file not found" in str(exc.value)
        assert str(tmp_path / "bundles" / "content" / "supermetrics" / "a.yaml") in str(exc.value)
        assert " and " not in str(exc.value).split("(tried")[1]

    def test_core_refuses_to_mint_inside_a_bundle(self, tmp_path):
        import vcfcf_core.packaging.loader as core
        manifest = _bundle_tree(tmp_path, sm_id="")
        sm_file = tmp_path / "content" / "supermetrics" / "a.yaml"
        before = sm_file.read_text(encoding="utf-8")
        with pytest.raises(core.BundleValidationError, match="missing id"):
            core.load_bundle(manifest, repo_root=tmp_path)
        assert sm_file.read_text(encoding="utf-8") == before
        b = core.load_bundle(manifest, repo_root=tmp_path, on_missing_id=lambda p: _SM_UUID,
                             provenance_of=lambda p: "probe")
        assert b.supermetrics[0].id == _SM_UUID
        assert b.supermetrics[0].provenance == "probe"
        assert sm_file.read_text(encoding="utf-8") == before

    def test_wrapper_sniffs_the_root_mints_and_classifies(self, tmp_path):
        import vcfcf_packaging.loader as old
        (tmp_path / "src" / "vcfcf_common").mkdir(parents=True)
        manifest = _bundle_tree(tmp_path, sm_id="")
        assert old._find_repo_root(manifest.parent) == tmp_path
        b = old.load_bundle(manifest)
        sm_file = tmp_path / "content" / "supermetrics" / "a.yaml"
        assert sm_file.read_text(encoding="utf-8").startswith(f"id: {b.supermetrics[0].id}\n")
        assert b.supermetrics[0].provenance == "factory"
        assert old.load_all_bundles.__defaults__ == ("bundles",)
        assert [x.name for x in old.load_all_bundles(tmp_path / "bundles")] == ["probe"]

    def test_wrapper_root_sniff_falls_back_to_the_manifest_parent_parent(self, tmp_path):
        import vcfcf_packaging.loader as old
        manifest = _bundle_tree(tmp_path)
        assert old._find_repo_root(manifest.parent) == tmp_path  # no vcfcf_common marker anywhere
        assert old.load_bundle(manifest).supermetrics[0].id == _SM_UUID

    def test_core_report_sections_default_to_dirs_beside_the_manifest(self, tmp_path):
        import vcfcf_core.packaging.loader as core
        project = tmp_path / "third_party" / "acme"
        (project / "views").mkdir(parents=True)
        (project / "reports").mkdir()
        vid = str(uuid.uuid4())
        (project / "views" / "v.yaml").write_text(
            f"id: {vid}\nname: \"Acme View\"\nsubject: {{adapter_kind: VMWARE, resource_kind: HostSystem}}\n"
            "columns:\n  - {display_name: CPU, attribute: cpu|usage_average}\n", encoding="utf-8")
        (project / "reports" / "r.yaml").write_text(
            f"id: {uuid.uuid4()}\nname: \"Acme Report\"\n"
            "subject_types:\n  - {adapter_kind: VMWARE, resource_kind: HostSystem, type: self}\n"
            "sections:\n  - {type: View, view: \"Acme View\"}\n", encoding="utf-8")
        (project / "PROJECT.yaml").write_text("name: acme\nfactory_native: false\n", encoding="utf-8")
        b = core.load_bundle(project / "PROJECT.yaml")
        assert b.reports[0].sections[0].view_id == vid
        # An explicit, empty directory makes the same reference unresolvable.
        with pytest.raises(core.BundleValidationError, match="could not be resolved"):
            core.load_bundle(project / "PROJECT.yaml", report_views_dir=tmp_path / "empty")


# ---------------------------------------------------------------------------
# dependency walker
# ---------------------------------------------------------------------------

class TestDepWalkerSplit:
    def test_offline_walk_is_core_and_needs_no_client(self):
        import vcfcf_core.common.dep_walker as core
        from vcfcf_core.supermetrics.loader import SuperMetricDef
        a = SuperMetricDef(name="[VCF Content Factory] A", formula='${this, attribute=@supermetric:"[VCF Content Factory] B"}',
                           id=_SM_UUID, resource_kinds=[{"resourceKindKey": "HostSystem", "adapterKindKey": "VMWARE"}])
        b = SuperMetricDef(name="[VCF Content Factory] B", formula="${this, metric=cpu|usage_average}",
                           id="bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb", resource_kinds=a.resource_kinds)
        sms, errors = core.expand_sm_crossrefs([a], [a, b])
        assert [s.name for s in sms] == [a.name, b.name] and errors == []
        graph = core.collect_deps([], [], [a, b], [])
        assert graph.errors == [] and graph.supermetrics == []

    def test_live_half_stays_factory_side_and_still_runs(self):
        import vcfcf_common.dep_walker as old
        from vcfcf_supermetrics.loader import SuperMetricDef

        class _Client:
            def export_default_policy_xml(self):
                return "<policy/>"

            def verify_supermetrics_enabled(self, policy_xml, uuids):
                return {u: True for u in uuids}

        sm = SuperMetricDef(name="[VCF Content Factory] A", formula="${this, metric=cpu|usage_average}",
                            id=_SM_UUID, resource_kinds=[{"resourceKindKey": "HostSystem", "adapterKindKey": "VMWARE"}])
        res = old.walk_and_check(client=_Client(), supermetrics=[sm], views=[], dashboards=[],
                                 customgroups=[], skip_metric_check=True)
        assert isinstance(res, old.WalkResult) and res.ok
        assert res.messages[-1] == ("OK", "OOTB metric check skipped (--skip-metric-check)")


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------

def _bundle_obj(**over):
    from vcfcf_core.packaging.loader import Bundle
    from vcfcf_core.supermetrics.loader import SuperMetricDef
    sm = SuperMetricDef(name="[VCF Content Factory] Asm SM", formula="${this, metric=cpu|usage_average}",
                        id=_SM_UUID, resource_kinds=[{"resourceKindKey": "HostSystem", "adapterKindKey": "VMWARE"}])
    kw = dict(name="asm-probe", description="d", sync_enabled=True, supermetrics=[sm],
              views=[], dashboards=[], customgroups=[])
    kw.update(over)
    return Bundle(**kw)


class TestAssembly:
    def test_vcfops_manifest_format_is_byte_for_byte(self):
        from vcfcf_core.packaging.assembly import render_vcfops_manifest
        out = render_vcfops_manifest({"bundle_name": "x", "template_version": "2026-01-01-1"}, built_at="2026-09-14T00:00:00Z")
        assert out == json.dumps({"bundle_name": "x", "template_version": "2026-01-01-1",
                                  "built_at": "2026-09-14T00:00:00Z"}, indent=2)
        discrete = render_vcfops_manifest(
            {"bundle_name": "x", "item_type": "dashboard", "item_name": "N", "item_version": "1.0",
             "template_version": "t"}, built_at="b")
        assert list(json.loads(discrete)) == ["bundle_name", "item_type", "item_name", "item_version",
                                              "template_version", "built_at"]

    def test_zip_member_order_and_payload_routing(self):
        from vcfcf_core.packaging.assembly import (
            assemble_distribution_zip, render_bundle_payloads, _build_bundle_json,
        )
        bundle = _bundle_obj()
        payloads = render_bundle_payloads(bundle, sm_map={}, bundle_context="probe")
        assert payloads.sm_json and payloads.views_xml is None and payloads.alerts_json is None
        blob = assemble_distribution_zip(
            slug="asm-probe", payloads=payloads, bundle_json=_build_bundle_json(bundle, "Asm Probe"),
            bundle_readme="# r", install_py="py", install_ps1="ps1", framework_readme="fw",
            vcfops_manifest="{}", license_text="MIT",
        )
        names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
        assert names == [
            "install.py", "install.ps1", "README.md", "vcfops_manifest.json", "LICENSE",
            "bundles/asm-probe/bundle.json", "bundles/asm-probe/README.md",
            "bundles/asm-probe/supermetric.json", "bundles/asm-probe/content/supermetrics.json",
        ]
        z = zipfile.ZipFile(io.BytesIO(blob))
        assert z.read("bundles/asm-probe/supermetric.json") == z.read("bundles/asm-probe/content/supermetrics.json")
        assert json.loads(z.read("bundles/asm-probe/bundle.json"))["content"]["supermetrics"]["items"] == [
            {"uuid": _SM_UUID, "name": "[VCF Content Factory] Asm SM"}]
        # No LICENSE member when none is supplied.
        blob2 = assemble_distribution_zip(
            slug="asm-probe", payloads=payloads, bundle_json="{}", bundle_readme="", install_py="",
            install_ps1="", framework_readme="", vcfops_manifest="{}", license_text=None,
        )
        assert "LICENSE" not in zipfile.ZipFile(io.BytesIO(blob2)).namelist()

    def test_assembly_reads_nothing_from_the_repo(self):
        import vcfcf_core.packaging.assembly as asm
        src = Path(asm.__file__).read_text(encoding="utf-8")
        for token in ("read_text(", "read_bytes(", "_TEMPLATES_DIR", "knowledge/designs",
                      "utcnow", "make_cache", "Path(__file__)", "os.environ"):
            assert token not in src, token


# ---------------------------------------------------------------------------
# vcfcf_common package init
# ---------------------------------------------------------------------------

def test_vcfcf_common_imports_nothing_eagerly():
    probe = (
        "import sys\n"
        "import vcfcf_common\n"
        "loaded = sorted(m for m in sys.modules if m.startswith('vcfcf_common.'))\n"
        "assert loaded == [], loaded\n"
        "assert 'requests' not in sys.modules\n"
        "import vcfcf_common.provenance, vcfcf_common.dep_walker\n"
        "loaded = sorted(m for m in sys.modules if m.startswith('vcfcf_common.'))\n"
        "assert loaded == ['vcfcf_common.dep_walker', 'vcfcf_common.provenance'], loaded\n"
        "assert 'requests' not in sys.modules\n"
        "from vcfcf_common import load_dotenv, add_profile_arg\n"
        "assert callable(load_dotenv) and callable(add_profile_arg)\n"
        "assert 'vcfcf_common._env' in sys.modules\n"
        "print('lazy ok')\n"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                            env={"PATH": "", "PYTHONPATH": str(SRC)}, cwd=str(REPO_ROOT), timeout=60)
    assert result.returncode == 0, result.stderr
    assert "lazy ok" in result.stdout


# ---------------------------------------------------------------------------
# buildkit sources
# ---------------------------------------------------------------------------

def test_buildkit_copies_the_core_loaders_not_the_wrappers():
    from vcfcf_managementpacks.buildkit import _FACTORY_SOURCES, _IMPORT_REWRITES
    core = SRC / "vcfcf_core"
    assert _FACTORY_SOURCES["sm_loader.py"] == core / "supermetrics" / "loader.py"
    assert _FACTORY_SOURCES["reports_loader.py"] == core / "reports" / "loader.py"
    assert _FACTORY_SOURCES["reports_render.py"] == core / "reports" / "render.py"
    assert "provenance.py" not in _FACTORY_SOURCES
    assert "sm_loader.py" not in _IMPORT_REWRITES
    import re  # noqa: PLC0415
    for dest, src in _FACTORY_SOURCES.items():
        if dest.endswith("_loader.py") or dest.endswith("_render.py") or dest in ("sm_crossref.py", "dashboard_yaml_utils.py"):
            offending = [
                line for line in src.read_text(encoding="utf-8").splitlines()
                if re.match(r"^\s*(from|import)\s+vcfcf_common", line)
            ]
            assert offending == [], f"{dest}: {offending}"
