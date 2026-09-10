# Framework review: reject `subject:` on pseudo-columns (PR #150, commit 6c9eb6f)

Verdict: **APPROVE** (0 BLOCKING / 1 WARNING / 2 NIT).

Reviewer: framework-reviewer. Date: 2026-09-10. Branch
`pr/multi-subject-view-columns`, commit `6c9eb6fdb9789e5dbbdc3087ceb9296d269a508f`,
reviewed in the context of the whole PR (`origin/main...HEAD`). The two earlier
PR commits were reviewed in `2026-08-29-multi-subject-column-binding.md` and
`2026-08-29-view-reference-guard.md` (both APPROVE); this report covers only the
Codex P2 follow-up.

## Change under review

`ViewDef.validate()` (`src/vcfops_dashboards/loader.py:561-586`) now raises
`DashboardValidationError` when a column sets `subject:` and is either a
`time_segment` column or an `instanced_group` driver column. Rationale: the
renderer emits neither `adapterKind` nor `resourceKind` on those two Items
(`render.py::_xml_time_segment_item` emits the fixed nine vendor Properties;
`_xml_instanced_group_item` returns the driver Item at `render.py:497` before
reaching `_xml_kind_binding_props`), so a `subject:` there was accepted and
silently dropped. Three tests added to
`tests/test_view_multi_subject_column_binding.py::TestLoaderRejects`. The
previously-missing `knowledge/context/api-surface/view_multi_subject_column_binding.md`
(cited by six src/tests files) was written and indexed in
`knowledge/context/README.md`.

## Checks re-run (independently, /usr/bin/python3, PYTHONPATH=src)

| Check | Result |
|---|---|
| `pytest tests/test_view_multi_subject_column_binding.py` | 25 passed |
| Full suite `pytest tests` | 1416 passed, 6 failed, 13 skipped. All 6 failures are `test_release_naming_phase_v2_item1.py` / `test_validator_phase2.py` real-repo packaging tests that fail on `bundles/releases/synology-diskstation-managementpack.yaml` -> `content/sdk-adapters/synology/adapter.yaml` not found. The sdk-adapter clones are gitignored and absent in this worktree; environmental, not this change. |
| Seven-package validate chain (supermetrics, dashboards, customgroups, symptoms, alerts, reports, managementpacks) | all rc=0 |
| `vcfops_packaging validate` | rc=1, every error is the absent `content/sdk-adapters/` clone; no other error |
| `bash scripts/path_reference_audit.sh` | clear (rc=0; two pre-existing RULE-015 standing-exception warnings) |
| Render regression | n/a for emitted bytes: the commit touches only `loader.py` validation; no renderer, template, or builder file changed. Ad hoc render of the inert paths (below) matches the documented shape. |
| pak-compare | n/a (no builder change) |

### Ad hoc behavior probe (loader + `render_views_xml`)

| Case | Result |
|---|---|
| Multi-subject, driver without `subject:` + member with `subject:` | loads; driver Item unbound, member Item carries `adapterKind`/`resourceKind` |
| Multi-subject, ordinary column with `subject:` + one without | loads; bound / unbound as documented |
| Multi-subject, driver with `subject:` | rejected with the new driver message |
| Multi-subject, time_segment with `subject:` | rejected with the new time_segment message |
| Multi-subject, time_segment without `subject:` | loads; unchanged nine-Property Item |
| Single scalar `subject:` view, driver with `subject:` | rejected with the driver message (kind check precedes the "no subjects: list" check, as intended) |
| Single scalar `subject:` view, ordinary column with `subject:` | rejected: "declares no subjects: list" (pre-existing) |
| **One-entry `subjects:` list, ordinary column with `subject:`** | **accepted and bound** (see WARNING) |

### Vendor ground truth

The new doc claims no vendor driver or time-segment Item carries a kind. The
worktree has no `reference/references/` clone, so I scanned the main checkout's
copy read-only (116 XML files under `reference/references/` and
`reference/docs/extracted/`): 24 instanced-group driver Items, 0 with
`adapterKind`; 1 `isTimeSegment` Item, 0 with `adapterKind`. Claim verified.

## Dimension walk

