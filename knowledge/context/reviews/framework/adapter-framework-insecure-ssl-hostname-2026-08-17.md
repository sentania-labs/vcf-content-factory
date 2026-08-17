# Framework review — `insecureSslContext()` hostname-verification fix (issue #82)

- **Date:** 2026-08-17
- **Area:** `src/vcfops_managementpacks/adapter_framework/`
- **Change:** reimplement the trust-all manager in `VcfCfAdapter.insecureSslContext()`
  as `javax.net.ssl.X509ExtendedTrustManager` (no-op `Socket` / `SSLEngine`
  overloads) so JSSE uses it directly instead of wrapping it in
  `AbstractTrustManagerWrapper`, which re-applies the endpoint identity check.
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 5 WARNING / 4 NIT

## Files touched (verified complete)

`git status --porcelain` shows exactly the three claimed files and nothing else:

```
 M adapter_framework/src/com/vcfcf/adapter/VcfCfAdapter.java
 M adapter_framework/src/com/vcfcf/adapter/http/HttpClientBuilder.java
 M adapter_framework/test/com/vcfcf/adapter/VcfCfAdapterTest.java
```

`adapter_runtime/vcfcf-adapter-base.jar` is gitignored (`.gitignore:32`), was
rebuilt locally, and `javap` confirms the shipped anonymous class now extends
`javax.net.ssl.X509ExtendedTrustManager` with all six check methods. No stale-jar
problem: `sdk_builder._ensure_framework_jar()` rebuilds on mtime drift and the
buildkit ships framework *source*, not the jar.

## Checks re-run independently

| Check | Result |
|---|---|
| `VcfCfAdapterTest` | 11/11 PASS |
| `RelationshipBuilderTest` | 8/8 PASS |
| `AmbientCredentialTest` | 28/28 PASS (**3** environmental SKIPs, not 2) |
| `SuiteApiStitchClientTest` | 18/18 PASS |
| Full `validate` chain (7 packages) | PASS |
| `vcfops_managementpacks validate` Tier 2 | `OK: 6 Tier 2 SDK adapter project(s) valid` |
| Regression test fails on un-fixed code | **PROVEN** (see below) |
| Negative test catches a global disable | **PROVEN** (see below) |

### Claim 3 + 4 — the regression test is real, and it fails on un-fixed code

I copied the framework source to a scratch tree, reverted *only* the trust
manager type and the four extended overloads, recompiled, and re-ran:

```
FAIL: 1/11 tests failed: [insecureSslContext(): handshake against a
hostname-mismatched cert should have succeeded but threw
javax.net.ssl.SSLHandshakeException: (certificate_unknown)
No subject alternative names matching IP address 127.0.0.1 found]
```

That is byte-for-byte the failure in issue #82. The test performs a real TLS
handshake against a live `HttpsServer` on `127.0.0.1` serving a
`CN=wrong.example.com` cert, over `java.net.http.HttpClient`. Not a type
assertion. Claims 3 and 4 confirmed.

### Claim 5 — the negative test is a genuine guard

Simulating a "fix" that turns verification off globally:

```
java -Djdk.internal.httpclient.disableHostnameVerification=true ... VcfCfAdapterTest
FAIL: validating context: handshake against a hostname-mismatched cert still fails
```

The guard fires. Claim 5 confirmed. (Weakness noted as WARNING-4.)

### Highest-severity check — no leak into the non-opt-in paths

- `getPlatformSslContext()` (VcfCfAdapter.java:979) is untouched and builds from
  `getAdapterTrustManager()` (the platform TOFU `CustomTrustManager`). It never
  reaches `insecureSslContext()`. Inert.
- `HttpClientBuilder.platformSsl()` (line 82) delegates to
  `getPlatformSslContext()`. Inert. Only `allowInsecure(true)` (line 100) reaches
  the changed code.
- Every in-repo caller of `insecureSslContext()` is gated on an explicit
  `allowInsecure` opt-in, or is `applyBcMirrorTransport()` (the vendor-mirror
  Suite API hop that already sets an all-true `HostnameVerifier`, so its
  effective behavior is unchanged). The compliance and vcommunity-\*
  `sslSocketFactoryFor()` helpers fall back to the **JDK default** factory when
  the platform context is unavailable, explicitly documented as "never a silent
  fall-through to trust-all". No adapter that did not ask for insecure gets it.
