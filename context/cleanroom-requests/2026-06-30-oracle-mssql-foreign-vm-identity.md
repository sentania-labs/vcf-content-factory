# Cleanroom follow-up — how do Oracle / MS SQL resolve the foreign VM identity (creds-free)?

**Filed:** 2026-06-30 (VCF-CF → cleanroom)
**Follow-up to:** request `ad419d29-d827-4897-868a-685f37c5c348` (answered: cross-MP edge push is SDK `Relationships` API; identity from target system, not Suite API).
**Priority:** High — determines whether synology can stitch with ZERO foreign credentials (ideal) vs needing vCenter creds.

## Why this follow-up

Your answer recommended synology obtain the foreign `VMWARE::Datastore` identity `(VMEntityObjectID, VMEntityVCID)` from **vCenter** (vCenter credential field, vSAN pattern), then push via the SDK `Relationships` API. That works, but it requires the adapter to hold **vCenter credentials**.

The **database adapters** (Oracle, MS SQL, mongodb, mysql) are the interesting counter-case: they relate a DB instance to the **`VMWARE::VirtualMachine` it runs on**, but they only hold **database** credentials — no vCenter, no vROPs. So how do THEY resolve the foreign VM's identity? Your mongodb note ("ExternalRelationship IP/name matching against foreign VMs") hints there may be a **platform-resolved match-by-attribute** path that needs no foreign-identity lookup at all.

## Primary exhibit if you have it: NetApp (and Dell/HPE storage)

**NetApp** is the closest possible analog to synology — third-party **external NFS/iSCSI storage**, relating its volumes/LUNs to `VMWARE::Datastore`, exactly synology's stitch (and unlike vSAN, which is integrated and can assume vCenter access). If a **NetApp** adapter is in corpus (or `DellStorageAdapter-01.04.0301` / `HPESimplivityVropsMP` as external-storage proxies), **how does it resolve the foreign `VMWARE::Datastore` identity for an NFS/iSCSI volume** — does it hold vCenter creds (vSAN pattern), do a Suite API lookup (primary-only), or push a **match-by-attribute** edge keyed on NFS export path / NAA id / datastore name that the platform binds (creds-free)? This is the single most directly applicable answer for synology.

## The question (apply to NetApp/Dell/HPE storage AND the DB adapters)

For the storage adapters above and for **Oracle and MS SQL** (`microsoftsqlserver_9.0.0.0100` is in your `inputs/from-marketplace/`; use mysql/mongodb as the DB-family proxy if Oracle isn't in corpus), determine how the cross-MP relationship resolves the foreign VMWARE identity. Which of these:

- **(a) Inventory lookup → full ResourceKey.** The adapter looks up the VM by IP/hostname (Suite API via SDK-injected client, or another API) to obtain the VM's uniqueness-bearing identifiers, then pushes a fully-specified foreign `ResourceKey`. (Needs ambient auth → primary-node-only.)
- **(b) Platform-resolved match-by-attribute (the prize).** The adapter pushes an `ExternalRelationship` / `Relationships` entry keyed on a **matchable, non-uniqueness attribute** (IP, hostname, FQDN, …) and the **platform analytics tier binds it** to the VM cluster-side — NO foreign-identity lookup, NO creds. If so: what API surface (`ExternalRelationship`? a `Relationships` variant?), what attributes are matchable, and is the match exact or heuristic?
- **(c) Something else** — describe it.

## Why it's decisive for the factory

If **(b)** exists, it is strictly better than the vCenter-creds recommendation for a Cloud-Proxy-deployable adapter: synology could push the LUN/NFS→Datastore edge keyed on a **matchable attribute** (NAA id, NFS export path, datastore name) and let the platform bind it — **zero vROPs creds AND zero vCenter creds**, works on a Cloud Proxy with nothing configured.

So please also answer directly: **does the SDK `Relationships`/`ExternalRelationship` API support pushing an edge by a NON-uniqueness-bearing attribute and having the platform resolve the foreign resource, or must the adapter always supply the full uniqueness-bearing `ResourceKey`?** That single fact decides whether synology needs vCenter creds at all.

## Deliverable

The concrete DB→VM identity mechanism Oracle/MS SQL (or mysql/mongodb) use, the exact SDK API surface for any match-by-attribute resolution, and a yes/no on whether a fully creds-free cross-MP stitch is achievable. SPEC addendum if it changes spec/07 or §20.
