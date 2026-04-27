# Design Artifact: Demand-Driven Capacity Planning v2

## Original Request

> I like the work you did on the Demand-Driven Capacity dashboard. In parallel I
> created [Custom] Demand Based Capacity Overview. I like some of what you did —
> the host contention outliers, vSAN etc. I mostly prefer my aesthetic taste —
> especially how I slimmed the Object list down to be a true selector — as the
> narrow single row design you took really makes it hard for a user to scroll
> around. I also think it's really important that we show in terms of percentage
> rather than raw numbers as it's easier for the user to understand. I'm also
> getting fond of the comparison between usable capacity and provisioned capacity.
> Can you review the two dashboards and based on the feedback create a
> demand-driven capacity v2 dashboard. Don't throw v1 out or modify it.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Memory demand unit | Raw auto-unit (GB/TB), not % | Matches Scott's custom dashboard pattern. No SM needed. Users compare against usable memory column. |
| VM detail view | Replace balloon/swap with storage latency | Scott's preference — CPU Ready + Co-Stop + Mem Contention + Read/Write Latency covers the key pain signals. Balloon/swap are secondary. |
| Heatmap scoping | Driven by ResourceList (DC level) | Heatmaps show broad visual scanning at DC level; detail views are driven by cluster row selection — two interaction tiers. |
| V1 preservation | Untouched — v2 is a new dashboard | Track factory's growth in capabilities. V1 views reused where unchanged. |

## Side-by-Side Analysis

| Aspect | V1 (Factory) | Scott's Custom | V2 (take from) |
|---|---|---|---|
| Scope picker | Full-width w=12, h=3 | Narrow w=2, h=8 left column | Scott's |
| Cluster view position | Below picker, full-width | Beside picker (w=10), same row | Scott's |
| Metric units | Raw MHz/KB | Percentages first, GHz/auto for absolutes | Scott's |
| Usable vs Provisioned | Only usable (post-HA) | Usable + Provisioned + Demand triangle | Scott's |
| Contention P95 | Not in cluster view | Both avg and P95 contention | Scott's |
| Visual scanning | No heatmaps | VM + Host contention heatmaps | Scott's |
| Host outlier detail | Dedicated view | Not present | V1 |
| vSAN contribution | Per-host vSAN latency/IOPS/congestion | Not present | V1 |
| VM contention detail | Ready, Co-Stop, balloon, swap | CPU demand/contention + storage latency | Merge |

## Dashboard Mockup

```
+---------+--------------------------------------------------------------+
| Select  |  Cluster Demand & Capacity Overview (v2)                     |
| vCenter |  +--------------------------------------------------------+  |
| or DC   |  | Name |CPU   |CPU   |CPU   |CPU   |Usable|Prov'd|Mem  |  |
|         |  |      |Demand|Demand|Contn |Contn |CPU   |CPU   |Dem  |  |
| [list]  |  |      |Avg % |P95 % |Avg % |P95 % |(GHz) |(GHz) |Avg  |  |
|         |  +------+------+------+------+------+------+------+-----+  |
| w=2     |  |Clus-A|  42% |  58% |  3%  |  7%  | 240  | 180  | 61G |  |
| h=8     |  |Clus-B|  78% |  92% | 12%  | 18%  | 120  | 155  | 85G |  |
|         |  +--------------------------------------------------------+  |
|         |  + Mem Demand P95, Usable Mem, Allocated Mem   w=10, h=8     |
+---------+-------------------+------------------+-----------------------+
|                             |                  |                       |
| VM Contention Heatmap       | Host Contention  | Host Contention       |
| color = contention %        | Heatmap          | Outliers (v1 view)    |
| size  = demand %            | color=contn %    | sorted worst-first    |
| group by: Host              | size=demand %    |                       |
| w=4, h=6                    | group: Cluster   | w=4, h=6              |
|                             | w=4, h=6         |                       |
+-----------------------------+------------------+-----------------------+
|                                    |                                   |
| VM Contention v2                   | Per-Host vSAN Contribution        |
| CPU Ready Avg/P95, Co-Stop P95,   | (v1 view)                         |
| Mem Contention, Read/Write Latency | Read/Write IOPS, Latency,        |
| w=6, h=7                          | Congestion                        |
|                                    | w=6, h=7                          |
+------------------------------------+-----------------------------------+
```

### Interaction Wiring

```
ResourceList (vCenter/DC) --resourceId--> Cluster Demand & Capacity (v2)
                          --resourceId--> VM Contention Heatmap
                          --resourceId--> Host Contention Heatmap

Cluster view (row select) --resourceId--> Host Contention Outliers
                          --resourceId--> VM Contention v2
                          --resourceId--> Per-Host vSAN Contribution
```

## Cluster Demand & Capacity Overview v2 — Columns

| # | Metric key | Display name | Unit | Transform | Thresholds |
|---|---|---|---|---|---|
| 1 | cpu\|demandPct | CPU Demand Avg | percent | AVG | 50y/70o/85r |
| 2 | cpu\|demandPct | CPU Demand P95 | percent | P95 | 60y/80o/90r |
| 3 | cpu\|capacity_contentionPct | CPU Contention Avg | percent | AVG | 5y/10o/20r |
| 4 | cpu\|capacity_contentionPct | CPU Contention P95 | percent | P95 | 7y/15o/25r |
| 5 | cpu\|haTotalCapacity_average | Usable CPU (GHz) | ghz | CURRENT | — |
| 6 | cpu\|vm_capacity_provisioned | Provisioned CPU (GHz) | ghz | CURRENT | — |
| 7 | mem\|host_demand | Mem Demand Avg | auto | AVG | — |
| 8 | mem\|host_demand | Mem Demand P95 | auto | P95 | — |
| 9 | mem\|haTotalCapacity_average | Usable Memory | auto | CURRENT | — |
| 10 | mem\|memory_allocated_on_all_powered_on_vms | Allocated Memory | auto | CURRENT | — |

