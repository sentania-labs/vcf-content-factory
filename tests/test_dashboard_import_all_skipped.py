"""Issue #97: a dashboard import that imported nothing must not read as ok.

`POST /api/content/operations/import` can finish with
``state=FINISHED`` while every object in the zip was skipped
(``imported=0, skipped=N``). The instance still holds the OLD content,
so reporting that as a successful sync/install is a false green.

Both dashboard sync paths (the standalone CLI and the bundle sync
handler) and the packaged installer template are covered here.

No network: the import call is stubbed in every test.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from vcfops_dashboards import cli as dash_cli
from vcfops_dashboards import handler as dash_handler
from vcfops_dashboards.client import (
    DASHBOARD_CONTENT_TYPES,
    all_skipped_content_types,
)


def _summary(content_type: str, imported: int, skipped: int) -> dict:
    return {
        "contentType": content_type,
        "imported": imported,
        "skipped": skipped,
        "failed": 0,
        "state": "FINISHED",
    }


def _result(imported: int, skipped: int, content_type: str = "DASHBOARDS") -> dict:
    return {
        "state": "FINISHED",
        "operationSummaries": [_summary(content_type, imported, skipped)],
    }


def _mixed_result(
    dash: tuple = (1, 0), views: tuple = (0, 2)
) -> dict:
    """The envelope these three call sites ACTUALLY produce: one zip,
    two content types. Every path here ships views and dashboards
    together, so a dashboard that imported fine routinely sits next to
    views the importer skipped."""
    return {
        "state": "FINISHED",
        "operationSummaries": [
            _summary("DASHBOARDS", *dash),
            _summary("VIEW_DEFINITIONS", *views),
        ],
    }


class _StubDashboard:
    """Stands in for a loaded Dashboard (name + widgets is all the
    sync path touches before the import call)."""

    def __init__(self, name: str = "[VCF Content Factory] Stub"):
        self.name = name
        self.widgets: list = []


# ---------------------------------------------------------------------------
# The detector itself
# ---------------------------------------------------------------------------

class TestAllSkippedContentTypes:
    def test_flags_imported_zero_with_skips(self):
        assert all_skipped_content_types(_result(0, 3)) == {"DASHBOARDS": (0, 3)}

    def test_clean_import_is_not_flagged(self):
        assert all_skipped_content_types(_result(3, 0)) == {}

    def test_partial_import_is_not_flagged(self):
        """Some imported means the import did change the instance."""
        assert all_skipped_content_types(_result(1, 2)) == {}

    def test_nothing_at_all_is_not_flagged(self):
        assert all_skipped_content_types({"state": "FINISHED"}) == {}
        assert all_skipped_content_types({}) == {}
        assert all_skipped_content_types(None) == {}

    def test_garbage_counts_degrade_instead_of_raising(self):
        bad = {
            "state": "FINISHED",
            "operationSummaries": [
                {"contentType": "DASHBOARDS", "imported": "oops", "skipped": 3}
            ],
        }
        assert all_skipped_content_types(bad) == {}

    def test_content_type_filter(self):
        res = _result(0, 3, content_type="SUPER_METRICS")
        assert all_skipped_content_types(res, DASHBOARD_CONTENT_TYPES) == {}
        assert all_skipped_content_types(res) == {"SUPER_METRICS": (0, 3)}


# ---------------------------------------------------------------------------
# Bundle sync handler
# ---------------------------------------------------------------------------

def _stub_handler_io(monkeypatch, api_result, dashboard):
    monkeypatch.setattr(dash_handler, "load_dashboard", lambda p: dashboard)
    monkeypatch.setattr(dash_handler, "load_view", lambda p: dashboard)
    monkeypatch.setattr(
        dash_handler, "get_current_user", lambda s: {"id": "u1", "userName": "admin"}
    )
    monkeypatch.setattr(dash_handler, "discover_marker_filename", lambda s: "1L.v1")
    monkeypatch.setattr(dash_handler, "build_import_zip", lambda *a, **k: b"zip")
    monkeypatch.setattr(
        dash_handler, "import_content_zip", lambda s, b: api_result
    )


class TestDashboardsHandlerSync:
    def test_all_skipped_import_is_warn_not_ok(self, monkeypatch, tmp_path):
        dash = _StubDashboard()
        _stub_handler_io(monkeypatch, _result(0, 3), dash)
        result = dash_handler.DashboardsHandler().sync(
            [str(tmp_path / "dashboards" / "d.yaml")], session=object()
        )
        assert [i.status for i in result.items] == ["warn"]
        msg = result.items[0].message
        assert "changed nothing" in msg
        assert "for DASHBOARDS (imported=0 skipped=3)" in msg
        # Still not a hard failure: skip-on-existing is a plausible
        # normal outcome, so the exit code must not flip.
        assert not result.has_failures

    def test_clean_import_still_reports_ok(self, monkeypatch, tmp_path):
        dash = _StubDashboard()
        _stub_handler_io(monkeypatch, _result(1, 0), dash)
        result = dash_handler.DashboardsHandler().sync(
            [str(tmp_path / "dashboards" / "d.yaml")], session=object()
        )
        assert [i.status for i in result.items] == ["ok"]

    def test_views_handler_also_warns(self, monkeypatch, tmp_path):
        view = _StubDashboard(name="[VCF Content Factory] Stub View")
        _stub_handler_io(
            monkeypatch, _result(0, 2, content_type="VIEW_DEFINITIONS"), view
        )
        result = dash_handler.ViewsHandler().sync(
            [str(tmp_path / "views" / "v.yaml")], session=object()
        )
        assert [i.status for i in result.items] == ["warn"]
        assert "for VIEW_DEFINITIONS (imported=0 skipped=2)" in result.items[0].message


# ---------------------------------------------------------------------------
# Standalone `python -m vcfops_dashboards sync`
# ---------------------------------------------------------------------------

def _stub_cli_io(monkeypatch, api_result, dashboards):
    monkeypatch.setattr(dash_cli, "_load", lambda args: ([], dashboards))
    monkeypatch.setattr(
        dash_cli.VCFOpsClient, "from_env", classmethod(lambda cls, **kw: object())
    )
    monkeypatch.setattr(
        dash_cli, "get_current_user", lambda c: {"id": "u1", "userName": "admin"}
    )
    monkeypatch.setattr(dash_cli, "discover_marker_filename", lambda c: "1L.v1")
    monkeypatch.setattr(dash_cli, "build_import_zip", lambda *a, **k: b"zip")
    monkeypatch.setattr(dash_cli, "import_content_zip", lambda c, b: api_result)
    monkeypatch.setattr(dash_cli, "_run_dep_walker", lambda *a, **k: 0)


def _sync_args(tmp_path):
    return types.SimpleNamespace(
        views_dir=str(tmp_path / "views"),
        dashboards_dir=str(tmp_path / "dashboards"),
        profile=None,
        supermetrics_dir=str(tmp_path / "supermetrics"),
        auto_enable_metrics=False,
        skip_metric_check=True,
    )


class TestCmdSync:
    def test_all_skipped_import_warns_loudly(self, monkeypatch, tmp_path, capsys):
        dash = _StubDashboard("[VCF Content Factory] Capacity")
        _stub_cli_io(monkeypatch, _result(0, 3), [dash])
        rc = dash_cli.cmd_sync(_sync_args(tmp_path))
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "imported=0 skipped=3" in captured.err
        # The affected content is named, not just counted.
        assert "[VCF Content Factory] Capacity" in captured.err
        assert rc == 0  # dep walker still drives the exit code

    def test_clean_import_prints_no_warning(self, monkeypatch, tmp_path, capsys):
        dash = _StubDashboard()
        _stub_cli_io(monkeypatch, _result(3, 0), [dash])
        rc = dash_cli.cmd_sync(_sync_args(tmp_path))
        captured = capsys.readouterr()
        assert "WARNING" not in captured.err
        assert rc == 0


# ---------------------------------------------------------------------------
# Packaged installer template (src/vcfops_packaging/templates/install.py)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def install_mod():
    """Import the installer template as a module without running it."""
    import importlib.util

    path = (
        Path(__file__).resolve().parents[1]
        / "src" / "vcfops_packaging" / "templates" / "install.py"
    )
    spec = importlib.util.spec_from_file_location("_install_template", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_install_template"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestInstallTemplateDashboards:
    def test_all_skipped_summaries_detector(self, install_mod):
        flagged = install_mod._all_skipped_summaries(
            _result(0, 3), ("DASHBOARDS", "VIEW_DEFINITIONS")
        )
        assert flagged == {"DASHBOARDS": (0, 3)}
        assert install_mod._all_skipped_summaries(_result(2, 1), ("DASHBOARDS",)) == {}
        assert install_mod._all_skipped_summaries({}, ("DASHBOARDS",)) == {}

    def test_install_dashboards_warns_on_all_skipped(
        self, install_mod, tmp_path, capsys
    ):
        ctx = self._make_ctx(install_mod, tmp_path, _result(0, 1))
        install_mod._install_dashboards(ctx)
        out = capsys.readouterr().out
        assert "WARN" in out
        assert "Import changed no dashboards" in out
        assert "[VCF Content Factory] Capacity" in out
        # W-1: this warning class must not flip the installer exit code.
        assert ctx["warnings"] == []
        # And the false-green line is NOT printed.
        assert "Imported 1 dashboard" not in out

    def test_install_dashboards_ok_on_clean_import(
        self, install_mod, tmp_path, capsys
    ):
        ctx = self._make_ctx(install_mod, tmp_path, _result(1, 0))
        install_mod._install_dashboards(ctx)
        out = capsys.readouterr().out
        assert "WARN" not in out
        assert "Imported 1 dashboard" in out
        assert ctx["warnings"] == []

    @staticmethod
    def _make_ctx(install_mod, tmp_path, api_result, with_views: bool = False):
        import json as _json

        bundle_dir = tmp_path / "bundle"
        (bundle_dir / "content").mkdir(parents=True)
        dash_file = bundle_dir / "content" / "dashboard.json"
        dash_file.write_text(
            _json.dumps({
                "dashboards": [
                    {"id": "dash-1", "name": "[VCF Content Factory] Capacity"}
                ]
            })
        )
        content = {"dashboards": {"file": "content/dashboard.json"}}
        if with_views:
            views_file = bundle_dir / "content" / "views_content.xml"
            views_file.write_text("<Content><ViewDefinitions/></Content>")
            content["views"] = {"file": "content/views_content.xml"}

        class _Client:
            def import_content_zip(self, blob, label):
                return api_result

        return {
            "client": _Client(),
            "ui_client": None,
            "marker": "1L.v1",
            "owner_id": "00000000-0000-0000-0000-000000000001",
            "username": "admin",
            "args": types.SimpleNamespace(),
            "warnings": [],
            "advisories": [],
            "bundle_dir": bundle_dir,
            "manifest": {"content": content},
        }


# ---------------------------------------------------------------------------
# Mixed envelope (framework review B-1): attribution must be per content type
# ---------------------------------------------------------------------------

class TestMixedEnvelopeAttribution:
    """The blocking case: DASHBOARDS imported=1 alongside
    VIEW_DEFINITIONS imported=0/skipped=2. Reporting the dashboard as
    "changed nothing" is a false statement contradicted by data in the
    same envelope, and it fires on the ordinary sync path."""

    def test_handler_does_not_blame_the_imported_dashboard(
        self, monkeypatch, tmp_path
    ):
        dash = _StubDashboard("[VCF Content Factory] Capacity")
        _stub_handler_io(monkeypatch, _mixed_result(dash=(1, 0), views=(0, 2)), dash)
        result = dash_handler.DashboardsHandler().sync(
            [str(tmp_path / "dashboards" / "d.yaml")], session=object()
        )
        assert [i.status for i in result.items] == ["ok"]
        assert result.items[0].message == ""

    def test_handler_flags_the_dashboard_when_dashboards_skipped(
        self, monkeypatch, tmp_path
    ):
        dash = _StubDashboard()
        _stub_handler_io(monkeypatch, _mixed_result(dash=(0, 1), views=(2, 0)), dash)
        result = dash_handler.DashboardsHandler().sync(
            [str(tmp_path / "dashboards" / "d.yaml")], session=object()
        )
        assert [i.status for i in result.items] == ["warn"]
        assert "DASHBOARDS" in result.items[0].message
        assert "VIEW_DEFINITIONS" not in result.items[0].message

    def test_views_handler_speaks_only_for_view_definitions(
        self, monkeypatch, tmp_path
    ):
        view = _StubDashboard(name="[VCF Content Factory] Stub View")
        # Views imported fine; the dashboards in the same envelope did not.
        _stub_handler_io(monkeypatch, _mixed_result(dash=(0, 1), views=(2, 0)), view)
        result = dash_handler.ViewsHandler().sync(
            [str(tmp_path / "views" / "v.yaml")], session=object()
        )
        assert [i.status for i in result.items] == ["ok"]

    def test_cmd_sync_names_only_the_flagged_type(
        self, monkeypatch, tmp_path, capsys
    ):
        dash = _StubDashboard("[VCF Content Factory] Capacity")
        _stub_cli_io(monkeypatch, _mixed_result(dash=(1, 0), views=(0, 2)), [dash])
        rc = dash_cli.cmd_sync(_sync_args(tmp_path))
        err = capsys.readouterr().err
        assert rc == 0
        assert "VIEW_DEFINITIONS" in err
        # The dashboard imported (imported=1); it must not be named as
        # affected, and must be reported as not affected.
        assert "affected DASHBOARDS content" not in err
        assert ("not affected (imported normally): "
                "[VCF Content Factory] Capacity") in err

    def test_install_template_keeps_the_dashboard_success_line(
        self, install_mod, tmp_path, capsys
    ):
        ctx = TestInstallTemplateDashboards._make_ctx(
            install_mod, tmp_path, _mixed_result(dash=(1, 0), views=(0, 2)),
            with_views=True,
        )
        install_mod._install_dashboards(ctx)
        out = capsys.readouterr().out
        assert "Imported 1 dashboard" in out
        assert "Import changed no views" in out
        assert "Import changed no dashboards" not in out
        # W-1: an advisory warning must not fail an install that succeeded.
        assert ctx["warnings"] == []

    def test_install_template_flags_only_dashboards_when_views_imported(
        self, install_mod, tmp_path, capsys
    ):
        ctx = TestInstallTemplateDashboards._make_ctx(
            install_mod, tmp_path, _mixed_result(dash=(0, 1), views=(2, 0)),
            with_views=True,
        )
        install_mod._install_dashboards(ctx)
        out = capsys.readouterr().out
        assert "Import changed no dashboards" in out
        assert "[VCF Content Factory] Capacity" in out
        assert "Imported 1 view(s)" in out
        assert ctx["warnings"] == []


class TestInstallerExitCodeUnchanged:
    def test_flagged_import_does_not_populate_the_installer_warnings_list(
        self, install_mod, tmp_path, capsys
    ):
        """W-1: ctx["warnings"] flows to sys.exit(2). This warning class
        must not turn a genuinely successful install into a failure."""
        ctx = TestInstallTemplateDashboards._make_ctx(
            install_mod, tmp_path, _result(0, 1)
        )
        install_mod._install_dashboards(ctx)
        assert ctx["warnings"] == []
        assert "WARN" in capsys.readouterr().out  # still loud


class TestDetectorParity:
    """N-4: the installer template must stay standalone, so it carries
    its own copy of the detector. Nothing pinned that the two agree."""

    FIXTURES = [
        _result(0, 3),
        _result(3, 0),
        _result(1, 2),
        _result(0, 2, content_type="VIEW_DEFINITIONS"),
        _mixed_result(dash=(1, 0), views=(0, 2)),
        _mixed_result(dash=(0, 1), views=(2, 0)),
        _mixed_result(dash=(0, 1), views=(0, 1)),
        {"state": "FINISHED"},
        {},
    ]

    def test_both_detectors_agree(self, install_mod):
        for fixture in self.FIXTURES:
            mine = all_skipped_content_types(fixture, DASHBOARD_CONTENT_TYPES)
            theirs = install_mod._all_skipped_summaries(
                fixture, DASHBOARD_CONTENT_TYPES
            )
            assert mine == theirs, fixture


# ---------------------------------------------------------------------------
# Bundle syncer end-of-run trailer (NIT N-1)
# ---------------------------------------------------------------------------

def test_sync_bundle_prints_a_warning_trailer(monkeypatch, capsys):
    """Per-item warn lines scroll away among the OK lines; the run must
    end with a count."""
    from vcfops_packaging import syncer
    from vcfops_packaging.handler import ItemResult, SyncResult

    class _Handler:
        content_type = "dashboards"
        sync_order = 4

        def sync(self, yaml_paths, session):
            r = SyncResult(content_type="dashboards")
            r.items.append(ItemResult(name="d1", status="warn", message="changed nothing"))
            r.items.append(ItemResult(name="d2", status="ok"))
            return r

    bundle = types.SimpleNamespace(name="b", description="", dashboards=["/x/d.yaml"])
    monkeypatch.setattr(syncer, "load_bundle", lambda p: bundle)
    monkeypatch.setattr(
        syncer, "_get_yaml_paths_for_type",
        lambda b, ct: ["/x/d.yaml"] if ct == "dashboards" else [],
    )
    rc = syncer.sync_bundle("bundles/<fixture>.yaml", handlers=[_Handler()],
                            session=object())
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 item(s) need attention (1 dashboards)" in out


# ---------------------------------------------------------------------------
# Installer summary trailer (review round 2 WARNING)
# ---------------------------------------------------------------------------

class TestInstallerAdvisoryTrailer:
    """The last line is what an operator remembers. A run whose import
    changed nothing must not end on an unqualified success line."""

    @staticmethod
    def _drive_summary(install_mod, monkeypatch, tmp_path, advisories, warnings):
        """Run the REAL _run_install summary block with a stub bundle."""
        import argparse

        class _StubClient:
            def __init__(self, *a, **k):
                self._user = "admin"

            def authenticate(self):
                return None

            def discover_marker_filename(self):
                return "1L.v1"

            def get_current_user(self):
                return {"id": "u1"}

        monkeypatch.setattr(install_mod, "Client", _StubClient)
        monkeypatch.setattr(
            install_mod, "_install_one_bundle",
            lambda bundle, gctx, step, total: (0, list(warnings), list(advisories)),
        )
        bundles = [{"dir": tmp_path, "manifest": {"content": {}}, "name": "b"}]
        args = argparse.Namespace(skip_enable=True, force=False)
        return install_mod._run_install(
            args, "ops.example.test", "admin", "local", "pw", False, bundles
        )

    def test_advisory_run_does_not_end_on_all_successful(
        self, install_mod, monkeypatch, tmp_path, capsys
    ):
        self._drive_summary(
            install_mod, monkeypatch, tmp_path,
            advisories=["[b] Import changed no dashboards ..."],
            warnings=[],
        )
        out = capsys.readouterr().out
        assert "Done. All content installed successfully." not in out
        assert "1 item(s) need attention" in out
        assert "ATTENTION" in out

    def test_clean_run_still_says_all_successful(
        self, install_mod, monkeypatch, tmp_path, capsys
    ):
        self._drive_summary(
            install_mod, monkeypatch, tmp_path, advisories=[], warnings=[]
        )
        out = capsys.readouterr().out
        assert "Done. All content installed successfully." in out
        assert "need attention" not in out

    def test_advisories_do_not_change_the_exit_code(
        self, install_mod, monkeypatch, tmp_path
    ):
        """Advisories are not failures: a genuinely successful install
        must still exit 0 (SystemExit is only raised on warnings)."""
        self._drive_summary(
            install_mod, monkeypatch, tmp_path,
            advisories=["[b] Import changed no dashboards ..."],
            warnings=[],
        )  # no SystemExit means rc 0

    def test_trailer_also_prints_in_the_warning_branch(
        self, install_mod, monkeypatch, tmp_path, capsys
    ):
        """A real warning still exits 2, and the advisory must not be
        lost behind it."""
        with pytest.raises(SystemExit) as exc:
            self._drive_summary(
                install_mod, monkeypatch, tmp_path,
                advisories=["[b] Import changed no dashboards ..."],
                warnings=["Super metric could not be enabled"],
            )
        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "Done with 1 warning(s):" in out
        assert "ATTENTION" in out


def test_installer_view_warning_names_the_views(install_mod, tmp_path, capsys):
    """Symmetry nit: the dashboard line names its dashboards, so the view
    line must name its views."""
    ctx = TestInstallTemplateDashboards._make_ctx(
        install_mod, tmp_path, _mixed_result(dash=(1, 0), views=(0, 2)),
        with_views=True,
    )
    # Give the staged views XML real titles.
    (ctx["bundle_dir"] / "content" / "views_content.xml").write_text(
        "<Content><Views>"
        "<ViewDef id='v1'><Title>[VCF Content Factory] Alpha</Title></ViewDef>"
        "<ViewDef id='v2'><Title>[VCF Content Factory] Beta</Title></ViewDef>"
        "</Views></Content>"
    )
    install_mod._install_dashboards(ctx)
    out = capsys.readouterr().out
    assert "Import changed no views" in out
    assert "[VCF Content Factory] Alpha" in out
    assert "[VCF Content Factory] Beta" in out


def test_extract_view_names_degrades_on_garbage(install_mod):
    assert install_mod._extract_view_names("") == []
    assert install_mod._extract_view_names("not xml at all") == []
    assert install_mod._extract_view_names(None) == []
