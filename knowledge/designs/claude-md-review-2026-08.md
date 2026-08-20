# CLAUDE.md / AGENTS.md review — Opus 5 / Fable era

Status: ASSESSMENT (no changes made beyond the AGENTS.md symlink)
Date: 2026-08-20
Trigger: Scott, before committing to bootstrap-v2 — "a review of
CLAUDE.md/AGENTS.md is in order given the changes in LLM capabilities
from opus 4.x to Opus 5/fable/sol era models"

## Headline

The file is factually healthy (zero dead paths, 20/20 agent roster
match) but structurally built for a weaker, smaller-context model:
~60-65% of it restates rules, skills, and agent prompts that already
hold the authoritative copy. The cost of that redundancy is no longer
tokens, it is drift.

## Measured state

| Artifact | Words | ~Tokens |
|---|---|---|
| CLAUDE.md | 2,810 | ~5.0k |
| knowledge/rules/ (INDEX + 17 rules) | 3,293 | ~6.1k |
| knowledge/lessons/INDEX.md | 1,077 | ~2.3k |
| knowledge/context/README.md | 1,112 | ~2.2k |
| **Mandatory session-start floor** | **8,292** | **~15.6k** |

Conditional tail: 25 lesson bodies total ~21k tokens, read on demand.

Duplication by section: foreman/roster 622w, delegation protocol 921w,
workflow patterns 679w, cross-reference table 95w, toolset gap 133w.
Genuinely CLAUDE.md-only content is ~600-700 words.

## What changed about the models, and what follows

### 1. Redundancy was a feature; now it is a liability

Opus 4.x-era agent files repeat rules near the point of use because
models drifted over long sessions. Fable 5 / Opus 5 follow long
instructions reliably across a much longer horizon, so restating a rule
a third time buys almost nothing and costs a third copy to keep in
sync. Evidence this is already biting: the cross-reference table exists
in **four** places, the RULE-005 validate chain is copied verbatim into
CLAUDE.md, and the curator has flagged the same stale
`vcfops-orchestration` pointer for **eight consecutive cycles**.

Direction: CLAUDE.md cites, it does not restate. "Validate per
RULE-005" instead of pasting seven commands.

### 2. The token floor matters less than it looks

At 200k context, 15.6k fixed was ~8% of the window and worth fighting.
At 1M it is ~1.5%. **Do not trim CLAUDE.md to save tokens** — that was
the old reason and it has largely expired. Trim it for
single-source-of-truth, which is a maintenance argument and still fully
valid. This distinction matters: it means the goal is fewer *copies*,
not a shorter file, and anything genuinely unique should stay however
long it is.

### 3. Delegation austerity: split the rationale

"Pass filenames, not file contents", "keeping file contents out of your
context is how this architecture stays affordable", "the failure mode
is a capable orchestrator that doesn't delegate" — this is
context-economy reasoning from an era when the orchestrator would
genuinely run out of room.

Two rationales are tangled here and they age differently:

- **Governance** (write-scope isolation, `tooling` is the only agent
  touching `src/vcfops_*/`, review gates, serial spawning to avoid UUID
  races): model-independent, still correct, keep verbatim. The serial
  spawn rule in particular guards a real race, not a model weakness.
