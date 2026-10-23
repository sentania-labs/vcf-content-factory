"""Unsigned-pak preflight and error translation (issue #216).

Fresh 9.0 and 9.1 clusters refuse unsigned paks until an admin activates
"Allow Unsigned PAK Installation". The installer reads the switch from
getIntegrations before uploading and stops with the admin-UI steps; 8.18
has no such key and no gate, so a missing key must never abort.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_managementpacks import installer  # noqa: E402


def _pak(tmp_path: Path, signed: bool = False) -> Path:
    p = tmp_path / ("signed.pak" if signed else "unsigned.pak")
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("manifest.txt", '{"name": "X", "version": "0.0.0.1"}')
        if signed:
            zf.writestr("signature.mf", "SHA1(manifest.txt)= 00")
            zf.writestr("signature.cert", "cert")
    return p


class _UI:
    def __init__(self, body=None, exc=None):
        self._body = body
        self._exc = exc
        self.calls = 0

    def solution_action(self, _timeout=None, **kwargs):
        self.calls += 1
        assert kwargs == {"mainAction": "getIntegrations"}
        if self._exc:
            raise self._exc
        return self._body

    get_unsigned_pak_policy = installer._UISession.get_unsigned_pak_policy


@pytest.mark.parametrize("value", [False, "false"])
def test_switch_off_aborts_before_upload_with_steps(tmp_path, capsys, value):
    ui = _UI({"installedMPs": [], "isUnsignedPakInstallationAllowed": value})
    with pytest.raises(SystemExit) as exc:
        installer._preflight_unsigned_policy(ui, _pak(tmp_path))
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Activate Unsigned PAK Installation" in err
    assert "/admin" in err
    assert "Security Settings" in err
    assert "cluster-wide" in err


@pytest.mark.parametrize("value", [True, "true"])
def test_switch_on_proceeds(tmp_path, capsys, value):
    ui = _UI({"isUnsignedPakInstallationAllowed": value})
    installer._preflight_unsigned_policy(ui, _pak(tmp_path))
    assert "allows unsigned" in capsys.readouterr().out


def test_missing_key_is_no_gate_not_refusal(tmp_path, capsys):
    """8.18.7 shape: no isUnsignedPakInstallationAllowed key at all."""
    ui = _UI({"availableMPs": [], "installedMPs": [], "installationState": {}})
    installer._preflight_unsigned_policy(ui, _pak(tmp_path))
    assert "no cluster-wide" in capsys.readouterr().out


def test_unrecognised_value_is_no_gate(tmp_path):
    ui = _UI({"isUnsignedPakInstallationAllowed": None})
    installer._preflight_unsigned_policy(ui, _pak(tmp_path))


def test_read_failure_warns_and_proceeds(tmp_path, capsys):
    ui = _UI(exc=RuntimeError("boom"))
    installer._preflight_unsigned_policy(ui, _pak(tmp_path))
    assert "Could not read" in capsys.readouterr().err


def test_signed_pak_skips_the_read(tmp_path):
    ui = _UI({"isUnsignedPakInstallationAllowed": False})
    installer._preflight_unsigned_policy(ui, _pak(tmp_path, signed=True))
    assert ui.calls == 0


def test_pak_is_signed_detection(tmp_path):
    assert installer._pak_is_signed(_pak(tmp_path, signed=True)) is True
    assert installer._pak_is_signed(_pak(tmp_path)) is False
    bad = tmp_path / "bad.pak"
    bad.write_bytes(b"not a zip")
    assert installer._pak_is_signed(bad) is False


def test_raw_upload_error_is_translated(tmp_path):
    """If the gate is still hit (switch flipped between read and upload),
    the raw key comes back with the same explanation."""

    class _R:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {"success": True,
                    "errorMsg": "unsigned_pak_installation.not.allowed"}

    class _S:
        def post(self, *a, **k):
            return _R()

    ui = installer._UISession(host="h", user="u", password="p")
    ui._session = _S()
    ui._csrf = "c"
    with pytest.raises(RuntimeError) as exc:
        ui.upload_pak(_pak(tmp_path))
    msg = str(exc.value)
    assert "unsigned_pak_installation.not.allowed" in msg
    assert "Activate Unsigned PAK Installation" in msg


def test_other_upload_errors_are_not_translated(tmp_path):
    class _R:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {"success": True, "errorMsg": "something else"}

    class _S:
        def post(self, *a, **k):
            return _R()

    ui = installer._UISession(host="h", user="u", password="p")
    ui._session = _S()
    with pytest.raises(RuntimeError) as exc:
        ui.upload_pak(_pak(tmp_path))
    assert "Activate Unsigned" not in str(exc.value)


# --- One case per platform shape, through the real _UISession read ----------
# 9.0/9.1 switch on, 9.0/9.1 switch off, 8.18.7 (key absent), and a 404 on
# the route (8.18.7 404s the CaSA allow_unsigned_pak routes). Only a present
# key reading false stops the upload.

class _HTTPResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = "" if body is None else json.dumps(body)

    def raise_for_status(self):
        import requests

        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}", response=self)

    def json(self):
        return self._body


def _real_ui(status, body):
    class _S:
        def post(self, url, data=None, timeout=None):
            assert url.endswith("/ui/solution.action")
            assert data["mainAction"] == "getIntegrations"
            return _HTTPResp(status, body)

    ui = installer._UISession(host="h", user="u", password="p")
    ui._session = _S()
    ui._csrf = "c"
    return ui


@pytest.mark.parametrize("shape,status,body,expect", [
    ("9.x switch on", 200, {"installedMPs": [], "isUnsignedPakInstallationAllowed": True}, True),
    ("9.x switch off", 200, {"installedMPs": [], "isUnsignedPakInstallationAllowed": False}, False),
    ("8.18 key absent", 200, {"availableMPs": [], "installedMPs": [], "installationState": {}}, None),
    ("route 404", 404, None, None),
])
def test_policy_read_per_platform_shape(shape, status, body, expect):
    assert _real_ui(status, body).get_unsigned_pak_policy() is expect, shape


@pytest.mark.parametrize("shape,status,body,stops", [
    ("9.x switch on", 200, {"isUnsignedPakInstallationAllowed": True}, False),
    ("9.x switch off", 200, {"isUnsignedPakInstallationAllowed": False}, True),
    ("8.18 key absent", 200, {"installedMPs": []}, False),
    ("route 404", 404, None, False),
])
def test_preflight_per_platform_shape(tmp_path, capsys, shape, status, body, stops):
    ui = _real_ui(status, body)
    if stops:
        with pytest.raises(SystemExit):
            installer._preflight_unsigned_policy(ui, _pak(tmp_path))
        assert "Activate Unsigned PAK Installation" in capsys.readouterr().err
    else:
        installer._preflight_unsigned_policy(ui, _pak(tmp_path))
        out = capsys.readouterr()
        assert "Activate Unsigned" not in out.err
        # A 404 is "no gate", not a failed read.
        assert "Could not read" not in out.err


def test_other_http_errors_warn_and_proceed(tmp_path, capsys):
    installer._preflight_unsigned_policy(_real_ui(500, {}), _pak(tmp_path))
    assert "Could not read" in capsys.readouterr().err


def test_install_pak_stops_before_upload_when_switch_off(tmp_path, monkeypatch):
    """The preflight runs after login and before prepareFileUpload/upload."""
    events = []

    class _FakeSession:
        def __init__(self, **kw):
            pass

        def login(self):
            events.append("login")

        def logout(self):
            events.append("logout")

        def get_unsigned_pak_policy(self):
            events.append("policy")
            return False

        def prepare_upload(self):
            events.append("prepare")

        def upload_pak(self, *a, **k):
            events.append("upload")

    monkeypatch.setattr(installer, "_UISession", _FakeSession)
    monkeypatch.setattr(installer, "_resolve_credentials",
                        lambda *a, **k: ("h", "u", "p", True))
    monkeypatch.setattr(installer, "_parse_manifest_txt",
                        lambda p: {"name": "X", "version": "0.0.0.1"})
    with pytest.raises(SystemExit):
        installer.install_pak(str(_pak(tmp_path)))
    assert events == ["login", "policy", "logout"]
