# Framework review: multi-subject view column binding (2026-08-29)

Verdict: **APPROVE** (first pass 0 BLOCKING / 2 WARNING / 2 NIT; re-review of
the follow-up delta 0 / 0 / 1). Area: `src/vcfops_dashboards/{loader,render,reverse}`,
`src/vcfops_extractor/{extractor,reverse_local}`, `src/vcfops_packaging/{deps,template_version}`.

Change under review: multi-subject views no longer bind every column to
`subjects[0]`; columns are unbound by default (the product treats a column's
adapterKind/resourceKind as a kind filter), optionally bound via per-column
`subject:`; reverse paths mirror it; bundle audit honours bound columns;
template version bumped to 2026-08-29-1.

Checks re-run by the reviewer: validate chain 7/7; tests 1309 pass (4
pre-existing environment failures); render regression against a detached HEAD
worktree, single-subject views byte-identical; deps audit output identical for
the existing corpus.

The full report, with the live evidence (lab instance, adapter and view names,
verbatim vendor ViewDefs), is product-bound and held under
`embargo/reviews/framework/` (not in git). The generic contract is documented
in `knowledge/context/wire-formats/view_column_wire_format.md`.

## Addendum 2026-08-30: delta re-review (comments and test fixture only)

Delta reviewed: comment and docstring rewording in `src/vcfops_dashboards/loader.py`
(ViewDef.subjects comment, ~466) and `src/vcfops_dashboards/render.py`
(`_column_kind_binding` docstring, ~616; View-widget fallback comment, ~2269);
`tests/test_view_multi_subject_column_binding.py` now reads a synthetic,
public-kinds-only fixture at `tests/fixtures/multi_subject_viewdef.xml` instead
of an embargoed extract.

Verified independently:

- `git diff HEAD` on both source files: every executable hunk is the one
  already reviewed above (`_column_kind_binding`, `_xml_kind_binding_props`,
  the loader `subject:` parsing and validation, the `_UUID_RE` render guard).
  Only comment and docstring text differs from the reviewed state; no
  code-path change.
- Fixture shape: two descendant/self SubjectType pairs; the shared column has
  no adapterKind/resourceKind and `isStringAttribute` is immediately followed
  by `rollUpType`; the kind-specific column binds to the second subject, not
  the first. That is the full contract in
  `knowledge/context/wire-formats/view_column_wire_format.md`, and the fixture
  sanity test asserts each of those three properties explicitly.
- Assertions are as strong as before: unbound default on both the generic and
  instanced-group paths, per-column binding to a non-first subject, loader
  rejection of unknown and malformed subjects, single-subject byte-identity
  (scalar `subject:` vs one-entry `subjects:`), and reverse round-trip through
  both YAML writers.
- `grep -rn -i` for the embargoed lab and adapter names over `src/` and
  `tests/`: empty.
- Tests: 1315 passed, 16 skipped, 4 failed (the same pre-existing
  `test_common_doctor` environment failures as the first pass).
- Validate chain: 6/7 pass; managementpacks fails on the known DEF-020
  sibling-pak view reference, unrelated to this delta.
- Render regression against a detached HEAD worktree: 31 tracked views
  byte-identical, unchanged from the first pass.

NIT: `tests/test_external_view_passthrough.py`, the
`("Some External View Name", False),` case line carries trailing whitespace.

Final verdict: **APPROVE** (0 BLOCKING / 0 WARNING / 1 NIT).
