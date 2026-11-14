"""Pak content that the installer drops silently (2026-11-14).

Two defects of the vCommunity Java pak 0.0.0.15 passed every check and were
found only in the appliance logs after a "successful" install on 9.0.2 and
9.1.1 (knowledge/context/investigations/2026-11-14-pak-content-silent-drops.md):

A. A view column with no display name got ``view.<id>.<key>=`` (an empty
   value) in ``content/reports/<dir>/resources/content.properties``; the
   content schema gives the value minLength 1, so the whole directory (the
   view, or a report and every view it embeds) failed to import.
B. Every symptom was written twice, in ``content/symptomdefs/`` and inside
   its alert's ``content/alertdefs/`` file; on 9.0.2 the second definition
   fails (duplicate key) and the alert loses its conditions.

Synthetic fixtures only (no third-party content). The pak is built through
``build_sdk_pak`` with the Java steps stubbed, and through ``validate-sdk``.
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core import java_properties  # noqa: E402
from vcfcf_core.packaging import pak_content  # noqa: E402
import vcfcf_managementpacks.sdk_builder as sb  # noqa: E402

KIND = "gate_probe"
P = "[VCF CF] "

VIEW_ID = "0f0f0f0f-1111-4222-8333-444455556666"
REPORT_ID = "1e1e1e1e-2222-4333-8444-555566667777"
SYM_SHARED = "2d2d2d2d-3333-4444-8555-666677778888"
COND_A = "3c3c3c3c-4444-4555-8666-777788889999"
COND_B = "4b4b4b4b-5555-4666-8777-88889999aaaa"

_DESCRIBE = """\
<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema" key="gate_probe"
             nameKey="1" version="1">
  <ResourceKinds>
    <ResourceKind key="gate_probe" nameKey="2" type="7"/>
    <ResourceKind key="GateWorld" nameKey="3" type="1"/>
  </ResourceKinds>
</AdapterKind>
"""

# A list view whose first column is the instanced-group driver with
# ``omit: [display_name]`` (Instance Name, no label: the shape the importer
# writes for a source column without displayName) and whose second column
# has a label; the description runs over two lines.
_VIEW = f"""\
id: {VIEW_ID}
name: "{P}Gate Host Licenses"
description: |-
  Licenses per host.
  Second line of the description.
data_type: list
presentation: list
subject:
  adapter_kind: VMWARE
  resource_kind: HostSystem
columns:
- instanced_group:
    name: GROUP_gate
    show_instance_name: true
    keep_instance_summary: true
  omit:
  - display_name
- attribute: "gate|Licensing:Edition|Key"
  display_name: "Edition"
  is_property: true
  is_string_attribute: true
- attribute: cpu|cpuModel
  is_property: true
  is_string_attribute: true
  omit:
  - display_name
"""

_REPORT = f"""\
id: {REPORT_ID}
name: "{P}Gate Host License Report"
description: "Report over the license view."
subject_types:
- adapter_kind: VMWARE
  resource_kind: HostSystem
  type: self
sections:
- type: View
  view: "{P}Gate Host Licenses"
