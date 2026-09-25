# SDK Adapter Review: compliance builds 72-73 (reset-port moved to the portgroup)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Builds reviewed:** 72 `f74c918` (adapter + profiles), 73 `1575478` (dashboard lists), vs build 71 `280f927`; pak-compare vs build 56 `32de5aa`
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.73.pak`
- **Prior review:** `knowledge/context/reviews/compliance-build-71.md` (CHANGES REQUESTED, 1 BLOCKING)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING / 0 NIT

**Correction to the build-71 report:** the coordinator reports that live recon today found no compliance adapter installed on prod, so prod was not affected by B1. The build-71 exposure statement relied on the 2026-07-01 recon (prod on fixed SCG 9.0) and is superseded. The defect still applied to any 7.0 / 8.0 / 9.0 benchmark.

## Claims check (independently re-run, at build 73)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 7 Java suites, generator unittest 14/14, drift test 3/3. |
| `generate_compliance_alerts.py --check` | **Up to date.** 137 per-control alerts: vDS 4, portgroup 7. |
| describe.xml totals | **Confirmed:** 151 symptoms / 144 alerts / 141 recommendations. The only reset-port alert left is `vcfcf_compliance_ctl_dvpg_network_reset_port` on DistributedVirtualPortgroup. |
| Dashboard lists | **Confirmed:** 143 / 87 / 24 / 32; the retired vDS id is absent from all four and the portgroup id is present where expected. The drift test passes. |
| All five canonical profiles reproduce | **Confirmed.** I re-ran every driver (6.7, 7.0, and the new 8.0 / 9.0 thin drivers, 9.1) into scratch; each output is byte-identical to the committed CSV. |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...73.pak`; adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 1 WARNING / 38 INFO**, same as before (the known ComplianceWorld attribute retirement). |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Build-71 B1: closed

- **Profiles:** `scripts/_adapter_deltas.reset_port_to_portgroup` rewrites the 7.0 / 8.0 / 9.0 row to `dvpg.network-reset-port` on DistributedVirtualPortgroup, with the same read (`bool:config.policy.portConfigResetAtDisconnect`, a DVPortgroupPolicy field) and expected value. It is the 9.1 shape, so one portgroup alert covers 7.0-9.1.
- **Delta safety:** the delta fails loudly if the row is missing or its read changes, so a factory rename cannot silently leave the old mapping.
- **Content identity of the regenerated 8.0 / 9.0 CSVs, verified by parsing old against new:** same headers and row counts (7.0: 122, 8.0: 156, 9.0: 226). After normalizing CRLF inside fields, **exactly one row differs per profile** (control_id and resource_kind of the reset-port row).
  - The raw differences (8.0: 28 rows, 9.0: 64) are `\r\n` to `\n` inside quoted `description` fields (and in `parameter` on 1 / 5 rows).
  - **None of those rows is scored with a changed evaluation field** (parameter / expected_value / read_recipe / parameter_kind / value_type), checked with the generator's own `scored()` rule.
  - The only runtime effect is that the per-control `Description` property text loses a `\r` on those controls, which is cosmetic.
- **Cleanup:** `ComplianceDecisions.RETIRED_CONTROL_IDS` adds `vds.network-reset-port` to the vDS cleanup candidates. The only values it could ever have left on a switch are -1 (always unreadable there), so this is belt-and-braces. It is correct and tested.
- **Consequence:** vDS objects under 7.0 / 8.0 / 9.0 lose the permanent unreadable control, so their collection alert clears on the first build-72 cycle. Portgroups under those profiles gain one real scored control.

## The new read-path guard (ProfileSetTest field table)

- **Style rules:** esxcli and service_state on hosts only; vami on vCenter only.
- **Per-kind allowed paths,** each checked against the vim25 data object types:

| Kind | Table entries | vim25 check |
|---|---|---|
| DistributedVirtualSwitch | `config.defaultPortConfig.{securityPolicy.*, ipfixEnabled, vlan, macManagementPolicy.macLearningPolicy.enabled}`, `config.linkDiscoveryProtocolConfig.operation`, `config.vspanSession`, `config.networkResourceManagementEnabled` | Correct (VMwareDVSConfigInfo / DVSConfigInfo, VMwareDVSPortSetting). `config.policy.*` correctly absent (DVSPolicy). |
| DistributedVirtualPortgroup | the same `defaultPortConfig` set, plus `config.policy.{portConfigResetAtDisconnect, securityPolicyOverrideAllowed}` | Correct (DVPortgroupConfigInfo; DVPortgroupPolicy / VMwareDVSPortgroupPolicy). |
| ClusterComputeResource | `configurationEx.vsanConfigInfo.{enabled, defaultConfig.autoClaimStorage, defaultConfig.checksumEnabled}` | Correct (VsanClusterConfigInfo / ...HostDefaultInfo). |
| VirtualMachine | `config.{bootOptions.efiSecureBootEnabled, flags.enableLogging, ftEncryptionMode, migrateEncryption, version, hardware.device}` | Correct (VirtualMachineConfigInfo). |
| HostSystem | `config.{lockdownMode, firewall.defaultPolicy.incomingBlocked, dateTimeInfo.ntpConfig.server}` | Correct (HostConfigInfo). |
| HostSystem | `config.encryptionState.{mode, requireSecureBoot, requireExecuteInstalledOnly}` | **Not supported by evidence.** See W1. |

The guard achieves its purpose (the old reset-port read now fails it, and every scored row in every profile passes). But its table records one family of paths as vim25 fields against the factory's own live evidence.

## WARNING

### W1. The host `config.encryptionState.*` reads are allow-listed but read unreadable on a healthy, connected host

- **Where:**
  - `ProfileSetTest.ALLOWED_PATHS["HostSystem"]` lists `config.encryptionState.mode`, `.requireSecureBoot` and `.requireExecuteInstalledOnly`, attributed to HostConfigInfo.
  - These back `esx.tpm-configuration` (scored in 7.0 / 8.0 / 9.0 / 9.1), `esx.secureboot-enforcement` (8.0 / 9.0 / 9.1) and `esx.tpm-trusted-binaries` (9.0 / 9.1).
- **Authority:**
  - `knowledge/context/investigations/compliance_build46_golden_comparison.md` §3.2: on **mgmt-esx01, a healthy connected devel host**, all three read `(unreadable)`, in both the baseline and the v2 run.
  - `UNAUDITED_CONTROLS.md` already lists `config.encryptionState` only as an example of a path that "may not exist" on older hosts.
  - Skill § *Gaps, name them, never hide them*; reviewer dimension 10.
- **What:** either the path is not a HostConfigInfo field at all (the same class as B1), or it is unset on hosts without the feature and comes back null. Both read as UNREADABLE. Since build 63 every unreadable control counts as failing and raises the collection alert. So on devel, and anywhere else this holds, **every ESX host scored against 7.0 / 8.0 / 9.0 / 9.1 would carry 1-3 unreadable controls permanently**: `non_compliant` = 1, a lowered score, and an uncleareable "Compliance data not collected (ESX host)" alert. In the no-TPM case the honest SCG outcome is a *failure* (TPM not in use), not a collection failure. The new guard blesses these paths, so it will not catch this.
- **Why WARNING, not BLOCKING:** unlike B1, whether the field exists on the type is not settled by a type definition in the repo. The live evidence (build 46, June) predates the current reader and ESX 9.1.1. It is visible on devel immediately, not silent.
- **Fix:**
  - **Before release, acceptance:** read the Actual of `esx.tpm-configuration` / `esx.secureboot-enforcement` / `esx.tpm-trusted-binaries` on a connected devel host (build-73 install).
  - **If still `(unreadable)`:** either demote the three via `manual_review.csv` (like the standard-switch rows), or move them to the esxcli reader (`system settings encryption get` returns Mode / RequireSecureBoot / RequireExecutablesOnlyFromInstalledVIBs, and the host already has an esxcli channel). Then drop the three paths from the guard table, or annotate them with their live evidence.
  - **If they resolve:** record that evidence beside the table entry.
- **Registration candidate:** if confirmed unreadable at devel install.

## Still owed at install

CHANGELOG acceptance plan (a)-(h) including (e2), plus:
- W1's live read check;
- on a portgroup under a 7.0 / 8.0 / 9.0 benchmark, `dvpg.network-reset-port` resolves (not unreadable);
- no vDS under those profiles carries an unreadable reset-port control.

## If shipped as-is

The reset-port false collection failure on every distributed switch is gone, and portgroups gain the real control on 7.0 / 8.0 / 9.0. The remaining risk is W1: if devel still reads the three encryption controls as unreadable, every ESX host shows a permanent "Compliance data not collected" alert and non-compliance that no operator action clears.
