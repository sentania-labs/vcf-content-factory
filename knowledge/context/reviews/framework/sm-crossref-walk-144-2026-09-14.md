# Framework review: SM-to-SM @supermetric walk in collect_deps (issue #144)

- Date: 2026-09-14
- Reviewer: framework-reviewer (read-only)
- Branch: `fix/144-sm-crossref-walk`, commit `018143c`, diffed against `main`
- Worktree: `.claude/worktrees/agent-abcb0c823c90fd454`
- Area: `src/vcfops_common/dep_walker.py`, `src/vcfops_packaging/discrete_builder.py`, `tests/test_dep_walker_sm_crossref.py`

## Verdict: APPROVE

0 BLOCKING / 3 WARNING / 3 NIT

## What changed

`collect_deps` gains step 2c: after view-column and widget `sm_<uuid>` refs are collected, each collected SM's formula is walked for `@supermetric:"<name>"` tokens (via `vcfops_supermetrics.crossref.crossref_names`, so issue #148 semantics are inherited) to a fixed point. Referents go through the existing `_collect_sm_uuid`, so the existing scope check applies to them. A missing referent or an id-less referent is a `DepGraph.errors` entry, and the walk continues. New public `expand_sm_crossrefs(sms, all_sms)` runs the same walk for callers that start from an SM or view. `discrete_builder._expand_sm_crossrefs` is now a thin adapter that raises `DiscreteBuilderError` on any error string, and the discrete dashboard path uses `dep_graph.supermetrics` directly instead of expanding a second time.

## Checks re-run (independently)

| Check | Result |
|---|---|
| `tests/test_dep_walker_sm_crossref.py` (worktree) | 13 passed |
| Full suite, main checkout (has pak clones) | 1513 passed, 4 skipped, 129 deselected |
| Full suite, worktree | 1511 passed, 6 failed, 13 skipped |
| Cause of the 6 worktree failures | All six assert on the real repo and fail on `artifact source not found: 'content/sdk-adapters/synology/adapter.yaml'`; the worktree has no managed-pak clones. Same tests pass on the main checkout at the same code. Environmental, not the change. |
| Validate chain (7 packages + `vcfops_packaging validate`), worktree | all rc=0 |
| Validate chain, main checkout with clones | all rc=0 |
| Render regression | n/a (no renderer touched) |
| pak-compare | n/a (no pak builder touched) |

Tooling's claims all held: chain, cycle, missing referent, id-less referent, and token-case/name-case behavior verified by the new tests and by my own probe (`Super Metric|@SUPERMETRIC:'B'`, single-quoted, prefixed, upper-cased token resolves to `B`).

## Hunt list from the brief

1. **Live-sync caller of `collect_deps` whose behavior changes.** None exists. `collect_deps` callers are `vcfops_packaging/composer.py:275` (errors only, `project_scope=None`), `vcfops_packaging/project.py:495` (errors only, scope check inside `validate`), and `discrete_builder.py:490` (dashboard artifact contents, which were already expanded on `main` by the removed `_expand_sm_crossrefs` call, so the zip content is unchanged). The live sync paths (`vcfops_supermetrics/cli.py:_run_dep_walker_for_sms`, `vcfops_dashboards/cli.py:_run_dep_walker`) use `walk_and_check`, which does not call `collect_deps`. Nothing syncs or enables more than before. See WARNING 1 for the flip side.
2. **Scope check on referents.** Referents pass through `_collect_sm_uuid`, so `_scope_allows` applies with identical semantics: same-project accepted, cross-linked factory SM accepted (probe case 2), non-cross-linked factory SM rejected (case 1), other-project SM rejected (case 3), empty provenance passes through. Matches the module docstring's "Project-scope semantics".
3. **Extractor skip list.** `--skip-supermetric` lives on `vcfops_extractor` (live-to-YAML pull); the extractor has its own UUID queue (`extractor.py:2075`) and never calls `collect_deps` or `expand_sm_crossrefs`. Not applicable to this walk; no divergence introduced.
4. **Double expansion on view / report paths.** View path: `_expand_sm_crossrefs(_resolve_view_deps(...))` once. Report path: `_resolve_report_deps` does UUID-only resolution, then one `_expand_sm_crossrefs`. Dashboard path: `collect_deps` only. Clean. (Double expansion would be idempotent anyway, given the seen-set.)
5. **Out-of-scope referent, does the error name the referrer?** No. See WARNING 2.

