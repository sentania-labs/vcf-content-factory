"""Phase 2 smoke tests for vcfops_packaging.release_builder.

Two smoke passes as specified in the Phase 2 requirements:

  Pass A — dashboard headline
    Headline: dashboards/demand_driven_capacity_v2.yaml
    Expects:  dest_subdir == "dashboards"
              zip_path.exists()
              zip filename == <release-name>.zip  (versionless consumer artifact)
              zip contains dashboard JSON, 4 view definitions, install scaffolding

  Pass B — bundle headline
    Headline: bundles/capacity-assessment.yaml
    Expects:  dest_subdir == "bundles"
              zip_path.exists()
              zip filename follows release convention (versionless)
              zip contains 11 SMs + 2 views + 1 dashboard + 1 customgroup payloads

Both passes use a temporary release manifest constructed at test time so they
bypass the Phase 1 flag-state validator (which requires released: true on the
source YAML — that flag is flipped by /release in Phase 4).  build_release()
is called directly.

Tests also cover the stale-check helpers expected_artifact_path() and
artifact_already_exists().
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import List

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers: write a minimal release manifest to a temp path
# ---------------------------------------------------------------------------

def _write_release_manifest(
    tmp_path: Path,
    name: str,
    version: str,
    source: str,
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Write a minimal release YAML to tmp_path/<name>.yaml and return the path."""
    # Resolve source to absolute so load_release can find it regardless of CWD.
    source_abs = (repo_root / source).resolve()
    assert source_abs.exists(), f"source not found: {source_abs}"
    manifest = {
        "name": name,
        "version": version,
        "description": f"Phase 2 smoke test release for {source}",
        "artifacts": [
            {
                "source": str(source_abs),
                "headline": True,
            }
        ],
    }
    out = tmp_path / f"{name}.yaml"
    out.write_text(yaml.dump(manifest, default_flow_style=False))
    return out


def _zip_members(zip_path: Path) -> List[str]:
    """Return sorted list of member names inside a zip file."""
    with zipfile.ZipFile(zip_path, "r") as z:
        return sorted(z.namelist())


# ---------------------------------------------------------------------------
# Pass A — dashboard headline
# ---------------------------------------------------------------------------