"""


def _symptom(sid, name, value, condition_type=None):
    extra = f"symptom_def_type: {condition_type}\n" if condition_type else ""
    return (
        f'id: {sid}\nname: "{name}"\nadapter_kind: VMWARE\nresource_kind: HostSystem\n'
        f"severity: CRITICAL\n{extra}condition:\n  type: metric_static\n"
        f"  key: cpu|usage_average\n  operator: GT\n  value: {value}\n"
    )


def _alert(name, symptoms):
    syms = "".join(f'        - name: "{s}"\n' for s in symptoms)
    return (
        f'name: "{name}"\nadapter_kind: VMWARE\nresource_kind: HostSystem\n'
        f"type: 15\nsub_type: 19\ncriticality: CRITICAL\nimpact:\n  badge: HEALTH\n"
        f"symptom_sets:\n  operator: ANY\n  sets:\n"
        f"    - defined_on: SELF\n      operator: ALL\n      symptoms:\n{syms}"
    )


SHARED = f"{P}Gate CPU High"
CA = "Condition_gate_a"
CB = "Condition_gate_b"


def _project(tmp_path: Path) -> Path:
    """Synthetic pak project: the view above, a report over it, an alert with
    two inline conditions, and a standalone symptom two alerts reference."""
    d = tmp_path / "gate"
    files = {
        "views/licenses.yaml": _VIEW,
        "reports/licenses.yaml": _REPORT,
        "symptoms/shared.yaml": _symptom(SYM_SHARED, SHARED, 90),
        "symptoms/cond-a.yaml": _symptom(COND_A, CA, 30, "condition_self"),
        "symptoms/cond-b.yaml": _symptom(COND_B, CB, 60, "condition_self"),
        "alerts/conditions.yaml": _alert(f"{P}Gate License Expiring", [CA, CB]),
        "alerts/first.yaml": _alert(f"{P}Gate CPU First", [SHARED]),
        "alerts/second.yaml": _alert(f"{P}Gate CPU Second", [SHARED]),
        "describe.xml": _DESCRIBE,
        "src/Gate.java": "class Gate {}\n",
    }
    for rel, text in files.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text, encoding="utf-8")
    (d / "adapter.yaml").write_text(
        "\n".join([
            f"adapter_kind: {KIND}",
            "entry_class: com.vcfcf.adapters.gate.GateAdapter",
            "name: VCF Content Factory Gate Probe",
            "version: 0.1.0",
            "build_number: 1",
            "tier: 2",
            "released: false",
            "content_foreign_adapter_kinds: [VMWARE]",
            "bundled_content:",
            "  views: [views/licenses.yaml]",
            "  reports: [reports/licenses.yaml]",
            "  symptoms: [symptoms/shared.yaml, symptoms/cond-a.yaml, symptoms/cond-b.yaml]",
            "  alerts: [alerts/conditions.yaml, alerts/first.yaml, alerts/second.yaml]",
        ]) + "\n",
        encoding="utf-8",
    )
    return d


def _stub_java(monkeypatch):
    """Everything build_sdk_pak does with a JDK, replaced; the content path
    (_load_bundled_content to _write_outer_pak and its gate) is real."""
    def _jar(_tool, _build_dir, jar_path):
        jar_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(jar_path, "w") as z:
            z.writestr("adapter.properties", "x=1\n")

    monkeypatch.delenv("VCFCF_RELEASE_BUILD", raising=False)
    for name, fn in {
        "_detect_jdk": lambda: "javac",
        "_detect_jar_tool": lambda: "jar",
        "_check_run_sdk_jars": lambda *a, **k: [],
        "_ensure_framework_jar": lambda: None,
        "_framework_jar_label": lambda _p: "stub",
        "_build_classpath": lambda _pd: "",
        "_require_javac_reads_jar": lambda *a, **k: None,
        "_compile": lambda *a, **k: None,
        "_adapter_compat_inputs": lambda _pd, sources: (sources, []),
        "_sdk_compat_check": lambda *a, **k: None,
        "_write_adapter_properties": lambda *a, **k: None,
        "_package_adapter_jar": _jar,
        "_collect_lib_jars": lambda *a, **k: [],
        "_generate_docs": lambda *a, **k: None,
        "_gate_built_pak": lambda *a, **k: None,
    }.items():
        monkeypatch.setattr(sb, name, fn)


def _build(tmp_path, monkeypatch) -> Path:
    _stub_java(monkeypatch)
    return sb.build_sdk_pak(_project(tmp_path), tmp_path / "out")


def _members(pak: Path) -> dict:
    with zipfile.ZipFile(pak) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


# ---------------------------------------------------------------------------
# Defect A: localization bundles
# ---------------------------------------------------------------------------

def test_built_pak_has_no_empty_localization_value(tmp_path, monkeypatch):
    m = _members(_build(tmp_path, monkeypatch))
    bundles = [n for n in m if n.startswith("content/reports/") and n.endswith(".properties")]
    assert len(bundles) == 2, bundles  # the view's own directory and the report's
    for n in bundles:
        entries = java_properties.load_entries(m[n].decode("utf-8"))
        assert entries, n
        for _line, key, value in entries:
            assert key.startswith(f"view.{VIEW_ID}."), (n, key)
            assert value != "", (n, key)
        keys = {k for _l, k, _v in entries}
        # The labelled column keeps its entry; the two unlabelled ones have none.
        assert f"view.{VIEW_ID}.gate_LicensingEdition_Key" in keys
        assert f"view.{VIEW_ID}.Instance_Name" not in keys
        assert f"view.{VIEW_ID}.cpu_cpuModel" not in keys
        # The two-line description stays one entry, read back whole.
        values = {k: v for _l, k, v in entries}
        assert values[f"view.{VIEW_ID}.desc"] == (
            "Licenses per host.\nSecond line of the description.")


def test_view_xml_and_bundle_agree(tmp_path, monkeypatch):
    """No localizationKey in the XML, so no entry is missing for it, and the
    gate reads the built pak clean."""
    pak = _build(tmp_path, monkeypatch)
    m = _members(pak)
    for n, data in m.items():
        if n.startswith("content/reports/") and n.endswith(".xml"):
            assert b"localizationKey" not in data, n
    assert pak_content.check_pak_content(pak) == []


def test_gate_names_the_view_and_field_of_an_empty_value(tmp_path, monkeypatch):
    """The pre-fix bundle (an empty value) fails the build, naming the view
    and the key."""
    _stub_java(monkeypatch)
    real = sb._generate_view_content_properties
    monkeypatch.setattr(
        sb, "_generate_view_content_properties",
        lambda v: real(v) + f"view.{v.id}.Instance_Name=\n",
    )
    with pytest.raises(sb.PakContentGateError) as exc:
        sb.build_sdk_pak(_project(tmp_path), tmp_path / "out")
    text = str(exc.value)
    assert "Gate Host Licenses" in text and VIEW_ID in text
    assert "'Instance_Name' has an empty value" in text
    assert "left for inspection" in text


def test_release_build_deletes_a_pak_that_fails_the_gate(tmp_path, monkeypatch):
    _stub_java(monkeypatch)
    monkeypatch.setattr(sb, "_is_release_build", lambda: True)
    real = sb._generate_view_content_properties
    monkeypatch.setattr(
        sb, "_generate_view_content_properties",
        lambda v: real(v) + f"view.{v.id}.x=\n",
    )
    with pytest.raises(sb.PakContentGateError, match="removed"):
        sb.build_sdk_pak(_project(tmp_path), tmp_path / "out")
    assert not list((tmp_path / "out").glob("*.pak"))


def _pak_with(tmp_path, files: dict) -> Path:
    p = tmp_path / "t.pak"
    with zipfile.ZipFile(p, "w") as z:
        for n, t in files.items():
            z.writestr(n, t)
    return p


def _viewdef(vid, title="T", inner=""):
    return (f'<?xml version="1.0"?><Content><Views><ViewDef id="{vid}"><Title>{title}</Title>'
            f"{inner}</ViewDef></Views></Content>")


def test_gate_dangling_key_overlong_key_and_stray_line(tmp_path):
    vid = VIEW_ID
    p = _pak_with(tmp_path, {
        "content/reports/a/content.xml": _viewdef(
            vid, inner='<Description localizationKey="desc">d</Description>'),
        "content/reports/a/resources/content.properties": (
            f"view.{vid}.title=T\nview.{vid}.{'k' * 65}=v\nview.{vid}.ok=first line\nsecond\n"
            f"view.99999999-0000-4000-8000-000000000000.title=Other\n"),
    })
    errs = pak_content.check_pak_content(p)
    text = "\n".join(errs)
    assert "localizationKey='desc'" in text           # XML key with no entry
    assert "65 characters" in text                     # maxLength 64
    assert "'second' is not of the form" in text       # unescaped line break
    assert "which no ViewDef" in text                   # entry for a view not here
    assert len(errs) == 4, errs


def test_gate_dashboard_bundle_empty_value(tmp_path):
    p = _pak_with(tmp_path, {
        "content/dashboards/d/dashboard.json": '{"dashboards": [{"id": "d1", "name": "D"}]}',
        "content/dashboards/d/resources/resources.properties": "D=D\nD.w=\n",
    })
    errs = pak_content.check_pak_content(p)
    assert len(errs) == 1 and "'D.w' has an empty value" in errs[0]


def test_dashboard_bundle_skips_blank_titles_and_escapes():
    class W:
        def __init__(self, t):
            self.title = t

    class D:
        name = "Dash"
        widgets = [W(""), W("   "), W("Line\\Two")]

    text = sb._generate_dashboard_resources_properties(D(), "Folder")
    entries = java_properties.load_entries(text)
    assert [(k, v) for _l, k, v in entries] == [
        ("Folder", "Folder"), ("Dash", "Dash"), ("Dash.Line\\Two", "Line\\Two")]


# ---------------------------------------------------------------------------
# Defect B: each content id once
# ---------------------------------------------------------------------------

def test_each_symptom_defined_once_and_inline_conditions_stay_in_their_alert(tmp_path, monkeypatch):
    pak = _build(tmp_path, monkeypatch)
    m = _members(pak)
    defs, unreadable = pak_content.content_definitions(
        {n: d for n, d in m.items() if n.startswith("content/")})
    assert unreadable == []
    where = {}
    for d in defs:
        if d.type == "symptom":
            where.setdefault(d.id, []).append(d.location)
    assert sorted(where) == sorted(
        f"SymptomDefinition-{x}" for x in (SYM_SHARED, COND_A, COND_B))
    assert all(len(v) == 1 for v in where.values()), where
    # No standalone copies: every bundled symptom is referenced by an alert.
    assert not any(n.startswith("content/symptomdefs/") for n in m)
    alert_files = sorted(n for n in m if n.startswith("content/alertdefs/"))
    # The two alerts sharing a symptom are one file; the condition alert its own.
    assert len(alert_files) == 2, alert_files
    cond_file = where[f"SymptomDefinition-{COND_A}"][0]
    assert where[f"SymptomDefinition-{COND_B}"][0] == cond_file
    shared_file = where[f"SymptomDefinition-{SYM_SHARED}"][0]
    assert shared_file != cond_file
    shared = m[shared_file].decode()
    assert shared.count("<AlertDefinition ") == 2
    assert shared.count(f'ref="SymptomDefinition-{SYM_SHARED}"') == 2
    cond = m[cond_file].decode()
    assert cond.count("<AlertDefinition ") == 1
    assert 'symptomDefType="condition_self"' in cond
    assert f'ref="SymptomDefinition-{COND_A}"' in cond and f'ref="SymptomDefinition-{COND_B}"' in cond


def test_unreferenced_symptom_is_standalone(tmp_path):
    from vcfcf_symptoms.loader import load_file as load_sym
    p = tmp_path / "s.yaml"
    p.write_text(_symptom(SYM_SHARED, SHARED, 90), encoding="utf-8")
    groups, standalone = sb.plan_alert_content_files([load_sym(p)], [], [])
    assert groups == [] and [s.name for s in standalone] == [SHARED]


def test_gate_reports_both_locations_of_a_duplicate(tmp_path):
    sym = ('<alertContent><SymptomDefinitions><SymptomDefinition id="SymptomDefinition-x1" '
           'name="S" adapterKind="VMWARE" resourceKind="HostSystem"/></SymptomDefinitions></alertContent>')
    p = _pak_with(tmp_path, {
        "content/symptomdefs/S.xml": sym,
        "content/alertdefs/A.xml": sym,
    })
    errs = pak_content.check_pak_content(p)
    assert len(errs) == 1
    assert "SymptomDefinition-x1 ('S') is defined 2 times" in errs[0]
    assert "content/alertdefs/A.xml" in errs[0] and "content/symptomdefs/S.xml" in errs[0]


def test_identical_view_copies_in_report_dirs_pass_differing_ones_fail(tmp_path):
    same = _pak_with(tmp_path, {
        "content/reports/v/content.xml": _viewdef(VIEW_ID),
        "content/reports/r/content.xml": _viewdef(VIEW_ID),
    })
    assert pak_content.check_pak_content(same) == []
    (tmp_path / "t.pak").unlink()
    differ = _pak_with(tmp_path, {
        "content/reports/v/content.xml": _viewdef(VIEW_ID, "One"),
        "content/reports/r/content.xml": _viewdef(VIEW_ID, "Two"),
    })
    errs = pak_content.check_pak_content(differ)
    assert len(errs) == 1 and "copies differ" in errs[0]


def test_inventory_splits_conditions_from_symptoms(tmp_path, monkeypatch):
    inv = pak_content.read_pak_content_inventory(_build(tmp_path, monkeypatch))
    assert set(inv.views) == {VIEW_ID} and set(inv.reports) == {REPORT_ID}
    assert set(inv.symptoms) == {f"SymptomDefinition-{SYM_SHARED}"}
    assert set(inv.conditions) == {f"SymptomDefinition-{COND_A}", f"SymptomDefinition-{COND_B}"}
    assert len(inv.alerts) == 3
    refs = {a.name: a.symptom_refs for a in inv.alerts.values()}
    assert refs[f"{P}Gate License Expiring"] == [
        f"SymptomDefinition-{COND_A}", f"SymptomDefinition-{COND_B}"]


# ---------------------------------------------------------------------------
# validate-sdk catches both without a build
# ---------------------------------------------------------------------------

def _validate(d: Path, monkeypatch):
    monkeypatch.setattr(sb.shutil, "which", lambda _n: None)  # no compile leg
    monkeypatch.delenv("VCFCF_SDK_COMPAT_REQUIRED", raising=False)
    return [e for e in sb.validate_sdk_project(d) if "compat" not in e.lower()]


def test_validate_sdk_clean(tmp_path, monkeypatch):
    assert _validate(_project(tmp_path), monkeypatch) == []


def test_validate_sdk_reports_empty_value_and_duplicate(tmp_path, monkeypatch):
    real_props = sb._generate_view_content_properties
    monkeypatch.setattr(
        sb, "_generate_view_content_properties",
        lambda v: real_props(v) + f"view.{v.id}.Instance_Name=\n",
    )
    # The pre-fix layout: every symptom standalone too.
    real_plan = sb.plan_alert_content_files

    def _old_layout(symptoms, alerts, recs):
        groups, _ = real_plan(symptoms, alerts, recs)
        return groups, list(symptoms)

    monkeypatch.setattr(sb, "plan_alert_content_files", _old_layout)
    errs = _validate(_project(tmp_path), monkeypatch)
    assert any("pak content:" in e and "'Instance_Name' has an empty value" in e for e in errs)
    dups = [e for e in errs if "is defined 2 times" in e]
    assert len(dups) == 3, errs


def test_validate_sdk_shows_render_warnings(tmp_path, monkeypatch, capsys):
    """A condition symptom no alert references: the render's warning reaches
    the validate-sdk output (the per-file progress lines do not)."""
    d = _project(tmp_path)
    (d / "symptoms" / "orphan.yaml").write_text(
        _symptom("5a5a5a5a-6666-4777-8888-99990000aaaa", "Condition_orphan", 5,
                 "condition_self"), encoding="utf-8")
    text = (d / "adapter.yaml").read_text(encoding="utf-8").replace(
        "symptoms/cond-b.yaml]", "symptoms/cond-b.yaml, symptoms/orphan.yaml]")
    (d / "adapter.yaml").write_text(text, encoding="utf-8")
    assert _validate(d, monkeypatch) == []
    err = capsys.readouterr().err
    assert "symptom 'Condition_orphan' is an alert's inline condition" in err
    assert "bundled content: content/alertdefs/" not in err


# ---------------------------------------------------------------------------
# W3: alerts sharing only a recommendation keep separate files
# ---------------------------------------------------------------------------

def _alert_with_rec(name, symptoms, rec):
    return _alert(name, symptoms) + f'recommendations:\n  - name: "{rec}"\n    priority: 1\n'


def test_shared_recommendation_does_not_merge_alert_files(tmp_path, monkeypatch):
    rec = f"{P}Gate Fix It"
    d = _project(tmp_path)
    (d / "recommendations").mkdir()
    (d / "recommendations" / "fix.yaml").write_text(
        f'name: "{rec}"\ndescription: Do the thing.\nadapter_kind: VMWARE\n', encoding="utf-8")
    (d / "symptoms" / "other.yaml").write_text(
        _symptom("6b6b6b6b-7777-4888-8999-aaaabbbbcccc", f"{P}Gate Mem High", 80),
        encoding="utf-8")
    (d / "alerts" / "first.yaml").write_text(
        _alert_with_rec(f"{P}Gate CPU First", [SHARED], rec), encoding="utf-8")
    (d / "alerts" / "mem.yaml").write_text(
        _alert_with_rec(f"{P}Gate Mem Alert", [f"{P}Gate Mem High"], rec), encoding="utf-8")
    text = (d / "adapter.yaml").read_text(encoding="utf-8")
    text = text.replace("symptoms/cond-b.yaml]", "symptoms/cond-b.yaml, symptoms/other.yaml]")
    text = text.replace("alerts/second.yaml]", "alerts/second.yaml, alerts/mem.yaml]")
    text += "  recommendations: [recommendations/fix.yaml]\n"
    (d / "adapter.yaml").write_text(text, encoding="utf-8")
    _stub_java(monkeypatch)
    pak = sb.build_sdk_pak(d, tmp_path / "out")
    m = _members(pak)
    alert_files = sorted(n for n in m if n.startswith("content/alertdefs/"))
    # the conditions alert, the two CPU alerts (shared symptom), the memory alert
    assert len(alert_files) == 3, alert_files
    with_rec = [n for n in alert_files if b"<Recommendation " in m[n]]
    assert len(with_rec) == 2
    assert pak_content.check_pak_content(pak) == []


def _two_recs_project(tmp_path):
    """Codex P2 repro: alert groups [shared] and [shared, extra]. The
    renderer indents the last <Recommendation> differently from earlier
    siblings, so the shared copy's tail whitespace differs between files."""
    shared, extra = f"{P}Gate Fix It", f"{P}Gate Extra Step"
    d = _project(tmp_path)
    (d / "recommendations").mkdir()
    for fname, name in (("fix.yaml", shared), ("extra.yaml", extra)):
        (d / "recommendations" / fname).write_text(
            f'name: "{name}"\ndescription: Do {fname}.\nadapter_kind: VMWARE\n',
            encoding="utf-8")
    (d / "symptoms" / "other.yaml").write_text(
        _symptom("6b6b6b6b-7777-4888-8999-aaaabbbbcccc", f"{P}Gate Mem High", 80),
        encoding="utf-8")
    (d / "alerts" / "first.yaml").write_text(
        _alert_with_rec(f"{P}Gate CPU First", [SHARED], shared), encoding="utf-8")
    (d / "alerts" / "mem.yaml").write_text(
        _alert(f"{P}Gate Mem Alert", [f"{P}Gate Mem High"])
        + f'recommendations:\n  - name: "{shared}"\n    priority: 1\n'
        + f'  - name: "{extra}"\n    priority: 2\n', encoding="utf-8")
    text = (d / "adapter.yaml").read_text(encoding="utf-8")
    text = text.replace("symptoms/cond-b.yaml]", "symptoms/cond-b.yaml, symptoms/other.yaml]")
    text = text.replace("alerts/second.yaml]", "alerts/second.yaml, alerts/mem.yaml]")
    text += "  recommendations: [recommendations/fix.yaml, recommendations/extra.yaml]\n"
    (d / "adapter.yaml").write_text(text, encoding="utf-8")
    return d


