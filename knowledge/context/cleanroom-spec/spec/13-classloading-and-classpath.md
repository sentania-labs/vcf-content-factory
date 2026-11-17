# 13 — Classloading + Appliance Runtime Classpath

**Status**: Pass 13 (2026-05-16).
**Scope**: what's on the VCF Operations appliance's shared classpath, what's per-pak-isolated, and what this means for VCF-CF packaging decisions (Tier 1 + Tier 2).

## TL;DR

- **The appliance has a shared classpath** containing the legacy SDK + platform API types + logging/trust-manager/RMI utility jars. Specifically: `alive_common.jar`, `alive_platform.jar`, `vrops-adapters-sdk-1.0.jar` + `vrops-adapters-sdk.jar`, `vrops-trustmanager-3.0-SNAPSHOT.jar`, `vrops-logging`, `vrops-csp-client`, `vrops-rmi`, etc.
- **Each adapter has an isolated per-pak classloader** layered on top of the shared classpath. Bundled deps in `<adapter>/lib/` are visible only to that pak.
- **`aria-ops-core` is NOT on the shared classpath.** Adapters that use it MUST bundle it in their own `lib/`. Confirmed for BlueMedora adapters + MPB-generated paks.
- **Direct consequence for MPB Tier 1 Path A / Strategy 4**: NOT viable without Broadcom platform-team participation. The MPB runtime's `com.vmware.mpb.MPBAdapter` lives in `mpb_adapter-*.jar` inside the mpb-adapter pak's own `lib/` — isolated. Other paks cannot access it. **MPB's per-pak codegen (Path B / Strategy 1 or 2) is the only practical Tier 1 path** for VCF-CF.

## The shared classpath: `common-lib/`

Located at `/home/scott/vault/workspaces/vcf-mp-cleanroom/inputs/from-devel/sdk/common-lib/` in the devel bundle. Contents (verified 2026-05-16):

```
alive_common.jar                          — legacy SDK common code (com.integrien.alive.common.*)
alive_platform.jar                        — platform API types (com.vmware.ops.api.*, SolutionDTO, ResourceDto, etc.)
vrops-adapters-sdk-1.0.jar                — SDK contract types (1.0 — likely a compat shim)
vrops-adapters-sdk.jar                    — SDK contract types (unversioned — current)
vrops-trustmanager-3.0-SNAPSHOT.jar       — SSL trust manager (NoopTrustManager + NdcTrustManager — see analysis/pak-signing-chain.md)
vrops-logging-1.0-SNAPSHOT.jar            — platform logging
vrops-csp-client-1.0-SNAPSHOT.jar         — Cloud Services Platform client
vrops-rmi-1.0-SNAPSHOT.jar                — RMI infrastructure
vrops-jmx-metrics-1.0.jar                 — JMX metric collection
vrops-alias-instrumentation-1.0-SNAPSHOT.jar    — instrumentation hooks
vrops-replication-client-1.0-SNAPSHOT.jar       — replication client
vrops-vidb-client-1.0-SNAPSHOT.jar              — vIDB (visibility intermediate DB) client
capability-registry-1.0-SNAPSHOT.jar            — feature/capability registry
```

13 jars. Combined with the WEB-INF lib (which has another ~20 jars for SuiteAPI consumers), this is the universe of classes any adapter can `import` without bundling.

## What's NOT on the shared classpath

Notably absent — adapters MUST bundle these:

- **`aria-ops-core-*.jar`** — confirmed by direct check. The MPB-generated UniFi pak bundles `aria-ops-core-8.0.0.jar` in its own lib; mongodb's pak bundles `aria-ops-core-8.2.0.jar`. Without these per-pak copies, those adapters wouldn't load.
- **Jackson** (jackson-core/databind/annotations/dataformat-xml) — every adapter that does JSON brings their own. Versions diverge wildly (2.11.3, 2.12.3, 2.15.0, 2.17.1 observed across the corpus).
- **HTTP clients** — Apache `httpclient-*` and `httpcore-*`, Ktor variants, `httpasyncclient-*`. Per-adapter.
- **gRPC** (in vim/lib) — vim bundles the whole gRPC stack.
- **Vendor SDK jars** — `nsx-java8-sdk-*`, `vapi-runtime-*`, `vsphere-client-*`, `vcops-vapi-runtime-*`. Per-adapter / per-vendor.
- **Kotlin stdlib + coroutines + reflect** — MPB-generated paks bundle the full Kotlin runtime per-pak.
- **log4j-{api,core}** — per-pak.
- **woodstox-core-*.jar** — per-pak (where XML parsing is needed).
- **commons-text / commons-codec / commons-lang / commons-io / commons-collections / etc.** — observed in adapter lib/ trees, NOT in common-lib.

## Three classloader topology shapes (matches the C1/C2 pak triage)

### Shape C2 — "SDK on classpath, lean per-pak" (SupervisorAdapter pattern)

```
<adapter>.jar (the entry jar) — no lib/ directory
        │
        ▼ relies on platform classpath for:
        │
APPLIANCE CLASSPATH:
    com.integrien.alive.common.adapter3.*      (alive_common.jar)
    com.vmware.ops.api.*                        (alive_platform.jar)
    com.vmware.vrops.*                          (other vrops-* jars)
```

