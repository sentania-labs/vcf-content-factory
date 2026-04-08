# Custom group `relationshipConditionRules` — relation semantics

Empirical findings from the 2026-04-08 lab investigation into why
`[AI Content] VMs on NFS` (and its vSAN/VMFS siblings) installed but
returned zero members.

## TL;DR

- In a `relationshipConditionRule`, `relation` is evaluated against
  Ops's **canonical topology tree**, not against the richer graph
  returned by `GET /api/resources/{id}/relationships?relationshipType=...`.
- `relation: DESCENDANT` means **"the candidate resource is at or
  below the named group in the canonical tree"**. `ANCESTOR` is the
  mirror.
- `PARENT`/`CHILD` appear to be degenerate / non-functional for
  cross-group-reference rules in this grammar — every experiment
  with them returned 0 members. Use `DESCENDANT`/`ANCESTOR`.
- The canonical tree is NOT "everything the REST relationships
  endpoint shows". In particular:
  - **DVS port group → VirtualMachine IS a canonical edge.** So
    "VMs on a given set of port groups" works with
    `VirtualMachine DESCENDANT EQ <PG group>`.
  - **VirtualMachine → Datastore is NOT a canonical edge**, even
    though `/api/resources/{vm}/relationships?relationshipType=CHILD`
    returns the backing datastores. Datastore hangs off Datacenter
    in the canonical tree (and off Host as a secondary relationship),
    not off VM. Therefore **no `relation:` value in this grammar
    can express "VMs whose backing datastore is a member of group
    X"**.

## Evidence

Lab: `vcf-lab-wld02` vCenter, 2026-04-08. Groups probed via
`GET /internal/resources/groups/{id}/members`
(requires `X-Ops-API-use-unsupported: true`).

### Working precedent — `[Custom] VMs on only Standard PGs` (26 members)

Rule:
```json
{"resourceKind":"VirtualMachine","adapterKind":"VMWARE"},
 "relationshipConditionRules":[
   {"relation":"DESCENDANT","name":"[Custom] Standard PGs","compareOperator":"EQ"},
   {"relation":"DESCENDANT","name":"[Custom] NSX PGs","compareOperator":"NOT_EQ"}]
```
Full JSON: `context/specimens/vm_by_portgroup_group.json`.

### Our broken group — `[AI Content] VMs on NFS` (0 members)

Rule as emitted by the customgroup loader:
```json
"relationshipConditionRules":[
  {"relation":"CHILD","name":"[AI Content] NFS Datastores","compareOperator":"EQ"}]
```
Full JSON: `context/specimens/vm_by_datastore_group_BROKEN.json`.

### Matrix of throwaway VirtualMachine groups (45s resolve wait)

Target `[Custom] Standard PGs` (port group group):

| relation    | members |
|-------------|---------|
| PARENT      | 0       |
| CHILD       | 0       |
| ANCESTOR    | 0       |
| DESCENDANT  | **26**  |

Target `[AI Content] NFS Datastores` (datastore group):

| relation    | members |
|-------------|---------|
| PARENT      | 0       |
| CHILD       | 0       |
| ANCESTOR    | 0       |
| DESCENDANT  | 0       |

Host pivot (VirtualMachine→HostSystem→Datastore) attempted via
`HostSystem` scoped rules with `PARENT` and `ANCESTOR` targeting
`[AI Content] NFS Datastores`: both 0. The canonical tree does not
carry the Host↔Datastore edge either.

Self-reference sanity: `Datastore DESCENDANT EQ [AI Content] NFS
Datastores` returned **3** — exactly the NFS datastores. This
confirms `DESCENDANT` means "candidate is at-or-below the group node
in the canonical tree", and that datastores sit cleanly in their
own subtree under the NFS datastores group container. They just
aren't in the VM subtree.

### Ops canonical tree vs. `/relationships` REST view

From `GET /api/resources/{vmId}/relationships?relationshipType=X`
on a real VM:

| relationshipType | Returned kinds |
|---|---|
| PARENT  | DistributedVirtualPortgroup, HostSystem, ResourcePool, VM Entity Status, Container/Function |
| CHILD   | Datastore |
| ANCESTOR | (empty) |
| DESCENDANT | (empty) |

