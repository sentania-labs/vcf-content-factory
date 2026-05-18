# MPB → VCF-CF Tier 1 Handoff

**Audience**: VCF-CF Tier 1 implementers.
**Source of authority**: cleanroom RE of `mpb_adapter-9.0.1-patch-1.jar` (the MPB runtime engine, ~15,440 classes, Kotlin) + 3 real-world MPB-built paks (UniFi, phpIPAM, vSAN — designer JSONs and built `.pak`s).
**Date**: 2026-05-16.
**Companion specs** (read these for full enumerations):
- `spec/10-mpb-builderfile-schema.md` — the BuilderFile Kotlin model (Tier 1 runtime vocabulary)
- `spec/11-mpb-designer-wire-format.md` — the designer JSON wire format + pak generation pipeline
- `spec/02-describe-xml.md § MPB-runtime emission` — the 24 Describe* component classes
- `spec/99-summary-and-vcf-cf-recommendations.md` — full synthesis across passes 1-17

This handoff stands alone for the strategic picture. Cross-references are for "I need to look up the exact field" lookups.

---

## TL;DR (10 takeaways)

1. **MPB is a Kotlin code generator that produces Track C-shaped paks** — NOT a declarative Track A pipeline. The "MPB runtime engine" `mpb_adapter-*.jar` is the **template/source** that gets regenerated per-pak with kind-key baked into every package path.

2. **A real MPB-built pak is 22 MB** — not the 226 KB you'd expect for "pure declarative." Each pak carries a ~236 KB generated entry jar + ~60 dependency jars (Kotlin stdlib + Ktor + Jackson + Apache HTTP client + log4j + woodstox + **aria-ops-core**) totaling ~21 MB of `lib/`.

3. **There are TWO JSON formats — don't conflate them**:
   - **Designer wire format** (the `*_MP_Builder_Design.json` the MPB UI exports): richer, structured expression objects with `@@@MPB_QUOTE <partId> @@@MPB_QUOTE` placeholders, captured response samples, HTTP-client config.
   - **Runtime BuilderFile** (shipped inside paks at `<adapter>/conf/design.json`): 1:1 with the Kotlin model in `spec/10`; expressions compiled down to string templates.

4. **aria-ops-core is the canonical SPI** (`Tester` / `Discoverer` / `LiveCollector` / `HistoricalCollector`). Bundled in every MPB-generated pak's `lib/`. Triple-confirmed: BlueMedora marketplace adapters use it, MPB runtime uses it, MPB-built paks bundle it. **VCF-CF's `vcfcf-adapter-base.jar` should adopt this SPI** — same SPI works for Tier 1 and Tier 2.

5. **The Tier 1 expressiveness ceiling is empirically bounded.** A design needs to promote to Tier 2 if it hits ANY of the items in the testable list at § 6 below — VCF-CF can statically determine "Tier-1-expressible" at design-validation time.

6. **Cross-MP attachment is first-class in MPB** — `BuilderHttpExternalResource` + `ariaOpsConf` declares foreign-resource targets; the runtime pushes properties/metrics via `HttpExternalResourcePropertyAdder`. This is the EASY path for "decorate a vSphere VM with my MP's data."

7. **The substitution/expression language is `${...}` templates** with explicit namespaces (`${configuration.X}`, `${authentication.credentials.X}`, `${authentication.basic}`, `${authentication.session.X}`, `${requestParameters.X}`) AND `@@@MPB_QUOTE_<SCOPE>`-marked response/context references. Confirmed marker family: `@@@MPB_QUOTE_BODY` (HTTP-response navigation), `@@@MPB_QUOTE_REQUEST_PARAMETERS` (chaining-context lookup — REQUIRED for `objectBinding.requestMatchIdExpression`, VCF-CF field-confirmed 2026-05-16). Additional markers may exist; treat the list as "at least these," not "only these." **Pass 25 empirical grammar bounds** (54 distinct compiled paths surveyed across UniFi + phpIPAM): the `@@@MPB_QUOTE_BODY` parser supports **pure dot-notation + a single `data.*` top-level array iteration** — NOT JMESPath, NOT Jayway JsonPath. No bracket indexing, no predicate projection (`[?...]`), no pipes, no function calls. Backed by Jackson `JsonNode`. See `spec/11 § Grammar bounds` for the full evidence table + workarounds for "iterate a sibling array by predicate" (recommended: declare a child ResourceKind).

8. **MPB shares iSDK template infrastructure.** Generated `manifest.txt` has un-filled `"display_name": "DISPLAY_NAME"` and `"vendor": "VENDOR"` placeholders — the same placeholders observed in Integration-SDK (Track B) paks. Don't assume these are MPB-specific bugs; they're shared scaffolding.

9. **Pak signing is broken in instructive ways — and the appliance doesn't enforce.** Single self-signed VMware cert signs everything (Broadcom-internal + marketplace re-signed third-party). Cert **expired 2026-01-03** but paks dated 2025-12-30 still ship with it. SHA-1 hashes + sha1WithRSAEncryption + RSA exponent 3. **Pass 23 empirical confirmation**: appliance accepts unsigned paks and installs them in full with NO admin override required (42 records observed across the devel log corpus), and **does NOT enforce cert validity dates** ("skip dates" behavior — expired-2026-01-03 cert still trusted on Dec-2025 paks). `checkSignature` is opt-in at the API layer. VCF-CF can ship unsigned MPB-built paks for any internal-deployment scenario without friction; marketplace distribution still requires re-signing via the Broadcom marketplace pipeline. See `spec/16-platform-install-and-signing.md` for full appliance behavior, `analysis/pak-signing-chain.md` for on-disk cryptographic format.

10. **VCF-CF Tier 1 is fundamentally a Kotlin code generation task**, not just declarative-pak emission. Two implementation paths (§ 7 below) with concrete recommendations and risk tradeoffs.

---

## 1. What MPB is (and isn't)

### What it is

**Management Pack Builder (MPB)** is VMware's official authoring toolchain for VCF Operations management packs. End users drive a UI / API that builds a "design" describing:

- HTTP collection workflow (request catalogue, authentication, paging, chained requests)
- Resource model (what kinds of resources to discover, how to identify them)
- Metrics and properties (what to extract from response bodies)
- Relationships (parent-child, cross-MP)
- Event-driven symptoms and alerts (limited surface — see § 5)

The designer compiles the design into a `.pak` file that installs on a VCF Operations appliance like any other MP.

