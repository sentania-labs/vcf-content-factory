# Provenance: P3 captures, all 69 types, no labels (2026-11-07)

Companion to `README.md` and the three 2026-11-06 PROVENANCE files in this
folder (all immutable under RULE-016, so this round gets its own file).
Answers Prerequisite P3 of `knowledge/designs/vsanperf-mp-v3.md`.

## Source and transport

- **vCenter:** `vcf-lab-vcenter-mgmt.int.sentania.net`, `about.fullName`
  `VMware vCenter Server 9.1.1.0100.25784172`, `apiVersion` 9.1.1.0.
- **Cluster:** `vcf-lab-mgmt-cl01`, MoRef `domain-c6004`, vSAN ESA, vSAN cluster
  uuid `90d067b8-0077-11f1-af60-000c297e270a`, 5 hosts, every host
  `VMware ESXi 9.1.1.0100.25782009` (build 25782009), from the PropertyCollector
  read below.
- **Transport:** identical to `PROVENANCE-2026-11-06-build2.md`: raw HTTPS from
  Python `http.client`, release id `8.0.3.0` in every path, headers
  `vmware-api-session-id` and `Accept-Encoding: gzip`, one wildcard spec per
  call, serial, cluster MoRef on every call.
- **Endpoint:** `POST /sdk/vim25/8.0.3.0/vsan/VsanPerformanceManager/vsan-performance-manager/VsanPerfQueryPerf`
- **Body (every `all-*` call):** `{"querySpecs":[{"_typeName":"VsanPerfQuerySpec","entityRefId":"<type>:*","startTime":"2026-11-07T13:47:50Z","endTime":"2026-11-07T13:54:50Z"}],"cluster":{"_typeName":"ManagedObjectReference","type":"ClusterComputeResource","value":"domain-c6004"}}`.
  **No `labels` key.**
- **Window:** 7 min, UTC, the same for every call (including the probes).
  Every non-empty entity carried two 5-minute buckets, `2026-11-07 13:45:00,2026-11-07 13:50:00`.
- **Captured:** 2026-11-07 ~07:54 America/Chicago (13:54 UTC).
- **Sessions (all logged out `204`, read-only):**
  1. inventory: Login, `ServiceInstance` content GET, `CreateContainerView`,
     one `RetrievePropertiesEx`, `DestroyView`, Logout;
  2. the 69 `all-*` queries (Login, 69 calls, Logout; 8.233 s wall around the loop);
  3. the 26 `probe-explicit-*` queries;
  4. one `VsanPerfGetSupportedEntityTypes` (`{}`; 117,329 B wire / 1,205,118 B
     decoded; response not saved, summarized in the digest).
- **Types and order:** the 69 keys of `perfsvc_model.ENTITIES` (31) plus
  `perfsvc_model_extra.ENTITIES` (38) at fork tag `v2.0.0-rc.2`
  (`content/sdk-adapters/vsanhostmetrics/`), split by `metric_scope.COVERED`
  into the 33 shipped types and the 36 new ones; each set alphabetical, shipped
  first. The 36 are exactly the design's §New types.
- **Files:** each is the gunzipped server body, byte for byte, server
  pretty-printing kept. Faults (HTTP 500) and empty wildcard echoes are saved
  like any other body.
- **Redactions:** none needed. The session id travels only in a request header
  and never appears in a response; every saved body was checked in-process for
  the session id, the `.env` password and credential values, the string
  `password` and `session-id` before it was written: 0 hits in 95 files. The
  bodies carry lab uuids, VM disk paths and vSAN world names only.

## 1. `all-<type>.json`, 69 files

"Result": `data` = at least one entity with `value`; `empty echo` = the single
`{"_typeName":"VsanPerfEntityMetricCSV","entityRefId":"<type>:*","sampleInfo":""}`
with no `value`; `fault` = HTTP 500 fault body. Wire B is the gzip body length
as received; decoded B is the saved file's size.

