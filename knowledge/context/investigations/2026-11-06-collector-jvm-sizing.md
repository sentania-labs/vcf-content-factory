# Collector JVM sizing in the lab (2026-11-06)

Read-only recon. SSH `ps`, `cat`, `grep`, `free`, `ls`, `du`, GC-log reads; Suite API GET `/api/collectors` and `/api/adapters`. MEASURED unless marked INFERRED. Times UTC from the GC log unless noted.

## What was reachable

| Host | Role | SSH result |
|---|---|---|
| 172.27.10.12 (devel, 9.0.2) | analytics node with embedded collector (collector id 1) | OK |
| 172.27.10.13 (devel proxy) | Cloud Proxy (collector id 2) | denied (no SSH credential available to the factory) |
| 172.27.10.10 / .11 (devel_9_1 node / proxy) | analytics node / Cloud Proxy | denied (no SSH credential available to the factory) |
| 172.27.10.14 / .15 (devel_8_18 node / proxy) | analytics node / Cloud Proxy | denied (no SSH credential available to the factory) |
| prod vcf-lab-operations (172.27.8.42) | n/a | port 22 connection refused |

The factory had an SSH credential for .12 only; the proxies and the other nodes were not readable.

CORRECTION to the footprint report: via `GET /api/adapters` the `VsanHostMetrics` instance `vsan-mgmt` runs on collector id 2, the Cloud Proxy, on all three devel instances (.13, .11, .15). It does NOT run on .14 (8.18.7 analytics node). The "slowest on .14" note there is really the proxy .15.

## Node 172.27.10.12 (devel, 9.0.2.0 build 25429562, Photon OS 5.0)

| Item | Value |
|---|---|
| Role | single analytics node; embedded collector (id 1) |
| vCPU / RAM | 2 / 7936 MB total, 7422 used, 116 free, 514 available, 1164 buff/cache; swap 861 of 4095 used |
| Uptime / load | 8d 3h; load 0.51 / 0.56 / 0.73 |
| Java | OpenJDK 17.0.16 (`/usr/java/jre-vmware-17`) |
| Analytics JVM | G1, `-Xms1958m -Xmx2304m`, RSS ~2.75 GB (5.4% CPU) |
| Collector JVM | `vcops-collector` -> `CollectorMain`, pid 6552, RSS 966 MB (944 MiB), VSZ 3.9 GB, 1.1% CPU |
| Collector `-Xms` / `-Xmx` | `-Xms205m -Xmx1024m` |
| Collector GC | `-XX:+UseParallelGC`, `-XX:MinHeapFreeRatio=20 -XX:MaxHeapFreeRatio=30`, `-XX:StringTableSize=80021`, `-XX:+HeapDumpOnOutOfMemoryError` (`/storage/db/vcops/heapdump/`), `-da` |
| Sets the heap | `/usr/lib/vmware-vcops/user/conf/collector/wrapper.conf.vcops` (`wrapper.java.initmemory=205`, `wrapper.java.maxmemory=1024`). The sibling `wrapper.conf` has `initmemory=128`, `maxmemory=` blank; the running process matches the `.vcops` file. The `.vcops` file is the generated one; the generator was not found by grep in install/ and support/. |
| How it derives | NOT VISIBLE. Same node's analytics heap is 1958/2304 in `analytics/wrapper.conf.vcops`, so sizing is per-process and per-node-size, but the formula was not located. Do not assume 1024 is fixed for other node sizes (INFERRED: scales with node size). |
| Other JVMs on node | Tomcat (`BootstrapWrapper`) RSS 1.34 GB; Gemfire 186 MB; two `start` JVMs ~460 MB each |
| GC log | `/storage/log/vcops/log/collector-gc-20261029152811.log` (current, 11.8 MB) plus 5 rotated `.gz`; `-Xlog:gc*,safepoint`, 5 files of 40 MB |

### Collector heap from the GC logs (ParOldGen, after each collection)

| Log (start) | Collections | Old-gen after GC, min to max | Old-gen capacity | Full GCs |
|---|---|---|---|---|
| 2026-09-21 | 22588 | 555 to 682 MB | 683 MB | 2072 |
| 2026-10-14 (a) | 196 | 2 to 670 MB | 683 MB | 22 |
| 2026-10-14 (b) | 4124 | 2 to 682 MB | 683 MB | 164 |
| 2026-10-17 | 23186 | 2 to 268 MB | 336 MB | 448 |
| 2026-10-26 | 6511 | 2 to 370 MB | 335 MB | 266 |
| 2026-10-29 (current, 8 days) | 13175 | 2 to 371 MB | 329 MB | 770 |

Full GC counts are `grep -c 'Pause Full'` per file, matched to files by name.

