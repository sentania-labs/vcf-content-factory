"""Import counters short of total, and the Section widget floor (issue #199).

Measured 2026-11-13 on 8.18.7 and 9.0.2
(knowledge/context/investigations/2026-11-13-section-widget-on-8x-and-90.md):
a dashboard with a widget type the build does not know (Section) aborts the
dashboards import. Through /api/content/operations/import the whole
dashboards batch is lost and the task still reports FINISHED with DASHBOARDS
total N, imported 0, skipped 0, failed 0 and no message. The all-skipped
check needs skipped > 0, so it never fired.

Two rules, each tested through the real entry points with synthetic
fixtures and no network:

1. On a FINISHED result, ``imported + skipped + failed < total`` is an error
   for DASHBOARDS (the measured type) and a warning that changes nothing for
   every other type, whose ``total`` is unverified; a counter that is not a
   whole number is a warning (one definition:
   vcfcf_dashboards.client.import_count_findings, pinned copies in both
   installer templates).
2. A content import carrying Section is refused before anything is sent on
   a build measured not to import it (below 9.1.0), and warned on and sent on
   the unmeasured 9.1.0 (vcfcf_core.dashboards.widget_versions.import_check;
   same pinned-copy rule). Content bundles declare no target version, so
   validate stays a warning, now saying the batch is lost.
"""
from __future__ import annotations

import json
import sys
import types
import warnings
from pathlib import Path

import pytest
import yaml

from vcfcf_core.dashboards import widget_versions as wv
from vcfcf_core.dashboards.loader import load_all as core_load_all
from vcfcf_dashboards import cli as dash_cli
from vcfcf_dashboards import client as dash_client
from vcfcf_dashboards import handler as dash_handler
from vcfcf_dashboards.client import (
    SHORTFALL_SEVERITY,
    VERSION_UNREADABLE_NOTE,
    import_count_findings,
    import_shortfall_message,
    import_shortfalls,
    import_uninterpretable_message,
)

from ps_runner import ps_exe, run_ps_file  # noqa: F401  (ps_exe is a fixture)

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / "src" / "vcfcf_packaging" / "templates"
PS_HARNESS = Path(__file__).resolve().parent / "fixtures" / "install_ps1_shortfall_harness.ps1"
needs_pwsh = pytest.mark.usefixtures("ps_exe")


# --- fixtures ----------------------------------------------------------------

def _summary(ct, total, imported=0, skipped=0, failed=0):
    return {"contentType": ct, "errorMessages": [], "failed": failed,
            "imported": imported, "infoMessages": [], "skipped": skipped,
            "state": "FINISHED", "total": total, "type": "import"}


def _envelope(*summaries, state="FINISHED"):
    """The measured shape: FINISHED, errorCode NONE, no messages."""
    return {"state": state, "errorCode": "NONE", "errorMessages": [],
            "operationSummaries": list(summaries), "type": "IMPORT"}


#: 8.18.7 / 9.0.2 r1: D1 (Section) + D2 (plain), both lost.
LOST_BATCH = _envelope(_summary("DASHBOARDS", 2))
CLEAN = _envelope(_summary("DASHBOARDS", 1, imported=1))

_TEXT = {"id": "t", "type": "TextDisplay", "title": "T",
         "coords": {"x": 1, "y": 2, "w": 4, "h": 2},
         "text_display_config": {"text": "hi"}}
_SECTION = {"id": "sec", "type": "Section", "title": "Header",
            "coords": {"x": 1, "y": 1, "w": 12, "h": 1}}
_D1_ID = "0f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a4b"
_D2_ID = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"


def _dashboards_dir(root: Path) -> Path:
    d = root / "content" / "dashboards"
    d.mkdir(parents=True)
    (d / "d1.yaml").write_text(yaml.safe_dump({
        "id": _D1_ID, "name": "[VCF CF] Probe Section D1", "description": "",
        "widgets": [_SECTION, _TEXT]}, sort_keys=False))
    (d / "d2.yaml").write_text(yaml.safe_dump({
        "id": _D2_ID, "name": "[VCF CF] Probe Plain D2", "description": "",
        "widgets": [_TEXT]}, sort_keys=False))
    (root / "content" / "views").mkdir(parents=True)
    return d


