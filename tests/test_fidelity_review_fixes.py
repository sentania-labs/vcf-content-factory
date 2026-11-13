"""Fixes from the 2026-11-12 framework review of the dashboard, report and
alert fidelity branch
(knowledge/context/reviews/framework/dashboards-report-alert-fidelity-2026-11-12.md).

B1  bundle, discrete and release builds refuse XML-only alert fields.
B2  two definitions under one rendered id fail, case-insensitively.
W3  omit: version floors gate a Tier 2 pak build and warn elsewhere.
W4  load errors name the file and the dashboard / report / alert / symptom.
W5  raw-id view and dashboard references are checked against the baseline.
W7  symptom-set thresholds render (ANY / ALL) or are refused, never dropped.
W8  validate-sdk reports the version gates under their own label.
N1, N2, N3 as named on each test.

Synthetic fixtures, plus copies of one real factory bundle for the builders.
"""
from __future__ import annotations

import shutil
import sys
import textwrap
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.alerts.loader import (  # noqa: E402
    AlertValidationError, load_dir as load_alert_dir, load_file as load_alert,
    load_recommendation_file, load_recommendations,
)
from vcfcf_core.alerts.render import render_alert_content_xml, rendered_id_collisions  # noqa: E402
from vcfcf_core.dashboards.loader import DashboardValidationError, load_dashboard  # noqa: E402
from vcfcf_core.packaging.loader import BundleValidationError  # noqa: E402
from vcfcf_core.reports.loader import ReportValidationError, load_file as load_report  # noqa: E402
from vcfcf_core.stock_ids import guard  # noqa: E402
from vcfcf_core.symptoms.loader import (  # noqa: E402
    SymptomValidationError, load_dir as load_sym_dir, load_file as load_sym,
)

ALERT_ID = "5f607182-93a4-4b52-86d7-e8f9a0b1c2d3"
SYM_ID = "60718293-a4b5-4c63-97e8-f9a0b1c2d3e4"
DASH_ID = "6a1d2e3f-4b5c-4d6e-8f70-819a2b3c4d5e"
REPORT_ID = "1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9"
# Real ids from the committed stock baseline (src/vcfcf_core/stock_ids/).
STOCK_VIEW_ALL_LINES = "007501f6-a356-42b2-9b6b-2dbd536d8069"   # 8.18.7, 9.0.2, 9.1.1
STOCK_VIEW_NOT_818 = "01510388-a80f-454e-b3fb-674bddf63adf"     # 9.0.2, 9.1.1
STOCK_DASH_NOT_818 = "082cf6d5-c879-4d33-b202-11a7746bbd91"     # 9.0.2, 9.1.1
UNKNOWN_ID = "3d4e5f60-7182-4930-a4b5-c6d7e8f9a0b1"


def _write(p: Path, data) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return p


def _alert_data(name="Probe Alert", **extra):
    data = {"name": name, "adapter_kind": "VMWARE", "resource_kind": "HostSystem",
            "type": 15, "sub_type": 19, "criticality": "WARNING", "impact": {"badge": "HEALTH"},
            "symptom_sets": {"operator": "ALL", "sets": [{"defined_on": "SELF", "operator": "ALL",
                                                          "symptoms": [{"name": "Probe Symptom"}]}]}}
    data.update(extra)
    return data


def _sym_data(name="Probe Symptom", **extra):
    data = {"name": name, "adapter_kind": "VMWARE", "resource_kind": "HostSystem",
            "severity": "WARNING",
            "condition": {"type": "metric_static", "key": "cpu|usage_average", "operator": "GT", "value": 90}}
    data.update(extra)
    return data


def _rec_data(name="Probe Rec", **extra):
    return {"name": name, "description": "Do the thing.", "adapter_kind": "VMWARE", **extra}


def _alert(tmp_path, name="a.yaml", **extra):
    return load_alert(_write(tmp_path / name, _alert_data(**extra)), enforce_framework_prefix=False)


# ---------------------------------------------------------------------------
# B1: bundle, discrete and release builds refuse XML-only fields
# ---------------------------------------------------------------------------

_B1_BUNDLE = REPO_ROOT / "bundles" / "storage-path-monitoring.yaml"
_B1_ALERT = "content/alerts/cluster_storage_path_inconsistency.yaml"
_B1_SYMPTOM = "content/symptoms/cluster_storage_paths_inconsistent.yaml"
_B1_REC = "content/recommendations/investigate_storage_path_degradation.yaml"
# The factory name prefix as the repo's own content spells it, so these tests
# hold on either side of a prefix migration.
_PREFIX = yaml.safe_load((REPO_ROOT / _B1_ALERT).read_text(encoding="utf-8"))["name"].split("] ", 1)[0] + "] "


def _b1_repo(tmp_path, *, alert_extra=None, symptom_extra=None, rec_extra=None) -> Path:
    """A scratch repo holding one real bundle and its files, the alert,
    symptom or recommendation given the fields under test."""
    root = tmp_path / "repo"
    manifest = yaml.safe_load(_B1_BUNDLE.read_text(encoding="utf-8"))
    manifest["name"] = "b1-probe"
    for key in ("supermetrics", "symptoms", "alerts", "recommendations"):
        for rel in manifest.get(key) or []:
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / rel, dst)
    for rel, extra in ((_B1_ALERT, alert_extra), (_B1_SYMPTOM, symptom_extra), (_B1_REC, rec_extra)):
        if extra:
            data = yaml.safe_load((root / rel).read_text(encoding="utf-8"))
            data.update(extra)
            _write(root / rel, data)
    _write(root / "bundles" / "b1-probe.yaml", manifest)
    return root


