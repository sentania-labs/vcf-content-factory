"""Summary binding per build line (#260) and the still-building refusal (#256).

#260: 9.0.2 Build 25429562 and 8.18.6 Build 25423535 read one
``dashboardAssociations`` map; 9.1.1 and 9.2 read ``assignedAssociations``
plus ``resetAssociations``. Each build NPEs before any write when its
parameter is absent and answers HTTP 200 with the generic error panel, so
the client sends the two-map form, then the single-map form on a non-``ok``
answer. 9.0.2 answers ``getSummaryTabId`` without ``isDashboard``.
Evidence: knowledge/context/investigations/2026-10-24-devel-summary-rebind-500-and-alertlist-gap.md.

#256: bind-summary reads the dashboard list first and refuses a source that
is still building (or whose state is not reported), naming its unfinished
widgets; ``--wait`` polls like the pak install path.

No live instance: every answer is faked.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from test_dashboard_summary_for import FakeUI, _load  # noqa: E402

NAME = "[VCF Content Factory] Host Summary"
UUID = "12345678-1234-4123-8123-123456789abc"
KEY = "resourceKind_002006VMWAREHostSystem"
NEW = "aaaaaaaa-1111-4222-8333-444444444444"
ERRPANEL = ("\n   <script type=\"text/javascript\">\n      Ext.onReady(function() {\n"
            "         var errorPanel = new Ext.Panel({ title: 'Internal Server Error' });")


# --- the UI client: one call, the form each build reads ------------------------------

class _Resp:
    def __init__(self, status, text):
        self.status_code = status
        self.text = text


class _Session:
    """Answers ``ok`` only to the form the faked build reads."""

    def __init__(self, reads, status_on_refusal=200):
        self.reads = reads  # "two-map" or "single-map"
        self.status_on_refusal = status_on_refusal
        self.posts = []

    def post(self, url, data=None, headers=None, **kw):
        self.posts.append(dict(data))
        has_two = "assignedAssociations" in data and "resetAssociations" in data
        has_one = "dashboardAssociations" in data
        ok = has_two if self.reads == "two-map" else has_one
        if ok:
            return _Resp(200, "ok")
        return _Resp(self.status_on_refusal, ERRPANEL)


def _client(session):
    from vcfcf_dashboards.ui_client import VCFOpsUIClient

    c = VCFOpsUIClient(host="ops.example", username="u", password="p")
    c._session, c._csrf_token = session, "tok"
    return c


def test_two_map_build_takes_one_call():
    s = _Session("two-map")
    c = _client(s)
    c.associate_resource_kind_dashboards({KEY: f"{NAME}_::_{UUID}"}, {})
    assert len(s.posts) == 1
    assert json.loads(s.posts[0]["assignedAssociations"]) == {KEY: f"{NAME}_::_{UUID}"}
    assert json.loads(s.posts[0]["resetAssociations"]) == {}
    assert "dashboardAssociations" not in s.posts[0]
    assert c.association_form == "two-map"


def test_single_map_build_falls_back_and_remembers():
    """9.0.2 / 8.18: the two-map call NPEs (nothing written), the single-map
    call answers ok; the next call goes straight to the single-map form."""
    s = _Session("single-map")
    c = _client(s)
    c.associate_resource_kind_dashboards({KEY: f"{NAME}_::_{UUID}"}, {})
    assert len(s.posts) == 2
    second = s.posts[1]
    assert set(second) == {"mainAction", "dashboardAssociations", "secureToken"}
    assert json.loads(second["dashboardAssociations"]) == {KEY: f"{NAME}_::_{UUID}"}
    assert second["mainAction"] == "associateResourceKindDashboards"
    assert c.association_form == "single-map"

    c.associate_resource_kind_dashboards({}, {KEY: "Host System Summary"})
    assert len(s.posts) == 3
    assert json.loads(s.posts[2]["dashboardAssociations"]) == {
        KEY: "Host System Summary_::_null"}


def test_remembered_form_that_stops_working_still_falls_back():
    s = _Session("two-map")
    c = _client(s)
    c.association_form = "single-map"
    c.associate_resource_kind_dashboards({KEY: f"{NAME}_::_{UUID}"}, {})
    assert [("dashboardAssociations" in p) for p in s.posts] == [True, False]
    assert c.association_form == "two-map"


@pytest.mark.parametrize("status,text", [
    (500, ERRPANEL),                                   # not HTTP 200
    (502, "Bad Gateway"),                              # proxy: the server may have written
    (401, "Unauthorized"),
    (200, "<html><form id='loginForm'>"),              # expired session: login page
])
def test_only_the_200_error_panel_falls_back(status, text):
    """Retry safety is proven only for the HTTP 200 NPE panel (#260 review
    W2): anything else raises after one write, never sending the other form."""
    from vcfcf_dashboards.ui_client import UIClientError

    class _Answer(_Session):
        def post(self, url, data=None, headers=None, **kw):
            self.posts.append(dict(data))
            return _Resp(status, text)

    s = _Answer("single-map")
    c = _client(s)
    with pytest.raises(UIClientError) as exc:
        c.associate_resource_kind_dashboards({KEY: f"{NAME}_::_{UUID}"}, {})
    assert len(s.posts) == 1 and "assignedAssociations" in s.posts[0]
    assert exc.value.status == status
    assert [a[0] for a in exc.value.answers] == ["two-map"]
    assert c.association_form is None


def test_both_forms_refused_keeps_every_answer():
    from vcfcf_dashboards.ui_client import UIClientError

    class _Never(_Session):
        def post(self, url, data=None, headers=None, **kw):
            self.posts.append(dict(data))
            return _Resp(200, ERRPANEL if len(self.posts) == 1 else ERRPANEL + " second")

    s = _Never("two-map")
    c = _client(s)
    with pytest.raises(UIClientError) as exc:
        c.associate_resource_kind_dashboards({KEY: f"{NAME}_::_{UUID}"}, {})
    assert len(s.posts) == 2
    assert exc.value.status == 200
    assert exc.value.body.startswith("[two-map] <script")
    assert "| [single-map] <script" in exc.value.body
    assert exc.value.answers[1][2].endswith("second")
    assert [a[0] for a in exc.value.answers] == ["two-map", "single-map"]
    assert "two-map HTTP 200, single-map HTTP 200" in str(exc.value)
    assert c.association_form is None


def test_association_params_per_form():
    from vcfcf_dashboards.ui_client import association_params

    two = association_params("two-map", {"a": "N_::_u"}, {"b": "Default"})
    assert json.loads(two["assignedAssociations"]) == {"a": "N_::_u"}
    assert json.loads(two["resetAssociations"]) == {"b": "Default"}
    one = association_params("single-map", {"a": "N_::_u"}, {"b": "Default"})
    assert list(one) == ["dashboardAssociations"]
    assert json.loads(one["dashboardAssociations"]) == {"a": "N_::_u", "b": "Default_::_null"}
    with pytest.raises(ValueError):
        association_params("three-map", {}, {})


def test_bind_and_reset_of_one_kind_is_refused_before_any_call():
    s = _Session("two-map")
    c = _client(s)
    with pytest.raises(ValueError):
        c.associate_resource_kind_dashboards({KEY: "N_::_u"}, {KEY: "Default"})
    assert s.posts == []


# --- getSummaryTabId shapes per build ---------------------------------------------------

@pytest.mark.parametrize("answer,expected", [
    ({"tabId": NEW, "isDashboard": True}, NEW),          # 9.1.1, 9.2
    ({"tabId": NEW}, NEW),                               # 9.0.2: no isDashboard key
    ({"tabId": "hostSummaryTab"}, None),                 # no key, not a template id
    ({"tabId": "legacy", "isDashboard": False, "pluginExist": True}, None),
    ({"isDashboard": False}, None),
    ({}, None),                                          # 9.0.2 built-in page
    ("not json", None),
])
def test_summary_dashboard_tab(answer, expected):
    from vcfcf_core.dashboards.summary_bind import summary_dashboard_tab

    assert summary_dashboard_tab(answer) == expected


class _Pre91UI(FakeUI):
    """9.0.2 readback shape: a bound kind answers ``{"tabId"}`` only."""

    def get_summary_tab_id(self, resource_kind_id):
        answer = super().get_summary_tab_id(resource_kind_id)
        answer.pop("isDashboard", None)
        return answer


def test_bind_succeeds_on_the_9_0_2_readback_shape(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    ui = _Pre91UI(installed={NAME: UUID}, current_template=NAME)
    ui.association_form = "single-map"
    lines = []
    rc = bind_summary(ui, [_load(tmp_path)], out=lines.append)
    assert rc == 0, lines
    assert any("wrote assignedAssociations" in l and "(single-map request form)" in l
               for l in lines)
    assert any(f"template UUID: {NEW}" in l for l in lines)


def test_unbind_on_the_9_0_2_readback_shape(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    ui = _Pre91UI(installed={NAME: UUID}, current_template=NAME)
    rc = bind_summary(ui, [_load(tmp_path)], unbind=True, out=lambda s: None)
    assert rc == 0


def test_ok_that_leaves_the_tab_unchanged_is_an_error(tmp_path):
    """Pre-9.1 skips a dashboard the session user cannot see and still
    answers ok; the Summary tab keeps the copy it had."""
    from vcfcf_dashboards.summary_bind import bind_summary

    class _Skips(FakeUI):
        def associate_resource_kind_dashboards(self, assigned, reset=None):
            self.calls.append(("associate", dict(assigned), dict(reset or {})))

    ui = _Skips(installed={NAME: UUID}, current_template=NAME)
    lines = []
    rc = bind_summary(ui, [_load(tmp_path)], out=lines.append)
    assert rc == 2
    assert any("still shows old-copy-uuid" in l and "did not take" in l for l in lines)


# --- #256: refuse a source still building ------------------------------------------------

_BUILDING = [
    {"id": "w1", "key": "Scoreboard", "title": "Environment Compliance", "isLoading": True},
    {"id": "w2", "key": "View", "title": "", "isLoading": True},
    {"id": "w3", "key": "AlertList", "title": "Alerts", "isLoading": False},
]


def test_building_source_is_refused_naming_its_widgets(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    ui = FakeUI(installed={NAME: UUID}, loading=True, widgets=_BUILDING)
    lines = []
    rc = bind_summary(ui, [_load(tmp_path)], out=lines.append)
    assert rc == 2
    assert not any(c[0] == "associate" for c in ui.calls)
    err = next(l for l in lines if "ERROR" in l)
    assert NAME in err and UUID in err and "still building" in err
    assert "'Environment Compliance', 'View'" in err and "'Alerts'" not in err
    assert "--wait" in err
    assert ("get_dashboard_config", UUID, False) in ui.calls


def test_widget_still_loading_under_a_built_list_entry_is_refused(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    ui = FakeUI(installed={NAME: UUID}, loading=False, widgets=_BUILDING)
    rc = bind_summary(ui, [_load(tmp_path)], out=lambda s: None)
    assert rc == 2 and not any(c[0] == "associate" for c in ui.calls)


def test_missing_isloading_fails_closed(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    ui = FakeUI(installed={NAME: UUID}, loading=None)
    lines = []
    rc = bind_summary(ui, [_load(tmp_path)], out=lines.append)
    assert rc == 2 and not any(c[0] == "associate" for c in ui.calls)
    assert any("carries no isLoading flag" in l for l in lines)


def test_unreadable_config_leaves_the_list_answer(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    class _NoConfig(FakeUI):
        def get_dashboard_config(self, tab_id, *, is_template=False):
            raise RuntimeError("HTTP 500")

    ui = _NoConfig(installed={NAME: UUID}, loading=False)
    assert bind_summary(ui, [_load(tmp_path)], out=lambda s: None) == 0
    ui = _NoConfig(installed={NAME: UUID}, loading=True)
    lines = []
    assert bind_summary(ui, [_load(tmp_path)], out=lines.append) == 2
    assert any("its unfinished widgets could not be read" in l for l in lines)


def test_two_dashboards_with_the_name_are_refused(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    ui = FakeUI(installed={NAME: UUID, f"Other Folder/{NAME}": "99999999-0000-4000-8000-000000000009"})
    lines = []
    rc = bind_summary(ui, [_load(tmp_path)], out=lines.append)
    assert rc == 2 and not any(c[0] == "associate" for c in ui.calls)
    err = next(l for l in lines if "ERROR" in l)
    assert UUID in err and "99999999-0000-4000-8000-000000000009" in err


class _Settles(FakeUI):
    """``loading`` per list call (the last value repeats); raises on the
    calls named in ``fail_on`` (1-based)."""

    def __init__(self, sequence, fail_on=(), **kw):
        super().__init__(loading=sequence[0], **kw)
        self.sequence = list(sequence)
        self.fail_on = set(fail_on)
        self.list_calls = 0

    def list_dashboards(self):
        self.list_calls += 1
        if self.list_calls in self.fail_on:
            raise RuntimeError("HTTP 503")
        self.loading = self.sequence[min(self.list_calls - 1, len(self.sequence) - 1)]
        return super().list_dashboards()


def test_wait_polls_until_built_then_binds(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    ui = _Settles([True, True, True, False], fail_on={2}, installed={NAME: UUID})
    slept, lines = [], []
    rc = bind_summary(ui, [_load(tmp_path)], wait=True, sleep=slept.append, out=lines.append)
    assert rc == 0, lines
    # call 1 refuses, call 2 is a transient error, call 3 still building, call 4 built
    assert slept == [30, 30, 30]
    assert any("could not read the dashboard list" in l for l in lines)
    assert [c for c in ui.calls if c[0] == "associate"] == [
        ("associate", {KEY: f"{NAME}_::_{UUID}"}, {})]


def test_wait_times_out_without_writing(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    ui = _Settles([True], installed={NAME: UUID})
    slept, lines = [], []
    rc = bind_summary(ui, [_load(tmp_path)], wait=True, wait_s=75, sleep=slept.append,
                      out=lines.append)
    assert rc == 2
    assert slept == [30, 30, 15]
    assert not any(c[0] == "associate" for c in ui.calls)
    assert any("still building" in l and "after 75 s" in l for l in lines)


def test_unbind_does_not_check_the_source(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    ui = FakeUI(installed={NAME: UUID}, current_template=NAME, loading=True)
    assert bind_summary(ui, [_load(tmp_path)], unbind=True, out=lambda s: None) == 0


def test_cli_wait_flags():
    from vcfcf_dashboards.cli import build_parser

    args = build_parser().parse_args(["bind-summary", "--wait", "--wait-timeout", "120"])
    assert args.wait is True and args.wait_timeout == 120
    args = build_parser().parse_args(["bind-summary"])
    assert args.wait is False and args.wait_timeout is None
    assert build_parser().parse_args(["bind-summary", "--wait-timeout", "900"]).wait_timeout == 900
    for bad in ("-1", "901", "x"):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["bind-summary", "--wait-timeout", bad])


def _cli_run(monkeypatch, argv, *, login_error=None):
    import vcfcf_dashboards.cli as dcli

    seen = {}

    class _UIClient:
        def login(self):
            if login_error is not None:
                raise login_error

        def logout(self):
            pass

    monkeypatch.setattr(dcli, "_load", lambda args: ([], ["d"]))
    monkeypatch.setattr(dcli.VCFOpsUIClient, "from_env",
                        classmethod(lambda cls, profile=None, default_profile="devel": _UIClient()))
    monkeypatch.setattr(dcli, "bind_summary",
                        lambda ui, d, **kw: seen.update(kw) or 0)
    return dcli.main(["bind-summary", *argv]), seen


def test_cli_wait_timeout_without_wait_warns(monkeypatch, capsys):
    rc, seen = _cli_run(monkeypatch, ["--wait-timeout", "30"])
    assert rc == 0 and seen["wait"] is False
    assert "--wait-timeout has no effect without --wait" in capsys.readouterr().err
    rc, seen = _cli_run(monkeypatch, ["--wait"])
    assert seen["wait_s"] == 660


def test_cli_login_transport_error_is_exit_2(monkeypatch, capsys):
    import requests

    rc, seen = _cli_run(monkeypatch, [], login_error=requests.ConnectionError("refused"))
    assert rc == 2 and seen == {}
    assert "FAILED (UI login)" in capsys.readouterr().err


# --- #260 review W1: a non-ok answer is read back before it is called a refusal -----------

def test_non_ok_answer_with_a_moved_tab_is_a_written_bind(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary
    from vcfcf_dashboards.ui_client import UIClientError

    class _WritesButNotOk(FakeUI):
        def associate_resource_kind_dashboards(self, assigned, reset=None):
            self.associate_error = None
            super().associate_resource_kind_dashboards(assigned, reset)
            raise UIClientError("not ok (single-map HTTP 200)", status=200, body="done")

    ui = _WritesButNotOk(installed={NAME: UUID}, current_template=NAME)
    lines = []
    rc = bind_summary(ui, [_load(tmp_path)], out=lines.append)
    assert rc == 0, lines
    assert any("WARNING" in l and "the write happened" in l for l in lines)
    assert any(f"template UUID: {NEW}" in l for l in lines)


def test_unreadable_tab_after_a_non_ok_answer_is_an_error(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary
    from vcfcf_dashboards.ui_client import UIClientError

    class _Blind(FakeUI):
        def get_summary_tab_id(self, resource_kind_id):
            if any(c[0] == "associate" for c in self.calls):
                raise RuntimeError("HTTP 503")
            return super().get_summary_tab_id(resource_kind_id)

    ui = _Blind(installed={NAME: UUID}, associate_error=UIClientError("not ok"))
    lines = []
    assert bind_summary(ui, [_load(tmp_path)], out=lines.append) == 2
    assert any("could not be read back" in l and "is unknown" in l for l in lines)


def test_a_refused_dashboard_does_not_stop_the_run(tmp_path):
    """#260 review N10: a refusal skips that dashboard only."""
    from vcfcf_dashboards.loader import load_dashboard
    from vcfcf_dashboards.summary_bind import bind_summary
    from vcfcf_dashboards.ui_client import UIClientError
    from test_dashboard_summary_for import _summary_dash, _write

    other = "[VCF Content Factory] VM Summary"
    a = _load(tmp_path)
    b = load_dashboard(_write(tmp_path / "b.yaml", _summary_dash(
        name=other, summary_for="VMWARE:VirtualMachine",
        dash_id="1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")))
    b.validate({})

    class _RefusesFirst(FakeUI):
        def associate_resource_kind_dashboards(self, assigned, reset=None):
            n = sum(1 for c in self.calls if c[0] == "associate")
            self.associate_error = UIClientError("refused") if n == 0 else None
            super().associate_resource_kind_dashboards(assigned, reset)

    ui = _RefusesFirst(installed={NAME: UUID, other: "22222222-2222-4222-8222-222222222222"})
    lines = []
    assert bind_summary(ui, [a, b], out=lines.append) == 2
    assert sum(1 for c in ui.calls if c[0] == "associate") == 2
    assert any("VMWARE:VirtualMachine  template UUID:" in l for l in lines)


