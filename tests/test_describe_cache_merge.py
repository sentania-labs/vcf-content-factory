"""Unit tests for DescribeCache.refresh() merge semantics (issue #143).

Prior behavior: ``refresh()`` wrote one instance's statkeys response over the
whole cache file. A cache grounded on a 9.x lab, refreshed against an 8.18
instance, silently lost every key the 8.18 instance did not report.

Required behavior: keys present in the live response are updated, keys
absent from it are retained (and named in a WARN). Removal only happens with
an explicit ``prune=True`` (CLI ``--prune``). Hand-written top-level keys
(``merged_from``, ``merge_note``) survive the refresh.

Fast (non-slow): no live network calls.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vcfops_packaging.describe import DescribeCache


_SEED_METRICS = {
    "cpu|usage_average": {"name": "CPU|Usage (%)", "default_monitored": True},
    "vsan|performance|domClient|iops": {"name": "vSAN|DOM Client|IOPS", "default_monitored": False},
    "gpu|utilization": {"name": "GPU|Utilization", "default_monitored": False},
}
_SEED_PROPERTIES = {
    "config|security|tpmVersion": {
        "name": "Security|TPM Version",
        "default_monitored": True,
        "instance_type": "INSTANCED",
    },
    "config|name": {
        "name": "Configuration|Name",
        "default_monitored": True,
        "instance_type": "INSTANCED",
    },
}
_MERGED_FROM = [
    {"source": "https://lab9/suite-api/...", "platform": "VCF Operations 9.x", "role": "primary"},
    {"source": "https://ro818/suite-api/...", "platform": "VCF Operations 8.18", "role": "additive"},
]


def _entry(key, name, dm=False, instance_type=None):
    e = {"key": key, "name": name, "defaultMonitored": dm}
    if instance_type is not None:
        e["instanceType"] = instance_type
    return e


def _seed_cache(tmp_path: Path, metrics=None, properties=None, extra=None) -> Path:
    cache_dir = tmp_path / "cache"
    (cache_dir / "VMWARE").mkdir(parents=True)
    doc = {
        "adapter_kind": "VMWARE",
        "resource_kind": "HostSystem",
        "fetched_at": "2026-07-27T22:10:45Z",
        "source": "https://lab9/suite-api/api/adapterkinds/VMWARE/resourcekinds/HostSystem/statkeys",
        "metrics": _SEED_METRICS if metrics is None else metrics,
        "properties": _SEED_PROPERTIES if properties is None else properties,
    }
    if extra:
        doc.update(extra)
    (cache_dir / "VMWARE" / "HostSystem.json").write_text(json.dumps(doc), encoding="utf-8")
    return cache_dir


def _make_client(stat_entries, prop_entries):
    client = MagicMock()
    client.base = "https://ro818/suite-api"

    def _request(method, url_path, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if url_path.endswith("/statkeys"):
            resp.json.return_value = {"resourceTypeAttributes": stat_entries}
        else:
            resp.json.return_value = {"resourceTypeAttributes": prop_entries}
        return resp

    client._request = MagicMock(side_effect=_request)
    return client


def _read(cache_dir: Path) -> dict:
    return json.loads((cache_dir / "VMWARE" / "HostSystem.json").read_text(encoding="utf-8"))


class TestRefreshMerges:

    def test_superset_adds_and_updates_without_dropping(self, tmp_path, capsys):
        cache_dir = _seed_cache(tmp_path)
        live_stats = [
            _entry("cpu|usage_average", "CPU|Usage (%)", True),
            _entry("vsan|performance|domClient|iops", "vSAN|DOM Client|IOPS", True),  # changed
            _entry("gpu|utilization", "GPU|Utilization", False),
            _entry("NTP|DRIFT_IN_MILLS", "NTP|Drift (ms)", True),  # new
        ]
        live_props = [
            _entry("config|security|tpmVersion", "Security|TPM Version", True, "INSTANCED"),
            _entry("config|name", "Configuration|Name", True, "INSTANCED"),
            _entry("config|secureBoot", "Security|Secure Boot", True, "INSTANCED"),
        ]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live_stats, live_props))
        cache.refresh("VMWARE", "HostSystem")

        doc = _read(cache_dir)
        assert set(doc["metrics"]) == set(_SEED_METRICS) | {"NTP|DRIFT_IN_MILLS"}
        assert doc["metrics"]["vsan|performance|domClient|iops"]["default_monitored"] is True
        assert set(doc["properties"]) == set(_SEED_PROPERTIES) | {"config|secureBoot"}

        out, err = capsys.readouterr()
        assert "retained-but-absent" not in out
        assert "WARN" not in err
        assert "1 added" in out
        assert "1 updated" in out

    def test_subset_retains_absent_keys_and_warns(self, tmp_path, capsys):
        """The #142 shape: an 8.18 instance reports fewer keys than the 9.x
        grounding. Nothing may be dropped, and the operator is told what
        the live instance did not report."""
        cache_dir = _seed_cache(tmp_path)
        live_stats = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        live_props = [_entry("config|name", "Configuration|Name", True, "INSTANCED")]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live_stats, live_props))
        cache.refresh("VMWARE", "HostSystem")

        doc = _read(cache_dir)
        assert doc["metrics"] == _SEED_METRICS
        assert doc["properties"] == _SEED_PROPERTIES

        out, err = capsys.readouterr()
        assert "2 retained-but-absent metric" in out or "2 retained-but-absent" in out
        assert "vsan|performance|domClient|iops" in err
        assert "gpu|utilization" in err
        assert "config|security|tpmVersion" in err
        assert "--prune" in err

    def test_disjoint_set_is_a_union(self, tmp_path, capsys):
        cache_dir = _seed_cache(tmp_path)
        live_stats = [_entry("mem|usage_average", "Memory|Usage (%)", True)]
        live_props = [_entry("config|dns", "Configuration|DNS", False, "INSTANCED")]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live_stats, live_props))
        cache.refresh("VMWARE", "HostSystem")

        doc = _read(cache_dir)
        assert set(doc["metrics"]) == set(_SEED_METRICS) | {"mem|usage_average"}
        assert set(doc["properties"]) == set(_SEED_PROPERTIES) | {"config|dns"}
        for k, v in _SEED_METRICS.items():
            assert doc["metrics"][k] == v

        out, _ = capsys.readouterr()
        assert "1 added" in out
        assert "3 retained-but-absent" in out

    def test_no_prior_cache_writes_live_response(self, tmp_path, capsys):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        live_stats = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live_stats, []))
        cache.refresh("VMWARE", "HostSystem")
        doc = _read(cache_dir)
        assert list(doc["metrics"]) == ["cpu|usage_average"]
        assert doc["properties"] == {}
        assert "WARN" not in capsys.readouterr().err


class TestRefreshPrune:

    def test_prune_removes_absent_keys_only(self, tmp_path, capsys):
        cache_dir = _seed_cache(tmp_path)
        live_stats = [
            _entry("cpu|usage_average", "CPU|Usage (%)", True),
            _entry("mem|usage_average", "Memory|Usage (%)", True),
        ]
        live_props = [_entry("config|name", "Configuration|Name", True, "INSTANCED")]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live_stats, live_props))
        cache.refresh("VMWARE", "HostSystem", prune=True)

        doc = _read(cache_dir)
        assert set(doc["metrics"]) == {"cpu|usage_average", "mem|usage_average"}
        assert set(doc["properties"]) == {"config|name"}

        out, err = capsys.readouterr()
        assert "2 pruned" in out
        assert "retained-but-absent" not in out
        assert "pruned 2 key(s)" in err
        assert "gpu|utilization" in err

    def test_default_is_not_prune(self, tmp_path):
        """Control: same live response without prune keeps everything."""
        cache_dir = _seed_cache(tmp_path)
        live_stats = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live_stats, []))
        cache.refresh("VMWARE", "HostSystem")
        doc = _read(cache_dir)
        assert set(doc["metrics"]) == set(_SEED_METRICS)
        assert doc["properties"] == _SEED_PROPERTIES

    def test_refresh_all_passes_prune_through(self, tmp_path):
        cache_dir = _seed_cache(tmp_path)
        live_stats = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live_stats, []))
        cache.refresh_all(kinds=[("VMWARE", "HostSystem")], prune=True)
        doc = _read(cache_dir)
        assert list(doc["metrics"]) == ["cpu|usage_average"]
        assert doc["properties"] == {}


class TestRefreshCarriesThroughHandWrittenKeys:

    def test_merged_from_and_merge_note_survive(self, tmp_path):
        cache_dir = _seed_cache(
            tmp_path,
            extra={"merged_from": _MERGED_FROM, "merge_note": "Union of two live instances."},
        )
        live_stats = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live_stats, []))
        cache.refresh("VMWARE", "HostSystem")
        doc = _read(cache_dir)
        assert doc["merged_from"] == _MERGED_FROM
        assert doc["merge_note"] == "Union of two live instances."
        # fetched_at / source describe this refresh, not the original grounding.
        assert doc["source"].startswith("https://ro818/suite-api/api/adapterkinds/VMWARE")
        assert doc["fetched_at"] != "2026-07-27T22:10:45Z"

    def test_properties_fetch_failure_still_merges_metrics(self, tmp_path, capsys):
        """Issue #75 behavior is preserved under merge: a failed /properties
        call keeps the cached section verbatim and says so."""
        cache_dir = _seed_cache(tmp_path)
        client = MagicMock()
        client.base = "https://ro818/suite-api"

        def _request(method, url_path, **kwargs):
            if url_path.endswith("/statkeys"):
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = {
                    "resourceTypeAttributes": [_entry("mem|usage_average", "Memory|Usage (%)", True)]
                }
                return resp
            raise ConnectionError("boom")

        client._request = MagicMock(side_effect=_request)
        cache = DescribeCache(cache_dir=cache_dir, client=client)
        cache.refresh("VMWARE", "HostSystem")
        doc = _read(cache_dir)
        assert set(doc["metrics"]) == set(_SEED_METRICS) | {"mem|usage_average"}
        assert doc["properties"] == _SEED_PROPERTIES
        out, err = capsys.readouterr()
        assert "/properties fetch failed" in err
        assert "preserved, not fetched" in out


class TestCliPruneFlag:

    def test_help_documents_prune(self, capsys):
        from vcfops_packaging.cli import main
        with pytest.raises(SystemExit) as exc:
            main(["refresh-describe", "--help"])
        assert exc.value.code == 0
        assert "--prune" in capsys.readouterr().out

    def test_prune_flag_reaches_refresh_all(self, monkeypatch):
        from vcfops_packaging import cli as cli_mod
        import vcfops_packaging.describe as describe_mod

        fake_cache = MagicMock()
        fake_cache._client = object()
        monkeypatch.setattr(describe_mod, "make_cache", lambda live=True: fake_cache)
        rc = cli_mod.main(["refresh-describe", "--kind", "VMWARE:HostSystem", "--prune"])
        assert rc == 0
        fake_cache.refresh_all.assert_called_once_with(
            kinds=[("VMWARE", "HostSystem")], prune=True
        )
