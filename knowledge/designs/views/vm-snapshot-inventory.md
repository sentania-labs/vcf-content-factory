# Design: VM Snapshot Inventory (view)

## Initial prompt

Verbatim from the user's content request (2026-07-27, via remote-control):

> # Content Request: Active VM Snapshot Inventory
>
> ## Goal
> Produce VCF Operations / Aria Operations content that lists all active VM
> snapshots with: VM name, Snapshot Name, Creator, Description, Age (days),
> Snapshot Space (GB), Parent Cluster, Parent vCenter, Parent Datastore.
>
> Target version: Aria Operations 8.17 (validate behavior holds on VCF Ops 9.x).
>
> ## Known constraint (verify before designing)
> Snapshot descriptive attributes (Name, Creator, Description, Managed Object
> Reference, Number of Days Old) are exposed as *instanced* properties on the
> **Datastore** object, under Disk Space > Snapshot > snapshot-<id> > <attr>.
> The instance key is dynamic per snapshot, so the View editor's property tree
> cannot address them generically.
>
> The **Virtual Machine** object exposes only Snapshot Age (Days) and Snapshot
> Space (GB) — no name/creator/description.
>
> Before proposing a design, confirm:
> 1. Exact property key paths on both Datastore and Virtual Machine adapter
>    object types (dump them from a live instance; do not assume).
> 2. Whether the "Add instance breakdown" option on a Datastore-subject List
>    view resolves the dynamic snapshot-<id> instances into rows.
> 3. Whether Property (not Metric) type attributes are supported by instance
>    breakdown, or if that path is metric-only.
>
> ## Deliverables
> 1. A written finding: is a native View/Dashboard achievable in 8.17? Yes/No
>    with the specific reason and the version where it changes, if it does.
> 2. If YES: the View definition and a Dashboard wrapping it, following repo
>    content standards. List view, Datastore subject if that's what works,
>    with filters to exclude zero-snapshot objects.
> 3. If NO: the best native approximation (VM-subject view with Age + Space,
>    alert definition for snapshots older than N days) PLUS a documented
>    workaround for the missing attributes — REST API (/suite-api/api/resources
>    .../properties), PowerCLI, or a custom group/supermetric approach. Include
>    working sample code.
> 4. Customer-facing summary paragraph suitable for pasting into a ticket reply.
>
> ## Acceptance criteria
> - No claim about attribute availability that wasn't verified against a live
>   8.17 or 9.x instance.
> - Any exported view/dashboard JSON imports cleanly without manual editing.
> - The finding explicitly distinguishes "not present" from "present but not
>   addressable in Views."

## Vision

- Verdict is **YES** (native view achievable), but the supplied constraint was
  wrong on both halves: the instanced snapshot descriptive properties
  (`diskspace:<dsId>|snapshot:snapshot-<n>|{name,mor,numberOfDays,creator,
  description}`) live on **VMWARE VirtualMachine**, not Datastore
  (verified live, 50/50 VMs vs 0/11 datastores — VCF Ops 9.1.0.0,
  recon_log.md 2026-07-27). Datastore carries only a flat aggregate GB metric.
- **List view, VirtualMachine subject**, instanced-group mechanism
  (`isInstancedGroup` driver item, `GROUP_diskspace`): empirically proven to
  fan out **one row per snapshot instance**, with property columns fully
  participating (see knowledge/context/investigations/
  vm-snapshot-instanced-fanout-2026-07-27.md).
- Columns: VM name (row subject), snapshot `name`, `numberOfDays`,
  instanced `used` metric (GB — requires tooling `preferredUnitId` fix),
  `creator` + `description` (present but disabled by default — policy
  enablement note in finding), flat `summary|parentCluster`,
  `summary|parentVcenter`, `summary|datastore`.
- Subject-level filter to exclude zero-snapshot VMs, stolen verbatim from the
  built-in "Optimization Report - Virtual Machines with Snapshot" embedded
  view: `diskspace|snapshot > 0.0001` (metrics) AND
  `diskspace|snapshot|snapshotAge != -1` (properties filterType).
