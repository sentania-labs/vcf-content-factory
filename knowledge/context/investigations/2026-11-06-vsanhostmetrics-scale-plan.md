# vsanhostmetrics: scaling plan and Java port for a 70-cluster vCenter

Written 2026-11-06 for the upstream author of nickfirefoot/vsanhostmetrics,
from reading 1.4.7 and the open 2.0.0 PR, the author's stated concerns
(too many metrics, collector JVM memory, sub-interval samples, views that
do not trend, a prospective environment with 70 vSAN clusters on one
vCenter and no way to scale-test), and lab measurements taken the same
day (reports cited inline). Rendered page:
`knowledge/designs/vsanhostmetrics-scale-plan-v1.html`.

Short version: the pack's problem is not the number of metrics *defined*.
It is (a) one Ops object per vSAN entity, which multiplies on hosts, NICs,
disks, VMs and virtual disks, and (b) one Performance Service call per
entity type per cluster, run serially. The port fixes (a) by owning no
objects and stitching onto vCenter's own HostSystem and VirtualMachine,
and (b) by running clusters in parallel. Whether one instance then
carries 70 clusters depends on a throughput ceiling the lab cannot
measure (section 3); the plan says so rather than assuming it.

## 1. Where the numbers come from

### What Ops charges for

Ops sizing is driven by **objects** first and **metric series** second,
where a series is one metric key on one object, written once per cycle.
Every object carries identity, relationships, a dynamic-threshold model
per metric and a row in every list. A series on an existing object is
cheap by comparison. The pack creates an object for everything it sees.

Three things people call "metrics": the 1,595 in the README are
**definitions** in describe.xml and cost nothing until emitted; the
counts below are **series**; each series writes one **data point** per
cycle (288 a day).

### What the pack emits today (default scope, measured)

Live footprint on the lab's one vSAN ESA cluster, fork 2.0.0, three Ops
instances (`2026-11-06-vsanhostmetrics-live-footprint.md`): 5 hosts,
41 VMs by Ops' count (30 by the Performance Service's VM entity count on
the same day; the difference is unreconciled), 1 ESA disk per host.

| Measured per instance | |
|---|---|
| Objects | 460 (28 kinds); the vCenter adapter holds ~90 for the same vCenter |
| Series per cycle | 6,184, 13.4 per object; the vCenter adapter ~8,000 |
| Full cycle time | 19 to 115 s min to max, 28 to 75 s per-instance means; unit inferred (ms) |
| Of which Performance Service calls | 6 to 11 s for the 33 types, serial (API map) |
| Container | ~90 MB of the 1 GB limit, ~2% CPU |

Per-unit ratios derived from that (the per-VM figures are measured
object counts divided by VM count; the per-host figures are what is left):

| Multiplies on | Kinds in scope | Scoped keys | Objects per unit | Series per unit |
|---|---|---|---|---|
| cluster | 7 | 91 | ~6 | ~90 |
| host (incl. NIC, vmknic, TCP stack, disk kinds) | 23 | 339 | ~17 to 20 | ~370 |
| VM (VM + ~4.5 vdisks + ~4.2 vSCSI devices) | 3 | 21 | ~10 | ~71 |

A per-VM count of 2 vdisks and 3 vSCSI devices was assumed in an earlier
draft; the lab measured 168 virtual disks and 155 vSCSI objects for 37
VMs, which is where ~10 objects and ~71 series per VM come from.

### The sub-interval sample figure

The author's arithmetic (2,200 metrics x 15 samples of 20 s per 5 minutes)
sets the wrong target, twice:

1. **The vSAN Performance Service samples every 5 minutes** (1 minute in
   verbose mode); 20 s is vCenter's realtime PerformanceManager, which
   this pack never reads. Measured: `statsIntervalSec` 300, verbose off.
2. **Ops wants one value per metric per object per cycle.** Adapters do
   not replay sub-interval samples. If a maximum over the interval
   matters, emit it as a second key for the few that matter.

### The 70-cluster environment, worked

Assume 6 hosts per cluster and 40 VMs per host (420 hosts, 16,800 VMs);
adjust the inputs, the shape is what matters.

