# Framework Review — sdk_builder SM/symptom/alert content emit (RULE-013)

**Reviewer:** framework-reviewer (read-only, pre-PR gate)
**Date:** 2026-06-16
**Branch:** chore/doc-hygiene (uncommitted working tree)
**Change under review:** `vcfops_managementpacks/sdk_builder.py` (+358 lines) +
new test `tests/managementpacks/test_sdk_content_emit.py` (20 tests) +
`tests/managementpacks/test_bundled_content_resolver.py` (updated for 5-tuple)
**Predecessor review (same working tree):**
`knowledge/context/reviews/framework/sdk-builder-content-files.md` — APPROVE, content/files
SolutionConfig fix. This diff stacks the SM/symptom/alert emit on top of it.

## What tooling changed

Three new SDK-pak content-emit paths to unblock the vCommunity Phase-2 content port:

1. `_load_bundled_content()` return type changed from `(views, dashboards)`
   2-tuple → `(views, dashboards, supermetrics, symptoms, alerts)` 5-tuple;
   added loaders for `bundled_content.supermetrics/.symptoms/.alerts` (all use
   `enforce_framework_prefix=False`, consistent with views/dashboards).
2. `_write_outer_pak()` new params `supermetrics/symptoms/alerts`; emits
   `content/supermetrics/<name>.json` (bare-UUID top-level key),
   `content/symptomdefs/<name>.xml`, `content/alertdefs/<name>.xml`; derives
   `_sm_scope` and passes it to every `render_views_xml()` call so
   `supermetric:"<name>"` view columns resolve at build time; an
   alert→symptom xref guard raises `SdkBuildError` before the zip opens.
3. `build_sdk_pak()` and `validate_sdk_project()` unpack the 5-tuple.

## Verdict: APPROVE — 0 BLOCKING

Every load-bearing claim was independently reproduced. The two regression
anchors are clean: no global-default/pak-specific leak (emit is gated to
populated subdirs only; empty adapter ships zero `content/` entries), no
key/label collision (SM JSON key and view attributeKey both derive from the
same `sm.id`). The prior content/files SolutionConfig fix still holds. Two
non-blocking findings below.

## Checks re-run (independently)

- **validate chain:** PASS — all 7 validators rc=0; `mp validate` reports
  `OK: 4 Tier 2 SDK adapter project(s) valid`.
- **managementpacks suite:** 81 passed, 4 skipped, 0 failed. (99 warnings are
  pre-existing Synology key-drift + time_window advisories — unrelated.)
- **new test file:** `test_sdk_content_emit.py` 20 passed.
- **resolver 5-tuple test:** `test_bundled_content_resolver.py` 7 passed
  (uses arity-safe `views, dashboards, *_ =`).
- **render-regression / build path:** synthetic full build (SM + view +
  symptom + alert + 6-file content/files/solutionconfig tree) via
  `_write_outer_pak`, `unzip -l` confirmed:
  - all 6 `content/files/solutionconfig/*.xml` present (claim 1 intact);
  - SM JSON top-level key `aaaabbbb-…` == view XML `Super Metric|sm_aaaabbbb-…`
    uuid — **match by construction** (claim 3);
  - empty adapter → **zero** `content/` entries (no empty-dir leak, claim 5);
  - files-only adapter → `content/files/` present, **no** spurious
    `content/supermetrics/` (populated-only discipline preserved, claim 5).
  - dangling view→SM ref (SM not in `bundled_content.supermetrics`) →
    `ValueError` from scoped renderer, build fails loudly (claim 3).
  - alert referencing a symptom absent from `bundled_content.symptoms` →
    `SdkBuildError`, **pak file does not exist** (guard fires before
    `zipfile.ZipFile` opens — no partial pak, claim 4).
- **pak-compare:** n/a (no committed reference for an SM/symptom/alert-bearing
  SDK pak yet; vCommunity has not declared `bundled_content` in adapter.yaml).

## Claim-by-claim verification

1. **content/files silent-drop fix not weakened — CONFIRMED.** All 6
   solutionconfig files package. The safety assertion (`_files_written_count
   == 0` while `content/files/` non-empty in-tree → `SdkBuildError`) still
   guards the real silent-drop class (wrong-root walk / `is_dir()` miss /
   dirs-only rglob). The new SM/symptom/alert blocks correctly feed
   `has_bundled_content`, so the `content/` root dir entry is written exactly
   once (the `_content_root_written = has_bundled_content` guard).