| # | File | Set | HTTP | Result | Entities | Series | Wire B | Decoded B (= file size) | ms |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `all-cache-disk.json` | shipped | 200 | empty echo | 0 | 0 | 119 | 129 | 179.5 |
| 2 | `all-capacity-disk.json` | shipped | 200 | empty echo | 0 | 0 | 121 | 132 | 147.4 |
| 3 | `all-cluster-domclient.json` | shipped | 200 | data | 1 | 14 | 512 | 4,774 | 128.7 |
| 4 | `all-cluster-domcompmgr.json` | shipped | 200 | data | 1 | 15 | 507 | 5,092 | 107.8 |
| 5 | `all-cluster-domowner.json` | shipped | 200 | data | 1 | 46 | 1,045 | 15,407 | 134.3 |
| 6 | `all-cluster-esa-dedup-domclient-io.json` | shipped | 200 | data | 1 | 42 | 823 | 14,182 | 141.8 |
| 7 | `all-cluster-rdt-network-latency.json` | shipped | 200 | data | 1 | 17 | 575 | 5,747 | 112.7 |
| 8 | `all-cluster-zdom-top-stats.json` | shipped | 200 | data | 1 | 12 | 466 | 4,123 | 122.0 |
| 9 | `all-cmmds-net.json` | shipped | 200 | data | 5 | 50 | 1,108 | 17,291 | 164.8 |
| 10 | `all-host-domclient.json` | shipped | 200 | data | 5 | 390 | 7,815 | 129,720 | 131.1 |
| 11 | `all-host-domcompmgr.json` | shipped | 200 | data | 5 | 410 | 8,028 | 136,120 | 121.1 |
| 12 | `all-host-domowner.json` | shipped | 200 | data | 5 | 1440 | 25,488 | 482,103 | 129.0 |
| 13 | `all-host-esa-dedup-domclient-io.json` | shipped | 200 | data | 5 | 210 | 3,830 | 70,831 | 110.0 |
| 14 | `all-host-zdom-top-stats.json` | shipped | 200 | data | 5 | 95 | 2,548 | 32,055 | 107.0 |
| 15 | `all-ioinsight.json` | shipped | 200 | empty echo | 0 | 0 | 118 | 128 | 117.4 |
| 16 | `all-rdt-network-latency.json` | shipped | 200 | data | 5 | 85 | 2,339 | 28,650 | 367.6 |
| 17 | `all-virtual-disk.json` | shipped | 200 | data | 148 | 1036 | 20,752 | 372,600 | 273.0 |
| 18 | `all-virtual-machine.json` | shipped | 200 | data | 30 | 240 | 5,634 | 84,490 | 142.3 |
| 19 | `all-vnic-rdt-network-latency.json` | shipped | 200 | data | 5 | 85 | 2,407 | 28,700 | 115.9 |
| 20 | `all-vsan-cluster-capacity.json` | shipped | 200 | data | 1 | 6 | 427 | 2,245 | 105.0 |
| 21 | `all-vsan-cpu.json` | shipped | 200 | data | 5 | 35 | 865 | 12,188 | 116.2 |
| 22 | `all-vsan-direct-cluster.json` | shipped | 200 | empty echo | 0 | 0 | 127 | 138 | 127.5 |
| 23 | `all-vsan-direct-host.json` | shipped | 200 | empty echo | 0 | 0 | 124 | 135 | 119.5 |
| 24 | `all-vsan-esa-disk-layer.json` | shipped | 200 | data | 5 | 190 | 4,122 | 64,047 | 130.0 |
| 25 | `all-vsan-esa-disk-scsifw.json` | shipped | 200 | data | 5 | 80 | 2,360 | 27,425 | 123.0 |
| 26 | `all-vsan-file-service.json` | shipped | 200 | empty echo | 0 | 0 | 125 | 136 | 110.1 |
| 27 | `all-vsan-host-net.json` | shipped | 200 | data | 5 | 80 | 2,091 | 27,136 | 135.1 |
| 28 | `all-vsan-memory.json` | shipped | 200 | data | 5 | 250 | 5,960 | 85,581 | 125.2 |
| 29 | `all-vsan-pnic-net.json` | shipped | 200 | data | 10 | 650 | 11,315 | 211,228 | 124.1 |
| 30 | `all-vsan-tcpip-stats.json` | shipped | 200 | data | 5 | 160 | 3,552 | 53,267 | 122.0 |
| 31 | `all-vsan-vnic-net.json` | shipped | 200 | data | 5 | 320 | 5,658 | 105,441 | 135.3 |
| 32 | `all-vscsi.json` | shipped | 200 | data | 148 | 1184 | 24,059 | 414,216 | 251.3 |
| 33 | `all-zdom-vtx.json` | shipped | 200 | data | 5 | 355 | 6,976 | 119,955 | 109.8 |
| 34 | `all-clom-disk.json` | new | 500 | fault `InvalidArgument` | - | - | 140 | 151 | 38.8 |
| 35 | `all-clom-host.json` | new | 500 | fault `InvalidArgument` | - | - | 140 | 151 | 38.9 |
| 36 | `all-cluster-esa-dedup-domcompmgr-io.json` | new | 200 | data | 1 | 42 | 947 | 14,339 | 163.6 |
| 37 | `all-cluster-esa-dedup-domowner-io.json` | new | 200 | data | 1 | 82 | 1,622 | 28,228 | 140.3 |
| 38 | `all-cluster-esa-dedup-store-chunksvc.json` | new | 200 | data | 1 | 33 | 876 | 11,184 | 117.1 |
| 39 | `all-cluster-esa-dedup-store-hashsvc.json` | new | 200 | data | 1 | 39 | 953 | 13,154 | 123.6 |
| 40 | `all-cluster-pmem.json` | new | 500 | fault `NotSupported` `pmemisunavailable` | - | - | 273 | 426 | 36.8 |
| 41 | `all-cluster-remotedomclient.json` | new | 200 | empty echo | 0 | 0 | 131 | 142 | 91.3 |
| 42 | `all-cluster-resync.json` | new | 200 | empty echo | 0 | 0 | 123 | 133 | 124.7 |
| 43 | `all-cmmds-workload.json` | new | 500 | fault `InvalidArgument` | - | - | 140 | 151 | 40.0 |
| 44 | `all-computeCluster-remotedomclient.json` | new | 200 | empty echo | 0 | 0 | 138 | 149 | 92.6 |
| 45 | `all-computeHost-remotedomclient.json` | new | 200 | empty echo | 0 | 0 | 135 | 146 | 81.8 |
| 46 | `all-ddh-disk.json` | new | 500 | fault `InvalidArgument` | - | - | 140 | 151 | 39.0 |
| 47 | `all-disk-group.json` | new | 200 | empty echo | 0 | 0 | 119 | 129 | 109.8 |
| 48 | `all-dom-world-cpu.json` | new | 200 | data | 330 | 990 | 23,371 | 400,681 | 159.5 |
| 49 | `all-heap-memory.json` | new | 500 | fault `InvalidArgument` | - | - | 140 | 151 | 60.5 |
| 50 | `all-host-cpu.json` | new | 200 | data | 165 | 495 | 11,776 | 197,161 | 158.8 |
| 51 | `all-host-esa-dedup-domcompmgr-io.json` | new | 200 | data | 5 | 210 | 4,249 | 71,452 | 154.7 |
| 52 | `all-host-esa-dedup-domowner-io.json` | new | 200 | data | 5 | 410 | 7,699 | 140,721 | 127.9 |
| 53 | `all-host-esa-dedup-store-chunksvc.json` | new | 200 | data | 5 | 165 | 3,769 | 55,748 | 105.0 |
| 54 | `all-host-esa-dedup-store-hashsvc.json` | new | 200 | data | 5 | 195 | 4,340 | 65,563 | 119.0 |
| 55 | `all-host-pmem.json` | new | 500 | fault `NotSupported` `pmemisunavailable` | - | - | 273 | 426 | 29.0 |
| 56 | `all-host-remotedomclient.json` | new | 200 | empty echo | 0 | 0 | 128 | 139 | 106.3 |
| 57 | `all-host-vsansparse.json` | new | 200 | data | 5 | 105 | 2,287 | 34,806 | 133.6 |
| 58 | `all-lsom-world-cpu.json` | new | 200 | empty echo | 0 | 0 | 123 | 133 | 116.5 |
| 59 | `all-rdt-net.json` | new | 200 | data | 5 | 5 | 410 | 2,781 | 128.5 |
| 60 | `all-remote-virtual-disk.json` | new | 500 | fault `InvalidArgument` | - | - | 140 | 151 | 43.9 |
| 61 | `all-remote-virtual-machine.json` | new | 500 | fault `InvalidArgument` | - | - | 140 | 151 | 37.3 |
| 62 | `all-remote-vscsi.json` | new | 500 | fault `InvalidArgument` | - | - | 140 | 151 | 38.0 |
| 63 | `all-slab-memory.json` | new | 500 | fault `InvalidArgument` | - | - | 140 | 151 | 40.6 |
| 64 | `all-system-mem.json` | new | 200 | data | 5 | 15 | 564 | 6,016 | 120.5 |
| 65 | `all-vsan-distribution.json` | new | 200 | empty echo | 0 | 0 | 124 | 136 | 120.2 |
| 66 | `all-vsan-dp-historical-stats.json` | new | 200 | data | 1 | 1 | 304 | 594 | 125.9 |
| 67 | `all-vsan-iscsi-host.json` | new | 200 | empty echo | 0 | 0 | 123 | 134 | 118.8 |
| 68 | `all-vsan-iscsi-lun.json` | new | 200 | empty echo | 0 | 0 | 122 | 133 | 104.4 |
| 69 | `all-vsan-iscsi-target.json` | new | 200 | empty echo | 0 | 0 | 125 | 136 | 132.0 |

