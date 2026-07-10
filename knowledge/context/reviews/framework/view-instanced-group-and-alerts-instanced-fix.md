# Framework Review — instanced-group view columns + alerts instanced-condition fix

- **Branch:** `feat/view-instanced-group-columns` (diff `main..HEAD`)
- **Commits:** `aaab287` (design/review artifacts), `43821e3` (instanced-group
  view columns), `b9ea66f` (alerts renderer instanced/thresholdType/valueType fix + DEF-008)
- **Reviewer:** framework-reviewer (RULE-013 blanket gate)
- **Date:** 2026-07-10
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING / 1 NIT
- **Surfaces:** `src/vcfops_dashboards/loader.py`, `src/vcfops_dashboards/render.py`,
  `src/vcfops_alerts/render.py`

## Checks re-run (independent)

- **validate chain ×7** — PASS (supermetrics, dashboards, customgroups, symptoms, alerts, reports, managementpacks).
- **full pytest** — 485 passed, 4 skipped, 162 deselected. Targeted: the two new
  test files (`test_view_instanced_group_columns.py`, `test_symptom_condition_instanced_attribute.py`),
  `test_defect_gate.py`, `test_emit_fidelity_bugs.py` all green (79 in that subset).
- **render regression — dashboards/views:** re-rendered all 16 factory
  `content/views/*.yaml` on `main` vs `HEAD` via `render_views_xml`. **Byte-identical.**
  The instanced-group feature is confirmed inert on the existing generic column path.
- **render regression — alerts/symptoms:** re-rendered all 16 factory
  `content/symptoms/*.yaml` on `main` vs `HEAD`. The ONLY diffs are the newly-added
  `instanced="false" thresholdType="static" valueType="numeric|string"` attributes on
  every metric_static/property `<Condition>`. `operator`, `value`, `key`, `type`
  unchanged; symbolic operators (`&gt;`, `&lt;`, `==`, `!=`) preserved — the
  emit-fidelity pins hold.
- **pak-compare:** n/a (no reference-pak dir); not applicable to this change.
- **DEF-008 end-to-end:** rebuilt `vcommunity-vsphere` dev pak
  (`build-sdk`, `0.0.0.5`, no tag), extracted it, confirmed all five
  `content/symptomdefs/*.xml` carry `instanced="true" thresholdType="static"
  valueType=...` (NIC → `string`, license metric → `numeric`). The closing-evidence
  claim is real. Adapter repo doc bumps (`docs/README.md`, `docs/inventory-tree.md`)
  reverted with `git checkout --`; adapter tree confirmed clean; dev pak removed.

## Dimension walk

1. **Global-default / pak-specific leak (`00d3382`):** CLEAR. Dashboards change is a
   pure early-return guard (`if getattr(col, "instanced_group", None) is not None`) plus a
   new synthesis branch; no existing ViewColumn sets `instanced_group` (default `None`),
   so the standalone/global view-import path is provably inert — proven both by code and
   by the byte-identical 16-view render diff. The `GROUP_vCommunity` token, the
   colon-syntax attributeKey, and the property-column rollUpType-omission are all confined
   to the new `_xml_instanced_group_item()` path; the generic `_xml_attribute_item()` is
   untouched. No pak-local default leaks global.
2. **Key/label derivation collision (`6c59f6b`):** CLEAR. attributeKeys are synthesized
   as `{prefix}:{sample_instance}|{suffix}` from author-supplied fields, not derived from
   a transform-blind path; each member column carries a distinct suffix. No
   `localizationKey` is emitted (matches the 80+ reference-view ground truth in
   `view_column_wire_format.md`).
3. **Wire-format conformance:** VERIFIED against vendor ground truth, not vibes.
   - Symptom conditions: line 5 of `ESXi Host NIC Disconnected Symptom.xml`,
     `Windows Service Down Symptom.xml`, and `Dell EMC Server Physical Disk Life
     Remaining - Critical.xml` all confirm `instanced="true" ... thresholdType="static"
     ... valueType="string|numeric"` with **lowercase** values. The REST-path casing
     (`STATIC`/`NUMERIC` in `vcfops_symptoms/loader._condition_to_wire`) is correctly NOT
     copied — the two wire formats are cased independently, and a test locks this.
   - View driver Item property order matches all three cited report XMLs
     (`objectType, attributeKey="Instance Name", rollUpCount, isInstancedGroup,
     showInstanceName, instanceGroupName, keepInstanceSummary [, displayName]`).
   - Member Item order (property vs metric, rollUpType omitted for `isProperty=true`,
     `rollUpType="NONE"` for metric) matches the License view lines I inspected directly.
   - `keepInstanceSummary` is per-view (Packages=false vs Licensing/Services=true),
     correctly threaded from YAML, not hardcoded.
