# Framework review: tooling/stock-id-guard (issue #345)

- Branch: `tooling/stock-id-guard`, base `origin/main` `285e156`
- Commits: `adcd628` (code, baseline, tests, context docs), `6a5b931` (lesson,
  skill §UUID contract, buildkit release notes)
- Reviewer: framework-reviewer, 2026-11-12
- Verdict: **APPROVE** (0 BLOCKING, 9 WARNING, 7 NIT). Every finding is to be
  fixed before the PR opens (CLAUDE.md delegation step 9).

## Checks re-run

- **Validate chain** (seven packages, branch): all rc=0, no `STOCK-ID` or
  `ALLOWLISTED` line.
- **Test suite**, branch vs a detached `origin/main` worktree, same machine,
  `PYTHONPATH=src`, no xdist, Python 3.14:
  - default (`not slow`): base 14 failed / 3638 passed; branch 14 failed / 3707 passed.
  - full (`-m "" --override-ini=addopts=`): base 20 failed / 3763 passed; branch
    20 failed / 3832 passed. **The failing ids are identical on both trees.**
  - Why 20 and not "14 jmespath": the extra 6 are slow-tier publish/release tests
    excluded from a default run. Of the 20, only 7 are `jmespath` (doctor x5,
    MPB JMESPath predicates x2); 1 is the recursion test on Python 3.14; 12
    (release-naming real-repo x5, packaging-validate real-repo x1, publish /
    third-party routing x5, discrete strict audit x1) fail because
    `bundles/releases/synology-diskstation-managementpack.yaml` points at
    `content/sdk-adapters/synology`, gitignored and absent from a worktree, so
    `vcfcf_packaging validate` fails. All environmental, none touched by this
    branch.
  - New files: `tests/test_stock_id_guard.py` + `tests/managementpacks/test_buildkit_stock_ids.py`: 63 passed.
- **Baseline reproducibility**: reran `scratchpad/sig/gen.sh` into scratch;
  baseline and candidates report are **byte-identical** to the committed file and
  the author's report. Load cost: 0.01 s for the 710 KB file, cached per process;
  a full pak scan is 0.01 to 0.08 s. Performance is a non-issue.
- **Guard over factory content**: validate chain (YAML) clean; `stock-id-check`
  over `dist/` (main checkout) 0 of 86 definitions stock; `validate-sdk` on the
  six registered paks in the main checkout (compliance, synology, unifi,
  vsanperf, template, vcommunity-java): all rc=0, no stock-id line. Kit built
  from the branch: `sdk_buildkit validate-sdk` on compliance rc=0, and the
  `vcfcf_alerts.render` import used by `check_stock_ids` is rewritten in the kit.
- **Builder wiring end to end** (not covered by tests, see W6): all three
  `bundles/*.yaml` build into scratch through the guard; with a synthetic
  baseline listing one of a real bundle's ids, `build_bundle` and
  `build_discrete` both raise `BundleValidationError` and write no zip.
- **Released third-party paks**: e1 `vCommunity_0.8.1.pak` 120 view hits, upstream
  0.3.1 (`ref_031`, unpacked) 117, both rc=2, nothing else stock. All four
  re-identified 0.3.x builds, both e1 fix builds and both unpacked fix trees: 0, rc=0.
- **Wheel**: built `vcf-cf-tooling-core` from the branch;
  `vcfcf_core/stock_ids/stock_ids_baseline.json` is in it (via the
  setuptools-scm file finder). No test asserts it (W7).
- **Scanner probe** (synthetic baseline): caught upper-case and lower-case ids,
  pak > adapters.zip > conf/views/views.zip, a view embedded in report
  content.xml, the third entry of a dashboard envelope, namespace-prefixed and
  malformed XML, BOM + whitespace. References stayed clean: report `ContentKey`,
  dashboard widget `viewDefinitionId`, `<Symptom ref>`, `<Recommendation ref>`.
  Silently missed: UTF-16 XML, an unreadable-compression member, nesting past
  depth 6 (W2).
- render-regression: n/a (no renderer touched). pak-compare: n/a (pak bytes unchanged).
- `src/vcfcf_core/dashboards/`: **no line touched.** The branch touches
  `src/vcfcf_dashboards/cli.py` (one hunk at 212-224, `cmd_validate`) and
  `src/vcfcf_dashboards/client.py` (one hunk at 354-368, `import_content_zip`).

## Baseline purity

