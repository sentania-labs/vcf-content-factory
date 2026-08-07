"""Dependency-auditor coverage for instanced_group view columns.

Covers the P1 confirmed on PR #70 external Codex review: extract_metric_
references() / _refs_from_view() previously skipped EVERY instanced_group
column (both the driver "Instance Name" sentinel and data-bearing member
columns), so a discrete view whose only reference to a built-in metric/
property key was via an instanced_group member column passed both strict
and automatic dependency audits while shipping a blank column (confirmed
concretely for VMWARE/VirtualMachine "diskspace|snapshot|creator" and
"diskspace|snapshot|description", both default_monitored=false in
knowledge/context/adapter_describe_cache/VMWARE/VirtualMachine.json).

Fix: skip only the driver column (prefix/suffix both unset). Member
columns' loader-synthesized `attribute` ("{prefix}:{sample_instance}|
{suffix}") is normalized back to the flat describe-cache key form by
splitting on "|" and stripping the ":<instance>" token from each segment,
then emitted as a MetricReference like any other column.

All fixtures are tmp_path-local except the two "real content" regression
tests, which read the committed content/views/vm_snapshot_inventory.yaml
and knowledge/context/adapter_describe_cache/ read-only.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# _normalize_instanced_group_key — pure unit tests
# ---------------------------------------------------------------------------


class TestNormalizeInstancedGroupKey:
    def test_multi_colon_sample_instance(self):
        """Ref: vm_snapshot_inventory.yaml Creator column — prefix
        "diskspace", sample_instance "356893|snapshot:snapshot-16",
        suffix "creator" synthesizes to
        "diskspace:356893|snapshot:snapshot-16|creator" and must normalize
        to "diskspace|snapshot|creator" (the real describe-cache key)."""
        from vcfops_packaging.deps import _normalize_instanced_group_key

        synthesized = "diskspace:356893|snapshot:snapshot-16|creator"
        assert _normalize_instanced_group_key(synthesized) == "diskspace|snapshot|creator"

    def test_simple_single_colon(self):
        """Ref: license-view fixture — prefix "vCommunity|Licensing",
        sample_instance "Evaluation Mode" (no embedded colon/pipe), suffix
        "Edition Key" synthesizes to
        "vCommunity|Licensing:Evaluation Mode|Edition Key" and normalizes
        to "vCommunity|Licensing|Edition Key"."""
        from vcfops_packaging.deps import _normalize_instanced_group_key

        synthesized = "vCommunity|Licensing:Evaluation Mode|Edition Key"
        assert (
            _normalize_instanced_group_key(synthesized)
            == "vCommunity|Licensing|Edition Key"
        )


# ---------------------------------------------------------------------------
# _normalize_metric_key — must match _normalize_instanced_group_key
# ---------------------------------------------------------------------------


class TestNormalizeMetricKeyMatchesInstancedGroupRule:
    """Framework review W1 (packaging-deps-instanced-group-2026-08-06.md):
    _normalize_metric_key() is used for every NON-instanced_group path
    (direct `attribute:` columns, SM formula `metric=` values, all widget
    keys, and the staged-bundle XML audit path), but before this fix it only
    stripped a `:<instance>` token from the *first* pipe segment. Real
    vendor instanced keys can carry the instance token on any segment, so a
    plain `attribute:` column referencing the same wire key an
    `instanced_group:` column resolves correctly would derive a different,
    wrong, describe-cache key and hard-fail the audit. _normalize_metric_key
    now delegates to the same segment-local rule as
    _normalize_instanced_group_key so both authoring forms produce identical
    output for the same wire key."""

    def test_multi_segment_instance_diskspace_snapshot(self):
        """Ref: reviewer W1 table row 1 — a direct-attribute column
        authored as "diskspace:262|snapshot:snapshot-1|used" must normalize
        to the same flat key an instanced_group member column would."""
        from vcfops_packaging.deps import _normalize_metric_key

        assert (
            _normalize_metric_key("diskspace:262|snapshot:snapshot-1|used")
            == "diskspace|snapshot|used"
        )

    def test_multi_segment_instance_vcommunity_licensing(self):
        """Ref: reviewer W1 table row 2 — instance token on a non-first
        segment ("vCommunity|Licensing:Evaluation Mode|Edition Key")."""
        from vcfops_packaging.deps import _normalize_metric_key

        assert (
            _normalize_metric_key("vCommunity|Licensing:Evaluation Mode|Edition Key")
            == "vCommunity|Licensing|Edition Key"
        )

    def test_still_correct_for_simple_leading_segment_form(self):
        """Regression: the original single-segment form
        ("net:instance|packetsPerSec") this function always handled must
        still normalize the same way after delegating."""
        from vcfops_packaging.deps import _normalize_metric_key

        assert (
            _normalize_metric_key("net:Aggregate of all instances|packetsPerSec")
            == "net|packetsPerSec"
        )

    def test_non_instanced_key_unchanged(self):
        """Regression: a plain, non-instanced key with no colon anywhere
        must pass through unchanged."""
        from vcfops_packaging.deps import _normalize_metric_key

        assert _normalize_metric_key("cpu|usage_average") == "cpu|usage_average"


# ---------------------------------------------------------------------------
# _refs_from_view — driver skipped, member column normalized + emitted
# ---------------------------------------------------------------------------


def _write_view(tmp_path: Path, data: dict, stem: str = "view") -> Path:
    import yaml

    d = tmp_path / "views"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{stem}.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _snapshot_style_view_data() -> dict:
    return {
        "name": "[VCF Content Factory] Instanced Group Audit Test",
        "description": "",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
        "columns": [
            {
                "display_name": "Instance",
                "instanced_group": {
                    "name": "GROUP_diskspace",
                    "show_instance_name": True,
                    "keep_instance_summary": False,
                },
            },
            {
                "display_name": "Creator",
                "is_property": True,
                "is_string_attribute": True,
                "instanced_group": {
                    "name": "GROUP_diskspace",
                    "prefix": "diskspace",
                    "suffix": "creator",
                    "sample_instance": "356893|snapshot:snapshot-16",
                },
            },
        ],
    }


class TestRefsFromView:
    def _load_view(self, tmp_path: Path):
        from vcfops_dashboards.loader import load_view

        p = _write_view(tmp_path, _snapshot_style_view_data())
        v = load_view(p, enforce_framework_prefix=False)
        v.validate(enforce_framework_prefix=False)
        return v

    def test_driver_column_still_skipped(self, tmp_path):
        from vcfops_packaging.deps import _refs_from_view

        v = self._load_view(tmp_path)
        refs = _refs_from_view(v)
        # Only the member (Creator) column should produce a reference; the
        # driver's "Instance Name" sentinel must never appear as a key.
        assert all(r.metric_key != "Instance Name" for r in refs)

    def test_member_column_emits_normalized_reference(self, tmp_path):
        from vcfops_packaging.deps import _refs_from_view, MetricReference

        v = self._load_view(tmp_path)
        refs = _refs_from_view(v)
        assert len(refs) == 1
        ref = refs[0]
        assert isinstance(ref, MetricReference)
        assert ref.adapter_kind == "VMWARE"
        assert ref.resource_kind == "VirtualMachine"
        assert ref.metric_key == "diskspace|snapshot|creator"


class TestExtractMetricReferencesIncludesInstancedMembers:
    def test_bundle_level_walk_includes_member_ref(self, tmp_path):
        from vcfops_dashboards.loader import load_view
        from vcfops_packaging.deps import extract_metric_references

        p = _write_view(tmp_path, _snapshot_style_view_data())
        v = load_view(p, enforce_framework_prefix=False)
        v.validate(enforce_framework_prefix=False)

        bundle = SimpleNamespace(supermetrics=[], views=[v], dashboards=[])
        refs = extract_metric_references(bundle)
        keys = {(r.adapter_kind, r.resource_kind, r.metric_key) for r in refs}
        assert ("VMWARE", "VirtualMachine", "diskspace|snapshot|creator") in keys


# ---------------------------------------------------------------------------
# Audit-level: a default_monitored=false key reachable only via an
# instanced_group member column must now be flagged/auto-enabled.
# ---------------------------------------------------------------------------


class TestAuditFlagsInstancedMemberKey:
    def _seed_cache(self, cache_dir: Path) -> None:
        import json

        ak_dir = cache_dir / "VMWARE"
        ak_dir.mkdir(parents=True, exist_ok=True)
        doc = {
            "adapter_kind": "VMWARE",
            "resource_kind": "VirtualMachine",
            "metrics": {},
            "properties": {
                "diskspace|snapshot|creator": {
                    "name": "Disk Space|Snapshot|Creator",
                    "default_monitored": False,
                    "instance_type": "INSTANCED",
                },
            },
        }
        (ak_dir / "VirtualMachine.json").write_text(json.dumps(doc))

    def _build_bundle(self, tmp_path: Path, builtin_metric_enables=None):
        from vcfops_dashboards.loader import load_view
        from vcfops_packaging.loader import Bundle

        p = _write_view(tmp_path, _snapshot_style_view_data())
        v = load_view(p, enforce_framework_prefix=False)
        v.validate(enforce_framework_prefix=False)
        return Bundle(
            name="test-instanced-audit",
            description="",
            sync_enabled=True,
            supermetrics=[],
            views=[v],
            dashboards=[],
            customgroups=[],
            builtin_metric_enables=builtin_metric_enables or [],
        )

    def test_auto_mode_auto_adds_instanced_member_key(self, tmp_path):
        from vcfops_packaging.audit import audit_bundle_dependencies
        from vcfops_packaging.describe import DescribeCache

        cache_dir = tmp_path / "describe_cache"
        self._seed_cache(cache_dir)
        cache = DescribeCache(cache_dir=cache_dir, client=None)

        bundle = self._build_bundle(tmp_path)
        result = audit_bundle_dependencies(bundle, cache, mode="auto")

        assert not result.unknown
        keys = {(a.adapter_kind, a.resource_kind, a.metric_key) for a in result.auto_added}
        assert ("VMWARE", "VirtualMachine", "diskspace|snapshot|creator") in keys

    def test_strict_mode_fails_when_undeclared(self, tmp_path):
        from vcfops_packaging.audit import audit_bundle_dependencies, AuditError
        from vcfops_packaging.describe import DescribeCache

        cache_dir = tmp_path / "describe_cache"
        self._seed_cache(cache_dir)
        cache = DescribeCache(cache_dir=cache_dir, client=None)

        bundle = self._build_bundle(tmp_path)
        with pytest.raises(AuditError, match="strict-deps"):
            audit_bundle_dependencies(bundle, cache, mode="strict")

    def test_strict_mode_passes_when_declared(self, tmp_path):
        """A manual builtin_metric_enables declaration (as the shipped
        vm-snapshot-inventory-dashboard release carries) corroborates the
        now-detected reference instead of conflicting with it."""
        from vcfops_packaging.audit import audit_bundle_dependencies
        from vcfops_packaging.describe import DescribeCache
        from vcfops_packaging.loader import BuiltinMetricEnable

        cache_dir = tmp_path / "describe_cache"
        self._seed_cache(cache_dir)
        cache = DescribeCache(cache_dir=cache_dir, client=None)

        bundle = self._build_bundle(
            tmp_path,
            builtin_metric_enables=[
                BuiltinMetricEnable(
                    adapter_kind="VMWARE",
                    resource_kind="VirtualMachine",
                    metric_key="diskspace|snapshot|creator",
                    reason="Manually declared.",
                )
            ],
        )
        result = audit_bundle_dependencies(bundle, cache, mode="strict")
        assert not result.auto_added
        keys = {(r.adapter_kind, r.resource_kind, r.metric_key) for r in result.needs_enable}
        assert ("VMWARE", "VirtualMachine", "diskspace|snapshot|creator") in keys


# ---------------------------------------------------------------------------
# Real content regression: the committed vm_snapshot_inventory view/release
# must still validate cleanly against the real (committed) describe cache,
# now that its Creator/Description member columns are actually audited
# (previously they dodged the gate entirely and only worked because of the
# manual builtin_metric_enables entries — now those entries are corroborated
# rather than made redundant/conflicting).
# ---------------------------------------------------------------------------


class TestRealSnapshotViewStillValidates:
    def test_vm_snapshot_inventory_view_survives_auto_audit(self):
        from vcfops_dashboards.loader import load_view
        from vcfops_packaging.audit import audit_bundle_dependencies
        from vcfops_packaging.describe import make_cache
        from vcfops_packaging.loader import Bundle, BuiltinMetricEnable

        view_path = REPO_ROOT / "content" / "views" / "vm_snapshot_inventory.yaml"
        v = load_view(view_path, enforce_framework_prefix=True)
        v.validate(enforce_framework_prefix=True)

        bundle = Bundle(
            name="vm-snapshot-inventory-dashboard",
            description="",
            sync_enabled=True,
            supermetrics=[],
            views=[v],
            dashboards=[],
            customgroups=[],
            builtin_metric_enables=[
                BuiltinMetricEnable(
                    adapter_kind="VMWARE",
                    resource_kind="VirtualMachine",
                    metric_key="diskspace|snapshot|creator",
                    reason="View Creator column reads this policy-disabled property.",
                ),
                BuiltinMetricEnable(
                    adapter_kind="VMWARE",
                    resource_kind="VirtualMachine",
                    metric_key="diskspace|snapshot|description",
                    reason="View Description column reads this policy-disabled property.",
                ),
            ],
        )

        cache = make_cache(live=False)
        result = audit_bundle_dependencies(bundle, cache, mode="strict")

        # Both instanced-group member keys must now show up as audited
        # needs_enable refs, corroborated (not conflicting) with the
        # bundle's manual declarations — strict mode must not raise.
        keys = {(r.adapter_kind, r.resource_kind, r.metric_key) for r in result.needs_enable}
        assert ("VMWARE", "VirtualMachine", "diskspace|snapshot|creator") in keys
        assert ("VMWARE", "VirtualMachine", "diskspace|snapshot|description") in keys
        assert not result.unknown
