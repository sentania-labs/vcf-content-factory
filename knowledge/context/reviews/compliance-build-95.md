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

## Re-review (2026-10-14, branch at `e527b03`)

- **Scope:** 15 review-fix commits `d95cd22..7f29351`, then 8 commits `0ee869b..e527b03` implementing "Decision 2026-10-14: unreadable data is skipped and flagged per object" (design `knowledge/designs/sdk-adapters/compliance-build-95-control-pass-rate.md`).
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.95.pak`, sha256 `f8878cbe...6153c`, reference 0.0.0.94.

### Verdict: CHANGES REQUESTED (1 BLOCKING, 2 WARNING, 4 NIT)

B1, W1 to W7 and the adapter-side NITs are closed. The decision is implemented as written. The arithmetic, the alerts, the shadow switch and the new list view are correct, and the build reproduces. The one blocker is what the decision leaves on screen for an object with nothing readable. Its score and its Controls Evaluated keep their last values. The per-object views, the ESX Hosts heatmap and the host property list carry no `has_unreadable` (or `collection_failed`) beside them. Meanwhile the README, overview, data-reference, installing guide and all six per-kind view descriptions tell the operator either that the flag is beside the score, or that only "Controls Evaluated = 0" marks a retained score. A host that stops responding while at 100% therefore still shows a green 100 in the host table, next to a description that implies the value is current.

### Independent verification

| Check | Result |
|---|---|
| `validate-sdk` on a clean `git archive e527b03` tree | OK (exit 0) |
| `build-sdk` of the same tree | Built. Every class in `vcfcf_compliance.jar`, `views.zip` content, `overview.packed` content and `describe.xml` match the author's pak byte for byte; only the zip timestamps differ. **Confirmed.** |
| `pak-compare` 0.0.0.95 vs 0.0.0.94 (both directions) | PASS, 0 BLOCKING / 0 WARNING / 2 INFO (the new Unreadable Objects report bundle). **Confirmed.** |
| `ci/run_java_tests.sh` (JDK 17.0.20.1) | All pass: 18 Java tests, including `Build95UnreadableTest`, `Build95PrefixBoundsTest` (27 recipes) and `BcHandshakeTest` (jars fetched, not skipped), plus every Python guard, now including `test_pass_rate_bindings` and `test_build95_dashboards`. JDK 25 not run locally (CI matrix). |
| Factory `pytest tests/` | 2063 passed, 5 skipped. Compliance `pytest tests/`: 48 passed. |
| `generate_compliance_alerts.py --check` | Up to date (136 control alerts, 6 collection alerts on `has_unreadable` = 1, wait 2 / cancel 1, plus `Rollup|incomplete` on the vCenter) |
| Dimension 13 (built pak `describe.xml`, own parser) | 146 symptom definitions and 146 SymptomSet refs, none dangling, none unreferenced. No `<SymptomSets>` with fewer than two children: the five single-symptom collection alerts carry a bare `<SymptomSet>` and the vCenter alert keeps a two-child `or`. All wait/cancel cycles are integers. Every describe `nameKey` resolves in `resources.properties`, including the retired 38 and 2020 to 2025. |
| ShadowMode against real stamps | Dev pak `conf/version.txt`: `0` / `0` / `0.95`, so 0.0.0.95, on. The CI release asset `v1.0.0.94` (downloaded from the pak repo's Release): `1` / `0` / `0.94`, so 1.0.0.94, off. |
| Em-dashes in added lines (`660999d..e527b03`) | None. The generated `docs/README.md` (2) and `docs/inventory-tree.md` (4) still carry the factory template's em-dashes (N6, tooling). |

### Prior findings

- **B1: closed by decision.** `controls_unreadable` is gone. A kind with nothing readable still keeps its last `pass_rate` (`ComplianceRollup.java` `passRate`). Scott chose to accept that, with the objects behind it surfaced on the Objects with Unreadable Controls list beside the tile and in the per-object alert after two cycles. The README (`:185`), the overview (`:280-286`), the data-reference (`:323-325`) and the by-vCenter view description now say the cell keeps its last value. The docs half of B1 is fixed. The residual (no per-cell tell in the by-vCenter table) is the owner's accepted cost.
- **W1: closed by decision.** There is no unreadable rollup at any granularity. The signal is per object.
- **W2: closed.** The by-vCenter view has All Controls Passing, Passed and Evaluated. The totals indices `[2,3,6,7,8,10,...,25]` sum counts only, with no percentage (checked against the column order). `test_pass_rate_bindings` pins it.
- **W3: closed** (`cf5f08b`). Session fields are set only after Login succeeds. A failed `connect()` is latched until `beginCycle` / `ensureConnected`. Login was already sent without a Cookie header before this change, so taking the session cookie only from the Login response does not regress real vCenters. The test fails against the old client.
- **W4: closed** (`71610f3`). Configure builds the new clients, swaps them in, then releases the old ones, and no field is nulled. A closed client refuses re-login. Logout is bounded at 5 s + 5 s. Residual: N13.
- **W5: closed.** Page bytes are logged, VM pages are 50, and one switch is decided per cycle from `conf/version.txt` (point 6, below).
- **W6: closed in code** (`Build95PrefixBoundsTest` walks every loaded `vim_property` recipe and fails on a missing row). It counts 27 recipes against my 31: my count included manual-review and duplicate recipes. The devel check that the `prefix-cap` count is 0 is still owed.
- **W7: closed.** Both guards run in `ci/run_java_tests.sh`.
- **N1 to N5, N9: closed** (`eefd4f5`, `08edfd7`, `1732bb3`, `188f929`, `4b7aa43`, `6635c2d`). The tests behind them pass.
- **N6, N7, N8: open, outside the adapter.** N6 is the factory template (route to `tooling`). N7 is devel timing. N8: the VMWARE `* 100` evidence is still not committed to the factory.

### The new commits, against the brief

**(a) Could not pushing leave a stale passing value that reads as current with nothing flagging it?**

The flag family is pushed whenever anything was unreadable:
- `complianceStats` pushes `has_unreadable` in both branches.
- `complianceProps` pushes `unreadable_reason` and `unreadable_controls` in both branches.
- The version-unreadable path pushes the flag, `collection_failed`, the reason and a fixed "not known" controls text.
- The no-benchmark and nothing-evaluated paths push `has_unreadable` = 0 and both properties as "".
- `object_kind` is added on all four push paths.
- `beginObject` resets the per-object reason before every object (host and VM loops, vCenter, `collectVimObject`; no path calls it twice for one object), and the reason text is never empty beside a non-zero count.
- `pushedIds` still includes unreadable controls, so the stale-key cleanup holds them at their last value instead of retiring them to -1 (tested).

The list view filters on `has_unreadable` EQUALS 1 on all six subject kinds, and its unbound columns are `object_kind`, `unreadable_count` and `unreadable_reason`.

Fully passing, then fully unreadable (a host goes notResponding):
- The cycle pushes `has_unreadable` 1, `unreadable_count` N, `collection_failed` 1, and the reason "host not responding (host-not-connected: connectionState=notResponding)".
- `score` (100), `total_count`, `pass_count`, `fail_count`, `non_compliant` (0) and every `Compliant` (1) keep their last values.
- The rollup leaves the host out of `scored`, `non_compliant` and the control counts, so the Host pass rate is computed over the other hosts.
- The host appears on the list immediately, and its alert fires after two cycles.

The flag is therefore pushed and listed, but it is not beside the stale value on any per-object surface (B2).

**(b) The cardinal rule in its new form**
- `ControlEvaluator.score(pass, fail)` is pass over (pass + fail). The placeholder 100 is returned only when nothing was read, and no caller pushes or rolls it up: `complianceStats` checks `totalCount > 0`, `recordEvaluated` returns early on `totalCount <= 0`, and `cs.hostsScored` is counted on `totalCount > 0`.
- `isNonCompliant(failCount)` covers read failures only.
- No path computes a fresh 100 from nothing, and the zero-divisor contract holds.
- Plainly: **yes, an all-unreadable object can show a stale 100%.** Its `score` key keeps its last value. That shows in the host, VM, vCenter, cluster, vDS and portgroup views, the ESX Hosts heatmap (green), the host property list and the object's metrics.
- **What sits beside it:**
  - In the per-kind views, only the Unreadable column (current, N) beside a stale Controls Evaluated.
  - For a version-unreadable object, nothing current at all: `unreadable_count` is not pushed, so its last value shows, usually 0.
  - In the heatmap, nothing.
  - Elsewhere: the separate list on the two environment dashboards, and the alert in the dashboards' alert lists after two cycles (10 minutes at the default interval).
- A partial outage moves the score both ways. Hiding failing controls raises it. Hiding passing ones lowers it, and that can raise Host Compliance Score Degraded. This is decision point 7 working as designed, but `docs/overview.md:237` ("a read outage no longer moves the score") and `:251-253` ("no longer lowers a host's score, so it no longer raises ... Score Degraded") are false for a partial outage. That is part of B2.

**(c) Alerts: correct.**
- The six collection symptoms are `has_unreadable` = 1, `waitCycle="2" cancelCycle="1"`.
- The retired `collection_failed` and `unreadable_count > 0` symptoms and their name keys are gone.
- The vCenter alert keeps `Rollup|incomplete` (wait 1) as its second child.
- The generator `--check` is clean and the two-child rule holds (table above).
- Score Degraded (`score < 95` / `< 80`, wait 1, cancel 3) is no longer fired by a whole-object outage, because no score is pushed. A partial outage can still fire or cancel it (above).
- Recommendation 2100 is rewritten to match.

**(d) ShadowMode: correct.**
- `ShadowMode.decide` is on only for a parsed `0.0.0.<digits>`. A missing file, unreadable file, incomplete stamp, garbage or any other version is off. It never throws.
- The path is the same `conf` directory `getAdapterDescribeFile` already resolves.
- The builder stamps `Implementation-Version=<patch>.<build>` (`sdk_builder.py:806-833`), so a dev build reads 0.0.0.95 and a tagged release 1.0.0.95. Both were confirmed on real paks (table).
- One INFO line is logged per change. Off records nothing and makes no bulk read (`runShadow` returns on no records).

**(e) object_kind and the list view: correct statically.**
- The labels map all six kinds.
- The view's six SubjectType pairs (descendant and self) each carry the metric filter, and the columns are unbound so they resolve on every kind.
- The widget type is `View` on both dashboards, already on the 9.0.x allowlist (`test_dashboard_widget_types` passes).
- Coordinates don't overlap: scoreboard x1-4, list x5-9, About/Scan x10-12, every row below shifted by one (`test_build95_dashboards`).
- Not provable statically, so owed on devel (W11): whether a list view pinned to vSphere World, and on the World Summary to ComplianceWorld (through the cross-MP edge to VMwareAdapter Instance), returns descendants of all six kinds.

**(f) Docs:** largely updated. README, overview, data-reference, installing, CANONICAL_SCHEMA, the CHANGELOG line and the view descriptions all describe skip-and-flag. The contradictions are in B2 and W10.

### Findings

#### BLOCKING

**B2. An object with nothing readable keeps its last score and Controls Evaluated on every per-object surface, with no flag beside them, and the docs say the flag is there.**
- Where:
  - Columns and descriptions of `views/compliance-host-detail.yaml:13`, `compliance-vm-detail.yaml:13`, `compliance-vcenter-list.yaml:13`, `compliance-cluster-list.yaml:16`, `compliance-vds-list.yaml:16`, `compliance-portgroup-list.yaml:14`.
  - `dashboards/compliance-esxi-hosts.yaml` (heatmap on `score`, property list without `has_unreadable`).
  - `README.md:178-180`.
  - `docs/overview.md:228-229`, `:237`, `:251-253`.
  - `docs/data-reference.md:134`, `:160-161`, `:292-299`.
  - `docs/installing.md:288-289`.
- Authority: reviewer dimension 11 (docs that contradict behavior are BLOCKING); skill section *Unreadable is NOT compliant* and `knowledge/lessons/unreadable-is-not-compliant.md` contract 1 (the explicit unreadable signal must be visible, never a healthy-looking datapoint alone); decision point 2 ("flag the stale metric").
- What's wrong:
  - `ComplianceDecisions.complianceStats` (nothing-readable branch) and `versionUnreadableStats` push no `score` and no `total_count`, so both keep their last values. That is the decision.
  - None of the six per-kind views, nor the ESX Hosts heatmap or property list, shows `has_unreadable` or `collection_failed`.
  - The six view descriptions give "a score beside Controls Evaluated = 0 is retained" as the staleness tell, but here Controls Evaluated is stale and non-zero.
  - `data-reference.md:134` says `total_count` is 0 when nothing was evaluated, and `:298` says to read a retained score with `total_count`.
  - README, overview, data-reference and installing say the last score "stays on screen with the flag beside it". It does not: the flag lives only on the separate list and the alert.
  - For a version-unreadable object even the Unreadable column is stale, usually 0.
  - `overview.md:237`, `:251-253` say a read outage no longer moves the score or raises Score Degraded. A partial outage does both (see (b)).
- Smallest correct fix:
  1. Add `VCF-CF Compliance|has_unreadable` (for example "Not Read", or 1/0) beside the score in the six per-kind views and the ESX Hosts property list.
  2. Reword the six descriptions to "a score beside Not Read = 1 is from what could be read, and if Controls Evaluated did not change this cycle, from an earlier cycle; see the reason".
  3. Correct `data-reference.md:134` and `:298`, and the "flag beside it" sentences, to name where the flag actually is.
  4. Correct `overview.md:237` / `:251-253` to "a whole-object outage no longer moves the score; a partial one scores what was read and can move it either way".

  No change to the decision's push behavior is needed.

#### WARNING

**W10. The list's Count column shows a stale number for a version-unreadable object, while its description says it has none.**
- Where: `views/compliance-unreadable-objects.yaml:13-14`; `ComplianceDecisions.versionUnreadableStats`.
- Authority: dimension 11.
- What's wrong: `unreadable_count` is (correctly) not invented for a version-unreadable object. But VCF Ops shows the last value, typically 0 from the previous scored cycle, so the row reads "0 unreadable controls" next to "product version unreadable".
- Fix: say so in the description ("the count shown is from an earlier cycle"), or add `unreadable_controls` as a column (it reads "(not known: ...)").

**W11. Platform behaviors the decision rests on are asserted in the docs but not yet seen on devel.**
- Authority: shared reviewer doctrine (unproven is a finding); `knowledge/rules/validate-before-install.md`.
- Owed on devel:
  1. An open per-control alert on a key that stops receiving samples stays open, as the docs claim ("its alert stays").
  2. A view's CURRENT transform over the 24 hour window still shows the last value after more than 24 hours with no sample. If it blanks instead, the docs' "keeps its last value" is wrong in the other, safe direction.
  3. The multi-subject list returns descendants of all six kinds from vSphere World and from ComplianceWorld.
  4. Pushing "" to `unreadable_reason` clears it (precedent: `overrides_file` "" since build 90).
  5. `prefix-cap` count is 0 (W6).
- Fix: run these on devel before the tag. They are not code changes.

#### NIT

- **N10** `docs/data-reference.md:424`: "An empty list means every object was fully read on its last cycle". Objects of a held-back kind, and every object when vCenter was not reached, are not visited, so they are not on the list. `Rollup|incomplete` raises the vCenter alert for those cases. Say so.
- **N11** The ESX Hosts heatmap colors by `score` only, so an unreachable host stays its last color. Accepted by the decision. Mention it in the dashboard's About text, or adopt the fix in B2.
- **N12** `ObjectUnreadable` cause ordering: on a tie, causes keep first-seen order (documented), so the reason can differ between cycles when read order changes. It is cosmetic, but it can churn the property.
- **N13** W4 residual: a cycle running across a reconfigure re-reads `vsphere` per call, so it can switch to the new client part-way and mix two configurations in one cycle. Rare (edit during a cycle), and never a pass.

### Registry check (`knowledge/context/defects.md`)

- **DEF-023: open, unchanged.** `ComplianceStitcher.java` is untouched in `660999d..e527b03`. The close condition (page-count line, a fixture over 10,000 objects, or a forced-failure devel cycle) is unmet.
- **DEF-025: open, unchanged.** `ComplianceDecisions.staleControls` (`:573`) and `cleanBatch` are untouched. Only the doc comment of `pushedIds` (`:725`) changed. Holding unreadable controls is a separate, correct behavior. The retired-key single -1 push is still as registered.
- **DEF-026: open, unchanged since the first review.** There is still no cycle budget or failure cutoff (no deadline in `ComplianceAdapter.java`). Point 6 turns shadow reads off in releases, which removes the build 95 addition to cycle length, but the close condition is unmet.

**Registration candidate (orchestrator's call, RULE-012):** B2, if it survives. A stale healthy score with no tell beside it is the "unreadable shown as healthy" class at object level, now on the most-viewed per-object surfaces.

### If shipped as-is

Rollups, pass rates and alerts behave as Scott decided. But a host that stops responding keeps its last score (often a green 100) and its old control counts in the host table, the heatmap and the host details, with no flag beside them. Those views' own descriptions imply the number is current, and the only tell is a separate list on the environment dashboards and an alert that appears ten minutes later.

## Fix confirmation (2026-10-14, branch at `2cd25f5`)

- **Scope:** 7 commits on top of the re-reviewed `e527b03`: `075578f` (B2), `fb40985` (W10), `528831a` (N10), `8326450` (N11), `6dc4de0` (N12), `fb729e8` (N13), `2cd25f5` (CHANGELOG).
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.95.pak`, sha256 `cb83a80a...0047` (matches the brief), reference 0.0.0.94.

