"""Phase 2 smoke tests for vcfops_packaging.release_builder.

Two smoke passes as specified in the Phase 2 requirements:

  Pass A — dashboard headline
    Headline: dashboards/demand_driven_capacity_v2.yaml
    Expects:  dest_subdir == "dashboards"
              zip_path.exists()
              zip filename == <release-name>.zip  (versionless consumer artifact)
              zip contains dashboard JSON, 4 view definitions, install scaffolding

  Pass B — bundle headline
    Headline: bundles/vks-core-consumption-bundle.yaml
    Expects:  dest_subdir == "bundles"
              zip_path.exists()
              zip filename follows release convention (versionless)
              zip contains 8 SMs + 1 view + 1 dashboard + 1 report payloads

Both passes use a temporary release manifest constructed at test time so they
bypass the Phase 1 flag-state validator (which requires released: true on the
source YAML — that flag is flipped by /release in Phase 4).  build_release()
is called directly.

Tests also cover the stale-check helpers expected_artifact_path() and
artifact_already_exists().

Note: capacity-assessment.yaml was removed in v2 item #1 cleanup (converted
to a standalone release-manifest dashboard). Pass B was re-pointed to
vks-core-consumption-bundle, the surviving multi-content bundle.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import List

import pytest
import yaml

# Tests in this file call build_release() which constructs full content-import
# zips from real YAML.  Each zip build takes a few seconds; the whole file is
# ~2.5 min serial.  No validators are run against the real corpus, so these
# tests are safe to parallelize — they just need the slow marker.
pytestmark = pytest.mark.slow

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
            source="content/dashboards/demand_driven_capacity_v2.yaml",
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
    """Smoke test: build a release whose headline is a bundle YAML.

    Uses vks-core-consumption-bundle (8 SMs / 1 view / 1 dashboard / 1 report /
    0 customgroups).  capacity-assessment.yaml was removed in v2 item #1 cleanup
    and is no longer a valid fixture.
    """

    @pytest.fixture(scope="class")
    def release_artifacts(self, tmp_path_factory):
        from vcfops_packaging.release_builder import build_release

        tmp = tmp_path_factory.mktemp("bundle_release")
        manifest_path = _write_release_manifest(
            tmp,
            name="vks-core-consumption-bundle",
            version="1.0",
            source="bundles/vks-core-consumption-bundle.yaml",
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
        expected_name = "vks-core-consumption-bundle.zip"
        actual_name = release_artifacts[0].zip_path.name
        assert actual_name == expected_name, (
            f"Expected filename {expected_name!r}, got {actual_name!r}"
        )

    def test_release_metadata(self, release_artifacts):
        art = release_artifacts[0]
        assert art.release_name == "vks-core-consumption-bundle"
        assert art.release_version == "1.0"

    def test_zip_has_eight_supermetrics(self, release_artifacts):
        """vks-core-consumption-bundle declares 8 SMs."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        assert bundle_json_entries, f"No bundle.json found. Members: {members}"
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        sm_section = bundle_data.get("content", {}).get("supermetrics", {})
        sm_items = sm_section.get("items", [])
        assert len(sm_items) == 8, (
            f"Expected 8 SMs in bundle.json, got {len(sm_items)}: "
            f"{[i.get('name') for i in sm_items]}"
        )

    def test_zip_has_one_view(self, release_artifacts):
        """vks-core-consumption-bundle declares 1 view."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        view_items = bundle_data.get("content", {}).get("views", {}).get("items", [])
        assert len(view_items) == 1, (
            f"Expected 1 view, got {len(view_items)}: "
            f"{[i.get('name') for i in view_items]}"
        )

    def test_zip_has_one_dashboard(self, release_artifacts):
        """vks-core-consumption-bundle declares 1 dashboard."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        dash_items = bundle_data.get("content", {}).get("dashboards", {}).get("items", [])
        assert len(dash_items) == 1, (
            f"Expected 1 dashboard, got {len(dash_items)}"
        )

    def test_zip_has_zero_customgroups(self, release_artifacts):
        """vks-core-consumption-bundle declares 0 custom groups."""
        zip_path = release_artifacts[0].zip_path
        members = _zip_members(zip_path)
        bundle_json_entries = [m for m in members if m.endswith("bundle.json")]
        with zipfile.ZipFile(zip_path, "r") as z:
            bundle_data = json.loads(z.read(bundle_json_entries[0]).decode("utf-8"))
        cg_items = bundle_data.get("content", {}).get("customgroups", {}).get("items", [])
        assert len(cg_items) == 0, (
            f"Expected 0 custom groups, got {len(cg_items)}: {cg_items}"
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
# SDK MP headline — pointer model
# ---------------------------------------------------------------------------

class TestSdkMpPointer:
    """Unit tests for _build_sdk_mp_headline pointer model.

    The new implementation does NOT call build_sdk_pak.  Instead it:
      1. Looks up the adapter in the managed-paks registry.
      2. Emits a small pointer-zip containing pointer.json.
      3. Raises ValueError for unregistered adapters.

    Tests use a fixture registry file (no real Java compilation needed,
    and no external repos need to exist — this is a pure unit test).

    Note: full end-to-end publish verification (registry lookup via real
    knowledge/context/managed_paks.md pointing at live sentania-labs repos) cannot
    be automated until Workstream D (de-track migration) is complete and
    the external repos exist.
    """

    # Fixture registry content with one live entry.
    _FIXTURE_REGISTRY = """\
# Managed paks (SDK adapter registry)

## Paks

<!--
Template block — skipped by parser.

### template-entry

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-template
- **Target:** `content/sdk-adapters/template-entry/`
- **adapter_kind:** vcfcf_template
-->

### test-pak

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-test-pak
- **Target:** `content/sdk-adapters/test-pak/`
- **adapter_kind:** vcfcf_test_pak
- **Owner:** sentania-labs. Public repo.
- **Notes:** Fixture entry for unit tests.
"""

    def _write_registry(self, tmp_path: Path) -> Path:
        """Write the fixture registry to a temp file and return its path."""
        reg = tmp_path / "managed_paks.md"
        reg.write_text(self._FIXTURE_REGISTRY)
        return reg

    def _make_adapter_yaml(self, tmp_path: Path, name: str) -> Path:
        """Create a minimal adapter project dir and return the adapter.yaml path."""
        project_dir = tmp_path / name
        project_dir.mkdir()
        adapter_yaml = project_dir / "adapter.yaml"
        adapter_yaml.write_text(f"adapter_kind: vcfcf_{name.replace('-', '_')}\n")
        return adapter_yaml

    # ------------------------------------------------------------------
    # Pointer record shape
    # ------------------------------------------------------------------

    def test_pointer_zip_created(self, tmp_path):
        """_build_sdk_mp_headline must produce a zip file."""
        import vcfops_packaging.managed_paks as _mp_mod
        from vcfops_packaging.release_builder import _build_sdk_mp_headline

        reg = self._write_registry(tmp_path)
        adapter_yaml = self._make_adapter_yaml(tmp_path, "test-pak")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        original_default = _mp_mod._DEFAULT_REGISTRY_PATH
        try:
            _mp_mod._DEFAULT_REGISTRY_PATH = reg
            zip_path = _build_sdk_mp_headline(adapter_yaml, tmp_out)
        finally:
            _mp_mod._DEFAULT_REGISTRY_PATH = original_default

        assert zip_path.exists(), f"Pointer zip not created: {zip_path}"
        assert zip_path.suffix == ".zip", f"Expected .zip extension, got {zip_path.suffix}"

    def test_pointer_zip_contains_pointer_json(self, tmp_path):
        """The pointer zip must contain a single file 'pointer.json'."""
        import vcfops_packaging.managed_paks as _mp_mod
        from vcfops_packaging.release_builder import _build_sdk_mp_headline

        reg = self._write_registry(tmp_path)
        adapter_yaml = self._make_adapter_yaml(tmp_path, "test-pak")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        original_default = _mp_mod._DEFAULT_REGISTRY_PATH
        try:
            _mp_mod._DEFAULT_REGISTRY_PATH = reg
            zip_path = _build_sdk_mp_headline(adapter_yaml, tmp_out)
        finally:
            _mp_mod._DEFAULT_REGISTRY_PATH = original_default

        with zipfile.ZipFile(zip_path) as zf:
            members = zf.namelist()
        assert members == ["pointer.json"], (
            f"Expected ['pointer.json'] in pointer zip, got {members}"
        )

    def test_pointer_json_fields(self, tmp_path):
        """pointer.json must contain all required fields with correct values."""
        import json
        import vcfops_packaging.managed_paks as _mp_mod
        from vcfops_packaging.release_builder import _build_sdk_mp_headline

        reg = self._write_registry(tmp_path)
        adapter_yaml = self._make_adapter_yaml(tmp_path, "test-pak")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        original_default = _mp_mod._DEFAULT_REGISTRY_PATH
        try:
            _mp_mod._DEFAULT_REGISTRY_PATH = reg
            zip_path = _build_sdk_mp_headline(adapter_yaml, tmp_out)
        finally:
            _mp_mod._DEFAULT_REGISTRY_PATH = original_default

        with zipfile.ZipFile(zip_path) as zf:
            data = json.loads(zf.read("pointer.json").decode("utf-8"))

        assert data["type"] == "sdk-pak-pointer", f"Wrong type: {data['type']!r}"
        assert data["adapter_name"] == "test-pak", f"Wrong adapter_name: {data['adapter_name']!r}"
        assert data["adapter_kind"] == "vcfcf_test_pak", (
            f"Wrong adapter_kind: {data['adapter_kind']!r}"
        )
        assert data["remote"] == (
            "https://github.com/sentania-labs/vcf-content-factory-sdk-test-pak"
        ), f"Wrong remote: {data['remote']!r}"
        assert data["latest_release_url"] == (
            "https://github.com/sentania-labs/vcf-content-factory-sdk-test-pak/releases/latest"
        ), f"Wrong latest_release_url: {data['latest_release_url']!r}"
        assert data["api_latest_url"] == (
            "https://api.github.com/repos/sentania-labs/"
            "vcf-content-factory-sdk-test-pak/releases/latest"
        ), f"Wrong api_latest_url: {data['api_latest_url']!r}"
        assert data["asset_glob"] == "*.pak", f"Wrong asset_glob: {data['asset_glob']!r}"

    def test_pointer_latest_release_url_is_latest(self, tmp_path):
        """latest_release_url must end with '/releases/latest' (version-free pointer)."""
        import json
        import vcfops_packaging.managed_paks as _mp_mod
        from vcfops_packaging.release_builder import _build_sdk_mp_headline

        reg = self._write_registry(tmp_path)
        adapter_yaml = self._make_adapter_yaml(tmp_path, "test-pak")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        original_default = _mp_mod._DEFAULT_REGISTRY_PATH
        try:
            _mp_mod._DEFAULT_REGISTRY_PATH = reg
            zip_path = _build_sdk_mp_headline(adapter_yaml, tmp_out)
        finally:
            _mp_mod._DEFAULT_REGISTRY_PATH = original_default

        with zipfile.ZipFile(zip_path) as zf:
            data = json.loads(zf.read("pointer.json").decode("utf-8"))

        url = data["latest_release_url"]
        assert url.endswith("/releases/latest"), (
            f"latest_release_url must end with '/releases/latest', got: {url!r}"
        )
        # Must not contain a version number — pointer stays version-free.
        assert "/releases/tag/" not in url, (
            f"latest_release_url must not pin a specific tag: {url!r}"
        )

    # ------------------------------------------------------------------
    # Unregistered adapter error path
    # ------------------------------------------------------------------

    def test_unregistered_adapter_raises(self, tmp_path):
        """An adapter not in the registry must raise ValueError with a clear message."""
        import vcfops_packaging.managed_paks as _mp_mod
        from vcfops_packaging.release_builder import _build_sdk_mp_headline

        reg = self._write_registry(tmp_path)
        # Use an adapter name NOT present in the fixture registry.
        adapter_yaml = self._make_adapter_yaml(tmp_path, "not-registered")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        original_default = _mp_mod._DEFAULT_REGISTRY_PATH
        try:
            _mp_mod._DEFAULT_REGISTRY_PATH = reg
            with pytest.raises(ValueError) as exc_info:
                _build_sdk_mp_headline(adapter_yaml, tmp_out)
        finally:
            _mp_mod._DEFAULT_REGISTRY_PATH = original_default

        msg = str(exc_info.value)
        assert "not-registered" in msg, (
            f"Error message must name the adapter; got: {msg!r}"
        )
        assert "managed_paks.md" in msg, (
            f"Error message must reference the registry file; got: {msg!r}"
        )
        # Must not mention any fallback to a local build.
        assert "local build" not in msg.lower() or "do not" in msg.lower(), (
            f"Error message must not suggest a local build fallback."
        )

    def test_unregistered_adapter_does_not_produce_zip(self, tmp_path):
        """A failing (unregistered) adapter must not write any zip to tmp_out."""
        import vcfops_packaging.managed_paks as _mp_mod
        from vcfops_packaging.release_builder import _build_sdk_mp_headline

        reg = self._write_registry(tmp_path)
        adapter_yaml = self._make_adapter_yaml(tmp_path, "also-not-registered")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        original_default = _mp_mod._DEFAULT_REGISTRY_PATH
        try:
            _mp_mod._DEFAULT_REGISTRY_PATH = reg
            with pytest.raises(ValueError):
                _build_sdk_mp_headline(adapter_yaml, tmp_out)
        finally:
            _mp_mod._DEFAULT_REGISTRY_PATH = original_default

        zips = list(tmp_out.glob("*.zip"))
        assert not zips, f"No zip should be written on failure; found: {zips}"

    # ------------------------------------------------------------------
    # No sdk_builder import
    # ------------------------------------------------------------------

    def test_no_sdk_builder_import(self, tmp_path):
        """_build_sdk_mp_headline must not import vcfops_managementpacks.sdk_builder."""
        import sys
        import vcfops_packaging.managed_paks as _mp_mod
        from vcfops_packaging.release_builder import _build_sdk_mp_headline

        reg = self._write_registry(tmp_path)
        adapter_yaml = self._make_adapter_yaml(tmp_path, "test-pak")
        tmp_out = tmp_path / "out"
        tmp_out.mkdir()

        # Remove sdk_builder from sys.modules to ensure it is not imported.
        sdk_key = "vcfops_managementpacks.sdk_builder"
        was_loaded = sdk_key in sys.modules
        sys.modules.pop(sdk_key, None)

        original_default = _mp_mod._DEFAULT_REGISTRY_PATH
        try:
            _mp_mod._DEFAULT_REGISTRY_PATH = reg
            zip_path = _build_sdk_mp_headline(adapter_yaml, tmp_out)
        finally:
            _mp_mod._DEFAULT_REGISTRY_PATH = original_default

        # sdk_builder must still be absent — the new code does not import it.
        assert sdk_key not in sys.modules, (
            f"_build_sdk_mp_headline must not import sdk_builder; "
            f"but it appeared in sys.modules after the call."
        )
        assert zip_path.exists(), f"Pointer zip must still be produced: {zip_path}"

        # Restore original state if it was loaded before.
        if was_loaded:
            import importlib
            importlib.import_module(sdk_key)


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

        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
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
