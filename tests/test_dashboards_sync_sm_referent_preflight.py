"""Dashboard and bundle sync report a missing @supermetric referent before
importing (#154, second half).

`vcfcf_dashboards sync` ran the dependency walker after the import with
``supermetrics=[]``, so the formula of a super metric a synced view uses was
never read and the #144 missing-referent DEP-ERROR could not fire. Bundle
sync ran no referent check at all: the SM step failed inside the push
resolver and the views and dashboards imported after it anyway. Both paths
now check the referents first and import nothing when one is missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_dashboards import cli as dash_cli  # noqa: E402
from vcfcf_packaging.handler import SyncResult  # noqa: E402
from vcfcf_packaging.syncer import sync_bundle  # noqa: E402

P = "[VCF Content Factory] Referent Preflight"
NAME_USED = f"{P} Used SM"
NAME_MID = f"{P} Middle SM"
NAME_MISSING = f"{P} Nowhere SM"
NAME_REMOTE = f"{P} Already Installed SM"
UUID_USED = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
UUID_MID = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
UUID_REMOTE = "eeeeeeee-5555-4555-8555-eeeeeeeeeeee"
RK = [{"resource_kind_key": "HostSystem", "adapter_kind_key": "VMWARE"}]


def _sm_doc(sm_id, name, ref=None):
    formula = (f'${{this, attribute=@supermetric:"{ref}"}}' if ref
               else "${this, metric=cpu|usage_average}")
    return {"id": sm_id, "name": name, "description": "d",
            "resource_kinds": RK, "formula": formula}


def _write_sms(sm_dir: Path, docs) -> None:
    sm_dir.mkdir(parents=True, exist_ok=True)
    for i, doc in enumerate(docs):
        (sm_dir / f"sm{i}.yaml").write_text(
            yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _view(sm_name):
    col = SimpleNamespace(attribute=f'supermetric:"{sm_name}"', display_name="SM col")
    return SimpleNamespace(name=f"{P} View", columns=[col], adapter_kind="VMWARE",
                           resource_kind="HostSystem", provenance="")


def _uuid_view(sm_id):
    view = _view("unused")
    view.columns[0].attribute = f"Super Metric|sm_{sm_id}"
    return view


def _dashboard(metric_key):
    spec = SimpleNamespace(metric_key=metric_key, adapter_kind="VMWARE",
                           resource_kind="HostSystem", metric_name="m")
    widget = SimpleNamespace(
        local_id="w1", type="Scoreboard", view_name=None, pin=None,
        scoreboard_config=SimpleNamespace(metrics=[spec]),
        metric_chart_config=None, health_chart_config=None,
        pareto_analysis_config=None, heatmap_config=None)
    return SimpleNamespace(name=f"{P} Dashboard", widgets=[widget], provenance="")


def _sm_ns(sm_id, name, ref=None):
    formula = (f'${{this, attribute=@supermetric:"{ref}"}}' if ref
               else "${this, metric=cpu|usage_average}")
    return SimpleNamespace(id=sm_id, name=name, provenance="", formula=formula)


class _FakeClient:
    def __init__(self, remote=None):
        self.remote = remote or {}
        self.events = []

    def find_by_name(self, name):
        self.events.append(("find_by_name", name))
        uid = self.remote.get(name)
        return {"id": uid, "name": name} if uid else None


class _RaisingClient(_FakeClient):
    """find_by_name raises, as the real one does on a duplicate name or a
    transport failure."""

    def find_by_name(self, name):
        self.events.append(("find_by_name", name))
        raise RuntimeError(f"2 super metrics named {name!r}")


# --- vcfcf_core supermetrics_used_by ----------------------------------------

def test_supermetrics_used_by_follows_uuid_name_and_crossrefs():
    from vcfcf_common.dep_walker import supermetrics_used_by

    sm_used = _sm_ns(UUID_USED, NAME_USED, ref=NAME_MID)
    sm_mid = _sm_ns(UUID_MID, NAME_MID)
    unused = _sm_ns(UUID_REMOTE, NAME_REMOTE)
    corpus = [sm_used, sm_mid, unused]
    assert supermetrics_used_by([_view(NAME_USED)], [], corpus) == ([sm_used, sm_mid], [])
    assert supermetrics_used_by([_uuid_view(UUID_MID)], [], corpus) == ([sm_mid], [])
    assert supermetrics_used_by([], [], [sm_used]) == ([], [])


@pytest.mark.parametrize("attr", [
    f'SuperMetric:"{NAME_USED}"',
    f'@SuperMetric:"{NAME_USED}"',
    f'  SUPERMETRIC:"{NAME_USED}"  ',
])
def test_supermetrics_used_by_accepts_every_token_case_the_renderer_does(attr):
    """W3: the seed regex is the renderer's, so a mis-cased column the
    renderer resolves as a super metric is a seed too."""
    from vcfcf_common.dep_walker import supermetrics_used_by
    from vcfcf_core.dashboards.render import _SM_COLUMN_REF_RE

    assert _SM_COLUMN_REF_RE.match(attr.strip())
    view = _view(NAME_USED)
    view.columns[0].attribute = attr
    sm_used = _sm_ns(UUID_USED, NAME_USED)
    assert supermetrics_used_by([view], [], [sm_used]) == ([sm_used], [])


def test_supermetrics_used_by_seeds_from_dashboard_widget_uuid_key():
    from vcfcf_common.dep_walker import supermetrics_used_by

    sm_used = _sm_ns(UUID_USED, NAME_USED, ref=NAME_MID)
    sm_mid = _sm_ns(UUID_MID, NAME_MID)
    dash = _dashboard(f"Super Metric|sm_{UUID_USED}")
    assert supermetrics_used_by([], [dash], [sm_used, sm_mid]) == ([sm_used, sm_mid], [])
    sms, unresolved = supermetrics_used_by(
        [], [_dashboard(f"sm_{UUID_REMOTE}")], [sm_used])
    assert sms == []
    assert unresolved == [
        f"dashboard '{P} Dashboard' widget 'w1' (Scoreboard) metric 'm' "
        f"references sm_{UUID_REMOTE}"
    ]


# --- vcfcf_dashboards sync ---------------------------------------------------

def _run_dash_sync(monkeypatch, tmp_path, capsys, sm_docs, client, views,
                   dashboards=(), sm_rel="content/supermetrics"):
    # cwd is the tmp repo: the check also reads content/supermetrics and
    # third_party/*/supermetrics relative to it, never the real repo.
    monkeypatch.chdir(tmp_path)
    _write_sms(tmp_path / sm_rel, sm_docs)
    imports = []
    monkeypatch.setattr(dash_cli, "_load", lambda args: (views, list(dashboards)))
    monkeypatch.setattr(dash_cli, "_resolve_import_navigations",
                        lambda args, d: (0, None))
    monkeypatch.setattr(dash_cli.VCFOpsClient, "from_env",
                        classmethod(lambda cls, **kw: client))
    monkeypatch.setattr(dash_cli, "get_current_user", lambda c: {"id": "u"})
    monkeypatch.setattr(dash_cli, "discover_marker_filename", lambda c: "m")
    monkeypatch.setattr(dash_cli, "build_import_zip", lambda *a, **k: b"zip")
    monkeypatch.setattr(dash_cli, "import_content_zip",
                        lambda c, blob: imports.append(blob) or {
                            "state": "FINISHED", "operationSummaries": []})
    monkeypatch.setattr(dash_cli, "_run_dep_walker", lambda *a, **k: 0)
    args = argparse.Namespace(supermetrics_dir=sm_rel, profile=None,
                              skip_materialization_check=True)
    rc = dash_cli.cmd_sync(args)
    return rc, imports, capsys.readouterr()


def test_dashboard_sync_names_missing_referent_and_does_not_import(
        monkeypatch, tmp_path, capsys):
    # View -> Used SM -> Middle SM (repo) -> Nowhere SM (absent everywhere):
    # the transitive referent is found and named.
    client = _FakeClient()
    rc, imports, out = _run_dash_sync(
        monkeypatch, tmp_path, capsys,
        [_sm_doc(UUID_USED, NAME_USED, ref=NAME_MID),
         _sm_doc(UUID_MID, NAME_MID, ref=NAME_MISSING)],
        client, [_view(NAME_USED)],
    )
    assert rc == 1
    assert imports == []
    assert "DEP-ERROR" in out.err
    assert f"SM '{NAME_MID}' formula" in out.err
    assert f'@supermetric:"{NAME_MISSING}"' in out.err
    assert "nothing was imported" in out.err
    # The in-repo referent resolved from the repo YAML, not the target.
    assert ("find_by_name", NAME_MID) not in client.events


def test_dashboard_sync_imports_when_referent_is_on_target(
        monkeypatch, tmp_path, capsys):
    client = _FakeClient(remote={NAME_REMOTE: UUID_REMOTE})
    rc, imports, out = _run_dash_sync(
        monkeypatch, tmp_path, capsys,
        [_sm_doc(UUID_USED, NAME_USED, ref=NAME_REMOTE)],
        client, [_view(NAME_USED)],
    )
    assert rc == 0, out.err
    assert imports == [b"zip"]
    assert ("find_by_name", NAME_REMOTE) in client.events


def test_dashboard_sync_ignores_sms_no_synced_content_uses(
        monkeypatch, tmp_path, capsys):
    # A broken SM in the repo that nothing being synced uses does not block.
    client = _FakeClient()
    rc, imports, _out = _run_dash_sync(
        monkeypatch, tmp_path, capsys,
        [_sm_doc(UUID_USED, NAME_USED),
         _sm_doc(UUID_MID, NAME_MID, ref=NAME_MISSING)],
        client, [_view(NAME_USED)],
    )
    assert rc == 0
    assert imports == [b"zip"]
    assert client.events == []


def test_dashboard_sync_widget_uuid_key_seeds_the_check(monkeypatch, tmp_path, capsys):
    client = _FakeClient()
    rc, imports, out = _run_dash_sync(
        monkeypatch, tmp_path, capsys,
        [_sm_doc(UUID_USED, NAME_USED, ref=NAME_MISSING)],
        client, [], dashboards=[_dashboard(f"Super Metric|sm_{UUID_USED}")],
    )
    assert rc == 1
    assert imports == []
    assert f"SM '{NAME_USED}' formula" in out.err
    assert f'@supermetric:"{NAME_MISSING}"' in out.err


def test_dashboard_sync_miscased_column_token_seeds_the_check(
        monkeypatch, tmp_path, capsys):
    view = _view(NAME_USED)
    view.columns[0].attribute = f'@SuperMetric:"{NAME_USED}"'
    client = _FakeClient()
    rc, imports, out = _run_dash_sync(
        monkeypatch, tmp_path, capsys,
        [_sm_doc(UUID_USED, NAME_USED, ref=NAME_MISSING)], client, [view],
    )
    assert rc == 1
    assert imports == []
    assert f'@supermetric:"{NAME_MISSING}"' in out.err


def test_dashboard_sync_unloadable_sm_yaml_fails_closed(monkeypatch, tmp_path, capsys):
    """W1: the check cannot run, so nothing is imported."""
    bad = tmp_path / "content/supermetrics"
    bad.mkdir(parents=True)
    (bad / "broken.yaml").write_text("name: [unclosed\n", encoding="utf-8")
    client = _FakeClient()
    rc, imports, out = _run_dash_sync(
        monkeypatch, tmp_path, capsys, [], client, [_view(NAME_USED)],
    )
    assert rc == 1
    assert imports == []
    assert "cannot check super metric references" in out.err
    assert "content/supermetrics" in out.err
    assert "nothing was imported" in out.err


def test_dashboard_sync_third_party_sm_dir_loads_without_prefix(
        monkeypatch, tmp_path, capsys):
    """W1: a third-party SM directory (no framework prefix) loads, so the
    check runs instead of being switched off by a prefix failure."""
    tp_used, tp_missing = "[Acme] Used SM", "[Acme] Nowhere SM"
    client = _FakeClient()
    rc, imports, out = _run_dash_sync(
        monkeypatch, tmp_path, capsys,
        [_sm_doc(UUID_USED, tp_used, ref=tp_missing)],
        client, [_view(tp_used)], sm_rel="third_party/acme/supermetrics",
    )
    assert rc == 1, out.err
    assert imports == []
    assert f"SM '{tp_used}' formula" in out.err
    assert f'@supermetric:"{tp_missing}"' in out.err


def test_dashboard_sync_default_dir_also_reads_third_party_sms(
        monkeypatch, tmp_path, capsys):
    """W2: on the default dir, a third-party SM a view names by sm_<uuid>
    is found in third_party/*/supermetrics and its referents are checked."""
    _write_sms(tmp_path / "third_party/acme/supermetrics",
               [_sm_doc(UUID_MID, "[Acme] Mid SM", ref=NAME_MISSING)])
    client = _FakeClient()
    rc, imports, out = _run_dash_sync(
        monkeypatch, tmp_path, capsys, [], client, [_uuid_view(UUID_MID)])
    assert rc == 1
    assert imports == []
    assert "SM '[Acme] Mid SM' formula" in out.err
    assert f'@supermetric:"{NAME_MISSING}"' in out.err


def test_dashboard_sync_warns_on_sm_uuid_in_no_corpus(monkeypatch, tmp_path, capsys):
    """W2: an sm_<uuid> no loaded YAML defines is named, and the sync goes
    ahead (the SM may exist only on the target)."""
    client = _FakeClient()
    rc, imports, out = _run_dash_sync(
        monkeypatch, tmp_path, capsys,
        [_sm_doc(UUID_USED, NAME_USED)], client, [_uuid_view(UUID_REMOTE)])
    assert rc == 0
    assert imports == [b"zip"]
    assert f"WARN  view '{P} View' col 'SM col' references sm_{UUID_REMOTE}" in out.err


def test_dashboard_sync_target_lookup_failure_stops_import(monkeypatch, tmp_path, capsys):
    client = _RaisingClient()
    rc, imports, out = _run_dash_sync(
        monkeypatch, tmp_path, capsys,
        [_sm_doc(UUID_USED, NAME_USED, ref=NAME_REMOTE)],
        client, [_view(NAME_USED)],
    )
    assert rc == 1
    assert imports == []
    assert f"lookup of super metric '{NAME_REMOTE}' on target failed" in out.err


# --- vcfcf_packaging bundle sync --------------------------------------------

class _RecordingHandler:
    def __init__(self, content_type, order, calls):
        self.content_type = content_type
        self.sync_order = order
        self._calls = calls

    def sync(self, yaml_paths, session):
        self._calls.append(self.content_type)
        return SyncResult(content_type=self.content_type)


@pytest.fixture
def make_bundle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _make(sm_docs, name="referent-preflight"):
        rels = []
        for i, doc in enumerate(sm_docs):
            rel = f"content/supermetrics/{name}-sm{i}.yaml"
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            rels.append(rel)
        manifest = {"name": name, "description": "d", "supermetrics": rels}
        path = tmp_path / "bundles" / f"{name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        return path.relative_to(tmp_path)

    return _make


def _handlers(calls):
    return [_RecordingHandler(ct, i, calls)
            for i, ct in enumerate(("supermetrics", "views", "dashboards"))]


def test_bundle_sync_names_missing_referent_and_imports_nothing(make_bundle, capsys):
    manifest = make_bundle([_sm_doc(UUID_USED, NAME_USED, ref=NAME_MISSING)])
    calls: list = []
    client = _FakeClient()
    rc = sync_bundle(manifest, handlers=_handlers(calls), session=client)
    err = capsys.readouterr().err
    assert rc == 1
    assert calls == []
    assert f"SM '{NAME_USED}' formula" in err
    assert f'@supermetric:"{NAME_MISSING}"' in err
    assert "nothing was imported" in err


def test_bundle_sync_proceeds_when_referents_resolve(make_bundle, capsys):
    manifest = make_bundle([
        _sm_doc(UUID_USED, NAME_USED, ref=NAME_MID),
        _sm_doc(UUID_MID, NAME_MID, ref=NAME_REMOTE),
    ])
    calls: list = []
    client = _FakeClient(remote={NAME_REMOTE: UUID_REMOTE})
    rc = sync_bundle(manifest, handlers=_handlers(calls), session=client)
    assert rc == 0, capsys.readouterr().err
    assert calls == ["supermetrics"]
    assert client.events == [("find_by_name", NAME_REMOTE)]


def test_bundle_sync_target_lookup_failure_imports_nothing(make_bundle, capsys):
    manifest = make_bundle([_sm_doc(UUID_USED, NAME_USED, ref=NAME_REMOTE)])
    calls: list = []
    rc = sync_bundle(manifest, handlers=_handlers(calls), session=_RaisingClient())
    err = capsys.readouterr().err
    assert rc == 1
    assert calls == []
    assert f"lookup of super metric '{NAME_REMOTE}' on target failed" in err


def test_bundle_sync_duplicate_sm_names_import_nothing(make_bundle, capsys):
    manifest = make_bundle([_sm_doc(UUID_USED, NAME_USED), _sm_doc(UUID_MID, NAME_USED)])
    calls: list = []
    client = _FakeClient()
    rc = sync_bundle(manifest, handlers=_handlers(calls), session=client)
    err = capsys.readouterr().err
    assert rc == 1
    assert calls == []
    assert client.events == []
    assert NAME_USED in err
    assert "nothing was imported" in err


def test_sync_all_bundles_continues_past_a_failing_bundle(make_bundle, monkeypatch, capsys):
    from vcfcf_packaging import syncer

    make_bundle([_sm_doc(UUID_USED, NAME_USED, ref=NAME_MISSING)], name="a-broken")
    make_bundle([_sm_doc(UUID_MID, NAME_MID)], name="b-clean")
    calls: list = []
    monkeypatch.setattr(syncer, "discover_handlers", lambda: _handlers(calls))
    monkeypatch.setattr(syncer, "_authenticate", lambda: _FakeClient())
    rc = syncer.sync_all_bundles("bundles")
    out = capsys.readouterr()
    assert rc == 1
    # The broken bundle imported nothing; the clean one after it still ran.
    assert calls == ["supermetrics"]
    assert "Syncing bundle: b-clean" in out.out
    assert f'@supermetric:"{NAME_MISSING}"' in out.err
