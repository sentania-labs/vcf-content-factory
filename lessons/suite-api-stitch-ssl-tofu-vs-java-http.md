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
- `vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/SuiteApiStitchClient.java` — fix site
- SDK class: `com.integrien.alive.common.adapter3.CustomTrustManager`
  (in `vrops-adapters-sdk-2.2.jar`) — confirmed by `javap` inspection
