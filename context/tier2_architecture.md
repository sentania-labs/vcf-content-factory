# Tier 2 (SDK) Management Pack Architecture

Living reference for VCF Content Factory's Tier 2 management pack
pipeline. Tier 2 uses **native Java SDK adapters** for cases MPB (Tier 1)
fundamentally can't handle.

For "is this case Tier 1 or Tier 2?" see
[`tier_decision_framework.md`](tier_decision_framework.md). For the
underlying SDK contract and design rationale, see
[`cleanroom-spec/spec/17-vcfcf-framework-design-guidance.md`](cleanroom-spec/spec/17-vcfcf-framework-design-guidance.md)
(framework design) and
[`cleanroom-spec/spec/15-tier2-handoff-for-vcf-cf.md`](cleanroom-spec/spec/15-tier2-handoff-for-vcf-cf.md)
(adapter authoring view). For the behavioral contract the framework
implements, see
[`cleanroom-spec/spec/19-adapterbase-behavioral-contract.md`](cleanroom-spec/spec/19-adapterbase-behavioral-contract.md).

## Three-layer stack (v2)

```
Layer 3: Per-adapter code (Claude-generated, ~200–600 lines)
         class SynologyAdapter extends VcfCfAdapter<SynologyConfig>
─────────────────────────────────────────────────────────────────────
Layer 2: vcfcf-adapter-base.jar (THIS PROJECT'S FRAMEWORK, v2)
         abstract class VcfCfAdapter<C> extends AdapterBase
─────────────────────────────────────────────────────────────────────
Layer 1: vrops-adapters-sdk.jar (Broadcom, on appliance classpath)
         AdapterBase / AdapterInterface3
```

**v2 change (2026-06-09):** Layer 2 previously extended
`UnlicensedAdapter` from `aria-ops-core.jar` (a BlueMedora/TVS
partner-channel artifact). The framework now extends `AdapterBase`
**directly**, eliminating every `com.vmware.tvs.*` dependency.
`aria-ops-core` is no longer required at compile time or at runtime.
The orchestration (onCollect/onTest/onDiscover/onConfigure/stop hooks)
is implemented from the clean-room behavioral contract in spec/19.

**Rule:** never patch Layer 1 or Layer 2 platform jars. All VCF-CF code
lives at Layer 2 (framework) or Layer 3 (per-adapter).

## Repo layout

```
content/sdk-adapters/<name>/        # Layer 3: Tier 2 adapter projects
    adapter.yaml                    # name, version, adapter_kind, tier:2, deps
    src/com/vcfcf/adapters/<name>/  # Java source (Claude-generated)
    describe.xml                    # hand-authored, or via framework DSL
    resources/resources.properties
    lib/                            # optional: vendor JARs (JDBC driver, etc.)

vcfops_managementpacks/
    adapter_framework/src/          # Layer 2 framework Java source
    adapter_runtime/                # pre-compiled JARs:
        vcfcf-adapter-base.jar      #   - Layer 2 (we build, commit, ship)
        vrops-adapters-sdk-*.jar    #   - Layer 1 (Broadcom, frozen)
        aria-ops-core-*.jar         #   - KEPT for reference / v1 compile tests
                                    #     NOT required for v2 framework build
        alive_common.jar            #   - not needed by v2 framework
        alive_platform.jar          #   - not needed by v2 framework
        mpb_adapter3.jar            #   - Tier 1 runtime (unrelated)
    sdk_builder.py                  # javac/jar invocation, pak assembly
    sdk_project.py                  # adapter.yaml loader, project model
```

The Tier 1 directories (`content/managementpacks/`, MPB JAR) are
unchanged. Tier 1 and Tier 2 coexist.

## Build approach: Python + `javac`, no Maven

- The only external dependency Tier 2 adds is a **JDK on PATH**
  (`javac`, `jar`). Tier 1 stays zero-dependency.
- Python tooling owns build orchestration: detect JDK, build
  classpath, invoke `javac`, package adapter JAR, assemble pak.
- No `pom.xml`, no Gradle wrapper. Compile classpath is
  `vcfcf-adapter-base.jar` + `vrops-adapters-sdk-2.2.jar` + `aria-ops-core-*.jar`
  (kept for v1 adapter compilation until all v1 adapters migrate) + any
  per-project `lib/*.jar`. Only `vcfcf-adapter-base.jar` and conditionally
  `aria-ops-core` (v1 only) are bundled into the pak's `lib/`;
  `vrops-adapters-sdk` is never bundled (resolves from appliance classpath).
