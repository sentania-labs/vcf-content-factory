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

from vcfcf_packaging.describe import DescribeCache


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
        # Hand-written entries are untouched; the refresh appends its own.
        assert doc["merged_from"][:2] == _MERGED_FROM
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
        from vcfcf_packaging.cli import main
        with pytest.raises(SystemExit) as exc:
            main(["refresh-describe", "--help"])
        assert exc.value.code == 0
        assert "--prune" in capsys.readouterr().out

    def test_prune_flag_reaches_refresh_all(self, monkeypatch):
        from vcfcf_packaging import cli as cli_mod
        import vcfcf_packaging.describe as describe_mod

        fake_cache = MagicMock()
        fake_cache._client = object()
        monkeypatch.setattr(describe_mod, "make_cache", lambda live=True: fake_cache)
        rc = cli_mod.main(["refresh-describe", "--kind", "VMWARE:HostSystem", "--prune"])
        assert rc == 0
        fake_cache.refresh_all.assert_called_once_with(
            kinds=[("VMWARE", "HostSystem")], prune=True
        )


class TestProvenanceAndByExceptionWarn:

    def _refresh(self, cache_dir, live_stats, live_props=(), host="https://ro818/suite-api"):
        client = _make_client(list(live_stats), list(live_props))
        client.base = host
        cache = DescribeCache(cache_dir=cache_dir, client=client)
        cache.refresh("VMWARE", "HostSystem")
        return _read(cache_dir)

    def test_merged_from_refresh_entry_records_counts_and_retained(self, tmp_path):
        cache_dir = _seed_cache(tmp_path, extra={"merged_from": _MERGED_FROM})
        doc = self._refresh(cache_dir, [_entry("cpu|usage_average", "CPU|Usage (%)", True)])
        entries = [e for e in doc["merged_from"] if e.get("role") == "refresh"]
        assert len(entries) == 1
        e = entries[0]
        assert e["source"].startswith("https://ro818/suite-api/api/adapterkinds/VMWARE")
        assert e["fetched_at"] == doc["fetched_at"]
        assert e["counts"]["metrics"] == {
            "added": 0, "updated": 0, "unchanged": 1,
            "retained": 2, "pruned": 0, "dropped_instance_local": 0,
        }
        assert e["retained_absent"]["metrics"] == [
            "gpu|utilization", "vsan|performance|domClient|iops",
        ]
        assert e["retained_absent"]["properties"] == sorted(_SEED_PROPERTIES)

    def test_refresh_entry_updated_in_place_per_host(self, tmp_path):
        cache_dir = _seed_cache(tmp_path, extra={"merged_from": _MERGED_FROM})
        live = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        self._refresh(cache_dir, live)
        doc = self._refresh(cache_dir, live)
        refresh_entries = [e for e in doc["merged_from"] if e.get("role") == "refresh"]
        assert len(refresh_entries) == 1, "same host must update, not append"
        assert doc["merged_from"][:2] == _MERGED_FROM
        # A different host gets its own entry.
        doc = self._refresh(cache_dir, live, host="https://lab9/suite-api")
        hosts = sorted(
            e["source"].split("/")[2] for e in doc["merged_from"] if e.get("role") == "refresh"
        )
        assert hosts == ["lab9", "ro818"]

    def test_second_identical_refresh_prints_count_line_not_list(self, tmp_path, capsys):
        cache_dir = _seed_cache(tmp_path)
        live = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        self._refresh(cache_dir, live)
        err1 = capsys.readouterr().err
        assert "WARN" in err1 and "gpu|utilization" in err1

        self._refresh(cache_dir, live)
        err2 = capsys.readouterr().err
        assert "gpu|utilization" not in err2
        assert "WARN" not in err2
        assert "2 cached key(s) not reported by ro818" in err2
        assert "unchanged since" in err2

    def test_changed_retained_set_prints_full_list_again(self, tmp_path, capsys):
        cache_dir = _seed_cache(tmp_path)
        self._refresh(cache_dir, [_entry("cpu|usage_average", "CPU|Usage (%)", True)])
        capsys.readouterr()
        # Now the instance also stops reporting cpu|usage_average.
        self._refresh(cache_dir, [_entry("mem|usage_average", "Memory|Usage (%)", True)])
        err = capsys.readouterr().err
        assert "WARN: VMWARE/HostSystem metrics" in err
        assert "cpu|usage_average" in err

    def test_different_host_prints_full_list(self, tmp_path, capsys):
        cache_dir = _seed_cache(tmp_path)
        live = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        self._refresh(cache_dir, live)
        capsys.readouterr()
        self._refresh(cache_dir, live, host="https://lab9/suite-api")
        err = capsys.readouterr().err
        assert "WARN" in err and "gpu|utilization" in err


