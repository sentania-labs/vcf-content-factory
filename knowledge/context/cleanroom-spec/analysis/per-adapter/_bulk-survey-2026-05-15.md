# Bulk survey — all remaining KEEP-C paks

**Date**: 2026-05-15
**Method**: Programmatic extraction of inner adapters.zip; read adapter.properties + describe.xml stats from each pak; identify foreign-kind references and notable patterns. **No per-pak deep analysis** — distinctive findings flagged inline.

## Master table

### From-devel adapters (installed tarballs surveyed)

Sorted by ResourceKind count (a rough proxy for declarative model size). All KEEP-C; ResourceAttribute counts only catch top-level `<ResourceAttribute key=...>` (nested in ResourceGroups are not counted, so 0 may mean "uses grouping" not "no attributes").

| Pak | KINDKEY | Entry class | Lib jars | lines / kinds / attrs / TraversalSpecs / ResourcePaths | Notes |
|---|---|---|---:|---|---|
| vmwarevi_adapter3 | `VMWARE` | `VMwareAdapter` | 72 | 13279 / 25 / 3688 / 4 / 24 | vSphere, fully analyzed pass 4 |
| AppOSUCPAdapter3 | `APPOSUCP` | `AppOSAdapter` | 116 | 5973 / **139** / 1247 / 0 / 0 | Most kinds in corpus; per-app+per-OS taxonomy; runtime-pushed topology |
| NSXTAdapter3 | `NSXTAdapter` | `NSXTAdapter` | 13 | 1958 / 41 / 848 / 0 / 0 | Analyzed pass 5 |
| vcops_adapter3 | `vCenter Operations Adapter` | `AliveAdapter` | 12 | 3724 / 18 / 823 / 1 / 13 | **Self-monitoring MP** (Operations monitoring itself); cross-refs internal components (API, Collector, Analytics, CaSA, Watchdog, etc.) |
| VirtualAndPhysicalSANAdapter3 | `VirtualAndPhysicalSANAdapter` | `VsanStorageAdapter` | 81 | 3472 / 16 / 366 / 0 / 0 | vSAN storage |
| container_adapter | (none — no adapter.properties) | — | 0 | 469 / 28 / 130 / 3 / 9 | Older container model |
| VcfAdapter | `VcfAdapter` | `VcfAdapter` | 2 | 1974 / 4 / 84 / 0 / 0 | Thin-lib (C1-light) |
| VMwareInfrastructureHealthAdapter | `VMWARE_INFRA_HEALTH` | `VMwareInfraHealthAdapter` | 81 | 985 / 53 / 52 / 0 / 0 | Heavy kind count but few attrs |
| vim | `VMWARE_INFRA_MANAGEMENT` | `ManagementAdapter` | 102 | 102 / 6 / 29 / 0 / 0 | Analyzed pass 2 |
| DiagnosticsAdapter3 | `DiagnosticsAdapter` | `DiagnosticsAdapter` | 30 | 41 / 1 / 20 / 0 / 0 | Stub |
| SupervisorAdapter | `SupervisorAdapter` | `SupervisorAdapter` | 0 | 652 / 9 / 20 / 0 / 0 | C2 sub-shape; Kubernetes (per VCFAutomation cross-ref); validated pass 4 ledger |
| LogAssistAdapter | `LogAssistAdapter` | `LogAssistAdapter` | 12 | 16 / 1 / 0 / 0 / 0 | Stub |
| ServiceDiscoveryAdapter3 | `APPLICATIONDISCOVERY` | `ServiceDiscoveryAdapter` | 115 | 522 / 5 / 0 / 3 / 2 | Cross-MP to VMWARE::VirtualMachine |
| VcfUnifiedConfigAdapter | `VCF_UNIFIED_CONFIG` | `ConfigAdapter` | 65 | 10 / 1 / 0 / 0 / 0 | Stub |
| VrAdapter | `VrAdapter` | `VrAdapter` | 86 | 591 / 6 / 0 / 2 / 2 | Cross-MP to VMWARE::VirtualMachine |
| mpb-adapter | `ManagementPackBuilderAdapter` | `MPBAdapter` | 2 | 129 / 1 / 0 / 0 / 0 | MPB runtime, analyzed pass 1 |

### From-devel paks without pre-installed tarball

| Pak | KINDKEY | Entry-class package | Lib | lines / kinds / attrs / Tr / Rp | Notes |
|---|---|---|---:|---|---|
| ManagementPackforStorageAreaNetwork | `VirtualAndPhysicalSANAdapter` | `com.vmware.adapter3` | 81 | 3472 / 16 / 366 / 0 / 0 | Same KINDKEY as VirtualAndPhysicalSANAdapter3 — DUPLICATE PAK |
| CASAdapter | `CASAdapter` | `com.vmware.adapter3` | 14 | 2285 / 12 / 146 / 10 / 32 | **Cloud Automation Services** — multi-cloud aggregator referencing `AZURE_VIRTUAL_MACHINE`, `AmazonAWSAdapter`, `Blueprint`, `CloudZone`, vSphere kinds; **most ResourcePaths in this group** |
| NetworkInsightAdapter | `NETWORK_INSIGHT` | `com.vmware.vrops.adapter3` | 35 | 1724 / 3 / 32 / 0 / 0 | Stub-ish |
| PingAdapter | `PingAdapter` | `com.vmware.adapter` | 2 | 92 / 4 / 24 / 0 / 0 | C1-light |
| ConfigurationManagement | `VCF_UNIFIED_CONFIG` | `com.vmware.adapter3.vcf` | 65 | 10 / 1 / 0 / 0 / 0 | Same KINDKEY as VcfUnifiedConfigAdapter — DUPLICATE PAK |

