# Framework Review — FB-009 residual stale-citation fix (packager.py)

- **Branch/commit:** `chore/fb-009-stale-citations` @ `91596dc`
- **Base:** `main` @ `2341d12`
- **Area:** `src/vcfops_dashboards/packager.py` (module docstring)
- **Reviewer:** framework-reviewer (pre-PR, factory-owned regression gate)
- **Date:** 2026-07-16
- **Verdict:** APPROVE (0 BLOCKING)

## Change under review

Single-line docstring citation update in the `packager.py` module
docstring: the stale reference
`memory/vcfops_content_import_wire_format.md` →
`knowledge/context/wire-formats/wire_formats.md` (FB-009 item 1).
Tooling reports citation-only, zero behavior change.

## Independent verification

1. **Diff is docstring-only.** `git diff main..HEAD` shows exactly one
   hunk, one changed line, inside the module docstring (packager.py
   lines 1–28). No code tokens, imports, signatures, or string literals
   used at runtime were touched. Confirmed.

2. **New citation path exists and is on-target.**
   `knowledge/context/wire-formats/wire_formats.md` exists (25.9 KB).
   It documents precisely the content-import wire format the docstring
   points readers at: `POST /api/content/operations/import`, multipart
   field `contentFile`, the marker filename, `configuration.json`,
   `usermappings.json`, and the owner-keyed `dashboards/<ownerUserId>`
   grouping — matching the layout the packager docstring itself
   describes. Strong, correct target.

3. **Old path is genuinely dead.** `memory/vcfops_content_import_wire_format.md`
   no longer exists on disk — the citation was truly stale, so the fix
   is warranted, not cosmetic churn.

4. **No residual stale refs.** `grep -rn "vcfops_content_import_wire_format"
   src/` and `grep -rn "memory/.*wire" src/` both return nothing — the
   sweep of this citation across `src/` is complete.

5. **Extractor item-2 claim confirmed.** `src/vcfops_extractor/extractor.py`
   lines ~2044–2051: the dead citation
   `context/feedback_packaging_dependency_audit.md` is already explicitly
   self-annotated in-comment as "no longer exists in the corpus and no
   direct successor was found during the reorg-v2 phase 2 citation sweep
   — the principle itself is preserved here verbatim." It is a
   deliberately-preserved-principle-with-dead-source annotation, not an
   unmarked stale pointer. Tooling's claim that it needs no change is
   correct.

## Re-run results

- **validate chain:** all 7 CLIs + Tier 2 SDK projects — `VALIDATE_EXIT=0`, clean.
- **pytest:** 574 passed, 4 skipped, 162 deselected, 0 failed (matches
  tooling's reported 574/4/0 exactly).
- **render-regression:** n/a — no renderer/builder/loader code touched.
- **pak-compare:** n/a — no builder/template/pak-structure change.

## Dimension walk

| Dimension | Result |
|---|---|
| 1. Global-default / pak-specific leak (00d3382) | n/a — no code changed |
| 2. Key / label derivation collision (6c59f6b) | n/a — no code changed |
| 3. Wire-format conformance | improved — docstring now cites the correct, existing wire doc |
| 4. Loader / validator correctness | n/a — untouched; validate clean |
| 5. Render regression vs known-good | n/a — no render path touched |
| 6. Builder / pak structure | n/a |
| 7. Corpus regression | none — validate + tests green |
| 8. Silent capability change / downgrade | none |
| 9. Stale-zip discipline | not triggered — `packager.py` is NOT in the trigger set (`packaging/templates/`, `packaging/builder.py`, `dashboards/render.py`); docstring-only, zero behavior change → no zip rebuild required |
| 10. Test coverage of the change | n/a — docstring text, not testable behavior |

## Findings

None. 0 BLOCKING / 0 WARNING / 0 NIT.

## If shipped as-is

A developer reading `packager.py` follows a citation that now resolves
to a real, on-topic wire-format reference instead of a dead
`memory/` path. No operator- or pak-facing behavior changes.
