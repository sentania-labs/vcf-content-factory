# Framework review: M2 row 2, dashboards loader/render/reverse/packager into vcfcf_core

Date: 2026-09-14. Reviewer: framework-reviewer. Branch
`feat/m2-row2-core-dashboards` (five commits over merge-base `86f96c3`, head
`148b359`). Design: `knowledge/designs/tooling-core-carveout-v1.md` row 2.
Precedent: `m2-row1-core-scaffold-2026-09-14.md`.

Verdict: **APPROVE** (zero BLOCKING). Two WARNINGs and five NITs, all to be
fixed before the PR opens per CLAUDE.md step 9. Ownership is marked on each.

## What changed

- `git mv` of `reverse.py`, `render.py`, `packager.py`, `loader.py` into
  `src/vcfcf_core/dashboards/`; the pure half of `summary_bind.py` follows.
- Core `load_view` / `load_dashboard` / `load_all` take `on_missing_id` and
  `provenance_of` callbacks; no callback means `DashboardValidationError`
  on a missing id and provenance `""`. `src/vcfcf_dashboards/loader.py` is a
  wrapper that keeps the old signatures, `_mint_id_into_file`, and the lazy
  `vcfcf_common.provenance` import.
- `render_view_def_fragments` / `render_views_xml` take `sm_map` +
  `sm_scope_active` instead of `sm_scope`; the cwd scan moves to
  `vcfcf_supermetrics.loader.sm_id_map()`. `build_import_zip` gains `sm_map`.
- `reverse` / `render` / `packager` old paths are `sys.modules` aliases;
  `loader` and `summary_bind` are wrappers.
- `buildkit.py` copies `dashboard_loader.py` / `dashboard_render.py` from core.

## Checks re-run (independently, from the worktree)

| Check | Result |
|---|---|
| Full suite `-n auto --dist=loadgroup -m ""` | **1846 passed, 7 skipped** (43 s); main at row 1 close was 1829, so +17 as claimed |
| `tests/test_core_contract.py` + `tests/test_core_shims.py` | 77 passed on branch (60 on the main export) |
| Validate chain (supermetrics, dashboards, customgroups, symptoms, alerts, reports, managementpacks, packaging) | all clean, tree clean afterwards (no ids minted) |
| `scripts/path_reference_audit.sh` | clear (six standing RULE-015 exceptions, pre-existing) |
| Byte identity of moved modules vs main | `reverse.py` identical; `render.py`, `loader.py`, `packager.py`, `summary_bind.py` differ only by the stated signature changes and relative imports (diffed `main:src/vcfcf_dashboards/X` against `HEAD:src/vcfcf_core/dashboards/X`) |
| Bundle zips, `build --all --no-live-describe`, `PYTHONHASHSEED=0`, branch vs `git archive main` export | 12/12, 17/17, 19/19 members (nested zips walked); only `vcfops_manifest.json` differs and only in `built_at` |
| **Standalone content-import zip** (`python3 -m vcfcf_dashboards package`, the 00d3382 path) branch vs main | identical member set and bytes apart from the `<time_ns>L.v1` marker name; `views.zip/content.xml` carries 35 `Super Metric|sm_` columns and 0 literal `supermetric:` tokens on both |
| sdk buildkit (reference pak `vcfcf_sdk_compliance.1.0.0.49.pak`) branch vs main | 57/57 members; only `dashboard_loader.py`, `dashboard_render.py`, `sdk_builder.py`, `sm_loader.py` differ, as claimed |
| Kit run with the factory absent (`env -i`, cwd `/tmp`, `PYTHONPATH` = kit only) | imports `dashboard_loader`, `dashboard_render`, `sm_loader`, `sdk_builder`; no `vcfcf_*` in `sys.modules`; loads a compliance view (provenance `""`), renders it through `sm_loader.sm_id_map`; a view with no `id:` raises `DashboardValidationError` and, through `sdk_builder._load_bundled_content`, `SdkBuildError: ... missing id (a uuid4); pass on_missing_id= to mint one`; the file is untouched |
| "All six managed paks carry ids" | true: every `views/*.yaml` and `dashboards/*.yaml` under `content/sdk-adapters/{compliance,vcommunity,vcommunity-os,vcommunity-vsphere}` starts with `id:`; `synology` and `unifi` bundle none |
| Provenance through every factory path (cwd `/tmp`, not the repo) | `load_view`/`load_dashboard`/`load_all` on `content/` give `factory`; a `third_party/idps-planner` view gives `idps-planner`; `vcfcf_packaging.loader.load_bundle` views/dashboards give `factory`; `sdk_builder._load_bundled_content` on compliance gives `factory`; `vcfcf_core.dashboards.loader.load_view` direct gives `""`. Nothing in `src/` outside the wrappers, shims and buildkit imports `vcfcf_core.dashboards` directly (grep) |
| Unscoped SM map | `sm_id_map()` from the repo root: 41 entries; from `/tmp`: 0, matching the old renderer's cwd scan. A view with an SM column rendered with no map **raises** `ValueError` (render and `build_import_zip`), so a dropped `sm_map=` is loud, not a silent downgrade |
| Callers of the changed signatures | every `src/` and `tests/` call site passes `sm_map=` / `sm_scope_active=` or renders views with no SM columns; no `sm_scope=` caller remains except comments; `test_localization_key_length_cap.py` stubs now accept `**kw` |
| Kit rewrite rules | `_apply_rewrites` raises on a zero-match rule, so the removed `dashboard_render.py` SM-loader rules and the removed `dashboard_loader.py` provenance rule were required removals; the four `sm_id_map` sites in the kit's `sdk_builder.py` are rewritten to `.sm_loader` |
| Contract test vs the new modules | the static walk recurses into function bodies, so a function-local `from vcfcf_common ...` would be caught; core's remaining function-local imports are relative (`from .render import _VIEW_PIN_CONTAINER`) and correctly exempt. Callbacks are the injection seam by design and cannot be checked statically; the dynamic half proves both modules import with the factory absent. No new rule is needed for row 2 |
| Em-dashes | zero in any line the branch adds (moved-verbatim lines excluded, as in row 1) |
| `knowledge/designs/tooling-core-carveout-v1.md` shows a 7-line removal in `main..HEAD` | not a branch edit: main gained the "Release log" section (`f45d3a4`) after the merge-base; `main...HEAD` shows no design change. Merge main before opening the PR |

