# vSAN adapter inventory (lab, 2026-11-06)

Read-only recon, VCF Operations 9.0.2.0 (build 25431135). Source: Suite API GET only. Purpose: stitch/skip analysis for content/sdk-adapters/vsanhostmetrics.

## 1. Adapter kind and resource kinds

Adapter kind `VirtualAndPhysicalSANAdapter` (name "vSAN Adapter"), one adapter instance `vcf-lab-mgmt - vSAN` (vCenter vcf-lab-vcenter-mgmt). The pack is already installed on the lab as adapter kind `VsanHostMetrics`, instance `vsan-mgmt`, 424 objects.

| Resource kind key | Display name | Objects |
|---|---|---|
| CacheDisk | Cache Disk | 0 |
| CapacityDisk | Capacity Disk | 0 |
| VirtualAndPhysicalSANAdapter Instance | vSAN Adapter Instance | 1 |
| VirtualSANDCCluster | vSAN Cluster | 1 |
| VirtualSANDiskGroup | vSAN Disk Group | 0 |
| Vsan2Disk | vSAN ESA Disk | 5 |
| VirtualSANFaultDomain | vSAN Fault Domain | 0 |
| FileServer | vSAN File Server | 0 |
| FileShare | vSAN File Share | 0 |
| StoragePool | vSAN Storage Pool | 5 |
| VirtualSANWitnessHost | vSAN Witness Host | 0 |
| vSAN World | vSAN World | 1 |

Notes: the lab is vSAN ESA (mgmt cluster vcf-lab-mgmt-cl01, 5 hosts), so OSA kinds (Cache Disk, Capacity Disk, Disk Group) have 0 objects and ESA kinds (vSAN ESA Disk, Storage Pool, 1 per host) are populated. There is no "vSAN Datastore" kind: the vSAN datastore is a VMWARE `Datastore` (e.g. vcf-lab-mgmt-cl01-vsan, DataStorePath `VSAN:90d067b8007711f1-af60000c297e270a`). Fault Domain, Witness, File Server and File Share are defined but empty here.

## 2. Stat keys per kind (counts; raw lists in the appendix)

| Kind (object sampled) | Total keys | Excluding generic (System Attributes, badge, OnlineCapacityAnalytics, diskspace|, summary alert) |
|---|---|---|
| vSAN Cluster | 104 | 80 |
| vSAN ESA Disk | 48 | 27 |
| vSAN Storage Pool | 33 | 10 |
| vSAN World | 78 | 62 |
| vSAN Adapter Instance | 42 | 27 |
| HostSystem (union of 3 hosts) | 412 | 361 |
| HostSystem host 1 | 361 | 318 |
| Datastore (1) | 78 | 42 |
| VirtualMachine (1) | 279 | 241 |

Key observation: built-in vSAN cluster performance is `vsan|performance|*` (11 metrics: congestion, iops, latency, oio, throughput, io size). ESA disk performance is `vSAN|Performance|*` (note different case). Storage Pool carries `DiskI/O|*`. No built-in key exposes DOM owner/client/compmgr, RDT, ZDOM, pNIC/vNIC, TCP/IP, CMMDS, per-VM vSAN, or virtual disk NIOPS metrics. The host `HostSystem` object has no `vsan` keys in its stat key list.

## 3. Pack scope vs built-in (name-based, PROBABLE overlap only)

Rule: "suffix" = last key segment equals the pack metric name (case-insensitive, punctuation ignored); "tokens" = all camelCase tokens of the pack name appear in a built-in key (tput=throughput, lat=latency), needs 2+ tokens. Built-in pool per pack kind: cluster-type kinds -> vSAN Cluster + vSAN World keys; disk kinds -> ESA Disk + Storage Pool keys; Vscsi/VirtualDisk/VM -> VM keys; the rest -> union of HostSystem keys. Token matches are heuristics; none was verified for semantic equality (units, aggregation).

