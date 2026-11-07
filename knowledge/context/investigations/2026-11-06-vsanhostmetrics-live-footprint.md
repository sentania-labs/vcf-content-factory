# vsanhostmetrics live footprint (3 lab instances, 2026-11-06)

Read-only recon, Suite API GET only (plus the token acquire POST). Profiles: `devel_8_18` (vcf-lab-operations-devel-8, 172.27.10.14), `devel` (vcf-lab-operations-devel, 172.27.10.12), `devel_9_1` (vcf-lab-operations-devel-91, 172.27.10.10). All numbers below are MEASURED unless marked otherwise. Self-metrics are 5-minute averages over the last 7 cycles (~35 min).

## 1. Version and pack

| Item | 8.18.7 | 9.0.2 | 9.1.1 |
|---|---|---|---|
| Ops release | Aria Operations 8.18.7 (build 25423534) | VCF Operations 9.0.2.0 (25431135) | VCF Operations 9.1.1.0 (25795063) |
| Solution `iSDK_VsanHostMetrics` version | 2.0.0 | 2.0.0 | 2.0.0 |
| Fork or upstream | fork 2.0.0 (final, not rc) | fork 2.0.0 | fork 2.0.0 |
| `vcenter_user` instance identifier | absent | absent | absent |
| Credential kind / fields | `vsan_vc_credential`: vcenter_username, vcenter_password | same | same |
| Built-in vSAN MP version | 8.18.7.25423575 | 9.0.2.0200.25430349 | 9.1.1.0100.25795118 |

Fork vs upstream is read from solution version plus identifiers (INFERRED from those, not from pak contents). Adapter kind has 70 resource kinds defined, 28 populated (incl. the adapter instance kind).

Out of scope but found: the `prod` profile (vcf-lab-operations, 172.27.8.42, VCF Ops 9.1.1.0) also has the pack at 1.4.6 (not 1.4.7), `metric_scope=all`, identifier `vcenter_user=administrator@vsphere.local`, 995 objects, 8896 metrics, 5 min, collector 4.

## 2. Adapter instance

| Setting | 8.18.7 | 9.0.2 | 9.1.1 |
|---|---|---|---|
| Name | vsan-mgmt | vsan-mgmt | vsan-mgmt |
| Collection interval (min) | 5 | 5 | 5 |
| `metric_scope` (Metrics to collect) | dashboard | dashboard | dashboard |
| `attach_to_vcenter` | true | true | true |
| vcenter_host | vcf-lab-vcenter-mgmt.int.sentania.net | same | same |
| `container_memory_limit` (MB) | 1024 | 1024 | 1024 |
| verify_certs | false | false | false |

All three point at the same physical vCenter and vSAN cluster (vcf-lab-mgmt-cl01).

## 3. Objects per resource kind

| Resource kind | 8.18.7 | 9.0.2 | 9.1.1 |
|---|---|---|---|
| VsanHostMetrics_adapter_instance | 1 | 1 | 1 |
| VsanClusterDomclient | 1 | 1 | 1 |
| VsanClusterDomcompmgr | 1 | 1 | 1 |
| VsanClusterDomowner | 1 | 1 | 1 |
| VsanClusterZdomTopStats | 1 | 1 | 1 |
| VsanClusterCapacity | 1 | 1 | 1 |
| VsanClusterEsaDedupDomclientIo | 1 | 1 | 1 |
| VsanClusterRdtLatency | 1 | 1 | 1 |
| VsanCmmdsNet | 5 | 5 | 5 |
| VsanHostDomclient | 5 | 5 | 5 |
| VsanHostDomcompmgr | 5 | 5 | 5 |
| VsanHostDomowner | 5 | 5 | 5 |
| VsanHostZdomTopStats | 5 | 5 | 5 |
| VsanHostEsaDedupDomclientIo | 5 | 5 | 5 |
| VsanHostNet | 5 | 5 | 5 |
| VsanCpu | 5 | 5 | 5 |
| VsanMemory | 5 | 5 | 5 |
| VsanRdtLatency | 5 | 5 | 5 |
| VsanTcpIp | 5 | 5 | 5 |
| VsanVnic | 5 | 5 | 5 |
| VsanVnicRdtLatency | 5 | 5 | 5 |
| VsanZdomVtx | 5 | 5 | 5 |
| VsanEsaDiskLayer | 5 | 5 | 5 |
| VsanEsaDiskScsifw | 5 | 5 | 5 |
| VsanPnic | 10 | 10 | 10 |
| VsanVirtualMachine | 37 | 30 | 37 |
| VsanVirtualDisk | 168 | 148 | 168 |
| VsanVscsi | 155 | 148 | 155 |
| **Total (GET /resources)** | **458** | **424** | **458** |
| Adapter-reported `collected_resources` | 460 | 460 | 460 |

The 2 to 36 gap between the resource listing and the adapter's own count is unexplained (cause not determined).

## 4. Adapter instance self-metrics (last 7 cycles)