- The framework JAR (`vcfcf-adapter-base.jar`) is built **once by us**
  and committed; users never compile it.
- Build command: `python3 -m vcfops_managementpacks build-sdk <project-dir>`.
- Auto-detect: bare `build <arg>` routes to Tier 1 if `arg` ends in
  `.yaml`, Tier 2 if it's a directory with `adapter.yaml`.

## Framework scope (v2)

All components compile against `vrops-adapters-sdk-2.2.jar` only.

| Component | Package | What it does |
|---|---|---|
| `VcfCfAdapter<C>` | `com.vcfcf.adapter` | Abstract base. Extends AdapterBase directly. Typed config binding, full lifecycle orchestration (onCollect/onTest/onDiscover/onConfigure), MetricDataCache, cancellation, platform SSL. |
| `VcfCfTester<C>` | `com.vcfcf.adapter.spi` | SPI: adapter-supplied connectivity test. Throws on failure; message is surfaced via TestParam (§5). |
| `VcfCfDiscoverer<C>` | `com.vcfcf.adapter.spi` | SPI: adapter-supplied resource enumeration. Populates DiscoveryResult directly (§6). |
| `VcfCfCollector<C>` | `com.vcfcf.adapter.spi` | SPI: adapter-supplied per-resource data gather. Provides collect/collectEvents/collectRelationships/rediscover/mapCollectException. |
| `HttpClientBuilder` | `com.vcfcf.adapter.http` | Fluent builder over stdlib HTTP client. Default: JVM trust store. `platformSsl(this)` for platform trust; `allowInsecure(true)` as explicit lab opt-out. |
| `ManagedHttpClient` | `com.vcfcf.adapter.http` | HTTP wrapper with base URL, auth, retry, DNS round-robin. |
| `AuthStrategy` + `BasicAuth`, `BearerAuth`, `SessionCookieAuth` | `com.vcfcf.adapter.auth` | Auth plug-in SPI and implementations. |
| `RetryPolicy` | `com.vcfcf.adapter.retry` | Exponential backoff + jitter. Default 3 attempts, 500ms base, 200ms jitter. |
| `RelationshipBuilder` | `com.vcfcf.adapter.stitch` | Fluent builder producing a `Relationships` object. Full-set semantics (`setRelationships`) by default; delta via `buildDelta()`. No aria-ops-core dependency. |
| `ForeignResourceResolver` | `com.vcfcf.adapter.stitch` | Cross-MP resource lookup through a `SuiteApiBridge` functional interface. No TVS/aria-ops-core compile dependency. Optional — only for adapters that do cross-MP stitching. |
| `MetricPusher` | `com.vcfcf.adapter.metric` | Fluent helper for pushing metrics and properties. Uses `new MetricKey(true, key)` for properties (bug fix vs v1). |
| `DescribeBuilder` | `com.vcfcf.adapter.describe` | describe.xml XML generator. No SDK dependency. |
| `SimpleJson` | `com.vcfcf.adapter.json` | Zero-dep recursive-descent JSON parser. |
| `AmbientCredential` | `com.vcfcf.adapter.stitch` | Reads `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`; decrypts via SDK `Crypt.getDefaultCrypt().decrypt()` — the only FIPS-safe path under `-Dorg.bouncycastle.fips.approved_only=true` (9.1+). Path resolution order: (1) system property `vcfcf.suiteapi.credential.path` if set; (2) hard-wired default `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`. **`CommonConstants.VCOPS` is NOT used** — it is a product display-name string (`"VCF Ops"`), not a filesystem path. See `lessons/sdk-constants-are-display-names.md`. Never hand-roll the cipher. |
| `SuiteApiStitchClient` | `com.vcfcf.adapter.stitch` | Framework REST transport for Suite API stitching. Token acquire/release lifecycle per push call. Credential resolution: explicit adapter-config fields > ambient `maintenanceuser.properties` > fail with actionable message. Platform SSL via `VcfCfAdapter.getPlatformSslContext()`. `java.net.http` / source-11 baseline. |
| `SuiteApiStitcher` | `com.vcfcf.adapter.stitch` | Thin facade adapter authors hold as a field. Factory methods: `SuiteApiStitcher.create(adapter, logger)` (ambient) and `SuiteApiStitcher.createExplicit(adapter, logger, host, user, pass)` (remote-collector fallback). No transport code required in the adapter. |

## Pak format — hard-won lessons (2026-05-19)