Totals: 69 calls, 8.233 s wall (serial, one timer around the loop), 218,360 B
wire, 3,601,561 B decoded, 958 entities, 10,284 series. Shipped 33: 27 data,
6 echo, 0 fault, 423 entities, 7,497 series, 151,996 / 2,555,412 B. New 36:
14 data, 11 echo, 11 fault, 535 entities, 2,787 series, 66,364 / 1,046,149 B.

## 2. Memory read and the Q4 arithmetic

Session 1's `RetrievePropertiesEx` (ContainerView over `ClusterComputeResource`
from `group-d1`, traversal `view` then `ComputeResource.host`; cluster paths
`name`, `host`; host paths `name`, `config.vsanHostConfig.enabled`,
`config.vsanHostConfig.clusterInfo.uuid`, `config.vsanHostConfig.clusterInfo.nodeUuid`,
`hardware.memorySize`, `summary.config.product.fullName`,
`summary.config.product.build`) returned HTTP 200, 1,350 B wire / 14,346 B
decoded, 29.3 ms. Not saved (vim25 inventory, same shape as
`retrievepropertiesex-cluster-hosts-2026-11-06.json` plus three paths); the
values used are below.

| Host | MoRef | nodeUuid | `hardware.memorySize` (B) |
|---|---|---|---|
| vcf-lab-mgmt-esx01 | host-6017 | 69805090-5bba-3949-88f7-38052534dfcc | 269,896,261,632 |
| vcf-lab-mgmt-esx02 | host-6015 | 698054c1-6eb8-30f8-8c1e-38052534ded0 | 269,896,261,632 |
| vcf-lab-mgmt-esx03 | host-6011 | 69805998-46aa-aafb-3dd4-38052534e318 | 269,896,261,632 |
| vcf-lab-mgmt-esx04 | host-15151 | 69fd149d-c1b8-aae3-bcb2-3805253936dc | 269,896,261,632 |
| vcf-lab-mgmt-esx05 | host-31189 | 6a8859db-a52e-c523-e78c-3805253a02fc | 269,896,261,632 |

