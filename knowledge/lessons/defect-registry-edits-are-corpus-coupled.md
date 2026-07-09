# Editing knowledge/context/defects.md is corpus-coupled — change it via PR, never a direct push to main

**Rule.** Any change to `knowledge/context/defects.md` — including just flipping a
`Status: open → closed` — goes through a **PR**, not a direct push to `main`.
The factory test suite (`tests/test_defect_gate.py`) has **real-corpus-coupled**
assertions that read the live registry; a status change can turn them red. The
PR's CI catches it so you fix the tests *in the same change*.

**Why.** `tests/test_defect_gate.py` mixes synthetic-fixture tests (controlled
inline registries — safe) with real-corpus tests that assert specific defects
are open / specific paks are blocked. Closing a defect (the legitimate, desired
action) invalidates the real-corpus assertions that named it.

**Failure mode.** Pushing the registry edit straight to `main` (bypassing the
PR/CI gate) lands a **red commit on `main`**: the required `test` check fails
("DEF-xxx must be an open blocker / must block <pak>"), blocking every other
branch that needs a green `main`. The defect closure itself is correct — the
*tests* are stale.

**Reproducer.** Closing DEF-001 (synology, 2026-06-26) and pushing it to factory
`main` turned 10 corpus-coupled tests red (584 pass → 574). The correct move:
close the defect AND de-brittle/retarget the corpus-coupled tests — point
refusal coverage at a still-open blocker, invert the now-clean pak's tests to
prove "closed defect clears the gate" — in one PR.

**Prevention.**
1. Close/modify defects via PR; the CI runs the corpus-coupled suite before merge.
2. When closing a defect that real-corpus tests reference, update those tests in
   the same change.
3. Real-corpus tests should assert *which ids are present/absent* (not counts)
   and prefer synthetic fixtures for behavior, so a future closure doesn't
   re-break CI.

**Source.** PR #27 (`test(defect-gate): de-brittle real-corpus assertions after
DEF-001 closed`); `knowledge/context/reviews/framework/defect-gate-tests-def001-closed.md`;
`knowledge/rules/release-gate-defects.md` (RULE-012). The registry's own note ("Only the
orchestrator writes here, in a diff") — this lesson refines *how* that diff ships.
