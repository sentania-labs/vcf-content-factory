# CLAUDE.md

Guidance for Claude Code (and any other agent — Codex, Cursor, etc.)
working in this repo.

## Knowledge precedence (read in this order)

1. `rules/INDEX.md` — Absolute. Obey without question.
2. `lessons/INDEX.md` — Hard-won lessons. Read before going
   down a path that looks obvious. If a lesson covers your
   situation, heed it.
3. `context/README.md` — Documentation and specs. Reference
   when doing work.
4. `references/` — Known-good examples. Grep when authoring.
5. `docs/` — Immutable vendor source material. Read-only.
6. `Memory.md` + `memory/` — Soul + per-user state. Advisory.

If a context file contradicts a rule, the rule wins.
If a lesson says a path is a dead end, don't take it.
Rules are not negotiable.

## The framework is the product

This repo is a framework any VCF Operations admin can clone and
drive in English. Tooling, agents, skills, CLIs, and context files
are all part of the deliverable.

- **Portability is non-negotiable.** Anything that depends on this
  machine, this user's memory, or this dev environment is a bug.
- **Reviewability matters.** All persistent knowledge lives in the
  repo where it can be diffed and PR'd. Auto-memory is off.
- **Codify, don't accumulate.** Hard-won lessons go in `lessons/`,
  `context/`, agent prompts, or skills. See `context/authoring/guide_codification.md`
  for how. The framework should get smarter over time.

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
| `ops-recon` | Read-only against live Ops | `context/investigations/recon_log.md` on request | **Before every authoring task.** Does this exist? Is it enabled? Does a built-in cover it? |
| `supermetric-author` | Author | `content/supermetrics/` | After recon. One SM per invocation. |
| `customgroup-author` | Author | `content/customgroups/` | User needs a dynamic group. Static is out of scope. |
| `view-author` | Author | `content/views/` | User wants a list view. Blocks if upstream SM/group missing. |
| `dashboard-author` | Author | `content/dashboards/` | User wants a dashboard. Blocks if upstream views missing. |
| `symptom-author` | Author | `content/symptoms/` | After recon confirms no existing symptom fits. |
| `alert-author` | Author | `content/alerts/`, `content/recommendations/` | After recon, **and** required symptoms exist. |
| `report-author` | Author | `content/reports/` | User wants a report. Blocks if upstream views missing. |
| `api-explorer` | Research | `context/`, `docs/` | Author returns TOOLSET GAP, install fails mysteriously, surface map gap. |
| `tooling` | Engineering | `vcfops_*/`, `context/` | Renderer/loader/CLI fix or new package bootstrap. **Only** agent that edits `vcfops_*/`. |
| `content-installer` | Plumbing | nothing (runs CLI) | User confirms install. |
| `content-packager` | Build | `bundles/`, `dist/` | Authors bundle manifests in `bundles/`; builds distributable zips into `dist/`. Rebuild after a tooling change. |
| `qa-tester` | Testing | `/tmp/` | Acceptance-test a built zip. Spawn after `content-packager`. |
| `api-cartographer` | Research | `context/api-maps/`, `docs/` | New external API for an MP. |
| `mp-designer` | Design | `designs/` | New MP. Wizard interview against API map. |
| `mp-author` | Author | `content/managementpacks/` | After `mp-designer` produces approved design. **Tier 1** MPB YAML spec. |
| `sdk-adapter-author` | Author/Engineering | `content/sdk-adapters/` (each an independent repo, gitignored) | After `mp-designer` produces approved design. **Tier 2** Java SDK adapter source. The Java sibling to `mp-author`. **Only** agent that edits adapter Java. Commits go to the pak's **own** remote; a real release is a `v*` tag on that repo, not a factory `/publish`. |
| `sdk-adapter-reviewer` | Read-only review | `context/reviews/` | After `sdk-adapter-author` reports a build, before the install gate. Skeptical correctness/quality check on Tier 2 Java — hunts unreadable-is-compliant, stitch corruption, crash-the-cycle. Never edits source, never installs. |
| `framework-reviewer` | Read-only review | `context/reviews/framework/` | After `tooling` touches `vcfops_*/`, **before the PR**. Skeptical correctness/regression gate on framework Python — the `vcfops_*/` sibling of `sdk-adapter-reviewer`. **Blanket:** every `vcfops_*/` diff. Re-runs validate/tests/render-regression; hunts global-default-leak / key-collision / silent-downgrade. Never edits source, never installs. |
| `curator` | Read-only audit | `context/curation/<date>-report.md` | When the SessionStart staleness hook says curation is due (or on request). Librarian over the governance corpus (rules/, lessons/, context/, `.claude/agents/`, CLAUDE.md, skills) — hunts SUPERSEDED / DRIFT / CONTRADICTION / INDEX-ROT / DEAD-REF / STALE-FACT / DUPLICATION / PROMPT-ROSTER-SKEW. Reports only; never edits the corpus, never installs. Spawn **in the background**. |

Agent prompts under `.claude/agents/` are authoritative for each
agent's behavior. If "Spawn when" above ever conflicts with a
prompt, the prompt wins.

## Delegation protocol

This is the spine of the orchestrator's job. It belongs in this
file (not a skill) because it runs before any skill could load.

0. **Check rules and lessons.** Before planning any work, read
   `rules/INDEX.md`. If any rule applies to the current request,
   follow it — do not propose alternatives. Then scan
   `lessons/INDEX.md` — if a lesson covers your situation, heed
   it before committing to a path. Only proceed to recon after
   confirming no rule blocks or redirects the request.

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

   **For dashboards specifically (RULE-011):** before spawning
   `dashboard-author`, enter plan mode and present an ASCII / markdown-
   table wireframe of the proposed layout. Get explicit user approval.
   Commit the wireframe to `designs/dashboards/<slug>.md`. Only then
   delegate. Skipping this step is how layout problems escape to install
   — see `rules/wireframe-before-dashboard.md`.

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