| Pack kind | In scope | Pool | Suffix | Tokens | Examples |
|---|---|---|---|---|---|
| VsanCacheDisk | 8 | disk | 8 | 0 | iopsDevRead ~ vSAN|Performance|iopsDevRead; iopsDevWrite ~ vSAN|Performance|iopsDevWrite |
| VsanCapacityDisk | 13 | disk | 8 | 4 | iopsDevRead ~ vSAN|Performance|iopsDevRead; iopsDevWrite ~ vSAN|Performance|iopsDevWrite |
| VsanClusterCapacity | 5 | cluster | 0 | 1 | dedupRatio ~ vsan|dedupCompressOverview|ratio |
| VsanClusterDomclient | 11 | cluster | 8 | 0 | congestion ~ vsan|performance|congestion; iopsRead ~ vsan|performance|iopsRead |
| VsanClusterDomcompmgr | 12 | cluster | 6 | 0 | congestion ~ vsan|performance|congestion; iopsRead ~ vsan|performance|iopsRead |
| VsanClusterDomowner | 23 | cluster | 6 | 2 | congestion ~ vsan|performance|congestion; iopsRead ~ vsan|performance|iopsRead |
| VsanClusterEsaDedupDomclientIo | 24 | cluster | 0 | 0 | - |
| VsanClusterRdtLatency | 9 | cluster | 0 | 2 | avgLatency ~ vsan|performance|latencyAvgRead; maxLatency ~ kpi|capacityDiskLatency_max |
| VsanClusterZdomTopStats | 7 | cluster | 7 | 0 | iopsRead ~ vsan|performance|iopsRead; iopsWrite ~ vsan|performance|iopsWrite |
| VsanCmmdsNet | 10 | host | 0 | 0 | - |
| VsanCpu | 7 | host | 0 | 1 | readyPct ~ Performance Risk|Contention|P90 vCPU Ready Pct |
| VsanDirectCluster | 8 | cluster | 0 | 0 | - |
| VsanDirectHost | 8 | host | 0 | 0 | - |
| VsanEsaDiskLayer | 5 | disk | 4 | 0 | avgLatReadCapacity ~ vSAN|Performance|avgLatReadCapacity; avgLatWriteCapacity ~ vSAN|Performance|avgLatWriteCapacity |
| VsanEsaDiskScsifw | 5 | disk | 4 | 0 | latencyDevDAvg ~ vSAN|Performance|latencyDevDAvg; latencyDevGAvg ~ vSAN|Performance|latencyDevGAvg |
| VsanFileService | 8 | cluster | 0 | 2 | readLatency ~ vsan|performance|latencyAvgRead; writeLatency ~ vsan|performance|latencyAvgWrite |
| VsanHostDomclient | 6 | host | 0 | 2 | latencyAvgRead ~ datastore:Aggregate of all instances|totalReadLatency_average; latencyAvgWrite ~ datastore:Aggregate of all instances|totalWriteLatency_average |
| VsanHostDomcompmgr | 16 | host | 0 | 2 | latencyAvgRead ~ datastore:Aggregate of all instances|totalReadLatency_average; latencyAvgWrite ~ datastore:Aggregate of all instances|totalWriteLatency_average |
| VsanHostDomowner | 38 | host | 0 | 2 | latencyAvgRead ~ datastore:Aggregate of all instances|totalReadLatency_average; latencyAvgWrite ~ datastore:Aggregate of all instances|totalWriteLatency_average |
| VsanHostEsaDedupDomclientIo | 24 | host | 0 | 0 | - |
| VsanHostNet | 8 | host | 0 | 2 | rxPackets ~ net|packetsRx_summation; txPackets ~ net:Aggregate of all instances|packetsTxPerSec |
| VsanHostZdomTopStats | 11 | host | 0 | 2 | latencyAvgRead ~ datastore:Aggregate of all instances|totalReadLatency_average; latencyAvgWrite ~ datastore:Aggregate of all instances|totalWriteLatency_average |
| VsanIoinsight | 82 | cluster | 4 | 2 | iopsRead ~ vsan|performance|iopsRead; iopsTotal ~ vsan|performance|total_iops |
| VsanMemory | 12 | host | 0 | 0 | - |
| VsanPnic | 17 | host | 0 | 0 | - |
| VsanRdtLatency | 11 | host | 0 | 2 | avgLatency ~ datastore:Aggregate of all instances|totalLatency_average; maxLatency ~ datastore|totalLatency_max |
| VsanTcpIp | 12 | host | 0 | 0 | - |
| VsanVirtualDisk | 7 | vm | 0 | 0 | - |
| VsanVirtualMachine | 6 | vm | 0 | 2 | latencyRead ~ datastore:Aggregate of all instances|totalReadLatency_average; latencyWrite ~ datastore:Aggregate of all instances|totalWriteLatency_average |
| VsanVnic | 10 | host | 0 | 2 | rxPackets ~ net|packetsRx_summation; txPackets ~ net:Aggregate of all instances|packetsTxPerSec |
| VsanVnicRdtLatency | 10 | host | 0 | 2 | avgLatency ~ datastore:Aggregate of all instances|totalLatency_average; maxLatency ~ datastore|totalLatency_max |
| VsanVscsi | 8 | vm | 0 | 2 | latencyRead ~ datastore:Aggregate of all instances|totalReadLatency_average; latencyWrite ~ datastore:Aggregate of all instances|totalWriteLatency_average |
| VsanZdomVtx | 10 | host | 0 | 0 | - |
| TOTAL | 451 | | 55 | 34 | |

