# Framework review: FIPS cluster truststore on the Suite API hop (issue #215)

- **Reviewer:** framework-reviewer (RULE-013 gate)
- **Date:** 2026-10-18 (America/Chicago)
- **Branch / commit:** `fix/215-fips-cluster-truststore` @ `daff1a6`, base `origin/main` `c433366`
- **Surface:** `src/vcfcf_managementpacks/adapter_framework/` (`VcfCfAdapter.java`,
  `stitch/SuiteApiStitchClient.java`, `test/.../VcfCfAdapterTest.java`) plus
  `knowledge/context/defects.md`, `knowledge/context/tier2_architecture.md`,
  `knowledge/context/api-surface/casa-injected-vs-raw-client.md`
- **Verdict:** **CHANGES REQUESTED** (2 BLOCKING / 2 WARNING / 3 NIT)

## Bottom line

The change does close the loud failure #215 reported: on an `IS_FIPS=true` node
the helper no longer installs trust-all, and every unreadable input fails
closed. Two things stop it shipping. First, the factory now has the vendor's
actual `useClusterTruststore` implementation in bytecode, and it does not read
the inputs this change hardcodes. Because the new FIPS path fails closed, any
mismatch takes Suite API stitching down for every pak on every FIPS node,
including prod, where stitching works today. Second, the one line that caused
#215 (the dispatcher in `openPlatformConnection`) has no test: putting the
trust-all fallback back passes all 37 tests.

## Checks re-run

| Check | Result |
|---|---|
| `build-framework.sh` (worktree) | pass, 20 sources, no aria-ops-core symbols; rebuilt `adapter_runtime/vcfcf-adapter-base.jar` (gitignored) |
| `VcfCfAdapterTest` | 37/37 |
| `CertificateReviewTest` | 86/86 |
| `AmbientCredentialTest` | 28/28 |
| `RelationshipBuilderTest` | 8/8 |
| `SuiteApiStitchClientTest` | 18/18 |
| `SuiteApiStitchRelationshipTest` | 59/59 with 1 group SKIP on SDK-only classpath; **165/165** with `adapter_runtime/lib/*` (log4j) added |
| Seven-package validate chain | pass, 7/7 |
| pytest | 2052 passed / 6 failed / 14 skipped. All 6 are `content/sdk-adapters/<pak>/adapter.yaml not found` in a bare worktree (pak clones are gitignored), the same environmental set earlier reviews recorded. Not caused by this diff. |
| Em-dash scan of added lines | 0 |
| render-regression / pak-compare | n/a (no renderer, builder, or template change) |

### Mutation run (designed by the reviewer, scratch copy under `/tmp/fr215/mut/`)

Each mutation was applied to a copy of `VcfCfAdapter.java`, compiled against the
SDK jar only, and run with the unmodified `VcfCfAdapterTest`.

