# API Map: vSAN Performance Service (VsanPerformanceManager, vsan-health)

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** vcf-lab-vcenter-mgmt.int.sentania.net:443 (vCenter 9.1.1.0100 build 25784172, one ESA vSAN cluster `vcf-lab-mgmt-cl01`, 5 hosts 9.1.1, 30 VMs)
- **Last updated:** 2026-11-06
- **Update history:**
  - 2026-11-06 (later) — added "JSON API transport": vSphere JSON-over-HTTP (`/sdk/vim25/<release>/vsan/...`) measured against SOAP on the same cluster and window; verbatim samples added under `reference/docs/vsan-perfsvc-json/`.
  - 2026-11-06 — initial mapping. Answers the collector questions in `knowledge/context/investigations/2026-11-06-vsanhostmetrics-scale-plan.md` §3: batching limits, cluster-omitted calls, labels, window/interval, concurrency, session cost. Also captured one full raw collection cycle to `/mnt/holding/vsan-perfsvc-recording-2026-11-06/` (simulator seed, outside the repo).
- **Evidence basis:** live API calls (JSON section: raw HTTPS from Python `http.client`, no SDK; other sections: pyVmomi 9.0.0.0 with the pack's vendored bindings, vsan binding version `vsan.version.v9_0_0_0`; server advertises urn:vsan 9.1.1.0); vendored type definitions in `content/sdk-adapters/vsanhostmetrics/app/vendor/vsanmgmtObjects.py`.
- **Notes:** Read-only. Only `VsanPerfQueryPerf`, `VsanPerfGetSupportedEntityTypes`, `VsanPerfGetAggregatedEntityTypes`, `VsanPerfQueryNodeInformation`, `VsanPerfQueryStatsObjectInformation`, vim25 property reads, and a GET of `/sdk/vsanServiceVersions.xml` were issued. **Only one vSAN cluster exists in this vCenter**, so every cross-cluster conclusion is single-cluster evidence. Timings are wall-clock from a workstation on the lab LAN; serial loops varied 6 to 22 s run to run on the same work, so treat single numbers as noisy.

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
| A wildcard spec must be the **only** spec (2 wildcards fault; 1 wildcard + 1 explicit faults too, in either order) | `wildcardlimit` | Only one wildcard query allowed in query specs. |
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

Top level is a JSON array of `VsanPerfEntityMetricCSV`. Every object carries `_typeName`. Verbatim sample: `reference/docs/vsan-perfsvc-json/queryperf-cluster-domclient-2026-11-06.json` (1 entity, 14 series); fault sample: `reference/docs/vsan-perfsvc-json/queryperf-fault-wildcardlimit-2026-11-06.json` `[observed 2026-11-06]`.

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

Use the JSON API. It reaches the same vsan-health handlers with identical batching limits, fault keys and cluster requirement, matches or beats SOAP on wall time, and has the same ~7 calls/s ceiling, so the collector design from the SOAP sections carries over unchanged. It removes the need for the vim25 and vSAN SDK jars: a Java 11+ `HttpClient` plus Jackson (or Gson) and four small POJOs (`QuerySpec`, `EntityMetricCSV`, `MetricSeriesCSV`, `MetricId`) cover it. Pin the release id to the oldest one the pak supports that the vCenter accepts (8.0.3.0 worked here; 8.0.0.0 did not), or read `about.apiVersion` at connect. Rules to build in: always send `_typeName` on specs, UTC dates only, `Accept-Encoding: gzip`, the `vmware-api-session-id` header on one session per vCenter per cycle, one wildcard type per call, parse `None` tokens, and dispatch on `faultMessage[].key`. The cost is ~40% more wire bytes and a larger decoded body than SOAP; stream-parse the array if memory matters. Unverified: JSON API availability on vCenter releases older than 8.0U1 (the JSON API arrived in 8.0U1 `[inferred from docs, not checked here]`), and behaviour across multiple clusters.

## Object Model Candidates

entityRefId formats `[observed 2026-11-06]`: cluster-scoped `<type>:<vsan cluster uuid>`; host-scoped `<type>:<host node uuid>`; `host-cpu:<node>|cpu-N`; `vsan-pnic-net:<node>|vmnicN`; `vsan-vnic-net:<node>|<stack>|vmkN`; `vnic-rdt-network-latency:<node>|vmkN`; `vsan-tcpip-stats:<node>|<stack>`; `dom-world-cpu:<node>|<world name>|<id>`; `vsan-esa-disk-*:<vsan disk uuid>`; `virtual-machine:<VM config.instanceUuid>`; `vscsi:<vm instanceUuid>|scsiX:Y`; `virtual-disk:<namespace uuid>/<path>`. VM perf uuids matched `config.instanceUuid` for 30 of 30 VMs. The full model is already in `content/sdk-adapters/vsanhostmetrics/app/perfsvc_model.py`.

## Cross-Request Join Keys

- `VsanPerfNodeInformation.vsanNodeUuid` = `HostSystem.config.vsanHostConfig.clusterInfo.nodeUuid` = host-scoped entityRefId suffix → binds host-scoped perf entities to HostSystem.
- `ClusterComputeResource.configurationEx.vsanConfigInfo.defaultConfig.uuid` = cluster-scoped entityRefId suffix.
- `VirtualMachine.config.instanceUuid` = `virtual-machine:` / `vscsi:` uuid.

## Design answers (scale plan §3)

**Can one call cover all clusters?** No. Every QueryPerf/NodeInformation/StatsObjectInformation call without a cluster faults `SystemError` (server-side `AttributeError` on the missing `_moId`/`_stub`). There is no vCenter-wide query. The cluster is the minimum scope per call, and one wildcard type per call is the minimum within a cluster. Only one cluster was available, so cross-cluster spanning could only be tested as "cluster omitted", and that faults.

**What is the call floor per cycle at 70 clusters?** One call per (cluster, entity type), because a wildcard spec must be alone in its call. Explicit-ref batching is legal (up to 100 refs) but about 6x slower in total, since the server cost is per spec. So the floor is 70 x 33 = 2,310 calls, or 70 x ~27 = 1,890 if types known to be empty on a cluster (OSA disks on ESA, IOInsight without a capture, Direct, File Service) are skipped. At ~0.19 s per call serial that is 6 to 7.5 minutes. At the ~7 calls/s ceiling seen against one cluster it is about 4.5 to 5.5 minutes, if that ceiling is per vsan-health. If it is per cluster, an 8-worker pool across clusters could get to roughly a minute. This must be measured on a multi-cluster vCenter before the design depends on it. Item 1 of scale-plan §3 (batch specs per cluster) does not work as written. Item 3 (a 7-minute window) is fine, but it saves almost nothing.

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
