# Prod vSphere World stale since 2026-10-17: the Container adapter instance is stuck (2026-11-11)

Read-only diagnosis, with one remediation performed afterwards (monitoring stop
and start, PUT; see the last section), on `prod` (VCF Operations 9.1.1.0, two analytics nodes
`vcf-lab-operations01` (.42, collector 5) and `vcf-lab-operations02` (.43,
collector 6), two Cloud Proxies (collectors 3 and 4)). The diagnosis used Suite API GETs only;
`/internal/*` calls carry `X-Ops-API-use-unsupported: true` and are
unsupported. No SSH (port 22 refused), no Admin UI. Times are America/Chicago
unless marked UTC.

## Finding

The vSphere World is not the fault. It is owned by the **Container adapter
instance** (`434146c8-2aaa-4810-b7dc-de7e8ee39175`, kind `Container`,
`collectorId 6`, operations02), and that adapter instance has not run since
**2026-10-17 03:54:51**. Its own resource state is **`STARTING`** (every other
object on the cluster that is not stopped reads `STARTED`; the cluster's
`Resources|CountByStates|StateStarting` is 1, and this is it). `GET
/api/adapters/434146c8...` has no `lastCollected`, `numberOfMetricsCollected` or
`numberOfResourcesCollected`; on devel_9_1 the same record carries all three and
is current.

Every object checked of those this adapter instance owns (39 checked of 93 on prod: vSphere World, Universe,
VCF World, vSAN World, NSX World, Supervisor World, the MPB worlds, every
`Environment` custom group including the factory `[VCF Content Factory]` groups,
PhysicalDatacenter, Organization, licensing objects) has its newest stat at
exactly 10-17 03:54:51 and status `NO_DATA_RECEIVING`. The rollups and the
super metrics on these objects are written in the Container adapter's cycle, so
they stopped together (the World's newest super metric sample is 03:53:22).

Objects owned by the vCenter adapters are unaffected: Datacenters, clusters,
hosts, VMs and the vCenter adapter instance objects all have stats and super
metric samples from the current minute. The World still parents the four
vCenter adapter instance objects, and there is one vSphere World and one
Universe on the instance.

## What happened on 2026-10-17

| Time | Evidence |
|---|---|
| 03:48 to 03:53 | alerts on NSX objects cancelled and re-raised as a batch |
| 03:54:51 to 03:54:53 | last samples from four adapter instances on collector 6: Container, MPB `beba8bf9...` (`34979f7e...`), VCF Operations API (operations02) (`5bb1a304...`), VCF Operations Adapter (operations02) (`40817391...`); "Adapter instance is not receiving data" raised on all four |
| 03:59 | cluster `NumberOfOnlineCollectors` 4 to 2, `NumberOfDataReceivingAIs` 51 to 22 |
| 04:04 | online collectors back to 4 |
| 04:19 | Infrastructure Health, Infrastructure Management and Diagnostics adapter instances on collector 6 resume (24 minute gap). Instances on collectors 3, 4 and 5 show no gap over 20 minutes |
| afterwards | Container, MPB `beba8bf9` and VCF Operations Adapter (operations02) never resume |

Later: operations01's COLLECTOR service restarted 10-24 13:38. operations02's
whole service set (COLLECTOR, ANALYTICS, API, UI, CASA) restarted
**2026-10-25 10:57** (`/api/deployment/node/services/info` queried against
each node's own FQDN; the `vcf-lab-operations` name round-robins .42 and .43).
After that restart, VCF Operations API (operations02) resumed at 11:01, but the
other three did not. So restarting the collector JVM on operations02 does not
clear this state. The cause is probably the controller-side `STARTING` state of
the adapter instance, not the collector process. That part is INFERRED.

Earlier, on 10-15 09:09 to 09:44, every adapter instance on every collector had
a gap (CASA, API and ANALYTICS on operations01 restarted 09:20 to 09:25). All of
them came back, Container included, and it ran normally for two days after.
This rules out the 10-15 restart as the direct cause.

The repo shows no prod pak work on 10-16 or 10-17 (the build 94 install was
10-14 09:01; `git log 2026-10-10..2026-10-20`).

## Hypotheses

| Hypothesis | Verdict | Evidence |
|---|---|---|
| World orphaned by a deleted or replaced vCenter adapter instance | OUT | The World is owned by the Container adapter instance, not a vCenter one. It still parents all four vCenter adapter instance objects. Creation time 2025-10-01 |
| Object stopped or not collecting | IN, one level up | The World itself is `STARTED`. Its owning adapter instance is stuck `STARTING` |
| Duplicate World takes the data | OUT | One vSphere World and one Universe exist |
| Policy excludes collection | OUT | All 39 Container-owned objects checked, across more than 20 kinds, stopped in the same second. Container-native stats stopped too. Other kinds compute super metrics |
| Maintenance | OUT | `StateMaintained` and `StateMaintainedManual` are 0 cluster-wide. The World reads `STARTED` |
| Platform upgrade changed how the World is populated | OUT as a direct cause | The Container ran for two days after the 10-15 restart. Same 9.1.1 build on devel_9_1, which is healthy |
| Cluster-level analytics or collector trouble | IN as the trigger | operations02's collector dropped for 24 minutes. Three adapter instances on it did not come back |

## Not visible from the API

- Why three instances on collector 6 did not restart. Read on operations02,
  `/storage/log/vcops/log/collector.log` and
  `/storage/log/vcops/log/adapters/ContainerAdapter/` (plus the
  `vCenterOperationsAdapter` and MPB folders) for 2026-10-17 08:45 to 09:30 UTC
  and 2026-10-25 15:57 UTC onward. Look for start or describe failures for
  `434146c8`. On operations01, read `analytics-*.log` and
  `collector-wrapper.log` for the same window: GemFire member departure, and the
  controller's "start adapter instance" task to collector 6.
- In the Admin UI, cluster status: operations02's role (it has no LOCATOR
  service, which makes it a data node) and whether it reports as fully online.
- What triggered the 10-17 03:54 outage on operations02. Note that the node
  clock displays UTC while operations01 displays CST. That is display only, but
  check NTP (the cluster raised "NTP Servers are not reachable" on 10-23 and
  11-09).

## Least invasive fix (performed 2026-11-11, worked)

Stop and start monitoring on the Container adapter instance only:
`PUT /api/adapters/434146c8-2aaa-4810-b7dc-de7e8ee39175/monitoringstate/stop`,
then `.../start`. Repeat for `40817391...` and `34979f7e...` if they stay dead.
This resets the controller's state for that instance without touching the
nodes. If the API refuses because Container is a system adapter, the next step
is taking operations02 offline and bringing it back online in the Admin UI
(owner approval and a snapshot first; that is a node outage on the cluster).
A collector-only restart on operations02 is already disproven by 10-25.

Outcome: all six PUTs (a stop and a start on each of the three instances) returned HTTP 200 with an empty body, so the Container
adapter is not refused as a system adapter. Container was stopped at 22:35:00
UTC and started about 40 seconds later; it reached `STARTED` /
`DATA_RECEIVING`, the vSphere World wrote a sample at 22:35:43 UTC and has
written on the five-minute cycle since, and World-scoped super metrics
computed within two cycles. `40817391...` and `34979f7e...` showed `STARTED` /
`NO_DATA_RECEIVING` rather than `STARTING`, with a newest stat from that
morning, so they may be a different or intermittent failure; both got the same
stop and start and wrote fresh stats within a minute. Their steady state after
several cycles was not re-checked. Why the Container instance stuck on 10-17 is
still unknown.
