# Framework review: dashboards and bundle sync, @supermetric referent preflight (#154)

- Branch: `fix/154-dashboards-sync-sm-walker`, commit `3701f4b`, diffed against `main`
- Reviewer: `framework-reviewer`, 2026-10-26
- Files: `src/vcfcf_core/common/dep_walker.py`, `src/vcfcf_dashboards/cli.py`,
  `src/vcfcf_packaging/syncer.py`, `tests/test_dashboards_sync_sm_referent_preflight.py`
- Verdict: **APPROVE** (0 BLOCKING / 4 WARNING / 2 NIT). Per CLAUDE.md delegation rule 9,
  every finding below is fixed before the PR opens.

## Checks re-run

| Check | Result |
|---|---|
| Validate chain (7 packages) | all rc 0 |
| New tests | 6 passed |
| Full suite | 2628 passed, 6 failed, 9 skipped. The 6 failures are the known main failures (`test_release_naming_phase_v2_item1.py` x5, `test_validator_phase2.py` x1) |
| Render regression | n/a. No render, builder, template or assembly file is in the diff, and `cmd_package` is unchanged |
| pak-compare | n/a |
| Stale-zip / `CURRENT_TEMPLATE_VERSION` | n/a. No file on the stale list is touched, and `templates/install.py` does not import the syncer |
| Corpus simulation, dashboards preflight | 26 views and 10 dashboards seed 39 of 41 repo SMs. There are 8 `@supermetric` referents and every one resolves from repo YAML, so there are zero target lookups and no false block on the factory corpus |
| Corpus simulation, bundle preflight | 3 bundles carry SMs (storage-path-monitoring, vcf-license-consumption-overview, vks-core-consumption). All are self-contained, there are no duplicate names and zero target lookups, so there is no false block on any shipped bundle |

## Answers to the brief's hunt list

**False blocks.** I found none on the shipped corpus, which I simulated (see above). Target
lookups use `find_by_name`, which matches exact names. That is the same matcher the SM push resolver uses
(`import_supermetrics_bundle._lookup_remote`). So a case or whitespace variant
that the preflight rejects would also have been refused when the SM was pushed. A referent that exists only on the
target resolves, and a test covers it. One behaviour is new but correct: if the repo formula of a
used SM was edited to reference a name that is nowhere, a dashboard sync now blocks
even though the target still holds the old formula. The DEP-ERROR text names the fix.
Coverage gaps, which mean a check is skipped rather than a sync wrongly blocked, are W1 to W3.

**Silent downgrade on SM load failure.** The fallback is fail-open and only partly
acceptable. For `content/supermetrics`, a load failure also empties the renderer's
`sm_id_map()`. Any `supermetric:"<name>"` view column then raises in
`build_import_zip` before the import, so name-form content still stops,
although it stops with a traceback rather than a DEP-ERROR. Content that uses only `sm_<uuid>` columns or
dashboard widget keys imports with the gate off, and the only signal is a WARN line. The bigger problem
is that `_load_repo_sms` enforces the framework prefix. Every third_party SM
directory therefore "fails to load", so the gate turns off on a legitimate configuration (W1).

**Walker name map.** The claim that the map "used to be always empty because of a wrong
default dir" is **not true on the CLI path**. The `sync` argparse default for
`--supermetrics-dir` has been `content/supermetrics` since `c170c0c` (layout
v3), so `args.supermetrics_dir` was always set and main loaded the repo SMs
into the map. The `_run_dep_walker` hunk is a pure refactor:
`sm_name_map = {d.name: d.id for d in sm_defs}` is byte-identical, and the swallowed
error is swallowed the same way. Inside `walk_and_check`, `sm_name_map` feeds only uuid-to-name
annotation and Phase 1b name resolution of SM-formula refs. With
`supermetrics=[]` there are no formula refs, and Phase 2 enables are keyed by the
view/dashboard UUID refs. **No enable or policy behaviour changes.** The comment
on `supermetrics=[]` is accurate. Phase 2 builds `syncing_ids` from
`supermetrics`, and an SM in that set that is not enabled is reported as "in sync batch (enable
step will activate)" and **not enabled**. Dashboard sync has no SM enable step,
so passing the used SMs would silently skip enabling them. It would also pull their formula
metric refs into the Phase 3 describe check. Keeping `[]` is correct. (The stale
defaults are N1.)

**Bundle rc semantics.** Before this change, a missing referent raised `VCFOpsError` inside
`resolve_sm_formula`. The SM handler caught it, marked the items failed, and returned rc 2, and the views and
dashboards imported anyway with blank SM columns. Now the result is rc 1 and nothing is imported,
symptoms, alerts, customgroups and reports included. That matches the issue's
"import nothing" requirement and the docstring's "1 on fatal". The change is limited to the factory CLI.
The shipped `install.py` is standalone, does not import `vcfcf_packaging.syncer`, and
resolves SM refs at build time. No shipped path changes.

**Syncer callers.** `vcfcf_packaging.cli.cmd_sync` returns the rc directly.
`sync_all_bundles` takes `max(rc)` and keeps going, so one bundle with a broken
referent fails the run but does not stop the others. Nothing in `.claude/` or the
docs branches on 1 vs 2. The existing tests that pass `session=object()` still pass
because their bundles' SMs carry no `@supermetric` tokens. A caller that cannot look up
SMs gets "no super metric ... on the target" from `_lookup_sm_uuid_on_target`
returning None when `find_by_name` is absent. Both real callers pass the SM-extended
client (`vcfcf_supermetrics.client.VCFOpsClient`), so this cannot happen in practice.

