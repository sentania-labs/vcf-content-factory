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

## Correction (2026-07-27, post-initial-authoring)

User correction, relayed via orchestrator: the companion view's table
was changed to show only snapshots with instanced `numberOfDays > 0`
(aged, live snapshots). A snapshot's instanced properties, including
Age, populate once the snapshot is **24 hours old**; `RECLAIM_SNAPSHOTS_DAYS`
governs reclamation/cost math only, not property materialization
(corrected doctrine — see "Snapshot ageing: the gate is 24 HOURS" in
`knowledge/context/investigations/vm-snapshot-instanced-fanout-2026-07-27.md`,
citing `reference/docs/extracted/brockpeterson-vm-snapshots-aria-operations/article.txt`;
an earlier draft here incorrectly attributed the gate to
`RECLAIM_SNAPSHOTS_DAYS=7`). The original threshold
(`diskspace|snapshot > 0.0001`, i.e. "has any snapshot space") no longer
matches the table's population rule and had to be re-aligned.

**Predicate change:** `diskspace|snapshot > 0.0001` (space-based) →
`diskspace|snapshot|snapshotAge > 0` (age-based), matching the view's
`numberOfDays > 0` gate at VM granularity. The scoreboard cannot
aggregate the view's per-snapshot instanced key directly (a count()
loop needs a per-VM value, not a per-snapshot fan-out), so it uses the
flat, per-VM property `diskspace|snapshot|snapshotAge` as the closest
available proxy for "this VM has at least one aged snapshot."

**DSL challenge:** `diskspace|snapshot|snapshotAge` is PROPERTY-ONLY on
this platform — confirmed absent from `/statkeys` live (recon
2026-07-27, "Active VM Snapshot Inventory" section,
`knowledge/context/investigations/recon_log.md`). Per the DSL's
documented property-vs-metric addressing rule (`metric=` slot accepts
both real metric keys and property keys — see
`knowledge/context/authoring/supermetric_authoring.md` §3, "Metric vs
property targets"; also `vcfops-supermetric-dsl` skill pitfall #5), and
per the existing canonical Dialect A example that already uses a bare
*property* key (`summary|config|type equals VMOperator`, not a metric)
in a `where=` clause, a numeric `where="diskspace|snapshot|snapshotAge
> 0"` clause is expressible under the established grammar. This is not
a novel construct — it follows the same property-key-in-where pattern
already in use elsewhere in the repo, just with a numeric operator
instead of `equals`.

**LIVE-VERIFIED 2026-07-27:** installer synced the corrected SM to
devel and confirmed computed value **2.0** — exactly the expected
docker + vcf-lab-avi-wld01-node0 population — read via statkey
`Super Metric|sm_77dca431-…` after one compute cycle, with the
timestamp advanced past baseline. This replaces the prior ungated
count of 5 and confirms the age-based predicate is correctly scoped.

**General DSL fact now proven:** a numeric `where=` clause on a
PROPERTY-ONLY key (absent from `/statkeys`) computes correctly on
VCF Ops 9.1.0.0 — the property-vs-metric addressing rule (`metric=`
slot accepts both real metric keys and property keys) extends to
where-clause predicates, not just the aggregated value itself. This
was previously grounded only in DSL doc/skill guidance and an
analogous string-operator precedent; it is now empirically confirmed
end-to-end (formula → sync → compute → correct value) rather than
inferred.

**Formula (current):**
```
count(${adaptertype=VMWARE, objecttype=VirtualMachine,
       metric=diskspace|snapshot|snapshotAge, depth=5,
       where="diskspace|snapshot|snapshotAge > 0"})
```
