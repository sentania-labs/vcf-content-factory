# Compliance Adapter — Data-Driven vim_property Reader

**Date**: 2026-06-01
**Status**: Approved for build
**Type**: Tier 2 SDK adapter enhancement (compliance)
**Owner agent**: `sdk-adapter-author`
**Parent design**: `knowledge/designs/managementpacks/vcf-compliance-adapter.md`

---

## Initial prompt

User asks (this session, verbatim intent):

> Going back to the controls — how do we dynamically ensure we are able
> to get the proper controls — i.e. close the gap, or when a new control
> is introduced capture that "data" without resorting to code changes?

Then, on scope:

> let's work on the vim_property path right now.

---

## Vision

Make `vim_property` controls **data-driven**, so a new vim_property
control is added by editing the benchmark CSV (and re-normalizing),
with **no Java change** — matching the zero-code property that
`advanced_setting` already has via the bulk `queryOptions(null)` read.

Today the three bespoke readers (`readSecurityPolicy`,
`getClusterVsanConfig`) hardcode, in Java, the translation from a
canonical logical key (`securityPolicy.forgedTransmits`) to the vim25
walk + unwrap. A new vim_property control only scores if its exact
field already happens to be one of those hand-read fields. That is the
gap.

## Resolved decisions (2026-06-01)

1. **Where vim structural knowledge lives → CSV `read_recipe` column.**
   The canonical schema gains a 13th column carrying the full read
   spec. Any new control whose extraction *style* already exists is
   then pure data — even for a vim structure never read before. The
   tradeoff (accepted): vim25 path knowledge moves into the
   profile/normalizers, and authors of custom profiles must know the
   vim path. The benchmark normalizers own this for the bundled
   profiles.

2. **Ship the "declared-but-unreadable" signal in the same task.** The
   generic reader and its safety net land together so a data-driven
   read that resolves to nothing (typo'd path, absent field) is
   surfaced explicitly, never folded into a sentinel pass.

## Schema change — `read_recipe` (canonical column 13)

Add to `CANONICAL_SCHEMA.md` and all three canonical CSVs.

Grammar: `<style>:<vim_path>`

- `<vim_path>` — a vim25 property path resolvable from the control's
  resource MO (the path passed to `PropertyCollector` /
  `getRawProperty`, optionally completed by a reflective getter walk
  for segments PropertyCollector won't resolve).
- `<style>` — closed extraction-style set (start small; new styles are
  the only thing that ever needs Java):

  | style | meaning | example path |
  |---|---|---|
  | `scalar` | direct scalar/String/Number/Boolean | `config.product.version` |
  | `bool` | boolean via `isX()`/`getX()` | `configurationEx.vsanConfigInfo.enabled` |
  | `bool_policy` | unwrap a `BoolPolicy` wrapper's `.value` | `config.defaultPortConfig.securityPolicy.forgedTransmits` |
  | `string_list_join` | join a `List<String>` (comma) | `config.dateTimeInfo.ntpConfig.server` |

Rules:
- `read_recipe` is **optional**. A `vim_property` control with an empty
  `read_recipe` is **non-evaluable** (informational only) — it loads,
  appears for traceability, and is skipped by the evaluator. This keeps
  existing CSVs valid and lets the column be populated incrementally.
- An unknown `<style>` → the control is unreadable (see below), never a
  silent skip and never a guess.

## Reader engine

New generic path (replaces the three bespoke readers; same
`evaluateVimProperties` downstream):

1. Group a resource's `vim_property` controls; for each, read
   `getRawProperty(moRef, recipe.path)`.
2. Apply the style extractor to the node → typed actual value.
3. Hand the typed value map to
   `ControlEvaluator.evaluateVimProperties` (its boolean
   Accept/Reject/Enabled coercion is already generic and stays).

Reflection-tolerant throughout (per the **vcfops-sdk-adapter** skill):
never cast to concrete vim25 subclasses; missing accessor → null.

## Unreadable signal

Three outcomes per evaluated control, not two:
- **pass** / **fail** — as today (value read and compared).
- **unreadable** — `read_recipe` present and evaluable, but the read
  resolved to null / the style couldn't extract / the style is unknown.

Contract:
- Unreadable controls are **excluded from pass, fail, and the score
  denominator** (they are not failures — we don't know).
- Add an aggregate `unreadable_count` alongside `pass/fail/total_count`,
  pushed per resource and rolled up on `ComplianceWorld`. An operator
  reads a non-zero `unreadable_count` as "the profile declares controls
  this adapter could not assess" — a profile/coverage problem, distinct
  from non-compliance.
- The existing zero-divisor contract is unchanged: no evaluable controls
  → score=100.0 with total_count=0; callers still refuse to fold a
  total_count==0 result into rollups.

## Behavior preservation (the proof gate)

The 7–8 existing evaluable vim_property controls (DVS/DVPG
`securityPolicy.*`, cluster `vsanConfig.*`) get `read_recipe` values
filled in (`bool_policy:…` / `bool:…`) and must produce **byte-identical
pass/fail/score** to the current bespoke readers before any expansion.
That equivalence is the acceptance test for the refactor. New controls
(host NTP, TLS profile, etc.) are a follow-up — out of scope here.

## Files in play

- `profiles/canonical/*.csv` — add `read_recipe` column; populate for
  the existing evaluable vim controls.
- `scripts/normalize_*.py` — emit the new column.
- `CANONICAL_SCHEMA.md` — document column 13 + the style enum.
- `src/.../BenchmarkProfile.java` — carry `readRecipe`; evaluability now
  requires a recipe for vim_property.
- `src/.../BenchmarkLoader.java` — header-aware read of the new column.
- `src/.../VSphereClient.java` — generic recipe-driven reader; retire
  the three bespoke readers once equivalence is proven.
- `src/.../ControlEvaluator.java` — unreadable outcome + `unreadable_count`.
- `src/.../ComplianceAdapter.java` — collectors call the generic reader;
  push `unreadable_count`.
- `CHANGELOG.md` / `adapter.yaml` — build bump.

## Non-goals

- Re-classifying `powercli_only` / `esxcli` / `manual_audit` controls
  (no execution runtime — separate effort, vRO fork).
- New host/VM vim_property controls beyond proving equivalence.
- Phase 2 remediation actions.
