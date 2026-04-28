"""v4 publish — PR mode tests.

Covers:

  T01 — Default mode (use_pr=True) creates a release branch, pushes it,
         and calls ``gh pr create`` with the correct title/body shape.
  T02 — --push (use_pr=False) does a direct push to main (regression guard).
  T03 — --dry-run builds in temp dir, no branch, no PR, no push.
  T04 — --no-push (use_pr=True, no_push=True) commits release branch
         locally but does not push and does not open a PR.
  T05 — --auto-merge triggers ``gh pr merge --auto --merge`` after PR creation.
  T06 — --pr --push (use_pr=True + auto_merge=True + push_direct) errors as
         mutually exclusive.
  T07 — gh absent → instructions printed, exit zero, branch left for user.
  T08 — Existing release branch → fail with clear message.
  T09 — Lockfile: acquired before build, released after PR open (not merge).
  T10 — Branch naming: batched publishes use ``release/<date>-<n>`` form.
"""
from __future__ import annotations

import datetime
import subprocess
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch, call

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_publish_phase3.py helpers)
# ---------------------------------------------------------------------------

def _init_dist_repo(tmp_path: Path, *, with_auto_markers: bool = True) -> Path:
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
    if with_auto_markers:
        readme_body = (
            "# VCF Content Factory Bundles\n\n"
            "Human-authored intro.\n\n"
            "<!-- AUTO:START release-catalog -->\n"
            "<!-- AUTO:END -->\n\n"
            "Human-authored footer.\n"
        )
    else:
        readme_body = "# VCF Content Factory Bundles\n\nNo AUTO markers.\n"
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
    release_notes: str = "",
) -> Path:
    manifest = {
        "name": name,
        "version": version,
        "description": description,
        "release_notes": release_notes,
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
            if p.name == "_phase1_selftest.yaml":
                continue
            rel = load_release(p, repo_root=factory_repo)
            if rel.name in seen:
                raise ValueError(f"duplicate: {rel.name}")
            seen[rel.name] = p
            releases.append(rel)
        return releases

    monkeypatch.setattr(_pub, "_enumerate_releases", _fake_enumerate)


def _source_abs() -> Path:
    return (
        REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml"
    ).resolve()


# ---------------------------------------------------------------------------
# T01 — PR mode (default): branch created, pushed, gh pr create invoked
# ---------------------------------------------------------------------------

class TestPRModeDefault:
    """T01: use_pr=True opens a PR via gh."""

    def _setup(self, tmp_path, monkeypatch, release_notes=""):
        from vcfops_packaging import publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
            description="PR mode test.",
            release_notes=release_notes,
        )
        _patch_enumerate(monkeypatch, releases_dir)
        return dist, releases_dir

    def test_pr_mode_opens_pr(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist, _ = self._setup(tmp_path, monkeypatch, release_notes="Initial ship.")

        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                if "pr" in cmd and "create" in cmd:
                    return MagicMock(
                        returncode=0,
                        stdout="https://github.com/org/repo/pull/42\n",
                        stderr="",
                    )
                return MagicMock(returncode=0, stdout="", stderr="")
            # Intercept git push to origin (no remote in temp repo).
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)
        monkeypatch.setattr(_pub, "_detect_gh", lambda: True)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            use_pr=True,
        )

        assert result.pr_url == "https://github.com/org/repo/pull/42", (
            f"Expected PR URL, got {result.pr_url!r}"
        )
        assert result.pushed is True
        assert result.release_branch is not None
        assert result.release_branch.startswith("release/")

    def test_pr_title_shape(self, tmp_path, monkeypatch):
        """PR title must match 'release: <names> (N built, M retired)' pattern."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist, _ = self._setup(tmp_path, monkeypatch)

        captured_titles = []
        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                if "pr" in cmd and "create" in cmd:
                    # --title comes after --title flag
                    idx = cmd.index("--title")
                    captured_titles.append(cmd[idx + 1])
                return MagicMock(
                    returncode=0,
                    stdout="https://github.com/org/repo/pull/1\n",
                    stderr="",
                )
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)
        monkeypatch.setattr(_pub, "_detect_gh", lambda: True)

        publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, use_pr=True)

        assert len(captured_titles) == 1, f"Expected one gh pr create, got: {captured_titles}"
        title = captured_titles[0]
        assert title.startswith("release: "), f"Title does not start with 'release: ': {title!r}"
        assert "built" in title, f"Title missing 'built' count: {title!r}"

    def test_pr_body_contains_release_notes(self, tmp_path, monkeypatch):
        """PR body must include the release_notes field from the manifest."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist, _ = self._setup(
            tmp_path, monkeypatch, release_notes="This release includes capacity planning improvements."
        )

        captured_bodies = []
        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                if "pr" in cmd and "create" in cmd:
                    idx = cmd.index("--body")
                    captured_bodies.append(cmd[idx + 1])
                return MagicMock(
                    returncode=0,
                    stdout="https://github.com/org/repo/pull/2\n",
                    stderr="",
                )
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)
        monkeypatch.setattr(_pub, "_detect_gh", lambda: True)

        publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, use_pr=True)

        assert captured_bodies, "No PR body captured"
        body = captured_bodies[0]
        assert "capacity planning improvements" in body, (
            f"Release notes not in PR body. Body:\n{body[:800]}"
        )

    def test_pr_mode_branch_pushed(self, tmp_path, monkeypatch):
        """The release branch must be pushed to origin before the PR is opened."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist, _ = self._setup(tmp_path, monkeypatch)

        pushed_branches = []
        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                if len(cmd) >= 3 and cmd[1] == "push" and cmd[2] == "origin":
                    branch = cmd[3] if len(cmd) > 3 else ""
                    pushed_branches.append(branch)
                    return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                return MagicMock(
                    returncode=0,
                    stdout="https://github.com/org/repo/pull/3\n",
                    stderr="",
                )
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)
        monkeypatch.setattr(_pub, "_detect_gh", lambda: True)

        result = publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, use_pr=True)

        release_pushes = [b for b in pushed_branches if b.startswith("release/")]
        assert release_pushes, (
            f"No release branch was pushed. pushed_branches={pushed_branches}"
        )


# ---------------------------------------------------------------------------
# T02 — --push: direct push to main (regression guard)
# ---------------------------------------------------------------------------

class TestPushModeDirectPush:
    """T02: use_pr=False (--push) does a direct push to main."""

    def test_push_mode_pushes_to_main(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        # Add a fake remote "origin" so git push doesn't fail.
        import vcfops_packaging.publish as _pub

        pushed_refs = []
        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                pushed_refs.append(list(cmd))
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            use_pr=False,
        )

        # Should have pushed to origin main (or at least pushed).
        push_calls = [c for c in pushed_refs if "origin" in c and "main" in c]
        assert push_calls, (
            f"Expected a push to origin main. pushed_refs={pushed_refs}"
        )
        assert result.pushed is True
        assert result.pr_url is None
        assert result.release_branch is None

    def test_push_mode_no_pr_created(self, tmp_path, monkeypatch):
        """--push must never call gh pr create."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases2"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        gh_called = []
        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                gh_called.append(cmd)
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, use_pr=False)

        pr_create_calls = [c for c in gh_called if "pr" in c and "create" in c]
        assert not pr_create_calls, (
            f"--push mode must not call gh pr create. gh calls: {gh_called}"
        )