Caveat: the pack kinds in COVERED total 33; the lab has live objects for 27 pack kinds (no VsanCacheDisk, VsanCapacityDisk, VsanDirectCluster, VsanDirectHost, VsanFileService, VsanIoinsight; those are OSA, vSAN Max/direct, file service, and IO Insight cases not present here).

Reading the table: strong overlap candidates are the CacheDisk/CapacityDisk/EsaDisk* rows (built-in ESA disk keys vSAN|Performance|* use the same metric names, e.g. iopsDevRead, latencyDevDAvg) and the cluster-level vsan|performance|* names. Cluster* suffix matches (congestion, iopsRead, latencyAvgRead) are name coincidences at a different layer: the pack gives DOM client/owner/compmgr per-layer values, the built-in gives one cluster aggregate, so they are NOT replacements. Host/VM/Vscsi token matches are weak (they hit datastore latency and net packets in the VMWARE adapter) and should be treated as noise unless checked.

## 4. Identifier scheme (built-in)

| Kind | Identifier (unique?) | Example value |
|---|---|---|
| VirtualSANDCCluster | ID (unique) | `vSAN Cluster(domain-c6004, vcf-lab-mgmt-dc01)` |
| VirtualSANDCCluster | Name (not unique) | `vSAN Cluster()` |
| VirtualSANDCCluster | VCID (unique) | `4ff53df1-d47a-4fb9-b6f8-b96c6ce8ae8e` |
| Vsan2Disk | ID (unique) | `05be46e901b9f278af34ebf2f7613991bcc95439a94f393fc82e68ce0487bb9351` |
| Vsan2Disk | Name (not unique) | `_T10.NVME____SAMSUNG_SSD_990_PRO_4TB_________________56F0A0514C382500` |
| Vsan2Disk | VCID (unique) | `4ff53df1-d47a-4fb9-b6f8-b96c6ce8ae8e` |
| Vsan2Disk | VSANID (not unique) | `52850722-bc18-61ea-8400-190ec367ac70` |
| StoragePool | ID (unique) | `host-6015` |
| StoragePool | Name (not unique) | `Storage Pool ()` |
| StoragePool | VCID (unique) | `4ff53df1-d47a-4fb9-b6f8-b96c6ce8ae8e` |
| vSAN World | none | (no identifiers; singleton, name `vSAN World`) |
| Adapter Instance | VCID | `4ff53df1-d47a-4fb9-b6f8-b96c6ce8ae8e` |
| Adapter Instance | VCServer | `vcf-lab-vcenter-mgmt.int.sentania.net` |

Notes: cluster ID embeds the vCenter MoRef and DC name: `vSAN Cluster(<domain-cNNN>, <datacenter>)`; display name is blank-ish `vSAN Cluster()`. ESA disk ID is a 66-char hex hash (not the vSAN disk UUID); the vSAN disk UUID is the non-unique `VSANID` identifier (e.g. `52850722-bc18-61ea-8400-190ec367ac70`), which equals the pack `VsanEsaDiskLayer.disk_uuid` for the same disk. Storage Pool ID is the HostSystem MoRef (`host-6015`) and name is blank (`Storage Pool ()`), 5 with the same name. VCID is the vCenter instance UUID (same as HostSystem `VMEntityVCID`).

How the pack currently identifies objects (from the live VsanHostMetrics resources):

| Pack kind | Identifiers | Example |
|---|---|---|
| VsanClusterDomowner | cluster_uuid | 90d067b8-0077-11f1-af60-000c297e270a |
| VsanHostDomowner | host_uuid | 69fd149d-c1b8-aae3-bcb2-3805253936dc |
| VsanEsaDiskLayer | disk_uuid | 52850722-bc18-61ea-8400-190ec367ac70 |
| VsanPnic | host_uuid, vmnic | 6a8859db-a52e-c523-e78c-3805253a02fc, vmnic1 |
| VsanVirtualMachine | vm_uuid | e8f31d49-d532-4b17-9ef1-7cc33efa33dc |
| VsanVirtualDisk | vdisk_uuid | a47e8269-1970-fbb7-4be9-38052534ded0/vcf-lab-vcenter-wld01_7.vmdk |

