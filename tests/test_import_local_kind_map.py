"""``import-local --map-kind`` and ``--describe`` through the real CLI.

The sources are rendered by the factory's own renderers from synthetic YAML
on a made-up adapter kind (``ProbeOld``, resource kinds ``Probe Library`` and
``Probe Item``), mapped to ``probe_new``; nothing is copied from third-party or
product content. ``ProbeOld`` also appears where it is NOT a kind (a metric key
segment ``ProbeOld|size``, names, descriptions, a super metric description
quoting the formula), to prove the map never text-replaces.

How-to: knowledge/context/authoring/importer_offline_conversion.md
§Re-pointing kinds and §Replacing descriptions.
"""
from __future__ import annotations

import hashlib
import json
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from vcfcf_core.alerts.loader import load_file as load_alert, load_recommendation_file
from vcfcf_core.alerts.render import render_alert_content_xml
from vcfcf_core.dashboards.loader import load_dashboard, load_view
from vcfcf_core.dashboards.render import render_dashboards_bundle_json, render_views_xml
from vcfcf_core.importer.kinds import KindMap, parse_kind_map
from vcfcf_core.packaging.assembly import _render_supermetrics_dict
from vcfcf_core.reports.loader import load_file as load_report
from vcfcf_core.reports.render import render_report_xml
from vcfcf_core.supermetrics.loader import load_file as load_sm
from vcfcf_core.symptoms.loader import load_file as load_sym

OLD, NEW = "ProbeOld", "probe_new"
SM_K = "5e000000-0000-4000-8000-0000000000a1"
SM_V = "5e000000-0000-4000-8000-0000000000a2"
SM_STAR = "5e000000-0000-4000-8000-0000000000a3"
V_LIB = "7a000000-0000-4000-8000-0000000000a1"
V_VM = "7a000000-0000-4000-8000-0000000000a2"
V_TWO = "7a000000-0000-4000-8000-0000000000a3"
D_K = "1d000000-0000-4000-8000-0000000000a1"
R_K = "2e000000-0000-4000-8000-0000000000a1"
Y_K = "3c000000-0000-4000-8000-0000000000a1"
A_K = "4a000000-0000-4000-8000-0000000000a1"
DERIVED_SYM = f"SymptomDefinition-{OLD}-Probe_Derived_Symptom"
DERIVED_ALERT = f"AlertDefinition-{OLD}-Probe_Derived_Alert"
SM_FORMULA = f"sum(${{adaptertype={OLD}, objecttype=Probe Item, metric={OLD}|size, depth=1}})"
SM_DESC = f"Sums {OLD}|size over items: adaptertype={OLD} in the formula"

SOURCES = {
    "sm_k.yaml": f"""
        id: {SM_K}
        name: Probe Kind SM
        formula: '{SM_FORMULA}'
        description: '{SM_DESC}'
        resource_kinds: [{{resource_kind_key: Probe Library, adapter_kind_key: {OLD}}}]
    """,
    "sm_v.yaml": f"""
        id: {SM_V}
        name: Probe VMware SM
        formula: avg(${{this, metric=cpu|usage_average}})
        description: untouched
        resource_kinds: [{{resource_kind_key: HostSystem, adapter_kind_key: VMWARE}}]
    """,
    "sm_star.yaml": f"""
        id: {SM_STAR}
        name: Probe Star SM
        formula: count(${{adaptertype={OLD}, objecttype=*, metric=badge|health, depth=1}})
        description: every kind
        resource_kinds: [{{resource_kind_key: Probe Library, adapter_kind_key: {OLD}}}]
    """,
    "v_lib.yaml": f"""
        id: {V_LIB}
        name: Probe Library List
        description: Lists {OLD} libraries
        subject: {{adapter_kind: {OLD}, resource_kind: Probe Library}}
        group_by: {{adapter_kind: {OLD}, resource_kind: Probe Item}}
        columns:
          - {{attribute: {OLD}|size, display_name: {OLD} size}}
          - attribute: supermetric:"Probe Kind SM"
            display_name: Kind SM
    """,
    "v_vm.yaml": f"""
        id: {V_VM}
        name: Probe VM List
        description: not on the mapped kind
        subject: {{adapter_kind: VMWARE, resource_kind: VirtualMachine}}
        columns:
          - {{attribute: {OLD}|size, display_name: Pushed by {OLD}}}
    """,
    "v_two.yaml": f"""
        id: {V_TWO}
        name: Probe Two Kinds
        description: two subjects
        subjects:
          - {{adapter_kind: {OLD}, resource_kind: Probe Library}}
          - {{adapter_kind: {OLD}, resource_kind: Probe Item}}
        columns:
          - {{attribute: badge|health, display_name: Health}}
    """,
    "d_k.yaml": f"""
        id: {D_K}
        name: Probe Kind Dashboard
        description: The {OLD} dashboard
        name_path: ""
        shared: false
        widgets:
          - id: lib
            type: View
            title: {OLD} libraries
            view: Probe Library List
            coords: {{x: 1, y: 1, w: 6, h: 4}}
            self_provider: true
            pin: {{adapter_kind: {OLD}, resource_kind: Probe Library, name: Main Library}}
          - id: score
            type: Scoreboard
            title: Score
            coords: {{x: 7, y: 1, w: 6, h: 4}}
            metrics:
              - {{adapter_kind: {OLD}, resource_kind: Probe Item, metric_key: {OLD}|size, metric_name: {OLD} size}}
              - {{adapter_kind: VMWARE, resource_kind: HostSystem, metric_key: cpu|usage_average, metric_name: CPU}}
          - id: items
            type: ResourceList
            title: Items
            coords: {{x: 1, y: 5, w: 6, h: 4}}
            resource_kinds: [{{adapter_kind: {OLD}, resource_kind: Probe Item}}]
          - id: alerts
            type: AlertList
            title: Alerts
            coords: {{x: 7, y: 5, w: 6, h: 4}}
            alert_definitions: [{DERIVED_ALERT}]
          - id: note
            type: TextDisplay
            title: Note
            html: "<b>{OLD} notes</b>"
            coords: {{x: 1, y: 9, w: 12, h: 2}}
    """,
    "r_k.yaml": f"""
        id: {R_K}
        name: Probe Kind Report
        description: report on {OLD}
        subject_types: [{{adapter_kind: {OLD}, resource_kind: Probe Library, type: self}}]
        sections:
          - {{type: CoverPage, colorize: false, font_color: "000000"}}
          - {{type: View, view: Probe Library List, orientation: Portrait}}
        settings: {{show_page_footer: true, output_formats: [pdf]}}
    """,
    "y_k.yaml": f"""
        id: {Y_K}
        name: Probe Library Big
        adapter_kind: {OLD}
        resource_kind: Probe Library
        severity: WARNING
        wait_cycles: 2
        cancel_cycles: 2
        condition: {{type: metric_static, key: {OLD}|size, operator: GT, value: 90, instanced: false}}
    """,
    "y_d.yaml": f"""
        name: Probe Derived Symptom
        adapter_kind: {OLD}
        resource_kind: Probe Item
        severity: CRITICAL
        wait_cycles: 2
        cancel_cycles: 2
        condition: {{type: metric_static, key: {OLD}|size, operator: GT, value: 1, instanced: false}}
    """,
    "k_1.yaml": """
        name: probeKindRec
        id: probeKindRec
        description: Check the library.
        adapter_kind: ProbeOld
    """,
    "a_k.yaml": f"""
        id: {A_K}
        name: Probe Library Alert
        description: The {OLD} library is big
        adapter_kind: {OLD}
        resource_kind: Probe Library
        type: 16
        sub_type: 19
        criticality: SYMPTOM_BASED
        impact: {{badge: HEALTH}}
        symptom_sets:
          operator: ALL
          sets:
            - {{defined_on: SELF, operator: ALL, symptoms: [{{name: Probe Library Big}}]}}
        recommendations: [{{name: probeKindRec, priority: 1}}]
    """,
    "a_d.yaml": f"""
        name: Probe Derived Alert
        description: derived ids
        adapter_kind: {OLD}
        resource_kind: Probe Item
        type: 16
        sub_type: 19
        criticality: SYMPTOM_BASED
        impact: {{badge: HEALTH}}
        symptom_sets:
          operator: ALL
          sets:
            - {{defined_on: SELF, operator: ALL, symptoms: [{{name: Probe Derived Symptom}}]}}
    """,
}


