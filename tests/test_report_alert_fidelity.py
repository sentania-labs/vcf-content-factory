"""Report, alert, symptom and recommendation fidelity fields, and the Section
minimum-version gate for Tier 2 paks (2026-11-12).

Synthetic fixtures only. Wire formats:
knowledge/context/wire-formats/template_fidelity_wire_format.md (report templates),
knowledge/context/wire-formats/alert_fidelity_wire_format.md,
knowledge/context/wire-formats/dashboard_fidelity_wire_format.md §Section.
"""
from __future__ import annotations

import sys
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.alerts.loader import (  # noqa: E402
    AlertValidationError, load_file as load_alert, load_recommendation_file,
)
from vcfcf_core.alerts.render import render_alert_content_xml  # noqa: E402
from vcfcf_core.reports.loader import ReportValidationError, load_file as load_report  # noqa: E402
from vcfcf_core.reports.render import render_report_xml  # noqa: E402
from vcfcf_core.symptoms.loader import SymptomValidationError, load_file as load_sym  # noqa: E402

REPORT_ID = "1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9"
OWN_VIEW_ID = "2c3d4e5f-6071-4829-93a4-b5c6d7e8f9a0"
BUILTIN_VIEW_ID = "3d4e5f60-7182-4930-a4b5-c6d7e8f9a0b1"
BUILTIN_DASH_ID = "4e5f6071-8293-4a41-b5c6-d7e8f9a0b1c2"
ALERT_ID = "5f607182-93a4-4b52-86d7-e8f9a0b1c2d3"
SYM_ID = "60718293-a4b5-4c63-97e8-f9a0b1c2d3e4"


# --- reports -----------------------------------------------------------------

def _report_env(tmp_path):
    views = tmp_path / "views"
    views.mkdir()
    (views / "v.yaml").write_text(yaml.safe_dump({"name": "Own View", "id": OWN_VIEW_ID}))
    dashes = tmp_path / "dashboards"
    dashes.mkdir()
    return views, dashes


def _report(tmp_path, sections, **extra):
    views, dashes = _report_env(tmp_path)
    data = {"id": REPORT_ID, "name": "Probe Report", "description": "",
            "subject_types": [{"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine", "type": "self"}],
            "sections": sections, "settings": {"show_page_footer": False, "output_formats": ["csv"]}}
    data.update(extra)
    p = tmp_path / "r.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return load_report(p, views, dashes, enforce_framework_prefix=False)


def _sections_xml(rd):
    root = ET.fromstring(render_report_xml([rd]))
    return root.find("Reports/ReportDef/Sections")


def test_cover_page_formatting(tmp_path):
    rd = _report(tmp_path, [{"type": "CoverPage", "colorize": False, "font_color": "000000"}])
    sec = _sections_xml(rd)[0]
    assert [c.tag for c in sec] == ["ContentType", "ContentKey", "ContentFormatting"]
    fmt = sec.find("ContentFormatting")
    assert [(c.tag, c.text) for c in fmt] == [("ColorizeListView", "false"), ("FontColor", "000000")]


def test_cover_page_without_formatting_is_unchanged(tmp_path):
    rd = _report(tmp_path, [{"type": "CoverPage"}, {"type": "TableOfContents"}])
    assert render_report_xml([rd]).count("<Section><ContentType>CoverPage</ContentType>"
                                         "<ContentKey>COVER_PAGE</ContentKey></Section>") == 1


@pytest.mark.parametrize("sec,match", [
    ({"type": "TableOfContents", "font_color": "000000"}, "only rendered on a CoverPage"),
    ({"type": "CoverPage", "font_color": "#000000"}, "six hex digits"),
    ({"type": "CoverPage", "colorize": "no"}, "colorize must be a bool"),
    ({"type": "View", "view": "Own View", "omit": ["formatting"], "colorize": True}, "contradicts colorize"),
    ({"type": "Dashboard", "dashboard_id": BUILTIN_DASH_ID, "colorize": True}, "not rendered on a Dashboard"),
    ({"type": "View", "view": "Own View", "omit": ["layout"]}, "omit accepts only"),
    ({"type": "CoverPage", "omit": ["formatting"]}, "View sections only"),
])
def test_section_negatives(tmp_path, sec, match):
    with pytest.raises(ReportValidationError, match=match):
        _report(tmp_path, [sec])


