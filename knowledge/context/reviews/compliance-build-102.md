# Review: compliance build 102

- **Date:** 2026-10-28 (America/Chicago)
- **Reviewer:** sdk-adapter-reviewer (static, pre-install; nothing installed, no live instance touched)
- **Adapter repo:** `content/sdk-adapters/compliance`, branch `build-102`, clean tree
- **Delta reviewed:** `17f75a6..44a0db4` = `1d8f588` (adapter, rollup, stitcher, tests, docs, CHANGELOG) + `44a0db4` (SCG view repoint, five dashboard comments)
- **Issues in scope:** #63, #20, #59, #64 (adapter repo). #58 is not in this build.
- **Reviewer's pak:** built from `44a0db4` into scratch, sha256 `7fc9d6bd29a8d595ad3e19fa7bdc7808e773885a641606ad2e5191025a099bb3`
- **Reference:** `dist/vcfcf_sdk_compliance.0.0.0.101.pak`, sha256 `c356ac0e…b8ff` (the pak the build 101 review confirmed)
- **Author's pak:** `dist/vcfcf_sdk_compliance.0.0.0.102.pak`, sha256 `160a764f…1bf7`, built 00:36, two minutes before `44a0db4` was committed. It does not contain the repointed view (0 occurrences of `scored_objects` in its views content.xml). See W2.

## Verdict: CHANGES REQUESTED (2 BLOCKING, 4 WARNING, 5 NIT)

## Independent verification

