# audit-log.md — vcf-mp-cleanroom

Provenance log for every classification, observation, and decision
that informs the SPEC. Append-only; one line per event. Format per
CLAUDE.md:

```
- <filename> — <KEEP-C|ELIMINATE-A|ELIMINATE-B|UNKNOWN> — evidence: <one line> — YYYY-MM-DD
```

---

## 2026-05-15 — First triage pass

Corpus: marketplace `Downloads.zip` (extracted) + lab-admin's devel
pull (`from-devel/paks/`) + downloaded calibration reference
(`VCFOperationsvCommunity_0.2.8.pak`). Triage methodology: recurse
into outer pak's nested `adapter.zip`/`adapters.zip`/`<name>.zip`;
inspect inner manifest, describe.xml presence, jar inventory
(lib/ tree and inner-archive root); for SDK-on-classpath candidates,
peek at adapter jar's `META-INF/MANIFEST.MF` and entry list (package
paths only — NO bytecode decompile).

**Calibration anchors established this pass**:
- Track B (Integration SDK): `VCFOperationsvCommunity_0.2.8.pak`
  (downloaded 2026-05-15 from
  github.com/vmbro/VCF-Operations-vCommunity). Inner archive ships
  no jars; container image lives on external registry, pulled by
  Cloud Proxy.
- Track C sub-shape C1 (rich lib): `vim-902025137884.pak` (102 lib
  jars + vim.jar root).
- Track C sub-shape C2 (SDK-on-classpath): `SupervisorAdapter-902025137863.pak`
  (zero lib/, single 53-entry adapter jar at inner root with
  `com/vmware/vcops/adapter/utils/...` classes).

**Rule refinement landed in CLAUDE.md same date**: all paks use JSON
manifest (not a discriminator); legacy `mpb_adapter-*.jar`-in-lib
rule matched zero paks in corpus; outer-pak `*.py` are install hooks
(not Track signal); Track A and Track B are structurally
indistinguishable from pak content alone (zero-jar shape) — runtime
target is resolved by appliance via external metadata.

### Dedupe

- `vmware-mpforaggregator-9.0.0.0-24723247 (1).pak` — DELETED — evidence: SHA256 `a2aaf29d…6d4682` identical to non-suffixed sibling — 2026-05-15

### ELIMINATE-B (Track B, Integration SDK) — moved to `inputs/_excluded/integration-sdk/`

- `VCFOperationsvCommunity_0.2.8.pak` — ELIMINATE-B — evidence: confirmed Track B reference (Khriss research, line 194); inner archive ships zero jars; outer manifest `name=iSDK_VCFOperationsvCommunity` (template prefix) + placeholder `display_name`/`vendor`/`description`; downloaded as calibration anchor — 2026-05-15
- `application-insight-flopsar-vcfmp2026-0.6.1.pak` — ELIMINATE-B — evidence: inner `adapter.zip` ships zero jars (describe.xml + resources + images only); JSON manifest with placeholder fields; structural identity to vCommunity reference; vendor naming `Indevops*` — 2026-05-15
- `datacenter-insight-uptimedc-2026-0.1.0.pak` — ELIMINATE-B — evidence: zero-jar inner archive; structural shape matches vCommunity Track B reference; `name=UptimeDCAdapter` — 2026-05-15
- `indevopsbrocadeswitches_0.0.3.pak` — ELIMINATE-B — evidence: zero-jar inner archive; structural shape matches vCommunity Track B reference; vendor `Indevops` — 2026-05-15
- `ipam-insight-phpipam-vcfmp-2026.0.0.7.pak` — ELIMINATE-B — evidence: zero-jar inner archive; structural shape matches vCommunity Track B reference; `name=IndevopsPHPIPAM` — 2026-05-15
- `network-insight-checkpoint-vcf-2026-0.0.6.pak` — ELIMINATE-B — evidence: zero-jar inner archive; structural shape matches vCommunity Track B reference; `name=IndevopsCheckPointSmartConsole` — 2026-05-15
- `network-insight-cisco-prime-vcfmp-2026-0.0.7.pak` — ELIMINATE-B — evidence: zero-jar inner archive; structural shape matches vCommunity Track B reference; `name=IndevopsCiscoPrimeInfrastructure` — 2026-05-15
- `network-insight-juniper-vcfmp-2026.0.0.3.pak` — ELIMINATE-B — evidence: zero-jar inner archive; structural shape matches vCommunity Track B reference; `name=IndevopsJunosSpace` — 2026-05-15
- `scc-execution-adapter-vcf-2026.0.0.1.pak` — ELIMINATE-B — evidence: zero-jar inner archive; structural shape matches vCommunity Track B reference; `name=IndevopsScriptControlCenter` — 2026-05-15
- `stretched-cluster-insight-vcfmp-2026-0.0.2.1.pak` — ELIMINATE-B — evidence: zero-jar inner archive; structural shape matches vCommunity Track B reference; `name=IndevopsStretchPerformanceMonitoringServiceEdition` — 2026-05-15
- `tam-mpak_1.2.0.2_signed.pak` — ELIMINATE-B — evidence: zero-jar inner archive; structural shape matches vCommunity Track B reference; `name=TAMManagementPack` (TAM = Technology Alliance Management, third-party partner pack) — 2026-05-15
- `uptime-checker-vcfmp-2026-0.0.3.pak` — ELIMINATE-B — evidence: zero-jar inner archive; structural shape matches vCommunity Track B reference; `name=IndevopsUptimeKuma` — 2026-05-15

### KEEP-C (Track C, native Java adapter) — devel bundle

- `AppOSUCPAdapter-902025137916.pak` — KEEP-C — evidence: inner `AppOSUCP.zip` has 116 lib jars + `AppOSUCPAdapter3.jar` root (sub-shape C1) — 2026-05-15
- `CASAdapter-902025137900.pak` — KEEP-C — evidence: inner `CASAdapter.zip` has 14 lib jars + `CASAdapter.jar` root (sub-shape C1) — 2026-05-15
- `ConfigurationManagement-902025137888.pak` — KEEP-C — evidence: inner `VcfUnifiedConfigAdapter.zip` has 65 lib jars + `VcfUnifiedConfigAdapter.jar` root (sub-shape C1) — 2026-05-15
- `MPBAdapter-902025137890.pak` — KEEP-C — evidence: inner `MPBAdapter.zip` has 2 lib jars + `mpb-adapter.jar` root; **PRIORITY RE TARGET** — this is the MPB runtime engine that executes Track A declarative designs; dual-tier insight (Tier 1 + Tier 2) — 2026-05-15
- `ManagementPackforStorageAreaNetwork-902025137912.pak` — KEEP-C — evidence: inner `VSANStorage.zip` has 81 lib jars + `VirtualAndPhysicalSANAdapter3.jar` root (sub-shape C1) — 2026-05-15
- `NSXTAdapter-902025137922.pak` — KEEP-C — evidence: inner `NSXTAdapter.zip` has 13 lib jars + `NSXTAdapter3.jar` root (sub-shape C1) — 2026-05-15
- `NetworkInsightAdapter-902025137914.pak` — KEEP-C — evidence: inner `NetworkInsightAdapter.zip` has 35 lib jars + `NetworkInsightAdapter.jar` root (sub-shape C1) — 2026-05-15
- `PingAdapter-902025137875.pak` — KEEP-C — evidence: inner `PingAdapter.zip` has 2 lib jars + `PingAdapter.jar` root (thin C1) — 2026-05-15
- `ServiceDiscoveryAdapter-902025137923.pak` — KEEP-C — evidence: inner `ServiceDiscovery.zip` has 113 lib jars + `ServiceDiscoveryAdapter3.jar` root (sub-shape C1) — 2026-05-15
- `SupervisorAdapter-902025137863.pak` — KEEP-C — evidence: inner `SupervisorAdapter.zip` has zero lib/ + `SupervisorAdapter.jar` root (sub-shape C2 calibration); jar entries include `com/vmware/vcops/adapter/utils/{VCenterUtils,VropsSuiteApiUtils}.class` — 2026-05-15
- `VCFAutomation-902025137921.pak` — KEEP-C — evidence: inner `VCFAutomation.zip` has 38 lib jars + `automation_adapter.jar` root (sub-shape C1) — 2026-05-15
- `VCFDiagnostics-902025137871.pak` — KEEP-C — evidence: inner `DiagnosticsAdapter.zip` has 30 lib jars + `DiagnosticsAdapter3.jar` root (sub-shape C1) — 2026-05-15
- `VCFLogAssist-902025137895.pak` — KEEP-C — evidence: inner `LogAssistAdapter.zip` has 12 lib jars + `LogAssistAdapter.jar` root (sub-shape C1) — 2026-05-15
- `VMwareInfrastructureHealth-902025137903.pak` — KEEP-C — evidence: inner `VMwareInfrastructureHealthAdapter.zip` has 81 lib jars + `VMwareInfrastructureHealthAdapter.jar` root (sub-shape C1) — 2026-05-15
- `VMwarevSphere-902025137897.pak` — KEEP-C — evidence: inner `vSphereSolutionPak.zip` has 72 lib jars + `vmwarevi_adapter3.jar` root (sub-shape C1) — 2026-05-15
- `VrAdapter-902025137918.pak` — KEEP-C — evidence: inner `adapters.zip` has 86 lib jars + `VrAdapter.jar` root (sub-shape C1) — 2026-05-15
- `vcf-902025137906.pak` — KEEP-C — evidence: inner `VcfAdapter.zip` has 2 lib jars + `VcfAdapter.jar` root (thin C1) — 2026-05-15
- `vim-902025137884.pak` — KEEP-C — evidence: inner `vim.zip` has 102 lib jars + `vim.jar` root (sub-shape C1 calibration); **PRIORITY RE TARGET** — most complex Broadcom MP — 2026-05-15

### KEEP-C (Track C, native Java adapter) — marketplace bundle

- `DellStorageAdapter-01.04.0301_signed.pak` — KEEP-C — evidence: inner `adapters.zip` has 19 lib jars + `dellstorage_adapter.jar` root (sub-shape C1) — 2026-05-15
- `microsoftsqlserver_9.0.0.0100.24815089.pak` — KEEP-C — evidence: inner `adapters.zip` has 20 lib jars + `sql_server_adapter.jar` root (sub-shape C1) — 2026-05-15
- `mongodb_9.0.0.0.24730517.pak` — KEEP-C — evidence: inner `adapters.zip` has 18 lib jars + `mongodb_adapter3.jar` root (sub-shape C1); `*_adapter3.jar` naming is a packaging convention, not Track A signal — 2026-05-15
- `mysql_9.0.0.0.24730518.pak` — KEEP-C — evidence: inner `adapters.zip` has 21 lib jars + `mysql_adapter3.jar` root (sub-shape C1) — 2026-05-15
- `networkingdevices_9.0.0.0.24730519.pak` — KEEP-C — evidence: inner `adapters.zip` has 32 lib jars + `networkingdevices_adapter_3.jar` root (sub-shape C1) — 2026-05-15
- `openmanageenterpriseadapter-3.0.68.pak` — KEEP-C — evidence: inner `adapters.zip` has 24 lib jars + `OpenManageEnterpriseAdapter.jar` root (sub-shape C1) — 2026-05-15
- `oracledatabase_9.0.0.0100.25232927.pak` — KEEP-C — evidence: inner `adapters.zip` has 28 lib jars + `oracledatabase_adapter_3.jar` root (sub-shape C1) — 2026-05-15
- `postgresql_9.0.0.0.24730774.pak` — KEEP-C — evidence: inner `adapters.zip` has 12 lib jars + `postgres_adapter3.jar` root (sub-shape C1) — 2026-05-15
- `servicenow_9.0.0.0200.25226290.pak` — KEEP-C — evidence: inner `adapters.zip` has 38 lib jars + `servicenow_adapter3.jar` root (sub-shape C1) — 2026-05-15
- `srmAdapterPak-9.1.0.0.25256726.pak` — KEEP-C — evidence: inner `adapters.zip` has 103 lib jars + `SrmAdapter.jar` root (sub-shape C1) — 2026-05-15
- `vlcradapter-9.0.0.0-24650510.pak` — KEEP-C — evidence: inner `adapters.zip` has 38 lib jars + `VLCRAdapter.jar` root (sub-shape C1) — 2026-05-15
- `vmw-vcdaadapter-1.4.1-24443579.pak` — KEEP-C — evidence: inner `VcdaAdapter.zip` has 23 lib jars + `VcdaAdapter.jar` root (sub-shape C1) — 2026-05-15
- `vmware-awsadapter-9.0.0.0-24731845.pak` — KEEP-C — evidence: inner `AWSAdapter.zip` has 108 lib jars + `amazon_aws_adapter3.jar` root (sub-shape C1) — 2026-05-15
- `vmware-diagnostics-9.0.0.0001-24879623.pak` — KEEP-C — evidence: inner `DiagnosticsAdapter.zip` has 30 lib jars + `DiagnosticsAdapter3.jar` root (sub-shape C1) — 2026-05-15
- `vmware-hcxadapter-5.4.0-21441913.pak` — KEEP-C — evidence: inner `HCXAdapter.zip` has 26 lib jars + `hcx_adapter.jar` root (sub-shape C1) — 2026-05-15
- `vmware-mpforaggregator-9.0.0.0-24723247.pak` — KEEP-C — evidence: inner `Aggregator.zip` has zero lib/ + `federation_adapter3.jar` root (sub-shape C2); jar entries include `com/vmware/adapter/aggregator/AggregatorAdapter.class` — 2026-05-15
- `vmware-mpforkubernetes-2.2.2-25125643.pak` — KEEP-C — evidence: inner `KubernetesSolution.zip` has 35 lib jars + 3 root jars (`KubernetesAdapter3.jar`, `PKSAdapter.jar`, `TMCAdapter*.jar`); 6 .py files inside `KubernetesAdapter3/scripts/` are lifecycle hooks (postAdapters/preAdapters/validate pattern, same as outer-pak install hooks), not adapter source (sub-shape C1) — 2026-05-15
- `vmware-mpfornsxadvancedlb-1.3.4-25277573.pak` — KEEP-C — evidence: inner `NSXAdvancedLBAdapter.zip` has 5 lib jars + `nsx-alb.jar` root (thin C1) — 2026-05-15
- `vmware-mpforvro-9.0.0.0-24731678.pak` — KEEP-C — evidence: inner `vRealizeOrchestrator.zip` has 12 lib jars + `vRealizeOrchestratorAdapter3.jar` root (sub-shape C1) — 2026-05-15
- `vmware-vcfaviadapter-9.1.0.0-25407309.pak` — KEEP-C — evidence: inner `VcfAviAdapter.zip` has 45 lib jars + `AviAdapter.jar` root (sub-shape C1) — 2026-05-15
- `vmware-vcfhcxadapter-9.1.0.0-25345970.pak` — KEEP-C — evidence: inner `VcfHcxAdapter.zip` has 12 lib jars + `vcf_hcx.jar` root (sub-shape C1) — 2026-05-15

