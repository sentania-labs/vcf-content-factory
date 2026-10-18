# CaSA routing: raw SDK client vs. injected (UnlicensedAdapter) client

**Question (the only one this file answers):** Does the **raw**
`vrops-adapters-sdk` `SuiteAPIClient` route through **CaSA**
(node-certificate mutual-TLS — the creds-free door on a Cloud Proxy),
or does CaSA routing live **only** in the `UnlicensedAdapter` /
aria-ops-core injection wrapper?

**Verdict:** **Neither.** No node-cert / CaSA mutual-TLS routing exists
in *any* pak/core jar — not in the raw SDK, not in the injected
`UnlicensedAdapter` client. Both are the identical
`SuiteAPIClient` targeting `https://localhost/suite-api/` with a plain
**username/password token**. The node-cert / CaSA mTLS the CORRECTION
doc hypothesized is done **entirely by the OS-level httpd-north +
haproxy PrxyRC tunnel** (platform runtime, outside the JVM), never by
adapter code.

**Confidence:** High — bytecode-proven (Tier 1, local jars). No live
appliance pull was needed; the routing question was fully answered by
the jars on disk plus the already-proven tunnel facts in
`casa-inventory-access.md`.

**Consequence for our decision ("how much do WE build"):** Staying on
bare `AdapterBase` (not extending `UnlicensedAdapter`, not pulling
aria-ops-core) costs us **nothing** on the CaSA axis, because
`UnlicensedAdapter` buys **no** node-cert plumbing anyway. Our door fix
is **small** on the transport axis: we do **not** build a node-cert
mTLS handshake — the tunnel is ambient and free. The only real delta
is **principal/identity** (see Residual).

---

## Evidence (jars in `src/vcfcf_managementpacks/adapter_runtime/`)

Tools: `javap -p -c` / `javap -v` on `vrops-adapters-sdk-2.2.jar`,
`aria-ops-core-8.0.0.jar`. Extracted to session scratchpad only;
nothing but this file written to the repo; no lab objects created.

### 1. The raw SDK jar has no Suite API client at all

`vrops-adapters-sdk-2.2.jar` contains
`com.integrien.alive.common.adapter3.AdapterBase` and a bare
`HttpsConnection`, but **zero** `SuiteAPIClient` / `SuiteAPI*` /
`casa` / `Unlicensed*` classes (grep of the jar index returns nothing).
So the "raw client" in the question does not exist as a distinct thing
— there is nothing in the SDK to route anywhere. `AdapterBase` exposes
no `getSuiteApiClient()` accessor (consistent with
`casa-inventory-access.md`).

### 2. `SuiteAPIClient` and `UnlicensedAdapter` are aria-ops-core only

Both live in `aria-ops-core-8.0.0.jar` under
`com/vmware/tvs/vrealize/adapter/core/…`. The "raw vs injected"
distinction collapses: there is exactly **one** `SuiteAPIClient`
class, used both ways.

### 3. `SuiteAPIClient` carries no CaSA / node-cert / port logic

`SuiteAPIClient(AdapterLoggerFactory, SuiteAPICredential)` →
`getClientConfigBuilder(cred)` builds a
`com.vmware.ops.api.client.Client$ClientConfig` with, verbatim:

- `serverUrl(cred.url)` — nothing else sets the endpoint; no
  `localhost:8443`, no `:443`, no CaSA `/casa/*` path, no node-role
  branch.
