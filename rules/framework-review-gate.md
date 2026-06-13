# RULE-013 — Framework Python changes pass `framework-reviewer` before merge

No change to `vcfops_*/` (the framework Python — loaders, renderers,
builders, CLIs) merges to `main` until the **`framework-reviewer`** agent
has reviewed it and returned **APPROVE** (zero BLOCKING).

The flow:

1. `tooling` makes the `vcfops_*/` change and reports it (the only agent
   that edits `vcfops_*/`).
2. **Before the PR is opened**, the orchestrator spawns
   `framework-reviewer`. Scope is **blanket** — *every* `vcfops_*/` diff,
   with no risk-weighting exceptions. A "boring" packaging or CLI change
   is in scope exactly like a renderer change.
3. The reviewer re-runs the `validate` chain, the test suite, and render
   regression itself, hunts the known escape modes (global-default leak,
   key/label collision, silent downgrade, wire-format drift), and returns
   **APPROVE** or **CHANGES REQUESTED**.
4. **CHANGES REQUESTED (≥1 BLOCKING) blocks the PR.** Re-brief `tooling`
   to fix, then re-review. Do not open or merge the PR with open BLOCKING
   findings — same human-in-loop discipline as the content-install gate.

Why this exists: the framework is the product, yet it shipped two
renderer regressions (`00d3382` global-default leak, `6c59f6b`
localizationKey collision) that `validate` passed and that were caught
only by Codex *after* the PR. Content has a skeptical reviewer; Tier 2
Java has one; the framework core must too. `framework-reviewer` is the
factory-owned, **pre-PR** gate — it complements Codex's generic post-PR
pass, it does not replace it.

Supporting obligations:

- **The reviewer is read-only and independent.** It never edits
  `vcfops_*/`; it hands findings back to `tooling`. A reviewer that edits
  the code it reviews is no longer a check.
- **No rubber-stamping.** The verdict must rest on re-run evidence
  (validate chain, tests, render regression), not on repeating `tooling`'s
  claims. The verdict is binary on BLOCKING count.
- **CI reminds, does not gate.** `scripts/check_framework_review.sh` warns
  (non-blocking) when a PR touches `vcfops_*/` with no
  `context/reviews/framework/` doc. The real gate is this rule + the
  orchestrator discipline; a CI doc-existence gate would be
  rubber-stampable and could wedge legitimate hotfixes.

Design of record: `designs/framework-reviewer-v1.md`. Reviewer prompt:
`.claude/agents/framework-reviewer.md`.
