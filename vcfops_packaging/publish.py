"""Publish orchestrator for vcfops_packaging (Phase 3).

Orchestrates a full publish operation from the factory repo to the
distribution repo:

  1. Lockfile guard — refuse concurrent publishes.
  2. Validate factory repo — seven per-package validators + vcfops_packaging.
  3. Clean-tree check on dist repo — refuse if dirty / not on main / behind origin.
  4. Enumerate release manifests from releases/.
  5. Per-release build + idempotence routing — build, skip, or fail on conflict.
  6. Process retirements — move deprecated zips to retired/<subdir>/.
  7. Stale-zip sweep — move orphaned zips to retired/<subdir>/.
  8. Regenerate README between AUTO markers.
  9. Commit + push (skip on dry_run; commit-only on no_push).
  10. Cleanup — staging dir + lockfile.

Public API
----------
publish(factory_repo, dist_repo, dry_run, force, no_push) -> PublishResult

dry_run=True:
  - Skips clean-tree git checks on dist repo.
  - Skips actual file copy/move.
  - Skips commit/push.
  - Lockfile is still acquired to prevent races with real runs.
  - Returns a populated PublishResult showing what WOULD happen.
"""
from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Validator modules + arguments.  Each entry is (module_arg, extra_args).
# We invoke them as  python3 -m <module> <extra_args...>
# ---------------------------------------------------------------------------
_VALIDATORS = [
    ("vcfops_supermetrics", ["validate"]),
    ("vcfops_dashboards",   ["validate"]),
    ("vcfops_customgroups", ["validate"]),
    ("vcfops_symptoms",     ["validate"]),
    ("vcfops_alerts",       ["validate"]),
    ("vcfops_reports",      ["validate"]),
    ("vcfops_managementpacks", ["validate"]),
    ("vcfops_packaging",    ["validate"]),
]


class PublishError(RuntimeError):
    """Hard-stop error in the publish pipeline."""


@dataclass
class PublishResult:
    built: List[Path] = field(default_factory=list)      # zips newly built and copied
    skipped: List[Path] = field(default_factory=list)    # zips already present at expected name+version
    retired: List[Path] = field(default_factory=list)    # zips moved to retired/
    readme_path: Path = None                             # path to the regenerated README
    commit_sha: Optional[str] = None                     # None on dry-run
    pushed: bool = False


# ---------------------------------------------------------------------------
# Lockfile helpers
# ---------------------------------------------------------------------------

def _lockfile_path(dist_repo: Path) -> Path:
    return dist_repo / ".publish.lock"


def _acquire_lock(dist_repo: Path) -> None:
    lock = _lockfile_path(dist_repo)
    if lock.exists():
        contents = ""
        try:
            contents = lock.read_text().strip()
        except Exception:
            pass
        raise PublishError(
            f"Publish lockfile exists: {lock}\n"
            f"  Contents: {contents or '(unreadable)'}\n"
            f"  Another publish is running (or a previous run crashed).\n"
            f"  Remove the lockfile manually if you are sure no other publish is active."
        )
    lock.write_text(
        f"pid={os.getpid()} started={datetime.datetime.utcnow().isoformat()}Z\n"
    )