### What it ISN'T

- **Not a declarative-only pipeline.** Generated paks are full Track C (native Java) shape with per-pak compiled code.
- **Not a shared-runtime dispatch model.** No central "MPB engine" loads designs from sibling paks. Each design ships its own bundled runtime.
- **Not the same vocabulary as native Track C.** The MPB authoring surface is a strict subset of what describe.xml + hand-written adapters can express. See § 6 for the gaps.
- **Not OAuth-aware.** Auth options are Basic, SessionToken (with body/header response-field extraction), or Custom (the escape hatch — implement at runtime). No first-class OAuth2 refresh, Kerberos, AWS SigV4, or HMAC signing.
- **Not non-HTTP.** No JDBC, gRPC, SNMP, file-watch, syslog, native binary protocols. HTTP-only at the source level.

### Where the MPB runtime lives

The MPB runtime engine is itself a Track C adapter, shipped as `mpb-adapter-902025137884.pak` (in the devel bundle). It's NOT a shared runtime that other paks load — it's the **source/template** that the designer reuses per-pak with kind-key substitution. The pak exists on appliances primarily to host the designer-UI machinery (and possibly for self-monitoring).

---

## 2. Pak structure on disk (the Track-C reality)

```
<MP-name>.pak                            [outer zip, ~22 MB]
├── signature.cert                       (signed releases — see Risk section)
├── signature.mf
├── manifest.txt                         (pak-level)
├── eula.txt
├── default.png                          (icon)
├── post-install-fast.sh
├── post-install.sh
├── post-install.py                      install hooks (don't validate signatures)
├── postAdapters.py
├── preAdapters.py
├── validate.py
├── resources/resources.properties
├── content/                             declarative content emitted from the design
│   ├── dashboards/{overview.json, customDashboard0.json, ...}
│   ├── supermetrics/customSuperMetrics.json
│   ├── reports/, views/, files/                                 (often empty)
└── adapters.zip                         [inner archive, ~22 MB]
    ├── manifest.txt
    ├── default.png
    ├── eula.txt
    ├── resources/resources.properties
    └── mpb_<kindkey>_adapter3/                                  ← adapter root
        ├── mpb_<kindkey>_adapter3.jar                           [generated entry jar — ~236 KB]
        │   ├── adapter.properties                               (KINDKEY=mpb_<kindkey>, ENTRYCLASS=...)
        │   └── com/vmware/mpb/<kindkey>/
        │       ├── MPB<DesignName>Adapter.class                 ← entry class
        │       └── impl/                                        ← per-pak generated runtime code
        │           ├── validation/BuilderFileValidationKt.class
        │           ├── result/HttpResourceCollection.class
        │           ├── relationships/RelationshipCreator.class
        │           ├── query/ResourceQueryHelperKt.class
        │           ├── externalresource/ExternalResourceCollectorKt.class
        │           └── collect/http/{HttpRequestHandlerKt, RequestOrdererKt, ...}
        ├── conf/
        │   ├── describe.xml                                     (emitted from BuilderFile)
        │   ├── describeSchema.xsd
        │   ├── design.json                                      [runtime BuilderFile — ~20-40 KB]
        │   ├── mpb_<kindkey>.properties                         (adapter-instance config defaults)
        │   └── resources/resources.properties
        ├── doc/
        └── lib/                                                 [~60 dep jars, ~21 MB]
            ├── aria-ops-core-8.0.0.jar
            ├── kotlin-stdlib-1.5.32.jar + kotlin-reflect-1.5.32.jar + kotlinx-coroutines-core-jvm-1.5.1.jar
            ├── ktor-{client,client-apache,client-jackson,client-json,client-logging,utils,network}-jvm-1.6.2.jar
            ├── jackson-{annotations,core,databind,dataformat-xml,module-jaxb-annotations}-2.12.3.jar
            ├── httpclient-4.5.6.jar + httpcore-4.4.14.jar + httpcore-nio-4.4.14.jar
            ├── log4j-{api,core}-2.18.0.jar
            ├── woodstox-core-6.2.1.jar
            ├── guava-31.1-jre.jar
            ├── licensecheck-1.1.5.jar                           (Broadcom per-kind license enforcement)
            └── (other utility jars)
```

### Key callouts

- **The entry class is at `com.vmware.mpb.<kindkey>.MPB<DesignName>Adapter`** — kind key baked into the package path. Example: kind `mpb_ubiquiti_unifi` → package `com.vmware.mpb.mpbubiquitiunifi`.
- **All impl classes are similarly namespaced**: `com.vmware.mpb.<kindkey>.impl.validation.BuilderFileValidationKt`, etc. The MPB runtime jar's `com.vmware.mpb.impl.*` is the template; each pak gets a kind-key-renamed copy.
- **`adapter.properties` at the entry-jar root** is the standard SDK contract registration: `KINDKEY=` + `ENTRYCLASS=`. Identical to hand-written Track C adapters.
- **`conf/design.json`** is the runtime BuilderFile that the generated entry class loads at startup and dispatches against.
- **`license_type: "adapter:<kindkey>"`** in `manifest.txt` + bundled `licensecheck-1.1.5.jar` enforces per-kind licensing. VCF-CF needs to understand the licensing model before shipping customer paks.

---

## 3. The two JSON formats

### Format A: Designer wire format (the authoring side)

What the MPB designer UI exports and what users author against. Filename pattern: `*_MP_Builder_Design.json`.

Top-level keys:
```
{
  "design":  {"design": {6 fields}, "buildNumber": int},
  "source":  {"source": {7 fields}, "configuration": [per-instance config-params]},
  "requests":      [...],
  "objects":       [...],       ← becomes "resources" in runtime
  "relationships": [...],
  "events":        [...],
  "content":       [...]        ← dashboards / additional content
}
```

Designer-only fields (NOT in runtime BuilderFile):
- `design.buildNumber` — UI build counter
- `source.source.testRequest.response.result.dataModelLists` — captured response samples with sample `example` values
- `source.source.configuration` — HTTP-client config: `port`, `hostname`, `maxRetries`, `sslSetting` (e.g. `"NO_VERIFY"`), `baseApiPath`, `customConfigs`, `minEventSeverity`, `connectionTimeout`, `maxConcurrentRequests`
- `source.source.globalHeaders` — applied to every request
- Structured expression objects: `{id, expressionText, expressionParts: [...]}` with per-part `regex`, `originId`, `originType ∈ {ATTRIBUTE, PARAMETER, ARIA_OPS_METRIC}`
- `chainingSettings` (designer name) → `parentRequest` (runtime name)
- `header.type ∈ {REQUIRED, IMMUTABLE, CUSTOM}` (designer) → `header.enabled: bool` (runtime)
- `objects[i].object.ariaOpsConf` — declares the foreign Aria Operations resource for cross-MP attachment

