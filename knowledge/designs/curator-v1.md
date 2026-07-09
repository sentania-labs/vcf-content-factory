# Curator agent — v1

Governance design (vault orchestration review 2026-06-12, **P6**).
Interviewed and decided interactively with Scott on 2026-06-13.

## Initial prompt (verbatim)

> We're adding a curator agent — a librarian over the governance corpus
> (rules/, lessons/, context/, .claude/agents/, CLAUDE.md). Rationale:
> at 100+ governance documents that grow every session, contradiction
> and staleness become product defects. Two real instances this week:
> the worker.int "MP removal loop" blocker stayed in circulation six
> weeks after commit 0f7aad9 fixed it, and the Synology tests pointed
> at content/managementpacks/ long after the adapter moved. Vault
> context: scott/reports/vcfcf-orchestration-review-2026-06-12.md (P6).
>
> Design with me first:
> 1. Agent: read-only posture over the governance corpus; sole write
>    target context/curation/<date>-report.md. Classifies findings as
>    SUPERSEDED (claim contradicted by later commits — cross-reference
>    against git log), DRIFT (prompts/docs/tests referencing moved or
>    renamed paths), CONTRADICTION (rules vs lessons vs context), and
>    INDEX ROT (context/README sections vs disk). Each finding: class,
>    evidence paths, proposed fix. Mechanical fixes may ride as a small
>    PR; judgment calls stay in the report for me. Model: sonnet.
>    Interview me on the hunt list — what other rot classes have burned
>    us?
> 2. Trigger (ships in the repo, portability rule applies): a
>    SessionStart staleness hook alongside the existing bootstrap hooks.
>    Marker file context/curation/.last-run (committed) holds timestamp
>    + session counter; hook increments the counter and, when
>    last-run > 7 days OR sessions-since > N (interview me on N), emits
>    additionalContext instructing the orchestrator to spawn the curator
>    in the background and tell the user. The hook never launches
>    sessions itself — orchestrators spawn agents, hooks inform.
>    Fail-open on any internal error. Marker resets when the curator
>    completes.
> 3. CLAUDE.md: add the curator to the roster and the trigger contract
>    to the delegation protocol.
>
> Then implement: agent prompt, hook script + settings wiring, marker
> convention, roster update. One PR.
> Acceptance (negative proof in the PR description): (a) seed a
> deliberate contradiction in a scratch lesson — the curator's report
> flags it with the right class and evidence; (b) demonstrate the
> trigger: marker aged artificially → session start emits the nudge;
> fresh marker → silent.

## Interview outcomes

- **Hunt list — all four proposed additions accepted.** The curator
  hunts **eight** finding classes: the four in the prompt plus —
  - **CITATION-INTEGRITY / DEAD-REF** — a rule/lesson/prompt/skill citing
    a rule-ID, lesson name, skill name, or doc that was renamed,
    renumbered, or removed. Grounded: `471365e` renumbered RULE-006-011
    → 004-009; this session added RULE-012/013 — old references dangle.
    Distinct from DRIFT (moved file *paths*); this is internal ID/name
    citation integrity. Mechanically checkable.
  - **STALE-FACT** — a version/count/lifecycle-status claim that has
    since changed (e.g. HOW_IT_WORKS still calls Synology/Dell "queued
    as the first real Tier 2 adapters" — both shipped; "context/README's
    81 sections"). Scoped to **enumerable** claims (counts, version
    strings, "queued/complete/planned") to limit false positives.
  - **DUPLICATION** — two+ lessons/context docs covering the same ground
    that can silently diverge (the corpus already has several
    SSL/stitch/MOID lessons).
  - **PROMPT-ROSTER SKEW** — an agent prompt's `writes to` / `spawn when`
    contradicting CLAUDE.md's roster, or a skill description contradicting
    its agent. CLAUDE.md already acknowledges this drift ("if Spawn-when
    conflicts with the prompt, the prompt wins").
- **Threshold N = 10.** Trigger fires when `last_run > 7 days` OR
  `sessions_since > 10`. The 7-day timer catches slow calendar drift; 10
  catches a heavy sprint before the weekly timer would.
- **Model: sonnet** (per the prompt — the work is pattern-matching and
  git-log cross-referencing, not deep correctness review).

## Mechanical-vs-judgment split

Each finding records: **class · evidence paths · proposed fix**. The
curator is read-only (sole write = its report). It does **not** open PRs.
After the report:
- **Mechanical** findings (DRIFT path fixes, INDEX ROT, DEAD-REF
  re-pointing) may be applied by the orchestrator as a small follow-up
  PR.
- **Judgment** findings (CONTRADICTION, DUPLICATION consolidation,
  STALE-FACT rewording, SUPERSEDED retirement) stay in the report for
  Scott to triage.

## Trigger marker — refinement (deliberate deviation, flagged)

The prompt specifies one committed marker `context/curation/.last-run`
holding *both* the timestamp and the session counter, incremented by the
hook every session. Implemented with a **two-file split**, because a
committed file the hook mutates every session would leave the working
tree perpetually dirty — which breaks the **clean-tree precondition** of
`/publish` and `/release` (a hard, shipped requirement):

- **`context/curation/.last-run`** — **committed**. Holds `last_run=<ISO>`
  (the durable, portable "when did we last curate"). Changes only when
  the curator completes — so a fresh clone immediately knows the calendar
  state and the 7-day timer works on first session. This is the portable
  shared state the portability rule cares about.
- **`context/curation/.sessions-since`** — **gitignored**. An integer the
  hook increments each session and the curator/orchestrator zeroes on
  completion. "Sessions since last curation" is inherently a *per-checkout
  velocity* signal — it has no meaning shared across clones/machines, so
  it correctly is **not** committed. A fresh clone starts its own count
  (fail-open: missing → treated as 0).

Net: same trigger semantics (`>7d OR >10 sessions`), portable durable
state committed, velocity counter local, and the tracked tree stays clean
between curations. If you'd rather have the literal single committed
marker, it's a one-file change — but it reintroduces the dirty-tree /
publish friction.

## Wiring

- **Agent:** `.claude/agents/curator.md` (sonnet, read-only, sole write
  `context/curation/<date>-report.md`).
- **Hook:** `scripts/curation_staleness_check.sh`, added to
  `SessionStart` in `.claude/settings.json` alongside the bootstrap
  hooks. Reads the marker, increments the gitignored counter, and emits
  `additionalContext` (structured `hookSpecificOutput`) instructing the
  orchestrator to spawn the curator in the background and tell the user —
  when due. **Never launches a session itself.** Fail-open on any error.
- **CLAUDE.md:** roster row + the trigger contract in the delegation
  protocol (no new RULE — the prompt scopes this to roster + contract).
- **`context/curation/`** — the report directory + a README convention.

## Acceptance (negative proof)

(a) Seed a deliberate contradiction in a scratch lesson → the curator's
report flags it with the right class + evidence. (b) Trigger demo: marker
aged artificially → session start emits the nudge; fresh marker → silent.

## Out of scope

- Auto-applying any fix (curator reports; orchestrator/user act).
- A scheduled cloud cron (the in-repo SessionStart hook is the portable
  trigger; a cron would be machine-specific).