### Summary

- Total paks triaged: 52 (33 marketplace + 18 devel + 1 vCommunity calibration download)
- After dedupe: 51 unique paks
- KEEP-C: 39 (21 marketplace + 18 devel)
- ELIMINATE-B: 12 (11 marketplace Indevops/TAM + 1 vCommunity)
- ELIMINATE-A: 0 (legacy `mpb_adapter-*.jar`-in-lib rule matched no paks in this corpus; Track A and Track B were structurally indistinguishable, defaulted ambiguous shape to ELIMINATE-B per vCommunity calibration)

---

## 2026-05-15 — RE pass 1: mpb-adapter

Source: `inputs/from-devel/installed/mpb-adapter-installed.tar.gz`.
Method: extract installed deployment form; survey
`vrops-adapters-sdk-2.2.jar` public API with `javap -p`; survey
mpb-adapter entry-point classes; read `describe.xml`. NO bytecode
decompiled — signatures only.

### Pan-out / disprove ledger

- **CONFIRMED — mpb-adapter is a Track C native adapter that is the MPB runtime engine.** Entry-point class `com.vmware.adapter.mpb.MPBAdapter` extends `AdapterBase` and implements `ActionableAdapterInterface`. The runtime engine itself is `lib/mpb_adapter-9.0.1-patch-1.jar`. The MPB runtime loads design JSON at runtime (action parameter `builderJson`) and translates HTTP responses into the SDK's `MetricData` / `ResourceKey` / `Relationships` / `ExternalEvent` types.
- **CONFIRMED + REFINED — legacy `mpb_adapter-*.jar` rule.** Triage rule looked for it at outer-pak `lib/`. It actually exists at **inner-archive `mpb-adapter/lib/`** as a runtime dep of the MPBAdapter Track C pak. The jar exists; the triage rule was looking in the wrong place.
- **CONFIRMED — dual-tier insight is real.** mpb-adapter's action result models (`CollectedAdapter`, `CollectedData`, `CollectedEvent`, `CollectedIdentifier`, `CollectedRelationship`, `CollectedResource`, `CollectedResourceKind`, `DataModelAttribute`, `DataModelList`, `HttpResponseResult`) describe the **Tier 1 design semantic model** explicitly. VCF-CF's MPB design schema must target these types as the collection semantics.
- **PARTIALLY DISPROVEN — "Track C adapters need a vendor SDK in lib/."** mpb-adapter has 2 lib jars (the runtime + the Suite API client) and no vendor SDK. Vendor SDK presence is a property of the *target system*, not of Track C as a class.
- **NEW THEORY — `vcops-suiteapi-client-*.jar` is the "look across to other Operations data" SDK.** Hypothesis to test in pass 2: adapters that don't query Operations' own data omit this lib; vim probably has it.
- **NEW THEORY — MPB designs are JSON.** Parameter `builderJson` literally names the format. The `DataModel*` classes in mpb-adapter's action result package are likely the in-memory JSON model.
- **NEW THEORY — MPB primarily collects from HTTP.** `RunRequest` action's tunables (timeouts, retries, concurrency) and result types (`HttpResponseResult`, `HttpResponseHeader`) are HTTP-shaped. Designs likely express REST/SOAP/arbitrary-HTTP requests + response mapping rules.

### SPEC sections drafted (first cut)

- `spec/00-overview.md` — vocabulary, runtime model, section index
- `spec/01-adapter-lifecycle.md` — `AdapterInterface3` contract + `AdapterBase` template-method pattern + helper API + sub-shape variants
- `spec/02-describe-xml.md` — root structure, AdapterKind/ResourceKind skeleton, surfaces inventory (DRAFT — much expansion needed)
- `spec/03-credential-model.md` — credential kind + field structure + multi-slot pattern
- `spec/04-actions.md` — `ActionableAdapterInterface` + Action/Method declaration + async pattern

### Reference artifact

- `analysis/sdk-survey/v2.2-public-api.md` — SDK API surface inventory (workspace-internal; not part of SPEC). Source of authority for the SPEC.

### Open questions seeded for pass 2+

1. How the platform finds the adapter class (ServiceLoader / manifest header / convention?)
2. Concurrency model of `collect()` — `AdapterBase.locker` Semaphore suggests at-most-one
3. Adapter object lifecycle — reused or fresh-per-cycle?
4. Is `vcops-suiteapi-client-*.jar` in vim?
5. Full inventory of `adapter3.action.*` (22 classes) — what does the SDK provide vs. what does mpb-adapter add?
6. Full `ResourceKind` `type` enumeration (only `type="7"` adapter-instance observed)

### Files committed

`spec/00..04`, `analysis/sdk-survey/v2.2-public-api.md`,
`analysis/per-adapter/mpb-adapter.md`, updates to `audit-log.md`.
Decompiled tarball extracted to `analysis/decompiled/mpb-adapter/`
(gitignored).

---

## 2026-05-15 — RE pass 2: vim (VMWARE_INFRA_MANAGEMENT)

Source: `inputs/from-devel/installed/vim-installed.tar.gz`. Method:
extract installed deployment form; `javap -p` on entry-point class +
NMP task interfaces; read pom.xml (build metadata, not source);
survey describe.xml shape and lib/ inventory. NO bytecode decompiled
— signatures only.

### Pan-out / disprove ledger

- **CONFIRMED — pass-1 open question: adapter registration is via `adapter.properties`** at the entry-point jar's root. Two keys observed in both mpb-adapter and vim: `ENTRYCLASS` (fully-qualified Adapter class), `KINDKEY` (matches describe.xml AdapterKind). Pass-1 hypothesis resolved.
- **CONFIRMED — adapters can ship their own SDK version.** vim bundles `vrops-adapters-sdk-1.0.jar` in lib/; mpb-adapter does not (relies on platform classpath). Both work. SPEC § 01 now documents both strategies.
- **NEW + CONFIRMED — TWO task/action protocols co-exist**:
  - Legacy: `ActionableAdapterInterface` (Integrien lineage), declared in describe.xml `<Actions>`, poll-style async (`checkActionStatus`). mpb-adapter uses this.
  - Modern (NMP): `TaskHandler`/`AsyncTaskHandler` (`com.vmware.vrops.nmp.task.*` in `vcops-common-*.jar`), NOT declared in describe.xml, dispatched on TaskParam runtime type, callback-style async. vim uses this.
  SPEC § 04 rewritten as Protocol A + Protocol B.
- **NEW THEORY — declaration-heavy vs implementation-heavy adapter dichotomy.** vim is 102 lines of describe.xml + 792 classes + 102 lib jars (impl-heavy). MPB designs (Tier 1) are declaration-heavy. Track C adapters span the spectrum. Tier 2 generator should pick a target style.
- **PARTIALLY DISPROVEN — `vcops-suiteapi-client-*.jar` is "THE" Suite API client.** Two artifacts exist: `vcops-suiteapi-client-2.2-all.jar` (public, mpb-adapter) and `vcops-suiteapi-internal-client-1.0.jar` (internal, vim). First-party adapters use the internal client.
- **CONFIRMED — vim is the SDK-limits stress test** (CLAUDE.md priority hypothesis). 102 jars, 792 classes, both protocols, optional capability flag (`isResourceRenameAllowed`), bundled SDK, multiple obfuscated subsystems. If a feature exists in the platform, vim probably touches it.
- **NEW OBSERVATION — partial-obfuscation pattern.** Top-level adapter class + serialized data models stay clear; internal logic obfuscated to single-letter package/class names. Pattern consistent with Proguard/R8 selective rules.
- **NEW OBSERVATION — describe.xml schema is versioned**. vim uses `version="9"`; mpb-adapter uses `version="8"`. `isSingleton` attribute on ResourceKind, `hidden`/`readOnly` on ResourceIdentifier observed only on the v9 adapter. Suspect these are v9 additions; full schema diff deferred.

### SPEC updates

- `spec/01-adapter-lifecycle.md` — added `adapter.properties` section, SDK provisioning strategies, capability declaration flags
- `spec/02-describe-xml.md` — added `isSingleton`, `hidden`, `readOnly` attributes; schema version table
- `spec/04-actions.md` — restructured as "two co-existing protocols", added full Protocol B (NMP tasks) section
- `spec/00-overview.md` — updated section index + pass-coverage table

### Reference artifact

- `analysis/per-adapter/vim.md` — per-adapter analysis + ledger

### Open questions seeded for pass 3+

1. NMP task taxonomy — full inventory of `com.vmware.vrops.nmp.task.*` subdomains; extensibility (third-party-defined task types?)
2. `vcops-suiteapi-internal-client` vs `vcops-suiteapi-client` — what's the access-level difference?
3. `byte-buddy` in production lib — runtime bytecode for what?
4. Schema v8 → v9 full diff
5. Concurrency model of `collect()`
6. Adapter instance lifecycle (fresh per cycle vs reused)
7. Maven groupId `com.vmware.adapter.management` — published?

### Files committed

`spec/00..04` (updates), `analysis/per-adapter/vim.md`, `audit-log.md`
update. Tarball extracted to `analysis/decompiled/vim/` (gitignored).

---

## 2026-05-15 — RE pass 3: mongodb (third-party marketplace adapter)

Source: `inputs/from-marketplace/mongodb_9.0.0.0.24730517.pak` (no
installed tarball; extracted inner adapters.zip). Method:
`javap -p` on adapter class + abstraction framework interfaces;
inventory describe.xml elements; cross-reference SDK signatures.

### Pan-out / disprove ledger

- **CONFIRMED — `adapter.properties` registration generalizes to marketplace adapters**. Third independent corroboration (mpb-adapter Broadcom, vim Broadcom internal, mongodb third-party BlueMedora).
- **BIG FINDING — there exists a third-party adapter abstraction framework (`aria-ops-core-8.2.0.jar`) used by BlueMedora-derived marketplace adapters**. Provides `UnlicensedAdapter` (extends `AdapterBase`) + a clean SPI decomposition: `Tester` / `Discoverer` / `LiveCollector` / `HistoricalCollector`. The LiveCollector has **three separate methods**: `getCurrentMetrics`, `getEvents`, `getRelationships`. This is **prior art for VCF-CF's planned `vcfcf-adapter-base.jar`** — the pattern works and should be adopted directly. SPEC § 01 documents the framework.
- **PARTIALLY DISPROVEN — "all Track C adapters extend `AdapterBase` directly"**. mongodb extends `UnlicensedAdapter` (which extends `AdapterBase`). Generated VCF-CF adapters may follow either pattern; the framework approach is cleaner.
- **CONFIRMED — describe.xml's resource/metric model is hierarchical**. ResourceKind > ResourceGroup (nestable) > ResourceAttribute. Metric fully-qualified key = pipe-delimited path of group keys + attribute key. SPEC § 05 + § 06 document.
- **CONFIRMED — computed-metric expression language exists and uses `${selector}` syntax**. Example: `sum(${adapterkind=X, resourcekind=Y, metric=Z|W, depth=N})`. Pass-2 open question resolved. Full syntax TBD.
- **CONFIRMED — metric vs. property is the `isProperty` boolean**. The SDK's `addMetricData(..., boolean isProperty)` overload matches the describe.xml `<ResourceAttribute isProperty="true|false">` flag. Properties are versioned attributes; metrics are time-series.
- **NEW THEORY — `isRate="false"` means "already-derived rate" and `isRate="true"` means "cumulative counter"**. Observed: mongodb's `unit="perSec"` metrics are `isRate="false"` (adapter pushes per-second values directly). Inverse case not yet observed.
- **CONFIRMED + EXTENDED — CredentialField supports enum-typed dropdowns** with nested `<enum value="X" default="true|false">` elements. Pass-1 hypothesis confirmed via mongodb.
- **NEW — adapters can declare multiple CredentialKinds**. mongodb has `mongodb_credentials` (with auth) and `mongodb_no_credentials` (placeholder). User picks at config time.
- **NEW — describe.xml has at least 31 distinct element types** (per mongodb inventory): ResourceAttribute (513), State (226), SymptomDefinition (214), Condition (214), Unit (206), ComputedMetric (189), ResourceGroup (110), UnitType (75), Recommendation (23), ResourcePath (17), ApplicableResourceContainer (14), etc. Most not yet documented in SPEC.
- **NEW THEORY — third-party marketplace adapters likely share `aria-ops-core`**. Other DB adapters (mysql / postgres / oracle / mssqlserver) all share `*_adapter3.jar` naming pattern. Pass 4 should cross-validate by spot-checking one.

### SPEC updates

- `spec/00-overview.md` — section index + coverage table extended
- `spec/01-adapter-lifecycle.md` — added "Adapter abstraction frameworks" section documenting `UnlicensedAdapter` + Tester/Discoverer/LiveCollector/HistoricalCollector SPI
- `spec/03-credential-model.md` — enum/dropdown CredentialField pattern; multiple CredentialKinds per adapter
- `spec/05-resource-model.md` (NEW) — ResourceKind / ResourceIdentifier / ResourceGroup (nestable) / ResourceAttribute, runtime ResourceKey
- `spec/06-metrics-units-expressions.md` (NEW) — metric keys, isRate/isProperty, computed-metric expression language, Unit / UnitType

### Reference artifact

- `analysis/per-adapter/mongodb.md`

### Open questions seeded for pass 4+

1. Verify `aria-ops-core` generalizes to another marketplace DB adapter (mysql, postgres, oracle, mssqlserver)
2. Confirm `isRate="true"` cumulative-counter hypothesis
3. Full `<RollUpType>` enum
4. Full set of expression-language aggregation functions
5. Symptom-condition expression syntax (214 in mongodb!)
6. `<Unit>` + `<UnitType>` schema + canonical unit catalog
7. `<ResourcePath>` + `<TraversalSpec>` relationship-model schemas
8. `<State>` element semantics for stateful attributes
9. Capacity-model elements (CapacityDefinition, ResourceContainer, WorkloadSettings, etc.)
10. `<AlertDefinition>` + `<Recommendation>` + `<SymptomSet>` shapes

### Files committed

`spec/00,01,03` (updates), `spec/05-resource-model.md` (NEW),
`spec/06-metrics-units-expressions.md` (NEW),
`analysis/per-adapter/mongodb.md`, `audit-log.md` update. Inner
adapters.zip extracted to `analysis/decompiled/mongodb/` (gitignored).

---

## 2026-05-15 — RE pass 4: vmwarevi_adapter3 (vSphere — KINDKEY=VMWARE)

