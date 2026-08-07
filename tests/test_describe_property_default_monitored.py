"""Unit tests for the property defaultMonitored blind spot fix.

Prior behavior: ``DescribeCache.resolve_metric()`` always returned a synthetic
``default_monitored=True`` for any key found in the properties cache,
regardless of the real value returned by the adapter describe API.
``DescribeCache.refresh()`` also never persisted the API's real
``defaultMonitored``/``instanceType`` fields for properties — only ``name``.

Per knowledge/context/investigations/adapter_describe_exploration.md, the
``/properties`` endpoint returns the same schema as ``/statkeys`` (including a
real ``defaultMonitored`` boolean) with only the ``property: true/false``
discriminator differing. This means the dependency auditor could silently
treat a policy-disabled property as already enabled — a real audit blind spot.

Fast (non-slow) — no live network calls, no zip building.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from vcfops_packaging.describe import DescribeCache


class TestResolveMetricPropertyDefaultMonitored:
    """DescribeCache.resolve_metric() must honor a property's real
    defaultMonitored value once persisted in the cache file."""

    def _write_cache(self, tmp_path: Path, properties: dict) -> Path:
        cache_dir = tmp_path / "cache"
        (cache_dir / "VMWARE").mkdir(parents=True)
        doc = {
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "metrics": {},
            "properties": properties,
        }
        (cache_dir / "VMWARE" / "VirtualMachine.json").write_text(json.dumps(doc))
        return cache_dir

    def test_property_default_monitored_true(self, tmp_path):
        cache_dir = self._write_cache(tmp_path, {
            "config|faultTolerant": {
                "name": "Configuration|Fault Tolerant",
                "default_monitored": True,
                "instance_type": "INSTANCED",
            }
        })
        cache = DescribeCache(cache_dir=cache_dir)
        info = cache.resolve_metric("VMWARE", "VirtualMachine", "config|faultTolerant")
        assert info is not None
        assert info.default_monitored is True

    def test_property_default_monitored_false(self, tmp_path):
        """The core blind-spot regression test: a property explicitly marked
        defaultMonitored=false in the cache must resolve as needing enable,
        not be silently treated as already-monitored."""
        cache_dir = self._write_cache(tmp_path, {
            "gpu|power_limit": {
                "name": "GPU|GPU Power limit (Max TDP)",
                "default_monitored": False,
                "instance_type": "INSTANCED",
            }
        })
        cache = DescribeCache(cache_dir=cache_dir)
        info = cache.resolve_metric("VMWARE", "VirtualMachine", "gpu|power_limit")
        assert info is not None
        assert info.default_monitored is False

    def test_legacy_cache_missing_field_defaults_true(self, tmp_path):
        """Cache files written before this fix only carry {"name": ...} for
        properties. For backward compatibility (no forced re-audit failures
        on unrefreshed caches), missing default_monitored is treated as True."""
        cache_dir = self._write_cache(tmp_path, {
            "summary|guest|toolsVersion": {"name": "Guest OS|Tools Version"}
        })
        cache = DescribeCache(cache_dir=cache_dir)
        info = cache.resolve_metric("VMWARE", "VirtualMachine", "summary|guest|toolsVersion")
        assert info is not None
        assert info.default_monitored is True

    def test_legacy_shortcut_warns_once_per_kind_pair(self, tmp_path, capsys):
        """Taking the legacy name-only fallback must emit a WARN — silently
        guessing defaultMonitored=true is wrong for a real fraction of
        properties (measured: 97/251 VMWARE/VirtualMachine). The WARN must
        fire once per (adapter_kind, resource_kind), not once per property."""
        cache_dir = self._write_cache(tmp_path, {
            "summary|guest|toolsVersion": {"name": "Guest OS|Tools Version"},
            "config|faultTolerant": {"name": "Configuration|Fault Tolerant"},
        })
        cache = DescribeCache(cache_dir=cache_dir)

        cache.resolve_metric("VMWARE", "VirtualMachine", "summary|guest|toolsVersion")
        cache.resolve_metric("VMWARE", "VirtualMachine", "config|faultTolerant")
        cache.resolve_metric("VMWARE", "VirtualMachine", "summary|guest|toolsVersion")

        captured = capsys.readouterr()
        warn_lines = [
            line for line in captured.err.splitlines()
            if "legacy name-only property entries" in line
        ]
        assert len(warn_lines) == 1, (
            f"expected exactly one WARN for the VMWARE/VirtualMachine pair, "
            f"got {len(warn_lines)}: {warn_lines}"
        )

    def test_no_warn_when_field_persisted(self, tmp_path, capsys):
        """A property with a real persisted default_monitored must NOT trigger
        the legacy-shortcut WARN."""
        cache_dir = self._write_cache(tmp_path, {
            "gpu|power_limit": {"name": "x", "default_monitored": False},
        })
        cache = DescribeCache(cache_dir=cache_dir)
        cache.resolve_metric("VMWARE", "VirtualMachine", "gpu|power_limit")
        captured = capsys.readouterr()
        assert "legacy name-only property entries" not in captured.err

    def test_unknown_key_still_returns_none(self, tmp_path):
        cache_dir = self._write_cache(tmp_path, {
            "config|faultTolerant": {"name": "x", "default_monitored": True}
        })
        cache = DescribeCache(cache_dir=cache_dir)
        info = cache.resolve_metric("VMWARE", "VirtualMachine", "does|not_exist")
        assert info is None


class TestRefreshPersistsPropertyMetadata:
    """DescribeCache.refresh() must persist defaultMonitored/instanceType for
    properties, not just name."""

    def _make_client(self, statkeys_body: dict, properties_body: dict):
        client = MagicMock()
        client.base = "https://vcfops.example.com/suite-api"

        def _request(method, path):
            resp = MagicMock()
            resp.status_code = 200
            if path.endswith("/statkeys"):
                resp.json.return_value = statkeys_body
            elif path.endswith("/properties"):
                resp.json.return_value = properties_body
            else:
                resp.json.return_value = {}
            return resp

        client._request.side_effect = _request
        return client

    def test_refresh_writes_default_monitored_and_instance_type(self, tmp_path):
        properties_body = {
            "resourceTypeAttributes": [
                {
                    "key": "gpu|power_limit",
                    "name": "GPU|GPU Power limit (Max TDP)",
                    "defaultMonitored": False,
                    "instanceType": "INSTANCED",
                    "property": True,
                },
                {
                    "key": "config|faultTolerant",
                    "name": "Configuration|Fault Tolerant",
                    "defaultMonitored": True,
                    "instanceType": "INSTANCED",
                    "property": True,
                },
            ]
        }
        client = self._make_client({"resourceTypeAttributes": []}, properties_body)
        cache_dir = tmp_path / "cache"
        cache = DescribeCache(cache_dir=cache_dir, client=client)

        cache.refresh("VMWARE", "VirtualMachine")

        written = json.loads((cache_dir / "VMWARE" / "VirtualMachine.json").read_text())
        props = written["properties"]
        assert props["gpu|power_limit"]["default_monitored"] is False
        assert props["gpu|power_limit"]["instance_type"] == "INSTANCED"
        assert props["config|faultTolerant"]["default_monitored"] is True
        assert props["config|faultTolerant"]["instance_type"] == "INSTANCED"

    def test_refresh_then_resolve_respects_false(self, tmp_path):
        """End-to-end: refresh() writes the real flag, resolve_metric() honors it."""
        properties_body = {
            "resourceTypeAttributes": [
                {
                    "key": "gpu|power_limit",
                    "name": "GPU Power Limit",
                    "defaultMonitored": False,
                    "instanceType": "INSTANCED",
                    "property": True,
                },
            ]
        }
        client = self._make_client({"resourceTypeAttributes": []}, properties_body)
        cache_dir = tmp_path / "cache"
        cache = DescribeCache(cache_dir=cache_dir, client=client)
        cache.refresh("VMWARE", "VirtualMachine")

        info = cache.resolve_metric("VMWARE", "VirtualMachine", "gpu|power_limit")
        assert info is not None
        assert info.default_monitored is False