| Check | Result |
|---|---|
| `bash ci/run_java_tests.sh` (the CI test job, gates the tag build) | **FAILS.** All 26 Java test classes pass (including BcHandshakeTest); then `tests/test_build95_dashboards.py::test_scg_versions_newest_first` fails and `set -e` ends the run. See B1. |
| `python3 -m unittest discover -s tests` | 55 tests, 1 failure (the same test) |
| `Build96BudgetTest` repeat (#63) | 8 of 8 sequential runs pass; 12 of 12 run concurrently on 4 CPUs (3x oversubscribed) pass |
| `validate-sdk` | OK. Same pre-existing warnings as build 101 (two dashboard names over 50 chars; 8.18.7 and 9.1.1 SDK compat jars absent, so those checks are skipped; the 9.0 compat compile passes) |
| `build-sdk` | Builds 0.0.0.102 |
| `pak-compare` 102 vs 101 | PASS: 0 BLOCKING / 0 WARNING / 0 INFO, "No structural divergences found". Matches the expected result. |
| Pak-level diff 101 to 102 (nested zips walked) | Exactly 8 entries change: both `manifest.txt`, `conf/version.txt`, `overview.packed`, `vcfcf_compliance.jar`, the views `content.xml`, and the Objects by SCG Version report (`content.xml`, `content.properties`). describe.xml and all five dashboards are byte-identical to 101: the dashboard edits are YAML comments only. |
| Rendered SCG view | Columns 0-4 `Benchmark|SCG_{9.1,9.0,8.0,7.0,6.7}|scored_objects`, 5-6 `none|objects`, `unknown|objects`; summary row `attributeIndexes` 0-4 |

No SDK ADAPTER RESULT block came with the brief, so the only claims checked are the ones in the brief, the CHANGELOG and the commit messages.

## BLOCKING

### B1. The CI test job fails at `44a0db4`, so a `v*` tag cannot build

- **Where:** `tests/test_build95_dashboards.py:76-81` (unchanged) against `views/compliance-scg-versions.yaml:18-27` (changed in `44a0db4`).
- **Authority:** author hard rules 8-9 (build hygiene); `knowledge/rules/validate-before-install.md`; the repo's own CI (`ci/run_java_tests.sh` runs every `tests/test_*.py` and gates the tag build).
- **What:** the test still expects `VCF-CF Compliance|Rollup|Benchmark|<B>|objects` for all seven columns. `1d8f588` passes. The view repoint in `44a0db4` was committed without updating the test, so the build has never been green as committed.
- **Fix:** update `test_scg_versions_newest_first` to expect `scored_objects` for the five SCG columns and `objects` for `none` and `unknown`. Assert the summary `columns: [0, 1, 2, 3, 4]` as well, so the "totals = Rollup|All|scored" property is pinned by a test. Re-run `bash ci/run_java_tests.sh` to green.

### B2. The CHANGELOG says the view was not changed, but it was

- **Where:** `CHANGELOG.md:6`: "The Environment Overview's Objects by SCG view still reads `objects` until it is repointed."
- **Authority:** review dimension 11 (docs that contradict actual behavior are BLOCKING); author hard rule 9 (a matching CHANGELOG line).
- **What:** `44a0db4` repointed the view but did not touch the CHANGELOG. The release notes for 102 tell operators the opposite of what the pak does: the SCG columns on the Environment Overview and the World Summary now count scored objects only, and the totals row no longer sums No Benchmark and Unknown. Line 7 (#64) also names only the Environment Overview's W6 comments, but six dashboards changed. That part is incomplete rather than wrong (N1).
- **Fix:** replace the sentence with what shipped: the view's five SCG columns read `scored_objects` and are renamed "SCG x Scored Objects"; No Benchmark and Unknown still read `objects`; the totals row sums only the five SCG columns, so it equals `Rollup|All|scored`; an object with nothing read or nothing applicable no longer appears in any SCG column. Name the test from B1.

## WARNING

### W1. #20: if VCF Ops rows lack `VMEntityVCID`, the kind is zeroed instead of held back, and nobody has checked live

- **Where:** `ComplianceStitcher.java:323-347` (`loadResourcesForKind`), together with `ComplianceAdapter.java:2067-2085` (`kindPushable`).
- **Authority:** skill § *Unreadable is NOT compliant*; the build 88 hold-back rule (the `kindPushable` Javadoc: a list that cannot be used holds the kind back instead of reporting every object unmatched); doctrine skeptic default.
- **What:** before 102, a row with no `VMEntityVCID` was kept unscoped. Now it is counted and dropped. The fetch is still `COMPLETE`, so the kind is pushable. If a kind's rows lack `VMEntityVCID` (for example DVS, port group or cluster rows, which the factory has no recorded identifier set for), every object of that kind goes unmatched. Its `Rollup|<K>|scored`, `All` and `Benchmark` counts then drop to 0 with `Rollup|incomplete = 0`, and the evidence is one INFO line. That is the "zeroes existing data" shape the brief asked about. The owner-unknown case is held back, but the same uncertainty at row level zeroes. It is not a false pass: `unmatched` rises, and 0 scored reads as "nothing evaluated". Per-object values stay at their last push. The evidence that `VMEntityVCID` is always present covers VirtualMachine (`isPartOfUniqueness: true`, `knowledge/context/investigations/adapter_describe_exploration.md:99`), Datastore (recon_log) and, implicitly, HostSystem: builds 51 to 101 scoped on it across devel_9_1's three vCenters. Nothing in the repo shows it for VmwareDistributedVirtualSwitch, DistributedVirtualPortgroup or ClusterComputeResource.
- **Fix (either):** (a) owe a devel_9_1 proof before tagging: for all five kinds, no `row(s) not indexed` INFO line and each kind's `Rollup|<K>|unmatched` unchanged from build 101; or (b) hold the kind back (`failedLoads.add`) when the list had rows but none were indexable because of `noVcid`. (a) is enough if it comes back clean. **Registration candidate** if it ships unproven.

### W2. The `dist/` pak for 0.0.0.102 is stale and does not match the commit under review

- **Where:** `dist/vcfcf_sdk_compliance.0.0.0.102.pak`, mtime 00:36; `44a0db4` committed at 00:38.
- **Authority:** `knowledge/rules/validate-before-install.md`; author hard rule 8 (the build is the reviewed state).
- **What:** two different paks now carry 0.0.0.102. The one in `dist/` has the old `objects` view. A devel proof or install from `dist/` would not exercise #59's view fix, and the "Objects by SCG = Rollup scored" check would fail for a reason unrelated to the code.
- **Fix:** rebuild from the final commit before any devel install, and record the sha256 in the proof.

### W3. #64: the upgrade note states a cause nobody has recorded evidence for

- **Where:** `docs/installing.md:260-269`, `docs/data-reference.md:534-539`, `docs/overview.md:161-164`, and the six dashboard comments.
- **Authority:** `knowledge/rules/no-fabricated-metrics.md` (docs state what is proven); review dimension 11.
- **What:** the docs say, as fact, that a Score Degraded alert raised before build 57 keeps subType 20 and is hidden by the `15_21` filter. The last comment on issue #64 (2026-10-26) says the cause of the three missing Score Degraded alerts is "not yet checked" and names the widget's criticality filter `[2, 3, 4]` as the candidate. The only factory record of subType 20 is a recon line from before build 57 (`recon_log.md:3845`). Neither the issue nor `knowledge/context/` shows the three missing alerts with subType 20 and a start time before build 57.
- **Fix:** post the Suite API evidence on #64 (the three alerts' definition subType and start time, from `/api/alerts`) before shipping the note. If they turn out to be criticality-filtered instead, the note is wrong and must change. The comment text is inert in the pak (comments are not rendered), so only the docs carry the risk.

### W4. Factory PR #285: the amended lesson is still inconsistent with the build 102 code (factory-side, not this pak)

- **Where:** `knowledge/lessons/stitch-moid-not-unique-across-vcenters.md` as amended by PR #285.
- **Authority:** the brief's consistency check; `knowledge/context/authoring/guide_codification.md` (a lesson must match the shipped idiom).
- **What:** the amended "Hold back, never guess" bullet matches the code: an unknown owner holds the kind back with incomplete = 1, and a row with no VCID is skipped and counted. Three things in the same file still describe the old behaviour:
  1. The "Log the scope" bullet still promises a `unscoped — owning vCenter UUID unknown` load line. Build 102 removed it. The owner-unknown line is now the WARN "`<kind>` not loaded: the owning vCenter instance UUID is unknown … held back this cycle" (`ComplianceStitcher.java:291-296`).
  2. The section header still reads "The fix pattern (vcommunity build 2 — copy this)", and that code still degrades to unscoped. The vcommunity repos are archived, so the reference should move to compliance build 102.
  3. The lesson does not mention the duplicate-MOID rule (two rows of the owning vCenter with one MOID match neither) or the no-identifier rule (never push by name), and both are now part of the idiom.
- **Fix:** amend those three spots in PR #285 before it merges.

## NIT

- **N1.** `CHANGELOG.md:7` names only the Environment Overview's W6 comments; `44a0db4` also changed the AlertList comments in five more dashboards. Fold this into the B2 edit.
- **N2.** `ComplianceRollupTest.java:121-144`: the carry test covers `addPart` but not `Part.plus` (a kind cut in two consecutive cycles), and it never asserts `sum(scored_objects) == All|scored` after a carry. By construction it holds (see below), but a one-line assert after `addPart`, plus one `plus()` case, would pin it.
- **N3.** `ComplianceStitcher.java:280-283`: `loadResourcesForKind` still allocates and registers an always-empty `byName` map for the vim25 kinds. It is dead state now that `countOfKind` reads `byMoid` for them.
- **N4.** `docs/overview.md:327-328` lists the held-back keys as `Rollup|All|*` and `Rollup|Benchmark|*|objects`. `scored_objects` is held back too. `docs/data-reference.md` says so; overview does not.
- **N5.** `Build96BudgetTest.adapterBreakerEndsCycle` (`:851`) keeps the pattern #63 removed: a 150 ms read timeout that the calls vCenter does answer (listing, CurrentTime, CreateContainerView) must beat on a loaded runner. Out of #63's scope, but it is the next flake of the same kind.

## Hunt results (asked in the brief)

### Multi-vCenter regressions in the stitcher

- The scoping order is sound. A row is skipped as foreign before the UUID/MOID checks, so another vCenter's rows never count as "not indexed" and never take part in duplicate detection (`:323-338`). `owner` is read once into a local from the volatile field (`:286`), so a mid-load change cannot split a load.
- The duplicate rule is correct for 2 and for 3 or more rows: the first is put, the second removes it and marks the MOID ambiguous, and later rows are skipped (`:347-353`). A MOID duplicated across two *different* vCenters is not ambiguous, because only the owner's rows reach that check. This is right.
- Two VMWARE adapter instances on the same vCenter (both carrying the same MOID+VCID) now match neither and are counted unmatched. Before, the last writer won. The new behaviour is the safer one; the only trace is the INFO "matched to neither" line and `Rollup|<K>|unmatched`.
- All five call sites pass the vim25 MOID from the listing (`ComplianceAdapter.java:2149, 2503, 2779, 2826, 2881`), so removing the name fallback cannot strand a caller that relied on a null MOID.
- The VMwareAdapter Instance path is unchanged except that rows with no UUID are now counted (`:233-239`). `matchVCenter` still has no name or prefix path (build 58).
- The `HashMap` prefix walk (#20) is gone: `matchResource` is MOID-only (`:550-557`). No residual name, prefix or `singletonOfKind` match exists anywhere in `src/`.
- The only regression found is W1: rows with no `VMEntityVCID`.

### A held-back kind staying held back forever, or zeroing data

- **Owner unknown** (`:286-297`): the kind is added to `failedLoads` without a fetch, `kindPushable` holds it back, `Rollup|incomplete = 1` is pushed every cycle, the vCenter collection alert fires, and the stitcher WARN plus the adapter WARN name the cause. It is not silent. It is not sticky either: the next cycle with a known owner goes through `fetchResources`, which clears the mark on a complete list (`:402, 440`). The build 96 empty-list history (`lastCompleteCount`, `emptyHeldBack`) is not touched on the hold-back path, so it cannot be corrupted. `about.instanceUuid` is null only if the vCenter's ServiceContent has no `about.instanceUuid` (`VSphereClient.java:344-347`). A vCenter always has one, so a permanent hold-back would need a broken vCenter, and that state stays flagged as incomplete for as long as it lasts.
- **Zeroing:** the owner-unknown path keeps values. The row-level no-VCID path zeroes (W1).
- Objects that previously matched by name, and whose MOID no longer matches, now go unmatched and keep their last per-object values. That is the build 88 unmatched semantics, unchanged. CHANGELOG reports no recorded case where the name fallback was needed.

### Rollup counters double-counting across early-ended cycles (#59)

- **Equal to `Rollup|All|scored` by construction:** `bumpScored` has exactly one call site, directly after `t.scored++` in `recordEvaluated` (`ComplianceRollup.java:279-280`), with the same kind and the same bucket normalisation as `bump`. `part()`, `Part.plus()` and `addPart()` copy and merge `scoredBuckets` in lockstep with the tally (`:346-357, 378-388, 395-415`). So `sum_B scoredByBucket == sum_K t.scored == All.scored` at every point, including after a carry.
- **No double counting:** a carried share is the objects before the resume point, and the resuming cycle reads only the tail (`KindWalk.order`). A `DROP`ped object is not recorded and is re-read next cycle. A cut-twice object (`pushCutTwice`) records `totalCount = 0`, so it lands in `objects` only and is never scored. A walk that is not a resume clears the carry (`carry(kind, null)`). `scored_objects` therefore cannot double-count unless `scored` does too, and the two can never disagree.
- **Hold-back:** pushed only on a complete cycle, next to `objects` and `All` (`:458-469`). The test covers this.
- **`none`/`unknown` are always 0:** no-benchmark objects go through `recordNoBenchmark` and version-unreadable ones through `recordVersionUnreadable`; neither path reaches `recordEvaluated`. With the five bundled SCG profiles, every scored object lands in one of the five SCG columns, so the view's totals row equals `Rollup|All|scored`. A future non-SCG profile name (`bucketOf` returns the name itself) would break that equality silently. Today no such profile exists.
- **Trade-off (intended per the view description, worth knowing):** an object with nothing read (an all-unreadable host, a non-vSAN cluster) no longer appears in any column of Objects by SCG Version. Until a vCenter's first complete cycle on 102, its SCG cells are blank, because the new keys do not exist yet.

### #63

The hung host-relayed call now waits on a latch that is released after the cycle (bounded at 60 s), and the read timeouts went from 200 ms to 2 s, so answered calls are no longer racing the timeout. This is the latch approach #63 asked for. The test's wall time grows by one 2 s timeout. 20 of 20 runs passed, 12 of them under oversubscription. There is no production change (`git diff` touches only the test). I propose closing #63 once B1 is green.

## Review dimensions

1. **Cardinal correctness:** no new path turns a failed read into a pass. Unmatched objects are not scored. Owner-unknown holds back. W1 is a zeroing path, not a pass.
2. **vim25 reads:** no vim25 change.
3. **Exceptions:** no new catch. `fetchResources` still never throws. The adapter's UUID catch now holds back instead of degrading.
4. **Canonical loader:** not touched.
5. **Stitching identity:** stricter than before, and it matches the skill's identity rule (instanceUuid + MOID). No foreign `ResourceKey` is built in this delta, so the uniqueness-flag trap does not apply.
6. **Logging:** the per-row WARN for a missing identifier became one INFO line per load (less spam). No secrets: the INFO names the row's name, MOID, VCID and identifier only. Owner-unknown is a WARN per kind per cycle, which is acceptable for a state that also raises an alert.
7. **Memory:** one small `TreeSet` per load. Maps are replaced per load, not grown.
8. **API discipline:** owner-unknown saves five `/api/resources` reads. No N+1 is introduced.
9. **Build hygiene:** `build_number` is 102 and the docs stamps are 102. CI is red (B1), the CHANGELOG is stale (B2), and the `dist/` pak is stale (W2).
10. **Gap honesty:** n/a.
11. **Docs parity:** overview.md, data-reference.md and installing.md are updated for #20, #59 and #64. Problems: the CHANGELOG contradicts the code (B2), the #64 cause is unproven (W3), and N4.
12. **Registry:** see below.
13. **describe.xml import rules:** describe.xml is byte-identical to 101, and no alert, symptom or generator change is in this delta. Not re-parsed.

## Registry check (`knowledge/context/defects.md`; no `defects.local.md` present)

Open defects with `Affects: compliance`:

- **DEF-025** (retired-key -1 pushed once): still open and unchanged by 102. `RetiredKeyRepeats` (`Configured.java:39`, `ComplianceDecisions.java:621, 863`) is not touched. The devel evidence of a retired-control alert cancelling is still owed.
- **DEF-026** (no cycle deadline): still open and unchanged by 102. `CycleBudget.java:35` and `ResumeCursor` are not touched. #63 changes only the test of the hung-host path (`Build96BudgetTest`). The throttled or unreachable vCenter case (a cycle actually cut by the budget) is still not shown on devel.

No closure proposed. W1 is a registration candidate if build 102 ships without the devel proof.

## If shipped as-is

A `v*` tag fails in CI on the stale view test, so there is no release. A local `dist/` install would carry the old SCG view, and the release notes would contradict what the pak does.

---

# Round 2: re-review of the fix round (`4271808`)

- **Date:** 2026-10-28 (America/Chicago)
- **Delta reviewed:** `44a0db4..4271808` (one commit, 16 files). The only production source change is `ComplianceStitcher.java` (+34/-9). The rest is tests, docs, CHANGELOG, README and YAML comments in six dashboards.
- **Reviewer's pak:** built from `4271808` into scratch, sha256 `904b69a5…7f0d`. **Author's pak:** `dist/vcfcf_sdk_compliance.0.0.0.102.pak`, sha256 `949bd104…07c`, built 01:09, after the 01:08:59 commit. With nested zips walked, the two paks differ only in the `overview.packed` container bytes (10 bytes: zip timestamps). Its unpacked contents are identical.

## Verdict: APPROVE (0 BLOCKING, 1 WARNING, 5 NIT)

## Independent verification

| Check | Result |
|---|---|
| `bash ci/run_java_tests.sh` at `4271808` | **PASS**, exit 0, 50 s. All 26 Java test classes print "all assertions passed" (Build96StitcherTest with the new `noVcidHoldsBack` and `adapterHoldsBackNoVcid`, Build96BudgetTest, ComplianceRollupTest). BcHandshakeTest also passes. 55 Python tests OK, including `test_scg_versions_newest_first`. |
| `Build96BudgetTest` under load | 12 of 12 concurrent runs pass on 4 CPUs (3x oversubscribed). This covers the reworked `adapterBreakerEndsCycle`. |
| `validate-sdk` | OK. The same pre-existing warnings as round 1 (8.18.7 and 9.1.1 SDK compat jars absent, so those checks are skipped). |
| `build-sdk` | Builds 0.0.0.102. |
| `pak-compare` 102 vs 101 (`dist/…101.pak`, sha `c356ac0e…b8ff`) | PASS, 0 BLOCKING / 0 WARNING / 0 INFO, "No structural divergences found". This holds for both my build and `dist/`. |
| Pak-level diff 101 to 102 | The same 8 entries as round 1: manifests, version.txt, overview.packed, the jar, the views content.xml, and the Objects by SCG report. Dashboards and describe.xml are byte-identical to 101, so the dashboard edits in this round are YAML comments only. |

## Round 1 findings

| Finding | Status | Evidence |
|---|---|---|
| B1 CI red | **Resolved** | `tests/test_build95_dashboards.py:76-93` expects `scored_objects` for the five SCG columns and `objects` for none/unknown, and pins the summary `columns: [0..4]`. CI is green. |
| B2 CHANGELOG contradicts the view | **Resolved** | `CHANGELOG.md:6` now describes the repointed view, the renamed columns, the totals = `Rollup|All|scored` rule and the blank cells before the first complete cycle, and it names the test. |
| W1 no-VCID rows zero the kind | **Resolved in code** (option b). See the analysis below. The live check moves to R2-W1. |
| W2 stale `dist/` pak | **Resolved** | `dist/` 0.0.0.102 was built after `4271808`, and its content matches my build (see above). |
| W3 #64 cause unproven | **Resolved** | [#64 comment 6461812901](https://github.com/sentania-labs/vcf-content-factory-sdk-compliance/issues/64#issuecomment-6461812901) (2026-10-28) shows the evidence. The three missing alerts are the three oldest active ones and appear only under `15_20`, while a control host's alert appears under `15_21`. Replaying the widget across five criticality sets always gives 7, so the criticality filter is ruled out. The docs now cite the comment and say "seen" / "appears to" / "can" rather than claiming a mechanism. |
| W4 lesson (factory PR #285) | **Resolved**, merged | All three spots are fixed: the header reads "tightened in compliance build 102", the unscoped log line is marked as vcommunity-only with "copy compliance build 102", and the duplicate-MOID and no-identifier rules are added. One small gap remains (R2-N5). |
| N1 dashboard comments in CHANGELOG | Resolved | `CHANGELOG.md:7` names all six dashboards. |
| N2 `Part.plus` and sum asserts | Resolved | `ComplianceRollupTest` covers a carry through two cut cycles and asserts `sum(scored_objects) == All|scored` after `addPart` and after `plus`. |
| N3 dead `byName` map | Resolved | It is gone from `loadResourcesForKind`. `resourcesByName` is now used only by the VMwareAdapter Instance loader (`:217`) and `countOfKind` (`:745`). |
| N4 overview hold-back keys | Resolved | `docs/overview.md:335-336` now lists `scored_objects`. |
| N5 breaker test races a sleep | Resolved | The latch pattern is used, the timeout is 2 s, and the test asserts the held count is at least `BREAKER_TIMEOUTS` and below the calls of a full cycle, with a wall-time bound of (held+2) x timeout. Esxcli calls are answered at once (see item 2). It passed 12 of 12 times under load. |

## The W1 hold-back (`ComplianceStitcher.java:313-382`)

**The rule:** `noVcid > 0 && ownerRows == 0` leads to `failedLoads.add(kind)`, a WARN, and `return` before the INFO and load lines. `ownerRows` counts every row whose `VMEntityVCID` equals the owner UUID, including rows that are later skipped for having no UUID or no MOID (`:335-344`).

**Multi-vCenter false hold-back, the case asked about: none.**
- If every row belongs to other vCenters and carries a VCID, then `noVcid == 0`, so the load completes with 0 indexed and is not held back. That is the genuine 0. The last case of `noVcidHoldsBack` covers it for DVS, port group and cluster.
- A vCenter with no objects of a kind is never affected. `kindPushable` is consulted only after vSphere lists at least one object of the kind (`ComplianceAdapter.java:2121-2126, 2469-2474, 2760-2767, 2807-2814, 2862-2869` all return on an empty listing first). So the stitcher's `failedLoads` mark on a kind this vCenter does not have never reaches `markIncomplete`.
- A held-back mark does not stick. The next cycle's `fetchResources` adds the mark and clears it on `COMPLETE` (`:427, 465`) before the rule runs again. The rule does not touch the build 96 empty-list history.
- Through the adapter, the hold-back gives `Rollup|incomplete = 1`, and the Host, All and Benchmark keys are not pushed (`adapterHoldsBackNoVcid`). This is the same path as the owner-unknown and failed-list holds.

**Remaining edges (none of them a false pass):**
- **Stray no-VCID row with no owner rows (R2-N3).** One orphan row with no `VMEntityVCID` sits among other vCenters' rows, and this vCenter's objects are not in VCF Ops at all, for example because its VMWARE adapter is new or the kind is not collected yet. The kind is then held back with incomplete = 1, where the correct reading is "unmatched". This is conservative and loud, and both the stitcher WARN and the adapter WARN name the cause. It clears as soon as one owner row appears.
- **Mixed rows (R2-N4).** At least one owner row carries the VCID while other objects of this vCenter's same kind lack it. The rows without it are counted, the kind completes, and those objects go unmatched, so the kind's counts drop by their number. This is the one path that still zeroes, and only partly. The CHANGELOG states it as the deliberate trade-off ("a stray no-VCID row beside rows of this vCenter is still only counted"), and the INFO "not indexed" line plus `Rollup|<K>|unmatched` show it. A mixed VCID population within one vCenter's rows of one kind has no recorded mechanism, so I accept the trade-off.
- **VCID present but not equal to `about.instanceUuid`** (case or format) puts every row under "from other vCenters" with a genuine 0. This was already true before 102 for all five kinds (the `owningVcUuid.equals(vcUuid)` foreign skip at `17f75a6`, `:290`), and builds 51-101 matched hosts and VMs on it across three vCenters. The new load line suffix "`N of M row(s) carry VMEntityVCID`" with "`loaded 0 … skipped M`" makes it a one-grep check (R2-W1).

## Item 2: `EsxcliSoapClient` hard-coded 120 s read timeout (`EsxcliSoapClient.java:704-705`)

**Assessment: not a DEF-026 regression, and not a fix for this build. It is a follow-up (R2-N2).**

- **Production behaviour equals the client's.** `VSphereClient.READ_TIMEOUT_MS` is also 120000 (`VSphereClient.java:146`). `setReadTimeoutMs` / `setShortReadTimeoutMs` are test seams only (`:134-136, 177-179`; no production caller), so in a shipped pak the esxcli read timeout and the client's normal read timeout are the same number. The gap is that the esxcli value is a separate literal: the two can drift apart, and tests cannot shorten it.
- **It is inside DEF-026's bound.** `post()` calls `b.check()` before every request (`:688-689`), reports `timedOut()` on a `SocketTimeoutException` (`:742-744`) and `answered()` on a full answer (`:750`). So each esxcli call is refused once the budget or breaker is reached, and it counts toward the breaker. Build 86's per-host unreachable mark (`:466-471`) limits a hung host to one 120 s timeout per cycle, not one per command. `CycleBudget`'s documented worst case ("the budget plus one call (30 s connect plus 120 s read)", `CycleBudget.java:14-17`) already assumes 120 s. DEF-026's open half is a devel proof that a throttled or unreachable vCenter's cycle is actually cut by the budget. This literal neither closes nor widens that.
- **What it does cost.** (1) The hung-esxcli path cannot be latch-tested: `adapterBreakerEndsCycle` has to answer the executer and ExecuteSoap calls at once, so no test shows a hung host-relayed esxcli call ending inside the budget. That is the #63 hung-host class. (2) Many hung hosts whose esxcli calls interleave with answered vCenter calls never trip the breaker, so each one costs a full 120 s until the time budget runs out. That is bounded, but it is the slow path. (#17 is the SOAP call-amplification issue: related through cycle length, not the same defect.)
- **Why not in 102.** Plumbing the client's timeout into `EsxcliSoapClient` changes the production read path, and 102's production delta is otherwise the stitcher alone. It needs its own test (a held esxcli call cut by the budget) and its own review. Doing it in a fix round is the drive-by the minimal-diff rule (author hard rule 9) exists to stop.
- **Recommendation:** open an adapter issue: pass `VSphereClient`'s read timeout to `EsxcliSoapClient` at `:389` (`new EsxcliSoapClient(…)`), replace the literal, and add a hung-esxcli latch test asserting one timeout per host and an end within the budget. The orchestrator should add a one-line note to DEF-026 Progress so the devel proof that closes DEF-026 also covers a host whose esxcli calls hang. It is not a separate registration candidate.

## Round 2 findings

### WARNING

**R2-W1. Before tagging, the devel proof must show `VMEntityVCID` on all five kinds.**
- **Where:** `ComplianceStitcher.java:362-377`, with `kindPushable` (`ComplianceAdapter.java:2068-2085`).
- **Authority:** doctrine skeptic default; skill § *Unreadable is NOT compliant* (hold-backs must be the rare case, not the steady state).
- **What:** the fix turns round 1's silent zeroing into a loud hold-back, which is correct. But the repo still has no evidence that VmwareDistributedVirtualSwitch, DistributedVirtualPortgroup or ClusterComputeResource rows carry `VMEntityVCID`. Builds 51-101 kept no-VCID rows unscoped, so they never needed it. If one of those kinds lacks it, every cycle on 102 holds that kind back, and `markIncomplete` also holds back the cross-kind `Rollup|All|*`, `Benchmark|*|objects` and the new `scored_objects` keys. In that case the whole environment rollup stays frozen at its build 101 values, the Objects by SCG columns stay blank forever (the keys are never created), and the not-collected alert never clears. That is not a false pass, but it is a pak that never finishes collecting.
- **Fix (proof, not code):** on the devel 102 install, after one cycle, every account's five `ComplianceStitcher: loaded … by MOID` lines should show `M of M row(s) carry VMEntityVCID` (or at least one owner row), no `not matched: … carry no VMEntityVCID` WARN, and `Rollup|incomplete = 0`. **Registration candidate** if 102 is tagged without this.

### NIT

- **R2-N1.** `docs/overrides.md:55` and `docs/installing.md:238` (the brief's `:234`, shifted by this round's edit at `:198-203`) still give only `Administration > Integrations > Accounts`, the 9.0.2 / 8.18.7 path. On 9.1.1 it is `Operate` tab > Administration > Integrations, as the README and `installing.md:198-203` now say. Point both lines at the paths in Step-by-Step Installation, or spell out both.
- **R2-N2.** `EsxcliSoapClient.java:705`: the hard-coded 120 s read timeout. Assessment and the recommended follow-up issue are above. Not for this build.
- **R2-N3.** False hold-back on a stray no-VCID row when this vCenter has no rows of the kind in VCF Ops (see above). Conservative and named in the WARN. No change asked; noted so the case is not misread in the field.
- **R2-N4.** Mixed rows still zero partly (see above). The CHANGELOG documents it as an accepted trade-off. No change asked.
- **R2-N5 (factory-side).** The merged lesson `knowledge/lessons/stitch-moid-not-unique-across-vcenters.md` "Hold back, never guess" bullet says to skip and count a no-VCID row, but not the `4271808` refinement (hold back when no row belongs to the owner and some have no VCID). It also still points at `content/sdk-adapters/vcommunity/…`, which `80f8f77` moved out of `content/sdk-adapters`. One-line amendment on the next lesson touch.

## Review dimensions (round 2 delta)

1. **Cardinal:** no new pass path. The change replaces a zeroing path with a hold-back.
2. **vim25:** not touched.
3. **Exceptions:** no new catch.
4. **Loader:** not touched.
5. **Stitching identity:** unchanged: MOID + owner UUID only. No foreign `ResourceKey` is built.
6. **Logging:** one WARN per kind per held cycle, naming the counts and the first row (name, MOID, VCID, identifier; no secrets). The load line gains the VCID count. No per-row spam.
7. **Memory:** one map less per vim25 kind (N3).
8. **API:** no new calls; the hold-back returns after the single paged fetch.
9. **Build hygiene:** `build_number: 102`; the CHANGELOG matches; CI is green; `dist/` matches the commit. The breaker test fix and the docs are within the round's scope.
10. **Gap honesty:** the CHANGELOG states where VCID evidence exists and where it does not.
11. **Docs parity:** the CHANGELOG, overview, data-reference, installing and README match the code and the #64 evidence. Two stale menu paths remain (R2-N1).
12. **Registry:** see below.
13. **describe.xml:** byte-identical to 101, and no alert, symptom or generator change. Not re-parsed.

## Registry check, round 2 (`knowledge/context/defects.md`; no `defects.local.md`)

- **DEF-025** (retired-key -1 pushed once): **open, unchanged**. `RetiredKeyRepeats` (`Configured.java:39`) is not touched by `4271808`. The devel evidence is still owed.
- **DEF-026** (no cycle deadline): **open, unchanged**. `CycleBudget.java:35` is not touched, and the round 2 production delta is the stitcher alone. The throttled or unreachable vCenter devel proof is still owed. Add the `EsxcliSoapClient` 120 s literal (R2-N2) as a Progress note; it does not widen the defect.

No closure proposed. Registration candidate: R2-W1, if 102 is tagged without the VCID evidence for all five kinds.

## If shipped as-is

On any environment where the switch, port group and cluster rows carry `VMEntityVCID` (unproven, R2-W1), operators get correct per-vCenter stitching, SCG columns that sum to scored objects, and an honest #64 upgrade note. If one of those kinds lacks it, the environment rollup freezes at its build 101 values and the not-collected alert never clears. That outcome is loud, not a false pass.
