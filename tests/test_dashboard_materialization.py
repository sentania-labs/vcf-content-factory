"""Report dashboards an import left half-built (issue #167).

A content import reports FINISHED after phase 1 only. A dashboard whose
entryKeys name an adapter kind the target lacks never completes phase 2
(STALLED). A dashboard can also stay incomplete with every adapter
installed: the 8.18.7 corpus export has "[VCF Content Factory] VCF License
Consumption Overview" incomplete for 19 days, pending CASAdapter /
NSXTAdapter / VMWARE / VMWARE_INFRA_HEALTH and the resources "License
Usage", "NSX World", "Automation World". So a dashboard still building
after one re-check is INCOMPLETE and reported, never called fine.

Fixture shapes copy the devel 9.0.2 and scott 8.18.7 exports in the
migrator corpus. No live instance: exports and the adapter-kind read are
faked.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.dashboards import materialization as mat  # noqa: E402
from vcfcf_dashboards import cli as dash_cli  # noqa: E402
from vcfcf_dashboards import client as dash_client  # noqa: E402
from vcfcf_dashboards import handler as dash_handler  # noqa: E402

ID_DONE = "66ec0811-0000-4000-8000-000000000001"
ID_MSSQL = "2679c78f-e88e-43ba-b1ae-864dbbe9c50c"
ID_LICENSE = "1b53e065-4319-4b09-8dd2-6da8b732f0e8"
ID_GONE = "deadbeef-0000-4000-8000-000000000004"


def _rk(rk, ak, n):
    return {"resourceKindKey": rk, "internalId": f"resourceKind:id:{n}_::_",
            "adapterKindKey": ak}


def _res(rk, ak, n, name):
    return {"resourceKindKey": rk, "internalId": f"resource:id:{n}_::_",
            "adapterKindKey": ak, "identifiers": [], "name": name}


ENTRY_KEYS_MSSQL = {
    "resourceKind": [
        _rk("HostSystem", "VMWARE", 1),
        _rk("SqlServer", "SqlServerAdapter", 2),
        _rk("SqlQuery", "SqlServerAdapter", 3),
        _rk("oracle_database_oracle_database_instance", "OracleDBAdapter", 5),
    ],
    "resource": [_res("vSphere World", "VMWARE", 0, "vSphere World")],
    "uuid": "752b2b1a-4cb7-446f-8c08-a926fc4fae77",
}
# The 8.18.7 counterexample: every adapter kind installed, stuck anyway.
ENTRY_KEYS_LICENSE = {
    "resourceKind": [
        _rk("VirtualMachine", "VMWARE", 0),
        _rk("LICENSE_USAGE_WORLD", "VMWARE_INFRA_HEALTH", 1),
    ],
    "resource": [
        _res("LICENSE_USAGE_WORLD", "VMWARE_INFRA_HEALTH", 0, "License Usage"),
        _res("NSXT World", "NSXTAdapter", 1, "NSX World"),
        _res("CAS World", "CASAdapter", 2, "Automation World"),
    ],
    "uuid": "u",
}

DONE = {"id": ID_DONE, "name": "Done", "importComplete": True, "entryKeys": None}
MSSQL = {"id": ID_MSSQL, "name": "MSSQL", "importComplete": False,
         "importAttempts": 0, "entryKeys": ENTRY_KEYS_MSSQL}
LICENSE = {"id": ID_LICENSE, "name": "License", "importComplete": False,
           "entryKeys": ENTRY_KEYS_LICENSE}
LICENSE_DONE = {"id": ID_LICENSE, "name": "License", "importComplete": True,
                "entryKeys": None}
INSTALLED = {"VMWARE", "VMWARE_INFRA_HEALTH", "NSXTAdapter", "CASAdapter",
             "VirtualAndPhysicalSANAdapter"}


class _D:
    def __init__(self, did, name):
        self.id, self.name = did, name


WANTED = [_D(ID_DONE, "Done"), _D(ID_MSSQL, "MSSQL"), _D(ID_LICENSE, "License")]


# --- core classifier ---------------------------------------------------------

def test_pending_adapter_kinds_reads_both_lists():
    assert mat.pending_adapter_kinds(MSSQL) == ["OracleDBAdapter", "SqlServerAdapter", "VMWARE"]
    assert mat.pending_adapter_kinds(LICENSE) == [
        "CASAdapter", "NSXTAdapter", "VMWARE", "VMWARE_INFRA_HEALTH"]
    assert mat.pending_adapter_kinds(DONE) == []


def test_pending_resource_names():
    assert mat.pending_resource_names(LICENSE) == [
        "License Usage", "NSX World", "Automation World"]
    assert mat.pending_resource_names(DONE) == []


def test_classify_first_read_states():
    got = {s.id: s for s in mat.classify_dashboards(
        [DONE, MSSQL, LICENSE],
        {d.id: d.name for d in WANTED + [_D(ID_GONE, "Gone")]}, INSTALLED)}
    assert got[ID_DONE].state == mat.COMPLETE
    assert got[ID_MSSQL].state == mat.STALLED
    assert got[ID_MSSQL].missing_adapter_kinds == ["OracleDBAdapter", "SqlServerAdapter"]
    assert got[ID_LICENSE].state == mat.SETTLING  # intermediate only
    assert got[ID_GONE].state == mat.ABSENT


def test_finalize_never_leaves_settling():
    statuses = mat.classify_dashboards([LICENSE], {ID_LICENSE: "License"}, INSTALLED)
    final = mat.finalize_statuses(statuses, 180)
    assert [s.state for s in final] == [mat.INCOMPLETE]
    assert final[0].checked_after_s == 180


def test_incomplete_message_names_kinds_and_resources_and_is_not_reassuring():
    st = mat.finalize_statuses(
        mat.classify_dashboards([LICENSE], {ID_LICENSE: "License"}, INSTALLED), 180)[0]
    msg = mat.describe_status(st)
    assert "180 s after the import" in msg
    assert "CASAdapter, NSXTAdapter, VMWARE, VMWARE_INFRA_HEALTH" in msg
    assert "'License Usage', 'NSX World', 'Automation World'" in msg
    assert "does not always" in msg
    assert "normal" not in msg


def test_unknown_installed_kinds_never_guess_stalled_or_claim_installed():
    st = mat.finalize_statuses(
        mat.classify_dashboards([MSSQL], {ID_MSSQL: "MSSQL"}, None), 0)[0]
    assert st.state == mat.INCOMPLETE
    msg = mat.describe_status(st)
    assert "could not be read" in msg
    assert "Every adapter kind is installed" not in msg


def test_import_complete_false_without_entry_keys_is_incomplete():
    got = mat.classify_dashboards([{"id": ID_DONE, "importComplete": False, "entryKeys": None}],
                                  {ID_DONE: "x"}, INSTALLED)
    assert got[0].state == mat.SETTLING


def test_ids_compare_case_insensitively():
    got = mat.classify_dashboards([DONE], {ID_DONE.upper(): "Done"}, INSTALLED)
    assert got[0].state == mat.COMPLETE


def test_stalled_message_names_the_missing_adapter():
    st = mat.classify_dashboards([MSSQL], {ID_MSSQL: "MSSQL"}, INSTALLED)[0]
    msg = mat.describe_status(st)
    assert "waiting on OracleDBAdapter, SqlServerAdapter" in msg
    assert "not installed" in msg


# --- wrapper check: export, adapterkinds, one bounded re-check -----------------

def _export_zip(dashboards):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("dashboard/dashboard.json",
                   json.dumps({"dashboards": dashboards, "entries": {}, "uuid": "u"}))
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("6844548499441080431L.v1", "owner")
        z.writestr("dashboards/owner-uuid", inner.getvalue())
    return outer.getvalue()


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, json.dumps(body)

    def json(self):
        return self._body


def _fake_client(monkeypatch, *exports, kinds_status=200):
    """Each export call returns the next scripted dashboard list (last repeats)."""
    calls = []
    seq = list(exports)

    def _export(c, types, **k):
        calls.append(("export", tuple(types)))
        n = sum(1 for x in calls if x[0] == "export")
        return _export_zip(seq[min(n - 1, len(seq) - 1)])

    monkeypatch.setattr(dash_client, "export_content_zip", _export)

    class _C:
        def _request(self, method, path, **k):
            calls.append((method, path))
            assert (method, path) == ("GET", "/api/adapterkinds")
            return _Resp(kinds_status, {"adapter-kind": [{"key": k} for k in sorted(INSTALLED)]})

    return _C(), calls


def _check(client, dashboards, wait=180, waits=None):
    slept = []
    statuses = dash_client.check_dashboard_materialization(
        client, dashboards, recheck_wait_s=wait,
        on_wait=(lambda n, s: waits.append((n, s))) if waits is not None else None,
        _sleep=slept.append,
    )
    return {s.id: s for s in statuses}, slept


def test_settling_is_rechecked_once_and_reported_incomplete(monkeypatch):
    c, calls = _fake_client(monkeypatch, [DONE, MSSQL, LICENSE])
    waits: list = []
    got, slept = _check(c, WANTED, waits=waits)
    assert got[ID_DONE].state == mat.COMPLETE
    assert got[ID_MSSQL].state == mat.STALLED
    assert got[ID_LICENSE].state == mat.INCOMPLETE
    assert got[ID_LICENSE].checked_after_s == 180
    assert slept == [180] and waits == [(1, 180)]
    assert [x for x in calls if x[0] == "export"] == [("export", ("DASHBOARDS",))] * 2
    assert calls.count(("GET", "/api/adapterkinds")) == 1


def test_recheck_that_completes_is_ok(monkeypatch):
    c, _calls = _fake_client(monkeypatch, [DONE, LICENSE], [DONE, LICENSE_DONE])
    got, slept = _check(c, [WANTED[0], WANTED[2]])
    assert got[ID_LICENSE].state == mat.COMPLETE
    assert slept == [180]


def test_no_recheck_when_nothing_is_settling(monkeypatch):
    c, calls = _fake_client(monkeypatch, [DONE, MSSQL])
    got, slept = _check(c, WANTED[:2])
    assert slept == []
    assert [x for x in calls if x[0] == "export"] == [("export", ("DASHBOARDS",))]
    assert got[ID_MSSQL].state == mat.STALLED


def test_no_adapter_read_when_all_complete(monkeypatch):
    c, calls = _fake_client(monkeypatch, [DONE])
    got, _slept = _check(c, WANTED[:1])
    assert got[ID_DONE].state == mat.COMPLETE
    assert calls == [("export", ("DASHBOARDS",))]


def test_wait_zero_reports_incomplete_at_once(monkeypatch):
    c, _calls = _fake_client(monkeypatch, [LICENSE])
    got, slept = _check(c, [WANTED[2]], wait=0)
    assert slept == []
    assert got[ID_LICENSE].state == mat.INCOMPLETE
    assert got[ID_LICENSE].checked_after_s == 0


def test_failed_recheck_export_falls_back_to_first_read(monkeypatch):
    c, _calls = _fake_client(monkeypatch, [LICENSE])
    real = dash_client.export_content_zip
    n = {"i": 0}

    def _flaky(cl, types, **k):
        n["i"] += 1
        if n["i"] == 2:
            raise dash_client.VCFOpsError("export busy")
        return real(cl, types, **k)

    monkeypatch.setattr(dash_client, "export_content_zip", _flaky)
    got, _slept = _check(c, [WANTED[2]])
    assert got[ID_LICENSE].state == mat.INCOMPLETE


def test_adapter_read_failure_never_guesses_stalled(monkeypatch):
    c, _calls = _fake_client(monkeypatch, [MSSQL], kinds_status=500)
    got, _slept = _check(c, [WANTED[1]], wait=0)
    assert got[ID_MSSQL].state == mat.INCOMPLETE
    assert got[ID_MSSQL].adapter_kinds_known is False


@pytest.mark.parametrize("requested,env,expect", [
    (None, None, dash_client.MATERIALIZATION_RECHECK_DEFAULT_S),
    (30, None, 30),
    (None, "45", 45),
    (10, "45", 10),
    (5000, None, dash_client.MATERIALIZATION_RECHECK_MAX_S),
    (-3, None, 0),
    (None, "junk", dash_client.MATERIALIZATION_RECHECK_DEFAULT_S),
])
def test_recheck_wait_resolution(monkeypatch, requested, env, expect):
    if env is None:
        monkeypatch.delenv(dash_client.MATERIALIZATION_RECHECK_ENV, raising=False)
    else:
        monkeypatch.setenv(dash_client.MATERIALIZATION_RECHECK_ENV, env)
    assert dash_client.materialization_recheck_wait(requested) == expect


# --- CLI output: greppable MATERIALIZATION <STATE>: lines -----------------------

def _final(states):
    out = []
    for d, s in zip(WANTED, states):
        st = mat.MaterializationStatus(id=d.id, name=d.name, state=s, checked_after_s=180)
        if s == mat.STALLED:
            st.missing_adapter_kinds = ["SqlServerAdapter"]
        if s == mat.INCOMPLETE:
            st.pending_adapter_kinds = ["NSXTAdapter"]
            st.pending_resources = ["NSX World"]
        out.append(st)
    return out


def test_cli_lines_per_outcome(monkeypatch, capsys):
    def _fake(c, d, recheck_wait_s=None, on_wait=None):
        on_wait(1, 180)
        return _final([mat.COMPLETE, mat.STALLED, mat.INCOMPLETE])

    monkeypatch.setattr(dash_cli, "check_dashboard_materialization", _fake)
    rc = dash_cli._report_materialization(object(), WANTED)
    out = capsys.readouterr()
    assert rc == 1
    assert "MATERIALIZATION WAIT: 1 dashboard(s) still building; re-checking once in 180 s" in out.out
    assert "MATERIALIZATION OK: 1 of 3 dashboard(s) finished building" in out.out
    assert "WARNING: MATERIALIZATION STALLED: dashboard 'MSSQL'" in out.err
    assert "SqlServerAdapter" in out.err
    assert "WARNING: MATERIALIZATION INCOMPLETE: dashboard 'License'" in out.err
    assert "'NSX World'" in out.err


def test_cli_incomplete_alone_warns_without_failing(monkeypatch, capsys):
    monkeypatch.setattr(dash_cli, "check_dashboard_materialization",
                        lambda c, d, **k: _final([mat.COMPLETE, mat.COMPLETE, mat.INCOMPLETE]))
    assert dash_cli._report_materialization(object(), WANTED) == 0
    assert "MATERIALIZATION INCOMPLETE" in capsys.readouterr().err


def test_cli_all_complete_prints_only_ok(monkeypatch, capsys):
    monkeypatch.setattr(dash_cli, "check_dashboard_materialization",
                        lambda c, d, **k: _final([mat.COMPLETE] * 3))
    assert dash_cli._report_materialization(object(), WANTED) == 0
    out = capsys.readouterr()
    assert out.out == "MATERIALIZATION OK: 3 of 3 dashboard(s) finished building\n"
    assert out.err == ""


def test_cli_check_failure_is_unchecked_warning_not_failure(monkeypatch, capsys):
    def _boom(c, d, **k):
        raise ConnectionError("network down")

    monkeypatch.setattr(dash_cli, "check_dashboard_materialization", _boom)
    assert dash_cli._report_materialization(object(), WANTED) == 0
    assert "WARNING: MATERIALIZATION UNCHECKED:" in capsys.readouterr().err


def test_cli_sync_flags_are_wired():
    ns = dash_cli.build_parser().parse_args(
        ["sync", "--skip-materialization-check", "--materialization-wait", "30"])
    assert ns.skip_materialization_check is True
    assert ns.materialization_wait == 30
    ns = dash_cli.build_parser().parse_args(["sync"])
    assert ns.skip_materialization_check is False
    assert ns.materialization_wait is None


# --- bundle-sync handler -------------------------------------------------------

def test_handler_maps_states_to_items(monkeypatch):
    monkeypatch.setattr(dash_handler, "check_dashboard_materialization",
                        lambda s, d, **k: _final([mat.COMPLETE, mat.STALLED, mat.INCOMPLETE]))
    by_id = dash_handler._materialization_by_id(object(), WANTED)
    items = [dash_handler._materialization_item(d, by_id.get(d.id)) for d in WANTED]
    assert [i.status for i in items] == ["ok", "failed", "warn"]
    assert items[1].message.startswith("MATERIALIZATION STALLED:")
    assert items[2].message.startswith("MATERIALIZATION INCOMPLETE:")
    assert "'NSX World'" in items[2].message


def test_handler_absent_is_warn():
    st = mat.MaterializationStatus(id=ID_GONE, name="Gone", state=mat.ABSENT)
    item = dash_handler._materialization_item(_D(ID_GONE, "Gone"), st)
    assert item.status == "warn" and item.message.startswith("MATERIALIZATION ABSENT:")


def test_handler_check_failure_is_recorded(monkeypatch):
    def _boom(s, d, **k):
        raise ConnectionError("down")

    monkeypatch.setattr(dash_handler, "check_dashboard_materialization", _boom)
    assert "__error__" in dash_handler._materialization_by_id(object(), WANTED)
