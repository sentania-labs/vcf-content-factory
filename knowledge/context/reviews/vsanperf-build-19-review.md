# vsanperf build 19 review (Build 3, `metric_scope`)

- **Adapter:** `content/sdk-adapters/vsanperf`, branch `build-3-metric-scope`, uncommitted tree, diffed against `main` = `0d55f30` (build 18, v1.1.0.18)
- **Reviewer:** `sdk-adapter-reviewer`, 2026-11-07
- **Design:** `knowledge/designs/vsanperf-mp-v3.md` (the "Decisions 2026-11-07" addendum wins over the body), on top of `vsanperf-mp-v2.md` and `-v1.md`. P3: `knowledge/context/api-maps/vsan-performance-service.md` §"P3: all 69 types, no labels"; `reference/docs/extracted/vsan-perfsvc-json/PROVENANCE-2026-11-07-all.md`
- **Verdict:** **CHANGES REQUESTED**. 1 BLOCKING, 4 WARNING, 5 NIT

The code is sound. `dashboard` is unchanged in every way that reaches vCenter or VCF Operations: the same requests, filters, keys, type order and learning. Under `all`, the 1,805 keys match Appendix A plus the 210 P3 labels exactly. The remote rule never lands a key on another cluster's object, and nothing new can crash a cycle. The rotation fix addresses a real pre-existing bug and I found no starvation.

The one BLOCKING finding is in the documentation, not the code. REFERENCE.md is the key contract, and for 44 new keys on the two ESA disk types its tables print the wrong key. Since keys become permanent at 1.2.0, the fix has to land before the tag. The warnings are about the strength of the T4 gate and one rotation edge case.

## Independent re-runs

| Claim | Re-run | Result |
|---|---|---|
| `ci/run_java_tests.sh` green | re-run on the working tree | **Confirmed.** 17 of 17 classes `all assertions passed`, exit 0, `real 4m15s` (JDK 17, 4 cores) |
| validate-sdk passes, 8.18 compatible | `validate-sdk --sdk-compat-jar …/vrops-adapters-sdk-8.18.7.jar` | **Confirmed.** `OK`. The 8.18.7 leg ran with javac 17, `--release 11`. The 9.1.1.0100 leg was skipped (no JDK 25 here; that leg runs in CI, RULE-019). |
| build-sdk `vcfcf_sdk_vsanperf.0.0.0.19.pak` | rebuilt into the scratchpad, tree hashed before and after | **Confirmed.** `adapters.zip` is 278,206 B. The adapter jar's contents are byte-identical to the author's `dist/` pak. All 77 classes are class-file 55 (Java 11), and no test or harness class is in the jar. The tree is unchanged by the build, so the generated docs in the tree are current. |
| pak-compare vs 0.0.0.18, 0 BLOCKING | build 18 rebuilt from `git archive main`, then compared; also compared against `dist/…0.0.0.18.pak` | **Confirmed.** `0 BLOCKING, 1 WARNING, 1 INFO`. W1 is the instance identifier count, 14 vs 13 (the new `metric_scope`, expected). I1 is the manifest description. |
| fixtures are the P3 captures verbatim | `cmp` of each `all-<type>-2026-11-07.json` against `reference/docs/extracted/vsan-perfsvc-json/all-<type>.json`, and sha256 against the README table | **Confirmed.** 69 of 69 are byte-identical, and 69 of 69 hashes match. `design-build3-metrics.md` matches the design's Appendix A on `main` with blank lines ignored. `design-build3-units.tsv` matches PY rc.2 `UNITS` and `PERMILLE` on all 762 rows (parsed from `app/metric_labels.py` and `app/perfsvc.py` at `v2.0.0-rc.2`, `af976fb`). |
| T4 (e) retained 31.4 to 32.4 MB < 35 MB | `ReplayBudgetTest` three times unloaded and once under 4 busy loops on 4 cores | Retained 31.2 to 32.3 MB, peak 38.5 to 39.6 MB (author: peak up to 46.1 MB). Every run passed. See W3. |

Reviewer-only probes (scratch copies; the adapter tree was not touched):

