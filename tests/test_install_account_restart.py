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
    ``fail_reads_from``: every GET at or after that elapsed time raises.
    ``read_code``: every GET answers that HTTP code. A state of UNKNOWN is
    served as a resource with no status entry.
    """

    def __init__(self, states, clock=None, schedule=None, on_start=None,
                 start_code=None, kind=KIND, fail_reads=False,
                 fail_reads_from=None, read_code=None):
        self.states = dict(states)
        self.clock = clock
        self.t0 = clock.now if clock else 0.0
        self.schedule = {k: list(v) for k, v in (schedule or {}).items()}
        self.on_start = on_start or {}
        self.start_code = start_code or {}
        self.kind = kind
        self.fail_reads = fail_reads
        self.fail_reads_from = fail_reads_from
        self.read_code = read_code
        self.starts = []          # (id, elapsed)
        self.calls = []
        self.timeouts = []        # (method, path, timeout)

    def _tick(self):
        if not self.clock:
            return
        el = self.clock.now - self.t0
        for aid, steps in self.schedule.items():
            while steps and steps[0][0] <= el:
                self.states[aid] = steps.pop(0)[1]

    def _request(self, method, path, **kw):
        self.calls.append((method, path, kw.get("params")))
        self.timeouts.append((method, path, kw.get("timeout")))
        self._tick()
        el = (self.clock.now - self.t0) if self.clock else 0.0
        if method == "GET" and (self.fail_reads or (
                self.fail_reads_from is not None and el >= self.fail_reads_from)):
            raise ConnectionError("connection refused")
        if method == "GET" and self.read_code is not None:
            return _Resp(self.read_code, None, "not allowed")
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
                {"identifier": aid, "resourceStatusStates": [] if self.states[aid] == "UNKNOWN" else [
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


@pytest.mark.parametrize("foreign", ["FAILED", "STARTED"])
def test_another_instances_status_entry_is_not_the_accounts_state(foreign):
    """Codex P2 on PR #293: a resource with only another adapter instance's
    status entry took that state, so a foreign FAILED drew a start and a
    foreign STARTED a false ACCOUNT OK. It stays unreadable."""
    class C:
        def __init__(self):
            self.puts = []

        def _request(self, method, path, **kw):
            if method == "PUT":
                self.puts.append(path)
                return _Resp(200)
            if path == "/api/adapters":
                return _Resp(200, {"adapterInstancesInfoDto": [
                    {"id": "a1", "resourceKey": {"name": "one", "adapterKindKey": KIND}}]})
            return _Resp(200, {"resourceList": [
                {"identifier": "a1", "resourceStatusStates": [
                    {"adapterInstanceId": "someone-else", "resourceState": foreign}]}]})

    c = C()
    assert ar.read_accounts(c, [KIND])["a1"].state == ar.UNREADABLE_STATE
    clock = _Clock()
    rc, out, err = _run(c, _before({"a1": "STARTED"}), clock)
    assert c.puts == []
    assert rc == 0
    assert "ACCOUNT OK" not in out
    assert "state unreadable" in err


def test_read_accounts_raises_on_non_200():
    class C:
        def _request(self, *a, **k):
            return _Resp(500, None, "boom")

    with pytest.raises(RuntimeError, match="HTTP 500"):
        ar.read_accounts(C(), [KIND])


def test_read_accounts_two_kinds_one_with_no_instances():
    calls = []

    class C:
        def _request(self, method, path, **kw):
            calls.append((path, kw["params"]))
            if path == "/api/adapters":
                if kw["params"]["adapterKindKey"] == "kind_a":
                    return _Resp(200, {"adapterInstancesInfoDto": [
                        {"id": "a1", "resourceKey": {"name": "one", "adapterKindKey": "kind_a"}},
                        {"id": "a2", "resourceKey": {"name": "two", "adapterKindKey": "kind_a"}}]})
                return _Resp(200, {"adapterInstancesInfoDto": []})
            return _Resp(200, {"resourceList": [
                {"identifier": aid, "resourceStatusStates": [
                    {"adapterInstanceId": aid, "resourceState": "STARTED"}]}
                for aid in kw["params"]["resourceId"]]})

    got = ar.read_accounts(C(), ["kind_a", "kind_empty"])
    assert sorted(got) == ["a1", "a2"]
    assert {a.adapter_kind for a in got.values()} == {"kind_a"}
    assert all(a.state == "STARTED" for a in got.values())
    # One GET per kind, then one batched resources GET.
    assert [p for p, _ in calls] == ["/api/adapters", "/api/adapters", "/api/resources"]


def test_read_accounts_one_failing_kind_fails_the_whole_read():
    class C:
        def _request(self, method, path, **kw):
            if kw["params"].get("adapterKindKey") == "bad":
                return _Resp(500, None, "boom")
            return _Resp(200, {"adapterInstancesInfoDto": []})

    with pytest.raises(RuntimeError, match="adapterKindKey=bad"):
        ar.read_accounts(C(), ["good", "bad"])


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


def test_refailing_account_gets_a_second_start_never_a_third():
    clock = _Clock()
    ids = {"a1": "STARTED"}
    suite = FakeSuite({"a1": "FAILED"}, clock=clock, on_start={"a1": "FAILED"})
    rc, out, err = _run(suite, _before(ids), clock)
    assert rc == ar.ACCOUNTS_NOT_STARTED_RC
    assert len(suite.starts) == ar.MAX_STARTS == 2
    (_, first), (_, second) = suite.starts
    assert first >= ar.START_DELAY_S
    assert second - first >= ar.RETRY_AFTER_S
    assert second < ar.TIMEOUT_S
    assert "re-issued a second time" in out
    assert "ACCOUNT NOT STARTED" in err
    assert "re-issued 2 time(s)" in err
    assert "Do not reinstall" in err
    assert clock.now - 1000.0 >= ar.TIMEOUT_S


def test_second_start_recovers_an_account_whose_first_start_came_too_early():
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock, on_start={"a1": "FAILED"})
    real = suite._request

    def jar_loads_late(method, path, **kw):
        # The collector has the jar by the second start.
        if method == "PUT" and suite.starts:
            suite.on_start["a1"] = "STARTED"
        return real(method, path, **kw)

    suite._request = jar_loads_late
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == 0, err
    assert len(suite.starts) == 2
    assert "ACCOUNT OK (restarted)" in out


def test_an_accepted_start_that_holds_is_not_repeated():
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock)
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == 0
    assert len(suite.starts) == 1


def test_refused_start_is_reported_with_the_servers_answer_and_not_retried():
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock, start_code={"a1": 500})
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == ar.ACCOUNTS_NOT_STARTED_RC
    assert len(suite.starts) == 1
    assert "start monitoring was refused: HTTP 500: server said no" in err


# B1: a prior counts as known only for STARTED, STARTING, UPDATING, FAILED.

@pytest.mark.parametrize("prior", ["STARTED", "STARTING", "UPDATING", "FAILED"])
def test_known_prior_stopped_after_install_is_started(prior):
    clock = _Clock()
    suite = FakeSuite({"a1": "STOPPED"}, clock=clock)
    rc, out, err = _run(suite, _before({"a1": prior}), clock)
    assert rc == 0, err
    assert [a for a, _ in suite.starts] == ["a1"]


@pytest.mark.parametrize("prior", ["STOPPED", "STOPPING", "MAINTAINED", "MAINTAINED_MANUAL"])
@pytest.mark.parametrize("post", ["STOPPED", "FAILED"])
def test_held_prior_is_never_started(prior, post):
    clock = _Clock()
    suite = FakeSuite({"a1": post}, clock=clock)
    rc, out, err = _run(suite, _before({"a1": prior}), clock)
    assert rc == 0
    assert suite.starts == []
    assert "ACCOUNT LEFT ALONE" in out


@pytest.mark.parametrize("prior", ["UNKNOWN", "NONE", "NOT_EXISTING", "REMOVING"])
def test_unusable_prior_stopped_after_install_is_left_alone(prior):
    clock = _Clock()
    suite = FakeSuite({"a1": "STOPPED"}, clock=clock)
    rc, out, err = _run(suite, _before({"a1": prior}), clock)
    assert rc == 0
    assert suite.starts == []
    assert "ACCOUNT NOT COLLECTING" in err
    # Settles once the watch ends instead of waiting out the timeout.
    assert clock.now - 1000.0 < ar.TIMEOUT_S


@pytest.mark.parametrize("prior", ["UNKNOWN", "NONE", "NOT_EXISTING", "REMOVING"])
def test_unusable_prior_failed_after_install_is_started(prior):
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock)
    rc, out, err = _run(suite, _before({"a1": prior}), clock)
    assert rc == 0, err
    assert [a for a, _ in suite.starts] == ["a1"]


def test_prior_read_without_a_status_entry_is_unusable_end_to_end():
    """read_accounts gives UNKNOWN for a missing status entry; that prior
    must not license a start of a STOPPED account."""
    clock = _Clock()
    pre = FakeSuite({"a1": "UNKNOWN"})
    before = ar.read_accounts(pre, [KIND])
    assert before["a1"].state == ar.UNREADABLE_STATE
    suite = FakeSuite({"a1": "STOPPED"}, clock=clock)
    rc, out, err = _run(suite, before, clock)
    assert suite.starts == []
    assert rc == 0


# N4: a missing post-install state is unreadable, not NOT STARTED.

def test_unreadable_post_install_state_is_unchecked_not_a_failure():
    clock = _Clock()
    suite = FakeSuite({"a1": "UNKNOWN"}, clock=clock)
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == 0
    assert suite.starts == []
    assert "ACCOUNT UNCHECKED" in err and "state unreadable" in err
    assert "NOT STARTED" not in err
    assert clock.now - 1000.0 < ar.TIMEOUT_S


# W1: never a verdict, or a start, from a stale reading.

def test_failed_final_read_reports_unchecked_not_a_failure():
    clock = _Clock()
    # FAILED until reads start failing at 105 s; the account recovers at
    # 200 s on its own, which the installer never sees.
    suite = FakeSuite({"a1": "FAILED"}, clock=clock, fail_reads_from=105,
                      schedule={"a1": [(200, "STARTED")]})
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == 0
    assert "ACCOUNTS UNCHECKED" in err
    assert "State as of 90 s" in err      # reads at 0, 15, ... 90 s succeeded
    assert "NOT STARTED" not in err
    # The last good read was before the start delay: no start went out.
    assert suite.starts == []


def test_one_warn_for_a_persistent_read_failure():
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock, fail_reads=True)
    rc, out, err = _run(suite, None, clock)
    assert err.count("WARN: account state read failed") == 1
    assert "failed read(s)" in err


# N2: an auth refusal stops the watch.

@pytest.mark.parametrize("code", [401, 403])
def test_auth_refusal_stops_polling_with_one_warn(code):
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock, read_code=code)
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == 0
    assert clock.sleeps == []
    assert err.count("WARN:") == 1
    assert "not retrying" in err and "1 failed read(s)" in err
    assert "ACCOUNTS UNCHECKED" in err


def test_token_refusal_from_the_client_counts_as_auth_refusal():
    assert ar._is_auth_refusal(RuntimeError("auth failed (401): bad"))
    assert not ar._is_auth_refusal(RuntimeError("auth failed (500): oops"))


# W2: timeouts on every Suite API call.

def test_every_suite_call_carries_a_timeout():
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock)
    _run(suite, _before({"a1": "STARTED"}), clock)
    methods = {(m, p.split("/")[-1]) for m, p, _ in suite.timeouts}
    assert ("PUT", "start") in methods and ("GET", "adapters") in methods \
        and ("GET", "resources") in methods
    assert all(t is not None and 0 < t <= ar.REQUEST_TIMEOUT_S
               for _, _, t in suite.timeouts)


def _slow(suite, clock, methods=("PUT",)):
    """Every request of ``methods`` runs to its timeout on the fake clock."""
    real = suite._request

    def slow(method, path, **kw):
        resp = real(method, path, **kw)
        if method in methods:
            clock.now += kw["timeout"]
        return resp

    suite._request = slow


def test_many_slow_starts_finish_within_the_cap():
    """Codex P2 on PR #293: 12 FAILED accounts whose start PUTs each run to
    the 30 s timeout took a 300 s check to 495 s."""
    clock = _Clock()
    ids = {f"a{i:02d}": "FAILED" for i in range(12)}
    suite = FakeSuite(ids, clock=clock, on_start={aid: "FAILED" for aid in ids})
    _slow(suite, clock)
    rc, out, err = _run(suite, _before({aid: "STARTED" for aid in ids}), clock)
    assert clock.now - 1000.0 <= ar.TIMEOUT_S
    assert rc == ar.ACCOUNTS_NOT_STARTED_RC
    # Every request's timeout fit inside what was left of the budget.
    assert all(t <= ar.REQUEST_TIMEOUT_S for _, _, t in suite.timeouts)
    # The budget ran out mid-sweep: the rest are named, none sent past it.
    assert "ran out before start monitoring could be sent" in err
    assert "budget ran out" in err
    assert len(suite.starts) < 12


def test_slow_reads_and_starts_together_stay_within_the_cap():
    clock = _Clock()
    ids = {f"a{i}": "FAILED" for i in range(5)}
    suite = FakeSuite(ids, clock=clock, on_start={aid: "FAILED" for aid in ids})
    _slow(suite, clock, methods=("GET", "PUT"))
    rc, out, err = _run(suite, _before({aid: "STARTED" for aid in ids}), clock)
    assert clock.now - 1000.0 <= ar.TIMEOUT_S


def test_second_start_is_timed_from_each_accounts_own_first_start():
    """Codex P2 on PR #293: every start in a sweep was stamped with the
    poll's start time, so a later account whose first start went out late
    (behind slow ones) could get its second under 60 s after it."""
    clock = _Clock()
    ids = {"a0": "FAILED", "a1": "FAILED", "a2": "FAILED"}
    # a0 and a1 take their start; a2 (started last, 40 s late) fails again.
    suite = FakeSuite(ids, clock=clock,
                      on_start={"a0": "STARTED", "a1": "STARTED", "a2": "FAILED"})
    real = suite._request

    def slow_put(method, path, **kw):
        resp = real(method, path, **kw)
        if method == "PUT":
            clock.now += 20          # each start takes 20 s
        return resp

    suite._request = slow_put
    rc, out, err = _run(suite, _before({aid: "STARTED" for aid in ids}), clock)
    by_id = {}
    for aid, at in suite.starts:
        by_id.setdefault(aid, []).append(at)
    assert by_id["a0"] == [ar.START_DELAY_S]
    assert by_id["a2"][0] == ar.START_DELAY_S + 40
    # a2 does get its second start, 60 s or more after its own first.
    assert len(by_id["a2"]) == 2
    assert by_id["a2"][1] - by_id["a2"][0] >= ar.RETRY_AFTER_S
    for times in by_id.values():
        assert all(b - a >= ar.RETRY_AFTER_S for a, b in zip(times, times[1:]))


JAR_SYNC = "Adapter jar synchronization failed"


def test_not_started_says_to_rerun_the_install_on_a_jar_sync_failure():
    """Compliance 0.0.0.103 on devel_8_18: the proxy's jar sync failed and it
    loaded the old version; a start would only run the old jar."""
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock, on_start={"a1": "FAILED"})
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == ar.ACCOUNTS_NOT_STARTED_RC
    line = next(l for l in err.splitlines() if l.startswith("ACCOUNT NOT STARTED"))
    assert JAR_SYNC in line
    assert "re-run the same install rather than starting the account" in line
    assert "Do not reinstall for any other reason" in line


def test_note_after_any_start_warns_it_may_run_the_old_jar():
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock)
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert rc == 0
    assert "ACCOUNT OK (restarted)" in out
    note = [l for l in out.splitlines() if l.startswith("NOTE:")]
    assert len(note) == 1 and JAR_SYNC in note[0]


def test_no_note_when_no_start_was_sent():
    clock = _Clock()
    suite = FakeSuite({"a1": "STARTED"}, clock=clock)
    rc, out, err = _run(suite, _before({"a1": "STARTED"}), clock)
    assert "NOTE:" not in out and JAR_SYNC not in out + err


def test_cli_epilog_names_the_jar_sync_exception():
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf), pytest.raises(SystemExit):
        cli.main(["install", "--help"])
    text = " ".join(buf.getvalue().split())
    assert "Do not reinstall on 3, with one exception" in text
    assert JAR_SYNC in text


def _not_started_ids(err):
    return {l.split("id ")[1].split(")")[0] for l in err.splitlines()
            if l.startswith("ACCOUNT NOT STARTED")}


def test_starts_that_use_the_budget_are_followed_by_a_read():
    """Codex P2 on PR #293 (third): six FAILED accounts, each start PUT
    succeeds after 30 s. The starts used the budget up, the loop ended on the
    pre-start FAILED reading and exited 3 for accounts that were STARTED."""
    clock = _Clock()
    ids = {f"a{i}": "FAILED" for i in range(6)}
    suite = FakeSuite(ids, clock=clock)            # a start makes it STARTED
    _slow(suite, clock)                            # each PUT takes its 30 s
    rc, out, err = _run(suite, _before({aid: "STARTED" for aid in ids}), clock)
    started = [aid for aid, _ in suite.starts]
    last_start = max(at for _, at in suite.starts)
    assert clock.now - 1000.0 <= ar.TIMEOUT_S
    # A state read came after the last start, inside the budget.
    reads = [i for i, (m, p, _) in enumerate(suite.calls) if p == "/api/resources"]
    puts = [i for i, (m, p, _) in enumerate(suite.calls) if m == "PUT"]
    assert reads[-1] > puts[-1]
    assert last_start <= ar.TIMEOUT_S - ar.POST_START_READ_RESERVE_S
    # Every account that was started is reported from that read, as OK.
    assert out.count("ACCOUNT OK (restarted)") == len(started)
    assert not (_not_started_ids(err) & set(started))
    # The one the budget had no room for is FAILED and honestly not started.
    missed = set(ids) - set(started)
    assert _not_started_ids(err) == missed
    assert rc == (ar.ACCOUNTS_NOT_STARTED_RC if missed else 0)
    assert "no start was sent" in err


def test_started_account_without_a_post_start_read_is_unchecked_not_not_started():
    """When even the reserved read is cut off (every request runs to its
    timeout), an account whose last start has no reading after it is
    UNCHECKED, never NOT STARTED."""
    clock = _Clock()
    ids = {f"a{i}": "FAILED" for i in range(6)}
    suite = FakeSuite(ids, clock=clock)
    _slow(suite, clock, methods=("GET", "PUT"))
    rc, out, err = _run(suite, _before({aid: "STARTED" for aid in ids}), clock)
    started = {aid for aid, _ in suite.starts}
    assert started
    assert clock.now - 1000.0 <= ar.TIMEOUT_S
    assert not (_not_started_ids(err) & started)
    unchecked = [l for l in err.splitlines() if l.startswith("WARNING: ACCOUNT UNCHECKED")]
    assert unchecked and all("no state was read after it" in l for l in unchecked)


def test_last_request_gets_only_what_is_left():
    clock = _Clock()
    suite = FakeSuite({"a1": "FAILED"}, clock=clock)
    left = {"v": 12.5}
    to = ar._request_timeout(ar.REQUEST_TIMEOUT_S, lambda: left["v"])
    assert to == 12.5
    left["v"] = 0.4
    with pytest.raises(ar.DeadlineReached):
        ar._request_timeout(ar.REQUEST_TIMEOUT_S, lambda: left["v"])
    with pytest.raises(ar.DeadlineReached):
        ar.start_account(suite, "a1", budget=lambda: 0.0)
    assert suite.starts == []      # never sent


def test_read_accounts_default_timeout_is_set():
    suite = FakeSuite({"a1": "STARTED"})
    ar.read_accounts(suite, [KIND])
    assert {t for _, _, t in suite.timeouts} == {ar.REQUEST_TIMEOUT_S}


def test_suite_client_token_acquire_gets_the_timeout(monkeypatch):
    from vcfcf_common import client as common_client

    seen = {}

    class _Sess:
        headers = {}

        def post(self, url, **kw):
            seen.update(kw)
            return _Resp(200, {"token": "t"})

    monkeypatch.setattr(common_client, "new_session", lambda v: _Sess())
    c = ar.default_suite_factory("ops.example", "u", "p", True)
    c.authenticate()
    assert seen["timeout"] == ar.REQUEST_TIMEOUT_S
    # Other callers keep the old behaviour: no timeout key at all.
    seen.clear()
    common_client.VCFOpsClient("ops.example", "u", "p").authenticate()
    assert "timeout" not in seen


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


def test_before_read_timeout_lets_the_install_go_ahead(monkeypatch, tmp_path):
    import requests
    events, pak = _wire_install(monkeypatch, tmp_path)

    def stalled(client, k):
        raise requests.exceptions.ReadTimeout("read timed out (30 s)")

    monkeypatch.setattr(ar, "read_accounts", stalled)
    installer.install_pak(str(pak), materialization_check=False,
                          suite_factory=_factory(events))
    assert "upload" in events and "install" in events
    assert ("restart", (KIND,), None) in events


def test_cli_flag_reaches_install_pak(monkeypatch):
    seen = {}
    monkeypatch.setattr(installer, "install_pak", lambda **kw: seen.update(kw) or 0)
    assert cli.main(["install", "x.pak", "--no-restart-failed"]) == 0
    assert seen["restart_failed"] is False
    seen.clear()
    assert cli.main(["install", "x.pak"]) == 0
    assert seen["restart_failed"] is True
