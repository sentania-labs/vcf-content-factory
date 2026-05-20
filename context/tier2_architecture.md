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
(adapter authoring view).

## Four-layer stack

```
Layer 4: Per-adapter code (Claude-generated, ~200–600 lines)
         class SynologyAdapter extends VcfCfAdapter<SynologyConfig>
─────────────────────────────────────────────────────────────────────
Layer 3: vcfcf-adapter-base.jar (THIS PROJECT'S FRAMEWORK)
         abstract class VcfCfAdapter<C> extends UnlicensedAdapter
─────────────────────────────────────────────────────────────────────
Layer 2: aria-ops-core.jar (Broadcom, ship as-is)
         UnlicensedAdapter / Tester / Discoverer / Collector SPI
─────────────────────────────────────────────────────────────────────
Layer 1: vrops-adapters-sdk.jar (Broadcom, on appliance classpath)
         AdapterBase / AdapterInterface3
```

**Rule:** never patch Layer 1 or Layer 2. All VCF-CF code lives at
Layer 3 (framework) or Layer 4 (per-adapter).

## Repo layout

```
content/sdk-adapters/<name>/        # Layer 4: Tier 2 adapter projects
    adapter.yaml                    # name, version, adapter_kind, tier:2, deps
    src/com/vcfcf/adapters/<name>/  # Java source (Claude-generated)
    describe.xml                    # hand-authored, or via framework DSL
    resources/resources.properties
    lib/                            # optional: vendor JARs (JDBC driver, etc.)

vcfops_managementpacks/
    adapter_framework/src/          # Layer 3 framework Java source
    adapter_runtime/                # pre-compiled JARs:
        vcfcf-adapter-base.jar      #   - Layer 3 (we build, commit, ship)
        aria-ops-core-*.jar         #   - Layer 2 (Broadcom, frozen)
        vrops-adapters-sdk-*.jar    #   - Layer 1 (Broadcom, frozen)
        mpb_adapter-*.jar           #   - Tier 1 runtime (unrelated)
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
- No `pom.xml`, no Gradle wrapper. Classpath is the four JARs in
  `adapter_runtime/` plus any per-project `lib/*.jar`.
- The framework JAR (`vcfcf-adapter-base.jar`) is built **once by us**
  and committed; users never compile it.
- Build command: `python3 -m vcfops_managementpacks build-sdk <project-dir>`.
- Auto-detect: bare `build <arg>` routes to Tier 1 if `arg` ends in
  `.yaml`, Tier 2 if it's a directory with `adapter.yaml`.

## Framework JAR scope (MVP — Phase 1)

Aligned with the cleanroom design guide (spec/17 §2) but trimmed to
what Synology actually needs first:

| Component | What it does |
|---|---|
| `VcfCfAdapter<C>` | Abstract base. Typed config binding, lifecycle defaults, hooks the aria-ops-core SPI. |
| `HttpClientBuilder` | Fluent builder over a stdlib HTTP client (java.net.http). Base URL, SSL, default headers. |
| `AuthStrategy` (SPI) + `BasicAuth`, `BearerAuth`, `SessionCookieAuth` | Auth plug-in. Note: Synology uses query-param auth (`_sid=`), not cookies — the adapter manages the session ID directly. SessionCookieAuth is available for APIs that use cookie-based sessions. |
| `RetryPolicy` | Exponential backoff + jitter. Default 3 attempts, retry on 5xx/429/IOException. Required because the platform doesn't retry `collect()` (Pass 23). |
| `ManagedHttpClient` + DNS round-robin | stdlib HTTP client wrapper with base URL, SSL, default headers. On `ConnectException`, resolves all IPs via `InetAddress.getAllByName()` and cycles through them — survives multi-IP hostnames with a dead IP. |
| `MetricPusher` | One-liner helpers: `push(resource).metric(key, value).property(key, value)`. (Note: Synology adapter uses `Resource.addData()` directly instead — MetricPusher is available but not required.) |

**Explicitly deferred** to future framework versions (don't build
until a second adapter needs them):

- OAuth2 client-credentials with refresh
- Kerberos / SPNEGO, AWS SigV4, mTLS
- Cursor / Link-header pagination
- Cross-MP attachment helpers (`ForeignResources` DSL)
- Relationship fluent builder over the 18-method API
- Action annotation dispatcher
- `<CustomGroupMetrics>`, capacity / policy describe surfaces

## Pak format — hard-won lessons (2026-05-19)

These were discovered empirically by installing SDK paks on VCF Ops
9.0.2 and diagnosing failures via appliance logs. Each row cost at
least one failed install attempt.

| Aspect | Requirement | What happens if wrong |
|---|---|---|
| `manifest.txt` (outer + inner) | JSON format, both identical | Staging hangs or install fails silently |
| `manifest.txt` `adapters:` field | `["adapters.zip"]` — **required** | STAGE phase can't locate the adapter archive; install hangs |
| `manifest.txt` `pak_icon:` | `"default.svg"` — must be a valid SVG, not 0-byte | Validate phase rejects: "incorrect format--exiting" |
| Inner `adapters.zip` | Must duplicate `manifest.txt`, `eula.txt`, `default.svg` from outer pak | Validate phase rejects missing files |
| `eula.txt` | Non-empty (MIT license text) | UI shows blank EULA page |
| ZIP directory entries | Explicit zero-byte directory entries required for every subdirectory in `adapters.zip` | `SyncAdapters.extractFiles()` throws `NoSuchFileException` — parent dirs don't exist |
| `vrops-adapters-sdk.jar` | **Must bundle in `<adapter>/lib/`** despite being on shared classpath | `installSolution` task fails in 14ms with empty errorMessages |
| `aria-ops-core.jar` | Must bundle in `<adapter>/lib/` | Adapter class can't load at runtime |
| Adapter JAR | `<adapter_kind>.jar` at root of `adapters.zip`, contains `adapter.properties` (ENTRYCLASS + KINDKEY) | Adapter kind not registered |
| Icons | SVG format at `conf/images/{AdapterKind,ResourceKind,TraversalSpec}/` | Generic icons in UI |
| Build number | Must increment on each rebuild — same version = platform skips JAR replacement | "Folder digests are not different" — old buggy JARs persist |

### Pak structure (canonical)

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
    <adapter_kind>/lib/aria-ops-core-*.jar
    <adapter_kind>/lib/vrops-adapters-sdk-*.jar
    <adapter_kind>/lib/[project vendor JARs]
    <adapter_kind>/work/                           [dir entry]
    <adapter_kind>/doc/                            [dir entry]
```

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
| How does relationships emission work? | `spec/07-relationships-cross-mp.md` |
| Pak layout / classloading? | `spec/13-classloading-and-classpath.md` |
| Install / signing on the appliance? | `spec/16-platform-install-and-signing.md` |
| Why these framework choices? | `spec/17-vcfcf-framework-design-guidance.md` |
| What does an authored Tier 2 adapter look like? | `spec/15-tier2-handoff-for-vcf-cf.md` |

## configure() vs onConfigure() — confirmed call chain

This was investigated against JAR bytecode (aria-ops-core-8.0.0.jar,
vrops-adapters-sdk-2.2.jar). Key findings:

- `UnlicensedAdapter.configure(ResourceStatus, ResourceConfig)` is declared
  **abstract**. It IS the hook that adapter subclasses must implement.
  There is no `super.configure()` to call — doing so would cause a compile
  error.

- `UnlicensedAdapter.onConfigure(ResourceStatus, ResourceConfig)` is called
  by the framework (via `AdapterBase.configureBase(AdapterStatus, ResourceConfig)`)
  **before** our hook. `onConfigure()` does internal setup: nulls the
  tester/discoverer/collector fields, creates the work directory, and
  initialises the SuiteAPI client. It then calls `configure()`.

- The `logger` field in `UnlicensedAdapter` is a **constructor-injected**
  field, not set during `onConfigure()`. It is available when `configure()`
  is called.

- **Do NOT log through the inherited `logger` field.** That logger is
  registered under `com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter`
  and its appender-level filter is derived from the root Log4j logger, which
  sits at WARN in production. INFO messages are silently dropped.

  The correct pattern (already implemented in `VcfCfAdapter`) is to obtain a
  logger via `getAdapterLoggerFactory().getLogger(getClass())` on first use
  and then pin it to INFO with `setLevel(Logger.CustomLevel.INFO)`. This
  gives a logger named after the concrete adapter class, attached to the
  right `SynologyAdapter_3008.log` file, with INFO messages passing through.
  The `VcfCfAdapter.logInfo()/logWarn()/logError()` helpers do this
  automatically via the lazily-initialised `adapterLogger` field — use those
  helpers; do not call the inherited `logger` directly.

- **Wire-format discovery (AdapterLoggerFactoryImpl internals):**
  `AdapterLoggerFactoryImpl(adapterName, adapterDir, instanceId)` creates the
  file appender at `<ADAPTERS_LOG>/<adapterName>/<adapterName>_<instanceId>.log`
  only when all three arguments are non-null. In the no-arg describe path
  `adapterDir` is null so the appender is skipped — that is expected.
  In the live-collection path all three are set, so the file IS created;
  the problem was purely the WARN-level appender filter.
  `Logger.setLevel(CustomLevel.INFO)` calls
  `Configurator.setLevel(loggerName, Level.INFO)` which overrides the
  LoggerConfig level at runtime.

- If `configure()` receives a `ResourceConfig` with an empty
  `getResourceIdentifiers()` list, the cause is NOT a missing
  `super.configure()` call. The most likely cause is a platform
  serialisation failure (e.g., the adapter instance's describe.xml
  identifiers don't match the stored config on the server, or the
  adapter was added before the current describe.xml was installed).
  Use `System.err.println()` debug output to confirm — the collector
  process captures stderr and it should appear in appliance logs.

## Compile-time stub JAR: `vmware-ops-api-stubs.jar`

The aria-ops-core `Resource` class has a field of type
`com.vmware.ops.api.model.resource.ResourceDto`. This class lives on the
appliance's runtime classpath but is NOT in any of the four staged SDK JARs
(the `alive_platform.jar` in `adapter_runtime/` uses the
`com.vmware.vcops.platform.api.*` namespace, not `com.vmware.ops.api.*`).

**Resolution**: a minimal stub JAR `adapter_runtime/vmware-ops-api-stubs.jar`
provides this class for compile-time resolution. It is:
- Included in the compile classpath by `sdk_builder.py`
- NOT bundled in the pak's `lib/` (the real class is on the appliance classpath)
- Gitignored along with all of `adapter_runtime/`

The stub must be regenerated if new `com.vmware.ops.api.*` types become
needed for compilation. Source: `adapter_framework/build-framework.sh`
contains generation instructions in its comments.

## Adapter kind naming convention

SDK adapter kind keys do NOT include the `vcfcf_` prefix in their value —
the prefix is added by the pak filename builder. Example:
- `adapter_kind: hello_world` → pak file: `vcfcf_hello_world.1.0.0.1.pak`
- `adapter_kind: synology` → pak file: `vcfcf_synology.1.0.0.1.pak`

This differs from Tier 1 where `adapter_kind` IS prefixed
(`mpb_vcf_content_factory_*`).

## Adapter authoring contract — critical rules

These are the non-obvious requirements discovered during the Synology
adapter build. Every Tier 2 adapter must follow these or it will fail
silently on the appliance.

### Constructors (both required)

```java
public MyAdapter() { super(); }
public MyAdapter(String adapterDir, Integer instanceId) { super(adapterDir, instanceId); }
```

- **No-arg**: analytics engine calls `Class.newInstance()` for describe
  generation. Without it: `InstantiationException`, adapter kind not
  registered, `apply_adapter` phase fails.
- **Two-arg**: collector calls `Constructor(String, Integer)` for
  instance startup. Without it: `NoSuchMethodException`, adapter
  instance won't start.

### Auto-discovery must be enabled

`getAutoDiscoveryEnabled()` must return `true` (the `VcfCfAdapter`
default). If `false`, `UnlicensedAdapter.processMetrics()` silently
drops every new resource returned by `getCurrentMetrics()`. The
adapter collects but discovers nothing — perpetual "1 object, 0 new
objects."

### Logging

Use the `logInfo()` / `logWarn()` / `logError()` helpers on
`VcfCfAdapter`. They use `getAdapterLoggerFactory().getLogger()` with
an explicit INFO level override. Do NOT use:
- The inherited `logger` field (WARN-filtered, INFO is silent)
- `java.util.logging.Logger` (goes to collector-wrapper.log, not adapter log)
- `System.err.println` (goes to collector-wrapper.log — useful for
  debug only, remove before shipping)

### JSON parsing

`com.vcfcf.adapter.json.SimpleJson` is included in the framework JAR.
Zero-dependency recursive-descent parser. Sufficient for REST API
responses. For adapters needing full Jackson/Gson, bundle in `lib/`.

### String properties: use `addProperty()`, never `resource.addData(key, stringValue)`

`VcfCfAdapter` exposes a `protected static void addProperty(Resource r, String key, String value)` helper.
**Always use this helper — never call `resource.addData(String, String)` for string properties.**

Root cause: the convenience overload `Resource.addData(String, String)` delegates to
`MetricKey.parseMetricKey(String)`, which hardcodes `isProperty = false`. A `MetricKey`
with `isProperty = false` is treated as a numeric metric by the platform. The string
value is silently discarded at collection time — properties never appear in the UI
and no error is raised. The `addProperty` helper constructs `new MetricKey(true, key)`
explicitly to set the property flag correctly.

Numeric metrics (double values) continue to use `resource.addData(String, double)` —
that overload is unaffected.

### Resource naming: use human-readable names

The `ResourceKey(name, kind, adapterKind)` name is the display label
in the VCF Ops tree. Always derive human-readable names from the API:

- Storage pools: `"Storage Pool " + num_id` (not `reuse_1`)
- Volumes: `"Volume " + num_id` (not `volume_1`)
- Disks: `disk.name` field (e.g., "Drive 4", not `sata1`)
- SSD Cache: `"SSD Cache (Volume N)"` (not `alloc_cache_1_1`)
- DiskStation: `model + " " + serial` (e.g., "DS1520+ 20B0RYRXRF3KF")

The stable identifier goes in the `ResourceIdentifier` field, not
the name. Changing names creates new resources (old ones age out).

### World objects

A "World" resource (like vSphere World) serves as a top-down
traversal entry point. Use a fixed identifier across all adapter
instances (e.g., `world_id=synology_world`) so the platform merges
them into one World that aggregates all DiskStations. Include it in
every TraversalSpec path as the first child after the adapter
instance root. No metrics needed — it's a container.

### Relationship `rel.add()` requirement

Calling `parentRes.addChild(childRes)` sets up the relationship on
the Java object, but the platform only sees it if the parent (or
child) is added to the `ResourceCollection` returned from
`getRelationships()`. Missing `rel.add()` causes silent relationship
loss — the most common cause of objects appearing flat in the tree.

### Rebuild the framework JAR after changes

The SDK builder compiles against `adapter_runtime/vcfcf-adapter-base.jar`.
After any change to `adapter_framework/src/**/*.java`, run:

```
cd vcfops_managementpacks/
./adapter_framework/build-framework.sh
```

Without this, adapters get "cannot find symbol" on new framework methods.

### Auth patterns

Synology uses `_sid` as a query parameter, not a cookie or header.
The `SessionCookieAuth` strategy doesn't fit. The adapter manages
auth directly by appending `&_sid=<token>` to every request URL.
Consider adding a `QueryParamAuth` strategy to the framework.

## Framework helpers (Layer 3)

| Component | Package | Purpose |
|---|---|---|
| `SimpleJson` | `com.vcfcf.adapter.json` | Zero-dep recursive-descent JSON parser |
| `ForeignResourceResolver` | `com.vcfcf.adapter.stitch` | Cross-MP resource lookup via Suite API. Caches by (adapterKind, resourceKind, identifierName). Used for Datastore/Host/VM stitching. |
| `RelationshipBuilder` | `com.vcfcf.adapter.stitch` | Fluent parent/child + cross-adapter relationship construction for `getRelationships()` |

## Pak signing roadmap

**Current (Phase 2):** paks ship unsigned via the VCF Content Factory
bundle pipeline. The appliance accepts unsigned paks without admin
override (confirmed empirically — 42 unsigned installs in the devel
corpus, see `cleanroom-spec/spec/16-platform-install-and-signing.md`).

**Future — self-signed:** generate a VCF Content Factory keypair, sign
paks with it, include `signature.mf` + `signature.cert`. The appliance
will report `signed: true, signatureValid: true, certificateUntrusted:
true` — proves provenance but doesn't achieve platform trust. Users
who care can verify the cert manually. Design the `--sign` step as a
pluggable hook in `sdk_builder.py` (no-op today).

**Future — marketplace:** for paks promoted through the VMware/Broadcom
marketplace, Broadcom re-signs with their trusted key. The appliance
reports `certificateUntrusted: false`. This is the Broadcom-side
process; the factory's job is to produce a pak that passes marketplace
review. Scott will work internally on the marketplace submission
pipeline once the content generation workflow is proven.

**The three tiers:**

| Tier | Signature | Platform trust | Distribution |
|---|---|---|---|
| Unsigned | none | accepted (no gate) | GitHub, direct download, bundle pipeline |
| Self-signed | VCF-CF keypair | `certificateUntrusted: true` (accepted, not trusted) | Same, but with provenance proof |
| Marketplace | Broadcom key | `certificateUntrusted: false` (fully trusted) | VMware marketplace |

## Implementation status

- Phase 1 (framework + tooling skeleton): **COMPLETE**
- Phase 2 (Synology adapter): **IN PROGRESS** — build 1.0.0.7
  installed on devel, 22 objects discovered, 278 metrics collected,
  internal parent/child relationships working. Remaining: cross-MP
  Datastore stitching via ForeignResourceResolver (build 8).
- Phase 3 (polish, agent prompts, promotion docs): not started.

Tracking: `designs/tier2-mp-architecture-plan.md`.