### Verdict: APPROVE (0 BLOCKING, 2 WARNING, 2 NIT)

B2, W10, N10, N11 and N12 are closed as claimed. N13 is mostly closed: the vCenter, Suite API and loader clients and the account are now copied once per cycle, the old vSphere client cannot log in again, and the next cycle picks up the new settings. The copy is not complete, though. The benchmark memory and the last resolved vCenter id are written by the cycle and read by the next one, and they sit outside the copy. A cycle that runs on after an edit refills them with the old vCenter's values after the edit cleared them. The commit's stated residual ("flagged unreadable, never a pass") is therefore wrong (W12). The new guard also lets four of five scratch bypasses through (W13). Neither is a regression: the same race existed before N13, and it needs an edit that changes the vCenter host to land during a running cycle. Both should be fixed in the same re-brief, per the factory rule that findings are fixed before the PR.

### Independent verification

| Check | Result |
|---|---|
| `validate-sdk` on a clean `git archive 2cd25f5` tree | OK (exit 0) |
| `build-sdk` of the same tree | Built. All 203 files inside the pak (nested jar, views.zip and content zips walked) are byte-identical to the author's pak. **Confirmed.** |
| `pak-compare` 0.0.0.95 vs 0.0.0.94 | PASS, 0 BLOCKING / 0 WARNING / 2 INFO. **Confirmed.** |
| `ci/run_java_tests.sh` (JDK 17) | Exit 0. All 18 Java tests pass, `BcHandshakeTest` ran (jars fetched, not skipped), and every Python guard passes, including the new `test_cycle_snapshot.py` |
| Factory `pytest tests/` | 2063 passed, 5 skipped. Compliance `pytest tests/`: 53 passed |
| Em-dashes in added lines (`e527b03..2cd25f5`) | None |
| `build_number` | Stays 95, as the CHANGELOG line says |

