# Cleanroom survey — cross-MP stitch identity+push across more reference adapters

**Filed:** 2026-06-30 (VCF-CF → cleanroom)
**Follow-up to:** `ad419d29` (idiomatic push = SDK `Relationships`; identity from target system) and `98166aec` (NetApp/Dell storage + Oracle/MS SQL; the match-by-attribute question).
**Goal:** widen the evidence base for the *idiomatic, ideally credential-free* cross-MP stitch pattern, so synology (and the factory framework generally) is re-architected once, correctly.

## Adapters to survey

Map each (if in corpus) to the same framework used in `98166aec`:

| Adapter | Cross-MP edge of interest | Status |
|---|---|---|
| **Avi** (NSX Advanced LB / Avi Load Balancer) | Virtual Service / Service Engine → VM / network / host | NEW |
| **SRM** (Site Recovery Manager / vSphere Replication — the `vSphere Replication Adapter` is live in our env) | protected VM / replication → `VMWARE::VirtualMachine` | NEW |
| **OpenManage Enterprise** (`openmanageenterpriseadapter-3.0.68.pak`, in your `inputs/from-marketplace/`) | server / chassis → `VMWARE::HostSystem` | NEW |
| **mongodb** | DB instance → VM | confirm/expand |
| **NSXTAdapter3** | TransportNode → ESXi host | confirm/expand |

## The classification (same as 98166aec)

For each, which identity-resolution path:

- **(a) Inventory lookup → full ResourceKey** (Suite API / SDK-injected client / other) → ambient auth, primary-only.
- **(b) Platform-resolved match-by-attribute** — push an `ExternalRelationship`/`Relationships` entry keyed on a NON-uniqueness attribute (IP, hostname, FQDN, NAA, export path, serviceTag, …) and the analytics tier binds it cluster-side. **No lookup, no creds.** ← the prize.
- **(c) Target-system-API identity** (vCenter/ComputeManager creds → full ResourceKey, vSAN/NSX pattern).

For mongodb specifically: is its "ExternalRelationship IP/name matching" **(a)** (it looks the VM up first) or **(b)** (it pushes IP/name and the platform matches)? For NSX: is the `VMWARE::HostSystem` key it pushes fully uniqueness-bearing **(c)**, or does it lean on platform match **(b)**?

## The decisive cross-cutting answer we need

**Does ANY reference adapter push a cross-MP edge by a non-uniqueness-bearing attribute and rely on the platform to resolve the foreign resource (path b)? If yes — name the adapter, the SDK API surface (`ExternalRelationship`? a `Relationships` overload?), and the matchable attributes.** That single fact decides whether synology can stitch with zero foreign credentials.

## Deliverable

Per-adapter classification table + the yes/no on a creds-free match-by-attribute path, with the exact API surface. SPEC addendum if it refines spec/07 or §20.
