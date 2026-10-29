# Review: compliance build 104

- **Date:** 2026-10-28 (America/Chicago)
- **Reviewer:** sdk-adapter-reviewer (static, pre-install; nothing installed, no live instance touched)
- **Adapter repo:** `content/sdk-adapters/compliance`, branch `build-104`, clean tree, one commit `469f331` on `origin/main` `a1376c1` (released v1.0.0.103)
- **Issue in scope:** adapter #17, last box: one batched Suite API push per cycle through buildkit 1.0.24 `SuiteApiStitcher.pushBatch` / `SuiteApiBatchResult`. Framework reference: `knowledge/context/api-surface/suite_api_batch_push.md`, 1.0.24 row of `knowledge/context/tier2_architecture.md`.
- **Author's pak:** `dist/vcfcf_sdk_compliance.0.0.0.104.pak`, sha256 `1dc71f98…c661` (confirmed).
- **Reviewer's pak:** rebuilt from `469f331` into scratch. Unpacked, nested zips walked: 0 class files differ; only container bytes differ (adapters.zip, jar, views.zip, overview.packed). Bundled framework `lib/vcfcf-adapter-base.jar` is byte-identical between the two, `Implementation-Version: 1.0.24`, and contains `SuiteApiBatchResult.class`.

## Verdict: APPROVE (0 BLOCKING, 4 WARNING, 5 NIT)

Nothing in this build turns a failed or missing read into a pass, the stitch identity is untouched, and the push path can't throw into the cycle. The warnings are about scale and blast radius. The build sends a whole cycle as one push at the end, so the batch sits outside the cycle budget and outside Stop Collecting. It holds every resource's values in memory until the flush. And one failed properties request now takes every stat of the cycle down with it, the not-collected signal included. W1 to W3 share one fix: an incremental flush inside the walk.

