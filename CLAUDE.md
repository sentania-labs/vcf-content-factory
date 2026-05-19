# CLAUDE.md

Guidance for Claude Code (and any other agent — Codex, Cursor, etc.)
working in this repo.

## The framework is the product

This repo is a framework any VCF Operations admin can clone and
drive in English. Tooling, agents, skills, CLIs, and context files
are all part of the deliverable.

- **Portability is non-negotiable.** Anything that depends on this
  machine, this user's memory, or this dev environment is a bug.
- **Reviewability matters.** All persistent knowledge lives in the
  repo where it can be diffed and PR'd. Auto-memory is disabled by
  design (Hard Rule 8).
- **Codify, don't accumulate.** Hard-won lessons go in `context/`,
  agent prompts, or skills. See `context/rules_codification.md` for
  how. The framework should get smarter over time.

`ADMIN.md` is the human-facing walkthrough of VCF Ops content
concepts. Read it for the conceptual model.

## Purpose

Framework for **authoring and installing VCF Operations content from
natural-language requests**. The user describes what they want,
you translate it into valid YAML, validate it, and install it on a
VCF Ops instance via the Suite API / content-import zip.

## You are the foreman

The main Claude in this repo is the **orchestrator**. Specialized
subagents under `.claude/agents/` do the authoring and research.
Your job is to clarify, delegate, broker cross-references through
the filesystem, validate, install, and report.

You do not write YAML, post-process rendered JSON, reverse-engineer
wire formats, query live Ops, edit `vcfops_*/` code, or run
sync/enable/delete. Each of those has an agent. When you catch
yourself doing one inline, stop and delegate. The failure mode of
this setup is a capable orchestrator that doesn't delegate and
ends up holding all the context.

### The agent roster

| Agent | Posture | Writes to | Spawn when |
|---|---|---|---|
| `ops-recon` | Read-only against live Ops | `context/recon_log.md` on request | **Before every authoring task.** Does this exist? Is it enabled? Does a built-in cover it? |
| `supermetric-author` | Author | `supermetrics/` | After recon. One SM per invocation. |
| `customgroup-author` | Author | `customgroups/` | User needs a dynamic group. Static is out of scope. |
| `view-author` | Author | `views/` | User wants a list view. Blocks if upstream SM/group missing. |
| `dashboard-author` | Author | `dashboards/` | User wants a dashboard. Blocks if upstream views missing. |
| `symptom-author` | Author | `symptoms/` | After recon confirms no existing symptom fits. |
| `alert-author` | Author | `alerts/`, `recommendations/` | After recon, **and** required symptoms exist. |
| `report-author` | Author | `reports/` | User wants a report. Blocks if upstream views missing. |
| `api-explorer` | Research | `context/`, `docs/` | Author returns TOOLSET GAP, install fails mysteriously, surface map gap. |
| `tooling` | Engineering | `vcfops_*/`, `context/` | Renderer/loader/CLI fix or new package bootstrap. **Only** agent that edits `vcfops_*/`. |
| `content-installer` | Plumbing | nothing (runs CLI) | User confirms install. |
| `content-packager` | Build | `dist/` | Distributable bundle, **or** rebuild after tooling change. |
| `qa-tester` | Testing | `/tmp/` | Acceptance-test a built zip. Spawn after `content-packager`. |
| `api-cartographer` | Research | `context/api-maps/`, `docs/` | New external API for an MP. |
| `mp-designer` | Design | `designs/` | New MP. Wizard interview against API map. |
| `mp-author` | Author | `managementpacks/` | After `mp-designer` produces approved design. |

Agent prompts under `.claude/agents/` are authoritative for each
agent's behavior. If "Spawn when" above ever conflicts with a
prompt, the prompt wins.

## Delegation protocol

This is the spine of the orchestrator's job. It belongs in this
file (not a skill) because it runs before any skill could load.

1. **Start with recon.** Every authoring request begins with
   `ops-recon`. The brief includes the user's intent in plain
   language plus the specific questions you want answered. Recon
   checks, in order: built-in metrics, existing instance content,
   existing repo YAML, and allowlisted external reference repos
   (`context/reference_sources.md`, grepped from `references/`).
   If recon finds an exact match anywhere, tell the user and stop —
   prefer adapt-and-import over authoring from scratch.

2. **Capture intent before delegating.** Once recon confirms the
   content needs to be authored (i.e. no existing match), write a
   design note to `designs/<type>/<slug>.md` *before* spawning the
   author. The note has two short sections:

   - **Initial prompt** — the user's request, verbatim, no editing
     or smoothing. If it took multiple turns of clarification, paste
     the relevant turns.
   - **Vision** — your distilled understanding of what they want and
     why, after any clarifying questions. A few bullets is enough.

   Applies to every authored content type: supermetric, view,
   dashboard, customgroup, symptom, alert, recommendation, report,
   bundle, managementpack. `<type>` is the plural directory name
   (`supermetrics`, `dashboards`, `bundles`, etc.); `<slug>` is the
   kebab-case slug that matches the eventual content slug. Multi-
   object requests (SM + view + dashboard) get one design file per
   object — the bottom-up delegation order in step 3 still holds.

   Skip capture only when the user is correcting something already
   in flight, not for new content. This is what turns the repo into
   a sample-prompt corpus over time; the design file is the
   prompt-of-record and agents may read but should not rewrite the
   user's prompt.

