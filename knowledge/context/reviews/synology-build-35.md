# Synology build 35 review

- **Adapter:** `content/sdk-adapters/synology` (branch `build-35`)
- **Commits reviewed:** 8e3ddec (Java: #16 form POST, #42 latency), 84dced0 (11 symptoms), 6a428af (7 alerts, 6 recommendations, `content_naming`), on top of origin/main 24934c4 (build 34)
- **Reviewer:** sdk-adapter-reviewer, 2026-10-28
- **Verdict:** CHANGES REQUESTED (2 BLOCKING / 3 WARNING / 3 NIT)

## Independent re-runs

| Check | Result |
|---|---|
| `validate-sdk content/sdk-adapters/synology` | OK. The SDK compatibility compile against 8.18.7 and 9.1.1.0100 was skipped here because the jars are not in `adapter_runtime/`. RULE-019 proof is owed by CI or by a host that has the jars. |
| `build-sdk` (into the reviewer scratchpad) | Built `vcfcf_sdk_synology_diskstation.0.0.0.35.pak` with 11 symptomdefs and 7 alertdefs |
| `pak-compare` vs `dist/…0.0.0.34.pak` | PASS: 0 BLOCKING, 0 WARNING, 19 INFO (all new `content/` files) |
| `ci/run_java_tests.sh` (16 Java tests + 9 python wiring tests) | All pass, DsmRequestTest and MetricsTest.latenciesAreMicrosecondsPublishedAsMs included |
| Built-pak alert XML (dimension 13) | Bare `<SymptomSet>` under `<State>` for the three single-set alerts (fan, pool, volume-not-healthy). `<SymptomSets operator="or">` holds 2 children in the four two-set alerts. Every ref resolves. `waitCycle`/`cancelCycle` are integers. `type` is 17/18 and `subType` is 18/20, inside Scott's 18-22. |

### Read-only NAS probe

DS1520+, DSM 7.3.2, run on 2026-10-28. The probe logged in with a form POST under the session name `VCFCFReview35`, made the reads below, then logged out (`logout success: True`). Credentials and the sid were never printed.

- Every call the probe made worked as a form POST with `_sid` in the body: `SYNO.Core.Hardware.FanSpeed`, `SYNO.Core.ExternalDevice.UPS`, `SYNO.Storage.CGI.Storage load_info`, `SYNO.Core.System.Utilization`, `SYNO.Core.Share list` with `additional`, and `SYNO.Core.FileServ.NFS.SharePrivilege load`. A call with no `_sid` in the body gets error 119.
- A DSM error body (bad method, code 103) does not echo the sid or any parameter.
- Values seen:
  - pool, volume and SSD-cache `status`: `normal`
  - disk `smart_status`: `normal`
  - `unc`: 0, 6 and 16 on HDDs, -1 on NVMe
  - `disk_failure_number`: 0
  - `cool_fan`: `yes`
  - UPS `status`: `usb_ups_status_unknown` (no UPS)
- DSM's static UI files read unauthenticated: `webman/modules/AdminCenter/admin_center.js`, `webman/texts/enu/strings`, `webman/3rdparty/StorageManager/storage_panel.js`, and `webman/modules/ResourceMonitor/resource.js`. The probe scripts live in the reviewer scratchpad and are not committed.

## Scope verdicts

### #16: DSM login, data calls and logout as form POSTs

**This part passes.**

- **Request paths.** `DsmRequest.post` (DsmRequest.java:96) builds the path `/webapi/<cgi>` with no query string. api, version, method, `_sid` and the extras all go in the body.
- **Call sites.** Every call goes through `callRaw(DsmRequest, …)`:
  - login (SynologyApiClient.java:108)
  - all 14 data calls through `call` (lines 304-316), the re-login retry included
  - logout (line 205)
  - the only GET left is `SYNO.API.Info` (line 146). `DsmApis.INFO_PATH` carries no secret and no session.
- **No other DSM HTTP site.** A grep of `src/` for `webapi`, `_sid`, `passwd`, `.post(` and `.get(` finds no other place that calls DSM.
- **Encoding of every parameter:**
  - `api` and `method` go through `urlEncode`, `version` is an int.
  - `account`, `passwd`, `session` and `share_name` go through `urlEncode`.
  - `shareType=all` and `format=sid` are literals.
  - `additional` is a pre-encoded constant (line 280).
  - The per-UTF-8-byte encoder (DsmRequest.java:111) is correct for 1- to 4-byte characters. `%X` is not locale-sensitive.
- **Secrets on error paths.** No secret reaches a URL, a thrown message or a log:
  - Transport failures go through `SynologyRedaction.transportFailure`, built from the endpoint label with no chained cause.
  - A non-200 reply throws `HTTP <code> from <endpoint>`.
  - A DSM error throws `api method failed: <DSM error JSON>`, and the probe showed DSM does not echo the request.
  - The framework `RetryPolicy` and the round-robin warnings log JDK exception text and the host, never the URI query or the body (ManagedHttpClient.java:119-135, 258-318).
  - The redaction patterns mask a form body. The new `Cookie:` `id=` pattern spares `device_id=` (tested).
- **Retry behavior is unchanged.** A POST login is retried up to 3 times on an IOException, exactly as the GET was.

### #42: latency from microseconds to ms

**This part passes.**

- **Evidence.** I confirmed the unit independently. DSM's `resource.js` declares `io_latency` (`read_avg_latency`, `write_avg_latency`, `total_io_latency`) and the NFS `total_latency` (`*_max_latency`) as `dataType:"timeus"`. The `timeus` formatter shows a value under 1e3 as us and divides by 1e3 for ms.
- **Code.** `SynologyMetrics.microsToMillis` is null-safe. `nfsMaxLatency` now skips the metric when DSM does not send it, where it used to publish 0.
- **Upgrade impact.**
  - History steps down by a factor of 1000 at the upgrade. Key names, display names and units are unchanged.
  - Nothing in the factory or the pak references `read_latency`, `write_latency` or `nfs_max_latency`. A grep of `content/`, `third_party/` and `bundles/` finds only describe.xml, so no shipped threshold breaks.
  - The README "To build 35" note, REFERENCE.md and docs/installing.md all state the step and the need to re-check user thresholds.
  - Residual effect, not documented: dynamic-threshold bands and anomaly history learned on the 1000x data stay wrong until Ops relearns them. See N2.

### #35: bundled symptoms, alerts and recommendations

**This part fails: two of the seven alerts cannot do what they claim.** Details are under BLOCKING.

Per alert, can it fire on what the adapter publishes?

| Alert | Key and value the adapter publishes | Fires on a real fault? |
|---|---|---|
| Storage Pool Not Healthy | `Configuration|status` = DSM `status` (`normal` live) | Yes. Also fires on blank, see W1. |
| Volume Not Healthy | same, on the volume | Yes. Also fires on blank, see W1. |
| Volume Nearly Full (85/95) | `Capacity|usage_pct` = used/total*100, skipped when unknown | Yes |
| Disk Failing | `Health|smart_status` (`normal`), `Health|unc_sectors` (DT_ABOVE) | SMART: yes, but also on blank and on `unknown` (W1). unc: only if the DT XML imports (W2). |
| SSD Cache Failure | `Hardware|disk_failure_count` (`"0"`), cache `Configuration|status` | Yes. A missing count reads `"0"`, which stays quiet. Status fires on blank (W1). |
| **Fan Failure** | `Fan|fan_status` = `cool_fan` | **No.** It is a fan-mode capability flag, not a health signal. See B2. |
| **UPS On Battery** | `Status|status` = DSM `status` | **No.** DSM sends `usb_ups_status_*` keys, not NUT codes. See B1. |

## BLOCKING

### B1. The UPS alert can never fire

**Where:** `symptoms/synology_ups_on_battery.yaml` and `symptoms/synology_ups_low_battery.yaml` (condition `CONTAINS "OB"` / `CONTAINS "LB"`). The published value comes from SynologyAdapter.java:1295.

**Authority:** `knowledge/rules/no-fabricated-metrics.md` (RULE-002) and skill § *Gaps — name them, never hide them*.

**What is wrong.** DSM's `SYNO.Core.ExternalDevice.UPS` `status` is a DSM translation key, not a NUT status code.
- DSM's own UI renders the status as `_T("ups", this.UPSInfo.status)` and special-cases `usb_ups_status_online` and `usb_ups_status_unknown` (admin_center.js, `onClickStatusButton`).
- The `ups` string table defines exactly these values:
  - `usb_ups_status_online` ("Connected")
  - `usb_ups_status_battery` ("On Battery")
  - `usb_ups_status_low_batt` ("Low Battery")
  - `usb_ups_status_off` ("Off")
- The live no-UPS value is `usb_ups_status_unknown`.

None of these contains `OB` or `LB` in any case. The NUT assumption comes from `knowledge/context/api-maps/synology-ups.md`, whose own text says the connected-state values "are still assumed to follow NUT conventions but cannot be verified without a UPS". An inferred value was shipped as an alert condition. The result is a power-loss alert that installs, is enabled by default, and stays silent through a real outage.

**Smallest correct fix:**
- On Battery (Warning): `operator: EQ`, `value: "usb_ups_status_battery"`.
- Low Battery (Critical): `operator: EQ`, `value: "usb_ups_status_low_batt"`.
- Keep the alert's ANY set and SYMPTOM_BASED criticality.
- Correct the api-map's NUT claim through the orchestrator (`api-explorer` owns `knowledge/context/`).
- The lab has no UPS, so record the remaining live gap: this is the vendor UI's own enumeration, but it has not been seen on a live UPS.

### B2. The Fan Failure alert keys on a fan-mode capability flag, not fan health

**Where:** `symptoms/synology_fan_failed.yaml` (`Fan|fan_status EQ "no"`). The published value comes from SynologyAdapter.java:993 (`cool_fan`).

**Authority:** RULE-002 and skill § *Gaps*.

**What is wrong.** DSM's Fan Speed Mode panel uses `cool_fan` to choose which radio buttons to show (admin_center.js):
- `"no"` shows the high-fan and low-fan buttons.
- `"single"` shows full and quiet, depending on `fan_type`.
- Any other value shows full, cool, quiet and quiet-stop.

It describes which fan modes the model offers. DSM reports a fan failure through its notification and beep path instead (strings `fan_fail`, `cpu_fan_fail`, `reason_fan_fail`), not through this field. The api-map basis is a guess: synology-system.md:207 says "likely 'no' = failed".

**Effect if shipped:**
- On every model whose `cool_fan` is `"no"`, a Critical "Fan Failure" fires from the first collection and never cancels.
- On every model, a real fan failure never fires the alert.
- `"single"` models are never covered.

**Smallest correct fix:**
- Remove `alerts/synology_fan_failure.yaml`, `symptoms/synology_fan_failed.yaml` and `recommendations/synology_replace_failed_fan.yaml` from `bundled_content`.
- Raise a DESIGN GAP to Scott: which DSM API carries a real fan-failure signal (`SYNO.Core.System.SystemHealth`, or the notification history), to be found by `api-explorer`.
- Do not remap the alert onto another guessed field.

## WARNING

### W1. Present-only: a missing status becomes a Critical alert

**Where:** SynologyAdapter.java:1044 (pool), :1073 (volume), :1123 (disk SMART), :1160 (cache).

**Authority:** skill § *Unreadable is NOT compliant*, the inverse case: a value that was not read must not become a verdict either way. The brief asked for present-only alerting.

**What is wrong.**
- All four properties are published with `asString("")`, so a field DSM omits is published as `""`. `NOT_EQ "normal"` then raises a Critical HEALTH alert on a read that found nothing. The adapter already expects older API versions to omit fields: its own lowered-version WARN says so.
- Disk `smart_status` also has a value `unknown`. DSM uses it for a disk whose SMART it cannot read: storage_panel.js `healthInfoDisabled` treats `"unknown"===smart_status` like a disconnected disk. Shipped as-is, `unknown` raises a Critical "Disk Failing".

**Fix:**
- Skip each of these four properties when the field is absent or blank, the property equivalent of `metricIfPresent`.
- Ask Scott whether SMART `unknown` should alert. If not, make the disk SMART set an ALL of two symptoms: `!= normal` and `!= unknown`.

### W2. The unc_sectors DT symptom ships in an XML shape no reference proves

**Where:** `symptoms/synology_disk_unc_sectors_increasing.yaml`. The built XML is `<Condition key="Health|unc_sectors" operator="DT_ABOVE" type="metric" instanced="false"/>`.

**Authority:**
- `src/vcfcf_core/alerts/render.py`, `_add_condition_element` docstring: "No vendor XML example with a DT (metric_dynamic) condition was found in any reference pak".
- Lessons `knowledge/lessons/pak-content-bundling.md` and `knowledge/lessons/unknown-widget-type-aborts-pak-dashboard-import.md` (pak content import fails silently).
- RULE-005.

**What is wrong.**
- This is the first `metric_dynamic` symptom in any factory pak. A grep of `reference/`, `/mnt/holding/vendor/vcf-ops-9.1.1.0100` and every pak in the repo finds no DT condition in XML.
- The DT symptom is embedded in the same alertdef file as the SMART symptom. If Ops rejects or drops it, the Disk Failing alert, the SMART Critical included, can vanish without a trace.

**Fix:** no code change is required if it imports. Before any `v*` tag, a devel install must prove three things through the Suite API:
1. the alert definition and both symptom definitions exist;
2. the DT condition is intact;
3. the disk alert can be seen bound.

If it does not import, split the DT symptom into its own alert so it cannot take SMART with it. If unproven at acceptance, this is a registration candidate.

### W3. Build hygiene and docs parity for #35

**Authority:** skill § *Build / verify loop* ("add a CHANGELOG.md line every build"), author hard rules 8-9, dimension 11.

**What is wrong.**
- CHANGELOG.md 0.0.0.35 has lines for #16 and #42 only. There is none for #35, which bundles 11 symptoms, 7 alerts, 6 recommendations and `content_naming`.
- No doc surface mentions that the pak now installs alerts, all enabled by default: not README.md, not docs/README.md, not docs/overview.md. An operator browsing the pak repo cannot see them or their thresholds (volume 85/95, SMART Critical, unc DT Warning).

**Fix:**
- Add a CHANGELOG line for #35.
- Add an alerts table (alert, resource kind, symptoms and severities, default-on) to README.md and docs/overview.md, or to `docs/_index_extra.md` so the generated index carries it.

## NIT

- **N1.** "Not normal" for pool, volume and cache also matches non-failure states. DSM's storage_panel.js shows `creating`, `deleting`, `deactivating`, `defrag` and others as summary statuses. The design chose `!= normal` knowingly ("non-normal strings are not enumerated"). Recommend a follow-up that enumerates the failure statuses (`degrade`, `crashed`, `pool_crashed`, `pool_error`, `read_only`) once seen.
- **N2.** The upgrade note could add that dynamic-threshold bands and anomaly history on the three latency keys were learned on the 1000x data and need a learning period to settle. The same applies to the new unc DT symptom: a fresh install has no DT band yet, so it cannot fire for the first days. Document both.
- **N3.** `SynologyRedaction.redact` does not mask a JSON `"sid":"…"` member. No current path logs a login response body, so this is defense in depth only.

## Registry check (`knowledge/context/defects.md`)

No open defect affects synology. The four synology defects are all closed: DEF-001, DEF-003, DEF-005 and DEF-006. DEF-001 (secrets on disk) was re-checked for regression in this build and has not regressed: the endpoint-only exception text, the uncaught-cause rule and redaction are intact, and URLs no longer carry secrets at all.

**Registration candidates if shipped without fixes:**
- B1 (UPS alert silent)
- B2 (Fan alert false Critical, real failures missed)
- W2 (if DT import is unproven at acceptance)

## If shipped as-is

On install, operators get a Critical "Fan Failure" that never clears on any model whose `cool_fan` is `"no"`, and no fan alert on any model when a fan really fails. A UPS on battery or low battery raises nothing.

---

## Round 2 (fix round re-review, 2026-10-28)

- **Commits reviewed:** 2ffd1ed (Java: SystemHealth, present-only, redaction, docs), 586277f (symptoms), d7c9bdc (alerts, recommendations), 1e29124 (docs), on top of 6a428af.
- **Verdict:** APPROVE (0 BLOCKING / 2 WARNING / 3 NIT). Nothing here stops the install. W2 stays open until the devel install proves it.

### Independent re-runs

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | All pass: 19 Java suites, SystemHealthTest included, and 9 python wiring tests |
| `validate-sdk` | OK. The bundled-content vs describe.xml check (factory #283) passes. The SDK compat compile is still skipped because no jars are in `adapter_runtime/`, so the RULE-019 proof is still owed by CI. |
| `build-sdk` (into the scratchpad) | Built `…0.0.0.35.pak`: 11 symptomdefs, 7 alertdefs |
| `pak-compare` vs `dist/…0.0.0.34.pak` | PASS: 0 BLOCKING, 1 WARNING, 19 INFO. The WARNING is "SynologyDiskstation group attribute count 34 vs 30". That is exactly the 4 new properties (`Fan\|fan_health` and 3 `Health\|system_health*`), so it is expected. |
| Unpacked pak | `adapters.zip` describe.xml: the DiskStation groups are System, CPU, Memory, Network, Fan, Health, NFS, with no duplicate group key. nameKeys 63 and 320-322 are new and unique, with no duplicate key in resources.properties. Alert structure (dimension 13): the 3 single-set alerts have a bare `<SymptomSet>` under `<State>`, and the 4 two-set alerts have `<SymptomSets operator="or">` with 2 children. Every ref resolves and cycles are integers. |

### Original findings

| Finding | Status | Evidence |
|---|---|---|
| **B1** UPS alert can never fire | **Resolved** | Rendered as `Status\|status == "usb_ups_status_battery"` (Warning) and `== "usb_ups_status_low_batt"` (Critical). These are the exact values in DSM's `ups` string table. The adapter publishes DSM's `status` text unchanged and present-only (SynologyAdapter.java:1331). The "not seen on a live UPS" gap is stated in REFERENCE.md and CHANGELOG. |
| **B2** Fan alert keyed on `cool_fan` | **Resolved** | The symptom now reads `Fan\|fan_health == "failed"`. Its source is `SYNO.Core.System.SystemHealth get`. `Fan\|fan_status` keeps its key and is relabelled "Fan Mode Support". See the review of the new code below. |
| **W1** Present-only statuses | **Resolved** | Pool, volume, Volume `Cache\|cache_status`, SSD cache, SMART and UPS statuses now go through `textIfPresent` (null, missing or blank means skipped). The `unknown` SMART value no longer fires (the regex excludes it). |
| **W2** DT condition unproven | **Open, carried** | Unchanged and acknowledged honestly: CHANGELOG says "Pending live verification on devel before a `v*` tag". Still a registration candidate if it is unproven at acceptance. |
| **W3** Changelog and docs parity | **Resolved** | CHANGELOG has lines for #35, B2, W1 and N3. The bundled-alerts tables are in README.md and REFERENCE.md, and docs/overview.md points to them. docs/installing.md lists SystemHealth as optional and says what a failed read costs. |
| **N1** "not normal" too broad | **Resolved**, see N4 | REGEX failure sets now replace `!= normal`. |
| **N2** DT relearning note | **Resolved** | README upgrade note and CHANGELOG cover the latency band relearning and the unc warm-up. |
| **N3** JSON sid redaction | **Resolved** | `sid`, `synotoken` and `did` are masked. RedactionTest covers the masking and that a `side` member is spared. |

### New code

**SystemHealth.java, and the mapping to `Fan|fan_health`.** I verified it independently against DSM 7.3.2's `webman/modules/SystemInfoApp/SystemHealthWidget.js`, fetched unauthenticated from the lab NAS (a static file, no login).
- **Response shape.** The widget polls `SYNO.Core.System.SystemHealth` `get` v1 and parses `data.rule`. The adapter reads `systemHealth.data().get("rule")`, which matches.
- **Level mapping.** `RuleMappingUtil` defines `TYPE_DANGER:0, TYPE_ATTENTION:1, TYPE_NORMAL:2`, which matches `level()`.
- **Message keys.** Widget line `parseRule`:
  - With `description_use_formatted`, `_T(...description_format.split(":"))`: the format is the key.
  - Otherwise `description_params.map(_T(split))`: each param is the key.

  `messageKeys()` follows both branches exactly.
- **Fan keys.** The `widget` string table holds `fan_fail`, `cpu_fan_fail` and `eunit_fan_fail`. Another table also has `enclosure_fan_fail`. `endsWith("fan_fail")` covers all of them.
- **Safety:**
  - Every accessor is null-safe, and a missing rule or level returns null, so the property is skipped.
  - The endpoint is optional: it is not in `SnapshotReads.REQUIRED`, and a failure is a single WARN followed by a skip. The cycle cannot abort.
  - `unknown` (another problem outranks the fans) is never `normal` and never fires.
- **Unproven by design.** No failed fan has been seen. This is documented in the README limits and in the alert and recommendation text.

**Can each alert fire on what the adapter publishes?**

| Alert | Published | Fires on a real fault | `unknown`, blank or missing |
|---|---|---|---|
| Storage Pool Not Healthy | `Configuration\|status`, present-only | `degrade`, `crashed`, `deverr` (DSM `volume_status_*` table). `pool_*`: see N4. | Never fires |
| Volume Not Healthy | same | + `ro` (`volume_status_ro` "Read Only") | Never fires |
| Volume Nearly Full | `Capacity\|usage_pct` (metricIfPresent) | yes | n/a |
| Disk Failing | `Health\|smart_status`, present-only | `failing`, `degraded` (`disk_smart_status_*`), `access_err` (storage_panel.js `"access_err"===this.smart_status`). DT: pending W2. | `unknown` excluded; blank skipped |
| SSD Cache Failure | status present-only; `disk_failure_count` | yes | Status never fires. A missing count reads `"0"`: see W4. |
| Fan Failure | `Fan\|fan_health` | `failed` | `unknown` and `normal` never fire |
| UPS On Battery | `Status\|status`, present-only | the two DSM keys | `usb_ups_status_unknown` never fires |

**The REGEX conditions render in the vendor form and would import.** The built XML is, for example, `<Condition key="Configuration|status" operator="regex" value="^(degrade|crashed|deverr|pool_crashed|pool_error)$" type="property" instanced="false" thresholdType="static" valueType="string" />`. That matches the vendor property-regex shape in `reference/` (for example `key="config|version" operator="regex" thresholdType="static" type="property" value="vmx-[1-9]|vmx-1[0-2]" valueType="string"`). The extra `instanced="false"` is the same attribute every other property condition in this pak already carries. The patterns are anchored, so they are correct whether Ops applies full-match or find semantics.

**UPS EQ keys.** These are exact `==` matches on the DSM keys, with no CONTAINS, so there is no substring overlap.

**Redaction additions.** The pattern is anchored on the quoted member name, so `"sid"` is masked and `"side"` is not (tested). No new log site was added.

### WARNING

- **W2 (carried).** The DT import of `Health|unc_sectors` is still unproven. Owed: the devel install and Suite API proof described in round 1, before any `v*` tag.
- **W4 (new; I missed this in round 1).**
  - **Where:** SynologyAdapter.java:1221-1222 publishes `Hardware|disk_failure_count` as `String.valueOf(cache.get("disk_failure_number").asLong())`, so a missing field is published as `"0"`.
  - **Authority:** skill § *Unreadable is NOT compliant*, and the same principle as W1. A value that was not read must not become a verdict.
  - **Why it matters now:** this property now feeds the bundled SSD Cache Disk Failure symptom. An unread count shows as "0 failed disks", which looks like a healthy reading. It cannot cause a false alarm, and the companion status symptom still covers a degraded cache.
  - **Fix:** one line, `propIfPresent(out, "Hardware|disk_failure_count", <num-or-null as integer string>)` using `SynologyMetrics.num`.
  - Not a registration candidate unless it ships unfixed past acceptance.

### NIT

- **N4.** `pool_crashed` and `pool_error` are values of `space_status.status` in DSM's storage_panel.js (`isPotentialCrashed(){return"pool_error"===this.space_status.status}`). The adapter reads the top-level `status`. They are harmless alternatives in the regex, but REFERENCE.md and README present them as values of `Configuration|status`. Either read `space_status.status` too (which would also pick up `pool_missing` and `assemble_fail`) or reword the docs. No regex value has been seen live on a failing pool. The values come from the string table, which is a reasonable source, but the gap should be named the way the UPS gap is.
- **N5.** When a firing Fan Failure is later outranked by another DSM problem, `fan_health` becomes `unknown` and the alert cancels after 3 cycles, even though the fan is still failed. The docs say a fan failure "is hidden" while outranked. They could add that an already-open alert clears.
- **N6.** The generated `docs/README.md` index does not link the bundled alerts. Root README.md and overview.md cover them, which satisfies W3. A `docs/_index_extra.md` line would put them on the docs landing page too.

### Registry check (`knowledge/context/defects.md`)

No open defect affects synology: DEF-001, DEF-003, DEF-005 and DEF-006 are all closed. DEF-001 (secrets in logs) was re-checked for regression and has not regressed: the redaction is now stronger (`sid`, `synotoken`, `did`), and no new log site echoes a body.

**Registration candidates:**
- W2, if the DT import is unproven at acceptance.
- W4, if it ships unfixed.

### If shipped as-is

Operators get seven alerts that fire only on DSM's own failure values. None of them fires on `unknown`, blank or missing data. The unc-sector DT symptom is unproven until the devel install shows it imported. An SSD cache whose failed-disk count DSM omits shows "0" instead of nothing.

---

## Round 3 (NOT_EXISTING opt-in and fix round, 2026-10-28)

- **Commits reviewed:** 59113d1 and a110ac4 (pool and volume regex), 9f3d55e (traversal root at SynologyWorld), 19b4915 (buildkit 1.0.22 opt-in, `ReadKinds`), 9443a3d (an empty list is not a complete read; an NFS probe with no rule list is a failed probe). Built against factory main 3eaaf90 (buildkit 1.0.23).
- **Framework read against:** `VcfCfAdapter.java` on main (`markVanished`, `markable`, `restoreReappeared`, the onCollect guard at :1224); `.github/release-notes-buildkit.md` §Behavior since 1.0.22; `tier2_architecture.md` §Vanished objects; UniFi build 18 round 2 (R2-B1, R2-W1) as the pattern.
- **Verdict: CHANGES REQUESTED** (1 BLOCKING / 3 WARNING / 3 NIT). This supersedes the round 2 APPROVE.

### Independent re-runs

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | All pass: 20 Java suites (ReadKindsTest new) and 11 python checks (test_traversal_root, test_vanished_wiring new). |
| Test strength | 8 mutations in scratch copies, 8 killed: `luns > 0` dropped, `exports > 0` and `probesFailed == 0` dropped, `!nfsOff` dropped, `volumes == 0` dropped from the no-pool proof, `volumeCached` dropped, `connectKnown` dropped, a null `used_by` treated as evidence, and the NFS `n < 0` failed-probe branch disabled. |
| `validate-sdk` | OK. **The RULE-019 compat compile now ran clean against both jars** (8.18.7, and 9.1.1.0100 with javac 25, `--sdk-compat-jar`, `VCFCF_SDK_COMPAT_REQUIRED=1`). |
| `build-sdk` (scratchpad) | Reproduces `…0.0.0.35.pak`: 11 symptomdefs, 7 alertdefs. The adapter tree is clean afterwards. |
| `pak-compare` vs `dist/…0.0.0.34.pak` | **0 BLOCKING, 1 WARNING, 19 INFO.** The WARNING is the DiskStation attribute count 34 vs 30, the 4 round 2 properties (expected). The INFOs are the new `content/` files. |
| Unpacked pak, DT symptom | `<Condition key="Health\|unc_sectors" operator="above" type="dtmetric" instanced="false" />`. This is the content-import form: it matches the vendor conditions in `reference/` (for example `key="datastore\|workload" operator="above" type="dtmetric"`) and the 1.0.23 fix (3eaaf90). |
| Unpacked pak, Disk Failing alert | `<SymptomSets operator="or">` has 2 children: the SMART regex (`^(failing\|degraded\|access_err)$`, critical) and the DT symptom (warning). Every ref resolves, and the recommendation is attached. Dimension 13 across all 7 alerts: no single-child `SymptomSets`, no dangling ref, and integer cycles. |
| Pool and volume regex | Built: pool `^(degrade\|crashed\|deverr)$`, volume `^(degrade\|crashed\|deverr\|ro)$`. No doc still presents `pool_crashed` or `pool_error` as `status` values. |
| Traversal root | Built describe.xml has `rootResourceKind="SynologyWorld"`, and all 7 paths start `synology_diskstation::SynologyWorld\|\|`. This matches `knowledge/lessons/traversal-spec-root-must-be-reachable.md`. |
| defect-gate | `no open blocking defects affecting synology` |

**Read-only NAS probe** (DS1520+, DSM 7.3.2, session `VCFCFReview35r3`; form POST login, then logout `True`; no secret or sid printed):
- `load_info` has the keys `detected_pools` and `missing_pools` (both `[]` here) as well as `storagePools`.
- Disks report `used_by`: `reuse_1` for sata1-5 and `shared_cache_1` for the two NVMe. The volume has `pool_path` `reuse_1` and `cache.id` `alloc_cache_1_1`. `sharedCaches[0].is_missing` is `false`.
- Share list: 20 shares, `total` 20 with no limit sent. With `limit=2` it returns 2 rows and `total` 20, so the endpoint pages.
- 16 shares have NFS rules, 4 have none, and no probe failed.
- LUN list: 2 LUNs, no `total`, and `limit` is ignored.
- UPS: `usb_ups_connect` false, `enable` false, mode SLAVE. SystemHealth reads.

### Kind-by-kind walk (ReadKinds vs enumerateResources)

| Kind | Declared when | Verdict |
|---|---|---|
| DiskStation | SystemHealth read | Safe. One DiskStation is delivered whenever the snapshot builds, so only other DiskStation keys under this instance can count. |
| Storage Pool | load_info complete, and pools > 0 or proven none | **Unsafe: R3-B1.** A pool DSM reports in `missing_pools` or `detected_pools` is not in `storagePools`. |
| Volume | as pool | Unsafe through R3-B1 (volumes on a missing pool), and R3-W1. |
| Disk | load_info complete with at least 1 disk | Safe for a failed read. Disks of a disconnected expansion unit: see R3-B1. |
| SSD Cache | list, ids, and caches > 0 or proven none | Empty-list evidence is sound. A missing shared cache is not checked: R3-W1. |
| iSCSI LUN | read, a non-empty list, a uuid on each | Safe. A confirmed 102 stores `{}`, which is not a list, so nothing is declared. |
| NFS Export | share list read and non-empty, names present, NFS not off, no failed probe, exports > 0 | Safe for failures. A probe with no rule list now fails (NfsProbesTest). A paged share list: R3-N1. |
| UPS | read, `usb_ups_connect` present, and `model` when connected | Safe. `usb_ups_connect=false` is DSM's positive statement, the kind of evidence the 1.0.22 notes allow. |
| World | excluded | Safe. |

**What was proven safe.**
- **Thread binding.** `enumerateResources` clears `lastRead` first and sets it last. `kindsReadThisCycle` answers only for the same thread. The framework calls both on the onCollect thread (`VcfCfAdapter.java:1063-1071`, then `markVanished` after the guard at :1224). A concurrent discovery pass nulls or replaces the record, and that cycle then marks nothing. This fails safe, as in UniFi round 2.
- **DSM error in a 200.** `success:false` throws in `call()` before and after a re-login (pinned in test_vanished_wiring). A required endpoint fails the build and nothing is counted. An optional endpoint is unread and its kind is left out.
- **The UniFi R2-B1 shape (an empty top-level list declares every kind).** It does not reproduce here:
  - Pools, volumes and disks come from a REQUIRED endpoint that must hold at least one disk.
  - Every other kind needs a non-empty list or a positive evidence field.

### BLOCKING

- **R3-B1. A missing or unassembled pool is counted gone and deleted, never alerted.**
  - **Where:** `SynologyAdapter.java:638-690` and `ReadKinds.java:123-130, 187-196`.
  - **Authority:**
    - skill § *Unreadable is NOT compliant*
    - release notes §1.0.22 ("Leave a kind out of `kindsReadThisCycle()` whenever any part of its read failed")
    - tier2_architecture.md §Vanished objects ("That a kind was delivered is not proof it was read in full")
    - the "Empty is not complete" rule (see the note below)
  - **What DSM does.** DSM lists pools in three places, and the pack reads one of them:
    - DSM's own Storage Manager builds its pool list as `storagePools.concat(detected_pools, missing_pools)`. This is `PoolModule.loadPool` in `webman/3rdparty/StorageManager/storage_panel.js`, fetched unauthenticated from the lab NAS: `let h=a.concat(i,s||[])`.
    - A pool with absent drives (`isMissingPool`: unassembled space with `missing_drives`) is in `missing_pools`, not in `storagePools`.
    - So is a pool that awaits Online Assemble (`isDetectedPool`) in `detected_pools`.
    - The adapter never reads either key (grep finds no match in `src/`). The API map already lists both as unexplored: `knowledge/context/api-maps/synology-storage.md:80, :1101`.
  - **Path, multi-pool NAS (an internal pool plus a DX517 pool, or an HDD pool plus an SSD pool):**
    1. The expansion unit loses power or its cable, or the drives are pulled, or the pool needs assembling after a reboot or migration.
    2. That pool leaves `storagePools`. `pools > 0`, so `SynologyStoragePool` is declared.
    3. The pool counts a miss every cycle and is marked NOT_EXISTING at 12 (an hour at 5 minutes).
    4. Retention deletes it with its history: 6 hours on 9.0 devel, 168 by default.
    5. Its volumes go the same way if they leave `volumes`. So do its disks when the unit is unplugged (`disks` declared).
  - **Path, single-pool NAS.** `noPoolConfigured` ignores both keys. If the remaining disks state an empty `used_by`, or name only a shared cache (all HDDs pulled, NVMe cache left), the empty pool and volume lists are "proven" and the same thing follows.
  - **Why it is BLOCKING.** The pool object gets no status, so Storage Pool Not Healthy never fires. DSM's worst storage state ends as a silent deletion instead of an alert. Before build 35 the pool only went stale. README:173 claims "a failed read never deletes anything", and this path contradicts it.
  - **Fix:**
    - Pass `missing_pools` and `detected_pools` to `ReadKinds.storage`. Declare Storage Pool, Volume and Disk only when both are lists and both are empty. An absent key is no evidence, so leave the kinds out.
    - Make `noPoolConfigured` require the same.
    - Leaving SSD Cache, LUN and Export out while any pool is missing or detected is the cheap safe side, because all of them can live on the absent pool.
    - Add ReadKindsTest cases for each key non-empty and for each key absent.

### WARNING

- **R3-W1. Lists inside one load_info that contradict each other still count as complete.**
  - **Where:** `SynologyAdapter.java:663-702` and `ReadKinds.java:123-143`.
  - **Authority:** as R3-B1, and UniFi R2-W1 (a parent that names a child the list omits).
  - **Unchecked cases:**
    - A volume whose `pool_path` names a pool not in `storagePools`.
    - A volume whose `cache.id` names a cache not in `ssdCaches`.
    - A `sharedCaches[]` entry with `is_missing: true`. DSM's UI shows it as "missing", and the cache allocation it backs may drop from `ssdCaches`.
  - Each is a pointer to an object that DSM still knows and the list omits. All three fields are present on DSM 7.3.2 (probe above).
  - **Fix:** leave the referenced kind out when any of these holds. **Registration candidate** if it ships unfixed.
- **R3-W2. The CI buildkit pin is behind what this pak needs.**
  - **Where:** `.github/workflows/build-pak-on-tag.yml:53` (`BUILDKIT_TAG: sdk-buildkit-v1`).
  - **Authority:** `knowledge/rules/validate-before-install.md`, the release gate.
  - `sdk-buildkit-v1` points at 1.0.20 (`gh release view`).
  - A `v*` tag cut now fails CI at compile, because `@Override` hooks it overrides do not exist in 1.0.20. That failure is loud.
  - The quiet case: if 1.0.22 is published and 1.0.23 is not, the pak builds, but the unc_sectors symptom renders as `DT_ABOVE`. The importer rejects it ("Invalid operator:dt_above", 3eaaf90) and drops it and the Disk Failing alert.
  - **Fix:** publish 1.0.23 and move `v1`, or pin `sdk-buildkit-v1.0.23`, before tagging.
- **R3-W3. Docs parity (dimension 11).**
  - The NOT_EXISTING behaviour is the biggest operator-visible change in the build, because objects get deleted. It is in the root README and REFERENCE.md.
  - `docs/README.md`, `docs/overview.md` and `docs/installing.md` say nothing about it.
  - **Fix:** a short paragraph and a link in `docs/_index_extra.md` or overview.md.
  - README:173 must also become true, which the R3-B1 fix does.
- **W2 (carried, now sharper).** Round 1's W2 was not hypothetical. 3eaaf90 records that devel 8.18 and 9.1 rejected the earlier `DT_ABOVE` form and dropped the symptom and the alert. The 1.0.23 form matches the vendor shape (table above). The devel re-install, with the Suite API showing both the symptom and Disk Failing imported, is mandatory before a `v*` tag.

### NIT

- **R3-N1. The share list's `total` is not checked.** `SYNO.Core.Share list` pages (`limit=2` gave 2 of `total` 20). With no limit it returned all 20 on the lab, but nothing proves that holds on a NAS with many shares. Declare exports only when `total` is absent or equals the rows returned (`ReadKinds.exports`). The same guard the DatastoreIndex already applies to `totalCount`.
- **R3-N2. CHANGELOG 0.0.0.35 states the rule twice.** Line 10 describes the pre-review rule: pools, volumes and disks together, and SSD cache and LUN without the empty-list conditions. Line 11 revises it. Fold them into one statement of the shipped rule.
- **R3-N3. Traversal render proof is owed.** The lesson says "see the tree render in the UI before a tag". The CHANGELOG cites live recon of the old, broken tree, not a render of the fix.

### Upgrade-warning accuracy

The README and CHANGELOG say 29 legacy objects per devel instance: 16 NFS exports, 7 disks, 2 LUNs, 1 pool, 1 volume, 1 SSD cache and the World. 28 are marked and the World is kept.
- **Arithmetic and code agree:** 16+7+2+1+1+1 = 28. `SynologyWorld` is the only excluded kind, and nothing else excludes or protects a legacy object.
- **The lab NAS matches today:**
  - Its current inventory is one-for-one with the legacy duplicates: 16 exports with rules, 7 disks, 2 LUNs, 1 pool, 1 volume and 1 cache.
  - On this shape every one of the six kinds is declared: pools, volumes, caches and LUNs are all non-empty, the LUN list is read, there are 16 exports, and no probe failed.
  - So all 28 will count from the first cycle and be marked about 12 cycles later.
- **Not re-verified:** the devel inventories themselves. This is a static review, with no Ops queries. On the code and NAS evidence the warning is **accurate**.

**Framework docs note.** The "Empty is not complete" paragraph the brief cites is not on factory main. It exists only on `origin/empty-read-is-not-complete` (3de0505: skill, release notes and tier2_architecture.md), which is not merged. The adapter follows it anyway. The orchestrator should merge that branch so the rule is in force.

### Registry check (`knowledge/context/defects.md`)

No open defect affects synology: DEF-001, -003, -005 and -006 are closed, and `defect-gate --pak synology` is clean. DEF-001 (secrets in logs) was re-checked for this delta: the only new log text is the NFS "answered with no rule list" line, which carries no secret.

**Registration candidates:**
- R3-B1, if it ships.
- R3-W1, if it ships unfixed.
- W2, if the DT import is unproven at tag.

### If shipped as-is

The 28 legacy duplicates go away as documented, and day to day nothing is deleted on a failed read. But when a pool goes missing (an expansion unit unplugged, drives pulled, a pool awaiting assembly), the pool raises no alert. An hour later it is marked Not Existing, and after retention it is deleted with its history, along with its volumes and the unit's disks.

## Round 4 (fix round for Round 3, 2026-10-28)

- **Commit reviewed:** 4f354a0 on 9443a3d (adapter branch `build-35`). Changed: `ReadKinds.java`, `SynologyAdapter.java` enumeration, ReadKindsTest, test_vanished_wiring.py, CHANGELOG, README, REFERENCE, `docs/README.md`, `docs/_index_extra.md`, `docs/overview.md`.
- **Verdict: APPROVE** (0 BLOCKING / 2 WARNING / 1 NIT). The R3-B1 deletion path is closed. The remaining findings fail safe: each one leaves an object stale and never deletes it. The stated missing-pool gap does not block this build (judgment below).

### Independent re-runs

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | All pass, rc 0: the Java suites plus the python wiring checks. |
| Test strength | 9 mutations in scratch exports of HEAD, 9 killed, each on an assertion and not a compile error: `noUnassembledPool` dropped from LUN, from Export and from SSD Cache; dropped from `storageComplete`; the `total` check removed; `sharedCacheMissing` dropped from `cacheDangling`; `is_missing` wired to false in the adapter (caught by test_vanished_wiring); the `noPoolConfigured` guard removed; `detectedList` dropped from `noUnassembledPool`. |
| `validate-sdk` | OK. With `VCFCF_SDK_COMPAT_REQUIRED=1`, javac 25 and both `--sdk-compat-jar` paths, it compiled against 9.0 (`--release 17`), 9.1.1.0100 (`--release 25`) and 8.18.7 (`--release 11`). Without the jars it still reports OK but prints SKIPPED, so the CI jar provisioning matters. |
| `build-sdk` (scratchpad) | Reproduces `vcfcf_sdk_synology_diskstation.0.0.0.35.pak`: 11 symptomdefs and 7 alertdefs. The adapter tree is clean afterwards. |
| `pak-compare` vs `dist/…0.0.0.34.pak` | **PASS: 0 BLOCKING, 1 WARNING, 19 INFO.** The WARNING is unchanged from Round 3: the SynologyDiskstation attribute count is 34 vs 30, which is the 4 round 2 properties. |
| DT symptom in the pak | `<Condition key="Health\|unc_sectors" operator="above" type="dtmetric" instanced="false" />`. There is no `DT_ABOVE` anywhere in `content/`. |
| Dimension 13 (parsed from the built pak) | 7 alerts and 11 symptoms. No single-child `SymptomSets`, every `SymptomSet ref` resolves, and all cycle values are integers. Disk Failing still ORs the SMART symptom and the DT symptom. |
| describe.xml | `rootResourceKind="SynologyWorld"`, unchanged. |
| `defect-gate --pak synology` | `no open blocking defects affecting synology` |

**Read-only NAS probe** (DS1520+, DSM 7.3.2, session `VCFCFReview35r4`; form POST login, logout `True`; no secret or sid printed):
- `load_info` keys: `detected_pools`, `disks`, `env`, `missing_pools`, `overview_data`, `ports`, `sharedCaches`, `ssdCaches`, `storagePools`, `volumes`. Both unassembled-pool keys are lists and empty, so the lab still declares every kind (the fix does not stop the 28 legacy objects being marked).
- Pool `reuse_1` is `normal`. Volume `/volume1` has `pool_path` `reuse_1`, which is a listed pool, and `cache.id` `alloc_cache_1_1`, which is a listed cache. `sharedCaches` holds `shared_cache_1`, `is_missing` false. So none of the R3-W1 contradiction flags fire on a healthy NAS.
- Share list: 20 rows, `total` 20, so the R3-N1 guard passes.
- `overview_data`: `status_level` `status_level_normal`, `space_affect_by_eunit_lost` false, `space_affect_by_location_mismatch` false, `incompatible_eunit` [], `pools_to_show.detected_pool` [].
- DSM's `storage_panel.js` (unauthenticated static file): an unassembled pool is flagged `is_unassembled_pool: true`. `isMissingPool` is that flag plus a `missing_drives` list, and `isDetectedPool` is the flag without one. `isPool()` holds when `pool_path === id`, which confirms that a volume's `pool_path` is matched against the pool's `id` (the R3-W1 check depends on this). DSM's UI defaults `load_info` to include `hotSpares: []`; DSM 7.3.2 does not send that key here.

### Round 3 findings

| Finding | Status | Evidence |
|---|---|---|
| **R3-B1** missing and detected pools | **Resolved** | `SynologyAdapter.java:685-692` reads both keys. `ReadKinds.noUnassembledPool` needs both to be lists and both empty, so an absent key is no evidence. `kinds()` (`ReadKinds.java:321-327`) gates Pool, Volume and Disk through `storageComplete`, and gates SSD Cache, LUN and Export on `noUnassembledPool`. `noPoolConfigured` returns false unless `noUnassembledPool` holds, which closes the single-pool path (HDDs pulled, cache disks left). If `unassembledPools` is never called, the field defaults to false and nothing on a pool is declared (pinned). ReadKindsTest runs the DX517 multi-pool path for 30 cycles with no miss counted. |
| **R3-W1** contradictory pointers | **Resolved** for the three named cases | `pool_path` naming an unlisted pool leaves Pool out. A `cache.id` naming an unlisted cache, or a shared cache with `is_missing`, leaves SSD Cache out. Mutation-killed. A fourth pointer of the same class is not checked: R4-W1. |
| **R3-W2** CI buildkit pin | **Open (pre-tag action, not code)** | `build-pak-on-tag.yml:53` is still `sdk-buildkit-v1`. `gh release` shows `sdk-buildkit-v1 → v1.0.20`, latest v1.0.20, and no 1.0.22 or 1.0.23 published. |
| **R3-W3** docs parity | **Resolved** | "Removed objects are deleted (build 35)" appears in `docs/_index_extra.md` and the merged `docs/README.md` (identical text), plus a Notable Behaviors bullet in `docs/overview.md`. The README anchor slug matches the heading. README:173ff now covers missing and detected pools, contradictions and the paged share list, so "a failed read never deletes anything" is true for every path this review found. |
| **W2** DT import live proof | **Open (devel proof)** | The pak form is right (above). The devel import is still unproven. |
| **R3-N1** share `total` | **Resolved** | `ReadKinds.exports` takes `total`, where -1 means absent. A non-numeric `total` reads as 0, which is not equal to the row count, so it fails safe. |
| **R3-N2** CHANGELOG twice | **Resolved** | There is one build 35 vanished-object entry. It states the shipped rule and the cost, including the missing-pool gap. |
| **R3-N3** traversal render proof | **Open (devel proof)** | Unchanged: static evidence only. |

### Hunt: empty, partial, contradictory or failed reads (this delta)

- **Failed reads.** load_info is required, so a failure throws and `lastRead` stays null. LUN, share and UPS failures leave their kinds out (unchanged, pinned).
- **Absent keys.** `missing_pools` or `detected_pools` absent declares nothing on a pool. `total` absent is accepted, as DSM 7.3.2 sends it present (20 of 20).
- **Wrong types.** A non-list `missing_pools` or `detected_pools` is no evidence. A non-list `ssdCaches` gives `cacheIds` empty, so any volume `cache.id` marks the cache list dangling, and `cachesRead` is false anyway. `asBoolean` on an absent `is_missing` is false. That is the healthy reading, which is the right default because DSM 7.3.2 sends the field (`False`).
- **Ordering.** `unassembledPools` and `contradictions` are each called exactly once, before `lastRead` is set. test_vanished_wiring pins both the count and the order.
- **Not covered (fails toward deletion):** R4-W1 below.

### Judgment on the stated gap: a missing pool keeps its last status and raises no alert

**Not blocking for build 35. Recorded as R4-W2 and a registration candidate.** The reasons:

1. **No regression.** Up to build 34 a pool that left `storagePools` was equally stale and silent. Build 35's only new harm was deletion, and R3-B1's fix removes it. The pool object now stays, and `collectStoragePool` logs a WARN `storage pool <id> absent from snapshot` each cycle (`SynologyAdapter.java:1206`). That WARN is the operator-visible trace.
2. **Gap honesty is met** (skill § *Gaps, name them, never hide them*). README, REFERENCE.md ("A missing pool is not a deleted pool") and the CHANGELOG all say the pool keeps its last status and raises no alert.
3. **No status value has been seen** (`knowledge/rules/no-fabricated-metrics.md`). The DSM UI source shows that a missing pool is identified by `is_unassembled_pool` and `missing_drives`, not by a status string the adapter could pass through. Inventing `missing` as `status` would publish a value DSM was never seen to send. That would also need an unverified assumption: that the `id` of a `missing_pools` entry equals the old `storagePools` id.

The cost is real, though. An operator looking at the pool sees its last status, usually `normal`, which is a stale green. Before 1.0.0.35 is tagged for wide release, the follow-up should be one of:
- Publish `overview_data.status_level` and `space_affect_by_eunit_lost` on the DiskStation, and alert when they are not normal or false. Both fields and their normal values were seen on the lab, so this needs no unseen value.
- Or publish a pool-presence property derived from membership in `missing_pools`, once a sample confirms the id.

### WARNING

- **R4-W1. A disk's `used_by` naming a pool that `storagePools` omits is not treated as a contradiction.**
  - **Where:** `SynologyAdapter.java:666-671` gathers `diskUsedBy`. It feeds only `noPoolConfigured` (the empty-list proof) and `noCacheConfigured`, never the non-empty case.
  - **Authority:** the same as R3-W1 (tier2_architecture.md §Vanished objects; UniFi R2-W1, a parent that names a child the list omits).
  - **Path:** a multi-pool NAS. Pool B leaves `storagePools`, but DSM puts it in neither unassembled list (for example an expansion unit DSM flags in `overview_data.incompatible_eunit`, or `space_affect_by_eunit_lost` true). Its disks still say `used_by: reuse_2`. `pools > 0`, so Pool is declared, and B is marked after 12 cycles.
  - DSM's own UI would also not show such a pool, so this path needs DSM to contradict itself. That is why this is a WARNING and not BLOCKING.
  - **Fix (cheap, fails safe):**
    - In the disk loop, set `poolDangling` when a non-empty `used_by` is neither a listed pool id nor a listed shared cache id.
    - Optionally, leave the storage kinds out when `overview_data.space_affect_by_eunit_lost` is true or `incompatible_eunit` is a non-empty list. Both fields were seen on the lab.
    - An unknown `used_by` value, such as a hot spare, then only stops pool marking on that NAS, which fails safe.
  - **Registration candidate** if it ships unfixed.
- **R4-W2. A missing pool stays green.** This is the stated gap, judged above. It is not a regression and it is documented. **Registration candidate**, so the follow-up is tracked and not lost in the CHANGELOG.
- **Carried:**
  - R3-W2 (buildkit pin) blocks the tag, not this approval.
  - W2 (DT import) is a devel proof item.

### NIT

- **R4-N1.** `validate-sdk` prints OK with the RULE-019 compat check SKIPPED for 9.1.1 and 8.18.7 unless the jars are supplied. This review ran it with both jars and it was clean. Make sure the release CI sets `VCFCF_SDK_COMPAT_REQUIRED=1` with the jars available, so a tag cannot ship on a skipped check.

### Registry check (`knowledge/context/defects.md`)

No open defect affects synology: DEF-001, -003, -005 and -006 are closed, and `defect-gate --pak synology` is clean. DEF-001 (secrets in logs) was re-checked for this delta. The commit adds no log line. The existing `absent from snapshot` WARN carries only the pool, volume, disk, cache or LUN id, or the share name.

**Registration candidates:** R4-W1 if unfixed, R4-W2 (follow-up tracking), and W2 if the DT import is unproven at tag.

### What the devel proof must show before a `v1.0.0.35` tag

1. **Buildkit:** 1.0.23 published, and `sdk-buildkit-v1` moved to it or the workflow pinned to `sdk-buildkit-v1.0.23` (R3-W2). The CI-built pak's unc_sectors condition is `type="dtmetric"`.
2. **Import:** on devel 8.18 and devel_9_1, the Suite API shows all 11 symptoms and all 7 alerts, including "Disk Uncorrectable Sectors Increasing" and Disk Failing with both symptom sets (W2).
3. **Traversal:** the "Synology DiskStation Storage Tree" renders World > DiskStation > pools, volumes, disks, caches, LUNs and exports in the UI, including the Datastore hops (R3-N3).
4. **Vanished objects:**
   - The 28 legacy objects (empty `diskstation_id`) go to Not Existing about 12 cycles after the upgrade. The legacy World stays.
   - None of the re-keyed live objects changes state.
   - The collector log shows no ERROR from `markVanished` and no `absent from snapshot` WARN for a live object.
5. **Healthy lab, every kind declared:** after the marking window, the re-keyed live set (1 pool, 1 volume, 7 disks, 1 cache, 2 LUNs, 16 exports, World, DiskStation) is still Data Receiving.
6. **Issue #16 and #42 carry-over:** collection works over POST (no 119 errors), and LUN and NFS latency values are now in the ms range.

### If shipped as-is

- The 28 legacy duplicates go as documented.
- A failed, empty, paged or self-contradictory DSM read deletes nothing, with one narrow exception (R4-W1): DSM drops a pool from every list while its disks still name it.
- A missing pool or an unplugged expansion unit no longer deletes anything. But the pool keeps its last status, raises no alert, and shows only as a WARN in the collector log.

## Round 5 (fix round for Round 4, plus the storage-health alerts, 2026-10-28)

- **Commits reviewed:** 9190fe3 and 22a1a31 on 4f354a0 (adapter branch `build-35`). 9190fe3: `StorageOverview.java` (new), `ReadKinds.java`, `SynologyAdapter.java` (enumeration evidence and 8 DiskStation properties), describe.xml (attributes 323-330), resources.properties, tests, CHANGELOG, README, REFERENCE. 22a1a31: 8 symptoms, 2 alerts, 2 recommendations, `adapter.yaml` `bundled_content`. **22a1a31 touches no doc.**
- Designs: `knowledge/designs/alerts/synology-storage-degraded.md`, `knowledge/designs/alerts/synology-expansion-unit-lost.md`. The content matches both (operators, values, severities, ANY of the sets, sub_type 18, health badge).
- **Verdict: CHANGES REQUESTED** (1 BLOCKING / 1 new WARNING + carried / 4 NIT). The code is right and fails safe. The one BLOCKING is docs only: every doc surface still says the pak ships seven alerts, and the two new alerts, eight symptoms and two recommendations appear in no doc.

### Independent re-runs

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | All pass, rc 0, including the new StorageOverviewTest, ReadKindsTest (disk naming an unlisted pool, lost/incompatible expansion unit, 30 cycles each) and the python wiring checks. |
| Test strength | 7 mutations in scratch exports of HEAD, **6 killed** on an assertion: `!diskPoolDangling` dropped from POOL; `!expansionUnitAffected` dropped from `everyPoolAccounted`; `eunitLost` made to need `"true"` (non-boolean no longer affected); `eunitIncompatible` made to need a list; the shared-cache exemption in `diskNamesUnlistedPool` removed; `level()` forced to the UI defaults. **Survived:** renaming `sysStatus.get("system_need_repair")` to a wrong key (R5-N2). |
| `validate-sdk` | OK. `VCFCF_SDK_COMPAT_REQUIRED=1`, javac 25, both `--sdk-compat-jar`: 9.0 (`--release 17`), 9.1.1.0100 (`--release 25`), 8.18.7 (`--release 11`) all clean. |
| `build-sdk` (scratchpad) | Reproduces `vcfcf_sdk_synology_diskstation.0.0.0.35.pak`. Adapter tree clean afterwards. |
| `pak-compare` vs `dist/…0.0.0.34.pak` | **PASS: 0 BLOCKING, 1 WARNING, 29 INFO.** The WARNING is the SynologyDiskstation attribute count, now 42 vs 30: the 4 round 2 properties plus the 8 new ones. |
| Content in the unpacked pak | **19 symptomdefs, 9 alertdefs.** The unc_sectors symptom is `<Condition key="Health\|unc_sectors" operator="above" type="dtmetric" instanced="false" />`. |
| Symptom keys vs describe.xml (parsed) | Every new condition is `type="property" valueType="string"` with `==` or `!=` on a string value, and every key resolves to a `dataType="string" isProperty="true"` attribute under `Health` on `SynologyDiskstation`. |
| Dimension 13 (parsed from the built pak) | 9 alerts, 19 symptoms. No single-child `SymptomSets` (Storage Degraded has 6 sets, Expansion Unit Lost 2), every `SymptomSet ref` resolves, every cycle value is an integer (`3`). |
| `defect-gate --pak synology` | `no open blocking defects affecting synology` |

### Read-only NAS probe

DS1520+, DSM 7.3.2, session `VCFCFReview35r5`, form POST login, logout `True`, no secret or sid printed.

| Field | Lab value | Published as | Fires? |
|---|---|---|---|
| `overview_data.status_level` | `status_level_normal` | `storage_status_level` = same; `storage_status` = `normal` | no (needs `danger` / `attention`) |
| `overview_data.sample_level_str` | `{normal: status_level_normal, attention: status_level_abnormal, danger: status_level_danger}` | used by `level()` | |
| `space_affect_by_eunit_lost` | `False` | `expansion_unit_lost` = `false` | no |
| `incompatible_eunit` | `[]` | `incompatible_expansion_units` = `0` | no |
| `missing_pools`, `detected_pools` | `[]`, `[]` | `0`, `0` | no |
| `env.status.system_crashed`, `system_need_repair` | `False`, `False` | `false`, `false` | no |
| disk `used_by` | 5 x `reuse_1`, 2 x `shared_cache_1` | pools `[reuse_1]`, shared caches `[shared_cache_1]` | `diskNamesUnlistedPool` false, so every kind is still declared on the lab |

**Nothing fires on the healthy NAS.** Every symptom is present-only: each property is skipped when DSM did not send the field (`propIfPresent`, null from `flag`, `count` or `level` on absent, wrong-typed or unknown values), so an unread value cannot raise anything. `Boolean.toString` gives `true`/`false`, so `flag()` sees the JSON booleans as text. `load_info` is a required read, so `s.storage` is always populated when the DiskStation is collected.

### Mapping vs DSM's Storage Manager code

Re-read `webman/3rdparty/StorageManager/storage_panel.js` (unauthenticated static file, fetched this round):
- `loadOverview` takes `status_level`, `sample_level_str || state.sampleLevelStr`, `space_affect_by_eunit_lost || false` (stored as `isSpaceIssueByMultipath`) and `incompatible_eunit`. The module default is `sampleLevelStr: {danger: "danger", attention: "abnormal", normal: Ks}` with `Ks = "normal"`, which is `StorageOverview.UI_DEFAULT_LEVELS` exactly.
- `isLevelDanger(e)` is `sampleLevelStr.danger === e`, `isLevelAttention` likewise. `level()` does the same equality, so **`storage_status` matches the UI**.
- `incompatibleEunitToShow.length > 0` is a Warning (attention) row. **Matches** (WARNING symptom on `!= 0`).
- `sysRAIDCrashed` (`env.status.system_crashed`) is a Critical row. **Matches.**
- `missing_pools` and `detected_pools` are the pool lists DSM's `loadPool` takes. **Matches** (the symptoms count list entries).
- **Diverges:** `space_affect_by_eunit_lost` never raises a row on its own. Every use is `isSpaceIssueByMultipath && isLevelDanger(spaceStatusLevel)` or the message wording inside `getPoolAbnormalMessage`. The adapter raises CRITICAL on the flag alone (R5-W1).
- **Narrower in the UI:** the "repair system partition" row needs `!sysRAIDCrashed && !sysRAIDRebuilding && !isLevelDanger(...)` and also counts `rootbackup_need_repair` (R5-N3).

### Round 4 findings

| Finding | Status | Evidence |
|---|---|---|
| **R4-W1** disk `used_by` naming an unlisted pool; expansion-unit gates | **Resolved** | `StorageOverview.diskNamesUnlistedPool` feeds `ReadKinds.disksNameUnlistedPool`, which keeps POOL out (`ReadKinds.java:357`). `eunitLost` / `eunitIncompatible` feed `expansionUnits`, and `everyPoolAccounted` gates Pool, Volume, Disk, SSD Cache, LUN and Export (`ReadKinds.java:355-364`). Absent fields are no evidence; a wrong type counts as affected, which fails safe. Both calls happen once, before `lastRead` (test_vanished_wiring pins this). Mutation-killed. |
| **R4-W2** a missing pool stays green | **Resolved in code and content**, live proof owed | `Health\|missing_pools` / `detected_pools` / `storage_status` / `expansion_unit_lost` on the DiskStation, with the Storage Degraded and Expansion Unit Lost alerts on them. A pool that leaves `storagePools` now raises an alert on the DiskStation, not just a log WARN. No degraded value has been seen live; the recommendation text says so. |
| **R4-N1** compat check SKIPPED without jars | **Open (CI action)** | This review ran with both jars and all legs ran. Release CI must still set `VCFCF_SDK_COMPAT_REQUIRED=1` with the jars. |
| **R3-W2** CI buildkit pin | **Open (pre-tag action)** | Unchanged. |
| **W2** DT import live proof | **Open (devel proof)** | The pak form is right (`dtmetric`, above). The devel import is still unproven, now for 19 symptoms and 9 alerts. |
| **R3-N3** traversal render proof | **Open (devel proof)** | Unchanged. |

### BLOCKING

- **R5-B1. The docs contradict the pak: they say seven alerts, and it ships nine.**
  - **Where:** `README.md:29-41` ("all seven are on after install", 7-row table), `REFERENCE.md:576-590` ("All seven are enabled", 7-row table), `docs/_index_extra.md:18-21` and the merged `docs/README.md:57-60` ("The pak ships seven alerts"), `docs/overview.md:213-216` ("Build 35 ships seven alerts"), `CHANGELOG.md:14` ("7 alerts, 11 symptoms and 6 recommendations").
  - **Authority:** review dimension 11 (docs that contradict actual behaviour are BLOCKING); author hard rule 9 (a CHANGELOG line per change).
  - 22a1a31 adds Storage Degraded and Expansion Unit Lost, 8 symptoms and 2 recommendations, and touches no doc. An operator browsing the pak repo sees a seven-alert pak; two CRITICAL-capable alerts on the DiskStation are invisible until they fire. README:186 now names the properties that show a missing pool but not the alert that fires on them.
  - **Fix:** add both alerts to the README and REFERENCE.md Bundled alerts tables (object DiskStation; each symptom, its condition and severity; the DSM source of each value; "not seen degraded live"); change "seven" to "nine" on all five surfaces and re-run `docs-gen` so `docs/README.md` follows `_index_extra.md`; one CHANGELOG line for 22a1a31 and correct the counts on line 14 (9 alerts, 19 symptoms, 8 recommendations).

### WARNING

- **R5-W1. Expansion Unit Lost raises CRITICAL on a flag DSM's UI only acts on together with a Critical storage level.**
  - **Where:** `symptoms/synology_expansion_unit_lost.yaml` (`Health|expansion_unit_lost` EQ `true`, CRITICAL); `alerts/synology_expansion_unit_lost.yaml` set 1.
  - **Authority:** the brief ("the mapping matches DSM's UI code"); `knowledge/rules/no-fabricated-metrics.md` (publish and alert on what the source says, as the source means it).
  - In `storage_panel.js` every use of `space_affect_by_eunit_lost` (`isSpaceIssueByMultipath`) is ANDed with `isLevelDanger(spaceStatusLevel)` or only changes the wording of the pool-abnormal message. DSM never shows a problem on the flag alone. The `StorageOverview` javadoc describes this correctly; the symptom does not follow it. If DSM ever sends `true` with a normal level (the UI's name for it suggests a multipath case, e.g. one of two expansion cables lost), the pak raises a CRITICAL that DSM itself does not show. Never seen `true` on the lab, so this is unproven, not observed.
  - Not BLOCKING: it fails loud, not silent; ReadKinds' use of the same flag fails safe (it only stops marking); and a real lost unit also drives `storage_status` to `danger`, which Storage Degraded catches.
  - **Fix (content only):** make set 1 of Expansion Unit Lost `ALL` of Expansion Unit Lost and Storage Critical, matching the UI. Keep the published property as is. **Registration candidate** if it ships unfixed.
- **Carried:** R3-W2 (buildkit pin) blocks the tag; W2 (DT import) is a devel proof item.

### NIT

- **R5-N1.** `SynologyAdapter.java:1076-1088`: `levelNames` was inserted between `propIfPresent`'s javadoc and `propIfPresent`, so the "Build 35 (review W1): publishes value unless it is null" block now sits orphaned above `levelNames`' own javadoc. Move `levelNames` above that comment.
- **R5-N2.** `env.status` key names are not pinned. `test_collect_wiring.py` pins `storageData.get("env").get("status")` but not `"system_crashed"` / `"system_need_repair"`; a typo in either survives every test (mutation above) and silently stops both properties and their symptoms. Add the two literals to the wiring assertions, as `space_affect_by_eunit_lost` already is.
- **R5-N3.** System Partition Needs Repair publishes `system_need_repair` raw. The UI shows that row only when the system partition is not crashed, not rebuilding and storage is not Critical, and it also counts `rootbackup_need_repair` (absent on DSM 7.3.2 here). The overlap is inside the same alert, so the operator impact is a second symptom, not a wrong alert. Document it in REFERENCE.md, or publish `rootbackup_need_repair` when DSM sends it.
- **R5-N4.** `diskNamesUnlistedPool` accepts listed pools and listed shared caches only. A disk in a non-shared SSD cache, or a hot spare, whose `used_by` names something else turns pool marking off on that NAS for good. That fails safe (pools are never marked, never deleted), and the INFO-less silence is the cost. Consider accepting `ssdCaches[].id` too, and say in REFERENCE.md that an unknown `used_by` keeps pool removal off.

### Registry check (`knowledge/context/defects.md`)

No `defects.local.md`; the factory registry applies. No open defect affects synology: DEF-001, -003, -005 and -006 are closed, and `defect-gate --pak synology` is clean. DEF-001 (secrets in logs) re-checked for this delta: neither commit adds a log line, and the new properties carry DSM status strings and counts only.

**Registration candidates:** R5-W1 if it ships unfixed; W2 if the DT import is unproven at tag. (R4-W1 and R4-W2 are resolved and no longer candidates.)

### What the devel proof must show before a `v1.0.0.35` tag (updated)

Items 1 and 3 to 6 of Round 4 stand. Item 2 becomes: on devel 8.18 and devel_9_1, the Suite API shows **all 19 symptoms and all 9 alerts**, including Disk Uncorrectable Sectors Increasing, Disk Failing with both sets, Storage Degraded with six sets and Expansion Unit Lost with two. Add:

7. **Storage health on the DiskStation:** the lab DiskStation shows `Health|storage_status` `normal`, `Health|storage_status_level` `status_level_normal`, `expansion_unit_lost` and both system-partition flags `false`, and the three counts `0`; Storage Degraded and Expansion Unit Lost are not raised.

### If shipped as-is

The code does what it says: a missing pool, a pool awaiting assembly, a Critical or Warning storage verdict from DSM, or a crashed system partition raises Storage Degraded on the DiskStation, and nothing on the storage side is deleted while DSM reports any of them. But an operator reading the README or the pak docs is told the pak has seven alerts and never learns about the two new ones, and an expansion-unit flag that DSM itself treats as secondary can raise a CRITICAL DSM does not show.