def _release_lock(dist_repo: Path) -> None:
    lock = _lockfile_path(dist_repo)
    try:
        lock.unlink(missing_ok=True)
    except Exception:
        pass  # Best-effort cleanup; don't mask the real error.


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _run_validators(factory_repo: Path) -> None:
    """Run all eight validators (seven per-package plus vcfops_packaging).

    Raises PublishError on any non-zero exit.
    """
    python = "python3"
    for module, extra_args in _VALIDATORS:
        cmd = [python, "-m", module] + extra_args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(factory_repo),
            check=False,
        )
        if result.returncode == 0:
            continue
        raise PublishError(
            f"Validator failed: python3 -m {module} {' '.join(extra_args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Git helpers (dist repo)
# ---------------------------------------------------------------------------

def _git(dist_repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        cwd=str(dist_repo),
        check=False,
    )


def _assert_clean_dist_repo(dist_repo: Path) -> None:
    """Raise PublishError if the dist repo has uncommitted changes, is not on
    main, or is behind origin/main."""

    # Must be on main.
    r = _git(dist_repo, "rev-parse", "--abbrev-ref", "HEAD")
    if r.returncode != 0:
        raise PublishError(
            f"Could not determine current branch in dist repo {dist_repo}: "
            f"{r.stderr.strip()}"
        )
    branch = r.stdout.strip()
    if branch != "main":
        raise PublishError(
            f"Dist repo {dist_repo} is on branch {branch!r}, not 'main'. "
            f"Switch to main before publishing."
        )

    # Working tree must be clean (ignore the publish lockfile itself — it is
    # a transient in-flight marker written by _acquire_lock before this check).
    r = _git(dist_repo, "status", "--porcelain")
    if r.returncode != 0:
        raise PublishError(
            f"Could not check git status in dist repo {dist_repo}: "
            f"{r.stderr.strip()}"
        )
    dirty_lines = [
        ln for ln in r.stdout.splitlines()
        if ln and not ln.endswith(".publish.lock")
    ]
    if dirty_lines:
        raise PublishError(
            f"Dist repo {dist_repo} has uncommitted changes:\n"
            f"{chr(10).join(dirty_lines)}\n"
            f"Commit or stash them before publishing."
        )

    # Not behind origin/main.  Fetch first (best-effort — no-op if offline).
    _git(dist_repo, "fetch", "origin", "main")
    r = _git(dist_repo, "rev-list", "--count", "HEAD..origin/main")
    if r.returncode == 0:
        try:
            behind = int(r.stdout.strip())
        except ValueError:
            behind = 0
        if behind > 0:
            raise PublishError(
                f"Dist repo {dist_repo} is {behind} commit(s) behind origin/main. "
                f"Run 'git pull' before publishing."
            )


def _git_commit(dist_repo: Path, message: str) -> Optional[str]:
    """Stage all changes, commit, and return the new commit SHA.

    Returns None if there was nothing to commit.
    """
    # Stage everything except the publish lockfile.  The lockfile is a
    # transient runtime guard that is removed before this call in the normal
    # path, but may still be on disk if an earlier step failed and the caller
    # is in the finally branch.  Explicitly excluding it here is belt-and-
    # suspenders: even if it is present, it will never land in the commit.
    r = _git(dist_repo, "add", "-A", "--", ":!.publish.lock")
    if r.returncode != 0:
        raise PublishError(
            f"git add failed in {dist_repo}: {r.stderr.strip()}"
        )

    r = _git(dist_repo, "commit", "-m", message)
    if r.returncode != 0:
        # "nothing to commit" is not a failure.
        if "nothing to commit" in r.stdout + r.stderr:
            return None
        raise PublishError(
            f"git commit failed in {dist_repo}: {r.stdout.strip()} {r.stderr.strip()}"
        )

    # Return the new HEAD SHA.
    r = _git(dist_repo, "rev-parse", "HEAD")
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def _git_push(dist_repo: Path) -> None:
    r = _git(dist_repo, "push", "origin", "main")
    if r.returncode != 0:
        raise PublishError(
            f"git push failed in {dist_repo}: {r.stderr.strip()}"
        )


# ---------------------------------------------------------------------------
# Release enumeration
# ---------------------------------------------------------------------------

def _enumerate_releases(factory_repo: Path):
    """Load all release manifests from releases/.

    Returns a list of ReleaseDef objects sorted by manifest filename.
    """
    from .releases import load_all_releases

    releases_dir = factory_repo / "releases"
    if not releases_dir.exists():
        return []

    return load_all_releases(releases_dir, repo_root=factory_repo)


# ---------------------------------------------------------------------------
# Subdirectory helpers
# ---------------------------------------------------------------------------

def _all_known_subdirs() -> List[str]:
    """Return the complete list of top-level subdirs we manage in the dist repo."""
    return [
        "bundles",
        "dashboards",
        "views",
        "supermetrics",
        "customgroups",
        "reports",
        "management-packs",
    ]


def _all_headline_paths(releases) -> set[str]:
    """Return the set of expected zip filenames across all release headlines.

    Each element is in the form  "<subdir>/<name>-<version>.zip",
    e.g. "dashboards/demand-driven-capacity-v2-1.0.zip".
    """
    from .release_builder import _artifact_dest_subdir, _zip_filename
    known = set()
    for r in releases:
        for a in r.artifacts:
            if a.headline:
                subdir = _artifact_dest_subdir(a)
                filename = _zip_filename(r.name, r.version)
                known.add(f"{subdir}/{filename}")
    return known


# ---------------------------------------------------------------------------
# Per-release build
# ---------------------------------------------------------------------------

def _build_one_release(release, staging_dir: Path, factory_repo: Path):
    """Build one release into staging_dir.

    Returns a list of (zip_path_in_staging, dest_subdir, zip_filename) triples.
    Raises PublishError on build failure.
    """
    from .release_builder import build_release, ReleaseArtifact

    try:
        artifacts = build_release(
            release_path=release.manifest_path,
            output_dir=staging_dir,
            skip_audit=True,
        )
    except Exception as exc:
        raise PublishError(
            f"Build failed for release {release.name!r}: {exc}"
        ) from exc

    return artifacts


# ---------------------------------------------------------------------------
# Stale-zip sweep
# ---------------------------------------------------------------------------

def _sweep_stale_zips(
    dist_repo: Path,
    known_filenames: set[str],
    dry_run: bool,
) -> List[Path]:
    """Move zips with no corresponding release manifest to retired/<subdir>/.

    Args:
        dist_repo:       Root of the distribution repo.
        known_filenames: Set of "<subdir>/<zipname>" for all current releases.
        dry_run:         If True, compute but don't move.

    Returns:
        List of paths that were (or would be) moved to retired/.
    """
    retired: List[Path] = []
    for subdir in _all_known_subdirs():
        subdir_path = dist_repo / subdir
        if not subdir_path.exists():
            continue
        for zip_path in sorted(subdir_path.glob("*.zip")):
            key = f"{subdir}/{zip_path.name}"
            if key not in known_filenames:
                retired_dir = dist_repo / "retired" / subdir
                if not dry_run:
                    retired_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(zip_path), str(retired_dir / zip_path.name))
                retired.append(dist_repo / "retired" / subdir / zip_path.name)
    return retired


