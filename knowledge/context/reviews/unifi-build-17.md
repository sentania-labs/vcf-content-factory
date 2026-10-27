# UniFi build 17 review (sdk-adapter-reviewer)

- **Adapter:** `content/sdk-adapters/unifi` (repo `sentania-labs/vcf-content-factory-sdk-unifi`)
- **Branch reviewed:** `feat/poe-budget-used-pct`, uncommitted on `8f0aa31`
- **Built pak (reviewer build, from the tree):** `vcfcf_sdk_unifi_controller.0.0.0.17.pak`
- **Factory tree:** branch `sdk-bundled-content-checks` (validate-sdk checks symptom keys against describe.xml and sub_type 18-22)
- **Date:** 2026-10-27
- **Current verdict (round 3): APPROVE** (0 BLOCKING, 2 WARNING, 2 NIT)
- This file supersedes `unifi-build-16.md`; rounds 2 and 1 are carried below unchanged.

---

## Round 3: fixes for the round-2 findings (build 17)

### Bottom line

Every round-2 finding is fixed or answered in the docs. WAN Degraded now
requires a WAN whose link is up, so the lab's unplugged WAN 2 will not
fire. Camera Not Recording skips cameras set never to record. The five
boolean properties publish only when the field is sent. The subTypes are
in the platform's 18-22 range. Two things remain before install, and
neither blocks. First, nothing in the repo proves what Protect's
`isRecording` reads for a `detections` or `schedule` camera between
events, so Camera Not Recording's behavior on those modes is a devel-proof
item (W1). Second, the only 0.0.0.17 pak the author built predates the
scoping YAML and still renders the unscoped WAN Degraded. It must not be
the pak that gets installed (W2).

### Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | All pass: 11 Java (incl. `UniFiValuesTest.flagAbsentIsNotFalse`, `recordingModeText`) + 13 Python (incl. new `test_present_only_flags`). |
| Wiring test strength | Mutation-checked in scratch, 5/5 killed: camera `is_connected` back to `asBoolean()`, port `up` back to `asBoolean()`, WAN `Status\|up` removed, `flagPropIfPresent` publishing `"false"` on absent, `recording_mode` via plain `prop(... asString(""))`. |
| validate-sdk (factory `sdk-bundled-content-checks`) | Confirmed `OK` (SDK compat ran vs 9.0; 8.18.7 and 9.1.1.0100 skipped, jars absent, as before). The new checks bite. On scratch copies, all four mutations failed validation: a bogus symptom key, a key in the wrong group, `sub_type: 3`, and a property key declared as `metric_static`. |
| build-sdk | Reproduces from the tree. Side effect, disclosed: the build regenerated `docs/README.md` and `docs/inventory-tree.md` in the adapter tree, and their version stamp moved from 0.0.0.16 to 0.0.0.17. That is ordinary generator output. It also shows the author never ran build-sdk on the tree itself (see W2). |
| pak-compare 17 vs 0.0.0.15 (`dist/`, sha256 `797f74c4...`, same file as round 2) | 0 BLOCKING, 3 WARNING (attribute count +1 on UniFiCamera, UniFiSwitch, UniFiWanInterface: exactly `Configuration\|recording_mode`, `PoE\|poe_budget_used_pct`, `Status\|up`), 23 INFO (8 alertdefs, 14 symptomdefs, `content/resources/resources.properties`). |
| Author's pak (`scratchpad/b17/dist/...0.0.0.17.pak`) | **Differs.** Same describe.xml, resources, jar inputs, but `content/` lacks `WAN Link Up` and `Camera Recording Enabled`, and its WAN Degraded is the build-16 single `or` set. See W2. |
| defect-gate | `no open blocking defects affecting unifi`. |

### Round-2 findings, re-checked

