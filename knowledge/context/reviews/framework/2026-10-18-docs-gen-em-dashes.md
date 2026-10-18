# Framework review: docs-gen em-dash removal (#194, #225)

- **Branch / commit:** `fix/docs-gen-em-dashes` @ `5f8f6dc`, base `origin/main` `c433366`
- **Area:** `src/vcfcf_managementpacks/docs_gen.py`, `src/vcfcf_managementpacks/sdk_builder.py` (Tier 2 SDK docset and build-docs writers)
- **Reviewer:** framework-reviewer (RULE-013), 2026-10-18
- **Verdict:** APPROVE (0 BLOCKING / 0 WARNING / 1 NIT)

The change does what it claims: no generated SDK pak doc carries U+2014 any
more, the new test fails on the old code, and regenerating the real UniFi
docset differs from the committed docs only by the em-dash replacements and
the version stamp. One coverage nit: the test and commit message say the
fixture hits every placeholder path, and it misses one.

## Checks re-run

| Check | Result |
|---|---|
| New test on branch | 2 passed |
| New test with both source files reverted to `c433366` (temp copy) | 2 failed |
| Per-hunk mutation (each source hunk reverted alone) | every generated-output hunk turns the test red, except `docs_gen.py:1012` (see NIT-1). Docstring, comment and log-line hunks stay green, as expected (they never reach a doc) |
| `tests/managementpacks/` | 195 passed, 10 skipped |
| Full `tests/` | 2053 passed, 6 failed, 15 skipped. All 6 failures are real-repo release-manifest integration tests (`test_release_naming_phase_v2_item1.py` x5, `test_validator_phase2.py` x1) failing on `artifact source not found: content/sdk-adapters/synology/adapter.yaml`: the worktree has no gitignored managed-pak clones. Environmental, unrelated to this diff (neither test touches docs_gen or the doc writers) |
| Seven-package validate chain | all 7 exit 0 |
| UniFi regeneration (clone exported via `git archive` into a temp dir, clone untouched) | `docs/README.md`, `docs/inventory-tree.md`, `.svg`, `.excalidraw`, `REFERENCE.generated.md`: zero residual diff after normalizing em-dash to new form and `0.0.0.15` to `1.1.0.15`. 84 em-dashes in committed `REFERENCE.generated.md`, 0 in the regen |
| Render regression / pak-compare | n/a (no content renderer or pak structure touched) |

## Scope confirmation

- `sdk_builder.py` edits are exactly the five claimed generated-output
  strings: REFERENCE title (`:2701`), REFERENCE identifier default
  placeholder (`:2749`), REFERENCE unit placeholder (`:2788`), REFERENCE
  monitored placeholder (`:2790`), README identifier default placeholder
  (`:3012`). No other line in the file changed.
- No em-dash remains anywhere in `docs_gen.py`.
- The em-dashes left in `sdk_builder.py` are in docstrings, comments and
  `stderr` log lines only; none sits in a string written to REFERENCE,
  README, CHANGELOG or the docset (checked every hit past `:2600`, and
  `_generate_changelog_md` / `_generate_readme_md` / the traversal tree
  renderer have none).

## Downstream pinning and parsing

Grepped `src/`, `tests/`, `scripts/`, `.github/`, `.claude/` and every
managed-pak clone's `.github/` and `scripts/` for the old header ("Do not
edit" variants), the old title shapes (`(U+2014) Reference`, `(U+2014) Documentation`,
`Inventory Tree (U+2014)`, `Overview (U+2014)`, `Installing & Configuring`), the Scaffold
callout, the Cross-MP intro, and the bare placeholder. Nothing pins or parses
any of them. The only "Do not edit" hit outside the two files is unrelated
prose in `.claude/agents/supermetric-author.md`.

## Readability and punctuation

- Each replacement keeps its meaning: `X Documentation`, `X Reference`,
  `Inventory Tree: X`, `Overview: X`, `Do not edit: regenerated on every
  build.`, `**Scaffold:** edit this file...`, and the Cross-MP intro split
  into two sentences all read as well as or better than before.
- A lone `-` in a GFM table data cell renders as literal text (only the
  second row is a delimiter row), and it matches the placeholder UniFi build
  15 already hand-adopted (#225), so future generated-vs-hand merges stop
  showing that diff.
- Added lines carry no en-dash, no `--`, and no other new non-ASCII. The one
  non-ASCII character on an added line is the pre-existing `→` in a docstring.
- Commit message has no em-dash.

## Dimensions

1. Global-default leak (`00d3382`): n/a. No renderer default, coordinate or
   flag; text only.
2. Key/label collision (`6c59f6b`): n/a. No key derivation touched.
3. Wire format: n/a. Markdown docs only; no describe.xml, template.json or
   content JSON emission changed.
4. Loader/validator: untouched.
5. Render regression: UniFi regen proves zero non-intended drift.
6. Builder/pak structure: pak file set unchanged; only doc text inside it.
7. Corpus regression: validate chain green; test suite green apart from the
   environmental failures above.
8. Silent downgrade: none. No content dropped; placeholders still mark
   blank cells.
9. Stale-zip / template version: none of the trigger paths
   (`src/vcfcf_packaging/templates/`, `builder.py`, `discrete_builder.py`,
   `release_builder.py`, `assembly.py`, `dashboards/render.py`) is touched,
   and content-bundle zips carry no SDK docs. No content-packager rebuild and
   no `CURRENT_TEMPLATE_VERSION` bump needed. SDK paks pick up the new text
   on their next build.
10. Test coverage: added and proven to fail on the old code. One gap, NIT-1.

## Findings

### BLOCKING

None.

### WARNING

None.

### NIT

- **NIT-1** `[src/vcfcf_managementpacks/docs_gen.py:1012]`,
  `[tests/managementpacks/test_docs_gen_no_em_dash.py:9-12]`. The test
  docstring and the commit message both say the fixture "exercise[s] every
  placeholder path." It does not. The `installing.md` fallback row
  (`| - | - | - | - | No adapter instance kind found |`) is only written when
  describe.xml has no `type="7"` kind, and the fixture always has one.
  Reverting that line alone leaves the test green. The source line itself is
  correct. Fix: add a small second fixture with no adapter-instance kind and
  assert that row (and no em-dash) in `docs/installing.md`, or narrow the
  docstring and commit message so they stop claiming full coverage. The
  first option is better because it closes the gap rather than describing
  it.

## Not a finding: follow-up for the per-pak regeneration pass

`docs/overview.md` and `docs/installing.md` are scaffold-once files. The
generator never overwrites them, so this fix does not reach existing paks'
copies. UniFi's committed `docs/overview.md` still opens with
`# Overview (U+2014) VCF Content Factory UniFi Controller` and has em-dashes in its
hand-written prose, and `installing.md` has some too. The "one regeneration
pass per pak" that #225 calls for will clean REFERENCE, README, the
inventory tree and the diagrams. It will not clean these two files, which
need a hand edit in each pak repo. That work lives in the pak repos, not on
this branch.