# ---------------------------------------------------------------------------
# Retirement handler
# ---------------------------------------------------------------------------

def _process_retirements(releases, dist_repo: Path, dry_run: bool) -> List[Path]:
    """For each release manifest that has a deprecates: list, locate the
    deprecated release's zip(s) and move them to retired/<subdir>/.

    The deprecated entries are file paths to other release manifests; we load
    them to learn their name + version, then compute the expected zip path.

    Returns list of paths that were (or would be) moved.
    """
    from .release_builder import _artifact_dest_subdir, _zip_filename
    from .releases import load_release

    retired: List[Path] = []
    already_handled: set[str] = set()

    for release in releases:
        if not release.deprecates:
            continue
        for dep_manifest_path in release.deprecates:
            try:
                dep_release = load_release(dep_manifest_path)
            except Exception:
                continue
            for a in dep_release.artifacts:
                if not a.headline:
                    continue
                subdir = _artifact_dest_subdir(a)
                filename = _zip_filename(dep_release.name, dep_release.version)
                src = dist_repo / subdir / filename
                key = f"{subdir}/{filename}"
                if key in already_handled:
                    continue
                already_handled.add(key)
                if src.exists():
                    retired_dir = dist_repo / "retired" / subdir
                    dest = retired_dir / filename
                    if not dry_run:
                        retired_dir.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src), str(dest))
                    retired.append(dest)

    return retired


# ---------------------------------------------------------------------------
# README update
# ---------------------------------------------------------------------------