- Known limitation to carry into the finding: **ghost instances** — deleted
  snapshots' instanced properties are never reaped (`numberOfDays == -1.0`
  marks them) and views have no per-row filter, so "active only" cannot be
  exact at the view layer. Mitigate by object-level filter + Age sort.
- Attribution: instanced-group column pattern adapted from vmbro
  "VM Snapshots List" (reference/references/vmbro_vcf_operations_vcommunity/
  Management Pack/content/reports/View - Set 4.xml ~L21991), per
  reference_sources.md attribution rule.

## Correction (2026-07-27, post-install live verify on devel)

The subject filter originally copied the built-in "Virtual Machines with
Snapshot" report's two-clause predicate verbatim: `diskspace|snapshot >
0.0001` AND `diskspace|snapshot|snapshotAge != -1`. Live verify on devel
showed the second clause is wrong for this view: `snapshotAge` is
`-1` unless a VM's *oldest* snapshot exceeds the policy's "older than X
days" threshold — it means "no snapshot older than threshold", not "no
snapshot". Requiring `!= -1` wrongly excluded VMs with live, young
snapshots (3 of 5 snapshot-bearing VMs on devel: `ca`, `dcint1`,
`vcf-lab-sddcmgr` — all had live snapshot space but `snapshotAge = -1`).

That clause was correct for the vendor's optimization report (which is
specifically an "old snapshot" cleanup nudge) but wrong for an inventory
of ALL active snapshots. Fixed by dropping the `snapshotAge` clause
entirely — `diskspace|snapshot > 0.0001` alone is sufficient to exclude
zero-snapshot VMs (a VM with only ghost instances and no live snapshot
has `diskspace|snapshot == 0`; control case `vcf-lab-operations-networks`
confirmed excluded by this clause alone). `content/views/
vm_snapshot_inventory.yaml` updated; UUID and columns unchanged.

## Correction 2 (2026-07-27, user-discovered mechanism, later the same day)

The user hand-edited view `38957c6d` on devel and found that a
`SubjectType filter=` clause whose `metricKey` carries an **instanced**
segment (`family:<instance>|attribute`) is evaluated **per fanned-out
row**, not per VM object — a mechanism api-explorer's earlier survey
(1,233 ViewDefs, 446 widgets) had missed and called "definitive: does
not exist." api-explorer verified this with a 15-variant matrix on
devel: the instance segment (e.g. `90|snapshot:snapshot-1`) is a pure
placeholder — family prefix (`diskspace`) and attribute suffix
(`numberOfDays`) must be real, but the instance token itself need not
match any actual snapshot. Full writeup:
`knowledge/context/investigations/vm-snapshot-instanced-fanout-2026-07-27.md`
§"Per-row filtering: IT EXISTS."

Replaced the flat `diskspace|snapshot > 0.0001` clause with the
recommended instanced-key clause:

```yaml
filter:
  - filter_type: properties
    metric_key: "diskspace:90|snapshot:snapshot-1|numberOfDays"
    condition: GREATER_THAN
    value: 0
```

This drops ghost/deleted-snapshot rows per-row (not just whole
ghost-only VMs) and lets Creator/Description/Snapshot Name columns stay
in the view without the earlier metric-only-members trade-off. **Recall
caveat, still true:** `numberOfDays` is gated by the global
`RECLAIM_SNAPSHOTS_DAYS` (default 7d) — snapshots younger than the
threshold have no materialized instanced data and still won't appear.
The filter fixes the ghost problem, not the young-snapshot recall gap;
both are called out in the view's `description:`. Verified on devel
only, for `GROUP_diskspace`; not yet confirmed on prod or for other
instanced groups (portability warning in the investigation doc).
`content/views/vm_snapshot_inventory.yaml` updated; UUID and columns
unchanged.
