# Dashboard: Compliance World Summary

- **Type:** dashboard, summary-bound (pak dashboards.properties), compliance SDK adapter build 88
- **Slug:** compliance-world-summary
- **Target:** `content/sdk-adapters/compliance/dashboards/compliance-world-summary.yaml`
- **Date:** 2026-10-12
- **Status:** mock approved by Scott 2026-10-12 (plan-mode, RULE-011); dashboard-author pending behind build 88 adapter work

## Initial prompt (Scott, verbatim, 2026-10-12)

> also we should have a summary dashboard for compliance world

then:

> not a wireframe, html mockup, but go.

## Vision

When a user opens the ComplianceWorld object in Ops, its Summary tab
shows the compliance environment at a glance: the four engine-computed
environment tiles, the last scan time, the per-vCenter table, the score
trend, the SCG version spread, and the open compliance alerts. It is the
Environment Overview re-cut for the Summary tab: every widget inherits
the page object (ComplianceWorld), nothing is pinned or self-provider,
so the dashboard is valid as `summary_for` and never depends on the
vSphere World pin. Reuses the two existing views unchanged.

Mock (RULE-011): `compliance-world-summary.html` beside this file. Tile
and table values are the devel readings from the 2026-10-12 2:57 PM
recon (build 87, before the Pod fix); scan time, trend and alert rows
simulated. Keys from describe.xml (ComplianceWorld: `Rollup|Environment|
{scored, non_compliant, no_benchmark, avg_score}`, `Summary|
last_scan_timestamp`).

Name: `[VCF Content Factory] Compliance World Summary` (47 characters,
under the 50-character UI cap, factory issue #198).
`summary_for: "vcfcf_compliance:ComplianceWorld"`. Every widget
`self_provider: false`, no `pin`, no `pin_to_world`.

## Layout (12-column grid)

| Row | Col span | Widget | Type | Subject / keys | Notes |
|---|---|---|---|---|---|
| 1 | 1-12 | Compliance Environment | Section (`collapsed: false`) | | Children: every widget below. x must be 1. |
| 2 | 1-9 | Environment Compliance | Scoreboard, `box_columns: 4` | `Rollup|Environment|avg_score` (%, uncolored, color_method 1), `non_compliant` (yellow 1 / orange 5 / red 20), `no_benchmark` (yellow 1 / orange 1 / red 5), `scored` (uncolored) | Same bounds as the Environment Overview. |
| 2 | 10-12 | Scan | PropertyList, compact | `Summary|last_scan_timestamp` | Value on ComplianceWorld unverified; if empty on devel, drop the widget and widen the Scoreboard to 12. |
| 3 | 1-12 | Compliance by vCenter and Object Type | View embed | view `[VCF Content Factory] Compliance by vCenter and Object Type`, descendants of page object | `select_first_row: true` so row 5 is never blank on load. |
| 4 | 1-6 | Environment Score Trend | MetricChart | `Rollup|Environment|avg_score`, `Rollup|Environment|non_compliant` (color_method 2) | |
| 4 | 7-12 | Objects by SCG Version | View embed | view `[VCF Content Factory] Compliance Objects by SCG Version`, descendants of page object | |
| 5 | 1-12 | Open Compliance Alerts | AlertList | `alert_types: ["15_21"]`, criticality [2,3,4], mode all, `depth: 5` | Driven by row 3 selection; depth 5 covers ComplianceWorld > vCenter > Datacenter > Cluster > Host > VM. |

## Interaction wiring

- Row 3 view (vCenter row) -> row 5 AlertList, `type: resourceId`.
- Everything else inherits the page object.

## Constraints

- Summary dashboards may not carry pinned or self-provider widgets
  (loader rule); this is why the Overview cannot simply be bound.
- One Summary dashboard per kind (`check_unique_summary_for`); no other
  pak dashboard claims ComplianceWorld.
- The View embeds depend on ComplianceWorld -> VMwareAdapter Instance
  being a real descendant relationship (build 82 addChild, proven on
  devel for the ComputedMetrics). Whether a View widget on a summary
  page walks it is unverified until the devel install.
- Scoreboard colour thresholds are ascending-only, so Average Score
  stays uncolored (known gap, same as the Overview).
- Ships in build 88 with the alert-widget rework and the rollup fix;
  install waits on Scott's yes.
