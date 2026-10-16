# Compliance build 96 review

- **Reviewer:** sdk-adapter-reviewer (read-only, static, pre-install)
- **Date:** 2026-10-16
- **Adapter:** `content/sdk-adapters/compliance/`, branch `fix/build-96-reliability`, 11 commits `34aa6ed..bcf4858` on `origin/main` `9acee93` (0.0.0.95, untagged). The brief said 12; `git log origin/main..HEAD` lists 11.
- **Pak reviewed:** `dist/vcfcf_sdk_compliance.0.0.0.96.pak` (sha256 `8440a375...73785`), reference `dist/vcfcf_sdk_compliance.0.0.0.95.pak`
- **Design:** `knowledge/designs/sdk-adapters/compliance-build-96-reliability-and-hygiene.md` items 1 to 14; recon `knowledge/context/investigations/2026-10-16-compliance-52-30-31-recon.md`

## Verdict: CHANGES REQUESTED (1 BLOCKING, 3 WARNING, 7 NIT)

Scoring is untouched, the build reproduces, and every author claim checks out. #52, #42, #26 and the #27 test infrastructure are correct. The one blocker is in #16. The budget always stops at the same point in the inventory and the next cycle starts again from the top, so any vCenter whose full walk takes longer than 80% of the interval never collects the objects after that point. Those objects keep their old scores, with a stale "Not Read" = 0 beside them, indefinitely. One host whose hostd hangs is enough to cause this on its own. Before this build the same vCenter finished late. Now the tail is never collected.