269,896,261,632 B = 257,393.13 MiB (/ 2^20) = 269,896.26 MB (/ 10^6).

**`pctMemUsed` is not a `vsan-memory` label.** `all-vsan-memory.json` returns
50 labels, all per-daemon `*ConsumedSize` / `*ReservedSize` / `*MemAllocMax` /
`*MemAllocMin`, with no percent and no host-total used figure. `pctMemUsed`
and `totalMbMemUsed` are on **`system-mem`** (labels `overcommitRatio`,
`pctMemUsed`, `totalMbMemUsed`), file `all-system-mem.json`, same window:

| nodeUuid (first 8) | bucket | `totalMbMemUsed` | `pctMemUsed` | 100 x used / MiB total | 100 x used / MB total | 1000 x used / MiB total |
|---|---|---|---|---|---|---|
| 69fd149d | 13:45 | 132,524 | 51 | 51.49 | 49.10 | 514.9 |
| 69fd149d | 13:50 | 132,544 | 51 | 51.49 | 49.11 | 514.9 |
| 69805090 | 13:45 | 144,228 | 56 | 56.03 | 53.44 | 560.3 |
| 69805090 | 13:50 | 143,904 | 55 | 55.91 | 53.32 | 559.1 |
| 6a8859db | 13:45 | 133,630 | 51 | 51.92 | 49.51 | 519.2 |
| 6a8859db | 13:50 | 133,509 | 51 | 51.87 | 49.47 | 518.7 |
| 69805998 | 13:45 | 134,759 | 52 | 52.36 | 49.93 | 523.6 |
| 69805998 | 13:50 | 134,844 | 52 | 52.39 | 49.96 | 523.9 |
| 698054c1 | 13:45 | 145,494 | 56 | 56.53 | 53.91 | 565.3 |
| 698054c1 | 13:50 | 145,448 | 56 | 56.51 | 53.89 | 565.1 |

