# SDK Adapter Review: compliance build 57 (v3 version-aware)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 57, commit `81cf55d` (on `120cc62` SCG 6.7/7.0 profiles) vs build 56 `32de5aa` (main)
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.57.pak`, reference `dist/vcfcf_sdk_compliance.0.0.0.56.pak`
- **Design contract:** `knowledge/designs/sdk-adapters/compliance-v3-version-aware.md`, `knowledge/designs/dashboards/compliance-environment-overview.md`, `knowledge/designs/dashboards/compliance-esxi-hosts.md`
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **CHANGES REQUESTED**
- **Findings:** 3 BLOCKING / 6 WARNING / 4 NIT

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `ci/run_java_tests.sh` all passing | **Confirmed.** All six Java suites pass; generator unittest suite 12/12 OK. |
| `validate-sdk` clean | **Confirmed.** 12 sources compiled, one benign `-source 11` warning. |
| `build-sdk` reproduces the pak | **Confirmed.** Rebuilt into scratch; adapter jar content, `views.zip` content and every other file byte-identical to `dist/...57.pak` (only zip timestamps differ). Adapter and factory trees clean after build. |
| pak-compare vs 56 | **Observed: 0 BLOCKING / 1 WARNING / 6 INFO.** W1 = ComplianceWorld attribute count 6 to 1 (the retired Summary numbers, intended). INFO = manifest description plus the five new profile files. The author's numbers were not in the brief, so this is the reference value. |
| describe.xml / resources.properties reproducible from the generator | **Confirmed.** `generate_compliance_alerts.py --check` reports up to date: 144 symptoms / 144 alerts / 144 recommendations (Host 86, VM 23, vCenter 15, Cluster 2, vDS 11, Portgroup 7). |
| Canonical profiles reproducible | **Confirmed** (beyond the brief). Re-ran `normalize_scg_v70.py`, `normalize_scg_v67.py`, `normalize_scg_v91.py`: `scg_7.0.csv`, `scg_6.7.csv`, `scg_9.1.csv` byte-identical to the committed files. Spot check: every mapped 6.7 advanced_setting row carries the same parameter as its newer-profile control_id (21/21). |
| Real Ops kind keys in generated definitions | **Confirmed.** `describe.xml` resourceKinds are only `HostSystem`, `VirtualMachine`, `VMwareAdapter Instance`, `ClusterComputeResource`, `VmwareDistributedVirtualSwitch`, `DistributedVirtualPortgroup`; all 291 `adapterKind="VMWARE"`. No CSV tokens (`VCenterAdapterInstance`, `DistributedVirtualSwitch`) leaked. `operator="="` on a numeric metric symptom has reference precedent (tkopton BlueScreenDetection). subType 21 = COMPLIANCE per `knowledge/context/api-surface/compliance_enablement_markers.md`. |
| Version parsing | **Confirmed by probe.** `majorMinor`: `8.0 U3` to 8.0, `8.0.3` to 8.0, `8.0U3` to 8.0, `9.0.0.0` to 9.0, `VMware ESXi 8.0.3 build-1` to null (adapter reads `product.version`, not `fullName`, so fine). |
| "Devel instances are on SCG 9.0" | **Refuted by the brief's recon (2026-09-23): all three devel instances are stored `VMware_SCG_9.1`.** See W6. |

## Registry check (`knowledge/context/defects.md`)

No `defects.local.md` exists. No open defect names `compliance` in `Affects:` (open entries are DEF-004 vcommunity-os, DEF-017 factory:packaging-cli, DEF-019 factory:extractor, DEF-020/021 vcommunity-vsphere). Nothing to re-assert or propose for closure. Registration candidates from this review: B2, W1, W2 (if they survive acceptance).

## What is sound

- **Unreadable controls still count against the object.** `ControlResult` now carries `unreadable`, forced `compliant=false` (`ControlEvaluator.java:693`); both unreadable constructors set it (`:248`, `:388`). Score arithmetic unchanged (unreadable excluded from numerator and denominator, as since build 48). `non_compliant` = `fail>0 || unreadable>0` in both the per-object push (`ComplianceAdapter.java:1517`) and the rollup (`ComplianceRollup.java:73-75,93`). `Compliant=-1` for unreadable (`ComplianceAdapter.java:1500-1502`) cannot fire a `= 0` symptom.
- **Cardinal fixes are real.** VM extraConfig read failure now folds to UNREADABLE (`:934-944`, was an empty map that passed every "or Undefined" control). Failed vim reads, a failed cluster vSAN probe and a failed vCenter settings read now fold to UNREADABLE (`:1205-1206`, `:1233`, `:1042-1051`, `:1336-1343`).
- **Zero-divisor contract kept.** `recordEvaluated` adds to scored/score_sum only when `totalCount>0`; `avg_score` only when `scored>0`; the per-object push omits score/pass/fail when `totalCount==0`.
- **vDS / portgroup / cluster follow vCenter.** `governingVersion` returns the vCenter version for every non-HOST/VM kind; `collectVimObject` never reads the object's own version.
- **Crash-the-cycle.** Every new per-object read (`getHostProductVersion`, `getVmHostMoid`, host-of-VM version, vCenter version) is caught per object. Stitcher pushes are swallowed at WARN by the framework (`SuiteApiStitcher.pushProperties/pushStats`). `profileForHistory` catches loader failures. No new throw path escapes a per-object loop. Pre-existing: `getHosts()` failure still fails the cycle loudly (correct).
- **Loader contract.** `manual_review.csv` parsed by header name, missing header throws (`BenchmarkLoader.java` `parseManualReview`). `loadAll` refuses a partial benchmark set.
- **Minimal-diff and hygiene.** `build_number` 57, CHANGELOG entry present, scope matches the design. No secrets in any new log line.

## BLOCKING

### B1. Rollup can land on another vCenter's object (stitching identity fallback)

- **Where:** `ComplianceStitcher.java:300-326` (`matchVCenterAdapterInstance`), consumed by `ComplianceAdapter.java:1011` and `pushRollup` `:483-500`.
- **Authority:** skill § *ARIA_OPS stitching identity, the MOID trap*; `knowledge/lessons/stitch-moid-not-unique-across-vcenters.md`; reviewer dimension 5 (always BLOCKING).
- **What:** the matcher tries `VMEntityVCID` first, but when the instance UUID is known and simply not in the index (the VMWARE adapter does not monitor this vCenter, or its key lacks `VMEntityVCID`), it falls through to a dot-prefix fuzzy match on `VCURL`, a display-name match, and finally `singletonOfKind`. With one VMWARE vCenter in Ops, a compliance instance on a different vCenter pushes its vCenter controls and, new in v3, its whole per-vCenter rollup onto the wrong vCenter every cycle. With a short `vcenter_host` (for example `vcsa`) the prefix loop picks an arbitrary `vcsa.<site>` entry. That silently overwrites the other instance's rollup, which is the last-writer-wins defect v3 exists to fix, and the environment super metrics double-count. The path predates v3; v3 makes it the only home of the environment numbers.
- **Fix:** when `vcInstanceUuid` is non-null and absent from `vcByVcUuid`, return null (no push, the existing WARN fires). Keep the name fallback only for an unreadable UUID, and even then exact `VCURL` match only, no prefix and no singleton.

### B2. A failed version read improves the object's posture and cancels its alerts

- **Where:** `BenchmarkSelector.java:119-122`; `ComplianceAdapter.java:708-731` (host), `:966-992` (VM), `:1254-1265` (`recordNoBenchmark`), `:1458-1469` (`pushNoBenchmark` writes `non_compliant=0`), `:590-642` (`noteApplied`).
- **Authority:** skill § *Unreadable is NOT compliant*; `knowledge/lessons/unreadable-is-not-compliant.md`; reviewer dimension 1.
- **What:** a SOAP fault on `summary.config.product.version` (or on a VM's `runtime.host`, or the host-of-VM version) makes the object "no benchmark for ESXi (version unreadable)". Then:
  1. it pushes `non_compliant=0`, so it drops out of every "non-compliant hosts" count;
  2. `noteApplied` sees a change from, say, `VMware_SCG_8.0` and pushes `Compliant=-1` for every control of the old benchmark, cancelling all its open per-control alerts;
  3. the rollup counts it under `no_benchmark` instead of non-compliant, and the host leaves the `Rollup|Host` denominator, bypassing the Task #16 last-known-score rule that exists for exactly this case.

  A host with 12 failing controls and one transient read fault looks clean for a cycle, then every alert re-fires. An unreadable control on the same host would have set `non_compliant=1`, so the two read-failure paths contradict each other.
- **Fix:** separate "version unreadable" from "version unmapped". For unreadable: treat the object as unreadable (`non_compliant=1`, not counted as no_benchmark), do not run orphan cleanup, and for hosts apply the last-known score like the whole-host-unreadable branch. Or reuse the object's previously applied benchmark from `appliedProfileByObject` when one is known. Only a readable version with no SCG gets the no-benchmark path.

### B3. The pak still bundles a dashboard built on the retired metrics

- **Where:** `adapter.yaml` `bundled_content` ships `dashboards/compliance-overview.yaml` (Compliance Fleet Overview); widgets read `Summary|total_hosts` (`:45`), `Summary|avg_host_score` (`:64`, `:168`), `Summary|hosts_below_threshold` (`:85`, `:173`), `Summary|profile_name` (`:105`).
- **Authority:** reviewer dimension 11 (shipped content that contradicts behavior is BLOCKING); `knowledge/rules/no-fabricated-metrics.md`; design § *Decided / Order* ("no pak is built without its dashboards").
- **What:** build 57 removes those attributes from describe.xml and stops pushing them (changelog item 5). After install, the bundled dashboard shows build 56's frozen last-writer-wins values (average host score, hosts below threshold, profile name) as if they were current. That is a fleet score no longer backed by any read, on the pak's own landing dashboard.
- **Fix:** drop `compliance-overview.yaml` from `bundled_content` in this build, or point its widgets at the per-vCenter rollup. Don't ship build 57 with it as-is. The design's Environment Overview replaces it.

## WARNING

### W1. Orphan-control cleanup depends on in-memory history; the "profile switch / Auto enabled" case is unproven

- **Where:** `ComplianceAdapter.java:61-67`, `:594`, `:637-641`; `docs/overview.md:103-107`; CHANGELOG item 3.
- **Authority:** skill § *Unreadable is NOT compliant* (stale signals); reviewer dimension 11.
- **What:** cleanup runs only when `appliedProfileByObject` holds the previous benchmark. The map is lost on collector restart, and switching an instance from a fixed profile to Auto is done by editing the instance. If that restarts or re-instantiates the adapter (unproven either way), the documented headline cases ("a profile switch", "Auto enabled") never clean up. Controls that only the old SCG evaluated keep `Compliant=0`, and their alerts stay open indefinitely with a runbook for a control that does not apply to the object's version. Also, `appliedProfileByObject.put` records the new benchmark before the push, and the framework swallows push failures, so one failed push during a transition also leaves the alerts open with no retry.
- **Fix:** make cleanup self-healing, not history-dependent. On an object's first cycle after start (`prev == null`), treat `prev` as the union of every loaded bundled profile's evaluated slice for that kind. Or push `-1` for every alertable control not in the current result set on a bounded schedule. Until proven, soften the docs claim.

### W2. Stale per-object and rollup values after a no-benchmark / nothing-evaluated transition

- **Where:** `pushNoBenchmark` `:1458-1469` and `pushProfileNamePropertyOnly` `:1436-1450` (no `total_count`, `fail_count`, `pass_count`, `unreadable_count`, `score`); `ComplianceRollup.java:151` (`avg_score` omitted when `scored==0`); `docs/overview.md:84-85` ("per-host compliance symptoms see no data").
- **Authority:** skill § *Unreadable is NOT compliant* (never a sentinel score); dashboard contract `compliance-esxi-hosts.md` ("shows blank score").
- **What:** Ops keeps a metric's last value when pushes stop. A host moving from SCG 8.0 to an unmapped version (or to version-unreadable, B2) keeps its old `score`, `fail_count` and `total_count`. The planned Host view, its heatmap and its summary average then show a score for an object the adapter says it did not score. The score-degraded alert keeps evaluating the frozen score. A vCenter whose scored count drops to 0 keeps its old `avg_score`. The contract's "shows blank score" holds only for an object that was never scored.
- **Fix:** adapter: push `total_count`, `pass_count`, `fail_count` and `unreadable_count` as 0 on the no-benchmark path so the counters are truthful. Content (register as a dashboard-authoring requirement): score columns, heatmap and the score alert must gate on `no_benchmark=0` and `total_count>0`. Correct the overview.md sentence.

### W3. The reproducibility gates are not wired into CI

- **Where:** `.github/workflows/build-pak-on-tag.yml` (no `ci/run_java_tests.sh`, no `generate_compliance_alerts.py --check`).
- **Authority:** `knowledge/rules/validate-before-install.md`; reviewer dimension 9.
- **What:** the generator's docstring calls `--check` "a reproducibility gate", but only a manual test run executes it. A hand edit inside the generated describe.xml blocks, or a profile change without regeneration, would ship through the tag build unchecked.
- **Fix:** add a CI step running `ci/run_java_tests.sh`, which already includes `--check`, before `build-sdk`.

### W4. The mixed-version simulation mirrors the adapter loop instead of running it

- **Where:** `tests/.../MixedVersionSimulationTest.java:19-23`.
- **Authority:** reviewer dimension 9 (prove behavior, don't assert it).
- **What:** the test drives the real selector, evaluator and rollup through a hand copy of the collect loop. `noteApplied` orphan cleanup, `vmHostVersion`, `collectVimObject`, `recordNoBenchmark`, the push payloads and the vCenter match are not exercised. The CHANGELOG line "VMs following hosts, vDS and portgroup following vCenter" is proven only against the mirror. The B2 and W1 paths are exactly the untested ones.
- **Fix:** extract the per-object decision (select, evaluate, push payload, orphan set) into an SDK-free class the adapter calls and the test drives. At minimum, add tests for the orphan set and the no-benchmark push payload.

### W5. Landing docs are silent on the foreign stitches

- **Where:** `docs/README.md` (generated: "Resource kinds: 1", no stitch or relationship mention), `docs/inventory-tree.md`.
- **Authority:** reviewer dimension 11 (unifi v1.1.0.11 origin).
- **What:** per-object pushes onto six VMWARE kinds, the new rollup on `VMwareAdapter Instance`, and 144 alerts on VMWARE kinds never appear in describe.xml, so the generated index cannot show them. The repo-root `README.md` and `overview.md` do cover them.
- **Fix:** add a hand-curated "Stitched onto VMWARE resources" pointer in the docs index (or a generator hook via `tooling`).

### W6. Devel acceptance premise is wrong: devel runs fixed SCG 9.1, not 9.0

- **Where:** the author's result reasoning (per the brief); `profiles/UNAUDITED_CONTROLS.md:490` ("devel runs 9.0", pre-existing and now stale: recon shows ESXi 9.1.1 on all hosts).
- **Authority:** `knowledge/rules/source-of-truth.md`; user rule "evidence over labels".
- **What:** no shipped doc asserts devel is on SCG 9.0 (the README's `VMware_SCG_9.0` upgrade example is illustrative only). But any acceptance plan built on it is wrong:
  - After upgrade, all three devel instances stay on **fixed** `VMware_SCG_9.1`. The devel install exercises fixed mode only, so Auto selection, mixed-version buckets and orphan cleanup stay unproven live until an instance is edited to Auto, and that edit is the W1 scenario.
  - Devel results change immediately in fixed 9.1 anyway. `vm.virtual-hardware` switches to the minimum comparison, and five 9.1 prose controls are demoted to manual review, so expect every VM's score to rise and the host totals to shrink.
- **Fix:** the acceptance plan must (a) record the stored `VMware_SCG_9.1` baseline, (b) edit one instance to Auto and verify orphan cleanup and alert cancellation live, and (c) correct the stale UNAUDITED line.

## NIT

- **N1.** `ComplianceAdapter.java:966-992`: `runtime.host` is read once per VM per cycle (one extra PropertyCollector round trip per VM). This is consistent with the existing per-object `name` reads, but it could be folded into the VM enumeration. Skill § *The bulk-read dynamic pattern*.
- **N2.** `scripts/normalize_scg_v67.py:4-8`: the docstring says only `scg_7.0.csv` must exist, but `_check_priorities` reads every `scg_<v>.csv` named in `ID_MAP` sources from the output directory (the rerun failed until `scg_9.1.csv` was present). Document the full prerequisite set.
- **N3.** The dashboard design docs define `non_compliant` as "fail_count > 0" (`compliance-environment-overview.md:55`, `compliance-esxi-hosts.md` flags section). The code (correctly) uses `fail>0 || unreadable>0`. Align the design text before the views are authored.
- **N4.** `ComplianceAdapter.java:1191`: `collectVimObject` gates on `countEvaluable(controls,"vim_property")==0`, while `evaluatedFor` and the generator also admit `esxcli` for cluster, vDS and portgroup. No such rows exist in any bundled profile today (checked), so this is latent only. Gate on vim_property + esxcli to keep the two rules identical.

## If shipped as-is

Operators get a bundled Fleet Overview dashboard showing frozen build-56 fleet numbers as current. A transient version-read fault makes a failing host look clean and cancels all its alerts for a cycle. In a lab with one VMWARE vCenter and a compliance instance on another, or with short `vcenter_host` names, one instance's rollup can overwrite another's.
