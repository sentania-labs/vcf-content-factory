# Review: compliance build 103

- **Date:** 2026-10-28 (America/Chicago)
- **Reviewer:** sdk-adapter-reviewer (static, pre-install; nothing installed, no live instance touched)
- **Adapter repo:** `content/sdk-adapters/compliance`, branch `build-103`, clean tree, one commit `73ad393` on `origin/main` `d585a9b` (build 102)
- **Issue in scope:** adapter #17 (SOAP call amplification), build 2: bulk `RetrieveProperties` primary, esxcli read timeout from the client (folded from the build 102 review, R2-N2), RuntimeException disconnect. The second #17 box (one Suite API push per object) is a framework TOOLSET GAP and is not in this build.
- **Reviewer's pak:** built from `73ad393` into scratch, sha256 `b6107e47…9b62`. **Author's pak:** `dist/vcfcf_sdk_compliance.0.0.0.103.pak`, sha256 `fc2de0d5…ddad8`. With nested zips walked, the two differ only in container bytes (jar, views.zip, adapters.zip, overview.packed). 0 class files and 0 content entries differ.
- **Reference:** `dist/vcfcf_sdk_compliance.0.0.0.102.pak`, sha256 `949bd104…07c` (the pak the build 102 round 2 review confirmed).

## Verdict: APPROVE (0 BLOCKING, 4 WARNING, 5 NIT)

## Independent verification

| Check | Result |
|---|---|
| `bash ci/run_java_tests.sh` at `73ad393` | **PASS**, exit 0, 40 s. 27 Java test classes print "all assertions passed" (the 26 from build 102 plus `Build103BulkPrimaryTest`); BcHandshakeTest passes; Python tests OK. |
| Timing-sensitive tests under load | `Build103BulkPrimaryTest` (held esxcli latch) and `Build96BudgetTest`, 6 of each run concurrently on 4 CPUs (3x oversubscribed): 12 of 12 pass. |
| Mutation check of the timeout claim | On a scratch copy with `EsxcliSoapClient` set back to a fixed `setReadTimeout(120000)`, `Build103BulkPrimaryTest` fails: "cut at the client's 300 ms, not 120 s or the 60 s latch (60004 ms)". The tests do tell the fix apart from the old code. |
| `validate-sdk` | OK. The same environment warnings as build 102: two dashboard names over 50 characters; the 8.18.7 and 9.1.1 SDK compat jars are not in `adapter_runtime/`, so those legs were skipped locally (CI sets `--require-sdk-compat`). The 9.0 leg compiles. |
| Bytecode | `ComplianceAdapter$BulkPager.class` is major 55 (Java 11), so the 8.18 collector can load it (RULE-019). The new code uses only Java 8 APIs. |
| `build-sdk` | Builds 0.0.0.103. |
| `pak-compare` 103 vs 102 | PASS, 0 BLOCKING / 0 WARNING / 0 INFO, "No structural divergences found", for both my pak and the author's `dist/` pak. |
| Pak-level diff 102 to 103 | Changed: both `manifest.txt`, `conf/version.txt`, `overview.packed` (both overview.html), `vcfcf_compliance.jar` (the adapter classes in the delta), `views.zip` (container only), and **`lib/vcfcf-adapter-base.jar`, framework 1.0.19 to 1.0.22** (11 framework classes, see W4). describe.xml and all dashboards are byte-identical to 102. |
| Evidence harness | `DevelBulkEquivalence.java` (scratchpad, local only) read in full. It is read-only, takes credentials from the environment, never writes them, and disconnects in `finally`. It runs the null-row (build 102) path, then two bulk-first passes, and compares every control outcome plus version, connection state, advanced-map size and hash, and vSAN state. It reimplements the paging (`i % page`) rather than calling `BulkPager`. Its output was not kept anywhere (W2). |

No `SDK ADAPTER RESULT` block came with the brief. The claims checked are the ones in the brief, the CHANGELOG and the commit message.

## Hunt results (asked in the brief)

### A missing bulk value scoring as pass: none found

Every bulk read has a per-object fallback with the same reader, and no bulk-only path can produce a pass.