These were discovered empirically by installing SDK paks on VCF Ops
9.0.2 and diagnosing failures via appliance logs.

| Aspect | Requirement | What happens if wrong |
|---|---|---|
| `manifest.txt` (outer + inner) | JSON format, both identical | Staging hangs or install fails silently |
| `manifest.txt` `adapters:` field | `["adapters.zip"]` — **required** | STAGE phase can't locate the adapter archive; install hangs |
| `manifest.txt` `pak_icon:` | `"default.svg"` — must be a valid SVG, not 0-byte | Validate phase rejects: "incorrect format--exiting" |
| Inner `adapters.zip` | Must duplicate `manifest.txt`, `eula.txt`, `default.svg` from outer pak | Validate phase rejects missing files |
| `eula.txt` | Non-empty (MIT license text) | UI shows blank EULA page |
| ZIP directory entries | Explicit zero-byte directory entries required for every subdirectory in `adapters.zip` | `SyncAdapters.extractFiles()` throws `NoSuchFileException` — parent dirs don't exist |
| `vrops-adapters-sdk.jar` | **Do NOT bundle in `<adapter>/lib/`** — resolves from the appliance shared classpath at runtime. Keep on `javac` compile classpath only. Historical note: this row previously stated "must bundle" citing a 14ms `installSolution` failure. That failure was **misattributed** — it was the missing-directory-entries structural bug of the same era (a true classpath problem surfaces as `NoClassDefFoundError` during collection, not a 14ms install rejection). Disproven by C2 install test: build 42, devel + prod, 2026-06-09 — install succeeded, full collection cycle ran, zero classloading errors in adapter logs. See `context/investigations/c2_no_sdk_jar_install_test.md`. | No failure — the appliance ships the SDK jar on its own classpath; the adapter resolves it cleanly at runtime. |
| `aria-ops-core.jar` | **v1 adapters: must bundle in `<adapter>/lib/`** — not on the appliance shared classpath. **v2 adapters: do NOT bundle** — framework v2 eliminated all `com.vmware.tvs.*` dependencies. Auto-detected at build time by scanning compiled class bytecode for `com/vmware/tvs` references (`sdk_builder._needs_aria_ops_core()`). This row becomes fully obsolete once all adapters (synology, unifi, compliance as of 2026-06-09) are migrated to framework v2. | v1: runtime `NoClassDefFoundError` for `com.vmware.tvs.*` types. v2: no impact — no TVS types referenced. |
| Adapter JAR | `<adapter_kind>.jar` at root of `adapters.zip`, contains `adapter.properties` (ENTRYCLASS + KINDKEY) | Adapter kind not registered |
| Icons | SVG format at `conf/images/{AdapterKind,ResourceKind,TraversalSpec}/` | Generic icons in UI |
| Build number | Must increment on each rebuild — same version = platform skips JAR replacement | "Folder digests are not different" — old buggy JARs persist |

### Pak structure (canonical, v2)

```
vcfcf_<adapter_kind>.<version>.<build>.pak        [outer ZIP]
  manifest.txt                                     [JSON]
  eula.txt                                         [MIT license]
  default.svg                                      [AdapterKind icon]
  resources/resources.properties                   [empty or i18n]
  adapters.zip                                     [inner ZIP]
    manifest.txt                                   [JSON — same as outer]
    eula.txt                                       [same as outer]
    default.svg                                    [same as outer]
    resources/                                     [dir entry]
    resources/resources.properties
    <adapter_kind>.jar                             [entry JAR]
      adapter.properties                           [ENTRYCLASS + KINDKEY]
      com/vcfcf/adapters/<name>/*.class
    <adapter_kind>/                                [dir entry]
    <adapter_kind>/conf/                           [dir entry]
    <adapter_kind>/conf/describe.xml
    <adapter_kind>/conf/resources/                 [dir entry]
    <adapter_kind>/conf/resources/resources.properties
    <adapter_kind>/conf/images/                    [dir entry]
    <adapter_kind>/conf/images/AdapterKind/        [dir entry]
    <adapter_kind>/conf/images/AdapterKind/<ak>.svg
    <adapter_kind>/conf/images/ResourceKind/       [dir entry]
    <adapter_kind>/conf/images/ResourceKind/<rk>.svg  [one per ResourceKind]
    <adapter_kind>/conf/images/TraversalSpec/      [dir entry]
    <adapter_kind>/conf/images/TraversalSpec/default.svg
    <adapter_kind>/lib/                            [dir entry]
    <adapter_kind>/lib/vcfcf-adapter-base.jar
    <adapter_kind>/lib/aria-ops-core-*.jar         [v1 adapters only — omitted for v2]
    <adapter_kind>/lib/[project vendor JARs]
    # vrops-adapters-sdk-*.jar is NOT bundled — resolves from appliance classpath
    <adapter_kind>/work/                           [dir entry]
    <adapter_kind>/doc/                            [dir entry]
```

