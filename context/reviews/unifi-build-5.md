# SDK Adapter Review — unifi build 5

- **Adapter:** `content/sdk-adapters/unifi`
- **Build reviewed:** 5 (commit `5ab0f13`) vs build 4 (`ed6d316`)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT
- **Date:** 2026-06-10
- **Context:** `context/investigations/unifi_401_and_relationship_persistence_2026_06_10.md`;
  framework §22 (`context/framework_v2_migration.md`); framework `main` d59785a.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `validate-sdk` clean | **Confirmed by direct run.** 4 sources compiled, 1 benign `-source 11` warning. The framework `ResourceSink`, the `discoverOnCollect()`/`enumerateResources(ResourceSink)` overrides all resolve against the framework jar — the adapter's private `ResourceSink` is deleted (uses the framework's). |
| `pak-compare` build-5 vs build-4 = 0/0/0 | **Confirmed by direct run.** `pak-compare 5 4` → "No structural divergences found. 0 BLOCKING, 0 WARNING, 0 INFO." describe.xml, all resource kinds, identifiers, and metric keys byte-identical 4→5 — consistent with a pure framework-jar-pickup + discovery-refactor change with zero descriptor surface. |
| Diff scope = framework jar pickup + §22 refactor + version/docs | **Confirmed.** `git diff 4→5` touches `UniFiAdapter.java`, `adapter.yaml` (4→5), `CHANGELOG.md` only. No `describe.xml`, no `conf/`, no other source. |
| `rcOf` unchanged → keys byte-identical (no 128-resource duplication) | **Confirmed.** `rcOf` is not in the diff hunk; body is unchanged `new ResourceKey(name, kind, ADAPTER_KIND)` + one identifying identifier. Same kinds, same id keys/values, same emission order as build 4. The 128 devel resources re-register to the same keys → de-dup, no duplicates. |
| Bundled framework jar carries the d59785a fixes | **Confirmed.** SHA-256 identical to the compliance-50 jar, which I bytecode-disassembled directly (see below). |
| Trees clean after build | **Confirmed.** unifi clone, compliance clone, factory tree all `git status` clean; sidecars in the gitignored build dir. |

## Author-requested verification 1 — no client-side CSRF cache (line-by-line, `UniFiApiClient.java`)

**CONFIRMED — there is no CSRF cache, and there cannot be one given the source.**

- **No CSRF field exists.** `UniFiApiClient` has exactly two instance fields:
  `private final ManagedHttpClient http` and `private final Logger log`
  (`:33-34`). No `csrf`, no `xCsrfToken`, no cached token of any kind. The only
  session artifact (the `TOKEN`/`unifises` cookie) is returned out of `login()`
  (`:91`) into the framework `SessionCookieAuth` — it is **not** stored in this
  client.
- **Data path is GET-only.** All four data methods — `listSites` (`:43`),
  `statDevice` (`:47`), `statHealth` (`:51`), `protectBootstrap` (`:57`, the
  Protect endpoint) — call the single private `get(path)` (`:63`), which does
  `http.get(...)` and nothing else. No header manipulation, no CSRF read, no
  CSRF replay on any read.
- **`login()` is the only POST** (`:78`), and it reads **only** `set-cookie`
  (`:85-86` via `extractCookie`, which filters `set-cookie` at `:95`). It does
  **not** read or store the controller's `x-csrf-token` /
  `x-updated-csrf-token` response headers (the investigation A1 confirmed the
  controller returns them; this client never touches them). `resp.headers()` is
  referenced **only** inside `extractCookie` for `set-cookie` — grep/read of the
  whole file finds no `x-csrf` access anywhere.
- **Consequence for 401 recovery:** because the only session artifact is the
  cookie and the framework now invalidates+replays on 401/403
  (`ManagedHttpClient` / `SessionCookieAuth`, verified below), a framework
  re-login refreshes the *only* thing the client depends on. There is no stale
  CSRF token to replay, so no "fixed cookie + stale CSRF" failure mode is
  possible. The author's claim that the GET-only data path needs **nothing**
  adapter-side is correct. **Authority:** investigation Part A; the no-CSRF
  read path is the load-bearing premise and it holds in source.
- **Both endpoint families are covered by one auth.** `buildHttpClient`
  (`:187-200`) builds a single `ManagedHttpClient` with `SessionCookieAuth`
  attached (`:199`) and hands it to the one `UniFiApiClient` (`:148`). Both
  `/proxy/network/...` and `/proxy/protect/...` go through that one `get()` →
  one `http` → one `SessionCookieAuth`, so the framework 401-retry covers
  network **and** Protect, exactly as claimed.

## Author-requested verification 2 — `currentSnapshot()` on a null snapshot cannot crash describe/install or silently enumerate empty

**CONFIRMED safe. No NPE, no silent-empty enumeration — failure is loud at every call site.**

Traced the §22 framework wiring (`VcfCfAdapter.java`) for every path that can
reach `enumerateResources` → `currentSnapshot()`:

1. **`currentSnapshot()` never returns null and never NPEs on a null field.**
   `UniFiAdapter.java:462-470`: when `this.snapshot == null` (fresh instance,
   first ever call) it **builds** a fresh snapshot via `Snapshot.build(api,
   this)` and stores it; it returns null only if `Snapshot.build` could return
   null (it does not — it either builds or throws). On a REST/auth failure
   `Snapshot.build` **throws a checked Exception**, which propagates out of
   `currentSnapshot()` and out of `enumerateResources`. There is no code path
   that returns an empty snapshot or a null.

2. **Describe/install never calls `enumerateResources` at all.** Framework
   javadoc + contract (`VcfCfAdapter.java:447-451`, "Bare-instantiation
   safety"): *"The framework never calls `enumerateResources` during the
   controller-side describe phase (where the adapter is instantiated bare with
   no injected state)."* So the bare-instance describe/install path cannot touch
   `currentSnapshot()` → the NPE-kills-describe scenario in the brief **cannot
   occur**. (And UniFi *does* override `enumerateResources`, so the framework's
   default-throw `UnsupportedOperationException` at `:466-475` — which fires only
   if an adapter sets `discoverOnCollect()=true` without overriding — never
   fires here.)

3. **`onDiscover()` path (default `getDiscoverer()`):** `getDiscoverer()` default
   (`:333-337`) returns a lambda calling `enumerateResources(dr::addResource)`.
   `onDiscover` (`:623-641`) wraps the call in try/catch: an exception out of
   `currentSnapshot()` → `dr.setErrorMsg(msg)` + `logError("onDiscover:
   failed…")` → returns a DiscoveryResult **carrying an error**, not a silently
   empty success. Loud, not silent-empty.

4. **Collect-path discovery (`discoverOnCollect()=true`):** `onCollect`
   (`:696-708`) calls `enumerateResources(this::registerNewResource)` in
   try/catch: `InterruptedException` → abort cycle; any other Exception →
   `logWarn("collect-path discovery … failed (non-fatal)")` and continue with
   the existing resource set. Again loud; a failed enumeration registers
   **nothing** rather than fabricating an empty set. **Authority:** skill
   *Unreadable is NOT compliant* (a failed API call must never silently register
   zero resources) — preserved.

**Net:** a fresh instance with no snapshot either (a) builds one and enumerates
normally, or (b) fails to build it and surfaces a loud error/WARN with zero
resources registered that attempt, retrying next cycle. No NPE escapes to kill
describe/install; no silent empty enumeration. The brief's BLOCKING scenario
does not exist.

## §22 adoption — correctness of the refactor

- **Single enumeration body, framework-plumbed.** Build 4's hand-rolled
  `needsRediscovery()=true` / `rediscover()` pair is **deleted** from the
  collector (replaced by a comment) and `discoverOnCollect()` now returns `true`
  (`:284`) over a single `@Override protected void
  enumerateResources(ResourceSink sink)` (`:309`). The private `ResourceSink`
  interface is deleted; the adapter now imports the framework
  `com.vcfcf.adapter.spi.ResourceSink`. `getDiscoverer()` override is deleted —
  the framework default wires the same body to the `onDiscover()` path. This is
  the exact §22 recipe; behaviour is preserved and the two paths cannot drift by
  construction (one body, two framework callers).
- **Identity preserved.** `enumerateResources` now pulls the snapshot internally
  via `currentSnapshot()` (the same 60s-cached per-cycle accessor the collect
  loop uses — no added UniFi API calls) instead of receiving it as a parameter;
  every `rcOf(...)` call is otherwise unchanged. pak-compare 0/0/0 corroborates
  zero descriptor/identifier/metric drift.
- **Idempotent re-registration.** `discoverOnCollect()=true` re-enumerates every
  cycle; all identifiers are stable (constant `unifi_world`; site `name`;
  hardware `mac`; `mac+port_idx`; `mac+radio band`; `siteName+"_wlan_aggregate"`;
  `nvr_mac`/`camera_mac` — no timestamp/counter), so the platform de-dups by
  identifying identifier. No duplicate resources, no leak (carried over from the
  build-4 audit, identifiers unchanged this build).

## Framework jar — bytecode-verified (verified via the byte-identical compliance-50 copy)

The bundled `vcfcf-adapter-base.jar` in the unifi-5 pak has SHA-256
`0e873aec…b0a8f15`, **identical** to the jar in the compliance-50 pak, which I
disassembled directly with `javap -p -c`:

- **`RelationshipBuilder.resource(...)`** constructs `new ResourceKey(name,
  resourceKind, adapterKind)` — the **CORRECTED** arg order (bytecode: `aload_2`
  name, `aload_1` kind, `adapterKind` field). The investigation's prime-suspect
  ResourceKey swap that silently dropped UniFi's relationship edges at
  persistence is **fixed** in the shipped jar. UniFi's `buildRelationships` is
  unchanged this build (not in the diff) — the persistence fix is entirely the
  framework jar, as the author claims.
- **`SessionCookieAuth` / `ManagedHttpClient`** carry the single-retry-on-401/403
  (`AuthStrategy.invalidateAuth()` → replay once, no loop) — this is the 401
  storm recovery the investigation Part A required, delivered framework-side with
  no adapter change.
- **`sendWithRoundRobin`** no longer sets the JDK-forbidden `Host` header (only a
  "Do NOT set a Host header" comment remains; no `"Host"` header is set).

## Findings

### NIT

- **[UniFiAdapter.java class javadoc / CHANGELOG — "populates on its first
  collect"]** — carried over from build 4 (`unifi-build-4.md` NIT-1) and still
  present. Resources *appear* in VCF Ops on the first collect cycle (registered
  into that cycle's embedded DiscoveryResult), but their **metrics** arrive on
  the **second** cycle (the per-resource collect loop iterates the inbound
  `resources` set, empty on cycle 1). This is the framework's standard
  one-cycle discover→collect latency, not a defect. → **Fix (optional):** reword
  to "resources appear on the first collect; metrics follow on the next cycle"
  so a fresh-instance acceptance test doesn't flag an empty-metrics first cycle
  as a regression. Non-blocking.

## Hunts cleared (verified safe)

- **Unreadable-is-compliant:** PASS. A failed snapshot build registers nothing
  (loud WARN/error), never an empty/fabricated resource set; the per-resource
  collect path is unchanged this build.
- **Crash-the-cycle:** PASS. `currentSnapshot()` cannot NPE on a null field
  (it builds); describe/install never calls it; both discovery call sites catch
  and log. No throw aborts describe/install.
- **Stitch corruption:** PASS — and **improved**. The framework
  `RelationshipBuilder` ResourceKey order is now corrected (bytecode-verified),
  which is the fix for UniFi's zero-edge-persistence; the adapter's
  `buildRelationships` and `rcOf` are byte-identical to build 4.
- **401 recovery:** PASS. Framework `SessionCookieAuth` 401/403 invalidate+retry
  delivers the recovery; no adapter change needed (no CSRF cache to invalidate —
  verified above).
- **Redaction (TOKEN/unifises/csrf/password):** PASS. `redact()` masks
  TOKEN/unifises/`"password":`/`password=` (`:114-121`), unchanged; login
  failure logs status only (`:82`); "UniFi session acquired" logs no value
  (`:90`). All build-5 added lines mentioning TOKEN/CSRF/password are
  documentation prose, not secret-emitting code. `rules/no-secrets-on-disk.md`
  clean.
- **Build hygiene:** PASS. `build_number` 4→5, matching CHANGELOG entry, minimal
  diff (refactor + jar pickup), no drive-by.

## If shipped as-is

An operator installs build 5 on VCF Ops 9.0.2. Discovery is unchanged in
behaviour from build 4 (framework-plumbed §22 instead of hand-rolled, identical
resource set, no duplication of the 128 devel resources). Two real fixes ride
entirely in the refreshed framework jar with no adapter-code change: (1) an
expired `TOKEN` cookie now triggers a single re-login-and-retry instead of
401-storming the instance to ERROR forever — and because UniFi caches no CSRF
token (verified line-by-line), the re-login refreshes the only session artifact
and recovers cleanly; (2) the relationship edges UniFi was already emitting
correctly now persist, because the framework `RelationshipBuilder` ResourceKey
arg-order bug (which silently dropped every edge at persistence) is fixed
(bytecode-verified). A fresh instance with no snapshot fails loudly (WARN/error,
zero resources that attempt, retry next cycle) rather than NPE-ing describe or
silently enumerating empty. The one operator-facing nuance remains the standard
one-cycle latency between a resource appearing and its first metrics (NIT).
Relationship persistence is the live-instance proof the investigation flagged as
a TOOLSET GAP — `qa-tester`/the orchestrator should confirm edges actually land
in the Suite API post-install; this static gate confirms the fix is in the
shipped bytecode.

## Verification artifacts

- `validate-sdk content/sdk-adapters/unifi` → OK, 4 sources compiled (direct).
- `build-sdk` → `dist/vcfcf_sdk_unifi_controller.1.0.0.5.pak` (adapters.zip
  95,869 B) from the clean `5ab0f13` tree (direct).
- `pak-compare 5 vs 4` → 0 BLOCKING / 0 WARNING / 0 INFO (direct).
- `UniFiApiClient.java` read in full: two fields (`http`, `log`), GET-only data
  path, `login()` reads `set-cookie` only, no `x-csrf` access anywhere.
- §22 wiring read in `VcfCfAdapter.java`: `enumerateResources` default-throw
  (`:466`), bare-instantiation-safety contract (`:447-451`), `getDiscoverer`
  default → `enumerateResources(dr::addResource)` (`:333`), `onDiscover`
  catch→setErrorMsg (`:634-638`), `onCollect` discoverOnCollect catch→WARN
  (`:696-708`). `currentSnapshot()` builds on null, throws on failure
  (`UniFiAdapter.java:462-470`).
- Framework jar bytecode (direct `javap` on the byte-identical compliance-50
  copy, SHA `0e873aec…b0a8f15`): `RelationshipBuilder.resource` →
  `new ResourceKey(name, kind, adapterKind)`; Host header not set;
  SessionCookieAuth 401-retry present.
- unifi tree clean (HEAD `5ab0f13`); compliance + factory trees clean; sidecars
  gitignored.