def _load(root: Path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return core_load_all(root / "content" / "views", _dashboards_dir(root))[1]


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class _VersionSession:
    """A Suite API session that only answers GET /api/versions/current."""

    def __init__(self, release_name="VCF Operations 9.0.2.0", status=200):
        self.release_name = release_name
        self.status = status
        self.calls = []

    def _request(self, method, path, **kw):
        self.calls.append((method, path))
        assert path == "/api/versions/current", path
        return _Resp(self.status, {"releaseName": self.release_name,
                                   "major": 2, "minor": 2, "buildNumber": 25431135})


# --- 1. the count check ---------------------------------------------------------

class TestImportCountFindings:
    def test_the_measured_envelope_is_a_dashboards_error(self):
        assert import_shortfalls(LOST_BATCH) == {"DASHBOARDS": (2, 0, 0, 0)}
        assert import_count_findings(LOST_BATCH) == [
            ("error", "DASHBOARDS", import_shortfall_message("DASHBOARDS", (2, 0, 0, 0)))]

    def test_only_dashboards_is_an_error(self):
        assert SHORTFALL_SEVERITY == {"DASHBOARDS": "error"}
        env = _envelope(_summary("SUPER_METRICS", 3, imported=2),
                        _summary("REPORTS", 1), _summary("VIEW_DEFINITIONS", 2))
        assert [(s, c) for s, c, _m in import_count_findings(env)] == [
            ("warning", "REPORTS"), ("warning", "SUPER_METRICS"), ("warning", "VIEW_DEFINITIONS")]
        msg = import_count_findings(env, ("REPORTS",))[0][2]
        assert "What total counts for REPORTS has not been verified" in msg
        assert "warning, not a failure" in msg and "Section" not in msg

    def test_counts_that_add_up_are_not_flagged(self):
        assert import_count_findings(CLEAN) == []
        assert import_count_findings(_envelope(_summary("DASHBOARDS", 3, 1, 1, 1))) == []
        # The owner-mapping skip adds up (skipped=1 of 1): the all-skipped
        # advisory owns it, not this check.
        assert import_count_findings(_envelope(_summary("DASHBOARDS", 1, skipped=1))) == []

    @pytest.mark.parametrize("state", ["FAILED", "RUNNING", "", None])
    def test_only_a_finished_task_is_checked(self, state):
        """W3: a FAILED task reports its own failure, never the widget-type text."""
        env = _envelope(_summary("DASHBOARDS", 2), state=state)
        assert import_count_findings(env) == [] and import_shortfalls(env) == {}

    @pytest.mark.parametrize("bad", [1.5, "2.0", True, -1, " 2", "2 ", "２", [2], {"n": 2}])
    def test_a_counter_that_is_not_a_whole_number_is_a_warning(self, bad):
        env = _envelope({"contentType": "DASHBOARDS", "total": 2, "imported": bad})
        assert import_count_findings(env) == [
            ("warning", "DASHBOARDS", import_uninterpretable_message("DASHBOARDS"))]
        assert import_shortfalls(env) == {}

    def test_digit_strings_are_counts(self):
        env = _envelope({"contentType": "DASHBOARDS", "total": "2", "imported": "1"})
        assert import_shortfalls(env) == {"DASHBOARDS": (2, 1, 0, 0)}

    @pytest.mark.parametrize("bad", [
        None, {}, {"state": "FINISHED"}, [],
        _envelope({"contentType": "DASHBOARDS", "imported": 0}),          # no total
        _envelope("not a summary", 7, None),
    ])
    def test_unusable_envelopes_are_quiet(self, bad):
        assert import_count_findings(bad) == []

    def test_dashboard_message_names_the_cause(self):
        msg = import_shortfall_message("DASHBOARDS", (2, 0, 0, 0))
        assert msg.startswith("DASHBOARDS: the import accounted for 0 of 2 ")
        assert "2 were neither imported, skipped nor failed" in msg
        assert "Section, measured failing on 8.18.7 and 9.0.2" in msg
        assert "every dashboard in the same import" in msg
        assert "restoreData failed to import Dashboards" in msg


def _stub_cli(monkeypatch, tmp_path, api_result, session=None, calls=None):
    dashboards = _load(tmp_path)
    monkeypatch.setattr(dash_cli, "_load", lambda args: ([], dashboards))
    monkeypatch.setattr(dash_cli.VCFOpsClient, "from_env",
                        classmethod(lambda cls, **kw: session or _VersionSession("VCF Operations 9.1.1.0")))
    monkeypatch.setattr(dash_cli, "get_current_user", lambda c: {"id": "u1", "username": "admin"})
    monkeypatch.setattr(dash_cli, "discover_marker_filename", lambda c: "1L.v1")
    monkeypatch.setattr(dash_cli, "build_import_zip", lambda *a, **k: b"zip")
    monkeypatch.setattr(dash_cli, "_run_dep_walker", lambda *a, **k: 0)

    def _import(c, b):
        if calls is not None:
            calls.append("import")
        return api_result
    monkeypatch.setattr(dash_cli, "import_content_zip", _import)
    return dashboards


def _sync_args(tmp_path):
    return types.SimpleNamespace(
        views_dir=str(tmp_path / "content" / "views"),
        dashboards_dir=str(tmp_path / "content" / "dashboards"),
        profile=None, supermetrics_dir=str(tmp_path / "supermetrics"),
        auto_enable_metrics=False, skip_metric_check=True,
    )


class TestCmdSyncShortfall:
    def test_short_counts_fail_the_sync_and_name_the_dashboards(
            self, monkeypatch, tmp_path, capsys):
        mat = []
        _stub_cli(monkeypatch, tmp_path, LOST_BATCH)
        monkeypatch.setattr(dash_cli, "_report_materialization",
                            lambda c, d, **k: mat.append([x.name for x in d]) or 0)
        rc = dash_cli.cmd_sync(_sync_args(tmp_path))
        err = capsys.readouterr().err
        assert rc == 1
        assert "ERROR: IMPORT SHORTFALL: DASHBOARDS: the import accounted for 0 of 2" in err
        assert "[VCF CF] Probe Section D1" in err and "[VCF CF] Probe Plain D2" in err
        # The existing by-id existence check still runs.
        assert mat == [["[VCF CF] Probe Section D1", "[VCF CF] Probe Plain D2"]]

    def test_a_view_shortfall_warns_and_keeps_the_exit_code(self, monkeypatch, tmp_path, capsys):
        _stub_cli(monkeypatch, tmp_path, _envelope(_summary("DASHBOARDS", 2, imported=2),
                                                   _summary("VIEW_DEFINITIONS", 2, imported=1)))
        monkeypatch.setattr(dash_cli, "_report_materialization", lambda *a, **k: 0)
        assert dash_cli.cmd_sync(_sync_args(tmp_path)) == 0
        err = capsys.readouterr().err
        assert "WARNING: IMPORT SHORTFALL: VIEW_DEFINITIONS: the import accounted for 1 of 2" in err
        assert "ERROR" not in err

    def test_clean_counts_say_nothing(self, monkeypatch, tmp_path, capsys):
        _stub_cli(monkeypatch, tmp_path, _envelope(_summary("DASHBOARDS", 2, imported=2)))
        monkeypatch.setattr(dash_cli, "_report_materialization", lambda *a, **k: 0)
        assert dash_cli.cmd_sync(_sync_args(tmp_path)) == 0
        assert "SHORTFALL" not in capsys.readouterr().err


class TestHandlersShortfall:
    def _stub(self, monkeypatch, api_result):
        monkeypatch.setattr(dash_handler, "get_current_user", lambda s: {"id": "u1"})
        monkeypatch.setattr(dash_handler, "discover_marker_filename", lambda s: "1L.v1")
        monkeypatch.setattr(dash_handler, "build_import_zip", lambda *a, **k: b"zip")
        monkeypatch.setattr(dash_handler, "import_content_zip", lambda s, b: api_result)

    def test_dashboards_handler_fails_every_dashboard(self, monkeypatch, tmp_path):
        from vcfcf_core.dashboards.materialization import ABSENT, MaterializationStatus
        _dashboards_dir(tmp_path)
        self._stub(monkeypatch, LOST_BATCH)
        monkeypatch.setattr(dash_handler, "_materialization_by_id", lambda s, ds: {
            d.id: MaterializationStatus(id=d.id, name=d.name, state=ABSENT) for d in ds})
        paths = sorted(str(p) for p in (tmp_path / "content" / "dashboards").glob("*.yaml"))
        result = dash_handler.DashboardsHandler().sync(paths, _VersionSession("VCF Operations 9.1.1.0"))
        assert [i.status for i in result.items] == ["failed", "failed"]
        for item in result.items:
            assert item.message.startswith("IMPORT SHORTFALL: DASHBOARDS: the import accounted for 0 of 2")
            assert "On the instance: MATERIALIZATION ABSENT." in item.message
        assert result.has_failures

    def test_a_failed_task_never_gets_the_shortfall_text(self, monkeypatch, tmp_path):
        _dashboards_dir(tmp_path)
        self._stub(monkeypatch, _envelope(_summary("DASHBOARDS", 2), state="FAILED"))
        paths = sorted(str(p) for p in (tmp_path / "content" / "dashboards").glob("*.yaml"))
        result = dash_handler.DashboardsHandler().sync(paths, _VersionSession("VCF Operations 9.1.1.0"))
        assert all("SHORTFALL" not in i.message for i in result.items)
        assert all(i.message == "import state=FAILED" for i in result.items)

    def test_views_handler_warns_and_keeps_status(self, monkeypatch, tmp_path, capsys):
        view = types.SimpleNamespace(name="[VCF CF] Stub View")
        monkeypatch.setattr(dash_handler, "load_view", lambda p: view)
        monkeypatch.setattr(dash_handler, "_sm_resolver_or_fail", lambda *a: (lambda n: None))
        self._stub(monkeypatch, _envelope(_summary("VIEW_DEFINITIONS", 1)))
        result = dash_handler.ViewsHandler().sync([str(tmp_path / "v.yaml")], object())
        assert [i.status for i in result.items] == ["ok"]
        assert "WARNING: IMPORT SHORTFALL: VIEW_DEFINITIONS: the import accounted for 0 of 1" \
            in capsys.readouterr().err


class TestOtherTypesWarnOnly:
    def test_supermetrics_handler(self, monkeypatch, tmp_path, capsys):
        from vcfcf_supermetrics import handler as sm_handler
        sm = types.SimpleNamespace(id="i", name="[VCF CF] SM", formula="1", description="",
                                   unit_id="", resource_kinds=[])
        monkeypatch.setattr(sm_handler, "load_file", lambda p: sm)
        session = types.SimpleNamespace(
            import_supermetrics_bundle=lambda b: _envelope(_summary("SUPER_METRICS", 1)))
        result = sm_handler.SuperMetricsHandler().sync([str(tmp_path / "s.yaml")], session)
        assert [i.status for i in result.items] == ["ok"]
        assert "WARNING: IMPORT SHORTFALL: SUPER_METRICS: the import accounted for 0 of 1" \
            in capsys.readouterr().err

    def test_reports_handler(self, monkeypatch, capsys):
        from vcfcf_reports import handler as rp_handler
        monkeypatch.setattr(rp_handler, "get_current_user", lambda s: {"id": "u1"})
        monkeypatch.setattr(rp_handler, "discover_marker_filename", lambda s: "1L.v1")
        monkeypatch.setattr(rp_handler, "build_import_zip", lambda *a, **k: b"zip")
        monkeypatch.setattr(rp_handler, "import_reports_zip",
                            lambda s, b: _envelope(_summary("REPORTS", 2, imported=1)))
        rd = types.SimpleNamespace(name="[VCF CF] Report")
        result = rp_handler.ReportsHandler().sync_loaded([rd], [], object())
        assert [i.status for i in result.items] == ["ok"]
        assert "WARNING: IMPORT SHORTFALL: REPORTS: the import accounted for 1 of 2" \
            in capsys.readouterr().err


# --- 2. the version floor ------------------------------------------------------

RELEASE_NAMES = [
    ("VCF Operations 9.0.2.0", (9, 0, 2)),
    ("VCF Operations 9.1.1.0100", (9, 1, 1, 100)),
    ("Aria Operations 8.18.7", (8, 18, 7)),
    ("VMware Aria Operations 8.18.7", (8, 18, 7)),
    ("VCF Operations 9.1.0.0", (9, 1)),
    ("VCF Operations 9.0.2.0 API 2.2", (9, 0, 2)),     # first dotted number wins
    ("VCF Operations\n9.0.2", (9, 0, 2)),              # same whitespace both sides
    ("VCF Operations 9.0.2", None),               # no-break space is not whitespace here
    ("VCF Operations ９.０.２", None),      # fullwidth digits
    ("VCF Operations 9.0²", None),                # superscript digit
    ("VCF Operations 9.2.0.0-beta", None),
    ("VCF Operations", None), ("garbage 1.2.3", None), ("", None),
]


@pytest.mark.parametrize("name,expected", RELEASE_NAMES + [(None, None), (42, None)])
def test_parse_release_name(name, expected):
    assert wv.parse_release_name(name) == expected


class TestImportCheck:
    PAIRS = [("[VCF CF] D1", [("sec", "Section"), ("t", "TextDisplay")]),
             ("[VCF CF] D2", [("t", "TextDisplay")])]

    @pytest.mark.parametrize("version,shown", [("8.18.7", "8.18.7"), ("9.0.2", "9.0.2"),
                                               ("9.0.9", "9.0.9")])
    def test_measured_failing_builds_are_refused(self, version, shown):
        refusal, warning = wv.import_check(self.PAIRS, version)
        assert warning is None
        assert refusal.startswith(f"refused before import: this instance is VCF Operations {shown}; ")
        assert "Section is measured not to import below 9.1.0 and proven to import from 9.1.1" in refusal
        assert "'[VCF CF] D1' (widget(s) sec (Section))" in refusal
        assert "[VCF CF] D2" not in refusal
        assert "loses EVERY dashboard in the same import (measured with one owner" in refusal
        assert "the import was not sent" in refusal

    @pytest.mark.parametrize("version", ["9.1.0", "9.1.0.0", "9.1.0.5"])
    def test_unmeasured_910_warns_and_imports(self, version):
        refusal, warning = wv.import_check(self.PAIRS, version)
        assert refusal is None
        assert warning.startswith("this instance is VCF Operations 9.1.0")
        assert "which is unverified" in warning and "Importing anyway" in warning
        assert "'[VCF CF] D1' (widget(s) sec (Section))" in warning

    @pytest.mark.parametrize("version", ["9.1.1", "9.1.1.0100", "9.2"])
    def test_at_or_above_the_proven_floor_is_clean(self, version):
        assert wv.import_check(self.PAIRS, version) == (None, None)

    def test_no_floored_type_is_clean(self):
        assert wv.import_check([("x", [("t", "TextDisplay")])], "8.18.7") == (None, None)


class TestRefusalAtEntryPoints:
    def test_cmd_sync_refuses_before_import(self, monkeypatch, tmp_path, capsys):
        calls = []
        session = _VersionSession("VMware Aria Operations 8.18.7")
        _stub_cli(monkeypatch, tmp_path, CLEAN, session=session, calls=calls)
        rc = dash_cli.cmd_sync(_sync_args(tmp_path))
        err = capsys.readouterr().err
        assert rc == 1 and calls == []
        assert "REFUSED: refused before import: this instance is VCF Operations 8.18.7" in err
        assert "'[VCF CF] Probe Section D1' (widget(s) sec (Section))" in err

    def test_cmd_sync_warns_and_imports_on_910(self, monkeypatch, tmp_path, capsys):
        calls = []
        _stub_cli(monkeypatch, tmp_path, _envelope(_summary("DASHBOARDS", 2, imported=2)),
                  session=_VersionSession("VCF Operations 9.1.0.0"), calls=calls)
        monkeypatch.setattr(dash_cli, "_report_materialization", lambda *a, **k: 0)
        assert dash_cli.cmd_sync(_sync_args(tmp_path)) == 0
        err = capsys.readouterr().err
        assert calls == ["import"]
        assert "WARNING: this instance is VCF Operations 9.1.0, which is unverified" in err

    def test_cmd_sync_imports_on_911(self, monkeypatch, tmp_path, capsys):
        calls = []
        _stub_cli(monkeypatch, tmp_path, _envelope(_summary("DASHBOARDS", 2, imported=2)),
                  calls=calls)
        monkeypatch.setattr(dash_cli, "_report_materialization", lambda *a, **k: 0)
        assert dash_cli.cmd_sync(_sync_args(tmp_path)) == 0
        assert calls == ["import"]
        err = capsys.readouterr().err
        assert "REFUSED" not in err and "unverified" not in err

    def test_unreadable_version_warns_and_imports(self, monkeypatch, tmp_path, capsys):
        calls = []
        _stub_cli(monkeypatch, tmp_path, LOST_BATCH, session=_VersionSession(status=500),
                  calls=calls)
        monkeypatch.setattr(dash_cli, "_report_materialization", lambda *a, **k: 0)
        rc = dash_cli.cmd_sync(_sync_args(tmp_path))
        err = capsys.readouterr().err
        assert calls == ["import"]
        assert VERSION_UNREADABLE_NOTE in err
        # ... and the count check is what then catches the loss.
        assert rc == 1 and "ERROR: IMPORT SHORTFALL" in err

    def test_no_floored_widget_makes_no_version_request(self, tmp_path):
        session = _VersionSession()
        d2 = [d for d in _load(tmp_path) if "Plain" in d.name]
        assert dash_client.widget_import_refusal(session, d2) == (None, None)
        assert session.calls == []

    def test_dashboards_handler_refuses_every_dashboard(self, monkeypatch, tmp_path):
        _dashboards_dir(tmp_path)
        monkeypatch.setattr(dash_handler, "import_content_zip",
                            lambda s, b: pytest.fail("import must not be sent"))
        paths = sorted(str(p) for p in (tmp_path / "content" / "dashboards").glob("*.yaml"))
        result = dash_handler.DashboardsHandler().sync(paths, _VersionSession())
        assert [i.status for i in result.items] == ["failed", "failed"]
        assert all(i.message.startswith("REFUSED: refused before import") for i in result.items)

    def test_bundle_sync_refuses_before_any_handler(self, monkeypatch, tmp_path, capsys):
        """A real bundle manifest with a Section dashboard, loaded by the core
        bundle loader."""
        import vcfcf_core.packaging.loader as core_bundle
        from vcfcf_packaging import syncer
        _dashboards_dir(tmp_path)
        (tmp_path / "bundles").mkdir()
        manifest = tmp_path / "bundles" / "probe.yaml"
        manifest.write_text("name: probe\ndashboards:\n  - content/dashboards/d1.yaml\n"
                            "  - content/dashboards/d2.yaml\n", encoding="utf-8")
        monkeypatch.setattr(syncer, "load_bundle",
                            lambda p: core_bundle.load_bundle(Path(p), repo_root=tmp_path))
        ran = []

        class _Handler:
            content_type = "dashboards"
            sync_order = 4

            def sync(self, yaml_paths, session):
                ran.append(yaml_paths)

        rc = syncer.sync_bundle(str(manifest), handlers=[_Handler()],
                                session=_VersionSession("VCF Operations 9.0.2.0"))
        err = capsys.readouterr().err
        assert rc == 1 and ran == []
        assert "FATAL: refused before import: this instance is VCF Operations 9.0.2" in err
        assert "[VCF CF] Probe Section D1" in err


def test_validate_stays_a_warning_and_says_the_batch_is_lost(tmp_path):
    """No content bundle declares a minimum version, so validate cannot gate."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        core_load_all(tmp_path / "content" / "views", _dashboards_dir(tmp_path))
    hits = [str(w.message) for w in caught if "issue #199" in str(w.message)]
    assert len(hits) == 1
    assert "is proven to import from VCF Ops 9.1.1" in hits[0]
    assert "loses EVERY dashboard in the same import" in hits[0]
    assert "no target version is declared" in hits[0]
    assert "sync and bundle install refuse" in hits[0]


# --- installer templates: install.py ------------------------------------------

@pytest.fixture(scope="module")
def install_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_install_template_199", TEMPLATES / "install.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_install_template_199"] = mod
    spec.loader.exec_module(mod)
    return mod


def _rendered_dashboard_json(tmp_path) -> str:
    """dashboard.json for D1 + D2 through the real renderer."""
    from vcfcf_core.dashboards.render import render_dashboards_bundle_json
    return render_dashboards_bundle_json(_load(tmp_path), {}, owner_user_id="PLACEHOLDER_USER_ID")


def _pairs_from_json(text):
    return [(d["name"], [(w["id"], w["type"]) for w in d.get("widgets") or []])
            for d in json.loads(text)["dashboards"]]


ENVELOPES = [
    LOST_BATCH, CLEAN,
    _envelope(_summary("DASHBOARDS", 2), _summary("VIEW_DEFINITIONS", 1, imported=1)),
    _envelope(_summary("SUPER_METRICS", 3, imported=2), _summary("REPORTS", 1, failed=1)),
    _envelope(_summary("DASHBOARDS", 1, skipped=1)),
    _envelope(_summary("DASHBOARDS", 2), state="FAILED"),
    _envelope({"contentType": "DASHBOARDS", "imported": 0}),
    _envelope({"contentType": "DASHBOARDS", "total": 2, "imported": 1.5}),
    _envelope({"contentType": "DASHBOARDS", "total": "2.0"}),
    _envelope({"contentType": "REPORTS", "total": True}),
    _envelope({"contentType": "REPORTS", "total": -1}),
    _envelope({"contentType": "REPORTS", "total": " 2"}),
    _envelope({"contentType": "REPORTS", "total": "2\n"}),
    _envelope({"contentType": "REPORTS", "total": "２"}),
    _envelope({"contentType": "SUPER_METRICS", "total": "3", "imported": "1"}),
    _envelope({"contentType": 7, "total": 1}, {"contentType": "", "total": 2, "imported": 2}),
    _envelope("junk", None, 3),
    {"state": "FINISHED"}, {},
]


class TestInstallPyParity:
    def test_findings(self, install_mod):
        for env in ENVELOPES:
            assert install_mod._import_count_findings(env) == import_count_findings(env), env

    def test_constants(self, install_mod):
        floored = {t: v for t, v in wv.WIDGET_TYPE_MIN_OPS_VERSION.items() if v is not None}
        assert install_mod._WIDGET_TYPE_FLOORS == floored
        assert install_mod._WIDGET_TYPE_REFUSE_BELOW == wv.WIDGET_TYPE_REFUSE_BELOW_OPS_VERSION
        assert install_mod._IMPORT_LOSS_SENTENCE == wv.IMPORT_LOSS_SENTENCE
        assert install_mod._SHORTFALL_SEVERITY == SHORTFALL_SEVERITY
        assert install_mod._VERSION_UNREADABLE_NOTE == VERSION_UNREADABLE_NOTE
        assert install_mod._RELEASE_NAME_VERSION_RE.pattern == wv.RELEASE_NAME_VERSION_RE.pattern

    @pytest.mark.parametrize("name,_e", RELEASE_NAMES + [(None, None)])
    def test_release_name(self, install_mod, name, _e):
        assert install_mod._parse_release_name(name) == wv.parse_release_name(name)

    @pytest.mark.parametrize("version", ["8.18.7", "9.0.2", "9.1.0", "9.1.1"])
    def test_check_on_rendered_json(self, install_mod, tmp_path, version):
        text = _rendered_dashboard_json(tmp_path)
        pairs = install_mod._dashboard_widget_pairs(text)
        assert pairs == _pairs_from_json(text)
        assert install_mod._import_check(pairs, version) == wv.import_check(pairs, version)


class _StubInstallClient:
    def __init__(self, *a, **k):
        self._user = "admin"

    def authenticate(self):
        return None

    def discover_marker_filename(self):
        return "1L.v1"

    def get_current_user(self):
        return {"id": "u1"}

    def get_ops_version(self):
        return _StubInstallClient.version


class TestInstallPyEntryPoints:
    def _ctx(self, install_mod, tmp_path, api_result):
        bundle_dir = tmp_path / "bundle"
        (bundle_dir / "content").mkdir(parents=True)
        (bundle_dir / "content" / "dashboard.json").write_text(json.dumps({"dashboards": [
            {"id": "dash-1", "name": "[VCF CF] Capacity"},
            {"id": "dash-2", "name": "[VCF CF] Plain"}]}))
        (bundle_dir / "content" / "sm.json").write_text(json.dumps({"i": {
            "name": "[VCF CF] SM", "formula": "1", "description": "", "unitId": "",
            "resourceKinds": []}}))
        (bundle_dir / "content" / "reports.xml").write_text(
            '<Content><ReportDef id="r"/></Content>')

        class _Client:
            def import_content_zip(self, blob, label):
                return api_result

        return {"client": _Client(), "ui_client": None, "marker": "1L.v1",
                "owner_id": "00000000-0000-0000-0000-000000000001", "username": "admin",
                "args": types.SimpleNamespace(), "warnings": [], "advisories": [],
                "bundle_dir": bundle_dir,
                "manifest": {"content": {"dashboards": {"file": "content/dashboard.json"},
                                         "supermetrics": {"file": "content/sm.json"},
                                         "reports": {"file": "content/reports.xml"}}}}

    def test_install_dashboards_lost_batch_is_an_error(self, install_mod, tmp_path, capsys):
        ctx = self._ctx(install_mod, tmp_path, LOST_BATCH)
        install_mod._install_dashboards(ctx)
        out = capsys.readouterr().out
        assert len(ctx["warnings"]) == 1
        assert ctx["warnings"][0].startswith("IMPORT SHORTFALL: DASHBOARDS: the import accounted for 0 of 2")
        assert "  ERROR  IMPORT SHORTFALL: DASHBOARDS" in out
        assert "Imported 1 dashboard" not in out
        # The end-of-run by-id existence check gets both ids.
        assert [i for i, _n in ctx["imported_dashboards"]] == ["dash-1", "dash-2"]

    def test_install_supermetrics_shortfall_only_warns(self, install_mod, tmp_path, capsys):
        ctx = self._ctx(install_mod, tmp_path, _envelope(_summary("SUPER_METRICS", 2, imported=1)))
        install_mod._install_supermetrics(ctx)
        out = capsys.readouterr().out
        assert ctx["warnings"] == []
        assert "WARN  IMPORT SHORTFALL: SUPER_METRICS: the import accounted for 1 of 2" in out
        assert "Imported 1 super metric(s)" in out

    def test_install_reports_shortfall_only_warns(self, install_mod, tmp_path, capsys):
        ctx = self._ctx(install_mod, tmp_path, _envelope(_summary("REPORTS", 1)))
        install_mod._install_reports(ctx)
        out = capsys.readouterr().out
        assert ctx["warnings"] == []
        assert "WARN  IMPORT SHORTFALL: REPORTS: the import accounted for 0 of 1" in out
        assert "Imported 1 report definition(s)" in out

    def _run_install(self, install_mod, monkeypatch, tmp_path, version, one_bundle=None):
        import argparse
        bundle_dir = tmp_path / "bundle"
        (bundle_dir / "content").mkdir(parents=True)
        (bundle_dir / "content" / "dashboard.json").write_text(_rendered_dashboard_json(tmp_path))
        _StubInstallClient.version = version
        monkeypatch.setattr(install_mod, "Client", _StubInstallClient)
        monkeypatch.setattr(install_mod, "_install_one_bundle",
                            one_bundle or (lambda *a: pytest.fail("nothing may be imported")))
        monkeypatch.setattr(install_mod, "_report_materialization", lambda *a: ([], []))
        bundles = [{"dir": bundle_dir, "name": "b",
                    "manifest": {"content": {"dashboards": {"file": "content/dashboard.json"}}}}]
        return install_mod._run_install(argparse.Namespace(skip_enable=True, force=False),
                                        "ops.example.test", "admin", "local", "pw", False, bundles)

    def test_run_install_refuses_before_any_import(self, install_mod, monkeypatch, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc:
            self._run_install(install_mod, monkeypatch, tmp_path, (9, 0, 2))
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "ERROR: refused before import: this instance is VCF Operations 9.0.2" in err
        assert "[VCF CF] Probe Section D1" in err

    def test_run_install_warns_on_910_and_imports(self, install_mod, monkeypatch, tmp_path, capsys):
        ran = []
        self._run_install(install_mod, monkeypatch, tmp_path, (9, 1),
                          one_bundle=lambda *a: ran.append(1) or (0, [], []))
        assert ran == [1]
        assert "WARN  this instance is VCF Operations 9.1.0, which is unverified" in capsys.readouterr().out

    def test_a_lost_batch_ends_on_not_imported(self, install_mod, monkeypatch, tmp_path, capsys):
        """W4: no "expected, refresh after ~5 minutes" over a lost batch."""
        lost = "IMPORT SHORTFALL: " + import_shortfall_message("DASHBOARDS", (2, 0, 0, 0))
        with pytest.raises(SystemExit) as exc:
            self._run_install(install_mod, monkeypatch, tmp_path, (9, 1, 1),
                              one_bundle=lambda *a: (0, [lost], []))
        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "Refresh after ~5 minutes" not in out and "This is expected" not in out
        assert f"  ERROR  {lost}" in out
        lines = [ln for ln in out.splitlines() if ln.strip()]
        assert lines[-1].startswith("ERROR: DASHBOARDS were not imported: ")
        assert "Waiting or refreshing will not bring them back." in lines[-1]

    def test_lost_lines_match_the_ps1_text(self, install_mod):
        assert install_mod._lost_import_lines([]) == []


# --- installer templates: install.ps1 (pwsh) ----------------------------------

@needs_pwsh
def test_install_ps1_matches_the_factory(tmp_path, install_mod):
    rendered = _rendered_dashboard_json(tmp_path)
    plain = json.dumps({"dashboards": [{"id": "d2", "name": "[VCF CF] Plain",
                                        "widgets": [{"id": "w", "type": "TextDisplay"}]}]})
    release_names = [n for n, _e in RELEASE_NAMES]
    versions = ("8.18.7", "9.0.2", "9.1.0", "9.1.1")
    install_dash = json.dumps({"dashboards": [{"id": "dash-1", "name": "[VCF CF] Capacity"},
                                              {"id": "dash-2", "name": "[VCF CF] Plain"}]})
    lost_inputs = ["IMPORT SHORTFALL: DASHBOARDS: x", "IMPORT SHORTFALL: REPORTS: y"]
    scenario = {
        "shortfalls": ENVELOPES,
        "lost": lost_inputs,
        "release_names": release_names,
        "refusals": [{"dash_json": rendered, "version": v} for v in versions],
        "preflights": [
            {"dash_json": rendered, "status": 200, "release_name": "VCF Operations 9.0.2.0"},
            {"dash_json": rendered, "status": 200, "release_name": "VCF Operations 9.1.1.0"},
            {"dash_json": rendered, "status": 500, "release_name": ""},
            {"dash_json": plain, "status": 200, "release_name": "VCF Operations 9.0.2.0"},
            {"dash_json": rendered, "status": 200, "release_name": "VCF Operations 9.1.0.0"},
        ],
        "installs": [{"dash_json": install_dash, "import_result": LOST_BATCH},
                     {"dash_json": install_dash, "import_result": _envelope(
                         _summary("DASHBOARDS", 2, imported=2))}],
        "other_installs": [
            {"fn": "Install-Supermetrics", "import_result": _envelope(_summary("SUPER_METRICS", 2, imported=1))},
            {"fn": "Install-Reports", "import_result": _envelope(_summary("REPORTS", 1))},
        ],
    }
    scen = tmp_path / "scenario.json"
    out = tmp_path / "out.json"
    scen.write_text(json.dumps(scenario), encoding="utf-8")
    proc = run_ps_file(PS_HARNESS, [TEMPLATES / "install.ps1", scen, out])
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    results = json.loads(out.read_text(encoding="utf-8-sig"))
    by_kind = {}
    for r in results:
        by_kind.setdefault(r["kind"], []).append(r["result"])

    for env, got in zip(ENVELOPES, by_kind["shortfall"]):
        want = [list(f) for f in import_count_findings(env)]
        assert (got or []) == want, env

    for line_in, got in zip(lost_inputs, by_kind["lost"]):
        assert list(got) == install_mod._lost_import_lines([line_in])

    for name, got in zip(release_names, by_kind["release"]):
        want = wv.parse_release_name(name)
        assert (tuple(got) if got is not None else None) == want, repr(name)

    pairs = _pairs_from_json(rendered)
    for v, got in zip(versions, by_kind["refusal"]):
        assert tuple(got) == wv.import_check(pairs, v), v

    refused, ok, unreadable, plain_run, unverified = by_kind["preflight"]
    assert refused["failed"] == wv.import_check(pairs, "9.0.2")[0]
    assert ok["failed"] is None and ok["version_calls"] == 1 and not ok["lines"]
    assert unreadable["failed"] is None
    assert any(VERSION_UNREADABLE_NOTE in ln for ln in unreadable["lines"])
    assert plain_run["failed"] is None and plain_run["version_calls"] == 0
    assert unverified["failed"] is None
    assert any(wv.import_check(pairs, "9.1.0")[1] in ln for ln in unverified["lines"])

    lost, clean = by_kind["install"]
    assert lost["warnings"] == ["IMPORT SHORTFALL: " + import_shortfall_message(
        "DASHBOARDS", (2, 0, 0, 0))]
    assert any(ln.startswith("  ERROR  IMPORT SHORTFALL: DASHBOARDS") for ln in lost["lines"])
    assert not any("Imported 1 dashboard" in ln for ln in lost["lines"])
    assert [p[0] for p in lost["recorded"]] == ["dash-1", "dash-2"]
    assert clean["warnings"] == [] and any("Imported 1 dashboard" in ln for ln in clean["lines"])

    sm, reports = by_kind["other"]
    for got, ct, counts, ok_line in ((sm, "SUPER_METRICS", (2, 1, 0, 0), "Imported 1 super metric(s)"),
                                     (reports, "REPORTS", (1, 0, 0, 0), "Imported 1 report definition(s)")):
        assert got["warnings"] == []  # exit code unchanged
        assert any(ln == "  WARN  IMPORT SHORTFALL: " + import_shortfall_message(ct, counts)
                   for ln in got["lines"])
        assert any(ok_line in ln for ln in got["lines"])


def test_install_ps1_summary_ends_on_not_imported():
    """W4, static: the PS summary keys on the same prefix and skips the note."""
    text = (TEMPLATES / "install.ps1").read_text(encoding="utf-8")
    body = text[text.index('$lost = [System.Collections.Generic.List[string]]::new()'):]
    body = body[:body.index("exit 2")]
    assert 'if ($lost.Count -eq 0) {' in body
    assert body.index('if ($lost.Count -eq 0) {') < body.index("This is expected. Refresh after ~5 minutes.")
    assert body.rstrip().endswith("foreach ($line in (Get-LostImportLines -Lost $lost.ToArray())) { Write-Host $line }")