class TestInstanceLocalKeys:

    _LOCAL = "Super Metric|sm_51613351-5865-478e-9f26-b9d5598fed4d"

    def test_live_super_metric_keys_are_not_imported(self, tmp_path, capsys):
        cache_dir = _seed_cache(tmp_path)
        live_stats = [
            _entry("cpu|usage_average", "CPU|Usage (%)", True),
            _entry(self._LOCAL, "Super Metric|Other Lab SM", True),
        ]
        live_props = [_entry("Super Metric|sm_deadbeef", "Super Metric|Prop", True, "INSTANCED")]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live_stats, live_props))
        cache.refresh("VMWARE", "HostSystem")
        doc = _read(cache_dir)
        assert not any(k.startswith("Super Metric|") for k in doc["metrics"])
        assert not any(k.startswith("Super Metric|") for k in doc["properties"])
        assert "2 instance-local key(s) skipped" in capsys.readouterr().out

    def test_cached_super_metric_keys_are_dropped_without_prune(self, tmp_path, capsys):
        metrics = dict(_SEED_METRICS)
        metrics[self._LOCAL] = {"name": "Super Metric|Other Lab SM", "default_monitored": True}
        cache_dir = _seed_cache(tmp_path, metrics=metrics)
        live_stats = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live_stats, []))
        cache.refresh("VMWARE", "HostSystem")
        doc = _read(cache_dir)
        assert self._LOCAL not in doc["metrics"]
        # Platform keys the instance did not report are still retained.
        assert "gpu|utilization" in doc["metrics"]
        out, err = capsys.readouterr()
        assert "1 dropped-instance-local" in out
        assert self._LOCAL in err
        # And the existence gate no longer sees it.
        assert cache.resolve_metric("VMWARE", "HostSystem", self._LOCAL) is None


class TestCorruptCacheFile:

    def _corrupt(self, tmp_path) -> Path:
        cache_dir = tmp_path / "cache"
        (cache_dir / "VMWARE").mkdir(parents=True)
        (cache_dir / "VMWARE" / "HostSystem.json").write_text("{not json", encoding="utf-8")
        return cache_dir

    def test_corrupt_file_raises_with_recovery_path(self, tmp_path):
        from vcfcf_packaging.describe import DescribeCacheError
        cache_dir = self._corrupt(tmp_path)
        live = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live, []))
        with pytest.raises(DescribeCacheError) as exc:
            cache.refresh("VMWARE", "HostSystem")
        msg = str(exc.value)
        assert "corrupt" in msg
        assert "delete the file" in msg
        assert "refresh-describe --kind VMWARE:HostSystem" in msg
        assert "--prune" in msg
        # File untouched.
        assert (cache_dir / "VMWARE" / "HostSystem.json").read_text() == "{not json"

    def test_corrupt_file_overwritten_with_prune(self, tmp_path, capsys):
        cache_dir = self._corrupt(tmp_path)
        live = [_entry("cpu|usage_average", "CPU|Usage (%)", True)]
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(live, []))
        cache.refresh("VMWARE", "HostSystem", prune=True)
        doc = _read(cache_dir)
        assert list(doc["metrics"]) == ["cpu|usage_average"]
        err = capsys.readouterr().err
        assert "corrupt" in err and "overwriting" in err


# ---------------------------------------------------------------------------
# M2 row 3 side item: a refresh that would change nothing but fetched_at
# leaves the file alone (a credentialed build used to dirty ten cache files)
# ---------------------------------------------------------------------------

