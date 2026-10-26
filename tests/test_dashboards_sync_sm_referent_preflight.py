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


class _FakeClient:
    def __init__(self, remote=None):
        self.remote = remote or {}
        self.events = []

    def find_by_name(self, name):
        self.events.append(("find_by_name", name))
        uid = self.remote.get(name)
        return {"id": uid, "name": name} if uid else None


# --- vcfcf_dashboards sync ---------------------------------------------------

def _run_dash_sync(monkeypatch, tmp_path, capsys, sm_docs, client, views):
    sm_dir = tmp_path / "supermetrics"
    _write_sms(sm_dir, sm_docs)
    imports = []
    monkeypatch.setattr(dash_cli, "_load", lambda args: (views, []))
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
    args = argparse.Namespace(supermetrics_dir=str(sm_dir), profile=None,
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


def test_supermetrics_used_by_follows_uuid_name_and_crossrefs():
    from vcfcf_common.dep_walker import supermetrics_used_by

    sm_used = SimpleNamespace(id=UUID_USED, name=NAME_USED, provenance="",
                              formula=f'${{this, attribute=@supermetric:"{NAME_MID}"}}')
    sm_mid = SimpleNamespace(id=UUID_MID, name=NAME_MID, provenance="",
                             formula="${this, metric=cpu|usage_average}")
    unused = SimpleNamespace(id=UUID_REMOTE, name=NAME_REMOTE, provenance="",
                             formula="1")
    by_uuid = SimpleNamespace(
        name="v2", adapter_kind="VMWARE", resource_kind="HostSystem", provenance="",
        columns=[SimpleNamespace(attribute=f"Super Metric|sm_{UUID_MID}",
                                 display_name="c")])
    assert supermetrics_used_by([_view(NAME_USED)], [], [sm_used, sm_mid, unused]) \
        == [sm_used, sm_mid]
    assert supermetrics_used_by([by_uuid], [], [sm_used, sm_mid, unused]) == [sm_mid]
    assert supermetrics_used_by([], [], [sm_used]) == []


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

    def _make(sm_docs):
        rels = []
        for i, doc in enumerate(sm_docs):
            rel = f"content/supermetrics/sm{i}.yaml"
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            rels.append(rel)
        manifest = {"name": "referent-preflight", "description": "d",
                    "supermetrics": rels}
        path = tmp_path / "bundles" / "referent-preflight.yaml"
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
