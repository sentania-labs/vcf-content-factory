# Compliance build 95: compliance percentage is passing controls over evaluated controls

- **Type:** managementpack (Tier 2 SDK adapter change), build 95
- **Slug:** compliance-build-95-control-pass-rate
- **Adapter repo:** `content/sdk-adapters/compliance/`
- **Date:** 2026-10-14
- **Status:** merged to compliance main (bd2eba6, 2026-10-15, PR #53, Codex round cf354ed); not tagged on Scott's word; proven on devel_9_1

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

## Scope addition: issue #17, phase 1 (Scott, 2026-10-14)

> what's the plan for #17?
> i though twe were talking about this for build 95?

Build 95 also carries the user-invisible part of adapter issue #17 and the
bulk collection design (`compliance-bulk-collection.md`, drafted 2026-10-02,
now in play): (1) per-phase timing and call counts in the cycle summary;
(2) the #17 quick wins: one keepalive per cycle, names kept from the
inventory listing, connections reused instead of closed per call, the prefix
fallback bounded; (3) bulk reads per kind in shadow mode, logging every
disagreement with the per-object path while scoring stays on it. Switching
scoring to bulk reads, batched pushes (framework change) and a shorter
interval follow in later builds once shadow mode shows zero disagreements on
devel.

## Decision 2026-10-14: unreadable data is skipped and flagged per object

Scott, verbatim, across the discussion:

> so I think we hvae a stale or not metric that we judge based on if the most
> recent colelction was successful, and if we have missing data we just don't
> log it - but flag the stale metric, and then that becomes an alarm.
> DOes that cover it?

> How are we publishing a reason?
> What value does stale count give us? Just tell us the object has unreadable
> controls.

Supersedes the earlier "unreadable excluded and reported as a count" wording
(Vision items 1 to 3) and closes build 95 review B1 and W1:

1. **Per control:** a control that could not be read this cycle is not pushed
   (its last pushed value and its alert stay as they were; no -1, no
   "(unreadable)" overwrite). Applies to every unreadable cause, including a
   host vCenter reports as not responding.
2. **Per object:** `VCF-CF Compliance|has_unreadable` (1 or 0, pushed every
   cycle), `unreadable_count` (existing), `unreadable_reason` (property: the
   cause in plain words, for example "host not responding", "esxcli
   unavailable", "permission refused", "appliance session refused", plus the
   detail the adapter logs), `unreadable_controls` (property: affected control
   ids, capped). An object with nothing readable this cycle pushes the flag and
   reason only.
3. **Rollups:** pass_rate and the counts come from what was read this cycle.
   No stale or unreadable rollup keys; drop `controls_unreadable` from the
   rollups, the Environment ComputedMetrics, the view and the tiles.
4. **Dashboards:** an "Objects with unreadable controls" list (object, kind,
   count, reason) next to the Controls Passing tile on the Environment
   Overview and World Summary.
5. **Alert:** "Compliance data not collected" fires on `has_unreadable` = 1
   after two consecutive cycles (wait 2), cancels after one clean cycle.
6. **Shadow mode default** (no answer yet from Scott; orchestrator default):
   on in dev-preview builds (0.0.0.N), off in tagged releases, through the
   internal switch.
7. Per-object `score` stays pass / evaluated over what was read; unreadable
   controls no longer count as failing in it (consistent with 1 and 3).
