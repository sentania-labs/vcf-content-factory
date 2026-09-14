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

Reference point is OFFLINE: committed versions of the content in git,
never the live instance. By default the working tree is compared against
HEAD. CI passes the PR merge-base (--id-guard-baseline) because in CI
the re-id is already committed, so HEAD alone is blind to it. A baseline
NEVER replaces the HEAD comparison: the working tree is compared against
HEAD, the baseline, AND every commit in between (git rev-list
baseline..HEAD), and the findings are unioned. Comparing against only
the two endpoints is not enough: a PR that renames a dashboard in one
commit and re-ids it under the new name in a later commit shows a clean
diff at both endpoints (HEAD equals the working tree; against the
merge-base both name and id differ, indistinguishable from
delete-plus-new), while the intermediate commit still published the new
name under the old id, so installing the tip orphans that UUID. Only the
intermediate scan catches that class. The flag can therefore only WIDEN
the comparison; a non-ancestor baseline is a hard validation error, not
a fallback, and nothing the flag does can suppress a finding the plain
HEAD comparison would report. No escape hatch.

Git-outcome handling follows
knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md: every
status we branch on is enumerated, and everything else degrades to
"guard could not run" with a printed warning, never to a silent pass and
never to a confident claim. Presence-in-a-rev is decided from
``git ls-tree <rev> -- <path>`` stdout (empty vs non-empty under rc 0),
never by parsing localized stderr text; ``_run_git`` additionally pins
LC_ALL=C so any stderr we embed in warnings is stable English.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

__all__ = ["check_dashboard_id_stability"]


def _run_git(args: List[str], cwd: Path) -> Tuple[Optional[int], str, str]:
    """Run git; return (returncode, stdout, stderr).

    returncode is None when git itself could not be executed (not
    installed / not on PATH). Callers must treat None and any
    non-enumerated returncode as "could not determine", never as a pass
    verdict in disguise.

    LC_ALL/LANG are pinned to C so no branch here can ever depend on a
    localized message, and stderr text embedded in warnings is stable.
    Verdicts must still come from return codes and stdout content, not
    from stderr wording.
    """
    env = dict(os.environ, LC_ALL="C", LANG="C")
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            env=env,
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


def _rev_dashboard_names(
    toplevel: Path, rel_dir: str, warnings_out: List[str], rev: str
) -> Dict[str, Tuple[str, str]]:
    """Map name -> (id, path) for every dashboard YAML committed at *rev*
    under rel_dir. Used for the file-rename case: a re-id'd dashboard in
    a renamed file must not slip past the path-based comparison.
    """
    rc, out, err = _run_git(
        ["ls-tree", "-r", "--name-only", rev, "--", rel_dir], toplevel
    )
    if rc != 0:
        warnings_out.append(
            "dashboard id-stability guard: could not list dashboards "
            f"committed at {rev} (git ls-tree rc={rc}: "
            f"{err.strip() or 'git unavailable'}); "
            "the file-rename check did not run for that rev"
        )
        return {}
    result: Dict[str, Tuple[str, str]] = {}
    for line in out.splitlines():
        p = line.strip()
        if not p.endswith((".yaml", ".yml")):
            continue
        rc2, blob, err2 = _run_git(["show", f"{rev}:{p}"], toplevel)
        if rc2 != 0:
            warnings_out.append(
                "dashboard id-stability guard: could not read committed "
                f"'{p}' at {rev} (git show rc={rc2}: {err2.strip()}); "
                "skipped in the file-rename check"
            )
            continue
        identity = _parse_identity(blob)
        if identity:
            result[identity[0]] = (identity[1], p)
    return result


