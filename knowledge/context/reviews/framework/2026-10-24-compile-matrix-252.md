# Framework review: compile matrix, 8.18 leg, `--release 11` (#252)

- **Branch:** `feat/252-compile-matrix-8-18-release-11`, worktree
  `.claude/worktrees/252-compile-matrix`, seven commits on `origin/main`
  8ad0911 (a434e96 .. ee165b6)
- **Area:** `src/vcfcf_managementpacks/` (sdk_builder, cli, buildkit,
  adapter_framework build-framework.sh and ManagedHttpClient.java),
  `.github/workflows/ci.yml`, `adapter_runtime/PROVENANCE.md`, tier2 docs
- **Reviewed:** 2026-10-24, about 00:57 CDT
- **Gate:** RULE-013 (`knowledge/rules/framework-review-gate.md`)

## Verdict: CHANGES REQUESTED

2 BLOCKING, 3 WARNING, 2 NIT.

The mechanics #252 asked for work, and I re-ran them: several legs, a JDK
per leg, every leg runs after one fails, main sources only, `--release 11`
everywhere, the 8.18.7 CI row, and the Java 11 request copy. The problem
is what `--release 11` on every compile costs. Nothing in the build checks
the Java 17 or Java 25 class library any more, and those are what the 9.0
and 9.1 collectors run. Code using an API that Java 12 to 25 removed now
builds green and fails on those collectors. Separately, `--require-sdk-compat`
reports a pass when the 8.18 leg never ran.

## Checks re-run (independently)

| Check | Result |
|---|---|
| CI pytest command (`-n auto --dist=loadgroup --override-ini="addopts=" -m ""`, pak clones symlinked) | 2669 passed, 8 skipped, 0 failed (123.6 s) |
| New and changed tests (`test_java_release_11.py`, `test_managed_http_client_copy.py`, `test_sdk_compat_target.py`) | 59 passed, 0 skipped |
| Seven-package validate chain | all rc 0 (managementpacks: 3 Tier 2 projects valid) |
| `build-sdk` compliance (copy in scratch; pak clone untouched), both `--sdk-compat-jar`, `--require-sdk-compat` | rc 0. 8.18.7 leg on javac 17, 9.1.1.0100 leg on javac 25.0.5, both `--release 11` |
| Class majors in the built pak | all 160 classes major 55 (110 in `vcfcf_compliance.jar`, 50 in `lib/vcfcf-adapter-base.jar`). Shipped `ManagedHttpClient` calls only `newBuilder()` and `newBuilder(URI)` |
| Probes through the real `_sdk_compat_check`, both jars, required | 2.2-only member `AdapterBase.getCertificateRenewalUrls` fails the 8.18 leg; 2.2-only class `RollUpType` fails the 9.1.1 leg; 9.1.1-only class `CalculationModelDescribe` **compiles on the 9.1.1 leg** (javac 25 `--release 11` really reads the major-69 jar) and fails the 8.18 leg; `String.indent` (12), `Stream.toList` and `HttpRequest.newBuilder(HttpRequest, BiPredicate)` (16) fail both legs. Each time the other leg still ran |
| JDK 17 only, 9.1.1 jar supplied | not required: 8.18 leg runs and 9.1.1 skips with the boxed banner, returns False. Required: `SdkCompatUnavailable` naming 9.1.1 only, plus the 8.18 compile error when there is one |
| `build-framework.sh --compat-only`, replaying both CI rows | 8.18.7 on JDK 17: rc 0. 9.1.1.0100 on JDK 25 (PATH and JAVA_HOME, as setup-java sets them): rc 0. 9.1.1.0100 with only JDK 17: rc 3, loud |
| CI YAML | parses. actionlint shows only the pre-existing `runs-on: lab` label note. The matrix rows differ only in `sdk`, `jdk` and `jar`. Replaying the hash check finds exactly one sha256 per jar in PROVENANCE.md, and `sha256sum -c` passes on the holding-share copies and on the copies in the private sdk-runtime repo |
| All seven Java paks (compliance, synology, template, unifi, vcommunity, -os, -vsphere) plus framework, `javac --release 11` | 0 errors against 2.2 and against 8.18.7 |
| `ManagedHttpClient.copyWithUri` against Java 16 `newBuilder(r, (n,v)->true).uri(ip)` on JDK 17 | equal for GET with headers, HEAD, PATCH with body and timeout, POST with noBody and HTTP_2, DELETE with expect-continue, OPTIONS |
| Broadcom jars in commits | no `*.jar` or `*.class` in any tree of the 7 branch commits |
| Em-dashes added by the diff | none |