Pack cluster_uuid `90d067b8-0077-11f1-af60-000c297e270a` is the vSAN cluster UUID, same string as in the VMWARE vSAN datastore path (`VSAN:90d067b8007711f1-af60000c297e270a`). The built-in vSAN Cluster object does not expose it as an identifier. Stitching to a VMWARE `ClusterComputeResource` needs the MoRef (`domain-c6004`, identifier `VMEntityObjectID` + `VMEntityVCID`), which is in the built-in cluster ID string. Stitching hosts: pack host_uuid (e.g. `698054c1-...`) is the ESXi hardware/vSAN node UUID, not the MoRef; matching to HostSystem needs a name or the Storage Pool `host-NNNN` ID (INFERRED path, not tested).

## 5. Lab reference

| Item | Value |
|---|---|
| HostSystem objects | 10 (3 vCenters: mgmt 5 hosts + wld01 + wld02) |
| VirtualMachine objects | 110 |
| ClusterComputeResource | 3 |
| Datastore | 12 |
| Ops version | VCF Operations 9.0.2.0 build 25431135 |
| Ops nodes | 1 collector/cluster node (172.27.10.12) |
| Ops node size | UNKNOWN. API gap: no read endpoint reachable (the node resource reports config|numCpu 2.0, numOfvCpus 2.0, which looks wrong for a 9.x node; casa API returns 403). Not asserted. |
| Pack objects on lab | 424 across 27 kinds plus the adapter instance (148 Vscsi, 148 VirtualDisk, 30 VM, 10 Pnic, rest 1 to 5) |

## Appendix A: raw stat keys

### vSAN Cluster (vSAN Cluster()) (104)

