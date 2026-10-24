# Framework review: SDK 9.1.1.0100 second compile target (#211), 2026-10-23

Branch `feat/211-sdk-jar-9-1-1-compile-target`, five commits on `main`
(`10b1ad0`): `32eeafa`, `627d08f`, `1325e98`, `e2097e5`, `c1bbffe`.
Reviewed in detached worktrees (the branch is checked out in the author's
worktree), pak clones symlinked in, the main checkout's adapter_runtime jars
copied in, the 9.1.1.0100 jar from the holding share (sha256 re-checked:
`79f7b123...46f7`), Temurin 25.0.5 from session scratch.

**Verdict: CHANGES REQUESTED.** 2 BLOCKING, 5 WARNING, 5 NIT.

The pass itself works: under JDK 25 it compiles the framework and all seven
Java paks against the 9.1.1.0100 jar, and a reference to the dropped
`adapter3.RollUpType` fails it, naming the class, in build-framework.sh, the
factory validate-sdk and the kit. The two blockers are around it. The jar is
kept off the shipped classpath only under one exact filename. And six
documents say the jar sits in the private runtime repo, which it does not.

## BLOCKING

### B1. The compat jar is excluded by exact filename only; under its appliance name it joins the shipped classpath and the pass skips

`src/vcfcf_managementpacks/sdk_builder.py:313` (`_is_compat_sdk_jar`, name
equality), `:464` (`_build_classpath_jars` globs `adapter_runtime/*.jar`),
`:469` (`adapter_runtime/lib/*.jar`, no exclusion at all).

The branch's own instructions send users to the appliance for the jar:
`src/vcfcf_managementpacks/README.md:157-159` says "a 9.1.1.0100 appliance's
`common/lib/vrops-adapters-sdk.jar`, put it in `adapter_runtime/`", and
`adapter_runtime/PROVENANCE.md` "Setting it up locally" says copy it here.
Under that name it is not `vrops-adapters-sdk-9.1.1.0100.jar`, so:

- `_build_classpath_jars` returns both SDK jars (re-run:
  `[..., 'vrops-adapters-sdk-2.2.jar', 'vrops-adapters-sdk.jar']`), which is
  the merged classpath the change exists to prevent;
- `_resolve_compat_sdk_jar` finds nothing, so the pass skips.

