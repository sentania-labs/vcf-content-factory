---
description: Build every release manifest under `releases/` into a zip, route artifacts to per-type subdirs in `vcf-content-factory-bundles/`, regenerate the README between AUTO markers, commit, and push. See `designs/release-lifecycle-v1.md`.
---

You are the VCF Content Factory orchestrator. The user invoked `/publish` with the following args:

```
$ARGUMENTS
```

## Your job

Wrap `python3 -m vcfops_packaging publish` and report the result. The CLI
runs the full publish pipeline (Phase 3 orchestrator from
`designs/release-lifecycle-v1.md`): validate → enumerate releases →
build → route → retire stale zips → regenerate README → commit → push.

This slash command is thin glue. Do not re-implement the orchestration in
markdown.

## Args grammar

```
/publish [--dry-run] [--force] [--no-push] [--dist-repo <path>]
```

- `--dry-run` (default false): build into a temp dir but do not copy
  anything to the dist repo, do not commit, do not push. Use for previewing
  what *would* happen.
- `--force` (default false): when an existing zip in the dist repo has the
  same name but a different version, overwrite it. Without `--force` the
  CLI errors on version conflicts.
- `--no-push` (default false): commit the dist repo locally but skip the
  push to `origin/main`. Use when you want to inspect the commit before
  publishing externally.
- `--dist-repo <path>` (default `../vcf-content-factory-bundles/`): override
  the dist repo path. Useful for testing.

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

If any of these aren't met, surface the issue early. Don't run.

### 2. Run the CLI

Pass `$ARGUMENTS` through directly:

```
python3 -m vcfops_packaging publish $ARGUMENTS
```

The CLI handles lockfile acquisition, full validation, build, route,
retire, README, commit, and push in that order. Each step is atomic; on
failure the CLI stops and reports.

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
```

Reflect that to the user. If `--dry-run` was used, make clear nothing
shipped — this was a preview.

If the CLI exits non-zero, surface the error verbatim. Common cases:

- **Lockfile present.** Another `/publish` is running, OR a previous one
  crashed without removing the lockfile. The CLI's message will say which.
  If the prior run is genuinely dead, the user can `rm
  vcf-content-factory-bundles/.publish.lock` and retry.
- **Validators failed.** The factory repo has invalid content. Hand the
  user the validator output and stop.
- **Dist repo dirty / wrong branch / behind origin.** Tell the user to
  fix the dist repo state. Do not auto-stash, auto-pull, or auto-push.
- **Version conflict** (an existing zip has the same release name but a
  different version). Tell the user to pass `--force` if they truly want
  to overwrite, or bump the release-manifest version with `/release
  <type> <name> --version <X.Y>` first.

### 4. Do not chain into other commands

`/publish` is the end of the lifecycle. Do not auto-run additional
operations after it (no auto-merge, no auto-tag, no auto-followups).

## Examples

```
/publish
/publish --dry-run
/publish --no-push
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
