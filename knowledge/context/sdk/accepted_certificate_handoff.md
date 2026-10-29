# Accepted certificates: what Ops stores and what the adapter receives

Investigated 2026-10-28 by `api-explorer`, read-only, on devel (VCF Operations
9.0.2.0 build 25431135), devel_9_1 (9.1.1.0 build 25795063) and devel_8_18
(Aria Operations 8.18.7 build 25423534). Trigger: the vsanhostmetrics fork
(`tuneup/upstream-2026-10`) pins vCenter by the SHA-256 of each PEM in
`certificate_config.certificates`, and review W2
(`reviews/python-packs/vsanhostmetrics-tuneup-2026-10-28.md`) asked whether
Ops stores the leaf or a CA. Nothing was changed on any instance: Suite API
GETs, read-only SSH, `SELECT`s in a `default_transaction_read_only` psql
session, jar copies to the workstation for `javap -c -p`.

**Answer in one line.** On all three versions, "Review and accept" stores
exactly one certificate, the presented **leaf** (`chain[0]`), as a single DER
entry keyed by its SHA-256. But the list the adapter receives is that
instance's accepted leaves **plus every globally trusted CA certificate**
(trust type `CERTIFICATE_AUTHORITY`) on the cluster. So the list can contain
CAs, never a concatenated chain, and on a cluster that already trusts the
target's CA the leaf is never stored at all.

## 1. Storage

- Table `public.kv_certificate` in `vcopsdb` (the `repl` postgres, port 5433),
  key `Certificate.<sha256 lowercase hex>`, value a Java-serialized
  `com.vmware.statsplatform.persistence.certificate.CertificateData`:
  `certificateString` (upper-case hex of **one** DER certificate; checked:
  string length / 2 equals the DER length in every row on all three
  versions), `certificateTrustObjects` (list of `{id, type}`),
  `enforceDateValidation`, `enforceHostnameVerification`, `known`,
  `thumbprint`.
- `GET /api/certificate` (public spec) lists the same rows: `thumbprint` is
  the SHA-256 of the DER, plus `issuedTo`, `issuedBy`, `expires`. It shows no
  trust objects; the DB row is the only place the instance links are visible.
  `GET /api/adapters/{id}` carries no certificate data.
- Trust object types seen: `ADAPTER_INSTANCE` (id = adapter instance UUID)
  and `CERTIFICATE_AUTHORITY` (no instance id).

## 2. What reaches the Python adapter

Chain of calls (`javap`, identical call sites on 9.0.2, 9.1.1 and 8.18.7):

