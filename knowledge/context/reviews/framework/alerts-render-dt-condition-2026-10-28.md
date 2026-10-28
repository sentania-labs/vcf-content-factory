# Framework review: DT symptom condition in content-import XML (buildkit 1.0.23)

- **Branch:** `dt-symptom-content-xml` at `886b210` (55ab72d fix, 65d6e95, merge of main fd5bc21). Branch contains current `origin/main`.
- **Area:** `src/vcfcf_core/alerts/render.py`, `src/vcfcf_core/symptoms/loader.py`, `src/vcfcf_managementpacks/buildkit.py`
- **Reviewer:** framework-reviewer, 2026-10-28 (America/Chicago)
- **Verdict:** APPROVE. 0 BLOCKING / 2 WARNING / 3 NIT

## Change

`_add_condition_element` rendered `metric_dynamic` as `type="metric" operator="DT_<dir>"`. Content import rejects that with `Invalid operator:dt_above` and drops the symptom, every symptom in the same alertdefs file, and every alert that references them, while the pak install still reports success (Synology 0.0.0.35). The fix emits `type="dtmetric" operator="above|below|abnormal" instanced=...` with no thresholdType, value, or valueType. An unknown direction now raises in the renderer. The symptom loader rejects `metric_dynamic` on a `Super Metric|` key. `BUILDKIT_VERSION` is 1.0.23. The REST path (`CONDITION_DT` / `DT_<dir>`) is unchanged.

## Evidence checked independently

| Claim (doc `knowledge/context/wire-formats/symptomdef_dt_condition_import.md`) | Result |
|---|---|
| XSD `alertDefinitionSchema.xsd` ConditionType: `dtmetric`/`dtsuper` enum, "For dtmetric and dtsuper: above, below, abnormal", `instanced` applies to dtmetric | Confirmed, lines 442-560 (460, 462, 514, 533, 545) |
| devel_9_1 VMSP `content/alertdefs/alertdefs.xml` line 355 `operator="above" type="dtmetric"` | Confirmed over read-only SSH. VMSP alertdefs and the vSphere describe.xml are the only `dtmetric` hits under `user/plugins/inbound`, apart from XSD copies. No file there uses `DT_` operators |
| vmwarevi_adapter3 describe.xml lines 7858, 8438, 8448, 8453 | Confirmed verbatim. 7858 has `instanced="true" operator="below"` |
| devel_9_1 analytics log `Invalid operator:dt_above` at 07:14:38.800Z and 07:14:42.538Z | Confirmed |
| devel_8_18 `vcops-bridge.log` lines 4478, 4484 | Confirmed: 2 hits at 06:35:05 and 06:35:10 |
| SampleDefaultPolicy.xml (7 lines) and HOL autoscale-policy.xml line 3112 | Confirmed, all `dtmetric` with lowercase operators |
| REST `CONDITION_DT_SUPER` exists (justifies the loader refusal) | Confirmed in `reference/docs/internal-api-9.1.json` (DTSM-condition) |

## Checks re-run

- **validate chain** (all seven packages, worktree): all pass.
- **pytest, full suite** (worktree): 3121 passed, 6 failed, 13 skipped. All 6 failures are in `test_release_naming_phase_v2_item1.py` and `test_validator_phase2.py`. They are environmental: the worktree has no gitignored `content/sdk-adapters/`. In scratch clones of the branch and of main, with `content/sdk-adapters` linked, both files pass (91/91) on both refs.
- **New guards fail on the old code:** with `tests/test_symptom_dt_condition_xml.py` copied onto main, 8 fail and 6 pass. The 6 that pass are the REST-unchanged checks and the positive cases, as they should.
- **Render regression:** I rendered every symptom and alert in `content/`, `third_party/`, and every `content/sdk-adapters/*` on main and on the branch (66 objects). The only symptom that differs is Synology `Disk Uncorrectable Sectors Increasing`, and the diff is exactly the intended one:
  `operator="DT_ABOVE" type="metric"` becomes `operator="above" type="dtmetric"`. The synology alert hash differences come from my harness, which embeds all of the pak's symptoms. The real builder embeds only the symptoms an alert references.
- **Kit:** built `sdk-buildkit-1.0.23.tgz` to scratch. `alerts_render.py` in the kit carries the fix and has no new imports, so no new rewrite rule is needed. Kit `validate-sdk` on synology: OK. Factory `validate-sdk` synology: OK. `-k buildkit` tests: 18 passed.
- **pak-compare:** n/a. No pak was built.

## Scope questions from the brief