Concrete: SupervisorAdapter ships ONE jar (53 classes, 171 KB), no `lib/`. Its imports are entirely covered by the platform classpath + its own internal helper classes.

This is the LEANEST possible Tier 2 pak. Suitable when an adapter has no third-party dependencies and uses only the legacy SDK + platform API.

### Shape C1 (light) — "SDK on classpath + a few bundled deps"

```
<adapter>/
├── <adapter>.jar (entry jar)
└── lib/
    ├── <a few HTTP/JSON jars>
    └── <a few vendor SDK jars>
```

Concrete: lighter Broadcom-internal adapters with modest dep needs.

### Shape C1 (rich) — "SDK on classpath + heavy bundled stack"

```
<adapter>/
├── <adapter>.jar (entry jar — relies on platform classpath for SDK)
└── lib/
    ├── ~60-100 dependency jars (HTTP stack, Jackson, gRPC, Kotlin runtime, aria-ops-core, etc.)
    └── vendor SDK jars
```

Concrete:
- vim: 102 jars in lib/
- vmwarevi_adapter3: 80+ jars in lib/
- mongodb: ~50 jars including aria-ops-core
- MPB-generated paks: ~60 jars including aria-ops-core + Kotlin runtime

Every richer adapter is C1 — bundling their own dep stack. The platform classpath provides only the SDK + platform API; everything else is per-pak.

## Per-pak classloader isolation

The platform creates a **separate classloader per installed pak**. Each pak's bundled `lib/` jars are visible ONLY to that pak. This means:

- ✅ **Version conflicts don't cascade**: vim's Jackson 2.17.1 can coexist with mongodb's Jackson 2.11.3.
- ✅ **Pak removal cleanly removes its classes**: no stale references in other paks.
- ✅ **Each pak is self-contained**: no install ordering dependencies between paks (except via the platform classpath, which is shared and rarely changes).
- ❌ **Paks CANNOT share classes via each other's lib/.** If pak A bundles `aria-ops-core-8.2.0.jar`, pak B cannot use those classes — pak B must bundle its own copy.

**This is the key finding that closes Path A / Strategy 4 viability for MPB Tier 1**. The `mpb-adapter` pak's `mpb_adapter-*.jar` (containing `com.vmware.mpb.MPBAdapter`) lives in mpb-adapter's per-pak classloader. Other paks (whether VCF-CF-generated or other MPB designs) cannot extend `MPBAdapter` from across the classloader boundary.

**MPB's response to this classloading reality**: per-pak codegen. Each MPB-generated pak gets its OWN copy of the runtime (regenerated with kind-key-renamed packages). No shared dispatch.

## Implications for VCF-CF Tier 1 (MPB-based)

### Path A / Strategy 4 are NOT viable

The "lightweight Tier 1 pak depending on a shared MPB runtime" model requires inter-pak class sharing. The appliance does NOT support this for arbitrary classes. **Stick with Path B** (per-pak codegen, Strategy 1 or 2 — see `spec/12 § 7`).

