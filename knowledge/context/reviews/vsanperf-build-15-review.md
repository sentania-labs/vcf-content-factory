# vsanperf builds 14 and 15 review (T3 replay harness, T4 budget gate, per-push-call dedup commit)

- **Adapter:** `content/sdk-adapters/vsanperf`, branch `build-14-t3-t4`, uncommitted tree, diffed against `main` = 7224fb4 (Build 2 merge, build 13)
- **Reviewer:** `sdk-adapter-reviewer`, 2026-11-07
- **Design:** `knowledge/designs/vsanperf-mp-v2.md` §Sizing (D6, requirements 1 to 5), §Test plan T3/T4; `vsanperf-mp-v1.md` §Value selection
- **Verdict:** **APPROVE**. 0 BLOCKING, 4 WARNING, 2 NIT

Build 15 does what it was built for: the VM-tier peak drops from ~71 MB to ~32 to 39 MB. I checked that the new T4 VM assertion catches the build 14 scheme: build 14's production source, run against the new `ReplayBudgetTest`, fails it at 71.3 MB. The per-call commit sets marks only after a clean push result. A failed call is re-sent and the clean calls are not, **except in one ordering**. If the older bucket's call fails and the newer bucket's call for the same (entity, label) is clean, the newer mark hides the failed value, so it is never re-sent (W1). At the documented 5-minute interval this loses nothing that build 14 kept, because the failed bucket has already left the next cycle's window. At a collection interval of about 2 minutes or less, it is a regression. Keys, identities, describe.xml and bytecode are unchanged.

## Independent re-runs

