# vsanhostmetrics: scaling plan for a 70-cluster vCenter

Written 2026-11-06 for the upstream author of nickfirefoot/vsanhostmetrics,
from reading 1.4.7 / the open 2.0.0 PR and the author's own notes
(too many metrics, JVM memory, 20-second samples, views that do not trend,
a first customer with 70 clusters on one vCenter and no way to scale-test).

Short version: the pack's problem is not Python versus Java and not the
number of metrics *defined*. It is (a) one object per vSAN entity, which
multiplies on hosts, NICs, disks, VMs and virtual disks, and (b) one
Performance Service call per entity type per cluster, serial. Fix those two
and the same pack runs at 70 clusters in either language. Switch to Java
and keep the design, and it falls over in the collector JVM instead of in
a container.

## 1. Where the numbers actually come from

### What Ops charges for

Ops sizing is driven by **objects** first and **metrics per cycle** second.
Every object carries identity, relationships, a dynamic-threshold model per
metric, and a row in every list. Metrics on an existing object are cheap
by comparison. This pack currently creates objects for everything.

### What the pack emits today (default "dashboard" scope, 1.4.7)

Grouped by what each kind multiplies on (from `app/perfsvc_model*.py`
identity fields and `app/metric_scope.py`):

| Multiplies on | Kinds in scope | Scoped metrics | Objects per unit (lab) |
|---|---|---|---|
| cluster | 7 | 91 | ~6 per cluster |
| host | 15 | 259 | ~10 per host (ESA dedup, IOInsight, File, Direct add 5 more when present) |
| host x TCP stack / vmknic / vmnic | 4 | 49 | ~5 per host |
| disk | 4 | 31 | 1 per disk (5 to 8 per host) |
| VM | 1 | 6 | 1 per VM |
| virtual disk | 1 | 7 | 1 per vdisk (~2 per VM) |
| VM x vSCSI device | 1 | 8 | 1 per vdisk (~3 per VM) |

So, roughly: **20 objects and ~370 metrics per host, 6 objects and ~44
metrics per VM, 6 objects and ~90 metrics per cluster.** That matches the
README's 500 to 850 objects on a four-host lab cluster.

### The 70-cluster customer, worked

Assume 6 hosts per cluster and 40 VMs per host (adjust; the shape is what
matters):

| | Hosts: 420 | VMs: 16,800 | Clusters: 70 | Total |
|---|---|---|---|---|
| Objects | 8,400 | 100,800 | 420 | **~110,000** |
| Data points per 5 min (one per metric key per object) | 155,000 | 740,000 | 6,300 | **~900,000** |
| Perf Service calls per cycle | | | 33 x 70 | **2,310 (API floor: one wildcard per call)** |

Against Broadcom's 8.18 sizing guideline (KB 369262): 900,000 series
fit a Small Cloud Proxy (1.2M) and a Small analytics node (1.6M), so the
metric count is not the problem. 110,000 objects needs an Extra Large
node (100k single-node) or a Medium cluster (136k), sharded across three
Standard Cloud Proxies (40k each). Deployable, but the pack adds ~6
objects per VM where the vCenter adapter carries 3 or 4, roughly
doubling the customer's object count for one pack.

What actually breaks is time: 2,310 serial calls at ~0.4 s is ~15
minutes against a 5-minute cycle. With VM kinds off: 8,800 objects and
160k series, inside a Small Cloud Proxy; the time problem is unchanged.

### The 20-second / 33k figure

Two corrections, because the author's math (2,200 metrics x 15 samples of
20 s in 5 minutes = 33k per 4-node cluster) sets the wrong design target:

1. **The vSAN Performance Service samples every 5 minutes** (every 1 minute
   with verbose mode on). The 20-second cadence is vCenter's realtime
   `PerformanceManager` counters, which this pack does not read. The
   pack already pulls a 15-minute window and keeps the last sample.
