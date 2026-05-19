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
Layer 4: Per-adapter code (Claude-generated, ~50–150 lines)
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
| `AuthStrategy` (SPI) + `BasicAuth`, `BearerAuth`, `SessionCookieAuth` | Auth plug-in. SessionCookie is what Synology DSM needs. |
| `RetryPolicy` | Exponential backoff + jitter. Default 3 attempts, retry on 5xx/429/IOException. Required because the platform doesn't retry `collect()` (Pass 23). |
| `MetricPusher` | One-liner helpers: `push(resource).metric(key, value).property(key, value)`. |
| `DescribeBuilder` | Typed builder for describe.xml — covers ResourceKinds, CredentialKinds, Identifiers, Attributes. |

**Explicitly deferred** to future framework versions (don't build
until a second adapter needs them):

- OAuth2 client-credentials with refresh
- Kerberos / SPNEGO, AWS SigV4, mTLS
- Cursor / Link-header pagination
- Cross-MP attachment helpers (`ForeignResources` DSL)
- Relationship fluent builder over the 18-method API
- Action annotation dispatcher
- `<CustomGroupMetrics>`, capacity / policy describe surfaces

## Pak format differences vs Tier 1

| | Tier 1 (MPB) | Tier 2 (SDK) |
|---|---|---|
| `template.json` | Yes (BuilderFile) | No |
| `design.json` | Yes | No |
| `manifest.txt` `adapters:` field | Yes (MPB-runtime adapter) | No (custom adapter JAR is in the pak) |
| Adapter JAR | `mpb_adapter-*.jar` (Broadcom) | `<name>.jar` (we built) |
| `adapter.properties` | Auto-emitted by MPB | We emit from `adapter.yaml` |
| `describe.xml` | Generated by MPB from BuilderFile | Hand-authored or built via DSL |
| Post-install scripts | None (we strip Gen-1 leftovers) | None |
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

## Implementation status

- Phase 1 (framework + tooling skeleton): **COMPLETE** — framework JAR built
  (`vcfcf-adapter-base.jar`), `sdk_builder.py` + `sdk_project.py` written,
  CLI extended (`build-sdk`, `validate-sdk`, `scaffold-sdk`), hello-world
  adapter compiles and produces a correct SDK-format `.pak` in `dist/`.
- Phase 2 (Synology adapter): not started.
- Phase 3 (polish, agent prompts, promotion docs): not started.

Tracking: `designs/tier2-mp-architecture-plan.md`.
