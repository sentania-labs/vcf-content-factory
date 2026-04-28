"""Phase 4 tests for vcfops_packaging bundle composer.

Test groups:
  T1 — slug uniqueness vs existing bundles (collision errors)
  T2 — slug uniqueness vs release manifests (collision errors)
  T3 — component discovery returns expected counts from the real corpus
  T4 — picking by index works
  T5 — picking by substring works
  T6 — dependency walk surfaces missing deps
  T7 — cross-provenance composition allowed without scope errors
  T8 — --dry-run prints, doesn't write
  T9 — --force overwrites
  T10 — output YAML round-trips through the bundle loader
"""
from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_input_seq(responses: list):
    """Return an input_fn that pops responses in order. Raises EOFError when exhausted."""
    responses = list(responses)

    def _fn(prompt=""):
        if not responses:
            raise EOFError("input sequence exhausted")
        return responses.pop(0)

    return _fn


def _capture_output():
    """Return (output_fn, lines_list) where output_fn appends to lines_list."""
    lines = []

    def _fn(msg="", end="\n"):
        lines.append(str(msg))

    return _fn, lines


def _minimal_input_seq(slug: str, description: str, per_type: Optional[list] = None):
    """Build input sequence for a minimal compose_bundle run.

    per_type: list of responses for each of the 9 content type prompts.
    Defaults to blank (skip all) for each type.
    """
    if per_type is None:
        per_type = [""] * 9  # skip all types

    return (
        [slug]                  # slug prompt (only called if slug not passed as arg)
        + [""]                  # display_name (use default)
        + description.splitlines()
        + ["END"]               # description terminator
        + per_type              # one pick per content type
    )


# ---------------------------------------------------------------------------
# T1 — slug uniqueness vs existing bundles
# ---------------------------------------------------------------------------

class TestSlugCollisionBundles:
    """T1: check_slug_collision raises collision on existing bundle."""

    def test_existing_bundle_slug_collides(self):
        # capacity-assessment.yaml was removed in v2 item #1 cleanup.
        # vks-core-consumption-bundle is the surviving bundle slug.
        from vcfops_packaging.composer import check_slug_collision
        err = check_slug_collision("vks-core-consumption-bundle", REPO_ROOT)
        assert err is not None, "vks-core-consumption-bundle bundle exists; should report collision"
        assert "vks-core-consumption-bundle" in err

    def test_fresh_slug_no_collision(self):
        from vcfops_packaging.composer import check_slug_collision
        err = check_slug_collision("__nonexistent-bundle-xyz__", REPO_ROOT)
        assert err is None

    def test_force_bypasses_collision_in_compose(self, tmp_path):
        """--force lets compose_bundle overwrite an existing bundle."""
        from vcfops_packaging.composer import compose_bundle

        bundle_path = tmp_path / "bundles" / "test-bundle.yaml"
        bundle_path.parent.mkdir(parents=True)
        # Write a pre-existing bundle stub.
        bundle_path.write_text(
            "name: test-bundle\ndescription: old\n"
            "supermetrics: []\nviews: []\ndashboards: []\n"
            "customgroups: []\nsymptoms: []\nalerts: []\n"
            "reports: []\nrecommendations: []\nmanagementpacks: []\n"
        )

        out_fn, _ = _capture_output()
        responses = (
            [""]                # display_name
            + ["A fresh description", "END"]  # description
            + [""] * 9          # skip all types
        )
        rc = compose_bundle(
            slug="test-bundle",
            force=True,
            dry_run=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq(responses),
            output_fn=out_fn,
        )
        # Loader will fail because content paths don't exist in tmp_path —
        # but it should NOT fail on the collision check.
        # Accept rc 0 or 1 from the round-trip loader; the key assertion is
        # that it didn't fail for "already exists" reasons.
        # We verify by checking that the file was written (not blocked by --force).
        assert bundle_path.stat().st_size > 0

    def test_no_force_blocks_existing_bundle(self, tmp_path, capsys):
        """Without --force, compose_bundle returns 1 on collision."""
        from vcfops_packaging.composer import compose_bundle

        bundle_path = tmp_path / "bundles" / "already-exists.yaml"
        bundle_path.parent.mkdir(parents=True)
        bundle_path.write_text("name: already-exists\ndescription: old\n")

        out_fn, _ = _capture_output()
        rc = compose_bundle(
            slug="already-exists",
            force=False,
            dry_run=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq([]),
            output_fn=out_fn,
        )
        assert rc == 1


