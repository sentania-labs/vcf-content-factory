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

import json
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

    def test_success_line_does_not_promise_the_list_is_immediately_below(
        self, install_mod, monkeypatch, tmp_path, capsys
    ):
        """N-18 (issue #103): the 5-minute NOTE block prints between the
        success line and the attention list, so "below" was seven lines
        optimistic. The ordering is deliberate, so the wording moved."""
        self._drive_summary(
            install_mod, monkeypatch, tmp_path,
            advisories=["[b] Import changed no dashboards ..."],
            warnings=[],
        )
        out = capsys.readouterr().out
        assert "see the attention list below" not in out
        assert "see the attention list at the end of this output." in out
        lines = [ln for ln in out.splitlines() if ln.strip()]
        # The claim the wording makes must be true: the list really is at
        # the end, and the NOTE block really does sit in between.
        assert lines[-1].startswith("  ATTENTION  ")
        pointer = next(
            i for i, ln in enumerate(lines) if "at the end of this output." in ln
        )
        header = next(i for i, ln in enumerate(lines) if "need attention" in ln)
        assert any("NOTE: VCF Operations needs" in ln for ln in lines[pointer:header])

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


# ---------------------------------------------------------------------------
# Issue #103: _extract_view_names was a regex over <Title>...</Title>.
# Quadratic on unclosed opens, unbounded output, defeated by any attribute
# on <Title>, and it handed the operator XML-escaped names beside
# unescaped dashboard names. It is now an ElementTree parse, modelled on
# vcfops_packaging/audit.py's ViewDef/Title walk.
# ---------------------------------------------------------------------------

_FACTORY_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    "<Content><Views>"
    '<ViewDef id="v1"><Title>[VCF Content Factory] Alpha</Title>'
    '<Description>a</Description></ViewDef>'
    '<ViewDef id="v2"><Title>[VCF Content Factory] Beta</Title>'
    '<Description>b</Description></ViewDef>'
    "</Views></Content>"
)


class TestExtractViewNames:
    def test_factory_shape_extracts_exactly_the_titles(self, install_mod):
        assert install_mod._extract_view_names(_FACTORY_XML) == [
            "[VCF Content Factory] Alpha",
            "[VCF Content Factory] Beta",
        ]

    def test_pre_def018_localization_key_attribute_no_longer_defeats_it(
        self, install_mod
    ):
        """The regex extracted ZERO names from this shape (commit 8ad7dd2's
        markup) and silently degraded to the generic "view(s)"."""
        xml_text = (
            "<Content><Views>"
            '<ViewDef id="v1">'
            '<Title localizationKey="k1">[VCF Content Factory] Alpha</Title>'
            "</ViewDef>"
            "</Views></Content>"
        )
        assert install_mod._extract_view_names(xml_text) == [
            "[VCF Content Factory] Alpha"
        ]

    def test_names_reach_the_operator_unescaped(self, install_mod):
        """N-17: the renderer escapes, so the parse must decode. Dashboard
        names print raw; these must match that fidelity."""
        xml_text = (
            "<Content><Views>"
            '<ViewDef id="v1"><Title>CPU &amp; Memory &lt;top&gt;</Title></ViewDef>'
            "</Views></Content>"
        )
        assert install_mod._extract_view_names(xml_text) == ["CPU & Memory <top>"]

    def test_unclosed_titles_return_empty_fast(self, install_mod):
        """N-14: the reviewer's pathological input. 20,000 unclosed opens
        took 21s under the regex (`.*?` with re.DOTALL rescans to
        end-of-string from every open tag). The parse rejects it outright."""
        import time

        pathological = "<Title>" * 20000
        start = time.perf_counter()
        assert install_mod._extract_view_names(pathological) == []
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"took {elapsed:.3f}s; regression to the O(n^2) scan"

    def test_a_very_long_name_is_clipped(self, install_mod):
        xml_text = (
            "<Content><Views>"
            f'<ViewDef id="v1"><Title>{"A" * 500_000}</Title></ViewDef>'
            "</Views></Content>"
        )
        names = install_mod._extract_view_names(xml_text)
        assert len(names) == 1
        assert len(names[0]) == install_mod._ADVISORY_NAME_MAX_CHARS + 3
        assert names[0].endswith("...")

    def test_many_names_get_an_and_n_more_tail(self, install_mod):
        n = install_mod._ADVISORY_NAMES_MAX + 7
        xml_text = (
            "<Content><Views>"
            + "".join(
                f'<ViewDef id="v{i}"><Title>View {i}</Title></ViewDef>'
                for i in range(n)
            )
            + "</Views></Content>"
        )
        names = install_mod._extract_view_names(xml_text)
        assert len(names) == install_mod._ADVISORY_NAMES_MAX + 1
        assert names[-1] == "and 7 more"
        assert names[0] == "View 0"

    def test_viewdef_without_a_title_falls_back_to_the_name_attribute(
        self, install_mod
    ):
        xml_text = (
            "<Content><Views>"
            '<ViewDef id="v1" name="Legacy View"/>'
            '<ViewDef id="v2"/>'
            "</Views></Content>"
        )
        assert install_mod._extract_view_names(xml_text) == [
            "Legacy View",
            "unnamed view",
        ]

    @pytest.mark.parametrize(
        "hostile",
        [
            None,
            "",
            0,
            42,
            b"<Content><Views></Views></Content>",
            b"\x00\x01\x02",
            [],
            ["<Title>x</Title>"],
            {},
            {"a": 1},
            "not xml at all",
            "<Title>orphan",
            "</Title>",
            "<Content><Views><ViewDef><Title>a<Title>b</Title></Title>"
            "</ViewDef></Views></Content>",
            "<Content><Views><ViewDef><Title>a\x00b</Title></ViewDef></Views></Content>",
            "<Content><Views><ViewDef><Title>\ud800</Title></ViewDef></Views></Content>",
            "<Content><Views><ViewDef><Title>a</Title></ViewDef></Views>",
            "<Title>" * 5000,
        ],
        ids=lambda v: repr(v)[:40],
    )
    def test_hostile_inputs_never_raise(self, install_mod, hostile):
        out = install_mod._extract_view_names(hostile)
        assert isinstance(out, list)

    def test_extraction_matches_real_renderer_output(self, install_mod, tmp_path):
        """Pins the coupling to src/vcfops_dashboards/render.py, which emits
        <Title>{escape(view.name)}</Title> once per ViewDef and nowhere
        else. Nothing pinned this before, so the extractor could drift out
        of step with the renderer silently (issue #103 item 3)."""
        import yaml

        from vcfops_dashboards.loader import load_view
        from vcfops_dashboards.render import render_views_xml

        names = [
            "[VCF Content Factory] VM Network Top Talkers",
            "[VCF Content Factory] CPU & Memory <top>",
        ]
        views = []
        for i, name in enumerate(names):
            data = {
                "name": name,
                "description": "Rendered through the real renderer.",
                "subject": {
                    "adapter_kind": "VMWARE",
                    "resource_kind": "VirtualMachine",
                },
                "columns": [
                    {
                        "display_name": "Name",
                        "attribute": "summary|name",
                        "is_property": True,
                        "is_string_attribute": True,
                    }
                ],
            }
            p = tmp_path / f"view{i}.yaml"
            p.write_text(yaml.dump(data, default_flow_style=False))
            views.append(load_view(p, enforce_framework_prefix=False))

        xml_text = render_views_xml(views)
        # Guard the premise: the renderer really does escape.
        assert "CPU &amp; Memory &lt;top&gt;" in xml_text
        assert xml_text.count("<Title") == len(names)
        assert install_mod._extract_view_names(xml_text) == names


