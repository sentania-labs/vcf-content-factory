# vsanperf build 23 (1.2.1) review

- **Adapter:** `content/sdk-adapters/vsanperf`, branch `build4/perfsvc-disabled-and-fault-isolation`, uncommitted working tree vs `main` 5528e7d (build 22)
- **Design (authoritative):** `knowledge/designs/vsanperf-mp-v3.md` section "1.2.1: Performance Service disabled", D1 to D8 (2026-11-08)
- **Reviewer:** sdk-adapter-reviewer, 2026-11-08
- **Verdict:** **block** (CHANGES REQUESTED). 1 BLOCKING, 3 WARNING, 6 NIT

## Claims check (independent re-runs)

| Claim | Re-run | Result |
|---|---|---|
| validate-sdk clean | `python3 -m vcfcf_managementpacks validate-sdk content/sdk-adapters/vsanperf` | **Confirmed** `OK`. The SDK compat check was skipped (9.1.1.0100 jar not in `adapter_runtime/`), same as every prior build |
| build-sdk reproduces | build-sdk to `/mnt/holding/vsanperf-review-23/dist` (TMPDIR off the /tmp tmpfs, which hit its quota) | **Confirmed.** The `.class` files in `vcfcf_vsanperf.jar` match the author's `dist/vcfcf_sdk_vsanperf.0.0.0.23.pak` byte for byte. Only zip timestamps differ |
| pak-compare 0 BLOCKING | vs `dist/vcfcf_sdk_vsanperf.0.0.0.22.pak`, both my build and the author's | **Confirmed** `0 BLOCKING, 0 WARNING, 4 INFO`: the two new content XMLs, `content/resources/resources.properties`, and the manifest description |
| Test suite green | `ci/run_java_tests.sh` | **Confirmed.** 17/17 classes print "all assertions passed", exit 0 (ReplayBudgetTest wall 235 s) |
| describe.xml import rules (dimension 13) | parsed the built pak's symptom and alert XML and `describe.xml` | **Clean.** No `<SymptomSets>` container anywhere: one bare `<SymptomSet>` sits under `<State>`, and its `ref` resolves to the bundled symptom id. `waitCycle="2"` and `cancelCycle="1"` are integers. The recommendation key resolves. nameKeys 44 and 45 are in both `resources.properties` copies inside the pak |
| Fixture provenance | `cmp` against `reference/docs/extracted/vsan-osa-probe/01-{esa,osa}-vsanclustergetconfig.json`; diffed `-false.json` against `-absent.json`; grepped the build-22 devel log for the fault text | **Honest.** `enabled` and `absent` are byte-identical to the captures. `false` differs from `absent` only by the inserted `perfsvcConfig` block. The pfcCountRaw faultstring matches the devel log verbatim, with kaReset on 5 log lines. The envelope follows `05-osa-queryperf-disk-group.json` without `faultMessage`, as the README says |
| `content_foreign_adapter_kinds` is a real feature | `src/vcfcf_managementpacks/sdk_project.py:33,728`, `sdk_builder.py:4806-4828`, added in factory #283 (before buildkit 1.0.25, which CI pins) | **Real.** It is an explicit opt-in that extends the set of foreign kinds content may target. It is not a bypass: any other kind is still an error, and own-kind content is still checked against describe.xml |
| Config call path is the vim25 `vsan/` namespace, not `/vsanHealth` | `VsanJsonClient.configPath()` vs `PROVENANCE-2026-11-07.md` line 24 | **Confirmed** the captures used `POST /sdk/vim25/<release>/vsan/VsanVcClusterConfigSystem/vsan-cluster-config-system/VsanClusterGetConfig`. ClientFakeServerTest pins path and body |

## BLOCKING

**B1. A 15-minute vSAN endpoint outage turns into a 24-hour, fleet-wide data blackout that reports healthy.**

- **Where:** `CycleEngine.java` `typeFault` 1988-1997, called from 1811, 1835 and 1852, and the every-call-failed rule at 1906-1912.
- **Authority:** skill § *Unreadable is NOT compliant*, `knowledge/lessons/unreadable-is-not-compliant.md`, reviewer dimension 1.

D8 makes every server fault, including any non-timeout `IOException` (`StatusException` for a 502/503 with no fault body, connection reset, `OverCapException`), a strike on its type. Core types are now included, and the strike is committed even in a cycle the W1 rule declares a whole-cluster failure ("every call failed"). The fault is then plainly not type-specific, yet each type still takes a strike. After three such cycles every type except `ioinsight` is learned-skipped for 24 h. On the next cycle the cluster makes 0 or 1 calls and counts `clusters_ok`. `last_error` reads `none`, the cycle does not fail, and nothing is pushed. When the re-probe faults again it re-learns at once, because the strike is held at 3.

I proved this with a scratch probe that compiles against `src`+`tests` and is not in the repo. Every call returns `IOException("HTTP 503")` for 3 cycles, then the server answers normally:

