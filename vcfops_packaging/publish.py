"""Publish orchestrator for vcfops_packaging (Phase 3 / v4).

Orchestrates a full publish operation from the factory repo to the
distribution repo:

  1. Lockfile guard — refuse concurrent publishes.
  2. Validate factory repo — seven per-package validators + vcfops_packaging.
  3. Clean-tree check on dist repo — refuse if dirty / not on main / behind origin.
  4. Enumerate release manifests from releases/.
  5. Per-release build + copy — always build; git diff decides whether to commit.
  6. Legacy-zip sweep — delete in-place any ``<slug>-<X.Y>.zip`` that corresponds
     to a current release slug (the slug itself is now the canonical versionless
     artifact name).  Does NOT move to retired/ — these are versioned filenames
     from the pre-versionless era, not actually deprecated content.
  7. Process retirements — move deprecated zips to retired/<subdir>/.
  8. Stale-zip sweep — move other orphaned zips to retired/<subdir>/.
  9. Regenerate README between AUTO markers.
  10. Commit + branch/PR or direct push:
        - PR mode (default): create release branch, push, open PR via gh CLI.
          Lockfile released after PR is open.
        - Push mode (--push): direct push to main (legacy/owner-fast-path).
          Lockfile released before staging (existing behaviour).
        - no_push mode (--no-push): commit to release branch locally, no push,
          no PR.  Lockfile released after commit.
        - dry_run: no commit/push/PR; lockfile released at end.
  11. Cleanup — staging dir + lockfile.

Public API
----------
publish(factory_repo, dist_repo, dry_run, force, no_push, use_pr, auto_merge)
  -> PublishResult

dry_run=True:
  - Skips clean-tree git checks on dist repo.
  - Skips actual file copy/move.
  - Skips commit/push/PR.
  - Lockfile is still acquired to prevent races with real runs.
  - Returns a populated PublishResult showing what WOULD happen.

force=True:
  - Forces a commit even when no on-disk content changed (git reports nothing
    to commit).  Useful for debugging or re-pushing identical content.

use_pr=True (default):
  - Commit to a release branch, push it, open a PR via the gh CLI.
  - If gh is absent/unauthenticated, prints manual instructions and exits 0.
  - Mutually exclusive with no_push=False + use_pr=False (push mode).

auto_merge=True:
  - After opening the PR, calls ``gh pr merge --auto --merge``.
  - Only meaningful in use_pr=True mode.
"""
from __future__ import annotations

import datetime
import hashlib
import io
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
    built: List[Path] = field(default_factory=list)      # zips built and copied to dist this run
    skipped: List[Path] = field(default_factory=list)    # kept for API compatibility; always empty now
    retired: List[Path] = field(default_factory=list)    # zips moved to retired/ (deprecations + stale)
    deleted: List[Path] = field(default_factory=list)    # legacy versioned zips deleted in-place
    readme_path: Path = None                             # path to the regenerated README
    commit_sha: Optional[str] = None                     # None on dry-run or when nothing changed
    pushed: bool = False
    pr_url: Optional[str] = None                         # URL of the opened PR (PR mode only)
    release_branch: Optional[str] = None                 # release branch name (PR / no-push mode)


# ---------------------------------------------------------------------------
# Content-hash helpers
# ---------------------------------------------------------------------------

