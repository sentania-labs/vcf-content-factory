# SDK adapter review: compliance build 87

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-05 (local, America/Chicago)
- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/environment-computed-metrics`, base `main` at `0a7d539`, uncommitted working tree carrying builds 86 and 87)
- **Artifact reviewed:** `dist/vcfcf_sdk_compliance.0.0.0.87.pak` (built 11:10 AM), sha256 `c02671aecb4293b3c104a3262f734f592261dc63f962915b62684c9e7980d6cf` (confirmed). Reference: `dist/vcfcf_sdk_compliance.0.0.0.86.pak`, sha256 `a3bf49f98afa1eea901a59577998fe641a92dc6e0f11dfaad9537db6b310f5de` (confirmed, unchanged since the build 86 review).
- **Prior pass:** `compliance-build-86.md` (APPROVE, 3 W / 4 N)
- **Verdict:** APPROVE (0 BLOCKING / 0 WARNING / 1 NIT)
- **Fit for a devel install: YES**, once Scott's go is recorded (`knowledge/context/approvals/` has 84 and 85 only; 86 was never installed, so the devel upgrade is 85 to 87 and carries every build 86 change).

## Bottom line

The delta is what the brief says: logging and docs only. Against 86, the pak differs in four adapter classes plus line tables and version stamps; `describe.xml`, both `resources.properties`, the framework jar, views, reports and dashboards are byte-identical. All six build 86 findings assigned to the author (W1, W2, N1 to N4) are closed, and W3 is closed by registration as DEF-022, which now makes `defect-gate` refuse a compliance release, as it should. The new once-per-cycle WARN cannot leak across cycles or instances. The `cross_mp_edges` entry is accurate and is documentation only: the framework reads it in `docs_gen.py` and nowhere else, and the shipped `describe.xml` is unchanged. One NIT, owned by `tooling`: the framework's generated Cross-MP section brings em-dashes into the compliance docs.

## Independent verification

| Check | Result |
|---|---|
| Pak checksums | 87 `c02671ae...d6cf`, 86 `a3bf49f9...10f5de`, both match |
| `validate-sdk content/sdk-adapters/compliance` | OK (only the existing `-source 11` options warning) |
| `ci/run_java_tests.sh` | 12 Java suites pass (`EnvironmentKeyContractTest` "4 computed keys, 5 metric references"); alert generator 16 tests OK and "up to date" (136 + 6 + 1 = 143 alerts); dashboard alert lists 3 tests OK |
| `build-sdk` into scratchpad | reproduces `vcfcf_sdk_compliance.0.0.0.87.pak`. Unpacked recursively against the author's pak: every file identical except `overview.packed`, whose unpacked contents are identical (zip timestamps). Adapter working tree unchanged by the build (status and diff hashes identical before and after). |
| `pak-compare` 87 vs 86 (author's pak and mine) | gate PASS, **0 BLOCKING / 0 WARNING / 0 INFO**, "No structural divergences found" |
| 86 vs 87 file diff (unpacked) | differs: `manifest.txt` (0.0.0.87), `conf/version.txt` (`Implementation-Version=0.87`), `adapters.zip` manifest, and the classes of `ComplianceAdapter`, `ComplianceDecisions`, `EsxcliSoapClient`, `VSphereClient` with their inner classes. Every changed inner class has identical bytecode (`javap -c -p`), so those are line-table changes only. Identical: `describe.xml`, both `resources.properties`, `vcfcf-adapter-base.jar`, all content. |
| New members (`javap -p`, 86 vs 87) | `ComplianceDecisions.hostScoreLineAtInfo(int)`; `EsxcliSoapClient.unreachableReported` (instance field, not static), `takeUnreachableToReport(String)` (synchronized), `commandFailedReason(String,String,String)` (static, pure); `VSphereClient.takeEsxcliUnreachable(String)`. Nothing else added or removed. |
| `defect-gate --pak compliance` | exit 2: "1 open blocking defect(s) block release of 'compliance'" (DEF-022). Correct, and it is a release gate, not a devel-install gate. |

## Mutation tests (independent)

Each mutation applied to a fresh scratch copy of `src/`, `tests/`, `profiles/` and `describe.xml`; only the one test compiled and run. Baselines pass.

| Mutation | Should fail? | Result |
|---|---|---|
| M20 `takeUnreachableToReport` stops de-duplicating | yes | **fails** ("second ask in the same cycle: not reported again") |
| M21 `beginCycle` does not clear `unreachableReported` | yes | **fails** ("marked again next cycle: reported again") |
| M22 `hostScoreLineAtInfo` always false / always true / `> 1` | yes | **fails** (all three) |
| M23 `commandFailedReason` label condition inverted | yes | **fails** |
| M24 host loop no longer asks `takeEsxcliUnreachable` | yes | **fails** (source pin) |
| M25 the WARN demoted to `logDebug` | yes | **fails** (source pin) |
| M26 `VSphereClient` passes `null` instead of the host's entry | yes | **fails** (source pin; this is build 86's M19, which survived) |
| M27 pass-through asks for the wrong host | yes | **fails** |
| M28 reporting removes the unreachable entry | yes | **fails** ("reporting does not clear the entry") |
| M29 INFO and DEBUG branches swapped | yes | **fails** |

The author's claim (four mutations, each fails) holds, and the wider set above fails too. The pins on `ComplianceAdapter` and `VSphereClient` are source-text checks (those classes need the SDK jar the runner leaves out); as at build 86 they fail loudly on a rewrite, never silently pass.

## Attack list

**1. Can the once-per-cycle WARN set leak across cycles?** No. `unreachableReported` is cleared in the same synchronized `beginCycle` as `unreachableHosts` (`EsxcliSoapClient.java:221-226`), and `beginCycle` is the second statement of every cycle (`ComplianceAdapter.java:421`, pinned). If `ensureConnected` throws, `beginCycle` is skipped, but that cycle fails anyway and the next successful one clears it. On a reconnect, `VSphereClient` builds a new `EsxcliSoapClient` with empty sets. Its size is bounded by the vCenter's host count in any case. Proven by M21.

**2. Across instances?** No. All four maps and sets are `private final` instance fields of `EsxcliSoapClient` (no static state; `javap` confirms). Each adapter instance owns its own `VSphereClient` and client, and the key is the host MOID, which is used only inside that one vCenter's client, so the MOID trap does not apply here.

**3. Thread safety.** Every method that touches `unreachableHosts` or `unreachableReported` is `synchronized` on the client (`beginCycle`, `unreachableReason`, `takeUnreachableToReport`, `readCommandResult`). `VSphereClient.takeEsxcliUnreachable` reads the `volatile esxcli` field once into a local and null-checks it, so a concurrent reconnect cannot cause an NPE. No new shared state outside the client.

**4. Can the WARN be missed or misplaced?** It is taken in the host loop after the host's evaluation (`ComplianceAdapter.java:1062`), and esxcli is used only by HostSystem controls (canonical profiles: 2 / 6 / 23 / 12 / 12 esxcli rows for SCG 6.7 / 7.0 / 8.0 / 9.0 / 9.1, all `HostSystem`), so every marking happens inside that host's iteration before the take. The host key matches: `HostInfo.moid` is `ref.value` (`VSphereClient.java:284`), the same value `readEsxcliRecipe` uses. A host skipped earlier in the loop (version unreadable, no benchmark, disconnected) never reaches an esxcli read, so it has nothing to report. The take cannot throw.

**5. Does the INFO line still carry host name and counts?** Yes: `Host <name> [<profile>]: score=<n>% (<pass> pass, <fail> fail, <unreadable> unreadable, <total> total)`, at INFO when `unreadableCount > 0`, else DEBUG (`ComplianceAdapter.java:1078-1092`). A wholly unreadable host keeps its separate INFO "UNREADABLE ... score 0" line and does not also get the score line (it takes the `else if` branch only when not wholly unreadable). The per-cycle summary was reworded to say per-host lines are at INFO for hosts with unreadable controls.

**6. Log volume at 5 minutes with one unreachable host.** Two new lines per cycle for that host (one WARN, one INFO score line), about 24 an hour or 576 a day, plus the per-cycle lines that already existed. Healthy hosts add nothing: devel's 9 healthy hosts read fully (unreadable_count 0; recon 10/02, the collection alerts cancelled 9/23), so the INFO condition does not quietly fire for every host. Worst case (vCenter's esxcli relay down, every host affected) is 2 lines per host per cycle, about what build 85 logged for every host. Acceptable.

**7. Secrets in the new WARN.** The reason is `describe(e)`: the exception's simple class name and its message, whitespace-collapsed and capped at 160 characters, or a fixed "no executer" string. The session cookie travels in a header and is not in I/O exception messages; the host name is not a secret. Clean under `knowledge/rules/no-secrets-on-disk.md`.

**8. `cross_mp_edges` accuracy.** Direction: parent `ComplianceWorld` (this adapter's kind), child `VMwareAdapter Instance` with `foreign_adapter_kind: VMWARE`, `child_foreign`. That matches the code: `linkWorld` calls `SuiteApiStitcher#addChild` with the world as parent and the instance's vCenter as child (`ComplianceAdapter.java:566-589`). "Additive, never removed": correct, the add is a Suite API POST, never the replacing PUT, and nothing removes the edge (the known limitation since build 82). "Every cycle" means every cycle in which the vCenter resolves and the world is found; otherwise the cycle WARNs and skips, which `docs/overview.md` already covers. Not a finding.