## Regression anchors

- `00d3382` (pak-local default leaking global): not applicable; no renderer default, coordinate, or flag touched. The only global-path effect is `validate` now seeing referents in the third-party scope check, which is the intended behavior and the corpus is green.
- `6c59f6b` (key derivation collision): not applicable; no key or label derivation. The one name-keyed lookup (`sm_by_name`) is discussed as NIT 1.

## Findings

### WARNING

**W1. Issue #144's stated operator impact (live-sync advisory) is not addressed by this diff.**
`src/vcfops_common/dep_walker.py:229` `extract_refs_from_supermetrics` still only recognises `attribute=sm_<uuid>` inside `${...}`; it returns no `SmRef` for `@supermetric:"<name>"` (probe: `extract_refs_from_supermetrics([A])` returned `[]` for a formula whose only term is a crossref). `walk_and_check` is what `vcfops_supermetrics sync` and `vcfops_dashboards sync` run, and neither path calls `collect_deps` or `expand_sm_crossrefs`. The issue body says: "Remaining impact is the live-sync dependency advisories: syncing a super metric that references another one will not advise that the referent is also needed... the advisory should name the missing referent up front." That sentence is still true after this change. The title of #144 ("collect_deps does not walk...") is met; the motivating symptom is not.
Authority: issue #144 body; `dep_walker.py` module docstring, which names `walk_and_check` as the online path that "checks the current policy XML and enables any SM".
Not BLOCKING: nothing regresses, and the resolver in `vcfops_supermetrics/client.py:601` still hard-errors (with the remote `find_by_name` fallback) rather than shipping a bad formula.
Fix (either): (a) in `extract_refs_from_supermetrics`, also emit an `SmRef(name=<ref_name>, sm_id=sm_name_map.get(name) or "")` per `crossref_names(formula)` so `walk_and_check` can report "SM 'A' formula references 'B' which is not in this sync batch" (needs the name map that `_run_dep_walker_for_sms` already builds); or (b) do not close #144 with this PR, mark it partial, and open a follow-up for the `walk_and_check` side. The PR body must not claim the live-sync advisory is fixed.

**W2. A scope-rejected referent is reported without the referring SM, and once per referrer.**
`src/vcfops_common/dep_walker.py:744-753`: the scope branch of `_collect_sm_uuid` appends `_scope_allows(...)`'s string and discards `source`. Probe output for a project-scoped dashboard whose SM `A` and SM `C` both reference factory SM `B` (not cross-linked):
```
scope violation: 'B' has provenance 'factory' but is not listed in cross_links for project 'proj'. ...
scope violation: 'B' has provenance 'factory' but is not listed in cross_links for project 'proj'. ...
```
`project.py:check_third_party_scope` prefixes this with the dashboard name only. An operator running `validate` sees a dashboard and an SM name and has to grep formulas to learn that `B` arrived via `A`'s formula, not via a view column. Every other error the walker emits in step 2 carries its source (`view '<v>' col '<c>' references ...`, `super metric '<a>': formula references ...`); the scope error is the one message in this new path that does not.
Authority: `collect_deps` docstring ("Missing deps are recorded as errors ... so callers see the full error list in one pass") and the module's own source-naming convention; issue #144 ("should name the missing referent up front"). Pre-existing for view-column refs, but the crossref walk is the case where the referrer is the only useful pointer.
Fix: in `_collect_sm_uuid`, append `f"{source}: {err}"` in the scope branch (the view-column callers already pass a `source`), and dedupe by `(sm_uuid, source)` or record rejected UUIDs so the second referrer does not repeat the same line. Add one test: scoped referent, assert the referrer name is in the message.

