# API Map: vSAN Performance Service (VsanPerformanceManager, vsan-health)

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** vcf-lab-vcenter-mgmt.int.sentania.net:443 (vCenter 9.1.1.0100 build 25784172, one ESA vSAN cluster `vcf-lab-mgmt-cl01`, 5 hosts 9.1.1, 42 VMs registered in the cluster of which 30 powered on (corrected in the P2 round); plus one standalone non-vSAN host `vcf-lab-mgmt-esx06`, first noted in the inventory round). P2 round also: VCF Ops `devel` 9.0.2.0, Suite API
- **Last updated:** 2026-11-06
- **Update history:**
  - 2026-11-06 (night) — added "P2: VM and disk joins over JSON, Ops cluster and VM targets (measured 2026-11-06)" for design Prerequisite P2: cluster-rooted VM ContainerView, light vs device read cost, `maxObjects` paging with `ContinueRetrievePropertiesEx`, vscsi bus-position and vdisk joins, `QueryDisksForVsan` shape and the ESA disk uuid match, netstacks/vmknics, Ops ClusterComputeResource and VirtualMachine identifiers (`VMEntityInstanceUUID` empty on the 30 target VMs), and a `VCFCF Test|` push and read-back on one cluster and one VM on devel. 17 verbatim files and `PROVENANCE-2026-11-06-p2.md` under `reference/docs/extracted/vsan-perfsvc-json/`. Corrected "30 on vSAN of 45" (42 in the cluster, 30 powered on). Two join-key lines amended, gaps updated; other earlier sections untouched and not re-verified.
  - 2026-11-06 (late evening) — added "Build 2 entity types (measured 2026-11-06)": the 30 remaining dashboard-scope types over JSON with COVERED labels (per-type table, totals, entityRefId grammar, 6 empty types, join keys verified against PropertyCollector, `QueryVsanManagedDisks` and `QueryDisksForVsan`); 24 verbatim samples and `PROVENANCE-2026-11-06-build2.md` under `reference/docs/extracted/vsan-perfsvc-json/`. Two join-key lines and gaps appended. Earlier sections untouched and not re-verified, apart from the instanceUuid and cluster/node uuid joins, which were re-verified.
  - 2026-11-06 (evening) — added "vim25 inventory over JSON" for design Prerequisite P1: per-object GET vs PropertyCollector for the cluster/host inventory reads, the `configurationEx` sub-path fault, and verbatim JSON samples for `host-domclient`, `host-domowner`, `vsan-pnic-net` (Build 1 labels), `VsanPerfQueryNodeInformation` and the RetrievePropertiesEx read, under `reference/docs/extracted/vsan-perfsvc-json/`. Earlier sections untouched and not re-verified this round.
  - 2026-11-06 (later) — added "JSON API transport": vSphere JSON-over-HTTP (`/sdk/vim25/<release>/vsan/...`) measured against SOAP on the same cluster and window; verbatim samples added under `reference/docs/extracted/vsan-perfsvc-json/`.
  - 2026-11-06 — initial mapping. Answers the collector questions in `knowledge/context/investigations/2026-11-06-vsanhostmetrics-scale-plan.md` §3: batching limits, cluster-omitted calls, labels, window/interval, concurrency, session cost. Also captured one full raw collection cycle to `/mnt/holding/vsan-perfsvc-recording-2026-11-06/` (simulator seed; local-only artifact, outside the repo and not reproducible from it; regenerate with the procedure in the Recording section).
