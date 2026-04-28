---
description: Build every release manifest under `releases/` into a zip, route artifacts to per-type subdirs in `vcf-content-factory-bundles/`, regenerate the README between AUTO markers, commit to a release branch, and open a PR (default) or push directly to main. See `designs/release-lifecycle-v1.md` and `designs/publish-pr-mode-v4.md`.
---

You are the VCF Content Factory orchestrator. The user invoked `/publish` with the following args:

```
$ARGUMENTS
```

## Your job

Wrap `python3 -m vcfops_packaging publish` and report the result. The CLI
runs the full publish pipeline (Phase 3 / v4 orchestrator from
`designs/release-lifecycle-v1.md` and `designs/publish-pr-mode-v4.md`):
validate → enumerate releases → build → route → retire stale zips →
regenerate README → commit → branch/PR (default) or direct push.

This slash command is thin glue. Do not re-implement the orchestration in
markdown.

## Args grammar

```
/publish              ← PR mode (default): opens a PR against main
/publish --push       ← direct push to main (legacy/owner fast-path)
/publish --pr         ← explicit PR mode (no-op; same as omitting it)
/publish --auto-merge ← open PR + immediately enable auto-merge
/publish --no-push    ← build and commit release branch locally; no push, no PR
/publish --dry-run    ← build into temp dir, no commit/branch/push/PR
/publish --force      ← force commit even if nothing changed
/publish --dist-repo <path>  ← override dist repo path
```

Flag semantics:

- **`--pr`** (default, no-op for explicitness): create a `release/<date>-<n>`
  branch, push it, open a PR via `gh pr create`.  Base: `main`. Prints the PR URL.
- **`--push`** (opt-in): direct push to `main` — the legacy/owner fast-path.
  Mutually exclusive with `--pr` and `--auto-merge`.
- **`--auto-merge`**: open PR then run `gh pr merge --auto --merge`.
  Implies PR mode. Mutually exclusive with `--push`.
- **`--no-push`**: commit to the release branch locally but do not push and
  do not open a PR. Lets the user inspect the branch before taking it further.
- **`--dry-run`** (default false): build into a temp dir but do not copy
  anything to the dist repo, do not commit, do not push, do not open PR.
  Use for previewing what *would* happen.
- **`--force`** (default false): force a commit even when content is byte-identical.
  Useful for debugging or re-pushing identical content.
- **`--dist-repo <path>`** (default `../vcf-content-factory-bundles/`): override
  the dist repo path. Useful for testing.

## gh CLI requirement

PR mode (the default) requires the `gh` CLI to be installed and authenticated.
If `gh` is absent or unauthenticated, the CLI prints detailed manual instructions
(push the branch, open a PR with the assembled title and body) and exits 0 — the
release branch is on the remote, the user just needs to open the PR manually.

## Idempotence

If a release branch with the expected `release/<date>-<n>` name already exists,
the CLI fails with a clear message. Delete the branch and retry, or merge/close
the existing PR first.

## Flow

### 1. Pre-flight reminders to the user

Before running, briefly note:

- **Factory repo working tree must be clean.** The CLI will refuse if it
  isn't (validates by running the eight per-package validators). User
  should commit any in-flight work first.
- **Dist repo working tree must be clean and on `main`.** The CLI checks.
- **Dist repo's README needs `<!-- AUTO:START release-catalog -->` markers
  somewhere.** Without them the CLI WARNs and skips README regen rather
  than failing — the publish still succeeds but the catalog table doesn't
  refresh. Tell the user to add markers if missing (one-time manual edit).
- **gh CLI required for PR mode (the default).** If absent, instructions
  are printed instead of failing.

If any of these aren't met, surface the issue early. Don't run.

### 2. Run the CLI

Pass `$ARGUMENTS` through directly:

```
python3 -m vcfops_packaging publish $ARGUMENTS
```

The CLI handles lockfile acquisition, full validation, build, route,
retire, README, commit, branch/PR (or direct push), in that order.
Each step is atomic; on failure the CLI stops and reports.

### 3. Report the result

The CLI prints a structured summary:

```
Publish complete.
  built   : N
    <list of zip paths>
  skipped : N
  retired : N
    <list>
  readme  : <path>
  commit  : <sha>  (or "none (dry-run)")
  pushed  : True | False
  branch  : release/<date>-<n>   (PR / no-push mode)
  pr      : <URL>                (PR mode; absent if gh unavailable)
```

Reflect that to the user. If `--dry-run` was used, make clear nothing
shipped — this was a preview. If a PR URL is present, surface it
prominently so the user can review and merge.

If the CLI exits non-zero, surface the error verbatim. Common cases:

- **Lockfile present.** Another `/publish` is running, OR a previous one
  crashed without removing the lockfile. The CLI's message will say which.
  If the prior run is genuinely dead, the user can `rm
  vcf-content-factory-bundles/.publish.lock` and retry.
- **Validators failed.** The factory repo has invalid content. Hand the
  user the validator output and stop.
- **Dist repo dirty / wrong branch / behind origin.** Tell the user to
  fix the dist repo state. Do not auto-stash, auto-pull, or auto-push.
- **Release branch already exists.** A PR for this date-slot may already
  be open. Tell the user to check the dist repo and retry.
- **`--push` + `--auto-merge` together.** These are mutually exclusive.
  Tell the user to pick one.

### 4. Do not chain into other commands

`/publish` is the end of the lifecycle. Do not auto-run additional
operations after it (no auto-tag, no auto-followups). The user decides
what happens after reviewing the PR.

## Examples

```
/publish
/publish --dry-run
/publish --push
/publish --no-push
/publish --auto-merge
/publish --force --dry-run
/publish --dist-repo /tmp/test-dist
```

## Constraints

- Do NOT modify any factory-repo or dist-repo file by hand. The CLI does
  everything.
- Do NOT push anything except via the CLI's git push step (which respects
  `--no-push`).
- Do NOT run agents — this is a CLI wrapper.
- If the user wants to ship one item without going through the lifecycle,
  redirect them to `/release <type> <name>` first, then `/publish`.
