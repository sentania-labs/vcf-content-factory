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
    docs/                           # docset; see "Generated docset" below

src/vcfcf_managementpacks/
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

### Generated docset (`docs/`)

`build-sdk` (and the standalone `docs-gen`) runs `docs_gen.py`, which
owns three classes of file under an adapter's `docs/`:

- **Regenerated every build** (hand edits are lost): `README.md` (the
  index), `inventory-tree.md`, `inventory-tree.svg`,
  `inventory-tree.excalidraw`.
- **Scaffolded once, then hand-curated:** `overview.md`, `installing.md`.
- **Read, never written:** `_index_extra.md`. Optional. Its Markdown is
  merged as written (leading and trailing blank lines dropped,
  indentation kept, a UTF-8 BOM ignored) into `README.md` under the heading
  `## Adapter-Specific Documentation`, after Quick Reference. Use it to
  link hand-written pages (for example `data-reference.md`) from the
  index. Write `###` or deeper headings inside it so they nest under the
  merged heading. A missing or blank file adds nothing (#171).

Any other file under `docs/` is the adapter's own and is never touched.

### Bundled content naming (`content_naming`)

`adapter.yaml` may declare `content_naming`, the naming contract for every
name under `bundled_content` (views, dashboards, super metrics, symptoms,
alerts, reports, recommendations) (#229):

| Value | Meaning |
|---|---|
| `factory_prefixed` (default) | Every name starts with `[VCF Content Factory] ` (RULE-006). |
| `unprefixed` | No name carries `[VCF Content Factory]`. For a pak that keeps its upstream names (the vCommunity paks). |

Content authors read the field to choose the name form. `validate-sdk` and
`build-sdk` enforce it: a declared contract fails on any mismatch; an
undeclared one applies the default as a single warning, so a pak that
predates the field keeps building until it declares. Any other value is an
`adapter.yaml` schema error.

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
- Build command: `python3 -m vcfcf_managementpacks build-sdk <project-dir>`.
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
| `HttpClientBuilder` | `com.vcfcf.adapter.http` | Fluent builder over stdlib HTTP client. Default: JVM trust store. `platformSsl(this)` for platform trust; `platformSsl(this, dialledHost)` adds the opt-in certificate name check (1.0.17, #185); `allowInsecure(true)` as explicit lab opt-out. `timeout(Duration)` is the per-request budget from send to response headers (default 30 s); `connectTimeout(Duration)` bounds establishing the connection and defaults to `timeout` (1.0.17, #222; a zero or negative value is rejected in the setter, `null` falls back), so a short connect timeout makes an unreachable target fail fast while a slow call keeps the full read budget. |
| `CertificateNames` | `com.vcfcf.adapter.http` | Opt-in certificate name checking (1.0.17, #185, #206): `nameCheckingContext`, `strictHostnameVerifier`, `secure(HttpsURLConnection, factory)`, `isNameMismatch`, `isNoUsableHost`, `mismatchedHost`. See "Accepting an untrusted target certificate". No SDK dependency. |
| `ManagedHttpClient` | `com.vcfcf.adapter.http` | HTTP wrapper with base URL, auth, retry, DNS round-robin. |
| `AuthStrategy` + `BasicAuth`, `BearerAuth`, `SessionCookieAuth` | `com.vcfcf.adapter.auth` | Auth plug-in SPI and implementations. |
| `RetryPolicy` | `com.vcfcf.adapter.retry` | Exponential backoff + jitter. Default 3 attempts, 500ms base, 200ms jitter. |
| `RelationshipBuilder` | `com.vcfcf.adapter.stitch` | Fluent builder producing a `Relationships` object. Full-set semantics (`setRelationships`) by default; delta via `buildDelta()`. No aria-ops-core dependency. |
| `ForeignResourceResolver` | `com.vcfcf.adapter.stitch` | Cross-MP resource lookup through a `SuiteApiBridge` functional interface. No TVS/aria-ops-core compile dependency. Optional — only for adapters that do cross-MP stitching. |
| `MetricPusher` | `com.vcfcf.adapter.metric` | Fluent helper for pushing metrics and properties. Uses `new MetricKey(true, key)` for properties (bug fix vs v1). |
| `DescribeBuilder` | `com.vcfcf.adapter.describe` | describe.xml XML generator. No SDK dependency. |
| `SimpleJson` | `com.vcfcf.adapter.json` | Zero-dep recursive-descent JSON parser. |
| `AmbientCredential` | `com.vcfcf.adapter.stitch` | Reads `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`; decrypts via SDK `Crypt.getDefaultCrypt().decrypt()` — the only FIPS-safe path under `-Dorg.bouncycastle.fips.approved_only=true` (9.1+). Path resolution order: (1) system property `vcfcf.suiteapi.credential.path` if set; (2) hard-wired default `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`. **`CommonConstants.VCOPS` is NOT used** — it is a product display-name string (`"VCF Ops"`), not a filesystem path. See `knowledge/lessons/sdk-constants-are-display-names.md`. Never hand-roll the cipher. |
| `SuiteApiStitchClient` | `com.vcfcf.adapter.stitch` | Framework REST transport for Suite API stitching. Token cached per instance; re-acquired on 401; released on `close()` / `discard()`, after which the client refuses every call. Credential resolution: explicit adapter-config fields > ambient `maintenanceuser.properties` > fail with actionable message. **Unified transport:** ALL calls go through `VcfCfAdapter.openPlatformConnection` (`HttpsURLConnection` mirroring the vendor `SuiteAPIClient`: trust-all + ignore-hostname, or cluster truststore + ignore-hostname when `IS_FIPS=true`; see "SSL / hostname verification" below). No `java.net.http.HttpClient` path. source-11 baseline. |
| `SuiteApiStitcher` | `com.vcfcf.adapter.stitch` | Thin facade adapter authors hold as a field. Factory methods: `SuiteApiStitcher.create(adapter, logger)` (ambient) and `SuiteApiStitcher.createExplicit(adapter, logger, host, user, pass)` (remote-collector fallback). No transport code required in the adapter. Surface: `pushProperties`, `pushStats`, `addChild` / `addChildren` (additive Suite API relationship POST, never PUT), `findSingletonResourceId`, `get` (and `get(path, accept)`), `discard`. A non-2xx GET throws `SuiteApiHttpException` (status, `apiErrorCode`, body excerpt). |

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
| `vrops-adapters-sdk.jar` | **Do NOT bundle in `<adapter>/lib/`** — resolves from the appliance shared classpath at runtime. Keep on `javac` compile classpath only. Historical note: this row previously stated "must bundle" citing a 14ms `installSolution` failure. That failure was **misattributed** — it was the missing-directory-entries structural bug of the same era (a true classpath problem surfaces as `NoClassDefFoundError` during collection, not a 14ms install rejection). Disproven by C2 install test: build 42, devel + prod, 2026-06-09 — install succeeded, full collection cycle ran, zero classloading errors in adapter logs. See `knowledge/context/investigations/c2_no_sdk_jar_install_test.md`. | No failure — the appliance ships the SDK jar on its own classpath; the adapter resolves it cleanly at runtime. |
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
see `knowledge/context/investigations/c2_no_sdk_jar_install_test.md`).
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

The gate is enforced by exit code (#181), in both the factory CLI and the
buildkit (`python3 -m sdk_buildkit`), from buildkit 1.0.11:

- One reference rule everywhere: the gate is judged against the CLOSEST
  reference pak (fewest BLOCKING, then WARNING, then INFO). In
  `--reference-dir` mode every pak in the directory is compared and
  reported, but an unrelated reference (an MPB pak beside SDK paks) cannot
  fail the build.
- `pak-compare` exits 1 when the closest reference reports any BLOCKING
  finding, or when the comparison cannot run; 0 only on a clean run. CI
  gates on the exit code, not on grepping the report.
- `build-sdk` compares against every pak in its reference directory after
  assembling the pak and fails the build on a BLOCKING against the closest
  one, or on a crashed compare. With `--release` it also
  fails when no reference pak is available, and deletes the failed pak so
  no later step can publish it.
- `build-sdk --pak-compare-warn-only` downgrades the gate to warnings for a
  dev build only; it is refused together with `--release`.
- A factory checkout has no reference pak unless one is placed under
  `tmp/reference_paks/`; a dev build there logs the skip. The buildkit
  always bundles one under `sdk_buildkit/reference_paks/`.
- `javac` runs with `-proc:none` (framework and adapter compiles), so an
  annotation processor inside a classpath jar never executes at build time.

### Defect gate in pak repos (re-vendor pending)

Each pak repo's release CI runs a VENDORED copy of
`src/vcfcf_packaging/defects.py` as `ci/defect_gate.py` (run as a plain
script, no package). The copies predate #153, so until they are refreshed a
registry entry with a multi-token `Affects:` still parses as valid there and
gates nothing. After #153 lands, every pak repo must re-vendor
`ci/defect_gate.py` from the current `defects.py`. The re-vendor waits on
Scott's decision about where the defect gate should live (vendored copy,
fetched at CI time, or shipped in the buildkit). Script mode is covered by
`tests/test_defect_affects_single_token.py`: with no managed-paks registry
importable, a malformed entry still fails closed for the pak being gated
when its first token names that pak, and the lookup failure is reported on
stderr.

## Agent roster for Tier 2

| Agent | Posture | Spawn when |
|---|---|---|
| `sdk-adapter-author` | Author (Java) | After `mp-designer` produces an approved Tier 2 design. Writes Java + describe.xml under `content/sdk-adapters/<name>/`. Validates with `validate-sdk` and builds with `build-sdk`. |
| `sdk-adapter-reviewer` | Read-only review | After `sdk-adapter-author` reports a build, before the install gate. |

There is no separate build agent. `sdk-adapter-author` runs `build-sdk`
(the `vcfcf_managementpacks` CLI) for the local dev preview; the official
pak is built by the adapter repo's own CI on a `v*` tag, with no agent in
the loop.

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

See `knowledge/context/framework_v2_migration.md` for the full import/API mapping.

### Per-resource status required every cycle — NEW in v2

The orchestrator calls `setResourceStatus()` automatically based on
whether `collect()` succeeds or throws. For custom status semantics,
override `VcfCfCollector.mapCollectException(Exception)`.

**Adapter instance status (issue #223, buildkit 1.0.14).** SDK 2.2 bytecode
(`AdapterBase.setResourceStatus` / `isValidStatusForResource`): ERROR and DOWN
are accepted only on the adapter instance resource, the account row in
Integrations > Accounts. A child resource accepts only NONE, DATA_RECEIVING
and NO_DATA_RECEIVING; anything else is refused (`setResourceStatus` returns
false and the SDK logs a WARN). The SDK's own helpers for a failed instance
are `setAdapterError(LocalizedMsg)` and `setAdapterDown(...)`. So the
framework now sets the adapter instance at the end of a completed cycle: ERROR
(or DOWN when every failure mapped to DOWN) when every resource the cycle
collected failed with ERROR or DOWN, and ERROR when there was nothing to
collect and the discovery step (`rediscover` or `discoverOnCollect`) failed,
with a one-line reason naming the first failure. That reason, the first
failing resource's exception class and message, is shown on the account row
to any user with Integrations access, so `collect()` must throw messages free
of credentials, session ids and tokens; the framework redacts Bearer / Basic /
OpsToken values, `password=`-style pairs and `user:password@` URL userinfo as a
best-effort backstop only (review W1). A partial failure, a
NO_DATA_RECEIVING mapping, or a cycle cut short by a stop or interrupt (also
an interrupt the collector wrapped, seen through the thread's interrupt flag) sets
nothing, and the next cycle starts from the SDK default again. Before this a
cached login failure left the account showing "Collecting" (UniFi build 14
devel_9_1 proof). Not yet seen on a live account row: what the UI shows for an
instance in ERROR is unproven.

Consequence for paks (not changed here): `mapCollectException` returning
ERROR or DOWN for a child resource never reached the platform; the framework's
`setStatusSafe` checks the adapter-instance list (`isAdapterAllowedStatus`),
not the child list (`isResourceAllowedStatus`). Recorded for a follow-up issue.

### Relationship API changed — v2

v1: `resource.addChild()` / `resource.addParent()` (aria-ops-core Resource).
v2: `RelationshipBuilder.build()` returns a `Relationships` object;
pass it to `adapter.addRelationshipsToCurrentCycle(rels)`.

### setRelationships on a foreign resource — per-adapter scoping proven (VCF Ops 9.0.2)

**Proven behavior (devel 9.0.2, synology build 16, 2026-06-10):**
When a non-owning adapter emits `setRelationships(foreignParent, {ownChildren})`
via `RelationshipBuilder.build()`, the platform **scopes the replacement to
the reporting adapter's edges only** — it does NOT clobber the owning
adapter's edges on the same parent.

Evidence: the `vcf-lab-wld01-cl01-iscsi` VMWARE Datastore retained all 22 of
its VMWARE-collected children (HostSystem, VM, Pods, etc.) after the Synology
adapter's build-16 collect pushed a `SynologyIscsiLun` child edge onto it via
`parentForeign(datastoreKey)` + `RelationshipBuilder.build()`. The Datastore
gained the new LUN child edge while the existing VMWARE child set was
undisturbed. This closed synology-build-16 WARNING-1
(`knowledge/context/reviews/synology-build-16.md`).

**Design implication:** adapters that cross-link to foreign resources via
`parentForeign` + full-set `build()` do NOT need a delta/labeled emission
workaround (`addRelationships`, `setGenericRelationships(…, label)`) to
preserve the owning adapter's edges. The full-set form is safe against foreign
parents on this platform version.

**Open residual:** behavior is confirmed on 9.0.2 only. Not yet verified on
9.1. Flag as an acceptance criterion on the first build-16 equivalent install
on 9.1. See `knowledge/lessons/setrelationships-foreign-adapter-scoped.md`.

### Auto-discovery behavior — changed in v2

v1: controlled by `getAutoDiscoveryEnabled()` gate in UnlicensedAdapter.
v2: the orchestrator always calls `collectResult.addNewResource()` when
`VcfCfCollector.needsRediscovery()` returns true and `rediscover()`
registers new resources via `adapter.registerNewResource()`. For new
resources discovered during collect, call `adapter.registerNewResource(key)`
from within `collect()`.

### Cycle start hook (issue #221, buildkit 1.0.17)

`VcfCfAdapter.onCycleStart()` (protected, default no-op) runs once at the
top of every `onCollect`, before `needsRediscovery`, `discoverOnCollect`
discovery and any per-resource `collect`. Use it for per-cycle state: one
snapshot shared by every resource in the cycle, a failed build cached for
the rest of the cycle. Anything it throws (a `LinkageError` included) is
logged at WARN and the cycle continues, except a `VirtualMachineError` or a
thread kill, which end the cycle; an interrupt has its status restored. `VcfCfCollector.needsRediscovery` is still called
exactly once per cycle (pinned by `AdapterInstanceStatusTest`), so paks
that mark the cycle start there (UniFi build 14, Synology build 31) keep
working until they move to the hook.

### Logging — UPDATED (componentLogger added)

Use `logInfo()` / `logWarn()` / `logError()` helpers on `VcfCfAdapter`
for adapter-level messages. For helper/component classes that accept a
`Logger` parameter, use `componentLogger(HelperClass.class)` — never
shadow the base's private `adapterLogger()`. See §15 in
`knowledge/context/framework_v2_migration.md` for the full rule and migration
steps.

**Level (issue #224, buildkit 1.0.14):** `componentLogger` and the adapter's
own logger raise a logger to INFO only when INFO is not already enabled. A
DEBUG or TRACE level that the operator or the pak's `conf/logging.properties`
set is kept however often the logger is looked up. Before 1.0.14 every
lookup called `setLevel(INFO)`, so a per-call lookup (UniFi build 14's
failure hook) silently discarded DEBUG. Fetching once in `configureAdapter()`
is still the pattern.

**What reaches the per-instance log (bytecode, SDK 2.2; issue #228):** the
SDK's `AdapterLoggerFactoryImpl` names each logger `(<instanceId>) <name>` and
attaches the instance file appender (`<adapter>_<id>.log`) at the level of the
entry governing the *bare* `<name>`: an entry from the adapter's
`<ADAPTER_HOME>/<adapter jar name>/conf/logging.properties` (vendor paks ship
`<package> = INFO` there, for example `com.vmware.adapter3.nsxt=INFO`), else
the collector root (WARN). `Logger.setLevel` changes only the logger's own
level, never that appender filter. So a framework helper named after its own
class (`com.vcfcf.adapter.stitch.SuiteApiStitcher`) sat outside the pak's
package entry and its INFO never reached the instance log, while the pak's
own classes did. Field evidence that fits only this: on the devel_9_1 Cloud
Proxy, Synology build 32's `SynologyApiClient` INFO line
(`com.vcfcf.adapters.synology`) is in `SynologyAdapter_1505.log` while the
`SuiteApiStitchClient` configure lines from the same configure call are in
neither that log nor `collector.log`; UniFi build 15 the same
(`knowledge/context/investigations/2026-10-16-unifi-15-devel-9-1-proof.md`).
Since buildkit 1.0.14 `componentLogger(cls)` keeps `cls`'s name when it is in
the adapter's package (or a subpackage) and otherwise names the logger as a
child of the adapter class, `<adapter class>.<simple name>` (for example
`com.vcfcf.adapters.unifi.UniFiAdapter.SuiteApiStitcher`), so framework helper
lines follow exactly the adapter's own level. Reproduced locally against the
real SDK factory and log4j-core (`ComponentLoggerTest`); a live Cloud Proxy
check is still owed. Where the Cloud Proxy's package-scoped entry comes from
(our paks ship no `logging.properties`) is not established; the platform's
per-adapter log-level setting is the likely writer. A pak that wants INFO
visible by default could ship `conf/logging.properties` with
`<its package> = INFO` like vendor paks; the builder does not do that today.

**Per-adapter log file appender — classloader behavior on hot-reload
(proven empirically, synology build 16, devel 9.0.2, 2026-06-10):**

The platform wires each adapter instance's `componentLogger` handles to a
per-adapter file appender at adapter load time. When an adapter pak is
hot-reloaded (re-installed without collector restart), the logging factory
re-initializes and the **old file appender detaches** — new log calls from
the freshly loaded adapter class are not written to the adapter's log file
until the adapter completes its first `configure` cycle (which re-fires
`componentLogger` wiring). During the gap between pak load and the first
completed configure cycle the messages are absorbed by the root logger only
(typically `collector.log`).

**Operational rule:** `collector.log` is authoritative for diagnosing issues
in the window immediately after a hot-reload. Per-adapter log files resume
only once the collector has completed a full configure cycle on the new build.
If per-adapter logs appear silent post-install, check `collector.log` for the
INSTALL and first configure/collect breadcrumbs before assuming a logging bug.
A collector restart eliminates the gap entirely — the appender wires correctly
at startup. Cross-reference: `knowledge/context/framework_v2_migration.md` §15
(reload-race note).

### String properties — UNCHANGED

Use `pushStringProperty(rc, key, value)` on `VcfCfAdapter`, or
`MetricPusher.ResourceContext.property(key, value)` — both use
`new MetricKey(true, key)` correctly.

### JSON parsing — UNCHANGED

`com.vcfcf.adapter.json.SimpleJson` is included in the framework JAR.

### Rebuild the framework JAR after changes — UNCHANGED

```
cd src/vcfcf_managementpacks/
./adapter_framework/build-framework.sh
```

v2 builds with SDK jar only. If you see `cannot find symbol` for
`com.vmware.tvs.*`, that is a clean-room wall violation — do not add
`aria-ops-core` back; report it as a TOOLSET GAP.

**Which framework a pak carries (issue #214, buildkit 1.0.14).** Each pak
bundles its own `vcfcf-adapter-base.jar` in `<adapter>/lib/`, loaded by that
adapter's own class loader, so paks built on different buildkits run side by
side on one collector. Both build paths (`build-framework.sh` and
`sdk_builder._ensure_framework_jar()`, the one the buildkit uses in pak CI)
stamp the jar manifest: `Implementation-Title: vcfcf-adapter-base`,
`Implementation-Version: <buildkit version>`, `Implementation-Vendor`, and
`X-Vcfcf-Source-Commit: <factory commit>` (`-dirty` when the framework source
had uncommitted changes, `unknown` without git). In the factory the version is
`BUILDKIT_VERSION` and the commit comes from git; in the kit both come from
the kit's `VERSION` and `SOURCE_COMMIT` files, never from git, which inside a
pak repo would name the pak's commit. `build-sdk` prints the stamp
(`framework: vcfcf-adapter-base 1.0.14 (source <sha>)`), and each adapter
instance logs it once at its first configure (`VcfCfAdapter: framework
vcfcf-adapter-base 1.0.14 (source <sha>)`). A jar built before the stamp is
reported as unversioned. Side-by-side versions are safe only while the
framework changes no JVM-wide state; `tests/test_adapter_framework_no_jvm_wide_state.py`
greps the framework source for those setters. Not done: pak-compare does not
report a framework version change between two paks.

### SSL — CHANGED in v2

v1: `HttpClientBuilder.allowInsecure(true)` was the only option, calling
an inline `insecureSslContext()`.

v2 recommended (production): `HttpClientBuilder.platformSsl(this)` —
uses `AdapterBase.getAdapterTrustManager()` / `getKeyManagers()`,
honoring the platform's certificate management.

v2 lab opt-out: `HttpClientBuilder.allowInsecure(true)` still works
but is now an explicit, documented opt-out (calls
`VcfCfAdapter.insecureSslContext()`).

#### Accepting an untrusted target certificate (2026-09-25)

Wire behaviour (bytecode, SDK 2.2 and the prod 9.1.1 appliance jars;
evidence in `knowledge/context/investigations/tls_certificate_unknown_2026_09_25.md`):

- Validate Connection runs `checkCertificate` before `test()`. The SDK
  default `onCheckCertificate` probes `getConnectionURLs(adapterConfig)`;
  the SDK default of that is `singletonList(getConnectionURL(cfg))` and
  `getConnectionURL` returns `null`, so the result is `NOT_SUPPORTED` and
  no review dialog appears. A non-empty URL list makes the platform open
  each URL over its own `HttpsConnection` + instance `CustomTrustManager`
  and return an untrusted chain to the UI as "Review and accept
  certificate"; `test()` waits for the accept.
- The collector's certificate-chain task
  (`Collector.handleGetAdapterSourceCertificateChain`) also calls
  `getConnectionURLs` on the running instance.
- Accepted certs are stored per adapter instance
  (`ResourceConfig.getTrustedCertificates()`) and loaded into the instance
  `CustomTrustManager` by `initTrust` before `configure`/`test`/`discover`,
  so `getPlatformSslContext()` / `platformSsl(this)` trust them with no
  transport change.
- `getCertificateRenewalUrls()` is consumed by
  `NonDisruptiveCertificateHandler`: it builds a throwaway instance (no-arg
  constructor, then `configure(adapterConfig)`), reads the set (`null` or
  empty logs `"Adapter certificate renewal url set is empty"`), keeps URLs
  whose `new URL(u).getHost()` matches the failing endpoint, and GETs each
  expecting JSON `{"jwt_token": ...}` carrying `certificate_chain` and the
  old thumbprint. That is a VCF-component renewal protocol; third-party
  targets (vCenter REST root, DSM, UniFi) are not expected to serve it, so
  for them renewal fails and the admin re-accepts via Validate Connection.
  **The framework therefore does not override `getCertificateRenewalUrls()`**
  (decision 2026-09-25, framework review W2): declaring the review URLs
  there would buy no renewal, and each unknown-certificate event on a saved
  instance would cost a throwaway adapter plus `configure()` (whose HTTP
  client is never discarded) and a GET to the target. Consequence: the
  collector keeps logging DEF-005's `"Adapter certificate renewal url set
  is empty"` for framework adapters. That line is harmless; it only means
  non-disruptive renewal is not attempted. Revisit only for a target that
  serves the renewal endpoint (a pak can then override the method itself).
- Hostname: `CustomTrustManager` extends `X509ExtendedTrustManager`, so JSSE
  does not add its endpoint-identity check, and its overloads do PKIX chain
  validation only. Setting the JDK default `HostnameVerifier` explicitly is
  a no-op (`HttpsURLConnection` recognises the default by class and leaves
  the name to the trust manager), and `java.net.http.HttpClient` has no
  verifier to set. So on `getPlatformSslContext()` / `platformSsl(this)` the
  chain is validated but the name is not matched to the host dialed, on
  either client (compliance build 93). The platform's review probe does
  check the name (`getVerifier()`, `CustomHostnameVerifier`).
  **Opt-in name checking (issues #185, #206, buildkit 1.0.17):**
  `getPlatformSslContext(String dialledHost)` and
  `HttpClientBuilder.platformSsl(this, dialledHost)` wrap the platform trust
  manager (`com.vcfcf.adapter.http.CertificateNames.nameCheckingContext`):
  the platform chain check runs first, unchanged (an untrusted chain still
  fails with the platform's own exception, so the accept dialog applies),
  then the leaf must carry the dialled host (IP SAN for an IP; DNS SAN, or
  the CN only when there is no DNS SAN, for a name; RFC 6125 wildcards),
  during the handshake, before any credential is sent. The host is fixed
  when the context is built, never read from the connection: BouncyCastle
  JSSE on 9.1.1 collectors reports no peer host on `HttpsURLConnection`
  sockets (compliance build 94). A blank or unusable host (a URL, a path,
  `?`, `#`, `@`, a Unicode name not in its punycode xn-- form) refuses every
  handshake with `CertificateNames.NO_HOST_MESSAGE`. For `HttpsURLConnection` paths
  (JAX-WS, raw SOAP) also call `CertificateNames.secure(conn, factory)`,
  which sets the strict always-false `strictHostnameVerifier()` so the JDK's
  own name check is final as well. The no-argument forms are unchanged, so a
  pak that does not opt in behaves as before. The Suite API hop
  (`openPlatformConnection`) is never name checked (loopback exemption: it
  keeps trust-all and ignore-hostname, see "SSL / hostname verification"
  below). An account entered by IP passes only when the certificate lists
  that IP; accepting the certificate does not fix a name mismatch.

Framework surface (`VcfCfAdapter`): `certificateCheckUrls(ResourceConfig)`
hook (default empty; called on an UNSAVED config, derive everything from
the argument), a `getConnectionURLs` override fed by it (falls back to
the SDK default when empty; it applies no allowInsecure logic itself, that
is the hook's job), and `onTest` maps a trust failure in the cause chain to
a readable message (the hook is consulted only after a trust failure is
found, and any `Throwable` from it means "no prompt"). Since buildkit 1.0.17
(issue #205) that default text is neutral: it points at the accept dialog
("open the account and click Validate Connection to review and accept the
certificate", "enter the host by the name on its certificate") and names
Allow Insecure SSL only when `describesAllowInsecure(config)` is true, which
by default reads the pak's describe (`onDescribe()`, once per instance) for
an `allowInsecure` identifier on the tested adapter-instance kind. The
describe, not the stored config, decides: an account saved before a pak
dropped the field still stores it. A certificate NAME failure gets its own
default text (`certificateNameFailureMessage`): a certificate that does not
carry the host dialled (`CertificateNames.isNameMismatch`, from the opt-in
check or the JDK's; "the certificate does not name <host>; enter the host by
a name on the certificate; accepting the certificate does not fix a name
mismatch", host read by `CertificateNames.mismatchedHost`), or a name check
with no usable host (`CertificateNames.isNoUsableHost`; set the host, a
Unicode name in its punycode xn-- form). The name is checked only after the
chain passed, so `findCertificateTrustFailure` never sees these; without
this branch the admin got raw TLS text such as `(certificate_unknown) No
subject alternative name matching ...` (framework review B1, 2026-10-24).
A pak replaces any of the three texts by overriding
`certificateFailureMessage(Throwable failure, ResourceConfig config, String
defaultMessage)`, called only for a certificate failure; `null` or blank
keeps the default, and anything it throws is logged and the default kept,
except a `VirtualMachineError` or a thread kill (`isThreadKill`, matched by
class name, issue #242), which are rethrown; an interrupt has the thread's
interrupt status restored. Compliance's workaround (rethrowing without the
cause and the PKIX strings so the framework does not rewrite them) keeps
working; a compliance build can drop it once it uses
`getPlatformSslContext(host)`, since its wrong-name failures then reach the
hook with `isNameMismatch` true. Two parsers read the
`allowInsecure` identifier, from either the legacy free-text value or the
`enum="true"` pulldown:

- `parseAllowInsecure(v)` / `isAllowInsecure(rc)`: strict, insecure only
  for `true` (trimmed, any case). Versus the legacy untrimmed
  `"true".equalsIgnoreCase(v)`, the only stored values that change are
  `true` with surrounding whitespace (`" true"`, `"TRUE "`): secure today,
  insecure after adoption.
- `parseAllowInsecureLegacyNotFalse(v)` / `isAllowInsecureLegacyNotFalse(rc)`:
  bit-for-bit the legacy `!"false".equalsIgnoreCase(v)`, untrimmed (absent
  or blank = insecure, only an exact `false` in any case validates). No
  stored value changes.

With the pulldown, new instances only store `true` or `false`, which both
parsers read identically; the difference is only ever about values stored
before the pulldown.
Pulldown XML used by the framework family:

```xml
<ResourceIdentifier key="allowInsecure" nameKey="N" type="string"
                    required="false" dispOrder="N" default="false"
                    enum="true">
  <enum value="false" displayOrder="1"/>
  <enum value="true" displayOrder="2"/>
</ResourceIdentifier>
```

Pak adoption (sdk-adapter-author; recorded 2026-09-25, not yet applied).
Default: Scott approved flipping the TLS default to secure for the template,
synology and unifi (template#8, carried to both paks; verbatim record:
`knowledge/context/approvals/2026-09-25-scott-decisions.md` item 15), so
every pulldown uses `default="false"`. The default applies to new instances only; stored
values keep their meaning per the Parse column.

| Pak | `certificateCheckUrls` returns | `allowInsecure` describe.xml | Parse (stored values that change meaning) |
|---|---|---|---|
| compliance | `https://<vcenter_host>:443` (REST, VAMI `/api/appliance`, SOAP `/sdk` all on 443) | free text, default `false`: switch to pulldown | `isAllowInsecure(rc)`; only padded `true` changes (secure to insecure) |
| synology | `https://<host>:<port>` (port default 5001) | free text, default `true`: switch to pulldown, default `false` | today `!"false".equalsIgnoreCase(v)`. Use `isAllowInsecureLegacyNotFalse(rc)`: nothing changes. If `isAllowInsecure(rc)` is used instead, these stored values flip from insecure to secure: absent, blank or whitespace, `false` with surrounding whitespace, and any other non-`true` text (`yes`, `1`); such an instance then validates certificates and fails collection until the admin accepts the certificate or picks `true` |
| unifi | `https://<host>:<port>` (port default 443) | free text, default `true`: switch to pulldown, default `false` | `isAllowInsecure(rc)`; only padded `true` changes (secure to insecure) |
| vcommunity, vcommunity-os, vcommunity-vsphere | `https://<host>:<port>` (vCenter; `port` is an integer identifier, default 443) | already a pulldown | `isAllowInsecure(rc)`; only padded `true` changes |
| sdk-template repo | `https://<host>:<port>` | free text, default `true`: switch to pulldown, default `false` | `isAllowInsecure(rc)`; only padded `true` changes |

Every override returns empty when the pak's chosen parser says insecure, or when the host identifier is blank, and reads only
from the passed `ResourceConfig`.

### ForeignResourceResolver — API changed in v2

v1: `new ForeignResourceResolver(suiteAPIClient, logger)` — required
an aria-ops-core `SuiteAPIClient`.

v2: `new ForeignResourceResolver(bridge, logger)` where `bridge` is a
`ForeignResourceResolver.SuiteApiBridge` functional interface. The adapter
supplies the lambda that calls its pak-bundled Suite API client. The
framework no longer compiles against any TVS or Suite-API artifact.

## Pak signing roadmap

**Current (Phase 2):** paks ship unsigned via the VCF Content Factory
bundle pipeline. On 9.0.x and 9.1.x the appliance installs unsigned paks
**only when the cluster-wide "Allow unsigned PAK installation" toggle is
on**; 8.18 has no such toggle (`investigations/2026-10-23-compliance-8-18-feature-check.md` row 1) (Admin UI
`/admin`, Administrator Settings, Security Settings; CaSA marker file
`/storage/db/casa/unsigned_pak_allowed`). With the toggle off, every
upload fails with `unsigned_pak_installation.not.allowed`, whatever
`ignoreSignatureChecking` says.

> **Correction, 2026-10-14.** This section used to say the appliance
> accepts unsigned paks without admin override, citing 42 unsigned installs
> in the devel corpus (`cleanroom-spec/spec/16-platform-install-and-signing.md`).
> That was a lab artifact. devel had the toggle switched on by hand on
> 2026-04-17 (CaSA audit log), and prod also has it on. A fresh 9.1.1
> install (devel_9_1) came up with it off and refused every factory pak.
> The default is off on 9.0.x and 9.1.x. Third-party paks cannot be
> "trusted signed": the platform only trusts VMware/Broadcom signatures, so
> a self-signed pak still needs the toggle. Evidence:
> `knowledge/context/investigations/2026-10-14-unsigned-pak-policy-9-1-1.md`.

**Future — self-signed:** generate a VCF Content Factory keypair, sign
paks with it, include `signature.mf` + `signature.cert`. The appliance
will report `signed: true, signatureValid: true, certificateUntrusted:
true` — proves provenance but doesn't achieve platform trust.

**Future — marketplace:** for paks promoted through the VMware/Broadcom
marketplace, Broadcom re-signs with their trusted key.

## Implementation status

This is an **architecture** doc: it describes how the Tier 2 framework
works, which is durable. It deliberately does **not** track per-adapter
build numbers or phase status — that rots fast and belongs where it stays
current, not embedded in a stable reference doc (see
`knowledge/lessons/no-volatile-status-in-reference-docs.md`):

- **Per-adapter build state:** the SDK reviews
  (`knowledge/context/reviews/<adapter>-build-<N>.md`).
- **Current (v2) design surface:** `knowledge/designs/vcfcf-base-v2-adapterbase-rehome.md`
  plus the per-adapter v2 migration designs under `knowledge/designs/sdk-adapters/`.
- **Historical:** `knowledge/designs/tier2-mp-architecture-plan.md` is the **v1**
  implementation plan — it predates this framework and still describes the
  retired `UnlicensedAdapter` / `aria-ops-core` design. Read it for history,
  **not** as a current target.

This document describes the **v2** framework.

## Ambient Suite API stitching transport

Added in the same session as v2, under `com.vcfcf.adapter.stitch`:

**Credential resolution order (implemented in `SuiteApiStitchClient.Builder`):**
1. Explicit — `host`/`username`/`password` from adapter config. Use for remote collectors.
2. Ambient — read `maintenanceuser.properties` via `AmbientCredential.load()` (path resolution: system property `vcfcf.suiteapi.credential.path` → hard-wired default `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`), decrypt via SDK `Crypt`. Targets `https://localhost/suite-api/`. **Do not derive path from `CommonConstants.VCOPS`** — that field is the display name `"VCF Ops"`, not a filesystem path (live bug: build 43, 2026-06-10; see `knowledge/lessons/sdk-constants-are-display-names.md`).
3. Neither resolves — `IllegalStateException` with actionable message.

**GET failures and Accept (issue #201):** `get(path)` sends
`Accept: application/json`; `get(path, accept)` sends the caller's value
(`null` or blank means JSON; a value with a control character is refused
before anything is sent). Use `*/*` for endpoints that return a raw body,
such as `GET /api/configurations/files?path=SolutionConfig/<name>.xml`. A
non-2xx answer throws `SuiteApiHttpException`, an `IOException` subclass, with
`getStatusCode()`, `getApiErrorCode()` (the JSON body's numeric
`apiErrorCode`, or `null`) and `getBodyExcerpt()` (at most 512 characters,
control characters replaced). The message keeps its shape (`Suite API GET
<url> HTTP <status>`) plus ` apiErrorCode <n>` when present; the body is not in
the message. Example: the configuration-file store answers a missing file with
HTTP 400 and `apiErrorCode` 1501, so a pak can now tell it from any other bad
request (compliance and vcommunity treat every 400 and 404 as absent today).

**What the client logs (issue #227):** the credential mechanism
(`explicit` or `ambient`), the ambient source label and the endpoint, never
the principal (the Suite API account name) and never a credential value. The
401 and no-token exception messages carry the mechanism only. Paks no longer
need a `principal=` redaction rule for framework output.

**FIPS constraint (hard rule):** The 9.1 collector JVM runs
`-Dorg.bouncycastle.fips.approved_only=true`. Never hand-roll the cipher.
Always use `Crypt.getDefaultCrypt().decrypt(encryptedPassword)` from
`com.integrien.alive.common.security.Crypt` (ships in `vrops-adapters-sdk.jar`).
The class is `@Deprecated` in the SDK jar but is still the only supported
decryption path for this credential file. `@SuppressWarnings("deprecation")`
is applied at the call site in `AmbientCredential.decryptWithPlatformCrypt()`.

**Token lifecycle:** A bearer token is acquired lazily on the first call and cached
for the lifetime of the `SuiteApiStitchClient` instance. On HTTP 401, the token
is re-acquired and the failed request is retried exactly once (per
`specs/20-suiteapi-client-behavioral-contract.md` §1/§2). The cached token is
released in `discard()` — failures are logged WARN and swallowed (the platform's
token TTL is the safety net, per §3). Release is always attempted even on the
cancellation path.

**Closed state (issue #217):** `close()` (and `discard()`, now the same call)
also marks the client closed. A closed client never acquires a token again:
`get` throws an `IOException` saying the client is closed, and `pushStats`,
`pushProperties`, `addChild` / `addChildren` and `findSingletonResourceId`
send nothing and log one WARN for the first refused call (DEBUG after that).
`isClosed()` reports it; the `SuiteApiStitcher` facade has `close()` and
`isClosed()` too. Before buildkit 1.0.14, a cycle still running on a client
its adapter had replaced on reconfigure logged in again and left a token
behind. Every shipped pak already retires a stitcher after discarding it, so
none changes behaviour beyond losing that stray login.

**SSL / hostname verification: vendor-mirror transport (DEF-005, issue #215):**

ALL Suite API calls (loopback and explicit/remote) go through
`VcfCfAdapter.openPlatformConnection(url)`, an `HttpsURLConnection` wired to
mirror `aria-ops-core` `SuiteAPIClient.getClientConfigBuilder()` exactly
(bytecode: `knowledge/context/api-surface/casa-injected-vs-raw-client.md` §3).
No loopback/remote peer-gating: the vendor does not gate, so neither do we.

- **Mode signal:** environment variable `IS_FIPS`, `Boolean.valueOf`
  semantics (vendor `Constants.FIPS_MODE_ENABLED`, and `SSLOptions.IS_FIPS`).
  Nothing else decides the mode. `-Dorg.bouncycastle.fips.approved_only` is
  printed as a diagnostic in the mode line but is not a signal: no vendor
  class on this path reads it. The mode, and the signal that chose it, is
  logged once per adapter instance at INFO. The dispatch is the static
  `applySuiteApiTransport`, unit-tested in both directions.
- **Non-FIPS** (`IS_FIPS` not `true`): trust-all (`insecureSslContext()`) +
  all-true `HostnameVerifier`. Vendor: `verify("false")` + `ignoreHostName(true)`.
  No cluster file is read.
- **FIPS** (`IS_FIPS=true`): the socket factory the vendor's
  `useClusterTruststore(true)` builds (`vcops-suiteapi-client`
  `HttpClientFactory` → `SSLOptions.getSSLOptions(VROPS_CLUSTER)` →
  `vROpsSSLSocketFactory`), + all-true `HostnameVerifier`. Vendor:
  `verify("true")` + `ignoreHostName(true)`. Inputs (bytecode detail in
  `knowledge/context/api-surface/casa-injected-vs-raw-client.md` §3):
  - options file: `$STORAGE/vcops/user/conf/ssl/secure-communications.properties`
    (`STORAGE` from the environment, else a system property); every key
    read as `inter_cluster.<key>` then `default.<key>`;
  - required keys `protocol`, `store_type`, `algorithm`,
    `supported_protocols`, `supported_cipher_suites` (`%all%` = JRE
    defaults; `TLS_RSA*` suites dropped in FIPS); `truststore` (and the
    optional client `keystore`) with `%VAR%` / `$VAR` substitution;
  - passwords `truststore_password` / `keystore_password`: `.encrypted`
    (SDK `Crypt`) before plain; the sentinel `%truststore_password%` /
    `%keystore_password%` redirects to `storePass.properties`
    `ssltruststorePassword` / `sslkeystorePassword`, `.encrypted` first;
  - context: `SSLContext(protocol)`, truststore as `store_type`,
    `TrustManagerFactory(algorithm)`, client keystore (if set) as
    `KeyStore.getDefaultType()` with `KeyManagerFactory(algorithm)`; every
    socket restricted to the configured protocols and cipher suites.
  The factory is cached per adapter instance and rebuilt when the
  modification time or size of the options file, `storePass.properties`,
  the truststore or the keystore changes (vendor: options once per JVM,
  context reloaded when the truststore's `lastModified` moves). Any
  unreadable or incomplete input throws an `IOException` naming the file
  and key and logs one WARN per instance; there is **no** fallback to
  trust-all. Where the vendor would carry on with an empty trust store and
  fail every handshake, the framework fails first and says why. The Suite
  API call fails; `SuiteApiStitchClient` logs and swallows it, so
  collection continues without stitching.
- **Why not the platform TOFU manager:** `CustomSSLSocketFactory` /
  `CustomTrustManager` never persist trust for framework adapters ("Adapter
  certificate renewal url set is empty") and PKIX-fail every cycle (DEF-005;
  `knowledge/lessons/suite-api-stitch-ssl-tofu-vs-java-http.md`).
- **Retired:** `java.net.http.HttpClient` on the Suite API path.
  `VcfCfAdapter.insecureSslContext()` remains the explicit lab opt-out for
  target-system connections and the non-FIPS Suite API trust half.

`isLoopbackUrl(String)` is informational only (used for the builder INFO log).

`HttpClientBuilder.platformSsl(this)` is correct and unchanged for target-system
(vCenter, NAS, etc.) connections — this SSL note applies only to the Suite API
stitching transport.

**Adapter opt-in (zero transport code required):**
```java
// In configureAdapter():
stitcher = SuiteApiStitcher.create(this, componentLogger(SuiteApiStitcher.class));
// — or remote-collector fallback:
stitcher = SuiteApiStitcher.createExplicit(this, componentLogger(SuiteApiStitcher.class), host, user, pass);

// In collect():
stitcher.pushProperties(foreignResourceUuid, props, System.currentTimeMillis());

// Link a foreign child under the pak's own shared singleton (additive POST).
// Look the singleton up every cycle (one local GET); never cache its id across
// cycles. true from addChild means "request accepted", not "linked".
String worldId = stitcher.findSingletonResourceId(ADAPTER_KIND, "MyWorld");
if (worldId != null && stitcher.addChild(worldId, foreignChildUuid)) {
    logger.info("Link to MyWorld requested (accepted by Suite API)");
}

// In onDiscard():
if (stitcher != null) stitcher.discard();
super.onDiscard();
```

**Relationships through the Suite API: POST adds, PUT replaces.**
`addChild(parentId, childId)` / `addChildren(parentId, ids)` issue
`POST /api/resources/{parentId}/relationships/children` with body
`{"uuids":["<childId>", ...]}` (operation `addRelationship`; path, verb and
`uuid-values` body are identical in the 9.0 and 9.1 operations-api specs).
The `PUT` on the same path (`setRelationship`) removes every existing child
and substitutes the body, so when several adapter instances share one parent
(a pak-level singleton each instance links its own vCenter or target to),
each instance's PUT would wipe the others' links and the last instance to
collect would win. The stitcher exposes no PUT/replace variant on purpose.
Spec facts to design around: the add is asynchronous (204 means accepted,
read `GET .../relationships/children` back to confirm), so a `true` return
means "request accepted", not "linked", and should be logged that way; children that would
form a cycle are skipped; 404 only when every UUID in the body is invalid.
Repeat-add of an existing edge is not described in words by the spec; the
first live use must confirm one edge remains after several cycles. Error
posture matches `pushStats`: one 401 retry, every failure logged at WARN and
swallowed, the call returns `false`. Blank or non-UUID ids are skipped with a
WARN before anything is sent (logged truncated, control characters stripped);
ids are trimmed and lowercased before duplicates collapse, and a child equal
to its parent is skipped with a WARN. Because `pushProperties`, `pushStats`,
`addChild` / `addChildren` and `findSingletonResourceId` repeat every cycle,
a failure of any of them is logged as one WARN line with the exception class
and message and its stack trace only at DEBUG. The one exception: the first
time a client sees an unexpected exception class (anything but the
`IOException` family and interrupts, a malformed response included) for an
operation, that line carries the stack trace at WARN; later ones are one line
(issue #192; until buildkit 1.0.14 the push methods logged a full trace every
cycle). An interrupt during a push restores the thread's interrupt flag.

**Known limitation: nothing removes these edges.** An edge added through
`addChild` / `addChildren` persists until something deletes it with
`DELETE /api/resources/{parentId}/relationships/children/{childId}`
(operation `deleteRelationship`; asynchronous, 204/404, identical in the 9.0
and 9.1 specs). The facade does not wrap that call today. A target dropped
from an adapter instance's scope (for example a vCenter removed from its
configuration) therefore stays a child of the shared parent, and any roll-up
over the parent's children keeps counting it, with no error anywhere. A pak
whose scope can shrink owns that cleanup, or records the stale edge as a
known limitation in its design.

`findSingletonResourceId(adapterKind, resourceKind)` runs
`GET /api/resources?adapterKind=..&resourceKind=..`, keeps entries whose
`resourceKey` kinds match the trimmed arguments exactly (case-sensitive),
and returns the `identifier` (lowercase) only when exactly one matches and it
is a UUID. Zero (normal on the first cycle, before the platform has created a
newly discovered resource; also a wrong kind key) or more than one (never
guesses) logs a WARN and returns `null`; so does a partial result page
(`pageInfo.totalCount` larger than the entries returned, so other matches may
sit on an unread page) and any query failure. A response with no usable
`totalCount` (`pageInfo` absent, `totalCount` absent, non-numeric or
negative) is trusted as complete and its single visible match is returned
(the server filters by kind and the default `pageSize` is 1000). Look the
singleton up every cycle and do not cache its id across cycles, as in the
sample above. A singleton that was deleted and recreated (pak reinstall,
admin delete) gets a new id, and clearing a cached id only when `addChild`
returns `false` does not catch that: the add is asynchronous, so a POST to
the deleted parent's id may be accepted (2xx) and dropped later, leaving the
stale id cached for the life of the collector while the adapter logs success
every cycle. The lookup is one GET against the local Suite API, so repeating
it each cycle costs nothing worth saving. `ForeignResourceResolver` is not used for
this: its `ResourceEntry` carries no Suite API UUID (it yields SDK
`ResourceKey`s for the SDK relationship route).

**Which relationship route.** Edges the adapter reports in its own collect
result go through `RelationshipBuilder` (own parent: `setRelationships`, full
set per parent; foreign parent: additive). A parent shared across adapter
instances, linked by each instance to its own child, goes through
`addChild`. Whether an SDK full set emitted for the same parent removes
children added through the Suite API is unverified; do not mix the two
routes on one parent until a live install shows it is safe.

Empirical basis: `knowledge/context/investigations/suiteapi_ambient_auth_devel_2026_06_09.md`
(devel 9.0.2 + prod 9.1 confirmation). Remote-collector caveat documented in that file.

## Changelog

| Date | Change |
|---|---|
| 2026-10-24 | **Compile matrix: one leg per supported line at its own Java, the 8.18.7 leg, several compat jars, `--release 11` for what ships (issue #252, RULE-019).** The shipped compile (framework and adapter, `build-framework.sh` primary) uses `javac --release 11` instead of `-source 11 -target 11`, so a Java 12+ library call fails the build instead of throwing `NoSuchMethodError` on the 8.18 collector (OpenJDK 11). It found one: `ManagedHttpClient`'s DNS round-robin retry copied the request with `HttpRequest.newBuilder(HttpRequest, BiPredicate)` (Java 16); it now copies field by field with Java 11 API in the package-private `ManagedHttpClient.copyWithUri` (method, body publisher, headers, timeout, version, expect-continue; the JDK's restricted headers Host, Connection, Content-Length, Expect and Upgrade are skipped, since the client derives them), covered by `adapter_framework/test/.../http/ManagedHttpClientCopyTest.java`, which `tests/managementpacks/test_managed_http_client_copy.py` compiles with `--release 11` and runs. That was the only call site `--release 11` flagged across the framework and the compliance, unifi and synology sources. Then the same main source (never tests) compiles once per supported line, nothing kept: 8.18.7 (`vrops-adapters-sdk-8.18.7.jar`, `--release 11`), 9.0 (the 2.2 jar again, `--release 17`) and 9.1.1.0100 (`--release 25`). Each leg's `--release` is its line's collector Java, read from the jar's class files, so each line's own class library is checked (a Java 17 or 25 removal, and `[removal]` warnings such as `ThreadDeath` on the 25 leg), on a JDK at least that new found per leg. A supplied jar is matched to its line by sha256 (`_SDK_COMPAT_LINES`, equal to `adapter_runtime/PROVENANCE.md`, test-checked). Every line is expected: one no supplied jar covers prints the SKIPPED box and fails a `--require-sdk-compat` run, unless `VCFCF_SDK_COMPAT_LEGS` (comma list of `8.18.7`, `9.0`, `9.1.1.0100`) narrows the set. Every leg runs after one fails; a missing symbol owned by `java.*`, `javax.*` or `jdk.*` is reported as not in the Java N class library, anything else against the jar. `--sdk-compat-jar` repeats (factory CLI and the kit), `VCFCF_SDK_COMPAT_JARS` is its env form, the one-jar `VCFCF_SDK_COMPAT_JAR` still works, all add up. The one-primary-SDK-jar check stays. `build-framework.sh` runs the legs whenever python3 can import the package (the 2.2 jar is the 9.0 leg) and still builds without python3, skipping them loudly. Factory CI `sdk-compat` has three rows (8.18.7 on JDK 17, 9.0 on JDK 17, 9.1.1.0100 on JDK 25), each fetching its jar from the private sdk-runtime repo (all three are there; `SDK_RUNTIME_SSH_KEY` is set), checking its hash against PROVENANCE.md, and running required with `VCFCF_SDK_COMPAT_LEGS` set to its own line. Measured 2026-10-24: compliance with all three legs required passes (JDK 17 for 8.18.7 and 9.0, Temurin 25.0.5 for 9.1.1.0100); the 25 leg shows the `ThreadDeath` `[removal]` warning; `java.rmi.activation` and `Runtime.traceInstructions` pass the 8.18.7 leg and fail the 9.0 leg as Java 17 library misses. **Versioning:** `BUILDKIT_VERSION` `1.0.18` (merge order: installer/shims branch 1.0.16, adapter-framework designs 1.0.17, this third); #242's fail-on-`[removal]` gate is ported into the per-leg code when the installer branch reaches main. **Adapter adoption:** every Tier 2 pak needs a rebuild on 1.0.18 for the `ManagedHttpClient` fix to reach an 8.18 collector; the framework and all seven Java paks compile clean with `--release 11` against 2.2 and 8.18.7 (framework review measurement; this branch measured compliance, unifi and synology). Pak CI gets the per-line legs when each pak repo's `build-pak-on-tag.yml` passes the jars (the #250 pattern, template first). |
| 2026-10-24 | **Adapter framework designs: certificate names, Test Connection text, cycle start, connect timeout (issues #185, #206, #205, #221, #222).** Opt-in certificate name checking (#185, #206): new `com.vcfcf.adapter.http.CertificateNames` (ported from compliance `VCenterCertificates`, builds 93 and 94: `nameCheckingContext`, `strictHostnameVerifier`, `secure`, `isNameMismatch`, `expectedHost`, `nameMatches`), `VcfCfAdapter.getPlatformSslContext(String dialledHost)` and `HttpClientBuilder.platformSsl(adapter, dialledHost)`; the platform chain check runs first, unchanged, then a SAN/CN match against the dialled host during the handshake, fail closed on no host; the no-argument forms and the Suite API hop (`openPlatformConnection`, trust-all and ignore-hostname, the loopback exemption) are unchanged. The stale 2026-06-30 claim that `openPlatformConnection` sets a peer-gated strict verifier is marked superseded. Test Connection text (#205): neutral default pointing at the accept dialog and at entering the host by the name on its certificate, naming Allow Insecure SSL only when `describesAllowInsecure(config)` finds the identifier in the pak's describe; a certificate name failure (`CertificateNames.isNameMismatch`, or the no-usable-host refusal `isNoUsableHost`) gets name-specific default text (`certificateNameFailureMessage`: the certificate does not name <host>, enter the host by a name on the certificate) and also goes through the hook (framework review B1); new protected hook `certificateFailureMessage(Throwable, ResourceConfig, String)`; every pak-hook wrapper rethrows a `VirtualMachineError` or a thread kill (`isThreadKill`, matched by class name as in #242; no framework code names the type) and restores an interrupt. Cycle start (#221): protected `onCycleStart()`, default no-op, once at the top of `onCollect` before `needsRediscovery` and discovery, anything but a fatal error logged and the cycle continues; `needsRediscovery` is pinned at exactly once per cycle. Connect timeout (#222): `HttpClientBuilder.connectTimeout(Duration)`, default the `timeout` value, non-positive rejected; `timeout` stays the per-request read budget. New tests `CertificateNamesTest` (235 checks, real wrong-name HTTPS handshakes, and Validate Connection driven through `onTest` against a wrong-name server) and `HttpClientBuilderTest`; `CertificateReviewTest` and `AdapterInstanceStatusTest` extended. **Versioning:** `BUILDKIT_VERSION` bumped to `1.0.17`; reaches paks once `sdk-buildkit-v1.0.17` is tagged and `sdk-buildkit-v1` moves to it. **Adapter adoption:** every change is opt-in or a no-op default, so a rebuild on 1.0.17 changes nothing a pak does except the Test Connection wording for an untrusted certificate (no Allow Insecure advice where the describe has no such field). Compliance can replace `VCenterCertificates.nameChecking` with `getPlatformSslContext(host)` and then drop its rethrow-without-cause workaround in favour of `certificateFailureMessage` (its wrong-name failures reach the hook with `CertificateNames.isNameMismatch` true); unifi and synology opt in to name checking with `platformSsl(this, host)` and move their cycle-start marker from `needsRediscovery` to `onCycleStart()`; synology can set `connectTimeout`. None of this is applied by this change. |
| 2026-10-24 | **Pak install: post-install dashboard checks (issues #244, #200).** `python3 -m vcfcf_managementpacks install` (with the default wait) now checks that each dashboard the pak ships finished building, by the pak's own dashboard ids over `getDashboardList` (a `CUSTOM` dashboard export does not carry pak dashboards), and prints the same `MATERIALIZATION` lines as `vcfcf_dashboards sync`; STALLED exits 3 (installed, post-install check failed), distinct from 1. For each `dashboards.properties` binding it reads the server's Summary copy and prints `SUMMARY OK` / `SUMMARY INCOMPLETE <kind> <copy id> (<n> of <m> widgets loading)` as information. The #200 repair (wait for the source, then bind again) is opt-in, `--summary-rebind` or `VCFCF_SUMMARY_REBIND=1`: on 2026-10-24 compliance 0.0.0.98 showed it refused by the server on 9.0.2 and 8.18.7 (generic Internal Server Error panel, nothing written, exit 3) and not needed on 9.1.1; a refused bind now quotes the HTTP status and a redacted 200-character excerpt of the answer. Cause of the refusal is open. Not in the buildkit (the installer is factory-only), so no `BUILDKIT_VERSION` change. **Adapter adoption:** none; operators of 9.0.2 and 8.18.7 bind the Summary dashboard by hand after the source finishes until #200 is resolved. |
| 2026-10-24 | **The framework no longer references `java.lang.ThreadDeath` (issue #242).** `VcfCfAdapter.certificatePromptAvailable` caught `VirtualMachineError | ThreadDeath` to rethrow them; `ThreadDeath` is deprecated for removal on JDK 20+ and the 9.1.1 collectors run Java 25. The catch is now `VirtualMachineError`, plus a new `isThreadKill(Throwable)` that matches the class by the name `java.lang.ThreadDeath`: Java 17 collectors still rethrow a thread kill, the JDK 25 compile has no reference to the type, and a JDK without the class never matches (its `Thread.stop` throws `UnsupportedOperationException`). An `InterruptedException` from the pak's `certificateCheckUrls` hook now restores the thread's interrupt status before answering "no prompt". `AmbientCredential`'s javadoc names the type with `{@code}`, not `{@link}`. The compat pass gains the expectation: `check_framework_sdk_compat` (framework source only, `build-framework.sh` and factory CI) fails on any javac `[removal]` warning; the framework + adapter pass in `build-sdk` / `validate-sdk` still only prints them, so no pak is newly gated. New tests: `CertificateReviewTest` thread-kill and interrupt cases (the error is created reflectively), and in `tests/managementpacks/test_sdk_compat_target.py` the removal gate (real javac 17 with `new Integer(int)`) plus a source guard that no framework code names `ThreadDeath`. Verified locally on 2026-10-24: on JDK 17 the framework compiles and CertificateReviewTest passes 95/95 (VcfCfAdapterTest 79/79); the required compat pass (`check_framework_sdk_compat`, javac 25.0.5, the 9.1.1.0100 jar from the holding share, sha256 `79f7b123...` matching `adapter_runtime/PROVENANCE.md`) passes on this source and fails on the previous one at `VcfCfAdapter.java:2352: warning: [removal] ThreadDeath`. In CI the `sdk-compat` job still skips until issue #250 lands. **Versioning:** `BUILDKIT_VERSION` `1.0.16` (the kit carries the framework source and `sdk_builder.py`). **Adapter adoption:** a rebuild on 1.0.16 picks it up; no source change needed. |
| 2026-10-23 | **Second SDK compile target: the 9.1.1.0100 jar (issue #211).** `adapter_runtime/vrops-adapters-sdk-9.1.1.0100.jar` sits beside the 2.2 jar, which stays the shipped compile target. The jar is not committed (the public repo keeps Broadcom jars out) and not yet in the private `vcf-content-factory-sdk-runtime` repo: it is parked on the lab holding share at `/mnt/holding/vendor/vcf-ops-9.1.1.0100/extracted-jars/` (local-only); the upload to the private repo and the factory secret are issue #250, and until then the factory CI job skips. Provenance and the OVA extraction chain: `adapter_runtime/PROVENANCE.md`, the one tracked file in that gitignored directory. After the primary compile, `build_sdk_pak` and `validate_sdk_project` compile the framework source plus the adapter source against it (primary SDK jar and `vcfcf-adapter-base.jar` off that classpath; the rest unchanged), and `build-framework.sh` does the same for the framework (new `--compat-only` mode for CI, no 2.2 jar needed). Nothing from the pass ships: compliance built with and without it carries 157 byte-identical classes. Any unresolved class or member fails the build or validate, naming it. The jar's class files are Java 25, so the pass needs JDK 25+, found on PATH, `JAVA_HOME`, the `JAVA_HOME_<N>_<ARCH>` variables `actions/setup-java` exports, `/usr/lib/jvm/*` and friends, or `VCFCF_SDK_COMPAT_JAVAC`; without the jar or the JDK the pass is skipped with a boxed warning (plus a `::warning::` annotation on a `--release` build under GitHub Actions), and `VCFCF_SDK_COMPAT_REQUIRED=1` / `--require-sdk-compat` turns that into a failure. `build-framework.sh` skips in the shell when no jar is present (no python3 needed) and exits 3 when the pass could not run, 1 when it ran and failed. New flags on `build-sdk` and `validate-sdk` (factory CLI and the kit): `--sdk-compat-jar` (`VCFCF_SDK_COMPAT_JAR`) and `--require-sdk-compat`. The primary compile now takes exactly one SDK jar: any second `vrops-adapters-sdk*.jar` in `adapter_runtime/` or its `lib/`, under any name (the appliance's is plain `vrops-adapters-sdk.jar`), stops the build naming it, because on the merged classpath it would resolve classes one target lacks and hide the drift. Factory CI: new `sdk-compat (9.1.1.0100)` job (GitHub-hosted, JDK 25, hash-pinned Python deps): clones the private sdk-runtime repo with the `SDK_RUNTIME_SSH_KEY` deploy key, checks the jar's sha256 against `adapter_runtime/PROVENANCE.md`, runs the pass required; without the secret (forks, and this repo until issue #250 lands) it skips with a notice, so today it checks nothing. **Versioning:** `BUILDKIT_VERSION` `1.0.15` (1.0.13 went to the defect-gate round, PR #246, and 1.0.14 to the adapter-framework round, PR #248). **Adapter adoption:** no source change needed (the framework and all seven Java paks pass, 2026-10-23). Pak builds get the pass only after each pak repo's `build-pak-on-tag.yml` adopts the flags, JDK 25 and the jar (blocked on issue #250); until then every tagged pak release skips it, with the warning and annotation above. |
| 2026-10-23 | **Adapter framework round: logging, Suite API client, account status, version stamp (issues #192, #201, #214, #217, #223, #224, #227, #228).** `SuiteApiStitchClient` no longer logs the principal or puts it in exception messages (#227); `pushStats` / `pushProperties` failures are one WARN line per call with the trace at DEBUG, an unexpected exception class shows its trace at WARN only the first time per client and operation, and an interrupt restores the thread flag (#192); a non-2xx GET throws `SuiteApiHttpException` with the status, the `apiErrorCode` and a body excerpt, and `get(path, accept)` sets the Accept header per call (#201); `close()` / `discard()` mark the client closed so it never acquires a token again (#217). `componentLogger` raises a logger to INFO only when INFO is not enabled, so an operator's DEBUG survives repeat lookups (#224), and names a class outside the adapter's package as a child of the adapter class (`<adapter class>.SuiteApiStitcher`), so framework helper lines reach the per-instance log at the adapter's level (#228; cause read from SDK bytecode and reproduced against the real SDK logger factory, live Cloud Proxy check owed). A completed cycle in which every collected resource failed, or there was nothing to collect and discovery failed, sets the adapter instance (the account row) to ERROR or DOWN with a one-line reason (#223). `vcfcf-adapter-base.jar` carries `Implementation-Title`, `Implementation-Version` and `X-Vcfcf-Source-Commit` from both build paths (the kit gains a `SOURCE_COMMIT` file), `build-sdk` prints them and each instance logs them once at first configure (#214); new guard test against JVM-wide setters. New tests: `SuiteApiStitchClientTransportTest`, `ComponentLoggerTest`, `AdapterInstanceStatusTest` (all SKIP without log4j on the runtime classpath; add `adapter_runtime/lib/*`), `LogCapture` helper, `VcfCfAdapterTest` manifest cases, `tests/test_adapter_framework_no_jvm_wide_state.py`, stamp cases in `tests/test_sdk_builder_framework_jar.py`. Found and recorded, not changed: the framework validates child statuses against the adapter-instance list, so ERROR or DOWN on a child never reaches the platform. **Versioning:** `BUILDKIT_VERSION` `1.0.14` (1.0.13 went to the defect-gate round, PR #246); reaches paks once `sdk-buildkit-v1.0.14` is tagged and `sdk-buildkit-v1` moves to it. **Adapter adoption:** every Tier 2 pak needs a rebuild on buildkit 1.0.14; no source change is required. Visible after the rebuild: framework helper lines appear in the instance log under the adapter class's name (update any log grep that keys on `com.vcfcf.adapter.stitch`), an account whose every resource fails shows ERROR instead of Collecting, and the instance log names the framework version at configure. Optional pak follow-ups: Synology can drop its `principal=` redaction rule; compliance and vcommunity can read `SuiteApiHttpException.getApiErrorCode()` (1501) instead of treating every 400 or 404 as an absent configuration file, and use `get(path, "*/*")` for it. |
| 2026-10-23 | **The kit ships the RULE-012 defect gate (issue #226).** New `sdk_buildkit/defect_gate.py`: `src/vcfcf_packaging/defects.py` verbatim behind a generated comment header (`kit_defect_gate_source()` in `buildkit.py`), runnable as `python3 sdk_buildkit/defect_gate.py --pak <name> --registry <defects.md> [--require-registry]`, exit 0 clean, 1 unusable registry, 2 refused. It replaces the drifted fork the sdk-template vendors as `ci/defect_gate.py`: the factory module adopted that fork's fail-closed parsing (disguised, code-indented and fenced DEF headings open a malformed entry instead of bleeding fields into the previous one; fenced lines are description; nested, code-indented, blockquoted and repeated fields are malformed; comma, backtick and edge-punctuated `Affects:` are malformed and fail closed for every pak they name; trailing text after a well-formed id is tolerated, as in the fork; BOM ignored; matching case-insensitive) inside RULE-012's per-entry isolation, and `--require-registry` (required in CI, the generated header says so) restores the fork's refusal on an absent registry or one with no valid entry, for CI that fetched it on purpose. The two looser divergences from the fork are both RULE-012: without the flag an absent, empty or unreadable registry warns and passes, and a malformed entry does not block a pak it does not name. One is stricter: an edge-punctuated `Affects:` (`synology.`) refuses the pak it names, where the fork matched nothing. `tests/test_defect_gate_parity.py` runs one fixture matrix, ported from the template's `tests/ci/test_defect_gate.py`, against the module and the defect_gate.py extracted from an assembled tarball. **Versioning:** `BUILDKIT_VERSION` bumped to `1.0.13` (not yet tagged); the adapter-framework round (PR #248) took `1.0.14` and the 9.1.1 compile target (PR #251) `1.0.15`. **Adapter adoption:** none forced; pak CI keeps its vendored copy until each pak repo switches its gate step, which is a separate decision (issue #226). |
| 2026-10-23 | **Docs include, `content_naming`, SCG normalizer fix-ups by `control_id` (#171, #229, #169, #170).** `docs_gen` merges an adapter's optional `docs/_index_extra.md` into the generated index (see "Generated docset" above). `adapter.yaml` gains `content_naming` (`factory_prefixed` default, or `unprefixed`), enforced by `validate-sdk` and `build-sdk` when declared and a warning when absent (see "Bundled content naming" above). The factory SCG normalizers (`scripts/normalize_scg_v8.py`, `normalize_scg_v9.py`) share one pipeline whose scoring fix-ups are keyed by `control_id`, and `vm.virtual-hardware` is emitted in the `vmx-N or newer` minimum form for SCG 8.0 and 9.0. That floor comes from the ingested source's Baseline Suggested Value column (`vmx-21` for 8.0, `vmx-19` for 9.0, from vendor revisions 803-20260107-01 and its 9.0 counterpart); newer vendor revisions (803-20260612-01, 902-20260612-01) lower it to `vmx-17 or higher`, which arrives unchanged once the compliance repo re-ingests them. **Versioning:** `BUILDKIT_VERSION` not bumped here; the `content_naming` check reaches paks with the next buildkit tag. **Adapter adoption:** the three vCommunity paks should declare `content_naming: unprefixed`; the compliance repo regenerates its 8.0 and 9.0 canonical profiles. |
| 2026-10-18 | **FIPS Suite API transport mirrors the vendor `useClusterTruststore` (issue #215).** `openPlatformConnection` detects FIPS by `IS_FIPS` only (vendor `Constants.FIPS_MODE_ENABLED`; `-Dorg.bouncycastle.fips.approved_only` is a diagnostic, not a signal) and in FIPS mode builds the socket factory the vendor `vcops-suiteapi-client` builds for `SSLOptions(VROPS_CLUSTER)`: `$STORAGE/vcops/user/conf/ssl/secure-communications.properties`, keys under `inter_cluster.` then `default.`, `store_type`/`protocol`/`algorithm` from the file, encrypted-first passwords with the `%truststore_password%` redirect to `storePass.properties` (`.encrypted` first), `%VAR%`/`$VAR` path substitution, optional client keystore, `TLS_RSA*` filtered and every socket restricted to the configured protocols and cipher suites; hostname ignored. This replaces the stopgap that fell through to trust-all. Any unreadable or incomplete input fails the connection loud (one WARN per instance, path and key named, exception class only), never trust-all. The factory is cached per instance and rebuilt when an input file's modification time or size changes. Non-FIPS branch unchanged and reads no cluster file. New package-private `applySuiteApiTransport` (the dispatch), `applyClusterTruststoreTransport`, `resolveClusterSslOptions`, `buildClusterSocketFactory`, `ClusterSocketFactoryCache`, `RestrictedSslSocketFactory`, `isFipsModeEnabled`, `clusterSslDirectory`, `describeTransportMode`; `isFipsApprovedOnly` removed. `VcfCfAdapterTest` (69 checks) covers the dispatch both ways, resolution order, sentinels, substitution, cipher filter, protocol restriction, client keystore, the cache and every failure input, with real TLS handshakes; mutation-checked (trust-all fallback, ignored flag, `approved_only` detection, plain-first passwords, nested prefixes, no cache refresh, no socket restriction, no cipher filter all fail the suite). Vendor bytecode and jar provenance: `knowledge/context/api-surface/casa-injected-vs-raw-client.md` §3. **Versioning:** `BUILDKIT_VERSION` bumped to `1.0.12`; paks build from the floating `sdk-buildkit-v1` tag, so the fix reached paks from `sdk-buildkit-v1.0.12` (tagged 2026-10-19 at `4ce6d2b`). **Adapter adoption:** every Tier 2 pak needs a rebuild on buildkit 1.0.12. |
| 2026-10-18 | **build-sdk rejects a one-child composite SymptomSets; dashboard advisories in the kit.** `build_sdk_pak` (and so `sdk_buildkit build-sdk --release`) and `validate-sdk` now fail on any describe.xml `<SymptomSets>` with fewer than two children, naming the AlertDefinition id: VCF Operations rejects the whole describe at install and the controller rolls back (compliance build 90, issue #203). The kit ships `dashboard_widget_versions.py` for the per-widget minimum Ops version warning (issue #199), and bundled dashboards now warn on names over 50 characters (issue #198) and on a Section widget; both are warnings, printed once per dashboard. **Versioning:** `BUILDKIT_VERSION` 1.0.12. The #203 guard reaches tagged pak releases from `sdk-buildkit-v1.0.12` (tagged 2026-10-19 at `4ce6d2b`, with `sdk-buildkit-v1` moved to it). **Adapter adoption:** none needed; no shipped describe.xml trips the check. |
| 2026-10-02 | **Suite API relationship add + singleton id lookup.** `SuiteApiStitchClient` and the `SuiteApiStitcher` facade gain `addChild(String parentResourceId, String childResourceId)` and `addChildren(String parentResourceId, Collection<String> childResourceIds)` (both return `boolean` accepted), issuing the additive `POST /api/resources/{id}/relationships/children` with `{"uuids":[...]}`; no PUT/replace variant is exposed (PUT replaces the whole child list, last-writer-wins across adapter instances). Also `findSingletonResourceId(String adapterKind, String resourceKind)`: returns the one matching resource UUID, `null` with a WARN on zero, more than one, a partial result page (`pageInfo.totalCount` above the entries returned), or failure; kinds trimmed, non-UUID identifiers dropped. Neither throws into the collect cycle. Callers look the singleton up every cycle rather than caching its id (the add is asynchronous, so a POST to a deleted singleton may be accepted and dropped later, and a cache cleared only on `false` would hold the stale id forever); a `true` from `addChild` means "request accepted", not "linked". An absent or unusable `pageInfo.totalCount` is trusted as complete. Known limitation: no remove (`deleteRelationship`) is wrapped, so edges outlive a shrinking scope. `RelationshipBuilder` Javadoc cross-references the new call for parents shared across instances. New test `adapter_framework/test/.../SuiteApiStitchRelationshipTest.java` (scripted fake `HttpURLConnection` behind an `openPlatformConnection` override; transport group needs log4j-api at runtime, SKIPs without it). Driver: `knowledge/designs/sdk-adapters/compliance-environment-computed-metrics.md` Vision item 2. **Versioning:** `BUILDKIT_VERSION` stays `1.0.11` (not yet tagged), so this ships in 1.0.11 provided it merges before that tag; otherwise bump. **Adapter adoption:** additive API, no existing pak changes behaviour; compliance adopts it. |
| 2026-09-25 | **Ops-native accept-certificate flow + `allowInsecure` pulldown.** `VcfCfAdapter` gains `certificateCheckUrls(ResourceConfig)` (protected, default empty, called on an unsaved config) and overrides `getConnectionURLs(AdapterConfig)` to return it, falling back to the SDK default when empty, so a pak that does not opt in behaves exactly as before (`NOT_SUPPORTED`, no dialog). An opted-in pak makes Validate Connection show VCF Operations' "Review and accept certificate" dialog for an untrusted target; accepted certs land in the instance `CustomTrustManager` that `platformSsl(this)` already uses. `getCertificateRenewalUrls()` is deliberately not overridden (renewal protocol is VCF-only; see SSL above), so DEF-005's harmless "renewal url set is empty" log line remains. `onTest` now replaces a raw `certificate_unknown(46)` / PKIX failure with a readable message (hook consulted only after a trust failure is detected). New `parseAllowInsecure(String)`, `parseAllowInsecureLegacyNotFalse(String)`, `isAllowInsecure(ResourceConfig)`, `isAllowInsecureLegacyNotFalse(ResourceConfig)`, `ALLOW_INSECURE_IDENTIFIER`. `scaffold-sdk` now emits a framework-v2 skeleton (the old one used the removed aria-ops-core API) with the `allowInsecure` pulldown and a `certificateCheckUrls` override, and derives the class name with `removeprefix` (was `lstrip`). New test `adapter_framework/test/.../CertificateReviewTest.java`. **Versioning:** `BUILDKIT_VERSION` is not bumped here; buildkit 1.0.11 (from `fix/pipeline-hardening-round`) is tagged only after both that branch and this one are merged, so this change ships in 1.0.11. **Adapter adoption:** per-pak table under SSL above. |
| 2026-08-17 | **`insecureSslContext()` hostname-verification fix (issue #82)**: the trust-all manager in `VcfCfAdapter.insecureSslContext()` is reimplemented as `javax.net.ssl.X509ExtendedTrustManager` (no-op `Socket`/`SSLEngine` overloads added for both `checkClientTrusted`/`checkServerTrusted`) instead of the legacy `javax.net.ssl.X509TrustManager`. Root cause: JSSE silently wraps a legacy `X509TrustManager` in `sun.security.ssl.AbstractTrustManagerWrapper`, which re-applies the endpoint identity (hostname) check whenever an endpoint identification algorithm is set. `java.net.http.HttpClient` always sets one, so a user with "Allow Insecure SSL" ticked still got a hostname-mismatch failure (live report against the Synology pack). Measured: this is **not** `HttpClient`-only. It also disables hostname verification on the `HttpsURLConnection` transport, including when the caller uses the JDK's own default `HostnameVerifier` (`HttpsClient` sets an endpoint identification algorithm whenever the verifier in effect is the default one, at which point JSSE decides the outcome instead of the verifier). No non-opt-in caller reaches the changed code (every caller gates on `allowInsecure` or is the vendor-mirror Suite API hop, which already sets an all-true `HostnameVerifier` regardless). Method signature/visibility unchanged; `getPlatformSslContext()` / the TOFU path untouched. `HttpClientBuilder.allowInsecure(boolean)` javadoc corrected to say it disables both chain validation and hostname verification. `SuiteApiStitchClient` keeps `openPlatformConnection()`/`HttpsURLConnection`, not because `HttpClient` still cannot express an unconditional all-true hostname posture (it now can, after this fix), but because matching the vendor `aria-ops-core SuiteAPIClient` transport byte-for-byte remains the goal (DEF-005 "mirror BC exactly"); see the corrected class javadoc and `knowledge/lessons/suite-api-stitch-ssl-tofu-vs-java-http.md`. Regression test added (`VcfCfAdapterTest`): real TLS handshake over `HttpClient` against a hostname-mismatched cert generated fresh per run via `keytool`, asserting `insecureSslContext()` succeeds and a normal validating context fails with the specific `SSLHandshakeException`/`CertificateException` identity failure (not merely "some exception"). `vcfcf-adapter-base.jar` rebuilt. **Adapter adoption:** rebuild and re-release synology, unifi, and compliance (the three paks confirmed on the affected `HttpClient`-transport pattern); the sdk-buildkit tarball must be republished first. |
| 2026-06-10 | **`setRelationships` on foreign resource is per-adapter scoped (9.0.2 proven)**: synology build-16 devel install confirmed the wld01 iSCSI VMWARE Datastore retained all 22 VMWARE-collected children (HostSystem/VM/Pods/etc.) while gaining the SynologyIscsiLun child edge — closing synology-build-16 WARNING-1. Full-set `parentForeign`+`build()` is safe against foreign parents; no delta/labeled workaround needed. 9.1 unverified (open residual). See "setRelationships on a foreign resource" authoring contract note above and `knowledge/lessons/setrelationships-foreign-adapter-scoped.md`. |
| 2026-06-10 | **Per-adapter log file appender detaches on hot-reload**: appender re-wires after first configure cycle completes post-reload; `collector.log` is authoritative during the gap. Collector restart eliminates the gap. See Logging authoring contract note above and `knowledge/context/framework_v2_migration.md` §15. |
| 2026-06-10 | **Multi-resource collect idiom documented** (synology build 14 exemplar): per-cycle snapshot cache pattern, `synchronized currentSnapshot()` thread-safety contract, topology-anchored-on-World relationship emission, and honesty requirement for failed refresh. See `knowledge/context/framework_v2_migration.md` §18. |
| 2026-06-10 | **`componentLogger(Class)` public accessor added (task #15, shadow-logger footgun)**: `VcfCfAdapter.componentLogger(Class<?> component)` is now a `protected` method that returns a `Logger` handle wired identically to the base's own private `adapterLogger()`: same factory, same `setLevel(INFO)` discipline, same `(instanceId) className` naming that routes to the adapter instance's file appender. Adapter subclasses must never shadow `adapterLogger()` or hand-roll a logger handle via `getAdapterLoggerFactory()`. The correct pattern is `componentLogger(HelperClass.class)` in `configureAdapter()`. `SuiteApiStitcher` Javadoc examples updated to use `componentLogger`. Visibility rule and migration note documented in `knowledge/context/framework_v2_migration.md` §15. `vcfcf-adapter-base.jar` rebuilt (clean, SDK-only). **Adapter adoption for synology/unifi:** both adapters must replace any shadow `adapterLogger()` methods and all `getAdapterLoggerFactory().getLogger(cls)` call sites with `componentLogger(cls)` before their v2 migration builds. Compliance (build 46) has no framework-method shadow to remove: its `adapterLogger()` shadow is in `ComplianceAdapter.java` and is the target of the pending compliance v2 fixup. **(Superseded 2026-08-26: that shadow was removed in build 49, `eba91b2`; `ComplianceAdapter.java` now uses `componentLogger(...)` throughout.)** |
| 2026-06-30 | **`SuiteApiStitchClient` unified transport (Change 3: retire `java.net.http.HttpClient` from Suite API path)**: `openPlatformConnection` is now peer-gated and self-contained: loopback peers get an all-true hostname verifier, non-loopback peers get JDK strict (no override), fail-closed on `getByName` failure. *(Superseded, corrected 2026-10-24 per issue #206: the peer gate was removed when DEF-005 closed; `openPlatformConnection` now sets an all-true `HostnameVerifier` for every peer, loopback or not, mirroring the vendor client. No framework path checked a target certificate's name until the opt-in `getPlatformSslContext(String)` of buildkit 1.0.16.)* ALL Suite API HTTP calls (ambient loopback AND explicit/remote CP) now go through `openPlatformConnection`; `java.net.http.HttpClient` + `insecureSslContext()` are retired from this path. `SuiteApiStitchClient` fields `rawHttpClient` and `isLoopback` removed; `adapter` is now always required. `isLoopbackUrl` is informational-only (builder INFO log). Unit test extended to 18 assertions covering the non-loopback strict-verifier branch. `vcfcf-adapter-base.jar` rebuilt. **Adapter adoption:** rebuild all stitching paks. |
| 2026-06-30 | **`SuiteApiStitchClient` loopback transport fix (prod `certificate_unknown(46)`)**: `java.net.http.HttpClient` performs hostname verification against the cert SAN independently of the trust manager and cannot accept a custom `HostnameVerifier`. On production appliances whose operator-replaced cert has no `localhost` SAN (standard org-PKI practice), the loopback Suite API call fails with `certificate_unknown(46)` — devel's stock VCOps self-signed cert has `localhost` in the SAN and hid this. Fix: added `VcfCfAdapter.openPlatformConnection(String)` (SSL integration section) — an `HttpsURLConnection` wired with `AdapterBase.getSocketFactory()` (the platform `CustomSSLSocketFactory`, which carries the TOFU-survival intercept for unknown certs) and an all-true hostname verifier. Do NOT use `getAdapterTrustManager()` here — it is the strict TOFU `CustomTrustManager` (always throws for unknown certs; vanilla JSSE factory drops the intercept and reproduces a PKIX failure). `SuiteApiStitchClient` now selects the loopback transport (`openPlatformConnection`, `HttpsURLConnection`) when the resolved Suite API host is a loopback address (`InetAddress.isLoopbackAddress()` — not the string `"localhost"`), and keeps the explicit/remote path (`java.net.http.HttpClient`) for non-loopback URLs. Token lifecycle also brought to spec: cached per instance, lazy acquire, single retry on 401, released on `discard()`. `getPlatformSslContext()` javadoc corrected (body uses `getAdapterTrustManager()`, not `getSocketFactory()`). `VcfCfAdapter.insecureSslContext()` remains defined but is no longer the loopback Suite API transport path. Unit test added (`adapter_framework/test/`). `BUILDKIT_VERSION` bumped to `0.2.1`. **Adapter adoption:** rebuild all stitching paks against the updated buildkit. See `knowledge/designs/suite-api-stitcher-tls-auth-cleanup-v1.md` and `specs/20-suiteapi-client-behavioral-contract.md` §5. |
| 2026-06-10 | **`SuiteApiStitchClient` SSL fix — trust-all for localhost Suite API (bug #3)**: `SuiteApiStitchClient.Builder.build()` was calling `adapter.getPlatformSslContext()` which wraps `CustomTrustManager`. `CustomTrustManager.checkServerTrusted()` throws `CustomCertificateException` unconditionally for any unknown cert (including the platform's own self-signed localhost cert), then fires `handleUnknownCertificate` as a side-effect notification. `java.net.http.HttpClient` receives the exception directly — no intercept, no retry — resulting in `SSLHandshakeException`/"PKIX path building failed" every cycle (credentials resolved correctly; SSL was the only failure). Fix: replaced `getPlatformSslContext()` with `VcfCfAdapter.insecureSslContext()` in the stitch client's SSL block. Trust-all is appropriate for the localhost Suite API endpoint (loopback isolation, platform's own self-signed cert). Does not affect `HttpClientBuilder.platformSsl(this)` for target-system connections. **Adapter adoption:** none — rebuild against updated `vcfcf-adapter-base.jar` only. See `knowledge/lessons/suite-api-stitch-ssl-tofu-vs-java-http.md`. |
| 2026-06-10 | **`onDescribe()` controller-side NPE fix (build 44 root cause)**: `VcfCfAdapter.onDescribe()` was calling `getAdapterKind()` which returns null during controller-side bare instantiation (no platform injection). Fix: added `private final String adapterKindKey` field + two keyed constructors (`VcfCfAdapter(String adapterKindKey)` and `VcfCfAdapter(String adapterKindKey, String adapterDir, Integer instanceId)`). `onDescribe()` now resolves kind from `adapterKindKey` first, falls back to `getAdapterKind()`, and throws an actionable message listing both sources if both are null — never reaches `getAdapterDescribeFile(null, …)`. **Adapter adoption required:** subclass constructors must call the keyed super variants (see `knowledge/context/framework_v2_migration.md` §3). `vcfcf-adapter-base.jar` rebuilt (clean, SDK-only). Lesson codified: `knowledge/lessons/controller-describe-bare-instantiation.md`. |
| 2026-06-09 | **Framework default `onDescribe()`**: `VcfCfAdapter.onDescribe()` is now provided by the framework. Loads `describe.xml` via `getAdapterDescribeFile(getAdapterKind(), "describe.xml")`; throws `RuntimeException` with path in message on failure (no silent null). Subclass overrides still win (non-final). Tracked gap in `knowledge/context/framework_v2_migration.md` §3 closed. `vcfcf-adapter-base.jar` rebuilt (clean, SDK-only). Existing adapters (compliance) that hand-roll `onDescribe()` continue to work without change — their override takes precedence. |
| 2026-06-10 | **AmbientCredential path-resolution bug fix**: `CommonConstants.VCOPS` (`"VCF Ops"` — a display name, not a path) removed from path derivation. New resolution order: system property `vcfcf.suiteapi.credential.path` → hard-wired default `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`. Failure message now lists all candidates tried. `vcfcf-adapter-base.jar` rebuilt (clean, SDK-only). Compliance needs pak rebuild only — no adapter source change. |
| 2026-06-09 | **Ambient Suite API transport**: `AmbientCredential`, `SuiteApiStitchClient`, `SuiteApiStitcher` added to `com.vcfcf.adapter.stitch`. Adapters opt in via `SuiteApiStitcher.create(this, logger)`. FIPS constraint documented: use SDK `Crypt` only. |
| 2026-06-09 | **v2 rehome**: `VcfCfAdapter` now extends `AdapterBase` directly. `aria-ops-core` (`com.vmware.tvs.*`) eliminated from compile classpath and runtime. New SPI: `VcfCfTester`, `VcfCfDiscoverer`, `VcfCfCollector` (all under `com.vcfcf.adapter.spi`). `RelationshipBuilder` rebuilt on SDK `Relationships` API. `ForeignResourceResolver` decoupled from TVS via `SuiteApiBridge` functional interface. `HttpClientBuilder` default SSL changed to platform trust store. `MetricPusher.property()` bug fixed (was using `isProperty=false`). Build script narrowed to SDK jar only. See `knowledge/context/framework_v2_migration.md` for adapter migration guide. |
| 2026-05-19 | Pak format hard-won lessons documented after 42 install attempts. |
| 2026-05-16 | Pass 23 field evidence added to spec/01. Per-instance single-thread collect confirmed. |

## SDK jar by platform version (read 2026-10-13)

| Source | Jar | sha256 (12) | Notes |
|---|---|---|---|
| devel 9.0.2.0 build 25137845 | `common/lib/vrops-adapters-sdk.jar` and 20+ copies under packs, controller and tomcat | 2d53a91fc2b9 | 1,002,682 bytes; manifest carries no version; Apache Maven 3.3.9, JDK 17.0.16 |
| factory `adapter_runtime/vrops-adapters-sdk-2.2.jar` | the buildkit's compile target | 2d53a91fc2b9 | byte-identical to devel's |
| prod 9.1.1 (both nodes) | `common/lib/vrops-adapters-sdk.jar` and 31 copies, one named `vrops-adapters-sdk-9.1.1.0.jar` | 9e905f1a5164 | 1,001,089 bytes; Maven JAR Plugin 3.5.0, Java-Version 25; 512 entries vs 518 |
| Aria Operations 8.18.7 build 25423534 (devel_8_18 node, same bytes on its Cloud Proxy), read 2026-10-24 | `/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar` (and the identical `-1.0.jar`); factory name `vrops-adapters-sdk-8.18.7.jar`, the 8.18 compat leg at `--release 11` (issue #252); binary not committed (never commit it to this public repo); in the private `vcf-content-factory-sdk-runtime` repo (its PRs 7 and 8, merged 2026-10-24), where factory CI's `sdk-compat (8.18.7)` row fetches it; lab copy on the holding share at `/mnt/holding/vendor/vcf-ops-8.18.7/extracted-jars/` (local-only); provenance in `src/vcfcf_managementpacks/adapter_runtime/PROVENANCE.md` | 45d54c6403ac | 965,383 bytes; 471 classes, class major 55 (Java 11), any JDK 11+ reads it; the collector and Cloud Proxy run OpenJDK 11.0.30; lacks 11 members 2.2 has (AdapterBase 2, CustomTrustManager 7, AdapterDescribe 2), adds none |
| 9.1.1.0100 build 25795063 (devel_9_1's build), from the appliance OVA, read 2026-10-23 | `common/lib/vrops-adapters-sdk.jar` (and the identical `-1.0.jar`) in `vmware-vcops-9.0.0.0-25794169` RPM; extraction chain in `src/vcfcf_managementpacks/adapter_runtime/PROVENANCE.md`; binary not committed (the public repo keeps Broadcom jars out); in the private `vcf-content-factory-sdk-runtime` repo (its PR 7, merged 2026-10-24; issue #250 closed), where factory CI's `sdk-compat (9.1.1.0100)` row fetches it with the `SDK_RUNTIME_SSH_KEY` deploy key; lab copy on the holding share at `/mnt/holding/vendor/vcf-ops-9.1.1.0100/extracted-jars/` (local-only); the 9.1 compat leg at `--release 25` | 79f7b1234090 | 1,001,091 bytes; not the prod 9.1.1.0 bytes (the 0100 patch rebuilt it); Maven JAR Plugin 3.5.0, Java-Version 25, class major 69; 512 entries, same 6 added / 12 removed vs 2.2 as prod |
| all three | `aria-ops-core-8.0.0.jar` | 8743cc28a010 | only inside the Synology MPB adapter's own lib; absent from `common/lib` |

Class delta between the two SDK jars: only in 9.1.1, `LIExtractedFieldDescribe`,
`vcd/CalculationModelDescribe`, `vcd/RecurringChargesDescribe`,
`Legacy{INI,Properties,XML}Configuration`; only in 9.0.2 and ours,
`adapter3/RollUpType`, `Logger$1`, `VcopsLicenseEdition$1`, `CPURateDescribe$1`
and a few `describe/policy/vcd/*Describe` classes. No framework or adapter
source references a class that 9.1.1 dropped. Since buildkit 1.0.15 (issue
#211) that is checked, not assumed: everything that ships is still compiled
against the 9.0.2 jar, and build-sdk, validate-sdk and `build-framework.sh`
compile the same source a second time against the 9.1.1.0100 jar
(`adapter_runtime/vrops-adapters-sdk-9.1.1.0100.jar` or
`VCFCF_SDK_COMPAT_JAR`), keep nothing, and fail on anything unresolved.
Scope: only the SDK jar is swapped. The compat classpath keeps the
9.0.2-era `alive_common.jar` and `alive_platform.jar` (and the pak's own
`lib/`), so their own 9.1.1 drift is not checked; checked 2026-10-23, they
share 0 classes with either SDK jar and provide none of the 12 classes
9.1.1 dropped, so they mask nothing today.
Measured 2026-10-23: JDK 17 javac cannot read the 9.1.1 jar on a classpath
(`class file has wrong version 69.0, should be 61.0`, even with
`-source 11 -target 11`), so the pass needs JDK 25; Temurin 25.0.5 with
`-source 11 -target 11` reads it and reports a reference to the dropped
`adapter3.RollUpType` as `cannot find symbol`. Without the jar or JDK 25 the
pass is skipped with a warning (`VCFCF_SDK_COMPAT_REQUIRED=1` makes that a
failure). The framework and all seven Java paks (compliance, unifi,
synology, vcommunity, vcommunity-os, vcommunity-vsphere, template) pass it
(2026-10-23). JDK 25 also
flags `ThreadDeath` (used in `VcfCfAdapter`'s catch of fatal errors) as
deprecated for removal; it still exists in Java 25, the 9.1.1 collector's
runtime. Jar provenance: `src/vcfcf_managementpacks/adapter_runtime/PROVENANCE.md`.
Since issue #252 the 9.1.1.0100 jar is one of three per-line legs: 8.18.7
(`--release 11`), 9.0 (the 2.2 jar again, `--release 17`) and 9.1.1.0100
(`--release 25`), each at its line's collector Java so each line's own
class library is checked, each on its own JDK. The shipped compile uses
`javac --release 11` rather than `-source 11 -target 11`, so the Java 11
library API is enforced for what ships (the 8.18 collector runs Java 11).
`--release` does not change which class-file versions javac reads on the
classpath, measured 2026-10-24: JDK 17 with `--release 11` reads the 2.2
jar (Java 17), and Temurin 25.0.5 reads the 9.1.1.0100 jar (Java 25) at
both `--release 11` and `--release 25`. With `-source 11 -target 11` the
old 9.1.1 pass checked Java 25's library; `--release 11` on every leg would
have checked only Java 11's, which is why the legs use their own release.
Devel's one outlier is the `VrAdapter` pack's bundled copy (0f2f3a8c5722, a
smaller build). The `2.2` and `1.0` in file names are names, not versions.

### API delta for the classes we use (read 2026-10-13)

Class files: every class in the 9.0.2 jar is major version 61 (Java 17);
every class in the 9.1.1 jar is major 69 (Java 25), so the 9.1.1 collector
runs Java 25 and compiling against the 9.1.1 jar needs JDK 25. Our adapters
target Java 11 bytecode and run on both.

Public API (`javap -public`, JDK 25) of the 22 SDK classes our framework and
the compliance, unifi, synology and vcommunity adapters import: 21 identical.
The one difference is additive: `adapter3.describe.AdapterDescribe` gains
`getDictionaryDir()`, `getLiExtractedFields()` and `setLiExtractedFields(...)`
in 9.1.1. Nothing we call was removed or changed signature.
