# UniFi build 19 review (sdk-adapter-reviewer)

- **Adapter:** `content/sdk-adapters/unifi` (repo `sentania-labs/vcf-content-factory-sdk-unifi`)
- **Branch reviewed:** `build-19`, commits `0e0204e` (NVR storage-health properties, `NvrStorageHealth.java`) and `405923f` (7 symptoms, "NVR Storage At Risk" alert, 1 recommendation), on `origin/main` `4f6f3dc` (build 18)
- **Design:** `knowledge/designs/alerts/unifi-nvr-storage-at-risk.md`
- **Evidence:** factory branch `unifi-nvr-storage-health-apimap` (PR #298), `knowledge/context/api-maps/unifi-network-api.md` § `nvr` storage health fields
- **Factory main at review:** `4bd972e`
- **Verdict: CHANGES REQUESTED** (4 BLOCKING, 6 WARNING, 3 NIT)

## Bottom line

The adapter half is good: the reads are verbatim and present-only, an unknown
drive state counts as not healthy, an incomplete disk list publishes no counts,
nothing in the new path can throw, and the read-completeness rules from build 18
are untouched. The alert does fire on devel, but only through the
"Volume At Risk AND Issue Other Than Missing Drive" set. The other sets have
problems:

- The I/O Errors regex cannot match the published value under Ops's
  whole-value regex semantics.
- The `lacking_disk` exception suppresses a case where Protect's own UI
  shows the volume at risk.
- Bad sectors > 0 is the pak's own threshold, not Protect's.
- The CHANGELOG and alert docs say the build ships no NVR alert.

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | All pass, including `NvrStorageHealthTest` and `test_build19_storage_health`. |
| `validate-sdk` | OK. The SDK compat check is **skipped** for both 8.18.7 and 9.1.1 because no SDK jar is in `adapter_runtime/`, the same as earlier builds. |
| `build-sdk` (to scratchpad) | Reproduces `vcfcf_sdk_unifi_controller.0.0.0.19.pak`. |
| `pak-compare` vs `dist/…0.0.0.18.pak` | **0 BLOCKING, 1 WARNING, 8 INFO.** The WARNING is the UniFiNvr attribute count 22 vs 11: the 11 new keys, expected. The INFOs are the 8 new content files. |
| Dimension 13 (built `content/alertdefs/*.xml`) | No single-child `<SymptomSets>` (the NVR alert has 6), every ref resolves, and cycles are integers. Single-symptom sets use the bare `ref=` form, which appears 217 times in vendor `reference/`. |
| Metric vs property | `volume_health` and `volume_issues` are `isProperty="true"` string, and their symptoms render `type="property"`. `drives_failed`, `drives_not_healthy` and `drive_bad_sectors` are float metrics, and their symptoms render `type="metric"`. All match. |
| **Discrepancy** | `dist/vcfcf_sdk_unifi_controller.0.0.0.19.pak` in the factory is **stale**: it has no NVR alertdef or symptomdefs, so it was built before `405923f`. Anyone who installs it for the devel proof gets the properties without the alert. Rebuild before the proof. |
| Tree hygiene | My `build-sdk` regenerated `docs/inventory-tree.{md,svg,excalidraw}` with differences (see W5). I restored them with `git checkout`, so the adapter tree is clean as found. |

**Read-only controller probe** (UDM Pro, Protect 7.3.70): UniFi OS login,
`/proxy/protect/api/bootstrap` (`nvr` storage subtree), `/api/system`
(`ustorage`), the `/main-*.js` UI bundles, then logout. No secret was printed and
serials were dropped.
- The bootstrap matches the api-map exactly. md3 `health` is `atrisk` with
  `reasons` `[{"type":"io_err","level":"atrisk","slot":0}]`, and there is no
  `raid` block.
- `/api/system` md3 adds `error_count: 9` and
  `raid: {expected: 2, had_most: 1, members: ["sda5"]}`.
- The disk is slot 1, state `normal`, `reason` `[]`, `bad_sector` 0.
- `hardDriveState` is `hddNotCompatible`.

## Vocabulary verified against the console UI code

I read these from the UI bundles myself rather than relying on the api-map:

- **Volume.** A zod discriminated union on `health`: `health`/`healthy`
  (mapped to healthy), `atrisk`, or `failed`. A record with no `health` is
  treated as healthy. Colours are healthy green, atrisk orange, failed red.
  `reasons` is `.optional()`, and its `type` enum is the 8 values the pack
  documents. Matches the pack.
- **`lacking_disk` transform, verbatim:**
  `"primary"===e.space_type&&"atrisk"===e.health&&e.reasons?.length===1&&"lacking_disk"===e.reasons[0].type&&"atrisk"===e.reasons[0].level&&(!e.raid||e.raid&&e.raid.had_most<e.raid.expected)?{...e,health:"healthy"}:e`
- **Drive states.** `nodisk` and `broken` are separate union members, and
  the other 12 states are an enum. These match `OK_STATES` and
  `FAILED_STATES` plus the orange set. Colour map:
  - orange: `risk`, `spare_at_risk`, `foreign`, `repairing`, `incompatible`
  - red: `not_support`, `broken`, `faulty`
  - green: `initializing`, `expanding`
  - `spare` is `color-black` and `probing` is neutral
- **Drive transform.** At risk if `health==="at_risk"` or a risk reason is
  present. **`spare` with any non-empty `reason`, or at risk, becomes
  `spare_at_risk`.** `normal` plus at risk becomes `risk`. The protobuf path
  maps `status.BROKEN` to `broken`, so the pack's `health: broken` counting
  as failed is consistent.
- **Space transform.** When the volume is healthy, `action` is `repairing`,
  `raid.expected===2`, `had_most>=expected`, one drive is `normal` and one is
  `repairing`, the UI re-labels the `repairing` drive as `initializing`
  (green).

Every value the pack publishes is Protect's text copied out of the record.
Only the counts and the first-unhealthy-drive pair are computed, and they use
the UI's own classification. Nothing is fabricated.

## Per-question walk (the brief's checks)

- **Present-only.** Every property is guarded: `vol.health != null`,
  `issues != null`, the `drives != null` block, `metricIfPresent` for bad
  sectors, and `textPropIfPresent` for `hardDriveState`. `NONE` is published
  only for a real empty `reasons[]` or when no drive is unhealthy in a
  fully-read list. OK.
- **"Not healthy" including unknown states.** Drives: yes (`notHealthy`
  falls through to `!OK_STATES.contains`). Volume: **no** (W2).
- **Each symptom can fire on what is published.**
  - Volume Failed: yes.
  - Volume At Risk + Issue Other: yes.
  - Drive Failed and Drive Not Healthy: yes.
  - Drive Bad Sectors: yes, but it should not be in the alert (B3).
  - I/O Errors: **no** (B1).
- **The ALL set and `lacking_disk`.** `"lacking_disk:atrisk, io_err:atrisk"`
  is `!= "lacking_disk:atrisk"`, so the two-reason case fires. That is
  correct and matches the UI's `length===1`. The level check is mirrored
  too: `lacking_disk:warn` fires. The `raid` condition is **not** mirrored
  (B2), and an atrisk volume with no `reasons` list cannot fire (W3).
- **`(^|, )io_err:` against `type:level` joined with `", "`.** The format is
  right (`NvrStorageHealth.issues`, `String.join(", ", …)`), but the pattern
  only matches under find semantics (B1).
- **Healthy NVR.** No alert. The bad-sector case is an exception (B3).
  Separately, the INFO symptom "Issue Other Than Missing Drive" is
  permanently active on a healthy NVR (W1).
- **Devel.** `volume_health=atrisk` and `volume_issues=io_err:atrisk` trigger
  Volume At Risk and Issue Other, so set 2 fires and the alert fires (Warning,
  Health badge) after the symptoms' 3 wait cycles. The proof holds, but it
  exercises set 2 only. It says nothing about B1.
- **Build 18 vanished-object marking and `ProtectEdgeHold`.** Untouched.
  - The diff adds one call inside `collectNvr` plus the static
    `collectNvrStorageHealth`. `ReadKinds`, `ProtectEdgeHold` and
    `holdNvrSite` (`UniFiAdapter.java:1942`) do not change.
    `holdNvrSite` still decides "Protect read" from `s.protect` and the NVR
    MAC alone.
  - No new storage field takes part in read completeness.
  - The new path cannot throw:
    - `SimpleJson.get` on a non-object returns a null node.
    - `asString` never throws.
    - `UniFiValues.number` and `UniFiValues.text` are null-safe.
    - `drives()` sorts only after every `slot` is checked non-null.
    - A JSON `null` list entry becomes all-null fields: an all-null space
      is not selected, and an all-null disk makes `drives()` return null.

## Findings

### BLOCKING

- **B1. `symptoms/unifi_nvr_volume_io_errors.yaml`: the regex cannot match under Ops whole-value regex semantics.**
  - **Problem.** `(^|, )io_err:` has no trailing wildcard, so it matches
    `io_err:atrisk` only if Ops uses find (substring) semantics.
  - **Evidence for whole-value semantics:**
    - The vendor property regexes in `reference/references` are written for
      full matches. For example, `config|version` regex
      `vmx-[1-9]|vmx-1[0-2]` (HOL-2501 `autoscale-policy.xml:3332`) means
      "below vmx-13" only under full-match; under find, `vmx-13` would match
      via `vmx-1`.
    - All 23 vendor `msg_event` regexes end in `,.*`.
    - The VCF 9.0 docs' "matches regular expression" example is `.*8\.\d*`.
    - Precedent: synology build 35 accepted regexes only because they were
      anchored and correct under either semantics.
  - **Impact.** Under full-match, the I/O Errors set never fires. It is the
    only set that catches `io_err` on a volume whose `health` is still
    `health`, the case where the UI offers a file system repair. Devel will
    not reveal this, because set 2 fires there anyway.
  - **Fix.** Use `CONTAINS "io_err:"`, which the loader supports and which
    does not depend on regex semantics. Alternatively use
    `(.*, )?io_err:.*`, which is correct under both semantics. Add a wiring
    test that the pattern matches `io_err:atrisk` and
    `lacking_disk:atrisk, io_err:atrisk` with `re.fullmatch`.
- **B2. The `lacking_disk` exception suppresses a case Protect shows as at risk.**
  - **Where:** `alerts/unifi_nvr_storage_at_risk.yaml` (set 2) and
    `symptoms/unifi_nvr_volume_issue_other_than_missing_drive.yaml`.
  - **Authority:** skill § *Unreadable is NOT compliant*; author hard
    rule 4; lesson `unenumerated-exit-status-is-not-a-verdict.md` (the
    residual bucket is never the reassuring branch).
  - **The UI rule.** Protect's UI shows `lacking_disk:atrisk`-only as
    healthy **only** when there is no `raid` block or
    `raid.had_most < raid.expected`, meaning the array never had all its
    members.
  - **What the pack does.** It suppresses `lacking_disk:atrisk`-only
    unconditionally. REFERENCE.md says the bootstrap sends no `raid` block,
    but that is because Protect trims it, not because the volume has no
    RAID: `/api/system` on the same console carries it (devel md3:
    `expected 2, had_most 1`).
  - **Impact.** A once-complete array that lost a member (`had_most >=
    expected`, the dead drive now `nodisk` so no drive symptom fires) shows
    "Storage At Risk of Failure" in Protect and raises no alert. Both the
    alert description and the CHANGELOG say "as the Protect UI does", which
    is inaccurate.
  - **Fix (a design decision, Scott's call).** Either:
    - (a) read `ustorage.space[].raid` from `/api/system` and apply the full
      rule, and when it cannot be read, do not apply the exception; or
    - (b) drop the exception, alert on `atrisk` alone, and document that a
      never-completed array may alert where the UI shows healthy.

    Correct the description either way.
- **B3. The Drive Bad Sectors set in the alert fires on a drive Protect calls healthy.**
  - **Authority:** the design's Vision ("Alert when Protect reports the
    volume or a drive as not healthy") and Scott's rule (alert on Protect's
    own drive and volume health).
  - **Problem.** `drive_bad_sectors > 0` is the pack's threshold.
    Protect's own judgment is the `too_many_bad_sectors` reason, which
    `drives_not_healthy` already counts. A drive with a few remapped sectors
    reads "Optimal" in Protect and fires this alert.
  - **Fix.** Remove the Bad Sectors set from the alert. Keep the metric, and
    keep the symptom standalone or drop it. Update the description.
- **B4. Docs contradict the build** (dimension 11, author hard rule 9).
  - CHANGELOG 0.0.0.19 says "No symptoms or alerts in this entry; they are
    authored next", and no entry covers the alert, the 7 symptoms or the
    recommendation.
  - REFERENCE.md § Alerts says "ships eight alert definitions … fourteen
    symptoms … six recommendations". Its table, Symptoms and
    Recommendations sections have no NVR rows.
  - `docs/overview.md` § Alerts has the same eight, fourteen and six counts.
  - Shipped as-is, the pak's own docs deny the alert exists.
  - **Fix.** Add a CHANGELOG line, add the alert row (conditions, severity,
    badge, the `lacking_disk` behavior after B2) and the symptom and
    recommendation rows, and update the counts in REFERENCE.md and
    overview.md. Add a Limits line for the fullness exclusion.

### WARNING

- **W1. `unifi_nvr_volume_issue_other_than_missing_drive.yaml` is a standing active symptom on every healthy NVR.**
  - **Problem.** `volume_issues` is `none`, which `!=`
    `lacking_disk:atrisk`, so the INFO symptom is permanently triggered and
    listed on the object.
  - **Impact.** This misses "nothing fires on a healthy NVR" at the symptom
    level.
  - **Fix.** Have the adapter publish the UI's displayed health (Protect's
    transform, applied once the raid block is read for B2) as one property,
    and replace the AND pair with a single EQ. Otherwise, document the
    standing symptom.