_B1_CASES = [
    ({"alert_extra": {"disable_in_base_policy": True}}, _B1_ALERT, "disable_in_base_policy"),
    ({"alert_extra": {"id": ALERT_ID}}, _B1_ALERT, "sets id"),
    ({"symptom_extra": {"disable_in_base_policy": True}}, _B1_SYMPTOM, "disable_in_base_policy"),
    ({"rec_extra": {"id": "probeRecommendationKey"}}, _B1_REC, "sets id"),
]


@pytest.mark.parametrize("kw,culprit,field", _B1_CASES)
def test_bundle_build_refuses_xml_only_fields(tmp_path, monkeypatch, kw, culprit, field):
    from vcfcf_packaging.builder import build_bundle
    root = _b1_repo(tmp_path, **kw)
    monkeypatch.chdir(root)
    out = tmp_path / "dist"
    with pytest.raises(BundleValidationError) as exc:
        build_bundle(root / "bundles" / "b1-probe.yaml", out, live_describe=False, skip_audit=True)
    msg = str(exc.value)
    assert culprit in msg and field in msg
    assert "content-import XML path of a pak build" in msg
    assert not out.exists() or not list(out.rglob("*.zip"))


def test_bundle_build_without_the_fields_still_builds(tmp_path, monkeypatch):
    from vcfcf_packaging.builder import build_bundle
    root = _b1_repo(tmp_path)
    monkeypatch.chdir(root)
    assert build_bundle(root / "bundles" / "b1-probe.yaml", tmp_path / "dist",
                        live_describe=False, skip_audit=True).exists()


@pytest.mark.parametrize("field", ["disable_in_base_policy", "id"])
def test_discrete_build_refuses_xml_only_alert_fields(tmp_path, field):
    from vcfcf_packaging.discrete_builder import build_discrete
    proj = tmp_path / "third_party" / "probe"
    data = yaml.safe_load((REPO_ROOT / _B1_ALERT).read_text(encoding="utf-8"))
    data["name"] = _PREFIX + "B1 Discrete Probe Alert"
    data[field] = True if field == "disable_in_base_policy" else ALERT_ID
    _write(proj / "alerts" / "probe.yaml", data)
    out = tmp_path / "discrete"
    with pytest.raises(BundleValidationError) as exc:
        build_discrete("alert", data["name"], out, extra_search_dirs=[proj],
                       live_describe=False, skip_audit=True)
    assert "alerts/probe.yaml" in str(exc.value) and "content-import XML path of a pak build" in str(exc.value)
    assert not out.exists() or not list(out.rglob("*.zip"))


def test_release_build_refuses_xml_only_alert_fields(tmp_path, monkeypatch):
    from vcfcf_packaging.release_builder import build_release
    root = _b1_repo(tmp_path, alert_extra={"disable_in_base_policy": True})
    _write(root / "bundles" / "releases" / "b1-probe.yaml", {
        "name": "b1-probe", "version": "1.0", "release_date": "2026-11-12", "description": "probe",
        "release_notes": "", "deprecates": [],
        "artifacts": [{"source": "bundles/b1-probe.yaml", "headline": True}],
    })
    monkeypatch.chdir(root)
    out = tmp_path / "rel"
    with pytest.raises(BundleValidationError) as exc:
        build_release(root / "bundles" / "releases" / "b1-probe.yaml", out, skip_audit=True)
    assert _B1_ALERT in str(exc.value) and "content-import XML path of a pak build" in str(exc.value)
    assert not out.exists() or not list(out.rglob("*.zip"))


def test_payloads_name_every_offender(tmp_path):
    from vcfcf_core.packaging.assembly import xml_only_alert_field_problems
    alert = _alert(tmp_path, id=ALERT_ID, disable_in_base_policy=True)
    sym = load_sym(_write(tmp_path / "s.yaml", _sym_data(disable_in_base_policy=True)), enforce_framework_prefix=False)
    rec = load_recommendation_file(_write(tmp_path / "r.yaml", _rec_data(id="k1")), enforce_framework_prefix=False)
    problems = xml_only_alert_field_problems(SimpleNamespace(alerts=[alert], symptoms=[sym], recommendations=[rec]))
    assert len(problems) == 4
    assert "a.yaml" in problems[0] and "disable_in_base_policy, id" in problems[0]
    assert "s.yaml" in problems[1] and "r.yaml" in problems[2]


# ---------------------------------------------------------------------------
# B2: duplicate rendered ids; N2: id case kept; N3: Recommendation.id
# ---------------------------------------------------------------------------

def test_alert_load_dir_refuses_ids_differing_only_in_case(tmp_path):
    _write(tmp_path / "al" / "one.yaml", _alert_data("Probe One", id=ALERT_ID))
    _write(tmp_path / "al" / "two.yaml", _alert_data("Probe Two", id=ALERT_ID.upper()))
    with pytest.raises(AlertValidationError, match="duplicate alert id") as exc:
        load_alert_dir(tmp_path / "al", enforce_framework_prefix=False)
    assert "one.yaml" in str(exc.value) and "two.yaml" in str(exc.value)