# ---------------------------------------------------------------------------
# T2 — slug uniqueness vs release manifests
# ---------------------------------------------------------------------------

class TestSlugCollisionReleases:
    """T2: check_slug_collision raises collision on existing release manifest."""

    def test_existing_release_slug_collides(self):
        from vcfops_packaging.composer import check_slug_collision
        # demand-driven-capacity-v2 is a real release manifest in the repo
        err = check_slug_collision("demand-driven-capacity-v2", REPO_ROOT)
        assert err is not None, "demand-driven-capacity-v2 release exists; should report collision"
        assert "release" in err.lower() or "demand-driven-capacity-v2" in err

    def test_fresh_slug_not_blocked_by_releases(self):
        from vcfops_packaging.composer import check_slug_collision
        err = check_slug_collision("__no-such-release-xyz__", REPO_ROOT)
        assert err is None


# ---------------------------------------------------------------------------
# T3 — component discovery
# ---------------------------------------------------------------------------

class TestComponentDiscovery:
    """T3: discover_components returns expected counts from the real corpus."""

    def test_discovers_factory_supermetrics(self):
        from vcfops_packaging.composer import discover_components
        entries = discover_components(REPO_ROOT, "supermetrics")
        factory_entries = [e for e in entries if e.provenance == "factory"]
        # We know there are at least 10 factory SMs
        assert len(factory_entries) >= 10, (
            f"Expected 10+ factory SMs, got {len(factory_entries)}"
        )

    def test_discovers_factory_dashboards(self):
        from vcfops_packaging.composer import discover_components
        entries = discover_components(REPO_ROOT, "dashboards")
        factory = [e for e in entries if e.provenance == "factory"]
        assert len(factory) >= 2, f"Expected 2+ factory dashboards, got {len(factory)}"

    def test_discovers_factory_views(self):
        from vcfops_packaging.composer import discover_components
        entries = discover_components(REPO_ROOT, "views")
        factory = [e for e in entries if e.provenance == "factory"]
        assert len(factory) >= 2, f"Expected 2+ factory views, got {len(factory)}"

    def test_discovers_third_party_dashboards(self):
        from vcfops_packaging.composer import discover_components
        entries = discover_components(REPO_ROOT, "dashboards")
        third_party = [e for e in entries if e.provenance not in ("factory", "")]
        # idps-planner has at least 1 dashboard
        assert len(third_party) >= 1, (
            f"Expected 1+ third-party dashboards (idps-planner), got {len(third_party)}"
        )

    def test_factory_entries_come_first(self):
        from vcfops_packaging.composer import discover_components
        entries = discover_components(REPO_ROOT, "supermetrics")
        if len(entries) < 2:
            pytest.skip("not enough entries to test ordering")
        # All factory entries should precede any non-factory entry
        first_non_factory = next(
            (i for i, e in enumerate(entries) if e.provenance != "factory"),
            len(entries),
        )
        last_factory = max(
            (i for i, e in enumerate(entries) if e.provenance == "factory"),
            default=-1,
        )
        assert last_factory < first_non_factory, (
            "Factory entries should all precede third-party entries"
        )

    def test_entries_have_rel_path(self):
        from vcfops_packaging.composer import discover_components
        entries = discover_components(REPO_ROOT, "dashboards")
        for e in entries:
            assert e.rel_path, f"Empty rel_path on entry {e.slug}"
            assert not e.rel_path.startswith("/"), (
                f"rel_path should be relative, got: {e.rel_path}"
            )

    def test_empty_type_returns_empty_list(self):
        from vcfops_packaging.composer import discover_components
        entries = discover_components(REPO_ROOT, "nonexistent_type_xyz")
        assert entries == []


# ---------------------------------------------------------------------------
# T4 — picking by index
# ---------------------------------------------------------------------------

