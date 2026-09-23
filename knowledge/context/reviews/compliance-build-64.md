# SDK Adapter Review: compliance builds 63 + 64 (reviewed together)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Builds reviewed:**
  - 63, commit `4e2d619` (adapter: score rule, collection alerts, carry-forward retired)
  - 64, commit `d76d378` (content: dashboard alert lists, view descriptions, Overview W3 `select_first_row`)
  - Delta vs build 62 `3fde16a`; pak-compare vs build 56 `32de5aa`.
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.64.pak`
- **Contract:** owner decisions after build 62, verbatim in `knowledge/designs/sdk-adapters/compliance-v3-version-aware.md` § "Owner decisions after build 62"; Option A recorded in the dashboard notes.
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 2 WARNING / 0 NIT

## Claims check (independently re-run, at build 64)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 7 Java suites, generator unittest 13/13, dashboard alert-list test 3/3. |
| `generate_compliance_alerts.py --check` | **Up to date** (144 per-control + 6 collection symptoms/alerts + 1 shared recommendation). |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...64.pak`. Bundled content: 4 SMs / 8 views / 4 dashboards. Adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 1 WARNING / 38 INFO**, same as builds 61-62 (the known ComplianceWorld attribute retirement). |
| Registry | No `defects.local.md`; no open defect names `compliance`. |
| Build 63 alone | Its own CI would be red (the drift test expects the collection ids that build 64 adds). Intended by the author; **never tag `v*` at 63.** |

## Score rule: every path that feeds it

- **Formula:** `ControlEvaluator.score(pass, fail, unreadable) = pass / (pass + fail + unreadable) * 100`. The placeholder 100.0 appears only when nothing was attempted.
- **Every producer uses it:**
  - `evaluateControls` passes 0 unreadable (advanced settings have no unreadable outcome).
  - `evaluateControlsUnreadable` scores all-unreadable as 0.
  - `evaluateVimProperties` covers vim / esxcli / VAMI.
  - `ComplianceAdapter.mergeResults` calls `score()` on the merged counts, so a host with advanced settings passing and vim reads unreadable is scored over the union, not per channel.
  - No other score computation remains (grep: the only literal 100.0 left is `emptyResult`, which has `attempted() == 0`).
- **Payload:** `ComplianceDecisions.complianceStats` pushes `score` when `attempted() > 0`, so an all-unreadable object pushes 0. `fail_count` and `unreadable_count` stay separate. Per-control `Compliant` stays -1 for unreadable. Objects with nothing attempted (for example a non-vSAN cluster) still omit the score (`pushOrProfileName` goes to the nothing-evaluated payload).
- **Rollup:** `recordEvaluated` scores when `totalCount + unreadableCount > 0`, so an all-unreadable object counts in `scored` / `score_sum` with 0. `recordStaleScore`, the `stale` tally and the `Rollup|Host|scored_stale` push are removed; `ComplianceRollupTest` and `MixedVersionSimulationTest` assert the key is absent.
- **Disconnected host:** `isDisconnectedState` leads to `wholeUnreadable` (all controls UNREADABLE), so `score = 0` is pushed. The `vcfcf_compliance_score_critical` symptom (`score < 80`) fires the "Host Compliance Score Degraded" alert at Critical. `unreadable_count > 0` fires `vcfcf_compliance_collection_host` at Immediate at the same time, as the owner decision expects. The per-control alerts cancel (all -1).
- **Carry-forward retired:** `lastKnownHostScore`, `evictAbsentHostScores` and `applyLastKnownForUnreadableHost` are deleted, including the call on the version-unreadable path.

## Collection alerts

Verified by script against `describe.xml` and `resources.properties`:
- **Totals:** 152 symptoms (144 + 6 + 2), 151 alert definitions (144 + 6 + 1), 148 recommendations (144 + 1 + 3). No duplicate ids.
- **References:** every `SymptomSet ref` and `Recommendation ref` resolves.
- **Name keys:** unique, each with a properties entry (2000-2011, 2100; no clash with the 1000-1431 per-control range or the hand-written 1xx keys).
- **Definitions:** the six alerts `vcfcf_compliance_collection_{host,vm,vcenter,cluster,vds,portgroup}` sit on the six real Ops kinds (HostSystem, VirtualMachine, VMwareAdapter Instance, ClusterComputeResource, VmwareDistributedVirtualSwitch, DistributedVirtualPortgroup). Condition: metric `VCF-CF Compliance|unreadable_count` `>` 0; symptom severity Immediate; alert type 15 subType 21, badge risk. All six share `vcfcf_compliance_collection_check`.
- **Recommendation text:** accurate against the code: counts as failing, no per-control alert, `Compliant` -1 with Actual "(unreadable)", Unreadable column, causes and checks.
- **Reproducibility:** the generator emits the collection blocks and `--check` is clean.

## Dashboards and drift test (build 64)