## BLOCKING

### B1. `--release 11` on every compile drops the Java 17 and Java 25 library checks (silent downgrade)

`sdk_builder.py` `_sdk_compat_leg` (`"--release", str(_JAVA_RELEASE)`
in the leg's javac command, about line 1011) and `_compile` (about line
744); `build-framework.sh` primary `javac --release 11`.

**Authority:** RULE-019 (`knowledge/rules/supported-platforms.md`, PR
#253): "Use no platform feature a supported line lacks". Review
dimension 8 (silent capability change). The branch's own comment beside
the warnings print ("Newer-JDK warnings (e.g. [removal]) matter: the
9.1.1 collector runs Java 25"). Sibling #242 (commit 3301554), whose
`[removal]` gate rests on that.

**What regresses:** `--release N` makes javac check against JDK N's
class library (from the JDK's `ct.sym` file), not the library of the
JDK that is running. Before this branch, the 9.1.1 leg (`-source 11
-target 11` on JDK 25) checked against Java 25's library, and the primary
compile (JDK 17) checked against Java 17's. Now every compile checks Java
11's library only, so an API that exists in Java 11 but was removed or
marked for removal by the collector's Java passes every compile.
Measured:

- JDK 25 against the 9.1.1.0100 jar, a probe calling
  `java.lang.Compiler.disable()` (removed in Java 21) and
  `java.util.jar.Pack200.newPacker()` (removed in 14): old flags give 2
  errors; `--release 11` gives **rc 0** (two warnings only).
- JDK 25, `catch (ThreadDeath t)` plus `Runtime.runFinalization()`: old
  flags give two `[removal]` warnings; `--release 11` gives **none**.
  The ThreadDeath catch is exactly what #242 fixed, and #242's
  fail-on-`[removal]` gate goes blind once both branches merge.
- JDK 17, `java.rmi.activation.ActivationID` plus
  `Runtime.traceInstructions` (removed in Java 17 and 13): `--release 11`
  gives rc 0; `--release 17` gives 2 errors. The primary compile is the
  only 9.0 (Java 17) check, since there is no 9.0 leg, so the 9.0 line
  lost its library check too.

**Which builds:** every `build-sdk`, `validate-sdk`, `build-framework.sh`
and factory CI `sdk-compat` run. For a pak that ships it, the failure is
a `NoSuchMethodError` or `NoClassDefFoundError` at collection time on 9.0
and 9.1 collectors, after release. That is the failure class this change
exists to prevent, moved from 8.18 onto the other two lines.

**Smallest correct fix:** compile against each line's own Java. The
shipped compile stays `--release 11` (bytecode plus the Java 11 API, for
8.18). Each compat leg compiles with `--release <that line's collector
Java>`, not 11. The jar's class-file version is a workable proxy and the
code already reads it: 8.18.7 gives 11, 9.1.1.0100 gives 25. Add a
non-shipping `--release 17` pass for the 9.0 line (the primary jar), or a
9.0 leg. Correct the leg comment. Test it on JDK 17 in CI: a stub jar at
major 61 plus `java.rmi.activation.ActivationID` must fail the leg (it
passes today). When merging #242, its fail-on-`[removal]` must be ported
into `_sdk_compat_leg`, which only works once the 9.1.1 leg compiles
against Java 25.

### B2. `--require-sdk-compat` passes when a supported line's leg never ran

`sdk_builder.py` `_resolve_compat_sdk_jars` and `_sdk_compat_check`.

**Authority:** RULE-019: "Compile the framework and the adapter against
every supported platform's adapter SDK jar ... `--require-sdk-compat`
makes a leg that cannot run (jar or JDK missing) fail too". Dimension 8.

**What regresses:** the legs are whatever jars the caller supplies. No
list of required lines exists, so a missing jar is never a missing leg.
Measured: `VCFCF_SDK_COMPAT_REQUIRED=1`, `VCFCF_SDK_COMPAT_JAR=<9.1.1
jar>`, source calling `AdapterBase.getCertificateRenewalUrls()` (absent
on 8.18). Result: `sdk-compat: ... compiles against the VCF Ops
9.1.1.0100 SDK jar`, `_sdk_compat_check` returns **True**, and no line
mentions 8.18. The same happens without the flag when `adapter_runtime/`
holds only the 9.1.1 jar: no skip banner for 8.18. This is the pak CI
shape today (and after #250-style adoption, if one jar is forgotten): a
required build reports green while the 8.18 check never ran.

**Smallest correct fix:** treat the known lines (`_SDK_COMPAT_JAR_NAMES`,
better keyed by the PROVENANCE sha256 than by file name) as the expected
set. Print the boxed SKIPPED banner for every expected line no supplied
jar covers. Under `--require-sdk-compat`, fail on it unless the caller
explicitly narrows the set (for example `VCFCF_SDK_COMPAT_LEGS=8.18.7`,
set per factory CI matrix row, so the one-jar-per-row design still
works). Test: required, only the 9.1.1 jar, raises naming 8.18.7.

## WARNING

### W1. The new docs say the 8.18 CI row skips; it will run

`ci.yml` sdk-compat header comment, `PROVENANCE.md` "8.18.7 jar",
`tier2_architecture.md` changelog row and 9.1.1 provenance row,
`src/vcfcf_managementpacks/README.md`, the buildkit doc text.

**Authority:** RULE-001 (source of truth); dimension 3 (a document that
contradicts what runs).

**What's wrong:** these say the 8.18.7 jar enters the private sdk-runtime
repo "with its PR 7", that until then the row "skips with a notice", and
(9.1.1 text) that the jar is "not yet in the private repo ... until #250
... skips". In fact:

- `SDK_RUNTIME_SSH_KEY` is set on this repo (00:18 CDT today).
- #250 is closed.
- sdk-runtime PR 7 (00:17 CDT) and PR 8 (00:29 CDT) are merged.
- The repo holds `vrops-adapters-sdk-2.2.jar`, `-8.18.7.jar` and
  `-9.1.1.0100.jar`. I fetched the two compat jars and they hash to the
  PROVENANCE values.

Both rows will run for real on this PR. My local replay says they pass,
but the docs tell a reader nothing is checked.

**Fix:** rewrite those passages to the current state: key set, both jars
in sdk-runtime, both rows run required.

### W2. Merge collision and kit version with the 1.0.16 branch

Branch `fix/installer-200-244-242-shims-159` holds BUILDKIT_VERSION
1.0.16 and #242.

**Authority:** dimension 9 (the version signal, not only the artifact).

**What's wrong:** `git merge-tree` against that branch conflicts in
`sdk_builder.py`, `tests/managementpacks/test_sdk_compat_target.py` and
`tier2_architecture.md`. #242's `fail_on_removal` targets the single-jar
`_sdk_compat_check` this branch replaces, so a mechanical resolution can
drop it. B1 shows that even ported as-is it detects nothing. This branch
also leaves `BUILDKIT_VERSION` unbumped on the plan that 1.0.16 carries it.

If 1.0.16 is tagged before this merges, the kit's ManagedHttpClient fix
and `--release` change ship under a version string that already names a
different tagged kit. Pak repos pinned to `v1.0.16` would then report
current without carrying either.

**Fix:** state the merge order in the PR body. Whichever branch merges
second bumps to the next kit version and carries #242's gate into the
per-leg code with a test.

### W3. RULE-019 and the 8.18 investigation are cited but not on main

`sdk_builder.py`, `build-framework.sh`, `ci.yml`, `PROVENANCE.md` and
tier2 docs cite RULE-019 and
`knowledge/context/investigations/2026-10-24-devel-8-18-sdk-jar-and-proxy-log.md`.

**Authority:** RULE-001 and RULE-015 (`cited-artifacts-reproducible.md`).

**What's wrong:** both files exist only on PR #253
(`fix/175-view-own-sort-rule-019`, commit ecc6638). If #252 merges
first, every citation dangles, and so does the evidence for the 8.18.7
hash and Java 11 claims.

**Fix:** merge #253 first, or rebase this branch onto it, and say so in
the PR body.

## NIT

### N1. A JDK-library miss is blamed on the SDK jar

`sdk_builder.py` `_sdk_compat_leg` failure message. For `String.indent`
the leg reports "references something that jar lacks or has changed, so
a pak built from it can fail to load on 8.18.7". The missing symbol is
in the Java 11 library, not the SDK jar. A reader goes hunting in the
wrong jar.

**Fix:** when the unresolved symbol's location is `java.*` or `javax.*`
(or the primary compile already failed on it), say "not in the Java
<release> class library".

### N2. Em-dashes in log strings of a touched file

`ManagedHttpClient.java` lines 198 and 272 (`LOG.warning` strings an
operator reads in the collector log), plus comments at 238, 267 and 305.
The branch added none, but it touches this file, and CLAUDE.md rule 9
(fix findings in touched code before the PR) and the no-em-dash rule
apply.

**Fix:** replace them with commas, colons or a period. The many
pre-existing em-dashes elsewhere in `sdk_builder.py` and the docs belong
to a repo-wide sweep, not this PR.

## Proven safe (no finding)

- **Request copy (Java 11 API).** It matches the Java 16 copy on six
  request shapes. Only `ofString` and `noBody` publishers are used in the
  framework and all paks, and both can be reused, so the round-robin loop
  resending one publisher is safe (the Java 16 copy shared it the same
  way). No pak or framework code sets a restricted header or
  `jdk.httpclient.allowRestrictedHeaders`. The restricted list only skips
  headers the original builder on the same JVM had to accept, so a JDK 11
  disallowed-set difference cannot drop a header a pak set.
- **Main sources only.** `_adapter_compat_inputs` takes
  `adapter_framework/src` and `_find_sources(project)`, never
  `adapter_framework/test` or the pak's `tests/`. This is tested.
- **One primary SDK jar.** Both compat names are excluded from primary
  candidates; any other `vrops-adapters-sdk*.jar` still stops the build.
  This is tested, including the 8.18 jar beside 2.2.
- **No leg skipped silently when a jar is supplied.** A missing explicit
  path raises whether or not the run is required. A JDK too old to read
  the jar skips with the boxed banner (and fails when required). Every
  supplied leg runs before the result is raised. B2 is the case where
  the jar is not supplied at all.
- **Dimension 9 stale zips.** No file on the stale-zip list is touched
  (templates, builder.py, discrete/release builders, assembly.py,
  render.py). `CURRENT_TEMPLATE_VERSION` is not affected. The kit
  version is W2.
- **Dimensions 1, 2, 5** (global-default leak, key derivation, render
  regression): not applicable; no renderer or loader change.
- **Worktree `adapter_runtime/`.** It does not hold gitignored copies of
  the compat jars, contrary to the brief: only the 2.2 jar is there. All
  leg runs above passed the holding-share jars explicitly.

## If shipped as-is

Paks build green while using Java APIs that Java 17 or 25 removed, then
fail on 9.0 and 9.1 collectors at collection time. A required pak build
given only the 9.1.1 jar reports success without the 8.18 check ever
running.
