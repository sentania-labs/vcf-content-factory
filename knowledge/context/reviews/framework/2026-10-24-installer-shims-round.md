# Framework review: installer and shims round (#244, #200, #242, #159), 2026-10-24

Branch `fix/installer-200-244-242-shims-159` on `origin/main` (`8ad0911`):
`519129a` (#244), `78cf4ae` (#200), `3301554` (#242), `1b6e0d8` (#159), plus
the orchestrator sweep `dcd3388` (agent prompt, CLAUDE.md, STRUCTURE.md,
review script, buildkit notes; no `src/` or `tests/` change). Reviewed in
the worktree `.claude/worktrees/fix-installer-200-244-242-shims-159` with the
pak clones symlinked in; baselines built from `git archive` trees of
`origin/main` and `HEAD` in the session scratchpad.

**Verdict: CHANGES REQUESTED.** 2 BLOCKING, 4 WARNING, 7 NIT.

1. The #159 removal test fails on every existing clone after a pull,
   including the main checkout: git leaves the ignored `__pycache__/`
   directories in `src/vcfops_*/`, so `import vcfops_common` succeeds as
   an empty namespace package.
2. The #200 Summary repair rebinds a kind when it cannot read the
   current Summary tab's name. That breaks its own documented guarantee
   that it never touches a tab that is not a copy of the pak dashboard.

Everything else holds up: the shipped content is byte-identical, the
`install.py` classifier matches the core one, and the Java change is clean
on JDK 17.

## Re-run evidence

| Check | Result |
|---|---|
| CI pytest command (`-n auto --dist=loadgroup --override-ini="addopts=" -m ""`), clones linked | **2693 passed, 9 skipped**, exit 0 |
| New test files alone (`test_install_materialization`, `test_pak_summary_rebind`, `test_vcfops_names_removed`, `managementpacks/test_sdk_compat_target`) | 114 passed, 0 skipped (the real-javac `[removal]` gate ran) |
| Seven-package validate chain | all rc=0 |
| Render regression: `vcfcf_packaging build --all` plus every release manifest, `origin/main` vs `HEAD`, every zip and nested zip extracted and compared member by member (13 zips) | Content byte-identical. Only differences: `install.py`, `vcfops_manifest.json` (`template_version` `2026-09-25-1` to `2026-10-24-1`, `built_at`), and the README footers (`vcfops_packaging` to `vcfcf_packaging`). The synology and unifi pak-pointer releases fail identically on both sides (no pak clone in the archive tree) |
| `install.py` in the built zip | byte-identical to `src/vcfcf_packaging/templates/install.py` |
| Template version signal | bumped to `2026-10-24-1` with a history line. Old zips will report stale. **All dist zips are stale: a full `content-packager` rebuild is required** (templates and `builder.py` / `discrete_builder.py` touched) |
| Framework Java on JDK 17.0.20 (`-source 11 -target 11`, SDK 2.2 jar) | compiles. `-Xlint:deprecation,removal`: one warning, `setResourceStatus` at `VcfCfAdapter.java:2818`, which already exists on main (`:2798`). No `[removal]` warning |
| `CertificateReviewTest` | 95/95 |
| `VcfCfAdapterTest` | 78/79. The one failure is the manifest-stamp case, because my hand-built jar lacked `X-Vcfcf-Source-Commit`. A problem with my test setup, not the branch |
| Java 12+ API in the change | none. New calls: `Class.forName(...).getDeclaredConstructor().newInstance()`, `Thread.interrupted()`, `Thread.currentThread().interrupt()`, all Java 11 safe |
| JDK 25 compat pass | not re-run (no JDK 25 on this host). The author's claim of a pass on 9.1.1.0100 is unverified here |
| Em-dashes in added lines and in commit messages | 0 and 0 |
| `vcfops_` module names in live files | one: `reference/README.md:14` (N1). Everything else is dated records, the removal test, or the `vcfops_install_venv_` temp prefix |

## Verified safe

- **`install.py` classifier parity.** The template's `_mat_*` functions
  match `vcfcf_core.dashboards.materialization` line for line: same
  incomplete signal (`entryKeys` non-null or `importComplete is False`),
  same STALLED rule, same SETTLING to INCOMPLETE finalization, and the same
  four sentences, including the "adapter kinds could not be read" variant.
  The parity test covers ABSENT, an unreadable kinds list, upper-case ids,
  empty `entryKeys`, and the 8.18.7 License regression case. The export
  reader drops the `entries` merge the core one does, which the classifier
  never reads. Wait default, cap, and env override match
  `materialization_recheck_wait` across eight combinations.
- **Global / standalone import path.** Imported content does not change.
  The check runs after every bundle has imported, reads only (one
  `CUSTOM DASHBOARDS` export plus `GET /api/adapterkinds`), and any failure
  degrades to `MATERIALIZATION UNCHECKED` as a note, never a die. Only
  STALLED changes the exit code (joins the existing exit-2 warnings).
- **The 660 s wait applies only to bound paks.** `poll` and the 660 s
  default are set only when `read_pak_bindings` returns bindings. A pak
  with no `dashboards.properties` gets the 180 s single re-check, and only
  while a dashboard is still settling. STALLED and COMPLETE end the wait at
  once.
- **8.18 `isLoading` absence.** An entry without `isLoading` is excluded
  from the classifier and printed as `MATERIALIZATION UNCHECKED`, never
  complete (`post_install._records`). Its source state is then unknown, so
  `repair_summary_bindings` never rebinds it. The 8.18 feature check
  (`2026-10-23-compliance-8-18-feature-check.md`, row 4e) shows 8.18
  carries `isLoading` on the source and the template anyway.
- **Kinds the installer did not bind.** Only `dashboards.properties`
  entries are considered, parsed the way the installer parses them. An
  empty or `isDashboard: false` `getSummaryTabId` answer is left alone.
- **Exit codes.** Pak `install`: 0 / 1 (`_abort`) / 2 (argparse) / 3 (new),
  no collision, and `main()` returns `args.func(args)`. `install_pak`'s only
  caller is `cmd_install`. `--no-wait` skips the check.
- **#242.** `catch (VirtualMachineError)` plus `isThreadKill` by class name
  keeps the Java 17 rethrow, and the interrupt flag is restored before
  "no prompt". `AmbientCredential` changed only in its javadoc.
  `BUILDKIT_VERSION` is 1.0.16 with release notes. The `[removal]` gate
  covers only the framework-only pass, as documented.
- **Credentials.** Never printed. The post-install sessions use the same
  `localItem` / `Local` auth sources as the installer's own session
  (`installer.py:401`).

## BLOCKING

### B1. #159: the "old names fail" test, and the claim behind it, fail on every existing clone after a pull

`tests/test_vcfops_names_removed.py:37` and `:49`; the deletion of the
`src/vcfops_*/__init__.py` and `__main__.py` files.

Git deletes only tracked files. On any clone that ever ran a shim, the
gitignored `src/vcfops_*/__pycache__/` remains. The main checkout also has
an ignored `src/vcfops_packaging/templates/`. All ten directories exist
there today. A directory with no `__init__.py` imports as a **namespace
package**, so after the merge:

- `import vcfops_common` **succeeds** (an empty module, not
  `ModuleNotFoundError`). An old caller fails later with an
  `AttributeError`, not at the import line the test says is loud.
  `python3 -m vcfops_packaging` still fails, with a different message.
- `test_old_import_name_fails[...]` and
  `test_no_shim_directories_or_machinery_remain` **fail**. Reproduced on a
  copy of the branch tree with two `__pycache__` directories added:
  `3 failed, 11 passed`. CI stays green only because CI clones fresh.

Rule: the dimension-7 corpus regression (the suite goes red on the
repository's own working checkout). Authority: CLAUDE.md "Portability is
non-negotiable" (a fresh clone and an upgraded clone must behave the same).

Fix: assert on what the removal actually guarantees (no `__init__.py` or
`__main__.py` under `src/vcfops_*`, and `import vcfops_x` either raises or
yields a namespace module with no attributes), or check
`importlib.util.find_spec(name).origin is None`. Separately, have the
doctor (or a one-line note in the PR) report leftover `src/vcfops_*/`
directories, so an upgraded clone can be cleaned with Scott's go. Never
delete them automatically.

### B2. #200: the repair rebinds when it cannot identify the current Summary tab, breaking its own "never touches a tab that is not a copy" guarantee

`src/vcfcf_managementpacks/post_install.py:432` and `:439` onward.

The copy guard is `if clone_name and not _is_copy_of(...)`. When
`getDashboardConfig?isTemplate=true` has no `tabConfigs` entry for the id
(`template_state` returns `(CLONE_UNKNOWN, "")`), or the tab has an empty
name, the guard is skipped. Because the state is UNKNOWN and the source is
COMPLETE, the code goes on to call `associateResourceKindDashboards`. I
proved it with fakes: a Summary tab pointing at `user-own-tab`, whose config
answer did not carry that tab, was rebound to the pak dashboard with rc 0
and `SUMMARY REBOUND`. A tab found under another name is correctly left
alone. The existing test `test_unknown_clone_state_with_finished_source_is_rebound`
covers only the case where the name is present.

Authority: `knowledge/context/api-surface/summary_dashboard_pak_binding.md`
(this branch) says the repair "never touches a Summary tab showing anything
other than a copy of the pak's dashboard"; the brief's hunt item; the
reviewer doctrine's skeptic default (a live write under an unproven
condition).

Blast radius is limited, because the installer itself re-bound the same kind
seconds earlier. Still, this is a default-on write against the target,
never exercised live, and it acts on exactly the answer it cannot
interpret.

Fix: rebind only when `clone_name` is non-empty and `_is_copy_of` holds. A
tab missing from the config answer becomes `SUMMARY UNCHECKED` with no
write. Add a test for `template_state(...) == (CLONE_UNKNOWN, "")`
producing no association. Optional: also accept UNKNOWN only with a
matching name, and say so in the doc.

## WARNING

### W1. #159's stated precondition is not met: the sdk-template README still teaches `python3 -m vcfops_managementpacks`

`sentania-labs/vcf-content-factory-sdk-template` `origin/main` `README.md:84,89,95`
(`build-sdk` twice, `validate-sdk`), plus comments in `ci/defect_gate.py:114`
and `icons/icons.yaml:6` there and in unifi and compliance. Issue #159's
reconciliation comment (2026-10-23) names the three template README lines
as remaining scope. No template PR exists. After this merge, every pak
instantiated from the template documents a command that fails.

Fix: open the three-line template README PR and land it with or before this
PR, and name it in this PR's body. This is a loud failure, not a silent one,
so it is a WARNING.

### W2. `--skip-summary-rebind` still pays the 660 s wait that exists only for the rebind

`post_install.py:543-547`. With bindings present and no explicit wait, the
660 s polled wait applies whether or not `summary_rebind` is set. The
module's own comment says "The binding step needs the source finished; one
importer tick." `test_report_env_wait_wins_and_skip_flag` confirms the
skip path still polls. An operator who opts out of the repair can sit up
to 11 minutes for nothing.

Fix: `if bindings and summary_rebind:` for the 660 s default and the 30 s
poll. Otherwise keep the 180 s single re-check.

### W3. The content-installer prompt under-describes exit 3 and the lines to record

`.claude/agents/content-installer.md:100-113` (commit `dcd3388`). It says 3
means "a bundled dashboard STALLED", but `repair_summary_bindings` also
returns 3 for `SUMMARY NOT REBOUND`, for a rebind that did not move the
tab, and for an unfinished new copy. It tells the agent to record only
`MATERIALIZATION` and `SUMMARY REBOUND` lines, so `SUMMARY NOT REBOUND`,
`SUMMARY NOT BOUND`, `SUMMARY UNCHECKED`, and `SUMMARY NOT CHECKED` would
go unreported. The CLI epilog (`cli.py`, `pi.epilog`) gets this right.

Fix: mirror the epilog. List both causes of 3 and record every
`MATERIALIZATION` and `SUMMARY` line.

### W4. The Summary repair is default-on and has never run live; the prior design was opt-in

The api-surface doc says so plainly: "Not yet seen working live." The
2026-10-13 review of the parked branch approved an **opt-in** rebind. This
round makes the write the default on every bound-pak install, including
prod installs run through content-installer. Open points carried over:
whether the 9.0.2 UI bind deletes or orphans the installer's clone, and
whether the tab renders after a repair.

Fix: do not close #200 as fixed in the PR. Before relying on it, run one
devel install showing `SUMMARY REBOUND`, then `getDashboardConfig?isTemplate=true`
with `isLoading: false` throughout, then the rendered tab. Defaulting the
repair to off until that run is the conservative alternative. That choice
belongs to Scott.

## NIT

1. `reference/README.md:14` still says "machine-routed by `vcfops_packaging`".
2. `read_pak_dashboards` (`post_install.py:101-114`) includes
   `GenericTemplates*` directories, which `read_pak_bindings` skips. On
   builds that import those as templates (not 9.0.2 GA), they are not in
   `getDashboardList`, so a third-party pak would get a false
   `MATERIALIZATION ABSENT`. Skip them in the check too. Factory paks emit
   none.
3. `SUMMARY NOT REBOUND` (`post_install.py:441`) says the source "had not
   finished building" even when its state is unknown (no `isLoading`).
   Say "could not be checked" in that case.
4. `install.py:2965` sorts warnings by the substrings "enable" and
   "resolve". A STALLED line whose dashboard or resource name contains
   either word lands among the super-metric enable warnings and prints the
   "super metrics could not be enabled" line. Tag the materialization
   warnings separately.
5. `install.ps1` does not run the check (documented). Open a follow-up
   issue, since the branch does not touch that file. The qa-tester prompt
   does not mention recording `MATERIALIZATION` lines from `install.py`.
6. The parity cases have no single-missing-kind STALLED case (the "is"
   verb branch) and do not pin `_check_materialization`'s re-check flow
   against `check_dashboard_materialization`. Add one case of each.
7. The same STALLED state exits 1 from `vcfcf_dashboards sync`, 2 from
   `install.py`, and 3 from the pak `install`. Each follows its tool's
   existing convention and is documented. One sentence in
   `dashboard_import_two_phase_materialization.md` lining the three up
   would save a reader the cross-check.

## If shipped as-is

A distribution-zip operator gets an accurate post-install verdict. A pak
operator on 9.0.2 gets Summary tabs repaired in the common case. But the
main checkout, and every existing clone, has a red test suite after the pull
and silently importable `vcfops_*` names. In the narrow case where the
config read does not return the bound tab, the repair overwrites a Summary
binding it could not identify.
