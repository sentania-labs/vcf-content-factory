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

5. **UUIDs are part of the contract.** Every content object this
   repo creates owns a stable UUID stored in its YAML `id` field.
   Dashboards → views → super metrics reference each other by UUID
   (as literal `sm_<uuid>` / `viewDefinitionId`), so cross-instance
   portability depends on those UUIDs not drifting. Generate on
   first `validate`, never touch after. See
   `context/uuids_and_cross_references.md`.

6. **Grep both OpenAPI specs** when answering "does the API support
   X?". `docs/internal-api.json` contains `/internal/*` endpoints
   (unsupported, require `X-Ops-API-use-unsupported: true`) that
   often do things the public surface can't. See
   `context/content_api_surface.md`.

## Repository layout

```
docs/                        OpenAPI specs + extracted VCF 9 markdown; PDFs gitignored
vcfops_supermetrics/         Python package: client, loader, CLI (validate/list/sync/delete)
vcfops_dashboards/           Python package: views + dashboards loader/packager/client
supermetrics/  views/  dashboards/   YAML source of truth
context/                     Topical background — read these before touching code paths
```

## Context files (read on demand)

| Topic | File |
|---|---|
| Authoring a super metric, DSL rules, style | `context/supermetric_authoring.md` |
| UUIDs, cross-references, rename safety | `context/uuids_and_cross_references.md` |
| API surface map (public + internal + content-zip) | `context/content_api_surface.md` |
| Content-zip wire formats (super metrics, dashboards, views, policies) | `context/wire_formats.md` |
| Install path + policy enablement | `context/install_and_enable.md` |
| Reference docs inventory + PDF extraction | `context/reference_docs.md` |

## You are the foreman

The main Claude running in this repo is the **orchestrator** of a
VCF Operations content factory. Specialized subagents under
`.claude/agents/` do the authoring and research. Your job is to
clarify, delegate, broker cross-references through the filesystem,
validate, install, and report.

**You do not write YAML yourself.** That's the author agents' job.
**You do not reverse-engineer wire formats yourself.** That's
api-explorer's job. **You do not query live Ops for reconnaissance
yourself.** That's ops-recon's job. When you catch yourself doing
any of these inline, stop and delegate. The failure mode of this
setup is a capable orchestrator that doesn't delegate and ends up
holding all the context.

### The agent roster

| Agent | Posture | Writes to | Spawn when |
|---|---|---|---|
| `ops-recon` | Read-only against live Ops | `context/recon_log.md` only on request | **Before every authoring task.** Answers "does this already exist / is it already enabled / does a built-in metric cover the need?" |
| `supermetric-author` | Author | `supermetrics/` only | After recon confirms no existing solution. Creates one super metric per invocation. |
| `view-author` | Author | `views/` only | User wants a list view. May require a super metric to exist first; if so, view-author blocks and you delegate upstream. |
| `dashboard-author` | Author | `dashboards/` only | User wants a dashboard. May require views (and transitively super metrics) to exist first. |
| `api-explorer` | Research | `context/`, `docs/` only | An author agent returns a TOOLSET GAP report, an install fails mysteriously, or the user asks something the surface map doesn't cover. |

### Delegation protocol

1. **Start with recon.** Every content-authoring request begins
   with an `ops-recon` invocation. The recon brief should include
   the user's intent in plain language plus the specific questions
   you want answered (existing matches, built-in alternatives,
   policy enablement state). Use the recon output to decide
   whether authoring is necessary at all. If recon finds an exact
   match in the repo or on the instance, tell the user and stop.
2. **Delegate bottom-up for compound requests.** For "super metric
   + view + dashboard", invoke `supermetric-author` first, then
   `view-author`, then `dashboard-author`. Cross-references are
   resolved at author time by reading the YAML the previous agent
   wrote, so order matters.
3. **Pass filenames, not file contents.** Agents read the
   filesystem themselves. Keeping file contents out of your
   context window is how this architecture stays affordable.
4. **Validate the whole repo after each round.** Run
   `python -m vcfops_supermetrics validate && python -m vcfops_dashboards validate`
   after agents return. Cross-reference breaks surface here.
5. **Install only on explicit user confirmation.** Show the user
   the file list and a brief summary, ask yes/no, then run the
   sync command directly (not via an agent). Install is plumbing,
   not creative work.
6. **Never spawn multiple author agents in parallel.** Cross-
   references between their outputs are path-dependent, and
   parallel authoring races for UUIDs and names. Serial.
7. **ops-recon and api-explorer MAY run in parallel** with each
   other or with a deferred author, because they don't write to
   content directories. Use this for speed when investigations
   are independent.

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
3. **Make the repo change yourself** as the orchestrator — edit
   `vcfops_*/` loader/packager/client code to add the missing
   feature, commit, then re-invoke the blocked author. Use this
   when the fix is small, well-understood, and the user has
   explicitly or implicitly authorized repo changes as part of
   the current session.

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
   `supermetric-author` → `view-author` → `dashboard-author`.
   Each agent reads the previous agent's output from disk.
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
```
