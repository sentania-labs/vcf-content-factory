# Framework review: SDK jar version.build names (2026-11-11)

- Branch: `tooling/sdk-jar-version-build-names`, commits `9b8d69e`, `e93d77d`, `dac1585`
  on merge base `ca094e7` (origin/main). Reviewed in worktree
  `.claude/worktrees/agent-a5b6620204a1779f7` only.
- Area: `src/vcfcf_managementpacks/` (sdk_builder, buildkit, cli,
  adapter_framework shell scripts, Java comments), `.github/workflows/ci.yml`
  `sdk-compat`, `.github/release-notes-buildkit.md`, PROVENANCE.md, docs.
- Verdict: **APPROVE** (0 BLOCKING, 2 WARNING, 5 NIT). Per delegation rule 9
  every finding below is to be fixed before the PR opens.

## What was re-run (independently)

| Check | Result |
|---|---|
| Full suite `pytest -m ""`, merge base (archive of `ca094e7`) | 20 failed / 3581 passed / 13 skipped |
| Full suite `pytest -m ""`, branch worktree | 20 failed / 3636 passed / 13 skipped |
| Failure sets | identical (same 20 node ids; real-corpus publish/naming, doctor venv, JMESPath predicates). Not 14 on this run; none in the touched area |
| Validate chain (7 packages), base and branch | all rc=0; outputs identical apart from the absolute path in one UserWarning |
| Pak output, `template` adapter: base (jar in `adapter_runtime/` as `-2.2.jar`; and `--sdk-jar`) vs branch (old name, new name, appliance name `vrops-adapters-sdk.jar`, `--sdk-jar whatever.jar`, `VCFCF_SDK_JAR` old and new name), every leaf of pak, `adapters.zip`, nested jars and `overview.packed` | base vs branch: only `conf/version.txt` and `vcfcf-adapter-base.jar!/META-INF/MANIFEST.MF` (`X-Vcfcf-Source-Commit` = the scratch tree's commit, changes on any commit). All six branch placements byte-identical leaves to each other |
| Same, `compliance` adapter (base runtime vs branch runtime new name vs branch `--sdk-jar` arbitrary name) | same result |
| `Adapter-Version-Ref` stamped | base: `2.2` (runtime) / `N/A` (`--sdk-jar`); branch: `9.0.2.0.25137845` in all six placements |
| pak-compare branch pak vs base pak | 0 BLOCKING, 0 WARNING, 0 INFO |
| Java diff | comment-only (no non-comment line changed); framework class bytes identical |
| Kit assembled (`build-buildkit`, no SDK jar in `adapter_runtime/`) | ok; publish workflow's Broadcom-jar name grep over the tarball: no match. Kit's no-jar message, `--sdk-jar` help and consumer text carry the new path and JDK 17+ |
| Kit build with fake javac 11 | stops before compiling: "javac 11 cannot read the SDK jar ... (VCF Operations 9.0.2.0 build 25137845 (9.0 line)) ... needs JDK 17" |
| Kit build with javac whose `-version` is unparseable | check is a no-op, build succeeds |
| Kit build with a non-zip `--sdk-jar` | check is a no-op; javac reports "zip END header not found" |
| CI `sdk-compat` rows, locally | runtime pin `cff8dbd` verified on GitHub: tree holds exactly the three new names, git blob ids equal to the old names' blobs at `b92956c` and to the local jars. Verify step simulated against the real PROVENANCE.md: one hash per row, `sha256sum -c` OK for all three. `build-framework.sh --compat-only` with `VCFCF_SDK_COMPAT_REQUIRED=1`: 8.18.7 row rc=0, 9.0 row rc=0; 9.1.1.0100 row rc=3 here (no JDK 25 on this host, expected) |
| `run_stitch_tests.sh` | new-name default lookup passes (59/59, log4j group skipped with ALLOW_SKIP); 9.1 jar on JDK 17 exits 3 with the plain message |
| Placeholders in release notes | `@FLOATING_TAG@` 2/2, `@REF_NAME@` 2/2, `@VERSION@` 2/2 (base/branch) |
| Hash and version.build strings | the four sha256 values and the version/build strings are identical in sdk_builder.py, PROVENANCE.md, release notes and tier2_architecture.md; ci.yml reads PROVENANCE.md |

What only a hosted CI run can show: the 9.1.1.0100 row on JDK 25, the
deploy-key fetch at `cff8dbd`, and the stitch suites with the Maven log4j
jars. What I could not verify at all: the 9.0.2.0200 jar's sha256
(`a8e9ebbd…119b`); no copy exists off the appliance and I do not touch live
instances. It is consistent in all five places and with the dated read-out.

## Adapter-Version-Ref consumers

- Appliance side (javap over the local jars): `aria-ops-core`
  `UnlicensedAdapter.logAdapterInformation` reads it with
  `PropertiesFile.getProperty` and concatenates it into a log line; no
  parse. `alive_platform` `AdapterLoader` reads Major/Minor/Maintenance/HF/
  Implementation-Version only. The MPB `Version` class only writes it. The
  SDK jar and `vcfcf-adapter-base.jar` never read it.
- Repo side: nothing parses it (pak_compare, docs_gen, validators). Tier 1
  `builder.py` writes its own constant.
- Values: known jar under any name gives its `<version>.<build>`; the 0200
  jar gives `9.0.2.0200.25431135` (tested with stub hash); unknown jar with a
  `<v>.<build>` name gives the name; unknown with no build in the name gives
  `unknown`; no jar gives `N/A`. A five-part dotted string breaks nothing found.

## Findings

### WARNING 1: the PROVENANCE tie test does not notice a missing main-table row

`tests/managementpacks/test_sdk_compat_target.py:926-946`. The test looks
each name up in any `|` row. The 9.0.2.0, 8.18.7 and 9.1.1.0100 jars also
appear, under both names, in the "Former names" table, so deleting their
rows from the main compile-target table leaves the test green, and CI's
verify step green too (it reads the same rows). Mutation run: deleting all
three `| Primary` / `| Compat leg` rows from PROVENANCE.md, then running the
test: **1 passed**. A wrong hash, a missing 0200 row, a missing former-name
row and a wrong hash in sdk_builder.py all fail it, as they should.
Fix: also assert that each known jar's current name appears in exactly one
row of the main table (the one whose first column is a role), with its hash.

### WARNING 2: a javac too old for a non-9.0 primary jar is told to upgrade the JDK

`src/vcfcf_managementpacks/sdk_builder.py:669-692` and
`src/vcfcf_managementpacks/adapter_framework/build-framework.sh:229-232`.
Scenario: `adapter_runtime/vrops-adapters-sdk-9.0.2.0.25137845.jar` holds the
9.1.1.0100 bytes (or `VCFCF_SDK_JAR` is the 9.1 jar), JDK 17. Python says
"... (VCF Operations 9.1.1.0100 build 25795063 (9.1.1.0100 line)) ... Install
JDK 25 or newer". The shell says "cannot read vrops-adapters-sdk-9.0.2.0.25137845.jar
(the 9.0 line's SDK jar) ... Install JDK 25+", which states the line from the
file name only. Following that advice gives a pak whose shipped classes are
compiled against the 9.1 jar, with only a SKIPPED notice for the 9.0 leg
(non-required build). The fix being suggested is the wrong one.
Fix: when the primary jar's sha256 is a known non-9.0 jar, say it is the
wrong jar and name the 9.0.2 jars instead of a JDK upgrade. In the shell,
drop "(the 9.0 line's SDK jar)" or say "named as".

### NIT 1: the CI matrix test accepts a former name the pinned runtime repo lacks

`tests/managementpacks/test_sdk_compat_target.py:905` checks
`leg["jar"] in lines[...].names`, current or former. At pin `cff8dbd` only
the current names exist, so a row reverted to `vrops-adapters-sdk-2.2.jar`
passes the test and fails CI. Fix: assert `leg["jar"] == line.jar_name`.

### NIT 2: contradictory INFO lines for a former name with unknown bytes

`sdk_builder.py:586-597` (`_note_former_name`) prints "vrops-adapters-sdk-2.2.jar
is the former name of vrops-adapters-sdk-9.0.2.0.25137845.jar (VCF Operations
9.0.2.0 build 25137845); it still works" from the name alone. Then
`_adapter_version_ref` prints "its sha256 matches no known SDK jar ...
Adapter-Version-Ref=unknown". Fix: print the former-name line only when the
bytes match that jar, or say "named as".

### NIT 3: "accepted, by sha256" reads as a check that does not exist

`sdk_builder.py:532` (`_SDK_JAR_HOWTO`, shown in every no-jar message and in
the kit), `src/vcfcf_managementpacks/README.md:223`. Any jar is accepted as
the compile target. The sha256 only decides the 9.0 leg and
`Adapter-Version-Ref`. The Consumer contract states this correctly ("It
still compiles, but the 9.0 leg reports it as an unknown jar"). Fix: "either
is recognised by its sha256".

### NIT 4: no adoption note for pak repos that bump the runtime pin

`.github/release-notes-buildkit.md:63`. Every live pak repo
(`template`, `compliance`, `synology`, `unifi`, `vsanperf` on GitHub) pins
`SDK_RUNTIME_COMMIT: b92956c…` with `SDK_JAR: vrops-adapters-sdk-2.2.jar`.
They keep working, as the bullet says. A repo that moves its pin to
`cff8dbd` must rename `SDK_JAR` in the same change, or the build stops on a
missing file. Fix: one sentence in the Adoption bullet.

### NIT 5: normative text still treats "2.2" as an SDK version or file

Untouched by the branch (follow-up eligible):
- `knowledge/lessons/sdk-constants-are-display-names.md:72`: the minimum
  reproducer runs `javap -classpath vrops-adapters-sdk-2.2.jar`.
- `.claude/skills/vcfops-sdk-adapter/SKILL.md:245` and
  `src/vcfcf_managementpacks/sdk_project.py:79` call it "SDK 2.2 (9.0)".

Dated investigation notes, reviews, the cleanroom spec and the dated rows of
tier2_architecture.md keep the old names, as expected. These are not reported.

## Proven safe (no finding)

- Global vs pak-specific leak (anchor `00d3382`): all six jar placements give
  identical pak leaves. Only `conf/version.txt` changed from base, as the
  owner accepted.
- Key/label collisions (anchor `6c59f6b`): not applicable. No rendered key
  derivation was touched. The `Adapter-Version-Ref` derivation comes from the
  hash, not the name, which is the point of the change.
- "Exactly one primary SDK jar": former-named compat jars are excluded from
  the candidates (code plus tests). Both names of the 9.0 jar side by side,
  or both 9.0 builds side by side, error in Python and in the shell alike.
  Both names of a compat jar side by side: the current name is used and the
  former one ignored.
- Shell/Python agreement: name lists are test-tied. Known existing gap: the
  shell accepts only the three 9.0 names, while Python accepts any
  `vrops-adapters-sdk*.jar`. The shell was stricter on the base as well
  (2.2 only).
- javac check: major = class-file major - 44 (55/61/69 to 11/17/25,
  correct). Unparseable javac, no class files, or not a zip: no-op. A newer
  JDK passes. Known SDK jars are uniform-major with no multi-release entries,
  so the max-major rule cannot reject a jar javac could read.
- Stale-zip / template version (dim 9): no touched path in the rebuild list
  (`vcfcf_packaging/templates`, packaging builders, `assembly.py`,
  dashboards/alerts `render.py`). No content-packager rebuild or
  `CURRENT_TEMPLATE_VERSION` bump is needed. `BUILDKIT_VERSION` stays 1.0.27:
  latest published is v1.0.26, so 1.0.27 is unreleased.
- Publish workflow: name-based Broadcom-jar gate unaffected. Nothing else in
  `.github/workflows/` references the old names or the old pin.