| | Hosts | VMs | Clusters | Total |
|---|---|---|---|---|
| Objects (today's model) | 8,400 | 168,000 | 420 | **~177,000** |
| Series per cycle | 155,000 | 1,190,000 | 6,300 | **~1,360,000** |
| Perf Service calls per cycle | | | 33 x 70 | **2,310** (API floor, section 3) |

Against Broadcom's 8.18 sizing guideline (KB 369262, figures not stored
in the repo): 1.36M series exceeds a Small Cloud Proxy (1.2M) and sits
just under a Small analytics node (1.6M), inside a Standard proxy (6M)
or Medium node (5M). Once stitched, series land through the Suite API on
the analytics tier, not the proxy collector, so count them against node
sizing; Suite API ingest at that rate is not measured anywhere and is a
Build 2 question. 177,000 objects under today's model needs a Large
cluster (Medium tops out at 136,000); after the model change the pack
adds no objects.

What fails regardless of sizing is time: 2,310 serial calls at the
measured 0.19 s median is about 7.3 minutes against a 5-minute cycle,
before the pack's own inventory work, which on the lab cluster is most
of the cycle (6 to 11 s of calls inside a 28 to 75 s cycle).

## 2. Object model: own nothing, stitch

A host-scoped vSAN entity (DOM owner, DOM client, component manager,
memory, CMMDS, RDT, zDOM, TCP/IP) is a metric group on the host, not an
object. The vCenter adapter already models NICs this way
(`net:vmnic0|received_average` is an instanced key on HostSystem, not a
vmnic object).

| Today (object per entity) | Target | Lands on |
|---|---|---|
| Host-scoped kinds (DOM owner/client/compmgr, memory, CPU, CMMDS, RDT, host net, zDOM, ESA dedup host kinds, IOInsight) | groups `vSAN Perf|DOM Owner|…` | existing VMWARE HostSystem |
| VsanPnic, VsanVnic, VsanVnicRdtLatency, VsanTcpIp | instanced groups `vSAN Perf|pNIC:vmnic0|…` | existing HostSystem |
| Disk kinds | drop from default scope, or stitch leftovers onto the built-in vSAN disk object (section 5) | built-in `Vsan2Disk` / OSA disk kinds |
| Cluster kinds | groups on the built-in vSAN Cluster or VMWARE ClusterComputeResource, or one own-kind cluster object (open) | existing cluster object |
| VsanVirtualMachine | group | existing VMWARE VirtualMachine |
| VsanVirtualDisk, VsanVscsi | instanced `vSAN Perf|vDisk:scsi0:0|…` | existing VirtualMachine |

Result: zero new objects at the host, disk and VM layers (70 if a
cluster object is kept). The "9 tree structures" become vCenter's one
tree. Series per cycle do not change by this move, which is why section
4 still matters; 1.36M series on existing objects is a sizing line,
177,000 objects is a redesign of the customer's deployment.

### This is stitching, as the compliance adapter does it

