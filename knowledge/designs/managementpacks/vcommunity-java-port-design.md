# Design Artifact: VCF Content Factory vCommunity (Java port of e1-rahabok 0.8.1)

- **Type:** managementpack, Tier 2 (Java SDK)
- **Intent and owner decisions:** `knowledge/designs/managementpacks/vcommunity-java-port-2026-11.md`
- **API map (the contract):** `knowledge/context/api-maps/vcommunity-e1-collection-map.md` and
  `knowledge/context/api-maps/vcommunity-e1-key-map.tsv` (rows are cited as `R<n>`, the 1-based data row
  number, header excluded; `R1` is `Configuration|Install Date|UTC`, `R257` is the `Options|<item>` family)
- **Pak repo:** `sentania-labs/vcf-content-factory-sdk-vcommunity-java` (private), cloned at
  `content/sdk-adapters/vcommunity-java/` from the SDK template
- **Author:** `sdk-adapter-author` (sonnet). Reviewer: `sdk-adapter-reviewer`.
- **Date:** 2026-11-12. **Status:** design, awaiting owner answers to section 12.

This design is written so the author never opens the Python pack. Where it says "per the TSV", the row's
`source`, `transform` and `when_absent_or_failed` columns are the specification, overridden only by the
honesty rules in section 5 and the deviation register (section 5.7).

---

## Original Request

Port `e1-rahabok/VCF-vCommunity-Adapter` 0.8.1 (continuation of `vmbro/VCF-Operations-vCommunity`) to the
factory's Java SDK, fresh from the current template, with full key, content and initial configuration parity.
Verbatim prompts and the owner's decisions are in the intent file above.

## Tier decision

Tier 2. Triggers (RULE-004, `knowledge/rules/tier-routing.md`): non-HTTP transport (vim25 SOAP over raw HTTP
plus guest operations), client-side joins across vCenter and the Suite API, custom response transforms
(regex over `guestDetailedData`, KPI arithmetic), per-instance long-lived state (certificate, periodic
check), programmatic in-guest actions. Lessons that bind: `cross-runtime-pak-upgrade-split-brain.md`
(distinct kind, no in-place upgrade from the Python pack), `stitch-moid-not-unique-across-vcenters.md`,
`foreign-resource-property-push.md`, `pak-content-must-not-reuse-stock-ids.md`.

Delivery: the pak lives in its own repo (above). It is **not yet in `knowledge/context/managed_paks.md`**;
the orchestrator adds the entry (name `vcommunity-java`, remote, target) before authoring. Bundled
dashboards, views, reports, alerts and symptoms ship from that repo.

## Interview Answers (owner, 2026-11-12, from the intent file)

| Question | Answer |
|---|---|
| Names | repo `vcf-content-factory-sdk-vcommunity-java`, adapter kind `vcfcf_vcommunity`, display name `VCF Content Factory vCommunity` |
| Key tree | `vCommunity|...` unchanged, same instance names, same objects |
| Content names | upstream names, `content_naming: unprefixed`; a re-authored view whose title equals a built-in's gets a distinct title |
| Failure handling | report honestly: a failed or missing read sends nothing and is counted; never a zero, False or sentinel; license key masked; a bad check-list entry is skipped and reported |
| Content route | grow the factory YAML route, no raw passthrough |
| Edited built-in views | re-authored under ids of their own |
| License | MIT, NOTICE crediting the original authors; repo private until the licensing record is complete |

---

## 0. Ground rules for the author

1. **Java 11 bytecode, JDK APIs of 11 only** (RULE-019): no records, text blocks, switch expressions,
   `String.strip()` is fine (11), `HttpClient` is not used on vim25 paths. Compile legs: 8.18.7, 9.0.2, 9.1.1.
2. **vim25 is raw SOAP 1.1 over `HttpsURLConnection`, parsed with JDK StAX.** No JAX-WS, no `vim25.jar`
   (the 9.1 JAX-WS provider collision, documented in the compliance `VSphereClient` header). Port the
   transport idea of `content/sdk-adapters/compliance/src/.../VSphereClient.java` (session cookie, relogin
   once on NotAuthenticated, CappedInputStream, `postFixingPaths` drop-and-retry), not its control logic.
   Read by element local name; a missing element is "absent", never an exception, never a default.
3. **No shared mutable "last fault" fields** in clients used from a pool. Every call returns a result that
   carries its own fault (`VimResult<T>`: value, faultClass, invalidPropertyPath, bytes).
4. **SDK-free logic.** Everything except `VCommunityAdapter` and the two thin port adapters (Suite API,
   logging) has no import from the VCF Ops SDK or the framework jar, so `ci/run_java_tests.sh` exercises it
   (template `tests/.../T.java` harness). Clients take a `Log` interface (compliance pattern).
5. **Never send a null.** All pushes go through `PushSet` (5.6). Never NaN, never Infinity, never a blank key.
6. **Python value rendering is part of the contract.** Values upstream produced with `str()` must render the
   same text in Java. One class owns this: `PyText` (Appendix B has the vectors). Booleans render `True` /
   `False`; vim25 `xsd:dateTime` renders as Python `str(datetime)`; floats as Python `repr`.
7. **Logging:** `componentLogger(X.class)` for helpers; one WARN per failure cause per cycle (count and
   first object), stack traces at DEBUG; never a credential, token, session id or license key in any line.
8. **Timestamps:** every value pushed in a cycle carries the cycle timestamp `T` = cycle start (ms).

---

## 1. Identity and packaging

`adapter.yaml`:

| Field | Value |
|---|---|
| `adapter_kind` | `vcfcf_vcommunity` |
| `entry_class` | `com.vcfcf.adapters.vcommunity.VCommunityAdapter` |
| `name` | `VCF Content Factory vCommunity` |
| `description` | one paragraph, written new: Java port of the vCommunity management pack; pushes the `vCommunity|` keys onto the vCenter adapter's own objects; three own kinds; attribution sentence "Port of vCommunity by Onur Yuzseven (github.com/vmbro/VCF-Operations-vCommunity) as continued by e1-rahabok (github.com/e1-rahabok/VCF-vCommunity-Adapter) 0.8.1." |
| `version` | `1.0.0`; dev builds stamp `0.0.0.<build>` (RULE-014); the release is the repo CI on a `v*` tag |
| `tier` / `released` | `2` / `false` |
| `vendor` | `VCF Content Factory` (explicit, so the line is reviewable) |
| `vendor_contact` | omit while the repo is private |
| `eula_file` | `LICENSE` (MIT, already in the template clone) |
| `content_naming` | `unprefixed` |
| `content_foreign_adapter_kinds` | `[VMWARE, Container]` |
| `logging` | default (package entry at INFO) |

`NOTICE` (repo root, shipped in the pak beside `LICENSE` by naming it in the README and copying it under
`docs/`): credits Onur Yuzseven and the vCommunity contributors (vmbro/VCF-Operations-vCommunity) and
e1-rahabok (VCF-vCommunity-Adapter) for the original design, key tree, KPI tables, content and check-list
files; states that this pak is an independent Java reimplementation. Final wording waits on the owner's
licensing record; the author writes a placeholder that the reviewer checks is present.

`stitch_targets` (documentation only, `knowledge/context/tier2_architecture.md` "Push targets"):

| adapter_kind / resource_kind | identity | key_groups |
|---|---|---|
| VMWARE / ClusterComputeResource | `VMEntityObjectID + VMEntityVCID` | `vCommunity|Cluster Configuration|*`, `vCommunity|Cluster Performance|*`, `vCommunity|Cluster Risk|*`, `vCommunity|Cluster Consumption|*`, `vCommunity|Availability|*`, `vCommunity|Periodic Cluster Check|*`, `vCommunity|Resource Pools|*` |
| VMWARE / HostSystem | same | `vCommunity|Configuration|*`, `vCommunity|Licensing:<license name>|*`, `vCommunity|Storage Adapter|*`, `vCommunity|Storage Adapter:<hba>|*`, `vCommunity|Network|*`, `vCommunity|Network|Device:<vmnic>|*`, `vCommunity|Runtime|*`, `vCommunity|Hardware|*`, `vCommunity|Capability|*`, `vCommunity|ESXi Performance|*`, `vCommunity|Availability|*` |
| VMWARE / VirtualMachine | same | `vCommunity|Configuration|*`, `vCommunity|Guest|*`, `vCommunity|Guest OS|*`, `vCommunity|Runtime|*`, `vCommunity|Summary|*`, `vCommunity|Network|Network Adapters:<label>|*`, `vCommunity|Virtual Disk:<label>|*`, `vCommunity|Options|*`, `vCommunity|VM Performance|*`, `vCommunity|Guest OS Performance|*`, `vCommunity|VM Guest OS KPI` |
| VMWARE / Datastore | same (E1) | `vCommunity|Identifiers|*`, `vCommunity|Summary|*` |
| VMWARE / VMwareAdapter Instance | `VMEntityVCID` | `vCommunity|Certificate|*`, `vCommunity|Configuration|*`, `vCommunity|Availability|*`, `vCommunity|Number of Port Groups`, `vCommunity|Collection Health|*` |
| VMWARE / Datacenter | `VMEntityObjectID + VMEntityVCID` (E1) | `vCommunity|Network|*` |
| VMWARE / vSphere World | singleton | `vCommunity|*` (14 keys, R198-R211) |
| Container / Tier, BusinessService, Enterprise | Suite API resource id from the Container tree | `vCommunity|Business Application|*` |

Kind-name check before the first install (open question Q8): `vcfcf_vcommunity` and the display name
`VCF Content Factory vCommunity` were the retired 2026 port's (`managed_paks.md` "Retired paks"). Recon must
confirm no lab instance still registers that kind; if one does, uninstall it first (credential stash per
`pak-uninstall-cascades-credentials.md`), or the new pak installs as an "upgrade" of the old one.

---

## 2. describe.xml

### 2.1 Adapter instance kind `vcfcf_vcommunity` (type 7), `monitoringInterval="5"`, `credentialKind="vsphere_user"`

The 19 fields keep upstream's keys, types, defaults, enums and required flags. Identifying = no `identType`
(main form, part of account uniqueness); advanced = `identType="2"` (Advanced Settings; works because each
is `required="false"` or has a non-empty default, `knowledge/context/python_integration_sdk.md` 2.3).
Labels are configuration parity and are listed; descriptions are written new by the author (short,
factual, no upstream prose).

| dispOrder | key | type | required | default | enum values (in order) | form | label |
|---|---|---|---|---|---|---|---|
| 0 | `host` | string | true | none | | identifying | vCenter Server |
| 1 | `esxi_adv_settings_config_file` | string | false | `esxi_advanced_system_settings` | | identifying | ESXi Advanced System Settings Config File |
| 2 | `esxi_vib_driver_config_file` | string | false | `esxi_packages` | | identifying | ESXi Software Packages Config File |
| 3 | `vm_adv_settings_config_file` | string | false | `vm_advanced_parameters` | | identifying | VM Advanced Parameters Config File |
| 4 | `vm_configuration_config_file` | string | false | `vm_options` | | identifying | VM Options Config File |
| 5 | `port` | integer | true | `443` | | advanced | Port |
| 6 | `vcenter_tls_validation` | string | false | `Trust on First Use` | `Trust on First Use`, `Enabled`, `Pinned` | advanced | vCenter TLS Validation |
| 7 | `vcenter_thumbprint` | string | false | none | | advanced | vCenter Thumbprint (SHA-256) |
| 8 | `cluster_check_period_hours` | string | false | `24` | `01`,`02`,`04`,`06`,`08`,`12`,`24` | advanced | Cluster Check Period (hours) |
| 9 | `periodic_cluster_check_time` | string | false | `00:00` | | advanced | Cluster Check Time (UTC) |
| 10 | `cluster_check_worst_percent` | integer | false | `5` | | advanced | Cluster Check Worst Percent |
| 11 | `monster_vm_cpu_percent_of_cores` | integer | false | `50` | | advanced | Monster VM CPU (% of host cores) |
| 12 | `monster_vm_memory_percent_of_dram` | integer | false | `40` | | advanced | Monster VM Memory (% of host DRAM) |
| 13 | `monster_vm_memory_min_gb` | integer | false | `256` | | advanced | Monster VM Memory Minimum (GB) |
| 14 | `win_service_config_file` | string | false | `windows_service_list` | | advanced | Windows Service Configuration File |
| 15 | `win_event_config_file` | string | false | `windows_event_list` | | advanced | Windows Event Log Configuration File |
| 16 | `serviceMonitoring` | string | false | `Disabled` | `Enabled`, `Disabled` | advanced | Guest OS Service Monitoring Status |
| 17 | `guest_tls_validation` | string | false | `Pinned` | `Pinned`, `Strict`, `Disabled` | advanced | Guest File Transfer TLS Validation |
| 18 | `winEventMonitoring` | string | false | `Disabled` | `Enabled`, `Disabled` | advanced | Windows Event Log Monitoring Status |

Parsing (`VCommunityConfig`, SDK-free) follows the map's Configuration table exactly: the same fallbacks
(period 24, time 00:00, worst 5, monster 50/40/256) with one WARN per field per cycle (upstream logs period
twice; DV-53), case-insensitive TLS modes, empty TLS mode = default, `"6"` and `"06"` both accepted,
`serviceMonitoring`/`winEventMonitoring` compared case-sensitively with `Enabled` (parity). Thumbprint
normalisation: strip whitespace, `:` and `-`, lowercase, hex only, length 64 or 128.

Note for the author: whether the UI shows the enum *values* (`01`) or anything else for the period pulldown
is not known for Tier 2 describe; ship the values as upstream's keys.

### 2.2 Credential kind `vsphere_user`

| dispOrder | key | type | required | password | label |
|---|---|---|---|---|---|
| 0 | `user` | string | true | false | vCenter User Name |
| 1 | `password` | string | true | true | vCenter Password |
| 2 | `winUser` | string | false | false | Windows User Name |
| 3 | `winPass` | string | false | true | Windows Password |

### 2.3 Own resource kinds (type 1), adapter kind `vcfcf_vcommunity`

| Kind key | Display | Identifiers (all `required="true"`, part of uniqueness) | Attributes |
|---|---|---|---|
| `Content Library` | Content Library | `Library ID` | R245-R252, declared under groups `vCommunity` > `Content Library`, units from the TSV `unit_declared_in_definition` column (`GB` for Total Size) |
| `Library Item` | Library Item | `Item ID` | R234-R244 |
| `VM Template` | VM Template | `VMEntityObjectID`, `VMEntityVCID` | R227-R233 |
| `vCommunityCollector` | VCF Content Factory vCommunity Collector | `vcenter` (the `host` field, trimmed only), `config_files` (the four identifying file-name fields joined with `,` exactly as stored, trimmed only) | none |