1. **Global/pak leak (00d3382)**: none. The change is a validate-time rejection; it emits no bytes and is path-independent (content-import zip, pak, report XML all go through the same `ViewDef.validate()`).
2. **Key/label collision (6c59f6b)**: n/a; no key derivation touched.
3. **Wire-format conformance**: no emission change. Rejecting rather than inventing a kind slot on the driver / time-segment Item is consistent with `knowledge/context/wire-formats/view_column_wire_format.md` §multi-subject (line 1258 ff.) and the vendor scan above.
4. **Loader/validator correctness**: the check runs after the `attribute`/`display_name` presence check (time_segment columns get `Interval Breakdown` synthesized at load) and before the `not self.subjects` check, so the error names the real problem. `is_driver` is `not prefix and not suffix`; half-set members are handled by the pre-existing `_validate_column` path, unchanged.
5. **Render regression vs known-good**: `content/views/vm_snapshot_inventory.yaml` is the only corpus view with instanced-group columns; its `subject:` is view-level, not per-column; dashboards validate passes. No corpus view newly fails.
6. **Builder/pak structure**: untouched.
7. **Corpus regression**: chain green; suite green apart from the environmental six.
8. **Silent downgrade**: this commit removes one (the dropped binding) and replaces it with a loud error. No capability removed: members and ordinary columns still bind (probe cases A, B).
9. **Stale-zip / version stamp**: `loader.py` is not in the CLAUDE.md stale list and changes no emitted bytes; no bump needed for this commit. The PR's earlier `render.py` change already bumped `CURRENT_TEMPLATE_VERSION` to `2026-08-29-1` (covered by the 2026-08-29 review).
10. **Test coverage**: three new rejection tests; the inert side (member still bound, ordinary bound, one-entry list byte-identical) was already covered at lines 186, 317, 324 of the same file.
11. **Reverse/extractor paths**: `reverse.py:458`, `reverse_local.py:338`, `extractor.py:750` all return the time_segment column before the `adapterKind` binding block, and none of the three reconstructs `instanced_group` at all (a driver Item reverses as an ordinary `attribute: "Instance Name"` column, pre-existing lossiness, DEF-019 territory). So no reverse path can emit YAML the new check rejects.

## Findings

### WARNING

- [`knowledge/context/api-surface/view_multi_subject_column_binding.md`, table "View shape / Column with `subject:`"] RULE-001/002 (source of truth, no fabrication) vs `loader.py:587` and `render.py:625`. The row says a single-subject view declared as a **one-entry `subjects:` list** gives "Loader error: `declares no subjects: list`". It does not: `self.subjects` is truthy, the membership check passes, and the renderer binds the column to the view's one kind (probe case F, byte-identical to the unbound output, so harmless). Only the scalar `subject:` shape raises. -> Split the row: scalar `subject:` = loader error; one-entry `subjects:` = accepted, bound to that kind, output unchanged. Doc-only; no code change.

### NIT

- [`knowledge/context/api-surface/view_multi_subject_column_binding.md` §Related defects, DEF-020] states the defect "keeps the managementpacks validate step red until the content is fixed". `vcfops_managementpacks validate` is green in this worktree because the `vcommunity` pak lives in the absent, gitignored `content/sdk-adapters/vcommunity/` clone. Could not verify the claim here; if it holds only with the clone present, say so in the sentence so a reader with a green step does not think DEF-020 is closed.
- [`knowledge/context/api-surface/view_multi_subject_column_binding.md` "What the platform does"] the survey figures (26 views, 59 of 68 columns) rest on embargoed evidence and are unverifiable from the repo; the doc says so, which is the right call, but a reader should treat the numbers as reported, not reproducible (RULE-015 spirit).

## Limits of this review

- `content/sdk-adapters/` and `reference/references/` clones are absent from the worktree. Vendor XML was scanned read-only from the main checkout; the sdk-adapter-dependent packaging tests and the DEF-020 claim could not be exercised here.
- No live-instance check (by mandate).

## If shipped as-is

Authors who put `subject:` on an Interval Breakdown or Instance Name column get a validate-time error naming the view, column and kind instead of a view that imports fine and quietly ignores the binding. Existing content, bundles and reverse output are unaffected. The doc table's one-entry-list row would mislead an author into expecting an error that never comes.
