"""delete-dashboard verifies by re-listing: HTTP 200 from deleteTab is not a delete.

Measured (knowledge/context/investigations/
2026-11-18-dashboard-import-by-name-and-delete-noop.md): on 9.1.1, with the
session another administrator account and the dashboards owned by the
built-in admin account, ``deleteTab`` answered 200 and deleted nothing, and
the CLI used to print "done" and exit 0. Fakes only; the probe cases of the
framework review (P1 to P5) are here as tests.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vcfcf_dashboards import cli  # noqa: E402
from vcfcf_dashboards import handler as handler_mod  # noqa: E402
from vcfcf_dashboards.ui_client import (  # noqa: E402
    UIClientError,
    VCFOpsUIClient,
    _dashboards_from_body,
    dashboard_delete_blockers,
)

U1 = "11111111-1111-1111-1111-111111111111"
U2 = "22222222-2222-2222-2222-222222222222"
U3 = "33333333-3333-3333-3333-333333333333"
ME = "svc-factory"


class FakeUI:
    """deleteTab answers 200 always; only ids in *deletable* go away.

    *after*: what every listing after the first returns instead of the real
    state (a list, or an exception instance to raise).
    """

    def __init__(self, dashboards, deletable, after=None, username=ME):
        self.dashboards = [dict(d) for d in dashboards]
        self.deletable = set(deletable)
        self.after = after
        self.username = username
        self.sent = []
        self.lists = 0
        self.logged_out = False

    def login(self):
        pass

    def logout(self):
        self.logged_out = True

    def list_dashboards_strict(self):
        self.lists += 1
        if self.lists > 1 and self.after is not None:
            if isinstance(self.after, Exception):
                raise self.after
            return [dict(d) for d in self.after]
        return [dict(d) for d in self.dashboards]

    list_dashboards = list_dashboards_strict

    def delete_dashboards(self, targets):
        self.sent.append(list(targets))
        ids = {t[0] for t in targets}
        self.dashboards = [d for d in self.dashboards
                           if not (d["id"] in ids and d["id"] in self.deletable)]
        return {}

    def delete_dashboards_verified(self, targets, before=None):
        return VCFOpsUIClient.delete_dashboards_verified(self, targets, before=before)


def _mine(uid, name, **kw):
    return {"id": uid, "name": name, "owner": ME, "locked": False, "edit": True, **kw}


def _theirs(uid, name):
    # The listing of the failing case (9.1.1): another owner, locked, edit false.
    return {"id": uid, "name": name, "owner": "admin", "locked": True, "edit": False,
            "editable": False, "shared": False}


@pytest.fixture
def run_cli(monkeypatch):
    from vcfcf_common import _env
    monkeypatch.setattr(_env, "_LOADED", True)  # never read a real .env

    def _run(fake, targets, dry_run=False, all_copies=False, session_user=ME):
        monkeypatch.setattr(cli.VCFOpsUIClient, "from_env",
                            classmethod(lambda cls, **kw: fake))
        monkeypatch.setattr(cli, "_session_user", lambda p, d: session_user)
        args = SimpleNamespace(targets=targets, dry_run=dry_run, all_copies=all_copies,
                               profile=None, _profile_default="devel")
        return cli.cmd_delete_dashboard(args)
    return _run


# --------------------------------------------------------------------------
# Strict listing (B1)
# --------------------------------------------------------------------------

class _Resp:
    def __init__(self, body=None, bad_json=False):
        self._body, self._bad = body, bad_json
        self.status_code, self.text = 200, "<html>"

    def json(self):
        if self._bad:
            raise ValueError("Expecting value")
        return self._body


@pytest.mark.parametrize("resp", [
    _Resp(bad_json=True), _Resp({}), _Resp({"dashboards": None}),
    _Resp({"dashboards": {}}), _Resp([]),
])
def test_strict_listing_refuses_what_it_cannot_read(resp):
    with pytest.raises(UIClientError):
        _dashboards_from_body(resp)


def test_strict_listing_accepts_an_empty_list():
    assert _dashboards_from_body(_Resp({"dashboards": []})) == []


def test_p1_after_listing_that_lost_other_dashboards_is_not_trusted(run_cli, capsys):
    """Probe P1: nothing deleted, after-listing degrades to []: was rc 0."""
    fake = FakeUI([_mine(U1, "D"), _mine(U2, "E")], deletable=[], after=[])
    assert run_cli(fake, [U1]) == 1
    cap = capsys.readouterr()
    assert "deleted (gone" not in cap.out
    assert "NOT VERIFIED (the listing after the delete lost 1 dashboard(s)" in cap.err


def test_unreadable_after_listing_is_unverified_not_deleted(run_cli, capsys):
    fake = FakeUI([_mine(U1, "D")], deletable=[U1],
                  after=UIClientError("getDashboardList answer has no 'dashboards' key"))
    assert run_cli(fake, [U1]) == 1
    cap = capsys.readouterr()
    assert "deleted (gone" not in cap.out
    assert "NOT VERIFIED (the listing after the delete could not be read" in cap.err


def test_verified_delete_sorts_ids():
    fake = FakeUI([_mine(U1, "a"), _theirs(U2, "b")], deletable=[U1])
    res = fake.delete_dashboards_verified([(U1, "a"), (U2, "b"), (U3, "c")])
    assert res.deleted == [(U1, "a")]
    assert [e["id"] for e in res.remaining] == [U2]
    assert res.unlisted == [(U3, "c")]
    assert res.unverifiable == [] and not res.ok
    # Every target is still sent.
    assert fake.sent == [[(U1, "a"), (U2, "b"), (U3, "c")]]
    fake = FakeUI([_mine(U1, "a")], deletable=[U1])
    assert fake.delete_dashboards_verified([(U1.upper(), "a")]).ok


# --------------------------------------------------------------------------
# Owner first, lock as context (W4, W5)
# --------------------------------------------------------------------------

def test_blockers_name_the_owner_only():
    assert dashboard_delete_blockers(_mine(U1, "a"), ME) == []
    assert dashboard_delete_blockers(_mine(U1, "a"), "SVC-Factory") == []
    # Owner matches, locked: not a blocker by itself.
    assert dashboard_delete_blockers(_mine(U1, "a", locked=True, edit=False), ME) == []
    assert dashboard_delete_blockers(_theirs(U1, "a"), ME) == [
        "listed owner 'admin' differs from session user 'svc-factory'; on 9.1.1 only "
        "the owner's delete deletes (8.18.7 and 9.0.2 not measured)"]
    # Session user unknown: nothing compared, nothing claimed.
    assert dashboard_delete_blockers(_theirs(U1, "a"), None) == []


def test_p3_owned_and_locked_is_not_warned(run_cli, capsys):
    """Probe P3: owner is the session, locked: true; was warned, deleted fine."""
    fake = FakeUI([_mine(U1, "D", locked=True)], deletable=[U1])
    assert run_cli(fake, [U1]) == 0
    assert "WARNING" not in capsys.readouterr().err


def test_p4_directory_suffix_reads_as_a_name_difference(run_cli, capsys):
    """Probe P4: owner 'jdoe', session 'jdoe@corp.example': worded as a
    listed-owner difference, never as another account."""
    fake = FakeUI([{"id": U1, "name": "D", "owner": "jdoe", "locked": False}],
                  deletable=[U1])
    assert run_cli(fake, [U1], session_user="jdoe@corp.example") == 0
    err = capsys.readouterr().err
    assert "listed owner 'jdoe' differs from session user 'jdoe@corp.example'" in err
    assert "another account" not in err.split("listed owner")[1]


def test_a_200_that_deleted_nothing_exits_non_zero(run_cli, capsys):
    fake = FakeUI([_theirs(U1, "D1"), _theirs(U2, "D2")], deletable=[])
    assert run_cli(fake, [U1, U2]) == 1
    cap = capsys.readouterr()
    assert "done" not in cap.out
    assert "WARNING: 2 target(s) list an owner other than the session user" in cap.err
    assert "NOT DELETED (still listed after the delete, which answered 200): 2" in cap.err
    assert ("likely cause: listed owner 'admin' differs from session user 'svc-factory'; "
            "on 9.1.1 only the owner's delete deletes (8.18.7 and 9.0.2 not measured). "
            "Run the delete on a profile that signs in as 'admin'") in cap.err
    assert "a copy under the same id owned by another account also produces this" in cap.err
    assert "A DASHBOARDS content export, or a listing as the owner, settles it" in cap.err
    assert fake.sent == [[(U1, "D1"), (U2, "D2")]]  # still attempted
    assert fake.logged_out


def test_survivor_owned_by_the_session_never_says_sign_in_as_owner(run_cli, capsys):
    fake = FakeUI([_mine(U1, "D1", locked=True), _mine(U2, "D2")], deletable=[U2])
    assert run_cli(fake, [U1, "D2"]) == 1
    cap = capsys.readouterr()
    assert "deleted (gone from the listing): 1" in cap.out and U2 in cap.out
    assert "cause unknown: the listed owner is the session user" in cap.err
    assert "signs in as" not in cap.err


def test_unknown_session_user_is_said(run_cli, capsys):
    fake = FakeUI([_theirs(U1, "D1")], deletable=[])
    assert run_cli(fake, [U1], session_user=None) == 1
    cap = capsys.readouterr()
    assert "listed owners are not compared" in cap.out
    assert "the session user could not be read" in cap.err
    assert "WARNING" not in cap.err


def test_a_verified_delete_exits_zero(run_cli, capsys):
    fake = FakeUI([_mine(U1, "D1"), _mine(U2, "D2")], deletable=[U1, U2])
    assert run_cli(fake, [U1, "D2"]) == 0
    cap = capsys.readouterr()
    assert "deleted (gone from the listing): 2" in cap.out
    assert cap.err == ""


# --------------------------------------------------------------------------
# Name and id resolution (B2, N2, N3)
# --------------------------------------------------------------------------

def test_p2_a_name_matching_several_copies_is_refused(run_cli, capsys):
    """Probe P2: twins under one name: was one deleted, rc 0, the other kept."""
    fake = FakeUI([_mine(U1, "[VCF CF] D"), _mine(U2, "[VCF CF] D")], deletable=[U1, U2])
    with pytest.raises(SystemExit) as ei:
        run_cli(fake, ["[VCF CF] D"])
    assert ei.value.code == 1
    err = capsys.readouterr().err
    assert f"names 2 dashboards ({U1}, {U2})" in err and "--all-copies" in err
    assert fake.sent == []


def test_all_copies_deletes_every_same_named_dashboard(run_cli, capsys):
    fake = FakeUI([_mine(U1, "[VCF CF] D"), _mine(U2, "[VCF CF] D"), _mine(U3, "Other")],
                  deletable=[U1, U2])
    assert run_cli(fake, ["[VCF CF] D", U1], all_copies=True) == 0
    assert fake.sent == [[(U1, "[VCF CF] D"), (U2, "[VCF CF] D")]]  # deduplicated
    assert [d["id"] for d in fake.dashboards] == [U3]


def test_p5_uuid_in_another_case_takes_the_listed_id_and_name(run_cli):
    """Probe P5 and N2: the uppercase UUID was sent as its own tabName."""
    fake = FakeUI([_mine(U1, "D")], deletable=[U1])
    assert run_cli(fake, [U1.upper()]) == 0
    assert fake.sent == [[(U1, "D")]]


def test_an_unlisted_id_is_flagged_in_dry_run_and_fails_the_run(run_cli, capsys):
    fake = FakeUI([_mine(U1, "D1")], deletable=[U1])
    assert run_cli(fake, [U3], dry_run=True) == 0
    assert "WARNING: 1 target(s) are not listed for this session" in capsys.readouterr().err
    assert fake.sent == []
    assert run_cli(fake, [U3]) == 1
    assert "NOT VERIFIED (not listed for this session before the delete" in \
        capsys.readouterr().err


def test_dry_run_warns_and_sends_nothing(run_cli, capsys):
    fake = FakeUI([_theirs(U1, "D1")], deletable=[U1])
    assert run_cli(fake, [U1], dry_run=True) == 0
    cap = capsys.readouterr()
    assert "Would delete 1 dashboard(s)" in cap.out
    assert "WARNING: 1 target(s)" in cap.err
    assert fake.sent == []


# --------------------------------------------------------------------------
# Bundle uninstall path (handler.py)
# --------------------------------------------------------------------------

def _handler_delete(monkeypatch, fake, names):
    monkeypatch.setattr(handler_mod.VCFOpsUIClient, "from_env",
                        classmethod(lambda cls, **kw: fake))
    monkeypatch.setattr(handler_mod, "get_current_user", lambda s: {"username": ME})
    return handler_mod.DashboardsHandler().delete(names, session=object())


def test_handler_delete_reports_a_200_that_deleted_nothing(monkeypatch):
    fake = FakeUI([_theirs(U1, "A"), _mine(U2, "B")], deletable=[U2])
    res = _handler_delete(monkeypatch, fake, ["A", "B", "Missing"])
    got = {i.name: (i.status, i.message) for i in res.items}
    assert got["B"][0] == "ok"
    assert got["Missing"][0] == "skipped"
    assert got["A"][0] == "failed" and "still listed after the delete" in got["A"][1]
    assert "listed owner 'admin' differs from session user 'svc-factory'" in got["A"][1]
    assert not res.ok


def test_handler_delete_refuses_an_ambiguous_name(monkeypatch):
    fake = FakeUI([_mine(U1, "A"), _mine(U2, "A")], deletable=[U1, U2])
    res = _handler_delete(monkeypatch, fake, ["A"])
    (item,) = res.items
    assert item.status == "failed" and "2 dashboards carry this name" in item.message
    assert fake.sent == []


def test_handler_delete_unreadable_after_listing_is_a_failure(monkeypatch):
    fake = FakeUI([_mine(U1, "A")], deletable=[U1], after=UIClientError("no list"))
    res = _handler_delete(monkeypatch, fake, ["A"])
    (item,) = res.items
    assert item.status == "failed" and "delete not verified" in item.message


# --------------------------------------------------------------------------
# View resolution by viewDefinitionKey
# --------------------------------------------------------------------------

def test_view_resolution_accepts_view_definition_key():
    groups_dict = {"LIST": {"VirtualMachine": [
        {"viewDefinitionKey": U1, "name": "V1"}, {"id": "i2", "name": "V2"}]}}
    groups_list = [{"viewDefinitionKey": "k3", "name": "V3"}, {"name": "no id"}]
    assert [cli.view_id(v) for v in cli.flatten_view_groups(groups_dict)] == [U1, "i2"]
    assert [cli.view_id(v) for v in cli.flatten_view_groups(groups_list)] == ["k3"]

    class _UI:
        def list_views(self):
            return groups_dict

    # By name (both id shapes) and by UUID, whose name comes from the listing.
    assert cli._resolve_view_ids(_UI(), ["V1", "V2", U1]) == [
        (U1, "V1"), ("i2", "V2"), (U1, "V1")]
