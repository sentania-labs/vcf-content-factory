# Dashboard layout change: compliance build 95

- **Type:** dashboard layout change (two existing pak dashboards), compliance build 95
- **Slug:** compliance-build-95-layout
- **Date:** 2026-10-14
- **Status:** RULE-011 gate run after the YAML was written (orchestrator slip:
  build 95 was briefed with "next to the Controls Passing tile" without a mock);
  nothing shipped; awaiting Scott's approval of `compliance-build-95-layout.html`

## Initial prompt

Scott, 2026-10-14: "What value does stale count give us? Just tell us the object
has unreadable controls." The orchestrator proposed an "Objects with unreadable
controls" list beside the tile; build 95 implemented it.

## Wireframe (12-column grid, Ops grid units)

### Environment Overview, build 95

| Widget | Type | x | y | w | h | Subject |
|---|---|---|---|---|---|---|
| Environment Compliance | Scoreboard 2x2 | 1 | 1 | 4 | 6 | Rollup Environment pass_rate, non_compliant, no_benchmark, scored |
| Objects with Unreadable Controls (new) | View | 5 | 1 | 5 | 6 | list view, has_unreadable = 1: object, kind, count, reason |
| About This Dashboard | TextDisplay | 10 | 1 | 3 | 6 | |
| Compliance by vCenter and Object Type | View | 1 | 7 | 12 | 8 | per-kind pass_rate, All passed / evaluated |
| Objects by SCG Version | View | 1 | 15 | 12 | 5 | |
| Environment Score Trend | MetricChart | 1 | 20 | 12 | 7 | pass_rate, non_compliant |
| Open Compliance Alerts | AlertList | 1 | 27 | 12 | 7 | type 15/21, driven by the vCenter view |

### World Summary, build 95

| Widget | Type | x | y | w | h | Subject |
|---|---|---|---|---|---|---|
| Environment Compliance | Scoreboard 2x2 | 1 | 1 | 4 | 5 | as above |
| Objects with Unreadable Controls (new) | View | 5 | 1 | 5 | 5 | as above |
| Scan | PropertyList | 10 | 1 | 3 | 5 | Summary Last Scan |
| Compliance by vCenter and Object Type | View | 1 | 6 | 12 | 8 | |
| Objects by SCG Version | View | 1 | 14 | 12 | 5 | |
| Environment Score Trend | MetricChart | 1 | 19 | 12 | 7 | pass_rate |
| Open Compliance Alerts | AlertList | 1 | 26 | 12 | 7 | |

Constraints: widget types limited to the 9.0.x allowlist (View, Scoreboard,
PropertyList, TextDisplay, MetricChart, AlertList are on it).