- **vim_property** (`VSphereClient.java:982-1040`): the row is tried first, and a null from it (absent, faulted, dropped path, missing element, or a reader exception) falls through to the unchanged per-object `SoapSource` read. The value or UNREADABLE that results, and its reason, are build 102's. `readFailure`/`lastFault` are reset after the bulk attempt, so a bulk reason never leaks onto a per-object result. esxcli never reads from the row (`readByRecipe` returns null for a `BulkRow`, and the caller only consults the row for `vim_property`).
- **The style readers are symmetric** (`VSphereClient.java:1206-1450`). `BulkRow.exact/longest` only return elements vCenter actually sent, within the same `prefixLengths` the per-object reader uses. The two list styles that can return TRUE (`list_empty`, `vm_hardware_device_absent`) require a non-null container (`readListConfirmed`). A row that lacks the container gives `ListRead.failed()`, which is null, which means a per-object read. A row can never hold a prefix the per-object reader would not have fetched itself: `bulkPaths` asks for exactly the per-object reader's first prefix, and `shortenBulkPath` respects `minPrefixSegments`.
- **Host advanced settings** (`ComplianceAdapter.java:2373-2406`): `advancedOf(row)` is null unless `config.option` is in the row, and a null goes to the unchanged per-object `getAdvancedSettings`, with the build 48 flap and build 77 failure handling intact. **The swap of source from QueryOptions to `config.option` cannot create a false pass with today's data.** I checked all five canonical CSVs: 0 of the 12 / 29 / 32 / 35 / 38 HostSystem `advanced_setting` rows (SCG 6.7 / 7.0 / 8.0 / 9.0 / 9.1) has an expected value that allows absence ("or Undefined", "Not Present"). A key that `config.option` leaves out therefore scores "(undefined)" FAIL, not a pass. The evidence scope is W1.
- **VM advanced settings:** the same property (`config.extraConfig`) is parsed both ways by the one shared `VimOptions.fromOptionList`. A VM whose row lacks it is read per object, and a failed read is UNREADABLE (the v3 fix at `:2709-2721` is unchanged). This matters because VMs do have "or Undefined" controls.
- **Version, connection state, vSAN probe:** each comes from the row only when present, otherwise per object. `vsanOf` calls the same `VsanGate.vsanEnabled` on the same `<val>` element as `hasVsanConfig`. A row without `configurationEx` means a per-object probe, never "not vSAN".
- **Whole-page failure** (`ComplianceAdapter.java:897-920`): any exception from `retrieveObjects` (a fault, the response cap, a deleted object, a parse error) empties the page, and the page's objects are then read per object. Never an empty result scored as data.
- **The test pins it:** `bulkEqualsPerObject` asserts that a fixture cycle scored from bulk pages pushes exactly what a cycle with every page failed pushes. `missingBothWaysIsUnreadable` asserts that a value absent both ways is not pushed and is flagged.

### Resume, budget and hold-back: no regression found (test gap W3)

- A page is fetched inside the first object of the page that the walk reaches, after `walk.next` has recorded `refusalsAtStart`. A budget refusal on the page call increments `CycleBudget.refusals()` in `post()`'s `b.check()` (`CycleBudget.Exhausted` is an IOException, rethrown unwrapped). `BulkPager.load` catches it as `refusedPages`, and the object's per-object reads are refused in turn, so `afterRead` returns DROP (or PUSH_THEN_STOP the second time). That is the build 96 semantics: no partial score, and the next cycle starts at that object, with a page that starts there.
- `walk.order` runs before `bulkOrder` is built, so the pages follow the resumed order.
- Hold-back: `bulkOrder` is empty when the Host or VM kind is not pushable. The vDS, port group and cluster walks still return before the pager when the kind is not pushable. `kindPushable` is unchanged.
- No test drives the refused-page branch itself (W3).

### Page boundaries; an object in two pages or in none: correct

- `load(at)` takes `order[at, at+pageSize)`, starting from the object the walk asked for. The walk iterates the same list `bulkOrder` was built from and only moves forward. An object already in `pageMoids` never triggers a fetch, so pages never overlap and no object is fetched twice.
- An object skipped before `bulk.row` (no benchmark, version unreadable) only wastes a slot in the page.
- An object in a failed or refused page is not fetched again for the rest of the cycle: `pageMoids` still holds it, so it is read per object.
- An object vCenter did not return is counted in `perObject` and read per object.
- Duplicate MOIDs in one listing (which vCenter does not produce) map to their first index (`putIfAbsent`).
- The fixture (12 hosts, 60 VMs) runs two host pages and two VM pages per cycle with pushes identical to per-object.

### Mixed benchmarks per kind: correct

