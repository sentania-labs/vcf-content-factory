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
