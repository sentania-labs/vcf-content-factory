# vsanperf T5, devel 9.1.1.0, build 22: metric_scope default (dashboard) (2026-11-07)

Upgrade 0.0.0.18 to `dist/vcfcf_sdk_vsanperf.0.0.0.22.pak` (1.2.0 build 22) on
devel 9.1 (`devel_9_1`, vcf-lab-operations-devel-91) by `content-installer`
(own log `install_devel_9_1.log`), instance
`15739079-052f-4c20-847a-6a2dac8f1759` (`vsanperf-91-accept`), Cloud Proxy
collector 2 (172.27.10.11), 5-minute interval, one cluster (`vcf-lab-mgmt-cl01`,
5 hosts). Tiers host and cluster on, disk and VM off, `vm_tier_every_n_cycles` 3.
Default scope only: `metric_scope` was never changed, no vCenter write, no
setting change. Times America/Chicago; self-metric times are the 5-minute stat
bucket labels (:x1:59 / :x6:59), which sit about a minute after the cycle.

| Step | Result |
|---|---|
| 1. Pre-state | **recorded**: solution 0.0.0.18; settings tier_host true, tier_cluster true, tier_disk false, tier_vm false, N 3, perf_timing_logging false, **no `metric_scope`**; last three cycles (11:05 / 11:10 / 11:15) perf_calls 23, 23, 23; series_pushed 1,186 x3; cycle_seconds 5.13 / 5.22 / 4.32; perf_call_ms_avg 208 / 215 / 175; clusters_ok 1; push_batches_failed, optional_calls_failed, every `*_unresolved`, entities_unparsed 0; last_error `none` |
| 2. Upgrade | **pass**: install exit 0 (started 11:16, "Install completed and verified" about 11:25); solutions endpoint 0.0.0.22; CLI read the instance FAILED at +133 s (the collector had not yet loaded the new adapter type; one collector.log ERROR at 11:20:29, "Unknown adapter type ... (Type = vcfcf_vsanperf)", from the CLI's own start-monitoring during the install) and re-sent start, then STARTED; collector loaded adapter version 0.0.0.0.0.22 at 11:24; instance id unchanged; `metric_scope` present with value `dashboard`, all other settings unchanged |
| 3. Three cycles and one more | **pass** (table below), zero failures, last_error `none` |
| 4. Read-back | **pass** (table below) |
| 5. Logs | **pass for the pak**, with a location deviation (below) |

**Step 3, cycles after the upgrade** (cycle 1 is the first on the new jar):

| Cycle | Bucket | perf_calls | series_pushed | cycle_s | call_ms_avg | failure and unresolved counters |
|---|---|---|---|---|---|---|
| 1 | 11:26 | 26 | 2,372 (two buckets) | 8.52 | 279 | 0 |
| 2 | 11:32 | 26 | 1,186 | 11.77 | 444 | 0 |
| 3 | 11:36 | 26 | 1,186 | 17.72 | 665 | 0 |
| 4 | 11:41 | **23** | 1,186 | 5.05 | 210 | 0 |

Counters read: clusters_failed, clusters_timed_out, clusters_unresolved,
hosts_unresolved, vms_unresolved, disks_unresolved, vdisks_unresolved,
push_batches_failed, optional_calls_failed, entities_unparsed (all 0 each
cycle); clusters_ok 1; `Collection|last_error` `none` after cycle 4 (read
at 11:27, 11:33 and 11:42 as `none`; not sampled between). Matches the 9.0.2
leg: 26, 26, 26, then 23; 2,372 then 1,186. Cycles 2 and 3 were slow on the
service side (0.4 to 0.7 s per call), same pattern as 9.0.2 and build 18.

**Step 4, read-back** (esx01 = `vcf-lab-mgmt-esx01`, cl01 = `vcf-lab-mgmt-cl01`,
`stats/latest`; the key counts are unchanged from build 18):

| Key | Read 11:27 | Read 11:33 | Read 11:42 |
|---|---|---|---|
| esx01 `vSAN Perf\|DOM Owner\|iops` | 665 (11:20:00) | 688 (11:25:00) | 578 (11:35:00) |
| cl01 `vSAN Perf\|Capacity\|usedBytes` | 9668388716544 (11:20:00) | 9668540760064 (11:25:00) | 9668698046464 (11:35:00) |

The 11:20 sample is the last before the pak finished installing; the latest
sample timestamp then moved to 11:25 and 11:35, past the upgrade. Key counts
with the `vSAN Perf|` prefix: esx01 **219**, cl01 **91**, the same as build 18
(no `all`-scope keys appeared).

**Step 5, logs.** The per-instance file `VsanPerfAdapter/VsanPerfAdapter_*.log`
on the proxy (read over SSH, key auth) has no new lines: the only files there
(`_2340`, `_2342`) were last written 2026-11-06 22:01, so there is no adapter
log for the running instance to count against. The check was made on
`collector.log` on 172.27.10.11 since 11:20:
vsanperf lines 12 (class-loading NOTICEs and the one ERROR above); ERROR
lines naming vsanperf or vcfcf after 11:24 (new jar loaded): **0** (210 other
ERROR lines belong to other adapters, for example EsxHealthOrchestrator);
stack-trace lines under a vsanperf line: 0 (the grep hits were EsxHealth
frames); `session[` anywhere in the window: 0; `password` on vsanperf lines: 0.
The WARN lines in the old `_2342` file (RESOURCE_STATUS_DOWN, 2026-11-06) are
from the earlier build, not this run. Whether the new build writes its own
adapter log, and where, was not established.

**Deviations from expectation:** none in the numbers. Two notes: (1) the
single collector.log ERROR at 11:20:29 during the upgrade window, caused by
the instance start sent before the new adapter type loaded, self-cleared on the
CLI's re-send; (2) no per-instance adapter log content to read (above), so
step 5 rests on collector.log.

Left in place: pak 0.0.0.22, `metric_scope` `dashboard`, `perf_timing_logging`
false. Nothing committed.