**9. Does `cross_mp_edges` make the SDK emit anything?** No. In `src/vcfcf_*` it is parsed in `sdk_project.py` (`_parse_cross_mp_edges`, schema validation only) and consumed only by `docs_gen.py` (the Cross-MP Relationships section and the Quick Reference count). No builder, renderer or Java template reads it, and the built `describe.xml` and adapter bytecode prove it: `describe.xml` is byte-identical to 86 and no class gained relationship code. The edge still comes only from the adapter's own `addChild`.

## Build 86 findings, closure check

| Finding | Status in build 87 | Evidence |
|---|---|---|
| 86 W1 partly unreadable host not named at INFO | **Closed** | `ComplianceDecisions.java:396`, `ComplianceAdapter.java:1062-1092`; `ComplianceDecisionsTest:324-328`; mutations M20 to M25, M29 |
| 86 W2 relationship missing from landing docs | **Closed** | `adapter.yaml:23-33`; rendered at `docs/README.md:19-25` (plus Quick Reference line 33) and `docs/inventory-tree.md:17-23`; root `README.md:27-30` |
| 86 W3 issue #15 not in the registry | **Closed (by registration)** | DEF-022 in `knowledge/context/defects.md` (factory working tree, uncommitted); `defect-gate --pak compliance` now exits 2 |
| 86 N1 troubleshooting blames the host | **Closed** | `docs/installing.md:162-173` ("goes to vCenter's `/sdk` ... if every host shows it, check vCenter first"); class Javadoc `EsxcliSoapClient.java:69-80`; inline comment `:401`; WARN text says the same |
| 86 N2 cancel 3 on Score Degraded | **Closed** | `docs/overview.md:205-212` |
| 86 N3 label untested | **Closed** | `EsxcliSoapClient.commandFailedReason`, `EsxcliCycleCacheTest:299-324`; the old M19 (now M26) fails |
| 86 N4 "does not delete" stated as fact | **Closed in the docs** | reworded in `README.md:129`, `docs/installing.md:153`, `docs/overview.md:137`, `docs/data-reference.md:181` and the build 86 CHANGELOG entry. Still owed: the devel observation (checklist item 4). |