`BenchmarkSelector.profilesFor` gives the pin, or every Auto profile, and `primaryPaths` asks for the union. An object's actual slice is always a subset. A profile outside that set (for example last-benchmark memory after an override change) finds nothing in the row, and its controls fall back per control. Paths that vCenter rejects (for example a 6.7 path on a 9.x vCenter) are shortened or dropped once and remembered. Only controls of the object's own profile ever read them, so an older profile's invalid paths cost nothing for objects scored on a newer one.

### Multi-vCenter: no new exposure

- `VSphereClient` is constructed per adapter instance (`ComplianceAdapter.java:187`).
- `acceptedPaths` and `bulkFallbackReads` are instance fields. No new static mutable state exists (`HOST_BASE_PATHS` and `CLUSTER_PROBE_PATH` are immutable).
- Pages are keyed by MOID inside one vCenter's session.
- `bulkOrder` uses the same `matchHost/matchVm/matchDvs/matchDvpg/matchCluster` (MOID plus owner UUID, build 102) as the walk. No foreign `ResourceKey` is built.

### Dev-preview double read leaking into a release: no leak

`ShadowMode.decide` is unchanged: on only for a `0.0.0.N` stamp in `conf/version.txt`; a missing, unreadable or incomplete file is off. When it is off, `ShadowComparator.record` returns at once (`!enabled`), `controls` and `names` stay empty, `hasRecords()` is false, and `runShadow` returns before any re-read. `evaluatePerObject` has no other caller. In a dev preview the re-read costs about build 102's per-object calls. They are scoped to `Phase.SHADOW`, checked against the budget per object, and skipped once the budget is used up (N4 covers two dev-only edges).

### RuntimeException disconnect and esxcli timeout: correct

- `conn` is assigned before the `try` in both `VSphereClient.postOnce` and `EsxcliSoapClient.post`, so the new `catch (RuntimeException)` cannot NPE. The budget refusal is an IOException thrown in `post()` before any connection, so it never reaches this catch.
- The esxcli client gets `readTimeoutMs` on every login (`:395`) and on the test seam. The production value is 120 s, unchanged.

## WARNING

### W1. The `config.option` = QueryOptions equivalence is proven on one lab, and the docs state it as a general fact

- **Where:** `CANONICAL_SCHEMA.md:248` ("(the same list)"); `docs/overview.md:409-411`; behaviour at `ComplianceAdapter.java:2373-2380`.
- **Authority:** doctrine skeptic default; `knowledge/rules/no-fabricated-metrics.md` (docs state what is proven); review dimension 11.
- **What:** host advanced settings now come from vCenter's cached `HostConfigInfo.option`, no longer from a live `QueryOptions` call to the host's OptionManager. The proof is 10 hosts behind three vCenters of one lab (vCenter 9.1.1), plus the build 95 shadow on 6 of the same hosts. The ESXi versions and the account's role were not recorded. The pak scores ESXi 6.7 to 9.1 and documents a Read-only role (`docs/installing.md:40`). As shown above, a gap here produces false FAILs ("(undefined)"), not false passes, because no host `advanced_setting` row allows absence. That is why this is a WARNING. But a host that `config.option` under-reports would read as non-compliant on controls it actually meets.
- **Fix:** record the ESXi build of each compared host and the role of the account used. Word the two doc lines as what was compared ("matched QueryOptions on the 10 devel hosts, ESXi x.y, <role>"). If an ESXi 7.x/8.x host or a Read-only-role account is available, re-run the harness against it before tagging. The dev-preview shadow still compares the two per cycle on devel, so a gap there would show up as `Bulk shadow disagreement:` lines.

### W2. The only evidence for switching the scoring path lives in a scratch directory

- **Where:** `CHANGELOG.md:5` (3,380 outcomes, 0 disagreements; the call counts); `docs/overview.md:421-423, 509-512`; the harness at the session scratchpad `…/scratchpad/harness/com/vcfcf/adapters/compliance/DevelBulkEquivalence.java` (local only, not reproducible).
- **Authority:** `knowledge/rules/cited-artifacts-reproducible.md` (RULE-015); CLAUDE.md "Reviewability matters"; doctrine independent verification.
- **What:** the harness source and its per-vCenter output (the DISAGREE lines, the per-kind fallback counts, the ESXi versions for W1) are not in either repo and not on issue #17. Issue #17 has no comment after 2026-10-28's fold-in note. The build 95 evidence went into `knowledge/context/investigations/`; this build's did not. The next reviewer, or an operator asking why scoring changed source, cannot see it.
- **Fix:** before tagging, post the harness output (the per-vCenter summary blocks) as a comment on #17, or add a factory investigation file. Commit the harness as a test-tree tool, or summarize it in full in that file.

