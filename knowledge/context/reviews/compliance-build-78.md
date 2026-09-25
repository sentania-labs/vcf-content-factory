# SDK Adapter Review: compliance build 78 (extraConfig not returned; rollup held back on failed listings)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 78, commit `b8e8735`, vs build 77 `05e6b9b`; pak-compare vs build 56 `32de5aa`
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.78.pak`
- **Prior review:** `knowledge/context/reviews/compliance-build-77.md` (CHANGES REQUESTED, 1 BLOCKING / 1 NIT)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING / 0 NIT

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 10 Java suites (`Build77FaultTest` extended), generator unittest 14/14, drift test 3/3. |
| `generate_compliance_alerts.py --check` | **Up to date** (143 alert definitions, unchanged). |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...78.pak`; adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 2 WARNING / 38 INFO**, same as builds 75-77. |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Build-77 B1: closed (re-probed)

I recompiled the build-78 `VimOptions` against the same two HTTP-200 fixtures that returned `{}` in the build-77 review:
- a `missingSet` NoPermission on `config.extraConfig` now throws `ReadFault: config.extraConfig not returned (fault NoPermission)`;
- a returnval with no propSet now throws `ReadFault: ... not returned (unset: inaccessible or orphaned object)`.

A propSet with no `<val>` also throws. Only a present value with no items gives an empty map. `getVmExtraConfig` throws into the existing VM catch, so every VM advanced-setting control is UNREADABLE (pushed -1, no pass, excluded from cleanup). `Build77FaultTest` now asserts all four shapes. The false-pass path opened in build 44 is fully closed across QueryOptions, vCenter settings and VM extraConfig.

## Build-77 N1: closed as designed, with a new consequence (W1)

- **What changed:** `ComplianceRollup.markIncomplete` is called from each of the four listing catches (VM, vDS, portgroup, cluster). `toStats` then omits that kind's `Rollup|<K>|*`, `Rollup|All|*` and every `Rollup|Benchmark|*|objects` key, while still pushing the complete kinds. The adapter logs a WARN naming the kinds each cycle, and `docs/overview.md` states the behavior.
- **The author's reasoning is sound for a one-cycle blip:** a flagged under-count would still be summed by the environment super metrics, while an omitted key keeps its last good value.
- **The consequence:** see W1.

## WARNING

### W1. If a listing keeps failing, the held-back rollup freezes indefinitely, and only the adapter log says so

- **Where:** `ComplianceRollup.toStats` (omission on `incomplete`); `ComplianceAdapter.pushRollup` and the four listing catches; `docs/overview.md` ("The adapter log names the kinds").
- **Authority:** skill § *Unreadable is NOT compliant* (a stale value must not read as current); build-57 W2 / build-58 owner rule (a retained value must be identifiable by the operator); reviewer dimension 11.
- **What:** omission is right for one bad cycle. But nothing bounds it. A *persistent* listing failure, for example a permission change on the VM folder or a vCenter bug on one container view, means:
  - `Rollup|All|*` and `Rollup|Benchmark|*|objects` are never pushed again for that vCenter, and neither is `Rollup|VM|*`;
  - Ops keeps the last good values, so the Environment Overview tiles, the Average Score trend and the by-vCenter / by-SCG views show a **frozen** number as current for days or weeks, while the real posture of that vCenter's hosts, clusters and switches (which are still evaluated) moves on unseen in the `All` figures;
  - the collection cycle itself succeeds, so the world resource stays green, no alert fires, and nothing on any dashboard changes;
  - the only signal is a WARN line in the collector log.

  Before build 78 a persistent failure was at least visible as `Rollup|VM|scored = 0`.
- **Fix (either works; the first keeps the author's design):**
  1. **Surface it.** Push an always-present 0/1 metric every cycle, for example `VCF-CF Compliance|Rollup|incomplete` (and / or `Rollup|<K>|listing_failed`). Being pushed every cycle, it can never go stale itself. Show it in the "Compliance by vCenter" view (a column beside No Benchmark), and optionally give it a symptom/alert on the VMwareAdapter Instance ("Compliance inventory incomplete"). Update overview.md to say where to look.
  2. **Bound it.** After N consecutive incomplete cycles (for example 3), push the under-count anyway. This reuses the rollup keys so dashboards change visibly. It is simpler, but loses the author's summation argument.

## Still owed at install

CHANGELOG acceptance plan (a)-(h), (e2), (i)-(iv); the non-vSAN cluster -1 check; if devel has an inaccessible VM, confirm it reports unreadable VM settings rather than a score.

## If shipped as-is

Every read-failure path now surfaces as unreadable, never a pass, and a one-cycle listing blip no longer distorts environment totals. If a VM, vDS, portgroup or cluster listing fails persistently, that vCenter's environment-level compliance numbers freeze at their last good values with no dashboard or alert signal. Only the collector log shows it.