**(a) Names and customer content.** Every view, dashboard and report name in the
baseline was read. All read as product content, and every one that looked
custom ("Custom - Text ...", "VMware Infra Custom - ...", "... cost", "(s)",
"?") carries the product `localizationKey` on two or more labs. Symptom and
alert owners, by adapter kind from the lab exports: VMWARE, NSXTAdapter,
VirtualAndPhysicalSANAdapter, APPOSUCP, VMWARE_INFRA_HEALTH, vCenter
Operations Adapter, Container, VMSP, VMWARE_INFRA_MANAGEMENT, VcfAdapter,
SupervisorAdapter, VsanSnapshotManagerAdapter, VrAdapter, DiagnosticsAdapter,
APPLICATIONDISCOVERY: product or native only. No factory, third-party or lab
marker is present.

Customer material in the session scratchpad: the original export holds 9190
definitions, 2665 of them under ids in the baseline. That is expected: a
scope-ALL export carries the product's own content under stock ids. The
migrator outputs (`bundle_migrator/`, `bundle_new/`, `migrator/out058b/`, 10 to
15 definitions each) are the customer-authored objects. Exactly one of their
ids is in the baseline, `f1aeaa58-ce9a-4456-878e-1d9582a66711`, and it is a
stock view the customer export also carried: localized, present on lab-a and
lab-b in exports that predate the migration, baseline name equal to the stock
name. None of the customer-authored names appears in the baseline or anywhere
in the diff. **No customer-authored id or name entered the repo.**

**(b) The contaminated 9.1.1 export.** The extra objects are in
`devel_9_1-2026-11-12-vcommunity-e1-fix-test/B0` (exported 23:45Z), not in the
`fix-test` B0: 4 views, 5 super metrics, 1 dashboard (custom groups are not
scanned). They are exactly the migrator's output, so "unknown origin" is the
customer migration. Of the ten, only `f1aeaa58-...` is in the baseline (see
(a)). The e1 B0 is a strict superset of the other 9.1.1 B0. Regenerating
without it gives the **same 4282-id set**. Only two values change: that view's
versions lose `9.1.1`, and one symptom's display name changes on a vote tie.
So the id set is pure, but one version claim (`9.1.1`) comes from customer
content (W3).

**(c) The stock-ness rules.** See W4. In short: yes, a third-party pak installed
on two labs is accepted as stock unless it is a `--known-content` package or
carries a name marker or excluded adapter kind. None is in today's baseline.
The 90% rule is a workable heuristic but fragile in both directions, and today
it sits one id from flipping for vsanhostmetrics.

**(d)** Reproduced byte for byte (above).

## Entry points (every content-emitting or content-importing path in `src/`)

| Path | Guarded | Notes |
|---|---|---|
| `vcfcf_packaging build` (`builder.build_bundle`) | yes | proven end to end |
| `build-discrete` / release component (`discrete_builder._assemble_zip`) | yes | proven end to end; no allowlist possible (N3) |
| `release` / `publish` bundle headline (`release_builder` -> `build_bundle`) | yes | |
| `release` MPB headline (`_build_mp_headline` -> `builder.build_pak`) | no | MPB paks ship empty content dirs; documented |
| SDK pointer (`_build_sdk_mp_headline`) | n/a | pointer JSON only |
| `build-sdk` (factory and kit) | yes | bundled content before the compile, then the built pak |
| `validate-sdk` (factory and kit) | yes | |
| per-type `validate` x5 | yes | customgroups n/a (server ids) |
| `import_content_zip` (dashboards / views / reports / SM sync, bundle sync) | yes | repo-wide allowlist (W1) |
| `vcfcf_supermetrics` policy re-import (`POST /api/policies/import`) | no | re-imports the instance's own policy; N6 |
| symptom / alert REST upsert | no | collides **by name**, not id; doc says "cannot collide" (W8) |
| `vcfcf_managementpacks install` | yes | `--allow-stock-ids`, default off; fail closed before login |
| `uninstall_pak` | no | #345 item 3, stated as open in the lesson (N5) |
| distribution zip `install.py` | no | installs what the builder checked; documented |
| `vcfcf_extractor` | n/a | writes YAML; caught by the validate chain afterwards |

Signature sweep: `install_pak(..., allow_stock_ids=False)` has one caller (the
CLI). `Bundle.stock_id_allowlist` and `SdkProjectDef.stock_id_allowlist` are
added last with defaults, so the positional and keyword constructors in `src/`
and `tests/` still work. `import_content_zip` keeps its signature and its
callers already handle `VCFOpsError`. Core change (`vcfcf_core/packaging/loader.py`):
`load_bundle` raises only when the key is present and malformed, so it is
compatible with the external migrator. `vcfcf_extractor` imports nothing that changed.

