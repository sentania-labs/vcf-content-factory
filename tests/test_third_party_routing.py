"""Third-party content routing tests.

Covers the routing changes introduced for ``factory_native: false`` bundles:

  T1 — release_types.headline_to_dir routing
       headline_to_dir with a bundle_data dict that has factory_native=False
       and exactly 1 dashboard returns "ThirdPartyContent/dashboards".

  T2 — release_types.headline_to_dir routing (multi-dashboard fallback)
       A bundle with 2 dashboards routes to "ThirdPartyContent/bundles".

  T3 — release_types.headline_to_dir factory-native unchanged
       A bundle with factory_native=True (explicit) or no factory_native field
       still routes to "bundles".

  T4 — release_builder.build_release zip lands under ThirdPartyContent/dashboards/
       Building a release whose headline is bundles/third_party/idps-planner.yaml
       produces a ReleaseArtifact with dest_subdir="ThirdPartyContent/dashboards"
       and the zip is named "idps-planner.zip".

  T5 — publish integration: zip lands at ThirdPartyContent/dashboards/idps-planner.zip
       Full publish() run with idps-planner as headline asserts zip at the correct path.

  T6 — README catalog renders Third-Party Content section
       _render_release_catalog produces a "Third-Party Content" H2 with a sub-
       section for dashboards containing a row for idps-planner, and the row
       includes the License and Authors columns.

  T7 — factory-native bundle still routes to bundles/ (regression guard)
       capacity-assessment.yaml (factory_native absent/True) routes to "bundles".

  T8 — stale-zip sweep does NOT touch ThirdPartyContent/ when zip is known
       A zip correctly placed at ThirdPartyContent/dashboards/idps-planner.zip
       is not swept to retired/ if it is in the known_filenames set.

  T9 — legacy-versioned-zip sweep does NOT scan ThirdPartyContent/ subdirs
       _sweep_legacy_versioned_zips is scoped to factory-native top-level subdirs
       only; placing a versioned-looking zip under ThirdPartyContent/ does NOT
       get deleted.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_dist_repo(tmp_path: Path) -> Path:
    """Initialise a minimal git repo mimicking the dist repo layout."""
    dist = tmp_path / "dist-repo"
    dist.mkdir()

    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=str(dist), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@vcfops-test.local"],
        cwd=str(dist), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "VCFOps Test"],
        cwd=str(dist), capture_output=True, check=True,
    )

    (dist / "LICENSE").write_text("MIT License\n")
    readme_body = (
        "# VCF Content Factory Bundles\n\n"
        "Human-authored intro.\n\n"
        "<!-- AUTO:START release-catalog -->\n"
        "<!-- AUTO:END -->\n\n"
        "Human-authored footer.\n"
    )
    (dist / "README.md").write_text(readme_body)

    subprocess.run(["git", "add", "-A"], cwd=str(dist), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(dist), capture_output=True, check=True,
    )
    return dist


def _write_release_manifest(
    releases_dir: Path,
    name: str,
    version: str,
    source_abs: Path,
    *,
    description: str = "Test release.",
) -> Path:
    """Write a minimal release manifest to releases_dir/<name>.yaml."""
    manifest = {
        "name": name,
        "version": version,
        "description": description,
        "artifacts": [
            {
                "source": str(source_abs),
                "headline": True,
            }
        ],
    }
    p = releases_dir / f"{name}.yaml"
    p.write_text(yaml.dump(manifest, default_flow_style=False))
    return p


def _patch_enumerate(monkeypatch, releases_dir: Path):
    """Replace _enumerate_releases to read from releases_dir."""
    from vcfops_packaging import publish as _pub
    from vcfops_packaging.releases import load_release

    def _fake_enumerate(factory_repo):
        manifests = sorted(releases_dir.glob("*.y*ml"))
        releases = []
        seen = {}
        for p in manifests:
            if p.name == "_phase1_selftest.yaml":
                continue
            rel = load_release(p, repo_root=factory_repo)
            if rel.name in seen:
                raise ValueError(f"duplicate: {rel.name}")
            seen[rel.name] = p
            releases.append(rel)
        return releases

    monkeypatch.setattr(_pub, "_enumerate_releases", _fake_enumerate)


# ---------------------------------------------------------------------------
# T1 — headline_to_dir: single-dashboard third-party bundle
# ---------------------------------------------------------------------------

class TestHeadlineToDirThirdParty:
    """T1: headline_to_dir routes factory_native=False + 1 dashboard correctly."""

    def test_single_dashboard_routes_to_thirdparty_dashboards(self):
        from vcfops_packaging.release_types import headline_to_dir

        bundle_data = {
            "factory_native": False,
            "dashboards": ["some/dashboard.yaml"],
        }
        result = headline_to_dir("bundles/third_party/idps-planner.yaml", bundle_data=bundle_data)
        assert result == "ThirdPartyContent/dashboards", (
            f"Expected 'ThirdPartyContent/dashboards', got {result!r}"
        )

    def test_two_dashboards_routes_to_thirdparty_bundles(self):
        """T2: 2 dashboards -> ThirdPartyContent/bundles."""
        from vcfops_packaging.release_types import headline_to_dir

        bundle_data = {
            "factory_native": False,
            "dashboards": ["d1.yaml", "d2.yaml"],
        }
        result = headline_to_dir("bundles/foo.yaml", bundle_data=bundle_data)
        assert result == "ThirdPartyContent/bundles", (
            f"Expected 'ThirdPartyContent/bundles', got {result!r}"
        )

    def test_zero_dashboards_routes_to_thirdparty_bundles(self):
        """T2b: 0 dashboards -> ThirdPartyContent/bundles (SM-only or similar)."""
        from vcfops_packaging.release_types import headline_to_dir

        bundle_data = {
            "factory_native": False,
            "supermetrics": ["sm1.yaml"],
        }
        result = headline_to_dir("bundles/foo.yaml", bundle_data=bundle_data)
        assert result == "ThirdPartyContent/bundles", (
            f"Expected 'ThirdPartyContent/bundles', got {result!r}"
        )

    def test_factory_native_true_ignores_dashboard_count(self):
        """T3: factory_native=True -> "bundles" regardless of dashboard count."""
        from vcfops_packaging.release_types import headline_to_dir

        bundle_data = {
            "factory_native": True,
            "dashboards": ["d.yaml"],
        }
        result = headline_to_dir("bundles/foo.yaml", bundle_data=bundle_data)
        assert result == "bundles", (
            f"factory_native=True should route to 'bundles', got {result!r}"
        )

    def test_no_bundle_data_defaults_to_factory_native(self):
        """T3b: bundle_data=None -> "bundles" (factory-native default)."""
        from vcfops_packaging.release_types import headline_to_dir

        result = headline_to_dir("bundles/capacity-assessment.yaml", bundle_data=None)
        assert result == "bundles", (
            f"bundle_data=None should route to 'bundles', got {result!r}"
        )

    def test_non_bundle_prefix_unaffected(self):
        """Non-bundle headline paths are not touched by the third-party logic."""
        from vcfops_packaging.release_types import headline_to_dir

        result = headline_to_dir("dashboards/demand_driven_capacity_v2.yaml", bundle_data=None)
        assert result == "dashboards", (
            f"dashboard headline should still route to 'dashboards', got {result!r}"
        )


# ---------------------------------------------------------------------------
# T4 — release_builder.build_release: idps-planner zip lands correctly
# ---------------------------------------------------------------------------

class TestBuildReleaseThirdParty:
    """T4: build_release for idps-planner produces ThirdPartyContent/dashboards dest."""

    @pytest.fixture(scope="class")
    def release_artifacts(self, tmp_path_factory):
        from vcfops_packaging.release_builder import build_release

        tmp = tmp_path_factory.mktemp("idps_release")
        source_abs = (REPO_ROOT / "content" / "third_party" / "idps-planner" / "PROJECT.yaml").resolve()
        assert source_abs.exists(), f"PROJECT.yaml not found: {source_abs}"

        manifest = {
            "name": "idps-planner",
            "version": "1.0",
            "description": "IDPS Planner third-party bundle test.",
            "artifacts": [
                {"source": str(source_abs), "headline": True}
            ],
        }
        manifest_path = tmp / "idps-planner.yaml"
        manifest_path.write_text(yaml.dump(manifest, default_flow_style=False))

        output_dir = tmp / "output"
        output_dir.mkdir()
        return build_release(manifest_path, output_dir)

    def test_returns_one_artifact(self, release_artifacts):
        assert len(release_artifacts) == 1, (
            f"Expected 1 artifact, got {len(release_artifacts)}"
        )

    def test_dest_subdir_is_thirdparty_dashboards(self, release_artifacts):
        """T4a: dest_subdir must be 'ThirdPartyContent/dashboards'."""
        assert release_artifacts[0].dest_subdir == "ThirdPartyContent/dashboards", (
            f"Expected dest_subdir='ThirdPartyContent/dashboards', "
            f"got {release_artifacts[0].dest_subdir!r}"
        )

    def test_zip_exists(self, release_artifacts):
        assert release_artifacts[0].zip_path.exists(), (
            f"Output zip not found: {release_artifacts[0].zip_path}"
        )

    def test_zip_filename_versionless(self, release_artifacts):
        """T4b: zip filename is idps-planner.zip (versionless)."""
        assert release_artifacts[0].zip_path.name == "idps-planner.zip", (
            f"Expected 'idps-planner.zip', got {release_artifacts[0].zip_path.name!r}"
        )

    def test_release_name(self, release_artifacts):
        assert release_artifacts[0].release_name == "idps-planner"


# ---------------------------------------------------------------------------
# T5 — publish integration: zip lands at ThirdPartyContent/dashboards/
# ---------------------------------------------------------------------------

def test_publish_thirdparty_zip_lands_at_correct_path(tmp_path, monkeypatch):
    """T5: publish() routes idps-planner to ThirdPartyContent/dashboards/idps-planner.zip."""
    from vcfops_packaging.publish import publish

    dist = _init_dist_repo(tmp_path)
    releases_dir = tmp_path / "tp_releases"
    releases_dir.mkdir()

    source_abs = (REPO_ROOT / "content" / "third_party" / "idps-planner" / "PROJECT.yaml").resolve()
    assert source_abs.exists(), f"PROJECT.yaml not found: {source_abs}"

    _write_release_manifest(
        releases_dir,
        name="idps-planner",
        version="1.0",
        source_abs=source_abs,
        description="IDPS Planner third-party publish test.",
    )
    _patch_enumerate(monkeypatch, releases_dir)

    result = publish(
        factory_repo=REPO_ROOT,
        dist_repo=dist,
        dry_run=False,
        no_push=True,
    )

    expected = dist / "ThirdPartyContent" / "dashboards" / "idps-planner.zip"
    assert expected.exists(), (
        f"Expected zip not found at {expected}\nbuilt: {result.built}"
    )

    assert len(result.built) == 1
    assert result.built[0].name == "idps-planner.zip"
    # Must NOT land under top-level bundles/ or dashboards/.
    assert not (dist / "bundles" / "idps-planner.zip").exists(), (
        "idps-planner.zip should not be in top-level bundles/"
    )
    assert not (dist / "dashboards" / "idps-planner.zip").exists(), (
        "idps-planner.zip should not be in top-level dashboards/"
    )


# ---------------------------------------------------------------------------
# T6 — README catalog: Third-Party Content section
# ---------------------------------------------------------------------------

class TestReadmeCatalogThirdPartySection:
    """T6: _render_release_catalog renders Third-Party Content section correctly."""

    def _build_minimal_release_for_idps(self, tmp_path: Path):
        """Return a loaded ReleaseDef for idps-planner."""
        from vcfops_packaging.releases import load_release

        source_abs = (REPO_ROOT / "content" / "third_party" / "idps-planner" / "PROJECT.yaml").resolve()
        assert source_abs.exists(), f"PROJECT.yaml not found: {source_abs}"

        manifest = {
            "name": "idps-planner",
            "version": "1.0",
            "description": "IDPS Planner readme test.",
            "artifacts": [{"source": str(source_abs), "headline": True}],
        }
        manifest_path = tmp_path / "idps-planner.yaml"
        manifest_path.write_text(yaml.dump(manifest, default_flow_style=False))
        return load_release(manifest_path, repo_root=REPO_ROOT)

    def test_thirdparty_h2_section_present(self, tmp_path):
        """T6a: README contains a 'Third-Party Content' H2 heading."""
        from vcfops_packaging.readme_gen import _render_release_catalog

        rel = self._build_minimal_release_for_idps(tmp_path)
        dist = tmp_path / "dist"
        dist.mkdir()

        catalog = _render_release_catalog(dist_repo=dist, releases=[rel])

        assert "## Third-Party Content" in catalog, (
            f"Expected '## Third-Party Content' not found in catalog.\n"
            f"Catalog:\n{catalog}"
        )

    def test_thirdparty_dashboards_subsection_present(self, tmp_path):
        """T6b: README contains a '### Dashboards' sub-section under Third-Party Content."""
        from vcfops_packaging.readme_gen import _render_release_catalog

        rel = self._build_minimal_release_for_idps(tmp_path)
        dist = tmp_path / "dist"
        dist.mkdir()

        catalog = _render_release_catalog(dist_repo=dist, releases=[rel])

        # The third-party Dashboards sub-section is H3.
        assert "### Dashboards" in catalog, (
            f"Expected '### Dashboards' sub-section under Third-Party Content.\n"
            f"Catalog:\n{catalog}"
        )

    def test_thirdparty_row_has_license_column(self, tmp_path):
        """T6c: Third-party row includes License column value from bundle YAML."""
        from vcfops_packaging.readme_gen import _render_release_catalog

        rel = self._build_minimal_release_for_idps(tmp_path)
        dist = tmp_path / "dist"
        dist.mkdir()

        catalog = _render_release_catalog(dist_repo=dist, releases=[rel])

        assert "| License |" in catalog, (
            f"Expected '| License |' column header not found.\n"
            f"Catalog:\n{catalog}"
        )
        # idps-planner.yaml has license: MIT
        assert "MIT" in catalog, (
            f"Expected 'MIT' license value not found in catalog.\n"
            f"Catalog:\n{catalog}"
        )

    def test_thirdparty_row_has_authors_column(self, tmp_path):
        """T6d: Third-party row includes Authors column value from bundle YAML."""
        from vcfops_packaging.readme_gen import _render_release_catalog

        rel = self._build_minimal_release_for_idps(tmp_path)
        dist = tmp_path / "dist"
        dist.mkdir()

        catalog = _render_release_catalog(dist_repo=dist, releases=[rel])

        assert "| Authors |" in catalog, (
            f"Expected '| Authors |' column header not found.\n"
            f"Catalog:\n{catalog}"
        )
        # idps-planner.yaml has author: Ryan Pletka, ...
        assert "Ryan Pletka" in catalog, (
            f"Expected author name 'Ryan Pletka' not found in catalog.\n"
            f"Catalog:\n{catalog}"
        )

    def test_thirdparty_row_has_version_column(self, tmp_path):
        """T6e: Third-party rows include a Version column (unlike factory-native rows)."""
        from vcfops_packaging.readme_gen import _render_release_catalog

        rel = self._build_minimal_release_for_idps(tmp_path)
        dist = tmp_path / "dist"
        dist.mkdir()

        catalog = _render_release_catalog(dist_repo=dist, releases=[rel])

        # The Version column must appear in the third-party table.
        assert "| Version |" in catalog, (
            f"Expected '| Version |' column in third-party table.\n"
            f"Catalog:\n{catalog}"
        )

    def test_thirdparty_download_link_uses_thirdparty_prefix(self, tmp_path):
        """T6f: Download link uses ThirdPartyContent/dashboards/ prefix."""
        from vcfops_packaging.readme_gen import _render_release_catalog

        rel = self._build_minimal_release_for_idps(tmp_path)
        dist = tmp_path / "dist"
        dist.mkdir()

        catalog = _render_release_catalog(dist_repo=dist, releases=[rel])

        expected_link = "[Download](ThirdPartyContent/dashboards/idps-planner.zip)"
        assert expected_link in catalog, (
            f"Expected third-party download link {expected_link!r} not found.\n"
            f"Catalog:\n{catalog}"
        )

    def test_thirdparty_section_absent_when_no_thirdparty_releases(self, tmp_path):
        """T6g: 'Third-Party Content' section is absent when all releases are factory-native."""
        from vcfops_packaging.readme_gen import _render_release_catalog
        from vcfops_packaging.releases import load_release

        # Use a factory-native release (no factory_native field → defaults True).
        source_abs = (REPO_ROOT / "content" / "factory" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        manifest = {
            "name": "demand-driven-capacity-v2",
            "version": "1.0",
            "description": "Factory-native test.",
            "artifacts": [{"source": str(source_abs), "headline": True}],
        }
        manifest_path = tmp_path / "demand-driven-capacity-v2.yaml"
        manifest_path.write_text(yaml.dump(manifest, default_flow_style=False))
        rel = load_release(manifest_path, repo_root=REPO_ROOT)

        dist = tmp_path / "dist"
        dist.mkdir()

        catalog = _render_release_catalog(dist_repo=dist, releases=[rel])

        assert "## Third-Party Content" not in catalog, (
            f"'Third-Party Content' section should be absent for factory-native-only releases.\n"
            f"Catalog:\n{catalog}"
        )


# ---------------------------------------------------------------------------
# T7 — factory-native bundle routes to bundles/ (regression guard)
# ---------------------------------------------------------------------------

class TestFactoryNativeRegressionGuard:
    """T7: factory-native bundles keep routing to top-level bundles/."""

    def test_capacity_assessment_routes_to_bundles(self, tmp_path):
        from vcfops_packaging.release_builder import _artifact_dest_subdir
        from vcfops_packaging.releases import load_release

        source_abs = (REPO_ROOT / "content" / "bundles" / "capacity-assessment.yaml").resolve()
        assert source_abs.exists(), f"capacity-assessment.yaml not found"

        manifest = {
            "name": "capacity-assessment",
            "version": "1.0",
            "description": "Regression guard.",
            "artifacts": [{"source": str(source_abs), "headline": True}],
        }
        manifest_path = tmp_path / "capacity-assessment.yaml"
        manifest_path.write_text(yaml.dump(manifest, default_flow_style=False))
        rel = load_release(manifest_path, repo_root=REPO_ROOT)

        headline = next(a for a in rel.artifacts if a.headline)
        subdir = _artifact_dest_subdir(headline)

        assert subdir == "bundles", (
            f"capacity-assessment should route to 'bundles', got {subdir!r}"
        )

    def test_capacity_assessment_publish_zip_in_bundles(self, tmp_path, monkeypatch):
        """End-to-end: capacity-assessment still lands in dist/bundles/."""
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "ca_releases"
        releases_dir.mkdir()

        source_abs = (REPO_ROOT / "content" / "bundles" / "capacity-assessment.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="capacity-assessment",
            version="1.0",
            source_abs=source_abs,
            description="Regression guard publish test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )

        expected = dist / "bundles" / "capacity-assessment.zip"
        assert expected.exists(), (
            f"capacity-assessment.zip should be in bundles/, not found at {expected}\n"
            f"built: {result.built}"
        )
        # Must NOT be in ThirdPartyContent/.
        tp_path = dist / "ThirdPartyContent" / "dashboards" / "capacity-assessment.zip"
        assert not tp_path.exists(), (
            f"capacity-assessment.zip must not appear in ThirdPartyContent/: {tp_path}"
        )


# ---------------------------------------------------------------------------
# T8 — stale-zip sweep does NOT move known ThirdPartyContent zips
# ---------------------------------------------------------------------------

class TestStaleZipSweepThirdParty:
    """T8: _sweep_stale_zips leaves ThirdPartyContent zips that are in known_filenames alone."""

    def test_known_thirdparty_zip_not_swept(self, tmp_path):
        from vcfops_packaging.publish import _sweep_stale_zips

        dist = tmp_path / "dist"
        tp_dir = dist / "ThirdPartyContent" / "dashboards"
        tp_dir.mkdir(parents=True)
        zip_path = tp_dir / "idps-planner.zip"
        zip_path.write_bytes(b"fake zip")

        known_filenames = {"ThirdPartyContent/dashboards/idps-planner.zip"}
        retired = _sweep_stale_zips(dist, known_filenames, dry_run=True)

        assert not any(p.name == "idps-planner.zip" for p in retired), (
            f"Known ThirdPartyContent zip was swept to retired/: {retired}"
        )

    def test_unknown_thirdparty_zip_swept(self, tmp_path):
        """An orphaned ThirdPartyContent zip IS moved to retired/ by the sweep."""
        from vcfops_packaging.publish import _sweep_stale_zips

        dist = tmp_path / "dist"
        tp_dir = dist / "ThirdPartyContent" / "dashboards"
        tp_dir.mkdir(parents=True)
        zip_path = tp_dir / "orphan-tp.zip"
        zip_path.write_bytes(b"fake orphan")

        known_filenames: set[str] = set()  # nothing known
        retired = _sweep_stale_zips(dist, known_filenames, dry_run=True)

        assert any(p.name == "orphan-tp.zip" for p in retired), (
            f"Orphaned ThirdPartyContent zip not found in retired list: {retired}"
        )


# ---------------------------------------------------------------------------
# T9 — legacy-versioned-zip sweep does NOT scan ThirdPartyContent/
# ---------------------------------------------------------------------------

class TestLegacyZipSweepDoesNotTouchThirdParty:
    """T9: _sweep_legacy_versioned_zips only touches factory-native top-level subdirs."""

    def test_versioned_looking_thirdparty_zip_not_deleted(self, tmp_path):
        from vcfops_packaging.publish import _sweep_legacy_versioned_zips

        dist = tmp_path / "dist"
        tp_dir = dist / "ThirdPartyContent" / "dashboards"
        tp_dir.mkdir(parents=True)
        # Place a zip with a versioned-looking name under ThirdPartyContent/.
        versioned_zip = tp_dir / "idps-planner-1.0.zip"
        versioned_zip.write_bytes(b"fake third party versioned")

        # Even if the slug matches a known slug, the sweep must not touch it.
        known_slugs = {"idps-planner"}
        deleted = _sweep_legacy_versioned_zips(dist, known_slugs, dry_run=True)

        assert not any(p.name == versioned_zip.name for p in deleted), (
            f"Legacy sweep incorrectly targeted ThirdPartyContent/ zip: {deleted}"
        )
