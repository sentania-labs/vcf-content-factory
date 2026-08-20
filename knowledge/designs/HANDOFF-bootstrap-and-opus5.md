# HANDOFF: bootstrap v2 + CLAUDE.md/agent optimization for Opus 5

Written 2026-08-20. Self-contained: a fresh session should be able to
execute from this file without replaying the review conversation.

**Status: PR 1 executed 2026-08-20 on Scott's explicit go** (single PR
combining PR 1's seven items, the model-tier split, and a sweep of the
open GitHub issues verified still-applicable at execution time). PRs
2-4 remain planned, not started.

## What this is

Three related work streams, scoped by Scott on 2026-08-20:
bootstrapping, CLAUDE.md, and agent optimization for the Opus 5 /
Fable 5 era. A fourth (Codex parity) was explicitly parked.

Source documents, both uncommitted at time of writing:
- `knowledge/designs/bootstrap-v2.md`, the bootstrap plan, revised
  once with Scott's feedback.
- `knowledge/designs/claude-md-review-2026-08.md`, the CLAUDE.md and
  agent-prompt review, plus the consolidated four-PR plan. **Read this
  one first; its "THE PLAN" section is the authoritative sequence.**

## Already done

- `AGENTS.md -> CLAUDE.md` symlink created at repo root (uncommitted).
  Rationale: Codex and other harnesses read AGENTS.md as their
  constitution. Keep it; it costs nothing and helps external Codex
  review (global rule 3).

## Decisions Scott made (do not relitigate)

1. **Bootstrap is a full concierge**, not just a preflight check. On an
   unconfigured clone it greets with "it looks like this is an
   unconfigured copy, want me to get it ready?" and walks python, venv,
   deps (asking for a corporate mirror if PyPI is blocked), creds, and
   reference clones.
2. **Upstream reporting is ELI5**, plain-language summary of what
   changed, grouped by area, not "behind by 7."
3. **Ahead-commits get classified** core vs environment/state; only
   core earns a "worth a PR" nudge. Nothing auto-pushes.
4. **No gh-axi dependency**, degrade gh-axi → gh → git-only.
5. **Everything new is Python-first** so Windows works. No bash in hook
   command lines.
6. **Model tiers accepted** (see below), with no floor.
7. **Codex parity parked**, "I'm not ready to fully tackle this yet."

## The model-tier decision (the least obvious part)

Verified fact that drove it: `model:` in agent frontmatter **defaults
to `inherit`**, and there is no templating/env-var/settings.json
indirection for subagent models.

Consequence: every `model:` line in the current roster is an active
*downgrade* from the session model. The 15 `sonnet` agents sit below
whatever Scott runs, and the 5 `opus` agents sit below him too whenever
he runs Fable 5, including both review gates.

Accepted split:

| Tier | Mechanism | Agents |
|---|---|---|
| Top (follows session) | **omit `model:`** | framework-reviewer, sdk-adapter-reviewer, sdk-adapter-author, tooling, mp-designer, api-cartographer, api-explorer |
| Bounded | `model: sonnet` | the 8 content authors, content-installer, content-packager, ops-recon, qa-tester |

Line drawn at blast radius: top tier is where a mistake costs an
expensive loop (pak build/install cycle, framework regression shipped,
wrong object model baked into a design). Bounded tier writes
well-specified YAML with domain knowledge already in skills, validated
mechanically afterward.

Accepted trade-off: **no floor.** Dropping the session to Sonnet drops
the review gates too. Reversible in one line per agent.

Note for whoever executes: Scott switched to Fable 5 on 2026-08-20
(the pending-credits blocker cleared). With `inherit`, the roster
follows whatever he is on, no action needed either way. One escape
hatch the original analysis missed: the Agent spawn call accepts a
per-spawn model override, so a soft floor for the two review gates on
a Sonnet-session day is a one-sentence CLAUDE.md instruction, not a
generator.

**Do not promote `curator`.** Its dead-ref misses are mechanical, not
cognitive. Fix `scripts/path_reference_audit.sh` instead (PR 1 item 7)
and let curator spend attention on judgment-shaped rot.

## The four PRs

Full detail in `claude-md-review-2026-08.md` §THE PLAN. Summary:

**PR 1, correctness + model tiers.** No judgment calls; everything is
either factually wrong or already decided. Seven items: stale
content-root traps, content-packager schema, dead refs, skill
reachability, author→reviewer handoff lines, model tiers (separate
commit), path-audit script extension. **Start here.**

**PR 2, CLAUDE.md v2.** Doc-only. Citation-over-restatement, name the
skills and slash commands, add the extractor workflow, governance-first
delegation framing, roster write-scope fixes, inbound stale citations.

**PR 3, agent prompt optimization.** House-style judgment calls worth
Scott's eyes: collapse refuse-into-hard-rules, factor the reviewer
twins, extract the Playwright block, skill citations.

**PR 4+, bootstrap-v2** phases 1-4 per `bootstrap-v2.md`, landing the
concierge playbook in the restructured CLAUDE.md rather than the old
one.

## Verified findings the executor can trust

These were checked against the filesystem during the review, not
inferred:

- Repo-root `dashboards/`, `views/`, `customgroups/` **do not exist**,
  the trap warnings in three author prompts are describing a vanished
  world, and `dashboard-author.md:20-21` states it as present fact.
- **No agent has `Skill` in its `tools:` line** (`grep -l "Skill"
  .claude/agents/*.md` → empty) while 16 prompts instruct reading a
  skill. Confirm whether Skill is callable without the allowlist entry
  before choosing the fix.
- `.claude/agents/mp-designer.md:34` routes to `sdk-author`; no such
  agent file exists.
- `scripts/path_reference_audit.sh` reports **"clear"** while both the
  `sdk-author` dead agent name and the bare `managementpacks/`
  citations are live, it covers neither class.
- Roster model pinning today: 15 sonnet, 5 opus.
- CLAUDE.md is 336 lines / 2,810 words; ~60-65% restates something with
  an authoritative copy elsewhere. Session-start reading floor is
  ~15.6k tokens.

## Framing that should survive into the work

The reason to cut duplication is **single-source-of-truth, not token
savings.** At 1M context the 15.6k floor is ~1.5% of the window; the
old "keep CLAUDE.md lean" argument has largely expired. The goal is
fewer *copies*, not a shorter file, anything genuinely unique stays
however long it is. Evidence the maintenance cost is real: the
cross-reference table exists in four places, and the stale
`vcfops-orchestration` pointer has survived eight curation cycles.

Similarly, delegation should be reframed **governance-first**.
Write-scope isolation and review gates are model-independent and stay
verbatim. The context-economy rationale ("delegate so the foreman's
context survives") has weakened, and subagents carry a real
disadvantage the old framing ignored: they lack the conversation's
accumulated context, so a reflexive hand-off can produce worse work
than doing it inline.