| Key under the adapter instance resource | 8.18.7 | 9.0.2 | 9.1.1 |
|---|---|---|---|
| `Instance Attributes|collected_metrics` | 6184 every cycle | 6184 | 6184 |
| `Instance Attributes|observations` | n/a (not queried) | 6184 | not queried |
| `Instance Attributes|collected_resources` | 460 | 460 | 460 |
| `Instance Attributes|monitoring_resources` | not queried | 459 | not queried |
| `Instance Attributes|collected_properties` | 0 | 0 | 0 |
| `Instance Attributes|new_resources` | not queried | 0 | not queried |
| `Instance Attributes|elapsed_collect_time` (min to max) | 38675 to 115280 | 19281 to 37178 | 28717 to 44603 |
| elapsed_collect_time (mean of 7) | ~75300 | ~28400 | ~35400 |
| `docker|memory|usage` (limit 1024) | ~92 | ~87 | ~80 |
| `docker|cpu|usage_percent` | 1.7 to 2.5 | 1.7 to 2.3 | 2.2 to 3.0 |
| `docker|restarts` | 0 | 0 | 0 |

Unit of elapsed_collect_time is NOT stated by the API; values read as milliseconds (19 to 115 s per 5 min cycle) by INFERENCE. Docker memory unit also unstated (MB likely against the 1024 limit; INFERRED). Other keys present on the resource: docker availability, network eth0 rx/tx bytes, relationship_updates, property_value_changes, not_existing_resource_count, no_data_receiving_resource_count, reropted_events (not sampled). The 8.18.7 instance is the slowest. Correction 2026-11-06 (collector sizing report): the `vsan-mgmt` instance runs on each instance's Cloud Proxy (collector id 2: .13, .11, .15), not on the analytics node, so the slow one is proxy 172.27.10.15, not .14.

## 5. Instance-wide totals

The audit and cluster-management endpoints are not reachable: `/api/audit/objects`, `/api/license`, `/api/license/usage`, `/api/deployment/*`, `/api/nodes`, `/api/system/stats` all returned 404 on all three. Totals are therefore the SUM of per-adapter-instance `numberOfResourcesCollected` / `numberOfMetricsCollected` from `GET /api/adapters` (current cycle, not the KB's audit figure). `GET /api/resources` totalCount is shown as a second object count (includes objects not owned by an adapter instance count).

| Measure | 8.18.7 | 9.0.2 | 9.1.1 |
|---|---|---|---|
| Adapter instances | not counted | 25 | not counted |
| Total objects (sum of adapter instances) | 1268 | 1270 | 1213 |
| Total objects (`/api/resources` totalCount) | 1145 | 1143 | 1599 |
| Total metrics (sum of adapter instances) | 35383 | 33322 | 34511 |
| vCenter adapter, mgmt instance: objects / metrics | 91 / 8005 | 88 / 8123 | 88 / 7941 |
| vCenter adapter, all 3 instances: metrics | 20878 | 21230 | 21475 |
| vSAN built-in adapter instance: objects / metrics | 60 / 368 | 60 / 387 | 60 / 421 |
| This pack: objects / metrics | 460 / 6184 | 460 / 6184 | 460 / 6184 |
| Pack share of total metrics | 17.5% | 18.6% | 17.9% |
| Pack share of total objects (adapter sum) | 36.3% | 36.2% | 37.9% |
| Pack share of total objects (`/resources`) | 40.2% | 40.2% | 28.8% |
| Pack metrics vs mgmt vCenter adapter | 77% | 76% | 78% |
| Pack metrics vs all three vCenter adapters | 30% | 29% | 29% |

Caveat: Ops-internal self-monitoring adapters are included. "Pack adds X" is relative to the existing mgmt vCenter adapter: it nearly doubles that vCenter's metric volume per instance (6184 on top of 8005 to 8123) and adds about 5x its object count (460 vs 88 to 91).

## 6. Size of the collected vSAN cluster (vcf-lab-mgmt-cl01, ESA)

| Item | 8.18.7 | 9.0.2 | 9.1.1 | Source |
|---|---|---|---|---|
| Hosts | 5 | 5 | 5 | vSAN cluster `summary|total_number_hosts` |
| VMs on the cluster | 41 | 41 | 41 | `summary|total_number_vms` |
| VMs the pack holds as objects | 37 | 30 | 37 | pack VsanVirtualMachine |
| Virtual disks (pack objects) | 168 | 148 | 168 | VsanVirtualDisk |
| vSCSI objects (pack) | 155 | 148 | 155 | VsanVscsi |
| ESA physical disks | 5 | 5 | 5 | `summary|total_number_esa_disks` |
| Storage pools | 5 | 5 | 5 | `summary|total_number_storage_pools` |
| Datastores | 1 | 1 | 1 | `summary|total_number_datastores` |
| pNICs / vNICs | 10 / 5 | 10 / 5 | 10 / 5 | pack VsanPnic / VsanVnic |

Whole-lab context (vCenter adapter): 10 hosts, 3 clusters, VMs 126 / 110 / 126 (8.18.7 / 9.0.2 / 9.1.1). Only the mgmt cluster is collected.

## Missing or not measured

- Audit / cluster-management totals (endpoints 404); sums above substitute.
- Unit of elapsed_collect_time and docker memory (inferred).
- Cause of 460 vs 424/458 object gap, and why 9.0.2 holds fewer VM/disk objects than the others.
- Metrics per object per kind (only the adapter total 6184 measured).
- Collector node size / resource impact on the Ops side.
- Pak contents were not inspected; "fork 2.0.0" rests on the solution version and identifier shape.
- 2026-11-06: test stat keys pushed on devel (9.0.2) host vcf-lab-wld01-esx01 (`1d6dae4e-e4d4-4b52-97e2-b6e13f9484b6`), prefixes `VCFCF Test|`, `VCFCFTestNic:`, `VCFCFTestFlat|`; see `2026-11-06-suite-api-instanced-push.md`.
