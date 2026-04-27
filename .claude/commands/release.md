---
description: Materialize a release manifest for a single content item, flip its `released:` flag, and commit. Local operation — does not build or push. Run `/publish` after to ship released items to the distribution repo.
---

You are the VCF Content Factory orchestrator. The user invoked `/release` with the following args:

```
$ARGUMENTS
```

## Your job

Wrap `python3 -m vcfops_packaging release` so the user can release a content
item by typing a slash command. The CLI does all the actual work — your job
is to parse the args, run the command, and report the result clearly.

The release lifecycle design doc lives at `designs/release-lifecycle-v1.md`
if anything below is ambiguous.

## Args grammar

```
/release <type> <name> [--version X.Y] [--notes <file>] [--deprecates <slug>] [--no-commit]
```

- `<type>` (required): one of `dashboard`, `view`, `supermetric`, `customgroup`,
  `report`, `bundle`. (Symptoms and alerts are not standalone-releasable in v1
  — they ride inside bundles. The CLI will error clearly if the user tries.)
- `<name>` (required): may be a filename stem (`demand_driven_capacity_v2`),
  a display name (`"[VCF Content Factory] Demand-Driven Capacity Planning v2"`),
  or a path (`dashboards/demand_driven_capacity_v2.yaml`). The CLI resolves
  in that order.
- `--version X.Y` (optional): explicit version for the release. If absent and
  a release manifest already exists for this slug, auto-bumps the minor
  (`1.0` → `1.1`). If absent and no manifest exists, defaults to `1.0`.
  Major.minor only — no patch component.
- `--notes <path>` (optional): path to a markdown file whose contents become
  the release manifest's `release_notes:` field.
- `--deprecates <slug>` (optional, repeatable): name of a prior release
  manifest this one supersedes. The next `/publish` will move the deprecated
  release's zip into `retired/`.
- `--no-commit` (optional): stage the changes but don't commit them. Default
  behavior IS to commit (per design Q2: `/release` commits).

## Flow

### 1. Run the CLI

Invoke directly, passing $ARGUMENTS through:

```
python3 -m vcfops_packaging release $ARGUMENTS
```

If the user did not supply a `<type>` or `<name>`, the CLI errors with usage
help — surface that error verbatim.

### 2. Report the result

The CLI prints a short summary to stdout:

```
release manifest : releases/<slug>.yaml
source flagged   : <source-path>  (released: true)
version          : X.Y
commit           : <sha>
```

Reflect that to the user. If `--no-commit` was used, the commit line will be
absent and there will be staged-but-uncommitted changes; mention this so the
user knows to commit by hand.

If the CLI exits non-zero, surface the error. Common cases:

- **Stale-state validation fails** (a `released: true` flag exists somewhere
  that the manifest scan can't reconcile). The CLI's error message is
  authoritative — show it. Do not try to fix.
- **Unsupported type** (`symptom`, `alert`). Tell the user these ride inside
  bundles in v1 and to release the parent bundle instead.
- **Version conflict** (the resulting version exactly matches what's already
  in the manifest). Tell the user to pass `--version X.Y` for an explicit
  bump.
- **Source resolution failure** (no YAML matches the type+name combination).
  Tell the user the resolved path the CLI tried, and the candidates it
  rejected.

### 3. Do not run `/publish` automatically

`/release` is a preparation step. It does not build zips, sync to the
distribution repo, or push anywhere. After one or more `/release` calls,
the user runs `/publish` separately to ship everything ready.

## Examples

```
/release dashboard demand_driven_capacity_v2
/release bundle capacity-assessment --version 1.1
/release view vks_core_consumption_by_vcenter --notes notes/vks-1.0.md
/release dashboard new_thing --deprecates old-thing-v1
```

## Constraints

- Do NOT touch any YAML by hand — the CLI does the manifest write and flag
  flip. If you want to edit the resulting manifest (e.g., expand the
  description), do that as a separate post-`/release` edit.
- Do NOT push anything. `/release` is local-only.
- Do NOT call other CLI commands or agents. This is a thin wrapper.
