"""Pak install rebinds a Summary tab cloned before its dashboard finished (#200).

The server's pak installer clones each ``dashboards.properties``-bound
dashboard into a SUMMARY template seconds after import. On devel 9.0.2 the
clone is taken while the source's widgets are unresolved and stays that way
(on 2026-10-24 the compliance ComplianceWorld clone ``1680c6bc`` read
``isLoading: true`` on all seven widgets, its source ``4e2c777e`` false on
all seven). The factory's install waits for the source, reads the clone with
``getDashboardConfig?isTemplate=true`` and binds again by the pak
dashboard's id only when the clone is unfinished.

Also pins the review findings on the parked 2026-10-13 branch: bind by id
(B1), fail closed on a missing flag (W1), transient errors keep polling
(W2), Java ``String.split`` semantics and ``GenericTemplates*`` (W3), a
distinct exit code (W4), one dashboard per bound directory (N2). No live
instance: every read is faked.
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

from vcfcf_core.dashboards import materialization as mat  # noqa: E402
from vcfcf_managementpacks import post_install as pi  # noqa: E402

ID_WORLD = "4e2c777e-9c6c-4c6a-bc16-ab55b6110f33"
ID_OTHER = "0be1f00d-0000-4000-8000-000000000009"
NAME = "[VCF Content Factory] Compliance World Summary"
RKID = "002016vcfcf_complianceComplianceWorld"
OLD_CLONE = "1680c6bc-51da-4947-9aa8-7a00a25f558a"
NEW_CLONE = "77777777-0000-4000-8000-000000000007"
ENTRIES = {"resourceKind": [{"resourceKindKey": "ComplianceWorld",
                             "internalId": "resourceKind:id:0_::_",
                             "adapterKindKey": "vcfcf_compliance"}]}


# --- dashboards.properties as the installer reads it ---------------------------

@pytest.mark.parametrize("value,expected", [
    ("vcfcf_compliance:ComplianceWorld", [("vcfcf_compliance", "ComplianceWorld")]),
    ("A:B:", [("A", "B")]),              # Java drops the trailing empty token
    (":B", [("", "B")]),                 # leading empty kept: size 2, accepted
    ("A: B", [("A", " B")]),             # not trimmed: the installer binds " B"
    ("A:B:C", []),                       # three tokens: skipped
    ("A", []),
    ("A:B,,C:D,", [("A", "B"), ("C", "D")]),
])
def test_java_split_semantics(tmp_path, value, expected):
    p = _pak(tmp_path, props=f"World={value}\n")
    dashes = pi.read_pak_dashboards(p, warn=print)
    got = pi.read_pak_bindings(p, dashes, warn=print)
    assert [tuple(k) for b in got for k in b.kinds] == expected


def test_properties_parser_and_generic_templates(tmp_path):
    props = ("# comment\n! also comment\n"
             "GenericTemplatesWorld=vcfcf_compliance:ComplianceWorld\n"
             "World : vcfcf_compliance:\\\n  ComplianceWorld\n")
    p = _pak(tmp_path, props=props, extra_dir="GenericTemplatesWorld")
    dashes = pi.read_pak_dashboards(p, warn=print)
    # Template directories never reach the materialization check either:
    # the dashboard list does not show them, so they would read as ABSENT.
    assert [d.directory for d in dashes] == ["World"]
    got = pi.read_pak_bindings(p, dashes, warn=print)
    assert [(b.directory, b.kinds) for b in got] == [
        ("World", [("vcfcf_compliance", "ComplianceWorld")])]


def test_directory_with_two_dashboards_is_not_guessed(tmp_path):
    warns = []
    p = _pak(tmp_path, props="World=vcfcf_compliance:ComplianceWorld\n", two_in_world=True)
    dashes = pi.read_pak_dashboards(p, warn=print)
    assert pi.read_pak_bindings(p, dashes, warn=warns.append) == []
    assert "holds 2 dashboard(s)" in warns[0]


def test_no_properties_no_bindings(tmp_path):
    p = _pak(tmp_path)
    assert pi.read_pak_bindings(p, pi.read_pak_dashboards(p, warn=print), warn=print) == []


# --- clone state ---------------------------------------------------------------------

def _config(tab_id, tab_loading, widget_flags, name=NAME + " 6"):
    widgets = []
    for f in widget_flags:
        w = {"key": "View"}
        if f is not None:
            w["isLoading"] = f
        widgets.append(w)
    tab = {"id": tab_id, "name": name, "widgets": widgets}
    if tab_loading is not None:
        tab["isLoading"] = tab_loading
    return {"dashboardConfig": {"tabConfigs": [tab], "widgetInteractions": []},
            "interactionTypes": []}


def test_template_state():
    assert pi.template_state(_config(OLD_CLONE, False, [False, False]), OLD_CLONE)[0] == pi.CLONE_COMPLETE
    assert pi.template_state(_config(OLD_CLONE, True, [True] * 7), OLD_CLONE)[0] == pi.CLONE_INCOMPLETE
    assert pi.template_state(_config(OLD_CLONE, False, [False, True]), OLD_CLONE)[0] == pi.CLONE_INCOMPLETE
    assert pi.template_state(_config(OLD_CLONE, None, [False]), OLD_CLONE)[0] == pi.CLONE_UNKNOWN
    assert pi.template_state(_config("other", False, [False]), OLD_CLONE)[0] == pi.CLONE_UNKNOWN
    assert pi.template_state({}, OLD_CLONE) == (pi.CLONE_UNKNOWN, "")
    assert pi.template_state(_config(OLD_CLONE.upper(), False, []), OLD_CLONE) == (
        pi.CLONE_COMPLETE, NAME + " 6")


def test_is_copy_of():
    assert pi._is_copy_of(NAME, NAME)
    assert pi._is_copy_of(NAME + " 6", NAME)
    assert not pi._is_copy_of(NAME + " v2", NAME)
    assert not pi._is_copy_of("Something else", NAME)


# --- repair ---------------------------------------------------------------------------

class _UI:
    def __init__(self, tab_answers, configs, assoc_raises=None, config_raises=False):
        self.tab_answers = list(tab_answers)
        self.configs = dict(configs)
        self.assoc = []
        self.assoc_raises = assoc_raises
        self.config_raises = config_raises

    def get_summary_tab_id(self, rkid):
        assert rkid == RKID
        return self.tab_answers.pop(0) if len(self.tab_answers) > 1 else self.tab_answers[0]

    def get_dashboard_config(self, tab_id, *, is_template=False):
        assert is_template is True
        if self.config_raises:
            raise RuntimeError("HTTP 500")
        return self.configs[tab_id]

    def associate_resource_kind_dashboards(self, assigned, reset):
        if self.assoc_raises:
            raise self.assoc_raises
        self.assoc.append((assigned, reset))


def _binding():
    d = pi.PakDashboard(id=ID_WORLD, name=NAME, directory="World", entries=ENTRIES)
    return pi.PakBinding(directory="World", dashboard=d,
                         kinds=[("vcfcf_compliance", "ComplianceWorld")])


def _status(state):
    return [mat.MaterializationStatus(id=ID_WORLD, name=NAME, state=state)]


def _repair(ui, state=mat.COMPLETE):
    out, err = [], []
    rc = pi.repair_summary_bindings(ui, [_binding()], _status(state),
                                    out=out.append, err=err.append)
    return rc, out, err


def test_finished_clone_is_left_alone():
    ui = _UI([{"tabId": OLD_CLONE}], {OLD_CLONE: _config(OLD_CLONE, False, [False] * 7)})
    rc, out, err = _repair(ui)
    assert rc == 0 and ui.assoc == [] and err == []
    assert out[0].startswith("SUMMARY OK: vcfcf_compliance:ComplianceWorld")


def test_unfinished_clone_of_finished_source_is_rebound_by_id():
    ui = _UI([{"tabId": OLD_CLONE}, {"tabId": NEW_CLONE, "isDashboard": True}],
             {OLD_CLONE: _config(OLD_CLONE, True, [True] * 7),
              NEW_CLONE: _config(NEW_CLONE, False, [False] * 7, name=NAME + " 7")})
    rc, out, err = _repair(ui)
    assert rc == 0 and err == []
    assert ui.assoc == [({f"resourceKind_{RKID}": f"{NAME}_::_{ID_WORLD}"}, {})]
    assert out[0].startswith("SUMMARY REBOUND: vcfcf_compliance:ComplianceWorld now shows "
                             f"copy {NEW_CLONE}")
    assert "complete" in out[0]


def test_unknown_clone_state_with_finished_source_is_rebound():
    ui = _UI([{"tabId": OLD_CLONE}, {"tabId": NEW_CLONE}],
             {OLD_CLONE: _config(OLD_CLONE, None, [None]),
              NEW_CLONE: _config(NEW_CLONE, False, [False])})
    rc, out, _ = _repair(ui)
    assert rc == 0 and len(ui.assoc) == 1 and "SUMMARY REBOUND" in out[0]


@pytest.mark.parametrize("state", [mat.INCOMPLETE, mat.STALLED])
def test_unfinished_source_is_never_bound(state):
    ui = _UI([{"tabId": OLD_CLONE}], {OLD_CLONE: _config(OLD_CLONE, True, [True])})
    rc, out, err = _repair(ui, state)
    assert ui.assoc == [] and rc == pi.POST_INSTALL_FAILED_RC
    assert err[0].startswith("WARNING: SUMMARY NOT REBOUND: ")
    assert "Manage Summary Dashboards" in err[0]


def test_source_missing_isloading_fails_closed():
    """W1: a source whose list entry had no isLoading never reaches COMPLETE
    (check_pak_dashboards leaves it out), so it is never bound, and the
    line says its state could not be checked rather than unfinished."""
    out, err = [], []
    ui = _UI([{"tabId": OLD_CLONE}], {OLD_CLONE: _config(OLD_CLONE, True, [True])})
    rc = pi.repair_summary_bindings(ui, [_binding()], [], out=out.append, err=err.append)
    assert ui.assoc == [] and rc == pi.POST_INSTALL_FAILED_RC
    assert "could not be checked" in err[0]
    assert "had not finished building" not in err[0]


@pytest.mark.parametrize("config", [
    {},                                                    # no dashboardConfig at all
    _config("some-other-tab", True, [True]),               # answer lacks the bound tab
    _config(OLD_CLONE, True, [True], name=""),             # bound tab, empty name
    _config(OLD_CLONE, None, [None], name=""),             # unknown state, empty name
])
def test_unidentifiable_summary_tab_is_never_written(config):
    """Review B2: a Summary tab whose name cannot be read is not known to be
    a copy of the pak dashboard, so nothing is written, whatever its state."""
    ui = _UI([{"tabId": "user-own-tab"}], {"user-own-tab": config})
    rc, out, err = _repair(ui)
    assert ui.assoc == [] and rc == 0 and out == []
    assert err[0].startswith("WARNING: SUMMARY UNCHECKED: vcfcf_compliance:ComplianceWorld")
    assert "left as it is" in err[0]


def test_not_bound_by_installer_is_left_alone():
    for answer in ({"isDashboard": False}, {"tabId": "plugin.key", "isDashboard": False,
                                            "pluginExist": True}):
        ui = _UI([answer], {})
        rc, out, err = _repair(ui)
        assert rc == 0 and ui.assoc == []
        assert err[0].startswith("WARNING: SUMMARY NOT BOUND: ")


def test_tab_showing_another_dashboard_is_left_alone():
    ui = _UI([{"tabId": OLD_CLONE}],
             {OLD_CLONE: _config(OLD_CLONE, True, [True], name="Somebody Else 2")})
    rc, out, err = _repair(ui)
    assert rc == 0 and ui.assoc == []
    assert "not a copy of" in err[0]


def test_absent_source_is_not_checked():
    ui = _UI([{"tabId": OLD_CLONE}], {})
    rc, out, err = _repair(ui, mat.ABSENT)
    assert rc == 0 and ui.assoc == [] and "SUMMARY NOT CHECKED" in err[0]


def test_rebind_that_does_not_move_the_tab_fails():
    ui = _UI([{"tabId": OLD_CLONE}], {OLD_CLONE: _config(OLD_CLONE, True, [True])})
    rc, out, err = _repair(ui)
    assert rc == pi.POST_INSTALL_FAILED_RC and len(ui.assoc) == 1
    assert "still points at" in err[0]


def test_new_copy_unfinished_fails():
    ui = _UI([{"tabId": OLD_CLONE}, {"tabId": NEW_CLONE}],
             {OLD_CLONE: _config(OLD_CLONE, True, [True]),
              NEW_CLONE: _config(NEW_CLONE, True, [True])})
    rc, out, err = _repair(ui)
    assert rc == pi.POST_INSTALL_FAILED_RC and "unfinished too" in err[0]


def test_read_error_is_unchecked_and_bind_error_after_a_known_blank_fails():
    ui = _UI([{"tabId": OLD_CLONE}], {}, config_raises=True)
    rc, out, err = _repair(ui)
    assert rc == 0 and err[0].startswith("WARNING: SUMMARY UNCHECKED: ")
    ui = _UI([{"tabId": OLD_CLONE}], {OLD_CLONE: _config(OLD_CLONE, True, [True])},
             assoc_raises=RuntimeError("associateResourceKindDashboards failed"))
    rc, out, err = _repair(ui)
    # A refused bind after a known blank copy is NOT REBOUND (exit 3); an
    # exception with no server reply attached is quoted as it is.
    assert rc == pi.POST_INSTALL_FAILED_RC
    assert err[0].startswith("WARNING: SUMMARY NOT REBOUND: ")
    assert "Server answer: associateResourceKindDashboards failed" in err[0]


# --- the polled wait ----------------------------------------------------------------------

class _ListUI:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    def list_dashboards(self):
        self.calls += 1
        a = self.answers[min(self.calls - 1, len(self.answers) - 1)]
        if isinstance(a, Exception):
            raise a
        return a


def _dash():
    return [pi.PakDashboard(id=ID_WORLD, name=NAME, directory="World", entries=ENTRIES)]


def test_poll_stops_when_settled_and_survives_a_transient_error():
    ui = _ListUI([{"id": ID_WORLD, "isLoading": True}],
                 RuntimeError("503 Service Unavailable"),
                 [{"id": ID_WORLD, "isLoading": True}],
                 [{"id": ID_WORLD, "isLoading": False}])
    slept = []
    statuses, _ = pi.check_pak_dashboards(
        ui, _dash(), wait_s=660, poll_s=30, adapter_kinds=lambda: {"vcfcf_compliance"},
        sleep=slept.append)
    assert slept == [30, 30, 30] and ui.calls == 4
    assert [s.state for s in statuses] == [mat.COMPLETE]
    assert statuses[0].checked_after_s == 90


def test_poll_times_out_incomplete():
    ui = _ListUI([{"id": ID_WORLD, "isLoading": True}])
    slept = []
    statuses, _ = pi.check_pak_dashboards(
        ui, _dash(), wait_s=70, poll_s=30, adapter_kinds=lambda: {"vcfcf_compliance"},
        sleep=slept.append)
    assert slept == [30, 30, 10]
    assert [(s.state, s.checked_after_s) for s in statuses] == [(mat.INCOMPLETE, 70)]


# --- end to end through report_pak_dashboards -----------------------------------------------

class _FullUI(_UI):
    def __init__(self, listings, **kw):
        super().__init__(**kw)
        self.listings = list(listings)
        self.list_calls = 0
        self.logged_out = False

    def login(self):
        pass

    def logout(self):
        self.logged_out = True

    def list_dashboards(self):
        self.list_calls += 1
        return self.listings[min(self.list_calls - 1, len(self.listings) - 1)]


def _report(tmp_path, ui, monkeypatch, **kw):
    import vcfcf_dashboards.client as dc

    monkeypatch.setattr(dc, "list_adapter_kind_keys", lambda c: {"vcfcf_compliance"})
    slept = []
    rc = pi.report_pak_dashboards(
        _pak(tmp_path, props="World=vcfcf_compliance:ComplianceWorld\n"),
        host="h", user="u", password="pw", verify_ssl=False,
        ui_factory=lambda *a: ui, suite_factory=lambda *a: object(),
        sleep=slept.append, **kw)
    return rc, slept


def test_report_waits_660_polled_then_rebinds(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("VCFCF_MATERIALIZATION_WAIT_S", raising=False)
    ui = _FullUI(
        [[{"id": ID_WORLD, "isLoading": True}], [{"id": ID_WORLD, "isLoading": False}]],
        tab_answers=[{"tabId": OLD_CLONE}, {"tabId": NEW_CLONE}],
        configs={OLD_CLONE: _config(OLD_CLONE, True, [True] * 7),
                 NEW_CLONE: _config(NEW_CLONE, False, [False] * 7, name=NAME + " 7")})
    rc, slept = _report(tmp_path, ui, monkeypatch, summary_rebind=True)
    out = capsys.readouterr().out
    assert rc == 0 and slept == [30]
    assert ("MATERIALIZATION WAIT: 1 dashboard(s) still building; re-checking every 30 s "
            "for up to 660 s") in out
    assert "MATERIALIZATION OK: 1 of 1" in out
    assert "SUMMARY REBOUND:" in out
    assert ui.assoc[0][0] == {f"resourceKind_{RKID}": f"{NAME}_::_{ID_WORLD}"}
    assert ui.logged_out


def test_report_env_wait_wins_with_rebind(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VCFCF_MATERIALIZATION_WAIT_S", "45")
    ui = _FullUI([[{"id": ID_WORLD, "isLoading": True}]],
                 tab_answers=[{"tabId": OLD_CLONE}],
                 configs={OLD_CLONE: _config(OLD_CLONE, True, [True])})
    rc, slept = _report(tmp_path, ui, monkeypatch, summary_rebind=True)
    assert slept == [30, 15]


@pytest.mark.parametrize("env,expected", [("", [180]), ("45", [45])])
def test_skip_summary_rebind_keeps_the_single_recheck(tmp_path, monkeypatch, capsys, env, expected):
    """Review W2: the 660 s polled wait exists only for the rebind."""
    monkeypatch.setenv("VCFCF_MATERIALIZATION_WAIT_S", env)
    ui = _FullUI([[{"id": ID_WORLD, "isLoading": True}]],
                 tab_answers=[{"tabId": OLD_CLONE}],
                 configs={OLD_CLONE: _config(OLD_CLONE, True, [True])})
    rc, slept = _report(tmp_path, ui, monkeypatch, summary_rebind=False)
    out = capsys.readouterr().out
    assert slept == expected
    assert f"re-checking once in {expected[0]} s" in out
    assert f"SUMMARY INCOMPLETE vcfcf_compliance:ComplianceWorld {OLD_CLONE} (1 of 1 widgets loading)" in out
    assert ui.assoc == []
    assert rc == 0  # information only: neither the source nor the copy changes it


def test_report_unfinished_source_and_blank_clone_exits_3(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VCFCF_MATERIALIZATION_WAIT_S", "0")
    ui = _FullUI([[{"id": ID_WORLD, "isLoading": True}]],
                 tab_answers=[{"tabId": OLD_CLONE}],
                 configs={OLD_CLONE: _config(OLD_CLONE, True, [True])})
    rc, _ = _report(tmp_path, ui, monkeypatch, summary_rebind=True)
    err = capsys.readouterr().err
    assert rc == pi.POST_INSTALL_FAILED_RC and ui.assoc == []
    assert "WARNING: MATERIALIZATION INCOMPLETE:" in err
    assert "WARNING: SUMMARY NOT REBOUND:" in err


# --- pak fixture --------------------------------------------------------------------------

def _pak(tmp_path, props=None, extra_dir=None, two_in_world=False) -> Path:
    p = tmp_path / "x.pak"
    world = [{"id": ID_WORLD, "namePath": "VCF Content Factory",
              "name": f"VCF Content Factory/{NAME}"}]
    if two_in_world:
        world.append({"id": ID_OTHER, "name": "Second"})
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("content/dashboards/World/dashboard.json",
                   json.dumps({"entries": ENTRIES, "dashboards": world, "uuid": "u"}))
        if extra_dir:
            z.writestr(f"content/dashboards/{extra_dir}/dashboard.json", json.dumps(
                {"entries": {}, "dashboards": [{"id": ID_OTHER, "name": "T"}], "uuid": "u"}))
        if props is not None:
            z.writestr("content/dashboards/dashboards.properties", props)
    return p


# --- repair on by default since #260 (the bind goes out in the form each build reads) ---

def test_repair_is_on_by_default(tmp_path, monkeypatch, capsys):
    """#200: with no switch the install waits for the source, then binds an
    unfinished copy again; the server's clone-before-build order is undone."""
    monkeypatch.delenv("VCFCF_MATERIALIZATION_WAIT_S", raising=False)
    ui = _FullUI([[{"id": ID_WORLD, "isLoading": False}]],
                 tab_answers=[{"tabId": OLD_CLONE}, {"tabId": NEW_CLONE}],
                 configs={OLD_CLONE: _config(OLD_CLONE, True, [True] * 7),
                          NEW_CLONE: _config(NEW_CLONE, False, [False] * 7, name=NAME + " 8")})
    rc, _ = _report(tmp_path, ui, monkeypatch)
    out = capsys.readouterr().out
    assert rc == 0
    assert ui.assoc[0][0] == {f"resourceKind_{RKID}": f"{NAME}_::_{ID_WORLD}"}
    assert f"SUMMARY REBOUND: vcfcf_compliance:ComplianceWorld now shows copy {NEW_CLONE}" in out