def test_view_section_without_formatting(tmp_path):
    rd = _report(tmp_path, [{"type": "View", "view": "Own View", "omit": ["formatting"]}])
    assert [c.tag for c in _sections_xml(rd)[0]] == ["ContentType", "ContentKey", "ContentOrientation"]


def test_builtin_view_and_dashboard_by_id(tmp_path):
    rd = _report(tmp_path, [
        {"type": "View", "view_id": BUILTIN_VIEW_ID, "orientation": "Portrait"},
        {"type": "Dashboard", "dashboard_id": BUILTIN_DASH_ID},
    ])
    secs = _sections_xml(rd)
    assert secs[0].findtext("ContentKey") == BUILTIN_VIEW_ID
    assert secs[1].findtext("ContentKey") == BUILTIN_DASH_ID
    assert all(s.external for s in rd.sections)


@pytest.mark.parametrize("sec,match", [
    ({"type": "View", "view_id": OWN_VIEW_ID}, "this project's own view 'Own View'"),
    ({"type": "View", "view": "Own View", "view_id": BUILTIN_VIEW_ID}, "exactly one of"),
    ({"type": "View", "view_id": "not-a-uuid"}, "must be a UUID"),
])
def test_raw_id_negatives(tmp_path, sec, match):
    with pytest.raises(ReportValidationError, match=match):
        _report(tmp_path, [sec])


def test_report_without_subject_types(tmp_path):
    rd = _report(tmp_path, [{"type": "CoverPage"}], subject_types=[])
    assert "<SubjectType" not in render_report_xml([rd])


def test_report_with_null_subject_types_still_fails(tmp_path):
    with pytest.raises(ReportValidationError, match="at least one subject_type"):
        _report(tmp_path, [{"type": "CoverPage"}], subject_types=None)


def test_discrete_builder_does_not_bundle_an_external_section(tmp_path):
    from vcfcf_packaging.discrete_builder import _resolve_report_deps
    rd = _report(tmp_path, [{"type": "View", "view_id": BUILTIN_VIEW_ID},
                            {"type": "View", "view": "Own View"}])
    from types import SimpleNamespace
    own = SimpleNamespace(name="Own View", id=OWN_VIEW_ID, columns=[], additional_columns=[])
    views, dashes, sms = _resolve_report_deps(rd, [own], [], [])
    assert [v.name for v in views] == ["Own View"]


# --- alerts and recommendations ----------------------------------------------

def _alert(tmp_path, **extra):
    data = {"name": "Probe Alert", "adapter_kind": "VMWARE", "resource_kind": "HostSystem",
            "type": 15, "sub_type": 19, "criticality": "WARNING", "impact": {"badge": "HEALTH"},
            "symptom_sets": {"operator": "ALL", "sets": [{"defined_on": "SELF", "operator": "ALL",
                                                          "symptoms": [{"name": "Probe Symptom"}]}]}}
    data.update(extra)
    p = tmp_path / "a.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return load_alert(p, enforce_framework_prefix=False)


def _symptom(tmp_path, **extra):
    data = {"name": "Probe Symptom", "adapter_kind": "VMWARE", "resource_kind": "HostSystem",
            "severity": "WARNING", "id": SYM_ID,
            "condition": {"type": "metric_static", "key": "cpu|usage_average", "operator": "GT", "value": 90}}
    data.update(extra)
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return load_sym(p, enforce_framework_prefix=False)