2. **Ops wants one value per metric per object per collection cycle.**
   Adapters do not replay sub-interval samples; the vCenter adapter
   averages the 20-second realtime points into one 5-minute value. If a
   max or an average over the interval matters for a particular metric,
   emit it as a second metric (`latencyRead|max`) computed in the adapter,
   and do that for the few that matter, not for 2,200.

So the per-cycle load is objects x metrics, once. Nothing is 15x.

## 2. Object model: stop creating objects

### Principle

A vSAN host-scoped entity (DOM owner, DOM client, component manager, LSOM,
memory, CMMDS, RDT, zDOM, TCP/IP) is not an object. It is a **metric group
on the host**. Ops models exactly this already: the vCenter adapter puts
`net:vmnic0|received_average` on the HostSystem as an instanced metric,
not as a vmnic object. The pack should do the same.

Target model:

| Today (object per entity) | Target | Lands on |
|---|---|---|
| VsanHostDomowner, VsanHostDomclient, VsanHostDomcompmgr, VsanMemory, VsanCpu, VsanCmmdsNet, VsanRdtLatency, VsanHostNet, VsanZdomVtx, VsanHostZdomTopStats, ESA dedup host kinds, VsanIoinsight | metric groups `vSAN Perf|DOM Owner|…`, `vSAN Perf|Memory|…` | **existing** VMWARE HostSystem |
| VsanPnic, VsanVnic, VsanVnicRdtLatency, VsanTcpIp | instanced groups `vSAN Perf|pNIC:vmnic0|…`, `vSAN Perf|vmknic:vmk1|…`, `vSAN Perf|TCP stack:defaultTcpipStack|…` | existing HostSystem |
| VsanCacheDisk, VsanCapacityDisk, VsanEsaDiskLayer, VsanEsaDiskScsifw | metric groups | **existing** built-in vSAN adapter Cache Disk / Capacity Disk objects (`VirtualAndPhysicalSANAdapter`), or instanced on the host keyed by disk name if matching those identifiers proves unreliable |
| VsanCluster* kinds, VsanClusterCapacity | metric groups | existing built-in vSAN Cluster object, or the VMWARE ClusterComputeResource |
| VsanVirtualMachine | metric group | existing VMWARE VirtualMachine |
| VsanVirtualDisk, VsanVscsi | instanced `vSAN Perf|vDisk:scsi0:0|…` | existing VirtualMachine |

Result: **zero new objects** from this pack at the host, disk and VM
layers. The 70-cluster customer goes from ~110,000 objects to 0 new
objects (or 70 if the cluster layer stays an own-kind object as a
landing spot for cluster dashboards). The "9 tree structures" disappear;
the tree is vCenter's.

Metrics per cycle do not change by this move alone (still ~900k at full
VM scope), which is why section 3 still matters. But 900k metrics on
existing objects is a sizing line item; 110k objects is a redesign of the
customer's Ops deployment.

### This is stitching, as the compliance adapter does it

ARIA_OPS stitching (`vcfops-sdk-adapter` skill, "Pushing data"): no own
host/VM/disk objects, Suite API batch push via `SuiteApiStitcher`,
resolver on vCenter instanceUuid + MOID, Ops credential on the instance,
failures counted not thrown. Reused as is. Stitched keys have no label
or unit (a pak declares its own kind), so name keys for people with the
unit in the name, settled before the first release.

Newly checked 2026-11-06 on devel (`2026-11-06-suite-api-instanced-push.md`):
instanced keys stitch one per instance; back-dated values are accepted;
the push returns 200 one to four minutes before the value is readable.

### The identity map is the one hard piece

The pack already has it: `build_parent_map` joins vSAN node uuid to the
host MOID via vCenter (not by hostname, which was the 1.4.x bug), vdisk
uuid to VM, disk uuid to host. Keep that map, build it once per cycle per
cluster, and use it to address pushes instead of to add children.

## 3. Collection: what the API allows (measured 2026-11-06)

