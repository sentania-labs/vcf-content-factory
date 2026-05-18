# Bulk survey — remaining devel adapters

**Date**: 2026-05-15
**Method**: Extract each installed tarball; read adapter.properties + javap entry class signature head + describe.xml stats. **No deep analysis** — distinctive findings flagged inline.

| Pak | KINDKEY | Entry class | Lib jars | describe.xml lines / kinds / attrs / TraversalSpecs / ResourcePaths | Notes |
|---|---|---|---|---|---|
| AppOSUCPAdapter3 | `APPOSUCP` | `AppOSAdapter` | 116 | 5973 / 139 / 1247 / 0
0 / 0
0 | adapters_ref:  |
| DiagnosticsAdapter3 | `DiagnosticsAdapter` | `DiagnosticsAdapter` | 30 | 41 / 1 / 20 / 0
0 / 0
0 | adapters_ref:  |
| LogAssistAdapter | `LogAssistAdapter` | `LogAssistAdapter` | 12 | 16 / 1 / 0
0 / 0
0 / 0
0 | adapters_ref:  |
| ServiceDiscoveryAdapter3 | `APPLICATIONDISCOVERY` | `ServiceDiscoveryAdapter` | 115 | 522 / 5 / 0
0 / 4 / 7 | adapters_ref: APPLICATIONDISCOVERY,Container,Services,VMWARE,VirtualMachine |
| VMwareInfrastructureHealthAdapter | `VMWARE_INFRA_HEALTH` | `VMwareInfraHealthAdapter` | 81 | 985 / 53 / 52 / 0
0 / 0
0 | adapters_ref:  |
| VcfAdapter | `VcfAdapter` | `VcfAdapter` | 2 | 1974 / 4 / 84 / 0
0 / 0
0 | adapters_ref:  |
| VcfUnifiedConfigAdapter | `VCF_UNIFIED_CONFIG` | `ConfigAdapter` | 65 | 10 / 1 / 0
0 / 0
0 / 0
0 | adapters_ref:  |
| VirtualAndPhysicalSANAdapter3 | `VirtualAndPhysicalSANAdapter` | `VsanStorageAdapter` | 81 | 3472 / 16 / 366 / 0
0 / 0
0 | adapters_ref:  |
| VrAdapter | `VrAdapter` | `VrAdapter` | 86 | 591 / 6 / 0
0 / 3 / 2 | adapters_ref: Instance,VMWARE,VirtualMachine,VrAdapter |
| container_adapter | `?` | `?` | 0 | 469 / 28 / 130 / 4 / 9 | adapters_ref: Container,Tier |
| vcops_adapter3 | `vCenter Operations Adapter` | `AliveAdapter` | 12 | 3724 / 18 / 823 / 2 / 13 | adapters_ref: API,Adapter,Analytics,CaSA,Collector,Controller,Fsdb,Node,Persistence,Proxy,UI,Watchdog |

## Per-pak deeper notes

(Distinctive findings only — most paks conform to patterns already documented in spec/.)