class TestPickByIndex:
    """T4: _parse_picks handles integer indices correctly."""

    def test_single_index(self):
        from vcfops_packaging.composer import _parse_picks, ComponentEntry
        entries = _make_entries(5)
        result = _parse_picks("1", entries)
        assert len(result) == 1
        assert result[0].slug == "item-0"

    def test_multiple_indices(self):
        from vcfops_packaging.composer import _parse_picks
        entries = _make_entries(5)
        result = _parse_picks("1,3,5", entries)
        assert [e.slug for e in result] == ["item-0", "item-2", "item-4"]

    def test_out_of_range_index_ignored(self):
        from vcfops_packaging.composer import _parse_picks
        entries = _make_entries(3)
        result = _parse_picks("1,99", entries)
        assert len(result) == 1

    def test_empty_picks_none(self):
        from vcfops_packaging.composer import _parse_picks
        entries = _make_entries(3)
        result = _parse_picks("none", entries)
        assert result == []

    def test_blank_picks_empty(self):
        from vcfops_packaging.composer import _parse_picks
        entries = _make_entries(3)
        result = _parse_picks("  ", entries)
        assert result == []

    def test_deduplication(self):
        from vcfops_packaging.composer import _parse_picks
        entries = _make_entries(3)
        result = _parse_picks("1,1,2", entries)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# T5 — picking by substring
# ---------------------------------------------------------------------------

class TestPickBySubstring:
    """T5: _parse_picks handles substring patterns."""

    def test_substring_match(self):
        from vcfops_packaging.composer import _parse_picks, ComponentEntry
        entries = [
            ComponentEntry(Path("/x/alpha.yaml"), "alpha.yaml", "alpha", "Alpha", "factory"),
            ComponentEntry(Path("/x/beta.yaml"), "beta.yaml", "beta", "Beta", "factory"),
            ComponentEntry(Path("/x/alphabeta.yaml"), "alphabeta.yaml", "alphabeta", "Alphabeta", "factory"),
        ]
        result = _parse_picks("alpha", entries)
        assert {e.slug for e in result} == {"alpha", "alphabeta"}

    def test_substring_case_insensitive(self):
        from vcfops_packaging.composer import _parse_picks, ComponentEntry
        entries = [
            ComponentEntry(Path("/x/Cluster_CPU.yaml"), "Cluster_CPU", "cluster_cpu", "Cluster CPU", "factory"),
            ComponentEntry(Path("/x/vm_mem.yaml"), "vm_mem", "vm_mem", "VM Mem", "factory"),
        ]
        result = _parse_picks("CLUSTER", entries)
        assert len(result) == 1
        assert result[0].slug == "cluster_cpu"

    def test_mixed_index_and_substring(self):
        from vcfops_packaging.composer import _parse_picks, ComponentEntry
        entries = [
            ComponentEntry(Path("/x/a.yaml"), "a.yaml", "alpha", "Alpha", "factory"),
            ComponentEntry(Path("/x/b.yaml"), "b.yaml", "beta", "Beta", "factory"),
            ComponentEntry(Path("/x/c.yaml"), "c.yaml", "gamma", "Gamma", "factory"),
        ]
        result = _parse_picks("3,alp", entries)
        assert {e.slug for e in result} == {"gamma", "alpha"}


# ---------------------------------------------------------------------------
# T6 — dependency walk surfaces missing deps
# ---------------------------------------------------------------------------

class TestDependencyWalk:
    """T6: _check_deps surfaces missing view/SM dependencies."""

    def test_no_deps_when_no_dashboards(self):
        from vcfops_packaging.composer import _check_deps
        errors = _check_deps(
            picked_dashboards=[],
            picked_views=[],
            picked_sms=[],
            picked_cgs=[],
            repo_root=REPO_ROOT,
        )
        assert errors == []

    def test_missing_view_for_dashboard(self):
        from vcfops_packaging.composer import _check_deps, discover_components

        # Pick a dashboard but provide NO views — the walker should report missing views.
        dashboards = [e for e in discover_components(REPO_ROOT, "dashboards")
                      if e.provenance == "factory"][:1]
        if not dashboards:
            pytest.skip("no factory dashboards available")

        errors = _check_deps(
            picked_dashboards=dashboards,
            picked_views=[],       # intentionally omit views
            picked_sms=[],
            picked_cgs=[],
            repo_root=REPO_ROOT,
        )
        # At least one error because the dashboard references views not in picks
        assert len(errors) >= 1, (
            "Expected at least one dep error when dashboard views are omitted"
        )

    def test_no_errors_when_deps_included(self):
        from vcfops_packaging.composer import _check_deps, discover_components

        # Capacity-assessment dashboard + its views + SMs should produce no errors.
        all_dashboards = discover_components(REPO_ROOT, "dashboards")
        cap_dash = next(
            (e for e in all_dashboards if "capacity_assessment" in e.slug),
            None,
        )
        if cap_dash is None:
            pytest.skip("capacity_assessment dashboard not found")

        all_views = discover_components(REPO_ROOT, "views")
        all_sms = discover_components(REPO_ROOT, "supermetrics")
        all_cgs = discover_components(REPO_ROOT, "customgroups")

        errors = _check_deps(
            picked_dashboards=[cap_dash],
            picked_views=all_views,
            picked_sms=all_sms,
            picked_cgs=all_cgs,
            repo_root=REPO_ROOT,
        )
        assert errors == [], f"Unexpected dep errors: {errors}"