def _scan_rev(
    rev: str,
    files: List[Path],
    dashboards_dir: Path,
    toplevel: Path,
) -> Tuple[List[str], List[str]]:
    """Compare the working-tree dashboard *files* against commit *rev*.

    Returns (errors, warnings) for this rev only; the caller unions the
    findings across all scanned revs.
    """
    errors: List[str] = []
    warns: List[str] = []
    rev_names: Optional[Dict[str, Tuple[str, str]]] = None  # lazy

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

        # Presence-in-rev is decided from ls-tree stdout, which is
        # locale-independent: rc 0 + non-empty stdout = committed, rc 0 +
        # empty stdout = no committed version at this path. stderr text is
        # never consulted for a verdict (localized git would defeat it).
        rc, tree_out, err = _run_git(["ls-tree", rev, "--", rel], toplevel)
        if rc != 0:
            warns.append(
                "dashboard id-stability guard: could not determine whether "
                f"'{rel}' has a committed version at {rev} (git ls-tree "
                f"rc={rc}: {err.strip() or 'git unavailable'}); identity not "
                "checked for this file at that rev"
            )
            continue
        need_name_scan = False
        if tree_out.strip():
            rc, blob, err = _run_git(["show", f"{rev}:{rel}"], toplevel)
            if rc != 0:
                warns.append(
                    "dashboard id-stability guard: could not read the "
                    f"committed version of '{rel}' at {rev} (git show "
                    f"rc={rc}: {err.strip() or 'git unavailable'}); identity "
                    "not checked for this file at that rev"
                )
                continue
            rev_identity = _parse_identity(blob)
            if rev_identity is not None:
                rev_name, rev_id = rev_identity
                if rev_name == wt_name and rev_id != wt_id:
                    errors.append(_orphan_message(f, wt_name, rev_id, wt_id, rel))
                    continue
                if rev_name != wt_name:
                    # Name changed in place (a rename, legitimate) OR the
                    # file was repurposed; either way its new name must
                    # not collide with a different committed dashboard.
                    need_name_scan = True
        else:
            # Path absent at this rev: could be a genuinely new dashboard,
            # or a file rename. The name scan decides.
            need_name_scan = True

        if need_name_scan:
            if rev_names is None:
                try:
                    rel_dir = dashboards_dir.relative_to(toplevel).as_posix()
                except ValueError:
                    rel_dir = "."
                rev_names = _rev_dashboard_names(toplevel, rel_dir, warns, rev)
            hit = rev_names.get(wt_name)
            if hit is not None:
                rev_id, rev_path = hit
                if rev_id != wt_id:
                    errors.append(
                        _orphan_message(f, wt_name, rev_id, wt_id, rev_path)
                    )

    return errors, warns


