# SDK Adapter Review: compliance builds 66-68 (ESX rename, vCenter-only scope pickers)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Builds reviewed:** 66 `c5f9c48` (docs), 67 `3e61a29` (docs), 68 `b87bacb` (content + labels), vs build 65 `d293a57`; pak-compare vs build 56 `32de5aa`
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.68.pak`
- **Contract:** owner direction verbatim in `knowledge/designs/sdk-adapters/compliance-v3-version-aware.md` § "Owner change after seeing devel": pickers list only vSphere World and vCenters; "change all references to ESXi to ESX" in authored strings. Vendor SCG text, metric keys, ids and file names are unchanged.
- **Known open, not a finding:** FB-021 (`column_preset: name-only` renders all default columns in the Ops UI; owner decision pending).
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 3 NIT

## Claims check (independently re-run, at build 68)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 7 Java suites, generator unittest 13/13, dashboard alert-list drift test 3/3. |
| `generate_compliance_alerts.py --check` | **Up to date.** |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...68.pak`. Bundled 4 SMs / 8 views / 4 dashboards; the host dashboard now renders as "[VCF Content Factory] Compliance ESX Hosts". Adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 1 WARNING / 38 INFO**, same as builds 61-65 (the known ComplianceWorld attribute retirement). |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Builds 66 and 67 (docs only)

- **Build 66** closes build-65 N1: `docs/overview.md` now says that on a disconnected or version-unreadable host both "Compliance data not collected" and the Critical "Host Compliance Score Degraded" alert (score 0) are expected, and both clear on reconnect.
- **Build 67** states all 151 alert definitions (144 + 6 + 1) in one overview row, matching describe.xml.
- Neither build changes code or content.

## Scope pickers and interactions (rendered `dashboard.json` inspected)

- **Pickers:** ESX Hosts, VMs and vCenter & Networking each render the ResourceList filter over exactly two kinds, `resourceKind:id:0` = vSphere World and `id:1` = VMwareAdapter Instance, with `selectFirstRow: true`. ClusterComputeResource and HostSystem are gone from the pickers.
- **ESX Hosts** keeps HostSystem and ClusterComputeResource in its kind table only for the heatmap (subject HostSystem, grouped by cluster), which is correct.
- **Interactions still resolve:**
  - ESX Hosts: Scope to Host Compliance view and to Host Score Heatmap; view to AlertList / MetricChart / PropertyList (5 edges, unchanged).
  - VMs: Scope to VM Compliance view; view to AlertList / PropertyList / MetricChart (4 edges).
  - vCenter & Networking: 8 edges, unchanged.
  - Overview: 1 edge.
- **Why the trimmed kinds still work:** a View widget lists descendants of its subject kind under the received resource, and the heatmap is `mode: all, depth: 10`. A World or vCenter selection still reaches every host and VM beneath it (the vCenter-to-host path is well within depth 10), so dropping the Cluster and Host picks only removes finer scopes, as the owner asked. The design tables (`compliance-esxi-hosts.md`, `compliance-vms.md` W1) were updated to match.

## "ESXi" to "ESX" sweep

`git grep ESXi` over the adapter repo, excluding CHANGELOG history and the vendor source and canonical CSVs:

- **describe.xml:** zero hits.
- **resources.properties:** every remaining hit is in the per-control range (nameKeys 1001-1389): SCG control titles and PowerCLI remediation quoted from the guides (for example `Get-VMHost -Name $ESXi`, `UserVars.ESXiShellTimeOut`). These are vendor-quoted and correctly unchanged. The adapter-authored strings are changed: collection alert and symptom names (2000-2025), the shared collection recommendation (2100), and the score recommendations (104, 105).
- **Remaining authored-file hits:**
  - SCG 6.7 Guideline IDs (`ESXi.set-account-lockout`, ...) in `normalize_scg_v67.py` and `CANONICAL_SCHEMA.md:388`: vendor ids, correctly unchanged.
  - `normalize_scg_v70.py:30`, "VMware ESXi" as the source's product name: vendor value.
  - `normalize_scg_v70.py:73,212`: two authored code comments. See N2.
- **Factory design notes:** remaining "ESXi" occurrences are all inside verbatim owner quotes, which is correct.

## profile_name label consistency

- `BenchmarkSelector.PRODUCT_ESXI` now has the value `"ESX"`; the identifier name is kept, which is fine since it is not user-facing. The pushed labels are therefore "no benchmark for ESX X.Y" and "benchmark unknown: ESX version unreadable".
- README lines 52/57, the BenchmarkSelector javadoc, `BenchmarkSelectorTest` (lines 37, 41, 52, 66) and `ComplianceDecisionsTest:41` all use the new text.
- No code parses these labels. `LastBenchmarkMemory` stores the profileName, and `decide()` looks it up by name in the loaded profiles, where a label never matches. So the label change cannot alter behavior.
- Objects keep an old "ESXi" label in Ops only until their next push.

## NIT

- **N1.** `knowledge/designs/sdk-adapters/compliance-v3-version-aware.md:268`, "Effect:" line: the bulk replace also hit the rule it describes, so it now reads `"ESX" becomes "ESX"`. It should read `"ESXi" becomes "ESX"`. The file is orchestrator-owned and uncommitted in the factory tree; fix it before commit so the design record states the rule.
- **N2.** `scripts/normalize_scg_v70.py:73` ("the ESXi advanced option") and `:212` ("# Delta 7: ESXi option key case") are authored comments, not vendor text, that still say ESXi. Developer-only scripts, never shipped or shown to operators, but the owner said "all references".
- **N3.** The host dashboard was renamed ("Compliance ESXi Hosts" to "Compliance ESX Hosts") with its id and file name unchanged. Nothing proves whether a pak upgrade on devel (which has the ESXi-named dashboard from the earlier install) replaces it by id or leaves a second, stale "ESXi Hosts" copy. Add to the CHANGELOG acceptance plan, next to item (e): after the upgrade, confirm only "Compliance ESX Hosts" exists. Removing a leftover needs the owner's verbatim go.

## Still owed at install

CHANGELOG acceptance plan (a)-(g) as extended through build 66, FB-021 (owner decision), and N3.

## If shipped as-is

Pickers offer only vSphere World and vCenters and still drive every list, heatmap and alert pane. Every adapter-authored label reads "ESX", while SCG-quoted titles and runbooks keep the vendor's "ESXi". The only unverified effect is whether devel keeps a stale "ESXi Hosts" copy of the renamed dashboard after the upgrade.