| Key |
|---|
| OnlineCapacityAnalytics|capacityRemainingPercentage |
| OnlineCapacityAnalytics|diskspace|capacityRemaining |
| OnlineCapacityAnalytics|diskspace|recommendedSize |
| OnlineCapacityAnalytics|diskspace|recommendedTotalSize |
| OnlineCapacityAnalytics|diskspace|timeRemaining |
| OnlineCapacityAnalytics|timeRemaining |
| System Attributes|alert_count_critical |
| System Attributes|alert_count_immediate |
| System Attributes|alert_count_info |
| System Attributes|alert_count_warning |
| System Attributes|all_metrics |
| System Attributes|availability |
| System Attributes|child_all_metrics |
| System Attributes|health |
| System Attributes|self_alert_count |
| System Attributes|total_alarms |
| System Attributes|total_alert_count |
| badge|compliance |
| badge|efficiency |
| badge|health |
| badge|risk |
| badge|workload |
| diskspace|workload |
| kpi|capacityDiskIops_max |
| kpi|capacityDiskLatency_max |
| kpi|diskGroupCacheLatency_max |
| kpi|diskGroupCapacityFree_min |
| kpi|diskGroupCongestionAbove60_count |
| kpi|diskGroupCongestion_max |
| kpi|diskGroupErrors_sum |
| kpi|diskGroupReadCacheHitRate_min |
| kpi|diskGroupWriteBufferFree_min |
| kpi|esaDiskErrors_sum |
| kpi|esaDiskIops_max |
| kpi|esaDiskLatency_max |
| kpi|hostVMKernelPacketDropped_sum |
| kpi|storagePoolCapacityFree_min |
| summary|cluster_capacity_remaining |
| summary|cluster_capacity_remaining_percent |
| summary|cpu_workload |
| summary|max_vsan_cpu_ready |
| summary|mem_workload |
| summary|total_alert_count |
| summary|total_number_client_vms |
| summary|total_number_datastores |
| summary|total_number_esa_disks |
| summary|total_number_hosts |
| summary|total_number_storage_pools |
| summary|total_number_vms |
| summary|total_vsan_cpu_used |
| summary|worst_vm_disk_latency |
| vsan|WhatIf:Management Storage Policy - Large|effectiveFreeSpace |
| vsan|WhatIf:Management Storage Policy - Regular|effectiveFreeSpace |
| vsan|WhatIf:Management Storage Policy - Single Node|effectiveFreeSpace |
| vsan|WhatIf:Management Storage Policy - Stretched ESA|effectiveFreeSpace |
| vsan|WhatIf:Management Storage Policy - Stretched Lite|effectiveFreeSpace |
| vsan|WhatIf:Management Storage Policy - Stretched|effectiveFreeSpace |
| vsan|WhatIf:Management Storage policy - Encryption|effectiveFreeSpace |
| vsan|WhatIf:Management Storage policy - Thin|effectiveFreeSpace |
| vsan|WhatIf:vSAN Default Storage Policy|effectiveFreeSpace |
| vsan|WhatIf:vSAN ESA Auto RAID Policy|effectiveFreeSpace |
| vsan|WhatIf:vSAN ESA Default Policy - RAID5|effectiveFreeSpace |
| vsan|WhatIf:vSAN ESA Default Policy - RAID6|effectiveFreeSpace |
| vsan|WhatIf:vSAN Object Store Policy|effectiveFreeSpace |
| vsan|WhatIf:vSAN Stretched ESA Default Policy - RAID5|effectiveFreeSpace |
| vsan|WhatIf:vSAN Stretched ESA Default Policy - RAID6|effectiveFreeSpace |
| vsan|WhatIf:vSAN Stretched ESA Default Policy|effectiveFreeSpace |
| vsan|WhatIf:vcf-lab-mgmt-cl01 - Optimal Datastore Default Policy - AutoRAID|effectiveFreeSpace |
| vsan|WhatIf:vcf-lab-mgmt-cl01 - Optimal Datastore Default Policy - RAID1|effectiveFreeSpace |
| vsan|WhatIf:vcf-lab-mgmt-cl01 - Optimal Datastore Default Policy - RAID5|effectiveFreeSpace |
| vsan|WhatIfDefaultPolicy|effectiveFreeSpaceOfDefaultPolicy |
| vsan|componentLimit|componentLimitUsed |
| vsan|componentLimit|totalComponentLimit |
| vsan|componentLimit|usedComponentLimit |
| vsan|dedupCompressOverview|ratio |
| vsan|dedupCompressOverview|savings |
| vsan|dedupCompressOverview|usedAfter |
| vsan|dedupCompressOverview|usedBefore |
| vsan|diskSpace|diskSpaceUsed |
| vsan|diskSpace|totalDiskSpace |
| vsan|diskSpace|totalRemoteDatastoreDiskSpace |
| vsan|diskSpace|usableCapacity |
| vsan|diskSpace|usedDiskSpace |
| vsan|diskSpace|usedRemoteDatastoreDiskSpace |
| vsan|health|score |
| vsan|performance|congestion |
| vsan|performance|iopsRead |
| vsan|performance|iopsWrite |
| vsan|performance|latencyAvgRead |
| vsan|performance|latencyAvgWrite |
| vsan|performance|oio |
| vsan|performance|readiosize |
| vsan|performance|throughputRead |
| vsan|performance|throughputWrite |
| vsan|performance|total_iops |
| vsan|performance|total_latency |
| vsan|performance|total_throughput |
| vsan|performance|totaliosize |
| vsan|performance|writeiosize |
| vsan|resync|bytesLeftToResync |
| vsan|resync|resyncingObjects |
| vsan|slackSpace|hostRebuildCapacity |
| vsan|slackSpace|minSpaceRequiredForVsanOp |
| vsan|slackSpace|transientSpace |

### vSAN ESA Disk (48)

| Key |
|---|
| OnlineCapacityAnalytics|capacityRemainingPercentage |
| OnlineCapacityAnalytics|diskspace|capacityRemaining |
| OnlineCapacityAnalytics|diskspace|recommendedSize |
| OnlineCapacityAnalytics|diskspace|timeRemaining |
| OnlineCapacityAnalytics|timeRemaining |
| PerformanceMetrics|busResets |
| PerformanceMetrics|commandsAborted |
| ScsiSmartStatistics|DriveTemperature.Value |
| ScsiSmartStatistics|HealthStatus.Value |
| ScsiSmartStatistics|PowerCycleCount.Value |
| ScsiSmartStatistics|PoweronHours.Value |
| ScsiSmartStatistics|ReadSectorsTOTCount.Value |
| ScsiSmartStatistics|ReallocatedSectorCount.Value |
| System Attributes|alert_count_critical |
| System Attributes|alert_count_immediate |
| System Attributes|alert_count_info |
| System Attributes|alert_count_warning |
| System Attributes|all_metrics |
| System Attributes|availability |
| System Attributes|health |
| System Attributes|self_alert_count |
| System Attributes|total_alarms |
| System Attributes|total_alert_count |
| badge|compliance |
| badge|efficiency |
| badge|health |
| badge|risk |
| badge|workload |
| diskspace|workload |
| vSAN|Health|Capacity|TotalDiskCapacity |
| vSAN|Health|Capacity|UsedDiskCapacity |
| vSAN|Health|Capacity|UsedDiskCapacityPercent |
| vSAN|Health|Congestion Health|Congestion Value |
| vSAN|Performance|avgLatReadCapacity |
| vSAN|Performance|avgLatWriteCapacity |
| vSAN|Performance|iopsDevRead |
| vSAN|Performance|iopsDevWrite |
| vSAN|Performance|iopsReadCapacity |
| vSAN|Performance|iopsTotal |
| vSAN|Performance|iopsWriteCapacity |
| vSAN|Performance|latencyDevDAvg |
| vSAN|Performance|latencyDevGAvg |
| vSAN|Performance|latencyDevRead |
| vSAN|Performance|latencyDevWrite |
| vSAN|Performance|throughputDevRead |
| vSAN|Performance|throughputDevWrite |
| vSAN|Performance|tputReadCapacity |
| vSAN|Performance|tputWriteCapacity |