**W3. Stale-zip discipline: `discrete_builder.py` is on the CLAUDE.md "After tooling changes" list.**
CLAUDE.md, "After tooling changes": touching `discrete_builder.py` means all distribution zips are stale and a full `content-packager` rebuild of every manifest in `bundles/` is "Not optional". Tooling's result block (as relayed) does not flag it. Output for the existing corpus is byte-for-byte the same logic (the dashboard path was already expanded on `main`; the SM/view/report paths return the same list from the same walk), so **no `CURRENT_TEMPLATE_VERSION` bump is required**: `template_version.py` scopes the bump to "output structure changes", and there is none. The rebuild itself is still the rule.
Fix: orchestrator schedules the `content-packager` rebuild after merge; PR body notes it.

### NIT

**N1. `sm_by_name` is last-wins on duplicate display names.** `dep_walker.py:757` and `expand_sm_crossrefs` (`by_name = {sm.name: sm for sm in all_sms}`): with a third-party SM and a factory SM sharing a name, the factory one (loaded last, `_load_all_sms` prepends `extra_search_dirs`) is the one resolved; under scope it is then rejected and the same-project SM is never considered (probe case 4). Third-party content loads with `enforce_framework_prefix=False`, so RULE-006 does not rule this out. Pre-existing for the view-column name path, and consistent with emit-time `sm_name_to_uuid_map` (also last-wins), so the walk and the resolver at least agree. Worth a lesson or a loud duplicate-name error in a follow-up, not this PR.

**N2. Test coverage gaps.** No test exercises the scope check on a crossref referent (cross-linked accepted, non-cross-linked rejected), and no test runs `build_discrete("dashboard", ...)` end to end to prove the dashboard path still carries referents after the second expansion was removed. The removed call was the only thing that made that path work on `main`; the new behavior is covered only indirectly through `collect_deps` unit tests. One integration test on a synthetic corpus would close it.

**N3. Docstring drift.** `_walk_sm_crossrefs` docstring says "Token semantics come from `SM_CROSSREF_RE`"; the code imports `crossref_names`. Same thing, but name the function that is actually called.

## If shipped as-is

Discrete builds and `validate` behave as they do today plus referent scope coverage; the live-sync advisory gap described in #144 remains, so an operator syncing an SM whose referent is not on the target still gets the resolver's hard error rather than an up-front advisory. No corruption, no silent drift.

## Independence note

No file under `src/` or `tests/` was modified by this review. Probe scripts live in the session scratchpad only.

---

# Round 2: follow-up commit `57cf2f0`

- Date: 2026-09-14
- Scope: only `57cf2f0` on `fix/144-sm-crossref-walk` (diff `018143c..57cf2f0`), `src/vcfops_common/dep_walker.py` and `tests/test_dep_walker_sm_crossref.py`. Worktree now has the six managed-pak clones.

## Verdict: APPROVE

0 BLOCKING / 2 WARNING / 1 NIT

## Checks re-run

| Check | Result |
|---|---|
| Full suite, worktree with clones | 1532 passed, 0 failed, 7 skipped, 130 deselected (matches the claim) |
| `tests/test_dep_walker_sm_crossref.py` default run | 22 passed, 1 deselected (the `slow` `build_discrete` end-to-end test) |
| Same file with `-m "slow or not slow"` | 23 passed (the claim of 23 holds once the slow marker is included) |
| Validate chain | unchanged from round 1 (no loader/renderer touched in this commit; not re-run) |

## Round 1 findings, disposition