| Finding | Status | Evidence |
|---|---|---|
| **B1** WAN Degraded on unused WAN 2 | **FIXED** | UniFiAdapter.java `collectWanInterface`: `flagPropIfPresent(out, "Status\|up", wan.get("up"))`, outside the informing guard; describe.xml `UniFiWanInterface` `Status\|up` string property (nameKey 268/269, labelled). `symptoms/unifi_wan_link_up.yaml` (`Status\|up` EQ `"true"`, Info). Rendered alertdef: `<SymptomSets operator="or">` with two `and` sets, each `WAN Link Up` plus one of Availability Low / Latency High. An unplugged WAN (link down) or one whose `up` is never sent cannot satisfy either set. `up` is a live-observed field on both `wan1` and `wan2` (`knowledge/context/api-maps/unifi-network-api.md`, gateway metrics list). REFERENCE.md, Alerts, Limits states that a configured WAN losing its link is not alerted, which meets the round-2 requirement ("say so in REFERENCE.md"). |
| **W1** camera set never to record | **FIXED** (with new W1 below) | `Configuration\|recording_mode` from `recordingSettings.mode` via `textPropIfPresent` (the `get().get()` chain is null-safe, `SimpleJson.get` returns an empty node on a missing key or non-map); `symptoms/unifi_camera_recording_enabled.yaml` (`!=` `never`, Info); alert is a three-symptom `and`. Property `!=` has corpus precedent (80 `operator="!="` property conditions under `reference/`). A camera without the field never fires, and the Limits section says so. |
| **W2** absent flag read as `false` | **FIXED** | `UniFiValues.flag` returns null for absent, blank, free text, NaN; `flagPropIfPresent` publishes only non-null. Applied to port `up`, `is_uplink`, camera `is_connected`, `is_recording`, WAN `up`; port `duplex` also present-only. `flag()` cannot throw (`number()` regex-gates and catches). Unit + wiring tests, mutation-checked. |
| **W3** sole-uplink loss shows as Switch Offline | **FIXED in REFERENCE.md** (Alerts table + Limits). The alert's own description is unchanged (N1). |
| **W4** subType outside the enum | **FIXED** | Rendered: offline/down/not-recording 18, WAN 19, PoE 20. validate-sdk on this branch now rejects anything outside 18-22. Factory side is being fixed on `sdk-bundled-content-checks` (`src/vcfcf_core/alerts/loader.py` `VALID_SUBTYPES`, `content/alerts/synology_*` moved to 18/19/20), so the round-2 `factory:alerts` registration candidate is moot once that branch lands. |
| **N1** inform error raises nothing | Answered: documented in Limits. Accepted as a judgment call. |
| **N2** stale holds | **FIXED**: Limits, "Stale holds" (WAN while gateway not informing, forgotten device, integrated console). |
| **N3** recommendation file name | **FIXED**: `recommendations/unifi_investigate_disconnected_camera.yaml`. |

### Rendered pak (dimension 13)

I parsed all 8 `content/alertdefs/*.xml` and 14 `content/symptomdefs/*.xml`
from my build. Only one `<SymptomSets>` wrapper exists (WAN Degraded) and
it has two children. Every other alert carries a single bare
`<SymptomSet>` under `<State>`. Every `ref` resolves to a definition in
the same file, on the alert's own resource kind. Every symptom key exists
on its kind with the matching property/metric type. Symptom definitions
duplicated between `symptomdefs/` and `alertdefs/` are identical.
`waitCycle`/`cancelCycle` are integers (3/3). Every referenced
recommendation is defined, and the adapter's `describe.xml` carries no
alert content. No duplicate `ResourceGroup` keys per kind and no
duplicate nameKeys.

### Dimensions 1-8 on the Java delta

1. Present-only is the right direction here: an absent read now raises
   nothing, never a `false` that alerts.
2. N/A (no vim25).
3. No new try/catch; the helpers cannot throw.
4-5. N/A.
6. No new logging.
7-8. One extra map lookup per object; no allocations of note.

Dimension 9: `build_number` 17, CHANGELOG 0.0.0.17 entry, minimal diff.
Dimension 11: REFERENCE.md, overview.md and the landing README (via
`_index_extra.md`) are consistent with the rendered conditions.

### Findings (round 3)

#### WARNING