ARIA_OPS stitching (`vcfops-sdk-adapter` skill, "Pushing data"): no own
host/VM/disk objects, Suite API batch push via `SuiteApiStitcher`,
resolver on vCenter instanceUuid + MOID (never MOID alone), Ops
credential on the instance, failures counted not thrown. Reused as is.
Stitched keys have no label or unit (a pak declares its own kind, not
VMWARE's), so name keys for people with the unit in the name, settled
before the first release.

Newly checked 2026-11-06 on devel 9.0.2 only
(`2026-11-06-suite-api-instanced-push.md`): instanced keys stitch one per
instance; back-dated values are accepted; both push endpoints return a
bare 200 and read-back lags from under 1 to over 3 minutes, so landing
checks are reads. Pushed stats are attributed to the Suite API adapter,
not to the pak's instance, so the pak's own "metrics collected"
self-metric will not count them; the pak logs its own per-cycle counts
and the push result counts instead. UI rendering of stitched instanced
keys is unverified. Per RULE-019, Build 1 proves the stitch on 8.18, 9.0
and 9.1, not only 9.0.2.

### The identity map is the one hard piece

The pack already has it: vSAN node uuid to host MOID through vCenter (the
fix for the 1.4.x hostname-join bug), vdisk uuid to VM, disk uuid to
host; the API map confirms the node-uuid join and the VM instanceUuid
join on the lab (30 of 30). Build it once, cache it, refresh every N
cycles, and use it to address pushes.

## 3. Collection: what the API allows (measured 2026-11-06)

Probed read-only on the lab vCenter 9.1.1, SOAP and JSON transports
(`knowledge/context/api-maps/vsan-performance-service.md`). A raw
recording of one cycle exists at
`/mnt/holding/vsan-perfsvc-recording-2026-11-06/` as a simulator seed;
**local-only artifact, not in the repo and not reproducible from it**;
the map's "Recording" section says how to regenerate one.

| Question | Answer |
|---|---|
| One call for all clusters | No. Cluster omitted faults (SystemError). |
| All 33 types in one call per cluster | No. `InvalidArgument` / `wildcardlimit`: one wildcard spec per call. Explicit refs batch 100 per call but cost ~6x more in total. |
| Per-cluster floor | 33 wildcard calls, 6 to 11 s serial (0.19 s median per call), 109 KB wire; 6 types empty on this cluster |
| `labels` filter | Halves bytes (1.31 MB to 0.68 MB decoded); no wall-time change |
| Window | 5 min drops entities at the boundary; 7 min safe; `interval` ignored |
| GetSupportedEntityTypes | Describes the vSAN version, not the cluster (listed PMem, which faulted); 4 ids are not query prefixes. Per-cluster learning stays, ~0.05 s per type |
| Concurrency | ~7 calls/s ceiling with 4 to 16 workers against one cluster; per-vCenter or per-cluster is unknown |
| Session | Login 0.26 s; reused-session call 0.002 to 0.04 s; idle timeout not measured |

At 70 clusters: floor 2,310 calls (~1,900 skipping known-empty types).
Serial ~7.3 min (fails the cycle). At 7 calls/s ~5.5 min (marginal). If
the ceiling is per cluster, an 8-worker pool is ~1 min. **Measuring the
ceiling on a multi-cluster vCenter or the simulator decides whether one
instance can carry 70 clusters or sharding is mandatory.**

1. Parallelise across clusters with a bounded pool sized to the ceiling.
2. Learn per cluster which types fault or are empty; re-probe daily.
3. Send `labels` on every spec.
4. 7-minute window.
5. Process and discard per cluster.
6. One vCenter session per instance, reused across cycles, re-login on
   `NotAuthenticated`.
7. Cache the inventory and name maps; rebuild every N cycles.
8. Cluster filter parameter so the customer can shard across instances
   and Cloud Proxies.

## 4. Metric scope: three levers instead of one switch

Keep "every metric declared, scope decides what is emitted". Replace the
dashboard/all enum with:

1. **Tiers:** cluster, host, disk, vm, cumulative. Default host. VM is
   the tier that multiplies by thousands and is opt-in per instance.
2. **Exclude list:** kinds or groups to drop on top of the tier.
3. **Cadence:** VM-tier kinds every Nth cycle.

Measure it: per-cycle log of objects touched, series pushed per group,
per-cluster and per-type call time, push batch results. The adapter's
own Ops self-metric does not see stitched series (section 2).

## 5. Content: trending comes free once metrics live on the host

The author's complaint (views are period-fixed, sparklines and health
scores do not scale, clicking a cell does not reach a trend) is a
consequence of the object model. Once DOM owner latency is a key on the
HostSystem: the host's Metrics tab trends it beside vCenter's CPU,
memory and network keys (HostSystem carries no vSAN keys today); a
dashboard is Object List to Metric Chart with the standard interaction;
Scoreboards follow dashboard time; symptoms attach to HostSystem in the
same policy as every other host alert. The list views stay as drill-down.

### What the lab says about the built-in vSAN adapter

Recon on 9.0.2 ESA (`2026-11-06-vsan-adapter-inventory.md`):

- **The pack's core is not duplicated.** The built-in adapter exposes
  nothing for DOM owner/client/compmgr, RDT, zDOM, pNIC, vmknic, TCP/IP,
  CMMDS or per-VM vSAN; HostSystem has zero vSAN keys.
- **The disk tier overlaps by name.** The built-in ESA disk object has 48
  keys, 15 of them `vSAN|Performance|*`, and those names cover 8 of 8
  cache-disk, 8 of 13 capacity-disk and 4 of 5 ESA disk-layer keys of
  the pack. OSA built-in disk objects were not observed (ESA lab), so
  "duplicated" is a name match, not a value comparison. The built-in
  disk's `VSANID` equals the pack's disk uuid but is not unique on its
  own; match on VSANID plus host.
- **Cluster stitching has a key.** The built-in cluster ID embeds the
  MoRef; match the VMWARE cluster on object id plus vCenter id.
- **Reference point:** the built-in adapter models the lab cluster in 11
  objects; the pack in 460.

## 6. The port is Java Tier 2: build it to a budget