| Probe | Result |
|---|---|
| Dump of every dashboard catalog row (label, leaf, per-mille, position, stat key, tier, target, group, form, `learnsEmpty`, wire cap) and the `labels` filter, built from `main` and from the branch | **Identical**, 451 rows over 33 types |
| `VsanJsonClient.perfBody` for the 33 dashboard types, `main` vs branch | **Byte-identical** |
| Collection order of the 33 dashboard types | **Identical**. The new types are interleaved in the enum, but `ofTiers(…, DASHBOARD)` filters them out. |
| The 1,805 `all` rows vs Appendix A + the P3 210 (parsed independently) | 0 extra, 0 missing, 0 leaf differences. No P3 label collides with another type's label. No (kind, group, leaf) is written by two types on one object kind. |
| REFERENCE.md key tables vs `EntityType` | **44 rows wrong** (B1); every other row agrees on key, leaf, group, instance and scope |
| `stitch_targets` key groups vs the groups each type can land on, per kind | exact on all three kinds |
| Rotation: the T4 (d) config, 12 cycles, under three rules: build 19, build 18's rule, and build 19 without `restartAt` | see claim 3 |
| T4 (a) and (e) repeated (variance), plus a full `ReplayBudgetTest` under CPU load | see W3 and N1 |

## The brief's claims

### 1. `dashboard` behaves exactly as build 18: **confirmed for everything vCenter and Ops see**

From the code and the dumps above:

- **Calls.** `Settings` drops every all-only type (`inScope`), and the 33 remaining types keep build 18's order.
- **Labels filter and request bodies.** Byte-identical for all 33 types.
- **Keys.** The catalog dump, stat keys and dedup positions are identical, because dashboard rows come first and the constructor enforces it. `statKey` changed only for an instanced type with a null instance; no dashboard path produces one, since `PATH` resolves its bus position first.
- **Parse.** `metric(label, DASHBOARD)` returns exactly the old rows. Under the filter no other label arrives, so `labels_dropped` stays 0.
- **Learned-empty and fault learning.** The strike branch is taken only for `faultStrikes` types, all nine of which are all-only. `noStrike` on a dashboard type removes from an empty map. `landsOnHost()` is true for all three dashboard runtime-landing types (`vsan-direct-cluster`, `vsan-file-service`, `ioinsight`; no host type shares their group).
- **Push and identity.** Unchanged.
- **Harness.** `ScopeTest.scopeSwitchRestarts` gives 26 calls and 2,372 values, then 23 steady, the build 10 figures. T4 (a') per-cluster is byte-for-byte build 18 (1,820 / 1,610 calls, 88.9 / 78.7 s).

Not byte-identical, though nothing reaches vCenter or Ops differently:

- the rotation change (claim 3), which also moves T4 (a)'s cycle 4 (N1);
- the log text (N2).

### 2. Under `all`: **confirmed**

- **Filter.** Every type, not only the 21 shared ones, sends no `labels` key (`ScopeTest.requestBody` over all 69). The parser keeps the scope's catalog and counts the rest. On P3 the only labels dropped are the 41 `Actual` twins.
- **Keys and tiers.** 1,805 keys = 451 + 1,144 + 210. The 36 new types sit in the tiers design §New types assigns: cluster 9, host 21, disk 3, VM 3. Types per tier are 3 / 34 / 19 / 7 / 6, and order follows C8 (`host-cpu` and `dom-world-cpu` last in the host tier).
- **The 210 P3 labels.** All are verbatim leaves with no suffix. None is released elsewhere, so rule 2 never applies, and rule 4 (unit unknown, P3 "Units for these are not in PY UNITS") gives the verbatim leaf.
- **The nine Q5 types.** Flag `STRIKES`, exactly the nine. A type-unavailable fault adds to `failedCalls` and `optional`, so it counts in `optional_calls_failed` and the once-per-refresh WARN. `LearnedTypes.strike` learns at the third consecutive fault, with `SKIP_MS + offsetMs` (the same spread). A re-probe that faults again re-learns at once, and any other answer resets the count. The two PMem types still learn at the first `NotSupported`, as the body says; Q5 names only the nine.
- **`pctMemUsed`.** Verbatim leaf, `perMille=false`, pushed as served (Q4, P3 arithmetic).
- **Remote types.** These hold:
  - The cluster remote types are `Target.CLUSTER`, so any uuid other than the queried cluster's goes to `unresolvedClusters`, which counts in `clusters_unresolved`.
  - The host remote types require `isNodeOf(c, uuid)`, a node of the queried cluster, before the node map is consulted.
  - The VM remote types require the queried cluster's VM read.
  - Every miss lands in `remoteUnresolved`, which counts in `clusters_unresolved` with one WARN per refresh that gives a count and no id.

  `ScopeTest.remoteRule` pins the host and cluster cases with a second in-scope cluster whose host is known; the VM-tier path is untested (N3).
- **`cluster-pmem`.** `landsOnHost()` is false because `host-pmem` owns `PMem` on HostSystem, so a node-uuid id goes to `entities_unparsed`, never to a host.
- **Scope change.** `configureAdapter` builds a new `CycleEngine` on every configure (`VsanPerfAdapter.java:83-123`), so learned state and marks cannot survive a scope change. `ScopeTest` pins the result: 56 calls, 0 learned skips, both buckets.

### 3. The rotation change: **the pre-existing bug is real; no starvation, no double collection, no watermark regression; one edge case (W1)**

**The bug.** In build 18, the pool task for a cluster that a worker dequeued after the deadline returned immediately without a call. It still advanced `furthestStarted`. A worker that finishes its in-flight cluster at the deadline drains the rest of the queue in microseconds, usually before the caller's `cancel(true)` lands. So `lastAttempted` became the last cluster in the cycle's order, and the next cycle started where this one had. On the new harness with build 18's rule restored (scratch copy):

```
build 18 rule, scope all, 12 cycles:   max gap 6 cycles; 7 clusters completed once in 12 ("......#.....")
build 18 rule, dashboard, 7 cycles:    6 clusters got no completed collection in cycles 1 to 3 ("...####")
build 19,      scope all, 12 cycles:   max gap 2 cycles; every cluster completes 4 to 6 times
build 19,      dashboard, 7 cycles:    max gap 1
build 19 without restartAt (counting fix only): max gap 5
```

I did not reproduce the author's exact "51 of 70 in two cycles", because scheduling varies run to run, but the mechanism and its effect are confirmed.

**Starvation.** None is possible. `restartAt` is chosen only among positions `p >= workers` of the current order, so a cycle that uses it starts at least `workers` positions further on. A cycle that does not use it starts after the furthest cluster started before the deadline. Every position between the old start and the new one was started in the cycle. The start therefore advances by at least `workers` (at least 1) every cycle, and every cluster is reached each lap. The two exclusions (one of the clusters the workers started with, or one cut last cycle too) keep a chronic cluster from holding the front two cycles running. `noStarvationBehindSlowCluster` still passes, and it does so through the `cutLastCycle` exclusion.

**Double collection.** Each cluster is submitted once per cycle. A restarted cluster re-queries the window: the types it pushed before the cut are dedup-skipped by their marks, and the types it never reached push both buckets, which is the existing self-overwrite behaviour.

**Watermarks.** No change to `Watermarks` or the commit path.

**Cost.** One edge case is real: W1.

### 4. Keys: **the catalog is exactly the sources; REFERENCE.md is not (B1)**

I compared all 1,354 new rows (1,144 Appendix A + 210 P3) with an independent parse of the design on `main` and of the P3 label list. Spelling, groups, instance templates and leaves all agree. The unit-suffix rule reproduces from the units TSV, and the TSV equals PY rc.2. No key is invented beyond the sources. The one cross-type leaf split, `latencyRead` (verbatim on PMem, `latencyReadUs` elsewhere), is design rule 1 overriding rule 2, as Appendix A lists it. REFERENCE.md is wrong for 44 keys (B1).

### 5. T4 (e) and T4 (d): **see W2 and W3**

### 6. `cf40feb`: **flagged (W4)**

### 7. The usual hunts: **proven safe** (below), except for the docs (B1)

## Registry check (`knowledge/context/defects.md`)

No defect names `vsanperf` in `Affects:`. There is no `defects.local.md`. `python3 -m vcfcf_packaging defect-gate --pak vsanperf` reports "no open blocking defects affecting vsanperf". Nothing to re-assert and nothing to propose for closure.

**Registration candidates** if they survive acceptance: W1 (rotation, `max_parallel_clusters=1`) and W3 (T4 flake risk on the tag workflow).

## BLOCKING

### B1. REFERENCE.md prints the wrong key for all 44 new keys on the two ESA disk types

**Where:** `REFERENCE.md:2533-2565` (`vsan-esa-disk-layer`, 33 rows) and `REFERENCE.md:2582-2592` (`vsan-esa-disk-scsifw`, 11 rows).
**Authority:** review dimension 11 (docs that contradict actual behaviour are BLOCKING); design v3 §"REFERENCE.md, docs-gen, CHANGELOG" ("every key table gains a Scope column … the 21 shared sections grow"); the brief's item 4 (keys are permanent once 1.2.0 installs, and REFERENCE.md is where an operator or a content author reads them).

Every new row in those two tables is a splice of the first dashboard row and the real row:

```
|`vSAN Perf\|ESA Disk Layer:<disk uuid>\|avgLatReadCapacity`|`avgLatReadCapacity`|vSAN Layer Average Read Latency of vSAN ESA Disk|none stated|none; name matches built-in `vSAN\|Performance\|avgLatReadPerf`|`avgLatReadPerf`|Latency read perf (average)|none stated|none|all|
```

The key and label columns name `avgLatReadCapacity` (or `latencyDevDAvgUs` on SCSI), which is a dashboard key. The real label (`avgLatReadPerf`) appears only in the middle of the Transform cell. A view or super metric written from this table targets the wrong key for 44 metrics. The code pushes the right keys. Every other table row in REFERENCE.md agrees with `EntityType` on key, label, leaf, instance and scope (1,761 rows checked).

**Fix:** regenerate the 44 rows in the shape the other shared sections use: `|`vSAN Perf\|ESA Disk Layer:<disk uuid>\|<leaf>`|`<label>`|<meaning>|<unit>|none|all|`, and the same for SCSI. A test that parses REFERENCE.md's key tables against `EntityType` (label, leaf, group, instance, scope, transform) would stop this recurring; it took about 40 lines of Python here.

## WARNING

### W1. A cluster the deadline cuts gets the front of the next cycle even when it cannot finish, and a per-call timeout counts as a cut

**Where:** `CycleEngine.java:1085-1093` (`restartAt` selection), `:1245` (`cycleSettled` excludes every `TIMED_OUT`), `:954-957` (rotation).
**Authority:** design v2 Scale requirement (fairness; the Codex starvation case this code exists for); the build's own docs: CHANGELOG 1.2.0.19 ("the earliest cluster **the cut** interrupted goes first") and README §Scale ("a cluster **the deadline** cut after it started late").

- **A chronic cluster.** A cluster that is slow every cycle and is reached late becomes `restartAt` once per rotation lap and holds one worker for the whole next cycle. With `max_parallel_clusters=1`, the documented range is 1 to 16, so that whole cycle collects nothing else. The author's own `EngineTest.cutClusterRestartsFirst` shows it: cycle 2 restarts the cut `c2`, `c2` is cut again, and **0 clusters complete in cycle 2**. Under build 18's rotation (counting fix kept), cycle 2 would have completed `c3` and `c1`. With `m` chronic clusters and one worker, up to `m` cycles per lap are spent this way. This is bounded (claim 3) and not starvation, but it is a throughput loss the docs don't mention.
- **A per-call timeout.** `cycleSettled` records only OK or FAILED, so a cluster whose own call hit `call_timeout_seconds` (`HttpTimeoutException`, outcome `TIMED_OUT`) well before the deadline counts as "cut" and can become `restartAt`. That rewinds the next cycle's start to it and re-collects the clusters between it and the furthest one. On a cycle that never hits the deadline, this only reorders the clusters. The CHANGELOG's "only on cycles that hit the deadline" is therefore not exactly true.

**Fix (smallest):** mark a cluster as cut only when the deadline cut it: its `ClusterDone` never arrived, or it arrived `TIMED_OUT` at or after `deadlineMs`. Skip `restartAt` when `workers == 1` and fall back to the `lastAttempted` rotation. Add an `EngineTest` for each case, and say in the CHANGELOG and README what a chronic cluster costs.

### W2. T4 (d) asserts fairness only from cycle 10; cycles 1 to 9 have no bound

**Where:** `ReplayBudgetTest.allScopePerVcenter` (`if (r.cycle >= 10)`).
**Authority:** design v3 §T4 rows: "(d) … every cluster completes at least once in any 2 consecutive cycles (rotation)", with no cycle qualifier.

The restriction is honest arithmetic, not a dodge. Before learning builds up, a cluster costs 56 calls, so only 28 complete per cycle, and 56 is less than 70. Learning takes until about cycle 9 because a cluster learns only when it is reached, and the nine Q5 types need three faults. The design assumed the steady 37 calls and ~45 clusters. Its claim does not hold for the first ~45 minutes after a switch to `all` under the per-vCenter ceiling, and the README says so.

The gate is weaker than the design, though: for 9 of 12 cycles nothing bounds the gap. In my runs, the build 18 rule (gap 6) and the counting fix without `restartAt` (gap 5) were both caught only at cycles 10 to 12, and only because of where their gaps happened to fall.

**Fix:** add a bound over all 12 cycles that holds now and fails both broken rules, for example "every cluster completes at least once in any 4 consecutive cycles" (build 19 max gap 2; build 18 rule 6; no `restartAt` 5). Keep the 2-cycle assertion from cycle 10. The orchestrator should add a design note that (d)'s 2-cycle bound applies only once learning has settled.

### W3. The T4 heap ceilings under `all` leave thin, load-sensitive margins

**Where:** `ReplayBudgetTest` (e) reuses `VM_PEAK_CEILING` 50 MB and `VM_RETAINED_CEILING` 35 MB; (d) uses `ALL_PEAK_CEILING` 50 MB.
**Authority:** design v3 §T4 row (e) ("VM-case ceilings (50 / 35 MB)"); the build 15 review's W4 and N1 (the sampler misses transients; readings vary run to run); the CI tag workflow runs this suite, so a flake blocks a release.

| Reading | Runs | Ceiling | Margin |
|---|---|---|---|
| (e) retained | 31.2, 31.3, 31.5, 32.3 (one under load); author 31.4 to 32.4 | 35 MB | 2.6 to 3.8 MB |
| (e) peak | 38.5, 39.2, 39.6, 39.6 (load); author 39.1 to **46.1** | 50 MB | 3.9 to 11.5 MB |
| (d) peak | 17.6, 25.6 (load); author 17.7 to 25.4 | 50 MB | comfortable |

Retained is tight but steady: about 1 MB of spread over 6 readings, one of them under load. Peak is the riskier figure. The author already saw 46.1 MB, and in my second full run, started just as the 4 busy loops of the load run ended, **T4 (a)'s pre-existing 15 MB ceiling failed at 16.3 MB** on cycle 1 (`AssertionError: regression ceiling: peak 16 MB < 15 MB`). Four clean repeats read 6.3 to 7.5 MB, so that was a sampler transient of about +9 MB. A transient of that size on (e) crosses 50 MB. The JDK 25 CI leg is unmeasured here.

**Fix:** give (e) its own ceilings with the basis recorded, as build 16 did: about 1.5x its readings, e.g. peak < 65 MB (the budget) and retained < 45 MB, and note it in the design. Alternatively, keep the ceilings and record the measured margins and the flake risk in the class doc and README, so a red tag build is read correctly. Measure on the JDK 25 leg before tagging.

### W4. The fixture provenance cites a commit a fresh clone cannot resolve

**Where:** `tests/fixtures/README.md:43` and `:206`; `tests/fixtures/design-build3-metrics.md:1` (header comment).
**Authority:** RULE-015 (`knowledge/rules/cited-artifacts-reproducible.md`: "a fresh clone plus bootstrap must be able to resolve every citation").

`cf40feb` exists only on the deleted branch `vsanperf-build3-design-p3`, which `git ls-remote origin` no longer lists; only a stale local tracking ref remains. The design and P3 landed squashed on `main` at `478d67b` (#329). The content is right: I checked the fixtures byte for byte against `main`. Only the pointer is dead.
**Fix:** replace `cf40feb` with `478d67b` in all three places.

## NIT

- **N1. T4 (a) cycle 4 margin shrank, and the class doc is stale.** The new rotation spreads the first cycles' gaps, so more clusters are still learning at cycle 4. Cycle 4 now reads 1,662 to 1,664 calls in 237 to 238 s over 7 runs, against build 18's 1,628 to 1,640 calls in 232.9 to 234.6 s. The margin to the `< 240 s` assertion drops from ~5 s to ~2 s. The class doc's "Variance" paragraph still quotes build 18's figures. Update it. For production, the dashboard steady state is unchanged from cycle 5.
- **N2. The dashboard log text is not byte-identical.** The configure line, the cycle summary (`; scope=dashboard;`) and `PERF tier … scope= labels_dropped=` are design-mandated. The `exclude_types` WARN wording changed from "collects" to "knows" (`VsanPerfConfig.java:170`), which the design did not ask for. Anyone grepping for the old text should know.
- **N3. The remote rule has no test on the VM tier.** `ScopeTest.remoteRule` covers `host-remotedomclient` and `cluster-remotedomclient` only. The `remoteUnresolved` branches for `remote-virtual-machine`, `remote-vscsi` and `remote-virtual-disk` (`CycleEngine.java:1913-1938`) are reviewed but untested. Design T1 asks for the remote rule with synthetic ids.
- **N4. The `stitch_targets` HostSystem identity omits Resync and the remote rule.** It names only the three V2 runtime-landing groups. `cluster-resync` also lands on hosts (this is in the YAML comment, which docs-gen does not render), and the remote rule is not stated. The key-group list itself is exact. Append both to `identity`.
- **N5.** The `PerfParser` javadoc "Accumulates entities of one response…" now sits on `DROPPED_NAMES_MAX` instead of `Acc`.

## Notes for the design owner (not findings against the author)

- `vSAN Perf|System Memory|overcommitRatioPct` follows Appendix A (PY `RATIO.PERCENT`, rule 6). P3 observed only zeros, so the unit is unverified. It becomes a permanent key at 1.2.0.
- The 210 P3 labels have no units at all (P3: "any unit is `[unverified]`"). Their leaves are verbatim forever (C7), as decided.

## Hunt list: proven safe

- **Unreadable is not data.** A fault, an empty echo, a remote miss, a landing miss or a dropped label pushes nothing, and each is counted. An all-`None` series yields no sample (unchanged). A strike fault never becomes data and never ends a cluster as OK on its own: core calls run every cycle.
- **Stitch corruption.**
  - Remote ids are gated on the queried cluster (`isNodeOf`, the cluster uuid, the cluster's VM read) before any map lookup, so another in-scope cluster's host is never touched (`remoteRule` checks `rid-host-9999`).
  - No (kind, group, leaf) is shared by two types.
  - `cluster-pmem` never reaches a host.
  - New instances come from the entity id only: `cpu-<n>`, `<world>-<id>`, `<target>/<lun>`, heap, slab.
  - The `host-cpu` aggregate (`vSAN Perf|pCPU|…`) has its own entityRefId and so its own dedup marks.
  - Watermark hashes include the type prefix, so ids of different types cannot collide.
- **Crash the cycle.** New parse paths return null, which counts as unparsed, on a wrong part count. `REMOTE_PATH` keeps `|` ids whole and lets the device map miss. `droppedInfo` filters names through a regex before logging. `EntityType`'s constructor checks run at class load and are exercised by every test. Per-call exceptions are caught at the existing per-call scope.
- **RULE-008.** New log lines carry a count (remote WARN), label names filtered to `[A-Za-z0-9_]{1,80}` (dropped-label INFO), and cluster MoRef, type id and fault class (strike INFO). The configure line adds only `scope=`. No credential, token or body appears in any new line or exception.
- **8.18 compatibility.** Compiles against `vrops-adapters-sdk-8.18.7.jar` at `--release 11`; 77 of 77 classes are version 55.
- **describe.xml.** `metric_scope`: `nameKey="43"`, `dispOrder="14"`, `identType="2"`, enum `dashboard` / `all`, default `dashboard`, the same shape as the existing enums. The nameKeys are unique (41 distinct), each has a `resources.properties` entry (`43=Metric scope`), and the packed copy carries both. No alerts or symptoms, so dimension 13 does not apply.
- **Docs parity, generated side.** The `stitch_targets` key groups match the code on all three kinds. `docs/README.md` and `docs/inventory-tree.*` are regenerated and current (the tree was unchanged by the rebuild).
- **Build hygiene.** `version: "1.2.0"`, `build_number: 19`, a CHANGELOG entry. The production diff is confined to scope, catalog, parser, remote and strike handling, and the rotation fix, which is disclosed. No drive-by refactors.
- **Memory.** `remoteWarned` is cleared at each host-map refresh. `droppedNames` is capped at 64 per response. The per-scope mark width is `size(ALL)` only under `all`.

## Not verified here

- The JDK 25 / 9.1.1.0100 compile leg and the JDK 25 heap readings (CI).
- Anything live. T5 on devel 9.0.2, then 8.18 and 9.1, is the orchestrator's step. In particular, the HCI Mesh ids (Q6) and the nine Q5 types on a non-9.1.1 vCenter remain unobserved.

## If shipped as-is

Collection would be correct under both scopes. The problem is the documentation: an operator or content author who builds from REFERENCE.md would target dashboard keys for 44 of the new ESA disk metrics. And with `max_parallel_clusters=1`, a cluster that never finishes would cost one empty cycle each time the rotation reaches it.
