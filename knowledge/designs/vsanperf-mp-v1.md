# Design Artifact: vSAN Performance Management Pack v1 (Tier 2, Java SDK)

**Status.** Build 1 ready for `sdk-adapter-author`. Prerequisite P1 was
resolved the same day: see the Addendum at the end, which supersedes §P1,
the Transport inventory row and call-plan steps 1 to 3. Build 2 described
for orientation; it gets its own design revision before authoring.

**MP display name:** `VCF Content Factory vSAN Performance` (prose prefix,
no brackets).
**adapter_kind:** `vcfcf_vsanperf` (distinct from the Python pack's
`VsanHostMetrics`; see Migration).
**Repo:** `sentania-labs/vcf-content-factory-sdk-vsanperf`, instantiated
from `sentania-labs/vcf-content-factory-sdk-template` 2026-11-06, registered
in `knowledge/context/managed_paks.md` (§vsanperf), cloned to
`content/sdk-adapters/vsanperf/`. The official `.pak` is that repo's CI
build on a `v*` tag. Bundled views and dashboards, when they come (Build 2),
live in that repo under `views/` and `dashboards/`.
**Replaces:** the Python Integration SDK pack `vsanhostmetrics` (fork
`sentania-labs/vsanhostmetrics`, 2.0.0), which keeps shipping until this
pak reaches parity.

**Grounding.** Every API fact here comes from:

| Ref | Source |
|---|---|
| MAP | `knowledge/context/api-maps/vsan-performance-service.md` (SOAP sections and "JSON API transport") |
| PLAN | `knowledge/context/investigations/2026-11-06-vsanhostmetrics-scale-plan.md` |
| PUSH | `knowledge/context/investigations/2026-11-06-suite-api-instanced-push.md` |
| JVM | `knowledge/context/investigations/2026-11-06-collector-jvm-sizing.md` |
| FOOT | `knowledge/context/investigations/2026-11-06-vsanhostmetrics-live-footprint.md` |
| INV | `knowledge/context/investigations/2026-11-06-vsan-adapter-inventory.md` |
| JSON | `reference/docs/extracted/vsan-perfsvc-json/` (README and `PROVENANCE-2026-11-06-evening.md`; `queryperf-cluster-domclient-2026-11-06.json`, `queryperf-fault-wildcardlimit-2026-11-06.json`, and the six evening captures: `queryperf-host-domclient-*`, `queryperf-host-domowner-*`, `queryperf-vsan-pnic-net-*`, `querynodeinformation-*`, `retrievepropertiesex-cluster-hosts-*`, `retrievepropertiesex-fault-invalidproperty-*`) |
| SKILL | `.claude/skills/vcfops-sdk-adapter/SKILL.md`; stitching precedent `content/sdk-adapters/compliance/` (`ComplianceStitcher`) |
| PY | `content/sdk-adapters/vsanhostmetrics/app/` (`metric_scope.py` COVERED, `perfsvc.py` KIND_SUFFIX / PERMILLE / `build_parent_map`, `metric_labels.py`, `perfsvc_model.py`) |

---

## Original Request

