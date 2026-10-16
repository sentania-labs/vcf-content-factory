# Compliance adapter cycle durations, all four instances

Date: 2026-10-16, run 11:55 AM to 12:10 PM Central. Read-only (GET only), profiles `prod`,
`devel`, `devel_9_1`, `devel_8_18`, via `vcfcf_common` `VCFOpsClient.from_env(profile=...)`.
Purpose: judge a proposed per-cycle time budget of 95% of the collection interval
(285 s at the 300 s default) before it ships. Windows are the 24 hours ending 12:02 PM today
(10-15 12:02 PM to 10-16 12:02 PM) unless stated.

## Bottom line

Every account on every instance averages 8 to 20 s per cycle against a 300 s interval (prod: 60
minute interval), and the 24 hour maximum is 42.5 s (devel). No cycle in the 24 hour window
comes within 6x of 285 s. One cycle in the 7 day history did exceed the interval: devel, 10-13
10:59 PM, 318 to 328 s on all three accounts at once, before 0.0.0.95 (the next sample slipped,
see below). Prod runs a 60 minute interval, not 5 minutes, so its 95% budget would be 3420 s.

## Sources

1. A pak-published per-cycle duration: NONE. describe.xml and docs/data-reference.md have no
   cycle_seconds or CycleStats key. `Summary|last_scan_timestamp` is a property (latest value
   only, no history) on ComplianceWorld. Cycle duration is only in the adapter log ("collection
   complete" line, ComplianceAdapter.java line 1143, and the build 86 `finally` timing), which
   has no no-SSH read path (see 2026-10-16-compliance-52-30-31-recon.md section c). Not read.
2. USED, primary: the platform's own per-adapter-instance metric
   `Instance Attributes|elapsed_collect_time` (milliseconds) on each `vcfcf_compliance` adapter
   instance resource. It is not a pak key; VCF Operations writes it for every adapter instance.
   Its sample timestamp is the end of the cycle. I found it with
   `GET /api/resources/{adapterInstanceId}/stats/latest`.
3. USED, cross-check: the spread of the collection timestamps of the objects pushed in one
   cycle (second source in the brief) against elapsed_collect_time. Agreement is within a second
   or two (table below), so elapsed_collect_time is the whole collect() including the pushes.
4. Adapter log: not reachable without SSH. Not used.

## Queries

```
GET /api/adapters?adapterKindKey=vcfcf_compliance
    -> per account: id, monitoringInterval (MINUTES: 5 or 60), collectorId, lastCollected
GET /api/solutions            -> pak version (name "VCF Content Factory Compliance")
GET /api/resources/{adapterInstanceId}/stats?statKey=Instance Attributes|elapsed_collect_time&begin=<ms>&end=<ms>
    (no rollUpType: with rollUpType=NONE the call returns an empty list; the default returns the
     raw one-per-cycle points, 288 per 24 h at 5 min, 24 at 60 min)
GET /api/resources?adapterKind=VMWARE&resourceKind=VMwareAdapter Instance  -> vCenter objects
GET /api/resources/{vCenterId}/stats?statKey=VCF-CF Compliance|Rollup|incomplete
GET /api/resources/{vCenterId}/stats?statKey=VCF-CF Compliance|Rollup|All|scored
GET /api/resources/stats/latest?resourceId=...&statKey=VCF-CF Compliance|has_unreadable
    (build 95 key; prod, build 94, has no such key so `VCF-CF Compliance|score` was used)
```
Scripts are in the session scratchpad (`.../scratchpad/cyc/`), not the repo.

## Builds and intervals

| Instance | VCF Ops | Pak | Accounts | Interval | Collector |
|---|---|---|---|---|---|
| prod | 9.1.1.0 | **1.0.0.94** (release pak, `GET /api/solutions`; it predates builds 95 and 96, so no has_unreadable key and no cycle time budget) | 3 (mgmt, wld01, wld02) | **60 minutes** (`monitoringInterval` 60) | collector 4 |
| devel | 9.0.2.0 | 0.0.0.95 | 3 | 5 min | collector 1 |
| devel_9_1 | 9.1.1.0 | 0.0.0.95 | 3 (compliance-mgmt, -wld01, -wld02) | 5 min | collector 2 |
| devel_8_18 | 8.18.7 | 0.0.0.95 | 1 (compliance-mgmt) | 5 min | collector 2 |

`monitoringInterval` is the platform's configured collection interval for the adapter instance.
(INFERRED that it is in minutes: prod's `lastCollected` values run exactly 60 minutes apart and
devel's are 5 minutes apart.)

## Results, last 24 hours (seconds, from elapsed_collect_time)

| Instance | Account | Interval | n | Min | Median | p95 | p99 | Max (when) | Cycles >= 285 s (95%) | Largest gap between samples |
|---|---|---|---|---|---|---|---|---|---|---|
| prod | mgmt | 3600 | 24 | 12.0 | 13.3 | 15.3 | 15.5 | 15.5 (10-15 12:15 PM) | 0 | 3608 |
| prod | wld01 | 3600 | 24 | 11.4 | 12.8 | 14.5 | 15.0 | 15.0 (10-15 2:15 PM) | 0 | 3608 |
| prod | wld02 | 3600 | 24 | 9.9 | 11.3 | 12.5 | 13.3 | 13.3 (10-15 12:15 PM) | 0 | 3608 |
| devel | mgmt | 300 | 288 | 8.5 | 17.1 | 24.0 | 30.0 | 42.5 (10-16 3:24 AM) | 0 | 322 |
| devel | wld01 | 300 | 288 | 8.6 | 17.1 | 24.2 | 31.4 | 42.5 (10-16 3:24 AM) | 0 | 322 |
| devel | wld02 | 300 | 288 | 7.4 | 15.7 | 22.7 | 29.8 | 41.4 (10-16 3:24 AM) | 0 | 322 |
| devel_9_1 | mgmt | 300 | 288 | 17.1 | 19.9 | 22.1 | 23.1 | 25.4 (10-15 2:22 PM) | 0 | 307 |
| devel_9_1 | wld01 | 300 | 288 | 16.7 | 19.7 | 21.8 | 23.2 | 24.9 (10-15 2:22 PM) | 0 | 307 |
| devel_9_1 | wld02 | 300 | 288 | 15.0 | 17.7 | 19.9 | 21.0 | 23.2 (10-15 2:22 PM) | 0 | 307 |
| devel_8_18 | mgmt | 300 | 268 (history starts 10-15 1:41 PM) | 0.0 (first cycle, 2 s) | 8.5 | 9.9 | 12.3 | 13.7 (10-16 12:02 AM) | 0 | 312 |

- Largest gap is the sample-to-sample spacing; any gap at or under about 1.1 x interval means no
  cycle was skipped. No gap in the 24 hour window exceeds 1.5 x interval on any account.
- `Rollup|incomplete` = 1 in 0 of 288 samples on each devel and devel_9_1 vCenter, 0 of 24 on each
  prod vCenter, 0 of 267 on devel_8_18 (the wld01 and wld02 vCenter objects on 8.18 returned no
  series, consistent with the one account covering only mgmt; not otherwise checked). No cycle ended early.
- The three accounts of one instance run at the same moment on the same collector, so their
  times move together (devel 3:24 AM spike hit all three: 42.5, 42.5, 41.4 s). That spike looks
  like collector or vCenter load at that minute (INFERRED; no log).

## Cross-check: spread of object timestamps within one cycle

| Instance | Cycle ending | Objects with the key | First to last timestamp | Platform elapsed_collect_time for the same cycle |
|---|---|---|---|---|
| devel_8_18 (1 account) | 11:57:45 AM | 63 | 7.7 s (11:57:37 to 11:57:45) | 8.9 s |
| devel_9_1 (3 accounts, same minute) | 12:02:52 to 12:03:11 PM | 180 | 19.0 s | about 17 to 20 s |
| devel (3 accounts) | 11:59:51 AM to 12:00:03 PM | 180 | 12.6 s | about 15 s |
| prod (3 accounts, build 94) | 11:15:52 to 11:16:04 AM | 178 | 11.5 s | 12.4 to 13.4 s |

Pushes are spread across the whole cycle (the first object lands about a second after the cycle
starts), so the spread is a faithful independent measure here, not a short tail. Both methods
agree.

## Longer view, 7 days (10-09 12:03 PM to 10-16 12:03 PM)

- prod: n=169 per account, max 40.4 s (wld01), 36.8 s (mgmt), 32.2 s (wld02), all at 10-15
  9:46 AM (a post-restart or maintenance cycle; gap-minimum 218 s shows two off-schedule
  collections). Nothing near 3420 s.
- devel_9_1: max 29.5 s (wld01, 10-15 9:57 AM); history is shorter (0.0.0.94 first collected 10-14
  2:45 PM). One sample gap of 836/761/614 s (wld01/wld02/mgmt) in the window; its date was not printed, assumed to be the 10-14 5:21 to 5:35 PM 0.94 to 0.95 upgrade (INFERRED).
- devel: cycles at or above 60 s (the last one is 10-14 1:28 PM, 61 s, mgmt only):
  - 10-12 2:47 AM 136 to 145 s, 10-12 3:51 PM 182 to 190 s, 10-12 5:10 PM 129 to 132 s
  - 10-13 11:35 AM 244 to 250 s, **10-13 10:59 PM 318 / 328 / 320 s** (the only cycles >= 300 s;
    also >= 285 s), plus smaller ones at 10-13 4:51 PM, 6:54 PM, 10:45 PM, 11:56 PM and
    10-14 2:02 AM, 8:48 AM, 8:54 AM, 11:12 AM (63 to 112 s).
  - Each long cycle is followed by a longer sample gap: the 328 s cycle at 10:59:29 PM has a 613 s
    gap before it (previous sample 10:49:16 PM). The platform started the next cycle late rather
    than running two at once (INFERRED from the single, regularly spaced series per account; no
    log). So "overlap" in the strict sense of two concurrent cycles on one account is not
    evidenced anywhere; the observed effect of exceeding the interval is a skipped or delayed
    cycle.
  - devel upgraded 0.94 to 0.95 on 10-15 1:36 to 1:40 PM (2026-10-15-devel-inventory-sync.md).
    Since then (the 24 hour table above) the max is 42.5 s. The 7 day long-cycle events are on
    earlier builds (0.0.0.94 or older), when devel was under active development load; the cause
    is not known. Since 10-14 12:00 PM the devel max is 53.9 to 60.5 s.
  - devel gap 10-14 11:16 AM to 1:28 PM (7889 s) is an outage window with no samples.

## What this says about a 95% budget

- Interval 300 s: budget 285 s. Today's worst 24 hour cycle (42.5 s devel) is 15% of it; the
  worst 7 day post-0.95 devel cycle is about 60 s (21%). Would have clipped: only the devel
  10-13 10:59 PM event (318 to 328 s), 0.0.0.94 or earlier, and that same cycle already
  exceeded the whole interval, which the current builds' existing 80% (240 s) limit would also
  have clipped (build 96 in the repo, not yet deployed to any instance here).
- Prod interval is 60 minutes, so 95% is 3420 s against a worst observed 40.4 s in 7 days. A
  budget scaled from the interval is not binding on prod; it matters only if a long-interval
  account were also to carry a huge inventory.
- Scale caveat: these labs hold 180 objects per instance (3 vCenters, 63 to 183 compliance
  objects, 178 scored). Cycle time scales with object count and with any slow host or esxcli call
  (each stuck call can add 30 s connect plus 120 s read per the overview.md note). A production
  customer fleet with thousands of VMs would not be bounded by these numbers.

## Confidence

| Item | Confidence |
|---|---|
| Configured interval (5 or 60 minutes) | High (`GET /api/adapters`; prod 60 min cross-checked by spacing of samples) |
| Typical (median) and max over 24 hours | High that the platform-measured value is what it says; the metric is the platform's, not the pak's, and agrees with the object timestamp spread within 1 to 3 s on four instances |
| Prod build 1.0.0.94 | High (`GET /api/solutions`) |
| Overlap (concurrent cycles) = none | Medium: no cycle in 24 h approaches the interval and no sample gap is below 0.9 x interval, so none overlapped; strict concurrency in the 7 day devel event is INFERRED to be a delayed start, not proven (no log) |
| Cause of the devel 10-13 spikes | Unknown |
| Per-cycle breakdown (which phase is slow) | Not measured; only in the adapter log (build 95 CycleMetrics summary line) |

Nothing was written to any instance or the repo apart from this file.