The resource kind keys keep upstream's strings (spaces included), so the attribute keys are identical; only
the adapter kind changes (`vCommunity` to `vcfcf_vcommunity`, DV-50). Every own attribute is declared, so
the 26 own keys get labels and units in the UI, which the 228 foreign keys cannot (3.4).

`vCommunityCollector` is the cycle anchor, not a World: one object per adapter instance, discovered from the
account values alone so it exists while vCenter is unreachable, and the whole cycle runs in its `collect()`
(the vsanperf `VsanPerfCollector` pattern, `knowledge/designs/vsanperf-mp-v1.md` build 7 addendum). Without
it a cycle with zero libraries would have nothing to collect and an unreachable vCenter could not show DOWN.
No World kind: the only own relationship is Content Library > Library Item, so a TraversalSpec
`vCommunity Content Libraries` rooted at `Content Library` (`vcfcf_vcommunity::Content Library||vcfcf_vcommunity::Library Item::child`)
has a reachable first hop (`traversal-spec-root-must-be-reachable.md`). Verify the tree in the UI before a tag.

Icons (`icons/icons.yaml`): adapter instance `adapter_instance`, `vCommunityCollector` `adapter_instance`.
**TOOLSET GAP T4:** need new hints `content_library` (three book spines on a shelf), `library_item` (a single
document with a folded corner over a small box), `vm_template` (a monitor outline with a dashed stencil
border). Until `tooling` adds them, the three kinds use `default`.

### 2.4 Self and health metrics on the adapter instance (declared, `Collection|*`)

Pushed through the Suite API onto the adapter instance resource every cycle (vsanperf pattern), so they land
even when the vCenter object cannot be resolved.

| Key | Type | Unit | Meaning |
|---|---|---|---|
| `Collection|cycle_seconds` | metric | s | wall time of the cycle |
| `Collection|reads_failed` | metric | count | failed read units this cycle (5.2) |
| `Collection|values_withheld` | metric | count | object x key values not sent because their read failed |
| `Collection|objects_unmatched` | metric | count | vCenter objects with no unique Ops resource |
| `Collection|checklist_entries_skipped` | metric | count | invalid check-list items dropped |
| `Collection|series_pushed` | metric | count | stat values sent |
| `Collection|properties_pushed` | metric | count | property values sent |
| `Collection|push_batches_failed` | metric | count | from `SuiteApiBatchResult` |
| `Collection|deadline_hit` | metric | 0/1 | the cycle stopped at its deadline |
| `Collection|vcenter_object_resolved` | metric | 0/1 | the VMwareAdapter Instance was matched |
| `Collection|guest_vms_done` / `guest_vms_pending` | metric | count | guest phase progress (section 8) |
| `Collection|last_error` | property | | first failure cause text, credential-free; `None in the last cycle` when none |

### 2.5 vCenter TLS: upstream modes on a Java in-collector adapter

All three modes stay as configured values (configuration parity). One SDK-free class `VcenterTls` builds the
`SSLSocketFactory` and hostname verifier for the SOAP client, the REST client and the certificate probe.