_README_PHASE3_TEMPLATE = """\
<!-- AUTO:START release-catalog -->
<!-- AUTO:END -->
"""


def _check_readme_markers(readme_path: Path) -> bool:
    """Return True if the README has at least one AUTO:START marker."""
    if not readme_path.exists():
        return False
    content = readme_path.read_text(encoding="utf-8")
    return "<!-- AUTO:START" in content


def _update_dist_readme(
    dist_repo: Path,
    factory_repo: Path,
    releases,
    dry_run: bool,
) -> Path:
    """Regenerate the dist repo README between AUTO markers.

    Uses the extended readme_gen.update_readme_release() function which
    renders per-subdir tables from the release manifests rather than from
    the factory repo content flags.

    If the README has no AUTO markers, raises a structured warning but
    does NOT fail the publish (the README is just left unchanged).

    Returns the path to the README.
    """
    readme = dist_repo / "README.md"
    if not readme.exists():
        # Nothing to update.
        return readme

    has_markers = _check_readme_markers(readme)
    if not has_markers:
        # TOOLSET GAP — document but don't fail.
        print(
            "WARN  README has no AUTO markers — skipping regeneration.\n"
            "      To enable auto-generation, add markers to the README:\n"
            "        <!-- AUTO:START release-catalog -->\n"
            "        <!-- AUTO:END -->"
        )
        return readme

    if not dry_run:
        from .readme_gen import update_readme_release
        update_readme_release(readme, dist_repo=dist_repo, releases=releases)

    return readme


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def publish(
    factory_repo: Path,
    dist_repo: Path,
    dry_run: bool = False,
    force: bool = False,
    no_push: bool = False,
) -> PublishResult:
    """Orchestrate a full publish operation.

    Args:
        factory_repo: Absolute path to the factory repo root.
        dist_repo:    Absolute path to the distribution repo root.
        dry_run:      If True, compute what would happen without writing files
                      or committing.  Lockfile is still acquired.
        force:        If True, overwrite an existing zip at the same name but
                      different version instead of failing.
        no_push:      If True, commit the dist repo but do not push to origin.

    Returns:
        PublishResult with built/skipped/retired/readme_path/commit_sha/pushed.

    Raises:
        PublishError: on any hard failure (lock busy, validator fail, git dirty,
                      version conflict without force, build error).
    """
    factory_repo = Path(factory_repo).resolve()
    dist_repo = Path(dist_repo).resolve()

    result = PublishResult()

    # -----------------------------------------------------------------------
    # Step 1: Lockfile guard
    # -----------------------------------------------------------------------
    _acquire_lock(dist_repo)

    try:
        _publish_inner(
            factory_repo=factory_repo,
            dist_repo=dist_repo,
            dry_run=dry_run,
            force=force,
            no_push=no_push,
            result=result,
        )
    finally:
        _release_lock(dist_repo)

    return result