9. **Tooling changes go through the `tooling` agent, then the
   `framework-reviewer` gate.** The same discipline that keeps you
   out of `supermetrics/` keeps you out of `vcfops_*/`. And the same
   discipline that gives Tier 2 Java a skeptical review before it
   ships gives framework Python one too: after `tooling` reports a
   `vcfops_*/` change and **before you open the PR**, spawn
   `framework-reviewer`. Scope is **blanket** — every `vcfops_*/`
   diff, no exceptions. A **CHANGES REQUESTED** verdict (≥1 BLOCKING)
   blocks the PR; re-brief `tooling` and re-review until APPROVE. This
   is the framework-code sibling of the `sdk-adapter-reviewer` gate
   (RULE-013). The framework is the product — it gets at least the
   protection the content does.

10. **Curation trigger — heed the staleness nudge.** The SessionStart
    hook `scripts/curation_staleness_check.sh` emits a "CURATION DUE"
    `additionalContext` when the governance corpus is overdue
    (`last_run > 7 days` OR `sessions_since > 10`). When you see it:
    spawn the `curator` agent **in the background** (read-only; it writes
    `context/curation/<date>-report.md`) and tell the user it's running —
    do not block their current task. When the curator completes, **reset
    the marker**: set `context/curation/.last-run`'s `last_run` to today
    and zero `context/curation/.sessions-since`. The hook only informs;
    it never launches the agent — that's your job. The corpus growing is
    the product, so its rot is a product defect; the curator is how it
    gets caught. (Design: `designs/curator-v1.md`.)

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
  `context/mpb/mpb_pak_structural_reference.md`.
- **Management pack (Tier 2 Java SDK):** clarify target API →
  cartographer → designer → **`sdk-adapter-author`** (not `mp-author`;
  Tier 2 is Java source, not MPB YAML) → `validate-sdk` (cheap loop) →
  `build-sdk` → **`sdk-adapter-reviewer`** (read-only correctness/quality
  gate on the Java — APPROVE / CHANGES REQUESTED; re-brief the author on
  any BLOCKING) → `pak-compare` against closest reference (zero BLOCKING
  is the gate) → confirm → install. There is no render-export /
  push-design / MPB UI Verify step — those are Tier 1 (YAML descriptor)
  only. The cheap loop here is `validate-sdk` (compile-check); the
  expensive loop is the pak build + install cycle. Same discipline:
  exhaust `validate-sdk` before building a pak. The compliance adapter
  (`content/sdk-adapters/compliance/`) is the reference implementation.
  **SDK paks are not stored in this repo.** Each adapter is its own
  independent git repo (in the `sentania-labs` org, named
  `vcf-content-factory-sdk-<name>`), cloned into the gitignored
  `content/sdk-adapters/<name>/` by `scripts/bootstrap_managed_paks.sh`
  from the `context/managed_paks.md` registry. Authoring/validate/review
  happen in-tree exactly as above and `build-sdk` is still the local dev
  preview — but the **official** release is the pak's own CI building the
  `.pak` on a `v*` git tag (no agent, no factory checkout: a runner pulls
  the published `sdk-buildkit` tarball and runs it). **Before any v\* tag
  is pushed, `python3 -m vcfops_packaging defect-gate --pak <name>` must
  pass** — an open blocking defect in `context/defects.md` refuses the
  release (RULE-012, `rules/release-gate-defects.md`). A factory `/publish`
  that references an SDK pak emits a **pointer** to that pak's latest
  GitHub Release, never a built/mirrored binary. New pak = instantiate the
  `…-sdk-template` repo + add one line to `context/managed_paks.md`.
- **Toolset gap:** punt / api-explorer / tooling → fix → re-invoke.
- **Framework changes (`vcfops_*/`):** tooling → **`framework-reviewer`**
  (blanket, every diff; CHANGES REQUESTED blocks the PR — RULE-013) →
  open PR. The pre-PR, factory-owned regression gate; complements Codex's
  post-PR pass, does not replace it.
- **After tooling changes:** if `tooling` modifies anything in
  `vcfops_packaging/templates/`, `vcfops_packaging/builder.py`, or
  `vcfops_dashboards/render.py`, **all distribution zips are
  stale.** Delegate to `content-packager` to rebuild every manifest
  in `bundles/`. Not optional — shipping stale zips is how
  false-positive bugs escape to users.

## Cross-reference syntax

| From → To | YAML | Resolved |
|---|---|---|
| SM formula → SM | `@supermetric:"<name>"` | validate (→ `sm_<uuid>`) |
| View column → SM | `supermetric:"<name>"` in `attribute:` | validate (→ `sm_<uuid>`) |
| Dashboard → View | `view: "<name>"` | validate (→ view UUID) |
| Alert → Symptom | `name: "<name>"` in symptom set | sync (→ symptom ID) |
| Alert → Recommendation | `name: "<name>"` + `priority` | validate (→ rec ID) |
| Report → View / Dashboard | `view:` / `dashboard:` | validate (→ UUID) |

## Reference material

Read `context/README.md` for the tiered index of all context files.
Scan it at session start — it costs almost nothing and prevents
re-deriving known knowledge.

## User context

Primary user is a VCF Ops SME, direct feedback style. The framework
exists to combine domain knowledge with Claude's scaling — codify
corrections so they compound across sessions and across users who
clone the repo.