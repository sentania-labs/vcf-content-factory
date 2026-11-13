"""``import-local``: every source key accounted for, and "identical" meaning it.

The fixes of the 2026-11-13 framework review of ``tooling/importer-fidelity``
(``knowledge/context/reviews/framework/extractor-import-local-2026-11-13.md``):
super metric ids rewritten in every type (B1), deviations and losses set
aside only at their exact paths (B2, W1), every source key classified (B3,
B6), one object's unexpected shape never stopping the run (B4), the bundle
loader's report resolution (B5), the target floor (W2), names (W4),
repeatable minting (W5), staged writing (W6, W7), unsupported types (W8),
the CLI options (W10) and the nits; and a mutation self-test: each single
change to a source or to a written YAML must be reported.

Fixtures are synthetic ("Probe ..." names), built by the factory's own
renderers (``test_import_local._build_source``); the real CLI and the real
layout loaders are used throughout.
"""
from __future__ import annotations

import json
import re
import shutil
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from test_import_local import (  # the shared synthetic source and CLI driver
    D_A, D_B, SM1, SM2, SOURCE_YAML, STOCK_VIEW_ID, V_DIST, V_HOST, V_LONE, V_TREND,
    _build_source, _files, _run, _yaml,
)
from vcfcf_core.alerts.render import render_alert_content_xml
from vcfcf_core.dashboards.loader import load_dashboard, load_view
from vcfcf_core.dashboards.render import render_dashboards_bundle_json, render_views_xml
from vcfcf_core.symptoms.loader import load_file as load_sym
from vcfcf_core.alerts.loader import load_file as load_alert

UNKNOWN_VIEW = "9e000000-0000-4000-8000-0000000000ee"


@pytest.fixture(scope="module")
def source(tmp_path_factory) -> Path:
    return _build_source(tmp_path_factory.mktemp("import_local_fidelity"))


