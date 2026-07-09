# SDK Adapter Review — compliance build 48

- **Adapter:** `content/sdk-adapters/compliance`
- **Build reviewed:** 48 (commit `8987db8`) vs CHANGES-REQUESTED 47 (`f24540a`)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Verdict:** **APPROVE**
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT
- **Scope:** verdict-scoped re-review of the build-47 CHANGES REQUESTED
  (1 BLOCKING per-resource sentinel-score leak, 1 WARNING asymmetric flap
  path, 1 NIT changelog format). Build 48 claims all three fixed.
- **Date:** 2026-06-10

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| Diff scope = only the two named fixes + version/docs | **Confirmed.** `git diff 47→48` touches exactly: `ComplianceAdapter.java` (the `AdvancedSettingsUnreadableException` branch rewritten 574–609; the `pushComplianceViaClient` guard added 1160–1164), `adapter.yaml` build_number 47→48, `REFERENCE.md` version string, `CHANGELOG.md` (1.0.0.48 entry + the 1.0.0.47 NIT reformat). No `ControlEvaluator` / `VSphereClient` source change; no describe/profile/content change. |
| pak-compare 48-vs-47 = 0/0/0 | **Confirmed by direct run.** `compare_paks(48, 47)` → "No structural divergences found. 0 BLOCKING, 0 WARNING, 0 INFO." describe.xml, profiles, resources, content all identical 47→48. |
| framework jar UNCHANGED (`9a1e5974…`) | **Confirmed by sha256.** `vcfcf-adapter-base.jar` = `9a1e59749edf56e0…` in both pak 47 and pak 48. No framework delta. |
| adapter jar differs as expected | **Confirmed.** `vcfcf_compliance.jar` 47 `0632edcc…` → 48 `1b090414…`. Compiled clean: 37 classes, `ComplianceAdapter` + `ControlEvaluator` + `AdvancedSettingsUnreadableException` all present, no `.java` leaked. |
| validate-sdk clean | **Inferred-confirmed** (same basis as build 47). The `sdk-buildkit` is not in this checkout (pulled from the published tarball at CI build time), so `validate-sdk` could not be re-invoked directly. The shipped `dist/…48.pak` compiled the build-48 sources into a well-formed adapter jar (all expected classes, no source remnants) — the compile-gate `validate-sdk` enforces. No discrepancy observed. |

## BLOCKING fix (build-47 #1) — RESOLVED

Traced **both** unreadable branches end-to-end into the wire push.

- **Connection-state branch** (ComplianceAdapter.java:541–568) and
  **adv-settings flap branch** (574–609) are now structurally identical:
  `evaluateControlsUnreadable(hostControls)` (adv) + `unreadableVimResult(hostControls)`
  (vim/esxcli) → `mergeResults` → `stats.unreadable += cr.unreadableCount`,
  `stats.total++` (no `scored++`, no `scoreSum`) → stitcher push → `continue`.

- **Both feed `mergeResults` a totalCount==0 result, proven:**
  - `evaluateControlsUnreadable` (ControlEvaluator.java:250) returns
    `pass=0, fail=0, total=0, unreadable=N, score=100.0` — the zero-divisor sentinel.
  - `unreadableVimResult` (ComplianceAdapter.java:986–1005) puts
    `VSphereClient.UNREADABLE` for every evaluable vim/esxcli control and passes
    that same sentinel to `evaluateVimProperties`; every value therefore hits the
    `actualObj == unreadableSentinel` branch (ControlEvaluator.java:376) →
    `unreadable++`, never pass/fail → `total = pass + fail = 0`.
  - `mergeResults` (1090–1099): `total = 0 + 0 = 0`; `score = total>0 ? … : 100.0`
    → merged `totalCount == 0`, score = sentinel 100.0.

- **The sentinel never reaches the wire.** `pushComplianceViaClient` now gates
  `score`/`pass_count`/`fail_count` behind `if (cr.totalCount > 0)`
  (ComplianceAdapter.java:1160–1164). For a `totalCount==0` unreadable host those
  three stats are **omitted**; only `total_count=0` + `unreadable_count` are
  pushed, plus per-control `|Actual`/`|Expected`/`|Description` (all honestly
  `(unreadable)`). The per-host symptoms (`host_compliance_score_warning.yaml` /
  `_critical.yaml`, LT 95 / LT 80) now see **no `score` data** rather than a
  green sentinel 100. `score=0` is correctly NOT substituted (would false-trip
  CRITICAL). Absent is the only honest per-resource value. The build-47 BLOCKING
  ("unreadable becomes a folded score=100 on a per-resource stat", skill
  § *Unreadable is NOT compliant*, zero-divisor contract) is closed for both
  branches.

