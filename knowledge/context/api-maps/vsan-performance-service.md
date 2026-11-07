# API Map: vSAN Performance Service (VsanPerformanceManager, vsan-health)

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** vcf-lab-vcenter-mgmt.int.sentania.net:443 (vCenter 9.1.1.0100 build 25784172, one ESA vSAN cluster `vcf-lab-mgmt-cl01`, 5 hosts 9.1.1, 30 VMs; plus one standalone non-vSAN host `vcf-lab-mgmt-esx06`, first noted in the inventory round)
- **Last updated:** 2026-11-06
- **Update history:**
  - 2026-11-06 (late evening) — added "Build 2 entity types (measured 2026-11-06)": the 30 remaining dashboard-scope types over JSON with COVERED labels (per-type table, totals, entityRefId grammar, 6 empty types, join keys verified against PropertyCollector, `QueryVsanManagedDisks` and `QueryDisksForVsan`); 24 verbatim samples and `PROVENANCE-2026-11-06-build2.md` under `reference/docs/extracted/vsan-perfsvc-json/`. Two join-key lines and gaps appended. Earlier sections untouched and not re-verified, apart from the instanceUuid and cluster/node uuid joins, which were re-verified.
  - 2026-11-06 (evening) — added "vim25 inventory over JSON" for design Prerequisite P1: per-object GET vs PropertyCollector for the cluster/host inventory reads, the `configurationEx` sub-path fault, and verbatim JSON samples for `host-domclient`, `host-domowner`, `vsan-pnic-net` (Build 1 labels), `VsanPerfQueryNodeInformation` and the RetrievePropertiesEx read, under `reference/docs/extracted/vsan-perfsvc-json/`. Earlier sections untouched and not re-verified this round.
  - 2026-11-06 (later) — added "JSON API transport": vSphere JSON-over-HTTP (`/sdk/vim25/<release>/vsan/...`) measured against SOAP on the same cluster and window; verbatim samples added under `reference/docs/extracted/vsan-perfsvc-json/`.
  - 2026-11-06 — initial mapping. Answers the collector questions in `knowledge/context/investigations/2026-11-06-vsanhostmetrics-scale-plan.md` §3: batching limits, cluster-omitted calls, labels, window/interval, concurrency, session cost. Also captured one full raw collection cycle to `/mnt/holding/vsan-perfsvc-recording-2026-11-06/` (simulator seed; local-only artifact, outside the repo and not reproducible from it; regenerate with the procedure in the Recording section).
