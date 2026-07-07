# SDK Adapter Review — vcommunity build 6

- **Adapter:** `content/sdk-adapters/vcommunity` (uncommitted working tree; HEAD is build 3, working tree is cumulative 3→6 — review-before-commit gate)
- **Build reviewed:** 6 (`vcfcf_sdk_vcommunity.1.0.0.6.pak`)
- **Reviewer:** `sdk-adapter-reviewer`
- **Ground truth:** the prod original `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/` — `app/adapter.py` (credential/identifier/enum definitions) + `app/constants/main.py` (key constants) + `content/symptomdefs/` (symptom UUIDs). The original is a Python/Cloud-native MP with **no static describe.xml** (it builds the describe at runtime via `AdapterDefinition`), so the credential/config keys come from `adapter.py`, not a describe.xml.
- **Reference impl:** `content/sdk-adapters/compliance/` (pak-compare baseline)
- **Verdict:** **APPROVE** (zero BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 2 NIT

## Independent claims verification (re-run, not trusted)

| Claim | My result | Status |
|---|---|---|
| validate-sdk passes | `OK: ... valid Tier 2 SDK adapter project`, 9 sources, only `-source 11` warning | **CONFIRMED** |
| build-sdk produces 1.0.0.6 pak | Built `dist/vcfcf_sdk_vcommunity.1.0.0.6.pak` | **CONFIRMED** |
| pak counts: 37 SM / 96 view XML / 12 dashboard / 2 symptomdef / 6 solutionconfig | Extracted pak: SM 37, view XML 96 (one `content.xml` per `content/reports/<n>/`), dashboard JSON 12, symptomdef 2, solutionconfig 6 | **CONFIRMED (exact)** |
| inner describe.xml has exactly one CredentialKind `vsphere_user` | `adapters.zip → vcfcf_vcommunity/conf/describe.xml`: 1 `<CredentialKind key="vsphere_user">`, fields `user`/`password`/`winUser`/`winPass`, `host` (string) / `port` (integer) | **CONFIRMED** |
| pak-compare vs compliance = 0 BLOCKING | `Score: 0 BLOCKING, 2 WARNING, 286 INFO` — the build-1 BLOCKING (CredentialKind 2 vs 1) is **eliminated** by collapsing to one kind. W1 (CredentialField 4 vs 2) and W2 (identifier 11 vs 4) are reference-topology divergence, matching the original ground truth (4 cred fields, 11 identifiers) — same accepted divergence as build 1. | **CONFIRMED** |
| defect-gate clean | `no open blocking defects affecting vcommunity` | **CONFIRMED** |

Build metadata correct: `adapter.yaml build_number: 6`, `version: 1.0.0`, CHANGELOG `1.0.0.6 (2026-06-17)` entry present and accurate.

## Registry check (context/defects.md)

- **No open defect names `vcommunity` in `Affects:`.** DEF-001 (synology), DEF-002 (unifi, open), DEF-003 (synology, closed) — none affect this pak. `defect-gate --pak vcommunity` independently confirms: "no open blocking defects affecting vcommunity." Nothing to re-assert.

## A — Credential / config / monitoring rework — VERIFIED SAFE

### A.1 Credential read correctness — SAFE
describe.xml declares one `CredentialKind key="vsphere_user"` with fields `user`/`password`/`winUser`/`winPass` — byte-for-byte the original's `app/adapter.py:118-122` (`USER_CREDENTIAL="user"`, `PASSWORD_CREDENTIAL="password"`, literal `winUser`/`winPass`). The Java reads all four by exact key from the single bound credential: `VCommunityAdapter.java:133-136` calls `getCredentialField(rc, "user"/"password"/"winUser"/"winPass")`. The base `VcfCfAdapter.getCredentialField` (`vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/VcfCfAdapter.java:983-992`) reads `resourceConfig.getResourceCredential()` (the ONE bound credential, kind-agnostic) and matches by `fieldKey.equals(f.getKey())`. **No key-name mismatch — every field the dialog collects is read.** The old two-kind shape left the Windows credential with no binding slot; the collapse fixes a real "Windows-cred-never-received" defect, not introduces one.

### A.2 Monitoring-gate semantics — SAFE (unreadable-is-NOT-on upheld)
`VCommunityConfig.WindowsMonitoring.from(svc, evt)` (`VCommunityConfig.java:38-50`) gates each toggle through `isEnabled(raw) = raw != null && "Enabled".equalsIgnoreCase(raw.trim())`. **null / blank / garbage → false → gate OFF.** Only the literal word "Enabled" (case-insensitive) turns a gate on; `services()`/`eventLogs()` derive from the resulting enum. Defaults in describe.xml are `Disabled` for both enums, matching the original (`adapter.py:100,109`). Guest-ops is then **triple-gated**: `buildGuestOps()` returns null unless `windowsMonitoring != DISABLED` AND `hasWindowsCredential()` (`VCommunityAdapter.java:413-416`); `VmCollector.collect:64-66` requires `windowsMonitoring != DISABLED` AND `hasWindowsCredential()` AND `guestOps != null && guestOps.ready()`. There is no path where unset/unreadable monitoring starts guest-ops, and none where a missing Windows credential silently runs it. Behavior preserved vs the old single enum.

### A.3 describe.xml validity / key consistency — SAFE
- All 30 distinct `nameKey` values in describe.xml (1-16, 20-31, 40, 41) resolve 1:1 in `resources/resources.properties` — **no missing key → no raw-key fallback** (the original sin from earlier builds is gone). `.description` help text present for the 11 identifier keys (6-16); credential-field/kind keys correctly have no `.description` (the classic describe schema only renders identifier help text — confirmed by the describe.xml header comment).
- `host` rename consistent everywhere: describe.xml `ResourceIdentifier key="host"`, Java `getIdentifier(rc, "host")`. `port` is `type="integer"` default 443.
- **No dangling old keys.** Grep across all `.java`/`.xml`/`.properties`/`.yaml` for `vcenter_host` / `windows_monitoring` / `windows_guest_credentials` / `vcenter_credentials` returns zero hits in source.

### A.4 Crash-the-cycle / describe path — SAFE
The no-arg constructor supplies the static `ADAPTER_KIND="vcfcf_vcommunity"` (`VCommunityAdapter.java:66-68`); the describe path uses `getAdapterDescribeFile(ADAPTER_KIND, "describe.xml")` (`:167`), never `getAdapterKind()` or any injected-state accessor — compliant with `lessons/controller-describe-bare-instantiation.md`. The credential/identifier reads (`buildConfig`) are in the collect path, not describe. This rework did not touch the describe path.

### Secrets-in-logs (RULE-008 / no-secrets-on-disk) — CLEAN after rework
The new config-summary log line (`VCommunityAdapter.java:118-122`) logs `winCred=<boolean>` (presence only, via `hasWindowsCredential()`) — never a credential value. No `log*` / exception / URL construction line touches `password`/`winPass`/`winPassword`. The credential rework introduced no leak.

## B — Content-import fix (symptomdef ID → UUID) — VERIFIED SAFE
- Symptom YAMLs carry the original's UUIDs as `id:`: `symptoms/esxi-host-nic-disconnected.yaml:1` = `c8d1e671-d0ea-489f-acc4-46e34cc246b6`; `symptoms/windows-service-down.yaml:1` = `7675759b-2ca0-4847-87ed-e3e23acdf7a5`. Both match the original `reference/references/.../symptomdefs/*.xml` exactly (`SymptomDefinition-c8d1e671-...` NIC HostSystem; `SymptomDefinition-7675759b-...` Windows Service VirtualMachine).
- The emitter consumes `id:` — the built pak's `content/symptomdefs/*.xml` carry `id="SymptomDefinition-c8d1e671-..."` and `id="SymptomDefinition-7675759b-..."`. An alertdef referencing these UUIDs would resolve to the same symptomdef on import.

## NIT
- **[VCommunityVSphereClient.java:584-600] — guest-OS property-key rename to original canonical names.** Build 4/5 (folded into this working tree) renamed `vmGuestOsInfo` output keys `Name`→`OS Name`, `BuildNumber`→`OS BuildNumber`, `Version`→`OS Version`, `Release ID`→`OS Release ID`, `Last Boot Up Time`→`OS Last Boot Up Time` to match the prod original's property names so ported content finds data. Safe-by-construction: absent keys still skip (no sentinel — unreadable-is-not-a-value preserved), doc comment updated. Not part of the build-6 credential/symptom changes the brief enumerated, but in scope for "what ships" since HEAD is build 3 and the working tree is a cumulative 3→6 diff. Worth the orchestrator noting that builds 4 and 5 were never committed as discrete review points.
- **[pak-compare W1/W2] — reference-topology divergence, ACCEPT.** CredentialField 4 vs 2 and identifier 11 vs 4 vs the minimal compliance reference are the design-mandated original shape (vCenter + Windows creds; host + 6 config files + 2 enums + port + allowInsecure), verified against `app/adapter.py`. Same accepted disposition as build 1. Not install defects; 0 BLOCKING.

## Failure-mode hunt — cleared (rework surface only; full read-path hunt was build 1)
- **Unreadable-is-NOT-on / -compliant:** the monitoring gates and guest-OS reads both uphold it (A.2, NIT-1). No failed/missing read folds into "on" or a sentinel.
- **Key-name mismatch (silent cred-ignored):** ruled out — describe.xml field keys ↔ Java reads ↔ original constants all agree (A.1).
- **describe-path crash:** ruled out — static-constant kind, no injected accessor (A.4).
- **Secrets on disk:** ruled out — presence-boolean only (A.3/RULE-008).
- The full build-1 hunt (vim25 reflection-tolerance, canonical CSV header-name parsing, stitching MOID, resource hygiene) is unchanged by this rework; build 1's clearances stand. The build-1 WARNING (bare-MOID stitch in multi-vCenter, a corpus-wide item shared with the shipped compliance reference) is untouched by build 6 and remains a tracked corpus item, not a vcommunity-specific blocker — no registry entry was graduated for it.

## If shipped as-is
An operator installs cleanly with **one** credential dialog ("vCenter Credential") that collects vCenter user/password (required) plus optional Windows user/password — and the adapter actually reads all four, fixing the prior two-kind shape where the Windows credential had no binding slot. Windows guest-ops stays OFF unless the operator explicitly sets a monitoring enum to "Enabled" AND supplies a Windows credential; an unset/garbage enum or a missing credential never starts guest-ops against Windows VMs. The two symptom definitions import under the original's UUIDs, so a ported alertdef referencing them resolves. The only latent risk is the pre-existing multi-vCenter bare-MOID stitch shared with the compliance reference (build-1 WARNING), unchanged here.