- **Context economy** (delegate so the foreman's context survives):
  substantially weakened. A 1M-context orchestrator can hold what it
  used to shed, and subagents now carry a *disadvantage* the old
  framing ignored — they lack the conversation's accumulated context,
  so a reflexive hand-off can produce worse work than doing it inline.

Direction: keep the "you do not write YAML / edit src / query live Ops"
negative list (that is governance), soften the affordability framing,
and say explicitly that delegation exists for write-scope and review
gates first, context second. Worth asking whether 20 agents is still
the right granularity, but that is a bigger question than this review.

### 4. The file predates most of its own harness

- **Skills**: five exist under `.claude/skills/`; CLAUDE.md names
  **zero** of them, referring to "skills" only as an abstract noun.
  Progressive disclosure is exactly the mechanism for the 60% that is
  currently inlined.
- **Slash commands**: `/bundle`, `/extract`, `/publish`, `/release`
  exist and are never enumerated.
- **`src/vcfops_extractor/`**: an entire workflow surface (third-party
  dashboard to factory YAML) absent from the workflow patterns list.
  `src/vcfops_common/` is also unmentioned.
- Plan mode, background agents, and the Workflow tool are all
  post-authorship and unreferenced.

### 5. Defensive prompting is now noise

"Never ignore a gap report. Never silently downgrade. The gap path is
first-class, not a sad fallback." Three sentences to make one point,
plus heavy bold/caps throughout. That cadence was anti-drift
scaffolding for 4.x. One clear statement now lands as well as three,
and the emphasis markup competes with the genuinely load-bearing rules
for attention.

### 6. AGENTS.md symlink and Codex: corrected 2026-08-20

**An earlier draft of this review claimed Codex has no subagents, no
skills, and no hooks, and that ~60% of CLAUDE.md would therefore be
inapplicable to it. That was wrong.** Scott pushed back; verification
against current Codex docs shows near-complete feature parity for
everything CLAUDE.md depends on:

| Capability | Claude Code | Codex |
|---|---|---|
| Project-scoped subagents | `.claude/agents/*.md`, YAML frontmatter + markdown body | `.codex/agents/*.toml`, version-controlled in-repo |
| Personal subagents | user settings | `~/.codex/agents/*.toml` |
| Agent schema | `name`, `description`, `tools` + body | `name`, `description`, `developer_instructions` required; `model`, `model_reasoning_effort`, `sandbox_mode`, `nickname_candidates` optional |
| Skills | `.claude/skills/<name>/SKILL.md` | `.agents/skills/` (project), `~/.agents/skills/` (personal) |
| Project config | `.claude/settings.json` | `.codex/config.toml` |
| Lifecycle hooks | SessionStart, PostToolUse, etc. | SessionStart, SessionEnd, PreToolUse, PostToolUse, PermissionRequest, PreCompact, PostCompact, UserPromptSubmit, SubagentStart, SubagentStop, Stop |
| Concurrency control | orchestrator discipline | `max_threads`, `max_depth` in config.toml |

Codex also treats AGENTS.md as the "constitution" loaded before any
work, which is exactly the role CLAUDE.md plays here. The symlink is
therefore sound, and the delegation architecture is portable rather
than Claude-specific.

**This inverts the recommendation.** The 20 agent prompts are the
repo's real asset, and both harnesses want the same content in
different envelopes. Instead of hiding Claude mechanics from Codex,
generate both:

- Single source of truth for agent definitions (the existing
  `.claude/agents/*.md` bodies, or a neutral intermediate).
- A small generator under `src/vcfops_*/` renders `.codex/agents/*.toml`
  from it: `description` maps to `description`, the markdown body maps
  to `developer_instructions`.
- Same treatment for the five skills (`.claude/skills/` and
  `.agents/skills/`) and for the SessionStart bootstrap hook
  (`.claude/settings.json` and `.codex/config.toml`), which makes
  bootstrap-v2 phase 1 portable to Codex with no redesign.
- CI check that the generated side is not stale, so the two never
  drift. This is a `tooling` job behind the `framework-reviewer` gate.

**One caveat that is load-bearing here.** Tool restrictions do not map
cleanly. Claude Code enforces write-scope with a per-agent `tools:`
allowlist (this is how `tooling` is genuinely the only agent that can
edit `src/vcfops_*/`). Codex offers `sandbox_mode`, which is coarser.
So on the Codex side, write-scope isolation degrades from *enforced* to
*instructed*. Given that write-scope isolation is the backbone of the
governance model, the honest position is that Codex is a supported
second-class harness: the same roster and the same instructions, with
weaker mechanical guarantees. That belongs in the docs rather than
being discovered later.

Structural note: CLAUDE.md should still separate harness-neutral
content from harness mechanics, but for a different reason than the one
originally given. Not because Codex cannot use the mechanics, but
because the mechanics now have two renderings and the shared part
should be written once.

## Real correctness bugs found (fix regardless of the restructure)

1. `.claude/skills/vcfops-project-conventions/SKILL.md` validate chain
   lists **6** commands, missing `vcfops_managementpacks validate`. An
   agent loading the skill and not CLAUDE.md ships unvalidated MP YAML.
2. Same skill's `vcfops-orchestration` back-pointer references a skill
   deleted 2026-05-09 (commit `8e4f13a`). Eight curation cycles stale,
   one-line fix. CLAUDE.md is the correct party.
3. Same skill's naming-prefix section omits the MP prose-prefix
   carve-out, so skill-only readers get the bracket rule wrong.
4. Roster write-scope drift: `tooling` row omits `tests/` (CLAUDE.md
   contradicts itself at :199), `content-packager` is granted `dist/`
   which its prompt never claims, `content-installer` "nothing" is not
   literally true (permitted remote log-level write).
5. `qa-tester` is declared to write `/tmp/` but its tool list has no
   Write or Edit; it can only write via Bash, and this conflicts with
   the harness scratchpad convention.
6. Stale inbound citations: `knowledge/HOW_IT_WORKS.md:153` cites
   "CLAUDE.md Hard Rule 8" (no such numbered section exists);
   `guide_delegation.md` says "the eight numbered rules" when there are
   now eleven (0-10).

## Recommendation

Do a CLAUDE.md v2 pass **before** building bootstrap-v2, because
bootstrap adds a concierge playbook to CLAUDE.md and it should land in
the restructured file, not the old one. Scope:

- Replace duplicated blocks with citations (validate chain, recon
  order, wireframe gate, framework-review gate, curator trigger,
  cross-reference table, TOOLSET GAP).
- Split harness-neutral content from harness mechanics, so the
  mechanics can be rendered twice (Claude Code and Codex) from one
  shared core.
- Name the five skills and four slash commands; add the extractor
  workflow.
- Reframe delegation as governance-first.
- Fix the six correctness items above.
- Target: the unique ~700 words plus citations, roughly half the
  current length, with no unique content lost.

## Agent prompt review (`.claude/agents/`, 20 files, 2,951 lines)

Assessed 2026-08-20, same Opus 5-era lens.

### Headline

Better shape than expected. All 20 files have explicit refusal
conditions, 18/20 declare knowledge sources, and the heavy domain
content is already factored out into skills. **The 4.x-era failure
pattern (long because defensive) is largely absent** — the biggest
files are big because they encode real failure taxonomies with named
provenance, and those earn their length. Zero instances of "think step
by step" anywhere.

So the work is not "strip the emphasis." It is three real defects, one
tool-allowlist gap, a model-routing question, and ~17% mechanical
duplication.

### Confirmed defects (verified against the filesystem)

1. **Stale content-root trap, ~35 lines across 3 files.**
   `dashboard-author.md:11-23`, `view-author.md:11-17`,
   `customgroup-author.md:12-16` warn about repo-root `dashboards/`,
   `views/`, `customgroups/` directories. Verified: **none of the three
   exist.** `dashboard-author.md:20-21` asserts as present-tense fact
   that "the repo root still contains real pak-bundled dashboards" —
   now false; those live under `content/sdk-adapters/<adapter>/`.
   Actively misleading text, safe to delete.
2. **`content-packager.md:26-42` manifest schema is wrong.** Shows
   `supermetrics: [supermetrics/<file>.yaml]`; real manifests
   (`bundles/storage-path-monitoring.yaml`) use `content/`-prefixed
   paths and carry `display_name:`, `released:`, `managementpacks:`
   which the prompt omits. An agent following this prompt authors an
   invalid manifest. The only prompt in the corpus that actively causes
   a failure.
3. **Dead references.** `mp-designer.md:34` routes to `sdk-author`,
   which does not exist (it is `sdk-adapter-author`). `<n>` placeholder
   corruption at `content-packager.md:22,51` and
   `dashboard-author.md:115` (residue of a `<name>` rename). Bare
   `managementpacks/` should be `content/managementpacks/` at
   `api-cartographer.md:27`, `mp-designer.md:67`,
   `sdk-adapter-author.md:21`.

   Note: these are exactly the DEAD-REF class `curator` is chartered to
   catch (`curator.md:70-76`) and it has not caught them. Worth a look
   at curation effectiveness, not just cadence.

### The Skill tool gap (verified)

16 of 20 prompts instruct the agent to read a `vcfops-*` skill, several
in strong terms (`sdk-adapter-reviewer.md:62` — "THE technical
authority. Read it first"). **Not one `tools:` line includes `Skill`**
(verified: `grep -l "Skill" .claude/agents/*.md` returns nothing). With
an explicit allowlist the Skill tool is not callable, and the prompts
give skill *names*, not the `.claude/skills/<name>/SKILL.md` paths that
`Read` would need.

So the most-cited knowledge source in the corpus is plausibly
unreachable by the agents told to treat it as authoritative. Fix is
either adding `Skill` to those allowlists or replacing names with
concrete paths. Confirm empirically which before choosing.

### Model routing — the core Opus 5-era question

Current pinning: **15 `sonnet`, 5 `opus`** (`opus` on
`api-cartographer`, `api-explorer`, `framework-reviewer`,
`mp-designer`, `sdk-adapter-reviewer`).

These bare aliases resolve to current-generation models, so the roster
already inherited a free upgrade to Sonnet 5 / Opus 5. But the *routing
decisions* were made when the Opus-to-Sonnet capability gap looked
different, and two placements now look inverted:

- **`tooling` is `sonnet`, `framework-reviewer` is `opus`.** The only
  agent permitted to edit framework Python is weaker than the gate
  reviewing it. A review gate catches defects; it does not prevent
  them, and every catch costs a full re-brief cycle.
- **`sdk-adapter-author` is `sonnet`, `sdk-adapter-reviewer` is
  `opus`.** Same inversion on Tier 2 Java, which is the highest-stakes
  authoring surface in the repo (the lessons index is dominated by
  Java adapter failures that took 40+ builds to find).
- **`curator` is `sonnet`** and just missed three dead references this
  audit found. Direct evidence that the tier is under-powered for a
  task that is essentially whole-corpus cross-referencing.

**Corrected recommendation, 2026-08-20** (Scott asked whether the answer
is "move everything to Opus", and proposed a bootstrap-time tier
preference instead). Verified against the subagent docs:

- `model:` accepts `sonnet`, `opus`, `haiku`, `fable`, a full model ID,
  or the literal `inherit`.
- **`model:` defaults to `inherit` when omitted.**
- There is **no** templating, env-var, or settings.json indirection for
  subagent models. A persisted "tier preference" would require a
  generator that rewrites all 20 files.

That default changes the picture entirely. **Every `model:` line in
this roster is an active downgrade from the session model**, not an
upgrade:

- The 15 `model: sonnet` agents are pinned below whatever Scott is
  running.
- The 5 `model: opus` agents are *also* pinned below the session when
  he runs Fable 5 — including `framework-reviewer` and
  `sdk-adapter-reviewer`, the two most consequential gates in the repo.

So the answer is not "move them all to Opus" and not a bootstrap
preference prompt. **It is to delete the `model:` line from the
top-tier agents and let them inherit.** That delivers exactly the
behavior Scott described — top-tier work follows his stated preference,
switching between Fable and Opus re-points the whole roster — using a
built-in default, with no generator, no config file, no bootstrap
question, and no drift surface. His `/model` setting is the dial.

**ACCEPTED — Scott, 2026-08-20: "your split seems reasonable."**

Tiers:

| Tier | Mechanism | Agents |
|---|---|---|
| Top (follows session) | omit `model:` | `framework-reviewer`, `sdk-adapter-reviewer`, `sdk-adapter-author`, `tooling`, `mp-designer`, `api-cartographer`, `api-explorer` |
| Bounded | `model: sonnet` | the 8 content authors, `content-installer`, `content-packager`, `ops-recon`, `qa-tester` |

Rationale for the split: the top tier is where a mistake costs an
expensive loop (a pak build and install cycle, a framework regression
shipped to users, a wrong object model baked into a design). The
bounded tier writes well-specified YAML with the domain knowledge
already factored into skills, and is validated mechanically afterward.

**The one trade-off, resolved by default:** `inherit` has no floor.
Dropping the session to Sonnet for a cheap day silently drops
`framework-reviewer` too. A hard floor would require hardcoding
`opus`/`fable` on the review gates and giving up follow-the-session for
them; there is no mechanism for both. Scott accepted the split without
calling for a floor, so **the default stands: pure `inherit`, no
floor.** Reversible in one line per agent if a Sonnet-session review
ever proves too thin.

**`curator` is a separate answer — do not promote it.** Its miss is
mechanical, not cognitive, and `scripts/path_reference_audit.sh`
already runs in CI (`.github/workflows/ci.yml:78`) for exactly this.
Verified today: the script reports "clear" while these dead references
are live in the corpus:

- `.claude/agents/mp-designer.md:34` routes to `sdk-author`; no such
  agent file exists. Agent-name references are entirely outside the
  script's scope.
- `.claude/agents/api-cartographer.md:27` and `mp-designer.md:67` cite
  bare `managementpacks/`; the script's path-token pattern does not
  match single-segment directory references.

Extending the script to cover (a) agent-name references resolving to a
real `.claude/agents/*.md` and (b) bare directory citations catches
this class deterministically, every run, at zero token cost. A better
model would catch it probabilistically at high cost. Fix the checker,
leave `curator` on `sonnet`, and let it spend its attention on the
judgment-shaped rot classes (CONTRADICTION, SUPERSEDED, STALE-FACT)
that a script genuinely cannot detect.

### Duplication (~480-520 lines, ~17%)

- **`## What you refuse` restates `## Hard rules`** in all 20 files;
  ~75 of ~110 lines are verbatim-equivalent to something earlier in the
  same file. Already diverging: `dashboard-author.md:74-75` lists 10
  widget types in hard rules while `:135` says only "unsupported widget
  types."
- **Reviewer twins share ~120 identical lines.** `framework-reviewer`
  and `sdk-adapter-reviewer` are ~45% structurally identical with the
  surface swapped. Largest single duplication block.
- **Convention restatements already in the project-conventions skill**:
  `[VCF Content Factory]` prefix (8 files), per-type validate command
  (12 files), refuse-without-recon (4 files), ~40 lines. Every one of
  those files already cites the skill.
- **Playwright visual-verification block** duplicated between
  `qa-tester.md:55-94` and `content-installer.md:100-116`, already
  diverging (only qa-tester has the layout-quality checklist). Not in
  any skill; prime extraction candidate.

TOOLSET GAP handling is the proof the citation pattern works here — 8
files reference it, none inline the format. The rest should follow it.

### Workflow gap

`tooling.md` never mentions `framework-reviewer` despite CLAUDE.md:302
making that gate mandatory after every `src/vcfops_*/` change.
`sdk-adapter-author.md` likewise never mentions `sdk-adapter-reviewer`.
Both reviewers know their author; neither author knows its reviewer, so
both can plausibly return "done" without signalling the gate. Two
lines, closes a real hole.

### Not recommended

Broad ALL-CAPS stripping. Most caps tokens are domain vocabulary
(`VMWARE`, `GT`/`LT`, `SELF`, `BLOCKING`), and the highest raw-caps
files are among the cleanest on genuine emphasis abuse. If trimming
emphasis, target `**bold**` density in `dashboard-author.md`,
`qa-tester.md`, and the two reviewers.

## PARKED: Codex parity

**Scott, 2026-08-20: "I'm not ready to fully tackle this yet. That's a
separate thing."** Not in scope. Captured here so the research is not
lost, to be picked up only on an explicit go:

1. Generator for `.codex/agents/*.toml` from single-source agent
   definitions, plus a CI staleness check.
2. Dual-home the five skills into `.agents/skills/`.
3. Mirror the bootstrap SessionStart hook into `.codex/config.toml`.
4. Document the write-scope caveat: enforced under Claude Code via
   per-agent tool allowlists, instructed-only under Codex via
   `sandbox_mode`.

The `AGENTS.md -> CLAUDE.md` symlink stays as-is. It is useful on its
own for external Codex review (global rule 3) and costs nothing.

## THE PLAN (consolidated, in scope)

Scope per Scott, 2026-08-20: bootstrapping, CLAUDE.md, and agent
optimization for Opus 5 / Fable 5. Codex parity parked.

### PR 1 — Correctness + model tiers

Nothing here is a judgment call; it is all either factually wrong or an
accepted decision. Safe to land without a style debate.

1. Delete the stale content-root trap blocks: `dashboard-author.md:11-23`,
   `view-author.md:11-17`, `customgroup-author.md:12-16` (~35 lines
   describing directories that do not exist).
2. Fix `content-packager.md:26-42` manifest schema against a real
   manifest (`bundles/storage-path-monitoring.yaml`); add the missing
   escalation target for broken cross-references.
3. Dead refs: `mp-designer.md:34` `sdk-author` → `sdk-adapter-author`;
   `<n>` → `<name>` at `content-packager.md:22,51` and
   `dashboard-author.md:115`; bare `managementpacks/` →
   `content/managementpacks/` at `api-cartographer.md:27`,
   `mp-designer.md:67`, `sdk-adapter-author.md:21`.
4. Skill reachability: confirm empirically whether an allowlisted agent
   can invoke `Skill`; then either add `Skill` to the 16 affected
   `tools:` lines or replace skill names with
   `.claude/skills/<name>/SKILL.md` paths.
5. Author→reviewer handoff: one line in `tooling.md` naming
   `framework-reviewer`, one in `sdk-adapter-author.md` naming
   `sdk-adapter-reviewer`.
6. Model tiers (accepted above): delete `model:` from the 7 top-tier
   agents. Separate commit so it reverts independently.
7. Extend `scripts/path_reference_audit.sh` to catch agent-name
   references and bare single-segment directory citations — the two
   classes it currently reports "clear" on while they are live.

Gate: `framework-reviewer` if item 7 touches anything under
`src/vcfops_*/` (it does not today; the script is standalone).

### PR 2 — CLAUDE.md v2

Doc-only. Citation-over-restatement for the seven duplicated blocks;
name the five skills and four slash commands; add the extractor
workflow and `src/vcfops_common/`; reframe delegation as
governance-first; separate harness-neutral content from harness
mechanics; fix the roster write-scope drift (`tooling` + `tests/`,
`content-packager` `dist/`, `content-installer` remote log-level
write). Target ~half the length with no unique content lost.

Also fixes the inbound stale citations: `HOW_IT_WORKS.md:153` "Hard
Rule 8", `guide_delegation.md` "eight numbered rules" (now eleven),
and the `vcfops-orchestration` back-pointer in
`vcfops-project-conventions/SKILL.md:10` that has survived eight
curation cycles. Same PR fixes that skill's missing
`vcfops_managementpacks validate` and its missing MP prefix carve-out.

### PR 3 — Agent prompt optimization

Judgment calls about house style; worth Scott's eyes. Collapse
`What you refuse` into `Hard rules` (~75 lines, removes a live
divergence hazard); factor the ~120 shared lines out of the reviewer
twins; extract the Playwright visual-verification block to a shared
doc or skill; replace the prefix/validate/recon restatements with
skill citations (~40 lines); trim the quadruple-stated reviewer
principles; delete the meta-justifications.

### PR 4+ — bootstrap-v2

Phases 1-4 per `knowledge/designs/bootstrap-v2.md`, landing the
concierge playbook in the restructured CLAUDE.md rather than the old
one. Unchanged by this review except that it now follows it.

### Status

Plan complete and reviewed. **PR 1 executed 2026-08-20 on Scott's
explicit go** (as a single PR, folding in the model-tier split and the
still-applicable open GitHub issues). Item 4 was resolved with the
concrete-paths fix rather than the tools-allowlist fix: every agent
already has Read, paths carry zero dependency on harness tool-surface
behavior, and they stay portable to the parked Codex work. PRs 2-4
still await their own go.
