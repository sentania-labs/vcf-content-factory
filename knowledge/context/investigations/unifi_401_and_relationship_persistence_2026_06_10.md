# UniFi adapter: 401 storm + relationship non-persistence — root-cause investigation

**Date:** 2026-06-10
**Instance under study:** `UniFiAdapter_5051` (adapterKind `unifi_controller`) on
the devel appliance (`vcf-lab-operations-devel`).
**Posture:** strictly read-only. UniFi controller: HTTP GETs + one login
(session only). VCF Ops appliance: read-only SSH + one Suite API token
(released). **Zero** resources or config created/modified on either system.

> **Unsupported-endpoint note:** none of the endpoints used here are
> unsupported VCF Ops internal APIs; the Suite API auth/resources/relationships
> calls are all public `suite-api`. No `X-Ops-API-use-unsupported` header was
> required.

---

## TL;DR verdicts

- **Part A (the 401 storm): adapter-code defect, NOT a controller lockout.**
  A fresh login to the UniFi controller with the `.env` credentials returns
  **HTTP 200** right now (no 429, no bad-creds 401, no 2FA). The controller
  expires the `TOKEN` session cookie after some interval; once it does, the
  adapter's cached cookie is never invalidated, so every subsequent request
  re-presents the dead cookie and gets 401 forever. The framework
  `SessionCookieAuth` only re-logs-in when its cached token is `null`, and
  **nothing in the UniFi client or the framework HTTP path ever nulls it on a
  401.** Synology recovers from the identical situation because *its* client has
  an explicit session-expiry re-login; UniFi has none.

- **Part B (relationships): the edges are emitted correctly and completely;
  they are lost at platform persistence. The prime suspect is the
  `RelationshipBuilder` ResourceKey constructor-argument swap, and there is NO
  live working v2 control proving otherwise.** Both the "only 18 of ~130 edges
  leave the adapter" and "server acks 0 of 18" clues from recon are **misreads**
  (explained below). UniFi is in fact the **first and only** v2 (`RelationshipBuilder`
  + `setRelationships`) adapter ever to attempt relationship persistence on this
  appliance, and it persists **zero**. Synology's persisted tree visible in the
  Suite API is **stale residue from 2026-05-27 built by the v1 adapter** (correct
  ResourceKey order, `Resource.addChild()` graph API) — it is not evidence that
  the current v2 framework persists anything.

---

## Part A — classify the 401 (controller side)

### A1. Fresh login works right now — no lockout

Replicated the adapter's exact login (`UniFiApiClient.login`:
`POST /api/auth/login` with a JSON `{username,password}` body) from this
workstation against the controller in `.env`:

| Probe | Result |
|---|---|
| `POST /api/auth/login` (real creds) | **HTTP 200**; sets `TOKEN` cookie; returns `x-csrf-token` + `x-updated-csrf-token` headers |
| `GET /proxy/network/api/self/sites` **with** valid `TOKEN`, no CSRF header | **HTTP 200** |
| same GET with a **bogus/expired** `TOKEN` cookie | **HTTP 401** (body `content-type: application/json`, no distinguishing header) |
| same GET with **no** cookie | **HTTP 401** |

Conclusions:
- **No account lockout, no 429, no 2FA challenge, no bad-creds.** The creds are
  good and the controller is healthy. The 401 storm is therefore **not** a
  controller-side condition.
- A UniFi-OS GET needs only the `TOKEN` cookie; **CSRF is not required** for the
  adapter's read calls. So a stale-CSRF theory is ruled out — the adapter never
  sends CSRF and doesn't need to.
- An expired cookie and a missing cookie are **indistinguishable** to the client
  (both bare 401, same body shape). The only signal available is the status code.

### A2. Why the adapter never recovers (the failing code path)

The session model is: `UniFiAdapter.buildHttpClient` wires a framework
`SessionCookieAuth("TOKEN", () -> UniFiApiClient.login(...))`. The token is
cached for the **lifetime of the adapter instance**:

`SessionCookieAuth.apply()` (framework):
```java
String token = cachedToken.get();
if (token == null) {            // re-login ONLY when the cache is empty
    token = acquireFresh();
}
builder.header("Cookie", cookieName + "=" + token);
```
`cachedToken` is set to `null` only by `invalidate()` / `discard()`, which are
called from `onConfigure`/`onDiscard` — **never on a 401.**