# ---------------------------------------------------------------------------
# T03 — --dry-run: no branch, no PR, no push
# ---------------------------------------------------------------------------

class TestDryRunNoBranchNoPR:
    """T03: dry_run=True builds in temp dir — no commit, no branch, no PR."""

    def test_dry_run_no_branch_created(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        gh_called = []
        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                gh_called.append(cmd)
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=True,
            use_pr=True,
        )

        assert result.commit_sha is None
        assert result.pushed is False
        assert result.pr_url is None
        assert result.release_branch is None
        assert not gh_called, f"dry_run should not invoke gh: {gh_called}"

        # No branch created.
        r = subprocess.run(
            ["git", "branch", "-a"],
            cwd=str(dist), capture_output=True, text=True,
        )
        branch_list = r.stdout
        assert "release/" not in branch_list, (
            f"Release branch found in dry-run. branches:\n{branch_list}"
        )

    def test_dry_run_no_files_on_disk(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases2"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=True, use_pr=True)

        dashboards_dir = dist / "dashboards"
        if dashboards_dir.exists():
            zips = list(dashboards_dir.glob("*.zip"))
            assert zips == [], f"dry_run must not copy files, found: {zips}"


# ---------------------------------------------------------------------------
# T04 — --no-push: commit branch locally, no push, no PR
# ---------------------------------------------------------------------------

class TestNoPushMode:
    """T04: use_pr=True + no_push=True commits locally but never pushes or opens PR."""

    def test_no_push_branch_committed_locally(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        gh_called = []
        original_run = subprocess.run
        pushed = []

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                gh_called.append(cmd)
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                pushed.append(cmd)
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
            use_pr=True,
        )

        # No push, no PR.
        assert result.pushed is False
        assert result.pr_url is None
        assert not gh_called, f"--no-push must not call gh: {gh_called}"
        assert not any("origin" in " ".join(c) and "release/" in " ".join(c) for c in pushed), (
            f"--no-push must not push release branch to origin: {pushed}"
        )

        # Branch was created locally.
        assert result.release_branch is not None
        r = subprocess.run(
            ["git", "branch", "--list", result.release_branch],
            cwd=str(dist), capture_output=True, text=True,
        )
        assert result.release_branch in r.stdout, (
            f"Release branch '{result.release_branch}' not found locally.\n"
            f"git branch output: {r.stdout}"
        )

    def test_no_push_commit_sha_populated(self, tmp_path, monkeypatch):
        """commit_sha must be set (commit happened on the local branch)."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases2"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
            use_pr=True,
        )

        assert result.commit_sha is not None, (
            "--no-push (PR mode) should still produce a commit on the local branch"
        )


# ---------------------------------------------------------------------------
# T05 — --auto-merge: gh pr merge called after PR open
# ---------------------------------------------------------------------------

class TestAutoMerge:
    """T05: auto_merge=True triggers gh pr merge after PR creation."""

    def test_auto_merge_calls_gh_merge(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        gh_calls = []
        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                gh_calls.append(list(cmd))
                if "pr" in cmd and "create" in cmd:
                    return MagicMock(
                        returncode=0,
                        stdout="https://github.com/org/repo/pull/99\n",
                        stderr="",
                    )
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)
        monkeypatch.setattr(_pub, "_detect_gh", lambda: True)

        publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            use_pr=True,
            auto_merge=True,
        )

        merge_calls = [c for c in gh_calls if "pr" in c and "merge" in c]
        assert merge_calls, f"Expected gh pr merge call. gh_calls: {gh_calls}"
        assert "--auto" in merge_calls[0], f"--auto flag missing: {merge_calls[0]}"
        assert "--merge" in merge_calls[0], f"--merge flag missing: {merge_calls[0]}"

    def test_auto_merge_order_after_pr_create(self, tmp_path, monkeypatch):
        """gh pr merge must be called AFTER gh pr create, not before."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases2"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        gh_calls_ordered = []
        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                gh_calls_ordered.append(tuple(cmd))
                if "pr" in cmd and "create" in cmd:
                    return MagicMock(
                        returncode=0,
                        stdout="https://github.com/org/repo/pull/88\n",
                        stderr="",
                    )
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)
        monkeypatch.setattr(_pub, "_detect_gh", lambda: True)

        publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            use_pr=True,
            auto_merge=True,
        )

        call_types = []
        for c in gh_calls_ordered:
            if "create" in c:
                call_types.append("create")
            elif "merge" in c:
                call_types.append("merge")

        assert call_types == ["create", "merge"], (
            f"Expected [create, merge] order, got {call_types}"
        )


