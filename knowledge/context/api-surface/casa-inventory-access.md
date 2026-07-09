# CaSA / Cloud-Proxy inventory-read mechanism

How a VCF Ops adapter running on a **Cloud Proxy** (CP) reads
cluster-wide VMWARE inventory (Datastores / Hosts / VMs) with **no
operator credentials**. Reverse-engineered from the live prod CP
(`vcf-lab-operations-collector.int.sentania.net`) and Broadcom
first-party bytecode. This corrects and supersedes the "authenticates
via the node certificate, bypassing the user-credential stack"
framing in `knowledge/context/investigations/recon_log.md`
(2026-06-30 section) — the node cert secures the **transport tunnel**,
but the suite-api call itself is authorized by a platform-managed
**service account token** (`automationAdmin`), not the node cert.

Investigated 2026-06-30. Clean-room: only Broadcom-owned jars were
decompiled (`vim.jar` = `VMWARE_INFRA_MANAGEMENT`, aria-ops-core
`alive_*.jar`, `vcops-suiteapi-*client`, `casa-*client`,
`vrops-adapters-sdk`). No third-party paks touched.

---

## TL;DR — the working path

An unprivileged CP-resident adapter reads cluster inventory by:

1. Building a Suite API client with base URL **`https://localhost/suite-api`**
   (equivalently `https://172.17.0.1/suite-api` from inside a container —
   172.17.0.1 is the docker bridge to the same local `httpd-north`).
2. Reading the local **`automationAdmin`** service credential via
   `com.vmware.vcops.platform.utils.ConfigUserUtils.getAutomationUserCredentials()`
   (public static; `alive_platform.jar`, on the collector classpath).
3. `POST /suite-api/api/auth/token/acquire` with that credential →
   bearer token.
4. `POST /suite-api/api/resources/query` (and friends) with the token →
   cluster inventory.

Local `httpd-north` transparently proxies `/suite-api/` →
`https://cptocluster:8443/suite-api/` → the **haproxy PrxyRC**
frontend → the primary node's `:443/suite-api`, with the CP's
**node/slice certificate** providing the CP↔cluster mutual-TLS
transport trust. The adapter does **no** cert handling itself.

**There is no dedicated "CaSA inventory endpoint."** Inventory is the
ordinary Suite API, reached over the Cloud-Proxy Reverse-Connect
(PrxyRC) tunnel. CaSA proper (`/casa/*`) is the cluster **control**
plane (deployment, proxyrc registration, authorize) — not the
inventory path.

---

## The moving parts (all proven on the live CP)

### 1. Local reverse-connect tunnel (`httpd-north` → haproxy PrxyRC)

`/etc/httpd-north/httpd.conf` on the CP:

```
ProxyPass        /suite-api/ https://cptocluster:8443/suite-api/ disablereuse=On
ProxyPassReverse /suite-api/ https://cptocluster:8443/suite-api/
ProxyPass        /casa/      https://cptocluster:8443/casa/
```

`cptocluster` → `127.0.0.1` (`/etc/hosts`). Port **8443** is the
haproxy `PrxyRC_FE` frontend (`/etc/haproxy/haproxy.cfg`):

```
frontend PrxyRC_FE
  bind localhost:8443 ssl crt /storage/vcops/user/conf/ssl/haproxy.slice.pem ...
backend PrxyRC_BE
  http-request set-header Host vcf-lab-operations.int.sentania.net:443
  server VROPS_0 vcf-lab-operations.int.sentania.net:443 ... ssl verify required \
         ca-file /storage/vcops/user/conf/ssl/haproxy.ca.pem
```

- `haproxy.slice.pem` = the CP **node certificate**
  (`CN=VCFOps-slice-1`, issued by `VCFOps-cluster-ca_<uuid>`). It is
  the **server** cert haproxy presents to local callers and the
  identity anchoring the reverse-connect registration with the
  cluster.
- Additional PrxyRC frontends: 8444 (unsecure), 8445 (vRLI), 8447
  (dynamic), 8448 (unified shell), 8446 (crushftp/broadcom eapi).
  8447/8448 accept a `/<primary-fqdn>/...` path prefix and strip it.

The CaSA control channel (`/casa/authorize`, `/casa/onprem/v1/proxyrc/cluster/ping`,
`/casa/saasproxy/...`) rides the same 8443 tunnel and is where the
node-cert / slice identity is actually consumed for cluster trust.