# --- #260 review W3, N3, N4, N10: wait diagnosis, flag reading, poll guard, run budget ------

def test_wait_ending_on_failed_reads_names_the_failure(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    ui = _Settles([True], fail_on={2, 3, 4}, installed={NAME: UUID})
    lines = []
    rc = bind_summary(ui, [_load(tmp_path)], wait=True, wait_s=90, sleep=lambda s: None,
                      out=lines.append)
    assert rc == 2
    err = [l for l in lines if "ERROR" in l][-1]
    assert "could not be confirmed built after 90 s" in err
    assert "the last read of the dashboard list failed (HTTP 503)" in err
    assert "isLoading: true;" not in err


def test_wait_ending_with_the_dashboard_gone_names_that(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    class _Gone(_Settles):
        def list_dashboards(self):
            out = super().list_dashboards()
            return out if self.list_calls == 1 else []

    ui = _Gone([True], installed={NAME: UUID})
    lines = []
    assert bind_summary(ui, [_load(tmp_path)], wait=True, wait_s=60, sleep=lambda s: None,
                        out=lines.append) == 2
    assert any(f"{UUID} was not in the dashboard list at the last read" in l
               for l in lines if "ERROR" in l)


def test_wait_budget_is_for_the_whole_run(tmp_path):
    from vcfcf_dashboards.loader import load_dashboard
    from vcfcf_dashboards.summary_bind import bind_summary
    from test_dashboard_summary_for import _summary_dash, _write

    other = "[VCF Content Factory] VM Summary"
    b = load_dashboard(_write(tmp_path / "b.yaml", _summary_dash(
        name=other, summary_for="VMWARE:VirtualMachine",
        dash_id="1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")))
    b.validate({})
    ui = _Settles([True], installed={NAME: UUID, other: "22222222-2222-4222-8222-222222222222"})
    slept = []
    rc = bind_summary(ui, [_load(tmp_path), b], wait=True, wait_s=60, sleep=slept.append,
                      out=lambda s: None)
    assert rc == 2 and sum(slept) == 60


@pytest.mark.parametrize("value,expected", [
    (True, True), (False, False), ("true", True), ("FALSE", False),
    (None, None), ("maybe", None), (1, None),
])
def test_loading_flag(value, expected):
    from vcfcf_core.dashboards.summary_bind import loading_flag, source_loading

    assert loading_flag(value) is expected
    assert source_loading({"isLoading": value}) is expected
    assert source_loading({}) is None


def test_loading_widgets_reads_string_flags():
    from vcfcf_core.dashboards.summary_bind import loading_widgets

    cfg = {"dashboardConfig": {"tabConfigs": [{"id": UUID, "widgets": [
        {"title": "A", "isLoading": "true"}, {"title": "B", "isLoading": "false"}]}]}}
    assert loading_widgets(cfg, UUID) == ["A"]


def test_null_isloading_is_refused(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    class _Null(FakeUI):
        def list_dashboards(self):
            return [dict(e, isLoading=None) for e in super().list_dashboards()]

    ui = _Null(installed={NAME: UUID})
    assert bind_summary(ui, [_load(tmp_path)], out=lambda s: None) == 2
    assert not any(c[0] == "associate" for c in ui.calls)


def test_wait_needs_a_positive_poll(tmp_path):
    from vcfcf_dashboards.summary_bind import bind_summary

    with pytest.raises(ValueError):
        bind_summary(FakeUI(installed={NAME: UUID}), [_load(tmp_path)], wait=True, poll_s=0,
                     out=lambda s: None)
