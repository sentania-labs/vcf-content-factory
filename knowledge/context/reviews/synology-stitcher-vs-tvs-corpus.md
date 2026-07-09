# Synology stitcher vs. the modern-TVS idiom — architecture review

**Reviewer:** `sdk-adapter-reviewer` (read-only) · **Date:** 2026-07-01
**Scope:** cross-MP relationship stitching in `content/sdk-adapters/synology`
(and shared framework `vcfops_managementpacks/adapter_framework/…/stitch/`),
measured against the presumed-correct 2023–2024 Broadcom TVS idiom documented in
`knowledge/context/api-maps/tvs-cross-mp-stitching.md`.
**Posture:** static; no build, no install, no live instance touched. Every
verdict is backed by a code quote or an explicit "can't determine from source."

This is an architecture opinion for a future `sdk-adapter-author` briefing, **not**
a build gate. No verdict block; no defect-registry closure proposals (the two open
defects that touch this surface — DEF-002 unifi, DEF-003 synology-closed — are
discussed inline where relevant).

---

## Evidence base (read, not re-derived)

- `knowledge/context/api-maps/tvs-cross-mp-stitching.md` — the vendor idiom (bytecode RE of 8 paks).
- `knowledge/context/cleanroom-requests/2026-06-30-CORRECTION-cp-stitches-via-casa.md` — the CaSA correction.
- `knowledge/context/investigations/recon_log.md` (2026-07-01 Oracle entry) — live proof Oracle stitches creds-free from the CP.
- `knowledge/lessons/setrelationships-foreign-adapter-scoped.md` — our 9.0.2-proven / 9.1-unverified scoping assumption.

Code read in full: `SynologyAdapter.java`, `SynologyStitcher.java`,
`SuiteApiStitcher.java`, `SuiteApiStitchClient.java`, `AmbientCredential.java`,
`RelationshipBuilder.java`, `VcfCfAdapter.java` (SSL/transport section), plus the
parallel `unifi` adapter + stitcher.

---

## Q1 — Which door does our stitcher use? **VERDICT: the user-credential door. Confirmed.**

Our stitcher authenticates by POSTing a **username/password/authSource** token
acquire to `https://localhost/suite-api` — the exact door the TVS map says 403s
for `cloudproxy_<uuid>` on a Cloud Proxy. It is **not** the CaSA node-certificate
door.

`SuiteApiStitchClient.acquireToken()`
(`vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/SuiteApiStitchClient.java:515-518`):

```java
String body = "{\"username\":" + jsonStr(resolvedUsername)
        + ",\"password\":" + jsonStr(resolvedPassword)
        + ",\"authSource\":" + jsonStr(AUTH_SOURCE) + "}";   // AUTH_SOURCE = "LOCAL"
String responseBody = urlConnRequest("POST",
        suiteApiBase + "/api/auth/token/acquire", body, null);
```

The ambient principal is the **maintenance user credential** read off disk, not a
node identity — `AmbientCredential` parses
`/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties` and decrypts the
password (`AmbientCredential.java:88`, `KEY_USERNAME`/`KEY_PASSWORD`,
`SuiteApiStitchClient.build():289-306`). On a primary node that principal
(`maintenanceAdmin`) carries resource-read RBAC → works creds-free. On a CP the
same door is served by the empty-roles `cloudproxy_<uuid>` account → 403.

**Important nuance on the transport vs. the auth identity.** The class doc and the
build-21/22 reviews correctly note that the *TLS layer* is unified on
`VcfCfAdapter.openPlatformConnection()` — the platform `CustomSSLSocketFactory`
(TOFU-survival) + peer-gated hostname verifier (`SuiteApiStitchClient:611-612`,
`VcfCfAdapter.java:1030-1043`). That fixes the *handshake* (loopback SAN / cert
trust). It does **nothing** for the *authorization* identity: the bearer token is
still minted from a user credential via `token/acquire`. Using the platform socket
factory is not the same as using the CaSA node-cert badge. **We are on the wrong
door regardless of how good the TLS posture is.**