## Findings

### WARNING

**W1. `src/vcfcf_dashboards/cli.py:647-661` (`_load_repo_sms`) and `:686-693`.** Authority:
`knowledge/rules/` RULE-006 is a *validate* gate, not a sync gate. The precedent is the
same file at `:313`, where the third_party SM pass loads with
`enforce_framework_prefix=False`. `_load_repo_sms` calls `load_dir(dir)` with the
default `enforce_framework_prefix=True`. I verified
`_load_repo_sms("third_party/idps-planner/supermetrics")` and it returns `([], 'name "[IDPS]
Net Receive (All VMs)" missing framework prefix ...')`. So
`vcfcf_dashboards sync --supermetrics-dir third_party/<project>/supermetrics`
always prints "could not load ... not checked" and imports with the #154 gate
off, and every third_party project hits this. Separately, any genuine load failure
is fail-open for `sm_<uuid>`-only content. **Fix:** load with
`enforce_framework_prefix=False`. When the directory exists and still fails to
load, return 1 ("cannot check super metric references; nothing was imported").
Validate (RULE-005) already fails on that corpus, so failing closed blocks
nothing that is validate-clean.

**W2. `src/vcfcf_dashboards/cli.py:686-694`.** Authority: the brief scope (third_party
projects), and `_navigation_corpus` in the same file, which already treats `content/` plus
`third_party/*/` as the corpus. With the default `--supermetrics-dir`, an SM that a
third_party view or dashboard names by `sm_<uuid>` is not in `repo_sms`, so
`supermetrics_used_by` never seeds it and its referents are never checked. Nothing is
printed about it. The current corpus has no exposure, because the idps-planner SMs carry no
`@supermetric` tokens, but the gate is structurally blind on that path. **Fix:** build
the preflight corpus from `--supermetrics-dir` plus every `third_party/*/supermetrics/`,
loaded with W1's no-prefix load. `supermetrics_used_by` already picks by provenance
across same-named candidates. Alternatively, print a WARN naming any `sm_<uuid>` seed
that is in no loaded corpus.

**W3. `src/vcfcf_core/common/dep_walker.py:522`, `_VIEW_SM_NAME_RE`.** Authority: the
renderer's `_SM_COLUMN_REF_RE` (`src/vcfcf_core/dashboards/render.py:692`,
`(?i:@?supermetric):["'](.+?)["']$`) and the #146 review. Two parsers that disagree on
the token is the exact class #146 closed. The view loader also lowercases before
accepting (`src/vcfcf_core/dashboards/loader.py:767`). The new regex is case-sensitive, and I proved the gap:

```
'supermetric:"X"'   renderer resolves: True  preflight seeds: 1
'SuperMetric:"X"'   renderer resolves: True  preflight seeds: 0
'@SuperMetric:"X"'  renderer resolves: True  preflight seeds: 0
```

A mis-cased column passes validate, renders to the SM, and its referents are never
checked, with no output. **Fix:** import and reuse the renderer's ref regex, or
match `(?i:@?supermetric):["'](.+?)["']$` against `col.attribute.strip()`. Add
a test.

**W4. `tests/test_dashboards_sync_sm_referent_preflight.py`.** Authority: review dimension
10. The new behaviour has no test for any of these:
1. The SM-YAML load-failure path in either direction (the W1 decision).
2. A target lookup that raises. Ambiguous or transport failures go to `_LOOKUP_FAILED` and then rc 1, on both paths.
3. A seed from a dashboard widget `sm_<uuid>` key. Only view columns are exercised.
4. Duplicate SM names in a bundle, where `SuperMetricCrossRefError` gives rc 1 and nothing imported.
5. A mis-cased column token (W3).
6. `sync_all_bundles` continuing past a bundle that fails the preflight and returning 1.

**Fix:** add these cases.

### NIT

**N1. `src/vcfcf_dashboards/cli.py:571` and `:719`.** The `getattr(args,
"supermetrics_dir", "supermetrics")` fallback and the `_run_dep_walker(...,
supermetrics_dir="supermetrics")` default are still the pre-layout-v3 path. The
new preflight at `:471` and `:668` uses `content/supermetrics`. A Namespace without the
attribute makes the two phases read different directories. **Fix:** use one
default, `content/supermetrics`, in all four places, and do not describe the walker hunk as
a behaviour fix in the PR body (see "Walker name map" above).

**N2 (follow-up issue, outside the changed functions).**
`extract_refs_from_views` (`src/vcfcf_core/common/dep_walker.py:280`) classifies a
`supermetric:"<name>"` column as an **OOTB MetricRef**, not an SmRef. The
post-import walker therefore never checks or enables the 19 name-form SM columns in
`content/views`, and it sends a describe lookup for a non-key, which is skipped as "not in
describe". This predates the branch, and the function is untouched. `supermetrics_used_by` now
recognises the name form, but the walker does not. File a follow-up issue.

## If shipped as-is

On the factory corpus and the three shipped bundles, operators see no change on a
clean sync, and a genuinely missing referent is now named before anything imports.
Three gaps remain where the gate checks nothing. A third_party sync with
`--supermetrics-dir` pointed at its project runs ungated behind a misleading "could not load" warning. A third_party
sync on the default dir runs ungated with no message at all. A view with a mis-cased `SuperMetric:"X"` column
also has its SM's referents left unchecked.