## Independent verification

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` at `469f331` | **PASS**, exit 0. 29 "all assertions passed" lines (`Build104BatchPushTest` included); BcHandshakeTest ran; Python tests OK. |
| `validate-sdk` | OK. Same environment warnings as build 103: the 8.18.7 and 9.1.1.0100 compat jars are not in `adapter_runtime/`, so those legs were skipped locally. CI runs them. |
| `build-sdk` (output to scratch) | Builds 0.0.0.104. The adapter tree stayed clean (`git status --porcelain` empty before and after). |
| `pak-compare` 104 vs `dist/…0.0.0.103.pak` | PASS, 0 BLOCKING / 0 WARNING / 0 INFO, for both my pak and the author's. |
| describe.xml 103 vs 104 | Byte-identical. No alert, symptom or generator change, so dimension 13 doesn't apply. |
| Stub fidelity | `tests/stubs/.../SuiteApiStitcher.pushBatch(Map<String,? extends Map<String,String>>, Map<String,? extends Map<String,Double>>, long)` matches the real 1.0.24 signature (`SuiteApiStitcher.java:287`). The stub `SuiteApiBatchResult` has a package-private 7-arg constructor and the same getters and `isClean()` rule as the real class. The adapter calls only those members, and it compiles against the real jar in build-sdk. |
| Adapter-to-framework mapping | `ComplianceAdapter.suiteApi()` copies `getSent/getBatchesOk/getBatchesFailed/getFellBack/getSkipped/getDropped/isStopped` into `BatchOutcome(sent, batchesOk, batchesFailed, fellBack, skipped, dropped, stopped)` in order. Correct by reading; no test runs it (N4). |
| Scratch probe: a cycle that throws still flushes | Harness, cycle 1 normal, then `loginFails` + `disconnect()`. Cycle 2 threw `VimOptions$ReadFault`; the `finally` flush sent one batch with `{Rollup|incomplete=1.0}` on `r-vc`, empty props. Works, but no committed test covers it (W4). |
| Scratch heap measurement | Synthetic queue shaped like a 9.0.2 VM (181 properties with shared Description/Expected strings and per-resource keys and Actual, 70 stats): **~38 KB retained per resource, ~189 MB for 5,000 VMs** (W3). |
| buildkit pin | `sdk-buildkit-v1` points at `1bc6473`, newer than `sdk-buildkit-v1.0.24` (`2448234`), so the tag build gets 1.0.24 or later, as the CHANGELOG says. |

No `SDK ADAPTER RESULT` block came with the brief. The claims checked are the brief's, the CHANGELOG's and the commit's.

## The five questions in the brief

### 1. Flush semantics

- **Nothing is sent twice.** `flushPushes` (`ComplianceStitcher.java:915`) copies and clears the queue under `pushLock` before sending. The second flush, from `endPushCycle` in the `finally` (`ComplianceAdapter.java:1101`), finds the queue empty and returns `NONE` without logging. Nothing pushes between the pre-completion flush (`:1366`) and the completion line.
- **Nothing is lost on an exception.** Every exit from `collectWorldCycle` passes the `finally`, including the not-reached path (`markCycleNotCollected`, then rethrow), InterruptedException from StopCheck, and any RuntimeException. I proved the not-reached case live in the harness (table above). `send` catches RuntimeException from `pushBatch` and turns it into WARN + skipped. An `Error` (OOM) propagates, but the queue was already cleared and `pushCycleOpen` is reset in `endPushCycle`'s own `finally`.
- **Stop or reconfigure mid-cycle.** Each configure builds a new `ComplianceStitcher` (`:214`), and the running cycle keeps its holder `c`, so a reconfigure can't clear or open another cycle's queue. The old Suite API client is only `discard()`ed (token released) and re-acquires a token, so the old cycle's final flush still goes out, as its per-id pushes did in 103. Stop Collecting raises InterruptedException through `StopCheck`, which does **not** set the thread interrupt flag. So the `finally` sends the whole queue after the user asked to stop, unbounded by budget or stop flag (W2).
- **A cycle that never opens.** With `c.stitcher == null`, nothing is queued and nothing is pushed. `beginPushCycle` runs before the `try` (`:1066`), so a throw from `CycleBudget.interval(...)` or the budget setup would leave `pushCycleOpen=true` with no flush. The queue is empty at that point, so nothing is lost, and the next `beginPushCycle` clears it (N1).
- **Cleared on every path:** yes, by `flushPushes` (always under the lock) and by `beginPushCycle`.
- **Memory bound:** the queue holds the entire cycle until the end (W3).

### 2. Timestamps

One timestamp per cycle (the cycle start) is correct for VCF Ops and consistent with the adapter's internals:

- Ops stores stats by sample timestamp and properties on change, and accepts timestamps in the past (the live landing proof in the batch-push doc wrote at "now" and older adjacent timestamps alike). The SDK collect convention is one collection timestamp per cycle. I couldn't check the BC / VMware adapter source from this repo; the claim stands on the SDK convention, not on the vendor code.
- **Ordering across cycles holds.** Cycles run in sequence on the collect thread, so cycle N+1's start is after cycle N's start, and every sample is newer than the last one. At the 103-to-104 upgrade, the first 104 cycle starts after the last 103 push, so no sample goes backwards.
- **Staleness:** the budget is 95% of the interval (`CycleBudget.FRACTION`). The last-read object's values are stamped up to about one interval, plus the flush time, before Ops receives them. On a 5-minute interval that's under one collection period. Symptom evaluation and "latest" queries are unaffected. Super metrics read the latest value and see it one cycle at a time, as before.
- **Retired-key repeats (DEF-025):** `fold` and `toPush` both record `pushTs()` as pending, and the object's push and the cleanup's push go out at that same value. `settle` matches the read-back sample time exactly, and because the whole cycle shares one timestamp, the match is easier, not harder. A pending entry whose batch was stopped is dropped as failed on the next cycle's read-back, as a failed per-id push was in 103. `Build96RetiredKeyTest` passes through the fake, which seeds at the batch timestamp.
- **Merge on equal timestamps:** in 103 two pushes to the same key in a cycle were two samples. In 104 they're one, and the later value wins. I found no producer pair that writes different values to the same key in one cycle: `orphanProps`/`orphanStats` touch only retired ids, which `cleanupPlan` keeps out of `p.pushed`, and `toPush` skips keys already folded into the object push. The summary line counts any value that gets replaced, and the fixture cycles count 0.

### 3. Unreadable is not compliant; stitch correctness

- The resource ids, keys and values each producer hands to `pushProperties`/`pushStats` are unchanged; only the timestamp argument changed (`System.currentTimeMillis()` to `pushTs()`). The queue copies every entry (`m.put` into its own LinkedHashMap), so no caller map is aliased. The existing per-object tests run unchanged against the fake's per-resource records and pass.
- A failed, stopped or thrown batch never produces a value: an undelivered key keeps its last stored value, exactly as a failed per-id push did. It never aborts scoring (`send` never throws; tested by `cycleSurvivesNotCleanBatch`). It logs exactly one line: INFO when clean, WARN `Suite API push NOT clean: …` with counts and the reason otherwise (tested).
- Stitch identity (MOID + VMEntityVCID, uniqueness flags) is untouched by this delta.
- The blast radius changed, though: see W1.

### 4. 2xx means accepted, not landed

Every vim25 kind and the vCenter instance are re-listed every cycle (`ComplianceAdapter.java:1710-1748`, `loadVCenterAdapterInstanceByIdentity` clears its indexes before each fetch). A stale id can only come from a resource deleted mid-cycle, in which case nothing is lost: it would have 404'd in 103 too. The one exception is the not-reached path, which pushes to the cached `cycle.lastVcResourceId()` without re-resolving it (N3).

### 5. Test quality

`Build104BatchPushTest` covers: queued pushes merged into one batch, an empty cycle, the outside-cycle path, a non-clean result, a thrown push, a stop across two timestamps, a real 3-host/4-VM cycle as one batch at one timestamp with the vCenter rollup, and a non-clean batch not failing the cycle. Each test asserts specific counts and message text, not just that nothing threw. The `FakeSuiteApi` change (record the batch, then expand it into the old per-resource `Push` records, properties first; `seed` stats at the batch timestamp) is what lets the whole prior suite act as the equivalence check, and it is honest about it. Gaps:

- No test drives a cycle that **throws** (not reached, Stop Collecting) and asserts the `finally` flush (W4).
- The adapter wrapper mapping and the stub's default `pushBatch` are never executed (N4).
- `cycleIsOneBatch` asserts that keys are present, not value equality with 103. Acceptable, because the prior suite asserts the values.

## Findings

### BLOCKING

None.

### WARNING

**W1. One stopped properties request now drops every stat of the cycle, including the not-collected signal.** `ComplianceStitcher.java:939` (`send`) calls the framework `pushBatch`, which runs properties for every resource and then stats. Per the framework contract (`SuiteApiStitchClient.pushBatch`, `:792-799`; the batch-push doc §What the facade does), a 5xx, a 429, a timeout or a token failure in the properties half sets `stopped`, and **the stats half sends nothing**. Properties are about 90% of the bytes (doc §Payload size: 145 KB/host and 56 KB/VM of properties against about 6 KB of stats), so they make up most of the requests and nearly all the exposure. One bad request among them loses `score`, `has_unreadable`, every `|Compliant`, and the vCenter `Rollup|incomplete` for the whole cycle. In 103 the same blip lost one object's push. Ops then shows the previous cycle's scores, `Rollup|incomplete` and `has_unreadable` as current, and the only trace is one WARN in the adapter log. That isn't a fabricated pass: no new value is created, and the next cycle retries. But it is the "stale data looks current" failure that DEF-026 and the build 93 `Rollup|incomplete` work exist to prevent, and the operator gets no in-product signal. Authority: skill § *Unreadable is NOT compliant* (a missing signal must surface), `knowledge/rules/no-fabricated-metrics.md` in spirit, and doc §What a batch API needs item 6 ("keep properties first **if** any adapter depends on it": no dependency is stated for compliance). **Fix:** send stats first, since they are small and carry every alerting signal, by calling `pushStatsBatch` then `pushPropertiesBatch` (add both to the SDK-free `SuiteApi`); or at least push the vCenter rollup and `has_unreadable` stats in their own call ahead of the big properties call. Alternatively, state and test why properties must come first. **Registration candidate** if shipped as-is.

**W2. The flush runs outside the cycle budget and ignores Stop Collecting (DEF-026).** `ComplianceAdapter.java:1366` and `:1101`. In 103 every push happened inside the walk, so its time counted against `CycleBudget` and the walk was cut when the budget ran out. In 104 the walk can use the full 95% budget, and the whole push then follows, unbudgeted. Estimate for a 5,000-VM estate: about 280 MB of property JSON, about 300 properties requests at the 1 MB cap, plus about 30 stats requests. The framework's 120 s read timeout bounds only a hung request (one timeout stops the call); a healthy but slow server is not bounded. Stop Collecting throws InterruptedException from `StopCheck.check` without setting the thread interrupt flag, so the framework's per-chunk `isInterrupted()` check never fires, and the `finally` sends the entire queue after the user asked to stop. That contradicts `StopCheck`'s own Javadoc ("nothing more is read or pushed"). On devel (55 to 66 objects, about 4 to 5 requests) none of this shows. Authority: DEF-026 close condition ("the cycle ends within the budget"); author hard rule on minimal behavioral change. **Fix:** flush incrementally inside the walk, when the queue passes a threshold (resources or estimated bytes) or at the end of each kind, so push time counts against the budget and Stop Collecting is checked between flushes. Or check `budget`/`abortRequested` between per-timestamp sends and push the vCenter rollup first. The same change fixes W3.

**W3. The whole cycle is queued in memory.** `ComplianceStitcher.java:823` (`queued`). Every resource's property and stat maps are held from the first push until the end of the cycle. Measured in scratch: about 38 KB of retained heap per VM-shaped resource, so about 189 MB for 5,000 VMs, plus hosts at about 2.4 times a VM's property count. On top of that, the framework's merged reference copy is held during the send (`pushBatchOf`, `merged`). This lives in the shared collector JVM, where DEF-026 already notes in-process adapters share the heap. In 103 each object's maps were transient. The memory is not unbounded across cycles (it's cleared every cycle), but the peak grows linearly with estate size and has no cap. Authority: reviewer dimension 7 (no holding the whole inventory when streaming would do). **Fix:** the threshold flush in W2, for example at 500 resources or about 16 MB estimated. Devel would still make about 4 to 5 requests.

**W4. Nothing tests the `finally` flush, which is now the only way the not-collected signal is delivered.** In 103, `markCycleNotCollected` sent `Rollup|incomplete=1` immediately. In 104 it's queued, and only the `finally` at `ComplianceAdapter.java:1101` delivers it. My scratch probe confirms it works today, but no committed test would catch a regression, for example someone moving `endPushCycle` or making the not-reached path return early. Stop Collecting mid-walk (what is or isn't sent) isn't tested either. Authority: author hard rule 9 (behavior preservation proved, not asserted). **Fix:** a harness test where cycle 2 fails `ensureConnected` and the last batch carries `Rollup|incomplete=1` on the vCenter resource; and one where `testAbort` trips mid-walk, asserting whatever behavior W2's fix chooses.

### NIT

- **N1.** `ComplianceAdapter.java:1066`: `beginPushCycle` runs before the `try` whose `finally` closes the cycle. Move it to just before `try` (after the budget setup) or inside it, so an open cycle always has its close.
- **N2.** Log lines now say "pushed" before anything is sent: `:1175` ("`Rollup|incomplete = 1 pushed to resource …`") and `:3558` ("`Pushed profile_name=… to resource=`"). Say "queued", or rely on the cycle's push summary. Also update `StopCheck`'s Javadoc ("nothing more is read or pushed"), which the `finally` flush contradicts.
- **N3.** The not-reached path pushes to the cached `lastVcResourceId()` (`Configured.java:64`). If that resource was replaced, the batch drops the id silently. In 103 the per-id 404 at least logged a framework WARN. `docs/overview.md` says "stale ids are caught by the per-cycle resource list, as before", which isn't true for this one id. Either say so in the overview or try `matchVCenterAdapterInstance` first.
- **N4.** The `ComplianceAdapter.suiteApi()` field mapping and the stub's default `pushBatch` (`tests/stubs/.../SuiteApiStitcher.java`) are never executed: every test injects `FakeSuiteApi` straight into the stitcher. The mapping is correct by reading. One test through `SuiteApiStitcher.testFactory` would pin it against a future field reorder.
- **N5.** The outside-cycle path (`pushProperties`/`pushStats` with no cycle open) logs one INFO summary per push. There's no production caller today. If one is ever added in a loop, that's per-object log spam: log at DEBUG for single-resource sends.

## Docs parity

`docs/overview.md` gains an accurate paragraph (one batched push, caps, one timestamp, the INFO/WARN lines, accepted-not-landed). `docs/README.md` and `inventory-tree.md` change only the version, which is correct: no new relationship, resource kind or capability is visible in the product. The CHANGELOG line is accurate except where W2 and N2/N3 note. `build_number` is bumped to 104 and the CHANGELOG has a matching entry. The diff is minimal and limited to the push path.

## Registry check (`knowledge/context/defects.md`)

| Defect | Status in build 104 |
|---|---|
| DEF-025 (retired-key -1 repeats) | **Still open, unchanged in substance.** `RetiredKeyRepeats.fold`/`toPush` now receive the cycle timestamp (`ComplianceAdapter.java:1904`, `:2178`). The exact-time read-back still matches, and `Build96RetiredKeyTest` passes. The devel evidence still owed (an open alert on a retired control cancelling within three cycles) is unchanged. No closure proposed. |
| DEF-026 (no per-cycle deadline / stop) | **Still open, and build 104 moves away from its close condition.** The new end-of-cycle flush is outside `CycleBudget` and not interruptible by Stop Collecting (W2). The throttled/unreachable-vCenter devel proof is still owed. No closure proposed. |
| DEF-022, DEF-023, DEF-024 | Closed; not re-asserted. |

Registration candidates: **W1** (one failed properties request loses all stats, including the not-collected signal, for the cycle), plus **W2/W3** if the fix is deferred past the next tag (likely as a note on DEF-026 rather than a new entry).

## If shipped as-is

On devel-sized estates operators see the same values with about 4 to 5 Suite API calls per cycle instead of about 130. On a large estate, cycles run past their budget by the length of the push, Stop Collecting waits for it, the collector holds a few hundred MB extra at the end of each cycle, and any Suite API blip during the properties push leaves that whole cycle's scores and not-collected flag stale, with only a log WARN.
