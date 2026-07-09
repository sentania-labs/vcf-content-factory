# SDK Adapter Review — unifi build 4

- **Adapter:** `content/sdk-adapters/unifi`
- **Build reviewed:** 4 (commit `0b8a915`, "fix(adapter): collect-path discovery
  for VCF Ops 9.0.2 (build 4)") — the **scoped delta** over the APPROVEd build 3
  (`9e0ee81`, reviewed in `context/reviews/unifi-build-3.md`).
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 2 NIT
- **Date:** 2026-06-10
- **Authority baseline:** build-3 review (`context/reviews/unifi-build-3.md`),
  framework SPI source (`vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/spi/VcfCfCollector.java`,
  `.../VcfCfAdapter.java`), spec/19 §1 step 1 (top-of-cycle rediscovery) + §2
  (new-resource registration identity contract), the compliance reference adapter
  (`content/sdk-adapters/compliance/src/.../ComplianceAdapter.java`), skill
  *Unreadable is NOT compliant* + *The bulk-read dynamic pattern*.

## Scope

Build 4 is a **Java-only behavioral change** to fix the build-3 live finding:
VCF Ops 9.0.2 never invokes `onDiscover()` for this adapter3-type collector, so
build 3 heartbeat GREEN but discovered zero resources. Build 4 refactors the
discoverer body into a shared `enumerateResources(Snapshot, ResourceSink)` fed by
**two** sinks — `getDiscoverer()` (`dr::addResource`, the `onDiscover()` path,
kept for forward-compat) and the collector's new `needsRediscovery()=true` +
`rediscover()` (`this::registerNewResource`, the collect-path discovery 9.0.2
actually runs). The diff stat is exactly: `UniFiAdapter.java` (the refactor),
`adapter.yaml` (build_number 3→4), `CHANGELOG.md` (+1.0.0.4 entry),
`REFERENCE.md` (build label 3→4). No other files.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `validate-sdk` clean | **CONFIRMED by direct run.** `validate-sdk content/sdk-adapters/unifi` → "OK: … is a valid Tier 2 SDK adapter project." 4 sources compile, only the benign `-source 11` system-modules warning. The new `ResourceSink` functional interface, the two method references (`dr::addResource`, `UniFiAdapter.this::registerNewResource`), and the `needsRediscovery`/`rediscover` overrides all compile. |
| `pak-compare` build-4 vs build-3 = 0 BLOCKING / 0 WARNING | **CONFIRMED — and stronger.** Freshly rebuilt build-4 pak (reproduced from the clean `0b8a915` tree) compared against `dist/vcfcf_sdk_unifi_controller.1.0.0.3.pak` → **0 BLOCKING / 0 WARNING / 0 INFO** ("No structural divergences found"). describe.xml, all 13 resource kinds, every identifier key, and all metric keys are byte-for-byte identical 3→4. This is a pure runtime change with **zero** descriptor surface. |
| describe.xml / resource kinds / identifiers / metric keys unchanged | **CONFIRMED.** `git diff 9e0ee81 0b8a915 --stat` lists no `describe.xml` and no `conf/` change; pak-compare 0/0/0 corroborates. |

Build reproduces from the clean tree (`build-sdk` → `/tmp/unifi-b4-review/…1.0.0.4.pak`,
94,934-byte adapters.zip). `build-sdk` touched `CHANGELOG.md`; **restored**
(`git checkout --`). unifi tree clean (`git status --short` empty, HEAD
`0b8a915`); factory tree clean (`dist/` gitignored, build output in `/tmp`).

---

## VERIFY item 1 — diff integrity 3→4: clean

Only the discovery refactor + version/docs. `pak-compare` 0/0/0 proves no
metric/identifier/describe drift. The refactor moved the enumeration body out of
the `getDiscoverer()` lambda into a private method **without altering a single
emitted `ResourceConfig`**: same kinds, same display-name helpers
(`deviceDisplayName`/`portDisplayName`/`radioDisplayName`), same identifier keys
and values, same emission order, same `isNull()`/optional-Protect guards. The
only token-level change inside the body is `dr.addResource(...)` → `sink.accept(...)`.
Verified by reading the full diff hunk line-by-line. ✔

## VERIFY item 2 — refactor correctness: single source, identity-preserving, correct API

- **Genuinely one source, no divergent logic.** Both sinks invoke the **same**
  `enumerateResources(s, sink)` body. There is no second enumeration anywhere —
  `getDiscoverer()` is now a 2-line lambda (`currentSnapshot()` +
  `enumerateResources(s, dr::addResource)`); `rediscover()` is the symmetric
  2-line body with `this::registerNewResource`. The two paths **cannot** drift
  by construction. ✔
- **ResourceSink seam does not change identity or ordering.** `ResourceSink` is a
  `@FunctionalInterface { void accept(ResourceConfig rc); }`. Each call site
  passes the identical `rcOf(kind, name, idKey, idValue)` it passed in build 3,
  in the identical loop order. `rcOf` builds `new ResourceKey(name, kind,
  ADAPTER_KIND)` + one **identifying** identifier (`new
  ResourceIdentifierConfig(idKey, idValue, true)`). Resource identity is the
  identifier, unchanged 3→4. ✔
- **`registerNewResource(ResourceConfig)` is the correct framework API.**
  Verified in `VcfCfAdapter.java:720` — public instance method that calls
  `collectResult.addNewResource(rc)` on the protected `collectResult` field, the
  spec/19 §2 collect-path registration path. The framework's `onCollect`
  (`VcfCfAdapter.java:536-549`) calls `collector.needsRediscovery(config)` then
  `collector.rediscover(config, httpClient, adapterInstance, this)` at the **top
  of the cycle, before** the per-resource collect loop (`:556`). The override's
  signature `rediscover(UniFiConfig, ManagedHttpClient, ResourceConfig,
  AdapterBase)` matches the SPI default (`VcfCfCollector.java:146`) exactly; the
  `needsRediscovery(UniFiConfig)` override matches `:119`. The method reference
  `UniFiAdapter.this::registerNewResource` from inside the anonymous collector
  resolves to the outer adapter's public method — compiles clean. ✔
- **Compliance comparison (author claim "structurally identical").** Compliance's
  `getDiscoverer()` (`ComplianceAdapter.java:247`) emits its single
  `ComplianceWorld` via `dr.addResource(worldResourceConfig())` with a
  `world_id`/`compliance_world` identifying identifier — the **same idiom** unifi
  uses for `UniFiWorld`/`unifi_world`. Structurally identical at the discoverer
  level. **But see VERIFY item 5** — compliance does NOT carry the collect-path
  rediscovery, so "structurally identical" is true of the *discoverer* and false
  of the *overall discovery strategy*. That divergence is the point of build 4,
  not a defect. ✔

## VERIFY item 3 — idempotency + performance: safe, no leak, no added API calls

- **Re-registering existing resources every cycle is idempotent platform-side.**
  `needsRediscovery` returns `true` unconditionally, so `rediscover` runs every
  cycle and re-emits the full resource set via `addNewResource`. The platform
  de-duplicates by the **identifying** identifier (spec/19 §2 identity contract;
  framework doc `VcfCfAdapter.java:701-703`). Safe **iff** every identifier is
  stable across cycles — verified below. ✔
- **All identifiers are stable; no timestamp/counter/sequence in any identifier.**
  Audited every `rcOf` call: `unifi_world` (constant); `site_name`=site `name`;
  gateway/switch/AP `mac` (hardware MAC); WAN `mac+"_wan1"`/`"_wan2"`; switch
  port `mac+"_"+port_idx`; radio `mac+"_"+radioCode` (band code e.g. `ng`/`na`);
  aggregate `siteName+"_wlan_aggregate"`; NVR `nvr_mac`; camera `camera_mac`.
  **None** contains a timestamp, uptime, counter, or churning value. The
  potentially-churning resources the brief flagged — switch ports and AP radios —
  key on `mac + port_idx` / `mac + radio band code`, both physically stable: a
  port index and a radio band do not change cycle-to-cycle on the same device. So
  re-registration de-dups to a no-op; **no resource leak / unbounded growth**.
  (Display *names* can drift — e.g. a renamed port — but identity is the
  identifier, not the name, so a rename updates the existing resource rather than
  spawning a duplicate.) ✔
- **No added API calls; rides the existing per-cycle snapshot.** `rediscover`
  calls `currentSnapshot()`, which is the same `synchronized` 60s-cached accessor
  (`MIN_REFRESH_INTERVAL_MS = 60_000`) the collect loop uses. Because `rediscover`
  runs at the top of the cycle and builds/caches the snapshot, the subsequent
  per-resource `collect()` calls in the same cycle reuse that cached snapshot —
  the rediscovery adds **zero** UniFi API round trips beyond the one snapshot the
  cycle already needed. Matches skill *The bulk-read dynamic pattern*. ✔

## VERIFY item 4 — first-cycle population: correct, with the standard one-cycle latency

`onCollect` (`VcfCfAdapter.java:536-556`) runs rediscovery **before** the
per-resource loop. On a freshly-configured instance the `resources` collection
passed into the *first* `onCollect` is empty, so:

- **Cycle 1:** `rediscover` enumerates the snapshot and `registerNewResource`s
  every resource into the cycle's embedded `DiscoveryResult` → the resources
  **appear in VCF Ops from cycle 1**. The per-resource loop iterates the
  (still-empty) inbound `resources` set, so **no metrics are emitted yet**.
- **Cycle 2+:** the now-known resources are passed into `onCollect`, the loop
  collects them, metrics flow.

This is the framework's standard collect-path-discovery latency (discover on
cycle N, collect on cycle N+1) and is **correct** — the fresh instance is no
longer stuck at 0 resources forever (the build-3 bug); it self-populates without
ever needing `onDiscover()`. The rediscovery failure path is non-fatal
(`VcfCfAdapter.java:544-548` WARNs and continues), and an unreadable `/self/sites`
still throws out of `currentSnapshot()` inside `rediscover` → caught as
"rediscovery failed (non-fatal)" WARN → no resources registered that cycle, retry
next cycle. No unreadable→silent-pass path is introduced (skill *Unreadable is NOT
compliant* preserved: a failed enumeration registers nothing, it never fabricates
a resource or a sentinel). ✔ See NIT-1 on the CHANGELOG's "populates on its first
collect" wording.

