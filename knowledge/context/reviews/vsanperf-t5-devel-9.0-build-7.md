# vsanperf T5 live proof, devel 9.0.2, build 7 (2026-11-06)

Upgrade of `vcfcf_vsanperf` from 0.0.0.5 to `dist/vcfcf_sdk_vsanperf.0.0.0.7.pak`
on devel 9.0.2 by `content-installer`; same instance
`f8ae0aaa-7a4a-4277-bc1d-00cb8c9d2b76` on Cloud Proxy collector id 2.
Build 7 = cycle in `collect()` on a per-instance `VsanPerfCollector` object
(design addendum "collector object, build 7").

Times are America/Chicago.

| Check | Result |
|---|---|
| Solution version | 0.0.0.5 before, 0.0.0.7 after (`GET /suite-api/api/solutions`); resource kinds now `vcfcf_vsanperf` + `VsanPerfCollector` |
| a. Collector object | `5078f68a-50c9-4162-8860-052dea7d42c3`, identifiers `vcenter=vcf-lab-vcenter-mgmt.int.sentania.net`, `cluster_scope=*`; NONE then DATA_RECEIVING within 10 min |
| b. Self-metrics on the instance | **pass**, all 12 fresh (21:49:05): clusters_in_scope 1, ok 1, failed 0, timed_out 0, hosts_unresolved 0, perf_calls 3, series_pushed 390, push_batches_failed 0, cycle_seconds 1.497, perf_calls_per_second 4.05, perf_call_ms_avg 245.7, last_error `none` |
| c. Host keys, esx01 | **pass** at the 21:45:00 bucket: `vSAN Perf\|DOM Owner\|iops` 702.0, `vSAN Perf\|DOM Client\|iopsRead` 42.0, `vSAN Perf\|pNIC:vmnic1\|portRxDropsPct` 0.0 (earlier buckets present, so history accrues) |
| d. Hosts carrying `vSAN Perf\|` keys | not counted in this run (esx01 only read); the build 5 run on this instance showed all 5 cluster hosts |
| e. Unreachable vCenter shows DOWN | **pass**: temp instance against a non-existent host: NONE at +0, DATA_RECEIVING at +2 and +4 min (collector object discovered, not yet collected), **DOWN at +6 min** with "Collection failed for all 1 resource(s): IOException: vCenter login or ServiceInstance read failed: Login: ConnectException"; no credential text. Temp instance stopped and deleted (204) |
| f. Browser pass / collector log scan | not run (no logged-in browser; collector key login not yet working) |

Side findings: the install CLI reported "no adapter instance of vcfcf_vsanperf
exists; nothing to start" although the instance existed (factory issue
#311; installer restarted it by hand). A deleted temporary instance leaves
its `VsanPerfCollector` object orphaned (`456c7229-…`); deleted afterwards
by the installer on instruction. Interval was the default 5 min.
