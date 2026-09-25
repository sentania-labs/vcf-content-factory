# TLS `certificate_unknown(46)` on compliance Test Connection (prod, 2026-09-25)

**Question:** Scott hit `org.bouncycastle.tls.TlsFatalAlert: certificate_unknown(46)` in a
Tier 2 SDK pak and asked whether the base layer (`vcfcf-adapter-base.jar`,
`src/vcfcf_managementpacks/adapter_framework/`) can be changed so an admin can accept/trust
the target's certificate.

**Answer:** Yes. The failure is on the **target-system** path (compliance to vCenter), not the
loopback Suite API stitcher. Our own trust manager rejected the vCenter certificate. The
Ops-native "Review and accept certificate" dialog never appeared because the framework never
tells the platform which URL to probe: `AdapterBase.getConnectionURL(s)` is not overridden, so
the platform's pre-test certificate check returns `NOT_SUPPORTED`. A small framework hook
(override `getConnectionURLs` + `getCertificateRenewalUrls`, fed by a per-adapter method)
turns the dialog on. The existing `platformSsl` / `getPlatformSslContext()` transport then
trusts the accepted cert at collection time with no transport change.

Method: read-only SSH log grep on devel, prod .42, prod .43 (collector unreachable: "No route
to host"); Suite API GETs; `javap` on the prod appliance's own `vrops-adapters-sdk.jar`,
`vcops-collector-1.0-SNAPSHOT.jar`, `mpb_adapter-9.1.1-rc-2.jar`, `NSXTAdapter3.jar` (copied
read-only to a scratch dir); `openssl s_client` against appliances and vCenters. Nothing was
created, changed, or accepted on any appliance.

All times America/Chicago.

---

## 1. Where it happened

One occurrence in the last ~24 h across devel, prod node 1 (.42), prod node 2 (.43):

| Field | Value |
|---|---|
| When | Friday 2026-09-25, 10:34:34 AM CDT |
| Node | prod primary `vcf-lab-operations01` (172.27.8.42), collector ID 5 |
| User | `sadmin@int.sentania.net` (bridge log, `testResource`) |
| Operation | UI **Validate Connection** on a **new, unsaved** adapter instance (`Test connection` task, `Details: {AIR=null,ResId={null};}`) |
| Pak | `vcfcf_compliance` (build 79 era; no compliance instance exists on prod per `GET /api/adapters`, consistent with an unsaved test) |
| Code path | `ComplianceAdapter` tester, `VCenterApiClient.login` (`VCenterApiClient.java:54`), `java.net.http.HttpClient`, SSLContext from `getPlatformSslContext()` (`allowInsecure` not set) |
| Target | `https://<vcenter_host>:443` (host not logged; all three lab vCenters present the same chain shape, see below) |
| Direction | **Sent by us.** Our client-side trust manager rejected the server certificate, and BouncyCastle raised `certificate_unknown` locally |

Stack (verbatim, `collector.log` line 40807 on .42, trimmed):

```
WARN [com.vcfcf.adapters.compliance.ComplianceAdapter.logWarn] - onTest: connection test failed: org.bouncycastle.tls.TlsFatalAlert: certificate_unknown(46)
javax.net.ssl.SSLException: org.bouncycastle.tls.TlsFatalAlert: certificate_unknown(46)
	at java.net.http/jdk.internal.net.http.HttpClientImpl.send(Unknown Source)
	at com.vcfcf.adapters.compliance.VCenterApiClient.login(VCenterApiClient.java:54)
	at com.vcfcf.adapters.compliance.ComplianceAdapter.lambda$getTester$0(ComplianceAdapter.java:271)
	at com.vcfcf.adapter.VcfCfAdapter.onTest(VcfCfAdapter.java:633)
	at com.integrien.alive.common.adapter3.AdapterBase.test(AdapterBase.java:1342)
	at com.integrien.alive.collector.Collector.testConnection(Collector.java:1161)
Caused by: org.bouncycastle.tls.TlsFatalAlert: certificate_unknown(46)
	at org.bouncycastle.jsse.provider.ProvSSLEngine.checkServerTrusted(ProvSSLEngine.java:155)
Caused by: com.integrien.alive.common.adapter3.CustomTrustManager$CustomCertificateException: Unable to construct a valid chain
	at com.integrien.alive.common.adapter3.CustomTrustManager.validate(CustomTrustManager.java:517)
	at com.integrien.alive.common.adapter3.CustomTrustManager.checkServerTrusted(CustomTrustManager.java:210)
Caused by: java.security.cert.CertPathBuilderException: No issuer certificate for certificate in certification path found.
```

`ProvSSLEngine.checkServerTrusted` then `CustomTrustManager.checkServerTrusted` is the client
validating the *server's* certificate. A peer-sent alert would surface from
`TlsProtocol.handleAlertMessage`/`receive`, not from our trust manager. **This is not the
loopback Suite API stitcher** (`SuiteApiStitchClient` uses the trust-all BC-mirror transport,
`VcfCfAdapter.openPlatformConnection`, and cannot raise this).

The .43 `web.log` hit and the `vcops-bridge` hits are the same event relayed to the UI. The UI
got the raw string `org.bouncycastle.tls.TlsFatalAlert: certificate_unknown(46)` because
`VcfCfAdapter.onTest` catches everything and `param.setErrorMsg(e.getMessage())`.

**Why the chain failed:** the lab vCenters (`vcf-lab-vcenter-mgmt`, `-wld01`, `-wld02`) each
present leaf + `CN=sentania Lab Issuing 2` and omit `sentania Lab Root 2`. A fresh (unsaved)
instance's `CustomTrustManager` keystore holds neither the issuing CA nor the root, so PKIX
cannot find an anchor ("No issuer certificate ... found"). Note `GET /api/certificate` on
prod already lists `sentania Lab Issuing 2` (accepted earlier by some other adapter instance).
It still didn't help, which is consistent with accepted certs being **per adapter instance**
(section 2), not a global trust list.

No `handleUnknownCertificate` / `NonDisruptive` line was logged. Expected: that path needs a
saved instance UUID (`ownerAdapter.getAdapterInstResource().getResourceUuid()`), and the test
instance had none.

## 2. How VCF Ops is meant to handle an untrusted target cert (bytecode evidence, prod 9.1.1 SDK)

### 2a. Test Connection runs a certificate check first

`com.integrien.alive.collector.Collector.testConnection(TaskTest)` (from the appliance's
`vcops-collector-1.0-SNAPSHOT.jar`):

1. Builds `TestParam` **and** `CheckCertificateParam` from the same unsaved `AdapterConfig`.
2. Calls `adapter.checkCertificate(CheckCertificateParam)` and stores the result on the task
   (`TaskTest.setCheckCertificateResult`). That result is what the UI renders as the
   "Review and accept certificate" dialog.
3. Gate (offsets 293 to 336): if the result carries a **non-empty certificate chain**, stop
   and return it for review. `test()` is **not** called. Only if the chain is empty **and**
   the state is `SUCCESS` or `NOT_SUPPORTED` does it call `adapter.test(TestParam)`.

### 2b. `checkCertificate` probes the URLs the adapter declares

`AdapterBase.checkCertificate` calls `initTrust(...)`, then `onCheckCertificate(param)`.
The default `onCheckCertificate`:

- `urls = getConnectionURLs(adapterConfig)`. The default is `singletonList(getConnectionURL(adapterConfig))`,
  and **the default `getConnectionURL` returns `null`**.
- null/empty/blank URL returns **`NOT_SUPPORTED`**. That is our adapters today.
- For each URL: `getConnection(url, getVerifier())` (an `HttpsConnection` on
  `getSocketFactory()`, the platform `CustomSSLSocketFactory` over the per-instance
  `CustomTrustManager`), then `CertificateChecker.checkCertificate[2]`. Results are merged.
  Unknown cert gives `UNKNOWN_CERTIFICATE` + chain. Other states: `SUCCESS`, `FAILURE`,
  `HOSTNAME_VERIFICATION_FAILED`, `CERTIFICATE_DATE_NOT_VALID`, `REVOKED_CERTIFICATE`.

### 2c. Where accepted certs live and how collection trusts them

- Stored **per adapter instance** as `CertificateConfig` (thumbprint, PEM, `enforceHostnameVerification`,
  `enforceDateValidityChecking`), exposed as `ResourceConfig.getTrustedCertificates()`.
- `CertificateChecker.initTrust(...)` reads `getTrustedCertificates()` into the instance's
  `CustomTrustManager` (`addCertificates`, `setCertificateConfigs`), which rebuilds its PKIX
  `TrustManagerFactory` over a keystore = platform base adapter truststore (JVM property
  `adapter_trust_store_path`, set in-process, file not mapped in this pass) + accepted certs.
- `initTrust` runs in `configure()` (before `applyConfiguration()`, so before our
  `onConfigure`/`configureAdapter`), in `test()` (before `onTest`), in `discover()`, and in
  `checkCertificate()`. So an SSLContext built from `getAdapterTrustManager()` inside
  `configureAdapter` or inside the tester sees the current accepted set.
- `CustomTrustManager.validate`: PKIX check over that keystore. On failure it records
  `rejectedCertificates`, tries `handleUnknownCertificate` (non-disruptive renewal, saved
  instances only), else throws `CustomCertificateException`. It is transport-agnostic: the
  same decision whether reached from `CustomSSLSocketFactory`/`HttpsURLConnection` or from
  `java.net.http.HttpClient` via `SSLContext.init(tm)` (the `SSLEngine` overload lands in the
  same `verifyServerCertificate`/`validate`).
- Public API mirror: `POST /api/adapters/testConnection` returns a `certificates-error`
  (list of `integration-certificates`) when certs need review; `PATCH /api/adapters/testConnection`
  / `PATCH /api/adapters` echo that body back to accept (operations-api.json). The internal
  spec has nothing further for adapter-instance certs.

### 2d. What Broadcom adapters do (prod appliance jars)

- **MPB runtime** (`com.vmware.mpb.MPBAdapter`): overrides `getConnectionURL(AdapterConfig)`.
  It reads `mpb_ssl_config`, `mpb_hostname`, `mpb_port` from the instance identifiers and returns
  `https://host:port` only when SSL mode is `VERIFY` (null for no-SSL/unverified, so the check is
  skipped). Its tester uses `getSocketFactory()`.
- **NSX-T** (`com.vmware.adapter3.nsxt.NSXTAdapter`): overrides `getConnectionURLs(AdapterConfig)`
  (multiple managers) **and** `getCertificateRenewalUrls()`, returning the hosts parsed from
  `getConnectionURLs(getAdapterConfig())`.
- That second override is exactly what DEF-005's `"Adapter certificate renewal url set is empty"`
  was complaining about: the default `getCertificateRenewalUrls()` returns `null`.

## 3. What our framework does today

- `HttpClientBuilder.platformSsl(adapter)` sets `adapter.getPlatformSslContext()`: `SSLContext("TLS")`
  initialised with `getAdapterTrustManager()` (the instance `CustomTrustManager`) and
  `getKeyManagers()`. Transport: `java.net.http.HttpClient`.
- `allowInsecure(true)` sets `insecureSslContext()` (trust-all `X509ExtendedTrustManager`, no hostname check).
- `openPlatformConnection()` is the BC-mirror trust-all Suite API transport (stitcher only).
- `VcfCfAdapter` overrides **none** of `getConnectionURL`, `getConnectionURLs`,
  `onCheckCertificate`, `getCertificateRenewalUrls`. Neither does any pak (grep of
  `content/sdk-adapters/*/src`).

So for a target with a private-CA or self-signed cert:

1. Test Connection: `checkCertificate` returns `NOT_SUPPORTED`, the gate falls through to `test()`,
   our `CustomTrustManager` rejects the unknown chain, and the user sees a raw BC alert string.
   **No dialog, ever.**
2. There is no way to get a cert into `getTrustedCertificates()` for these instances through the
   UI, so collection would fail the same way on a saved instance.
3. The prior lesson's "java.net.http drops the TOFU intercept" is **not the blocker here**. The
   dialog is a *pre-test* probe the platform runs itself over its own `HttpsConnection`. Once the
   cert is accepted, `validate()` passes on PKIX regardless of transport, so `HttpClient` +
   `getPlatformSslContext()` is fine. What was missing is the URL declaration, not the transport.
   (The lesson's premise that "the admin approves the cert via the platform UI before collection
   starts" was right in principle but was never actually wired up for framework adapters.)

## 4. Recommendation

### 4a. Framework change (tooling, `VcfCfAdapter`), small

1. New protected hook, default empty:
   ```java
   /** Target endpoints whose TLS certificate the platform should review on Test Connection.
    *  Called on an UNSAVED config: read identifiers from rc, never from instance state.
    *  Return empty when the instance opted out of verification (allowInsecure). */
   protected java.util.List<String> certificateCheckUrls(ResourceConfig rc) { return List.of(); }
   ```
2. `@Override public final List<String> getConnectionURLs(AdapterConfig cfg)`: return
   `certificateCheckUrls(cfg.getAdapterInstResource())`, or `null` when empty (keeps
   `NOT_SUPPORTED` for adapters that don't opt in, which is today's behaviour, zero regression).
3. `@Override public Set<String> getCertificateRenewalUrls()`: hosts of
   `getConnectionURLs(getAdapterConfig())`, mirroring NSX-T. This lets the platform's
   non-disruptive renewal handle a rotated target cert on a saved instance instead of hard failing.
4. `onTest`: walk the cause chain, and if a `CustomTrustManager.CustomCertificateException` is
   present, set a readable message ("Target certificate is not trusted. Re-run Validate
   Connection and accept the certificate, or set Allow Insecure.") instead of the raw
   `TlsFatalAlert` text. Cheap and useful for adapters that haven't adopted the hook.
5. Leave the transport alone: keep `platformSsl` / `getPlatformSslContext()` on
   `java.net.http.HttpClient`. The platform's probe uses its own `CustomSSLSocketFactory`, so
   FIPS/BC compliance is inherited from the platform (prod runs
   `-Dorg.bouncycastle.fips.approved_only=true` with `bctls-fips-2.1.23`). No new crypto code,
   no custom keystore, nothing to FIPS-certify on our side.
6. Tests: a unit test that `getConnectionURLs` returns null by default and the subclass URLs
   when overridden; a test for the cause-chain message. Buildkit version bump.

Effort: roughly half a day of tooling work plus framework-reviewer, then a per-pak line or two.

### 4b. Pak adoption (one small override each)

| Pak | Target TLS today | URL(s) to declare |
|---|---|---|
| compliance | `getPlatformSslContext()` (REST, VAMI, SOAP all on `https://<vcenter_host>`) | `https://<vcenter_host>:443` unless `allowInsecure` |
| vcommunity, vcommunity-vsphere, vcommunity-os | `getPlatformSslContext()` or `insecureSslContext()` fallback | the configured target base URL |
| synology | `platformSsl` / `allowInsecure(true)` | DSM `https://host:port` |
| unifi | `platformSsl` / `allowInsecure(true)` | controller `https://host:port` |

Every pak must read identifiers from the passed `ResourceConfig` (unsaved on Test Connection),
the same trap compliance's tester already handles via `testResourceConfig(param)`.

### 4c. Things to verify live after the change (devel first)

- Dialog appears on Validate Connection for a private-CA vCenter; after accept, test passes;
  saved instance collects. Check `GET /api/adapters/{id}` (or the Certificates page) shows the
  accepted cert on that instance.
- Which certs the UI stores from the chain (leaf only vs leaf + issuer). Broadcom adapters on
  the same FIPS appliance succeed with the same `CustomTrustManager`, so our result should match
  theirs whichever it is. Not verified here.
- Hostname checking on the `HttpClient` path under BC JSSE with an `X509ExtendedTrustManager`
  is the trust manager's job; `CustomTrustManager` may not enforce it (the platform's
  `CustomHostnameVerifier` does that on the `HttpsURLConnection` path). Low risk, note only.

### 4d. Interim workarounds (no code)

- **Allow Insecure = true** on the compliance instance: works today (trust-all), loses
  verification. Fine for the lab.
- **Importing the lab CA via Administration > Certificates / `POST /api/certificate`:** not
  shown to help. Prod already lists `sentania Lab Issuing 2` there and a fresh instance still
  failed, consistent with trust being per-instance. Don't rely on it.
- Adding the lab root to the platform base adapter truststore would be a manual appliance
  change (RULE/CLAUDE rule 11: no), and would be lost on upgrade. Not recommended.

## 5. Side finding: devel "certificate is expired" banner and devel Suite API TLS failures

- Devel appliance certs are all valid until April 16, 2031 (web, slice, cluster CA, cluster,
  postgres), and the 443 SAN includes `localhost`, `127.0.0.1`, the IP, and the FQDN. Nothing
  on the appliance is expired.
- The only expired cert on devel is a stale **accepted adapter certificate** in
  `GET /api/certificate`: the old `CN=vcf-lab-vcenter-mgmt.int.sentania.net` (issued by
  sentania Lab Issuing 2), expired Monday July 6, 2026, 1:50 AM CDT. Its replacement (valid to
  May 10, 2028) is also stored. That's the likely banner source. Cleanup is an admin choice
  (deleting it is destructive, so not done).
- The other agent's devel Suite API TLS failure is **workstation-side**: `~/.bashrc` exports
  `REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt`. `requests` lets that env var override
  `Session.verify = False`, so `VCFOPS_DEVEL_VERIFY_SSL=false` is silently ignored and devel's
  private cluster CA fails ("self-signed certificate in certificate chain"). Prod works only
  because its cert chains to the lab CA that the system bundle trusts. Proven: same call succeeds
  with `REQUESTS_CA_BUNDLE` unset. Framework fix (tooling, `vcfcf_common/client.py`): pass
  `verify=` per request or set `session.trust_env`-aware handling so the profile setting wins.
  Tracked here only; not yet filed as an issue.