Source: `inputs/from-devel/installed/vmwarevi_adapter3-installed.tar.gz`.
Method: extract installed form; `javap -p` on entry class + cross-MP
helper classes; survey describe.xml structure (5 TraversalSpecs, 24
ResourcePaths, 25 ResourceKinds, 3688 attributes). Combined with
mongodb's `ExUnoUtils$ExternalRelationship` from pass 3 to answer
Scott's cross-MP attachment question.

### Pan-out / disprove ledger

- **CONFIRMED — cross-MP attachment mechanism: ResourceKey identity matching, no special API**. An adapter constructs a `ResourceKey(adapterKind=foreign, resourceKind=foreign, identifiers=matching)` and pushes via `addMetricData` to a `ResourceConfig` keyed on it. The platform de-duplicates by identity, attaching the data to the existing resource record owned by the foreign adapter. There is NO `ExternalResource` class in the SDK; cross-MP is emergent from the identity model.
- **CONFIRMED — TraversalSpec/ResourcePath syntax supports cross-MP edges**. Path expressions like `VMWARE::Datastore::child||STORAGE_DEVICES::Mount::child` reference foreign adapter kinds directly. The `||` separator is for levels; `::` separates within a level; `::child` is forward edge, `::~child` is inverse edge; `/recursive` and `/preferred` are modifiers.
- **CONFIRMED — VirtualMachine identifier shape documented**. The cross-MP attachment contract for vSphere VMs: `(VMEntityName, VMEntityObjectID, VMEntityVCID, VMEntityInstanceUUID)`. The latter two are optional but useful for cross-vCenter identity.
- **CONFIRMED — BlueMedora's `ExternalRelationship` is a proven join-pattern** for matching foreign resources by IP/name. The struct holds local + foreign keys + match metrics. mongodb uses it specifically to pair MongoDB resources with vSphere VMs (`isVMRelationship` flag) and EpOps-monitored OS instances.
- **NEW — three additional vSphere-specific SDK interfaces** observed in VMwareAdapter: `VcCommunication`, `VcManagement` (in `com.integrien.alive.common.adapter3`), `CompatibilityChecker` (in `.compatibility`). Pattern: per-adapter-kind extra contracts the platform or other adapters can query for.
- **BIG FINDING — `vcf-ops-data-sdk-1.0-SNAPSHOT.jar` is a parallel modern SDK**, Broadcom-namespaced (`com.broadcom.ops.data.*`), with stream/subscriber/observer architecture and vCenter integration. Distinct from legacy `com.integrien.alive.common.adapter3.*`. Likely the future direction. Worth a dedicated pass before VCF-CF freezes its abstraction layer.
- **NEW — the legacy adapter SDK has at least two evolutionary successors**: NMP tasks (pass 2) AND `vcf-ops-data-sdk` (this pass). Both Broadcom-namespaced. VMware is migrating; we should track.
- **CONFIRMED — vSphere has the largest action surface** in the corpus. 11 action subpackages (modifydrsconfig, movevm, rebalance, reconfigurevm.{allocationconfig, cpumemoryvalue}, removesnapshot, scripts.{dispatch, guestoperation.impl}, states, etc.). Production reference for legacy actions.
- **NEW THEORY — declaration-vs-implementation axis goes both ways**. vSphere has BOTH a heavy describe.xml (13,279 lines / 3688 attrs / 25 kinds) AND a heavy implementation (455 classes + 72 libs). Some adapters are heavy on both axes; the dichotomy in pass 2 was overstated.

### SPEC updates

- `spec/07-relationships-cross-mp.md` (NEW) — TraversalSpec/ResourcePath syntax, cross-MP attachment recipe, identifier shape for `VMWARE::VirtualMachine`
- `spec/00-overview.md` — section + coverage table updated

### Reference artifact

- `analysis/per-adapter/vmwarevi_adapter3.md` — full per-adapter analysis + ledger

### Question answered

> "find out how to append/stitch metrics and properties onto a VM from a different MP"

Documented in `spec/07-relationships-cross-mp.md`. Summary: construct a `ResourceKey(adapterKind="VMWARE", resourceKind="VirtualMachine", ...)` with matching identifier values, push via `addMetricData`. The hard part is computing the matching identifiers (typically by IP + hostname → vCenter lookup); BlueMedora's `ExternalRelationship` struct is a proven pattern for this.

### Open questions seeded for pass 5+

1. How to synthesize a `ResourceConfig` for a foreign `ResourceKey` (the `getMonitoringResource()` path only returns this adapter's resources — the platform-side lookup mechanism isn't yet documented)
2. Orphan behavior when foreign ResourceKey doesn't yet exist on platform
3. Full `vcf-ops-data-sdk` API characterization (HIGH priority — may inform VCF-CF abstraction layer)
4. `VcCommunication` / `VcManagement` interface signatures
5. `<PowerState>` / `<Icon>` / `<Condition>` / `<Case>` element schemas (rich evidence in vSphere)
6. `<CapacityModel>` / `<CapacityDefinition>` schema (vSphere references `CapacityModel-VM`)
7. Identifier shapes for HostSystem, Datastore, NSX kinds (next-priority foreign-attachment targets — pass 5 NSX will cover NSX)

### Files committed

`spec/00,07`, `analysis/per-adapter/vmwarevi_adapter3.md`, `audit-log.md`. Decompiled tarball at `analysis/decompiled/vmwarevi_adapter3/` (gitignored).

---

## 2026-05-15 — RE pass 5: NSXTAdapter3

Source: `inputs/from-devel/installed/NSXTAdapter3-installed.tar.gz`.
Method: `javap -p` on entry class; describe.xml structural survey (41
kinds, 848 attrs, 0 TraversalSpec/ResourcePath, 5 CredentialKinds).

### Pan-out / disprove ledger

- **NEW — declarative vs runtime-pushed topology is a real axis**. NSX has 41 ResourceKinds and ZERO TraversalSpec/ResourcePath declarations. Topology is built entirely at runtime via the SDK's `Relationships` API. Contrast with vSphere (5 TraversalSpecKinds, 24 ResourcePaths). Both patterns coexist in production. SPEC § 07 updated with two-mode taxonomy.
- **CONFIRMED — adapter-instance lifecycle is reuse-the-instance**. NSX caches heavy state across `collect()` calls (per-resource statistics maps, last-collection timestamps). Pass-1 open question resolved.
- **NEW — internal SuiteAPI client variants**: `vcops-suiteapi-internal-client` exists in versions 1.0 (vim) and 2.2 (NSX). Both are first-party-only.
- **NEW — `vrops-adapters-sdk.jar` (no version in filename)** as a third SDK-pinning style observed (alongside version-suffixed in vim and platform-classpath in mpb-adapter).
- **NEW — `ComputeManager` tracking is the NSX→vSphere bridge**. NSX adapter has `getComputeManagerMap()` returning the vCenter instances NSX manages. Provides runtime data to push cross-MP relationships from NSX TransportNodes to vSphere HostSystems.

SPEC § 07 updated with the two-mode topology section.

### Files committed

`spec/00,07` updates, `analysis/per-adapter/NSXTAdapter3.md`, audit-log.

---

## 2026-05-15 — RE pass 6: VCFAutomation

Source: extracted from `inputs/from-devel/paks/VCFAutomation-902025137921.pak`. No installed tarball.

### Pan-out / disprove ledger

- **CONFIRMED — declarative cross-MP topology is the dominant pattern when adapters aggregate views**. VCFAutomation has 9 ResourcePaths and **EVERY** one references foreign adapter kinds (VMWARE + SupervisorAdapter). The vSphere case in pass 4 was the light version; aggregator adapters like Automation are the heavy version.
- **NEW BIG FINDING — `com.vmware.ops.api.model.resource.ResourceDto` is the foreign-resource bridge type** at the platform's API layer. VCFAutomation builds runtime lookup maps from its own UUIDs to `ResourceDto` instances for foreign vSphere/NSXT resources. **This is the runtime API for cross-MP resource references** that was an open question from pass 4. SPEC § 07 updated.
- **NEW — three identity models in the Operations API ecosystem now visible**:
  - Legacy: `ResourceKey` + `ResourceConfig` (`com.integrien.alive.common.adapter3`)
  - Mid-layer: `ResourceDto` (`com.vmware.ops.api.model.resource`)
  - Modern data SDK: `ResourceIds` (`com.broadcom.ops.data.model`, from pass 4)
- **NEW — explicit relationship-cache pattern** observed: `Map<ResourceKey, Collection<ResourceKey>> getLastRelationships()`. Adapter remembers its previous relationship set so it can push deltas / detect changes.
- **NEW — concurrent collector pattern**: two parallel ExecutorService task queues (metric collector + relationship collector). VCFAutomation has substantial concurrency machinery for a small adapter — suggests aggregator workload is I/O-bound.
- **CONFIRMED — "aggregator adapter" is a valid Track C archetype**. Small Java footprint, no resources of its own to deeply instrument, mostly busy declaring relationships across other MPs' resources.

### Files committed

`spec/07` update, `analysis/per-adapter/VCFAutomation.md`, audit-log.

---

## 2026-05-15 — Bulk survey (all remaining KEEP-C paks)

Programmatic survey of all 38 remaining KEEP-C paks (15 devel, 1 already from VCFAutomation, 22 marketplace). Method: extract inner adapters.zip, read adapter.properties + describe.xml stats. Captured in `analysis/per-adapter/_bulk-survey-2026-05-15.md`.

### Headline findings

- **14 paks declaratively reference `VMWARE::VirtualMachine`** — the most-cross-referenced foreign kind in the corpus. Confirms vSphere VM is THE canonical cross-MP attachment target.
- **`com.bluemedora.vrealize.adapter.*` is the dominant marketplace framework**: mongodb, mysql, postgresql, oracle, networkingdevices, microsoftsqlserver, servicenow. All atop `aria-ops-core` (pass 3 finding).
- **AppOSUCPAdapter3 has 139 ResourceKinds** — most in the corpus — and runtime-pushes topology (0 TraversalSpec). Modern replacement for EpOps. Per-application kind families (e.g., `activedirectory_*`, `apache_*`, etc.).
- **vmware-awsadapter has 118 kinds, 282 ResourcePaths** — most declarative-topology adapter in the corpus.
- **Duplicate paks for same KINDKEY** observed: `VirtualAndPhysicalSANAdapter` + `ManagementPackforStorageAreaNetwork`, and `VCF_UNIFIED_CONFIG` + `ConfigurationManagement`. Different distribution channels for the same adapter kind.
- **Empty-stub adapters are common**: register a KINDKEY in describe.xml without declaring metric attrs. Either rely on runtime-pushed dynamic metrics or reference foreign kinds only.
- **Three platform-internal adapters**: `vcops_adapter3` (self-monitoring), `FederatedAdapter` (cross-Operations federation), `vim` (VCF integration).
- **EpOps OS kinds still referenced**: `Linux`, `AIX`, `HPUX`, `Solaris`, `HostSystem` — by mysql and postgresql adapters. EpOps not present in corpus but its kind names are still authoritative.

### Files committed

`analysis/per-adapter/_bulk-survey-2026-05-15.md`, audit-log update.

---

## 2026-05-15 — MPB pak insights deep-dive (Scott's specific ask)

Source: `analysis/decompiled/mpb-adapter/mpb-adapter/lib/mpb_adapter-9.0.1-patch-1.jar` — the MPB runtime engine, 15,440 classes.

### Pan-out / disprove ledger

- **BIG FINDING — MPB runtime contains a complete code-generation subsystem**: `com.vmware.mpb.generation.*`. Generates `adapter.properties` (`AdapterProperties` class implements `IWritableFile`), dashboard JSON (`dashboards/DashboardJson` builder pattern), and almost certainly describe.xml. **VCF-CF Tier 1 can REUSE this rather than reinventing**.
- **CONFIRMED — MPB runtime uses aria-ops-core internally**. The runtime `com.vmware.mpb.MPBAdapter` has `getLiveDataCollector` — the same SPI as mongodb/BlueMedora adapters. MPB IS an aria-ops-core adapter with the design JSON as its runtime implementation.
- **CONFIRMED — MPB runtime is Kotlin** (.kt source files, `kotlin.jvm.functions.Function1` types, suspend coroutine patterns).
- **NEW — cross-MP attachment in MPB is named explicitly**: `com.vmware.mpb.impl.collect.http.HttpExternalResourcePropertyAdder`. The runtime has a dedicated class for pushing properties to foreign resources. Built-in capability.
- **NEW — HTTP-chained requests are first-class**: `HttpChainedRequestUtils` supports list-then-detail patterns with parameter substitution from prior response. Async fan-out via `asyncFlatMap` / `asyncMap`.
- **NEW — MPB design DSL is bounded by**:
  - `BuilderConfigParam.DataType` enum: STRING, INTEGER, SINGLE_SELECTION (no BOOLEAN visible; presumably handled via SINGLE_SELECTION enums)
  - `BuilderFunction` enum: BASE64, NONE observed (full set TBD)
- **NEW — hierarchical data extraction**: `DataModelList.parentListId` supports nested data trees (cluster → replica set → member, etc.)
- **NEW — MPB design designers see `example` values**: `DataModelAttribute.example` is the sample value displayed in the design preview UI
- **NEW — validation engine ships with the runtime**: `com.vmware.mpb.impl.validation.BuilderFileValidation`. VCF-CF should gate generated designs through it.

### Recommended VCF-CF architecture (in mpb-adapter-insights-for-vcf-cf.md)

