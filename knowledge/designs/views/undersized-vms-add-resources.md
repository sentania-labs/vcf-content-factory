# Design — [VCF Content Factory] Undersized VMs — Add Resources (view)

Part of the **Fleet Capacity & Rightsizing** dashboard (Band D-2). See
`knowledge/designs/dashboards/fleet-capacity-rightsizing.md`.

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

---

## Change: 2026-11-17 (current size and 30-day usage columns)

**Initial prompt (verbatim):**

> Additionally, I'd liek the oversized VMs and undersized VMs dashboard to have:
> CPU Demand Avg, CPU Demand Max. CPU Demand P95, Memory Usage avg, memory Usage Mx, Memory P95 utilizatio, along with how much memory and CPU they have - so we can gauge better the affect it.
>
> SO like vCPU, Allocated Mem, CPU Avg, CPU Max, CPU P95, Mem Av, Mem Max, P95 (30 day spans).

**Vision:** show what the VM has now and how it was used over the last 30
days next to the engine's recommendation, so the effect of a resize can be
judged from the list. Column order and keys: see the 2026-11-17 change
section of `knowledge/designs/dashboards/fleet-capacity-rightsizing.md`.