def test_turned_off_is_information_only(tmp_path, monkeypatch, capsys):
    """Repair turned off: no long wait, no write, exit code untouched, one
    SUMMARY line per bound kind with the copy id and the loading count."""
    monkeypatch.delenv("VCFCF_MATERIALIZATION_WAIT_S", raising=False)
    ui = _FullUI([[{"id": ID_WORLD, "isLoading": False}]],
                 tab_answers=[{"tabId": OLD_CLONE}],
                 configs={OLD_CLONE: _config(OLD_CLONE, True, [True] * 7)})
    rc, slept = _report(tmp_path, ui, monkeypatch, summary_rebind=False)
    out = capsys.readouterr().out
    assert rc == 0 and slept == [] and ui.assoc == []
    assert (f"SUMMARY INCOMPLETE vcfcf_compliance:ComplianceWorld {OLD_CLONE} "
            f"(7 of 7 widgets loading)") in out
    assert "--skip-summary-rebind or VCFCF_SUMMARY_REBIND=0" in out


def _info(ui):
    lines = []
    pi.report_summary_copies(ui, [_binding()], out=lines.append)
    return lines


def test_info_ok_line():
    ui = _UI([{"tabId": NEW_CLONE, "isDashboard": True}],
             {NEW_CLONE: _config(NEW_CLONE, False, [False] * 7, name=NAME + " 4")})
    assert _info(ui) == [
        f"SUMMARY OK vcfcf_compliance:ComplianceWorld {NEW_CLONE} (0 of 7 widgets loading)"]
    assert ui.assoc == []


