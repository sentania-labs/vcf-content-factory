# vsanperf T5 live proof, devel 9.1.1.0, build 7 (2026-11-06)

Fresh install of `dist/vcfcf_sdk_vsanperf.0.0.0.7.pak` on devel 9.1
(`VCFOPS_DEVEL_9_1`, VCF Operations 9.1.1.0 build 25795063) by
`content-installer`. Instance `vsanperf-91-accept`
(`15739079-052f-4c20-847a-6a2dac8f1759`) on collector group
`factory-cloud-proxy` (collector 2, where the Python pack runs), credential
`vsanperf-91-accept-cred`, `cluster_include` empty, timing logging off.
Python `VsanHostMetrics` 2.0.0 untouched.

Times are America/Chicago.

| Check | Result |
|---|---|
| Solution version | absent before, 0.0.0.7 after; kinds `vcfcf_vsanperf` + `VsanPerfCollector` |
| TLS | cycle 2 ERROR "… Login: SSLException: … certificate_unknown(46)" until the vCenter leaf (thumbprint 6dad10b5…4f245c) was accepted on the instance via `testConnection` + `PATCH /api/adapters` (the UI accept dialog's path, `accepted_certificate_handoff.md`); 9.1 has no global CA for this vCenter. Next cycle clean. Credential-free message |
| a. Collector object | `52834c41-760a-4206-99b6-da6a9e4a363b`, present after cycle 1, DATA_RECEIVING |
| b. Self-metrics | **pass**, all 12 (22:02 cycle): in_scope 1, ok 1, failed 0, timed_out 0, hosts_unresolved 0, perf_calls 3, perf_call_ms_avg 258.7, perf_calls_per_second 3.87, cycle_seconds 0.939, series_pushed 390, push_batches_failed 0, last_error `none` |
| c. Host keys, esx01 | **pass** at the 21:50:00 bucket: `vSAN Perf\|DOM Owner\|iops` 526.0, `vSAN Perf\|DOM Client\|iopsRead` 14.0, `vSAN Perf\|pNIC:vmnic1\|portRxDropsPct` 0.0. Note: pNIC keys were readable one cycle before the DOM keys (DOM keys answered "no data" until after the next cycle); read lag vs late landing not established |
| d. Hosts carrying `vSAN Perf\|` keys | **pass**: exactly the 5 cluster hosts (mgmt-esx01..05), 34 keys in the latest read, 78 listed; esx06 and the four wld hosts none |
| e. Unreachable vCenter shows DOWN | **pass**: temp instance NONE through cycle 1 (collector object present, lastCollected null), **DOWN at cycle 2** with "Collection failed for all 1 resource(s): IOException: vCenter login or ServiceInstance read failed: Login: ConnectException"; no "Resource discovery failed" text. Temp instance, adapter and credential deleted (credential delete 409 until the adapter removal finished) |
| Browser pass / log scan / wrong-credential ERROR variant | not run |

Side findings: adapter create on 9.1 takes `collectorGroupId` only (not both
ids); the four numeric/advanced settings created via the API read back as
empty strings rather than describe defaults (adapter applied its defaults;
cycle was clean). Orphaned `VsanPerfCollector` from the temp instance
(`2395a0a2-…`) deleted afterwards on instruction. `docs/installing.md` needs
the 9.1 certificate-accept step.
