"""Schema tests for the release-manifest ``builtin_metric_enables:`` field.

Covers the TOOLSET GAP fix: discrete (single-item) release manifests had no
way to declare built-in metric enablements, because that field previously
lived only on bundle YAMLs.  These tests cover schema round-trip and
validation for the new field on ``bundles/releases/*.yaml``.

Fast (non-slow) — pure schema parsing, no zip building.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vcfops_packaging.releases import ReleaseValidationError, load_release
from vcfops_packaging.loader import BuiltinMetricEnable

REPO_ROOT = Path(__file__).parent.parent


def _write_manifest(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "test-release.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _minimal_manifest(**overrides) -> dict:
    source_abs = (
        REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml"
    ).resolve()
    assert source_abs.exists(), f"fixture source not found: {source_abs}"
    manifest = {
        "name": "test-release",
        "version": "1.0",
        "description": "Schema test release.",
        "artifacts": [{"source": str(source_abs), "headline": True}],
    }
    manifest.update(overrides)
    return manifest


class TestBuiltinMetricEnablesSchema:
    def test_defaults_to_empty_list(self, tmp_path):
        """A manifest with no builtin_metric_enables field parses with an empty list."""
        manifest_path = _write_manifest(tmp_path, _minimal_manifest())
        release = load_release(manifest_path)
        assert release.builtin_metric_enables == []

    def test_round_trip_single_entry(self, tmp_path):
        manifest = _minimal_manifest(builtin_metric_enables=[
            {
                "adapter_kind": "VMWARE",
                "resource_kind": "VirtualMachine",
                "metric_key": "net|packetsPerSec",
                "reason": "Needed for the headline dashboard's network widget.",
            }
        ])
        manifest_path = _write_manifest(tmp_path, manifest)
        release = load_release(manifest_path)

        assert len(release.builtin_metric_enables) == 1
        bme = release.builtin_metric_enables[0]
        assert isinstance(bme, BuiltinMetricEnable)
        assert bme.adapter_kind == "VMWARE"
        assert bme.resource_kind == "VirtualMachine"
        assert bme.metric_key == "net|packetsPerSec"
        assert bme.reason == "Needed for the headline dashboard's network widget."

    def test_round_trip_multiple_entries(self, tmp_path):
        manifest = _minimal_manifest(builtin_metric_enables=[
            {
                "adapter_kind": "VMWARE",
                "resource_kind": "VirtualMachine",
                "metric_key": "net|packetsPerSec",
            },
            {
                "adapter_kind": "VMWARE",
                "resource_kind": "HostSystem",
                "metric_key": "cpu|some_key",
                "reason": "Optional",
            },
        ])
        manifest_path = _write_manifest(tmp_path, manifest)
        release = load_release(manifest_path)
        assert len(release.builtin_metric_enables) == 2
        assert release.builtin_metric_enables[0].reason == ""
        assert release.builtin_metric_enables[1].reason == "Optional"

    def test_reason_optional_defaults_empty(self, tmp_path):
        manifest = _minimal_manifest(builtin_metric_enables=[
            {
                "adapter_kind": "VMWARE",
                "resource_kind": "VirtualMachine",
                "metric_key": "net|packetsPerSec",
            }
        ])
        manifest_path = _write_manifest(tmp_path, manifest)
        release = load_release(manifest_path)
        assert release.builtin_metric_enables[0].reason == ""

    def test_not_a_list_raises(self, tmp_path):
        manifest = _minimal_manifest(builtin_metric_enables={"adapter_kind": "VMWARE"})
        manifest_path = _write_manifest(tmp_path, manifest)
        with pytest.raises(ReleaseValidationError, match="must be a list"):
            load_release(manifest_path)

    def test_entry_not_a_mapping_raises(self, tmp_path):
        manifest = _minimal_manifest(builtin_metric_enables=["not-a-mapping"])
        manifest_path = _write_manifest(tmp_path, manifest)
        with pytest.raises(ReleaseValidationError, match="must be a mapping"):
            load_release(manifest_path)

    @pytest.mark.parametrize("missing_field", ["adapter_kind", "resource_kind", "metric_key"])
    def test_missing_required_field_raises(self, tmp_path, missing_field):
        entry = {
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "metric_key": "net|packetsPerSec",
        }
        del entry[missing_field]
        manifest = _minimal_manifest(builtin_metric_enables=[entry])
        manifest_path = _write_manifest(tmp_path, manifest)
        with pytest.raises(ReleaseValidationError, match=missing_field):
            load_release(manifest_path)