- **W1** `symptoms/unifi_camera_recording_enabled.yaml`, `alerts/unifi_camera_not_recording.yaml`,
  REFERENCE.md Alerts Limits. Authority: reviewer doctrine (unproven is a
  finding); dimension 10/11. No source in the repo says what Protect's
  `isRecording` reads for a camera in `detections` (or `schedule`) mode
  between events. The docs assume two things that are hard to hold
  together. They warn that a `schedule` camera "can fire outside its
  scheduled hours", which treats `isRecording` as "actively recording now".
  Yet they treat `detections` as safely covered. If `isRecording` is
  false between detections, every detection-mode camera holds a Warning on
  Health most of the day. The lab read 12/12 `is_recording = true` on
  2026-10-16, but the cameras' modes were not recorded, so that proves
  nothing either way. Fix: in the devel proof, record each lab camera's
  `Configuration|recording_mode` and `Status|is_recording` across several
  idle cycles. If a `detections` camera reads `false` while idle, narrow
  the scope (for example, `recording_mode` EQ `always`) or document the
  behavior next to the `schedule` caveat. **Registration candidate**
  (`Affects: unifi`) if the proof shows the false positive and it ships.
- **W2** `scratchpad/b17/dist/vcfcf_sdk_unifi_controller.0.0.0.17.pak`
  (author build), adapter `docs/README.md` / `docs/inventory-tree.md`.
  Authority: `knowledge/rules/validate-before-install.md`; claims check.
  The only author-built 0.0.0.17 pak was built from a copy before the
  scoping YAML landed. Its WAN Degraded is the unscoped build-16 condition
  (B1 again), and it has no `WAN Link Up` or `Camera Recording Enabled`.
  It has the same version number as a correct build, so it cannot be told
  apart by name. Fix: discard it; the install candidate is a fresh
  build-sdk from the tree (mine reproduces). Commit the regenerated docs
  stamps (0.0.0.17) with the build.

#### NIT

- **N1** `alerts/unifi_uplink_port_down.yaml` description still reads
  "Fires when a switch port that serves as an uplink has lost link" with no
  caveat. Round-2 W3 asked for the sentence in the alert description too,
  because the description is what an operator sees in Ops. Add: "A switch
  that loses its only uplink shows as Switch Offline instead."
- **N2** Devel proof for B1: confirm on the lab that WAN 1 reads
  `Status|up = true` and WAN 2 reads `false`. The field is live-observed on
  both objects (API map), but the value on the unplugged WAN 2 is not
  recorded. If `up` were not sent, WAN Degraded would go silent on every
  WAN (fail-safe, but silent).

### Defect registry (knowledge/context/defects.md)

No `defects.local.md`; the inherited registry governs. `Affects: unifi`:
DEF-002 (closed), DEF-007 (closed). **No open defect affects this pak**
(defect-gate agrees). The round-2 B1 candidate is resolved in this build.
The round-2 W4 `factory:alerts` candidate is being fixed on the factory
branch. New candidate: round-3 W1, only if the devel proof shows the
false positive.

### If shipped as-is (from a fresh build of the tree)

No alert fires on the unused WAN 2. Cameras set never to record are
skipped, and a missing field raises nothing. Whether detection-mode
cameras raise Camera Not Recording between events is unproven. The
offline, PoE and uplink alerts behave as documented.

---

## Round 2: bundled symptoms, alerts, recommendations (issue #30)

Scope: 12 symptoms (`symptoms/`), 8 alerts (`alerts/`), 6 recommendations
(`recommendations/`), wired by `adapter.yaml` `bundled_content` with
`content_naming: factory_prefixed`; CHANGELOG, REFERENCE.md, docs/overview.md,
docs/_index_extra.md (merged into docs/README.md). Java unchanged since round 1.

### Bottom line

The wiring is clean: every symptom key exists on the right resource kind with
the right property/metric type, values match what the collector writes, every
alert's symptoms sit on the alert's own kind, and the rendered XML is
structurally sound. One alert is wrong on day one: **WAN Degraded fires
permanently on an unplugged second WAN**, and this lab has one (B1). Three
other alerts have false-positive or false-negative edges that are neither
scoped nor documented (W1 to W3), and every alert carries a subType outside
the platform's enum (W4).

### Claims check (independently re-run)

