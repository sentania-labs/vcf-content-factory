# vsanperf T5 live proof, devel 8.18.7, build 7 (2026-11-06)

Fresh install of `dist/vcfcf_sdk_vsanperf.0.0.0.7.pak` on devel 8.18
(`VCFOPS_DEVEL_8_18`, Aria Operations 8.18.7 build 25423534) by
`content-installer`. Python `iSDK_VsanHostMetrics` 2.0.0 and the other paks
untouched. Unsigned pak accepted (no unsigned-pak gate on this instance).

Times are America/Chicago.

| Check | Result |
|---|---|
| Solution version | absent before, 0.0.0.7 after |
| **Cloud Proxy start (OPEN)** | first instance on collector 2 / group `factory-cloud-proxy` (where the Python pack and the other Java paks run, all STARTED) stayed `resourceState: FAILED`, empty statusMessage, lastCollected null for ~10 min; stop/start no effect. Deleted; recreated on collector 1 / "Default collector group" (the analytics node, same group as the mgmt vCenter adapter), started within seconds. Cause unknown at run time: the installer had no proxy login (the stored prod SSH password works as root on this proxy, found afterwards; factory key now installed; proxy-side investigation `2026-11-06-vsanperf-proxy-logs.md` follows). Candidates: pak not yet distributed to the proxy, or a load failure on the proxy JVM |
| TLS | first two cycles ERROR "Login: SSLHandshakeException: … the trustAnchors parameter must be non-empty"; accepted the vCenter leaf (thumbprint 6dad10b5…4f245c) via `testConnection` + `PATCH /api/adapters`; next cycle clean |
| Instance | `vsanperf-mgmt` `5dbd106b-ec5e-444c-9ebe-a4d28069d81e`, collector 1, `cluster_include` empty, timing off; new instances sit STOPPED until `monitoringstate/start` |
| a. Collector object | `a1ed6504-be30-4d20-bd90-e584bc49d983`, present after cycle 1; NO_DATA_RECEIVING on the failed cycle, DATA_RECEIVING after |
| b. Self-metrics | **pass**, all 12 (22:10:19): in_scope 1, ok 1, failed 0, timed_out 0, hosts_unresolved 0, perf_calls 3, perf_call_ms_avg 382.7, perf_calls_per_second 2.61, cycle_seconds 1.369, series_pushed 390, push_batches_failed 0, last_error `none` |
| c. Host keys, esx01 | **pass** at the 22:05:00 bucket: `vSAN Perf\|DOM Owner\|iops` 597.0, `vSAN Perf\|DOM Client\|iopsRead` 29.0, `vSAN Perf\|pNIC:vmnic1\|portRxDropsPct` 0.0. DOM keys readable ~6 min after the pNIC keys (registered at once, data later) |
| d. Hosts carrying keys | **pass**: exactly mgmt-esx01..05, 78 keys each (38 + 6 + 34 pNIC over two NICs) = 390 series |
| e. Unreachable vCenter shows DOWN | **pass**: temp instance DATA_RECEIVING (empty message) through cycle 1, **DOWN at cycle 2** with "Collection failed for all 1 resource(s): IOException: vCenter login or ServiceInstance read failed: Login: ConnectException"; `last_error` carried the same text; no credential text. Temp instance deleted |
| Browser pass / log scan / wrong-credential variant | not run |

Afterwards: the temp instance's orphaned collector object (`ea30a0a0-…`) was
deleted (204; a GET on a deleted resource returns 500 on 8.18, not 404). The
Cloud Proxy `vcf-lab-operations-devel-8-collector` (collector 2, 172.27.10.15)
reports UP with a current heartbeat and runs the Python pack, compliance,
unifi, synology and ClusterPerfRisk; the collectors API exposes no adapter
kind availability per collector, so whether the pak reached the proxy can
only be seen on the proxy itself.

RULE-019 status for 8.18: collection proved on the analytics-node collector;
the Cloud Proxy leg is open pending the proxy-side read.