1. `ResourceConfigConstructor` (`vcops-collector-controller`) builds each
   instance's `ResourceConfig`: `fillTrustedCertificateConfigs(rc,
   AdapterData.getTrustedCertificateIds())` (the instance's own links), then
   **`fillCACertificateConfigs(rc)`**, which appends
   `Controller.getAllCACertificateConfigs()`, which is
   `CertificateDataService.getAllCertificateAuthorities()`: every row with a
   `CERTIFICATE_AUTHORITY` trust object.
2. On the collector, `DockerizedAdapterApiConverter.convertTrustedCertificatesSdkToApi`
   (`collector/lib/dockerized-adapter-plugin/v1_0/vrops-dockerized-adapter-api-1.0-SNAPSHOT.jar`)
   maps `rc.getTrustedCertificates()` one to one into
   `certificate_config.certificates[]`: `certPemString =
   CommonUtils.convertCertificateStringToPem(certificateString)`, one PEM per
   entry.
3. Flags are copied with no negation: `isInvalidHostnameAccepted :=
   getEnforceHostnameVerification()`, `isExpiredCertificateAccepted :=
   getEnforceDateValidityChecking()`. At accept time the bridge sets
   `enforceHostnameVerification` from `CheckCertificateResult.isPassesHostnameVerification()`
   and `enforceDateValidityChecking` from `!dateIsNotValid()`. So the Python
   `is_invalid_hostname_accepted()` / `is_expired_certificate_accepted()`
   carry the platform's "enforce" bits, not "user accepted a bad name/date".
   Stored values vary (devel_9_1's vCenter-mgmt leaf: hostname `false`;
   devel's vCenter leaves: `true`). Do not build logic on them; an exact pin
   makes them moot.

## 3. What "accept" stores, per path

| Path | Code | Stored |
|---|---|---|
| UI dialog (Integrations account, ExtJS `CertificateManager.js` / `ManageResourcePanel`) | Bridge `ResourceManager.testResource` returns the **whole** chain as `untrustedCertificates`; the UI then does `untrustedCertificates[0]` ("Get the leaf certificate info from the certificate chain"), shows only it, and on Accept pushes only it into `newTrustedCertificates` | leaf only |
| Bridge "save silently" (NOT_SUPPORTED result) | `addNewTrustedCertificate(chain[0])` | leaf only |
| Suite API `POST`/`PATCH /api/adapters`, `/api/adapters/testConnection` | `DefaultResourceService.checkForUntrustedCertificates`: `getCertificateChain()[0]` per URL | leaf only |

All three versions: same UI source lines (148-149), same `iconst_0; aaload`
in `checkForUntrustedCertificates`. The dialog offers no choice of chain
element, so **an operator cannot accept a CA through "Review and accept"**,
even when the endpoint presents a chain. A CA reaches an adapter only as a
global `CERTIFICATE_AUTHORITY` entry; the public route that looks like it is
`POST /api/certificate` (multipart import). Not exercised (it changes state),
and how devel's two CA rows were created was not established.

## 4. Observed, per version

The lab vCenters present leaf + issuing CA (enterprise CA "sentania Lab
Issuing 2", not VMCA). `openssl s_client -showcerts`, SHA-256 of DER:

| Endpoint | Leaf sha256 | Issuer cert presented |
|---|---|---|
| vcf-lab-vcenter-mgmt | `6dad10b5…4f245c` | Issuing 2 `06c86dd3…524cc5` |
| vcf-lab-vcenter-wld01 | `b7f3187a…a8c017` | same |
| vcf-lab-vcenter-wld02 | `b60d654e…7e7f7f` | same |

| Version | Rows in `kv_certificate` | VsanHostMetrics instance gets | vSphere (`VMWARE`) instances get |
|---|---|---|---|
| 9.1.1 (devel_9_1) | 5 leaves, 0 CA | `a41ef1c9…` linked to `6dad10b5…` = the presented mgmt leaf. List = [mgmt leaf] | each linked to its vCenter's current leaf |
| 9.0.2 (devel) | 6 leaves + Issuing 2 + Root 2 (`c8423095…`), both `CERTIFICATE_AUTHORITY` | `fbe09ba8…` linked to nothing. List = [Issuing 2, Root 2] (CAs only, no leaf) | leaves, and two instances hold **two** leaves each (old and renewed wld01/wld02), plus the 2 CAs |
| 8.18.7 (devel_8_18) | 5 leaves, 0 CA | `3c57dcf3…` linked to nothing. List = [] | each linked to its vCenter's leaf |

Every `ADAPTER_INSTANCE` link on all three versions points at a leaf. Every
leaf's stored sha256 equals the presented leaf's.

Why devel and 8.18 have no leaf for VsanHostMetrics: on devel the platform's
own check (`CustomTrustManager`, with the global CAs loaded) validates the
chain, so the result is SUCCESS and no dialog appears; nothing is stored. On
8.18 the cause was not established (no global CA there). All three instances
run pack 1.4.6 with `verify_certs=false`.

## 5. Consequences for a pack that pins

- The list is not "the leaf". Expect, per instance: zero or more accepted
  leaves (re-accepting after a renewal adds a leaf and keeps the old one),
  plus every cluster-wide CA. Never a bundled chain in one PEM.
- An exact leaf pin works for every account where the operator clicked
  Accept, on all three versions.
- An exact pin **fails** where Ops trusts the target through a global CA: no
  dialog, no leaf, the list holds only CAs, and the pack's container CA
  bundle does not have a private CA. That is the W2 "matches none" outcome on
  devel today, for a different reason than the review supposed.
- Handle both: before pinning, verify normally against a context loaded with
  every received PEM (`ssl.create_default_context(cadata=<all pems>)`, hostname
  check on). A CA set that reaches a self-signed root then validates the
  chain; an intermediate-only or leaf entry is not accepted as an anchor
  unless `VERIFY_X509_PARTIAL_CHAIN` is set. Then fall back to the exact leaf
  pin. Distinguish entries if needed by
  `BasicConstraints ca=True`.
- `mp-test` stores the leaf only and never a CA, so the local loop cannot
  reproduce the CA-only case; seed `connections.json` with a CA PEM by hand to
  test it.

## Provenance (RULE-015)

Local-only, not redistributed: jars copied read-only from the devel_9_1 node
(`common/lib/vcops-collector-controller-1.0-SNAPSHOT.jar`,
`persistence-1.0-SNAPSHOT.jar`, `alive_platform.jar`, `vrops-adapters-sdk.jar`,
`controller/plugins/vcops-bridge-server-1.0-SNAPSHOT.jar`,
`common/lib/vcops-bridge-client-1.0-SNAPSHOT.jar`,
`tomcat-enterprise/webapps/suite-api/WEB-INF/classes/.../DefaultResourceService.class`),
the matching controller/SDK/persistence jars and `DefaultResourceService` from
the devel and devel_8_18 nodes, and the dockerized plugin jar from all three
Cloud Proxies. UI source read in place at
`tomcat-web-app/webapps/ui/js/components/integrations/accounts/CertificateManager.js`.
Call sites and constants only; no decompiled source is reproduced.
