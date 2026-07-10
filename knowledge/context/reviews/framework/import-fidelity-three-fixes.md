# Framework Review — import-fidelity three fixes

- **Branch:** `fix/report-subject-filter-escaping` (`main..HEAD`)
- **Commits:** `b16f3dd` (report SubjectType filter escaping), `3d5ba94`
  (alert multi-set SymptomSet wrapper + localization key length cap)
- **Areas:** `src/vcfops_reports/render`, `src/vcfops_alerts/render`,
  `src/vcfops_managementpacks/sdk_builder`, `src/vcfops_dashboards/render`
- **Reviewer:** framework-reviewer (read-only, pre-PR)
- **Date:** 2026-07-10
- **Verdict:** APPROVE (0 BLOCKING)

## Gates re-run (independently)

| gate | result |
|---|---|
| path audit | PASS — diff touches only 4 `src/vcfops_*` files, 3 `tests/` files, 2 `knowledge/context/` docs. No content YAML, `.claude/`, `.github/`, `designs/`. |
| validate ×7 | PASS (supermetrics, dashboards, customgroups, symptoms, alerts, reports, managementpacks) |
| pytest -m "" (full) | **695 passed, 4 skipped**, 285 warnings, 0 failed (50m53s) — matches tooling's claim exactly |
| pytest (targeted 4 files) | 38 passed (alert_symptomset_encoding, localization_key_length_cap, report_subject_filter_escaping, emit_fidelity_bugs) |
| render-regression | verified — full alert corpus re-rendered main vs HEAD; localization keys enumerated for the 4 offender views |
| pak-compare | n/a — no `describe.xml`/`template.json`/pak-shape change (but see staleness WARNING) |

---

## Fix 1 — report SubjectType `filter=` escaping (`vcfops_reports/render.py`)

**Correct.** The added map `escape(st.filter, {chr(34): "&quot;"})` is byte-for-byte
identical to the view/dashboard path (`src/vcfops_dashboards/render.py:627`,
`escape(filter_json, {chr(34): "&quot;"})`), so the report and view SubjectType
filters now encode identically.

Verified byte-exact against vendor ground truth
`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/Report - VOA - Supervisor Cluster for CSV export.xml`:
vendor emits `filter="[[{&quot;condition&quot;:&quot;EQUALS&quot;,…}]]"` —
inner quotes as `&quot;`, `&`/`<`/`>` via the default `escape()`. The fix
reproduces this exactly.

No-filter reports unchanged: the `if st.filter else ""` guard is preserved, so a
`SubjectType` without a filter emits no `filter=` attribute (identical to pre-fix).
`test_report_subject_filter_escaping.py` (155 lines) asserts the byte-exact shape
and the no-filter passthrough; passes.

Global/standalone import path: this is the standalone report content-import path
(no pak-specific default), and it now matches vendor. No leak.

---

## Fix 2 — alert multi-set `<SymptomSets>` wrapper (`vcfops_alerts/render.py`)

**Correct on every output path.** Re-rendered the entire alert corpus (14 alerts)
at `main` vs `HEAD` via `render_alert_content_xml` and diffed.

Independently confirmed against the wire-format spec
(`knowledge/context/wire-formats/alertdef_symptomset_import.md`):

- **Wrapper emitted iff ≥2 sets.** 7 alerts gain `<SymptomSets operator="…">`:
  6 in `content/alerts/` — synology ×4 (`disk_health`, `storage_pool_health`,
  `system_temperature`, `volume_space`), `vm_cpu_usage`, `host_compliance_score`
  — matching the brief, **plus** the SDK alert
  `content/sdk-adapters/vcommunity-vsphere/alerts/esxi-host-license-expiring.yaml`
  (7th, an SDK-adapter alert; in scope but not in the brief's `content/alerts/`
  count). Our esxi output is byte-structurally identical to the vendor
  `<SymptomSets operator="or">` 4-child shape.
- **Single-set alerts get NO wrapper** (`synology_fan_failure`,
  `synology_ups_on_battery`, `cluster_storage_path_inconsistency`) — the bare
  `<SymptomSet>` sits directly under `<State>`. Item (c) failure mode
  (single-symptom set wrongly wrapped, or multi-symptom set exploding into
  siblings) is **absent** — confirmed by re-render and by
  `test_multi_symptom_single_set_no_wrapper` (asserts 1 `<SymptomSet>`, 2
  `<Symptom>` children, no wrapper, no explosion).
- **`aggregation="any"` dropped** on every emitted `<SymptomSet>` — vendor-aligned
  per the spec ("not part of the vendor grammar"). Asserted absent in the tests.
- **Nested `<Symptom ref=…>` multi-symptom-set path** is not exercised by any
  corpus alert (no factory alert has a ≥2-symptom set); it is test-covered by
  `test_multi_set_alert_emits_single_symptomsets_wrapper` (mixed 1-symptom +
  2-symptom sets) and `test_multi_symptom_single_set_no_wrapper`. Adequate.
- **Emit-fidelity operator pins hold** — `test_emit_fidelity_bugs.py` (19 tests)
  passes; symptom `<Condition>` operator translation (`!=`, `>` etc.) intact.

Per-set `operator` derives from the set's own `operator` (`ALL→and`, else `or`)
and `applyOn` from `defined_on` (`SELF→self`); the wrapper `operator` from
`symptom_sets["operator"]`. Matches the spec's derivation rules.

See WARNING-1: the render-regression scope is larger than the brief stated.

---

## Fix 3 — localization key 64-char cap (`sdk_builder.py`, dormant twin in `dashboards/render.py`)

