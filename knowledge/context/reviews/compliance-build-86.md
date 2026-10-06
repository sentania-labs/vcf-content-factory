# SDK adapter review: compliance build 86

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-05 (local, America/Chicago)
- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/environment-computed-metrics`, base `main` at `0a7d539`, uncommitted working tree including the four unstaged deletions under `supermetrics/`)
- **Artifact reviewed:** `dist/vcfcf_sdk_compliance.0.0.0.86.pak` (built 10:53 AM), sha256 `a3bf49f98afa1eea901a59577998fe641a92dc6e0f11dfaad9537db6b310f5de` (confirmed). Reference: `dist/vcfcf_sdk_compliance.0.0.0.85.pak` (on devel), sha256 `9b0d22a9...a7209fa7` (confirmed).
- **Prior passes:** `compliance-build-84.md` (APPROVE, 3 W / 3 N), `compliance-build-85.md` (APPROVE, 7 W / 5 N)
- **Verdict:** APPROVE (0 BLOCKING / 3 WARNING / 4 NIT)
- **Fit for a devel install: YES.** Every claimed change is in the source and in the shipped bytes, the build reproduces, the framework jar is a fresh compile of the approved commit, and nothing found would make the devel test misleading, provided the checklist's dashboard check (item 3) is done: the retired super metrics stay installed on devel, so an Overview that was not actually re-imported would still look right.

## Bottom line

The build does what the brief says. Alert ids, symptom ids and recommendation ids are identical to 85; the only differences in the 143 alert and 151 symptom definitions are the cycle values, and the only property changes are the 143 alert names plus recommendation 105. 138 symptoms and 137 alerts are now wait 1 / cancel 3 (136 per-control plus the score ones); the 13 collection symptoms and 6 collection alerts stay 1 / 1. Nothing in the pak references a super metric any more. I independently re-ran 19 mutations: 17 fail their test as they should, including the three that survived at build 85.

Three warnings, none blocking devel. (W1) The DEBUG demotion removed the only INFO line that named a partly unreadable host, so the new `esxcli-host-unreachable` case cannot be traced to a host from an INFO log. (W2) The ComplianceWorld to vCenter relationship is now documented, but only in `docs/overview.md` and `docs/data-reference.md`; the landing pages are silent, and the framework already has the hook that fixes it. (W3) Not from this delta: adapter issue #15, a confirmed High false-compliance bug, is still in the shipped evaluator and is not in the defect registry, so the release gate cannot stop on it.

## Independent verification

| Check | Result |
|---|---|
| Pak checksums | 86 `a3bf49f9...b310f5de` and 85 `9b0d22a9...a7209fa7`, both match |
| `validate-sdk content/sdk-adapters/compliance` | OK (javac 19 files, the existing `-source 11` options warning only) |
| `ci/run_java_tests.sh` | 12 Java suites pass (`EnvironmentKeyContractTest` "4 computed keys, 5 metric references", `EsxcliCycleCacheTest` all assertions); alert generator 16 tests OK and "up to date" (136 control alerts plus 6 collection alerts, plus the hand-written score alert, 143); dashboard alert lists 3 tests OK |
| `build-sdk` into scratchpad | reproduces `vcfcf_sdk_compliance.0.0.0.86.pak`. Against the author's pak: every adapter class, `describe.xml`, both `resources.properties`, the framework jar and the dashboards identical; `vcfcf_compliance.jar`, `views.zip` and `overview.packed` differ only in zip timestamps (contents identical). Adapter repo working tree unchanged by the build (status plus diff hash identical before and after). |
| `pak-compare` 86 vs 85 (author's pak and mine) | gate PASS, 0 BLOCKING / 0 WARNING / 4 INFO, the four `content/supermetrics/*.json` removals. Nothing else. pak-compare does not report alert names or cycle values, so it is not evidence for them; checked directly below. |
| Built `describe.xml` and `resources.properties` | byte-identical to the source files; `monitoringInterval="5"`; `version.txt` `Implementation-Version=0.86`, manifest `0.0.0.86` |
| Cycle values, built pak | 85: all 151 symptoms and 143 alerts 1 / 1. 86: symptoms 138 at 1 / 3 and 13 at 1 / 1; alerts 137 at 1 / 3 and 6 at 1 / 1. The 1 / 1 alerts are exactly the six `vcfcf_compliance_collection_*`; the two non-control 1 / 3 symptoms are `score_warning` (< 95) and `score_critical` (< 80). |
| Ids and names, built pak | symptom, alert and recommendation id sets identical to 85; no alert or symptom differs from 85 except in the cycle attributes. 143 of 143 alert names start with `VCF Content Factory Compliance Alert: `; changed properties are the 143 alert names plus `105` (recommendation now says the alert clears after three cycles). Lengths: max 174 (three names), 10 over 160, 28 over 150, 76 over 128; build 85's longest was 136. |
| Super metric references | rendered dashboard JSON, views and reports in the pak: zero hits for "Super Metric", `sm_`, "supermetric" or "Compliance Average Score". "Non-Compliant Objects", "Objects Scored" and "Without Benchmark" appear only as tile labels (`metricName`) on the new `Rollup|Environment|*` keys. Views are unchanged from 85 (contents identical). |
| Overview dashboard 85 vs 86 | the only changes: the dashboard's `resourceKind` entry `VMWARE / vSphere World` becomes `vcfcf_compliance / ComplianceWorld`; W1 (Scoreboard) and W5 (MetricChart), mode `resourceKind` / `resourceKindAll`, bind `Rollup|Environment|{avg_score, non_compliant, no_benchmark, scored}` and `{avg_score, non_compliant}`; the description text. Layout, interactions, W3/W4 (still on vSphere World), About text and the alert list unchanged. |
| Dashboard alert lists | filter by `AlertDefinition-vcfcf_compliance-<id>`, never by name. Per dashboard, the id set is identical to 85 (hash compared). The Overview lists 142 (all but `score_degraded`), as in 85. |
| Shipped bytecode | `collectWorldCycle` calls `ensureConnected` then `beginCycle` before anything else; `collectWorld` uses `System.nanoTime` and carries "ComplianceAdapter cycle took", "ComplianceAdapter cycle failed after", "Hosts scored this cycle"; `VSphereClient` carries `esxcli-host-unreachable: `; `EsxcliSoapClient` carries the no-executer reason. No test class in the jar. |
| Adapter classes 85 vs 86 | changed: `ComplianceAdapter` (plus recompiled inner classes), `EsxcliSoapClient` (`$CommandFetcher` replaced by `$Transport` and `$1`), `VSphereClient` (plus inner classes), `ComplianceRollup` and `UnreadableReasons` (comment-only source changes, line table only) |
| Framework jar | pak jar sha256 `f87ea245...` equals `adapter_runtime/vcfcf-adapter-base.jar`. `src/` has no working-tree change and no diff against `692b71b`. I compiled the framework from `git archive 692b71b` (not the working tree; `-source 11 -target 11 -proc:none`, SDK jar only): all 43 classes byte-identical to the pak's jar. Against 85's jar only `SuiteApiStitchClient.class` differs (new `FAILURE_TAIL_KEEP` and `capHeadAndTail`, the framework review's N10 to N13 work). framework-reviewer passes 4 to 6 cover it; the sixth pass is APPROVE 0 / 0 / 0. The 10:49 AM mtimes are the `git reset --hard`, not a content change. |
| `defect-gate --pak compliance` | "no open blocking defects affecting compliance" |

## Mutation tests (independent)

Each mutation applied to a fresh scratch copy of `src/`, `tests/` and `describe.xml`; only the one test compiled and run.

| Mutation | Should fail? | Result |
|---|---|---|
| Baseline | no | pass |
| M1 `beginCycle` does not clear `resultCache` | yes | **fails** (drift) |
| M2 `beginCycle` does not clear `executerByHost` (survived at 85) | yes | **fails** ("executer cache cleared") |
| M2b `beginCycle` does not clear `unreachableHosts` | yes | **fails** |
| M8 cache key ignores the command (survived at 85) | yes | **fails** ("second command reads its own result") |
| M9 `VSphereClient.beginCycle` body emptied (survived at 85) | yes | **fails** (source pin) |
| M9eq `beginCycleOn(this.esxcli)`, behaviour unchanged | no | **fails** (see attack 7: strict, fails loud) |
| M11 `beginCycle` moved before `ensureConnected` | yes | **fails** |
| M11b `beginCycle` removed from the cycle body | yes | **fails** |
| M12 an `IOException` does not mark the host | yes | **fails** ("no further calls to a host that timed out") |
| M13 the negative entry is never consulted | yes | **fails** |
| M14 any exception marks the host | yes | **fails** ("non-I/O failure does not skip the host") |
| M15 a missing executer does not mark the host | yes | **fails** |
| M16 a failed result is not cached | yes | **fails** |
| M17 reason cap removed | yes | **fails** |
| M18 a found executer is not cached | yes | **fails** |
| M19 `VSphereClient` never uses the `esxcli-host-unreachable` label | yes | **passes** (N3; diagnostics only) |
| C1 `depth=2,` inside a reference (survived at 85) | yes | **fails** |
| C2 space before `}` (survived at 85) | yes | **fails** |
| C3 spaces around `=` | yes | **fails** |

The author's claim (every listed mutation now fails) holds.

## The attack list, item by item

**1. Do renamed alerts keep their active instances on the 85 to 86 upgrade?** What I can establish: the platform keys these definitions as `AlertDefinition-vcfcf_compliance-<id>` (recon 2026-10-02 4:13 PM), every id is unchanged, the alert list widgets filter by those ids, and an active alert has survived earlier pak upgrades with an unchanged definition (esx02's collection alert, started 9/23, still ACTIVE on 10/02 after the 82 and 84 installs). What I cannot establish: none of those upgrades changed a definition's content. Whether a redescribe that changes a definition's name and cycles updates it in place and keeps its active alerts, or cancels and re-raises them, is not recorded anywhere in the repo. The expected outcome is in place; the devel checklist (item 1) proves it before and after with instance ids and start times, not counts alone.

**2. Does removing the super metrics break anything that still references them?** No. Nothing in the pak references them (table above). Outside the pak: the devel instance keeps the four super metrics (if content import leaves them, which the docs say but the repo does not prove: N4). They keep calculating harmlessly where enabled, and that is useful one more time on devel as a cross-check (checklist item 4).

**3. Does a redescribe update `waitCycle` / `cancelCycle` on symptoms that already exist?** Not established from the repo. The 85 install's analytics log shows "Newer version describe received ... Performing describe update" (recon 5:13 PM, 10/02), and the ComputedMetrics block was applied on that path, so the describe is re-read on upgrade; nothing records whether existing symptom and alert definitions take changed attributes. The read-back is cheap: checklist item 2. A second open question that matters more: these symptoms sit on VMWARE resources whose `Compliant` value is pushed through the Suite API by a different adapter, and the repo does not record whose cycle the analytics counts for wait and cancel (the compliance push or the VMWARE resource's own collection). The docs' "3 cycles, 15 minutes" is right when both run every 5 minutes, which is the default configuration. On devel the instances are still at 60 (checklist item 6).

**4. Can a transient failure on command 1 wrongly mark the host's other commands unreadable?** Yes. One `IOException` (a read timeout, a refused or reset connection) or a missing executer marks the host for the rest of the cycle, and every remaining esxcli-backed control on it is UNREADABLE with reason `esxcli-host-unreachable`. On SCG 8.0 that is 19 host controls across 7 commands; before 86 the same blip cost only the controls of that one command (at most 11). It is acceptable under `knowledge/lessons/unreadable-is-not-compliant.md`: the read path never produces a value, `readCommandResult` turns the skip into a cached FAILED result, `readField` / `readRowField` return `COMMAND_FAILED`, and `Compliant` is pushed as -1, never 1. It is the safe direction, bounded to one cycle (`beginCycle` clears it, proven by M2b), and other hosts are unaffected. A fault that comes back as an answer (HTTP 500, esxcli `<fault>`, parse error) still fails only that command (M14). Two consequences the docs do not state: the connection is to vCenter's `/sdk`, not the host (N1), and an unreadable cycle lowers a host's score, so with cancel 3 one blip can hold Score Degraded for 15 minutes (N2).

**5. After the DEBUG demotion, can someone diagnose a single host from an INFO log?** Partly. At INFO they get the per-cycle "Hosts scored this cycle: N of M (K non-compliant, J wholly unreadable)", the reason counts by category ("Unreadable controls this cycle by reason"), a WARN with the total unreadable count, the per-host "UNREADABLE ... score 0" line for a wholly unreadable host, and the per-host WARN when advanced settings fail. They do **not** get the name of a host that is only partly unreadable, which is exactly the new `esxcli-host-unreachable` case. Before 86 the per-host INFO score line named it with its unreadable count. The object is still findable in the UI (its collection alert and `unreadable_count`), not in the log. W1.

**6. The 174 character alert name.** No length limit is recorded anywhere in the repo, and no definition failed at 136 characters in 85. That only says 136 imported; it does not prove the full string was kept. Checklist item 2 reads back the three 174 character definitions and compares them character for character. The UI truncating a long name in a list is cosmetic.

**7. Is the source-level test pin brittle?** Yes, in the safe direction. It requires `VSphereClient.beginCycle` to be exactly `EsxcliSoapClient.beginCycleOn(esxcli);` and the first two statements of `collectWorldCycle` to be exactly `vsphere.ensureConnected()` and `vsphere.beginCycle()`. A behaviour-preserving rewrite (`this.esxcli`, M9eq) fails it, and its brace matcher would be confused by a brace inside a comment or string in those bodies. Every way it can go wrong is a loud false failure that names the expected text, never a silent pass, and `VSphereClient.beginCycle`'s Javadoc says the body is pinned. Acceptable; not a finding.

**8. Docs accuracy against the shipped pak.** Accurate on: 143 alert definitions and the prefix, ids unchanged, the cycle values and which alerts keep 1, recommendation 105, the four `Rollup|Environment` keys and their expressions, one interval behind and one point skipped per upgrade, the never-removed link, the Scored tile beside Non-Compliant, no policy enablement, the 5 minute default and "existing instances keep their stored interval" (backed by the 10/02 5:13 PM recon: 85 installed, cycles still hourly at :04). Gaps: W2, N1, N2, N4.

## Build 84 and 85 findings, closure check

| Finding | Status in build 86 | Evidence |
|---|---|---|
| 85 W1 flapping at 5 minutes | **Closed in code** | 136 control and 2 score symptoms, 137 alerts at 1 / 3 in the built pak; `test_wait_and_cancel_cycles` pins all 294 definitions by group. Behaviour on devel still owed (checklist 6). |
| 85 W2 hung host costs 7 x 120 s | **Closed in code** | `EsxcliSoapClient.java:344-370`, `unreachableHosts`; mutations M12 to M15. A live timeout has not been observed. |
| 85 W3 interval decision and upgrade behaviour | **Closed** | Decision in `knowledge/context/approvals/2026-10-02-compliance-build-85-devel-install.md`; devel showed 60 stayed 60; upgrade note in `README.md:120` and `docs/installing.md` "Upgrading". Scale is still unmeasured, which the bulk-collection design already owns. |
| 85 W4 framework jar not reviewed | **Closed** | framework-reviewer passes 4 to 6 (sixth APPROVE 0 / 0 / 0); pak jar equals a fresh compile of `692b71b`; CHANGELOG build 86 entry names the framework jar. |
| 85 W5 / 84 W1 docs parity | **Partly closed** | ComplianceWorld keys and the link are in `docs/overview.md` and `docs/data-reference.md`; "carries only" is gone. The landing surfaces still say nothing about the relationship: W2. |
| 85 W6 release ordering | **Open, no code needed** | CHANGELOG build 86 entry restates the buildkit prerequisite. |
| 85 W7 custom CSV cache | **Closed as a follow-up** | Adapter issue #36. |
| 85 N1 esxcli test gaps | **Closed** | M2, M8, M9 now fail. |
| 85 N2 cycle time on failed cycles | **Closed** | `ComplianceAdapter.java:394-412`, `finally` with `nanoTime`; INFO "cycle took", WARN "cycle failed after". |
| 85 N3 / 84 N2 reference parameters | **Closed** | C1 to C3 fail. |
| 85 N4 log volume | **Closed, with a side effect** | `ComplianceAdapter.java:1069`, `:1466` at DEBUG, per-cycle summary at `:1090`. Side effect: W1. |
| 85 N5 / 84 N3 zero-scored tile | **Closed** | Scored tile beside Non-Compliant, stated in README, `docs/overview.md` and `docs/data-reference.md`. |

## Findings

### BLOCKING

None.

### WARNING

**W1. A partly unreadable host is no longer named at INFO, including the new `esxcli-host-unreachable` case.** Authority: review dimension 6 (failures logged with resource context; logs must separate "evaluated" from "couldn't read"). `ComplianceAdapter.java:1069` moved the per-host score line, the only INFO line that named a host with some unreadable controls, to DEBUG. Nothing at INFO or WARN names the host when `EsxcliSoapClient.java:361` marks it unreachable after a 120 s timeout or a refused connection. An operator reading the log at INFO sees "esxcli-host-unreachable=19" and has to turn on DEBUG or go to the UI to find which host. The volume reduction is right for healthy hosts. **Fix (small):** keep the per-host line at INFO when `cr.unreadableCount > 0` (bounded to problem hosts), or log one WARN the first time a host is marked unreachable in a cycle, with the host name and the capped cause. Not a devel blocker: on devel's handful of hosts the UI shows the host.

**W2. The ComplianceWorld to vCenter relationship is documented only in `docs/overview.md` and `docs/data-reference.md`.** Authority: review dimension 11 (cross-MP relationships never appear in `describe.xml`, so the generated docs cannot pick them up; buried but present is a WARNING; origin unifi v1.1.0.11). Root `README.md`, `docs/README.md` and `docs/inventory-tree.md` have no mention. The framework already has the hook: `adapter.yaml` `cross_mp_edges:` (synology uses it), which `docs_gen` renders as a "Cross-MP Relationships" section in both generated files. Compliance's `adapter.yaml` has none. **Fix:** add a `cross_mp_edges` entry (parent `ComplianceWorld`, child `VMWARE VMwareAdapter Instance`, `direction: child_foreign`, `foreign_adapter_kind: VMWARE`, one line saying it is added each cycle and never removed), regenerate, and add one sentence under README "What it does for you". Carries 85 W5 / 84 W1. **Registration candidate** (RULE-012) if a `v*` tag is proposed before it is fixed.

**W3. Adapter issue #15, a confirmed High false-compliance bug, ships in this pak and is not in the defect registry.** Authority: review dimension 1 (`knowledge/lessons/unreadable-is-not-compliant.md`, a missing read must never improve a score) and RULE-012 (`knowledge/rules/release-gate-defects.md`). `ControlEvaluator.java:150-161`: when an advanced setting is absent and the guide's expected value does not accept "Undefined" or "Not Present", the control is `continue`d. It is not counted as pass, fail or unreadable, so an un-hardened object drops a failing control from its denominator and scores higher, and that control's alert can never fire. The issue names `vm.vmrc-lock`, the EFI boot-types control, `RemoteDisplay.maxConnections`, `mks.enable3d` and the vpxd syslog, password and log-level controls. This build does not touch it, 85 behaves the same, and it does not make the 86 devel test misleading, so it does not block the devel install, and per delegation rule 9 it is not a re-brief item for this build. But it is exactly what `defect-gate` exists to stop, and today the gate reports "no open blocking defects affecting compliance". Builds 82 to 85 were reviewed without flagging this registry gap; that was my miss. **Fix:** the orchestrator registers it in `knowledge/context/defects.md` (`Affects: compliance`, blocking) so no `v*` tag ships with it; the code fix is the one in the issue (emit a non-compliant `(undefined)` result and count it as a fail, with a `ControlEvaluatorTest` case).

### NIT

**N1. The troubleshooting text blames the host for what may be vCenter.** `docs/installing.md:162-168` says "that host timed out, refused the connection or returned no esxcli executer". The esxcli calls go to vCenter's `/sdk` (`EsxcliSoapClient.post`), and vCenter relays them to the host. A refused or reset connection, or a timeout, is between the collector and vCenter. An operator who sees it on every host should look at vCenter, not each ESX host's firewall. A vCenter-side outage mid-cycle also still costs one timeout per host, not one per vCenter. **Fix:** "the esxcli request for that host, made through vCenter, timed out or could not connect ... if every host shows it, check vCenter first." Same wording in the CHANGELOG entry and the `EsxcliSoapClient` class Javadoc ("transport failure on a host").

**N2. The docs explain cancel 3 for the per-control alerts only.** `docs/overview.md:194` and `docs/data-reference.md` describe cancel 3 as stopping a failing control from losing its alert on one unreadable cycle. For Score Degraded it works the other way: unreadable counts as failing, so one unreadable cycle lowers the score, the alert can raise after 1 cycle and now holds for 3 (15 minutes). With the per-host negative entry one timeout makes up to 19 SCG 8.0 controls unreadable, enough to cross 80 (Critical) on a healthy host. This is the safe direction under the lesson. It just needs saying. **Fix:** one sentence next to the existing paragraph, pointing at the "Compliance data not collected" alert raised in the same cycle.

**N3. The `esxcli-host-unreachable` label has no test.** Mutation M19 passes: `VSphereClient.java:750-761` chooses the label, and the runner cannot load `VSphereClient` (SDK dependency). It is diagnostics only (no score impact) and the shipped string is confirmed in bytecode. **Fix (optional):** move the label choice into an SDK-free static helper on `EsxcliSoapClient` and test it.

**N4. "A pak upgrade does not delete content it imported earlier" is stated as fact without evidence in the repo.** `docs/installing.md:152`, `docs/overview.md:136`, `docs/data-reference.md:180`, CHANGELOG. No recon entry or lesson records it. If it is wrong, the only harm is an admin looking for super metrics that are already gone, but under evidence over labels it should be confirmed. **Fix:** checklist item 4 confirms it on devel; record it in `recon_log.md` and adjust the wording if needed.

### Notes (not findings)

- `knowledge/designs/sdk-adapters/compliance-environment-computed-metrics.md` "Go and progress" still says framework-reviewer approved "on two passes" and "Devel install: not done". It is orchestrator-owned and not in the pak.
- There is no approval record for installing 86 on devel yet (`knowledge/context/approvals/` has 84 and 85 only). The install, and the instance interval edit in checklist item 6, each need Scott's verbatim go recorded first.
- Adapter issue #19 (esxcli cache lives for the session) is fixed by 85 and 86 in code. Propose closing it after checklist item 7 proves it live.

## Registry check (`knowledge/context/defects.md`)

Open entries: DEF-004 (vcommunity-os), DEF-017 (factory:packaging-cli, `/publish` pointer crash, not on the devel install path), DEF-019 (factory:extractor), DEF-020 and DEF-021 (vcommunity-vsphere). **None has `Affects: compliance`.** No `defects.local.md` in this clone. `defect-gate --pak compliance` agrees. **Registration candidates:** W3 now (a confirmed false-compliance defect in shipped code), and W2 if a `v*` tag is proposed before it is fixed.

## Devel checklist (after Scott's go is recorded)

1. **Alert continuity, before and after.** Immediately before the install, page `/api/alerts?activeOnly=true` and keep only `status == ACTIVE` (that endpoint also returns CANCELED on this instance; recon 10/02 4:13 PM). Match pak alerts by `alertDefinitionId` prefix `AlertDefinition-vcfcf_compliance-`. Record the count (388 on 10/02) and, for a sample of 10 (include esx02's collection alert `dc90c189`), the alert id and start time. After install, the same alert ids should still be ACTIVE with the same start times and the new prefixed names. A drop to near zero followed by new ids with new start times means the upgrade cancelled and re-raised them: report it, it is how every future rename will behave.
2. **Definitions took the new attributes.** Read back `/api/alertdefinitions/AlertDefinition-vcfcf_compliance-vcfcf_compliance_ctl_esx_ssh_login_banner` (174 characters): the name complete and character-for-character, and wait 1 / cancel 3. Do the same for one collection alert (expect 1 / 1), `score_degraded` (1 / 3), and the matching symptom definitions. If the cycles still read 1 / 1, the redescribe does not update existing definitions, and the cancel 3 change has not taken effect on any upgraded instance.
3. **The Overview really reads ComplianceWorld.** Export the Environment Overview from devel (or open W1 and W5 in edit) and confirm the metric keys are `Rollup|Environment|*` on ComplianceWorld, not `Super Metric|sm_...` on vSphere World. This matters because the old super metrics are still installed, so a dashboard that was not re-imported would look identical. Then confirm the four tiles and the trend show values with no policy edit.
4. **Retired super metrics.** Confirm whether the four "[VCF Content Factory] Compliance ..." super metrics are still listed (N4). If they are, compare their latest values with the four `Rollup|Environment` values for the same timestamps one last time.
5. **Cycle time line.** The format changed: each cycle now logs a separate INFO line `ComplianceAdapter cycle took N ms` (no longer inside "collection complete"), or a WARN `ComplianceAdapter cycle failed after N ms` just before `onCollect`'s error. Expect about 5 to 7 seconds per instance (10/02 baseline 4.5 to 6.6 s). Also confirm one `Hosts scored this cycle: N of M (...)` INFO line per cycle per instance, and no per-host score lines at INFO.
6. **Cancel 3 behaviour needs the interval at 5.** The three instances are still at 60. At 60, cancel 3 means about 3 hours before a fixed control clears, and nothing can be learned about flapping in a session. With Scott's go, set all three to 5 minutes and confirm it reads back 5. Then watch for alerts on the same definition and object that cancel and re-raise within an hour (should now be rare). Note whether the timing matches the compliance cycle or the VMWARE cycle (attack 3).
7. **esxcli live proof (carried from 85, needs Scott's go because it changes a devel host).** Change one esxcli-backed setting on one host; the control's `Compliant` should change within two 5 minute cycles without a collector restart. Revert it. With cancel 3, the alert for a control you fixed clears 3 cycles after the fix, not 1.
8. **Upgrade gap.** Expect one missing `Rollup|Environment` point around the install (redescribe reset, as at 85). Not a failure.

## If shipped as-is

To devel: the Overview reads engine-computed totals with no policy step, every alert is renamed under one prefix (most likely in place), a failing control's alert survives a single unreadable cycle, a hung host costs one timeout per cycle instead of seven, and the INFO log is quieter but no longer names a partly unreadable host (W1). As a public release: not yet. W3 is a known false-compliance bug the gate cannot see until it is registered, W2 leaves the relationship off the landing docs, and 85 W6 (buildkit ordering) still applies.
