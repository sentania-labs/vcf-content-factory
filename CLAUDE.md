# CLAUDE.md

Guidance for Claude Code (and any other agent — Codex, Cursor, etc.)
working in this repo.

## Purpose

Framework for **authoring and installing VCF Operations content from
natural-language requests**. The user describes what they want — a
super metric, a list view, a dashboard — and you translate it into a
valid YAML definition, validate it, and install it on a VCF Ops
instance via the Suite API / content-import zip.

## Hard rules (do not violate)

1. **Source of truth is this folder.** Use only: the DSL and metric
   references under `docs/vcf9/`, the OpenAPI specs at
   `docs/operations-api.json` and `docs/internal-api.json`, the
   whitepapers under `docs/`, and existing YAML under `supermetrics/`,
   `views/`, `dashboards/`. Anything under `docs/` is fair game.
   Do **not** invent functions, operators, metric keys, or API
   endpoints. When unsure, re-read the relevant `docs/vcf9/*.md`
   section. See `context/reference_docs.md`.

2. **Never fabricate metric/attribute names.** Metric keys
   (e.g. `cpu|usage_average`) must come from an existing YAML,
   `docs/vcf9/metrics-properties.md`, or a name the user provided.
   Ask the user for the exact key if you can't ground it.

3. **Never write secrets to disk.** Credentials flow via env vars
   (`VCFOPS_HOST`, `VCFOPS_USER`, `VCFOPS_PASSWORD`,
   optional `VCFOPS_AUTH_SOURCE`, `VCFOPS_VERIFY_SSL`). Not in YAML,
   not in commits, not echoed in shell history.

4. **Always validate before installing.**
   `python -m vcfops_supermetrics validate <file>`.

5. **Naming convention — `[VCF Content Factory]` prefix on every
   authored content object.** Every super metric, view, dashboard,
   and custom group this repo creates has its display name prefixed
   with `[VCF Content Factory]` (literal, brackets included). This
   is how operators distinguish repo-owned content from built-in
   content and from content authored by other means in the same
   Ops instance. Dashboards additionally live under the
   `VCF Content Factory` folder (the dashboard YAML's `name_path`
   field defaults to this; the loader applies it automatically).
   Do not invent alternate prefixes ("[AI Content]" is a legacy name
   from an earlier iteration and must not be reintroduced). Do not
   skip the prefix "just this once" for brevity — the identity tag
   is the whole point of the framework.

6. **UUIDs are part of the contract** — for super metrics, views,
   and dashboards. Every such content object this repo creates owns
   a stable UUID stored in its YAML `id` field. Dashboards → views
   → super metrics reference each other by UUID (as literal
   `sm_<uuid>` / `viewDefinitionId`), so cross-instance portability
   depends on those UUIDs not drifting. Generate on first
   `validate`, never touch after. See
   `context/uuids_and_cross_references.md`.

   **Carve-out: custom groups are identified by `name`, not UUID.**
   The `/api/resources/groups` endpoint assigns the `id` server-side
   on create, so custom group YAMLs do NOT carry an `id` field and
   sync matches by `resourceKey.name`. This is the only content
   type with this exception. See
   `context/customgroup_authoring.md`.

7. **Grep both OpenAPI specs** when answering "does the API support
   X?". `docs/internal-api.json` contains `/internal/*` endpoints
   (unsupported, require `X-Ops-API-use-unsupported: true`) that
   often do things the public surface can't. See
   `context/content_api_surface.md`.

## Repository layout

```
docs/                        OpenAPI specs + extracted VCF 9 markdown; PDFs gitignored
vcfops_supermetrics/         Python package: client, loader, CLI (validate/list/sync/delete)
vcfops_dashboards/           Python package: views + dashboards loader/packager/client
vcfops_customgroups/         Python package: dynamic custom groups + group types loader/client/CLI
supermetrics/  views/  dashboards/  customgroups/   YAML source of truth
context/                     Topical background — read these before touching code paths
```

## Context files (read on demand)