## WARNING fix (build-47 #2) — RESOLVED

The `AdvancedSettingsUnreadableException` (flap-between-reads) branch no longer
folds only the advanced_setting channel while scoring vim/esxcli live from
cache. It now folds the WHOLE host (adv + vim/esxcli) UNREADABLE, identical
accounting to the connection-state branch: one loud WARN, `stats.unreadable +=`,
`stats.total++` only (never `scored`), no-score push, `continue`. The build-46/47
partial-score shape on the narrow flap window is eliminated — a host whose
OptionManager vanished can no longer publish a flattering partial vim score. The
two unreadable paths are now symmetric. Stats arithmetic: `unreadable` counted,
`scored` never incremented, `scoreSum` never touched, so the disconnected/flapped
host **cannot skew `avg_host_score`** (world rollup gates on `scored>0`, line 330).

## Diff integrity 47→48 — confirmed

- **Generic `catch (Exception)` adv-settings branch (610–618) UNCHANGED.** Still
  sets `advUnreadable=true` and falls through to evaluate vim/esxcli live — the
  build-47-reviewed behavior (a SOAP/transport fault on adv-settings is a distinct
  signal from a disconnect; surfacing the systemic failure while still scoring the
  vim channel was accepted in the build-47 review and is byte-identical here).
- **Healthy-host source path (620–649) UNCHANGED.** Same `evaluateControls` /
  `evaluateVimForResource` / `mergeResults` / `scored>0` gate / push as 47/46.
  pak-compare 0/0/0 and the byte-identical describe corroborate no healthy-path
  scoring change.

## NIT (build-47 #3) — addressed

The 1.0.0.47 changelog entry was reformatted from one wall-of-text paragraph
into the numbered-list form. Resolved.

---

## NIT (new, non-blocking)

- **[ComplianceAdapter.java:1160–1164 + docstring 1123–1126]** — the
  `if (cr.totalCount > 0)` guard was added inside the **shared**
  `pushComplianceViaClient`, which serves all six callers (host, VM, vCenter,
  cluster/vSAN via `pushOrProfileName`, world rollup). For the unreadable host
  branches this is exactly right. But it also changes the wire output for ANY
  caller reaching the push with `totalCount==0 AND unreadableCount==0`: builds
  46/47 emitted `|score=100, pass_count=0, fail_count=0` for such a resource;
  build 48 omits all three. The direct callers (host 647 / VM 700 / vCenter 756)
  push unconditionally, so a fully-readable resource whose profile slice happens
  to have zero evaluable controls would now lose its `|score=100`. In practice no
  real profile produces a healthy host/VM with zero evaluable controls (every
  resource carries many advanced_setting + vim controls), and the cluster path
  already routes a no-signal resource through `pushOrProfileName` — so this corner
  is effectively unreachable on real data, and the new behavior (no score where
  nothing was evaluated) is *more* honest, matching the world-rollup discipline.
  The finding is only that (a) the method docstring's "byte-identical to v1 /
  golden-comparison contract" claim (1124–1125) is now stale for the
  `totalCount==0, unreadable==0` corner, and (b) that corner is untested. No
  false-pass, no operator impact. → Optionally update the docstring to note the
  build-48 `totalCount>0` score gate, and confirm (or document as N/A) that no
  shipped profile yields a healthy zero-evaluable-control resource. Non-blocking.

## If shipped as-is

The build-47 silent false-pass is gone. An operator watching a flapping or
disconnected ESXi host (the esx04 scenario) now sees **no `VCF-CF Compliance|score`
on that resource** (absent, not a sentinel 100) plus a loud `unreadable_count`
and a WARN naming the host — the per-host WARNING/CRITICAL symptoms see "no data"
rather than green, and the world `avg_host_score` stays honestly suppressed. A
blind host can no longer masquerade as perfect, and the flap window can no longer
emit a flattering partial score. No new regression on healthy hosts (pak-compare
0/0/0, describe byte-identical, framework jar unchanged).

## Verification artifacts

- Framework jar sha (47 == 48): `9a1e59749edf56e0…` (matches brief `9a1e5974…`).
- Adapter jar sha 47 `0632edcc…` → 48 `1b090414…` (differs, expected).
- pak-compare 48-vs-47 (direct `compare_paks` run): 0 BLOCKING / 0 WARNING / 0 INFO,
  "No structural divergences found."
- Build-48 adapter jar: 37 classes, target classes present, no `.java` leak.
- No `build-sdk` run by this review; CHANGELOG.md/REFERENCE.md untouched.
  Adapter tree clean (the two untracked `knowledge/context/investigations/*.md` predate
  this review and are factory-side, not adapter source).