- **Other Condition XML emitters:** none. `alerts/render.py` is the only writer of `<Condition>`. `vcfcf_managementpacks/builder.py` writes an empty `<SymptomDefinitions>`. `sdk_builder.py` content/symptomdefs and alertdefs go through `vcfcf_alerts.render.render_alert_content_xml`, which is the core module. The kit uses its rewritten copy. The REST `_condition_to_wire` is the only other DT spelling, and it is correct.
- **Factory zips:** the bytes are unaffected. No `content/` or `third_party/` YAML uses `metric_dynamic`; synology is the only user. The factory install script installs symptoms from `symptoms.json` over REST, which is unchanged. See W2 for the signal gap.
- **Release notes:** missing. See W1.

## Dimension walk

1. **Global/pak leak (00d3382):** the change is inert on the standalone content-import path for all repo content, verified by rendering. It applies uniformly to both paths, which is correct because both feed the same importer (`DescribeConversionUtil`).
2. **Key/label collision (6c59f6b):** n/a. No key derivation changed.
3. **Wire conformance:** matches the vendor XSD and all vendor examples. `abnormal` is schema-valid but no vendor file uses it (the doc says this).
4. **Loader/validator:** the Super Metric refusal is loud, and no content hits it. The static-on-SM case is still allowed (tested, and `content/symptoms/cluster_storage_paths_inconsistent.yaml` still validates). Symptom keys are literal strings, never `@supermetric` tokens, so the prefix check cannot be bypassed by late resolution.
5. **Render regression:** clean apart from the intended synology delta.
6. **Builder/pak:** no structural change. Synology must be rebuilt to land the symptom and the `Disk Failing` alert.
7. **Corpus:** clean (above).
8. **Silent downgrade:** none. The fix removes one.
9. **Stale signal:** `BUILDKIT_VERSION` was bumped. See W2 for `CURRENT_TEMPLATE_VERSION`.
10. **Tests:** good. The vendor attribute set is checked exactly, as are the alertdefs embedding, REST stability, and the SM refusal.

## Findings

### WARNING

**W1. `.github/release-notes-buildkit.md` has no "Behavior since 1.0.23" section.** Every kit bump since 1.0.15 has added one (1.0.22: e1e18f9). The publish workflow sends this file verbatim as the release body (`publish-buildkit.yml` lines 186-198). As things stand, the 1.0.23 release page says nothing about its only behaviour change, and pak maintainers are not told to rebuild.
→ Add a section covering four things. First, `metric_dynamic` symptoms now import (`type="dtmetric"`, lowercase operator); before this, they and every alert using them were dropped silently. Second, rebuild synology to land `Disk Uncorrectable Sectors Increasing` and `Disk Failing`. Third, `validate-sdk` now refuses `metric_dynamic` on a `Super Metric|` key. Fourth, other paks' built bytes are unchanged. Also refresh the 1.0.22 "Version note: open PR #281 holds 1.0.21", since #281 has merged. The orchestrator owns `.github/`.

**W2. `alerts/render.py` writes `AlertContent.xml` into every factory zip (`src/vcfcf_core/packaging/assembly.py:399`), but it is not on the `CURRENT_TEMPLATE_VERSION` bump list (`src/vcfcf_core/packaging/template_version.py` docstring) or on CLAUDE.md's "After tooling changes" list.** Nothing in this repo is affected. A clone that authored its own DT symptom, though, holds an `AlertContent.xml` (the "Alerts > Alert Definitions > Import" UI path in the zip README) that drops the symptom silently, and `check-staleness` will keep reporting it current. This is the dimension-9 signal class. It is a WARNING, not BLOCKING, because the scripted install path uses REST JSON, which was always correct.
→ Add `vcfcf_core/alerts/render.py (AlertContent.xml wire format)` to both lists and bump `CURRENT_TEMPLATE_VERSION` with a history line naming this fix. Alternatively, record an explicit no-bump decision with this reasoning in the tier2 row and the template_version history. Silence is not acceptable.

### NIT

**N1.** The `knowledge/context/tier2_architecture.md` change-log row reads "#281 holds 1.0.21, #287 holds 1.0.22; whichever merges later re-checks the number". Both have merged, so state that 1.0.23 follows the merged 1.0.22.

**N2.** `symptomdef_dt_condition_import.md` §3 still reads "Today: ... Must be". Relabel it as before/after now that the status is fixed.

**N3.** The new shape has not been imported live yet. VMSP omits `instanced`, while we emit `instanced="false"`. That is schema-valid (XSD optional boolean), and static conditions already import with it, but it is not observed on `dtmetric`. When synology is rebuilt and installed, confirm `SYMPTOM_DEFINITION.IMPORT result="success"` in the analytics audit log and 11 symptoms / 7 alerts over REST.

## If shipped as-is

The fix is correct. Synology's DT symptom and `Disk Failing` alert land on the next rebuild. Kit consumers get a release page that does not mention the change, and any clone's factory zip with a DT symptom is never flagged stale.
