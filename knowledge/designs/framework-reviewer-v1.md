# Framework-code reviewer — v1

Governance design (vault orchestration review 2026-06-12, **P4**).
Interviewed and decided interactively with Scott on 2026-06-13, same
discipline the factory applies to its own content.

## Initial prompt

> Let's move forward with Priority 4.

P4 from the review, verbatim:

> **The framework has no review gate that Tier 2 Java gets.** `tooling`
> (Sonnet) edits the loaders/renderers/builders — the product core —
> gated only by "never break validate" willpower, and validate didn't
> catch the renderer-defaults leak. The Tier 2 review pattern already
> proves the fix works.

The two real escapes that motivate it — both in `src/vcfops_dashboards/render.py`,
both caught by **Codex after the PR**, by nothing the factory owned:

- **`00d3382`** — pak-specific renderer defaults (`hidden:true`, a +1
  coordinate shift for compliance's 0-based YAML) leaked into the
  *global* standalone content-import path: dashboards imported invisible,
  1-based coords overflowed the 12-column grid.
- **`6c59f6b`** — the renderer derived `localizationKey` from the
  attribute path with no transform awareness, so all transformed columns
  (AVG/MAX/P95) of one metric collided on one key and key-resolving
  environments showed identical labels.

## Vision (interview outcomes)

A read-only, skeptical correctness/regression gate on `src/vcfops_*/` Python
changes — the **framework-code sibling of `sdk-adapter-reviewer`**.
`tooling` writes the framework Python; this agent tries to find what's
wrong before the change ships. Most of the Tier 2 reviewer template
transfers; the four deltas Scott decided:

- **Positioning vs Codex — pre-PR, complementary.** Codex now
  auto-reviews PRs (it caught both escapes above). This reviewer runs
  **before** the PR is opened, catches issues a cycle earlier, and earns
  its place by doing what Codex structurally can't: encoding the
  factory's *specific* failure modes (the two escapes as named anchors),
  checking emitted output against the factory's documented wire formats
  and known-good reference values, and re-running the factory's own
  `validate` chain + test suite + render regression. Codex stays as the
  generic second pass on the PR itself.
- **Trigger — prose discipline + non-blocking CI reminder.** CLAUDE.md
  mandates spawning the reviewer after any `src/vcfops_*/` edit, before the
  PR. A CI step **warns** (does not fail) when a PR's diff touches
  `src/vcfops_*/` but adds no `context/reviews/framework/` doc — a nudge, not
  a rubber-stampable hard gate.
- **Scope — BLANKET.** *Every* `src/vcfops_*/` diff gets a review, no
  risk-weighting exceptions. (Scott chose this over the recommended
  risk-weighted option: the cost of a missed review on a "boring"
  packaging change is worse than the Opus spend, and a blanket rule has
  no judgment-call seam to get wrong.)
- **Teeth — blocking before merge.** A **CHANGES REQUESTED** verdict
  (≥1 BLOCKING) means the orchestrator does not open/merge the tooling
  PR until `tooling` resolves the BLOCKING findings — same human-in-loop
  discipline as the content-install gate. Verdict is binary on BLOCKING
  count; NITs are advisory. (Not CI-enforced on the verdict string —
  that couples CI to a markdown token and can wedge the pipeline.)

Model: **opus** (reviewer ≥ author capability; `tooling` is Sonnet —
the review's own data called tooling-at-Sonnet the one borderline model
call, so the gate above it must be the stronger model). Writes only
`context/reviews/framework/`. Never edits `src/vcfops_*/`, never installs.

## Failure-mode taxonomy (the review dimensions)

Anchored on the two real escapes, generalized:

1. **Global-default / pak-specific leak** (`00d3382`). A default,
   transform, or coordinate convention added for one pak/path that
   changes behavior on the *global* / standalone content-import path.
   → BLOCKING.
2. **Key/label derivation collisions** (`6c59f6b`). Keys or labels
   derived without transform/context awareness; checked against the
   ground-truth (reference packs use plain `displayName`, no
   `localizationKey`). → BLOCKING.
3. **Wire-format conformance.** Emitted JSON/XML matches the documented
   wire formats (`context/wire-formats/`, `context/mpb/`) and known-good
   reference values; no silent schema drift.
4. **Loader / validator correctness.** Cross-reference resolution
   (`sm_<uuid>`, view UUIDs), UUID stability (RULE-007), prefix
   enforcement (RULE-006); a loader change that mis-resolves or
   mis-validates previously-good content.
5. **Render regression vs known-good.** Re-render the repo's own content
   and diff against committed/known-good output — both escapes were
   "render output drifted from the known-good values."
6. **Builder / pak structure.** `template.json` / `describe.xml`
   emission, the C2 shape, `pak-compare` implications — changes here
   ripple to every pak.
7. **Corpus regression.** Re-run the full `validate` chain over the
   existing content corpus and the test suite; a change that
   mis-validates previously-good content fails.
8. **Silent capability change / downgrade.** A renderer/loader feature
   removed or defaulted-off that silently drops content — the
   framework analog of "unreadable is not compliant."
9. **Stale-zip discipline.** If the change touches
   `src/vcfops_packaging/templates/`, `builder.py`, or `render.py`, all dist
   zips are stale (CLAUDE.md already says this) — the change must flag a
   `content-packager` rebuild.
10. **Test coverage of the change.** Did `tooling` add/extend tests for
    the changed behavior? The render surface was untested when both
    escapes shipped — a `render.py`/`loader.py` change with no new test
    is at least a WARNING.

## Wiring

- **Roster:** new row in CLAUDE.md's agent table.
- **Discipline:** after `tooling` reports a `src/vcfops_*/` change and
  *before* opening the PR, spawn `framework-reviewer`; blanket; BLOCKING
  blocks the PR; re-brief `tooling` until APPROVE. Sits beside delegation
  step 9 and the "After tooling changes" workflow note.
- **CI reminder:** non-blocking `scripts/check_framework_review.sh`
  invoked from a CI step on `pull_request` — emits a `::warning::` when
  the PR diff touches `src/vcfops_*/` with no `context/reviews/framework/`
  doc in the same diff.
- **Output dir:** `context/reviews/framework/` (SDK reviews stay in
  `context/reviews/`; framework reviews get their own subdir).

## Acceptance (negative proof, per the review)

The eval of the reviewer is the reviewer itself: a branch seeded with the
renderer-leak anti-pattern (`00d3382` reverted) must be **flagged**
BLOCKING. A reviewer that APPROVES the bug that already escaped fails
acceptance.

## Out of scope (this PR)

- Auto-spawning the reviewer from a hook (agents are orchestrator-spawned;
  the CI reminder is the mechanism surface).
- Golden-design / behavioral agent evals (review's layer 2/3 harness) —
  separate, later.