def test_shared_recommendation_copies_with_different_indentation_pass(tmp_path, monkeypatch):
    d = _two_recs_project(tmp_path)
    assert _validate(d, monkeypatch) == []
    _stub_java(monkeypatch)
    pak = sb.build_sdk_pak(d, tmp_path / "out")
    m = _members(pak)
    copies = [m[n] for n in m if n.startswith("content/alertdefs/")
              and b'key="Recommendation-df-' in m[n] and b"Gate_Fix_It" in m[n]]
    assert len(copies) == 2
    # The repro holds: the raw serializations differ (tail whitespace)...
    import xml.etree.ElementTree as ET
    raw = {ET.tostring(e) for c in copies for e in ET.fromstring(c).iter("Recommendation")
           if "Gate_Fix_It" in (e.get("key") or "")}
    assert len(raw) == 2
    # ...and the gate still reads them as one definition.
    assert pak_content.check_pak_content(pak) == []


def test_viewdef_copies_with_different_indentation_pass_but_different_content_fails(tmp_path):
    compact = _viewdef(VIEW_ID, inner="<Usage>report</Usage>")
    pretty = ('<?xml version="1.0"?>\n<Content>\n  <Views>\n'
              f'    <ViewDef id="{VIEW_ID}">\n      <Title>T</Title>\n'
              '      <Usage>report</Usage>\n    </ViewDef>\n'
              f'    <ViewDef id="{REPORT_ID}"><Title>Other</Title></ViewDef>\n'
              '  </Views>\n</Content>\n')
    ok = _pak_with(tmp_path, {"content/reports/v/content.xml": compact,
                              "content/reports/r/content.xml": pretty})
    assert pak_content.check_pak_content(ok) == []
    (tmp_path / "t.pak").unlink()
    differ = _pak_with(tmp_path, {
        "content/reports/v/content.xml": compact,
        "content/reports/r/content.xml": _viewdef(VIEW_ID, inner="<Usage>dashboard</Usage>")})
    errs = pak_content.check_pak_content(differ)
    assert len(errs) == 1 and "copies differ" in errs[0]


