"""Regression tests for the 2026-08-20 packaging audit/describe batch.

Covers (framework review W2, report:
knowledge/context/reviews/framework/packaging-audit-cli-2026-08-20.md):

1. Issue #71/#72: ``audit._refs_from_views_xml`` parses factory-emitted view
   XML (SubjectType + attributeInfos wire shape, NOT the phantom
   <Column attributeKey=...> / <ResourceKind> shape the old parser expected).
   Pinned against a committed fixture rendered from
   content/views/vm_snapshot_inventory.yaml: 10 refs, including the
   subject-filter metricKey (issue #72) and excluding the instanced-group
   "Instance Name" driver sentinel.

2. Issue #75: ``DescribeCache.refresh()`` preserves previously-cached
   properties when the /properties fetch fails, on both the
   exception path and the non-200 path, and warns to stderr either way.

Fast (non-slow): no live network calls, no zip building.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from vcfops_packaging.audit import _refs_from_views_xml
from vcfops_packaging.describe import DescribeCache

FIXTURE = Path(__file__).parent / "fixtures" / "vm_snapshot_inventory_views_content.xml"


# ---------------------------------------------------------------------------
# Issue #71/#72: staged-bundle view XML parser
# ---------------------------------------------------------------------------

class TestRefsFromViewsXml:
    """Pin the rewritten analyze-path parser against real factory XML.

    The fixture is the exact views_content.xml the packaging builder emits
    for the VM Snapshot Inventory view (rendered via
    vcfops_dashboards.render.render_views_xml). The old parser extracted 0
    refs from this shape ("silently dodges the gate", issue #71); the build
    audit sees 10. These tests pin the analyze path at parity.
    """

    def _refs(self):
        return _refs_from_views_xml(FIXTURE)

    def test_extracts_ten_refs(self):
        assert len(self._refs()) == 10

    def test_all_refs_carry_subject_kinds(self):
        for r in self._refs():
            assert r.adapter_kind == "VMWARE"
            assert r.resource_kind == "VirtualMachine"

    def test_column_keys_extracted(self):
        keys = [r.metric_key for r in self._refs()]
        # Instanced-group member columns, normalized to base form.
        assert "diskspace|snapshot|name" in keys
        assert "diskspace|snapshot|used" in keys
        assert "diskspace|snapshot|creator" in keys
        assert "diskspace|snapshot|description" in keys
        # Plain property columns.
        assert "summary|parentCluster" in keys
        assert "summary|parentVcenter" in keys
        assert "summary|datastore" in keys

    def test_subject_filter_key_extracted(self):
        """Issue #72: the SubjectType filter= JSON metricKey must be audited.

        numberOfDays appears once as a column AND once from the subject
        filter; both occurrences must be present (the audit dedupes refs
        downstream, the parser must not)."""
        keys = [r.metric_key for r in self._refs()]
        assert keys.count("diskspace|snapshot|numberOfDays") == 2

    def test_instance_name_driver_sentinel_skipped(self):
        """The instanced-group driver column has no describe-cache key."""
        keys = [r.metric_key for r in self._refs()]
        assert "Instance Name" not in keys

    def test_source_desc_uses_title_child(self):
        """Factory XML carries the view title in <Title>, not a name attr;
        source_desc must not degrade to "view 'unknown view'" (review N2)."""
        for r in self._refs():
            assert r.source_desc == "view '[VCF Content Factory] VM Snapshot Inventory'"


# ---------------------------------------------------------------------------
# Issue #75: properties preservation on /properties fetch failure
# ---------------------------------------------------------------------------

_SEED_PROPERTIES = {
    "summary|guest|toolsVersion": {
        "name": "Summary|Guest|Tools Version",
        "default_monitored": False,
        "instance_type": "",
    },
    "config|name": {
        "name": "Configuration|Name",
        "default_monitored": True,
        "instance_type": "",
    },
}

_STATKEYS_BODY = {
    "resourceTypeAttributes": [
        {"key": "cpu|usage_average", "name": "CPU|Usage (%)", "defaultMonitored": True},
    ]
}


class TestDescribeRefreshPropertiesPreservation:
    """A failed /properties call must not clobber a good cache (issue #75)."""

    def _seed_cache(self, tmp_path: Path) -> Path:
        cache_dir = tmp_path / "cache"
        (cache_dir / "VMWARE").mkdir(parents=True)
        doc = {
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "metrics": {"old|metric": {"name": "Old", "default_monitored": False}},
            "properties": _SEED_PROPERTIES,
        }
        (cache_dir / "VMWARE" / "VirtualMachine.json").write_text(json.dumps(doc))
        return cache_dir

    def _make_client(self, props_behavior):
        """Stub client: /statkeys succeeds; /properties per props_behavior."""
        client = MagicMock()

        statkeys_resp = MagicMock()
        statkeys_resp.status_code = 200
        statkeys_resp.json.return_value = _STATKEYS_BODY

        def _request(method, url_path, **kwargs):
            if url_path.endswith("/statkeys"):
                return statkeys_resp
            return props_behavior()

        client._request = MagicMock(side_effect=_request)
        return client

    def _read_cache_doc(self, cache_dir: Path) -> dict:
        return json.loads(
            (cache_dir / "VMWARE" / "VirtualMachine.json").read_text(encoding="utf-8")
        )

    def test_exception_path_preserves_properties(self, tmp_path, capsys):
        cache_dir = self._seed_cache(tmp_path)

        def _raise():
            raise ConnectionError("boom")

        cache = DescribeCache(cache_dir=cache_dir, client=self._make_client(_raise))
        cache.refresh("VMWARE", "VirtualMachine")

        doc = self._read_cache_doc(cache_dir)
        # Metrics refreshed from the (successful) statkeys fetch...
        assert "cpu|usage_average" in doc["metrics"]
        # ...but properties preserved from the prior cache, not clobbered to {}.
        assert doc["properties"] == _SEED_PROPERTIES
        # And the half-failure is reported, not silent (review W1).
        err = capsys.readouterr().err
        assert "WARN" in err
        assert "VMWARE/VirtualMachine" in err
        assert "ConnectionError" in err

    def test_non_200_path_preserves_properties(self, tmp_path, capsys):
        cache_dir = self._seed_cache(tmp_path)

        def _http_500():
            resp = MagicMock()
            resp.status_code = 500
            return resp

        cache = DescribeCache(cache_dir=cache_dir, client=self._make_client(_http_500))
        cache.refresh("VMWARE", "VirtualMachine")

        doc = self._read_cache_doc(cache_dir)
        assert "cpu|usage_average" in doc["metrics"]
        assert doc["properties"] == _SEED_PROPERTIES
        err = capsys.readouterr().err
        assert "WARN" in err
        assert "HTTP 500" in err

    def test_success_path_writes_fresh_properties(self, tmp_path, capsys):
        """Control: a 200 /properties response replaces the cached section."""
        cache_dir = self._seed_cache(tmp_path)

        def _http_200():
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "resourceTypeAttributes": [
                    {
                        "key": "config|fresh",
                        "name": "Configuration|Fresh",
                        "defaultMonitored": True,
                        "instanceType": "INSTANCED",
                    }
                ]
            }
            return resp

        cache = DescribeCache(cache_dir=cache_dir, client=self._make_client(_http_200))
        cache.refresh("VMWARE", "VirtualMachine")

        doc = self._read_cache_doc(cache_dir)
        assert list(doc["properties"]) == ["config|fresh"]
        assert "WARN: /properties fetch failed" not in capsys.readouterr().err

    def test_failure_with_no_prior_cache_writes_empty_properties(self, tmp_path, capsys):
        """No prior cache file: nothing to preserve, empty dict is correct."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        def _raise():
            raise ConnectionError("boom")

        cache = DescribeCache(cache_dir=cache_dir, client=self._make_client(_raise))
        cache.refresh("VMWARE", "VirtualMachine")

        doc = self._read_cache_doc(cache_dir)
        assert doc["properties"] == {}
        assert "WARN" in capsys.readouterr().err
