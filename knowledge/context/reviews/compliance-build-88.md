# SDK adapter review: compliance build 88

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-12 (local, America/Chicago)
- **Adapter:** `content/sdk-adapters/compliance`, branch `feat/build-88-rollup-unmatched-pod-skip`, three commits on `main` (`1b484f2`): `370f69f` (3:10 PM, AlertList rework), `8bda355` (3:35 PM, adapter rollup change), `a81668c` (3:37 PM, World Summary dashboard and drift test). Working tree clean.
- **Artifacts:** author's `dist/vcfcf_sdk_compliance.0.0.0.88.pak` (built 3:35 PM), sha256 `c958b2bf...5710f`; reviewer build from HEAD (3:41 PM, scratchpad), sha256 `b2fa44dd...19a9`. Reference: `dist/vcfcf_sdk_compliance.0.0.0.87.pak`, sha256 `c02671ae...d6cf` (matches the build 87 review).
- **Prior pass:** `compliance-build-87.md` (APPROVE, 0 / 0 / 1)
- **Verdict:** APPROVE (0 BLOCKING / 3 WARNING / 6 NIT)
- **Fit for a devel install: YES, from a fresh build of HEAD only** (W1), and once Scott's go is recorded (`knowledge/context/approvals/` has no build 88 record).

## Bottom line

The adapter change does what the design says and fails in the right direction. A failed VCF Ops resource list (exception, non-2xx, unparseable body) holds the kind back and raises `Rollup|incomplete` = 1, which fires the existing vCenter collection alert, so a Suite API hiccup cannot shrink the totals silently. Pods are skipped before matching; when the guest id read falls back, Pods surface as `VM|unmatched`, never as scored VMs, and the totals do not move. `vCenter|unmatched` is provably 0 whenever it is pushed. The summary dashboard passes the loader's summary rule, has no pin or self-provider widget, and every key it reads is declared on ComplianceWorld. The drift test would catch a regression to pins.

Three warnings. **W1:** the `dist/` build 88 pak was built two minutes before the summary dashboard commit and does not contain it; rebuild before install. **W2:** a resource list that parses but is incomplete (no `resourceList`, or more resources than the one 10,000 page) is still taken as complete, and since build 88 the objects it misses drop out of the totals with only a metric and an INFO line to say so. **W3:** README and `docs/overview.md` still say "four dashboards" and never mention the Summary tab.

## Independent verification

| Check | Result |
|---|---|
| `validate-sdk content/sdk-adapters/compliance` | OK (only the existing `-source 11` options warning) |
| `ci/run_java_tests.sh` | 12 Java suites pass (`ComplianceRollupTest`, `ComplianceDecisionsTest` include the build 88 cases and source pins; `EnvironmentKeyContractTest` 4 computed keys, 5 references); generator tests 16 OK; dashboard AlertList tests 5 OK |
| `scripts/generate_compliance_alerts.py --check` | "up to date" (136 + 6 alerts, 1 shared recommendation), exit 0 |
| `build-sdk` from HEAD into scratchpad | builds `0.0.0.88`; adapter working tree unchanged afterwards |
| Author pak vs reviewer pak (unpacked, recursive) | `vcfcf_compliance.jar` classes and `views.zip` contents identical. **Differs:** the author's pak has no `content/dashboards/VCF_Content_Factory_Compliance_World_Summary/` and no `content/dashboards/dashboards.properties` (W1). |
| `pak-compare` HEAD build vs 87 | gate PASS, 0 BLOCKING / 0 WARNING / 3 INFO (the three new summary dashboard files) |
| `pak-compare` author's pak vs 87 | gate PASS, 0 / 0 / 0. This is the stale artifact's result, not HEAD's. |
| `dashboards.properties` in the HEAD pak | one binding: `VCF_Content_Factory_Compliance_World_Summary=vcfcf_compliance:ComplianceWorld` |
| Rendered dashboards, 87 vs 88 | pinned definition ids 87 / 142 / 24 / 31 (ESX Hosts, Environment Overview, VMs, vCenter & Networking) in 87, 0 in 88; each 88 AlertList carries `15_21`. Summary dashboard JSON: 0 `selfProvider: true`, 0 pinned resource ids, 0 definition ids, AlertList depth 5. |
| describe.xml ComplianceWorld keys | `Summary|last_scan_timestamp` (string property), `Rollup|Environment|{scored, non_compliant, no_benchmark, avg_score}` (ComputedMetrics). Every key the summary dashboard reads is declared. |
| `defect-gate --pak compliance` | exit 2, DEF-022 (correct; a release gate, not a devel gate) |