## Findings

### WARNING

**W1. [`src/vcfcf_packaging/stock_ids.py:100`, `:195`] One manifest's allowlist entry silences every other manifest's hit on validate and content import.**
Authority: `knowledge/context/stock_id_guard.md` §Escape hatch ("for the rare
deliberate case; reviewable in the diff that adds it"). `repo_allowlist()`
merges the entries of every `bundles/*.yaml` and `third_party/*/PROJECT.yaml`,
then `report_stock_ids` and `refuse_stock_ids_in_zip` apply the merged list to
whatever is being validated or imported. So an entry in bundle A lets bundle
B's or a standalone `content/` object's stock-id definition validate and import
silently. The build paths are correctly scoped (`guard_bundle` uses only the
bundle's own list). None exist today, so nothing slips now.
Fix: scope each entry to the files its manifest owns. Record the content paths
per manifest in `repo_allowlist` and match `Definition.location` against them.
For an import, pass the bundle's own list from `syncer.sync_bundle` down to
the handlers and use no allowlist for a standalone per-type sync. Add a test
where manifest A's entry must not cover B's definition.

**W2. [`src/vcfcf_core/stock_ids/guard.py:346`, `:351`, `:355`, `:359`, `:214`] The scanner fails open on content it cannot read.**
Authority: shared reviewer doctrine ("unreadable is not compliant"); this
module's own fail-closed contract. A nested zip past depth 6, a `BadZipFile`
member, a member over 512 MB, or a member raising `NotImplementedError` /
`RuntimeError` / `OSError` (unsupported compression, encryption) is skipped
with no record. UTF-16 XML is not recognised (`_strip_lead` handles only the
UTF-8 BOM). Each case yields "no definition uses a stock id" and, on
`install`, a clean preflight. The comment at `:78` says an oversized member is
"skipped with a note", but no note is emitted. Not BLOCKING because the
product importer (java.util.zip) cannot read most of these forms either.
UTF-16 is the exception it likely can.
Fix: collect skipped members (location and reason) on a result object.
`check_paths`, `install`'s preflight, `refuse_stock_ids_in_zip` and the
built-pak gate treat any skip as "cannot check" (exit 1 / refuse). Decode
UTF-16/32 XML by BOM. Correct the comment. Add a test per skip class.

**W3. [`src/vcfcf_core/stock_ids/stock_ids_baseline.json`, view `f1aeaa58-ce9a-4456-878e-1d9582a66711`; `knowledge/context/stock_id_guard.md:149`; `knowledge/lessons/pak-content-must-not-reuse-stock-ids.md:39`; `.github/release-notes-buildkit.md:10`] One source is not clean, and one version claim comes from customer-migrated content.**
Authority: RULE-002 (no fabrication); the generator's own rule ("scope-ALL
content exports taken on a clean instance"). The lab-c source
`devel_9_1-2026-11-12-vcommunity-e1-fix-test/B0` was taken after a migration
tool imported customer content. The id set is unaffected (proven above), but
this view is tagged stock in `9.1.1` only because of that import (absent from
the three other 9.1.1 exports). The error message for a hit on it says "stock
in 8.18.7, 9.0.2, 9.1.1". The docs call all sources clean.
Fix: drop that `--export` from the generation command and regenerate. That
changes only the view's versions and one symptom's display name, and makes the
"clean" claim true. Record the dropped source and why in the PR body.

**W4. [`src/vcfcf_core/stock_ids/generate.py:78`, `:195-203`; `knowledge/context/stock_id_guard.md` §How the baseline is generated, step 3] The 90% "installed" rule is fragile in both directions, and vsanhostmetrics sits one id above it.**
Authority: generator docstring ("a non-stock id in the baseline fails builds that are fine").
Measured presence of each known package per lab: `fork-vsanhostmetrics` 91% on
lab-a, b and c (44 ids, 40 present). One more view or dashboard in the fork
drops it under 90% on every lab. Its 40 present ids then become
three-instance evidence and enter the baseline on the next regeneration. Its
dashboards carry no name marker, so only this rule keeps them out. The
candidates report would not show them, because they would no longer be
candidates. The harm is a false refusal of the fork's own build on
`vcfcf_managementpacks install` (needs `--allow-stock-ids`) and false
`stock-id-check` hits, with an error that wrongly calls the content "VCF
Operations stock". The opposite failure: a package that copied stock ids and
is installed on every lab (vCommunity upstream sits at 40% on lab-a, b and c
and 89% on lab-d) would explain those stock ids away, a silent hole on exactly
the ids that matter. A third-party pak not passed as `--known-content`,
installed on two labs, is accepted as stock outright. None is in today's
baseline: all symptom and alert kinds are product, and all view, dashboard and
report names are product and localized.
Fix: (1) Treat the registered fork trees (`vsanhostmetrics`,
`cluster-perf-risk`, `vcommunity`) as exclusions (`--factory-tree` or a new
`--exclude-content`), not `--known-content`. Their ids are re-identified and
never stock: 0 of their ids are in the baseline today, so this changes nothing
now and removes the fragility. (2) Print each known package's presence ratio
per instance on generation and warn when it is within 10 points of the
threshold. (3) State both failure modes and the unknown-third-party-pak case
in `stock_id_guard.md` §Known holes, with "diff the baseline on every
regeneration and read every added name" as the review step.

**W5. [`src/vcfcf_packaging/stock_ids.py:238`, `src/vcfcf_managementpacks/buildkit.py:792`, `src/vcfcf_managementpacks/sdk_builder.py:5103`] Success messages claim more coverage than the baseline has.**
Authority: dimension 8 / doctrine (no green that is not earned);
`stock_id_guard.md` §Known holes. "no definition uses a stock id" and "no
bundled definition uses a stock id" print when:
(i) the super metric and recommendation tables are empty, so a stock super
metric id always passes;
(ii) single-instance 8.18.7 and 9.0.2 content, and badge or `ALL`-kind
symptoms, are holes;
(iii) the path held zero definitions. `stock-id-check content/` on a YAML tree
scans nothing ("distinct definition ids scanned: none") and still reports
clean, exit 0. The six registered pak repo trees scanned that way all report
clean while scanning nothing.
The known holes appear only in `stock_id_guard.md`, not in any output a user sees.
Fix: word the pass as "none of the N baseline ids (versions ...; no super
metric or recommendation ids measured, see stock_id_guard.md §Known holes)".
When zero definitions were scanned, say so, and exit 1 from `stock-id-check`
("nothing to check: YAML is checked by validate / validate-sdk"). Add the
super metric and recommendation gap to the lesson and the release-notes entry,
which currently say only "4282 ids from clean ... exports".

**W6. [`src/vcfcf_packaging/builder.py:507-510`, `src/vcfcf_packaging/discrete_builder.py:783-786`, `src/vcfcf_managementpacks/sdk_builder.py:4849-4856`] The build wiring has no test.**
Authority: dimension 10 (a `builder.py` change with no accompanying test is
at least a WARNING). The tests call `guard_bundle`, `check_stock_ids` and
`_gate_built_pak_stock_ids` directly. Nothing fails if the call in
`build_bundle`, `_assemble_zip` or the pre-compile block of `build_sdk_pak` is
removed or moved after `write_bytes`. I proved all three by hand (above); a
test must.
Fix: one test each, building a bundle and a discrete item against a synthetic
baseline that lists one of their ids. Assert `BundleValidationError` and no
zip on disk. For `build_sdk_pak`, assert the pre-compile refusal (the kit test
covers only the no-baseline case).

**W7. [`tests/test_core_row4_seams.py:358`] Shipping the baseline in the `vcfcf_core` wheel is untested.**
Authority: the brief's requirement (1); `pyproject.toml` has no package-data
declaration, so inclusion rests on the setuptools-scm file finder seeing a git
checkout. The existing wheel fixture asserts `.py` members only. A wheel built
from a git-less tree, or a future MANIFEST change, would ship a `vcfcf_core`
whose `load_baseline()` fails closed everywhere.
Fix: assert `vcfcf_core/stock_ids/stock_ids_baseline.json` is in the wheel and
byte-equal to `src/` in `core_wheel_site`. Declare it in
`[tool.setuptools.package-data]` so it does not depend on the scm finder.

**W8. [`knowledge/context/stock_id_guard.md:62-64`] "Symptom and alert `sync` ... cannot collide" is not true.**
Authority: `src/vcfcf_symptoms/client.py:77-82`, `src/vcfcf_alerts/client.py:113-117`
(upsert by name: find by name, then PUT the existing id). An unprefixed
third-party symptom or alert named like a stock one overwrites the stock
object through REST. The id guard cannot see this. RULE-006's prefix protects
factory content, not third-party content.
Fix: reword. The REST path collides by name, not id. Factory content is
protected by RULE-006, unprefixed third-party content is not. Record it as
open under #345 item 4. Optionally refuse a symptom or alert sync whose name
equals a baseline stock name (the baseline already carries names).

**W9. [`src/vcfcf_managementpacks/buildkit.py:97`; `.github/release-notes-buildkit.md:5`; `buildkit.py:379` docstring "kit 1.0.29+"] Kit version stamp lags the kit's behavior.**
Authority: dimension 9, version signal; precedent `285e156` (1.0.28 bumped in
its feature commit). The kit gains a guard, two files and a subcommand, and
the notes say "Behavior since 1.0.29", but `BUILDKIT_VERSION` stays `1.0.28`.
The publish workflow takes the version from the tag, but factory-mode builds
stamp `BUILDKIT_VERSION` (e.g. the jar `Implementation-Version`). Every
local build between merge and a later bump labels 1.0.29 behavior as 1.0.28.
What must be true at merge: `BUILDKIT_VERSION = "1.0.29"` in this PR, the
release-notes heading unchanged, and `sdk-buildkit-v1.0.29` tagged from main
after merge. Note in the notes that repos on the floating `sdk-buildkit-v1`
get the guard on their next CI run (the six registered paks pass), while
exact-pinned repos must bump their pin to get it.

### NIT

**N1. [`src/vcfcf_core/stock_ids/generate.py:289`] The display-name vote counts observations, not instances.** Lab-a and lab-b each fed three exports and lab-c four, so an instance with more exports outvotes. Count one vote per instance.

**N2. [PR body; `stock_ids_baseline.json` `regenerate` field] The exact generation command lives only in a session scratchpad.** `stock_id_guard.md` says to record it in the PR. Put the full command line in the PR body with paths replaced by the neutral labels, including the dropped source (W3).

**N3. [`src/vcfcf_packaging/discrete_builder.py:245`; `knowledge/context/stock_id_guard.md:86`] A `PROJECT.yaml` allowlist is honoured by validate and import but by no build.** `_make_synthetic_bundle` never sets `stock_id_allowlist`, and `project.py` does not parse the key. So a third-party item can pass validate and fail its release build. That is the fail-closed direction, but the doc claims PROJECT.yaml works. Either thread it through or say builds ignore it.

**N4. [`src/vcfcf_alerts/cli.py:102`] Order of output.** `OK: ... valid` prints before the stock-id check, which can then fail with rc 1. The same applies to the supermetrics, symptoms and reports listings. Run the check before printing OK.

**N5. [PR body] Do not close #345.** The PR delivers wanted items 1 and 5. Items 2 to 4 (install-time collision with the target's ids, uninstall refusal, name-based delete scoping) stay open, as the lesson says. Use "Part of #345".

**N6. [`knowledge/context/stock_id_guard.md` §Where it runs] List the unguarded paths explicitly:** the policy re-import in `vcfcf_supermetrics` (it carries `<superMetric uuid>` definitions; the guard counts in-policy super metrics, so once super metric ids enter the baseline, a policy export embedding stock super metrics will be flagged), `uninstall_pak`, and Tier 1 `build_pak`. Also add `stock-id-check` to the `python-mp-reviewer` checklist (`knowledge/context/python_integration_sdk.md`). The vCommunity forks are that vehicle and are not built by `build-sdk`.

**N7. [PR body; CLAUDE.md "After tooling changes"] Stale-zip note.** `builder.py` and `discrete_builder.py` are touched, so the rule calls for a rebuild. Zip bytes are unchanged and nothing distributed carries a stock id (`dist/` scan: 0), so neither a rebuild nor a `CURRENT_TEMPLATE_VERSION` bump is needed. Say so in the PR so the orchestrator does not have to re-derive it. Separately, `stock_id_guard.md:9` and `:169-171` say "devel" where the baseline uses neutral labels; use "lab-b" for consistency (the profile name is not secret, already in the investigation filename).

## If shipped as-is

Builds, validate, imports and pak installs refuse stock-id definitions as
designed, and nothing the factory ships trips it. The residual risk is
quieter: a third-party pak with an unreadable member, or a stock super metric,
passes with a message saying no stock id is used, and the next baseline
regeneration can silently start refusing the vsanhostmetrics fork's own install.
