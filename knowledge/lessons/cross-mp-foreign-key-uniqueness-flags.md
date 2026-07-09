# Cross-MP foreign ResourceKey must carry the real uniqueness-identifier set

**Rule.** When an SDK adapter builds a `ResourceKey` for a *foreign*
(other-adapter-kind) resource — to push a cross-MP **relationship** or to
attach a metric/property — the key MUST carry the foreign resource's real
**uniqueness-bearing** identifier set, with each identifier's actual
`isPartOfUniqueness` flag. Read the flag from the Suite API response
(`resourceKey.resourceIdentifiers[].identifierType.isPartOfUniqueness`) and
propagate it verbatim. **Never hardcode `isPartOfUniqueness=true` for every
identifier.**

**Why.** VCF Ops resolves a relationship/attachment endpoint by matching the
submitted key's *uniqueness-bearing* identifier tuple against the registered
resource's. If the submitted key marks extra (non-uniqueness) identifiers as
unique, its effective identity differs from the real resource's, and the
platform cannot bind it to anything.

**Failure mode — SILENT.** The edge is emitted every collection cycle (the
collector log shows `Relationship items count: N>0`), the analytics server
processes the payload (3–4s), and the edge **never persists in inventory** —
with **zero error/rejection in any log** (adapter, collector, analytics). It
looks like the platform is dropping cross-MP edges; it is actually rejecting a
malformed key. Direction (own-parent vs foreign-parent) is **not** the cause —
both directions persist once the key is correct.

**Reproducer.** Synology adapter, `SuiteApiDatastoreBridge.listResources()`
hardcoded `isPartOfUniqueness="true"` for all four VMWARE `Datastore`
identifiers. A Datastore's real identity is the 2-tuple
`(VMEntityObjectID, VMEntityVCID)`; `DataStrorePath` and `VMEntityName` are
**non**-uniqueness-bearing. The 4-tuple key never bound → iSCSI-LUN/NFS-Export ↔
Datastore edges silently dropped across builds .18–.21 regardless of direction.
Fix: read and propagate the real flag → edges persist (synology `1.0.0.19`).

**Positive control.** First-party `VirtualAndPhysicalSANAdapter` (vSAN) holds
VMWARE `Datastore`/`HostSystem` as both parents and children on the same
appliance, via the runtime push model — proof the platform persists SDK-pushed
cross-MP edges in either direction when the key is right.

**Source.** `knowledge/context/reviews/synology-build-19.md`;
`knowledge/context/cleanroom-spec/spec/07-relationships-cross-mp.md` (cross-MP
relationships bullet + the EMPIRICALLY CONFIRMED note). Related:
`knowledge/lessons/setrelationships-foreign-adapter-scoped.md`,
`knowledge/lessons/foreign-resource-property-push.md`.
