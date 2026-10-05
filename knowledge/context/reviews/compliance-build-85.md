# SDK adapter review: compliance build 85

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-02 (local, America/Chicago)
- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/environment-computed-metrics`, base `main` at `0a7d539`, uncommitted working tree)
- **Artifact reviewed:** `dist/vcfcf_sdk_compliance.0.0.0.85.pak` (built 15:51 CDT), sha256 `9b0d22a9607a2e8f5f53c7ca707065370869aba518e4e9ef1296d463a7209fa7` (confirmed). Reference: `dist/vcfcf_sdk_compliance.0.0.0.84.pak` (the build on devel).
- **Prior pass:** `knowledge/context/reviews/compliance-build-84.md` (APPROVE, 3 WARNING / 3 NIT)
- **Verdict:** APPROVE (0 BLOCKING / 7 WARNING / 5 NIT)
- **Fit for a devel install: YES.** The esxcli fix is correct and is in the shipped bytecode, no other cache can serve a stale pass, and nothing found would make the devel test misleading. Two things to watch on devel are new: alert flapping and whether the three existing instances actually move from 60 to 5 minutes (checklist below).

## Bottom line

The stale-pass bug is real and fixed. Before build 85 the esxcli result cache lived as long as the vCenter SOAP session, and the per-cycle keepalive keeps that session alive indefinitely, so a host's first esxcli answer was served until a collector restart. Build 85 empties both esxcli caches at the top of every cycle, right after `ensureConnected()`, before any read. I walked every other piece of state in the adapter and found nothing else that carries a control value across cycles.

The interval change is where the risk now sits, and it is operational, not correctness. At 5 minutes with `waitCycle=1` / `cancelCycle=1`, a single unreadable cycle cancels a failing control's alert and the next good cycle raises a new one (W1). A host whose esxcli calls time out now costs up to 7 x 120 s every cycle instead of once per session (W2). The 5 minute value also contradicts the drafted bulk-collection design, which says to pick the interval after measuring (W3).

One undisclosed delta: the framework jar changed between 84 and 85 (the framework review's N7 to N9 fixes). It is safe, but the brief and the CHANGELOG do not mention it, and framework-reviewer has not seen it (W4).

## Independent verification

| Check | Result |
|---|---|
| Pak checksum | `9b0d22a9...a7209fa7`, matches the brief |
| `validate-sdk content/sdk-adapters/compliance` | OK (javac 19 files, the existing `-source 11` options warning only) |
| `ci/run_java_tests.sh` | 12 Java suites pass, including `EnvironmentKeyContractTest` ("4 computed keys, 5 metric references") and `EsxcliCycleCacheTest` ("5 fetches across 4 cycles"); alert generator 14 tests OK ("up to date"); dashboard alert lists 3 tests OK. Both new tests are in the runner's loop, and the runner is `set -euo pipefail`. |
| `build-sdk` into scratchpad | reproduces `vcfcf_sdk_compliance.0.0.0.85.pak`. Compared with the author's pak: adapter jar classes, `describe.xml`, `resources.properties`, views and framework jar identical; `overview.packed` differs only in zip timestamps (contents identical). The adapter repo working tree was unchanged by the build (porcelain hash the same before and after). |
| `pak-compare` 85 vs 84 (author's pak and mine) | gate PASS, 0 BLOCKING / 0 WARNING / 0 INFO. pak-compare does not report the `monitoringInterval` change, so it is not evidence for it; checked directly. |
| Built `describe.xml` | identical to source; `monitoringInterval="5"` at line 22 on the `vcfcf_compliance` kind. `version.txt` `Implementation-Version=0.85`, manifest `0.0.0.85`. |
| Shipped bytecode, call order | `javap` of `ComplianceAdapter.collectWorld`: `System.currentTimeMillis`, then `VSphereClient.ensureConnected`, then `VSphereClient.beginCycle`, then the conf dir and selector. `VSphereClient.beginCycle` reads `esxcli` once into a local and calls `EsxcliSoapClient.beginCycle` when non-null. |
| Adapter classes 84 vs 85 | changed: `ComplianceAdapter` (and its inner classes, recompiled), `EsxcliSoapClient` (+ `$CommandFetcher`, `$ParsedResult` now package-visible), `VSphereClient` (+ inner classes, recompiled). Nothing else. No test class is in the jar. |
| Framework jar 84 vs 85 | **changed**: `dac4b36d...` to `cad29420...`. Only `SuiteApiStitchClient.class` differs: new `loggable(String, int)`, used by `failureSummary` (framework review N7). The pak's jar equals `adapter_runtime/vcfcf-adapter-base.jar` and a fresh compile of the current framework source (`-source 11 -target 11 -proc:none`, SDK jar only), class for class. `SuiteApiStitchRelationshipTest` with `adapter_runtime/lib/*`: 145/145 (was 130 at build 84; the new ones are the N7 cap and the N8 interrupt tests). See W4. |
| "Hourly" text | none left in the source tree, the docs, the built pak or `overview.packed` (searched for hour, hourly, 60 min, two hours). README, REFERENCE.md, `REFERENCE.generated.md` and recommendation 105 say 5 minutes. No cycle-count-based timing constant exists that would scale with the interval. |
| `defect-gate --pak compliance` | "no open blocking defects affecting compliance" |

## The attack: anything else that outlives a cycle

Every field and cache in the adapter path, and whether it can carry a control value from one cycle into the next.

| State | Lifetime | Can it serve a stale pass? |
|---|---|---|
| `EsxcliSoapClient.resultCache`, `executerByHost` | per cycle since build 85 (`EsxcliSoapClient.java:167`) | No. Cleared before any read. A mid-cycle reconnect builds a new client with empty caches, which can only make reads fresher. |
| `VamiApiClient` path cache and session | one client per `evaluateVamiForVCenter` call, closed in `finally` (`ComplianceAdapter.java` around 1600 to 1630) | No. New object every cycle. |
| `VCenterApiClient` | Test Connection and logout only | No data cache. |
| `VSphereClient` `aboutVersion`, `aboutInstanceUuid`, `aboutFullName` | life of the SOAP session | Not a control value. Drives benchmark choice and stitch scoping. A vCenter upgrade restarts vpxd, which kills the session and forces a reconnect, so this cannot outlive a version change in practice. |
| `VSphereClient` `lastReasons`, `lastFault`, `readFailure` | reset per `readVimProperties` call and per control | Diagnostics only. |
| `VSphereClient.warnedEsxciFields` | life of the adapter instance | Log de-duplication only. |
| Host advanced settings, VM `extraConfig`, vCenter settings, connection state | read live per object per cycle, no cache; build 77 throws on a failed read | No. |
| `hostVersions` | local to `collectWorld` | No. |
| `ComplianceStitcher` indexes | each `load*` puts fresh maps *before* fetching (`ComplianceStitcher.java` `loadResourcesForKind`, `loadVCenterAdapterInstanceByIdentity` clears `vcByHost` / `vcByVcUuid` first) | No. A failed load leaves that kind empty, never last cycle's index. `owningVcUuid` is set every cycle. |
| `BenchmarkLoader` bundled profiles | cached per conf dir and appliance flag | No for bundled CSVs (fixed within an install). |
| `BenchmarkLoader` custom profile | cached per path for the life of the instance | **Yes, from config, not reads.** An operator who edits the custom CSV in place keeps being scored against the old expected values until an instance edit or collector restart. Outside this delta and independent of the interval: W7. |
| `LastBenchmarkMemory` | instance life, trimmed to inventory | Holds a profile name for the B2 fallback, never a value. |
| `cycleReasons`, `pendingCleanup`, `profilesByName`, `cycleConfDir`, `ComplianceRollup`, `CycleStats` | replaced or cleared at the top of each cycle | No. |
| Framework `MetricDataCache` | per cycle, flushed at end | Only the ComplianceWorld timestamp goes through it; compliance data is pushed through the Suite API. |
| `SuiteApiStitchClient` bearer token | until 401 | Auth only. |

**Does `beginCycle()` run on every path into a cycle?** Yes. It is the second statement of `collectWorld`, which is the only collect body. After a reconnect inside `ensureConnected()`, `connect()` has already built a new, empty client, and `beginCycle()` clears it again (harmless). When `ensureConnected()` throws, the cycle aborts before any read, and the old client is already gone: the keepalive-failure path calls `disconnect()` (which nulls `esxcli`) before `connect()`, and the first-connect path is only reachable when `esxcli` is already null. Nothing outside `collectWorld` reads esxcli; Test Connection, if it ever touched the shared client, would be wiped at the next cycle start.

**Can the test fetch hook be reached or left set in production?** No. `EsxcliSoapClient(CommandFetcher)` (`EsxcliSoapClient.java:148`) is package-private on a package-private final class; the only caller is the test, and the only production construction is `VSphereClient.java:200` with the three-argument constructor, which sets `fetcher = this::fetchLive`. `fetcher` is `final`, so it cannot be swapped after construction. Test classes are not in the shipped jar.

**Does the cache still dedupe within a cycle?** Yes. The test asserts one fetch for two recipes on the same host and command, and the no-cache mutation fails it.

**Can two cycles overlap?** Not for one adapter instance, on the evidence we have. `knowledge/context/cleanroom-spec/spec/01-adapter-lifecycle.md` (Pass 21 bytecode, Pass 23 field logs on devel) records a per-instance `Semaphore(1)` in `AdapterBase`: one instance's cycles were strictly sequential while different instances overlapped freely. The framework's `onCollect` takes no lock of its own and does not need one. Each of the three devel instances has its own `VSphereClient` and `EsxcliSoapClient`, and no adapter class holds mutable static state, so cross-instance overlap shares nothing. `readCommandResult`, `getExecuter` and `beginCycle` are all `synchronized` on the client anyway. What I **cannot** establish from the repo: what the scheduler does when a cycle runs past its interval. Whether the next tick waits on the semaphore, is skipped, or is queued is not recorded anywhere I can find. The devel checklist covers how to see it.

**At 5 minutes, what if a cycle takes longer than the interval?** On devel today, probably nothing: the bulk-collection design records about 20 s per cycle for 164 scored objects (one observation), and a June recon measured 74.7 s. The exposure is a slow host, not inventory size (W2), and large estates (W3). Because of the semaphore a long cycle cannot cause double pushes or interleaved caches. The likely effect is later or fewer cycles, so data and alerts go stale on a slower cadence than the docs promise.

**Does the cycle timer measure what it says?** Mostly. It runs from the first line of `collectWorld` (before `ensureConnected`, so a re-login counts) to the summary line. It leaves out the framework's collect-path discovery before `collectWorld` and the metric-cache flush after it, both small. It is only logged when the cycle completes, so the slowest cycles (timeouts that end in an exception) report no duration. It uses wall-clock time. N2.

## Mutation tests

Each mutation was applied to a scratch copy, then the one test was compiled and run alone.

**`EsxcliCycleCacheTest`**

| Mutation | Should fail? | Result |
|---|---|---|
| Baseline | no | pass |
| M1 `beginCycle` does not clear `resultCache` | yes | **fails** ("cycle 2 re-reads and sees the drift") |
| M2 `beginCycle` does not clear `executerByHost` | yes | **passes** (N1) |
| M3 `beginCycle` clears failures only | yes | **fails** (drift) |
| M4 `beginCycle` clears successes only | yes | **fails** ("cycle 4 reads the host again") |
| M5 failures not cached | yes | **fails** ("not retried within the cycle") |
| M6 cache never hit | yes | **fails** ("fetched once per cycle") |
| M7 cache key ignores host | yes | **fails** ("another host is its own fetch") |
| M8 cache key ignores command | yes | **passes** (N1) |
| M9 `VSphereClient.beginCycle` body emptied | yes | **passes** (N1; the test Javadoc says the delegation is not exercised) |
| M10 a fetch exception becomes an empty struct | yes | **fails** ("cycle 3 read failed") |

The call in `ComplianceAdapter.collectWorld` is not testable in this runner (SDK dependency). I confirmed it in the shipped bytecode instead.

**`EnvironmentKeyContractTest`** (build 84 N2 closure)

| Mutation | Should fail? | Result |
|---|---|---|
| `scored` expression replaced by constant `0` | yes | **fails** |
| `scored` reads `All|non_compliant` | yes | **fails** |
| `no_benchmark` reads `Host|` | yes | **fails** |
| `avg_score` divides `scored / score_sum` | yes | **fails** |
| `avg_score` multiplies | yes | **fails** |
| `avg_score` drops the divisor (sum of `score_sum`) | yes | **fails** |
| `avg_score` gains `+ 0` | yes | **fails** |
| `sum` to `avg` / `max` | yes | **fails** |
| Two ComputedMetric keys swapped | yes | **fails** |
| `resourcekind` lowercased | yes | **fails** |
| Extra `depth=2,` inside a reference | arguably | **passes** (N3) |
| Space before `}` | arguably | **passes** (N3) |

Every case build 84 N2 listed now fails. N2 is closed.

## Build 84 findings, closure check

| Build 84 finding | Status in build 85 | Evidence |
|---|---|---|
| W1 docs parity | **Open, deferred to phase 3 by design** | `docs/overview.md:50` ("Adapter liveness anchor"), `docs/overview.md:52` and `docs/data-reference.md:122` ("carries only") unchanged. Carried as W5. |
| W2 release ordering | **Open, no code needed** | `.github/workflows/build-pak-on-tag.yml:35` still `sdk-buildkit-v1`. Carried as W6. |
| W3 framework change not reviewed | **Superseded** | The framework review's third pass covered `logFailure` / `isExpectedFailure` / `failureSummary` (APPROVE, N7 to N9). The N7 to N9 fixes landed after it and ship in this pak: W4. |
| N1 `NO_WORLD` wording | **Closed** | `ComplianceAdapter.java:585` onward: "no single ComplianceWorld resource was found or the lookup could not be queried (see the preceding SuiteApiStitchClient findSingletonResourceId WARN for the cause; zero matches is normal only on the first cycle)". |
| N2 contract test pinning | **Closed** | Mutation table above. |
| N3 zero-scored tile guard | **Open, deferred to phase 3** | No consumer yet. Carried as N5. |

## Findings

### BLOCKING

None.

### WARNING

**W1. At 5 minutes, one unreadable cycle cancels a failing control's alert and the next cycle raises a new one.** Authority: review dimension 1 and `knowledge/lessons/unreadable-is-not-compliant.md` (the read path is right; this is what the alerting does with it), and the brief's flapping question. `ComplianceDecisions.complianceStats` (`ComplianceDecisions.java` around line 130) pushes `COMPLIANT_NOT_EVALUATED`, not `0`, for an unreadable control, and every per-control symptom is `Compliant = 0` with `waitCycle="1" cancelCycle="1"` (all 294 symptoms). So a control that is failing and then unreadable for one cycle (an esxcli fault, a slow host, a host that flaps) cancels its alert, and when it reads again it raises a *new* alert with a new start time. In the same cycle the host's collection alerts (`unreadable_count > 0`, `collection_failed = 1`) raise, and the score symptoms can move because unreadable counts as failing. At 60 minutes this happened at most hourly. At 5 minutes it can happen 12 times an hour. Build 85 also makes it more visible: an esxcli failure used to be frozen for the life of the session, and now it shows up one cycle at a time, which is the truth but noisier. Not a false pass in either direction, and not a devel blocker. **Fix (after devel shows the rate):** `cancelCycle` 2 or 3 on the per-control and score symptoms so one unreadable cycle does not close a real finding; consider `waitCycle` 2 on the collection-health symptoms. The generator is `scripts/generate_compliance_alerts.py`.

**W2. A host whose esxcli calls time out now costs up to about 14 minutes every cycle.** Authority: review dimensions 7 and 8; the brief's long-cycle question. `EsxcliSoapClient.getExecuter` (`EsxcliSoapClient.java:317`) caches only a successful executer lookup, and `readCommandResult` caches a failure per (host, command), so each distinct command on a hung host pays its own `RetrieveManagedMethodExecuter` at a 120 s read timeout (`EsxcliSoapClient.java:505`). SCG 8.0 has 7 distinct esxcli commands (9.0 and 9.1 have 6), so the cost is up to 7 x 120 s per hung host. Before build 85 it was paid once per session, because the failure stayed cached. Now it is paid every cycle, against a 5 minute interval. The connection-state guard only skips hosts vCenter already reports as disconnected or not responding, not a connected host that is slow to answer. **Fix:** within a cycle, after the first timeout or connect failure for a host, fail that host's remaining esxcli commands at once (per-host negative entry, cleared by `beginCycle`), keeping the reason so the controls stay UNREADABLE with a cause.

**W3. The 5 minute interval was set before the measurement the drafted bulk-collection design asks for, and nobody knows yet whether existing instances pick it up.** Authority: review dimension 9 (minimal diff, design intent) and dimension 11 (docs must say what the pak does). `knowledge/designs/sdk-adapters/compliance-bulk-collection.md` §4 says to decide `monitoringInterval` "from build A through D's measured numbers, not before", with a working assumption of 15 minutes. Build 85 ships 5 now, with no measured per-phase numbers (build A) and no recorded decision; the CHANGELOG reason is that ComputedMetrics land one cycle late and the other paks use 5. On devel's 164 objects this is fine. At the design's own scale example (5,000 VMs, 200 hosts, roughly 35,000 VM reads and 10,400 pushes per cycle, all per object), 5 minutes is unproven. Second, `monitoringInterval` in `describe.xml` is the default for the adapter kind, and recon has read a per-instance `monitoringInterval 60` on devel's three instances. Whether a pak upgrade moves existing instances to 5 is not established, and `docs/installing.md:103` already notes that existing instances keep their stored profile choice on upgrade. If the interval behaves the same way, README "collects every 5 minutes" is wrong for every upgrader. **Fix:** before any `v*` tag, record Scott's interval decision in the bulk-collection design (or move this change into its build E), confirm the upgrade behavior on devel (checklist item 1), and if instances keep 60, add an upgrade note to README and `docs/installing.md`. **Registration candidate** (RULE-012) if a tag is proposed with neither done.

**W4. The framework jar changed between 84 and 85 without disclosure and has not been through framework-reviewer.** Authority: RULE-013 (CLAUDE.md delegation rule 9); review dimension 9. `SuiteApiStitchClient.java` was last modified at 09:51:50 CDT and the jar rebuilt at 09:52:18. The framework review (`knowledge/context/reviews/framework/adapter-framework-stitch-relationship-add-2026-10-02.md`) was last written at 09:51:05, and its third pass lists N7 to N9 as open. The code has the N7 sanitizing cap (`FAILURE_MESSAGE_MAX = 200`, `loggable(msg, ...)` in `failureSummary`), the N8 interrupt tests and the N9 rewrap (no line over 110 characters). Neither the brief nor the CHANGELOG build 85 entry mentions a framework change. For this pak I checked the change myself: sanitize and cap only, no new throw (`loggable` is null-safe and `msg` is null-checked), jar equals a fresh compile of current source, 145/145 framework tests. It does not hold up devel. **Fix:** a fourth framework-reviewer pass on the N7 to N9 diff before the factory PR; add one clause to the CHANGELOG build 85 entry ("pak carries the framework jar with the framework review N7 to N9 fixes").

**W5. Docs parity, carried from build 84 W1 (phase 3 by design).** `docs/overview.md:50`, `docs/overview.md:52` and `docs/data-reference.md:122` still say ComplianceWorld is a liveness anchor that "carries only" `last_scan_timestamp`, and the ComplianceWorld to VMwareAdapter Instance edge is in no doc surface. **Fix:** the phase 3 docs round, before any `v*` tag. Registration candidate if a tag is proposed first.

**W6. Release ordering, carried from build 84 W2.** A `v*` tag today fails CI at compile time (published buildkit lacks `addChild` / `findSingletonResourceId`). Loud, not silent. **Fix:** factory PR merged, `sdk-buildkit-v1.0.11` published and `v1` moved, then the adapter tag.

**W7. An edited custom profile CSV is not reread until an instance edit or collector restart (outside this delta).** Authority: dimension 1 (a stale expectation is a false pass) and the brief's "profile caches keyed on file path". `BenchmarkLoader.load` caches on `profileName|customPath|confDir|appliance`, with no file timestamp in the key. An operator who tightens an expected value in the CSV keeps getting passes against the old value, and nothing in `docs/installing.md` or `CANONICAL_SCHEMA.md` warns about it. This is not touched by build 85 and does not depend on the interval, so per delegation rule 9 it is a follow-up issue, not a re-brief item for this build. **Fix:** add the file's size and last-modified time to the cache key, or document "edit the instance after changing the CSV".

### NIT

**N1. The esxcli test leaves three regressions unguarded.** `EsxcliCycleCacheTest.java`. Mutations M2 (executer cache not cleared), M8 (cache key ignores the command) and M9 (`VSphereClient.beginCycle` emptied) all pass, and nothing tests the one-line call in `collectWorld` that the whole fix depends on (confirmed only in bytecode for this build). **Fix:** route a stub executer lookup through the seam so the executer clear is observable; read a second command on the same host in cycle 1; pin the call order with a source-level check of `collectWorld` (`ensureConnected();` followed by `beginCycle();`) in the style of `EnvironmentKeyContractTest`, or move the cycle-start sequence into a helper with no SDK dependency that can be tested.

**N2. "cycle took N ms" is the collect body, and it is missing on failed cycles.** `ComplianceAdapter.java:392` and `:475`. Framework discovery and the metric flush are outside it, and an aborted cycle (where the time usually goes) logs no duration. `System.currentTimeMillis()` also moves with clock steps. **Fix:** log the duration from a `finally`, including on failure ("cycle failed after N ms"), and use `System.nanoTime()`.

**N3. The contract test ignores unknown parameters and spacing inside a reference.** `EnvironmentKeyContractTest.java`, the reference parser. Adding `depth=2,` to a reference passes, and a depth change alters what the engine sums. **Fix:** assert that each reference has exactly the three parameters `adapterkind`, `resourcekind`, `metric`.

**N4. Log volume at 12x.** The per-host INFO score line (`ComplianceAdapter.java` `collectHosts`) and the per-cluster "vSAN not enabled" INFO run every cycle. At 200 hosts that is about 57,600 lines a day per instance. Authority: review dimension 6. **Fix:** move the per-object lines to DEBUG, or keep them only for hosts whose score changed.

**N5. Zero-scored environments read as "0 non-compliant", carried from build 84 N3 (phase 3).** No consumer yet.

## Registry check (`knowledge/context/defects.md`)

No open defect has `Affects: compliance`. Open entries are synology, unifi, vcommunity-os, vcommunity-vsphere, `dashboard/*`, `factory:dashboards`, `factory:extractor` and `factory:packaging-cli`. DEF-005 mentions compliance in its body but is `Affects: synology`. There is no `defects.local.md` in this clone. `defect-gate --pak compliance` confirms. Registration candidates: W3 and W5, if a `v*` tag is proposed before they are resolved.

## Devel checklist for the 5 minute test

1. **Did the interval actually change?** After install, have ops-recon read `monitoringInterval` on all three instances (mgmt, wld01, wld02). Expect 5. If they still read 60, the upgrade did not carry the new default: the instances need an edit, and W3's docs note becomes required. Note which it was.
2. **Cycle duration.** In each instance's collector log, read the end-of-cycle line `ComplianceAdapter collection complete: ... cycle took N ms`. Expect tens of seconds (devel baseline is about 20 to 75 s). Over 150,000 ms (half the interval) needs a look. Over 300,000 ms, or successive "collection complete" lines more than about 6 minutes apart, means cycles are falling behind.
3. **Overlap or backlog.** Each cycle starts with `ComplianceAdapter enumerate: registering ComplianceWorld` and ends with the "collection complete" line. Two "enumerate" lines for the same instance with no "collection complete" between them would mean overlap and would contradict the semaphore model; report it. An "enumerate" line a second or two after the previous "collection complete", cycle after cycle, means the instance is running back to back (backlog). A cycle that ends in `onCollect: error collecting` logs no duration (N2), so read the timestamps.
4. **Load.** Watch for rising `SuiteApiStitchClient` WARN lines (HTTP 429 / 5xx / timeouts), a growing vCenter session count (expect one SOAP session per instance; the VAMI session should be opened and deleted each cycle), and collector heap/CPU over a few hours. Look for `RetrieveManagedMethodExecuter` / esxcli reasons in the "Unreadable controls this cycle by reason" line on a single host. If you see them, check that host's cycle time against W2.
5. **Live proof of the esxcli fix (needs Scott's go, because it changes a devel host).** Pick one esxcli-backed control on one host, change the setting, and confirm its `Compliant` value changes within two cycles (10 minutes) without a collector restart. Then revert it and confirm the value changes back. Build 84 would not have shown the change until a restart.
6. **Flapping (W1).** After a couple of hours, list the compliance alerts that were cancelled and raised again on the same object (several short-lived instances of one alert definition), and whether the "Unreadable controls this cycle by reason" counts move from cycle to cycle. Any such pairs are W1 in action; count them before deciding on `cancelCycle`.
7. **Environment totals.** The four `Rollup|Environment|*` values should now show up within one 5 minute cycle of the per-vCenter rollups, and still equal the bundled super metrics on vSphere World for the same timestamps. `NO_WORLD` after the second cycle is a failure; read the `SuiteApiStitchClient` WARN directly above it.

## If shipped as-is

To devel: compliance re-reads every host's esxcli settings every 5 minutes instead of trusting the first answer forever, so drift shows up within one cycle. Expect more alert churn than before (W1). If the existing instances keep their stored 60 minute interval, nothing about cadence changes at all (W3). As a public release: not possible yet (W6). The docs would contradict the pak (W5), and the 5 minute default is unproven at scale (W3).