@pytest.mark.parametrize("answer,configs,needle", [
    ({"isDashboard": False}, {}, "not bound to a dashboard"),
    ({"tabId": OLD_CLONE}, {OLD_CLONE: {}}, "could not be read"),
    ({"tabId": OLD_CLONE}, {OLD_CLONE: _config(OLD_CLONE, True, [True], name="Other 2")},
     "not a copy of"),
])
def test_info_unchecked_lines(answer, configs, needle):
    ui = _UI([answer], configs)
    lines = _info(ui)
    assert len(lines) == 1 and lines[0].startswith("SUMMARY UNCHECKED vcfcf_compliance:ComplianceWorld")
    assert needle in lines[0] and ui.assoc == []


def test_info_never_raises():
    ui = _UI([{"tabId": OLD_CLONE}], {}, config_raises=True)
    lines = _info(ui)
    assert lines[0].startswith("SUMMARY UNCHECKED") and "HTTP 500" in lines[0]


def test_refused_bind_reports_status_and_redacted_body():
    from vcfcf_dashboards.ui_client import UIClientError

    body = ("\n   <script type=\"text/javascript\">\n   Ext.onReady(function() { var errorPanel "
            "= new Ext.Panel({ secureToken=SECRET-TOKEN-1234 title: 'Internal Server Error', "
            "pw hunter2-pass }); });</script>" + "x" * 400)
    ui = _UI([{"tabId": OLD_CLONE}], {OLD_CLONE: _config(OLD_CLONE, True, [True] * 7)},
             assoc_raises=UIClientError("associateResourceKindDashboards failed (HTTP 200)",
                                        status=200, body=body))
    out, err = [], []
    rc = pi.repair_summary_bindings(ui, [_binding()], _status(mat.COMPLETE),
                                    out=out.append, err=err.append,
                                    secrets=("hunter2-pass",))
    assert rc == pi.POST_INSTALL_FAILED_RC and out == []
    line = err[0]
    assert line.startswith("WARNING: SUMMARY NOT REBOUND: vcfcf_compliance:ComplianceWorld")
    assert f"unfinished copy {OLD_CLONE}" in line
    assert "Server answer: HTTP 200: '<script type=\"text/javascript\"> Ext.onReady" in line
    assert "Internal Server Error" in line
    assert "SECRET-TOKEN-1234" not in line and "hunter2-pass" not in line
    assert "x" * 201 not in line  # excerpt capped at 200 characters