Probed read-only on the lab vCenter 9.1.1 (one ESA cluster, 5 hosts,
30 VMs). Map: `knowledge/context/api-maps/vsan-performance-service.md`.
Recording for a simulator: `/mnt/holding/vsan-perfsvc-recording-2026-11-06/`.

| Question | Answer |
|---|---|
| One call for all clusters | No. Cluster omitted faults (SystemError). |
| All 33 types in one call per cluster | No. `InvalidArgument` / `wildcardlimit`: one wildcard spec per call. Explicit refs batch 100 per call but cost ~6x more. |
| Per-cluster floor | 33 wildcard calls, 6 to 11 s serial, 109 KB, 423 entities; 6 types empty here |
| `labels` filter | Halves bytes (1.31 MB to 0.68 MB); no wall-time change |
| Window | 5 min drops entities at the boundary; 7 min safe; `interval` ignored |
| GetSupportedEntityTypes | Describes the vSAN version, not the cluster (listed PMem, which faulted); 4 ids are not query prefixes. Per-cluster learning stays, ~0.05 s per type |
| Concurrency | ~7 calls/s ceiling with 4 to 16 workers on one cluster; per-vCenter or per-cluster is unknown |
| Session | Login 0.26 s; reused-session call 0.002 to 0.04 s |

At 70 clusters: floor 2,310 calls (~1,900 skipping known-empty types).
Serial ~6 to 7.5 min (fails the cycle). At 7 calls/s ~5 min (marginal).
If the ceiling is per cluster, an 8-worker pool is ~1 min. **Measuring
the ceiling on a multi-cluster vCenter decides whether one instance can
carry 70 clusters or sharding is mandatory.**

The pack's live cycle is 28 to 75 s on this cluster while the 33 perf
calls take 6 to 11 s: most of the cycle is inventory walking, name
resolution and child re-attachment, not the Performance Service.

1. Parallelise across clusters with a bounded pool sized to the ceiling.
2. Learn per cluster which types fault or are empty; re-probe daily.
3. Send `labels` on every spec.
4. 7-minute window.
5. Process and discard per cluster.
6. One vCenter session per instance, reused across cycles.
7. Cache the inventory and name maps; rebuild every N cycles.
8. Cluster filter parameter so the customer can shard across instances
   and Cloud Proxies.

## 4. Metric scope: three levers instead of one switch

Keep "every metric is declared, scope decides what is emitted"; that is
already right. Replace the dashboard/all enum with:

1. **Tiers:** `cluster`, `host`, `disk`, `vm`, cumulative. Default
   `host` (cluster + host + NIC/vmknic layers). `vm` is the one that
   multiplies by thousands and is opt-in per instance. Combined with
   the cluster filter, a site can turn VM detail on for the two
   clusters it is troubleshooting.
2. **Exclude list:** a free-text list of kinds or metric groups to drop
   on top of the tier, so a site can trim without a release.
3. **Cadence:** collect VM-tier kinds every Nth cycle (N=3 gives
   15-minute VM trends). Ops tolerates gaps; the window logic already
   takes "last sample in window".

And measure it: log, per cycle, objects touched and metrics emitted per
kind and the per-cluster query time, and point users at the adapter
instance's own `Metrics collected` self-metric. The README's "11 to 16
seconds" says nothing about ingest.

What stays as own-kind objects after this: nothing, or cluster only.
If a cluster object is kept, 70 objects per 70 clusters is fine.

## 5. Content: trending comes free once metrics live on the host

The author's complaint ("views are time period fixed, you have to hunt
from the view to the metric trending, sparklines and health scores don't
scale") is a consequence of the object model, not of Ops. Once DOM owner
latency is a metric on the HostSystem:

- The host's **Metrics tab** trends it with the normal time slider,
  alongside CPU, memory and vCenter's own vSAN metrics. No hunt.
- A dashboard is **Object List (hosts in cluster) -> Metric Chart** with
  the standard selection interaction. Click a host, see the chart. That
  is the vCenter adapter's own dashboard pattern.