### W3. No test drives a budget refusal on a page fetch

- **Where:** `ComplianceAdapter.java:905-908` (`catch (CycleBudget.Exhausted e) { refusedPages++; }`); `tests/…/Build96BudgetTest.java` (`adapterBudgetEndsCycle`, `twoCyclesVisitEverything` and the third budget case now charge their cost on each host's esxcli executer lookup).
- **Authority:** author hard rule 9 (prove behaviour preservation when generalizing); the brief's resume/budget hunt; skill § *Unreadable is NOT compliant* (a cut object carries no partial score).
- **What:** the existing budget tests were moved off the calls the bulk page now carries, so they still cut, but only on esxcli. The new branch, where a page's own `RetrieveProperties` is refused, the first object of that page is dropped, and the next cycle resumes at it with a fresh page, is correct by reading (see the hunt above) but is never executed by a test. This is the path a busy 5,000-VM vCenter will take.
- **Fix:** one `AdapterHarness` test with the 12-host fixture. Advance the clock past the budget on the second host page's `RetrieveProperties` (the call whose objectSet starts at the 11th host). Assert that host 11 is not pushed, that `Rollup|incomplete` = 1 and the summary shows `1 refused by the cycle budget`, and that the next cycle starts at host 11 with a page that starts there, and that two cycles together push all 12.

### W4. The dev preview ships framework 1.0.22; a release tagged today would ship 1.0.20

- **Where:** `lib/vcfcf-adapter-base.jar` in the built pak (`Implementation-Version: 1.0.22`, `X-Vcfcf-Source-Commit: fd5bc21`; build 102 carried 1.0.19); `.github/workflows/build-pak-on-tag.yml:53` `BUILDKIT_TAG: sdk-buildkit-v1`; `CHANGELOG.md:8`.
- **Authority:** `knowledge/rules/validate-before-install.md` (RULE-005, the proven artifact is the one that ships); author hard rule 8.
- **What:** `gh release list` confirms `sdk-buildkit-v1 (→ v1.0.20)` and no 1.0.21 to 1.0.23 kit is published. A devel proof of 0.0.0.103 runs eleven changed framework classes (`VcfCfAdapter`, `SuiteApiStitcher`, `AmbientCredential`, and others) that a `v1.0.0.103` tag would not contain. The CHANGELOG lists a `fix(framework)` (compliance#58) that such a release does not carry. The line says so plainly, so this is not a docs contradiction. It is a tested-versus-shipped gap.
- **Fix:** publish a 1.0.22 or later kit and move `v1` before tagging 103, or pin `BUILDKIT_TAG` to the kit actually proven. Otherwise, mark the line "not in a release built before `v1` moves".

## NIT

- **N1.** `VimOptions.java:108-131`: the new `fromOptionList` Javadoc went in between `missingSetFault`'s Javadoc and its method. `fromOptionList` now has two doc blocks (the first describes `missingSetFault`), and `missingSetFault` has none. Move the first block back down.
- **N2.** `VSphereClient.java:2251`: `retrieveObjects` resets `st.pathFixes = 0` on every page, so `BulkPager.logSummary` reports "vCenter rejected N this cycle" for the last page only. On a first cycle where page 1 paid the fixes it shows 0. Accumulate it per kind instead.
- **N3.** Dead production code kept in the jar: `retrieveBulk` (the CHANGELOG acknowledges it), but also `evaluateBulkRow` (`:2433`, edited in this diff although nothing in `src/` calls it) and the four-argument `ShadowComparator.summary` (`:206`). Fold all three into the announced cleanup.
- **N4.** Dev preview only, `ComplianceAdapter.java:2558-2590`. (a) When the budget runs out partway through an object's per-object re-read, `evaluatePerObject` folds the refused reads to UNREADABLE, and the comparator logs them as `Bulk shadow disagreement:` lines before the next iteration's budget check breaks. Those are false disagreements on the channel that is the equivalence evidence. Check `budgetExhausted()` after the re-read and skip the compare when it flipped. (b) The `catch (Exception)` around the loop is gone, so the Javadoc's "never fails the cycle" now depends on every callee catching. Today they do.
- **N5.** `BulkPager.load` tries every page again after a failure. A kind whose pages always exceed the 64 MB cap (for example VMs with very large `guestinfo` in extraConfig) downloads up to 64 MB per page, every cycle, before each per-object fallback. The cost is bounded and there is no correctness impact. Consider halving the page size for the rest of the kind after a `ResponseTooLarge`, and logging the largest page size from devel so the 10/50/100 sizes are grounded.

## Review dimensions

1. **Cardinal correctness:** no path from a missing bulk value to a pass (see the hunt). The zero-divisor contract is unchanged. The evaluable set is not widened.
2. **vim25 reads:** DOM walks only, no casts. Every new accessor (`textOf`, `hostVersionOf`, `advancedOf`, `vsanOf`) is null-safe and static. Reader exceptions on the row are caught per control, and page exceptions per page.
3. **Exceptions:** page failures are caught per page, with one WARN per kind that names the count and the cause, and the rest go into the summary. No empty catch hides a pass: the bulk `catch (Exception e) { value = null; }` falls through to the per-object read. Two shadow-only edges are noted in N4.
4. **Canonical loader:** not touched.
5. **Stitching identity:** the build 102 matching is reused for `bulkOrder`. No foreign `ResourceKey`.
6. **Logging:** one INFO line per kind per cycle, one WARN per kind on a failed page, and per-page detail at DEBUG. No per-object spam. Only vCenter fault text is logged, never credentials.
7. **Memory:** one page DOM is held at a time and released when the next loads. The per-call 64 MB cap is unchanged. Per-kind index maps are O(n) MOIDs. The `acceptedPaths` keys are bounded by the distinct path sets.
8. **API discipline:** this is the #17 fix itself. The fixture pins 36 calls per cycle (was 572). The devel figures are in W2.
9. **Build hygiene:** `build_number: 103`, CHANGELOG lines for all three changes, and docs stamps at 103. CI is green and `dist/` matches the commit. The refactors (`postFixingPaths`, `bulkRowOf`, `fromOptionList`) are extractions shared by the new path and the old one, not drive-bys. Equivalence is shown by `bulkEqualsPerObject` and the devel harness (W2, W3).
10. **Gap honesty:** the one-push-per-object box is named as a framework TOOLSET GAP and left out. Nothing is faked.
11. **Docs parity:** overview.md (bulk read, shadow reversed, esxcli timeout, hung-host wording) and CANONICAL_SCHEMA match the code. No relationship or user-visible kind changed, so README and the inventory tree only need the version stamp. W1 covers the "same list" wording.
12. **Registry:** see below.
13. **describe.xml import rules:** describe.xml is byte-identical to 102, with no alert, symptom or generator change. Not re-parsed.

## Registry check (`knowledge/context/defects.md`; no `defects.local.md`)

Open defects with `Affects: compliance` (DEF-004 and DEF-019 are open but affect vcommunity-os and factory:extractor):

- **DEF-025** (a retired key's -1 is pushed once): **open, unchanged.** `RetiredKeyRepeats` (`Configured.java:39`) and `ComplianceDecisions.java` are not in the delta. The devel evidence of a retired-control alert cancelling is still owed.
- **DEF-026** (no cycle deadline): **open.** This build closes the build 102 R2-N2 gap: esxcli calls now take the client's read timeout (`VSphereClient.java:395`, `EsxcliSoapClient.java:734`), and `heldEsxcliCutByBudget` shows a held esxcli call cut at the client timeout with the cycle ending inside the budget. The mutation check confirms the tests fail against the old literal. `CycleBudget.java:35` is not touched. The close condition's devel half (a throttled or unreachable vCenter cycle actually cut by the budget) is still not shown. **Progress note proposed for the orchestrator:** "build 103 (compliance 73ad393): esxcli read timeout follows the client; hung-esxcli latch test added". No closure.

Registration candidates: none, provided W1 and W2 are handled before the tag. If 103 is tagged without them, W1 (host advanced settings from `config.option`, unproven beyond one lab) is a candidate.

## If shipped as-is

Operators get the same scores from about a tenth of the vCenter calls (devel: 518-711 down to 34-62 per cycle). Any read the bulk call misses falls back to the build 102 read, so nothing new can pass. The exposures are a possible false FAIL on host advanced settings for an ESXi version or role nobody compared (W1), and a release cut before `sdk-buildkit-v1` moves that silently lacks the 1.0.22 framework the dev preview was proven on (W4).
