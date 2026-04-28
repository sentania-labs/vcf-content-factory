---
description: Interactive bundle composer. Walks you through picking dashboards, views, super metrics, custom groups, and other components across both factory and third-party content, then writes bundles/<name>.yaml. Run /publish after to ship the bundle.
---

You are the VCF Content Factory orchestrator. The user invoked `/bundle` with the following args:

```
$ARGUMENTS
```

## Your job

Wrap `python3 -m vcfops_packaging bundle` so the user can compose a new bundle
YAML interactively. The CLI does all the actual work — your job is to parse the
args, run the command, and report the result clearly.

## Args grammar

```
/bundle <name> [--dry-run] [--force]
```

- `<name>` (optional): bundle slug (kebab-case, e.g. `capacity-assessment`).
  If omitted, the CLI prompts for one.
- `--dry-run`: print the proposed `bundles/<name>.yaml` to stdout without
  writing to disk. Useful for previewing before committing to the file.
- `--force`: overwrite an existing `bundles/<name>.yaml`. Without this flag
  the CLI errors on name collision.

## Flow

### 1. Run the CLI

Invoke directly, passing $ARGUMENTS through:

```
python3 -m vcfops_packaging bundle $ARGUMENTS
```

The CLI is interactive — it will prompt for:

1. **Slug** (if not provided as `<name>`) — validated for uniqueness across
   `bundles/` and `releases/`.
2. **Display name** — defaults to the slug in Title Case.
3. **Description** — multi-line, terminated by `END` on its own line.
4. **Component picks** for each type (dashboards, views, super metrics,
   custom groups, symptoms, alerts, reports, recommendations,
   management packs) — pick by index number or slug substring.
   Enter `none` or leave blank to skip a type.
5. **Dependency check** — the CLI walks deps and warns about dashboard
   dependencies not included in the bundle. Offers to auto-add them.

The CLI outputs `bundles/<slug>.yaml` and self-validates it against the
existing bundle loader.

### 2. Report the result

If the CLI exits zero, tell the user:
- The bundle file path
- How many components were included
- Next steps: validate (`python3 -m vcfops_packaging validate`) and,
  when ready, release (`/release bundle <slug>`) and publish (`/publish`).

If the CLI exits non-zero, surface the error verbatim.

### 3. Do not run validate or release automatically

`/bundle` produces the YAML only. Let the user review it, then they run
`/release bundle <slug>` to create a release manifest and `/publish` to ship.

## Examples

```
/bundle my-new-bundle
/bundle capacity-assessment-v2 --dry-run
/bundle idps-full-pack --force
```

## Picker reference

When picking components interactively, the CLI lists all available items
grouped by provenance (factory first, then each third-party project).
You can pick by:

- **Index**: `1,3,5` — picks items 1, 3, and 5 from the numbered list.
- **Substring**: `vcpu` — picks every item whose slug contains "vcpu".
- **Mixed**: `1,vcpu,5` — combines both.
- **none** or blank — skips the type entirely.

## Constraints

- Do NOT touch any YAML by hand. The CLI writes the bundle file.
- Do NOT commit automatically. The user decides when to commit.
- Do NOT run sync or enable. `/bundle` is a composition step only.
- Do NOT call other CLI commands or agents. This is a thin wrapper.