| Check | Result |
|---|---|
| validate-sdk | Confirmed OK (SDK compat check skipped, jars absent, as before). As briefed, it does not check symptom keys, so I did (below). |
| build-sdk | Rebuilt into scratch; the `content/` tree (12 symptomdefs, 8 alertdefs, resources) is byte-identical to the author's pak. Working tree unchanged by the build. |
| pak-compare 16 vs 15 | 0 BLOCKING, 1 WARNING (UniFiSwitch attribute count 20 vs 19, the new PoE metric), 21 INFO (the 20 new content files plus `content/resources/resources.properties`). |
| `ci/run_java_tests.sh` | All pass, including the strengthened `tests/test_poe_budget_used_pct.py`. |
| Round-1 W1 | Fixed: `block_body()` brace-matches the `if (perf && poeReported) {` block and asserts each PoE key is inside it and not outside. |
| Round-1 N1 | Fixed: REFERENCE.md header reads build 16. |
| defect-gate | `no open blocking defects affecting unifi`. |

### Symptom keys vs describe.xml and the collector

| Symptom | Kind | Key | describe | Collector writes | Verdict |
|---|---|---|---|---|---|
| AP/Gateway/Switch Offline | UniFiAccessPoint/Gateway/Switch | `Status\|state_code` | property string | `UniFiValues.stateName`: "disconnected", "heartbeat missed", ... (UniFiValues.java:102-115), only when state is a whole number | OK, regex matches the exact strings |
| Switch Connected | UniFiSwitch | `Status\|state` | metric | 1.0 only for raw state 1, else 0.0, null when unknown (UniFiValues.java:56-66) | OK |
| PoE Budget High | UniFiSwitch | `PoE\|poe_budget_used_pct` | metric | inside `perf && poeReported` | OK |
| Port Link Down / Is Uplink | UniFiSwitchPort | `Status\|up`, `Status\|is_uplink` | property string | "true"/"false" (UniFiAdapter.java:1113, 1118) | OK (see W2) |
| Camera Connected/Disconnected/Not Recording | UniFiCamera | `Status\|is_connected`, `Status\|is_recording` | property string | "true"/"false" (UniFiAdapter.java:1349-1352) | OK (see W1, W2) |
| WAN Availability Low / Latency High | UniFiWanInterface | `Health\|availability`, `Health\|latency` | metric | only while the gateway informs (UniFiAdapter.java:983-984) | key OK, condition wrong for unused WANs (B1) |

`Status|state_code` regex and the property `regex` operator have corpus
precedent (`vmbro_vcf_operations_hardware_vcommunity`, `type="property"
operator="regex"`). Switch ports exist only on `usw` devices
(UniFiAdapter.java:573-584), so gateway WAN ports never reach Uplink Port Down.

### Rendered pak (dimension 13)

Parsed all 8 `content/alertdefs/*.xml` and 12 `content/symptomdefs/*.xml`:
no `<SymptomSets>` wrapper anywhere (every alert has exactly one set; single
symptom sets are bare `ref=` under `<State>`, multi-symptom sets carry
`<Symptom ref>` children), every `ref` resolves to a SymptomDefinition in the
same file, the duplicate definitions in symptomdefs/ and alertdefs/ are
identical, every referenced recommendation is defined in its file, and
`waitCycle`/`cancelCycle` on symptoms are integers (3/3). The adapter's own
`describe.xml` carries no alert content. `AlertDefinition` has no
`waitCycle`/`cancelCycle` attributes (the YAML's 1/1 is the default, so no
behavior change). The content-tree path (`content/alertdefs/` with slug ids)
is the one vcommunity-vsphere proved live (DEF-009 closing evidence;
`knowledge/context/wire-formats/alertdef_symptomset_import.md` shows a slug
`SymptomDefinition-VMWARE-...` id imported on devel).

### Findings

#### BLOCKING