def _zip_content_hash(path: Path) -> str:
    """Return a content hash of a distribution zip that ignores build-timestamps.

    Distribution zips are non-deterministic: the ``vcfops_manifest.json``
    member embeds a ``built_at`` wall-clock timestamp, and nested inner zips
    (``Dashboard.zip``, ``Views.zip``, etc.) embed per-entry date_time fields
    that also reflect the build clock.  None of these timestamps carry
    semantic content — they are all overwritten by VCF Ops on import.

    This function computes a content-only hash by:
      1. Skipping ``vcfops_manifest.json`` at any nesting level.
      2. For members that are themselves zips, recursing to hash their
         logical content (via ``zf.read(name)`` which returns decompressed
         bytes, stripping the zip framing that embeds date_time stamps).
      3. Hashing all other members' raw decompressed bytes.
      4. Sorting member names for deterministic iteration.

    Two builds of the same factory content will produce the same digest,
    enabling idempotent re-publishes even when the build clock advanced.

    For non-zip files or unreadable zips, falls back to a full file hash.

    Returns:
        A SHA-256 hex digest stable across same-content re-builds.
    """
    import zipfile as _zipfile

    def _hash_zip_data(data: bytes, h: "hashlib._Hash") -> None:
        """Recursively hash the logical content of a zip given its bytes."""
        try:
            with _zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in sorted(zf.namelist()):
                    if name.endswith("/") or name.endswith("vcfops_manifest.json"):
                        continue  # skip directories and build-timestamp-only member
                    member_bytes = zf.read(name)
                    h.update(name.encode())
                    if name.endswith(".zip"):
                        # Recurse into inner zip: hash its logical content,
                        # not its bytes (which embed date_time stamps).
                        _hash_zip_data(member_bytes, h)
                    else:
                        h.update(member_bytes)
        except Exception:
            # If we can't parse as zip, hash raw bytes.
            h.update(data)

    try:
        h = hashlib.sha256()
        _hash_zip_data(path.read_bytes(), h)
        return h.hexdigest()
    except Exception:
        # Fallback: hash the raw bytes (non-zip or corrupt zip).
        h2 = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h2.update(chunk)
        return h2.hexdigest()


def _copy_if_changed(src: Path, dest: Path) -> bool:
    """Copy src to dest only when the semantic content differs.

    Uses :func:`_zip_content_hash` to compare zip files, which excludes the
    ``vcfops_manifest.json`` build-timestamp entry so that idempotent
    re-builds of the same content do not overwrite the dest file.

    If dest is absent or has different content, copies src to dest using
    ``shutil.copy2`` (preserves mtime so dist-repo README dates stay stable).

    Returns:
        True if the file was copied (content changed or dest was absent).
        False if the copy was skipped (semantically identical).
    """
    if dest.exists() and _zip_content_hash(src) == _zip_content_hash(dest):
        return False
    shutil.copy2(str(src), str(dest))
    return True


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
# PR-mode helpers
# ---------------------------------------------------------------------------

def _detect_gh() -> bool:
    """Return True if the ``gh`` CLI is installed and authenticated."""
    try:
        r = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
        )
        return r.returncode == 0
    except FileNotFoundError:
        return False


def _next_release_branch_name(dist_repo: Path) -> str:
    """Compute the next available ``release/<date>-<n>`` branch name.

    Checks the remote (and local) for existing branches matching
    ``release/<YYYY-MM-DD>-<n>`` and returns the next unused name.
    """
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    prefix = f"release/{today}-"

    # Fetch remote refs (best-effort).
    _git(dist_repo, "fetch", "origin", "--prune")

    # List all local + remote branches.
    r = _git(dist_repo, "branch", "-a", "--list", f"*{prefix}*")
    existing_n: set[int] = set()
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            line = line.strip().lstrip("* ")
            # Strip remote prefix e.g. "remotes/origin/release/2026-04-27-2"
            if "/" in line:
                short = line.rsplit("/", 1)[-1]
            else:
                short = line
            # short = "release/<date>-<n>" or just "2026-04-27-2" after rsplit
            # Normalise: strip the "release/" prefix if it survived.
            if short.startswith("release/"):
                short = short[len("release/"):]
            # Now short should be "<date>-<n>"
            date_part = f"{today}-"
            if short.startswith(date_part):
                suffix = short[len(date_part):]
                try:
                    existing_n.add(int(suffix))
                except ValueError:
                    pass

    n = 1
    while n in existing_n:
        n += 1
    return f"release/{today}-{n}"


