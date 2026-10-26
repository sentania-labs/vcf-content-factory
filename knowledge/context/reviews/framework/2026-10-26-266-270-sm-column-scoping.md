# Framework review: `supermetric:"<name>"` column scoping (#270) and walker SM refs (#266)

- Branch: `fix/266-270-name-form-sm-columns`, commit `0b844c1` on `main` `173767c`
- Reviewer: `framework-reviewer`, 2026-10-26
- Area: `src/vcfcf_core/supermetrics/column_resolver.py` (new), `src/vcfcf_dashboards/sm_columns.py` (new), `src/vcfcf_core/dashboards/render.py`, `src/vcfcf_core/dashboards/packager.py`, `src/vcfcf_core/supermetrics/loader.py`, `src/vcfcf_core/common/dep_walker.py`, `src/vcfcf_common/dep_walker.py`, `src/vcfcf_dashboards/cli.py`, `src/vcfcf_dashboards/handler.py`, `src/vcfcf_managementpacks/sdk_builder.py`
- Verdict: **APPROVE** (0 BLOCKING / 3 WARNING / 6 NIT). Per delegation rule 9, fix every finding in one re-brief before the PR opens.

## What I re-ran, independently

All runs used scratch copies of the branch and of `main` `173767c`, never the worktree or the real pak repos.

| Check | Result |
|---|---|
| Seven-package validate chain (branch) | all seven exit 0 |
| Full suite, `-m "" --override-ini=addopts=` with paks present | **3146 passed / 9 skipped**, matching the author's claim. The default selection gives 3015 passed (131 deselected). Main's default selection gives 2989. |
| Render regression, every view YAML in `content/views`, `third_party/*/views`, `content/sdk-adapters/*/views` (247 files), branch resolver vs main `sm_map=sm_id_map()` | `content/views`: 26 files byte-identical (timestamps normalized), 35 `Super Metric\|sm_` occurrences on both sides. idps-planner, compliance, vcommunity-os: identical. The only diffs are 19 vcommunity/vcommunity-vsphere views. They errored on main ("could not be resolved", since factory sync only knew `content/supermetrics`) and now bind to their own pak's SMs. |
| `vcfcf_dashboards package` (standalone content-import zip, factory content) | branch and main zips identical apart from the random marker filename and timestamps |
| Bundle payloads (`render_bundle_payloads` with `sm_id_map(bundle.sm_paths)`), all 3 bundles in `bundles/` | identical hashes on branch and main. The new duplicate-name rejection trips on none of them. |
| `validate-sdk`, factory CLI, all paks | compliance, synology, template, unifi, vcommunity, vcommunity-os, vcommunity-vsphere OK (cluster-perf-risk and vsanhostmetrics have no `adapter.yaml`) |
| Standalone buildkit (built into scratch, run with `env -i`) `validate-sdk` | vcommunity, vcommunity-vsphere, compliance OK. Kit parity holds. |
| pak-compare | n/a: no pak built. The SDK view render is unchanged for every pak that bundles SMs, and no pak bundles zero SMs while naming one. |

Twin check: vcommunity and vcommunity-vsphere carry the same 37 SM ids. "Bind to their own pak" is therefore true by set key, but this corpus cannot tell it apart from binding to the twin. The author's unit test `test_sdk_adapter_paks_are_separate_content_sets` covers different-id twins.

## Dimensions cleared, with evidence