- **B1** `symptoms/unifi_wan_availability_low.yaml` / `alerts/unifi_wan_degraded.yaml`.
  Authority: reviewer doctrine (a known false positive in shipped content);
  dimension 11 (the docs say the alert means a degraded WAN; an unplugged
  WAN is not degraded). Evidence, not inference:
  `knowledge/context/investigations/2026-10-16-unifi-15-devel-9-1-proof.md`
  item 7: on this lab's UDM Pro, "WAN 2 reads 0.0 for every traffic and
  health metric ... it has no IP, no netmask and Health|availability 0.0, so
  it is an unplugged second WAN". Discovery creates a WAN 2 resource whenever
  the `wan2` object exists (UniFiAdapter.java:570-573), the gateway is
  connected so the metric publishes every cycle, and `0 < 99` holds forever.
  Result: on install, a Warning WAN Degraded alert fires on WAN 2 in this lab
  and never clears, and the same on any dual-WAN-capable gateway (UDM Pro,
  UXG, etc.) with an unused second WAN. That trains operators to ignore the
  alert. Fix (author's choice of mechanism; the requirement is: no alert on
  an unused WAN, a real degradation on a live WAN still alerts): publish the
  WAN's `up` (and/or a configured signal such as a non-empty IP) as a
  property on UniFiWanInterface and add a scoping symptom to WAN Degraded,
  the same pattern as Camera Connected / Port Is Uplink. If a hard-down
  primary WAN then stops alerting, say so in REFERENCE.md or add a separate
  WAN Down alert; do not leave it silent.

#### WARNING

- **W1** `alerts/unifi_camera_not_recording.yaml`. Authority: dimension 10
  (gap honesty), the brief's false-positive hunt. A camera whose Protect
  recording mode is deliberately "never" (privacy, indoor camera, spare)
  reports `isRecording` false while connected and holds a Warning on Health
  forever. The pak publishes no recording-mode property, so an operator
  cannot scope it except by disabling the alert per object. The lab shows
  12/12 recording today (same proof doc, item 3), so this is not a day-one
  lab false positive. Fix: publish the camera's recording mode and scope the
  alert to mode not "never", or state the behavior in REFERENCE.md and the
  recommendation text ("if the camera is intentionally not recording, disable
  this alert for it").
- **W2** UniFiAdapter.java:1113, 1118, 1349-1352. Authority: vcfops-sdk-adapter
  skill, *Unreadable is NOT compliant*; overview.md's own build-15 contract
  "no 0.0 for fields the controller does not send". `Status|up`,
  `Status|is_uplink`, `Status|is_connected` and `Status|is_recording` coerce
  an absent JSON field to "false". Before this build that was cosmetic; now
  "false" drives Critical alerts (Camera Offline on an absent `isConnected`,
  Uplink Port Down on an absent `up`) and Camera Not Recording. Low
  likelihood with current firmware, but an absent read becoming an alert is
  the same class of defect as an absent read becoming a pass. Fix: publish
  these four only when the field is present (the build-15 present-only idiom),
  so a missing field raises nothing.
- **W3** `alerts/unifi_uplink_port_down.yaml`, REFERENCE.md Alerts table.
  Authority: dimension 10/11. A switch reports `is_uplink` on the port it uses
  to reach the controller; when that single link fails the switch stops
  informing, its own port keeps the controller's last cached `up` (port
  properties publish regardless of `perf`, UniFiAdapter.java:1113), and the
  upstream switch's facing port is not `is_uplink`. So the most common uplink
  failure surfaces as Switch Offline, not Uplink Port Down; this alert only
  fires where the switch keeps another path (LAG, redundant uplink, STP
  failover). The docs say "Fires when a switch port that serves as an uplink
  has lost link" with no caveat. Fix: one sentence in REFERENCE.md and the
  alert description stating that a lost sole uplink appears as Switch Offline.