def _rec(tmp_path, **extra):
    data = {"name": "Probe Rec", "description": "Do the thing.", "adapter_kind": "VMWARE"}
    data.update(extra)
    p = tmp_path / "rec.yaml"
    p.write_text(yaml.safe_dump(data))
    return load_recommendation_file(p, enforce_framework_prefix=False)


def _alert_el(tmp_path, alert, recs=()):
    root = ET.fromstring(render_alert_content_xml([_symptom(tmp_path)], [alert], list(recs)))
    return root, root.find("AlertDefinitions/AlertDefinition")


def test_alert_explicit_id_and_disable_in_base_policy(tmp_path):
    root, ad = _alert_el(tmp_path, _alert(tmp_path, id=ALERT_ID, disable_in_base_policy=True))
    assert ad.get("id") == f"AlertDefinition-{ALERT_ID}"
    assert ad.get("disableInBasePolicy") == "true"


def test_alert_defaults_unchanged(tmp_path):
    root, ad = _alert_el(tmp_path, _alert(tmp_path))
    assert ad.get("id") == "AlertDefinition-VMWARE-Probe_Alert"
    assert not {"disableInBasePolicy", "waitCycle", "cancelCycle"} & set(ad.attrib)


def test_alert_cycles_written_only_when_not_one(tmp_path):
    _, ad = _alert_el(tmp_path, _alert(tmp_path, wait_cycles=2, cancel_cycles=3))
    assert (ad.get("waitCycle"), ad.get("cancelCycle")) == ("2", "3")
    _, ad = _alert_el(tmp_path, _alert(tmp_path, wait_cycles=1, cancel_cycles=1))
    assert ad.get("waitCycle") is None and ad.get("cancelCycle") is None


@pytest.mark.parametrize("extra,match", [
    ({"id": "AlertDefinition-x"}, "id must be a UUID"),
    ({"disable_in_base_policy": "true"}, "must be a bool"),
])
def test_alert_negatives(tmp_path, extra, match):
    with pytest.raises(AlertValidationError, match=match):
        _alert(tmp_path, **extra)


def test_alert_to_wire_refuses_xml_only_field(tmp_path):
    a = _alert(tmp_path, disable_in_base_policy=True)
    with pytest.raises(AlertValidationError, match="content-import XML path"):
        a.to_wire({"Probe Symptom": "sid"})
    assert _alert(tmp_path, id=ALERT_ID).to_wire({"Probe Symptom": "sid"})["name"] == "Probe Alert"


def test_recommendation_explicit_id_is_key_and_ref(tmp_path):
    rec = _rec(tmp_path, id="probeRecommendationKey")
    root, ad = _alert_el(tmp_path, _alert(tmp_path, recommendations=[{"name": "Probe Rec", "priority": 1}]), [rec])
    assert ad.find("State/Recommendations/Recommendation").get("ref") == "probeRecommendationKey"
    assert root.find("Recommendations/Recommendation").get("key") == "probeRecommendationKey"


def test_recommendation_default_key_unchanged(tmp_path):
    rec = _rec(tmp_path)
    root, _ = _alert_el(tmp_path, _alert(tmp_path, recommendations=[{"name": "Probe Rec", "priority": 1}]), [rec])
    assert root.find("Recommendations/Recommendation").get("key") == "Recommendation-df-VMWARE-Probe_Rec"


@pytest.mark.parametrize("bad", ["has space", "1starts-with-digit", "", 5])
def test_recommendation_id_negatives(tmp_path, bad):
    with pytest.raises(AlertValidationError, match="recommendation key"):
        _rec(tmp_path, id=bad)


# --- symptoms ----------------------------------------------------------------

def _sym_el(s):
    return ET.fromstring(render_alert_content_xml([s], [], [])).find("SymptomDefinitions/SymptomDefinition")


