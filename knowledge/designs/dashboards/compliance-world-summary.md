# Dashboard: Compliance World Summary

- **Type:** dashboard, summary-bound (pak dashboards.properties), compliance SDK adapter build 88
- **Slug:** compliance-world-summary
- **Target:** `content/sdk-adapters/compliance/dashboards/compliance-world-summary.yaml`
- **Date:** 2026-10-12
- **Status:** mock approved by Scott 2026-10-12 (plan-mode, RULE-011); built in adapter build 88; Section row dropped for build 89 on Scott's go 2026-10-13 (see Correction below)

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
| 1 | 1-9 | Environment Compliance | Scoreboard, `box_columns: 4` | `Rollup|Environment|avg_score` (%, uncolored, color_method 1), `non_compliant` (yellow 1 / orange 5 / red 20), `no_benchmark` (yellow 1 / orange 1 / red 5), `scored` (uncolored) | Same bounds as the Environment Overview. |
| 1 | 10-12 | Scan | PropertyList, compact | `Summary|last_scan_timestamp` | Value on ComplianceWorld unverified; if empty on devel, drop the widget and widen the Scoreboard to 12. |
| 2 | 1-12 | Compliance by vCenter and Object Type | View embed | view `[VCF Content Factory] Compliance by vCenter and Object Type`, descendants of page object | `select_first_row: true` so row 4 is never blank on load. |
| 3 | 1-6 | Environment Score Trend | MetricChart | `Rollup|Environment|avg_score`, `Rollup|Environment|non_compliant` (color_method 2) | |
| 3 | 7-12 | Objects by SCG Version | View embed | view `[VCF Content Factory] Compliance Objects by SCG Version`, descendants of page object | |
| 4 | 1-12 | Open Compliance Alerts | AlertList | `alert_types: ["15_21"]`, criticality [2,3,4], mode all, `depth: 4` | Driven by row 2 selection. The input is always the selected vCenter row (`select_first_row`), never ComplianceWorld, so depth 4 covers vCenter > Datacenter > Cluster > Host > VM, same as the Environment Overview (build 88 review NIT 5; was 5). |

## Interaction wiring

- Row 2 view (vCenter row) -> row 4 AlertList, `type: resourceId`.
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

## Correction 2026-10-13: Section row dropped (build 89)

The approved mock had a full-width `Section` header ("Compliance
Environment") as row 1. Build 88 installed on devel (VCF Operations
9.0.2.0) and the Summary tab stayed stock: the 9.0.x dashboard importer has
no `Section` widget type and aborts the whole dashboard on the first unknown
type, so the dashboard never imported and the `dashboards.properties`
binding never ran (evidence:
`knowledge/context/investigations/2026-10-12-compliance-pak-summary-binding.md`).
Scott: "sections are not present in 9.0.x" and "drop the secon row and do
build 89" (approval record
`knowledge/context/approvals/2026-10-13-compliance-build-89-devel-install.md`).
The table above is the build 89 layout: the five remaining rows are the
approved ones, moved up one row. The mock keeps the header struck through
rather than redrawn. Rule for pak-shipped dashboards while 9.0.x is a
target: no `Section` widgets (factory issue #199 tracks the validator guard).