def _create_and_push_release_branch(
    dist_repo: Path,
    branch_name: str,
) -> None:
    """Create ``branch_name`` at current HEAD and push to origin.

    Raises PublishError if the branch already exists locally or remotely
    (idempotence guard — signals a retry situation).
    """
    # Check local branch.
    r_local = _git(dist_repo, "branch", "--list", branch_name)
    if r_local.returncode == 0 and r_local.stdout.strip():
        raise PublishError(
            f"Release branch '{branch_name}' already exists locally in {dist_repo}. "
            f"Delete it with 'git branch -d {branch_name}' and retry."
        )

    # Create the branch at current HEAD.
    r = _git(dist_repo, "checkout", "-b", branch_name)
    if r.returncode != 0:
        raise PublishError(
            f"Could not create release branch '{branch_name}': {r.stderr.strip()}"
        )

    # Push it to origin.
    r = _git(dist_repo, "push", "origin", branch_name)
    if r.returncode != 0:
        # Push failed — clean up the local branch and raise.
        _git(dist_repo, "checkout", "main")
        _git(dist_repo, "branch", "-D", branch_name)
        err = r.stderr.strip()
        if "already exists" in err or "rejected" in err:
            raise PublishError(
                f"Release branch '{branch_name}' already exists on origin. "
                f"Delete the remote branch and retry."
            )
        raise PublishError(
            f"git push (release branch) failed in {dist_repo}: {err}"
        )

    # Switch back to main so subsequent git operations behave normally.
    _git(dist_repo, "checkout", "main")


def _assemble_pr_body(
    releases,
    dist_repo: Path,
    branch_name: str,
    built_names: List[str],
    n_retired: int,
    n_deleted: int,
) -> str:
    """Assemble a PR body from release notes + README diff + files summary.

    Keeps the body reasonably compact: release notes per release (full text),
    README diff (truncated at 3000 chars), files-changed summary.
    """
    parts: list[str] = []

    # --- Per-release notes section ---
    release_notes_section: list[str] = []
    for r in releases:
        if r.name not in built_names:
            continue
        if r.release_notes and r.release_notes.strip():
            release_notes_section.append(f"### {r.name} {r.version}\n\n{r.release_notes.strip()}")
    if release_notes_section:
        parts.append("## Release notes\n\n" + "\n\n".join(release_notes_section))

    # --- README diff section ---
    r_diff = subprocess.run(
        ["git", "diff", f"main...{branch_name}", "--", "README.md"],
        capture_output=True,
        text=True,
        cwd=str(dist_repo),
        check=False,
    )
    if r_diff.returncode == 0 and r_diff.stdout.strip():
        diff_text = r_diff.stdout.strip()
        _DIFF_TRUNCATE = 3000
        if len(diff_text) > _DIFF_TRUNCATE:
            diff_text = diff_text[:_DIFF_TRUNCATE] + "\n\n…(diff truncated — see full diff in PR files view)"
        parts.append(f"## README diff\n\n```diff\n{diff_text}\n```")

    # --- Files summary ---
    r_files = subprocess.run(
        ["git", "diff", "--name-status", f"main...{branch_name}"],
        capture_output=True,
        text=True,
        cwd=str(dist_repo),
        check=False,
    )
    if r_files.returncode == 0 and r_files.stdout.strip():
        file_lines = r_files.stdout.strip().splitlines()
        added = [ln[2:].strip() for ln in file_lines if ln.startswith("A")]
        modified = [ln[2:].strip() for ln in file_lines if ln.startswith("M")]
        removed = [ln[2:].strip() for ln in file_lines if ln.startswith("D")]
        summary_lines: list[str] = []
        if added:
            summary_lines.append(f"**Added** ({len(added)}): " + ", ".join(f"`{f}`" for f in added))
        if modified:
            summary_lines.append(f"**Modified** ({len(modified)}): " + ", ".join(f"`{f}`" for f in modified))
        if removed:
            summary_lines.append(f"**Removed** ({len(removed)}): " + ", ".join(f"`{f}`" for f in removed))
        if summary_lines:
            parts.append("## Files changed\n\n" + "\n\n".join(summary_lines))

    return "\n\n---\n\n".join(parts) if parts else "Automated release publish."