def test_server_answer_reads_a_requests_error():
    class _Resp:
        status_code = 503
        text = "  Service   Unavailable  password=abc12345 "

    exc = RuntimeError("boom")
    exc.response = _Resp()
    assert pi.server_answer(exc) == "HTTP 503: 'Service Unavailable password=<redacted>'"
    assert pi.server_answer(RuntimeError("no reply")) is None


def test_ui_client_associate_failure_carries_status_and_body():
    from vcfcf_dashboards.ui_client import UIClientError, VCFOpsUIClient

    class _Resp:
        status_code = 200
        text = "<html>Internal Server Error</html>"

    class _Session:
        posts = 0

        def post(self, *a, **k):
            self.posts += 1
            return _Resp()

    c = VCFOpsUIClient(host="ops.example", username="u", password="p")
    session = _Session()
    c._session, c._csrf_token = session, "tok"
    with pytest.raises(UIClientError) as exc:
        c.associate_resource_kind_dashboards({"resourceKind_x": "N_::_u"}, {})
    # no error-panel marker: not the proven wrong-form answer, so no second write
    assert session.posts == 1
    assert exc.value.status == 200
    assert exc.value.body == "[two-map] <html>Internal Server Error</html>"
    assert exc.value.answers == [("two-map", 200, "<html>Internal Server Error</html>")]
    assert "HTTP 200" in str(exc.value)