def check_dashboard_id_stability(
    dashboards_dir: Path, baseline: Optional[str] = None
) -> Tuple[List[str], List[str]]:
    """Compare each working-tree dashboard YAML against committed history.

    *baseline* is a git rev; None/empty means compare against HEAD only.
    A supplied baseline must resolve to a commit that is an ancestor of
    HEAD (equal to HEAD is fine) and ADDS comparisons, it never replaces
    the HEAD one: the working tree is checked against HEAD, the baseline,
    and every commit in baseline..HEAD, with identical findings deduped.
    A non-ancestor baseline is a misconfiguration and fails validation
    outright. An unresolvable baseline is an environment condition (e.g.
    CI could not compute a merge-base): degrade to HEAD-only with a
    printed warning, never silently.

    Returns (errors, warnings). Errors are hard validation failures: a
    committed dashboard shares the working-tree name but carries a
    different id. Warnings mean the guard (or part of it) could not run
    (no git, not a repo, unreadable rev); validation proceeds, but never
    silently.
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
    rc, head_out, err = _run_git(["rev-parse", "--verify", "--quiet", "HEAD"], toplevel)
    if rc != 0:
        warns.append(
            "dashboard id-stability guard: repository has no commits yet "
            "(HEAD is unborn), so there is no committed baseline to "
            "compare dashboard ids against."
        )
        return errors, warns
    head_hash = head_out.strip()

    # HEAD is always scanned; a baseline can only ADD revs to scan.
    revs: List[str] = ["HEAD"]
    if baseline and baseline != "HEAD":
        rc, out, err = _run_git(
            ["rev-parse", "--verify", "--quiet", f"{baseline}^{{commit}}"],
            toplevel,
        )
        if rc != 0:
            # Environment condition (e.g. CI failed to compute a
            # merge-base): degrade to HEAD-only, loudly. HEAD-only is the
            # narrower comparison, so say exactly what is not covered.
            warns.append(
                "dashboard id-stability guard: baseline rev "
                f"'{baseline}' did not resolve to a commit (git rev-parse "
                f"rc={rc}: {err.strip() or 'no output'}); comparing against "
                "HEAD only. A re-id already committed since the intended "
                "baseline would NOT be caught in this run."
            )
        else:
            resolved = out.strip()
            rc, _, err = _run_git(
                ["merge-base", "--is-ancestor", resolved, "HEAD"], toplevel
            )
            if rc == 0:
                if resolved != head_hash:
                    # Every commit strictly between baseline and HEAD, so a
                    # violation confined to an intermediate commit (rename
                    # then re-id inside one PR) cannot hide from the
                    # endpoint comparisons.
                    rc, out, err = _run_git(
                        ["rev-list", f"{resolved}..HEAD"], toplevel
                    )
                    if rc == 0:
                        for line in out.splitlines():
                            c = line.strip()
                            if c and c != head_hash and c not in revs:
                                revs.append(c)
                    else:
                        warns.append(
                            "dashboard id-stability guard: could not "
                            f"enumerate commits between baseline "
                            f"'{baseline}' and HEAD (git rev-list rc={rc}: "
                            f"{err.strip() or 'no output'}); comparing "
                            "against the baseline and HEAD only. A re-id "
                            "confined to an intermediate commit would NOT "
                            "be caught in this run."
                        )
                    revs.append(resolved)
            elif rc == 1:
                # Misconfiguration, not an environment condition: a
                # baseline may only add earlier commits on this history
                # to the comparison (widening it). Refuse, hard.
                errors.append(
                    f"id-guard baseline '{baseline}' ({resolved}) is not "
                    "an ancestor of HEAD. --id-guard-baseline may only "
                    "add earlier commits on this history to the "
                    "comparison; it can never narrow or disable the "
                    "guard. Fix the baseline computation (CI passes the "
                    "PR merge-base) or drop the flag to compare against "
                    "HEAD."
                )
                return errors, warns
            else:
                warns.append(
                    "dashboard id-stability guard: could not determine "
                    f"whether baseline '{baseline}' is an ancestor of HEAD "
                    f"(git merge-base rc={rc}: {err.strip() or 'no output'}); "
                    "comparing against HEAD only. A re-id already committed "
                    "since the intended baseline would NOT be caught in "
                    "this run."
                )

    # Union the findings across all scanned revs; identical findings
    # (same file, name, and id pair) produce identical strings and dedupe.
    seen_errors: set = set()
    seen_warns: set = set()
    for rev in revs:
        rev_errors, rev_warns = _scan_rev(rev, files, dashboards_dir, toplevel)
        for msg in rev_errors:
            if msg not in seen_errors:
                seen_errors.add(msg)
                errors.append(msg)
        for msg in rev_warns:
            if msg not in seen_warns:
                seen_warns.add(msg)
                warns.append(msg)

    return errors, warns


def _orphan_message(f: Path, name: str, rev_id: str, wt_id: str, rev_path: str) -> str:
    return (
        f"{f}: dashboard '{name}' changed id from {rev_id} (committed in "
        f"{rev_path}) to {wt_id} while keeping its name. Dashboard import "
        "identity is the NAME: installing this would replace the existing "
        f"dashboard and silently orphan UUID {rev_id}; every deep link, "
        "summary-tab association, and bookmark pinned to it breaks with no "
        "error in the import envelope (issue #113, RULE-007). Fix: restore "
        f"the original id ({rev_id}); if this is genuinely a new dashboard, "
        "give it a new name instead."
    )
