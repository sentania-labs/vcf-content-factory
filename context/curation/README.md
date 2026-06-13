# context/curation/ — knowledge-corpus curation

Reports and trigger state for the **`curator`** agent (P6) — the read-only
librarian that audits the governance corpus (`rules/`, `lessons/`,
`context/`, `.claude/agents/`, `CLAUDE.md`, skills) for staleness and
self-contradiction. Design of record: `designs/curator-v1.md`. Agent:
`.claude/agents/curator.md`.

## Contents

- **`<date>-report.md`** — a curation report (the curator's sole write
  target). Findings in eight classes: SUPERSEDED, DRIFT, CONTRADICTION,
  INDEX ROT, CITATION-INTEGRITY/DEAD-REF, STALE-FACT, DUPLICATION,
  PROMPT-ROSTER SKEW — each split into *mechanical* (orchestrator may
  apply as a small PR) and *judgment* (triage by Scott).
- **`.last-run`** — **committed** staleness marker. `last_run=<ISO8601>`
  of the last completed curation. Reset to "now" when the curator
  finishes. Portable shared state: a fresh clone immediately knows the
  calendar position.
- **`.sessions-since`** — **gitignored** per-checkout velocity counter.
  The SessionStart hook (`scripts/curation_staleness_check.sh`)
  increments it each session; the orchestrator zeroes it when the curator
  completes. Not committed because "sessions since last curation" is a
  local signal, not shared state.

## Trigger

`scripts/curation_staleness_check.sh` runs at SessionStart (wired in
`.claude/settings.json` alongside the bootstrap hooks). When
`last_run > 7 days` **OR** `sessions_since > 10`, it emits an
`additionalContext` nudge telling the orchestrator to spawn `curator` in
the background and inform the user. The hook **never launches** anything
and **fails open** (any error → silent no-op, never blocks a session).

To force a curation pass now, run the `curator` agent on request (or age
`.last-run` past the 7-day threshold). After a pass, reset `.last-run` to
today and zero `.sessions-since`.
