# SuiteAPI ambient authentication — how the v1 compliance stitcher authenticates with no operator credentials

**Date:** 2026-06-09
**Investigator:** api-explorer
**Instance:** devel `vcf-lab-operations-devel.int.sentania.net` (VCF Ops **9.0.2.0**, build 25137838)
**Pak under test:** compliance build 42 (v1 framework — `UnlicensedAdapter` / aria-ops-core stitcher), installed and collecting healthily on devel.
**Posture:** strictly READ-ONLY. Root SSH used for `cat`/`ls`/`/proc` reads/`ss`/`grep`, and three jars `scp`'d off-box for local `javap`/`strings` decompilation. **Nothing created, modified, restarted, or deleted on the appliance.** Local `/tmp` decompile scratch removed after.

This investigation blocks the compliance v2 migration: framework v2 (`vcfcf-adapter-base`, now directly on `AdapterBase`, `SuiteAPIClient` removed) must either reproduce this ambient mechanism or fall back to explicit Suite API credential fields.

---

## TL;DR / VERDICT

The v1 stitcher authenticates to the Suite API as a **built-in local service account `maintenanceAdmin`** (authSource `LOCAL`), over **localhost HTTPS to `https://localhost/suite-api/`** (real network, `127.0.0.1:443`), using a **username + encrypted password read from a plain file on disk**: `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties` (owner `admin:admin`, mode `0400` — readable by the collector, which runs as `admin`). The password is decrypted with `com.integrien.alive.common.security.Crypt`, **which ships in `vrops-adapters-sdk.jar`** (on the appliance shared classpath and the v2 compile classpath).

**This is NOT private in-process SDK wiring. It is a documented-shape, file-based credential + standard REST token auth that raw `AdapterBase` code can reproduce.** Therefore:

> **v2 transport recommendation: OPTION 1 — ambient reuse.** Have the v2 framework's REST pusher read `maintenanceuser.properties`, decrypt the password via the SDK's `com.integrien.alive.common.security.Crypt`, acquire a token at `POST https://localhost/suite-api/api/auth/token/acquire`, and push properties/relationships as `maintenanceAdmin`. No operator credential fields are required on the adapter config. Keep explicit-credential-fields (Option 2) only as a fallback/escape hatch for environments where the maintenance file is absent or unreadable (e.g. a remote collector — see Caveats).

The three options as framed in the brief:

1. **Ambient reuse via token file path + plain `java.net.http`** — **SUPPORTED, recommended.** The credential is a real on-disk file; the transport is ordinary localhost HTTPS REST. No SDK in-process session is involved.
2. **Explicit Suite API credential fields + framework REST pusher** — works, but unnecessary as the *default* on a standard all-in-one/cloud-proxy node. Best kept as a fallback.
3. **Private in-process session injection inside the SDK wrapper** — **NOT what v1 does.** Ruled out by evidence (real `127.0.0.1:443` sockets, real `token/acquire`+`token/release` REST pairs, real `maintenanceAdmin` LOGIN/LOGOUT audit events). There is nothing in-process to "reuse"; the SDK's `SuiteAPIClient` is itself just a REST client over localhost.

---

## Q1 — What principal do the stitcher calls hit the Suite API as?

**`maintenanceAdmin`** (userId `437440f9-992a-4397-9503-3348657ce863`, `authSource="LOCAL"`), connecting from `clientIP="127.0.0.1"`, `Origin: "REST_API"`.

Audit logging **is enabled** on devel. Evidence is in the analytics audit log
`/storage/log/vcops/log/analytics.audit-0ad8f158-5363-48d4-b6d0-2b50057b279c.log`. Representative login/logout pair (token acquire → release):

```
2026-06-10T02:53:04.936Z INFO audit ... userId="437440f9-992a-4397-9503-3348657ce863"
    username="maintenanceAdmin" authSource="LOCAL" session="4a5c642c-..."
    clientIP="127.0.0.1" auditID="AUTHENTICATION_LOGIN" ... Origin: "REST_API".
2026-06-10T02:53:05.006Z INFO audit ... username="maintenanceAdmin" ...
    auditID="AUTHENTICATION_LOGOUT" ... Log out succeeded.
```

