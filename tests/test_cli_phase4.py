"""Phase 4 smoke tests for vcfops_packaging CLI: release + publish subcommands.

Six test groups as specified:

  T1 — release smoke: release a dashboard, manifest created, flag flipped.
  T2 — auto-bump: second release without --version produces 1.1.
  T3 — deprecates: --deprecates adds to manifest; errors on missing slug.
  T4 — validate-failure guard: a deliberately broken manifest write is caught.
  T5 — commit: release in a temp git repo produces exactly one commit
       touching the two expected files.
  T6 — publish --dry-run: cmd_publish with dry_run returns success, reports
       what it would do, and writes nothing mutating.

All tests use temp directories.  The real releases/ directory is never
written to, and the real vcf-content-factory-bundles/ is never touched.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_git_repo(path: Path) -> None:
    """Initialise a minimal git repo at path with an initial commit."""
    subprocess.run(["git", "init", "-b", "main"], cwd=str(path),
                   capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@vcfops-test.local"],
                   cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "VCFOps Test"],
                   cwd=str(path), capture_output=True, check=True)
    # Initial commit so HEAD exists.
    (path / "README.md").write_text("test repo\n")
    subprocess.run(["git", "add", "-A"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"],
                   cwd=str(path), capture_output=True, check=True)


def _init_dist_repo(path: Path) -> Path:
    """Minimal dist repo with AUTO markers and an initial commit."""
    dist = path / "dist-repo"
    dist.mkdir()
    _init_git_repo(dist)
    (dist / "README.md").write_text(
        "# VCF Content Factory Bundles\n\n"
        "Intro.\n\n"
        "<!-- AUTO:START release-catalog -->\n"
        "<!-- AUTO:END -->\n\n"
        "Footer.\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=str(dist), capture_output=True)
    subprocess.run(["git", "commit", "-m", "add readme"],
                   cwd=str(dist), capture_output=True)
    return dist


def _make_factory_copy(tmp_path: Path) -> Path:
    """Copy the real repo into tmp_path so tests can mutate content/ and
    content YAML files without touching the real working tree.

    Only copies content we need: content/ (all subdirs) and the vcfops_* packages.
    """
    factory = tmp_path / "factory"
    factory.mkdir()

    # Copy the content/ umbrella directory (v3 layout), but exclude existing
    # release manifests so cmd_release tests start clean (version = "1.0").
    src_content = REPO_ROOT / "content"
    if src_content.exists():
        shutil.copytree(str(src_content), str(factory / "content"))
        # Remove any pre-existing release manifests so tests start at v1.0.
        releases_dir = factory / "releases"
        if releases_dir.exists():
            shutil.rmtree(str(releases_dir))
            releases_dir.mkdir()
        # Reset released: true flags on dashboards so flag-flip tests start clean.
        import yaml as _yaml
        for dash_yaml in (factory / "content" / "dashboards").glob("*.yaml"):
            d = _yaml.safe_load(dash_yaml.read_text()) or {}
            if d.get("released"):
                d["released"] = False
                dash_yaml.write_text(_yaml.dump(d, default_flow_style=False, allow_unicode=True))
    else:
        (factory / "content").mkdir(exist_ok=True)

    # symlink vcfops_* packages and vcfops_common back to the real location
    # so imports work, without creating duplicate symlinks.
    _linked: set[str] = set()
    for pkg in REPO_ROOT.glob("vcfops_*"):
        if pkg.is_dir() and pkg.name not in _linked:
            (factory / pkg.name).symlink_to(pkg.resolve())
            _linked.add(pkg.name)

    # Copy describe cache if present (needed for validators).
    describe_cache = REPO_ROOT / ".describe_cache.json"
    if describe_cache.exists():
        shutil.copy2(str(describe_cache), str(factory / ".describe_cache.json"))

    # git init so the release commit step works.
    _init_git_repo(factory)
    # Stage + commit the content files so the tree is clean.
    subprocess.run(["git", "add", "-A"], cwd=str(factory), capture_output=True)
    subprocess.run(["git", "commit", "-m", "content"],
                   cwd=str(factory), capture_output=True)

    return factory


def _build_release_args(**kwargs) -> SimpleNamespace:
    """Build a SimpleNamespace mimicking argparse args for cmd_release."""
    defaults = {
        "content_type": "dashboard",
        "name": "demand_driven_capacity_v2",
        "version": None,
        "notes": None,
        "deprecates": None,
        "no_commit": True,  # default no-commit for most tests; override per-test
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# T1 — release smoke: manifest created, flag flipped
# ---------------------------------------------------------------------------

class TestReleaseSmoke:
    """T1: basic release invocation creates manifest and flips released flag."""

    def test_manifest_created(self, tmp_path, monkeypatch):
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(no_commit=True)
        rc = cmd_release(args)
        assert rc == 0, f"cmd_release returned {rc}"

        # New convention: slug = <stem>-<type> = demand-driven-capacity-v2-dashboard
        manifest_path = factory / "releases" / "demand-driven-capacity-v2-dashboard.yaml"
        assert manifest_path.exists(), f"manifest not created: {manifest_path}"

    def test_manifest_schema(self, tmp_path, monkeypatch):
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(no_commit=True)
        cmd_release(args)

        manifest_path = factory / "releases" / "demand-driven-capacity-v2-dashboard.yaml"
        data = yaml.safe_load(manifest_path.read_text())

        assert data["name"] == "demand-driven-capacity-v2-dashboard"
        assert data["version"] == "1.0"
        assert isinstance(data["description"], str) and data["description"].strip()
        assert isinstance(data["artifacts"], list) and len(data["artifacts"]) == 1
        assert data["artifacts"][0]["headline"] is True
        assert "demand_driven_capacity_v2.yaml" in data["artifacts"][0]["source"]

    def test_released_flag_flipped(self, tmp_path, monkeypatch):
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        dashboard_yaml = factory / "content" / "dashboards" / "demand_driven_capacity_v2.yaml"
        # Confirm not yet released.
        before = yaml.safe_load(dashboard_yaml.read_text()) or {}
        assert not before.get("released", False)

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(no_commit=True)
        cmd_release(args)

        after = yaml.safe_load(dashboard_yaml.read_text()) or {}
        assert after.get("released") is True, (
            f"released flag not flipped; dashboard YAML:\n{dashboard_yaml.read_text()[:400]}"
        )

    def test_display_name_resolution(self, tmp_path, monkeypatch):
        """T1: display name lookup resolves to correct source file."""
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        display_name = "[VCF Content Factory] Demand-Driven Capacity Planning v2"
        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(name=display_name, no_commit=True)
        rc = cmd_release(args)
        assert rc == 0, f"display-name resolution returned {rc}"
        # New convention slug: <stem>-dashboard
        assert (factory / "releases" / "demand-driven-capacity-v2-dashboard.yaml").exists()

    def test_path_resolution(self, tmp_path, monkeypatch):
        """T1: explicit relative path resolves to correct source file."""
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(
            name="content/dashboards/demand_driven_capacity_v2.yaml",
            no_commit=True,
        )
        rc = cmd_release(args)
        assert rc == 0
        assert (factory / "releases" / "demand-driven-capacity-v2-dashboard.yaml").exists()


# ---------------------------------------------------------------------------
# T2 — auto-bump: second release without --version produces 1.1
# ---------------------------------------------------------------------------

class TestAutoBump:
    """T2: auto-bump path produces 1.1 on second invocation."""

    def test_auto_bump_minor(self, tmp_path, monkeypatch):
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_release

        # First release -> 1.0  (new slug convention: demand-driven-capacity-v2-dashboard)
        args1 = _build_release_args(no_commit=True)
        rc = cmd_release(args1)
        assert rc == 0
        manifest_path = factory / "releases" / "demand-driven-capacity-v2-dashboard.yaml"
        v1 = yaml.safe_load(manifest_path.read_text())["version"]
        assert v1 == "1.0", f"first release version should be 1.0, got {v1!r}"

        # Second release without --version -> 1.1
        args2 = _build_release_args(no_commit=True)
        rc = cmd_release(args2)
        assert rc == 0
        v2 = yaml.safe_load(manifest_path.read_text())["version"]
        assert v2 == "1.1", f"second release version should be 1.1, got {v2!r}"

    def test_explicit_version_override(self, tmp_path, monkeypatch):
        """Explicit --version 2.0 overrides auto-bump."""
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(version="2.0", no_commit=True)
        rc = cmd_release(args)
        assert rc == 0
        manifest_path = factory / "releases" / "demand-driven-capacity-v2-dashboard.yaml"
        v = yaml.safe_load(manifest_path.read_text())["version"]
        assert v == "2.0", f"explicit version should be 2.0, got {v!r}"

    def test_noop_explicit_version_errors(self, tmp_path, monkeypatch):
        """--version X.Y on an already-at-X.Y manifest is a hard error."""
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_release
        # First release at 1.0.
        cmd_release(_build_release_args(version="1.0", no_commit=True))
        # Second call with same version -> error.
        rc = cmd_release(_build_release_args(version="1.0", no_commit=True))
        assert rc != 0, "no-op release attempt should return non-zero"


# ---------------------------------------------------------------------------
# T3 — deprecates: adds to manifest; errors on missing slug
# ---------------------------------------------------------------------------

class TestDeprecates:
    """T3: --deprecates flag handling."""

    def test_deprecates_added_to_manifest(self, tmp_path, monkeypatch):
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        # Create a prior release manifest manually (so there's something to deprecate).
        prior_slug = "some-prior-slug"
        prior_manifest = factory / "releases" / f"{prior_slug}.yaml"
        prior_manifest.parent.mkdir(parents=True, exist_ok=True)
        prior_manifest.write_text(yaml.dump({
            "name": prior_slug,
            "version": "1.0",
            "description": "Prior release for deprecation test.",
            "artifacts": [{
                "source": "content/dashboards/demand_driven_capacity_v2.yaml",
                "headline": True,
            }],
        }))

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(deprecates=[prior_slug], no_commit=True)
        rc = cmd_release(args)
        assert rc == 0

        # New convention slug: demand-driven-capacity-v2-dashboard
        manifest_path = factory / "releases" / "demand-driven-capacity-v2-dashboard.yaml"
        data = yaml.safe_load(manifest_path.read_text())
        assert isinstance(data.get("deprecates"), list)
        assert any(prior_slug in d for d in data["deprecates"]), (
            f"prior slug not in deprecates list: {data['deprecates']}"
        )

    def test_deprecates_missing_slug_errors(self, tmp_path, monkeypatch):
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(
            deprecates=["nonexistent-slug"],
            no_commit=True,
        )
        rc = cmd_release(args)
        assert rc != 0, "missing --deprecates target should return non-zero"


# ---------------------------------------------------------------------------
# T4 — validate-failure guard
# ---------------------------------------------------------------------------

class TestValidateFailureGuard:
    """T4: when the post-write validate step catches a bad manifest, cmd_release returns non-zero."""

    def test_validate_catches_bad_write(self, tmp_path, monkeypatch):
        """Monkeypatch validate to fail and confirm cmd_release exits 1."""
        import vcfops_packaging.cli as _cli

        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        # Monkeypatch subprocess.run to simulate a validation failure
        # only for the vcfops_packaging validate call.
        import subprocess as _sp
        original_run = _sp.run

        def _fake_run(cmd, *a, **kw):
            if (
                isinstance(cmd, list)
                and "vcfops_packaging" in cmd
                and "validate" in cmd
            ):
                return _sp.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="",
                    stderr="FAIL  injected validate failure\n",
                )
            return original_run(cmd, *a, **kw)

        monkeypatch.setattr(_sp, "run", _fake_run)

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(no_commit=True)
        rc = cmd_release(args)
        assert rc != 0, "should return non-zero when validate fails"


# ---------------------------------------------------------------------------
# T5 — commit: produces exactly one commit touching exactly two files
# ---------------------------------------------------------------------------

class TestCommit:
    """T5: release commit touches exactly the manifest + source YAML."""

    def test_commit_created(self, tmp_path, monkeypatch):
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        # Count commits before.
        r_before = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(factory), capture_output=True, text=True,
        )
        count_before = int(r_before.stdout.strip())

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(no_commit=False)
        rc = cmd_release(args)
        assert rc == 0

        r_after = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(factory), capture_output=True, text=True,
        )
        count_after = int(r_after.stdout.strip())
        assert count_after == count_before + 1, (
            f"Expected exactly one new commit; before={count_before}, after={count_after}"
        )

    def test_commit_touches_two_files(self, tmp_path, monkeypatch):
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(no_commit=False)
        rc = cmd_release(args)
        assert rc == 0

        # List files in the last commit.
        r = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", "HEAD"],
            cwd=str(factory), capture_output=True, text=True,
        )
        changed = set(r.stdout.strip().splitlines())
        # New convention slug: demand-driven-capacity-v2-dashboard
        assert "releases/demand-driven-capacity-v2-dashboard.yaml" in changed, (
            f"manifest not in commit: {changed}"
        )
        assert "content/dashboards/demand_driven_capacity_v2.yaml" in changed, (
            f"source yaml not in commit: {changed}"
        )
        assert len(changed) == 2, (
            f"expected exactly 2 files in commit, got {len(changed)}: {changed}"
        )

    def test_commit_message_format(self, tmp_path, monkeypatch):
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_release
        args = _build_release_args(no_commit=False)
        rc = cmd_release(args)
        assert rc == 0

        r = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=str(factory), capture_output=True, text=True,
        )
        subject = r.stdout.strip()
        # New convention slug: demand-driven-capacity-v2-dashboard
        assert subject == "release: demand-driven-capacity-v2-dashboard 1.0", (
            f"unexpected commit message: {subject!r}"
        )


# ---------------------------------------------------------------------------
# T6 — publish --dry-run smoke
# ---------------------------------------------------------------------------

class TestPublishCLI:
    """T6: cmd_publish with --dry-run returns success, reports would-be build, writes nothing."""

    def _make_factory_with_release_manifest(self, tmp_path: Path) -> tuple[Path, Path]:
        """Return (factory_repo, dist_repo) with one release manifest already in place."""
        factory = _make_factory_copy(tmp_path)

        # Write a release manifest pointing at the dashboard (source must exist).
        releases_dir = factory / "releases"
        releases_dir.mkdir(parents=True, exist_ok=True)
        dashboard_src = factory / "content" / "dashboards" / "demand_driven_capacity_v2.yaml"

        # Flip released: true on the source so the validator is happy.
        dashboard_data = yaml.safe_load(dashboard_src.read_text()) or {}
        dashboard_data["released"] = True
        dashboard_src.write_text(
            yaml.dump(dashboard_data, default_flow_style=False, allow_unicode=True)
        )

        manifest_data = {
            "name": "demand-driven-capacity-v2",
            "version": "1.0",
            "description": "Phase 4 smoke test.",
            "release_notes": "",
            "artifacts": [{
                "source": "content/dashboards/demand_driven_capacity_v2.yaml",
                "headline": True,
            }],
            "deprecates": [],
        }
        (releases_dir / "demand-driven-capacity-v2.yaml").write_text(
            yaml.dump(manifest_data, default_flow_style=False)
        )

        # Commit the new state so the factory tree is clean.
        subprocess.run(["git", "add", "-A"], cwd=str(factory), capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add release manifest"],
            cwd=str(factory), capture_output=True,
        )

        dist = _init_dist_repo(tmp_path)
        return factory, dist

    def test_dry_run_returns_zero(self, tmp_path, monkeypatch):
        factory, dist = self._make_factory_with_release_manifest(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_publish
        args = SimpleNamespace(
            dry_run=True,
            force=False,
            no_push=True,
            dist_repo=str(dist),
        )
        rc = cmd_publish(args)
        assert rc == 0, f"cmd_publish returned {rc}"

    def test_dry_run_reports_would_build(self, tmp_path, monkeypatch, capsys):
        factory, dist = self._make_factory_with_release_manifest(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_publish
        args = SimpleNamespace(
            dry_run=True,
            force=False,
            no_push=True,
            dist_repo=str(dist),
        )
        cmd_publish(args)

        captured = capsys.readouterr()
        out = captured.out
        # Should mention the release name in the output.
        assert "demand-driven-capacity-v2" in out, (
            f"release name not in dry-run output:\n{out}"
        )
        assert "[DRY RUN]" in out, f"DRY RUN tag not in output:\n{out}"

    def test_dry_run_no_files_written(self, tmp_path, monkeypatch):
        factory, dist = self._make_factory_with_release_manifest(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_publish
        args = SimpleNamespace(
            dry_run=True,
            force=False,
            no_push=True,
            dist_repo=str(dist),
        )
        cmd_publish(args)

        # No zip files should appear in dist repo.
        zips = list(dist.rglob("*.zip"))
        assert zips == [], f"dry_run should not write files, found: {zips}"

    def test_dry_run_no_commit(self, tmp_path, monkeypatch):
        factory, dist = self._make_factory_with_release_manifest(tmp_path)
        monkeypatch.chdir(factory)

        r_before = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True,
        )
        count_before = int(r_before.stdout.strip())

        from vcfops_packaging.cli import cmd_publish
        args = SimpleNamespace(
            dry_run=True,
            force=False,
            no_push=True,
            dist_repo=str(dist),
        )
        cmd_publish(args)

        r_after = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True,
        )
        count_after = int(r_after.stdout.strip())
        assert count_after == count_before, (
            f"dry_run should not commit; count changed {count_before} -> {count_after}"
        )

    def test_unsupported_type_errors(self, tmp_path, monkeypatch):
        """Passing 'symptom' or 'alert' as type returns non-zero."""
        factory = _make_factory_copy(tmp_path)
        monkeypatch.chdir(factory)

        from vcfops_packaging.cli import cmd_release
        for bad_type in ("symptom", "symptoms", "alert", "alerts"):
            args = _build_release_args(content_type=bad_type, name="some_name")
            rc = cmd_release(args)
            assert rc != 0, f"expected non-zero for unsupported type {bad_type!r}"