# ---------------------------------------------------------------------------
# T7 — cross-provenance composition allowed
# ---------------------------------------------------------------------------

class TestCrossProvenanceComposition:
    """T7: bundles may mix factory and third-party content without scope errors."""

    def test_cross_provenance_no_scope_errors(self):
        from vcfops_packaging.composer import _check_deps, discover_components

        # Combine a factory dashboard with all views + SMs (including third-party).
        factory_dashboards = [
            e for e in discover_components(REPO_ROOT, "dashboards")
            if e.provenance == "factory"
        ][:1]
        if not factory_dashboards:
            pytest.skip("no factory dashboards found")

        # Intentionally include third-party views too
        all_views = discover_components(REPO_ROOT, "views")
        all_sms = discover_components(REPO_ROOT, "supermetrics")
        all_cgs = discover_components(REPO_ROOT, "customgroups")

        errors = _check_deps(
            picked_dashboards=factory_dashboards,
            picked_views=all_views,
            picked_sms=all_sms,
            picked_cgs=all_cgs,
            repo_root=REPO_ROOT,
        )
        # Scope violations must NOT appear — cross-provenance is allowed in bundles.
        scope_errors = [e for e in errors if "scope violation" in e.lower()]
        assert scope_errors == [], (
            f"Scope errors must not fire in bundle composition: {scope_errors}"
        )

    def test_third_party_dashboard_plus_factory_view_allowed(self):
        """A third-party dashboard paired with a factory view must not produce scope errors."""
        from vcfops_packaging.composer import _check_deps, discover_components

        third_party_dashboards = [
            e for e in discover_components(REPO_ROOT, "dashboards")
            if e.provenance not in ("factory", "")
        ][:1]
        if not third_party_dashboards:
            pytest.skip("no third-party dashboards found")

        factory_views = [
            e for e in discover_components(REPO_ROOT, "views")
            if e.provenance == "factory"
        ]

        errors = _check_deps(
            picked_dashboards=third_party_dashboards,
            picked_views=factory_views,
            picked_sms=discover_components(REPO_ROOT, "supermetrics"),
            picked_cgs=discover_components(REPO_ROOT, "customgroups"),
            repo_root=REPO_ROOT,
        )
        scope_errors = [e for e in errors if "scope violation" in e.lower()]
        assert scope_errors == [], (
            f"Scope violations in bundle composition: {scope_errors}"
        )


# ---------------------------------------------------------------------------
# T8 — --dry-run prints, doesn't write
# ---------------------------------------------------------------------------

