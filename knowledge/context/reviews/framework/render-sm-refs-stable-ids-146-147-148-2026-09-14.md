# Framework review: view-column SM token case, stable extModel ids, SM name-case pin (#146, #147, #148)

- Branch: `fix/146-147-148-render-sm-refs-stable-ids`, worktree `.claude/worktrees/agent-ac612e1ed64c8847b`
- Base: `2ea26eb` (main); commits `9f0f1db` (#146), `372f003` (#147), `01cdd0e` (#148)
- Surface: `src/vcfops_dashboards/render.py` (+46/-14), three test files (+373), `knowledge/context/wire-formats/dashboard_section_gauge_viewdetails.md`
- Reviewer: framework-reviewer, 2026-09-14

## Verdict: APPROVE

0 BLOCKING / 2 WARNING / 3 NIT.

## Checks re-run (independently)

| Check | Result |
|---|---|
| Validate chain, main checkout corpus (managed paks present), worktree `src` on PYTHONPATH: supermetrics, dashboards, customgroups, symptoms, alerts, reports, managementpacks, packaging | all exit 0 |
| Worktree suite, worktree src | 1543 passed, 6 failed, 11 skipped |
| Main suite, main src (baseline) | 1513 passed, 0 failed |
| New tests against pre-fix main src (scratchpad copy, no worktree conftest) | 22 failed / 69 passed: 17 of 22 `test_view_column_sm_ref_case.py` cases and 5 of 6 `test_dashboard_ext_model_id_stable.py` cases fail pre-fix; all #148 pins pass pre-fix, as expected for an invariant that already held |
| Render regression: `vcfops_dashboards package` old src (`PYTHONHASHSEED=0`) vs new src | nested `dashboard/dashboard.json` identical after normalising `extModel<n>-` numbers; `views.zip/content.xml` byte-identical (`4448d9bcb3037e08`) |
| Determinism: new src at `PYTHONHASHSEED=1`, `2`, `0` | `dashboard/dashboard.json` sha256 `ac2d0a0b3ef10b664347a85c7e1fa7a4f6286905534fdb9adebd2b0c6dbd2e2f` on all three runs, matching tooling's claim; `content.xml` identical |
| pak-compare | n/a (no builder or MPB path touched) |

The 6 worktree failures are all `test_release_naming_phase_v2_item1.py` / `test_validator_phase2.py` "real repo" packaging-validate integration tests. Their error is `artifact source not found: content/sdk-adapters/synology/adapter.yaml`, the gitignored managed-pak clone the worktree lacks. `python3 -m vcfops_packaging validate` run in the main checkout with the worktree `src` exits 0. Environmental, confirmed.

## Dimension walk

1. **Global-default leak (anchor `00d3382`).** The change is on the global standalone-import path by design (view XML for every bundle). Re-render of the whole corpus is identical modulo the intended id values; all 19 corpus `supermetric:` column references are lowercase so no shipped content changes shape. Inert on existing content, proven.

2. **Key/label collision (anchor `6c59f6b`).** `_SM_COLUMN_PREFIX_RE` / `_SM_COLUMN_REF_RE` scope `(?i:...)` to the token; the name is a case-sensitive dict lookup against `sm_name_to_uuid_map`, which the new #148 pins prove does not fold on either side (map key or lookup). Two SMs differing only by case bind to their own UUIDs on both the formula path and the view-column path.

   Could `(?i:supermetric):["']` swallow a real adapter metric key? It requires the literal `supermetric:` immediately followed by a quote character. No key of that shape exists in `knowledge/context/adapter_describe_cache`, `reference/`, or `content/` (grep, case-insensitive); VCF Ops keys are `group|stat` or `group:instance|stat` and a `Supermetric|x` style key does not match. The pre-fix code already matched the lowercase form, so the widening only adds case variants of an already-reserved prefix. Safe.

3. **Wire-format conformance.** `extModel<0..99999>-<seq>` shape is unchanged (`dashboard_section_gauge_viewdetails.md`, `wire_formats.md` Scoreboard examples, product fixtures `extModel2490-1`, `extModel21560-1`). `hashlib` is already imported (`render.py:17`). The wire doc's new derivation text matches the code exactly.

4. **Loader/validator.** Untouched. `deps._is_sm_ref` already lowercases; the loader's only `supermetric:` site (`loader.py:676`) lowercases. `render.py` now agrees with both on case. See WARNING 1 for the spellings on which they still disagree.

5. **Render regression.** Clean apart from the stated intent (id values). See table.

6. **Builder / pak structure.** Not touched.

7. **Corpus regression.** Validate chain green over the full corpus with managed paks; suite green apart from the environmental six.

8. **Silent capability change.** None. Previously silent mis-cased tokens now either resolve or raise the existing `ValueError`; that is strictly louder.

9. **Stale-zip discipline and `CURRENT_TEMPLATE_VERSION`.** `render.py` is on the CLAUDE.md "After tooling changes" list, so every `dist/` zip is stale by rule and the orchestrator must delegate a `content-packager` rebuild of every manifest in `bundles/` (WARNING 2, because the brief does not show tooling flagging it). **No `CURRENT_TEMPLATE_VERSION` bump is needed.** `template_version.py` conditions a `render.py` bump on "dashboard or view wire format changes"; the wire form is unchanged and the only value that moves is one the product treats as an opaque per-widget entry id, which every previously distributed zip already carried as a per-run arbitrary number. An old zip is not obsolete, so a stamp that tells operators to rebuild would be a false signal. Same reasoning as the 2026-08-25 changelog entry in `knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md` (no bump, rebuild still required).

10. **Test coverage.** Every changed behaviour is covered, and the new tests were run against pre-fix `src` to prove they detect the defects. The extModel test pins a literal value (`extModel35101-1` for the probe's uuid5 widget id) and runs two subprocesses at different hash seeds, which is the property tested the way it breaks. The #148 pins go through the production map builder and were mutation-tested by tooling (folding at either side breaks 24 or 25 of 25); I did not repeat the mutation, but the tests' structure makes the claim credible and the pre-fix run shows they exercise the real resolver.

## Hunt list from the brief

- **`(?i:supermetric)` matching a real metric key:** no such key exists in any describe cache or reference; the prefix needs `supermetric:` plus a quote. Safe (dimension 2).
- **deps.py vs render.py agreement on every spelling:** agree on case. The loader strips leading/trailing whitespace (`loader.py:2144`), so those are moot. They still disagree on three pre-existing shapes (WARNING 1).
- **Other emission sites or reverse-path parsers assuming the old formula:** none. The only two `hash(`-derived sites were both replaced; `grep` over worktree `src/` finds no remaining builtin `hash(` call. `vcfops_extractor` does not parse `extModel` ids; the reverse-path tests use arbitrary literals (`extModel1-1`, `extModel24191-10`) and pass.
- **sha1 truncation collisions across widgets in one dashboard:** the numeric part is `int(sha1[:8],16) % 100000`, so two widgets in one dashboard collide with probability about 1/100000 per pair; `seq` does not disambiguate across widgets (both would emit `extModel<n>-1`). Corpus scan of the packaged output: 6 dashboards, up to 4 id-emitting widgets each, zero cross-widget collisions. The old `abs(hash()) % 100000` had the identical collision space, so this is not a regression, and the product fixtures show the ids are scoped per widget config (the same `extModel6912-1` / `-2` pattern under one widget). Not a finding.
- **Committed fixtures are product exports, not renderer output:** `tests/fixtures/dashboards/license_consumption_widgets.json` and `license_overview_resource_mode.json` were committed in `165c6f9` with docstrings stating they are trimmed from Scott's public VCF License Consumption export; they carry `showDT` / `roundDecimals` fields the renderer did not emit at that time (they were the "drops" that commit fixed), and their ids are monotonic ExtJS-style counters, not `%100000` residues of any factory widget id. The raw export is not committed, so this is consistent-with rather than proven-from-artifact; either way no test asserts fixture ids against rendered ids (the suite passes with the new derivation), so leaving them alone is correct.
- **Determinism claim reproduced:** yes, see table; sha256 matches tooling's `ac2d0a0b3ef10b66`.
- **6 worktree failures environmental:** yes, see above.

## Findings

### WARNING

1. `src/vcfops_dashboards/render.py:637` vs `src/vcfops_packaging/deps.py:126`, issue #146 (same class), reviewer doctrine "reports-green-while-broken". Pre-existing, not introduced here, but the brief asked. The dependency auditor classifies any attribute whose lowercased text starts with `supermetric:` as an SM reference and skips it; the renderer only enters the SM branch when a quote immediately follows the colon. Probe results (worktree src):

   | attribute | deps `_is_sm_ref` | render branch | wire result |
   |---|---|---|---|
   | `supermetric: "X"` (space after colon) | True (skipped) | plain metric | literal `attributeKey`, `rollUpType=AVG`, silent |
   | `supermetric:X` (unquoted) | True (skipped) | plain metric | literal, silent |
   | `@supermetric:"X"` (formula token in a view column) | True (skipped) | plain metric | literal, silent |
   | `supermetric:"X` (missing close quote) | True | SM branch | `ValueError` malformed, loud |

   Smallest correct fix: widen `_SM_COLUMN_PREFIX_RE` to `(?i:@?supermetric)\s*:` so every SM-shaped attribute enters the branch and the existing malformed-reference `ValueError` fires for the loose forms (`_SM_COLUMN_REF_RE` stays strict). Recommend a follow-up issue rather than expanding this PR, matching how #146 itself was handled.

2. CLAUDE.md "After tooling changes"; `render.py` is on the list. All `dist/` zips are stale by rule and the orchestrator must delegate a `content-packager` rebuild of every manifest in `bundles/` after merge. Tooling's result block (as relayed) does not flag it. No `CURRENT_TEMPLATE_VERSION` bump (dimension 9 above).

### NIT

1. `knowledge/context/wire-formats/dashboard_section_gauge_viewdetails.md:138-140` says the marker member name is "the one remaining per-run difference in a `package` zip". The nested containers (`views.zip`, `dashboards/<uuid>`) also embed the build time as zip member `date_time`, so the outer zip bytes differ across runs that straddle a second boundary; the doc's byte-identical claim is true of `dashboard/dashboard.json` and `content.xml`, which is what matters, but the sentence about the only remaining difference is not. Reword to "the marker name and the nested-zip member timestamps".
2. Tooling reported "12 new tests of which 10 fail on the pre-fix renderer" for #146. Counting parametrized cases, `test_view_column_sm_ref_case.py` has 22 and 17 fail pre-fix (the 5 canonical-token cases pass). The substantive claim holds; the count does not.
3. `_SM_COLUMN_REF_RE` (`(.+?)["']$`) captures `a"b` for `supermetric:"a"b"`. Pre-existing and harmless (the name lookup fails loudly), noted only for completeness.

## If shipped as-is

Operators get byte-stable dashboard renders across runs, mis-cased `SuperMetric:"..."` view columns now resolve (or fail loudly) instead of shipping blank, and no existing bundle changes shape beyond opaque widget entry ids. The remaining silent path is the loose spellings in WARNING 1, which no shipped content uses.

## Round 2: commit `fac94e3` (closes round-1 WARNING 1 and NIT 1)

### Verdict: APPROVE

0 BLOCKING / 0 WARNING / 2 NIT. Round-1 WARNING 2 (content-packager rebuild after merge, no version bump) still stands for the orchestrator.

### Checks re-run (worktree, pak clones now present)

| Check | Result |
|---|---|
| Suite, worktree src | 1562 passed, 0 failed, 7 skipped (matches tooling's claim) |
| Validate chain, all 8 packages | 7 exit 0; `managementpacks` exit 1 on `vcommunity-vsphere` only, error names the view, column, literal, and expected shape (the intended DEF-021 fallout); `packaging validate` exit 0 |
| Extended `test_view_column_sm_ref_case.py` against the previous gate (`01cdd0e` src, scratchpad copy) | 9 failed / 22 passed: exactly the 9 new cases fail on the old gate, as claimed |
| `defect-gate --pak` for all six paks | vcommunity-vsphere refused (2 open blocking: DEF-020, DEF-021); vcommunity-os refused (1, pre-existing); vcommunity, synology, unifi, compliance pass |
| Registry parse (`parse_registry`) | 0 parse errors; DEF-021 reads `severity=blocking`, `status=open`, `affects='vcommunity-vsphere'` (single token, no continuation-line fold, the #153 trap avoided); heading `### DEF-021` matches `_SECTION_RE` |

### Brief items

- **`@` form agreement.** Probe on the new regexes: `@supermetric:"X"`, `@SuperMetric:'X'` are True in `deps._is_sm_ref`, enter the render gate, and the strict ref regex captures the name; the same `sm_map` lookup applies, so the `@` form resolves identically on both paths and the wrong-case-name hard error still fires (pinned by `test_at_sign_form_wrong_case_name_still_hard_errors`). `supermetric: "X"`, `supermetric:X`, `supermetric:"X` (no close quote), `supermetric:"X" ` (trailing space, moot after loader strip) all enter the gate and hit the malformed-reference `ValueError`.
- **Nothing else trips the widened gate.** Grep of every `attribute:` across `content/views/` and all six `content/sdk-adapters/*/views/` for `@?supermetric\s*:` in any case: 19 factory columns and 28 pak columns are quoted; the only loose spellings are the four `Report Distributed Switch for CSV export.yaml` columns (lines 15, 19, 39, 43) DEF-021 names. No SM-shaped `attribute:` exists outside views directories (the other hits are `metric=@supermetric:` inside SM formulas, a different parser). Validate chain confirms: only vcommunity-vsphere fails.
- **DEF-021 substance.** Rendering the view with main's renderer emits the literal `attributeKey="supermetric:Number of VM"` (and the other three) with the plain-metric branch, so the "renders blank on main" claim is reproduced; all four SM names exist in the pak's `supermetrics/` with that exact casing, so the close condition (quote them) is the right fix.
- **Doc claim.** The rewritten determinism note (`dashboard_section_gauge_viewdetails.md:136-141`) now says `dashboard.json` and `content.xml` are byte-identical and that both the marker name and the nested-zip member timestamps carry the build time, which is exactly what the round-1 nested-zip inspection showed.

### NIT

1. Residual paths where `deps._is_sm_ref` and the render gate still differ, all loud or unreachable, none authored anywhere: `supermetric :"X"` (space before the colon) is audited as a plain metric key by deps but hard-errors in render; `@ supermetric:"X"` (space after `@`) is a plain metric key on both paths and is caught only by the describe-cache audit. Neither silently ships a literal, so no finding; recorded so the next widening does not rediscover them.
2. `vcfops_managementpacks validate` wraps the render `ValueError` as "localization-key check failed unexpectedly: View ... has malformed supermetric reference ...". The message is loud and complete, but the wrapper attributes it to the localization-key pass rather than the view render. A cosmetic mislabel; worth a one-line follow-up if it confuses an operator.

### If shipped as-is

Loose `supermetric` column spellings now fail validate with a message that names the view, column, and expected form; the `@` form is accepted in columns and resolves like the plain token; vcommunity-vsphere is release-gated by DEF-021 until its four columns are quoted and the pak re-released.