- **Evidence basis:** live API calls (P2 section adds the VCF Ops Suite API on devel; JSON section: raw HTTPS from Python `http.client`, no SDK; other sections: pyVmomi 9.0.0.0 with the pack's vendored bindings, vsan binding version `vsan.version.v9_0_0_0`; server advertises urn:vsan 9.1.1.0); vendored type definitions in `content/sdk-adapters/vsanhostmetrics/app/vendor/vsanmgmtObjects.py`.
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

## P2: VM and disk joins over JSON, Ops cluster and VM targets (measured 2026-11-06)

Answers design Prerequisite P2 and part of Q9 (`knowledge/designs/vsanperf-mp-v2.md`). Same vCenter and transport as the sections above (release `8.0.3.0`, raw `http.client`, gzip, one session per script, logged out `204`), plus devel VCF Ops 9.0.2.0 for the Suite API side. Window 2026-11-07 05:15 to 05:45 UTC. Verbatim bodies and exact requests: `reference/docs/extracted/vsan-perfsvc-json/PROVENANCE-2026-11-06-p2.md` `[observed 2026-11-06]`.

### VM inventory scoped to one cluster

- **A ContainerView rooted at the cluster works.** `CreateContainerView` with `container` = the `ClusterComputeResource` MoRef (`domain-c6004`), `type ["VirtualMachine"]`, `recursive true`, then the usual `view` traversal: HTTP 200, **42 VMs**. The traversal alternative (ObjectSpec on the cluster MoRef, `skip true`, `ComputeResource.host` then `HostSystem.vm`) returns the same 42 at the same cost. A root-folder view returns 45; the 3 extra are on the standalone `vcf-lab-mgmt-esx06` `[observed 2026-11-06]`.
- **Correction to the earlier "30 on vSAN of 45".** 42 VMs are registered in the vSAN cluster, not 30. The other 12 are all `poweredOff` (10 templates, 2 VMs; 11 on the vSAN datastore, 1 template on NFS). The 30 perf VMs are exactly the 30 powered-on VMs in the cluster (30/30 instanceUuids, no perf VM outside the view). So cluster scoping drops only the 3 VMs outside the cluster here; the per-cluster read still carries templates and powered-off VMs `[observed 2026-11-06; "perf covers powered-on VMs only" is one lab, one window]`.

| Read (42 VMs, cluster view) | Wire B | Decoded B | ms p50 (n=3 after a first call) | per VM wire / decoded |
|---|---|---|---|---|
| light: `name`, `config.instanceUuid`, `runtime.host` | 4,307 | 51,322 | 8.9 (first 9.8) | ~103 B / ~1.2 KB |
| + `config.hardware.device` | 142,035 | 1,043,400 | 60.0 (first 73.2) | ~3.4 KB / ~24.8 KB |
| light, root-folder view (45 VMs) | 4,536 | 54,932 | 10.9 | |
| + devices, root-folder view (45) | 149,339 | 1,093,984 | 65.9 | |

`[observed 2026-11-06]`. The device list is ~97% of the bytes, as the earlier root-view measurement said; the per-VM figures agree with it (3.3 KB / 24 KB).

- **The device list cannot be narrowed by path.** `config.hardware.device.backing` faults HTTP 500 `{"_typeName":"InvalidProperty","name":"config.hardware.device.backing"}`. The whole `config.hardware.device` array comes back (here 15 device classes: 160 `VirtualDisk`, 84 `VirtualIDEController`, 42 each of keyboard, PS/2, PCI, SIO, video, VMCI, vmxnet3, 32 `ParaVirtualSCSIController`, 19 `VirtualAHCIController`, 18 `VirtualCdrom`, 17 `VirtualLsiLogicController`, 15 USB). Filter client side to `VirtualDisk` plus the controllers they point at `[observed 2026-11-06]`. Key-indexed paths (`device[2000]`) were not tried.
- **VirtualDisk fields used** (verbatim in the devices pages): `key` (e.g. 2000), `deviceInfo.label` (`Hard disk 1`), `backing.fileName` (`[vcf-lab-mgmt-cl01-vsan] a489e06a-.../adfs1.vmdk`), `backing.datastore` (MoRef), `controllerKey` (1000), `unitNumber` (0), plus `backing.uuid`, `backing.backingObjectId`, `diskObjectId` (`588-2000`), `capacityInBytes`. The controller device (found by `key` = `controllerKey` in the same array) carries `busNumber` `[observed 2026-11-06]`.
- **Paging works over JSON.** `RetrieveOptions.maxObjects: 10` is honoured exactly: 42 VMs come back as 10/10/10/10/2. The result carries `"token"` (a short string, here `"4"`, `"5"`, `"6"`, `"7"`: a fresh token per page) while more remain and omits it on the last page. `ContinueRetrievePropertiesEx` with `{"token":"<t>"}` returns the next `RetrieveResult` in the same shape. A token that was already consumed faults HTTP 500 `{"_typeName":"InvalidArgument","invalidProperty":"token",...}`, so a client must use each token once and in order `[observed 2026-11-06]`.

| Chain, maxObjects 10 | pages | total wire B | total decoded B | total ms | largest page decoded |
|---|---|---|---|---|---|
| light | 5 | 5,056 | 51,638 | 19.5 | 12,328 |
| devices | 5 | 142,138 | 1,043,716 | 80.5 | 314,138 (10 VMs) |

  Paging costs ~1.3x the unpaged wall time for the devices read and ~2x for the light one (more round trips), and caps the decoded size per page; the 314 KB page shows that per-VM device size varies ~1.5x around the mean `[observed 2026-11-06]`.

### VM joins: vscsi bus position and virtual-disk path

From the 42-VM devices read and a same-session perf query (window 05:24:49Z to 05:31:49Z) `[observed 2026-11-06]`:

- **`vscsi` instance = controller `busNumber` + `unitNumber`.** For every `VirtualDisk`, `<prefix><controller.busNumber>:<disk.unitNumber>` with prefix `scsi` reproduces **148/148** `vscsi:<instanceUuid>|scsiN:M` refs. Controllers on this lab: `ParaVirtualSCSIController` (93 disks) and `VirtualLsiLogicController` (67); both map to `scsi`. No SATA (`VirtualAHCIController`), NVMe or IDE disk exists here, so the vscsi prefix for those is **unobserved**.
- **`virtual-disk` by backing path:** 148/148 matched (leading `/` stripped, `[<datastore>] ` removed), re-verifying the earlier round.
- **Same disk, both ids.** For all 148 vdisks the bus position derived from the device read is also a `vscsi` ref on the same VM. So a `virtual-disk` entity can be instanced by `scsiN:M` with no further lookup, which supports design Q5 `[observed 2026-11-06]`.
- `deviceInfo.label` is unique per VM (no duplicate (VM, label)); 24 distinct labels (`Hard disk 1` to `Hard disk 24`). Localization and renumbering after a disk removal remain unverified.
- 160 `VirtualDisk`s in the cluster, 148 in perf: the 12 not in perf are one disk each on the 12 powered-off VMs.

### QueryDisksForVsan (one host, all five measured)

- **Request:** `POST /sdk/vim25/8.0.3.0/HostVsanSystem/<configManager.vsanSystem moId>/QueryDisksForVsan`, body `{}`. The moId here is `vsanSystem-<host number>` (`vsanSystem-15151` for `host-15151`), read from `configManager.vsanSystem` in RetrievePropertiesEx; the read with `name`, nodeUuid, `configManager.vsanSystem`, `config.network.vnic`, `config.network.netStackInstance`, `config.vsanHostConfig.networkInfo` for 5 hosts was 14,685 B wire / 144,214 B decoded / 31 ms (the network paths are the bulk; `configManager.vsanSystem` alone adds a MoRef per host) `[observed 2026-11-06]`.
- **Response:** a bare JSON array of `VsanHostDiskResult`, one per local disk (3 per host here): `{_typeName, disk: HostScsiDisk, state, vsanUuid, error}`. `disk` carries `canonicalName`, `uuid`, `deviceName`, `ssd`, `capacity`, `serialNumber`, `model`, and, on the vSAN disk only, `vsanDiskInfo: {"_typeName":"VsanHostVsanDiskInfo","vsanUuid":"<same uuid>","formatVersion":24}` `[observed 2026-11-06]`.
- **Identifying the vSAN disk:** top-level `vsanUuid` non-empty (equal to `disk.vsanDiskInfo.vsanUuid`). **`state` is `"ineligible"` on all 15 disks** in the lab, in use or not. The in-use disk's `error` is `VsanFault` with `faultMessage[0].key` = `vim.hostd.vsanDiskOperation.inUseByStoragePool`; the unused ones carry `DiskHasPartitions`. Key on non-empty `vsanUuid`; `state` does not separate them on ESA (`VsanHostDiskResultState` also defines `inUse` and `eligible` `[inferred from docs; not seen here]`) `[observed 2026-11-06]`.
- **Cost:** 8.3 / 9.8 / 10.8 / 10.8 / 11.2 ms, 1,548 to 1,602 B wire, 7,707 to 7,734 B decoded per host. `QueryVsanManagedDisks` for the same hosts: 29.9 to 56.1 ms, 858 to 862 B wire, 3,067 B decoded; response `{_typeName, storagePools:[{_typeName, storagePoolDisks:[{_typeName, disk, vsanUuid, isMounted, isEncrypted, dekId, diskType}]}]}`. Both gave the same 5 uuids `[re-verified 2026-11-06]`.

### ESA disk id = QueryDisksForVsan vsanUuid

All 5 `vsan-esa-disk-layer` ids in a fresh query, all 5 in this session's `vsan-esa-disk-scsifw` query, and all 5 in the earlier saved capture (`queryperf-vsan-esa-disk-layer-2026-11-06.json`) equal a non-empty `vsanUuid` from `QueryDisksForVsan` on exactly one host; no unmatched id and no extra disk in the map `[observed 2026-11-06]`:

| ESA disk uuid | host |
|---|---|
| `52d171f6-2e48-758a-777f-d5098533d861` | `host-15151` (esx04) |
| `52c7ed3e-9dcf-b82e-8177-f704806c2e4a` | `host-31189` (esx05) |
| `52bde68f-b0e5-6952-075b-bcb49bd54fa6` | `host-6015` (esx02) |
| `52585910-fedf-604c-04d3-868955bf7f7d` | `host-6017` (esx01) |
| `52850722-bc18-61ea-8400-190ec367ac70` | `host-6011` (esx03) |

### Netstacks and vmknics per host

- Every host has **8 netstack instances** (`defaultTcpipStack`, `vmotion`, `vSphereProvisioning`, `vxlan`, `hyperbus`, `mirror`, `ops`, `vnetworking`) and **6 or 7 vmknics** (`vmk0`, `vmk2`, `vmk3` on 3 hosts, on `defaultTcpipStack`; `vmk1` on `vmotion`; `vmk10`, `vmk11` on `vxlan`; `vmk50` on `hyperbus`). Only **`vmk2`** is in `config.vsanHostConfig.networkInfo.port` on each host `[observed 2026-11-06]`.
- The perf types report only the vSAN vmknic and its stack: `vsan-tcpip-stats` 5 ids, all `<node>|defaultTcpipStack`; `vsan-vnic-net` 5, all `<node>|defaultTcpipStack|vmk2`; `vnic-rdt-network-latency` 5, all `<node>|vmk2` (window 05:24:49Z to 05:31:49Z). Other stacks and vmknics, including the second vmknic on `defaultTcpipStack` (`vmk0`, `vmk3`), do not appear `[observed 2026-11-06]`.
- **Multi-stack and multi-vmk instancing remain unobserved.** The lab has many stacks and vmknics, but only one vSAN-tagged vmknic per host, so it cannot show a host with two vSAN stacks or two vSAN vmknics. What it does show: the types are filtered to vSAN-tagged vmknics, not to every vmknic on the stack `[observed 2026-11-06; selection rule inferred from one tagging layout]`.

### Ops side (devel, VCF Operations 9.0.2.0)

- **Cluster:** `GET /suite-api/api/resources?adapterKind=VMWARE&resourceKind=ClusterComputeResource` returns 3 clusters (8,938 B, 167 ms). Identifiers: `VMEntityObjectID` (the MoRef, `domain-c6004`, `isPartOfUniqueness: true`), `VMEntityVCID` (the vCenter `about.instanceUuid`, `4ff53df1-d47a-4fb9-b6f8-b96c6ce8ae8e`, `isPartOfUniqueness: true`), `VMEntityName` (not part of uniqueness; **empty string** on `vcf-lab-mgmt-cl01`, the resource `name` is set; populated on the two workload clusters). Ops id `d8b36417-e50a-4f42-84f7-ff0020501d55`. The (MoRef, VCID) pair resolves the cluster exactly as `OpsHostMap` resolves hosts `[observed 2026-11-06]`.
- **VirtualMachine:** `...&resourceKind=VirtualMachine&pageSize=500` returns all 109 VMs in one page: **319,014 B, 1,357 ms, ~2.9 KB per VM**, no gzip (Ops sent no `Content-Encoding` despite `Accept-Encoding: gzip`). Identifiers on every VM: `VMEntityObjectID` (MoRef, uniqueness), `VMEntityVCID` (uniqueness), `VMEntityInstanceUUID`, `VMEntityName`, `isPingEnabled`, `VMServiceMonitoringEnabled` (the last four not part of uniqueness). (MoRef, VCID) matched **45/45** of the mgmt vCenter's VMs `[observed 2026-11-06]`.
- **`VMEntityInstanceUUID` is not reliable.** Where populated it equals vCenter `config.instanceUuid` (15/15). But it is **empty on 30 of the 45 mgmt-vCenter VMs, and those 30 are exactly the 30 powered-on vSAN perf VMs** (their `VMEntityName` is empty too). It is populated on the 12 powered-off cluster VMs, the 3 VMs on esx06, and all 64 VMs of the two workload vCenters. Cause unknown (possibly how these resources were first discovered on devel) `[observed 2026-11-06; cause unverified]`. The VM-tier targets are the ones that lack it, so it cannot serve as a resolution path or as a pass/fail cross-check on this instance; resolve on (MoRef, VCID).
- **Push onto both kinds works.** One batch `POST /suite-api/api/resources/stats` with `VCFCF Test|Build2|clusterKey` = 42.0 on the cluster and the instanced `VCFCF Test|Build2|vdisk:scsi0:0|probe` = 7.0 on VM `adfs1` (`vm-39030`, Ops id `0b2a707d-b2b7-414c-85a3-2d607a1bd9e9`), one sample at `1794029593951` (2026-11-07 05:33:13.951 UTC): HTTP 200, empty body, 28 ms. Baseline: 317 stat keys on the cluster, 230 on the VM, none `VCFCF*` `[observed 2026-11-06]`.
- **Both read back.** The VM's instanced key was readable on the first read, ~42 s after the push; the cluster key first read back ~343 s after it (the poll ~30 s earlier was empty). Both carry timestamp `1794029593951` and the pushed value; `/statkeys` then lists exactly the one `VCFCF*` key on each resource. The cluster lag (between ~5 and ~6 min) is longer than the 1 to 4 min seen for HostSystem in `knowledge/context/investigations/2026-11-06-suite-api-instanced-push.md`; a self-check must allow at least 6 min `[observed 2026-11-06, one sample each]`.
- Read-back request: `GET /suite-api/api/resources/<id>/stats?statKey=<url-encoded key>&begin=<ts-60000>&end=<ts+60000>`, no rollup parameters (the earlier investigation's rule). The response is `{"values":[{"resourceId":..,"stat-list":{"stat":[{"timestamps":[1794029593951],"statKey":{"key":"VCFCF Test|Build2|vdisk:scsi0:0|probe"},"intervalUnit":{"quantifier":1},"data":[7.0]}]}}]}`: the instanced key with a colon inside the instance (`scsi0:0`) is stored verbatim `[observed 2026-11-06]`.
- Ops closed an idle keep-alive connection after ~30 s (`RemoteDisconnected` on the next request). A Java client that keeps a Suite API connection between cycles must expect that and reconnect `[observed 2026-11-06, once]`.
- What remains on devel: the two test keys above, on those two resources; no per-key delete exists, data ages out. One Ops auth token from the first push script was not released (the script stopped on the dropped connection after the push); it expires on its own.

## P3: all 69 types, no labels (measured 2026-11-07)

Answers Prerequisite P3 and open questions Q4 and Q5 of `knowledge/designs/vsanperf-mp-v3.md`. Same vCenter (9.1.1.0100 build 25784172), cluster `domain-c6004` (5 hosts, ESXi 9.1.1.0100 build 25782009) and transport as "Build 2 entity types": release `8.0.3.0`, raw `http.client`, gzip, one session for the 69 queries (logged out `204`), one wildcard spec per call, serial, window `2026-11-07T13:47:50Z` to `13:54:50Z` (7 min), and **no `labels` key** on any call. Types: the 69 keys of the Python pack's `perfsvc_model.ENTITIES` + `perfsvc_model_extra.ENTITIES` at fork tag `v2.0.0-rc.2`, 33 shipped (kind in `metric_scope.COVERED`) and 36 new (exactly the design's §New types). Verbatim bodies, exact requests and per-file sizes: `reference/docs/extracted/vsan-perfsvc-json/PROVENANCE-2026-11-07-all.md` (69 `all-<type>.json`, 26 `probe-explicit-*.json`) `[observed 2026-11-07]`.

### Per-type results

"Labels returned / model" compares the distinct labels returned with the type's label list in the PY model (both files, `Actual` twins included, since the model carries them). "Beyond model" = returned but not in the model. Every type with data returned **every** model label (0 missing on all 41) `[observed 2026-11-07]`.

| Type | Set | Result | Entities | Series | Labels returned / model | Labels beyond model | entityRefId form | Wire / decoded B | ms |
|---|---|---|---|---|---|---|---|---|---|
| `cache-disk` | shipped | empty echo | 0 | 0 | 0 / 8 | 0 | n/a (echo) | 119 / 129 | 179.5 |
| `capacity-disk` | shipped | empty echo | 0 | 0 | 0 / 13 | 0 | n/a (echo) | 121 / 132 | 147.4 |
| `cluster-domclient` | shipped | data | 1 | 14 | 14 / 14 | 0 | `<vsan cluster uuid>` | 512 / 4,774 | 128.7 |
| `cluster-domcompmgr` | shipped | data | 1 | 15 | 15 / 15 | 0 | `<vsan cluster uuid>` | 507 / 5,092 | 107.8 |
| `cluster-domowner` | shipped | data | 1 | 46 | 46 / 46 | 0 | `<vsan cluster uuid>` | 1,045 / 15,407 | 134.3 |
| `cluster-esa-dedup-domclient-io` | shipped | data | 1 | 42 | 42 / 24 | 18 | `<vsan cluster uuid>` | 823 / 14,182 | 141.8 |
| `cluster-rdt-network-latency` | shipped | data | 1 | 17 | 17 / 17 | 0 | `<vsan cluster uuid>` | 575 / 5,747 | 112.7 |
| `cluster-zdom-top-stats` | shipped | data | 1 | 12 | 12 / 12 | 0 | `<vsan cluster uuid>` | 466 / 4,123 | 122.0 |
| `cmmds-net` | shipped | data | 5 | 50 | 10 / 10 | 0 | `<nodeUuid>` | 1,108 / 17,291 | 164.8 |
| `host-domclient` | shipped | data | 5 | 390 | 78 / 78 | 0 | `<nodeUuid>` | 7,815 / 129,720 | 131.1 |
| `host-domcompmgr` | shipped | data | 5 | 410 | 82 / 82 | 0 | `<nodeUuid>` | 8,028 / 136,120 | 121.1 |
| `host-domowner` | shipped | data | 5 | 1440 | 288 / 288 | 0 | `<nodeUuid>` | 25,488 / 482,103 | 129.0 |
| `host-esa-dedup-domclient-io` | shipped | data | 5 | 210 | 42 / 24 | 18 | `<nodeUuid>` | 3,830 / 70,831 | 110.0 |
| `host-zdom-top-stats` | shipped | data | 5 | 95 | 19 / 19 | 0 | `<nodeUuid>` | 2,548 / 32,055 | 107.0 |
| `ioinsight` | shipped | empty echo | 0 | 0 | 0 / 82 | 0 | n/a (echo) | 118 / 128 | 117.4 |
| `rdt-network-latency` | shipped | data | 5 | 85 | 17 / 17 | 0 | `<nodeUuid>` | 2,339 / 28,650 | 367.6 |
| `virtual-disk` | shipped | data | 148 | 1036 | 7 / 7 | 0 | datastore path (`<ns uuid>/...vmdk`) | 20,752 / 372,600 | 273.0 |
| `virtual-machine` | shipped | data | 30 | 240 | 8 / 8 | 0 | `<VM instanceUuid>` | 5,634 / 84,490 | 142.3 |
| `vnic-rdt-network-latency` | shipped | data | 5 | 85 | 17 / 17 | 0 | `<nodeUuid>|vmkN` | 2,407 / 28,700 | 115.9 |
| `vsan-cluster-capacity` | shipped | data | 1 | 6 | 6 / 6 | 0 | `<vsan cluster uuid>` | 427 / 2,245 | 105.0 |
| `vsan-cpu` | shipped | data | 5 | 35 | 7 / 7 | 0 | `<nodeUuid>` | 865 / 12,188 | 116.2 |
| `vsan-direct-cluster` | shipped | empty echo | 0 | 0 | 0 / 8 | 0 | n/a (echo) | 127 / 138 | 127.5 |
| `vsan-direct-host` | shipped | empty echo | 0 | 0 | 0 / 8 | 0 | n/a (echo) | 124 / 135 | 119.5 |
| `vsan-esa-disk-layer` | shipped | data | 5 | 190 | 38 / 38 | 0 | `<vsan disk uuid>` | 4,122 / 64,047 | 130.0 |
| `vsan-esa-disk-scsifw` | shipped | data | 5 | 80 | 16 / 16 | 0 | `<vsan disk uuid>` | 2,360 / 27,425 | 123.0 |
| `vsan-file-service` | shipped | empty echo | 0 | 0 | 0 / 8 | 0 | n/a (echo) | 125 / 136 | 110.1 |
| `vsan-host-net` | shipped | data | 5 | 80 | 16 / 16 | 0 | `<nodeUuid>` | 2,091 / 27,136 | 135.1 |
| `vsan-memory` | shipped | data | 5 | 250 | 50 / 50 | 0 | `<nodeUuid>` | 5,960 / 85,581 | 125.2 |
| `vsan-pnic-net` | shipped | data | 10 | 650 | 65 / 65 | 0 | `<nodeUuid>|vmnicN` | 11,315 / 211,228 | 124.1 |
| `vsan-tcpip-stats` | shipped | data | 5 | 160 | 32 / 32 | 0 | `<nodeUuid>|defaultTcpipStack` | 3,552 / 53,267 | 122.0 |
| `vsan-vnic-net` | shipped | data | 5 | 320 | 64 / 64 | 0 | `<nodeUuid>|defaultTcpipStack|vmkN` | 5,658 / 105,441 | 135.3 |
| `vscsi` | shipped | data | 148 | 1184 | 8 / 8 | 0 | `<VM instanceUuid>|scsiN:M` | 24,059 / 414,216 | 251.3 |
| `zdom-vtx` | shipped | data | 5 | 355 | 71 / 71 | 0 | `<nodeUuid>` | 6,976 / 119,955 | 109.8 |
| `clom-disk` | new | fault `InvalidArgument` | - | - | 0 / 3 | 0 | n/a (fault) | 140 / 151 | 38.8 |
| `clom-host` | new | fault `InvalidArgument` | - | - | 0 / 2 | 0 | n/a (fault) | 140 / 151 | 38.9 |
| `cluster-esa-dedup-domcompmgr-io` | new | data | 1 | 42 | 42 / 24 | 18 | `<vsan cluster uuid>` | 947 / 14,339 | 163.6 |
| `cluster-esa-dedup-domowner-io` | new | data | 1 | 82 | 82 / 24 | 58 | `<vsan cluster uuid>` | 1,622 / 28,228 | 140.3 |
| `cluster-esa-dedup-store-chunksvc` | new | data | 1 | 33 | 33 / 27 | 6 | `<vsan cluster uuid>` | 876 / 11,184 | 117.1 |
| `cluster-esa-dedup-store-hashsvc` | new | data | 1 | 39 | 39 / 34 | 5 | `<vsan cluster uuid>` | 953 / 13,154 | 123.6 |
| `cluster-pmem` | new | fault `NotSupported` `pmemisunavailable` | - | - | 0 / 8 | 0 | n/a (fault) | 273 / 426 | 36.8 |
| `cluster-remotedomclient` | new | empty echo | 0 | 0 | 0 / 8 | 0 | n/a (echo) | 131 / 142 | 91.3 |
| `cluster-resync` | new | empty echo | 0 | 0 | 0 / 24 | 0 | n/a (echo) | 123 / 133 | 124.7 |
| `cmmds-workload` | new | fault `InvalidArgument` | - | - | 0 / 23 | 0 | n/a (fault) | 140 / 151 | 40.0 |
| `computeCluster-remotedomclient` | new | empty echo | 0 | 0 | 0 / 8 | 0 | n/a (echo) | 138 / 149 | 92.6 |
| `computeHost-remotedomclient` | new | empty echo | 0 | 0 | 0 / 11 | 0 | n/a (echo) | 135 / 146 | 81.8 |
| `ddh-disk` | new | fault `InvalidArgument` | - | - | 0 / 10 | 0 | n/a (fault) | 140 / 151 | 39.0 |
| `disk-group` | new | empty echo | 0 | 0 | 0 / 38 | 0 | n/a (echo) | 119 / 129 | 109.8 |
| `dom-world-cpu` | new | data | 330 | 990 | 3 / 3 | 0 | `<nodeUuid>|VSAN_0x<hex>_<role>|<world id>` | 23,371 / 400,681 | 159.5 |
| `heap-memory` | new | fault `InvalidArgument` | - | - | 0 / 1 | 0 | n/a (fault) | 140 / 151 | 60.5 |
| `host-cpu` | new | data | 165 | 495 | 3 / 3 | 0 | `<nodeUuid>|cpu-<n>` (160) and `<nodeUuid>` (5) | 11,776 / 197,161 | 158.8 |
| `host-esa-dedup-domcompmgr-io` | new | data | 5 | 210 | 42 / 24 | 18 | `<nodeUuid>` | 4,249 / 71,452 | 154.7 |
| `host-esa-dedup-domowner-io` | new | data | 5 | 410 | 82 / 24 | 58 | `<nodeUuid>` | 7,699 / 140,721 | 127.9 |
| `host-esa-dedup-store-chunksvc` | new | data | 5 | 165 | 33 / 27 | 6 | `<nodeUuid>` | 3,769 / 55,748 | 105.0 |
| `host-esa-dedup-store-hashsvc` | new | data | 5 | 195 | 39 / 34 | 5 | `<nodeUuid>` | 4,340 / 65,563 | 119.0 |
| `host-pmem` | new | fault `NotSupported` `pmemisunavailable` | - | - | 0 / 8 | 0 | n/a (fault) | 273 / 426 | 29.0 |
| `host-remotedomclient` | new | empty echo | 0 | 0 | 0 / 11 | 0 | n/a (echo) | 128 / 139 | 106.3 |
| `host-vsansparse` | new | data | 5 | 105 | 21 / 21 | 0 | `<nodeUuid>` | 2,287 / 34,806 | 133.6 |
| `lsom-world-cpu` | new | empty echo | 0 | 0 | 0 / 2 | 0 | n/a (echo) | 123 / 133 | 116.5 |
| `rdt-net` | new | data | 5 | 5 | 1 / 1 | 0 | `<nodeUuid>` | 410 / 2,781 | 128.5 |
| `remote-virtual-disk` | new | fault `InvalidArgument` | - | - | 0 / 3 | 0 | n/a (fault) | 140 / 151 | 43.9 |
| `remote-virtual-machine` | new | fault `InvalidArgument` | - | - | 0 / 6 | 0 | n/a (fault) | 140 / 151 | 37.3 |
| `remote-vscsi` | new | fault `InvalidArgument` | - | - | 0 / 6 | 0 | n/a (fault) | 140 / 151 | 38.0 |
| `slab-memory` | new | fault `InvalidArgument` | - | - | 0 / 1 | 0 | n/a (fault) | 140 / 151 | 40.6 |
| `system-mem` | new | data | 5 | 15 | 3 / 3 | 0 | `<nodeUuid>` | 564 / 6,016 | 120.5 |
| `vsan-distribution` | new | empty echo | 0 | 0 | 0 / 5 | 0 | n/a (echo) | 124 / 136 | 120.2 |
| `vsan-dp-historical-stats` | new | data | 1 | 1 | 1 / 1 | 0 | `<vsan cluster uuid>` | 304 / 594 | 125.9 |
| `vsan-iscsi-host` | new | empty echo | 0 | 0 | 0 / 10 | 0 | n/a (echo) | 123 / 134 | 118.8 |
| `vsan-iscsi-lun` | new | empty echo | 0 | 0 | 0 / 10 | 0 | n/a (echo) | 122 / 133 | 104.4 |
| `vsan-iscsi-target` | new | empty echo | 0 | 0 | 0 / 10 | 0 | n/a (echo) | 125 / 136 | 132.0 |

**Totals:** 69 calls, 8.233 s wall serial, 218,360 B wire, 3,601,561 B decoded, 958 entities, 10,284 series; per-call p50 120.5 ms (128 ms over the 41 data types); slowest `rdt-network-latency` 368 ms (single outlier, 116 ms in Build 2), `virtual-disk` 273, `vscsi` 251. Shipped 33: 27 data / 6 echo / 0 fault, 423 entities, 7,497 series, 151,996 / 2,555,412 B (matches the JSON "no labels" row of the SOAP vs JSON comparison: 423 / 7,497, 153 KB / 2.56 MB). New 36: 14 data / 11 echo / 11 fault, 535 entities, 2,787 series, 66,364 / 1,046,149 B, 3.52 s summed call time `[observed 2026-11-07]`.

- **Every new-type count in the design's REC column holds over JSON:** 14 return entities, 11 empty echo, 11 fault (9 `InvalidArgument: entityRefId`, 2 `NotSupported` `pmemisunavailable`); `host-cpu` 165 entities (160 `cpu-<n>` + 5 aggregate), `dom-world-cpu` 330 (66 per host: 48 `CompServer`, 6 `Owner`, 6 `OwnerHlpr0`, 6 `Client`; no world name repeats within a host); dedup label counts 42/82/33/39 `[observed 2026-11-07]`.
- **Joins:** the first `|`-segment is the cluster uuid `90d067b8-0077-11f1-af60-000c297e270a` on all 12 cluster-scoped data types, and exactly the 5 node uuids of the R2 read on all 23 host-scoped data types (shipped and new) `[observed 2026-11-07]`.
- **`dom-world-cpu` ref:** `<nodeUuid>|VSAN_0x<12 hex>_<role>|<world id>`, e.g. `dom-world-cpu:6a8859db-a52e-c523-e78c-3805253a02fc|VSAN_0x432abcf22c40_CompServer|2099225`; role one of `CompServer`, `Owner`, `OwnerHlpr0`, `Client` `[observed 2026-11-07]`.
- **`host-cpu` ref:** `host-cpu:<nodeUuid>|cpu-<n>` (32 per host) plus a 1-part `host-cpu:<nodeUuid>` per host `[observed 2026-11-07]`.
- **`None` tokens without the filter:** 2,226 of 20,568 tokens. Concentrated in `virtual-disk` (1,184 of 2,072, the four `NIOPS*` labels as in Build 2), `vsan-vnic-net` (440 / 640), `vsan-pnic-net` (200 / 1,300), `host-domowner` (160 / 2,880), `host-domclient` (100 / 780), `host-domcompmgr` (100 / 820), `vsan-host-net` (40 / 160), `vsan-cluster-capacity` (2 / 12). None on any new type `[observed 2026-11-07]`. Which labels carry them was not broken down beyond `virtual-disk`.
- **`Actual` twins** are model labels, not extras: `vsan-pnic-net` 24, `vsan-tcpip-stats` 10, `vsan-vnic-net` 7 returned (41) `[observed 2026-11-07]`.

### Labels beyond the Python model (210, ESA dedup types only)

Only the 10 ESA dedup types return labels outside the model. The cluster and host variant of each family return the identical extra set `[observed 2026-11-07]`:

- **`cluster-esa-dedup-domclient-io`, `host-esa-dedup-domclient-io`, `cluster-esa-dedup-domcompmgr-io`, `host-esa-dedup-domcompmgr-io` (18 each, same 18 on all four):** `dedupChunkReadCongestion`, `dedupChunkRecoveryUnmapCongestion`, `dedupChunkRecoveryWriteCongestion`, `dedupChunkResyncReadCongestion`, `dedupChunkUnmapCongestion`, `dedupChunkUnmapCount`, `dedupChunkWriteCongestion`, `dedupEngineReadCongestion`, `dedupEngineWriteCongestion`, `dedupHashReadCongestion`, `dedupHashRecoveryUnmapCongestion`, `dedupHashRecoveryWriteCongestion`, `dedupHashResyncReadCongestion`, `dedupHashUnmapCongestion`, `dedupHashUnmapCount`, `dedupHashWriteCongestion`, `iopsDedupChunkObjUnmap`, `iopsDedupHashObjUnmap`.
- **`cluster-esa-dedup-domowner-io`, `host-esa-dedup-domowner-io` (58 each):** the 18 above, plus `dedupChunkReadLeafOwnerCountLocal`, `dedupChunkReadLeafOwnerCountRemote`, `dedupChunkWriteLeafOwnerCountLocal`, `dedupChunkWriteLeafOwnerCountRemote`, `dedupHashReadLeafOwnerCountLocal`, `dedupHashReadLeafOwnerCountRemote`, `dedupHashWriteLeafOwnerCountLocal`, `dedupHashWriteLeafOwnerCountRemote`, `iopsDedupChunkReadLeafOwnerLocal`, `iopsDedupChunkReadLeafOwnerRemote`, `iopsDedupChunkWriteLeafOwnerLocal`, `iopsDedupChunkWriteLeafOwnerRemote`, `iopsDedupHashReadLeafOwnerLocal`, `iopsDedupHashReadLeafOwnerRemote`, `iopsDedupHashWriteLeafOwnerLocal`, `iopsDedupHashWriteLeafOwnerRemote`, `latencyAvgDedupChunkReadLeafOwnerLocal`, `latencyAvgDedupChunkReadLeafOwnerRemote`, `latencyAvgDedupChunkWriteLeafOwnerLocal`, `latencyAvgDedupChunkWriteLeafOwnerRemote`, `latencyAvgDedupHashReadLeafOwnerLocal`, `latencyAvgDedupHashReadLeafOwnerRemote`, `latencyAvgDedupHashWriteLeafOwnerLocal`, `latencyAvgDedupHashWriteLeafOwnerRemote`, `tputDedupChunkReadLeafCompLocal`, `tputDedupChunkReadLeafCompRemote`, `tputDedupChunkReadLeafOwnerLocal`, `tputDedupChunkReadLeafOwnerRemote`, `tputDedupChunkWriteLeafCompLocal`, `tputDedupChunkWriteLeafCompRemote`, `tputDedupChunkWriteLeafOwnerLocal`, `tputDedupChunkWriteLeafOwnerRemote`, `tputDedupHashReadLeafCompLocal`, `tputDedupHashReadLeafCompRemote`, `tputDedupHashReadLeafOwnerLocal`, `tputDedupHashReadLeafOwnerRemote`, `tputDedupHashWriteLeafCompLocal`, `tputDedupHashWriteLeafCompRemote`, `tputDedupHashWriteLeafOwnerLocal`, `tputDedupHashWriteLeafOwnerRemote` (40).
- **`cluster-esa-dedup-store-chunksvc`, `host-esa-dedup-store-chunksvc` (6 each):** `rateAsyncTaskBatches`, `rateChunksOpportunisticDelete`, `rateChunksRetained`, `rateChunksToDelete`, `totalNumBytesRetained`, `totalTputRetained`.
- **`cluster-esa-dedup-store-hashsvc`, `host-esa-dedup-store-hashsvc` (5 each):** `capBytesPerUnitPerHashObj`, `rateDupEntries`, `rateLiveUniqEntries`, `rateStaleUniqEntries`, `rateUniqEntriesPerUnit`.

2 x (18 + 18 + 58 + 6 + 5) = 210, the design's figure (§Uncataloged labels, Q3). Units for these are not in PY `UNITS`; any unit is `[unverified]`.

### Q4: `pctMemUsed` is integer percent (MiB basis)

- `pctMemUsed` is a **`system-mem`** label, not a `vsan-memory` one. `vsan-memory` returns 50 per-daemon labels (`*ConsumedSize`, `*ReservedSize`, `*MemAllocMax`, `*MemAllocMin`), no percent and no host total. `system-mem` returns `overcommitRatio`, `pctMemUsed`, `totalMbMemUsed` `[observed 2026-11-07]`.
- `hardware.memorySize` (PropertyCollector, same session as the inventory read) = 269,896,261,632 B on all 5 hosts = 257,393.13 MiB `[observed 2026-11-07]`.
- On all 10 samples (5 hosts x 2 buckets) `pctMemUsed = floor(100 x totalMbMemUsed / 257,393.13)` exactly, e.g. 132,524 → 51.49 → **51**; 143,904 → 55.91 → **55** (truncates, does not round). A decimal-MB basis gives 49.1 for a reported 51; a per-mille reading would need 515. **Percent, 0 to 100, integer; `totalMbMemUsed` is MiB** `[observed 2026-11-07; arithmetic in the PROVENANCE file]`.
- So the Python pack's `perfsvc.PERMILLE` entry for `pctMemUsed` (divides by 10) would report 5.1 %; the design's verbatim, no-transform key is correct `[observed 2026-11-07 against PY rc.2 source]`. `overcommitRatio` was 0 on every sample.

### Q5: the 9 `InvalidArgument: entityRefId` types

`VsanPerfGetSupportedEntityTypes` over JSON (`{}`, 117 KB wire / 1.21 MB decoded, 40 ms, not saved) returned 70 entries whose `name` values are exactly the 69 model types (one name twice, not identified); **all 9 are advertised** on 9.1.1 `[observed 2026-11-07]`. This differs from test 2's SOAP reading ("66 advertised directly, 3 renames"), which looked at namespaced ids; the JSON `name` field was not compared with those ids `[unverified which field test 2 used]`.

Explicit-ref probes, one spec per call, same window and cluster. Every form below faulted with a body **byte-identical** to the one an invented prefix (`nosuch-type:*` and `nosuch-type:<nodeUuid>`) returns: HTTP 500, `InvalidArgument`, `faultstring` `A specified parameter was not correct: entityRefId`, no `faultMessage`, 140 B wire, 36 to 65 ms. Control `host-domclient:<nodeUuid>` returned data (1 entity, 195 ms) `[observed 2026-11-07]`.

| Type | Wildcard `:*` | `:<nodeUuid>` | `:<cluster uuid>` | Design form | 9.1.1 mgmt (vSAN ESA) | wld01 / wld02 (9.1.1, no vSAN) | 9.0 / 8.x vCenter |
|---|---|---|---|---|---|---|---|
| `clom-host` | fault | fault | fault | `<nodeUuid>` (same) | no working ref | not run | none in lab |
| `cmmds-workload` | fault | fault | fault | `<nodeUuid>` (same) | no working ref | not run | none in lab |
| `heap-memory` | fault | fault | fault | `<nodeUuid>\|<heap>`: heap names unknown, not tried | no working ref found | not run | none in lab |
| `slab-memory` | fault | fault | fault | `<nodeUuid>\|<slab>`: slab names unknown, not tried | no working ref found | not run | none in lab |
| `clom-disk` | fault | fault | fault | `<vsan disk uuid>` `52d171f6-...`: fault | no working ref | not run | none in lab |
| `ddh-disk` | fault | fault | fault | `<vsan disk uuid>`: fault | no working ref | not run | none in lab |
| `remote-virtual-machine` | fault | fault | fault | `<VM instanceUuid>`: fault | no working ref | not run | none in lab |
| `remote-vscsi` | fault | fault | fault | `<VM instanceUuid>\|scsi1:0`: fault | no working ref | not run | none in lab |
| `remote-virtual-disk` | fault | fault | fault | vdisk path: fault | no working ref | not run | none in lab |

**Answer on 9.1.1:** advertised, but the query handler rejects every ref form tried, wildcard and explicit, exactly as it rejects an unknown prefix. On this build they behave as "no working prefix" rather than "explicit refs needed" `[observed 2026-11-07]`. Whether they are version-bound is **unanswered**: `.env` names no 9.0 or 8.x vCenter, and the only other lab vCenters (`vcf-lab-vcenter-wld01`, `-wld02`, also what devel 9.0 and 8.18 Ops monitor) are 9.1.1.0100 build 25784172 with `config.vsanHostConfig.enabled` false on all 4 hosts, so the wildcard set was not run there `[observed 2026-11-07]`. For the pak: one ~40 ms fault per type per cluster per day under fault learning, as designed.

## Object Model Candidates

entityRefId formats `[observed 2026-11-06]`: cluster-scoped `<type>:<vsan cluster uuid>`; host-scoped `<type>:<host node uuid>`; `host-cpu:<node>|cpu-N`; `vsan-pnic-net:<node>|vmnicN`; `vsan-vnic-net:<node>|<stack>|vmkN`; `vnic-rdt-network-latency:<node>|vmkN`; `vsan-tcpip-stats:<node>|<stack>`; `dom-world-cpu:<node>|<world name>|<id>`; `vsan-esa-disk-*:<vsan disk uuid>`; `virtual-machine:<VM config.instanceUuid>`; `vscsi:<vm instanceUuid>|scsiX:Y`; `virtual-disk:<namespace uuid>/<path>`. VM perf uuids matched `config.instanceUuid` for 30 of 30 VMs. The full model is already in `content/sdk-adapters/vsanhostmetrics/app/perfsvc_model.py`.

## Cross-Request Join Keys

- `VsanPerfNodeInformation.vsanNodeUuid` = `HostSystem.config.vsanHostConfig.clusterInfo.nodeUuid` = host-scoped entityRefId suffix → binds host-scoped perf entities to HostSystem.
- `ClusterComputeResource.configurationEx.vsanConfigInfo.defaultConfig.uuid` = cluster-scoped entityRefId suffix.
- `HostSystem.config.vsanHostConfig.clusterInfo.uuid` = the same vSAN cluster uuid (5 of 5 hosts). Unlike the `configurationEx` sub-paths, this one is retrievable by PropertyCollector `[observed 2026-11-06]`.
- `VirtualMachine.config.instanceUuid` = `virtual-machine:` / `vscsi:` uuid `[re-verified 2026-11-06: 30/30 VMs, 148/148 vscsi refs; re-verified again in P2]`.
- `vscsi:` instance `scsiN:M` = `scsi` + the disk's controller `busNumber` + `:` + `VirtualDisk.unitNumber` (controller found by `controllerKey` in the same device array) `[observed 2026-11-06, 148/148, PVSCSI and LSI Logic only]`.
- (`VMEntityObjectID`, `VMEntityVCID`) on Ops VMWARE `ClusterComputeResource` / `VirtualMachine` = (MoRef, vCenter `about.instanceUuid`) `[observed 2026-11-06 on devel: 1 cluster, 45/45 VMs]`. `VMEntityInstanceUUID` = `config.instanceUuid` only where populated (15/45; empty on the 30 powered-on vSAN VMs).
- `QueryVsanManagedDisks(host).storagePools[].storagePoolDisks[].vsanUuid` (or non-empty `QueryDisksForVsan()[].vsanUuid`) = `vsan-esa-disk-*` suffix → binds a disk to the host the call was made against `[observed 2026-11-06, 5/5; re-verified in P2 for both ESA types and the saved capture]`.
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
- Only one vSAN stack (`defaultTcpipStack`) and one vSAN vmknic (`vmk2`) per host here, so multi-stack / multi-vmk instancing of `vsan-tcpip-stats`, `vsan-vnic-net`, `vnic-rdt-network-latency` is unobserved. P2 confirmed the hosts have 8 stacks and 6 to 7 vmknics, but only `vmk2` is vSAN-tagged, and only it is reported.
- P2 gaps: vscsi prefix for SATA, NVMe and IDE virtual disks (none on the lab); `deviceInfo.label` localization and renumbering; why `VMEntityInstanceUUID` and `VMEntityName` are empty on the 30 powered-on mgmt-cluster VMs on devel (not checked on prod, 9.1 or 8.18); whether the perf service ever reports a powered-off VM; Suite API VM list size at 500 per page (109 VMs only here); `QueryDisksForVsan` on OSA (`state` and `vsanUuid` for cache and capacity disks).
- vim25 inventory: no multi-cluster vCenter, so R2 cost at 70 clusters is unmeasured (RetrievePropertiesEx paging with `token` was verified in P2 for VMs). A non-vSAN host inside a vSAN cluster was not available. The `vsan-pnic-net` NIC selection rule (vSAN uplinks vs link-up NICs) could not be separated here. The `configurationEx` sub-path fault was seen over JSON only; SOAP was not re-tested.
