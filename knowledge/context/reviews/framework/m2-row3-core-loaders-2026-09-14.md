# Framework review: M2 row 3, loaders, walker, describe reader, audit and zip assembly into vcfcf_core

Date: 2026-09-14. Reviewer: framework-reviewer. Branch
`feat/m2-row3-core-loaders` (six commits over main `fa23bcf`, head
`27f72ba`). Design: `knowledge/designs/tooling-core-carveout-v1.md` row 3
plus "Side item to fold in". Precedent: `m2-row2-core-dashboards-2026-09-14.md`.

Verdict: **APPROVE** (zero BLOCKING). Two WARNINGs and five NITs, all to be
fixed before the PR opens per CLAUDE.md step 9. Ownership is marked on each.

## What changed

- `git mv` (`a04d786`) of `common/dep_walker`, `common/provenance`,
  `packaging/{describe,audit,deps,loader}`, `supermetrics/{loader,reverse}`,
  `customgroups/loader`, `reports/{loader,render}` into `src/vcfcf_core/`.
- Split (`a6709e3`): core `provenance_from_path(path, repo_root)` requires
  the root; core `DescribeCache(cache_dir)` requires the directory and gains
  `invalidate()`; core `load_bundle` takes `repo_root`, `report_views_dir`,
  `report_dashboards_dir`, `on_missing_id`, `provenance_of`; the SM, custom
  group and report loaders take their directories as required arguments and
  minting / provenance as callbacks; core `sm_id_map(None)` is an empty map.
  Factory wrappers keep every old signature and default (`vcfcf_common.
  provenance` sniffs the root, `vcfcf_packaging.loader` sniffs the root and
  resolves reports against `content/views` under the cwd, `vcfcf_packaging.
  describe.DescribeCache` subclasses core with the repo cache dir and the
  live `refresh`, `vcfcf_packaging.audit.run_dependency_audit` stays,
  `vcfcf_supermetrics.loader.sm_id_map()` keeps the cwd scan). `deps`,
  `reverse`, `reports/render` are `sys.modules` aliases; the rest are
  `__getattr__` wrappers.
- `vcfcf_common/__init__` imports nothing eagerly; `.env`, profile CLI and
  client names resolve through module `__getattr__`.
- New `vcfcf_core/packaging/assembly.py` (`c861cab`): payload rendering,
  inner zips, `bundle.json`, `render_vcfops_manifest`, outer zip layout;
  `builder.py` and `discrete_builder.py` call it and re-export the old names.
- Side item (`5badd6e`): `refresh()` skips the write when only the two
  `fetched_at` stamps would change.
- Buildkit copies core `sm_loader.py` / `reports_loader.py` /
  `reports_render.py`, drops the kit `provenance.py` and its rewrite rule.

## Checks re-run (independently, from the worktree)