`UniFiApiClient.get()` (adapter):
```java
HttpResponse<String> resp = http.get(path, ...);
if (resp.statusCode() != 200) {
    throw new IOException("UniFi GET " + redact(path) + " returned HTTP "
            + resp.statusCode());          // <-- 401 becomes a plain IOException
}
```
There is no `if (401) { auth.invalidate(); retry; }` anywhere — confirmed by
grep across the UniFi adapter and the framework `auth/`, `http/`, `retry/`
packages: the only `invalidate` hits are `UniFiStitcher.invalidateCache` (a
Suite-API resolver cache, unrelated) and `SessionCookieAuth.invalidate` (never
called on the data path). The framework `RetryPolicy` retries on
`ConnectException`/IO transients, not on an HTTP-401-shaped success.

**Net effect:** the first cycle after the controller expires the cookie throws
`HTTP 401`, the framework marks the resource ERROR, the cached cookie is left
in place, and **every** subsequent cycle reuses the dead cookie → permanent
401 until the instance is reconfigured/restarted. The live log shows exactly
this: clean collection through 12:20:26Z, then from `12:25:25Z` onward every
resource and the `rediscover()` enumeration fail with
`UniFi GET /proxy/network/api/self/sites returned HTTP 401`, indefinitely.

### A3. Why Synology does not have this failure (the contrast)

`SynologyApiClient.call()` wraps every authenticated call in an explicit
expiry-and-retry:
```java
ensureSession();                                   // login if sid == null
SimpleJson resp = callRaw(...);
if (!resp.isSuccess()) {
    int code = ...;
    if (code == 106 || code == 107 || code == 119) {   // DSM "session expired"
        invalidateSession();                            // null the sid
        login();                                        // re-auth
        resp = callRaw(...);                            // and RETRY the call
    }
    ...
}
```
Synology owns its session (it uses a `_sid` query param, deliberately *not* the
framework cookie auth) and recovers transparently. UniFi delegated session
handling to `SessionCookieAuth`, which has no expiry-recovery path — so the
recovery the adapter needs simply does not exist for it.

---

## Part B — relationship persistence (appliance side)

### B0. Ground truth from the Suite API (read-only)

| adapterKind | resources | World→child edges in Suite API | live today? |
|---|---|---|---|
| `unifi_controller` | 128 | **0** (World children=0, parents=0; first 30 resources: 0 of 30 have any edge) | yes (until 401) |
| `synology_diskstation` | 25 | **present** — World→Diskstation→StoragePool→{5 disks, 2 cache disks, Volume 1}; Diskstation→Universe | **no — last collect 2026-05-27** |
| `vcfcf_compliance` | 3 | 0 (World has no children — compliance builds an essentially flat tree) | yes |

So UniFi's edges genuinely do **not** persist (confirmed directly, not inferred
from a counter). But the synology tree that "persists" is **not a live control**
— see B3.

### B1. The two recon clues are both misreads

**"Server acks 0 of 18" is a misread.** The `Sending task … Relationship items
count: 18` / `Received response … Relationship items count: 0` round-trip in
`collector.log` is the **Auto-Discover task counter**, and "0 on the response"
is the **normal acknowledgement** for *every* adapter — including ones whose
edges definitely persist:
- `VMWARE` inst 121: sends count **1** → response **0**
- `VirtualAndPhysicalSANAdapter` inst 64: sends count **14** → response **0**
- `synology_diskstation` inst 3036: sends count **5/8** → response **0**

The "N in, 0 out" pattern is universal and is **not** a drop signal.

**"Only 18 of ~130 edges leave the adapter" is a misread.** `18` is the number
of **relationship *items*** = distinct parent groups, not edges.
`RelationshipBuilder.build()` emits one `setRelationships(parent, children)`
call **per parent**. For the live UniFi topology (1 site, 1 gateway+2 WANs,
8 switches, 6 APs, 1 NVR) the distinct parents are:
World(1) + Site(1) + Gateway(1) + 8 switches + 6 APs + NVR(1) = **18**.
Those 18 items carry **all ~130 child edges** between them. The adapter logs
`Relationships built: … tree` every cycle and `LLDP→HostSystem cross-link: 0
port→host edges` (the cross-link legitimately matches nothing). Nothing is
truncated; the full set leaves the adapter.

**"Processing relationship took … is the accept signal, and UniFi/Synology lack
it" is also a misread.** `processRelationShip` is a method of the legacy
`com.integrien.adapter.vmware.VMwareAdapter` — it appears **only** for instances
121/63 (VMWARE). v2/SDK adapters attach relationships through
`CollectResult.addRelationships` (a different code path that does not emit that
log line). Its absence for synology and unifi is expected and non-diagnostic.

### B2. How each adapter emits relationships (mechanism)