## Findings

### WARNING

1. **Test coverage of the new seams** (dimension 10; anchor `00d3382`
   lived on exactly the standalone import path). Three behaviours the
   branch introduced have no test: (a) `sm_id_map()`
   (`src/vcfcf_supermetrics/loader.py:229-268`): candidate order
   `content/supermetrics` then `supermetrics`, all-or-nothing swallow in
   unscoped mode, `ValueError` naming `bundle_context` in scoped mode;
   (b) the standalone path wiring, `cli.py:322,343` and
   `handler.py:111,284` passing `sm_id_map()`: no test loads a view with a
   `supermetric:"..."` column through `cmd_package` / `ViewsHandler` and
   asserts `Super Metric|sm_` in the emitted `content.xml`; (c) the kit
   delta: a bundled view or dashboard with no `id:` now fails the pak
   build (`buildkit.py:64-68`), proven by hand above but pinned nowhere.
   Not BLOCKING because a dropped `sm_map=` raises rather than rendering
   blank (proven), and `tests/test_core_shims.py:98-127` covers the
   core-vs-wrapper minting contract. Owner: tooling. Fix: one test each;
   (b) can reuse `tests/test_dashboard_import_all_skipped.py`'s handler
   harness with an SM YAML in a `content/supermetrics` under `tmp_path`
   and `monkeypatch.chdir`.