Write the Tier 2 design for a native Java SDK management pack that replaces
the Python vsanhostmetrics pack with a scale-safe adapter. The Python pack
creates one Ops object per vSAN entity (460 objects and 6,184 series per
cycle on the lab's 5-host cluster, FOOT §3 and §4) and calls the
Performance Service serially; a prospective customer has 70 vSAN clusters
on one vCenter. The port owns no objects, stitches the vSAN metrics onto
vCenter's own HostSystem, runs clusters through a bounded pool, and is built
to a collector heap budget (PLAN §2, §3, §6).

## Tier decision (recorded, not re-evaluated)

**Tier 2, Java SDK.** Decided 2026-11-06 (PLAN §Decisions). RULE-004
triggers that apply:

- **Dynamic time/computed parameters:** every `VsanPerfQueryPerf` spec needs
  a computed UTC `startTime`/`endTime` window (MAP "Working shapes", "Window
  and interval").
- **Advanced auth / session state:** login returns a token in the
  `vmware-api-session-id` response header that must be sent on every call
  and re-acquired on `NotAuthenticated` (MAP "Working shapes").
- **Per-instance long-lived state and client-side fan-out:** one call per
  (cluster, entity type), a wildcard spec must be alone in its call, the
  cluster argument is mandatory (MAP test 3, test 4); a bounded pool across
  clusters is the only wall-time lever (MAP test 7, PLAN §3).
- **Custom response transforms / joins:** CSV `values` strings aligned to a
  CSV `sampleInfo`, `None` tokens, per-mille conversion, and a vSAN node
  uuid to HostSystem MoRef join (MAP "Response shape", "Cross-Request Join
  Keys"; PY `PERMILLE`).
- **ARIA_OPS stitching of instanced keys** onto existing VMWARE HostSystem
  through the Suite API (PUSH; SKILL "Pushing data").

No MPB design is produced.

## Decisions (2026-11-06, Scott)

| # | Decision | Source |
|---|---|---|
| D1 | Build 1 (MVP): one vSAN cluster, host tier only. Three entity types: `host-domclient`, `host-domowner`, `vsan-pnic-net`. Stitched onto existing VMWARE HostSystem as instanced metrics (compliance-style ARIA_OPS stitching). No new object per vSAN entity. Instance key = entity type + entity id; pNIC instanced by NIC name. | brief; PLAN §Decisions |
| D2 | Build 2: metric parity with the Python pack's default "dashboard" scope (451 keys over 33 kinds, INV §3) on the optimised model: cluster, disk and VM tiers as scope levers; one object per cluster at most; hosts stitched; lower tiers instanced or off. | brief; PLAN §2, §4 |
| D3 | Transport: vSphere JSON API, `POST /sdk/vim25/{release}/vsan/VsanPerformanceManager/vsan-performance-manager/VsanPerfQueryPerf`; one wildcard spec per call; cluster argument always; 7-minute window; last sample; `labels` filter; gzip; one reused session per adapter instance. No vSAN or vim25 SDK jars. | brief; MAP "Recommendation for the Java port" |
| D4 | Collector: vSAN cluster inventory read once per cycle and cached for the cycle; per cluster process and discard; bounded pool; per-call timeouts plus a cycle deadline; cluster include/exclude filter parameter for sharding across adapter instances. | brief; PLAN §3 items 1 to 8 |
| D5 | Advanced setting: performance-timing debug logging, on/off, off by default (per-call and per-cluster timings, call counts, bytes, cycle total). | brief; PLAN §Decisions |
| D6 | Heap budget ~65 MB per adapter instance on the collector. | JVM §Budget |
| D7 | Distinct adapter kind from the Python pack; migration is uninstall old, install new, recreate instances and credentials. | `knowledge/lessons/cross-runtime-pak-upgrade-split-brain.md` |
| D8 | Prove on 8.18, 9.0, 9.1. | RULE-019 |
| D9 | Throughput ceiling (per vCenter vs per cluster) is unmeasured. Do not design around a guess; the timing log must let the answer be read from logs. | brief; MAP test 7 |

## Interview Answers

The interview is answered by D1 to D9. The API is not in
`knowledge/context/api_pattern_catalog.md`; the orchestrator should add a
"vSAN Performance Service (JSON)" entry from this design and MAP (signature:
`/sdk/vim25/<rel>/vsan/...` POST with `_typeName` bodies; auth: vim25
`SessionManager.Login` header token; default model: stitch onto VMWARE,
own nothing; known limits: one wildcard per call, cluster mandatory,
~7 calls/s sustained against one cluster).

| Question | Answer |
|---|---|
| Monitoring scope | Build 1: DOM client, DOM owner, pNIC on hosts, Python pack's COVERED metric set for those kinds (61 keys). Build 2: the 451-key default scope. |
| Object granularity | No first-class vSAN objects. Host-scoped entities become key groups on HostSystem; pNIC is an instanced group. |
| Cross-adapter stitching | Yes: VMWARE HostSystem (Build 1); ClusterComputeResource, VirtualMachine, built-in vSAN disk (Build 2). |
| Collection interval | 5 minutes (matches the Performance Service's native 300 s, MAP test 6). |

---

## Object Model

```
VCF Content Factory vSAN Performance (adapter kind vcfcf_vsanperf)
 └── vSAN Performance Adapter Instance      (own kind, one per account; the ONLY object the pak creates)

Stitched (ARIA_OPS, no describe.xml entry, keys pushed through the Suite API):
VMWARE HostSystem (existing, owned by the vCenter adapter)
 ├── vSAN Perf|DOM Client|<metric>          6 keys, one set per host
 ├── vSAN Perf|DOM Owner|<metric>           38 keys, one set per host
 └── vSAN Perf|pNIC:<vmnic>|<metric>        17 keys per vSAN pNIC instance
```

New objects per cluster: **0**. Lab comparison: the Python pack holds 460
objects for this cluster, 28 kinds (FOOT §3); the vCenter adapter holds 88
to 91 for the whole vCenter (FOOT §5).

### Relationships

1. None created. Stitched keys ride on HostSystem, which already sits in
   vCenter's tree. No `addChild`, no `RelationshipBuilder` edges in Build 1.
2. The adapter instance kind has no children. (A pak singleton plus
   ComputedMetrics for fleet totals, SKILL "Environment-wide totals", is a
   Build 2 option, not Build 1.)

## Object Type Details

### vSAN Performance Adapter Instance (`vcfcf_vsanperf`, type 7)
- Identifier: `vcenter_host` (required) plus `cluster_include` (see Settings,
  part of uniqueness so two shard instances on one vCenter are distinct
  accounts; Open question Q3).
- Name expression: the account name the admin types.
- Source: none (the instance itself).
- Icon hint: `adapter_instance` (from `knowledge/context/mpb/mp_icon_library.md`).
- Self-metrics (own kind, delivered in the collect result, so the platform
  attributes them to this instance; stitched series are not counted by the
  platform's own `collected_metrics`, PUSH §"statkeys and attribution"):

| Key | Label | Type | Meaning |
|---|---|---|---|
| `Collection\|clusters_in_scope` | Clusters in scope | METRIC | vSAN-enabled clusters after include/exclude |
| `Collection\|clusters_ok` | Clusters collected | METRIC | clusters whose three calls all returned |
| `Collection\|clusters_failed` | Clusters failed | METRIC | any call faulted or errored |
| `Collection\|clusters_timed_out` | Clusters timed out | METRIC | per-call timeout or cycle deadline |
| `Collection\|perf_calls` | Performance Service calls | METRIC | QueryPerf calls issued this cycle |
| `Collection\|series_pushed` | Series pushed | METRIC | stat values handed to `pushStatsBatch` |
| `Collection\|hosts_unresolved` | Hosts unresolved | METRIC | node uuids with no HostSystem resource id |
| `Collection\|push_batches_failed` | Push batches failed | METRIC | from `SuiteApiBatchResult` |
| `Collection\|cycle_seconds` | Cycle time (s) | METRIC | wall time of collect |
| `Collection\|perf_calls_per_second` | Performance Service call rate | METRIC | perf_calls / elapsed wall-clock seconds of the perf phase (first call start to last call end across all workers); this is aggregate throughput, the D9 ceiling signal |
| `Collection\|perf_call_ms_avg` | Performance Service call latency (ms) | METRIC | summed per-call wall ms / perf_calls; latency diagnostic, not throughput |
| `Collection\|last_error` | Last error | PROPERTY | short, credential-free text |

### Stitch target: VMWARE HostSystem (not declared in describe.xml)
- Foreign identity: `VMEntityObjectID` (host MoRef) **plus** `VMEntityVCID`
  (vCenter `about.instanceUuid`). Never MOID alone
  (`knowledge/lessons/stitch-moid-not-unique-across-vcenters.md`; SKILL "MOID
  trap"; PY `build_parent_map` docstring: verified 2026-09-23 that
  instanceUuid equals VMEntityVCID).
- Entity to host join: host-scoped `entityRefId` suffix = vSAN node uuid =
  `HostSystem.config.vsanHostConfig.clusterInfo.nodeUuid` (MAP "Cross-Request
  Join Keys"; observed for all 5 lab hosts, INV §4). **No hostname fallback.**
  The Python pack's hostname alias fallback (PY `build_parent_map`) is the
  route that orphaned or mis-joined hosts in 1.4.x; here an unresolved node
  uuid is counted (`hosts_unresolved`) and logged once per refresh, and its
  data is dropped. Wrong host is data corruption; missing is visible.
- Icon hint: n/a (foreign kind renders with VMWARE icons).

#### Instance key (D1) and stat key scheme

Internal identity of one stitched series set = `(entityType, entityId)`,
where `entityId` is everything after the first `:` of `entityRefId`
(MAP "Object Model Candidates"):

| Entity type | entityRefId form | entityId parts | Lands on | Ops key prefix |
|---|---|---|---|---|
| `host-domclient` | `host-domclient:<node uuid>` | node | host(node) | `vSAN Perf\|DOM Client\|` |
| `host-domowner` | `host-domowner:<node uuid>` | node | host(node) | `vSAN Perf\|DOM Owner\|` |
| `vsan-pnic-net` | `vsan-pnic-net:<node uuid>\|vmnicN` | node, nic | host(node) | `vSAN Perf\|pNIC:<nic>\|` |

- Group names come from PY `KIND_SUFFIX` ("DOM Client", "DOM Owner", "pNIC").
- The host-scoped types carry no instance segment: one entity per host, so
  an instance would only repeat the host. pNIC instance segment is the NIC
  name verbatim (`vmnic0`).
- Both key placements were accepted and read back on 9.0.2, including spaces
  in segments and a nested instance `Group|sub:inst|metric` (PUSH
  §Findings). One instanced key is stored per instance.
- A `vsan-pnic-net` ref whose id does not split into exactly two parts on
  `|`, or any ref containing `*` (the empty-type echo, MAP "Same rules"), is
  skipped and counted, never pushed under a guessed instance.
- Pushed keys get **no label and no unit** in the UI: HostSystem metadata
  comes from VMWARE's describe, and a pak's describe cannot declare keys for
  VMWARE (PUSH §Verdict). Hence units go in the leaf name (next section).
  Whether the Metrics tab renders `pNIC:vmnic0` as an instance node is
  unverified (PUSH §Visual); Build 1's three-platform proof answers it.

#### Leaf naming rule (recommended; Q1)

Leaf = the vSAN label verbatim, then:
- per-mille labels in PY `PERMILLE` are divided by 10 and get `Pct`
  (PY `perfsvc.py` comment: the service reports these per mille; Broadcom
  thresholds are in percent);
- microsecond labels get `Us`, byte-rate labels get `BytesPerSec`, unless
  the label already ends in `Us`, `Sec` or `Bps`;
- everything else unchanged.

Units come from PY `metric_labels.py` UNITS, which were harvested from
HCIBench dashboards, not from the API (the API returns only `label` and
`metricsCollectInterval`, MAP "Response shape"). The microsecond and byte
rate readings are consistent with the recorded sample magnitudes
(`latencyAvgRead` 3232 / 1143, `throughputRead` 46,022,819 / 18,507,009 in
JSON `queryperf-cluster-domclient`), not proven. Key names are permanent
once data exists (no per-key delete, PUSH "What remains"), so they are fixed
before the first `v*` tag.

---

## Build 1 metric list (61 keys)

Labels are the Python pack's (PY `metric_labels.py` LABELS); they become
documentation (`REFERENCE.md`) and view column headers later, since pushed
keys carry no label. The metric set is PY `metric_scope.COVERED` for the
kind; every label is also in PY `perfsvc_model.ENTITIES[type].metrics`
(checked). Send exactly the "vSAN label" column as the spec's `labels`
array (MAP test 5: the response is restricted to the requested labels).

### `host-domclient` (Python kind VsanHostDomclient), 6 keys per host

|vSAN label|Ops stat key|Label (Python pack)|Unit|Transform|
|---|---|---|---|---|
| `congestion` | `vSAN Perf\|DOM Client\|congestion` | Congestions | none stated | none |
| `iopsRead` | `vSAN Perf\|DOM Client\|iopsRead` | Read IOPS | IO/s | none |
| `iopsWrite` | `vSAN Perf\|DOM Client\|iopsWrite` | Write IOPS | IO/s | none |
| `latencyAvgRead` | `vSAN Perf\|DOM Client\|latencyAvgReadUs` | Read Latency | microseconds | none |
| `latencyAvgWrite` | `vSAN Perf\|DOM Client\|latencyAvgWriteUs` | Write Latency | microseconds | none |
| `oio` | `vSAN Perf\|DOM Client\|oio` | Outstanding IO | none stated | none |

### `host-domowner` (Python kind VsanHostDomowner), 38 keys per host

The API returns 288 labels for this type unfiltered (MAP test 2); the
`labels` filter is what keeps this type cheap.

|vSAN label|Ops stat key|Label (Python pack)|Unit|Transform|
|---|---|---|---|---|
| `highOIODurationPercentWrite` | `vSAN Perf\|DOM Owner\|highOIODurationPercentWrite` | High outstanding IO duration percent (write) | none stated | none |
| `iops` | `vSAN Perf\|DOM Owner\|iops` | IOPS | IO/s | none |
| `iopsSegCleanerUnmap` | `vSAN Perf\|DOM Owner\|iopsSegCleanerUnmap` | IOPS seg cleaner unmap | IO/s | none |
| `iopsUnmap` | `vSAN Perf\|DOM Owner\|iopsUnmap` | Unmap IOPS | IO/s | none |
| `latencyAvgRead` | `vSAN Perf\|DOM Owner\|latencyAvgReadUs` | Read Latency | microseconds | none |
| `latencyAvgSegCleanerUnmap` | `vSAN Perf\|DOM Owner\|latencyAvgSegCleanerUnmapUs` | Latency avg seg cleaner unmap | microseconds | none |
| `latencyAvgUnmap` | `vSAN Perf\|DOM Owner\|latencyAvgUnmapUs` | Unmap Latency | microseconds | none |
| `latencyAvgWrite` | `vSAN Perf\|DOM Owner\|latencyAvgWriteUs` | Write Latency | microseconds | none |
| `latencyMaxRead` | `vSAN Perf\|DOM Owner\|latencyMaxReadUs` | Latency (max, read) | microseconds | none |
| `latencyMaxSegCleanerUnmap` | `vSAN Perf\|DOM Owner\|latencyMaxSegCleanerUnmapUs` | Latency max seg cleaner unmap | microseconds | none |
| `latencyMaxUnmap` | `vSAN Perf\|DOM Owner\|latencyMaxUnmapUs` | Latency max unmap | microseconds | none |
| `latencyMaxWrite` | `vSAN Perf\|DOM Owner\|latencyMaxWriteUs` | Latency (max, write) | microseconds | none |
| `latencyStddevSegCleanerUnmap` | `vSAN Perf\|DOM Owner\|latencyStddevSegCleanerUnmapUs` | Latency standard deviation seg cleaner unmap | microseconds | none |
| `latencyStddevWrite` | `vSAN Perf\|DOM Owner\|latencyStddevWriteUs` | Latency standard deviation (write) | microseconds | none |
| `numNetSchedControllerIopsLimit` | `vSAN Perf\|DOM Owner\|numNetSchedControllerIopsLimit` | Num net sched controller IOPS limit | IO/s | none |
| `numNetSchedGuestLTLatUs` | `vSAN Perf\|DOM Owner\|numNetSchedGuestLTLatUs` | Num net sched guest lt latency us | microseconds | none |
| `numNetSchedLowBand` | `vSAN Perf\|DOM Owner\|numNetSchedLowBand` | Num net sched low band | none stated | none |
| `numNetSchedLowBandSec` | `vSAN Perf\|DOM Owner\|numNetSchedLowBandSec` | Num net sched low band sec | seconds | none |
| `numNetSchedLowBandThreshUs` | `vSAN Perf\|DOM Owner\|numNetSchedLowBandThreshUs` | Num net sched low band thresh us | microseconds | none |
| `numNetSchedLowToMidBand` | `vSAN Perf\|DOM Owner\|numNetSchedLowToMidBand` | Num net sched low to mid band | none stated | none |
| `numNetSchedMidBand` | `vSAN Perf\|DOM Owner\|numNetSchedMidBand` | Num net sched mid band | none stated | none |
| `numNetSchedMidBandSec` | `vSAN Perf\|DOM Owner\|numNetSchedMidBandSec` | Num net sched mid band sec | seconds | none |
| `numNetSchedMidToLowBand` | `vSAN Perf\|DOM Owner\|numNetSchedMidToLowBand` | Num net sched mid to low band | none stated | none |
| `numNetSchedRollingAvgLatUs` | `vSAN Perf\|DOM Owner\|numNetSchedRollingAvgLatUs` | Num net sched rolling avg latency us | microseconds | none |
| `numNetSchedSeenNonResyncTpBps` | `vSAN Perf\|DOM Owner\|numNetSchedSeenNonResyncTpBps` | Num net sched seen non resync tp bps | bytes/s | none |
| `numNetSchedSeenTotalTpBps` | `vSAN Perf\|DOM Owner\|numNetSchedSeenTotalTpBps` | Num net sched seen total tp bps | bytes/s | none |
| `oio` | `vSAN Perf\|DOM Owner\|oio` | Outstanding IO | none stated | none |
| `owner2PCCommitLatencyAvgUs` | `vSAN Perf\|DOM Owner\|owner2PCCommitLatencyAvgUs` | Owner2 pc commit latency avg us | microseconds | none |
| `readLeafOwnerLatencyLocal` | `vSAN Perf\|DOM Owner\|readLeafOwnerLatencyLocalUs` | Read leaf owner latency local | microseconds | none |
| `readLeafOwnerLatencyRemote` | `vSAN Perf\|DOM Owner\|readLeafOwnerLatencyRemoteUs` | Read leaf owner latency remote | microseconds | none |
| `recoveryWriteCongestion` | `vSAN Perf\|DOM Owner\|recoveryWriteCongestion` | Resync Read Congestions (sic, Python pack label) | none stated | none |
| `segCleanerUnmapCongestion` | `vSAN Perf\|DOM Owner\|segCleanerUnmapCongestion` | Seg cleaner unmap congestion | none stated | none |
| `segCleanerUnmapLeafOwnerMaxLatencyAvgUs` | `vSAN Perf\|DOM Owner\|segCleanerUnmapLeafOwnerMaxLatencyAvgUs` | Seg cleaner unmap leaf owner max latency avg us | microseconds | none |
| `serverSwitchCount` | `vSAN Perf\|DOM Owner\|serverSwitchCount` | Server switch count | none stated | none |
| `throughputSegCleanerUnmap` | `vSAN Perf\|DOM Owner\|throughputSegCleanerUnmapBytesPerSec` | Throughput seg cleaner unmap | bytes/s | none |
| `unmapCount` | `vSAN Perf\|DOM Owner\|unmapCount` | Unmap count | none stated | none |
| `writeLeafOwnerLatencyLocal` | `vSAN Perf\|DOM Owner\|writeLeafOwnerLatencyLocalUs` | Write leaf owner latency local | microseconds | none |
| `writeLeafOwnerLatencyRemote` | `vSAN Perf\|DOM Owner\|writeLeafOwnerLatencyRemoteUs` | Write leaf owner latency remote | microseconds | none |

### `vsan-pnic-net` (Python kind VsanPnic), 17 keys per vSAN pNIC

|vSAN label|Ops stat key|Label (Python pack)|Unit|Transform|
|---|---|---|---|---|
| `ioChainDrops` | `vSAN Perf\|pNIC:<vmnic>\|ioChainDrops` | IO chain drops | none stated | none |
| `ioChainRxdrops` | `vSAN Perf\|pNIC:<vmnic>\|ioChainRxdrops` | IO chain RX drops | none stated | none |
| `ioChainTxdrops` | `vSAN Perf\|pNIC:<vmnic>\|ioChainTxdrops` | IO chain TX drops | none stated | none |
| `pauseCount` | `vSAN Perf\|pNIC:<vmnic>\|pauseCountPct` | pNic 802.3x Pause Rate | percent | per-mille / 10 |
| `pfcCountRaw` | `vSAN Perf\|pNIC:<vmnic>\|pfcCountRaw` | PFC count raw | none stated | none |
| `portRxDrops` | `vSAN Perf\|pNIC:<vmnic>\|portRxDropsPct` | Inbound Packet Drop Rate of vSwitch Port | percent | per-mille / 10 |
| `portTxDrops` | `vSAN Perf\|pNIC:<vmnic>\|portTxDropsPct` | Outbound Packet Drop Rate of vSwitch Port | percent | per-mille / 10 |
| `portTxpkts` | `vSAN Perf\|pNIC:<vmnic>\|portTxpkts` | Port TX packets | none stated | none |
| `rxCrcErr` | `vSAN Perf\|pNIC:<vmnic>\|rxCrcErrPct` | pNIC RX CRC Error | percent | per-mille / 10 |
| `rxCrcErrRaw` | `vSAN Perf\|pNIC:<vmnic>\|rxCrcErrRaw` | RX CRC errors raw | none stated | none |
| `rxErr` | `vSAN Perf\|pNIC:<vmnic>\|rxErrPct` | pNIC RX Generic Error | percent | per-mille / 10 |
| `rxFifoErr` | `vSAN Perf\|pNIC:<vmnic>\|rxFifoErrPct` | pNIC RX FIFO Error | percent | per-mille / 10 |
| `rxMissErr` | `vSAN Perf\|pNIC:<vmnic>\|rxMissErrPct` | pNIC RX missed error (ring buffer full) | percent | per-mille / 10 |
| `rxMissErrRaw` | `vSAN Perf\|pNIC:<vmnic>\|rxMissErrRaw` | pNIC RX missed error (ring buffer full) (raw) | none stated | none |
| `rxOvErr` | `vSAN Perf\|pNIC:<vmnic>\|rxOvErrPct` | pNIC RX Buffer Overflow Error | percent | per-mille / 10 |
| `txCarErr` | `vSAN Perf\|pNIC:<vmnic>\|txCarErrPct` | pNIC TX Carrier Error | percent | per-mille / 10 |
| `txErr` | `vSAN Perf\|pNIC:<vmnic>\|txErrPct` | pNIC TX Generic Error | percent | per-mille / 10 |

**Totals.** 61 key definitions (6 + 38 + 17). On the lab cluster (5 hosts,
10 vSAN pNICs, FOOT §6) that is up to 5 x 6 + 5 x 38 + 10 x 17 = **390
series per cycle**, against 6,184 for the Python pack (FOOT §4). "Up to":
a label absent from a response is simply not pushed.

### Value selection (all three types)

- Parse `sampleInfo` (UTC, `yyyy-MM-dd HH:mm:ss`, no zone) and each series'
  `values` CSV, index-aligned (MAP "Response shape").
- Take the **newest non-`None` token** and its own timestamp. `None` is a
  literal token (2,218 seen in one cycle); parse with a check, not
  `Double.parseDouble` alone. This matches PY `_last_number` but keeps the
  timestamp, which PY drops.
- Push with the **sample's** timestamp (epoch ms), not "now". Back-dated
  points, including ones older than the newest stored point, are accepted
  (PUSH §Findings "Timestamps").
- Remember the last pushed sample timestamp **per `entityRefId`** for the
  life of the instance (each entity carries its own `sampleInfo` and hosts
  can lag each other by a bucket; a per-type key would drop a lagging host's
  bucket for good); skip an entity's series whose newest timestamp is not
  newer than that. T1 covers the lagging-host case. A 7-minute window often holds two 5-minute buckets
  (MAP test 6) and the cycle is not aligned to them, so without this the
  same bucket is pushed twice.
- Skip a label ending `Actual` (PY: identical to its base). With the labels
  filter on it does not arrive anyway.
- Values are stored as float32 (PUSH "Precision"); no rounding needed.

---

## Transport (D3)

All calls are HTTPS to the vCenter named in `vcenter_host`, using a
framework `HttpClientBuilder` client with `platformSsl(this, vcenter_host)`
(certificate name checking opt-in, SKILL "Target-system TLS"). Headers on
every call: `Content-Type: application/json`, `Accept-Encoding: gzip`,
`vmware-api-session-id: <token>` (after login).

| Call | Method and path | Body | Source |
|---|---|---|---|
| Release id | `GET /sdk/vimServiceVersions.xml` | none | MAP "Working shapes" |
| Login | `POST /sdk/vim25/{rel}/SessionManager/SessionManager/Login` | `{"userName":..,"password":..}`; token in response header `vmware-api-session-id` | MAP |
| About / instanceUuid | `GET /sdk/vim25/{rel}/ServiceInstance/ServiceInstance/content` | none; read `about.instanceUuid`, `about.apiVersion`, `about.fullName` | MAP (about observed); instanceUuid per PY `build_parent_map` |
| Inventory (clusters, hosts, node uuids) | vim25 JSON `ViewManager` / `PropertyCollector` | `CreateContainerView` (ClusterComputeResource, recursive), `RetrievePropertiesEx` with a traversal to `host`, `ContinueRetrievePropertiesEx` while a `token` is returned; shapes in MAP "vim25 inventory over JSON" and the `retrievepropertiesex-*` samples | measured 2026-11-06 (Addendum) |
| Perf query | `POST /sdk/vim25/{rel}/vsan/VsanPerformanceManager/vsan-performance-manager/VsanPerfQueryPerf` | `{"querySpecs":[{"_typeName":"VsanPerfQuerySpec","entityRefId":"<type>:*","startTime":"<UTC ISO, Z>","endTime":"<UTC ISO, Z>","labels":[...]}],"cluster":{"_typeName":"ManagedObjectReference","type":"ClusterComputeResource","value":"<moid>"}}` | MAP "Working shapes"; JSON README |
| Logout | `POST .../SessionManager/SessionManager/Logout` on `onDiscard` | none | MAP (logout 0.004 s) |

Rules the client enforces (MAP "Recommendation for the Java port"):
`_typeName` on every spec; dates always UTC with `Z` (a non-zero offset is
silently dropped by the server); exactly one wildcard spec per call;
cluster always present (omitted cluster faults `SystemError`); no
`interval` field (ignored for regular queries); send `labels`.

**Release id (recommended, Q5).** Pin `8.0.3.0`, the oldest id the 9.1.1
server accepted (MAP; `8.0.0.0` and `7.0.3.0` fault `InvalidRequest:
Unknown release ID.`). On that fault, read `/sdk/vimServiceVersions.xml`,
use the server's vim25 version, log it once. The JSON API is inferred to
start at vCenter 8.0 U1 (MAP, unverified); an older vCenter fails Test
Connection with a message that says so.

**Response handling.** Read the body gzip-decoded through a size cap
(template `BoundedBody` pattern). Two deviations from the template, both
required by this API:
1. vSAN faults arrive as **HTTP 500 with a JSON body** carrying
   `_typeName`, `faultstring` and, for validation faults, `faultMessage[]`
   of `{key, message}` (JSON fault sample; MAP "Errors on the way"). The
   template does not read non-200 bodies; this client must read a 500 body
   up to a small cap (64 KB recommended) to dispatch on `faultMessage[].key`.
2. Do not let the framework retry policy re-send a call that got a vSAN
   fault body: those faults are deterministic. Retry only transport errors,
   once, inside the cycle deadline.

Parsing: framework `SimpleJson` on the capped body is acceptable for Build
1 (labels on, three types). If the replay harness heap test (Test plan T4)
exceeds the D6 budget at 70 clusters, switch the perf response to a
streaming parse (MAP: "stream-parse the array if memory matters"). See Risk
R5.

**Session.** One token per adapter instance, created on first use and
reused across cycles. On `NotAuthenticated` (any call): log in again once
and retry that call once; a second `NotAuthenticated` fails the cycle with
a credential-free message. Login costs ~0.25 s (MAP comparison table);
session idle timeout is not measured (MAP), so no proactive refresh.

### Prerequisite P1 (blocks inventory code only)

**Superseded 2026-11-06 by the Addendum:** the round ran; the cluster-side
`configurationEx.vsanConfigInfo.*` paths named below fault `InvalidProperty`
over JSON and must not be requested. Kept for the record.

MAP measured the vSAN calls, Login and `ServiceInstance/content` over JSON,
but **not** the vim25 inventory reads this adapter needs:

- list `ClusterComputeResource` with `name`, vSAN enabled
  (`configurationEx.vsanConfigInfo.enabled`, PY `vsan_enabled`), vSAN cluster
  uuid (`configurationEx.vsanConfigInfo.defaultConfig.uuid`, MAP join keys)
  and `host`;
- for those hosts, `name` and `config.vsanHostConfig.clusterInfo.nodeUuid`
  (MAP join keys; PY reads the same value via
  `configManager.vsanSystem.config.clusterInfo.nodeUuid`).

Before inventory code is written, the orchestrator should brief
`api-cartographer` to add to MAP: the JSON shape of `CreateContainerView`
and `RetrievePropertiesEx` (or the per-object property GET the 405/InvalidType
error hints at), for those exact paths, on the lab vCenter, plus verbatim
JSON-transport `VsanPerfQueryPerf` responses for `host-domclient`,
`host-domowner`, `vsan-pnic-net` with the Build 1 `labels` set, and one
`VsanPerfQueryNodeInformation`, saved under `reference/docs/extracted/vsan-perfsvc-json/`
(RULE-016). The two existing samples cover only `cluster-domclient` and a
fault. Fallback if the JSON vim25 surface misbehaves: the compliance
adapter's JAX-WS `VSphereClient` for inventory only (vim25 jar bundled),
keeping the vSAN calls on JSON.

---

## Collector shape (D4)

### Per-cycle call plan

| Step | Calls | When | Notes |
|---|---|---|---|
| 0. Release id + login + about | 0 to 3 | first cycle, after a reconfigure, or after re-login | reused across cycles |
| 1+2. Cluster and host inventory (merged, Addendum) | 1 `RetrievePropertiesEx` over a session-lived container view (plus `ContinueRetrievePropertiesEx` pages; view recreated after re-login) | every cycle | clusters with `name`, `host`; hosts with `name`, vSAN `enabled`, `clusterInfo.uuid`, `nodeUuid`; cluster vSAN flag and uuid derived from members (rule in the Addendum); apply include/exclude; node uuid to host MoRef |
| 3. Ops resource map | Suite API `GET /api/resources` for VMWARE HostSystem, filtered to this vCenter by VMEntityVCID | every 12th cycle, on a change in the in-scope host set, or when a (MoRef, VCID) misses | compliance `ComplianceStitcher` pattern; resolves (MoRef, VCID) to Ops resource id; also where stale ids are detected (SKILL: a 2xx batch drops unknown ids silently) |
| 4. Perf queries | **3 per cluster** (one per entity type) | every cycle | the API floor: one wildcard per call, cluster mandatory (MAP test 3, 4) |
| 5. Stats push | `ceil(hosts / 100)` batch requests (and by ~1 MB) | every cycle | `SuiteApiStitcher.pushStatsBatch`; properties: none |

**Build 1 on the lab (1 cluster, 5 hosts):** steady state 1 + 3 + 1 = 5
HTTP calls per cycle; 7 on refresh cycles. Perf calls: 3 x ~0.12 to 0.25 s
p50 serial (MAP comparison table and test 7).

**70 clusters at Build 1 scope (projection, not a target):** 210 perf calls
per cycle. At the measured serial median 0.19 s, ~40 s; at the ~7 calls/s
sustained ceiling, ~30 s (MAP test 7). Either fits a 5-minute cycle, so
Build 1 scope does not need the ceiling answered. Build 2's full scope does
(PLAN §3: 2,310 calls, ~5.5 min at 7 calls/s if the ceiling is per vCenter).

### Threads and flow

```
collect()
  ├─ inventory (caller thread) ──> ordered cluster list
  ├─ submit one task per cluster to a bounded pool (N workers, setting)
  │     task(cluster):  for type in [host-domowner, host-domclient, vsan-pnic-net]:
  │                         call QueryPerf (per-call timeout)
  │                         parse -> compact rows (hostResourceId, key, ts, value)
  │                         discard response body
  │                     hand ClusterResult to a bounded queue
  └─ caller thread drains the queue: accumulate rows; when >=100 hosts or ~1 MB,
        pushStatsBatch; at end push the remainder; stop at the cycle deadline
```

- **Parallelism is across clusters only.** A cluster's three calls run
  serially inside its task (PLAN §3.1; MAP: no gain from parallel calls on
  one cluster beyond ~7 calls/s).
- **Order within a cluster:** `host-domowner` first (the most valuable
  group; the DOM owner family was the slowest serially, `cluster-domowner`
  0.45 s, MAP test 7), then DOM client, then pNIC, so a deadline cut loses
  the least useful group first.
- **Only the caller thread touches the stitcher.** `SuiteApiStitcher`
  thread safety is not documented in SKILL; one pushing thread avoids the
  question and keeps batches full.
- **Process and discard.** A worker never holds more than one response body;
  a `ClusterResult` is compact rows; the caller releases rows once pushed.
- **Fairness.** Rotate the cluster start order each cycle (start after the
  last cluster completed in the previous cycle) so a deadline cut never
  starves the same clusters (compliance has the same idea in `ResumeCursor`).
- **Learned types.** Per (cluster, type): on `NotSupported` or
  `InvalidArgument` with `faultstring` ending `entityRefId`, mark the type
  unavailable on that cluster for 24 h, then re-probe (PLAN §3.2; a faulting
  type costs 0.04 to 0.07 s, MAP). An empty echo (`<type>:*`, no `value`) is
  recorded as "empty this cycle", not learned. The three Build 1 types are
  expected on every vSAN cluster, so this is mostly Build 2 machinery; build
  it now because the per-cluster state map is the same.

### Timeouts and deadline

| Budget | Default | Basis |
|---|---|---|
| Connect timeout | 5 s | SKILL "HTTP client timeouts" (a few seconds) |
| Per-call request timeout | 30 s | slowest observed wildcard call 3.54 s at 16 workers (MAP test 7); 30 s is the framework default |
| Cycle deadline | interval minus 60 s (240 s at 5 min) | below the interval (PLAN §6) |

At the deadline: stop submitting, cancel queued tasks, interrupt running
ones, push every completed cluster, count the rest `clusters_timed_out`,
and return normally.

---

## Settings (describe.xml, adapter instance kind)

| Key | Label | Type / default | identType | Notes |
|---|---|---|---|---|
| `vcenter_host` | vCenter Server | string, required | 1 | host or host:port as the certificate names it |
| `cluster_include` | Clusters to include | string, default empty = all | **1** (Q3) | comma list; each item a cluster name or MoRef (`domain-c6004`); exact match, case-insensitive on names |
| `cluster_exclude` | Clusters to exclude | string, default empty | 2 | applied after include |
| `max_parallel_clusters` | Parallel clusters | int, default 4, range 1 to 16 | 2 | 4 to 16 workers all hit the same ~7 calls/s on one cluster (MAP test 7); 4 is the knee |
| `call_timeout_seconds` | Call timeout (s) | int, default 30 | 2 | per HTTP call |
| `cycle_deadline_seconds` | Cycle deadline (s) | int, default 0 = interval minus 60 s | 2 | |
| `perf_timing_logging` | Performance timing logging | enum `false`/`true`, default `false` | 2 | D5 |

Credential kind `vcenter_credentials` (username, password), as compliance.
The Suite API side uses the injected per-instance credential through
`AmbientCredential` (works on Cloud Proxies;
`knowledge/lessons/cross-mp-stitch-cp-identity-and-edge-mechanics.md`); no
Ops credential field on the account.

`identType="2"` with a default puts a field under Advanced Settings
(`knowledge/context/python_integration_sdk.md` §2.3). Changing a field's
identType after release changes account identity, so these are fixed for
Build 1.

**Build 2 additions (not in Build 1):** `tiers` (cluster, host, disk, vm;
default host), `exclude_groups` (type or group list on top of the tier),
`vm_tier_every_n_cycles` (PLAN §4).

## Logging (D5)

Always (INFO, one line each): configure summary (vCenter, release id in
use, include/exclude, workers, deadline; never the principal or token);
once per cycle a summary line: clusters ok/failed/timed out, perf calls,
series pushed, hosts unresolved, push batches ok/failed, cycle seconds.
WARN: per failed cluster (one line, fault class plus `faultMessage` key),
push failures (from `SuiteApiBatchResult`), unresolved node uuids (once per
identity refresh, not per cycle).

When `perf_timing_logging=true`, additionally at **INFO** (DEBUG may not
reach the per-instance log, `knowledge/context/tier2_architecture.md`
"Logging" #228), with a fixed `PERF` prefix and `key=value` fields so the
lines can be grepped and tabulated:

| Line | Fields |
|---|---|
| `PERF call` | cycle id, cluster moid, entity type, worker id, queue wait ms, wall ms, HTTP status, wire bytes, decoded bytes, entities, series kept, fault key |
| `PERF cluster` | cycle id, cluster moid, hosts, calls, wall ms, result (ok / failed / timeout) |
| `PERF pool` | cycle id, workers, max in-flight, max queue depth |
| `PERF push` | cycle id, batch no, resources, stat values, bytes, ms, result |
| `PERF inventory` | cycle id, read (clusters / hosts / ops-resources), ms, count, pages. Never log the ContainerView moId: it embeds the vCenter session key (MAP) |
| `PERF cycle` | cycle id, clusters, perf calls, perf phase wall ms (elapsed, all workers), calls/s (= perf calls / perf phase wall s), summed per-call ms and avg call ms (latency only), push ms, cycle ms, heap used before/after (Runtime) |

**Reading the ceiling (D9).** With several clusters per instance, compare
`PERF cycle` calls/s (perf calls over the perf phase's elapsed wall-clock
time; dividing by summed per-call time would only give inverse latency and
hide the pool's effect) against `max_parallel_clusters`: if calls/s stays
near ~7 as workers rise and avg call ms grows, the ceiling is per vCenter;
if calls/s scales with workers while each cluster's own rate stays under ~7,
it is per cluster. The same lines from the replay harness give the
adapter-side overhead with the server removed.

## Failure handling

| Failure | Behaviour | Cycle outcome |
|---|---|---|
| One cluster's call times out | that cluster counted `timed_out`; its completed types are still pushed; next cluster continues | cycle succeeds |
| One cluster faults (`SystemError`, unexpected fault, 5xx without fault body) | WARN once with fault class and key; cluster `failed` | cycle succeeds |
| `NotSupported` / `InvalidArgument entityRefId` for a type | learned per cluster for 24 h, INFO once | cycle succeeds |
| Batching faults (`wildcardlimit`, `querySpecsSizeLimitOnlyRegularQuery`, `queryspectypelimit`) | programming error; ERROR with key; cluster `failed` | cycle succeeds; unit tests make it impossible (T1) |
| `ManagedObjectNotFound` on a cluster MoRef | cluster removed from the cycle cache; inventory re-read next cycle | cycle succeeds |
| `ManagedObjectNotFound` (or any fault) on the session-lived ContainerView | destroy-ignore, recreate the view, retry the read once; the fault text is logged without the view moId | fails only if the retry fails |
| `NotAuthenticated` | re-login once, retry once | fails only if re-login fails |
| Login fails / vCenter unreachable / certificate failure | instance error with credential-free text (SKILL: first failure message is shown on the account row) | cycle fails |
| Inventory read fails | no perf calls (nothing to address) | cycle fails |
| Every cluster failed | throw a credential-free summary so the account shows down | cycle fails |
| Node uuid not in identity map | count, WARN once per refresh, drop that entity's rows; force identity refresh next cycle | cycle succeeds |
| HostSystem not found in Ops (vCenter adapter not collecting it) | count as unresolved; no push for it | cycle succeeds |
| Push batch fails | counted from `SuiteApiBatchResult`; stitcher never throws (SKILL) | cycle succeeds |
| Response over the size cap | treated as a failed call for that cluster/type, WARN with the cap | cycle succeeds |
| Cycle deadline reached | as in Collector shape | cycle succeeds |
| `vcenter instanceUuid` empty or unreadable | no pushes at all (would orphan or mis-address everything, PY `build_parent_map` comment); ERROR | cycle fails |

A thread kill or `VirtualMachineError` is rethrown, never swallowed
(framework convention, `tier2_architecture.md` 2026-10-24 entry).

---

## Sizing

| Measure | Value | Basis |
|---|---|---|
| Collector heap budget | ~65 MB per instance | JVM §Budget: 10% of ~650 MB headroom on the devel 9.0.2 embedded collector (`-Xmx1024m`, live ~230 to 306 MB, 371 MB 8-day high); worst retained log leaves ~340 MB |
| Cloud Proxy collector heap | unknown | JVM: proxies not readable (no SSH credential); the Python pack instances run on the proxies |
| Objects added | 0 (+1 adapter instance) | this design; Python pack 460 on the lab (FOOT §3) |
| Series per cycle, lab, Build 1 | up to 390 | metric list above; FOOT §6 counts |
| Series per cycle, 70 clusters x 6 hosts x 2 pNICs, Build 1 | ~32,760 (420 hosts x 78) | PLAN §1 worked example inputs; NIC count per host is a lab ratio, not known for the target |
| Perf calls per cycle | 3 per cluster | MAP test 4 |
| Wire bytes per cluster, Build 1 | 9,130 B wire (918 + 4,475 + 3,737), ~131.6 KB decoded, on the lab cluster (5 hosts, 10 pNICs); inventory read 908 B wire / 9,821 B decoded | `PROVENANCE-2026-11-06-evening.md`; confirm at scale with `PERF call` |
| Response with gzip | host-domclient unlabelled 7.8 KB gzip vs 130 KB without | MAP comparison table |
| Push volume | `ceil(hosts/100)` requests per cycle | SKILL batch push |

Deployment note to ship in README: recommend pinning the instance to its
own collector group (PLAN §6).

---

## Test plan

**T1. Offline unit tests (plain JUnit-free mains or the template's
`ci/run_java_tests.sh` harness, no SDK, no network):**
- Request builder: exactly one spec; `_typeName` present on the spec;
  cluster MoRef shape; dates UTC with `Z`; labels array equals the design
  list per type; no `interval`.
- Parser against `queryperf-cluster-domclient-2026-11-06.json` (verbatim):
  1 entity, 14 series, `sampleInfo` two timestamps, newest-value selection
  picks `457` for `iopsRead` at `2026-11-07 00:10:00` UTC.
- Fault parser against `queryperf-fault-wildcardlimit-2026-11-06.json`:
  class `InvalidArgument`, key
  `com.vmware.vsan.perfsvc.fault.queryperf.wildcardlimit`, empty-param
  `faultstring`.
- `None` tokens: newest non-`None` wins; all-`None` yields no value.
- Empty-type echo (`entityRefId` ends `:*`, no `value`): zero rows.
- entityRefId splitting for each type, including a malformed pNIC id
  (skipped and counted).
- Per-mille conversion and leaf naming for all 61 keys (table-driven from
  this design, so the design and the code cannot drift).
- Duplicate-bucket suppression across two simulated cycles.
- Identity: node uuid to MoRef to Ops resource id; MoRef present in two
  vCenters resolves only under the matching VCID.
- Fixtures for `host-domclient`, `host-domowner`, `vsan-pnic-net` are the
  verbatim evening captures (`queryperf-host-domclient-2026-11-06.json`,
  5 entities / 30 series; `queryperf-host-domowner-2026-11-06.json`, 5 / 190;
  `queryperf-vsan-pnic-net-2026-11-06.json`, 10 / 170), copied into the pak
  with their provenance; never hand-invented responses presented as vendor
  output. Inventory parser fixture: `retrievepropertiesex-cluster-hosts-2026-11-06.json`
  (wrapped scalars, bare MoRefs, name-sorted properties) and the
  `InvalidProperty` fault sample.

**T2. Fake-server tests (JDK `HttpServer`):** session header sent on every
call; `NotAuthenticated` then re-login then retry once; HTTP 500 fault body
read through the small cap; gzip decode; over-cap response; per-call
timeout fires and the next cluster proceeds; cycle deadline cancels and the
completed clusters are still pushed.

**T3. Replay harness (PLAN §7):** a fake perf client that serves recorded
per-type responses and rewrites cluster uuid, node uuids and NIC names per
synthetic cluster, with configurable per-call latency and a global calls/s
throttle (to model both ceiling hypotheses, D9). Seed: P1 captures in the
repo; optionally the local-only recording at
`/mnt/holding/vsan-perfsvc-recording-2026-11-06/` (SOAP-derived JSON, not
the JSON transport shape, outside the repo; dev use only, never a CI
dependency). Runs the real collect path minus the Suite API (a recording
stitcher fake).

**T4. Budget gate (CI, on every change):** harness at 70 synthetic clusters
x 6 hosts x 2 pNICs: assert peak heap delta under 65 MB (D6), cycle wall
time under the deadline with a 0.19 s per-call latency and 4 workers, and
series pushed equal to the expected count. Both throttle models run; the
per-vCenter model is the one that must pass.

**T5. Live proof, three platforms (RULE-019, D8):** install on devel_8_18,
devel (9.0.2) and devel_9_1, one instance each against
`vcf-lab-vcenter-mgmt` / `vcf-lab-mgmt-cl01`, on the Cloud Proxy collector
(where the Python pack runs, JVM). For each:
- installed solution version read from `GET /suite-api/api/solutions`
  (SKILL: not the CLI OK line);
- read-back of one key per group on each of the 5 hosts with
  `GET /suite-api/api/resources/{id}/stats?statKey=...` after allowing the
  1 to 4 minute lag (PUSH), compared to the newest sample in the same
  cycle's `PERF` log;
- browser pass on one host's Metrics tab: does `vSAN Perf > pNIC > vmnic0`
  render as an instance, what label a leaf shows (PUSH §Visual open item);
- adapter self-metrics present; one cycle with `perf_timing_logging=true`
  captured for the record;
- the build record names which compile legs ran (8.18 Java 11 bytecode,
  2.2, 9.1.1.0100). Recorded under `knowledge/context/reviews/`.
- Side-by-side with the Python pack on the same instance is fine (distinct
  adapter kind); its own objects are unaffected.

Gate order: `validate-sdk`, `build-sdk`, `sdk-adapter-reviewer`,
pak-compare zero BLOCKING, then T5, then `v*` tag via the repo CI and the
defect gate (RULE-012).

---

## Request Mapping

| # | Request | API | Objects fed | Notes |
|---|---|---|---|---|
| 1 | Login / about | vim25 JSON | none (session, VCID) | per instance |
| 2 | Cluster + host inventory | vim25 JSON (P1) | identity map | cached |
| 3 | `GET /api/resources` HostSystem | Suite API | identity map (Ops ids) | refresh cadence |
| 4 | `VsanPerfQueryPerf host-domowner:*` | vSAN JSON | HostSystem `vSAN Perf\|DOM Owner\|*` | per cluster |
| 5 | `VsanPerfQueryPerf host-domclient:*` | vSAN JSON | HostSystem `vSAN Perf\|DOM Client\|*` | per cluster |
| 6 | `VsanPerfQueryPerf vsan-pnic-net:*` | vSAN JSON | HostSystem `vSAN Perf\|pNIC:<nic>\|*` | per cluster |
| 7 | `POST /api/resources/stats` | Suite API | all of the above | batched |

## Events

None. Pak-runtime events are stripped from SDK pak builds (SKILL "Events").
Alerting on these keys is factory symptoms and alerts on HostSystem
(Build 2 content round), which is the point of putting the keys on the host
(PLAN §5).

## Bundled Dashboard

None in Build 1. Build 2 content (PLAN §5): host-centric Object List to
Metric Chart, Scoreboard following dashboard time; views as drill-down.
Bundled in the pak repo, goes through the RULE-011 wireframe gate.

---

## Build 2 (orientation, gets its own design revision)

Parity target: the Python pack's default scope, 451 keys over 33 kinds
(INV §3; PY `metric_scope.COVERED`). Tiers by entity type (PY kind to type
mapping via `perfsvc_model.ENTITIES`):

| Tier | Entity types | Keys | Lands on (recommended) | Default |
|---|---|---|---|---|
| host | `cmmds-net`, `vsan-cpu`, `vsan-direct-host`, `host-domclient`, `host-domcompmgr`, `host-domowner`, `host-esa-dedup-domclient-io`, `vsan-host-net`, `host-zdom-top-stats`, `vsan-memory`, `vsan-pnic-net` (instanced by NIC), `rdt-network-latency`, `vsan-tcpip-stats` (instanced by stack), `vsan-vnic-net` (by stack + vmk), `vnic-rdt-network-latency` (by vmk), `zdom-vtx` | 210 | VMWARE HostSystem | on |
| cluster | `vsan-cluster-capacity`, `cluster-domclient`, `cluster-domcompmgr`, `cluster-domowner`, `cluster-esa-dedup-domclient-io`, `cluster-rdt-network-latency`, `cluster-zdom-top-stats`, `vsan-direct-cluster`, `vsan-file-service`, `ioinsight` | 189 | VMWARE ClusterComputeResource, keyed (MoRef, VCID), Q6 | on |
| disk | `cache-disk`, `capacity-disk`, `vsan-esa-disk-layer`, `vsan-esa-disk-scsifw` | 31 | built-in vSAN disk kinds matched on `VSANID` + host (INV §3, §4); 24 of the 31 keys match built-in `vSAN\|Performance\|*` names (INV §3 suffix column, name match only), so emit only the non-overlapping ones unless a value comparison shows otherwise | off |
| vm | `virtual-machine`, `virtual-disk` (instanced by disk), `vscsi` (instanced by device) | 21 | VMWARE VirtualMachine via `config.instanceUuid` (30/30 matched, MAP) | off; cadence every N cycles |

Notes from the inputs:
- `vsan-direct-cluster`, `vsan-file-service` and `ioinsight` are modelled
  per host uuid in the Python pack (PY identity `host_uuid`) despite sitting
  in the cluster pool of INV §3; confirm the entity id form per type during
  Build 2 before deciding where they land.
- Call floor at full scope: 33 per cluster, ~27 after learned skips
  (MAP "Design answers"); this is where D9's ceiling decides whether one
  instance carries 70 clusters or sharding via `cluster_include` is
  mandatory.
- Suite API ingest at ~1.36M series per cycle (PLAN §1) is unmeasured; the
  `PERF push` lines give the first number.
- VM tier needs a VM MoRef map per cluster (inventory cost grows with VM
  count); that read gets its own cadence.

## Migration (D7)

Distinct adapter kind `vcfcf_vsanperf`; the Python pack (`VsanHostMetrics`,
DOCKERIZED) cannot be upgraded in place to a classic Java pak
(`knowledge/lessons/cross-runtime-pak-upgrade-split-brain.md`). Users run
both side by side while comparing, then uninstall the Python pack, and
recreate accounts and credentials on this pak. No data carries over: the
Python pack's per-entity objects and their history are removed with it;
this pak's history starts on HostSystem from its first cycle. README must
say this plainly.

---

## Key Risks

1. **R1 Inventory over JSON (closed 2026-11-06).** Measured, one
   `RetrievePropertiesEx` call; see the Addendum. Residual: paging and cost
   at 70 clusters are projected, not measured (the lab has one cluster).
2. **R2 Pushed keys have no label or unit, and instance rendering is
   unverified** (PUSH). Mitigation: unit in the leaf name; T5 browser pass
   on all three platforms before the first tag; key names frozen at that
   point because pushed keys cannot be deleted.
3. **R3 Units are borrowed.** PY units come from HCIBench, not the API;
   per-mille handling rests on the Python pack's own evidence
   (`tcpRcvdupackRate` comparison). A wrong suffix is permanent. Mitigation:
   Q1; spot-check a few values against the vSphere client's vSAN
   performance charts during T5.
4. **R4 Throughput ceiling unknown (D9).** Harmless at Build 1 scope (210
   calls at 70 clusters), decisive for Build 2. Mitigation: `PERF` logging
   and the harness's two throttle models.
5. **R5 Heap on the Cloud Proxy is unknown** (JVM). The 65 MB budget is
   derived from the analytics-node collector. `SimpleJson` builds a full
   tree per response. Mitigation: T4 gate; streaming parse if it fails.
6. **R6 JSON API version floor.** Release ids below 8.0.3.0 were rejected on
   9.1.1; JSON API on vCenter older than 8.0 U1 is inferred absent (MAP).
   The supported vCenter range for this pak is not yet stated (Q7).
7. **R7 Silent push drops.** A batch 2xx does not mean every id landed
   (SKILL). Mitigation: resolver refresh detects stale ids; T5 read-back.
8. **R8 Read-back lag** of 1 to 4 minutes (PUSH) means no in-cycle
   self-check may treat "not readable yet" as failure.
9. **R9 Sharding identity.** If `cluster_include` were not part of account
   uniqueness, two shard instances on one vCenter would collide as the same
   account (inferred from identType semantics, not tested). Q3.

---

## Open questions for the user

Each has a recommended answer already written into the design above; the
author can proceed on the recommendation unless told otherwise.

1. **Q1 Stat key leaf names.** Recommended: vSAN label verbatim plus a unit
   suffix (`Us`, `BytesPerSec`, `Pct` for per-mille converted to percent),
   e.g. `vSAN Perf|DOM Owner|latencyAvgWriteUs`, `vSAN Perf|pNIC:vmnic0|rxErrPct`.
   Alternative: raw labels, raw per-mille values, units only in docs.
   Permanent once shipped.
2. **Q2 Root segment.** Recommended `vSAN Perf` (PLAN §2, PUSH tests).
   Alternative: a pak-branded root such as `VCF Content Factory vSAN` to make
   ownership obvious on HostSystem.
3. **Q3 Cluster filter as account identity.** Recommended: `cluster_include`
   is part of uniqueness (identType 1), so shard instances against one
   vCenter are distinct accounts; `cluster_exclude` stays advanced. Cannot
   be changed after release without re-creating accounts.
4. **Q4 Self-metrics on the adapter instance.** Recommended: yes, the
   eleven `Collection|*` keys, so health and the call rate are visible in
   Ops, not only in logs.
5. **Q5 Release id.** Recommended: pin `8.0.3.0`, fall back to the server's
   own version on `Unknown release ID`.
6. **Q6 (Build 2) Cluster-level home.** Recommended: stitch onto VMWARE
   ClusterComputeResource keyed (MoRef, VCID), zero new objects. Alternatives:
   the built-in vSAN Cluster object (ID string embeds MoRef and datacenter
   name, INV §4) or one own-kind object per cluster.
7. **Q7 Supported vCenter range.** Recommended: vCenter 8.0 U3 and later
   (oldest release id accepted is 8.0.3.0; the 8.0 U1/U2 JSON surface is
   unverified). Needs the target customer's vCenter version (PLAN
   §Decisions, still open).
8. **Q8 Prerequisite P1.** Closed 2026-11-06: the round ran (Addendum).

## Addendum 2026-11-06: P1 resolved, Q1 to Q5 adopted for Build 1

Q1 to Q5 were adopted by the orchestrator for Build 1 as the designer's
recommendations, surfaced to Scott the same day and not yet confirmed by
him; Q1 (key names) and Q3 (identity) are permanent once data lands, so a
change must come before the first live push on a customer instance.

The orchestrator ran the `api-cartographer` round the same day (MAP
subsection "vim25 inventory over JSON (measured 2026-11-06)", six verbatim
samples under `reference/docs/extracted/vsan-perfsvc-json/`). Outcome:

- Inventory is one `RetrievePropertiesEx` over a container view of
  `ClusterComputeResource` traversing to hosts (~20 ms on the lab). The
  JAX-WS fallback is not needed. **Lifecycle decision:** the view is created
  once per session and kept; it is recreated after a re-login or when a read
  on it faults (failure table). Its moId embeds the session key and is never
  logged. **Paging:** loop `ContinueRetrievePropertiesEx` while the result
  carries a `token` (MAP; expected at ~70 clusters), with a T2 fake-server
  two-page test. PropertyCollector JSON wraps strings, booleans and arrays
  as `{"_typeName":..,"_value":..}`, leaves MoRefs bare, and returns
  properties sorted by name.
- **Correction to §Prerequisite P1 and the call plan:** the cluster-side
  paths `configurationEx.vsanConfigInfo.enabled` and `.defaultConfig.uuid`
  fault `InvalidProperty` over JSON. The cluster's vSAN enabled flag and
  uuid are derived from its member hosts'
  `config.vsanHostConfig.clusterInfo.uuid` (equal to the cluster uuid on
  every host). Call-plan steps 1 and 2 are one call. **Rule:** a cluster is
  vSAN-enabled when at least one member host has `enabled=true` and a
  non-empty `clusterInfo.uuid`; that uuid is the cluster uuid, and if
  members disagree the majority value is used with one WARN. A cluster with
  no such host (including an empty cluster) is skipped with one INFO. A host
  with an empty `nodeUuid` is left out of the node map.
- A standalone non-vSAN host (outside any cluster) carries `enabled=false`
  and `nodeUuid=""` (empty string, not absent); it appears in none of the
  three perf types.
- pNIC entityRefId confirmed as `vsan-pnic-net:<nodeUuid>|vmnicN`. Only the
  vSAN-active NICs with link up were reported on the lab; whether the rule is
  "uplinks behind vSAN" or "every NIC with link" is unresolved.
- All three Build 1 types returned exactly the designed labels (390 series
  on 5 hosts), so the per-type fixtures for T1 exist.
- Not measured: PropertyCollector paging at 70 clusters, a non-vSAN host
  inside a vSAN cluster.

Build 1 is authored on the recommended answers to Q1 through Q5; Q6 and Q7
remain open for the Build 2 revision.

## Addendum 2026-11-06 (later): collector object, build 7

The devel 9.0.2 proof of build 5 showed the platform never includes the
adapter instance among the resources it collects, so a cycle that runs in
`rediscover` cannot report DOWN: an unreachable vCenter showed ERROR
"Resource discovery failed and there was nothing to collect" (T5 record
`knowledge/context/reviews/vsanperf-t5-devel-9.0-build-5.md`). Build 7
applies the build 4 review's W1 fix (`knowledge/context/reviews/vsanperf-build-4-review.md`).
**This addendum supersedes §Object Model ("the only object the pak creates",
"new objects per cluster: 0", "no children"), §Relationships item 2 and the
"delivered in the collect result" line: the pak now declares a second kind,
`VsanPerfCollector`, one object per adapter instance, a child of the instance
in the discovery result, carrying no metrics. Self-metrics are addressed to
the adapter instance resource that `rediscover` hands over and are pushed
through the Suite API like the host keys.**

- Each instance discovers **one object of its own kind**,
  `VsanPerfCollector` ("VCF Content Factory vSAN Performance Collector"),
  and the whole cycle runs in `collect()` for it, as compliance does for
  `ComplianceWorld`. A failed cycle is a normal collect failure, so an
  unreachable vCenter maps to DOWN with the credential-free message.
- **Identity of that object** (permanent once released): `vcenter` (the
  configured vCenter host, lower-cased) plus `cluster_scope` (the cleaned
  include list, `*` for all). Not the vCenter instanceUuid, which is only
  known after a successful login and would leave an unreachable vCenter
  undiscoverable. This is the same tuple as the account identity, so it
  stays one object per instance. **Correction (peer review of the records
  PR):** build 7 normalised the values (host lower-cased, scope trimmed and
  de-duplicated) while the account identity is the raw strings, so two
  accounts differing only in case or whitespace would share one object.
  Build 8 (before the first tag) builds the identity from the trimmed raw
  values exactly as the account stores them.
- Self-metrics stay on the adapter instance (proved on 9.0.2, 8.18.7 and 9.1.1); `rediscover`
  only hands that resource along and never throws.
- An object discovered in cycle N is first collected in cycle N+1, so a new
  instance against an unreachable vCenter shows DOWN from the second cycle.
