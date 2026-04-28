"""Phase 3 dep_walker tests — project-scope awareness.

Covers:
  D1 — Provenance population: loaded content objects carry the correct
       provenance string ("factory", third-party slug, or "").

  D2 — Auto-detect project_scope from starting dashboard provenance.

  D3 — Factory scope: factory dashboard can reference factory components;
       factory dashboard referencing a third-party component is an error.

  D4 — Third-party scope (self-contained): third-party dashboard referencing
       only its own project's components passes with no errors.

  D5 — Third-party scope + cross-links: a third-party dashboard referencing a
       factory component that appears in the project's cross_links is allowed.

  D6 — Third-party scope + cross-links violation: a third-party dashboard
       referencing a factory component NOT in cross_links is an error.

  D7 — Cross-project error: third-party dashboard referencing another
       third-party project's component is an error.

  D8 — Empty provenance pass-through: components with no provenance (test
       fixtures constructed without a source_path) are always accepted
       regardless of scope — the scope boundary only applies to objects
       whose provenance is known.

  D9 — Explicit project_scope overrides auto-detection.

  D10 — Real repo: factory dashboards have provenance=="factory"; idps-planner
        dashboards have provenance=="idps-planner".

  D11 — check_project_membership uses scope-aware walker (integration).

All tests are pure-Python using tmp_path fixtures (or the real repo for D10/D11).
No network calls; no content YAML is mutated.
"""
from __future__ import annotations

import textwrap
import uuid as _uuid_mod
from pathlib import Path
from typing import List

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n")
    return path


def _make_sm(sm_dir: Path, stem: str, name: str):
    """Write a minimal SM YAML and return a loaded SuperMetricDef."""
    sm_dir.mkdir(parents=True, exist_ok=True)
    p = sm_dir / f"{stem}.yaml"
    p.write_text(yaml.dump({
        "name": name,
        "formula": "${this, metric=cpu|usage_average}",
        "resource_kinds": [{"resource_kind_key": "VirtualMachine", "adapter_kind_key": "VMWARE"}],
    }, default_flow_style=False))
    from vcfops_supermetrics.loader import load_file
    return load_file(p, enforce_framework_prefix=False)


def _make_view(views_dir: Path, stem: str, sm_uuid: str):
    """Write a minimal view YAML referencing one SM and return a loaded ViewDef."""
    views_dir.mkdir(parents=True, exist_ok=True)
    p = views_dir / f"{stem}.yaml"
    p.write_text(yaml.dump({
        "name": f"View {stem}",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
        "columns": [{"attribute": f"Super Metric|sm_{sm_uuid}", "display_name": "Metric"}],
    }, default_flow_style=False))
    from vcfops_dashboards.loader import load_view
    return load_view(p, enforce_framework_prefix=False)


def _make_dashboard(dash_dir: Path, stem: str, view_name: str):
    """Write a minimal dashboard YAML referencing a view and return a loaded Dashboard."""
    dash_dir.mkdir(parents=True, exist_ok=True)
    p = dash_dir / f"{stem}.yaml"
    p.write_text(yaml.dump({
        "name": f"Dashboard {stem}",
        "widgets": [{
            "id": str(_uuid_mod.uuid4()),
            "type": "View",
            "title": f"Widget for {view_name}",
            "coords": {"x": 1, "y": 1, "w": 6, "h": 6},
            "view": view_name,
        }],
    }, default_flow_style=False))
    from vcfops_dashboards.loader import load_dashboard
    return load_dashboard(p, enforce_framework_prefix=False, default_name_path="")


def _make_project_yaml(proj_dir: Path, slug: str, cross_links: dict = None) -> None:
    """Write a minimal PROJECT.yaml with optional cross_links."""
    proj_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "name": slug,
        "display_name": f"{slug} Display",
        "factory_native": False,
        "author": "Test Author",
        "license": "MIT",
        "description": "A test project.",
    }
    if cross_links:
        data["cross_links"] = cross_links
    (proj_dir / "PROJECT.yaml").write_text(yaml.dump(data, default_flow_style=False))


# ---------------------------------------------------------------------------
# D1 — Provenance population
# ---------------------------------------------------------------------------

