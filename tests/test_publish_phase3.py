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

    source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
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
        # Versionless consumer artifact name.
        assert result.built[0].name == "demand-driven-capacity-v2.zip", (
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
    """S2a: zip lands at <dist>/dashboards/<slug>.zip (versionless)."""
    from vcfops_packaging.publish import publish

    dist = _init_dist_repo(tmp_path)
    releases_dir = tmp_path / "rr_releases"
    releases_dir.mkdir()
    source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
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

    # Versionless consumer artifact: <slug>.zip, not <slug>-<version>.zip.
    expected = dist / "dashboards" / "demand-driven-capacity-v2.zip"
    assert expected.exists(), (
        f"Expected zip not found: {expected}\nbuilt: {result.built}"
    )
    assert len(result.built) == 1
    assert result.built[0].name == "demand-driven-capacity-v2.zip"


def test_real_run_readme_regenerated(tmp_path, monkeypatch):
    """S2b: README is regenerated and human content outside markers is preserved."""
    from vcfops_packaging.publish import publish

    dist = _init_dist_repo(tmp_path)
    releases_dir = tmp_path / "rr_releases2"
    releases_dir.mkdir()
    source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
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
    source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
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
    """S3: a second publish with identical release manifests produces no new commit.

    With the versionless naming, publish always builds and copies the zip.
    Idempotence is at the git level: if the zip bytes are unchanged, git sees
    no diff and produces no new commit (commit_sha is None on the second run).
    """

    def test_second_publish_no_new_commit(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases2"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Idempotence test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        # First publish — should produce a commit.
        result1 = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )
        assert len(result1.built) == 1, f"First run should build 1, got {result1.built}"
        assert result1.commit_sha is not None, "First run should produce a commit"

        # Second publish — identical content; git diff shows nothing changed.
        result2 = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )
        # Built list still populated (zip was re-copied) but no new commit.
        assert result2.commit_sha is None, (
            f"Second run should produce no commit (content unchanged), "
            f"but got commit_sha={result2.commit_sha!r}"
        )

    def test_second_publish_commit_count_unchanged(self, tmp_path, monkeypatch):
        """Commit count must not increase when content is byte-identical."""
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases2b"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Idempotence commit count test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, no_push=True)

        r_after_first = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True,
        )
        count_after_first = int(r_after_first.stdout.strip())

        publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, no_push=True)

        r_after_second = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True,
        )
        count_after_second = int(r_after_second.stdout.strip())

        assert count_after_second == count_after_first, (
            f"Commit count changed on idempotent second publish: "
            f"{count_after_first} → {count_after_second}"
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
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
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
        """Download link target must be '<subdir>/<slug>.zip' (versionless)."""
        readme, _dist = self._run_publish_and_read_readme(tmp_path, monkeypatch)
        # The correct path-prefixed, versionless link must appear.
        assert "[Download](dashboards/demand-driven-capacity-v2.zip)" in readme, (
            f"Expected subdir-prefixed versionless download link not found.\n"
            f"README excerpt:\n{readme[readme.find('demand-driven'):][:400]}"
        )

    def test_download_cell_does_not_use_bare_filename(self, tmp_path, monkeypatch):
        """The old bare-filename pattern (Bug 1) must not appear."""
        readme, _dist = self._run_publish_and_read_readme(tmp_path, monkeypatch)
        # Bare filename link (no subdir prefix before the zip name) should be absent.
        assert "](demand-driven-capacity-v2.zip)" not in readme, (
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
        """Table header must contain 'Download' and 'Install' columns but not 'Version'."""
        readme, _dist = self._run_publish_and_read_readme(tmp_path, monkeypatch)
        assert "| Download |" in readme, (
            "Separate 'Download' column header not found in README."
        )
        assert "| Install |" in readme, (
            "Separate 'Install' column header not found in README."
        )
        # Version is internal-only — must not appear in consumer-facing catalog.
        assert "| Version |" not in readme, (
            "Version column must not appear in consumer-facing README catalog table."
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


# ---------------------------------------------------------------------------
# S6 — lockfile NOT in commit  (Fix 2 regression)
# ---------------------------------------------------------------------------

class TestLockfileNotInCommit:
    """S6: .publish.lock must never appear in the commit written to the dist repo.

    Regression test for the bug where git add -A ran while the lockfile was
    still on disk, causing it to be tracked in the commit.
    """

    def test_lockfile_absent_from_commit_tree(self, tmp_path, monkeypatch):
        """After a successful publish(), git ls-tree HEAD must not list .publish.lock."""
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases_lockcommit"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Lockfile-not-in-commit regression test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )

        assert result.commit_sha is not None, "Expected a commit to have been made"

        # Inspect the commit tree for .publish.lock.
        r = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"],
            cwd=str(dist), capture_output=True, text=True, check=True,
        )
        tracked_files = r.stdout.splitlines()
        assert ".publish.lock" not in tracked_files, (
            f".publish.lock was committed to the dist repo.\n"
            f"Tracked files in HEAD: {tracked_files}"
        )

    def test_lockfile_absent_from_commit_stat(self, tmp_path, monkeypatch):
        """git show HEAD --stat must not list .publish.lock in the diff."""
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases_lockstat"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Lockfile stat regression test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )

        assert result.commit_sha is not None

        r = subprocess.run(
            ["git", "show", "HEAD", "--stat", "--name-only"],
            cwd=str(dist), capture_output=True, text=True, check=True,
        )
        commit_output = r.stdout
        assert ".publish.lock" not in commit_output, (
            f".publish.lock appeared in 'git show HEAD --stat'.\n"
            f"Output:\n{commit_output}"
        )

    def test_lockfile_also_not_on_disk_after_commit(self, tmp_path, monkeypatch):
        """The lockfile must be removed from disk (not just from the commit)."""
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases_lockdisk"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Lockfile on-disk cleanup test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )

        lockfile = dist / ".publish.lock"
        assert not lockfile.exists(), (
            f"Lockfile still on disk after publish completed: {lockfile}"
        )


# ---------------------------------------------------------------------------
# S7 — policy caveat appears in per-zip READMEs  (Fix 1 regression)
# ---------------------------------------------------------------------------

class TestPolicyCaveatInReadme:
    """S7: the Default Policy caveat must appear in every per-zip README surface.

    Three surfaces checked:
      (a) top-level README.md (from README_framework.md template)
      (b) bundle-level README (from builder._generate_bundle_readme)
      (c) discrete-level README (from discrete_builder._generate_discrete_readme)
    """

    _CAVEAT_FRAGMENT = "Default Policy"

    def test_framework_readme_template_has_caveat(self):
        """The static README_framework.md template contains the policy caveat."""
        from pathlib import Path
        template = (
            Path(__file__).parent.parent
            / "vcfops_packaging" / "templates" / "README_framework.md"
        )
        content = template.read_text(encoding="utf-8")
        assert self._CAVEAT_FRAGMENT in content, (
            f"Policy caveat fragment {self._CAVEAT_FRAGMENT!r} not found in "
            f"README_framework.md.\nTemplate excerpt:\n{content[:1000]}"
        )

    def test_bundle_readme_has_caveat(self, tmp_path, monkeypatch):
        """A built bundle zip's top-level README.md contains the policy caveat."""
        from vcfops_packaging.publish import publish
        import zipfile

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "caveat_bundle"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Policy caveat bundle test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )

        assert result.built, "Expected at least one built zip"
        zip_path = result.built[0]
        assert zip_path.exists(), f"Built zip not found: {zip_path}"

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            # Top-level README.md (from framework template)
            assert "README.md" in names, f"README.md not in zip: {names}"
            readme = zf.read("README.md").decode("utf-8")

        assert self._CAVEAT_FRAGMENT in readme, (
            f"Policy caveat fragment {self._CAVEAT_FRAGMENT!r} not found in "
            f"top-level README.md inside the built zip.\n"
            f"README excerpt:\n{readme[:1500]}"
        )

    def test_bundle_inner_readme_has_caveat(self, tmp_path, monkeypatch):
        """A built bundle zip's bundle-level README.md contains the policy caveat."""
        from vcfops_packaging.publish import publish
        import zipfile

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "caveat_bundle_inner"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Policy caveat bundle inner test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )

        assert result.built
        with zipfile.ZipFile(result.built[0]) as zf:
            names = zf.namelist()
            # Bundle-level README is at bundles/<slug>/README.md
            inner_readmes = [n for n in names if n.endswith("/README.md")]
            assert inner_readmes, (
                f"No bundle-level README.md found in zip. Names: {names}"
            )
            inner_readme = zf.read(inner_readmes[0]).decode("utf-8")

        assert self._CAVEAT_FRAGMENT in inner_readme, (
            f"Policy caveat fragment {self._CAVEAT_FRAGMENT!r} not found in "
            f"bundle-level README.md ({inner_readmes[0]}) inside the built zip.\n"
            f"README excerpt:\n{inner_readme[:1500]}"
        )


