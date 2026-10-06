# SDK adapter review: compliance build 84

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-02 (local, America/Chicago)
- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/environment-computed-metrics`, base `main` at `0a7d539`, uncommitted working tree)
- **Artifact reviewed:** `dist/vcfcf_sdk_compliance.0.0.0.84.pak` (built 09:45 CDT), sha256 `1185dcec1c064cce11430411883b3be0901d704b8052d28006fd56d47e31415f` (confirmed). Reference: `dist/vcfcf_sdk_compliance.0.0.0.79.pak` (the build on devel).
- **Prior pass:** `knowledge/context/reviews/compliance-build-82.md` (APPROVE, 3 WARNING / 4 NIT)
- **Verdict:** APPROVE (0 BLOCKING / 3 WARNING / 3 NIT)
- **Fit for a devel install: YES.** None of the open findings changes what the devel test will show or makes it misleading.

## Bottom line

Every claimed change is in the source and in the built pak. The world-id cache is gone from both the source and the bytecode (no field, lookup every cycle), the success line says "requested and accepted", `NO_VCENTER` is DEBUG, `ADD_FAILED` is one WARN, and the framework jar in the pak is byte-identical to `adapter_runtime/vcfcf-adapter-base.jar` and to a fresh compile of the current framework source. The new contract test catches every rename it claims to catch; it does not catch a swapped or semantically wrong expression (N2). The one new process gap: the framework's log-sanitising change landed after framework-reviewer's second pass and has not been reviewed by it (W3). That gates the factory PR, not the devel install; I read and tested that code myself for this pak.

## Independent verification

| Check | Result |
|---|---|
| Pak checksum | `1185dcec...e31415f`, matches the brief |
| `validate-sdk content/sdk-adapters/compliance` | OK (javac 19 files, the pre-existing `-source 11` options warning only) |
| `ci/run_java_tests.sh` | 11 Java suites pass, including `EnvironmentKeyContractTest` ("4 computed keys, 5 metric references"); alert generator 14 tests OK; dashboard alert lists 3 tests OK. Runner is `set -euo pipefail` and `T.check` throws `AssertionError`, so a failed assertion fails CI. |
| `build-sdk` into scratchpad | reproduces `vcfcf_sdk_compliance.0.0.0.84.pak`. Versus the author's pak: adapter jar classes identical, `describe.xml` and `resources.properties` identical, views and overview contents identical (zip timestamps only), framework jar byte-identical. Adapter repo working tree unchanged by the build (porcelain status and diff hash equal before and after). |
| `pak-compare` 84 vs 79 (author's pak and mine) | gate PASS, 0 BLOCKING / 0 WARNING / 0 INFO. As in build 82, pak-compare reports nothing for the new `ComputedMetrics` block, so it is not evidence for it; verified directly. |
| Built pak `describe.xml` | identical to source; `Rollup` (30) > `Environment` (31) with `scored`, `non_compliant`, `no_benchmark`, `avg_score` (32 to 35) and the four `ComputedMetric` entries; ComplianceWorld comment describes the build 82+ route and "looked up each cycle, never cached" |
| Pak manifest / version.txt | `0.0.0.84` / `Implementation-Version=0.84` |
| Adapter bytecode: no cached world id | `javap -p ComplianceAdapter`: no world-id field (the only volatile `String` fields are `cycleConfDir` and `lastObjectFailure`). `WorldLink` has only `outcome` and `worldId`; `LinkOutcome` is `ACCEPTED, NO_VCENTER, NO_WORLD, ADD_FAILED`; `linkWorld(String, Supplier, BiPredicate)` takes no cached id. `linkVCenterToWorld` bytecode: no `putfield`; `NO_VCENTER` goes to `logDebug`, `NO_WORLD` and `ADD_FAILED` to one `logWarn` each, `ACCEPTED` to `logInfo` with "requested and accepted by Suite API". |
| Build 83 vs 84 | adapter jar classes and `describe.xml` identical; only the framework jar differs (`1dd0648d...` to `dac4b36d...`). Matches the CHANGELOG's "no adapter source change". |
| Framework jar in pak | sha256 `dac4b36d...c73341`, equal to `src/vcfcf_managementpacks/adapter_runtime/vcfcf-adapter-base.jar`. No framework `.java` is newer than the jar. Fresh compile of current framework source (`-source 11 -target 11 -proc:none`, SDK jar only): all 43 classes byte-identical to the jar. |
| Framework tests | `SuiteApiStitchRelationshipTest` with `adapter_runtime/lib/*`: 130/130 pass, including the `isExpectedFailure` / `failureSummary` cases and the RuntimeException stack-trace branch for both calls. |
| Secrets in the new log lines | `failureSummary` logs `Class: message`. Transport messages carry method, URL, HTTP status, and on 401 the mechanism and principal name; never the password or token (`acquireToken` builds the credential body but never puts it in an exception). Consistent with `knowledge/rules/no-secrets-on-disk.md`. |
| `defect-gate --pak compliance` | "no open blocking defects affecting compliance" |

## Build 82 findings, closure check

| Build 82 finding | Status in build 84 | Evidence |
|---|---|---|
| W1 docs parity | **Open, deferred to phase 3 by design** | `docs/overview.md:50` ("Adapter liveness anchor"), `docs/overview.md:52` and `docs/data-reference.md:122` ("carries only") unchanged; relationship still in no doc surface. Deferral recorded in the design file, "Carried into phase 3". Carried as W1 below. |
| W2 world-id cache | **Closed** | Source and bytecode above; `ComplianceDecisionsTest` asserts a lookup every cycle and that a recreated world id is used on the next cycle. |
| W3 release ordering | **Open, no code needed** | `build-pak-on-tag.yml:35` still `sdk-buildkit-v1`; CHANGELOG build 83 entry records the buildkit prerequisite. Carried as W2 below. |
| N1 stale describe comment | **Closed** | `describe.xml:57-73`. |
| N2 log volume | **Closed** | `NO_VCENTER` at DEBUG; persistent `ADD_FAILED` is now one framework WARN line (stack trace at DEBUG for `IOException` / `InterruptedException`) plus one adapter WARN line. |
| N3 key contract test | **Closed, with gaps** | See mutation results; residual gaps are N2 below. |
| N4 zero-scored tile guard | **Open, deferred to phase 3 by design** | No consumer exists yet in this build. Carried as N3 below. |

## Mutation test of `EnvironmentKeyContractTest`

Each mutation applied to a scratch copy of `describe.xml` or `ComplianceRollup.java`, then the test compiled and run alone.

| Mutation | Should fail? | Result |
|---|---|---|
| Baseline | no | pass |
| Rename declared attribute `avg_score` | yes | **fails** ("ComputedMetric key is a declared attribute") |
| Rename referenced metric `All|score_sum` | yes | **fails** ("produced by toStats") |
| `resourcekind=VMwareAdapterInstance` (no space) | yes | **fails** |
| Change `ComplianceRollup.PREFIX` | yes | **fails** ("carries ComplianceRollup.PREFIX") |
| Rename `score_sum` in `toStats` | yes | **fails** |
| Delete one `ComputedMetric` | yes | **fails** (set mismatch) |
| `adapterkind=vmware` | yes | **fails** |
| Rename `Environment` group | yes | **fails** |
| `scored` expression replaced by constant `"0"` | yes | **passes** (N2) |
| `Environment|scored` reads `All|non_compliant` | yes | **passes** (N2) |
| `no_benchmark` reads `Host|` instead of `All|` | yes | **passes** (N2) |
| `avg_score` divides `scored / score_sum` | yes | **passes** (N2) |
| Space before `}` in a metric reference | arguably | **passes** (the test trims; whether the engine does is unknown) |

The test does exactly what the brief claims (keys against declared attributes, referenced keys against `toStats` using the real `PREFIX`). It does not pin which source key feeds which environment key.

## Findings

### BLOCKING

None.

### WARNING

**W1. Docs parity: still open, carried from build 82 W1.** Authority: review dimension 11; `knowledge/rules/no-fabricated-metrics.md`. `docs/overview.md:50`, `docs/overview.md:52`, `docs/data-reference.md:122` still describe ComplianceWorld as a liveness anchor that "carries only" `last_scan_timestamp`, and the ComplianceWorld to VMwareAdapter Instance edge is in no doc surface (`README.md`, `docs/README.md`, `docs/inventory-tree.md`, `overview.md`). The deferral is recorded in `knowledge/designs/sdk-adapters/compliance-environment-computed-metrics.md` ("Carried into phase 3"). Not a devel blocker: the docs are not in the pak, and writing the values in before devel proves them would itself be a fabrication. **Fix:** in the phase 3 round, before any `v*` tag. **Registration candidate** (RULE-012) if phase 3 slips and a tag is proposed with these lines unchanged.

**W2. Release ordering: still open, carried from build 82 W3.** A `v*` tag today fails CI at compile time because the published buildkit lacks `addChild` / `findSingletonResourceId`. Loud, not silent. Recorded in the CHANGELOG build 83 entry and the design file. **Fix:** factory PR merged, `sdk-buildkit-v1.0.11` published and `v1` moved, then the adapter tag.

**W3. The framework change that ships in this pak has not been through framework-reviewer.** Authority: RULE-013 (`knowledge/rules/` blanket framework gate, CLAUDE.md delegation rule 9). The framework review report (`knowledge/context/reviews/framework/adapter-framework-stitch-relationship-add-2026-10-02.md`, last written 09:30 CDT) has no mention of `logFailure`, `isExpectedFailure` or `failureSummary`; `SuiteApiStitchClient.java` was last modified 09:40 and `SuiteApiStitcher.java` 09:33, both after it. The design file's "framework-reviewer APPROVE on two passes" therefore no longer covers the current diff. I read the change for what this pak exercises (catch-all intact, interrupt flag restored, no secrets in the one-line summary, stack trace kept for unexpected runtime exceptions) and the framework suite passes 130/130, so it does not hold up the devel install. **Fix:** a third framework-reviewer pass on the post-09:30 framework diff before the factory PR opens; update the design file's "Go and progress" line once it lands.

### NIT

**N1. The `NO_WORLD` WARN says "not found (expected on the first cycle)" when the lookup itself failed.** `ComplianceAdapter.java` `linkVCenterToWorld`, `NO_WORLD` case. Authority: review dimension 6 (logs must separate "could not read" from "read and found nothing"). `findSingletonResourceId` returns `null` for zero matches, several matches, a partial page and a failed query alike, so the adapter cannot tell them apart and always prints the first-cycle wording, on every cycle.

Would it mislead during the devel test? Only a reader who looks at the adapter line alone. The framework writes its own WARN immediately before it, naming the real cause ("findSingletonResourceId query failed for vcfcf_compliance/ComplianceWorld: IOException: Suite API GET ... HTTP 403", or "found 2 ... resources", or "partial page"), and a grep for `ComplianceWorld` returns both lines. The devel checklist below also treats `NO_WORLD` after the second cycle as a failure regardless of wording. Nothing is scored from this path, so no false pass is possible. **Fix (cheap):** drop "(expected on the first cycle, ...)" or reword to "no single ComplianceWorld id resolved (see the preceding SuiteApiStitchClient WARN for why; normal only on the first cycle)".

**N2. The contract test does not pin which source key feeds which environment key.** `tests/com/vcfcf/adapters/compliance/EnvironmentKeyContractTest.java`. A swapped key, a `Host|` instead of `All|` reference, an inverted `avg_score` division, or a constant expression all pass (mutation table). The final assertion `refs >= computed.size()` is labelled "every ComputedMetric expression references a metric" but checks the total, so one constant expression passes while `avg_score` contributes two references. A swap is a silent wrong number, which is the failure this test exists to stop. **Fix:** a literal expected map, `Rollup|Environment|scored` to `[All|scored]`, `non_compliant` to `[All|non_compliant]`, `no_benchmark` to `[All|no_benchmark]`, `avg_score` to `[All|score_sum, All|scored]` in that order, checked per expression.

**N3. Zero-scored environments read as "0 non-compliant" (carried from build 82 N4, deferred to phase 3).** Authority: `knowledge/lessons/unreadable-is-not-compliant.md` zero-divisor contract. No consumer of `Rollup|Environment|*` exists in this build, so nothing can mis-render yet. **Fix:** when the dashboard is repointed, gate the tile on `scored > 0` and consider a count of vCenters reporting.

## Anything the changes introduced

- No new throw path: `linkWorld` has no I/O; both framework calls still catch `Exception`, restore the interrupt flag and return `false` / `null`; `logDebug` null-guards its logger.
- No new memory or session state: removing the cache removed the only cross-cycle field this feature added.
- Cost: one extra local GET per cycle per instance (the lookup), as intended.
- `docs/README.md` and `docs/inventory-tree.md` now carry the `0.0.0.84` dev stamp from `build-sdk`; that is the intended behaviour since factory #188 and a release build regenerates them.

## Devel checklist (unchanged from build 82, still applies)

1. Collector log: the first `ACCEPTED` INFO line ("requested and accepted by Suite API"). `NO_WORLD` on cycle 1 is normal; on cycle 2 or later, read the `SuiteApiStitchClient` WARN directly above it for the cause.
2. `GET /api/resources/{world}/relationships/children` shows exactly the expected VMwareAdapter Instances, and still exactly those after three or more cycles (gaps would mean the VMWARE adapter is removing the foreign parent edge).
3. Note when the edge first appears versus the first `Rollup|Environment|*` value.
4. The four Environment values equal the bundled super metrics on vSphere World for the same timestamps.
5. Where a 0/0 can be observed, `avg_score` is no data, not 0 or 100.

## Registry check (`knowledge/context/defects.md`)

No open defect has `Affects: compliance` (open entries are synology, unifi, vcommunity-*, `factory:dashboards`, `factory:extractor`). No `defects.local.md` exists in this clone. `defect-gate --pak compliance` confirms. Registration candidate: W1, if a `v*` tag is proposed before the phase 3 docs round.

## If shipped as-is

To devel: vCenter objects become children of Compliance World each cycle and the four environment metrics either fill (the desired result) or stay empty; collection, the per-vCenter rollup and every existing dashboard are unaffected, and a failed link is two short WARN lines per cycle with the real cause in the first. As a public release: not possible yet (W2), and the docs would contradict the pak (W1).