def test_canonical_form_keeps_attribute_values_and_text():
    import xml.etree.ElementTree as ET
    c = pak_content.canonical_definition
    a = ET.fromstring('<R key="k" a="1"><D>x</D></R>')
    assert c(a) == c(ET.fromstring('<R a="1" key="k">\n  <D>x</D>\n</R>'))  # order, layout
    assert c(a) != c(ET.fromstring('<R key="k" a="2"><D>x</D></R>'))       # attribute value
    assert c(a) != c(ET.fromstring('<R key="k" a="1"><D> x</D></R>'))      # significant text


def test_gate_recommendation_copies_identical_pass_differing_fail(tmp_path):
    def _f(desc):
        return ('<alertContent><Recommendations><Recommendation key="R1">'
                f"<Description>{desc}</Description></Recommendation>"
                "</Recommendations></alertContent>")
    ok = _pak_with(tmp_path, {"content/alertdefs/a.xml": _f("x"),
                              "content/alertdefs/b.xml": _f("x")})
    assert pak_content.check_pak_content(ok) == []
    (tmp_path / "t.pak").unlink()
    bad = _pak_with(tmp_path, {"content/alertdefs/a.xml": _f("x"),
                               "content/alertdefs/b.xml": _f("y")})
    errs = pak_content.check_pak_content(bad)
    assert len(errs) == 1 and "copies differ" in errs[0]