## VERIFY item 5 — compliance reconciliation (for task #19, the fresh-instance audit)

**Both author counter-claims confirmed in source:**

1. **Compliance does NOT override `needsRediscovery`.** Grep of
   `ComplianceAdapter.java` for `needsRediscovery`/`rediscover`/
   `registerNewResource` returns **only** the `getDiscoverer` block (`:243-251`);
   its `getCollector()` (`:267`) overrides `collect` and `mapCollectException`
   **only** — it inherits the SPI defaults `needsRediscovery()=false` and
   `rediscover()=no-op`. Confirmed. ✔
2. **The discoverers are structurally identical** (single synthetic world
   resource emitted via `dr.addResource(worldResourceConfig())` with an
   identifying `world_id`). Confirmed. ✔

**HOW compliance's resources come into being on a fresh instance — stated plainly
for task #19:** Compliance's `ComplianceWorld` resource is created **exclusively**
via `getDiscoverer()` → `onDiscover()`. There is **no** collect-path genesis: no
`needsRediscovery`/`rediscover` override, no `registerNewResource` call anywhere
in compliance, and **no pre-seeded resource** in a `template.json` (compliance has
none — only `describe.xml`). My earlier build-43/46/48 compliance reviews
described the world resource as appearing "via MetricData emission"; that was
**imprecise and is corrected here**: `MetricData` only *populates metrics onto* an
already-existing `ComplianceWorld` resource (`collectWorld(rc, out)` runs against
the `rc` the platform hands the collector) — it does **not** create the resource.
The resource itself is born only from `onDiscover()`'s `dr.addResource`.

