# Design — [VCF Content Factory] Undersized VMs — Add Resources (view)

Part of the **Fleet Capacity & Rightsizing** dashboard (Band D-2). See
`designs/dashboards/fleet-capacity-rightsizing.md`.

## Vision
A list view of undersized VMs (performance-risk counterpart to reclamation) and
the resources each needs. Driven by the dashboard's cluster selection
(fleet-wide by default).

## View spec
- **Type:** list view
- **Subject:** `VirtualMachine` (VMWARE adapter)
- **Filter:** `summary|undersized == 1`
- **Sort:** by `summary|undersized|vcpus` descending

### Columns
| Column label | Source key | Notes |
|---|---|---|
| VM | resource name | |
| Cluster | parent cluster | relationship/ancestor — author resolves the cluster column form |
| vCPUs to Add | `summary|undersized|vcpus` | metric |
| Memory to Add (GB) | `summary|undersized|memory` | KB — format GB if possible |

## Constraints
- Built-in metrics only. `summary|undersized` confirmed live (0 currently — view may be empty, expected).