**C2 shape (2026-06-09 onwards):** `vrops-adapters-sdk-*.jar` is no longer bundled
— it resolves from the appliance shared classpath at runtime (proven by C2 test,
see `context/investigations/c2_no_sdk_jar_install_test.md`).
`aria-ops-core-*.jar` is bundled only for v1 adapters (detected automatically by
scanning compiled class bytecode for `com/vmware/tvs` references). v2 adapters
get neither. `vcfcf-adapter-base.jar` + optional project vendor JARs are always
bundled.

### Tier 1 vs Tier 2 comparison

| | Tier 1 (MPB) | Tier 2 (SDK) |
|---|---|---|
| `template.json` | Yes (BuilderFile) | No |
| `design.json` | Yes | No |
| Adapter JAR | `mpb_adapter-*.jar` (Broadcom) | `<name>.jar` (we built) |
| `describe.xml` | Generated by MPB | Hand-authored |
| Icons | SVG | SVG |
| Outer pak prefix | `mpb_vcf_content_factory_*` | `vcfcf_*` |

## Verification

After every build, run `pak-compare` against an SDK reference pak (e.g.
HPE SimpliVity, Pure Storage). Zero BLOCKINGs is the install gate, same
as Tier 1.

## Agent roster additions for Tier 2

| Agent | Posture | Spawn when |
|---|---|---|
| `sdk-author` | Author (Java) | After `mp-designer` produces an approved Tier 2 design. Writes Java + describe.xml under `content/sdk-adapters/<name>/`. Validates by compiling. |
| `sdk-builder` | Build | After `sdk-author`. Detects JDK, runs `javac`/`jar`, assembles pak, runs pak-compare. |

`mp-designer` is updated (not duplicated) — interview now includes
tier evaluation per `tier_decision_framework.md`.

## Cross-references into the cleanroom spec

The cleanroom bundle under `cleanroom-spec/` is the ground truth for
SDK behavior:

| Question | Read |
|---|---|
| What's the adapter lifecycle / SPI? | `spec/01-adapter-lifecycle.md` |
| What does describe.xml allow? | `spec/02a-describe-xsd-canonical.md` |
| Full behavioral contract (v2 orchestrator target)? | `spec/19-adapterbase-behavioral-contract.md` |
| How does relationships emission work? | `spec/07-relationships-cross-mp.md` |
| Pak layout / classloading? | `spec/13-classloading-and-classpath.md` |
| Install / signing on the appliance? | `spec/16-platform-install-and-signing.md` |
| Why these framework choices? | `spec/17-vcfcf-framework-design-guidance.md` |
| What does an authored Tier 2 adapter look like? | `spec/15-tier2-handoff-for-vcf-cf.md` |

## configure() vs onConfigure() — v2 call chain

