"""The sync handler reads the session user's name from the right key.

``GET /api/auth/currentuser`` returns the account name under
``username`` (lower-case n) on every supported version: the ``user``
schema in ``reference/docs/operations-api-8.18.json``,
``operations-api.json`` (9.0) and ``operations-api-9.1.json`` all name
it so, and a 9.0.2 response was observed with it
(``knowledge/context/investigations/2026-11-11-owner-mapping-dashboard-skip-reproduction.md``).
The handler used to read ``userName`` and so always wrote ``admin``.

No network: every call is stubbed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vcfcf_dashboards import handler as dash_handler
from vcfcf_dashboards.client import current_user_name

_REPO = Path(__file__).resolve().parents[1]

# Shape of a currentuser body per the `user` schema (all three specs
# agree). Values are placeholders; no live response is quoted.
CURRENTUSER_BODY = {
    "id": "29c1613f-3bbe-4aa0-8236-2c74db22c661",
    "username": "svc.content",
    "firstName": "Service",
    "lastName": "Content",
    "emailAddress": "svc.content@example.invalid",
    "distinguishedName": "",
    "enabled": True,
    "roleNames": ["Administrator"],
    "role-permissions": [],
    "groupIds": [],
    "links": [],
}


@pytest.mark.parametrize(
    "spec",
    ["operations-api-8.18.json", "operations-api.json", "operations-api-9.1.json"],
)
def test_every_spec_names_the_key_username(spec):
    """Pin the fact the helper relies on to the vendor specs."""
    path = _REPO / "reference" / "docs" / spec
    if not path.exists():
        pytest.skip(f"{spec} not present")
    d = json.loads(path.read_text())
    schemas = d.get("definitions") or d["components"]["schemas"]
    props = schemas["user"]["properties"]
    assert "username" in props
    assert "userName" not in props


class TestCurrentUserName:
    def test_reads_username(self):
        assert current_user_name(CURRENTUSER_BODY) == "svc.content"

    def test_username_wins_over_userName(self):
        assert current_user_name({"username": "a", "userName": "b"}) == "a"

    def test_userName_is_a_fallback(self):
        assert current_user_name({"id": "x", "userName": "b"}) == "b"

    @pytest.mark.parametrize(
        "body", [{"id": "x"}, {"username": ""}, {"username": None}, {}, None]
    )
    def test_admin_is_the_last_resort(self, body):
        assert current_user_name(body) == "admin"


class _Stub:
    def __init__(self, name):
        self.name = name
        self.widgets: list = []


def _stub(monkeypatch, captured):
    stub = _Stub("[VCF CF] Stub")
    monkeypatch.setattr(dash_handler, "load_dashboard", lambda p: stub)
    monkeypatch.setattr(dash_handler, "load_view", lambda p: stub)
    monkeypatch.setattr(dash_handler, "get_current_user", lambda s: CURRENTUSER_BODY)
    monkeypatch.setattr(dash_handler, "discover_marker_filename", lambda s: "1L.v1")

    def _build(*a, **k):
        captured.append(k)
        return b"zip"

    monkeypatch.setattr(dash_handler, "build_import_zip", _build)
    monkeypatch.setattr(
        dash_handler,
        "import_content_zip",
        lambda s, b: {"state": "FINISHED", "operationSummaries": []},
    )


def test_dashboards_handler_writes_the_session_user_name(monkeypatch, tmp_path):
    captured: list = []
    _stub(monkeypatch, captured)
    dash_handler.DashboardsHandler().sync(
        [str(tmp_path / "dashboards" / "d.yaml")], session=object()
    )
    assert captured and captured[0]["owner_username"] == "svc.content"
    assert captured[0]["owner_user_id"] == CURRENTUSER_BODY["id"]


def test_standalone_sync_writes_the_session_user_name(monkeypatch, tmp_path):
    """``python3 -m vcfcf_dashboards sync`` (cmd_sync) used to omit
    owner_username entirely, so it always wrote ``admin``."""
    import types
    from vcfcf_dashboards import cli as dash_cli

    captured: list = []
    stub = _Stub("[VCF CF] Stub")
    monkeypatch.setattr(dash_cli, "_load", lambda args: ([], [stub]))
    monkeypatch.setattr(
        dash_cli.VCFOpsClient, "from_env", classmethod(lambda cls, **kw: object())
    )
    monkeypatch.setattr(dash_cli, "get_current_user", lambda c: CURRENTUSER_BODY)
    monkeypatch.setattr(dash_cli, "discover_marker_filename", lambda c: "1L.v1")

    def _build(*a, **k):
        captured.append(k)
        return b"zip"

    monkeypatch.setattr(dash_cli, "build_import_zip", _build)
    monkeypatch.setattr(
        dash_cli, "import_content_zip",
        lambda c, b: {"state": "FINISHED", "operationSummaries": []},
    )
    monkeypatch.setattr(dash_cli, "_run_dep_walker", lambda *a, **k: 0)
    monkeypatch.setattr(dash_cli, "_report_materialization", lambda *a, **k: 0)
    args = types.SimpleNamespace(
        views_dir=str(tmp_path / "views"),
        dashboards_dir=str(tmp_path / "dashboards"),
        profile=None,
        supermetrics_dir=str(tmp_path / "supermetrics"),
        auto_enable_metrics=False,
        skip_metric_check=True,
    )
    dash_cli.cmd_sync(args)
    assert captured and captured[0]["owner_username"] == "svc.content"
    assert captured[0]["owner_user_id"] == CURRENTUSER_BODY["id"]


def test_views_handler_writes_the_session_user_name(monkeypatch, tmp_path):
    captured: list = []
    _stub(monkeypatch, captured)
    dash_handler.ViewsHandler().sync(
        [str(tmp_path / "views" / "v.yaml")], session=object()
    )
    assert captured and captured[0]["owner_username"] == "svc.content"