Both v2 adapters use the **identical** documented multi-resource idiom
(`knowledge/context/framework_v2_migration.md` §18): build the full topology once, return
it only on the **World** resource's `collectRelationships(rc)` call; the
framework calls `addRelationshipsToCurrentCycle(rels)` →
`collectResult.addRelationships(rels)`. Both build keys via
`RelationshipBuilder.resource(kind, name, idKey, idValue)`. The identifier keys
match between registration and relationship construction on both sides
(unifi: `world_id`/`site_name`/`mac`; identical in both paths).

The one **structural** difference between them:

| | resource registration | discovery trigger |
|---|---|---|
| Synology (v1, the persisted tree) | `Resource.addChild()/addParent()` graph API; `ResourceKey(name, kind, adapterKind)` **correct order** | real `onDiscover()` |
| Synology (v2 source in repo) | `RelationshipBuilder` + `setRelationships` | real `onDiscover()` |
| UniFi (v2, live) | `RelationshipBuilder` + `setRelationships` | **collect-path** `registerNewResource` (`needsRediscovery()=true`/`rediscover()`), because VCF Ops 9.0.2 never calls `onDiscover()` |

### B3. The synology "control" is stale residue, not live proof — TOOLSET GAP

This is the crux and the honest limit of a read-only investigation:

- Synology instance 3036's Suite-API tree was last (re)built on **2026-05-27**,
  by the **v1** adapter (`com.vmware.tvs…UnlicensedAdapter`, log message
  "internal tree + datastore stitching", `pool-…-thread`). v1 built keys with
  the **correct** `ResourceKey(name, kind, ADAPTER_KIND)` order (ref source
  lines 973/980) and used `Resource.addChild()` — **not** the v2
  `RelationshipBuilder`/`setRelationships` path.
- Synology 3036 has **not collected successfully since 2026-06-07**: it dies
  every cycle with `java.lang.IllegalArgumentException: restricted header name:
  "Host"` (a *separate* framework bug — `ManagedHttpClient.sendWithRoundRobin`
  sets a `Host` header the JDK `HttpClient` forbids; it fires for synology
  because its hostname resolves to multiple IPs, then `HttpTimeoutException`).
  The Suite-API tree is simply old persisted state that was never torn down.
- The only v2 adapter that has built relationships in the current framework era
  is **UniFi (today)** — and it persists **zero**.

Therefore: **there is no live, working v2 adapter on this appliance that proves
`RelationshipBuilder` + `setRelationships` persistence works.** I cannot, purely
read-only, fully separate these candidate root causes for the zero-persistence:

1. **`RelationshipBuilder` ResourceKey constructor swap (prime suspect).**
   `RelationshipBuilder.resource()` calls
   `new ResourceKey(adapterKind, resourceKind, name)`, but the verified SDK
   3-arg constructor is `ResourceKey(resourceName, resourceKind, adapterKind)`
   (bytecode disassembly of `vrops-adapters-sdk-2.2.jar`: fields are set in the
   order name, kind, adapterKind). The builder therefore produces keys whose
   `adapterKind` field holds the **human name** and whose `resourceName` field
   holds the literal **adapter-kind string**. `ResourceKey.equals` →
   `compareTo` compares **adapterKind first** (`compareToIgnoreCase`), then
   resourceKind, then (when identifiers are present) the identifier list. With
   `adapterKind` corrupted to the display name, a relationship endpoint can
   never compareTo-equal the registered resource (whose `adapterKind` =
   `"unifi_controller"`), so the platform cannot bind the edge to a real
   resource → the edge is dropped at persist time. The adapters'
   **registration** path (`rcOf`) uses the **correct** order, so the resources
   themselves register fine — only the **relationship endpoints** are corrupted.
   This swap has existed since framework build 8 (commit `379b7d8`) and has
   **never** been exercised by a live, persisting v2 adapter until UniFi.

2. **Collect-path registration interaction.** UniFi registers all 127 resources
   (incl. the World anchor) via `registerNewResource` on the collect path rather
   than `onDiscover()`. It is conceivable the platform binds relationship
   endpoints only against resources known from a discovery task at the moment
   the relationships are processed. This is **plausible but unproven**; I could
   not isolate it read-only.

The evidence weight is on (1): it is a concrete, verified constructor-order bug
on the exact field `ResourceKey.compareTo` checks first, and the only adapter
that ever persisted a tree did so with the *correct* order via a different API.

> **TOOLSET GAP (honest):** confirming (1) as the sole cause vs. a contribution
> from (2) requires a mutating experiment (e.g. a one-line `RelationshipBuilder`
> fix in a dev build, or a probe instance that registers via `onDiscover()`),
> which is out of scope for this read-only brief. Recommend the build-5 author
> fix (1) first (cheap, certain to be *a* bug) and re-observe persistence before
> investigating (2).