- **W4** every `alerts/*.yaml` (`sub_type: 1|2|3`). Authority:
  `knowledge/context/api-surface/compliance_enablement_markers.md` item 2
  (BuilderAlertSubType 18=AVAILABILITY 19=PERFORMANCE 20=CAPACITY
  21=COMPLIANCE 22=CONFIGURATION, from internal-api-9.1.json) and the reference
  corpus: every `<AlertDefinition>` with type 15-19 under `reference/` uses
  subType 18-22, none 1-5. The rendered alertdefs carry `subType="1"`, `"2"`,
  `"3"`. Import is likely tolerated (the loader accepts any int), but the
  alerts will not classify as Availability/Capacity/Performance in Ops alert
  lists and filters. Root cause is factory-side: `src/vcfcf_core/alerts/loader.py:15`
  documents `1=Availability ... 5=Configuration`, and factory `content/alerts/synology_*`
  copies it. Fix here: 18 for the offline/down/not-recording alerts, 20 for
  PoE, 19 for WAN. **Registration candidate** as `factory:alerts` (the loader
  doc and any defaults), separate from this pak.

#### NIT

- **N1** Offline symptoms match only `disconnected` and `heartbeat missed`. A
  device stuck in `inform error` (9) or an unknown code publishes no metrics
  (not in `INFORMING_STATES`) and raises no alert, so it goes silently stale.
  The exclusion is documented, so this is a judgment call; consider adding
  `inform error`.
- **N2** Stale holds, documented nowhere: when a gateway stops informing, WAN
  metrics stop and WAN Degraded holds its last state until it returns; a
  device forgotten in the controller while offline keeps its last
  `state_code` and its Offline alert until the Ops object is removed; on an
  integrated console (UDM), Gateway Offline cannot fire because the controller
  is the gateway (collection itself fails). A line in REFERENCE.md would do.
- **N3** `recommendations/unifi_investigate_offline_camera.yaml` is named
  "Investigate Disconnected Camera"; rename the file to match.

### Dimensions not covered above

1-8 (code): no Java change since round 1. 9: build 16, CHANGELOG entries for
both parts, minimal diff. 11: landing README, overview and REFERENCE all name
the alerts; no relationship change. 12: below.

### Defect registry (knowledge/context/defects.md)

No `defects.local.md`; the inherited registry governs. `Affects: unifi`:
DEF-002 (closed), DEF-007 (closed). **No open defect affects this pak**
(defect-gate agrees). Registration candidates: B1 if it ships unfixed
(`Affects: unifi`); W4 as `factory:alerts`.

### If shipped as-is

On install, WAN Degraded fires on the lab's unplugged WAN 2 and never
clears; a camera set not to record alerts forever; the offline, PoE and
uplink alerts otherwise behave as documented.

---

## Round 1 (PoE metric, 2026-10-27): APPROVE

### Bottom line

The calculation and its guards are right. `UniFiValues.poeBudgetUsedPct`
returns null (nothing published) when the draw is unknown, when the budget
is absent, 0 or negative, or when the result is not finite, so
usw-aggregation (`total_max_power` 0) publishes nothing instead of NaN,
Infinity or a fake 0. The publish sits inside the existing
`if (perf && poeReported)` block in `collectSwitch`, so a switch not
informing the controller, or one where no PoE port reports a draw,
publishes nothing. The one gap is in the test, not the code: the Python
wiring test claims to pin that guard and does not (W1).

### Claims check (independently re-run)

| Claim | Result |
|---|---|
| `ci/run_java_tests.sh` passes | Confirmed: 11 Java + 12 Python, all pass, including `UniFiValuesTest.poeBudgetUsedPct` and `tests/test_poe_budget_used_pct.py`. |
| validate-sdk | Confirmed: `OK: ... valid Tier 2 SDK adapter project`. SDK compat check skipped (8.18.7 and 9.1.1.0100 jars not in `adapter_runtime/`), same as prior builds. |
| build-sdk reproduces | Confirmed. My scratch build of 0.0.0.16 has byte-identical class files to the author's pak (`unifi_controller.jar` differs only in zip metadata); built `describe.xml` equals source apart from the version stamp. Build did not modify the working tree. |
| pak-compare vs 0.0.0.15 | 0 BLOCKING, 1 WARNING (`UniFiSwitch: group attribute count factory=20, reference=19`), 0 INFO. Expected: exactly the one new attribute. |
| describe.xml | `poe_budget_used_pct` in UniFiSwitch `PoE` group, `dataType="float"`, `isProperty="false"`, `defaultMonitored="true"`, `unit="%"` (same unit form as `cpu_pct`, `satisfaction`). nameKey 267 appears once in describe.xml, once in resources.properties (`267=PoE Budget Used %`), and never in the repo history (`git log -S`); no duplicate nameKeys or property keys; every nameKey has a label. No alerts or symptom sets in the built describe (dimension 13 not applicable). |

