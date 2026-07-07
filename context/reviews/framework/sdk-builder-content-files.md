# Framework Review — sdk_builder `content/files/**` packaging (RULE-013)

**Reviewer:** framework-reviewer (read-only, pre-PR gate)
**Date:** 2026-06-16
**Branch:** chore/doc-hygiene (uncommitted working tree)
**Change under review:** `vcfops_managementpacks/sdk_builder.py` (+68 lines) +
new test `tests/managementpacks/test_sdk_content_files.py` (12 tests)
**Root-cause evidence:** `context/investigations/vcommunity-solutionconfig-400-2026-06-16.md`

## What tooling changed

`_write_outer_pak` never packaged an adapter's `content/files/**`, so any SDK
adapter shipping config files (vCommunity's 6 SolutionConfig XMLs) shipped
without them → empty central config store → HTTP 400 / apiErrorCode 1501 on
every fetch. The fix:

1. After the bundled-content blocks, a new gated block recursively copies
   `project_dir/content/files/**` into the pak at `content/files/<rel>`,
   emitting explicit dir entries for `content/`, `content/files/`, and every
   ancestor — mirroring the `conf/profiles/` pattern (lines 915-929).
2. A build-time safety assertion raises `SdkBuildError` if `content/files/`
   is non-empty in-tree but zero files were packaged (silent-drop guard).
3. Documentation of emit status added above `_ALL_CONTENT_DIRS`.

## Verdict: APPROVE — 0 BLOCKING

The change is correct on its load-bearing axis (no global-default leak), wire-
format-conformant, and the silent-drop it fixes is real and proven. Two
non-blocking findings (1 WARNING, 2 NIT) below.

## Checks re-run (independently)

- **validate chain:** PASS — all 7 validators rc=0; `mp validate` reports
  `OK: 4 Tier 2 SDK adapter project(s) valid`.
- **new test:** 12 passed in 0.06s.
- **managementpacks tests:** 61 passed, 4 skipped (pre-existing).
- **full suite:** 333 passed, 4 skipped, 162 deselected, 0 failed. (95 warnings
  are pre-existing Synology key-drift, unrelated.)
- **vCommunity pak rebuild:** `build-sdk content/sdk-adapters/vcommunity` →
  `dist/vcfcf_sdk_vcommunity.1.0.0.3.pak`. `unzip -l` shows all 6
  `content/files/solutionconfig/*.xml` with byte-sizes identical to source
  (49919/3202/2606/3345/716/637), plus correct `content/`, `content/files/`,
  `content/files/solutionconfig/` dir entries.

## Dimension walk

### 1. Global-default / pak-specific leak (anchor 00d3382) — CLEAR (proven)

This is the #1 mode and the load-bearing safety check. **Proven inert** for
adapters that do not ship `content/files/`:

- The new block is double-gated: `project_dir is not None` AND
  `content_files_dir.is_dir()` (lines 1488, 1490). compliance/unifi/synology
  have no `content/files/` directory (verified on disk).
- **Empirical proof:** built `unifi` (a real adapter with `project_dir` set,
  no `content/files/`) and compared the pak entry set with the change stashed
  vs. applied — `git stash` the source, rebuild, `git stash pop`. Entry sets
  are **identical**. The no-content/files adapter's pak is structurally
  unchanged by this diff. (unifi pak has zero `content/` entries either way.)
- There is no standalone content-import path here — `_write_outer_pak` only
  produces SDK adapter paks. The "global path" analog (no-config adapters) is
  proven unaffected.

### 2. Key / label derivation collisions (anchor 6c59f6b) — N/A

No key/label derivation. Files are copied verbatim at their source relative
path. No transform, no localizationKey, no metric key. The packaged XML bytes
are identical to source (verified by `test_file_content_is_correct` and by
byte-size match in the rebuilt pak).

### 3. Wire-format conformance — CLEAR (cited)

Authority: `context/cleanroom-spec/spec/18-pak-content-bundle.md` §9
(`content/files/solutionconfig/`) and the canonical `content/` tree (lines
56-88), plus the ground-truth reference pak
`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/files/`.

- Emitted layout `content/files/solutionconfig/<name>.xml` matches spec §9 and
  the reference pak exactly.
- Dir-entry discipline (zero-byte `content/`, `content/files/`,
  `content/files/solutionconfig/`) matches the `conf/profiles/` precedent that
  the platform's `.upload` staging extractor requires (lines 910-913 comment).
- **No double-write of `content/` root:** `_content_root_written =
  has_bundled_content` (line 1486). When bundled content already wrote
  `content/` at line 1394, the flag starts True and the files block skips its
  own `zf.writestr("content/", "")`. Correct by inspection (see WARNING on
  test coverage of this exact line).

### 4. Loader / validator correctness — N/A

No loader/validator/cross-reference change. UUID stability (RULE-007), prefix
(RULE-006) untouched. validate chain re-run clean.

### 5. Render regression vs known-good — CLEAR

No renderer touched. The vCommunity pak's bundled-content entries are
unaffected; only `content/files/` entries are added. Byte-for-byte source copy.

### 6. Builder / pak structure — CLEAR

This IS a builder change, but it only **adds** the previously-missing
`content/files/` subtree; it does not alter manifest, adapters.zip,
overview.packed, resources, or the bundled-content emission. The no-config
adapter pak is byte-structurally identical (dimension 1 proof). `pak-compare`
skipped — no reference_paks dir present locally (`tmp/reference_paks` absent);
the reference VMware vCommunity pak's `content/files/` tree is the static
ground truth and the emitted layout matches it.

### 7. Corpus regression — CLEAR

Full suite 333 passed / 0 failed; validate chain clean. No previously-good
content mis-validates.

### 8. Silent capability change / downgrade — CLEAR (this fixes one)

The change *removes* a silent downgrade (the dropped XMLs). The safety
assertion makes any future recurrence loud (`SdkBuildError`) rather than
silent. This is the correct direction.

### 9. Stale-zip discipline — N/A

The change touches `vcfops_managementpacks/sdk_builder.py`, **not**
`vcfops_packaging/templates/`, `vcfops_packaging/builder.py`, or
`vcfops_dashboards/render.py`. The CLAUDE.md stale-dist-zip rule keys on those
three paths; it does not apply. SDK paks are not stored in this repo (each
adapter releases from its own CI on a `v*` tag), so there is no factory dist
zip to rebuild for this change.

### 10. Test coverage of the change — MOSTLY COVERED (one gap → WARNING)

12 new tests cover: flat file, nested subdir, all-6 XMLs, byte content, deep
nesting, no-project_dir, no-content/files-dir, empty-dir (no false-fire),
safety-assertion fire, and an in-tree vCommunity integration smoke. Good
coverage. One real gap (W1 below): the `content/` double-write guard's
`has_bundled_content=True` branch is **not** actually exercised.

## Findings

### WARNING

- **W1 — [sdk_builder.py:1486; test_sdk_content_files.py:182-212] dimension 10**
  — `test_content_root_not_duplicated_when_bundled_content_also_present`
  claims (in its docstring) to verify the dual-path duplicate guard, but it
  passes no `views`/`dashboards`, so `has_bundled_content` is False and the
  `has_bundled_content=True` branch of `_content_root_written` never executes.
  The one line that prevents a double `content/` zip entry when an adapter
  ships BOTH bundled views/dashboards AND `content/files/` is correct by
  inspection but has no executing test. The test's own inline comment admits
  this ("views=[] evaluates False"). → **Fix:** make the test pass a real (or
  minimally-rendered) view/dashboard so `has_bundled_content` is True with
  `content/files/` also present, then assert `names.count("content/") == 1`.
  A duplicate `content/` zip entry is the exact class of silent structural
  drift this gate exists to catch.

### NIT

- **N1 — [sdk_builder.py:1520-1528] safety-assertion false-fire on a
  subdir-only tree.** The assertion guards on
  `any(_cf_src.rglob("*"))` (True if any dir OR file exists) but
  `_files_written_count` only counts `is_file()` entries. A `content/files/`
  tree containing **only empty subdirectories** (no files) trips the
  assertion: `any(rglob)` sees the dir, count stays 0 → spurious
  `SdkBuildError`. Reproduced directly. Low severity (degenerate input; real
  trees carry `.gitkeep` files which package fine), but the smallest correct
  fix aligns the guard with the loop's own filter:
  `any(p.is_file() for p in _cf_src.rglob("*"))`.

- **N2 — [sdk_builder.py:1490-1505] dotfiles are packaged verbatim.** The
  recursive walk packages every `is_file()` including `.DS_Store` and
  `.gitkeep` (reproduced). The actual vCommunity adapter tree is clean, and
  this exactly mirrors the `conf/profiles/` precedent (no dotfile filter) and
  even the reference VMware pak (which itself ships `.DS_Store`/`.gitkeep`), so
  this is consistent with ground truth, not a divergence. Noted for hygiene
  only — a future `.DS_Store` committed under an adapter's `content/files/`
  would be imported into the config store (inert, but noise).

## If shipped as-is

An operator installs the rebuilt vCommunity pak on a fresh host; the 6
SolutionConfig XMLs now land in the central config store and every
`/api/configurations/files?path=SolutionConfig/...` fetch returns 200 instead
of 400 — the ~54 gated parity keys light up. No-config adapters
(compliance/unifi/synology) ship byte-identical paks. The only residual risks
are the two non-blocking findings: an untested duplicate-`content/`-entry guard
(W1) and a false-fire on the degenerate subdir-only input (N1) — neither
affects any current adapter.