### Prior findings

- **B2: closed.**
  - All six per-kind views have `has_unreadable` ("Not Read") directly after the score. I checked this in the built pak's rendered views, not only the YAML.
  - The totals indices are correct in all six: host and VM `[5..10]`, vCenter and vDS `[3..8]`, cluster and portgroup `[2..7]`. In the rendered pak each one maps to has_unreadable, total, fail, unreadable, non-compliant and No SCG. The score and the string columns are never summed.
  - The vCenter, cluster, vDS and portgroup views add Unreadable Reason as an unsummed string column. Host and VM point to the list instead.
  - The ESX Hosts Compliance Details PropertyList has the row after SCG Applied. I compared the rendered dashboard's six `gridsterCoords` with 0.0.0.94: identical.
  - No view description still names "Controls Evaluated = 0" as the tell. The old wording ("flag beside it", "0 when nothing was evaluated", "no longer moves the score") is gone from every .md, .yaml, .xml and .properties file outside the CHANGELOG.
  - `data-reference.md` (total_count, the read-them-with paragraph), `overview.md` (Score Degraded, partial versus whole outage), README and installing now match the code.
- **W10: closed.** The list adds Control IDs (`unreadable_controls`). The version-unreadable path pushes "(not known: the benchmark depends on the version)" (`ComplianceDecisions.java:385`). The description says the count is from an earlier cycle.
- **N10: closed.** `data-reference.md` now limits the empty list to the objects that were visited, and names `Rollup|incomplete` and the collection status for the other cases.
- **N11: closed.** The ESX Hosts description, and the dashboard tables in README, overview and docs/README, say the heatmap keeps an unreadable host's last color.
- **N12: closed.** `ObjectUnreadable` sorts equal counts by plain words and keeps the alphabetically smallest detail. The new test records the same causes in two orders and gets one text.
- **N13: mostly closed, residual W12.** Details below.
- **W11: still owed on devel** (unchanged; not code).
- **N6, N7, N8: unchanged, outside the adapter.**
- **Descriptions:** every view and dashboard description is under 1024 characters. The longest are vDS at 1012 and Clusters at 1000 in the source, and 1015 and 1003 in the rendered XML. All are ASCII.