class TestProvenancePopulation:
    """D1: loaded content objects carry the correct provenance string."""

    def test_factory_sm_has_factory_provenance(self, tmp_path):
        """SM loaded from content/supermetrics/ gets provenance='factory'."""
        sm = _make_sm(tmp_path / "content" / "supermetrics", "my_sm", "My SM")
        assert sm.provenance == "factory", (
            f"Expected provenance='factory', got {sm.provenance!r}"
        )

    def test_thirdparty_sm_has_slug_provenance(self, tmp_path):
        """SM loaded from third_party/proj-a/supermetrics/ gets provenance='proj-a'."""
        sm = _make_sm(tmp_path / "third_party" / "proj-a" / "supermetrics", "tp_sm", "TP SM")
        assert sm.provenance == "proj-a", (
            f"Expected provenance='proj-a', got {sm.provenance!r}"
        )

    def test_factory_view_has_factory_provenance(self, tmp_path):
        """ViewDef loaded from content/views/ gets provenance='factory'."""
        sm = _make_sm(tmp_path / "content" / "supermetrics", "my_sm", "My SM")
        view = _make_view(tmp_path / "content" / "views", "my_view", sm.id)
        assert view.provenance == "factory", (
            f"Expected provenance='factory', got {view.provenance!r}"
        )

    def test_thirdparty_view_has_slug_provenance(self, tmp_path):
        """ViewDef loaded from third_party/proj-a/views/ gets provenance='proj-a'."""
        sm = _make_sm(tmp_path / "third_party" / "proj-a" / "supermetrics", "tp_sm", "TP SM")
        view = _make_view(tmp_path / "third_party" / "proj-a" / "views", "tp_view", sm.id)
        assert view.provenance == "proj-a", (
            f"Expected provenance='proj-a', got {view.provenance!r}"
        )

    def test_factory_dashboard_has_factory_provenance(self, tmp_path):
        """Dashboard loaded from content/dashboards/ gets provenance='factory'."""
        sm = _make_sm(tmp_path / "content" / "supermetrics", "my_sm", "My SM")
        view = _make_view(tmp_path / "content" / "views", "my_view", sm.id)
        dash = _make_dashboard(tmp_path / "content" / "dashboards", "my_dash", view.name)
        assert dash.provenance == "factory", (
            f"Expected provenance='factory', got {dash.provenance!r}"
        )

    def test_thirdparty_dashboard_has_slug_provenance(self, tmp_path):
        """Dashboard loaded from third_party/proj-a/dashboards/ gets provenance='proj-a'."""
        sm = _make_sm(tmp_path / "third_party" / "proj-a" / "supermetrics", "tp_sm", "TP SM")
        view = _make_view(tmp_path / "third_party" / "proj-a" / "views", "tp_view", sm.id)
        dash = _make_dashboard(
            tmp_path / "third_party" / "proj-a" / "dashboards", "tp_dash", view.name
        )
        assert dash.provenance == "proj-a", (
            f"Expected provenance='proj-a', got {dash.provenance!r}"
        )

    def test_explicit_path_outside_trees_gets_empty_provenance(self, tmp_path):
        """A YAML loaded from a path outside content/ and third_party/ gets provenance=''."""
        # tmp_path has no 'content/' or 'third_party/' children
        scratch_dir = tmp_path / "scratch" / "supermetrics"
        sm = _make_sm(scratch_dir, "scratch_sm", "Scratch SM")
        assert sm.provenance == "", (
            f"Expected provenance='', got {sm.provenance!r}"
        )

    def test_different_project_slugs_are_distinct(self, tmp_path):
        """Two third-party SMs get different slugs based on their project dir."""
        sm_a = _make_sm(tmp_path / "third_party" / "proj-a" / "supermetrics", "sm_a", "SM A")
        sm_b = _make_sm(tmp_path / "third_party" / "proj-b" / "supermetrics", "sm_b", "SM B")
        assert sm_a.provenance == "proj-a"
        assert sm_b.provenance == "proj-b"


# ---------------------------------------------------------------------------
# D2 — Auto-detect project_scope
# ---------------------------------------------------------------------------

class TestAutoDetectScope:
    """D2: collect_deps auto-detects project_scope from starting dashboard provenance."""

    def test_auto_detect_factory_scope(self, tmp_path):
        """Factory dashboard with no explicit scope still uses factory scope internally."""
        from vcfops_common.dep_walker import collect_deps

        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)
        dash_f = _make_dashboard(tmp_path / "content" / "dashboards", "dash_f", view_f.name)

        # No project_scope passed — should auto-detect "factory"
        graph = collect_deps([dash_f], [view_f], [sm_f], [])
        assert graph.errors == [], (
            f"Factory self-contained walk should produce no errors: {graph.errors}"
        )
        assert len(graph.views) == 1
        assert len(graph.supermetrics) == 1

    def test_auto_detect_thirdparty_scope(self, tmp_path):
        """Third-party dashboard auto-detects its project slug as scope."""
        from vcfops_common.dep_walker import collect_deps

        proj_dir = tmp_path / "third_party" / "proj-a"
        sm_a = _make_sm(proj_dir / "supermetrics", "sm_a", "SM A")
        view_a = _make_view(proj_dir / "views", "view_a", sm_a.id)
        dash_a = _make_dashboard(proj_dir / "dashboards", "dash_a", view_a.name)

        assert dash_a.provenance == "proj-a"

        # No project_scope passed — auto-detects "proj-a"
        graph = collect_deps([dash_a], [view_a], [sm_a], [])
        assert graph.errors == [], (
            f"Self-contained third-party walk should produce no errors: {graph.errors}"
        )

    def test_auto_detect_mixed_provenance_no_scope(self, tmp_path):
        """Multiple dashboards with different provenances → no auto-detected scope (None)."""
        from vcfops_common.dep_walker import collect_deps

        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)
        dash_f = _make_dashboard(tmp_path / "content" / "dashboards", "dash_f", view_f.name)

        sm_a = _make_sm(tmp_path / "third_party" / "proj-a" / "supermetrics", "sm_a", "SM A")
        view_a = _make_view(tmp_path / "third_party" / "proj-a" / "views", "view_a", sm_a.id)
        dash_a = _make_dashboard(
            tmp_path / "third_party" / "proj-a" / "dashboards", "dash_a", view_a.name
        )

        # Mixed provenances → no scope auto-detected → no scope enforcement
        graph = collect_deps(
            [dash_f, dash_a],
            [view_f, view_a],
            [sm_f, sm_a],
            [],
        )
        assert graph.errors == [], (
            f"Mixed provenance with no scope should produce no errors: {graph.errors}"
        )

    def test_auto_detect_empty_provenance_no_scope(self):
        """Fixture dashboards with empty provenance → no scope auto-detected."""
        from vcfops_common.dep_walker import collect_deps, _auto_detect_scope
        from vcfops_dashboards.loader import Dashboard, Widget

        widget = Widget(
            local_id="w1",
            type="View",
            title="T",
            coords={"x": 1, "y": 1, "w": 6, "h": 6},
            view_name="No View",
            dashboard_name="Fixture Dash",
        )
        dash = Dashboard(
            id="00000000-0000-0000-0000-000000000001",
            name="Fixture Dash",
            description="",
            widgets=[widget],
            interactions=[],
            # no source_path → provenance=""
        )
        assert dash.provenance == "", "Programmatic dashboard should have empty provenance"

        # Auto-detect should return None
        scope = _auto_detect_scope([dash])
        assert scope is None, f"Expected None for empty provenance, got {scope!r}"


