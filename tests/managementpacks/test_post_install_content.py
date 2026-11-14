"""Post-install content count (2026-11-14): views, reports, symptoms, alerts.

Fake clients replay the shapes read on the lab after the vCommunity Java
0.0.0.15 install: a condition symptom is 404 on /api/symptomdefinitions and
appears inside its alert as ``alertConditions[].id = "Condition-<x>"`` (9.1.1,
8.18.7); on 9.0.2 the alert's sets came back empty.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.packaging import pak_content  # noqa: E402
from vcfcf_managementpacks import post_install_content as pic  # noqa: E402

V1 = "11111111-1111-4111-8111-111111111111"
V2 = "22222222-2222-4222-8222-222222222222"
R1 = "33333333-3333-4333-8333-333333333333"
S1 = "SymptomDefinition-44444444-4444-4444-8444-444444444444"
C1 = "SymptomDefinition-55555555-5555-4555-8555-555555555555"
C2 = "SymptomDefinition-66666666-6666-4666-8666-666666666666"
A1 = "AlertDefinition-77777777-7777-4777-8777-777777777777"
A2 = "AlertDefinition-88888888-8888-4888-8888-888888888888"

_ALERTS = f"""<alertContent><AlertDefinitions>
<AlertDefinition id="{A1}" name="Cond Alert" adapterKind="VMWARE" resourceKind="HostSystem">
 <State severity="automatic"><SymptomSets operator="or">
  <SymptomSet applyOn="self" operator="and" ref="{C1}"/>
  <SymptomSet applyOn="self" operator="and"><Symptom ref="{C2}"/></SymptomSet>
 </SymptomSets></State></AlertDefinition>
</AlertDefinitions><SymptomDefinitions>
<SymptomDefinition id="{C1}" name="Condition_1" symptomDefType="condition_self" adapterKind="VMWARE" resourceKind="HostSystem"/>
<SymptomDefinition id="{C2}" name="Condition_2" symptomDefType="condition_self" adapterKind="VMWARE" resourceKind="HostSystem"/>
</SymptomDefinitions></alertContent>"""

_ALERT2 = f"""<alertContent><AlertDefinitions>
<AlertDefinition id="{A2}" name="Plain Alert" adapterKind="VMWARE" resourceKind="HostSystem">
 <State severity="automatic"><SymptomSets operator="or">
  <SymptomSet applyOn="self" operator="and" ref="{S1}"/></SymptomSets></State></AlertDefinition>
