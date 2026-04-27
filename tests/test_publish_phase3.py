"""Phase 3 smoke tests for vcfops_packaging.publish.

Five scenarios as specified:

  S1 — dry-run:
       publish(dry_run=True) returns PublishResult showing the dashboard would
       be built but no files were copied and no commit happened.

  S2 — real run (no_push):
       publish(dry_run=False, no_push=True) builds the zip, copies it to
       <dist>/dashboards/, regenerates README, commits in the temp dist repo,
       does not push.

  S3 — no-op skip:
       A follow-up publish() with no new release manifests is a complete no-op
       (everything skipped, no new commit).

  S4 — stale-zip sweep:
       A manually-placed legacy zip (no corresponding release manifest) is moved
       to retired/<subdir>/ on publish.

  S5 — lockfile guard:
       Writing the lockfile manually and then attempting a publish raises a
       clear PublishError.

All tests use temp directories — the real vcf-content-factory-bundles/ repo
is never written to.
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
# Helpers: temp dist repo
# ---------------------------------------------------------------------------

def _init_dist_repo(tmp_path: Path, *, with_auto_markers: bool = True) -> Path:
    """Initialise a minimal git repo mimicking the dist repo layout.

    - git init
    - Commits a LICENSE and a README.md (with or without AUTO markers).
    """
    dist = tmp_path / "dist-repo"
    dist.mkdir()

    # git init with an explicit initial branch name
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

    # LICENSE
    (dist / "LICENSE").write_text("MIT License\n")

    # README.md
    if with_auto_markers:
        readme_body = (
            "# VCF Content Factory Bundles\n\n"
            "Human-authored intro.\n\n"
            "<!-- AUTO:START release-catalog -->\n"
            "<!-- AUTO:END -->\n\n"
            "Human-authored footer.\n"
        )
    else:
        readme_body = (
            "# VCF Content Factory Bundles\n\n"
            "Human-authored content, no AUTO markers.\n"
        )
    (dist / "README.md").write_text(readme_body)

    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(dist), capture_output=True, check=True,
    )
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


# ---------------------------------------------------------------------------
# Factory repo fixture: use a temp copy of releases/ so we don't pollute
# the real repo.
# ---------------------------------------------------------------------------

@pytest.fixture
def factory_with_release(tmp_path):
    """Return a (factory_repo, releases_dir) tuple where factory_repo is the
    real REPO_ROOT (content YAML must stay in place) and releases_dir is a
    temp directory that publish() will scan.

    We patch the _enumerate_releases() function to point at our temp dir
    instead of factory_repo/releases/.  This keeps the real releases/ clean
    (no new committed manifests).

    Alternatively: we write our temp manifest into a tmp releases/ dir,
    then call publish() with a custom _releases_dir override via monkeypatching.

    Strategy: monkeypatch vcfops_packaging.publish._enumerate_releases so it
    reads from our temp releases_dir, still using REPO_ROOT as the factory_repo
    for all other operations.
    """
    releases_dir = tmp_path / "tmp_releases"
    releases_dir.mkdir()

    source_abs = (REPO_ROOT / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
    assert source_abs.exists(), f"source not found: {source_abs}"

    _write_release_manifest(
        releases_dir,
        name="demand-driven-capacity-v2",
        version="1.0",
        source_abs=source_abs,
        description="Demand-driven capacity dashboard. First release.",
    )

    return releases_dir


# ---------------------------------------------------------------------------
# Monkeypatch helper: redirect _enumerate_releases to our temp dir.
# ---------------------------------------------------------------------------

def _patch_enumerate(monkeypatch, releases_dir: Path):
    """Replace _enumerate_releases to read from releases_dir instead of
    factory_repo/releases/."""
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
# S1 — dry-run
# ---------------------------------------------------------------------------

class TestDryRun:
    """S1: dry_run=True shows what would happen without writing files."""

    def test_dry_run_result(self, tmp_path, factory_with_release, monkeypatch):
        from vcfops_packaging.publish import publish, PublishError

        dist = _init_dist_repo(tmp_path)
        _patch_enumerate(monkeypatch, factory_with_release)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=True,
            force=False,
            no_push=True,
        )

        # The dashboard should appear in 'built' (would-be path).
        assert len(result.built) == 1, (
            f"Expected 1 would-be built artifact, got {result.built}"
        )
        assert result.built[0].name == "demand-driven-capacity-v2-1.0.zip", (
            f"Unexpected artifact name: {result.built[0].name}"
        )

    def test_dry_run_no_files_copied(self, tmp_path, factory_with_release, monkeypatch):
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        _patch_enumerate(monkeypatch, factory_with_release)

        publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=True,
            force=False,
            no_push=True,
        )

        dashboards_dir = dist / "dashboards"
        if dashboards_dir.exists():
            zips = list(dashboards_dir.glob("*.zip"))
            assert zips == [], (
                f"dry_run=True must not copy files, but found: {zips}"
            )

    def test_dry_run_no_commit(self, tmp_path, factory_with_release, monkeypatch):
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        _patch_enumerate(monkeypatch, factory_with_release)

        # Capture commit count before.
        r_before = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True,
        )
        count_before = int(r_before.stdout.strip())

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=True,
            force=False,
            no_push=True,
        )

        r_after = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True,
        )
        count_after = int(r_after.stdout.strip())

        assert count_after == count_before, (
            f"dry_run=True must not commit, but commit count changed "
            f"from {count_before} to {count_after}"
        )
        assert result.commit_sha is None, (
            f"commit_sha must be None on dry_run, got {result.commit_sha!r}"
        )
        assert result.pushed is False


# ---------------------------------------------------------------------------
# S2 — real run, no_push
# ---------------------------------------------------------------------------

def test_real_run_zip_lands(tmp_path, monkeypatch):
    """S2a: zip lands at <dist>/dashboards/<name>-<version>.zip."""
    from vcfops_packaging.publish import publish

    dist = _init_dist_repo(tmp_path)
    releases_dir = tmp_path / "rr_releases"
    releases_dir.mkdir()
    source_abs = (REPO_ROOT / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
    _write_release_manifest(
        releases_dir,
        name="demand-driven-capacity-v2",
        version="1.0",
        source_abs=source_abs,
        description="Demand-driven capacity dashboard. Phase 3 real run.",
    )
    _patch_enumerate(monkeypatch, releases_dir)

    result = publish(
        factory_repo=REPO_ROOT,
        dist_repo=dist,
        dry_run=False,
        no_push=True,
    )

    expected = dist / "dashboards" / "demand-driven-capacity-v2-1.0.zip"
    assert expected.exists(), (
        f"Expected zip not found: {expected}\nbuilt: {result.built}"
    )
    assert len(result.built) == 1
    assert result.built[0].name == "demand-driven-capacity-v2-1.0.zip"


def test_real_run_readme_regenerated(tmp_path, monkeypatch):
    """S2b: README is regenerated and human content outside markers is preserved."""
    from vcfops_packaging.publish import publish

    dist = _init_dist_repo(tmp_path)
    releases_dir = tmp_path / "rr_releases2"
    releases_dir.mkdir()
    source_abs = (REPO_ROOT / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
    _write_release_manifest(
        releases_dir,
        name="demand-driven-capacity-v2",
        version="1.0",
        source_abs=source_abs,
        description="Phase 3 readme test.",
    )
    _patch_enumerate(monkeypatch, releases_dir)

    result = publish(
        factory_repo=REPO_ROOT,
        dist_repo=dist,
        dry_run=False,
        no_push=True,
    )

    readme = dist / "README.md"
    assert readme.exists()
    content = readme.read_text()
    assert "demand-driven-capacity-v2" in content, (
        f"Release name not in regenerated README:\n{content[:600]}"
    )
    assert "Human-authored intro." in content
    assert "Human-authored footer." in content


def test_real_run_commit_and_no_push(tmp_path, monkeypatch):
    """S2c: a commit is created, pushed=False."""
    from vcfops_packaging.publish import publish

    dist = _init_dist_repo(tmp_path)
    releases_dir = tmp_path / "rr_releases3"
    releases_dir.mkdir()
    source_abs = (REPO_ROOT / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
    _write_release_manifest(
        releases_dir,
        name="demand-driven-capacity-v2",
        version="1.0",
        source_abs=source_abs,
        description="Phase 3 commit test.",
    )
    _patch_enumerate(monkeypatch, releases_dir)

    result = publish(
        factory_repo=REPO_ROOT,
        dist_repo=dist,
        dry_run=False,
        no_push=True,
    )

    assert result.commit_sha is not None, "Expected a commit SHA"
    assert result.pushed is False

    r = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(dist), capture_output=True, text=True,
    )
    assert int(r.stdout.strip()) == 2  # initial + publish


# ---------------------------------------------------------------------------
# S3 — no-op skip
# ---------------------------------------------------------------------------

class TestNoOpSkip:
    """S3: a second publish with identical release manifests produces no changes."""

    def test_second_publish_is_noop(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases2"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Idempotence test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        # First publish.
        result1 = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )
        assert len(result1.built) == 1, f"First run should build 1, got {result1.built}"

        # Second publish — same manifests, nothing new.
        result2 = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )
        assert result2.built == [], (
            f"Second run should build nothing (idempotent), got {result2.built}"
        )
        assert len(result2.skipped) == 1, (
            f"Second run should skip the existing zip, got {result2.skipped}"
        )


# ---------------------------------------------------------------------------
# S4 — stale-zip sweep
# ---------------------------------------------------------------------------

class TestStaleZipSweep:
    """S4: a manually-placed legacy zip with no release manifest is moved to retired/."""

    def test_stale_zip_moved_to_retired(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)

        # Place a legacy zip at the top-level dashboards/ subdir that has no
        # corresponding release manifest.
        dashboards_dir = dist / "dashboards"
        dashboards_dir.mkdir(parents=True, exist_ok=True)
        legacy_zip = dashboards_dir / "[VCF Content Factory] VM Performance.zip"
        legacy_zip.write_bytes(b"fake legacy zip content")

        # Stage + commit so dist repo stays clean for the check.
        subprocess.run(["git", "add", "-A"], cwd=str(dist), capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add legacy zip"],
            cwd=str(dist), capture_output=True,
        )

        # Empty releases dir — no release manifests at all.
        releases_dir = tmp_path / "releases_empty"
        releases_dir.mkdir()
        _patch_enumerate(monkeypatch, releases_dir)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )

        # Legacy zip must be gone from dashboards/.
        assert not legacy_zip.exists(), (
            f"Legacy zip should have been swept to retired/, still at: {legacy_zip}"
        )

        # Legacy zip must now be in retired/dashboards/.
        retired_path = dist / "retired" / "dashboards" / legacy_zip.name
        assert retired_path.exists(), (
            f"Legacy zip not found in retired/: {retired_path}\n"
            f"retired list: {result.retired}"
        )

        # result.retired must reference it.
        retired_names = [p.name for p in result.retired]
        assert legacy_zip.name in retired_names, (
            f"Legacy zip name not in result.retired: {retired_names}"
        )


# ---------------------------------------------------------------------------
# S5 — lockfile guard
# ---------------------------------------------------------------------------

class TestLockfileGuard:
    """S5: a pre-existing lockfile causes a clear PublishError."""

    def test_lockfile_blocks_publish(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish, PublishError

        dist = _init_dist_repo(tmp_path)

        # Write the lockfile manually.
        lockfile = dist / ".publish.lock"
        lockfile.write_text("pid=99999 started=2026-04-27T00:00:00Z\n")

        releases_dir = tmp_path / "releases_lock"
        releases_dir.mkdir()
        _patch_enumerate(monkeypatch, releases_dir)

        with pytest.raises(PublishError, match="lockfile"):
            publish(
                factory_repo=REPO_ROOT,
                dist_repo=dist,
                dry_run=True,  # Even dry-run is blocked by lockfile.
            )

    def test_lockfile_released_on_success(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases_lock2"
        releases_dir.mkdir()
        _patch_enumerate(monkeypatch, releases_dir)

        publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=True,
        )

        lockfile = dist / ".publish.lock"
        assert not lockfile.exists(), (
            f"Lockfile should be removed after publish, still exists: {lockfile}"
        )

    def test_lockfile_released_on_error(self, tmp_path, monkeypatch):
        """Lockfile must be cleaned up even when a validator fails."""
        from vcfops_packaging.publish import publish, PublishError

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases_err"
        releases_dir.mkdir()
        _patch_enumerate(monkeypatch, releases_dir)

        # Patch _run_validators to always raise.
        import vcfops_packaging.publish as _pub
        monkeypatch.setattr(
            _pub, "_run_validators",
            lambda _: (_ for _ in ()).throw(PublishError("injected validator failure")),
        )

        with pytest.raises(PublishError, match="injected"):
            publish(
                factory_repo=REPO_ROOT,
                dist_repo=dist,
                dry_run=False,
                no_push=True,
            )

        lockfile = dist / ".publish.lock"
        assert not lockfile.exists(), (
            f"Lockfile should be cleaned up on error, still exists: {lockfile}"
        )


# ---------------------------------------------------------------------------
# Bonus: readme with no AUTO markers produces a warning, not a crash
# ---------------------------------------------------------------------------

class TestReadmeNoMarkers:
    """When the dist repo README has no AUTO markers, publish warns but succeeds."""

    def test_no_markers_no_crash(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path, with_auto_markers=False)
        releases_dir = tmp_path / "releases_nomark"
        releases_dir.mkdir()
        _patch_enumerate(monkeypatch, releases_dir)

        # Must not raise.
        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=True,
        )
        # README path is still returned.
        assert result.readme_path is not None


# ---------------------------------------------------------------------------
# README cell-format assertions (Bug 1 + Bug 2 regression tests)
# ---------------------------------------------------------------------------

class TestReadmeCellFormat:
    """Assert correct Download / Install column shapes in the rendered README.

    Bug 1 — install link was missing the subdir prefix (bare filename).
    Bug 2 — link text implied running the installer; should be two columns.
    """

    def _run_publish_and_read_readme(self, tmp_path, monkeypatch) -> str:
        """Helper: publish a dashboard release and return the README text."""
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "cell_fmt_releases"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Cell format regression test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )
        return (dist / "README.md").read_text(encoding="utf-8"), dist

    def test_download_cell_includes_subdir(self, tmp_path, monkeypatch):
        """Download link target must be '<subdir>/<name>-<version>.zip'."""
        readme, _dist = self._run_publish_and_read_readme(tmp_path, monkeypatch)
        # The correct path-prefixed link must appear.
        assert "[Download](dashboards/demand-driven-capacity-v2-1.0.zip)" in readme, (
            f"Expected subdir-prefixed download link not found.\n"
            f"README excerpt:\n{readme[readme.find('demand-driven'):][:400]}"
        )

    def test_download_cell_does_not_use_bare_filename(self, tmp_path, monkeypatch):
        """The old bare-filename pattern (Bug 1) must not appear."""
        readme, _dist = self._run_publish_and_read_readme(tmp_path, monkeypatch)
        # Bare filename link (no subdir prefix before the zip name) should be absent.
        assert "](demand-driven-capacity-v2-1.0.zip)" not in readme, (
            "Bare-filename download link (Bug 1) is still present in README."
        )

    def test_install_cell_is_code_fence(self, tmp_path, monkeypatch):
        """Install cell must contain the bare command in a code fence, not a link."""
        readme, _dist = self._run_publish_and_read_readme(tmp_path, monkeypatch)
        assert "`python3 install.py`" in readme, (
            f"Expected '`python3 install.py`' not found in README.\n"
            f"README excerpt:\n{readme[readme.find('demand-driven'):][:400]}"
        )
        # The old combined link+command shape (Bug 2) must be gone.
        assert "[`python3 install.py`](" not in readme, (
            "Old combined link-text install cell (Bug 2) is still present in README."
        )

    def test_readme_has_download_and_install_columns(self, tmp_path, monkeypatch):
        """Table header must contain both 'Download' and 'Install' columns."""
        readme, _dist = self._run_publish_and_read_readme(tmp_path, monkeypatch)
        assert "| Download |" in readme, (
            "Separate 'Download' column header not found in README."
        )
        assert "| Install |" in readme, (
            "Separate 'Install' column header not found in README."
        )


class TestRetiredSectionDownloadLink:
    """Retired section download links must use 'retired/<subdir>/' prefix (Bug 1 parity)."""

    def test_retired_download_link_uses_retired_prefix(self, tmp_path, monkeypatch):
        from vcfops_packaging.readme_gen import _render_release_catalog
        from pathlib import Path
        import datetime

        # Build a minimal dist_repo with a retired zip.
        dist = tmp_path / "dist"
        (dist / "retired" / "dashboards").mkdir(parents=True)
        zip_name = "old-dashboard-0.9.zip"
        zip_path = dist / "retired" / "dashboards" / zip_name
        zip_path.write_bytes(b"retired artifact")

        # Render with no active releases so only the Retired section is populated.
        catalog = _render_release_catalog(dist_repo=dist, releases=[])

        expected_link = f"[Download](retired/dashboards/{zip_name})"
        assert expected_link in catalog, (
            f"Expected retired download link '{expected_link}' not found.\n"
            f"Catalog output:\n{catalog}"
        )

    def test_retired_download_link_does_not_use_bare_filename(self, tmp_path, monkeypatch):
        from vcfops_packaging.readme_gen import _render_release_catalog

        dist = tmp_path / "dist2"
        (dist / "retired" / "dashboards").mkdir(parents=True)
        zip_name = "old-dashboard-0.9.zip"
        (dist / "retired" / "dashboards" / zip_name).write_bytes(b"retired artifact")

        catalog = _render_release_catalog(dist_repo=dist, releases=[])

        # Bare filename link (no retired/subdir prefix) must not appear.
        assert f"]({zip_name})" not in catalog, (
            f"Bare-filename retired download link found — subdir prefix is missing.\n"
            f"Catalog output:\n{catalog}"
        )
