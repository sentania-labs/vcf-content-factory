# SDK Adapter Review: compliance build 76 (per-object cleanup plan, VAMI absent default)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 76, commit `0273cc5`, vs build 75 `ba636f6`; pak-compare vs build 56 `32de5aa`
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.76.pak`
- **Prior review:** `knowledge/context/reviews/compliance-build-75.md` (APPROVE, 1 WARNING / 1 NIT)
- **Owner decisions since:** `read_appliance_settings` ships default off; no SSO grant in the lab for now.
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **CHANGES REQUESTED**
- **Findings:** 1 BLOCKING / 0 WARNING / 0 NIT

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 9 Java suites (new `Build76CleanupAbsentTest`), generator unittest 14/14, drift test 3/3. |
| `generate_compliance_alerts.py --check` | **Up to date** (143 alert definitions, unchanged). |
| Profiles reproduce | **Confirmed** for 7.0 / 8.0 / 9.0 / 9.1. Only the four root-password rows change, to `...max_days_between_password_change?absent=-1`. |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...76.pak`; adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 2 WARNING / 38 INFO**, same as build 75 (the intended `read_appliance_settings` identifier and the known ComplianceWorld retirement). |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Build-75 closures

- **W1, stale values on non-applicable controls:** closed for the vSAN case.
  - `ComplianceDecisions.cleanupPlan` builds `zeroOrOne` = the current benchmark's evaluated controls for the kind minus the ids actually pushed this cycle (`pushedIds(cr)`), and `zeroOnly` = the build-59 candidate set minus pushed ids minus `zeroOrOne`.
  - `staleControls` retires 0 or 1 on `zeroOrOne` and only 0 on `zeroOnly`. It reads values back first, never creates keys, and does nothing when the read-back fails.
  - A non-vSAN cluster (`emptyResult`, nothing pushed) now gets its old `cluster.managed-disk-claim` 1 or 0 retired to -1, as requested. Tested.
- **N1, root password never expires:** closed.
  - `VamiRecipe` `<field>?absent=<value>` applies only when a **successful 200 JSON-object** body lacks the field (or has it as JSON null). HTTP, session and non-object failures stay UNREADABLE. The option is rejected on `(value)` / `(list)`, and an empty default is rejected as malformed.
  - It is used only on the four root-password rows, per the vendor spec. A permission problem on that endpoint surfaces as 401/403, not as a 200 without the field, so it cannot be mistaken for "never expires".

## The widened cleanup: can a legitimately evaluated control have a real 0/1 wrongly retired?

Walked every path that reaches `afterPush` with its `pushed` set:

| Situation | Controls pushed? | Retire risk |
|---|---|---|
| Unreadable control (vim / esxcli / VAMI) | Yes, as `ControlResult(unreadable)` (-1) | None: pushed ids are excluded. |
| Whole host unreadable (disconnected, OptionManager MoRef null) | Yes: `evaluateControlsUnreadable` + `unreadableVimResult` emit every attempted control | None. |
| Host / VM / vCenter settings read **throws** | Yes: folded to `evaluateControlsUnreadable` | None. |
| vSAN probe fails | Yes: `unreadableVimResult` | None. |
| Version unreadable, no history | No `afterPush` call at all (no cleanup) | None. |
| Version unreadable, previous benchmark reused | Normal evaluation | None. |
| Instance edit / collector restart | Plan uses only this cycle's push (no history) | None. |
| Advanced setting **absent** from a **successful** read, no "or Undefined" default | Not pushed, so it lands in `zeroOrOne` | Correct **only if "absent" really means the read succeeded.** It does not always. See B1. |

## BLOCKING

### B1. A SOAP fault on the settings reads comes back as an empty "successful" map. It already caused false passes; build 76 now also retires real 0s and 1s

