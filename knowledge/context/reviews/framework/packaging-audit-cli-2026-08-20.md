# Framework review: packaging audit/CLI batch (issues #69/#80, #71-#77, #78 src-side), 2026-08-20

Reviewer: framework-reviewer (pre-PR gate, blanket scope).
Diff under review: uncommitted working tree, `src/vcfops_packaging/` (23 files) + `src/vcfops_dashboards/` (7 files).
Out of scope (per brief): non-src working-tree changes (agent prompts, content YAML sweep, scripts).

## Verdict: CHANGES REQUESTED (1 BLOCKING / 4 WARNING / 3 NIT)

## Checks re-run (independently, not taken from tooling's report)

- Validate chain (all 7 packages): PASS.
- pytest tests/: 646 passed, 4 skipped, 178 deselected (matches tooling's claim).
- Render regression: clean. The entire `src/vcfops_dashboards/` diff was proven
  punctuation-only by token-normalized comparison of every +/- line (zero
  non-punctuation deltas); renderer regression tests (test_renderer_regression_phase16,
  emit-fidelity suite) green.
- Issue #69/#80: `build bundles/releases/synology-diskstation-managementpack.yaml`
  rc=0, loud `pointer ...` line, no crash. Print-only (no dist file) matches the
  publish.py pointer contract (publish.py:1189-1196 writes no file either), so this
  is not a silent skip.
- Issue #71: rebuilt vm-snapshot-inventory-dashboard.zip offline; `analyze` on the
  staged bundle dir now reports 10 refs / 2 needs-enable, identical to the build
  audit (was 2 vs 10 per the issue). `_refs_from_views_xml` run directly on the
  emitted views_content.xml returns all 10 keys including the subject-filter key
  `diskspace|snapshot|numberOfDays` (issue #72) and skips the `Instance Name`
  sentinel. Shape matches knowledge/context/wire-formats/view_column_wire_format.md
  (SubjectType adapterKind/resourceKind/filter; attributeInfos Item/Value/Property
  name="attributeKey").
- Issue #74: `build <release>.yaml --no-live-describe` left
  knowledge/context/adapter_describe_cache/ untouched (git-status diff before/after
  identical); `--strict-deps` on the release path now runs the audit in mode=strict
  (observed) instead of silently downgrading to auto.
- Issue #75: simulated a stub client with (a) /properties raising and (b) /properties
  returning 500, against a pre-seeded cache file: both paths preserve the existing
  `properties` section while refreshing metrics. Fix direction met.
- Issue #73: strict discrete build of the non-headline view now fails with the new
  discrete-build remedy text (release-manifest guidance, not the nonexistent bundle
  manifest); the synthetic-vs-real discrimination via `Bundle.source_path`
  (loader.py:192, set at loader.py:431, None at discrete_builder.py:242) is correct.
  Swallowed ReleaseValidationError now warns to stderr (verified with a malformed
  manifest fixture).
- Issue #77 dedupe parity: `run_dependency_audit` preserves both call sites'
  behavior (same skip-audit warning, same live-refresh loop, same auto-add merge,
  AuditError propagates; both callers still print the summary guarded for None).
  `parse_builtin_metric_enables` raises the caller-supplied exception class
  (ReleaseValidationError in releases.py, BundleValidationError in loader.py);
  test_release_builtin_metric_enables_schema green.
- Issue #78 src-side: every remaining packaging file (composer, defects, handler,
  project, syncer, managed_paks, release_types, publish) proven punctuation-only by
  the same token-normalized comparison. Only "—" left in src is the three declared
  readme_gen.py table-cell placeholders (lines 656, 792, 857).
- pak-compare: n/a (no MP/pak builder emission changes in this diff).

## BLOCKING

- B1 [src/vcfops_packaging/release_builder.py:194-198 with releases.py:302-323]
  Issue #76 acceptance + CLAUDE.md "Never silently downgrade": the cwd half of
  issue #76 is NOT fixed, and the new docstring claims it is. The `_REPO_ROOT`
  default only changes `repo_root` (used inside `load_release` for source-path
  resolution). The directory scan itself, `load_all_releases(releases_dir, ...)`
  with default `"bundles/releases"`, still resolves `releases_dir` against
  `Path.cwd()` (releases.py:321 `releases_dir = Path(releases_dir)`), and a
  missing directory returns `[]` without raising, so the new
  ReleaseValidationError warning never fires either.
  Verified: calling `find_builtin_metric_enables_for_discrete_item('dashboard',
  '[VCF Content Factory] VM Snapshot Inventory')` from cwd=/tmp returns `[]`
  silently; from the repo root it returns the 2 curated enables
  (diskspace|snapshot|creator / description). Exactly the silent enable-drop the
  issue describes: strict builds fail on already-declared metrics, auto builds
  lose the curated reason text. The docstring ("NOT Path.cwd(), which would
  silently drop declared enables when invoked from outside the repo root") is now
  false documentation on the exact escape.
  Smallest fix: in the helper (or in `load_all_releases`), anchor a relative
  `releases_dir` to `repo_root` (`releases_dir = Path(releases_dir);
  if not releases_dir.is_absolute(): releases_dir = repo_root / releases_dir`),
  and emit the same stderr warning when the resolved directory does not exist.

## WARNING

- W1 [src/vcfops_packaging/describe.py:329-345] Issue #75 / brief requirement
  "must not mask genuine fetch errors": the /properties failure path is entirely
  silent. Both the raised exception and the non-200 are swallowed with no message,
  and the success line "refreshed describe cache: ... (N property keys)" then
  presents preserved stale properties as freshly fetched. Data integrity is now
  protected (the point of #75), but the operator cannot tell a refresh half-failed.
  Fix: one stderr WARN naming the adapter/resource pair and the failure, matching
  the WARN convention this same diff adds in release_builder.py.
- W2 [whole diff, no tests/ changes] Review dimension 10: zero new or extended
  tests for any changed behavior: the `_refs_from_views_xml` rewrite (the
  "silently-dodges-the-gate" class named in issue #71), `run_dependency_audit`,
  `parse_builtin_metric_enables`, the SDK-pointer CLI branch, the describe
  properties-preservation path, and the flag threading of #74. My verification
  above is one-shot; nothing pins these against the next drift. Minimum: a fixture
  test asserting the 10-ref parse of a committed factory views_content.xml, and a
  unit test for the describe preservation path.
- W3 [src/vcfops_packaging/templates/*, template_version.py:6-14, builder.py README
  text] Stale-zip discipline (CLAUDE.md "After tooling changes") + issue #78's own
  "then repackaging affected zips": templates/install.py, install.ps1, and
  README_framework.md changed (shipped, user-visible text) but
  CURRENT_TEMPLATE_VERSION was not bumped, violating template_version.py's own
  stated contract, so `check-staleness` will report old zips as current. All dist
  zips are stale; the change must flag a `content-packager` rebuild and bump the
  template version.
- W4 [src/vcfops_packaging/readme_gen.py:656,792,857] Scott's global rule 7 ("No
  em-dashes. Anywhere. ... generated docs"): the three kept "—" literals render
  into the published distribution README table cells, which are generated docs.
  Tooling declared them deliberate; the rule's wording does not carve them out.
  Trivial fix ("-" or "n/a"), or get an explicit waiver from Scott recorded in the
  PR.

## NIT

- N1 [src/vcfops_packaging/cli.py:371-374 + audit.py analyze path] Pre-existing,
  not introduced here: `analyze <zip-file>` (or any dir without content/) exits 0
  with "no metric references found", the same gate-dodging class as #71. Suggest a
  follow-up issue: hard-error when `bundle_dir/content` is absent.
- N2 [src/vcfops_packaging/audit.py:461] `viewdef.get("name")` is always absent in
  factory XML (title lives in the `<Title>` child), so every ref's source_desc is
  "view 'unknown view'" (visible in analyze's auto-detected reasons). Read the
  Title child.
- N3 [src/vcfops_packaging/deps.py:283-289 area, src/vcfops_dashboards/render.py]
  Sweep artifacts: several continuation lines now begin with ", " at column 0
  (e.g. deps.py `_refs_from_widgets` docstring, render.py ", see
  _cap_localization_key"). Cosmetic only.

## If shipped as-is

An operator running build-discrete from any directory other than the repo root
still silently loses curated builtin_metric_enables (strict builds fail on
already-declared metrics; auto builds ship auto-generated reasons), the exact
defect issue #76 records as fixed, now with a docstring asserting it cannot
happen. Everything else in the batch independently verifies.

---

# Round 2 (same day): re-review after tooling addressed round 1

## Verdict: APPROVE (0 BLOCKING / 0 WARNING / 2 NIT)

## Checks re-run (round 2, independently)

- Validate chain (all 7 packages): PASS.
- pytest tests/: 656 passed, 4 skipped, 178 deselected (matches tooling's claim;
  +10 from the new test file).
- B1 closed and proven: `find_builtin_metric_enables_for_discrete_item` now
  anchors a relative releases_dir to repo_root (is_absolute() check,
  release_builder.py) and WARNs when the resolved dir is missing. Verified from
  cwd=/tmp: returns the 2 curated VM Snapshot Inventory enables (was silent []);
  a bogus releases_dir produces the loud missing-dir WARNING and []. Docstring
  now correctly documents load_all_releases's cwd/[] behavior.
- W1 closed: both /properties failure paths (exception and non-200) emit a
  stderr WARN naming the pair, the failure, and the preserved-from-cache nature
  of the property count. Covered by capsys assertions in the new tests.
- W2 closed, and the tests are not tautologies: the fixture
  tests/fixtures/vm_snapshot_inventory_views_content.xml was verified
  byte-identical to the views_content.xml the packaging builder actually emitted
  in my round-1 rebuild (independent diff, modulo nothing: same bytes). The 10
  tests pin: 10-ref count, every specific key, the duplicate subject-filter
  occurrence count (2x numberOfDays, parser must not dedupe), Instance Name
  sentinel exclusion, Title-based source_desc, and describe preservation with
  both failure paths plus a 200-success control and a no-prior-cache control.
- W3 closed: CURRENT_TEMPLATE_VERSION bumped to 2026-08-20-1 in
  template_version.py (the single source check-staleness and both builders
  read). Rebuild of all dist zips by content-packager remains an orchestrator
  action before anything ships.
- W4 closed: the three readme_gen.py placeholders are now "-"; grep confirms
  zero em-dashes across src/vcfops_packaging/ and src/vcfops_dashboards/.
- N2 closed (parser reads <Title> child with name-attr fallback, test-pinned);
  N3 closed (no column-0 ", " artifacts remain); N1 deferred to issue #85 as
  agreed.

## Remaining NITs (non-blocking, no action required before PR)

- N4 [src/vcfops_packaging/templates/install.py:55] The in-template
  `TEMPLATE_VERSION = "2026-04-18-1"` literal was not bumped and its comment
  ("injected at build time by vcfops_packaging builder") is inaccurate: the
  template is copied verbatim (builder.py:622,736) and the authoritative stamp
  is vcfops_manifest.json's template_version from CURRENT_TEMPLATE_VERSION,
  which is what check-staleness reads (cli.py:497-540). Harmless today; either
  drop the unused constant or fix the comment on a future pass.
- N1 (carried, filed as #85): analyze exits 0 with "no metric references found"
  when pointed at a zip file or a dir without content/.

## If shipped as-is

All eight verified issue fixes land intact; the only operator-facing follow-up
is the already-flagged content-packager full rebuild (all dist zips are stale
against template version 2026-08-20-1 and the swept README/installer text).
