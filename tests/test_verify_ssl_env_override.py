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

import ast
import importlib.util
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


_MODULE_VERBS = {"get", "post", "put", "delete", "patch", "head", "options", "request"}
_SESSION_NAMES = {"Session", "session"}


def _dotted(node):
    """Return ["a", "b", "c"] for a Name/Attribute chain a.b.c, else None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return parts[::-1]
    return None


def _has_real_verify(call):
    """True when the call passes verify= with something other than None."""
    for k in call.keywords:
        if k.arg == "verify":
            return not (isinstance(k.value, ast.Constant) and k.value.value is None)
    return False


def _requests_misuse(tree):
    """Yield (lineno, text) for every requests usage that bypasses the helper.

    Resolves import aliases (``import requests as r``, ``import
    requests.sessions as rs``), flags any from-import of a session class or a
    module-level verb from ``requests`` or its submodules, flags constructing
    a session through any path (``requests.Session()``,
    ``requests.sessions.Session()``), and flags module-level verb calls whose
    ``verify=`` is missing or ``None``.
    """
    # local name -> dotted module path it stands for
    aliases = {"requests": ["requests"]}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "requests" or a.name.startswith("requests."):
                    if a.asname:
                        aliases[a.asname] = a.name.split(".")
                    else:
                        aliases[a.name.split(".")[0]] = ["requests"]
        elif isinstance(node, ast.ImportFrom) and node.module and (
                node.module == "requests" or node.module.startswith("requests.")):
            for a in node.names:
                if a.name in _SESSION_NAMES or a.name in _MODULE_VERBS:
                    yield node.lineno, f"from {node.module} import {a.name}"
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _dotted(node.func)
        if not chain or chain[0] not in aliases:
            continue
        full = aliases[chain[0]] + chain[1:]
        if full[0] != "requests" or len(full) < 2:
            continue
        rest = full[1:]
        if rest[-1] in _SESSION_NAMES and rest[:-1] in ([], ["sessions"]):
            yield node.lineno, ".".join(full) + "()"
        elif rest[-1] in _MODULE_VERBS and rest[:-1] in ([], ["api"]):
            if not _has_real_verify(node):
                yield node.lineno, ".".join(full) + "(...) without a non-None verify="


def test_no_bare_requests_session_in_src():
    """Regression guard: every session in src/vcfcf_* goes through the
    verify-respecting helper, and every module-level requests call passes
    verify= explicitly (a per-request verify=False is not overridden by the
    env bundle). Subclassing requests.Session (the helpers themselves) is
    fine; constructing one is not."""
    offenders = []
    for py in (REPO / "src").rglob("*.py"):
        if "adapter_runtime" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for lineno, what in _requests_misuse(tree):
            offenders.append(f"{py.relative_to(REPO)}:{lineno}: {what}")
    assert offenders == [], "requests usage bypassing new_session:\n" + "\n".join(offenders)


@pytest.mark.parametrize("src, expect", [
    ("import requests\ns = requests.Session()\n", 1),
    ("import requests\ns = requests.session()\n", 1),
    ("import requests\ns = requests.sessions.Session()\n", 1),
    ("import requests as r\ns = r.Session()\n", 1),
    ("import requests.sessions as rs\ns = rs.Session()\n", 1),
    ("import requests as r\nr.get('https://x')\n", 1),
    ("from requests import Session\n", 1),
    ("from requests.sessions import session\n", 1),
    ("from requests import get\n", 1),
    ("from requests import post as p\n", 1),
    ("from requests.api import request\n", 1),
    ("import requests\nrequests.get('https://x')\n", 1),
    ("import requests\nrequests.get('https://x', verify=None)\n", 1),
    ("import requests\nrequests.api.put('https://x')\n", 1),
    ("import requests\nrequests.post(\n  'https://x',\n  json={},\n)\n", 1),
    ("import requests\nrequests.post('https://x', verify=False)\n", 0),
    ("import requests\nrequests.post('https://x', verify=flag)\n", 0),
    ("import requests\nclass S(requests.Session):\n    pass\n", 0),
    ("from requests.adapters import HTTPAdapter\n", 0),
    ("import requests\nraise requests.exceptions.ConnectionError()\n", 0),
])
def test_guard_detects_each_bypass_shape(src, expect):
    assert len(list(_requests_misuse(ast.parse(src)))) == expect


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