Re-run with JDK 25 as the javac on PATH (which the docs tell users to set up
for the pass), adapter source referencing the 9.1.1-only class
`describe.LIExtractedFieldDescribe`: validate-sdk exits 0 with only the
"COMPAT CHECK SKIPPED" box. A pak built that way references a class 9.0.2
does not have, which is the reverse of the drift #211 guards against, and
nothing says so. With JDK 17 the primary compile happens to fail ("cannot
access", class version 69), so the hole is open exactly when the user has
done what the docs ask. The leak existed before this branch for any stray
jar. This branch makes a second SDK jar in adapter_runtime/ the documented
setup and claims `_is_compat_sdk_jar` "keeps it out of every glob here"
(PROVENANCE.md, tier2 row). That claim holds only for one filename.

Fix: the primary classpath takes exactly one SDK jar (the `VCFCF_SDK_JAR`
one or `_primary_sdk_jars()[0]`). Any other `vrops-adapters-sdk*.jar` (glob
without the dash, so `vrops-adapters-sdk.jar` matches) in adapter_runtime/
or adapter_runtime/lib/ is a loud error naming the file and the expected
name, not silently included. Add a test with the appliance name.

### B2. Six documents say the 9.1.1.0100 jar is in the private runtime repo; it is not

`gh api repos/sentania-labs/vcf-content-factory-sdk-runtime/contents` today:
`README.md` and `vrops-adapters-sdk-2.2.jar` only. The last commit there is
2026-09-25. Claims to the contrary:

- `src/vcfcf_managementpacks/adapter_runtime/PROVENANCE.md:27-29` ("Copies:
  the private ... repo beside the 2.2 jar (where factory CI fetches it)")
- `src/vcfcf_managementpacks/README.md:156-157` ("take it from the private
  ... repo")
- `reference/docs/vendor-jars/PROVENANCE.md:3-4` ("lives in the private ...
  repo beside the 2.2 jar")
- `knowledge/context/README.md:234` ("held in the private ... repo")
- `knowledge/context/tier2_architecture.md:757` (changelog row: "copies in
  the private ... repo") and `:785` (table row: "binary in the private ...
  repo")

RULE-015: a fresh clone cannot resolve the citation, and the holding-share
path is local-only. RULE-016: the `reference/docs/` copy becomes immutable
once merged, so after merge the false sentence can never be corrected in
place. It also undercuts the CI job: per its own comment (`ci.yml`, "With the
secret, a jar missing from that repo ... fails"), the day someone adds
`SDK_RUNTIME_SSH_KEY` to this repo the job goes red. It is green today only
because the secret is absent (confirmed: not in the repo's secret list), so
`sdk-compat` currently proves nothing on any run.

Fix, one of: (a) push the jar to the private repo before this merges.
That puts a Broadcom binary somewhere under Scott's identity, so it needs his
verbatim go (global rule 8). Or (b) reword all six to "not yet in the
private repo; local-only at the holding share" with the RULE-015
local-only disclaimer, and open an issue for the upload plus the secret.

## WARNING

### W1. Every tagged pak release will build with the pass skipped, and only a stderr box says so

Pak CI (`build-pak-on-tag.yml`, compliance copy read today) pins the floating
`sdk-buildkit-v1`, sets up JDK 17, and passes only `--sdk-jar` (2.2). Once
1.0.13 is tagged and v1 moves, every pak release runs the pass, skips it,
prints the box to stderr, and publishes. `--release`
(`VCFCF_RELEASE_BUILD`) does not escalate the skip. There is no
`::warning::` annotation and no step-summary line, and no issue tracks the
adoption (no pak workflow in the factory carries the change; the private
repo has no jar to fetch anyway, see B2). This is documented, so not
BLOCKING. But #211 asked to "fail the build if an adapter references a class
missing from either", and on the only path that ships, the check never runs.
`tier2_architecture.md:757` "pak builds get the pass once
`sdk-buildkit-v1.0.13` is tagged" overstates it (the same row later says
"otherwise it warns and skips").

Fix: when the pass skips under `VCFCF_RELEASE_BUILD` and `GITHUB_ACTIONS` is
set, also emit `::warning title=sdk-compat skipped::...` so the release run
shows it. Reword the tier2 sentence. File the pak-workflow adoption issue
(JDK 25, fetch the 9.1.1 jar, `--require-sdk-compat`), blocked on B2.

### W2. Default build-framework.sh now needs python3 with PyYAML, and reports a missing module as a 9.1.1 compile failure

`src/vcfcf_managementpacks/adapter_framework/build-framework.sh:61-65`,
`:149-154`. `compat_pass` imports `vcfcf_managementpacks.sdk_builder`, whose
package `__init__` imports `loader.py`, which imports `yaml`
unconditionally. Re-run of the default (non `--compat-only`) build with a
python3 that has no site-packages: `ModuleNotFoundError: No module named
'yaml'`, then "COMPAT PASS FAILED: framework source does not compile against
the 9.1.1.0100 SDK jar", exit 1. The primary framework build now fails on a
missing Python module, even with no compat jar present (where the contract
is "skip with a warning"), and the message points at the wrong cause.
Before, the script needed javac and jar only.

Fix: in the shell, skip the call (with the same notice) when neither
`$VCFCF_SDK_COMPAT_JAR` nor `adapter_runtime/vrops-adapters-sdk-9.1.1.0100.jar`
exists and `VCFCF_SDK_COMPAT_REQUIRED` is unset. Have the Python side exit
with a distinct code for "could not run" (import error), and print a message
that names it.

### W3. Neither call site is tested: removing both leaves the suite green

`sdk_builder.py:3675-3679` (build_sdk_pak step 4b) and `:4030-4036`
(validate_sdk_project). Mutant: both `_sdk_compat_check(...)` calls replaced
with `pass`. Full suite still 2175 passed / 8 skipped. The 20 new tests cover
the helpers only. Dimension 10: a builder change with no test of its wiring.
Fix: two tests with the existing stub-jar fixtures. validate_sdk_project
returns the "SDK compat check failed ... missing class X" error.
build_sdk_pak raises it before step 5. Plus one for `build-framework.sh
--compat-only` exit codes (pass / skip / required-skip).

### W4. BUILDKIT_VERSION collision with `fix/gate-integrity-219-218-226` is not recorded

Both branches set `BUILDKIT_VERSION = "1.0.13"` (confirmed:
`fix/gate-integrity-219-218-226` at `090837b`, its current tip, `buildkit.py:88`). Neither
the tier2 row (`:757`, "**Versioning:** ... bumped to `1.0.13`") nor
`.github/release-notes-buildkit.md` ("Behavior since 1.0.13") says so. If
both merge as-is, one tag means two different kits, or the second merge
silently folds its changes into the first's notes. Fix: add to the row
"collides with the gate-integrity branch (#219/#218/#226), also 1.0.13;
whichever merges second takes 1.0.14 and moves its row and release-notes
heading".

### W5. `reference/docs/vendor-jars/PROVENANCE.md` is factory-authored text in the vendor tree, with no vendor artifact beside it

RULE-010 (no framework output under `reference/docs/`) and RULE-016
(additions there are vendor extracts). The directory holds only this file,
written by an agent, and its own header says "Verbatim Broadcom jars,
byte-for-byte as shipped". After merge it is immutable, which is what turns
B2's false sentence into a permanent one. The same provenance already lives
in `adapter_runtime/PROVENANCE.md` and the tier2 table. Fix: drop it, or move
the OVA-extraction chain into `knowledge/context/` (for example a section of
`adapter_runtime/PROVENANCE.md`), and point `knowledge/context/README.md:234`
there.

## NIT

- **N1.** `.github/workflows/ci.yml:272-273`: the hash is the first 64-hex
  string on any line that mentions the jar name in backticks. It fails closed
  today (re-ran it locally: it extracts `79f7b123...46f7` and `sha256sum -c`
  passes). A later prose line carrying another hash would make it pick the
  wrong one. Anchor to the table row (`^| Second target`), and fail when more
  than one distinct hash matches.
- **N2.** `ci.yml:293`: `pip install pyyaml` is unpinned. The compliance
  workflow this job cites as its pattern installs hash-pinned wheels (its
  CI7). Low risk (read-only token, key already deleted), but the job does not
  follow the pattern it names.
- **N3.** `sdk_builder.py:4048`: when javac is missing and the pass is not
  required, validate-sdk prints only the primary "skipping compile check"
  line and no compat box. Minor, but it is the one skip without the loud
  notice.
- **N4.** `.github/release-notes-buildkit.md:64-71`: omits
  `VCFCF_SDK_COMPAT_JAVAC`, and that the default with no jar or JDK 25 is a
  skip. A kit user reading only the notes learns the flags but not that a
  plain `build-sdk` checks nothing.
- **N5.** The compat classpath keeps the 9.0.2-era `alive_common.jar` /
  `alive_platform.jar` (and project `lib/`). Verified: 0 classes overlap the
  2.2 SDK jar, and none provide any of the 12 classes 9.1.1 dropped, so
  nothing is masked today. Nothing guards that, and the pass does not check
  those jars' own 9.1.1 drift. One sentence in the tier2 section stating the
  scope would do.

## Checks re-run

| Check | Result |
|---|---|
| Full suite (`PYTHONPATH=src pytest`) | 2175 passed, 8 skipped (author: 2169 / 14; same 2183 total, environment-dependent skips) |
| `tests/managementpacks/test_sdk_compat_target.py` | 20 passed |
| Seven-package validate chain | all rc 0 |
| `build-framework.sh --compat-only`, jar + JDK 25 | passes; ThreadDeath `[removal]` warning surfaced as documented |
| same, JDK 17 only | boxed skip, rc 0; with `VCFCF_SDK_COMPAT_REQUIRED=1` rc 1 |
| same, no jar, required | rc 1, names the missing jar |
| RollUpType probe in framework source, full `build-framework.sh` | fails, `symbol: class RollUpType`; `vcfcf-adapter-base.jar` sha256 unchanged |
| RollUpType probe in an adapter copy, factory validate-sdk and kit `sdk_buildkit validate-sdk` | both fail, "missing class RollUpType" |
| validate-sdk `--require-sdk-compat` on compliance, unifi, synology, vcommunity, vcommunity-os, vcommunity-vsphere, template (JDK 25) | all pass the 9.1.1.0100 pass |
| Overlap of the other compat-classpath jars with the 2.2 / dropped classes | 0 / 0 |
| Appliance-name leak (B1) | reproduced |
| Kit tarball built with the 9.1.1 jar present in adapter_runtime/ | `sdk-buildkit-1.0.13.tgz`, no `.jar` entries, VERSION 1.0.13 (the command exits 1 afterward on the pre-existing "no reference .pak", tarball already written) |
| `git ls-files` for jars | no binary committed; only `adapter_runtime/PROVENANCE.md` and `reference/docs/vendor-jars/PROVENANCE.md` |
| Em-dashes in added lines | 0 |
| CI job | SHA-pinned (same pins as the existing `test` job), `persist-credentials: false`, `contents: read`, key written umask 077 and removed by an EXIT trap before any repo code runs, host keys byte-identical to compliance's, GitHub-hosted (repo is public, needs no lab: github-ci rule 4); secret absent from this repo, so the job skips with a notice today |

## Not verified

- **Compliance byte-identical with and without the pass (157 classes).** I
  could not run it: the permission system denied the build-sdk pak build.
  From the code, the pass compiles into a `TemporaryDirectory` and never
  touches `build_dir`, so I expect it holds, but I did not observe it.
- **The CI job end to end with the secret.** The secret is not set, and the
  jar is not in the private repo (B2).
- **`JAVA_HOME_25_X64` discovery on a real hosted runner.** It is covered
  only by the unit test with a fake env.

## If shipped as-is

A factory user who copies the jar from an appliance under its own name and
installs JDK 25, as the docs say to, gets a green validate and a pak compiled
against both SDKs. Every tagged pak release builds with the check skipped.
The factory CI job stays green without checking anything until the secret is
added, then goes red because the jar it fetches does not exist.
