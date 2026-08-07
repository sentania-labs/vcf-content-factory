"""Discrete (single-item release) builder tests for builtin_metric_enables.

Covers the TOOLSET GAP fix reported by content-packager: the vm-snapshot-
inventory-dashboard release zip shipped without content/builtin_metric_
enables.json because the discrete/single-item release build path
(discrete_builder.build_discrete -> _assemble_zip) never emitted that
section, and had no dependency-audit gate at all.

This file covers:
  - Discrete build emits content/builtin_metric_enables.json + the matching
    bundle.json content-block key when builtin_metric_enables is declared.
  - Regression: existing discrete builds with no declared entries emit no
    such section (byte-for-byte unaffected by this change).
  - The dependency audit gate now runs for discrete builds: unknown metric
    keys are a hard failure; defaultMonitored=false metrics are auto-added
    (mode=auto, the default) or hard-fail when undeclared (mode=strict) —
    the same auto-add/fail semantics build_bundle() uses.

All tests build real zips, so they are marked slow (excluded from the
default `pytest` run; use `pytest -m slow` or unset -k to include them).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
import yaml

from vcfops_packaging.audit import AuditError
from vcfops_packaging.discrete_builder import build_discrete
from vcfops_packaging.loader import BuiltinMetricEnable

pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SM_FORMULA = (
    "${this, metric=cpu|usage_average} + "
    "${adaptertype=VMWARE, objecttype=VirtualMachine, "
    "metric=discrete_test_group|discrete_test_metric_v1}"
)


def _write_sm_fixture(
    tmp_path: Path,
    name: str = "Discrete Builder Test SM",
    *,
    under_third_party: bool = False,
) -> Path:
    """Write a minimal third-party-style project with one supermetric YAML.

    Uses a synthetic metric key ("discrete_test_group|discrete_test_metric_v1")
    unlikely to collide with any real cache entry, so audit-gate tests can
    control resolution deterministically via a monkeypatched describe cache.

    When ``under_third_party`` is True, the project lives under a literal
    ``third_party/`` directory (``tmp_path/third_party/<proj>/supermetrics/...``)
    so that ``release_builder.build_release()``'s
    ``third_party/<project>/<type>/<file>.yaml`` shape detection routes it
    through the discrete builder with ``extra_search_dirs`` populated — this
    is required for an end-to-end ``build_release()`` test, since a bare
    (non-third-party-shaped) source path is only ever resolved against the
    factory-native ``content/`` tree.
    """
    root = (tmp_path / "third_party") if under_third_party else tmp_path
    proj = root / "sm_project"
    sm_dir = proj / "supermetrics"
    sm_dir.mkdir(parents=True)
    sm_yaml = {
        "name": name,
        "formula": _SM_FORMULA,
        "description": "Fixture SM for discrete builder builtin_metric_enables tests.",
        "resource_kinds": [
            {"resource_kind_key": "VirtualMachine", "adapter_kind_key": "VMWARE"}
        ],
    }
    (sm_dir / "test_metric_sm.yaml").write_text(yaml.dump(sm_yaml))
    return proj


def _zip_members(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path, "r") as z:
        return sorted(z.namelist())


def _bundle_json(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path, "r") as z:
        members = [m for m in z.namelist() if m.endswith("bundle.json")]
        assert members, f"no bundle.json in {zip_path}"
        return json.loads(z.read(members[0]).decode("utf-8"))


def _seed_describe_cache(cache_dir: Path, metrics: dict) -> None:
    """Write a minimal offline describe cache file for VMWARE/VirtualMachine."""
    ak_dir = cache_dir / "VMWARE"
    ak_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "adapter_kind": "VMWARE",
        "resource_kind": "VirtualMachine",
        "metrics": metrics,
        "properties": {},
    }
    (ak_dir / "VirtualMachine.json").write_text(json.dumps(doc))


@pytest.fixture
def sm_project(tmp_path):
    return _write_sm_fixture(tmp_path)


# ---------------------------------------------------------------------------
# Emission tests
# ---------------------------------------------------------------------------

class TestDiscreteBuildEmitsBuiltinMetricEnables:
    def test_emits_json_and_bundle_key_when_declared(self, tmp_path, sm_project):
        out_dir = tmp_path / "out"
        bmes = [
            BuiltinMetricEnable(
                adapter_kind="VMWARE",
                resource_kind="VirtualMachine",
                metric_key="discrete_test_group|discrete_test_metric_v1",
                reason="Declared on the release manifest.",
            )
        ]
        zip_path = build_discrete(
            content_type="supermetric",
            item_name="Discrete Builder Test SM",
            output_dir=out_dir,
            extra_search_dirs=[sm_project],
            builtin_metric_enables=bmes,
            skip_audit=True,
        )

        members = _zip_members(zip_path)
        content_entries = [m for m in members if m.endswith("content/builtin_metric_enables.json")]
        assert content_entries, f"content/builtin_metric_enables.json missing. Members: {members}"

        with zipfile.ZipFile(zip_path) as z:
            payload = json.loads(z.read(content_entries[0]).decode("utf-8"))
        assert payload == [
            {
                "name": "discrete_test_group|discrete_test_metric_v1",
                "adapter_kind": "VMWARE",
                "resource_kind": "VirtualMachine",
                "metric_key": "discrete_test_group|discrete_test_metric_v1",
                "reason": "Declared on the release manifest.",
            }
        ]

        bundle_data = _bundle_json(zip_path)
        bme_section = bundle_data["content"].get("builtin_metric_enables")
        assert bme_section is not None, (
            f"'builtin_metric_enables' missing from bundle.json content block. "
            f"Keys: {list(bundle_data['content'].keys())}"
        )
        assert bme_section["file"] == "content/builtin_metric_enables.json"
        assert bme_section["items"] == [
            {
                "name": "discrete_test_group|discrete_test_metric_v1",
                "adapter_kind": "VMWARE",
                "resource_kind": "VirtualMachine",
                "metric_key": "discrete_test_group|discrete_test_metric_v1",
                "reason": "Declared on the release manifest.",
            }
        ]

    def test_no_reason_omits_reason_key(self, tmp_path, sm_project):
        out_dir = tmp_path / "out"
        bmes = [
            BuiltinMetricEnable(
                adapter_kind="VMWARE",
                resource_kind="VirtualMachine",
                metric_key="discrete_test_group|discrete_test_metric_v1",
            )
        ]
        zip_path = build_discrete(
            content_type="supermetric",
            item_name="Discrete Builder Test SM",
            output_dir=out_dir,
            extra_search_dirs=[sm_project],
            builtin_metric_enables=bmes,
            skip_audit=True,
        )
        bundle_data = _bundle_json(zip_path)
        item = bundle_data["content"]["builtin_metric_enables"]["items"][0]
        assert "reason" not in item


class TestDiscreteBuildRegressionNoField:
    """Existing discrete releases with no builtin_metric_enables declared must
    build with no such section — byte-for-byte unaffected by this change."""

    def test_synthetic_supermetric_no_bme_section(self, tmp_path, sm_project):
        out_dir = tmp_path / "out"
        zip_path = build_discrete(
            content_type="supermetric",
            item_name="Discrete Builder Test SM",
            output_dir=out_dir,
            extra_search_dirs=[sm_project],
            skip_audit=True,
        )
        members = _zip_members(zip_path)
        assert not any(m.endswith("builtin_metric_enables.json") for m in members), (
            f"unexpected builtin_metric_enables.json in zip with no declared entries: {members}"
        )
        bundle_data = _bundle_json(zip_path)
        assert "builtin_metric_enables" not in bundle_data["content"]

    def test_real_dashboard_release_no_bme_section(self, tmp_path):
        """Regression against a real repo item (demand_driven_capacity_v2),
        mirroring the existing Pass A fixture in test_release_builder_phase2."""
        out_dir = tmp_path / "out"
        zip_path = build_discrete(
            content_type="dashboard",
            item_name="[VCF Content Factory] Demand-Driven Capacity Planning v2",
            output_dir=out_dir,
            skip_audit=True,
        )
        bundle_data = _bundle_json(zip_path)
        assert "builtin_metric_enables" not in bundle_data["content"], (
            f"Content keys: {list(bundle_data['content'].keys())}"
        )


# ---------------------------------------------------------------------------
# Audit gate tests
# ---------------------------------------------------------------------------

class TestDiscreteBuildAuditGate:
    def test_unknown_metric_key_fails_loudly(self, tmp_path, sm_project, monkeypatch):
        """A metric key not present in the describe cache at all must raise
        AuditError regardless of mode — same as build_bundle()."""
        import vcfops_packaging.describe as describe_mod

        cache_dir = tmp_path / "describe_cache"
        # Cache file exists for the pair but does NOT contain the referenced key.
        _seed_describe_cache(cache_dir, metrics={})

        monkeypatch.setattr(
            describe_mod, "make_cache",
            lambda live=True, cache_dir=None: describe_mod.DescribeCache(
                cache_dir=(tmp_path / "describe_cache"), client=None
            ),
        )

        with pytest.raises(AuditError):
            build_discrete(
                content_type="supermetric",
                item_name="Discrete Builder Test SM",
                output_dir=tmp_path / "out",
                extra_search_dirs=[sm_project],
                skip_audit=False,
                live_describe=False,
            )

    def test_auto_mode_auto_adds_needs_enable_metric(self, tmp_path, sm_project, monkeypatch):
        """mode=auto (default): a defaultMonitored=false metric not already
        declared is auto-added to builtin_metric_enables, not a hard failure."""
        import vcfops_packaging.describe as describe_mod

        cache_dir = tmp_path / "describe_cache"
        _seed_describe_cache(cache_dir, metrics={
            "cpu|usage_average": {"name": "CPU Usage", "default_monitored": True},
            "discrete_test_group|discrete_test_metric_v1": {
                "name": "Discrete Test Metric", "default_monitored": False,
            },
        })
        monkeypatch.setattr(
            describe_mod, "make_cache",
            lambda live=True, cache_dir=None: describe_mod.DescribeCache(
                cache_dir=(tmp_path / "describe_cache"), client=None
            ),
        )

        zip_path = build_discrete(
            content_type="supermetric",
            item_name="Discrete Builder Test SM",
            output_dir=tmp_path / "out",
            extra_search_dirs=[sm_project],
            skip_audit=False,
            live_describe=False,
            audit_mode="auto",
        )

        bundle_data = _bundle_json(zip_path)
        bme_items = bundle_data["content"]["builtin_metric_enables"]["items"]
        keys = {i["metric_key"] for i in bme_items}
        assert "discrete_test_group|discrete_test_metric_v1" in keys
        auto_item = next(
            i for i in bme_items
            if i["metric_key"] == "discrete_test_group|discrete_test_metric_v1"
        )
        assert "Auto-detected" in auto_item.get("reason", "")

    def test_strict_mode_fails_on_undeclared_needs_enable(self, tmp_path, sm_project, monkeypatch):
        """mode=strict: a defaultMonitored=false metric not declared in
        builtin_metric_enables must raise AuditError."""
        import vcfops_packaging.describe as describe_mod

        cache_dir = tmp_path / "describe_cache"
        _seed_describe_cache(cache_dir, metrics={
            "cpu|usage_average": {"name": "CPU Usage", "default_monitored": True},
            "discrete_test_group|discrete_test_metric_v1": {
                "name": "Discrete Test Metric", "default_monitored": False,
            },
        })
        monkeypatch.setattr(
            describe_mod, "make_cache",
            lambda live=True, cache_dir=None: describe_mod.DescribeCache(
                cache_dir=(tmp_path / "describe_cache"), client=None
            ),
        )

        with pytest.raises(AuditError, match="strict-deps"):
            build_discrete(
                content_type="supermetric",
                item_name="Discrete Builder Test SM",
                output_dir=tmp_path / "out",
                extra_search_dirs=[sm_project],
                skip_audit=False,
                live_describe=False,
                audit_mode="strict",
            )

    def test_skip_audit_bypasses_gate_entirely(self, tmp_path, sm_project):
        """skip_audit=True (the release/publish default) must build without
        touching the describe cache at all, even for an unresolvable key."""
        zip_path = build_discrete(
            content_type="supermetric",
            item_name="Discrete Builder Test SM",
            output_dir=tmp_path / "out",
            extra_search_dirs=[sm_project],
            skip_audit=True,
        )
        assert zip_path.exists()


# ---------------------------------------------------------------------------
# Regression tests — framework-reviewer BLOCKING findings B1 / B2
# (packaging-discrete-builtin-metric-enables-2026-07-27.md)
# ---------------------------------------------------------------------------

class TestAuditGateRegressionRealContent:
    """The newly-wired audit gate must not hard-fail on previously-good,
    released content. Runs offline against the committed describe cache."""

    def test_cpu_support_status_dashboard_survives_audit(self, tmp_path):
        """B1: unresolved supermetric:"<name>" view-column cross-references
        (CLAUDE.md's documented View column -> SM authoring form) must not be
        treated as unknown built-in metric keys by the dependency auditor,
        which runs before render_views_xml() resolves them to sm_<uuid>."""
        zip_path = build_discrete(
            content_type="dashboard",
            item_name="[VCF Content Factory] CPU Support Status",
            output_dir=tmp_path / "out",
            skip_audit=False,
            live_describe=False,
        )
        assert zip_path.exists()

    def test_quarterly_capacity_review_dashboard_survives_audit(self, tmp_path):
        """B1 regression on a second SM-backed view."""
        zip_path = build_discrete(
            content_type="dashboard",
            item_name="[VCF Content Factory] Quarterly Capacity Review",
            output_dir=tmp_path / "out",
            skip_audit=False,
            live_describe=False,
        )
        assert zip_path.exists()

    def test_vm_snapshot_inventory_dashboard_survives_audit(self, tmp_path):
        """B2 (original fix) + PR #70 Codex P1 follow-up: the driver column's
        literal "Instance Name" sentinel still has no describe-cache key and
        is skipped, but member columns' "prefix:instance|suffix" synthetic
        form is now normalized back to its flat describe-cache key and IS
        walked into the audit (see test_deps_instanced_group_columns.py).
        This dashboard's Creator/Description member columns resolve to
        default_monitored=false keys. This test builds with the default
        audit_mode="auto" and no builtin_metric_enables argument, so the
        release manifest is never read here — the audit passes because auto
        mode auto-adds the two newly-detected keys, not because they are
        "corroborated" by the release manifest's manual
        builtin_metric_enables declarations. See
        test_vm_snapshot_inventory_dashboard_survives_strict_audit_via_cli
        below for the strict-mode coverage that does exercise the release
        manifest's declarations (via the build-discrete CLI wiring)."""
        zip_path = build_discrete(
            content_type="dashboard",
            item_name="[VCF Content Factory] VM Snapshot Inventory",
            output_dir=tmp_path / "out",
            skip_audit=False,
            live_describe=False,
        )
        assert zip_path.exists()

    def test_vm_snapshot_inventory_view_survives_audit_directly(self, tmp_path):
        """Same regression at the view level (not just via the dashboard),
        since _refs_from_view is the function B2 fixes."""
        zip_path = build_discrete(
            content_type="view",
            item_name="[VCF Content Factory] VM Snapshot Inventory",
            output_dir=tmp_path / "out",
            skip_audit=False,
            live_describe=False,
        )
        assert zip_path.exists()

    def test_vm_snapshot_inventory_dashboard_survives_strict_audit_via_cli(self, tmp_path):
        """Framework review B1 (packaging-deps-instanced-group-2026-08-06.md):
        `build-discrete --strict-deps` on a released discrete item must not
        hard-fail on defaultMonitored=false keys that ARE already declared in
        the item's release manifest (bundles/releases/vm-snapshot-inventory-
        dashboard.yaml). Before the fix, cmd_build_discrete never loaded the
        release manifest, so --strict-deps was structurally unsatisfiable for
        this dashboard: the error told the operator to add declarations that
        were already sitting in the manifest it never read. This drives the
        actual CLI entry point (not build_discrete() directly) so the
        release-manifest lookup wiring in cmd_build_discrete is exercised."""
        from types import SimpleNamespace
        from vcfops_packaging.cli import cmd_build_discrete

        args = SimpleNamespace(
            content_type="dashboard",
            item_name="[VCF Content Factory] VM Snapshot Inventory",
            output_dir=str(tmp_path / "out"),
            strict_deps=True,
            lax_deps=False,
            no_live_describe=True,
            skip_audit=False,
        )
        rc = cmd_build_discrete(args)
        assert rc == 0, (
            "build-discrete --strict-deps should succeed: the required "
            "builtin_metric_enables are declared in "
            "bundles/releases/vm-snapshot-inventory-dashboard.yaml"
        )


# ---------------------------------------------------------------------------
# End-to-end: release manifest -> build_release -> assert-zip-member (W1)
# ---------------------------------------------------------------------------

class TestReleaseBuilderEndToEnd:
    """The actual shipping path: a release manifest declaring
    builtin_metric_enables:, driven through build_release() (as publish and
    `python3 -m vcfops_packaging build` do), must emit the section — not just
    build_discrete() called directly."""

    def test_release_manifest_with_bme_emits_section(self, tmp_path):
        from vcfops_packaging.release_builder import build_release

        # Must be shaped as third_party/<project>/<type>/<file>.yaml so
        # build_release() routes it through the discrete builder WITH
        # extra_search_dirs populated (a bare tmp_path source only resolves
        # against the factory-native content/ tree — see _write_sm_fixture).
        tp_project = _write_sm_fixture(tmp_path, under_third_party=True)

        manifest = {
            "name": "test-e2e-bme-release",
            "version": "1.0",
            "description": "End-to-end release-manifest builtin_metric_enables test.",
            "artifacts": [
                {
                    "source": str((tp_project / "supermetrics" / "test_metric_sm.yaml").resolve()),
                    "headline": True,
                }
            ],
            "builtin_metric_enables": [
                {
                    "adapter_kind": "VMWARE",
                    "resource_kind": "VirtualMachine",
                    "metric_key": "discrete_test_group|discrete_test_metric_v1",
                    "reason": "End-to-end release manifest declaration.",
                }
            ],
        }
        manifest_path = tmp_path / "test-e2e-bme-release.yaml"
        manifest_path.write_text(yaml.dump(manifest, default_flow_style=False))

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        artifacts = build_release(manifest_path, output_dir, skip_audit=True)

        assert len(artifacts) == 1
        zip_path = artifacts[0].zip_path
        assert zip_path.exists()

        members = _zip_members(zip_path)
        assert any(m.endswith("content/builtin_metric_enables.json") for m in members), (
            f"content/builtin_metric_enables.json missing from build_release() output. "
            f"Members: {members}"
        )

        bundle_data = _bundle_json(zip_path)
        bme_section = bundle_data["content"].get("builtin_metric_enables")
        assert bme_section is not None
        assert bme_section["items"] == [
            {
                "name": "discrete_test_group|discrete_test_metric_v1",
                "adapter_kind": "VMWARE",
                "resource_kind": "VirtualMachine",
                "metric_key": "discrete_test_group|discrete_test_metric_v1",
                "reason": "End-to-end release manifest declaration.",
            }
        ]


# ---------------------------------------------------------------------------
# Cross-builder parity (W2): builder.py and discrete_builder.py must render
# byte-identical builtin_metric_enables item dicts via the shared helper.
# ---------------------------------------------------------------------------

class TestRenderBmeItemsParity:
    def test_render_bme_items_matches_manual_shape(self):
        from vcfops_packaging.loader import BuiltinMetricEnable, render_bme_items

        bmes = [
            BuiltinMetricEnable(
                adapter_kind="VMWARE",
                resource_kind="VirtualMachine",
                metric_key="net|packetsPerSec",
                reason="Reason text.",
            ),
            BuiltinMetricEnable(
                adapter_kind="VMWARE",
                resource_kind="HostSystem",
                metric_key="cpu|some_key",
            ),
        ]
        items = render_bme_items(bmes)
        assert items == [
            {
                "name": "net|packetsPerSec",
                "adapter_kind": "VMWARE",
                "resource_kind": "VirtualMachine",
                "metric_key": "net|packetsPerSec",
                "reason": "Reason text.",
            },
            {
                "name": "cpu|some_key",
                "adapter_kind": "VMWARE",
                "resource_kind": "HostSystem",
                "metric_key": "cpu|some_key",
            },
        ]

    def test_builder_and_discrete_builder_use_same_helper(self):
        """Both modules must import render_bme_items from vcfops_packaging.loader
        rather than carrying their own copy of the item-shape logic."""
        import vcfops_packaging.builder as builder_mod
        import vcfops_packaging.discrete_builder as discrete_mod
        from vcfops_packaging.loader import render_bme_items

        assert builder_mod.render_bme_items is render_bme_items
        assert discrete_mod.render_bme_items is render_bme_items