- W1 (live-sync advisory): addressed in code (see below for how far the wiring carries it).
- W2 (scope error names referrer, deduped): closed. Probe: A referencing B twice and C once, plus a view column referencing B, yields exactly three lines: `view 'V' col 'Bcol': scope violation: 'B' ...`, `super metric 'A': scope violation: 'B' ...`, `super metric 'A': scope violation: 'C' ...`. The `(uuid, source)` dedupe collapses only the duplicate token inside one formula; a second referrer or a second referent is still its own line. Does not hide a distinct violation.
- W3 (stale-zip rebuild): still the orchestrator's action after merge; nothing in this commit changes that.
- N1 (last-wins name map): deferred, as agreed.
- N2 (tests): closed; scoped-referent tests and a `build_discrete("dashboard")` end-to-end test added.
- N3 (docstring): closed.

## Coordinator's verification list

1. **Lookup cached per name, no fan-out.** `walk_and_check` Phase 1b keys `_remote_by_name` on the referent name and looks up once per unresolved name across the whole batch. Probe: three SMs referencing `X` (four token occurrences) and `Y` (two occurrences) produced exactly two `find_by_name` calls, `['X', 'Y']`. Confirmed.
2. **Exception from `find_by_name`.** `_lookup_sm_uuid_on_target` catches `Exception`, records `ERROR lookup of super metric '<name>' on target failed: <e>`, returns `None`, and the loop continues to the next name (probe: `Y` was still looked up after `X` raised). Not swallowed, not aborting. But see WARNING R2-1: the `None` return is then indistinguishable from "absent", so a second ERROR follows claiming the name is not on the target.
3. **Auto-enable of a target-only referent.** Once resolved, the ref carries `sm_id` and enters the pre-existing `sm_by_uuid` dedupe and Phase 2 loop unchanged: enabled already, in the sync batch, or "SM not enabled, enabling" via the existing `_get_sm_resource_kinds` + `_enable_sm` helpers. Probe with a fake client returning a target-only UUID and `enabled=False` took the existing enable branch and the existing post-inject verification. No new enable path; identical treatment to a view-column `sm_<uuid>` reference to a pre-existing SM.
4. **Scope dedupe.** Covered above under W2: `(uuid, source)` only collapses the same referent named twice by the same referrer.
5. **`find_by_name` contract.** Exact-name match; raises `VCFOpsError` on more than one match rather than guessing (client.py:83). The walker's catch turns that ambiguity into a recorded ERROR, which is the correct direction (never bind to a UUID nobody chose).

## Findings

### WARNING

**R2-1. A failed lookup is reported twice, and the second line makes a false claim.**
`dep_walker.py` `_lookup_sm_uuid_on_target` returns `None` both for "not on target" and for "lookup raised"; Phase 1b then treats `None` as absent and emits `... but no super metric with that name is in this sync batch, in the repo SM YAML, or on the target instance.` Probe with a raising client:
```
ERROR lookup of super metric 'X' on target failed: boom
ERROR SM 'A' formula references @supermetric:"X" but no super metric with that name is ... on the target instance. ...
```
The second line is not true (the target was never successfully asked) and its remediation ("Sync that super metric first, or fix the name in the formula") sends the operator to fix a name that may be fine. rc=1 either way, so no silent pass; this is a misleading message, not a missed error.
Authority: user rule 11 (evidence over labels: "record unresolved rather than plausible"); `walk_and_check` docstring ("Fails closed if the endpoint is unreachable" is the stated posture for describe, and the same posture should read as "unreachable", not "missing").
Fix: return a sentinel (or a `(uid, failed)` tuple) from `_lookup_sm_uuid_on_target`, and in Phase 1b skip the "missing" message when the lookup failed; the "lookup failed" line already carries the error and the exit code.

