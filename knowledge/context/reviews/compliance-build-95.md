# Compliance build 95 review

- **Reviewer:** sdk-adapter-reviewer (read-only, static, pre-install)
- **Date:** 2026-10-14
- **Adapter:** `content/sdk-adapters/compliance/`, branch `feat/build-95-control-pass-rate`, 11 commits `66454f9..660999d` on main `e92baab` (v1.0.0.94)
- **Pak reviewed:** `dist/vcfcf_sdk_compliance.0.0.0.95.pak`, sha256 `6a8a6824...4187d`, built from `7f1a846` (`660999d` is test-only, confirmed: one file, `tests/.../FakeVCenter.java`)
- **Designs:** `knowledge/designs/sdk-adapters/compliance-build-95-control-pass-rate.md` (incl. "Scope addition: issue #17, phase 1"), `knowledge/designs/sdk-adapters/compliance-bulk-collection.md` ("What must not regress"); triage `knowledge/context/reviews/compliance-open-issues-triage-2026-10-14.md`

## Verdict: CHANGES REQUESTED (1 BLOCKING, 7 WARNING, 9 NIT)

The arithmetic is right, the transport changes never turn a capped or truncated response into a pass, and the build reproduces. The one blocker is what the new percentage shows when a kind has nothing readable: `pass_rate` stops being pushed, VCF Ops keeps showing the last value, the view has no per-kind column that reveals it, and the README and the view description say the opposite ("no percentage"). Before build 95 the same state showed 0.

## Independent verification