# ---------------------------------------------------------------------------
# Versionless naming + legacy cleanup
# ---------------------------------------------------------------------------

class TestVersionlessNaming:
    """New requirement: consumer-facing artifacts use <slug>.zip, not <slug>-<version>.zip."""

    def test_versionless_zip_lands_at_correct_path(self, tmp_path, monkeypatch):
        """A published release lands at <dist>/<subdir>/<slug>.zip, not <slug>-<version>.zip."""
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "vl_releases"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Versionless naming test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )

        # Versionless zip must exist.
        versionless = dist / "dashboards" / "demand-driven-capacity-v2.zip"
        assert versionless.exists(), (
            f"Versionless zip not found at {versionless}\nbuilt: {result.built}"
        )
        # Legacy versioned zip must NOT exist.
        versioned = dist / "dashboards" / "demand-driven-capacity-v2-1.0.zip"
        assert not versioned.exists(), (
            f"Legacy versioned zip should not exist: {versioned}"
        )

    def test_legacy_versioned_zip_deleted_on_publish(self, tmp_path, monkeypatch):
        """A pre-existing legacy <slug>-<X.Y>.zip is deleted in-place on publish."""
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)

        # Pre-place a legacy versioned zip.
        dashboards_dir = dist / "dashboards"
        dashboards_dir.mkdir(parents=True, exist_ok=True)
        legacy_zip = dashboards_dir / "demand-driven-capacity-v2-1.0.zip"
        legacy_zip.write_bytes(b"legacy versioned content")

        # Stage + commit so the dist repo is clean for the pre-check.
        subprocess.run(["git", "add", "-A"], cwd=str(dist), capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add legacy versioned zip"],
            cwd=str(dist), capture_output=True,
        )

        releases_dir = tmp_path / "legacy_releases"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Legacy cleanup test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )

        # Legacy versioned zip must be gone from dashboards/.
        assert not legacy_zip.exists(), (
            f"Legacy versioned zip should have been deleted, still at: {legacy_zip}"
        )
        # It must NOT be in retired/ — it is a naming-era artifact, not deprecated content.
        retired_path = dist / "retired" / "dashboards" / legacy_zip.name
        assert not retired_path.exists(), (
            f"Legacy versioned zip was moved to retired/ instead of deleted: {retired_path}"
        )
        # result.deleted must record it.
        deleted_names = [p.name for p in result.deleted]
        assert legacy_zip.name in deleted_names, (
            f"Legacy zip name not in result.deleted: {deleted_names}"
        )
        # Versionless zip must now be present.
        assert (dist / "dashboards" / "demand-driven-capacity-v2.zip").exists(), (
            "Versionless zip should have been created alongside the deletion."
        )

    def test_legacy_zip_safe_for_release_with_version_looking_slug(self, tmp_path, monkeypatch):
        """A release whose slug ends in a version-looking suffix is NOT eaten by the sweep.

        A release named 'something-1.2' produces 'something-1.2.zip'.  The legacy
        sweep must not delete it because the slug 'something-1' doesn't match any
        known release slug.
        """
        from vcfops_packaging.publish import _sweep_legacy_versioned_zips

        dist = tmp_path / "dist"
        dashboards_dir = dist / "dashboards"
        dashboards_dir.mkdir(parents=True)

        # Simulate a zip whose name looks like a legacy versioned name.
        safe_zip = dashboards_dir / "something-1.2.zip"
        safe_zip.write_bytes(b"content")

        # The slug 'something-1' is not a known release slug (known slug is 'something-1.2').
        known_slugs = {"something-1.2"}
        deleted = _sweep_legacy_versioned_zips(dist, known_slugs, dry_run=True)

        assert safe_zip not in deleted and not any(
            p.name == safe_zip.name for p in deleted
        ), (
            f"Safe zip 'something-1.2.zip' was incorrectly identified as a "
            f"legacy versioned zip.  deleted: {[p.name for p in deleted]}"
        )