- **Where:**
  - `VSphereClient.queryOptions` (`:450-471`): `Document resp = post(...); if (resp == null) return result;` returns an **empty map**. `post()` returns null on any non-2xx, i.e. every SOAP fault (`:1390-1394`, `// SOAP fault (500) / auth failure -> null upstream`). This backs host advanced settings (`getAdvancedSettings`, non-null OptionManager) and vCenter settings (`getVCenterAdvancedSettings`).
  - `VSphereClient.getVmExtraConfig` (`:423-438`): `getRawPropertyElement` returns null when `retrieveProperties` hit a fault, which becomes `if (val == null) return result;`, an **empty map**.
  - Consumers: `ControlEvaluator.evaluateControls` `:150-161` (absent key: "or Undefined" is a **pass**, otherwise `continue`); build-76 `cleanupPlan` (unpushed means retire 0 or 1).
- **Authority:**
  - skill § *Unreadable is NOT compliant* ("a read that finds nothing must never become a pass");
  - `knowledge/lessons/unreadable-is-not-compliant.md`;
  - `knowledge/context/investigations/compliance_esx04_partial_collection_2026_06_10.md` (the "empty-adv-map" regression that builds 47/48 guarded only for the null-MoRef case);
  - CHANGELOG build 57 item 9, which claims the VM extraConfig failure path was fixed. The *exception* path was fixed; the *fault* path was not.
- **What:** a SOAP fault on these reads (for example a host that stops responding after the connectionState check, `ManagedObjectNotFound` on a VM being removed or reregistered, an `InvalidState`, a session that faults instead of dropping) is indistinguishable from "read OK, keys not set".
  1. **Existing false pass:** every VM "or Undefined" control **passes**. That is 12-13 controls per VM in 7.0-9.1 (counted from the profiles with the generator's scored rule). Only the vim reads can pull the score down. The host is the same class: about 30 host advanced-setting controls silently drop, leaving a flattering partial score from the few vim/esxcli reads. That is the build-46 esx04 regression, reachable again whenever QueryOptions faults on a live MoRef.
  2. **New in build 76:** every non-Undefined advanced-setting control on that object is now "not pushed" and joins `zeroOrOne`. Its real **0 is retired to -1, closing a valid per-control alert and hiding a failure for that cycle**, and a real 1 is likewise wiped. The next good cycle re-pushes the 0, so the alert flaps closed and open. That is exactly the scenario the brief asked about.
- **Fix (smallest correct, closes both):**
  - Make the failed call distinguishable from an empty success. `queryOptions` should throw when `post` returned null (message including `lastFault`). `getVmExtraConfig` should throw when `retrieveProperties` returned null, meaning the call faulted, while still returning an empty map when the call succeeded and the property is genuinely empty or absent. `lastFault` is already recorded for exactly this. A small `retrieveProperties`-level "call failed" signal is cleaner than inferring it from a null `<val>`.
  - The existing catches then fold these to UNREADABLE (host: `advUnreadable` / `evaluateControlsUnreadable`; VM: `evaluateControlsUnreadable`; vCenter: same). The controls are then *pushed* as -1, so the cleanup never touches them, and "absent" once again only means "read succeeded, key not set".
  - Treat the vCenter `settingOptionMgr == null` returning an empty map the same way.
  - Add tests: a faulted QueryOptions / extraConfig read yields unreadable (not pass, not skip), and a faulted read leaves a stored 0 untouched by cleanup.

## Still owed at install

CHANGELOG acceptance plan (a)-(h), (e2), (i)-(iv), plus: on the non-vSAN wld01 / wld02 clusters, `cluster.managed-disk-claim` and `cluster.object-checksum` read -1.

## If shipped as-is

Non-vSAN clusters get cleaned correctly and a never-expiring root password reads compliant once appliance reads are enabled. But any transient SOAP fault on a host's or VM's settings read scores the object as if its settings were unset. VMs pass their "or Undefined" controls, hosts get a flattering partial score, and from this build the object's real failing controls are set to "not evaluated", so their alerts close until the next good cycle.