- **Scoreboards follow dashboard time** (the pack's BACKLOG already
  established `periodLength: dashboardTime`), and a Scoreboard of eight
  hosts x four metrics with sparklines is a normal widget load.
- Symptoms and alerts attach to HostSystem, so an alert on
  `vSAN Perf|DOM Owner|latencyAvgWrite` shows up where every other host
  alert does, in the same policy. Health scores are not needed.

The eight shipped list views remain useful as a tabular drill-down; they
just stop being the only path.

## 6. The port is Java Tier 2: build it to a budget

The target is a native Java Tier 2 SDK adapter (decision 2026-11-06).
The container comparison still says what the port inherits: the
collector's heap and threads are shared with every adapter on that
Cloud Proxy, an OOM restarts the collector, a stuck call holds a
collector thread. So the port is built to a budget from the first
commit:

- Port `perfsvc.py` first, as a plain Java class with the same offline
  tests and a replay harness; adapter lifecycle second.
- **Transport: JSON over HTTP, no vSAN SDK jars** (measured 2026-11-06,
  map section "JSON API transport"): same handlers, limits, faults and
  ceiling as SOAP, slightly faster; `HttpClient` + Jackson. Specs need
  `_typeName`; UTC ISO dates only; release id from
  `/sdk/vimServiceVersions.xml` (8.0.3.0+); token in
  `vmware-api-session-id`; gzip; `None` tokens in values CSV; re-login on
  `NotAuthenticated`.
- Metrics land on HostSystem / VirtualMachine via the Suite API batch
  push (`SuiteApiStitcher.pushBatch`, buildkit 1.0.24+), with a
  resolver keyed on vCenter instanceUuid + MOID, refreshed every few
  cycles. Needs an Ops credential on the instance.
- ~100 MB heap budget for the instance (measured 2026-11-06 on the devel
  9.0.2 collector: 1 GB max, 230 to 240 MB live after full GC with 12
  instances, 371 MB 8-day peak, 682 MB September peak; see
  `2026-11-06-collector-jvm-sizing.md`), proven against the harness at
  70 synthetic clusters; bounded pool; process-and-discard per cluster;
  one vCenter session per instance; timeouts on every call and a cycle
  deadline below the interval.
- Ship with a recommendation to pin the instance to its own collector
  group.
- Start from the factory's `…-sdk-template` repo, buildkit and CI; the
  Java path is build-and-figure-it-out and that cost is already paid
  there.

The real win of the port is airgap: one pak file, no image.

## 7. Scale-testing without 70 clusters

The author cannot scale-test. He does not need 70 clusters:

1. **Record** one cluster's Performance Service responses for every
   entity type (one cycle, raw SOAP or the pyVmomi objects pickled).
2. **Replay** them through a fake `perf` object that answers
   `VsanPerfQueryPerf` from the recording with the cluster uuid, host
   uuids, VM uuids and vdisk uuids rewritten per synthetic cluster.
   70 synthetic clusters from 1 recording.