These LOGIN/LOGOUT timestamps line up **to the millisecond** with the Suite API access-log token lifecycle (see Q2):

```
# /storage/log/vcops/log/suite-api/localhost_access_log.txt
2026-06-09T22:53:04.938Z 127.0.0.1 - - "POST /suite-api/api/auth/token/acquire HTTP/1.1" 200 197 16
2026-06-09T22:53:05.006Z 127.0.0.1 - - "POST /suite-api/api/auth/token/release HTTP/1.1" 200 - 6
```

**Caveat on attribution:** `maintenanceAdmin` is a shared platform service identity — many internal subsystems (not just compliance) authenticate as it, so the audit log alone shows thousands of `maintenanceAdmin` logins/day and does not tag the calling adapter. The tie to the compliance stitcher specifically is established structurally, not by audit attribution:
- The stitcher is `com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter.matchResource` / `ComplianceStitcher` (confirmed in the compliance adapter log — it logs `ComplianceStitcher: no VirtualMachine match for ...` from that class).
- That class calls the aria-ops-core `SuiteAPIClient` (Q3), whose **only** credential source is `maintenanceuser.properties` → `maintenanceAdmin` (the decompiled `getSuiteAPIMaintenanceUserCredential()` path, Q3). The adapter config carries no Suite API credential. So whatever principal the stitcher uses **must** be `maintenanceAdmin`.

The Suite API **access** log's remote-user field is unpopulated (`-`); principal identity comes from the **audit** log, not the access log. (The dedicated `/storage/log/vcops/log/opsapi.audit.log` is present but **0 bytes** on devel — the live audit stream is the analytics audit log above.)

Other principals seen in the same audit window with **UUID-shaped usernames** (e.g. `691f8e60-cfd6-42cd-930c-6857acf46177`, `aa13152f-81f0-4b25-9df9-8f9063453b3a`) are per-adapter-instance internal collection identities — distinct from the stitcher's `maintenanceAdmin`.

---

## Q2 — What transport does it use?

**Localhost HTTPS REST to `https://localhost/suite-api/` (`127.0.0.1:443`).** Not a Unix socket, not a loopback-only auth exemption, not the internal API.

Process / socket evidence (collector pid 1882229, runs as `admin`, `com.integrien.alive.collector.CollectorMain`):

```
# ss -tnp  (collector pid 1882229)
ESTAB      ... [::ffff:127.0.0.1]:57036  [::ffff:127.0.0.1]:443  users:(("vcops-collector",pid=1882229,...))
CLOSE-WAIT ... [::ffff:127.0.0.1]:45376  [::ffff:127.0.0.1]:443  ...   (many — per-call connections)
# remote :443 sockets go to vCenters 172.27.8.31/32; :10000 is gemfire — unrelated to the stitcher
```

The endpoint URL `https://localhost/suite-api/` is a hard-coded string constant in the aria-ops-core `SuiteAPICredential` class (Q3 disasm). The Suite API access log confirms the call pattern (token-scoped REST):

```
# /storage/log/vcops/log/suite-api/localhost_access_log.txt  (all clientIP 127.0.0.1)
POST /suite-api/api/auth/token/acquire            200   # log in (basic auth: maintenance user/pass)
POST /suite-api/api/resources/properties/latest/query?_no_links=true   200   # reads for matching
POST /suite-api/api/resources/query?...           200   # resource lookups (stitch target resolution)
POST /suite-api/api/resources/bulk/relationships?...  200   # relationship push (stitch)
POST /suite-api/api/resources/<uuid>/stats        200   # metric/property push onto foreign resource
POST /suite-api/api/auth/token/release            200   # log out
```

So the stitcher: **acquires a bearer token → queries to resolve the foreign HostSystem/VM resource → POSTs relationships and stats/properties → releases the token**, all to `127.0.0.1:443` (`/suite-api/api/...`, the *public* Suite API, not `/suite-api/internal/...`).

The TLS terminator on `127.0.0.1:443` is the platform Apache (`/var/log/apache2/access_log*`) fronting the suite-api webapp.

---

## Q3 — Is this reusable by raw AdapterBase code, or private SDK wiring?