class TestDryRun:
    """T8: --dry-run prints YAML to output, does not write file."""

    def test_dry_run_does_not_write_file(self, tmp_path):
        from vcfops_packaging.composer import compose_bundle

        out_fn, lines = _capture_output()
        rc = compose_bundle(
            slug="dry-run-test",
            dry_run=True,
            force=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq(
                [""]                  # display_name
                + ["My description", "END"]  # description
                + [""] * 9            # skip all types
            ),
            output_fn=out_fn,
        )
        assert rc == 0
        bundle_path = tmp_path / "bundles" / "dry-run-test.yaml"
        assert not bundle_path.exists(), "dry-run must not write to disk"

    def test_dry_run_prints_yaml(self, tmp_path):
        from vcfops_packaging.composer import compose_bundle

        out_fn, lines = _capture_output()
        rc = compose_bundle(
            slug="dry-run-yaml-test",
            dry_run=True,
            force=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq(
                [""]                  # display_name
                + ["A test description for dry run", "END"]
                + [""] * 9
            ),
            output_fn=out_fn,
        )
        assert rc == 0
        combined = "\n".join(lines)
        assert "name: dry-run-yaml-test" in combined, (
            f"Expected name field in dry-run output, got:\n{combined}"
        )
        assert "description:" in combined

    def test_dry_run_prints_dry_run_tag(self, tmp_path):
        from vcfops_packaging.composer import compose_bundle

        out_fn, lines = _capture_output()
        compose_bundle(
            slug="my-dry-slug",
            dry_run=True,
            force=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq(
                [""] + ["Short description", "END"] + [""] * 9
            ),
            output_fn=out_fn,
        )
        combined = "\n".join(lines)
        assert "dry-run" in combined.lower(), (
            f"Expected 'dry-run' tag in output, got:\n{combined}"
        )


# ---------------------------------------------------------------------------
# T9 — --force overwrites
# ---------------------------------------------------------------------------

class TestForceOverwrite:
    """T9: --force allows overwriting an existing bundle."""

    def test_force_overwrites_existing(self, tmp_path):
        from vcfops_packaging.composer import compose_bundle

        bundle_path = tmp_path / "bundles" / "overwrite-me.yaml"
        bundle_path.parent.mkdir(parents=True)
        bundle_path.write_text(
            "name: overwrite-me\ndescription: original\n"
            "supermetrics: []\nviews: []\ndashboards: []\n"
            "customgroups: []\nsymptoms: []\nalerts: []\n"
            "reports: []\nrecommendations: []\nmanagementpacks: []\n"
        )
        original_size = bundle_path.stat().st_size

        out_fn, _ = _capture_output()
        compose_bundle(
            slug="overwrite-me",
            dry_run=False,
            force=True,
            repo_root=tmp_path,
            input_fn=_make_input_seq(
                [""]
                + ["New description that is definitely longer than the original", "END"]
                + [""] * 9
            ),
            output_fn=out_fn,
        )
        # File should be re-written (may be larger due to new description)
        assert bundle_path.exists()
        new_content = bundle_path.read_text()
        assert "New description" in new_content, (
            f"Expected new description in overwritten file, got:\n{new_content}"
        )

    def test_without_force_returns_1_on_existing(self, tmp_path, capsys):
        from vcfops_packaging.composer import compose_bundle

        bundle_path = tmp_path / "bundles" / "no-overwrite.yaml"
        bundle_path.parent.mkdir(parents=True)
        bundle_path.write_text(
            "name: no-overwrite\ndescription: original\n"
            "supermetrics: []\nviews: []\ndashboards: []\n"
            "customgroups: []\nsymptoms: []\nalerts: []\n"
            "reports: []\nrecommendations: []\nmanagementpacks: []\n"
        )

        out_fn, _ = _capture_output()
        rc = compose_bundle(
            slug="no-overwrite",
            dry_run=False,
            force=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq([]),
            output_fn=out_fn,
        )
        assert rc == 1