def _open_pr(
    dist_repo: Path,
    branch_name: str,
    title: str,
    body: str,
) -> str:
    """Open a PR via ``gh pr create`` and return the PR URL.

    Raises PublishError if the gh call fails for reasons other than
    "PR already exists" (which gets a more specific message).
    """
    r = subprocess.run(
        [
            "gh", "pr", "create",
            "--base", "main",
            "--head", branch_name,
            "--title", title,
            "--body", body,
        ],
        capture_output=True,
        text=True,
        cwd=str(dist_repo),
        check=False,
    )
    if r.returncode != 0:
        combined = (r.stdout + r.stderr).lower()
        if "already exists" in combined or "pull request" in combined:
            # Try to surface the existing PR URL.
            r_view = subprocess.run(
                ["gh", "pr", "view", branch_name, "--json", "url", "--jq", ".url"],
                capture_output=True,
                text=True,
                cwd=str(dist_repo),
                check=False,
            )
            existing_url = r_view.stdout.strip() if r_view.returncode == 0 else "(unknown)"
            raise PublishError(
                f"A PR for branch '{branch_name}' already exists: {existing_url}\n"
                f"Delete the branch and retry, or merge/close the existing PR first."
            )
        raise PublishError(
            f"gh pr create failed:\n{r.stdout.strip()}\n{r.stderr.strip()}"
        )
    return r.stdout.strip()


def _gh_auto_merge(dist_repo: Path, pr_url: str) -> None:
    """Enable auto-merge on the PR identified by ``pr_url``.

    Prints a warning (does not raise) if auto-merge is blocked by branch
    protection settings, since the PR was already successfully opened.
    """
    r = subprocess.run(
        ["gh", "pr", "merge", "--auto", "--merge", pr_url],
        capture_output=True,
        text=True,
        cwd=str(dist_repo),
        check=False,
    )
    if r.returncode != 0:
        combined = (r.stdout + r.stderr).strip()
        print(
            f"WARN  --auto-merge requested but gh pr merge returned non-zero "
            f"(branch protection may block auto-merge):\n  {combined}"
        )


def _print_manual_pr_instructions(
    dist_repo: Path,
    branch_name: str,
    title: str,
    body: str,
) -> None:
    """Print manual PR instructions when gh is absent or unauthenticated."""
    print(
        "\nINFO  gh CLI is not available or not authenticated.\n"
        "      The release branch has been pushed — open the PR manually:\n\n"
        f"  git -C {dist_repo} push origin {branch_name}  # (if not already pushed)\n\n"
        "  Then open a PR:\n"
        f"    Base  : main\n"
        f"    Head  : {branch_name}\n"
        f"    Title : {title}\n\n"
        "  Body (copy below the dashes):\n"
        "  " + "-" * 60 + "\n"
    )
    for line in body.splitlines():
        print(f"  {line}")
    print("  " + "-" * 60)


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
    """Return the complete list of factory-native top-level subdirs we manage.

    These are the subdirs scanned by the legacy-versioned-zip sweep
    (which is factory-era naming cleanup only) and the stale-zip sweep.
    Third-party content lives under ThirdPartyContent/<sub>/ and is
    handled separately by _all_third_party_subdirs().
    """
    return [
        "bundles",
        "dashboards",
        "views",
        "supermetrics",
        "customgroups",
        "reports",
        "management-packs",
    ]


def _all_third_party_subdirs() -> List[str]:
    """Return the complete list of ThirdPartyContent sub-paths we manage.

    These are scanned by the stale-zip sweep but NOT by the legacy-versioned-
    zip sweep (the versioned-name era predates third-party routing).
    """
    return [
        "ThirdPartyContent/dashboards",
        "ThirdPartyContent/bundles",
    ]


def _all_headline_paths(releases) -> set[str]:
    """Return the set of expected zip filenames across all release headlines.

    Each element is in the form  "<subdir>/<slug>.zip" (versionless),
    e.g. "dashboards/demand-driven-capacity-v2.zip" or
    "ThirdPartyContent/dashboards/idps-planner.zip".
    """
    from .release_builder import _artifact_dest_subdir, _zip_filename
    known = set()
    for r in releases:
        for a in r.artifacts:
            if a.headline:
                subdir = _artifact_dest_subdir(a)
                filename = _zip_filename(r.name)
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
# Legacy-versioned-zip sweep
# ---------------------------------------------------------------------------

# Pattern for the OLD versioned zip naming: <anything>-<digits>.<digits>.zip
# Captured groups: (slug, version) where slug is everything before the last
# "-<digits>.<digits>" segment.
import re as _re_module
_LEGACY_VERSIONED_ZIP_RE = _re_module.compile(
    r"^(.+)-(\d+\.\d+)\.zip$"
)