In v2, adapter authors implement **`configureAdapter(ResourceStatus,
ResourceConfig)`** instead of v1's `configure(ResourceStatus,
ResourceConfig)`. The orchestration:

1. `AdapterBase.configure(AdapterConfig)` (final — platform calls this)
2. → `VcfCfAdapter.onConfigure(ResourceStatus, ResourceConfig)` (our override)
3. → resets abort flag, closes old HTTP client
4. → `configureAdapter(ResourceStatus, ResourceConfig)` (adapter author's code)
5. → creates new `MetricDataCache` instance

The logger field notes from v1 still apply: use `logInfo()` / `logWarn()`
/ `logError()` helpers on `VcfCfAdapter`. Do NOT use the inherited Log4j
path directly.

## Adapter authoring contract — critical rules (v2)

These requirements are unchanged from v1 except where noted.

### Constructors (both required — UNCHANGED)

```java
public MyAdapter() { super(); }
public MyAdapter(String adapterDir, Integer instanceId) {
    super(adapterDir, instanceId);
}
```

### SPI methods replace v1 abstract methods

v1 required: `configure()`, `getTester()`, `getDiscoverer()`,
`getLiveDataCollector()`, `getHistoricalDataCollector()`,
`getAutoDiscoveryEnabled()`, `needRediscovery()`.

v2 requires: `configureAdapter()`, `getTester()`, `getDiscoverer()`,
`getCollector()` (consolidates live+historical), `onDescribe()`.

See `context/framework_v2_migration.md` for the full import/API mapping.

### Per-resource status required every cycle — NEW in v2

The orchestrator calls `setResourceStatus()` automatically based on
whether `collect()` succeeds or throws. For custom status semantics,
override `VcfCfCollector.mapCollectException(Exception)`.

### Relationship API changed — v2

v1: `resource.addChild()` / `resource.addParent()` (aria-ops-core Resource).
v2: `RelationshipBuilder.build()` returns a `Relationships` object;
pass it to `adapter.addRelationshipsToCurrentCycle(rels)`.

### Auto-discovery behavior — changed in v2

v1: controlled by `getAutoDiscoveryEnabled()` gate in UnlicensedAdapter.
v2: the orchestrator always calls `collectResult.addNewResource()` when
`VcfCfCollector.needsRediscovery()` returns true and `rediscover()`
registers new resources via `adapter.registerNewResource()`. For new
resources discovered during collect, call `adapter.registerNewResource(key)`
from within `collect()`.

### Logging — UNCHANGED

Use `logInfo()` / `logWarn()` / `logError()` helpers on `VcfCfAdapter`.

### String properties — UNCHANGED

Use `pushStringProperty(rc, key, value)` on `VcfCfAdapter`, or
`MetricPusher.ResourceContext.property(key, value)` — both use
`new MetricKey(true, key)` correctly.

### JSON parsing — UNCHANGED

`com.vcfcf.adapter.json.SimpleJson` is included in the framework JAR.

### Rebuild the framework JAR after changes — UNCHANGED

```
cd vcfops_managementpacks/
./adapter_framework/build-framework.sh
```

v2 builds with SDK jar only. If you see `cannot find symbol` for
`com.vmware.tvs.*`, that is a clean-room wall violation — do not add
`aria-ops-core` back; report it as a TOOLSET GAP.

### SSL — CHANGED in v2

v1: `HttpClientBuilder.allowInsecure(true)` was the only option, calling
an inline `insecureSslContext()`.

v2 recommended (production): `HttpClientBuilder.platformSsl(this)` —
uses `AdapterBase.getAdapterTrustManager()` / `getKeyManagers()`,
honoring the platform's certificate management.

v2 lab opt-out: `HttpClientBuilder.allowInsecure(true)` still works
but is now an explicit, documented opt-out (calls
`VcfCfAdapter.insecureSslContext()`).

### ForeignResourceResolver — API changed in v2

v1: `new ForeignResourceResolver(suiteAPIClient, logger)` — required
an aria-ops-core `SuiteAPIClient`.

v2: `new ForeignResourceResolver(bridge, logger)` where `bridge` is a
`ForeignResourceResolver.SuiteApiBridge` functional interface. The adapter
supplies the lambda that calls its pak-bundled Suite API client. The
framework no longer compiles against any TVS or Suite-API artifact.

## Pak signing roadmap

**Current (Phase 2):** paks ship unsigned via the VCF Content Factory
bundle pipeline. The appliance accepts unsigned paks without admin
override (confirmed empirically — 42 unsigned installs in the devel
corpus, see `cleanroom-spec/spec/16-platform-install-and-signing.md`).

**Future — self-signed:** generate a VCF Content Factory keypair, sign
paks with it, include `signature.mf` + `signature.cert`. The appliance
will report `signed: true, signatureValid: true, certificateUntrusted:
true` — proves provenance but doesn't achieve platform trust.

**Future — marketplace:** for paks promoted through the VMware/Broadcom
marketplace, Broadcom re-signs with their trusted key.

## Implementation status

- Phase 1 (framework + tooling skeleton): **COMPLETE**
- Phase 2 (Synology adapter): **IN PROGRESS** — build 1.0.0.7
  installed on devel, 22 objects discovered, 278 metrics collected.
  Pending: migration to v2 framework.
- Phase 3 (framework v2 migration — compliance, synology, unifi): IN PROGRESS.
  Framework v2 JAR built; adapters to be migrated serially by sdk-adapter-author.

Tracking: `designs/tier2-mp-architecture-plan.md`.

## Ambient Suite API stitching transport

Added in the same session as v2, under `com.vcfcf.adapter.stitch`:

**Credential resolution order (implemented in `SuiteApiStitchClient.Builder`):**
1. Explicit — `host`/`username`/`password` from adapter config. Use for remote collectors.
2. Ambient — read `maintenanceuser.properties` via `AmbientCredential.load()` (path resolution: system property `vcfcf.suiteapi.credential.path` → hard-wired default `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`), decrypt via SDK `Crypt`. Targets `https://localhost/suite-api/`. **Do not derive path from `CommonConstants.VCOPS`** — that field is the display name `"VCF Ops"`, not a filesystem path (live bug: build 43, 2026-06-10; see `lessons/sdk-constants-are-display-names.md`).
3. Neither resolves — `IllegalStateException` with actionable message.

