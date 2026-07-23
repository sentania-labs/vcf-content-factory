# Dashboard: CPU Support Status (KB 318697)

## Initial prompt (verbatim)

> I'd like a dashboard that helps me identify CPU support in relation to
> vsphere. The official source of record is:
> https://knowledge.broadcom.com/external/article/318697/cpu-support-deprecation-and-discontinuat.html
>
> If i were to build this, I would probably create a number of Groups or
> a super metric that joined thigns together in "supported"/unsupport"
> and the display it.
>
> I'd like the dashboard to have a scoping tier, that then lists all
> hosts in the scope with: hostname, model, CPU model, deprecated,
> discontinued, discontinued 9.2, supported.

(Clarification thread: knowledge/designs/supermetrics/cpu-support-status.md.)

## Vision

- Dashboard `[VCF Content Factory] CPU Support Status`
  (`content/dashboards/cpu_support_status.yaml`).
- Scoping tier (clusters) drives a host list view showing per-host CPU
  support classification against Broadcom KB 318697, via the single
  coded supermetric (0=supported … 3=discontinued-9.2).
- Interaction pattern from content/dashboards/fleet_capacity_rightsizing.yaml;
  self-provider widgets use pin_to_world (heatmap-empty-groupby lesson:
  selfProvider + empty resource list silently never queries).

## Wireframe (RULE-011 — approved with plan, 2026-07-22)

```
+--------------------------------------------------------------+
| Row 1  SCOPE TIER                                            |
| +----------------------------------------------------------+ |
| | Object List: vSphere Clusters (self-provider,            | |
| | pin_to_world, auto-select first)                         | |
| +----------------------------------------------------------+ |
| Row 2  HOST STATUS LIST (interaction: cluster selection ->)  |
| +----------------------------------------------------------+ |
| | View: CPU Support Status by Host                         | |
| | host | model | CPU model | CPU Support Status (0-3)      | |
| +----------------------------------------------------------+ |
+--------------------------------------------------------------+
```

- Row 1: Object List widget, vSphere Cluster (ClusterComputeResource),
  self-provider, pinned to vSphere World, auto-select first row.
- Row 2: View widget embedding "CPU Support Status by Host"; receives
  the cluster resourceId from Row 1 selection.
- Status legend (0-3 mapping + KB 318697 citation) surfaced in the view
  description / widget title. No third row (fleet scoreboards deferred
  unless requested).

### Amendment (2026-07-22) — scope-tier picker broadened to 3 kinds

Row 1 picker now lists three resource kinds, in this order: `vSphere
World`, `VMwareAdapter Instance` (vCenter), `ClusterComputeResource`
(all `adapter_kind: VMWARE`) — instead of ClusterComputeResource only.
Widget title changed to "Scope (World / vCenter / Cluster)". Intent:
selecting a World row surfaces every host in scope, including
standalone hosts belonging to no cluster (e.g. `vcf-lab-mgmt-esx05`);
selecting a vCenter row scopes to that vCenter's hosts; selecting a
Cluster row preserves original behavior. Geometry, widget count, and
interaction wiring (`cluster_picker` → `cpu_support_status_view` via
`resourceId`) are unchanged — non-layout tweak, no RULE-011
re-wireframe required. Precedent for multi-kind ResourceList:
`content/dashboards/quarterly_capacity_review.yaml` and
`content/dashboards/demand_driven_capacity_v2.yaml`.

### Amendment v2 (2026-07-22) — tiered scoping layout (RULE-011 approved with plan)

User concern: cluster-only picker gets too long in large environments.
Approved v2 wireframe:

```
+--------------------------------------------------+
| Row 1  Scope picker (ResourceList)               |
|        kinds: vSphere World, VMwareAdapter       |
|        Instance ONLY (cluster kind removed —     |
|        clusters now live in Row 2)               |
+--------------------------------------------------+
| Row 2  View: CPU Support Status by Cluster       |
|        <- picker (resourceId)                    |
|        cluster | worst status (0-3, colored)     |
+--------------------------------------------------+
| Row 3  View: CPU Support Status by Host          |
|        <- picker AND <- cluster view (dual       |
|        provider, most-recent-selection wins)     |
|        host | model | CPU model | status         |
+--------------------------------------------------+
```

- Host→cluster reverse drill (cycle) not possible; native object links
  are the drill-back. Dual-provider on Row 3 per user: "It can be
  driven by both. The most recently selected is what drives the
  population." If the loader cannot express two interactions targeting
  one receiver, that is a TOOLSET GAP → tooling.
- Cluster roll-up column: worst status only (user choice).
- 1-based coords per DEF-013.

### Fix (2026-07-22) — Row 2 `select_first_row: false`

Row 2's default auto-select was re-firing the `resourceId` interaction
into Row 3 on every Row 1 selection, permanently pinning Row 3 to the
first cluster and breaking the intended most-recent-selection-wins
behavior. `cpu_support_status_cluster_view` now sets
`select_first_row: false`, so Row 1 drives Row 3 directly and Row 2
only drives it on an explicit user click. Row 1 (picker) and Row 3
(terminal, no receivers) are unchanged.

### Amendment v2.1 (2026-07-22) — side-by-side scope tier, taller pickers

User feedback on v2 screenshot: "vcenter vsphere world select needs more
height so you don't have to scroll. Like it should be like 10-20 high.
Maybe next to the cluster selector not above…"

```
+---------------------------+------------------------------------+
| Scope (World / vCenter)   | CPU Support Status by Cluster      |
| ResourceList              | (worst status roll-up)             |
| x:1 y:1 w:5 h:10          | x:6 y:1 w:7 h:10                   |
+---------------------------+------------------------------------+
| CPU Support Status by Host (all columns)                       |
| x:1 y:11 w:12 h:12                                             |
+----------------------------------------------------------------+
```

Interactions and select_first_row settings unchanged — pure geometry.

`cluster_picker` now sets `column_preset: name-only` so the scope picker's
grid shows only the Name column (Adapter Type/Object Type/Policy/
Collection columns hidden as noise in a picker).