The ONE exception: if Broadcom adds the MPB runtime classes to `common-lib/` (so they're on the shared classpath), then Strategy 4 becomes viable. That would require platform-team participation; out of scope for VCF-CF MVP.

### Per-pak codegen is the cost-of-doing-business for MPB Tier 1

VCF-CF Tier 1 paks WILL be 22 MB each. That's the reality of shipping a per-pak Kotlin runtime + Ktor + Jackson + aria-ops-core + log4j stack. Can't reduce without platform changes.

### Bundling strategy for VCF-CF Tier 1 paks

Match MPB's exact dependency set. Specifically:

- `aria-ops-core-X.Y.Z.jar` (pin to the version MPB ships — currently 8.0.0 in MPB-generated paks; 8.2.0 in mongodb's pak. Newer/different versions exist; verify per release)
- Kotlin: `kotlin-stdlib-1.5.32.jar`, `kotlin-reflect-1.5.32.jar`, `kotlinx-coroutines-core-jvm-1.5.1.jar` (the versions MPB compiled against)
- Ktor 1.6.2 stack (client / client-apache / client-jackson / client-json / client-logging / utils / network — all `-jvm-1.6.2.jar`)
- Jackson 2.12.3 stack (annotations / core / databind / dataformat-xml / module-jaxb-annotations)
- Apache HTTPClient 4.5.6 + httpcore 4.4.14 + httpcore-nio 4.4.14
- log4j 2.18.0 (api + core)
- woodstox-core 6.2.1
- guava 31.1-jre
- jboss-logging 3.2.1.Final
- commons-text 1.10.0
- jakarta.activation-api 1.2.1
- annotations 13.0
- licensecheck 1.1.5 (Broadcom — per-kind license enforcement; required if using `license_type: "adapter:<kindkey>"` in manifest.txt)

VCF-CF should treat this as a versioned bundle. Pin everything; upgrade explicitly per VCF-CF release.

## Implications for VCF-CF Tier 2 (native adapter generation)

### Choose pak shape based on dependency footprint

- **C2 (lean, no lib/)** — if the adapter uses only the legacy SDK + platform API + `com.vmware.ops.api.*`. Smallest paks. Suitable for adapters that don't do HTTP/JSON (e.g., adapters that work entirely through SuiteAPI internal calls).
- **C1 (light)** — adapter has modest deps (e.g., a vendor SDK + HTTP client). Bundle just what's needed.
- **C1 (rich)** — adapter has heavy framework deps (gRPC, large vendor SDKs, etc.). Bundle the full stack.

VCF-CF generators should expose this as a deployment-mode knob, default to C1 (rich) for safety.

### Always-available platform classes (don't bundle these)

VCF-CF Tier 2 adapters can rely on these being present without bundling:

```
com.integrien.alive.common.adapter3.*                  (the SDK contract)
com.integrien.alive.common.adapter3.config.*           (config types)
com.integrien.alive.common.adapter3.action.*           (action interfaces)
com.integrien.alive.common.adapter3.describe.*         (describe in-memory model)
com.integrien.alive.common.util.*                      (common utilities)

com.vmware.ops.api.*                                   (mid-layer platform API)
com.vmware.ops.api.model.resource.ResourceDto          (foreign-resource bridge — see spec/07)
com.vmware.ops.api.client.Client                       (SuiteAPI client)

com.vmware.vrops.logging.*                             (platform logging — AdapterLoggerFactory)
com.vmware.vrops.secure.connection.*                   (trust manager — Noop and Ndc variants)
```

### MUST bundle these if used

- **`aria-ops-core-*.jar`** (if VCF-CF picks Option B aria-ops-core wrapper, see `spec/12 § Adopt aria-ops-core...`)
- **HTTP client of choice** (Apache, Ktor, OkHttp, etc.)
- **JSON/XML parsing** (Jackson, etc.)
- **Any third-party SDK** (vendor APIs)
- **Logging implementation** (the platform provides `Logger` interface but adapters typically bundle their own log4j or slf4j-backend)

### Version discipline

- **Pin everything per release.** The corpus shows the same library (e.g., Jackson) shipped in 4 different versions across adapters (2.11.3, 2.12.3, 2.15.0, 2.17.1). Each works in isolation because of per-pak classloader isolation. **Don't assume sibling-adapter versions are compatible.**
- **The legacy SDK is the only thing you can rely on having a stable version.** Even there, the corpus shows BOTH `vrops-adapters-sdk-1.0.jar` AND `vrops-adapters-sdk.jar` (unversioned) on the shared classpath — likely a compat-shim arrangement. Adapters that bundle their own SDK (vim does — `vrops-adapters-sdk-2.2.jar` in its lib) override the platform version for their classloader. VCF-CF should NOT bundle the SDK unless there's a specific version-pinning requirement; rely on the platform-shipped copy.

## Quick reference: what to bundle

| Component | Platform-provides | Bundle |
|---|---|---|
| Legacy SDK (`com.integrien.alive.common.adapter3.*`) | ✅ via `alive_common.jar` + `vrops-adapters-sdk.jar` | ❌ |
| Platform API (`com.vmware.ops.api.*`) | ✅ via `alive_platform.jar` | ❌ |
| Logging (`com.vmware.vrops.logging.*`) | ✅ via `vrops-logging-*.jar` | ❌ |
| Trust manager (`com.vmware.vrops.secure.connection.*`) | ✅ via `vrops-trustmanager-*.jar` | ❌ |
| aria-ops-core | ❌ | ✅ if Option B (per `spec/12`) |
| Jackson | ❌ | ✅ (pick a version, pin it) |
| Apache HTTPClient / Ktor / OkHttp | ❌ | ✅ |
| Kotlin runtime (stdlib + reflect + coroutines) | ❌ | ✅ if generated code is Kotlin |
| log4j / logback | ❌ | ✅ (typically log4j 2.x to match MPB-generated paks) |
| gRPC / vendor SDKs | ❌ | ✅ |
| Broadcom licensecheck | ❌ | ✅ if using `license_type: "adapter:..."` in manifest |

## Open questions

1. **Is the appliance classpath stable across versions?** The `-SNAPSHOT` suffixes on most jars suggest active development. VCF-CF should pin a minimum platform version (`vcops_minimum_version` in manifest.txt) and verify the API surface it uses is present.
2. **Are there other shared classpath locations beyond `common-lib/`?** The Tomcat-deployed services (suite-api, etc.) have their own `WEB-INF/lib/` — those are visible to web requests but presumably NOT to adapter classloaders. Worth confirming.
3. **Can adapters define service-provider-loaded extensions?** I.e., does the platform run `ServiceLoader.load(...)` against per-pak classes for any extension points? If yes, that's a way to contribute to platform behavior without per-adapter dispatch. Not investigated.
4. **Class-leak risk from `MPBAdapter`-style inheritance:** since MPB regenerates per-pak, what happens if two MPB-generated paks somehow share a kind-key (collision)? Presumably platform-level rejection — but the classloader isolation might mask this until install time.