Decision 2026-11-06: native Java Tier 2 adapter in a factory SDK repo.
Measured on the devel 9.0.2 analytics node's embedded collector
(`2026-11-06-collector-jvm-sizing.md`): 1 GB max heap, ~230 to 306 MB
live at steady state with 12 adapter instances, 682 MB in a September
pressure period against a 683 MB old-gen cap, hundreds of full GCs and a
7 s pause in recent logs. That is the collector the author is worried
about, and it argues for the following, not against the port:

- **Heap budget ~65 MB per instance** (a tenth of the ~650 MB headroom on
  that node), proven against the replay harness at 70 synthetic
  clusters. The Cloud Proxies, where a customer would run this, could
  not be read (no SSH credential) and are probably smaller and more
  crowded; their number is still open.
- **Transport: JSON over HTTP, no vSAN SDK jars** (map section "JSON API
  transport"): same handlers, limits, faults and ceiling as SOAP,
  slightly faster; `HttpClient` + Jackson. Specs need `_typeName`; UTC
  ISO dates only; release id from `/sdk/vimServiceVersions.xml`; token in
  `vmware-api-session-id`; gzip; `None` tokens in values CSV; re-login
  on `NotAuthenticated`. Measured on 9.1.1 only: that server accepts
  release ids 8.0.3.0 and up; whether an 8.0 U3 vCenter serves the
  endpoint is untested, and the target environment's vCenter version has
  to be checked before this choice is final.
- Port the Performance Service client first, as a plain Java class with
  the Python module's offline tests and a replay harness; adapter
  lifecycle second.
- Process and discard per cluster; bounded pool; timeouts on every call
  and a cycle deadline below the interval; one session per instance.
- Ship with a recommendation to pin the instance to its own collector
  group.
- Start from the factory's `…-sdk-template` repo, buildkit and CI.
- **Migration:** a distinct adapter kind key, side-by-side with the
  Python pack; existing 2.0.0 users uninstall, install, recreate
  instances and credentials
  (`knowledge/lessons/cross-runtime-pak-upgrade-split-brain.md`).

The real win of the port is airgap: one pak file, no image.

## 7. Scale-testing without 70 clusters

1. Record one cluster's Performance Service responses for every type
   (raw JSON; the API map's recording procedure).
2. Replay them through a fake client that rewrites cluster, host, VM and
   vdisk uuids per synthetic cluster: 70 clusters from one recording.
3. Run the collect path from a JUnit test and measure wall time, peak
   heap, and series pushed per cycle. It runs in CI on every change.

## 8. Order of work

1. Record and measure on the Python pack (fixture and before number).
2. Port the Performance Service client to Java with its tests and the
   replay harness.
3. Collector loop: parallel clusters, learned types, labels, 7-minute
   window, cluster filter, timeouts, cycle deadline; prove heap and wall
   time against the harness.
4. Model: stitch host-scoped kinds onto HostSystem, DOM owner first,
   prove on all three lab instances, then the rest; VM tier last behind
   the vm tier; disk tier per section 5.
5. Content: host-centric dashboards (Object List, Metric Chart,
   Scoreboard); views stay.
6. Scope: tiers, exclude list, cadence.

The open 2.0.0 PR on the Python pack is still worth landing: it keeps the
shipping pack honest while the port is built, and its per-cluster
isolation and credential shape are the behaviour the port matches.

## Decisions (2026-11-06, Scott)

- **Vehicle:** native Java Tier 2 SDK adapter in a factory SDK repo
  (instantiated from `…-sdk-template`, registered in `managed_paks.md`),
  not a branch of nickfirefoot/vsanhostmetrics; the Python fork keeps
  shipping meanwhile.
- **Build 1 (MVP):** one cluster, host tier only, three groups stitched
  onto VMWARE HostSystem: DOM owner, DOM client, pNIC. No VM or disk
  tier. Proves the stitch on 8.18, 9.0 and 9.1, the identity map and the
  heap budget.
- **Build 2:** metric parity with the Python pack's default scope (451
  keys) on the zero-objects model; the cluster-object question is
  settled there.
- **Throughput ceiling (per vCenter vs per cluster):** answered when a
  simulator or a multi-cluster environment is available. Until then the
  adapter ships an **advanced instance setting for performance-timing
  debug logging** (off by default): per-cluster and per-type call wall
  time, bytes, pool occupancy, cycle total, push batch timings.
- **Still open:** Cloud Proxy collector heap (needs an SSH credential);
  UI rendering of stitched instanced keys (Build 1 shows it); Suite API
  ingest at Build 2 volume; the target vCenter's version for the JSON
  transport.