Build hygiene: `build_number: 87`, a matching CHANGELOG entry, minimal diff (no code path outside logging and the label helper changed; `ControlEvaluator`, rollup and push classes are byte-identical to 86).

## Findings

### BLOCKING

None.

### WARNING

None.

### NIT

**N1. The generated Cross-MP section brings em-dashes into the compliance docs (owner: `tooling`, not the adapter).** Authority: Scott's standing rule (no em-dashes anywhere, generated docs included). This build's first `cross_mp_edges` entry makes `docs_gen.py:455-460` (`_render_cross_mp_edges_md`) write an em-dash into the section's preamble sentence ("never appear in `describe.xml`", then the dash, then "they are declared explicitly ...") in `docs/README.md:21` and `docs/inventory-tree.md:19`; the same generator also puts em-dashes in titles, the "Do not edit" banner and empty table cells (`docs/inventory-tree.md:1,3,15`, `docs/README.md:1`). It affects every pak with generated docs, and the adapter author cannot fix it (generated, regenerated on every build). **Fix:** a `tooling` follow-up issue to replace the generator's em-dashes (code this branch does not touch, so a follow-up issue is right under delegation rule 9). Not a devel blocker.

### Notes (not findings)

- The DEF-022 registry entry is in the factory working tree, not yet committed. The gate reads the working tree, so it holds locally; commit it before anyone relies on the gate from another clone.
- There is still no approval record for a compliance devel install after 85. The install and the instance interval edit in item 6 each need Scott's verbatim go recorded first.
- Adapter issue #19 (esxcli cache lived for the session) is fixed in code since 85. Propose closing it after checklist item 7 proves it live.

## Registry check (`knowledge/context/defects.md`)

Open entries: DEF-004 (vcommunity-os), DEF-017 (factory:packaging-cli), DEF-019 (factory:extractor), DEF-020 and DEF-021 (vcommunity-vsphere), **DEF-022 (compliance)**. No `defects.local.md` in this clone.