## Mutation tests (independent)

Each mutation applied to a fresh scratchpad copy; only the relevant suite run. A no-op baseline passes both suites.

| Mutation | Result |
|---|---|
| R1 `toStats` pushes every kind's keys even when incomplete | fails ("VM unmatched held back") |
| R2 `recordUnmatched` also bumps `scored` | fails |
| R3 `isPodGuestId` case-sensitive | fails (`CRXPOD1GUEST`) |
| R4 `fetchResources` never clears the failed mark | fails (source pin) |
| R5 guest id retry removed | fails (source pin) |
| R6 Pod check disabled | fails (source pin) |
| R7 adapter `kindPushable` no longer marks incomplete | fails (source pin) |
| R8 `skipped_pods` omitted when 0 | fails |
| R9 `collectVimObject` evaluates an unmatched object anyway | fails (source pin) |
| R10 unmatched name cap ignored | fails |
| R11 `All|unmatched` emitted | fails |
| R12 `ComplianceDecisions.kindPushable` ignores the failed list | fails |

12 of 12 fail. The author's "26 of 27" claim is consistent with this. As before, the `ComplianceAdapter` / `VSphereClient` / `ComplianceStitcher` checks are source-text pins (those classes need the SDK jar); they fail loudly on a rewrite, never pass silently.

## Hunt list (from the brief)