### 2. Node cert alone is NOT suite-api auth (proven)

| Test (from CP) | Result | Meaning |
|---|---|---|
| `GET https://localhost:8443/suite-api/...` (haproxy direct) | **Not Authorized** HTML | tunnel reaches cluster, no token |
| `GET https://vcf-lab-operations:443/suite-api/...` with `--cert slice_1_cert.pem --key slice_1_key.pem` (node cert mTLS direct to primary) | **Not Authorized** HTML | node cert ≠ suite-api principal |
| `GET https://localhost/suite-api/api/versions/current` (via httpd tunnel, no token) | **HTTP 401** | reached cluster suite-api; needs bearer token |
| `POST https://localhost/suite-api/api/auth/token/acquire` (bogus creds) | **HTTP 400** | acquire endpoint live over tunnel |

The haproxy `server` lines carry **no client `crt`** — haproxy does
not present a client cert to the primary's suite-api. So suite-api
sees an anonymous TLS peer and demands a token. **The node cert
secures the pipe; the token authorizes the API.**

### 3. The credential-free service account: `automationAdmin`

`/usr/lib/vmware-vcops/user/conf/automationuser.properties`:

```
username=automationAdmin
password=<encrypted>
encrypted=true
```

`com.vmware.vcops.platform.utils.ConfigUserUtils` (`alive_platform.jar`)
exposes public static accessors that read + decrypt these local
"config user" props (via `com.vmware.vcops.security.Crypt`):

- `getAutomationUserCredentials()` → `automationAdmin`
- `getMaintenanceUserCredentials()` → `maintenanceAdmin`
- `getCloudUserCredentials()`

Props constants: `AUTOMATION_CREDENTIALS_PROPS`,
`MAINTENANCE_CREDENTIALS_PROPS`, `CLOUD_CREDENTIALS_PROPS`. These are
node-local, platform-generated (random) passwords — **no operator
input**. This is why `VMWARE_INFRA_MANAGEMENT` runs with
`credentialInstanceId=null`.

> The prior factory 403 was from using the ambient
> `cloudproxy_<uuid>` maintenance account, which has no suite-api
> role grant. The correct principal is `automationAdmin` (or a token
> minted for it), not the reverse-connect maintenance account.

### 4. The Broadcom reference: `VMWARE_INFRA_MANAGEMENT` (`vim.jar`)

`com.vmware.adapter.management.core.configuration.VCFOpsClientConfiguration`
holds exactly three fields — `restApiUrl`, `username`, `password` —
with the baked-in constant **`https://localhost/suite-api`**. The
adapter uses `vcops-suiteapi-internal-client` and calls
`/api/auth/token/acquire`, `/api/auth/token/exchange`,
`/api/auth/token/release`, `/api/resources/query`, `/api/adapters`,
`/api/configurations/files`. Internal endpoints carry the
`X-vRealizeOps-API-use` (unsupported) header. It is a first-party
Broadcom adapter that composes platform-internal helpers directly; it
is **not** built on the public adapter SDK's `AdapterBase`.

### 5. CaSA REST client (control plane, for completeness)

`com.vmware.vcops.platform.utils.CasaClientFactory.getInstance()`
(public static) builds a `com.vmware.vcops.casarest.client.CaSAClient`
using `ConfigUserUtils` config-user creds with
`AuthType.TOKEN_AUTH` against `/casa/authorize`. The CaSA cert store
(`com.integrien.alive.common.security.CaSACertificateStoreConfig`) is
a BCFKS keystore/truststore (`vcopsKeystore` / `vcopsTruststore`).
This is the **admin/deployment** surface (`/casa/sysadmin/*`,
`/casa/deployment/*`, `/casa/proxyrc/*`), **not** how inventory is
read.

---

## What the factory must do

Goal: read `VMWARE::Datastore` (and Host/VM) inventory from a CP with
no operator creds. Two options:

### (a) "Injected client via UnlicensedAdapter" — NOT available as a supported path
There is **no `UnlicensedAdapter` class and no suite-api accessor** in
`vrops-adapters-sdk.jar`. `AdapterBase` exposes no
`getSuiteApiClient()` / internal-client provider. The infra adapters'
suite-api access comes from **platform-internal** classes
(`ConfigUserUtils`, `vcops-suiteapi-internal-client`), not from an
SDK-provided injected client. So option (a) as literally posed does
not exist to bytecode. **NEEDS SDK DOCS** to confirm whether a
supported managed-pak accessor exists in the 2.2 SDK that isn't
visible on `AdapterBase` (none found).