def _sweep_legacy_versioned_zips(
    dist_repo: Path,
    known_slugs: set[str],
    dry_run: bool,
) -> List[Path]:
    """Delete in-place any ``<slug>-<X.Y>.zip`` whose slug matches a current release.

    These are leftover artifacts from the pre-versionless era.  They are NOT
    moved to ``retired/`` — the user's intent is "delete and let git history
    record it."  ``retired/`` is reserved for genuinely deprecated content
    (entries listed in a release's ``deprecates:`` field).

    Safety: only zips whose parsed slug is an exact member of ``known_slugs``
    are touched.  A release legitimately named ``something-1.2`` (with a
    version-looking suffix in its slug) will not be deleted because its
    expected zip is ``something-1.2.zip`` (present in ``known_filenames``)
    and the stale-zip sweep skips it.

    Args:
        dist_repo:   Root of the distribution repo.
        known_slugs: Set of release slugs (e.g. ``{"demand-driven-capacity-v2"}``).
        dry_run:     If True, compute but don't delete.

    Returns:
        List of paths that were (or would be) deleted.
    """
    deleted: List[Path] = []
    for subdir in _all_known_subdirs():
        subdir_path = dist_repo / subdir
        if not subdir_path.exists():
            continue
        for zip_path in sorted(subdir_path.glob("*.zip")):
            m = _LEGACY_VERSIONED_ZIP_RE.match(zip_path.name)
            if not m:
                continue
            slug = m.group(1)
            if slug not in known_slugs:
                continue
            # This is a legacy versioned zip for a slug we still manage.
            if not dry_run:
                zip_path.unlink()
            deleted.append(zip_path)
    return deleted


# ---------------------------------------------------------------------------
# Stale-zip sweep
# ---------------------------------------------------------------------------