## Independent verification

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` on a clean `git archive HEAD` tree (JDK 17.0.20.1) | Exit 0. 26 `*Test.java` (all "all assertions passed", BcHandshakeTest included, jars fetched), 10 `tests/test_*.py` OK. **Confirmed.** JDK 25 not run locally. |
| SimpleJson parity (`tests/test_test_stubs.py`) | Skipped in the archive (factory not beside it). In the real clone it compares and passes (byte-identical to the factory copy). In CI it always skips (N4). |
| `generate_compliance_alerts.py --check` | Up to date (136 control alerts, 6 collection, 1 overrides). **Confirmed.** `describe.xml` not touched by the branch, so dimension 13 is not triggered. |
| `validate-sdk` (clean tree) | OK, exit 0. **Confirmed.** |
| `build-sdk` (clean tree) | Built 0.0.0.96. Every file in the author's pak is byte-identical to mine after unpacking: all 105 jar entries, `views.zip` content, the `overview.packed` content, dashboards, describe. Only the zip timestamps differ. **Confirmed.** |
| Jar content | `vcfcf_compliance.jar` holds `META-INF/MANIFEST.MF`, `adapter.properties` and `com/vcfcf/adapters/compliance/*` only. No `com/integrien`, no `com/vcfcf/adapter/*`, no test, stub, fake or harness class. **Confirmed.** |
| Stubs vs the real SDK | `javap` on `alive_common.jar`: `AdapterBase.getMonitoringIntervalInSec()` and `ResourceConfig.getIntervalInSec()` are both `java.lang.Integer`, and the first returns the adapter instance's `ResourceConfig.getIntervalInSec()`. The stub signatures match. |
| `pak-compare` 0.0.0.96 vs 0.0.0.95 | PASS, 0 BLOCKING / 0 WARNING / 0 INFO. **Confirmed.** |
| #33 in the built pak | `content/dashboards/VCF_Content_Factory_Compliance_ESX_Hosts/dashboard.json`, Host Score Heatmap: `minValue 0.0`, `maxValue 100.0`, `thresholds {"values":[0,80,95],"colors":["#DE3F30","#ECC33E","#74B43B"]}`, `solidColoring true`, colour by `VCF-CF Compliance|score`. Red below 80, amber 80 to 95, green from 95. **Confirmed.** |
| Em-dashes in added lines | None (the generated docs are not touched by this diff). |

## Hard rule: no change to evaluation or scoring

`git diff origin/main...HEAD` on the evaluation path:
- `ControlEvaluator.java`: only the removal of `evaluateAdvancedSettings`.
- `BenchmarkSelector.java`, `ComplianceRollup.java`, `profiles/`, `views/`, `dashboards/`, `describe.xml`: unchanged.
- `ComplianceDecisions.java`: one comment, `heldNotEvaluatedControls` (cleanup only, -1 keys, outside every score) and the new `resourcePageOutcome` overload (stitcher only).
- `LastBenchmarkMemory.java`: javadoc only.
- The adapter's `decide` call: WARN text only.

A cycle that never reaches its budget or breaker takes no new branch except `heldNotEvaluatedControls`, which pushes -1 keys only. Scores are unchanged for any cycle that finishes inside the budget. **Confirmed.** A cycle that ends early can change one object's score (W2).

## Item by item

**#52 (255cdd7): correct.**
- An empty but valid list (empty `resourceList` with total 0 or no pageInfo, or no list with total 0) is `EMPTY_UNCONFIRMED` only when `collected == 0`, the last complete count was above 0, and the previous read was not already a held empty (`ComplianceDecisions.java:686-696`).
- The held mark is removed at the start of every read (`ComplianceStitcher.java:350`), so a failed read in between clears it, and the next empty list is held again (tested).
- `lastCompleteCount` moves only on COMPLETE (`:384`).
- The kind stays in `failedLoads`, so it is held back by the existing DEF-023 path: incomplete = 1, and Host, All and Benchmark keep their values (tested through `AdapterHarness`).
- A new stitcher has no history, so its first empty list is accepted (tested).
- Reconfigure: the history does **not** survive it, exactly as the author says. `configureAdapter` builds a new stitcher (`ComplianceAdapter.java:213`), so the first cycle after every restart or instance edit accepts an empty list (N1).
- The one-cycle "Compliance data not collected (vCenter)" alert on a genuine removal (symptom wait 1, cancel 1, `describe.xml:1846-1851`) is not documented outside the CHANGELOG (W3).
- Interrupt: both catches restore the flag (`ComplianceStitcher.java:417-420`, `:611-614`). `StopCheck.orInterrupted` uses `isInterrupted()` (non-clearing), and no `Thread.interrupted()` is called in `src/`. The next `stop.check` (the first host, or the cleanup batch at `:1548`) ends the cycle. Calls made before that point (vCenter version, host listing) still run, because HttpURLConnection ignores the flag. Acceptable.

**#41: fixed on main, confirmed.**
- `afterPush` adds the Skip ids to the live set, and the Skip -1 goes out in the object's own push every cycle (build 92, `4e3e059`).
- Doc half: `docs/overrides.md:37-59` has the Management Packs Configuration path, the `.xml_Copy` default, and "without `.xml`".
- No "Administration > Configuration Files" remains.

**#42 (a47ceba): correct, but the cost is unbounded (W1).**
- `heldNotEvaluatedControls` returns only plan keys whose latest value is -1. It compares a `Double` with a `double` constant, so it unboxes (no reference compare). It never creates a key, and a failed read pushes nothing.
- The held keys go out in the same two calls as the retirement.
- `Build96RetiredKeyTest` asserts the -1 on cycles 1, 2 and 3 through the adapter.

**#18: fixed on main, confirmed.**
- `listOrHoldBack` (`ComplianceDecisions.java:740-749`) gives one WARN, `markIncomplete(HOST)` and an empty map. `memory.retain(seen, incompleteKinds())` (`ComplianceAdapter.java:928`) does not trim a held-back kind.
- The new orchestration test runs this through the real `collectWorld`.

**#16 (3294aff): the mechanism is correct. The ordering starves (B1).**

What I confirmed:
- The interval chain and the 80% budget. Out-of-range intervals fall back to 300 s rather than clamp (N3).
- Refusal happens before any connection (`VSphereClient.java:2239-2246`, `EsxcliSoapClient.java:662`) as `Exhausted`, which is an IOException.
- The breaker counts only `SocketTimeoutException`, connect or read. The answer reset happens after the body is fully read or a fault body is drained, and a stall mid-body is a timeout.
- `Logout` goes through `postOnce`, never refused.
- A limit during the host listing: `listOrHoldBack` catches `Exhausted` and holds Host back.
- A limit between kinds: every collector calls `cycleOver` on entry, which marks its kind incomplete. `retain` skips incomplete kinds, so no object that was never listed is trimmed.
- incomplete = 1 uses the same `markIncomplete` path DEF-023 uses.
- Cleanup and shadow are skipped on an early end (`:1528`, `:1984`).

On the 30 s cheap-read timeout:
- A vCenter that is slow but healthy and takes over 30 s for one scalar `RetrieveProperties` is rare. The result is then UNREADABLE (a version read falls back to the last benchmark), plus one breaker count that the next answer resets. It is never a pass.
- A keepalive misfire costs a logout and re-login, not the cycle.
- Acceptable.

**#23, #24, #25: fixed on main, confirmed.**
- `connectOnce` commits the session fields only after Login returns a cookie, and `releaseClients` runs on reconfigure (`ComplianceAdapter.java:227`).
- `MAX_SOAP_RESPONSE_BYTES` = 64 MB, parsed from the capped stream (`VSphereClient.java:197`, `:2386`).
- `basicAuthorization` encodes UTF-8 (`ComplianceDecisions.java:42-46`), and no bare `getBytes()` is left in `src/`.

**#26 (7f95a0a): correct.**
- `testSoapLogin` connects, classifies certificate failures like the REST step, and disconnects in `finally`. `disconnect` sets `closed` and sends Logout only if a session cookie exists.
- No credential reaches a message: the Login fault text comes from vCenter.
- Suite API WARN-only is the right call. Test Connection can run on a node that does not serve the Suite API, and failing there would block saving a working account. The framework note the author cites agrees.
- The custom-profile bullet is moot: build 92 removed custom profiles.

**#27 (34aa6ed): correct, no runtime change.**
- `ComplianceStitcher.SuiteApi` mirrors the framework methods with the same checked exceptions (`IOException`, `InterruptedException`) and passes arguments by reference (no copies).
- The stitcher used only `info`, `debug`, `warn` and `isDebugEnabled` before, and all four map one to one in `clientLog`. A null logger now becomes a no-op instead of an NPE.
- The stubs carry signatures plus named test hooks, and `test_src_uses_no_test_hook` guards `src/`.
- `AdapterHarness` calls the real private `collectWorld` by reflection. It installs the configured holder directly, so `configureAdapter` itself is not exercised.

**f771fd2 (deflake): a real fix.** The assertion is unchanged ("the end line ends with the summary passed in"). The old test called `summary()` twice, and the two calls could straddle a millisecond. Nothing was loosened.

**#28 (c035b4e): confirmed dead.** `git grep evaluateAdvancedSettings origin/main` finds only the declaration.

**#43 (70d7396): docs present.**
- `installing.md` has the IP-host dialog and the non-resolving host behaviour.
- `overrides.md` and `data-reference.md` already had "fetch failed".

**#33: confirmed in the built pak** (table above).

**N17 (ec8a3c7): correct**, WARN and javadocs.

**CHANGELOG:** one line each for #52, #42, #18, #16, #26, #28, #43, #27 and N17. There is no build 96 line for the confirmations of #23, #24, #25, #33 and #41 (N7).

## Findings

### BLOCKING

**B1. The cycle budget starves the end of the inventory permanently. Every cycle stops at the same point and restarts from the top, so objects past that point are never collected again.**
- Where: `ComplianceAdapter.java:909-921` (fixed order: hosts, VMs, then the vCenter object, vDS, portgroups, clusters), `:648` (`cycleOver`), and `:740-760` (a fresh budget each cycle, with no record of where the last cycle stopped).
- Contributing: `VSphereClient.java:794` (host `QueryOptions` keeps 120 s) and `EsxcliSoapClient.java:679` (esxcli keeps 120 s).
- Authority:
  - `knowledge/lessons/unreadable-is-not-compliant.md` ("never ... a healthy-looking datapoint").
  - DEF-026's own summary ("stale data reads as current").
  - Skeptic default: there is no evidence that a full cycle fits in 240 s on a large vCenter. The only timings on record are about 17 s on the 3-vCenter devel lab (`compliance_esx04_partial_collection_2026_06_10.md:112`).
- Failure scenario 1, a large estate: a vCenter with a few thousand VMs whose per-object walk takes 6 minutes.
  - Build 95 finished every cycle, late.
  - Build 96 stops at second 240 in the VM loop every cycle.
  - The VMs past that point, the vCenter appliance object (15 control alerts), every vDS, portgroup and cluster are never read again.
  - Their scores, Controls Evaluated and per-control keys keep their last values, and "Not Read" (`has_unreadable`) keeps its last value of 0 beside them on every per-object view.
  - The only signal is the vCenter's "Compliance data not collected", which never clears. The operator's only lever is the collection interval, which no doc mentions.
- Failure scenario 2, one host whose hostd hangs while vCenter still reports it connected:
  - Its `QueryOptions` (a host-side OptionManager call that vCenter relays to hostd) waits 120 s, then its first esxcli command waits another 120 s. Build 86 marks the host after that, for esxcli only.
  - That is the whole 240 s budget for one host. Every cycle ends at that host, so the hosts after it, all VMs, the vCenter object, the network and the clusters go dark until the host is fixed.
  - The breaker does not trip, because the other hosts' answered calls reset it between the two timeouts.
- Smallest correct fix:
  1. Guarantee a bounded visit interval. Record in the configured holder where an early-ended cycle stopped (kind and object index or MOID), and start the next cycle with the kinds and objects it skipped. At minimum, collect the small kinds (vCenter, vDS, portgroup, cluster) before VMs, and rotate the host and VM start offset after an early end.
  2. On a timeout of a host-relayed vim25 call (`QueryOptions`), mark the host unreadable for the rest of the cycle, the same way build 86 marks it for esxcli.
  3. Test: two consecutive budget-ended cycles together visit every object.
  4. Docs (overview, data-reference): what a cycle that always ends early means, and that the remedy is a longer collection interval.

### WARNING

**W1. #42: the -1 repeat costs two Suite API calls per object per cycle, forever, and runs outside the budget.**
- Where: `ComplianceAdapter.java:1625-1650`, `:1528` (the budget is checked once, at cleanup entry); `ComplianceDecisions.java:604-618`.
- Authority: reviewer dimension 8, and DEF-026's purpose (bound the cycle).
- What happens:
  - The key never stops being -1, because the adapter keeps pushing it, so the repeat never ends.
  - After a fleet upgrade (SCG 8.0 to 9.0), every host and VM holds retired keys. 3000 objects is 6000 extra pushes per cycle. At typical Suite API latency that is minutes, added after collection and not covered by the budget, so the cycle overruns the interval this build set out to protect.
  - The alert needs only 3 fresh non-failing samples (the control symptoms' cancel cycles).
- Is an uncapped repeat acceptable? No.
- Fix, either:
  - Bound it with an in-memory per-object counter: stop after cancel cycles + 1 (4) pushes. A restart re-pushes at most 4 times, which is harmless.
  - Or carry the held ids into the object's own per-cycle push next cycle, the way build 92 does for Skip (zero extra calls).
  - Either way, check the budget per cleanup batch.

**W2. The object being read when the limit hits is pushed with a score over only the controls read before the cut.**
- Where: the host and VM loops (`ComplianceAdapter.java:1746-1750`, `:2071-2075`). The budget is checked only before each object, so the object in flight is evaluated with its remaining reads refused (UNREADABLE) and then pushed.
- Authority: lesson contract 1 permits skip-and-flag, which is why this is a WARNING; reviewer dimension 3.
- Scenario:
  - The devel host `vcf-lab-mgmt-esx01` sits at 64.58 (17 of 48 failing). The cut lands after 5 passing reads, so it is pushed as 100 (5/5) with Not Read = 1.
  - The heatmap tile goes green for that cycle.
  - If it is the last object of its kind, the kind is never marked incomplete, so the partial object is folded into the kind's rollup.
  - If it is the last cluster, `Rollup|incomplete` stays 0 and no "ENDED EARLY" is logged, while the cleanup logs "the cycle ended early".
  - This is self-inflicted: the adapter chose to stop.
- Fix: after an object's evaluation and before its push, if `budgetExhausted()`, do not push the object (it keeps its last values, as an unvisited object does) and mark the kind incomplete.

**W3. Docs parity (dimension 11).**
- Where: `docs/data-reference.md:226-230`, `README.md`, `docs/overview.md`.
- What's missing:
  - #52's held-back cycle, and the one-cycle "Compliance data not collected (vCenter)" alert when the last object of a kind is genuinely removed, appear only in the CHANGELOG.
  - The `Rollup|incomplete` definition lists neither the early end nor the unconfirmed empty list.
  - The landing README says nothing about the cycle limit.
  - No doc says what to do when every cycle ends early (B1).
- Fix: add all of these.

### NIT

- **N1** `ComplianceStitcher.java:135` / `ComplianceAdapter.java:213`: the #52 history lives in the stitcher, which is rebuilt on every configure. So the first cycle after a VCF Ops or collector restart (plausibly when a transient empty list is most likely) still reads an empty list as zero, with incomplete 0. This is documented in code and the CHANGELOG, and the cost is visible (unmatched > 0, for one cycle). Accept it, or seed the history from the kind's last pushed `Rollup|<K>|scored`.
- **N2** `EsxcliSoapClient.java:440-446`: `Exhausted` is an IOException, so a refused esxcli call marks the host "unreachable" with the reason `Exhausted: cycle ended early...`. The host's unreachable report then reads like a host fault. Fix: catch `CycleBudget.Exhausted` first, and fail the command without marking the host.
- **N3** `CycleBudget.java:70-87`: an interval outside 60 s to 24 h falls back to 300 s (the docs say "not believed"); it is not clamped as the brief described. A 25 h interval gets a 240 s budget.
- **N4** `tests/test_test_stubs.py:44-48`: the SimpleJson parity check can never run in CI, only in a clone nested in the factory. Pin the framework copy's sha256 in the test so CI catches local edits to the vendored copy.
- **N5** `CycleBudget.java:13-14` ("cannot hold the collector thread past the next scheduled cycle"): the budget is checked before a call and does not cancel one in flight. Worst case is the budget plus one connect and read (30 + 120 s), so 390 s on a 300 s interval. Reword the javadoc and overview to say "about".
- **N6** The VAMI and vCenter REST calls in `collectVCenter` are outside the budget and the breaker.
- **N7** No build 96 CHANGELOG line records the confirmations of #23, #24, #25, #33 and #41 (design items 2, 6, 7, 9, 12 say "confirm / close with evidence"). The evidence is only in this report.

## Registry check (`knowledge/context/defects.md`; no `defects.local.md` in this clone)

Open defects with `Affects: compliance`: DEF-023, DEF-025, DEF-026.

- **DEF-023: code-side close condition met; propose close.** The close condition names "a log line or a test fixture over 10,000 objects" as the owed item. Evidence:
  - `Build96StitcherTest.elevenPages` (255cdd7) runs the real `fetchResources` loop over 105,000 rows in 11 pages: complete, every row indexed, a last-page row matches.
  - `failedReads` covers an HTTP error, a timeout, an interrupt, an unparseable body and an empty page short of its total, each held back.
  - The adapter-cycle test shows the hold-back reaches `Rollup|incomplete`.
  - All pass on JDK 17 here.
  - The devel alternative (an exercised failed list) is still unobserved. The orchestrator decides whether the fixture alone closes it.
- **DEF-025: open; code half met.** The fix landed (`ComplianceAdapter.java:1625-1650`, `ComplianceDecisions.java:604`) with `Build96RetiredKeyTest` asserting the -1 on cycles 1 to 3. Still owed: devel evidence that an open alert on a retired control cancels within three cycles of a version change. W1 (unbounded cost) should be settled first.
- **DEF-026: open; code half landed, but B1.** The budget and breaker are in (`CycleBudget.java`, `ComplianceAdapter.java:740-760`) with `Build96BudgetTest`. The devel check (an unreachable vCenter ends inside the budget with incomplete 1) is still owed. B1 is a new failure in the same area, and it should be fixed before any closure is proposed.

**Registration candidates (orchestrator's call, RULE-012):**
- B1 if it survives: permanent loss of collection for the end of the inventory, with stale per-object values.
- W1: an unbounded per-cycle Suite API load that grows with every guide-version change.

## If shipped as-is

On small inventories like devel, nothing visible changes except that retired-control alerts now clear. On any vCenter whose walk takes more than 80% of the collection interval, or that has one host with a hung hostd, everything after the cut point stops being collected for good. That includes the vCenter appliance, distributed switch, portgroup and cluster compliance, plus the host and VM tail. Those objects keep showing their old scores, and only the vCenter-level "not collected" alert says otherwise.

## Round 2 (2026-10-16, branch at `d3fa2b5`)

- **Scope:** 3 commits on `bcf4858`:
  - `56ccd70`: code for B1, W1, W2, N2, N3, N5, N10.
  - `5940891`: docs for W3, B1, N1, N7.
  - `d3fa2b5`: N4.
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.96.pak`, sha256 `13292a60...51f1a`.

### Verdict: CHANGES REQUESTED (1 BLOCKING, 0 WARNING, 2 NIT)

W1, W2, W3 and N2 to N7 are closed, and N10 is fixed as well. B1 is only half fixed.
- **What works:** small kinds first, resume within a kind, the hung-host mark, and no partial score. Hosts are covered across cycles.
- **What doesn't:** the resume point is per kind, and every cycle still starts again at the small kinds and then hosts. VMs run only after a full host pass fits inside one cycle's remaining budget. When the host walk alone overruns, VMs are never collected. The author reads this as "VMs can wait a cycle"; in fact they wait indefinitely. Separately, an object that takes longer than the budget left when it starts is aborted every cycle, so the cursor never moves past it.

### Independent verification

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` on a clean `git archive d3fa2b5` tree (JDK 17.0.20.1) | Exit 0. 26 Java tests (all "all assertions passed", BcHandshakeTest with jars) and 10 Python checks OK. **Confirmed.** |
| N4 pin | `test_simple_json_matches_the_pinned_framework_sha256` ran in the archive. The pinned `501451fe...da2fe` equals the sha256 of both the vendored copy and the factory's `SimpleJson.java`. |
| `validate-sdk` | OK. **Confirmed.** |
| `build-sdk` | Built. Every unpacked file matches the author's pak (jar classes, views, overview, dashboards, describe). The jar adds `ResumeCursor` and `RetiredKeyRepeats` and still has no stub or test class. **Confirmed.** |
| `pak-compare` vs 0.0.0.95 | PASS, 0 / 0 / 0. **Confirmed.** |
| `generate_compliance_alerts.py --check` | Up to date. `describe.xml` untouched. |
| Scoring | `git diff origin/main...HEAD` on `ControlEvaluator`, `BenchmarkSelector`, `ComplianceRollup`, `profiles/`, `views/`, `dashboards/` and `describe.xml` shows only the 7-line `evaluateAdvancedSettings` removal. Round 2 changes only order, which objects get pushed (abort), and cleanup. **Scoring untouched, confirmed.** No per-object score depends on order, and a kind's rollup is pushed only when the kind was fully read. |
| Em-dashes in added lines | None. |

### The coordinator's hunt list

**A cursor that never advances: yes, it can (B1-r2, part b).**
- `KindWalk.abortObject` records `stoppedAfter(kind, done)` with the object *before* the aborted one, so the next cycle starts with the aborted object again (`ComplianceAdapter.java` KindWalk; `ResumeCursor.java:56-59`).
- If that object takes longer than the budget left after the small kinds, it is aborted again every cycle. The cursor never moves, and nothing after it in the kind (or in any later kind) is read again.
- Example 1: a host whose hostd hangs costs one `QueryOptions` read timeout (120 s, plus up to 30 s connect) per cycle, because the hung mark is cleared by `beginCycle`. On a 5-minute interval it pins the host walk whenever the small kinds take over about 90 s.
- Example 2: on any interval under about 3 minutes (budget 144 s or less), it pins the walk outright.
- A pinned hung host is never pushed either, so it never gets its own `has_unreadable` flag.
- `abortObject` decides by elapsed time, not by whether a call was refused for this object (N2-r2), which widens the window slightly.

**A cursor surviving a reconfigure wrongly: no.**
- `ResumeCursor` and `RetiredKeyRepeats` live in `Configured` (`Configured.java:35-39`), which `configureAdapter` builds fresh. A reconfigure starts every walk from the top and drops the repeat counts. Both are safe defaults: at most one extra round, or 4 more -1 pushes.
- A cycle still running on the old holder writes to the old holder only (the per-cycle `cycle` copy).
- A cursor whose MOID is gone falls back to listing order (`ResumeCursor.java:44`).

**memory.retain trimming objects skipped by the cursor: no.**
- A walk that ends early goes through `cycleOver`, and an abort goes through `markIncomplete`. Both put the kind in `incompleteKinds()`, which `retain(seen, incompleteKinds())` never trims.
- A kind that completes its rotated walk has every object in `seen`.
- `walk.finish()` for hosts and VMs runs only when the kind is pushable, so a held-back kind keeps its cursor.

**W2 and the #52 hold-back: no conflict.**
- A kind held by `EMPTY_UNCONFIRMED` is in `failedLoads`. `kindPushable` is false, so its objects match nothing and nothing is pushed. An abort in that kind calls `markIncomplete` again, which is harmless.
- `walk.finish()` is unconditional for vDS, portgroups and clusters. That clears their cursor after a held but fully walked kind, which is correct, because every object was visited.
- The vCenter object's own abort (`budgetExhausted()` after its reads) holds VCENTER back. It does not touch #52.

### Prior findings

- **B1: still BLOCKING, narrowed** (below).
- **W1: closed.**
  - `RetiredKeyRepeats` caps -1 at 4 pushes per key, the retirement included.
  - `toPush` runs for every object in the plan, so a key that leaves the retired set is pruned and counts afresh if it retires again.
  - The budget is checked before every cleanup batch.
  - Tests: the decision table (pushes 1 to 4, then capped, a per-object count, a fresh retirement) and the adapter cycle (-1 on cycles 1 to 4, none on cycle 5).
  - Residual: N1-r2.
- **W2: closed.** An object read while the limit was reached is not pushed or counted. Its kind is held back, and the next cycle starts with it (host, VM, vDS, portgroup, cluster and the vCenter object). `noPartialScore` asserts that `r-host-10` keeps its earlier score and gets no push. This is also the source of B1-r2 part b.
- **W3: closed, except where the docs now overpromise** (part of B1-r2).
  - `data-reference.md` `Rollup|incomplete` now lists #52 and the early end.
  - The one-cycle alert on a genuine removal, and the restart behaviour (N1), are documented.
  - README, overview and installing describe the limit and its remedy.
- **N1: closed** (documented).
- **N2: closed.** `CycleBudget.Exhausted` is caught before IOException, so the host is not marked and the reason reads `esxcli-budget-reached`.
- **N3: closed** (clamped 60 s to 24 h, and the source names the clamp).
- **N4: closed** (the pin runs in CI).
- **N5: closed** (the javadoc and overview give the 390 s worst case).
- **N6/N10: closed.** VAMI `send` checks the budget, counts an `HttpTimeoutException` and resets on an answer.
- **N7: closed** (confirmations CHANGELOG line).

### Findings

#### BLOCKING

**B1-r2. VMs can still starve permanently, and an object longer than the remaining budget pins its kind's cursor.**
- Where: `ComplianceAdapter.java` `collectWorldCycle` (always small kinds, then hosts, then VMs), `KindWalk.next` / `abortObject`, `ResumeCursor` (one cursor per kind, none across kinds).
- Authority: `knowledge/lessons/unreadable-is-not-compliant.md` ("never ... a healthy-looking datapoint"); DEF-026's summary; reviewer dimension 11, because the docs now contradict the behaviour. README: "the next cycle carries on from where it stopped, so every object is still read every few cycles". `data-reference.md`: "every object is still read every two or three cycles". `overview.md`: "consecutive early-ended cycles together read every object" and "one hung hostd cannot use up the budget".
- **(a) VM starvation.**
  - The host walk ends only on the limit or after its whole rotated list, and `collectVms` runs only after it. So VMs are read only in a cycle where small kinds plus one full host pass fit in the budget.
  - Scenario, two hosts with hung hostd at the default 5-minute interval:
    - Each costs one 120 s `QueryOptions` timeout per cycle.
    - Cycle N: H1 is pushed, then the limit is reached inside H2, so H2 is aborted.
    - Cycle N+1 starts at H2, wraps round, and H1 is aborted.
    - The pattern alternates, and the VM walk is never entered.
  - Every VM keeps its old score and per-control keys, with a stale "Not Read" = 0, until both hosts are fixed. A vCenter with a few hundred healthy hosts gets the same result with no fault at all.
  - `twoCyclesVisitEverything` uses hosts only, so it cannot catch this.
- **(b) A pinned cursor.** As above: an aborted object is retried first, and an object longer than the budget left after the small kinds is aborted every cycle.
- Smallest correct fix:
  1. One resume point across kinds. When a cycle ends early in kind K, the next cycle starts at K's cursor and carries on through the kinds after K (VMs after hosts) before wrapping to the small kinds and hosts. Every object is then visited within a bounded number of cycles, whatever the per-kind sizes.
  2. An object aborted on two consecutive cycles is pushed on the second with what was read (refused reads UNREADABLE, `has_unreadable` = 1, the build 95 skip-and-flag rule), or the cursor steps past it. Either way the walk always advances.
  3. Tests: a harness with hosts and VMs where the host walk alone exceeds the budget, asserting every VM is pushed within N cycles; and an object longer than the budget, asserting the objects after it are reached.
  4. Bring the README, overview and data-reference sentences in line with whatever the fix guarantees.

#### NIT

- **N1-r2** `RetiredKeyRepeats.java:93-125`: entries are pruned only when the object is cleaned again, so objects that leave inventory keep their counts for the life of the configuration. That is slow growth with VM churn on a long-running collector. Drop entries for resource ids absent from this cycle's `pendingCleanup` when a cleanup completes (or reuse `retain`'s seen set).
- **N2-r2** `KindWalk.abortObject`: decides on `exhausted()`, which is also true when the deadline passes after an object's last read (during evaluation). A fully read object can therefore be dropped. Prefer "a call was refused while this object was read" (a refusal count on `CycleBudget`, compared before and after the object).

### Registry check (round 2)

- **DEF-023:** unchanged since round 1. Propose closing it on the 105,000-row fixture (orchestrator's call).
- **DEF-025: open; code half met.**
  - The repeat is now capped at 4 pushes (`RetiredKeyRepeats`; `Build96RetiredKeyTest` cycles 1 to 4, none on 5).
  - Devel evidence (an open alert on a retired control cancels within three cycles) is still owed.
- **DEF-026: open.** The budget, breaker, hung-host mark and resume are in, with tests. B1-r2 has to be fixed before closure can be proposed, and the devel check is still owed.

**Registration candidate:** B1-r2 if it survives (permanent VM starvation while the docs promise full coverage).

### If shipped as-is (round 2)

Small inventories behave correctly, and retired-control alerts clear after 4 pushes. On a vCenter where two hosts have hung hostd, or where the host walk alone takes more than about 4 minutes, VM compliance stops updating altogether, while the docs say every object is still read every few cycles.

## Round 3 (2026-10-16, branch at `fab413c`)

- **Scope:** 2 commits on `d3fa2b5`:
  - `b0d00e7`: code for B1-r2, N1-r2, N2-r2.
  - `fab413c`: docs.
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.96.pak` (built 11:39 AM), sha256 `2fc2d279...`.

### Verdict: APPROVE (0 BLOCKING, 0 WARNING, 0 NIT)

B1-r2, N1-r2 and N2-r2 are closed. Every object is now visited within a bounded number of cycles, no single object can stop the walk from advancing, scoring is untouched, and the build reproduces.

### Independent verification

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` on a clean `git archive fab413c` tree (JDK 17.0.20.1) | Exit 0. 26 Java tests (all "all assertions passed", including `vmsNotStarved`, `objectLongerThanBudget`, `deadlineAfterReadsDoesNotDrop`; BcHandshakeTest with jars) and 10 Python checks OK, including the SimpleJson sha256 pin. **Confirmed.** |
| `validate-sdk` | OK. **Confirmed.** |
| `build-sdk` | Built. Every unpacked file matches the author's pak (jar classes, views, overview, dashboards, describe). The jar holds only `com/vcfcf/adapters/compliance/*`, `META-INF` and `adapter.properties`. **Confirmed.** |
| `pak-compare` vs 0.0.0.95 | PASS, 0 / 0 / 0. **Confirmed.** |
| `generate_compliance_alerts.py --check` | Up to date. `describe.xml` untouched. |
| Scoring | `git diff origin/main...HEAD` on `ControlEvaluator`, `BenchmarkSelector`, `ComplianceRollup`, `profiles/`, `views/`, `dashboards/` and `describe.xml` is still only the 7-line `evaluateAdvancedSettings` removal. **Untouched, confirmed.** |
| VMs before hosts | `vmHostVersion` uses the same `getHostProductVersion` (`summary.config.product.version`, then `config.product.version`) as `collectHosts`, and `resolveVmHostVersion` caches it per host for the cycle. Same benchmark choice, one extra read per host and not one per VM. |
| Em-dashes in added lines | None. |

### Prior findings

**B1-r2 (a), VM starvation: closed.**
- `ResumeCursor.round()` (`ResumeCursor.java:105`) starts at `startKind`, runs to the end of `ROUND` (`:94`: vCenter, vDS, portgroups, clusters, hosts, VMs) and wraps.
- `collectWorldCycle` iterates that round and sets `startAt(cycleEndedIn)` after it (`ComplianceAdapter.java:1044-1085`).
- Within the start kind, `order` returns only the tail after the cursor, not a rotation, so the walk leaves the kind at the end of its list and goes on to VMs.
- Trace, the round 2 scenario (two hung hosts at the default interval):
  - Cycle N stops in hosts after H1.
  - Cycle N+1 starts in hosts at H2, finishes the host tail, then reads VMs, then wraps to the small kinds. If it stops in VMs, N+2 starts there.
  - VMs are reached every pass.
- `vmsNotStarved` asserts all three VMs are pushed while every cycle ends early inside the host walk.

**B1-r2 (b), cursor pinning: closed.**
- `afterRead` (`ComplianceAdapter.java:751`) drops an object only when `CycleBudget.refusals()` (`CycleBudget.java:185`) grew while it was read.
- A second consecutive cut of the same `KIND|moid` returns `PUSH_THEN_STOP`. The object is pushed with refused reads UNREADABLE and Not Read = 1 (the build 95 skip-and-flag rule, documented in overview), the cursor moves to that object, and the kind is held back. An object that never fits costs at most two cycles.
- `objectLongerThanBudget`: cycle 1 drops it, cycle 2 pushes it flagged, cycle 3 reaches the next host.
- The drop mark clears on any cycle without a drop.

**Hung host: no pin.** A hung host's later reads are skipped by the hung mark, not refused, so it is never dropped. Its `QueryOptions` timeout counts once, and it is pushed flagged ("host not answering").

**N1-r2: closed.** `RetiredKeyRepeats` is keyed by `LastBenchmarkMemory.key` and trimmed by `retain(seen, incompleteKinds())`, the same rule as the benchmark memory. A resumed or held kind is not trimmed.

**N2-r2: closed.** `deadlineAfterReadsDoesNotDrop`: a host whose reads all finished before the deadline is pushed with its full score, and the walk stops before the next host.

### The coordinator's hunt items, re-checked

- **A cursor surviving a reconfigure:** still per `Configured` holder, rebuilt on configure. Safe.
- **retain vs the cursor:** a resumed tail is marked incomplete in `KindWalk.order` *before* the walk, so neither `retain` trims objects before the cursor.
- **W2 vs #52:** unchanged from round 2. No conflict.
- **New residue (harmless, not a finding):**
  - `PUSH_THEN_STOP` on the vCenter object records a VCENTER cursor that nothing reads (`collectVCenter` never calls `order`) and nothing clears.
  - A held-back (not pushable) host or VM kind keeps its cursor until a pushable tail reaches the end. That costs one extra held-back cycle, then it converges.

### The stated side effect: incomplete stays 1 until a full pass completes

Correct, and acceptable.
- **A single transient early end** gives `Rollup|incomplete` = 1 on that cycle and on the next. The next cycle reads only the stopped kind's tail and holds that kind back. A clean cycle after it starts at the top of the round, so the incomplete flag returns to 0 on the third cycle. The vCenter alert (wait 1, cancel 1) is active for two cycles.
- **A vCenter whose full walk always needs more than one budget:** incomplete stays 1 and the alert stays active for as long as that lasts. The Rollup keys and Environment tiles for kinds never read whole in one cycle keep their last values, while every object keeps updating.
- Why this is the right direction: a rollup assembled from different cycles would be a number no single moment produced, and holding it back is the conservative choice.
- The docs say what it means and what to do: README, overview, data-reference and installing all say that if every cycle ends early, the collection interval should be lengthened.

### Registry check (round 3)

- **DEF-023:** unchanged. Propose closing it on the 105,000-row fixture (orchestrator's call).
- **DEF-025: open; code half met** (4-push cap, tested). Devel evidence that an open alert on a retired control cancels is still owed.
- **DEF-026: open; code half met.**
  - The budget, breaker, hung-host mark, cross-kind resume and two-strike step-past are in, each tested (`Build96BudgetTest`).
  - Still owed: the devel check that an unreachable or throttled vCenter ends inside the budget, marks incomplete and raises the alert.
  - Propose closure after that devel proof.

**Registration candidate:** none.

### If shipped as-is (round 3)

Normal cycles score exactly as build 95 did. A cycle that runs out of time stops cleanly, raises "Compliance data not collected", and the following cycles carry on from where it stopped until every object has been read. A host that stops answering costs one timeout per visit, and retired-control alerts clear after four pushes.

## Round 4 (2026-10-16, branch at `1976619`)

- **Scope:** 2 commits on `fab413c`:
  - `5d0233e`: peer review items 1 to 8, code and tests.
  - `1976619`: docs.
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.96.pak` (built 12:13 PM), sha256 `235cbf74...`.
- **Measured context:** `knowledge/context/investigations/2026-10-16-compliance-cycle-durations.md` (longest build 95 cycle in 24 h: 42.5 s against 300 s).

### Verdict: APPROVE (0 BLOCKING, 0 WARNING, 3 NIT)

The carried share counts each object exactly once per pass. It cannot combine with the #52 hold-back, and a reconfigure drops it. The markers-only second cut, the narrowed hung-host skip, and the repeats riding the object's own push are all correct. Normal-cycle integer totals and the pass rate are unchanged. The one exception is in the last digits of `score_sum` / `avg_score` (N1-r4).

### Independent verification

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` on a clean `git archive 1976619` tree (JDK 17.0.20.1) | Exit 0. 26 Java tests (all "all assertions passed", including `dropsMustBeConsecutive`, `resumeOrderByMoid`, `repeatsWhenEveryCycleEndsEarly`; BcHandshakeTest with jars) and 10 Python checks OK. **Confirmed.** |
| `validate-sdk` | OK. **Confirmed.** |
| `build-sdk` | Built. Every unpacked file matches the author's pak. The jar holds only adapter classes. **Confirmed.** |
| `pak-compare` vs 0.0.0.95 | PASS, 0 / 0 / 0. **Confirmed.** |
| `generate_compliance_alerts.py --check` | Up to date. `describe.xml` untouched. |
| Evaluation path | `ControlEvaluator` (only the 7-line removal), `BenchmarkSelector`, `profiles/`, `views/`, `dashboards/` and `describe.xml`: unchanged since main. **Per-control and per-object scoring untouched, confirmed.** `ComplianceRollup` changed this round (below). |
| Em-dashes in added lines | None. |

### (3) The carried rollup: the hardest check

- **Normal cycle.**
  - The `ComplianceRollup` diff adds `bucketsByKind`, filled in `bump`, plus `Part`, `part`, `addPart` and `clearIncomplete`. `toStats` and `put` are untouched, and nothing reads `bucketsByKind` except `part`. `byBucket` is merged exactly as before.
  - On a cycle that never ends early: `KindWalk.order` sees `resumed == false`, drops any carry, and returns the full list. `finish` takes the not-ended branch with no prior, so `completed` runs and nothing is added.
  - So the integer counts, bucket counts and `pass_rate` (a ratio of integer counts) are identical to build 95 for the same per-object results.
  - Exception: N1-r4.
- **No double counting.**
  - A pass accumulates `prior.part.plus(now)` only on an ended walk. The cursor only moves forward in MOID order (`ResumeCursor.java:45-66`), and the tail is strictly after the cursor, so no object is read in both the carried share and the tail.
  - A dropped object is not recorded and is retried first next cycle, so it is counted once, then.
  - A cut-twice object is recorded once, as a bucket only (`pushCutTwice`, `recordEvaluated(..., 0, 0, 0, 0.0)`), and the cursor steps past it.
  - If the cursor's object leaves inventory mid-pass, `resumed()` is false, so `order` drops the carry and walks the full list (no double count).
  - A new object with a MOID before the cursor is missed by this pass and counted by the next.
  - `Tally` has seven fields, and `add` copies all seven. Pods carry with the VM share.
  - The completing cycle's All is the sum of each kind's complete share, so each object is counted once.
  - Covered by `twoCyclesVisitEverything` cycles 3 and 4: Host scored 3 with host-10 from the carry, then 3 again on a full pass, incomplete 0.
- **Mixed cycles.**
  - The completing cycle's kind rollup combines objects read across the cycles of one pass, each value at most one pass old.
  - That is the stated design, and `overview.md` "Resume" says so ("the part read by the earlier cycles of the pass is carried and added").
  - It is never fabricated: every object contributes its own last full read or its cut-twice bucket only.
- **Reconfigure.** The carry lives in `ResumeCursor`, inside `Configured`, which `configureAdapter` rebuilds. A reconfigure drops it.
- **#52 and the carry on one kind: they cannot both apply.**
  - vDS, portgroup and cluster check `kindPushable` (which `markIncomplete`s on `loadFailed`) *before* the `KindWalk` is built, and return. No walk, no `finish`, carry untouched.
  - Hosts and VMs call `walk.finish()` only `if (pushable)`. A held cycle neither adds to nor consumes the carry, and the next pushable cycle resumes with the prior share intact.
  - No other path marks a kind incomplete inside a walk except the budget (`cycleOver` and `afterRead`), and both set `ended`.
- **The 95% budget.** 285 s against a measured worst build 95 cycle of 42.5 s. Worst case with a call in flight is 435 s (documented). Sound.

### (4) Repeats on the object's push; the carried cleanup

- `withRetiredRepeats` folds only keys not live (not pushed with a value and not skipped this cycle) with fewer than 4 pushes, so a repeat can never overwrite a real value.
- `toPush` skips keys the object's push already carried (`foldedThisCycle`), so there are no extra calls.
- Item 6: an empty read-back changes nothing (`RetiredKeyRepeats.java:81`).
- The deferred cleanup runs first in the next cycle, before the walk, and is budget-checked per batch (`ComplianceAdapter.java:1859-1880`).
- **The noted window, judged harmless (N2-r4).**
  - The deferred plan is last visit's. It can set a lingering 0 or 1 to -1 only for a key outside that benchmark which the object already has.
  - After a version change to a new benchmark, the new benchmark's keys normally do not exist yet, and "never create a key" holds. The window needs an object that moves back to a benchmark it had before, between its visit and the deferred cleanup.
  - Even then, only one -1 sample is written before the next visit pushes the real value. The cleanup's repeat rides the object's own push, and the visit's push marks the key live. One non-failing sample cannot cancel an alert that needs 3.

### Other items

- **(1)** The hung-host skip is narrowed to `QueryOptions` (`getAdvancedSettings`) and esxcli. The per-control vim25 skip was removed, so vCenter-answered property reads behave as in build 95. Correct.
- **(2)** The second cut pushes only `has_unreadable` = 1 and the "cut by cycle budget twice" reason props (`ComplianceDecisions.java:394-406`): no score, no counters, no per-control keys. Last values stay. Correct.
- **(5)** `dropsMustBeConsecutive` is present and passes.
- **(7)** MOID order uses `nullsLast(naturalOrder)` (string order, so `host-10` sorts before `host-9`). It is consistent across cycles, which is what the cursor needs.
- **(8)** The CHANGELOG records the interrupt behaviour.

### Findings

#### NIT

- **N1-r4** `ResumeCursor.sorted` (item 7) changes the order in which `scoreSum` is accumulated, so `Rollup|<K>|score_sum` and `avg_score` can differ from build 95 in the last digits for the same per-object scores.
  - A 300-object shuffle test gave 18 distinct sums over 2000 orders, around 1e-11 apart.
  - Integer counts and `pass_rate` are exact.
  - Build 95 itself depended on the ContainerView listing order, and no bundled content binds `avg_score`.
  - Say so in the CHANGELOG, or accept it.
- **N2-r4** `runDeferredCleanup`: the one-sample window above. Optional guard: skip a deferred entry whose object was already re-queued this cycle.
- **N3-r4** A budget refusal during the version read sends the object down the version-unreadable path, which does not go through `afterRead`. It is pushed with version-unreadable markers and counted in bucket "unknown" (also inside a carried share) rather than being dropped. That is never a score, but the reason reads "version unreadable" rather than "cut by cycle budget".

### Registry check (round 4)

- **DEF-023:** unchanged. Propose closing it on the 105,000-row fixture (orchestrator's call).
- **DEF-025: open; code half met.** Repeats ride the object's push, capped at 4 (`repeatsEveryCycle`, `repeatsWhenEveryCycleEndsEarly`). Devel evidence (an open alert on a retired control cancels within three cycles) is still owed.
- **DEF-026: open; code half met.** Still owed: the devel check (an unreachable or throttled vCenter ends inside the budget, marks incomplete, and raises the alert). Propose closure after it.

**Registration candidate:** none.

### If shipped as-is (round 4)

At measured cycle lengths (under 45 s against a 285 s budget) nothing changes from build 95 except that retired-control alerts clear. A vCenter that ever overruns finishes its pass over the next cycles, and then pushes complete totals with the "not collected" alert cleared, instead of holding the totals back.

## Round 5 (2026-10-16, branch at `0c61f66`)

- **Scope:** 1 commit on `1976619` (round 4 nits).
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.96.pak`, sha256 `d3d97068...61daa`, matching the coordinator's.

### Verdict: APPROVE (0 BLOCKING, 0 WARNING, 0 NIT)

N1-r4, N2-r4 and N3-r4 are closed. The per-kind cleanup touches only objects that some cycle actually visited and pushed. It makes the same number of read-back requests as before, and the Skip push and the zero cleanup see the same per-cycle state.

### Independent verification

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` on a clean `git archive 0c61f66` tree (JDK 17.0.20.1) | Exit 0. 26 Java tests (all "all assertions passed", including the new `versionReadCutIsACut` and `carriedEntrySupersededByVisit`) and 10 Python checks OK. **Confirmed.** |
| `validate-sdk` | OK. **Confirmed.** |
| `build-sdk` | Built. Every unpacked file matches the author's pak. **Confirmed.** |
| `pak-compare` vs 0.0.0.95 | PASS, 0 / 0 / 0. **Confirmed.** |
| `generate_compliance_alerts.py --check` | Up to date. |
| Scoring | The evaluation path since main is still only the 7-line removal. `ComplianceRollup` and `ComplianceDecisions` are untouched this round. **Confirmed.** |
| Em-dashes in added lines | None. |

### cleanKind, the four questions

- **Can it retire a key for an object the walk has not reached this pass?** No.
  - Cleanup entries are created only by `afterPush`, so only for objects pushed in this cycle or an earlier one. `cleanKind` (`ComplianceAdapter.java:1924`) takes this cycle's entries of the kind plus carried entries of the kind, and drops any carried entry whose object was queued again this cycle (`carriedSuperseded`).
  - `runCarriedForStartKind` (`:1905`) runs only the resumed kind's carried entries. Those come from the early-ended cycle's walk of that kind, so they are objects before the cursor, which this cycle does not visit again.
  - Edge: if the cursor's object left inventory, the walk restarts from the top. Those carried entries then run one walk before their objects are revisited, against a plan one cycle old. Harm needs a benchmark change in that same cycle, and the cost is at most one -1 sample, which cannot cancel an alert. Not a finding.
- **Can a kind held back by #52 run its cleanup against a stale read-back?** No.
  - The read-back is a fresh Suite API read of latest values by resource id. It does not depend on the kind's resource list.
  - A held kind pushes nothing, so it has no fresh entries. Its carried entries are for objects not revisited, so their plan is still the latest known one.
  - A failed read skips the batch (logged, `cleanupSkipped`), and the retirement is retried at the object's next visit.
- **Cost: is the read-back now once per kind rather than once per cycle?** The request count is unchanged.
  - The old `cleanStaleControls` already grouped entries by kind and batched within each kind (`1976619`, line 1797), so it already made at least one request per kind. Per-kind invocation adds no requests.
  - `bundledForCleanup` now runs up to 6 times per cycle, but `BenchmarkLoader.loadAll` returns its cache (`BenchmarkLoader.java:129-132`).
- **Do the build 76 zero cleanup and the build 92 Skip push see the same per-cycle state?** Yes.
  - The Skip ids still go out in the object's own push, and `afterPush` adds them to the entry's live set.
  - `cleanBatch` still uses `cycleOverrides.skipped`. The overrides are refreshed at cycle start (`:1037`), before the stitcher load (`:1045`) and before both `runCarriedForStartKind` (`:1081`) and every `cleanKind`.
  - Retired-key folds for a kind's objects happen during that kind's walk, so they precede that kind's cleanup exactly as they preceded the old end-of-cycle cleanup.
  - The one ordering change: `retiredRepeats.retain` now runs after the cleanups rather than between them. It only trims objects not seen, so the result is the same.

### Prior nits

- **N1-r4: closed.** The CHANGELOG notes that `score_sum` and `avg_score` can differ in the last digits.
- **N2-r4: closed, structurally** (above).
- **N3-r4: closed.** On all four version-unreadable paths (`:2162`, `:2508`, `:2657`, `:2908`), `afterRead` runs first. A refusal is a cut (dropped, or markers only on the second cut). A genuine unreadable version returns `CONTINUE` and takes the build 95 path unchanged. Covered by `versionReadCutIsACut`.

### Registry check (round 5)

- **DEF-023:** unchanged. Propose closing it on the 105,000-row fixture (orchestrator's call).
- **DEF-025: open; code half met.** Devel evidence is still owed.
- **DEF-026: open; code half met.** The devel check is still owed. Propose closure after it.

**Registration candidate:** none.

### If shipped as-is (round 5)

Same as round 4. Normal cycles match build 95, retired-control alerts clear, and a vCenter that overruns finishes its pass over the following cycles. The cleanup now runs right after each kind and never acts on an object later in the walk than the current position.