- **DEF-022: open, still present, unchanged.** `ControlEvaluator.java:150-161`: when the setting is absent and `allowsUndefined(expected)` is false, the branch `continue`s with no pass, fail or unreadable recorded. `ControlEvaluator.class` is byte-identical between 86 and 87. It does not make the devel test misleading (the behaviour matches 85 on devel today), so it does not block the devel install. It does block a `v*` tag, and the gate enforces that now.

No closure proposed. No new registration candidates from this build.

## Devel checklist (carried from build 86, updated for 87; after Scott's go is recorded)

The devel upgrade is 85 to 87, so every build 86 item still applies.

1. **Alert continuity, before and after.** Immediately before the install, page `/api/alerts?activeOnly=true` and keep only `status == ACTIVE` (that endpoint also returns CANCELED on this instance; recon 10/02 4:13 PM). Match pak alerts by `alertDefinitionId` prefix `AlertDefinition-vcfcf_compliance-`. Record the count (388 on 10/02) and, for a sample of 10 (include esx02's collection alert `dc90c189`), the alert id and start time. After install, the same alert ids should still be ACTIVE with the same start times and the new prefixed names. A drop to near zero followed by new ids with new start times means the upgrade cancelled and re-raised them: report it, because every future rename will behave the same way.
2. **Definitions took the new attributes.** Read back `/api/alertdefinitions/AlertDefinition-vcfcf_compliance-vcfcf_compliance_ctl_esx_ssh_login_banner` (174 characters): the name complete and character-for-character, and wait 1 / cancel 3. Do the same for one collection alert (expect 1 / 1), `score_degraded` (1 / 3), and the matching symptom definitions. If the cycles still read 1 / 1, the redescribe does not update existing definitions, and cancel 3 has not taken effect on any upgraded instance.
3. **The Overview really reads ComplianceWorld.** Export the Environment Overview from devel (or open W1 and W5 in edit) and confirm the metric keys are `Rollup|Environment|*` on ComplianceWorld, not `Super Metric|sm_...` on vSphere World. The old super metrics are still installed, so a dashboard that was not re-imported would look identical. Then confirm the four tiles and the trend show values with no policy edit.
4. **Retired super metrics (closes the evidence half of 86 N4).** Confirm whether the four "[VCF Content Factory] Compliance ..." super metrics are still listed. If they are, compare their latest values with the four `Rollup|Environment` values for the same timestamps one last time, and record the result in `recon_log.md`. If they are gone, the five "to be confirmed" sentences (README, `docs/installing.md`, `docs/overview.md`, `docs/data-reference.md`, CHANGELOG) need rewording.
5. **Log lines (updated for 87).** Per cycle per instance: INFO `ComplianceAdapter cycle took N ms` (about 5 to 7 seconds; 10/02 baseline 4.5 to 6.6 s), or WARN `ComplianceAdapter cycle failed after N ms`; one INFO `Hosts scored this cycle: N of M (...)`. Per-host score lines at INFO **only** for hosts with unreadable controls (expect none for a healthy host, and the "UNREADABLE ... score 0" line for a disconnected host such as esx02). If any host shows `esxcli-host-unreachable` in "Unreadable controls this cycle by reason", expect exactly one WARN per cycle naming it ("esxcli request through vCenter failed (...)").
6. **Cancel 3 needs the interval at 5.** The three instances are still at 60. At 60, cancel 3 means about 3 hours before a fixed control clears, and nothing can be learned about flapping in a session. With Scott's go, set all three to 5 minutes and confirm it reads back 5. Then watch for alerts on the same definition and object that cancel and re-raise within an hour (should now be rare), and note whether the timing follows the compliance cycle or the VMWARE cycle.
7. **esxcli live proof (carried from 85; needs Scott's go because it changes a devel host).** Change one esxcli-backed setting on one host; the control's `Compliant` should change within two 5 minute cycles without a collector restart. Revert it. With cancel 3, the alert for a control you fixed clears 3 cycles after the fix, not 1.
8. **Upgrade gap.** Expect one missing `Rollup|Environment` point around the install (redescribe reset, as at 85). Not a failure.
9. **Relationship docs match what is live (new).** On ComplianceWorld, confirm the children are the three VMwareAdapter Instance objects (mgmt, wld01, wld02) and nothing else, as `docs/README.md` now states.

## If shipped as-is

To devel: everything build 86 delivers (engine-computed Overview totals, prefixed alert names, cancel 3, one timeout per hung host per cycle), plus an INFO log that names any partly unreadable host and one WARN per cycle naming a host whose esxcli calls were skipped. As a public release: refused by `defect-gate` until DEF-022 is fixed, and the buildkit ordering prerequisite from build 85 still applies.
