# A deferred internal nit becomes the external Codex finding

Date: 2026-09-14. PR #156 (#144, SM-to-SM dependency walk).

## What happened

The framework reviewer's round 1 listed a NIT: name resolution was
last-wins when two super metrics share a display name. No shipped
content triggered it, so the orchestrator deferred it as a follow-up
and moved on through three more internal rounds. Codex's one external
round then raised exactly that item as a P2, so it was fixed anyway,
one round later, with a fourth internal review to confirm it.

Across the three M0 PRs that day, every item Codex could see had
already been named by the internal gate. The only findings Codex could
not have raised were in files the branch was scoped away from (#154).

## Lesson

Fix every internal finding before the PR opens, warnings and nits
alike, in one re-brief. The external round is for what the internal
gate missed, not for what it chose to defer. Deferring costs a full
extra loop (Codex round, tooling round, review round) for the same
change. A follow-up issue is only for a finding in code the branch does
not touch; anything else stays in the review report as a note, not an
issue, so the issue list carries only things that block a milestone.
