"""``python3 -m vcfcf_extractor import-local``: the offline content converter.

Every test drives the real CLI (``vcfcf_extractor.cli.main``) on a synthetic
source tree and, where it loads the result, uses the real loader of the
target layout (factory per-type loaders for content/, the factory bundle
loader for a third-party PROJECT.yaml, ``sdk_builder._load_bundled_content``
for a pak). The source tree is produced by the factory's own renderers from
synthetic YAML ("Probe ..." names, generic VMWARE keys, made-up UUIDs), so
no third-party or product content is copied here. One stock view id from the
committed baseline is used to prove the stock-id guard refuses it.

How-to: knowledge/context/authoring/importer_offline_conversion.md.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest
import yaml

from vcfcf_core.alerts.loader import load_file as load_alert, load_recommendation_file
from vcfcf_core.alerts.render import render_alert_content_xml
from vcfcf_core.dashboards.loader import load_dashboard, load_view
from vcfcf_core.dashboards.render import render_dashboards_bundle_json, render_views_xml
from vcfcf_core.importer import compare
from vcfcf_core.importer.convert import parse_id_list, parse_tsv_map
from vcfcf_core.packaging.assembly import _render_supermetrics_dict
from vcfcf_core.reports.loader import load_file as load_report
from vcfcf_core.reports.render import render_report_xml
from vcfcf_core.supermetrics.loader import load_file as load_sm
from vcfcf_core.symptoms.loader import load_file as load_sym

STOCK_VIEW_ID = "007501f6-a356-42b2-9b6b-2dbd536d8069"  # in stock_ids_baseline.json

SM1 = "5e000000-0000-4000-8000-000000000001"
SM2 = "5e000000-0000-4000-8000-000000000002"
V_HOST = "7a000000-0000-4000-8000-000000000001"
V_DIST = "7a000000-0000-4000-8000-000000000002"
V_TREND = "7a000000-0000-4000-8000-000000000003"
V_LONE = "7a000000-0000-4000-8000-000000000004"
D_A = "1d000000-0000-4000-8000-000000000001"
D_B = "1d000000-0000-4000-8000-000000000002"
D_BARE = "1d000000-0000-4000-8000-000000000003"
D_EXT = "1d000000-0000-4000-8000-0000000000ee"
R_1 = "2e000000-0000-4000-8000-000000000001"
Y_1 = "3c000000-0000-4000-8000-000000000001"
Y_2 = "3c000000-0000-4000-8000-000000000002"
A_1 = "4a000000-0000-4000-8000-000000000001"

# --------------------------------------------------------------- sources
SOURCE_YAML = {
    "sm1.yaml": f"""
        id: {SM1}
        name: Probe SM One
        formula: avg(${{this, metric=cpu|usage_average}})
        description: first
        unit_id: percent
        resource_kinds: [{{resource_kind_key: HostSystem, adapter_kind_key: VMWARE}}]
    """,
    "sm2.yaml": f"""
        id: {SM2}
        name: Probe SM Two
        formula: '${{this, metric=@supermetric:"Probe SM One"}} * 2'
        description: second
        resource_kinds: [{{resource_kind_key: HostSystem, adapter_kind_key: VMWARE}}]
    """,
    "v_host.yaml": f"""
        id: {V_HOST}
        name: Probe Host List
        description: hosts
        data_type: list
        subject:
          adapter_kind: VMWARE
          resource_kind: HostSystem
          types: [descendant]
          filter:
            - {{filter_type: properties, metric_key: summary|version, condition: CONTAINS, value: "8.0"}}
        group_by: {{adapter_kind: VMWARE, resource_kind: ClusterComputeResource}}
        usage: [dashboard, report, content]
        top_n: 10
        time_window: {{unit: DAYS, count: 7}}
        columns:
          - attribute: cpu|usage_average
            display_name: CPU
            unit: percent
            sort: desc
            roll_up_type: AVG
            roll_up_unit: HOURS
            roll_up_count: 1
            yellow_bound: 70
            orange_bound: 80
            red_bound: 90
            ascending_range: false
          - attribute: summary|version
            display_name: Version
            is_property: true
            is_string_attribute: true
            omit: [roll_up_type, show_relative_timestamp]
          - attribute: supermetric:"Probe SM One"
            display_name: SM One
        summary:
          - {{display_name: Total, aggregation: SUM, columns: [0]}}
    """,
    "v_dist.yaml": f"""
        id: {V_DIST}
        name: Probe Distribution
        description: dist
        data_type: distribution
        presentation: pie-chart
        subject: {{adapter_kind: VMWARE, resource_kind: VirtualMachine}}
        distribution_color: "37B3EB"
        columns:
          - attribute: cpu|usage_average
            display_name: CPU
        buckets:
          dynamic: false
          min_value: 0
          max_value: 0
          is_sum: false
          ranges:
            - {{start: 0, end: 25, color: "74B43B"}}
            - {{start: 25, end: 100, color: "DE3F30"}}
        page_size: 50
        additional_columns:
          - attribute: supermetric:"Probe SM Two"
            display_name: SM Two
            localized_name: Super Metric|Probe SM Two
            roll_up_type: NONE
    """,
    "v_trend.yaml": f"""
        id: {V_TREND}
        name: Probe Trend
        description: trend
        data_type: trend
        subject: {{adapter_kind: VMWARE, resource_kind: Datastore}}
        transformations: [NONE, TREND, FORECAST]
        forecast_days: 7
        omit: [pagination, metadata]
        columns:
          - attribute: disk|usage_average
            display_name: Disk
    """,
    "v_lone.yaml": f"""
        id: {V_LONE}
        name: Probe Unreferenced
        description: no dashboard uses me
        subject: {{adapter_kind: VMWARE, resource_kind: VirtualMachine}}
        columns:
          - {{attribute: mem|usage_average, display_name: Memory}}
    """,
    "d_a.yaml": f"""
        id: {D_A}
        name: Probe Dashboard A
        description: first dashboard
        name_path: Probe Folder
        shared: true
        hidden: true
        time_range: last7Days
        omit: [temporary]
        widgets:
          - id: hosts
            type: View
            title: Hosts
            view: Probe Host List
            coords: {{x: 1, y: 1, w: 6, h: 4}}
            ui:
              height: 324
              states:
                - {{key: perm_toolbarVisible_, value: "b%3A0"}}
            navigations:
              - dashboard: Probe Dashboard B
                widgets: [dist]
              - dashboard_id: {D_EXT}
          - id: score
            type: Scoreboard
            title: Score
            coords: {{x: 7, y: 1, w: 6, h: 4}}
            metrics:
              - {{adapter_kind: VMWARE, resource_kind: HostSystem, metric_key: "Super Metric|sm_{SM1}", metric_name: Probe SM One}}
          - id: note
            type: TextDisplay
            title: Note
            html: "<b>probe</b>"
            coords: {{x: 1, y: 5, w: 12, h: 2}}
        interactions:
          - {{from: hosts, to: score, type: resourceId}}
    """,
    "d_b.yaml": f"""
        id: {D_B}
        name: Probe Dashboard B
        description: second dashboard
        name_path: ""
        shared: false
        widgets:
          - id: head
            type: Section
            title: Head
            coords: {{x: 1, y: 1}}
            widgets: [dist, trend]
          - id: dist
            type: View
            title: Dist
            view: Probe Distribution
            coords: {{x: 1, y: 2, w: 6, h: 4}}
          - id: trend
            type: View
            title: Trend
            view: Probe Trend
            coords: {{x: 7, y: 2, w: 6, h: 4}}
    """,
    "d_bare.yaml": f"""
        id: {D_BARE}
        name: Probe Bare
        description: a bare dashboard file
        name_path: ""
        shared: false
        widgets:
          - id: lone
            type: View
            title: External view
            view: {STOCK_VIEW_ID}
            coords: {{x: 1, y: 1, w: 12, h: 4}}
    """,
    "r_1.yaml": f"""
        id: {R_1}
        name: Probe Report
        description: report
        subject_types: [{{adapter_kind: VMWARE, resource_kind: HostSystem, type: self}}]
        sections:
          - {{type: CoverPage, colorize: false, font_color: "000000"}}
          - {{type: TableOfContents}}
          - {{type: View, view: Probe Host List, orientation: Portrait}}
          - {{type: View, view_id: {STOCK_VIEW_ID}, orientation: Landscape, omit: [formatting]}}
          - {{type: Dashboard, dashboard: Probe Dashboard A, orientation: Landscape}}
        settings: {{show_page_footer: true, output_formats: [pdf, csv]}}
    """,
    "y_1.yaml": f"""
        id: {Y_1}
        name: Probe CPU High
        adapter_kind: VMWARE
        resource_kind: HostSystem
        severity: WARNING
        wait_cycles: 1
        cancel_cycles: 1
        disable_in_base_policy: true
        symptom_def_type: condition_self
        omit: [wait_cycles, cancel_cycles]
        condition: {{type: metric_static, key: cpu|usage_average, operator: GT, value: 90, instanced: false}}
    """,
    "y_2.yaml": f"""
        id: {Y_2}
        name: Probe Powered Off
        adapter_kind: VMWARE
        resource_kind: HostSystem
        severity: CRITICAL
        wait_cycles: 2
        cancel_cycles: 3
        condition: {{type: property, key: runtime|powerState, operator: EQ, value: poweredOff, instanced: false}}
    """,
    "k_1.yaml": """
        name: probeRecommendationKey
        id: probeRecommendationKey
        description: Check the host.
        adapter_kind: VMWARE
    """,
    "a_1.yaml": f"""
        id: {A_1}
        name: Probe Host Alert
        description: alert
        adapter_kind: VMWARE
        resource_kind: HostSystem
        type: 16
        sub_type: 19
        criticality: SYMPTOM_BASED
        disable_in_base_policy: true
        impact: {{badge: HEALTH}}
        symptom_sets:
          operator: ALL
          sets:
            - defined_on: SELF
              operator: ANY
              symptoms: [{{name: Probe CPU High}}, {{name: Probe Powered Off}}]
        recommendations: [{{name: probeRecommendationKey, priority: 1}}]
    """,
}


def _yaml_dir(tmp: Path) -> Path:
    d = tmp / "authored"
    d.mkdir()
    for name, text in SOURCE_YAML.items():
        (d / name).write_text(textwrap.dedent(text).lstrip())
    return d


def _build_source(tmp: Path) -> Path:
    """Render the synthetic YAML into product-shaped source files."""
    y = _yaml_dir(tmp)
    sms = [load_sm(y / "sm1.yaml", enforce_framework_prefix=False), load_sm(y / "sm2.yaml", enforce_framework_prefix=False)]
    sm_map = {s.name: s.id for s in sms}
    views = {k: load_view(y / f"{k}.yaml", enforce_framework_prefix=False) for k in ("v_host", "v_dist", "v_trend", "v_lone")}
    by_name = {v.name: v for v in views.values()}
    dashes = {k: load_dashboard(y / f"{k}.yaml", enforce_framework_prefix=False, default_name_path="")
              for k in ("d_a", "d_b", "d_bare")}
    vd = tmp / "authored_views"
    vd.mkdir()
    for v in views.values():
        (vd / f"{v.id}.yaml").write_text(f"id: {v.id}\nname: {v.name}\n")
    dd = tmp / "authored_dashes"
    dd.mkdir()
    for d in dashes.values():
        (dd / f"{d.id}.yaml").write_text(f"id: {d.id}\nname: {d.name}\n")
    report = load_report(y / "r_1.yaml", vd, dd, enforce_framework_prefix=False)
    syms = [load_sym(y / "y_1.yaml", enforce_framework_prefix=False), load_sym(y / "y_2.yaml", enforce_framework_prefix=False)]
    rec = load_recommendation_file(y / "k_1.yaml", enforce_framework_prefix=False)
    alert = load_alert(y / "a_1.yaml", enforce_framework_prefix=False)

    src = tmp / "source" / "content"
    (src / "reports").mkdir(parents=True)
    (src / "resources" / "nested").mkdir(parents=True)
    (src / "dashboards" / "sub").mkdir(parents=True)
    (src / "alertdefs").mkdir()
    (src / "symptomdefs").mkdir()
    (src / "supermetrics").mkdir()
    (src / "files" / "solutionconfig").mkdir(parents=True)
    # several ViewDefs in one file, one in a nested folder, one repeated (identical)
    (src / "reports" / "View - Set.xml").write_text(
        render_views_xml([views["v_host"], views["v_dist"], views["v_trend"]], sm_map=sm_map))
    (src / "resources" / "nested" / "extra.xml").write_text(
        render_views_xml([views["v_lone"], views["v_host"]], sm_map=sm_map))
    (src / "reports" / "Report.xml").write_text(render_report_xml([report]))
    env = json.loads(render_dashboards_bundle_json([dashes["d_a"], dashes["d_b"]], by_name, "0",
                                                   known_dashboards=list(dashes.values())))
    (src / "dashboards" / "Both.json").write_text(json.dumps(env, indent=2))
    bare_env = json.loads(render_dashboards_bundle_json([dashes["d_bare"]], by_name, "0"))
    bare = dict(bare_env["dashboards"][0])
    bare["entries"] = bare_env["entries"]
    (src / "dashboards" / "sub" / "Bare.json").write_text(json.dumps(bare, indent=2))
    (src / "alertdefs" / "Alert.xml").write_text(render_alert_content_xml(syms, [alert], [rec]))
    (src / "symptomdefs" / "Sym.xml").write_text(render_alert_content_xml([syms[0]], [], []))
    smd = _render_supermetrics_dict(type("B", (), {"supermetrics": sms})())
    (src / "supermetrics" / "SMs.json").write_text(json.dumps(smd, indent=2))
    (src / "files" / "solutionconfig" / "list.xml").write_text("<packages><p name='x'/></packages>")
    (src / "alertdefs" / ".gitkeep").write_text("")
    return src


@pytest.fixture(scope="module")
def source(tmp_path_factory) -> Path:
    return _build_source(tmp_path_factory.mktemp("import_local"))


def _cli(argv, capsys) -> tuple:
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


def _run(source, out, capsys, *extra):
    return _cli(["import-local", source, "--out", out, *extra], capsys)


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _yaml(out: Path, rel: str) -> dict:
    return yaml.safe_load((out / rel).read_text())


def _files(out: Path, sub: str) -> list:
    return sorted(p.name for p in (out / sub).glob("*.yaml"))


# ------------------------------------------------------------ completeness
def test_every_object_converted_recursive_multi_file_and_summary(source, tmp_path, capsys):
    out = tmp_path / "out"
    before = _tree_hash(source)
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 0, text
    assert _tree_hash(source) == before, "inputs must be read only"
    # the view no dashboard references, found in a nested folder, is emitted
    assert "probe-unreferenced.yaml" in _files(out, "views")
    assert len(_files(out, "views")) == 4
    # an envelope of two dashboards becomes two files; the bare dashboard a third
    assert _files(out, "dashboards") == ["probe-bare.yaml", "probe-dashboard-a.yaml", "probe-dashboard-b.yaml"]
    assert len(_files(out, "reports")) == 1 and len(_files(out, "alerts")) == 1
    assert len(_files(out, "symptoms")) == 2 and len(_files(out, "recommendations")) == 1
    assert len(_files(out, "supermetrics")) == 2
    # identical copies are merged and said so; non-content files are passed over
    assert f"merged: view {V_HOST} is the same in 2 files" in text
    assert "files/solutionconfig/list.xml: XML with no content definition element" in text
    assert ".gitkeep: empty file" in text
    assert "  view                 4          4" in text
    assert "  dashboard            3          3" in text


def test_failed_object_makes_exit_nonzero_unless_allow_partial(source, tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    for f in source.rglob("*.xml"):
        if "View - Set" in f.name:
            (src / f.name).write_text(f.read_text())
    # a text-presentation view: not modeled, so it fails with the reason
    (src / "text.xml").write_text(
        '<Content><Views><ViewDef id="7a000000-0000-4000-8000-0000000000aa"><Title>Probe Text</Title>'
        '<Description/><SubjectType adapterKind="VMWARE" resourceKind="HostSystem" type="self"/>'
        '<Usage>dashboard</Usage><Presentation type="text"/></ViewDef></Views></Content>')
    rc, text = _run(src, tmp_path / "o1", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 1
    assert "FAILED view 7a000000-0000-4000-8000-0000000000aa 'Probe Text'" in text
    assert "TOOLSET GAP" in text
    rc, text = _run(src, tmp_path / "o2", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--allow-partial")
    assert rc == 0, text


def test_unreadable_archive_member_is_reported_and_never_accepted(source, tmp_path, capsys):
    z = tmp_path / "in.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("content.xml", (source / "reports" / "View - Set.xml").read_text())
        zf.writestr("broken.zip", b"PK\x03\x04not really a zip")
    rc, text = _run(z, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--allow-partial")
    assert rc == 1, "what cannot be read was not checked: --allow-partial does not cover it"
    assert "CANNOT READ" in text and "broken.zip" in text


def test_zip_nesting_depth_limit(source, tmp_path, capsys):
    data = (source / "reports" / "View - Set.xml").read_bytes()
    name = "content.xml"
    for _ in range(7):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(name, data)
        data, name = buf.getvalue(), "inner.zip"
    z = tmp_path / "deep.zip"
    z.write_bytes(data)
    rc, text = _run(z, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 1
    assert "nested more than 6 levels deep" in text


def test_pak_and_export_zip_inputs(source, tmp_path, capsys):
    """A packed .pak (pak > adapters.zip style nesting) and a content-export
    style zip (views.zip inside) are read like the directory."""
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as zf:
        zf.writestr("content.xml", (source / "reports" / "View - Set.xml").read_text())
    pak = tmp_path / "probe.pak"
    with zipfile.ZipFile(pak, "w") as zf:
        zf.writestr("content/reports/views.zip", inner.getvalue())
        zf.writestr("content/dashboards/Both.json", (source / "dashboards" / "Both.json").read_text())
        zf.writestr("content/supermetrics/SMs.json", (source / "supermetrics" / "SMs.json").read_text())
    rc, text = _run(pak, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--verify")
    assert rc == 0, text
    assert _files(tmp_path / "o", "dashboards") == ["probe-dashboard-a.yaml", "probe-dashboard-b.yaml"]


# ------------------------------------------------------------------ verify
@pytest.mark.parametrize("layout", ["third-party", "pak"])
def test_verify_round_trip_identical_through_layout_loader(source, tmp_path, capsys, layout):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", layout, "--ids", "keep", "--naming", "unprefixed", "--verify")
    assert "compared 14 object(s)" in text, text
    assert "14 identical" in text, text
    for t in ("view", "dashboard", "report", "alert", "symptom", "recommendation", "supermetric"):
        assert f"  {t:16s}" in text
    # documented non-differences are counted, not hidden
    assert "renumbered ids (widget)" in text
    if layout == "pak":
        # Section needs 9.1.1; the pak gate says so (reported, not converted
        # away), and a pak check failure is never accepted: nothing written.
        assert "PAK CHECK" in text and "Section" in text
        assert rc == 1
        assert not out.exists() and "nothing written to" in text
        rc, text = _run(source, out, capsys, "--layout", layout, "--ids", "keep", "--naming", "unprefixed",
                        "--allow-partial")
        assert rc == 1 and not out.exists(), "--allow-partial does not accept a pak check failure"
    else:
        assert rc == 0, text
        assert (out / "PROJECT.yaml").exists()
        assert (out / ".vcfcf-import-local").exists()


def test_verify_reports_differences_and_presence(tmp_path, capsys):
    """A source Property the schema cannot carry is reported as a loss and
    found by verify; an empty preferredUnitId is a documented class."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "v.xml").write_text(
        '<Content><Views><ViewDef id="7a000000-0000-4000-8000-0000000000bb"><Title>Probe Lossy</Title>'
        '<Description/><SubjectType adapterKind="VMWARE" resourceKind="HostSystem" type="descendant"/>'
        '<SubjectType adapterKind="VMWARE" resourceKind="HostSystem" type="self"/>'
        '<Usage>dashboard</Usage><Usage>report</Usage><Usage>details</Usage><Usage>content</Usage>'
        '<Controls><Control id="t" type="time-interval-selector" visible="false">'
        '<Property name="advancedTimeMode" value="false"/><Property name="unit" value="HOURS"/>'
        '<Property name="count" value="24"/></Control>'
        '<Control id="a" type="attributes-selector" visible="false"><Property name="attributeInfos"><List>'
        '<Item><Value><Property name="objectType" value="RESOURCE"/><Property name="attributeKey" value="cpu|x"/>'
        '<Property name="preferredUnitId" value=""/><Property name="isStringAttribute" value="false"/>'
        '<Property name="adapterKind" value="VMWARE"/><Property name="resourceKind" value="HostSystem"/>'
        '<Property name="rollUpType" value="AVG"/><Property name="rollUpCount" value="1"/>'
        '<Property name="transformations"><List><Item value="CURRENT"/></List></Property>'
        '<Property name="isProperty" value="false"/><Property name="displayName" value="X"/>'
        '<Property name="addTimestampAsColumn" value="false"/><Property name="isShowRelativeTimestamp" value="false"/>'
        '</Value></Item></List></Property></Control>'
        '<Control id="p" type="pagination-control" visible="true"><Property name="start" value="0"/>'
        '<Property name="size" value="500"/></Control>'
        '<Control id="m" type="metadata" visible="false"><Property name="maxPointsCount" value="5000"/>'
        '<Property name="hideObjectNameColumn" value="false"/><Property name="listTopResultSize" value="-1"/>'
        '<Property name="includeResourceCreationTime" value="false"/></Control></Controls>'
        '<DataProviders><DataProvider dataType="list-view" id="l"/></DataProviders>'
        '<Presentation type="list"/></ViewDef></Views></Content>')
    rc, text = _run(src, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--verify")
    assert rc == 1
    assert "LOSS view 'Probe Lossy': column 0: empty preferredUnitId is not modeled" in text
    # the loss is recorded at its exact path and accepted only there
    assert "Property{preferredUnitId}]" in text
    assert "0 identical" in text and "1 differ only at recorded losses" in text
    assert "ONLY RECORDED LOSSES views/probe-lossy.yaml" in text
    assert not (tmp_path / "o").exists()


def test_compare_counts_fields_and_presence_one_side():
    c = compare.Comparison()
    compare.diff_flat({"x.a": 1, "x.b.c": 2}, {"x.a": 1, "x.d": 3}, c, xml=False)
    assert c.fields == 3
    assert [(d.path, d.kind) for d in c.differences] == [("x.b.c", "missing"), ("x.d", "extra")]
    # exact: whitespace counts, a string is not a number, true is not 1
    c = compare.Comparison()
    compare.diff_flat({"a": "X ", "b": "1", "c": True}, {"a": "X", "b": 1, "c": 1}, c, xml=False)
    assert len(c.differences) == 3


def test_verify_exits_4_when_nothing_was_compared(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.xml").write_text("<packages/>")
    rc, text = _run(src, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--verify")
    assert rc == 4
    assert "compared nothing" in text


# ----------------------------------------------------------------- ids
def test_ids_keep_on_stock_id_fails_and_writes_nothing(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    y = tmp_path / "y.yaml"
    y.write_text(textwrap.dedent(SOURCE_YAML["v_lone.yaml"]).replace(V_LONE, STOCK_VIEW_ID))
    (src / "v.xml").write_text(render_views_xml([load_view(y, enforce_framework_prefix=False)]))
    out = tmp_path / "o"
    rc, text = _run(src, out, capsys, "--layout", "pak", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 3
    assert f"view id {STOCK_VIEW_ID}" in text and "--ids mint" in text
    assert not out.exists()
    rc, text = _run(src, out, capsys, "--layout", "pak", "--ids", "mint", "--mint-namespace", "probe", "--naming",
                    "unprefixed")
    assert rc == 0, text
    assert _yaml(out, "views/probe-unreferenced.yaml")["id"] != STOCK_VIEW_ID


def test_ids_mint_rewrites_every_reference_and_writes_the_map(source, tmp_path, capsys):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "mint", "--mint-namespace", "probe",
                    "--naming", "unprefixed", "--verify")
    assert rc == 0, text
    rows = [r.split("\t") for r in (out / "import-report" / "id_map.tsv").read_text().splitlines()[2:]]
    assert len(rows) == 14
    new = {r[1]: r[2] for r in rows}
    old_ids = {SM1, SM2, V_HOST, V_DIST, V_TREND, V_LONE, D_A, D_B, D_BARE, R_1}
    blob = "".join(p.read_text() for p in out.rglob("*.yaml"))
    for old in old_ids:
        assert new[old] != old
        assert old not in blob, f"old id {old} still in the output"
    # the widget's super metric wire key follows the minted super metric id
    score = _yaml(out, "dashboards/probe-dashboard-a.yaml")["widgets"][1]["metrics"][0]["metric_key"]
    assert score == f"Super Metric|sm_{new[SM1]}"
    # references by name are unchanged by minting
    assert _yaml(out, "supermetrics/probe-sm-two.yaml")["formula"].startswith('${this, metric=@supermetric:"Probe SM One"}')
    assert "14 identical" in text


def test_id_map_maps_some_and_keeps_the_rest(source, tmp_path, capsys):
    m = tmp_path / "map.tsv"
    new_view = "7b000000-0000-4000-8000-000000000001"
    m.write_text(f"old_id\tnew_id\n{V_HOST}\t{new_view}\n9f000000-0000-4000-8000-000000000000\t9f000000-0000-4000-8000-000000000001\n")
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--id-map", m, "--naming", "unprefixed", "--verify")
    assert rc == 0, text
    assert _yaml(out, "views/probe-host-list.yaml")["id"] == new_view
    assert _yaml(out, "views/probe-distribution.yaml")["id"] == V_DIST
    assert "WARNING: id map: 9f000000-0000-4000-8000-000000000000 names no object in the input" in text


def test_ids_decision_is_required(source, tmp_path, capsys):
    rc, text = _run(source, tmp_path / "o", capsys, "--layout", "third-party", "--naming", "unprefixed")
    assert rc == 2
    assert "--ids" in text


def test_drop_leaves_references_as_raw_ids(source, tmp_path, capsys):
    d = tmp_path / "drop.tsv"
    d.write_text(f"id\tname\n{V_HOST}\tProbe Host List\n")
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--drop", d, "--verify")
    assert rc == 0, text
    assert "probe-host-list.yaml" not in _files(out, "views")
    assert f"dropped (--drop): view {V_HOST}" in text
    assert _yaml(out, "dashboards/probe-dashboard-a.yaml")["widgets"][0]["view"] == V_HOST
    sections = _yaml(out, "reports/probe-report.yaml")["sections"]
    assert sections[2] == {"type": "View", "view_id": V_HOST, "orientation": "Portrait", "colorize": True}


# --------------------------------------------------------------- names
def test_factory_prefixed_naming_follows_every_reference(source, tmp_path, capsys):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "content", "--ids", "keep", "--naming", "factory-prefixed",
                    "--verify")
    assert rc == 0, text
    assert _yaml(out, "views/probe-host-list.yaml")["name"] == "[VCF CF] Probe Host List"
    d = _yaml(out, "dashboards/probe-dashboard-a.yaml")
    assert d["widgets"][0]["view"] == "[VCF CF] Probe Host List"
    assert d["widgets"][0]["navigations"][0]["dashboard"] == "[VCF CF] Probe Dashboard B"
    assert _yaml(out, "reports/probe-report.yaml")["sections"][4]["dashboard"] == "[VCF CF] Probe Dashboard A"
    a = _yaml(out, "alerts/probe-host-alert.yaml")
    assert a["symptom_sets"]["sets"][0]["symptoms"][0]["name"] == "[VCF CF] Probe CPU High"
    assert a["recommendations"][0]["name"] == "[VCF CF] probeRecommendationKey"
    assert _yaml(out, "supermetrics/probe-sm-two.yaml")["formula"].startswith('${this, metric=@supermetric:"[VCF CF] Probe SM One"}')
    assert 'supermetric:"[VCF CF] Probe SM One"' in (out / "views" / "probe-host-list.yaml").read_text()
    assert "name length: dashboards/probe-dashboard-a.yaml: 26 of 50 characters" in text
    assert "14 identical" in text


def test_content_layout_refuses_unprefixed_names(source, tmp_path, capsys):
    rc, text = _run(source, tmp_path / "o", capsys, "--layout", "content", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 2
    assert "--naming factory-prefixed" in text
    assert not (tmp_path / "o").exists()


def test_prefixed_dashboard_name_over_50_fails_with_rename_hint(source, tmp_path, capsys):
    r = tmp_path / "rename.tsv"
    r.write_text("dashboard\tProbe Bare\tProbe Bare With A Very Long Name That Will Not Fit\n")
    rc, text = _run(source, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "factory-prefixed", "--rename", r)
    assert rc == 1
    assert "FAILED dashboard" in text and "--rename" in text and "50" in text


def test_rename_by_name_and_by_id_applies_to_references(source, tmp_path, capsys):
    r = tmp_path / "rename.tsv"
    r.write_text(f"type\told\tnew\nview\tProbe Host List\tProbe Hosts Renamed\ndashboard\t{D_B}\tProbe Second\n")
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--rename", r, "--verify")
    assert rc == 0, text
    d = _yaml(out, "dashboards/probe-dashboard-a.yaml")
    assert d["widgets"][0]["view"] == "Probe Hosts Renamed"
    assert d["widgets"][0]["navigations"][0]["dashboard"] == "Probe Second"
    assert _yaml(out, "reports/probe-report.yaml")["sections"][2]["view"] == "Probe Hosts Renamed"


def test_two_objects_sharing_a_name_fail_naming_both(source, tmp_path, capsys):
    r = tmp_path / "rename.tsv"
    r.write_text(f"view\t{V_LONE}\tProbe Trend\n")
    rc, text = _run(source, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--rename", r)
    assert rc == 1
    assert "2 views share the name 'Probe Trend'" in text
    assert V_LONE in text and V_TREND in text


# ---------------------------------------------------------- duplicates
def test_differing_copies_stop_and_name_both_files_unless_told(source, tmp_path, capsys):
    src = tmp_path / "src"
    (src / "a").mkdir(parents=True)
    (src / "b").mkdir()
    one = (source / "resources" / "nested" / "extra.xml").read_text()
    (src / "a" / "first.xml").write_text(one)
    (src / "b" / "second.xml").write_text(one.replace("<Title>Probe Unreferenced</Title>", "<Title>Probe Changed</Title>"))
    rc, text = _run(src, tmp_path / "o1", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 1
    assert f"FAILED view {V_LONE}" in text and "a/first.xml" in text and "b/second.xml" in text
    assert "--prefer-source" in text
    rc, text = _run(src, tmp_path / "o2", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--prefer-source", "b/second")
    assert rc == 0, text
    # matched against the path relative to the input root: a fragment of
    # the input root itself matches both files and is an error
    rc, text = _run(src, tmp_path / "o3", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--prefer-source", ".xml")
    assert rc == 2 and "matches 2 of the files" in text
    rc, text = _run(src, tmp_path / "o4", capsys, "--layout", "third-party", "--ids", "keep", "--naming",
                    "unprefixed", "--prefer-source", "src/b")
    assert rc == 2 and "matches none of the files" in text
    assert _yaml(tmp_path / "o2", "views/probe-changed.yaml")["id"] == V_LONE


# ------------------------------------------------------------ versions
def test_target_min_drops_newer_omit_and_lists_the_deviation(source, tmp_path, capsys):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--target-min", "8.18.7", "--verify")
    # A Section dashboard is converted, not deliverable to 8.18.7 (W2): the
    # run exits non-zero and writes nothing; --allow-partial accepts it in a
    # third-party layout (never in a pak layout, test above).
    assert rc == 1 and not out.exists()
    assert "NOT DELIVERABLE to 8.18.7: dashboards/probe-dashboard-b.yaml" in text
    assert "widget w0 (Section) needs VCF Operations 9.1.1" in text
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--target-min", "8.18.7", "--allow-partial")
    assert rc == 0, text
    assert "omit" not in _yaml(out, "dashboards/probe-dashboard-a.yaml")
    assert "TARGET 8.18.7: dashboards/probe-dashboard-a.yaml" in text and "omit: temporary not emitted" in text
    assert "set aside only at dashboard.temporary" in text
    assert "dashboard: dashboard.temporary [extra]" in text  # forced, listed under deviations
    assert "1 identical apart from keys forced by --target-min" in text
    # Section is reported, not converted away
    assert any(w["type"] == "Section" for w in _yaml(out, "dashboards/probe-dashboard-b.yaml")["widgets"])


def test_without_target_reproduces_source_and_warns(source, tmp_path, capsys):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 0, text
    assert _yaml(out, "dashboards/probe-dashboard-a.yaml")["omit"] == ["temporary"]
    assert "omit: temporary reproduces the source, but its floor is 9.1.1" in text
    assert "(Section): needs VCF Operations 9.1.1 or later; on any build below it" in text


# -------------------------------------------------------------- safety
def test_refuses_non_empty_target_and_force_replaces_only_its_own_tree(source, tmp_path, capsys):
    """W7: --force replaces only a directory carrying the importer's marker,
    whole (no file of an earlier run is left behind); anything else is
    refused, with or without --force."""
    out = tmp_path / "out"
    (out / "views").mkdir(parents=True)
    (out / "views" / "probe-host-list.yaml").write_text("keep me\n")
    for extra in ((), ("--force",)):
        rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                        *extra)
        assert rc == 2 and "not empty" in text
        assert (out / "views" / "probe-host-list.yaml").read_text() == "keep me\n"
    assert "was not written by import-local" in text
    out2 = tmp_path / "out2"
    rc, text = _run(source, out2, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 0, text
    (out2 / "views" / "stale.yaml").write_text("id: x\nname: stale\n")
    (out2 / "PROJECT.yaml").write_text((out2 / "PROJECT.yaml").read_text() + "# edited attribution\n")
    rc, text = _run(source, out2, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 2 and "--force" in text
    rc, text = _run(source, out2, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed",
                    "--force")
    assert rc == 0, text
    assert not (out2 / "views" / "stale.yaml").exists()
    assert "# edited attribution" in (out2 / "PROJECT.yaml").read_text() and "KEPT" in text


def test_refuses_output_inside_input(source, tmp_path, capsys):
    rc, text = _run(source, source / "out", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 2 and "read only" in text


# --------------------------------------------------- mapping, per type
def test_view_fidelity_fields_are_mapped(source, tmp_path, capsys):
    out = tmp_path / "out"
    _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    h = _yaml(out, "views/probe-host-list.yaml")
    assert h["subject"]["types"] == ["descendant"]
    assert h["subject"]["filter"] == [[{"filter_type": "properties", "metric_key": "summary|version",
                                        "condition": "CONTAINS", "value": "8.0"}]]
    assert h["group_by"] == {"adapter_kind": "VMWARE", "resource_kind": "ClusterComputeResource"}
    assert h["usage"] == ["dashboard", "report", "content"] and h["top_n"] == 10
    c0, c1, c2 = h["columns"]
    assert (c0["sort"], c0["roll_up_unit"], c0["ascending_range"]) == ("desc", "HOURS", False)
    assert "roll_up_type" in c1["omit"] and "show_relative_timestamp" in c1["omit"]
    assert c2["attribute"] == 'supermetric:"Probe SM One"'
    assert h["summary"] == [{"display_name": "Total", "aggregation": "SUM", "columns": [0]}]
    d = _yaml(out, "views/probe-distribution.yaml")
    assert d["buckets"]["ranges"][1] == {"start": 25, "end": 100, "color": "DE3F30"}
    assert d["additional_columns"][0]["attribute"] == 'supermetric:"Probe SM Two"'
    assert d["distribution_color"] == "37B3EB" and d["page_size"] == 50
    t = _yaml(out, "views/probe-trend.yaml")
    assert t["transformations"] == ["NONE", "TREND", "FORECAST"] and t["forecast_days"] == 7
    assert set(t["omit"]) == {"pagination", "metadata"}


def test_dashboard_fidelity_fields_are_mapped(source, tmp_path, capsys):
    out = tmp_path / "out"
    _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    a = _yaml(out, "dashboards/probe-dashboard-a.yaml")
    assert (a["hidden"], a["time_range"], a["name_path"]) == (True, "last7Days", "Probe Folder")
    w = a["widgets"][0]
    assert w["ui"]["height"] == 324 and w["ui"]["states"] == [{"key": "perm_toolbarVisible_", "value": "b%3A0"}]
    assert w["navigations"][1] == {"dashboard_id": D_EXT}
    assert a["interactions"] == [{"from": "w0", "to": "w1", "type": "resourceId"}]
    b = _yaml(out, "dashboards/probe-dashboard-b.yaml")
    assert b["widgets"][0]["type"] == "Section" and b["widgets"][0]["widgets"] == ["w1", "w2"]
    bare = _yaml(out, "dashboards/probe-bare.yaml")
    assert bare["widgets"][0]["view"] == STOCK_VIEW_ID  # product view: raw id


def test_report_alert_symptom_supermetric_fields_are_mapped(source, tmp_path, capsys):
    out = tmp_path / "out"
    _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    r = _yaml(out, "reports/probe-report.yaml")
    assert r["sections"][0] == {"type": "CoverPage", "colorize": False, "font_color": "000000"}
    assert r["sections"][3] == {"type": "View", "view_id": STOCK_VIEW_ID, "omit": ["formatting"], "orientation": "Landscape"}
    assert r["sections"][4]["dashboard"] == "Probe Dashboard A"
    a = _yaml(out, "alerts/probe-host-alert.yaml")
    assert (a["id"], a["disable_in_base_policy"], a["criticality"]) == (A_1, True, "SYMPTOM_BASED")
    y = _yaml(out, "symptoms/probe-cpu-high.yaml")
    assert (y["symptom_def_type"], set(y["omit"])) == ("condition_self", {"wait_cycles", "cancel_cycles"})
    k = _yaml(out, "recommendations/probekey.yaml") if (out / "recommendations" / "probekey.yaml").exists() else \
        _yaml(out, "recommendations/proberecommendationkey.yaml")
    assert k["id"] == "probeRecommendationKey"
    s = _yaml(out, "supermetrics/probe-sm-one.yaml")
    assert s["resource_kinds"] == [{"resource_kind_key": "HostSystem", "adapter_kind_key": "VMWARE"}]


def test_alert_referencing_a_symptom_outside_the_set_fails(source, tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    text = (source / "alertdefs" / "Alert.xml").read_text()
    # keep the alert, remove its symptom definitions from the input
    import re
    text = re.sub(r"<SymptomDefinitions>.*</SymptomDefinitions>", "", text, flags=re.S)
    (src / "a.xml").write_text(text)
    rc, out_text = _run(src, tmp_path / "o", capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 1
    assert f"FAILED alert AlertDefinition-{A_1}" in out_text and "by name only" in out_text


# ------------------------------------------------------------- loaders
def test_third_party_project_report_names_its_own_views(source, tmp_path, capsys, monkeypatch):
    """The factory bundle loader resolves a PROJECT.yaml's report sections
    against the project's own views/ and dashboards/, not content/ under
    the working directory."""
    out = tmp_path / "proj"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 0, text
    monkeypatch.chdir(tmp_path)  # no content/ here
    from vcfcf_packaging.loader import load_bundle
    b = load_bundle(out / "PROJECT.yaml")
    sec = b.reports[0].sections[2]
    assert sec.view_name == "Probe Host List" and sec.view_id == V_HOST


def test_tsv_parsers():
    assert parse_tsv_map("old_id\tnew_id\nA\tB\tlabel\n# c\n\nC\tD\n", "m") == {"A": "B", "C": "D"}
    with pytest.raises(ValueError):
        parse_tsv_map("A\tB\nA\tC\n", "m")
    with pytest.raises(ValueError):
        parse_tsv_map("A\n", "m")
    assert parse_id_list("id\tname\nX\tone\nY\n", "d") == {"X": "one", "Y": ""}


def test_written_yaml_a_loader_refuses_fails_and_cascades(source, tmp_path, capsys):
    """An object whose YAML the loader refuses is not written; an object that
    names it fails too, so the written tree always loads."""
    src = tmp_path / "src"
    (src / "dashboards").mkdir(parents=True)
    xml = (source / "reports" / "View - Set.xml").read_text()
    # a summary row naming a column the view does not have: maps, but the view loader refuses it
    assert '<Item value="0"/></List></Property></Value></Item></List></Property>' in xml
    xml = xml.replace('<Item value="0"/></List></Property></Value></Item></List></Property>',
                      '<Item value="0"/><Item value="9"/></List></Property></Value></Item></List></Property>', 1)
    (src / "views.xml").write_text(xml)
    (src / "dashboards" / "Both.json").write_text((source / "dashboards" / "Both.json").read_text())
    (src / "sms.json").write_text((source / "supermetrics" / "SMs.json").read_text())
    out = tmp_path / "o"
    rc, text = _run(src, out, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed", "--verify",
                    "--allow-partial")
    assert rc == 0, text
    assert f"FAILED view {V_HOST} 'Probe Host List': the written YAML does not load" in text
    assert f"FAILED dashboard {D_A} 'Probe Dashboard A': the written YAML does not load" in text
    assert "probe-host-list.yaml" not in _files(out, "views")
    assert "probe-dashboard-a.yaml" not in _files(out, "dashboards")
    # the rest loads through the real third-party loader and verifies
    assert "LOAD ERROR" not in text


# ------------------------------------------------- the factory's own corpus
@pytest.mark.slow
def test_factory_corpus_renders_convert_back_identically(tmp_path, capsys):
    """Every view, dashboard, report, super metric, symptom, alert and
    recommendation under content/ is rendered by the factory, converted back
    by import-local into a content/ layout and verified through the factory
    loaders: the converter covers every widget type and field the factory's
    own content uses. Reads content/ only."""
    import warnings
    from vcfcf_core.alerts.loader import load_dir as load_alerts, load_recommendations
    from vcfcf_core.dashboards.loader import load_all
    from vcfcf_core.reports.loader import load_dir as load_reports
    from vcfcf_core.supermetrics.loader import load_dir as load_sms
    from vcfcf_core.symptoms.loader import load_dir as load_syms
    repo = Path(__file__).resolve().parent.parent
    c = repo / "content"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sms = load_sms(c / "supermetrics")
        views, dashes = load_all(c / "views", c / "dashboards")
        reports = load_reports(c / "reports", c / "views", c / "dashboards")
        syms = load_syms(c / "symptoms")
        alerts = load_alerts(c / "alerts")
        recs = load_recommendations(c / "recommendations")
    src = tmp_path / "src"
    src.mkdir()
    sm_map = {s.name: s.id for s in sms}
    (src / "views.xml").write_text(render_views_xml(views, sm_map=sm_map))
    by_name = {v.name: v for v in views}
    for i, d in enumerate(dashes):
        env = json.loads(render_dashboards_bundle_json([d], by_name, "0", known_dashboards=dashes))
        (src / f"d{i}.json").write_text(json.dumps(env))
    (src / "reports.xml").write_text(render_report_xml(reports))
    (src / "alerts.xml").write_text(render_alert_content_xml(syms, alerts, recs))
    (src / "sms.json").write_text(json.dumps(_render_supermetrics_dict(type("B", (), {"supermetrics": sms})())))
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys, "--layout", "content", "--ids", "keep", "--naming", "factory-prefixed",
                    "--verify", "--allow-partial")
    n = len(views) + len(dashes) + len(reports) + len(sms) + len(syms) + len(alerts) + len(recs)
    assert f"compared {n} object(s)" in text, text
    assert f"{n} identical" in text, text


# -------------------------------------------- project boundary (dep walker)
def test_project_boundary_accepts_a_raw_external_view_id(source, tmp_path, capsys):
    """A converted third-party dashboard that names a product view by raw id
    (the external-view passthrough) passes the project-boundary walk; one
    that names its own project's view by raw id is still an error."""
    from vcfcf_packaging.project import check_project_membership
    proj = tmp_path / "third_party" / "probe-port"
    rc, text = _run(source, proj, capsys, "--layout", "third-party", "--ids", "keep", "--naming", "unprefixed")
    assert rc == 0, text
    from vcfcf_packaging.loader import load_bundle
    b = load_bundle(proj / "PROJECT.yaml")
    for o in b.dashboards + b.views:
        o.provenance = "probe-port"
    bare = next(d for d in b.dashboards if d.name == "Probe Bare")
    assert bare.widgets[0].view_name == STOCK_VIEW_ID
    errors = check_project_membership(b.dashboards, b.views, b.supermetrics, [], third_party_dir=tmp_path / "third_party")
    assert not [e for e in errors if "unknown view" in e], errors
    # the same widget naming the project's own view by raw id: by name is the rule
    bare.widgets[0].view_name = V_HOST
    errors = check_project_membership([bare], b.views, b.supermetrics, [], third_party_dir=tmp_path / "third_party")
    assert any("by its raw id" in e for e in errors), errors