4. **Loader/validator correctness:** Four rejections verified by test AND by reading the
   code: attribute+instanced_group together, prefix-xor-suffix, member missing
   sample_instance, member without a matching driver in the same view. All raise
   `DashboardValidationError` with actionable messages. Additive-only — no previously-good
   content newly mis-validates (validate ×7 green over the whole corpus).
5. **Render regression vs known-good:** Covered above. Dashboards byte-identical; symptom
   diffs are exactly the intended new attributes and nothing else.
6. **Builder/pak structure:** No `builder.py`/template change. Dev-pak rebuild produced a
   structurally valid pak; symptomdefs land correctly.
7. **Corpus regression:** validate ×7 + full suite green. No red.
8. **Silent capability change/downgrade:** This change *reverses* a silent downgrade
   (DEF-008: every instanced symptom silently degraded to exact-string matching in built
   paks). The `metric_dynamic` omission of thresholdType/valueType is documented and
   mirrors the REST path's own CONDITION_DT omission — a loud, reasoned gap, flagged to
   api-explorer, not a silent one. Acceptable.
9. **Stale-zip discipline:** see WARNING below.
10. **Test coverage:** Strong. Both changed behaviors have dedicated, vendor-cited test
    files (loader validation + XML emission for views; instanced/casing/valueType-split
    for conditions). This is the render surface that was untested when the two historic
    escapes shipped — now covered.

Defect-registry coupling: DEF-008 is sequential (follows DEF-007), `Severity: blocking`,
`Status: closed`, `Affects: vcommunity-vsphere`. `test_defect_gate.py` green with it
present; `defect-gate --pak vcommunity-vsphere` reports no open blocking defects (release
gate correctly clears now that DEF-008 is closed). Path audit: only `src/vcfops_*/`,
`tests/`, `knowledge/context/**` touched — no content YAML, no `.claude/`, no `.github/`.

## WARNING

- [stale-zip discipline / CLAUDE.md "After tooling changes"] `src/vcfops_dashboards/render.py`
  is a **named** staleness trigger, and `src/vcfops_alerts/render.py` **materially changes**
  emitted symptom XML (every metric_static/property condition now gains
  `instanced/thresholdType/valueType`). Therefore every built artifact embedding symptom or
  dashboard content is stale — notably `bundles/storage-path-monitoring.yaml` (embeds
  symptoms+alerts) and the already-shipped SDK pak
  `vcfcf_sdk_vcommunity_vsphere.1.0.0.2.pak` (the exact broken artifact DEF-008 documents).
  → The orchestrator must delegate a `content-packager` rebuild of affected bundles, and the
  vcommunity-vsphere pak needs a fresh `v*` release (now unblocked — DEF-008 closed) before
  the fix reaches instances. This is a handoff/process note, not a code defect.

## NIT

- [`src/vcfops_dashboards/render.py` `_xml_instanced_group_item`] The driver Item always
  emits `displayName`, whereas the `ESXi Host License Information vCommunity.xml` exemplar
  omits it (the other two cited files include it). This is a documented, deliberate choice
  (display_name is a required ViewColumn field; 2-of-3 vendor files include it; both
  variants are server-accepted per the exports). Byte-faithful to the majority pattern, not
  to the License view specifically. Informational only — no action required.

## If shipped as-is

Operators get a working instanced-group view construct (one row per license/package/service
instance) and — more importantly — every `instanced: true` symptom now actually matches all
instances instead of silently collapsing to one, closing DEF-008. **Caveat:** the fix only
reaches instances after the affected bundles/paks are rebuilt (WARNING above); until then the
shipped `vcommunity-vsphere 1.0.0.2` pak remains the broken artifact.

---

## Addendum — commit `301145b` (Codex P2 on PR #46: member-column transformation companions)

- **Date:** 2026-07-10
- **Rebase:** branch rebased cleanly onto `origin/main` (commit hashes changed:
  `ea6e614` view columns, `6a074a7` alerts fix, `8c43647` prior review report,
  `301145b` this follow-up). Re-reviewed against the rebased tree.
- **Verdict:** APPROVE (0 BLOCKING). Original approval stands; this commit is
  additive-and-corrective, inert on all existing rendered content.
