# Framework review: managed-paks registry reader stops at `## Retired paks`

- **Date:** 2026-10-15
- **Branch:** `chore/retire-vcommunity-paks` (commit under review `76ad364`; branch context `014ca02`, `81ac459`)
- **Area:** `src/vcfcf_packaging/managed_paks.py`, `tests/test_managed_paks.py`
- **Verdict:** APPROVE (0 BLOCKING / 3 WARNING / 2 NIT). Per CLAUDE.md delegation rule 9 the warnings and nits still get fixed (or, where the code is outside this branch, filed) before the PR opens.

## Change

`load_registry` now breaks at the first non-comment line matching `^## Retired paks\s*$`. Before this, the Python reader returned every entry with an `adapter_kind:` line, so after `014ca02` moved the three vcommunity entries below a new `## Retired paks` heading, main's reader still returned them (verified: main's `managed_paks.py` against the branch registry returns `compliance, unifi, synology, vcommunity, vcommunity-vsphere, vcommunity-os`). The fix is necessary, and with it the reader returns exactly `compliance, unifi, synology`.

## Checks re-run

| Check | Result |
|---|---|
| Seven-package validate chain (+ `vcfcf_packaging validate`) | all rc=0 |
| `pytest tests/` (default addopts, `not slow`) | 2067 passed, 5 skipped, 131 deselected |
| Targeted run, `-m ""`: managed_paks, defect gate, release_builder, publish seams, vcommunity-corpus tests | 230 passed |
| `vcfcf_packaging publish --dry-run` | 12 releases, 0 retired, dist repo left clean |
| README regen against a scratch copy of the dist README | only diff: the `vcommunity-vsphere-managementpack` row drops (intended) |
| `_resolve_sdk_mp_pointer` for synology / unifi / compliance | resolve; vcommunity-vsphere raises `ValueError` (no manifest references it any more) |
| `defect-gate --pak` for vcommunity-vsphere / vsanhostmetrics / synology | rc=0 each; `gate_pak` keys on the token, not on registry membership |
| Render regression / pak-compare | n/a (no renderer, builder, or template touched; no stale-zip or template-version obligation) |

## Hunt results

### 1. Callers and a full publish

Callers of the reader: `release_builder._resolve_sdk_mp_pointer` (hard fail if unregistered), `readme_gen._resolve_sdk_pointer_for_artifact` (soft, returns None), `defects._known_pak_names` (attribution of malformed multi-token `Affects:` only). `publish` enumerates `bundles/releases/*.yaml`; the only sdk-adapter manifests left are synology and unifi, both registered. The deleted vcommunity-vsphere manifest was the only one that would have tripped the hard `ValueError`, so deleting it in the same branch is what keeps `/publish` green. Note that `publish --dry-run` does not call `build_one_release` or the README writer, so I exercised both paths directly (table above). Every `vcommunity*` `Affects:` in `knowledge/context/defects.md` is single-token, so the `_known_pak_names` change attributes nothing differently. Safe.

### 2. Bash and Python parser divergence

Real for the parsers, not for the file as it stands. On the current registry both yield the same live SDK set (bash additionally clones the two forks, see 3). Proven divergences:

- The Python test fixture `_RETIRED_REGISTRY` (`tests/test_managed_paks.py:360`) run through the bash parse loop yields **zero** entries, because bash breaks on the `## Retired paks` inside the comment block before it does comment skipping. Python yields `live-entry, also-live`.
- A heading like `## Retired paks (archived)` (or doubled spaces / a tab) stops bash and not Python, so Python would return the retired entries as live.

