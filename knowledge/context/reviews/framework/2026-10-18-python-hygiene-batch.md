# Framework review: python hygiene batch (2026-10-18)

- Branch: `fix/python-hygiene-batch`, 8 commits on `c433366` (origin/main)
- Issues: #187, #190, #186, #207, #152, #189, #196, #180
- Reviewer: framework-reviewer (RULE-013 gate)
- Verdict: **APPROVE** (0 BLOCKING / 1 WARNING / 1 NIT)

Under CLAUDE.md delegation rule 9 the WARNING and the NIT still get fixed
in one re-brief before the PR opens. Neither one blocks the verdict.

## Checks re-run (independently)

| Check | Result |
|---|---|
| Full suite, `PYTHONPATH=src python3 -m pytest tests -n 8 --dist=loadgroup -m "" --override-ini="addopts="`, with the main checkout's `content/sdk-adapters` and `reference/references` symlinked in read-only (removed afterward, tree clean) | 2220 passed, 9 skipped (twice). The skips are pre-existing: 4 gap_b_f_d product-decision skips, 3 pak_compare dist/ paks absent, 1 SDK jar absent in the worktree, 1 core_shims. The buildkit isolated-build and release-flag tests ran. |
| Seven-package validate chain | all rc=0 (managementpacks: 7 Tier 2 projects valid) |
| Bare `pytest --collect-only` from the root with the vendor SDK clone present (it ships `tests/test_mp_build.py` and others) | 2098/2229 collected, 131 deselected; every collected id is under `tests/`. `pytest .` collects 0 ids outside `tests/`. |
| #196: new tests against the base syncer (`c433366:src/vcfcf_packaging/syncer.py` overlaid in a temp package copy) | all 4 FAIL (3 new, plus the navigation test with its masking patch removed), every one with `AttributeError: 'Bundle' object has no attribute 'symptom_paths'`. All pass on HEAD. |
| #189: own temp git repos, scaffolded project, `_generate_docs` | no history, dev: `## Unreleased`. No history, release: `## 1.0.0.1`. History, dev: `## Unreleased (...)`, then `## 1.0.0.1 (...)`. History, release: `## 1.0.0.7 (...)`, then `## 1.0.0.1 (...)`. |
| #186: `scaffold-sdk` of `9Lives` and `Cert Demo`, then `validate-sdk` with `VCFCF_SDK_JAR` set to the main checkout's jar (real javac) | both compile and pass. File, `class` declaration, `package`, and the loader default `entry_class` all agree: `com.vcfcf.adapters.vcfcf_9lives.Vcfcf9livesAdapter` and `com.vcfcf.adapters.cert_demo.CertDemoAdapter`. The scaffold writes no explicit `entry_class`, so the shared helper is the actual binding. |
| #152: `env -u PYTHONPATH python3 src/vcfcf_common/doctor.py` | runs, rc=0 |
| Em-dash / en-dash sweep of the diff's added lines and all 8 commit messages | 0 / 0. The detector was sanity-checked: it finds the 148 pre-existing ones in `sdk_builder.py`. |

The orchestrator brief asked to confirm that a `--release` build writes
the version heading. I verified that by calling
`_generate_docs(..., release_build=True)` directly and by reading the
wiring (`_is_release_build()` at `sdk_builder.py:3275` reaches
`_generate_docs(..., release_build=release_build)` at `:3369`). I did
**not** run `build-sdk --release` by hand. RULE-014
(`knowledge/rules/pak-version-lines.md`) reserves the release opt-in for CI,
and this reviewer's hard rule 2 forbids building release paks.

## Dimension walk

1. **Global-default / pak-specific leak (anchor 00d3382).** No touched file
   is on the content render or import path: no `vcfcf_core` render,
   loader, or assembly, and no `vcfcf_packaging/templates`. Three changes
   have wider reach, and each one is inert apart from its intended change:
   - `adapter_class_name` changes the loader default only for `vcfcf_<digit>...`
     kinds. Every live pak (compliance, synology, unifi, the vcommunity trio,
     the template) declares an explicit `entry_class`, and none of them is
     digit-leading.
   - `_singular` returns exactly what `rstrip("s")` returned for all nine
     `CONTENT_TYPES` (none ends in "ss").
   - `norecursedirs` restates pytest's defaults verbatim. Its two added
     entries are tail-matched against the path. No existing `tests/` path
     contains `reference/references` or `content/sdk-adapters`.
2. **Key / label collisions (anchor 6c59f6b).** `adapter_class_name` can
   give `vcfcf_foo` and `foo` the same simple name, but the two live in
   different packages (`...adapters.vcfcf_foo` and `...adapters.foo`), so
   the FQNs never collide. That was already true before this change.
3. **Wire-format conformance.** #190 is docstring-only. It now matches
   `knowledge/context/investigations/policy_fragment_wire_format.md` (lines
   20-33: `<SuperMetrics>` sits directly under `<PackageSettings>`), and no
   `SuperMetricsCatalog` remains in `src/` or `knowledge/context/`. The new
   parser test mirrors that recorded export.
4. **Loader / validator correctness.** The syncer now reads `bundle.symptoms`
   and `bundle.alerts` (`vcfcf_core/packaging/loader.py:241-242`). Their
   objects carry `source_path` (symptoms loader:128, alerts loader:184),
   the same as the other four types. The "other bundles" overlap check
   (`syncer.py:88/97`) uses the same function on both sides, so path
   strings compare consistently.
5. **Render regression.** No renderer was touched, and the validate chain
   is clean.
