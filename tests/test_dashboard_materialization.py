"""Report dashboards left incomplete by a missing adapter (issue #167).

A content import reports FINISHED after phase 1 only. A dashboard whose
entryKeys name an adapter kind the target lacks never completes phase 2.
The fixtures copy the shape of the devel 9.0.2 export recorded in
knowledge/context/api-surface/dashboard_import_two_phase_materialization.md
(MSSQL dashboard 2679c78f, pending SqlServerAdapter / OracleDBAdapter).
No live instance: the export and the adapter-kind read are faked.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

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
ID_SETTLING = "f5a14e9c-0000-4000-8000-000000000003"
ID_GONE = "deadbeef-0000-4000-8000-000000000004"


def _rk(rk, ak, n):
    return {"resourceKindKey": rk, "internalId": f"resourceKind:id:{n}_::_",
            "adapterKindKey": ak}


ENTRY_KEYS_MSSQL = {
    "resourceKind": [
        _rk("HostSystem", "VMWARE", 1),
        _rk("SqlServer", "SqlServerAdapter", 2),
        _rk("SqlQuery", "SqlServerAdapter", 3),
        _rk("oracle_database_oracle_database_instance", "OracleDBAdapter", 5),
    ],
    "resource": [{"resourceKindKey": "vSphere World", "internalId": "resource:id:0_::_",
                  "adapterKindKey": "VMWARE", "identifiers": [], "name": "vSphere World"}],
    "uuid": "752b2b1a-4cb7-446f-8c08-a926fc4fae77",
}
ENTRY_KEYS_SETTLING = {"resourceKind": [_rk("ClusterComputeResource", "VMWARE", 0)],
                       "resource": [], "uuid": "u"}

EXPORTED = [
    {"id": ID_DONE, "name": "Done", "importComplete": True, "entryKeys": None},
    {"id": ID_MSSQL, "name": "MSSQL", "importComplete": False, "importAttempts": 0,
     "entryKeys": ENTRY_KEYS_MSSQL},
    {"id": ID_SETTLING, "name": "Settling", "importComplete": False,
     "entryKeys": ENTRY_KEYS_SETTLING},
]
INSTALLED = {"VMWARE", "vcfcf_compliance", "VirtualAndPhysicalSANAdapter"}


class _D:
    def __init__(self, did, name):
        self.id, self.name = did, name


WANTED = [_D(ID_DONE, "Done"), _D(ID_MSSQL, "MSSQL"), _D(ID_SETTLING, "Settling")]


# --- core classifier ---------------------------------------------------------

def test_pending_adapter_kinds_reads_both_lists():
    assert mat.pending_adapter_kinds(EXPORTED[1]) == ["OracleDBAdapter", "SqlServerAdapter", "VMWARE"]
    assert mat.pending_adapter_kinds(EXPORTED[0]) == []


def test_classify_states():
    got = {s.id: s for s in mat.classify_dashboards(
        EXPORTED, {d.id: d.name for d in WANTED + [_D(ID_GONE, "Gone")]}, INSTALLED)}
    assert got[ID_DONE].state == mat.COMPLETE
    assert got[ID_MSSQL].state == mat.STALLED
    assert got[ID_MSSQL].missing_adapter_kinds == ["OracleDBAdapter", "SqlServerAdapter"]
    assert got[ID_SETTLING].state == mat.SETTLING
    assert got[ID_GONE].state == mat.ABSENT


def test_unknown_installed_kinds_never_guess_stalled():
    got = mat.classify_dashboards(EXPORTED, {ID_MSSQL: "MSSQL"}, None)
    assert got[0].state == mat.SETTLING


def test_import_complete_false_without_entry_keys_is_incomplete():
    got = mat.classify_dashboards([{"id": ID_DONE, "importComplete": False, "entryKeys": None}],
                                  {ID_DONE: "x"}, INSTALLED)
    assert got[0].state == mat.SETTLING


def test_ids_compare_case_insensitively():
    got = mat.classify_dashboards(EXPORTED, {ID_DONE.upper(): "Done"}, INSTALLED)
    assert got[0].state == mat.COMPLETE


def test_stalled_message_names_the_missing_adapter():
    st = mat.classify_dashboards(EXPORTED, {ID_MSSQL: "MSSQL"}, INSTALLED)[0]
    msg = mat.describe_status(st)
    assert "waiting on OracleDBAdapter, SqlServerAdapter" in msg
    assert "not installed" in msg


# --- wrapper check: export + adapterkinds -------------------------------------

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


def _fake_check_client(monkeypatch, exported, kinds_status=200):
    calls = []
    monkeypatch.setattr(dash_client, "export_content_zip",
                        lambda c, types, **k: calls.append(("export", tuple(types)))
                        or _export_zip(exported))

    class _C:
        def _request(self, method, path, **k):
            calls.append((method, path))
            assert (method, path) == ("GET", "/api/adapterkinds")
            return _Resp(kinds_status, {"adapter-kind": [{"key": k} for k in sorted(INSTALLED)]})

    return _C(), calls


def test_check_reads_export_and_adapter_kinds(monkeypatch):
    c, calls = _fake_check_client(monkeypatch, EXPORTED)
    got = {s.id: s.state for s in dash_client.check_dashboard_materialization(c, WANTED)}
    assert got == {ID_DONE: mat.COMPLETE, ID_MSSQL: mat.STALLED, ID_SETTLING: mat.SETTLING}
    assert calls == [("export", ("DASHBOARDS",)), ("GET", "/api/adapterkinds")]


def test_check_skips_adapter_read_when_all_complete(monkeypatch):
    c, calls = _fake_check_client(monkeypatch, EXPORTED[:1])
    got = dash_client.check_dashboard_materialization(c, WANTED[:1])
    assert [s.state for s in got] == [mat.COMPLETE]
    assert calls == [("export", ("DASHBOARDS",))]


def test_adapter_read_failure_degrades_to_settling(monkeypatch):
    c, _calls = _fake_check_client(monkeypatch, EXPORTED, kinds_status=500)
    got = {s.id: s.state for s in dash_client.check_dashboard_materialization(c, WANTED)}
    assert got[ID_MSSQL] == mat.SETTLING


# --- CLI and bundle-sync handler reporting -------------------------------------

def _statuses(states):
    return [mat.MaterializationStatus(id=d.id, name=d.name, state=s,
                                      missing_adapter_kinds=["SqlServerAdapter"] if s == mat.STALLED else [])
            for d, s in zip(WANTED, states)]


def test_cli_stalled_fails_and_names_adapter(monkeypatch, capsys):
    monkeypatch.setattr(dash_cli, "check_dashboard_materialization",
                        lambda c, d: _statuses([mat.COMPLETE, mat.STALLED, mat.SETTLING]))
    rc = dash_cli._report_materialization(object(), WANTED)
    out = capsys.readouterr()
    assert rc == 1
    assert "WARNING: dashboard 'MSSQL'" in out.err and "SqlServerAdapter" in out.err
    assert "NOTE: dashboard 'Settling'" in out.out
    assert "Done" not in out.out + out.err


def test_cli_complete_is_silent(monkeypatch, capsys):
    monkeypatch.setattr(dash_cli, "check_dashboard_materialization",
                        lambda c, d: _statuses([mat.COMPLETE] * 3))
    assert dash_cli._report_materialization(object(), WANTED) == 0
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


def test_cli_check_failure_is_warning_not_failure(monkeypatch, capsys):
    def _boom(c, d):
        raise ConnectionError("network down")

    monkeypatch.setattr(dash_cli, "check_dashboard_materialization", _boom)
    assert dash_cli._report_materialization(object(), WANTED) == 0
    assert "could not check" in capsys.readouterr().err


def test_cli_sync_skip_flag_is_wired():
    ns = dash_cli.build_parser().parse_args(["sync", "--skip-materialization-check"])
    assert ns.skip_materialization_check is True
    assert dash_cli.build_parser().parse_args(["sync"]).skip_materialization_check is False


def test_handler_maps_states_to_items(monkeypatch):
    monkeypatch.setattr(dash_handler, "check_dashboard_materialization",
                        lambda s, d: _statuses([mat.COMPLETE, mat.STALLED, mat.ABSENT]))
    by_id = dash_handler._materialization_by_id(object(), WANTED)
    items = [dash_handler._materialization_item(d, by_id.get(d.id)) for d in WANTED]
    assert [i.status for i in items] == ["ok", "failed", "warn"]
    assert "SqlServerAdapter" in items[1].message


def test_handler_check_failure_is_recorded(monkeypatch):
    def _boom(s, d):
        raise ConnectionError("down")

    monkeypatch.setattr(dash_handler, "check_dashboard_materialization", _boom)
    assert "__error__" in dash_handler._materialization_by_id(object(), WANTED)