def test_alert_id_case_is_kept(tmp_path):
    a = _alert(tmp_path, id=ALERT_ID.upper())
    xml = render_alert_content_xml([], [a], [])
    assert f'id="AlertDefinition-{ALERT_ID.upper()}"' in xml


def test_recommendation_explicit_key_equal_to_a_derived_key(tmp_path):
    _write(tmp_path / "rec" / "a.yaml", _rec_data("Probe Rec"))
    _write(tmp_path / "rec" / "b.yaml", _rec_data("Other Rec", id="recommendation-df-VMWARE-Probe_Rec"))
    with pytest.raises(AlertValidationError, match="duplicate recommendation id") as exc:
        load_recommendations(tmp_path / "rec", enforce_framework_prefix=False)
    assert "a.yaml" in str(exc.value) and "b.yaml" in str(exc.value)


def test_recommendation_id_property_returns_the_explicit_key(tmp_path):
    rec = load_recommendation_file(_write(tmp_path / "r.yaml", _rec_data(id="probeKey")),
                                   enforce_framework_prefix=False)
    assert rec.id == "probeKey"
    plain = load_recommendation_file(_write(tmp_path / "p.yaml", _rec_data()), enforce_framework_prefix=False)
    assert plain.id == "Recommendation-df-VMWARE-Probe_Rec"


def test_symptom_load_dir_refuses_a_duplicate_explicit_id(tmp_path):
    _write(tmp_path / "sy" / "one.yaml", _sym_data("Probe One", id=SYM_ID))
    _write(tmp_path / "sy" / "two.yaml", _sym_data("Probe Two", id=SYM_ID.upper()))
    with pytest.raises(SymptomValidationError, match="duplicate symptom id") as exc:
        load_sym_dir(tmp_path / "sy", enforce_framework_prefix=False)
    assert "one.yaml" in str(exc.value) and "two.yaml" in str(exc.value)


def test_render_refuses_collisions_across_directories(tmp_path):
    a = load_alert(_write(tmp_path / "x" / "a.yaml", _alert_data("Probe One", id=ALERT_ID)), enforce_framework_prefix=False)
    b = load_alert(_write(tmp_path / "y" / "a.yaml", _alert_data("Probe Two", id=ALERT_ID)), enforce_framework_prefix=False)
    with pytest.raises(ValueError, match="duplicate alert id"):
        render_alert_content_xml([], [a, b], [])
    # One definition listed twice is not a collision.
    assert rendered_id_collisions(alerts=[a, a]) == []


def test_bundle_payloads_refuse_collisions(tmp_path):
    from vcfcf_core.packaging.assembly import render_bundle_payloads
    s1 = load_sym(_write(tmp_path / "x" / "s.yaml", _sym_data("Probe One", id=SYM_ID)), enforce_framework_prefix=False)
    s2 = load_sym(_write(tmp_path / "y" / "s.yaml", _sym_data("Probe Two", id=SYM_ID)), enforce_framework_prefix=False)
    bundle = SimpleNamespace(name="probe", alerts=[], symptoms=[s1, s2], recommendations=[])
    with pytest.raises(BundleValidationError, match="duplicate symptom id"):
        render_bundle_payloads(bundle, sm_map={}, bundle_context="probe")


def test_pak_inline_symptoms_collide_across_alert_files(tmp_path):
    """A pak writes one alert file per alert, each with its symptoms inline,
    so no single render sees two symptoms from different alerts."""
    from vcfcf_managementpacks.sdk_builder import check_bundled_content_references
    s1 = load_sym(_write(tmp_path / "x" / "s.yaml", _sym_data("Probe One", id=SYM_ID)), enforce_framework_prefix=False)
    s2 = load_sym(_write(tmp_path / "y" / "s.yaml", _sym_data("Probe Two", id=SYM_ID)), enforce_framework_prefix=False)
    a1 = load_alert(_write(tmp_path / "a1.yaml", _alert_data(
        "Probe A1", symptom_sets={"operator": "ALL", "sets": [{"defined_on": "SELF", "operator": "ALL",
                                                               "symptoms": [{"name": "Probe One"}]}]})),
        enforce_framework_prefix=False)
    a2 = load_alert(_write(tmp_path / "a2.yaml", _alert_data(
        "Probe A2", symptom_sets={"operator": "ALL", "sets": [{"defined_on": "SELF", "operator": "ALL",
                                                               "symptoms": [{"name": "Probe Two"}]}]})),
        enforce_framework_prefix=False)
    errors = check_bundled_content_references([s1, s2], [a1, a2], [])
    assert any("duplicate symptom id" in e and "x/s.yaml" in e and "y/s.yaml" in e for e in errors)


# ---------------------------------------------------------------------------
# W3: omit: version floors
# ---------------------------------------------------------------------------

def _view_widget():
    return {"id": "v", "type": "View", "title": "V", "coords": {"x": 1, "y": 1, "w": 6, "h": 4},
            "view": STOCK_VIEW_ALL_LINES}


def _dash_file(tmp_path, **extra):
    return _write(tmp_path / "dashboards" / "d.yaml",
                  {"id": DASH_ID, "name": "Omit Probe", "description": "", "widgets": [_view_widget()], **extra})