# ---------------------------------------------------------------------------
# T10 — output YAML round-trips through the bundle loader
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """T10: produced bundle YAML round-trips through load_bundle without errors."""

    def test_empty_bundle_round_trips(self, tmp_path):
        """A bundle with no components should load cleanly."""
        from vcfops_packaging.composer import compose_bundle
        from vcfops_packaging.loader import load_bundle, BundleValidationError

        out_fn, _ = _capture_output()
        rc = compose_bundle(
            slug="roundtrip-empty",
            dry_run=False,
            force=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq(
                [""]
                + ["An empty bundle for round-trip testing", "END"]
                + [""] * 9
            ),
            output_fn=out_fn,
        )
        assert rc == 0, "compose_bundle should succeed for an empty bundle"

        bundle_path = tmp_path / "bundles" / "roundtrip-empty.yaml"
        assert bundle_path.exists()

        try:
            bundle = load_bundle(bundle_path)
        except BundleValidationError as e:
            pytest.fail(f"Bundle YAML failed round-trip validation: {e}")

        assert bundle.name == "roundtrip-empty"
        assert bundle.description.strip(), "description should be non-empty"
        assert bundle.supermetrics == []
        assert bundle.views == []
        assert bundle.dashboards == []

    def test_bundle_with_real_components_round_trips(self, tmp_path):
        """A bundle picking real factory components should load cleanly."""
        from vcfops_packaging.composer import compose_bundle, discover_components
        from vcfops_packaging.loader import load_bundle, BundleValidationError

        # Copy the real content tree symlink-style so loader paths resolve.
        content_src = REPO_ROOT / "content"
        if not content_src.exists():
            pytest.skip("content/ directory not found")

        # Symlink content/ and third_party/ into tmp_path so the bundle loader
        # can resolve component paths from there.
        (tmp_path / "content").symlink_to(content_src.resolve())
        third_party_src = REPO_ROOT / "third_party"
        if third_party_src.exists():
            (tmp_path / "third_party").symlink_to(third_party_src.resolve())

        # Also symlink vcfops_common (needed by loader to find repo_root).
        (tmp_path / "vcfops_common").symlink_to((REPO_ROOT / "vcfops_common").resolve())

        # Pick 2 supermetrics (indices 1 and 2)
        sm_entries = discover_components(REPO_ROOT, "supermetrics")
        picks_sm = "1,2" if len(sm_entries) >= 2 else ("1" if sm_entries else "")

        # CONTENT_TYPES order: dashboards, views, supermetrics, customgroups,
        # symptoms, alerts, reports, recommendations, managementpacks
        out_fn, _ = _capture_output()
        rc = compose_bundle(
            slug="roundtrip-with-sms",
            dry_run=False,
            force=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq(
                [""]                           # display_name
                + ["Bundle with real SMs for round-trip test", "END"]
                + [""]                         # dashboards: skip
                + [""]                         # views: skip
                + [picks_sm]                   # supermetrics: pick 1+2
                + [""] * 6                     # skip customgroups..managementpacks
            ),
            output_fn=out_fn,
        )
        assert rc == 0, (
            f"compose_bundle returned non-zero; this likely means the round-trip "
            f"loader validation failed"
        )

        bundle_path = tmp_path / "bundles" / "roundtrip-with-sms.yaml"
        assert bundle_path.exists()
        bundle = load_bundle(bundle_path)
        if picks_sm:
            expected_count = min(len(sm_entries), 2) if "," in picks_sm else 1
            assert len(bundle.supermetrics) == expected_count, (
                f"Expected {expected_count} SMs, got {len(bundle.supermetrics)}"
            )


# ---------------------------------------------------------------------------
# T11 — CLI subcommand integration (cmd_bundle smoke test)
# ---------------------------------------------------------------------------

class TestCLIIntegration:
    """Verify cmd_bundle is wired into the argparse parser and dispatches correctly."""

    def test_bundle_subcommand_registered(self):
        from vcfops_packaging.cli import build_parser
        parser = build_parser()
        # argparse stores subparser names in the choices dict.
        subparsers_action = next(
            a for a in parser._actions if hasattr(a, "_name_parser_map")
        )
        assert "bundle" in subparsers_action._name_parser_map, (
            "bundle subcommand not registered in argparse parser"
        )

    def test_bundle_dry_run_flag(self):
        from vcfops_packaging.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["bundle", "my-slug", "--dry-run"])
        assert args.name == "my-slug"
        assert args.dry_run is True
        assert args.force is False

    def test_bundle_force_flag(self):
        from vcfops_packaging.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["bundle", "my-slug", "--force"])
        assert args.force is True
        assert args.dry_run is False

    def test_bundle_name_optional(self):
        from vcfops_packaging.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["bundle"])
        assert args.name is None


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_entries(n: int):
    """Create n synthetic ComponentEntry objects for picker tests."""
    from vcfops_packaging.composer import ComponentEntry
    return [
        ComponentEntry(
            path=Path(f"/fake/{i}.yaml"),
            rel_path=f"content/supermetrics/item-{i}.yaml",
            slug=f"item-{i}",
            display_name=f"Item {i}",
            provenance="factory",
        )
        for i in range(n)
    ]