### Marketplace adapters

Sorted by ResourceKind count.

| Pak | KINDKEY | Entry-class package | Lib | lines / kinds / TraversalSpecs / ResourcePaths | Foreign-kind refs |
|---|---|---|---:|---|---|
| vmware-awsadapter | `AmazonAWSAdapter` | `com.vmware.adapter3` | 108 | 8426 / **118** / 3 / **282** | Self-only (cross-MP via runtime?) — most paths in corpus |
| OracleDBAdapter | `OracleDBAdapter` | `com.bluemedora.vrealize.adapt` | 28 | 1736 / 16 / 1 / 9 | `VMWARE::VirtualMachine` |
| HCXAdapter | `HCXAdapter` | `com.vmware.vcops.adapter3` | 26 | 2726 / 15 / 5 / 20 | `VMWARE::VirtualMachine`, `DistributedVirtualPortgroup`, plus HCX-specific |
| OpenManageEnterpriseAdapter | `OpenManageEnterpriseAdapter` | `com.dell.pg.vrops` | 24 | 1997 / 16 / 2 / 0 | Dell-specific (DellChassis*, DellServer*) |
| networkingdevices | `NETWORKINGDEVICES_ADAPTER` | `com.bluemedora.vrealize.adapt` | 32 | 2145 / 10 / 2 / 19 | `CiscoUcsAdapter`, `HPComputeAdapter`, vSphere kinds |
| MySQLAdapter | `MySQLAdapter` | `com.bluemedora.vrealize.adapt` | 21 | 1738 / 12 / 1 / 10 | `VMWARE`, `Linux`, `Solaris`, `HostSystem` (EpOps OS kinds) |
| SqlServerAdapter | `SqlServerAdapter` | `com.bluemedora.vrealize.adapt` | 20 | 1475 / 10 / 1 / 4 | vSphere kinds (HostSystem, etc.) — Windows-only so no OS-instance kinds |
| mongodb | `MONGODB_ADAPTER` | `com.bluemedora.vrealize.adapt` | 18 | 1947 / 11 / 1 / 17 | `VMWARE::VirtualMachine` — analyzed pass 3 |
| POSTGRESQL_ADAPTER | `POSTGRESQL_ADAPTER` | `com.bluemedora.vrealize.adapt` | 12 | 913 / 9 / 1 / 9 | `Linux`, `AIX`, `HPUX`, `HostSystem`, `Datastore` — multi-OS DB |
| DellStorageAdapter | `DellStorageAdapter` | `com.dell.storage` | 19 | 253 / 8 / 0 / 0 | Dell hardware |
| SrmAdapter | `SrmAdapter` | `com.vmware.srm` | 103 | 3485 / 11 / 4 / 0 | `VMWARE::VirtualMachine`, plus Groups/History/Instance |
| VLCRAdapter | `VLCRAdapter` | `com.vmware.vcops.adapter` | 38 | 1102 / 8 / 5 / 0 | `Center`, `CloudFileSystems`, `ProtectedSites`, `RecoveryPlan`, `RecoverySDDCs` |
| VcdaAdapter | `VcdaAdapter` | `com.vmware.vcda` | 23 | 292 / 6 / 2 / 5 | `Cloud`, `Instance`, `ORG`, `ORG_VDC`, `ORG_VDC_STORAGE_PROFILE` (vCloud Director) |
| FederatedAdapter | `FederatedAdapter` | `com.vmware.adapter` | 0 | 210 / 2 / 2 / 8 | C2 sub-shape; cross-MP to API/Adapter/Analytics/CaSA/Collector (same as vcops_adapter3) — federation across Operations instances |
| vcf_hcx | `vcf_hcx` | `com.vmware.adapter` | 12 | 209 / 6 / 0 / 0 | HCX modern variant |
| OrchestratorAdapter | `OrchestratorAdapter` | `com.vmware.adapter3` | 12 | 1077 / 4 / 0 / 0 | vRO |
| AviAdapter | `AviAdapter` | `com.vmware.adapter` | 45 | 121 / 3 / 0 / 0 | Avi load balancer |
| KubernetesAdapter | `KubernetesAdapter` | `com.vmware.vcops.adapter` | 35 | 1292 / 2 / 0 / 0 | K8s (older variant; newer is SupervisorAdapter) |
| NSXAdvancedLBAdapter | `NSXAdvancedLBAdapter` | `com.vmware` | 5 | 577 / 4 / 0 / 0 | NSX ALB |
| DiagnosticsAdapter (market) | `DiagnosticsAdapter` | `com.vmware.adapter3` | 30 | 41 / 1 / 0 / 0 | Stub (same as devel DiagnosticsAdapter3) |
| SERVICENOW_ADAPTER | `SERVICENOW_ADAPTER` | `com.bluemedora` | 38 | 446 / 3 / 0 / 0 | BlueMedora |