All 10 samples satisfy `pctMemUsed = floor(100 x totalMbMemUsed / (memorySize / 2^20))`
exactly (55.91 gives 55, so it truncates rather than rounds). The MB-decimal
reading misses on every sample (49.1 against 51) and the per-mille reading is
off by 10x. **Answer: `pctMemUsed` is an integer percent of host physical
memory, and `totalMbMemUsed` is in MiB.** `overcommitRatio` was 0 on all 10.

## 3. Explicit-ref probes for the 9 wildcard faults (`probe-explicit-*.json`, 26 files)

Session 3, same window and cluster, one explicit spec per call. Ref values:
cluster uuid above; nodeUuid `69fd149d-c1b8-aae3-bcb2-3805253936dc` (esx04);
vSAN disk uuid `52d171f6-2e48-758a-777f-d5098533d861` (the first
`all-vsan-esa-disk-layer.json` entity); VM instanceUuid
`e8f31d49-d532-4b17-9ef1-7cc33efa33dc` with device `scsi1:0` (from
`all-vscsi.json`); vdisk path = the first `all-virtual-disk.json` ref. Every
fault body is 140 B wire / 151 B decoded; the control success is 1,541 /
25,924 B.

| # | entityRefId sent (type, form) | HTTP | Outcome | ms | File |
|---|---|---|---|---|---|
| 1 | `clom-host`, node | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 64.3 | `probe-explicit-clom-host-node.json` |
| 2 | `clom-host`, cluster | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 38.7 | `probe-explicit-clom-host-cluster.json` |
| 3 | `cmmds-workload`, node | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 47.2 | `probe-explicit-cmmds-workload-node.json` |
| 4 | `cmmds-workload`, cluster | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 36.3 | `probe-explicit-cmmds-workload-cluster.json` |
| 5 | `heap-memory`, node | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 38.9 | `probe-explicit-heap-memory-node.json` |
| 6 | `heap-memory`, cluster | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 39.4 | `probe-explicit-heap-memory-cluster.json` |
| 7 | `slab-memory`, node | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 44.4 | `probe-explicit-slab-memory-node.json` |
| 8 | `slab-memory`, cluster | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 40.7 | `probe-explicit-slab-memory-cluster.json` |
| 9 | `clom-disk`, disk | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 43.3 | `probe-explicit-clom-disk-disk.json` |
| 10 | `clom-disk`, node | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 39.7 | `probe-explicit-clom-disk-node.json` |
| 11 | `clom-disk`, cluster | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 36.7 | `probe-explicit-clom-disk-cluster.json` |
| 12 | `ddh-disk`, disk | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 36.5 | `probe-explicit-ddh-disk-disk.json` |
| 13 | `ddh-disk`, node | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 35.0 | `probe-explicit-ddh-disk-node.json` |
| 14 | `ddh-disk`, cluster | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 36.6 | `probe-explicit-ddh-disk-cluster.json` |
| 15 | `remote-virtual-machine`, vm | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 39.3 | `probe-explicit-remote-virtual-machine-vm.json` |
| 16 | `remote-virtual-machine`, node | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 37.2 | `probe-explicit-remote-virtual-machine-node.json` |
| 17 | `remote-virtual-machine`, cluster | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 41.6 | `probe-explicit-remote-virtual-machine-cluster.json` |
| 18 | `remote-vscsi`, vm-dev | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 44.2 | `probe-explicit-remote-vscsi-vm-dev.json` |
| 19 | `remote-vscsi`, node | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 42.1 | `probe-explicit-remote-vscsi-node.json` |
| 20 | `remote-vscsi`, cluster | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 52.7 | `probe-explicit-remote-vscsi-cluster.json` |
| 21 | `remote-virtual-disk`, path | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 53.5 | `probe-explicit-remote-virtual-disk-path.json` |
| 22 | `remote-virtual-disk`, node | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 39.8 | `probe-explicit-remote-virtual-disk-node.json` |
| 23 | `remote-virtual-disk`, cluster | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 43.2 | `probe-explicit-remote-virtual-disk-cluster.json` |
| 24 | `host-domclient`, node | 200 | 1 result(s), 1 with value | 195.2 | `probe-explicit-host-domclient-node.json` |
| 25 | `nosuch-type`, node | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 38.2 | `probe-explicit-nosuch-type-node.json` |
| 26 | `nosuch-type`, wild | 500 | InvalidArgument: A specified parameter was not correct: entityRefId | 35.4 | `probe-explicit-nosuch-type-wild.json` |

Rows 24 and 25 are controls: a valid explicit ref on a working type returns
data; an invented prefix (`nosuch-type`) faults with the byte-identical body
the 9 types return.

**Other vCenters.** `.env` names no 9.0 or 8.x vCenter. The only other
vCenters in the lab inventory (`vcf-lab-vcenter-wld01`, `vcf-lab-vcenter-wld02`,
the ones devel 9.0 and 8.18 Ops monitor alongside mgmt per
`knowledge/context/investigations/2026-10-15-devel-8-18-recon.md`) were read
with the session-1 inventory shape: both `VMware vCenter Server
9.1.1.0100.25784172`, one cluster each (`domain-c10`, `domain-c9`), 2 hosts
each, `config.vsanHostConfig.enabled` false on all 4 hosts. No vSAN, same
build: the wildcard queries were not run there. Nothing was saved from them.

## Digest

`knowledge/context/api-maps/vsan-performance-service.md`, section
"P3: all 69 types, no labels (measured 2026-11-07)".
