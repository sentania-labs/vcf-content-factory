# vsanperf T5, devel 8.18.7, build 12 (Build 2, default tiers) (2026-11-07)

Upgrade 0.0.0.8 to `dist/vcfcf_sdk_vsanperf.0.0.0.12.pak` on devel 8.18 by
`content-installer` (own log `install_devel_8_18.log`), instance
`vsanperf-mgmt` `5dbd106b-ec5e-444c-9ebe-a4d28069d81e` on collector 1 (the
analytics node; the Cloud Proxy leg stays open, factory #314). Times
America/Chicago.

| Check | Result |
|---|---|
| Solution version | 0.0.0.8 before, 0.0.0.12 after; CLI reported the account collecting; first new cycle 00:56:51 (perf_calls 26, series_pushed 2,372) |
| Settings read-back | tier_host true, tier_cluster true, tier_disk false, tier_vm false, vm_tier_every_n_cycles 3, perf_timing_logging false; other advanced fields empty (defaults) |
| a. Self-metrics | **pass** (01:17:13 and 01:22:13): clusters_ok 1, perf_calls 23 (26 on the first cycle observed; cycles 2 and 3 not read), series_pushed 1,680 then 1,436 (window carrying two buckets for some series), optional_calls_failed 0, every *_unresolved, entities_unparsed and push_batches_failed 0, cycle_seconds 16.0, perf_calls_per_second 1.45, last_error `none`; one transient "account state read failed (will retry quietly)" at install, no effect |
| b. Host keys, vcf-lab-mgmt-esx01 | **pass**: 219 keys in 16 groups; `Memory\|clomdConsumedSizeBytes` 14487552 at 01:10:00; `DOM Owner\|iops` 773 at 01:05:00 then advancing; 5-minute history continuous from 00:32 across the upgrade. Groups sit one bucket apart on a read (service bucket cadence) |
| c. Cluster keys, vcf-lab-mgmt-cl01 | **pass**: 91 keys in Capacity, DOM Client, DOM Comp Mgr, DOM Owner, ESA Dedup DOM Client, RDT Latency, ZDOM Top Stats, all at the pushed sample timestamp (01:05:00 then 01:15:00): `Capacity\|dedupRatio` 144, `freeBytes` 10481273143296, `savedByDedupBytes` 1971459850240, `totalBytes` 20166838583296, `usedBytes` 9685564391424 |
| d. Tiers off | **pass**: 0 of 126 VirtualMachines carry a `vSAN Perf\|` key; no disk-instanced group on any host |
| e. Hosts with host-tier keys | **pass**: exactly mgmt-esx01..05 |

Expected shortfalls, not failures: File Service, vSAN Direct Cluster and
IOInsight (cluster) and vSAN Direct (host) carry no keys because those
types return no entities on this lab (learned-empty after 3 cycles; ioinsight
queried every cycle, empty), so 91 of 189 cluster keys appear, and 219 host
keys: the host tier's 149 less vSAN Direct's 8 is 141, plus the 61 core
labels, which land as 78 keys with 2 pNICs.