**R2-2. The "advise up front" claim does not hold for `vcfops_supermetrics sync` as wired.**
`src/vcfops_supermetrics/cli.py:cmd_sync` calls `client.import_supermetrics_bundle(bundle)` first (client.py:601 resolves every `@supermetric` token there and raises `VCFOpsError` on an unresolvable name, with the same `find_by_name` fallback), and only then `_run_dep_walker_for_sms`. So on that CLI the new "missing referent" DEP-ERROR is unreachable: an unresolvable name still fails at push, before the walker runs, exactly as the issue describes. `vcfops_dashboards sync` passes `supermetrics=[]`, so Phase 1b never sees a formula there. The real gain from this commit on the CLIs is the target-resolved referent now being policy-checked and enabled after import, which is worth having, but the commit message's "advise up front instead of failing at push" describes `walk_and_check` in isolation, not the operator experience.
Authority: issue #144 body ("the advisory should name the missing referent up front"); user rule 8 (done means seen working, not the unit test passing).
Fix (either): run the referent resolution (Phase 1b, or a cheap pre-import call to `extract_refs_from_supermetrics` + `find_by_name`) before `import_supermetrics_bundle` in `cmd_sync`, so the DEP-ERROR is what the operator sees; or state in the PR body that the up-front advisory is reachable for library callers only and file the CLI ordering as a follow-up. Not BLOCKING: nothing regresses, the push-time hard error still protects the instance.

### NIT

**R2-N1.** The missing-referent ERROR is emitted once per token occurrence, not per `(referrer, name)`: a formula naming `X` twice prints the same line twice (probe output above). Dedupe on `(ref.source, ref.name)` before emitting, the same way the scope path now does.

## If shipped as-is

Operators syncing an SM whose referent already exists on the target get it policy-checked and enabled, which they did not before. An unresolvable referent still fails at push on `vcfops_supermetrics sync` (unchanged), and a target lookup failure prints one accurate and one misleading DEP-ERROR. No corruption, no silent drift, rc is correct in every probed case.

---

# Round 3: follow-up commit `dc5e517`

- Date: 2026-09-14
- Scope: only `dc5e517` (`_LOOKUP_FAILED` sentinel; missing-referent ERROR deduped on `(source, name)`; two tests). R2-2 (CLI ordering) is filed as issue #154 and is out of this branch.

## Verdict: APPROVE

0 BLOCKING / 0 WARNING / 0 NIT

## Checks re-run

| Check | Result |
|---|---|
| Full suite, worktree with clones | 1534 passed, 0 failed, 7 skipped, 130 deselected (matches the claim) |
| `tests/test_dep_walker_sm_crossref.py` with `-m "slow or not slow"` | 25 passed |

## Sentinel containment, verified by probe

Client whose `find_by_name` raises for `X` and returns `None` for `Y`; one SM referencing `X` twice and `Y` once; `get_supermetric` instrumented to fail the run if the enable path is reached.

- Messages: exactly one `ERROR lookup of super metric 'X' on target failed: boom`, exactly one missing-referent ERROR for `Y`, nothing else. R2-1 and R2-N1 closed.
- `_remote_by_name` still caches per name (`['X', 'Y']`, two calls for three token occurrences).
- Phase 1b tests `uid is _LOOKUP_FAILED` before `if uid:`; that order matters because `object()` is truthy, and it is correct. `ref.sm_id` stays `""` on the failed path (all three refs' `sm_id` are `str`), so the later `if not ref.sm_id: continue` keeps the ref out of `sm_by_uuid`: zero policy exports, zero `verify_supermetrics_enabled` calls, enable path never entered. The sentinel is confined to the `_remote_by_name` dict and cannot reach `sm_id`, `_uuid_to_name`, or the enable helpers.
- `rc` remains 1 (`ok=False`) on a failed lookup, so a transport error or ambiguous name still stops the sync.

## If shipped as-is

Library and CLI callers get one accurate line per failed lookup and one per genuinely missing referent, with the same exit code as round 2. Open items outside this branch: #154 (walker runs after the import on `vcfops_supermetrics sync`), round 1 W3 (content-packager rebuild after merge, no template-version bump), round 1 N1 (last-wins duplicate names, follow-up).