- **Evidence basis:** live API calls (JSON section: raw HTTPS from Python `http.client`, no SDK; other sections: pyVmomi 9.0.0.0 with the pack's vendored bindings, vsan binding version `vsan.version.v9_0_0_0`; server advertises urn:vsan 9.1.1.0); vendored type definitions in `content/sdk-adapters/vsanhostmetrics/app/vendor/vsanmgmtObjects.py`.
- **Notes:** Read-only. Only `VsanPerfQueryPerf`, `VsanPerfGetSupportedEntityTypes`, `VsanPerfGetAggregatedEntityTypes`, `VsanPerfQueryNodeInformation`, `VsanPerfQueryStatsObjectInformation`, vim25 property reads, and a GET of `/sdk/vsanServiceVersions.xml` were issued. The inventory round added only vim25 property GETs, `CreateContainerView`, `RetrievePropertiesEx`, `DestroyView`, Login and Logout. **Only one vSAN cluster exists in this vCenter**, so every cross-cluster conclusion is single-cluster evidence. Timings are wall-clock from a workstation on the lab LAN; serial loops varied 6 to 22 s run to run on the same work, so treat single numbers as noisy.

## Connection

- Endpoint: `https://<vc>/vsanHealth` SOAP, stub built by `vsanapiutils.GetVsanVcMos(si._stub, ...)` and sharing the vim25 session cookie; MO key `vsan-performance-manager` `[observed 2026-11-06]`
- Auth: vim25 `SmartConnect` session, then the cookie is reused by the vSAN stub (no second login) `[observed 2026-11-06]`
- Responses are gzip-compressed on the wire: ~8 to 12x smaller than the XML (e.g. 1.31 MB XML = 109 KB wire) `[observed 2026-11-06]`
- Version doc: `GET /sdk/vsanServiceVersions.xml` returns urn:vsan 9.1.1.0 (`/vsanHealth/vsanServiceVersions.xml` is an HTTP error) `[observed 2026-11-06]`

### Session cost (test 8)

| Operation | median | min / max (n) |
|---|---|---|
| SmartConnect login | 0.264 s | 0.241 / 0.347 (5) |
| `perfsvc.connect` (login + cluster ContainerView + vSAN stub) | 0.301 s | 0.298 / 0.312 (3) |
| GetVsanVcMos (stub creation, no network) | <0.001 s | (5) |
| Disconnect | 0.006 s | (5) |
| Reused session `CurrentTime` | 0.002 s | (10) |
| Reused session `VsanPerfQueryNodeInformation` | 0.037 s | (10) |

A login is ~0.3 s, about one and a half perf calls. One session per instance per cycle is worth having but is not the bottleneck `[observed 2026-11-06]`.

## Endpoints

Signatures from the vendored bindings `[documented in vsanmgmtObjects.py]`:
`VsanPerfQueryPerf(querySpecs: VsanPerfQuerySpec[], cluster?: ComputeResource) -> VsanPerfEntityMetricCSV[]`;
`VsanPerfQuerySpec{entityRefId, startTime?, endTime?, group?, labels?: string[], interval?: int}`;
`VsanPerfGetSupportedEntityTypes()` and `VsanPerfGetAggregatedEntityTypes()` take **no arguments** (no cluster);
`VsanPerfQueryNodeInformation(cluster?)`, `VsanPerfQueryStatsObjectInformation(cluster?)`.

### Inventory and service state (test 1)

| Cluster | moid | vSAN | hosts | vSAN cluster uuid |
|---|---|---|---|---|
| vcf-lab-mgmt-cl01 | domain-c6004 | enabled | 5 | 90d067b8-0077-11f1-af60-000c297e270a |

`[observed 2026-11-06]` One ClusterComputeResource, one vSAN cluster. ESA (`vsan-esa-disk-*` populated, `cache-disk`/`capacity-disk`/`disk-group` empty).

| Call | time | wire / XML bytes | result |
|---|---|---|---|
| QueryNodeInformation(cluster) | 0.051 s | 647 / 2,989 | 5 nodes, no errors; stats master esx05 |
| QueryStatsObjectInformation(cluster) | 0.301 s | 799 / 2,635 | `.vsan.stats` object healthy, FTT=1 |

- Performance Service on and **verbose mode off**: the stats master's `masterInfo` reports `statsIntervalSec=300`, `verboseMode=False`, `secSinceLastStatsCollect=1`, `statsDirectoryPercentFree=95`, `collectionFailureHostUuids=[]` `[observed 2026-11-06]`. Only the stats-master node carries `masterInfo`; use it to read verbose mode and interval per cluster without `VsanClusterGetConfig`.
- Node `vsanNodeUuid` = host `config.vsanHostConfig.clusterInfo.nodeUuid` = the uuid in host-scoped entityRefIds `[observed 2026-11-06]`.

### VsanPerfGetSupportedEntityTypes / GetAggregatedEntityTypes (test 2)

| Call | time | wire / XML bytes | result |
|---|---|---|---|
| GetSupportedEntityTypes() | 0.111 s | 89,465 / 766,687 | 70 types |
| GetAggregatedEntityTypes() | 0.743 s | 815 / 4,072 | 1 type: `aggregate` (8 metrics) |

- Ids are namespaced `com.vmware.vsan.perf.entity.<id>` `[observed 2026-11-06]`.
- Advertised but **not usable as an entityRefId prefix**: `vm`, `tcpip`, `vmdk-ioinsight`, `domcomp-sched`, `aggregate` all fault `InvalidArgument: entityRefId`. The query prefixes that work are `virtual-machine`, `vsan-tcpip-stats`, `ioinsight`. `domcomp-sched` has no known working prefix `[observed 2026-11-06]`.
- Of the pack's 69 model types, 66 are advertised directly; the other 3 are the renames above. All 33 in-scope types are queryable.
- Advertised metric counts understate what comes back (`host-domowner` 18 advertised vs 288 returned, `zdom-vtx` 2 vs 71, `host-domclient` 14 vs 78); `disk-group` overstates (76 vs 38 modelled) `[observed 2026-11-06]`.
- It is version-wide, not per cluster: there is no cluster argument, so it cannot say PMem, iSCSI, File Service or IOInsight is absent on a given cluster. Here it advertised `cluster-pmem`/`host-pmem`, which then fault `NotSupported` on the cluster.

### VsanPerfQueryPerf with the cluster omitted (test 3)

Every cluster-taking call faults if you leave the cluster out `[observed 2026-11-06]`:

| Call | time | fault |
|---|---|---|
| QueryPerf([`host-domclient:*`]) | 0.067 s | `vmodl.fault.SystemError: A general system error occurred: AttributeError("'NoneType' object has no attribute '_moId'")` |
| QueryPerf([`cluster-domclient:*`]) | 0.006 s | same |
| QueryNodeInformation() | 0.008 s | `SystemError ... AttributeError("'NoneType' object has no attribute '_stub'")` |
| QueryStatsObjectInformation() | 0.005 s | same as NodeInformation |

With the cluster supplied, `host-domclient:*` took 1.04 s and returned 5 entities, one per host uuid, 390 series. The cluster argument is mandatory in practice even though the binding marks it optional.

### VsanPerfQueryPerf batching rules (test 4)

Server-side validation, keys from `faultMessage[].key` (`com.vmware.vsan.perfsvc.fault.queryperf.*`) `[observed 2026-11-06]`:

| Rule | fault key | message |
|---|---|---|
| A wildcard spec must be the **only** spec (2 wildcards fault; 1 wildcard + 1 explicit faults too, in either order) | `wildcardlimit` (verbatim message: "Invalid Argument. Only one wildcard query allowed in query specs.") | Only one wildcard query allowed in query specs. |
| At most **100** explicit specs per call (100 ok, 101 faults) | `querySpecsSizeLimitOnlyRegularQuery` | The size of query specs should not be more than 100 when only regular query in query specs. |
| One spec class per call (regular, high-res, PMEM, cross-vCenter HCI mesh, mesh high-res) | `queryspectypelimit` | Only single type of query specs is allowed. ... |
| Unknown type prefix in any spec | (none; `invalidProperty=entityRefId`) | A specified parameter was not correct: entityRefId |

The outer fault is always `vmodl.fault.InvalidArgument`, and the `msg` is empty. Read `faultMessage` to tell the cases apart.

**The 33-wildcard batch is rejected outright** (`wildcardlimit`, 0.04 to 0.16 s), whether or not an unsupported type is in it. Adding `cluster-pmem`, `host-pmem`, `vsan-iscsi-target`, `vsan-iscsi-lun`, `disk-group` or a bogus type does not change that. Per-type behaviour alone:

- `cluster-pmem:*`, `host-pmem:*`: `NotSupported`, faultMessage `pmemisunavailable` ("no PMem storage is monitored by vSAN in this cluster").
- `vsan-iscsi-*:*`, `disk-group:*` on ESA: succeed with 1 result that just echoes the wildcard (no objects).
- Model types that fault `InvalidArgument: entityRefId` on a wildcard: `clom-disk`, `clom-host`, `cmmds-workload`, `ddh-disk`, `heap-memory`, `slab-memory`, `remote-virtual-disk`, `remote-virtual-machine`, `remote-vscsi` (none in scope).

Explicit-ref batches work but are **slower**. Server time grows with the number of specs, not round trips:

| Strategy (33 in-scope types, 7 min, no labels) | calls | wall | wire / XML bytes | entities |
|---|---|---|---|---|
| One wildcard spec per call, serial | 33 | 6.0 to 11.0 s (10.2 first run) | 109 KB / 1.31 MB | 423 |
| Explicit refs, 100 per call (423 refs) | 5 | 62.5 s | 102 KB / 1.30 MB | 423 |
| One 100-ref call | 1 | 15 to 22 s | 44 KB / 554 KB | 100 |

- An explicit ref to a missing object (zero uuid, a host-domclient or disk-group ref) does not fault: it comes back with 0 series `[observed 2026-11-06]`.
- Of the 33 in-scope types, 27 have objects here. Empty: `cache-disk`, `capacity-disk`, `ioinsight`, `vsan-direct-cluster`, `vsan-direct-host`, `vsan-file-service`.

### labels filter (test 5)

The series loop with `labels` set per spec to the type's `metric_scope.COVERED` names `[observed 2026-11-06]`:

| Window | labels | wall | wire / XML bytes | series |
|---|---|---|---|---|
| 7 min | none | 6.0 / 11.0 s | 109 KB / 1,309,920 | 7,497 |
| 7 min | COVERED | 7.4 / 8.9 s | 60 KB / 675,084 | 3,636 |
| 15 min | none | 18.3 s | 128 KB / 1,383,793 | 7,497 |
| 15 min | COVERED | 7.0 s | 70 KB / 719,739 | 3,636 |

The response is restricted to the requested labels: every returned `metricId.label` was in the requested set, for all 423 entities. Labels cut bytes and parse work roughly in half (-45 to 48%). Wall time is unchanged within the noise.

### Window and interval (test 6)

| Spec | points per entity (min/max) | wire / XML bytes | entities |
|---|---|---|---|
| 5 min | 1 / 2 | 100 KB / 1,279,448 | **421** (2 entities absent) |
| 7 min | 1 / 2 | 109 KB / 1,309,920 | 423 |
| 15 min | 3 / 4 | 128 KB / 1,383,793 | 423 |
| 60 min | 11 / 13 | 212 KB / 1,716,934 | 423 |
| 15 min, interval=300 | 3 / 4 | 128 KB / 1,383,793 | 423 |
| 15 min, interval=60 | 3 / 4 | identical | 423 |
| 60 min, interval=1800 | 11 / 13 | identical | 423 |

- The native interval is 300 s. `sampleInfo` holds comma-separated timestamps on 5-minute boundaries, in UTC with no zone marker (`2026-11-06 23:25:00,2026-11-06 23:30:00`), and `metricId.metricsCollectInterval=300`. Verbose mode is off `[observed 2026-11-06]`.
- **`interval` is ignored** for regular queries: the bytes and timestamps were identical at 60, 300 and 1800 `[observed 2026-11-06]`.
- A 5-minute window can drop an entity whose only bucket falls just outside it. Seven minutes always held at least one point. Fixed overhead dominates the payload (7 min is 95% of the 15-min XML), so a shorter window barely shrinks it. The labels filter is the lever that does.

### Concurrency (test 7)

Single session, shared stub, labels on, 7 min, all against the one cluster `[observed 2026-11-06]`:

| Run | calls | workers | wall | per-call p50 / p90 / max | errors |
|---|---|---|---|---|---|
| serial | 33 | 1 | 6.3 to 7.9 s | 0.17 to 0.24 / 0.26 to 0.34 / 0.37 s | 0 |
| one cycle | 33 | 4 | 6.0 s | 0.69 / 0.95 / 1.17 s | 0 |
| one cycle | 33 | 8 | 5.0 s | 1.08 / 1.33 / 1.91 s | 0 |
| 4 cycles | 132 | 4 | 19.8 s | 0.54 / 0.81 / 1.29 s | 0 |
| 8 cycles | 264 | 8 | 35.7 s | 0.99 / 1.46 / 2.58 s | 0 |
| 4 cycles | 132 | 16 | 18.6 s | 2.17 / 2.57 / 3.54 s | 0 |

No faults and no throttling messages. Throughput saturates at **~7 calls/s** (vs ~5/s serial): extra workers only stretch per-call latency. Whether that ceiling belongs to vsan-health (per vCenter) or to the cluster's stats master/stats DB (per cluster) **cannot be told from one cluster**. That is the open question that decides whether a cross-cluster pool scales. Slowest types serially: cluster-domowner 0.45 s, virtual-disk 0.35, cache-disk 0.32, vscsi 0.30.

## JSON API transport (measured 2026-11-06)

Raw HTTPS + JSON from Python `http.client` (no SDK), same vCenter, cluster `domain-c6004`, 7-minute window, 33 in-scope types. SOAP re-run side by side in the same half hour for the comparison `[observed 2026-11-06]`.

### Working shapes

- Release id: the vim25 apiVersion. `9.1.1.0`, `9.0.0.0` and `8.0.3.0` all work for vSAN calls; `8.0.0.0`, `7.0.3.0` fault `InvalidRequest: Unknown release ID.`. No discovery doc: `GET /sdk/vim25/` faults the same way and `GET /api/` is a 405 HTML page. Read the release from `GET /sdk/vimServiceVersions.xml` (urn:vim25 9.1.1.0) or `about.apiVersion` `[observed 2026-11-06]`.
- Login: `POST /sdk/vim25/9.1.1.0/SessionManager/SessionManager/Login`, body `{"userName":..,"password":..}`, returns a `UserSession` and the token in response header `vmware-api-session-id` (40 chars). No Set-Cookie. Send that header on every call. `GET .../ServiceInstance/ServiceInstance/content` gives `about` (`VMware vCenter Server 9.1.1.0100.25784172`) `[observed 2026-11-06]`.
- vSAN calls: `POST /sdk/vim25/<release>/vsan/<MoType>/<moId>/<Method>`, e.g. `.../vsan/VsanPerformanceManager/vsan-performance-manager/VsanPerfQueryPerf`. The `vsan/` segment is the namespace; `/vsanHealth/vim25/<release>/vsan/...` also works with the same session `[observed 2026-11-06]`.
- Body: `{"querySpecs":[{"_typeName":"VsanPerfQuerySpec","entityRefId":"host-domclient:*","startTime":"2026-11-07T00:03:19.033Z","endTime":"...","labels":[..]}],"cluster":{"_typeName":"ManagedObjectReference","type":"ClusterComputeResource","value":"domain-c6004"}}`. `_typeName` is **required on each spec**; on the MoRef it is optional, and `type:"ComputeResource"` also works `[observed 2026-11-06]`.
- Dates: ISO-8601 strings, with or without ms, `Z`, `+00:00` or no zone. **A non-zero offset is silently dropped**: `18:07-06:00` was read as 18:07 UTC (data 6 h old, different values); `+05:30` returned no `value`. SOAP via pyVmomi does the same. Always send UTC `[observed 2026-11-06]`.
- Other methods: `VsanPerfQueryNodeInformation` and `VsanPerfQueryStatsObjectInformation` take `{"cluster":<MoRef>}`; `VsanPerfGetSupportedEntityTypes` / `GetAggregatedEntityTypes` take `{}` `[observed 2026-11-06]`.

Errors on the way (all HTTP 500 with a JSON fault body `{"_typeName":..,"faultstring":..}`) `[observed 2026-11-06]`:

| Attempt | fault |
|---|---|
| `/sdk/vim25/<rel>/VsanPerformanceManager/vsan-performance-manager/...` (no `vsan/`) | `ManagedObjectNotFound` (obj `vsan-performance-manager`) |
| moId `VsanPerformanceManager` | `ManagedObjectNotFound` |
| `/sdk/vsan/<rel>/...` | SOAP XML fault envelope (not a JSON endpoint) |
| GET on a method | `InvalidType: Managed object type 'VsanPerformanceManager' doesn't have a 'VsanPerfQueryPerf' property.` |
| spec without `_typeName` | `InvalidArgument: Invalid MoRef field: entityRefId` |
| `"cluster":"domain-c6004"` | `InvalidArgument: Unexpected string value.` |
| epoch integer dates | `InvalidArgument: Unexpected integer value.` |
| no / bad / logged-out session header | `NotAuthenticated` |
| unknown cluster moId | `ManagedObjectNotFound: The object 'vim.ClusterComputeResource:domain-c99999' has already been deleted...` |

### Same rules, same faults

The vSAN semantics are identical to SOAP: same vsan-health service behind both `[observed 2026-11-06]`.

- Batching: 2 wildcards, wildcard + explicit (either order), and all 33 wildcards fault `InvalidArgument` with `faultMessage[].key` ending `wildcardlimit`; 101 explicit refs fault `querySpecsSizeLimitOnlyRegularQuery`; 100 succeed. `faultstring` is `A specified parameter was not correct: ` (empty param), so read `faultMessage` as on SOAP.
- Unknown type: `InvalidArgument`, `faultstring` ends `entityRefId`, no faultMessage. `cluster-pmem:*`: `NotSupported` + `pmemisunavailable`.
- Cluster omitted (`host-domclient`, `cluster-domclient`): `SystemError`, `reason` `AttributeError("'NoneType' object has no attribute '_moId'")`, 0.003 s. NodeInformation without cluster: same `'_stub'` error.
- Labels filter: response restricted to the requested labels for all 423 entities; bytes roughly halve.
- Empty types echo the wildcard: `{"_typeName":"VsanPerfEntityMetricCSV","entityRefId":"cache-disk:*","sampleInfo":""}` with no `value` key.

### Comparison, SOAP vs JSON (same cluster, 7 min, serial = one wildcard per call)

| Measure | SOAP (pyVmomi) | JSON (raw HTTP) |
|---|---|---|
| 33 calls, no labels: wall | 5.25 / 7.72 s (6.0 to 11.0 earlier) | 4.63 / 4.98 s |
| 33 calls, no labels: wire / decoded | 110 KB / 1.31 MB XML | 153 KB / 2.56 MB |
| 33 calls, labels: wall | 4.68 / 4.60 s | 4.47 / 4.49 s |
| 33 calls, labels: wire / decoded | 60 KB / 675 KB | 83 KB / 1.28 MB |
| entities / series (no labels) | 423 / 7,497 | 423 / 7,497 |
| per-call p50 (serial) | 0.12 to 0.25 s | 0.12 to 0.13 s |
| one 100-explicit-ref call | 8.4 s, 45 KB wire | 7.2 s, 63 KB wire |
| sustained parallel (4/8/16 workers, 132 to 264 calls) | ~7 calls/s | 6.83 / 6.93 / 7.02 calls/s |
| one 33-call burst, 8 workers | 5.0 s (6.6/s) | 2.86 s (11.5/s) |
| login / logout | 0.264 / 0.006 s | 0.250 (0.246 on a new TLS conn) / 0.004 s |
| reused cheap call | CurrentTime 0.002 s; NodeInformation 0.037 s | serverClock 0.001 s; NodeInformation 0.041 s |
| gzip | yes | yes, when `Accept-Encoding: gzip` is sent (else 130 KB vs 7.8 KB for host-domclient) |

- The JSON body is pretty-printed: decoded size is ~2x the XML, but compact re-serialization is 49% of it (host-domclient 129,807 to 63,977 bytes). On the wire JSON is ~40% larger than SOAP. Server time dominates either way, so this is a parse/memory cost, not latency `[observed 2026-11-06]`.
- The ~7 calls/s sustained ceiling is the same on both transports, so it is server-side (vsan-health or the stats DB), not pyVmomi. JSON's faster single burst is probably a warm-cache effect; the sustained runs agree `[observed 2026-11-06; burst cause inferred]`.
- Session lifetime: not discoverable by property read. `currentSession` carries `loginTime`/`lastActiveTime`; `VpxSettings` has no session-timeout key (`vpxd.httpClientIdleTimeout=900` is the outbound HTTP client). The usual vCenter idle timeout of 30 min is `[unverified]`. A Java client should treat `NotAuthenticated` as "log in again once and retry" `[inferred from pattern]`.

### Response shape for a Java client

Top level is a JSON array of `VsanPerfEntityMetricCSV`. Every object carries `_typeName`. Verbatim sample: `reference/docs/extracted/vsan-perfsvc-json/queryperf-cluster-domclient-2026-11-06.json` (1 entity, 14 series); fault sample: `reference/docs/extracted/vsan-perfsvc-json/queryperf-fault-wildcardlimit-2026-11-06.json` `[observed 2026-11-06]`.

```json
[{"_typeName":"VsanPerfEntityMetricCSV",
  "entityRefId":"cluster-domclient:90d067b8-0077-11f1-af60-000c297e270a",
  "sampleInfo":"2026-11-07 00:05:00,2026-11-07 00:10:00",
  "value":[{"_typeName":"VsanPerfMetricSeriesCSV",
            "metricId":{"_typeName":"VsanPerfMetricId","label":"iopsRead","metricsCollectInterval":300},
            "values":"806,457"}]}]
```

- Across a full cycle (429 results, 7,497 series) the only keys seen were: entity `_typeName, entityRefId, sampleInfo, value` (`value` absent on the 6 wildcard echoes); series `_typeName, metricId, values`; metricId `_typeName, label, metricsCollectInterval`. No other fields (e.g. `group`, `description`) appeared `[observed 2026-11-06]`.
- `values` is a comma-separated string aligned with `sampleInfo`; 2,218 tokens were the literal `None` (no sample). Parse with a `None` check, not `Double.parseDouble` alone `[observed 2026-11-06]`.
- `sampleInfo` timestamps are UTC, no zone marker, format `yyyy-MM-dd HH:mm:ss`.
- Faults: HTTP 500, object with `_typeName` (the fault class), `faultstring`, and for vSAN validation faults `faultMessage[]` of `{key, message}` (see the fault sample).

### Recommendation for the Java port

Use the JSON API. It reaches the same vsan-health handlers with identical batching limits, fault keys and cluster requirement, matches or beats SOAP on wall time, and has the same ~7 calls/s ceiling, so the collector design from the SOAP sections carries over unchanged. It removes the need for the vim25 and vSAN SDK jars: a Java 11+ `HttpClient` plus Jackson (or Gson) and four small POJOs (`QuerySpec`, `EntityMetricCSV`, `MetricSeriesCSV`, `MetricId`) cover it. Pin the release id to the oldest one the pak supports that the vCenter accepts (8.0.3.0 worked here; 8.0.0.0 did not), or read `about.apiVersion` at connect. Rules to build in: always send `_typeName` on specs, UTC dates only, `Accept-Encoding: gzip`, the `vmware-api-session-id` header on one session per adapter instance reused across cycles (re-login once on `NotAuthenticated`), one wildcard type per call, parse `None` tokens, and dispatch on `faultMessage[].key`. The cost is ~40% more wire bytes and a larger decoded body than SOAP; stream-parse the array if memory matters. Unverified: JSON API availability on vCenter releases older than 8.0U1 (the JSON API arrived in 8.0U1 `[inferred from docs, not checked here]`), and behaviour across multiple clusters.

## vim25 inventory over JSON (measured 2026-11-06)

Answers design Prerequisite P1 (`knowledge/designs/vsanperf-mp-v1.md`). Same vCenter, release id `8.0.3.0` (accepted for Login, vim25 reads and vSAN calls), raw `http.client`, `Accept-Encoding: gzip`, one `vmware-api-session-id` session per run. Two sessions were used (the first exposed the cluster-path fault, the second measured the fix); both were logged out (`204`). Wall times are from a workstation on the lab LAN `[observed 2026-11-06]`.

Lab inventory seen: `group-d1` root, `datacenter-3`, host folder `group-h5`, one cluster `domain-c6004` (`vcf-lab-mgmt-cl01`, 5 hosts, all vSAN ESA) **plus one standalone non-vSAN host** `host-31155` (`vcf-lab-mgmt-esx06`, parent `ComputeResource` `domain-s31156`), 6 HostSystems total `[observed 2026-11-06]`. ServiceContent ids: `propertyCollector` = `propertyCollector`, `viewManager` = `ViewManager`, `rootFolder` = `group-d1` `[observed 2026-11-06]`.

### Per-object property GET: top-level properties only

`GET /sdk/vim25/8.0.3.0/<MoType>/<moId>/<property>` works for a **top-level** property and returns the bare value: `"vcf-lab-mgmt-cl01"` for `name`, a bare JSON array of MoRefs for `host`, a bare MoRef for `Datacenter/.../hostFolder` (no `DynamicProperty` / `_value` wrapper) `[observed 2026-11-06]`.

Any dotted path faults, HTTP 500 `[observed 2026-11-06]`:

| GET | fault body |
|---|---|
| `HostSystem/host-6011/config.vsanHostConfig.clusterInfo.nodeUuid` | `{"_typeName":"InvalidType","faultstring":"Managed object type 'HostSystem' doesn't have a 'config.vsanHostConfig.clusterInfo.nodeUuid' property."}` |
| `HostSystem/.../config.vsanHostConfig`, `configManager.vsanSystem`, `summary.config.name` | same `InvalidType` |
| `ClusterComputeResource/domain-c6004/configurationEx.vsanConfigInfo` and `....enabled` | same `InvalidType` |
| `ClusterComputeResource/domain-c6004/configurationEx/vsanConfigInfo` | `{"_typeName":"InvalidRequest","faultstring":"Invalid URI format - too long"}` |

So the GET path can reach the data only by fetching whole objects: cluster `configurationEx` (15,708 B decoded, 2,690 B wire, 3 ms) and per host `configManager` then `HostVsanSystem/<id>/config` (a `VsanHostConfigInfo` with `enabled`, `clusterInfo.uuid`, `clusterInfo.nodeUuid`, 1,107 B). `HostSystem/<id>/config` works but is 2.33 MB decoded / 207 KB wire / 0.14 s per host: never use it. The lab walk (root `childEntity`, `hostFolder`, folder `childEntity`, cluster `name`/`host`/`configurationEx`, host `name` x5) was 11 successful GETs at ~1 ms each; with the 2 extra GETs per host for nodeUuid it is 3 + 3 + 3 x hosts calls (21 here), linear in hosts. Not recommended `[observed 2026-11-06; call count for the nodeUuid variant derived from the per-call measurements]`.

### PropertyCollector: works, with one path restriction

- `POST /sdk/vim25/8.0.3.0/ViewManager/ViewManager/CreateContainerView`, body `{"container":{"_typeName":"ManagedObjectReference","type":"Folder","value":"group-d1"},"type":["ClusterComputeResource"],"recursive":true}`, returns `{"_typeName":"ManagedObjectReference","value":"session[<uuid>]<uuid>","type":"ContainerView"}` (2.3 ms, 174 B). The view moId embeds the vpxd session key, so the view dies with the session `[observed 2026-11-06; lifetime inferred from pattern]`.
- `POST .../PropertyCollector/propertyCollector/RetrievePropertiesEx`, body `{"specSet":[PropertyFilterSpec],"options":{"_typeName":"RetrieveOptions"}}`. `_typeName` was sent on every spec object; the run did not test omitting it `[observed 2026-11-06]`.
- `POST .../ContainerView/<view moId>/DestroyView`, body `{}`, returns `204`, 1.2 ms `[observed 2026-11-06]`.

**The cluster vSAN paths in the design are not retrievable.** Every sub-path of `configurationEx` faults `InvalidProperty`, HTTP 500, in RetrievePropertiesEx, whether alone or mixed with valid paths `[observed 2026-11-06]`:

| pathSet entry | fault body |
|---|---|
| `configurationEx.vsanConfigInfo.enabled` | `{"_typeName":"InvalidProperty","name":"configurationEx.vsanConfigInfo.enabled"}` |
| `configurationEx.vsanConfigInfo.defaultConfig.uuid` | same, `name` = that path |
| `configurationEx.vsanConfigInfo.defaultConfig` | same |
| `configurationEx.vsanConfigInfo` | same |

`configurationEx` itself works (val `_typeName` `ClusterConfigInfoEx`, with `vsanConfigInfo: {"_typeName":"VsanClusterConfigInfo","enabled":true,"defaultConfig":{"uuid":"90d067b8-...","autoClaimStorage":false},"vsanEsaEnabled":true}`). Probable cause: `configurationEx` is declared as the base type `ComputeResourceConfigInfo` on ComputeResource, so subtype fields are not addressable as paths `[inferred from pattern; SOAP not re-tested]`. Host paths below `config` (`config.vsanHostConfig.enabled`, `.clusterInfo.uuid`, `.clusterInfo.nodeUuid`, `config.network.pnic`) all work `[observed 2026-11-06]`.

Single-call shapes that worked, ContainerView of clusters traversed `view` then `ComputeResource.host`, first call plus 10 repeats on one session (cluster-only: one call) `[observed 2026-11-06]`:

| Shape | Cluster paths | Host paths | time p50 (min/max) | wire / decoded |
|---|---|---|---|---|
| R2 (recommended) | `name`, `host` | `name`, `config.vsanHostConfig.enabled`, `config.vsanHostConfig.clusterInfo.uuid`, `config.vsanHostConfig.clusterInfo.nodeUuid` | 16.8 ms (15.7 / 22.5; 22.5 = first call) | 908 B / 9,821 B |
| R3 | `name`, `configurationEx`, `host` | `name`, `config.vsanHostConfig.clusterInfo.nodeUuid` | 17.9 ms (15.7 / 19.1) | 3,842 B / 31,366 B |
| cluster only | `name`, `configurationEx` | (none) | 2.8 ms | 3,509 B / 26,824 B |
| hosts by cluster MoRef, no view | (ObjectSpec per cluster MoRef, `skip:true`, traverse `host`) | `name`, `...nodeUuid` | 14 to 35 ms (n=6) | 555 B / 4,602 B |

R2 request body, verbatim apart from the view moId `[observed 2026-11-06]`:

```json
{"specSet":[{"_typeName":"PropertyFilterSpec",
  "propSet":[{"_typeName":"PropertySpec","type":"ClusterComputeResource","pathSet":["name","host"]},
             {"_typeName":"PropertySpec","type":"HostSystem","pathSet":["name","config.vsanHostConfig.enabled","config.vsanHostConfig.clusterInfo.uuid","config.vsanHostConfig.clusterInfo.nodeUuid"]}],
  "objectSet":[{"_typeName":"ObjectSpec","obj":{"_typeName":"ManagedObjectReference","value":"<view moId>","type":"ContainerView"},"skip":true,
    "selectSet":[{"_typeName":"TraversalSpec","name":"v","type":"ContainerView","path":"view","skip":false,
      "selectSet":[{"_typeName":"TraversalSpec","name":"ch","type":"ComputeResource","path":"host","skip":false}]}]}]}],
 "options":{"_typeName":"RetrieveOptions"}}
```

Response shape (verbatim sample `reference/docs/extracted/vsan-perfsvc-json/retrievepropertiesex-cluster-hosts-2026-11-06.json`) `[observed 2026-11-06]`:

- `{"_typeName":"RetrieveResult","objects":[ObjectContent...]}`. No `token` at this size (6 objects), so no `ContinueRetrievePropertiesEx`. At 70 clusters the server's default page size may produce a `token`; handle it `[inferred from pattern, unverified]`.
- `ObjectContent` = `{"_typeName":"ObjectContent","obj":<MoRef>,"propSet":[DynamicProperty...]}`; `missingSet` absent when all paths resolve.
- `DynamicProperty` = `{"_typeName":"DynamicProperty","name":<path>,"val":...}`. **Primitives and arrays are boxed**: `{"_typeName":"string","_value":"vcf-lab-mgmt-cl01"}`, `{"_typeName":"boolean","_value":true}`, `{"_typeName":"ArrayOfManagedObjectReference","_value":[MoRef...]}`. MoRefs and data objects are not boxed (`{"_typeName":"ManagedObjectReference","value":"domain-c6004","type":"ClusterComputeResource"}`, `{"_typeName":"ClusterConfigInfoEx",...}`).
- `propSet` comes back **sorted by path name**, not in request order (`config...nodeUuid` before `name`); `objects` order is not the cluster's `host` order. Key by `name` and `obj.value`.
- The cluster object and its hosts arrive in the same flat `objects` array; join via the cluster's `host` array.

Cost of the recommended read per cycle: CreateContainerView + RetrievePropertiesEx + DestroyView = 3 calls, ~2.3 + ~17 + ~1.2 ≈ 20 ms, ~1.1 KB wire, for 1 cluster / 5 hosts. Keeping the view for the life of the session cuts it to 1 call per cycle; recreate it after a re-login, since the view is session-scoped `[timings observed 2026-11-06; sum derived; view lifetime inferred]`. The cold create+retrieve+destroy loop was run 5 times, but its retrieve used a faulting pathSet, so there is no measured end-to-end cold figure.

**Recommendation: PropertyCollector over JSON, shape R2, in one call.** It covers design steps 1 and 2 together: cluster `name` and `host`, then for each host `name`, `nodeUuid`, vSAN enabled, and vSAN cluster uuid. Derive the cluster's vSAN-enabled flag and uuid from its member hosts: `config.vsanHostConfig.clusterInfo.uuid` equals the cluster's `configurationEx.vsanConfigInfo.defaultConfig.uuid` (`90d067b8-0077-11f1-af60-000c297e270a`, 5 of 5 hosts) `[observed 2026-11-06]`. To read the cluster flag exactly, use shape R3 (whole `configurationEx`, about 3.5 KB wire per cluster here) and read `vsanConfigInfo` client side. `configurationEx` carries DRS rules, groups and per-VM HA/DRS overrides, so its size grows with cluster config `[inferred from pattern]`. **The JAX-WS fallback is not needed** for inventory.

### Build 1 perf samples over JSON

One wildcard spec per call, cluster `domain-c6004`, window `2026-11-07T02:28:26Z` to `02:35:26Z` (7 min, UTC), `labels` = the design's Build 1 list for the type (6 / 38 / 17). Every requested label came back and no others; `metricsCollectInterval` 300 everywhere; no `None` tokens in these windows; two 5-minute buckets (`02:25:00,02:30:00`) per series `[observed 2026-11-06]`.

| Type | entities | series | time | wire / decoded | file |
|---|---|---|---|---|---|
| `host-domclient` | 5 | 30 | 0.162 s | 918 B / 10,777 B | `queryperf-host-domclient-2026-11-06.json` |
| `host-domowner` | 5 | 190 | 0.175 s | 4,475 B / 64,463 B | `queryperf-host-domowner-2026-11-06.json` |
| `vsan-pnic-net` | 10 | 170 | 0.254 s | 3,737 B / 56,337 B | `queryperf-vsan-pnic-net-2026-11-06.json` |
| `VsanPerfQueryNodeInformation` (`{"cluster":<MoRef>}`) | 5 nodes | n/a | 0.034 s | 468 B / 2,207 B | `querynodeinformation-2026-11-06.json` |

The three perf types total **390 series**, exactly the design's "up to 390" for this cluster `[observed 2026-11-06]`.

- **entityRefId formats** `[observed 2026-11-06]`: `host-domclient:<nodeUuid>`, `host-domowner:<nodeUuid>`, and **`vsan-pnic-net:<nodeUuid>|vmnicN`**, with a pipe between the node uuid and the NIC, e.g. `vsan-pnic-net:69fd149d-c1b8-aae3-bcb2-3805253936dc|vmnic1`. This matches the design's entity table (`vsan-pnic-net:<node uuid>|vmnicN`) and the earlier map entry. A `<nodeUuid>:<vmnicN>` form (colon) does **not** occur. Split on the first `:` for the type, then on `|`.
- **pNICs reported**: vmnic1 and vmnic2 on each of the 5 hosts. Each host has vmnic0 to vmnic3, but only vmnic1/vmnic2 have a `linkSpeed` (link up) in `config.network.pnic`, and vmnic0/vmnic3 are not reported. vSAN uses `vmk2` on every node. This lab cannot tell whether the type reports "uplinks backing the vSAN vmknic" or "all link-up NICs", because they coincide here `[observed 2026-11-06; selection rule unverified]`.
- **Non-vSAN host**: `vcf-lab-mgmt-esx06` (standalone, `config.vsanHostConfig.enabled` = `{"_typeName":"boolean","_value":false}`, `clusterInfo.nodeUuid` = `{"_typeName":"string","_value":""}`, an empty string, not absent) appears in **none** of the three responses, and NodeInformation lists only the 5 cluster nodes. All 5 node uuids in every response match the cluster hosts' `nodeUuid` 1:1 `[observed 2026-11-06]`. Because the perf query is cluster-scoped, a host outside a vSAN cluster cannot appear. Not tested, since the lab has none: a non-vSAN or compute-only host *inside* a vSAN cluster, and HCI Mesh client clusters. The inventory should treat an empty `nodeUuid` as "not a vSAN node" and leave it out of the node-to-host map.
- NodeInformation entries: `version`, `hostname`, `isCmmdsMaster`, `isStatsMaster`, `vsanMasterUuid`, `vsanNodeUuid`, `diagnosticMode`. Only the stats master carries `masterInfo` (`secSinceLastStatsWrite`, `secSinceLastStatsCollect`, `statsIntervalSec` 300, `statsDirectoryPercentFree`, `verboseMode` false). `hostname` is the host's vCenter `name` here (FQDN), but join on `vsanNodeUuid` `[observed 2026-11-06]`.

## Build 2 entity types (measured 2026-11-06)

Every entity type in the Python pack's default dashboard scope (`metric_scope.COVERED`, 33 kinds / 451 labels) that Build 1 does not cover: 30 types, 390 labels. Kind to wire type via `perfsvc_model.ENTITIES`, plus `perfsvc_model_extra.ENTITIES` for 8 COVERED kinds the live model lacks (`cache-disk`, `capacity-disk`, both `*-esa-dedup-domclient-io`, `vsan-direct-cluster`, `vsan-direct-host`, `vsan-file-service`, `ioinsight`); the pack loads both. Same transport as above: release `8.0.3.0`, one session (login, 30 queries, join reads, logout `204`), one wildcard spec per call, `labels` = that kind's COVERED labels, cluster `domain-c6004`, window `2026-11-07T05:01:41Z` to `05:08:41Z` (7 min, UTC), gzip, serial. Provenance and per-file sizes: `reference/docs/extracted/vsan-perfsvc-json/PROVENANCE-2026-11-06-build2.md` `[observed 2026-11-06]`.

### Per-type results

All 30 calls returned HTTP 200; no faults. Every requested label came back on every non-empty type, and no others; `metricsCollectInterval` 300 everywhere `[observed 2026-11-06]`.

| Tier | Type | Labels | Entities | Series | Wire / decoded B | ms |
|---|---|---|---|---|---|---|
| cluster | `vsan-cluster-capacity` | 5 | 1 | 5 | 416 / 1,917 | 139 |
| cluster | `cluster-domclient` | 11 | 1 | 11 | 453 / 3,800 | 216 |
| cluster | `cluster-domcompmgr` | 12 | 1 | 12 | 443 / 4,100 | 167 |
| cluster | `cluster-domowner` | 23 | 1 | 23 | 696 / 7,739 | 196 |
| cluster | `cluster-esa-dedup-domclient-io` | 24 | 1 | 24 | 588 / 8,201 | 145 |
| cluster | `cluster-rdt-network-latency` | 9 | 1 | 9 | 435 / 3,160 | 125 |
| cluster | `cluster-zdom-top-stats` | 7 | 1 | 7 | 404 / 2,525 | 121 |
| cluster | `vsan-direct-cluster` | 8 | **0** | 0 | 127 / 138 | 119 |
| cluster | `vsan-file-service` | 8 | **0** | 0 | 125 / 136 | 138 |
| cluster | `ioinsight` | 82 | **0** | 0 | 118 / 128 | 81 |
| host | `cmmds-net` | 10 | 5 | 50 | 1,178 / 17,293 | 140 |
| host | `vsan-cpu` | 7 | 5 | 35 | 872 / 12,188 | 120 |
| host | `vsan-direct-host` | 8 | **0** | 0 | 124 / 135 | 130 |
| host | `host-domcompmgr` | 16 | 5 | 80 | 2,510 / 27,671 | 127 |
| host | `host-esa-dedup-domclient-io` | 24 | 5 | 120 | 2,526 / 40,919 | 122 |
| host | `vsan-host-net` | 8 | 5 | 40 | 1,172 / 14,161 | 122 |
| host | `host-zdom-top-stats` | 11 | 5 | 55 | 1,859 / 19,225 | 144 |
| host | `vsan-memory` | 12 | 5 | 60 | 1,986 / 21,576 | 161 |
| host | `rdt-network-latency` | 11 | 5 | 55 | 1,251 / 18,950 | 116 |
| host | `vsan-tcpip-stats` | 12 | 5 | 60 | 1,779 / 20,670 | 144 |
| host | `vsan-vnic-net` | 10 | 5 | 50 | 1,246 / 17,526 | 120 |
| host | `vnic-rdt-network-latency` | 10 | 5 | 50 | 1,278 / 17,345 | 126 |
| host | `zdom-vtx` | 10 | 5 | 50 | 1,364 / 17,850 | 125 |
| disk | `cache-disk` | 8 | **0** | 0 | 119 / 129 | 153 |
| disk | `capacity-disk` | 13 | **0** | 0 | 121 / 132 | 118 |
| disk | `vsan-esa-disk-layer` | 5 | 5 | 25 | 920 / 9,417 | 127 |
| disk | `vsan-esa-disk-scsifw` | 5 | 5 | 25 | 766 / 9,316 | 233 |
| vm | `virtual-machine` | 6 | 30 | 180 | 4,884 / 65,245 | 111 |
| vm | `virtual-disk` | 7 | 148 | 1,036 | 19,884 / 372,560 | 253 |
| vm | `vscsi` | 8 | 148 | 1,184 | 23,786 / 414,348 | 250 |

Tier column follows the design's Build 2 table, not the wire `<type>` prefix.

**Totals (serial, one timer around the 30 calls):** 30 calls, 4.395 s wall, 73,430 B wire, 1,148,500 B decoded, 403 entities, 3,246 series (cluster 91, host 705, disk 50, VM 2,400). Per-call p50 128 ms. Slowest three: `virtual-disk` 253 ms, `vscsi` 250 ms, `vsan-esa-disk-scsifw` 233 ms (next `cluster-domclient` 216 ms) `[observed 2026-11-06]`. With Build 1's three types (390 series, ~0.6 s, 9.1 KB wire, evening round) the full 33-type dashboard scope is about 3,636 series and ~5 s serial per cycle on this cluster `[derived from the two rounds; not run as one set]`.

- **Empty types (6), all the wildcard echo** `[{"_typeName":"VsanPerfEntityMetricCSV","entityRefId":"<type>:*","sampleInfo":""}]` with no `value`: `cache-disk`, `capacity-disk` (OSA only; this cluster is ESA), `vsan-direct-cluster`, `vsan-direct-host` (vSAN Direct not configured), `vsan-file-service` (File Service not enabled), `ioinsight` (no IOInsight capture running). An empty type still costs a full call: 81 to 153 ms, ~120 B wire `[observed 2026-11-06; causes inferred from the lab's configuration, not checked per feature]`. That leaves 27 of 33 types with data, which matches the "~27 after learned skips" figure in "Design answers".
- **ESA dedup types return data.** `cluster-esa-dedup-domclient-io` (1 entity) and `host-esa-dedup-domclient-io` (5) returned all 24 requested labels. The Python pack carries both only in its provisional `perfsvc_model_extra.py` (0 objects observed, advertised metrics) and the 2026-11-06 recording did not list them among the empty ones; on this 9.1.1 ESA cluster they are live `[observed 2026-11-06]`.
- **`virtual-disk`: 4 of 7 labels are all `None`.** `NIOPSRead`, `NIOPSReadDelayed`, `NIOPSWrite`, `NIOPSWriteDelayed` arrived for all 148 entities with every token the literal `None` (1,180 tokens; 588 two-bucket series, 4 one-bucket). The other 3 labels have values. Possibly these are IOPS-limit (normalized IOPS) counters that only fill when a storage policy sets an IOPS limit `[observed 2026-11-06; cause unverified]`. `virtual-machine` and `vscsi` had no `None` tokens.
- **Buckets.** Two 5-minute buckets (`05:00:00,05:05:00`) on every entity, except one VM, one vdisk and one vscsi entity that carried only `05:00:00` (one bucket). The per-`entityRefId` last-pushed timestamp in the design handles this `[observed 2026-11-06]`.

### entityRefId grammar per type

The part after the first `:`. One real example each `[observed 2026-11-06]`:

| Type(s) | Grammar | Example |
|---|---|---|
| `vsan-cluster-capacity`, `cluster-domclient`, `cluster-domcompmgr`, `cluster-domowner`, `cluster-esa-dedup-domclient-io`, `cluster-rdt-network-latency`, `cluster-zdom-top-stats` | `<vsan cluster uuid>` | `cluster-domowner:90d067b8-0077-11f1-af60-000c297e270a` |
| `cmmds-net`, `vsan-cpu`, `host-domcompmgr`, `host-esa-dedup-domclient-io`, `vsan-host-net`, `host-zdom-top-stats`, `vsan-memory`, `rdt-network-latency`, `zdom-vtx` | `<host nodeUuid>` | `zdom-vtx:69fd149d-c1b8-aae3-bcb2-3805253936dc` |
| `vsan-tcpip-stats` | `<nodeUuid>\|<stack>` | `vsan-tcpip-stats:6a8859db-a52e-c523-e78c-3805253a02fc\|defaultTcpipStack` |
| `vsan-vnic-net` | `<nodeUuid>\|<stack>\|<vmk>` | `vsan-vnic-net:69fd149d-c1b8-aae3-bcb2-3805253936dc\|defaultTcpipStack\|vmk2` |
| `vnic-rdt-network-latency` | `<nodeUuid>\|<vmk>` | `vnic-rdt-network-latency:6a8859db-a52e-c523-e78c-3805253a02fc\|vmk2` |
| `vsan-esa-disk-layer`, `vsan-esa-disk-scsifw` | `<vsan disk uuid>` (no host in the id) | `vsan-esa-disk-layer:52d171f6-2e48-758a-777f-d5098533d861` |
| `virtual-machine` | `<VM config.instanceUuid>` | `virtual-machine:e8f31d49-d532-4b17-9ef1-7cc33efa33dc` |
| `vscsi` | `<VM config.instanceUuid>\|<controller>:<unit>` | `vscsi:e8f31d49-d532-4b17-9ef1-7cc33efa33dc\|scsi1:0` |
| `virtual-disk` | datastore path without `[datastore] `, optionally with a leading `/` | `virtual-disk:2488e26a-77c5-25bd-da80-38052534dfcc/vcf-lab-automation-runtime-vn26h.vmdk` |
| `vsan-direct-*`, `vsan-file-service`, `ioinsight`, `cache-disk`, `capacity-disk` | not observable here (empty) | n/a |

- Instancing seen: `vsan-tcpip-stats` only `defaultTcpipStack`; `vsan-vnic-net` and `vnic-rdt-network-latency` only `vmk2`; one entity per host for each. `vscsi` controllers `scsi0` (132) and `scsi1` (16), up to 24 devices on one VM `[observed 2026-11-06]`.
- `virtual-disk` path shapes, 148 refs: `<ns uuid>/<file>.vmdk` 109; `/<ns uuid>/<file>.vmdk` (leading slash) 3, e.g. `/a489e06a-d655-c8f9-da07-38052534e318/adfs1.vmdk`; `<ns uuid>/_00ee/<32-hex>.vmdk` 14; `<ns uuid>/_003e/_000e/<32-hex>.vmdk` 22. All nested ones sit in one namespace (`d7528269-...`), possibly the FCD/CNS volume folder `[observed 2026-11-06; FCD reading inferred from pattern]`. No two refs collide after stripping the leading slash `[observed 2026-11-06]`.
- Parse rule for a Java client: split on the first `:` for the type; for the pipe types split the rest on `|`; for `virtual-disk` take the rest whole (it contains `/` and never `|` here) `[observed 2026-11-06]`.

### Join keys per target object

Verified in the same session with read-only calls (timings are single runs) `[observed 2026-11-06]`:

- **Cluster types → ClusterComputeResource.** The suffix is the vSAN cluster uuid `90d067b8-0077-11f1-af60-000c297e270a`, equal to every member host's `config.vsanHostConfig.clusterInfo.uuid` (5/5), which the R2 PropertyCollector read already returns (22 ms, 981 B wire this run). Cluster MoRef comes from that read; 7 of 7 cluster types matched.
- **Host types → HostSystem.** The first `|`-segment is the host's `config.vsanHostConfig.clusterInfo.nodeUuid` from the same R2 read: 5/5 distinct node uuids matched for each of the 12 non-empty host types, no extra uuids.
- **Disk types → host and disk.** The id carries only the vSAN disk uuid, so the owning host has to come from a per-host disk call. Two read-only calls work over JSON and give the same map (5 disks, one per host, 5/5 matched for both ESA types):
  - `POST /sdk/vim25/8.0.3.0/vsan/VimClusterVsanVcDiskManagementSystem/vsan-disk-management-system/QueryVsanManagedDisks`, body `{"host":<HostSystem MoRef>}`: `storagePools[].storagePoolDisks[]` with `vsanUuid`, `disk` (a `HostScsiDisk`), `diskType`, `isMounted`, `isEncrypted`, `dekId`. 31 to 79 ms, ~860 B wire per host. This is the ESA-native view and what the Python pack uses for the host binding.
  - `POST /sdk/vim25/8.0.3.0/HostVsanSystem/<configManager.vsanSystem moId>/QueryDisksForVsan`, body `{}`: every local disk with `state`, `vsanUuid`, `disk`. 7 to 10 ms, ~1.6 KB wire per host. On this ESA cluster the in-use disks report `state: "ineligible"` with a populated `vsanUuid`, and the non-vSAN disks report `ineligible` with `vsanUuid: ""`; key on non-empty `vsanUuid`, not on `state`. The vsanSystem moId needs `configManager.vsanSystem` added to the R2 host pathSet.
  Either way it is one call per host per inventory refresh; the host is the one the call was made against. Five ESA disks here (one per host), not the seven the Python pack observed on 2026-10-22.
- **`virtual-machine` and `vscsi` → VirtualMachine.** Key on `config.instanceUuid` (30/30 VMs; 148/148 vscsi refs over 30 VMs). `config.uuid` (SMBIOS) matched 0/30. Map instanceUuid to the VM MoRef from a PropertyCollector read of `VirtualMachine`; the Ops VirtualMachine object is then reached by MoRef + vCenter instance uuid, as the design states.
- **`virtual-disk` → VirtualMachine.** Strip the leading `/`, then match against each VM's `config.hardware.device[]` `VirtualDisk.backing.fileName` with the `[<datastore>] ` prefix removed: 148/148 refs matched, 30 VMs, no misses. Example backing: `[vcf-lab-mgmt-cl01-vsan] 2488e26a-77c5-25bd-da80-38052534dfcc/vcf-lab-automation-runtime-vn26h.vmdk`. **Cost:** the VM read with `name`, `config.instanceUuid`, `config.uuid`, `config.hardware.device` over a root-folder ContainerView (45 VMs vCenter-wide, 30 on vSAN) was 149 KB wire / 1.09 MB decoded / 70 ms, almost all of it `config.hardware.device`. `virtual-machine`/`vscsi` alone need only `config.instanceUuid`. Scoping the view to the cluster (a ComputeResource is a valid ContainerView container) was not tested.

## Object Model Candidates

entityRefId formats `[observed 2026-11-06]`: cluster-scoped `<type>:<vsan cluster uuid>`; host-scoped `<type>:<host node uuid>`; `host-cpu:<node>|cpu-N`; `vsan-pnic-net:<node>|vmnicN`; `vsan-vnic-net:<node>|<stack>|vmkN`; `vnic-rdt-network-latency:<node>|vmkN`; `vsan-tcpip-stats:<node>|<stack>`; `dom-world-cpu:<node>|<world name>|<id>`; `vsan-esa-disk-*:<vsan disk uuid>`; `virtual-machine:<VM config.instanceUuid>`; `vscsi:<vm instanceUuid>|scsiX:Y`; `virtual-disk:<namespace uuid>/<path>`. VM perf uuids matched `config.instanceUuid` for 30 of 30 VMs. The full model is already in `content/sdk-adapters/vsanhostmetrics/app/perfsvc_model.py`.

## Cross-Request Join Keys

- `VsanPerfNodeInformation.vsanNodeUuid` = `HostSystem.config.vsanHostConfig.clusterInfo.nodeUuid` = host-scoped entityRefId suffix → binds host-scoped perf entities to HostSystem.
- `ClusterComputeResource.configurationEx.vsanConfigInfo.defaultConfig.uuid` = cluster-scoped entityRefId suffix.
- `HostSystem.config.vsanHostConfig.clusterInfo.uuid` = the same vSAN cluster uuid (5 of 5 hosts). Unlike the `configurationEx` sub-paths, this one is retrievable by PropertyCollector `[observed 2026-11-06]`.
- `VirtualMachine.config.instanceUuid` = `virtual-machine:` / `vscsi:` uuid `[re-verified 2026-11-06: 30/30 VMs, 148/148 vscsi refs]`.
- `QueryVsanManagedDisks(host).storagePools[].storagePoolDisks[].vsanUuid` (or non-empty `QueryDisksForVsan()[].vsanUuid`) = `vsan-esa-disk-*` suffix → binds a disk to the host the call was made against `[observed 2026-11-06, 5/5]`.
- `VirtualDisk.backing.fileName` minus `[<datastore>] ` = `virtual-disk:` suffix minus any leading `/` → binds a vdisk to its VM `[observed 2026-11-06, 148/148]`.

## Design answers (scale plan §3)

**Can one call cover all clusters?** No. Every QueryPerf/NodeInformation/StatsObjectInformation call without a cluster faults `SystemError` (server-side `AttributeError` on the missing `_moId`/`_stub`). There is no vCenter-wide query. The cluster is the minimum scope per call, and one wildcard type per call is the minimum within a cluster. Only one cluster was available, so cross-cluster spanning could only be tested as "cluster omitted", and that faults.

**What is the call floor per cycle at 70 clusters?** One call per (cluster, entity type), because a wildcard spec must be alone in its call. Explicit-ref batching is legal (up to 100 refs) but about 6x slower in total, since the server cost is per spec. So the floor is 70 x 33 = 2,310 calls, or 70 x ~27 = 1,890 if types known to be empty on a cluster (OSA disks on ESA, IOInsight without a capture, Direct, File Service) are skipped. At ~0.19 s per call serial that is 6 to 7.5 minutes. At the ~7 calls/s ceiling seen against one cluster it is about 4.5 to 5.5 minutes, if that ceiling is per vsan-health. If it is per cluster, an 8-worker pool across clusters could get to roughly a minute. This must be measured on a multi-cluster vCenter before the design depends on it. Batching specs per cluster, which an earlier draft of scale-plan §3 proposed, does not work; the plan's §3 now lists parallelism across clusters as the only lever on wall time. The 7-minute window is fine but saves almost nothing.

**Does labels help?** Yes for bytes and parsing: the response holds only the requested labels, and wire and XML size fall 45 to 48% (1.31 MB to 0.68 MB XML per cluster cycle here). No measurable wall-time gain, so it is a memory/CPU lever, not a latency lever. It can also remove the in-process `keep` filtering.

**Does GetSupportedEntityTypes replace probing?** No. It takes no cluster, so it describes the vSAN version, not the cluster's features. It advertised PMem types that then faulted `NotSupported` on this cluster. Its ids also differ from the working query prefixes for 4 types (`vm`, `tcpip`, `vmdk-ioinsight`, `domcomp-sched`), and its metric lists understate what is returned. It is useful once per vCenter build to find new types. Per-cluster learning (remember `NotSupported`/`InvalidArgument` per type, re-probe daily) is still needed. Now that batching is ruled out, that probing is cheap: a faulting type costs 0.04 to 0.07 s.

## Recording (simulator seed)

`/mnt/holding/vsan-perfsvc-recording-2026-11-06/`: `manifest.json` (capture time, vCenter build, vsanServiceVersions.xml, cluster/host/node/VM uuids, vdisk and vscsi refs, a per-call index), `supported-entity-types.json`, `aggregated-entity-types.json`, and `perf/<type>.json` for 73 prefixes (model plus advertised; 58 ok, 41 with objects, 15 faults kept with their fault text). 15-minute window, no labels, 3.81 MB. No credentials were found in any file (checked by scan).

## Gaps / Questions

- One vSAN cluster only: whether the throughput ceiling is per cluster or per vCenter, and cross-cluster behaviour, remain unverified.
- Verbose mode is off here, so 1-minute point density and the high-res spec class are unobserved.
- OSA (`disk-group`, `cache-disk`, `capacity-disk`), File Service, iSCSI, Direct and IOInsight returned no objects. Payload sizes for them are unknown.
- The query prefix for advertised `domcomp-sched` was not found.
- Explicit-ref call time (~0.15 to 0.2 s per ref) was measured once per size and not profiled further. A same-session re-run gave 100 refs in 8.4 s (SOAP) / 7.2 s (JSON), so the earlier 15 to 22 s was partly server noise.
- JSON API: session idle timeout not measured; release ids below 8.0.3.0 only tested for 8.0.0.0 and 7.0.3.0.
- Build 2 types empty on this lab, so entity id form and payload size are unobserved: `vsan-direct-cluster`, `vsan-direct-host`, `vsan-file-service`, `ioinsight`, `cache-disk`, `capacity-disk`. In particular, whether `vsan-direct-cluster`, `vsan-file-service` and `ioinsight` key on the cluster uuid or a host nodeUuid (the Python pack's provisional model says host) is still open.
- `virtual-disk` `NIOPS*` labels were all `None`; whether they fill under an IOPS-limit policy is unverified.
- Only one vSAN stack (`defaultTcpipStack`) and one vSAN vmknic (`vmk2`) per host here, so multi-stack / multi-vmk instancing of `vsan-tcpip-stats`, `vsan-vnic-net`, `vnic-rdt-network-latency` is unobserved.
- vim25 inventory: no multi-cluster vCenter, so RetrievePropertiesEx paging (`token`) and R2 cost at 70 clusters are unmeasured. A non-vSAN host inside a vSAN cluster was not available. The `vsan-pnic-net` NIC selection rule (vSAN uplinks vs link-up NICs) could not be separated here. The `configurationEx` sub-path fault was seen over JSON only; SOAP was not re-tested.
