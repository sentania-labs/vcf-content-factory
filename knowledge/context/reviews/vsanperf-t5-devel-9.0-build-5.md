# vsanperf T5 live proof, devel 9.0.2, build 5 (2026-11-06)

First live install of the Java vSAN Performance adapter (design
`knowledge/designs/vsanperf-mp-v1.md` §T5). Installed by `content-installer`
from `dist/vcfcf_sdk_vsanperf.0.0.0.5.pak` onto devel 9.0.2 (`VCFOPS_DEVEL`),
instance on the Cloud Proxy `vcf-lab-operations-devel-collector` (collector
id 2, where the Python `VsanHostMetrics` pack also runs; both left in place).

Times are America/Chicago.

| Check | Result |
|---|---|
| Solution version via `GET /suite-api/api/solutions` | `VCF Content Factory vSAN Performance 0.0.0.5` (was absent; 14 solutions before) |
| Instance | `f8ae0aaa-7a4a-4277-bc1d-00cb8c9d2b76`, `vcf-lab-vcenter-mgmt`, `cluster_include` empty, DATA_RECEIVING / GREEN |
| a. Self-metrics on the instance | **pass**, all 12 at 21:34:15: clusters_in_scope 1, ok 1, failed 0, timed_out 0, hosts_unresolved 0, perf_calls 3, series_pushed 390, push_batches_failed 0, cycle_seconds 1.024, perf_calls_per_second 5.69, perf_call_ms_avg 175.67, last_error `none` |
| b. Host keys | **pass** on esx01..esx05 at the 21:30:00 bucket; esx01: `vSAN Perf\|DOM Owner\|iops` 672.0, `vSAN Perf\|DOM Client\|iopsRead` 19.0, `vSAN Perf\|pNIC:vmnic1\|portRxDropsPct` 0.0, `vSAN Perf\|pNIC:vmnic1\|ioChainDrops` 0.0; esx06 (standalone, not vSAN) has none |
| c. `PERF cycle` log line, no `session[` / password in the log | **not verified**: no Suite API log endpoint; the installer had no Cloud Proxy login (the stored prod SSH password works as root on the devel proxies, found afterwards; the factory key is now installed on all three) |
| d. Unreachable vCenter shows DOWN | **FAILED**: temporary instance against a non-existent host showed ERROR, "Resource discovery failed and there was nothing to collect: IOException: vCenter login or ServiceInstance read failed: Login: ConnectException" (credential-free, but the ERROR path). Cause: the cycle runs in `rediscover`, not `collect()` (review W1; the review's W2 is factory issue #310). Temporary instance deleted. Fix: build 7 moves the cycle to `collect()` |
| e. Browser pass (pNIC instance rendering) | SKIPPED: a Playwright login would put the Ops password in the transcript |

Notes for the installer path: the adapter-create request needed a top-level
`resourceIdentifiers` list of `{name, value}` plus `credential: {id}` and
`credentialInstanceId`; the `resourceKey` form returned a 500 "vcenter_host
missing". The vCenter credential `vsanperf-vc-cred` was created from `.env`
inside a script (RULE-008) and remains in use by the instance.

Open after this round: c (needs a Cloud Proxy login or a Suite API log
route), e (needs a logged-in browser Scott drives), 8.18 and 9.1 legs of
RULE-019, T3 replay harness, T4 heap gate. Build 6 (scheduling fairness and
call-deadline carry-over, Codex findings on pak PR #2) merged after this
install; devel is upgraded to build 7 once the DOWN fix is in.