1. **Global-default leak (anchor `00d3382`).** `sm_resolver` is an additive keyword that defaults to None on `render_views_xml`, `render_view_def_fragments` and `build_import_zip`. With None the old `sm_map` branch runs verbatim. The standalone package zip and every bundle payload are byte-identical to main, so nothing leaks onto the import-zip or bundle path.
2. **Key collision (anchor `6c59f6b`).** This change removes a collision: the flat `{name: uuid}` map let a third-party column bind to a same-named factory SM, last-loaded-wins. Binding is now per content set, ambiguity raises, and factory keys are unchanged.
3. **Wire format.** No XML or JSON shape change. `attributeKey` is still `Super Metric|sm_<uuid>`.
4. **Loader/validator.** Scoped `sm_id_map` now rejects two different ids under one name. That previously chose last-loaded silently, and no bundle or pak trips it. The UUID contract (RULE-007) is untouched. Read-only loading never mints. The sync path no longer mints at all (see N5).
5. **Render regression.** Clean (table above).
6. **Builder.** `sdk_builder` scope is always a list, so factory `build-sdk` / `validate-sdk` no longer fall back to `content/supermetrics`. That now matches the kit, which has used an empty map since M2 row 3.
7. **Corpus.** Validate chain and suite green.
8. **Silent downgrade.** None found. Not-found, ambiguous, broken own set and id-less SM all fail before any import or write.
9. **Stale-zip discipline.** `render.py` changed, and the author flags a full rebuild. Every bundle payload is byte-identical, so no distributed zip is wrong. Leaving `CURRENT_TEMPLATE_VERSION` alone is correct: a bump would tell every operator to rebuild a zip that is not stale.
10. **Tests.** `tests/test_sm_column_scoping.py` (493 lines) covers own set first, factory fallback, cross-project isolation, ambiguity, broken own set, id-less, handler no-import, pak sets, pak no-fallback, the scoped-map duplicate, walker enable/check/lookup/missing, and the regex parity pin. The two #154 preflight tests were inverted to the new semantics. Each inversion is the point of #270, not a weakened assertion.

## WARNING

**W1. `src/vcfcf_core/common/dep_walker.py:540` and `:632`: the #154 formula-referent walk can check another pak's same-named SM (author's open item 2).**
- Authority: issue #270 says the preflight and the renderer must never disagree; reviewer doctrine says to prove behavior on every path.
- `supermetrics_used_by` seeds through the new resolver, then calls `expand_sm_crossrefs(seeds, all_sms)`. That still uses `_pick_sm_by_name` by `provenance`.
- This branch widened `all_sms` to every `content/sdk-adapters/*/supermetrics`. Pak SMs carry provenance `""` (a pak repo has its own `content/` child, so `_find_repo_root` stops at the pak), so every pak shares one provenance bucket.
- Probe: pak `p2`'s SM `X` with formula `@supermetric:"Y"`, where `p1` and `p2` both define `Y` with different ids. The walk took **`p1`'s `Y`**.
- Effect: the read-only pre-import check reads the wrong formula. It can pass a sync whose real referent is missing (green while broken) or block a valid one. Emitted bytes are unaffected.
- Not reachable on main (pak SMs were not in the corpus). Not hit today (the only twins share ids).
- Fix: give `expand_sm_crossrefs` an optional `resolve(name, referrer)`. In `supermetrics_used_by`, pass `lambda name, ref: column_resolver.resolve(ref, name)`. `content_set_of` works on SMs, so a referent resolves in the referrer's own set and then the factory, the same rule as the column. Add a different-id two-pak test.