**(a) Skip-before-read: can real objects leave the totals without a visible signal?**
- *Suite API exception, non-2xx, unparseable body:* safe. `fetchResources` adds the kind to `failedLoads` before the GET and removes it only after a non-null parse (`ComplianceStitcher.java:273-286`); `SuiteApiStitchClient` throws on any non-2xx (framework `SuiteApiStitchClient.java:1043-1053`). The kind is then skipped and marked incomplete (`ComplianceAdapter.java` `kindPushable`), its keys plus `All` and `Benchmark` hold their previous values, and `Rollup|incomplete` = 1 fires the vCenter collection alert, whose recommendation (nameKey 2100) now names this cause. Proven by R4, R7, R12.
- *Stale index across cycles:* not possible. `loadStitcherResources` reloads all six kinds every cycle, each loader installs fresh maps before fetching, and `failedLoads` is re-marked per kind every load.
- *Parsed but incomplete list:* **not safe (W2).** A 2xx body without `resourceList` is accepted as "0 resources" (`ComplianceStitcher.java:288`), and nothing checks that the single `pageSize=10000` page (line 279; unscoped, so it holds every vCenter's resources of that kind) is the whole set. Before build 88 a missed object was still scored and counted; now it is dropped from every total, and the only traces are `Rollup|<K>|unmatched` on the vCenter object and one INFO line. Neither is on a dashboard or behind an alert (N3).
- *Real cache miss (object newer than the VMWARE collection, or VMWARE does not collect it):* this is the design's intended "unmatched" case, counted and named. Accepted by design.
- *A processing throw inside a loader after a good parse* would leave a partial index without the failed mark. I found no throwing path: `getIdValue` and `findUuid` null-guard, and `SimpleJson` chaining is null-safe. Not a finding.

**(b) guestId retry fallback.** `getVms` retries without `config.guestId` only when the first `retrieveViewRows` returns null (SOAP fault or non-2xx), with a WARN naming the fault (`VSphereClient.java:315-327`). After a retry, or on the per-VM walk, `guestId` is null, `isPodGuestId(null)` is false, and Pods go to `matchVm`. They have no VirtualMachine resource (VCF Ops models them as kind Pod), so they land in `VM|unmatched` and are named in the INFO line. They are never scored, and because Pods were outside the totals anyway, the totals do not move between a normal cycle and a fallback cycle. One theoretical exception: `matchResource` falls back to exact-name and dot-prefix name matching, so a Pod whose name equals a real VM's name in the same vCenter would be scored and pushed onto that VM. That path is old, and it needs a name collision between a Supervisor Pod and a real VM. Not a finding. An IOException on the first call propagates (no retry) and marks the VM kind incomplete through `collectVms`'s catch, which is the right direction.

**(c) Held-back semantics vs "pushed every cycle".** The design says `unmatched` is "pushed every cycle like `Rollup|incomplete`, 0 when none". The code pushes it (and `VM|skipped_pods`) with the kind's other keys, so it is held back when the kind is incomplete (`ComplianceRollup.toStats`). That is the correct reading: on an incomplete cycle the count was not taken (vCenter listing failed, or nothing could be matched), and pushing 0 would be a sentinel, which the skill section *Unreadable is NOT compliant* forbids. `Rollup|incomplete` itself is still pushed every cycle, so the hold is visible. README, `docs/data-reference.md`, `docs/overview.md` and the CHANGELOG all describe the implemented behavior. The design file does not (N2).

**(d) vCenter-kind unmatched always 0 when pushed.** Proven. `recordUnmatched(VCENTER, ...)` is called in exactly one place, the `he == null` branch of `collectVCenter`, which returns null. `pushRollup(null, ...)` WARNs and pushes nothing. With no stitcher, `collectVCenter` returns null before any record and `pushRollup` returns early. `collectVimObject` is only called for vDS, portgroup and cluster. So any pushed rollup comes from a cycle where the vCenter matched and `vCenter|unmatched` = 0. The key is constant whenever it exists. That is documented, and harmless.

**(e) Summary dashboard vs the loader rule and the approved table.** The loader's summary rule (`src/vcfcf_core/dashboards/loader.py:1762-1784`) rejects `self_provider`, `pin`, `pin_to_world` and a self-providing ResourceRelationshipAdvanced; the build passed it, and the rendered JSON confirms 0 self-providers and 0 pinned resources. Layout matches the approved table row by row: Section; Scoreboard with four keys and the specified bounds; Scan PropertyList; the by-vCenter View with `select_first_row`; MetricChart; the SCG View; AlertList `15_21`, criticality [2,3,4], mode all, depth 5; one interaction (row 3 to row 5, `resourceId`). Name is 46 characters. Every metric key is declared on ComplianceWorld (table above). No key falls outside describe.xml. One comment inaccuracy (N5).

**(f) Would the drift test catch a regression to pins?** Yes. `widget_problems` flags any `alert_definitions:` key at any indentation, a missing or altered `alert_types` (including one that is only commented out), and a changed depth. `test_checker_catches_drift` shows the checker fails on each. The loader's only pin field for AlertList definitions is `alert_definitions` (`loader.py:3121`). Its `type_codes` alias would read as a missing `alert_types` and fail, which is safe. Limits: it checks YAML, not the rendered JSON, and `test_every_dashboard_is_covered` only sees AlertLists the line parser recognises (`^  - id:` and `^    type: AlertList`), so a new dashboard written with different indentation would escape it (N6).

## Other dimensions

- **Reflection-tolerant reads / exceptions:** no new vim25 casts. The new read is one extra path in an existing bulk call, with a null-tolerant row map. The Pod check and the match are pure. No new catch blocks except the stitcher's existing one, which now WARNs on an unparseable body.
- **Logging:** the per-object "no match" WARN moves to DEBUG behind `isDebugEnabled`. Unmatched objects are named once per cycle per kind at INFO, capped at 20. Pods are named at DEBUG, with the count at INFO. The new lines carry names and MOIDs only, no credentials (`knowledge/rules/no-secrets-on-disk.md`).
- **Memory:** `failedLoads` is bounded by six kind names. `unmatchedNames` lives in the per-cycle `ComplianceRollup` and is capped per kind.
- **MOID trap:** unchanged. Matching still goes through the owning-vCenter-scoped tables. Pre-existing, outside this delta: when `getVCenterInstanceUuid()` throws, matching degrades to unscoped. Noted, not a finding for this build.
- **Build hygiene:** `build_number: 88`, CHANGELOG entries present (one is wrong about pak impact, N1). The diff is confined to the rollup scope, the Pod skip, the stitcher failure mark, docs, the five AlertLists and the new dashboard.

## Findings

### BLOCKING

None.

### WARNING

**W1. The `dist/` build 88 pak is stale: it has no World Summary dashboard (owner: `sdk-adapter-author`, rebuild; the orchestrator gates install on it).** Authority: `knowledge/rules/validate-before-install.md`; reviewer workflow step 4 (the reported build must reproduce). `dist/vcfcf_sdk_compliance.0.0.0.88.pak` was written at 3:35 PM, with commit `8bda355`. `a81668c` (3:37 PM) added `dashboards/compliance-world-summary.yaml` and its `adapter.yaml` registration. The author's pak lacks `content/dashboards/VCF_Content_Factory_Compliance_World_Summary/` and `dashboards.properties`; everything else matches HEAD. Its pak-compare 0 / 0 / 0 is that artifact's result, while HEAD's is 0 / 0 / 3 INFO. Installed as-is, devel gets build 88 with no Summary tab, while the CHANGELOG says it ships. **Fix:** rebuild from HEAD, record the new sha256, and install that. My HEAD build (`b2fa44dd...19a9`) is the reference for what it should contain.

**W2. A resource list that parses but is incomplete is taken as complete, and since build 88 the missed objects leave the totals (owner: `sdk-adapter-author`).** Authority: skill section *Unreadable is NOT compliant* (a read that did not return the data must surface, not shrink the result); reviewer dimension 1. `ComplianceStitcher.fetchResources` clears the failed mark on any non-null parse. It then returns 0 resources when `resourceList` is absent (line 288) and never compares the one `pageSize=10000` page (line 279) with `pageInfo.totalCount`. The request is not scoped to this vCenter, so the page holds every vCenter's VMs, and 10,000 VMs is an ordinary enterprise inventory. No vendor document in the repo confirms that the Suite API honours 10,000 as a page size. Before build 88 such objects still counted in the totals (just not pushed); now they are unmatched and dropped, so Objects Scored and Non-Compliant fall. The only traces are a metric not on any dashboard and an INFO line. The class Javadoc's "never a wrong match" is still true, but "nothing lost from the totals" no longer is. **Fix:** in `fetchResources`, keep the kind marked failed when `resourceList` is missing or when `pageInfo.totalCount` exceeds the rows returned (or page through until it does not), so the kind is held back with `Rollup|incomplete` = 1. Add a source pin and a unit case. **Registration candidate** (RULE-012): the truncation exposure predates build 88 and is likely to survive acceptance, since devel is far below 10,000.

**W3. Docs parity: the Summary tab dashboard is not documented, and two sentences still say "four dashboards" (owner: `sdk-adapter-author`).** Authority: reviewer dimension 11. `README.md:11` ("four dashboards give you the big picture"), `README.md:56` ("Four dashboards install with the pack") and `docs/overview.md:125` ("any of the four dashboards"), and the overview's Dashboards table (lines 114-119), all predate the new dashboard. Nothing tells an operator that ComplianceWorld now has a Summary tab. It is `hidden: true`, so "four" is defensible for the dashboard menu. That is why this is a WARNING (absent everywhere) and not a contradiction. **Fix:** a row in the overview table and a sentence in the README dashboards section ("open the Compliance World object; its Summary tab shows ..."), and change "four" to say four dashboards plus the Summary tab.

### NIT

**N1. The `370f69f` CHANGELOG entry says "docs only, no pak change, so build_number stays 87" (owner: `sdk-adapter-author`).** The four bundled dashboards ship in the pak, and their JSON changed (284 pinned ids in 87, 0 in 88, `15_21` added). **Fix:** reword it as part of build 88.

**N2. The design file still says `unmatched` is "pushed every cycle like `Rollup|incomplete`" (owner: orchestrator).** The implementation holds it back with the kind, which is the safer reading (hunt item c) and is what every shipped doc says. **Fix:** amend `knowledge/designs/sdk-adapters/compliance-rollup-unmatched-and-pod-skip.md` to record the deviation and why.

**N3. Unmatched objects are visible only as a vCenter metric and an INFO line (owner: orchestrator, design follow-up with Scott).** The design accepted this level of visibility. But if a kind's whole list comes back empty with a 2xx (the VMWARE adapter not yet collected, or a scoping mismatch), Objects Scored on the Overview and the new Summary tab simply shrink, and nothing on screen says why. **Fix (proposal):** an Unmatched column in the by-vCenter view, or a symptom on `Rollup|<K>|unmatched` > 0. File it as a follow-up issue, not a build 88 change.

**N4. The type filter widens what the alert panels show (owner: orchestrator, devel observation).** `15_21` matches any Application / Compliance alert in VCF Ops, not just this pak's. At depth 4 the vCenter & Networking "Failing Controls" panel now lists every host and VM compliance alert under the selected vCenter (before: 31 vCenter, cluster, vDS and portgroup definitions). The ESX Hosts panel now includes the host's VMs' alerts. This is what Scott asked for ("cover all the children"), but it changes what those panels mean. **Fix:** confirm on devel that the volume is acceptable (388 active alerts on 10/02).

**N5. The summary AlertList's depth comment describes a path the widget does not walk (owner: `dashboard-author` via the orchestrator).** With `select_first_row: true` and the view's subject `VMwareAdapter Instance`, the AlertList input is always a vCenter row, so depth 4 reaches every VM. Depth 5 is harmless over-reach, but the "ComplianceWorld > ..." comment (`compliance-world-summary.yaml:138`) and the drift test's expected 5 encode the wrong reason. **Fix:** either keep 5 and correct the comment to "input is the selected vCenter (4); 5 kept as margin", or set 4 and update the test.

**N6. The drift test's coverage check only sees AlertLists its line parser recognises (owner: `sdk-adapter-author`).** `test_every_dashboard_is_covered` relies on `^  - id:` and `^    type: AlertList`, so a new dashboard YAML indented differently would carry an unchecked AlertList. **Fix:** also fail when a dashboard's text contains `AlertList` but the parser found no widget.

## Registry check (`knowledge/context/defects.md`)

Open entries: DEF-004 (vcommunity-os), DEF-017 (factory:packaging-cli), DEF-019 (factory:extractor), DEF-020 and DEF-021 (vcommunity-vsphere), **DEF-022 (compliance)**. No `defects.local.md` in this clone.

- **DEF-022: open, still present, unchanged.** `ControlEvaluator.java:150-161`: when the setting is absent and `allowsUndefined(expected)` is false (the branch at line 151), the code `continue`s without recording a pass, fail or unreadable. `ControlEvaluator.java` is not in the build 88 diff. It does not block the devel install; it blocks a `v*` tag, and `defect-gate` enforces that (exit 2).

No closure proposed. **Registration candidate:** W2 (an incomplete VCF Ops resource list is accepted as complete; truncation past one page drops objects from the totals since build 88).

## Devel checklist (after a fresh HEAD build and Scott's recorded go)

1. **Install the right artifact.** Rebuild from HEAD (W1) and confirm the pak contains `content/dashboards/dashboards.properties` before upload.
2. **Rollup (design expectation).** On wld01's vCenter object: `Rollup|VM|scored` 25, `Rollup|VM|skipped_pods` 18; `skipped_pods` 0 on mgmt and wld02; `Rollup|<K>|unmatched` 0 for every kind on all three; `Rollup|incomplete` 0. One interval later, ComplianceWorld `Rollup|Environment|scored` 175 and `non_compliant` 140.
3. **Logs per cycle.** `VM compliance: N VMs seen, 18 vSphere Pod VM(s) skipped` on wld01; the summary line's "0 with no VCF Ops resource"; no `bulk VM read with config.guestId failed` WARN; no `<Kind>: N object(s) with no matching VCF Ops resource` lines (if any appear, their names explain them).
4. **Alert panels.** All five AlertLists show alerts (Environment Overview, ESX Hosts, VMs, vCenter & Networking, Summary). If they do, README Known issues #30 and #31 can close. Note the vCenter & Networking volume (N4).
5. **Summary tab.** Open Compliance World: the Summary tab shows the new dashboard; the Scan property has a value (the design says drop the widget if it is empty); both View widgets list rows (the ComplianceWorld to vCenter walk on a summary page is unverified); selecting a vCenter row drives the alert list.

## If shipped as-is

From `dist/` today: devel gets the corrected rollup and the alert panel rework but no Compliance World Summary tab, despite the CHANGELOG. From a fresh HEAD build: Objects Scored and Non-Compliant drop to the objects VCF Ops actually has (175 / 140 on devel), Pods are counted separately, a Suite API outage holds the totals and raises the collection alert, and the Summary tab appears. A public release is still refused by `defect-gate` until DEF-022 is fixed.
