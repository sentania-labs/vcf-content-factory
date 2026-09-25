# SDK Adapter Review: compliance build 77 (SOAP faults on option reads)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 77, commit `05e6b9b`, vs build 76 `0273cc5`; pak-compare vs build 56 `32de5aa`
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.77.pak`
- **Prior review:** `knowledge/context/reviews/compliance-build-76.md` (CHANGES REQUESTED, 1 BLOCKING)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **CHANGES REQUESTED**
- **Findings:** 1 BLOCKING / 0 WARNING / 1 NIT

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 10 Java suites (new `Build77FaultTest`), generator unittest 14/14, drift test 3/3. |
| `generate_compliance_alerts.py --check` | **Up to date** (143 alert definitions, unchanged). |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...77.pak`; adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 2 WARNING / 38 INFO**, same as builds 75-76. |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Build-76 B1: mostly closed

- **QueryOptions** (host advanced settings, vCenter settings): `VimOptions.fromQueryOptions` throws `ReadFault` (with `lastFault`) when `post` returned null, i.e. any SOAP fault. An empty map now only comes from a successful response with no returnvals. **Closed.**
- **vCenter setting manager missing:** throws. **Closed.**
- **VM extraConfig:** a faulted call (`resp == null`) throws, and a response with no `returnval` throws. **But a successful response whose returnval carries no `propSet` for `config.extraConfig` still returns an empty map. See B1.**
- **Downstream:** the callers' existing catches fold to `evaluateControlsUnreadable`, so every advanced-setting control is pushed as -1 and excluded from the cleanup plan (tested).

## Focus areas

### A failed host listing now fails the cycle: no new harm

`getHosts` throws, so `collectWorld` throws before any other kind is walked. Consequences checked:
- **No partial writes:** no rollup push, no `Summary|last_scan_timestamp`, no stale-control cleanup (it runs after all collectors), and no `LastBenchmarkMemory.retain` (so memory is not trimmed on a partial inventory).
- **Status:** the world resource goes to ERROR via `mapCollectException`, which is a visible failure.
- **Stale values:** Ops keeps last cycle's values, the same as any failed cycle, and the next good cycle re-pushes everything.
- **Before build 77** the same fault produced an empty host list and a pushed rollup with `Rollup|Host|scored = 0`, a misleading number. Failing loudly is strictly better.

### Objects kept under their MOID when the name read fails: cannot mis-stitch

`nameOrMoid` substitutes `ref.value` and logs a WARN. The stitcher's `matchResource` tries the MOID index first, and that index has been scoped to the owning vCenter's instance UUID since build 51, so the object stitches exactly as before. On a MOID miss, the name fallbacks compare `host-12` / `vm-42` against display names. An exact match would need a VMWARE object literally named like a MOID, and the dot-prefix fuzzy match needs `host-12.`-shaped names. Neither is realistic, and both were reachable before for any name. The version map and `LastBenchmarkMemory` key on MOID, so they are unaffected. Objects are evaluated rather than silently dropped, which is the right trade.

### Other VSphereClient reads that could still map a fault to success

- **Inventory:** `createContainerView` / `listView` / member listing now throw. The bulk VM read (`retrieveViewRows`) returns null on a fault and falls back to `listView`, which throws; `collectVms` logs and skips. **Safe.**
- **Recipe reads:** a null becomes the UNREADABLE sentinel (`readVimProperties`). List styles (`list_empty`, `vm_hardware_device_absent`) require a confirmed container, so a failed fetch is UNREADABLE, never "empty / absent". `vlan_id_not` returns null on a missing node. **Safe.**
- **Other null-returning reads:** `hasVsanConfig` throws on null `configurationEx` (build 74); the OptionManager MoRef raises `AdvancedSettingsUnreadableException`; `getHostProductVersion` / `getVmHostMoid` give "version unreadable" (build 58/65 rules); `getHostConnectionState` gives unknown, after which the settings read now throws. **Safe.**
- **Remaining gap:** `VimOptions.fromPropertyOptions` treats "object present, property not in propSet" as "unset". See B1.

## BLOCKING

### B1. VM extraConfig: a returnval without the property is still read as "nothing set", which passes the "or Undefined" controls

- **Where:** `VimOptions.fromPropertyOptions` (`:75-95`), the final `return out;   // property unset on the object: read OK, nothing set`, used by `VSphereClient.getVmExtraConfig`.
- **Authority:** skill § *Unreadable is NOT compliant*; the build-76 B1 fix requirement ("empty only for a successful, genuinely empty read"); vim25 `ObjectContent.missingSet` (per-property faults such as NoPermission are returned *inside* a successful RetrieveProperties response, not as a SOAP fault).
- **What (probed):** I compiled `VimOptions` and fed it two HTTP-200 responses:
  1. a returnval whose `missingSet` names `config.extraConfig` with a `NoPermission` fault;
  2. a returnval with the object and no `propSet` at all, the shape expected when the property is unset, for example an **inaccessible or orphaned VM** whose `config` is unset.

  **Both return `{}`** (no exception). The evaluator then passes every "X or Undefined" VM control (12-13 per VM in SCG 7.0-9.1, counted from the profiles) and skips the rest. Since build 76 the skipped ones also have their real 0/1 retired to -1. So an inaccessible VM, or a VM whose extraConfig the account cannot read, **scores as mostly compliant from a read that returned no data**. This is the same defect B1 was opened for, through the one door the fix left open. `Build77FaultTest` asserts the "no propSet" case as a legitimate empty map, so the gap is baked into the test.
- **Why the empty case is not needed:** a readable VM always carries `config.extraConfig` entries (vCenter populates at least the core keys). A returnval with no propSet for the path means vCenter did not give the value, not that the VM has none.
- **Fix:**
  - In `fromPropertyOptions`, when no `propSet` matches `propPath`, throw `ReadFault`, including the `missingSet` fault type when present. Keep the empty map only for a present `propSet` whose `val` has no items.
  - Update `Build77FaultTest`: missingSet gives ReadFault; no propSet gives ReadFault; propSet with empty val gives an empty map.
  - The VM path then folds to UNREADABLE (-1 pushed, not a pass, excluded from cleanup).

## NIT

- **N1.** When a non-host inventory kind fails to list (VMs, vDS, portgroups, clusters are caught and skipped by design), the cycle still pushes the per-vCenter rollup, with that kind at `scored` 0 and `avg_score` omitted, so `Rollup|All` and the environment super metrics under-count for that cycle. This is pre-existing (before build 77 the fault produced an empty list with the same effect) and it is logged. Since a host-listing failure now fails the cycle loudly, consider skipping the rollup push (or flagging it) when any kind's listing failed, so one cycle's environment average cannot silently drop a whole kind.

## Still owed at install

CHANGELOG acceptance plan (a)-(h), (e2), (i)-(iv); the non-vSAN cluster -1 check; and, after B1, confirm that an inaccessible VM (if devel has one) reports unreadable VM settings rather than a score.

## If shipped as-is

SOAP faults on host, vCenter and VM settings reads now correctly surface as unreadable, and a failed host listing fails the cycle visibly. But a VM whose extraConfig vCenter does not return (an inaccessible or orphaned VM, or a property-level permission fault) still passes its "or Undefined" controls and has its real failing controls set to "not evaluated".