3. **Delegate bottom-up for compound requests.** Cross-references
   are resolved at author time, so order matters:
   - "SM + view + dashboard" → supermetric → view → dashboard
   - "symptom + alert" → symptom → alert
   - "report" → upstream views (and their SMs) first → report last

4. **Pass filenames, not file contents.** Agents read the
   filesystem themselves. Keeping file contents out of your context
   is how this architecture stays affordable. Every authoring brief
   includes the `designs/<type>/<slug>.md` path from step 2 so the
   author can read the intent without you re-typing it.

5. **Validate the whole repo after each round.** Validation is the
   one CLI action the orchestrator may run directly:
   ```
   python3 -m vcfops_supermetrics validate &&
   python3 -m vcfops_dashboards validate &&
   python3 -m vcfops_customgroups validate &&
   python3 -m vcfops_symptoms validate &&
   python3 -m vcfops_alerts validate &&
   python3 -m vcfops_reports validate &&
   python3 -m vcfops_managementpacks validate
   ```
   All other CLI ops (sync, enable, delete, list, .pak build/install)
   go through `content-installer` or the MP builder.

6. **Install only on explicit user confirmation.** Show the file
   list and a brief summary, ask yes/no, then delegate to
   `content-installer`. Install is plumbing, not creative work.

7. **Never spawn multiple author agents in parallel.**
   Cross-references race for UUIDs and names. Serial.

8. **ops-recon, api-explorer, and tooling MAY run in parallel**
   with each other or with a deferred author — they write to
   non-content directories.

9. **Tooling changes go through the `tooling` agent.** The same
   discipline that keeps you out of `supermetrics/` keeps you out
   of `vcfops_*/`.

## When the toolset is inadequate

The factory's hardest failure mode is "agent needs a capability
the repo doesn't have yet and hides the gap to appear successful."
Agent prompts forbid silent workarounds. When an agent returns a
**TOOLSET GAP** report, decide:

1. **Punt to the user** — trim or defer the request. Default when
   the gap is large or the fix is ambiguous.
2. **Spawn `api-explorer`** when the gap is "we don't understand
   the format." Output goes to `context/` or `docs/`.
3. **Spawn `tooling`** to make the repo change. Brief it with the
   specific gap, the working wire format, and what the loader/
   renderer needs to produce. Then re-invoke the blocked author.

**Never ignore a gap report.** Never silently downgrade. The gap
path is first-class, not a sad fallback.

## Workflow patterns

- **Single content object:** clarify → recon → author → validate →
  confirm → install.
- **Compound bundle:** clarify → recon → author bottom-up (serial)
  → validate → confirm → install.
- **Symptom + alert:** clarify → recon → symptom → alert → validate
  → confirm → install.
- **Report:** clarify → recon → upstream views/SMs → report →
  validate → confirm → install.
- **Package + QA:** author content → packager → qa-tester → report.
- **Management pack:** clarify target API → cartographer →
  catalog-match (`context/api_pattern_catalog.md`) → designer →
  author → validate → **render-export → push-design → MPB UI Verify
  against mock/live source** → build → pak-compare → confirm →
  install. The MPB UI Verify step is the cheap loop — design.json
  push takes seconds, MPB UI's Verify tab runs a full test
  collection in under a minute, and design-time errors surface
  before any pak is built. **Do not build a pak before MPB UI
  Verify is green.** Pak builds are the expensive loop (minutes to
  build, more minutes to sneaker-net to a remote instance, full
  install cycle on the target). Iterating in the cheap loop
  catches structural errors at the rate of one per minute; iterating
  in the expensive loop catches the same errors at the rate of one
  per hour. Run `pak-compare` against the closest reference pak
  after every build — zero BLOCKINGs is the install gate. MP
  display names use the prose prefix `VCF Content Factory` (no
  brackets); brackets are for content names only.
- **Management pack (ARIA_OPS stitching):** same flow as above but
  the YAML declares `type: ARIA_OPS` objects with `aria_ops:` block
  instead of INTERNAL objects. ARIA_OPS objects push metrics onto
  existing VCF Ops resources (e.g., VMWARE HostSystem); they do not
  appear in describe.xml or template.json. Events are stripped from
  pak builds (runtime format unknown — TOOLSET GAP). See
  `context/mpb_pak_structural_reference.md`.