class TestRefreshSkipsTimestampOnlyRewrites:

    def _live(self):
        stats = [_entry(k, v["name"], v["default_monitored"]) for k, v in _SEED_METRICS.items()]
        props = [_entry(k, v["name"], v["default_monitored"], v["instance_type"]) for k, v in _SEED_PROPERTIES.items()]
        return stats, props

    def test_second_identical_refresh_is_a_no_op_on_disk(self, tmp_path, capsys):
        cache_dir = _seed_cache(tmp_path, extra={"merged_from": list(_MERGED_FROM), "merge_note": "kept"})
        path = cache_dir / "VMWARE" / "HostSystem.json"
        stats, props = self._live()

        # First refresh from this host: adds the host's merged_from refresh
        # entry (new counts, new source), so the file is rewritten.
        DescribeCache(cache_dir=cache_dir, client=_make_client(stats, props)).refresh("VMWARE", "HostSystem")
        first = path.read_bytes()
        first_doc = json.loads(first)
        assert first_doc["merged_from"][-1]["role"] == "refresh"
        assert "not rewritten" not in capsys.readouterr().out

        # Second refresh, same instance, same answer: only the two fetched_at
        # stamps would change, so nothing is written.
        path.write_bytes(first)
        before_stat = path.stat()
        DescribeCache(cache_dir=cache_dir, client=_make_client(stats, props)).refresh("VMWARE", "HostSystem")
        out = capsys.readouterr().out
        assert path.read_bytes() == first
        assert path.stat().st_mtime_ns == before_stat.st_mtime_ns
        assert "cache file unchanged, not rewritten" in out

        # Third refresh: still a no-op (the no-op path does not accumulate state).
        DescribeCache(cache_dir=cache_dir, client=_make_client(stats, props)).refresh("VMWARE", "HostSystem")
        assert path.read_bytes() == first

    def test_a_real_change_is_still_written(self, tmp_path, capsys):
        cache_dir = _seed_cache(tmp_path)
        path = cache_dir / "VMWARE" / "HostSystem.json"
        stats, props = self._live()
        DescribeCache(cache_dir=cache_dir, client=_make_client(stats, props)).refresh("VMWARE", "HostSystem")
        first = path.read_bytes()
        stats2 = stats + [_entry("NTP|DRIFT_IN_MILLS", "NTP|Drift (ms)", True)]
        DescribeCache(cache_dir=cache_dir, client=_make_client(stats2, props)).refresh("VMWARE", "HostSystem")
        assert path.read_bytes() != first
        assert "NTP|DRIFT_IN_MILLS" in _read(cache_dir)["metrics"]
        assert "not rewritten" not in capsys.readouterr().out
        # A flag flip on an existing key is a change too.
        stats3 = [_entry(k, v["name"], not v["default_monitored"]) if k == "gpu|utilization"
                  else _entry(k, v["name"], v["default_monitored"]) for k, v in _SEED_METRICS.items()]
        stats3.append(_entry("NTP|DRIFT_IN_MILLS", "NTP|Drift (ms)", True))
        second = path.read_bytes()
        DescribeCache(cache_dir=cache_dir, client=_make_client(stats3, props)).refresh("VMWARE", "HostSystem")
        assert path.read_bytes() != second
        assert _read(cache_dir)["metrics"]["gpu|utilization"]["default_monitored"] is True

    def test_in_memory_layer_is_still_invalidated_on_the_no_op_path(self, tmp_path):
        cache_dir = _seed_cache(tmp_path)
        stats, props = self._live()
        cache = DescribeCache(cache_dir=cache_dir, client=_make_client(stats, props))
        cache.refresh("VMWARE", "HostSystem")
        assert cache.resolve_metric("VMWARE", "HostSystem", "cpu|usage_average") is not None
        assert ("VMWARE", "HostSystem") in cache._cache
        cache.refresh("VMWARE", "HostSystem")  # no-op on disk
        assert ("VMWARE", "HostSystem") not in cache._cache
        assert cache.resolve_metric("VMWARE", "HostSystem", "cpu|usage_average").default_monitored is True

    def test_same_but_fetched_at_helper(self):
        from vcfcf_packaging.describe import _same_but_fetched_at
        a = {"fetched_at": "1", "metrics": {"k": 1},
             "merged_from": [{"role": "primary", "source": "x"}, {"role": "refresh", "source": "y", "fetched_at": "1", "counts": {}}]}
        b = json.loads(json.dumps(a))
        b["fetched_at"] = "2"
        b["merged_from"][1]["fetched_at"] = "2"
        assert _same_but_fetched_at(a, b)
        b["merged_from"][1]["counts"] = {"metrics": {"added": 1}}
        assert not _same_but_fetched_at(a, b)
        assert not _same_but_fetched_at({}, a)
        assert _same_but_fetched_at({"metrics": {}}, {"metrics": {}, "fetched_at": "3"})

