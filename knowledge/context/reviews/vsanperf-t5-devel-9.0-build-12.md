# vsanperf T5, devel 9.0.2, build 12 (Build 2, default tiers) (2026-11-07)

Upgrade 0.0.0.9 to `dist/vcfcf_sdk_vsanperf.0.0.0.12.pak` on devel 9.0.2 by
`content-installer` (own log `install_devel.log`), instance
`f8ae0aaa-7a4a-4277-bc1d-00cb8c9d2b76` on the Cloud Proxy (collector 2).
Build 12 = Build 2 (pak PR #8; build 13 differs only in the VM tier, off here).
Times America/Chicago.

| Check | Result |
|---|---|
| Solution version | 0.0.0.9 before, 0.0.0.12 after; CLI restarted the instance at +121 s; new jar confirmed by the new keys and the 26 to 23 call change |
| Settings read-back | tier_host true, tier_cluster true, tier_disk false, tier_vm false, vm_tier_every_n_cycles 3, max_parallel_clusters 4, call_timeout_seconds 30, cycle_deadline_seconds 0, perf_timing_logging false, filters empty; 5-minute interval |
| a. Self-metrics | **pass** (01:13:54): clusters_in_scope 1, ok 1, failed 0, timed_out 0, push_batches_failed 0, perf_calls 23 (26 on the first three cycles, 23 once the three empty types were learned), series_pushed 1,186 (2,372 on the first cycle: both window buckets on a cold start, per the every-bucket rule), optional_calls_failed 0, all *_unresolved and entities_unparsed 0, cycle_seconds 9.09, perf_calls_per_second 2.64, perf_call_ms_avg 378, last_error `none` |
| b. Host keys, esx01 | **pass**: 219 `vSAN Perf\|` keys; new groups CMMDS Network, CPU, DOM Comp Mgr, ESA Dedup DOM Client, Host Network, Memory, RDT Latency, `TCP/IP:defaultTcpipStack`, ZDOM Top Stats, ZDOM VTX, `vNIC:vmk2`, `vNIC RDT Latency:vmk2`; at the 01:10:00 bucket `vSAN Perf\|Memory\|kernelConsumedSize` 2022132736, `vSAN Perf\|CMMDS Network\|rdtRx` 21, `vSAN Perf\|DOM Owner\|iops` 797 (Build 1 key still updating) |
| c. Cluster keys, vcf-lab-mgmt-cl01 | **pass**: 91 `vSAN Perf\|` keys at sample time 01:10:00 (read 373 s later): `Capacity\|usedBytes` 9694163763200, `Capacity\|totalBytes` 20166840680448, `Capacity\|dedupRatio` 144 (pushed as served, x100), `DOM Owner\|iopsRead` 2366, `DOM Owner\|iopsWrite` 4351; the two workload clusters carry none |
| d. Tiers off | **pass**: none of the 109 VirtualMachines carries a `vSAN Perf\|` key; no disk-instanced group on any of the 10 hosts |
| e. Hosts with host-tier keys | **pass**: exactly mgmt-esx01..05 (219 keys each); esx06 and the four wld hosts none |

Cycle time rose from ~1 s (3 calls) to ~9 s (23 calls serial on one
cluster); perf_call_ms_avg 378 ms is the service, not the client.