# ---------------------------------------------------------------------------
# T06 — Mutually exclusive flags
# ---------------------------------------------------------------------------

class TestMutuallyExclusiveFlags:
    """T06: use_pr=True + auto_merge=True + push (direct) errors."""

    def test_auto_merge_with_push_mode_raises(self):
        """auto_merge=True with use_pr=False must raise PublishError."""
        from vcfops_packaging.publish import publish, PublishError

        with pytest.raises(PublishError, match="auto-merge"):
            publish(
                factory_repo=REPO_ROOT,
                dist_repo=Path("/tmp/nonexistent-dist"),
                dry_run=True,
                use_pr=False,
                auto_merge=True,
            )


# ---------------------------------------------------------------------------
# T07 — gh absent: print instructions, exit 0, branch left for user
# ---------------------------------------------------------------------------

class TestGhAbsent:
    """T07: gh not found → manual instructions printed, result.pr_url=None."""

    def test_gh_absent_no_error(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        # gh is absent.
        monkeypatch.setattr(_pub, "_detect_gh", lambda: False)

        # git push to origin would fail (no remote); intercept it.
        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        # Must not raise.
        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            use_pr=True,
        )

        assert result.pr_url is None, (
            f"pr_url should be None when gh is absent, got {result.pr_url!r}"
        )
        assert result.pushed is True  # branch was still pushed

        # Instructions must be printed.
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "gh" in output.lower() or "manually" in output.lower() or "instructions" in output.lower(), (
            f"Expected manual instructions in output. Got:\n{output}"
        )

    def test_gh_absent_branch_info_in_output(self, tmp_path, monkeypatch, capsys):
        """Manual instructions must include the branch name."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases2"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        monkeypatch.setattr(_pub, "_detect_gh", lambda: False)

        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            use_pr=True,
        )

        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert result.release_branch is not None
        assert result.release_branch in output, (
            f"Branch name '{result.release_branch}' not in instructions output.\n"
            f"Output:\n{output}"
        )


# ---------------------------------------------------------------------------
# T08 — Existing release branch → clear failure message
# ---------------------------------------------------------------------------

class TestExistingReleaseBranch:
    """T08: if the release branch's remote push is rejected, fail with a clear message.

    In the auto-increment naming scheme, local branch conflicts are avoided by
    design (n increments past any existing branch). The idempotence guard fires
    when the remote push is rejected — signalling a PR is already open for that
    branch. We simulate this by making git push return a rejected error.
    """

    def test_push_rejected_fails_with_clear_message(self, tmp_path, monkeypatch):
        from vcfops_packaging.publish import publish, PublishError
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"] and "origin" in cmd:
                # Simulate a push rejection (branch already exists on remote).
                return MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="error: failed to push some refs\n"
                           "hint: Updates were rejected because the remote contains work that you do not have locally.",
                )
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        with pytest.raises(PublishError) as exc_info:
            publish(
                factory_repo=REPO_ROOT,
                dist_repo=dist,
                dry_run=False,
                use_pr=True,
            )

        msg = str(exc_info.value)
        assert "release/" in msg or "already exists" in msg.lower() or "push" in msg.lower(), (
            f"Error message should mention the branch name or 'already exists' or 'push'.\n"
            f"Message: {msg}"
        )

    def test_local_branch_already_exists_fails(self, tmp_path, monkeypatch):
        """If _next_release_branch_name cannot find an unused branch, git checkout -b fails."""
        from vcfops_packaging.publish import publish, PublishError
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases2"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")

        # Override _next_release_branch_name to return a branch that already exists.
        monkeypatch.setattr(
            _pub,
            "_next_release_branch_name",
            lambda dist_repo: f"release/{today}-1",
        )

        # Pre-create that exact branch locally.
        existing_branch = f"release/{today}-1"
        subprocess.run(
            ["git", "checkout", "-b", existing_branch],
            cwd=str(dist), capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=str(dist), capture_output=True, check=True,
        )

        with pytest.raises(PublishError) as exc_info:
            publish(
                factory_repo=REPO_ROOT,
                dist_repo=dist,
                dry_run=False,
                use_pr=True,
            )

        msg = str(exc_info.value)
        assert existing_branch in msg or "already exists" in msg.lower() or "create" in msg.lower(), (
            f"Error message should mention the branch name or 'already exists'.\n"
            f"Message: {msg}"
        )


# ---------------------------------------------------------------------------
# T09 — Lockfile: acquired before build, released after PR open
# ---------------------------------------------------------------------------

class TestLockfileLifecyclePRMode:
    """T09: lockfile is acquired at start, released after PR open (not after merge)."""

    def test_lockfile_absent_after_pr_opened(self, tmp_path, monkeypatch):
        """After publish() returns, the lockfile must be gone."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        monkeypatch.setattr(_pub, "_detect_gh", lambda: True)

        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                if "pr" in cmd and "create" in cmd:
                    return MagicMock(
                        returncode=0,
                        stdout="https://github.com/org/repo/pull/7\n",
                        stderr="",
                    )
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, use_pr=True)

        lockfile = dist / ".publish.lock"
        assert not lockfile.exists(), (
            f"Lockfile must be released after PR opens. Still present: {lockfile}"
        )

    def test_lockfile_not_in_pr_branch_commit(self, tmp_path, monkeypatch):
        """The release branch commit must not include .publish.lock."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases2"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        monkeypatch.setattr(_pub, "_detect_gh", lambda: True)

        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                if "pr" in cmd and "create" in cmd:
                    return MagicMock(
                        returncode=0,
                        stdout="https://github.com/org/repo/pull/8\n",
                        stderr="",
                    )
                return MagicMock(returncode=0, stdout="", stderr="")
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        result = publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, use_pr=True)

        assert result.commit_sha is not None, "Expected a commit on the release branch"
        assert result.release_branch is not None

        # Inspect the release branch commit tree.
        r = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", result.release_branch],
            cwd=str(dist), capture_output=True, text=True, check=True,
        )
        tracked_files = r.stdout.splitlines()
        assert ".publish.lock" not in tracked_files, (
            f".publish.lock was committed to the release branch.\n"
            f"Tracked files: {tracked_files}"
        )


# ---------------------------------------------------------------------------
# T10 — Branch naming: batched publishes use release/<date>-<n>
# ---------------------------------------------------------------------------

class TestBranchNaming:
    """T10: branch names follow release/<YYYY-MM-DD>-<n> format."""

    def test_branch_name_format(self, tmp_path, monkeypatch):
        """Branch name must match release/<date>-<n> for a single publish."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        monkeypatch.setattr(_pub, "_detect_gh", lambda: True)

        original_run = subprocess.run

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                return MagicMock(
                    returncode=0,
                    stdout="https://github.com/org/repo/pull/10\n",
                    stderr="",
                )
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        result = publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, use_pr=True)

        import re
        assert result.release_branch is not None
        assert re.match(r"release/\d{4}-\d{2}-\d{2}-\d+", result.release_branch), (
            f"Branch name '{result.release_branch}' does not match 'release/<date>-<n>' pattern"
        )

    def test_second_publish_increments_n(self, tmp_path, monkeypatch):
        """A second publish on the same day uses -2 (or higher) suffix."""
        from vcfops_packaging.publish import publish
        import vcfops_packaging.publish as _pub

        dist = _init_dist_repo(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(
            releases_dir,
            name="demand-driven-capacity-v2",
            version="1.0",
            source_abs=_source_abs(),
        )
        _patch_enumerate(monkeypatch, releases_dir)

        monkeypatch.setattr(_pub, "_detect_gh", lambda: True)

        original_run = subprocess.run
        pr_counter = [0]

        def _fake_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                pr_counter[0] += 1
                return MagicMock(
                    returncode=0,
                    stdout=f"https://github.com/org/repo/pull/{pr_counter[0]}\n",
                    stderr="",
                )
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        result1 = publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, use_pr=True)
        result2 = publish(factory_repo=REPO_ROOT, dist_repo=dist, dry_run=False, use_pr=True)

        assert result1.release_branch != result2.release_branch, (
            f"Two sequential publishes must use different branch names. "
            f"Both got: {result1.release_branch!r}"
        )

        # Both must start with release/ and have a numeric suffix.
        import re
        for b in (result1.release_branch, result2.release_branch):
            assert re.match(r"release/\d{4}-\d{2}-\d{2}-\d+", b), (
                f"Branch name '{b}' does not match expected pattern"
            )

        # Suffix of second must be higher than first.
        def _suffix(b: str) -> int:
            return int(b.rsplit("-", 1)[-1])

        assert _suffix(result2.release_branch) > _suffix(result1.release_branch), (
            f"Second branch suffix should be higher: "
            f"{result1.release_branch!r} vs {result2.release_branch!r}"
        )

    def test_next_release_branch_name_skips_existing(self, tmp_path):
        """_next_release_branch_name skips branches that already exist locally."""
        from vcfops_packaging.publish import _next_release_branch_name

        dist = _init_dist_repo(tmp_path)
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")

        # Pre-create release/<today>-1 and release/<today>-2.
        for n in (1, 2):
            b = f"release/{today}-{n}"
            subprocess.run(
                ["git", "checkout", "-b", b],
                cwd=str(dist), capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=str(dist), capture_output=True, check=True,
            )

        name = _next_release_branch_name(dist)
        assert name == f"release/{today}-3", (
            f"Expected 'release/{today}-3', got {name!r}"
        )