# ---------------------------------------------------------------------------
# D3 — Factory scope enforcement
# ---------------------------------------------------------------------------

class TestFactoryScope:
    """D3: factory scope blocks third-party components."""

    def test_factory_scope_allows_factory_components(self, tmp_path):
        """Explicit project_scope='factory' passes for a fully factory dep graph."""
        from vcfops_common.dep_walker import collect_deps

        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)
        dash_f = _make_dashboard(tmp_path / "content" / "dashboards", "dash_f", view_f.name)

        graph = collect_deps([dash_f], [view_f], [sm_f], [], project_scope="factory")
        assert graph.errors == [], f"Factory scope with factory deps should be clean: {graph.errors}"

    def test_factory_scope_blocks_thirdparty_view(self, tmp_path):
        """Explicit project_scope='factory' errors on a third-party view."""
        from vcfops_common.dep_walker import collect_deps

        # Third-party SM and view
        sm_a = _make_sm(tmp_path / "third_party" / "proj-a" / "supermetrics", "sm_a", "SM A")
        view_a = _make_view(tmp_path / "third_party" / "proj-a" / "views", "view_a", sm_a.id)
        # Factory dashboard that references the third-party view
        dash_f = _make_dashboard(tmp_path / "content" / "dashboards", "dash_f", view_a.name)

        graph = collect_deps([dash_f], [view_a], [sm_a], [], project_scope="factory")
        assert graph.errors, "Expected scope violation error"
        assert any("scope violation" in e for e in graph.errors), (
            f"Error should mention 'scope violation': {graph.errors}"
        )
        assert any("proj-a" in e for e in graph.errors), (
            f"Error should mention the offending provenance 'proj-a': {graph.errors}"
        )


# ---------------------------------------------------------------------------
# D4 — Third-party scope (self-contained)
# ---------------------------------------------------------------------------

class TestThirdPartyScopeClean:
    """D4: self-contained third-party project passes with no errors."""

    def test_self_contained_project_passes(self, tmp_path):
        """Third-party project with all deps in same project → no errors."""
        from vcfops_common.dep_walker import collect_deps

        proj_dir = tmp_path / "third_party" / "proj-a"
        sm = _make_sm(proj_dir / "supermetrics", "sm", "SM")
        view = _make_view(proj_dir / "views", "view", sm.id)
        dash = _make_dashboard(proj_dir / "dashboards", "dash", view.name)

        # Pass full corpus (includes both project content — just self here)
        graph = collect_deps([dash], [view], [sm], [], project_scope="proj-a")
        assert graph.errors == [], (
            f"Self-contained project should produce no errors: {graph.errors}"
        )
        assert len(graph.views) == 1
        assert len(graph.supermetrics) == 1


# ---------------------------------------------------------------------------
# D5 — Third-party scope + cross-links allowed
# ---------------------------------------------------------------------------

