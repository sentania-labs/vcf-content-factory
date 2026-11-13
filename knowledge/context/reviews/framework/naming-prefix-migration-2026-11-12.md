# Framework review: `[VCF CF]` content-prefix migration (2026-11-12)

- Branch: `migration/vcf-cf-prefix`, five commits on merge base `285e156`
  (`a32a66b`, `83216dc`, `b4665a2`, `52c61cd`, `014fa92`).
- Note: `origin/main` has moved to `3a4eadf` (#352, view schema fidelity)
  since the branch was cut. It merges cleanly, adds no legacy literal, and the
  merged tree's validate chain and suite match the branch's (below).
- Reviewer: `framework-reviewer`, one round (RULE-013). Static and offline: no
  live instance contacted, no pak clone modified (all pak work on
  `git archive` copies under the session scratchpad).

## Verdict

**CHANGES REQUESTED**: 3 BLOCKING, 7 WARNING, 7 NIT.

The core claim holds. On every factory output path I could render, the
rename changes display names and name-bearing localization strings and
nothing else: ids, keys, widget UUIDs, cross-reference targets and file
paths are byte-identical. The migration command reproduces commit `52c61cd`
exactly, is idempotent, and changes only strings that contain the label. The
hard cut holds on every factory loader path and in the kit.

The three blockers sit outside that core:

1. the SDK pak render changes in-pak file paths and the Summary-binding key;
2. the cleanup command can delete objects that are not rename leftovers,
   and there is a concrete case of this in the repo today;
3. with the registered pak clones present, which is how CI runs, the PR is
   red, and no merge order is recorded.

## What I re-ran

| Check | Result |
|---|---|
| Seven-package chain plus packaging validate, branch worktree (no pak clones) | 7/7 green. `vcfcf_packaging validate` rc=1 on the base and the branch alike: the synology and unifi release manifests point at absent `content/sdk-adapters/`. |
| Same chain, merge base + registered pak clones at their HEAD (unmigrated) | 8/8 green |
| Same chain, branch + the same unmigrated pak clones | `vcfcf_managementpacks validate` **rc=1**: compliance 14, synology 36, unifi 35, vsanperf 3 legacy-name errors |
| Same, branch + pak clones migrated with `migrate-prefix` (scratch) | 8/8 green |
| Same chain, branch merged with `origin/main` 3a4eadf | same as branch |
| Full suite (`-m "" --override-ini=addopts=`), no pak clones: base vs branch vs merged | 20 failed each, **identical lists**. Of these, 2 are jmespath (`test_gap_b_f_d`) and 5 doctor (the venv-dependent ones). 1 is `test_deeply_nested_json_does_not_escape_as_recursionerror` (Python 3.14 here). 12 are real-repo tests that need `content/sdk-adapters/{synology,unifi}`: the release manifests, publish, and the `vm_snapshot` strict audit, which gets an empty enables list because the release scan fails. |
| Full suite, registered pak clones present (CI condition): merge base vs branch | base **8** failed (the 2 + 5 + 1 above); branch **15** failed. The 7 new ones are `test_cli_phase4::TestPublishCLI::{test_dry_run_reports_would_build,test_dry_run_returns_zero}`, `test_publish_phase3::test_real_run_zip_lands`, `test_third_party_component_routing_phase5::{test_project_yaml_release_still_routes_to_thirdparty_dashboards,test_publish_dryrun_thirdparty_view}`, `test_third_party_routing::{TestFactoryNativeRegressionGuard::test_capacity_assessment_publish_zip_in_bundles,test_publish_thirdparty_zip_lands_at_correct_path}`. All 7 come from publish's validator, which runs `vcfcf_managementpacks validate` and hits the unmigrated paks. They pass (98 passed) once the four pak copies are migrated. |
| Render regression, merge base vs branch: every bundle and release manifest (`build --no-live-describe`) plus a synthetic manifest carrying the entire `content/` corpus (45 SM, 28 views, 12 dashboards, 4 CG, 1 report, 17 symptoms, 9 alerts, 10 recs), with nested zips exploded | 237 files each side; same file set and paths. After mapping legacy label to new, only `built_at` differs (the idps README's Markdown link is my normalizer's artifact; the branch correctly keeps it). AlertContent.xml, symptoms.json, alerts.json, dashboard.json (widget ids), views XML, supermetrics.json, customgroup.json, reports XML: no id change. |
| `vcfcf_dashboards package` + `build-discrete` of every SM, dashboard, view, report, alert, custom group (86 zips) | 868 files each side, name-only. The same 11 view discrete builds fail on both sides (pre-existing). |
| SDK paks compliance (9 views, 5 dashboards) and unifi (19 symptoms, 9 alerts, 7 recs): migrate copies, render bundled content via `_load_bundled_content` + `_write_outer_pak` with a stub adapters.zip (no JDK/SDK jar here, so no `build-sdk`) | unifi: ids, keys and XML bodies identical; **alertdef/symptomdef file names change**. compliance: dashboard.json and view XML ids identical; **`content/dashboards/<dir>/` and `content/reports/<dir>/` paths change, and so does the `dashboards.properties` key**. See B1. |
| `migrate-prefix` on a fresh copy of merge-base `content/ third_party/ bundles/` | Output equals commit `52c61cd` byte for byte (`diff -r` empty). 126 files, 246 occurrences. Second run: "Nothing to migrate". Dirty tree: REFUSED rc=1. Parse check over every changed file: 174 id-like keys unchanged, key order unchanged, only label-bearing strings differ, every changed line differs by the label only. The 3 line-count changes are wrapped labels in folded `description:` blocks, joined onto one line (parse-equal). |
| Hard cut probe: legacy names in a view, symptom, recommendation, custom group and report | Each package's validate fails with the migration message. `build` of a release fails. `dashboards package` fails. Alerts validate turns a failed symptom/recommendation load into a WARN, as it already did before this change; the chain still fails at symptoms. |
| Buildkit 1.0.29 assembled for real (`assemble_buildkit`), extracted, run with only the kit on `PYTHONPATH` | `sdk_buildkit/naming.py` is shipped and every kit module imports it. `validate-sdk` on unmigrated unifi: legacy errors; on migrated unifi: OK. |

## BLOCKING

### B1. SDK pak render changes in-pak file paths and the Summary-binding key

`src/vcfcf_managementpacks/sdk_builder.py`:

- 2853-2862: `_view_slug`, used at 3478 for views and 3756 for reports;
- 3520-3523: the dashboard directory slug;
- 3423-3427: the SM `safe_name`;
- 3571-3574: the symptom `safe_name`;
- 3639-3642: the alert `safe_name`.

The brief's own bar: a changed file path inside a rendered artifact is blocking.

Scope item 6 routes name-derived identifiers through `id_basis_name`, but
these sites slug the display name itself. So a pak built with the kit moves:

- `content/dashboards/VCF_Content_Factory_Compliance_*` to `VCF_CF_Compliance_*`;
- `content/reports/VCF_Content_Factory_*` to `VCF_CF_*`;
- `content/alertdefs/VCF Content Factory UniFi *.xml` and
  `content/symptomdefs/...` to `VCF CF ...`.

The `content/dashboards/dashboards.properties` key moves with them
(`VCF_Content_Factory_Compliance_World_Summary=` becomes
`VCF_CF_Compliance_World_Summary=`).

The key is the directory name the server-side installer binds Summary
dashboards by (`knowledge/context/api-surface/summary_dashboard_pak_binding.md`
§File format). The same doc records that the installer leaves the old
SUMMARY template orphaned on re-bind. What a changed directory key does on
pak upgrade is not recorded anywhere. `prefix_migration.md`'s "Behaviour
that depends on the prefix" table does not list these paths, and its
closing sentence ("changes ... nothing that an installed object is keyed
by") goes unproven for paks.

**Fix (smallest):** slug `id_basis_name(name)` at those six sites, the same
treatment as `alerts/render.py::_slug` and `Widget.widget_id`. That makes
pak content byte-identical apart from display strings and localization
values. Add a pak-render regression test: render a two-dashboard,
one-symptom, one-alert fixture under both spellings and assert identical
`namelist()` and `dashboards.properties`. Then add the row to the
`prefix_migration.md` table.

Note: the `resources.properties` *keys* are the escaped dashboard name
(`[VCF\ CF]\ Compliance\ ...`). They are name-bearing localization entries,
consistent between `dashboard.json` and the properties file, and acceptable
under the brief. If you would rather keep them stable too, they need the
same treatment. State which you chose.

### B2. `cleanup-legacy-prefix` can delete objects that are not rename leftovers

`src/vcfcf_common/legacy_cleanup.py:169-223` (matching at 184-185, verdicts
at 196-222).

Matching is on the name alone. The repo item's adapter kind, resource kind
and owner are never compared. The deletion rules do not establish that the
leftover is the earlier incarnation of the repo object.

A case that exists today: `content/symptoms/synology_ups_on_battery.yaml`
(`mpb_synology_dsm`/`ups`) and the synology pak's
`symptoms/synology_ups_on_battery.yaml` (`synology_diskstation`/`SynologyUps`)
are both named `[VCF Content Factory] Synology UPS On Battery`. Take an
instance with the old synology pak installed. Run the cleanup from the
factory root after syncing the renamed factory symptom. Both the factory's
old MPB symptom and **the pak's installed symptom** are marked WOULD DELETE:
server-owned kind, different id from the twin. `--apply` then deletes a
symptom the pak's alert uses. The command run from the pak root does the
mirror image to the factory's MPB symptom.

The UUID-owned branch has the same hole. For SMs, views and reports the
rename lands in place (same UUID), so by construction any legacy-named
object with a *different* id is not a leftover of this rename. It could be
a pak's object, a user's clone that kept the name, or another user's
dashboard. Yet it is deleted whenever the twin carries the repo id.

Dashboards: `list_dashboards` returns `owner` and `shared`
(`src/vcfcf_dashboards/ui_client.py:262-283`); neither is consulted, nor shown.

**Fix:**

- Symptoms and alerts: match on (name, `adapterKindKey`, `resourceKindKey`),
  read from the repo YAML.
- SMs, views and reports: a legacy-named object with a non-repo id becomes
  CONFLICT, never delete, because the rename cannot have produced it.
- Dashboards: require the leftover's owner to be the owner the factory
  installs as. Show owner and the twin's id in the listing.
- Tests: add one with a foreign same-named symptom of another adapter kind
  (must not delete), and one with a legacy-named view under a non-repo
  UUID (must be CONFLICT).

### B3. With the registered pak clones present, the PR is red, and no merge order is recorded

CI (`.github/workflows/ci.yml:84`) runs `scripts/bootstrap_managed_paks.sh`,
which clones the pak default branches. Those are unmigrated today.

Against them the branch reds `python3 -m vcfcf_managementpacks validate`
(seven-package chain step 7, RULE-005) and the 7 publish tests listed
above. Merge base: green. Branch with migrated pak copies: green.

Migrating the pak repos first does not avoid it. On merge-base code,
`check_content_naming` requires the old prefix for a declared
`factory_prefixed` pak, so factory `main` goes red instead. The paks'
release builds (`BUILDKIT_TAG` 1.0.27 in unifi) also reject the new prefix
until the tag moves to 1.0.29, which has to be published first.

**Fix:** record the order in the PR body and in `prefix_migration.md`. One
workable order:

1. the four pak migration PRs (compliance, synology, unifi, vsanperf) are
   prepared with `migrate-prefix` and held;
2. this PR merges;
3. tag `sdk-buildkit-v1.0.29`;
4. the pak PRs merge, each with its `BUILDKIT_TAG` and `SHA256SUMS` bump in
   the same commit, and factory CI is re-run.

Otherwise accept a stated red window. Either way the PR must not be
presented as green on the author's "14 known failures" figure: that figure
assumes locally migrated clones.

## WARNING

### W1. Abbreviated flags trigger `--apply`

`src/vcfcf_common/legacy_cleanup.py:364`, with the same issue in
`migrate_prefix.py:332`. argparse's default `allow_abbrev=True` means
`--a`, `--ap` and `--appl` all set `apply=True`; I verified each. Likewise
`--f` means `--force` for migrate.

**Fix:** set `ArgumentParser(..., allow_abbrev=False)` on both parsers, and
add a test that `--appl` exits 2.

### W2. The dry run does not name the instance, and nothing says to back up

`legacy_cleanup.py:335-357` and `prefix_migration.md` §Removing the leftovers.

- The output never prints the profile or host it is acting on. The default
  is `devel`, but `VCFOPS_PROFILE` silently overrides it (`_profile_cli.py:30-33`).
- Nothing tells the operator to back up before `--apply`. The owner's
  standing rule is snapshot first, nothing irreversible without his word.
- `--apply` re-lists and deletes in one go. It does not act on the plan the
  operator reviewed.

**Fix:**

- Print `profile=<name> host=<host>` in the header.
- End the dry run with an explicit backup instruction: snapshot the
  instance, or content-export the listed ids.
- Optionally, require `--apply` to repeat the dry run's delete count or a
  plan digest, so it deletes exactly what was reviewed.
- Document all of this in `prefix_migration.md`.

### W3. A failed delete does not stop the run

`legacy_cleanup.py:347-354`: after a failure the loop continues to later
kinds, so a failed dependent delete (dashboard, alert) is followed by
deletes of what it depends on.

**Fix:** stop at the first failure and report what was not attempted.

### W4. The buildkit release note claims more than `prefix_migration.md` evidences

`.github/release-notes-buildkit.md:23-27`: "an upgrade renames views,
symptoms, alerts and recommendations in place".

- `prefix_migration.md` says views are "in place, expected" (on the content
  zip path; the pak path is not stated) and pak alerts are "in place,
  expected" (compliance build 86 review: "not proven").
- The note is silent on super metrics and reports, which paks bundle.
- It is silent on the changed in-pak paths and Summary-binding key (B1).

Lines 11-13 also say legacy fails "in every pak" and then that "unprefixed
paks are unaffected". In fact unprefixed paks now also reject a name that
starts with `[VCF CF]`: new behavior, small but real.

**Fix:** say "expected to update in place (not yet observed on an upgrade)"
for alerts and views. Name what is evidenced. Add SMs and reports. Correct
the unprefixed sentence.

### W5. Buildkit 1.0.29 collides with `tooling/stock-id-guard`

That branch (worktree `agent-a22ea2cbd1089d09e`, head `29d2881`) also adds
a `## Behavior since 1.0.29` section to `.github/release-notes-buildkit.md`,
still with `BUILDKIT_VERSION = "1.0.28"`. It also edits `buildkit.py`
`_FACTORY_SOURCES` and `_IMPORT_REWRITES`: `stock_ids.py`,
`stock_ids_baseline.json`, and the `sdk_builder.py` stock_ids rewrite.

Reconcile at merge:

- If neither is tagged yet: one 1.0.29 section carrying both sets of bullets
  (the `naming.py` and `stock_ids.py` kit-contents lines together), with
  `BUILDKIT_VERSION` 1.0.29 once.
- If 1.0.29 is tagged first: the second branch moves to 1.0.30, both in its
  notes and in `BUILDKIT_VERSION`.

`tests/test_prefix_migration.py:267` asserts `BUILDKIT_VERSION == "1.0.29"`
exactly, and breaks on the next bump.

**Fix:** drop that assertion, or assert `>= (1, 0, 29)`.

### W6. Old distributed zips revert the rename, and nothing tells their holders

`CURRENT_TEMPLATE_VERSION` (`src/vcfcf_core/packaging/template_version.py`)
is not bumped. Strictly, its bump list does not require it here: no
template, structure or wire-format change.

But anyone holding a pre-migration zip who re-runs it reverts the rename:

- UUID-keyed SMs, views and reports rename back to the legacy name in place;
- name-keyed dashboards, symptoms, alerts and custom groups get legacy twins;
- `check-staleness` still reports the zip as current.

**Fix:** bump it with a history line ("content prefix moved to `[VCF CF]`;
zips built before carry the legacy names"), so old copies report stale. This
is dimension 9's signal-about-the-artifact case.

### W7. No test that a pak *built* through `build_sdk_pak` rejects legacy names

`check_content_naming` is unit-tested (`test_prefix_migration.py:246-258`)
and I verified it through the real kit. No test drives `build_sdk_pak`, or
the kit's `validate-sdk` in the isolated-kit harness
(`tests/managementpacks/test_buildkit_isolated_build.py`), with a legacy name.

**Fix:** add a legacy-name case to the isolated-kit test, asserting the
retired-prefix error and no pak written.

## NIT

N1. **Doubled prefix in discrete zip names.** `src/vcfcf_packaging/discrete_builder.py:833`
writes `[VCF CF] [VCF CF] <title>.zip`. The display name already carries the
prefix; this is pre-existing, but the branch touched the line. The
`prefix_migration.md:71` row ("`[VCF CF] <name>.zip`") is therefore wrong.
**Fix:** `strip_factory_prefix(display_name)` before prepending, or drop the
prepend, and correct the row. (Release builds rename the output to the
release slug, so published names are unaffected.)

N2. **Docs describe zip names that do not exist.** `README.md:119`,
`README.md:158` and `Getting_Started.md:334` (orchestrator commit) describe
distribution zips as `[VCF CF] <Name>.zip`. The builder writes slug names
(`dist/vks-core-consumption-bundle.zip`; verified). The stale claim was
carried forward by the edit. **Fix:** use the slug form.

N3. **Usage text is incomplete.** `src/vcfcf_common/__main__.py:32-34`
omits `--dry-run` and `--types` for cleanup. `prefix_migration.md` §Removing
the leftovers does not state the `devel` default profile.

N4. **The Markdown-link exception can also skip a name.** `naming.py:448`:
it skips any label followed by `(`. A name like
`[VCF Content Factory](Beta) X` would be left unmigrated, and the loader
then errors on it. None in the corpus. **Fix:** document it in the
`rewrite_legacy_prefix` docstring.

N5. **`dashboard-author` does not know the new error.**
`.claude/agents/dashboard-author.md` never mentions the 41-character title
budget, which is now a validate error. **Fix:** one line pointing at
`knowledge/lessons/dashboard-name-limit-50-editor.md`.

N6. **Wrapped labels make long lines.** `migrate-prefix` joins a label
wrapped across lines onto one line, which leaves 150+ character lines in
folded descriptions (`content/supermetrics/total_snapshot_space_gb.yaml:11`,
`vcf_license_*_total_license_usage_percent.yaml`). Harmless (parse-equal).
If kept, say so in the docstring; it already does, fine.

N7. **Core wheel.** `vcfcf_core` gains a module and behavior (the dashboard
name error, the widget-id basis). The external migrator imports only
`extractor._*_from_export_zip` and `supermetrics.crossref.crossref_names`
from it, both unchanged, so nothing breaks. A `core-v*` tag is only needed
when the migrator should pick it up.

## Dimensions walked

1. **Global/pak leak.** `id_basis_name` applies on both paths. The
   standalone import-zip path is byte-identical except names (verified).
   The 50-character error fires regardless of `enforce_framework_prefix`,
   on the name itself. Intended and tested
   (`test_prefixed_over_limit_is_an_error_without_prefix_enforcement`).
2. **Key collisions.** No new collisions. `strip_factory_prefix` makes
   `[VCF CF] X` and `[VCF Content Factory] X` share a recommendation key and
   a discrete slug, but the hard cut prevents both spellings coexisting in
   one load.
3. **Wire formats.** Unchanged (render regression).
4. **Loader/validator.** Every core loader routes through
   `framework_prefix_problem`. Legacy references are checked, not treated
   as built-ins (`is_factory_name`). `enforce_framework_prefix=False`
   callers are third-party projects, the extractor, the composer, and pak
   loads. Paks are covered by `check_content_naming` in both `build-sdk`
   (`sdk_builder.py:4837`) and `validate-sdk` (5628). Third-party content
   that contains the old words is accepted (`test_migrate_factory_tree`
   fixture, idps DESCRIPTION link).
5. **Render regression.** Clean on the factory paths. Drift on the pak path
   (B1).
6. **Builder/pak.** Kit ships `naming.py`, verified. `pak-compare` not run:
   no built pak, no JDK or SDK jar here.
7. **Corpus regression.** Clean without pak clones. Red with them (B3).
8. **Silent downgrade.** None found.
9. **Stale zips.** Every distribution zip must be rebuilt and republished:
   every factory-native bundle's content names changed (113 files in my
   build set), and CLAUDE.md's after-tooling rule fires anyway on
   `alerts/render.py`, `builder.py` and `discrete_builder.py`. Published zip
   *file names* do not change: bundle and release outputs are slug-named,
   and the dist file sets are identical base vs branch. The distribution
   README's generated bundle names (`readme_gen`) do change. Template
   version: W6.
10. **Tests.** Good unit coverage of naming, migration and cleanup planning.
    Gaps: B1 (pak render), B2 (foreign twins), W1, W7.

## Remaining-literal sweep

`grep -rn "VCF Content Factory\]" src scripts .claude CLAUDE.md README.md
ADMIN.md Getting_Started.md knowledge/rules knowledge/lessons .github`:

- Every `src/` hit is the legacy constant, the migration/cleanup docstrings,
  or the `content_naming` docs of the legacy check. Correct.
- RULE-006, the dashboard-name lesson and the buildkit note mention the old
  spelling historically. Correct.
- `tests/`: only `test_prefix_migration.py`. Correct.
- `knowledge/context/` hits are investigations, reviews, wire-format and
  api-surface evidence logs, attic, exports, `defects.md:907` and
  `feedback_queue.md`: historical. Correct.
- No prefix built from parts, no regex, and nothing in
  `src/vcfcf_packaging/templates/` (install.py and install.ps1 print the
  prose `VCF Content Factory` banner only). `vcfcf_packaging/cli.py:891`
  strips the prose MP prefix `"VCF Content Factory "`, which is unchanged
  by design.

## Signature changes

`_resolve_view_ids` was split into `flatten_view_groups` plus the same
function; its signature is unchanged and its only new caller is
`legacy_cleanup`. `_FACTORY_CONTENT_PREFIX` was removed from
`sdk_builder`, and nothing imports it: the repo, the pak clones' tests and
the migrator are all clean. `check_content_naming` and
`dashboard_name_length_problem` keep their signatures. The
`Dashboard.validate` behavior change (an error) reaches the extractor and
composer callers only for names that already carry the new prefix.