| Claim | Re-run | Result |
|---|---|---|
| validate-sdk passes, 9.0 and 8.18.7 | `validate-sdk --sdk-compat-jar /mnt/holding/vendor/vcf-ops-8.18.7/extracted-jars/vrops-adapters-sdk-8.18.7.jar` | **Confirmed.** `OK`. 8.18.7 leg: javac 17, `--release 11`. 9.1.1.0100 leg skipped (only JDK 17 here; CI's job, RULE-019). `stitch_targets` passes the #310 validator. |
| build-sdk `vcfcf_sdk_vsanperf.0.0.0.15.pak` | rebuilt into the scratchpad | **Confirmed.** `adapters.zip` 250,850 B. Its jar's entries are byte-identical to the author's `dist/` pak, and the jar and `overview.packed` differ only in zip timestamps. All 75 classes are class-file 55 (Java 11, 8.18-safe). No test or harness class is in the jar. The adapter tree was unchanged by the build (hashed before and after). |
| pak-compare 0 BLOCKING / 0 WARNING vs rebuilt build 13 | build 13 rebuilt from `git archive main`, then compared | **Confirmed.** `0 BLOCKING, 0 WARNING, 0 INFO`, "No structural divergences found". `describe.xml` is byte-identical between 15 and 13; the manifest differs only in version. |
| `ci/run_java_tests.sh`, 14 classes, ~1 min 42 s | re-run | **Confirmed.** 14 of 14 `all assertions passed`, `real 1m35.4s`. |
| T4 (a) per-vCenter: cycles 1 to 3 deadline (~1,664 calls), cycle 4 1,640 calls 234.6 s, steady 1,610 / 230.3 s, 98,350 series, peak 7.3 MB | `ReplayBudgetTest` (in the suite), `ci/replay.sh --cycles 7 --model vcenter`, and once more under CPU load | **Confirmed within run-to-run variance.** Cycles 1 to 3: 1,664 to 1,681 calls, 240.0 to 240.5 s, 61 to 64 of 70 clusters ok. Cycle 4: 1,628 to 1,640 calls, 232.9 to 234.6 s, 70 ok (4 runs). Cycle 7: 1,610 calls, 230.3 s in every run. Newest bucket 98,350 from cycle 4. Peak heap delta 6.3 MB (6.2 MB under load). Build 14 source on the same test: 15.2 MB. |
| per-cluster model 78.7 s steady | `ci/replay.sh --cycles 7 --model cluster` | **Confirmed.** 1,820 calls / 88.9 s for cycles 1 to 3, then 1,610 / 78.7 s. Deterministic in every run. |
| VM tier N = 3 peak 33.5 to 37.4 MB (build 14: 70.8 to 76.6), retained ~27 MB | `ci/replay.sh --vm --vm-every 3 --heap --pace 20`, the T4 (b) run, and build 14 source on the new T4 | **Confirmed.** Build 15 per-vCenter: 32.0 MB (T4 in the suite), 35.8 MB (standalone), 38.9 MB (T4 under 4 busy loops), retained 26.4 to 28.3 MB. Per-cluster: 36.1 MB, all 70 clusters complete each cycle (1,892 / 1,868 / 1,910 / 1,682 calls; 110.7 / 102.4 / 114.3 / 99.7 s). **Build 14 production source on the new T4 (b): 71.3 MB peak, `AssertionError: VM variant peak heap 71 MB < 65 MB`.** |

Reviewer-only probes (scratch copies; the adapter tree was not touched):

| Probe | Result |
|---|---|
| Heap sampling every 10 ms instead of 150 ms, VM N = 3 per vCenter | peak 37.7 MB (150 ms: 32.0 to 35.8) |
| VM N = 1 (design T4 (c)) | peak 36.6 MB, retained 28.8 MB; 12 to 15 clusters time out each cycle (per-vCenter) |
| All tiers, disk + VM N = 3 (design T4 (b) as written) | peak 36.4 MB |
| VM N = 3 unpaced (the queue-full bound the harness doc warns about) | peak 33.3 MB |
| VM N = 3 paced with `--perf` | `max_queue_depth` 5 to 8 of 16, `vm_permit_wait_ms_max=0` |
| `ReplayBudgetTest` under 4 CPU-bound loops on 4 cores | passed, wall 125 s (unloaded 80 s) |
| Watermark: fail each of the four push calls of `failedMiddleBatchOnly`'s setup in turn | see W1 |

## Registry check (`knowledge/context/defects.md`)

No defect names `vsanperf` in `Affects:`. `python3 -m vcfcf_packaging defect-gate --pak vsanperf`: "no open blocking defects affecting vsanperf". Nothing to re-assert, nothing to propose for closure.

**Registration candidate** if it survives acceptance: W1.

## BLOCKING

None.

## WARNING

### W1. A failed older bucket is masked by its clean newer bucket, so it is never re-sent

**Where:** `CycleEngine.java:1921-1925` (`pushGroup` commits per group); `Watermarks.record` keeps the newest mark per (entity, label); the skip test is `CycleEngine.java:1117` (`ts <= marks.last(er.mark, pos)`).
**Authority:** design v2 §Sizing requirement 2 (a bucket newer than the per-(entity, label) mark is pushed; the mark moves only after a clean push), the build's own docs (`REFERENCE.md:184-188`: "after a failed call the next cycle sends that call's buckets again while they are still in the 7-minute window"; CHANGELOG 1.1.0.15: "a failed call leaves exactly its own values' marks unset, so only those buckets are sent again next cycle"), and the brief's invariant.

Groups are per (kind, sample time). When one (entity, label) has two buckets in a cycle, T1 and T2 land in different push calls. If the T1 call fails and the T2 call is clean, `commitTo` records T2 for that label. The next cycle sees T1 with `T1 <= last == T2` and counts it as a duplicate. The failed value is never re-sent. Build 14 committed nothing when any call failed, so it re-sent T1.

Probe (scratch only): `EngineTest.failedMiddleBatchOnly`'s setup (150 hosts, buckets 02:25 and 02:30, four calls), failing each call in turn:

```
failCall=0 (02:25, 100 values) FAILED -> next cycle re-sent 0 of the 100 failed values, duplicatesSkipped=300
failCall=1 (02:30, 100 values) FAILED -> next cycle re-sent 100 of the 100 failed values, duplicatesSkipped=200
failCall=2 (02:25,  50 values) FAILED -> next cycle re-sent 0 of the 50 failed values,  duplicatesSkipped=300
failCall=3 (02:30,  50 values) FAILED -> next cycle re-sent 50 of the 50 failed values,  duplicatesSkipped=250
```

The author's test fails call 1, which is the one ordering that works.

**Why WARNING, not BLOCKING:** the window is 7 minutes and buckets are 5 minutes apart. With cycles 5 minutes apart, a bucket that is the older of two in cycle k is outside cycle k+1's window, so build 14 could not re-send it either. Loss is identical at the documented interval (`REFERENCE.md:14`). The loss becomes real, and build 15 regresses against build 14, when consecutive window ends are about 2 minutes apart or less. The interval is read from the instance (`VsanPerfAdapter.java:374-380`), so an operator who shortens it gets silent per-sample gaps after any failed push. The only trace is the push WARN and `push_batches_failed`. If sub-5-minute intervals are in scope, treat this as BLOCKING.

**Fix (smallest):** keep the `Pending` of each **failed** group on the `PushBuffer`; failure is rare, and the worst case, every call failing, is build 14's footprint at 12 B per value. At the end of `flush`, for each failed entry with `last(e, p) >= time`, lower the mark to `time - 1 s`. That needs a new `Watermarks.lower(e, w, p, ts)`, because `record` only raises. T1 is then re-sent, and T2 is re-sent as a self-overwrite, which the design accepts. Add `EngineTest` cases with `failCall = 0` and `2`. Alternatively, keep the code and correct REFERENCE and CHANGELOG to state that the guarantee holds only at the 5-minute interval.

### W2. `stitch_targets` HostSystem omits the three runtime-landing groups

**Where:** `adapter.yaml` `stitch_targets[0].key_groups`; generated `docs/README.md` and `docs/inventory-tree.md` "Metrics Pushed Onto".
**Authority:** review dimension 11 (docs parity; cross-MP stitches appear only through this stanza); `REFERENCE.md:171-176` ("an id equal to one node uuid of that cluster lands on that host under the same group name"); `EntityType.java:216,226,236` (`Target.CLUSTER_OR_HOST`).

The 33 listed groups match the REFERENCE headings and the `EntityType` group names exactly. However, `vSAN Perf|vSAN Direct Cluster|*`, `vSAN Perf|File Service|*` and `vSAN Perf|IOInsight|*` can land on **HostSystem**. The stanza says so only in a YAML comment, which docs-gen does not render. The landing page therefore lists them under ClusterComputeResource only. This is documented in REFERENCE but absent from the landing page: a WARNING.
**Fix:** add the three groups to the HostSystem `key_groups`, and append to its `identity` text: "vsan-direct-cluster, vsan-file-service and ioinsight: only when the entity id is one node uuid of the cluster (runtime landing)".

### W3. T4 covers less than design §Test plan T4 asks for

**Where:** `ReplayBudgetTest.vmTierPerVcenter` and the class doc.
**Authority:** design v2 §Test plan T4: (b) "**all tiers**, VM N = 3: peak heap < 65 MB; under the per-vCenter model the deadline path is exercised …; **under the per-cluster model the cycle completes**"; (c) "VM N = 1: heap only".

T4 (b) runs default + VM, not disk. It asserts neither the per-vCenter deadline path nor per-cluster completion, and (c) is not run. README §Scale verification says "Every case is inside the 65 MB budget", which is true only of the cases in its table. My probes show the missing cases pass: all tiers 36.4 MB; per-cluster VM 36.1 MB with 70 of 70 complete every cycle; N = 1 36.6 MB. The fix is cheap and safe.
**Fix:** set `c.tierDisk = true` in (b). In (b), assert `clustersTimedOut > 0` on at least one cycle. Add a per-cluster VM variant (4 cycles) that asserts `clustersOk == 70`. Either run (c) with heap-only output, or record in the class doc and README that (c) is run through `ci/replay.sh`, not in CI. Each VM variant costs about 40 s of CI wall time, so if CI time matters, make (c) the replay-only case.

### W4. T4 is a budget gate, not a regression gate, and its reading has known blind spots

**Where:** `ReplayBudgetTest` (`peak < BUDGET` only); `ReplayHarness.HeapSampler`, `Ops.pushStats`.
**Authority:** design v2 §Sizing ("T4 is the gate"; the D6 table counts the push body ~1 MB and the gzip wire buffer); the brief's question about whether T4 would catch a build 14 kind of regression.

- **Sensitivity.** Build 14's scheme fails the new (b), but only by 6.3 MB here (71.3 vs 65). Build 15 sits at 32 to 39 MB, so a regression of up to ~25 MB passes T4 silently. The same applies to (a): build 14 measured 15.2 MB against 6.3 MB now, which is invisible to a 65 MB check.
- **Blind spots.** The 150 ms post-GC sampler misses transients: 10 ms sampling read 37.7 MB against 32.0 to 35.8 MB. The recording stitcher never serializes the push body; production builds up to ~1 MB of JSON per call, plus HTTP buffers. The fake vCenter never holds the gzip wire `byte[]` that `CappedBody` holds, ~0.2 MB per VM call. These are a few MB together, well inside the current ~26 MB headroom, but not counted. The JDK 25 CI leg is unmeasured locally; only JDK 17 is installed.

**Fix:** add regression ceilings beside the budget, about 2x the current reading: (a) `peak < 15 MB`; (b) `peak < 50 MB` and `retained < 35 MB`. Then a build 14 class regression fails on its own merits, not by a 6 MB margin. Make `Ops.pushStats` serialize the stats map to a `StringBuilder` and discard it, so the push body is counted. Name the sampler's miss (~2 to 5 MB) in the class doc.

## NIT

- **N1. The simulated time is not deterministic.** Thread scheduling still moves the results between runs: cycles 1 to 3 at 1,664 to 1,681 calls with 61 to 64 clusters ok, cycle 4 at 1,628 to 1,640 calls and 232.9 to 234.6 s. Separately, the caller's clock is the minimum over registered workers, including finished ones, so the caller often never cuts: `cut=false` with `timed_out=10` (the class doc covers only part of this). The T4 tolerances absorb all of it: 5 of 5 runs passed, one under full CPU load. But the README table gives single figures, and the cycle 4 `< 240 s` assertion has only ~5.4 s of margin. Say "varies run to run" in the README and the class doc.
- **N2. Push latency is not modelled.** The recording stitcher returns instantly, so the caller thread never stalls on a slow Suite API the way production's synchronous `pushGroup` does. The heap effect is bounded: unpaced 33.3 MB, paced `max_queue_depth` 5 to 8 of 16. The cycle-time effect is not; the post-deadline `flush` time is still unmeasured, as design §Cycle time says. A fixed per-call delay in `Ops.pushStats`, paced like the perf calls, would make T3 report it.

## Hunt list: proven safe

- **Marks only after the push result.** `g.pending.add` buffers; `commitTo` runs only after `ops.pushStats` returns and only if `o.clean` (`CycleEngine.java:1917-1925`). A clean call's values are not re-sent (probe, failCall 1 and 3: the clean 200 / 250 are skipped).
- **A push that throws.** The framework contract is "Never throws" (`SuiteApiStitchClient` `pushStatsBatch` javadoc); `isClean()` is false on any failed, skipped or dropped batch, or a stopped call. If a defect did throw, the group was already removed from the buffer and no mark is set, so its values are re-sent. Earlier clean groups stay committed, which is correct because they landed. The exception leaves `run()` as before build 15.
- **Two groups, one entity, different times.** Within one `EntityRows` a label's buckets are added oldest first (`PerfParser.buckets` sorts by time), and one entityRefId arrives in one message. So a mid-cycle commit of T2 cannot skip an un-buffered T1 of the same cycle. The only cross-time hazard is the next-cycle masking in W1.
- **Hash collisions.** Unchanged: a width mismatch resets the entity's marks (never skip on a foreign mark). Interleaved per-group commits only make a reset happen earlier in the cycle.
- **Packing.** `(position << 16) | (width & 0xffff)`, unpacked with `>>> 16` / `& 0xffff`; catalog widths are at most 82. A negative position would unpack above the width and `record` drops it.
- **Sizing.** Per-group arrays are sized from the previous cycle's largest group, at most ~10k values (1 MB cap / ~100 B per key), so ~120 KB. Vendor sample times are 5-minute aligned (every capture), so only a handful of groups are live at once. `lastLargestGroup` is touched only on the caller thread.
- **Result queue cap.** 16 is production's own value (`ArrayBlockingQueue(Math.max(8, 4 * workers))`, `CycleEngine.java:926`); the harness drives the real engine. (Design §Sizing's table says "depth = workers"; the code has been 4 x workers since before this build, which is not a finding here.)
- **Stream generation.** The harness feeds `PerfParser.parse` a chunked `InputStream`, so the parser's own buffers and per-entity trees are production code and are measured. Only the wire `byte[]` is absent (W4).
- **Pacing.** It throttles the workers, not the caller, so it cannot hide caller-side allocation. The unpaced bound is no higher (33.3 MB).
- **Keys and identities.** `describe.xml` is byte-identical to build 13. `EntityType.java`, `OpsHostMap.java` and `Inventory.java` are untouched, and all identity reads are unchanged.
- **Secrets.** No credential, token or host secret in the diff or the new scripts (the harness uses `"u"` / `"p"` placeholders); no new log line.
- **Build hygiene.** `build_number` is 15; CHANGELOG has entries for 14 and 15. The production delta is 2 files and 70 lines, with no drive-by changes. Docs were regenerated by build-sdk; the generated docs in the tree match the build output (the tree was unchanged after my build).
- **CI runtime.** The suite takes 1 min 35 s; T4 takes 80 s unloaded and 125 s under 4 busy loops. Both fit a GitHub job comfortably, including the tag workflow's test step.

## Not verified here

- The JDK 25 leg of the CI matrix (heap readings and timing).
- A live push-failure cycle on devel. W1 is shown in the engine with the fakes only.

## If shipped as-is

At the default 5-minute interval, operators get the same data as build 14, with a VM-tier heap peak around 35 MB instead of ~71 MB. Two things are off: an instance whose collection interval is shortened to about 2 minutes or less permanently loses samples after a failed push, and the landing page does not say that three cluster-tier groups can appear on hosts.