class TestCrossLinksAllowed:
    """D5: factory component explicitly listed in cross_links is allowed."""

    def test_cross_linked_factory_view_and_sm_allowed(self, tmp_path):
        """Third-party project referencing cross-linked factory view + its SM passes.

        When a factory view is cross-linked, the factory SM it references must also
        be explicitly listed (the walker checks each component independently against
        the cross_links list).
        """
        from vcfops_common.dep_walker import collect_deps, CollectDepsCrossLinks

        # Factory SM and view
        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)

        # Third-party dashboard referencing the factory view
        proj_dir = tmp_path / "third_party" / "proj-a"
        dash_a = _make_dashboard(proj_dir / "dashboards", "dash_a", view_f.name)

        # Both the view and the SM it uses must be listed in cross_links
        cl = CollectDepsCrossLinks(views={view_f.name}, supermetrics={sm_f.name})
        graph = collect_deps(
            [dash_a],
            [view_f],
            [sm_f],
            [],
            project_scope="proj-a",
            cross_links=cl,
        )
        assert graph.errors == [], (
            f"Cross-linked factory view+SM should be allowed: {graph.errors}"
        )
        assert len(graph.views) == 1
        assert graph.views[0].name == view_f.name
        assert len(graph.supermetrics) == 1
        assert graph.supermetrics[0].name == sm_f.name

    def test_cross_linked_factory_view_without_sm_is_partial_error(self, tmp_path):
        """Cross-linking a factory view but not its SM → SM is still a scope violation.

        The cross_links list is explicit — each factory component must be declared
        individually.  Cross-linking a view does NOT grant implicit allowance to the
        factory SMs that view references.
        """
        from vcfops_common.dep_walker import collect_deps, CollectDepsCrossLinks

        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)

        proj_dir = tmp_path / "third_party" / "proj-a"
        dash_a = _make_dashboard(proj_dir / "dashboards", "dash_a", view_f.name)

        # Only the view is cross-linked, not the SM
        cl = CollectDepsCrossLinks(views={view_f.name})
        graph = collect_deps(
            [dash_a],
            [view_f],
            [sm_f],
            [],
            project_scope="proj-a",
            cross_links=cl,
        )
        # The view resolves cleanly (it's cross-linked)
        assert view_f.name in {v.name for v in graph.views}, (
            "Cross-linked view should resolve"
        )
        # The SM is a violation because it's not listed
        assert any("Factory SM" in e for e in graph.errors), (
            f"SM not in cross_links should produce a scope violation: {graph.errors}"
        )

    def test_cross_linked_factory_sm_allowed(self, tmp_path):
        """Third-party project using a cross-linked factory SM via a project view passes."""
        from vcfops_common.dep_walker import collect_deps, CollectDepsCrossLinks

        # Factory SM
        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")

        # Third-party view referencing the factory SM
        proj_dir = tmp_path / "third_party" / "proj-a"
        view_a = _make_view(proj_dir / "views", "view_a", sm_f.id)
        dash_a = _make_dashboard(proj_dir / "dashboards", "dash_a", view_a.name)

        cl = CollectDepsCrossLinks(supermetrics={sm_f.name})
        graph = collect_deps(
            [dash_a],
            [view_a],
            [sm_f],
            [],
            project_scope="proj-a",
            cross_links=cl,
        )
        assert graph.errors == [], (
            f"Cross-linked factory SM should be allowed: {graph.errors}"
        )
        assert len(graph.supermetrics) == 1
        assert graph.supermetrics[0].name == sm_f.name


# ---------------------------------------------------------------------------
# D6 — Cross-links violation
# ---------------------------------------------------------------------------

