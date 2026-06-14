# Volatile status doesn't belong in reference docs

## Symptom

`context/tier2_architecture.md` carried an "Implementation status" block —
*"Phase 2 (Synology): IN PROGRESS — build 1.0.0.7"*, *"Phase 3: IN
PROGRESS"* — embedded in an **architecture** doc. Synology reached build
17 and those phases completed, but the block was never updated, so a
stable reference doc shipped stale and contradicted reality. The P6
`curator` flagged it as STALE-FACT on its first real run.

## Root cause

Reference docs — `rules/`, `lessons/`, and the architecture / authoring
guides under `context/` — exist to hold **durable** facts: how the
framework works, why a path is a dead end, what a grammar is. **Volatile
status** is the opposite: build numbers, version strings, "IN PROGRESS" /
phase state, counts ("81 sections", "100+ docs"). It changes every few
sessions.

Embedding volatile status in a stable doc *guarantees* the doc goes stale,
because nobody re-opens an architecture doc to bump a build number. It also
invites **duplication** — the same status copied into two docs, each
rotting independently (here it also half-lived in a stale `status.md`).

## The rule

**Reference / architecture / lessons docs state durable facts only.**
Volatile status lives in — or is derived from — the transient surfaces:

- per-adapter build state → `context/reviews/<adapter>-build-<N>.md`,
  `context/session-handoff.md`;
- everything else → derived from the artifacts themselves (git history,
  the actual YAML / specs, `pak-compare`), never hand-copied into a
  reference doc.

If a reference doc genuinely needs to mention current state, **point** to
the live surface — don't embed the value.

**Prevention beats detection.** The P6 `curator`'s STALE-FACT class is the
backstop that catches regressions of this pattern, but the cheaper win is
not writing the volatile value into the stable doc in the first place.
Before you put a number, a version, or an "IN PROGRESS" into `rules/`,
`lessons/`, or a `context/` reference doc, ask: *will this be wrong in a
month?* If yes, link to where it stays current instead.
