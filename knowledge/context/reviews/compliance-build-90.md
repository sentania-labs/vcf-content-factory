# SDK adapter review: compliance build 90

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-13 (local, America/Chicago)
- **Adapter:** `content/sdk-adapters/compliance`, branch `feat/build-90-overrides-file`, HEAD `0f833bd`, four commits `a27fea6..0f833bd` (all stamped 10:28 AM) on top of the build 89 baseline `72c44e6`. Working tree clean before and after every check.
- **Artifacts:** author's `dist/vcfcf_sdk_compliance.0.0.0.90.pak` (built 10:27 AM), sha256 `078bdb01...27a4` (matches the brief); reviewer build from HEAD into the scratchpad, sha256 `51ff59cf...2334`. Reference: `dist/vcfcf_sdk_compliance.0.0.0.89.pak`.
- **Design:** `knowledge/designs/sdk-adapters/compliance-overrides-file.md`
- **Prior pass:** `compliance-build-89.md` (APPROVE, 0 / 1 / 1)
- **Verdict:** APPROVE (0 BLOCKING / 2 WARNING / 5 NIT)
- **Fit for a devel install: YES.** Not fit for release: DEF-022 (open, blocking) still gates it, and W1 below shows build 90 gives operators a new, documented way to hit DEF-022.

## Bottom line

The overrides file does what the design says, and the cardinal rule holds for unreadable reads: no Skip, Override or Profile entry can turn an `(unreadable)` control into a pass. The parser refuses DOCTYPE, so external and internal entities are both blocked (I checked both). Pins come from the loader's output, so the manual-review overlay and the appliance-settings downgrade still apply under a pin. Skip cleanup only touches this instance's own objects, and only controls a bundled profile evaluates for that kind. The template is valid XML with every entry commented out, and it ships at `content/files/solutionconfig/` directly. The new setting, the World attributes, the labels and the generated alert are all in the pak. The author's pak matches a fresh HEAD build entry for entry.

Two warnings. **W1:** an Override that drops "or Undefined" from an advanced setting (an operator making the rule *stricter*) runs into DEF-022. An object with the key unset is then not failed but dropped from the control, and the pass it had before is retired to -1. I reproduced this on `vm.deactivate-console-copy`. **W2:** a fetch failure with no copy in force (a persistent 401/403/5xx, or no Suite API channel) runs on the guide's values with no alert, indefinitely. The status text says "VCF Operations did not answer" even when it answered with a 403.

## Independent verification