class TestCrossLinksViolation:
    """D6: factory component NOT in cross_links is an error."""

    def test_unlisted_factory_view_is_error(self, tmp_path):
        """Third-party dashboard referencing factory view not in cross_links → error."""
        from vcfops_common.dep_walker import collect_deps, CollectDepsCrossLinks

        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)

        proj_dir = tmp_path / "third_party" / "proj-a"
        dash_a = _make_dashboard(proj_dir / "dashboards", "dash_a", view_f.name)

        # cross_links is empty — factory view is not allowed
        cl = CollectDepsCrossLinks()
        graph = collect_deps(
            [dash_a],
            [view_f],
            [sm_f],
            [],
            project_scope="proj-a",
            cross_links=cl,
        )
        assert graph.errors, "Expected scope violation error"
        assert any("cross_links" in e for e in graph.errors), (
            f"Error should mention 'cross_links': {graph.errors}"
        )

    def test_unlisted_factory_view_error_no_cross_links_arg(self, tmp_path):
        """Same violation without passing cross_links arg (defaults to None)."""
        from vcfops_common.dep_walker import collect_deps

        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)

        proj_dir = tmp_path / "third_party" / "proj-a"
        dash_a = _make_dashboard(proj_dir / "dashboards", "dash_a", view_f.name)

        # No cross_links arg — factory view still rejected
        graph = collect_deps(
            [dash_a],
            [view_f],
            [sm_f],
            [],
            project_scope="proj-a",
        )
        assert graph.errors, "Expected scope violation error with no cross_links"
        assert any("cross_links" in e for e in graph.errors), (
            f"Error should mention 'cross_links': {graph.errors}"
        )

    def test_partial_cross_link_only_listed_allowed(self, tmp_path):
        """Only the view listed in cross_links is allowed; unlisted factory view is rejected."""
        from vcfops_common.dep_walker import collect_deps, CollectDepsCrossLinks

        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f1 = _make_view(tmp_path / "content" / "views", "view_f1", sm_f.id)
        view_f2 = _make_view(tmp_path / "content" / "views", "view_f2", sm_f.id)

        proj_dir = tmp_path / "third_party" / "proj-a"
        sm_a = _make_sm(proj_dir / "supermetrics", "sm_a", "SM A")
        view_a = _make_view(proj_dir / "views", "view_a", sm_a.id)

        # Dashboard references both view_f1 (allowed) and view_f2 (not allowed)
        proj_dir.mkdir(parents=True, exist_ok=True)
        dash_dir = proj_dir / "dashboards"
        dash_dir.mkdir(parents=True, exist_ok=True)
        p = dash_dir / "multi_view_dash.yaml"
        p.write_text(yaml.dump({
            "name": "Dashboard multi_view_dash",
            "widgets": [
                {
                    "id": str(_uuid_mod.uuid4()),
                    "type": "View",
                    "title": "f1",
                    "coords": {"x": 1, "y": 1, "w": 6, "h": 6},
                    "view": view_f1.name,
                },
                {
                    "id": str(_uuid_mod.uuid4()),
                    "type": "View",
                    "title": "a",
                    "coords": {"x": 7, "y": 1, "w": 6, "h": 6},
                    "view": view_a.name,
                },
                {
                    "id": str(_uuid_mod.uuid4()),
                    "type": "View",
                    "title": "f2",
                    "coords": {"x": 1, "y": 7, "w": 6, "h": 6},
                    "view": view_f2.name,
                },
            ],
        }, default_flow_style=False))
        from vcfops_dashboards.loader import load_dashboard
        dash = load_dashboard(p, enforce_framework_prefix=False, default_name_path="")

        cl = CollectDepsCrossLinks(views={view_f1.name})  # only f1 is cross-linked

        graph = collect_deps(
            [dash],
            [view_f1, view_f2, view_a],
            [sm_f, sm_a],
            [],
            project_scope="proj-a",
            cross_links=cl,
        )
        # view_a (same project) + view_f1 (cross-linked) are fine
        # view_f2 (factory, not cross-linked) is a violation
        assert graph.errors, "Expected 1 scope violation for view_f2"
        assert any(view_f2.name in e for e in graph.errors), (
            f"Error should mention view_f2: {graph.errors}"
        )
        # view_f1 and view_a should be resolved (2 views in graph)
        resolved_names = {v.name for v in graph.views}
        assert view_f1.name in resolved_names, "view_f1 (cross-linked) should be resolved"
        assert view_a.name in resolved_names, "view_a (same project) should be resolved"
        assert view_f2.name not in resolved_names, "view_f2 (violation) should NOT be resolved"


# ---------------------------------------------------------------------------
# D7 — Cross-project error
# ---------------------------------------------------------------------------

class TestCrossProjectError:
    """D7: third-party dashboard referencing another project's component is an error."""

    def test_cross_project_view_is_error(self, tmp_path):
        """proj-a dashboard referencing proj-b's view is a scope violation."""
        from vcfops_common.dep_walker import collect_deps

        proj_b = tmp_path / "third_party" / "proj-b"
        sm_b = _make_sm(proj_b / "supermetrics", "sm_b", "SM B")
        view_b = _make_view(proj_b / "views", "view_b", sm_b.id)

        proj_a = tmp_path / "third_party" / "proj-a"
        dash_a = _make_dashboard(proj_a / "dashboards", "dash_a", view_b.name)

        # proj-a dashboard referencing proj-b view
        graph = collect_deps(
            [dash_a],
            [view_b],
            [sm_b],
            [],
            project_scope="proj-a",
        )
        assert graph.errors, "Expected cross-project scope violation"
        assert any("proj-b" in e for e in graph.errors), (
            f"Error should mention the other project 'proj-b': {graph.errors}"
        )
        assert any("proj-a" in e for e in graph.errors), (
            f"Error should mention the scope project 'proj-a': {graph.errors}"
        )

    def test_cross_project_sm_is_error(self, tmp_path):
        """proj-a view referencing proj-b's SM is a scope violation."""
        from vcfops_common.dep_walker import collect_deps

        proj_b = tmp_path / "third_party" / "proj-b"
        sm_b = _make_sm(proj_b / "supermetrics", "sm_b", "SM B")

        proj_a = tmp_path / "third_party" / "proj-a"
        view_a = _make_view(proj_a / "views", "view_a", sm_b.id)
        dash_a = _make_dashboard(proj_a / "dashboards", "dash_a", view_a.name)

        graph = collect_deps(
            [dash_a],
            [view_a],
            [sm_b],
            [],
            project_scope="proj-a",
        )
        assert graph.errors, "Expected cross-project SM scope violation"
        assert any("proj-b" in e for e in graph.errors), (
            f"Error should mention offending project 'proj-b': {graph.errors}"
        )


# ---------------------------------------------------------------------------
# D8 — Empty provenance pass-through
# ---------------------------------------------------------------------------

