# vsanperf T5, devel 9.0.2, build 22: metric_scope dashboard / all / dashboard (2026-11-07)

Upgrade 0.0.0.16 to `dist/vcfcf_sdk_vsanperf.0.0.0.22.pak` (1.2.0 build 22) on
devel 9.0.2 by `content-installer` (own log `install_devel.log`), instance
`f8ae0aaa-7a4a-4277-bc1d-00cb8c9d2b76`, Cloud Proxy collector 2, 5-minute
interval, one cluster (`vcf-lab-mgmt-cl01`, 5 hosts). Tiers host and cluster
on, disk and VM off, `vm_tier_every_n_cycles` 3 throughout. Times
America/Chicago (adapter log times are Z, minus 6 h). Settings were changed with
`PUT /api/adapters` (200); each change started a new engine (cycle numbering
restarted at 1) with no pak install in between. Adapter log:
`VsanPerfAdapter_7083.log` on the proxy, read over SSH with key auth.

| Step | Result |
|---|---|
| 1. Pre-state | **recorded**: solution 0.0.0.16; `perf_timing_logging` false, tier_vm false, N 3, no `metric_scope`; last three cycles (stat labels 09:57 / 10:02 / 10:07) perf_calls 23, 23, 23; series_pushed 1,186 x3; cycle_seconds 3.69 / 4.81 / 3.99; perf_call_ms_avg 136 / 202 / 168; push_batches_failed 0; optional_calls_failed 0; last_error `none` |
| 2. Upgrade | **pass**: install exit 0 (started 10:11, "Install completed and verified" about 10:16); solutions endpoint 0.0.0.22; CLI found the instance FAILED/NONE at +122 s and re-sent start, then STARTED; first cycle 10:17:58 (26 calls, 2,372 series); `metric_scope` present with value `dashboard`; the other settings unchanged |
| 3. Default scope | **pass**: cycles 1 to 4 (10:17:58, 10:23:27, 10:28:21, 10:32:49): perf_calls 26, 26, 26, **23**; series_pushed 2,372 (two buckets), 1,186, 1,186, 1,186; cycle_seconds 18.5 / 46.5 / 40.4 / 8.2 (service slow for three cycles, perf_call_ms_avg 681 / 1,783 / 1,550 / 354); optional_calls_failed, push_batches_failed, every `*_unresolved`, entities_unparsed 0; last_error `none`; esx01 219 keys, cl01 91 keys; `stats/latest` advanced 10:10 to 10:20 to 10:25 (host `DOM Owner\|iops` 1802, 1253, 1158; cluster `Capacity\|usedBytes` 9668722952672, 9668883889751, 9669061005263) |
| 4. Scope `all` | **pass with differences from the README** (table below). Set 10:33:03 with `perf_timing_logging` true. Keys on the host 1,282, on the cluster 348 |
| 5. Read-back | **pass** (table below) |
| 6. Back to `dashboard` | **pass**: set 10:53:36 (timing off). Cycles at 10:57:50, 11:02:48, 11:07:56, 11:12:54: perf_calls 26, 26, 26, **23**; series_pushed 2,372, 1,186, 1,186, 1,186; cycle_seconds 8.5 / 6.7 / 11.4 / 8.6; optional_calls_failed 0; `learned skips=3` on the fourth. Keys pushed under `all` stay on the objects (Ops keeps them): esx01 still 1,282 keys, cl01 still 348, but the `all`-only keys get no newer sample (System Memory, pCPU, ESA Dedup keys last at the 10:50:00 bucket, read at 11:13), while `DOM Owner\|iops` / `Capacity\|usedBytes` advanced to 11:05:00 |
| 7. Error check | **pass for the pak**: adapter log since 10:17: 0 ERROR, 0 stack-trace markers, 0 `session[`, 0 `password`; WARN lines 4 (the four cycle-1 faults below). collector.log since 10:17: 0 ERROR or stack lines mention vsanperf, 0 `session[`; 219 ERROR lines belong to other adapters (vmwareinfrahealth, WCP, container metrics, vCenter availability); 3 lines contain `password`, all the standard vSphere `InvalidLogin ... incorrect user name or password` fault text of another adapter's account, no credential value |

**Step 4, cycles at `metric_scope=all`** (times from the adapter log; `PERF cycle` / `cycle N summary`):

| Cycle | Time | perf_calls (core/host/cluster) | series_pushed | cycle_s | call_ms_avg | optional_calls_failed | learned skips | `*_unresolved`, entities_unparsed, push_batches_failed |
|---|---|---|---|---|---|---|---|---|
| 1 | 10:38:29 | 56 (3/34/19) | 13,516 (2 x 6,758) | 48.4 | 846 | 4 | 0 | 0 |
| 2 | 10:43:24 | 54 (3/33/18) | 6,758 | 43.0 | 793 | 4 | 2 | 0 |
| 3 | 10:48:20 | 54 (3/33/18) | 6,758 | 39.1 | 718 | 4 | 2 | 0 |
| 4 | 10:52:56 | **37** (3/21/13) | 6,758 | 14.4 | 383 | 0 | 19 | 0 |

6,758 = core 2,060 + host 4,350 + cluster 348. `last_error` read `none` after
cycle 4; it was not sampled during cycles 1 to 3, so whether it named a fault
there is not recorded. `PERF tier` lines: `scope=all`, labels_dropped core 240
(`Actual` twins, e.g. `vsan-pnic-net`), host 85, cluster 0; the dropped-label
INFO was logged once per type (vsan-pnic-net, vsan-tcpip-stats, vsan-vnic-net).

Learning, from the adapter log:

- Cycle 1: `cluster-pmem` and `host-pmem` answered `pmemisunavailable`, logged
  "does not offer ... (NotSupported); not queried there for about 24 h".