def _write_yaml(d: Path, sources: dict) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for name, text in sources.items():
        (d / name).write_text(textwrap.dedent(text).lstrip())


def build_source(tmp: Path, sources: dict = None, skip=()) -> Path:
    """Render the synthetic YAML into product-shaped source files."""
    srcs = {k: v for k, v in (sources or SOURCES).items() if k not in skip}
    y = tmp / "authored"
    _write_yaml(y, srcs)
    ld = dict(enforce_framework_prefix=False)
    sms = [load_sm(y / f, **ld) for f in sorted(srcs) if f.startswith("sm_")]
    views = [load_view(y / f, **ld) for f in sorted(srcs) if f.startswith("v_")]
    dashes = [load_dashboard(y / f, default_name_path="", **ld) for f in sorted(srcs) if f.startswith("d_")]
    by_name = {v.name: v for v in views}
    vd, dd = tmp / "idx_views", tmp / "idx_dashes"
    vd.mkdir()
    dd.mkdir()
    for v in views:
        (vd / f"{v.id}.yaml").write_text(f"id: {v.id}\nname: {v.name}\n")
    for d in dashes:
        (dd / f"{d.id}.yaml").write_text(f"id: {d.id}\nname: {d.name}\n")
    reports = [load_report(y / f, vd, dd, **ld) for f in sorted(srcs) if f.startswith("r_")]
    syms = [load_sym(y / f, **ld) for f in sorted(srcs) if f.startswith("y_")]
    recs = [load_recommendation_file(y / f, **ld) for f in sorted(srcs) if f.startswith("k_")]
    alerts = [load_alert(y / f, **ld) for f in sorted(srcs) if f.startswith("a_")]
    src = tmp / "source"
    src.mkdir()
    if views:
        (src / "views.xml").write_text(render_views_xml(views, sm_map={s.name: s.id for s in sms}))
    if dashes:
        env = json.loads(render_dashboards_bundle_json(dashes, by_name, "0", known_dashboards=dashes))
        (src / "dashboards.json").write_text(json.dumps(env, indent=2))
    if reports:
        (src / "reports.xml").write_text(render_report_xml(reports))
    if syms or alerts or recs:
        (src / "alerts.xml").write_text(render_alert_content_xml(syms, alerts, recs))
    if sms:
        (src / "sms.json").write_text(json.dumps(_render_supermetrics_dict(type("B", (), {"supermetrics": sms})()),
                                                 indent=2))
    return src


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


def _tsv(tmp: Path, name: str, rows) -> Path:
    p = tmp / name
    p.write_text("".join("\t".join(r) + "\n" for r in rows))
    return p


def _run(src, out, capsys, *extra, layout="third-party", ids=("--ids", "keep"), naming="unprefixed"):
    return _cli(["import-local", src, "--out", out, "--layout", layout, *ids, "--naming", naming, *extra], capsys)


def _y(out: Path, rel: str) -> dict:
    return yaml.safe_load((out / rel).read_text())


def _report(out: Path) -> dict:
    return json.loads((out / "import-report" / "report.json").read_text())


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


STAR_ROW = [(OLD, "*", NEW, "*")]


@pytest.fixture(scope="module")
def source(tmp_path_factory) -> Path:
    # sm_star (objecttype=*) is tested on its own source
    return build_source(tmp_path_factory.mktemp("kind_src"), skip=("sm_star.yaml",))


def _status(rep: dict) -> dict:
    return {d["name"]: d["status"] for d in rep["verify"]["objects_detail"]}


# ------------------------------------------------------------ every type
def test_star_map_repoints_every_type_and_never_text_replaces(source, tmp_path, capsys):
    out = tmp_path / "out"
    before = _tree_hash(source)
    rc, text = _run(source, out, capsys, "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW))
    assert rc == 0, text
    assert _tree_hash(source) == before, "inputs must be read only"
    # super metric: the formula's resource entry and resourceKinds move; the
    # same string in the description and in the metric key segment does not
    sm = _y(out, "supermetrics/probe-kind-sm.yaml")
    assert sm["formula"] == f"sum(${{adaptertype={NEW}, objecttype=Probe Item, metric={OLD}|size, depth=1}})"
    assert sm["description"] == SM_DESC
    assert sm["resource_kinds"] == [{"resource_kind_key": "Probe Library", "adapter_kind_key": NEW}]
    # views: subject, group_by and column bindings; metric keys and labels stay
    v = _y(out, "views/probe-library-list.yaml")
    assert v["subject"]["adapter_kind"] == NEW and v["group_by"]["adapter_kind"] == NEW
    assert v["description"] == f"Lists {OLD} libraries"
    assert v["columns"][0]["attribute"] == f"{OLD}|size" and v["columns"][0]["display_name"] == f"{OLD} size"
    assert [s["adapter_kind"] for s in _y(out, "views/probe-two-kinds.yaml")["subjects"]] == [NEW, NEW]
    assert _y(out, "views/probe-vm-list.yaml")["subject"]["adapter_kind"] == "VMWARE"
    # dashboard: pin, metric entries, resource list kinds, AlertList derived id
    d = _y(out, "dashboards/probe-kind-dashboard.yaml")
    lib, score, items, alerts, note = d["widgets"]  # YAML ids are positions (w0..w4)
    assert lib["pin"]["adapter_kind"] == NEW
    assert [m["adapter_kind"] for m in score["metrics"]] == [NEW, "VMWARE"]
    assert score["metrics"][0]["metric_key"] == f"{OLD}|size"
    assert items["resource_kinds"] == [{"adapter_kind": NEW, "resource_kind": "Probe Item"}]
    assert alerts["alert_definitions"] == [f"AlertDefinition-{NEW}-Probe_Derived_Alert"]
    assert note["html"] == f"<b>{OLD} notes</b>" and d["description"] == f"The {OLD} dashboard"
    assert _y(out, "reports/probe-kind-report.yaml")["subject_types"][0]["adapter_kind"] == NEW
    # symptoms and alerts: kinds; a derived id follows the kind (no id: in the YAML)
    sym = _y(out, "symptoms/probe-derived-symptom.yaml")
    assert sym["adapter_kind"] == NEW and "id" not in sym and sym["condition"]["key"] == f"{OLD}|size"
    al = _y(out, "alerts/probe-derived-alert.yaml")
    assert al["adapter_kind"] == NEW and "id" not in al
    assert _y(out, "alerts/probe-library-alert.yaml")["id"] == A_K
    assert _y(out, "recommendations/probekindrec.yaml")["adapter_kind"] == NEW
    idmap = (out / "import-report" / "id_map.tsv").read_text()
    assert f"symptom\t{DERIVED_SYM}\tSymptomDefinition-{NEW}-Probe_Derived_Symptom\t" in idmap
    assert f"alert\t{DERIVED_ALERT}\tAlertDefinition-{NEW}-Probe_Derived_Alert\t" in idmap
    # per object counts, and the buckets: never "identical" when re-pointed
    assert ("KIND supermetric 'Probe Kind SM': 2 kind reference(s) re-pointed (ProbeOld:Probe Item -> "
            "probe_new:Probe Item; ProbeOld:Probe Library -> probe_new:Probe Library)") in text
    assert "kind map: 1 row(s), 1 used; 9 converted object(s) carry re-pointed kinds, 23 kind reference(s)" in text
    rep = _report(out)
    st = _status(rep)
    assert st["Probe Kind SM"] == st["Probe Kind Dashboard"] == "identical apart from re-pointed kinds"
    assert st["Probe VM List"] == st["Probe VMware SM"] == st["probeKindRec"] == "identical"
    assert rep["verify"]["identical"] == 3 and rep["verify"]["identical_apart_from_intended_changes"] == 9
    assert rep["verify"]["differ"] == 0 and rep["verify"]["differ_only_at_recorded_losses"] == 0
    assert rep["verify"]["intended_changes"] == {"objects_with_repointed_kinds": 9, "kind_references_repointed": 23,
                                                "descriptions_replaced": 0}
    by = {o["name"]: o for o in rep["objects"]}
    assert by["Probe Library List"]["kind_references_repointed"] == 5
    assert by["Probe VM List"]["kind_references_repointed"] == 0
    assert rep["kind_map"]["rows"][0]["map"] == "ProbeOld:* -> probe_new:*"
    assert "9 identical apart from intended changes" in text


def test_pak_snippet_treats_the_mapped_kind_as_the_paks_own(source, tmp_path, capsys):
    rc, text = _run(source, tmp_path / "plain", capsys, layout="pak")
    assert rc == 0, text
    plain = (tmp_path / "plain" / "import-report" / "bundled_content.yaml").read_text()
    assert "content_foreign_adapter_kinds: [ProbeOld]" in plain
    rc, text = _run(source, tmp_path / "mapped", capsys, "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW),
                    layout="pak")
    assert rc == 0, text
    snip = (tmp_path / "mapped" / "import-report" / "bundled_content.yaml").read_text()
    assert f"re-pointed content to {NEW}, taken as the pak's own adapter kind" in snip
    assert "content_foreign_adapter_kinds" not in snip
    # the same body, only the header differs
    assert snip.split("bundled_content:", 1)[1] == plain.split("bundled_content:", 1)[1]


def test_resource_kind_row_wins_over_the_star_row(source, tmp_path, capsys):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--map-kind",
                    _tsv(tmp_path, "k.tsv", STAR_ROW + [(OLD, "Probe Item", NEW, "probe_item")]))
    assert rc == 0, text
    v = _y(out, "views/probe-library-list.yaml")
    assert (v["subject"]["adapter_kind"], v["subject"]["resource_kind"]) == (NEW, "Probe Library")
    assert (v["group_by"]["adapter_kind"], v["group_by"]["resource_kind"]) == (NEW, "probe_item")
    sm = _y(out, "supermetrics/probe-kind-sm.yaml")
    assert f"adaptertype={NEW}, objecttype=probe_item, metric={OLD}|size" in sm["formula"]
    assert _y(out, "alerts/probe-derived-alert.yaml")["resource_kind"] == "probe_item"
    assert _status(_report(out))["Probe Two Kinds"] == "identical apart from re-pointed kinds"