class TestEmptyProvenancePassThrough:
    """D8: objects with empty provenance are always accepted regardless of scope."""

    def test_fixture_objects_with_no_source_path_always_accepted(self):
        """Programmatically constructed objects (no source_path) pass any scope."""
        from vcfops_common.dep_walker import collect_deps
        from vcfops_dashboards.loader import ViewDef, ViewColumn, Dashboard, Widget
        from vcfops_supermetrics.loader import SuperMetricDef

        # Build a SM, view, and dashboard without source_path → empty provenance
        sm = SuperMetricDef(
            id="11111111-2222-3333-4444-555555555555",
            name="Fixture SM",
            formula="${this, metric=cpu|usage_average}",
            resource_kinds=[{"resourceKindKey": "VirtualMachine", "adapterKindKey": "VMWARE"}],
        )
        assert sm.provenance == "", "Programmatic SM should have empty provenance"

        view = ViewDef(
            id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="Fixture View",
            description="",
            adapter_kind="VMWARE",
            resource_kind="VirtualMachine",
            columns=[ViewColumn(
                attribute=f"Super Metric|sm_{sm.id}",
                display_name="Metric",
            )],
        )
        assert view.provenance == "", "Programmatic ViewDef should have empty provenance"

        widget = Widget(
            local_id="w1",
            type="View",
            title="Widget",
            coords={"x": 1, "y": 1, "w": 6, "h": 6},
            view_name=view.name,
            dashboard_name="Fixture Dash",
        )
        dash = Dashboard(
            id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            name="Fixture Dash",
            description="",
            widgets=[widget],
            interactions=[],
        )
        assert dash.provenance == "", "Programmatic Dashboard should have empty provenance"

        # With an arbitrary project_scope, fixture objects should still resolve
        graph = collect_deps(
            [dash],
            [view],
            [sm],
            [],
            project_scope="some-project",
        )
        assert graph.errors == [], (
            f"Fixture objects with empty provenance should be scope-transparent: "
            f"{graph.errors}"
        )
        assert len(graph.views) == 1
        assert len(graph.supermetrics) == 1


# ---------------------------------------------------------------------------
# D9 — Explicit project_scope overrides auto-detection
# ---------------------------------------------------------------------------

class TestExplicitScopeOverridesAutoDetect:
    """D9: explicit project_scope overrides the auto-detected scope."""

    def test_explicit_scope_forces_rejection_of_sibling_project(self, tmp_path):
        """An explicit scope forces scope enforcement even on a multi-dash corpus."""
        from vcfops_common.dep_walker import collect_deps

        proj_a = tmp_path / "third_party" / "proj-a"
        sm_a = _make_sm(proj_a / "supermetrics", "sm_a", "SM A")
        view_a = _make_view(proj_a / "views", "view_a", sm_a.id)

        proj_b = tmp_path / "third_party" / "proj-b"
        sm_b = _make_sm(proj_b / "supermetrics", "sm_b", "SM B")
        view_b = _make_view(proj_b / "views", "view_b", sm_b.id)
        dash_b = _make_dashboard(proj_b / "dashboards", "dash_b", view_b.name)

        # Explicitly scope to proj-a even though the dashboard is from proj-b
        # This would normally auto-detect as "proj-b", but explicit wins.
        graph = collect_deps(
            [dash_b],
            [view_a, view_b],
            [sm_a, sm_b],
            [],
            project_scope="proj-a",  # explicit override
        )
        # view_b has provenance "proj-b" ≠ "proj-a" → scope violation
        assert graph.errors, (
            "Expected scope violation because explicit scope='proj-a' "
            "but view_b is from proj-b"
        )

    def test_undetectable_scope_skips_enforcement(self, tmp_path):
        """When scope cannot be auto-detected (mixed provenances), enforcement is disabled.

        Passing project_scope=None with two dashboards from different projects
        results in no auto-detected scope → no enforcement → cross-project deps
        resolve cleanly.
        """
        from vcfops_common.dep_walker import collect_deps

        proj_a = tmp_path / "third_party" / "proj-a"
        sm_a = _make_sm(proj_a / "supermetrics", "sm_a", "SM A")
        view_a = _make_view(proj_a / "views", "view_a", sm_a.id)
        dash_a = _make_dashboard(proj_a / "dashboards", "dash_a", view_a.name)

        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)
        dash_f = _make_dashboard(tmp_path / "content" / "dashboards", "dash_f", view_f.name)

        # Two dashboards with different provenances → auto-detect returns None → no enforcement
        graph = collect_deps(
            [dash_a, dash_f],
            [view_a, view_f],
            [sm_a, sm_f],
            [],
            project_scope=None,  # auto-detect will find mixed → None → no enforcement
        )
        assert graph.errors == [], (
            f"Mixed-provenance corpus with no scope should produce no errors: {graph.errors}"
        )
        assert len(graph.views) == 2


# ---------------------------------------------------------------------------
# D10 — Real repo provenance
# ---------------------------------------------------------------------------