Matches the documented residual in `synology-build-22.md` ("`cloudproxy_<uuid>`→403
vs explicit-account→200") — that residual is the direct fingerprint of the
user-credential door.

---

## Q2 — Injected vs raw client (the root cause). **VERDICT: we extend bare `AdapterBase` and hand-roll a raw REST client. Confirmed — this is the root cause.**

`SynologyAdapter extends VcfCfAdapter<SynologyConfig>` and
`VcfCfAdapter … extends AdapterBase` directly
(`VcfCfAdapter.java:120`) — **not** `UnlicensedAdapter`. The adapter's own class
doc states the migration explicitly (`SynologyAdapter.java:34-40`):

> "Re-homed from aria-ops-core (`UnlicensedAdapter` + `com.vmware.tvs.*`) onto
> `VcfCfAdapter` (which extends `AdapterBase` directly) … No `com.vmware.tvs.*`,
> no `Resource`/`ResourceCollection`, no JAX-WS."

Consequently we never receive the **platform-injected, CaSA-routed
`SuiteAPIClient`** that the aria-ops-core `UnlicensedAdapter` hands its subclasses.
Instead we build a **raw** REST client ourselves (`SuiteApiStitchClient`) that
targets `localhost/suite-api` with the maintenance-user token. The framework
deliberately does not even compile against a Suite API artifact
(`SynologyStitcher.java:47` "The framework does not compile against any Suite API
artifact; this bridge is the boundary").

This is exactly the split the brief hypothesised, and the live Oracle evidence
corroborates it: `OracleDatabaseAdapter` (an aria-ops-core `UnlicensedAdapter`
descendant, injected client) stitches FRESH from the prod CP; Synology (bare
`AdapterBase`, raw client) 403s from the CP. **Same door theory, opposite
outcomes, root cause = base class / client provenance.**

---

## Q3 — How big is the fix? **VERDICT: medium-to-large, and blocked on two still-open cleanroom questions.**

The delta depends on an answer we **cannot** get from our source (the framework
holds no Suite API artifact to inspect), so I flag it honestly:

- **If a raw SDK `SuiteAPIClient` also routes through CaSA by node role** (cleanroom
  request Q3, still open): the fix is **small-to-medium** — swap `AmbientCredential`
  + hand-rolled `token/acquire` for obtaining the SDK-injected/managed
  `SuiteAPIClient` (or a node-cert credential variant, cleanroom Q4) and read
  inventory through it. `SuiteApiStitchClient` becomes a thin wrapper over that
  client; `SynologyStitcher`/`SuiteApiDatastoreBridge` are unaffected (they already
  sit behind the `SuiteApiBridge` seam). The 3 explicit `vrops_*` credential fields
  could then be deprecated.
- **If only the `UnlicensedAdapter`-injected client routes through CaSA:** the fix
  is **large** — re-parent `VcfCfAdapter` (or Synology specifically) onto
  `UnlicensedAdapter`, reintroducing the `com.vmware.tvs.*` / aria-ops-core
  dependency the v2 migration deliberately removed, with describe/packaging/base-
  class blast radius across *every* factory Tier-2 adapter (synology, unifi,
  compliance, the vcommunity family). That is a framework-wide decision, not a
  synology patch.

**Do not implement either until the cleanroom answers land.** The `SuiteApiBridge`
seam (`ForeignResourceResolver.SuiteApiBridge`) is the right place to land the swap
whichever way it goes — the bridge already isolates "list foreign resources" from
the transport, so the identity-resolution and relationship-emit code do not move.

Blocked on: cleanroom Q1–Q4 (endpoint/port CaSA selection, node-cert keystore
path/alias, raw-vs-injected client routing, CaSA credential variant).

---

## Q4 — Write verb: additive vs full-set. **VERDICT: we use full-set `setRelationships` REPLACEMENT. Divergence from the uniformly-additive vendor corpus. Separate axis from the door.**

`SynologyAdapter.emitDatastoreCrossLink()` calls `rb.parentForeign(ds, lunKey)`
(`SynologyAdapter.java:1007`, `:1038`) and the relationship pass calls `rb.build()`
(`:964`). `parentForeign` files the child under the foreign parent entry
(`RelationshipBuilder.java:164-165`) and `build()` → `doBuild()` emits **full-set
replacement**:

```java
// RelationshipBuilder.doBuild(), line 291-292
if (!batch.isEmpty()) {
    rels.setRelationships(entry.parent, batch);   // REPLACEMENT, not add
}
```

An additive form exists (`buildDelta(false)` → `rels.addRelationships(...)`,
`:242`) but the Synology cross-link does **not** use it. So our foreign edge rides
`setRelationships(Datastore, {synologyChildren})`, whose clobber-safety depends on
the platform scoping the replacement per-reporting-adapter —
**proven on 9.0.2 only** (`knowledge/lessons/setrelationships-foreign-adapter-scoped.md`,
DEF-003 closed on that basis), **unverified on 9.1**.

The TVS corpus is uniformly **additive** (`addParent`/`addChild`/`addMultipleParents`
— `tvs-cross-mp-stitching.md` §TL;DR C, §PureStorage bytecode) and is therefore
clobber-safe *structurally*, with no dependency on any platform-scoping assumption.

**Recommendation (medium, independent of the door fix):** switch the foreign
cross-link to the additive verb — either `buildDelta(false)` for the foreign
entries, or (cleaner) a dedicated `parentForeignAdditive(...)` that routes foreign
parents to `addRelationships` while local edges keep `setRelationships`. This
retires the 9.1-unverified scoping risk that currently blocks DEF-002 (unifi) and
shadows DEF-003 (synology) on any 9.1 promotion, and aligns us with the vendor
idiom. Note: this is orthogonal to Q1–Q3 — worth doing even if the door is never
touched, because it removes a live-verification dependency from every future
cross-MP build.

---

## Q5 — Overall approach vs. the modern-TVS idiom

### 5a. Credential model — **DIVERGENCE (justified-but-symptomatic).**
Every modern TVS pak exposes **one target-system credential, no vROps field**
(`tvs-cross-mp-stitching.md` §A, per-pak matrix). We expose **three extra optional
Suite API credential fields** — `vrops_url` / `vrops_username` / `vrops_password`
(`SynologyAdapter.buildConfig():207-209`, describe.xml `required="false"`, build-21
review). These exist **only** to work around the CP-403, i.e. they are a symptom of
being on the wrong door (Q1/Q2). If the door fix lands, this surface should be
deprecated to match the vendor idiom. Until then it is a defensible workaround
(safe-degrades, loopback-misconfig WARN added in build 22) — but it is a credential
surface no vendor pak carries, and it exposes a Suite API password field to the
operator that the correct architecture would make unnecessary.

### 5b. Jar footprint — **NO DIVERGENCE (we're leaner; fine).**
Some TVS paks bundle `vim25` as unused build baggage (`tvs-cross-mp-stitching.md`
§B). We bundle **neither** vim25 nor a Suite API SDK jar — the framework talks REST
over `URLConnection` and does not compile against any Suite API artifact
(`SynologyStitcher.java:47`). Leaner than the vendors; not a defect. (Caveat: this
leanness is *also* what denies us the injected CaSA client — see Q2. The footprint
is fine; the missing injected client is the cost.)

### 5c. Identity resolution — **DIVERGENCE in mechanism (client-side bulk join vs. server-side property search); acceptable, but note the two sub-points.**
Vendor idiom: a **server-side** `SuiteAPIClient.ResourceQuery` property search
resolves the *one* foreign Datastore by its backing-NAA property
(`tvs-cross-mp-stitching.md` §D, KEY_TYPE.PROPERTY). Our idiom: pull **all** VMWARE
Datastores in one `GET /api/resources?adapterKind=VMWARE&resourceKind=Datastore&pageSize=10000`
and index/match **client-side** by `DataStrorePath`
(`SynologyStitcher.loadDatastores():86-127`, `SuiteApiDatastoreBridge:216-257`).
This is the documented factory bulk-read + client-lookup pattern
(`knowledge/lessons/synology-dsm-client-side-joins.md`) — reasonable, and it enables the
multi-vCenter fan-out the vendor single-value `loadAll` would collapse
(`SynologyStitcher.java:56-64`). Two things to keep on the radar, neither blocking:

1. **`pageSize=10000` is an unpaged cap.** On a fleet with >10k datastores the tail
   is silently dropped and those LUNs/exports would miss their cross-link with no
   log signal. Vendor server-side search has no such cap. Low risk at lab scale;
   note it for large-fleet correctness.
2. **Identity/uniqueness handling is CORRECT and worth preserving.** The foreign
   `ResourceKey` is rebuilt from the real per-identifier uniqueness flags read from
   the Suite API (`SuiteApiDatastoreBridge:246-247`
   `id.get("identifierType").get("isPartOfUniqueness").asBoolean()`), **not**
   hardcoded `true` — exactly what `knowledge/lessons/cross-mp-foreign-key-uniqueness-flags.md`
   requires (the synology .18–.21 over-marking bug that silently dropped edges).
   The Datastore is resolved by `DataStrorePath`, never a bare MOID
   (`SynologyStitcher.java:24-26`, `lunDataStorePath`/`nfsDataStorePath`) — the
   MOID-trap is avoided. This half of the idiom is right; do not disturb it during a
   door fix.

### 5d. Shared blast radius — unifi is on the identical pattern.
`unifi` uses the same `SuiteApiStitcher.create(this, …)` ambient path
(`UniFiAdapter.java:161-162`), the same `ForeignResourceResolver.SuiteApiBridge`
seam (`UniFiStitcher.java`), and the same `parentForeign` → full-set `build()`
verb (`UniFiAdapter.java:1059`). Therefore **every finding here applies verbatim to
unifi**: same user-credential door (its LLDP HostSystem cross-link would 403 on a
CP for the same reason), same full-set write verb (this *is* DEF-002, still open,
9.1-unverified and 9.0.2 never live-proven for unifi). A door fix or a write-verb
switch should be made in the shared framework so both adapters move together.

---

## Prioritized recommendations (for a future `sdk-adapter-author` briefing)

| # | Change | Size | Blocked on |
|---|---|---|---|
| R1 | **Write-verb switch:** route foreign cross-MP edges through the additive verb (`addRelationships` / a `parentForeignAdditive`) instead of full-set `setRelationships`. Retires the 9.1-unverified scoping dependency; matches the uniformly-additive vendor corpus; unblocks DEF-002 without a live 9.1 setRelationships proof. Do in the shared `RelationshipBuilder`/adapters so synology + unifi move together. | **Medium** | Nothing — do this first; independent of the door question. |
| R2 | **Door fix:** stop authenticating as the maintenance/`cloudproxy_<uuid>` user over `localhost/suite-api`; obtain inventory through the CaSA node-cert path (injected/managed `SuiteAPIClient` or a node-cert credential). Land it behind the existing `SuiteApiBridge` seam. | **Small→Large** — *small/med* if a raw SDK `SuiteAPIClient` routes through CaSA; *large* (re-parent onto `UnlicensedAdapter`, reintroduce aria-ops-core, framework-wide) if only the injected client does. | **Cleanroom Q1–Q4** (CaSA endpoint/port + node-role selection; node-cert keystore path/alias; raw-vs-injected routing; CaSA credential variant). Do not implement until answered. |
| R3 | **Credential/jar cleanup:** once R2 lands, deprecate the 3 optional `vrops_url/username/password` fields (no vendor pak carries them) to converge on the single-target-credential vendor idiom. | **Small** (describe + config) | Depends on R2 shipping. |
| R4 | **Paging hardening (5c-1):** page the `GET /api/resources` datastore pull or WARN on hitting the 10000 cap, so a large fleet does not silently drop foreign matches. | **Small** | Nothing. |

**Keep as-is (do not regress during the above):** `DataStrorePath`/NAA identity
resolution (no MOID), the real-`isPartOfUniqueness` propagation
(`SuiteApiDatastoreBridge:246-247`), the multi-vCenter fan-out, and the
degrade-not-crash posture (`stitcher==null` skip; `loadDatastores` swallow-to-empty;
cross-link failure never costs the cycle its internal topology).

## Open live questions this review is explicitly blocked on
- **9.1 `setRelationships` per-adapter scoping** — unverified (R1 removes the need to answer it).
- **Exact CaSA invocation mechanism / raw-vs-injected `SuiteAPIClient` routing** — cannot be determined from factory source (no Suite API artifact in-tree); gates R2's size.
