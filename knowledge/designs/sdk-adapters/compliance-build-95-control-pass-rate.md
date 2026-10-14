# Compliance build 95: compliance percentage is passing controls over evaluated controls

- **Type:** managementpack (Tier 2 SDK adapter change), build 95
- **Slug:** compliance-build-95-control-pass-rate
- **Adapter repo:** `content/sdk-adapters/compliance/`
- **Date:** 2026-10-14
- **Status:** go from Scott 2026-10-14; authoring

## Initial prompt (Scott, verbatim, 2026-10-14)

> let's talk about making sure the math is mathing. how do we have average
> compliance of 79%, but our vds and clusters and a lot are much lower

> Can we change it so compliance percentage is basically: Total passing
> controls/total controls evaluated

> okay let's do that. also are there any critical bugs or open issues we
> should include?

("that" = the proposal with both recommendations: per-type columns switch
too; unreadable controls excluded from both counts and reported separately.)

## Why

Today every percentage in the pack is a mean of per-object scores. Prod
2026-10-14: Environment 79.9% while vCenters score 50, vDS 75, hosts about 68,
because 58 port groups at about 93% and 103 VMs at about 74% dominate an
object-weighted mean (verified: the object-weighted mean of the table rows is
79.87). A port group counts as much as a vCenter.

## Vision

1. **New rollup keys, per kind and for All** (pushed on each vCenter
   adapter-instance object next to the existing ones, held back with the kind
   when the kind's listing fails, like every other rollup key):
   - `Rollup|<Kind>|controls_evaluated`: sum over the kind's scored objects of
     the controls evaluated on that object (passed plus failed; unreadable,
     manual-review and override-skipped controls excluded, as in the
     per-object score today).
   - `Rollup|<Kind>|controls_passed`: sum of controls passed.
   - `Rollup|<Kind>|controls_unreadable`: sum of controls the adapter could not
     read (never a pass, never in the denominator; surfaced so missing data is
     visible).
   - `Rollup|<Kind>|pass_rate`: controls_passed / controls_evaluated * 100,
     omitted when controls_evaluated is 0 (never 100 on nothing evaluated).
2. **Environment** (ComplianceWorld ComputedMetrics): add
   `Rollup|Environment|controls_evaluated`, `controls_passed`,
   `controls_unreadable` (sums of the children's `Rollup|All|*`) and
   `Rollup|Environment|pass_rate` = sum(controls_passed) / sum(controls_evaluated)
   * 100. The existing `avg_score`, `score_sum`, `scored`, `non_compliant`,
   `no_benchmark` stay (no removal in this build; dashboards stop showing
   `avg_score`).
3. **Dashboards and views**: the Environment Compliance tile becomes
   "Controls Passing" bound to `Rollup|Environment|pass_rate` (same colour
   bounds as today's average); every per-kind "Avg Score (%)" column in the
   "Compliance by vCenter and Object Type" view and the Environment
   Overview becomes "Controls Passing (%)" bound to `Rollup|<Kind>|pass_rate`;
   "vCenter Compliance Score" likewise. The totals row uses the environment
   keys. Add a "Controls Unreadable" column (All) to the view. The trend chart
   plots `pass_rate`.
4. **Alerts**: Score Degraded keeps its per-host trigger (a host's own score is
   already pass over evaluated for that host, so its meaning does not change).
5. **Docs**: data-reference and overview explain the two numbers (pass rate
   over controls; object counts for scored / non-compliant) and why the pass
   rate replaced the object average.

## Verification on devel (separate go)

After two cycles: per-kind pass_rate equals passed/evaluated from the keys;
Environment pass_rate equals the sum ratio across the three vCenters; the tile
and table agree; avg_score still present but not displayed.