def _load_dash(path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # The loader's own folder default, which factory validate and a pak's
        # _load_bundled_content also use (Codex P2 on PR 356).
        return load_dashboard(path, enforce_framework_prefix=False)


def test_omit_temporary_floor_is_9_1_1(tmp_path):
    d = _load_dash(_dash_file(tmp_path, omit=["temporary", "widget_interactions"]))
    problems = d.omit_version_problems("8.18.7")
    assert len(problems) == 2 and "omit: temporary" in problems[0] and "9.1.1" in problems[0]
    assert "d.yaml" in problems[0] and "Omit Probe" in problems[0]
    assert d.omit_version_problems("9.1.1") == []


def test_omit_entries_proven_on_8_18_7_pass_the_pak_gate(tmp_path):
    # Through the pak's own loader, with its own folder default: the gate
    # the test name claims (Codex P2 on PR 356).
    from vcfcf_managementpacks.sdk_builder import _load_bundled_content, check_bundled_version_floors
    _dash_file(tmp_path, name_path="", omit=["name_path"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bundled = _load_bundled_content({"bundled_content": {"dashboards": ["dashboards/d.yaml"]}},
                                        tmp_path, tmp_path)
    d = bundled[1][0]
    assert d.name_path == "" and d.omit == ["name_path"]
    assert check_bundled_version_floors(bundled) == []
    assert d.omit_version_problems("8.18.7") == []
    assert d.omit_version_problems() == []


def test_omit_folder_in_name_has_no_floor(tmp_path):
    d = _load_dash(_dash_file(tmp_path, name_path="Folder", omit=["folder_in_name"]))
    assert "absent from no product export" in d.omit_version_problems("9.1.1")[0]


def test_validate_warns_for_a_bundle(tmp_path):
    from vcfcf_core.dashboards.loader import load_all
    _dash_file(tmp_path, omit=["temporary"])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_all(tmp_path / "views", tmp_path / "dashboards", enforce_framework_prefix=False)
    assert any("omit: temporary" in str(w.message) for w in caught)


def test_sdk_gate_fails_on_an_omit_entry_above_the_oldest_line(tmp_path):
    from vcfcf_managementpacks.sdk_builder import _load_bundled_content, check_bundled_version_floors
    _dash_file(tmp_path, omit=["temporary"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bundled = _load_bundled_content({"bundled_content": {"dashboards": ["dashboards/d.yaml"]}},
                                        tmp_path, tmp_path)
    errors = check_bundled_version_floors(bundled)
    assert len(errors) == 1 and "d.yaml" in errors[0] and "omit: temporary" in errors[0]
    assert "RULE-019" in errors[0]


def test_symptom_and_report_floors_gate_the_same_way(tmp_path, monkeypatch):
    import vcfcf_core.reports.loader as rl
    import vcfcf_core.symptoms.loader as sl
    sym = load_sym(_write(tmp_path / "s.yaml", _sym_data(omit=["instanced"])), enforce_framework_prefix=False)
    assert sym.omit_version_problems("8.18.7") == []
    monkeypatch.setitem(sl.SYMPTOM_OMIT_MIN_OPS_VERSION, "instanced", (9, 1, 1))
    assert "omit: instanced" in sym.omit_version_problems("8.18.7")[0]
    views = tmp_path / "views"
    _write(views / "v.yaml", {"name": "Own View", "id": "2c3d4e5f-6071-4829-93a4-b5c6d7e8f9a0"})
    (tmp_path / "dashes").mkdir()
    rd = load_report(_write(tmp_path / "r.yaml", {
        "id": REPORT_ID, "name": "Omit Report", "description": "", "subject_types": [],
        "sections": [{"type": "View", "view": "Own View", "omit": ["formatting"]}]}),
        views, tmp_path / "dashes", enforce_framework_prefix=False)
    assert rd.omit_version_problems("8.18.7") == []
    monkeypatch.setitem(rl.SECTION_OMIT_MIN_OPS_VERSION, "formatting", None)
    assert "sections[0]" in rd.omit_version_problems("8.18.7")[0]


# ---------------------------------------------------------------------------
# W4: errors name the file and the object
# ---------------------------------------------------------------------------

def test_widget_error_names_file_and_dashboard(tmp_path):
    w = dict(_view_widget(), ui={"height": -3})
    p = _write(tmp_path / "d.yaml", {"id": DASH_ID, "name": "Named Probe", "description": "", "widgets": [w]})
    with pytest.raises(DashboardValidationError) as exc:
        load_dashboard(p, enforce_framework_prefix=False)
    assert str(exc.value).startswith(f"{p}: dashboard 'Named Probe': widget 'v': ui.height")


def test_report_section_error_names_file_and_report(tmp_path):
    (tmp_path / "v").mkdir()
    (tmp_path / "d").mkdir()
    p = _write(tmp_path / "r.yaml", {"id": REPORT_ID, "name": "Named Report", "subject_types": [],
                                     "sections": [{"type": "CoverPage", "font_color": "#00"}]})
    with pytest.raises(ReportValidationError) as exc:
        load_report(p, tmp_path / "v", tmp_path / "d", enforce_framework_prefix=False)
    assert str(exc.value).startswith(f"{p}: report 'Named Report': sections[0]")


def test_report_validate_error_names_the_file(tmp_path):
    (tmp_path / "v").mkdir()
    (tmp_path / "d").mkdir()
    p = _write(tmp_path / "r.yaml", {"id": REPORT_ID, "name": "Named Report", "subject_types": [],
                                     "sections": [{"type": "Nope"}]})
    with pytest.raises(ReportValidationError) as exc:
        load_report(p, tmp_path / "v", tmp_path / "d", enforce_framework_prefix=False)
    assert str(exc.value).startswith(f"{p}: Named Report: section type")


def test_alert_and_symptom_errors_name_the_file(tmp_path):
    with pytest.raises(AlertValidationError) as exc:
        _alert(tmp_path, criticality="LOUD")
    assert str(exc.value).startswith(str(tmp_path / "a.yaml"))
    p = _write(tmp_path / "s.yaml", _sym_data(severity="LOUD"))
    with pytest.raises(SymptomValidationError) as exc:
        load_sym(p, enforce_framework_prefix=False)
    assert str(exc.value).startswith(f"{p}: Probe Symptom: severity")


# ---------------------------------------------------------------------------
# W5: raw-id references against the stock baseline
# ---------------------------------------------------------------------------

LINES = ("8.18.7", "9.0", "9.1.1.0100")


def test_reference_warnings_unknown_and_missing_on_a_line():
    baseline = guard.load_baseline()
    refs = [("view", UNKNOWN_ID, "probe.yaml: a"), ("view", STOCK_VIEW_NOT_818, "probe.yaml: b"),
            ("view", STOCK_VIEW_ALL_LINES, "probe.yaml: c"), ("dashboard", STOCK_DASH_NOT_818.upper(), "probe.yaml: d")]
    plain = guard.reference_warnings(refs, baseline)
    assert len(plain) == 1 and plain[0].startswith("probe.yaml: a") and "not a known" in plain[0]
    pak = guard.reference_warnings(refs, baseline, LINES)
    assert len(pak) == 3
    assert "probe.yaml: b" in pak[1] and "absent from VCF Operations 8.18.7" in pak[1]
    assert "probe.yaml: d" in pak[2] and "8.18.7" in pak[2]


def test_report_and_dashboard_expose_their_raw_id_references(tmp_path):
    (tmp_path / "v").mkdir()
    (tmp_path / "d").mkdir()
    rd = load_report(_write(tmp_path / "r.yaml", {
        "id": REPORT_ID, "name": "Ref Report", "subject_types": [],
        "sections": [{"type": "View", "view_id": UNKNOWN_ID}, {"type": "Dashboard", "dashboard_id": STOCK_DASH_NOT_818}]}),
        tmp_path / "v", tmp_path / "d", enforce_framework_prefix=False)
    refs = rd.external_references()
    assert [(t, i) for t, i, _ in refs] == [("view", UNKNOWN_ID), ("dashboard", STOCK_DASH_NOT_818)]
    assert "r.yaml" in refs[0][2] and "sections[0] view_id" in refs[0][2]
    d = _load_dash(_dash_file(tmp_path))
    assert [(t, i) for t, i, _ in d.external_view_references()] == [("view", STOCK_VIEW_ALL_LINES)]
    assert d.external_view_references([STOCK_VIEW_ALL_LINES]) == []


def test_reports_validate_warns_on_an_unknown_view_id(tmp_path, monkeypatch, capsys):
    from vcfcf_reports import cli as rcli
    (tmp_path / "v").mkdir()
    (tmp_path / "d").mkdir()
    p = _write(tmp_path / "r.yaml", {"id": REPORT_ID, "name": _PREFIX + "Ref Report",
                                     "description": "probe", "subject_types": [],
                                     "sections": [{"type": "View", "view_id": UNKNOWN_ID}]})
    monkeypatch.chdir(REPO_ROOT)
    rc = rcli.cmd_validate(SimpleNamespace(paths=[str(p)], views_dir=str(tmp_path / "v"),
                                           dashboards_dir=str(tmp_path / "d"), profile=None))
    err = capsys.readouterr().err
    assert rc == 0 and "WARNING:" in err and UNKNOWN_ID in err and "r.yaml" in err


def test_sdk_reference_warnings_name_the_missing_line(tmp_path):
    from vcfcf_managementpacks.sdk_builder import bundled_reference_warnings
    (tmp_path / "v").mkdir()
    (tmp_path / "d").mkdir()
    rd = load_report(_write(tmp_path / "r.yaml", {
        "id": REPORT_ID, "name": "Ref Report", "subject_types": [],
        "sections": [{"type": "View", "view_id": STOCK_VIEW_NOT_818}]}),
        tmp_path / "v", tmp_path / "d", enforce_framework_prefix=False)
    warns = bundled_reference_warnings(([], [], [], [], [], [rd], []))
    assert len(warns) == 1 and "8.18.7" in warns[0] and "r.yaml" in warns[0]


# ---------------------------------------------------------------------------
# W7: symptom-set thresholds on the XML path
# ---------------------------------------------------------------------------

def _set_alert(tmp_path, **set_extra):
    s = {"defined_on": "CHILD", "operator": "ANY", "symptoms": [{"name": "Probe Symptom"}], **set_extra}
    return _alert(tmp_path, symptom_sets={"operator": "ALL", "sets": [s]})


@pytest.mark.parametrize("tt,wire", [("ANY", "any"), ("ALL", "all")])
def test_any_and_all_render_as_aggregation(tmp_path, tt, wire):
    xml = render_alert_content_xml([], [_set_alert(tmp_path, threshold_type=tt)], [])
    ss = ET.fromstring(xml).find("AlertDefinitions/AlertDefinition/State/SymptomSet")
    assert ss.get("aggregation") == wire and ss.get("applyOn") == "child"


def test_no_threshold_renders_no_aggregation(tmp_path):
    xml = render_alert_content_xml([], [_set_alert(tmp_path)], [])
    assert "aggregation" not in xml


@pytest.mark.parametrize("extra", [
    {"threshold_type": "COUNT", "threshold_value": 3},
    {"threshold_type": "PERCENT", "threshold_value": 25},
    {"threshold_type": "COUNT"},
    {"threshold_type": "ANY", "threshold_value": 1},
])
def test_count_percent_and_values_are_refused_on_xml(tmp_path, extra):
    a = _set_alert(tmp_path, **extra)
    with pytest.raises(ValueError, match="not rendered on the content-import XML path") as exc:
        render_alert_content_xml([], [a], [])
    assert "a.yaml" in str(exc.value) and "sets[0]" in str(exc.value)
    if "threshold_value" in extra:
        # The REST body still carries them (vcfcf_alerts sync).
        assert a.to_wire({"Probe Symptom": "sid"})["states"][0]["base-symptom-set"]["value"] == float(extra["threshold_value"])


def test_threshold_on_a_self_set_is_refused(tmp_path):
    a = _alert(tmp_path, symptom_sets={"operator": "ALL", "sets": [
        {"defined_on": "SELF", "operator": "ALL", "symptoms": [{"name": "Probe Symptom"}], "threshold_type": "ANY"}]})
    with pytest.raises(ValueError, match="SELF set"):
        render_alert_content_xml([], [a], [])


# ---------------------------------------------------------------------------
# W8: validate-sdk reports the version gate under its own label
# ---------------------------------------------------------------------------

def test_validate_sdk_reports_the_section_gate_and_keeps_checking(tmp_path):
    from vcfcf_managementpacks.sdk_builder import validate_sdk_project
    project = tmp_path / "probe_adapter"
    (project / "dashboards").mkdir(parents=True)
    (project / "src").mkdir()
    (project / "src" / "A.java").write_text("class A {}\n")
    (project / "adapter.yaml").write_text(textwrap.dedent("""\
        name: "Probe Adapter"
        version: "1.0.0"
        build_number: 1
        adapter_kind: "probe_kind"
        tier: 2
        content_naming: factory_prefixed
        bundled_content:
          dashboards:
            - dashboards/d.yaml
        """), encoding="utf-8")
    (project / "describe.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<AdapterKind key="probe_kind" nameKey="1" version="1">'
        '<ResourceKinds><ResourceKind key="probe_world" nameKey="2" type="1"/></ResourceKinds></AdapterKind>\n',
        encoding="utf-8")
    _write(project / "dashboards" / "d.yaml", {
        "id": DASH_ID, "name": "Unprefixed Section Probe", "description": "",
        "widgets": [{"id": "sec", "type": "Section", "title": "Head", "coords": {"x": 1, "y": 1}}]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        errors = validate_sdk_project(project)
    assert any(e.startswith("version floor: ") and "Section" in e for e in errors)
    assert not any("during localization check" in e for e in errors)
    # The naming contract still ran beside it (the dashboard is unprefixed).
    assert any("Unprefixed Section Probe" in e and not e.startswith("version floor") for e in errors)


# ---------------------------------------------------------------------------
# N1: resource_kind_name on a resource-mode Scoreboard
# ---------------------------------------------------------------------------

def test_resource_kind_name_rejected_in_resource_mode(tmp_path):
    w = {"id": "s", "type": "Scoreboard", "title": "S", "coords": {"x": 1, "y": 1, "w": 6, "h": 3},
         "metric_mode": "resource", "self_provider": True,
         "resource": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem", "name": "h1"},
         "metrics": [{"metric_key": "cpu|usage_average", "metric_name": "CPU", "resource_kind_name": "Host"}]}
    p = _write(tmp_path / "d.yaml", {"id": DASH_ID, "name": "N1 Probe", "description": "", "widgets": [w]})
    with pytest.raises(DashboardValidationError, match="resource_kind_name is not rendered with metric_mode: resource"):
        load_dashboard(p, enforce_framework_prefix=False)


# ---------------------------------------------------------------------------
# Codex P2 on PR 356: name_path: "" with omit: [name_path] through every real
# entry point, each with its own folder default; an absent name_path keeps
# that default.
# ---------------------------------------------------------------------------

_NP_DASH_ID = "7b2e3f40-5c6d-4e7f-8091-a2b3c4d5e6f7"


def _np_dash(name, **extra):
    return {"id": _NP_DASH_ID, "name": name, "description": "",
            "widgets": [{"id": "t", "type": "TextDisplay", "title": "T",
                         "coords": {"x": 1, "y": 1, "w": 4, "h": 2}, "text": "hi"}],
            "interactions": [], **extra}


_NO_FOLDER = {"name_path": "", "omit": ["name_path"]}


def _rendered(dashboard_json: str) -> dict:
    import json
    return json.loads(dashboard_json)["dashboards"][0]


def _pak_render(tmp_path, data):
    """The pak path: _load_bundled_content, then the dashboard.json and
    resources.properties _write_outer_pak writes (no Java, stub adapters.zip)."""
    import io
    import zipfile
    from vcfcf_managementpacks.sdk_builder import _load_bundled_content, _write_outer_pak
    from vcfcf_managementpacks.sdk_project import SdkProjectDef, _derive_entry_class
    _write(tmp_path / "dashboards" / "d.yaml", data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        v, d, sm, sy, al, rp, rc = _load_bundled_content(
            {"bundled_content": {"dashboards": ["dashboards/d.yaml"]}}, tmp_path, tmp_path)
    project = SdkProjectDef(
        name="VCF Content Factory Test", version="1.0.0", build_number=1, adapter_kind="test_adapter",
        description="Test", tier=2, dependencies=[], entry_class=_derive_entry_class("test_adapter"),
        source_path=tmp_path / "adapter.yaml",
    )
    stub = io.BytesIO()
    with zipfile.ZipFile(stub, "w") as z:
        z.writestr("stub.txt", "stub")
    out = tmp_path / "dist"
    out.mkdir()
    pak = _write_outer_pak(project, stub.getvalue(), out, tmp_path, views=v, dashboards=d,
                           owning_adapter_kind="test_adapter", owning_resource_kind="TestWorld")
    with zipfile.ZipFile(pak) as zf:
        dj = [n for n in zf.namelist() if n.endswith("/dashboard.json")]
        props = [n for n in zf.namelist() if n.startswith("content/dashboards/") and n.endswith("resources.properties")]
        assert len(dj) == 1 and len(props) == 1
        return d[0], _rendered(zf.read(dj[0]).decode()), zf.read(props[0]).decode()


def test_pak_build_loads_and_renders_an_explicitly_empty_omitted_folder(tmp_path):
    d, db, props = _pak_render(tmp_path, _np_dash("Folderless Probe", **_NO_FOLDER))
    assert d.name_path == ""
    assert "namePath" not in db and db["name"] == "Folderless Probe"
    assert "VCF Content Factory=" not in props


def test_pak_build_keeps_the_default_folder_for_an_absent_name_path(tmp_path):
    d, db, props = _pak_render(tmp_path, _np_dash("Foldered Probe"))
    assert d.name_path == "VCF Content Factory"
    assert db["namePath"] == "VCF Content Factory" and db["name"] == "VCF Content Factory/Foldered Probe"
    assert "VCF\\ Content\\ Factory=VCF Content Factory" in props


def test_pak_build_refuses_omit_name_path_without_the_explicit_empty_folder(tmp_path):
    from vcfcf_managementpacks.sdk_builder import SdkBuildError
    with pytest.raises(SdkBuildError, match="omit name_path needs an empty folder"):
        _pak_render(tmp_path, _np_dash("Folderless Probe", omit=["name_path"]))


def test_pak_gate_for_folder_omits_is_unchanged(tmp_path):
    # name_path is proven on 8.18.7 (passes the pak gate); folder_in_name has
    # no floor and still fails it.
    from vcfcf_managementpacks.sdk_builder import _load_bundled_content, check_bundled_version_floors
    for i, extra in enumerate((_NO_FOLDER, {"name_path": "Folder", "omit": ["folder_in_name"]})):
        root = tmp_path / str(i)
        _write(root / "dashboards" / "d.yaml", _np_dash("Gate Probe", **extra))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            bundled = _load_bundled_content({"bundled_content": {"dashboards": ["dashboards/d.yaml"]}}, root, root)
        errors = check_bundled_version_floors(bundled)
        if i == 0:
            assert errors == []
        else:
            assert len(errors) == 1 and "folder_in_name" in errors[0]


def test_factory_loader_and_validate_accept_an_explicitly_empty_omitted_folder(tmp_path):
    # The factory wrapper the dashboards CLI validate calls (load_all with
    # the "VCF Content Factory" default), on a file under content/.
    from vcfcf_dashboards import loader as factory
    content = tmp_path / "content"
    _write(content / "dashboards" / "none.yaml", _np_dash(_PREFIX + "Folderless Probe", **_NO_FOLDER))
    _write(content / "dashboards" / "dflt.yaml",
           {**_np_dash(_PREFIX + "Foldered Probe"), "id": "8c3f4051-6d7e-4f80-9102-b3c4d5e6f708"})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, dashes = factory.load_all(content / "views", content / "dashboards")
    by = {d.name: d for d in dashes}
    assert by[_PREFIX + "Folderless Probe"].name_path == ""
    assert by[_PREFIX + "Folderless Probe"].provenance == "factory"
    assert by[_PREFIX + "Foldered Probe"].name_path == "VCF Content Factory"


def test_dashboards_cli_validate_accepts_an_explicitly_empty_omitted_folder(tmp_path, monkeypatch, capsys):
    from vcfcf_dashboards import cli
    content = tmp_path / "content"
    _write(content / "dashboards" / "none.yaml", _np_dash(_PREFIX + "Folderless Probe", **_NO_FOLDER))
    (content / "views").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["--views-dir", str(content / "views"),
                   "--dashboards-dir", str(content / "dashboards"), "validate"])
    out = capsys.readouterr()
    assert rc == 0, out


def _bundle_repo(tmp_path, dash_rel, data, factory_native=True):
    root = tmp_path / "repo"
    _write(root / dash_rel, data)
    (root / "content").mkdir(parents=True, exist_ok=True)
    _write(root / "bundles" / "np-probe.yaml", {
        "name": "np-probe", "description": "probe", "factory_native": factory_native,
        "supermetrics": [], "views": [], "dashboards": [dash_rel], "customgroups": [], "reports": [],
    })
    return root


@pytest.mark.parametrize("dash_rel,name,factory_native", [
    ("content/dashboards/d.yaml", _PREFIX + "Folderless Probe", True),
    ("third_party/probe/dashboards/d.yaml", "Folderless Probe", False),
])
def test_bundle_render_honours_an_explicitly_empty_omitted_folder(tmp_path, monkeypatch, dash_rel, name,
                                                                   factory_native):
    from vcfcf_core.packaging.assembly import render_bundle_payloads
    from vcfcf_packaging.loader import load_bundle
    root = _bundle_repo(tmp_path, dash_rel, _np_dash(name, **_NO_FOLDER), factory_native)
    monkeypatch.chdir(root)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bundle = load_bundle(root / "bundles" / "np-probe.yaml")
        db = _rendered(render_bundle_payloads(bundle, sm_map={}, bundle_context="np").dashboard_json)
    assert "namePath" not in db and db["name"] == name


@pytest.mark.parametrize("dash_rel,name,factory_native,folder", [
    ("content/dashboards/d.yaml", _PREFIX + "Foldered Probe", True, "VCF Content Factory"),
    ("third_party/probe/dashboards/d.yaml", "Foldered Probe", False, ""),
])
def test_bundle_render_keeps_each_default_for_an_absent_name_path(tmp_path, monkeypatch, dash_rel, name,
                                                                   factory_native, folder):
    from vcfcf_core.packaging.assembly import render_bundle_payloads
    from vcfcf_packaging.loader import load_bundle
    root = _bundle_repo(tmp_path, dash_rel, _np_dash(name), factory_native)
    monkeypatch.chdir(root)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bundle = load_bundle(root / "bundles" / "np-probe.yaml")
        db = _rendered(render_bundle_payloads(bundle, sm_map={}, bundle_context="np").dashboard_json)
    assert db["namePath"] == folder
    assert db["name"] == (f"{folder}/{name}" if folder else name)


def test_discrete_build_honours_an_explicitly_empty_omitted_folder(tmp_path):
    import json
    import zipfile
    from vcfcf_packaging.discrete_builder import build_discrete
    proj = tmp_path / "third_party" / "probe"
    _write(proj / "dashboards" / "d.yaml", _np_dash(_PREFIX + "Folderless Discrete Probe", **_NO_FOLDER))
    out = tmp_path / "discrete"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        z = build_discrete("dashboard", _PREFIX + "Folderless Discrete Probe", out,
                           extra_search_dirs=[proj], live_describe=False, skip_audit=True)
    with zipfile.ZipFile(z) as zf:
        dj = [n for n in zf.namelist() if n.endswith("dashboard.json")]
        assert dj
        db = json.loads(zf.read(dj[0]))["dashboards"][0]
    assert "namePath" not in db and db["name"] == _PREFIX + "Folderless Discrete Probe"


def test_buildkit_copy_loads_and_renders_an_explicitly_empty_omitted_folder(tmp_path):
    """The kit's vendored loader and sdk_builder, imported with the factory
    packages off the path, as pak CI runs them."""
    import json
    import os
    import subprocess
    from vcfcf_managementpacks.buildkit import (
        _FACTORY_SOURCES, _IMPORT_REWRITES, _KIT_INIT, _KIT_MAIN, _apply_rewrites,
    )
    pkg = tmp_path / "kit" / "sdk_buildkit"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(_KIT_INIT, encoding="utf-8")
    (pkg / "__main__.py").write_text(_KIT_MAIN, encoding="utf-8")
    for dest, src in _FACTORY_SOURCES.items():
        if src.is_file():
            rules = _IMPORT_REWRITES.get(dest, [])
            if rules:
                (pkg / dest).write_text(_apply_rewrites(src.read_text(encoding="utf-8"), rules), encoding="utf-8")
            else:
                (pkg / dest).write_bytes(src.read_bytes())
    proj = tmp_path / "proj"
    _write(proj / "dashboards" / "a.yaml", _np_dash("Folderless Probe", **_NO_FOLDER))
    _write(proj / "dashboards" / "b.yaml",
           {**_np_dash("Foldered Probe"), "id": "8c3f4051-6d7e-4f80-9102-b3c4d5e6f708"})
    script = textwrap.dedent(f"""
        import json, sys, warnings
        from pathlib import Path
        warnings.simplefilter("ignore")
        from sdk_buildkit.sdk_builder import _load_bundled_content
        from sdk_buildkit.dashboard_render import render_dashboards_bundle_json
        root = Path({str(proj)!r})
        _, ds, *_ = _load_bundled_content(
            {{"bundled_content": {{"dashboards": ["dashboards/a.yaml", "dashboards/b.yaml"]}}}}, root, root)
        out = [json.loads(render_dashboards_bundle_json([d], {{}}, "0", known_dashboards=ds))["dashboards"][0]
               for d in ds]
        assert not any(m.startswith("vcfcf_") for m in sys.modules), "factory package imported"
        print(json.dumps([{{"name": o["name"], "namePath": o.get("namePath", "<absent>")}} for o in out]))
    """)
    repo_root = REPO_ROOT.resolve()
    pp = [e for e in os.environ.get("PYTHONPATH", "").split(os.pathsep)
          if e and Path(e).resolve() not in {repo_root, repo_root / "src"}]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(tmp_path / "kit"), *pp])}
    res = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                         cwd=str(tmp_path), env=env, timeout=60)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout.strip().splitlines()[-1]) == [
        {"name": "Folderless Probe", "namePath": "<absent>"},
        {"name": "VCF Content Factory/Foldered Probe", "namePath": "VCF Content Factory"},
    ]