- **W2. Volume health outside `health`/`healthy`/`atrisk`/`failed` never alerts** (skill § *Unreadable is NOT compliant*; the brief's "including unknown states").
  - **Problem.** Drives treat an unknown state as not healthy, but the
    volume path does not.
  - **Why it matters.** The UI's union is closed, so a new value is one
    Protect's own page cannot render either.
  - **Fix.** Add a set on `volume_health` `NOT_REGEX ^(health|healthy|atrisk|failed)$`.
    It is fully anchored, so it is correct under either semantics.
- **W3. An `atrisk` volume with no `reasons` list cannot fire set 2.**
  - **Problem.** `reasons` is `.optional()` in the UI schema, and the UI
    shows such a volume at risk because the exception needs exactly one
    reason. The pack publishes no `volume_issues`, so the property symptom
    has nothing to evaluate.
  - **Fix.** Fold into the W1/B2 displayed-health property.
- **W4. A "repairing" drive alerts during a rebuild the UI shows green.**
  - **Problem.** The UI's space transform shows a `repairing` drive as
    `initializing` (green) when the volume is healthy, `action` is
    `repairing`, the RAID is complete and one drive is `normal`. The pack
    counts it as not healthy, so Drive Not Healthy (Warning) fires during
    that resync.
  - **Fix.** Apply the transform once `raid` is readable (B2a), or document
    it in Limits.
- **W5. `docs/inventory-tree.{md,svg,excalidraw}` lag the factory generator.**
  - **Problem.** Regenerating with main `4bd972e` (which includes #291)
    adds the recursive Switch and Access Point nesting from build 18. That
    nesting was build 18 review W4, a toolset gap that is now fixed.
  - **Fix.** Regenerate and commit, so the shipped tree shows the uplink
    nesting.
- **W6. A hot spare with errors passes.**
  - **Problem.** The UI turns `spare` with **any** non-empty `reason` into
    `spare_at_risk` (orange: "This drive has errors and cannot serve as a
    hot spare"). `NvrStorageHealth.notHealthy` checks only the seven risk
    reasons, so `spare` plus `lower_rpm` counts as healthy. The UI's own
    classification is the authority the class Javadoc cites.
  - **Fix.** In `notHealthy`, treat a `spare` with non-empty `reasons` as
    not healthy, and add a test.

### NIT

- **N1.** `collectNvrStorageHealth` is silent in three cases: when
  `drives()` returns null (a disk entry without `state` or `slot`), when
  `primary()` returns null, and when there is no `ustorage`. Add a
  once-per-streak DEBUG or INFO log (the `StreakLog` idiom) so an operator
  can tell "not sent" from "could not use".
- **N2.** The `NvrStorageHealth` Javadoc and the api-map call `spare`
  green. The UI colour map has `spare: color-black`. This is cosmetic and
  does not change the count.
- **N3.** `SimpleJson.asString()` on an object or list returns
  `Map.toString()`. If Protect ever sent `health` or `state` as an object,
  the pack would publish `{...}` as text. It has not been seen; a string
  type check in the reader would close it.

## Registry check (`knowledge/context/defects.md`)

No open defect affects unifi. The unifi entries DEF-002 and DEF-007 are both
closed. The open entries affect other paks: DEF-004 (vcommunity-os), DEF-019
(factory:extractor), DEF-025 and DEF-026 (compliance). There is no
`defects.local.md`.

**Registration candidates if they survive acceptance:** B1 (a symptom that can
never fire), B2 (suppressing a state Protect shows as at risk), and W2/W6
(unhealthy states that pass).

## If shipped as-is

The devel NVR alerts correctly. Elsewhere:
- A RAID that lost a member and no longer sees the drive stays silent while
  Protect shows "At Risk".
- `io_err` on a volume Protect still calls healthy never alerts.
- A drive with a few remapped sectors that Protect calls "Optimal" raises a
  storage alert.
- The pak's CHANGELOG and alert docs say the alert does not exist.

---

## Round 2 (2026-10-28)

- **Commits reviewed:** `433bdca` (adapter: `volume_display_health`, `/api/system` raid read, W4/W6/N1/N3, docs tree), `2a0a450` (content: 5 symptoms, alert revised), `f718ce7` (doc counts). Branch `build-19`, tree clean.
- **Design revision:** `knowledge/designs/alerts/unifi-nvr-storage-at-risk.md` § Revision after review.
- **Verdict: CHANGES REQUESTED** (2 BLOCKING, 2 WARNING, 3 NIT). The adapter half is right. Both blockers are small: a stale landing README, and an operator symbol nobody has seen Ops accept.

### Claims check (re-run independently)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | All pass. `NvrStorageHealthTest` gains `displayHealth`, `lackingDiskException`, `rebuildRelabel` and `spareWithReason`, and `test_build19_storage_health` passes. |
| `validate-sdk` | OK. SDK compat is skipped for 8.18.7 and 9.1.1 because no jar is in `adapter_runtime/`, the same as round 1. |
| `build-sdk` (to scratchpad) | Builds `vcfcf_sdk_unifi_controller.0.0.0.19.pak`. The adapter tree stays clean afterwards, so the committed `docs/inventory-tree.*` match the generator (W5 resolved). |
| `pak-compare` vs `dist/…0.0.0.18.pak` | **0 BLOCKING, 1 WARNING, 6 INFO.** The WARNING is UniFiNvr attributes 23 vs 11 (the 12 new keys, now including `volume_display_health`). The INFOs are 1 alertdef and 5 symptomdefs. |
| Unzipped pak | 9 alertdefs, 19 symptomdefs, 7 recommendations, which matches the 9/19/7 claim and `adapter.yaml`. The NVR alertdef's `<SymptomSets operator="or">` has 5 children, each a bare `ref=` that resolves to a symptomdef in the same file. `waitCycle`/`cancelCycle` are integers. describe.xml has `volume_display_health` with nameKey 307, and `307=Volume Display Health` is in both resources.properties. Dimension 13 is clean. |
| Volume symptom types | All three volume symptoms render as `type="property"` on `Storage|volume_display_health`, `valueType="string"`. The drive symptoms stay `type="metric"`. |
| **Discrepancy** | `dist/vcfcf_sdk_unifi_controller.0.0.0.19.pak` in the factory is **stale again** (R2-W1). |

### Round 1 findings

| # | Status | Evidence |
|---|---|---|
| B1 I/O regex | **Resolved** (removed) | The symptom and the alert set are gone. An `io_err` on a volume Protect displays healthy no longer alerts, by design (Protect's verdict), and REFERENCE.md Limits says so. |
| B2 `lacking_disk` | **Resolved** | See "Display-health rule" below. |
| B3 bad sectors | **Resolved** | The symptom is removed from the alert and the pak. The metric is still published, and Limits says so. |
| B4 docs | **Partly resolved** | CHANGELOG, REFERENCE.md and overview.md are fixed. The landing `docs/README.md` still says eight alerts (R2-B1). Round 1 missed this surface; that miss is mine. |
| W1 standing INFO symptom | **Resolved** | The helper symptom is removed, and `volume_display_health` replaces the AND pair. |
| W2 unknown volume health | **Resolved, pending R2-B2** | `displayHealth` returns an unknown value verbatim, and the Unrecognised symptom catches it. |
| W3 `atrisk` with no reasons | **Resolved** | `reasons == null` is never forgiven. Test: "atrisk with no reasons list stays atrisk". |
| W4 resync relabel | **Resolved** (NIT R2-N1) | `rebuildRelabel`, applied only when the raid block was read. |
| W5 tree | **Resolved** | Regenerated. A fresh `build-sdk` leaves no diff. |
| W6 spare with reason | **Resolved** | `notHealthy`: `spare` with a non-empty `reasons` counts as not healthy. Tests cover it. |
| N1 silent skips | **Resolved** | `storageNote` covers no `ustorage`, no volume, raid unread on an `atrisk` volume, and an unusable disk list, once per streak per NVR (`StreakLog`, re-armed each cycle). |
| N2 spare colour | **Resolved** | Javadoc fixed. |
| N3 object as text | **Resolved** | `scalarText` returns null for an object or list, and is used throughout the storage path. The test asserts there is no raw `.asString()`. |

### Display-health rule vs the console UI bundle (probe data, read myself)

- **Source of the rule.** In `bundle3.js`, the zod schema `M` is a discriminated union on `health`, followed by `.transform(e=>"primary"===e.space_type&&"atrisk"===e.health&&e.reasons?.length===1&&"lacking_disk"===e.reasons[0].type&&"atrisk"===e.reasons[0].level&&(!e.raid||e.raid&&e.raid.had_most<e.raid.expected)?{...e,health:"healthy"}:e)`.
- **Its input carries `raid`.** The schema has `raid` (`expected`, `had_most`, `members`) and `error_count`, `resv_bytes`, and the protobuf path in `bundle1.js` builds `raid:c` too. That is the `/api/system` shape (`system_ustorage.json`), not the bootstrap's. So reading `raid` from `/api/system` is the right source.
- **`NvrStorageHealth.displayHealth` matches term for term:**
  - `primary` is required.
  - `reasons` must have size 1, and the single reason must equal `lacking_disk:atrisk`. Because `reason()` builds `type:level`, this is the same as the UI's separate type and level checks.
  - The raid condition is `s.raid != null && (!present() || hadMost < expected)`. `Raid.NONE` stands for a JSON `null` or absent block, which is `!e.raid` in the UI.
  - A block that is present but lacks a numeric `had_most` or `expected` becomes `null` (unread) and is not forgiven. In the UI, `undefined < n` is false, so it is not forgiven there either.
  - **The one deliberate deviation:** when the raid block is unread (call failed, device not listed, block malformed), the exception is not applied. This matches the design revision and is the safe side, since it surfaces rather than passes.
- **The device join is valid.** Bootstrap `md3` and `/api/system` `md3` are the same device.
- **Devel walk:**
  - Bootstrap md3 is `health: atrisk` with `reasons: [io_err:atrisk]`. With 1 reason that is not `lacking_disk`, it is not forgiven whatever the raid block says, so `volume_display_health = atrisk`.
  - Drives: slot 1 is `normal` with `reason []`, so `drives_not_healthy = 0` and `drives_failed = 0`.
  - The alert fires through set 2 (Volume At Risk, Warning), after 3 symptom wait cycles plus 1 alert wait cycle. The UI shows the same md3 as at risk.
- **Healthy NVR:**
  - `health: health` becomes `healthy`. Failed and At Risk do not match, and Unrecognised does not match (see below).
  - All drives `normal`/`spare` with no reasons give counts of 0.
  - Nothing fires, at the symptom level either: no standing symptom remains.
- **`lacking_disk` applied only per Protect's rule:**
  - Tests cover each case: no raid forgiven; `had_most < expected` forgiven; once-complete not forgiven; raid unread not forgiven; secondary not forgiven; a second reason not forgiven; level `warn` not forgiven.
  - Read in code: the exception is applied in exactly one place, `displayHealth`. Nothing else forgives `lacking_disk`, and the raw `volume_health` and `volume_issues` stay verbatim.
- **Resync relabel** (`R` transform): the conditions are display-healthy, action `repairing`, `raid.expected===2`, `had_most>=expected`, some disk `normal`, and some disk `repairing`. The pack matches these, with one ordering difference (R2-N1). The UI also re-labels the volume action to `syncing`. The pack leaves `volume_action` verbatim, which is harmless because nothing alerts on it.
- **Spare.** The UI's drive transform `w` is `"spare"===e.state&&(e.reason.length||t)` → `spare_at_risk`, which matches the new `notHealthy` branch.

### `/api/system` read

- **Request and auth.**
  - `UniFiApiClient.system()` is a GET only, on the same `ManagedHttpClient` and session cookie as every other call.
  - The framework replays once on 401/403, the same as for `stat/sysinfo`.
  - Errors are typed (`UniFiHttpException`), and the path goes through `redact`.
  - No secret can reach a log: the messages carry only the call name, status and `e.getMessage()`.
- **When it is asked.** Once per snapshot build, only when `s.protect != null`, and gated by its own `SysinfoGate` instance (`systemGate`).
  - After a 401/403/429 it is not asked again for 15 minutes, with one WARN per window.
  - Any other failure, or a payload with no `ustorage` object, is logged at INFO once per streak (`SYSTEM_STREAK`).
  - `InterruptedException` is rethrown. Every other exception is caught inside the snapshot build, so a failure never fails the snapshot and never touches `ReadKinds` or `ProtectEdgeHold`. The cost is only the exception, on the safe side.
- **Extra load.** One small GET per cycle on consoles running Protect, plus nothing on a refusing account beyond one ask per 15 minutes. `systemUstorage` is per snapshot and is not retained across builds. The streak keys are bounded (`StreakLog.open.retainAll(failedThisCycle)`). This is acceptable.
- **Still unproven (devel proof item, not a finding).** Whether the adapter's own account may read `/api/system`. If it is refused, a never-complete array whose only reason is `lacking_disk:atrisk` alerts while the UI shows it healthy, with a WARN every 15 minutes. That is surfaced, not passed, so it is safe. But the devel proof should show no `/api/system refused` WARN and no `raid ... was not read` INFO for the NVR.

### NOT_REGEX `^(healthy|atrisk|failed)$`

- **Semantics: correct under both models.** I checked with `re.fullmatch` and `re.search`:
  - `healthy`, `atrisk` and `failed` do not fire.
  - `health`, `degraded`, `atrisk2` and `Healthy` fire.
  - The anchors make whole-value and find matching agree.
  - `displayHealth` normalises `health` to `healthy`, so Protect's own word for healthy does not trip it.
  - An absent property cannot fire (present-only).
- **Wire symbol: unproven** (R2-B2).

### Findings

#### BLOCKING

- **R2-B1. `docs/README.md:57` contradicts the build** (dimension 11; round 1 B4).
  - **Problem.** The landing README says "The pak ships eight alerts with their symptoms and recommendations (build 16)" and lists only the eight older alerts. The pak ships nine, and the NVR alert is not mentioned on the landing page at all.
  - **Fix.** Update the sentence to nine (build 19) and add "NVR storage at risk" to the list.
- **R2-B2. The content-import operator `notRegex` has never been seen accepted by Ops.**
  - **Authority:** dimension 13 (what Ops checks at install); `knowledge/context/wire-formats/symptomdef_dt_condition_import.md`; lesson `knowledge/lessons/pak-content-bundling.md`.
  - **Where:** `symptoms/unifi_nvr_volume_health_unrecognised.yaml`, rendered as `operator="notRegex"`.
  - **No evidence it is accepted:**
    - The vendor reference XML in `reference/references` uses `regex` 29 times and `contains` 17 times, but never `notRegex`.
    - The 9.1.1 SDK jar has no such string.
    - No factory content using it has been installed.
    - The mapping in `knowledge/context/investigations/vcommunity_1006_emit_fidelity_fixes.md` was inferred from the pattern. Only `!=`, `<`, `>=` were observed there.
  - **Failure mode, per the `dt_above` precedent (Synology 0.0.0.35):** the importer throws `Invalid operator`, then drops this symptom, every other symptom in the same alertdefs file, and the NVR alert, **while the pak install reports success**. That would silently remove the whole NVR alert this build exists to ship.
  - **Fix: either one.**
    - (a) Prove it. After installing the rebuilt pak on devel, GET the symptom definition by name and the NVR alert definition, and record the result in that wire-format note (the orchestrator or api-explorer, not me).
    - (b) Use the verified `REGEX` with `^(?!(healthy|atrisk|failed)$).*`. It is correct under both full-match and find (checked), and needs no new wire evidence.

#### WARNING

- **R2-W1. The factory `dist/vcfcf_sdk_unifi_controller.0.0.0.19.pak` is a mixed build** (author hard rules 8 and 9; `knowledge/rules/validate-before-install.md`).
  - **Problem.** It was built at 06:48, between `433bdca` (06:48:04) and `2a0a450` (06:49:26), so it has the new Java with the round 1 content. Its NVR alert references the three removed symptoms (Bad Sectors, I/O Errors, Issue Other Than Missing Drive), and it lacks Volume Health Unrecognised.
  - **Fix.** Rebuild before the devel proof. If it was already installed on devel, content import does not delete, so the three orphan symptom definitions stay and must be removed by hand.
- **R2-W2. `REFERENCE.md:796-799` (Limits) says the pack logs a missing volume health, but it does not** (dimension 11).
  - **Problem.** The doc says an NVR whose Protect sends no volume `health` publishes no `volume_display_health` "(logged once per streak)". `collectNvrStorageHealth` logs no note when `vol != null && vol.health == null`. Only no-ustorage, no-volume, unread-raid-on-atrisk and unusable-disks are logged.
  - **Fix.** Add a `storageNote(mac, "health", ...)` for that case, or drop the claim.

#### NIT

- **R2-N1. `NvrStorageHealth.rebuildRelabel` tests the raw `normal` state.**
  - The UI tests the state after its drive transform, where a `normal` drive that is at risk is already `risk`, so the UI does not relabel.
  - In that case the pack relabels the `repairing` drive while the UI keeps it orange. The alert still fires through the at-risk drive, but `drives_not_healthy` reads 1 where the UI shows 2.
  - **Fix.** Require the `normal` drive to be `!notHealthy`.
- **R2-N2. `NvrStorageHealth.primary` leaves out the UI selector's third branch** (`Lo`: when the spaces carry no `space_type`, the UI takes the first).
  - This predates the round, and it is the safe side: nothing is published, and the `volume` note is logged.
- **R2-N3. The CHANGELOG 0.0.0.19 first bullet and `REFERENCE.md:417` call the bootstrap's `ustorage` "the same block UniFi OS serves at `/api/system`".**
  - The next paragraph correctly says the bootstrap trims the RAID block. Reword the first to "a trimmed copy of".

### Registry check (`knowledge/context/defects.md`)

No open defect affects unifi. DEF-002 and DEF-007 (unifi) are closed. The open entries affect other paks: DEF-004 (vcommunity-os), DEF-019 (factory:extractor), DEF-025 and DEF-026 (compliance). There is no `defects.local.md`.

**Registration candidate:** R2-B2, if the pak ships with `notRegex` and the install drops the alert. It would also be a factory renderer defect (`vcfcf_core/alerts/render.py` `NOT_REGEX` → `notRegex`, and likely the other unverified `not*`/`startsWith`/`endsWith` symbols), affecting `factory:alerts`.

### If shipped as-is

On devel, the volume logic alerts on the volume Protect shows at risk and stays quiet on a healthy NVR. But if Ops rejects `notRegex`, the whole NVR alert silently fails to import while the install reports success. The landing README also still says the pak has eight alerts.