</AlertDefinitions><SymptomDefinitions>
<SymptomDefinition id="{S1}" name="Plain Symptom" adapterKind="VMWARE" resourceKind="HostSystem"/>
</SymptomDefinitions></alertContent>"""


def _view(vid, title):
    return (f'<Content><Views><ViewDef id="{vid}"><Title>{title}</Title></ViewDef></Views>'
            f'</Content>')


@pytest.fixture()
def pak(tmp_path):
    p = tmp_path / "p.pak"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("content/reports/v1/content.xml", _view(V1, "View One"))
        z.writestr("content/reports/v2/content.xml", _view(V2, "View Two"))
        z.writestr("content/reports/r1/content.xml",
                   f'<Content>{_view(V2, "View Two")[9:-10]}<Reports><ReportDef id="{R1}">'
                   f"<Title>Report One</Title></ReportDef></Reports></Content>")
        z.writestr("content/alertdefs/Cond Alert.xml", _ALERTS)
        z.writestr("content/alertdefs/Plain Alert.xml", _ALERT2)
    return p


class _Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


class FakeSuite:
    """GET by path; ``state`` is what the instance holds."""

    def __init__(self, reports, symptoms, alerts):
        self.reports, self.symptoms, self.alerts = reports, symptoms, alerts
        self.calls = []

    def _request(self, method, path, params=None):
        self.calls.append(path)
        if path == "/api/reportdefinitions":
            items = [{"id": r} for r in self.reports]
            return _Resp(200, {"reportDefinitions": items,
                               "pageInfo": {"totalCount": len(items)}})
        if path.startswith("/api/symptomdefinitions/"):
            sid = path.rsplit("/", 1)[1]
            return _Resp(200, {"id": sid}) if sid in self.symptoms else _Resp(404, {})
        if path.startswith("/api/alertdefinitions/"):
            aid = path.rsplit("/", 1)[1]
            return _Resp(200, self.alerts[aid]) if aid in self.alerts else _Resp(404, {})
        raise AssertionError(path)


class FakeUI:
    def __init__(self, views):
        self.views = views

    def list_views(self):
        # The grouped shape the 9.x build answers with: type -> subject -> list.
        return {"LIST": {"Host System": [{"viewDefinitionKey": v, "name": v} for v in self.views]}}


def _alert_json(*sets):
    """REST alert definition, one state, a composite of SYMPTOM_SETs."""
    return {"states": [{"base-symptom-set": {
        "type": "SYMPTOM_SET_COMPOSITE", "operator": "OR",
        "symptom-sets": [{"type": "SYMPTOM_SET", "symptomDefinitionIds": ids,
                          "alertConditions": [{"id": c} for c in conds]}
                         for ids, conds in sets]}}]}


def _cond(sid):
    return "Condition-" + sid[len("SymptomDefinition-"):]


def _run(pak, suite, ui, *, sleep=None):
    inv = pak_content.read_pak_content_inventory(pak)
    out, err, slept = [], [], []
    rc = pic.check_installed_content(
        inv, read=lambda: pic.read_live_content(suite, ui, inv),
        out=out.append, err=err.append, sleep=sleep or slept.append,
    )
    return rc, out, err, slept


def test_all_present_with_conditions_as_alert_conditions(pak):
    # 9.1.1 / 8.18.7 shape: the conditions live in the alert, never on
    # /api/symptomdefinitions, and that is not a shortfall.
    suite = FakeSuite([R1], {S1}, {
        A1: _alert_json(([], [_cond(C1)]), ([], [_cond(C2)])),
        A2: _alert_json(([S1], [])),
    })
    rc, out, err, slept = _run(pak, suite, FakeUI([V1, V2]))
    assert rc == 0 and err == [] and slept == []
    assert out[-1].startswith("CONTENT OK: 2 view(s), 1 report template(s), 1 symptom")
    # The conditions were never looked up as symptoms.
    assert not any(C1[len("SymptomDefinition-"):] in c for c in suite.calls
                   if c.startswith("/api/symptomdefinitions/"))


def test_shortfall_lists_missing_ids_by_type_and_exits_3(pak):
    # 9.0.2 shape of 0.0.0.15: a view and the report never imported, the
    # standalone symptom is gone, and the condition alert's sets are empty.
    suite = FakeSuite([], set(), {
        A1: _alert_json(([], []), ([], [])),
        A2: _alert_json(([], [])),
    })
    rc, out, err, slept = _run(pak, suite, FakeUI([V2]))
    assert rc == pic.CONTENT_FAILED_RC == 3
    assert f"CONTENT MISSING: view {V1} 'View One'" in err
    assert f"CONTENT MISSING: report template {R1} 'Report One'" in err
    assert f"CONTENT MISSING: symptom definition {S1} 'Plain Symptom'" in err
    lost = [e for e in err if e.startswith("CONTENT INCOMPLETE")]
    assert len(lost) == 2
    assert any("'Cond Alert' lost 2 of 2" in e and "Condition_1" in e for e in lost)
    assert any("'Plain Alert' lost 1 of 1" in e for e in lost)
    assert err[-1].startswith("ERROR: CONTENT SHORTFALL: 5 problem(s)")
    # Re-read every 30 s for 120 s while something was missing.
    assert slept == [30, 30, 30, 30]
    assert out[0].startswith("CONTENT WAIT: 5 problem(s)")


def test_missing_alert_is_reported(pak):
    suite = FakeSuite([R1], {S1}, {A2: _alert_json(([S1], []))})
    rc, _out, err, _ = _run(pak, suite, FakeUI([V1, V2]))
    assert rc == 3
    assert f"CONTENT MISSING: alert definition {A1} 'Cond Alert'" in err


def test_late_content_passes_on_a_re_read(pak):
    suite = FakeSuite([], {S1}, {
        A1: _alert_json(([], [_cond(C1)]), ([], [_cond(C2)])),
        A2: _alert_json(([S1], [])),
    })
    slept = []

    def _sleep(s):
        slept.append(s)
        suite.reports = [R1]  # lands before the first re-read

    rc, out, err, _ = _run(pak, suite, FakeUI([V1, V2]), sleep=_sleep)
    assert rc == 0 and err == [] and slept == [30]
    assert out[-1].startswith("CONTENT OK")


def test_unreadable_is_a_warning_not_a_failure(pak):
    class Broken(FakeSuite):
        def _request(self, method, path, params=None):
            raise ConnectionError("refused")

    rc, _out, err, _ = _run(pak, Broken([], set(), {}), FakeUI([V1, V2]))
    assert rc == 0
    assert err and err[0].startswith("WARNING: CONTENT UNCHECKED")


def test_unexpected_status_is_unreadable(pak):
    class Odd(FakeSuite):
        def _request(self, method, path, params=None):
            if path.startswith("/api/symptomdefinitions/"):
                return _Resp(500, {})
            return super()._request(method, path, params)

    rc, _out, err, _ = _run(pak, Odd([R1], set(), {}), FakeUI([V1, V2]))
    assert rc == 0 and "HTTP 500" in err[0]


def test_report_pak_content_wires_factories(pak, monkeypatch):
    suite = FakeSuite([R1], {S1}, {
        A1: _alert_json(([], [_cond(C1)]), ([], [_cond(C2)])),
        A2: _alert_json(([S1], [])),
    })

    class UI(FakeUI):
        logged = []

        def login(self):
            self.logged.append("in")

        def logout(self):
            self.logged.append("out")

    ui = UI([V1, V2])
    rc = pic.report_pak_content(
        pak, host="h", user="u", password="p", verify_ssl=False,
        ui_factory=lambda *a: ui, suite_factory=lambda *a: suite, sleep=lambda s: None,
    )
    assert rc == 0 and ui.logged == ["in", "out"]


def _wire_install(monkeypatch, tmp_path):
    import vcfcf_managementpacks.installer as inst

    class _Session:
        def __init__(self, **kw):
            pass

        def login(self):
            pass

        def logout(self):
            pass

        def prepare_upload(self):
            pass

        def upload_pak(self, *a, **k):
            return {"pakId": "X-1", "solutionName": "X", "solutionVersion": "0.0.0.1"}

        def trigger_install(self, pak_id):
            pass

        def is_pak_installing(self, timeout=None):
            return {"isPakInstalling": False, "isPakUninstallActive": False}

    monkeypatch.setattr(inst, "_UISession", _Session)
    monkeypatch.setattr(inst, "_resolve_credentials",
                        lambda *a, **k: ("ops.example", "u", "p", True,
                                         inst.ProfileAuth("Local", "devel")))
    monkeypatch.setattr(inst, "_parse_manifest_txt",
                        lambda p: {"name": "X", "version": "0.0.0.1", "adapter_kinds": ""})
    monkeypatch.setattr(inst, "_verify_adapter_registered", lambda *a, **k: None)
    monkeypatch.setattr(inst, "_preflight_unsigned_policy", lambda *a, **k: None)
    monkeypatch.setattr(inst, "_preflight_stock_ids", lambda *a, **k: None)
    pak = tmp_path / "x.pak"
    pak.write_bytes(b"PK")
    return inst, pak


def test_installer_returns_the_content_checks_code(monkeypatch, tmp_path):
    """install_pak runs the content check after the dashboard check and
    returns its 3 although every other check passed; content_check=False
    (--skip-content-check) does not run it."""
    inst, pak = _wire_install(monkeypatch, tmp_path)
    calls = []
    import vcfcf_managementpacks.post_install as pi
    monkeypatch.setattr(pi, "report_pak_dashboards",
                        lambda *a, **k: calls.append("dashboards") or 0)
    monkeypatch.setattr(pic, "report_pak_content",
                        lambda *a, **k: calls.append("content") or 3)
    assert inst.install_pak(str(pak)) == 3
    assert calls == ["dashboards", "content"]
    calls.clear()
    assert inst.install_pak(str(pak), content_check=False) == 0
    assert calls == ["dashboards"]
    calls.clear()
    # Runs without the dashboard check too.
    assert inst.install_pak(str(pak), materialization_check=False) == 3
    assert calls == ["content"]


def test_cli_flag_maps_to_content_check(monkeypatch, tmp_path):
    from vcfcf_managementpacks import cli
    import vcfcf_managementpacks.installer as inst
    seen = {}
    monkeypatch.setattr(inst, "install_pak", lambda **k: seen.update(k) or 0)
    parser = cli.build_parser()
    args = parser.parse_args(["install", str(tmp_path / "x.pak"), "--skip-content-check"])
    assert args.func(args) == 0
    assert seen["content_check"] is False
    args = parser.parse_args(["install", str(tmp_path / "x.pak")])
    args.func(args)
    assert seen["content_check"] is True
