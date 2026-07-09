# Compliance Adapter — Coverage Surfacing (honest denominator)

**Date**: 2026-06-03
**Status**: Queued (behind the esxcli sprint)
**Type**: Tier 2 SDK adapter + content enhancement (compliance)
**Owner agents**: `sdk-adapter-author` (counts) + `dashboard-author` (widget)
**Parent**: `knowledge/designs/managementpacks/vcf-compliance-adapter.md`

---

## Initial prompt

> is there a way that based on the CSV — like if it doesn't refer to a
> normalized reference point, we have a text widget or notice someplace — or
> do we operate on the assumption that the user will read the benchmark and
> understand what is and is not auditable by code/dashboard?

Trigger: `vc.vpxuser-length` — the SCG itself stamps it `Audit: N/A` (no
observation method exists); it loads for traceability but contributes
nothing to pass/fail/unreadable, so a host score silently reflects only the
*auditable subset* of the benchmark.

## Vision

Stop relying on "the operator reads the benchmark." Make non-auditability a
**first-class, surfaced signal** — the same principle that already justifies
`unreadable_count`: coverage gaps must be loud, not silent. The score must
never be presented naked (it silently uses the auditable subset as the
denominator and overstates compliance).

## The counts (mechanically derived from the CSV — no per-control curation)

Add, alongside the existing `pass`/`fail`/`unreadable`/`total` stats, per
resource + `ComplianceWorld` rollup:

- **`manual_review_count`** — controls the benchmark defines but that have
  **no machine audit method** (`Audit: N/A` in the SCG source, or
  `parameter_kind=manual_audit` with no recipe). *Will never* be code-audited.
- **`not_yet_count`** — controls that ARE API-reachable but have no recipe
  built yet (the `vim_property`/`esxcli`/reclassifiable-`powercli` backlog).
  *Will* be covered by a future build.

These two are the "Cannot" vs "Haven't yet" split already in
`UNAUDITED_CONTROLS.md` — promoted from a doc-in-the-pak to live counts. The
loader derives them from `parameter_kind` + `read_recipe` presence + (for the
deepest signal) the SCG source `Audit` column.

## The dashboard (score is never naked)

A coverage widget on the compliance dashboard showing the full split next to
the score, e.g.:

```
SCG 9.0 — vcf-lab-mgmt-esx01
Score (of auditable): 56%   ▓▓▓▓▓░░░░
  Auto-audited:  A      Manual review: M
  Not-yet-built: N      Unreadable:    U
```

so "56%" reads as "56% of the A we can machine-check, with M requiring manual
review and N on the roadmap" — not "56% compliant with SCG 9.0."

`UNAUDITED_CONTROLS.md` stays the drill-down detail; optionally expose it via a
report section or a long-text property so it is reachable in-product, not only
inside the pak file.

## Scope / non-goals

- IN: the two counts (loader/evaluator + push), the dashboard coverage widget.
- Reuses the existing `SuiteApiPropertyPusher` push path and the CSV signals —
  modest work; no new collection.
- NOT: changing the score formula itself (denominator stays "of auditable";
  we *contextualize* it, not redefine it). A "% of full benchmark" secondary
  metric could be a follow-up if wanted.
- NOT: part of the esxcli sprint — build this after, as its own increment, to
  keep the esxcli slices clean.

## Gate

`validate-sdk` → `build-sdk` → `pak-compare` → prove counts on devel (the
split should sum to total per resource) → dashboard via `dashboard-author`
(RULE-011 wireframe first).
