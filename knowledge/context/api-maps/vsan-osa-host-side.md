# API Map: vSAN OSA (disk-group) data without the Performance Service

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** vcf-lab-vcenter-mgmt.int.sentania.net:443 (vCenter 9.1.1.0100 build 25784172). OSA cluster `vcf-lab-osa-probe-cl01` (`domain-c39146`, 3 hosts `vcf-lab-osa-esx01/02/03` = `host-39158/39155/39160`, ESXi 9.0.0.0 build 24755229, nested, one all-flash disk group per host: 50 GiB NVMe cache + 500 GiB NVMe capacity, dedup/compression off, no VMs). ESA comparison: `vcf-lab-mgmt-cl01` (`domain-c6004`, 5 hosts 9.1.1.0100), host-side calls on esx01 `host-6017`.
- **Last updated:** 2026-11-07
- **Update history:**
  - 2026-11-07 — initial mapping. Performance Service state on both clusters and what `masternotfound` means; OSA inventory, health, space and host-side counters reachable without the Performance Service (vSAN MOs on `/vsanHealth` over JSON, `HostVsanInternalSystem`, esxcli over the executer); vSphere Automation REST checked for vSAN services. Captures in `reference/docs/extracted/vsan-osa-probe/` (`PROVENANCE-2026-11-07.md`).
- **Evidence basis:** live API calls (raw HTTPS, vSphere JSON API release `8.0.3.0`, vSphere Automation REST), 2026-11-07 18:41 to 18:55 America/Chicago. Pak model labels read from the vsanperf pak's `EntityType.java` (`content/sdk-adapters/vsanperf/`, gitignored clone; mirrored in `REFERENCE.md`); the Python fork's `perfsvc_model_extra.py` carries the same 38.
- **Notes:** Read-only: no enable, no IOInsight, no health run from vCenter (cache only). The OSA cluster is idle, nested and freshly built (22:33 UTC), so every congestion, dedup and resync value seen is 0; field presence is verified, value behaviour under load is not. Only one OSA cluster and one ESXi 9.0 build exist in the lab. Companion maps: `vsan-performance-service.md` (perfsvc transport, 69 types) and `esxi-esxcli-over-soap.md` (executer route). This file is separate because most of it is not the Performance Service.

## 1. Performance Service state and what `masternotfound` means

| Signal | OSA probe `domain-c39146` | ESA `domain-c6004` |
|---|---|---|
| `VsanClusterGetConfig` → `perfsvcConfig` | **key absent** (no `perfsvcConfig`, no `mode`) | `{"enabled": true}` |
| `VsanPerfQueryNodeInformation` | 3 nodes, every `isStatsMaster: false`, no `masterInfo`; esx01 is CMMDS master | esx05 `isStatsMaster: true`, `masterInfo` interval 300 s, verbose off |
| `VsanPerfQueryStatsObjectInformation` | `{"directoryName": "unknown"}` only | `.vsan.stats` object, healthy, FTT=1 |
| Health test `perfsvc.perfsvcstatus` (cached summary) | yellow, row "Performance service is disabled", action `EnablePerformanceServiceAction` | group green: statsdb, masterexist, collection, hostsmissing, renameddirs |
| esxcli `vsan perf get` (host) | `Enabled=false VerboseMode=N/A` (3.2 s) | CLI fault "Failed to get vSAN performance service master node." (10.4 s, on non-master esx01) |
| `VsanPerfQueryPerf` any type | HTTP 500 `NotFound`, `faultMessage.key` `com.vmware.vsan.perfsvc.fault.masternotfound`, message "Stats primary cannot be found in the cluster." (45 to 62 ms) | data |

All `[observed 2026-11-07]` (captures `01`..`05`, `12`, `40-*-vsan-perf-get`).

- **On this cluster `masternotfound` means the Performance Service is disabled** (never enabled since the cluster was built). Five independent signals agree `[observed 2026-11-07]`.
- The config signal is **absence** of `perfsvcConfig`, not `enabled: false`. Whether a cluster that had the service turned on and then off reports `enabled: false` or omits the key is `[unverified]`. Read it as "enabled only if `perfsvcConfig.enabled == true`".
- `masternotfound` can in principle also occur with the service enabled while the stats primary is being re-elected or the stats object is inaccessible `[inferred from the fault text, unverified]`. So the fault alone should not be read as "disabled"; the config read should be.
- esxcli `vsan perf get` is not a usable probe: it faulted on an ESA host of a cluster where the service is healthy (`[observed 2026-11-07]`, cause unknown; possibly it only answers on the stats master `[unverified]`).
- **Q2 (OSA perf types on the probe): skipped by design.** The service is disabled and was not enabled. `disk-group`, `cache-disk`, `capacity-disk`, `lsom-world-cpu` on the probe all return the same `masternotfound` (`05-osa-*`); on ESA they return the empty wildcard echo (`05-esa-*`) `[observed 2026-11-07]`.

