# Design — [VCF Content Factory] Datastore Reclaimable Space (view)

Part of the **Fleet Capacity & Rightsizing** dashboard (Band E). See
`knowledge/designs/dashboards/fleet-capacity-rightsizing.md`.

## Vision
A list view of datastores showing total/used capacity plus reclaimable space
from snapshots and orphaned disks. Covers the "Snapshots & orphaned disk"
rightsizing focus. Driven by the dashboard's cluster selection (fleet-wide by
default).

## View spec
- **Type:** list view
- **Subject:** `Datastore` (VMWARE adapter)
- **Sort:** by `diskspace|snapshot` descending (largest snapshot consumers first)

### Columns
| Column label | Source key | Notes |
|---|---|---|
| Datastore | resource name | |
| Total (GB) | `capacity|total_capacity` | metric |
| Used % | `capacity|usedSpacePct` | metric |
| Free (GB) | `capacity|available_space` | metric |
| Snapshot Space (GB) | `diskspace|snapshot` | metric |
| Orphaned Disk (GB) | `reclaimable|orphaned_disk|diskspace` | metric |

## Constraints
- Built-in metrics only, all confirmed live by recon.