### N13, the snapshot, point by point

1. **Does any read later in the cycle bypass the copy? No.**
   - `configured*` is read only at the copy block (`ComplianceAdapter.java:576-580`) and in `onDiscard`.
   - Nothing from `collectWorld` through `onDiscard` reads `config.` or `this.config`.
   - The methods above `collectWorld` that the cycle calls (`sslContextFor`, `sslSocketFactoryFor`, `clientLog`) take the host as a parameter.
   - The VAMI client is built from `cycleConfig`.
2. **Can the closed old clients log in again? The vSphere client cannot. The Suite API client can (N14).**
   - `VSphereClient` checks `closed` in `connect()` (`:265`), after an in-flight login (`:358`, which logs the new session straight out), in `ensureSession` (`:483`), and in the mid-cycle re-login (`:2179`).
   - `SuiteApiStitcher.discard()` only releases the token. `SuiteApiStitchClient.ensureToken` acquires a new one on the next call.
   - So a cycle running across an edit keeps pushing through the old Suite API client to the local VCF Ops. The pushes land on the old cycle's own objects, so nothing goes to the wrong host.
3. **Does the next cycle pick up the new settings? Yes.** Every cycle copies `config` and the four `configured*` fields before its `try` block.
4. **Can the residual only produce unreadable, never a pass? No (W12).**
5. **Do the tests fail when the copy is bypassed? Only for some bypasses (W13).** Scratch mutations, each run against `test_cycle_snapshot.py` and the `CertificateTest`, `Build95TriageTest` and `OverridesTest` source pins:

| Mutation | Caught by |
|---|---|
| M3: bare `config.overridesFile` in `skipInForce` | `test_cycle_snapshot` |
| M6: configure also assigns `this.vsphere` | `test_cycle_snapshot` |
| M5: VAMI client from `this.config` | `CertificateTest` only |
| M1: `this.config.vcenterHost` in `collectVCenter` | **nothing** |
| M2: `configuredStitcher.matchVCenterAdapterInstance` in `collectVCenter` | **nothing** |
| M4: `configuredVsphere.ensureConnected()` | **nothing** |
| M7: a `configuredLoader` read after the copy | **nothing** |

### Findings

#### WARNING

**W12. The snapshot leaves out the state the cycle hands to the next cycle, and it is not taken atomically.**
- Where: `ComplianceAdapter.java:165`, `:168` and `:212` (configure clears `lastVcResourceId` and `memory`); `:235-238` (the swap); `:747` (`memory.retain`); `:773-775` (`lastVcResourceId = vcEntry.resourceId`); `afterPush` (`memory.record`, `:1263`); `LastBenchmarkMemory` (key `<Kind>|<moid>`; the vCenter's moid is the constant `"vcenter"`); `ComplianceDecisions.markNotCollected` (`:1118`, prefers the last id).
- Authority: skill section *Unreadable is NOT compliant*; reviewer dimension 5 (a moid on its own is not an identity across vCenters, which is the hazard the N13 commit names itself); shared reviewer doctrine (unproven is a finding).
- What's wrong:
  - **(a) Leak into the next cycle.**
    - The edit clears `memory` and `lastVcResourceId` mid-cycle. The old cycle then carries on. `afterPush` records a benchmark for every object it decides, even one whose reads all fail. `memory.retain(seen)` keeps those entries. Line 774 stores the old vCenter's resource id, because `vcEntry` comes from the stitcher cache loaded at the start of the cycle.
    - The first cycle on the new vCenter then inherits both.
    - If the new vCenter cannot be reached, `Rollup|incomplete` = 1 is pushed to the **old** vCenter's resource every failed cycle. The log line names the new host and the old resource id. If no instance monitors the old vCenter any more, its alert never clears.
    - If the new vCenter is reached but its version read fails, `decide` takes the old vCenter's benchmark from the `VCENTER|vcenter` key. That key always collides. Clusters, vDS and portgroups follow too when their moids happen to match. The new vCenter's real reads are then scored against the other vCenter's SCG, pushed, and alerted on. That is a scored result, passes included, not "flagged unreadable", so the commit's residual claim does not hold.
  - **(b) Torn copy.**
    - Configure writes `this.config` at `:165` and the clients only at `:235-238`, after building the vSphere client and running `SuiteApiStitcher.create`.
    - A cycle that starts in that gap copies the new account with the old clients. For example, it would match the vCenter by the new host name while reading the version through the old client.
    - The window is short, but nothing rules it out.
- Smallest correct fix:
  - In configure, build one immutable per-configuration holder: the account, the vSphere client, the loader, the Suite API client, the stitcher, a fresh `LastBenchmarkMemory` and a slot for the last resolved vCenter id. Publish it with a single volatile write after the clients are built.
  - `collectWorld` copies that one reference. The cycle reads and writes memory and the vCenter id only through it.
  - An old cycle then writes into its own orphaned holder, and the edit no longer has to clear anything in place.
  - Correct the residual sentence in the commit history's successor (CHANGELOG or overview).
- Not a regression (the same race existed before N13). It needs an edit that changes the vCenter host to land during a running cycle. **Registration candidate (RULE-012) if it is not fixed before the tag.**

**W13. `test_cycle_snapshot.py` does not fail on the most likely bypasses.**
- Where: `tests/test_cycle_snapshot.py`, `test_cycle_reads_the_account_copy` (its regex `(?<![\w.])config\.` skips `this.config.`) and `test_cycle_copies_once_at_start` (it counts assignments, not reads).
- Authority: reviewer dimension 9 (prove the behavior, do not assert it); shared reviewer doctrine. The adapter cannot run without the SDK, so this guard is the only proof N13 has.
- What's wrong: M1, M2, M4 and M7 pass every guard (table above).
- Fix:
  - Assert that `configured(Vsphere|Loader|Suite|Stitcher)` appears only in the field declarations, `configureAdapter`, the copy block and `onDiscard`.
  - Assert that `this.config` and bare `config.` appear nowhere from `collectWorld` through `onDiscard`.
  - With W12's holder, pin instead that the cycle reaches the clients only through the copied holder.

#### NIT

- **N14** The old Suite API client is not closed by the edit. `SuiteApiStitchClient.discard()` only releases its token, and `ensureToken` acquires a new one. A cycle spanning an edit therefore logs in again to the local VCF Ops, keeps pushing to its own objects, and leaves that token unreleased until it expires. The `onDiscard` comment ("instead of an NPE or a fresh login") and the W4 "closed client refuses re-login" are true only of the vSphere client. Fix: correct the comment. A closed state in `SuiteApiStitchClient` is framework code (route to `tooling`).
- **N15** `docs/overview.md` (N13 paragraph): "its remaining reads are unreadable". The appliance (VAMI) client is built per cycle from the cycle's account copy, and the edit does not close it, so those reads go on against the old vCenter. That is the right object, so nothing goes to the wrong host, but the sentence overstates. Say "its remaining vCenter inventory reads".

### Registry check (`knowledge/context/defects.md`; no `defects.local.md` in this clone)

- **DEF-023: open, unchanged.** `ComplianceStitcher.java` is not touched in `e527b03..2cd25f5`. The close condition is unmet.
- **DEF-025: open, unchanged.** `ComplianceDecisions.java` is not touched in this delta (`staleControls` still at `:573`).
- **DEF-026: open, unchanged.** There is still no cycle budget or deadline in `ComplianceAdapter.java` (no match for deadline or budget).

**Registration candidate:** W12, if it ships unfixed.

### If shipped as-is

A host, VM, vCenter, cluster, switch or portgroup that could not be read now shows "Not Read = 1" beside its score everywhere that score is shown, except the heatmap, and the docs say so. The leftover risk is narrow. If someone edits an instance to point at a different vCenter while a cycle is running, the next cycle can raise the "not collected" flag on the old vCenter, or, when the new vCenter's version cannot be read, score it against the old vCenter's benchmark for a cycle.

## Holder confirmation (2026-10-14, branch at `3ef7eaf`)

- **Scope:** 4 commits on top of the fix-confirmed `2cd25f5`: `ca48013` (W12, the holder), `41c2179` (W13, the guard), `e8db013` (N14), `3ef7eaf` (N15).
- **Pak:** scratch `b95final/vcfcf_sdk_compliance.0.0.0.95.pak`, sha256 `4e034d8c...a8120d` (matches the brief), reference 0.0.0.94.

### Verdict: APPROVE (0 BLOCKING, 0 WARNING, 1 NIT)

W12, W13, N14 and N15 are closed. Configure now builds one `Configured` holder and publishes it with one volatile write. Each cycle copies that reference once and touches the account, the clients and the cross-cycle state only through the copy. A cycle running across an edit can only refill its own, orphaned holder. Every bypass I tried against the new guard fails it, including ten at sites the author did not pick. Stopping setting the platform's `this.config` is safe: neither the framework nor the platform reads that field for this adapter. One NIT: a guard comment claims a check the code does not make.

### Independent verification

| Check | Result |
|---|---|
| `validate-sdk` on a clean `git archive 3ef7eaf` tree | OK (exit 0) |
| `build-sdk` of the same tree | Built. All 204 files inside the pak (nested jar, views.zip and content zips walked) are byte-identical to the scratch pak, `Configured.class` included. Only the outer zip timestamps differ. **Confirmed.** |
| `pak-compare` 0.0.0.95 vs 0.0.0.94 | PASS, 0 BLOCKING / 0 WARNING / 2 INFO. **Confirmed.** |
| `ci/run_java_tests.sh` (JDK 17) | Exit 0. Every Java test passes, `SnapshotHolderTest` included, `BcHandshakeTest` ran (not skipped), and every Python guard passes |
| Factory `pytest tests/` | 2063 passed, 5 skipped. Compliance `pytest tests/`: 51 passed, 64 subtests (53 before, because `test_cycle_snapshot.py` went from four test methods to two) |
| Em-dashes in added lines (`2cd25f5..3ef7eaf`) | None |
| `build_number` | Stays 95, as the CHANGELOG line says |

### The holder, point by point

1. **Contents and immutability: as claimed.** `Configured.java` holds `account`, `vsphere`, `loader`, `suite`, `stitcher`, a `LastBenchmarkMemory` created fresh with each holder, the vCenter id slot (`AtomicReference`) and the retired-Custom flag (`AtomicBoolean`). Every field is final, and `SnapshotHolderTest.immutable()` checks that by reflection. The memory and the two atomics change inside one holder, but the holder never swaps them out, which is what the design needs.
2. **One publish.** `configureAdapter` builds the vSphere client, the loader, the Suite API client and the stitcher first. It then makes its only write to `configured` (`ComplianceAdapter.java:224`), and only after that releases the old holder's clients (`:226-228`). A cycle can no longer pair the new account with the old clients: the account exists only inside the holder, so the torn copy in W12(b) cannot happen.
3. **One copy, used only through the copy.**
   - `collectWorld` reads `configured` once (`:561`) and assigns `cycle = c` (`:566`). That is the only write to `cycle` anywhere.
   - Every read of the memory, the vCenter id and the Custom flag goes through `cycle.`: `:634` (`markNotCollected`), `:737` (`retain`), `:764` (`rememberVcResourceId`), `:1015`/`:1029` (Custom bucket), `:1187` (`previous`), `:1253` (`record`).
   - `configured` appears only in its declaration, in configure, in the copy block and in `onDiscard`. There are no `this.config` or bare `config.` reads left in the adapter.
   - `cycle` is a field, not a local. That relies on the platform never running two collect cycles of one instance at the same time, which is the same assumption the code made before. Configure never writes `cycle`, so an edit cannot move a running cycle onto a new holder.
4. **A cycle spanning an edit refills only the old holder: confirmed.** All six writes listed above go through the holder the cycle copied at its start. The edit publishes a new holder whose memory and vCenter id are empty. Nothing reads the old holder again, and the `cycle` field drops it at the next cycle's start. The two W12(a) leaks (`Rollup|incomplete` on the old vCenter, and the new vCenter scored against the old benchmark through the `VCENTER|vcenter` key) are closed.
5. **Not setting `this.config` is safe.**
   - Framework (`src/vcfcf_managementpacks/adapter_framework/.../VcfCfAdapter.java`, unchanged since `sdk-buildkit-v1.0.11`, the tag CI's floating `sdk-buildkit-v1` resolves to): `config` is a protected field the framework declares itself, so the platform's `AdapterBase` cannot see it. `onConfigure` already set it to null (`:610`) before it called `configureAdapter`. Beyond that, the framework only passes it as an argument:
     - `onTest` (`:644`): the compliance tester ignores `cfg` and builds its own config from the `TestParam`. That has been true since build 46, because Test Connection runs on an instance that has never been configured.
     - `onDiscover` (`:684`): `getDiscoverer()` is not overridden, so nothing runs.
     - `needsRediscovery`, `collectEvents` and `collectRelationships` (`:728`, `:802`, `:806`): the `VcfCfCollector` interface defaults, which never dereference it.
     - `collect` (`:778`): the adapter's lambda ignores `cfg` and calls `collectWorld`.
   - `onDescribe` reads the adapter kind and describe.xml, not `config`. `onDiscard` does not read it.
   - `SuiteApiStitcher.create(this, ...)` and `SuiteApiStitchClient` read the platform's `adapter.getAdapterConfig()`, not this field.
   - The history has never contained a `config == null` check in `VcfCfAdapter.java`, so no framework path can skip a cycle because the field is null.
6. **SnapshotHolderTest runs the two scenarios through real code, with one limit.**
   - The holder, `ComplianceDecisions.markNotCollected` and `ComplianceDecisions.decide` (with the real bundled profiles) are real code. The test's control case shows that the old memory *would* score the new vCenter (`reusedPrevious`). The new holder gives `VERSION_UNREADABLE` instead, and `Rollup|incomplete` goes only to B's object or to nothing.
   - The publish-then-copy sequence itself is simulated with local variables, because the adapter cannot load without the SDK. The guard pins that sequence in the adapter source. I accept that split (the same one the review asked for in W13).

### Bypass mutations against the new guard

The review's M1, M2, M4 and M7 are in the test as subtests, and all fail the check. I also wrote ten mutations of my own, at sites the author did not anchor on, and applied each to the clean tree (script outside the repo):

| Mutation | Result |
|---|---|
| R1: `this.config.vcenterHost` in the `markCycleNotCollected` log | caught |
| R2: `configured.stitcher.pushStats` in `pushRollup` | caught |
| R4: `configured.vsphere.getVCenterVersion()` | caught |
| R7: `configured.loader.lastManualReviewApplied()` | caught |
| R8: `configured.memory.retain(seen)` | caught |
| R9: `configured.rememberVcResourceId(...)` | caught |
| R10: `markNotCollected(configured.lastVcResourceId(), ...)` | caught |
| R11: `ComplianceAdapter.this.configured.suite` in `refreshOverrides` | caught |
| R12: bare `config.overridesFile` in `refreshOverrides` | caught |
| R13: a lambda that sets `cycle = configured` mid-cycle | caught |
| R14: a new field written in configure and read in the cycle | **escapes** (N16) |

### Prior findings

- **W12: closed.** Points 1 to 4 above. The CHANGELOG corrects the N13 residual claim and says the leak could produce a scored result before this fix.
- **W13: closed.** All of the review's M1 to M7 fail the guard, and so do R1 to R13.
- **N14: closed.** The `onDiscard`, configure and `releaseClients` comments now say that only the vSphere client is closed, and that the Suite API client gets a new token if a running cycle calls it. The CHANGELOG notes that the issue #23/#28 entry overstated this. A closed state for the Suite API client stays framework work.
- **N15: closed.** The overview now says "remaining vCenter inventory reads", says appliance reads still go to the old vCenter (its own object), and says nothing carries over to the next cycle.
- **W11: still owed on devel** (unchanged; not code). **N6, N7, N8: unchanged, outside the adapter.**

### Findings

#### NIT

- **N16** `tests/test_cycle_snapshot.py`, the comment above the configure checks: "writes no other account or client field". The code checks only `this.config` and `cycle`. A new field that configure fills with a client and the cycle then reads (R14) passes the guard. That needs someone to add a field on purpose, so the risk is low. Fix: either drop the clause from the comment, or check that configure assigns only `this.configured` among instance fields. Authority: reviewer dimension 9 (prove the behavior, do not assert it).

### Registry check (`knowledge/context/defects.md`; no `defects.local.md` in this clone)

- **DEF-023: open, unchanged.** `ComplianceStitcher.java` is not touched in `2cd25f5..3ef7eaf`.
- **DEF-025: open, unchanged.** `ComplianceDecisions.java` is not touched in this delta (`staleControls` still at `:573`).
- **DEF-026: open, unchanged.** There is still no cycle budget or deadline in `ComplianceAdapter.java` (zero matches for deadline or budget).

**Registration candidate:** none. W12 is fixed, so the earlier candidate falls away.

### If shipped as-is

An instance edit during a running cycle now leaves that cycle on its own vCenter to the end. The next cycle starts fresh, with no carried-over benchmark and no vCenter id, so it can neither flag the old vCenter nor score the new one against the old one's SCG. Nothing an operator sees changes otherwise.

## Final confirmation (2026-10-14, branch at `eb612fe`)

- **Scope:** 2 commits on top of the holder-confirmed `3ef7eaf`: `afeaa71` (N16, configure assigns only `configured`) and `eb612fe` (the `has_unreadable` column is headed "Not Read").
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.95.pak`, sha256 `486631cec9aa46487f610a8ede841f4e1cc7aeefff076e3d228ecda5e15bfb57` (matches the brief), reference 0.0.0.94.

### Verdict: APPROVE (0 BLOCKING, 0 WARNING, 0 NIT)

N16 is closed and the relabel is complete. The delta is exactly what the brief says: no Java source changed, only the guard test, the dashboard test, six view YAMLs, the ESX Hosts dashboard, README, three docs and the CHANGELOG.

### Independent verification

| Check | Result |
|---|---|
| Delta `3ef7eaf..eb612fe` | 14 files, none under `src/`. Every non-test hunk is the label change "Not Fully Read" to "Not Read" (six view `display_name`s, the host details `label`, descriptions, README, overview, data-reference, installing) plus one CHANGELOG line. **Only what the brief claims.** |
| `validate-sdk` on a clean `git archive eb612fe` tree | OK (exit 0) |
| `build-sdk` of the same tree | Built. All 204 files inside the pak (nested jar, views.zip and content zips walked) are byte-identical to the author's pak. **Confirmed.** |
| `pak-compare` 0.0.0.95 vs 0.0.0.94 | PASS, 0 BLOCKING / 0 WARNING / 2 INFO. **Confirmed.** |
| "Fully Read" in the pak | Zero hits across every nested entry (also checked "Fully" alone, URL-encoded and UTF-16). "Not Read" appears in 14 entries. Zero hits in the adapter tree outside the CHANGELOG and the test that forbids it. |
| `ci/run_java_tests.sh` | Exit 0, every Java test and Python guard passes |
| Compliance `pytest tests/` | 51 passed, 68 subtests (64 before, plus M10 to M13) |
| Factory `pytest tests/` | 2063 passed, 5 skipped |
| Em-dashes in added lines | None |
| `build_number` | Stays 95, as the CHANGELOG line says |

### N16 guard: mutations

The clean tree passes the check. I applied the four new subtests' mutations myself (script outside the repo), plus three of my own, and read the reason each one fails, so none fails for an unrelated reason:

| Mutation | Result |
|---|---|
| M10: `this.cycleConfDir = ...` in configure | caught: "configure assigns this.cycleConfDir" |
| M11: bare `bulkShadow = true` | caught: "configure assigns field `bulkShadow`" |
| M12: new package-private `String lastHost`, set in configure | caught: "configure assigns field `lastHost`" |
| M13: `cycleSkippedInForce += 1` | caught: "configure assigns field `cycleSkippedInForce`" |
| X1: `this.config = null` in configure | caught (both the new check and the old one) |
| X2: new `private int hits`, `hits++` in configure | caught |
| X3: a local `String cycleConfDir` declared and reassigned in configure | passes, as it should (a shadowing local is not a field write) |

The guard also now fails if its own field scan misses `configured`, `cycle` or `cycleConfDir`, so a source reformat cannot quietly turn the field checks off. That closes R14 from the holder confirmation.

### Prior findings

- **N16: closed.** Mutations above.
- **W11: still owed on devel** (not code). **N6, N7, N8: unchanged, outside the adapter.**

### Registry check (`knowledge/context/defects.md`; no `defects.local.md` in this clone)

- **DEF-023: open, unchanged.** No file under `src/` changed in `3ef7eaf..eb612fe`.
- **DEF-025: open, unchanged.** Same.
- **DEF-026: open, unchanged.** Same.

**Registration candidate:** none.

### If shipped as-is

Same behavior as the holder-confirmed build. The flag column beside the score now reads "Not Read" and fits on screen in the host and VM views. A value of 1 there means at least one control could not be read this cycle, not that the object went unread entirely. The view descriptions and the docs say so.