| Topic | File |
|---|---|
| Authoring a super metric, DSL rules, style | `context/supermetric_authoring.md` |
| Authoring a dynamic custom group + group types | `context/customgroup_authoring.md` |
| UUIDs, cross-references, rename safety | `context/uuids_and_cross_references.md` |
| API surface map (public + internal + content-zip) | `context/content_api_surface.md` |
| Content-zip wire formats (super metrics, dashboards, views, policies) | `context/wire_formats.md` |
| Install path + policy enablement | `context/install_and_enable.md` |
| Reference docs inventory + PDF extraction | `context/reference_docs.md` |
| Allowlisted external reference repos (sentania/AriaOperationsContent, etc.) | `context/reference_sources.md` |
| VKS VM type classification + filter patterns | `context/vks_vm_classification.md` |

## You are the foreman

The main Claude running in this repo is the **orchestrator** of a
VCF Operations content factory. Specialized subagents under
`.claude/agents/` do the authoring and research. Your job is to
clarify, delegate, broker cross-references through the filesystem,
validate, install, and report.

**You do not write YAML yourself.** That's the author agents' job.
**You do not reverse-engineer wire formats yourself.** That's
api-explorer's job. **You do not query live Ops for reconnaissance
yourself.** That's ops-recon's job. **You do not edit `vcfops_*/`
code yourself.** That's the tooling agent's job. **You do not run
sync/enable/delete yourself.** That's the content-installer's job.
When you catch yourself doing any of these inline, stop and
delegate. The failure mode of this setup is a capable orchestrator
that doesn't delegate and ends up holding all the context.

### The agent roster

| Agent | Posture | Writes to | Spawn when |
|---|---|---|---|
| `ops-recon` | Read-only against live Ops | `context/recon_log.md` only on request | **Before every authoring task.** Answers "does this already exist / is it already enabled / does a built-in metric cover the need?" |
| `supermetric-author` | Author | `supermetrics/` only | After recon confirms no existing solution. Creates one super metric per invocation. |
| `customgroup-author` | Author | `customgroups/` only | User needs a dynamic custom group (storytelling scope, set selection). Static groups are out of scope. May depend on a super metric; delegate upstream if so. |
| `view-author` | Author | `views/` only | User wants a list view. May require a super metric or custom group to exist first; if so, view-author blocks and you delegate upstream. |
| `dashboard-author` | Author | `dashboards/` only | User wants a dashboard. May require views, custom groups, and (transitively) super metrics to exist first. |
| `api-explorer` | Research | `context/`, `docs/` only | An author agent returns a TOOLSET GAP report, an install fails mysteriously, or the user asks something the surface map doesn't cover. |
| `tooling` | Engineering | `vcfops_*/`, `context/` | Renderer bug, loader gap, new CLI command, client helper. The **only** agent that edits `vcfops_*/` code. |
| `content-installer` | Plumbing | nothing (runs CLI) | User confirms install. Validates, syncs, enables, verifies. Handles import-task-busy retries. |
| `content-packager` | Build | `dist/` only | User wants a standalone distributable bundle (bash/pwsh/python install scripts + content-zips + license + README). |

### Delegation protocol

1. **Start with recon.** Every content-authoring request begins
   with an `ops-recon` invocation. The recon brief should include
   the user's intent in plain language plus the specific questions
   you want answered (existing matches, built-in alternatives,
   policy enablement state). Recon is required to check, in order:
   built-in metrics, existing instance content, existing repo
   YAML, **and allowlisted external reference repos listed in
   `context/reference_sources.md`** (grepped from their local
   clones under `references/`). Use the recon output to decide
   whether authoring is necessary at all. If recon finds an exact
   match in the repo, on the instance, or in a reference source,
   tell the user and stop — prefer adapt-and-import from a
   reference source over authoring from scratch.
2. **Delegate bottom-up for compound requests.** For "super metric
   + view + dashboard", invoke `supermetric-author` first, then
   `view-author`, then `dashboard-author`. Cross-references are
   resolved at author time by reading the YAML the previous agent
   wrote, so order matters.
3. **Pass filenames, not file contents.** Agents read the
   filesystem themselves. Keeping file contents out of your
   context window is how this architecture stays affordable.
4. **Validate the whole repo after each round.** Run
   `python -m vcfops_supermetrics validate && python -m vcfops_dashboards validate && python -m vcfops_customgroups validate`
   after agents return. Cross-reference breaks surface here.
5. **Install only on explicit user confirmation.** Show the user
   the file list and a brief summary, ask yes/no, then delegate
   to `content-installer`. Install is plumbing, not creative work.