- Constraint check: no `System.setProperty`, no mutable static state, no
  `jdk.internal.httpclient.disableHostnameVerification`. Grep-confirmed.

## WARNING

**W1 — [`VcfCfAdapter.java:1160-1177`] Javadoc scopes the change to
`java.net.http.HttpClient`; measurement shows it also changes the
`HttpsURLConnection` path. Issue #82's "Not affected" list understates the blast
radius.**

I ran the vcommunity caller pattern against the mismatched-cert server on both
builds:

| Probe | pre-fix | post-fix |
|---|---|---|
| A: insecure factory + all-true `HostnameVerifier` | HTTP 200 | HTTP 200 |
| B: insecure factory + **default** `HostnameVerifier` | `SSLHandshakeException` | **HTTP 200** |

Row A is the good news: the four `HttpsURLConnection` adapters
(vcommunity, vcommunity-vsphere, vcommunity-os, compliance `VSphereClient`)
are byte-identical before and after, so signature/binary/behavioral
compatibility for those callers is confirmed. Row B is the finding: `HttpsClient`
sets an endpoint-identification algorithm and therefore skips its own
`checkURLSpoofing` verifier call, deferring to JSSE, which this change now makes
permissive. So the default `HostnameVerifier` no longer protects anyone holding
this factory. No current caller is in that shape (all gate on `allowInsecure`),
which is why this is not BLOCKING, but the javadoc's "Implementation note
(hostname verification with `java.net.http.HttpClient`)" framing actively teaches
the next author that `HttpsURLConnection` is unaffected. That is the same
underclaiming-javadoc failure mode the change is fixing.
→ **Fix:** state in the javadoc that the returned context suppresses hostname
verification on **both** transports, and that the JDK default `HostnameVerifier`
does not restore it on `HttpsURLConnection`. Correct #82's blast-radius section.

**W2 — [`VcfCfAdapter.java:1022`] Stale javadoc in the changed file.**
`openPlatformConnection()`'s javadoc still reads
"`{@link #insecureSslContext()}` (trust-all `{@code X509TrustManager}`)". Wrong
interface as of this diff, in the same file, describing the method that consumes
the change.
→ **Fix:** `X509TrustManager` → `X509ExtendedTrustManager`.

**W3 — [`SuiteApiStitchClient.java:38-39`] Stale limitation claim, and the result
block's justification for keeping the workaround is factually wrong.**
The class javadoc still asserts the `HttpClient` + `insecureSslContext()` path
"could not inject a `HostnameVerifier`" as a live limitation. That is precisely
what this change removes. Separately, `tooling` justified keeping the workaround
with "its peer-gated hostname verifier (loopback all-true, remote strict) is
logic `HttpClient` structurally cannot express". **The peer-gating no longer
exists.** DEF-005 removed it; both `VcfCfAdapter.java:1026-1031` ("Earlier
revisions of this method peer-gated the hostname verifier ... is removed here")
and `SuiteApiStitchClient.java:356-361` ("since DEF-005 the transport no longer
peer-gates") say so explicitly. The verifier is now unconditionally all-true,
which `HttpClient` *can* express after this fix. The *conclusion* (keep
`openPlatformConnection`) is still correct, but for the vendor-mirror reason
(`casa-injected-vs-raw-client.md` §3, DEF-005 "mirror BC exactly"), not the
stated one. The rest of the read is correct: `SuiteApiStitchClient` routes all
calls through `openPlatformConnection()` (line 680) and uses no
`java.net.http.HttpClient`.
→ **Fix:** update the `SuiteApiStitchClient` javadoc to say the underlying gap
is closed and the transport choice is now a vendor-mirror decision, not a
capability limit. Same for `knowledge/lessons/suite-api-stitch-ssl-tofu-vs-java-http.md:104`.

**W4 — [`VcfCfAdapterTest.java:190-206`] The negative test asserts only "some
exception was thrown".** It catches bare `Exception` and sets `threw = true`. A
server that failed to start, a bind refusal, a connect/read timeout, or a DNS
hiccup all pass it. It is a real guard today (proven above), but it will not stay
one.
→ **Fix:** assert the throwable is an `SSLHandshakeException` /
`CertificateException` whose message names the identity failure, not merely that
something threw.

**W5 — [`VcfCfAdapterTest.java:214-238`] `keytool` subprocess has no timeout and
hard-fails the suite if the binary is absent.**
Resolving `keytool` from `System.getProperty("java.home")` rather than `PATH` is
the right call, and pure-Java keypair generation would need `sun.security.x509`
internals (not exported since JDK 9) or a BouncyCastle dependency the clean-room
framework deliberately excludes, so `keytool` is defensible. The problems are:
`p.waitFor()` blocks forever with no timeout and no `destroyForcibly()`; and a
jlink'd or JRE-only `java.home` (no `bin/keytool`) throws `IOException` and reds
the whole suite rather than skipping. Mitigating: no workflow in
`.github/workflows/` runs any Java, so the release runner is not currently
exposed.
→ **Fix:** `p.waitFor(30, TimeUnit.SECONDS)` + `destroyForcibly()` on timeout,
and record a `SKIP` (the pattern `AmbientCredentialTest` already uses for the
absent `Crypt` classes) when the `keytool` binary does not exist.

## NIT

- **N1** — `tooling` reported `AmbientCredentialTest` "28/28 (2 environmental
  SKIPs)"; the run emits **3** SKIP lines (encrypted round trip,
  injected-credential assertions, `load(cfg)` end-to-end). Claim inaccuracy only.
