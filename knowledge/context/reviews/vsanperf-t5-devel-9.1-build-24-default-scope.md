# vsanperf T5, devel 9.1.1.0, build 24: default scope with the OSA probe cluster in scope (2026-11-08)

Upgrade 0.0.0.22 to `dist/vcfcf_sdk_vsanperf.0.0.0.24.pak` (288,082 B) on devel 9.1 (`devel_9_1`) by
`content-installer` (own log `install_devel_9_1.log`), instance `15739079-052f-4c20-847a-6a2dac8f1759`
(`vsanperf-91-accept`), Cloud Proxy collector 2 (172.27.10.11), 5-minute interval. `validate-sdk` OK before
install (SDK compat check skipped, no 9.1.1 jar); the brief cited no pak-compare gate. No vCenter write, no
setting change. Times America/Chicago; self-metric times are 5-minute bucket labels (about a minute after the cycle).

**Scope: two clusters** (`clusters_in_scope` 2): `vcf-lab-mgmt-cl01` and `vcf-lab-osa-probe-cl01` (`domain-c39146`).
So the 9.0.2 build 24 behaviour applies, not the single-cluster 23 calls / 1,186 series of build 22.

| Step | Result |
|---|---|
| 1. Pre-state (build 22), buckets 10:10 / 10:15 / 10:20 | perf_calls 43 x3; series_pushed 1,633 x3; in_scope 2, ok 1, failed 1; optional_calls_failed 5; cycle_s 21.1 / 22.2 / 18.5; `last_error` = cluster-rdt-network-latency `kaReset` fault on domain-c39146 |
| 2. Upgrade | **pass**: exit 0 (10:17 to 10:24), `/api/solutions` 0.0.0.24, instance id unchanged, CLI saw it FAILED at +121 s and re-sent start, then STARTED/NONE; `metric_scope` dashboard, tiers host+cluster on, disk+VM off, N 3, timing false, all unchanged; `clusters_perfsvc_disabled` and `required_calls_failed` declared stat keys and populated from the first good cycle |
| 3. Cycles | **pass** (table) |
| 4. Read-back | **pass**: cl01 `Performance Service\|enabled` 1.0 at 10:29, 10:34, 10:39, 10:44 (probe also 1.0); esx01 `DOM Owner\|iops` 567 / 697 / 884 / 598 at 10:25 to 10:40, advancing |
| 5. Content | **pass**: symptom (VMWARE/ClusterComputeResource, WARNING, key `vSAN Perf\|Performance Service\|enabled` LT 1.0), alert (waitCycles 1, cancelCycles 1, recommendation attached at priority 1), recommendation `Recommendation-df-VMWARE-vSAN_Enable_Performance_Service` all exist; 0 of 5,260 active alerts are this definition (full scan; the server ignores the `alertDefinitionId` filter) |
| Logs | adapter log found: `VsanPerfAdapter_2340.log` (the file the running instance writes; the build 22 record `vsanperf-t5-devel-9.1-build-22-default-scope.md` misjudged it stale). Since 10:22: ERROR 0, `session[` 0, `password` 0; stack traces: only in the one failed cycle at 10:24 (see deviations), none after |

| Cycle (bucket) | perf_calls | series_pushed | cycle_s | ok / failed / perfsvc_disabled | required / optional failed |
|---|---|---|---|---|---|
| 0 (10:25) | 0 | 0 | 30.0 | login timeout, see deviations | 0 / 0 |
| 1 (10:30) | 52 | 3,268 (two buckets) | 15.0 | 2 / 0 / 0 | 1 / 5 |
| 2 (10:35) | 52 | 1,635 | 16.3 | 2 / 0 / 0 | 1 / 5 |
| 3 (10:40) | 52 | 1,635 | 14.4 | 2 / 0 / 0 | 1 / 5 |
| 4 (10:45) | **37** | 1,635 | 9.2 | 2 / 0 / 0 | 0 / 0 |

`last_error` `none` after cycle 4 (cycle 1 to 3 showed the vsan-pnic-net `pfcCountRaw` fault). 1,635 = 1,633 + 2
Performance Service `state` values. push_batches_failed, clusters_timed_out, entities_unparsed 0 throughout.

**Deviations**
- First cycle after the install (10:24:50, log 16:24:50Z) failed: vCenter login timed out (29,999 ms), preceded by
  an SSLException (CustomTrustManager cert handling) and a RetrievePropertiesEx timeout; adapter set DOWN for that
  one cycle (self-metrics all 0), recovered on the next cycle with no action. Cause: the restart window.
  That is the only source of stack traces in the log, so "0 stack traces" holds from 10:29 on, not from install.
- Learning is 3 cycles at 52 calls, steady 37 (not the brief's "+3 calls"): six types fault on the probe
  (pnic-net, three RDT types, vsan-cpu, vsan-memory), as on 9.0.2. optional_calls_failed is 5, not 3.
- The cycle-summary line (`state N`) is not in the log at default level (needs `perf_timing_logging`, a setting
  change); the `state` pair is inferred from series_pushed. The six "faulted 3 cycles in a row" INFO lines are
  likewise not logged at default level; the six WARNs (once, at 10:29) are.

Left in place: pak 0.0.0.24, settings untouched. Nothing committed.
