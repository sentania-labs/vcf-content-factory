"""Post-install dashboard materialization check in the shipped installers (#244).

Issue #167 added the check to ``vcfcf_dashboards sync`` and bundle sync.
This file covers the two installers that did not run it:

- the distribution zip's ``install.py`` (standalone: it re-states the core
  classifier, so a parity test pins that the two agree on every state and
  every sentence);
- the pak installer (``vcfcf_managementpacks install``), which reads
  ``getDashboardList`` by the pak's own dashboard ids because a CUSTOM
  ``DASHBOARDS`` export does not carry pak-installed dashboards.

The regression case is the 8.18.7 corpus dashboard "[VCF Content Factory]
VCF License Consumption Overview", incomplete for 19 days with every adapter
kind installed: it must be reported INCOMPLETE, never fine. No live instance:
every read is faked.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.dashboards import materialization as mat  # noqa: E402
from vcfcf_core.extractor import dashboards_from_export_zip  # noqa: E402
from vcfcf_managementpacks import post_install  # noqa: E402

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
        _rk("oracle_database_oracle_database_instance", "OracleDBAdapter", 5),
    ],
    "resource": [_res("vSphere World", "VMWARE", 0, "vSphere World")],
    "uuid": "752b2b1a-4cb7-446f-8c08-a926fc4fae77",
}
#: The 8.18.7 regression case: every adapter kind installed, stuck anyway.
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
         "entryKeys": ENTRY_KEYS_MSSQL}
LICENSE = {"id": ID_LICENSE, "name": "License", "importComplete": False,
           "entryKeys": ENTRY_KEYS_LICENSE}
LICENSE_DONE = {"id": ID_LICENSE, "name": "License", "importComplete": True,
                "entryKeys": None}
INSTALLED = {"VMWARE", "VMWARE_INFRA_HEALTH", "NSXTAdapter", "CASAdapter"}
WANTED = {ID_DONE: "Done", ID_MSSQL: "MSSQL", ID_LICENSE: "License",
          ID_GONE: "Gone"}


def _export_zip(*dashboards) -> bytes:
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("dashboard/dashboard.json", json.dumps(
            {"entries": {}, "dashboards": list(dashboards), "uuid": "x"}))
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("dashboards/29c1613f-3bbe-4aa0-8236-2c74db22c661", inner.getvalue())
        z.writestr("dashboardsharings/29c1613f-3bbe-4aa0-8236-2c74db22c661", "[]")
        z.writestr("configuration.json", "{}")
    return outer.getvalue()


@pytest.fixture(scope="module")
def install_mod():
    path = SRC / "vcfcf_packaging" / "templates" / "install.py"
    spec = importlib.util.spec_from_file_location("_install_template_mat", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_install_template_mat"] = mod
    spec.loader.exec_module(mod)
    return mod


# --- install.py: parity with the core classifier -----------------------------

PARITY_CASES = [
    ([DONE, MSSQL, LICENSE], INSTALLED, 0),
    ([DONE, MSSQL, LICENSE], INSTALLED, 180),
    ([DONE, MSSQL, LICENSE], None, 180),  # adapter kinds unreadable
    ([LICENSE_DONE], INSTALLED, 0),
    ([], INSTALLED, 0),  # everything ABSENT
    ([{"id": ID_DONE.upper(), "importComplete": False, "entryKeys": {}}], set(), 30),
    ([{"id": ID_LICENSE, "importComplete": False, "entryKeys": None}], INSTALLED, 5),
    # One missing adapter kind: the singular "is" sentence.
    ([{"id": ID_LICENSE, "importComplete": False,
       "entryKeys": {"resourceKind": [_rk("rubrik_vm", "mpb_rubrik", 0)]}}], INSTALLED, 0),
]


@pytest.mark.parametrize("exported,kinds,after", PARITY_CASES)
def test_install_template_classifier_matches_core(install_mod, exported, kinds, after):
    core = mat.finalize_statuses(mat.classify_dashboards(exported, WANTED, kinds), after)
    mine = install_mod._mat_finalize(install_mod._mat_classify(exported, WANTED, kinds), after)
    assert len(core) == len(mine)
    for c, m in zip(core, mine):
        assert (c.id, c.name, c.state) == (m["id"], m["name"], m["state"])
        assert c.pending_adapter_kinds == m["pending"]
        assert c.missing_adapter_kinds == m["missing"]
        assert c.pending_resources == m["resources"]
        assert c.checked_after_s == m["after"]
        assert mat.describe_status(c) == install_mod._mat_describe(m)


def test_install_template_export_reader_matches_core(install_mod):
    blob = _export_zip(DONE, MSSQL, LICENSE)
    core = [d["id"] for d in dashboards_from_export_zip(blob)]
    mine = [d["id"] for d in install_mod._mat_dashboards_from_export_zip(blob)]
    assert core == mine == [ID_DONE, ID_MSSQL, ID_LICENSE]
    with pytest.raises(ValueError):
        install_mod._mat_dashboards_from_export_zip(b"not a zip")


def test_install_template_wait_matches_factory(install_mod, monkeypatch):
    from vcfcf_dashboards.client import materialization_recheck_wait

    for env, req in (("", None), ("60", None), ("bogus", None), ("5000", None),
                     ("", 0), ("", -4), ("", 2000), ("60", 10)):
        monkeypatch.setenv("VCFCF_MATERIALIZATION_WAIT_S", env)
        assert install_mod._mat_wait(req) == materialization_recheck_wait(req)


# --- install.py: the run-level check -----------------------------------------

class _ExportClient:
    """Fake installer Client: a queue of export zips and the adapter kinds."""

    def __init__(self, exports, kinds=INSTALLED, kinds_error=False):
        self.exports = list(exports)
        self.kinds = kinds
        self.kinds_error = kinds_error
        self.export_calls = 0

    def export_dashboards_zip(self):
        self.export_calls += 1
        item = self.exports.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def list_adapter_kind_keys(self):
        if self.kinds_error:
            raise RuntimeError("403")
        return set(self.kinds)


def _args(**kw):
    return argparse.Namespace(**{"skip_materialization_check": False,
                                 "materialization_wait": 0, **kw})


def test_install_template_reports_ok(install_mod, capsys):
    client = _ExportClient([_export_zip(DONE)])
    warnings, notes = install_mod._report_materialization(
        client, [(ID_DONE, "Done")], _args())
    assert (warnings, notes) == ([], [])
    assert "MATERIALIZATION OK: 1 of 1 dashboard(s) finished building" in capsys.readouterr().out


def test_install_template_stalled_fails_the_install(install_mod, capsys):
    client = _ExportClient([_export_zip(MSSQL)])
    warnings, notes = install_mod._report_materialization(
        client, [(ID_MSSQL, "MSSQL")], _args())
    assert len(warnings) == 1 and notes == []
    assert warnings[0].startswith("MATERIALIZATION STALLED: ")
    assert "OracleDBAdapter, SqlServerAdapter" in warnings[0]
    assert "WARNING: MATERIALIZATION STALLED:" in capsys.readouterr().out


def test_install_template_regression_8187_incomplete_after_one_recheck(install_mod, capsys):
    """#244 regression case: incomplete with every adapter installed is
    re-checked once and then reported INCOMPLETE, never fine, never failed."""
    client = _ExportClient([_export_zip(LICENSE), _export_zip(LICENSE)])
    slept = []
    statuses = install_mod._check_materialization(
        client, [(ID_LICENSE, "License")], 180, _sleep=slept.append)
    assert slept == [180] and client.export_calls == 2
    assert [s["state"] for s in statuses] == ["incomplete"]
    out = capsys.readouterr().out
    assert "MATERIALIZATION WAIT: 1 dashboard(s) still building; re-checking once in 180 s" in out
    assert "180 s after the import" in install_mod._mat_describe(statuses[0])


def test_install_template_settles_on_recheck(install_mod):
    client = _ExportClient([_export_zip(LICENSE), _export_zip(LICENSE_DONE)])
    statuses = install_mod._check_materialization(
        client, [(ID_LICENSE, "License")], 30, _sleep=lambda s: None)
    assert [s["state"] for s in statuses] == ["complete"]


def test_install_template_failed_recheck_reports_first_read(install_mod):
    client = _ExportClient([_export_zip(LICENSE), RuntimeError("busy")])
    statuses = install_mod._check_materialization(
        client, [(ID_LICENSE, "License")], 30, _sleep=lambda s: None)
    assert [(s["state"], s["after"]) for s in statuses] == [("incomplete", 0)]


def test_install_template_unchecked_is_a_note_not_a_failure(install_mod, capsys):
    client = _ExportClient([RuntimeError("export failed (500)")])
    warnings, notes = install_mod._report_materialization(
        client, [(ID_DONE, "Done")], _args())
    assert warnings == [] and len(notes) == 1
    assert notes[0].startswith("MATERIALIZATION UNCHECKED: ")
    assert "WARNING: MATERIALIZATION UNCHECKED:" in capsys.readouterr().out


def test_install_template_absent_and_skip_flag(install_mod, capsys):
    client = _ExportClient([_export_zip(DONE)])
    warnings, notes = install_mod._report_materialization(
        client, [(ID_GONE, "Gone")], _args())
    assert warnings == [] and notes[0].startswith("MATERIALIZATION ABSENT: ")
    skip = _ExportClient([])
    assert install_mod._report_materialization(
        skip, [(ID_DONE, "Done")], _args(skip_materialization_check=True)) == ([], [])
    assert skip.export_calls == 0


def test_install_template_records_only_dashboards_the_import_changed(install_mod, tmp_path):
    def _ctx(result):
        bundle_dir = tmp_path / "b"
        (bundle_dir / "content").mkdir(parents=True, exist_ok=True)
        (bundle_dir / "content" / "dashboard.json").write_text(json.dumps({"dashboards": [
            {"id": "dash-1", "name": "VCF Content Factory/[VCF Content Factory] Cap",
             "namePath": "VCF Content Factory"}]}))

        class _C:
            def import_content_zip(self, blob, label):
                return result

        return {"client": _C(), "marker": "1L.v1",
                "owner_id": "00000000-0000-0000-0000-000000000001",
                "username": "admin", "args": types.SimpleNamespace(),
                "warnings": [], "advisories": [], "bundle_dir": bundle_dir,
                "manifest": {"content": {"dashboards": {"file": "content/dashboard.json"}}}}

    ok = _ctx({"state": "FINISHED", "operationSummaries": [
        {"contentType": "DASHBOARDS", "imported": 1, "skipped": 0}]})
    install_mod._install_dashboards(ok)
    assert ok["imported_dashboards"] == [("dash-1", "[VCF Content Factory] Cap")]
    skipped = _ctx({"state": "FINISHED", "operationSummaries": [
        {"contentType": "DASHBOARDS", "imported": 0, "skipped": 1}]})
    install_mod._install_dashboards(skipped)
    assert skipped.get("imported_dashboards", []) == []


def _drive_run(install_mod, monkeypatch, tmp_path, exports, args):
    class _StubClient(_ExportClient):
        def __init__(self, *a, **k):
            super().__init__(exports)
            self._user = "admin"

        def authenticate(self):
            return None

        def discover_marker_filename(self):
            return "1L.v1"

        def get_current_user(self):
            return {"id": "u1"}

    def _one_bundle(bundle, gctx, step, total):
        gctx["imported_dashboards"].append((ID_LICENSE, "License"))
        return 0, [], []

    monkeypatch.setattr(install_mod, "Client", _StubClient)
    monkeypatch.setattr(install_mod, "_install_one_bundle", _one_bundle)
    bundles = [{"dir": tmp_path, "manifest": {"content": {}}, "name": "b"}]
    return install_mod._run_install(args, "ops.example.test", "admin", "local", "pw",
                                    False, bundles)


def test_install_template_incomplete_run_does_not_end_on_all_successful(
        install_mod, monkeypatch, tmp_path, capsys):
    _drive_run(install_mod, monkeypatch, tmp_path,
               [_export_zip(LICENSE)], _args(skip_enable=True, force=False))
    out = capsys.readouterr().out
    assert "Done. All content installed successfully." not in out
    assert "see the attention list at the end of this output." in out
    assert "1 dashboard(s) need a later look" in out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines[-1].startswith("  ATTENTION  MATERIALIZATION INCOMPLETE: ")


def test_install_template_stalled_run_exits_2(install_mod, monkeypatch, tmp_path, capsys):
    stalled = dict(LICENSE, entryKeys={"resourceKind": [_rk("X", "mpb_rubrik", 0)]})
    with pytest.raises(SystemExit) as exc:
        _drive_run(install_mod, monkeypatch, tmp_path,
                   [_export_zip(stalled)], _args(skip_enable=True, force=False))
    assert exc.value.code == 2
    assert "WARN  MATERIALIZATION STALLED:" in capsys.readouterr().out


def test_install_template_flags_parse(install_mod, monkeypatch):
    seen = {}
    monkeypatch.setattr(sys, "argv", ["install.py", "--skip-materialization-check",
                                      "--materialization-wait", "42"])
    monkeypatch.setattr(install_mod, "_discover_bundles", lambda: [])

    def _die(msg):
        raise SystemExit(msg)

    monkeypatch.setattr(install_mod, "_die", _die)
    orig = install_mod.argparse.ArgumentParser.parse_args

    def _capture(self, *a, **k):
        ns = orig(self, *a, **k)
        seen["ns"] = ns
        return ns

    monkeypatch.setattr(install_mod.argparse.ArgumentParser, "parse_args", _capture)
    with pytest.raises(SystemExit):
        install_mod.main()
    assert seen["ns"].skip_materialization_check is True
    assert seen["ns"].materialization_wait == 42


# --- pak installer -------------------------------------------------------------

PAK_ENTRIES = {
    "resourceKind": [{"resourceKindKey": "ComplianceWorld", "internalId": "resourceKind:id:0_::_",
                      "adapterKindKey": "vcfcf_compliance"}],
    "adapterKind": [{"internalId": "adapterKind:id:0_::_", "adapterKindKey": "vcfcf_compliance"}],
}
ID_WORLD = "4e2c777e-9c6c-4c6a-bc16-ab55b6110f33"
ID_HOSTS = "e2e42416-0000-4000-8000-000000000002"


def _pak(tmp_path, extra=None, props=None) -> Path:
    p = tmp_path / "x.pak"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("manifest.txt", "{}")
        z.writestr("content/dashboards/World/dashboard.json", json.dumps({
            "entries": PAK_ENTRIES,
            "dashboards": [{"id": ID_WORLD, "namePath": "VCF Content Factory",
                            "name": "VCF Content Factory/[VCF Content Factory] World"}],
            "uuid": "u"}))
        z.writestr("content/dashboards/World/resources/resources.properties", "")
        z.writestr("content/dashboards/Hosts/dashboard.json", json.dumps({
            "entries": {"resourceKind": [_rk("HostSystem", "VMWARE", 0)]},
            "dashboards": [{"id": ID_HOSTS.upper(), "name": "[VCF Content Factory] Hosts"}],
            "uuid": "u"}))
        if props is not None:
            z.writestr("content/dashboards/dashboards.properties", props)
        for name, body in (extra or {}).items():
            z.writestr(name, body)
    return p


def test_read_pak_dashboards(tmp_path):
    warns = []
    p = _pak(tmp_path, extra={
        "content/dashboards/Bad/dashboard.json": "[1, 2]",
        "content/dashboards/Worse/dashboard.json": "{nope",
    })
    got = post_install.read_pak_dashboards(p, warn=warns.append)
    assert [(d.id, d.name, d.directory) for d in got] == [
        (ID_HOSTS, "[VCF Content Factory] Hosts", "Hosts"),
        (ID_WORLD, "[VCF Content Factory] World", "World"),
    ]
    assert got[1].entries == PAK_ENTRIES
    assert len(warns) == 2


class _FakeUI:
    """getDashboardList answers, one list per call (last one repeats)."""

    def __init__(self, *listings, fail_first=False):
        self.listings = list(listings)
        self.fail_first = fail_first
        self.calls = 0
        self.logged_in = False
        self.logged_out = False

    def login(self):
        self.logged_in = True

    def logout(self):
        self.logged_out = True

    def list_dashboards(self):
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise RuntimeError("503 Service Unavailable")
        return self.listings[min(self.calls - 1, len(self.listings) - 1)]


def _entry(did, loading, **kw):
    e = {"id": did, "name": "n", "owner": "admin"}
    if loading is not None:
        e["isLoading"] = loading
    e.update(kw)
    return e


def test_pak_check_states(tmp_path):
    dashes = post_install.read_pak_dashboards(_pak(tmp_path), warn=print)
    ui = _FakeUI([_entry(ID_WORLD, False), _entry(ID_HOSTS, True)])
    statuses, unknown = post_install.check_pak_dashboards(
        ui, dashes, wait_s=0, adapter_kinds=lambda: {"VMWARE", "vcfcf_compliance"})
    got = {s.id: s.state for s in statuses}
    assert got == {ID_WORLD: mat.COMPLETE, ID_HOSTS: mat.INCOMPLETE}
    assert unknown == []
    ui = _FakeUI([_entry(ID_HOSTS, True)])
    statuses, _ = post_install.check_pak_dashboards(
        ui, dashes, wait_s=0, adapter_kinds=lambda: {"vcfcf_compliance"})
    got = {s.id: s for s in statuses}
    assert got[ID_WORLD].state == mat.ABSENT
    assert got[ID_HOSTS].state == mat.STALLED
    assert got[ID_HOSTS].missing_adapter_kinds == ["VMWARE"]


def test_pak_check_rechecks_once(tmp_path):
    dashes = post_install.read_pak_dashboards(_pak(tmp_path), warn=print)
    ui = _FakeUI([_entry(ID_WORLD, True), _entry(ID_HOSTS, False)],
                 [_entry(ID_WORLD, False), _entry(ID_HOSTS, False)])
    waits, slept = [], []
    statuses, _ = post_install.check_pak_dashboards(
        ui, dashes, wait_s=60, adapter_kinds=lambda: {"vcfcf_compliance", "VMWARE"},
        on_wait=lambda n, s: waits.append((n, s)), sleep=slept.append)
    assert waits == [(1, 60)] and slept == [60] and ui.calls == 2
    assert {s.state for s in statuses} == {mat.COMPLETE}


def test_pak_check_missing_isloading_is_unchecked_not_complete(tmp_path):
    dashes = post_install.read_pak_dashboards(_pak(tmp_path), warn=print)
    ui = _FakeUI([_entry(ID_WORLD, None), _entry(ID_HOSTS, False)])
    statuses, unknown = post_install.check_pak_dashboards(
        ui, dashes, wait_s=0, adapter_kinds=lambda: set())
    assert unknown == [ID_WORLD]
    assert [s.id for s in statuses] == [ID_HOSTS]


def _run_report(tmp_path, ui, kinds=frozenset({"vcfcf_compliance", "VMWARE"}), **kw):
    class _Suite:
        pass

    import vcfcf_dashboards.client as dc

    orig = dc.list_adapter_kind_keys
    dc.list_adapter_kind_keys = lambda client: set(kinds)
    try:
        return post_install.report_pak_dashboards(
            _pak(tmp_path, **kw), host="h", user="u", password="s3cret-pw", verify_ssl=False,
            wait_s=0, ui_factory=lambda *a: ui, suite_factory=lambda *a: _Suite(),
            sleep=lambda s: None)
    finally:
        dc.list_adapter_kind_keys = orig


def test_pak_report_ok_and_stalled_exit_codes(tmp_path, capsys):
    ui = _FakeUI([_entry(ID_WORLD, False), _entry(ID_HOSTS, False)])
    assert _run_report(tmp_path, ui) == 0
    out, err = capsys.readouterr()
    assert "MATERIALIZATION OK: 2 of 2 dashboard(s) finished building" in out
    assert ui.logged_in and ui.logged_out
    assert "s3cret-pw" not in out + err

    ui = _FakeUI([_entry(ID_WORLD, False), _entry(ID_HOSTS, True)])
    assert _run_report(tmp_path, ui, kinds={"vcfcf_compliance"}) == post_install.POST_INSTALL_FAILED_RC
    err = capsys.readouterr().err
    assert "WARNING: MATERIALIZATION STALLED: dashboard '[VCF Content Factory] Hosts'" in err


def test_pak_report_unreadable_list_is_unchecked_rc0(tmp_path, capsys):
    ui = _FakeUI([], fail_first=True)
    assert _run_report(tmp_path, ui) == 0
    assert "WARNING: MATERIALIZATION UNCHECKED:" in capsys.readouterr().err
    assert ui.logged_out


def test_pak_report_pak_without_dashboards_is_silent(tmp_path, capsys):
    p = tmp_path / "empty.pak"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("manifest.txt", "{}")
    rc = post_install.report_pak_dashboards(
        p, host="h", user="u", password="p", verify_ssl=False,
        ui_factory=lambda *a: pytest.fail("no session for a pak without dashboards"))
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_install_cli_flags_and_exit_code(monkeypatch):
    from vcfcf_managementpacks import cli as mp_cli
    from vcfcf_managementpacks import installer

    seen = {}

    def _fake_install(**kw):
        seen.update(kw)
        return post_install.POST_INSTALL_FAILED_RC

    monkeypatch.setattr(installer, "install_pak", _fake_install)
    rc = mp_cli.main(["install", "x.pak", "--skip-materialization-check",
                      "--materialization-wait", "12"])
    assert rc == post_install.POST_INSTALL_FAILED_RC
    assert seen["materialization_check"] is False
    assert seen["materialization_wait"] == 12
    mp_cli.main(["install", "x.pak"])
    assert seen["materialization_check"] is True and seen["materialization_wait"] is None


def test_install_pak_runs_the_check_after_logout(monkeypatch, tmp_path):
    from vcfcf_managementpacks import installer

    events = []

    class _Session:
        def __init__(self, **kw):
            pass

        def login(self):
            events.append("login")

        def logout(self):
            events.append("logout")

        def get_unsigned_pak_policy(self):
            return True

        def prepare_upload(self):
            pass

        def upload_pak(self, *a, **k):
            return {"pakId": "X-1", "solutionName": "X", "solutionVersion": "0.0.0.1"}

        def trigger_install(self, pak_id):
            events.append("install")

        def is_pak_installing(self, timeout=None):
            return {"isPakInstalling": False}

    monkeypatch.setattr(installer, "_UISession", _Session)
    monkeypatch.setattr(installer, "_resolve_credentials", lambda *a, **k: ("h", "u", "p", True))
    monkeypatch.setattr(installer, "_parse_manifest_txt",
                        lambda p: {"name": "X", "version": "0.0.0.1"})
    monkeypatch.setattr(installer, "_verify_adapter_registered", lambda *a, **k: events.append("verify"))
    monkeypatch.setattr(installer, "_preflight_unsigned_policy", lambda *a, **k: None)

    def _report(p, **kw):
        events.append("materialization")
        assert kw["verify_ssl"] is True and kw["wait_s"] == 7
        return 3

    monkeypatch.setattr(post_install, "report_pak_dashboards", _report)
    pak = tmp_path / "x.pak"
    pak.write_bytes(b"PK")
    rc = installer.install_pak(str(pak), poll_interval=0, materialization_wait=7)
    assert rc == 3
    assert events == ["login", "install", "verify", "logout", "materialization"]

    events.clear()
    assert installer.install_pak(str(pak), poll_interval=0, materialization_check=False) == 0
    assert "materialization" not in events
    events.clear()
    assert installer.install_pak(str(pak), poll_interval=0, wait=False) == 0
    assert "materialization" not in events


# --- review NIT 6: the re-check flow matches check_dashboard_materialization ---

class _D:
    def __init__(self, did, name):
        self.id, self.name = did, name


@pytest.mark.parametrize("reads", [
    [LICENSE, LICENSE_DONE],          # settles on the re-check
    [LICENSE, LICENSE],               # still building: INCOMPLETE after the wait
    [LICENSE, RuntimeError("busy")],  # failed re-check: the first read stands
    [MSSQL],                          # STALLED: no re-check at all
    [DONE],                           # complete: no re-check
])
def test_install_template_recheck_flow_matches_factory(install_mod, monkeypatch, reads):
    import vcfcf_dashboards.client as dc

    did = reads[0]["id"]
    wanted = [(did, "X")]

    def _zip_or_raise(item):
        if isinstance(item, Exception):
            raise item
        return _export_zip(item)

    factory_reads = list(reads)

    def _fake_export(client, types, timeout_s=0, label=""):
        item = factory_reads.pop(0)
        if isinstance(item, Exception):
            raise dc.VCFOpsError(str(item))
        return _export_zip(item)

    monkeypatch.setattr(dc, "export_content_zip", _fake_export)
    monkeypatch.setattr(dc, "list_adapter_kind_keys", lambda c: set(INSTALLED))
    core_slept, mine_slept = [], []
    core = dc.check_dashboard_materialization(
        object(), [_D(did, "X")], recheck_wait_s=60, _sleep=core_slept.append)

    client = _ExportClient([r for r in reads])
    client.export_dashboards_zip = (lambda q=list(reads): _zip_or_raise(q.pop(0)))
    mine = install_mod._check_materialization(client, wanted, 60, _sleep=mine_slept.append)

    assert core_slept == mine_slept
    assert [(c.state, c.checked_after_s) for c in core] == [
        (m["state"], m["after"]) for m in mine]
    assert [mat.describe_status(c) for c in core] == [install_mod._mat_describe(m) for m in mine]


# --- review NIT 4: a STALLED line is never filed as a super metric enable failure ---

def test_install_template_stalled_name_with_enable_is_not_an_enable_warning(
        install_mod, monkeypatch, tmp_path, capsys):
    stalled = dict(LICENSE, entryKeys={"resourceKind": [_rk("X", "mpb_rubrik", 0)]})

    class _StubClient(_ExportClient):
        def __init__(self, *a, **k):
            super().__init__([_export_zip(stalled)])
            self._user = "admin"

        def authenticate(self):
            return None

        def discover_marker_filename(self):
            return "1L.v1"

        def get_current_user(self):
            return {"id": "u1"}

    def _one_bundle(bundle, gctx, step, total):
        gctx["imported_dashboards"].append((ID_LICENSE, "Enable and Resolve Board"))
        return 0, [], []

    monkeypatch.setattr(install_mod, "Client", _StubClient)
    monkeypatch.setattr(install_mod, "_install_one_bundle", _one_bundle)
    bundles = [{"dir": tmp_path, "manifest": {"content": {}}, "name": "b"}]
    with pytest.raises(SystemExit) as exc:
        install_mod._run_install(_args(skip_enable=True, force=False), "ops.example.test",
                                 "admin", "local", "pw", False, bundles)
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "WARN  MATERIALIZATION STALLED: dashboard 'Enable and Resolve Board'" in out
    assert "super metrics could not be enabled" not in out