2. **The stale-zip signal now names an alias** (dimension 9; provenance
   note in the reviewer prompt: "checked the artifact but not the signal
   about the artifact"). `CLAUDE.md:314-319` and
   `.claude/agents/framework-reviewer.md:180-184` trigger the
   content-packager rebuild on `src/vcfcf_dashboards/render.py`, which is
   now a five-line `sys.modules` alias that no future renderer change will
   touch. The renderer is `src/vcfcf_core/dashboards/render.py`. As written
   the rule can never fire again for the file it was written for. Owner:
   orchestrator (both files are outside `src/` and `tests/`). Fix: name
   `src/vcfcf_core/dashboards/render.py` in both places (keep the
   packaging paths as they are; `builder.py` / `discrete_builder.py` did
   not move).

### NIT

3. **`src/vcfcf_supermetrics/loader.py:253-256`**: the scoped-mode error
   still reads `render_view_def_fragments: failed to load scoped SM for
   bundle ...`. The function that raises it is `sm_id_map`; an operator
   reading a failed bundle build is pointed at the wrong function. Owner:
   tooling. Fix: `sm_id_map: failed to load scoped SM ...`.

4. **`src/vcfcf_dashboards/loader.py:24-25, 77-82`** (row-1 W3 class).
   `from vcfcf_core.dashboards.loader import *` copies names into the
   wrapper namespace, so `monkeypatch.setattr(vcfcf_dashboards.loader,
   "stable_id", ...)` patches the copy and `vcfcf_core.dashboards.loader.
   stable_id`, which `load_view` actually calls, is untouched (proven by
   hand). No test in the tree does this today (grep), and
   `test_core_shims.py` pins identity for reads only. The docstring says
   every other name "resolves to the core module object itself", which is
   true for reads and not for writes. Owner: tooling. Fix: one docstring
   sentence ("patch `vcfcf_core.dashboards.loader`, not this module, to
   affect the running loader"), or drop `import *` and let `__getattr__`
   serve every non-wrapper name so the asymmetry is at least visible.

5. **Docs that describe current architecture by the old file path.**
   Tooling-owned (`knowledge/context/`):
   `wire-formats/view_column_wire_format.md:591,645,844,846,864,889,891,976,1018,1076,1335,1337`,
   `wire-formats/wire_formats.md:122`,
   `api-surface/widget_renderer_scope.md:18-19,659`,
   `api-surface/view_multi_subject_column_binding.md:52,55,100`,
   `authoring/view_dashboard_design_guide.md:386-387`. Orchestrator-owned:
   `.claude/agents/view-author.md:68`, `knowledge/ROADMAP.md:160`,
   `scripts/path_reference_audit.sh:70-71` (comment example), and the row 2
   line of `knowledge/designs/tooling-core-carveout-v1.md:73` (mark done
   with the PR number, as row 1 was). Dated records (`defects.md`,
   `feedback_queue.md`, lessons, `framework-reviewer-v1.md`,
   `content-migrator-plan-v1.md`) describe the tree at the time and should
   stay. `api-surface/summary_dashboard_assignment.md:320` is still
   correct (`bind_summary` stayed). Module import paths
   (`vcfcf_dashboards.reverse` in `src/vcfcf_extractor/README.md:148` and
   `.claude/commands/extract.md:145`) still resolve through the alias and
   need no change.

6. **Rebuild flag absent from the result block** (dimension 9). The
   branch touches `src/vcfcf_packaging/builder.py` and (the alias of)
   `render.py`, so CLAUDE.md's rule applies literally, yet tooling's report
   does not mention the content-packager rebuild. The zip comparison above
   proves every member byte-identical, so no rebuild and no
   `CURRENT_TEMPLATE_VERSION` bump is warranted; the PR body should say
   that in one line so the exception is taken visibly. Owner: orchestrator.

7. **`src/vcfcf_managementpacks/buildkit.py:13-20, 31-45`**: untouched
   docstring lines keep their em-dashes next to the two lines this branch
   converted to `:` (row-1 optional NIT, carried). Owner: tooling.

## Claims verified as stated

Pure `git mv` for row commit `f795b8d` (reverse identical; the other files'
edits are all in later commits and match the description); wrapper keeps
old signatures, `_mint_id_into_file`, lazy provenance import,
`__getattr__` forwarding; `sm_id_map` semantics match the removed renderer
block line for line; all callers updated (builder, discrete_builder, four
`sdk_builder` sites, packager, cli, handler); aliases vs wrappers as
described; kit copies from core with the two relative-import rewrites and
the four `sm_id_map` rewrites; 1846/7; validate clean; three bundles
identical except `built_at`; kit 57/57 with the four expected diffs;
managed paks all carry ids.

## If shipped as-is

Factory output is identical to main on every path checked, including the
standalone content-import zip where both named escapes hid. The next
renderer change would land in `src/vcfcf_core/dashboards/render.py` and the
CLAUDE.md stale-zip rule, still keyed on the alias, would not prompt the
rebuild; and a regression in `sm_id_map` or the handler wiring would fail
loudly in a build but have no test to name it first.
