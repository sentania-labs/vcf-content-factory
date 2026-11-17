# Framework review: text-only pass on `cleanup/public-tree-pass-1` (2026-11-16)

- **Gate:** RULE-013, `framework-reviewer`, one round.
- **Commits in scope:** `b5550aef`, `3fdbc042` (13 files under `src/` and `tests/`, +26/-25).
  The other branch commits are documentation only and were read as context.
- **Stated scope:** comments, docstrings and three displayed message strings; no logic
  change, no rendered-output change.
- **Verdict:** APPROVE (0 BLOCKING / 3 WARNING / 3 NIT). Every finding is text in a line
  the branch already touches, so per CLAUDE.md delegation rule 9 all of them get fixed
  before the PR opens.

## Checks re-run

| Check | Result |
|---|---|
| No other `src/`/`tests/` change on the branch | `git diff origin/main...b5550aef~1` and `3fdbc042..HEAD` on `src tests`: empty |
| AST equivalence, base vs branch, per touched file | All 13 files are AST-identical with docstrings masked. The 3 that differ beyond that (`importer/dashboards.py`, `importer/inputs.py`, `managementpacks/post_install.py`) become identical once f-string literal text is also masked: only displayed text changed |
| Runtime docstring readers | `grep __doc__ / inspect.getdoc / getsource` in `src/`: none, so docstring edits cannot reach output |
| Consumers of the 3 changed strings | `_DashMapper.loss` raises a TOOLSET GAP carrying the message; `b.problem` is only tested for truthiness and displayed (`convert.py:636,1536,1553,1565`); `post_install` `out(...)` is printed. Test assertions (`test_import_local_summary_binding.py:213`, `test_pak_summary_rebind.py:182,192,373,448,605,621`) match prefixes the change leaves untouched |
| Render regression, dashboards | `vcfcf_dashboards package` with `origin/main` `src/` against branch `src/`, same content: 12/12 members, nested zips descended, **content-identical** after UUID and timestamp normalization (head vs head shows the same per-run noise and nothing else) |
| Validate chain (7 packages) | all rc=0 |
| Test suite | 14 failed / 4906 passed / 15 skipped. The 14 are exactly the known-unrelated set: 2 `TestGapFJMESPathPredicates`, 5 `test_common_doctor`, 1 recursion test, 5 `test_release_naming_phase_v2_item1`, 1 `test_validator_phase2::…passes_on_real_repo` |
| Version-parsing inputs with "9.2" | untouched (`test_dashboard_widget_min_version.py:108`, `test_section_fallback.py:284,316,634`, `test_import_shortfall_and_widget_floor.py:329,363`, `test_sdk_compat_target.py:1123`) |
| Renamed lesson | `knowledge/lessons/pak-isunremovable-not-enforced-server-side.md` exists (R085); `git grep pak-isunremovable-vendor-bug` finds nothing tracked |
| Deleted files referenced from `src/`/`tests/`/`scripts/`/`.github/` | none. The branch's net deletions are only the two `reference/` files below |
| Distribution-zip rebuild / `CURRENT_TEMPLATE_VERSION` | not required: `render.py` changed in a comment and a docstring only, AST-identical, output identical |
| pak-compare | n/a (no builder or template change) |

## Dimensions

1, 2, 4, 6, 8: no executable change, so nothing can leak to the import path, collide a key,
mis-resolve a reference or change a pak shape. 3, 5: output identical (above). 7: corpus
validates; suite at its known baseline. 9: no stamp bump needed (no output change).
10: no behaviour to cover.

The rest of the review is dimension 3 of the brief: whether each new "9.1.1" in code is
backed by what the knowledge base records.

| Code citation | Backed by | Holds? |
|---|---|---|
| `ui_client.py:322` "2026-08-25 note … confirmed live on 9.1.1" | `summary_dashboard_assignment.md` table row "9.1.1 (devel on 2026-08-25) … answered 200 ok live"; devel was 9.1.1.0 on 2026-08-25/26 per `dashboard_widgets_alertvolume_section_viewdetails.md` and `dashboard_view_pin_resolution.md` | yes |
| `ui_client.py:374,389` two-map on 9.1.1 Build 25794169 | `summary_dashboard_assignment.md` "Two request forms" table; `2026-10-26-dashboardaction-associate-evidence.md` | yes |
| `render.py:146` NSX World live-verified on 9.1.1 | `dashboard_view_pin_resolution.md` (import on devel 9.1.1.0) | yes |
| `summary_bind.py` (both), test comments: `isDashboard: true` and two maps on 9.1.1 | `summary_dashboard_pak_binding.md` read-side paragraph; `summary_dashboard_assignment.md` `execute()` 227-258 (9.1.1) | yes |
| `widget_versions.py:24,30` Section and `view_details` proven on 9.1.1 | `summary_dashboard_pak_binding.md` "proven importing on 9.1.1"; `dashboard_section_gauge_viewdetails.md` | yes |
| `importer/dashboards.py:211`, `importer/inputs.py:359,460` GenericTemplates as template on 9.1.1 | `summary_dashboard_pak_binding.md` "Decompiled core (9.1.1)"; `importer_offline_conversion.md:136-138` | yes |
| `post_install.py:596` "the bind action deletes it on 9.1.1" | 9.1.1 evidence is bytecode only (`2026-10-26-dashboardaction-associate-evidence.md` offsets 405/432); `summary_dashboard_assignment.md` §corrected call: "from the bytecode (not yet exercised live)" | **no**, W1 |
| `loader.py:2176`, `loader.py:2247-2248` "a Suite API export on 9.1.1" | on `origin/main` the export was qa 9.2 (`reference/docs/extracted/dashboard-widgets/README.md` "from a 9.2.0.0 instance"; parity note "returned all 228 qa dashboards"). The branch doc header now says devel pulled it, which re-attributes rather than records | **no**, W2 |
| `loader.py:1792-1793` "Surveyed on 9.1.1 (15 gauge widgets …)" | the branch removed the count from `dashboard_section_gauge_viewdetails.md` because it covered the 9.1.1 / 9.2 capture set; `origin/main` code said "Surveyed on 9.2 (15 gauge widgets" | **no**, W3 |

