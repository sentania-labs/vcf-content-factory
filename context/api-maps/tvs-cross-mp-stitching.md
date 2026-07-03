# TVS cross-MP stitching — bytecode-verified

**Question (one sentence):** How do modern (2023–2024) Broadcom True
Visibility Suite management paks stitch cross-MP relationships onto
VMWARE-owned resources (Datastore / VirtualMachine), and what does that imply
for our creds-free, Cloud-Proxy-safe Synology / Oracle Tier-2 SDK adapters?

**Method:** `unzip` + `javap -p -c` (bytecode, not just class topology) on 8
priority paks from `references/tvs/` — PureStorage FlashArray 4.3.0 (the
spec's "direct Synology template"), Dell EMC Isilon 4.3.2, Dell EMC VNX Block
4.1.0, NetApp E-Series 6.1.0, HPE Nimble 5.2.0, NetApp FAS-AFF 4.3.0, Oracle
Database 9.1.0 — plus MSSQL 4.0.0 and MongoDB 4.0.0 for DB-adapter contrast.
Extracted to scratchpad only; nothing written to the repo except this file; no
lab objects created. **This confirms — and materially corrects — spec/20 §7–8
and spec/21 §5–6a, which were written from class/package topology "no bytecode
read".** Bytecode read here.

---

## TL;DR — the canonical modern-TVS idiom

Every 2023–2024 storage/DB pak in the priority set is built on
**`aria-ops-core`** (7.1.0 / 7.1.1) and shares one stitch idiom:

1. **Credentials (A):** a **single target-system credential kind**
   (username/password), **no vROps field, no vCenter field.** Confirmed on all 8.
2. **Relationship API (C):** **ADDITIVE**, not full-set replacement. Foreign
   edges are created with `addParent` / `addChild` / `addMultipleParents` /
   `addMultipleChildren` (on `RelationshipInfo`) →
   `ResourceDtoClient.addRelationship(...)` → SDK
   `com.vmware.tvs.…core.data.Resource.addParent(Resource)`. `setRelationships`
   exists in `aria-ops-core` but is **not** the foreign-stitch verb (used for
   the adapter's own local edges). **No TVS pak uses full-set
   `setRelationships` to stitch a foreign VMWARE parent.**
3. **Identity resolution (D):** the foreign VMWARE resource is resolved by a
   **Suite API READ** — `SuiteAPIClient` → `com.vmware.ops.api.client.Client`
   → `ResourceQuery.setPropertyName/PropertyValue/ResourceKind/AdapterKind`
   (or `findResourcesWithIdentifiers`). **This is not a lookup-free, describe-
   only, platform-auto-dedupe path.** Creds-*free* (no operator credential) but
   **not lookup-free** — it depends on the ambient maintenance identity that
   the platform injects for `localhost/suite-api`.
4. **`vim25` (B):** bundled by Pure / FAS-AFF / Oracle; **absent** from Isilon /
   VNX Block / E-Series / Nimble. Where bundled, it is **not used** for foreign
   resolution — Pure's shim makes zero `vSphereClient`/vim25 login calls, and
   `aria-ops-core-7.1.0` does not even ship an `extensions/vsphere` package.
   vim25 is build-template baggage. **None of these adapters query vCenter
   directly** (consistent with having no vCenter credential field).

**Name for the pattern:** *aria-ops-core additive external-relationship stitch,
resolved by ambient Suite-API property/identifier search.*

---

## The decisive correction for the Synology CP-403 problem

The spec framed the no-`vim25` storage adapters as matching "a storage object
to the platform's existing Datastore **by identifier against the resource
graph**" — implying **no Suite API read**, hence CP-safe. **Bytecode refutes
this.** "Match against the resource graph" is mechanically a
`SuiteAPIClient.ResourceQuery` (property search) = a **Suite API read** against
`localhost/suite-api`.

- Isilon / VNX Block / E-Series / Nimble each call `SuiteAPIClient` (6–15 refs
  in their **own** shim jar, on top of aria-ops-core's 54) and
  `addGeneralParentRelationship` — there is **no** alternative lookup-free path
  in their bytecode.
- Therefore **every modern TVS storage/DB adapter that stitches a foreign edge
  performs a Suite API read to resolve the foreign resource.** On the
  **primary/data node** the ambient maintenance identity has resource-read RBAC
  → works, creds-free. On a **Cloud Proxy** the `cloudproxy_<uuid>` account
  acquires a token (200) but carries **empty roles** → the VM/Datastore
  inventory read **403s** (spec/21 §5 footnote already confirmed this live for
  `OracleDatabase-9.1.0` on CP 172.27.8.51).

**So the TVS corpus does NOT demonstrate a CP-safe creds-free foreign stitch.**
It demonstrates an *in-appliance* creds-free stitch. For Synology:

- **In-appliance (primary/data node) Synology adapter:** copy the aria-ops-core
  idiom verbatim — ambient `SuiteAPIClient` property search on the LUN
  NAA/serial → `VMWARE::Datastore`, additive `addParent`. Creds-free, no
  vCenter creds. This is genuinely what PureStorage 4.3.0 does.
- **Cloud-Proxy Synology adapter:** NO TVS pak solves this creds-free. The only
  CP-safe options are (a) add a **vCenter credential field**, query vCenter
  directly for the datastore's backing-device NAA + `(VMEntityObjectID,
  VMEntityVCID)`, and push via the SDK **without any Suite API read** (the vSAN
  idiom, spec/20 §6 — note TVS does *not* do this), or (b) explicit vROps creds
  pointed at the **primary FQDN**. The vROps-cred variant is exactly what the 2
  outlier paks (CitrixADC, OEM) expose and what CitrixADC 9.0.0 marks
  "(Deprecated)" — a legacy auth path for the same inventory read.

---

## Bytecode evidence (PureStorage FlashArray 4.3.0, the reference)

Push path — additive, SDK-native, no REST write:

```
ExternalRelationshipCollection.createRelationships(
    AdapterLoggerFactory, SuiteAPIClient, ResourceCollection)
  → RelationshipInfo.addParent/addChild/addMultipleParents/addMultipleChildren(
        ResourceDtoClient, Resource, Collection<String>)
    → ResourceDtoClient.getResources(RelationshipInfo, value)          // LOOKUP
        → ResourceDtoClient.getResourcesFromSuiteApi(...)              // Suite API READ
            → new ResourceQuery(); setAdapterKind/ResourceKind/
              PropertyName/PropertyValue(...)                          // property search
    → ResourceDtoClient.addRelationship(Resource local, ResourceDto foreign)  // PUSH
        → getResource(ResourceDto) : core.data.Resource               // foreign→SDK Resource
        → Resource.addParent(Resource)                                // ADDITIVE, rides CollectResult
```

Declarative surface (aria-ops-core):
- `RelationshipInfo` carries `KEY_TYPE ∈ {METRIC, PROPERTY, RESOURCE_NAME,
  IDENTIFIER}` — the match key class.
- `ExternalRelationship{ByName,ByMetric}`: `ExternalRelationshipType ∈
  {CHILD_OF_EXTERNAL, PARENT_OF_EXTERNAL}`, `ExternalRelationshipMethod ∈
  {ONE_TO_ONE, ONE_TO_MANY}`, plus a `String→List<String>`
  `valueManipulationFunction` (e.g. NAA normalisation) and a
  `withTagResourceParentOfExternalKind(...)` local container/tag.

Identity keys (PureStorage Volume): `naa_id`, `protocol_endpoint_naa_id`,
`serial`, `serial_number` — all declared **`isProperty="true"`** and flagged
`asExternalIdentifier` in the DP (`VolumeDefinition`). Observed live value form
`naa.624a9370…` — the VMFS backing-device NAA. The Volume's **own** uniqueness
identifiers (describe `identType="1"`) are only `adapter_instance_id` + `serial`;
the NAA keys are *properties used to match the foreign Datastore*, resolved via
`ResourceQuery` property search (`KEY_TYPE.PROPERTY`). No describe-level
cross-adapter auto-dedupe.

---

## Two-layer stitch (base edge + transitive `.sdm`)

1. **Base edge** `storage-object → VMWARE::Datastore` (or DB → VM): in the
   adapter/DP shim via aria-ops-core `SuiteAPIClient` +
   `addGeneralParentRelationship` (Suite API read + additive push, as above).
2. **Transitive edges** `Datastore → VirtualMachine → HostSystem → Datacenter →
   vSphere World`: declarative `.sdm` (SuperDuperMetrics) that walks the
   **already-present** platform graph from the storage resource. Verb is
   additive and gathers foreign nodes under a **local container/tag** resource
   kind — never touches the VMWARE parent's edge set:

   ```
   (addRelationship (container "Nimble Volume VMs" "nimble_volume_tag" "NIMBLESTORAGE_ADAPTER")
                    (parents (parents this "Datastore") "VirtualMachine"))
   ```
   (VNX Block `hosted_on_block.sdm`, E-Series `virtual_machines.sdm`, Nimble
   `Nimble-Volume-VMS.sdm` — all identical shape.) `.sdm` count: Isilon 0, Pure
   0, FAS-AFF 0 (moved to compiled Kotlin), VNX Block 1, E-Series 2, Nimble 2.
   The transitive layer still *reads* the platform graph, so it is subject to
   the same CP RBAC constraint as layer 1.

---

## Per-pak matrix (priority set)

| Pak (build) | aria-ops-core | vim25 | cred kinds | vROps field | foreign-resolve | match key |
|---|---|---|---|---|---|---|
| PureStorage FlashArray 4.3.0 (2023) | 7.1.0 | **yes** (unused) | 1 `credentials` | no | SuiteAPI property search | Volume NAA / serial → Datastore |
| Dell EMC Isilon 4.3.2 (2024) | 7.1.0 | no | 1 | no | SuiteAPI + `addVmParentBy*` | identity + VM name/IP → Datastore/VM |
| Dell EMC VNX Block 4.1.0 (2023) | 7.1.0 | no | 1 | no | SuiteAPI; `.sdm` transitive | LUN serial → Datastore |
| NetApp E-Series 6.1.0 (2023) | 7.1.0 | no | 1 | no | SuiteAPI; 2 `.sdm` | volume/chassis serial → Datastore/VM |
| HPE Nimble 5.2.0 (2023) | 7.1.0 | no | 1 (+opt community string) | no | SuiteAPI; 2 `.sdm` | volume iSCSI IQN/serial → Datastore |
| NetApp FAS-AFF 4.3.0 (2023) | 7.1.0 | yes (unused) | 1 `netapp_ocum_credentials` | no | SuiteAPI (WWN/full-path, compiled) | WWN / datastore full-path |
| Oracle Database 9.1.0 (2024) | 7.1.1 | yes (unused) | 1 `oracle_database_credentials` (+role) | no | SuiteAPI `addVmParentByNames/Ip` | DB host name / IP → VM |
| MicrosoftSQLServer 4.0.0 (2020) | (bundled) | — | 1 `sql_server_credentials` | no | `addVmParentByNamesWithIpLookup` | SQL host name / IP → VM |
| MongoDB 4.0.0 (2020) | (bundled) | — | 2 (`mongodb_credentials`, `mongodb_no_credentials`) | no | `addVmParentByNames/Ip` | Mongo host name / IP → VM |

**Storage vs DB identity split:** storage adapters match a **deterministic
shared storage identifier** (NAA / volume serial / WWN / iSCSI IQN) against the
Datastore's backing-device property. DB adapters match **VM name / IP**
(`addVmParentByNames*`, `addVmParentByIp`) — a fuzzier inventory search. Both go
through the same `SuiteAPIClient` Suite API read; neither is CP-safe off-primary.

**Deviations:** none within the modern set on the core idiom. `mongodb` offers a
`_no_credentials` kind — that is *no-auth-to-Mongo*, **not** a vROps variant (do
not confuse with CitrixADC/OEM's vROps-cred variants, which are outside this
priority set). No pak in this set exposes a vROps credential field.

---

## Relation to `lessons/setrelationships-foreign-adapter-scoped.md`

Our lesson holds that our own **full-set `setRelationships(foreignParent,
{ownChildren})`** is per-reporting-adapter scoped (proven on 9.0.2, 9.1
unverified) and therefore does not clobber the owner's edges. **The TVS corpus
takes a different route and so does not bear on that lesson's clobber question
either way:** TVS uses **additive** `addParent`/`addChild` (and local
container/tag nodes), which structurally cannot replace the owner's child set.
So:
- Our factory idiom (full-set `setRelationships`, relying on platform scoping)
  and the vendor idiom (additive add) are **both** clobber-safe, by different
  mechanisms. The vendor corpus is *not* evidence for or against our scoping
  assumption — it simply never issues the call that would test it.
- What the vendor corpus **does** settle is identity resolution: it is a Suite
  API read, and it is the real Cloud-Proxy constraint — not the relationship
  write verb.

## Flags / limits

- Config bodies are Kotlin lambdas + embedded YAML (`reprlib`/ex-uno format);
  string constants for the exact per-adapter `RelationshipInfo(VMWARE,
  Datastore, <property-key>, KEY_TYPE)` triple live in synthetic lambda classes
  and YAML resources, read via `strings`, not clean `javap` — the *mechanism*
  is bytecode-solid; the exact per-pak property key name (e.g. which Datastore
  property holds the backing NAA) was read from resource strings, not decompiled
  source.
- No decompiler available; `javap -c` bytecode only. No obfuscation encountered
  — class/method names are intact throughout aria-ops-core and the shims.
- `setRelationships` was **not** traced to a foreign-parent call site; its 3–4
  references per pak are consistent with local-edge use. If a future task needs
  certainty, disassemble `RelationshipCoalescer` / `RelationshipUtils`.