- Cycle 1 to 3: four optional host-tier types faulted `InvalidArgument`
  ("A specified parameter was not correct: entityRefId", HTTP 500) and were
  logged WARN once, in cycle 1: `heap-memory`, `slab-memory`, `clom-host`,
  `cmmds-workload` (counted in optional_calls_failed 4 each cycle); at the
  third fault, 10:48:16: "faulted (InvalidArgument) 3 cycles in a row; not
  queried there for about 24 h".
- Cycle 3, 10:47:49 to 10:48:19: 13 types "answered empty 3 cycles in a row":
  `vsan-direct-cluster`, `vsan-file-service`, `cluster-resync`,
  `cluster-remotedomclient`, `computeCluster-remotedomclient`,
  `vsan-direct-host`, `lsom-world-cpu`, `vsan-distribution`,
  `host-remotedomclient`, `computeHost-remotedomclient`, `vsan-iscsi-host`,
  `vsan-iscsi-target`, `vsan-iscsi-lun`. `ioinsight` answers empty every cycle
  and stays called.
- Cycle 4: 19 learned skips = 13 empty + 4 faulted + 2 pmem; 56 - 19 = 37.

**Step 5, read-back** (esx01 = `vcf-lab-mgmt-esx01`, cl01 = `vcf-lab-mgmt-cl01`;
three reads, bucket and value; epochs are multiples of 300,000 ms, for example
1794069600000 = 10:40:00):

| Key | Read 10:43:54 (10:40 bucket) | Read 10:53:29 (10:45) | Read 11:13:10 (10:50) |
|---|---|---|---|
| esx01 `vSAN Perf\|System Memory\|totalMbMemUsed` (`system-mem`) | 143,633 | 143,201 | 143,033 |
| esx01 `vSAN Perf\|System Memory\|pctMemUsed` | 55 | 55 | 55 (integer percent) |
| esx01 `vSAN Perf\|pCPU:cpu-0\|pcpuUsedPct` (instanced) | 12 | 14 | 13 |
| esx01 `vSAN Perf\|pCPU\|pcpuUsedPct` (aggregate) | 22 | 24 | 21 |
| esx01 `vSAN Perf\|ESA Dedup DOM Owner\|dedupHashWriteLeafOwnerCountLocal` (no unit suffix; 9.1.1 label not in the Python model) | 219,884 | 240,955 | 235,625 |
| esx01 `vSAN Perf\|ESA Dedup DOM Owner\|dedupChunkReadCongestion` | 0 | 0 | 0 |
| esx01 `vSAN Perf\|ESA Dedup Chunk Service\|totalNumRefCnt` | 163,731,729 | 163,765,410 | 163,781,428 |
| cl01 `vSAN Perf\|Data Protection\|totalSnapshotCapacity` (`vsan-dp-historical-stats`) | 64,257,117,696 | same | same |
| cl01 `vSAN Perf\|ESA Dedup DOM Owner\|dedupChunkReadCongestion` | 0 | 0 | 0 |

Key counts with the `vSAN Perf|` prefix: **esx01 1,282** (122 groups: 66 `DOM World:<name>`
instances, 32 `pCPU:cpu-N`, `pNIC:vmnic1/2`, `TCP/IP:defaultTcpipStack`,
`vNIC:vmk2`, `vNIC RDT Latency:vmk2`), **cl01 348** (12 groups: ESA Dedup DOM
Owner 82, DOM Owner 46, ESA Dedup DOM Client 42, DOM Comp Mgr 42 and so on).
`cluster-resync` answered empty on this lab (entities=0), so the cluster key
from a newly added type is from `vsan-dp-historical-stats`. The cl01 first
all-scope read (10:43:39) already carried the 10:35 bucket from cycle 1 (pushed
10:38:29), more than 5 minutes later; the 6-minute wait was not needed as a
separate step.

**Differences from the README's expectations**

- Calls: cycle 1 **56** (README 63), cycles 2 and 3 **54** (61), steady **37**
  (39). Only **four** of the nine Q5 types are called on this tier set
  (`heap-memory`, `slab-memory`, `clom-host`, `cmmds-workload`), not nine; the
  other five were not observed and are presumably in tiers that are off here
  (not verified). `ioinsight` accounts for the rest of the steady count.
  Reconciliation (orchestrator, from `EntityType.java`): the README's check 7
  assumed all four tiers on; this run kept the account's tiers (host and
  cluster). The five Q5 types not seen are `clom-disk` and `ddh-disk`
  (`Tier.DISK`) and `remote-virtual-machine`, `remote-vscsi`,
  `remote-virtual-disk` (`Tier.VM`), so the call counts and the 13 instead of
  16 learned-empty types are the tier set, not a defect. The disk and VM
  tiers at scope `all` remain unproven on a live instance (replay harness
  T4 rows d, d', e only).
- Learned-empty: 13 types, not 16.
- Series: `series_pushed` 6,758 is the push count, not the key count; the
  1,282 host and 348 cluster keys match "about 1,280 and 348". The same gap
  exists at dashboard scope (1,186 pushed against 219 + 91 keys per object).
- On the return to `dashboard` the first cycle made 26 calls (as the task
  said), not the README's 30; steady 23 from cycle 4, not 25.
- Cycle times are long on `all` (48 / 43 / 39 s, then 14 s) because the service
  answered slowly (call_ms_avg 700 to 850 ms, against 130 to 400 ms on the
  default scope); the same slowdown showed in the dashboard cycles 2 and 3
  after the upgrade (46 and 40 s, 1.5 to 1.8 s per call). Nothing failed or
  timed out.

Left in place: pak 0.0.0.22, `metric_scope` `dashboard`, `perf_timing_logging`
false.
