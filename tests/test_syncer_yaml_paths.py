"""Bundle sync collects YAML paths for every content type (issue #196).

`_get_yaml_paths_for_type` read `bundle.symptom_paths` / `bundle.alert_paths`,
which the Bundle model never had, so `python3 -m vcfcf_packaging sync`
raised AttributeError on every bundle before doing anything. These tests call
`sync_bundle` against a real loaded bundle (network patched out: a recording
handler per content type and a dummy session), which is what would have
caught it.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vcfcf_packaging.handler import SyncResult
from vcfcf_packaging.syncer import _get_yaml_paths_for_type, sync_bundle

# Every content type the syncer collects paths for.
SYNC_TYPES = ("supermetrics", "customgroups", "views", "dashboards",
              "symptoms", "alerts")

P = "[VCF Content Factory] Sync Paths"

_FILES = {
    "supermetrics": ("content/supermetrics/sm.yaml", {
        "id": "aaaaaaaa-1111-4111-8111-111111111111",
        "name": f"{P} SM",
        "description": "d",
        "resource_kinds": [{"resource_kind_key": "HostSystem",
                            "adapter_kind_key": "VMWARE"}],
        "formula": "${this, metric=cpu|usage_average}",
    }),
    "customgroups": ("content/customgroups/cg.yaml", {
        "name": f"{P} Group",
        "description": "d",
        "type": "Environment",
        "auto_resolve_membership": True,
        "rules": [{"resource_kind": "VirtualMachine", "adapter_kind": "VMWARE",
                   "stat": [{"key": "summary|oversized", "op": "EQ", "value": 1}]}],
    }),
    "views": ("content/views/v.yaml", {
        "id": "bbbbbbbb-2222-4222-8222-222222222222",
        "name": f"{P} View",
        "description": "d",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "columns": [{"attribute": "cpu|usage_average", "display_name": "CPU"}],
    }),
    "dashboards": ("content/dashboards/d.yaml", {
        "id": "cccccccc-3333-4333-8333-333333333333",
        "name": f"{P} Dashboard",
        "description": "d",
        "widgets": [{"id": "txt", "type": "TextDisplay", "title": "t",
                     "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
                     "html": "<b>x</b>"}],
        "interactions": [],
    }),
    "symptoms": ("content/symptoms/s.yaml", {
        "name": f"{P} Symptom",
        "adapter_kind": "VMWARE",
        "resource_kind": "HostSystem",
        "severity": "WARNING",
        "wait_cycles": 3,
        "cancel_cycles": 3,
        "condition": {"type": "metric_static", "key": "cpu|usage_average",
                      "operator": "GT", "value": 90, "instanced": False},
        "description": "d",
    }),
    "alerts": ("content/alerts/a.yaml", {
        "name": f"{P} Alert",
        "description": "d",
        "adapter_kind": "VMWARE",
        "resource_kind": "HostSystem",
        "type": 16,
        "sub_type": 19,
        "wait_cycles": 1,
        "cancel_cycles": 1,
        "criticality": "WARNING",
        "impact": {"badge": "HEALTH"},
        "symptom_sets": {"operator": "ALL", "sets": [{
            "defined_on": "SELF", "operator": "ALL",
            "symptoms": [{"name": f"{P} Symptom"}],
        }]},
    }),
}


class _RecordingHandler:
    """Stands in for a real handler; records what sync_bundle hands it."""

    def __init__(self, content_type: str, order: int, calls: dict):
        self.content_type = content_type
        self.sync_order = order
        self._calls = calls

    def sync(self, yaml_paths, session):
        self._calls[self.content_type] = list(yaml_paths)
        return SyncResult(content_type=self.content_type)


@pytest.fixture
def bundle_repo(tmp_path, monkeypatch):
    for rel, doc in _FILES.values():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    manifest = {"name": "sync-paths", "description": "sync path collection"}
    manifest.update({ct: [rel] for ct, (rel, _doc) in _FILES.items()})
    bundle = tmp_path / "bundles" / "sync-paths.yaml"
    bundle.parent.mkdir(parents=True)
    bundle.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path, bundle.relative_to(tmp_path)


def test_sync_bundle_hands_every_type_its_yaml_path(bundle_repo, capsys):
    root, manifest = bundle_repo
    calls: dict = {}
    handlers = [_RecordingHandler(ct, i, calls) for i, ct in enumerate(SYNC_TYPES)]
    rc = sync_bundle(manifest, handlers=handlers, session=object())
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert set(calls) == set(SYNC_TYPES)
    for ct, (rel, _doc) in _FILES.items():
        assert [Path(p).resolve() for p in calls[ct]] == [(root / rel).resolve()], ct


def test_sync_bundle_without_handlers_warns_per_type(bundle_repo, capsys):
    """The no-handler trailer walks every type too; it must not crash."""
    _root, manifest = bundle_repo
    rc = sync_bundle(manifest, handlers=[], session=object())
    out = capsys.readouterr().out
    assert rc == 0
    for ct in SYNC_TYPES:
        assert f"no handler for '{ct}' (1 file(s) skipped)" in out


def test_get_yaml_paths_for_type_on_loaded_bundle(bundle_repo):
    from vcfcf_packaging.loader import load_bundle

    root, manifest = bundle_repo
    bundle = load_bundle(manifest)
    for ct, (rel, _doc) in _FILES.items():
        got = _get_yaml_paths_for_type(bundle, ct)
        assert [Path(p).resolve() for p in got] == [(root / rel).resolve()], ct
    assert _get_yaml_paths_for_type(bundle, "no-such-type") == []