class TestRealRepoProvenance:
    """D10: real repo content has correct provenance strings."""

    def test_factory_dashboards_have_factory_provenance(self):
        """All dashboards under content/dashboards/ have provenance='factory'."""
        from vcfops_dashboards.loader import load_all

        views, dashboards = load_all(
            REPO_ROOT / "content" / "views",
            REPO_ROOT / "content" / "dashboards",
        )
        for dash in dashboards:
            assert dash.provenance == "factory", (
                f"Dashboard '{dash.name}' has provenance={dash.provenance!r}, "
                f"expected 'factory'"
            )

    def test_factory_views_have_factory_provenance(self):
        """All views under content/views/ have provenance='factory'."""
        from vcfops_dashboards.loader import load_all

        views, _ = load_all(
            REPO_ROOT / "content" / "views",
            REPO_ROOT / "content" / "dashboards",
        )
        for view in views:
            assert view.provenance == "factory", (
                f"View '{view.name}' has provenance={view.provenance!r}, "
                f"expected 'factory'"
            )

    def test_idps_planner_dashboards_have_slug_provenance(self):
        """idps-planner dashboards have provenance='idps-planner'."""
        idps_dir = REPO_ROOT / "third_party" / "idps-planner"
        if not idps_dir.exists():
            pytest.skip("idps-planner not present")

        dash_dir = idps_dir / "dashboards"
        if not dash_dir.exists():
            pytest.skip("idps-planner has no dashboards/")

        from vcfops_dashboards.loader import load_dashboard
        for p in sorted(dash_dir.rglob("*.y*ml")):
            dash = load_dashboard(p, enforce_framework_prefix=False, default_name_path="")
            assert dash.provenance == "idps-planner", (
                f"Dashboard '{dash.name}' (path={p}) has provenance="
                f"{dash.provenance!r}, expected 'idps-planner'"
            )

    def test_factory_supermetrics_have_factory_provenance(self):
        """All SMs under content/supermetrics/ have provenance='factory'."""
        from vcfops_supermetrics.loader import load_dir

        sms = load_dir(REPO_ROOT / "content" / "supermetrics")
        for sm in sms:
            assert sm.provenance == "factory", (
                f"SM '{sm.name}' has provenance={sm.provenance!r}, "
                f"expected 'factory'"
            )


# ---------------------------------------------------------------------------
# D11 — check_project_membership integration
# ---------------------------------------------------------------------------