3. Run `collect()` against it under `mp-test` and measure wall time,
   peak RSS (the container's limit is the budget), objects and metrics
   per cycle. That is the number the customer will ask for.

The offline test split the pack already has (`perfsvc.py` has no SDK
imports) makes this a day's work, not a lab.

## 8. Order of work

1. Measure (section 4 logging, section 7 replay harness). One day.
   Gives the before number.
2. Collector: batch per cluster, bounded pool, 7-minute window, learn
   unsupported types per cluster, cluster filter parameter. Two days.
   Fixes the cycle-time failure at 70 clusters by itself.
3. Model: host-scoped kinds to metric groups on HostSystem, one kind
   first (DOM owner, the 38-metric one), prove on the lab for a day,
   then the rest. VM-scoped kinds last, behind the `vm` tier.
4. Content: rebuild the dashboards host-centric (Object List + Metric
   Chart + Scoreboard). Views stay.
5. Tiers, exclude list, cadence.

The 2.0.0 PR (certificate, error surfacing, cluster isolation, credential)
should land before any of this, since steps 2 and 3 touch the same
collect loop and the per-cluster isolation it adds is a prerequisite for
batching.

## What the lab says (recon 2026-11-06, VCF Ops 9.0.2, vSAN ESA)

Full report: `2026-11-06-vsan-adapter-inventory.md`.

- **The pack's core is not duplicated.** The built-in vSAN adapter
  (`VirtualAndPhysicalSANAdapter`) exposes nothing for DOM owner, DOM
  client, component manager, RDT, zDOM, pNIC, vmknic, TCP/IP, CMMDS or
  per-VM vSAN. HostSystem carries no vSAN stat key at all. Those layers
  are the pack's reason to exist and nothing in section 2 removes them;
  it only moves where they land.
- **The disk tier is largely duplicated.** Built-in `vSAN|Performance|*`
  on the ESA disk object (47 keys) covers 8 of 8 cache-disk, 8 of 13
  capacity-disk and 4 of 5 ESA disk-layer metrics by name. Decision for
  the author: drop the disk tier from the default scope, or stitch the
  remaining few onto the built-in disk object. Its `VSANID` identifier
  equals the pack's `disk_uuid`, so the key already matches.
- **Cluster stitching has a key.** The built-in vSAN Cluster `ID` is
  `vSAN Cluster(domain-cNNNN, <datacenter>)`; parse the MoRef and match
  the VMWARE cluster on `VMEntityObjectID` + `VMEntityVCID`. The pack's
  `cluster_uuid` is not on the built-in object, so the join goes through
  vCenter, which the pack already queries. Cluster-level DOM metrics
  overlap the built-in 11 `vsan|performance|*` keys only by name: the
  built-in is one aggregate, the pack is per layer. Keep the pack's.
- **Host stitching needs no new key.** The pack already resolves vSAN
  node uuid to host MOID through vCenter for its relationships (the fix
  for the 1.4.x hostname-join bug); that is the address for the push.
- **Reference point (live footprint, 3 instances, fork 2.0.0):** one ESA
  cluster, 5 hosts, 41 VMs: **460 objects, 6,184 series per cycle,
  collection 19 to 115 s per cycle** (unit inferred), ~90 MB container
  memory. The vCenter adapter has ~90 objects and ~8,000 series for the
  same vCenter; the built-in vSAN adapter models the cluster in 11
  objects. 70 clusters in series at 28 to 75 s each is 33 to 87 minutes
  per cycle. Report: `2026-11-06-vsanhostmetrics-live-footprint.md`.

Still open: whether Python-SDK foreign-key metrics land on 9.x with the
pack's re-attach logic, or whether a Suite API pusher is needed in the
container too. One host, one kind, one cycle answers it.

## Decisions (2026-11-06, Scott)

- **Vehicle:** native Java Tier 2 SDK adapter in a **factory SDK repo**
  (instantiated from `…-sdk-template`, registered in `managed_paks.md`),
  not a branch of nickfirefoot/vsanhostmetrics. Nick reviews.
- **Build 1 (MVP):** one cluster, host tier only, three groups pushed onto
  VMWARE HostSystem: DOM owner, DOM client, pNIC. No VM tier, no disk
  tier. Proves the push, the identity map and the heap budget.
- **Build 2:** metric-collection parity with the Python pack's default
  scope (451 keys) on the optimised object model.
- **Throughput ceiling (per vCenter vs per cluster):** answered when a
  simulator or a multi-cluster environment is available. Until then the
  adapter ships an **advanced instance setting for performance-timing
  debug logging** (off by default): per-cluster and per-type call wall
  time, bytes, pool occupancy, cycle total, push batch timings.
- **Open explorations in flight:** JSON transport for the Performance
  Manager on 9.1 (SOAP vs HTTP/JSON for the port), collector JVM heap on
  the lab Cloud Proxies (budget as a fraction of a known number), and an
  instanced-key Suite API push onto a devel HostSystem (declared vs
  undeclared keys, UI rendering).