### Format B: Runtime BuilderFile (the shipped form)

1:1 with the Kotlin `BuilderFile` data class (full enumeration in `spec/10`). Top-level keys:

```
{
  "version": 1,
  "id": "<uuid>",
  "name": "<MP display name>",
  "pakSettings": {
    "adapterKind": "mpb_<slug>",
    "author": "<author>",
    "name": "<MP name>",
    "version": "<x.y.z>",
    "description": "<...>",
    "icon": "default.png"
  },
  "source": {
    "type": "HTTP",
    "basePath": "<base url>",
    "testRequestId": "<request id>",
    "authentication": {"credentials": [...], "headers": [...], "type": "BASIC|SESSION_TOKEN|CUSTOM"},
    "configuration": [<per-instance config params>],
    "requests": [<BuilderRequest>],
    "resources": [<BuilderHttpResource>],
    "externalResources": [<BuilderHttpExternalResource>],
    "events": [<BuilderEvent>]
  },
  "constants": [<BuilderConstant>],
  "relationships": [<BuilderRelationship>]
}
```

### Transformations (designer → runtime)

| Designer | Runtime BuilderFile |
|---|---|
| `objects[]` | `source.resources[]` |
| `chainingSettings` | `parentRequest` |
| `{expressionText, expressionParts}` (structured) | `"${@@@MPB_QUOTE_BODY <jsonpath> @@@MPB_QUOTE}"` (string template) |
| `source.source.configuration.{sslSetting, maxConcurrentRequests, ...}` | dropped or baked into generated code |
| `globalHeaders` | merged into request headers |
| `header.type` enum | `header.enabled` bool |
| `dataModelLists` (captured samples) | dropped |
| Per-request `.response` (captured samples) | dropped |
| Auto-namespaced ResourceKind: `<adapterKind>_<label-sanitized>` (see § Label→key sanitize algorithm below) | computed at transform time |

### Size impact

| Design | Designer JSON | Runtime BuilderFile | Built pak |
|---|---|---|---|
| vSAN | 37 KB | (single source) | (zip wrapper) |
| UniFi | 213 KB | 40 KB | 22 MB |
| phpIPAM | 374 KB | 21 KB | 22 MB |

Designer JSON is 5-17× bigger than the runtime form (carries samples + dataModelLists). The pak is ~1000× bigger again because of the bundled Kotlin/Ktor/aria-ops-core/log4j runtime libs.

---

## 4. The Tier 1 authoring vocabulary (capability surface)

What VCF-CF designs CAN express (✅) — full BuilderFile schema reference in `spec/10`. Quick-reference table:

| Surface | Capability | Bounds |
|---|---|---|
| Source protocol | HTTP only | 1 source-type value (HTTP); no JDBC/gRPC/SNMP/file-watch |
| HTTP verbs | GET, POST, DELETE, PUT, PATCH | 5 verbs; no HEAD/OPTIONS/TRACE/CONNECT |
| Pagination | OFFSET (offset+limit), PAGES (page+perPage) | 2 strategies; no cursor / link-header / Range |
| Request chaining | Parent→child with list-then-detail substitution | First-class; `parentRequest` field links by requestId |
| Auth | Basic, SessionToken (with login/logout/extract), Custom | 3 types; SessionToken supports BODY or HEADER token extraction; Custom is escape hatch |
| Per-instance config | STRING, INTEGER, SINGLE_SELECTION | 3 types; no BOOLEAN (use SINGLE_SELECTION enum), no FILE, no rich types |
| Value transforms | BASE64, NONE | 2 transforms only; no URL encode/regex/JSONPath/XPath/concat/arithmetic |
| Resource naming | PROPERTY (look up a property by id) | 1 strategy; no literal-name, no expression-name |
| Resource identifiers | Property-keyed | Each identifier slot binds to a property by `propertyKey` |
| Metric data types | STRING, DECIMAL | 2 types; no integer/long/float distinction (everything numeric flattens to DECIMAL) |
| Metric flags | `property`, `kpi` | 2 booleans; no `isImpact`/`defaultMonitored`/`dtType`/`isRate`/`isDiscrete`/`favoriteGroups` |
| Timeseries handling | FIRST, LAST | 2 modes; no aggregation (SUM/AVG/MAX/MIN — use ComputedMetrics post-processing) |
| Metric hierarchy | Nested `metricGroups` (recursive) | Mirrors describe.xml `<ResourceGroup>` nesting |
| Cross-MP attachment | First-class via `BuilderHttpExternalResource` + `ariaOpsConf` | Foreign adapterKind+resourceKind+identifying metrics declared; runtime resolves and pushes |
| Cross-MP relationships | First-class | Both `parent` and `child` in BuilderRelationship can be FOREIGN adapter kinds |
| Identifier matching | IDENTIFIER (ResourceKey id) or PROPERTY (resource property) | 2 types; with optional regex extractor per match |
| Events | Dynamic severity (expression+map+default), message templating, pre-filtering, ALL/FIRST match mode, multi-resource matching | Rich at authoring layer; describe.xml emission collapses to event-message symptoms only |
| Event severity (authoring) | CRITICAL, IMMEDIATE, WARNING, INFO, DEBUG, IGNORE | 6 values; DEBUG/IGNORE are MPB-specific (collapsed to nothing at describe layer) |
| Alert categorization | type × subType × badge | 5 types × 5 subTypes × 3 badges (HEALTH/RISK/EFFICIENCY) — describeValue ints accessible via BuilderAlertType/SubType enums |
| Substitution language | `${configuration.X}`, `${authentication.credentials.X}`, `${authentication.basic}`, `${authentication.session.X}`, `${requestParameters.X}`, `${@@@MPB_QUOTE_BODY <jsonpath> @@@MPB_QUOTE}`, `${@@@MPB_QUOTE_REQUEST_PARAMETERS <key> @@@MPB_QUOTE}` (and likely more `@@@MPB_QUOTE_<SCOPE>` markers — list is non-exhaustive) | Uniform across all expression contexts |
| Named constants | `BuilderConstant(id, key, value)` for reusable substitutions | Top-level; referenced via `${<key>}` (presumably) |

