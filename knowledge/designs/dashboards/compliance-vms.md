# [VCF Content Factory] Compliance VMs

- **Type:** dashboard (bundled in the compliance pak)
- **Slug:** compliance-vms
- **Authored YAML:** content/sdk-adapters/compliance/dashboards/compliance-vms.yaml
- **Date:** 2026-09-23
- **Status:** mock approved and authored 2026-09-23; ships in adapter build 61
- **Mock:** knowledge/designs/dashboards/compliance-vms.html
- **Parent design:** knowledge/designs/sdk-adapters/compliance-v3-version-aware.md

## Initial prompt

See the parent design note for the verbatim prompts. The relevant ask
(Scott, 2026-09-23):

> Like a Top level: Environment overview with a breakdown by object type and then different dashboards that drill into each object: vCenter Server, ESXi host, vDS, VM, etc.

## Vision

The ESX Hosts pattern applied to VMs, sized for thousands of objects:
pick a scope, see the VMs in it worst first, select one to see its
failing controls with runbooks. No heatmap: at VM counts it stops being
readable; the sorted list and its totals row carry the overview.

## Keys

Adapter v3 build 60 key list (per-object, on `VMWARE / VirtualMachine`):
`VCF-CF Compliance|score`, `|pass_count`, `|fail_count`,
`|total_count`, `|unreadable_count`, `|non_compliant`, `|no_benchmark`,
`|profile_name`. Known-good VMWARE keys used across reference content:
`summary|parentHost`, `summary|parentCluster`, `summary|parentVcenter`.

## Wireframe

| # | Widget | Type | Grid (col, row, w, h) | Subject | Metrics / content |
|---|---|---|---|---|---|
| W1 | Scope | ResourceList | 1, 1, 3, 12 | `vSphere World`, `VMwareAdapter Instance` | Picker, name column only (`column_preset: name-only`). Drives W2 |
| W2 | VM Compliance | View | 4, 1, 9, 12 | driven by W1, descendants of kind `VirtualMachine` | New view (below), score ascending. Selection drives W3, W4, W5 |
| W3 | Failing Controls on Selected VM | AlertList | 1, 13, 7, 8 | driven by W2 | explicit `alert_definitions` list of the generated `vm.*` alert definitions, criticality warning and up |
| W4 | Compliance Details | PropertyList | 8, 13, 5, 8 | driven by W2 | `summary\|parentHost`, `VCF-CF Compliance\|profile_name`, `\|total_count`, `\|pass_count`, `\|fail_count`, `\|unreadable_count` |
| W5 | Score Trend | MetricChart | 1, 21, 12, 5 | driven by W2 | `VCF-CF Compliance\|score` and `\|fail_count`, 30 days |

Interactions: W1 drives W2; W2 row selection drives W3, W4, W5.

## New view: Compliance VM Detail (subject `VirtualMachine`)

| Column | Key | Notes |
|---|---|---|
| VM | name | |
| Host | `summary\|parentHost` | the SCG follows this host's ESX version |
| Cluster | `summary\|parentCluster` | |
| vCenter | `summary\|parentVcenter` | |
| SCG applied | `VCF-CF Compliance\|profile_name` | |
| Score (%) | `VCF-CF Compliance\|score` | red < 80, orange < 90, yellow < 95 |
| Failing | `VCF-CF Compliance\|fail_count` | |
| Unreadable | `VCF-CF Compliance\|unreadable_count` | |
| Non-compliant | `VCF-CF Compliance\|non_compliant` | 0/1 |
| No SCG | `VCF-CF Compliance\|no_benchmark` | 0/1 |

Summary row: VM count, average score, sums of Failing, Non-compliant,
No SCG. Score columns filtered to `no_benchmark = 0` and
`total_count > 0` so a retained old score never shows as current
(review of build 57, W2).

## Known constraints

- At prod scale a vSphere World scope lists every VM; the view pages
  and sorts server side, so worst-first still works, but the default
  selection may move to the first vCenter if load time is poor on the
  first install.
- Unreadable VM settings raise no per-control alert (Compliant = -1) but
  count as failing in the score (build 63); the object counts as
  non-compliant, the Unreadable column shows them, and a "Compliance data
  not collected" alert says why.

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
