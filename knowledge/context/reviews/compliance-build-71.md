# SDK Adapter Review: compliance builds 69-71 (Codex PR #12 follow-ups)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Builds reviewed:** 69 `58a0536` (docs), 70 `f717325` (adapter), 71 `280f927` (content), vs build 68 `b87bacb`; pak-compare vs build 56 `32de5aa`
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.71.pak`
- **Trigger:** Codex review on compliance PR #12. P1: standard-switch controls scored on DVS objects (false pass). P2: retained score not identifiable once an object stops being evaluated.
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **CHANGES REQUESTED**
- **Findings:** 1 BLOCKING / 0 WARNING / 0 NIT

## Claims check (independently re-run, at build 71)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 7 Java suites, generator unittest 14/14, dashboard alert-list drift test 3/3. |
| `generate_compliance_alerts.py --check` | **Up to date.** 138 per-control (vDS 5, was 11) + 6 collection alerts. |
| describe.xml totals | **Confirmed by script:** 152 symptoms / 145 alerts / 142 recommendations; no `*standard*` alert id remains. |
| Dashboard lists | **Confirmed:** Overview 144, ESX Hosts 87, VMs 24, vCenter & Networking 33; the drift test passes. |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...71.pak`; adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 1 WARNING / 38 INFO**, same as builds 61-68 (the known ComplianceWorld attribute retirement). |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Build 69 (docs): build-68 nits closed

- The design note's Effect line now reads `"ESXi" becomes "ESX"`.
- The two `normalize_scg_v70.py` comments are fixed; the remaining hit at `:30` is the vendor product name.
- The CHANGELOG adds acceptance item (e2) to confirm the renamed host dashboard replaces the old one.

## Codex P1 closure (build 70)

- **Overlay:** `profiles/manual_review.csv` gains the 15 rows (3 standard-switch ids x 5 profiles). My independent sweep (below) confirms every one is now unscored in every profile and that no `*standard*` alert remains.
- **Overlay required:**
  - `BenchmarkLoader.loadManualReview` now throws when the file is absent from both `<confDir>/profiles/` and the classpath.
  - **It cannot take a normal install Down:** the file ships in the pak at `vcfcf_compliance/conf/profiles/manual_review.csv` (extracted from the built pak), and `confDir` is the parent of `describe.xml`, which is that `conf/` directory.
  - Custom-profile mode never calls it on the scoring path. The cleanup's `bundledForCleanup` catches a load failure and skips cleanup.
  - ProfileSetTest asserts the missing-file failure and its actionable message.
- **Cleanup of demoted controls:** `candidateControlIds` now adds every overlay-demoted control of the kind from every bundled profile, then removes the current benchmark's evaluated set. A `Compliant = 0` left on a vDS by builds 57-69 for the six standard-switch ids is read back by the live stats/latest cleanup and flipped to -1 (the build-59 cleanup never creates keys and never touches -1/1). Correct, and its only cost is that a handful of prose-demoted ids join the queried candidate set.
- **Guard:** ProfileSetTest fails if any DVS/DVPG row with an `esx-`/`esxi-` source ref, or a `standard` id or source ref, is evaluable. It is a useful guard, but it keys on names, not on whether the recipe path exists on the kind. That gap is how B1 below got through.

## Codex P2 closure (build 71)

The six object views gain "Controls Evaluated" (`VCF-CF Compliance|total_count`) after the score. The SUM index lists resolve by script to:
- Host Detail, VM Detail, vCenter Servers, Clusters, Distributed Switches, Distributed Portgroups: `total_count, fail_count, unreadable_count, non_compliant, no_benchmark`;
- Compliance by vCenter: the 5 x (`scored`, `non_compliant`) pairs + `no_benchmark`;
- SCG Versions: all 7 bucket columns.

No index points at a string or score column or out of range. `total_count` is zeroed on the no-benchmark, nothing-evaluated and version-unreadable payloads, so a retained score now sits beside "Controls Evaluated 0". That closes P2.

## Independent DVS / DVPG / Cluster / vCenter sweep (every row, all five profiles)

