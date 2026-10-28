"""Post-install account restart (lesson remote-collector-upgrade-start-race).

On a remote collector or Cloud Proxy a pak install sends Start monitoring
before the collector has loaded the new jar, every account of the adapter
kind lands FAILED, and nothing retries (compliance 0.0.0.102 on devel_9_1,
2026-10-28: all three FAILED, a manual start each fixed them). ``install``
now reads the accounts before the upload, watches them after the install,
and sends one start to each the install left FAILED or STOPPED, never to one
the user had stopped or put in maintenance. These tests drive it against a
fake Suite API shaped like the devel_9_1 answers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_managementpacks import account_restart as ar  # noqa: E402
from vcfcf_managementpacks import cli, installer  # noqa: E402

KIND = "vcfcf_compliance"


class _Resp:
    def __init__(self, code, body=None, text=""):
        self.status_code = code
        self._body = body
        self.text = text

    def json(self):
        return self._body


class _Clock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


class FakeSuite:
    """Fake /suite-api: adapter instances with a state each.

    ``states`` maps id -> state. ``schedule`` maps id -> list of
    ``(at_elapsed, state)`` applied as the clock passes them (the race: the
    install leaves the account FAILED). ``on_start`` maps id -> the state a
    start produces (default STARTED); ``start_code`` id -> HTTP code.
    """

    def __init__(self, states, clock=None, schedule=None, on_start=None,
                 start_code=None, kind=KIND, fail_reads=False):
        self.states = dict(states)
        self.clock = clock
        self.t0 = clock.now if clock else 0.0
        self.schedule = {k: list(v) for k, v in (schedule or {}).items()}
        self.on_start = on_start or {}
        self.start_code = start_code or {}
        self.kind = kind
        self.fail_reads = fail_reads
        self.starts = []          # (id, elapsed)
        self.calls = []

    def _tick(self):
        if not self.clock:
            return
        el = self.clock.now - self.t0
        for aid, steps in self.schedule.items():
            while steps and steps[0][0] <= el:
                self.states[aid] = steps.pop(0)[1]

    def _request(self, method, path, **kw):
        self.calls.append((method, path, kw.get("params")))
        self._tick()
        if self.fail_reads and method == "GET":
            raise ConnectionError("connection refused")
        if method == "GET" and path == "/api/adapters":
            kind = kw["params"]["adapterKindKey"]
            if kind != self.kind:
                return _Resp(200, {"adapterInstancesInfoDto": []})
            return _Resp(200, {"adapterInstancesInfoDto": [
                {"id": aid, "collectorId": 2,
                 "resourceKey": {"name": f"acct-{aid}", "adapterKindKey": KIND,
                                 "resourceKindKey": KIND}}
                for aid in self.states]})
        if method == "GET" and path == "/api/resources":
            ids = kw["params"]["resourceId"]
            return _Resp(200, {"resourceList": [
                {"identifier": aid, "resourceStatusStates": [
                    {"adapterInstanceId": aid, "resourceState": self.states[aid],
                     "resourceStatus": "DATA_RECEIVING" if self.states[aid] == "STARTED" else "NONE",
                     "statusMessage": ""}]}
                for aid in ids if aid in self.states]})
        if method == "PUT" and path.endswith("/monitoringstate/start"):
            aid = path.split("/")[3]
            el = (self.clock.now - self.t0) if self.clock else 0.0
            self.starts.append((aid, el))
            code = self.start_code.get(aid, 200)
            if code == 200:
                self.states[aid] = self.on_start.get(aid, "STARTED")
                self.schedule.pop(aid, None)
            return _Resp(code, None, "" if code == 200 else "server said no")
        raise AssertionError(f"unexpected {method} {path}")


def _before(states):
    return {aid: ar.Account(id=aid, name=f"acct-{aid}", adapter_kind=KIND, state=st)
            for aid, st in states.items()}


def _run(suite, before, clock, **kw):
    out, err = [], []
    rc = ar.restart_failed_accounts(suite, [KIND], before, sleep=clock.sleep,
                                    clock=clock.time, out=out.append,
                                    err=err.append, **kw)
    return rc, "\n".join(out), "\n".join(err)


# ---------------------------------------------------------------------------
# read_accounts
# ---------------------------------------------------------------------------

def test_read_accounts_picks_the_instances_own_status_entry():
    class C:
        def _request(self, method, path, **kw):
            if path == "/api/adapters":
                return _Resp(200, {"adapterInstancesInfoDto": [
                    {"id": "a1", "collectorId": 2, "resourceKey": {"name": "one", "adapterKindKey": KIND}},
                    {"id": "a2", "resourceKey": {"name": "two", "adapterKindKey": KIND}}]})
            assert kw["params"]["resourceId"] == ["a1", "a2"]
            return _Resp(200, {"resourceList": [
                {"identifier": "a1", "resourceStatusStates": [
                    {"adapterInstanceId": "other", "resourceState": "STARTED"},
                    {"adapterInstanceId": "a1", "resourceState": "FAILED",
                     "resourceStatus": "NONE", "statusMessage": "Unknown adapter type"}]}]})

    got = ar.read_accounts(C(), [KIND])
    assert got["a1"].state == "FAILED"
    assert got["a1"].message == "Unknown adapter type"
    assert got["a1"].collector_id == 2
    assert got["a2"].state == "UNKNOWN"     # no resource entry


def test_read_accounts_raises_on_non_200():
    class C:
        def _request(self, *a, **k):
            return _Resp(500, None, "boom")

    with pytest.raises(RuntimeError, match="HTTP 500"):
        ar.read_accounts(C(), [KIND])


def test_pak_adapter_kinds_splits_the_manifest_field():
    assert ar.pak_adapter_kinds({"adapter_kinds": "a, b,,"}) == ["a", "b"]
    assert ar.pak_adapter_kinds({}) == []


# ---------------------------------------------------------------------------
# restart_failed_accounts
# ---------------------------------------------------------------------------

def test_race_left_failed_accounts_get_one_start_after_the_delay():
    clock = _Clock()
    ids = {"a1": "STARTED", "a2": "STARTED", "a3": "STARTED"}
    # The install's own start lands 30 s in and is rejected: FAILED.
    sched = {aid: [(30, "FAILED")] for aid in ids}
    suite = FakeSuite(ids, clock=clock, schedule=sched)
    rc, out, err = _run(suite, _before(ids), clock)
    assert rc == 0, err
    assert sorted(a for a, _ in suite.starts) == ["a1", "a2", "a3"]
    assert all(el >= ar.START_DELAY_S for _, el in suite.starts)
    assert out.count("ACCOUNT START SENT") == 3
    assert out.count("ACCOUNT OK (restarted)") == 3
    assert "was STARTED before the install" in out


def test_healthy_accounts_are_watched_then_left_alone():
    clock = _Clock()
    ids = {"a1": "STARTED"}
    suite = FakeSuite(ids, clock=clock)
    rc, out, err = _run(suite, _before(ids), clock)
    assert rc == 0
    assert suite.starts == []
    assert "ACCOUNT OK (collecting)" in out
    # Stops once the delay has passed, not at the timeout.
    assert clock.now - 1000.0 < ar.TIMEOUT_S


def test_user_stopped_and_maintained_accounts_are_never_started():
    clock = _Clock()
    before = {"s": "STOPPED", "m": "MAINTAINED_MANUAL", "f": "STARTED"}
    after = {"s": "STOPPED", "m": "MAINTAINED_MANUAL", "f": "FAILED"}
    suite = FakeSuite(after, clock=clock)
    rc, out, err = _run(suite, _before(before), clock)
    assert rc == 0, err
    assert [a for a, _ in suite.starts] == ["f"]
    assert out.count("ACCOUNT LEFT ALONE") == 2


def test_start_is_sent_once_and_a_still_failed_account_fails_the_install_check():
    clock = _Clock()
    ids = {"a1": "STARTED"}
    suite = FakeSuite({"a1": "FAILED"}, clock=clock, on_start={"a1": "FAILED"})
    rc, out, err = _run(suite, _before(ids), clock)
    assert rc == ar.ACCOUNTS_NOT_STARTED_RC
    assert len(suite.starts) == 1
    assert "ACCOUNT NOT STARTED" in err
    assert "re-issued once" in err
    assert "Do not reinstall" in err
    assert clock.now - 1000.0 >= ar.TIMEOUT_S


def test_refused_start_is_reported_with_the_servers_answer():
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock, start_code={"a1": 500})
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == ar.ACCOUNTS_NOT_STARTED_RC
    assert "start monitoring was refused: HTTP 500: server said no" in err


def test_stopped_after_install_from_started_gets_a_start():
    clock = _Clock()
    suite = FakeSuite({"a1": "STOPPED"}, clock=clock)
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == 0
    assert [a for a, _ in suite.starts] == ["a1"]


def test_without_a_before_reading_only_failed_is_started():
    clock = _Clock()
    suite = FakeSuite({"f": "FAILED", "s": "STOPPED"}, clock=clock)
    rc, out, err = _run(suite, None, clock)
    assert rc == 0
    assert [a for a, _ in suite.starts] == ["f"]
    assert "ACCOUNT NOT COLLECTING" in err and "acct-s" in err


def test_no_instances_returns_at_once():
    clock = _Clock()
    suite = FakeSuite({}, clock=clock)
    rc, out, err = _run(suite, {}, clock)
    assert rc == 0
    assert clock.sleeps == []
    assert "nothing to start" in out


def test_unreadable_states_warn_and_leave_the_exit_code_alone():
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock, fail_reads=True)
    rc, out, err = _run(suite, None, clock)
    assert rc == 0
    assert "ACCOUNTS UNCHECKED" in err
    assert suite.starts == []


def test_a_failed_read_mid_watch_is_retried():
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock)
    real = suite._request
    n = {"gets": 0}

    def flaky(method, path, **kw):
        if method == "GET" and path == "/api/adapters":
            n["gets"] += 1
            if n["gets"] == 2:
                raise ConnectionError("blip")
        return real(method, path, **kw)

    suite._request = flaky
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == 0
    assert "will retry" in err
    assert len(suite.starts) == 1


# ---------------------------------------------------------------------------
# install_pak wiring and the CLI flag
# ---------------------------------------------------------------------------

def _wire_install(monkeypatch, tmp_path, kinds=KIND):
    events = []

    class _Session:
        def __init__(self, **kw):
            pass

        def login(self):
            pass

        def logout(self):
            events.append("logout")

        def prepare_upload(self):
            pass

        def upload_pak(self, *a, **k):
            events.append("upload")
            return {"pakId": "X-1", "solutionName": "X", "solutionVersion": "0.0.0.102"}

        def trigger_install(self, pak_id):
            events.append("install")

        def is_pak_installing(self, timeout=None):
            return {"isPakInstalling": False, "isPakUninstallActive": False}

    monkeypatch.setattr(installer, "_UISession", _Session)
    monkeypatch.setattr(installer, "_resolve_credentials",
                        lambda *a, **k: ("ops.example", "u", "p", True))
    monkeypatch.setattr(installer, "_parse_manifest_txt",
                        lambda p: {"name": "X", "version": "0.0.0.102",
                                   "adapter_kinds": kinds})
    monkeypatch.setattr(installer, "_verify_adapter_registered",
                        lambda *a, **k: events.append("verify"))
    monkeypatch.setattr(installer, "_preflight_unsigned_policy", lambda *a, **k: None)

    def fake_read(client, k):
        events.append(("read", tuple(k)))
        return _before({"a1": "STARTED"})

    def fake_restart(client, k, before):
        events.append(("restart", tuple(k), sorted(before) if before else before))
        return ar.ACCOUNTS_NOT_STARTED_RC

    monkeypatch.setattr(ar, "read_accounts", fake_read)
    monkeypatch.setattr(ar, "restart_failed_accounts", fake_restart)
    pak = tmp_path / "x.pak"
    pak.write_bytes(b"PK")
    return events, pak


def _factory(events):
    def f(*a):
        events.append("suite")
        return object()
    return f


def test_install_reads_accounts_before_upload_and_restarts_after_verify(monkeypatch, tmp_path):
    events, pak = _wire_install(monkeypatch, tmp_path)
    rc = installer.install_pak(str(pak), materialization_check=False,
                               suite_factory=_factory(events))
    assert rc == ar.ACCOUNTS_NOT_STARTED_RC
    names = [e if isinstance(e, str) else e[0] for e in events]
    assert names.index("read") < names.index("upload")
    assert names.index("verify") < names.index("restart")
    assert ("restart", (KIND,), ["a1"]) in events


def test_no_restart_failed_skips_the_check(monkeypatch, tmp_path, capsys):
    events, pak = _wire_install(monkeypatch, tmp_path)
    rc = installer.install_pak(str(pak), materialization_check=False,
                               restart_failed=False, suite_factory=_factory(events))
    assert rc == 0
    assert "suite" not in events
    assert not any(isinstance(e, tuple) for e in events)
    assert "--no-restart-failed" in capsys.readouterr().out


def test_no_wait_never_touches_accounts(monkeypatch, tmp_path):
    events, pak = _wire_install(monkeypatch, tmp_path)
    rc = installer.install_pak(str(pak), wait=False, suite_factory=_factory(events))
    assert rc == 0
    assert "suite" not in events


def test_pak_without_adapter_kinds_skips_the_check(monkeypatch, tmp_path):
    events, pak = _wire_install(monkeypatch, tmp_path, kinds="")
    rc = installer.install_pak(str(pak), materialization_check=False,
                               suite_factory=_factory(events))
    assert rc == 0
    assert "suite" not in events


def test_account_rc_combines_with_the_dashboard_check(monkeypatch, tmp_path):
    from vcfcf_managementpacks import post_install
    events, pak = _wire_install(monkeypatch, tmp_path)
    monkeypatch.setattr(post_install, "report_pak_dashboards", lambda *a, **k: 0)
    rc = installer.install_pak(str(pak), suite_factory=_factory(events))
    assert rc == ar.ACCOUNTS_NOT_STARTED_RC


def test_before_read_failure_passes_none_and_install_goes_ahead(monkeypatch, tmp_path):
    events, pak = _wire_install(monkeypatch, tmp_path)

    def boom(client, k):
        raise ConnectionError("no route")

    monkeypatch.setattr(ar, "read_accounts", boom)
    installer.install_pak(str(pak), materialization_check=False,
                          suite_factory=_factory(events))
    assert "install" in events
    assert ("restart", (KIND,), None) in events


def test_cli_flag_reaches_install_pak(monkeypatch):
    seen = {}
    monkeypatch.setattr(installer, "install_pak", lambda **kw: seen.update(kw) or 0)
    assert cli.main(["install", "x.pak", "--no-restart-failed"]) == 0
    assert seen["restart_failed"] is False
    seen.clear()
    assert cli.main(["install", "x.pak"]) == 0
    assert seen["restart_failed"] is True