### vSAN Storage Pool (33)

| Key |
|---|
| DiskI/O|busResets |
| DiskI/O|commandsAborted |
| DiskI/O|iopsDevRead |
| DiskI/O|iopsDevWrite |
| DiskI/O|latencyDevRead |
| DiskI/O|latencyDevWrite |
| DiskI/O|throughputDevRead |
| DiskI/O|throughputDevWrite |
| DiskSpace|capacityUsage |
| DiskSpace|capacityUsed |
| OnlineCapacityAnalytics|capacityRemainingPercentage |
| OnlineCapacityAnalytics|diskspace|capacityRemaining |
| OnlineCapacityAnalytics|diskspace|recommendedSize |
| OnlineCapacityAnalytics|diskspace|timeRemaining |
| OnlineCapacityAnalytics|timeRemaining |
| System Attributes|alert_count_critical |
| System Attributes|alert_count_immediate |
| System Attributes|alert_count_info |
| System Attributes|alert_count_warning |
| System Attributes|all_metrics |
| System Attributes|availability |
| System Attributes|child_all_metrics |
| System Attributes|health |
| System Attributes|self_alert_count |
| System Attributes|total_alarms |
| System Attributes|total_alert_count |
| badge|compliance |
| badge|efficiency |
| badge|health |
| badge|risk |
| badge|workload |
| diskspace|capacity |
| diskspace|workload |

### vSAN World (78)

| Key |
|---|
| Compliance|Critical|totalCount |
| Compliance|Immediate|totalCount |
| Compliance|Normal|totalCount |
| Compliance|Unknown|totalCount |
| Compliance|Warning|totalCount |
| Efficiency|Critical|totalCount |
| Efficiency|Immediate|totalCount |
| Efficiency|Normal|totalCount |
| Efficiency|Unknown|totalCount |
| Efficiency|Warning|totalCount |
| Efficiency|populationAverage |
| Health|Critical|totalCount |
| Health|Immediate|totalCount |
| Health|Normal|totalCount |
| Health|Unknown|totalCount |
| Health|Warning|totalCount |
| Health|populationAverage |
| ObjectCountMetricGroup:ClusterComputeResource|count |
| ObjectCountMetricGroup:Datastore|count |
| ObjectCountMetricGroup:HostSystem|count |
| ObjectCountMetricGroup:StoragePool|count |
| ObjectCountMetricGroup:VirtualAndPhysicalSANAdapter Instance|count |
| ObjectCountMetricGroup:VirtualMachine|count |
| ObjectCountMetricGroup:VirtualSANDCCluster|count |
| ObjectCountMetricGroup:Vsan2Disk|count |
| Risk|Critical|totalCount |
| Risk|Immediate|totalCount |
| Risk|Normal|totalCount |
| Risk|Unknown|totalCount |
| Risk|Warning|totalCount |
| Risk|populationAverage |
| System Attributes|alert_count_critical |
| System Attributes|alert_count_immediate |
| System Attributes|alert_count_info |
| System Attributes|alert_count_warning |
| System Attributes|all_metrics |
| System Attributes|availability |
| System Attributes|child_all_metrics |
| System Attributes|health |
| System Attributes|self_alert_count |
| System Attributes|total_alarms |
| System Attributes|total_alert_count |
| TimeRemainingCapIQ|Critical|totalCount |
| TimeRemainingCapIQ|Immediate|totalCount |
| TimeRemainingCapIQ|Normal|totalCount |
| TimeRemainingCapIQ|Unknown|totalCount |
| TimeRemainingCapIQ|Warning|totalCount |
| Workload|Critical|totalCount |
| Workload|Immediate|totalCount |
| Workload|Normal|totalCount |
| Workload|Unknown|totalCount |
| Workload|Warning|totalCount |
| badge|compliance |
| badge|efficiency |
| badge|health |
| badge|risk |
| badge|workload |
| populationGroup|populationTotalCount |
| summary|compute_cluster_count |
| summary|esa_cluster_count |
| summary|max_cluster_count |
| summary|osa_cluster_count |
| summary|remaining_capacity |
| summary|remaining_capacity_percent |
| summary|total_cluster_count |
| summary|total_datastore_count |
| summary|total_dedup_compress_savings |
| summary|total_iops |
| summary|total_latency |
| summary|total_number_cache_disks |
| summary|total_number_capacity_disks |
| summary|total_number_diskgroups |
| summary|total_number_esa_disks |
| summary|total_number_hosts |
| summary|total_number_storage_pools |
| summary|total_number_vms |
| summary|vsan_diskspace_capacity |
| summary|vsan_diskspace_capacity_used |

