"""Phase 1.5 smoke tests for the dep_walker extension.

Verifies:
  1. collect_deps() starting from capacity_assessment.yaml surfaces:
       - the vms_rightsizing_candidates custom group
       - all 11 SMs listed in the bundle manifest
       - both views listed in the bundle manifest
  2. collect_deps() starting from demand_driven_capacity_v2.yaml returns:
       - 4 views, 0 SMs, 0 customgroups
  3. Missing-dep errors are surfaced correctly (customgroup ref not in corpus).
  4. Customgroup recursion does not infinite-loop on a self-referencing fixture.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Repo root fixture
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent


def _load_all():
    """Load the full repo corpus (views, dashboards, SMs, customgroups)."""
    from vcfops_supermetrics.loader import load_dir as _load_sms
    from vcfops_dashboards.loader import load_all as _load_dash
    from vcfops_customgroups.loader import load_dir as _load_cgs

    all_sms = _load_sms(REPO_ROOT / "content" / "factory" / "supermetrics")
    all_views, all_dashboards = _load_dash(
        REPO_ROOT / "content" / "factory" / "views",
        REPO_ROOT / "content" / "factory" / "dashboards",
    )
    all_cgs = _load_cgs(REPO_ROOT / "content" / "factory" / "customgroups")
    return all_sms, all_views, all_dashboards, all_cgs


# ---------------------------------------------------------------------------
# Test 1 — capacity_assessment
# ---------------------------------------------------------------------------

class TestCapacityAssessment:
    """Walk dashboards/capacity_assessment.yaml and verify the full dep graph."""

    @pytest.fixture(scope="class")
    def dep_graph(self):
        from vcfops_common.dep_walker import collect_deps
        all_sms, all_views, all_dashboards, all_cgs = _load_all()
        # Select only the capacity assessment dashboard
        target = [d for d in all_dashboards
                  if "Capacity Assessment" in d.name and "Right-Sizing" in d.name]
        assert len(target) == 1, (
            f"Expected exactly 1 capacity assessment dashboard, got {len(target)}: "
            f"{[d.name for d in target]}"
        )
        return collect_deps(target, all_views, all_sms, all_cgs)

    def test_no_errors(self, dep_graph):
        assert dep_graph.errors == [], (
            f"collect_deps returned errors: {dep_graph.errors}"
        )

    def test_customgroup_present(self, dep_graph):
        """The motivating test: vms_rightsizing_candidates group must be in the graph."""
        cg_names = [cg.name for cg in dep_graph.customgroups]
        assert "[VCF Content Factory] VMs - Right-Sizing Candidates" in cg_names, (
            f"Expected custom group not found. Got: {cg_names}"
        )

    def test_views_present(self, dep_graph):
        """Both views listed in the bundle manifest must be in the dep graph."""
        view_names = {v.name for v in dep_graph.views}
        expected = {
            "[VCF Content Factory] Cluster Capacity Overview",
            "[VCF Content Factory] VM Right-Sizing Candidates",
        }
        missing = expected - view_names
        assert not missing, (
            f"Missing views in dep graph: {missing}. Got: {view_names}"
        )
        assert len(dep_graph.views) == 2, (
            f"Expected exactly 2 views, got {len(dep_graph.views)}: {view_names}"
        )

    def test_supermetrics_count(self, dep_graph):
        """All 11 SMs listed in the bundle manifest must be in the dep graph.

        The walker may find MORE than 11 if it surfaces SM refs directly from
        dashboard Scoreboard widget metric keys (e.g. cluster_reclaimable_*
        are referenced in the rightsizing_kpis Scoreboard but were not
        explicitly listed in the bundle manifest). We assert >= 11 and that
        every bundle-listed SM name is present.
        """
        sm_names = {sm.name for sm in dep_graph.supermetrics}
        sm_count = len(dep_graph.supermetrics)
        assert sm_count >= 11, (
            f"Expected at least 11 super metrics (bundle manifest), got {sm_count}. "
            f"Names: {sorted(sm_names)}"
        )
        # All 11 bundle-manifest SMs must be present
        bundle_sms = {
            "[VCF Content Factory] Cluster - CPU Free % After HA",
            "[VCF Content Factory] Cluster - Memory Free % After HA",
            "[VCF Content Factory] Cluster - VMs That Fit (CPU, demand-based)",
            "[VCF Content Factory] Cluster - VMs That Fit (Memory, allocation-based)",
            "[VCF Content Factory] Cluster - Oversized VM Count",
            "[VCF Content Factory] Cluster - Undersized VM Count",
            "[VCF Content Factory] Cluster - Idle VM Count",
            "[VCF Content Factory] VM - Target vCPUs (oversized)",
            "[VCF Content Factory] VM - Target Memory GB (oversized)",
            "[VCF Content Factory] VM - Target vCPUs (undersized)",
            "[VCF Content Factory] VM - Target Memory GB (undersized)",
        }
        missing = bundle_sms - sm_names
        assert not missing, (
            f"Bundle-listed SMs missing from dep graph: {missing}"
        )

    def test_supermetrics_names(self, dep_graph):
        """Spot-check a few expected SM names."""
        sm_names = {sm.name for sm in dep_graph.supermetrics}
        # These 4 SMs are referenced by the capacity overview view columns
        # and/or right-sizing view columns.
        for expected in (
            "[VCF Content Factory] Cluster - CPU Free % After HA",
            "[VCF Content Factory] VM - Target vCPUs (oversized)",
            "[VCF Content Factory] VM - Target Memory GB (oversized)",
        ):
            assert expected in sm_names, (
                f"Expected SM '{expected}' not found. Got: {sm_names}"
            )


# ---------------------------------------------------------------------------
# Test 2 — demand_driven_capacity_v2 (sanity check — no customgroups or SMs)
# ---------------------------------------------------------------------------

class TestDemandDrivenCapacityV2:
    """Walk dashboards/demand_driven_capacity_v2.yaml — no SMs, no customgroups."""

    @pytest.fixture(scope="class")
    def dep_graph(self):
        from vcfops_common.dep_walker import collect_deps
        all_sms, all_views, all_dashboards, all_cgs = _load_all()
        target = [d for d in all_dashboards if "Demand-Driven Capacity" in d.name]
        assert len(target) == 1, (
            f"Expected 1 demand-driven capacity dashboard, got {len(target)}"
        )
        return collect_deps(target, all_views, all_sms, all_cgs)

    def test_no_errors(self, dep_graph):
        assert dep_graph.errors == [], (
            f"collect_deps returned errors: {dep_graph.errors}"
        )

    def test_four_views(self, dep_graph):
        """demand_driven_capacity_v2 has 4 View widgets."""
        assert len(dep_graph.views) == 4, (
            f"Expected 4 views, got {len(dep_graph.views)}: "
            f"{[v.name for v in dep_graph.views]}"
        )

    def test_zero_supermetrics(self, dep_graph):
        """No view in demand_driven_capacity_v2 references any SM."""
        assert len(dep_graph.supermetrics) == 0, (
            f"Expected 0 SMs, got {len(dep_graph.supermetrics)}: "
            f"{[sm.name for sm in dep_graph.supermetrics]}"
        )

    def test_zero_customgroups(self, dep_graph):
        """demand_driven_capacity_v2 has no customgroup-scoped views."""
        assert len(dep_graph.customgroups) == 0, (
            f"Expected 0 custom groups, got {len(dep_graph.customgroups)}: "
            f"{[cg.name for cg in dep_graph.customgroups]}"
        )


# ---------------------------------------------------------------------------
# Test 3 — missing customgroup ref surfaces a clear error
# ---------------------------------------------------------------------------

def test_missing_customgroup_error():
    """collect_deps emits an error when a view references a non-existent customgroup."""
    from vcfops_dashboards.loader import Dashboard, Widget, ViewDef, ViewColumn
    from vcfops_common.dep_walker import collect_deps

    # Build a view that references a group not present in the corpus
    view = ViewDef(
        id="00000000-0000-0000-0000-000000000001",
        name="[VCF Content Factory] Test View",
        description="Test",
        adapter_kind="VMWARE",
        resource_kind="VirtualMachine",
        columns=[ViewColumn(attribute="cpu|usage_average", display_name="CPU")],
        customgroups=["[VCF Content Factory] Nonexistent Group"],
    )

    widget = Widget(
        local_id="w1",
        type="View",
        title="Test",
        coords={"x": 1, "y": 1, "w": 6, "h": 6},
        view_name="[VCF Content Factory] Test View",
        dashboard_name="[VCF Content Factory] Test Dashboard",
    )
    dashboard = Dashboard(
        id="00000000-0000-0000-0000-000000000002",
        name="[VCF Content Factory] Test Dashboard",
        description="Test",
        widgets=[widget],
        interactions=[],
    )

    graph = collect_deps([dashboard], [view], [], [])  # empty customgroups corpus
    assert graph.errors, "Expected an error for missing customgroup"
    assert any("Nonexistent Group" in e for e in graph.errors), (
        f"Error should mention the missing group name. Got: {graph.errors}"
    )


# ---------------------------------------------------------------------------
# Test 4 — customgroup recursion guard (no infinite loop)
# ---------------------------------------------------------------------------

def test_customgroup_recursion_guard():
    """collect_deps does not infinite-loop when a CG relationship references itself."""
    from vcfops_dashboards.loader import Dashboard, Widget
    from vcfops_customgroups.loader import CustomGroupDef
    from vcfops_common.dep_walker import collect_deps

    # Build a minimal view that references a customgroup
    from vcfops_dashboards.loader import ViewDef, ViewColumn
    view = ViewDef(
        id="00000000-0000-0000-0000-000000000010",
        name="[VCF Content Factory] Recursive Test View",
        description="",
        adapter_kind="VMWARE",
        resource_kind="VirtualMachine",
        columns=[ViewColumn(attribute="cpu|usage_average", display_name="CPU")],
        customgroups=["[VCF Content Factory] Group A"],
    )

    # Build a customgroup that has a relationship rule referencing itself (pathological)
    cg_a = CustomGroupDef(
        name="[VCF Content Factory] Group A",
        rules=[{
            "resource_kind": "VirtualMachine",
            "adapter_kind": "VMWARE",
            "relationship": [{"relation": "DESCENDANT", "name": "[VCF Content Factory] Group A", "op": "EQ"}],
        }],
    )

    widget = Widget(
        local_id="w1",
        type="View",
        title="Test",
        coords={"x": 1, "y": 1, "w": 6, "h": 6},
        view_name="[VCF Content Factory] Recursive Test View",
        dashboard_name="[VCF Content Factory] Recursive Test Dashboard",
    )
    dashboard = Dashboard(
        id="00000000-0000-0000-0000-000000000011",
        name="[VCF Content Factory] Recursive Test Dashboard",
        description="",
        widgets=[widget],
        interactions=[],
    )

    # Must complete without infinite loop
    graph = collect_deps([dashboard], [view], [], [cg_a])
    assert not graph.errors, f"Unexpected errors: {graph.errors}"
    assert len(graph.customgroups) == 1
    assert graph.customgroups[0].name == "[VCF Content Factory] Group A"
