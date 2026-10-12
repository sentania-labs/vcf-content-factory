# Design: Compliance Fleet Overview Dashboard

> **Superseded 2026-09-23** by `compliance-environment-overview.md` (adapter v3).
> Its ComplianceWorld Summary keys were retired in build 57 and the
> dashboard is no longer bundled.

## Initial prompt

"Author compliance dashboards: Compliance Overview (heatmap + scoreboard) and
Drift Timeline." User clarified: this must be a fleet-level dashboard, not a
host-by-host picker. All widgets show aggregate or all-hosts data.

## Vision

A single fleet-level compliance dashboard. No host picker. Every widget is
self-provider with a pin. Operators scan the heatmap and table to spot
outliers, check fleet trends, and review alerts. Host-level drill-down
happens via the VCF Ops UI (click host -> All Metrics).

## Wireframe (approved 2026-05-27)

```
ROW 1: Fleet KPIs  (self-provider, pinned to ComplianceWorld)
┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
│ Hosts     │ │ Avg Score │ │ Below     │ │ Active    │
│ Scanned   │ │   (%)     │ │ Threshold │ │ Profile   │
│ (w:3,h:3) │ │ (w:3,h:3) │ │ (w:3,h:3) │ │ (w:3,h:3) │
└───────────┘ └───────────┘ └───────────┘ └───────────┘

ROW 2: All-Hosts Overview  (self-provider, pinned to HostSystem)
┌─────────────────────┐  ┌───────────────────────────────────────┐
│  Heatmap             │  │  View: Compliance Host Overview       │
│  All hosts           │  │  All hosts table                     │
│  color: score        │  │  sorted worst-first                  │
│  (w:5, h:8)          │  │  (w:7, h:8)                          │
└─────────────────────┘  └───────────────────────────────────────┘

ROW 3: Fleet Trends + Alerts
┌──────────────────────────┐ ┌────────────────────────────────────┐
│  MetricChart: Avg Score  │ │  AlertList                         │
│  + hosts_below_threshold │ │  All compliance alerts fleet-wide  │
│  (w:6, h:7)             │ │  (w:6, h:7)                        │
└──────────────────────────┘ └────────────────────────────────────┘
```

## Widget specs

1. **hosts_scanned** (Scoreboard) — Summary|total_hosts on ComplianceWorld, color_method:1
2. **avg_score** (Scoreboard) — Summary|avg_host_score on ComplianceWorld, red<80/orange<90/yellow<95
3. **below_threshold** (Scoreboard) — Summary|hosts_below_threshold on ComplianceWorld, yellow≥1/orange≥2/red≥3
4. **active_profile** (Scoreboard) — Summary|profile_name on ComplianceWorld, is_string_metric:true
5. **score_heatmap** (Heatmap) — VCF-CF Compliance|score on VMWARE/HostSystem, green→red
6. **host_overview_view** (View) — [VCF Content Factory] Compliance Host Overview
7. **fleet_trend** (MetricChart) — avg_host_score + hosts_below_threshold on ComplianceWorld
8. **fleet_alerts** (AlertList) — all compliance alerts, criticality [2,3,4]

## Interactions

None. All widgets are self-provider with pins.

## Correction 2026-10-12: alert widget filter and input depth

### Initial prompt (Scott, verbatim)

> Dashboards for this pak:
> The alert widgets show blank.  The alert widget should be updated to filter on Alert Type: "Application ALerts Compliance" since that is how we have defined all of our compliance pak alerts.
>
> Additionally, the input transformation depth needs to be updated to an appropriate depth based on the input object - to cover all the children of that object

### Vision

Every AlertList widget in the five compliance dashboards (compliance-overview,
compliance-environment-overview, compliance-esxi-hosts, compliance-vms,
compliance-vcenter-networking) filters by alert type rather than by a pinned
list of alert definition ids. Every alert the pak ships is declared in
describe.xml as `type="15" subType="21"` (Application / Compliance), so the
widget filter is the alert type code `15_21` (loader field `alert_types`).
The `alert_definitions` pin is removed; it is the suspected cause of the blank
widgets and is redundant once the type filter is in place.

The widget's input depth (loader field `depth`, the Input Transformation
depth in the UI) is sized per widget from the object that feeds it, so that
the widget reaches every descendant that can carry a compliance alert
(VMwareAdapter Instance, Cluster, HostSystem, VirtualMachine, vDS, Distributed
Port Group), following the VMWARE relationship tree. Each chosen depth is
justified in a YAML comment on the widget. Layout, coords and interactions
are unchanged, so the RULE-011 wireframe gate does not re-open.
