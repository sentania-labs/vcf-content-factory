# vsanperf T5, devel 9.0.2, build 9: logging proof and release v1.0.0.9 (2026-11-06)

Upgrade 0.0.0.8 to `dist/vcfcf_sdk_vsanperf.0.0.0.9.pak` on devel 9.0.2 by
`content-installer` (instance `f8ae0aaa-7a4a-4277-bc1d-00cb8c9d2b76`, Cloud
Proxy `vcf-lab-operations-devel-collector`, collector 2). Times are
America/Chicago unless marked Z.

| Check | Result |
|---|---|
| Solution version | 0.0.0.8 before, 0.0.0.9 after; collector.log `logAdapterVersions`: `'vcfcf_vsanperf' adapter version: 0.0.0.0.0.9` (the new jar loaded; the Sync Adapters race did not strike this time) |
| Restart | CLI re-sent start at +121 s (FAILED/NONE after install), then STARTED / DATA_RECEIVING |
| `perf_timing_logging` | set true 22:54:09 via `PUT /api/adapters` (200), no restart. Cycle numbering restarts with the adapter: the CLI's post-install restart came after the 22:53:22 cycle ("cycle 1"), so 22:58:21 is cycle 1 again and 23:03:21 is cycle 2; the quoted lines are the 23:03:21 cycle. The push line's `batch=2` is the push sequence number, not a count of batches in the cycle (the summary's `push batches ok=1` is the count) |
| Self-metrics | all 12 fresh at 23:03:21: ok 1, failed 0, timed_out 0, hosts_unresolved 0, perf_calls 3, perf_call_ms_avg 142.3, perf_calls_per_second 7.01, cycle_seconds 0.496, series_pushed 390, push_batches_failed 0, last_error `none`; collector object `5078f68a…` unchanged |
| **Summary line every cycle** | **pass**, read over SSH (key auth) from `/storage/log/vcops/log/adapters/VsanPerfAdapter/VsanPerfAdapter_7083.log`: `cycle 2 summary: clusters ok=1 failed=0 timed_out=0 of 1; perf calls=3; series pushed=390 (0 already pushed); hosts unresolved=0; push batches ok=1 failed=0; 0.5 s` (also present for the 22:53 cycle before the flag) |
| **PERF lines only while the flag is on** | **pass**: none before 22:54; after: `PERF cycle cycle=2 clusters=1 perf_calls=3 perf_phase_ms=428 calls_per_s=7.01 call_ms_sum=427 call_ms_avg=142.3 push_ms=45 cycle_ms=496 heap_before=907973344 heap_after=911594584` (heap is the whole collector JVM); `PERF call cycle=2 cluster=domain-c6004 type=vsan-pnic-net worker=vsanperf-c2-w1 queue_wait_ms=0 wall_ms=148 status=200 wire_bytes=3741 decoded_bytes=56337 entities=10 series_kept=170 fault=-`; `PERF inventory cycle=2 read=clusters_hosts ms=20 clusters=1 in_scope=1 hosts=5 nodes=5 pages=1`; `PERF push cycle=2 batch=2 sample_time=1794027600000 resources=5 stat_values=390 bytes~33360 ms=45 result=ok`; `PERF pool cycle=2 workers=1 max_in_flight=1 max_queue_depth=2`; 6 `PERF call` lines over two cycles |
| Secret scan of the adapter log | `session[` 0, `vmware-api-session-id` 0, `password` 0 |
| Flag off | set back to false by the installer after the read (recorded in its report) |

Release: tag `v1.0.0.9` (adapter.yaml version 1.0.0, build 9; RULE-014 refused
`v0.1.0.9` because `0.x` is the hand-built line) built by the repo CI after the
`sdk-release` Environment got its `SDK_RUNTIME_SSH_KEY` (missing on the fresh
template instantiation; first run failed at "Fetch Broadcom SDK jar", re-run
succeeded). Release marked pre-release with notes:
https://github.com/sentania-labs/vcf-content-factory-sdk-vsanperf/releases/tag/v1.0.0.9
(`vcfcf_sdk_vsanperf.1.0.0.9.pak`, SHA256SUMS). Devel keeps the `0.x`
preview per RULE-014. T3/T4 moved to pak issue #6.