def test_duplicate_message_is_neutral(tmp_path):
    sm = '{"u1": {"name": "SM", "formula": "1"}}'
    p = _pak_with(tmp_path, {"content/supermetrics/a.json": sm,
                             "content/supermetrics/b.json": sm})
    errs = pak_content.check_pak_content(p)
    assert len(errs) == 1 and "Factory policy is one definition" in errs[0]
    assert "9.0.2" not in errs[0] and "duplicate key" not in errs[0]


# ---------------------------------------------------------------------------
# N1, N2: properties escaping, read back by the Properties reader
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "#Dash: a=b c", "!bang", "tab\there", "line\nbreak", "cr\rlf", "ff\fx",
    " leading", "back\\slash", "Grüße", "日本", "emoji \U0001F600", "a b",
])
def test_properties_keys_and_values_read_back_exactly(text):
    out = sb._render_properties([(text, text), (f"{text}.w", text)], "#hdr")
    assert out.isascii()
    assert [(k, v) for _l, k, v in java_properties.load_entries(out)] == [
        (text, text), (f"{text}.w", text)]


def test_dashboard_named_like_a_comment_keeps_its_entry():
    class W:
        title = "Widget"

    class D:
        name = "#Dash: a=b c"
        widgets = [W()]

    text = sb._generate_dashboard_resources_properties(D(), "")
    keys = [k for _l, k, _v in java_properties.load_entries(text)]
    assert keys == ["#Dash: a=b c", "#Dash: a=b c.Widget"]


def test_render_properties_refuses_an_entry_that_does_not_read_back(monkeypatch):
    monkeypatch.setattr(sb, "_java_properties_escape_value", lambda v: v)  # broken escaper
    with pytest.raises(sb.SdkBuildError, match="does not read back"):
        sb._render_properties([("k", "line\nbreak")], where="test bundle")


def test_java_properties_joins_escaped_surrogate_pairs():
    assert java_properties.unescape("\\ud83d\\ude00") == "\U0001F600"
    assert java_properties.unescape("\\ud83d") == "\ud83d"  # a lone one stays