6. **Builder / pak structure.** `sdk_builder.py` and `sdk_project.py` also
   ship inside the buildkit tarball. The buildkit rewriter
   (`buildkit.py:128+`) deliberately leaves the relative
   `from .sdk_project import` untouched and copies `sdk_project.py`
   verbatim, so the new multi-line import and `adapter_class_name` travel
   with the kit. The kit isolated-build tests ran green. CHANGELOG.md and
   REFERENCE.md are not packed into the pak (`sdk_builder.py:3075`).
   pak-compare: n/a.
7. **Corpus regression.** Suite and validate chain are both green (above).
8. **Silent capability change.** None. #196 turns a loud crash on every
   `sync` into working symptom and alert sync. #152 adds a voiced line and
   removes nothing. The test patch that hid #196
   (`tests/test_dashboard_navigations.py`) is gone, and the test still
   passes for real.
9. **Stale-zip discipline.** No file on the CLAUDE.md "After tooling
   changes" list was touched (`templates/`, `builder.py`,
   `discrete_builder.py`, `release_builder.py`, `assembly.py`,
   `render.py`), so no dist rebuild and no `CURRENT_TEMPLATE_VERSION` bump
   is owed. The #189/#186 behavior reaches pak repos' CI only through the
   next `sdk-buildkit-v*` tag, which is the normal buildkit cadence and not
   a defect here.
10. **Test coverage.** Every behavior change has a test:
    - #187: unit test over all `CONTENT_TYPES`
    - #190: parser test
    - #186: scaffold-to-loader binding for digit and normal names
    - #207: hermetic subprocess collection test, bare and dot
    - #152: voiced, sentinel-silent, and stale-record cases
    - #189: fallback and history, dev and release
    - #196: end-to-end `sync_bundle` over all six types, proven to fail on base

    The #186 tests check identifier validity by name, not by compiling.
    My javac run above covers the compile.

Downstream CHANGELOG-heading consumers (brief's #189 check): none. I
grepped `src/` (release_builder, defect gate, docs version stamp),
`.github/`, `scripts/`, `bundles/`, the template repo's three workflows
(`build-pak-on-tag.yml`, `pak-tests.yml`, `tests.yml`), and the pak repos'
`.github/`. Nothing parses a CHANGELOG heading. The live pak repos already
head their hand-kept CHANGELOGs `Unreleased` (synology:
`## 0.0.0.33 (Unreleased)`, unifi: `## 0.0.0.15 (Unreleased)`,
compliance: `## Unreleased`), so the new fallback matches existing
practice.

#152 header contract: both bootstrap scripts already emit
`unknown=$un` with a `-` default (`bootstrap_references.sh:37-40`,
`bootstrap_managed_paks.sh:47`). The doctor's header comment block
(`doctor.py:105-121`) now documents the key. No test binds the scripts'
emitted keys to that header (the "contract" is the comment). That was
true before this change too, so it is not a finding against this diff.
The all-green summary is blocked because any `bootstrap_report_lines`
output lands in `attention` (`doctor.py:1397-1399`), and
`test_unknown_key_reports_alignment_not_checked` asserts that.

## Findings

### BLOCKING

None.

### WARNING

- **[src/vcfcf_managementpacks/sdk_builder.py:2980-2988; tests/managementpacks/test_docs_version_stamp.py `test_history_dev_build_heads_current_build_unreleased`]**
  RULE-014 (`knowledge/rules/pak-version-lines.md`: on a dev build "all
  version surfaces ... generated docs" carry the 0.x line).
  - **The problem.** In the commit-history path, a dev build now heads the
    current build `Unreleased`. Every *earlier* build is still headed with
    its declared 1.x version (`## 1.0.0.1 (...)` in my temp-repo run). If
    those earlier builds were hand-built, they shipped as `0.0.0.N`, so a
    locally generated doc names 1.x versions that never existed as
    artifacts.
  - **The test codifies it.** The new test asserts `"## 1.0.0.0 ("` is
    present on a dev build.
  - **Reachability today is near zero.** `git log` runs from
    `project_dir.parent.parent.parent`. For a gitignored pak clone that is
    the factory repo, which has no history for the path, and in the
    template CI it is outside the checkout. Both fall back to the no-history
    branch, which is now correct. The loop also predates this change.
  - **Why fix it anyway.** The commit touches exactly this loop and makes
    an explicit decision here, so it should be resolved, not carried.
  - **Fix.** On a dev build, head earlier groups by build number without
    the declared version (for example `## build 1 (date)`), and adjust the
    test. If keeping declared versions is deliberate (they may be CI
    releases), say so in the `_generate_changelog_md` docstring, citing
    RULE-014, so the next reader does not take it for an oversight.

### NIT

- **[tests/test_pytest_collection_scope.py fixture]** The comment in
  `pyproject.toml` explains that the two added `norecursedirs` entries are
  tail-matched. The test proves a `tests/fixtures/reference/` dir is still
  collected. It does not prove the converse, which the tail-match also
  implies: a fixture at `tests/**/content/sdk-adapters/` would be skipped.
  No such path exists today. → Add one line to the `pyproject.toml`
  comment noting that `tests/**/reference/references` and
  `tests/**/content/sdk-adapters` would also be excluded, so a future
  fixture author is not surprised.

## If shipped as-is

Operators get working `vcfcf_packaging sync` (it crashed on every bundle
before), a doctor line for untracked clones, a clean bare `pytest`, valid
Java names for digit-leading scaffolds, and first dev builds whose
CHANGELOG makes no 1.x release claim. Content, dist zips, and the import
path are unaffected.
