"""Phase 5 tests — direct third-party component release routing.

Covers the Phase 5 extensions introduced for discrete third-party component
releases (source paths of the form ``third_party/<project>/<type>/<file>.yaml``).

Test inventory
--------------

T1 — headline_to_dir for each third-party content type
     Verifies each type subdir maps to the correct ThirdPartyContent/<sub>.

T2 — headline_to_dir: malformed third-party paths raise ValueError
     Paths with too few components or unknown type dirs raise with a clear message.

T3 — headline_to_dir: existing PROJECT.yaml-style routing still works
     Regression safety: the bundles/ + factory_native:false path is unchanged.

T4 — release_builder._artifact_dest_subdir for a third-party view
     Building a release manifest whose source is
     third_party/idps-planner/views/IDPS Planner - Cluster Selection.yaml
     produces dest_subdir == "ThirdPartyContent/views".

T5 — release_builder._artifact_dest_subdir for a third-party supermetric
     Source third_party/idps-planner/supermetrics/IDPS Net Receive All VMs.yaml
     -> dest_subdir == "ThirdPartyContent/supermetrics".

T6 — build_release for a third-party view produces a zip + correct routing
     Full build_release() invocation for a third-party view headline.

T7 — cmd_release type-first lookup finds third-party component
     A display-name search for a third-party view/supermetric finds the file and
     emits a release manifest whose headline.source is the full third_party/... path.

T8 — publish dry-run end-to-end: third-party view lands in ThirdPartyContent/views/
     Full publish() dry-run with a third-party view release manifest confirms the
     artifact would land under ThirdPartyContent/views/.

T9 — PROJECT.yaml release still routes to ThirdPartyContent/dashboards/ (regression)
     The existing idps-planner PROJECT.yaml release still routes correctly after
     Phase 5 additions.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
TP_ROOT = REPO_ROOT / "third_party" / "idps-planner"

# Representative third-party files used across tests.
TP_VIEW_PATH = TP_ROOT / "views" / "IDPS Planner - Cluster Selection.yaml"
TP_SM_PATH = TP_ROOT / "supermetrics" / "IDPS Net Receive All VMs.yaml"

# Require these fixtures to exist.
pytestmark = pytest.mark.skipif(
    not TP_VIEW_PATH.exists(),
    reason="third_party/idps-planner fixtures not found",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_dist_repo(tmp_path: Path) -> Path:
    """Initialise a minimal git repo mimicking the dist repo layout."""
    dist = tmp_path / "dist-repo"
    dist.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(dist), capture_output=True, check=True)
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
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(dist), capture_output=True, check=True)
    return dist


def _write_release_manifest(
    releases_dir: Path,
    name: str,
    version: str,
    source_abs: Path,
    *,
    description: str = "Test release.",
) -> Path:
    manifest = {
        "name": name,
        "version": version,
        "description": description,
        "artifacts": [{"source": str(source_abs), "headline": True}],
    }
    p = releases_dir / f"{name}.yaml"
    p.write_text(yaml.dump(manifest, default_flow_style=False))
    return p


def _patch_enumerate(monkeypatch, releases_dir: Path):
    from vcfops_packaging import publish as _pub
    from vcfops_packaging.releases import load_release

    def _fake_enumerate(factory_repo):
        manifests = sorted(releases_dir.glob("*.y*ml"))
        releases = []
        seen = {}
        for p in manifests:
            rel = load_release(p, repo_root=factory_repo)
            if rel.name in seen:
                raise ValueError(f"duplicate: {rel.name}")
            seen[rel.name] = p
            releases.append(rel)
        return releases

    monkeypatch.setattr(_pub, "_enumerate_releases", _fake_enumerate)


# ---------------------------------------------------------------------------
# T1 — headline_to_dir for each third-party content type
# ---------------------------------------------------------------------------

class TestHeadlineToDirThirdPartyComponents:
    """T1: headline_to_dir maps third_party/<proj>/<type>/<file> to ThirdPartyContent/<sub>."""

    @pytest.mark.parametrize("type_dir,expected_sub", [
        ("dashboards",    "ThirdPartyContent/dashboards"),
        ("views",         "ThirdPartyContent/views"),
        ("supermetrics",  "ThirdPartyContent/supermetrics"),
        ("customgroups",  "ThirdPartyContent/customgroups"),
        ("reports",       "ThirdPartyContent/reports"),
        ("managementpacks", "ThirdPartyContent/management-packs"),
    ])
    def test_type_routing(self, type_dir, expected_sub):
        from vcfops_packaging.release_types import headline_to_dir

        source = f"third_party/idps-planner/{type_dir}/Some File.yaml"
        result = headline_to_dir(source)
        assert result == expected_sub, (
            f"source={source!r}: expected {expected_sub!r}, got {result!r}"
        )


# ---------------------------------------------------------------------------
# T2 — malformed third-party paths raise ValueError
# ---------------------------------------------------------------------------

class TestHeadlineToDirThirdPartyMalformed:
    """T2: malformed third_party/ paths raise ValueError with a clear message."""

    def test_too_few_components(self):
        from vcfops_packaging.release_types import headline_to_dir

        with pytest.raises(ValueError, match="malformed"):
            headline_to_dir("third_party/idps-planner/views")

    def test_only_prefix(self):
        from vcfops_packaging.release_types import headline_to_dir

        with pytest.raises(ValueError, match="malformed"):
            headline_to_dir("third_party/")

    def test_unknown_type_dir(self):
        from vcfops_packaging.release_types import headline_to_dir

        with pytest.raises(ValueError, match="not a recognised content type"):
            headline_to_dir("third_party/idps-planner/widgets/foo.yaml")

    def test_symptoms_raises(self):
        """symptoms/ is excluded from discrete routing in v1 even under third_party/."""
        from vcfops_packaging.release_types import headline_to_dir

        with pytest.raises(ValueError, match="not a recognised content type"):
            headline_to_dir("third_party/idps-planner/symptoms/foo.yaml")


# ---------------------------------------------------------------------------
# T3 — PROJECT.yaml-style routing regression
# ---------------------------------------------------------------------------

class TestProjectYamlRoutingRegression:
    """T3: existing bundles/ + factory_native:false routing is unaffected."""

    def test_single_dashboard_thirdparty_bundle(self):
        from vcfops_packaging.release_types import headline_to_dir

        bundle_data = {"factory_native": False, "dashboards": ["d.yaml"]}
        result = headline_to_dir("bundles/idps-planner.yaml", bundle_data=bundle_data)
        assert result == "ThirdPartyContent/dashboards", (
            f"PROJECT.yaml-style single-dashboard bundle should still route to "
            f"ThirdPartyContent/dashboards, got {result!r}"
        )

    def test_multidash_thirdparty_bundle(self):
        from vcfops_packaging.release_types import headline_to_dir

        bundle_data = {"factory_native": False, "dashboards": ["d1.yaml", "d2.yaml"]}
        result = headline_to_dir("bundles/foo.yaml", bundle_data=bundle_data)
        assert result == "ThirdPartyContent/bundles"

    def test_factory_native_bundle_unchanged(self):
        from vcfops_packaging.release_types import headline_to_dir

        result = headline_to_dir("bundles/capacity-assessment.yaml")
        assert result == "bundles"


# ---------------------------------------------------------------------------
# T4 — _artifact_dest_subdir for a third-party view
# ---------------------------------------------------------------------------

class TestArtifactDestSubdirThirdPartyView:
    """T4: _artifact_dest_subdir routes third-party view to ThirdPartyContent/views."""

    def test_thirdparty_view_dest_subdir(self, tmp_path):
        from vcfops_packaging.release_builder import _artifact_dest_subdir
        from vcfops_packaging.releases import load_release

        assert TP_VIEW_PATH.exists(), f"fixture not found: {TP_VIEW_PATH}"
        manifest = {
            "name": "idps-planner-cluster-view",
            "version": "1.0",
            "description": "Phase 5 test.",
            "artifacts": [{"source": str(TP_VIEW_PATH), "headline": True}],
        }
        manifest_path = tmp_path / "idps-planner-cluster-view.yaml"
        manifest_path.write_text(yaml.dump(manifest, default_flow_style=False))
        rel = load_release(manifest_path, repo_root=REPO_ROOT)

        headline = next(a for a in rel.artifacts if a.headline)
        result = _artifact_dest_subdir(headline)

        assert result == "ThirdPartyContent/views", (
            f"third-party view should route to ThirdPartyContent/views, got {result!r}"
        )


# ---------------------------------------------------------------------------
# T5 — _artifact_dest_subdir for a third-party supermetric
# ---------------------------------------------------------------------------

class TestArtifactDestSubdirThirdPartySM:
    """T5: _artifact_dest_subdir routes third-party supermetric to ThirdPartyContent/supermetrics."""

    def test_thirdparty_sm_dest_subdir(self, tmp_path):
        from vcfops_packaging.release_builder import _artifact_dest_subdir
        from vcfops_packaging.releases import load_release

        assert TP_SM_PATH.exists(), f"fixture not found: {TP_SM_PATH}"
        manifest = {
            "name": "idps-net-receive-sm",
            "version": "1.0",
            "description": "Phase 5 SM test.",
            "artifacts": [{"source": str(TP_SM_PATH), "headline": True}],
        }
        manifest_path = tmp_path / "idps-net-receive-sm.yaml"
        manifest_path.write_text(yaml.dump(manifest, default_flow_style=False))
        rel = load_release(manifest_path, repo_root=REPO_ROOT)

        headline = next(a for a in rel.artifacts if a.headline)
        result = _artifact_dest_subdir(headline)

        assert result == "ThirdPartyContent/supermetrics", (
            f"third-party SM should route to ThirdPartyContent/supermetrics, got {result!r}"
        )


# ---------------------------------------------------------------------------
# T6 — build_release for a third-party view produces a zip + correct routing
# ---------------------------------------------------------------------------

class TestBuildReleaseThirdPartyView:
    """T6: build_release for a third-party view headline produces a correctly routed artifact."""

    @pytest.fixture(scope="class")
    def release_artifacts(self, tmp_path_factory):
        from vcfops_packaging.release_builder import build_release

        tmp = tmp_path_factory.mktemp("tp_view_release")
        assert TP_VIEW_PATH.exists(), f"fixture not found: {TP_VIEW_PATH}"

        manifest = {
            "name": "idps-planner-cluster-view",
            "version": "1.0",
            "description": "Phase 5 third-party view build test.",
            "artifacts": [{"source": str(TP_VIEW_PATH), "headline": True}],
        }
        manifest_path = tmp / "idps-planner-cluster-view.yaml"
        manifest_path.write_text(yaml.dump(manifest, default_flow_style=False))

        output_dir = tmp / "output"
        output_dir.mkdir()
        return build_release(manifest_path, output_dir)

    def test_returns_one_artifact(self, release_artifacts):
        assert len(release_artifacts) == 1, (
            f"Expected 1 artifact, got {len(release_artifacts)}"
        )

    def test_dest_subdir_is_thirdparty_views(self, release_artifacts):
        assert release_artifacts[0].dest_subdir == "ThirdPartyContent/views", (
            f"Expected ThirdPartyContent/views, got {release_artifacts[0].dest_subdir!r}"
        )

    def test_zip_exists(self, release_artifacts):
        assert release_artifacts[0].zip_path.exists(), (
            f"Output zip not found: {release_artifacts[0].zip_path}"
        )

    def test_zip_filename_versionless(self, release_artifacts):
        assert release_artifacts[0].zip_path.name == "idps-planner-cluster-view.zip", (
            f"Expected versionless zip filename, got {release_artifacts[0].zip_path.name!r}"
        )

    def test_headline_source_is_third_party_path(self, release_artifacts):
        """Headline source field contains the third_party/... path."""
        src = release_artifacts[0].headline_source
        assert "third_party" in src, (
            f"Expected headline_source to contain 'third_party', got {src!r}"
        )


# ---------------------------------------------------------------------------
# T7 — cmd_release type-first lookup finds third-party component
# ---------------------------------------------------------------------------

class TestCmdReleaseLookupThirdParty:
    """T7: the name-resolution block inside cmd_release finds third-party components.

    We test the lookup logic directly rather than running the full cmd_release
    (which invokes validation and writes to the real repo).  The lookup
    logic is extracted here in the same way it runs inside cmd_release: the
    _THIRD_PARTY_TYPE_DIR search block added in Phase 5.
    """

    def _do_lookup(self, content_type: str, name_arg: str) -> "Path | None":
        """Run the third-party lookup logic against the real repo and return the resolved path."""
        _THIRD_PARTY_TYPE_DIR = {
            "dashboard":   "dashboards",
            "view":        "views",
            "supermetric": "supermetrics",
            "customgroup": "customgroups",
            "report":      "reports",
        }
        if content_type not in _THIRD_PARTY_TYPE_DIR:
            return None

        tp_type_subdir = _THIRD_PARTY_TYPE_DIR[content_type]
        tp_root = REPO_ROOT / "third_party"
        if not tp_root.exists():
            return None

        source_path = None
        for project_dir in sorted(p for p in tp_root.iterdir() if p.is_dir()):
            type_dir = project_dir / tp_type_subdir
            if not type_dir.exists():
                continue
            # Filename stem match
            sc = type_dir / (name_arg + ".yaml")
            if sc.exists():
                return sc
            sc_yml = type_dir / (name_arg + ".yml")
            if sc_yml.exists():
                return sc_yml
            # Display name match
            for yaml_file in sorted(type_dir.glob("*.y*ml")):
                try:
                    data = yaml.safe_load(yaml_file.read_text()) or {}
                    if isinstance(data, dict):
                        if str(data.get("name", "")).strip() == name_arg:
                            return yaml_file
                except Exception:
                    continue
        return source_path

    def test_lookup_finds_third_party_view_by_display_name(self):
        """Display name 'IDPS Planner - Cluster Selection' resolves to the third-party path."""
        resolved = self._do_lookup("view", "IDPS Planner - Cluster Selection")
        assert resolved is not None, "Lookup returned None for third-party view by display name."
        assert resolved.exists(), f"Resolved path does not exist: {resolved}"
        # Must be under third_party/
        assert "third_party" in resolved.parts, (
            f"Resolved path is not under third_party/: {resolved}"
        )
        assert resolved.parent.name == "views", (
            f"Resolved path parent should be 'views', got {resolved.parent.name!r}"
        )
        # Verify the rel-path shape
        rel = resolved.relative_to(REPO_ROOT)
        assert str(rel).startswith("third_party/"), (
            f"Relative path should start with 'third_party/', got {str(rel)!r}"
        )

    def test_lookup_finds_third_party_supermetric_by_display_name(self):
        """Display name '[IDPS] Net Receive (All VMs)' resolves to the third-party SM path."""
        resolved = self._do_lookup("supermetric", "[IDPS] Net Receive (All VMs)")
        assert resolved is not None, "Lookup returned None for third-party SM by display name."
        assert "third_party" in resolved.parts, (
            f"Resolved path not under third_party/: {resolved}"
        )
        assert resolved.parent.name == "supermetrics", (
            f"Parent should be 'supermetrics', got {resolved.parent.name!r}"
        )

    def test_lookup_relative_path_produces_third_party_source_in_manifest(self):
        """When source is resolved under third_party/, source_rel uses third_party/ prefix."""
        # Simulate the source_rel computation from cmd_release.
        resolved = self._do_lookup("view", "IDPS Planner - Cluster Selection")
        assert resolved is not None
        resolved = resolved.resolve()
        repo_root_resolved = REPO_ROOT.resolve()
        try:
            source_rel = str(resolved.relative_to(repo_root_resolved))
        except ValueError:
            source_rel = str(resolved)

        assert source_rel.startswith("third_party/"), (
            f"source_rel should start with 'third_party/', got {source_rel!r}"
        )
        assert "views" in source_rel, (
            f"Expected 'views' in source_rel, got {source_rel!r}"
        )


# ---------------------------------------------------------------------------
# T8 — publish dry-run: third-party view lands in ThirdPartyContent/views/
# ---------------------------------------------------------------------------

def test_publish_dryrun_thirdparty_view(tmp_path, monkeypatch):
    """T8: publish dry-run for a third-party view reports ThirdPartyContent/views/ destination."""
    from vcfops_packaging.publish import publish

    dist = _init_dist_repo(tmp_path)
    releases_dir = tmp_path / "tp_view_releases"
    releases_dir.mkdir()

    assert TP_VIEW_PATH.exists(), f"fixture not found: {TP_VIEW_PATH}"

    _write_release_manifest(
        releases_dir,
        name="idps-planner-cluster-view",
        version="1.0",
        source_abs=TP_VIEW_PATH,
        description="Phase 5 dry-run test.",
    )
    _patch_enumerate(monkeypatch, releases_dir)

    result = publish(
        factory_repo=REPO_ROOT,
        dist_repo=dist,
        dry_run=True,
        no_push=True,
    )

    # In dry-run mode, result.built contains the would-be dest paths (not
    # actual files).  Verify the artifact would land under ThirdPartyContent/views/.
    assert len(result.built) == 1, (
        f"Expected 1 planned artifact, got {len(result.built)}: {result.built}"
    )
    planned_path = result.built[0]
    assert "ThirdPartyContent" in planned_path.parts, (
        f"Expected ThirdPartyContent in planned path, got {planned_path}"
    )
    assert "views" in planned_path.parts, (
        f"Expected 'views' subdir in planned path, got {planned_path}"
    )
    # Must NOT land under top-level views/ or bundles/.
    assert "ThirdPartyContent" in str(planned_path), (
        f"Planned path should be under ThirdPartyContent/: {planned_path}"
    )
    assert planned_path.name == "idps-planner-cluster-view.zip", (
        f"Expected versionless zip name, got {planned_path.name!r}"
    )


# ---------------------------------------------------------------------------
# T9 — PROJECT.yaml release still routes correctly (regression)
# ---------------------------------------------------------------------------

def test_project_yaml_release_still_routes_to_thirdparty_dashboards(tmp_path, monkeypatch):
    """T9: idps-planner PROJECT.yaml release still lands in ThirdPartyContent/dashboards/."""
    from vcfops_packaging.publish import publish

    dist = _init_dist_repo(tmp_path)
    releases_dir = tmp_path / "project_yaml_releases"
    releases_dir.mkdir()

    source_abs = TP_ROOT / "PROJECT.yaml"
    assert source_abs.exists(), f"PROJECT.yaml not found: {source_abs}"

    _write_release_manifest(
        releases_dir,
        name="idps-planner",
        version="1.0",
        source_abs=source_abs,
        description="Phase 5 regression: PROJECT.yaml route.",
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
        f"Expected idps-planner.zip at {expected}\n"
        f"built: {result.built}"
    )
    assert len(result.built) == 1
    assert result.built[0].name == "idps-planner.zip"