---

## Recommended fix list for the UniFi build-5 author

**A. 401 / session recovery (Part A) — required, this is the GREY-everything bug.**

1. **Add 401-driven re-login + single retry in `UniFiApiClient.get()`.** On a
   401 (and 403, which UniFi OS also uses for an invalid session), invalidate
   the cached session and retry once. The client needs a handle to the
   `SessionCookieAuth` (or a re-login callback) so it can call `invalidate()`
   before the retry. Sketch:
   ```java
   HttpResponse<String> resp = http.get(path, ofString());
   if (resp.statusCode() == 401 || resp.statusCode() == 403) {
       auth.invalidate();              // force re-login on next apply()
       resp = http.get(path, ofString());   // one retry with a fresh TOKEN
   }
   if (resp.statusCode() != 200) throw new IOException(...);
   ```
   This mirrors the proven `SynologyApiClient.call()` 106/107/119 recovery.

2. **Preferred (framework-level, fixes every cookie-auth adapter):** teach the
   framework to recover from 401 on the cookie path — e.g. a
   `SessionCookieAuth`-aware wrapper in `ManagedHttpClient` that, on a 401,
   calls `auth.invalidate()` and replays the request once. This is the more
   durable fix; the UniFi build-5 author should flag it as a `tooling`/framework
   change rather than only patching UniFi. (Route through the `tooling` agent —
   it owns `vcfops_managementpacks/adapter_framework/`.)

**B. Relationship persistence (Part B) — fix the builder, then re-verify.**

3. **Fix the `RelationshipBuilder` ResourceKey constructor order (framework
   change, `tooling` agent).** In
   `vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/RelationshipBuilder.java`,
   `resource()` must construct
   `new ResourceKey(name, resourceKind, adapterKind)` — currently
   `new ResourceKey(adapterKind, resourceKind, name)`. Verified against the SDK
   bytecode (`ResourceKey(resourceName, resourceKind, adapterKind)`) and against
   how both adapters' own `rcOf()` correctly order the same three args. This is
   a single-line fix that affects **every** v2 adapter using the builder.

4. **After (3): rebuild and re-observe UniFi relationship persistence directly
   via the Suite API** (`/resources/{world}/relationships?relationshipType=CHILD`
   should return the Site, etc.). Do **not** rely on the `collector.log`
   "Relationship items count" counter — it reads 0 on the response for working
   adapters too.

5. **If edges still do not persist after (3)+(4): investigate the collect-path
   registration path (candidate 2).** Try registering the World (at minimum the
   relationship-anchor resources) through a real `onDiscover()` as well, or
   confirm the platform binds relationship endpoints against collect-path-
   registered resources. This step is only needed if (3) is insufficient.

**C. Incidental — `restricted header name: "Host"` (framework, affects
multi-IP hosts like the Synology NAS).** `ManagedHttpClient.sendWithRoundRobin`
sets a `Host` header, which the JDK `HttpClient` rejects with
`IllegalArgumentException`. UniFi's host resolves to a single IP so it has not
hit this, but it is a latent framework bug that bricks any adapter whose target
is multi-homed (it is what killed synology 3036 on 06-07). Flag to `tooling`.
The JDK forbids setting `Host` directly; SNI/vhost must be steered another way
(e.g. a custom `HostnameVerifier`/SNI parameter, or per-IP `HttpClient`s),
not via a `Host` request header.

---

## Evidence appendix (commands were read-only; values never logged)

- UniFi login + cookie/CSRF probes: `curl` `POST /api/auth/login` and
  `GET /proxy/network/api/self/sites` with valid / bogus / no cookie.
- SDK `ResourceKey` constructor + `compareTo` field order: `javap -p -c` on
  `ResourceKey.class` from `vrops-adapters-sdk-2.2.jar`.
- Suite API: `auth/token/acquire`, `resources?adapterKind=…`,
  `resources/{id}/relationships?relationshipType=CHILD|PARENT` (token released).
- Appliance logs (read-only SSH): `UniFiAdapter_5051.log`,
  `SynologyAdapter_3036.log`, `collector.log*`.
- Source: `RelationshipBuilder.java`, `SessionCookieAuth.java`,
  `ManagedHttpClient.java`, `VcfCfAdapter.java`, `UniFiAdapter.java`,
  `UniFiApiClient.java`, `SynologyAdapter.java`, `SynologyApiClient.java`;
  git history of `RelationshipBuilder` (commit `379b7d8`).