- **Findings (this commit):** 0 BLOCKING / 0 WARNING / 1 NIT (carry-forward).

### What changed

1. `_xml_instanced_group_item()` now emits `transformExpression` as a sibling
   Property **immediately before** `transformations` for TRANSFORM_EXPRESSION
   members, and handles MAX/TIMESTAMP.
2. `rollUpType` is now **unconditional `"NONE"`** for non-property instanced
   members — the previous `else "AVG"` fallback was removed.
3. `ViewDef._validate_column` **rejects** PERCENTILE and TIME_POINT on
   instanced_group member columns (fail-closed; no vendor evidence exists).
4. Wire-format doc updated with the survey and a documented out-of-scope
   `preferredUnitId` gap note.

### Independent verification

- **Vendor citations — verified at the cited spots in `View - Set 4.xml`**
  (`vmbro_vcf_operations_vcommunity/Management Pack/content/reports/`):
  - `cpu:0|Percent.DPC.Time` (Windows CPU Usage) — `rollUpType="NONE"`, MAX. ✓
  - `diskio:dm-0|read.time` (Linux Disk Performance) — `rollUpType="NONE"`,
    `transformExpression="(current-first)/60000"` emitted **immediately before**
    the `transformations` Property. ✓ (matches the render order exactly)
  - `diskspace:262|snapshot:snapshot-1|accessTime` (VM Snapshots List) —
    `rollUpType="NONE"`, TIMESTAMP, no extra siblings. ✓
  - **Every** non-property instanced member in the survey carries
    `rollUpType="NONE"` — the AVG→NONE change is vendor-correct, not a guess.
    (Vendor examples also carry `id`/`preferredUnitId` the factory omits — a
    pre-existing generic difference, out of scope; see NIT.)
- **rollUpType change does not alter existing content:** re-rendered **115
  views** (16 factory `content/views` + 98 `vcommunity-vsphere` + 1
  `vcommunity-os`) on `HEAD~1` vs `HEAD`. Output **byte-identical**. The
  licensing/ported views use CURRENT/plain members (→ NONE under both the old
  and new code), so the removed AVG branch was never exercised by existing
  content. (10 of 115 are pre-existing standalone SM-cross-ref load errors,
  identical on both trees — not caused by this commit.)
- **Rejection does not leak onto ordinary columns:** the guard is scoped
  `c.instanced_group is not None and not is_driver`; ordinary columns have
  `instanced_group=None`. Proven by the new test
  `test_percentile_still_allowed_on_non_instanced_column` (ordinary PERCENTILE
  column still validates) and by validate ×7 passing over the whole corpus
  (which includes non-instanced PERCENTILE/TIMESTAMP columns).
- **Test coverage:** 6 new tests — MAX→rollUpType=NONE, transformExpression
  sibling emission, TIMESTAMP no-extra-siblings, PERCENTILE rejected,
  TIME_POINT rejected, and the non-leak regression above.

### Gates re-run

- **full pytest** — 491 passed, 4 skipped, 162 deselected (matches the claim).
- **validate ×7** — PASS.
- **render regression** — 115 views byte-identical `HEAD~1`→`HEAD`.
- **path audit** — this commit touches only `src/vcfops_dashboards/loader.py`,
  `src/vcfops_dashboards/render.py`, `tests/test_view_instanced_group_columns.py`,
  `knowledge/context/wire-formats/view_column_wire_format.md`. No content YAML, no
  `.claude/`/`.github/`. Clean.

### NIT (carry-forward, no action required for this PR)

- [`_xml_instanced_group_item`] Instanced-group member columns still do not emit
  `preferredUnitId` even though the vendor `View - Set 4.xml` members carry it
  (`ViewColumn.unit` is read by the generic path but ignored here). This is a
  **pre-existing** gap in the original instanced-group implementation (not
  introduced by this commit), now **honestly documented** in the wire-format doc
  as out-of-scope and flagged for a future tooling pass — a loud, documented
  limitation, not a silent downgrade. If an author sets `unit:` on an
  instanced-group member it would be silently ignored; no current pak content
  does. Acceptable to defer.

### Stale-zip note (unchanged)

The WARNING from the original review still applies: `src/vcfops_dashboards/render.py`
is a named staleness trigger and the branch also carries the alerts symptom-XML
change, so a `content-packager` rebuild of affected bundles plus a fresh
`vcommunity-vsphere` `v*` release is required before the fix reaches instances.
This commit's render change is inert on existing content, so it adds no *new*
staleness beyond what the branch already carried.