## VM Contention v2 — Columns

| # | Metric key | Display name | Unit | Transform | Thresholds |
|---|---|---|---|---|---|
| 1 | cpu\|readyPct | CPU Ready Avg (24h) | percent | AVG | 5y/10o/20r |
| 2 | cpu\|readyPct | CPU Ready P95 (24h) | percent | P95 | 5y/10o/20r |
| 3 | cpu\|costopPct | Co-Stop P95 (24h) | percent | P95 | 3y/5o/10r |
| 4 | mem\|host_contentionPct | Mem Contention Avg (24h) | percent | AVG | 2y/5o/10r |
| 5 | storage\|totalReadLatency_average | Read Latency Avg (24h) | auto | AVG | — |
| 6 | storage\|totalWriteLatency_average | Write Latency Avg (24h) | auto | AVG | — |

## Content Inventory

| # | Type | File | Status |
|---|---|---|---|
| 1 | View | views/cluster_demand_capacity_v2.yaml | NEW |
| 2 | View | views/vm_contention_v2.yaml | NEW |
| 3 | Dashboard | dashboards/demand_driven_capacity_v2.yaml | NEW |
| 4 | View | views/host_contention_outliers.yaml | REUSE from v1 |
| 5 | View | views/host_vsan_contribution.yaml | REUSE from v1 |

Super metrics: none needed. All built-in VMWARE adapter metrics.

---

## Revision 2026-04-27 — vCPU:pCPU column + right-side explainer

### Prompt

> I'd like to make a revision to the Demand-Drive Capacity Planning v2
> dashboard. on the cluster demand and capacity overview, between
> Contention P95, let's add a vCPU:pCPU ratio - i beleive there is an
> OOTB metric for this.
>
> Also i'd like a small text widget placed maybe to the left of the
> capcity overview dashboard (we would need to shrink it a bit) that
> gives a bit of an explanation of some of the metrics in the overview
> - namely what the heck is provisioned CPU?

(Clarified during planning: column lands *after* CPU Contention P95;
explainer goes to the *right* of the overview, not the left — "click
the datacenter, view the stats, scan right to see the explanation".)

### Decision

- **vCPU:pCPU Ratio column** uses OOTB metric
  `cpu|vcpus_to_cores_allocation_ratio` (UI display name "CPU|Current
  Overcommit Ratio", `default_monitored: true`). Found in
  `context/adapter_describe_cache/VMWARE/ClusterComputeResource.json:1409`.
  Initial recon missed it because the markdown extract at
  `docs/vcf9/metrics-properties.md` doesn't list it; user push-back
  ("what about CPU|Current Overcommit ratio?") corrected the omission.
  No super metric needed.
- **Thresholds**: yellow 4.0 / orange 6.0 / red 8.0, descending range
  (higher is worse). Maps to vSphere overcommit tiers — below 4:1
  healthy, 4–6:1 watch, 6–8:1 warn, above 8:1 critical.
- **Explainer placement**: right of the cluster overview, not left.
  Reading flow is scope-pick → table → glossary.
- **Width split**: explainer w:3, cluster overview w:7 (was w:10);
  scope picker w:2 unchanged.
- **Explainer scope**: Provisioned CPU (GHz), Usable CPU (GHz), CPU
  Demand %. (Contention % deliberately omitted — user did not ask
  for it; the column display already implies the "is this hurting"
  read.)

### New Row 1 layout

```
+-------+----------------------------------+--------------+
| picker|         cluster_overview          | explainer    |
| (2)   |              (7)                  |    (3)       |
|       |                                   |              |
+-------+----------------------------------+--------------+
  x:1     x:3                                 x:10
```

### Cluster Demand & Capacity Overview v2 — revised columns

| # | Metric key | Display name | Unit | Transform | Thresholds |
|---|---|---|---|---|---|
| 1 | cpu\|demandPct | CPU Demand Avg | percent | AVG | 50y/70o/85r |
| 2 | cpu\|demandPct | CPU Demand P95 | percent | P95 | 60y/80o/90r |
| 3 | cpu\|capacity_contentionPct | CPU Contention Avg | percent | AVG | 5y/10o/20r |
| 4 | cpu\|capacity_contentionPct | CPU Contention P95 | percent | P95 | 7y/15o/25r |
| **5** | **cpu\|vcpus_to_cores_allocation_ratio** | **vCPU:pCPU Ratio** | **(none)** | **CURRENT** | **4y/6o/8r** |
| 6 | cpu\|haTotalCapacity_average | Usable CPU (GHz) | ghz | CURRENT | — |
| 7 | cpu\|vm_capacity_provisioned | Provisioned CPU (GHz) | ghz | CURRENT | — |
| 8 | mem\|host_demand | Mem Demand Avg | auto | AVG | — |
| 9 | mem\|host_demand | Mem Demand P95 | auto | P95 | — |
| 10 | mem\|haTotalCapacity_average | Usable Memory | auto | CURRENT | — |
| 11 | mem\|memory_allocated_on_all_powered_on_vms | Allocated Memory | auto | CURRENT | — |

### Files touched

| File | Change |
|---|---|
| `views/cluster_demand_capacity_v2.yaml` | Inserted column 5 (vCPU:pCPU Ratio); old 5–10 shifted to 6–11. UUID unchanged. |
| `dashboards/demand_driven_capacity_v2.yaml` | `cluster_overview` w:10 → w:7; new `overview_explainer` TextDisplay at `{x:10, y:1, w:3, h:8}`. UUID + interactions unchanged. |
