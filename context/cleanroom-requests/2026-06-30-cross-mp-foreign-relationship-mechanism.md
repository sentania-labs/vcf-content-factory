# Cleanroom request — how do reference paks create cross-MP (foreign-adapter) relationships?

**Filed:** 2026-06-30 (VCF-CF → cleanroom)
**Priority:** High — blocks a synology release decision; may invalidate the factory's entire Suite-API-stitch design.
**Boundary note:** VCF-CF is NOT dispatched into the cleanroom. This is a research question for the cleanroom to answer from the decompiled reference corpus; the answer belongs in the SPEC.

## The disagreement to resolve

The factory's current SPEC (`spec/20-suiteapi-client-behavioral-contract.md` §4) concludes:

> "explicit credential fields are the only viable mechanism for remote-collector deployment. They are not a fallback; they are the only path."

i.e. to relate its resources to a *foreign* adapter's resources (Synology iSCSI LUN / NFS export → VMware Datastore), the factory adapter reads the global VMware inventory via a **Suite API REST call** (`GET /api/resources?adapterKind=VMWARE&resourceKind=Datastore`) and then pushes the relationship edge. On a **Cloud Proxy**, the ambient identity is a scoped `cloudproxy_<uuid>` account that gets **HTTP 403** on that read, so the SPEC concludes the operator must supply explicit vROPs credentials.

**The SME (Scott) vehemently disagrees:** *no shipping pak he has seen requires the operator to provide vROPs/Suite-API credentials in order to cross-stitch.* If that's true, the SPEC's "explicit creds are the only path" is wrong, and the factory's Suite-API-read approach to cross-MP stitching is **non-idiomatic** — there must be a platform/SDK-native mechanism that needs no cluster API credentials.

## The specific question

**How do BlueMedora/native reference paks relate their own resources to FOREIGN (other-adapter) resources — and does that mechanism require reading or calling the Suite API at all?**

Concretely, trace at least one reference pak that creates a cross-*adapter* relationship (storage→datastore, app→VM, etc.) and determine which of these it uses:

1. **adapter-3 SDK relationship API (hypothesis — SME's implied mechanism).** Does the adapter declare the foreign relationship through the SDK's `CollectResult` relationship surface using a **foreign `ResourceKey`** (adapterKind + resourceKind + identifiers of the other adapter's resource), and the **platform** resolves/persists the edge cluster-side — with NO Suite API REST call and NO cluster credentials? If so, document the exact API (`CollectResult.addRelationships` / `addRelationship` / the `Relationship`/`ResourceKey` shape), how the foreign resource is identified (does the adapter need to already know the foreign identifiers, or does the platform match?), and where the persistence happens (collector → analytics, not adapter → Suite API).

2. **describe.xml declarative cross-kind path (`TraversalSpec`/`ResourcePath`).** Is a cross-adapter relationship declared statically in describe.xml (e.g. a `ResourcePath` naming the foreign `adapterKind::resourceKind`) and resolved by the platform, with the runtime only emitting the edge by key? (This was an earlier factory hypothesis — `context/feedback_queue.md` FB-005 — that we retired; please confirm whether it is in fact the idiomatic mechanism.)

3. **Suite API REST (what the factory does today).** Do ANY reference paks actually call the Suite API REST surface at runtime to read foreign inventory and push relationships? If so, how do THOSE paks authenticate on a Cloud Proxy — is there a platform-injected cloud-proxy service token / cluster credential we missed (SPEC ledger #9 "no forwarding" is only **Med — absence of evidence**), or do they too require operator creds?

## Why it matters / what a good answer settles

- If **(1)** or **(2)**: the factory should stop reading the Suite API for stitching and use the SDK/declarative path → **no vROPs creds needed on a Cloud Proxy, ever**. The in-flight synology "explicit creds" build (22) would be the wrong fix and should not ship.
- If **(3)** and there IS a platform cloud-proxy credential/token: document it; the factory uses that instead of operator-supplied creds.
- If **(3)** and there genuinely is no credential-less path: the SPEC §4 stands and the explicit-creds build is correct — but we want this confirmed against an actual reference pak, not inferred.

## Evidence already gathered (factory side, to inform the cleanroom)

- Live: on the prod Cloud Proxy, `maintenanceuser.properties` username = `cloudproxy_<uuid>` (scoped), and the Suite API datastore read returns **403** (authenticated-but-forbidden). Confirms the *ambient localhost* path fails on a CP; does NOT prove a foreign-relationship edge requires the Suite API at all.
- The factory's stitch path: `SuiteApiStitchClient` (REST) + `RelationshipBuilder.parentForeign` / `setRelationships`. We do NOT currently know whether the reference paks reach a foreign resource via this REST surface or via the adapter-3 `CollectResult` relationship API.
- SPEC provenance ledger #9 ("no remote routing/forwarding") is **Med — absence of evidence**; #10/#13 (explicit creds required / must target primary) are High but derive from the *assumption that stitching goes through the Suite API*.

## Requested deliverable

A SPEC addendum (or correction to §20 §4) stating the **idiomatic mechanism by which a reference pak relates a resource to a foreign-adapter resource**, whether it touches the Suite API, and — if it does — how it authenticates on a Cloud Proxy. Name the reference pak(s) examined.