@pytest.mark.parametrize("argv,env,expected", [
    ([], "", True),
    (["--summary-rebind"], "", True),
    ([], "1", True),
    ([], "no", False),
    ([], "0", False),
    ([], "OFF", False),
    (["--summary-rebind"], "0", True),
    (["--skip-summary-rebind"], "", False),
    (["--skip-summary-rebind"], "1", False),
])
def test_cli_summary_rebind_switch(monkeypatch, capsys, argv, env, expected):
    from vcfcf_managementpacks import cli as mp_cli
    from vcfcf_managementpacks import installer

    seen = {}
    monkeypatch.setenv("VCFCF_SUMMARY_REBIND", env)
    monkeypatch.setattr(installer, "install_pak", lambda **kw: seen.update(kw) or 0)
    assert mp_cli.main(["install", "x.pak", *argv]) == 0
    assert seen["summary_rebind"] is expected
    assert "deprecated" not in capsys.readouterr().err


def test_cli_both_switches_is_a_usage_error(monkeypatch, capsys):
    from vcfcf_managementpacks import cli as mp_cli
    from vcfcf_managementpacks import installer

    monkeypatch.setattr(installer, "install_pak",
                        lambda **kw: pytest.fail("must not install on a usage error"))
    assert mp_cli.main(["install", "x.pak", "--summary-rebind", "--skip-summary-rebind"]) == 2
    assert "contradict" in capsys.readouterr().err