| Check | Result |
|---|---|
| `validate-sdk content/sdk-adapters/compliance` | OK (exit 0) |
| `build-sdk` of a clean `git archive 7f1a846` tree | Built. sha256 differs from the author's (`b736f8b4...`) only through zip timestamps: every class file in `vcfcf_compliance.jar`, the bundled `describe.xml`, `views.zip` contents and all dashboard JSON are byte-identical to the author's pak. **Confirmed.** |
| `pak-compare` 0.0.0.95 vs 0.0.0.94 | PASS, 0 BLOCKING / 0 WARNING / 0 INFO. **Confirmed.** |
| `ci/run_java_tests.sh` | All pass on JDK 17.0.20.1, including `Build95CollectionTest`, `Build95TriageTest`, `ComplianceRollupTest`, `EnvironmentKeyContractTest` (8 computed keys) and `BcHandshakeTest` (BouncyCastle jars fetched, not skipped). **JDK 25 is not installed here; not run locally.** CI's `tests.yml` matrix covers 17 and 25. |
| New Python guards | `tests/test_pass_rate_bindings.py` (3 OK), `tests/test_build95_dashboards.py` (5 OK), but neither is run by CI (W7) |
| Factory `pytest tests/` | 2063 passed, 5 skipped. Compliance `pytest tests/`: 45 passed. (A repo-root `pytest` aborts collecting `cluster-perf-risk` for a missing `aria` module, which this build doesn't touch.) |
| Dimension 13, built pak `describe.xml` | Identical to source at `7f1a846`; 152 symptom definitions, 152 SymptomSet references, none dangling, no single-child `<SymptomSets>`, wait/cancel cycles all integers. The build does not touch alerts. |
| Em-dashes in added lines | One, in the generated `docs/inventory-tree.md` header (factory template, N6) |

## Commit by commit

### 66454f9: pass rate (rollup, ComputedMetrics, view, dashboards, docs)

**(a) Arithmetic: correct.** `ComplianceRollup.recordEvaluated` (lines 260-277) adds `totalCount` to evaluated, `totalCount - min(failCount, totalCount)` to passed and `unreadableCount` to unreadable. `totalCount == pass + fail` holds at every construction site (`ControlEvaluator.java:261, :314, :566-569`; `ComplianceAdapter.mergeResults`), so passed equals `passCount`. All sums the per-kind tallies (`toStats`). `pass_rate` is omitted when evaluated is 0 (`passRate`, line 347). The new keys go through `put()`, which runs only for kinds not marked incomplete, and All only on a complete cycle, so they are held back with the kind (tested in `ComplianceRollupTest` and `Build95TriageTest.hostListingFailure`). `emptyResult` (nothing attempted) adds zeros. The zero-divisor contract holds.

**The `* 100` in `Rollup|Environment|pass_rate`: accepted, with evidence.** VMWARE's own describe.xml (decompiled `vmwarevi_adapter3/conf/describe.xml`, outside this repo under `vcf-mp-cleanroom/analysis/`) carries ComputedMetric expressions with constant multipliers: `(${this, metric=cpu|usagemhz_average} / ${this, metric=cpu|capacity_provisioned}) * 100`, `sum(...) * 200` and `100 * sum(...)`. The super metric DSL takes the same form (`content/supermetrics/cluster_cpu_free_pct_after_ha.yaml`). `a / b * 100` evaluates left to right as `(a/b)*100`. The 0/0 case is the same open devel item `avg_score` already carries. This evidence is not committed (N8).

**Dashboards and view (g).** All bindings resolve to declared keys. `test_pass_rate_bindings` guards them, and no bundled content binds `avg_score`. The totals row indices `[3,4,5,7,8,9,11,12,13,15,16,17,19,20,21,22,23]` map exactly onto the count columns, so no percentage is summed. The heatmap renders `maxValue: 100.0` and `solidColoring: true`; the vendor Home template uses the same `color.maxValue` field. Widget types are unchanged and `test_dashboard_widget_types` passes. The colour bounds on the view columns are unchanged.

**B1 is in this commit** (below). So are W1 and W2.

### 52526d9: #17 phase 1 (measurement, quick wins, shadow)

- **Keepalive once per cycle.** Reads call `ensureSession()` (log in only when there's no session). `ensureConnected()` (keepalive) is left to the adapter's cycle start. A lapsed session is caught in `post()` (NotAuthenticated, then re-login and one retry; `VSphereClient.java:1999-2021`). A failed re-login returns null, so the read is UNREADABLE, never a default. That's correct for one call, but there's no latch across calls (W3).
- **Names from the listing.** `listView` asks for `name` in the same RetrieveProperties and falls back to `nameOrMoid` only when it's missing. A failed listing still throws (build 77 contract kept).
- **Connection reuse (c).** No disconnect after a 2xx. The body stream is read through the parser and then closed, and an IOException disconnects. Session cookie: an explicit `Cookie` header on every request, unchanged from before. JDK keep-alive keys HTTPS connections by host, port and `SSLSocketFactory`, so connections are never shared across accounts or vCenters. A server-closed kept-alive connection: JDK 17 retries a buffered (non-streaming) POST once by default (`sun.net.http.retryPost`), and the client uses buffered POSTs. If that retry is disabled, the result is an IOException, so UNREADABLE, never a pass. Thread safety: one `VSphereClient` per adapter instance, used by the single collect thread. Test Connection builds its own client. The `volatile` per-call state (`readFailure`, `lastFault`) is not thread-safe but has only one writer. The exception is the reconfigure path (W4).
- **Bounded prefix fallback (d).** `prefixLengths` caps attempts at 4 and the floor at 2 segments for HostSystem and VirtualMachine, so a whole host or VM `config` is never fetched. A path it can't reach is UNREADABLE with `prefix-cap`, never a pass. I walked all 31 non-esxcli `vim_property` recipes in the canonical CSVs against vim25 declared types (cluster vSAN at 1 of 4, vDS / port group security policy at 1 to 2 under `walkToParent`, the port group mac-learning path at 2 of 5, host NTP / firewall at 3 to 4, VM devices at `config.hardware`): every resolvable prefix falls inside the new bounds. That is reasoning, not a test (W6).
- **Shadow (e).** Scores and pushes come only from the per-object path. `runShadow` runs after each kind's loop. A failed bulk read is caught and reported as `bulk read FAILED (...)` in the kind's summary. Stop is rethrown. The per-object `readFailure` and `lastFault` it overwrites are reset before every per-object read. esxcli recipes return `esxcli-not-bulk` on a bulk row, and esxcli is its own parameter kind, so it is never in `bulkComparable`. The pathSet comes from the recipes (`bulkPaths`), and an InvalidProperty is shortened one segment at a time, at most 64 fixes, remembered per type and path set. Log volume: one summary, at most 25 disagreement lines and a "+N more" line per kind per cycle, plus one rejected-paths line while any path is dropped. That is bounded. Memory and prod exposure: W5. Token cancel: N1.
- **Measurement.** `CycleMetrics` is synchronized and charges nested phases once. The summary goes on the existing completion line.
- **Secrets.** No log line carries a SOAP body. The re-login, too-large and fault paths log the SOAPAction and vCenter's fault string only (`knowledge/rules/no-secrets-on-disk.md` respected).

### 1a4c9b9: #18 host listing hold-back

Correct. It follows the same pattern as the other kinds: WARN, `markIncomplete(HOST)`, return an empty map. All and Benchmark are held back, `Rollup|incomplete` = 1, the other kinds are still collected, and VMs read their host version on demand (`vmHostVersion`, failures there become version-unreadable, never a guess). This closes the triage's worst "whole cycle lost, no alert" path.

### 06e1a90: #16 stop check (first slice)

Correct for its scope. `StopCheck` runs at the top of every per-object loop, every shadow row and every cleanup batch (`ComplianceAdapter.java:1290, :1463, :1705` and the four network/VM loops). It throws InterruptedException, `runShadow` rethrows it, and the framework restores the interrupt and marks the world ERROR. No partial push reads as complete: checks happen only between objects, never between one object's property and stat pushes, and the per-vCenter rollup (including `Rollup|incomplete`) is not pushed on an abandoned cycle, so the rollup on screen is the previous complete one. The stopped account itself is the operator's signal. No time budget yet, so DEF-026 stays open. Logging: N4.

### c0ce8b8: #24 cap and streaming parse (d)

The parser reads straight from `CappedInputStream`. Over the cap, the stream throws, `parseXml` returns null, `exceeded()` routes to `tooLarge()` (WARN, `lastTooLarge`, reason `response-too-large`), and the connection is disconnected. A truncated body cannot form a DOM, so it becomes null too. Every null response path ends in a throw or UNREADABLE: `VimOptions.fromQueryOptions` / `fromPropertyOptions` throw ReadFault on null (so never an empty "nothing set" map that would pass "X or Undefined"), `listView` throws, and `retrieveBulk` throws on a null page. **No path turns a capped or truncated response into a pass.** XXE hardening is kept (`newBuilder`). Fault bodies are capped at 1 MB. Diagnostic wording: N2.

### 1dd1dc9: #23 release on reconfigure, #28 vcApi removed

The leak is fixed for the normal (serial) case: `releaseClients()` logs the old session out and discards the Suite API client, and it never throws. `stitcher` is rebuilt later in configure. The concurrent case is not proven safe (W4).

### 01f9445: #25 UTF-8 Basic auth

Correct. `ComplianceDecisions.basicAuthorization` is used by both `VCenterApiClient.login` and `VamiApiClient`. No `getBytes()` without a charset remains in `src/`.

### 2826ada: #39, #32, #33, #34

The `unmatched` columns are bound and summed, the SCG view is newest first and full width on both dashboards, the heatmap scale is fixed, and the About box is shorter. `test_build95_dashboards` checks for overlaps. The visual result is still owed on devel (the author says so).

### 42c2032, 7f1a846, 660999d

Test pins updated for the removed `vcApi` (counts 4 to 3 and 5 to 4 match the source). One em-dash replaced by a colon. The fake vCenter turns Nagle off (N7).

## (b) Host score vs pass rate: which matches the lesson, and the risk of each

Since build 63 (owner decision 2026-09-23, `ControlEvaluator.score`, line ~805) an object's own score is `pass / (pass + fail + unreadable)`, so unreadable counts as failing. Build 95's `pass_rate` is `passed / (passed + failed)`, with unreadable in neither count and reported as `controls_unreadable`.

- **Both comply with `knowledge/lessons/unreadable-is-not-compliant.md`.** Contract 1 allows either "drop the control from the denominator" or "surface an explicit unreadable signal". Neither rule ever turns an unread control into a pass.
- **Host-score rule, risk: false alarm, never false comfort.** A read outage looks like a compliance regression and can fire Host Compliance Score Degraded. It cannot overstate compliance. For a security product it is the strictly safer rule for a headline number.
- **Pass-rate rule, risk: false comfort when the unreadable count is not beside the rate.** It is lesson-compliant only if the unreadable count is visible at the same granularity as the percentage. As built it is not:
  - The view shows `controls_unreadable` for All only, so it can't tell which kind is unreadable.
  - The Environment tile shows no unreadable count at all, though `Rollup|Environment|controls_unreadable` is computed.
  - The vCenter column changed from the vCenter's own score to `Rollup|vCenter|pass_rate`. A vCenter with 10 passes, 0 fails and 30 unreadable controls showed 25% and now shows 100%.
  - A version-unreadable object adds nothing to `controls_unreadable`.
  - Worst of all, a kind with nothing readable shows a stale rate (B1).
- **Inconsistency on screen.** The ESX Hosts heatmap and the Score Degraded alert use the host score, while the per-vCenter table uses the pass rate. The same host population can read 60% on one page and 95% on another. data-reference.md documents the difference.
- **Grade:** WARNING (W1), and a design decision for Scott. Option A: keep the pass rate and put unreadable beside every rate at the same granularity (tile, per kind), or show coverage, evaluated / (evaluated + unreadable). Option B: count unreadable as failing in the pass rate too, which matches the host score and alert. Not fixed here, by design.

## Findings

### BLOCKING

**B1. A kind with nothing readable keeps showing its last pass rate, with no per-kind tell, and the docs say it shows nothing.**
- Where: `src/.../ComplianceRollup.java:347`; `views/compliance-by-vcenter.yaml` columns; `README.md:167`; `views/compliance-by-vcenter.yaml:8`.
- Authority: skill §*Unreadable is NOT compliant*; `knowledge/lessons/unreadable-is-not-compliant.md` ("never ... a healthy-looking datapoint"); reviewer dimension 11 (docs contradicting behaviour).
- What happens: when every control of a kind is unreadable (vCenter permissions, a vCenter fault mid-cycle, a single-object kind such as vCenter with VAMI and settings both failing), `controls_evaluated` is 0 and `pass_rate` is not pushed. VCF Ops keeps the last pushed value. That is stated in the code's own `markIncomplete` doc and admitted in `docs/overview.md:280` ("the table cell then keeps the last rate it had").
- Before build 95 the same state showed `avg_score` 0 (unreadable scored as 0), and the old view description named its tell ("a retained average (scored = 0 ...) is identifiable at a glance"). The new view drops that description and adds no replacement. `scored` stays above 0 for unreadable objects, `non_compliant == scored` also happens legitimately, and Controls Unreadable is All-only. So the stale green-looking cell can't be identified.
- `README.md:167` and the shipped view description say "With nothing evaluated there is no percentage, never 100", which contradicts the behaviour.
- Smallest correct fix: (1) make the state identifiable per kind in the view: add `Rollup|<K>|controls_unreadable` (or `controls_evaluated`) beside each kind's Controls Passing column; (2) correct `README.md:167`, the view description and `docs/overview.md:91` to say the cell keeps its last value and how to read it. The stronger alternative needs Scott's call: push `pass_rate` = 0 when evaluated is 0 and unreadable > 0 (the build 63 "nothing collected scores 0" rule).

### WARNING

**W1. The pass rate's unreadable signal is not at the same granularity as the rate (Environment tile, per kind, vCenter column), and it differs from the host score, heatmap and alert.**
- Where: `dashboards/compliance-environment-overview.yaml` scoreboard; `dashboards/compliance-world-summary.yaml` scoreboard; `views/compliance-by-vcenter.yaml:25` and `:92`.
- Authority: lesson contract 1; design Vision 1 ("surfaced so missing data is visible").
- Fix: design decision for Scott, see (b). Minimum: add `Rollup|Environment|controls_unreadable` to both scoreboards.

**W2. The per-vCenter table can't be reconciled with the tile.**
- Where: `views/compliance-by-vcenter.yaml`.
- Authority: design §*Verification on devel* ("the tile and table agree").
- What's wrong: the table has no All `pass_rate`, `controls_evaluated` or `controls_passed` column, so neither a row nor the totals row can be compared with the Environment pass rate. The planned devel check can't be done from the dashboard. "vCenter Controls Passing" is the vCenter appliance kind only, not the vCenter's overall rate (see N9).
- Fix: add All `controls_passed`, `controls_evaluated` (summed in totals) and All `pass_rate` columns.

**W3. A failed mid-cycle re-login is not latched, so with bad credentials every later SOAP call tries Login again.**
- Where: `VSphereClient.java:1999-2021`, `:224-253`.
- Authority: triage #23 (half-initialised session), #16 (failure cutoff); DEF-026.
- What's wrong: `connect()` stores `propertyCollector` and captures the `vmware_soap_session` cookie from RetrieveServiceContent before Login. After a failed Login, `ensureSession()` therefore sees a "session". The next call gets NotAuthenticated and logs in again, then the next does the same, so one cycle can send thousands of failed logins and trip the SSO lockout policy. Before this build it was one attempt per public read. Now it is one per SOAP call.
- Fix: latch a failed re-login for the rest of the cycle (cleared in `beginCycle`), and set the session fields only after Login succeeds.

**W4. #23: release on reconfigure is not safe against a running cycle.**
- Where: `ComplianceAdapter.java:2482-2500`, `:175`.
- Authority: skeptic default (the triage left concurrency unproven).
- What's wrong: `releaseClients()` nulls `vsphere`, `suiteStitcher` and `stitcher`, then logs the old session out. A cycle still running on the same object reads those fields directly (NPE, cycle lost, or the wrong client mid-cycle). Its in-flight calls on the old client get NotAuthenticated and re-log-in, opening a session that nobody logs out. Build 94 had no null window. Also, `disconnect()` posts Logout synchronously, so configure can block for up to 30 s connect plus 120 s read on an unreachable old vCenter.
- Fix: build the new clients first, swap the fields, then release the old ones; have `disconnect()` mark the client closed so `post()` refuses re-login.

**W5. Shadow mode is compiled on, with no runtime switch, and ships to whatever installs 1.0.0.95.**
- Where: `ComplianceAdapter.java:450`, `:460`; `ShadowComparator.java:41`; `VSphereClient.java:116`.
- Authority: dimension 7 / 8; bulk-collection design (shadow proves out "on devel"); DEF-026.
- What's wrong:
  - Every cycle repeats every kind as bulk reads: more vCenter load and longer cycles, with no budget.
  - VM pages of 200 carry the whole `config.hardware` plus `config.extraConfig`. The 64 MB cap counts bytes, but the DOM is several times that, in the collector JVM every adapter shares.
  - `ShadowComparator.recorded` holds one outcome string per control for every scored object of the kind until the bulk read ends, so memory grows with objects times controls.
  - Nothing logs the page size, so devel can't size any of this.
- Fix: log the largest page bytes per kind in the shadow summary. Scott to decide whether the release build ships with `BULK_SHADOW` on. Consider a VM page of 50.

**W6. No proof that the bounded fallback leaves existing controls unchanged.**
- Where: `VSphereClient.prefixLengths`, `Build95CollectionTest.prefixCap`.
- Authority: author hard rule 8 (prove behaviour preservation when generalizing).
- What's wrong: the tests pin the arithmetic only. My walk of the 31 recipes found none out of bounds, but that is reasoning about vim25 declared types. A miss would move controls from pass or fail to UNREADABLE (never a pass).
- Fix: a table test pinning each canonical `vim_property` recipe's resolvable prefix length inside `prefixLengths`, plus a devel check that the `prefix-cap` reason count is 0.

**W7. The two new guards don't run in CI.**
- Where: `ci/run_java_tests.sh`.
- Authority: `knowledge/rules/validate-before-install.md`; the guards' own purpose.
- What's wrong: `tests/test_pass_rate_bindings.py` and `tests/test_build95_dashboards.py` are in neither `run_java_tests.sh` nor `tests.yml`, so a regression to an `avg_score` binding would ship green.
- Fix: add both to `run_java_tests.sh` next to the other `tests/test_*.py`.

### NIT

- **N1** `VSphereClient.java:1803-1822`: when a page handler throws (Stop, an evaluation error), the token for the next page has been parsed inside `handlePage` but not yet returned. `cancelRetrieveQuietly` then cancels the already-consumed token, which leaves a server-side retrieval open on what is now a long-lived session.
- **N2** A 2xx body that fails to parse for a reason other than the cap (a read timeout mid-body) becomes null with `lastFault` null. The unreadable reason then reads `missing-element ... not returned` instead of the transport error build 94 surfaced, and the connection is not disconnected. Not a pass.
- **N3** A mid-cycle re-login replaces `EsxcliSoapClient` and drops the build 86 unreachable-host marks, so an unreachable host can cost another timeout.
- **N4** An abandoned cycle logs two WARNs ("abandoned", then "failed ... logged by onCollect") and drops the timing summary, which is exactly what #16's budget sizing needs.
- **N5** `Build95TriageTest` pins #18, #16 and #23 by source-text matching, not behaviour (known gap, issue #27).
- **N6** The generated `docs/inventory-tree.md` header has an em-dash ("Do not edit", em-dash, "regenerated") from the factory template: route to `tooling`.
- **N7** The reuse speed-up is unproven against a real vCenter. The fake needed TCP_NODELAY (44 ms reused vs 2.7 ms new without it). Compare the devel phase timings with build 94.
- **N8** The `* 100` evidence is a decompiled VMWARE describe outside the repo. Codify a verbatim extract (RULE-015 / RULE-017) if it is to be cited again.
- **N9** "vCenter Controls Passing (%)" reads as the vCenter's overall rate but is the vCenter appliance kind only (`views/compliance-by-vcenter.yaml:25`). The same ambiguity existed with the old label.

## Registry check (`knowledge/context/defects.md`)

Open defects with `Affects: compliance`: DEF-023, DEF-025, DEF-026.

- **DEF-023: open, unchanged.** `ComplianceStitcher.fetchResources` paging logic is unchanged except for `countCall()`. The new timing line's inventory Suite API call count gives indirect sight of paging, but there is still no page-count line, no fixture over 10,000 objects and no forced-failure devel cycle. The close condition is unmet. Tracked; doesn't gate.
- **DEF-025: open, unchanged.** `ComplianceDecisions.staleControls` (line 441) and `cleanBatch` are untouched (the only change to `ComplianceDecisions` is `basicAuthorization`). Tracked; doesn't gate.
- **DEF-026: open; the first slice landed.** The stop check is in every loop (`StopCheck.java`; `ComplianceAdapter.java:1290, :1463, :1705` and others). There is still no cycle budget or consecutive-failure cutoff, so the close condition is unmet. Build 95's shadow reads make cycles longer with no budget (W5). Tracked; doesn't gate.

**Registration candidates (orchestrator's call, RULE-012):** B1 if it survives (stale percentage on screen while nothing was readable, the "unreadable shown as healthy" class); W3 (an SSO lockout risk that reaches beyond this pak).

## If shipped as-is

Normal cycles show correct numbers. But when a kind (or a single-object kind like vCenter) can't be read, its Controls Passing cell keeps showing the last, possibly green, percentage with nothing on the page to say it is stale, where build 94 showed 0. And every install runs the bulk shadow reads on top of the normal collection.
