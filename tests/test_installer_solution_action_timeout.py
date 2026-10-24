"""A hung getIntegrations re-read cannot hold the install verify (issue #235).

solution_action used to POST with no timeout, so one socket that accepted the
connection and never answered held the post-install settle loop forever.
These tests point a real _UISession at a local listener that accepts and
then says nothing.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_managementpacks import installer  # noqa: E402

AK = "vcfcf_compliance"
MANIFEST = {"name": "Compliance", "version": "0.0.0.90", "adapter_kinds": AK}


@pytest.fixture
def hung_host():
    """host:port of a listener that accepts connections and never replies."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    held = []
    stop = threading.Event()

    def _accept():
        srv.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except (socket.timeout, OSError):
                continue
            held.append(conn)

    t = threading.Thread(target=_accept, daemon=True)
    t.start()
    yield f"127.0.0.1:{srv.getsockname()[1]}"
    stop.set()
    t.join(timeout=2)
    for c in held:
        c.close()
    srv.close()


def _session(host: str) -> installer._UISession:
    ui = installer._UISession(host=host, user="u", password="p", verify_ssl=False)
    ui._session = requests.Session()
    ui._session.verify = False
    ui._csrf = "csrf"
    return ui


def test_solution_action_always_sends_a_timeout():
    seen = {}

    class _S:
        def post(self, url, data=None, timeout=None):
            seen["timeout"] = timeout

            class _R:
                text = "{}"

                def raise_for_status(self):
                    pass

                def json(self):
                    return {}

            return _R()

    ui = installer._UISession(host="h", user="u", password="p")
    ui._session = _S()
    ui.solution_action(mainAction="getIntegrations")
    assert seen["timeout"] == installer.SOLUTION_ACTION_TIMEOUT
    ui.get_integrations(timeout=4.0)
    assert seen["timeout"] == (min(installer.SOLUTION_ACTION_TIMEOUT[0], 4.0), 4.0)


def test_hung_socket_raises_runtime_error_within_timeout(hung_host):
    ui = _session(hung_host)
    start = time.monotonic()
    with pytest.raises(RuntimeError, match="timed out"):
        ui.get_integrations(timeout=0.5)
    assert time.monotonic() - start < 3


def test_hung_reread_does_not_exceed_settle_window(hung_host, capsys):
    """First read shows the prior build; every re-read hangs. The verify must
    give up at the end of the settle window and fail loud, not wait forever."""
    real = _session(hung_host)

    class _UI:
        calls = 0

        def get_integrations(self, timeout=None):
            _UI.calls += 1
            if _UI.calls == 1:
                return [{"pakId": "Compliance", "name": "Compliance",
                         "version": "0.0.0.89", "isInstalled": True,
                         "adapterKind": AK}]
            return real.get_integrations(timeout=timeout)

    settle = 2
    start = time.monotonic()
    with pytest.raises(SystemExit):
        installer._verify_adapter_registered(
            _UI(), MANIFEST, "Compliance", "0.0.0.90",
            settle_timeout=settle, settle_interval=0.1,
        )
    elapsed = time.monotonic() - start
    assert elapsed < settle + 1.5, elapsed
    err = capsys.readouterr().err
    assert "timed out" in err
    assert "0.0.0.89" in err