The generator's own `scored()` rule was run over every canonical row of the four non-host kinds.
- **No host-sourced or standard-switch row is scored on a distributed object.** The only such rows are the 15 now demoted plus the `dvpg.network-vgt` powercli-only duplicates, which were never scored.
- **Every scored recipe path was checked against the vim25 type of the object it is read from.** DVPG paths (`config.defaultPortConfig.{securityPolicy.*, macManagementPolicy..., vlan}`, `config.policy.{securityPolicyOverrideAllowed, portConfigResetAtDisconnect}`), DVS paths (`config.networkResourceManagementEnabled`, `config.linkDiscoveryProtocolConfig.operation`, `config.defaultPortConfig.ipfixEnabled`, `config.vspanSession`) and cluster paths (`configurationEx.vsanConfigInfo.defaultConfig.{checksumEnabled, autoClaimStorage}`) all exist on their kind, **except one** (B1).
- `dvpg.network-restrict-port-level-overrides` checks 1 of about 7 override flags. It is already named in UNAUDITED_CONTROLS § Partial-coverage, so it is a documented gap, not a finding.

## BLOCKING

### B1. `vds.network-reset-port` (SCG 7.0 / 8.0 / 9.0) reads a portgroup-only field from the distributed switch

- **Where:** `profiles/canonical/scg_7.0.csv`, `scg_8.0.csv`, `scg_9.0.csv`, row `vds.network-reset-port`: `resource_kind = DistributedVirtualSwitch`, recipe `bool:config.policy.portConfigResetAtDisconnect`, scored. It generates `vcfcf_compliance_ctl_vds_network_reset_port` on `VmwareDistributedVirtualSwitch` (listed in both dashboards).
- **Authority:**
  - reviewer dimension 10 (a control mapped onto a non-existent field is BLOCKING);
  - the factory's own record that the field belongs to the portgroup: `knowledge/context/reviews/compliance-scg-benchmark-set-2026-08-25.md` W1 ("`bool:config.policy.portConfigResetAtDisconnect` is a DVPortgroupConfigInfo.policy field"), repeated in CHANGELOG build 56 item 2, which is why SCG 9.1 moved the control to `dvpg.network-reset-port`;
  - vim25 types: a DVS's `config.policy` is `DVSPolicy` (autoPreInstallAllowed, autoUpgradeAllowed, partialUpgradeAllowed), whereas `portConfigResetAtDisconnect` is on `DVPortgroupPolicy`.
- **What:** on every distributed switch scored against SCG 7.0, 8.0 or 9.0, the PropertyCollector read of that path fails or returns nothing. `readVimProperties` then folds it to UNREADABLE (`VSphereClient.java:579-582`). That is never a pass. But since build 63, unreadable counts as failing and raises the collection alert, so **every vDS permanently has `unreadable_count` 1, `non_compliant` 1, a lowered score, and an active "Compliance data not collected (distributed switch)" alert.** Its per-control alert can never fire. The recommendation sends the operator to check connectivity and permissions for a read that can never succeed.
- **Exposure:** prod was recorded on fixed `VMware_SCG_9.0` (recon log, 2026-07-01), and any Auto-mode vCenter at 7.0/8.0/9.0 is affected. Devel runs 9.1, which uses the portgroup id, so the devel acceptance plan would not catch it.
- **Why the build-70 sweep missed it:** it is not host-sourced or standard-switch; it is a DVPG field on the wrong distributed kind. Same class of defect as Codex P1 (a control read from the wrong object), with a false-alarm outcome instead of a false pass.
- **Fix (smallest correct):**
  - **Preferred:** re-home the 7.0/8.0/9.0 `vds.network-reset-port` rows to `DistributedVirtualPortgroup` in the normalizer drivers, the same recipe build 56 gave 9.1's `dvpg.network-reset-port`. This restores real coverage; the generator's one-kind-per-id rule still holds.
  - **Alternative:** add the three rows to `manual_review.csv`.
  - **Either way:** regenerate the alerts and check the dashboard lists (unchanged if re-homed, 142/32 if demoted). Extend the ProfileSetTest guard to reject any evaluable DVS row whose recipe path starts `config.policy.` with a field not on `DVSPolicy`, or better, a positive allowlist of the recipe paths valid per kind.
  - **Cleanup:** the existing values on vDS for this id are -1 (unreadable), which cleanup leaves alone. A re-homed or demoted id needs no flip, but the stale -1 and "(unreadable)" Actual will remain on each vDS.

## Still owed at install

CHANGELOG acceptance plan (a)-(h) including (e2), plus, after B1 is fixed, a check on a 9.0 benchmark (prod, or one devel instance set to fixed `VMware_SCG_9.0`) that no vDS raises the collection alert.

## If shipped as-is

The standard-switch false pass is gone and retained scores are now identifiable. But every distributed switch scored against SCG 7.0, 8.0 or 9.0, including prod's recorded fixed 9.0, shows as non-compliant with a permanent "Compliance data not collected" alert that no permission or connectivity fix can clear.