def test_an_unused_row_is_a_warning_and_changes_nothing(source, tmp_path, capsys):
    rc, text = _run(source, tmp_path / "plain", capsys)
    assert rc == 0, text
    rc, text = _run(source, tmp_path / "mapped", capsys, "--map-kind",
                    _tsv(tmp_path, "k.tsv", [("NoSuchKind", "*", NEW, "*")]))
    assert rc == 0, text
    assert "WARNING: kind map: " in text and "NoSuchKind:* -> probe_new:* matches no kind-bearing place" in text
    rep = _report(tmp_path / "mapped")
    assert rep["kind_map"]["rows"][0]["used"] == 0
    for sub in ("views", "dashboards", "reports", "symptoms", "alerts", "recommendations", "supermetrics"):
        assert _tree_hash(tmp_path / "plain" / sub) == _tree_hash(tmp_path / "mapped" / sub)


@pytest.mark.parametrize("rows,needle", [
    ([(OLD, "*", NEW)], "expected old adapter kind<TAB>old resource kind or *"),
    ([(OLD, "*", NEW, "probe_x")], "the new resource kind must be * too"),
    ([(OLD, "*", NEW, "*"), (OLD, "*", "other", "*")], "is already mapped differently by"),
    ([(OLD, "*", NEW, "*"), (OLD, "*", NEW, "*")], "is already mapped the same way by"),
    ([(OLD, "*", OLD, "*")], "maps a kind to itself"),
    ([(OLD, "*", NEW, "*"), (NEW, "*", "third", "*")], "chains and swaps are not supported"),
    ([(OLD, "*", "probe/new", "*")], "which delimits the forms a kind is written in"),
])
def test_bad_map_rows_are_usage_errors(source, tmp_path, capsys, rows, needle):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--map-kind", _tsv(tmp_path, "k.tsv", rows))
    assert rc == 2, text
    assert needle in text
    assert not out.exists()


def test_adapter_kind_alone_needs_an_unambiguous_map(tmp_path, capsys):
    src = build_source(tmp_path / "s", sources={"sm_star.yaml": SOURCES["sm_star.yaml"]})
    # only one resource kind is mapped: objecttype=* cannot be re-pointed
    rc, text = _run(src, tmp_path / "o1", capsys, "--map-kind",
                    _tsv(tmp_path, "k1.tsv", [(OLD, "Probe Library", NEW, "*")]), "--allow-partial")
    assert f"FAILED supermetric {SM_STAR} 'Probe Star SM': kind map: formula entry 1" in text
    assert "is mapped only for some resource kinds" in text and "TOOLSET GAP" in text
    rc, text = _run(src, tmp_path / "o2", capsys, "--map-kind", _tsv(tmp_path, "k2.tsv", STAR_ROW))
    assert rc == 0, text
    assert _y(tmp_path / "o2", "supermetrics/probe-star-sm.yaml")["formula"] == (
        f"count(${{adaptertype={NEW}, objecttype=*, metric=badge|health, depth=1}})")


def test_a_map_that_merges_two_kinds_of_one_object_stops_it(source, tmp_path, capsys):
    rows = [(OLD, "Probe Library", NEW, "one"), (OLD, "Probe Item", NEW, "one")]
    rc, text = _run(source, tmp_path / "out", capsys, "--map-kind", _tsv(tmp_path, "k.tsv", rows))
    assert rc == 1
    assert (f"FAILED view {V_TWO} 'Probe Two Kinds': kind map: the kind map makes ProbeOld:Probe Item, "
            f"ProbeOld:Probe Library the same kind probe_new:one in this view") in text