Both scripts' comments, and `knowledge/context/managed_paks.md:162-164` ("exact text ..., parsed by both"), claim parity that does not hold. Recommendation: make bash match Python, not the reverse. Python's form (check after comment skip, end-anchored) is the one the tests pin, and the bash in-comment break is the worse failure: a template or note inside a comment that mentions the heading silently empties the clone set. That is an orchestrator edit (`scripts/` is outside tooling's scope): move the check below the comment-skip block and use `[[ "$line" =~ ^##\ Retired\ paks[[:space:]]*$ ]]`. See W1.

### 3. Forks without `adapter_kind:`

Confirmed. Main's reader on main's registry returned the six SDK entries and never the forks; bash on main cloned all eight. On the branch: Python returns 3, bash clones 5. Dependence on that gap:

- `release_builder` / `readme_gen`: no fork release manifests exist and forks are not factory-published (registry says build-sdk, validate-sdk and pak-compare do not apply). The gap actually matches intent here: the reader means "factory SDK paks".
- `defects._known_pak_names`: forks are absent, so a *malformed* multi-token `Affects:` whose first token is a fork name stays unattributed and blocks nothing (fails open). A well-formed single-token `Affects: vsanhostmetrics` gates normally. No such entry exists today. Latent only; see N2.

### 4. Validate chain and suite

Both green (table). The suite needed the gitignored clones; they are present in this tree, including the retired vcommunity clones, which is what hides W2 locally.

## Findings

### BLOCKING

None.

### WARNING

**W1. `scripts/bootstrap_managed_paks.sh:101-107` vs `src/vcfcf_packaging/managed_paks.py:74,131-133`. Parsers claim parity they do not have.**
Authority: the module docstring and both inline comments assert the two readers "match the same line"; `knowledge/context/managed_paks.md:162-164` repeats it. Demonstrated: the Python test fixture gives 0 entries in bash, 2 in Python; `## Retired paks (archived)` stops bash only. Output path: the bootstrap clone set (and CI, which runs bootstrap) vs the publish/README/defect path. Fix: orchestrator aligns the bash check to Python's semantics (after comment skip, end-anchored, single spaces) in this branch; optionally tooling adds a parity test that runs the bash parse loop on the same fixture (the loop can be extracted with sed, as this review did, or factored into `scripts/lib/`).

**W2. CI coverage silently drops for six real-corpus tests.**
Authority: dimension 8/10, silent capability downgrade; the render surface is where both named escapes (`00d3382`, `6c59f6b`) hid. `.github/workflows/ci.yml:84` runs the bootstrap script, which no longer clones vcommunity or vcommunity-vsphere, so these now skip in CI and on every fresh clone: `tests/test_emit_fidelity_bugs.py` `test_96_views_render_without_error` and `test_applicationdiscovery_view_is_valid_but_optional` (skipif at :463, :491), `tests/managementpacks/test_sdk_content_files.py:363` `TestVCommunityIntegration` (2 tests), `tests/test_distribution_view_no_data_warning.py:293,334` (2 tests). They pass locally only because the old clones are still on disk. The test files are not touched by this branch, so a follow-up issue is acceptable, but the loss must be stated in the PR body. Fix: issue to either move a minimal fixture copy of the needed views/SMs into `tests/fixtures/` (keeps the 96-view render regression alive) or delete the tests deliberately.

**W3. `tests/test_managed_paks.py:424`. Exact-list assertion on the live registry.**
`assert names == ["compliance", "unifi", "synology"]` couples the suite to a doc the orchestrator edits. CLAUDE.md says a new pak is "one registry line"; with this test that line reds CI and needs a tooling round, since `tests/` is tooling's write scope. Fix: keep the retired-absent loop, and replace the equality with a subset check (`{"compliance","unifi","synology"} <= set(names)`) plus "no name below the Retired heading is returned".

### NIT

**N1. `src/vcfcf_packaging/managed_paks.py:12` and `:91`. Docstrings say "return all live entries".** Live fork entries are not returned (no `adapter_kind:`). Say "entries that carry an `adapter_kind:` line" so the gap reads as intent, as the new test docstring already does.

**N2. `src/vcfcf_packaging/defects.py:509-519`. `_known_pak_names` omits the forks.** Consequence in 3: a malformed multi-token `Affects:` naming a fork fails open. Not touched by this branch; file an issue, or cover it with the N1 docstring and a one-line note in `knowledge/context/defects.md` that fork names need a single-token `Affects:`.

## If shipped as-is

The publish run drops the vcommunity-vsphere README row and otherwise behaves exactly as today, but the bootstrap and Python readers would keep disagreeing on edge-case headings, and CI would quietly stop running six real-corpus render/packaging tests.
