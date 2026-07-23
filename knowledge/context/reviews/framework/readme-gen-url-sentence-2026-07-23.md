# Framework Review — readme_gen URL-safe first-sentence summarizer

- **Date:** 2026-07-23
- **Area:** `src/vcfops_packaging/readme_gen.py`
- **Change:** New `_first_sentence()` helper (sentence boundary = period
  followed by whitespace or EOS) replaces the naive
  `desc.split(".")[0]` at the release-catalog description-summarization
  site (~line 656). New `tests/test_readme_gen_url_sentence_split.py` (5 tests).
- **Motivation:** Codex P2 on the bundles PR — catalog cell truncated at
  `https://knowledge.` because a URL dot was read as a sentence end.
- **Verdict:** APPROVE (0 BLOCKING)

## Scope note

Working tree also carries concurrent `content/` YAML + `knowledge/designs/`
edits (Codex P1 tier recode). Out of scope per brief — `src/` only. Only
`src/vcfops_packaging/readme_gen.py` is under review; `tests/...` is its
accompanying test.

## Checks re-run

- **Full suite:** `608 passed, 4 skipped, 162 deselected` (67s). Clean.
- **New test file:** `5 passed`.
- **Validate chain:** not re-run — this change touches only README/catalog
  documentation generation, not any loader/renderer/validator on the
  content path. No corpus behavior is exercised by `_first_sentence`.
- **Render-regression:** n/a — `readme_gen.py` emits Markdown docs, not
  import wire format or pak content.
- **pak-compare:** n/a.

## Dimension walk

1. **Global-default / pak-specific leak (anchor 00d3382):** n/a. No
   pak-specific default, coordinate, or flag. `_first_sentence` is a pure
   string function with one call site; behavior is identical for every
   release row regardless of source. No standalone/import path exists here.
2. **Key/label collision (anchor 6c59f6b):** n/a. No key/label derivation;
   output is a human-readable catalog cell, never a resolved identifier.
3. **Wire-format conformance:** n/a. Output is `README` Markdown via
   `publish.py::update_readme_release` / `cli.py::update_readme`. Not
   `template.json`, `describe.xml`, dashboard JSON, or any imported format.
4. **Loader/validator correctness:** untouched.
5. **Render regression vs known-good:** n/a (no renderer touched).
6. **Builder/pak structure:** `builder.py`, `templates/`,
   `render.py` all confirmed unmodified (`git status`). readme_gen is not
   invoked by the pak builder.
7. **Corpus regression:** full suite green; no validator path touched.
8. **Silent capability change / downgrade:** HUNTED — see below. No new
   blank-row risk.
9. **Stale-zip discipline:** N/A and correctly so. `readme_gen.py` is NOT
   in the stale-zip trigger set (`src/vcfops_packaging/templates/`,
   `builder.py`, `render.py`). It generates README docs, not zips. No
   `content-packager` rebuild is required by this change.
10. **Test coverage:** Added. 5 tests cover embedded URL preservation,
    simple two-sentence split, missing-terminal-period append, empty/None,
    and URL-at-EOS. Adequate for the changed behavior.

## Silent-downgrade hunt (does the regex ever blank a catalog row?)

Independently probed `_first_sentence` on the brief's edge cases:

| input | result |
|---|---|
| `"...foo.html) — source of record ... classification. Scope tier..."` | first sentence kept, full URL intact |
| `"Requires VCF 9.2 or later for this feature. More text."` | `Requires VCF 9.2 or later for this feature.` (version dot preserved) |
| `"https://knowledge.broadcom.com/.../foo.html"` (URL only) | `https://...foo.html.` (non-empty, period appended) |
| `"Deprecated in ...9.2."` | `Deprecated in ...9.2.` |
| `""` / `None` / `"   "` | `""` |
| `"3.14 is pi"` | `3.14 is pi.` |

The regex returns `""` **only** for empty/whitespace/None input. The prior
`desc.split(".")[0].strip()` logic returned `""` for those same inputs
(`"".split(".")[0]` = `""`). So the empty-cell case is **pre-existing, not
introduced** — no new blank-row regression. For every non-empty
description the helper returns a non-empty string, including the URL-only
case (which the old logic would have chopped to `https://knowledge`).

## Straggler / caller checks

- Grepped `src/vcfops_packaging/` for `.split(".")`: only remaining hits are
  `cli.py:759` and `cli.py:1052`, both semver `major, minor =
  existing_version.split(".")` — unrelated to description summarization and
  correctly left alone. The single description-summarization site was fully
  migrated.
- `re` is imported at `readme_gen.py:48` — no missing-import risk.

## Findings

**BLOCKING:** none.

**WARNING:** none.

**NIT:**
- [readme_gen.py:_first_sentence] Abbreviations (`e.g. `, `i.e. `) are read
  as sentence ends, so `"Uses e.g. a metric..."` truncates to `"Uses e.g."`.
  This is cosmetic (a catalog summary cell) and is strictly *better* than
  the prior `split(".")[0]` behavior, which truncated even earlier
  (`"Uses e"`). No action required; flagged only for awareness if release
  descriptions ever lead with an abbreviation.

## If shipped as-is

Operators reading the generated release catalog see full, un-truncated
descriptions with embedded Broadcom KB URLs intact instead of a cell chopped
at `https://knowledge.`. No content, pak, or import behavior changes.
