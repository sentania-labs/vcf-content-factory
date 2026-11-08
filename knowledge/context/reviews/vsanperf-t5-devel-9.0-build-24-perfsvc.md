# vsanperf T5, devel 9.0.2, build 24: Performance Service state and type fault isolation (2026-11-08)

Upgrade 0.0.0.22 to `dist/vcfcf_sdk_vsanperf.0.0.0.24.pak` (288,082 B, 1.2.1 build 24) on devel 9.0.2
by `content-installer` (own log `install_devel_b24.log`), instance `f8ae0aaa-7a4a-4277-bc1d-00cb8c9d2b76`,
Cloud Proxy collector 2, 5-minute interval. Scope `dashboard`, tiers host and cluster on, disk and VM off,
N 3. Two clusters: cl01 (`domain-c6004`, ESA, 5 hosts) and `vcf-lab-osa-probe-cl01` (`domain-c39146`, 3 hosts,
Performance Service on). Times America/Chicago (adapter log is Z, minus 6 h). Adapter log
`VsanPerfAdapter_7083.log` on the proxy (no new log id; same file), read over SSH key auth. No vCenter writes.
`validate-sdk` was run before the install (OK; SDK compat check skipped, no 9.1.1 jar in `adapter_runtime/`);
pak-compare was not run by the installer (the brief cited no gates).

| Step | Result |
|---|---|
| 1. Pre-state (build 22) | **recorded**: cycles 09:34 / 09:39 (log cycles 194, 195): perf_calls 43, 43; series_pushed 1,633 x2; clusters ok 1 / failed 1; cycle_seconds 25.2 / 14.8; **optional_calls_failed 5** (brief said 3; see deviations); `last_error` read `none` only after the upgrade (not sampled before); WARN each cycle: `vsan-pnic-net` `pfcCountRaw`, plus the five optional types once per refresh |
| 2. Upgrade | **pass**: install exit 0 (about 09:35 to 09:42; "Install completed and verified", pakInstalling True for about 2 min); `/api/solutions` 0.0.0.24; instance `f8ae0aaa` survived, CLI found it FAILED/NONE at +120 s and re-sent start, then STARTED/NONE; settings unchanged (`metric_scope` dashboard, tiers, N 3, workers 4); no `MATERIALIZATION` or `SUMMARY` lines (no dashboards in the pak); `Collection|clusters_perfsvc_disabled` and `Collection|required_calls_failed` present |
| 3. Cycles | see tables; **pass on the structure, different numbers** (6 types learned, not 4; steady 37, not 39) |
| 4. Read-back | **pass** (below) |
| 5. Content | **pass** (below) |
| 6. Logs | **pass**: adapter log from the install (15:42Z, line 2838) to 16:13Z: ERROR 0, Exception / stack-trace 0, `session[` 0, `password` 0; WARN 12 (the six type faults, once at 09:43 and once at 09:49, each once per restart) |
| 7. Timing logging | on at 09:44 (PUT 200), off at 10:14 (PUT 200, log shows `perfTimingLogging=false`) |
| Phase 2, disabled state | **pending Scott**: Performance Service off on the probe (metric 0, alert raised, 23 calls, `clusters_perfsvc_disabled` 1, then re-enable: metric 1, alert cancels). Not done by this run |

The `PUT /api/adapters` that turned timing logging on (09:44:26) restarted the engine: learned state is in
memory, so the learning count started over (cycle numbering restarted at 1, as in the build 22 record).
The first post-install cycle (09:43:20, timing off, before the PUT) is listed as cycle 0 and is a full
52-call probe cycle too.

**Step 3, per cycle** (log `cycle N summary`; `state 2` = the two Performance Service values, included in series_pushed)

| Cycle | Time | perf_calls | series_pushed (core / host / cluster / state) | cycle_s | clusters ok / failed / perfsvc_disabled | required failed | optional failed | learned skips | cfg-call ms (probe / cl01) |
|---|---|---|---|---|---|---|---|---|---|
| 0 (timing off) | 09:43:20 | 52 | 3,268 (two buckets) | 20.2 | 2 / 0 / 0 | 1 | 5 | 0 | not logged (timing off) |
| 1 | 09:49:43 | 52 | 3,268 (1,044 / 1,890 / 332 / 2; two buckets) | 102.9 | 2 / 0 / 0 | 1 | 5 | 0 | 13 / 35 |
| 2 | 09:53:45 | 52 | 1,635 (522 / 945 / 166 / 2) | 44.8 | 2 / 0 / 0 | 1 | 5 | 0 | 18 / 62 |
| 3 | 09:58:25 | 52 | 1,635 | 25.3 | 2 / 0 / 0 | 1 | 5 | 0 | 15 / 45 |
| 4 | 10:03:10 | **37** | 1,635 | 8.9 | 2 / 0 / 0 | 0 | 0 | 15 | 12 / 54 |
| 5 | 10:08:10 | 37 | 1,635 | 8.7 | 2 / 0 / 0 | 0 | 0 | 15 | 14 / 55 |
| 6 | 10:13:09 | 37 | 1,635 | 8.1 | 2 / 0 / 0 | 0 | 0 | 15 | 15 / 36 |

- Config call: one `PERF perfsvc` line per cluster per cycle, `state=enabled fault=-` on every line (12 of 12),
  12 to 62 ms. It is not counted in `perf_calls`.