def _publish_inner(
    factory_repo: Path,
    dist_repo: Path,
    dry_run: bool,
    force: bool,
    no_push: bool,
    result: PublishResult,
) -> None:
    """Inner body of publish() — runs inside the lockfile try/finally."""
    import zipfile

    # -----------------------------------------------------------------------
    # Step 2: Validate factory repo
    # -----------------------------------------------------------------------
    _run_validators(factory_repo)

    # -----------------------------------------------------------------------
    # Step 3: Clean-tree check on dist repo
    # -----------------------------------------------------------------------
    if not dry_run:
        _assert_clean_dist_repo(dist_repo)

    # -----------------------------------------------------------------------
    # Step 4: Enumerate release manifests
    # -----------------------------------------------------------------------
    releases = _enumerate_releases(factory_repo)

    # Build the set of all expected zip filenames for idempotence and stale sweep.
    known_filenames = _all_headline_paths(releases)

    # -----------------------------------------------------------------------
    # Step 5: Per-release build + idempotence routing
    # -----------------------------------------------------------------------
    built_names: List[str] = []  # release names for commit message

    with tempfile.TemporaryDirectory(prefix="vcfops_publish_staging_") as staging_str:
        staging = Path(staging_str)

        for release in releases:
            from .release_builder import (
                artifact_already_exists,
                expected_artifact_path,
                _artifact_dest_subdir,
                _zip_filename,
            )

            # Compute expected destination path (first headline only for single-headline
            # releases; multi-headline releases iterate artifacts below).
            for manifest_artifact in release.artifacts:
                if not manifest_artifact.headline:
                    continue

                from .release_builder import _artifact_dest_subdir as _ads
                from .release_builder import _zip_filename as _zfn
                subdir = _ads(manifest_artifact)
                filename = _zfn(release.name, release.version)
                dest_path = dist_repo / subdir / filename

                if dest_path.exists():
                    # Exact match — skip (idempotent).
                    result.skipped.append(dest_path)
                    continue

                # Check for same-name different-version conflict.
                # A conflict = a zip with the same release name but ANY version in the subdir.
                import re as _re
                name_prefix = release.name + "-"
                conflicts = [
                    p for p in (dist_repo / subdir).glob("*.zip")
                    if p.name.startswith(name_prefix)
                ]
                if conflicts and not force:
                    raise PublishError(
                        f"Version conflict for release {release.name!r}: "
                        f"existing zip(s) {[c.name for c in conflicts]!r} in "
                        f"{subdir}/ but release manifest declares version "
                        f"{release.version!r}.  Use force=True to overwrite."
                    )

                # Build this release into staging.
                if not dry_run:
                    artifacts = _build_one_release(release, staging, factory_repo)

                    for art in artifacts:
                        dest_dir = dist_repo / art.dest_subdir
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest_file = dest_dir / art.zip_path.name
                        shutil.copy2(str(art.zip_path), str(dest_file))
                        result.built.append(dest_file)
                        built_names.append(release.name)
                else:
                    # Dry-run: record the would-be path.
                    result.built.append(dest_path)
                    built_names.append(release.name)

                # Only build each release once even if it has multiple headlines;
                # break after first headline to avoid duplicate builds.
                # (build_release internally processes all headlines in one call.)
                break

    # -----------------------------------------------------------------------
    # Step 6: Process retirements
    # -----------------------------------------------------------------------
    retired_from_deprecates = _process_retirements(releases, dist_repo, dry_run)
    result.retired.extend(retired_from_deprecates)

    # Remove deprecations from known_filenames so stale sweep doesn't re-retire.
    # (Files just moved to retired/ are no longer in the top-level subdirs.)

    # -----------------------------------------------------------------------
    # Step 7: Stale-zip sweep
    # -----------------------------------------------------------------------
    retired_from_sweep = _sweep_stale_zips(dist_repo, known_filenames, dry_run)
    result.retired.extend(retired_from_sweep)

    # -----------------------------------------------------------------------
    # Step 8: Regenerate README
    # -----------------------------------------------------------------------
    result.readme_path = _update_dist_readme(dist_repo, factory_repo, releases, dry_run)

    # -----------------------------------------------------------------------
    # Step 9: Commit + push
    # -----------------------------------------------------------------------
    if not dry_run:
        # Release the lockfile BEFORE staging so it is never included in the
        # commit.  The outer try/finally in publish() calls _release_lock again
        # after this returns, but _release_lock is idempotent (missing_ok=True),
        # so double-removal is safe.  The finally branch also covers any
        # exception thrown below (e.g. a failed push) — the lock is already
        # gone by that point, which is the correct behaviour (the content was
        # fully written; only the push failed).
        _release_lock(dist_repo)

        n_built = len(result.built)
        n_retired = len(result.retired)
        release_names_str = (
            ", ".join(sorted(set(built_names))) if built_names else "none"
        )
        commit_msg = (
            f"release-publish: {n_built} built, {n_retired} retired "
            f"({release_names_str})"
        )
        sha = _git_commit(dist_repo, commit_msg)
        result.commit_sha = sha

        if sha and not no_push:
            _git_push(dist_repo)
            result.pushed = True

    return