# --- #260 review: read back after a non-ok answer, name the request form -----------------

class _FormUI(_UI):
    association_form = "single-map"


def test_rebound_line_names_the_request_form():
    ui = _FormUI([{"tabId": OLD_CLONE}, {"tabId": NEW_CLONE}],
                 {OLD_CLONE: _config(OLD_CLONE, True, [True] * 7),
                  NEW_CLONE: _config(NEW_CLONE, False, [False] * 7, name=NAME + " 8")})
    rc, out, err = _repair(ui)
    assert rc == 0 and err == []
    assert out[0].startswith("SUMMARY REBOUND:") and "(request form: single-map)" in out[0]


def test_non_ok_answer_with_a_moved_tab_is_rebound_not_refused():
    """The single-map success body is unread: a non-ok answer whose readback
    shows a new copy was written, and is reported as such (W1)."""
    from vcfcf_dashboards.ui_client import UIClientError

    exc = UIClientError("not ok", status=200, body="[two-map] panel | [single-map] done")
    exc.answers = [("two-map", 200, "panel"), ("single-map", 200, "done")]
    ui = _UI([{"tabId": OLD_CLONE}, {"tabId": NEW_CLONE}],
             {OLD_CLONE: _config(OLD_CLONE, True, [True] * 7),
              NEW_CLONE: _config(NEW_CLONE, False, [False] * 7, name=NAME + " 8")},
             assoc_raises=exc)
    rc, out, err = _repair(ui)
    assert rc == 0 and err == []
    assert out[0].startswith("SUMMARY REBOUND:")
    assert "was not answered ok" in out[0] and "so it was written" in out[0]
    assert "(request forms tried: two-map, single-map)" in out[0]


