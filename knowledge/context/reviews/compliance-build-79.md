# SDK Adapter Review: compliance build 79 (Rollup|incomplete flag), final pre-release pass

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 79, commit `d3665c5`, vs build 78 `b8e8735`; pak-compare vs build 56 `32de5aa`
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.79.pak`
- **Prior review:** `knowledge/context/reviews/compliance-build-78.md` (APPROVE, 1 WARNING)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE**
- **Findings:** 0 BLOCKING / 0 WARNING / 0 NIT. **Nothing remains open from the review series (builds 57-79).**

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 10 Java suites, generator unittest 14/14, dashboard alert-list drift test 3/3. |
| `generate_compliance_alerts.py --check` | **Up to date.** |
| describe.xml integrity (script) | 151 symptoms / 143 alerts / 140 recommendations; no duplicate ids; no dangling `SymptomSet` or `Recommendation` references; nameKeys unique and all present in `resources.properties` (new 2030 = "Compliance inventory listing failed on vCenter"). |
| Dashboards | Unchanged in this build (empty diff over dashboards, views, super metrics and the drift test). Lists 142 / 87 / 24 / 31. The Overview and vCenter & Networking alert lists already carry `vcfcf_compliance_collection_vcenter`, so the new trigger surfaces there with no content change. |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...79.pak`; adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 2 WARNING / 38 INFO**, the same two intended warnings as builds 75-78 (the `read_appliance_settings` instance identifier, `identType="2"`, and the ComplianceWorld attribute retirement). |
| Registry | No `defects.local.md`; no open defect in `knowledge/context/defects.md` names `compliance`. Nothing to re-assert, no closure to propose, no registration candidate. |

## Build-78 W1: closed

- **Always pushed:** `ComplianceRollup.toStats` writes `VCF-CF Compliance|Rollup|incomplete` (0/1) **before** the incomplete early return. It is therefore present on a complete cycle (0) and on a held-back cycle (1), and never omitted, so it cannot go stale. `Build77FaultTest` asserts 1 on a failed listing and 0 on the next complete cycle.
- **Push path:** `pushRollup` sends the whole map whenever the vCenter object resolves. When it does not resolve, nothing is pushed to that object at all, which is the existing, logged behavior.
- **Symptom wiring:** a generated `vcfcf_compliance_collection_vcenter_rollup_incomplete` symptom (`Rollup|incomplete` `=` 1, Immediate, VMWARE / VMwareAdapter Instance, nameKey 2030) is the third child of the existing `vcfcf_compliance_collection_vcenter` `SymptomSets operator="or"`. That is the same structure as the two-child form reviewed in build 65 and the hand-written score alert proven firing on prod. The alert id is unchanged, so the dashboard lists and the drift test are unaffected.
- **Recommendation:** the shared recommendation adds the vCenter case (which listing failed is in the log; check the account's inventory read permissions) and when the alert clears.
- **Operator visibility:** a persistent VM / vDS / portgroup / cluster listing failure now raises "Compliance data not collected (vCenter)" on that vCenter. It shows in the Environment Overview and vCenter & Networking alert panes and clears on the first complete cycle. A persistent *host* listing failure still fails the whole cycle (build 77), which puts the adapter instance into ERROR. That is a different, already-visible signal, so the flag not being pushed in that case is not a gap.

## Release-readiness statement

This static gate has no open findings for the compliance pak at build 79: no BLOCKING, WARNING or NIT from any review in the 57-79 series remains unresolved, and no registry defect affects the pak. What is still owed is **live verification, not code**: the CHANGELOG acceptance plan items (a)-(h), (e2) and (i)-(iv), plus the review-added devel checks:
- non-vSAN clusters show `cluster.managed-disk-claim` / `cluster.object-checksum` at -1;
- a disconnected host shows score 0 with both the Critical score alert and the collection alert, clearing on reconnect;
- an inaccessible VM, if devel has one, reports unreadable VM settings;
- `dvpg.network-reset-port` resolves on portgroups under a 7.0 / 8.0 / 9.0 benchmark;
- the three esxcli encryption fields resolve (or the WARN names the fields returned).

Per RULE-012 the release is also gated by `python3 -m vcfcf_packaging defect-gate --pak compliance` in the tag workflow.

## If shipped as-is

The pak behaves as designed and reviewed. Every read failure surfaces as unreadable (never a pass), environment rollups are never silently under-counted, and a persistent listing failure raises a visible vCenter collection alert.
