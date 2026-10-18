"""Post-install verification checks the installed version, not just presence.

Issue #202: installing compliance build 90 over 89, the pak manager's
apply_adapter failed and the controller kept 0.0.0.89, but the installer
printed "OK: Install completed and verified ... 0.0.0.90" because the adapter
kind was still registered (isInstalled=true) from build 89.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_managementpacks import installer  # noqa: E402

AK = "vcfcf_compliance"
MANIFEST = {"name": "Compliance", "version": "0.0.0.90", "adapter_kinds": AK}


class _FakeUI:
    """Returns a scripted sequence of getIntegrations replies (last one repeats)."""

    def __init__(self, *replies):
        self._replies = list(replies)
        self.calls = 0

    def get_integrations(self):
        self.calls += 1
        reply = self._replies[min(self.calls - 1, len(self._replies) - 1)]
        if isinstance(reply, Exception):
            raise reply
        return reply


def _entry(version, installed=True, ak=AK, name="Compliance"):
    return {"pakId": name, "name": name, "version": version,
            "isInstalled": installed, "adapterKind": ak}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(installer.time, "sleep", lambda _s: None)


def _verify(ui, manifest=MANIFEST, server_version="0.0.0.90", timeout=0):
    installer._verify_adapter_registered(
        ui, manifest, "Compliance", server_version,
        settle_timeout=timeout, settle_interval=0,
    )


def test_prior_build_still_installed_fails_loud(capsys):
    """The build 90 over 89 case: adapter kind present, old version."""
    ui = _FakeUI([_entry("0.0.0.89")])
    with pytest.raises(SystemExit) as exc:
        _verify(ui)
    assert exc.value.code == 1
    out = capsys.readouterr()
    assert "0.0.0.89" in out.err and "0.0.0.90" in out.err
    assert "OK:" not in out.out


def test_matching_version_passes(capsys):
    _verify(_FakeUI([_entry("0.0.0.90")]))
    out = capsys.readouterr().out
    assert "OK: Install completed and verified" in out
    assert "0.0.0.90" in out


def test_trailing_zero_components_compare_equal():
    _verify(_FakeUI([_entry("1.0.0.0")]), manifest={**MANIFEST, "version": "1.0.0"})


def test_version_lag_settles_within_window(monkeypatch, capsys):
    """A version that catches up on a re-read passes; it is not a failure."""
    clock = iter(range(0, 1000))
    monkeypatch.setattr(installer.time, "time", lambda: next(clock))
    ui = _FakeUI([_entry("0.0.0.89")], [_entry("0.0.0.90")])
    _verify(ui, timeout=30)
    assert ui.calls == 2
    assert "OK: Install completed and verified" in capsys.readouterr().out


def test_version_never_settles_fails_after_window(monkeypatch):
    clock = iter(range(0, 1000))
    monkeypatch.setattr(installer.time, "time", lambda: next(clock))
    ui = _FakeUI([_entry("0.0.0.89")])
    with pytest.raises(SystemExit):
        _verify(ui, timeout=5)
    assert ui.calls > 1


def test_manifest_version_wins_over_upload_reply():
    """Expected version is the pak just uploaded (manifest), not a stale reply."""
    with pytest.raises(SystemExit):
        _verify(_FakeUI([_entry("0.0.0.89")]), server_version="0.0.0.89")


def test_upload_reply_version_used_when_manifest_lacks_one():
    manifest = {"name": "Compliance", "adapter_kinds": AK}
    _verify(_FakeUI([_entry("0.0.0.90")]), manifest=manifest, server_version="0.0.0.90")
    with pytest.raises(SystemExit):
        _verify(_FakeUI([_entry("0.0.0.89")]), manifest=manifest, server_version="0.0.0.90")


def test_no_version_anywhere_warns_not_verified(capsys):
    manifest = {"name": "Compliance", "adapter_kinds": AK}
    _verify(_FakeUI([_entry("0.0.0.89")]), manifest=manifest, server_version="(unknown)")
    out = capsys.readouterr()
    assert "version unverified" in out.out
    assert "OK: Install completed and verified" not in out.out
    assert "WARN" in out.err


def test_missing_adapter_kind_still_fails():
    with pytest.raises(SystemExit):
        _verify(_FakeUI([_entry("0.0.0.90", ak="something_else")]))


def test_is_installed_false_still_fails():
    with pytest.raises(SystemExit):
        _verify(_FakeUI([_entry("0.0.0.90", installed=False)]))


def test_name_only_path_checks_version():
    manifest = {"name": "Compliance", "version": "0.0.0.90"}
    _verify(_FakeUI([_entry("0.0.0.90")]), manifest=manifest)
    with pytest.raises(SystemExit):
        _verify(_FakeUI([_entry("0.0.0.89")]), manifest=manifest)


def test_get_integrations_failure_stays_unverified_warning(capsys):
    _verify(_FakeUI(RuntimeError("boom")))
    out = capsys.readouterr()
    assert "unverified" in out.out
    assert "WARN" in out.err