**Direct consequence for task #19:** if the build-3 finding generalizes — i.e.
VCF Ops 9.0.2 does not invoke `onDiscover()` for adapter3-type SDK collectors as a
class, not just for unifi — then **compliance has the identical latent defect**:
a freshly-configured compliance instance on 9.0.2 would heartbeat GREEN and sit at
**zero resources** (no `ComplianceWorld`, therefore no fleet rollups and no
stitched per-host compliance), exactly the build-3 unifi symptom. Compliance has
no collect-path discovery fallback to save it. Whether `onDiscover()` actually
fires for compliance on 9.0.2 is a **live-instance question this static review
cannot answer** — it depends on the platform's discovery-task behavior, which the
unifi build-3 live finding showed is version/adapter-type-dependent. Task #19
should treat "does `onDiscover()` fire for compliance on the target build" as an
open, must-verify item, and should consider whether compliance ought to adopt the
same `needsRediscovery()=true` + `rediscover()` collect-path fallback build 4
introduces. I am stating this as the reconciled fact the task asked me to nail
down; I am **not** prescribing the compliance change (that is the author's call
via the orchestrator).

---

## Findings

### NIT

- **[CHANGELOG.md 1.0.0.4 + UniFiAdapter.java rediscover javadoc — "populates on
  its first collect"]** — Mild precision nit. The new resources *appear* in VCF
  Ops on the first collect cycle (registered into that cycle's embedded
  DiscoveryResult), but their **metrics** arrive on the **second** cycle, because
  the per-resource collect loop iterates the inbound `resources` set, which is
  empty on the first cycle (`VcfCfAdapter.java:556`). "Populates on its first
  collect" is true for resource *visibility*, slightly optimistic for *data*. Not
  a defect — this is the framework's standard one-cycle discover→collect latency.
  → **Fix (optional):** reword to "resources appear on the first collect; metrics
  follow on the next cycle" so a fresh-instance acceptance test (and task #19)
  doesn't flag an empty-metrics first cycle as a regression.

- **[UniFiAdapter.java getCollector — `needsRediscovery()` is unconditionally
  true]** — Every cycle re-enumerates and re-registers the full resource set. This
  is **safe** (idempotent, stable identifiers, snapshot reused — proven above) and
  is the pragmatic fix for the 9.0.2 gap, but it does run the enumeration walk
  each cycle in perpetuity even once the inventory is stable. The cost is bounded
  (one snapshot already needed + an in-memory walk + de-duped `addNewResource`
  calls), so this does not gate. → **Fix (optional, future):** if cycle cost ever
  matters, gate `needsRediscovery` on a cheap change-signal (e.g. site/device
  count delta vs last cycle) rather than unconditional `true`. Acceptable as-is;
  flagged only so it's a conscious choice, not an oversight.

## If shipped as-is

An operator installs build 4 on VCF Ops 9.0.2 and, unlike build 3, the
freshly-configured UniFi instance **self-populates**: on its first collect cycle
the collect-path `rediscover` enumerates the snapshot and registers the full
sites→gateways/switches/APs/ports/radios/NVR/cameras tree (resources visible from
that cycle), and from the next cycle every resource collects v1-identical metrics
— no dependence on an `onDiscover()` that 9.0.2 never sends. Re-running discovery
every cycle is harmless: stable MAC/port-idx/band identifiers de-dup
platform-side, no duplicate resources, no resource leak, and no extra UniFi API
calls (the cached per-cycle snapshot is reused). All build-3 safety properties are
preserved (the resource-emission body is byte-identical; pak descriptor unchanged
0/0/0). The one operator-facing nuance is the standard one-cycle latency between a
resource appearing and its first metrics (NIT-1). **Cross-adapter flag for task
#19:** compliance creates its `ComplianceWorld` resource *only* via `onDiscover()`
and has no collect-path fallback — if the 9.0.2 `onDiscover()` gap is
adapter-type-wide, a fresh compliance instance would exhibit the same zero-resource
symptom build 4 just fixed for unifi.

## Verification artifacts

- `validate-sdk content/sdk-adapters/unifi` → OK, 4 sources compiled, 1 benign
  `-source 11` warning (direct run).
- `build-sdk` reproduced build-4 pak from clean `0b8a915` tree →
  `/tmp/unifi-b4-review/vcfcf_sdk_unifi_controller.1.0.0.4.pak` (94,934-byte
  adapters.zip).
- `pak-compare` build-4 vs `dist/vcfcf_sdk_unifi_controller.1.0.0.3.pak` →
  **0 BLOCKING / 0 WARNING / 0 INFO** ("No structural divergences found").
- Framework SPI: `needsRediscovery(C)` default false / `rediscover(C,
  ManagedHttpClient, ResourceConfig, AdapterBase)` default no-op
  (`VcfCfCollector.java:119,146`); `onCollect` runs rediscovery at top-of-cycle
  before per-resource loop (`VcfCfAdapter.java:536-556`); `registerNewResource(rc)`
  → `collectResult.addNewResource(rc)` (`VcfCfAdapter.java:720-725`).
- Compliance genesis: `ComplianceWorld` created only via
  `getDiscoverer()`→`dr.addResource(worldResourceConfig())`
  (`ComplianceAdapter.java:247-260`); **no** `needsRediscovery`/`rediscover`/
  `registerNewResource`; no `template.json`. `MetricData` populates, does not
  create.
- Identifier stability audit: all `rcOf` id values constant or hardware-stable
  (MAC / port_idx / radio band / site name); no timestamp/counter.
- `build-sdk` touched CHANGELOG.md; **restored** (`git checkout --`). unifi tree
  clean (HEAD `0b8a915`); factory tree clean; `/tmp` build output only.

## Report
`context/reviews/unifi-build-4.md`
