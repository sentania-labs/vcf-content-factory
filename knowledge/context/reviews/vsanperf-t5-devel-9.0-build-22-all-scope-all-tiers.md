# vsanperf T5, devel 9.0.2, build 22: metric_scope all with all four tiers, then back (2026-11-07)

Build 22 (0.0.0.22) already installed on devel 9.0.2 (instance
`f8ae0aaa-7a4a-4277-bc1d-00cb8c9d2b76`, Cloud Proxy collector 2, 5-minute
interval, `vcf-lab-mgmt-cl01`, 5 hosts); no pak install, no vCenter write. All
settings changes were `PUT /api/adapters` (200), each starting a new engine
(cycle numbering restarts at 1). Times America/Chicago (adapter log times are Z,
minus 6 h). Adapter log: `VsanPerfAdapter_7083.log` on the proxy, read over SSH
with key auth; self-metrics and keys through the Suite API on profile `devel`.
Method as in `vsanperf-t5-devel-9.0-build-22-metric-scope.md`.

**A second vSAN cluster joined the collection at cycle 3 and is in every
number below.** `vcf-lab-osa-probe-cl01` (`domain-c39146`, 3 hosts, 6 disks in the
disk map) went from `in_scope=1` (cycle 2, "clusters=2 in_scope=1") to
`in_scope=2` (cycle 3, `trigger=change`); it was not created by this run. Its
Performance Service has no master: every type answers HTTP 500
`com.vmware.vsan.perfsvc.fault.masternotfound` ("The object or item referred to
could not be found"). Totals (self-metrics) are therefore both clusters; the
`cl01` columns come from `PERF cluster` lines (timing logging on). It stays
`clusters_failed=1`, costs 61 calls (67 on its VM run) every cycle under `all`
and **26 under `dashboard`**, and is never learned (NotFound is not a learned
fault; only its two `NotSupported` pmem types are). `last_error` carries one of
its faults throughout. Nothing in the pak was wrong; the cl01 data pushed
normally.

| Step | Result |
|---|---|
| 1. Pre-state | **recorded**: scope `dashboard`, tier_host/cluster true, disk/vm false, N 3, timing false; stat labels 16:13 / 16:18 / 16:23: perf_calls 23 x3; series_pushed 1,186 x3; cycle_seconds 3.66 / 4.42 / 91.17 (service slow on the last, perf_call_ms_avg 155 / 188 / 3,957); optional_calls_failed 0, push_batches_failed 0, every `*_unresolved` 0, entities_unparsed 0; last_error `none` |
| 2. Set | **pass**: 16:25:58, one PUT: `metric_scope` all, `tier_disk` true, `tier_vm` true, `perf_timing_logging` true; N 3 unchanged; read back as set |
| 3. Cycles | **pass with differences** (table below): 12 cycles, 16:28 to 17:23 |
| 4. Faulting and learned | **pass**: all nine Q5 types observed faulting and learned; 16 learned-empty (list below) |
| 5. Keys and read-back | **pass** (below) |
| 6. Footprint | collector JVM (the adapter runs inside `vcops-collector`, pid 9902) RSS 2,934,256 KB before (16:25), 2,972,872 KB at 17:10, 2,925,452 KB at 17:24; no growth. Adapter `heap_before/after` 0.73 to 1.23 GB across cycles. Host `free`: used 7,925 MB before, 7,972 MB at 17:10 |
| 7. Log check | **pass**: adapter log from the set to 17:51: 0 ERROR, 0 stack-trace markers, 0 `session[`, 0 `password`; WARN 117 (89 up to cycle 12: 74 are the probe cluster's masternotfound faults, logged once per type per refresh, 15 are the cl01 InvalidArgument faults logged once in cycle 1 and once in cycle 3 for the VM types; 28 more after the revert, all probe cluster) |
| 8. Revert | **pass for cl01, see below**: one PUT 17:25:03 (scope `dashboard`, disk false, vm false, timing false), read back as set |

**Step 3, cycles at `metric_scope=all`, all four tiers** (VM = a cl01 VM run;
"probe VM" = the probe cluster's staggered VM run; totals are both clusters,
the tier split is of the total; self-metrics and the adapter log agree on
perf_calls, series_pushed, cycle_seconds and call_ms_avg for every cycle):

| Cycle | Time | perf_calls total (core/host/cluster/disk/vm) | cl01 / probe calls | series_pushed (core/host/cluster/disk/vm) | cycle_s | call_ms_avg | optional_calls_failed | learned skips | push_ms | VM |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 16:28:27 | 63 (3/34/19/7/0) | 63 / not in scope | 14,056 (4,120/8,700/696/540/0) | 12.7 | 185 | 6 | 0 | 266 | no |
| 2 | 16:33:23 | 61 (3/33/18/7/0) | 61 / not in scope | 7,028 (2,060/4,350/348/270/0) | 9.1 | 146 | 6 | 2 | 116 | no |
| 3 | 16:38:27 | 130 (6/67/37/14/6) | 67 / 63 | 10,764 (.../3,736) | 11.8 | 117 | 67 | 2 | 306 | **cl01** |
| 4 | 16:43:23 | 100 (6/54/31/9/0) | 39 / 61 | 7,028 | 7.9 | 112 | 58 | 26 | 170 | no |
| 5 | 16:48:44 | 106 (6/54/31/9/6) | 39 / 67 | 7,028 | 28.6 | 298 | 64 | 26 | 270 | probe |
| 6 | 16:53:25 | 106 (6/54/31/9/6) | 45 / 61 | 10,745 (.../3,717) | 9.2 | 115 | 61 | 26 | 265 | **cl01** |
| 7 | 16:58:25 | 100 | 39 / 61 | 7,028 | 8.8 | 128 | 58 | 26 | 132 | no |
| 8 | 17:03:25 | 106 | 39 / 67 | 7,028 | 8.9 | 118 | 64 | 26 | 184 | probe |
| 9 | 17:08:26 | 106 | 45 / 61 | 10,764 | 9.4 | 127 | 61 | 26 | 301 | **cl01** |
| 10 | 17:13:23 | 100 | 39 / 61 | 7,028 | 7.2 | 109 | 58 | 26 | 136 | no |
| 11 | 17:18:27 | 106 | 39 / 67 | 7,028 | 10.4 | 130 | 64 | 26 | 139 | probe |
| 12 | 17:23:22 | 103 (6/54/31/9/3) | **42** / 61 | 10,745 | 5.7 | 84 | 58 | 29 | 319 | **cl01** |

Every row: `*_unresolved` (hosts, clusters, disks, vms, vdisks) 0, entities_unparsed 0,
push_batches_failed 0 (`push batches ok` 4 on the first cycle and VM cycles, 2
otherwise). `last_error` named a probe-cluster `vsan-cluster-capacity`
NotFound at every sampling (16:38 onward); at 16:23 (pre) `none`. `series_pushed`
7,028 = 5 x 1,336 + 348 (core 2,060 + host 4,350 + cluster 348 + disk 270);
the VM adds 1,868 per bucket x 2 buckets (3,736; 3,717 on cycles 6 and 12 where
one bucket carried 29 VMs, 1,849 values), 30 VMs. Cycle 1 pushes both buckets
(14,056 = 2 x 7,028). `PERF tier` per cl01 cycle: core 3, host 33/21, cluster
18/13, disk 7/2, VM 6/3 calls; core `labels_dropped` 240, host 85, cluster 0;
call_ms_sum 11.6 s and 8.9 s at cycles 1 and 2. `PERF push` lines (all `result=ok`):
cluster 348 values, about 34 KB, 26 to 56 ms; HostSystem 5 resources, 6,680
values, about 646 KB, 83 to 214 ms; VirtualMachine 30 resources, 1,868 values,
about 159 KB, 42 to 61 ms (13 + 13 + 8 batches).

cl01 alone, against the README's check 7.2: cycle 1 **63** (63), cycle 2 **61**
(61), cycle 3 **67** (67 on the VM run), cycles 4, 5, 7, 8, 10, 11 **39** (39),
VM runs at cycles 6 and 9 **45** (42 expected: the three VM-only Q5 types are
still called until the third VM run), VM run at cycle 12 **42** (42). So the
README holds for cl01 once the VM learning (three VM runs, cycle 9) has settled;
the first two VM runs after the set cost 45, not 42, and the README's "(VM types:
on the first three VM runs)" matches that.

**Step 4, faulting and learned** (cl01 = `domain-c6004`; times of the adapter's
"not queried there for about 24 h" line):

- Nine Q5 types, all `InvalidArgument` ("A specified parameter was not correct:
  entityRefId", HTTP 500), WARN once at first fault:
  - host and disk tier, first fault cycle 1 (16:28:27), learned cycle 3
    (16:38:23 to :25): `heap-memory`, `slab-memory`, `clom-host`,
    `cmmds-workload`, `clom-disk`, `ddh-disk`. Counted in optional_calls_failed
    (6 on cycles 1 and 2).
  - VM tier, first fault cycle 3 (16:38:26, the first cl01 VM run), learned at
    the third VM run, cycle 9 (17:08:25, "faulted (InvalidArgument) 3 VM runs in
    a row"): `remote-virtual-machine`, `remote-virtual-disk`, `remote-vscsi`.
    The VM-tier `failed` counter (3) falls to 0 on the VM run at cycle 12 (3
    calls, not 6).
- `cluster-pmem` and `host-pmem`: "does not offer ... (NotSupported)" cycle 1 on
  cl01 (16:28:19, :24), cycle 3 on the probe cluster (16:38:17, :18).
- **Learned-empty on cl01, 16** (cycle 3, 16:38:18 to :25, "answered empty 3
  cycles in a row"): `vsan-direct-cluster`, `vsan-file-service`,
  `cluster-resync`, `cluster-remotedomclient`, `computeCluster-remotedomclient`,
  `vsan-direct-host`, `lsom-world-cpu`, `vsan-distribution`,
  `host-remotedomclient`, `computeHost-remotedomclient`, `vsan-iscsi-host`,
  `vsan-iscsi-target`, `vsan-iscsi-lun` (the 13 of the host+cluster run) plus the
  disk tier's `cache-disk`, `capacity-disk`, `disk-group`. `ioinsight` answers
  empty every cycle and stays called.
- Learned skips: 26 from cycle 4 = cl01 16 empty + 6 Q5 + 2 pmem, plus the probe
  cluster's 2 pmem; 29 from cycle 12 (+3 VM Q5 types).
- Probe cluster: not learned. All its types except the pmem pair fault NotFound
  every cycle (61 calls, 67 on its VM run, 58 / 64 optional failures).

**Step 5, key counts** (`vSAN Perf|` prefix; `stats/latest`, esx01 =
`vcf-lab-mgmt-esx01`, cl01 = `vcf-lab-mgmt-cl01`):

- esx01 **1,336** keys, 124 groups (read 16:49 with `currentOnly=true`; the same
  1,336 with `currentOnly=false` at 17:51). The `all`-scope host-tier keys are
  1,282, as in the host+cluster run; the disk tier adds **54**: the disk tier
  stitches to the **HostSystem** (no separate disk object), instance
  `ESA Disk Layer:<disk uuid>` and `ESA Disk SCSI:<disk uuid>`, one disk uuid per
  host here (disk map count=5, 10 entities, 270 series_kept per cycle). Largest
  groups: DOM Owner 272, ESA Dedup DOM Owner 82, DOM Comp Mgr 72, ZDOM VTX 71,
  DOM Client 68, Memory 50.
- cl01 **348** keys, 12 groups (ESA Dedup DOM Owner 82, DOM Owner 46, ESA Dedup
  DOM Client 42, ESA Dedup DOM Comp Mgr 42, ...), unchanged; the disk and VM
  tiers add nothing to the cluster object.
- VM with the most keys: `vcf-lab-automation-runtime-vn26h` (`3e743185-94dd-4683-a3d0-6dcab8b75769`)
  **272** keys = `VM` 8 + 72 `Virtual Disk:<bus>` + 192 `vSCSI:<scsi>` over 12
  and 24 instances. 30 VMs carry `vSAN Perf|` keys; next are `vcf-lab-vcenter-mgmt`
  and `vcf-lab-vcenter-wld01` 195, `vcf-lab-vcenter-wld02` 173, two runtimes 129.

Read-back of `all`-only keys (REFERENCE.md scope column `all`): the disk key
`vSAN Perf|ESA Disk Layer:52585910-fedf-604c-04d3-868955bf7f7d|iopsReadPerf` on
esx01 and the VM key `vSAN Perf|VM|readCount` / `writeCount` on the VM above
(`ESA Disk Layer ... iopsReadCapacity`, a dashboard key, and the VM `iopsWrite`
shown for comparison). Epochs are multiples of 300,000 ms.

| Key | Read 16:49 (VM bucket 16:35, cycle 3 push) | Read 17:10:03 (17:05) | Read 17:24:46 (17:20) |
|---|---|---|---|
| esx01 disk `iopsReadPerf` (`all`) | not read | 11 | 16 |
| esx01 disk `iopsWritePerf` (`all`) | not read | 6,818 | 8,094 |
| esx01 disk `avgLatReadPerf` (`all`, us) | not read | 383 | 2,555 |
| esx01 disk `iopsReadCapacity` (dashboard) | not read | 2,344 | 3,435 |
| VM `readCount` (`all`) | 2,067 | 2,037 | 1,838 |
| VM `writeCount` (`all`) | 128,200 | 119,040 | 114,486 |
| VM `iopsWrite` (dashboard) | 421 | 391 | 374 |
| esx01 `System Memory\|totalMbMemUsed` | | 142,272 | 145,012 |

The VM bucket at 17:05 and 17:20 were pushed by VM runs (cycles 9 and 12); the
disk buckets advance every cycle. Not done: the same-window JSON query of the
Performance Service for each value, and the browser pass.

**Step 8, revert** (set 17:25:03, timing off, so no `PERF` lines; totals from
the `cycle N summary` and self-metrics, both clusters):

| Cycle | Time | perf_calls total | series_pushed | cycle_s | call_ms_avg | optional_calls_failed | learned skips |
|---|---|---|---|---|---|---|---|
| 1 | 17:28:21 | 52 | 2,372 | 3.7 | 84 | 23 | 0 |
| 2 | 17:33:20 | 52 | 1,186 | 3.5 | 90 | 23 | 0 |
| 3 | 17:38:22 | 52 | 1,186 | 3.4 | 90 | 23 | 0 |
| 4 | 17:43:22 | **49** | 1,186 | 3.7 | 96 | 23 | 3 |
| 5 | 17:48:22 | 49 | 1,186 | 3.1 | 92 | 23 | 3 |

The probe cluster contributes 26 calls and 23 failures every cycle (all its
non-core types; 3 core calls), so cl01 is 52 - 26 = **26** on the first cycle
(then 26, 26) and 49 - 26 = **23** from cycle 4 (three `dashboard` empties
learned at 17:38:20: `vsan-direct-cluster`, `vsan-file-service`,
`vsan-direct-host`); series 2,372 then **1,186**, as in the earlier record. The
split is by subtraction, not read from a `PERF cluster` line. Keys pushed under
`all` stay on the objects: esx01 still 1,336 with `currentOnly=false` (the 54
disk keys' last bucket 17:20, the host `all`-only keys likewise), but
`currentOnly=true` returned 1,282 at 17:51, without the disk keys.

**Differences from the README's check 7 expectations**

- cl01 matches 63 / 61 / 61 then 39, and 67 on the VM run; the VM-run steady 42
  only from the fourth VM run (cycle 12); VM runs 1 to 3 (cycles 3, 6, 9) made
  67 / 45 / 45 (README text: nine Q5 types learned after three faults, VM types
  on the first three VM runs: consistent, but the 42 steady is not in the
  README's "from cycle 4" wording; for the VM tier it is cycle 12 at N = 3).
  Totals on this instance differ because of the probe cluster: 130 / 100 /
  106 / 103, not 69 / 42.
- Nine Q5 types: nine observed (the previous record saw four). Learned-empty:
  **16** as in the README (the previous host+cluster run saw 13; the disk tier's
  `cache-disk`, `capacity-disk`, `disk-group` are the other three).
- Disk tier: 7 calls cycles 1 to 3 (2 steady after `clom-disk` and `ddh-disk`
  are learned and the three OSA disk types learned empty), 270 series, 54 keys
  per host on a single disk uuid.
- Revert: first cycle 26 and steady 23 on cl01 as the previous record, not the
  README's 30 and 25 (inferred, see above).
- Not in the README: a cluster whose Performance Service has no master
  (`masternotfound`) is called in full every cycle forever (26 calls under
  `dashboard`, 61 to 67 under `all`) because NotFound is not a learned fault.
  It does not fail the other clusters or the pak, but it is about 60 % of the
  steady `all` calls and half of the `dashboard` ones on this instance, and it
  holds `clusters_failed=1` and `last_error` for the whole run. Worth a decision
  on whether a cluster-wide `masternotfound` should be learned like the others.
- Service speed: this window ran fast (call_ms_avg 84 to 185 apart from cycle
  5, 298 at 28 s cycle), against 700 to 850 ms in the previous record and the
  91 s pre-state cycle.

Left in place: pak 0.0.0.22, `metric_scope` `dashboard`, `tier_disk` false,
`tier_vm` false, `perf_timing_logging` false, tiers host and cluster on, N 3.
