# Design — [VCF Content Factory] Oversized VMs — Reclaimable (view)

Part of the **Fleet Capacity & Rightsizing** dashboard (Band D-1). See
`knowledge/designs/dashboards/fleet-capacity-rightsizing.md`.

## Vision
A list view of oversized VMs and what can be reclaimed from each. Driven by
the dashboard's cluster selection (filters to the selected cluster; fleet-wide
by default).

## View spec
- **Type:** list view
- **Subject:** `VirtualMachine` (VMWARE adapter)
- **Filter:** `summary|oversized == 1`
- **Sort:** by `summary|oversized|vcpus` descending (biggest reclaim first)

### Columns
| Column label | Source key | Notes |
|---|---|---|
| VM | resource name | |
| Cluster | parent cluster | relationship/ancestor — author resolves the cluster column form |
| vCPUs to Remove | `summary|oversized|vcpus` | metric |
| Memory to Remove (GB) | `summary|oversized|memory` | KB — format GB if possible |

## Constraints
- Built-in metrics only. `summary|oversized` confirmed live (2 VMs currently oversized).