```
core-only cycle 1-3: calls=3  ok=0 failed=1 ... FAILED: every call failed
core-only cycle 4:   calls=0  ok=1 failed=0 skips=3  series=0 failure=null last_error=none
default   cycle 1-3: calls=26 ok=0 failed=1
default   cycle 4:   calls=1  ok=1 failed=0 skips=25 series=0 failure=null last_error=none
```

Build 22 never learned a core type on a server fault, so the same outage showed `clusters_failed` for its duration and recovered on the first good cycle. The same mechanism also gives "permanently OK while pushing nothing" when a cluster's core types all fault for a genuinely type-level reason with `tier_cluster`/`tier_host` off. PerfsvcEngineTest `strikesResetOnAnAnswer` runs the all-fault case for one cycle only, so it cannot see this.

**Smallest fix**, two parts. Both amend the wording of D8, so Scott should confirm them.

1. Defer the strike commit to the end of the cluster task. Strike the types only when the cluster ends OK. When the every-call-failed rule (or any cluster-level failure) fires, call `noStrike` for that cycle's struck types, because a fault on every call is not a type fault.
2. A cluster whose three core types are all skipped as fault-learned this cycle must not count `clusters_ok`. Either count it failed with `last_error` "core types skipped after server faults", or exclude core types from server-fault learning. In the second case they are still counted in `required_calls_failed` every cycle, at a cost of one call per faulting core type.

Add an engine test: all-503 for 3 cycles, then healthy. Cycle 4 must make 26 calls and push data.

## WARNING

**W1. masternotfound detection is only tested on a hand-built fault, never on the verbatim capture.**

- **Where:** `PerfsvcEngineTest.java:208-215`, `VsanFault.isMasterNotFound`.
- **Authority:** skill § *Unreadable is NOT compliant*, reviewer dimension 2. The skeptic default says this has to be proven.

The test constructs `new VsanFault("NotFound", ..., List.of("...masternotfound"))`. No test runs the captured body (`reference/docs/extracted/vsan-osa-probe/05-osa-queryperf-disk-group.json`, `faultMessage[0].key`) through `VsanFault.parse(...).isMasterNotFound()`. By reading the code I find that it parses correctly today. But D8 now routes every unrecognised `VsanFault` into strike-and-learn. If key extraction ever regressed, a disabled cluster whose config read fails would learn every type and go silent-OK. **Fix:** copy the 05 capture into `tests/fixtures/vsan-perfsvc-json/` verbatim and assert `isMasterNotFound()` on it, plus one engine cycle through that fixture.

**W2. Docs parity: the operator-facing docs say nothing about the bundled alert or the disabled-cluster skip.**

- **Where:** `docs/overview.md` (packed into the pak), `docs/README.md` (landing page), `REFERENCE.md`, `README.md:624`.
- **Authority:** reviewer dimension 11; design "Describe / docs / version" ("a Bundled content section names the three items").

What each surface has today:

- `overview.md` has no mention of the Performance Service state, the skip, or the symptom, alert and recommendation.
- The landing `docs/README.md` gains only the `vSAN Perf|Performance Service|*` key-group row.
- `REFERENCE.md` has no "Bundled content" section, which the design requires.
- `README.md` mentions the alert only inside acceptance check 8. Its "Bundled content (optional)" section is still template boilerplate ("dashboards/views").

**Fix:** add a Bundled content section to REFERENCE.md naming the three items with the key, threshold and wait/cancel values. Add a paragraph to `overview.md` and to the README intro.

**W3. Registration candidate (RULE-012), not a separate defect.** If B1 is accepted as "known" rather than fixed, register it against `vsanperf` before any `v1.2.1` tag. The defect-gate would otherwise pass a pak with a known silent-OK path.

## NIT

**N1. D3 deviation is under-stated in the CHANGELOG.**

- **Where:** `CycleEngine.java:1818-1828`, `CHANGELOG.md`.

D3 says "Unchanged", but `masternotfound` on a non-core type now fails the cluster. In 1.2.0 it was an optional failure. During a mid-task stats-primary re-election after the core types answered, 1.2.1 reports FAILED where 1.2.0 reported OK. Data is still pushed because there is no break, so this is acceptable and arguably more honest. But the CHANGELOG names only batching faults as "now on any type". Say it for masternotfound too, and record it in the design.

**N2. No loop break after `masternotfound`.**

- **Where:** `CycleEngine.java:1828-1830`.

On a cluster with the service off whose config read is unknown, the task still makes every remaining call, 26 at `dashboard` and 61 to 67 at `all`, each faulting the same way. This is unchanged from 1.2.0. A break after the first masternotfound, once at least one core call is made, would save that.

**N3. The cycle summary's per-tier breakdown no longer adds up to `series_pushed`.**

- **Where:** `PushBuffer.add` 2306-2307.

