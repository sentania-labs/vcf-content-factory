# Framework Review — reorg step 2: `docs/`+`references/` → `reference/`

- **Area:** scripts/{bootstrap_references,immutability_guard,path_reference_audit}.sh; vcfops_* docstring/comment citations
- **Change:** Reorg step 2 moved `docs/` → `reference/docs/` and `references/` → `reference/references/`; tooling made scripts and code citations consistent, plus fixed a pre-existing `((var++))`/`set -e` truncation bug in the bootstrap.
- **Branch:** chore/reorg-step2-reference (working tree vs `main`)
- **Verdict:** APPROVE
- **Findings:** 0 BLOCKING / 0 WARNING / 4 NIT
- **Checks re-run:** validate-chain **pass** (all 7 CLIs exit 0); tests **468 passed / 4 skipped**; render-regression **clean** (no render logic touched; emit-fidelity + reverse tests green); pak-compare **n/a** (no builder/template logic touched)

## Independent verification

- **vcfops_* diffs are provably comment/docstring/CLI-help-string only.** Diff-inspected every hunk (alerts/render.py, dashboards/render.py, extractor/cli.py, managementpacks/{render,render_export,sdk_builder}.py + README, reports/{render,client}.py, both test files). No functional path logic. Grep for runtime path usage (`open`/`Path`/`glob`/`join`) of `docs/` or `references/` in `vcfops_*/*.py` → **zero hits**. Nothing in emit/loader/render code reads these roots at runtime; the reorg cannot change any emitted byte.
- **managementpacks/render.py** additionally corrected two already-stale citations to `context/mpb/mp_schema_vs_existing_mp.md` and `context/mpb/reference-mpb-research.md` — both targets confirmed present on disk.
- **bootstrap_references.sh regex** `\`reference/references/([^/\`]+)/?\`` matches the actual `context/reference_sources.md` `**Local path:**` line format exactly (16 entries verified, including the jcox line with trailing `(design JSONs);` text after the closing backtick — captured slug is clean).
- **Arithmetic fix complete and semantics-preserving.** All 5 counter-increment sites converted `((var++))` → `var=$((var+1))`. No remaining statement-position `((...))` in bootstrap. The only surviving `((...))` in the three scripts is `for (( i = 0; i < n - 1; i++ ))` in path_reference_audit.sh — a C-style for-loop arithmetic context, immune to the `set -e`/post-increment-returns-0 abort. The fix is a genuine bug fix: previously the first counter to go 0→1 (e.g. first "Exists" repo) returned exit 1 under `set -e` and truncated the bootstrap after the first registry entry. Counters still start at 0 and increment by 1 — no semantics change.
- **immutability_guard match is prefix-with-slash-safe.** `[[ "${p}" == "${d}"* ]]` with `d="reference/"` requires the literal `reference/` prefix; `reference-foo`, `referencebook.md`, or a hypothetical `references-old/` do not match (char after `reference` must be `/`). The R-handling `case` block was **not** touched by this diff — only `IMMUTABLE_DIRS` and two echo messages changed — so no rename-classification regression is introduced here.
- **path_reference_audit.sh two-segment bare-root pass does not over-allow.** The new `reference/references|reference/references/` case returns 0 only for the exact bare root; any `reference/references/<name>` asset falls through to the `reference/references/?*` handler and is still registry-gated against `context/reference_sources.md`. Ran the audit: exits 0 with only the two documented `reference/references/tvs` RULE-015 WARNINGs — no genuine dead ref suppressed. The tooling-claimed `reference/docs/extracted` findings have resolved now that the files are staged.

## Dimension walk

- **1 Global-default / pak-specific leak (00d3382):** N/A — no default, coordinate convention, transform, or flag added anywhere. Standalone/content-import path is byte-identical.
- **2 Key/label collision (6c59f6b):** N/A — no key/label derivation logic touched.
- **3 Wire-format conformance:** No emit logic changed; validate + emit-fidelity tests green.
- **4 Loader/validator correctness:** No logic changed; validate chain exit 0 across corpus.
- **5 Render regression:** No render logic changed; render/reverse tests pass.
- **6 Builder/pak structure:** `sdk_builder.py` change is a comment; no `template.json`/`describe.xml`/pak-shape logic touched.
- **7 Corpus regression:** validate exit 0; 468 passed / 4 skipped.
- **8 Silent capability change:** None.
- **9 Stale-zip discipline:** `vcfops_dashboards/render.py` is in the diff, so the mechanical CLAUDE.md trigger ("modifies anything in render.py → all dist zips stale") fires — see NIT-1. The change is provably a docstring-only edit; rendered JSON is byte-identical, so a rebuild is a no-op.
- **10 Test coverage:** No behavior changed in `vcfops_*`, so no new tests required. The three shell scripts remain untested (pre-existing gap) — see NIT-4; the bootstrap arithmetic fix was verified manually.

## NITs (non-blocking)

1. **[stale-zip discipline]** The mechanical CLAUDE.md trigger fires because `vcfops_dashboards/render.py` is touched, but the edit is a comment and rendered output is provably unchanged. Tooling's result block did not mention it. No functional rebuild is required; the orchestrator can skip the `content-packager` pass for this diff, or run it defensively — either is correct.
2. **[vcfops_reports/render.py:8]** Docstring line `Wire format reference: context/reports_api_surface.md` is stale — the file lives at `context/api-surface/reports_api_surface.md`. Pre-existing, but tooling was actively editing lines 11–12 of this same docstring and could have swept it. Fix: update the citation.
3. **[scripts/immutability_guard.sh:128]** For a rename that lands a file *into* `reference/`, the offender is labeled `R (renamed in, content changed)` even when it is a pure `R100` rename with no content change (as the reorg's own `docs/*` → `reference/docs/*` moves are). Cosmetic only; the flag itself is correct. Also note: were the guard ever wired as a hook, running it over this reorg commit refuses it (the moves trip the `renamed away`/`renamed in` branches) — it is currently a manual tool ("does not yet run automatically as a git hook"), so it blocks nothing here. Consideration for whoever eventually wires it.
4. **[scripts/*.sh]** The three reorg-touched shell scripts have no test coverage (pre-existing). The bootstrap arithmetic fix is a real behavior change verified only by manual inspection + a live audit run. Not blocking, but a candidate for a small bats/shell test if this surface keeps changing.

## If shipped as-is

An operator sees no behavioral change: all seven validate CLIs, the full pytest suite, the path audit, and the immutability guard behave correctly against the new `reference/` root, and the bootstrap now completes past the first registry entry instead of truncating. No downstream pak or content-import path is affected — every `vcfops_*` change is inert (comment/string).

## Addendum (2026-07-07) — re-verification of incremental citation fix

Tooling applied NIT-2 plus its sibling: `vcfops_reports/render.py:7` and `vcfops_reports/client.py:90`, both `context/reports_api_surface.md` → `context/api-surface/reports_api_surface.md`. Diff-inspected: both hunks are docstring/comment-only (no code change); target path confirmed on disk; grep of `vcfops_*/` shows zero remaining stale `context/reports_api_surface.md` citations. A content-packager rebuild touched `dist/` only. **APPROVE stands for the full change set.**
