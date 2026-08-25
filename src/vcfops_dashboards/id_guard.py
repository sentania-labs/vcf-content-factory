"""Validate-time guard: a dashboard's id must not change under an unchanged name.

Why (issue #113, measured on the devel lab, evidence in
knowledge/context/api-surface/content_import_skip_semantics.md):
dashboard import identity on VCF Ops is the NAME, not the UUID. Importing
a dashboard whose name matches an existing one but whose id differs
REPLACES the existing dashboard and silently orphans the old UUID. Deep
links, summary-tab associations (associateResourceKindDashboards), and
bookmarks pinned to the old UUID die with no error anywhere in the
import envelope. A rename does not change the UUID, so a changed id
under an unchanged name is always an authoring error (RULE-007).

Reference point is OFFLINE: the last committed version of the content in
git HEAD, never the live instance. Each working-tree dashboard YAML is
compared against ``git show HEAD:<path>``; if the committed version (or
any committed dashboard, for file renames) carries the same name under a
different id, validation fails hard. No escape hatch.

Git-outcome handling follows
knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md: every
status we branch on is enumerated, and everything else degrades to
"guard could not run" with a printed warning, never to a silent pass and
never to a confident claim.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

__all__ = ["check_dashboard_id_stability"]

# git show HEAD:<path> stderr fragments that mean "this path has no
# committed version" (git 2.x wording, both variants observed):
#   "fatal: path '<p>' exists on disk, but not in 'HEAD'"
#   "fatal: path '<p>' does not exist in 'HEAD'"
_PATH_NOT_IN_HEAD_FRAGMENTS = (
    "exists on disk, but not in",
    "does not exist in",
)


def _run_git(args: List[str], cwd: Path) -> Tuple[Optional[int], str, str]:
    """Run git; return (returncode, stdout, stderr).

    returncode is None when git itself could not be executed (not
    installed / not on PATH). Callers must treat None and any
    non-enumerated returncode as "could not determine", never as a pass
    verdict in disguise.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError) as exc:
        return None, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def _parse_identity(text: str) -> Optional[Tuple[str, str]]:
    """Extract (name, id) from raw dashboard YAML text.

    Returns None when the text is not a YAML mapping or lacks either
    field. Raw top-level fields are compared on both sides, so any
    loader-side name transformation cancels out.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    name = str(data.get("name") or "").strip()
    dash_id = str(data.get("id") or "").strip().lower()
    if not name or not dash_id:
        return None
    return name, dash_id


def _head_dashboard_names(
    toplevel: Path, rel_dir: str, warnings_out: List[str]
) -> Dict[str, Tuple[str, str]]:
    """Map name -> (id, path) for every dashboard YAML committed in HEAD
    under rel_dir. Used for the file-rename case: a re-id'd dashboard in
    a renamed file must not slip past the path-based comparison.
    """
    rc, out, err = _run_git(
        ["ls-tree", "-r", "--name-only", "HEAD", "--", rel_dir], toplevel
    )
    if rc != 0:
        warnings_out.append(
            "dashboard id-stability guard: could not list committed dashboards "
            f"(git ls-tree rc={rc}: {err.strip() or 'git unavailable'}); "
            "the file-rename check did not run"
        )
        return {}
    result: Dict[str, Tuple[str, str]] = {}
    for line in out.splitlines():
        p = line.strip()
        if not p.endswith((".yaml", ".yml")):
            continue
        rc2, blob, err2 = _run_git(["show", f"HEAD:{p}"], toplevel)
        if rc2 != 0:
            warnings_out.append(
                "dashboard id-stability guard: could not read committed "
                f"'{p}' (git show rc={rc2}: {err2.strip()}); skipped in the "
                "file-rename check"
            )
            continue
        identity = _parse_identity(blob)
        if identity:
            result[identity[0]] = (identity[1], p)
    return result


def check_dashboard_id_stability(dashboards_dir: Path) -> Tuple[List[str], List[str]]:
    """Compare each working-tree dashboard YAML against git HEAD.

    Returns (errors, warnings). Errors are hard validation failures: a
    committed dashboard shares the working-tree name but carries a
    different id. Warnings mean the guard could not run (no git, not a
    repo, unreadable HEAD); validation proceeds, but never silently.
    """
    errors: List[str] = []
    warns: List[str] = []

    if not dashboards_dir.exists():
        return errors, warns
    files = sorted(dashboards_dir.rglob("*.y*ml"))
    if not files:
        return errors, warns

    dashboards_dir = dashboards_dir.resolve()
    rc, out, err = _run_git(["rev-parse", "--show-toplevel"], dashboards_dir)
    if rc is None:
        warns.append(
            "dashboard id-stability guard could not run: git is not "
            f"available ({err.strip()}). A changed id: under an unchanged "
            "name: would NOT be caught in this run."
        )
        return errors, warns
    if rc != 0:
        # 128 covers both "not a git repository" and a broken repository;
        # git does not distinguish them here, so neither do we: unknown,
        # reported, not silently passed.
        warns.append(
            "dashboard id-stability guard could not run: "
            f"'{dashboards_dir}' is not inside a usable git repository "
            f"(git rev-parse rc={rc}: {err.strip()}). A changed id: under "
            "an unchanged name: would NOT be caught in this run."
        )
        return errors, warns
    toplevel = Path(out.strip()).resolve()

    # Unborn HEAD (fresh repo, no commits): there is no committed
    # baseline, so there is nothing to guard against. Enumerated pass.
    rc, _, err = _run_git(["rev-parse", "--verify", "--quiet", "HEAD"], toplevel)
    if rc != 0:
        warns.append(
            "dashboard id-stability guard: repository has no commits yet "
            "(HEAD is unborn), so there is no committed baseline to "
            "compare dashboard ids against."
        )
        return errors, warns

    head_names: Optional[Dict[str, Tuple[str, str]]] = None  # lazy

    for f in files:
        wt_identity = _parse_identity(f.read_text())
        if wt_identity is None:
            # Unparseable or missing name/id: the loader owns that
            # complaint; the guard has nothing to compare.
            continue
        wt_name, wt_id = wt_identity
        try:
            rel = f.resolve().relative_to(toplevel).as_posix()
        except ValueError:
            warns.append(
                f"dashboard id-stability guard: '{f}' resolves outside the "
                f"git toplevel '{toplevel}'; identity not checked for this file"
            )
            continue

        rc, blob, err = _run_git(["show", f"HEAD:{rel}"], toplevel)
        need_name_scan = False
        if rc == 0:
            head_identity = _parse_identity(blob)
            if head_identity is not None:
                head_name, head_id = head_identity
                if head_name == wt_name and head_id != wt_id:
                    errors.append(_orphan_message(f, wt_name, head_id, wt_id, rel))
                    continue
                if head_name != wt_name:
                    # Name changed in place (a rename, legitimate) OR the
                    # file was repurposed; either way its new name must
                    # not collide with a different committed dashboard.
                    need_name_scan = True
        elif rc == 128 and any(
            frag in err for frag in _PATH_NOT_IN_HEAD_FRAGMENTS
        ):
            # New path: could be a genuinely new dashboard, or a file
            # rename. The name scan decides.
            need_name_scan = True
        else:
            warns.append(
                "dashboard id-stability guard: could not read the committed "
                f"version of '{rel}' (git show rc={rc}: "
                f"{err.strip() or 'git unavailable'}); identity not checked "
                "for this file"
            )
            continue

        if need_name_scan:
            if head_names is None:
                try:
                    rel_dir = dashboards_dir.relative_to(toplevel).as_posix()
                except ValueError:
                    rel_dir = "."
                head_names = _head_dashboard_names(toplevel, rel_dir, warns)
            hit = head_names.get(wt_name)
            if hit is not None:
                head_id, head_path = hit
                if head_id != wt_id:
                    errors.append(
                        _orphan_message(f, wt_name, head_id, wt_id, head_path)
                    )

    return errors, warns


def _orphan_message(f: Path, name: str, head_id: str, wt_id: str, head_path: str) -> str:
    return (
        f"{f}: dashboard '{name}' changed id from {head_id} (committed in "
        f"{head_path}) to {wt_id} while keeping its name. Dashboard import "
        "identity is the NAME: installing this would replace the existing "
        f"dashboard and silently orphan UUID {head_id}; every deep link, "
        "summary-tab association, and bookmark pinned to it breaks with no "
        "error in the import envelope (issue #113, RULE-007). Fix: restore "
        f"the original id ({head_id}); if this is genuinely a new dashboard, "
        "give it a new name instead."
    )
