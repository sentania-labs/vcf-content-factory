# vsanperf T5, devel 9.1.1.0, build 18 (scale build, default tiers) (2026-11-07)

Upgrade 0.0.0.12 to `dist/vcfcf_sdk_vsanperf.0.0.0.18.pak` on devel 9.1 by
`content-installer` (own log `install_devel_9_1.log`), instance
`15739079-052f-4c20-847a-6a2dac8f1759` on collector group
`factory-cloud-proxy`. Times America/Chicago.

| Check | Result |
|---|---|
| Solution version | 0.0.0.12 before, 0.0.0.18 after; CLI restarted the instance at +121 s; restart confirmed by perf_calls 26 and series_pushed 2,372 on the first cycle (any restart clears the in-memory state); the version claim rests on the solutions endpoint; no TLS error |
| Settings | tier_host true, tier_cluster true, tier_disk false, tier_vm false, vm_tier_every_n_cycles 3, perf_timing_logging false |
| a. Self-metrics | **pass**: perf_calls 23, 23 (old jar), 26, 26, 26, 23 (learned-empty after three consecutive empties); series_pushed 1,186, 1,186, 2,372, 1,186, 1,186, 1,186; clusters ok 1; push_batches_failed, optional_calls_failed, every *_unresolved and entities_unparsed 0 on all cycles; last_error `none`; cycle_seconds per cycle 3.72, 4.40 (old jar), 5.42, 9.32, 12.38, 19.40 (post-restart cycles at about 02:51, 02:56, 03:01, 03:06; the service slowed over the window, perf_calls_per_second 6.1 to 1.2, nothing failed) |
| b. Host keys, vcf-lab-mgmt-esx01 | **pass**: 219 keys; `vSAN Perf\|DOM Owner\|iops` every 300 s from 00:55 to 03:00 (read at 03:03) with no gap across the upgrade (809, 1074, 847, 902, 1025 at 02:40 to 03:00, the same values 8.18 read from the same vCenter); `stats/latest` `DOM Owner\|iops` 834 and `CPU\|usedPct` 5.0 both at 03:05:00 (bucket-latest reads at the :x2:59 labels gave 4.0 and 6105 one bucket earlier) |
| c. Cluster keys, vcf-lab-mgmt-cl01 | **pass**: 91 keys; `stats/latest` `Capacity\|usedBytes` 9656184340480 at epoch 1794042300000 = 03:05:00, on the 5-minute grid (an earlier read quoted 03:02:59: that was the range query's bucket label under rollUpType=LATEST / 5-minute intervals, which sit at :x2:59, not the pushed sample time); `Capacity\|dedupRatio` 145 |
| d. Tiers off | **pass**: 0 of 126 VMs and 0 of 12 datastores carry a key; no disk-level instanced group on any host; resource listings for VirtualDisk, CacheDisk, CapacityDisk and vSANDiskGroup return 0 (HTTP 200) |
| e. Hosts with host-tier keys | **pass**: exactly mgmt-esx01..05, 219 keys in 16 groups each |

With this, the scale build (production code of build 16; builds 17/18 are
harness and docs) has T5 on all three platforms: 9.0.2 (build 16, VM tier
on), 8.18 and 9.1 (build 18, default tiers).