### vSAN Adapter Instance (42)

| Key |
|---|
| Instance Attributes|collected_metrics |
| Instance Attributes|collected_properties |
| Instance Attributes|collected_resources |
| Instance Attributes|elapsed_collect_time |
| Instance Attributes|monitoring_resources |
| Instance Attributes|new_resources |
| Instance Attributes|no_data_receiving_resource_count |
| Instance Attributes|not_existing_resource_count |
| Instance Attributes|observations |
| Instance Attributes|property_value_changes |
| Instance Attributes|relationship_updates |
| Instance Attributes|reropted_events |
| System Attributes|alert_count_critical |
| System Attributes|alert_count_immediate |
| System Attributes|alert_count_info |
| System Attributes|alert_count_warning |
| System Attributes|all_metrics |
| System Attributes|availability |
| System Attributes|child_all_metrics |
| System Attributes|health |
| System Attributes|self_alert_count |
| System Attributes|total_alarms |
| System Attributes|total_alert_count |
| badge|compliance |
| badge|efficiency |
| badge|health |
| badge|risk |
| summary|compute_cluster_count |
| summary|esa_cluster_count |
| summary|max_cluster_count |
| summary|osa_cluster_count |
| summary|total_cluster_count |
| summary|total_datastore_count |
| summary|total_iops |
| summary|total_number_cache_disks |
| summary|total_number_capacity_disks |
| summary|total_number_diskgroups |
| summary|total_number_esa_disks |
| summary|total_number_hosts |
| summary|total_number_storage_pools |
| summary|total_number_vms |
| summary|total_throughput |

### HostSystem (non-generic keys, union of 3 hosts)

361 keys, listed as groups with counts (full list retrievable via /api/resources/{id}/statkeys).

