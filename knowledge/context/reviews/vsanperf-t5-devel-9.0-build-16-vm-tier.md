# vsanperf T5, devel 9.0.2, build 16: VM tier on, push timings (2026-11-07)

Upgrade 0.0.0.12 to `dist/vcfcf_sdk_vsanperf.0.0.0.16.pak` on devel 9.0.2
(instance `f8ae0aaa-7a4a-4277-bc1d-00cb8c9d2b76`, Cloud Proxy collector 2),
then `tier_vm=true`, `vm_tier_every_n_cycles=1`, `perf_timing_logging=true`
set 02:12:36 to 02:12:39 via the Suite API (no restart); reverted
02:31:14 (tier_vm false, N 3; timing off afterwards). Times America/Chicago;
log times Z.

| Check | Result |
|---|---|
| Solution version | 0.0.0.12 before, 0.0.0.16 after; CLI restarted the instance at +121 s; new jar confirmed by the VM keys |
| a. Self-metrics | **pass**: cycles 02:16:32 / 02:21:32 / 02:26:44: perf_calls 29 = 26 + 3 VM calls (3 core + 13 host + 10 cluster + 3 VM). The 26 before the change shows nothing had been learned yet: the post-upgrade restart at +121 s had cleared the in-memory learned-empty state and fewer than three cycles ran before 02:12:36, so this run neither shows nor contradicts the design's reset-on-reconfigure (build 10 review: a reconfigure builds a new CycleEngine). The first VM-tier cycle's 5,988 = 2 x 2,994 shows the cluster and host tiers re-sent both buckets, which only happens when the dedup marks were rebuilt: direct evidence that the reconfigure built a new engine, series_pushed 5,988 then 2,994 then 2,955, cycle_seconds 12.5 / 8.4 / 7.6, perf_call_ms_avg 254, every *_unresolved, optional_calls_failed and push_batches_failed 0, last_error `none` |
| b. VM keys | **pass**: 30 of 109 VirtualMachines (the powered-on mgmt-cluster VMs) carry `vSAN Perf\|` keys; per-VM counts 17 to 270 depending on disk count; sample `vcf-lab-automation-runtime-vn26h` 270 keys all at the 02:20:00 bucket: `VM\|iopsWrite` 386, `VM\|latencyWriteUs` 14331, `Virtual Disk:scsi0:0\|NIOPS` 423, `vSCSI:scsi0:0\|iopsWrite` 330, `vSCSI:scsi0:0\|throughputWriteBytesPerSec` 4638570; 27 distinct Virtual Disk and vSCSI instances across the 30 VMs, all `scsiN:M`; 1,769 of 1,808 latest values at 02:20:00, 39 at 02:15:00 |
| c. Hosts and cluster | **pass**: esx01..05 still 219 keys each; cluster 91 |
| Collector log (SSH, key auth) | per-type `PERF call` lines for all 29 calls (virtual-disk 148 entities / 444 series / 20 KB wire / 371 ms; vscsi 148 / 1,184 / 24 KB / 631 ms; virtual-machine 30 / 180 / 4.8 KB / 132 ms); `PERF cycle` perf_phase_ms 7,385 to 10,528, push_ms 149 to 399, cycle_ms 7,573 to 12,521; `PERF inventory` clusters_hosts 32 ms; no `session[` / password |

**Push cost, verbatim `PERF push` lines** (the number the replay harness needed):

```
kind=ClusterComputeResource resources=1  stat_values=91   bytes~8106   ms=55 / 69 / 56 / 54
kind=HostSystem             resources=5  stat_values=1095 bytes~97160  ms=74 / 51 / 61 / 47
kind=VirtualMachine         resources=30 stat_values=1808 bytes~155226 ms=70 / 80 / 113 / 48
```

So a Suite API stats push costs a fixed ~50 to 60 ms per call plus at most
~1 to 2 ms per resource ((113 - 55) / 30), not the 9 ms per resource the
harness had extrapolated from a single 5-host batch; the replay model is
corrected in build 18 (60 ms per call + 1.5 ms per resource). Under that
model the harness reports 38 to 76 s of pushing per cycle at 70 clusters
with the VM tier every 3rd cycle and 74 to 150 s with it every cycle
(batches are per kind and sample time, so they are not perfectly packed and
the first cycle carries two buckets); a perfectly packed lower bound would
be 168 batches x ~210 ms, about 35 s.