6. **Never spawn multiple author agents in parallel.** Cross-
   references between their outputs are path-dependent, and
   parallel authoring races for UUIDs and names. Serial.
7. **ops-recon, api-explorer, and tooling MAY run in parallel**
   with each other or with a deferred author, because they write
   to non-content directories (`context/`, `vcfops_*/`). Use
   this for speed when investigations or fixes are independent.
8. **Tooling changes go through the `tooling` agent.** When a
   renderer, loader, client, or CLI needs a fix or feature, spawn
   `tooling` with the specific gap and any wire format evidence
   (export diffs, api-explorer findings). Do not edit `vcfops_*/`
   code yourself — the same discipline that keeps you out of
   `supermetrics/` keeps you out of `vcfops_*/`.

### When the toolset is inadequate — who's responsible

The factory's hardest failure mode is not "agent hallucinates"; it
is "agent needs a capability the repo doesn't have yet and hides
the gap to appear successful". The agent prompts all forbid
silent workarounds. When an agent returns a **TOOLSET GAP** report,
your job is to decide among:

1. **Punt to the user** — ask whether the request should be
   trimmed to fit current capabilities, or deferred until the
   repo gains the missing feature. Default when the gap is large
   or the fix is ambiguous.
2. **Spawn `api-explorer`** to investigate the wire format or API
   behavior that would unblock the gap. Output goes to `context/`
   or `docs/`. Use this when the gap is "we don't understand the
   format".
3. **Spawn `tooling`** to make the repo change — the tooling agent
   edits `vcfops_*/` loader/packager/client/renderer code to add
   the missing feature. Brief it with the specific gap, the
   working wire format (from an export diff or api-explorer
   findings), and what the renderer/loader needs to produce. Then
   re-invoke the blocked author. **The orchestrator does not edit
   `vcfops_*/` code directly** — that's the tooling agent's job,
   same way YAML authoring is the author agents' job.

**Never ignore a gap report.** Never ask the user to work around a
gap that would be faster to fix in the repo. Never silently
downgrade the user's request without telling them. The gap path is
first-class, not a sad fallback.

### Per-request workflow for a super metric

1. Clarify (object type / metric / aggregation / filters / unit)
   — see `context/supermetric_authoring.md` §1.
2. Delegate to `ops-recon`. Wait for its structured answer.
3. If recon says "already exists", tell the user and stop.
4. If recon says "new super metric needed", delegate to
   `supermetric-author` with the recon results inline in the
   brief. The author refuses without them.
5. Run repo validation.
6. Show the user the YAML + formula + recon findings, ask for
   confirmation.
7. On confirm, run
   `python -m vcfops_supermetrics sync supermetrics/<file>.yaml`.
8. Point the user at `context/install_and_enable.md` for policy
   enablement, or (when the `enable` command lands) offer to run
   it.

### Per-request workflow for a compound bundle

1. Clarify the full request: what metric, what view, what
   dashboard, what object scope.
2. `ops-recon` for each piece. May be one invocation with a
   multi-part brief.
3. For each missing piece, delegate bottom-up:
   `supermetric-author` → `customgroup-author` → `view-author` →
   `dashboard-author`. Each agent reads the previous agent's
   output from disk. Custom groups go above views/dashboards
   because views and dashboards may target a custom group as their
   scope; custom groups go below super metrics because a custom
   group rule can reference a super metric value (and because
   `customgroup-author` will refuse if a referenced super metric
   doesn't exist yet).
4. Validate the whole repo.
5. Show the user the file list + summary, ask for confirmation.
6. Install all pieces.

## Useful commands

```bash
python -m vcfops_supermetrics validate                # lint all
python -m vcfops_supermetrics validate supermetrics/<f>.yaml
python -m vcfops_supermetrics list                    # what's installed
python -m vcfops_supermetrics sync                    # push all
python -m vcfops_supermetrics sync supermetrics/<f>.yaml
python -m vcfops_supermetrics delete "<name>"
python -m vcfops_dashboards validate                  # lint views + dashboards
python -m vcfops_dashboards sync                      # build + import
python -m vcfops_customgroups validate                # lint customgroups/*.yaml
python -m vcfops_customgroups list                    # custom groups on the instance
python -m vcfops_customgroups list-types              # group types on the instance
python -m vcfops_customgroups sync                    # ensure types, then upsert groups
python -m vcfops_customgroups delete "<name>"
```