---

## 5. The describe.xml emission pipeline

What VCF-CF's BuilderFile gets transformed into at pak-build time. The MPB runtime jar's `com.vmware.mpb.generation.*` package contains the emission machinery — 6 `IWritableFile` implementations + 1 dashboard writer:

| Class | Output file | Input |
|---|---|---|
| `DescribeXml` | `<adapter>/conf/describe.xml` | BuilderFile + DescribeResourcesProperties |
| `DescribeResourcesProperties` | `<adapter>/conf/resources/resources.properties` | (populated as Describe components register strings) |
| `AdapterProperties` | `<adapter>/adapter.properties` (the SDK contract) | BuilderFile |
| `Manifest` | `manifest.txt` (pak-level) | BuilderFile |
| `PakResourcesProperties` | pak-level `resources/resources.properties` | BuilderFile |
| `Version` | `version.txt` | BuilderFile |
| `DashboardJson.File` | `content/dashboards/*.json` | BuilderFile |

The `DescribeAdapterKind` in-memory root has 24 child component classes (one per describe.xml element):
- Adapter kind / instance kind / credential kind / credential field
- Resource kind / resource group / resource attribute / resource identifier
- Attribute data-type / unit / unit-type / computed-metric
- Traversal spec (with path-member / relation-type / relation-modifier)
- Discovery
- Relative-tag / world-tag resource kinds (synthetic tag kinds)
- Symptom definition / symptom state / symptom-state condition (eventMsg-only)
- Alert definition / alert state / alert impact / alert recommendation / alert symptom-set
- Recommendation definition / recommendation description

**XSD validation is built-in** via `DescribeXml.validateSchema()` using shaded `com.sun.msv` (Multi-Schema Validator).

### What MPB emission CANNOT produce (Tier 2 only)

Looking at `DescribeAdapterKind`'s child list vs. the full XSD (`spec/02a-describe-xsd-canonical.md`), MPB does NOT emit:
- `<CapacityDefinitions>` — capacity / time-remaining model
- `<Policies>` / `<PolicyMetrics>` / `<OotbPolicies>` — OOTB policy badges/thresholds
- `<CustomGroupMetrics>` — custom-group rollups
- `<Actions>` / `<Methods>` — user-invokable actions
- `<LicenseConfig>` / `<HAConfig>` — platform integration
- `<ProblemDefinitions>` — legacy alert surface
- `<Faults>` — pair-based event-driven alerts (separate framework from Symptoms)
- `<LaunchConfigurations>` — declarative UI deep-links
- `<TraversalSpecExtensionKinds>` — extending another adapter's TraversalSpecs
- `<FavoriteGroups>` — metric grouping for UI
- `<Names>` — ad-hoc names not tied to ResourceKinds

Metric-threshold symptoms, property-comparison symptoms, fault-event symptoms, compound boolean symptoms via `<SymptomSets>`, and `applyOn=child|descendant` relationship-scoped symptoms are also NOT emittable — MPB-generated `<SymptomDefinition>` has only `eventMsg` conditions.

---

## 6. Tier 1 → Tier 2 promotion triggers (the testable list)

**VCF-CF can statically determine at design-validation time whether a design is Tier-1-expressible** by checking against this list. If ANY trigger fires, promote to Tier 2 (native code generation against the legacy SDK + aria-ops-core SPI).

### Source / runtime triggers
- ❌ Non-HTTP collection (gRPC, JDBC, SNMP, file watch, syslog, native protocols)
- ❌ Auth beyond Basic / SessionToken / Custom (OAuth2 refresh flows, Kerberos SPNEGO, AWS SigV4, HMAC per-request signing, mTLS with cert renewal)
- ❌ Stateful collection (persistent connections, server-side subscriptions, streaming)
- ❌ Value transforms beyond BASE64 (URL encode, regex-on-final-value beyond the per-expression-part `regex` hook, XPath, concatenation, arithmetic, conditional). **JSON body navigation specifically is bounded** to dot-path + single-level `data.*` array iteration; predicate projections (JMESPath `[?...]`), bracket indexing, pipes, and function calls are NOT supported — see `spec/11 § Grammar bounds`. Need them → Tier 2.
- ❌ Pagination beyond OFFSET/PAGES (cursor-based, link-header, Range-header)
- ❌ HTTP verbs beyond GET/POST/DELETE/PUT/PATCH (rare but possible)

### Authoring-surface triggers
- ❌ Config-param types beyond STRING/INTEGER/SINGLE_SELECTION (BOOLEAN, FILE, encrypted strings beyond credentials)
- ❌ Metric data types beyond STRING/DECIMAL (integer-typed, long, float-vs-int distinction)
- ❌ Resource naming beyond property-lookup (literal, expression-computed, conditional)
- ❌ Per-attribute metric flags beyond `property`/`kpi` (isImpact, defaultMonitored, dtType, isRate, isDiscrete, isPropertyHistoryEnabled, keyAttribute, favoriteGroups/Instances)
- ❌ Aggregating timeseries (only FIRST/LAST in MPB; need ComputedMetrics post-processing for SUM/AVG/MAX/MIN)
- ❌ Programmatic actions (`<Actions>` / `<Methods>`)

### Describe-surface triggers (cannot be expressed in DescribeAdapterKind)
- ❌ `<CapacityDefinitions>`, `<Policies>`, `<OOTBPolicies>`, `<CustomGroupMetrics>`
- ❌ `<Actions>` / `<Methods>` / `<LaunchConfigurations>`
- ❌ `<Faults>` (pair-based event-driven alert framework)
- ❌ `<LicenseConfig>` / `<HAConfig>`
- ❌ `<TraversalSpecExtensionKinds>` / `<FavoriteGroups>` / `<Names>` / `<ProblemDefinitions>`

### Alert-axis triggers
- ❌ Metric-threshold symptoms (`Condition type="metric"`)
- ❌ Property-comparison symptoms (`Condition type="property"`)
- ❌ Dynamic threshold via reference (`thresholdType="metric|property"` with `targetKey`)
- ❌ Hard-threshold capacity symptoms (`Condition type="htmetric"`)
- ❌ Fault-event symptoms (`Condition type="fault"`)
- ❌ Compound boolean symptoms (`<SymptomSets>` or multi-`<Symptom>` `<SymptomSet>`)
- ❌ Relationship-scoped symptoms (`applyOn="child"|"descendant"`)
- ❌ Per-instance evaluation (`instanced="true"`)
- ❌ Multi-state alerts
- ❌ Recommendations with automated cross-adapter actions (`<Recommendation><Action>`)

