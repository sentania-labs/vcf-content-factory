# SDK Adapter Review: compliance build 62 (re-review of build 61)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 62, commit `3fde16a`, vs build 61 `04de2b4` (delta: test, docs, one SM description) and build 56 `32de5aa` (pak-compare reference)
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.62.pak`
- **Prior review:** `knowledge/context/reviews/compliance-build-61.md` (APPROVE, 3 WARNING / 3 NIT)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING (carried, owner decision pending) / 0 NIT

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 7 Java suites, generator unittest 12/12, new dashboard alert-list test 3/3. The script runs under `set -euo pipefail`, so a failing Python test fails the script and both workflows that call it (push/PR on `ubuntu-latest`, tag build). |
| `generate_compliance_alerts.py --check` | **Up to date.** |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...62.pak`. Bundled content is unchanged from build 61 (same 4 SMs / 8 views / 4 dashboards; identical content file list). Adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 1 WARNING / 38 INFO**, identical to build 61 (the WARNING is the known ComplianceWorld attribute retirement). |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Build-61 finding closure

| # | Closed? | Evidence |
|---|---|---|
| W1 alert-list drift | **Closed** | `tests/test_dashboard_alert_lists.py` compares each dashboard's `alert_definitions` with `generate_compliance_alerts.collect()` filtered by kind (all / HostSystem / VirtualMachine / vCenter+Cluster+vDS+DVPG). It is stdlib-only, so it runs on the hosted PR runner. Because it derives the expected set from the profiles, profile-side drift (a new or renamed generated control) also fails it. **Independent tamper test** on scratch copies of the repo (ESXi Hosts dashboard edited, real test run): a removed id fails `missing`; an added vm.* id fails `extra`; a duplicated id fails `duplicate`; a renamed id fails `missing`; rewriting the list in flow style (`[...]`) fails "expected one alert_definitions list, found 0". So the line parser cannot silently read nothing. The unmodified repo passes. |
| W2 score gating vs designs | **Open, carried** (owner decision pending) | See WARNING below. |
| W3 SM enablement / dashboards undocumented | **Closed** | README.md and docs/overview.md each gain a Dashboards section naming the four dashboards and stating that the four SMs (vSphere World) must be enabled in the active policy or the Overview tiles and trend stay empty, and that auto-enablement is unconfirmed. docs/installing.md adds this as numbered step 8. Honest about what is unproven. |
| N1 Average Score description | **Closed** | Reworded to "expected, to be confirmed at the devel install", with the correct safe-failure argument (`score_sum > 0` implies `scored > 0`, so the worst case is a false-alarm 0, never a pass). |
| N2 picker default | **Closed as a planned verification** | CHANGELOG acceptance plan (f). No code or content change is possible before seeing the rendered default. |
| N3 upgrade residue | **Closed as a planned verification** | CHANGELOG acceptance plan (e), with removal gated on the owner's verbatim go. |

## Regression review

- The new test only reads files, and wiring it into the runner only adds a check.
- No Java, describe.xml, view, dashboard or super metric formula changed (the SM change is description text only; its formula is byte-identical).
- The docs add no claim that contradicts behavior. In `docs/installing.md` the dashboards table follows step 9 outside the numbered list; it renders as intended.

## WARNING

### W2 (carried from build 61). Approved per-kind designs require score gating that the shipped views and heatmap do not implement

- **Where / what:** unchanged from `compliance-build-61.md` W2. `compliance-esxi-hosts.md`, `compliance-vms.md` and `compliance-vcenter-networking.md` require score columns (and the ESXi heatmap) to hide scores unless `no_benchmark = 0` and `total_count > 0`. The shipped views list every object with flag columns instead, and the heatmap colors a no-longer-scored host by its retained score. The view descriptions still point to a "Known constraints" section that does not exist in the view YAML.
- **Status:** waiting on the owner. Either (a) amend the three designs to accept flag columns and fix the view descriptions, or (b) row-filter the heatmap and add scored-only list variants.
- **Ship risk:** display-only, for unmapped-version objects in Auto mode. Not blocking, but under the fix-everything-before-PR rule it must be resolved (in either direction) before the PR opens.

## Still owed at install (from the CHANGELOG acceptance plan)

Build 60 (a)-(d): live stats/latest shape check, and a staged fixed-8.0 flip proving stale-0 cleanup and alert cancellation on devel, then prod. Build 62 (e)-(g): upgrade-residue check, picker defaults, Average Score no-data before the first cycle, and whether the SMs arrived enabled.

## If shipped as-is

Correct dashboards, keys, alerts and super metrics. A future profile change can no longer silently drop controls from the failing-controls lists, and operators are told to enable the super metrics. The one open item is the owner's call on score gating: the ESXi heatmap can still color an unscored host by an old score.