The state value is counted in `series_pushed` but in no tier, so the by-tier breakdown is off by one per cluster with a definite read. Document it, or show it as `state=N`.

**N4. The unresolved-cluster WARN is misleading with `tier_cluster` off.**

- **Where:** `CycleEngine.java:1484-1493`.

The WARN says "their cluster tier data is not pushed". With `tier_cluster` off, what is lost is the Performance Service state (D7).

**N5. The alert's type code and the content names drift from the design.**

- **Where:** `alerts/vsanperf_performance_service_disabled.yaml:6`.

`type: 16` is Virtualization/Hypervisor, while the design says storage (18) / configuration. The alert and recommendation names also differ from the design table. Either is fine if intended: record the chosen names and codes in `knowledge/designs/alerts/vsanperf-performance-service-disabled.md`.

**N6. Dedup marks are not cleared on re-enable, contrary to the D2 text.**

The deviation is correct in effect. Marks are keyed by entity and label, and they only suppress buckets already pushed, which is the right behaviour after an outage shorter than 24 h. Add a one-line addendum to the design so the text matches the code.

## Checked and found safe (hunt list a to g)

- **(a) Disabled path:**
  - `readPerfsvc` runs before the type loop and returns DISABLED with 0 calls. The disk and VM reads are lazy inside the loop, so they never run.
  - `plan()` side effects are discarded by `clusterState.remove`.
  - DISABLED counts only `clustersPerfsvcDisabled`. It is settled, so never cut and never `restartAt`, and it is excluded from `furthest`.
  - `last_error` is untouched.
  - `collectible` excludes disabled clusters from the whole-cycle failure check.
  - The 0/1 value is pushed with `tier_cluster` off (D7, tested) and never pushed on unknown (tested for 503, timeout, NotAuthenticated, HTML, `[]`).
  - Config failure: `IOException|RuntimeException` gives unknown. `InterruptedException` propagates to TIMED_OUT. The timeout is `min(callTimeout, left)`. The call is outside `callMs`/`perf_calls` and inside `wallMs` and the deadline (ReplayBudget row f').
  - The WARN fires once per cluster per refresh and logs the fault class only.
- **(b) Strikes:**
  - A VM type strikes only on VM runs, because the `continue` comes before the try, so cadence cycles neither strike nor reset.
  - `noStrike` in `finally` resets the count on any non-strike outcome.
  - The 24 h re-probe is driven by `T.CLOCK` (+25 h, tested). Empty-streak and fault-streak reset each other.
  - `last_error` names the type while it is called and reads `none` after it is learned.
  - `required_calls_failed` and `optional_calls_failed` partition by `TypeFailure.required = tier == CORE`, so nothing is counted twice. A RuntimeException on a core type still fails the cluster as in 1.2.0.
  - The every-call-failed rule's added `!optional.isEmpty()` guard is unreachable-safe.
  - The only defect found here is B1.
- **(c) masternotfound:** the 1.2.0 core path is unchanged. The non-core change is N1, the missing break is N2.
- **(d) Stitch push:**
  - The value goes to `opsClusters.resourceId(moid)`, the same (MoRef, VCID) resolver the cluster tier uses.
  - It is stamped `stateTs` = cycle start, a new timestamp every cycle, and carries no dedup mark, so a constant 1 is never suppressed.
  - It shares the (CLUSTER, ts) push group, and a failed batch drops only that cycle's value.
- **(e) Content:** the symptom key `vSAN Perf|Performance Service|enabled` equals `EntityType.ROOT + "|Performance Service|enabled"` exactly. The XML is well-formed and its refs resolve (table above).
- **(f) Tests:**
  - The `T.CLOCK` pin at 2026-11-07T14:00Z sits inside 24 h of every fixture sample (00:05Z to 13:50Z on 11-07), and fakes never enforced the query window, so the pin masks nothing.
  - `PerfsvcEngineTest` asserts each D1-D8 claim it names.
  - The `vmReadsSerialize` fix (advancing the shared clock while holding the permit) is sound.
- **(g) Conformance:** RULE-008: the new log lines carry moid, name, fault class and a scrubbed fault text, with no credential or session id. nameKeys 44 and 45 are present. The REFERENCE.md row is checked by `ReferenceDocTest`. `build_number` 23 has a matching CHANGELOG entry.

## Registry check (`knowledge/context/defects.md`)

No open defect names `vsanperf` (27 entries; `Affects:` covers compliance, synology, unifi, vcommunity-*, factory:*, two dashboards). Nothing to re-assert or close. W3 is a registration candidate if B1 ships unfixed. There is no `defects.local.md`.

## If shipped as-is

A routine vsan-health restart or a 15-minute vSAN endpoint outage leaves every cluster collecting nothing for the next 24 hours. Meanwhile the adapter reports `clusters_ok`, `last_error none` and a clean cycle, and operators trust dashboards that have gone flat.
