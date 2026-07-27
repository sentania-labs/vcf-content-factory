# Design: Total Snapshot Space (GB) — super metric

## Initial prompt

Derived requirement, 2026-07-27. Parent request: "Active VM Snapshot
Inventory" (see knowledge/designs/views/vm-snapshot-inventory.md for the
verbatim ticket). The user-approved dashboard wireframe
(knowledge/designs/dashboards/vm-snapshot-inventory.md) includes a
scoreboard tile:

> | Scoreboard: Total snapshot space (GB, fleet) |

dashboard-author reported blocked-upstream: no built-in vSphere World-scope
metric provides a fleet-wide sum of VM snapshot space (verified against
recon 2026-07-27 and world-scope scoreboard precedents).

## Vision

- World-scope (vSphere World) super metric: SUM of `diskspace|snapshot`
  (GB) across VMWARE VirtualMachine descendants.
- Consumed by a Scoreboard widget (`self_provider: true`,
  `pin: {resource_kind: vSphere World}`) on the VM Snapshot Inventory
  dashboard, unit GB.
- `diskspace|snapshot` chosen over `summary|snapshotSpace` for consistency
  with the view's filter/columns; both are flat per-VM GB metrics
  (recon 2026-07-27).
