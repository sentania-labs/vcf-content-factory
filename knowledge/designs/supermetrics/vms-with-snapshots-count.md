# Design: VMs with Snapshots (Count) — super metric

## Initial prompt

Derived requirement, 2026-07-27. Parent request: "Active VM Snapshot
Inventory" (see knowledge/designs/views/vm-snapshot-inventory.md for the
verbatim ticket). The user-approved dashboard wireframe
(knowledge/designs/dashboards/vm-snapshot-inventory.md) includes a
scoreboard tile:

> | Scoreboard: VMs with snapshots (count) |

dashboard-author reported blocked-upstream: no built-in vSphere World-scope
metric provides a fleet-wide count of VMs carrying snapshots (verified
against recon 2026-07-27 and world-scope scoreboard precedents in
capacity_assessment.yaml / fleet_capacity_rightsizing.yaml).

## Vision

- World-scope (vSphere World) super metric: COUNT of VMWARE
  VirtualMachine descendants where `diskspace|snapshot > 0.0001`
  (same threshold as the view's subject filter, for consistency).
- Consumed by a Scoreboard widget (`self_provider: true`,
  `pin: {resource_kind: vSphere World}`) on the VM Snapshot Inventory
  dashboard.
- Ghost caveat does not apply: flat `diskspace|snapshot` reflects live
  snapshot space, not ghost instanced properties.