| ID | Mutation | Result |
|---|---|---|
| M1 | `applyClusterTruststoreTransport` installs `insecureSslContext()` instead of the truststore context | **killed** ("cert NOT in the cluster truststore should have failed (this would mean trust-all)") |
| M2 | `openPlatformConnection` catches the FIPS `IOException`, calls `applyBcMirrorTransport`, and returns the connection (the exact #215 stopgap shape) | **survived, 37/37** |
| M3 | `openPlatformConnection` ignores the FIPS flag (`if (!fips)` becomes `if (true)`) | **survived, 37/37** |
| M4 | `clusterTruststoreSslContext` returns `insecureSslContext()` on `KeyStoreException` | killed |
| M5 | `isFipsModeEnabled()` reads `org.bouncycastle.fips.approved_only` again instead of `IS_FIPS` | survived (test only compares against this host's unset env, so both read null) |
| M6 | trust manager initialised from `null` (JDK cacerts) instead of the cluster store | killed (handshake crashes the suite) |

## Vendor bytecode re-verification

All `javap -c -p -constants`, run by the reviewer.

**Confirmed as claimed (`aria-ops-core-8.0.0.jar`):**
- `Constants.<clinit>`: `FIPS_MODE_ENABLED = Boolean.valueOf(System.getenv("IS_FIPS"))`;
  `SSL_DIRECTORY_PATH = (getProperty("VCOPS_DATA_VCOPS") or Paths.get("/data","vcops"))/user/conf/ssl`;
  `TRUSTSTORE_PATH = .../tcserver.truststore`; `TRUSTSTORE_PASSWORD_PATH = .../storePass.properties`.
- `Constants.getStorePassProperty`: commons-configuration `PropertiesConfiguration`,
  plain key returned when non-null, else `Crypt.getDefaultCrypt().decrypt(<key>.encrypted)`.
- `SuiteAPIClient.getClientConfigBuilder`: FIPS gives `useJson`, `serverUrl`,
  `allowClientToCommunicateWithOlderServers(true)`, `verify("true")`,
  `ignoreHostName(true)`, then `useClusterTruststore(true)` by reflection. Non-FIPS
  gives `verify("false")` and `ignoreHostName(true)`.
- `alive_common` `CaSACertificateStoreConfig`: `IS_FIPS_MODE = Boolean.valueOf(getenv("IS_FIPS"))`,
  store type `BCFKS` if FIPS else `JKS`; default directory recipe
  `${STORAGE}/vcops/user/conf/ssl/` with `tcserver.truststore` / `storePass.properties`.

**Not established, and contradicted by the real implementation:**
- No class in `aria-ops-core-8.0.0.jar` reads `TRUSTSTORE_PATH`,
  `TRUSTSTORE_PASSWORD_PATH`, or `getTrustStorePassword()`. They are defined and
  never used. So "the inputs `Constants` exposes for it" are not the inputs
  `useClusterTruststore` uses.
- The `useClusterTruststore` implementation is in `vcops-suiteapi-client-2.2-all.jar`
  (found on this workstation at
  `~/claude/vcf-mp-cleanroom/analysis/decompiled/mpb-adapter/mpb-adapter/lib/`,
  also under `DiagnosticsAdapter3` and `VMwareInfrastructureHealthAdapter`; it has
  the same `Client$ClientConfig$Builder.useClusterTruststore(boolean)` signature).
  `HttpClientFactory.createClient`, when `verify` is true and no explicit store,
  cert, or socket factory is given and `isUseClusterTruststore()` is set, calls
  `SSLOptions.getSSLOptions(convertConnectionCategory(getOpsConnectionCategory()))`,
  where the builder default category is `VROPS_CLUSTER` (`inter_cluster`, parent `default`).
  `SSLOptions` (static, built once per JVM):
  - root: `STORAGE` (env, then system property), **not** `VCOPS_DATA_VCOPS`;
  - reads `<STORAGE>/vcops/user/conf/ssl/secure-communications.properties`, keys
    under prefixes `default.inter_cluster.` then `default.`: `store_type`
    (required), `truststore` (path, `%VAR%`/`$VAR` substituted), `protocol`,
    `algorithm`, `supported_protocols`, `supported_cipher_suites` (`TLS_RSA*`
    filtered when `IS_FIPS`);
  - `truststore_password` (and `.encrypted`, decrypted with `com.vmware.vcops.security.Crypt.dec`);
    the sentinel `%truststore_password%` redirects to `storePass.properties`
    through `CryptUtils.readPasswordProperty`, which tries
    **`ssltruststorePassword.encrypted` first**, then the plain key.

## BLOCKING

### B1. The FIPS trust anchors are reconstructed, not mirrored, and the mismatch fails closed on prod

- **Where:** `VcfCfAdapter.java` `openPlatformConnection` FIPS branch,
  `clusterSslDirectory`, `FIPS_TRUSTSTORE_TYPE`, `readTrustStorePassword`
  (about lines 1162-1405); the matching claims in
  `casa-injected-vs-raw-client.md` §3 ("Framework mirror ... uses the `Constants`
  inputs") and `tier2_architecture.md` ("Inputs, from vendor `Constants`").
- **Authority:** `knowledge/rules/source-of-truth.md` (RULE-001); the DEF-005
  "mirror BC exactly" directive in `knowledge/context/defects.md`; vendor bytecode
  above (`HttpClientFactory.createClient`, `SSLOptions.<clinit>`/`<init>`,
  `CryptUtils.readPasswordProperty`).
- **What is wrong:** the code reads `$VCOPS_DATA_VCOPS/user/conf/ssl/tcserver.truststore`
  as `BCFKS` and resolves the password plain-first. The vendor resolves the
  truststore path, its type, and its password from
  `$STORAGE/vcops/user/conf/ssl/secure-communications.properties`
  (`default.inter_cluster.*` / `default.*`), with `.encrypted`-first ordering on
  `storePass.properties`. These may coincide on a real node, but nothing in the
  repo shows that they do. The author's own doc already flags the root spelling
  (`STORAGE` vs `VCOPS_DATA_VCOPS`) as live-only.
- **Which output path regresses:** every Tier 2 pak's Suite API hop on any
  `IS_FIPS=true` node (prod 9.1.1, remote collectors). Today that hop works
  through trust-all. With this change, a wrong root, type, file, or password
  order makes every token acquire and stitch write fail, so stitched
  properties, stats, and relationships stop. The framework WARN appears once per
  instance and the stitch client WARNs per call, so it is loud, not silent. It
  is still an outage, and it replaces a working, vendor-equivalent posture with
  a guess.
- **Smallest correct fix:** either (a) mirror `SSLOptions` resolution for the
  `VROPS_CLUSTER` category: `STORAGE` root, `secure-communications.properties`
  prefix lookup, `store_type`, `truststore` with variable substitution,
  `truststore_password[.encrypted]` with the `%truststore_password%` redirect to
  `storePass.properties` `.encrypted`-first. Keep fail-closed. Or (b) keep the
  current code only after a read-only capture from a FIPS node (prod collector01
  and a devel FIPS node) shows that `secure-communications.properties` resolves to exactly
  `tcserver.truststore`, `BCFKS`, and the `%truststore_password%` redirect, and
  that `VCOPS_DATA_VCOPS` and `STORAGE` point at the same directory. Record the
  values (never the password) in the casa doc. In both cases, correct the three
  docs to cite `vcops-suiteapi-client` `HttpClientFactory`/`SSLOptions` as the
  ground truth, and commit or register that jar's provenance so the citation is
  reproducible (`knowledge/rules/cited-artifacts-reproducible.md`, RULE-015).

### B2. The #215 downgrade site is untested: re-adding the trust-all fallback passes every test

- **Where:** `VcfCfAdapter.java:1162-1186` (the `if (!fips)` dispatch and the
  `catch (IOException) { WARN; throw e; }`); `VcfCfAdapterTest` class javadoc
  says `openPlatformConnection` itself is not exercised.
- **Authority:** framework-reviewer dimension 10 (a behavior matching a known
  escape pattern stays BLOCKING until covered); issue #215 (the escape was a
  silent trust-all fallback in this method); reviewer doctrine, "unproven is a finding".
- **Evidence:** mutations M2 (swallow the exception and fall back to
  `applyBcMirrorTransport`) and M3 (ignore the flag) both pass 37/37. The tests
  cover the helpers, but the decision that put trust-all on FIPS nodes before
  this fix is still unguarded.
- **Smallest correct fix:** move the dispatch into a static, instance-free
  helper that `openPlatformConnection` calls with only `https`, `fips`,
  `sslDir`, store type, decryptor, and a failure callback for the once-per-instance
  WARN. Test three cases: (1) `fips=true` and missing store throws, and the
  connection still has the JDK default factory and verifier; (2) `fips=true` and
  an out-of-store server cert fails the handshake; (3) `fips=false` installs
  trust-all and the all-true verifier. Re-run M2 and M3 to show both are killed.
  Also add a case for M5 (detection ignores `approved_only=true` when
  `IS_FIPS` is unset) using the two-argument `isFipsModeEnabled(String)` with a
  property-set scenario, or a `describeTransportMode`-level assertion.

## WARNING

### W1. The SSLContext and BCFKS store are rebuilt on every Suite API request

- **Where:** `openPlatformConnection` FIPS branch to `clusterTruststoreSslContext`
  (every token acquire, datastore page, and stitch write).
- **Authority:** vendor `SSLOptions` is a static per-JVM map and the vendor
  builds its socket factory once per `Client` (bytecode above); DEF-005 mirror
  directive.
- **Why it matters:** BCFKS load runs PBKDF2 key derivation under the FIPS
  provider. A new `SSLContext` per call also defeats `HttpsURLConnection`
  keep-alive (the cache is keyed on the socket factory), so every request is a
  full handshake. The non-FIPS path already pays the second cost; the first is
  new, unmeasured, and not what the vendor does.
- **Fix:** cache the context keyed on the truststore and password file
  `(path, lastModified, size)` so rotation is still picked up, or measure
  per-cycle cost on a FIPS devel node and record it as acceptable.

### W2. Buildkit version not bumped, so the fix has no delivery vehicle

- **Where:** `src/vcfcf_managementpacks/buildkit.py:85` `BUILDKIT_VERSION = "1.0.11"`;
  `tier2_architecture.md` changelog row 2026-10-18 has no **Versioning:** line.
- **Authority:** framework-reviewer dimension 9 (the version signal, not just
  the artifact); the `buildkit.py` comment "bump when kit contents change"; the
  convention in prior changelog rows (2026-10-02, 2026-09-25).
- **Evidence:** `sdk-buildkit-v1.0.11` is already tagged and is an ancestor of
  `c433366`. Paks' `build-pak-on-tag.yml` follow the floating `sdk-buildkit-v1`
  and compile the framework from the kit's source. Until a new kit is cut,
  every pak release keeps building the trust-all-on-FIPS framework, and nothing
  tells anyone the 1.0.11 kit is superseded.
- **Fix:** bump to `1.0.12` in this branch (or state explicitly in the
  changelog row that the bump is release-step owned) and add the Versioning
  line. Note that each Tier 2 pak needs a rebuild on the new kit.

## NIT

- **N1.** `clusterTruststoreSslContext` load failure embeds `e.toString()` of
  the keystore exception, while the decrypt path deliberately logs the class
  name only "because a decrypt exception message is not trusted to be free of
  secret material". JDK and BC load messages observed here carry no secret
  ("keystore password was incorrect"), but the two postures disagree. Pick one.
- **N2.** `clusterSslDirectory()` is now evaluated on the non-FIPS path too. A
  malformed `VCOPS_DATA_VCOPS` (`InvalidPathException`) would newly break the
  non-FIPS Suite API hop, which before did not depend on it. Compute it only
  when `fips` is true, or catch it in the log line.
- **N3.** In FIPS mode the vendor also filters `TLS_RSA*` cipher suites and
  applies the configured `protocol`/`supported_protocols`. The framework uses
  JVM defaults. Under BCJSSE approved-only those are FIPS-approved anyway, so
  this is a parity note, not a risk. Fold it into B1(a) if that route is taken.

## Proven safe

- **Non-FIPS behavior:** `applyBcMirrorTransport` and `insecureSslContext`
  bodies are byte-identical to `c433366` (extracted-method diff). A non-FIPS
  call still installs trust-all plus the all-true verifier. The only delta is
  logging: the old WARN (fired on `approved_only=true`) is gone and a
  once-per-instance INFO mode line is added. That matches the vendor, which
  never reads `approved_only`.
- **Flag reading:** `Boolean.parseBoolean(System.getenv("IS_FIPS"))` matches
  vendor `Boolean.valueOf` semantics (case-insensitive "true" only, no trim).
  Env names are case-sensitive on Linux in both. The env is JVM-constant, so
  per-call reading is equivalent to the vendor's clinit read.
- **No second Suite API path:** framework callers all go through
  `urlConnRequest` to `openPlatformConnection`. Every pak in
  `content/sdk-adapters/*` reaches the Suite API only through `SuiteApiStitcher`
  (compliance `testSuiteApi`/`suiteApi`, unifi `UniFiStitcher`, vcommunity
  `SolutionConfigStore`). `HttpClientBuilder` and the remaining
  `insecureSslContext()` callers (vcommunity) target vCenter, not the Suite API.
  No code sets a default socket factory or verifier.
- **No reuse of a trust-all socket:** each FIPS call builds a new factory, and
  the JDK keep-alive cache matches on factory, so no pooled socket from a
  trust-all connection can be handed to a FIPS connection.
- **Failure propagation:** the `IOException` is rethrown, not swallowed.
  `pushProperties`/`pushStats`/`addChild(ren)`/`findSingletonResourceId` catch
  it and log one WARN per call (`isExpectedFailure` treats it as expected, so
  no stack trace). `get()` propagates it to pak code, which already handles
  `IOException` (degrade or reuse cache). Non-IOException paths (`LinkageError`
  from a missing `Crypt`, `IllegalArgumentException` from a malformed
  properties file) are converted to `IOException`. Nothing new can crash the
  collect cycle.
- **Thread safety:** both once-flags are instance `AtomicBoolean`s using
  `compareAndSet`.
- **Password hygiene:** never logged. Error messages name the file and key,
  decrypt failures carry the class name only, and the `char[]` is zeroed after load.
- **Target-system TLS:** no hunk touches `HttpClientBuilder`,
  `getPlatformSslContext`, or the certificate-review path.
- **Stale-zip (dimension 9, content side):** none of the CLAUDE.md
  "after tooling changes" files are touched, so no `content-packager` rebuild
  of content bundles is owed. The pak-side delivery is W2.

## Live proof still owed (priority order, all read-only unless noted)

1. **Prod collector01: is it actually `IS_FIPS=true`?** The #215 evidence was the
   `approved_only` property, not `IS_FIPS`. Read the collector JVM's environment
   (`/proc/<collector pid>/environ`) for `IS_FIPS` and `STORAGE`, and its
   `-DVCOPS_DATA_VCOPS`. If `IS_FIPS` is unset, this change leaves prod on
   trust-all, the same as the vendor, and #215's premise needs restating.
2. **Prod and a devel FIPS node: capture `secure-communications.properties`**
   `default.*` and `default.inter_cluster.*` for `store_type`, `truststore`, and
   `truststore_password` (record only whether it is the `%truststore_password%`
   sentinel, never a value). Also capture whether `storePass.properties` carries
   plain, `.encrypted`, or both keys (names only), and confirm the collector
   user can read both files. This closes or confirms B1.
3. **Devel FIPS node, positive:** a pak built on this framework logs
   `mode=FIPS`, then token acquire plus a stitch write succeed, with no WARN.
   This exercises BCFKS under the BC FIPS provider and the platform `Crypt`
   decrypt, which no off-collector test can reach (tests use PKCS12).
4. **Devel FIPS node, negative:** an explicit-credential instance pointed at a
   host whose cert is not in the cluster truststore. Expect the one framework
   WARN and per-call stitch WARNs (PKIX), with no successful write. This proves
   no trust-all on the live path.
5. **Remote collector on FIPS (tunnelled `localhost`):** the cluster truststore
   and `storePass.properties` exist and are readable there.
6. **Cost:** per-cycle Suite API timing on FIPS, with W1's per-call BCFKS
   load, compared against non-FIPS.
7. **Non-FIPS regression on devel:** `mode=non-FIPS` INFO line, and stitching unchanged.

## If shipped as-is

On a FIPS node, Suite API stitching either works (if the guessed
`VCOPS_DATA_VCOPS` / `tcserver.truststore` / BCFKS / plain-first inputs happen to
match what the platform configures) or stops entirely, with one WARN per
instance and one per call. Nothing in the repo says which. In either case a
future edit that brings back the trust-all fallback would pass CI. Non-FIPS
nodes are unaffected.
