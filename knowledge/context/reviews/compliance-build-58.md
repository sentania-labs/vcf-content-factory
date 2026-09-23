# SDK Adapter Review: compliance build 58 (re-review of build 57)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 58, commit `5e4a476`, vs build 57 `81cf55d` (delta) and build 56 `32de5aa` (pak-compare reference)
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.58.pak`
- **Prior review:** `knowledge/context/reviews/compliance-build-57.md` (3 BLOCKING / 6 WARNING / 4 NIT)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING / 4 NIT

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass.** 7 Java suites (new `ComplianceDecisionsTest` included) + generator unittest 12/12. |
| `generate_compliance_alerts.py --check` | **Up to date.** 144 / 144 / 144, kind and severity split unchanged from 57. |
| `validate-sdk` | **OK.** One benign `-source 11` warning. |
| `build-sdk` | **Reproduces.** My scratch build matches `dist/...58.pak` in every extracted file, including the adapter jar's classes; only zip timestamps differ. Bundled content: 1 view, 0 dashboards. Adapter tree clean after build. |
| pak-compare vs 56 | **0 BLOCKING / 1 WARNING / 8 INFO.** WARNING is the intended ComplianceWorld attribute retirement (6 to 1). INFO adds the Fleet Overview dashboard files now absent from the pak (B3 closure), the manifest description, and the five new profile files. |
| Registry | No `defects.local.md`; no open defect in `knowledge/context/defects.md` names `compliance`. |

## Build-57 finding closure (verified in code, not taken from the changelog)

| # | Closed? | Evidence |
|---|---|---|
| B1 stitch fallback | **Closed** | `ComplianceStitcher.matchVCenterAdapterInstance` delegates to `ComplianceDecisions.matchVCenter` (`:294-306`). A known UUID resolves only through `byUuid.get` (no fallthrough). An unreadable UUID gets an exact, case-insensitive VCURL match only. `singletonOfKind` deleted; prefix and display-name fallbacks gone. Tested: unknown UUID returns null even when a VCURL would match (`ComplianceDecisionsTest:150`). |
| B2 version unreadable | **Closed** | `Selection.versionUnreadable()` is split from `noBenchmark()`. `ComplianceDecisions.decide` (`:70-91`) reuses last cycle's benchmark, otherwise returns `VERSION_UNREADABLE`. The adapter then pushes `non_compliant=1` and `no_benchmark=0`, skips `afterPush` (no cleanup, tracker untouched), counts non_compliant plus the `unknown` bucket (`ComplianceRollup.recordVersionUnreadable`), and for hosts applies the last-known score (`ComplianceAdapter.java:724-730`). Applied uniformly on the host, VM, vCenter and vim-object paths. |
| B3 retired-key dashboard | **Closed** | `adapter.yaml` `dashboards: []`; confirmed absent from the built pak. The remaining bundled view reads only keys that are still pushed. |
| W1 in-memory cleanup | **Closed**, with a cost (see W1 below) | `AppliedBenchmarkTracker`: first sight means cleanup against the union of bundled profiles. The tracker is cleared on `configureAdapter` (`:146`) and every 24 cycles. `tracker.record` only after a push was attempted; skipped (retried) when profiles fail to load. |
| W2 stale counters | **Closed** (owner-accepted remainder) | The no-benchmark, nothing-evaluated and version-unreadable payloads zero pass/fail/total; evaluated objects always push pass/fail. `score` and `avg_score` stay omitted when nothing was scored (owner decision recorded). docs/overview.md now states the retained-score behavior honestly. |
| W3 CI gates | **Closed** | `build-pak-on-tag.yml` runs `--check` and `ci/run_java_tests.sh` after `setup-java` and before build-sdk. The test compile path needs no SDK jar (verified: `ComplianceDecisions` depends on `ComplianceAdapterConstants`, not the adapter). |
| W4 mirrored tests | **Closed** | `ComplianceDecisions` holds the decision, payload, orphan set, VM-follows-host and vCenter match logic, and the adapter calls it. `MixedVersionSimulationTest` drives it plus the tracker over two cycles (8.0-to-9.0 upgrade, reuse on version failure, new unreadable host). Remaining untested glue: `afterPush` ordering and early returns in the adapter (small, read and correct). |
| W5 docs pointer | **Closed** for the hand docs | `docs/overview.md` opens with "Stitched onto VMWARE resources" (per-object keys, rollup, alerts). Generated `docs/README.md` needs a generator hook, reported as a TOOLSET GAP; acceptable. |
| W6 devel baseline | **Closed** | The UNAUDITED line is corrected (devel is fixed `VMware_SCG_9.1`, ESXi 9.1.1). The README example uses 9.1. CHANGELOG item 9 carries an acceptance plan: record the fixed-9.1 baseline, edit one instance to Auto, prove selection, first-sight cleanup, alert cancel and rollup live. |
| N1 per-VM host read | **Closed** | `getVms` reads `name` and `runtime.host` in one container-view RetrieveProperties (`retrieveViewRows`). A SOAP fault returns null and falls back to the old walk with a per-VM read. A transport exception is caught by `collectVms`, same as before. |
| N2 v67 docstring | **Closed** | Documents both prerequisites and the output-directory lookup. |
| N3 design-doc drift | **Closed** (orchestrator) | Both dashboard designs now say `fail_count > 0 or unreadable_count > 0`. |
| N4 esxcli gate | **Closed** | `collectVimObject` gates on vim_property + esxcli. |

## Regression review of the new code

- **Cardinal rule.** No new path turns a failed read into a pass, a score or `non_compliant=0`. The version-unreadable object is non-compliant and never cleaned up. A reused benchmark scores real reads against the object's last applied SCG.
- **Crash-the-cycle.** `afterPush` catches loader failure (`bundledForCleanup` returns null and the cycle continues). Pushes are swallowed by the framework. The new VM bulk read throws only on transport failure, into the existing `collectVms` catch. No new unchecked path escapes the per-object loops. `ConcurrentHashMap` values are never null (`record` null-guards).
- **Stitch identity.** Only tightened. vim25 kinds are unchanged (MOID scoped by VC UUID since build 51).
- **Payload correctness.** The orphan set always excludes controls the current benchmark evaluates, so cleanup can never overwrite a live result in the same cycle.
- **CI edit.** Placement is correct, it needs no new action, and it uses the job's JDK 17.

## WARNING

### W1. First-sight / daily union cleanup creates and keeps alive per-control keys an object never had

- **Where:** `ComplianceDecisions.orphanControlIds` (`:218-235`, union branch); `AppliedBenchmarkTracker.startCycle` (`:67-75`); `ComplianceAdapter.afterPush` (`:630-662`); `docs/overview.md` ("they are harmless").
- **Authority:** skill § *Pushing data* and § *Unreadable is NOT compliant* (a `-1` is a signal, and this adds signals that describe nothing on the object); reviewer dimension 7 (no per-cycle growth that compounds) and dimension 11 (docs accuracy).
- **Measured cost** (computed from the bundled profiles with the generator's own scored rule). A 9.1-benchmarked object gets, on first sight after every collector start and instance edit, and again every 24 cycles:

  | Kind | Union of alertable controls | Keys the object never had (9.1 / worst case 6.7) |
  |---|---|---|
  | HostSystem | 86 | **38 / 71** metrics + the same number of `Actual` properties |
  | VirtualMachine | 23 | 1 / 14 |
  | vCenter | 15 | 6 / 8 (7.0) |
  | vDS | 11 | 4 / 7 |
  | Portgroup | 7 | 0 / 3 |
  | Cluster | 2 | 0 / 1 |

  On devel (fixed 9.1, never changed benchmark under v3 keys), the first build-58 cycle creates about 38 metric series and 38 properties on every host. None of them can hold a stale `0`, because v3 keys are new in build 57. The cost is bounded (at most the union size per object, never growing past 144 keys) and storage is trivial: one data point per key per sweep, and properties are stored only on change.
- **What it does cost:**
  - **Clutter.** Each host's metric browser gains roughly 38 `Compliant = -1` rows for other SCG versions. Any "Compliant is not 1" list or view picks them up alongside real unreadable controls, and -1 now means both "couldn't read" and "not in your SCG". Only `Actual` tells them apart.
  - **Kept alive forever.** The daily re-sweep re-pushes these keys forever, so they never age out as one-point series. Fleet-wide that is roughly 38 x hosts extra live metrics (about 19k at 500 hosts), plus a push burst every sweep cycle and every restart.
  - **Docs.** "Harmless" undersells it.
- **Benefit:** the union is only needed when history was lost AND the object previously held a `0` under a different benchmark. That means after a restart or edit coincident with a benchmark change, or a silently failed cleanup push. That scenario is real (the fixed-to-Auto switch on devel) but narrow.
- **A narrower set does the job.** The harm to prevent is a lingering `Compliant=0`, so clean only keys that exist on the object with a value of 0:
  - **Preferred:** on first sight and on the sweep, bulk-read the latest `VCF-CF Compliance|*|Compliant` values for the cycle's matched resources (one Suite API `stats/latest/query` per batch, same ambient identity the stitcher already uses for `/api/resources`). Push `-1` only for keys whose latest value is `0` and whose control the current benchmark does not evaluate. Zero keys created; it self-heals every cycle instead of daily, so the 24-cycle sweep can go.
  - **Alternative:** query active alerts from the 144 generated definitions and cancel only those whose control is not in the object's current benchmark.
  - **If neither is wanted now:** keep the union but make it a one-time pass (start or edit only), not a daily re-push, and reword the docs to state the key creation and the -1 overload plainly. That is an owner decision to record, as W2's avg_score was.
- **Ship risk:** correctness is fine. The cost is operational clutter and roughly 10% more live metric series on each host (38 against a few hundred VMWARE host metrics), not wrong data. Not blocking.

## NIT

- **N1.** `docs/overview.md` says "the counters are always pushed, zeroed when nothing was scored, so they are never stale", but `ComplianceDecisions.versionUnreadableStats` (`:175-183`) deliberately does not push `unreadable_count` (the javadoc explains why). Say so in the doc sentence.
- **N2.** `AppliedBenchmarkTracker.RESWEEP_CYCLES = 24` is labelled "one day at the default 60-minute interval", and the docs say "once a day". The collection interval is operator-editable (`monitoringInterval="60"` is only the default): at 5 minutes the union push runs every 2 hours. Tie the sweep to elapsed time (24 h since the last sweep), not to a cycle count, or document that it scales with the interval. Moot if W1's preferred fix removes the sweep.
- **N3.** The sweep clears `applied`, which is also B2's "benchmark last cycle" memory. An object whose version read fails on the sweep cycle (or the first cycle after start or edit) is reported as `unknown` / non-compliant instead of reusing its benchmark. That is conservative (never a pass), but it couples two concerns. Keep a separate "cleaned since" set so the sweep does not erase reuse memory.
- **N4.** The new CI gates run only in the tag-build workflow, so a stale generated block is caught at release rather than at PR time. Acceptable as a release gate. A push or PR workflow running the same two steps would catch it a round earlier.

## If shipped as-is

Correct compliance data and alert behavior, including across restarts and profile switches. Each host carries about 38 extra "not evaluated" per-control metrics (up to 71 on 6.7 hosts) that describe controls from other SCG versions and are re-pushed daily. They clutter its metric list and any "not compliant" metric listing, but they never fire an alert or change a score.