## Cross-MP attachment targets — corpus-wide tally

How many paks reference each foreign adapter kind:

- **`VMWARE::VirtualMachine`** — 14 paks reference (most-referenced foreign kind in corpus)
  - vSphere itself (self-refs, 12 internal mentions)
  - Aggregators: ServiceDiscoveryAdapter (10), CASAdapter (10), VCFAutomation (3)
  - Networking/HCI: networkingdevices (8), HCX (8)
  - Databases: mongodb (7), MS SQL (4), postgresql (2), mysql (2), oracle (1)
  - Other: srmAdapter (2), OpenManageEnterpriseAdapter (2), VrAdapter (2)
- **`SupervisorAdapter::*` (K8s kinds)** — VCFAutomation (multiple)
- **`STORAGE_DEVICES::Mount`** — vSphere only (referenced but not satisfied in this corpus — STORAGE_DEVICES adapter not present)
- **EpOps OS kinds** (`Linux`, `AIX`, `HPUX`, `Solaris`, `HostSystem`) — database adapters: mysql, postgresql

## Patterns confirmed at scale

### 1. Cross-MP to VMWARE::VirtualMachine is the canonical pattern

14 paks declare it. **Any adapter that monitors a system whose unit of deployment is "a VM" attaches to VMWARE::VirtualMachine.** This is THE most important foreign-attachment use case.

VCF-CF generator must make this first-class: design language should let users say "this resource attaches to a VM" without writing the join logic by hand.

### 2. BlueMedora's `com.bluemedora.vrealize.adapter.*` is the dominant marketplace framework

Adapters in this package: mongodb, mysql, postgresql, oracle, networkingdevices, servicenow, microsoftsqlserver. All BlueMedora-origin, all built atop `aria-ops-core` (pass-3 finding). This is the de-facto Track C abstraction framework for marketplace adapters.

### 3. Empty-stub adapters are common

LogAssistAdapter, VcfUnifiedConfigAdapter, DiagnosticsAdapter*, mpb-adapter, NSXAdvancedLBAdapter, AviAdapter, VLCRAdapter, OrchestratorAdapter, KubernetesAdapter, vcf_hcx, SERVICENOW_ADAPTER, DellStorageAdapter — all have minimal describe.xml. They register an adapter kind but rely on:
- Runtime-pushed dynamic metrics (`isDynamicMetricsAllowed`), OR
- Top-level kind declaration only (resources accessed via foreign-kind cross-MP refs), OR
- Are framework adapters where the kind is the entry point for something else

### 4. AmazonAWSAdapter is the most-declarative adapter

118 ResourceKinds, **282 ResourcePaths**, 8426-line describe.xml. AWS has a huge object catalog (EC2, S3, RDS, ELB, VPC, IAM, etc.). Most TraversalSpec-heavy adapter in the corpus.

### 5. Adapters can be DUPLICATE PAKS for the same KINDKEY

Two paks observed sharing a KINDKEY:
- `ManagementPackforStorageAreaNetwork` AND `VirtualAndPhysicalSANAdapter3` both = `VirtualAndPhysicalSANAdapter`
- `ConfigurationManagement` AND `VcfUnifiedConfigAdapter` both = `VCF_UNIFIED_CONFIG`

These appear to be packaging-only duplicates (different distribution channels for the same adapter kind). The platform presumably refuses to install both.

### 6. Three Operations-internal adapters exist

- **`vcops_adapter3`** (KINDKEY `vCenter Operations Adapter`) — the self-monitoring MP. References internal components.
- **`vmware-mpforaggregator`** (KINDKEY `FederatedAdapter`) — federation across Operations instances. Also references the same internal components.
- **`vim`** (KINDKEY `VMWARE_INFRA_MANAGEMENT`) — VCF integration management.

These are the "Operations monitors itself" / "Operations talks to other Operations" / "Operations integrates with VCF" trio. Useful evidence that the platform expects platform-self-monitoring as a first-class concept.

### 7. AppOSUCPAdapter3 is the modern "application-on-OS" framework

139 ResourceKinds covering: AD/ActiveMQ/Apache/Cassandra/PostgreSQL/MySQL/MS SQL/Redis/RabbitMQ/IIS/JBoss/Nginx/Tomcat/etc. **Per-application kind families** (e.g., `activedirectory_database`, `activedirectory_dns`, `activedirectory_security` for AD; `apache_Application`, `apache_*` for Apache).

Has 0 declared TraversalSpecs — uses **runtime-pushed relationships** (NSX-style). This is THE adapter that attaches application-level metrics to underlying OSes (and through them, to vSphere VMs). Modern replacement for EpOps.

For VCF-CF: AppOSUCP is the reference architecture for any "monitor-things-inside-the-OS" use case.
