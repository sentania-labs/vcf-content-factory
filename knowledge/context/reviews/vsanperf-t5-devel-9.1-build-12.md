# vsanperf T5, devel 9.1.1.0, build 12 (Build 2, default tiers) (2026-11-07)

Upgrade 0.0.0.8 to `dist/vcfcf_sdk_vsanperf.0.0.0.12.pak` on devel 9.1 by
`content-installer` (own log `install_devel_9_1.log`), instance
`15739079-052f-4c20-847a-6a2dac8f1759` on collector group `factory-cloud-proxy`.
Times America/Chicago.

| Check | Result |
|---|---|
| Solution version | 0.0.0.8 before, 0.0.0.12 after; CLI restarted the instance at +121 s; new jar confirmed by perf_calls 26 and series_pushed 2,372 on the first cycle; no TLS error (certificate already accepted) |
| Settings read-back | tier_host true, tier_cluster true, tier_disk false, tier_vm false, vm_tier_every_n_cycles 3, perf_timing_logging false; other advanced fields empty (defaults apply) |
| a. Self-metrics | **pass** (01:14:45): clusters_in_scope 1, ok 1, failed 0, timed_out 0, perf_calls 23 (26 on the first cycle observed; cycles 2 and 3 not read), series_pushed 1,186, optional_calls_failed 0, push_batches_failed 0, all *_unresolved and entities_unparsed 0, cycle_seconds 23.6, perf_call_ms_avg 1,008, perf_calls_per_second 0.99 (the service was slow at that moment; 5.4 calls/s on the first cycle), last_error `none` |
| b. Host keys, vcf-lab-mgmt-esx01 | **pass**: 219 `vSAN Perf\|` keys in 16 groups at the 01:10:00 bucket: `CPU\|usedPct` 7.0, `CMMDS Network\|rdtRxThroughputBytesPerSec` 10678, `DOM Owner\|iops` 797 |
| c. Cluster keys, vcf-lab-mgmt-cl01 | **pass**: 91 keys at sample time 01:10:00: `Capacity\|dedupRatio` 144, `Capacity\|usedBytes` 9694163763200 |
| d. Tiers off | **pass**: 0 of 126 VirtualMachines carry a `vSAN Perf\|` key; no disk-instanced group on any of the 10 hosts |
| e. Hosts with host-tier keys | **pass**: exactly mgmt-esx01..05; esx06 and the four wld hosts none |

Note: host display names on 9.1 are the FQDNs (`vcf-lab-mgmt-esx01.int…`),
so key reads must match on the full name.