**Reusable by raw AdapterBase code.** The mechanism is entirely file + standard REST; there is no in-process session that only the SDK wrapper can mint.

How v1 builds it (decompiled from `aria-ops-core-8.0.0.jar`, class
`com.vmware.tvs.vrealize.adapter.core.extensions.suiteapi.SuiteAPICredential`):

- `getSuiteAPIMaintenanceUserCredential()` calls `loadProperties(Constants.MAINTENANCE_CREDENTIALS_PATH)`.
- `Constants.MAINTENANCE_CREDENTIALS_PATH = <VCOPS user dir>/conf/maintenanceuser.properties`
  (built in `Constants`' static initializer from the VCF Ops user dir + `"conf"` + `"maintenanceuser.properties"`).
  Resolved on this appliance to **`/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`**.
- It reads property keys `username`, `password`, `encrypted`. When `encrypted=true` (it is), the password is decrypted via
  `com.integrien.alive.common.security.Crypt.getDefaultCrypt().decrypt(<password>)`.
- The endpoint is the constant `https://localhost/suite-api/`.
- `SuiteAPICredential` fields are simply `public final String username, password, url`; the `SuiteAPIClient(AdapterLoggerFactory, SuiteAPICredential)` constructor builds a `com.vmware.ops.api.client.Client` (the platform `vcops-suiteapi-client-2.2.jar`) and authenticates with those values. There is **no** ambient/loopback auth bypass — it is plain username+password → token.

Why raw `AdapterBase` (v2) code can reproduce all of this:
- **The file is plain on disk and readable by the collector user.** `maintenanceuser.properties` is `admin:admin 0400`; the collector runs as `admin`. Any code in the collector JVM can `Files.readString(...)` it.
- **The decryptor is on the v2 classpath.** `com.integrien.alive.common.security.Crypt` ships **inside `vrops-adapters-sdk.jar`** (verified: `com/integrien/alive/common/security/Crypt.class` present), which is on the appliance shared classpath and is the v2 framework's compile classpath. Public API: `Crypt.getDefaultCrypt()` → `.decrypt(String)`. So v2 does **not** need aria-ops-core to decrypt — it can call the SDK's own `Crypt`.
- **The transport is ordinary HTTPS REST.** `POST https://localhost/suite-api/api/auth/token/acquire` with the maintenance username/password returns a token; subsequent calls send it. The v2 `HttpClientBuilder` / `ManagedHttpClient` + `BasicAuth`/`BearerAuth` already cover this. (`platformSsl(this)` for the localhost cert, or `allowInsecure(true)` lab opt-out for the self-signed localhost cert.)

The only thing the SDK wrapper "added" was constructing the aria-ops-core `SuiteAPIClient`; the credential and transport underneath are reproducible without aria-ops-core and without any SDK-private session.

---

## Q4 — Supporting evidence (paths, permissions, shapes — no secret values)

**Credential file (REDACTED — keys/shape only, never values):**

```
path:  /usr/lib/vmware-vcops/user/conf/maintenanceuser.properties
owner: admin:admin   mode: 0400 (-r--------)   size: 186 bytes   mtime: Apr 16 22:12
keys:  username=<redacted>   (value length 16  → "maintenanceAdmin", 16 chars, matches audit principal)
       password=<redacted>   (value length 27, encrypted)
       encrypted=true
decryptor: com.integrien.alive.common.security.Crypt.getDefaultCrypt().decrypt(...)
           (class present in vrops-adapters-sdk.jar AND alive jars; on collector classpath)
```

**Collector process (pid 1882229):** runs as `admin`; `com.integrien.alive.collector.CollectorMain`; classpath includes `vcops-suiteapi-client-2.2.jar`, `vcops-suiteapi-internal-client-2.2.jar`, `vrops-adapters-sdk.jar`. (No Suite API credentials in `/proc/<pid>/environ` — the environ carries role/wrapper vars only; credentials come from the file, not env.)

**Audit log (principal, timestamped) — REDACTED of session tokens:**
`/storage/log/vcops/log/analytics.audit-<instanceId>.log`
`username="maintenanceAdmin" authSource="LOCAL" clientIP="127.0.0.1" auditID="AUTHENTICATION_LOGIN" Origin:"REST_API"`, LOGIN/LOGOUT pairs matching the access-log token acquire/release to the millisecond.

**Suite API access log (endpoints/timing):**
`/storage/log/vcops/log/suite-api/localhost_access_log.txt` — `127.0.0.1` token acquire → `resources/*/query`, `bulk/relationships`, `resources/<uuid>/stats` → token release. Public `/suite-api/api/...`, not `/internal/`.

**Compliance stitcher class (ties the path to compliance):**
`/usr/lib/vmware-vcops/user/log/adapters/ComplianceAdapter/ComplianceAdapter_3240.log` —
`com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter.matchResource` logging `ComplianceStitcher: no VirtualMachine match for ...`. The compliance adapter collects ~hourly (cycles observed at ~:10–:16 each hour; latest 2026-06-10T02:13Z).

**Decompiled classes (off-box, local `/tmp` scratch, since removed):**
- `aria-ops-core-8.0.0.jar` → `…suiteapi.SuiteAPICredential` (path/url/decrypt logic), `…configuration.Constants` (path construction), `…suiteapi.SuiteAPIClient` (REST client over `com.vmware.ops.api.client.Client`).
- `vrops-adapters-sdk.jar` → `com.integrien.alive.common.security.Crypt` (decrypt API).
- `vcops-suiteapi-client-2.2.jar` → `com.vmware.ops.api.client.*` controllers (the actual REST surface).

---

## Implications for v2 (compliance migration) — concrete

1. **Add an "ambient maintenance credential" provider to the v2 framework** (or to the compliance adapter's stitcher path): read `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`, honor `encrypted=true` via `com.integrien.alive.common.security.Crypt` (already on classpath — no new dependency), and feed username/password to the framework REST pusher targeting `https://localhost/suite-api/`. The path should be derived, not hard-coded, ideally from the same VCF Ops user dir the SDK exposes; `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties` is the resolved value on 9.0.2.
2. **No operator credential fields on the compliance adapter config are required** for the standard case — this preserves v1's zero-config stitching behavior.
3. **Keep explicit Suite API credential fields as a documented fallback** (Option 2) for the cases in Caveats below; the framework REST pusher is the same either way, only the credential source differs.
4. **Token lifecycle:** mirror v1 — acquire per collection (or cache briefly) and release. The access log shows v1 acquires/releases around each batch; a short-lived token per cycle is the proven-safe pattern.
5. **SSL to localhost:** the localhost Suite API presents the platform self-signed cert; use `platformSsl(this)` (preferred) or the explicit `allowInsecure(true)` lab opt-out.

---

## Caveats / where ambient reuse can fail (drives the Option-2 fallback)

- **Remote collectors.** This evidence is from an all-in-one node where the collector is co-resident with the Suite API on `127.0.0.1:443`. On a **remote collector / cloud proxy**, `https://localhost/suite-api/` may not be reachable and/or `maintenanceuser.properties` may not be present. The v2 framework should detect file-absence/connect-failure and fall back to explicit credential fields. (Not tested here — devel is all-in-one.)
- **9.1 platform.** This was confirmed on **devel 9.0.2 only**. The file path, the `maintenanceAdmin` account, and the localhost endpoint should be re-confirmed on 9.1 before shipping v2 to a 9.1 target. (Separately, 9.1 has the JAX-WS javax/jakarta collision documented in `prod_91_jaxws_provider_failure.md` — orthogonal to this auth mechanism, but relevant to the same compliance v2 build.)
- **Crypt key scoping.** `Crypt.getDefaultCrypt()` resolves the platform's default crypt key on the local node; decryption works because it runs in-collector on the same appliance that wrote the file. This is inherently a **local-node** mechanism — another reason it is unsuitable for remote collectors and must degrade to explicit credentials there.
- **Username could differ.** The principal name is `maintenanceAdmin` here (16-char `username` value). v2 must read it from the file, not assume the literal string, in case a future build renames it.

---

## Clean-up

Off-box jars and local decompile scratch were under `/tmp/ambient_probe/` on the **investigator host** (not the appliance) and were removed. **Nothing was created, modified, or deleted on the devel appliance** — all appliance access was `cat`/`ls`/`ss`/`grep`/`/proc` reads.

---

## Prod 9.1 confirmation (2026-06-09)

**Instance:** prod `vcf-lab-operations.int.sentania.net` — VCF Ops **9.1.0.0**
(`vrops-init-9.1.0.0100-25434855`; the cosmetic `vmware-vcops` rpm still reads
`9.0.0.0-25434844`, but init/build is the 9.1 line). Collector pid **6350**,
runs as **admin** (uid 1000), `vcops-collector` / OpenJDK 17.0.16.
**Posture: strictly READ-ONLY** — root SSH (`sshpass`, doubled password,
length 20) used for `cat`/`ls`/`stat`/`ss`/`grep`/`unzip -l`/`/proc` reads only.
No Suite API token acquired as maintenanceAdmin. Nothing created, modified,
restarted, or deleted. `/tmp` verified clean (no artifacts created this session).

### VERDICT: **AMBIENT PATTERN CONFIRMED ON 9.1** — with two benign deltas (perms 0600, SDK jar versioned `1.0`/`9.1.0.0`), neither of which breaks the mechanism.

All four pillars hold on 9.1. Point-by-point against the 9.0.2 finding:

| # | Pillar | Devel 9.0.2 | Prod 9.1 | Status |
|---|---|---|---|---|
| Q1 | `maintenanceuser.properties` exists | yes | **yes** (`/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`, 186 bytes, mtime Oct 1 2025) | SAME path |
| Q1 | keys | `username`/`password`/`encrypted` | **same three keys**; `encrypted=true` | SAME |
| Q1 | owner | `admin:admin` | **`admin:admin`** (uid 1000 / gid 1003) | SAME |
| Q1 | mode | `0400` (`-r--------`) | **`0600`** (`-rw-------`) | **DELTA — still owner-readable** |
| Q1 | collector can read it | yes (collector=admin) | **yes** — collector pid 6350 runs as uid 1000 (admin); file owner uid 1000, owner-read bit set → readable | SAME (intact) |
| Q2 | Suite API on localhost:443 | yes | **yes** — httpd LISTEN `0.0.0.0:443`; collector pid 6350 holds live `127.0.0.1:*→127.0.0.1:443` sockets | SAME |
| Q3 | `maintenanceAdmin` account exists | yes | **yes** (`authSource="LOCAL"`); **35,063** audit lines, **7,206** REST_API logins from origin `127.0.0.1`; live `token/acquire→token/release` pairs in `localhost_access_log.txt` matching audit LOGIN to the millisecond | SAME |
| Q4 | `com.integrien.alive.common.security.Crypt` in SDK jar | yes | **yes** — `com/integrien/alive/common/security/Crypt.class` present in `/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar` (`unzip -l`) | SAME (class present) |

### Q1 detail — credential file (keys/shape only, no values)

```
path:  /usr/lib/vmware-vcops/user/conf/maintenanceuser.properties
owner: admin:admin (uid 1000 / gid 1003)   mode: 0600 (-rw-------)   size: 186 bytes   mtime: 2025-10-01
keys:  password   encrypted   username        (same three as 9.0.2)
       encrypted=true                         (boolean flag value only — no FIPS/format change in the flag itself)
```

**Perm delta (0600 vs devel 0400):** the file is now group/other-unreadable
but **owner read+write** instead of owner read-only. The collector runs **as
the owner** (`admin`), so it can still read it — readability is unaffected. This
is a tightening-then-loosening cosmetic difference on the owner write bit, not a
break. v2 code reading the file as the collector user is unaffected.

### Q3 detail — `maintenanceAdmin` still live on 9.1

`/storage/log/vcops/log/analytics.audit-<instanceId>.log` (253 MB, live).
Representative redacted REST_API login (the stitcher-shaped path):

```
2026-06-10T02:59:40.006Z INFO audit ... subject="maintenanceAdmin" authSource="LOCAL"
    session=REDACTED origin="127.0.0.1" result="success" comment="Log in success. Origin: \"REST_API\"."
```

Matching localhost Suite API token lifecycle (same millisecond):

```
# /storage/log/vcops/log/suite-api/localhost_access_log.txt
2026-06-10T02:59:40.007Z 127.0.0.1 - - "POST /suite-api/api/auth/token/acquire HTTP/1.1" 200 202 5282
2026-06-10T02:59:40.072Z 127.0.0.1 - - "POST /suite-api/api/auth/token/release HTTP/1.1" 200 - 3520
```

Note the 9.1 audit record format shifted slightly from devel
(`auditID="AUTHENTICATION.LOGIN"`, `subject=`/`userID=`/`origin=` field names vs
devel's `auditID="AUTHENTICATION_LOGIN"`, `username=`/`userId=`/`clientIP=`). This
is a **log-schema cosmetic change only** — the principal, authSource, and REST
token flow are identical. The `opsapi.audit.log` is present but 0 bytes (same as
devel — the live stream is the analytics audit log).

### Q4 detail — Crypt decryptor present on 9.1

`com/integrien/alive/common/security/Crypt.class` is in the platform
`vrops-adapters-sdk.jar` (the unversioned symlink-equivalent and
`vrops-adapters-sdk-1.0.jar`, both 994024 bytes, `admin:admin`,
`/usr/lib/vmware-vcops/common/lib/`). The platform SDK jar is versioned **`1.0`**
on 9.1 (the same jar ships into ~30 controller plugins, the suite-api webapp, ui,
etc.). The decrypt class is byte-present; the public `Crypt.getDefaultCrypt().decrypt(...)`
path remains available on the collector classpath.

### Q5 — 9.1-specific factors that could affect the pattern

- **FIPS approved-only mode is ON.** The collector JVM carries
  `-Dorg.bouncycastle.fips.approved_only=true`. The `encrypted=true` flag in the
  file is unchanged in shape, and the platform `Crypt` class is the same FQCN in
  the same SDK jar — so decryption is expected to work in-collector (it is the
  same JVM that the platform itself uses to read this file). **However**, v2
  must use the platform's own `Crypt`/crypt-key resolution (as v1 does), not a
  hand-rolled cipher, because under FIPS approved-only a non-approved cipher
  construction could throw. This is already the recommended approach (reuse the
  SDK `Crypt`), so no change to the v2 plan — but it is a *hard* reason not to
  reimplement the decryption.
- **Perm 0600 not 0400** (above) — cosmetic, still owner-readable.
- **Audit log schema field-name change** (above) — affects anyone *parsing* the
  audit log for attribution, not the auth mechanism. Not load-bearing for v2.
- **No file move, no account rename, no localhost-API removal.** The three things
  that would have broken the pattern are all absent.
- **Orthogonal known issue:** prod 9.1's compliance stitcher is currently down
  with the JAX-WS javax/jakarta `Provider` collision
  (`prod_91_jaxws_provider_failure.md`). That failure is at vim25 SOAP-stub
  creation, **before** any Suite API call — it does **not** touch this ambient
  auth path. The `maintenanceAdmin` REST traffic seen above (7,206 localhost
  logins) is other platform subsystems, confirming the auth surface is healthy
  independent of our stitcher's collection failure.

### Bottom line for v2 on 9.1

The OPTION-1 ambient-reuse recommendation from the 9.0.2 finding **carries
over to 9.1 unchanged**: read `maintenanceuser.properties` (same path, same
keys, owner-readable by the collector), decrypt via the platform SDK
`com.integrien.alive.common.security.Crypt` (present, and mandatory to reuse
given FIPS approved-only), acquire a token at
`POST https://localhost/suite-api/api/auth/token/acquire` as `maintenanceAdmin`,
push, release. No operator credential fields required on the standard all-in-one
9.1 node. The only code-relevant caution new to 9.1 is **do not reimplement the
decryption** (FIPS approved-only) — call the SDK `Crypt`.

### Clean-up (prod 9.1)

All prod appliance access was `cat`/`ls`/`stat`/`ss`/`grep`/`unzip -l`/`/proc`
reads. **Nothing created, modified, restarted, or deleted.** No Suite API token
acquired. `/tmp` confirmed free of artifacts. Clean-up verified: yes.