| Mode | Upstream | Java | Identical? |
|---|---|---|---|
| Trust on First Use | no check before login; certificate watched afterwards | trust-all trust manager and all-true hostname verifier, built per instance (same posture as the framework's `insecureSslContext()`), on SOAP and REST; the per-cycle probe feeds the Certificate keys | Yes on the wire. Same weakness (credentials sent before any check); flagged to the owner (Q6). FIPS 9.1 collector: E15 |
| Enabled | system trust store (SOAP), certifi bundle (REST), TLS 1.2+, hostname checked | platform trust: `getPlatformSslContext(host)` (chain against the instance's trust, including certificates the admin accepts in the Validate Connection dialog) plus the framework name check (`CertificateNames.secure(conn, factory)` on every `HttpsURLConnection`); `certificateCheckUrls` returns `https://<host>:<port>` in this mode only, so the accept dialog appears | **No.** Trust anchors differ (collector trust plus accepted certificates, not the proxy OS store or certifi). A self-signed vCenter that upstream refuses can be accepted here. Name checking is equivalent. DV-52 |
| Pinned | pyVmomi thumbprint compare before anything is sent; REST pinned with SHA-256 only | adapter-managed `X509TrustManager`: SHA-256 (64 hex) or SHA-512 (128 hex) of the leaf DER equals the normalised field, chain and name ignored, checked during the handshake before credentials. Used by SOAP and REST alike | Yes for SOAP. REST also accepts a 128-hex pin (DV-51). Invalid or empty pin in Pinned mode: the cycle fails with a credential-free message naming the field (same as upstream SOAP; upstream REST skipped libraries) |

- The per-cycle probe (`ThumbprintProbe`): one raw TLS handshake to `host:port`, trust-all, 10 s timeout,
  nothing sent after the handshake, SHA-256 of the leaf DER, lowercase hex. Every mode. Failure: presented
  thumbprint unknown, counted (cause `F-CERT-PROBE`), Certificate Status withheld (DV-23).
- `certificateFailureMessage` override: point at the vCenter TLS Validation field and its three modes.
- Unknown mode text (not one of the three after case folding): the cycle fails at configure with a message
  naming the field (parity).

Guest file-transfer TLS (section 8.4) is a second, separate trust manager.

---

## 3. Object binding and stitching

### 3.1 The owning vCenter and the Ops resource maps

Every cycle the SOAP session yields `about.instanceUuid` (the VCID). It is pinned before any lookup. An
unknown VCID (login failed) holds back every foreign push for the cycle (`stitch-moid-not-unique-across-vcenters.md`,
compliance build 102 rule); own objects that need no vCenter (none do) would still go.

`OpsResourceMap` (SDK-free, port of the vsanperf `OpsHostMap` identity rules) indexes
`GET /api/resources?adapterKind=VMWARE&resourceKind=<kind>&page=<n>&pageSize=<s>` by
(`VMEntityVCID`, `VMEntityObjectID`) to the Suite API resource id:

- A row is indexed only with a resource id, a MoRef and a VCID equal to the pinned VCID.
- A MoRef carried by two rows of this vCenter matches neither (counted `objects_unmatched`, DV-07).
- No name fallback, ever.
- Page size 5000 (500 for VirtualMachine), refresh every 12th cycle, on a change in the vCenter object set,
  or on a MoRef miss (at most once per 12 cycles per kind), as vsanperf does.
- A failed page fails that kind's map for the cycle (no partial maps); the previous map is kept if one
  exists and was built under the same VCID, else that kind's pushes are held back.

| Target | How it is resolved | Upstream | Deviation |
|---|---|---|---|
| ClusterComputeResource, HostSystem, VirtualMachine, Datastore | `OpsResourceMap` (VCID + MoRef) | scoped query + MoRef | none in result (scoping by VCID instead of adapter instance id) |
| VMwareAdapter Instance | rows of that kind whose `VMEntityVCID` equals the VCID; exactly one, else hold back and count | first object whose `VCURL` equals the `host` string | DV-01, DV-02 |
| Datacenter | `OpsResourceMap` by Datacenter MoRef + VCID (E1 confirms the identifiers) | Ops resource name equals host `summary|parentDatacenter` | DV-05 |
| vSphere World | `findSingletonResourceId("VMWARE", "vSphere World")` every cycle; null (zero or ambiguous) holds back World keys | first result of an unscoped query | DV-06 |
| Container Tier, BusinessService, Enterprise | `GET /api/resources?adapterKind=Container&resourceKind=<kind>` (all instances), then `GET /api/resources/{id}/relationships?relationshipType=CHILD` | same | none |
| Own kinds | SDK discovery (`registerNewResource`), own `ResourceKey` with identifiers | SDK result | none |

The VMware adapter instance id that upstream looked up through `GET api/adapters` is not needed: every
scoped read is scoped by the VCID-filtered resource ids instead.

### 3.2 Joins that cannot merge same-named objects (deliberate deviations)

All membership comes from this cycle's vim25 reads, by MoRef, inside one vCenter:

| Join | Upstream (by display name) | Java | DV |
|---|---|---|---|
| VM to host | VM Ops property `summary|parentHost` equals host Ops name | VM `runtime.host` MoRef | DV-03 |
| Host to cluster | host Ops property `summary|parentCluster` equals cluster Ops name | host `parent` MoRef when it is a `ClusterComputeResource` (a standalone host's parent is a `ComputeResource`: no cluster) | DV-04 |
| Host to Datacenter | host Ops property `summary|parentDatacenter` equals Datacenter Ops name | per-Datacenter `ContainerView(datacenter, [HostSystem], recursive)` membership (the same pass that serves port groups, 4.8) | DV-05 |

Power state and host states used by the KPIs keep upstream's source (Ops latest properties), so only
membership changes. User-visible effect: same-named clusters in two Datacenters no longer share hosts and
VMs; after a vMotion the VM counts under its new host from this cycle rather than after the VMware adapter's
next collection.

### 3.3 How the 228 foreign keys are pushed

- One `PushSet` per cycle: `Map<resourceId, Map<key, String>>` for properties and
  `Map<resourceId, Map<key, Double>>` for stats, built by the collectors, pushed once by the caller thread
  with `stitcher.pushBatch(props, stats, T)` (properties first, at most 100 resources and about 1 MB per
  request, `SKILL.md` "Many objects per cycle"). Count from `SuiteApiBatchResult`; `isClean()` false raises
  `push_batches_failed`.
- **Properties are pushed on change.** `LastPushed` (in memory) holds a 64-bit hash per (resource id, key);
  a property is sent when its value changed, on the first cycle after start, and in a full refresh every
  12th cycle (hourly at 5 minutes). Stats are sent every cycle. DV-49. Rationale: properties dominate bytes
  (`suite_api_batch_push.md`), VM properties are ~59 per VM.
- **Series volume per cycle** (stats): clusters 38 x C, hosts up to 13 x H plus one `Remaining Days` per
  license per host, powered-on VMs up to 7 x Von, vCenter 3, World 14, Datacenter 1 x DC, Container 3 x
  (Tr+A+E), own kinds 6 per library/item/template. Example (C 10, H 100, Von 1,600, DC 2): about 13,000
  values, about 1.1 MB at 85 B per value (`suite_api_batch_push.md` measurement), 18 to 20 batches.
- **Numeric property (R43 `Maintenance Mode Required`).** Upstream lands it as a numeric property (1.0/0.0).
  The framework batch takes string property values only. **TOOLSET GAP T3:** numeric property values in
  `pushPropertiesBatch`. Until T3 lands the key is withheld (counted), not sent as text, because mixing a
  string sample into a key whose history is numeric is untested (E3).

What is known about labels, units and deletion (from `knowledge/context/investigations/2026-11-06-suite-api-instanced-push.md`
and `suite_api_batch_push.md`):

- Pushed undeclared keys land and are registered on the resource on first push; instanced keys work.
- **No label, no unit.** The UI's metadata comes from the resource's own adapter kind (VMWARE); our
  describe.xml cannot declare keys on another adapter's kinds. Expect raw key segments as labels and no unit
  for all 228 foreign keys. Upstream's own-kind declarations in `definition.py` almost certainly did not help
  either (map gap 1); E2 compares what the UI shows today for upstream's keys with what it shows for ours.
- Stats are stored as float32.
- Read-back lags a 200 by 1 to 4 minutes.
- A 2xx does not mean every id landed: a stale id is dropped silently; stale ids are caught in the map refresh.
- **No deletion.** Nothing removes a pushed key. A stat simply stops getting samples. A property keeps its last
  value indefinitely, which matters for the honesty rules (5.3, Q1). Whether uninstalling the pak removes the
  keys from VMWARE objects is unknown (E10).

### 3.4 Relationships

- The only relationship written: Content Library (parent) > Library Item (children), own objects, through the
  SDK result (`RelationshipBuilder`, full set per library). A library whose collection failed is not sent, so
  its links stay as they were (parity).
- **No edge on any foreign object.** No `addChild`, no `parentForeign`. VM Template gets no parent (parity).
- Business Application objects (Container kinds) are read only: their CHILD relationships are read, never
  written.

---

## 4. Collectors

### 4.1 Cycle architecture

```
VCommunityAdapter.collect(vCommunityCollector)         SDK side, thin
  CycleEngine.run(ports, config, clock)                SDK-free
    A. caller thread, serial
       1. VimSession.ensure() + about (VCID, patchLevel)            [vim25]
       2. ThumbprintProbe                                            [raw TLS]
       3. CheckListStore.refresh (only the files in use, 4.10)       [Suite API GET x <=6]
       4. OpsResourceMap refresh where due; World singleton id        [Suite API GET]
    B. inventory pool, W_inv = 4 workers, each task isolated, own timeout
       R-CL clusters, R-HO hosts, R-HOO host options, R-VM VMs, R-DS datastores,
       R-DC datacenters + membership + DVPG, R-RP resource pools, R-FO folder names,
       R-LIC licensing, R-OPT vCenter options, R-LIB libraries (REST)
       then per-host calls on a sub-pool of 8: installDate, fetchSoftwarePackages
    C. read-back pool, W_ops = 4 workers                              [Suite API POST/GET]
       VM latest stats + properties, host latest stats (+ instance stats) + properties,
       cluster latest stats (+ timestamps), periodic history, World reads, Container tree + stats,
       certificate cold-start read-back
    D. caller thread: Collectors (pure functions) -> PushSet + Failures; KPI engine
    E. caller thread: push (properties, then stats), events, self metrics, health keys
    F. guest phase (only when a guest switch is on), its own pool, until the cycle deadline
  deadline = T + interval - 60 s; at the deadline unfinished tasks are abandoned (counted),
  and what completed is pushed
```

- **One bulk read per vim25 type per cycle,** held in an immutable `Inventory` snapshot that every collector
  reads. No collector issues its own vim25 read except the per-host method calls and guest operations.
- **One read-back per Ops data set per cycle,** shared by the KPI engine and the collectors (upstream reads
  hosts' properties three times and VM contention stats twice; Java reads each once).
- Bulk reads: `CreateContainerView(rootFolder, [type], recursive)`, `RetrievePropertiesEx` with
  `maxObjects` = the page size below, `ContinueRetrievePropertiesEx` until no token, `DestroyView` in finally.
  A failed page fails the whole type for the cycle (never a partial list read as complete; upstream issue 62).
  `name` always in the path set.
- Responses are parsed with StAX into compact `BulkRow`s holding only requested paths, arrays projected to
  small records (device list to `VDevice` records). No DOM of a whole page (heap, section 9).
- Timeouts: SOAP connect 10 s, read 120 s per call; REST 60 s per request (parity); Suite API stitcher
  defaults (30 s) for GETs, 120 s for history POSTs; per-host method calls 30 s.

| Read | Type and path set (TSV `source` column is the authority) | Page |
|---|---|---|
| R-CL | `ClusterComputeResource`: `name`, `configStatus`, `overallStatus`, `summary` (whole: `drsScore`, `currentEVCModeKey`, `numEffectiveHosts` live on subtypes), `configuration` (whole, for `dasConfig`, `drsConfig`), `configurationEx` (whole, for `dpmConfigInfo`, `proactiveDrsConfig`, `drsConfig.option`) | 10 |
| R-HO | `HostSystem`: `name`, `parent`, `runtime.connectionState`, `runtime.bootTime`, `configStatus`, `summary.maxEVCModeKey`, `summary.config.sslThumbprint`, `config.network.pnic`, `config.network.dnsConfig`, `config.network.portgroup`, `config.dateTimeInfo.timeZone`, `config.storageDevice.hostBusAdapter`, `hardware.biosInfo.vendor`, `hardware.pciDevice`, `capability.storageVMotionSupported`, `configManager.imageConfigManager` | 50 |
| R-HOO | `HostSystem` explicit objectSet: `config.option` only; keep the two VAAI keys (R8, R9) and the ESXi Advanced Settings list items, discard the rest while parsing | 25 |
| R-VM | `VirtualMachine`: every path the VM rows name (R82-R130), with `guest` split into its sub-paths (`guest.guestState`, `guest.appState`, `guest.guestKernelCrashed`, `guest.guestOperationsReady`, `guest.guestStateChangeSupported`, `guest.interactiveGuestOperationsReady`, `guest.customizationInfo`, `guest.guestDetailedData`, `guest.toolsStatus`, `guest.guestFamily`) instead of the whole object (DV-56); plus `runtime.host`, `parent`, `datastore`, `config.template`, `config.guestFullName`, `config.version`, `summary.config.numCpu`, `summary.config.memorySizeMB`, `summary.storage.committed`; plus `config.extraConfig` when the VM Advanced Parameters list is non-empty; plus the validated VM Options paths (5.5) | 50 |
| R-DS | `Datastore`: `name`, `overallStatus`, `iormConfiguration`, `info` | 100 |
| R-DC | `Datacenter`: `name`, `networkFolder`; per Datacenter a `ContainerView(dc, [HostSystem])` (MoRefs) and a `ContainerView(networkFolder, [DistributedVirtualPortgroup])` with `name` | 100 |
| R-RP | `ResourcePool`: `name`, `parent` (VirtualApp rows, told by the `obj` type attribute, are excluded; E9) | 500 |
| R-FO | `Folder`: `name`, explicit objectSet of the templates' `parent` MoRefs | all |
| R-LIC | `LicenseAssignmentManager.QueryAssignedLicenses()` with no entity (one call) | |
| R-OPT | `OptionManager(content.setting).QueryOptions(name = null)`: every vCenter setting in one call; pick the ten keys (DV-37) | |

An InvalidProperty fault that names a path is handled by `postFixingPaths`: the path is removed (for VM
Options: dropped, never shortened, because a shortened path would publish under a different key), the call
repeated, at most 20 times per read, and the accepted path set remembered for the type and list content.
The dropped path's keys are withheld and counted. A version-dependent path (`guest.guestDetailedData` on an
older vCenter) is handled the same way.

### 4.2 Package layout (Java-idiomatic, SDK-free except where marked)

```
com.vcfcf.adapters.vcommunity
  VCommunityAdapter            SDK: lifecycle, describe, test, discover, collect, ports wiring
  OpsPort                      SDK: SuiteApiStitcher adapter (reads, pushes, events)
  VCommunityConfig             19 fields, credential, fallbacks, warnings
  CycleEngine                  phases A-F, deadline, pools, Failures
  vim/   VimSoapClient, VimResult, BulkReader (StAX), BulkRow, MoRef, VDevice, GuestOpsClient
  tls/   VcenterTls, PinnedTrustManager, ThumbprintProbe, GuestTls, CertificateState
  ops/   OpsResourceMap, OpsReads (latest stats/properties/history parsers), PushSet, LastPushed, EventBatch
  inv/   Inventory, Membership (VM->host->cluster->Datacenter by MoRef)
  coll/  ClusterCollector, HostCollector, VmCollector, DatastoreCollector, VCenterCollector,
         WorldCollector, DatacenterCollector, LibraryCollector, TemplateCollector, BusinessAppCollector
  kpi/   KpiTable, KpiScorer, Percentile, Staleness, PyRound,
         ClusterPerformance, ClusterRisk, ClusterConsumption, EsxiPerformance, VmPerformance,
         GuestOsPerformance, VmGuestOsKpi, OperationalAvailability, NetworkSpeed,
         PeriodicWindow, PeriodicCheck, ClusterDelta, WorldRollups, BusinessApps
  list/  CheckListParser, CheckListStore, EventListValidator, ServiceNameFilter, VmOptionPath
  guest/ GuestPlan, GuestCursor, PsCommand, CsvParser, WindowsEventMapper
  text/  PyText, LicenseKeyMask, InstanceNames, DetailedDataParser
  health/ Failures, FailureCause (catalogue 5.2), CollectionHealth
  json/  Json (minimal reader, lift from vsanperf Json/JsonStream)
```

Plain-JDK tests cover every class outside the two SDK-marked ones, with fixtures under
`tests/fixtures/` (SOAP response XML for the bulk parser, Suite API JSON, CSV, check-list XML, KPI vectors).

### 4.3 Cluster collector

- Reads: R-CL; Ops: cluster latest stats (D3 usable capacity keys, `summary|total_number_hosts`,
  `configuration|dasConfig|hostFailoverLevel`), cluster latest properties (failover level fallback), D9
  timestamps and history; KPI inputs from the shared VM and host read-backs; membership.
- Owns: R132-R152 and R220 (vim25 properties, transforms per TSV), R218-R219 (resource pools, from R-RP),
  R221 (availability), R153-R155 and R159-R184 (KPIs, section 7), R222-R225 (periodic check).
- HA/DRS rows: the TSV's "HA off: null", "DRS off: null" become withheld (DV-09, Q1). EVC Enabled (R144):
  `currentEVCModeKey` absent in a cluster summary that was read means EVC is off, `False` is a reading (kept,
  Q2). DRS Score (R220): DRS off or negative is withheld (DV-16); a missing `drsScore` is withheld.
- Resource pools (DV-35): level of a pool = number of ResourcePool hops from the pool up to the cluster,
  not counting the cluster's root pool; Number of Resource Pools counts levels 1 to 3, Cascading Resource
  Pools levels 2 to 5 (R218-R219). A cluster with no pools after a successful read: `0` (a real count). Read
  failed: withheld for every cluster. The differential (E9) decides whether this equals upstream's Ops-based
  count; if not, fall back to Ops PARENT relationships with per-pool GETs (upstream method, honest failure).

### 4.4 Host collector

- Reads: R-HO, R-HOO, R-LIC, per connected host `installDate()` and (list non-empty) `fetchSoftwarePackages()`
  on the sub-pool of 8; Ops host read-backs for D4, D8, D12.
- Owns: R1-R46, R255 (properties), R156, R185-R193 (ESXi Performance), R195 (availability), R196 (network).
- Hosts whose `runtime.connectionState` is not `connected` are skipped for every vim25 key (parity, issue 86;
  Q3 proposes publishing their Availability).
- Licensing (R2-R6): assignments grouped by `entityId` = host MoRef; instance name `assignedLicense.name`;
  a missing name withholds that assignment's five keys (DV-13). `License Key` is masked (5.4). `Remaining Days`
  = floor of (expiration minus now UTC) in days, Python `timedelta.days` semantics (floor toward minus
  infinity, so -0.5 days is -1). No `expirationDate`: not published (parity). Expiration rendered as Python
  `str(datetime)` (Appendix B).
- Storage adapters (R7, R20-R25): instance name `device`, falling back to the last `-` segment of `key` when
  `device` is empty or the text `null` (a derivation, kept). `Number of HBA`: count of the array when the
  path was returned (`0` for a returned empty array, E6), withheld when absent.
- NICs (R27-R39): instance `pnic.device`. Status (R30) `Connected` when `linkSpeed` is set, `Disconnected`
  when the NIC was read and `linkSpeed` is unset (a reading; the bundled "ESXi Host NIC Disconnected" alert
  depends on it; Q2). Duplex (R39) withheld while the link is down (DV-15). PCI fields (R31-R35): joined on
  `pciDevice.id == pnic.pci`; no match: withheld (DV-14); ids formatted as 4-digit lowercase hex of the
  unsigned 16-bit value (`v & 0xFFFF`) (DV-33, E13).
- Packages (R40-R46): per connected host, filtered by exact `name` equal to a list item; `Maintenance Mode
  Required` numeric property (T3).
- Advanced System Settings (R26/R255): option key equals the list item exactly; value via `PyText`.
- Install Date (R1): ISO form `YYYY-MM-DDTHH:MM:SS.ffffff+00:00` per the TSV; call failure withheld (DV-10).

### 4.5 VM collector

- Reads: R-VM; Ops VM latest properties (power state, shares, `config|hardware|numCpu`,
  `config|hardware|memoryKB`) with the latest-stats fallback for shares (R70-R71); VM latest stats for D5/D6.
- Owns: R70-R131, R256, R257 (properties and the two share metrics), R157-R158, R194, R214 (KPIs); guest keys
  R72-R80 come from the guest phase (section 8).
- VMs that are templates (`config.template = true`) go to the Template collector, not here (parity: upstream
  publishes no VM keys on them; confirm in the differential).
- Device-derived families (R120-R130): SCSI controllers by `busNumber`, type names per the TSV mapping; an
  unmapped controller type renders as its vim25 `xsi:type` local name (DV-34). Network adapters instance
  `deviceInfo.label` stripped; Virtual Disk instance `deviceInfo.label`. A device without a label: withheld
  (sentinel instance names `Unknown Adapter`, `unknown`, `Unknown` are not used; DV-57). SCSI Controllers
  Count (R120) is `0` for a returned device list with no controller, withheld when the list is absent.
- Detailed Data (R112-R118): `guest.guestDetailedData` is a string of `name='value'` pairs; the same
  non-greedy pattern `(\w+)=['"](.*?)['"]` is applied (values with embedded quotes are cut at the first
  quote, parity); field absent: withheld.
- Customization Status (R110): strip, remove `TOOLSDEPLOYPKG_`; absent: withheld.
- Advanced Parameters (R81/R256): `config.extraConfig` key equals the item exactly.
- Options (R131/R257): section 5.5.

### 4.6 Datastore collector

- Reads: R-DS. Owns R47-R55. MOID (R49) from the MoRef. Extents (R47-R48) 1-based positions in
  `info.vmfs.extent`; non-VMFS: Block Size, Max Blocks, VMFS Upgradable not published (parity), Number of
  Extents withheld when `info.vmfs` is absent (DV-11).

### 4.7 vCenter collector (VMwareAdapter Instance)

- Reads: `about` (from session), R-OPT, the probe, the certificate state (section 6), the port-group pass
  (4.8), this cycle's cluster availability values.
- Owns: R56-R59 (certificate), R60-R69 (ten options, option missing or call failed: withheld, DV-37),
  R212 (min of this cycle's cluster values; any cluster's value withheld: withheld), R213 (port groups),
  R226 (Patch Level; attribute absent: withheld), R253-R254 and the added health keys (5.2), configuration
  problem events (4.10).

### 4.8 Datacenter collector and port groups

- Port groups (R213): per Datacenter, distinct names over the member hosts' `config.network.portgroup[].spec.name`
  (already in R-HO) and the Datacenter's DistributedVirtualPortgroup names; summed over Datacenters. Any
  Datacenter's membership or DVPG read failed, or any member host's R-HO row missing: withheld.
- Datacenter (R197): count of this cycle's member hosts whose Network Speed Degradation is below 100. A host
  with no comparable NIC (read succeeded, nothing to compare) does not count, parity. Withheld when any member
  host's NIC read-back failed, or when no member host has a value (DV-22).

### 4.9 World collector (vSphere World, all vCenters)

- Reads (unscoped, every resource of the kind in Ops, previous cycle's values, 10-minute rule; port groups
  15 minutes): cluster KPI scores and Cluster Operational Availability, host Operational Availability and
  Network Speed Degradation, vCenter Number of Port Groups, VM tools properties (`summary|guest|toolsVersionStatus2`,
  `summary|guest|toolsRunningStatus`, `summary|runtime|powerState`).
- Owns R198-R211; Cluster Delta (R199-R200) per section 7.
- Unscoped resource id lists come from `GET /api/resources?adapterKind=VMWARE&resourceKind=<kind>` without the
  VCID filter, refreshed on the same 12-cycle cadence.
- Any read for a key's inputs failed: that key withheld (DV-24); the query returning zero resources is only
  "none" when the call succeeded (DV-20).
- Every adapter instance of the pak computes and pushes the same values (parity; Q4).

### 4.10 Check-list collector (configuration files)

- `CheckListStore` (SDK-free, `Fetcher` interface, after the compliance `OverridesStore` and the retired
  `SolutionConfigStore`): `GET api/configurations/files?path=SolutionConfig/<name>.xml` through
  `stitcher.get(path, "*/*")`, one token for all files.
- Which files are read: the four identifying lists always; the Windows service list only when
  `serviceMonitoring` is `Enabled`; the event list only when `winEventMonitoring` is `Enabled` (DV-28).
- Outcomes per file: `OK`; `ABSENT` (HTTP 404, or HTTP 400 with `apiErrorCode` 1501, read from
  `SuiteApiHttpException.getApiErrorCode()`): empty list, last good dropped; `FETCH_FAILED` (any other error):
  the last good list stays in force; `PARSE_FAILED`: the last good list stays in force (DV-27). Every non-OK
  outcome produces one configuration-problem event and one health count.
- Parsing (`CheckListParser`): secure XML parser (DTDs and external entities disabled); items are the root
  element's text before its first child element, comments dropped and the text either side joined, split on
  `,`, each item stripped, empties dropped, duplicates collapsed keeping the first. An item containing a line
  break, tab or other control character is skipped and reported ("separate items with commas") (DV-60).
- Per-list validation: ESXi settings, packages and VM parameters accept any other item verbatim (keys with
  `|` or `:` publish exactly the key upstream would; logged once at INFO); VM Options: section 5.5; Windows
  services: upstream's safe-name rule (letters, digits, space, `_ . $ # @ ( ) + -`, first character
  alphanumeric or `_`, at most 256, no `$(`), rejects skipped, logged once and counted.
- Event list (`EventListValidator`): well-formed, root `Events`, `Log` children with a non-empty `Name`,
  `EventID` children with integer text; anything else is a reported problem and the list is not used
  (DV-30). The XML text is passed to the guest as a file (section 8).
- Configuration-problem events: on the VMwareAdapter Instance, message prefix `vCommunity configuration: `
  then a new sentence naming the file and the outcome, severity WARNING, as DIAGNOSTIC/LOG events (DV-31,
  section 8.6). Only when the vCenter object is resolved (parity).

### 4.11 Library collector (REST) and Template collector

- REST: `POST /api/session` (Basic), then `GET /api/content/library`, per library `GET /api/content/library/{id}`
  and `GET /api/content/library/item?library_id={id}`, per item `GET /api/content/library/item/{id}`; unwrap a
  `value` envelope; `DELETE /api/session` in finally (parity: login per cycle). TLS per 2.5. 60 s per request.
- Isolation (DV-46): a failed list call fails all libraries (nothing sent, links kept); a failed library
  detail call skips that library; a failed item call withholds that item and the library's four aggregate
  metrics (R249-R252), other libraries proceed. Upstream aborted everything on any non-2xx.
- Owns R234-R252. A JSON field absent: withheld; present and empty: sent as empty (DV-17). Counts R250-R251
  withheld for a library when any of its items lacks the field (DV-18; E-L1 checks how often that happens).
  Sizes: `round(bytes / 1024^3, 2)` with `PyRound`.
- Templates (R227-R233): every VM with `config.template = true` in R-VM becomes a `VM Template` own object
  (Q5, DV-47), identifiers MoRef and VCID. Datastore (R231) = `", ".join` of datastore names from R-DS in the
  VM's `datastore` order; Folder (R232) from R-FO (DV-48). Memory (GB) `str(round(MB/1024, 2))` via `PyText`;
  absent sources withheld.

### 4.12 Business Applications collector

- Reads: Container Tier, BusinessService, Enterprise resources (unscoped), their CHILD relationships, the
  CHILD VMs' `vCommunity|VM Guest OS KPI` (latest, 10 minutes, previous cycle), K8S-Namespace children and
  grandchildren through non-Tier children with `Performance|Performance`.
- Owns R215-R217. Tier = mean of its VMs' values that exist; BusinessService = `max(namespace values +
  [min(Tier values)])` (issue 6 stays as upstream); Enterprise = mean of its BusinessService values.
- Failure: a relationship GET or stats batch that failed withholds the objects whose inputs it carried and
  every parent above them (DV-24), instead of stopping the remaining levels for everyone.
- Every instance publishes the same values (Q4).

### 4.13 Guest collector

Section 8.

---

## 5. Report honestly

### 5.1 Rule

1. **Read failed** (a call raised, timed out, returned non-2xx, a page failed, the object's row is missing
   from a bulk result, a batch failed, the deadline cut it): the affected keys get **nothing**; the failure
   is counted once per cause (`Failures.add(cause, object, keysWithheld)`); one WARN line per cause per cycle
   with the count and the first object.
2. **Read succeeded and the source is absent or unset** (path in `missingSet` or not returned, JSON field
   missing, CSV cell empty): the key gets **nothing**. Not counted as a failure (counted only in
   `values_withheld` when a row of the TSV is flagged `Y:` for it, so the register stays measurable).
3. **Read succeeded and the value itself is the reading** (a returned empty array counts 0; link down means
   Disconnected; every scored KPI row green means 100): sent. Section 5.3 lists the definitional values kept.
4. **Aggregates** (max, min, percentile, mean, count, sum) are published only when every input read they
   depend on succeeded. Missing inputs because the object has no fresh sample (10-minute rule) are not
   failures and are excluded, as upstream.

### 5.2 Collection health

Upstream keys kept on the VMwareAdapter Instance with the same meaning:

| Key | Type | Java meaning |
|---|---|---|
| `vCommunity|Collection Health|Warnings in Last Cycle` (R253) | metric | count of WARN-and-above lines the pak logged this cycle plus failed push batches the framework reported (the pak cannot hook every logger; DV-32); `0` when none (a count, kept) |
| `vCommunity|Collection Health|First Warning` (R254) | property | text of the first such line, credential-free; `None in the last cycle` when none (kept: a true statement, and without it the last warning would linger) |

Added on the same object (additive; alerts may use them):

| Key | Type | Meaning |
|---|---|---|
| `vCommunity|Collection Health|Reads Failed in Last Cycle` | metric | failed read units (one per cause per object group) |
| `vCommunity|Collection Health|Values Withheld in Last Cycle` | metric | object x key values not sent because of rule 1 |
| `vCommunity|Collection Health|Check-List Entries Skipped` | metric | invalid items dropped this cycle, all lists |
| `vCommunity|Collection Health|Objects Not Matched` | metric | vCenter objects with no unique Ops resource |
| `vCommunity|Collection Health|Cycle Seconds` | metric | cycle wall time |
| `vCommunity|Collection Health|First Failure` | property | first rule-1 cause text; `None in the last cycle` when none |
| `vCommunity|Collection Health|Collector:<name>|Status` | property | `OK`, `PARTIAL`, `FAILED`, `SKIPPED` (switched off or prerequisite failed), `NOT RUN` (deadline); `<name>` in `cluster, host, vm, datastore, vcenter, world, datacenter, library, template, business_applications, check_lists, guest, kpi` |
| `vCommunity|Collection Health|Collector:<name>|Failures` | metric | rule-1 count for that collector |

When the vCenter object is not resolved these keys cannot land; the same figures always land on the adapter
instance (2.4).

Failure cause catalogue (`FailureCause`, each with a fixed id used in logs and tests): `F-LOGIN`, `F-SOAP-<read>`
(one per R-xx read), `F-SOAP-INVALIDPROP`, `F-HOST-INSTALLDATE`, `F-HOST-PACKAGES`, `F-REST-LIST`,
`F-REST-LIB`, `F-REST-ITEM`, `F-OPS-MAP-<kind>`, `F-OPS-STATS-<set>`, `F-OPS-PROPS-<set>`, `F-OPS-HISTORY`,
`F-OPS-REL`, `F-CERT-PROBE`, `F-CERT-READBACK`, `F-CHECKLIST-<file>`, `F-GUEST-<step>`, `F-PUSH`,
`F-EVENTS`, `F-DEADLINE`.

### 5.3 The 19 failure-becomes-value mechanisms (map catalogue) and the Java behaviour

| # | Upstream mechanism (rows: TSV `Y:` flags) | Java | DV |
|---|---|---|---|
| 1 | `str(None)` gives `"None"` for an absent path | nothing (rule 2) | DV-08 |
| 2 | explicit `"null"` placeholders (VAAI, DHCP, search domain, HBA fields, HA off, DRS off, EVC mode, customization, Detailed Data, starts-connected, vCenter options) | nothing; feature-off transitions per Q1 | DV-09 |
| 3 | failed `installDate()` gives `"null"` | nothing, counted `F-HOST-INSTALLDATE` | DV-10 |
| 4 | counts read 0 when the source is missing (HBA, extents, SCSI, effective hosts, op notification timeout, template vCPU/memory/disk, library sizes) | nothing when the source is absent; `0` only for a returned empty collection | DV-11 |
| 5 | Max EVC `"[]"` | nothing | DV-12 |
| 6 | `"Unknown"` (license fields, Patch Level, disk share level, disk backing) | nothing | DV-13 |
| 7 | `"N/A"` PCI fields with no PCI match | nothing | DV-14 |
| 8 | NIC Status `"Disconnected"`, Duplex `"half-duplex"` on link down | Status kept (reading; Q2); Duplex nothing | DV-15 |
| 9 | DRS Score 0 when DRS is off or negative | nothing | DV-16 |
| 10 | empty strings (template guest OS, hardware version, datastore list, folder; library and item text) | nothing when absent; `""` only when the source returned an empty value | DV-17 |
| 11 | library counts treat a missing `cached` / `security_compliance` as not stored / not compliant | the library's count withheld | DV-18 |
| 12 | resource pool counts 0 for an unmatched cluster or a silently empty pool query | nothing; `0` for a matched cluster with no pools after a successful read | DV-19 |
| 13 | VMware Tools counts 0/0 when the unscoped VM query silently returns nothing | nothing on a failed query; `0` only after a successful query | DV-20 |
| 14 | host availability: failed stats batch drops hosts to at most 75; cluster pads missing hosts with 0 | failed batch: those hosts and their clusters withheld. Kept: a condition with no data after a successful read scores 0 for that condition, and hosts counted in N but absent from the successful reads are padded with 0 (the metric's definition) | DV-21 |
| 15 | Datacenter network count 0 when its hosts have no value | nothing | DV-22 |
| 16 | Certificate Status `"Recorded"` (and the recorded thumbprint overwritten) on a non-200 or empty read-back; `"Unknown"` when it raises or the probe fails | Status withheld and the recorded value never overwritten on a failed read-back or probe | DV-23 |
| 17 | KPI 100 (0 after the flip) when every row with data is green-skipped; Consumption forced to 100 at zero usable capacity | **kept**: both are the algorithm's result on real data (Q2). A usable capacity that is absent (not zero) withholds the KPI | none |
| 18 | Collection Health 0 and `"None in the last cycle"` every cycle | **kept** (5.2) | none |
| 19 | aggregates published over partial batches (issue 60) | rule 4: withheld | DV-24 |

### 5.4 Host license key mask (R3)

`LicenseKeyMask.mask(key)`: split on `-`; every character of every group except the last is replaced with
`*`; the last group is kept; hyphens kept. Example `AB12C-DE34F-GH56I-JK78L-MN90P` becomes
`*****-*****-*****-*****-MN90P`. A key without `-`: all but the last 5 characters replaced with `*` (a key of 5
or fewer characters is fully masked). Empty or absent key: withheld. The full key never appears in a log
line, an exception message or a push. Test vectors include the evaluation key (`00000-00000-00000-00000-00000`
to `*****-*****-*****-*****-00000`). DV-25.

### 5.5 A bad VM Options entry is isolated

1. **Syntax** (`VmOptionPath.isValid`): one or more segments separated by `.`, each matching
   `[A-Za-z][A-Za-z0-9]*`, at most 256 characters. Anything else (spaces, `[0]`, `/`, a trailing dot) is
   skipped and reported before any call.
2. **Probe** (once per distinct list content and vCenter session, re-run after a reconnect): one
   `RetrieveProperties` of type `VirtualMachine` for one VM MoRef with only the list paths, through
   `postFixingPaths` in drop mode. Every path vCenter rejects as `InvalidProperty` is removed and reported
   (`F-SOAP-INVALIDPROP` names the path, not counted as a cycle failure after the first report). The accepted
   set is cached under the list content hash.
3. **Main read:** only accepted paths join R-VM. If the main read still faults with InvalidProperty (a
   vCenter upgrade between probes), `postFixingPaths` drops the named path and repeats; the base VM keys are
   never lost to an options entry (DV-26). A fault that does not name a path fails R-VM as a whole (rule 1).
4. **Values:** a scalar (string, number, boolean, enum, dateTime) renders via `PyText`; a data object or an
   array is skipped and reported once ("not a single value") because upstream's Python object text cannot
   be reproduced (DV-26). Unset on a VM: nothing.

### 5.6 Never send a null

`PushSet.prop(resourceId, key, String)` and `PushSet.stat(resourceId, key, double)` are the only way to
queue a value. They reject (and count as a programming error, logged once per key at WARN): a null or blank
resource id or key, a null string, a NaN or infinite double. `Double` boxing is never exposed to collectors.
A unit test feeds every collector an all-absent `Inventory` and asserts the PushSet is empty.

### 5.7 Deviation register

Every place the Java pak intentionally differs from upstream 0.8.1. "Effect" is what a user can see.

| DV | Upstream | Java | Why | User-visible effect |
|---|---|---|---|---|
| DV-01 | finds the VMware adapter instance by `VCURL` equal to the `host` string | finds the VMwareAdapter Instance by `VMEntityVCID` equal to vCenter `instanceUuid` | a string match fails on FQDN vs IP vs case | accounts entered by IP or another alias work instead of failing the cycle |
| DV-02 | two matches: first wins | two objects with the same VCID: vCenter keys held back, counted | never guess the target | duplicate vCenter accounts in the VMware pack show missing vCenter keys plus a health count |
| DV-03 | VM to host by host display name (Ops property) | by `runtime.host` MoRef this cycle | same-named hosts merge | KPIs correct with duplicate host names; vMotion reflected one VMware cycle sooner |
| DV-04 | host to cluster by cluster display name | by host `parent` MoRef | same-named clusters in two Datacenters merge | cluster KPIs, availability and consumption stop mixing same-named clusters |
| DV-05 | host to Datacenter and Datacenter object by name | membership by per-Datacenter container view; object by MoRef + VCID | same-named Datacenters share a count | per-Datacenter counts correct |
| DV-06 | World = first result of an unscoped query | singleton lookup; zero or several: World keys held back | never guess | World keys absent (with health count) if Ops has more than one World |
| DV-07 | duplicate MoRef: whichever the code met | matched to neither, counted | MOID trap rule | object with a duplicated Ops identity gets no keys |
| DV-08 | absent path sends `"None"` | nothing | report honestly (mechanism 1) | key shows no value (or its last real value) instead of `None` |
| DV-09 | `"null"` placeholders (mechanism 2) | nothing (see Q1 for feature-off transitions) | report honestly | key shows no value instead of `null` |
| DV-10 | failed `installDate()` sends `"null"` | nothing, counted | report honestly | Install Date keeps its last real value; health shows the failure |
| DV-11 | missing source counts as 0 | nothing; 0 only for a returned empty collection | report honestly | no false zeros |
| DV-12 | Max EVC `"[]"` | nothing | report honestly | no `[]` text |
| DV-13 | `"Unknown"` license, Patch Level, share level, backing; sentinel license instance `Unknown` | nothing; such license assignment not published | report honestly | no `Unknown` values or `Licensing:Unknown` instances |
| DV-14 | `"N/A"` PCI fields | nothing | report honestly | no `N/A` |
| DV-15 | Duplex `"half-duplex"` on link down | nothing while down | a down link has no duplex | Duplex blank (or last real value, Q1) while the link is down |
| DV-16 | DRS Score 0 when DRS off or negative | nothing | report honestly | no false 0 scores in DRS views |
| DV-17 | empty strings for absent template and library fields | nothing when absent | report honestly | blank stays blank, no overwrite of a real value with "" |
| DV-18 | missing `cached` / `security_compliance` counted as not stored / not compliant | library count withheld | report honestly | the two counts may be absent for some libraries (E-L1) |
| DV-19 | resource pool counts 0 for unmatched clusters or a silent empty query | nothing | report honestly | no false zeros |
| DV-20 | Tools counts 0/0 on a silently empty query | nothing on failure | report honestly | no false "all tools fine" |
| DV-21 | failed batch caps host availability at 75 | hosts and clusters of a failed batch withheld | report honestly | no false availability drops during Suite API trouble |
| DV-22 | Datacenter count 0 with no host values | nothing | report honestly | no false 0 |
| DV-23 | certificate `Recorded`/`Unknown` on failed read-back or probe; recorded thumbprint overwritten | withheld; recorded value never overwritten | a failed read must not reset trust history | no spurious `Recorded` after an Ops hiccup; a real change is never masked |
| DV-24 | aggregates over partial batches | withheld unless all input reads succeeded | report honestly (issue 60) | fewer values during partial failures, none of them wrong |
| DV-25 | full host license key published | masked to the last group | secret hygiene (owner decision) | views show `*****-...-MN90P` |
| DV-26 | one invalid VM Options path fails the whole VM read; object values published as Python text | invalid path skipped and reported, VM read unaffected; non-scalar values skipped | isolation (owner decision); Python object text is not reproducible | a typo in the list costs one key, not every VM key |
| DV-27 | file read failure or invalid XML: list empty this cycle | fetch or parse failure keeps the last good list; an absent file clears it | do not silently stop collecting on an Ops hiccup | check-list keys keep updating through transient store errors; the event says so |
| DV-28 | Windows service and event files read every cycle, events raised for them even with monitoring Disabled | read only when the matching monitoring is Enabled | no spurious configuration events | no warning events about files nobody uses |
| DV-29 | unknown guest TLS mode fails the whole cycle | guest phase off for the cycle, health `guest` = FAILED, rest collects | isolation | a typo there no longer stops all collection |
| DV-30 | event-list structure not checked (silent in the guest) | validated, problem reported, list not used | report honestly | operator told the file is wrong |
| DV-31 | events sent as SDK events in the collect result (configuration problems on vCenter, Windows events on VMs) | `POST /api/events/bulk` as DIAGNOSTIC/LOG | NOTIFICATION events pushed onto a foreign VM are silently dropped; DIAGNOSTIC lands (`vcommunity-notification-events-foreign-vm.md`) | events appear on the object's events/troubleshooting timeline, not the notification stream (Q11) |
| DV-32 | Warnings in Last Cycle counts every logger's WARN records | counts the pak's WARN lines and failed push batches; adds the health keys of 5.2 and the self metrics of 2.4 | the pak cannot hook every logger; failures need their own counts | counts can differ from upstream's; more health detail |
| DV-33 | PCI ids formatted from signed shorts (ids above 0x7FFF negative, E13) | unsigned 4-digit hex | correct id | `8086`, not `-7f7a` (only if E13 shows upstream is negative) |
| DV-34 | unknown SCSI controller type shows a Python class name | the vim25 type name | Python names not reproducible | different text for rare controller types |
| DV-35 | resource pool levels from Ops PARENT relationships, one GET per pool | from the vim25 pool tree | P calls per cycle down to one read | same values if E9 confirms; else fallback |
| DV-36 | port groups read again per Datacenter | from the host bulk read plus DVPG per Datacenter | cost | none |
| DV-37 | ten `QueryOptions(name)` calls; failure gives `"null"` | one `QueryOptions` for all; missing key withheld | cost; report honestly | no `null` values |
| DV-38 | vim25 login and logout every cycle; no timeouts on SOAP and Suite API | one session reused, relogin on NotAuthenticated; every call has a timeout; cycle deadline interval minus 60 s, pushes what completed | long-lived adapter; a hung call must not hang the collector | fewer vCenter logins in vCenter's session list; a slow cycle reports partial data instead of none |
| DV-39 | guest gate re-reads `toolsStatus` and `guestFamily` live, twice per script per VM | from the VM bulk read | cost (2 to 3 SOAP calls per VM per script) | none |
| DV-40 | PowerShell started with `-Command "<command>"` (doubled quoting, unverified), service list as a PowerShell array literal, exit code ignored, CSV with a BOM | `-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand` (8.3), inputs as files, non-zero exit is a failure, CSV written without BOM and parsed BOM-tolerant | the Windows-services-empty finding; injection safety | guest keys can appear where upstream returned nothing |
| DV-41 | service CSV without `StartType` (PowerShell before 5.0): nothing published | Service Name and Status published, Start Type withheld | partial data is still real data | older Windows guests show two of three keys |
| DV-42 | event criticality from localized `LevelDisplayName` (non-English: always INFO) | from the numeric level, message text unchanged | localization | correct severity on non-English guests |
| DV-43 | guest budget 1800 s per cycle, serial, same VM order every cycle | until the cycle deadline, 4 guests in parallel, rotating cursor | a 5-minute cycle; starved VMs | every Windows VM eventually collected; a VM's guest keys may update every few cycles at scale (Q10) |
| DV-44 | guest monitoring on without a Windows credential: an error per VM per cycle | guest phase skipped, one WARN, health `guest` = SKIPPED | noise | one clear message |
| DV-45 | transfer URL with `*` as host used as is | `*` replaced by the ESXi host's name (only if G4 shows it occurs) | broken URL | guest transfers work behind such a setup |
| DV-46 | any library REST failure drops all libraries | per-library and per-item isolation | isolation | one bad item no longer blanks every library |
| DV-47 | VM Template objects only for templates the VMware adapter also models as VirtualMachine | for every template in vCenter (Q5) | the gate was an artefact of loop order | template objects appear even if the VMware adapter does not model templates (E5) |
| DV-48 | template datastore and folder names read per object | from bulk reads | cost | none |
| DV-49 | every property pushed every cycle | properties on change, full refresh every 12th cycle and after start | bytes | property sample timestamps update less often; values identical |
| DV-50 | own kinds under adapter kind `vCommunity` | under `vcfcf_vcommunity`; content subjects re-pointed | new kind (lesson: no cross-runtime upgrade) | own objects are new objects; no history carried |
| DV-51 | Pinned REST accepts SHA-256 only | SOAP and REST accept SHA-256 or SHA-512 | one trust manager | a 128-hex pin also works for libraries |
| DV-52 | Enabled uses the proxy OS trust store (SOAP) and certifi (REST) | platform trust plus the accept dialog | in-collector adapter | a self-signed vCenter can be accepted in Validate Connection |
| DV-53 | invalid instance fields warned twice per cycle | once | noise | one warning |
| DV-54 | 101 views that are edited built-in views ship under built-in ids; 19 renamed built-ins ship under built-in ids | 101 re-authored under new ids and fresh titles; 19 not shipped, referenced in place | `pak-content-must-not-reuse-stock-ids.md` | installing or removing the pak never overwrites or deletes built-in views; 101 views have new titles |
| DV-55 | (only if Q1 is accepted) `None`/`null` sent while a feature is off | on a set-to-unset transition, `""` pushed once | a property keeps its last value forever | a turned-off feature's settings show blank, not their old values |
| DV-56 | whole `guest` object read for every VM | the ten sub-paths | bytes and heap | none (Detailed Data on an older vCenter: withheld, as rule 2) |
| DV-57 | sentinel instance names (`Unknown Adapter`, `unknown`, `Unknown`) for devices without labels | such devices not published | a sentinel instance is a fake object | no `Unknown` instances |
| DV-58 | (only if Q3 is accepted) disconnected hosts keep their last Availability | Availability published for every host of the vCenter | issue 86 | World availability includes disconnected hosts |
| DV-59 | (only if T3 has not landed) `Maintenance Mode Required` numeric property | withheld until T3 | no string into a numeric history | key absent until the framework sends numeric properties |
| DV-60 | a check-list item with a line break is used verbatim (always invalid) | skipped and reported | report honestly | operator told to add commas |

60 rows (DV-55, DV-58 and DV-59 are conditional).

---

## 6. State across cycles

| State | Upstream | Java | Cold start (adapter start, reconfigure, failover to another collector) | First cycle ever |
|---|---|---|---|---|
| Certificate thumbprint, previous thumbprint, Last Changed, 24-hour Changed window | read back from the vCenter object every cycle | **memory**, `CertificateState` | read back `Certificate|SHA-256 Thumbprint` and `Last Changed` from the vCenter object (properties latest). Read failed: Status withheld, retried next cycle, never "Recorded" (DV-23) | read-back succeeded and empty: Status `Recorded`, thumbprint published |
| Periodic Cluster Check "already published for window W" per cluster | latest timestamps of the 4 Periodic keys every cycle | **memory** map cluster id to last window end published | read back the latest timestamps of the 4 Periodic keys and 3 KPI keys for this vCenter's clusters (one request per 1,000) | parity: due at the first window end once KPI samples exist in the window |
| Periodic Cluster Check values | history of the 3 KPI keys | **read every time** (it is the data), `resources/stats/query` AVG, 5 minutes, window bounds, 100 clusters per request | same | partial first window gives values from what exists (parity) |
| Cluster Delta once-per-window gate | World's two counts' timestamps | **read back while not done for the window** (another instance may have published it); memory remembers "done for W" after a read-back or own push | read back | parity: 0 and 0 once per window until two consecutive windows of Close for Business exist |
| World roll-ups and Business Applications | read-backs of stored values, all vCenters | **read back every cycle** (other instances' outputs; cannot be memory) | same | not published until values exist (parity) |
| Last pushed property hashes (DV-49) | none | memory | empty: full push | full push |
| Accepted VM Options paths, Ops resource maps, World id | none | memory (maps refreshed on the 12-cycle cadence; World id looked up every cycle) | rebuilt | rebuilt |
| Check-list last good parse | none | memory | lost: a fetch failure on the first cycle after start means that list is empty for the cycle (reported) | same |
| Guest cursor | none | memory | restarts at the first VM | same |

Restart and failover need nothing persisted outside Ops: the cold-start read-backs reconstruct the two
pieces of state upstream designed to survive (certificate, periodic check). Two pak instances on the same
vCenter (duplicate accounts) each hold their own memory and write the same keys: certificate and periodic
values converge because both read the same sources; acceptable and parity-equivalent (E11).

The periodic design depends on our pushed timestamp being the sample timestamp Ops stores (map gap 18). In
Java the pak sets it (`pushBatch(..., T)`), so it carries over; E12 confirms history reads return those
timestamps on all three lines.

---

## 7. Derived metrics

### 7.1 Engine specification

Limits: Appendix A (49 rows, the facts from upstream's `kpi_tables.tsv`). `KpiTable` loads them from a
bundled resource file `conf/kpi_tables.tsv` with the same columns; tests pin the row count and each row.

`KpiScorer.score(value, limits)`:
1. Round the value with `PyRound.round2` (Python `round(x, 2)`: exact binary value, half-even;
   `new BigDecimal(x).setScale(2, HALF_EVEN)`).
2. Higher-is-better when `zero_at < best`: negate the value and all five limits.
3. Score points (best 100, green 75, yellow 50, orange 25, zero_at 0). At or below best: 100. Inside a tier,
   linear between the tier's two scores. A tier of zero width is skipped. Beyond zero_at: 0.
4. Weight `2^((100 - score)/25)`. KPI = weighted mean of row scores, `round2`.
5. `skip_when_green` rows are left out while the value is at or below best, or below green (after negation).
6. No value: row left out. No row with data: no KPI. Every row with data skipped as green: KPI 100.
7. Cluster Risk and Cluster Consumption publish `100 - KPI`.
8. `published_by_pack = False` rows are scored but not pushed.

Inputs (Suite API latest stats, keys exactly as the map's D1-D7; staleness drops samples older than 600 s,
Number of Port Groups on World 900 s; properties are last known, never filtered):

| KPI (kpi_tables group) | Object | Inputs | Scope (membership 3.2) |
|---|---|---|---|
| Cluster Performance (D1) | cluster | VM `cpu|20_sec_peak_readyPct`, `cpu|20_sec_peak_costopPct`, `mem|20_sec_peak_host_contentionPct`, `virtualDisk|20_sec_peak_totalLatency_average` (worst = max, 90th = nearest rank); host `net|errorsRx_summation_sum`, `net|errorsTx_summation_sum`, `net|droppedRx_summation_sum`, `net|droppedTx_summation_sum`, `net|packetsRx_summation_sum`, `net|packetsTx_summation_sum` | powered-on VMs (Ops `summary|runtime|powerState == "Powered On"`) on the cluster's hosts |
| Cluster Risk (D2) | cluster, max over hosts | host stats and properties listed in the map D2; monster rows use instance fields 12-14 | cluster's hosts |
| Cluster Consumption (D3) | cluster | cluster `cpu|demand|usableCapacity`, `cpu|capacity_provisioned`, `mem|demand|usableCapacity`, `mem|host_provisioned`; host D2 stats of this cycle plus `mem:NVMe|tier.usage`, `mem:NVMe|memory_tier_size`; running-host rule of D3 | cluster's running hosts |
| ESXi Performance (D4) | host | D1 rows over the host's powered-on VMs plus its own bad-packet % | published for connected hosts only |
| VM Performance (D5) | powered-on VM | map D5 keys; Memory Zip Swap = `(mem|compressed_average + mem|swapped_average) / guest|used_memory x 100` | |
| Guest OS Performance (D6) | powered-on VM | `guest|20_sec_peak_cpu_queue`, `guest|20_sec_peak_disk_queue`, `guest|mem.free_latest / 1024`, `guest|page.outRate_latest` | |
| VM Guest OS KPI (D7) | powered-on VM | mean of D5 and D6, D5 alone when D6 missing, nothing when D5 missing | |
| Operational Availability (D8) | host, cluster, vCenter | host: `sys|poweredOn` stat and three runtime properties, 25 each; cluster: N, k and the formula of R221; vCenter: min of clusters | |
| Network Speed Degradation (D12) | host | per-NIC instance stats `net:<nic>|speed`, `net:<nic>|configuredSpeed` (latest-stats request asking for instances) | |

Percentiles (`Percentile`, nearest rank): p-th = `sorted[max(ceil(p/100 x n), 1) - 1]`; 90th with fewer than
10 values is the max; World 10th = `sorted[ceil(0.1 n) - 1]`.

Periodic Cluster Check (`PeriodicWindow`, `PeriodicCheck`): window end = latest `HH:MM` UTC + k x period at or
before now (period divides 24), start = end minus one period; due test, 500-per-cycle rotation by
`(cycles since window end x 500) mod due` over clusters sorted by Ops id, history read, Worst Performance =
worst-percent from the low end of the Cluster Performance Score samples, Worst Risk and Worst Consumption =
(100 - worst%)th percentile, Close for Business thresholds (red below 20, orange below 40 on health = value or
100 - value): exactly the map's D9. Cluster Delta: the map's D10, with "any failed batch: nothing" kept.

### 7.2 Cycle-ordering dependencies

- **Same cycle, in memory:** host availability before cluster availability before vCenter's worst cluster
  availability (R195, R221, R212); host Network Speed before the Datacenter count (R196, R197); D2 host stats
  reused by D3; D5 and D6 before D7.
- **Previous cycle, read back:** World roll-ups (R198, R201-R211), Business Applications (R215-R217, from VM
  Guest OS KPI), Periodic Cluster Check (from KPI history), Cluster Delta (from Close for Business history).
- The engine runs after phase C; nothing it computes feeds another collector in the same cycle except the
  in-memory chains above. No job reads another job's push in the same cycle (parity).

### 7.3 Fixture format for the upstream worked examples

Upstream's tests carry worked examples (inputs and expected outputs). These are facts; they are re-expressed
as JSON vectors, not code. **Who:** `api-cartographer` extracts them into
`knowledge/context/api-maps/vcommunity-e1-kpi-fixtures/` (one file per upstream test module), one vector per
example; the author copies them into `tests/fixtures/kpi/` and a plain-JDK test runs every file.

Two vector shapes:

```json
{
  "id": "risk-cpu-thread-util-tier-yellow",
  "source": "upstream test module and test name (text only)",
  "kind": "rows",
  "kpi": "Cluster Risk Score",
  "rows": [ {"sub_metric": "Highest ESXi CPU Thread Utilization", "value": 85.0} ],
  "expected": { "row_scores": {"Highest ESXi CPU Thread Utilization": 37.5}, "kpi": 37.5, "published": 62.5 },
  "deviation": null
}
```

```json
{
  "id": "cluster-availability-padded",
  "kind": "engine",
  "now_ms": 1794000000000,
  "config": { "cluster_check_period_hours": "24", "periodic_cluster_check_time": "00:00",
              "cluster_check_worst_percent": "5", "monster_vm_cpu_percent_of_cores": "50",
              "monster_vm_memory_percent_of_dram": "40", "monster_vm_memory_min_gb": "256" },
  "inventory": {
    "clusters": [ {"moref": "domain-c1", "ops_id": "c1"} ],
    "hosts":    [ {"moref": "host-1", "ops_id": "h1", "cluster": "domain-c1", "datacenter": "datacenter-1"} ],
    "vms":      [ {"moref": "vm-1", "ops_id": "v1", "host": "host-1"} ]
  },
  "ops": {
    "stats":      [ {"id": "h1", "key": "sys|poweredOn", "ts": 1793999900000, "value": 1.0} ],
    "properties": [ {"id": "h1", "key": "runtime|connectionState", "value": "connected"} ],
    "history":    [ {"id": "c1", "key": "vCommunity|Cluster Performance|Cluster Performance Score",
                     "ts": [1793990000000], "values": [88.5]} ],
    "failed_reads": [ "stats:host" ]
  },
  "expected": {
    "pushes":   [ {"id": "c1", "key": "vCommunity|Availability|Cluster Operational Availability", "value": 100.0} ],
    "withheld": [ {"id": "c1", "key": "...", "cause": "F-OPS-STATS-host"} ]
  },
  "deviation": "DV-21"
}
```

Rules: upstream examples that encode a failure-becomes-value outcome are kept with `deviation` naming the DV
row and `expected` rewritten to the Java outcome, plus `upstream_expected` holding the original value, so the
register is tested. Upstream examples written against name joins are re-expressed with MoRef membership
(`inventory`), same expected values. The illustrative numbers in the two blocks above are placeholders, not
upstream data.

---

## 8. Guest operations and events

**This is the section with unproven platform behaviour.** Shipped disabled by default (`serviceMonitoring`
and `winEventMonitoring` default `Disabled`, parity). It cannot be called done until the experiments in 8.7
pass on a real hardened Windows guest and on all three platform lines.

### 8.1 Gate and plan (`GuestPlan`, SDK-free)

- On when `serviceMonitoring == Enabled` (services and OS information) or `winEventMonitoring == Enabled` with
  a non-empty, valid event list (events). Guest TLS mode invalid: phase off, health FAILED (DV-29). No
  `winUser` or `winPass`: phase off, one WARN, health SKIPPED (DV-44).
- Candidate VMs from R-VM: `guest.toolsStatus == toolsOk` and `guest.guestFamily == windowsGuest`, resolved to
  an Ops resource id, not a template (DV-39).
- Order: `GuestCursor` (rotating, memory) so the VMs not reached this cycle are first next cycle (DV-43).
  Per VM, scripts in upstream order: services, OS information, events.
- Budget: phase starts after the push of phase E; deadline = cycle deadline. 4 VMs in parallel
  (`GUEST_WORKERS`, constant). A started VM is not interrupted by the deadline (parity), but its per-call
  timeouts still apply. Results of VMs that finish after the main push are pushed at the end of the phase in
  one more batch.

### 8.2 Call sequence (raw SOAP through `GuestOpsClient`, lifted in shape from the retired
`/mnt/holding/vcf-content-factory/retired-paks/vcommunity-os/src/.../GuestOpsClient.java`, fixed)

Auth: `NamePasswordAuthentication(winUser, winPass, interactiveSession=false)` in every call; never logged.
Constants as upstream: temp parent `C:\Windows\Temp`, interpreter
`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`, directory prefix `VCFOperationsvCommunity-`,
suffixes `-Services-TEMP`, `-OSInfo-TEMP`, `-EventLog-TEMP`.

1. `CreateTemporaryDirectoryInGuest(vm, auth, prefix, suffix, C:\Windows\Temp)`.
2. Inputs as files: services: `InitiateFileTransferToGuest` for `<dir>\services.txt` (UTF-8, no BOM, one
   filtered name per line); events: `CreateTemporaryFileInGuest(prefix "events", suffix ".xml", dir)` plus
   transfer of the event XML, then `ListFilesInGuest(dir, 0, 100)` name check (case-insensitive), parity.
   HTTPS PUT per 8.4, 10 s connect, 300 s read, 200/201 = ok.
3. `StartProgramInGuest(programPath = powershell.exe, arguments = see 8.3, workingDirectory = dir)`.
4. Poll `ListProcessesInGuest(vm, auth, [pid])` with sleeps 1, 2, 4, 8, 10, 10 ... s until `exitCode` is set or
   300 s; on timeout `TerminateProcessInGuest`, script skipped (`F-GUEST-TIMEOUT`). A process no longer listed
   counts as finished. **Exit code checked:** 0 = ok; anything else = `F-GUEST-EXIT` (DV-40).
5. `InitiateFileTransferFromGuest(vm, auth, <dir>\out.csv)`; HTTPS GET of the returned URL (a `*` host
   replaced per DV-45, only after G4); 200 = body (cap 1 MB, `F-GUEST-TOOLARGE` above it).
6. Parse (8.5) and queue keys.
7. Finally `DeleteDirectoryInGuest(vm, auth, dir, recursive = true)`; failure logged at WARN once per cycle.

Every step's fault is captured in the call's `VimResult` and becomes a `F-GUEST-<step>` cause for that VM;
one VM's failure never affects another VM or the cycle.

### 8.3 The three scripts (rewritten; shipped as `conf/scripts/*.ps1` in the pak, read at configure)

Invocation (`PsCommand`): `-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand <b64>`,
where `<b64>` is Base64 of the UTF-16LE text of the script body with its two input paths and its output path
bound as PowerShell single-quoted literals (`'` doubled) at the top. Evaluation:

- `-NonInteractive`: kept. A prompt in a Tools-launched process would hang until the 300 s kill.
- `-ExecutionPolicy Bypass`: kept, but it only overrides the Process scope; a Group Policy MachinePolicy or
  UserPolicy wins over it, so on a hardened domain controller it does not help a *script file*. This is why
  the body goes through `-EncodedCommand`: execution policy governs script files, not command text, so the
  leading theory for the empty-services finding (`vcommunity-windows-services-empty-2026-06-23.md`, policy
  blocks the Tools-launched script) is avoided rather than overridden. Constrained Language Mode under
  AppLocker or WDAC still applies to command text; the scripts therefore use only cmdlets and
  `[PSCustomObject]` literals, no .NET method calls except the no-BOM writer below, which has a CLM-safe
  fallback (`Out-File -Encoding utf8` plus BOM-tolerant parsing).
- Fallback if G3 shows the arguments length is limited: upload the script and run with `-File`.

Output: each script builds its objects exactly as upstream (same properties, same order, so the values render
with the same default formatting, including the guest culture's date text for `LastBootUpTime`), converts with
`ConvertTo-Csv -NoTypeInformation`, writes the lines with
`[System.IO.File]::WriteAllLines($out, $lines, (New-Object System.Text.UTF8Encoding($false)))`, and ends with
`exit 0`; a terminating error writes nothing and `exit 2`.

| Script | Behaviour | Columns |
|---|---|---|
| OS information | `Get-CimInstance Win32_OperatingSystem` and the registry `ReleaseId`, one row | `Name` (Caption), `Version`, `BuildNumber`, `OSArchitecture`, `LastBootUpTime`, `ReleaseId` |
| Services | names from `services.txt`; per name `Get-Service -Name <n> -ErrorAction SilentlyContinue`; not found skipped; `StartType` emitted empty when the property does not exist (DV-41) | `Name`, `DisplayName`, `Status`, `StartType` |
| Events | event XML from the file; for each `Log/@Name` and each `EventID`, `Get-WinEvent -FilterHashtable @{LogName; Id; StartTime = now - 5 min} -MaxEvents 1 -ErrorAction Stop` in try/catch, where "no events found" is not an error and any other error is written to the host stream and skipped (parity) | `Level` (`LevelDisplayName`), `LevelNumber` (`Level`, new), `Event` (`[Timestamp=<TimeCreated>] [Category=<log>] [EventID=<id>] [Source=<ProviderName>] [Message=<Message>]`) |

An empty service list runs no script (map gap 7 sidestepped; upstream behaviour unverified).

### 8.4 Guest file-transfer TLS (`GuestTls`)

| Mode | Java | Identical? |
|---|---|---|
| Pinned (default) | adapter trust manager compares the ESXi leaf hash with the host's `summary.config.sslThumbprint` from R-HO (40 hex: SHA-1; 64 hex: SHA-256); no recorded thumbprint: transfer unchecked, one WARN per host per cycle | yes; FIPS 9.1 SHA-1 digest availability: E15 |
| Strict | as Pinned; no recorded thumbprint: VM skipped | yes |
| Disabled | trust-all | yes |

No hostname check in any mode (the pin replaces it). A fresh connection per transfer. Thumbprints come from
the cycle's R-HO snapshot (no per-transfer reads; upstream read `vm.runtime.host` and `host.summary` per
transfer).

### 8.5 CSV parsing (`CsvParser`, SDK-free)

- Decode UTF-8; drop one leading U+FEFF (the byte-order mark question, map gap 5: handled either way).
- RFC 4180: fields separated by `,`, quoted fields may contain `,`, `""` and **line breaks** (event messages
  are multi-line; the retired parser split lines first and broke on them).
- Header by name, never position (`SKILL.md` canonical loader rule). Required columns: OS information all six;
  services `Name`, `DisplayName`, `Status` (`StartType` optional); events `Level`, `Event` (`LevelNumber`
  optional). A missing required column: nothing published for the script, `F-GUEST-HEADER`.
- A row with fewer fields than the header: skipped and counted.
- Publishing: OS information R72-R77, every data row, last wins (parity); services R78-R80 instance
  `DisplayName` (a duplicate display name: last wins, parity); empty cells withheld.

### 8.6 Events

- Transport: `POST /api/events/bulk` with `eventType: DIAGNOSTIC`, `diagnosticSubType: LOG`, `resourceId` =
  the foreign object's Suite API id, `startTimeUTC` = now. **TOOLSET GAP T2:** the framework stitcher has no
  events call; `tooling` adds `pushEvents(List<Event>)` (never throws, returns sent/failed counts, one WARN
  per cycle on failure).
- Windows events: one per CSV row, at most 100 per VM per cycle (rest counted), message
  `[WindowsEvent-<Level> <Event>]`, severity from `LevelNumber` (1 CRITICAL, 2 IMMEDIATE, 3 WARNING, 4 or 5
  INFORMATION), falling back to upstream's `LevelDisplayName` map (Information/Verbose INFORMATION, Warning
  WARNING, Error IMMEDIATE, Critical CRITICAL, else INFORMATION) (DV-42).
- Configuration-problem events: on the VMwareAdapter Instance, WARNING (4.10).
- Clearing (upstream: auto-cancel, watch 1, cancel 3): `managedExternally: false` and not re-pushing is the
  documented auto-cancel analogue; whether it cancels after one cycle, three, or never for a GENERAL adapter's
  REST event is unknown (G5). If G5 shows no auto-cancel, switch to `managedExternally: true` with an explicit
  cancel (same message plus `cancelTimeUTC`) after three cycles without a repeat, tracked in memory.
- NOTIFICATION is never used: it returns 200 and is silently dropped (proven 2026-06-22).

### 8.7 Experiments required before guest operations are done

| # | Question | Pass condition |
|---|---|---|
| G1 | Does the old `Export-Csv -Encoding UTF8` BOM appear in the transferred body, and does our no-BOM writer work under CLM? | header parses with and without BOM; keys land |
| G2 | On a hardened DC (GPO AllSigned or Restricted, and one with AppLocker/WDAC CLM): does `-EncodedCommand` run the three scripts where `-Command` and `-File` fail? | services and OS keys on that DC |
| G3 | Is `GuestProgramSpec.arguments` length-limited (encoded body about 6 to 12 KB)? | the longest script starts |
| G4 | Does `InitiateFileTransferToGuest`/`FromGuest` return `*` as host behind a Cloud Proxy? | URL host recorded per line |
| G5 | DIAGNOSTIC event lifecycle for `managedExternally: false` and `true`: when does it cancel? | documented per line |
| G6 | Localized guest: `LevelDisplayName` text and `LevelNumber` | severity correct |
| G7 | Guest operations from a Cloud Proxy collector reach ESXi 443 for transfers | transfer 200 |
| G8 | 4 parallel guests per vCenter: any vCenter or Tools throttling? | no faults at 4 |
| G9 | Events visible on the VM's timeline in the UI, on 8.18.7, 9.0.2, 9.1.1 | seen in a browser |

---

## 9. Scale and resource budget

### 9.1 Call-volume model (symbols as the map: C, H, Hc, V, Von, DC, L, I, T, Ndue, Vx, Vw; pages
`pc(n,s) = ceil(n/s)`, `pg(n) = ceil(n/1000)`)

vim25 per cycle:

| Item | Java | Upstream |
|---|---|---|
| session | 1 keepalive (login only on a new or expired session) | about 5 |
| cert probe | 1 handshake | 1 |
| bulk reads | about 3 per type x 8 types + pages: `pc(C,10) + pc(H,50) + pc(Hc,25) + pc(V,50) + pc(DS,100) + pc(RP,500) + 2 x DC x 3 + 1` | 4 types, plus per-object hidden round trips |
| licensing, options | 2 | 2 + 10 |
| per host | Hc install date, Hc packages (list non-empty) | same |
| templates | 0 per template | T x (ds + 2) |
| guest gate | 0 | Vx x 2 to 3 per script |
| guest per Windows VM per script | about 6 manager calls + polls + 2 HTTPS (events +3 calls +1 HTTPS) | same plus thumbprint and name reads |

Suite API per cycle: check lists up to 6 GET (one token; upstream 18 calls); maps about 1 amortized
(`1 + 1 + pc(V,500) + 1 + 1 + 1` every 12th cycle); World id 1; latest stats `pg(Von)` VMs + 2 hosts + 1
clusters + 1 periodic timestamps; latest properties `pg(V)` VMs + 1 hosts; history `ceil(Ndue/100)` only in a
due window; World about 6 to 8 unscoped reads plus `pg(Vw_all)`; Business Applications `3 + Tr + A + Ac + E`
GETs + 2; pushes `ceil(changed property resources/100)` + `ceil(stat resources/100)` (and about 1 MB caps);
events 1 to 2. REST: `2 + 1 + 2L + I` (parity).

Example (C 10, H 100, V 2,000, Von 1,600, DS 50, DC 2, RP 50, L 5, I 100, guests off): vim25 about 250 calls
(about 50 of them bulk pages, 200 per-host); Suite API about 60 calls per cycle plus about 25 extra on the
hourly property refresh; REST 113. Upstream for the same: vim25 well over 300 plus per-template and
per-attribute round trips, Suite API about 120 including 18 for check lists and 3 x per-cluster requests.

### 9.2 Parallelism

| Pool | Size | Reason |
|---|---|---|
| inventory (vim25 bulk, REST) | 4 | vsanperf knee for one vCenter; upstream used 5 |
| per-host method calls | 8 | small calls; bounded so a large vCenter does not get 100 concurrent requests |
| Suite API read-back | 4 | local API; matches the stitcher's single-token model |
| guest | 4 | Tools operations are slow and per-VM |
| pushes | caller thread only | ordering (properties before stats) and one batch result |

All pools are created per cycle with named threads and shut down in finally; interrupts restore the flag.

### 9.3 Heap budget in the collector JVM

Budget: **65 MB peak per instance, 35 MB retained between cycles** (`knowledge/context/investigations/2026-11-06-collector-jvm-sizing.md`
Budget: 10 % of about 650 MB headroom on the devel 9.0.2 embedded collector, `-Xmx1024m`; the Cloud Proxy heap
is unknown; vsanperf adopted the same, `vsanperf-mp-v1.md` D6, and measured a 6.3 MB peak delta in its
default case, `vsanperf-mp-v3.md` "Heap").

| Holder | Estimate at the example | Control |
|---|---|---|
| one VM page in flight (50 VMs, device list, extraConfig when on, guest sub-paths) | 1 to 3 MB wire, never a whole-page DOM | StAX into `BulkRow`, `CappedInputStream` 16 MB per response |
| `Inventory` retained during the cycle | about 2 KB per VM, 4 MB for 2,000 VMs; hosts with options filtered to the list | compact projections |
| Ops maps | about 0.5 MB | ids and MoRefs only |
| read-backs | under 2 MB | parsed to `double` arrays per resource |
| PushSet | about 2 MB of stats; properties up to about 12 MB on a full refresh | properties are serialized batch by batch (1 MB), not all at once |
| LastPushed | about 6 MB (120,000 hashes) | long hashes keyed by interned resource and key ids |
| guest | 4 x 1 MB CSV cap | per-VM release |

Expected peak about 30 to 45 MB, retained about 15 MB. Must be measured.

### 9.4 What to measure in the scale run

A replay harness (vsanperf T4 pattern) with recorded SOAP and Suite API responses at 2,000 and 10,000 VMs, then
one live run on the largest lab vCenter on each line:

- cycle wall time per phase, per read, against the 240 s deadline; `deadline_hit` over 24 hours;
- heap used before and after each cycle (`Runtime`), peak delta against 65 MB, GC log on the embedded
  collector; a run on a Cloud Proxy collector with whatever heap figure is obtainable (E16);
- bytes per bulk page per type, pages, InvalidProperty fixes;
- Suite API calls and bytes per cycle, push batch count and time, `SuiteApiBatchResult` stats;
- vCenter session count and API call rate during the cycle (vCenter side);
- guest phase: VMs per cycle at 4 workers, average per-VM time, cursor lap time.

---

## 10. Content plan

Everything ships as factory YAML in the pak repo under `views/`, `dashboards/`, `reports/`, `supermetrics/`,
`symptoms/`, `alerts/`, and the six check-list files under `content/files/solutionconfig/` (the builder now
packs `content/files/**`, `sdk_builder.py` "content/files/"). Inventory of 0.8.1 (session evaluation, see
"Map and inventory insufficiencies" below): 52 dashboards, 189 distinct views, 16 reports, 2 super metrics,
2 symptom definitions, 4 alert definitions, 6 check-list files.

### 10.1 Id and name rules

| Content | Id | Name |
|---|---|---|
| The 101 views that began as edited built-in views | new ids minted by the factory | freshly written title and description; a title equal to any built-in view title on 8.18.7, 9.0.2 or 9.1.1 gets a distinct title |
| The 19 views that only renamed a built-in | **not shipped** | dashboards and reports reference the built-in view in place, by its built-in id; E17 checks each exists with the same id on all three lines; one missing on a line is re-authored under a new id instead |
| All other views (about 69) | upstream ids | upstream names |
| Dashboards (52) | upstream ids | upstream names (50-character editor limit, `dashboard-name-limit-50-editor.md`) |
| Reports (16), super metrics (2), symptoms (2), alerts (4) | upstream ids | upstream names |
| Check-list files (6) | same file names (`esxi_advanced_system_settings`, `esxi_packages`, `vm_advanced_parameters`, `vm_options`, `windows_service_list`, `windows_event_list`) | rewritten: own header text, every entry commented, examples one per line with trailing commas |

Every id that keeps upstream's value is checked against a clean export of each line by the stock-id guard
(issue #345); a collision means re-id it like the 101.

### 10.2 Re-authoring the 101 views from a neutral spec

For each, `view-author` receives a spec file `knowledge/designs/views/vcommunity-<slug>.md` with: subject
(adapter kind and resource kind), columns (metric or property key, aggregation, unit, transformation), filters,
sort, thresholds/colours, summary rows, time setting. Titles and descriptions are written new from the spec,
never copied. Specs are derived from upstream's XML by the orchestrator (facts only).

Subject re-pointing: content on upstream's own kinds (`vCommunity:Content Library` etc.) is re-pointed to
`vcfcf_vcommunity` (DV-50). Content on VMWARE and Container kinds keeps its subjects.

### 10.3 Dependencies on tooling in flight (content build is sequenced after these land)

| Need | Status |
|---|---|
| View schema fidelity (every column/filter/summary form upstream uses) | in flight |
| Importer fidelity (upstream XML to neutral spec without loss) | in flight |
| Dashboard time range and hidden flag | in flight |
| Report gaps; alert gaps (recommendations on sync, #346) | in flight |
| Stock-id guard at build, install and uninstall | #345 |
| Section widget | not available on 9.0.x (and assume 8.18): no dashboard may carry it; the build guard (`unknown-widget-type-aborts-pak-dashboard-import.md`, #199) must cover all 52 |
| Super metrics on foreign objects need policy enablement (`environment-totals-are-computed-metrics-not-super-metrics.md`) | document in the installing guide; the two SMs stay SMs (no percentile in ComputedMetrics, and they are upstream content) |

Alerts: `content_foreign_adapter_kinds: [VMWARE, Container]` covers "ESXi Host NIC Disconnected", "ESXi Host
License Expiring", "Windows Service Down" and "vCommunity Collection Warnings". Each depends on keys this
design keeps (NIC Status R30, Remaining Days R6, Service Status R79, Warnings R253). New-key alerts fire from the
second sample (`new-metric-alerts-need-two-samples.md`). RULE-011 applies to the dashboards (Q7).

---

## 11. Build sequence

Each phase ends with: validate-sdk, build-sdk (0.0.0.N), pak-compare zero BLOCKING, install on 9.0.2 devel
(Python pack never co-installed on the same Ops instance), the differential check, a CHANGELOG line.

**Differential check (TOOLSET GAP T5).** Run e1 0.8.1 collector-only (built from the sentania-labs fork with
its content stripped, so no stock ids are installed) on one lab Ops instance and the Java pak on another, both
against the same vCenter. A `tooling` CLI compares the two instances' `vCommunity|*` keys per (VCID, MoRef or
own identifier, key): key set equal; properties equal; metrics within 0.01 after rounding (or within a stated
tolerance for timing-skewed KPIs); every difference must map to a DV id listed in
`tests/fixtures/differential/expected-deviations.tsv` in the pak repo.

| Phase | Scope | Exit proof |
|---|---|---|
| P0 Prerequisites | managed_paks entry; T1, T2, T3 in the framework (tooling, framework-reviewer, PR); kpi table and content inventories committed (insufficiencies 1-3); recon for Q8 | registry reader lists the pak; buildkit release carrying T1-T3 |
| P1 Skeleton and configuration parity | describe.xml (2.1-2.4), `VCommunityConfig`, TLS modes, probe, session, `vCommunityCollector`, Test Connection (login, Suite API reachability, each check-list file's outcome and item count in the result message), health keys, self metrics | account dialog on 9.0.2 matches 0.8.1 field for field (labels, defaults, enums, main vs Advanced) seen in a browser; Test Connection passes in all three TLS modes against a lab vCenter and fails with the right text for a wrong pin; collector object DATA_RECEIVING; self metrics present |
| P2 Properties | 4.3-4.8 and 4.10 property rows, licensing mask, check lists, VM Options isolation | differential over the property rows: equal or registered; a deliberately bad VM Options entry costs only its key |
| P3 Own objects | libraries, items, templates, relationship, traversal | objects, identifiers, Content Library > Library Item in the UI tree; differential on R227-R252 |
| P4 Derived metrics | section 7, 4.9, 4.12, Datacenter, resource pools, port groups, periodic check across one full window | fixture tests green; differential within tolerance over 24 hours with at least one periodic window and one Delta |
| P5 Guest and events | section 8, T2 | experiments G1-G9 pass; keys and events on a Windows VM and on the hardened DC |
| P6 Content | section 10, after the tooling items land | stock-id guard clean on all three lines; dashboards counted after install (52); views render; alerts fire after two samples |
| P7 Scale and release | 9.4 runs; sdk-adapter-reviewer gate; defect gate (RULE-012) | heap and deadline within budget; RULE-019 install record (installed and collecting, account state checked after the restart watch) on 8.18.7, 9.0.2 and 9.1.1 in `knowledge/context/reviews/`; `v1.0.0` tag through CI |

RULE-019 notes: 8.18.7 Cloud Proxies can miss a new kind's jar (`remote-collector-upgrade-start-race.md` third
mode): confirm `plugins/inbound/vcfcf_vcommunity.jar` on each proxy before creating an instance there. 8.18 has
no unsigned-pak switch.

---

## 12. Open questions for the owner

Each with a recommendation; none blocks P0-P1.

| Q | Question | Recommendation |
|---|---|---|
| Q1 | A property whose source becomes unset while the read works (HA turned off, link down Duplex, Detailed Data gone) keeps its last value forever if we send nothing, so a view would show the old HA settings for a cluster with HA off. | On a set-to-unset transition seen in memory, push `""` once (DV-55); first sight of an unset field sends nothing. Honest blank beats a stale value. |
| Q2 | Keep these as readings, not failures: NIC Status `Disconnected` (the bundled alert needs it), EVC Enabled `False`, KPI 100 when every scored row is green, Consumption 100 at zero usable capacity, Collection Health `0` / `None in the last cycle`, resource-pool `0` for a cluster with no pools. | Keep all six. |
| Q3 | Disconnected hosts (issue 86): upstream stops publishing their Availability. | Publish Operational Availability for every host of the vCenter (DV-58); keep vim25 host properties skipped. |
| Q4 | World and Business Application keys: every pak instance computes and writes the same values (parity, last writer wins with equal values). | Keep parity for 1.0; measure the World cost in P7; add a freshness gate only if it is material. |
| Q5 | VM Template objects only exist upstream when the VMware adapter also models the template as a VM. | Create one for every vCenter template (DV-47). |
| Q6 | vCenter TLS default stays Trust on First Use (configuration parity), which sends credentials before any check. | Keep the default for 1.0 as decided; make Enabled the default in 1.1 once the accept dialog is proven on all three lines. |
| Q7 | RULE-011 for 52 ported dashboards. | One HTML mock per dashboard generated from the upstream definition, approved in batches by dashboard family in plan mode; the rule is met per dashboard, the review is batched. |
| Q8 | `vcfcf_vcommunity` / `VCF Content Factory vCommunity` were the retired port's identity. | Keep the names; recon confirms no instance registers the kind before the first install. |
| Q9 | Differential environment: e1 0.8.1 must run somewhere, and installing it as shipped overwrites 117 built-in views. | Collector-only build from the fork (content stripped) on one lab instance; never co-installed with the Java pak. |
| Q10 | Guest operations at scale: upstream allowed 1,800 s per cycle; a 5-minute cycle allows about 240 s. | Deadline-bound phase, 4 parallel guests, rotating cursor (DV-43). |
| Q11 | Windows and configuration events appear as DIAGNOSTIC events (troubleshooting timeline), not notifications. | Accept; NOTIFICATION is dropped by the platform. |

## 13. Live experiments needed (list only; nothing was probed for this design)

| # | Experiment |
|---|---|
| E1 | Identifiers and uniqueness flags of VMWARE Datastore, Datacenter and VMwareAdapter Instance on 8.18.7, 9.0.2, 9.1.1 (VCID present on each) |
| E2 | UI labels and units for upstream's keys today versus ours on VMWARE objects (map gap 1) |
| E3 | Numeric property push and a string sample into a numeric property history (R43) |
| E4 | POST read endpoints (`resources/stats/latest/query`, `resources/properties/latest/query`, `resources/stats/query`) under the ambient identity on 8.18.7 and on a Cloud Proxy; per-instance `net:<nic>|speed` returned (map gap 13) |
| E5 | Does the VMware adapter create VirtualMachine resources for templates (map gap 9) |
| E6 | PropertyCollector representation of an empty array versus an absent path |
| E7 | InvalidProperty fault names the path on vCenter 7, 8 and 9 |
| E8 | `summary.drsScore`, `mem:DRAM|memory_tier_total_capacity`, `mem:NVMe|*`, 20-second-peak keys present on 8.18 (map gaps 12, 14) |
| E9 | Resource pool levels: vim25 tree versus Ops PARENT relationships, VirtualApp handling |
| E10 | Pak uninstall effect on `content/files` SolutionConfig files and on keys pushed onto VMWARE objects |
| E11 | Two pak instances (two vCenters, or a duplicate account) writing vCenter and World keys (map gap 19) |
| E12 | Pushed timestamps returned by history reads (map gap 18) |
| E13 | PCI `vendorId` sign on the wire and upstream's published text (map gap 11) |
| E14 | License `expirationDate` time zone on the SOAP wire (map gap 10) |
| E15 | 9.1.1 FIPS collector: custom trust managers (TOFU, Pinned, guest) and SHA-1 digest |
| E16 | Cloud Proxy collector heap and reachability of vCenter 443 and ESXi 443 |
| E17 | The 19 rename-only built-in views exist with the same ids on all three lines |
| E-L1 | How often library items omit `cached` / `security_compliance` |
| G1-G9 | Section 8.7 |

## TOOLSET GAPS

| Id | Owner | Gap |
|---|---|---|
| T1 | tooling | `SuiteApiStitcher.post(path, jsonBody)` returning the body and throwing like `get` (non-2xx as `SuiteApiHttpException`), for the three query endpoints of E4. The facade has `get` only today. |
| T2 | tooling | `SuiteApiStitcher.pushEvents(events)` to `POST /api/events/bulk` (8.6). |
| T3 | tooling | numeric property values in `pushPropertiesBatch` (R43). |
| T4 | tooling | icon hints `content_library`, `library_item`, `vm_template` (2.3). |
| T5 | tooling | key differential CLI across two Ops instances (section 11). |

## Key Risks

1. **Guest operations may still return nothing on hardened guests** (policy or CLM). Mitigation: EncodedCommand,
   experiments G1-G3 before P5 is called done; the phase is off by default.
2. **Honest withholding versus stale properties** (Q1): without the transition marker, turned-off features show
   old values indefinitely.
3. **Labels and units cannot be declared** for 228 foreign keys; dashboards and views must carry their own
   labels and units (they do upstream too; E2).
4. **Heap on Cloud Proxies is unknown**; the VM bulk read with device lists and extraConfig is the largest
   holder. StAX and page size 50 are mandatory, not optimizations.
5. **Differential noise**: KPIs read Ops stats at slightly different moments on two instances. Tolerances and
   a 24-hour window are needed before calling a mismatch.
6. **Content volume** (52 dashboards, 189 views) waits on four in-flight tooling items and a stock-id guard; the
   collector can ship (P1-P5) ahead of content but a 1.0 release needs both.
7. **Migration hazard for users of upstream**: uninstalling upstream 0.8.1 deletes the 117 built-in views it
   shipped under stock ids. The installing guide must say so and give the recovery path before anyone swaps.
8. **Old kind registration** (Q8) can turn the first install into an upgrade of the retired port.

## Map and inventory insufficiencies found while designing

1. `kpi_tables.tsv` (the 49 limit rows) is cited by the map but lives only in session scratch, against RULE-015.
   The values are copied into Appendix A so this design stands alone; the file should be committed beside the
   map.
2. The content inventory, the 101 edited-built-in view ids, the 19 rename-only ids and the three additional ids
   (`dropped19.txt`, `extra3.txt`, `content_inventory.tsv`) also live only in session scratch; section 10 cannot
   be executed until they are committed.
3. The map's instance-field table lacks labels, display order, `port` being `required` with identType 2, and the
   `integer` type of the numeric fields; section 2.1 took them from upstream's generated definition.
4. D6 "Guest CPU Run Queue per vCPU": whether `guest|20_sec_peak_cpu_queue` is divided by the vCPU count is not
   stated.
5. Resource-pool "level" (R218-R219) is defined against Ops relationships only; the vim25 equivalent (root pool,
   VirtualApps) needs E9.
6. Per-row rendering of Python `str()` for floats and datetimes is given by example in the TSV; Appendix B fixes
   the rules, and the cartographer should confirm them against upstream's published values in the differential.
7. Collection interval is not stated in the map (the 10-minute staleness implies 5 minutes); 5 is assumed.

---

## Appendix A: KPI limits (facts from upstream `kpi_tables.tsv`, 49 rows)

Columns: kpi, sub_metric, unit, best, green, yellow, orange, zero_at, skip_when_green, published_by_pack.

| kpi | sub_metric | unit | best | green | yellow | orange | zero_at | skip | pub |
|---|---|---|---|---|---|---|---|---|---|
| Cluster Performance Score | Worst VM CPU Ready | % | 0 | 4 | 8 | 16 | 32 | F | T |
| Cluster Performance Score | Worst VM CPU Co-Stop | % | 0 | 2 | 4 | 8 | 16 | F | T |
| Cluster Performance Score | Worst VM Memory Latency | % | 0 | 1 | 2 | 4 | 8 | F | T |
| Cluster Performance Score | Worst VM Disk Latency | ms | 0 | 40 | 80 | 160 | 320 | F | T |
| Cluster Performance Score | 90th Percentile VM CPU Ready | % | 0 | 1 | 2 | 4 | 8 | F | T |
| Cluster Performance Score | 90th Percentile VM CPU Co-Stop | % | 0 | 0.5 | 1 | 2 | 4 | F | T |
| Cluster Performance Score | 90th Percentile VM Memory Latency | % | 0 | 0.5 | 1 | 2 | 4 | F | T |
| Cluster Performance Score | 90th Percentile VM Disk Latency | ms | 0 | 20 | 40 | 60 | 80 | F | T |
| Cluster Performance Score | Highest ESXi Bad Network Packets | % | 0 | 0 | 0.2 | 0.4 | 0.8 | T | T |
| Cluster Risk Score | Highest ESXi CPU Thread Utilization | % | 0 | 60 | 80 | 90 | 95 | T | T |
| Cluster Risk Score | Worst ESXi CPU Imbalance | none | 1 | 1 | 1.3 | 1.6 | 2 | F | T |
| Cluster Risk Score | Highest ESXi Memory Consumed | % | 0 | 80 | 90 | 95 | 100 | T | T |
| Cluster Risk Score | Worst ESXi Memory Ballooned | % | 0 | 1 | 2 | 4 | 8 | F | T |
| Cluster Risk Score | Worst ESXi Memory Zip Swap | % | 0 | 0.25 | 0.5 | 1 | 2 | F | T |
| Cluster Risk Score | Worst ESXi Memory Tiering Latency | µs | 0 | 150 | 300 | 450 | 600 | F | T |
| Cluster Risk Score | Highest ESXi CPU Reservation | % | 0 | 10 | 40 | 60 | 80 | T | T |
| Cluster Risk Score | Highest ESXi Memory Reservation | % | 0 | 10 | 40 | 60 | 80 | T | T |
| Cluster Risk Score | Highest ESXi CPU Overcommit Ratio | none | 0 | 1 | 2 | 3 | 4 | T | T |
| Cluster Risk Score | Highest ESXi Memory Overcommit Ratio | none | 0 | 1 | 1.4 | 1.8 | 2.2 | T | T |
| Cluster Risk Score | Highest CPU Monster VM to Host Ratio | none | 0 | 1 | 2 | 3 | 4 | F | T |
| Cluster Risk Score | Highest Memory Monster VM to Host Ratio | none | 0 | 1 | 2 | 3 | 4 | F | T |
| Cluster Consumption Score | Cluster-wide ESXi CPU Thread Utilization | % | 0 | 55 | 70 | 85 | 100 | F | T |
| Cluster Consumption Score | Cluster-wide ESXi Memory Consumed | % | 0 | 70 | 80 | 90 | 100 | F | T |
| Cluster Consumption Score | Cluster Memory Tiering Consumption | % | 0 | 4 | 8 | 16 | 32 | F | T |
| Cluster Consumption Score | Cluster-wide ESXi Memory Ballooned | % | 0 | 1 | 2 | 4 | 8 | F | T |
| Cluster Consumption Score | Cluster-wide ESXi Memory Zip Swap | % | 0 | 0.25 | 0.5 | 1 | 2 | F | T |
| ESXi Performance Score | Worst VM CPU Ready | % | 0 | 4 | 8 | 16 | 32 | F | T |
| ESXi Performance Score | Worst VM CPU Co-Stop | % | 0 | 2 | 4 | 8 | 16 | F | T |
| ESXi Performance Score | Worst VM Memory Latency | % | 0 | 1 | 2 | 4 | 8 | F | T |
| ESXi Performance Score | Worst VM Disk Latency | ms | 0 | 40 | 80 | 160 | 320 | F | T |
| ESXi Performance Score | 90th Percentile VM CPU Ready | % | 0 | 1 | 2 | 4 | 8 | F | T |
| ESXi Performance Score | 90th Percentile VM CPU Co-Stop | % | 0 | 0.5 | 1 | 2 | 4 | F | T |
| ESXi Performance Score | 90th Percentile VM Memory Latency | % | 0 | 0.5 | 1 | 2 | 4 | F | T |
| ESXi Performance Score | 90th Percentile VM Disk Latency | ms | 0 | 20 | 40 | 60 | 80 | F | T |
| ESXi Performance Score | ESXi Bad Network Packets | % | 0 | 0 | 0.2 | 0.4 | 0.8 | T | T |
| VM Performance Score | CPU Co-Stop | % | 0 | 1 | 2 | 4 | 8 | F | F |
| VM Performance Score | CPU Ready | % | 0 | 2 | 4 | 8 | 16 | F | F |
| VM Performance Score | CPU Overlap | % | 0 | 0.5 | 1 | 2 | 4 | T | F |
| VM Performance Score | Memory Contention | % | 0 | 0.5 | 1 | 2 | 4 | F | F |
| VM Performance Score | Disk Latency | ms | 0 | 10 | 20 | 40 | 80 | F | F |
| VM Performance Score | Network Dropped Tx | % | 0 | 0 | 0.5 | 1 | 2 | T | F |
| VM Performance Score | CPU Run | % | 0 | 95 | 97 | 99 | 100 | T | F |
| VM Performance Score | Memory Ballooned | % | 0 | 2 | 4 | 8 | 16 | F | F |
| VM Performance Score | Memory Zip Swap | % | 0 | 0.25 | 0.5 | 1 | 2 | F | T |
| Guest OS Performance Score | Guest CPU Run Queue per vCPU | none | 0 | 2 | 4 | 8 | 16 | F | F |
| Guest OS Performance Score | Guest Disk Queue | none | 0 | 20 | 40 | 80 | 160 | F | F |
| Guest OS Performance Score | Guest Free Memory | MB | 1024 | 512 | 256 | 128 | 0 | F | F |
| Guest OS Performance Score | Guest Page-Out Rate | none | 0 | 1000 | 2000 | 4000 | 8000 | F | F |

## Appendix B: Python value rendering (`PyText`) rules and vectors

| Source | Rule | Examples |
|---|---|---|
| boolean (`xsd:boolean`, JSON bool) | `True` / `False` | `true` to `True` |
| integer (`xsd:int/long/short`) | decimal, no `.0` | `30` to `30`; short `-31114` to `-31114` (PCI ids use DV-33 instead) |
| float (`xsd:double/float`) | Python `repr`: shortest round-trip digits; exponent form when the decimal exponent is below -4 or at least 16, as `1e-05`, `1.5e+16`; integral values keep `.0` | `2.0`, `0.1`, `1e-05`, `1.5e+16`, `123456789.0` |
| `xsd:dateTime` (`str(datetime)`) | `YYYY-MM-DD HH:MM:SS[.ffffff]+00:00` in UTC; fractional part as 6 digits when non-zero, omitted when zero | `2025-01-02T03:04:05.123Z` to `2025-01-02 03:04:05.123000+00:00`; `2025-01-02T03:04:05Z` to `2025-01-02 03:04:05+00:00` |
| Install Date (R1) | ISO form `YYYY-MM-DDTHH:MM:SS.ffffff+00:00` (`isoformat`, fraction omitted when zero) | `2025-01-02T03:04:05.123456+00:00` |
| enum | the wire text as is | `green`, `connected` |
| string | as is, trimmed only where the TSV says `strip` | |
| `round(x, 2)` | `PyRound.round2`, half-even on the exact binary value | `2.675` to `2.67` (binary below), `0.125` to `0.12` |
| list joins | `", ".join` in source order | `ds1, ds2` |

The author writes a test per row with these vectors; the differential (P2) confirms them against upstream's
published values and any mismatch becomes a map correction, not a guess.