def _copy(source: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "src"
    shutil.copytree(source, dst)
    return dst


def _sub(path: Path, pattern: str, repl, count: int = 1) -> None:
    text = path.read_text()
    new, n = re.subn(pattern, repl, text, count=count)
    assert n, f"{pattern!r} not found in {path}"
    path.write_text(new)


def _dash_json(root: Path, fn, dash_id: str = D_A) -> None:
    p = root / "dashboards" / "Both.json"
    env = json.loads(p.read_text())
    fn(next(d for d in env["dashboards"] if d["id"] == dash_id))
    p.write_text(json.dumps(env, indent=2))


def _load_yaml(text: str, tmp_path: Path, name: str):
    p = tmp_path / name
    p.write_text(textwrap.dedent(text).lstrip())
    return p


# ======================================================================== B1
def _sm_everywhere_source(tmp_path: Path) -> Path:
    """The shared source plus a symptom, an alert's inline symptom, a view
    filter and a Pareto additional column on ``Super Metric|sm_<SM1>``."""
    src = _build_source(tmp_path)
    y = tmp_path / "b1"
    y.mkdir()
    sym = _load_yaml(f"""
        id: 3c000000-0000-4000-8000-0000000000b1
        name: Probe SM Symptom
        adapter_kind: VMWARE
        resource_kind: HostSystem
        severity: WARNING
        wait_cycles: 1
        cancel_cycles: 1
        omit: [wait_cycles, cancel_cycles]
        condition: {{type: metric_static, key: "Super Metric|sm_{SM1}", operator: GT, value: 5, instanced: false}}
    """, y, "s.yaml")
    inline = _load_yaml(f"""
        id: 3c000000-0000-4000-8000-0000000000b2
        name: Probe SM Inline Symptom
        adapter_kind: VMWARE
        resource_kind: HostSystem
        severity: CRITICAL
        wait_cycles: 2
        cancel_cycles: 2
        condition: {{type: metric_static, key: "Super Metric|sm_{SM1}", operator: LT, value: 1, instanced: false}}
    """, y, "si.yaml")
    alert = _load_yaml("""
        id: 4a000000-0000-4000-8000-0000000000b1
        name: Probe SM Alert
        description: sm alert
        adapter_kind: VMWARE
        resource_kind: HostSystem
        type: 16
        sub_type: 19
        criticality: WARNING
        impact: {badge: HEALTH}
        symptom_sets:
          operator: ALL
          sets:
            - defined_on: SELF
              operator: ALL
              symptoms: [{name: Probe SM Inline Symptom}]
    """, y, "a.yaml")
    (src / "symptomdefs" / "SmSym.xml").write_text(
        render_alert_content_xml([load_sym(sym, enforce_framework_prefix=False)], [], []))
    (src / "alertdefs" / "SmAlert.xml").write_text(render_alert_content_xml(
        [load_sym(inline, enforce_framework_prefix=False)], [load_alert(alert, enforce_framework_prefix=False)], []))
    # a view filter on the super metric
    _sub(src / "reports" / "View - Set.xml", r'(<ViewDef id="%s".*?filter=")([^"]*)(")' % V_HOST,
         lambda m: m.group(1) + m.group(2).replace("summary|version", f"Super Metric|sm_{SM1}") + m.group(3))
    _sub(src / "resources" / "nested" / "extra.xml", r'(<ViewDef id="%s".*?filter=")([^"]*)(")' % V_HOST,
         lambda m: m.group(1) + m.group(2).replace("summary|version", f"Super Metric|sm_{SM1}") + m.group(3))
    # a Pareto additional column on the super metric (dashboard B)
    p = _load_yaml(f"""
        id: 1d000000-0000-4000-8000-0000000000b1
        name: Probe Pareto
        description: pareto
        name_path: ""
        shared: false
        widgets:
          - id: top
            type: ParetoAnalysis
            title: Top
            coords: {{x: 1, y: 1, w: 12, h: 4}}
            adapter_kind: VMWARE
            resource_kind: HostSystem
            metric_key: cpu|usage_average
            metric_name: CPU
            mode: all
            top_n: 10
            depth: 1
            additional_columns:
              - {{metric_key: "Super Metric|sm_{SM1}", metric_name: Probe SM One, label: SM, adapter_kind: VMWARE, resource_kind: HostSystem}}
    """, y, "p.yaml")
    d = load_dashboard(p, enforce_framework_prefix=False, default_name_path="")
    (src / "dashboards" / "Pareto.json").write_text(render_dashboards_bundle_json([d], {}, "0"))
    return src


@pytest.mark.parametrize("mode", ["mint", "map"])
def test_b1_super_metric_ids_follow_in_every_type(tmp_path, capsys, mode):
    src = _sm_everywhere_source(tmp_path)
    out = tmp_path / "out"
    if mode == "mint":
        ids = ["--ids", "mint", "--mint-namespace", "b1"]
    else:
        m = tmp_path / "map.tsv"
        m.write_text(f"{SM1}\t5f000000-0000-4000-8000-0000000000b1\n")
        ids = ["--id-map", m]
    rc, text = _run(src, out, capsys, "--layout", "third-party", *ids, "--naming", "unprefixed")
    assert rc == 0, text
    rows = {r.split("\t")[1]: r.split("\t")[2] for r in (out / "import-report" / "id_map.tsv").read_text().splitlines()
            if r and not r.startswith(("#", "type\t"))}
    new = rows[SM1]
    assert new != SM1
    blob = "".join(p.read_text() for p in out.rglob("*.yaml"))
    assert SM1 not in blob.lower(), "an old super metric id survived"
    # symptom condition, alert-file inline symptom, view filter, widget
    # metric entry, Pareto additional column: the new id (no name form)
    assert _yaml(out, "symptoms/probe-sm-symptom.yaml")["condition"]["key"] == f"Super Metric|sm_{new}"
    assert _yaml(out, "symptoms/probe-sm-inline-symptom.yaml")["condition"]["key"] == f"Super Metric|sm_{new}"
    filt = _yaml(out, "views/probe-host-list.yaml")["subject"]["filter"][0][0]
    assert filt["metric_key"] == f"Super Metric|sm_{new}"
    assert _yaml(out, "dashboards/probe-dashboard-a.yaml")["widgets"][1]["metrics"][0]["metric_key"] == \
        f"Super Metric|sm_{new}"
    assert _yaml(out, "dashboards/probe-pareto.yaml")["widgets"][0]["additional_columns"][0]["metric_key"] == \
        f"Super Metric|sm_{new}"
    # formulas and view columns: the name form
    assert '@supermetric:"Probe SM One"' in _yaml(out, "supermetrics/probe-sm-two.yaml")["formula"]
    assert re.search(r"; 0 differ$", text, re.M), text


def test_b1_an_old_id_that_survives_fails_its_object_naming_the_field(source, tmp_path, capsys, monkeypatch):
    from vcfcf_core.importer import convert
    monkeypatch.setattr(convert._Planner, "rewrite_ids", lambda self, e: None)  # simulate a missed rewrite
    rc, text = _run(source, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "mint", "--mint-namespace",
                    "b1", "--naming", "unprefixed", "--allow-partial")
    assert f"FAILED dashboard {D_A}" in text
    assert "field widgets[1].metrics[0].metric_key still names" in text and SM1 in text


# ======================================================================= B3
def test_b3_column_localization_key_is_a_gap_not_a_silent_drop(source, tmp_path, capsys):
    src = _copy(source, tmp_path)
    _sub(src / "reports" / "View - Set.xml", r'(<ViewDef id="%s".*?)<Property name="displayName"' % V_TREND,
         r'\1<Property localizationKey="probeKey" name="displayName"')
    rc, text = _run(src, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 1
    assert f"FAILED view {V_TREND}" in text and "Property{displayName}@localizationKey" in text
    assert "TOOLSET GAP" in text


def test_b3_copies_differing_in_a_formerly_ignored_attribute_do_not_merge(source, tmp_path, capsys):
    src = _copy(source, tmp_path)
    # renumbered: control ids differ between copies -> still one object
    _sub(src / "resources" / "nested" / "extra.xml", r'(<ViewDef id="%s".*?<Control id=")[^"]*' % V_HOST, r"\1other-id")
    rc, text = _run(src, tmp_path / "o1", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 0 and f"merged: view {V_HOST}" in text, text
    # a Control visible differs -> two different copies
    _sub(src / "resources" / "nested" / "extra.xml", r'(<ViewDef id="%s".*?type="time-interval-selector" visible=")false'
         % V_HOST, r"\1true")
    rc, text = _run(src, tmp_path / "o2", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 1 and f"FAILED view {V_HOST}" in text and "defined differently" in text


# ======================================================================= B4
def _alert_list_source(tmp_path: Path, fn) -> Path:
    src = tmp_path / "b4"
    src.mkdir(parents=True)
    p = _load_yaml("""
        id: 1d000000-0000-4000-8000-0000000000b4
        name: Probe Alerts
        description: alerts
        name_path: ""
        shared: false
        widgets:
          - id: al
            type: AlertList
            title: Alerts
            coords: {x: 1, y: 1, w: 6, h: 4}
            alert_definitions: [AlertDefinition-VMWARE-ProbeAlert]
          - id: mc
            type: MetricChart
            title: Chart
            coords: {x: 7, y: 1, w: 6, h: 4}
            metrics:
              - {adapter_kind: VMWARE, resource_kind: HostSystem, metric_key: cpu|usage_average, metric_name: CPU}
    """, tmp_path, "b4.yaml")
    d = load_dashboard(p, enforce_framework_prefix=False, default_name_path="")
    env = json.loads(render_dashboards_bundle_json([d], {}, "0"))
    fn(env["dashboards"][0])
    (src / "d.json").write_text(json.dumps(env))
    return src


def test_b4_product_shapes_are_gaps_not_crashes(tmp_path, capsys):
    def ids_as_strings(db):
        db["widgets"][0]["config"]["alertDefinitions"] = ["AlertDefinition-VMWARE-ProbeAlert"]

    def list_relationship_mode(db):
        db["widgets"][1]["config"]["relationshipMode"]["relationshipMode"] = [1, -1, 0]
    for fn, what in ((ids_as_strings, "alertDefinitions"), (list_relationship_mode, "relationshipMode as a list")):
        src = _alert_list_source(tmp_path / fn.__name__, fn)
        rc, text = _run(src, tmp_path / fn.__name__ / "o", capsys, "--layout", "third-party", "--ids", "keep",
                        "--naming", "unprefixed")
        assert rc == 4, text  # the one object failed: nothing was left to compare
        assert "FAILED dashboard" in text and what in text and "TOOLSET GAP" in text
        assert "INTERNAL ERROR" not in text and "Traceback" not in text


def test_b4_an_unexpected_exception_fails_one_object_and_exits_5(source, tmp_path, capsys, monkeypatch):
    from vcfcf_core.importer import views as _views
    real = _views.map_view

    def boom(elem, location):
        if elem.get("id") == V_TREND:
            raise KeyError("probe")
        return real(elem, location)
    monkeypatch.setattr(_views, "map_view", boom)
    rc, text = _run(source, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--allow-partial")
    assert rc == 5, text
    assert f"INTERNAL ERROR view {V_TREND} 'Probe Trend': internal error in the converter: KeyError" in text
    assert "View - Set.xml" in text
    assert "Traceback" not in text
    # the other objects are still converted and reported; the internal
    # error is counted in its own column
    assert re.search(r"^  view\s+4\s+3\s+\d+\s+\d+\s+0\s+1\s+0$", text, re.M), text


# ======================================================================= B5
def _repo_with_factory_view(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "content" / "views").mkdir(parents=True)
    (repo / "content" / "views" / "f.yaml").write_text(textwrap.dedent(SOURCE_YAML["v_lone.yaml"]).replace(
        V_LONE, "7a000000-0000-4000-8000-0000000000f1").replace("Probe Unreferenced", "'[VCF CF] Probe Factory View'"))
    return repo


def _project_with_report(repo: Path, sections: list, cross_views=()) -> Path:
    proj = repo / "third_party" / "b5"
    (proj / "views").mkdir(parents=True)
    (proj / "reports").mkdir()
    (proj / "views" / "v.yaml").write_text(textwrap.dedent(SOURCE_YAML["v_trend.yaml"]))
    doc = {"name": "b5", "display_name": "b5", "description": "b5", "factory_native": False, "released": False}
    if cross_views:
        doc["cross_links"] = {"views": list(cross_views)}
    (proj / "PROJECT.yaml").write_text(yaml.safe_dump(doc))
    (proj / "reports" / "r.yaml").write_text(yaml.safe_dump({
        "id": "2e000000-0000-4000-8000-0000000000b5", "name": "Probe B5 Report", "description": "r",
        "subject_types": [{"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "type": "self"}],
        "sections": sections, "settings": {"show_page_footer": True, "output_formats": ["pdf"]}}))
    return proj / "PROJECT.yaml"


@pytest.mark.parametrize("case", ["own", "cross-linked", "both"])
def test_b5_project_report_resolves_own_then_cross_linked_factory_views(tmp_path, monkeypatch, case):
    from vcfcf_packaging.loader import load_bundle
    repo = _repo_with_factory_view(tmp_path)
    own = {"type": "View", "view": "Probe Trend", "orientation": "Portrait"}
    factory = {"type": "View", "view": "[VCF CF] Probe Factory View", "orientation": "Portrait"}
    sections = {"own": [own], "cross-linked": [factory], "both": [own, factory]}[case]
    manifest = _project_with_report(repo, sections, cross_views=["[VCF CF] Probe Factory View"])
    monkeypatch.chdir(repo)
    b = load_bundle(manifest)
    got = [s.view_id for s in b.reports[0].sections]
    want = {"own": [V_TREND], "cross-linked": ["7a000000-0000-4000-8000-0000000000f1"],
            "both": [V_TREND, "7a000000-0000-4000-8000-0000000000f1"]}[case]
    assert got == want


# ======================================================================= W4
def test_w4_whitespace_names_are_recorded_renames_and_collide_normalized(source, tmp_path, capsys):
    src = _copy(source, tmp_path)
    _sub(src / "reports" / "View - Set.xml", r"<Title>Probe Trend</Title>", "<Title>Probe Trend  </Title>")
    out = tmp_path / "o"
    rc, text = _run(src, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 0, text
    assert "RENAMED view 'Probe Trend  ' -> 'Probe Trend' (surrounding whitespace the loader strips)" in text
    row = next(r for r in (out / "import-report" / "id_map.tsv").read_text().splitlines() if r.startswith("view\t" + V_TREND))
    assert row.split("\t")[4] == "Probe Trend  "
    # dashboards too: "X" and "X " collide once the loader strips
    _dash_json(src, lambda d: d.__setitem__("name", "Probe Folder/Probe Dashboard B "))
    _dash_json(src, lambda d: d.__setitem__("namePath", "Probe Folder"), D_B)
    _dash_json(src, lambda d: d.__setitem__("name", "Probe Folder/Probe Dashboard B"), D_B)
    rc, text = _run(src, tmp_path / "o2", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 1 and "2 dashboards share the name 'Probe Dashboard B' once the loader strips whitespace" in text


# ======================================================================= W5
def test_w5_mint_is_repeatable_and_records_the_namespace(source, tmp_path, capsys):
    ids = []
    for n in (1, 2):
        out = tmp_path / f"o{n}"
        rc, text = _run(source, out, capsys, "--layout", "third-party", "--project-name", "probe-port", "--ids",
                        "mint", "--naming", "unprefixed")
        assert rc == 0, text
        tsv = (out / "import-report" / "id_map.tsv").read_text()
        assert tsv.startswith("# mint-namespace: project:probe-port (uuid ")
        ids.append(tsv)
    assert ids[0] == ids[1]
    rc, text = _run(source, tmp_path / "o3", capsys, "--layout", "third-party", "--ids", "mint", "--mint-namespace",
                    "other", "--naming", "unprefixed")
    assert rc == 0 and (tmp_path / "o3" / "import-report" / "id_map.tsv").read_text() != ids[0]
    rc, text = _run(source, tmp_path / "o4", capsys, "--layout", "pak", "--ids", "mint", "--naming", "unprefixed")
    assert rc == 2 and "--mint-namespace" in text


# ================================================================== W6 / W7
def test_w6_a_write_failure_leaves_the_target_untouched(source, tmp_path, capsys, monkeypatch):
    from vcfcf_extractor import importer as I
    real = I._write_tree

    def half(plan, root, args, out, report_inside):
        (root / "views").mkdir(parents=True)
        (root / "views" / "partial.yaml").write_text("x: 1\n")
        raise PermissionError("probe: read-only")
    monkeypatch.setattr(I, "_write_tree", half)
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 2 and "nothing written to" in text and "PermissionError" in text
    assert not out.exists()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".out.import-local-")], "staging left behind"
    monkeypatch.setattr(I, "_write_tree", real)


def test_w6_a_failed_run_writes_nothing_and_says_so(source, tmp_path, capsys):
    src = _copy(source, tmp_path)
    _sub(src / "reports" / "View - Set.xml", r'(<ViewDef id="%s")' % V_TREND, r'\1 extra="1"')
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 1 and not out.exists() and "nothing written to" in text
    rc, text = _run(src, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--allow-partial")
    assert rc == 0 and out.exists() and "probe-trend.yaml" not in _files(out, "views")


# ======================================================================= W8
def test_w8_unsupported_types_are_listed_per_object_and_fail_the_run(source, tmp_path, capsys):
    src = _copy(source, tmp_path)
    (src / "customgroups").mkdir()
    (src / "customgroups" / "customgroups.json").write_text(json.dumps({"customGroups": [
        {"name": "Probe Group", "resourceKind": "Environment", "adapterKind": "Container",
         "membershipDefinition": {"ruleGroups": []}}], "customGroupTypes": []}))
    (src / "policies").mkdir()
    (src / "policies" / "policies.xml").write_text(
        '<PolicyContent><Policies><Policy key="p1" name="Probe Policy"><PackageSettings/></Policy>'
        '</Policies></PolicyContent>')
    rc, text = _run(src, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 1
    assert "NOT CONVERTED (unsupported type) custom group" in text and "'Probe Group'" in text
    assert "NOT CONVERTED (unsupported type) policy p1 'Probe Policy'" in text
    assert text.count("policies.xml") == 1, "the policy file is listed once (nit 6)"
    rc, text = _run(src, tmp_path / "o2", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--allow-partial")
    assert rc == 0, text


# ====================================================================== W10
def test_w10_report_dir_dry_run_and_project_name(source, tmp_path, capsys):
    out, rep = tmp_path / "out", tmp_path / "rep"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--dry-run")
    assert rc == 0 and not out.exists() and "dry run: nothing written, nothing verified" in text
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--report-dir", rep, "--project-name", "probe-named")
    assert rc == 0, text
    assert yaml.safe_load((out / "PROJECT.yaml").read_text())["name"] == "probe-named"
    assert (rep / "report.json").exists() and (rep / "id_map.tsv").exists() and not (out / "import-report").exists()
    assert json.loads((rep / "report.json").read_text())["verify"]["identical"] == 14
    # nit 3: a --report-dir holding files import-local did not write is refused
    other = tmp_path / "other"
    other.mkdir()
    (other / "report.json").write_text("{}")
    rc, text = _run(source, tmp_path / "out2", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--report-dir", other)
    assert rc == 2 and "did not write" in text and (other / "report.json").read_text() == "{}"
    # its own report dir is rewritten on the next run
    rc, text = _run(source, tmp_path / "out3", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--report-dir", rep)
    assert rc == 0, text


def test_no_verify_warns_and_a_loss_still_fails_without_allow_partial(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "v.xml").write_text(_lossy_view_xml("Probe Lossy NV", "7a000000-0000-4000-8000-0000000000c1"))
    rc, text = _run(src, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--no-verify")
    assert rc == 1 and "WARNING: --no-verify: nothing was checked" in text
    rc, text = _run(src, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--no-verify", "--allow-partial")
    assert rc == 0, text


# ===================================================================== nits
def test_nits_reserved_names_json_duplicates_encodings_doctype(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    y = _load_yaml(SOURCE_YAML["v_lone.yaml"].replace("Probe Unreferenced", "CON"), tmp_path, "con.yaml")
    (src / "con.xml").write_text(render_views_xml([load_view(y, enforce_framework_prefix=False)]))
    (src / "dup.json").write_text('{"dashboards": [], "name": "a", "name": "b"}')
    latin = render_views_xml([load_view(_load_yaml(SOURCE_YAML["v_trend.yaml"].replace("Probe Trend", "Probe Trend é"),
                                                  tmp_path, "l.yaml"), enforce_framework_prefix=False)])
    latin = re.sub(r"^\s*<\?xml[^>]*\?>", "", latin)
    (src / "latin.xml").write_bytes(('<?xml version="1.0" encoding="ISO-8859-1"?>' + latin).encode("latin-1"))
    (src / "dtd.xml").write_text('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><Content><Views>'
                                 '<ViewDef id="7a000000-0000-4000-8000-0000000000dd"><Title>&a;</Title></ViewDef>'
                                 '</Views></Content>')
    out = tmp_path / "o"
    rc, text = _run(src, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--allow-partial")
    assert rc == 1  # unreadable inputs are never accepted
    assert "dup.json: JSON with the object key 'name' twice" in text
    assert "dtd.xml: XML with a DOCTYPE or entity declaration, refused before parsing" in text
    assert not any("latin.xml" in ln for ln in text.splitlines() if ln.startswith("CANNOT READ"))
    assert re.search(r"^  view\s+2\s+2\s", text, re.M), "the ISO-8859-1 view is read by its declared encoding"
    assert "file name: the name slugs to 'con', a name Windows reserves; written as con-view.yaml" in text


def test_nit_rename_is_keyed_by_type(source, tmp_path, capsys):
    r = tmp_path / "rename.tsv"
    r.write_text("dashboard\tProbe Host List\tProbe Renamed\n")  # a view's name, keyed as a dashboard
    out = tmp_path / "o"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--rename", r)
    assert rc == 0, text
    assert _yaml(out, "views/probe-host-list.yaml")["name"] == "Probe Host List"
    assert "rename file: dashboard 'Probe Host List' names no object in the input" in text
    r.write_text("widget\tX\tY\n")
    rc, text = _run(source, tmp_path / "o2", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--rename", r)
    assert rc == 2 and "type 'widget' is not one of" in text


def test_nit_folder_text_lands_on_the_folder_deviation(source, tmp_path, capsys):
    src = _copy(source, tmp_path)

    def no_folder(d):
        d["name"] = "Probe Dashboard A"  # namePath stays "Probe Folder"
        d.pop("widgetInteractions")
    _dash_json(src, no_folder)
    rc, text = _run(src, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--target-min", "8.18.7", "--allow-partial")
    lines = [ln for ln in text.splitlines() if ln.startswith("TARGET 8.18.7: dashboards/probe-dashboard-a.yaml")]
    assert any("folder_in_name" in ln and "carries its folder" in ln for ln in lines)
    assert not any("folder_in_name" not in ln and "carries its folder" in ln for ln in lines)


def test_nit_widget_id_placeholder_is_counted(source, tmp_path, capsys):
    src = _copy(source, tmp_path)
    _dash_json(src, lambda d: d["widgets"][0]["config"].__setitem__("widgetId", d["widgets"][0]["id"]))
    rc, text = _run(src, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 0, text
    assert "renumbered ids (config.widgetId, compared as its position token)" in text


# ====================================================== mutation self-test
def _lossy_view_xml(name: str, vid: str) -> str:
    """A list view whose column 0 has an empty preferredUnitId (a recorded
    loss) and whose column 1 has a unit."""
    col = ('<Item><Value><Property name="objectType" value="RESOURCE"/><Property name="attributeKey" value="{k}"/>'
           '<Property name="preferredUnitId" value="{u}"/><Property name="isStringAttribute" value="false"/>'
           '<Property name="adapterKind" value="VMWARE"/><Property name="resourceKind" value="HostSystem"/>'
           '<Property name="rollUpType" value="AVG"/><Property name="rollUpCount" value="1"/>'
           '<Property name="transformations"><List><Item value="CURRENT"/></List></Property>'
           '<Property name="isProperty" value="false"/><Property name="displayName" value="{d}"/>'
           '<Property name="addTimestampAsColumn" value="false"/><Property name="isShowRelativeTimestamp" value="false"/>'
           '</Value></Item>')
    return (f'<Content><Views><ViewDef id="{vid}"><Title>{name}</Title><Description/>'
            '<SubjectType adapterKind="VMWARE" resourceKind="HostSystem" type="descendant"/>'
            '<SubjectType adapterKind="VMWARE" resourceKind="HostSystem" type="self"/>'
            '<Usage>dashboard</Usage><Usage>report</Usage><Usage>details</Usage><Usage>content</Usage>'
            '<Controls><Control id="t" type="time-interval-selector" visible="false">'
            '<Property name="advancedTimeMode" value="false"/><Property name="unit" value="HOURS"/>'
            '<Property name="count" value="24"/></Control>'
            '<Control id="a" type="attributes-selector" visible="false"><Property name="attributeInfos"><List>'
            + col.format(k="cpu|x", u="", d="X") + col.format(k="cpu|y", u="percent", d="Y") +
            '</List></Property></Control>'
            '<Control id="p" type="pagination-control" visible="true"><Property name="start" value="0"/>'
            '<Property name="size" value="500"/></Control>'
            '<Control id="m" type="metadata" visible="false"><Property name="maxPointsCount" value="5000"/>'
            '<Property name="hideObjectNameColumn" value="false"/><Property name="listTopResultSize" value="-1"/>'
            '<Property name="includeResourceCreationTime" value="false"/></Control></Controls>'
            '<DataProviders><DataProvider dataType="list-view" id="l"/></DataProviders>'
            '<Presentation type="list"/></ViewDef></Views></Content>')


LOSSY = "7a000000-0000-4000-8000-0000000000c0"
D_NOINT = "1d000000-0000-4000-8000-0000000000c0"


@pytest.fixture(scope="module")
def mutation_source(tmp_path_factory) -> Path:
    """The shared source, plus a view with a recorded loss and a dashboard
    with no widgetInteractions key (a target-version deviation under
    --target-min 8.18.7)."""
    tmp = tmp_path_factory.mktemp("import_local_mutations")
    src = _build_source(tmp)
    (src / "reports" / "Lossy.xml").write_text(_lossy_view_xml("Probe Lossy", LOSSY))
    p = _load_yaml(f"""
        id: {D_NOINT}
        name: Probe No Interactions
        description: no interactions key
        name_path: ""
        shared: false
        widgets:
          - {{id: a, type: TextDisplay, title: A, html: "<b>a</b>", coords: {{x: 1, y: 1, w: 6, h: 2}}}}
          - {{id: b, type: TextDisplay, title: B, html: "<b>b</b>", coords: {{x: 7, y: 1, w: 6, h: 2}}}}
    """, tmp, "noint.yaml")
    env = json.loads(render_dashboards_bundle_json([load_dashboard(p, enforce_framework_prefix=False,
                                                                   default_name_path="")], {}, "0"))
    env["dashboards"][0].pop("widgetInteractions")
    (src / "dashboards" / "NoInt.json").write_text(json.dumps(env))
    return src


def _convert(src: Path, work: Path, target=None):
    from vcfcf_core.importer.convert import ConvertOptions, plan_conversion
    from vcfcf_core.importer.inputs import scan_inputs
    from vcfcf_extractor import importer as I
    plan = plan_conversion(scan_inputs([src]), ConvertOptions(ids="keep", naming="unprefixed", target_min=target,
                                                               layout="third-party"))
    I._load_check(plan, "third-party", None)
    tree = work / "tree"
    I._write_tree(plan, tree, SimpleNamespace(layout="third-party", project_name="mut", naming="unprefixed"),
                  work / "absent", None)
    return plan, tree


def _status(plan, tree, rel):
    from vcfcf_extractor import importer as I
    v = I._verify(plan, tree, "third-party")
    if v["load_errors"]:
        return "load error"
    return {d["file"]: d["status"] for d in v["objects_detail"]}.get(rel, "not compared")


@pytest.fixture(scope="module")
def converted(mutation_source, tmp_path_factory):
    work = tmp_path_factory.mktemp("mut_base")
    plan, tree = _convert(mutation_source, work, target="8.18.7")
    from vcfcf_extractor import importer as I
    v = I._verify(plan, tree, "third-party")
    base = {d["file"]: d["status"] for d in v["objects_detail"]}
    return plan, tree, base


def _y(fn):
    def m(doc):
        fn(doc)
        return doc
    return m


def _first(items, pred):
    return next(x for x in items if pred(x))


#: (label, written file, mutation of its YAML)
YAML_MUTATIONS = [
    ("view: drop a column", "views/probe-host-list.yaml", _y(lambda d: d["columns"].pop())),
    ("view: change a column unit", "views/probe-host-list.yaml", _y(lambda d: d["columns"][0].update(unit="kb"))),
    ("view: flip a column sort", "views/probe-host-list.yaml", _y(lambda d: d["columns"][0].update(sort="asc"))),
    ("view: change a filter operand", "views/probe-host-list.yaml",
     _y(lambda d: d["subject"]["filter"][0][0].update(value="9.0"))),
    ("view: change a column threshold", "views/probe-host-list.yaml",
     _y(lambda d: d["columns"][0].update(yellow_bound=71))),
    ("view: internal whitespace in the name (unreferenced view)", "views/probe-unreferenced.yaml",
     _y(lambda d: d.update(name="Probe  Unreferenced"))),
    ("view: internal whitespace in a column display_name", "views/probe-unreferenced.yaml",
     _y(lambda d: d["columns"][0].update(display_name="Mem  ory"))),
    ("view beside a recorded loss: change another column's unit", "views/probe-lossy.yaml",
     _y(lambda d: d["columns"][1].update(unit="kb"))),
    ("view: change the time window", "views/probe-host-list.yaml",
     _y(lambda d: d["time_window"].update(count=8))),
    ("dashboard: move a widget", "dashboards/probe-dashboard-a.yaml",
     _y(lambda d: d["widgets"][0]["coords"].update(x=2))),
    ("dashboard: change a widget title", "dashboards/probe-dashboard-a.yaml",
     _y(lambda d: d["widgets"][2].update(title="Note X"))),
    ("dashboard: change TextDisplay html", "dashboards/probe-dashboard-a.yaml",
     _y(lambda d: d["widgets"][2].update(html="<b>x</b>"))),
    ("dashboard: invent an interaction (no deviation)", "dashboards/probe-dashboard-a.yaml",
     _y(lambda d: d["interactions"].append({"from": "w2", "to": "w0", "type": "resourceId"}))),
    ("dashboard with a widget_interactions deviation: invent an interaction", "dashboards/probe-no-interactions.yaml",
     _y(lambda d: d.update(interactions=[{"from": "w0", "to": "w1", "type": "resourceId"}]))),
    ("dashboard: retarget a navigation", "dashboards/probe-dashboard-a.yaml",
     _y(lambda d: d["widgets"][0]["navigations"][1].update(dashboard_id="1d000000-0000-4000-8000-0000000000ff"))),
    ("dashboard: change a widget ui height", "dashboards/probe-dashboard-a.yaml",
     _y(lambda d: d["widgets"][0]["ui"].update(height=325))),
    ("alert: drop a symptom", "alerts/probe-host-alert.yaml",
     _y(lambda d: d["symptom_sets"]["sets"][0]["symptoms"].pop())),
    ("alert: change a recommendation priority", "alerts/probe-host-alert.yaml",
     _y(lambda d: d["recommendations"][0].update(priority=2))),
    ("symptom: change the threshold", "symptoms/probe-cpu-high.yaml",
     _y(lambda d: d["condition"].update(value=91))),
    ("symptom: change wait_cycles", "symptoms/probe-powered-off.yaml", _y(lambda d: d.update(wait_cycles=5))),
    ("super metric: change the formula", "supermetrics/probe-sm-one.yaml",
     _y(lambda d: d.update(formula="(" + d["formula"] + ") * 2"))),
    ("report: flip a section orientation", "reports/probe-report.yaml",
     _y(lambda d: d["sections"][2].update(orientation="Landscape"))),
    ("report: flip a section colorize", "reports/probe-report.yaml",
     _y(lambda d: d["sections"][2].update(colorize=False))),
    ("report: swap a section's view", "reports/probe-report.yaml",
     _y(lambda d: d["sections"][2].update(view="Probe Trend"))),
]


@pytest.mark.parametrize("label,rel,mutate", YAML_MUTATIONS, ids=[m[0] for m in YAML_MUTATIONS])
def test_mutation_of_a_written_yaml_is_reported(converted, tmp_path, label, rel, mutate):
    plan, tree, base = converted
    assert base[rel] in ("identical", "identical apart from forced target keys", "differs only at recorded losses")
    work = tmp_path / "tree"
    shutil.copytree(tree, work)
    p = work / rel
    p.write_text(yaml.safe_dump(mutate(yaml.safe_load(p.read_text())), sort_keys=False, allow_unicode=True))
    assert _status(plan, work, rel) not in ("identical", "identical apart from forced target keys",
                                            "differs only at recorded losses"), label


def _view_xml(rx, repl, vid=V_DIST):
    def m(root):
        _sub(root / "reports" / "View - Set.xml", r'(<ViewDef id="%s".*?)' % vid + rx, r"\1" + repl)
    return m


def _dash(fn):
    return lambda root: _dash_json(root, fn)


#: (label, object type and id, mutation of the source tree)
SOURCE_MUTATIONS = [
    ("view: extra attribute on ViewDef", ("view", V_DIST),
     lambda r: _sub(r / "reports" / "View - Set.xml", r'<ViewDef id="%s"' % V_DIST, f'<ViewDef extra="1" id="{V_DIST}"')),
    ("view: extra attribute on DataProvider", ("view", V_DIST), _view_xml(r"<DataProvider ", '<DataProvider extra="1" ')),
    ("view: extra attribute on a column Item", ("view", V_DIST),
     _view_xml(r'(<Property name="attributeInfos"><List>)<Item>', r'\2<Item extra="1">'.replace(r"\2", r"\2"))),
    ("view: extra attribute on a Usage element", ("view", V_DIST), _view_xml(r"<Usage>", '<Usage extra="1">')),
    ("view: extra attribute on Title", ("view", V_DIST), _view_xml(r"<Title>", '<Title extra="1">')),
    ("view: localizationKey on a column displayName Property", ("view", V_DIST),
     _view_xml(r'<Property name="displayName"', '<Property localizationKey="k" name="displayName"')),
    ("view: an attribute other than value on a control Property", ("view", V_DIST),
     _view_xml(r'<Property name="unit"', '<Property extra="1" name="unit"')),
    ("view: Control visible flipped", ("view", V_DIST),
     _view_xml(r'type="time-interval-selector" visible="false"', 'type="time-interval-selector" visible="true"')),
    ("view: a second time-interval-selector control", ("view", V_DIST),
     _view_xml(r"(<Controls>)", r'\2<Control id="x" type="time-interval-selector" visible="false">'
                                '<Property name="unit" value="DAYS"/><Property name="count" value="3"/>'
                                '<Property name="advancedTimeMode" value="false"/></Control>')),
    ("view: Description with trailing whitespace", ("view", V_DIST),
     _view_xml(r"<Description>dist</Description>", "<Description>dist </Description>")),
    ("dashboard: widget config.refreshInterval", ("dashboard", D_A),
     _dash(lambda d: d["widgets"][0]["config"].update(refreshInterval=999))),
    ("dashboard: View widget config.isUpdatedView", ("dashboard", D_A),
     _dash(lambda d: d["widgets"][0]["config"].update(isUpdatedView=False))),
    ("dashboard: navigation interactionType", ("dashboard", D_A),
     _dash(lambda d: next(iter(d["dashboardNavigations"].values()))[0]["widgets"][0].update(interactionType="metricKey"))),
    ("dashboard: config.title differing from the title", ("dashboard", D_A),
     _dash(lambda d: d["widgets"][0]["config"].update(title="Other"))),
    ("dashboard: config.widgetId of another widget", ("dashboard", D_A),
     _dash(lambda d: d["widgets"][0]["config"].update(widgetId=d["widgets"][1]["id"]))),
    ("dashboard: an unknown dashboard key", ("dashboard", D_A), _dash(lambda d: d.update(probeKey=1))),
    ("dashboard: a customFilter excluded resource", ("dashboard", D_A),
     _dash(lambda d: d["widgets"][1]["config"]["customFilter"].update(excludedResources=["x"]))),
    ("report: CoverPage ContentKey changed", ("report", "2e000000-0000-4000-8000-000000000001"),
     lambda r: _sub(r / "reports" / "Report.xml", r"<ContentKey>COVER_PAGE</ContentKey>", "<ContentKey>OTHER</ContentKey>")),
    ("symptom: an extra Condition attribute", ("symptom", "SymptomDefinition-" + "3c000000-0000-4000-8000-000000000002"),
     lambda r: _sub(r / "alertdefs" / "Alert.xml", r'(<SymptomDefinition [^>]*id="SymptomDefinition-3c000000-0000-4000-'
                                                    r'8000-000000000002"[^>]*>\s*<State[^>]*>\s*<Condition )', r'\1extra="1" ')),
    ("super metric: an unknown key", ("supermetric", SM2),
     lambda r: (lambda p, j: p.write_text(json.dumps({**j, SM2: {**j[SM2], "probeKey": 1}})))(
         r / "supermetrics" / "SMs.json", json.loads((r / "supermetrics" / "SMs.json").read_text()))),
]


@pytest.mark.parametrize("label,obj,mutate", SOURCE_MUTATIONS, ids=[m[0] for m in SOURCE_MUTATIONS])
def test_mutation_of_a_source_is_reported(mutation_source, tmp_path, label, obj, mutate):
    from vcfcf_core.importer.convert import norm_id
    src = tmp_path / "src"
    shutil.copytree(mutation_source, src)
    mutate(src)
    plan, tree = _convert(src, tmp_path)
    t, oid = obj
    failed = [f for f in plan.failures if f.type == t and norm_id(t, f.id) == norm_id(t, oid)]
    if failed:
        assert failed[0].kind == "failed" and failed[0].gap, f"{label}: failed without a TOOLSET GAP: {failed[0].reason}"
        return
    e = next(e for e in plan.emitted if e.type == t and norm_id(t, e.source_id) == norm_id(t, oid))
    assert _status(plan, tree, e.relpath) not in ("identical", "identical apart from forced target keys"), label


def test_mutation_source_name_whitespace_is_a_recorded_rename(mutation_source, tmp_path):
    src = tmp_path / "src"
    shutil.copytree(mutation_source, src)
    _sub(src / "reports" / "View - Set.xml", r"<Title>Probe Distribution</Title>", "<Title> Probe Distribution</Title>")
    plan, tree = _convert(src, tmp_path)
    e = next(e for e in plan.emitted if e.source_id == V_DIST)
    assert e.rename_reasons == ["surrounding whitespace the loader strips"] and e.source_name == " Probe Distribution"


# ================================================================ W3 (walker consumers)
def _w3_dashboard(path: Path, name: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({
        "id": "1d000000-0000-4000-8000-0000000000e3", "name": name, "description": "w3", "shared": False,
        "widgets": [
            {"id": "stock", "type": "View", "title": "Stock", "view": STOCK_VIEW_ID,
             "coords": {"x": 1, "y": 1, "w": 6, "h": 4}},
            {"id": "unknown", "type": "View", "title": "Unknown", "view": UNKNOWN_VIEW,
             "coords": {"x": 7, "y": 1, "w": 6, "h": 4}},
        ]}, sort_keys=False))
    return path


def _assert_w3(err: str) -> None:
    assert "PREREQUISITE" in err and UNKNOWN_VIEW in err and STOCK_VIEW_ID in err
    assert f"{UNKNOWN_VIEW} is not a known VCF Operations stock view id" in err
    assert f"{STOCK_VIEW_ID} is not a known" not in err


def test_w3_walker_records_external_views_with_where():
    from vcfcf_common.dep_walker import collect_deps
    from vcfcf_core.dashboards.loader import load_dashboard as _ld
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        dash = _ld(_w3_dashboard(Path(d) / "d.yaml", "Probe W3"), enforce_framework_prefix=False, default_name_path="")
        g = collect_deps([dash], [], [], [])
    assert [(t, i) for t, i, _ in g.external_views] == [("view", STOCK_VIEW_ID), ("view", UNKNOWN_VIEW)]
    assert all("dashboard 'Probe W3'" in w for _, _, w in g.external_views)


def test_w3_navigation_closure_reports_external_views(tmp_path, capsys):
    from vcfcf_packaging.navigation import navigation_closure
    dash = load_dashboard(_w3_dashboard(tmp_path / "d.yaml", "Probe W3"), enforce_framework_prefix=False,
                          default_name_path="")
    navigation_closure([dash], [dash], [], [], [])
    _assert_w3(capsys.readouterr().err)


def test_w3_composer_reports_external_views(tmp_path, capsys):
    from vcfcf_packaging.composer import _check_deps, discover_components
    _w3_dashboard(tmp_path / "content" / "dashboards" / "d.yaml", "[VCF CF] Probe W3")
    entries = discover_components(tmp_path, "dashboards")
    ext: list = []
    assert _check_deps(entries, [], [], [], tmp_path, external_views=ext) == []
    assert [i for _, i, _ in ext] == [STOCK_VIEW_ID, UNKNOWN_VIEW]
    from vcfcf_packaging.navigation import print_external_view_prerequisites
    print_external_view_prerequisites(ext, "the composed bundle")
    _assert_w3(capsys.readouterr().err)


@pytest.mark.slow
def test_w3_bundle_builder_reports_external_views(tmp_path, monkeypatch, capsys):
    from vcfcf_packaging.builder import build_bundle
    _w3_dashboard(tmp_path / "content" / "dashboards" / "d.yaml", "[VCF CF] Probe W3")
    (tmp_path / "bundles").mkdir()
    (tmp_path / "bundles" / "w3.yaml").write_text(yaml.safe_dump(
        {"name": "w3", "description": "w3", "dashboards": ["content/dashboards/d.yaml"]}))
    monkeypatch.chdir(tmp_path)
    build_bundle(tmp_path / "bundles" / "w3.yaml", tmp_path / "dist", skip_audit=True, live_describe=False)
    _assert_w3(capsys.readouterr().err)


@pytest.mark.slow
def test_w3_discrete_and_release_builders_report_external_views(tmp_path, monkeypatch, capsys):
    from vcfcf_packaging.discrete_builder import build_discrete
    from vcfcf_packaging.release_builder import build_release
    proj = tmp_path / "third_party" / "w3proj"
    d = _w3_dashboard(proj / "dashboards" / "d.yaml", "Probe W3")
    (proj / "PROJECT.yaml").write_text(yaml.safe_dump({"name": "w3proj", "factory_native": False}))
    monkeypatch.chdir(tmp_path)
    build_discrete("dashboard", "Probe W3", tmp_path / "dist", extra_search_dirs=[proj], skip_audit=True,
                   live_describe=False)
    _assert_w3(capsys.readouterr().err)
    manifest = tmp_path / "w3-release.yaml"
    manifest.write_text(yaml.safe_dump({"name": "w3-release", "version": "1.0", "description": "w3",
                                        "artifacts": [{"source": str(d.resolve()), "headline": True}]}))
    build_release(manifest, tmp_path / "rel", skip_audit=True)
    _assert_w3(capsys.readouterr().err)