Tier 1 strongest path: VCF-CF emits a `BuilderFile` (MPB's in-memory design representation), then delegates emission of adapter.properties / dashboards / (likely) describe.xml to the MPB runtime's existing `generation` subsystem.

Tier 1→Tier 2 promotion triggers (when MPB can't express the use case):
- Non-HTTP collection protocol
- Stateful collection (persistent connections / subscriptions)
- User-invokable actions required
- Complex foreign-resource matching beyond simple identifier joining

### Files committed

`analysis/per-adapter/mpb-adapter-insights-for-vcf-cf.md`, audit-log update.

---

## 2026-05-15 — Final summary written

`spec/99-summary-and-vcf-cf-recommendations.md`. Consolidates findings across all passes; identifies high-confidence vs sketched vs not-started areas; produces 7 Tier 2 recommendations and 4 Tier 1 recommendations for VCF-CF.

Highest-leverage finding to follow up: verify MPB runtime's generation subsystem emits describe.xml (currently inferred); if confirmed, Tier 1 implementation cost drops dramatically because VCF-CF can target the existing in-memory `BuilderFile` model class.

Final coverage:
- 51 unique paks triaged
- 7 deep-analyzed adapters (mpb-adapter, vim, mongodb, vSphere, NSXTAdapter, VCFAutomation, AppOSUCP light)
- 32 bulk-surveyed
- 1 Track B spot-check (Indevops Brocade)
- 1 SDK survey, 1 MPB runtime survey
- 8 SPEC sections (00-07) + final summary (99)
- 11 local commits, full theory pan-out/disprove ledger preserved

Self-assessment:
- Tier 2 (native adapter) SPEC: ~50% complete
- Tier 1 (MPB design) recommendations: ~70% complete (the "reuse mpb-generation" insight reshapes the problem)


---

## 2026-05-16 — RE pass 7: MPB BuilderFile schema + describe.xml emission CONFIRMED

Source: `analysis/decompiled/mpb-adapter/mpb-adapter/lib/mpb_adapter-9.0.1-patch-1.jar` (extracted to `/tmp/mpb-pass7` for javap). Method: package enumeration via `unzip -l`, `javap -p` on key classes (`BuilderFile`, `BuilderPakSettings`, `IBuilderSource`, `HttpBuilderSource`, `DescribeXml`, `DescribeAdapterKind`, `DescribeAlertDefinition`, `DescribeSymptomDefinition`, `DescribeSymptomStateCondition`, `BuilderFunction`, `BuilderConfigParam$DataType`, `BuilderHttpAuthentication$AuthenticationType`, all 6 `IWritableFile` implementations).

### Pan-out / disprove ledger

- **🎯 CONFIRMED (was the #1 open question) — `com.vmware.mpb.generation.describe.DescribeXml` exists and emits describe.xml from a BuilderFile.** Constructor signature: `DescribeXml(BuilderFile, DescribeResourcesProperties) : IWritableFile`. Has built-in `validateSchema()`. The describe element tree is mirrored class-for-class as 24 `Describe*` components under `com.vmware.mpb.generation.describe.components`. SPEC § 02 expanded with the full in-memory-model mapping.
- **CONFIRMED — full deployable artifact set is generated from a single BuilderFile.** Exactly 6 `IWritableFile` implementations exist: `DescribeXml`, `DescribeResourcesProperties`, `AdapterProperties`, `Manifest`, `PakResourcesProperties`, `Version`. Plus `DashboardJson.File` for dashboards. All take BuilderFile as sole input. **A BuilderFile fully determines a deployable pak** (modulo binary icon).
- **NEW — full BuilderFile schema enumerated**: 6 top-level fields (`id`, `name`, `pakSettings: BuilderPakSettings`, `source: IBuilderSource`, `constants: List<BuilderConstant>`, `relationships: List<BuilderRelationship>`). Relationships are top-level (not nested under source); designs can declare cross-source relationships.
- **NEW — `IBuilderSource.Type` enum has exactly ONE value: HTTP.** MPB v1 is HTTP-only at the source level. Non-HTTP collection is a definitive Tier 1→Tier 2 promotion trigger; no exceptions in v1.
- **CONFIRMED — `BuilderFunction` enum is exactly {BASE64, NONE}.** No URL encode/decode, regex, JSONPath, XPath at the value-transform layer. (Some logic may live in `BuilderQuery*` for response parsing — TBD.)
- **CONFIRMED — `BuilderConfigParam.DataType` enum is exactly {STRING, INTEGER, SINGLE_SELECTION}.** No BOOLEAN type. Tier 1 designs needing booleans must use single-selection enums.
- **CONFIRMED — `BuilderHttpAuthentication.AuthenticationType` is exactly {SESSION_TOKEN, BASIC, CUSTOM}.** No first-class OAuth2 / Kerberos / mTLS / token refresh; CUSTOM is the escape hatch.
- **NEW — alert framework via MPB is event-driven ONLY.** `DescribeSymptomStateCondition` has a single field: `eventMsg: String`. MPB-generated symptoms fire on event matches, not metric thresholds. Compare mongodb's 214 metric-threshold symptoms (those bypass the MPB emission path — direct describe.xml authoring). Tier 1 designs needing metric thresholds must promote to Tier 2.
- **NEW — `DescribeAlertDefinition.state` is singular (one DescribeAlertState).** The schema permits multiple states; MPB emits one. Multi-state alerts force Tier 2 promotion.
- **NEW — DescribeAdapterKind's child-list IS the Tier 1 describe-surface bound**: adapterInstance + credentialKinds + resourceKinds + tagKinds + discoveries + symptoms + alerts + recommendations + traversalSpecs + unitTypes. **Notable absences** that force Tier 2: `<ProblemDefinitions>`, `<CapacityDefinitions>`, `<Policies>`, `<CustomGroupMetrics>`, `<LicenseConfig>`, `<HAConfig>`, `<Actions>`/`<Methods>`.
- **NEW — XSD validation is built-in and callable** (`DescribeXml.validateSchema()`, using shaded `com.sun.msv`). VCF-CF should use it as the final gate before pak emission — same check the appliance runs at install.
- **NEW — BuilderFile is Jackson-serializable** (`BuilderFileDeserializer` present, `BuilderFile.toJsonString()` is public). The Kotlin object and the JSON wire format are 1:1.

### Architectural impact

Tier 1 (MPB design generation) implementation cost drops significantly. Concrete two-path architecture documented in `analysis/per-adapter/mpb-adapter-insights-for-vcf-cf.md § Revised Tier 1 architecture (post-Pass 7)`. Promotion-to-Tier-2 triggers are now objectively testable (full list in `spec/99 § Tier 1 promotion-to-Tier-2 triggers — now empirically bounded`).

### Files committed

`spec/02-describe-xml.md` (new MPB-runtime emission-pipeline section); `spec/99-summary-and-vcf-cf-recommendations.md` (Pass 7 update — Tier 1 de-risk + bounded promotion triggers); `analysis/per-adapter/mpb-adapter-insights-for-vcf-cf.md` (Pass 7 update appended); audit-log.

---

## 2026-05-16 — RE pass 8: Alert framework grammar enumerated

Source: `analysis/decompiled/mongodb/mongodb_adapter3/conf/describe.xml` (214 symptoms, 12 alerts — light variety) cross-referenced with `analysis/decompiled/vmwarevi_adapter3/vmwarevi_adapter3/conf/describe.xml` (517 symptoms, 119 alerts — full variety incl. fault/msg_event/htmetric/dtmetric/property conditions and compound SymptomSets).

### Pan-out / disprove ledger

- **NEW — `<Condition>` has 6 type values**, each with its own attribute shape:
  - `metric` — static threshold OR dynamic-via-reference (`targetKey` + `thresholdType="metric|property"`)
  - `dtmetric` — platform-computed dynamic baseline (`operator="above|below"`, no value)
  - `htmetric` — hard-threshold capacity metric (e.g., `timeRemaining <= 30`)
  - `property` — string/numeric property comparison
  - `msg_event` — event message match with `eventMsg` (supports `regex` operator) + `eventType` / `eventSubType` int codes
  - `fault` — fault event match via `faultevent` (canonical class name)
- **NEW — `thresholdType` is a first-class attribute** on `metric` conditions: `static` (288 cases vSphere), `metric` (3 cases — compare to another metric), `property` (6 cases — compare to a property). **Dynamic-threshold-by-reference** is supported in the schema; this was not visible from mongodb alone.
- **NEW — operator vocabulary is rich**: `=`, `!=`, `<`, `<=`, `>`, `>=` (comparison); `above`, `below` (dt/ht-metric); `contains`, `equals`, `regex` (string); `and`, `or` (boolean, at SymptomSet level only).
- **NEW — severity values are 5**: `Info`, `Warning`, `Immediate`, `Critical`, `Automatic`. Case-insensitive on the wire (both `Critical` and `critical` observed); should emit canonical case.
- **CONFIRMED — `<State>` is singular per AlertDefinition**. Zero AlertDefinitions across 631 inspected have multiple State children. Authors emit multiple AlertDefinitions with different ids for severity ladders. Matches the MPB-runtime observation from Pass 7 (DescribeAlertDefinition.state is singular).
- **NEW — compound symptom logic via `<SymptomSets operator="and|or">`** wrapping multiple `<SymptomSet>` children. Two-level boolean tree, with each `<SymptomSet>` independently scoped by `applyOn` and combined by its own `operator`. 16 cases in vSphere.
- **NEW — `<SymptomSet>.applyOn`** is the relationship-traversal-aware part of the alert framework: `self` (126 cases vSphere), `child` (10), `descendant` (5). Enables alerts that fire based on conditions in related resources.
- **NEW — `<SymptomSet>.aggregation`** values: `any` (default) and `percent` (14 cases vSphere — threshold attribute not yet identified, follow-up needed).
- **NEW — `<AlertDefinition>.type` and `.subType` are int codes** owned by the platform (not in describe.xml). Observed type values: 15, 16, 20. SubType values: 6, 18, 19, 20, 21, 22, 28, 29. Map to platform alert categories (Performance / Configuration / Availability / etc.); full table not in describe.xml.
- **NEW — `<AlertDefinition>` policy controls**: `allowMultipleAlertsPerResource` (bool), `disableInBasePolicy` (bool — register but disabled by default; admin enables via policy).
- **NEW — `<Impact>`**: `type="badge"` always observed; `key` ∈ {`health`, `risk`, `efficiency`} (the standard Aria Operations 3-badge model). Drives badge contribution.
- **NEW — Top-level `<Recommendations>` is a shared catalog** keyed by string; alerts reference entries via `<Recommendation ref=… priority=N/>`. Dedup is by `key`. vSphere has 23 entries, mongodb 12.
- **NEW — Adapters NEVER programmatically raise alerts**. The entire alert framework is declarative: adapters push metrics/properties/events; the platform evaluates the declared symptoms and emits alerts. **This means VCF-CF can fully generate alert frameworks at SPEC time — no per-adapter alert code needed beyond data emission.**
- **CONFIRMED + EXTENDED — Tier 1 → Tier 2 promotion triggers from the alert axis**: metric-threshold, property-comparison, threshold-by-reference, htmetric, fault, compound boolean, relationship-scoped (`applyOn=child|descendant`), per-instance (`instanced="true"`) — any of these forces Tier 2 promotion.
- **Bonus finding — `<ApplicableResourceContainer>`** is part of the CAPACITY model, not alerts. Observed in mongodb wrapped in `<StressedSettings>`, `<UsableCapacitySettings>`, `<WorkloadSettings>`, `<CapacityTimeRemainingSettings>`, `<ReclaimableCapacitySettings>`, `<WasteSettings>`, `<IdleSettings>`, `<PoweredOffSettings>`, `<UnUsedSettings>`. Noted for future capacity-pass.

### Files committed

`spec/08-alerts-symptoms-recommendations.md` (new); `spec/00-overview.md` (index updated); audit-log.

---

## 2026-05-16 — RE pass 9: vcf-ops-data-sdk characterized (modern stream SDK)

Source: `analysis/decompiled/vmwarevi_adapter3/vmwarevi_adapter3/lib/vcf-ops-data-sdk-1.0-SNAPSHOT.jar` — the only production jar in the corpus that bundles `com.broadcom.ops.data.*`. Method: package enumeration + `javap -p` on entry-point classes and key types. Full analysis in `analysis/per-adapter/vcf-ops-data-sdk.md`.

### Pan-out / disprove ledger

- **DISPROVEN (was a Pass 6 worry) — "the modern com.broadcom.ops.data SDK is the successor that VCF-CF must target".** Evidence: shipped in 1 of 39 KEEP-C paks (vSphere only), stuck at 1.0-SNAPSHOT since April 2022 (4 years stale), uses legacy `Logger` everywhere, pushes results through legacy `addMetricData` at the end of the pipeline. **It's a middleware sidecar, not a successor.** This eliminates the Pass 6 risk "building atop the legacy SDK just as VMware completes a migration" — the migration is not underway.
- **CONFIRMED — `vcf-ops-data-sdk` is a Reactive-Streams subscriber for vCenter PerformanceManager stats streams.** Architecture: adapter calls `client.startCollection(specName, interval)` → SDK creates a query against vCenter stats-provider, opens a stream via `org.reactivestreams.Publisher<Result>` → `StatsSubscriber.onNext(Result)` consumes → `MetricDataStoreManager` buffers → adapter drains via `client.getStatsData()` → pushes via legacy SDK.
- **NEW — `Routes` enum exposes a 3-destination multi-fan-out**: `ops` (legacy SDK → Operations platform), `database` (local persistent DB), `kafka` (publish to Kafka topic). **Operations has an internal Kafka backplane for stats** — relevant if VCF-CF wants downstream stream-analytics integration later.
- **NEW — `AggregateFunc` enum is {SUM, AVG, MAX, MIN}**; query specs declare `aggregatesPerCounter: Map<String, Set<AggregateFunc>>`. **vCenter performs aggregation server-side over each sampling bucket**; the SDK receives pre-rolled values.
- **NEW — `Value` carries pre-aggregated statistics per data point** (value, min, max, count, sum, avg, opaque DataValue for non-numeric). 10-100× wire reduction vs. raw samples. Suggests the platform-internal metric pipeline is summary-stats-per-bucket, not raw-tick-per-sample.
- **NEW — `ResourceIds` identity shape is a flat List<ResourceId(key, value)>** — adapterKind / resourceKind are NOT in the model. Lossy if cross-stream; relies on QuerySpec scoping. Different identity shape from legacy `ResourceKey` (which DOES carry kind discrimination).
- **NEW — Auth path: SAML token + TOFU thumbprint verification** (`VcAuthentication` + `SamlTokenUtils` + `TOFUThumbprintVerifier`). vCenter SSO integration with trust-on-first-use cert handling.
- **NEW — `TransformerType` enum has 1 value: `VC_STATS_ESX`.** Designed to grow per-source-type; never has.
- **NEW — Failure model is sophisticated**: `FailedStream(specName, sourceId, lastPayloadTimeStamp, samplingInterval, retryCount, exception)`. SDK auto-retries via `retryFailedStreams()`, gives up via `cleanMaxRetryFailedStreams()`. Adapter polls failures via `client.collectFailureDetails()`.
- **NEW — Even the abstract `SdkClient` base carries `VcResource` + `VcBindingsManager` fields.** The "abstraction" is vCenter-shaped from the start; non-vc extension would require refactoring the base class. Package layout reserves space for other concretes (`SdkClient` → `VcSdkClient` is the one concrete shipping); intent ≠ implementation.

### Architectural recommendations for VCF-CF (`vcfcf-adapter-base.jar`)

- **DO** build the Tier 2 abstraction atop legacy `vrops-adapters-sdk-2.2.jar` + aria-ops-core decomposition (Pass 3 finding stands).
- **DON'T** bundle `vcf-ops-data-sdk` in the shared base jar (40MB, narrow applicability, appliance classpath doesn't carry it universally).
- **DO** leave a subscription hook in `LiveCollector` so generated adapters can implement `getCurrentMetrics()` as "drain-from-buffer". Future stream-based sources plug in without architectural refactoring.
- **DO** treat `vcf-ops-data-sdk` as a per-adapter optional dep — bundle only when the target source is vCenter stats.
- **Re-evaluate in 6-12 months**: if `vcf-ops-data-sdk-2.x.jar` ships and starts appearing in non-vSphere paks, the calculus changes.

### Files committed

`analysis/per-adapter/vcf-ops-data-sdk.md` (new); `spec/99-summary-and-vcf-cf-recommendations.md` (Pass 8 + Pass 9 updates appended); audit-log.

---

## 2026-05-16 — RE pass 10: describeSchema.xsd read directly (authoritative grammar)

Source: `analysis/decompiled/vim/vim/conf/describeSchema.xsd` (4629 lines, schema v6.3.0). Cross-checked with VrAdapter / SupervisorAdapter (v6.1.0) and VMwareInfrastructureHealthAdapter (v6.3.0). Full reading captured in `spec/02a-describe-xsd-canonical.md`.

### Pan-out / disprove ledger

- **DISPROVEN — "schemas are identical across adapters" (the CLAUDE.md assumption).** 3 distinct md5 variants in the corpus: 6.3.0 (vim, VMwareInfrastructureHealthAdapter), and TWO different 6.1.0 variants (VrAdapter ≠ SupervisorAdapter despite same advertised version). VCF-CF should target the newest (6.3.0).
- **NEW — `<AdapterKind>` permits 19 top-level children, only 1 required (`ResourceKinds`).** 7 of the 19 are completely undocumented in current SPEC: `Names`, `LaunchConfigurations`, `CustomGroupMetrics`, `TraversalSpecExtensionKinds`, `Faults`, `BasePolicyAnalysisSettings`, `OOTBPolicies`, `FavoriteGroups`.
- **NEW — `<Faults>` is a SEPARATE alert mechanism from Symptoms/AlertDefinitions.** Pair-based: `<ProblemEvent key="...">` triggers, `<ClearEvent key="...">` clears, `faultScore` (1-100) drives badge severity. `autoGenerateAlertDefs=true` shortcuts the Symptom+AlertDef boilerplate. Adapter pushes `FaultExternalEvent(eventId=key)` to trigger/clear. Useful when source system already emits trigger/clear pairs.
- **NEW — `<LaunchConfigurations>` is declarative UI deep-links.** LaunchConfig has HostProtocol + UriTemplate + Variables; matched by regex on adapterKindKey / resourceKindKey / alertType / alertSubType / active. ConfigMapping declares uiConfigKey (which UI page) + dispOrder. **First-class UI extension** that Tier 2 adapters can ship — deep link from a vSphere host to its vCenter UI page, etc.
- **NEW — `<Recommendation>` can trigger automated cross-adapter actions** via nested `<Action actionAdapterKey targetResourceKind actionKey/>`. Never observed in vSphere/mongodb data (text-only) but the framework supports full remediation automation. Major Tier 2 surface.
- **NEW — `<OOTBPolicies>` supports inheritance via `parentPolicy`.** Each policy carries `PolicySettings` keyed by adapter-kind × resource-kind combinations. Allows OOTB policies to span multiple MPs.
- **NEW — `ResourceKind.dynamic=true` is the schema-blessed mechanism for runtime-created kinds.** Dynamic kinds are NOT reconciled at re-describe time — DB state preserved. **EXPLAINS the NSXTAdapter3 finding** (Pass 5): 41 declared kinds + 0 TraversalSpecs + runtime-pushed topology = additional kinds are created with dynamic=true and survive across describe upgrades.
- **NEW — `ResourceKind.type` enum has 6 values, all documented in XSD**: 1=general, 2=Business Service, 3=Tier, 4=Tag, 7=Adapter Instance, 8=Group. Previously only type=7 was in SPEC. `subType` has its own 6-value enum with platform-specific meanings (geo, Enterprise, adapter-managed group, rules-managed group, world objects).
- **NEW — `ResourceKind.credentialKind` is COMMA-DELIMITED**: a single ResourceKind can accept multiple credential kinds. Multi-auth scenarios supported.
- **NEW — `ResourceAttribute` has 7 first-class booleans + dataType enum (5 values, not 3)**:
  - `isProperty`, `isPropertyHistoryEnabled`, `isRate`, `isDiscrete`, `isKpi`, `isImpact`, `defaultMonitored`, `keyAttribute`
  - **`isKpi` feeds Self-Health-Score → Anomalies badge** (drives the platform UI's anomaly indicator)
  - **`isImpact` excludes the attribute from root-cause analysis** (prevents misleading alert attribution)
  - **`defaultMonitored` decides whether the metric is collected by default in OOTB policy**
  - `dtType` lets author hint at preferred dynamic-thresholding algorithm (e.g., "multinomial" for strings)
  - `favoriteGroups` (";" delimited) is UI metric grouping
- **NEW — `PropertyDatatypeType` is a 17-value enum** (String, SInt32, UInt32, SInt64, UInt64, Decimal, Double, Boolean, DateTime, Binary, Byte, Enum, TypeName, Any, Integer, SnapshotData, ProcessesData) — DIFFERENT from ResourceAttribute's 5-value dataType. Used by method/action parameter declarations.
- **NEW — Condition `type` enum has 10 values in the XSD, only 6 observed in data**: schema-only values are `htsuper` (deprecated), `dtsuper`, `metric_event` (with "exists" operator), `smart` (VMware-internal). `htmetric` is also schema-deprecated ("use metric instead") — many vSphere uses are actually deprecated forms.
- **NEW — Condition `operator` has 20 values, 11 observed**: never-observed but schema-valid include `startswith`, `notstartwith`, `endswith`, `notendwith`, `notcontain`, `notregex`, `abnormal` (dt-metric — exotic baseline-deviation operator), `exists` (metric_event).
- **NEW — Severity enum in XSD has 4 values** (Info/Warning/Immediate/Critical, with lowercase variants). **`Automatic` is NOT in the XSD** but IS observed in vSphere. Either platform accepts non-schema values, or there's a 6.4+ schema we don't have. **Portability risk** — flag.
- **NEW — XSD `ConditionType` had a commented-out `xsd:assert`** that would have enforced inter-attribute consistency (type+key+operator combinations). Validators do NOT catch ill-formed conditions; the appliance does at runtime. VCF-CF should add cross-attribute validation the XSD lacks.
- **CONFIRMED — `<Discoveries>`/`<Discovery>` (not `<DiscoveryDescribes>` as drafted).** MPB's `DescribeDiscovery` emits `<Discovery>`. spec/02 needs correction.
- **NEW — DiscoveryParam.type enum is {string, integer, host, ip}** — same 4 values as `CredentialField.type` but DIFFERENT from ResourceAttribute.dataType. Three different "type" enums in the schema for three different surfaces.

### Architectural impact for VCF-CF

- 7 new top-level describe surfaces to expose as Tier 2 authoring options (Faults, LaunchConfigurations, OOTBPolicies, BasePolicyAnalysisSettings, CustomGroupMetrics, TraversalSpecExtensionKinds, FavoriteGroups).
- spec/05 (resource model) and spec/06 (metric model) need substantial expansion — ResourceAttribute has ~3× more authorable attributes than documented.
- VCF-CF should embed its own cross-attribute Condition validator (XSD doesn't enforce; appliance catches at runtime which is bad UX).
- Target schema v6.3.0; document the variant differences as a portability footnote.

### Files committed

`spec/02a-describe-xsd-canonical.md` (new — XSD-derived canonical grammar); `spec/00-overview.md` (index updated); audit-log.

---

## 2026-05-16 — RE pass 11: BuilderFile JSON hunt — NEGATIVE + bonus findings

Searched every pak in corpus (39 KEEP-C + 12 ELIMINATE-B + mpb-adapter itself) for a BuilderFile JSON instance.

### Ledger

- **NEGATIVE — no BuilderFile JSON in the corpus.** The mpb-adapter pak ships the runtime engine but no example design. No Track A pak in the corpus contains a BuilderFile. **Confirms what CLAUDE.md noted at calibration time**: "Pure Track A content packs were absent" from the bundle. The MPB runtime is shipped, but no consumers of it are.
- **NEW — `mpb_adapter-9.0.1-patch-1.jar` bundles `schema/describeSchema.xsd`** at the jar root. Confirms the Pass 7 finding that `DescribeXml.validateSchema()` runs XSD validation against the embedded schema. VCF-CF can pull the XSD from this location at build time. (Worth verifying whether the bundled XSD matches the v6.3.0 we read in Pass 10.)
- **NEW — MPB uses Hibernate Validator (JSR-303)** — `org/hibernate/validator/*.properties` bundled in 10 locales. **`BuilderFileValidation` is likely a thin wrapper over Hibernate Validator annotations on the BuilderFile model classes.** Big implication for Pass 16: the validation rules are declared as annotations on the Kotlin model — VCF-CF can read those annotations directly to enumerate the rule list.
- **CONFIRMED — wire format is reachable only via the Kotlin model** (no shipped instances). Until VCF-CF (or a unit test against the MPB jar) emits a sample, the spec must work from `BuilderFile.toJsonString()` semantics. Acceptable: the Kotlin model IS the source of truth.

### Files committed

audit-log update only — no spec/per-adapter file (negative result).

---

## 2026-05-16 — RE pass 15: MPB Bucket A — full BuilderFile guts enumerated

Source: `mpb_adapter-9.0.1-patch-1.jar`, packages `com.vmware.mpb.model.*`. Full spec at `spec/10-mpb-builderfile-schema.md`.

### Pan-out / disprove ledger

- **NEW — `BuilderHttpMetric.DataType` enum has ONLY 2 values: STRING, DECIMAL.** Compare to describe.xml dataType (5 values) and PropertyDatatypeType (17 values). **MPB metrics are coarse**: all numeric is DECIMAL (no int/float distinction; integers flattened). Tier 2 needed for fine-grained data types.
- **NEW — `BuilderEventSeverityEnum` has 6 values, not 4**: CRITICAL, IMMEDIATE, WARNING, INFO, **DEBUG, IGNORE**. The last two are MPB-specific (suppressed/filtered before reaching describe.xml's 4-value severity enum). Each enum carries `level: Int` and `describeLabel: String` — explicit MPB→describe mapping.
- **🎯 NEW — `BuilderAlertType` enum RESOLVES Pass 8's "platform alert-type code table" open question.** 5 values: APPLICATION, VIRTUALIZATION, HARDWARE, STORAGE, NETWORK — each with `describeValue: Int` (the actual int codes observed in vSphere data, {15, 16, 20}). VCF-CF can read the int values via reflection to close the MPB-enum ↔ platform-int bijection.
- **🎯 NEW — `BuilderAlertSubType` enum**: 5 values: AVAILABILITY, PERFORMANCE, CAPACITY, COMPLIANCE, CONFIGURATION — each with describeValue. **MPB SubType enum (5 values) is a SUBSET of the platform's 8 distinct values observed in vSphere data** ({6, 18, 19, 20, 21, 22, 28, 29}); Tier 2 adapters access subType codes Tier 1 cannot author.
- **CONFIRMED — `BuilderBadge` is exactly {EFFICIENCY, HEALTH, RISK}** — matches Pass 8 spec/08 finding.
- **NEW — `BuilderEvent` is MUCH richer than the Pass 7 "eventMsg-only" hint suggested**: dynamic severity (`BuilderEventSeverity` = expression + mapping table + default), message templating (`messageExpression`), pre-filtering (`filterExpression`), multi-resource matching (`matchMode: ALL|FIRST`), and cross-MP event attachment (`BuilderEventMatcher.adapterKind` can be foreign). **The MPB-emitted describe.xml `<SymptomDefinition>` is still eventMsg-only at the wire layer (Pass 7); the upstream BuilderEvent model that VCF-CF generates against has substantially more expressivity.**
- **NEW — `BuilderRelationship.parent` and `.child` are both `BuilderRelationResource` with `adapterKind` field** — both sides can be FOREIGN. Cross-MP relationships are first-class declarative in MPB.
- **NEW — `BuilderHttpAuthentication.AuthenticationType` is abstract with 3 concrete subclasses**: `BasicBuilderAuth` (hardcoded USERNAME_CREDENTIAL + PASSWORD_CREDENTIAL keys), `SessionTokenBuilderAuth` (rich — getSession+releaseSession requests, responseFields with BODY/HEADER location enum, nested credentialType so login uses Basic/Custom), `CustomBuilderAuth` (empty escape hatch). **SessionToken supports modern REST token APIs end-to-end including clean logout — no OAuth/Kerberos/SigV4/HMAC first-class.**
- **NEW — `BuilderRequest.HttpMethod` is 5 verbs**: GET, POST, DELETE, PUT, PATCH. No HEAD/OPTIONS/TRACE/CONNECT.
- **NEW — `BuilderPaging.BuilderPagingType` is 2 strategies**: OFFSET (offset/limit) and PAGES (page/perPage). **No cursor-based or link-header pagination** as first-class; either CUSTOM or unsupported.
- **NEW — `BuilderRequest.parentRequest` + `BuilderParentRequestParameter`** formalize the chained-request mechanism: child declares parent by `requestId`, runtime walks `listExpression` to enumerate items, extracts `attributeExpression` from each to substitute into child URL/body/params. This is the list-then-detail pattern as a first-class authoring concept.
- **NEW — `BuilderObjectBindingType` is 2 values**: ATTRIBUTE_TO_PROPERTY (match-by-identifier) and CHAINED_REQUEST (1:1 via chained linkage). The cross-MP attachment path is ATTRIBUTE_TO_PROPERTY.
- **NEW — `BuilderMatchIdentifier` is the cross-cutting matching primitive** (used by object bindings, event matchers, relationship resources). 2 types: IDENTIFIER (match against ResourceKey identifier) or PROPERTY (match against resource property). With optional `regex` for fuzzy extraction.
- **NEW — `HttpResourceNameType` enum has ONLY 1 value: PROPERTY.** Resource names are always computed by looking up a designated property. No literal-name or expression-based-name authoring — designs that need computed names must materialize them as a property first.
- **NEW — `TimeseriesMode` is 2 values**: FIRST or LAST. No aggregation; use ComputedMetrics for sum/avg/max/min.
- **NEW — `BuilderHeader.enabled: Boolean`** — toggle flag for conditional headers. Asymmetric with `BuilderParam` (no enabled flag).
- **NEW — MPB metric attribute booleans are POOR vs. describe.xml**: only `property` and `kpi` exposed. The richer `isImpact`, `defaultMonitored`, `dtType`, `isRate`, `isDiscrete`, `isPropertyHistoryEnabled`, `keyAttribute`, `favoriteGroups`/`favoriteInstances` from Pass 10's XSD reading are NOT in MPB's authoring surface — Tier 1 cannot author them.

### Architectural impact for VCF-CF Tier 1

The full BuilderFile authoring surface is now characterized. The Tier 1 capability list and Tier 2 promotion-trigger list are documented exhaustively in `spec/10-mpb-builderfile-schema.md`. Notable additions to the promotion-trigger list:

- Auth beyond Basic / SessionToken / Custom (OAuth2 refresh, Kerberos, AWS SigV4, HMAC per-request, mTLS-with-renewal)
- Metric data types beyond STRING/DECIMAL (integer-typed, structured)
- Resource naming strategies beyond property-lookup
- The 7+ richer ResourceAttribute booleans (isImpact, defaultMonitored, dtType, isRate, isDiscrete, isPropertyHistoryEnabled, keyAttribute, favoriteGroups)
- Pagination beyond OFFSET/PAGES (cursor, link-header, Range)
- Aggregating timeseries (only FIRST/LAST; need ComputedMetrics post-processing)
- HTTP verbs beyond GET/POST/DELETE/PUT/PATCH

### Notable: alert categorization is generatable from MPB enums

VCF-CF can populate Tier 1 alert-authoring dropdowns directly from `BuilderAlertType` × `BuilderAlertSubType` × `BuilderBadge` enum constants (5 × 5 × 3 = 75 combinations). The actual platform int codes are accessible via the `describeValue` field on the type/subType enums — closes the Pass 8 "type/subType int → category lookup table" open question.

### Files committed

`spec/10-mpb-builderfile-schema.md` (new — full Tier 1 authoring vocabulary); audit-log.

---

## 2026-05-16 — RE pass 17: 🔥 MPB output is Track C-shaped, NOT Track A

Source: `inputs/known_mpb/` — 3 real-world MPB designs (UniFi, phpIPAM, vSAN) + the paks they produced. Full spec at `spec/11-mpb-designer-wire-format.md`. **Major architectural reframe.**

### Pan-out / disprove ledger

- **🔥 DISPROVEN — Pass 1/7 hypothesis "MPB outputs lightweight Track A paks dispatched by a shared `mpb-adapter` runtime".** Real MPB-built paks are **22 MB Track C-shaped**, each carrying:
  - A per-pak generated entry jar (~236 KB, ~100 classes) with `KINDKEY` + `ENTRYCLASS` in adapter.properties at the entry-jar root (standard SDK contract)
  - **60 bundled dep jars** including `aria-ops-core-8.0.0.jar`, Kotlin stdlib/coroutines/reflect, Ktor (client/utils/network), Jackson, Apache HTTP client, woodstox, log4j, guava
  - The runtime `conf/design.json` (BuilderFile, ~20-40 KB)
  - Standard pak chrome (manifest.txt, eula.txt, install scripts, dashboards)
- **NEW — per-pak code generation, kind-key baked into package paths**: every class is `com.vmware.mpb.<kindkeyNoUnderscores>.impl.*`. UniFi pak has `com.vmware.mpb.mpbubiquitiunifi.impl.{validation,result,relationships,query,externalresource,collect.http}.*`; phpIPAM has `com.vmware.mpb.mpbphpipam.impl.*`. Same class set, different package. The MPB runtime jar (`mpb_adapter-*.jar`'s `com.vmware.mpb.impl.*`) is the **template/source** that gets regenerated per pak.
- **🎯 NEW — TWO distinct JSON formats** (this resolves the Pass 7 "1:1" confusion):
  1. **Designer wire format** (`*_MP_Builder_Design.json`, what the user provided): richer, structured-expression-objects with `@@@MPB_QUOTE <partId> @@@MPB_QUOTE` placeholders, captured response samples in `dataModelLists`, designer UUIDs, HTTP-client config (`source.source.configuration` with port/sslSetting/baseApiPath/maxRetries/maxConcurrentRequests/connectionTimeout/minEventSeverity), `globalHeaders`. Top-level keys: design, source, requests, objects, relationships, events, content.
  2. **Runtime BuilderFile** (shipped in `<adapter>/conf/design.json` inside the pak): **1:1 with the Kotlin model from spec/10**. Top-level keys: id, name, pakSettings, source, constants, relationships, version. The designer's `objects[]` → runtime's `source.resources[]`; `chainingSettings` → `parentRequest`; structured expressions → string templates `${@@@MPB_QUOTE_BODY <jsonpath> @@@MPB_QUOTE}`; designer-only fields stripped.
- **CONFIRMED — spec/10 Kotlin BuilderFile model exactly matches shipped runtime form.** Pass 15's enumeration was validated against real shipped data across all 3 designs.
- **NEW — runtime expression DSL is string-template form**: `${@@@MPB_QUOTE_BODY <jsonpath> @@@MPB_QUOTE}` for body navigation. Other namespaces (from designer): `${configuration.<key>}`, `${authentication.credentials.<key>}`, `${authentication.basic}`, `${authentication.session.<key>}`, `${requestParameters.<key>}`. The runtime's `ResourceQueryHelperKt` evaluates these.
- **🎯 CONFIRMED + REINFORCED — aria-ops-core IS the canonical SPI**. `aria-ops-core-8.0.0.jar` bundled in EVERY MPB-generated pak's `lib/`. The Pass 3 finding is now triply confirmed (BlueMedora marketplace adapters + MPB runtime + every MPB-built pak). **VCF-CF's `vcfcf-adapter-base.jar` should adopt this SPI** — Pass 3+9+17 all point the same direction.
- **NEW — auto-namespaced ResourceKind keys**: `<adapterKindKey>_<label-slug>` (spaces → `___`, lowercased). Example: `mpb_ubiquiti_unifi_unifi___clients` for label "UniFi - Clients" under adapter kind `mpb_ubiquiti_unifi`.
- **NEW — header.type enum on designer side**: `REQUIRED`, `IMMUTABLE`, `CUSTOM` — richer than runtime BuilderHeader's `enabled: bool`. Designer-only knob.
- **NEW — Header substitution pattern for Basic auth**: `Authorization: Basic ${authentication.basic}` — the substitution language pre-computes the base64-encoded basic auth string.
- **NEW — sessionVariables (designer side)**: `sessionSettings.sessionVariables[]` declares which response fields to extract into the auth context. Each has `key`, `path`, `usage` (template like `${authentication.session.rawvalue}`), `location: BODY|HEADER`. Cleaner than Pass 15's SessionTokenResponseField enumeration.
- **NEW — manifest.txt iSDK template placeholders**: MPB designer leaves `"display_name": "DISPLAY_NAME"` and `"vendor": "VENDOR"` unfilled — **MPB shares the iSDK template** infrastructure. Same calibration finding noted for Track B paks (CLAUDE.md) holds for MPB-built paks too.
- **NEW — license enforcement is per-kind**: `manifest.txt:"license_type": "adapter:<kindkey>"` + bundled `licensecheck-1.1.5.jar`. Every MPB-built adapter is individually licensed.
- **NEW — pak-platform compatibility**: `vcops_minimum_version: "7.5.0"` + `platform: ["Windows", "Linux Non-VA", "Linux VA"]` + `disk_space_required: 500` (MB). These are pre-install pre-check fields.

### Architectural impact for VCF-CF — major reframe

Pass 7's "load mpb_adapter jar, call IWritableFile writers, package result" is INSUFFICIENT for matching real MPB designer output. Tier 1 is fundamentally a **Java/Kotlin code generation task**. Two paths documented in spec/11:

- **Path A (lightweight, unofficial)**: Emit only BuilderFile + describe.xml + manifest as a tiny pak that depends on a shared `mpb-adapter` runtime pak. Not observed in the wild; appliance support uncertain.
- **Path B (match the official toolchain — RECOMMENDED)**: Per-pak codegen — generate ~100 Kotlin classes templated against the design's kind key, compile, bundle ~60 dep jars, ship 22 MB Track C-shaped pak. Indistinguishable from MPB-designer output.

Three impl strategies for the codegen step (in spec/11):
1. Source-level kind-key rename + recompile with kotlinc
2. Bytecode-level package rename with ASM (no kotlinc needed)
3. Shared runtime (Path A — confirm appliance support first)

### Files committed

`spec/10-mpb-builderfile-schema.md` (Pass 10's premature edit rolled back — spec/10 is correct for the runtime form); `spec/11-mpb-designer-wire-format.md` (new — designer wire format + pak generation pipeline + Track-C-shape finding); `spec/00-overview.md` (index updated); `.gitignore` (inputs/known_mpb added); audit-log.

---

## 2026-05-16 — RE pass 16 (partial): MPB emission pipeline polish

Source: `mpb_adapter-9.0.1-patch-1.jar`. Open follow-ups from Pass 7 partially resolved; remaining items deferred.

### Pan-out / disprove ledger

- **NEW — the pak orchestrator does NOT exist inside the MPB runtime jar.** Exhaustively searched for any class referencing both `IWritableFile` and `DescribeXml` — none exists outside the writer classes themselves. The orchestration of "call all 6 writers + bundle a pak" is the responsibility of an EXTERNAL build tool (the MPB designer's pak-build step / a CLI not in our corpus). **VCF-CF MUST own this orchestration** — no library hook to delegate to. Documented in `spec/12 § "The pak orchestrator does NOT exist..."`.
- **NEW — `MPBAdapter` abstract class architecture mapped**. `abstract class MPBAdapter : UnlicensedAdapter` (from aria-ops-core). The per-pak generated entry class only overrides TWO methods: `getAdapterDirectoryName()` and `getTemplateSHA()`. Everything else (aria-ops-core SPI implementations, request runtime, relationship creator, etc.) lives in the inherited base class + `com.vmware.mpb.impl.*` package. **A per-pak adapter is effectively a 2-method override.**
- **NEW — Strategy 4 codegen path** unlocked by the MPBAdapter finding: if VCF-CF ships a "runtime-contribution pak" that places `com.vmware.mpb.MPBAdapter` + impl tree on the appliance classpath, every Tier 1 pak becomes a ~50 KB stub class extending MPBAdapter + design.json + describe.xml. Same risk as Path A (classloader sharing must be confirmed). Added to `spec/12 § Strategy 4`.
- **DEFERRED — DescribeAttributeDataType enum values, DescribeUnitType catalog, Hibernate Validator annotations** — polish items with diminishing returns vs. the broader investigation. Will pick up in a future targeted pass if VCF-CF requests specific items.

### Files committed

`spec/12-mpb-handoff-for-vcf-cf.md` (extended with Strategy 4 + pak-orchestrator finding); audit-log.

---

## 2026-05-16 — RE pass 12: 🚨 aria-ops-core universality DISPROVED

Source: entry-class decompilation for each Broadcom-internal native adapter + lib/ inspection. **Major correction to Pass 3/9/17 framing.**

### Pan-out / disprove ledger

- **🚨 DISPROVEN — "aria-ops-core is universally used as the SPI" (Pass 3/9/17 framing).** Verified by extracting `ENTRYCLASS` from `adapter.properties` of every Broadcom-internal native adapter and running javap to inspect the parent class:
  - **All Broadcom-internal classic adapters extend `com.integrien.alive.common.adapter3.AdapterBase` DIRECTLY** (not via aria-ops-core): vim (ManagementAdapter), NSXTAdapter3 (NSXTAdapter), vmwarevi_adapter3 (VMwareAdapter), VCFAutomation (AutomationAdapter), VrAdapter (VrAdapter), SupervisorAdapter, ServiceDiscoveryAdapter3, VirtualAndPhysicalSANAdapter3, AppOSUCPAdapter3.
  - **NONE of them bundle `aria-ops-core-*.jar`** in lib/. Searched all 9 Broadcom-internal adapter trees.
- **NEW — aria-ops-core IS a wrapper, not parallel**: `com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter extends com.integrien.alive.common.adapter3.AdapterBase`. So aria-ops-core adopters still ultimately compile against AdapterBase; the wrapper just provides a Tester/Discoverer/LiveCollector/HistoricalCollector SPI decomposition on top.
- **CORRECTED architectural landscape**:
  - `AdapterBase` (legacy template-method) = UNIVERSAL foundation — every Track C adapter extends it
  - **Option A (Broadcom-internal pattern)**: extend AdapterBase directly, write own helpers — used by all Broadcom-internal classic teams (vim, NSX, vSphere, VCFAutomation, ...)
  - **Option B (BlueMedora-derived + MPB pattern)**: extend `UnlicensedAdapter` for the cleaner SPI — used by BlueMedora marketplace adapters (mongodb/mysql/postgresql/oracle/etc.) + MPB runtime + MPB-generated paks
- **NEW — there is NO shared "Broadcom-internal-adapter framework"** between vim/NSX/vSphere/VCFAutomation etc. They each work directly against AdapterBase with their own helper code. Confirmed by diffing the lib/ jar sets — no common framework jar shared across them. The "three SDK-pinning styles" finding from Pass 5 is reinforced: each adapter team makes independent dep-bundling decisions.
- **aria-ops-core is Broadcom-owned** (post-BlueMedora acquisition ~2018, `com.vmware.tvs.*` package = "True Visibility Suite", the BlueMedora product line). It's not a third-party / external dependency risk. But it's ALSO not the Broadcom-internal-team standard.

### Architectural impact for VCF-CF

The recommendation in spec/99 / cleanroom-key-findings #2 / spec/12 "adopt aria-ops-core SPI for vcfcf-adapter-base.jar" needs CORRECTION (not retraction):

- **Both Option A (direct AdapterBase) and Option B (aria-ops-core wrapper) are legitimate.** Either produces a valid Track C adapter.
- **Option B is still recommended** because (a) the SPI is cleaner and pre-built, (b) MPB-generated paks already use it (so VCF-CF Tier 1 path inherits this SPI for free — no abstraction-layer divergence between Tier 1 and Tier 2), (c) Broadcom-owned + shipped in production.
- **But it's a choice, not a forced conclusion from "everyone does it this way."** ~Half the production ecosystem uses Option A.
- **The three-axis collection split (`getCurrentMetrics`/`getEvents`/`getRelationships`) is good design regardless** — VCF-CF should adopt that pattern even if it picks Option A (then implements the SPI itself).

### Files committed

`spec/12-mpb-handoff-for-vcf-cf.md` (aria-ops-core section corrected with Option A vs Option B framing); audit-log.

### Memory updates required

`cleanroom-key-findings.md` finding #2 needs the same correction.

### Files to remove from mpb_spec.zip + rebuild

The earlier zip (commit 98c0d2f) has the pre-correction spec/12. Need to rebuild after committing this update.

---

## 2026-05-16 — RE pass 13: classloading + appliance runtime classpath

Source: `inputs/from-devel/sdk/common-lib/` (the platform shared classpath) + per-adapter lib/ inspections + entry-class import enumeration. Full spec at `spec/13-classloading-and-classpath.md`.

### Pan-out / disprove ledger

- **NEW — appliance shared classpath enumerated** (`common-lib/` directory, 13 jars): `alive_common.jar` (legacy SDK common), `alive_platform.jar` (platform API), `vrops-adapters-sdk-1.0.jar` + `vrops-adapters-sdk.jar` (two versions of the SDK contract — compat shim arrangement), `vrops-trustmanager-3.0-SNAPSHOT.jar`, `vrops-logging`, `vrops-csp-client`, `vrops-rmi`, `vrops-jmx-metrics`, `vrops-alias-instrumentation`, `vrops-replication-client`, `vrops-vidb-client`, `capability-registry`.
- **CONFIRMED — `aria-ops-core` is NOT on the shared classpath.** Adapters that use it MUST bundle it in their own lib/ (mongodb bundles 8.2.0; MPB-generated paks bundle 8.0.0). This explains the Pass 12 finding from a different angle.
- **NEW — per-pak classloader isolation confirmed**: each adapter has its own classloader layered on the shared platform classpath. Bundled lib/ jars are visible only to that pak. Version conflicts don't cascade (same library can ship at different versions in different paks).
- **🎯 NEW — Path A / Strategy 4 for MPB Tier 1 are NOT VIABLE** without platform-team participation. The MPB runtime's `com.vmware.mpb.MPBAdapter` lives in `mpb-adapter` pak's per-pak classloader; other paks (whether VCF-CF-generated or MPB designs) cannot extend it across the classloader boundary. **MPB regenerates per-pak BECAUSE of this isolation** — the lightweight shared-runtime model isn't a Broadcom design choice they declined; it's actively prevented by the classloading topology.
- **NEW — three pak shapes mapped to classpath behavior**:
  - **C2 (lean, no lib/)**: SupervisorAdapter pattern. 53 classes, 171 KB, entirely relies on shared classpath for the legacy SDK + platform API + own helper classes.
  - **C1 (light)**: a few HTTP/JSON jars bundled.
  - **C1 (rich)**: 60-100 dep jars including full HTTP/JSON/vendor stacks. vim, vSphere, mongodb, MPB-generated.
- **NEW — version inconsistency observed across the corpus**: same library (e.g., Jackson) ships in 4 different versions (2.11.3, 2.12.3, 2.15.0, 2.17.1). Per-pak isolation makes this work. Tier 2 generators should treat each pak's dep set as INDEPENDENT.
- **CONFIRMED — platform-always-available class set documented** for VCF-CF Tier 2 generators: legacy SDK (`com.integrien.alive.common.adapter3.*`), platform API (`com.vmware.ops.api.*`), logging (`com.vmware.vrops.logging.*`), trust manager (`com.vmware.vrops.secure.connection.*`). MUST-BUNDLE list: aria-ops-core (if Option B), Jackson, HTTP client, Kotlin runtime (if Kotlin codegen), log4j, vendor SDKs, licensecheck (if using `license_type`).

### Architectural impact for VCF-CF

- **MPB Tier 1**: Path B (per-pak codegen) is the only practical path. Strategies 1/2 in spec/12. Path A and Strategy 4 are eliminated from consideration unless Broadcom platform-team adds shared-classpath support.
- **Tier 2 packaging**: documented C2/C1-light/C1-rich shapes with a recommendation to default to C1-rich for safety; expose pak-shape as a deployment knob.
- **Dependency bundling discipline**: spec/13's "what to bundle" table is the authoritative reference for Tier 2 generators.

### Files committed

`spec/13-classloading-and-classpath.md` (new); audit-log.

---

## 2026-05-16 — VCF-CF field findings folded back into spec

Source: VCF-CF api-explorer empirical reverse-engineering during 2026-05-16 implementation work. Two findings that addressed spec open questions / vagueness.

### Pan-out / disprove ledger

- **NEW — `sanitizeFunction` label→key derivation algorithm enumerated** (VCF-CF empirical RE):
  1. Drop `.`
  2. Drop `()`
  3. Lowercase
  4. Replace whitespace + `%` with `_`
  5. Collapse `_+` runs to single `_`
  
  Earlier spec described examples like `mpb_ubiquiti_unifi_unifi___clients` with triple-underscore (which doesn't match the collapse step). This suggests the runtime's slugifier doesn't apply collapse in every codepath, OR is version-dependent. **VCF-CF should run the full 5-step pipeline on emit AND tolerate either form on read.**
- **NEW — `@@@MPB_QUOTE_REQUEST_PARAMETERS` marker confirmed** as REQUIRED for `objectBinding.requestMatchIdExpression` when the resource is owned by a chained request. The marker FAMILY (not just `@@@MPB_QUOTE_BODY`) is `@@@MPB_QUOTE_<SCOPE>`:
  - `BODY` — HTTP response body navigation
  - `REQUEST_PARAMETERS` — chaining-context lookup (connects child rows to parent context)
  - Likely more for headers / session / etc. — spec should treat the list as "at least these," not exhaustive
  
  Without the `REQUEST_PARAMETERS` marker, chained-resource bindings break (orphaned child rows with no parent reference).

### Architectural impact

These corrections address two of the spec's open follow-ups (the dataModelList → expression-string compilation algorithm + sanitize behavior). Field findings like these should continue to flow back as VCF-CF works through more designs.

### Files committed

`spec/11-mpb-designer-wire-format.md` (expression-DSL + sanitize-algorithm sections expanded); `spec/12-mpb-handoff-for-vcf-cf.md` (TL;DR + capability table + new § 8.5 "Field findings from VCF-CF"); audit-log.

---

## 2026-05-16 — RE pass 18+19: Capacity model + Policy framework (spec/09)

Source: vSphere (11 CapacityDefinitions, 16 OOTBPolicies/PolicySettings, full settings ladder) + mongodb (3 + 2 + 5, complete reclaimable ladder) + VirtualAndPhysicalSANAdapter3 + VCFAutomation + vcops_adapter3.

### Pan-out / disprove ledger

- **NEW — Two-layer architecture**: `<CapacityDefinition>` declares resource-container axes (cpu/mem/disk/network/...) per resource kind; `<PolicySettings>` configures how those axes are analyzed.
- **NEW — `<ResourceContainer>` full attribute surface**: 25+ attributes including model (default/alloc), consumer/provider linkage for cross-kind capacity flow, computeFromConsumers/Providers, custom-profile linkage, sizing-recommendation knobs.
- **NEW — Settings ladder** (full): StressedSettings, UsableCapacitySettings (with CapacityBuffer + OverCommit), WorkloadSettings, CapacityTimeRemainingSettings, TimeSettings, ReclaimableCapacitySettings (wraps WasteSettings + IdleSettings + PoweredOffSettings + UnderusedSettings + UnUsedSettings), DensitySettings, plus vSphere-only RiskLevelSettings / WorkloadAutomationSettings / WorkloadOptimizationSettings.
- **NEW — `<ApplicableResourceContainer>` is the per-axis applicability primitive** across all settings — `resourceContainerKey` + `enabled` + (optionally) `threshold`, `slaEntireRange`, `slaDuration`, `hidden`.
- **NEW — OOTBPolicies has TWO shapes**:
  - mongodb pattern: inline PolicySettings inheriting from base via `inheritPolicySettings`
  - vSphere pattern: PackageSettings with per-alert `<Alerts adapterKind resourceKind><Alert id enabled/></Alerts>` toggles
- **NEW — Capacity-and-policy is the largest describe.xml surface** (often 80%+ of a complex adapter's describe.xml volume). VCF-CF should expose templated authoring: simple/full-capacity-aware/placement-participant.

### Files committed

`spec/09-capacity-and-policy.md` (new); audit-log.

---

## 2026-05-16 — RE pass 20: UI + Operational Surfaces (spec/14)

Source: vSphere (66 Methods, 42 Actions, 34 LaunchConfigs, 28 PowerState/Icon blocks), AppOSUCPAdapter3 (77 Methods — largest), VirtualAndPhysicalSANAdapter3 (477 FaultStates — largest), vSphere ProblemEvent/ClearEvent pairs.

### Pan-out / disprove ledger

- **NEW — Methods + Actions are two-layer**: Method declares the callable + parameter schema; Action binds method to resource contexts + UI invocation form. Multi-context Actions (one Action exposed on VirtualMachine, HostSystem, AND ClusterComputeResource — vSphere PowerOffVM pattern) are first-class.
- **NEW — Action has its OWN SpEL-like expression language** with helpers (identifier, attribute, parents/children/descendants, isAttributeDisabledFromPolicy, localizedString, resourceAttributeFormat, value('invalid') as skip-sentinel). Used in resourceEndpointExpression, resourceTarget, ActionContextField.value, LaunchConfig.active, LaunchConfig.Variable.
- **NEW — Method `<Metadata>` annotations**: `translationExpression` (translate user-supplied raw value via SpEL), `groupedValueExpression` (semantic-list parameter for batch), `disableBatching` (method-level — no parameter batching across resources).
- **NEW — Faults can have MULTIPLE `<ProblemEvent>` at escalating faultScores** sharing one `<ClearEvent>`. vSAN's Yellow(30)/Red(100) pattern is the dominant idiom. Multi-severity fault progressions are first-class.
- **NEW — LaunchConfig substitution syntax is `{var}` (curly only)** — DISTINCT from `${expr}` used elsewhere. Variables declared via `<Variable name>expression</Variable>` children with full SpEL syntax.
- **NEW — LaunchConfig.active is a SpEL predicate** for version/feature gating (e.g., `isVCenterVersionEqualOrNewerThan('6.7') and !isVCenterVersionEqualOrNewerThan('7.0')`). Adapter-specific helper functions can be registered.
- **NEW — `<Icon>` is a multi-level decision tree**: `<Condition property><Case suffix value>...<Condition>...</Case></Condition>`. Walks properties + PowerState to build icon-name suffix path (e.g., `vm_ft_primary_power_on.svg`). vSphere has 28 such trees.
- **NEW — `<PowerState alias>` maps source-system power values to canonical keys** (ON/OFF/SUSPENDED/UNKNOWN/STANDBY). Used by capacity analysis to exclude powered-off resources.

### Files committed

`spec/14-ui-and-operational-surfaces.md` (new); audit-log.

---

## 2026-05-16 — RE pass 21: Loose ends resolved

Sources: bytecode constant-pool inspection of MPB enum classes (BuilderAlertType, BuilderAlertSubType, BuilderEventSeverityEnum); SDK Relationships + AdapterBase + AdapterInterface3 javap.

### Pan-out / disprove ledger

- **🎯 RESOLVED — BuilderAlertType.describeValue ints**: APPLICATION=15, VIRTUALIZATION=16, HARDWARE=17, STORAGE=18, NETWORK=19. Extracted from bytecode constant-pool via `javap -c -p`.
- **🎯 RESOLVED — BuilderAlertSubType.describeValue ints**: AVAILABILITY=18, PERFORMANCE=19, CAPACITY=20, COMPLIANCE=21, CONFIGURATION=22.
- **NEW — type=20 and subType={6, 28, 29} observed in vSphere are TIER-2-ONLY values** — they're outside the MPB enum range. MPB enum is a STRICT SUBSET of platform-accepted codes. Documented in spec/08 § "Type / SubType code table — RESOLVED".
- **RESOLVED — BuilderEventSeverityEnum.level ints**: CRITICAL=4, IMMEDIATE=3, WARNING=2, INFO=1, DEBUG=0, IGNORE=0. (DEBUG and IGNORE share level=0 because they're MPB-specific and suppress before reaching the platform's severity system.)
- **🎯 RESOLVED — `Semaphore locker` in AdapterBase CONFIRMED** as the concurrency-serialization mechanism. `collect()` is at-most-one per adapter instance. Per-instance Adapter object is REUSED across cycles. Documented in spec/01 § Open/pending → RESOLVED.
- **NEW — AdapterInterface3 exact surface**: 8 abstract methods + 1 default (`stopCollection`). Documented in spec/01.
- **NEW — Relationships API full surface** (spec/07 updated): 18 method signatures across 3 axes — (add/remove/set) × (standard/generic) × (single/bulk-merge). Generic variants carry a `label` and optional `namespace` for typed edges. `set` is REPLACEMENT semantics with optional `Set<String>` filter for label-scoped replacement.

### Architectural impact

- Tier 2 generators now have precise int code tables for both directions (MPB-enum ↔ platform-int) for alerts.
- Concurrency model resolved as at-most-one — VCF-CF can plan around single-threaded collect() per instance.
- Full Relationships API documented — VCF-CF can expose all 6 operation families to authoring users.

### Files committed

`spec/07-relationships-cross-mp.md` (full API surface section), `spec/08-alerts-symptoms-recommendations.md` (type/subType resolved), `spec/01-adapter-lifecycle.md` (concurrency + AdapterInterface3 confirmations); audit-log.

---

## 2026-05-16 — RE pass 22: Tier 2 handoff doc + Navani gap-ask request

Closes the Tier 2 (Native Java) RE arc.

### Pan-out / disprove ledger

- **NEW — spec/15 Tier 2 handoff doc**: 12 takeaways + the
  vcfcf-adapter-base.jar shape recommendation (Option A AdapterBase-direct
  vs Option B aria-ops-core wrapper). Stands alone as a strategic-picture
  document for VCF-CF Tier 2 implementers, parallel to spec/12 for MPB.
- **NEW — cross-workspace request filed to lab-admin (Navani)** for 4
  narrow data/log gaps: CustomGroupMetrics example, install lifecycle
  log, collect() debug trace, signature validation logs. Request ID
  `6d25e88d-6aad-42f7-af62-eea3db2ec61d`. Lives in PKA infrastructure
  at `agents/riker/inbox/archive/`, not in this workspace tree.

### Architectural impact

- Tier 2 spec is shippable as-is to VCF-CF. The Navani request is for
  upgrading "inferred" claims to "confirmed" — not blocking on Tier 2
  work starting.

### Files committed

`spec/15-tier2-handoff-for-vcf-cf.md` (new), `spec/00-overview.md` (index), `.gitignore` (gitignore .pka/ + tier2_spec.zip).

---

## 2026-05-16 — RE pass 23: integrate Navani field confirmations

Source: Navani's response bundle at
`/home/scott/vault/workspaces/lab-admin/exports/vcf-mp-cleanroom-2026-05-16/`
(8.9MB, structured per-ask). All 4 requested asks answered; 3 are
substantive deltas, 1 is a confirmed-negative.

### Pan-out / disprove ledger

- **🎯 RESOLVED — Install pipeline architecture**: two-layer model with
  CASA orchestrator (Java) driving a 7-phase state machine that invokes
  a Python subprocess (`vcopsPakManager.py --action <phase>`) per phase.
  Phases: STAGE → PREAPPLY_VALIDATE → VALIDATE →
  APPLY_ADAPTER_PRE_SCRIPT → APPLY_ADAPTER → APPLY_ADAPTER_POST_SCRIPT
  → CLEANUP. Documented in new spec/16.
- **🎯 RESOLVED — `describe.xml` parsed during the `apply_adapter`
  phase**, not at adapter-instance configure() time. Answers the
  long-standing open question in spec/01 about WHEN describe is read.
- **🎯 CORRECTED — Adapter hook scripts route by `manifest.txt` keys,
  not by filename**. The `validate.py` / `preAdapters.py` /
  `postAdapters.py` names visible in some Broadcom-internal paks are
  conventional, not contractual. Pak authors choose filenames; the
  appliance routes by `pak_validation_script` / `adapter_pre_script` /
  `adapter_post_script` keys in `manifest.txt`.
- **🎯 RESOLVED — Semaphore scope is PER-INSTANCE**. Empirically
  confirmed via DEBUG collector log: same-kind different-instance
  adapters run in parallel on different worker threads (rules out
  per-kind), different-kind adapters overlap freely (rules out
  global), same-instance never overlaps itself across cycles
  (confirms per-instance Semaphore(1) keyed on instance ID). Within
  a single instance's cycle, single-threaded (all DEBUG lines on
  same thread per cycle). Documented in spec/01 § Pass 23
  confirmations.
- **🎯 RESOLVED — Platform does NOT retry failed `collect()` cycles**.
  Errors are swallow-and-log; the next scheduled cycle proceeds
  normally. Retry behavior exists one layer down in vendor SDK
  callers (e.g. `QueryStatsCaller` "attempt N" counters), but the
  platform-level `collect()` contract is "fire on schedule, log what
  you get". Adapter authors must implement own retry inside
  onCollect() if needed.
- **🎯 RESOLVED — Empirical signature validation: appliance accepts
  unsigned paks and installs them in full**. 42 distinct
  unsigned-install records observed (Rubrik-11025, GitLab-1001,
  Synology*, VCFContentFactory*); each shows complete STAGE→CLEANUP
  cycle in `casa_pak_history_<pakID>.json`. The `invalid_reason`
  field is recorded but not enforced as a gate. No admin override
  required.
- **🎯 RESOLVED — Cert validity dates are NOT enforced**. Paks built
  2025-12-30 with the expired-2026-01-03 VMware self-signed cert
  (per analysis/pak-signing-chain.md), uploaded April 2026, come
  back `certificateUntrusted:false`. Behavior is "skip dates" —
  either explicit bypass or fingerprint-pinning that never consults
  the validity window.
- **🎯 RESOLVED — Signature check is opt-in at the API layer**:
  `findPakInformation` / `getPakInformation` take an optional
  `checkSignature` parameter; the common case is null (no check
  requested). Even when set true, the result is informational, not
  gating.
- **NEGATIVE — `<CustomGroupMetrics>` remains unobserved in any
  installed adapter** on either lab ops appliance. Grep across 22
  devel + 30 prod `conf/describe.xml` returns zero. Parser-class
  evidence proves the runtime contract is real (clean-room safe via
  `unzip -l`): `CustomGroupMetricsDescribe.class` in
  `vrops-adapters-sdk-1.0.jar`, plus `CustomGroupMetrics.class` and
  `CustomGroupMetricDescriber.class` in `persistence-1.0-SNAPSHOT.jar`.
  Schema documented in spec/02a from XSD; runtime usage example needs
  a fresh pak from outside the lab corpus (e.g., ServiceNow MP).

### Architectural impact

- New spec/16 documents the full appliance install + signing pipeline
  — a previously undocumented "platform mechanics" surface that
  matters for VCF-CF when generating paks for deployment.
- VCF-CF can ship unsigned paks for internal lab use without needing
  admin overrides — the path-of-least-resistance MVP is viable.
- VCF-CF-generated adapter authors do not need to plan for
  platform-side collect retry; build it into the adapter when
  needed.
- All previously-inferred Pass 1 lifecycle claims about install
  ordering are now grounded in empirical evidence; the
  `validate.py`/`preAdapters.py`/`postAdapters.py` naming inference
  from Pass 1 is corrected.

### Provenance

Request: `agents/riker/inbox/archive/2026-05-16-1500-vcf-mp-cleanroom-to-navani-tier2-spec-gap-asks.md`
Response: `agents/riker/inbox/archive/2026-05-16-1526-lab-admin-to-vcf-mp-cleanroom-response-tier2-spec-gap-asks.md`
Bundle: `workspaces/lab-admin/exports/vcf-mp-cleanroom-2026-05-16/` (8.9MB; install-logs, sig-logs, collect-logs, customgroup-metrics subdirs).

### Files committed

`spec/16-platform-install-and-signing.md` (new), `spec/00-overview.md` (index + § 16 entry), `spec/01-adapter-lifecycle.md` (Pass 23 confirmations + install cross-ref), `spec/02a-describe-xsd-canonical.md` (CustomGroupMetrics parser-class note), `analysis/pak-signing-chain.md` (Pass 23 update + cross-ref); audit-log.

---

## 2026-05-16 — RE pass 24: fold Pass 23 confirmations into handoff docs + spec/99

Polish pass — the handoff docs (spec/12 + spec/15) and the synthesis
doc (spec/99) were all written before Pass 23 arrived. Many "inferred"
/ "TBD" / "needs live confirmation" statements are now empirically
resolved and the docs should reflect that.

### Pan-out / disprove ledger

- **spec/15 point 11** (Semaphore): augmented with Pass 23 per-instance
  scope confirmation + "no platform retry on collect()" note.
- **spec/15 point 12** (signing): rewritten with empirical findings —
  "broken but functional" → "broken AND appliance doesn't enforce".
  VCF-CF guidance simplified: unsigned is the path-of-least-resistance
  for internal deployment with no admin override needed.
- **spec/15 install hooks section**: clarified that hook script
  filenames are conventional, not contractual — appliance routes by
  manifest.txt keys.
- **spec/15 Pak signing subsection**: rewritten with Pass 23 empirical
  findings + cross-ref to spec/16 (authoritative for appliance
  behavior) and analysis/pak-signing-chain.md (authoritative for
  on-disk format).
- **spec/15 § 13 Open questions**: items 6 (live install logs) and 7
  (pak signing policy) marked as RESOLVED via Pass 23 with cross-refs
  to spec/16. Item 4 (CustomGroupMetrics) updated with Pass 23
  confirmed-negative + parser-class evidence. New item 8 added
  (Cloud Proxy install pipeline cross-confirmation — out of corpus).
- **spec/15 § 14 crossref index**: added spec/16 entry; refined
  analysis/pak-signing-chain.md description.
- **spec/12 point 9** (MPB pak signing): rewritten with Pass 23
  empirical findings, similar to spec/15 point 12.
- **spec/99 "What we know less well" table**: 6 items struck through
  as RESOLVED (collect concurrency, Relationships API, Symptom/Alert
  schemas, CapacityDefinition, PowerState/Icon, Policy/PolicyMetric);
  2 new items added (install pipeline, signing-validation policy,
  CustomGroupMetrics). Mid-layer-API row updated with Pass 9
  characterization.

### Architectural impact

- Both Tier 1 (spec/12) and Tier 2 (spec/15) handoff docs are now
  internally consistent with the post-Pass-23 state of knowledge —
  no stale "needs live confirmation" hedges where empirical
  confirmation exists.
- The synthesis doc (spec/99) now accurately reflects what's actually
  unresolved (vs. the 2026-05-15 snapshot it was written against).

### Files committed

`spec/15-tier2-handoff-for-vcf-cf.md` (5 sections updated), `spec/12-mpb-handoff-for-vcf-cf.md` (point 9 rewritten), `spec/99-summary-and-vcf-cf-recommendations.md` (table refresh); audit-log.

---

## 2026-05-16 — RE pass 25: empirical grammar bounds on @@@MPB_QUOTE_BODY

Triggered by a VCF-CF question about whether `ResourceQueryHelperKt`'s
JSON-body parser supports JMESPath features (filter projections,
pipes, function calls). Surveyed all distinct `@@@MPB_QUOTE_BODY`
paths across the two compiled MPB-built paks Scott provided
(UniFi 1.0.0.7 + phpIPAM 1.0.0.11) plus their designer-side wire
format files. Reported the findings to VCF-CF; folded them back here
as a permanent reference.

### Pan-out / disprove ledger

- **🎯 RESOLVED — `@@@MPB_QUOTE_BODY` grammar bounds**: 54 distinct
  compiled paths surveyed; **100% pure dot-notation + only `data.*`
  top-level wildcard**. ZERO occurrences of brackets, predicate
  projections (`[?...]`), pipes (`|` for piping; `|` only appears in
  cross-MP aria-ops metric-key syntax, unrelated to body parsing),
  slice expressions, or function calls. The parser is Jackson
  `JsonNode`-backed (per spec/10) — NOT Jayway JsonPath, NOT JMESPath.
- **🎯 RESOLVED — designer-side `originId` collection segments**:
  exactly TWO body-navigation forms observed: `base` (single object,
  no iteration) and `data.*` (top-level array iteration). Plus
  `ARIA_OPS_METRIC` form `aria-<adapterKind>-<resourceKind>-<keyPath>`
  for cross-MP references. No nested array iteration
  (`data.*.X.*`) observed in either pak.
- **🎯 CORRECTED — `originType` enum is 4-value, not 3**:
  `ATTRIBUTE`, `METRIC`, `ARIA_OPS_METRIC`, `PARAMETER`. spec/11
  previously listed only 3 (missing `METRIC`). Corrected.
- **NEW — "iterate sibling array by predicate" is structurally
  impossible in MPB**. Idiomatic workarounds documented in spec/11
  § Grammar bounds: declare a child ResourceKind (canonical MPB
  pattern), multiple HTTP requests per filter value (if API supports
  server-side filtering), or promote to Tier 2.

### Architectural impact

- VCF-CF Tier 1 can now make confident parser-grammar promises to
  authoring users: "any field via dot-path; one-level array iteration
  via `data.*`; anything beyond → promote to Tier 2."
- Tier 1 → Tier 2 promotion-trigger list (spec/12 § 6) tightened to
  call out the specific bounds rather than the vague "JSONPath
  beyond X" hedge that was there before.
- The "iterate by predicate" pattern is the most common JSON-body
  scenario where users will be surprised — having a documented
  workaround (child ResourceKind, as UniFi's own MP exemplifies)
  matters for Tier 1 authoring UX.

### Provenance

Triggering question: VCF-CF asked about `ResourceQueryHelperKt`
grammar (specifically `radio_table[]` per-band metric on parent AP).
Empirical survey conducted via Python script over
`inputs/known_mpb/{Ubiquiti UniFi-1.0.0.7,phpIPAM-1.0.0.11}` paks
(both `.pak.1` compiled forms + `_MP_Builder_Design.json.1` designer
forms). Class-list confirmation via `unzip -l` on
`mpb_ubiquiti_unifi_adapter3.jar` — clean-room safe (no
decompilation, entry-list inspection only).

### Files committed

`spec/11-mpb-designer-wire-format.md` (new "Grammar bounds (empirical, Pass 25)" section + originType enum corrected + open-follow-up #1 marked partially resolved), `spec/12-mpb-handoff-for-vcf-cf.md` (point 7 augmented with empirical bounds + § 6 promotion-trigger JSONPath line tightened); audit-log.

---

## 2026-05-16 — RE pass 26: spec/17 VCF-CF framework design guidance

Forward-looking design synthesis triggered by Scott's question:
"how do we build a framework for VCF-CF so it's not constantly
rewriting core logic for Tier 2 MPs?" Wrote spec/17 as a self-contained
design-guide for `vcfcf-adapter-base.jar`.

### Pan-out / disprove ledger

- **NEW — 4-layer architecture recommendation**: AdapterBase (Layer 1)
  → aria-ops-core UnlicensedAdapter (Layer 2) → vcfcf-adapter-base.jar
  (Layer 3, VCF-CF's design space) → per-pak adapter (Layer 4, ~50-150
  lines). Layer 2 treated as a stable third-party dependency; never
  patched. All VCF-CF additions live at Layer 3.
- **NEW — concrete framework capability inventory**: 11 capability
  groups the framework should own (auth strategies, pagination,
  retry, typed cache, cross-MP helpers, relationship fluent builder,
  describe.xml typed builder, CollectResult plumbing, lifecycle
  defaults, action plumbing via annotations, pak packaging plugin).
  Each capability cross-referenced to the spec section that informs it.
- **NEW — MVP build order with effort estimates**: 7 phases over
  ~10-12 weeks for a team of 2-3 engineers. Skeleton + describe.xml
  builder is highest leverage; saved tier-1→tier-2 promotion
  translator for phase 7.
- **NEW — 8 design tenets**: no required boilerplate, no magic,
  escape hatches everywhere, vendor-neutral, versioned and pinnable,
  standalone testable, per-pak code is human-readable,
  single-source-of-truth describe.xml. Each phrased for code-review
  enforcement.
- **NEW — 3 open decisions documented**: Kotlin-or-Java (recommend
  Java by default), library-only-or-DSL+codegen (recommend library
  first), vendor-SDK-bundling-policy (default per-pak, revisit if
  pak size becomes painful).
- **CROSS-CUT — Pass 23 finding folded in**: the framework MUST
  provide retry/backoff since the platform doesn't retry collect()
  failures. Otherwise every adapter author reinvents it.
- **CROSS-CUT — aria-ops-core SPI decision**: per spec/15 § 1.4,
  Option B (aria-ops-core wrapper) is recommended over Option A
  (direct AdapterBase) specifically for VCF-CF's goal of minimizing
  author code. spec/17 endorses Option B.

### Architectural impact

- spec/17 is a self-contained design-guide audience-targeted at
  VCF-CF framework architects (vs spec/15 which is for adapter
  authors learning what Tier 2 IS). Different audience, complementary
  content.
- Cross-refs threaded back through every relevant spec section so
  framework architects can pull authoritative grammar/contract
  details on demand without re-reading the full investigation.
- The 11-capability inventory provides a concrete checklist for
  "what does framework-MVP feature-completeness look like" — useful
  for VCF-CF planning.

### Files committed

`spec/17-vcfcf-framework-design-guidance.md` (new), `spec/00-overview.md` (§ 17 entry added to index), `spec/15-tier2-handoff-for-vcf-cf.md` (crossref index gets spec/17 entry); audit-log.