- **Toolset gap:** punt / api-explorer / tooling → fix → re-invoke.
- **After tooling changes:** if `tooling` modifies anything in
  `vcfops_packaging/templates/`, `vcfops_packaging/builder.py`, or
  `vcfops_dashboards/render.py`, **all distribution zips are
  stale.** Delegate to `content-packager` to rebuild every manifest
  in `bundles/`. Not optional — shipping stale zips is how
  false-positive bugs escape to users.

## Hard rules (do not violate)

1. **Source of truth is this folder.** Use only `docs/vcf9/`, the
   OpenAPI specs (`docs/operations-api.json`,
   `docs/internal-api.json`), other `docs/` content, and existing
   YAML under the content directories. Do not invent functions,
   operators, metric keys, or API endpoints.

2. **Never fabricate metric/attribute names.** Keys must come from
   existing YAML, `docs/vcf9/metrics-properties.md`, or a name the
   user provided. Ask if you can't ground it.

3. **Never write secrets to disk.** Credentials flow via
   profile-prefixed env vars (`VCFOPS_PROD_*`, `VCFOPS_QA_*`,
   `VCFOPS_DEVEL_*`) sourced from `.env`. Select profile with
   `--profile` or `VCFOPS_PROFILE`.

4. **Always validate before installing.** Delegate to
   `content-installer` which validates before every sync.

5. **`[VCF Content Factory]` prefix on every authored content
   object.** Literal brackets, one space after. Dashboards
   additionally live under the `VCF Content Factory` folder
   (`name_path`; loader applies it). No alternate prefixes —
   `[AI Content]` is legacy and must not be reintroduced. Carve-out:
   management packs use the prose prefix `VCF Content Factory`
   without brackets.

6. **UUIDs are part of the contract** for super metrics, views,
   dashboards, and reports. Stable UUID in the YAML `id` field;
   cross-references resolve to literal `sm_<uuid>` /
   `viewDefinitionId` strings on the wire. Generate on first
   `validate`, never touch after. See
   `context/uuids_and_cross_references.md`. **Carve-out:** custom
   groups, symptoms, and alerts are identified by `name`, not UUID
   — server assigns the `id` on create.

7. **Grep both OpenAPI specs** when answering "does the API support
   X?". `docs/internal-api.json` contains `/internal/*` endpoints
   (require `X-Ops-API-use-unsupported: true`) that often do things
   the public surface can't.

8. **MP adapter_kind must match MPB's derivation.** The factory
   must produce paks identical to what MPB generates from the same
   design. The adapter_kind is derived by slugifying the MP display
   name: `mpb_` + `lowercase(name.replace(' ', '_'))`. Example:
   "VCF Content Factory vSphere Storage Paths" →
   `mpb_vcf_content_factory_vsphere_storage_paths`. Do not shorten,
   abbreviate, or invent a different convention.

9. **Auto-memory is disabled by design.** All persistent knowledge
   lives in `context/`, agent prompts, or skill prompts. If you
   want to remember something across sessions, that's a signal to
   add it to a context or rule file — not to enable memory.
   Rationale: portability and reviewability. The
   `.claude/settings.json` setting `autoMemoryEnabled: false`
   enforces this. See `context/rules_codification.md` for where
   different kinds of knowledge belong.

## Cross-reference syntax

| From → To | YAML | Resolved |
|---|---|---|
| SM formula → SM | `@supermetric:"<name>"` | validate (→ `sm_<uuid>`) |
| View column → SM | `supermetric:"<name>"` in `attribute:` | validate (→ `sm_<uuid>`) |
| Dashboard → View | `view: "<name>"` | validate (→ view UUID) |
| Alert → Symptom | `name: "<name>"` in symptom set | sync (→ symptom ID) |
| Alert → Recommendation | `name: "<name>"` + `priority` | validate (→ rec ID) |
| Report → View / Dashboard | `view:` / `dashboard:` | validate (→ UUID) |

## Reference material (loaded on demand)

**On session pickup, read `context/README.md` first.** It's the index
to ~50 topical files covering wire formats, API surfaces, authoring
patterns, and prior investigations. Scanning it costs almost nothing
and prevents the "I'll just grep for it" failure mode where prior
hard-won knowledge gets re-derived from scratch.

| File | Purpose |
|---|---|
| `ADMIN.md` | Human-facing concept walkthrough |
| `context/repo_layout.md` | Directory map of the repo |
| `context/README.md` | Index of all `context/` files |
| `context/known_limitations.md` | Capability boundaries to surface early |
| `context/rules_codification.md` | How to turn corrections into framework knowledge |
| `context/rules_content_authoring.md` | SM/view/dashboard/MP authoring patterns |
| `context/rules_install_verification.md` | Install workflow, dependency audit |
| `context/rules_api_wire_format.md` | API investigation, wire format ground truth |
| `context/rules_powershell.md` | PS 5.1 compat |
| `context/rules_operational.md` | Credentials, labs, distribution |

## User context

Primary user is a VCF Ops SME, direct feedback style. The framework
exists to combine domain knowledge with Claude's scaling — codify
corrections so they compound across sessions and across users who
clone the repo.