### What the pak should display

- One `VsanClusterGetConfig` per cluster per cycle costs 12 to 48 ms (one call, ~0.7 KB wire) `[observed 2026-11-07]`. Use it to set a cluster property such as "Performance Service: disabled" and skip every perf type for that cluster. On this instance that removes the 26 (`dashboard`) to 61 to 67 (`all`) failing calls per cycle recorded in `knowledge/context/reviews/vsanperf-t5-devel-9.0-build-22-all-scope-all-tiers.md`, clears `clusters_failed`/`last_error` noise, and re-arms on its own when someone enables the service.
- If the config read is not wanted, the fallback is to treat a cluster-wide `masternotfound` on the first type of a cycle as "no stats primary" for that cycle and skip the rest, re-trying next cycle `[inferred]`.

## 2. OSA counters reachable without the Performance Service

Cost = median of 5 serial calls on a reused session, wall ms, from a lab-LAN workstation `[observed 2026-11-07]`. "Scope" = what one call returns.

| Surface / call | Scope | OSA-specific fields (per disk or disk group) | Cost | Refresh | Overlaps perfsvc |
|---|---|---|---|---|---|
| `VsanVcClusterHealthSystem.VsanQueryVcClusterHealthSummary(cluster, fetchFromCache=true, fields=["physicalDisksHealth"])` | **cluster, all disks** | per disk: `congestionValue`, `congestionArea`, `congestionHealth`, `capacity`, `usedCapacity`, `reservedCapacity` (capacity tier only), `usedComponents`/`maxComponents`, `operationalHealth`, `metadataHealth`, `capacityHealth`, `dedupUsageHealth`, `summaryHealth`, `rebalanceResult.{diskUsage,remainingBytesToMove,bytesMoving}`, `isAllFlash` (1 on the cache disk, 0 on capacity), `dedupScope` | **3 ms** (24 KB decoded); full summary 20 ms, 268 KB | vCenter health cache; `timestamp` was 14 min old at read (00:27Z read 00:41Z). Cadence of the periodic run `[unverified]` | `disk-group` `*Congestion`, `capacity`, `capacityUsed` |
| `VimClusterVsanVcDiskManagementSystem.QueryDiskMappings(host)` | host, its disk groups | `mapping.ssd` (cache) and `mapping.nonSsd[]` (capacity) as full `HostScsiDisk` with `vsanDiskInfo.vsanUuid`; `isMounted`, `isAllFlash`, `isDataEfficiency`, `dataEfficiencyConfig`, `encryptionInfo` | 77 ms | config | inventory only. **ESA returns `[]`** |
| `HostVsanInternalSystem.QueryPhysicalVsanDisks(props?)` on any one host | **cluster, all disks** (CMMDS view: 6 disks from esx01, owners on all 3 hosts) | per disk (ints, inside a JSON string: double decode as for `QueryVsanStatistics`): `writeBufferSize`, `writeBufferUsage` (cache disk; capacity disks carry the DG's usage too), `capacityUsed`, `physCapacityUsed`, `capacityReserved`, `dgAvgDataDestageBytesSec`, `dgAvgZeroDestageBytesSec`, `dgAvgResyncReadBytesPerSec`, `dgAvgTotalRead/WriteBytesPerSec`, `dgAvgRecWriteBytesPerSec`, `avgReads/WritesPerSecond`, `avgRead/WriteServiceTime`, `avgRead/WriteQueueTime`, `pendingWrite`/`pendingDelete`/`pendingUnmap`, `numTotalComponents`, `maxComponents`, `ssdUuid` (= DG/cache uuid), `owner` (= node uuid), `isSsd`, dedup totals (`totalDedup*`, `dedupAddrRatio`) | 39 ms all props (20 KB); `props` filter honoured (16 names, 3.6 KB) | CMMDS-published averages; cadence `[unverified]` | `disk-group` `wbFreePct`, `wbSize`, `capacity*`, destage, resync tput |
| `HostVsanInternalSystem.QueryVsanStatistics(labels=["lsom"])` | host, local disks only | per disk `info`: `type` cache/data, `wbSize`, `wbFreeSpace` (→ write buffer free %), `memCongestion`, `slabCongestion`, `ssdCongestion`, `iopsCongestion`, `logCongestion`, `compCongestion` (+ `*LocalMax`), `oobLogCongestionIOPS`, `currentDrainRate`, `drainRateMovingAvg`, `currentIncomingRate`, `avgRead/Write/UnmapIOPS`, `avgRead/WriteLatency`, `avgRead/WriteTPut`, `nrOutstanding*Ops`, `capacity`/`capacityUsed`/`capacityReserved`, `numComp`/`maxComp`, `diskMappings`; `aggStats.*` cumulative (`readIoCount`, `writeIoCount`, `bytesRead`, `bytesWritten`, `readIoTime`, `writeIoTime`, `warEvictions`, `quotaEvictions`, `rarPercent`...); capacity disks add `CFStats`, `virstoStats`; plus queue histograms | 73 ms, 82 KB | live snapshot (`lsom.disks-taken` epoch) | `disk-group` congestions, `wbFreePct`, evictions, `ssdBytesDrained`; `cache-disk`/`capacity-disk` IOPS/latency |
| `QueryVsanStatistics(["plog"])` | host, local disks | per device `info.dedupRatio`, `possibleDDPRatio`, `isSSD`, `mappedUUID`, `devState`, `needsRepair`; `elevStats` (destage: `ssdWbSize`, `ssdWbFreeSpace`, `dgCurr/AvgDataDestageBytesSec`, `totalBytesDrained`, `plogDataUsage`); `stats` (`cacheHits`/`cacheLookups`, read/write/repair errors); `dedupStats` (`dedupPercent`, `compressedBytes`, `hashedBytes`...); SMART counters (`health/SMART/*`) | 70 ms, 85 KB | live | destage, dedup |
| `QueryVsanStatistics(["disks"])` | host, local vSAN devices | per device `commands`, `failedCommands`, `blocksRead/Written`, `readOps`/`writeOps` and failed counts, `maxIoTime` (cumulative) | 41 ms | live | device IOPS |
| `QueryVsanStatistics(["lsom-node"])` | host | `numDiskGroups`, `numMaxDiskGroups` (5), `numMDs`, `numMaxMDs` (35), `numOpenedComponents`, `numMaxComponents` (9000), `pendingComponents` | 37 ms | live | none |
| esxcli `vsan debug disk list` | cluster-wide view from one host (6 rows here) | `DiskTier` Cache/Capacity, `DiskGroup` uuid, `CongestionHealth.{CongestionValue,CongestionArea,State}`, `SpaceHealth.{CapacityInBytes,UsedInBytes,ReservedInBytes}`, `DedupRatio`, `Owner` | **15.4 s** OSA, 10.8 s ESA | live (runs checks) | same as health summary, far slower |
| esxcli `vsan storage list` | host | `IsCapacityTier`, `VSANDiskGroupUUID`, `VSANDiskGroupName`, `Deduplication`, `Compression`, `ChecksumOK` | 194 ms OSA; ESA empty (8 ms), ESA uses `vsan storagepool list` | config | inventory only |
| esxcli `vsan debug resync summary get` | cluster | `TotalBytesLeftToResync`, `TotalNumberOfResyncingObjects` | 3.0 s OSA, 0.4 s ESA | live | `cluster-resync` |
| esxcli `vsan debug limit get` | host | `FreeComponents`, `MaxComponents`, `LowestFreeDiskSpace` (%), `UsedDiskSpace` | 3.8 s OSA, 0.4 s ESA | live | none |

Combined: one `QueryVsanStatistics(["lsom","plog","disks","lsom-node"])` is accepted and costs 125 ms (108 to 163) per host `[observed 2026-11-07]`.

### Counter semantics

- `aggStats.*` and `disks.stats` are **cumulative since boot/mount**: over 60 s on idle esx01, `writeIoCount` 19,150 → 19,301, `bytesWritten` +6.48 MB, device `commands` 57,801 → 58,258 (`25-*-t0`, `-t60`) `[observed 2026-11-07]`. Rates need a delta. `avg*IOPS`, `avg*Latency`, `current*Rate`, `*Congestion` and `wbFreeSpace` are gauges `[inferred from names; values 0 or static on an idle cluster]`.
- Write buffer free %: `wbFreeSpace / wbSize` on the `type: cache` lsom entry (52,586,938,368 / 52,610,174,976 = 99.96 %); the same pair appears as `elevStats.ssdWbFreeSpace/ssdWbSize` in plog and as `writeBufferSize - writeBufferUsage` in `QueryPhysicalVsanDisks` (agree to within about 1 MB across calls made minutes apart) `[observed 2026-11-07]`.
- `QueryVsanStatistics` returns a **JSON string** whose content is JSON (double decode). `QueryPhysicalVsanDisks` is the same double decode; the decoded values are mostly ints (576 int, 36 str across 6 disks) `[observed 2026-11-07]`.
- Dedup/compression ratio: fields present (`plog info.dedupRatio`, `dedupStats.dedupPercent`, `QueryPhysicalVsanDisks totalDedup*`, esxcli `DedupRatio`, space report `efficientCapacity`), but DE is off on the probe, so every value is 0 / `N/A` and `VsanQuerySpaceUsage` carries no `efficientCapacity` on OSA (ESA has it plus `spaceEfficiencyRatio`) `[observed 2026-11-07]`. Behaviour with DE on is `[unverified]`.
- Evacuation: no counter found. `rebalanceResult` in `physicalDisksHealth` and `VsanQueryObjectIdentities(includeHealth)` → `objectsRelayoutBytes` are the nearest; `VsanQueryWhatIfEvacuationResult` exists in the bindings but was not called `[observed 2026-11-07 / not tested]`.

### Same calls on ESA

`QueryVsanStatistics` `lsom`, `plog`, `disks` return empty maps on ESA; `QueryDiskMappings` returns `[]`; esxcli `vsan storage list` is empty `[observed 2026-11-07]`. These are OSA-only surfaces. `physicalDisksHealth`, `QueryPhysicalVsanDisks` and esxcli `vsan debug *` work on both (ESA `QueryPhysicalVsanDisks` with no `props` is 2.0 MB decoded on 5 disks, because of per-disk `lsom_objects`; always pass `props`). ESA `dom-objects` is 4.5 MB per host (686 ms): do not call it.

## 3. Refused or not useful on 9.x

| Call | Result |
|---|---|
| `VsanPerfQueryPerf` (every type) on the probe | `NotFound` / `masternotfound` (service disabled) |
| `VsanObjectSystem.VsanQuerySyncingVsanObjectsSummary` | `InvalidType: Managed object type 'VsanObjectSystem' doesn't have a 'VsanQuerySyncingVsanObjectsSummary' method.` (both clusters; name or MO guessed wrong, not a version refusal) |
| `QueryVsanStatistics(["ssd"])`, `(["worldlets"])` | 200 with only `on-esx-collect-duration`: labels accepted, no data, both 9.0 and 9.1 `[observed]`; likely retired `[inferred]` |
| esxcli `vsan debug controller list` (OSA 9.0 nested) | CLI fault "Type mismatch on field: Max Supported Queue Depth ... Implementation error!" (works on ESA 9.1, 1.3 s) |
| esxcli `vsan perf get` (ESA esx01) | CLI fault "Failed to get vSAN performance service master node." |
| esxcli `vsan health cluster list` | works but runs the host-side checks: 57.6 s OSA, 30.7 s ESA. Its network-latency row was yellow while vCenter's cached summary said network green |

Every other `QueryVsanStatistics` label tried (`dom`, `lsom`, `plog`, `dom-objects`, `dom-objects-counts`, `lsom-node`, `disks`, `mem`, `cpus`, `slabs`, `vscsi`, `cbrc`, `rdtassocsets`, `rdtglobal`, `system-mem`, `pnics`) answered 200 on ESXi 9.0.0 and 9.1.1; nothing is refused as deprecated `[observed 2026-11-07]`. These are internal, undocumented APIs (`HostVsanInternalSystem` is not in the supported vSAN SDK surface `[inferred from docs]`); field names may change per build.

esxcli vsan namespaces: 133 `vim.EsxCLI.vsan.*` methods on the 9.0 OSA host, 135 on the 9.1 ESA host (ESA adds `vsan.dedup.scan.get`, `vsan.maintenancemode.recommission`) `[observed 2026-11-07, captures 30-*]`.

## 4. vSphere Automation REST

- `GET /api/vapi/metadata/metamodel/service`: 528 services, **none** containing `vsan`; package list has only `vcenter.storage*`, `vcenter.vm.storage*`, `namespace_management.*storage*` and an `esx.settings` HCL override package `[observed 2026-11-07]`.
- `/api/vcenter/vsan`, `/api/vsan`, `/api/vcenter/vsan/clusters`, `/rest/vcenter/vsan`: 404 `[observed 2026-11-07, not captured]`. `/api/vcenter/cluster/domain-c39146` returns only `name` and `resource_pool`.
- Result: no vSAN REST surface on vCenter 9.1.1, config or metrics. Everything vSAN is on `/vsanHealth` (SOAP or JSON) or vim25 host MOs.

## Object model candidates

- **HostSystem (stitched, as the pak already does for ESA disks):** instanced per disk uuid (`vsanUuid`) or per disk group (cache-disk `vsanUuid`, = `ssdUuid` on capacity rows = lsom `info.uuid` of the cache entry = esxcli `VSANDiskGroupUUID`).
- **ClusterComputeResource:** property `Performance Service` (enabled/disabled) from `VsanClusterGetConfig`.

## Cross-request join keys

- `QueryDiskMappings` `vsanDiskInfo.vsanUuid` = `physicalDisksHealth.disks[].uuid` = `QueryPhysicalVsanDisks` key/`uuid` = lsom `lsom.disks` key = plog `info.deviceUUID` = esxcli `UUID`/`VSANUUID` `[observed 2026-11-07]`.
- Disk group id = cache disk `vsanUuid` = capacity rows' `ssdUuid` (QPVD) = lsom `info.diskMappings` partner = esxcli `DiskGroup` / `VSANDiskGroupUUID` `[observed 2026-11-07]`.
- `QueryPhysicalVsanDisks.owner` = `VsanPerfNodeInformation.vsanNodeUuid` = esxcli `LocalNodeUUID` (host node uuid) `[observed 2026-11-07]`.
- Device name `eui.*` = plog key = `disks.stats` key = `HostScsiDisk.canonicalName`; lsom `devName` adds a `:2` partition suffix `[observed 2026-11-07]`.

## Recommendation

1. **Do (small, high value): perfsvc-disabled detection.** One `VsanClusterGetConfig` per cluster per cycle; if `perfsvcConfig.enabled` is not `true`, publish a cluster property and skip the cluster's perf calls. Fixes the probe cluster's 26 to 67 wasted calls per cycle and the permanent `clusters_failed=1`.
2. **Maybe (cheap fallback, works on OSA and ESA): disk health from the cached health summary.** One call per cluster, 3 ms, with `fields=["physicalDisksHealth"]`: per-disk congestion value, used/capacity, component use and health states, stitched to HostSystem by disk uuid. Supported vSAN SDK method, no Performance Service needed. Only worth it if users with the service off are a real audience; values are only as fresh as vCenter's health cache.
3. **Not now: an lsom/plog OSA tier.** It reaches the classic OSA internals (write buffer free %, six congestion types, destage, dedup stats) at ~125 ms per host, but it is an internal API with string/JSON-in-string payloads, cumulative counters needing deltas, and nothing here to validate it under load (idle nested lab, DE off, one DG per host). An OSA cluster with the Performance Service on would deliver most of the same through `disk-group` anyway.
4. **Fix before OSA matters with perfsvc on:** the vsanperf pak's `disk-group` model (38 labels in `EntityType.java`, the same 38 in the Python fork) is mostly the `domcomp-sched` graph set; the server's `VsanPerfGetSupportedEntityTypes` (capture 06) carries **two** entity-type entries named `disk-group`: one with 76 labels across 21 classic graphs, and one with 38 labels across 6 `domcomp-sched` graphs, which is exactly the pak's set; which one `VsanPerfQueryPerf` serves on OSA is unobserved (the probe's service is off). The classic ones (`wbFreePct`, `wbSize`, `memCongestion`, `ssdCongestion`, `logCongestion`, `compCongestion`, `iopsCongestion`, `slabCongestion`, `rcHitRate`, `warEvictions`, `quotaEvictions`, `ssdBytesDrained`, `latencyAvgRead/Write`...) are not modelled `[observed 2026-11-07, capture 06; pak model read from source]`. Values from a live OSA perfsvc remain `[unverified]` here.
5. esxcli `vsan debug *` is not a collection path: 0.4 to 15 s per call and some run checks on demand.

## Gaps / questions

- OSA with the Performance Service enabled: never observed (not enabled by policy of this run). `disk-group`/`cache-disk`/`capacity-disk` series shape and entityRefId grammar on OSA are `[unverified]`.
- `perfsvcConfig` after an enable-then-disable: absent or `enabled: false` `[unverified]`.
- `masternotfound` with the service enabled (master failover) `[unverified]`.
- Dedup/compression values on an OSA DE cluster; hybrid (non-all-flash) OSA read-cache fields (`rcSize`, `rcHitRate`) `[untested]`.
- Health-cache refresh cadence and `QueryPhysicalVsanDisks` average windows `[unverified]`.
- Correct name/MO for the syncing-objects summary method `[open]`.
- Least privilege for `HostVsanInternalSystem` calls (run as the pak's admin account) `[untested]`.