def test_two_objects_landing_on_one_derived_id_both_fail(tmp_path, capsys):
    def sym(name, kind):
        return f"""
            name: {name}
            adapter_kind: {kind}
            resource_kind: Probe Item
            severity: CRITICAL
            wait_cycles: 2
            cancel_cycles: 2
            condition: {{type: metric_static, key: a|b, operator: GT, value: 1, instanced: false}}
        """
    src = build_source(tmp_path / "s", sources={"y_a.yaml": sym("Probe X", NEW), "y_b.yaml": sym("Probe X!", OLD)})
    rc, text = _run(src, tmp_path / "out", capsys, "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW))
    assert rc == 4, text  # both fail, so verification compares nothing
    assert text.count(f"2 symptoms would ship under the id {NEW.lower()}-probe_x") == 2, text


@pytest.mark.parametrize("key,value,needle", [
    # a key no kind row classifies
    ("viewDetails", f"http://probe.invalid/{OLD}-details", "the value names ProbeOld in a place the importer does not classify"),
    # a traversal spec id (<spec>-<adapter>-<root kind>) is kind-bearing, but
    # the target adapter's specs cannot be known
    ("traversalSpecId", f"Probe Spec-{OLD}-Probe Library", "a traversal spec is declared by an adapter's describe.xml"),
])
def test_a_mapped_kind_the_importer_cannot_repoint_is_a_gap(tmp_path, capsys, key, value, needle):
    src = build_source(tmp_path / "s", sources={k: SOURCES[k] for k in ("sm_k.yaml", "v_lib.yaml", "d_k.yaml")})
    env = json.loads((src / "dashboards.json").read_text())
    env["dashboards"][0]["widgets"][0]["config"][key] = value
    env["dashboards"][0]["widgets"][3]["config"]["alertDefinitions"] = []  # its alert is not in this source
    (src / "dashboards.json").write_text(json.dumps(env))
    rc, text = _run(src, tmp_path / "out", capsys, "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW))
    assert rc == 1
    assert (f"FAILED dashboard {D_K} 'Probe Kind Dashboard': kind map: source key "
            f"widget[0:View].config.{key}: ") in text, text
    assert needle in text
    assert "TOOLSET GAP" in text and f"--map-kind at widget:View.config.{key}" in text
    # without the map the same source converts
    rc, text = _run(src, tmp_path / "plain", capsys)
    assert rc == 0, text


def test_a_literal_equal_to_the_kind_and_a_where_clause_word_are_gaps(tmp_path, capsys):
    srcs = {"y_p.yaml": f"""
        id: {Y_K}
        name: Probe Kind Property
        adapter_kind: VMWARE
        resource_kind: HostSystem
        severity: WARNING
        wait_cycles: 2
        cancel_cycles: 2
        condition: {{type: property, key: summary|adapter, operator: EQ, value: {OLD}, instanced: false}}
    """, "sm_w.yaml": f"""
        id: {SM_V}
        name: Probe Where SM
        formula: 'count(${{adaptertype=VMWARE, objecttype=HostSystem, attribute=badge|health, depth=1, where="summary|adapter equals {OLD}"}})'
        resource_kinds: [{{resource_kind_key: HostSystem, adapter_kind_key: VMWARE}}]
    """}
    src = build_source(tmp_path / "s", sources=srcs)
    rc, text = _run(src, tmp_path / "out", capsys, "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW))
    assert rc == 4, text  # both fail, so verification compares nothing
    assert ("SymptomDefinition/State/Condition[0]@value: the value 'ProbeOld' equals a mapped adapter kind" in text)
    assert "has the word 'ProbeOld', a mapped adapter kind; it may name the kind as data" in text


def test_derived_reference_outside_the_input_stops_unless_dropped(tmp_path, capsys):
    srcs = {k: SOURCES[k] for k in ("sm_k.yaml", "v_lib.yaml", "d_k.yaml", "y_d.yaml", "a_d.yaml")}
    full = build_source(tmp_path / "full", sources=srcs)
    lone = build_source(tmp_path / "lone", sources={k: srcs[k] for k in ("sm_k.yaml", "v_lib.yaml", "d_k.yaml")})
    km = _tsv(tmp_path, "k.tsv", STAR_ROW)
    rc, text = _run(lone, tmp_path / "o1", capsys, "--map-kind", km)
    assert rc == 1
    assert (f"widget 3 (AlertList) alertDefinitions: references alert {DERIVED_ALERT}, which is not in the input; "
            f"its id embeds the mapped adapter kind ProbeOld") in text
    # dropped: the product object stays where it is, so the reference does too
    rc, text = _run(full, tmp_path / "o2", capsys, "--map-kind", km,
                    "--drop", _tsv(tmp_path, "drop.tsv", [(DERIVED_ALERT,)]))
    assert rc == 0, text
    d = _y(tmp_path / "o2", "dashboards/probe-kind-dashboard.yaml")
    assert [w for w in d["widgets"] if w["id"] == "w3"][0]["alert_definitions"] == [DERIVED_ALERT]


def test_summary_page_bound_to_a_mapped_kind_stops(tmp_path, capsys):
    src = build_source(tmp_path / "s", sources={k: SOURCES[k] for k in ("sm_k.yaml", "v_lib.yaml", "d_k.yaml")})
    pak = tmp_path / "pakish" / "dashboards" / "HostFolder"
    pak.mkdir(parents=True)
    (pak / "dashboard.json").write_text((src / "dashboards.json").read_text())
    (src / "dashboards.json").unlink()
    (tmp_path / "pakish" / "views.xml").write_text((src / "views.xml").read_text())
    km = _tsv(tmp_path, "k.tsv", [("VMWARE", "HostFolder", NEW, "probe_folder")])
    # the folder name alone binds nothing (no binding file): nothing to re-point
    rc, text = _run(tmp_path / "pakish", tmp_path / "out0", capsys, "--map-kind", km)
    assert "Summary page for" not in text, text
    # the binding file is what binds it
    (tmp_path / "pakish" / "dashboards" / "dashboards.properties").write_text("HostFolder=VMWARE:HostFolder\n")
    rc, text = _run(tmp_path / "pakish", tmp_path / "out", capsys, "--map-kind", km)
    assert rc == 1
    assert "Summary page for VMWARE:HostFolder (its binding" in text and "does not re-point Summary page bindings" in text


def test_accounting_catches_a_kind_the_rewriter_missed():
    from vcfcf_core.importer.accounting import account_kinds
    from vcfcf_core.importer.model import MappingError
    km = KindMap(parse_kind_map(f"{OLD}\t*\t{NEW}\t*\n", "k"))
    with pytest.raises(MappingError, match="the importer missed this place"):
        account_kinds("symptom", {"SymptomDefinition@adapterKind": OLD,
                                  "SymptomDefinition@resourceKind": "Probe Library"}, km)
    # the same name in text and in a metric key is not a kind
    account_kinds("symptom", {"SymptomDefinition@adapterKind": NEW, "SymptomDefinition@name": f"{OLD} big",
                              "SymptomDefinition/State/Condition[0]@key": f"{OLD}|size"}, km)
    # formulas: a missed entry, and the kind outside any entry
    with pytest.raises(MappingError, match="the importer missed this place"):
        account_kinds("supermetric", {"supermetric.formula": f"sum(${{adaptertype={OLD}, objecttype=X, "
                                                             f"metric=a|b, depth=1}})"}, km)
    with pytest.raises(MappingError, match="outside the kind slots, metric keys, names and quoted strings"):
        account_kinds("supermetric", {"supermetric.formula": f"{OLD} + sum(${{adaptertype={NEW}, objecttype=X, "
                                                             f"metric=a|b, depth=1}})"}, km)
    account_kinds("supermetric", {"supermetric.formula": f"sum(${{adaptertype={NEW}, objecttype=X, "
                                                         f"metric={OLD}|b, resourcename={OLD} one, depth=1}})"}, km)


# ------------------------------------------------------------ interplay
def test_map_with_id_map_mint_and_factory_prefixed(source, tmp_path, capsys):
    km = _tsv(tmp_path, "k.tsv", STAR_ROW)
    new_view = "7a000000-0000-4000-8000-0000000000ff"
    rc, text = _cli(["import-local", source, "--out", tmp_path / "m", "--layout", "third-party",
                     "--id-map", _tsv(tmp_path, "ids.tsv", [(V_LIB, new_view)]), "--naming", "unprefixed",
                     "--map-kind", km], capsys)
    assert rc == 0, text
    v = _y(tmp_path / "m", "views/probe-library-list.yaml")
    assert v["id"] == new_view and v["subject"]["adapter_kind"] == NEW
    # mint: every id minted from the source id; kinds re-pointed; the
    # AlertList follows the minted alert id; prefixed names follow references
    out = tmp_path / "mint"
    rc, text = _cli(["import-local", source, "--out", out, "--layout", "content", "--ids", "mint",
                     "--mint-namespace", "probe", "--naming", "factory-prefixed", "--map-kind", km], capsys)
    assert rc == 0, text
    rep = _report(out)
    assert rep["verify"]["differ"] == 0
    al = _y(out, "alerts/probe-derived-alert.yaml")
    assert al["adapter_kind"] == NEW and al["name"] == "[VCF CF] Probe Derived Alert"
    d = _y(out, "dashboards/probe-kind-dashboard.yaml")
    assert [w for w in d["widgets"] if w["id"] == "w3"][0]["alert_definitions"] == [
        f"AlertDefinition-{al['id']}"]
    # mint: the derived ids are minted, not re-pointed (19 = 23 less the 4 id references)
    assert rep["kind_map"]["kind_references_repointed"] == 19


def test_mint_follows_a_derived_alert_id_without_a_map(source, tmp_path, capsys):
    """Without --map-kind too: an AlertList naming a derived alert id follows
    the minted id, and the alert's derived symptom reference verifies."""
    out = tmp_path / "mint"
    rc, text = _cli(["import-local", source, "--out", out, "--layout", "third-party", "--ids", "mint",
                     "--mint-namespace", "probe", "--naming", "unprefixed"], capsys)
    assert rc == 0, text
    al = _y(out, "alerts/probe-derived-alert.yaml")
    d = _y(out, "dashboards/probe-kind-dashboard.yaml")
    assert [w for w in d["widgets"] if w["id"] == "w3"][0]["alert_definitions"] == [f"AlertDefinition-{al['id']}"]
    assert _report(out)["verify"]["identical"] == 12


def test_dry_run_reports_and_writes_nothing(source, tmp_path, capsys):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--dry-run", "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW),
                    "--describe", _tsv(tmp_path, "d.tsv", [("view", "Probe VM List", "New text")]))
    assert rc == 0, text
    assert not out.exists() and "dry run: nothing written" in text
    assert "KIND view 'Probe Library List': 5 kind reference(s) re-pointed" in text
    assert "DESCRIBED view 'Probe VM List': description replaced" in text


# ------------------------------------------------------------ --describe
DESCRIBE_ROWS = [
    ("type", "name", "description"),
    ("view", "Probe Library List", r"Fresh view\nline two"),
    ("dashboard", D_K, "Fresh dashboard"),
    ("report", "Probe Kind Report", "Fresh report"),
    ("supermetric", "Probe Kind SM", r"Fresh SM \\ path"),
    ("alert", "Probe Library Alert", "Fresh alert"),
    ("recommendation", "probeKindRec", r"Fresh recommendation\ttabbed"),
]


def test_describe_replaces_each_type_and_verification_counts_it(source, tmp_path, capsys):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--describe", _tsv(tmp_path, "d.tsv", DESCRIBE_ROWS), layout="pak")
    assert rc == 0, text
    assert _y(out, "views/probe-library-list.yaml")["description"] == "Fresh view\nline two"
    assert _y(out, "dashboards/probe-kind-dashboard.yaml")["description"] == "Fresh dashboard"
    assert _y(out, "reports/probe-kind-report.yaml")["description"] == "Fresh report"
    assert _y(out, "supermetrics/probe-kind-sm.yaml")["description"] == "Fresh SM \\ path"
    assert _y(out, "alerts/probe-library-alert.yaml")["description"] == "Fresh alert"
    assert _y(out, "recommendations/probekindrec.yaml")["description"] == "Fresh recommendation\ttabbed"
    rep = _report(out)
    st = _status(rep)
    for n in ("Probe Library List", "Probe Kind Dashboard", "Probe Kind Report", "Probe Kind SM",
              "Probe Library Alert", "probeKindRec"):
        assert st[n] == "identical apart from a replaced description", (n, st[n])
    assert st["Probe VM List"] == "identical"
    assert rep["verify"]["intended_changes"]["descriptions_replaced"] == 6
    by = {o["name"]: o for o in rep["objects"]}
    assert by["Probe Library List"]["description_replaced"] is True
    assert by["Probe Library List"]["source_description_length"] == len(f"Lists {OLD} libraries")
    assert {"field": "description", "length": 22} in by["Probe VM List"]["verbatim_text"]
    assert all(f["field"] != "description" for f in by["Probe Library List"]["verbatim_text"])
    assert "DESCRIBED alert 'Probe Library Alert': description replaced (27 characters in the source, 11 written)" \
        in text


def test_describe_with_map_and_rename_matches_source_names(source, tmp_path, capsys):
    out = tmp_path / "out"
    rename = _tsv(tmp_path, "r.tsv", [("view", "Probe Library List", "Renamed List")])
    desc = _tsv(tmp_path, "d.tsv", [("view", "Probe Library List", "Fresh"), ("view", "Renamed List", "Nope")])
    rc, text = _run(source, out, capsys, "--rename", rename, "--describe", desc,
                    "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW))
    assert rc == 0, text
    v = _y(out, "views/renamed-list.yaml")
    assert v["description"] == "Fresh" and v["subject"]["adapter_kind"] == NEW
    assert "WARNING: describe file: view 'Renamed List' names no object in the input" in text
    assert _status(_report(out))["Renamed List"] == "identical apart from re-pointed kinds and a replaced description"


def test_describe_removes_the_whitespace_loss_it_replaces(tmp_path, capsys):
    src = build_source(tmp_path / "s", sources={"v_vm.yaml": SOURCES["v_vm.yaml"]})
    x = (src / "views.xml").read_text().replace("not on the mapped kind</Description>", "not on the mapped kind  "
                                                "</Description>")
    (src / "views.xml").write_text(x)
    rc, text = _run(src, tmp_path / "o1", capsys)
    assert rc == 1 and "LOSS view 'Probe VM List': Description surrounding whitespace" in text
    rc, text = _run(src, tmp_path / "o2", capsys, "--describe",
                    _tsv(tmp_path, "d.tsv", [("view", V_VM, "Clean")]))
    assert rc == 0, text
    assert "LOSS" not in text
    assert _status(_report(tmp_path / "o2"))["Probe VM List"] == "identical apart from a replaced description"


@pytest.mark.parametrize("rows,needle", [
    ([("symptom", "Probe Library Big", "x")], "a symptom has no description on the content-import wire"),
    ([("view", "Probe VM List")], "expected type<TAB>name or id<TAB>new description"),
    ([("view", "Probe VM List", r"bad \q escape")], "unknown escape \\q"),
    ([("view", "Probe VM List", "a"), ("view", "Probe VM List", "b")], "is listed twice"),
    ([("view", "Probe VM List", "a"), ("view", V_VM, "b")], "is named by 2 rows"),
    ([("policy", "x", "y")], "is not one of view, dashboard"),
])
def test_describe_usage_errors(source, tmp_path, capsys, rows, needle):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--describe", _tsv(tmp_path, "d.tsv", rows))
    assert rc == 2, text
    assert needle in text and not out.exists()


def test_describe_row_naming_two_objects_is_a_usage_error(tmp_path, capsys):
    two = dict(SOURCES)
    two["v_vm2.yaml"] = SOURCES["v_vm.yaml"].replace(V_VM, "7a000000-0000-4000-8000-0000000000b9")
    src = build_source(tmp_path / "s", sources={k: two[k] for k in ("v_vm.yaml", "v_vm2.yaml")})
    rc, text = _run(src, tmp_path / "out", capsys, "--describe",
                    _tsv(tmp_path, "d.tsv", [("view", "Probe VM List", "x")]))
    assert rc == 2
    assert "--describe: view 'Probe VM List' names 2 objects" in text and "key the row by id" in text


# ------------------------------------------------------------ verbatim text
def test_verbatim_free_text_is_listed_per_object(source, tmp_path, capsys):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--rename", _tsv(tmp_path, "r.tsv", [("view", V_VM, "Renamed VM")]))
    assert rc == 0, text
    by = {o["name"]: o for o in _report(out)["objects"]}
    d = {f["field"]: f["length"] for f in by["Probe Kind Dashboard"]["verbatim_text"]}
    assert d["name"] == len("Probe Kind Dashboard") and d["description"] == len(f"The {OLD} dashboard")
    assert d["widget w0 title"] == len(f"{OLD} libraries") and d["widget w4 html"] == len(f"<b>{OLD} notes</b>")
    # a renamed name is not the source's prose; a recommendation's name is its key
    assert [f["field"] for f in by["Renamed VM"]["verbatim_text"]] == ["description"]
    assert [f["field"] for f in by["probeKindRec"]["verbatim_text"]] == ["description"]
    assert "free-text field(s)" in text and "listed per object in report.json (verbatim_text)" in text
    # no --map-kind / --describe: the report carries none of their keys
    rep = _report(out)
    assert "kind_map" not in rep and "intended_changes" not in rep["verify"]
    assert "kind_references_repointed" not in by["Renamed VM"] and "description_replaced" not in by["Renamed VM"]


def test_verbatim_lists_prefixed_names_and_measures_the_source(tmp_path, capsys):
    src = build_source(tmp_path / "s", sources={"v_vm.yaml": SOURCES["v_vm.yaml"]})
    x = (src / "views.xml").read_text().replace("not on the mapped kind</Description>",
                                                "not on the mapped kind  </Description>")
    (src / "views.xml").write_text(x)
    out = tmp_path / "out"
    rc, text = _cli(["import-local", src, "--out", out, "--layout", "content", "--ids", "mint", "--mint-namespace",
                     "p", "--naming", "factory-prefixed", "--allow-partial"], capsys)
    assert rc == 0, text
    vt = {f["field"]: f["length"] for f in _report(out)["objects"][0]["verbatim_text"]}
    # the prefixed name still ships the source's name; the length is the source's
    assert vt == {"name": len("Probe VM List"), "description": len("not on the mapped kind  ")}


# ------------------------------------------------- review fixes (2026-11-13)
DERIVED_REC = f"Recommendation-df-{OLD}-Probe_Derived_Rec"
REC_D = f"""
    name: Probe Derived Rec
    description: Check the item.
    adapter_kind: {OLD}
"""


def _with_rec(alerts_using_it):
    srcs = {k: SOURCES[k] for k in ("y_k.yaml", "y_d.yaml", "a_k.yaml", "a_d.yaml")}
    srcs["k_d.yaml"] = REC_D
    for a in alerts_using_it:
        srcs[a] = srcs[a].replace("        recommendations: [{name: probeKindRec, priority: 1}]\n", "")
        srcs[a] = srcs[a].rstrip() + "\n        recommendations: [{name: Probe Derived Rec, priority: 1}]\n"
    return srcs


def test_derived_recommendation_key_takes_the_alerts_new_kind(tmp_path, capsys):
    src = build_source(tmp_path / "s", sources=_with_rec(["a_d.yaml"]))
    assert DERIVED_REC in (src / "alerts.xml").read_text()
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys, "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW))
    assert rc == 0, text
    rec = _y(out, f"recommendations/recommendation-df-{NEW.replace('_', '-')}-probe-derived-rec.yaml")
    assert rec["id"] == f"Recommendation-df-{NEW}-Probe_Derived_Rec" and rec["adapter_kind"] == NEW
    assert "no alert in the set references this recommendation" not in text
    assert _y(out, "alerts/probe-derived-alert.yaml")["recommendations"][0]["name"] == rec["name"]


def test_recommendation_key_is_kept_when_no_alert_using_it_moves(tmp_path, capsys):
    # the map names Probe Library only; the alert using the key is on Probe Item
    km = _tsv(tmp_path, "k.tsv", [(OLD, "Probe Library", NEW, "*")])
    src = build_source(tmp_path / "s", sources=_with_rec(["a_d.yaml"]))
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys, "--map-kind", km)
    assert rc == 0, text
    assert _y(out, "recommendations/recommendation-df-probeold-probe-derived-rec.yaml")["id"] == DERIVED_REC
    # alerts on both kinds use it, and only one moves: that stops it
    src2 = build_source(tmp_path / "s2", sources=_with_rec(["a_d.yaml", "a_k.yaml"]))
    rc, text = _run(src2, tmp_path / "o2", capsys, "--map-kind", km, "--allow-partial")
    assert (f"FAILED recommendation {DERIVED_REC} '{DERIVED_REC}': kind map: recommendation key {DERIVED_REC} "
            f"embeds the mapped adapter kind {OLD}; the alerts that use it move to {NEW} while alerts on "
            f"{OLD}:Probe Item stay") in text


def test_alertlist_naming_a_repointed_alert_that_failed_fails_too(tmp_path, capsys):
    srcs = {k: SOURCES[k] for k in ("sm_k.yaml", "v_lib.yaml", "d_k.yaml", "y_d.yaml", "a_d.yaml")}
    src = build_source(tmp_path / "s", sources=srcs)
    x = (src / "alerts.xml").read_text()
    start = x.index("<SymptomDefinition ")
    end = x.index("</SymptomDefinition>", start) + len("</SymptomDefinition>")
    (src / "alerts.xml").write_text(x[:start] + x[end:])  # the alert's symptom is gone: the alert fails
    rc, text = _run(src, tmp_path / "out", capsys, "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW),
                    "--allow-partial")
    assert f"FAILED alert {DERIVED_ALERT} 'Probe Derived Alert'" in text
    assert (f"FAILED dashboard {D_K} 'Probe Kind Dashboard': field widgets[3].alert_definitions[0] references "
            f"alert AlertDefinition-{NEW}-Probe_Derived_Alert (its derived id re-pointed by --map-kind), which did "
            f"not convert") in text
    assert not (tmp_path / "out" / "dashboards").exists() or not list((tmp_path / "out" / "dashboards").iterdir())


def test_a_prefixed_drop_or_id_map_key_names_its_own_type_only(tmp_path, capsys):
    srcs = {k: SOURCES[k] for k in ("y_d.yaml", "a_d.yaml")}
    srcs["a_d.yaml"] = srcs["a_d.yaml"].replace("name: Probe Derived Alert", "name: Probe Derived Symptom")
    src = build_source(tmp_path / "s", sources=srcs)
    sym_id = f"SymptomDefinition-{OLD}-Probe_Derived_Symptom"
    alert_id = f"AlertDefinition-{OLD}-Probe_Derived_Symptom"
    assert alert_id in (src / "alerts.xml").read_text()
    rc, text = _run(src, tmp_path / "d1", capsys, "--drop", _tsv(tmp_path, "d1.tsv", [(sym_id,)]), "--allow-partial")
    assert f"dropped (--drop): symptom {sym_id}" in text and "dropped (--drop): alert" not in text
    # a bare key names no type and matches both, as before
    rc, text = _run(src, tmp_path / "d2", capsys, "--drop",
                    _tsv(tmp_path, "d2.tsv", [(f"{OLD}-Probe_Derived_Symptom",)]), "--dry-run")
    assert f"dropped (--drop): symptom {sym_id}" in text and f"dropped (--drop): alert {alert_id}" in text
    new = "11111111-2222-4333-8444-555555555555"
    rc, text = _cli(["import-local", src, "--out", tmp_path / "m", "--layout", "third-party", "--naming", "unprefixed",
                     "--id-map", _tsv(tmp_path, "m.tsv", [(sym_id, f"SymptomDefinition-{new}")])], capsys)
    assert rc == 0, text
    idmap = (tmp_path / "m" / "import-report" / "id_map.tsv").read_text()
    assert f"symptom\t{sym_id}\tSymptomDefinition-{new}\t" in idmap
    assert f"alert\t{alert_id}\t{alert_id}\t" in idmap


def test_kind_valued_labels_follow_the_kind(tmp_path, capsys):
    heat = f"""
        id: 1d000000-0000-4000-8000-0000000000c1
        name: Probe Kind Heat
        description: heat
        name_path: ""
        shared: false
        widgets:
          - id: heat
            type: Heatmap
            title: Heat
            coords: {{x: 1, y: 1, w: 12, h: 6}}
            mode: all
            depth: 1
            configs:
              - name: Probe Tab
                adapter_kind: {OLD}
                resource_kind: Probe Library
                color_by: {{metric_key: {OLD}|size, label: Size}}
                size_by: {{metric_key: {OLD}|size, label: Size}}
                group_by: {{adapter_kind: {OLD}, resource_kind: Probe Item, text: Items}}
                color:
                  min_value: 0
                  max_value: 100
                  thresholds: {{values: [0, 100], colors: ["#74B43B", "#DE3F30"]}}
                solid_coloring: false
                focus_on_groups: false
    """
    srcs = {k: SOURCES[k] for k in ("sm_k.yaml", "v_lib.yaml", "d_k.yaml", "y_d.yaml", "a_d.yaml")}
    srcs["d_h.yaml"] = heat
    src = build_source(tmp_path / "s", sources=srcs)
    env = json.loads((src / "dashboards.json").read_text())
    heat_db = next(d for d in env["dashboards"] if d["name"] == "Probe Kind Heat")
    assert heat_db["widgets"][0]["config"]["configs"][0]["groupBy"]["parentText"] == OLD
    rc, text = _run(src, tmp_path / "o1", capsys, "--map-kind", _tsv(tmp_path, "k1.tsv", STAR_ROW))
    assert rc == 0, text
    tab = _y(tmp_path / "o1", "dashboards/probe-kind-heat.yaml")["widgets"][0]["configs"][0]
    assert tab["group_by"].get("parent_text", NEW) == NEW and tab["group_by"]["adapter_kind"] == NEW
    # a resource kind renamed: the Scoreboard entry's resourceKindName follows
    rc, text = _run(src, tmp_path / "o2", capsys, "--map-kind",
                    _tsv(tmp_path, "k2.tsv", [(OLD, "Probe Item", OLD, "Probe Thing")]))
    assert rc == 0, text
    m = _y(tmp_path / "o2", "dashboards/probe-kind-dashboard.yaml")["widgets"][1]["metrics"][0]
    assert m["resource_kind"] == "Probe Thing" and m.get("resource_kind_name", "Probe Thing") == "Probe Thing"
    assert _report(tmp_path / "o2")["verify"]["differ"] == 0


def test_headers_after_comments_and_upper_case_ids(source, tmp_path, capsys):
    km = tmp_path / "k.tsv"
    km.write_text(f"# kinds\n\nold_adapter_kind\told_rk\tnew_ak\tnew_rk\n{OLD}\t*\t{NEW}\t*\n")
    desc = tmp_path / "d.tsv"
    desc.write_text(f"# descriptions\ntype\tname\tdescription\nview\t{V_VM.upper()}\tUpper id\n")
    rc, text = _run(source, tmp_path / "out", capsys, "--map-kind", km, "--describe", desc)
    assert rc == 0, text
    assert _y(tmp_path / "out", "views/probe-vm-list.yaml")["description"] == "Upper id"
    bad = tmp_path / "bad.tsv"
    bad.write_text(f"{OLD}\t*\t{NEW}\t*\nold_adapter_kind\told_rk\tnew_ak\tnew_rk\n")
    rc, text = _run(source, tmp_path / "o2", capsys, "--map-kind", bad)
    assert rc == 2 and "a header row is only read as the first row" in text


# ------------------------------------------------ independent oracle (W4)
_KIND_FIELDS = ("adapter_kind", "adapter_kind_key", "parent_text")


def _flat_yaml(x, path="", out=None):
    out = {} if out is None else out
    if isinstance(x, dict):
        for k, v in x.items():
            _flat_yaml(v, f"{path}.{k}" if path else str(k), out)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            _flat_yaml(v, f"{path}[{i}]", out)
    else:
        out[path] = x
    return out


def _yaml_by_object(root: Path) -> dict:
    out = {}
    for p in root.rglob("*.yaml"):
        if p.name == "PROJECT.yaml" or "import-report" in p.parts:
            continue
        d = yaml.safe_load(p.read_text())
        out[(p.parent.name, str(d.get("name")))] = d
    return out


def _corpus_source(tmp: Path) -> Path:
    import warnings
    from vcfcf_core.alerts.loader import load_dir as load_alerts, load_recommendations
    from vcfcf_core.dashboards.loader import load_all
    from vcfcf_core.reports.loader import load_dir as load_reports
    from vcfcf_core.supermetrics.loader import load_dir as load_sms
    from vcfcf_core.symptoms.loader import load_dir as load_syms
    c = Path(__file__).resolve().parent.parent / "content"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sms = load_sms(c / "supermetrics")
        views, dashes = load_all(c / "views", c / "dashboards")
        reports = load_reports(c / "reports", c / "views", c / "dashboards")
        syms, alerts, recs = load_syms(c / "symptoms"), load_alerts(c / "alerts"), load_recommendations(
            c / "recommendations")
    src = tmp / "src"
    src.mkdir()
    (src / "views.xml").write_text(render_views_xml(views, sm_map={s.name: s.id for s in sms}))
    by_name = {v.name: v for v in views}
    for i, d in enumerate(dashes):
        (src / f"d{i}.json").write_text(render_dashboards_bundle_json([d], by_name, "0", known_dashboards=dashes))
    (src / "reports.xml").write_text(render_report_xml(reports))
    (src / "alerts.xml").write_text(render_alert_content_xml(syms, alerts, recs))
    (src / "sms.json").write_text(json.dumps(_render_supermetrics_dict(type("B", (), {"supermetrics": sms})())))
    return src


@pytest.mark.parametrize("old_ak,old_rk,new_ak,new_rk", [
    ("VMWARE", "*", "oracle_ak", "*"),
    ("VMWARE", "VirtualMachine", "VMWARE", "OracleVM"),
])
def test_independent_oracle_mapped_vs_unmapped_yaml(tmp_path, capsys, old_ak, old_rk, new_ak, new_rk):
    """Logic independent of the importer's mapper: the factory corpus is
    converted with and without the map and the two YAML trees are diffed.
    Every differing leaf must be an exact old-to-new kind swap, and no kind
    field of a converted object may still name a kind the map moves. A place
    the rewriter missed is unchanged in both runs and so cannot cancel out
    here the way it can in verification (which compares against the
    re-pointed source)."""
    src = _corpus_source(tmp_path)
    common = ["--layout", "third-party", "--ids", "keep", "--naming", "unprefixed", "--allow-partial"]
    rc, text = _cli(["import-local", src, "--out", tmp_path / "plain", *common], capsys)
    assert rc == 0, text
    rc, text = _cli(["import-local", src, "--out", tmp_path / "mapped", *common, "--map-kind",
                     _tsv(tmp_path, "k.tsv", [(old_ak, old_rk, new_ak, new_rk)])], capsys)
    assert rc == 0, text
    plain, mapped = _yaml_by_object(tmp_path / "plain"), _yaml_by_object(tmp_path / "mapped")
    swaps, bad, stale = 0, [], []

    def swap(v: str) -> str:  # the new value spelled with the old kind
        return v.replace(new_ak, old_ak) if old_rk == "*" else v.replace(new_rk, old_rk)

    for key, dm in mapped.items():
        dp = plain.get(key)
        if dp is None:
            continue
        fm, fp = _flat_yaml(dm), _flat_yaml(dp)
        for path in set(fm) | set(fp):
            vm, vp = fm.get(path), fp.get(path)
            if vm != vp:
                if isinstance(vm, str) and isinstance(vp, str) and swap(vm) == vp:
                    swaps += 1
                else:
                    bad.append((key, path, vp, vm))
            leaf = path.rsplit(".", 1)[-1]
            if old_rk == "*" and leaf in _KIND_FIELDS and vm == old_ak:
                stale.append((key, path))
            if old_rk != "*" and leaf in ("resource_kind", "resource_kind_key", "resource_kind_name") \
                    and vm == old_rk:
                ak = fm.get(path.rsplit(".", 1)[0] + (".adapter_kind_key" if leaf.endswith("_key") else ".adapter_kind"),
                            fm.get("adapter_kind"))
                if ak == old_ak:
                    stale.append((key, path))
    assert swaps > (50 if old_rk == "*" else 10), swaps
    assert not bad, bad[:10]
    assert not stale, stale[:10]


# ------------------------------------- a malformed object never takes the run
UNUSED_ROW = [("Unused", "*", "other", "*")]
BAD_SM, GOOD_SM = "5e000000-0000-4000-8000-0000000000d1", "5e000000-0000-4000-8000-0000000000d2"


def _sm_pair_source(tmp: Path) -> Path:
    src = tmp / "smsrc"
    src.mkdir()
    sms = {BAD_SM: {"id": BAD_SM, "name": "Bad SM", "formula": "1", "description": "", "unitId": "",
                    "resourceKinds": 1},
           GOOD_SM: {"id": GOOD_SM, "name": "Good SM", "formula": "avg(${this, metric=cpu|usage_average})",
                     "description": "", "unitId": "",
                     "resourceKinds": [{"adapterKindKey": "VMWARE", "resourceKindKey": "HostSystem"}]}}
    (src / "sms.json").write_text(json.dumps(sms))
    return src


@pytest.mark.parametrize("extra", [[], ["--allow-partial"]])
@pytest.mark.parametrize("with_map", [False, True])
def test_malformed_super_metric_is_an_internal_error_with_or_without_the_map(tmp_path, capsys, extra, with_map):
    """Codex P2 (PR 365): `resourceKinds: 1` raised out of the kind-map step
    and stopped the run, even with an unused row. It is that object's
    INTERNAL ERROR, as without the map: the other objects are still
    converted and reported, and the run exits 5 (never accepted)."""
    src = _sm_pair_source(tmp_path)
    km = ["--map-kind", _tsv(tmp_path, "k.tsv", UNUSED_ROW)] if with_map else []
    rc, text = _run(src, tmp_path / "out", capsys, *km, *extra)
    assert rc == 5, text
    assert "Traceback" not in text
    assert f"INTERNAL ERROR supermetric {BAD_SM} 'Bad SM': internal error in the converter" in text
    assert "TypeError: 'int' object is not iterable" in text
    assert "  supermetric          2          1" in text  # the good one converts
    assert "compared 1 object(s)" in text


def _dash_with(tmp: Path, mutate) -> Path:
    src = build_source(tmp / "s", sources={k: SOURCES[k] for k in ("sm_k.yaml", "v_lib.yaml", "d_k.yaml")})
    env = json.loads((src / "dashboards.json").read_text())
    env["dashboards"][0]["widgets"][3]["config"]["alertDefinitions"] = []
    mutate(env)
    (src / "dashboards.json").write_text(json.dumps(env))
    return src


def _metric_not_a_list(env):
    env["dashboards"][0]["widgets"][1]["config"]["metric"]["resourceKindMetrics"] = 5


def _entries_not_a_list(env):
    env["entries"]["resourceKind"] = 3


@pytest.mark.parametrize("mutate", [_metric_not_a_list, _entries_not_a_list])
def test_malformed_dashboard_is_an_internal_error_under_the_map(tmp_path, capsys, mutate):
    src = _dash_with(tmp_path, mutate)
    rc, text = _run(src, tmp_path / "out", capsys, "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW),
                    "--allow-partial")
    assert rc == 5, text
    assert "Traceback" not in text
    assert f"INTERNAL ERROR dashboard {D_K} 'Probe Kind Dashboard': internal error in the converter" in text
    # the view and the super metric still convert, re-pointed
    assert "KIND view 'Probe Library List'" in text and "KIND supermetric 'Probe Kind SM'" in text


@pytest.mark.parametrize("func,type_,oid,name", [
    ("_view", "view", V_LIB, "Probe Library List"),
    ("_report", "report", R_K, "Probe Kind Report"),
    ("_symptom", "symptom", f"SymptomDefinition-{Y_K}", "Probe Library Big"),
    ("_alert", "alert", f"AlertDefinition-{A_K}", "Probe Library Alert"),
    ("_recommendation", "recommendation", "probeKindRec", "probeKindRec"),
])
def test_a_fault_in_an_xml_remapper_is_that_objects_internal_error(source, tmp_path, capsys, monkeypatch,
                                                                    func, type_, oid, name):
    """XML payloads cannot take a shape these remappers trip on, so a fault
    is injected into the one object's remap (the isolation is the same)."""
    from vcfcf_core.importer import kinds as K
    real = getattr(K, func)

    def wrapped(el, *rest):
        if (el.get("id") or el.get("key")) == oid:
            raise RuntimeError(f"injected fault on {oid}")
        return real(el, *rest)
    monkeypatch.setattr(K, func, wrapped)
    rc, text = _run(source, tmp_path / "out", capsys, "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW),
                    "--allow-partial")
    assert rc == 5, text
    assert "Traceback" not in text
    assert f"INTERNAL ERROR {type_} {oid} '{name}': internal error in the converter (--map-kind): RuntimeError" in text
    assert "INTERNAL ERROR" not in text.replace(f"INTERNAL ERROR {type_} {oid}", "", 1).split("summary")[0]


def test_a_fault_in_the_derived_id_table_is_that_objects_internal_error(source, tmp_path, capsys, monkeypatch):
    from vcfcf_core.importer import kinds as K
    real = K._derived_ak

    def wrapped(id_, prefix, ak):
        if id_ == DERIVED_SYM:
            raise RuntimeError("injected fault")
        return real(id_, prefix, ak)
    monkeypatch.setattr(K, "_derived_ak", wrapped)
    rc, text = _run(source, tmp_path / "out", capsys, "--map-kind", _tsv(tmp_path, "k.tsv", STAR_ROW),
                    "--allow-partial")
    assert rc == 5 and "Traceback" not in text, text
    assert f"INTERNAL ERROR symptom {DERIVED_SYM} 'Probe Derived Symptom': internal error in the converter " \
           f"(--map-kind): RuntimeError: injected fault" in text
    assert "KIND view 'Probe Library List'" in text


def test_a_fault_in_describe_or_the_verbatim_listing_is_that_objects_internal_error(source, tmp_path, capsys,
                                                                                   monkeypatch):
    from vcfcf_core.importer import convert as C

    class Boom(dict):
        def __getitem__(self, k):
            raise RuntimeError("injected describe fault")
    monkeypatch.setattr(C, "DESCRIBED_TYPES", Boom(C.DESCRIBED_TYPES))
    rc, text = _run(source, tmp_path / "o1", capsys, "--describe",
                    _tsv(tmp_path, "d.tsv", [("view", "Probe VM List", "x")]), "--allow-partial")
    assert rc == 5 and "Traceback" not in text, text
    assert f"INTERNAL ERROR view {V_VM} 'Probe VM List': internal error in the converter (--describe)" in text
    monkeypatch.undo()
    real = C.verbatim_text

    def wrapped(e):
        if e.source_id == V_VM:
            raise RuntimeError("injected listing fault")
        return real(e)
    monkeypatch.setattr(C, "verbatim_text", wrapped)
    rc, text = _run(source, tmp_path / "o2", capsys, "--allow-partial")
    assert rc == 5 and "Traceback" not in text, text
    assert f"INTERNAL ERROR view {V_VM} 'Probe VM List': internal error in the converter (verbatim text listing)" \
        in text
    assert "compared 11 object(s)" in text