**Correct.** The cap is provably identity for keys ≤64: the diff only wraps the
existing return in `_cap_localization_key`, which returns the input unchanged when
`len(key) <= 64`. Therefore **existing short keys emit byte-identical pre/post** —
critical for `knowledge/lessons/pak-content-localization-bundles.md` (a re-keyed
short key would break localizationKey matching across every bundle).

Independently generated `content.properties` for the 4 offender
vcommunity-vsphere views (151 keys total): only the **2 distinct over-64
attributes** changed; the other 149 keys are byte-identical. Max post-cap key
length = 64. The offenders cap deterministically and uniquely:

- `virtualDiskAggregate_of_all_instances_numberWriteAverag_3f79f164` (was 65)
- `config_policies_override_network_resourcepool_moving_ov_4c68f737` (was 69)

Both appear in 2 views each (the "4 known offenders"), and the same attribute
maps to the same capped key in each — deterministic, no cross-view breakage.

- **Uniqueness under shared-prefix truncation** — the collision test is real
  (`test_two_long_keys_sharing_64_char_prefix_dont_collide`: `"a"*64 + suffixA`
  vs `+ suffixB`, both capped, asserted distinct). The 8-hex SHA-1 of the *full*
  attribute is the divergence source; a blind truncate would collide, this does
  not.
- **Guard trip-wire** (`_validate_localization_key_contract` Step 5) genuinely
  fails the build on an over-64 key — `test_guard_trips_on_synthetic_over_long_key`
  monkeypatches around the cap and confirms `[localization-key-too-long]` fires;
  `test_guard_silent_when_keys_are_capped` confirms no false-positive on the
  normal path.
- **Dormant twin** in `vcfops_dashboards/render.py::_attribute_to_localization_key`
  — identical logic. Confirmed it has **no call site** in `render.py` (only its
  definition), so it produces **zero change to any emitted dashboard/view
  output**. No global-default leak, no key-collision (this fix *prevents* the
  6c59f6b-class collision), no silent downgrade.

Note: I verified the cap at the source-generation level (rendering the offender
views' `content.properties` directly) rather than by building a pak — cleaner and
within the read-only boundary. The "rebuilt vcommunity-vsphere dev pak carries
capped keys" claim is confirmed at the generation stage that the pak build
consumes.

---

## Findings

### WARNING

- **[render-regression scope understated]** `vcfops_alerts/render.py` — the brief
  claim "3 single-set alerts byte-identical" is **inaccurate**. Re-render shows
  **all 14 alerts change output**, because `aggregation="any"` is dropped from
  *every* `<SymptomSet>`, including single-set alerts. The new output is *more*
  correct (vendor-aligned), so this is **not a regression** — but the packaging
  scope is wider than stated: every zip/pak that ships *any* factory alert is
  stale, not only the 6 multi-set ones. → Correct the staleness scope when
  re-briefing content-packager.

- **[stale distribution zips — rebuild required]** CLAUDE.md "After tooling
  changes" + dimension 9. The change touches `src/vcfops_dashboards/render.py`
  (mechanical stale-trigger), though that edit is dormant-only (zero output
  change). More materially: the **alert** output (`AlertContent.xml`, consumed by
  `sdk_builder`, `buildkit`, `packaging/builder`, `discrete_builder`) and the
  **vcommunity-vsphere view** `content.properties` genuinely change. Any bundle
  in `bundles/` / zip in `dist/` carrying these alerts or vcommunity-vsphere
  views is stale → delegate `content-packager` to rebuild before shipping.

- **[buildkit tarball propagation]** `src/vcfops_managementpacks/buildkit.py`
  vendors a copy of `vcfops_alerts/render.py` (as `alerts_render.py`) and
  `sdk_builder`'s helpers into the published `sdk-buildkit` tarball. Official SDK
  pak CI builds from that **published** tarball, not the factory checkout — so the
  alert-wrapper and key-cap fixes reach released SDK paks (synology, compliance,
  vcommunity) only after the buildkit tarball is regenerated/republished **and**
  each pak is rebuilt on a new `v*` tag. Flag this in the release path.

### NIT

- The dormant `vcfops_dashboards/render.py` cap helper duplicates the
  `sdk_builder` helper verbatim. The code comment already acknowledges "share one
  helper if practical" — a future consolidation would remove the drift risk of
  two identical copies. Not blocking.

---

## Defect-registry assessment (requested; read-only — recommendation only)

**A defect-registry entry is warranted.** The 6 corrected multi-set alerts shipped
in **released** paks with the pre-fix bug (bare `<SymptomSet>` siblings, no
wrapper → the platform keeps only the *last* sibling on import):

- synology pak — 4 multi-tier alerts (`disk_health`, `storage_pool_health`,
  `system_temperature`, `volume_space`) currently import as **last-tier-only**;
  the earlier tiers are silently dropped on every field install.
- compliance pak — `host_compliance_score` alert, same collapse.

This is a silent field-facing correctness defect (operators believe multi-tier
alerting is active when only one tier fires), exactly the class the defect
registry exists to track. Recommend `tooling`/orchestrator add an entry to
`knowledge/context/defects.md` describing the collapse, the fix commit (`3d5ba94`),
and the requirement that synology + compliance paks be rebuilt+republished (per
the buildkit-propagation WARNING) to clear it. I did **not** edit `defects.md`
(read-only corpus for this review).

---

## If shipped as-is

An operator gets: report SubjectType filters that import correctly (Fix 1),
multi-tier alerts that finally register all tiers instead of only the last one
(Fix 2), and vcommunity-vsphere views + all 11 reports that import instead of
aborting on the 64-char XSD limit (Fix 3). The one operational caveat is
packaging: the shipped `dist/` zips and released SDK paks still carry the old
alert/key output until content-packager rebuilds and the sdk-buildkit tarball is
republished — until then the field paks keep running last-tier-only alerts (hence
the defect-registry recommendation).