### (b) Bare-`AdapterBase` adapter reaches the tunnel directly — this is the concrete path
An MPB/SDK adapter running in the collector JVM can:

1. Construct a Suite API client (either
   `com.vmware.ops.api.client.Client` from
   `vcops-suiteapi-client`, or `vcops-suiteapi-internal-client`)
   with `serverUrl = https://localhost/suite-api`.
2. Obtain the `automationAdmin` credential via
   `ConfigUserUtils.getAutomationUserCredentials()` (public static,
   on the collector classpath), OR reproduce token acquisition with
   whatever service principal the platform exposes.
3. `token/acquire` → token → `resources/query`.

The adapter does **no** node-cert / keystore handling — `httpd-north`
+ haproxy PrxyRC own the mTLS transport. Routing is **automatic by
node role**: on a CP, `localhost/suite-api` is wired to the tunnel;
on the analytics node the same URL is the local API. The adapter code
is identical either way — it always targets `https://localhost/suite-api`.

**Tradeoff / risk to flag:**
- `ConfigUserUtils` / `CasaClientFactory` / `vcops-suiteapi-internal-client`
  are **internal, undocumented, unsupported** Broadcom classes. They
  are on the collector classpath today but are not part of the public
  adapter SDK contract and can change between releases.
- Internal suite-api endpoints require the `X-vRealizeOps-API-use`
  (a.k.a. `X-Ops-API-use-unsupported`) header — **unsupported-endpoint
  warning applies.**
- Reproducing the `automationAdmin` password decryption outside
  `ConfigUserUtils` is not viable (platform `Crypt` key); the
  supported-ish move is to call `ConfigUserUtils` directly if the
  adapter runs in-JVM with that jar available.

### Recommended framework direction
Point the factory's `SuiteApiStitchClient` at
**`https://localhost/suite-api`** (not the primary FQDN, not
`localhost:8443` directly) and acquire a token as **`automationAdmin`**
via `ConfigUserUtils` rather than the `cloudproxy_<uuid>` account.
That single change (right base URL + right principal, relying on the
ambient tunnel) is what turns the 403 into a working credential-free
inventory read on a Cloud Proxy. Validate on the analytics node too —
same URL should work there without the tunnel.

---

## Proven vs. needs-docs

**Proven (live CP + bytecode):** the httpd→8443→primary tunnel and
its routing; haproxy PrxyRC binds the slice/node cert; node cert alone
yields 401 on suite-api; `automationAdmin`/`maintenanceAdmin` config
users and `ConfigUserUtils` public API; `vim` adapter base URL
`https://localhost/suite-api` + token acquire/exchange/release +
`resources/query`; `CasaClientFactory` is config-user token auth;
no `UnlicensedAdapter`/suite-api accessor in the public SDK.

**Needs SDK docs (vrops-adapters-sdk 2.2):** whether a *supported*
managed-pak API exposes an internal/ambient Suite API client (none
found on `AdapterBase`); the officially blessed way for a Tier-1/Tier-2
pak to obtain a service token on a CP; long-term stability guarantees
for `ConfigUserUtils` / `vcops-suiteapi-internal-client`.

---

## Endpoint quick-reference

| Purpose | Call | Auth |
|---|---|---|
| Inventory (Datastore/Host/VM) | `POST https://localhost/suite-api/api/resources/query` | bearer token |
| Acquire token | `POST https://localhost/suite-api/api/auth/token/acquire` | `automationAdmin` creds |
| Exchange/release token | `.../api/auth/token/exchange`, `.../release` | token |
| Adapters list | `GET https://localhost/suite-api/api/adapters` | bearer token |
| CaSA control (not inventory) | `https://localhost/casa/*` → 8443 tunnel | config-user token / node cert |

Node cert / tunnel files (CP): `/storage/vcops/user/conf/ssl/haproxy.slice.pem`,
`slice_1_cert.pem` + `slice_1_key.pem`, `haproxy.ca.pem` (managed by
haproxy — adapters do not touch these).
