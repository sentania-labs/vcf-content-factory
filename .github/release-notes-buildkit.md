Portable Tier 2 SDK adapter build toolchain (jar-free).

## Consumer contract

The kit compiles adapters against `vrops-adapters-sdk-2.2.jar` which
**you must supply**. It is a Broadcom internal build artifact with no
public redistribution channel and must not ship in a public toolchain
tarball (see redistribution survey 2026-06-09).

**How to obtain the SDK JAR (pick one):**
1. Extract from your VCF Ops appliance:
   `scp root@<appliance>:/usr/lib/vmware-vcops/common-lib/vrops-adapters-sdk-2.2.jar .`
   (also present at `/usr/lib/vmware-vcops/suite-api/WEB-INF/lib/vrops-adapters-sdk.jar`)
2. Pull from the Broadcom TAP / partner SDK portal (if you have access).

**CI usage (adapter repo's build workflow):**

```yaml
- name: Download sdk-buildkit
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    gh release download @FLOATING_TAG@ \
      --repo sentania-labs/vcf-content-factory \
      --pattern 'sdk-buildkit-*.tgz*'
    sha256sum -c sdk-buildkit-*.tgz.sha256   # verify before use
    tar xzf sdk-buildkit-*.tgz

- name: Build adapter pak
  env:
    VCFCF_SDK_JAR: ${{ secrets.VCFCF_SDK_JAR_PATH }}   # path to vrops-adapters-sdk-2.2.jar
  run: python3 -m sdk_buildkit build-sdk .
```

## Version pinning
- **Exact pin**: `@REF_NAME@`
- **Floating major**: `@FLOATING_TAG@`
  (always points at the latest backwards-compatible release of this major)

## Checksum

Each release carries `sdk-buildkit-<version>.tgz.sha256` (sha256sum
format) next to the tarball. Download both and run `sha256sum -c` before
extracting. A pattern of `sdk-buildkit-*.tgz` alone does not fetch the
checksum file.

## Behavior since 1.0.11

- `pak-compare` gates against the closest reference pak: it exits 1 when
  that reference reports any BLOCKING finding, or when the comparison
  cannot run.
- `build-sdk` applies the same rule and fails the build on a BLOCKING
  finding by default. `--pak-compare-warn-only` restores the old
  warn-and-continue behavior for local experiments and is refused
  together with `--release`; `--release` builds also fail when no
  reference pak is available.
- javac runs with `-proc:none`: annotation processors in classpath jars
  never run.

A workflow that ran the old kit and relied on grepping the compare output
for "0 BLOCKING" now also fails on the exit code; under `set -o pipefail`
that is the intended gate.

## Behavior since 1.0.16

- The adapter framework no longer references `java.lang.ThreadDeath`
  (deprecated for removal on Java 25 collectors, factory #242): the
  catch is `VirtualMachineError` plus a name-matched thread-kill check,
  with the same Java 17 behaviour, and the thread's interrupt status is
  restored when a certificate hook is interrupted. A pak rebuild on this
  kit picks it up with no source change.
- The framework compatibility pass (`check_framework_sdk_compat`) fails
  on any `[removal]` warning; the framework-plus-adapter pass in
  `build-sdk` and `validate-sdk` still only prints them.

## Behavior since 1.0.17

- Opt-in certificate name checking for pak HTTP connections (#185, #206):
  `VcfCfAdapter.getPlatformSslContext(host)` and
  `HttpClientBuilder.platformSsl(adapter, host)` run the platform chain check
  and then require the certificate to name the dialled host. The no-argument
  forms are unchanged; the Suite API loopback never name-checks.
- Validate Connection certificate text (#205): a protected
  `certificateFailureMessage` hook, neutral default text pointing at the
  accept dialog, name-mismatch text naming the host, and the Allow Insecure
  SSL wording only when the describe declares that field.
- `onCycleStart()` on the adapter base (#221), called once per cycle before
  discovery; `needsRediscovery` is still called exactly once per cycle.
- `HttpClientBuilder.connectTimeout(Duration)` (#222), defaulting to the
  existing timeout, which stays the read budget.
- 1.0.16 is the installer and ThreadDeath round (factory #242); this kit
  carries both.

## Behavior since 1.0.15

- `build-sdk` and `validate-sdk` take `--sdk-compat-jar <path to
  vrops-adapters-sdk-9.1.1.0100.jar>` (or `VCFCF_SDK_COMPAT_JAR`) to compile
  the framework and adapter a second time against the VCF Ops 9.1.1.0100 SDK
  jar on JDK 25+, and `--require-sdk-compat` (or
  `VCFCF_SDK_COMPAT_REQUIRED=1`) to fail instead of warn when that check
  cannot run; the pak itself is still compiled against the 2.2 jar.
- The default is a skip: with no 9.1.1.0100 jar, or no JDK 25+ (looked for
  on PATH, `JAVA_HOME`, `JAVA_HOME_<N>_X64`, or set
  `VCFCF_SDK_COMPAT_JAVAC=/path/to/javac`), a plain `build-sdk` prints a
  warning box and checks nothing against 9.1.1. A `--release` build under
  GitHub Actions also emits a `::warning::` annotation.
- The primary compile takes exactly one SDK jar: a second
  `vrops-adapters-sdk*.jar` beside it in `adapter_runtime/` now stops the
  build.

Version note: 1.0.13 is the defect-gate round (PR #246) and 1.0.14 the
adapter-framework round (PR #248); this is 1.0.15.