- FIPS branch → `useClusterTruststore` (set by reflection). Non-FIPS →
  `verify("false")`, `ignoreHostName(true)`. `SuiteAPIClient` itself holds
  no client keystore or cert, but the FIPS branch can present one (see
  "client keystore" below); that is not CaSA or node identity, it is
  whatever `secure-communications.properties` configures for the cluster
  category.

  **FIPS branch in full** (re-read 2026-10-18 for issue #215, `javap -p -c
  -constants`; corrected the same day after framework review, see
  `knowledge/context/reviews/framework/2026-10-18-fips-cluster-truststore.md`):

  - **Switch** (`aria-ops-core-8.0.0.jar`): `Constants.FIPS_MODE_ENABLED =
    Boolean.valueOf(System.getenv("IS_FIPS"))`. The BouncyCastle
    `approved_only` JVM property is not read anywhere on this path.
  - **Builder** (`SuiteAPIClient.getClientConfigBuilder`, FIPS): `useJson`,
    `serverUrl`, `allowClientToCommunicateWithOlderServers(true)`,
    `verify("true")`, `ignoreHostName(true)`, then
    `Client$ClientConfig$Builder.useClusterTruststore(boolean)` invoked by
    reflection with `true`. No truststore path, type or password is passed.
    The hostname is ignored in both modes.
  - **Not the inputs:** `Constants.TRUSTSTORE_PATH`
    (`$VCOPS_DATA_VCOPS/user/conf/ssl/tcserver.truststore`, default root
    `/data/vcops`), `TRUSTSTORE_PASSWORD_PATH` and `getTrustStorePassword()`
    are defined in aria-ops-core and read by no class in that jar. An
    earlier revision of this section and of the framework mirrored them;
    that was wrong.
  - **Where `useClusterTruststore` is implemented**
    (`vcops-suiteapi-client-2.2-all.jar`, provenance below):
    `HttpClientFactory.createClient`, when `verify` is true and no
    truststore path, certificate path, certificates or socket factory is
    configured and `isUseClusterTruststore()` is set, calls
    `SSLOptions.getSSLOptions(convertConnectionCategory(getOpsConnectionCategory()))`
    and builds `vROpsSSL.newSSLSocketFactoryBuilder(options).build()`, a
    `vROpsSSLSocketFactory`. The builder's default category is
    `VROPS_CLUSTER` (`configurationKey` `inter_cluster`, parent `DEFAULT`,
    key `default`). `certificateSecureAutoRefreshConfig` is rejected
    together with `useClusterTruststore`, so no NDC refresh applies.
    The hostname verifier is `getHostnameVerifier(isIgnoreHostName())`.
  - **`SSLOptions.<clinit>`** (once per JVM, one instance per category):
    `IS_FIPS = Boolean.parseBoolean(System.getenv("IS_FIPS"))`;
    root `STORAGE` (`System.getenv`, else `System.getProperty`); files
    `<STORAGE>/vcops/user/conf/ssl/secure-communications.properties` and
    `<STORAGE>/vcops/user/conf/ssl/storePass.properties`. If `STORAGE` is
    unset or the options file is absent it logs "Failed to find
    secure-communications.properties file." and keeps the defaults
    (`protocol` `TLS`, `algorithm` `PKIX`, `store_type` `JKS`, no
    truststore), so every handshake then fails for want of trust anchors.
  - **Key lookup** (`propertyLookupPrefixes` + `readProperty`): for
    `VROPS_CLUSTER` the prefixes are `inter_cluster` then `default`, and a
    key is read as `<prefix>.<key>`, first hit wins. Traced from the
    bytecode: the stack is popped root first, the root contributes
    `default`, and because the root has no parent the accumulated prefix
    resets to empty before `inter_cluster` is built, so
    `default.inter_cluster.<key>` is **never** consulted (the review
    report's reading of a nested prefix does not match the bytecode).
    `protocol`, `store_type`, `algorithm`, `supported_cipher_suites` and
    `supported_protocols` are required (absent → `RuntimeException`
    "... not found."); `keystore`, `truststore` and the passwords are
    optional.
  - **Lists:** `supported_cipher_suites` / `supported_protocols` equal to
    `%all%` (case-insensitive) take the JRE defaults of
    `SSLContext.getInstance(protocol)`; otherwise `trim()` then split on
    `\s*,\s*`. When `IS_FIPS`, `filterRestrictedCiphers` drops every suite
    starting `TLS_RSA`. Protocols are not filtered.
  - **Paths:** `truststore` and `keystore` go through `replacePathEnvVars`:
    `%NAME%` then `$NAME`, value from the environment, else a system
    property; unresolved names stay as written.
  - **Passwords** (`readPasswordProperty`): `<key>.encrypted` under any
    prefix, decrypted with `com.vmware.vcops.security.Crypt.dec`
    (= `getDefaultCrypt().decrypt`, which is what the SDK-jar
    `com.integrien.alive.common.security.Crypt.getDefaultCrypt().decrypt`
    delegates to), before the plain `<key>` under any prefix. A resulting
    value of `%truststore_password%` / `%keystore_password%`
    (case-insensitive) loads `storePass.properties` and reads
    `ssltruststorePassword` / `sslkeystorePassword` through
    `CryptUtils.readPasswordProperty`: **`.encrypted` first** (decrypted),
    then the plain key, null if neither.
  - **Context** (`vROpsSSL.createvROpsSSLContext`):
    `SSLContext.getInstance(protocol)`; truststore
    `KeyStore.getInstance(store_type)` loaded from `truststore` with its
    password (or empty when `truststore` is null);
    `TrustManagerFactory.getInstance(algorithm)`. **Client keystore:** when
    `keystore` is set, it is loaded as `KeyStore.getDefaultType()` with
    `keystore_password` and `KeyManagerFactory.getInstance(algorithm)`
    supplies key managers, so the client presents that certificate.
    Failures surface as `RuntimeException("Failed to initialize SSL
    context")`.
  - **Sockets** (`vROpsSSLSocketFactory.prepareSocket`): every socket's
    enabled protocols and cipher suites are set to the socket's supported
    set intersected with the configured lists (an empty intersection is
    logged and applied). The factory reloads its context when the
    truststore file's `lastModified` passes its load time; the
    `SSLOptions` themselves are never re-read.
  - **Store type:** comes from `store_type` in the file. The value on a
    FIPS node is a live-only fact. (For reference only:
    `alive_common CaSACertificateStoreConfig` loads `tcserver.truststore`
    as `BCFKS` when `IS_FIPS`, `JKS` otherwise, from
    `${STORAGE}/vcops/user/conf/ssl/`, and feeds gemfire's
    `cluster-ssl-truststore`; MPB 9.0.1 `VropsGlobalTrustStore` always uses
    `JKS`. Neither is on the Suite API path.)
  - **Framework mirror:** `VcfCfAdapter.openPlatformConnection` FIPS branch
    (`applySuiteApiTransport` → `applyClusterTruststoreTransport`) reproduces
    every step above for `VROPS_CLUSTER`, fail-closed: where the vendor
    would proceed with an empty trust store (no `STORAGE`, no options file,
    no `truststore` key) or hit a null password, the framework throws an
    `IOException` naming the file and key instead.

  **Provenance of `vcops-suiteapi-client-2.2-all.jar`** (RULE-015
  local-only artifact; not reproducible from this repo; findings summarized
  here in full so the citation is not needed). Maven coordinates
  `com.vmware.vcops:vcops-suiteapi-client:2.2` (its `pom.properties`),
  classes dated 2025-12-30, Build-Jdk-Spec 17, sha256
  `a387dfbb2a5b342bc67d36cea12e8fe6c489ff7d0b0e51c0187e354edc398570`.
  Extracted from the `lib/` of the MPB adapter pak
  `MPBAdapter-902025137890.pak` (Major-Version 9, Minor-Version 0,
  Implementation-Version 25137890, pulled from the devel 9.0.2 instance)
  in the separate clean-room workspace (`vcf-mp-cleanroom`, not part of
  this repo); byte-identical copies ship in the `DiagnosticsAdapter3` and
  `VMwareInfrastructureHealthAdapter` paks extracted there. The jar is not
  copied into this repo and is not on the factory classpath. To re-verify
  on another machine, take the jar from any of those paks on a 9.0.2
  appliance and check the sha256.
- Auth: `UserAndAuthManagementClient.acquireToken(UsernamePassword)`
  from `cred.username`/`cred.password` → `tokenAuth(token)`.

Log strings confirm the model: *"Acquiring Suite API token for user"*,
*"Token-authentication client created"*. It is a **user-token client**,
full stop.

### 4. `SuiteAPICredential` is a plain user credential

Fields: `username`, `password`, `url`. Default `url` constant =
`https://localhost/suite-api/`. Two credential sources:

- `getSuiteApiAdapterCredential(AdapterConfig)` → reads
  `AdapterCredentialConfig.getUserName()/getPassword()` — the
  **operator-supplied** adapter credential.
- `getSuiteAPIMaintenanceUserCredential()` → `loadProperties(Path)` on
  constant `MAINTENANCE_CREDENTIALS_PATH` (`maintenanceuser.properties`),
  keys `username`/`password`/`encrypted`, decrypted via
  `com.integrien.alive.common.security.Crypt.decrypt`. This is the
  **maintenance user** — the *same door our `SuiteApiStitchClient`
  already uses and which 403s on a Cloud Proxy*
  (`synology-stitcher-vs-tvs-corpus.md`). **`automationAdmin` is never
  referenced in aria-ops-core** — it is platform-internal
  (`ConfigUserUtils` in `alive_platform.jar`).

### 5. `UnlicensedAdapter` injection adds nothing on the CaSA axis

`onConfigure`: if `useBuiltinSuiteApiClient()` (default `return true`)
→ `new SuiteAPIClient(loggerFactory,
SuiteAPICredential.getSuiteApiAdapterCredential(getAdapterConfig()))`.
Also a `setSuiteAPIClient(SuiteAPIClient)` seam for external injection.
Either way it is the **same** `SuiteAPIClient` from §3 with a
**username/password** credential. No node cert, no CaSA endpoint, no
keystore. The "injected client" is just this client constructed with
the operator's adapter creds instead of the maintenance-user creds.

---

## Where the CaSA / node-cert routing actually is (already proven)

Per `casa-inventory-access.md` (live prod CP + bytecode): the
`https://localhost/suite-api` request is transparently proxied by
`httpd-north` → haproxy `PrxyRC_FE:8443` → primary `:443/suite-api`,
with the CP's **slice/node certificate** (`haproxy.slice.pem`)
anchoring the CP↔cluster mutual-TLS *transport*. haproxy presents **no
client cert to suite-api**, so suite-api still demands a **user token**.
**The node cert secures the pipe; the token authorizes the API.** All
of this is OS/platform runtime — no adapter (raw or UnlicensedAdapter)
touches a keystore. This is why the CORRECTION doc's "injected
SuiteAPIClient routes through CaSA via node cert" is bytecode-false: no
JVM-level CaSA routing exists to find.

---

## Deliverable 2 — build spec (what our framework must actually do)

Because there is **no** node-cert handshake to replicate, the
`SuiteApiBridge` seam does **not** need to build CaSA mTLS. It needs
exactly two things, both already scoped in `casa-inventory-access.md`:

1. **Base URL:** `https://localhost/suite-api` (relies on the ambient
   tunnel; identical code on primary and CP — routing is automatic by
   node role at the OS layer). We already do this.
2. **Principal:** acquire the token as **`automationAdmin`**, not the
   maintenance user. Obtain via
   `com.vmware.vcops.platform.utils.ConfigUserUtils.getAutomationUserCredentials()`
   (public static, `alive_platform.jar`, on the collector classpath) →
   `POST /api/auth/token/acquire` → bearer → `resources/query`. This is
   the single change that turns our current CP 403 into a working
   creds-free read.

No node keystore path, no cert alias, no mTLS handshake in our code —
those belong to haproxy, not the adapter.

**Unsupported-endpoint warning:** internal suite-api endpoints and
`ConfigUserUtils`/`vcops-suiteapi-internal-client` are undocumented
Broadcom-internal classes and require the `X-Ops-API-use-unsupported`
(a.k.a. `X-vRealizeOps-API-use`) header. They are on the collector
classpath today but are not a public SDK contract and can change
between releases.

---

## Deliverable 3 — Residual (genuine live/cleanroom-only unknowns)

1. **Is `automationAdmin` CP-safe (does its token carry resource-read
   RBAC on a Cloud Proxy)?** Strong inference yes — the first-party
   `VMWARE_INFRA_MANAGEMENT` adapter runs `credentialInstanceId=null`
   on the prod CP and actively reads 29 VMWARE resources, and it uses
   `automationAdmin` (`casa-inventory-access.md` §3/§4). But whether a
   token *minted on the CP* for `automationAdmin` returns read roles is
   a **live-only** confirmation. Our own maintenance-user path is
   proven to 403 there.
2. **Version coverage 9.0.2 vs 9.1.** These jars are aria-ops-core
   **8.0.0** and SDK **2.2**. The `ConfigUserUtils.getAutomationUserCredentials`
   API surface and `automationuser.properties` presence should be
   re-checked on 9.0.2 specifically — the parallel cleanroom request is
   carrying that version cross-check.
3. **Long-term stability** of `ConfigUserUtils` /
   `vcops-suiteapi-internal-client` as the token source — Broadcom-
   internal, no SDK guarantee.

No Tier-2 live appliance pull was required to answer the routing
question; items 1–2 above are the only parts a live pull / cleanroom
answer could still tighten, and they concern **identity**, not the
(now-closed) **transport/routing** question.
