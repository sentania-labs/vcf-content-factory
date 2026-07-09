# Lesson: Suite API Stitch Client SSL — TOFU Trust Manager vs java.net.http.HttpClient

**Confirmed:** devel + prod, VCF Ops 9.0.2 + 9.1, compliance build 45, 2026-06-10.

## What broke

Every Suite API call from `SuiteApiStitchClient` failed with:

```
javax.net.ssl.SSLHandshakeException: PKIX path building failed:
  sun.security.provider.certpath.SunCertPathBuilderException:
  unable to find valid certification path to requested target
```

Credentials resolved correctly. The TOFU notification fired immediately after
each failure:

```
com.integrien.alive.common.adapter3.CustomTrustManager.handleUnknownCertificate
  - Initiating non-disruptive certificate handling for adapter: <uuid>
```

## Root cause

`SuiteApiStitchClient.Builder.build()` called `adapter.getPlatformSslContext()`,
which wraps `AdapterBase.getAdapterTrustManager()` — the platform's
`CustomTrustManager` instance.

`CustomTrustManager` is a TOFU (Trust-On-First-Use) manager. Its
`verifyServerCertificate()` / `validate()` path:
1. Calls `handleUnknownCertificate()` as a side-effect notification (tells the
   platform to register the cert for future TOFU approval).
2. **Always throws `CustomCertificateException`** for any cert not already in the
   platform's trusted store — including the platform's own self-signed localhost
   cert.

With old `URLConnection` / `getSocketFactory()` paths (used by v1), the platform
intercepts the exception and retries after the cert is registered. With
`java.net.http.HttpClient` (used in v2), the exception propagates directly to
the caller as `SSLHandshakeException`. There is no intercept, no retry.

The JVM default truststore likewise has no knowledge of the platform's
self-signed cert and always fails the same way.

**Both `getPlatformSslContext()` and the JVM default truststore fail** for the
localhost Suite API endpoint when using `java.net.http.HttpClient`.

## Fix

`SuiteApiStitchClient.Builder.build()` now uses `VcfCfAdapter.insecureSslContext()`
(trust-all) for Suite API calls.

**Trust-all is appropriate here because:**
- The endpoint is always `https://localhost/suite-api` (the platform's own node).
- The cert is always the platform's own self-signed cert.
- Loopback-network isolation provides equivalent transport security for this hop.
- There is no third-party cert to validate and no MITM threat on loopback.

## What this does NOT affect

`HttpClientBuilder.platformSsl(this)` — the path for target-system connections
(vCenter, NAS, etc.) — is correct and unchanged. `CustomTrustManager` works there
because the admin approves the cert via the platform UI before collection starts,
so the cert is already in the platform's trusted store when `checkServerTrusted`
is called.

## Generalizable rule

> **`CustomTrustManager` always throws on first contact with any unknown cert
> when used via `java.net.http.HttpClient`.** Only use `getPlatformSslContext()`
> for target-system endpoints where the platform cert approval UI workflow applies.
> For localhost Suite API calls, use `insecureSslContext()`.

## References

- `context/tier2_architecture.md` — transport section, SSL rationale
- `src/vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/SuiteApiStitchClient.java` — fix site
- SDK class: `com.integrien.alive.common.adapter3.CustomTrustManager`
  (in `vrops-adapters-sdk-2.2.jar`) — confirmed by `javap` inspection

## Addendum (2026-07-01) — vindicated live; DEF-005

A later revision (2026-06-30, `designs/suite-api-stitcher-tls-auth-cleanup-v1.md`
§0) tried to have it both ways: route the loopback hop back through the
platform's strict TOFU `CustomTrustManager` via `getSocketFactory()`, betting
that `getSocketFactory()`'s socket factory (unlike `getPlatformSslContext()`'s
vanilla JSSE factory) carries a working TOFU-survival intercept — register the
unknown cert on first contact, then transparently retry.

**Live devel proved that bet wrong.** `context/investigations/synology-b23-devel-pkix-2026-07-01.md`:
the intercept *does* fire (the platform's `NonDisruptiveCertificateHandler`
starts on every cycle), but it **always errors** —
`"Adapter certificate renewal url set is empty"` — because framework
(`com.vcfcf`) adapters declare no certificate-renewal URL set in their
describe/definition. With no renewal URL, the handler can never persist the
cert, so the *next* cycle re-encounters an "unknown" cert and PKIX-fails
again. Forever. Build 19 (pre-rework, `insecureSslContext()` trust-all) never
hit this because it bypassed `CustomTrustManager` entirely — it isn't that
devel's cert became trusted, it's that the strict trust manager was never
consulted.

**This vindicates this lesson's original generalizable rule.** Strict-TOFU on
the loopback Suite API hop cannot self-heal for framework adapters — not
because of a hostname-verifier gap (that was the 2026-06-30 correction's
finding, and it's still true), but because the *persistence* half of TOFU
depends on a platform capability (adapter-declared cert-renewal URL set) that
this framework's adapters do not — and, per the vendor ground truth below,
should not need to — have.

**Filed as `context/defects.md` DEF-005 (blocking)** and fixed by mirroring
the Broadcom vendor transport exactly instead of re-deriving a TOFU posture:
`context/api-surface/casa-injected-vs-raw-client.md` §3 shows (bytecode-proven)
that `aria-ops-core SuiteAPIClient.getClientConfigBuilder()` — the client used
by every shipping Broadcom pak — sets `verify("false")` + `ignoreHostName(true)`
in non-FIPS mode, `useClusterTruststore` under FIPS. No pak, including the
first-party ones, uses the strict TOFU path for this hop. Directive: "mirror
the BC behavior, don't invent new ways of doing things." The fix site
(`VcfCfAdapter.openPlatformConnection`) now applies that trust-all +
ignore-hostname posture unconditionally (no loopback/remote peer-gating — the
vendor doesn't gate either), with the FIPS branch left as a documented TODO
(no `aria-ops-core` dependency available to this framework to replicate
`useClusterTruststore`).

**Updated generalizable rule:** for the loopback (and CP/remote) Suite API
hop, do not re-derive a trust posture from platform primitives — mirror the
vendor `SuiteAPIClient` transport exactly. TOFU via `CustomTrustManager` is
not a safe substitute: its persistence depends on a certificate-renewal URL
set this framework's adapters do not declare.