| Group | Keys |
|---|---|
| Performance Risk|CPU | 4 |
| Performance Risk|Composite | 1 |
| Performance Risk|Contention | 7 |
| Performance Risk|Memory | 4 |
| Performance Risk|Network | 1 |
| Performance Risk|Storage | 2 |
| VCF Content Factory vSphere Storage Paths | 12 |
| VCF-CF Compliance | 9 |
| VCF-CF Compliance|VMware_SCG_9.0 | 49 |
| VCF-CF Compliance|VMware_SCG_9.1 | 52 |
| VCF-CF Compliance|esx.account-lockout-duration | 1 |
| VCF-CF Compliance|esx.account-lockout-max-attempts | 1 |
| VCF-CF Compliance|esx.account-password-history | 1 |
| VCF-CF Compliance|esx.ad-admin-group-autoadd | 1 |
| VCF-CF Compliance|esx.ad-admin-validate-interval | 1 |
| VCF-CF Compliance|esx.api-soap-timeout | 1 |
| VCF-CF Compliance|esx.ceip-disable | 1 |
| VCF-CF Compliance|esx.cpu-hyperthread-warning | 1 |
| VCF-CF Compliance|esx.dcui-timeout | 1 |
| VCF-CF Compliance|esx.deactivate-mob | 1 |
| VCF-CF Compliance|esx.deactivate-shell | 1 |
| VCF-CF Compliance|esx.disable-accounts-dcui | 1 |
| VCF-CF Compliance|esx.firewall-incoming-default | 1 |
| VCF-CF Compliance|esx.forensic-snapshots | 1 |
| VCF-CF Compliance|esx.hardware-virtual-nic | 1 |
| VCF-CF Compliance|esx.key-persistence | 1 |
| VCF-CF Compliance|esx.lockdown-dcui-access | 1 |
| VCF-CF Compliance|esx.lockdown-mode | 1 |
| VCF-CF Compliance|esx.log-audit-forwarding | 1 |
| VCF-CF Compliance|esx.log-audit-local | 1 |
| VCF-CF Compliance|esx.log-audit-local-capacity | 1 |
| VCF-CF Compliance|esx.log-audit-persistent | 1 |
| VCF-CF Compliance|esx.log-filter | 1 |
| VCF-CF Compliance|esx.log-forwarding-tls-ciphers | 1 |
| VCF-CF Compliance|esx.log-forwarding-tls-x509 | 1 |
| VCF-CF Compliance|esx.log-level | 1 |
| VCF-CF Compliance|esx.log-persistent | 1 |
| VCF-CF Compliance|esx.memeagerzero | 1 |
| VCF-CF Compliance|esx.memory-tiering-encryption | 1 |
| VCF-CF Compliance|esx.network-bpdu | 1 |
| VCF-CF Compliance|esx.network-dvfilter | 1 |
| VCF-CF Compliance|esx.network-rpf-promisc | 1 |
| VCF-CF Compliance|esx.password-complexity | 1 |
| VCF-CF Compliance|esx.password-max-age | 1 |
| VCF-CF Compliance|esx.secureboot-enforcement | 1 |
| VCF-CF Compliance|esx.session-timeout | 1 |
| VCF-CF Compliance|esx.shell-interactive-timeout | 1 |
| VCF-CF Compliance|esx.shell-timeout | 1 |
| VCF-CF Compliance|esx.shell-warning | 1 |
| VCF-CF Compliance|esx.snmp | 1 |
| VCF-CF Compliance|esx.ssh | 1 |
| VCF-CF Compliance|esx.time | 1 |
| VCF-CF Compliance|esx.tls-ciphers | 1 |
| VCF-CF Compliance|esx.tpm-configuration | 1 |
| VCF-CF Compliance|esx.tpm-trusted-binaries | 1 |
| VCF-CF Compliance|esx.transparent-page-sharing | 1 |
| VCF-CF Compliance|esx.vib-trusted-binaries | 1 |
| VCF-CF Compliance|esx.vmotion-encryption-offload | 1 |
| configuration|dasConfig | 1 |
| cost | 12 |
| cpu | 32 |
| cpu|demand | 2 |
| datastore | 8 |
| datastore:Aggregate of all instances | 7 |
| disk | 4 |
| disk:Aggregate of all instances | 9 |
| gpu | 10 |
| hardware|cpuInfo | 1 |
| mem | 31 |
| mem|demand | 2 |
| net | 16 |
| net:Aggregate of all instances | 2 |
| performance | 1 |
| power | 1 |
| rescpu | 1 |
| runtime | 1 |
| storage | 9 |
| storageAdapter | 2 |
| storageAdapter:Aggregate of all instances | 6 |
| summary | 8 |
| sys | 3 |
| vCommunity|Licensing:VMware Cloud Foundation (cores) | 1 |
| vmop|vmotion | 2 |


### VirtualMachine: group counts

| Group | Keys |
|---|---|
| VCF-CF Compliance | 68 |
| config | 2 |
| cost | 16 |
| cpu | 23 |
| datastore | 5 |
| datastore:Aggregate of all instances | 5 |
| disk | 3 |
| disk:Aggregate of all instances | 1 |
| diskspace-total | 1 |
| diskspace:200 | 1 |
| guest | 16 |
| guestfilesystem | 3 |
| guestfilesystem:/ | 3 |
| guestfilesystem:/boot | 3 |
| guestfilesystem:/boot/efi | 3 |
| guestfilesystem:/host | 3 |
| mem | 22 |
| mem-host | 1 |
| net | 14 |
| net:Aggregate of all instances | 4 |
| performance | 1 |
| power | 1 |
| rescpu | 2 |
| storage | 2 |
| summary | 11 |
| sys | 2 |
| vCommunity | 2 |
| virtualDisk | 6 |
| virtualDisk:Aggregate of all instances | 8 |
| virtualDisk:scsi0:0 | 7 |
| vmop | 2 |