Latest Full GCs in the current log: `489M->236M(496M)` at 23:02 and `484M->230M(485M)` at 23:44 (7.0 s pause). The heap is ergonomically kept near 485 to 500 MB committed, well under the 1024 MB max; old-gen steady live set is ~230 to 306 MB; young gen ~150 to 160 MB.

Heap high-water: highest live old-gen seen in any retained log is 682 MB (Sept log, old-gen at its 683 MB cap, which is the signature of a period of memory pressure; 2026-10-14 logs show the same). Highest in the current 8-day window is 371 MB. Whole-heap max committed in the logs was not extracted beyond that; no `Maximum heap size` line was present in the current log header.

### Adapter instances on this node's collector (id 1) and their log folders

12 instances by `/api/adapters` on collector 1 (10 distinct adapter kinds named here; two kinds have two instances): Container, DiagnosticsAdapter, ManagementPackBuilderAdapter, SupervisorAdapter, VMWARE_INFRA_HEALTH, VMWARE_INFRA_MANAGEMENT, unifi_controller, vCenter Operations Adapter, vRealizeOpsMgrAPI, vcfcf_compliance. Log folder sizes in `/usr/lib/vmware-vcops/user/log/adapters/` (24 dirs, some are stale or case-duplicates of old MPB names):

| Folder | MB |
|---|---|
| DiagnosticsAdapter | 102 |
| VCommunityAdapter | 66 |
| VMwareAdapter | 44 |
| ComplianceAdapter | 44 |
| UniFiAdapter | 34 |
| VCOpsAdapter | 19 |
| MPBVCFContentFactoryUniFiIntegrationAdapter | 19 |
| ManagementAdapter | 18 |
| SynologyAdapter | 16 |
| VsanStorageAdapter | 14 |
| SupervisorAdapter | 14 |
| VMwareInfraHealthAdapter | 11 |
| all others (13 dirs) | 1 to 4 |

No `VsanHostMetrics` folder on this node, which agrees with it running on the proxy.

## Cloud Proxies (.13, .11, .15) and devel_9_1 / devel_8_18 nodes

Not readable (see top). From the API only: each proxy hosts `VsanHostMetrics` plus the vCenter/vSAN/ClusterPerfRisk/APPOSUCP/etc. instances. Instances on the proxy collector (id 2): devel 14, devel_9_1 19, devel_8_18 11. Proxy vCPU, RAM, collector Xmx, GC log, and Ops version of the proxies are UNKNOWN. Proxy types per API: UNIFIED_CLOUD_PROXY (9.x), CLOUD_PROXY (8.18).

## Container (Python SDK) memory

Not measurable on the readable node: `docker`, `podman`, `crictl`, `nerdctl`, `ctr` are all absent on .12, and no container process runs there. The container runtime for `VsanHostMetrics` is on the proxies (unreadable). Only the earlier API data stands: limit 1024 MB (`container_memory_limit`), usage ~80 to 92 (unit INFERRED MB). `/usr/lib/vmware-vcops/user/plugins/inbound/container_adapter/conf` and `VsanHostMetrics/conf` exist on .12 but no memory file was read there.

## Budget

The only collector JVM I could read is the embedded one on the 2 vCPU / 8 GB devel node: `-Xmx1024m`, ParallelGC, 12 adapter instances, heap committed ~485 to 500 MB. At steady state the live set after a Full GC is ~230 to 306 MB (cap-to-live), so about 790 MB of the 1024 MB max is unused by that measure. Against the highest live set in the current 8-day window (371 MB) the headroom is ~650 MB; against the worst retained log (682 MB live at a 683 MB old-gen cap, Sept) it is ~340 MB. State a new Java adapter instance's budget as at most about 10% of the 650 MB figure (~65 MB heap), and treat 340 MB as the number if the node ever repeats the September pressure. The node is itself memory-tight (514 MB available of 7.9 GB, 861 MB of swap in use), and the Oct 26 and Oct 29 logs show Full GCs in the hundreds with a 7 s pause, so adding heap pressure is not free here.

This is NOT the smallest collector in the lab: the three Cloud Proxies are probably smaller and host more instances, but could not be read. A proxy-based Java adapter budget stays UNKNOWN until one of those has a usable SSH credential.

## Could not read, and why

- Proxies .13 .11 .15, nodes .10 and .14: SSH denied; no credential available to the factory for them.
- Prod: sshd refuses connections on port 22.
- Collector heap formula (node size to Xmx): generator script not found by grep.
- Container memory settings for Python SDK adapters: runtime lives on the proxies.
- Live heap used right now: no `jcmd`/`jstat` on the node (only `java`, `jfr`, JMX is SSL with client auth); last GC line gave old-gen 306 MB of 337 MB at 00:09 UTC.