**FIPS constraint (hard rule):** The 9.1 collector JVM runs
`-Dorg.bouncycastle.fips.approved_only=true`. Never hand-roll the cipher.
Always use `Crypt.getDefaultCrypt().decrypt(encryptedPassword)` from
`com.integrien.alive.common.security.Crypt` (ships in `vrops-adapters-sdk.jar`).
The class is `@Deprecated` in the SDK jar but is still the only supported
decryption path for this credential file. `@SuppressWarnings("deprecation")`
is applied at the call site in `AmbientCredential.decryptWithPlatformCrypt()`.

**Token lifecycle:** acquire → push → release per call (proven-safe pattern from v1).
Release is always in a `finally` block — cooperative cancellation is honoured.

**SSL:** `VcfCfAdapter.getPlatformSslContext()` (platform trust store, trusts
the localhost self-signed cert). Do not use `allowInsecure` for the Suite API path.

**Adapter opt-in (zero transport code required):**
```java
// In configureAdapter():
stitcher = SuiteApiStitcher.create(this, adapterLogger());
// — or remote-collector fallback:
stitcher = SuiteApiStitcher.createExplicit(this, adapterLogger(), host, user, pass);

// In collect():
stitcher.pushProperties(foreignResourceUuid, props, System.currentTimeMillis());

// In onDiscard():
if (stitcher != null) stitcher.discard();
super.onDiscard();
```

Empirical basis: `context/investigations/suiteapi_ambient_auth_devel_2026_06_09.md`
(devel 9.0.2 + prod 9.1 confirmation). Remote-collector caveat documented in that file.

## Changelog

| Date | Change |
|---|---|
| 2026-06-09 | **Framework default `onDescribe()`**: `VcfCfAdapter.onDescribe()` is now provided by the framework. Loads `describe.xml` via `getAdapterDescribeFile(getAdapterKind(), "describe.xml")`; throws `RuntimeException` with path in message on failure (no silent null). Subclass overrides still win (non-final). Tracked gap in `context/framework_v2_migration.md` §3 closed. `vcfcf-adapter-base.jar` rebuilt (clean, SDK-only). Existing adapters (compliance) that hand-roll `onDescribe()` continue to work without change — their override takes precedence. |
| 2026-06-10 | **AmbientCredential path-resolution bug fix**: `CommonConstants.VCOPS` (`"VCF Ops"` — a display name, not a path) removed from path derivation. New resolution order: system property `vcfcf.suiteapi.credential.path` → hard-wired default `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`. Failure message now lists all candidates tried. `vcfcf-adapter-base.jar` rebuilt (clean, SDK-only). Compliance needs pak rebuild only — no adapter source change. |
| 2026-06-09 | **Ambient Suite API transport**: `AmbientCredential`, `SuiteApiStitchClient`, `SuiteApiStitcher` added to `com.vcfcf.adapter.stitch`. Adapters opt in via `SuiteApiStitcher.create(this, logger)`. FIPS constraint documented: use SDK `Crypt` only. |
| 2026-06-09 | **v2 rehome**: `VcfCfAdapter` now extends `AdapterBase` directly. `aria-ops-core` (`com.vmware.tvs.*`) eliminated from compile classpath and runtime. New SPI: `VcfCfTester`, `VcfCfDiscoverer`, `VcfCfCollector` (all under `com.vcfcf.adapter.spi`). `RelationshipBuilder` rebuilt on SDK `Relationships` API. `ForeignResourceResolver` decoupled from TVS via `SuiteApiBridge` functional interface. `HttpClientBuilder` default SSL changed to platform trust store. `MetricPusher.property()` bug fixed (was using `isProperty=false`). Build script narrowed to SDK jar only. See `context/framework_v2_migration.md` for adapter migration guide. |
| 2026-05-19 | Pak format hard-won lessons documented after 42 install attempts. |
| 2026-05-16 | Pass 23 field evidence added to spec/01. Per-instance single-thread collect confirmed. |
