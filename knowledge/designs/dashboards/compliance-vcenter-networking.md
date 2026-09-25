# [VCF Content Factory] Compliance vCenter & Networking

- **Type:** dashboard (bundled in the compliance pak)
- **Slug:** compliance-vcenter-networking
- **Authored YAML:** content/sdk-adapters/compliance/dashboards/compliance-vcenter-networking.yaml
- **Date:** 2026-09-23
- **Status:** mock approved and authored 2026-09-23; ships in adapter build 61
- **Mock:** knowledge/designs/dashboards/compliance-vcenter-networking.html
- **Parent design:** knowledge/designs/sdk-adapters/compliance-v3-version-aware.md

## Initial prompt

See the parent design note for the verbatim prompts. The relevant ask
(Scott, 2026-09-23):

> Like a Top level: Environment overview with a breakdown by object type and then different dashboards that drill into each object: vCenter Server, ESXi host, vDS, VM, etc.

Orchestrator proposal accepted in the same session: vCenter, cluster,
vDS and portgroup share one dashboard because they carry few scored
controls (build 57 alerts: vCenter 15, vDS 11, portgroup 7, cluster 2).

## Vision

One page for the four low-count object types. Four compact lists, one
per type, each worst first, all scoped by one picker. Selecting any
row in any list shows that object's failing controls and runbooks in a
single shared alert list.

## Keys

Per-object keys from adapter v3 build 60 on `VMwareAdapter Instance`,
`ClusterComputeResource`, `VmwareDistributedVirtualSwitch`,
`DistributedVirtualPortgroup`: `VCF-CF Compliance|score`,
`|fail_count`, `|unreadable_count`, `|non_compliant`, `|no_benchmark`,
`|profile_name`. Observed by recon: `summary|version` on the vCenter
and on the vDS (vDS reports its own 9.0.0 under vCenter 9.1.1).

## Wireframe

| # | Widget | Type | Grid (col, row, w, h) | Subject | Metrics / content |
|---|---|---|---|---|---|
| W1 | Scope | ResourceList | 1, 1, 3, 12 | `vSphere World`, `VMwareAdapter Instance` | Picker, name column only (`column_preset: name-only`). Drives W2 to W5 |
| W2 | vCenter Servers | View | 4, 1, 9, 5 | driven by W1, `VMwareAdapter Instance` | name, `summary\|version`, SCG applied, score, failing, unreadable |
| W3 | Clusters | View | 4, 6, 9, 7 | driven by W1, `ClusterComputeResource` | name, SCG applied, score, failing, unreadable |
| W4 | Distributed Switches | View | 1, 13, 6, 7 | driven by W1, `VmwareDistributedVirtualSwitch` | name, `summary\|version` (switch version, shown for context), SCG applied, score, failing, unreadable |
| W5 | Distributed Portgroups | View | 7, 13, 6, 7 | driven by W1, `DistributedVirtualPortgroup` | name, SCG applied, score, failing, unreadable |
| W6 | Failing Controls on Selected Object | AlertList | 1, 20, 12, 7 | driven by W2, W3, W4, W5 (last selection wins) | explicit `alert_definitions` list of the generated `vc.*`, `cluster.*`, `vds.*`, `dvpg.*` alert definitions, criticality warning and up |

Each list sorts by score ascending, has a totals row (count, average
score, sum failing, sum non-compliant), and filters score columns to
`no_benchmark = 0` and `total_count > 0`.

Interactions: W1 drives W2 to W5. Selecting a row in any of W2 to W5
drives W6. Several dashboards in this repo already send more than one
widget into one receiver (e.g. vSphere Network Configuration 2.0).

## Known constraints

- Clusters carry 2 scored controls; a cluster score is coarse (0, 50
  or 100). The list shows failing count beside it so that is visible.
- The vDS version column is context only. The SCG applied follows the
  vCenter version by design, so a 9.0.0 switch under a 9.1.1 vCenter
  shows SCG 9.1.
- Unreadable controls raise no per-control alert (Compliant = -1) but
  count as failing in the score (build 63); the object counts as
  non-compliant, they show in the Unreadable column, and a "Compliance
  data not collected" alert says why.

## Amendments after approval (2026-09-23)

- **Totals rows are SUM-only.** The framework allows one aggregation per
  totals row (issue #168); owner decision: ship without count and
  average for now. Wherever this note says a summary row carries a
  count or an average, read: sums of the count and flag columns only.
- **No default sort.** Embedded views open in the product default
  order; the framework drops View widget sort settings (TOOLSET GAP
  reported by dashboard-author). Click the Score header to sort.
- **Alert lists** filter by an explicit `alert_definitions` list of the
  generated per-control definitions (adapter kind VMWARE, type 15,
  subType 21), not by adapter kind.
- **Keys** are the adapter v3 build 60 contract (README.md and
  docs/overview.md in the adapter repo); build 61 ships this dashboard.
- **Retained scores (owner decision 2026-09-23, Option A).** Ops keeps
  a metric's last value when pushes stop. Score columns list every row
  and rely on the No SCG flag column beside them instead of hiding the
  score (views can only filter whole rows). The ESX heatmap has no flag
  column and may color a host by a retained score after it moves to a
  version with no SCG; accepted as rare.
- **Unreadable counts as failing** (owner decision 2026-09-23,
  build 63): unreadable controls lower the score, and a per-object
  "Compliance data not collected" alert says why.
- **Scope pickers (owner change 2026-09-23):** every compliance scope
  picker lists only vSphere World and the vCenters, and shows the name
  column only (no adapter type, object type or other columns). The
  ESX Hosts dashboard is renamed "Compliance ESX Hosts".