2. **2-tuple→5-tuple breaking contract — CONFIRMED SAFE.** Tree-wide sweep:
   both executable call sites (`sdk_builder.py:2602`, `:2828`) unpack the
   5-tuple; tests use `*_`. No latent 2-tuple unpack survives. See WARNING-1
   for the buildkit regex caveat (pre-existing, not a regression).

3. **sm_map / sm_scope resolution — CONFIRMED deterministic.** `render_views_xml`
   scoped mode builds `sm_map[sm.name] = sm.id` from the bundled SM YAML and
   emits `Super Metric|sm_{sm.id}`; the JSON file is keyed by the SAME `sm.id`
   (a bare uuid4, matching the known-good reference key format —
   `reference/references/brockpeterson_operations_supermetrics/*.json` are bare-UUID
   keyed). An unresolved ref raises `ValueError` rather than emitting a
   dangling key. No "installs clean, no data" path.

4. **Alert→symptom xref guard — CONFIRMED.** Raises before the zip opens (no
   partial pak). ID consistency is by construction: within the single
   `render_alert_content_xml(symptoms=referenced_syms, alerts=[alert])` call,
   both the SymptomDefinition `id=` (`_render_symptom_definition`, uses
   `sym.adapter_kind`) and the SymptomSet `ref=` (`_render_alert_definition`,
   resolves via the symptom object's own `adapter_kind`) use the same
   `_symptom_id(sym.adapter_kind, name)`. The guard's name-based membership
   check is correct; its `expected_id` (using `alert.adapter_kind`) is for the
   error message only and does not affect pass/fail.

5. **Global-default-leak / key-collision in new loops — CONFIRMED SAFE.**
   Populated-only emit verified in the build above. Filename-collision risk
   (two SMs/symptoms sanitizing to the same `safe_name`) exists in theory —
   see NIT-1 — but is not a wire-format defect.

## WARNING

- [`vcfops_managementpacks/buildkit.py`:134-142] — buildkit hygiene, not a
  regression of THIS diff. The two `_IMPORT_REWRITES["sdk_builder.py"]` regex
  rules that rewrite `_repo_root = _HERE.parent\n bundled_views, ... =
  _load_bundled_content(` are dead: `_repo_root` no longer appears anywhere in
  `sdk_builder.py` (it was removed before this change — both call sites now
  pass `project_dir, project_dir` directly). `re.sub` on a non-matching
  pattern is a silent no-op, so the kit copy of `sdk_builder.py` still
  functions (the 5-tuple unpack is internal to the file). But these rules are
  now doubly stale (wrong variable name AND wrong arity) and give a false
  impression that buildkit tracks the bundled-content call shape. There is no
  assertion that any rewrite rule actually matched. → Recommend tooling either
  delete the two dead rules or add a "rewrite applied" assertion in
  `_apply_rewrites`, in a follow-up. Not blocking this PR.

## NIT

- [`sdk_builder.py`:~1551, ~1660, ~1709] — `safe_name` derivation for SM JSON,
  symptomdef XML, and alertdef XML filenames does not dedupe. Two SMs (or two
  symptoms) whose display names sanitize to the same `safe_name` would have
  the second silently overwrite the first in the zip. Low likelihood (display
  names are normally distinct), filename-only (the UUID/ID payloads are still
  correct), and the platform keys on payload UUID/ID not filename — so not a
  wire defect. A `seen`-set suffix (`<name>-2.json`) would close it.

- [`sdk_builder.py`:~1561] — the SM JSON omits `modificationTime`/`modifiedBy`
  (correctly — server-side fields). Worth a one-line code comment that these
  are intentionally absent and the importer tolerates their absence (the
  reference files include them; confirm tolerance held on first live import).

## If shipped as-is

An operator porting vCommunity's Phase-2 content (or any SDK adapter declaring
`bundled_content.supermetrics/.symptoms/.alerts`) gets a pak that installs SMs,
symptoms, alerts, and SM-referencing views with cross-references intact and
resolved at build time; an authoring mistake (view→missing-SM or
alert→missing-symptom) fails the build loudly instead of shipping a dead
reference. No regression to the content/files SolutionConfig packaging. The
only latent risk is a same-sanitized-filename collision (NIT-1), which is
improbable and payload-safe.