def _sweep_stale_zips(
    dist_repo: Path,
    known_filenames: set[str],
    dry_run: bool,
) -> List[Path]:
    """Move zips with no corresponding release manifest to retired/<subdir>/.

    Only touches zips that are NOT the versionless canonical artifact for a
    current release (those are in ``known_filenames``) and are NOT legacy
    versioned zips for a current slug (those are handled by
    ``_sweep_legacy_versioned_zips``).

    Scans both factory-native top-level subdirs and ThirdPartyContent/<sub>/
    subdirs.  The legacy-versioned-zip sweep does NOT scan ThirdPartyContent/
    (that naming era predates third-party routing).

    Args:
        dist_repo:       Root of the distribution repo.
        known_filenames: Set of "<subdir>/<zipname>" for all current releases
                         (may include "ThirdPartyContent/dashboards/foo.zip").
        dry_run:         If True, compute but don't move.

    Returns:
        List of paths that were (or would be) moved to retired/.
    """
    retired: List[Path] = []
    all_subdirs = list(_all_known_subdirs()) + list(_all_third_party_subdirs())
    for subdir in all_subdirs:
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
    them to learn their name + version, then look for the zip under both the
    current versionless name (``<slug>.zip``) and the legacy versioned name
    (``<slug>-<version>.zip``) so that retirements work regardless of when
    the deprecated release was originally published.

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
                # Look for the deprecated zip under both the versionless name
                # (if the dep release was published after the naming change) and
                # the legacy versioned name (if it was published before).
                candidate_filenames = [
                    _zip_filename(dep_release.name),                          # versionless
                    f"{dep_release.name}-{dep_release.version}.zip",          # legacy versioned
                ]
                for filename in candidate_filenames:
                    src = dist_repo / subdir / filename
                    key = f"{subdir}/{filename}"
                    if key in already_handled:
                        continue
                    if not src.exists():
                        continue
                    already_handled.add(key)
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
    use_pr: bool = True,
    auto_merge: bool = False,
) -> PublishResult:
    """Orchestrate a full publish operation.

    Args:
        factory_repo: Absolute path to the factory repo root.
        dist_repo:    Absolute path to the distribution repo root.
        dry_run:      If True, compute what would happen without writing files
                      or committing.  Lockfile is still acquired.
        force:        If True, force a commit even when no on-disk content changed
                      (git reports nothing to commit).  Useful for debugging or
                      re-pushing identical content.
        no_push:      If True, commit the release branch locally but do not push
                      and do not open a PR.  (In PR mode: branch committed locally,
                      no remote push; in push mode: commit only, no push to main.)
        use_pr:       If True (default), create a release branch, push it, and
                      open a PR via ``gh pr create``.  Set to False for direct-push
                      mode (legacy/owner fast-path).  Mutually exclusive: use_pr=False
                      and auto_merge=True is an error.
        auto_merge:   If True, call ``gh pr merge --auto --merge`` after opening the
                      PR.  Only valid when use_pr=True.

    Returns:
        PublishResult with built/skipped/deleted/retired/readme_path/commit_sha/pushed/pr_url.

    Raises:
        PublishError: on any hard failure (lock busy, validator fail, git dirty,
                      build error).
    """
    if auto_merge and not use_pr:
        raise PublishError("--auto-merge requires PR mode (do not combine with --push).")

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
            use_pr=use_pr,
            auto_merge=auto_merge,
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
    use_pr: bool,
    auto_merge: bool,
    result: PublishResult,
) -> None:
    """Inner body of publish() — runs inside the lockfile try/finally."""
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
                _artifact_dest_subdir as _ads,
                _zip_filename as _zfn,
            )

            # Determine the expected destination path for each headline.
            # Always build and copy; git diff --staged decides whether content changed.
            built_this_release = False
            if not dry_run:
                artifacts = _build_one_release(release, staging, factory_repo)
            else:
                artifacts = None  # dry-run: no actual build

            for manifest_artifact in release.artifacts:
                if not manifest_artifact.headline:
                    continue

                subdir = _ads(manifest_artifact)
                filename = _zfn(release.name)   # versionless
                dest_path = dist_repo / subdir / filename

                if not dry_run:
                    assert artifacts is not None
                    for art in artifacts:
                        if art.dest_subdir != subdir:
                            continue
                        dest_dir = dist_repo / art.dest_subdir
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest_file = dest_dir / art.zip_path.name
                        _copy_if_changed(art.zip_path, dest_file)
                        result.built.append(dest_file)
                        built_names.append(release.name)
                        built_this_release = True
                else:
                    # Dry-run: record the would-be path.
                    result.built.append(dest_path)
                    built_names.append(release.name)
                    built_this_release = True

                # Only process each release once (first headline drives the
                # build; build_release processes all headlines internally).
                if built_this_release:
                    break

    # -----------------------------------------------------------------------
    # Step 6: Legacy-versioned-zip sweep (delete in-place, not retire)
    # -----------------------------------------------------------------------
    # Build the set of release slugs so the sweep can match precisely.
    known_slugs = {r.name for r in releases}
    deleted_legacy = _sweep_legacy_versioned_zips(dist_repo, known_slugs, dry_run)
    result.deleted.extend(deleted_legacy)

    # -----------------------------------------------------------------------
    # Step 7: Process retirements (move deprecated zips to retired/)
    # -----------------------------------------------------------------------
    retired_from_deprecates = _process_retirements(releases, dist_repo, dry_run)
    result.retired.extend(retired_from_deprecates)

    # -----------------------------------------------------------------------
    # Step 8: Stale-zip sweep (move other orphaned zips to retired/)
    # -----------------------------------------------------------------------
    retired_from_sweep = _sweep_stale_zips(dist_repo, known_filenames, dry_run)
    result.retired.extend(retired_from_sweep)

    # -----------------------------------------------------------------------
    # Step 9: Regenerate README
    # -----------------------------------------------------------------------
    result.readme_path = _update_dist_readme(dist_repo, factory_repo, releases, dry_run)

    # -----------------------------------------------------------------------
    # Step 10: Commit + branch/PR or direct push
    # -----------------------------------------------------------------------
    if not dry_run:
        n_built = len(result.built)
        n_retired = len(result.retired)
        n_deleted = len(result.deleted)
        release_names_str = (
            ", ".join(sorted(set(built_names))) if built_names else "none"
        )
        commit_msg = (
            f"release-publish: {n_built} built, {n_retired} retired, "
            f"{n_deleted} legacy deleted ({release_names_str})"
        )

        if use_pr:
            # PR mode (default) -----------------------------------------------
            # Compute the release branch name BEFORE the lockfile is released.
            branch_name = _next_release_branch_name(dist_repo)
            result.release_branch = branch_name

            # Create the release branch on the dist repo at current HEAD, then
            # stage+commit on that branch.
            r_cb = _git(dist_repo, "checkout", "-b", branch_name)
            if r_cb.returncode != 0:
                raise PublishError(
                    f"Could not create release branch '{branch_name}': "
                    f"{r_cb.stderr.strip()}"
                )

            # Release the lockfile before staging — the branch itself now acts
            # as the in-flight signal for anyone checking the dist repo.
            # The outer try/finally calls _release_lock again; idempotent.
            _release_lock(dist_repo)

            # Stage + commit on the release branch.
            if force:
                r = _git(dist_repo, "add", "-A", "--", ":!.publish.lock")
                if r.returncode != 0:
                    raise PublishError(
                        f"git add failed in {dist_repo}: {r.stderr.strip()}"
                    )
                r = _git(dist_repo, "commit", "--allow-empty", "-m", commit_msg)
                if r.returncode != 0:
                    raise PublishError(
                        f"git commit (force) failed in {dist_repo}: "
                        f"{r.stdout.strip()} {r.stderr.strip()}"
                    )
                r2 = _git(dist_repo, "rev-parse", "HEAD")
                result.commit_sha = r2.stdout.strip() if r2.returncode == 0 else None
            else:
                sha = _git_commit(dist_repo, commit_msg)
                result.commit_sha = sha

            if no_push:
                # --no-push: branch committed locally, no remote push, no PR.
                # Switch back to main so the dist repo is in a predictable state.
                _git(dist_repo, "checkout", "main")
                return

            # Push the release branch.
            r_push = _git(dist_repo, "push", "origin", branch_name)
            if r_push.returncode != 0:
                err = r_push.stderr.strip()
                if "already exists" in err or "rejected" in err:
                    raise PublishError(
                        f"Release branch '{branch_name}' already exists on origin. "
                        f"Delete the remote branch and retry."
                    )
                raise PublishError(
                    f"git push (release branch) failed in {dist_repo}: {err}"
                )
            result.pushed = True

            # Switch back to main so the dist repo is in a predictable state.
            _git(dist_repo, "checkout", "main")

            # Build PR title + body.
            pr_title = (
                f"release: {release_names_str} "
                f"({n_built} built, {n_retired} retired)"
            )
            pr_body = _assemble_pr_body(
                releases=releases,
                dist_repo=dist_repo,
                branch_name=branch_name,
                built_names=list(set(built_names)),
                n_retired=n_retired,
                n_deleted=n_deleted,
            )

            # Open the PR via gh CLI (or print manual instructions).
            if _detect_gh():
                pr_url = _open_pr(dist_repo, branch_name, pr_title, pr_body)
                result.pr_url = pr_url
                print(f"PR opened: {pr_url}")
                if auto_merge:
                    _gh_auto_merge(dist_repo, pr_url)
            else:
                _print_manual_pr_instructions(dist_repo, branch_name, pr_title, pr_body)
                result.pr_url = None

        else:
            # Direct-push mode (--push) ---------------------------------------
            # Release the lockfile BEFORE staging so it is never included in
            # the commit.  The outer try/finally calls _release_lock again;
            # _release_lock is idempotent (missing_ok=True).
            _release_lock(dist_repo)

            if force:
                r = _git(dist_repo, "add", "-A", "--", ":!.publish.lock")
                if r.returncode != 0:
                    raise PublishError(
                        f"git add failed in {dist_repo}: {r.stderr.strip()}"
                    )
                r = _git(dist_repo, "commit", "--allow-empty", "-m", commit_msg)
                if r.returncode != 0:
                    raise PublishError(
                        f"git commit (force) failed in {dist_repo}: "
                        f"{r.stdout.strip()} {r.stderr.strip()}"
                    )
                r2 = _git(dist_repo, "rev-parse", "HEAD")
                result.commit_sha = r2.stdout.strip() if r2.returncode == 0 else None
            else:
                sha = _git_commit(dist_repo, commit_msg)
                result.commit_sha = sha

            if result.commit_sha and not no_push:
                _git_push(dist_repo)
                result.pushed = True

    return
