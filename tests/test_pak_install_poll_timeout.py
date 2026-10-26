"""Pak install poll timeout (2026-10-26).

Compliance build 100 on devel_8_18 and devel_9_1 was still installing when
the old 300 s poll ran out; the CLI exited 1 and the post-install checks
never ran, though the server finished minutes later. The poll now defaults
to 1800 s (``--install-timeout`` / ``VCFCF_INSTALL_TIMEOUT_S``), and running
out exits 4 with an INSTALL STILL RUNNING message instead of a failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_managementpacks import cli, installer, post_install  # noqa: E402


class _Clock:
    """Fake time: sleep advances it, so a poll loop runs without waiting."""

    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    def sleep(self, s):
        self.now += s


def _wire(monkeypatch, tmp_path, installing_polls, script=None):
    """Fake session that reports isPakInstalling=True for ``installing_polls``
    polls (None: forever), then False.  ``script(n)``, when given, answers
    poll ``n`` instead (return a body, or raise)."""
    events = []
    clock = _Clock()
    polls = {"n": 0, "timeouts": []}

    class _Session:
        def __init__(self, **kw):
            pass

        def login(self):
            events.append("login")

        def logout(self):
            events.append("logout")

        def prepare_upload(self):
            pass

        def upload_pak(self, *a, **k):
            return {"pakId": "X-1", "solutionName": "X", "solutionVersion": "0.0.0.100"}

        def trigger_install(self, pak_id):
            events.append("install")

        def is_pak_installing(self, timeout=None):
            polls["n"] += 1
            polls["timeouts"].append(timeout)
            if script is not None:
                return script(polls["n"])
            if installing_polls is None or polls["n"] <= installing_polls:
                return {"isPakInstalling": True, "isPakUninstallActive": False}
            return {"isPakInstalling": False, "isPakUninstallActive": False}

    monkeypatch.setattr(installer, "_UISession", _Session)
    monkeypatch.setattr(installer, "time", clock)
    monkeypatch.setattr(installer, "_resolve_credentials",
                        lambda *a, **k: ("ops.example", "u", "p", True))
    monkeypatch.setattr(installer, "_parse_manifest_txt",
                        lambda p: {"name": "X", "version": "0.0.0.100"})
    monkeypatch.setattr(installer, "_verify_adapter_registered",
                        lambda *a, **k: events.append("verify"))
    monkeypatch.setattr(installer, "_preflight_unsigned_policy", lambda *a, **k: None)

    def _report(p, **kw):
        events.append("materialization")
        return 0

    monkeypatch.setattr(post_install, "report_pak_dashboards", _report)
    pak = tmp_path / "x.pak"
    pak.write_bytes(b"PK")
    return pak, events, clock, polls


def test_default_is_1800_and_distinct_rc():
    assert installer.INSTALL_POLL_TIMEOUT == 1800
    assert installer.INSTALL_STILL_RUNNING_RC == 4
    assert installer.INSTALL_STILL_RUNNING_RC not in (0, 1, 2, post_install.POST_INSTALL_FAILED_RC)
    # Uninstall keeps its own poll.
    assert installer.POLL_TIMEOUT == 300


def test_resolve_install_timeout(monkeypatch, capsys):
    monkeypatch.delenv(installer.INSTALL_TIMEOUT_ENV, raising=False)
    assert installer.resolve_install_timeout() == 1800
    assert installer.resolve_install_timeout(60) == 60
    monkeypatch.setenv(installer.INSTALL_TIMEOUT_ENV, "2400")
    assert installer.resolve_install_timeout() == 2400
    assert installer.resolve_install_timeout(60) == 60  # flag beats env
    for bad in ("soon", "0", "-5"):
        monkeypatch.setenv(installer.INSTALL_TIMEOUT_ENV, bad)
        assert installer.resolve_install_timeout() == 1800
        assert installer.INSTALL_TIMEOUT_ENV in capsys.readouterr().err


def test_install_finishing_after_300s_completes(monkeypatch, tmp_path):
    """The 2026-10-26 case: still installing at 300 s, done later."""
    monkeypatch.delenv(installer.INSTALL_TIMEOUT_ENV, raising=False)
    # 5 s polls: 120 installing polls is 600 s, past the old 300 s.
    pak, events, clock, _ = _wire(monkeypatch, tmp_path, installing_polls=120)
    rc = installer.install_pak(str(pak))
    assert rc == 0
    assert events == ["login", "install", "verify", "logout", "materialization"]
    assert clock.now - 1000.0 >= 600


def test_timeout_exits_4_still_running_no_checks(monkeypatch, tmp_path, capsys):
    pak, events, clock, _ = _wire(monkeypatch, tmp_path, installing_polls=None)
    rc = installer.install_pak(str(pak), poll_timeout=60)
    assert rc == installer.INSTALL_STILL_RUNNING_RC == 4
    # Logged out, verify and the post-install checks did not run.
    assert events == ["login", "install", "logout"]
    assert 60 <= clock.now - 1000.0 <= 65
    err = capsys.readouterr().err
    assert "INSTALL STILL RUNNING" in err
    assert "ERROR:" not in err
    assert "pakInstalling=True" in err
    assert "0.0.0.100" in err and "ops.example" in err
    assert "do not reinstall" in err
    assert "did NOT run" in err
    assert "--install-timeout" in err and installer.INSTALL_TIMEOUT_ENV in err


def test_default_timeout_runs_full_1800s(monkeypatch, tmp_path):
    monkeypatch.delenv(installer.INSTALL_TIMEOUT_ENV, raising=False)
    pak, _, clock, _ = _wire(monkeypatch, tmp_path, installing_polls=None)
    assert installer.install_pak(str(pak)) == 4
    assert 1800 <= clock.now - 1000.0 <= 1805


def test_env_override_applies(monkeypatch, tmp_path):
    monkeypatch.setenv(installer.INSTALL_TIMEOUT_ENV, "30")
    pak, _, clock, _ = _wire(monkeypatch, tmp_path, installing_polls=None)
    assert installer.install_pak(str(pak)) == 4
    assert 30 <= clock.now - 1000.0 <= 35


def test_no_wait_still_returns_0(monkeypatch, tmp_path):
    pak, events, _, polls = _wire(monkeypatch, tmp_path, installing_polls=None)
    assert installer.install_pak(str(pak), wait=False) == 0
    assert polls["n"] == 0
    assert "materialization" not in events


def test_cli_flag_passes_through(monkeypatch):
    seen = {}

    def _fake(**kw):
        seen.update(kw)
        return 4

    monkeypatch.setattr(installer, "install_pak", _fake)
    monkeypatch.delenv("VCFCF_SUMMARY_REBIND", raising=False)
    assert cli.main(["install", "x.pak", "--install-timeout", "2700"]) == 4
    assert seen["poll_timeout"] == 2700
    seen.clear()
    cli.main(["install", "x.pak"])
    assert seen["poll_timeout"] is None


@pytest.mark.parametrize("bad", ["0", "-1", "soon"])
def test_cli_flag_rejects_non_positive(bad, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["install", "x.pak", "--install-timeout", bad])
    assert exc.value.code == 2
    assert "positive whole number" in capsys.readouterr().err


def test_epilog_documents_exit_4():
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction")
    epilog = sub.choices["install"].epilog
    assert "4 the wait" in epilog
    assert "--install-timeout or VCFCF_INSTALL_TIMEOUT_S, default 1800 s" in epilog
    assert "Do not reinstall on 4" in epilog


# --- review B1: exit 4 needs a last poll that read isPakInstalling true ------

def _raise(n):
    raise RuntimeError("isPakInstalling returned HTTP 401. Response body: x")


def test_every_poll_fails_exits_1_not_4(monkeypatch, tmp_path, capsys):
    pak, events, _, polls = _wire(monkeypatch, tmp_path, None, script=_raise)
    with pytest.raises(SystemExit) as exc:
        installer.install_pak(str(pak), poll_timeout=30)
    assert exc.value.code == 1
    assert "logout" in events and "verify" not in events
    err = capsys.readouterr().err
    assert "INSTALL STILL RUNNING" not in err
    assert f"the last {polls['n']} status poll(s) failed" in err
    assert "HTTP 401" in err
    assert "Last good status: (unknown)" in err


def test_missing_key_is_a_failed_poll(monkeypatch, tmp_path, capsys):
    """An answer without isPakInstalling was read as True before review B1."""
    pak, _, _, polls = _wire(monkeypatch, tmp_path, None,
                             script=lambda n: {"error": "session expired"})
    with pytest.raises(SystemExit) as exc:
        installer.install_pak(str(pak), poll_timeout=30)
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "INSTALL STILL RUNNING" not in err
    assert "no boolean isPakInstalling" in err
    assert f"the last {polls['n']} status poll(s) failed" in err


def test_true_then_failures_exits_1_naming_stale_status(monkeypatch, tmp_path, capsys):
    def script(n):
        if n <= 2:
            return {"isPakInstalling": True, "isPakUninstallActive": False}
        raise RuntimeError("connection reset")

    pak, _, _, polls = _wire(monkeypatch, tmp_path, None, script=script)
    with pytest.raises(SystemExit) as exc:
        installer.install_pak(str(pak), poll_timeout=60)
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "INSTALL STILL RUNNING" not in err
    assert f"the last {polls['n'] - 2} status poll(s) failed" in err
    assert "connection reset" in err
    assert "Last good status: pakInstalling=True" in err


def test_failures_then_true_exits_4(monkeypatch, tmp_path, capsys):
    """A failed poll followed by a good True read is evidence again."""
    def script(n):
        if n <= 3:
            raise RuntimeError("blip")
        return {"isPakInstalling": True, "isPakUninstallActive": False}

    pak, _, _, _ = _wire(monkeypatch, tmp_path, None, script=script)
    assert installer.install_pak(str(pak), poll_timeout=60) == 4
    assert "INSTALL STILL RUNNING" in capsys.readouterr().err


# --- review W1: each status poll carries a bounded request timeout ----------

def test_poll_passes_the_time_left(monkeypatch, tmp_path):
    pak, _, _, polls = _wire(monkeypatch, tmp_path, None)
    installer.install_pak(str(pak), poll_timeout=20)
    t = polls["timeouts"]
    assert t[0] == pytest.approx(20)
    assert all(b < a for a, b in zip(t, t[1:]))  # shrinks as the wait runs
    assert all(x > 0 for x in t)


class _Resp:
    ok = True
    status_code = 200
    text = "{}"

    def json(self):
        return {"isPakInstalling": True}


class _Http:
    def __init__(self):
        self.kw = None

    def post(self, url, **kw):
        self.kw = kw
        return _Resp()


def _session():
    s = installer._UISession.__new__(installer._UISession)
    s._session = _Http()
    s._host = "ops.example"
    s._csrf = "tok"
    return s


def test_is_pak_installing_sends_a_timeout():
    connect, read = installer.SOLUTION_ACTION_TIMEOUT
    s = _session()
    s.is_pak_installing()
    assert s._session.kw["timeout"] == (connect, read)
    s.is_pak_installing(timeout=7.5)
    assert s._session.kw["timeout"] == (connect, 7.5)
    s.is_pak_installing(timeout=10_000)
    assert s._session.kw["timeout"] == (connect, read)  # capped at the default read


def test_stalled_poll_falls_into_retry(monkeypatch, tmp_path, capsys):
    """A request timeout is a failed poll: retried, then exit 1 if it is last."""
    import requests

    def script(n):
        if n == 1:
            return {"isPakInstalling": True}
        raise requests.exceptions.ReadTimeout("read timed out")

    pak, _, _, polls = _wire(monkeypatch, tmp_path, None, script=script)
    with pytest.raises(SystemExit) as exc:
        installer.install_pak(str(pak), poll_timeout=30)
    assert exc.value.code == 1
    assert polls["n"] > 2  # retried after the timeout
    err = capsys.readouterr().err
    assert "Status poll failed (will retry): read timed out" in err


# --- review N1 ---------------------------------------------------------------

def test_cli_rejects_install_timeout_with_no_wait(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(installer, "install_pak", lambda **kw: called.append(kw) or 0)
    monkeypatch.delenv("VCFCF_SUMMARY_REBIND", raising=False)
    assert cli.main(["install", "x.pak", "--no-wait", "--install-timeout", "5"]) == 2
    assert not called
    assert "--no-wait" in capsys.readouterr().err
    assert cli.main(["install", "x.pak", "--no-wait"]) == 0