- Cycle 1 calls: cl01 26 (core 3, host 13, cluster 10) and probe 26 (same split), 52 total; cl01 3.3 s, probe
  102 s (the probe's service answered 1 to 28 s per call; `ioinsight` 27 s). From cycle 2 the probe sped up
  (call_ms_avg 2,023 / 924 / 552 / 330).
- Faults, cycle 1 (WARN once per type, text names the column): core `vsan-pnic-net` (`pfcCountRaw`); optional
  `cluster-rdt-network-latency`, `rdt-network-latency`, `vnic-rdt-network-latency` (`kaReset`), `vsan-cpu`
  (`avgRunPct`), `vsan-memory` (`kernelConsumedSize`). All `SystemError` HTTP 500 on the probe only. The core
  WARN reads "skipped there for about 24 h after 3 faulting cycles in a row".
- Cycle 3, 09:58:25: six INFO lines "`<type>` faulted (SystemError) 3 cycles in a row; not queried there for
  about 24 h" (the five above and `vsan-pnic-net`). Cycle 4: calls 37 = 52 - 15 skips; skips 15 = 6 faulted + 9
  learned-empty / not-offered (the 9 from the 1.2.0 learning, now re-learned in cycles 1 to 3).
- Cycles 1 to 3: `clusters_failed` 0 on every one (was 1 on build 22); the probe cluster counted ok each time.
- After cycle 4: `last_error` `none` (read at 10:13 from the instance property), `clusters_perfsvc_disabled` 0.
  `last_error` during cycles 1 to 3 was **not sampled** (the property keeps only its latest value; the Suite API
  returns no history), so "names domain-c39146 and a type" is unconfirmed; the WARNs name the cluster and type.
- series_pushed 1,635 steady = 1,633 + 2 `state` values (core 522, host 945, cluster 166). The probe's
  hosts lose the pNIC core keys while the type is learned (accepted).

**Step 4, read-back** (`/api/resources/<id>/stats`, 5-minute buckets, read 10:14)

| Object | Key | Values |
|---|---|---|
| cl01 `d8b36417-...` | `vSAN Perf\|Performance Service\|enabled` | 1 at 09:47, 09:52, 09:57, 10:02, 10:07, 10:12 (plus an off-bucket 1 at 10:13) |
| probe `40512bba-...` | same | 1 at the same six buckets (and 10:13) |
| probe esx02 (`vcf-lab-osa-esx02`) | `vSAN Perf\|DOM Owner\|iops` | 76, 63, 53, 73, 75, 73 at 09:47 to 10:12, advancing every 5 min after the upgrade |
| probe esx01, esx03 | `vSAN Perf\|DOM Owner\|iops` | 0 at every bucket (idle hosts: samples arrive, value 0) |

**Step 5, content** (GET by name; `kind` = adapter kind / resource kind)

| Object | Found | Detail |
|---|---|---|
| Symptom `[VCF Content Factory] vSAN Performance Service Disabled` | yes | VMWARE / ClusterComputeResource; WARNING; key `vSAN Perf\|Performance Service\|enabled` `LT` 1.0, static |
| Alert `[VCF Content Factory] vSAN Performance Service disabled on cluster (vSAN Perf collection paused)` | yes | VMWARE / ClusterComputeResource; type 18 / subType 22; WARNING; impact BADGE risk; one symptom set; **waitCycles 1, cancelCycles 1** |
| Recommendation `[VCF Content Factory] vSAN Enable Performance Service` | yes | `Recommendation-df-VMWARE-vSAN_Enable_Performance_Service`, attached to the alert at priority 1 |
| Policy enablement | **not determinable** | `GET /api/policies` lists 20; `GET /api/policies/<id>` returns HTTP 500 "Internal Server error, cause unknown." for all 20; `/api/resources/<id>/policy` 404. Same as the 2026-11-07 recon on this instance. Fallback: the alert is present in `GET /api/alertdefinitions` |
| Active alerts | none | 7,250 active alerts on the instance, 0 for this alert definition |

**Differences from the expectations**

- **Six types learn, not four.** The probe also faults `vsan-cpu` (`avgRunPct`) and `vsan-memory`
  (`kernelConsumedSize`), both optional host-tier types, besides the three RDT types and `vsan-pnic-net`.
  So `optional_calls_failed` is **5** (not 3) in cycles 0 to 3 and on build 22 as well (the build 22 row of
  the brief said 3), and steady `perf_calls` is **37** (not 39): 52 - 15 skips.
  Steady split: cl01 23 and probe 14 (the design expected probe 16). The README check 8.1 and design T5 (probe 16,
  `optional_calls_failed` 3, 39 calls, "four" INFO lines) need the two extra types; the INFO count is **6**.
- Learned-empty re-learn: the first post-install cycles made 52 calls (26 + 26), not 43 + 3/6; the learned
  state is in memory and was lost at the install restart and again at the timing PUT, so cl01 re-ran its 3
  learning cycles too (cl01 26, steady 23).
- `required_calls_failed` and `optional_calls_failed` stayed 1 and 5 through cycle 3 (the strike counter
  commits only when the cluster ended OK with at least one call, D8 amendment 2), then 0 and 0 from cycle 4.
- Alert `waitCycles` 1 / `cancelCycles` 1 and symptom wait 2 / cancel 1 are as the design's content table
  says (the symptom carries the debounce); README check 8.4's "wait 2, cancel 1" refers to the symptom. No gap.
- Pre-state `last_error` and cycles 1 to 3 `last_error` were not sampled.
- The `state 2` pair is in `series_pushed` as the cycle summary now shows; 1,635 vs 1,633 on build 22.
- Not done: phase 2 (needs Scott to disable the service on the probe); README 8.5 (enable/disable
  transition, capture of `VsanClusterGetConfig` body); no browser pass (no UI content).

Left in place: pak 0.0.0.24, `metric_scope` `dashboard`, `perf_timing_logging` false, Performance Service
untouched on both clusters.