| Check | Result |
|---|---|
| Full suite `-n auto --dist=loadgroup -m ""`, adapter clones reachable via a scratch symlink (removed afterwards) | **1955 passed, 8 skipped** (54 s), as claimed |
| `tests/test_core_contract.py` | 93 passed; `ALLOWLIST` empty; both new AST rules fire on their `_VIOLATION_SAMPLES` and the clean-module sample still passes |
| Validate chain (supermetrics, dashboards, customgroups, symptoms, alerts, reports, managementpacks, packaging) | all exit 0, tree clean afterwards (no ids minted) |
| Byte identity, `build --all --no-live-describe`, `PYTHONHASHSEED=0`, branch vs `git archive main` export | `storage-path-monitoring` 12/12, `vcf-license-consumption-overview` 19/19, `vks-core-consumption-bundle` 22/22 members (nested zips walked); every member byte-equal except `vcfops_manifest.json` (`built_at` only; key order identical; text equal once `built_at` is masked) and the nested `Views.zip` / `Dashboard.zip` / `Reports.zip` containers, whose entries are all byte-equal (zip entry timestamps differ, as they do between any two builds) |
| Discrete zip, `build-discrete dashboard "[VCF Content Factory] VKS Core Consumption"` on both sides | 19/19 members, only `built_at` differs, manifest key order `bundle_name, item_type, item_name, item_version, template_version, built_at` on both. (My first pick, "Fleet Capacity & Rightsizing", fails the audit identically on main and branch: no describe cache for VMWARE:Datastore, pre-existing) |
| Standalone content-import zip (`python3 -m vcfcf_dashboards package`, the 00d3382 path) | 9/9 members, identical apart from the `<time_ns>L.v1` marker name |
| `vcfops_manifest.json` consumer | `cli.py:526-532` (`check-staleness`) reads `vcfops_manifest.json` from the zip and compares `template_version`; the shipped installer templates do not read it. Format, key order and `indent=2` are unchanged |
| `CURRENT_TEMPLATE_VERSION` | unchanged (`2026-08-29-1`); no bump is warranted because the zips are byte-identical |
| Describe merge semantics (PR #155) | `_merge_section`, `_host_of`, `_is_instance_local`, `MergeStats`, `_counts`, `_summarize` move verbatim to core; `refresh()` body in the wrapper is the main body plus the skip and `self.invalidate(...)` in place of the two `pop`s. All pre-existing `test_describe_cache_merge.py` cases pass (retain absent keys, `--prune` only removal, `merged_from` refresh entry, `Super Metric|` never imported, corrupt-file recovery) |
| Side-item test read for tautology | `TestRefreshSkipsTimestampOnlyRewrites`: first refresh writes (new `merged_from` entry), second and third are proven no-ops on bytes **and** `st_mtime_ns`, an added key and a `default_monitored` flip are each proven to write, the in-memory layer is proven invalidated on the no-op path, and `_same_but_fetched_at` is unit-tested on nested `merged_from` stamps. Not tautological |
| `vcfcf_common` lazy init | no module-level side effects in `_env.py` / `_profile_cli.py`; `client.py` and `_profile_cli.py` import from `._env` directly; `doctor.py` imports nothing from `vcfcf_common`; no `from vcfcf_common import <name>` in `src/`, `scripts/`, `.claude/`; tests only import submodules (`_env`, `setup_credentials`, `doctor`). `.env` loading order is unchanged for every CLI (they import `_profile_cli` / `_env` submodules) |
| Kit run with the factory absent (`env -i`, cwd `/tmp`, `PYTHONPATH` = kit parent, reference pak `vcfcf_sdk_compliance.1.0.0.49.pak`) | imports `sdk_buildkit.{sm_loader,reports_loader,reports_render,dashboard_loader,dashboard_render,alerts_loader,alerts_render,symptoms_loader,sm_crossref,sdk_builder,sdk_project,pak_compare,docs_gen}`; no `vcfcf_*` in `sys.modules`; `sm_loader.sm_id_map(None) == {}`; an SM YAML with no `id:` raises `SuperMetricValidationError: ... missing id (a uuid4); pass on_missing_id= to mint one` and the file is untouched; kit `sdk_builder` imports `from .sm_loader import sm_id_map` (4 sites) |
| Kit members branch vs main | 57 to 56; only `provenance.py` dropped; only `sm_loader.py` and `reports_loader.py` differ; no `import`-bearing reference to `provenance` remains in any kit `.py` |
| "All six managed paks carry ids" | true (Python walk, filenames with spaces handled): compliance 1 view / 1 dashboard, vcommunity 37 SM / 96 views / 12 dashboards, vcommunity-os 1 view, vcommunity-vsphere 37 SM / 11 reports / 109 views / 12 dashboards, all with `id:` on line 1; synology and unifi bundle none |
| Silent-downgrade hunt (brief item 1) | every factory caller of a moved name still imports the wrapper path: `extractor.py:1596,1782` (`DescribeCache()` default cache dir), `:971-972,2271,2360` (audit/deps aliases), `composer.py:235-237,486`, `readme_gen.py:155,197,239` (explicit dirs), `project.py:455`, `syncer.py:134,222,277`, `cli.py:187,299,344,387`, `sdk_builder.py:953,1007,1058,1949,2201,3337`; `release_builder.py` imports only `.releases` / `.release_types`. Nothing outside the wrappers, aliases, `assembly.py`, `builder.py`, `discrete_builder.py` and `buildkit.py` imports `vcfcf_core` directly (grep). Provenance from a foreign cwd still classifies `content/` as `factory` and `third_party/idps-planner` as `idps-planner` (seams test, re-run). No test in the tree monkeypatches a served core name on a wrapper; the one `describe_mod` patch (`test_release_audit_default_and_this_refs.py:109`) targets `make_cache`, which the wrapper owns and `run_dependency_audit` imports at call time, so it still reaches the running audit |
| Callers of the changed core signatures | `load_sm` / `load_view` / `load_dashboard` / `load_cg` / `load_report` inside core `load_bundle` all pass the callbacks and report dirs; `sdk_builder.py:1007-1016` passes `views_dir` / `dashboards_dir` explicitly (already did, for the adapter layout), so the kit's now-required report dirs are supplied |
| Contract rules vs the pattern tooling named (brief item 6) | `_static_findings` on a probe module with `def load_dir(directory="alerts")`, `"recommendations"`, `"symptoms"`, `Path("alerts")`, `Path("symptoms")` returns **no findings**, and on the real `src/vcfcf_core/alerts/loader.py` and `symptoms/loader.py` returns none. See W1 |
| Em-dashes | zero in any line the branch adds that is not verbatim on main (35 added lines carry one; all 35 exist byte-for-byte in the main versions of the moved files) |
| Doc paths commit `27f72ba` | seven live docs re-pointed to the core paths; two orchestrator-owned files missed, see N4 |
| Worktree | clean after every check; the scratch `content/sdk-adapters` symlink was removed |

## Findings

### WARNING

1. **Cwd-relative directory defaults survive in core, and the contract does
   not see them** (dimension 1, the design's named row-1/row-3 leak class:
   "loaders default to `content/...` directories; become required").
   `src/vcfcf_core/alerts/loader.py:459` `load_recommendations(directory=
   "recommendations")`, `:590` `load_dir(directory="alerts")`, and
   `src/vcfcf_core/symptoms/loader.py:328` `load_dir(directory="symptoms")`
   are bare cwd-relative names in the library. No factory path is affected
   (every `src/` caller passes a directory; the CLIs pass `DEFAULT_DIR`), so
   this is not a regression on any output path, but a library consumer that
   calls `load_dir()` gets whatever the working directory holds, which is
   the row-2 renderer scan in a new coat. `tests/test_core_contract.py:61-62`
   only flags defaults under `content/`, `knowledge/`, `dist` or exactly
   `content|knowledge|supermetrics|views|dashboards|bundles`, so these three
   (and any future `"reports"`, `"customgroups"`, `"symptoms"` default)
   pass; proven above with a probe module and with the real files. Owner:
   tooling, this branch. Fix: (a) make `directory` required on the three
   functions (the factory wrappers `vcfcf_alerts.loader` /
   `vcfcf_symptoms.loader` keep the old defaults, as the row-3 wrappers do;
   check `src/vcfcf_alerts/cli.py:26,31` and `src/vcfcf_symptoms/cli.py:19,
   24` still pass through); (b) tighten the rule so it does not depend on a
   word list: flag any string default on a parameter named `directory` or
   ending in `_dir` / `_root` / `_path`, and add one `_VIOLATION_SAMPLES`
   entry (`def load_dir(directory="alerts")`) plus one clean sample (a
   non-path parameter with a string default) so the rule is self-checked
   like the others.

2. **The stale-zip signal does not name the file the zip layout now lives
   in** (dimension 9; row-2 W2 class, "the signal names an alias").
   `CLAUDE.md:314-319` and `.claude/agents/framework-reviewer.md:180-184`
   trigger the content-packager rebuild on `templates/`, `builder.py`,
   `discrete_builder.py`, `release_builder.py`, `render.py`. After this
   branch the member order, `bundle.json`, the inner zips and
   `render_vcfops_manifest` are in `src/vcfcf_core/packaging/assembly.py`,
   which neither list names; a future assembly change would ship without
   the rebuild prompt. Owner: orchestrator (both files are outside `src/`).
   Fix: add `src/vcfcf_core/packaging/assembly.py` to both lists. Related,
   for the PR body (orchestrator): the branch touches `builder.py` and
   `discrete_builder.py`, so the rule applies literally; the byte-identity
   proof above is why no rebuild and no `CURRENT_TEMPLATE_VERSION` bump is
   warranted, and the PR body should say so in one line so the exception is
   taken visibly (row-2 N6, same shape).

### NIT

3. **`tests/test_core_row3_seams.py:481-484`** (dimension 10). The last
   assertion of `test_buildkit_copies_the_core_loaders_not_the_wrappers`
   strips the substrings `vcfcf_common.dep_walker` and
   `vcfcf_common.provenance` from each kit source before asserting
   `"vcfcf_common" not in ...`, so a re-introduced
   `from vcfcf_common.provenance import provenance_from_path` in a core
   loader would pass this test (the line becomes `from  import ...`). The
   contract test's non-core-import rule is the real guard, so nothing is
   unprotected, but the seam test claims more than it checks. Owner:
   tooling. Fix: assert on import-bearing lines only, e.g. no line matching
   `^\s*(from|import)\s+vcfcf_common`, and drop the two `replace` calls.

4. **Docs that describe current architecture by the old file path.**
   Orchestrator-owned (outside `src/` and `knowledge/context/`):
   `.claude/skills/vcfops-supermetric-dsl/SKILL.md:211` ("The loader
   (`src/vcfcf_supermetrics/loader.py`) enforces a subset of ..." is now
   `src/vcfcf_core/supermetrics/loader.py`) and
   `.claude/agents/customgroup-author.md:25` (the YAML-schema docstring is
   now on `src/vcfcf_core/customgroups/loader.py`). Also mark row 3 of
   `knowledge/designs/tooling-core-carveout-v1.md:74` done with the PR
   number, as rows 1 and 2 are. Tooling-owned: none left; `27f72ba` covered
   the `knowledge/context/` and `src/vcfcf_extractor/README.md` references,
   and no live doc still describes the kit's `provenance.py` or the eager
   `vcfcf_common` import.

5. **`src/vcfcf_managementpacks/sdk_builder.py:1824-1826, 1962-1963`**: the
   comments say that with `sm_scope=None` `sm_id_map` "falls back to its
   unscoped mode (scanning the full supermetrics/ dir)". True in the
   factory (wrapper), false in the kit since this branch, where the same
   file is shipped verbatim next to the core `sm_loader.py` whose
   `sm_id_map(None)` is `{}` (proven above). `buildkit.py:64-70` states
   the kit delta; the comment at the call site contradicts it for a reader
   of the kit. Owner: tooling. Fix: one clause per comment, "in the
   factory; the kit's core copy returns an empty map and a view naming an
   SM then fails the build".

6. **`src/vcfcf_packaging/audit.py:74`**: `getattr(describe_cache,
   "_client", None) is not None` replaces `describe_cache._client is not
   None`. Fine on its own (a bare core `DescribeCache` has no `_client`),
   but the docstring of `run_dependency_audit` still says the cache comes
   from `make_cache`, which always returns the factory subclass; if the
   `getattr` is meant to admit a core cache passed by a future caller, say
   so in one comment line, otherwise restore the attribute access so a
   wrapper/core mismatch is loud rather than silently offline. Owner:
   tooling.

7. **Carried from row 1 / row 2 (optional)**: the 35 moved-verbatim lines
   with em-dashes now sit in `src/vcfcf_common/dep_walker.py` (walk_and_check
   messages and comments) next to lines this branch rewrote. Exempt by the
   moved-verbatim rule; convert when that module is next touched. Owner:
   tooling.

## Claims verified as stated

Pure `git mv` for `a04d786`; wrappers keep every old signature and default
(`__defaults__` pinned by the seams tests and re-read here); core loaders
never write (`_resolve_id` raises with no callback, callback return is
validated); `sm_id_map(None)` is `{}` in core and the wrapper scans
`content/supermetrics` then `supermetrics` (seams tests, re-run);
`load_bundle` root sniff, report dirs, minting and provenance all on the
wrapper; describe merge helpers verbatim in core, `refresh` verbatim plus
the skip; `assembly.py` reads nothing from the repo (source-token test plus
my read: no `read_text`, clock, template dir, cache); manifest key order
and formatting identical on bundle and discrete paths; `vcfcf_common`
lazy; contract 93 with empty `ALLOWLIST` and the two new rules
self-checked; shims 46 and seams 30 pass inside the 1955; validate clean;
three bundles, the standalone zip and one discrete zip identical to main
apart from `built_at` / the marker name / nested zip entry timestamps; kit
57 to 56 with exactly the claimed deltas and no factory module reachable;
all six managed paks carry ids.

## If shipped as-is

Operators and downstream paks see no change: every zip, manifest and kit
artifact is byte-identical to main apart from timestamps, and every
factory CLI keeps its cwd conventions. The two warnings are about the
next change, not this one: a library consumer calling
`vcfcf_core.alerts.loader.load_dir()` scans its working directory with no
contract failure, and a future edit to `assembly.py` would ship without
the stale-zip rebuild prompt.

## Round 2 (2026-09-14, head `739ec91`)

Fix commits reviewed: `3dfac84` (tooling: W1, N3, N5, N6, N7) and `5e9b230`
(orchestrator: W2, N4, design row 3 marked done).

Verdict: **APPROVE** (zero BLOCKING). One NIT re-opened (N6, comment
accuracy only); fix before the PR opens per CLAUDE.md step 9.

### Finding-by-finding

| # | Status | Evidence |
|---|---|---|
| W1 | **Closed** | Core `alerts/loader.py:459,590` and `symptoms/loader.py:328` take `directory` with no default (`fn()` raises `TypeError`, pinned by `test_row3_w1_core_alert_and_symptom_loaders_require_a_directory`). New wrappers `src/vcfcf_alerts/loader.py` and `src/vcfcf_symptoms/loader.py` keep exactly main's defaults: `__defaults__ == ("alerts", True)`, `("recommendations", True)`, `("symptoms", True)`, keyword name `enforce_framework_prefix` preserved (compared against `git show main:` of the three signatures). Both wrappers moved from `SHIMS` to `WRAPPERS` in `test_core_shims.py` with identity checks on served names. Every factory caller passes a directory: `vcfcf_alerts/cli.py:26,31,60-61` (`DEFAULT_*_DIR`, `rec_dir`), `vcfcf_alerts/cli.py:48-49` (symptom dir), `vcfcf_symptoms/cli.py:19,24`, `readme_gen.py:218-223`, `discrete_builder.py:694-695`. The kit's `sdk_builder.py` imports only `load_file` / `load_recommendation_file` from the two loaders (`:971,989,1037`), so the kit copies of the core loaders need no default. No test monkeypatches a name on either wrapper (grep). `vcfcf_alerts validate` and `vcfcf_symptoms validate` exit 0. |
| W1 rule | **Closed, not tautological** | `tests/test_core_contract.py:181-191` `_is_path_param`: `directory` or suffix `_dir` / `_root` / `_path`; `:282-289` pairs defaults to parameter names for positional (tail-aligned), positional-only and kw-only args. Probed independently on `_static_findings`: fires on `load_dir(directory='reports')`, `def f(*, cache_root='x')`, `def h(directory: str = 'symptoms', enforce=True)`, and a positional-only `out_path='o'`; silent on `default_name_path='X'`, `out_path=None`, `mode='auto'`; zero findings on every real `src/vcfcf_core/**/*.py`. Three new `_VIOLATION_SAMPLES` and the extended clean sample are in the self-check. |
| `default_name_path` exemption | **Justified and narrow** | The only path-named parameters with a string default in core are `dashboards/loader.py:2457` and `:3125` (`default_name_path="VCF Content Factory"`), consumed at `:3110` as `name_path=name_path or default_name_path`: the VCF Ops folder on the wire, not a filesystem path. An AST walk over core with the suffixes `dir` / `root` / `path` (no underscore) finds nothing else. A one-name set, not a pattern. |
| W2 | **Closed** | `CLAUDE.md` and `.claude/agents/framework-reviewer.md` stale-zip lists now name `src/vcfcf_core/packaging/assembly.py` (diff of `5e9b230`). |
| N3 | **Closed** | `tests/test_core_row3_seams.py:481-488` asserts no line matches `^\s*(from|import)\s+vcfcf_common`, the two `replace` calls are gone, the failure message names the offending lines. A re-introduced `from vcfcf_common.provenance import ...` in a copied core loader now fails the seam test, not just the contract. |
| N4 | **Closed** | `.claude/skills/vcfops-supermetric-dsl/SKILL.md` and `.claude/agents/customgroup-author.md` name the core loader paths; `knowledge/designs/tooling-core-carveout-v1.md` row 3 marked done (PR pending). |
| N5 | **Closed** | `sdk_builder.py:1824-1827, 1964-1967` now say the kit's core copy returns an empty map and an unbundled SM reference fails the build there. Matches the kit behavior proven in round 1. |
| N6 | **Re-opened (NIT)** | `src/vcfcf_packaging/audit.py:73-76` says "`make_cache()` is patched in tests to return a core `DescribeCache` (no `_client` attribute at all)". Not true of the tree: every `make_cache` patch (`test_release_audit_default_and_this_refs.py:109-114,268-271`, `test_discrete_builder_builtin_metric_enables.py:248-252,277,316`, `test_view_time_segment_column.py:238-240`) returns the factory subclass `describe_mod.DescribeCache(cache_dir=..., client=None)`, which sets `_client = None`; `test_describe_cache_merge.py:274-275` returns a `MagicMock` with `_client` set. No test hands the audit a core cache. The `getattr` is fine; the reason written for it is a claim the tests do not back (rule 11). Fix: one honest line, e.g. "a core `vcfcf_core.packaging.describe.DescribeCache` has no `_client`; a library caller passing one gets the offline audit rather than an `AttributeError`; every factory path goes through `make_cache`, whose subclass always carries `_client`". |
| N7 | **Closed** | Nine em-dashes in `src/vcfcf_common/dep_walker.py` converted. Across `main..HEAD`, 35 added lines still carry an em-dash and all 35 exist byte-for-byte on main (binary-safe comparison against every `main:` blob under `src`, `tests`, `.claude`, `CLAUDE.md`, `knowledge`); the three post-round-1 commits add zero. |

### Checks re-run (round 2)

| Check | Result |
|---|---|
| `test_core_contract.py` + `test_core_shims.py` + `test_core_row3_seams.py` | 174 passed, 1 skipped (same skip as round 1) |
| Full suite, `-n auto --dist=loadgroup -m ""`, adapter clones reachable via a scratch `content/sdk-adapters` symlink (removed afterwards) | **1961 passed, 8 skipped** (44 s); 1955 in round 1 plus the six new W1 cases |
| Validate chain (supermetrics, dashboards, customgroups, symptoms, alerts, reports, managementpacks, packaging) | all exit 0 (packaging needs the adapter clones, as in round 1: it fails on the missing `content/sdk-adapters/synology/adapter.yaml` without the symlink, which is the pre-existing gitignore situation, not this branch) |
| Worktree | clean after every check, symlink removed |

### If shipped as-is

Unchanged from round 1 for operators and downstream paks. A library
consumer calling `vcfcf_core.alerts.loader.load_dir()` or
`vcfcf_core.symptoms.loader.load_dir()` now gets a `TypeError` instead of
a silent cwd scan, and the contract rule catches the next such default
without a word list. The one open item is a comment that gives a reason the
test suite does not support; no behavior rides on it.