def test_non_ok_answer_and_unreadable_tab_is_not_rebound():
    from vcfcf_dashboards.ui_client import UIClientError

    class _Flaky(_UI):
        reads = 0

        def get_summary_tab_id(self, rkid):
            self.reads += 1
            if self.reads > 1:
                raise RuntimeError("HTTP 503")
            return super().get_summary_tab_id(rkid)

    ui = _Flaky([{"tabId": OLD_CLONE}], {OLD_CLONE: _config(OLD_CLONE, True, [True] * 7)},
                assoc_raises=UIClientError("not ok", status=502, body="Bad Gateway"))
    rc, out, err = _repair(ui)
    assert rc == pi.POST_INSTALL_FAILED_RC and out == []
    assert err[0].startswith("WARNING: SUMMARY NOT REBOUND:")
    assert "could not be read back" in err[0] and "is unknown" in err[0]
    assert "HTTP 502" in err[0]


def test_cli_unrecognised_env_value_warns_and_stays_on(monkeypatch, capsys):
    from vcfcf_managementpacks import cli as mp_cli
    from vcfcf_managementpacks import installer

    seen = {}
    monkeypatch.setenv("VCFCF_SUMMARY_REBIND", "fasle")
    monkeypatch.setattr(installer, "install_pak", lambda **kw: seen.update(kw) or 0)
    assert mp_cli.main(["install", "x.pak"]) == 0
    assert seen["summary_rebind"] is True
    err = capsys.readouterr().err
    assert "VCFCF_SUMMARY_REBIND='fasle'" in err and "stays on" in err