# ---------------------------------------------------------------------------
# --force flag: forces a commit even when content is byte-identical
# ---------------------------------------------------------------------------

class TestForceFlag:
    """--force triggers a commit even when no content changed."""

    def test_force_commits_when_content_unchanged(self, tmp_path, monkeypatch):
        """After an identical second publish with force=True, a new commit exists."""
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "force_releases"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Force flag test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        # First publish — establishes baseline.
        result1 = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
        )
        assert result1.commit_sha is not None, "First publish should produce a commit"

        r_count1 = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True,
        )
        count1 = int(r_count1.stdout.strip())

        # Second publish with force=True — should produce a commit even though
        # the content is byte-identical.
        result2 = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            force=True,
            no_push=True,
        )
        assert result2.commit_sha is not None, (
            "force=True should produce a commit even when content is unchanged"
        )

        r_count2 = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True,
        )
        count2 = int(r_count2.stdout.strip())
        assert count2 == count1 + 1, (
            f"force=True should add exactly one commit; "
            f"count before={count1}, after={count2}"
        )

    def test_normal_second_publish_no_commit(self, tmp_path, monkeypatch):
        """Without --force, a second identical publish produces no commit."""
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "force_normal_releases"
        releases_dir.mkdir()
        source_abs = (REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml").resolve()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=source_abs,
            description="Force flag normal run test.",
        )
        _patch_enumerate(monkeypatch, releases_dir)

        publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, no_push=True)

        r_count1 = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True,
        )
        count1 = int(r_count1.stdout.strip())

        result2 = publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, no_push=True)
        assert result2.commit_sha is None, (
            "Second publish without --force should produce no commit when content is unchanged"
        )

        r_count2 = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True,
        )
        count2 = int(r_count2.stdout.strip())
        assert count2 == count1, (
            f"Commit count should not change on identical re-publish: {count1} → {count2}"
        )
