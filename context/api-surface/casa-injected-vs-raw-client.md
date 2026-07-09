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

## Evidence (jars in `src/vcfops_managementpacks/adapter_runtime/`)

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
  `verify("false")`, `ignoreHostName(true)`. **This is server-side
  trust only** (a truststore to verify the server) — there is **no
  client keystore, no client cert, no node/slice identity, no
  mutual-TLS client material** anywhere in the class.
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
