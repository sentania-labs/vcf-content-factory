# vsanperf T5, devel 8.18.7, build 24: default scope (2026-11-08)

Upgrade 0.0.0.22 to `dist/vcfcf_sdk_vsanperf.0.0.0.24.pak` (288,082 B) on devel
8.18 (`vcf-lab-operations-devel-8`, profile `devel_8_18`) by `content-installer`
(own log `install_devel_8_18_b24.log`; auth line named
`vcf-lab-operations-devel-8.int.sentania.net`, matching the profile). Instance
`vsanperf-mgmt` `5dbd106b-ec5e-444c-9ebe-a4d28069d81e`, collector 1 (analytics
node), 5-minute interval, `metric_scope` `dashboard`, tiers host and cluster
on. **Two clusters in scope** this time (`vcf-lab-mgmt-cl01` and the OSA probe
cluster, `domain-c39146`), unlike the one-cluster build 22 record. No vCenter
writes, no setting changes. Times America/Chicago.

| Step | Result |
|---|---|
| 1. Pre-state (0.0.0.22) | cycles 09:57 / 10:02 / 10:07 / 10:12 / 10:17: perf_calls **43**; series_pushed 1,633 (1,633 each); clusters_in_scope 2, ok 1, **failed 1**; optional_calls_failed 5; push_batches_failed 0; cycle_seconds 28 / 7.4 / 7.8 / 8.0 / 11; last_error = probe-cluster vSphere fault (`cluster-rdt-network-latency`, `no such column: kaReset`, HTTP 500) |
| 2. Upgrade | **pass**: install exit 0 (10:17 start; "Install completed and verified ... 0.0.0.24"); solutions endpoint 0.0.0.24; ACCOUNT OK, STARTED / DATA_RECEIVING, was STARTED before; instance id unchanged; all identifiers/settings byte-identical to pre-state; new self-metrics `Collection\|clusters_perfsvc_disabled` and `Collection\|required_calls_failed` present |
| 3. Cycles | cycle 1 to 4 (10:20 / 10:25 / 10:30 / 10:35): perf_calls **52, 52, 52, 37**; series_pushed 3,715 / 1,452 / 1,635 / 1,686; clusters_ok 2, failed 0, timed_out 0; clusters_perfsvc_disabled 0; required_calls_failed 1, 1, 1, **0**; optional_calls_failed 5, 5, 5, **0**; cycle_seconds 21 / 14.4 / 14.6 / 11.6; cycle 5 (10:40): calls 37, series 1,619, last_error `none`. last_error during learning cycles: probe-cluster fault `vsan-pnic-net ... no such column: pfcCountRaw` (HTTP 500); `none` from cycle 4 |
| 4. Read-back | **pass** (mgmt-cl01 only; the probe cluster's key was not read on 8.18): mgmt-cl01 `vSAN Perf\|Performance Service\|enabled` = 1 at 10:20, 10:25, 10:30, 10:35 (new sample each 5 min); mgmt-esx01 `vSAN Perf\|DOM Owner\|iops` 680 / 567 / 697 at 10:20 / 10:25 / 10:30 after 1,050 at 10:15, no gap across the upgrade (latest bucket lags one cycle, as in build 22) |
| 5. Content | **pass**: symptom `[VCF Content Factory] vSAN Performance Service Disabled` (`SymptomDefinition-VMWARE-VCF_Content_Factory_vSAN_Performance_Service_Disabled`), alert definition `[VCF Content Factory] vSAN Performance Service disabled on cluster (vSAN Perf collection paused)`, recommendation `Recommendation-df-VMWARE-vSAN_Enable_Performance_Service` all present; 0 of 510 active alerts belong to that definition |
| Adapter log | **not read**: instance is on the analytics node, key SSH refused (same gap as builds 18 and 22). `state N` in the cycle summary therefore not observed |

**Deviations from expectation**
- Pre-state was not the clean one-cluster 23-call steady state: 43 calls, one of two clusters failing every cycle on a vCenter-side HTTP 500 from the probe cluster. So "back to the pre-upgrade steady value" is 37, not 43.
- Learning cycles were +9 calls (43 to 52), not +3, for 3 cycles, consistent with the second cluster's learning calls plus the failing-call set; cycle 4 dropped to 37.
- Series did not settle at pre +1 per cluster: 3,715 / 1,452 / 1,635 / 1,686 / 1,619 against a flat 1,635 on 9.0.2 and 9.1 for the same two clusters. Cause not determined (the times above are 5-minute stat bucket labels, so a bucket-alignment artifact on this slower analytics-node collector is possible; mgmt-cl01 was not isolated). Step 3 passes on calls and counters; the series drift is an open item for the next 8.18 preview.
- clusters_failed went 1 to 0 and last_error to `none` only from cycle 4; cycles 1 to 3 showed `required_calls_failed` 1 and `optional_calls_failed` 5 with a `pfcCountRaw` fault in last_error. Probe-cluster faults are vCenter-side (stats DB column errors); the cause of the change is unconfirmed without the log.

Left in place: pak 0.0.0.24. Not committed.
