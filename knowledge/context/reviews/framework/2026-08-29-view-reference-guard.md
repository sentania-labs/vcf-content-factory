# Framework review: unresolved view reference guard (2026-08-29)

Verdict: **APPROVE** (0 BLOCKING / 1 WARNING, closed by a follow-up test / 3 NIT).
Area: `src/vcfops_dashboards/render.py` (`UnresolvedViewReferenceError`),
`src/vcfops_managementpacks/sdk_builder.py` (bundled dashboard vs view
cross-validation), `src/vcfops_extractor/reverse_local.py` (PARTIAL on the new
error).

Change under review: a View widget whose `view:` is neither a loaded view nor
an anchored UUID now fails the render loudly instead of leaking the name into
`viewDefinitionId` (which the product reports as "view does not exist"). UUID
passthrough unchanged; every render entry point was walked (table in the full
report) and none silently downgrades.

Exposure judged correct, not a regression: the `vcommunity-vsphere` pak fails
the validate chain because `VM Details.yaml` references a view that ships only
in the sibling os pak (DEF-020). Recommendation: keep the chain red until that
repo is fixed.

The full report, including the live incident that motivated the change, is
held under `embargo/reviews/framework/` (not in git). Lesson:
`knowledge/lessons/dashboard-import-without-views-corrupts-refs.md`.

## Addendum 2026-08-30: delta re-review (comments and one test string only)

Delta reviewed: the fallback comment above the `UnresolvedViewReferenceError`
raise in `src/vcfops_dashboards/render.py` (~2269) was reworded to remove
incident-specific wording; one string in `tests/test_external_view_passthrough.py`.

Verified independently: `git diff HEAD` shows the guard itself unchanged
(anchored `_UUID_RE` imported from the loader, raise on a non-UUID name that is
not a loaded view, verbatim passthrough for a canonical UUID). The agreement
test still exercises upper-case, leading-space, trailing-garbage and dash-less
forms against both the loader and the renderer. `grep -rn -i` for the
embargoed lab and adapter names over `src/` and `tests/` is empty. Tests: 1315
passed, 4 pre-existing environment failures. Validate chain: managementpacks
still red on DEF-020 as expected; the other six pass. Render regression
against HEAD: clean.

Final verdict: **APPROVE** (0 BLOCKING / 0 WARNING / 0 NIT).