### Dimensions

1. **Unreadable is not compliant / absent is not zero.** Proven safe.
   `maxPower` comes from `UniFiValues.number`, which already rejects
   absent, non-numeric, NaN and Infinity text. The helper adds `> 0`
   (negation form `!(maxPower > 0)` also catches NaN) and `isFinite` on the
   result (overflow, tested with 1e308/1e-308). A draw of 0 with a real
   budget reads a real 0, which is correct: the draw was read. Over-budget
   reads above 100, as reported, documented.
2. **Reflection-tolerant reads.** N/A (no vim25); the JSON reads are the
   existing null-tolerant ones, no new throw paths.
3. **Exception granularity.** No new try/catch; the helper cannot throw
   (primitive `double` autoboxes to a non-null `Double`).
4. **Canonical loader.** N/A.
5. **Stitching identity.** N/A, no relationship changes.
6. **Logging.** No new logging.
7. **Memory/resources.** No new allocations beyond one metric per switch.
8. **Performance.** Reuses the already-summed `poeConsumption` and
   already-parsed `maxPower`; no extra reads.
9. **Build hygiene.** `build_number` 15 -> 16, CHANGELOG entry
   `0.0.0.16 (Unreleased)` matches; minimal diff. `docs/README.md` and
   `docs/inventory-tree.md` title punctuation changes are generator output
   (my build reproduced them with no tree change).
10. **Gap honesty.** CHANGELOG states the alert is not part of this build.
11. **Docs parity.** overview.md "Build 16 adds" section and REFERENCE.md
    row match the behavior. No relationship changes, so no landing-README
    gap. See N1 for the stale REFERENCE.md header.
12. **Registry.** See below.
13. **describe.xml import rules.** No alerts/symptoms in this build.

### Findings

### WARNING

- **W1** `tests/test_poe_budget_used_pct.py` (guard check, `body.index("if (perf && poeReported) {") < body.index("PoE|poe_budget_used_pct")`).
  Authority: vcfops-sdk-adapter skill, *Unreadable is NOT compliant*;
  reviewer doctrine (unproven is a finding). The test docstring says it pins
  publication "only inside the block guarded by perf and a reported draw",
  but it only checks the key appears *after* the `if` text, not inside the
  block. Mutation run in scratch: moving the `metricIfPresent(...)` call to
  after the block's closing brace passes the test. If that regression ever
  landed, a disconnected PoE switch with a known budget would publish
  `poe_budget_used_pct = 0` every cycle (0 draw summed, budget > 0), which
  reads as "budget healthy" for a switch that was not read. The shipped
  code is correct; the test gives false assurance. Fix: extract the body of
  the `if (perf && poeReported) { ... }` block with the same brace matcher
  as `method_body` and assert the key is inside it (the same weakness as
  build 15 N3 for the other switch PoE metrics, which this would close too
  if applied to all three keys).

### NIT

- **N1** `REFERENCE.md:3` still reads "for build 15 (dev 0.0.0.15)" while
  the table now includes the build 16 row. Bump the header.
- **N2** (advisory for the #30 alert, not this build) The metric stops
  updating when a switch stops informing the controller; Ops keeps the last
  value, so a ">= 90%" symptom can stay active on stale data for a
  disconnected switch. The alert author should pair it with the
  `Status|state` metric or accept that behavior knowingly.

### Defect registry (knowledge/context/defects.md)

No `defects.local.md` exists, so the inherited registry governs. Entries
with `Affects: unifi`: DEF-002 (closed), DEF-007 (closed). **No open defect
affects this pak.** No new finding here is a registration candidate (W1 is
a test-strength gap with correct shipped code).

### If shipped as-is

Operators get a correct "PoE Budget Used %" on every switch reporting a PoE budget above 0 and
nothing on usw-aggregation or non-PoE switches; no NaN, Infinity or fake 0.