- **N2** — `buildkit.py:76` `BUILDKIT_VERSION` stays `1.0.9` despite a meaningful
  change to bundled framework source. Per
  `knowledge/context/reviews/framework/buildkit-vendored-import.md:126` this is
  cosmetic (the CI release version is tag-driven from the `sdk-buildkit-v*` tag),
  so NIT. But the fix only reaches the reporting user after an `sdk-buildkit-v*`
  republish **and** a re-release of synology / unifi / compliance. The PR body
  should say so.
- **N3** — No changelog row added to `knowledge/context/tier2_architecture.md`,
  though the analogous 2026-06-30 SSL transport fix has one (line 506).
- **N4** — `withMismatchedCertServer`'s `finally` deletes the `.p12` then the
  directory; any extra artifact makes the directory delete throw from the
  `finally` and mask the real failure. Use a recursive delete.

## Dimension walk

| # | Dimension | Result |
|---|---|---|
| 1 | Global-default / pak-specific leak (`00d3382`) | Clean. Change is confined to `insecureSslContext()`, reachable only via explicit `allowInsecure` or the vendor-mirror Suite API hop. `platformSsl` / TOFU proven inert. |
| 2 | Key / label derivation collisions (`6c59f6b`) | n/a. |
| 3 | Wire-format conformance | n/a — no emitted JSON/XML touched. |
| 4 | Loader / validator correctness | n/a. Full chain re-run green. |
| 5 | Render regression | n/a — `render.py` untouched. |
| 6 | Builder / pak structure | n/a. All 6 Tier 2 adapters recompile. |
| 7 | Corpus regression | Green: 7-package validate chain + 65 Java assertions. |
| 8 | Silent capability change / downgrade | **W1** — a real widening on the `HttpsURLConnection` path, loud in effect but silent in the docs. Not BLOCKING: no non-opt-in caller reaches it. |
| 9 | Stale-zip discipline | dist zips **not** stale (no `templates/`, `builder.py`, `discrete_builder.py`, `release_builder.py`, or `render.py` change). The sdk-buildkit tarball **is** stale — see N2. |
| 10 | Test coverage | Strong. Real handshake, proven to fail on un-fixed code, plus a proven negative guard. Robustness gaps in W4/W5. |

## If shipped as-is

The Synology user gets a working collection against a hostname-mismatched
self-signed cert once the buildkit is republished and the pak re-released;
nothing else changes behavior. The residual risk is documentary: three javadoc
sites and one lesson still describe a limitation this change removed, and the
`insecureSslContext()` javadoc tells the next author that `HttpsURLConnection`
callers are unaffected when they are not.
