# Design: Compliance Fleet Overview Dashboard

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