**W2. `src/vcfcf_dashboards/cli.py:170` (`cmd_validate`): validate does not check name-form columns (author's open item 1).**
- Authority: `knowledge/rules/validate-before-install.md` (RULE-005).
- A column that is unresolved, ambiguous, or names an SM in a broken set passes `vcfcf_dashboards validate` and fails only at package, sync or build.
- The branch doc honestly moves the cross-reference table row from "validate" to "render", but the gate the orchestrator runs (the only CLI it runs directly) now knows less than sync does.
- The gap predates the branch, but `cli.py` and the resolver are both touched here and the fix is small, so it belongs on this branch. It is not a follow-up issue.
- Fix: in `cmd_validate`, after the views load (factory plus the `third_party/*` it already walks), run `sm_columns.column_errors(views, sm_columns.load_sm_corpus())`. Treat ambiguous, unresolved and broken-set as ERROR. Treat id-less as WARN, so validate does not depend on chain order (SM validate mints first anyway). Pak views stay with `validate-sdk`. Add one test per failure class.

**W3. `src/vcfcf_managementpacks/sdk_builder.py:2641`, `:4250`, `:4606`, `:4367`, and `src/vcfcf_core/supermetrics/loader.py:286` (kit `sm_loader.py`): an adapter-visible build change with no Tier 2 changelog entry or `BUILDKIT_VERSION` decision.**
- Authority: `knowledge/context/tier2_architecture.md` changelog convention. Every `sdk_builder` or kit change records Versioning and Adapter adoption, including "no bump" decisions (see the #226 and #260 rows).
- Two changes go undocumented. Factory `build-sdk` / `validate-sdk` lose the `content/supermetrics` fallback. The kit's `sm_loader` gains a new build failure (duplicate SM name within the pak).
- Fix: add a 2026-10-26 row. State "factory now matches the kit, no fallback; kit sm_loader rejects duplicate names; all seven SDK paks validate clean on factory and kit". Record an explicit `BUILDKIT_VERSION` decision (no bump is defensible: no pak trips it) and "Adapter adoption: none".

## NIT

**N1. `src/vcfcf_dashboards/sm_columns.py:51`: `content_set_of` checks only the symlink-resolved path.**
- A pak symlinked into `content/sdk-adapters/<name>` from elsewhere loses its `sdk-adapter:<name>` key. Probe: it returned `'factory'`.
- Its SMs then merge into the factory or `""` set. Mostly that fails loud as ambiguity, but a pak view could reach a second symlinked pak's SM.
- The module docstring (lines 8-10) and the doc also say a pak "reads as factory provenance". For real pak repos, which have a `content/` child, it reads `""`.
- Fix: check `Path(src).absolute().parts` first, then the resolved parts. Correct the docstring.

**N2. Dead helpers left behind.**
- `vcfcf_supermetrics/loader.py:104` `unscoped_sm_defs_readonly`, `:131` `load_dir_readonly` (its only caller is the former), and `vcfcf_dashboards/cli.py:682` `_sm_corpus_dirs` have no callers.
- `cli.py:734` docstring still names `_sm_corpus_dirs`.
- The unscoped mode of `sm_id_map()` also has no in-repo caller now (both builders pass a list).
- Fix: remove them, or mark them as kept for API compatibility.

**N3. The legacy `./supermetrics` fallback is gone.**
- The unscoped map scanned `content/supermetrics` and then `supermetrics` under cwd (`vcfcf_supermetrics/loader.py:96`).
- The new corpus reads only `content/supermetrics`, `third_party/*` and paks. A run from a layout with root-level `supermetrics/` (for example a pak repo root) now fails loudly unless `--supermetrics-dir supermetrics` is passed.
- Fix: add `supermetrics` as a primary fallback when `content/supermetrics` is absent, or say so in the doc section.

**N4. Pak view resolution differs between sync and build.**
- `dashboards package` / `sync` of a pak view falls back to a factory SM. `build-sdk` refuses the same column (pak scope only).
- It fails loudly at build, so this is not silent, but the two paths disagree about one view.
- Fix: pass `fallback_set=None` for `sdk-adapter:` sets (a small `_sets_for` rule). Otherwise state the asymmetry in the doc section.

**N5. Factory-only behavior change: package and sync no longer mint an id into a freshly authored, id-less SM.**
- The old `sm_id_map()` loaded with `load_dir`, which minted. The new path fails with "run validate to mint one".
- This is better under RULE-005 and is loud, but it is a change for factory-only users.
- Fix: one line in the PR body and the doc.

**N6. `supermetrics_used_by`'s fourth parameter changed meaning (`column_sms` dict to `column_resolver`) without a shim.**
- Only `cli.py` calls it in-repo. `vcfcf_core` is a distributable package (`vcf-cf-tooling-core`), so an external caller passing `column_sms=` gets a `TypeError`, and one passing it positionally gets an `AttributeError`. Both fail loud.
- Fix: note it in the PR body. Optionally accept `column_sms=` once with a `DeprecationWarning`.

## Observation (not a finding)

#266 makes `vcfcf_dashboards sync` of factory content **enable** the SMs behind the 19 name-form columns in 10 views on the Default Policy when they are off. This is a new live write on a path that only skipped them before. It is the issue's intent and matches `sm_<uuid>` column behavior; call it out in the PR body so it is not a surprise on the first post-merge sync.

## If shipped as-is

Factory content renders and imports byte-identically. Third-party and pak name-form columns now bind to their own SMs, or fail before import, instead of binding silently to a factory twin. `validate` stays blind to those columns. The pre-import referent check can read the wrong pak's formula once two paks diverge on a shared SM name.