---

## 7. Recommended Tier 1 implementation

Tier 1 is fundamentally a **Kotlin/Java code generation task** — not just declarative pak emission. There are two viable architectural paths and three implementation strategies for the code-gen step.

### Path A: Lightweight shared-runtime mode (UNOFFICIAL; verify appliance support)

VCF-CF emits only:
- BuilderFile JSON at `<adapter>/conf/design.json`
- `describe.xml` (via MPB runtime's `DescribeXml`)
- `adapter.properties` with a special ENTRYCLASS pointing at the shared `mpb-adapter` runtime
- `manifest.txt`

The pak depends on the `mpb-adapter` runtime pak already being installed on the appliance, and the shared runtime dispatches by `KINDKEY` to the design JSON in this pak.

**Pros**: ~50 KB pak (vs. 22 MB); no kotlinc in build pipeline; clean lifecycle.
**Cons**: Install-ordering dependency; runtime version coupling; **not observed in the wild** — no Track A paks of this shape in our corpus. Appliance support for this dispatch model is UNVERIFIED. Worth a conversation with Broadcom before committing.

### Path B: Match the MPB designer exactly (RECOMMENDED)

Per-pak codegen — generate ~100 Kotlin classes templated against the design's kind key, compile, bundle ~60 dep jars, ship 22 MB Track C-shaped pak. Indistinguishable from MPB-designer-generated paks at the runtime layer.

**Pros**: Matches what users / Broadcom support recognize; works on any VCF Operations appliance; no install dependencies; survives MPB runtime upgrades cleanly (each pak versioned independently).
**Cons**: 22 MB per pak (real but not crippling); requires kotlinc OR ASM in the build pipeline; need to maintain a Kotlin source tree extracted from the MPB runtime.

**Recommendation**: **Path B**. Match the official toolchain so VCF-CF-generated paks are interoperable with manually-built MPB designs and pass appliance compatibility checks identically.

### Code-gen step: three implementation strategies for Path B

#### Strategy 1: Source-level kind-key rename + recompile (cleanest)

Maintain a Kotlin source tree (extracted from `mpb_adapter-*.jar` by decompiling — note this is *for VCF-CF's build pipeline*, NOT for the cleanroom SPEC; the SPEC's no-copy rule doesn't apply to a derivative compiled product). Per pak:

1. Copy the source tree to a temp dir
2. Rename packages: `com.vmware.mpb.impl.*` → `com.vmware.mpb.<kindkey>.impl.*`
3. Substitute kind key in class names where applicable (entry class)
4. Compile with `kotlinc`
5. Package the resulting `.class` files into the per-pak entry jar

**Risk**: Maintenance burden if MPB runtime changes between releases. **Recommendation**: pin to a specific MPB runtime version per VCF-CF release; upgrade explicitly.

#### Strategy 2: Bytecode-level package rename (no kotlinc)

Use ASM (or jandex / classgraph) to rewrite class bytecodes:

1. Read each `.class` from the MPB runtime jar
2. Rewrite `Class-Reference`, `Constant-Pool` `Utf8` entries, internal references from `com/vmware/mpb/impl/...` to `com/vmware/mpb/<kindkey>/impl/...`
3. Write the rewritten classes into the per-pak entry jar

**Pros**: No Kotlin compiler in build pipeline; faster builds.
**Cons**: Brittle to MPB runtime updates (Kotlin metadata annotations may need handling); harder to debug than source-level.

#### Strategy 3: Skip per-pak codegen (Path A — confirm first)

If Broadcom confirms the appliance supports a shared-runtime dispatch model (Path A), this becomes simpler than 1 or 2 — VCF-CF just emits a small declarative pak with the BuilderFile + describe.xml.

#### Strategy 4: Per-pak stub class extending MPBAdapter (Pass 16 finding)

Discovered by reverse-engineering `com.vmware.mpb.MPBAdapter` (the abstract base class). Its full signature:

```kotlin
abstract class MPBAdapter : UnlicensedAdapter {
    private var builderFile: BuilderFile                            // loaded from <adapter>/conf/design.json at startup
    private val validateSHA: Boolean                                // verify design integrity at load
    // Abstract — per-pak overrides (these are THE ONLY two per-pak overrides):
    abstract fun getAdapterDirectoryName(): String
    abstract fun getTemplateSHA(): String
    // Concrete — inherited by every per-pak adapter unchanged:
    fun configure(status: ResourceStatus, config: ResourceConfig)
    fun getTester(...): Tester                                      // ← aria-ops-core SPI implemented in base
    fun getDiscoverer(...): Discoverer
    fun getHistoricalDataCollector(...): HistoricalCollector
    fun getLiveDataCollector(...): LiveCollector
    fun getAutoDiscoveryEnabled(...): Boolean
    fun isResourceRenameAllowed(): Boolean
    fun useBuiltinSuiteApiClient(): Boolean                         // overridable hook
    fun needRediscovery(...): Boolean                               // overridable hook
    // + ~70 more inherited helper methods
}
```

**A per-pak adapter is effectively a 2-line override** — the heavy machinery (aria-ops-core SPI implementations, the request-handler runtime, the relationship creator, etc.) lives in the inherited base class and its `com.vmware.mpb.impl.*` package.

Why doesn't MPB ship paks this small then? Because the appliance does NOT have the MPB runtime on a shared classpath — each pak's classloader is isolated (Pass 13 will confirm). So MPB regenerates the `com.vmware.mpb.impl.*` tree per-pak with kind-key-renamed packages to keep packages unique-by-pak AND copies the abstract `MPBAdapter` base class into each pak's lib/ implicitly via `mpb_adapter-*.jar`.

**Strategy 4 viability for VCF-CF**: only if VCF-CF ships a SEPARATE "runtime-contribution pak" that places `com.vmware.mpb.MPBAdapter` + its dependencies on the appliance classpath, then every VCF-CF-generated Tier 1 pak becomes a ~50 KB stub:

```kotlin
// Per-pak generated code, ~20 lines:
package com.vcfcf.adapters.<kindkey>

class <DesignName>Adapter(...) : com.vmware.mpb.MPBAdapter(...) {
    override fun getAdapterDirectoryName() = "<kindkey>_adapter3"
    override fun getTemplateSHA() = "<sha-of-bundled-design.json>"
}
```

Plus the standard pak chrome (`design.json`, `describe.xml`, manifest, etc.). No 21 MB lib/ bundle.

**Trade-offs vs. Strategies 1 + 2 (per-pak full codegen)**:
- ✅ Tiny paks (~50 KB) — easier distribution, faster install
- ✅ No kotlinc / ASM in VCF-CF's build pipeline — just template substitution
- ❌ Requires a runtime-contribution pak to be installed first — adds an install ordering dependency
- ❌ Version coupling: every VCF-CF pak depends on a specific MPB-runtime version contributed by the runtime pak
- ❌ Classloader isolation may PREVENT this from working — needs explicit appliance support (same risk as Path A)

**Strategy 4 vs. Path A**: similar shape, but Strategy 4 has the VCF-CF pak supply the entry stub class while Path A would have the pak supply only declarative content. Strategy 4 is "Path A++"  — keeps the per-pak ENTRYCLASS standard contract intact, just makes the entry class trivial.

**Recommendation**: prototype Strategy 4 alongside Strategy 1/2. If appliance classloading permits sharing, Strategy 4 is significantly cheaper than per-pak codegen. Validate by inspecting how `mpb-adapter` runtime pak vs. an MPB-generated pak interact when both installed (the runtime jar exists in both — no conflict observed in practice, suggesting per-pak classloader isolation works).

### Dependency bundling

For Path B, VCF-CF needs to bundle the same ~60 dep jars MPB does:
- `aria-ops-core-8.0.0.jar` (the SPI — critical)
- Kotlin: `kotlin-stdlib-1.5.32.jar`, `kotlin-reflect-1.5.32.jar`, `kotlinx-coroutines-core-jvm-1.5.1.jar`
- HTTP: Ktor (`client`, `client-apache`, `client-jackson`, `client-json`, `client-logging`, `utils`, `network` — all `-jvm-1.6.2.jar`), Apache HTTPClient (`4.5.6` + httpcore `4.4.14`)
- JSON/XML: Jackson 2.12.3 (`annotations`, `core`, `databind`, `dataformat-xml`, `module-jaxb-annotations`), woodstox `6.2.1`
- Logging: log4j `2.18.0` (`api` + `core`), jboss-logging `3.2.1.Final`
- Utility: guava `31.1-jre`, commons-text `1.10.0`, jakarta.activation-api `1.2.1`, annotations `13.0`
- Broadcom-specific: `licensecheck-1.1.5.jar` (per-kind license enforcement)

Maintain these as a versioned bundle in VCF-CF's build pipeline. **Pin all versions** to match what MPB ships, to ensure compatibility with the runtime's expectations.

### The pak orchestrator does NOT exist inside the MPB runtime jar (Pass 16 finding)

I searched the `mpb_adapter-9.0.1-patch-1.jar` exhaustively for any class that references both `IWritableFile` and `DescribeXml` — none exists. The orchestration of "call all 6 writers + bundle into a Pak" is the responsibility of an **external build tool** (the MPB designer's pak-build step / a CLI we don't have access to).

**Implication for VCF-CF**: there is NO `PakBuilder.build(BuilderFile): Pak` API to delegate to. VCF-CF must own:

1. Calling each of the 6 + 1 `IWritableFile.write()` methods in sequence with appropriate destination paths
2. Writing the BuilderFile JSON to `<adapter>/conf/design.json`
3. Computing the BuilderFile SHA and threading it into `getTemplateSHA()` of the per-pak entry class
4. Generating the per-pak entry jar (per chosen Strategy)
5. Copying the ~60 dep jars to `<adapter>/lib/` (Strategies 1/2) OR skipping bundling (Strategies 3/4)
6. Producing `manifest.txt` with `KINDKEY`, `ENTRYCLASS`, and the platform/version/license fields
7. Zipping the adapter directory + lib/ into `adapters.zip`
8. Wrapping with the outer pak chrome (install scripts, eula, content/, optionally signatures)

This is straightforward orchestration work, but it has to live in VCF-CF — there's no library hook for it.

### Generation pipeline (full)

```
Designer authoring (UI or YAML or API)
    │
    ▼
VCF-CF translates to BuilderFile (Kotlin object, per spec/10)
    │
    ▼
Static validation:
    1. Hibernate Validator annotations on BuilderFile model (built-in)
    2. Cross-attribute consistency checks (XSD-permissive but appliance-strict)
    3. Tier-1 promotion-trigger check (§ 6 above) — fail-fast if Tier 2 needed
    │
    ▼
For each output artifact:
    DescribeXml(builderFile, properties).write(<adapter>/conf/describe.xml)
    AdapterProperties(builderFile).write(<adapter>/adapter.properties)
    Manifest(builderFile).write(manifest.txt)
    DescribeResourcesProperties.write(<adapter>/conf/resources/resources.properties)
    PakResourcesProperties.write(resources/resources.properties)
    Version(builderFile).write(version.txt)
    DashboardJson.File.write(content/dashboards/*.json)
    BuilderFile.toJsonString().write(<adapter>/conf/design.json)
    │
    ▼
Code-gen step (Strategy 1 or 2):
    Per-pak entry jar with com.vmware.mpb.<kindkey>.impl.* classes
    │
    ▼
Dependency bundling:
    Copy ~60 dep jars to <adapter>/lib/
    │
    ▼
DescribeXml.validateSchema() ← final pre-flight gate
    │
    ▼
Pak assembly:
    Inner zip: adapters.zip (the adapter root + lib/ + conf/)
    Outer zip: .pak (signature.* if signing + manifest.txt + content/ + install hooks + adapters.zip)
    │
    ▼ (optional)
Sign with VMware cert / VCF-CF cert / leave unsigned (admin-override path)
    │
    ▼
Deployable .pak file
```

---

## 8. Cross-cutting recommendations

### Consider aria-ops-core SPI for vcfcf-adapter-base.jar (with caveat)

**Correction to earlier passes**: Pass 12 disproved my prior "aria-ops-core is universally used" framing. The actual landscape is:

| Adapter family | Base class | Uses aria-ops-core |
|---|---|---|
| Broadcom-internal classic (vim, NSXTAdapter3, vmwarevi_adapter3, VCFAutomation, VrAdapter, SupervisorAdapter, ServiceDiscoveryAdapter3, VirtualAndPhysicalSANAdapter3, AppOSUCPAdapter3, ...) | `com.integrien.alive.common.adapter3.AdapterBase` directly | **NO** |
| BlueMedora-derived marketplace (mongodb, mysql, postgresql, oracle, networkingdevices, microsoftsqlserver, servicenow, ...) | `UnlicensedAdapter` (extends AdapterBase) | YES |
| MPB runtime engine (`mpb_adapter-*.jar`) | `MPBAdapter` (extends UnlicensedAdapter) | YES |
| MPB-generated paks (UniFi, phpIPAM, vSAN, ...) | per-pak `MPB<Name>Adapter` (extends MPBAdapter) | YES (bundled `aria-ops-core-8.0.0.jar` in lib/) |

**Architectural reality**:
- `com.integrien.alive.common.adapter3.AdapterBase` is the UNIVERSAL foundation. Every Track C adapter ultimately extends it (directly OR transitively through `UnlicensedAdapter`).
- `aria-ops-core` (`UnlicensedAdapter extends AdapterBase`) is a Broadcom-owned WRAPPER (originally BlueMedora, acquired ~2018) that decomposes AdapterBase into a cleaner SPI: `Tester / Discoverer / LiveCollector / HistoricalCollector`.
- Broadcom-internal classic adapter teams chose NOT to adopt aria-ops-core. They use AdapterBase directly with their own helper code.
- **There is no shared framework between Broadcom-internal native adapters beyond AdapterBase itself** — `vim/NSX/vSphere/...` each have independent dependency stacks; no common helper jar across them.

**VCF-CF's actual choice for `vcfcf-adapter-base.jar`**:

**Option A: Direct AdapterBase pattern** — matches Broadcom-internal style. Maximum flexibility, no third-party-feeling framework dependency. VCF-CF writes its own helpers from scratch.

**Option B: aria-ops-core wrapper** — cleaner SPI decomposition out of the box. Less framework code to write. Adopts a third-party-feel framework that Broadcom-internal teams chose not to use (~half the ecosystem does use it).

Either produces a valid Track C adapter. The aria-ops-core decomposition (Tester / Discoverer / LiveCollector with three-axis `getCurrentMetrics`/`getEvents`/`getRelationships`) is genuinely better SPI design than the raw `collect()` template method — that's WHY BlueMedora and MPB picked it. But it's not "the Broadcom-internal standard" either.

**Recommended**: Option B (aria-ops-core), because:
- The SPI is cleaner and pre-built
- MPB-generated paks already use it (so VCF-CF Tier 1 paths inherit it via Strategy 1/2/B automatically — no architectural divergence between Tier 1 and Tier 2 abstractions)
- It's Broadcom-owned (post-BlueMedora acquisition) and shipped in production with every MPB pak — won't disappear

But understand it's a **choice**, not a forced conclusion from "everyone does it this way."

### Adopt the three-axis collection split regardless of base-class choice

Whether VCF-CF picks Option A or B above, the **three-axis collection decomposition** (`getCurrentMetrics()` + `getEvents()` + `getRelationships()` as separate methods) is a strong pattern. With Option A, VCF-CF implements this as its OWN SPI on top of AdapterBase. With Option B, it inherits the SPI from aria-ops-core.

The split matters because:
- Metrics, events, and relationships have different cadences and failure modes
- Mixing them in a monolithic `collect()` makes failure-isolation impossible
- Each axis can have independent retry / circuit-breaker behavior

### Leave a stream-subscription hook for future modern-SDK adoption

The `vcf-ops-data-sdk` (`com.broadcom.ops.data.*`) is a stalled, vCenter-specific specialty SDK — NOT a successor to the legacy SDK (Pass 9 finding). But its Reactive-Streams + multi-destination-routing patterns telegraph where the platform's internal data infra is heading.

**Recommendation**: design `LiveCollector.getCurrentMetrics()` to accept EITHER a pull implementation (call source, collect, return) OR a subscription implementation (subscribe at `configure()` time, drain a buffer in `getCurrentMetrics()`). Doesn't bind to any specific subscription SDK; preserves the architectural escape hatch.

### Signing — make a deliberate choice

The current MPB pak signing chain (Pass-tangent in `analysis/pak-signing-chain.md`):
- One self-signed VMware cert signs everything (Broadcom-internal + marketplace re-signed third-party)
- **Cert expired 2026-01-03**; appliance presumably skips validity checks
- SHA-1 + RSA exponent 3 (cryptographically deprecated)
- Community/dev paks ship with zero-byte `signature.cert` (unsigned)

VCF-CF options (in order of operational maturity):
1. **Generate unsigned paks** for the customer-side / internal-tool use case. Confirm the appliance accepts unsigned paks under what conditions (admin flag? per-cert trust override?). Path of least resistance for an MVP.
2. **Generate paks signed with a VCF-CF / customer-supplied cert.** Requires confirming the appliance accepts certs other than the VMware-pinned root.
3. **Submit to the marketplace re-signing pipeline.** Requires understanding the marketplace ingestion process (likely internal-only to Broadcom).

Whatever you pick, design the signing step as a **pluggable strategy** — Broadcom should modernize the format eventually (SHA-256, PSS or ECDSA, per-vendor identity, automated rotation) and VCF-CF should follow without architectural surgery.

### iSDK template placeholder hygiene

MPB-built paks ship `manifest.txt` with `"display_name": "DISPLAY_NAME"` and `"vendor": "VENDOR"` LITERALLY un-filled. This is the same scaffolding placeholder pattern observed in Track B (Integration SDK) paks. **VCF-CF should fill these in correctly** — they appear in the UI's MP catalog, and leaving them as placeholder strings would degrade the user experience even if the appliance accepts the pak.

Fields to fill in explicitly:
- `display_name` — the UI-rendered MP name (separate from `name`)
- `vendor` — vendor display string
- `description` — UI description
- `pak_icon` — icon path (default.png usually)

### Per-kind license enforcement

`manifest.txt:"license_type": "adapter:<kindkey>"` + bundled `licensecheck-1.1.5.jar` enforces licensing per adapter kind. VCF-CF needs to understand:
- Whether customer-deployed VCF-CF paks need a license entitlement or if they pass-through unlicensed
- How license_type strings are resolved (VCF Operations admin UI or external license file)
- Whether to ship `licensecheck-*.jar` or skip it (unsigned-pak deployments may not need it)

This is an external dependency on Broadcom's licensing infrastructure that VCF-CF needs to clarify before customer distribution.

---

## 8.5. Field findings from VCF-CF (additions from real-world usage)

These started as open follow-ups in earlier passes; VCF-CF's api-explorer work surfaced them empirically in production. Folding them back here.

### Label → key sanitize algorithm

When the MPB designer derives a `resourceKind` key (or any other identifier key) from a human-authored label, the `sanitizeFunction` applies these transformations IN ORDER:

1. **Drop `.`** (literal period)
2. **Drop `()`** (literal parens — handles unit annotations like `(%)`)
3. **Lowercase** the entire string
4. **Replace whitespace + `%` with `_`**
5. **Collapse `_+` runs to a single `_`**

Example trace: `"CPU Usage (%) Avg."` → `"CPU Usage (%) Avg"` → `"CPU Usage % Avg"` → `"cpu usage % avg"` → `"cpu_usage___avg"` → `"cpu_usage_avg"`.

**Behavior inconsistency observed**: some shipped BuilderFiles contain UN-collapsed forms (e.g., `mpb_ubiquiti_unifi_unifi___clients` with triple-underscore). That suggests the runtime's slugifier doesn't apply the collapse step in every codepath, OR that step is version-dependent. **VCF-CF should run the full 5-step pipeline on emit AND tolerate either form on read** (the platform appears to accept both).

### `@@@MPB_QUOTE_REQUEST_PARAMETERS` marker

The runtime expression DSL has a **family** of `@@@MPB_QUOTE_<SCOPE>` markers, not just `@@@MPB_QUOTE_BODY`. Critically:

- `@@@MPB_QUOTE_BODY` — navigates the current HTTP response body (JSON path)
- **`@@@MPB_QUOTE_REQUEST_PARAMETERS`** — looks up a value from the chaining-substitution context. **REQUIRED for `objectBinding.requestMatchIdExpression` when the resource is owned by a chained request** — connects child rows back to parent context.

VCF-CF field-confirmed by fixing a broken chained-resource binding that needed this marker. Without it, child resources don't bind to their parent context and you get orphaned rows.

Likely additional markers exist for the other expression contexts (headers, request params, session-extracted values) — the spec treats the list as "at least these," not "only these." If VCF-CF discovers more via testing, the spec should be extended.

The runtime classes that parse and evaluate these markers: `BuilderQueryRequestParamParserKt`, `BuilderQueryJsonNodeParserKt`, `ResourceQueryHelperKt` (all in `com.vmware.mpb.model.query.*`).

## 9. Open questions VCF-CF should track

1. **Does the appliance support Path A (shared-runtime dispatch)?** Worth a Broadcom conversation. If yes, Path A is simpler than Path B for VCF-CF MVP.
2. **What's the precise dataModelList → expression-string compilation algorithm?** The designer's structured expressions compile to `${@@@MPB_QUOTE_BODY <path> @@@MPB_QUOTE}` runtime strings, but the regex-handling, originType mapping, and multi-part templating details need full enumeration. Probably in `BuilderQueryJsonNodeParserKt` / `BuilderQueryRequestParamParserKt`. Future RE pass.
3. **Are the per-pak entry jars byte-identical modulo package-rename across designs?** Pass 17 strongly suggests yes (UniFi and phpIPAM have identical class lists with renamed packages) but a byte-level diff would prove it — and confirm that bytecode-level ASM rewriting (Strategy 2) is viable without recompilation surprises.
4. **What MPB SDK / build tool does Broadcom internally use for codegen?** May exist as a downloadable artifact. If found, VCF-CF could call it directly instead of reimplementing the codegen.
5. **What's the licensing model for VCF-CF-generated paks?** See § 8.
6. **Appliance signature-validation policy on expired certs and unsigned paks** — see § 8.
7. **`BuilderEvent` event-driven path in describe.xml emission** — the designer model supports rich event handling (dynamic severity, ALL/FIRST matching, cross-MP event-to-resource binding) but the emitted `<SymptomDefinition>` is `eventMsg`-only. What gets DROPPED in the compilation, and is the dropped behavior implemented in the per-pak generated code instead (i.e., the runtime evaluates the rich grammar internally before producing simple eventMsg symptoms for the platform)? Affects how much of the rich event grammar Tier 1 designs can actually rely on.
8. **MPB-emitted `Severity="Automatic"` portability** — observed in vSphere data but NOT in the XSD enum. Either the appliance accepts schema-non-compliant values, or there's a 6.4+ schema. Affects whether MPB designs using DEBUG/IGNORE/Automatic severities are portable across appliance versions.

---

## 10. Quick reference — crossref index to detailed specs

For full enumerations and evidence:

- **BuilderFile schema (Kotlin runtime model)**: `spec/10-mpb-builderfile-schema.md`
- **Designer wire format + pak generation pipeline**: `spec/11-mpb-designer-wire-format.md`
- **describe.xml in-memory emission model + MPB-runtime emission limits**: `spec/02-describe-xml.md § Describe-xml in-memory model`
- **describe.xml canonical XSD grammar (what Tier 2 can express that Tier 1 cannot)**: `spec/02a-describe-xsd-canonical.md`
- **Adapter lifecycle / SDK contract / packaging shapes**: `spec/01-adapter-lifecycle.md`
- **Credential model**: `spec/03-credential-model.md`
- **Resource model**: `spec/05-resource-model.md`
- **Metrics + units + computed expressions**: `spec/06-metrics-units-expressions.md`
- **Relationships + cross-MP attachment recipe**: `spec/07-relationships-cross-mp.md`
- **Alert framework (full Tier 2 grammar)**: `spec/08-alerts-symptoms-recommendations.md`
- **Investigation journey (chronological)**: `audit-log.md`
- **Pak signing chain analysis**: `analysis/pak-signing-chain.md`
- **MPB runtime architecture (early discovery — read with this handoff)**: `analysis/per-adapter/mpb-adapter-insights-for-vcf-cf.md`
- **vcf-ops-data-sdk characterization (not a successor SDK)**: `analysis/per-adapter/vcf-ops-data-sdk.md`
- **Final synthesis across all passes**: `spec/99-summary-and-vcf-cf-recommendations.md`