# ---------------------------------------------------------------------------
# _extract_dashboard_names, the other half of the same advisory sentence.
# It returned d.get("name") unconverted, so a non-string JSON name reached
# ", ".join(...) at install.py:1526 -- which sits OUTSIDE any try -- and
# aborted the installer AFTER content had been imported, leaving a partial
# install. It also had neither the clip nor the cap the view side gained.
# ---------------------------------------------------------------------------

class TestExtractDashboardNames:
    def test_factory_shape_extracts_the_names(self, install_mod):
        payload = json.dumps({"dashboards": [
            {"id": "d1", "name": "[VCF Content Factory] Alpha"},
            {"id": "d2", "name": "[VCF Content Factory] Beta"},
        ]})
        assert install_mod._extract_dashboard_names(payload) == [
            "[VCF Content Factory] Alpha",
            "[VCF Content Factory] Beta",
        ]

    def test_falls_back_to_id_then_placeholder(self, install_mod):
        payload = json.dumps({"dashboards": [{"id": "d1"}, {}]})
        assert install_mod._extract_dashboard_names(payload) == ["d1", "?"]

    def test_non_string_name_is_coerced_not_returned_raw(self, install_mod):
        """The crash: [123] joined with ", " raises TypeError."""
        payload = '{"dashboards":[{"name":123}]}'
        names = install_mod._extract_dashboard_names(payload)
        assert names == ["123"]
        assert all(isinstance(n, str) for n in names)

    @pytest.mark.parametrize(
        "payload",
        [
            '{"dashboards":[{"name":123}]}',
            '{"dashboards":[{"name":1.5}]}',
            '{"dashboards":[{"name":true}]}',
            '{"dashboards":[{"name":null,"id":7}]}',
            '{"dashboards":[{"name":["a","b"]}]}',
            '{"dashboards":[{"name":{"k":"v"}}]}',
            '{"dashboards":[null]}',
            '{"dashboards":["just a string"]}',
            '{"dashboards":[1,2,3]}',
            '{"dashboards":{"not":"a list"}}',
            '{"dashboards":"nope"}',
            '{"dashboards":[]}',
            "[1,2,3]",
            '"just a json string"',
            "42",
            "null",
            "not json at all",
            "",
            None,
            42,
            b'{"dashboards":[{"name":"Bytes Dash"}]}',
        ],
        ids=lambda v: repr(v)[:44],
    )
    def test_hostile_payloads_never_raise_and_always_join(
        self, install_mod, payload
    ):
        """Every element must survive the join that builds the advisory.
        This is the property the installer actually depends on."""
        names = install_mod._extract_dashboard_names(payload)
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)
        ", ".join(names)  # must not raise

    def test_deeply_nested_json_does_not_escape_as_recursionerror(
        self, install_mod
    ):
        """W-2: json.loads raises RecursionError here, and RecursionError
        subclasses RuntimeError, so the old `except (TypeError,
        ValueError)` did not catch it. Every caller runs AFTER the import,
        so an escape leaves a partial install."""
        payload = '{"dashboards":' + "[" * 40000 + "]" * 40000 + "}"
        assert install_mod._extract_dashboard_names(payload) == []

    def test_view_sibling_also_survives_deep_nesting(self, install_mod):
        """The symmetry claim, driven rather than assumed. Note the view
        side survives by PARSING deep XML successfully (ElementTree's C
        accelerator does not recurse in Python), not by degrading to []:
        50,000 nested ViewDefs come back as 50,000 unnamed views, capped.
        The property that matters is the same either way -- it does not
        raise, and the result is join-safe."""
        deep = (
            "<Content><Views>"
            + "<ViewDef>" * 50000
            + "</ViewDef>" * 50000
            + "</Views></Content>"
        )
        names = install_mod._extract_view_names(deep)
        assert isinstance(names, list)
        assert len(names) == install_mod._ADVISORY_NAMES_MAX + 1
        assert names[-1] == "and 49980 more"
        ", ".join(names)  # must not raise

    def test_dashboards_as_a_string_is_rejected_not_iterated(
        self, install_mod
    ):
        """N-9: pins the isinstance(entries, list) guard. Without it the
        string iterates character by character and returns ['?','?','?',
        '?'] -- no exception, both other properties still hold, and the
        operator reads "NOT updated: ?, ?, ?, ?". The guard was the only
        one of the four that no test killed when mutated out."""
        assert install_mod._extract_dashboard_names('{"dashboards":"nope"}') == []

    def test_bounded_names_cannot_raise_on_its_own(self, install_mod):
        """It is a shared helper now, so its contract is its own, not the
        callers'. A third caller must not be able to reintroduce the
        crash-after-import class."""
        class _BadStr:
            def __str__(self):
                raise RuntimeError("boom")

        def _raising_iter():
            yield "ok"
            raise RuntimeError("boom")

        for bad in (None, 42, object(), [_BadStr()], _raising_iter()):
            out = install_mod._bounded_names(bad)
            assert isinstance(out, list)
            assert all(isinstance(n, str) for n in out)
            ", ".join(out)  # must not raise

    def test_a_very_long_name_is_clipped(self, install_mod):
        payload = json.dumps({"dashboards": [{"name": "A" * 500_000}]})
        names = install_mod._extract_dashboard_names(payload)
        assert len(names) == 1
        assert len(names[0]) == install_mod._ADVISORY_NAME_MAX_CHARS + 3
        assert names[0].endswith("...")

    def test_many_names_get_an_and_n_more_tail(self, install_mod):
        n = install_mod._ADVISORY_NAMES_MAX + 7
        payload = json.dumps(
            {"dashboards": [{"name": f"Dash {i}"} for i in range(n)]}
        )
        names = install_mod._extract_dashboard_names(payload)
        assert len(names) == install_mod._ADVISORY_NAMES_MAX + 1
        assert names[-1] == "and 7 more"
        assert names[0] == "Dash 0"

    def test_bounds_match_the_view_side(self, install_mod):
        """The asymmetry this fix closes: both halves of the sentence are
        clipped and capped by the same shared helper."""
        long_name = "B" * 500_000
        dash = install_mod._extract_dashboard_names(
            json.dumps({"dashboards": [{"name": long_name}]})
        )
        view = install_mod._extract_view_names(
            f"<Content><Views><ViewDef><Title>{long_name}</Title></ViewDef>"
            "</Views></Content>"
        )
        assert dash == view

    def test_installer_dashboard_advisory_survives_a_non_string_name(
        self, install_mod, tmp_path, capsys
    ):
        """End to end through the real _install_dashboards: the join at
        :1526 is outside every try, so this used to abort mid-install."""
        ctx = TestInstallTemplateDashboards._make_ctx(
            install_mod, tmp_path, _mixed_result(dash=(0, 1), views=(1, 0)),
            with_views=True,
        )
        (ctx["bundle_dir"] / "content" / "dashboard.json").write_text(
            '{"dashboards":[{"id":"d1","name":123}]}'
        )
        install_mod._install_dashboards(ctx)  # must not raise
        out = capsys.readouterr().out
        assert "Import changed no dashboards" in out
        assert "123" in out