def test_symptom_fidelity_fields(tmp_path):
    s = _symptom(tmp_path, disable_in_base_policy=True, symptom_def_type="condition_self",
                 omit=["wait_cycles", "cancel_cycles", "instanced"])
    el = _sym_el(s)
    assert el.get("disableInBasePolicy") == "true" and el.get("symptomDefType") == "condition_self"
    assert el.get("waitCycle") is None and el.get("cancelCycle") is None
    assert "instanced" not in el.find("State/Condition").attrib


def test_symptom_defaults_unchanged(tmp_path):
    el = _sym_el(_symptom(tmp_path))
    assert el.get("waitCycle") == "1" and el.get("cancelCycle") == "1"
    assert el.find("State/Condition").get("instanced") == "false"
    assert not {"disableInBasePolicy", "symptomDefType"} & set(el.attrib)


@pytest.mark.parametrize("extra,match", [
    ({"symptom_def_type": "condition_other"}, "symptom_def_type must be one of"),
    ({"omit": ["severity"]}, "omit accepts"),
    ({"omit": ["wait_cycles"], "wait_cycles": 3}, "needs wait_cycles: 1"),
    ({"omit": ["instanced"], "condition": {"type": "metric_static", "key": "k", "operator": "GT",
                                           "value": 1, "instanced": True}}, "contradicts instanced"),
    ({"omit": ["instanced"], "condition": {"type": "metric_dynamic", "key": "k", "direction": "ABOVE"}},
     "metric_static and property"),
    ({"disable_in_base_policy": 1}, "must be a bool"),
])
def test_symptom_negatives(tmp_path, extra, match):
    with pytest.raises(SymptomValidationError, match=match):
        _symptom(tmp_path, **extra)


@pytest.mark.parametrize("extra", [{"disable_in_base_policy": True}, {"symptom_def_type": "condition_population"}])
def test_symptom_to_wire_refuses_xml_only_fields(tmp_path, extra):
    with pytest.raises(SymptomValidationError, match="content-import XML path"):
        _symptom(tmp_path, **extra).to_wire()


# --- Section minimum version: Tier 2 pak gate -------------------------------

def _section_dash(tmp_path):
    (tmp_path / "dashboards").mkdir(exist_ok=True)
    p = tmp_path / "dashboards" / "d.yaml"
    p.write_text(yaml.safe_dump({
        "id": "0f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a4b", "name": "Section Probe", "description": "",
        "widgets": [{"id": "sec", "type": "Section", "title": "Head", "coords": {"x": 1, "y": 1}},
                    {"id": "t", "type": "TextDisplay", "title": "T", "coords": {"x": 1, "y": 2, "w": 4, "h": 2},
                     "text": "hi"}]}))
    return p


def test_oldest_supported_line_is_the_rule_019_floor():
    from vcfcf_managementpacks.sdk_builder import _oldest_supported_line
    assert _oldest_supported_line() == "8.18.7"


def test_sdk_pak_build_refuses_a_section_dashboard(tmp_path):
    from vcfcf_managementpacks.sdk_builder import SdkBuildError, _load_bundled_content
    _section_dash(tmp_path)
    raw = {"bundled_content": {"dashboards": ["dashboards/d.yaml"]}}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(SdkBuildError, match=r"Section Probe.*Section.*9\.1\.1.*8\.18\.7"):
            _load_bundled_content(raw, tmp_path, tmp_path)


def test_dashboard_version_problems_against_a_target(tmp_path):
    from vcfcf_core.dashboards.loader import load_dashboard
    d = load_dashboard(_section_dash(tmp_path), enforce_framework_prefix=False)
    assert d.widget_version_problems("9.1.1") == []
    assert len(d.widget_version_problems("9.0.2")) == 1


def test_no_target_warning_names_the_dashboard(tmp_path):
    from vcfcf_core.dashboards.loader import load_all
    _section_dash(tmp_path)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_all(tmp_path / "views", tmp_path / "dashboards", enforce_framework_prefix=False)
    msgs = [str(w.message) for w in caught if "issue #199" in str(w.message)]
    assert len(msgs) == 1 and "dashboard 'Section Probe'" in msgs[0]