The REST view lists the datastore as a CHILD of the VM. The
custom-group rule grammar **does not** treat this as a tree edge.
Reading `relationshipType=CHILD` on a VM and assuming you can write
`relation: CHILD name: "<datastore group>"` is the trap we hit.

For completeness, `GET .../relationships` on a Datastore returned
`PARENT: [HostSystem, VM Entity Status, Datacenter, Environment]`
and no CHILDren. On a HostSystem: `CHILD: [Datastore,
VirtualMachine]`. None of these map to walkable edges in the
`relationshipConditionRule` grammar for cross-group references.

## Correct rule shape for known patterns

- **"VMs on a set of port groups"** — works:
  `VirtualMachine DESCENDANT EQ <port group group>`.
- **"VMs on a set of datastores"** — CANNOT be expressed with
  `relationshipConditionRules`. See TOOLSET GAP below.

## TOOLSET GAP: "VMs on a set of datastores"

The repo's intent for `vms_on_nfs.yaml` / `vms_on_vsan.yaml` /
`vms_on_shared_vmfs.yaml` / `vms_on_local_vmfs.yaml` cannot be
implemented with a `relationshipConditionRule` regardless of
`relation:` value. The VM↔Datastore edge exists only in the
denormalized REST relationship view, not in the canonical tree the
rule engine walks.

### Proposed alternatives (orchestrator to choose)

1. **Super metric pivot.** Author a VM-scoped super metric per
   datastore tier — e.g. `sm_vm_on_nfs` that returns 1 if any
   related datastore carries the tier property (NFS, vSAN, VMFS
   local/shared) and 0 otherwise. The formula would traverse from
   VM to its datastores via the DSL's relationship functions
   (`${adapterkind=VMWARE&resourcekind=Datastore&..}` child
   syntax — needs confirmation in `docs/vcf9/` DSL reference),
   grab `config|backing_type` or equivalent, and emit a boolean.
   Then the custom group uses a `propertyConditionRules` /
   `statConditionRules` condition on that super metric: no
   relationship rule needed. This is the cleanest path and matches
   the "property-keyed custom group" pattern already used for the
   datastore groups themselves.

2. **Tag-based.** If the user can attach a vSphere tag to each VM
   reflecting its primary datastore tier, use
   `resourceTagConditionRules`. Requires out-of-band tagging; not
   automatic.

3. **Static snapshot group.** Compute the VM set externally and
   POST an `includedResources` list. Breaks auto-resolution —
   new VMs won't appear. Explicitly rejected by
   `customgroup_authoring.md` unless the user asks.

Recommend option 1. It keeps the custom groups dynamic and
self-maintaining, keeps the datastore-tier definition in a single
place (the property rule on the Datastore group), and pushes the
VM↔Datastore hop into the super metric DSL, which *can* walk that
edge.

### Loader implications

The loader in `vcfops_customgroups/` faithfully emits whatever the
YAML says. No loader bug here — the YAML itself was expressing an
unrepresentable rule. No code change needed unless we want the
validator to warn on
`VirtualMachine relationshipConditionRule name="<datastore group>"`
patterns as a known-dead shape; that requires the loader to peek
at the referenced group's member kind, which crosses a layering
line. Recommend documenting the gotcha in
`context/customgroup_authoring.md` instead.

## Gotchas to remember

- `relationshipType` on `/api/resources/{id}/relationships` is a
  different concept from `relation` in
  `relationshipConditionRules`. The REST endpoint gives you the
  full graph (including consumption edges); the rule grammar walks
  only the canonical tree.
- `PARENT`/`CHILD` in the rule grammar appear useless for
  cross-group-reference rules. Every experiment returned 0.
  Default to `DESCENDANT` / `ANCESTOR`.
- Membership resolution is async but fast — all non-zero results
  in this investigation were visible within 15s of group create.
  If a rule still shows 0 at 45s, it is almost certainly
  structurally wrong, not slow.
- The `travesalSpecId` (sic) field was not exercised in this
  investigation. It may narrow or redirect the walk; worth a
  follow-up if we ever need to disambiguate multi-path topologies.
