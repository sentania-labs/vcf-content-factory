# SDK adapter review: compliance build 82

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-02 (local, America/Chicago)
- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/environment-computed-metrics`, base `main` at `0a7d539`, uncommitted diff)
- **Artifact reviewed:** `dist/vcfcf_sdk_compliance.0.0.0.82.pak` (sha256 `d8e2f35d...6183358588`, built 09:24 CDT), reference `dist/vcfcf_sdk_compliance.0.0.0.79.pak` (the build on devel)
- **Framework dependency:** uncommitted factory diff in `src/vcfcf_managementpacks/adapter_framework/.../stitch/` (`addChild`, `addChildren`, `findSingletonResourceId`), reviewed separately in `knowledge/context/reviews/framework/adapter-framework-stitch-relationship-add-2026-10-02.md`
- **Verdict:** APPROVE (0 BLOCKING / 3 WARNING / 4 NIT)

## Bottom line

The new code cannot link the wrong object, cannot throw into the collect cycle, and runs strictly after the per-vCenter rollup push, so it cannot cost the rollup anything. The ComputedMetric keys match the declared `Rollup > Environment` nesting and the exact keys `ComplianceRollup.toStats` pushes. `avg_score` on 0/0 can produce no data or at worst 0 (a false alarm), never a pass. The weak spots: the world-id cache is only invalidated if a POST to a deleted parent fails synchronously, which the platform does not promise (W2); the docs say the world "carries only" `last_scan_timestamp` and never mention the new relationship (W1); and a `v*` tag today would fail CI because the published buildkit lacks `addChild` (W3). None of those makes the devel test misleading if the devel checklist below is followed.

## Independent verification

| Check | Result |
|---|---|
| `validate-sdk content/sdk-adapters/compliance` | OK (javac 19 files, one pre-existing `-source 11` options warning) |
| `ci/run_java_tests.sh` | all 10 Java suites pass (incl. `ComplianceDecisionsTest`), alert generator 14 tests OK, dashboard alert lists 3 tests OK |
| `build-sdk` into scratchpad | builds `vcfcf_sdk_compliance.0.0.0.82.pak`; vs the author's pak: `describe.xml` identical to source, adapter jar contents identical class for class, views identical, `vcfcf-adapter-base.jar` byte-identical (and byte-identical to `adapter_runtime/vcfcf-adapter-base.jar`, built 09:19 CDT). Only zip timestamps differ. Adapter repo working tree unchanged by the build. |
| `pak-compare` 82 vs 79 (author's and mine) | gate PASS, 0 BLOCKING / 0 WARNING / 0 INFO. Note: pak-compare reported no divergence at all for the new `ComputedMetrics` block and new attributes, so it is not evidence for them; verified directly below. |
| Built pak `describe.xml` | carries `Rollup` (30) > `Environment` (31) with `scored` / `non_compliant` / `no_benchmark` / `avg_score` (32 to 35) and the four-entry `<ComputedMetrics>` block |
| Built pak framework jar | `javap` on `SuiteApiStitcher`: `addChild(String,String)`, `addChildren(String,Collection)`, `findSingletonResourceId(String,String)`; `SuiteApiStitchClient.class` contains the partial-page guard (framework review W1 fix is in this jar) |
| Adapter bytecode | `ComplianceAdapter` references `ComplianceDecisions.linkWorld`, `SuiteApiStitcher.findSingletonResourceId`, and a method handle to `SuiteApiStitcher.addChild` |
| XSD | `tmp/describeSchema.xsd` (has `ComputedMetrics` in the `ResourceKind` choice and `ComputedMetricsType`; provenance not confirmed beyond matching the recon description). `main` describe: 9 errors, build 82 describe: the same 9 errors, all the pre-existing `enum@displayOrder`. Zero new errors from the added group or `ComputedMetrics`. The vcommunity copy of the XSD does not load in lxml (malformed at line 788), not used. |
| nameKeys | 30 to 35 new, no duplicate keys in `resources.properties`, no duplicate nameKey in `describe.xml`, every describe nameKey resolves |
| `defect-gate --pak compliance` | "no open blocking defects affecting compliance" |

## The brief's questions, answered from the code

**Wrong vCenter or wrong parent?** No.
- Child is `vcEntry.resourceId`, the same entry `pushRollup` uses, resolved by `ComplianceDecisions.matchVCenter` (`VMEntityVCID` instance UUID first with no hostname fallback when the UUID is known, else exact or case-insensitive `VCURL`). Same identity as the rollup push since build 51 (`knowledge/lessons/stitch-moid-not-unique-across-vcenters.md`), so the link cannot be wrong where the rollup is right.
- Parent comes from `findSingletonResourceId("vcfcf_compliance", "ComplianceWorld")`: exact, case-sensitive match on both kind keys, UUID-only ids, `null` on zero, more than one, or a partial page. Kind strings match `describe.xml` (`ResourceKind key="ComplianceWorld"`, adapter kind `vcfcf_compliance`). The world identifier (`world_id=compliance_world`) has been constant since the repo extraction.
- Argument order: `BiPredicate.test(worldId, vcResourceId)` bound to `sas::addChild(parent, child)`. Parent world, child vCenter. The test asserts `"w-1>vc-a"`.
- No foreign `ResourceKey` is built (Suite API UUIDs only), so the uniqueness-flag trap (`knowledge/lessons/cross-mp-foreign-key-uniqueness-flags.md`) does not apply.

**Can any new path throw into or abort the cycle, or the rollup push?** No.
- `linkVCenterToWorld` runs after `pushRollup` returns, so nothing in it can pre-empt the rollup.
- `addChildren` and `findSingletonResourceId` catch `Exception` around all I/O and parsing, restore the interrupt flag, and return `false` / `null` (skill section *Pushing data: the SuiteApiStitcher facade*; confirmed by reading the framework source and by the framework reviewer's probe). The code outside their `try` blocks (`isUuid`, `normalizeUuid`, size comparisons) cannot throw on any input.
- Every dereference of `vcEntry` in the switch is safe: `LINKED`, `NO_WORLD` and `ADD_FAILED` are only reachable when `vcResourceId` is non-blank, which implies `vcEntry != null`. `NO_VCENTER` logs `config.vcenterHost`, not `vcEntry`.
- `suiteStitcher == null` returns early; `configureAdapter` already logs that.
- Both HTTP calls have connect and read timeouts (`REQUEST_TIMEOUT`).

**Cache behaviour.**
- World not created yet: `findWorld` returns `null`, outcome `NO_WORLD`, nothing cached, retried next cycle. Tested.
- vCenter entry null or blank id: `NO_VCENTER`, no lookup, cache kept. Tested.
- World recreated: correct only if the POST to the old id returns non-2xx. See W2.

**ComputedMetric keys vs declared group and pushed keys.** Consistent.
- Declared: `ResourceGroup Rollup` > `ResourceGroup Environment` > attributes `scored`, `non_compliant`, `no_benchmark`, `avg_score`. Computed keys `Rollup|Environment|<attr>`, the same `group|group|attr` path shape VMWARE uses for `summary|...` on vSphere World.
- Referenced: `VCF-CF Compliance|Rollup|All|{scored, non_compliant, no_benchmark, score_sum}`. `ComplianceRollup.PREFIX = "VCF-CF Compliance|Rollup|"`, `put(out, "All", all)` emits `p + "scored"`, `"non_compliant"`, `"no_benchmark"`, `"score_sum"`. Exact match, including `score_sum` and the prefix.
- Expression form mirrors the VMWARE world counts quoted in the 2026-10-01 recon entry (`sum(${adapterkind=VMWARE, resourcekind=VMwareAdapter Instance, metric=...})`, no `depth`). The bundled super metrics use the same metric keys with spaces and hyphens and work on devel, so the key text itself is proven parseable in the SM engine; whether the ComputedMetric evaluator reads pushed dynamic keys is a devel question.

**avg_score and unreadable-is-not-compliant.** Safe. `score_sum` counts unreadable controls as failing (build 63 rule), and `score_sum > 0` implies `scored > 0`, so a 0/0 can only resolve to no data or 0, which reads as a false alarm, never as a pass (`knowledge/lessons/unreadable-is-not-compliant.md`). It is the weighted shape, never an average of averages. The per-vCenter `avg_score` is not used. See N4 for the sibling counts.

**Does the SDK collect result emit anything that could replace the relationships?** No. The compliance collector does not override `collectRelationships` (framework default returns `null`, and `VcfCfAdapter` only attaches non-empty sets); discovery-on-collect only calls `registerNewResource`; there is no `RelationshipBuilder` use in the adapter. The adapter pushes only `Summary|last_scan_timestamp` onto the world. The skill's "do not mix the two routes on one parent" rule is respected. Whether the VMWARE adapter's own relationship reporting for its `VMwareAdapter Instance` (a type 7 adapter-instance kind) removes a foreign parent edge is unknown; per-cycle re-assertion covers it, but devel should watch for flapping.

**Log volume.** Normal cycle: one INFO line (`Linked vCenter ...`). First cycle: one framework WARN plus one adapter WARN. Persistent failure: see N2.

**Do the tests exercise the decision logic?** Yes for `linkWorld`: first link with lookup, cached re-assert with no lookup, null and blank vCenter, world absent, add failed clears cache, fresh lookup links the new world, argument order. Not covered (and not unit-testable without the SDK): the wiring in `linkVCenterToWorld`, which I verified by reading and bytecode. Not covered and cheaply testable: the describe-to-rollup key contract (N3).

## Findings

### BLOCKING

None.

### WARNING

**W1. Docs parity: the relationship and the environment metrics are undocumented, and two doc lines are about to become false.** Authority: review dimension 11 (cross-MP relationships never appear in `describe.xml`-generated docs); `knowledge/rules/no-fabricated-metrics.md` (why the docs cannot simply claim the values yet).
- `docs/overview.md:50` calls ComplianceWorld an "Adapter liveness anchor"; `docs/overview.md:52` and `docs/data-reference.md:122` say the world "carries only `Summary|last_scan_timestamp`". Build 82 declares four more metrics on it and makes each vCenter object a child of it.
- The new edge (ComplianceWorld parent, VMwareAdapter Instance child) is in no doc surface: not `README.md`, not `docs/README.md`, not `docs/inventory-tree.md`, not `overview.md`. An operator will see vCenter objects appear under Compliance World in navigation with no explanation. The "edge is never removed" limitation is only in `CHANGELOG.md` and a code comment.
- Not BLOCKING for this dev preview: the "carries only" contradiction is conditional on the open devel question (the adapter still pushes only `last_scan_timestamp`; whether the engine fills the four keys is exactly what devel tests), and these docs are not in the pak (`overview.packed` holds only the stub overview HTML). Writing the values into the docs before devel proves them would itself be a fabrication.
- **Fix:** before any `v*` tag, in the same round as the phase 3 repoint: document the relationship and its never-removed limitation in `overview.md`, the landing `README.md` and `data-reference.md`; replace the "carries only" lines with the four `Rollup|Environment` keys. **Registration candidate** (RULE-012) if devel passes and the docs are not updated in that round.

**W2. The world-id cache is only cleared if the POST to a deleted parent fails synchronously, which is not proven; meanwhile the INFO line claims success.** `ComplianceAdapter.java:564` (`complianceWorldId = link.nextCachedWorldId`), `:567` (`Linked vCenter ...` INFO), `ComplianceDecisions.java:614-617`. Authority: skill section *Pushing data: the SuiteApiStitcher facade* ("The add is asynchronous"); framework Javadoc on `addChildren` ("a 2xx means the request was accepted ... the edge may appear a little later"; the spec's 404 is stated for invalid or missing UUIDs in the body, not for the parent).
- If the platform accepts the POST for a parent that no longer exists (or accepts and then drops the edge asynchronously), `addChild` returns `true`, the stale id stays cached for the life of the collector, the edge is never formed, the environment totals stay empty, and the log says "Linked ... under ComplianceWorld" every cycle. That is the "could not do it" case reading as "did it" in the log (review dimension 6: logs must let an operator tell evaluated from could-not-read).
- The cache saves one GET per collect cycle against the local Suite API, which is negligible.
- **Fix (smallest):** reword the INFO to "link requested (accepted by Suite API)". **Fix (robust):** drop the cache and look the world up every cycle, or refresh it on a short TTL (for example every 12 cycles). Either way, add the devel check below (delete-and-recreate is not practical on devel, so at least confirm the edge exists by readback after the first `LINKED`).

**W3. Release ordering: a `v*` tag today fails CI.** Adapter code calls `addChild` and `findSingletonResourceId`, which exist only in the uncommitted factory framework diff. `build-pak-on-tag.yml:35` pins `BUILDKIT_TAG: sdk-buildkit-v1` (floating major); per the framework review, the latest published buildkit is 1.0.10 and `1.0.11` (`src/vcfcf_managementpacks/buildkit.py`) is not tagged. Authority: CLAUDE.md Tier 2 workflow (the official release is the adapter repo's CI build on a `v*` tag). Failure mode is loud (compile error), not silent, hence WARNING. **Fix:** sequence it: factory framework PR merged, `sdk-buildkit-v1.0.11` published and the `v1` tag moved, then the adapter `v*` tag. Record the minimum buildkit in the adapter CHANGELOG entry.

### NIT

**N1. Stale `describe.xml` comment.** `describe.xml:61-70` still says "Build 81 does not create that relationship yet (the framework stitcher has no relationship call)". Build 82 does create it. **Fix:** update the comment to build 82 and the `addChild` route.

**N2. Log volume on the failure paths.** Authority: review dimension 6. An unresolved vCenter now produces four WARNs per cycle for one cause (`ComplianceStitcher.matchVCenterAdapterInstance`, `collectVCenter`, `pushRollup`, and the new `NO_VCENTER`). A persistent `addChild` failure (for example a 403 if the injected instance credential lacks relationship-write rights) produces a framework WARN with a full stack trace plus an adapter WARN and an extra GET every cycle. **Fix:** log `NO_VCENTER` at DEBUG (the three earlier WARNs already say it), and consider WARN-once-then-DEBUG for repeated identical `ADD_FAILED`.

**N3. No test pins the cross-artifact key contract.** The ComputedMetric keys, the `Rollup > Environment` nesting, and `ComplianceRollup.PREFIX + "All|" + {scored, non_compliant, no_benchmark, score_sum}` match today (verified by hand above). A future rename on either side would be silent (no data, no error). **Fix:** a small plain-JDK test that parses `describe.xml`, checks each `ComputedMetric@key` resolves to a declared attribute path, and checks each referenced `metric=` key is in `new ComplianceRollup().toStats()` keys.

**N4. Forward-looking, for phase 3 consumers: zero-scored environments read as "0 non-compliant".** Authority: `knowledge/lessons/unreadable-is-not-compliant.md` zero-divisor contract. When nothing is scored, `Rollup|Environment|non_compliant` sums to 0 next to `scored` 0. Correct as a count, but a tile that shows only `non_compliant` would read as all clear. There is also no environment indicator of how many vCenters are actually reporting (a vCenter that is never resolved is silently absent from the totals; one whose instance died keeps contributing its last values). Both are parity with the bundled super metrics, not regressions. **Fix (when repointing the dashboard):** gate the non-compliant tile on `scored > 0`, and consider a fifth computed key such as a `count(...)` of children carrying `VCF-CF Compliance|Rollup|incomplete`, so "N vCenters reporting" is visible.

## Devel checklist (not findings; makes the devel test conclusive)

1. Collector log: the ambient identity line (`file=instance|automation|maintenance`) and the first `LINKED` line. Then `GET /api/resources/{world}/relationships/children` shows exactly the expected VMwareAdapter Instances, and still exactly those (no duplicates, no gaps) after three or more cycles. Gaps between cycles would mean the VMWARE adapter is removing the foreign parent edge.
2. Relationship-scoped or global evaluation: note the time the edge first appears versus the first `Rollup|Environment|*` value. Values before any edge mean the engine is not walking children, and the relationship is not what made it work.
3. Values: the four Environment keys equal the bundled super metrics on vSphere World (same inputs) for the same timestamps.
4. If any vCenter is unresolved or a 0/0 state can be observed, confirm `avg_score` is no data, not 0 or 100.
5. Confirm the Suite API accepts a type 7 adapter-instance resource (`VMwareAdapter Instance`) as a child of a foreign kind (the 2xx alone does not prove it, see W2).

## Registry check (`knowledge/context/defects.md`)

No open defect has `Affects: compliance`. The closed entries that mention compliance (DEF-005 context) are not reopened by this build. `defect-gate --pak compliance` confirms. Registration candidate: W1, if devel passes and the docs are not updated in that round.

## If shipped as-is

On devel: vCenter objects become children of Compliance World each cycle and the four environment metrics either appear (the desired result) or stay empty; collection, the per-vCenter rollup, and every existing dashboard are unaffected. As a public release: the tag would fail CI (W3), and an operator would find vCenters under Compliance World and four new metrics that the docs say do not exist.
