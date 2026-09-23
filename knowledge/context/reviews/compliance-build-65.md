# SDK Adapter Review: compliance build 65 (re-review of builds 63 + 64)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 65, commit `d293a57`, vs build 64 `d76d378` (delta) and build 56 `32de5aa` (pak-compare reference)
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.65.pak`
- **Prior review:** `knowledge/context/reviews/compliance-build-64.md` (APPROVE, 2 WARNING)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 7 Java suites, generator unittest 13/13, dashboard alert-list test 3/3. |
| `generate_compliance_alerts.py --check` | **Up to date.** |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...65.pak`. Bundled content: 4 SMs / 8 views / 4 dashboards. Adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 1 WARNING / 38 INFO**, same as builds 61-64 (the known ComplianceWorld attribute retirement). |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Build-64 finding closure

### W1 version-unreadable: closed

- **Payload:** `ComplianceDecisions.versionUnreadableStats` now pushes `score` 0, pass/fail/total 0, `no_benchmark` 0, `non_compliant` 1 and `collection_failed` 1. It still does not push `unreadable_count`, which is deliberate and documented: the adapter does not know which benchmark's controls apply.
- **Rollup:** `ComplianceRollup.recordVersionUnreadable` counts the object as non-compliant, scored 0 and in the `unknown` bucket, so it no longer flatters the average. It also skips alert cleanup and leaves benchmark memory untouched, as before.
- **New metric `VCF-CF Compliance|collection_failed`:** pushed on every payload path of a matched object:
  - `complianceStats`: `collectionFailed(cr)` is `totalCount == 0 && unreadableCount > 0`, so it is 1 only when everything attempted was unreadable (disconnected host) and 0 on any object with at least one read value;
  - `noBenchmarkStats`: 0;
  - `nothingEvaluatedStats`: 0;
  - `versionUnreadableStats`: 1.

  **It cannot hold an alert open on a healthy object:** the next normal cycle recomputes it from that cycle's result and pushes 0. The one path that pushes 1 without an evaluation (version unreadable) is replaced the next cycle, either by the reused previous benchmark (now remembered) or by a normal evaluation.
- **Tests:** version-unreadable payload; `collection_failed` is 1 on all-unreadable, 0 on partial-unreadable, no-benchmark and nothing-evaluated; rollup scored-0; a restart case in `MixedVersionSimulationTest`.
- **Expected consequence (consistent with build 63):** a version-unreadable HostSystem now pushes score 0, so the Critical "Host Compliance Score Degraded" alert fires alongside the collection alert, exactly as for a disconnected host.

### Collection alerts, two-symptom OR: verified

- **Symptoms:** six new `vcfcf_compliance_collection_<kind>_failed` symptoms, one per Ops kind (HostSystem, VirtualMachine, VMwareAdapter Instance, ClusterComputeResource, VmwareDistributedVirtualSwitch, DistributedVirtualPortgroup), each `VCF-CF Compliance|collection_failed` `=` 1, Immediate, nameKeys 2020-2025.
- **Alerts:** the six alert ids are unchanged. Each now carries `<SymptomSets operator="or">` with two `<SymptomSet ... operator="and" aggregation="any" applyOn="self" negateCondition="false"/>` children (`_unreadable` and `_failed`). This is the same structure as the hand-written `vcfcf_compliance_score_degraded` (warning / critical OR), which is proven installed and firing on prod (recon log, build-56 era).
- **Script check of describe.xml:** 158 symptoms (144 + 12 + 2), 151 alerts, 148 recommendations. No duplicate ids, no dangling symptom or recommendation references, nameKeys unique and all present in `resources.properties`. The shared recommendation text now covers the version-unreadable case.

### W2 stale wording: closed

The three UNAUDITED passages, the ControlEvaluator javadocs and comments, the `decide()` javadoc, README and overview.md now state the build-63 rule. A repo sweep for `excluded from every score | excluded from the score | last-known | scored_stale` leaves only:
- historical CHANGELOG entries;
- the two tests asserting `scored_stale` is absent;
- the ComplianceRollup and overview notes saying it is retired;
- `UNAUDITED_CONTROLS.md:416`, which is still correct: it describes an *absent* advanced-setting key, which is skipped, not unreadable.

## Dashboards and drift test

Unaffected: `git diff d76d378 d293a57 -- dashboards views supermetrics tests/test_dashboard_alert_lists.py` is empty. The collection alert ids did not change, so the 150 / 87 / 24 / 39 lists and the drift test still pass.

## NIT

- **N1.** `docs/overview.md:122-131` says a disconnected host "is not reported as a violation ... Instead the object raises 'Compliance data not collected'". Since build 63 its score of 0 also fires the Critical "Host Compliance Score Degraded" alert, and since build 65 so does a version-unreadable host. The CHANGELOG (build 63 item 3) says this, but the operator docs do not. Add one sentence so an operator seeing two alerts on a disconnected host knows that is expected.

## Observation (not the adapter's to fix)

`docs/inventory-tree.md` carries an em-dash in the factory docs generator's fixed "Do not edit ... regenerated on every build" header line, unchanged except for the version number. It comes from the factory generator (`tooling` owns it), not the adapter, and it conflicts with the user's no-em-dash rule, so it is worth a tooling issue.

## Still owed at install

CHANGELOG acceptance plan (a)-(g), plus: on devel, a disconnected or not-responding host shows score 0, `collection_failed` 1, the Critical score alert and the collection alert, and all clear on reconnect.

## If shipped as-is

Scores, alerts, rollups and dashboards behave as the owner decided in every read-failure case, including a version that cannot be read after a restart. The only gap is that the overview doc does not warn that a disconnected host raises the score alert as well as the collection alert.