class TestDashboardHeadline:
    """Smoke test: build a release whose headline is a dashboard YAML."""

    @pytest.fixture(scope="class")
    def release_artifacts(self, tmp_path_factory):
        from vcfops_packaging.release_builder import build_release

        tmp = tmp_path_factory.mktemp("dash_release")
        manifest_path = _write_release_manifest(
            tmp,
            name="demand-driven-capacity-v2",
            version="1.0",
            source="dashboards/demand_driven_capacity_v2.yaml",
        )
        output_dir = tmp / "output"
        output_dir.mkdir()
        return build_release(manifest_path, output_dir)

    # --- Structural assertions ---

    def test_returns_one_artifact(self, release_artifacts):
        assert len(release_artifacts) == 1, (
            f"Expected 1 artifact, got {len(release_artifacts)}"
        )

    def test_dest_subdir(self, release_artifacts):
        assert release_artifacts[0].dest_subdir == "dashboards", (
            f"Expected dest_subdir='dashboards', got {release_artifacts[0].dest_subdir!r}"
        )

    def test_zip_exists(self, release_artifacts):
        assert release_artifacts[0].zip_path.exists(), (
            f"Output zip not found: {release_artifacts[0].zip_path}"
        )

    def test_zip_filename_convention(self, release_artifacts):
        """Filename must be <release-name>.zip (versionless consumer artifact)."""
        expected_name = "demand-driven-capacity-v2.zip"
        actual_name = release_artifacts[0].zip_path.name
        assert actual_name == expected_name, (
            f"Expected filename {expected_name!r}, got {actual_name!r}"
        )

    def test_release_metadata(self, release_artifacts):
        art = release_artifacts[0]
        assert art.release_name == "demand-driven-capacity-v2"
        assert art.release_version == "1.0"

    # --- Zip content assertions ---

    def test_zip_has_dashboard_json(self, release_artifacts):
        """bundle.json must contain a 'dashboards' entry."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        # bundle.json lives under bundles/<slug>/bundle.json
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        assert bundle_json_entries, (
            f"No bundle.json found in zip. Members: {members}"
        )
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        assert "dashboards" in bundle_data.get("content", {}), (
            f"'dashboards' not in bundle.json content block. Keys: {list(bundle_data.get('content', {}).keys())}"
        )

    def test_zip_has_four_view_definitions(self, release_artifacts):
        """The dashboard has 4 View widgets; the zip must include all 4 views."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        views_section = bundle_data.get("content", {}).get("views", {})
        view_items = views_section.get("items", [])
        assert len(view_items) == 4, (
            f"Expected 4 views in bundle.json, got {len(view_items)}: {view_items}"
        )

    def test_zip_has_install_py(self, release_artifacts):
        members = _zip_members(release_artifacts[0].zip_path)
        assert "install.py" in members, f"install.py missing. Members: {members}"

    def test_zip_has_install_ps1(self, release_artifacts):
        members = _zip_members(release_artifacts[0].zip_path)
        assert "install.ps1" in members, f"install.ps1 missing. Members: {members}"

    def test_zip_has_readme(self, release_artifacts):
        members = _zip_members(release_artifacts[0].zip_path)
        readme_entries = [m for m in members if m.endswith("README.md")]
        assert readme_entries, f"No README.md found. Members: {members}"

    def test_zip_has_license(self, release_artifacts):
        members = _zip_members(release_artifacts[0].zip_path)
        assert "LICENSE" in members, f"LICENSE missing. Members: {members}"

    def test_zip_has_views_zip(self, release_artifacts):
        """Views.zip must be present for a dashboard release with view deps."""
        members = _zip_members(release_artifacts[0].zip_path)
        views_zip_entries = [m for m in members if m.endswith("Views.zip")]
        assert views_zip_entries, (
            f"Views.zip not found in release zip. Members: {members}"
        )

    def test_zip_has_dashboard_zip(self, release_artifacts):
        """Dashboard.zip (drag-drop artifact) must be present."""
        members = _zip_members(release_artifacts[0].zip_path)
        dash_zip_entries = [m for m in members if m.endswith("Dashboard.zip")]
        assert dash_zip_entries, (
            f"Dashboard.zip not found in release zip. Members: {members}"
        )

    def test_zero_supermetrics(self, release_artifacts):
        """demand_driven_capacity_v2 has no SMs; bundle.json must not have a supermetrics entry."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        content = bundle_data.get("content", {})
        assert "supermetrics" not in content, (
            f"Expected no 'supermetrics' in bundle.json for demand-driven-capacity-v2. "
            f"Content keys: {list(content.keys())}"
        )


# ---------------------------------------------------------------------------
# Pass B — bundle headline
# ---------------------------------------------------------------------------

class TestBundleHeadline:
    """Smoke test: build a release whose headline is a bundle YAML."""

    @pytest.fixture(scope="class")
    def release_artifacts(self, tmp_path_factory):
        from vcfops_packaging.release_builder import build_release

        tmp = tmp_path_factory.mktemp("bundle_release")
        manifest_path = _write_release_manifest(
            tmp,
            name="capacity-assessment",
            version="1.0",
            source="bundles/capacity-assessment.yaml",
        )
        output_dir = tmp / "output"
        output_dir.mkdir()
        return build_release(manifest_path, output_dir)

    def test_returns_one_artifact(self, release_artifacts):
        assert len(release_artifacts) == 1, (
            f"Expected 1 artifact, got {len(release_artifacts)}"
        )

    def test_dest_subdir(self, release_artifacts):
        assert release_artifacts[0].dest_subdir == "bundles", (
            f"Expected dest_subdir='bundles', got {release_artifacts[0].dest_subdir!r}"
        )

    def test_zip_exists(self, release_artifacts):
        assert release_artifacts[0].zip_path.exists(), (
            f"Output zip not found: {release_artifacts[0].zip_path}"
        )

    def test_zip_filename_convention(self, release_artifacts):
        """Filename must be <release-name>.zip (versionless consumer artifact)."""
        expected_name = "capacity-assessment.zip"
        actual_name = release_artifacts[0].zip_path.name
        assert actual_name == expected_name, (
            f"Expected filename {expected_name!r}, got {actual_name!r}"
        )

    def test_release_metadata(self, release_artifacts):
        art = release_artifacts[0]
        assert art.release_name == "capacity-assessment"
        assert art.release_version == "1.0"

    def test_zip_has_eleven_supermetrics(self, release_artifacts):
        """capacity-assessment bundle declares 11 SMs."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        assert bundle_json_entries, f"No bundle.json found. Members: {members}"
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        sm_section = bundle_data.get("content", {}).get("supermetrics", {})
        sm_items = sm_section.get("items", [])
        assert len(sm_items) == 11, (
            f"Expected 11 SMs in bundle.json, got {len(sm_items)}: "
            f"{[i.get('name') for i in sm_items]}"
        )

    def test_zip_has_two_views(self, release_artifacts):
        """capacity-assessment bundle declares 2 views."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        view_items = bundle_data.get("content", {}).get("views", {}).get("items", [])
        assert len(view_items) == 2, (
            f"Expected 2 views, got {len(view_items)}: "
            f"{[i.get('name') for i in view_items]}"
        )

    def test_zip_has_one_dashboard(self, release_artifacts):
        """capacity-assessment bundle declares 1 dashboard."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        dash_items = bundle_data.get("content", {}).get("dashboards", {}).get("items", [])
        assert len(dash_items) == 1, (
            f"Expected 1 dashboard, got {len(dash_items)}"
        )

    def test_zip_has_one_customgroup(self, release_artifacts):
        """capacity-assessment bundle declares 1 custom group."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        cg_items = bundle_data.get("content", {}).get("customgroups", {}).get("items", [])
        assert len(cg_items) == 1, (
            f"Expected 1 custom group, got {len(cg_items)}: {cg_items}"
        )

    def test_zip_has_install_scaffolding(self, release_artifacts):
        members = _zip_members(release_artifacts[0].zip_path)
        for required in ("install.py", "install.ps1", "LICENSE"):
            assert required in members, (
                f"{required!r} missing from bundle release zip. Members: {members}"
            )
        readme_entries = [m for m in members if m.endswith("README.md")]
        assert readme_entries, f"No README.md found. Members: {members}"


# ---------------------------------------------------------------------------
# Stale-check / idempotence helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    """Unit tests for expected_artifact_path() and artifact_already_exists()."""

    @pytest.fixture
    def minimal_release(self, tmp_path):
        """Return a loaded ReleaseDef for demand-driven-capacity-v2."""
        from vcfops_packaging.release_builder import build_release
        from vcfops_packaging.releases import load_release

        source_abs = (REPO_ROOT / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        manifest = {
            "name": "demand-driven-capacity-v2",
            "version": "1.0",
            "description": "Helper test release",
            "artifacts": [{"source": str(source_abs), "headline": True}],
        }
        manifest_path = tmp_path / "demand-driven-capacity-v2.yaml"
        manifest_path.write_text(yaml.dump(manifest))
        return load_release(manifest_path)

    def test_expected_artifact_path_structure(self, minimal_release, tmp_path):
        from vcfops_packaging.release_builder import expected_artifact_path

        dest_root = tmp_path / "dist-repo"
        path = expected_artifact_path(minimal_release, dest_root)
        # Versionless: <slug>.zip, not <slug>-<version>.zip
        assert path.name == "demand-driven-capacity-v2.zip"
        # Should be under <dest_root>/dashboards/
        assert path.parent.name == "dashboards"
        assert path.parent.parent == dest_root.resolve()

    def test_artifact_does_not_exist_initially(self, minimal_release, tmp_path):
        from vcfops_packaging.release_builder import artifact_already_exists

        dest_root = tmp_path / "dist-repo"
        assert artifact_already_exists(minimal_release, dest_root) is False

    def test_artifact_exists_after_creation(self, minimal_release, tmp_path):
        from vcfops_packaging.release_builder import (
            artifact_already_exists,
            expected_artifact_path,
        )

        dest_root = tmp_path / "dist-repo"
        # Create the file
        expected = expected_artifact_path(minimal_release, dest_root)
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_bytes(b"fake zip content")
        assert artifact_already_exists(minimal_release, dest_root) is True