- **Lists:** Overview 150, ESXi Hosts 87, VMs 24, vCenter & Networking 39. No duplicates. Each carries exactly its kinds' collection ids. The hand-written score alert remains excluded.
- **Drift test:** `expected_ids` now appends `gen.collection_ids()` filtered by kind, so the collection alerts are covered by the same missing / extra / duplicate check verified by tamper test in the build-62 review.
- **Overview W3:** `select_first_row: true` is explicit and the rendered `dashboard.json` carries `selectFirstRow: true` on W3; W6 receives 150 definitions.
- **Views:** all six descriptions state Option A (unfiltered rows, the No SCG flag marks a retained score, unreadable counts as failing, SUM-only totals). The build-61 dangling "Known constraints below" reference is gone. Option A is recorded in the dashboard design notes (for example `compliance-esxi-hosts.md` § Retained scores).
- **Build-61 W2:** closed by owner decision (Option A).

## Stale-reference sweep

`grep -i "scored_stale|last-known|lastKnown|recordStaleScore|excluded from the score|excluded from every"` over the adapter repo (excluding `.git` and CHANGELOG history):
- **Clean:** README, docs/*, views and dashboards. `docs/overview.md:154` and `ComplianceRollup.java:38` mention scored_stale only to say it is retired, which is correct. The two test mentions assert it is absent.
- **Still stale:** see W2.

## WARNING

### W1. A version-unreadable object is a collection failure that raises no collection alert and drops out of the score average

- **Where:** `ComplianceDecisions.versionUnreadableStats` (`:175-183`, pushes no `unreadable_count` and no score); `ComplianceAdapter.recordVersionUnreadable`; `ComplianceRollup.recordVersionUnreadable` (non_compliant and bucket only, never scored).
- **Authority:** owner decision 1 ("count it as failing, but can we tell the user it's failing to collect?"); skill § *Unreadable is NOT compliant* (a failed read must not flatter the average).
- **What:** when an object's governing version cannot be read and there is no previous benchmark (first cycle after a collector restart or instance edit, plus a version-read failure):
  1. **No collection alert, or a wrong one.** The collection symptom reads `unreadable_count`, which this path deliberately does not push. So the alert follows whatever value Ops retained: it never fires if the last value was 0, or stays firing on a stale count. The user is not told this object failed to collect, which is the exact case decision 1 asks to surface.
  2. **The average is flattered.** Every other all-unreadable object now scores 0 in the rollup, but this one is left out of `scored` / `score_sum`. With the build-49 carry-forward retired, nothing keeps it in the denominator, so the vCenter and environment averages improve when a host's version cannot be read. That is the flattering-denominator case Task #16 existed to prevent.
- **Scope:** rare (restart or edit plus a version-read fault). It never produces a pass: `non_compliant` = 1 and the `unknown` bucket still show it.
- **Fix:** make version-unreadable consistent with the new rule:
  - **Payload:** push `score` 0 and a collection signal. Either set `unreadable_count` to at least 1 on this path, or add a dedicated `VCF-CF Compliance|collection_failed` (0/1) metric pushed on every path and move the six collection symptoms onto it.
  - **Rollup:** count it as scored with 0 in `recordVersionUnreadable`.
  - **Alternative:** record an explicit owner acceptance of the gap in the design and docs.

### W2. Stale "excluded from the score" and "last-known" text survives the rule change

- **Where:**
  - `profiles/UNAUDITED_CONTROLS.md` lines 383, 429 and 456: "counted in `unreadable_count`, excluded from every score". This file ships inside the pak (`conf/profiles/`).
  - `src/.../ControlEvaluator.java:71`: "excluded from pass / fail / the score denominator".
  - `src/.../ComplianceDecisions.java:62`: `decide()` javadoc still promises a "last-known host score" for version-unreadable objects.
- **Authority:** reviewer dimension 11 (docs must state what the pak does; the landing docs are correct, and this is a shipped secondary note plus code comments, hence WARNING); coordinator brief ("no stale references ... in code, docs").
- **What:** the audit note tells an operator that an unreadable coverage gap never affects a score, but since build 63 it pulls the score down, to 0 for a fully unreadable object. The two javadocs describe retired behavior to the next maintainer.
- **Fix:** reword the three UNAUDITED lines to "counted in `unreadable_count` and as failing in the score (build 63), never a pass". Correct the two javadocs.

## Still owed at install

CHANGELOG acceptance plan (a)-(g) as of build 62. In addition, confirm on devel that a disconnected or not-responding host shows score 0 with both the Critical score alert and the collection alert, and that both clear when the host reconnects.

## If shipped as-is

Scores, alerts and dashboards behave as the owner decided. A disconnected host now reads 0 and raises both the Critical score alert and a "Compliance data not collected" alert with a runbook. In the rare case where an object's version cannot be read right after a restart, the user gets no collection alert and the vCenter and environment averages briefly improve. The shipped UNAUDITED_CONTROLS note still says unreadable gaps never affect a score.