| Check | Result |
|---|---|
| `git diff --stat 72c44e6..0f833bd` | 26 files: new `ComplianceOverrides.java`, `OverridesStore.java`, `OverridesTest.java`, template, `docs/overrides.md`, `tests/test_overrides_template.py`; edits to adapter, config, decisions, selector, profile, describe.xml, resources, generator, docs, CHANGELOG, `adapter.yaml` (89 to 90), `ci/run_java_tests.sh`. `ControlEvaluator.java` and `ComplianceStitcher.java` untouched. Matches the stated scope. |
| `validate-sdk content/sdk-adapters/compliance` | OK (only the existing `-source 11` warning) |
| `build-sdk` from HEAD into the scratchpad | builds `0.0.0.90`; logs `content/files/solutionconfig/compliance_overrides_template.xml` |
| Author pak vs reviewer pak (recursive, nested zips, jar and `overview.packed` unpacked) | 242 entries each, **zero content differences** |
| Pak 89 vs author pak 90 (recursive) | 16 new entries: the 13 `ComplianceOverrides*` / `OverridesStore*` classes, `content/files/`, `content/files/solutionconfig/`, the template. Changed: the 6 touched classes and their inner classes, describe.xml, both resources.properties, the version and manifest files, overview html. Nothing else. |
| `pak-compare` author 90 vs 89 | gate PASS, 0 BLOCKING / 2 WARNING (identifier count 6 vs 5; ComplianceWorld group attributes 6 vs 1) / 1 INFO (template present). **Matches the author.** |
| Template in pak | byte-identical to source, at `content/files/solutionconfig/compliance_overrides_template.xml` (top level, no subdirectory, which matters because of the installer's `sub[i]` bug) |
| `ci/run_java_tests.sh` | 13 Java suites pass (OverridesTest included); generator 17 OK (`--check` up to date, 144 alert definitions, 143 at build 89); AlertList 6 OK; widget types 2 OK; template 5 OK |
| `pytest tests/` | 30 passed, 11 subtests |
| Em-dashes in added text | none in authored text. The only hit is the generated `docs/inventory-tree.md` stamp line, which `tooling` owns and which predates this build. |

### Reviewer probe (scratch harness under the session scratchpad, compiled against `src/`, nothing written to the repo)

- `<Override control="vm.deactivate-console-copy" expected="TRUE"/>` (the SCG value is `TRUE or Undefined`) is accepted. A VM with the key unset gets pass 1 / total 1 under the SCG value, and **pass 0 / fail 0 / total 0, no result** under the site value. See W1.
- `<Skip control="ESX.ACCOUNT-LOCKOUT-DURATION"/>` is rejected as an unknown id. `" esx.account-lockout-duration "` is trimmed and accepted. Control ids are case-sensitive and trimmed.
- An internal-subset DTD (entity expansion) is refused with "DOCTYPE is disallowed". The external entity case is in OverridesTest.
- An Override of a manual-review control (`esx.ad-admin-group-name`) is rejected ("does not check this control automatically").

## Dimension walk

1. **Cardinal correctness.** Unreadable stays unreadable. `withSiteExpected` changes only `expectedValue`. The `UNREADABLE` sentinel short-circuits before any comparison (`ControlEvaluator.evaluateVimProperties` ~384), and `evaluateControlsUnreadable` ignores the expected value. `complianceProps` leaves `(unreadable)` Actual as it is (tested). `checkValue` allows the absence-is-compliant forms (`Not Present`, `X or Undefined`) on advanced settings only, where absence is a real "not set" and not a failed read. A rejected Override leaves the SCG value everywhere (tested). Skip is an explicit operator exclusion: it is visible in `overrides_skipped`, and the key goes to -1. The zero-divisor contract is untouched. **Exception: W1.**
2. **vim25 reads.** No new vim25 code.
3. **Exception granularity.** `refreshOverrides` never throws: every failure becomes a status. A parse failure is a `ParseException`, not a swallowed pass. `InterruptedException` restores the flag (tested). The two empty catches in `secureFactory` are for unsupported optional parser features, and the disallow-doctype feature is set without a catch, so it fails closed.
4. **Loader contract.** The XML is parsed by element and attribute name. Unknown elements and attributes are rejected and reported. A wrong root is a parse failure.
5. **Stitching identity.** No new foreign keys. Status keys go to `vcEntry.resourceId`, the instance's own matched vCenter.
6. **Logging.** One INFO per cycle, one WARN per rejected entry per cycle, one WARN per cycle for absent, parse failed or fetch failed. Exception messages carry the URL and HTTP status, no token. Log lines echo entries as written, which is fine since the file holds no secrets.
7. **Memory and hygiene.** One parse is kept per instance. Profiles are copied, never mutated, so the loader cache stays clean.
8. **API discipline.** One GET per cycle, and none when the setting is empty.
9. **Build hygiene.** build_number 90, a CHANGELOG line, and a diff limited to scope. The generator change is additive, and `--check` is clean.
10. **Gap honesty.** Docs say plainly that new controls, alert names and recommendation text cannot change from the file, and that the recommendation may still quote the guide's value. That is an honest account of the design's "alert text carries the site value", which turned out impossible with static alerts.
11. **Docs parity.** `docs/overrides.md`, README, installing, data-reference, overview, building and REFERENCE match the code, with W1, N1, N2 and N3 as the exceptions. The ComplianceWorld last-writer behavior is stated in overrides.md, data-reference, overview and README. Wait and cancel cycles in the docs (1/1 for the overrides alert, 3 for per-control cancel) match the generator.
12. **Registry.** Below.

## Findings

### WARNING

**W1. An Override that removes "or Undefined" from an advanced setting drops unset objects instead of failing them (DEF-022, newly reachable from the file) (owner: `sdk-adapter-author`).** Authority: `knowledge/lessons/unreadable-is-not-compliant.md`, skill § *Unreadable is NOT compliant*, DEF-022.

`ComplianceOverrides.checkValue` accepts a plain value (`TRUE`), `(non-empty)` or `not:X` on an advanced setting whose SCG value carries "or Undefined". At scoring time `ControlEvaluator.java:150-162` hits `continue` for an absent key unless the expected value allows undefined. So an object with the key unset is in no result, pass, fail or total. Its last value is then retired to -1 by the cleanup (the control is in the current benchmark and was not pushed), with Actual `(not in applied benchmark: VMware_SCG_9.0)`. That is wrong as well, because the control *is* in the applied benchmark.

The operator wrote a stricter rule and got a higher score. Reproduced above on `vm.deactivate-console-copy`. This is the most natural thing to do with Override on the VM advanced settings (about 15 of 16 in SCG 9.0 carry "or Undefined"). The docs imply it works ("Compliant when the setting is X or is not set" next to a plain X, and "A host set to anything else fails"). I graded it WARNING, not BLOCKING, for three reasons: the root defect is DEF-022, already registered as blocking; the release defect gate refuses this pak while DEF-022 is open; and a devel install harms nothing.

**Fix:** land DEF-022's known fix (an absent key whose expected value does not allow undefined becomes a fail with Actual `(undefined)`), and add an OverridesTest case: an Override `TRUE` on `vm.deactivate-console-copy` with the key absent is a fail. Until then, overrides.md should say that on advanced settings a plain value does not fail an object where the setting is unset.

**W2. A fetch failure with no copy in force raises no alert and can last forever (owner: `sdk-adapter-author`).** Authority: skill § *Gaps, name them, never hide them*; the design's Visibility section (status and alert so the operator knows the file is not in force).

`OverridesStore.Snapshot.notLoaded()` is true only for ABSENT and PARSE_FAILED. FETCH_FAILED covers every other failure: no Suite API channel, a 401 after re-auth, a 403 (for example the channel identity lacking the configuration-file read privilege), a 5xx, a timeout. With no earlier copy (first cycle after an adapter or collector restart, or a persistent failure from the start), the instance runs on the guide's values with only `overrides_status = fetch failed` and a WARN line. Skips are not applied, so skipped controls are pushed live, alert, and get cleaned when a later fetch works. The docs call it "transient" and say "VCF Operations did not answer", but a 403 is an answer and nothing bounds the duration.

**Fix:** set `overrides_not_loaded = 1` when the status is FETCH_FAILED and `parsed == null`, or after N consecutive fetch failures whatever the copy. Update the alert recommendation and the overrides.md status table to match ("could not be read: <detail>" rather than "did not answer"). The keep-last-good behavior can stay.

### NIT

**N1. `overrides_skipped` / `overrides_overridden` count entries accepted against any bundled profile, not entries in force for this instance.** `resolve` checks against `known` (all bundled plus the instance's own). An instance fixed to `VMware_SCG_9.0` with `<Override control="esx.account-lockout" .../>` (a 6.7/7.0-only id, confirmed by the probe) logs "applied", counts 1, and changes nothing it scores. overrides.md and data-reference say "in force". Fix: count ids present in the cycle's selected profiles (`profilesByName`), or reword to "accepted".

**N2. Two accepted value forms are undocumented.** `checkValue` accepts `vmx-N or higher` (text controls; it is in the CHANGELOG) and `X or Not Present` (advanced settings). Neither overrides.md's table nor the template lists them. Add both rows.

**N3. The overrides.md Step 4 key table omits `VCF-CF Compliance|Summary|overrides_not_loaded`**, the metric the alert fires on (data-reference lists it). Add the row.

**N4. Control ids and element names are case-sensitive, and the docs do not say so.** A mis-cased id is rejected visibly, so this is safe, but one line in "Step 3" saves an operator a cycle.

**N5. No source pin on the SDK-bound wiring.** OverridesTest covers the SDK-free pieces well, rejection paths included: 11 parse rejections, 5 resolve rejections, malformed, empty, wrong root, XXE, absent, parse, fetch and path refusal. Nothing pins the adapter wiring, though: `refreshOverrides` before `buildSelector`, `cleanupPlan(..., cycleOverrides.skipped)`, `orphanProps(..., skipped, overridesFile)`, `complianceProps(..., siteOverriddenFor(...))`, and `pushOverridesStatus` after `pushRollup`. If the skipped set stopped reaching `cleanupPlan`, skipped controls would keep a stale 0 or 1 with every test still green. The build 88 idiom (string pins in `ComplianceDecisionsTest` ~416) fits.

### Notes (not findings)

- **"An upgrade can replace the template"** is accurate: only a force upgrade overwrites it (`summary_dashboard_pak_binding.md` § *Pak upgrade and the configuration-file store*). A non-force upgrade leaves the old template and logs an ERROR-level "already exist" import failure. A copy whose name differs from the template only in case is the **same** store entry (the key is lowercased), so a force upgrade would overwrite it and an uninstall with `removeContent` would delete it. The docs' "a name the pack never uses" covers this in practice. A one-line "not just a case change" would make it explicit.
- **ABSENT is any HTTP 400 or 404**, without checking apiErrorCode 1501, because `SuiteApiStitchClient.rawRequest` throws before reading the error body. This is consistent with the investigation. Checking 1501 would take a `tooling` change.
- **Live proof still owed on devel** (a static review cannot supply it): the UI has a copy action for a Management Packs Configuration file (the docs' Step 1 depends on it); the template imports at install over 89; a user copy fetches 200 through the instance's channel; Skip retires the key and its alert cancels; Override shows "(site override)"; a VM pin changes `profile_name`; and the malformed-file and absent-file alerts fire and cancel. These are the design's own verification steps.

## Registry check (`knowledge/context/defects.md`)

Open defects with `Affects: compliance`: DEF-022, DEF-023. No `defects.local.md` exists.

- **DEF-022 (blocking, open): still present, now with a wider reach.** Re-checked `src/com/vcfcf/adapters/compliance/ControlEvaluator.java:150-162`, unchanged (the file is not in the diff). Build 90 adds an operator-reachable path into it (W1, reproduced). Proposal for the orchestrator: amend DEF-022's summary to name the override path, and add "an OverridesTest case with an Override that removes 'or Undefined' and an absent key is a fail" to its close condition. Not a new registration: same root, same fix.
- **DEF-023 (tracked, open): fix in place, closure still owed.** `ComplianceStitcher.java` is untouched in this build (not in the diff stat), and `ComplianceDecisions.resourcePageOutcome` is unchanged (the decisions diff touches only the build 90 additions). Closure still needs devel proof of the paging, which the build 90 devel install can supply.

**Registration candidates:** W2, if it is not fixed before release (an alert-layer gap that is silent and unbounded). W1 folds into DEF-022 as above.

## Re-review (fix commits ed4236d and a285ce9, HEAD a285ce9)

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-13, 10:58 AM (local, America/Chicago)
- **Scope:** `git diff 0f833bd..a285ce9`, 14 files. `ControlEvaluator.java` (DEF-022), `OverridesStore.java` (W2), `ComplianceOverrides.java` and `ComplianceAdapter.java` (N1), `ControlEvaluatorTest.java` and `OverridesTest.java`, the generator recommendation text, template, docs, CHANGELOG, CANONICAL_SCHEMA. `ComplianceStitcher.java` untouched. `build_number` stays 90 (the pak was never installed). Working tree clean before and after.
- **Artifacts:** author's `dist/vcfcf_sdk_compliance.0.0.0.90.pak`, sha256 `b59a3181...707f` (matches the brief, built 10:48 AM, commit a285ce9 stamped 10:49 AM). Reviewer build from HEAD into the scratchpad, sha256 `d0c99b75...8540`.
- **Verdict:** CHANGES REQUESTED (1 BLOCKING / 1 WARNING / 3 NIT)
- **Fit for a devel install: YES.** The one BLOCKING is a README sentence; the code delta is correct. It blocks the ship step, not the devel proof.

### Bottom line

All seven prior findings are closed, and DEF-022 is fixed as its close condition asks. An unset advanced setting now fails with Actual `(undefined)` unless the guide allows absence. The dvfilter exception cannot mask an unreadable read and cannot reach any other bundled control. Two things stop an APPROVE. **B1:** the landing README still says absent settings are skipped and points to a Known issues entry this build removed. **W3** (new, pre-existing since the repo's root commit, not touched here): `vm.dvfilter` always passes, because its parameter is a wildcard that is looked up literally.

### Independent verification

| Check | Result |
|---|---|
| `validate-sdk` | OK (only the existing `-source 11` warning) |
| `build-sdk` from HEAD | builds `0.0.0.90`, template logged at `content/files/solutionconfig/` |
| Author pak vs HEAD build (recursive, nested zips and jar unpacked) | 242 / 242 entries, **zero content differences**: the author's pak is HEAD |
| Pak 89 vs pak 90 (recursive) | the same 16 new entries and the same changed set as the first pass |
| `pak-compare` 90 vs 89 | gate PASS, 0 BLOCKING / 2 WARNING (identifier count 6 vs 5; ComplianceWorld group attributes 6 vs 1) / 1 INFO (template). Same as the first pass. |
| `ci/run_java_tests.sh` | 13 Java suites pass (ControlEvaluatorTest, OverridesTest included); generator 17 OK, `--check` up to date; AlertList 6, widget types 2, template 5 OK |
| `pytest tests/` | 30 passed, 11 subtests |
| Em-dashes in added lines | 0 |

### Prior findings

| Finding | Status | Evidence |
|---|---|---|
| W1 (stricter Override drops unset objects, DEF-022) | **Closed** | `ControlEvaluator.java:176-191`: an absent or empty value is a result with Actual `(undefined)`, fail unless `allowsUndefined`. `OverridesTest.overrideDropsOrUndefined` (line 323): Override `TRUE` on `vm.deactivate-console-copy`, key absent, asserts "unset FAILS under the site TRUE", total 1, Actual `(undefined)`. A failing result is pushed, so the cleanup no longer retires it with "(not in applied benchmark)". Template and overrides.md now say a plain value fails an unset object. |
| W2 (fetch failure with no copy, silent and unbounded) | **Closed** | `OverridesStore.java:100-110`: `notLoaded()` is true for FETCH_FAILED with `parsed == null`, or `fetchFailures >= 3`. The counter resets on a good fetch, an absent result, a path refusal, an empty name and a new name. A parse failure resets it as well, since the fetch worked. `fetchReason` (line 173) maps 401/403 to `refused (HTTP 4xx)`, other statuses to `HTTP nnn`, otherwise `no answer (<Exception>)`. `OverridesTest.fetchFailureAlert` (line 678) covers 403 and 401 with no copy, no channel, timeout, 1 and 2 failures with a copy (no alert), the 3rd (alert, "fetch failed 3 cycles"), the 4th, recovery, a parse failure ending the run, and a new name. The generated recommendation (nameKey 2042) and overrides.md say "refused" and no longer say "did not answer". The claim that the collector log names the identity is true: `SuiteApiStitchClient` logs `principal=` at INFO when it starts (framework lines 333, 359, 388). See N7 for the no-channel corner. |
| N1 (counts not in force) | **Closed** | `Resolved.skippedIn` / `overriddenIn` (`ComplianceOverrides.java:550`) count an id only when the profile that governs its kind scores it: the pin for a pinned kind, otherwise the instance's own profiles. `buildSelector` computes them from the unadjusted profiles and resets them to 0 on an empty file. `pushOverridesStatus` uses them. `OverridesTest.inForceCounts` (line 360) covers fixed 9.0, an 8.0 host pin and Auto. |
| N2 (undocumented forms) | **Closed** | `vmx-N or higher` and `X or Not Present` rows are in overrides.md and the template |
| N3 (`overrides_not_loaded` row) | **Closed** | in the overrides.md Step 4 table |
| N4 (case sensitivity) | **Closed** | overrides.md and the template; overrides.md also covers a copy name that differs only in case |
| N5 (no wiring pin) | **Closed, and the pin bites** | `OverridesTest.adapterWiringSourcePins` (line 779). Comments are stripped before matching. I mutated three scratch copies of HEAD: (1) `cleanupPlan(..., Collections.emptySet())`, (2) the real call commented out next to an empty-set call, (3) `orphanProps(..., emptySet(), ...)`. **All three fail** OverridesTest with "cleanBatch: expected, in order: ...". The unmutated copy passes. |

### Focus checks

**(a) DEF-022 fix.** With a successful read, a missing or empty value goes to one branch (`ControlEvaluator.java:176-191`): a pass only for `X or Undefined`, `X or Not Present` or bare `Not Present`, otherwise a fail. Both outcomes carry Actual `(undefined)` and sit in pass, fail and total. `(non-empty)` and `not:X` reach the mode checks only with a present value, so an absent one fails. `ControlEvaluatorTest.absentAdvancedSetting` (line 112) asserts this for six forms: "plain TRUE, unset: fail", "X or Undefined, unset: pass", "Not Present, unset: pass", "X or Not Present, unset: pass", "(non-empty), unset: fail", "not:X, unset: fail (absence is never 'not equal')", plus "failing controls stay in the denominator" (total 6, score 50) and "absent is not unreadable". The map reaching `evaluateControls` comes only from a successful `QueryOptions` / `extraConfig` read. Every fault throws `ReadFault` or `AdvancedSettingsUnreadableException` and goes to `evaluateControlsUnreadable` (`VimOptions.java:52-111`, `ComplianceAdapter.java` around 1317, 1469 and 1588). An unreadable read therefore never reaches the new fail branch, and never the pass branch either. Scale: across the five bundled profiles, 21, 35, 40, 44 and 46 advanced-setting controls (6.7 to 9.1) have no absence-allowing form. Those now fail when unset, which is the change DEF-022 asks for. The CHANGELOG says scores may drop.

**(b) The explicit-empty exception.** `expectsExplicitEmpty` (line 324) matches `NULL` (case-insensitive) or a value of two or more characters that is empty or blank once one pair of surrounding quotes is removed. It fires only when the key is **present** with an empty value (line 164). An absent key still fails ("absent against \"\": fail (undefined)"). I read every advanced_setting row by header in all five canonical CSVs. The only match is `esx.network-dvfilter` (HostSystem): `NULL` in 6.7, `""` in 7.0 to 9.1. Values such as `esx.password-complexity` (`"random=0 ..."`, quoted) do not match. In the bundled profiles it cannot widen to another control. Through the overrides file it can (N6). On the cardinal rule: an empty Actual can only come from a successful `QueryOptions` that returned a `<value>` element with no text (`VimOptions.fromQueryOptions:58-63`; an OptionValue with no `<value>` element is dropped, so it reads as absent and fails). A probe on all five profiles' dvfilter control through `evaluateControlsUnreadable` gives pass 0, unreadable 1. The exception cannot mask an unreadable read.

**Devel evidence that settles dvfilter.** After a build 90 collect on devel, read `VCF-CF Compliance|esx.network-dvfilter|Actual` and `|Compliant` on each ESX host. **Actual `""` with Compliant 1** confirms ESX returns the key with an empty string through `QueryOptions(null)`, and the exception works. **Actual `(undefined)` with Compliant 0** means ESX omits the value, the exception never fires, and every hardened host fails this control. That would need an owner decision (a false fail, not a false pass). Build 89 data cannot tell the two apart, because both cases were skipped then. `esxcli system settings advanced list -o /Net/DVFilterBindIpAddress` or the vSphere Client Advanced System Settings view can corroborate, but neither is the adapter's read path. The pushed Actual is the decisive evidence.

**(c) W2.** See the table. Alert after 3 straight failures with a copy in force. Alert at once with no copy. 401/403 reads "refused (HTTP 4xx)".

**(d) N1.** See the table.

**(e) N5.** Mutation-proven, see the table.

**DEF-022 close wording vs the tests.** The fix commit and the CHANGELOG claim "ControlEvaluatorTest covers the absent-key path for every expected-value form (plain, or Undefined, Not Present, or Not Present, (non-empty), not:X), present-empty values, and the explicit-empty exception". This matches `ControlEvaluatorTest.absentAdvancedSetting` assertion for assertion, including "empty value against TRUE: fail", "present and empty against \"\" / NULL: pass", "a bound address against \"\": fail" and "absent against \"\": fail (undefined)". The override half of the proposed amendment matches `OverridesTest.overrideDropsOrUndefined`. One overstatement: `vmx-N or higher` is a valid Override form on a text advanced setting and is not in the six. It takes the same fail branch (`allowsUndefined` is false), so nothing is wrong, but "every form" means every form listed. "A failed read is unchanged" is covered by the existing suites (`Build77FaultTest`, the `evaluateControlsUnreadable` cases), not by the new tests. That is fine. I compared against the commit message and the CHANGELOG because the author's result block was not in my brief.

### New findings

#### BLOCKING

**B1. The landing README contradicts build 90's scoring (owner: `sdk-adapter-author`).** Authority: review dimension 11 (docs that contradict actual behavior are BLOCKING). `README.md:59-60` still says "(One known gap: a setting that is simply absent is currently skipped rather than failed; see Known issues.)". This build fails such settings, and the same commit removed the #15 entry from Known issues, so the pointer leads nowhere. An operator who sees new `(undefined)` failures and reads the landing page gets the opposite explanation. **Fix:** replace the parenthetical with the current rule (an unset setting fails unless the guide allows it to be unset, Actual `(undefined)`), or delete it.

#### WARNING

**W3. `vm.dvfilter` always passes: its wildcard parameter is looked up as a literal key (owner: `sdk-adapter-author`; registration candidate).** Authority: skill § *Unreadable is NOT compliant*; `knowledge/lessons/unreadable-is-not-compliant.md`; skill § *Gaps, name them, never hide them*; `knowledge/rules/no-fabricated-metrics.md`. In SCG 7.0, 8.0, 9.0 and 9.1, `vm.dvfilter` has parameter `ethernet*.filter*.name` and expected `Not Present`. `ControlEvaluator.java:136` does `advancedSettings.get(param)`, and no VMX key is literally `ethernet*.filter*.name`. So the value is always absent, `allowsUndefined("Not Present")` is true, and the control passes. Probe: a VM with `ethernet0.filter0.name = dvfilter-generic-vmware` scores pass 1 / fail 0 under all four profiles. The control cannot detect the condition it exists to detect, yet it reports a pass. It has been there since the root commit `c6d9e73`. Build 90 neither introduced it nor changed it (the DEF-022 fix leaves `Not Present` passing on absence). I graded it WARNING for that reason, following the DEF-022 precedent (build 86 W3), and propose registering it at blocking severity so the release gate holds it. **Fix:** match wildcard parameters as patterns: any key matching `ethernet\d+\.filter\d+\.name` present is a fail, with that key and value as Actual. Or, until a matcher exists, put `vm.dvfilter` in `profiles/manual_review.csv` as an honest gap. Add a test where a VM with a filter attachment fails.

#### NIT

**N6. An Override of `""`, `" "`, `NULL` or `null` turns on the explicit-empty pass for any text advanced setting.** `checkValue` passes these through `checkPlain` (`ComplianceOverrides.java:464`). Probe on `esx.log-level`: all four are accepted, a present empty value then passes, and an absent one fails. This is operator-explicit and marked "(site override)", so it is not a hidden widening and not an unreadable mask. But `null` in particular reads like a literal value. **Fix:** document in overrides.md that `""` / `NULL` mean "present and empty", or reject `NULL` / `null` in `checkValue`.

**N7. "no Suite API channel ... the alert fires" cannot happen.** With no channel, `stitcher` is null, so `pushOverridesStatus` pushes the status only to Compliance World. The vCenter metric the alert reads is never written (the same applies to an unmatched vCenter). The overrides.md status and reason tables together imply the alert fires. The snapshot flag is right; the delivery is impossible. The no-channel case is already flagged by "Ambient Suite API stitcher unavailable". **Fix:** one line in overrides.md: with no channel, the status appears on Compliance World only and the alert cannot fire.

**N8. Actual `(undefined)` on a failing control is not in data-reference's list of Actual values** (`docs/data-reference.md:82-94`). Before this build it appeared only on passes. Add a line.

### Registry check (`knowledge/context/defects.md`)

- **DEF-022: RESOLVED, propose close.** Fix: adapter commit `ed4236d`, `ControlEvaluator.java:150-191`, build 90 (pak sha256 `b59a3181...707f`). The close condition is met: a `ControlEvaluatorTest` case (`absentAdvancedSetting`) asserts an absent key with a value-required expected value is a fail, not a skip ("plain TRUE, unset: fail", "value-required controls fail when unset", "failing controls stay in the denominator"). It also asserts that `requiresAbsence` / non-empty / not-equal expectations do not depend on the skip ("Not Present, unset: pass", "(non-empty), unset: fail", "not:X, unset: fail"). The override path from the first pass is covered by `OverridesTest.overrideDropsOrUndefined`. Confirmed statically on this build. The close condition needs no live proof. A devel collect showing `vm.vmrc-lock` Compliant 0 with Actual `(undefined)` on a VM without the key would corroborate it. B1 is a stale README line about this defect. The orchestrator may close now or on the B1 re-review.
- **DEF-023: open, unchanged.** `ComplianceStitcher.java` and `ComplianceDecisions.resourcePageOutcome` are not touched by `ed4236d` or `a285ce9`. Closure still owes the devel paging proof, which this build's devel install can supply.

**Registration candidate:** W3 (`vm.dvfilter` wildcard false pass), proposed at blocking severity, `Affects: compliance`, first seen `c6d9e73`.

### If shipped as-is

Scores are now honest for unset advanced settings. But the landing README tells operators the opposite. `vm.dvfilter` keeps passing VMs that carry a dvfilter attachment, as it has in every build.
