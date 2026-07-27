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

## Correction (2026-07-27, post-initial-authoring)

User correction, relayed via orchestrator: the companion view's table was
changed to show only snapshots with instanced `numberOfDays > 0` (aged,
live snapshots). `RECLAIM_SNAPSHOTS_DAYS=7` gates when the per-snapshot
instanced properties populate — younger snapshots can take up to ~a week
(sometimes as little as ~24h) before their instanced properties appear.
The scoreboard must align with the same gate. Same predicate change as
applied to the companion count SM
(`knowledge/designs/supermetrics/vms-with-snapshots-count.md`):
`diskspace|snapshot|snapshotAge > 0` in the where clause, gating which
VMs' snapshot space is summed.

**Predicate change:** unconditional sum of `diskspace|snapshot` over all
VirtualMachine descendants → sum gated by
`where="diskspace|snapshot|snapshotAge > 0"` (metric summed remains
`diskspace|snapshot`; the where clause filters to VMs carrying at least
one aged snapshot).

**Semantics note:** `diskspace|snapshot` is a flat per-VM total, so this
sums the WHOLE snapshot space of any VM with at least one aged snapshot —
it cannot split young vs. aged space within a single VM. On current devel
data this is identical to a strict per-snapshot aged sum (no VM currently
mixes aged and non-aged snapshots).

**DSL grounding:** same as the companion count SM —
`diskspace|snapshot|snapshotAge` is PROPERTY-ONLY on this platform
(confirmed absent from `/statkeys`, recon 2026-07-27, "Active VM Snapshot
Inventory" section, `knowledge/context/investigations/recon_log.md`). Per
the DSL's documented property-vs-metric addressing rule (`vcfops-
supermetric-dsl` skill pitfall #5; `knowledge/context/authoring/
supermetric_authoring.md` §3) and the existing canonical Dialect A example
using a bare property key in a where clause (`summary|config|type equals
VMOperator`), a numeric `where="diskspace|snapshot|snapshotAge > 0"`
clause is expressible under the established grammar.

**LIVE-VERIFIED 2026-07-27:** installer confirmed the corrected SM on
devel — computed **12.522092819213867 GB** (expected ≈12.5: docker 8.33 +
avi 4.19), statkey `Super Metric|sm_faab0b29-…`, timestamp advanced past
baseline after one compute cycle. This proves the DSL fact (matching the
companion count SM's finding): a numeric where-clause on a property-only
key (`diskspace|snapshot|snapshotAge > 0`) computes correctly on 9.1.0.0.

**Formula (current):**
```
sum(${adaptertype=VMWARE, objecttype=VirtualMachine,
      metric=diskspace|snapshot, depth=5,
      where="diskspace|snapshot|snapshotAge > 0"})
```