## WARNING

**W1.** `src/vcfcf_managementpacks/post_install.py:596`, operator-facing `SUMMARY REBOUND`
message. Authority: `summary_dashboard_assignment.md` (server-side behaviour of the
corrected call "from the bytecode (not yet exercised live)") and
`2026-10-26-dashboardaction-associate-evidence.md`. The sentence now reads "(the bind
action deletes it on 9.1.1, and per the bytecode on 9.0.2 and 8.18; not seen live
there)". Set against "per the bytecode" and "not seen live there", the 9.1.1 clause reads
as a live observation. No live 9.1.1 delete is recorded: the one 9.1.1 rebind on record
(`summary_dashboard_pak_binding.md`, compliance 0.0.0.98) was `SUMMARY OK`, and no bind
was sent. An operator gets a firmer claim than the evidence supports.
**Fix:** "(per the bytecode the bind action deletes it on 9.1.1, 9.0.2 and 8.18; not
seen live)".

**W2.** `src/vcfcf_core/dashboards/loader.py:2176` and `:2247-2248`, the
`AlertVolumeConfig` and `SectionConfig` docstrings. Authority: `origin/main`
`reference/docs/extracted/dashboard-widgets/README.md` and the base parity note in
`dashboard_widgets_alertvolume_section_viewdetails.md`. Both now cite "a Suite API export
on 9.1.1". The only Suite API export behind these shapes was the deleted qa 9.2 sample.
The branch's own `dashboard_section_gauge_viewdetails.md:10-12` says the import-bundle
form "was later confirmed from the vendor templates", which is the defensible source.
**Fix:** "§1 (appliance widget + editor source on 9.1.1; export form from the vendor
dashboard templates under reference/docs/extracted/dashboard-widgets/)". Do the same at
§3. The source doc's **Method** line makes the same re-attribution. That line is out of
this gate's scope, but it should be corrected in the same PR so code and doc agree.

**W3.** `src/vcfcf_core/dashboards/loader.py:1792-1793`, the `ScoreboardConfig` gauge
recipe docstring. Authority: `dashboard_section_gauge_viewdetails.md` as changed on this
branch. "Surveyed on 9.1.1 (15 gauge widgets" keeps a count that the knowledge doc
dropped because it covered the mixed 9.1.1 / 9.2 capture set. The base code tied the 15
to 9.2. The code now asserts a 9.1.1 observation that the knowledge base does not record.
**Fix:** "Surveyed on 9.1.1 (gauge widgets in ``getWidgetConfigs`` captures, 2026-08-25;
see …)", without the count.

## NIT

**N1.** `src/vcfcf_core/dashboards/loader.py:1699-1701`, the Scoreboard bound semantics.
Authority: lesson `scoreboard-partial-bounds-render-unknown.md`. "on a lab instance" is
accurate, but the lesson and the gauge doc on this branch both say the partial-set
`"?"` answer still needs re-verification on a released version. The docstring states it
as settled. **Fix:** add "(not yet re-verified on a released version)".

**N2.** `src/vcfcf_managementpacks/installer.py:431`. The renamed path is correct, but the
sentence says the lesson enumerates the surface that includes
`getLatestInstalledSolutionStatuses`. Neither the old lesson nor the new one mentions
that action; they list `remove` / `enable` / `cancel` / `resetSolutionUninstallState` /
`finishStage`. The imprecision predates this branch, but the branch touches this line.
**Fix:** "per the `/ui/solution.action` mainAction surface (see knowledge/lessons/…
for the uninstall-side actions)", or drop the claim that the lesson lists this action.

**N3.** This item is in a context doc, not code. `knowledge/context/wire-formats/dashboard_view_pin_resolution.md:17`
still says the resource is displayed as `NSX World` "on both devel and qa", while line 5
of the same doc dropped the qa (9.2.0.0) cross-check. It is a residual pre-release
reference that this pass meant to remove. **Fix:** "on devel".

## Immutability guard (for the PR)

`scripts/immutability_guard.sh --range origin/main...HEAD` (the CI form,
`.github/workflows/ci.yml:168`) exits 2, REFUSED, on exactly three paths:

- `D reference/docs/extracted/brockpeterson-vm-snapshots-aria-operations/article.txt`
- `M reference/docs/extracted/dashboard-widgets/README.md`
- `D reference/docs/extracted/dashboard-widgets/qa-9.2.0-export-alertvolume-section-viewdetails.json`

Nothing else under `reference/` changed. The earlier clean-room tree removals were
restored later on the branch, and `git diff --name-status origin/main...HEAD -- reference/`
lists only these three. That CI job will be red on this PR until a RULE-010 exception is
decided.

## If shipped as-is

No behaviour or output change for any user or pak. One operator-facing line (W1) would
claim a 9.1.1 live observation that does not exist, and three docstrings would cite
evidence that is not in the repo.