class TestCheckProjectMembershipIntegration:
    """D11: check_project_membership uses the scope-aware walker."""

    def test_self_contained_project_no_errors(self, tmp_path):
        """Self-contained third-party project passes membership check."""
        from vcfops_packaging.project import check_project_membership

        tp = tmp_path / "third_party"
        proj_dir = tp / "proj-a"
        _make_project_yaml(proj_dir, "proj-a")
        proj_dir.mkdir(parents=True, exist_ok=True)

        sm = _make_sm(proj_dir / "supermetrics", "sm", "SM A")
        view = _make_view(proj_dir / "views", "view", sm.id)
        dash = _make_dashboard(proj_dir / "dashboards", "dash", view.name)

        errors = check_project_membership(
            dashboards=[dash],
            all_views=[view],
            all_supermetrics=[sm],
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert errors == [], f"Self-contained project should pass: {errors}"

    def test_cross_factory_dep_without_cross_links_is_error(self, tmp_path):
        """Third-party project referencing factory content without cross_links → error."""
        from vcfops_packaging.project import check_project_membership

        tp = tmp_path / "third_party"
        proj_dir = tp / "proj-a"
        _make_project_yaml(proj_dir, "proj-a")  # no cross_links
        proj_dir.mkdir(parents=True, exist_ok=True)

        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)
        dash_a = _make_dashboard(proj_dir / "dashboards", "dash_a", view_f.name)

        errors = check_project_membership(
            dashboards=[dash_a],
            all_views=[view_f],
            all_supermetrics=[sm_f],
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert errors, "Expected boundary error for factory dep without cross_links"
        assert any("proj-a" in e for e in errors), (
            f"Error should mention the project: {errors}"
        )

    def test_cross_factory_dep_with_cross_links_is_ok(self, tmp_path):
        """Third-party project referencing factory content listed in cross_links → OK.

        Both the view and the SM it references must be listed in cross_links,
        since each factory component is checked independently.
        """
        from vcfops_packaging.project import check_project_membership

        tp = tmp_path / "third_party"
        proj_dir = tp / "proj-a"

        sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)

        # Write PROJECT.yaml with both view_f and sm_f in cross_links
        _make_project_yaml(proj_dir, "proj-a", cross_links={
            "views": [view_f.name],
            "supermetrics": [sm_f.name],
        })

        dash_a = _make_dashboard(proj_dir / "dashboards", "dash_a", view_f.name)

        errors = check_project_membership(
            dashboards=[dash_a],
            all_views=[view_f],
            all_supermetrics=[sm_f],
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert errors == [], (
            f"Cross-linked factory dep should pass: {errors}"
        )

    def test_factory_native_dashboard_unconstrained(self, tmp_path):
        """Factory-native dashboards are not subject to the boundary check."""
        from vcfops_packaging.project import check_project_membership

        tp = tmp_path / "third_party"

        sm = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
        view = _make_view(tmp_path / "content" / "views", "view_f", sm.id)
        dash = _make_dashboard(tmp_path / "content" / "dashboards", "dash_f", view.name)

        errors = check_project_membership(
            dashboards=[dash],
            all_views=[view],
            all_supermetrics=[sm],
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert errors == [], (
            f"Factory dashboard should be unconstrained: {errors}"
        )

    def test_cross_project_dep_is_error(self, tmp_path):
        """Third-party dashboard pulling in another third-party project's view → error."""
        from vcfops_packaging.project import check_project_membership

        tp = tmp_path / "third_party"

        proj_b = tp / "proj-b"
        _make_project_yaml(proj_b, "proj-b")
        proj_b.mkdir(parents=True, exist_ok=True)
        sm_b = _make_sm(proj_b / "supermetrics", "sm_b", "SM B")
        view_b = _make_view(proj_b / "views", "view_b", sm_b.id)

        proj_a = tp / "proj-a"
        _make_project_yaml(proj_a, "proj-a")
        proj_a.mkdir(parents=True, exist_ok=True)
        dash_a = _make_dashboard(proj_a / "dashboards", "dash_a", view_b.name)

        errors = check_project_membership(
            dashboards=[dash_a],
            all_views=[view_b],
            all_supermetrics=[sm_b],
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert errors, "Expected cross-project boundary error"
        assert any("proj-a" in e for e in errors), (
            f"Error should mention proj-a: {errors}"
        )

    def test_real_repo_idps_planner_still_clean(self):
        """Real repo: idps-planner is still self-contained under scope-aware check."""
        from vcfops_packaging.project import check_project_membership
        from vcfops_dashboards.loader import load_view, load_dashboard
        from vcfops_supermetrics.loader import load_dir as load_sm_dir

        import warnings

        tp = REPO_ROOT / "third_party"
        proj = tp / "idps-planner"

        if not proj.exists():
            pytest.skip("idps-planner not present")

        views = []
        for p in sorted((proj / "views").rglob("*.y*ml")) if (proj / "views").exists() else []:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    views.append(load_view(p, enforce_framework_prefix=False))
                except Exception:
                    pass

        dashboards = []
        for p in sorted((proj / "dashboards").rglob("*.y*ml")) if (proj / "dashboards").exists() else []:
            try:
                dashboards.append(
                    load_dashboard(p, enforce_framework_prefix=False, default_name_path="")
                )
            except Exception:
                pass

        sms = []
        if (proj / "supermetrics").exists():
            try:
                sms = load_sm_dir(proj / "supermetrics", enforce_framework_prefix=False)
            except Exception:
                pass

        errors = check_project_membership(
            dashboards=dashboards,
            all_views=views,
            all_supermetrics=sms,
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert errors == [], (
            f"idps-planner should be self-contained under scope-aware check:\n"
            + "\n".join(errors)
        )


# ---------------------------------------------------------------------------
# Sample error output documentation (not assertions — just exercise the paths)
# ---------------------------------------------------------------------------

def test_sample_error_outputs(tmp_path, capsys):
    """Run all three new walker error types and print their messages for the record.

    This test exercises:
      (a) Factory dashboard referencing third-party component
      (b) Third-party dashboard referencing factory component not in cross_links
      (c) Third-party dashboard referencing another third-party component
    """
    from vcfops_common.dep_walker import collect_deps

    # (a) Factory dashboard + third-party view
    sm_tp = _make_sm(tmp_path / "third_party" / "proj-a" / "supermetrics", "sm_tp", "TP SM")
    view_tp = _make_view(tmp_path / "third_party" / "proj-a" / "views", "view_tp", sm_tp.id)
    dash_factory = _make_dashboard(tmp_path / "content" / "dashboards", "dash_f", view_tp.name)
    g_a = collect_deps([dash_factory], [view_tp], [sm_tp], [], project_scope="factory")
    print("\n[A] Factory-scope pulling third-party view:")
    for e in g_a.errors:
        print(f"    {e}")
    assert g_a.errors

    # (b) Third-party dashboard + factory view (not cross-linked)
    sm_f = _make_sm(tmp_path / "content" / "supermetrics", "sm_f", "Factory SM")
    view_f = _make_view(tmp_path / "content" / "views", "view_f", sm_f.id)
    dash_tp = _make_dashboard(
        tmp_path / "third_party" / "proj-a" / "dashboards", "dash_tp", view_f.name
    )
    g_b = collect_deps([dash_tp], [view_f], [sm_f], [], project_scope="proj-a")
    print("\n[B] Third-party scope pulling factory view (not cross-linked):")
    for e in g_b.errors:
        print(f"    {e}")
    assert g_b.errors

    # (c) Third-party dashboard + other project's view
    sm_b = _make_sm(tmp_path / "third_party" / "proj-b" / "supermetrics", "sm_b", "SM B")
    view_b = _make_view(tmp_path / "third_party" / "proj-b" / "views", "view_b", sm_b.id)
    dash_a = _make_dashboard(
        tmp_path / "third_party" / "proj-a" / "dashboards", "cross_proj_dash", view_b.name
    )
    g_c = collect_deps([dash_a], [view_b], [sm_b], [], project_scope="proj-a")
    print("\n[C] Third-party proj-a pulling proj-b view:")
    for e in g_c.errors:
        print(f"    {e}")
    assert g_c.errors
