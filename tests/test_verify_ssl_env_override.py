"""Issue #174: an explicit VERIFY_SSL=false must beat REQUESTS_CA_BUNDLE.

Plain ``requests`` lets ``REQUESTS_CA_BUNDLE`` / ``CURL_CA_BUNDLE`` replace
``Session.verify = False`` whenever a request does not pass ``verify=``
itself. Every Suite API / UI session in ``src/vcfcf_*`` now comes from
``vcfcf_common.client.new_session`` (or the standalone installer template's
mirror of it), which keeps ``False`` while leaving ``True`` free to pick up
the env bundle.

The end-to-end tests mount a recording transport adapter on the real
session, so they observe the ``verify`` value ``requests`` actually hands to
the transport, with no network.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import requests
from requests.adapters import HTTPAdapter

from vcfcf_common.client import VCFOpsClient, VerifyRespectingSession, new_session

REPO = Path(__file__).resolve().parents[1]
BUNDLE = "/nonexistent/ca-bundle-for-test.crt"


class _Recorder(HTTPAdapter):
    """Transport adapter that records ``verify`` and returns a canned 200."""

    def __init__(self):
        super().__init__()
        self.seen = []

    def send(self, request, **kwargs):  # noqa: D401 (requests signature)
        self.seen.append(kwargs.get("verify"))
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b"{}"
        resp.url = request.url
        resp.request = request
        return resp


def _verify_sent(session: requests.Session, **req_kwargs):
    rec = _Recorder()
    session.mount("https://", rec)
    session.get("https://ops.example.invalid/suite-api/api/versions/current", **req_kwargs)
    return rec.seen[-1]


@pytest.fixture
def ca_bundle_env(monkeypatch):
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", BUNDLE)
    monkeypatch.delenv("CURL_CA_BUNDLE", raising=False)


def test_plain_requests_session_has_the_bug(ca_bundle_env):
    """Documents the upstream behaviour this fix works around. If requests ever
    changes it, this test tells us the wrapper is no longer needed."""
    s = requests.Session()
    s.verify = False
    assert _verify_sent(s) == BUNDLE


def test_verify_false_wins_over_requests_ca_bundle(ca_bundle_env):
    assert _verify_sent(new_session(False)) is False


def test_verify_false_wins_over_curl_ca_bundle(monkeypatch):
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.setenv("CURL_CA_BUNDLE", BUNDLE)
    assert _verify_sent(new_session(False)) is False


def test_verify_true_still_honours_requests_ca_bundle(ca_bundle_env):
    assert _verify_sent(new_session(True)) == BUNDLE


def test_verify_true_without_env_is_true(monkeypatch):
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("CURL_CA_BUNDLE", raising=False)
    assert _verify_sent(new_session(True)) is True


def test_per_request_verify_still_wins(ca_bundle_env):
    assert _verify_sent(new_session(False), verify="/explicit/ca.pem") == "/explicit/ca.pem"
    assert _verify_sent(new_session(True), verify=False) is False


def test_proxies_from_env_still_honoured(ca_bundle_env, monkeypatch):
    """The fix must not switch off trust_env (corporate proxies live there)."""
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.invalid:3128")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    s = new_session(False)
    settings = s.merge_environment_settings(
        "https://ops.example.invalid/", {}, None, None, None)
    assert settings["verify"] is False
    assert settings["proxies"].get("https") == "http://proxy.example.invalid:3128"


def test_vcfops_client_session_respects_verify_false(ca_bundle_env):
    c = VCFOpsClient("ops.example.invalid", "u", "p", verify_ssl=False)
    assert isinstance(c._session, VerifyRespectingSession)
    assert _verify_sent(c._session) is False


def test_no_bare_requests_session_in_src():
    """Regression guard: every session in src/vcfcf_* goes through the
    verify-respecting helper. The only allowed ``requests.Session`` references
    are the helper definitions themselves and type annotations."""
    offenders = []
    for py in (REPO / "src").rglob("*.py"):
        if "adapter_runtime" in py.parts:
            continue
        for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"requests\.Session\(\)", line):
                offenders.append(f"{py.relative_to(REPO)}:{n}: {line.strip()}")
    assert offenders == [], "bare requests.Session() found:\n" + "\n".join(offenders)


@pytest.fixture(scope="module")
def install_mod():
    path = REPO / "src" / "vcfcf_packaging" / "templates" / "install.py"
    spec = importlib.util.spec_from_file_location("_install_template_verify", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_install_template_verify"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_install_template_suite_client_respects_verify_false(install_mod, ca_bundle_env):
    c = install_mod.Client("ops.example.invalid", "u", "p", verify_ssl=False)
    assert _verify_sent(c._session) is False


def test_install_template_verify_true_honours_env(install_mod, ca_bundle_env):
    assert _verify_sent(install_mod._new_session(True)) == BUNDLE
