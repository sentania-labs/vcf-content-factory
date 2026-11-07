# vsanperf T5, devel 8.18.7, build 22: default scope only (2026-11-07)

Upgrade 0.0.0.18 to `dist/vcfcf_sdk_vsanperf.0.0.0.22.pak` (1.2.0 build 22) on
devel 8.18 (`vcf-lab-operations-devel-8`, profile `devel_8_18`) by
`content-installer` (own log `install_devel_8_18_b22.log`; its auth line named
`vcf-lab-operations-devel-8.int.sentania.net`, matching the profile). Instance
`vsanperf-mgmt` `5dbd106b-ec5e-444c-9ebe-a4d28069d81e`, collector 1 (the
analytics node), 5-minute interval, one cluster (`vcf-lab-mgmt-cl01`). Tiers
host and cluster on, disk and VM off, `vm_tier_every_n_cycles` 3. `metric_scope`
was **not** changed (no `all` leg on this instance). No vCenter writes, no
setting changes. Times America/Chicago. Method as the 9.0.2 record
(`vsanperf-t5-devel-9.0-build-22-metric-scope.md`).

| Step | Result |
|---|---|
| 1. Pre-state | **recorded**: solution 0.0.0.18; settings as above, `perf_timing_logging` false, no `metric_scope`; last three cycles (11:00:54 / 11:05:56 / 11:10:57, plus 11:15:57 just before the install) perf_calls 23 each; series_pushed 1,186; cycle_seconds 4.7 / 6.8 / 3.3 (6.8 at 11:15:57); perf_call_ms_avg 202 / 271 / 135; push_batches_failed, optional_calls_failed and every `*_unresolved` 0; last_error `none`; health GREEN, DATA_RECEIVING |
| 2. Upgrade | **pass**: install exit 0 (started 11:16:15; "Install completed and verified ... 0.0.0.22"); solutions endpoint 0.0.0.22; CLI account check "ACCOUNT OK (collecting)", STARTED / DATA_RECEIVING, was STARTED before; no restart or FAILED state seen; `metric_scope` present with value `dashboard`, other settings unchanged |
| 3. Default scope | **pass**: cycles 1 to 4 (11:20:09, 11:25:09, 11:30:16, 11:35:16): perf_calls **26, 26, 26, 23**; series_pushed 2,372, 1,186, 1,186, 1,186; cycle_seconds 28.6 / 10.2 / 12.7 / 5.5; perf_call_ms_avg 373 / 356 / 465 / 218; push_batches_failed, optional_calls_failed, clusters_failed, clusters_timed_out, entities_unparsed and every `*_unresolved` 0 on every cycle; last_error `none` (read after cycle 4 only) |
| 4. Read-back | **pass**: esx01 219 keys, cl01 91 keys (same counts as build 18). esx01 `vSAN Perf\|DOM Owner\|iops` pre-upgrade last bucket 11:10 (884); after the upgrade 11:20 665, 11:25 688, 11:30 878. cl01 `vSAN Perf\|Capacity\|usedBytes` pre 11:10 (9,668,345,724,928); after 11:20 9,668,388,716,544, 11:25 ...540,760,064, 11:30 ...596,334,592. Series at exact 5-minute spacing from 10:50 to 11:30 with no gap across the upgrade. At the read (11:37) the 11:35 bucket was not yet readable (latest was 11:30) |
| 5. Adapter log | **not done**: the instance runs on collector 1, the analytics node. Key-auth SSH as root to `vcf-lab-operations-devel-8` is refused (`Permission denied (publickey,password,keyboard-interactive)`); no password was tried. The Cloud Proxy (`-collector`) accepts the key but hosts no vsanperf instance. Substitute evidence only: last_error `none`, all failure counters 0 for four cycles, account GREEN. The 0 ERROR / 0 stack-trace / no `session[` or `password` claim is **not verified** on 8.18 (same gap as the build 18 record) |

**Deviation from expectation:** none in the numbers. Calls up by 3 for cycles
1 to 3 then back to 23, series_pushed doubled on cycle 1 only, zero failures.
Cycle times were longer than steady state on cycles 1 to 3 (28.6 / 10.2 / 12.7 s
against 3 to 7 s) with call latency 360 to 465 ms against 135 to 290 ms before,
the same slowdown the 9.0.2 leg saw; nothing timed out. The only open item is
step 5 (log access).

Left in place: pak 0.0.0.22, `metric_scope` `dashboard`.
