# 11 — MPB designer wire format + the pak generation pipeline

**Status**: Pass 17 (2026-05-16) — written after inspecting 3 real-world MPB designs (UniFi, phpIPAM, vSAN) and the paks they produced.
**Source**: `inputs/known_mpb/` (gitignored — Track A authoring samples + corresponding built paks).

## TL;DR — the major architectural reframe

**MPB-generated paks are Track C-shaped, not Track A.** Each pak contains:
1. A **per-pak generated entry jar** (~100-200 classes, all under package `com.vmware.mpb.<kindkey>.impl.*`)
2. **~60 bundled dependency jars** including `aria-ops-core-8.0.0.jar`, Kotlin stdlib + coroutines + reflect, Ktor HTTP client, Jackson, Apache HTTP client, log4j, woodstox
3. The **design.json** at `<adapter>/conf/design.json` — the runtime BuilderFile (a 1:1 serialization of the Kotlin model from spec/10)
4. Standard pak chrome: `manifest.txt`, `eula.txt`, `default.png`, install hook scripts, optional `content/dashboards/*.json`

Per-pak size is **22 MB** (vs the ~226KB I'd expected for "pure Track A"). The Pass 1/7 hypothesis that MPB outputs lightweight Track A paks dispatched by a shared `mpb-adapter` runtime was **wrong** — the shared runtime in `mpb-adapter-*.jar` is the **template/source** that the designer uses to generate per-pak code; the actual deployed form has the runtime baked into each pak.

This radically reframes Tier 1 implementation for VCF-CF (see § Implications below).

## Two distinct JSON formats

There are **two** JSON formats in the MPB ecosystem, and conflating them led to the Pass 7 "1:1" confusion:

### Format A: Designer wire format (`*_MP_Builder_Design.json`)

What the MPB designer UI exports for user-facing authoring. **Richer than the runtime form** — includes designer-tool metadata.

Top-level keys:
```
{
  "design":  {"design": {6 fields}, "buildNumber": int},
  "source":  {"source": {7 fields}, "configuration": [...]},
  "requests":      [...],
  "objects":       [...],       // ← renamed to "resources" in runtime form
  "relationships": [...],
  "events":        [...],
  "content":       [...]        // ← dashboards / additional content
}
```

Designer-only fields (NOT in the runtime BuilderFile):
- `design.buildNumber` — UI's build counter
- `source.source.testRequest.response` (and per-request `.response`) — **captured example responses** the designer recorded during authoring
- `response.result.dataModelLists` — the response data-model tree (with sample `example` values) used to map fields
- `expression{id, expressionText: "...@@@MPB_QUOTE <partId> @@@MPB_QUOTE...", expressionParts: [...]}` — **structured expression model** with per-part regex/origin/originType
- `source.source.globalHeaders` — applied to every request
- `source.source.configuration` — HTTP-client config (port, sslSetting, baseApiPath, maxRetries, maxConcurrentRequests, connectionTimeout, minEventSeverity, customConfigs)
- `chainingSettings` (instead of runtime's `parentRequest`) — slightly different shape with `baseListId`, `parentRequestId`, and `attributeExpression` (structured) on each param
- `header.type ∈ {REQUIRED, IMMUTABLE, CUSTOM}` — richer than runtime's enabled bool

### Format B: Runtime BuilderFile (`<adapter>/conf/design.json` inside the pak)

The shipped runtime form. **1:1 with the Kotlin `BuilderFile` data class** (spec/10).

Top-level keys (7, including `version`):
```
{
  "version": 1,                  // file-format version
  "id": "...",
  "name": "Ubiquiti UniFi",
  "pakSettings":   {6 fields},   // SIMPLER than designer — many BuilderPakSettings defaults omitted
  "source":        {9 fields},
  "constants":     [...],
  "relationships": [...]
}
```

The transformations from Format A → Format B during pak build:

| Designer | Runtime BuilderFile |
|---|---|
| `objects[]` | `source.resources[]` |
| `chainingSettings` | `parentRequest` |
| `expression{expressionText, expressionParts[]}` | `expression: "${@@@MPB_QUOTE_BODY <jsonpath> @@@MPB_QUOTE}"` (compiled to string template) |
| `source.source.{configuration}` | dropped or moved to runtime classpath config |
| `source.source.globalHeaders` | merged into `source.headers` (or per-request) |
| `header.type: REQUIRED|IMMUTABLE|CUSTOM` | `header.enabled: bool` |
| `response.result.dataModelLists` | dropped (designer-only) |
| `*.response` (captured samples) | dropped |
| Long-form designer field names | compacted |
| Per-resource auto-namespaced `resourceKind: "mpb_<kindkey>_<label-slug>"` | (computed during transformation) |

### Size comparison (3-design corpus)

| Design | Designer JSON | Runtime BuilderFile | Built pak |
|---|---|---|---|
| vSAN | 37 KB | (not extracted — single-source pak) | (zip provided alongside) |
| UniFi | 213 KB | 40 KB | 22 MB |
| phpIPAM | 374 KB | 21 KB | 22 MB |

**The runtime BuilderFile is 5-17× smaller than the designer JSON** (designer carries response samples + dataModelLists). The pak is ~1000× larger again because of the bundled Kotlin/Ktor/aria-ops-core/etc. runtime libs.

## Inside an MPB-built pak (the Track-C shape)

Concrete UniFi pak structure (22 MB total):

```
Ubiquiti UniFi-1.0.0.7.pak     [outer zip]
├── signature.cert             (would be present on a signed release; not in dev builds)
├── signature.mf
├── manifest.txt               (pak-level — see below)
├── eula.txt
├── default.png                (icon)
├── post-install-fast.sh       \
├── post-install.sh             \
├── post-install.py              ├─ install hooks (don't validate signature; see analysis/pak-signing-chain.md)
├── postAdapters.py             /
├── preAdapters.py             /
├── validate.py               /
├── resources/resources.properties
├── content/                   (declarative content emitted from design)
│   ├── dashboards/{overview.json, customDashboard0.json}
│   ├── supermetrics/customSuperMetrics.json
│   ├── reports/                                 (empty in samples)
│   ├── views/                                   (empty)
│   └── files/reskndmetric/                      (empty)
└── adapters.zip               [inner archive — 22 MB]
    ├── manifest.txt           (inner-archive manifest)
    ├── default.png
    ├── eula.txt
    ├── resources/resources.properties
    └── mpb_ubiquiti_unifi_adapter3/                   ← adapter root, kind-key named
        ├── mpb_ubiquiti_unifi_adapter3.jar            [entry jar — 236 KB, per-pak generated code]
        │   └── (root)
        │       ├── adapter.properties
        │       │   ├── ENTRYCLASS=com.vmware.mpb.mpbubiquitiunifi.MPBUbiquitiUniFiAdapter
        │       │   └── KINDKEY=mpb_ubiquiti_unifi
        │       └── com/vmware/mpb/mpbubiquitiunifi/   ← PER-PAK PACKAGE — kind-key baked in
        │           ├── MPBUbiquitiUniFiAdapter.class  (the entry class)
        │           └── impl/
        │               ├── validation/BuilderFileValidationKt.class
        │               ├── result/HttpResourceCollection.class
        │               ├── relationships/RelationshipCreator.class
        │               ├── query/ResourceQueryHelperKt.class
        │               ├── externalresource/ExternalResourceCollectorKt.class
        │               └── collect/http/HttpRequestHandlerKt.class
        ├── conf/
        │   ├── design.json                            [the runtime BuilderFile — 40 KB]
        │   ├── mpb_ubiquiti_unifi.properties          [adapter-instance config defaults]
        │   └── resources/resources.properties
        ├── doc/                                       (empty)
        └── lib/                                       [60 bundled dep jars — ~21 MB]
            ├── aria-ops-core-8.0.0.jar                ← BlueMedora SPI
            ├── kotlin-stdlib-1.5.32.jar
            ├── kotlin-reflect-1.5.32.jar
            ├── kotlinx-coroutines-core-jvm-1.5.1.jar
            ├── ktor-{client,client-apache,client-jackson,client-json,client-logging,utils,network}-jvm-1.6.2.jar
            ├── jackson-{annotations,core,databind,dataformat-xml,module-jaxb-annotations}-2.12.3.jar
            ├── httpclient-4.5.6.jar + httpcore-4.4.14.jar + httpcore-nio-4.4.14.jar
            ├── log4j-core-2.18.0.jar + log4j-api
            ├── woodstox-core-6.2.1.jar
            ├── guava-31.1-jre.jar
            ├── jboss-logging-3.2.1.Final.jar
            ├── jakarta.activation-api-1.2.1.jar
            ├── licensecheck-1.1.5.jar                 ← Broadcom license enforcement
            ├── commons-text-1.10.0.jar
            └── annotations-13.0.jar
```

**Both UniFi and phpIPAM paks have IDENTICAL structure** with substituted kind keys: `mpb_phpipam_adapter3/...`, package `com.vmware.mpb.mpbphpipam.impl.*`, entry class `MPBPhpIPAMAdapter`. The generator templates the kind key into every package path and class name.

### Pak-level `manifest.txt`

```json
{
    "display_name": "DISPLAY_NAME",                  // iSDK template placeholder — left unfilled
    "name": "Ubiquiti UniFi",
    "description": "UniFi - On Premise",
    "version": "1.0.0.7",
    "run_scripts_on_all_nodes": "true",
    "vcops_minimum_version": "7.5.0",
    "disk_space_required": 500,
    "eula_file": "eula.txt",
    "platform": ["Windows", "Linux Non-VA", "Linux VA"],
    "vendor": "VENDOR",                              // iSDK template placeholder
    "pak_icon": "default.png",
    "license_type": "adapter:mpb_ubiquiti_unifi",
    "pak_validation_script": {"script": "python validate.py"},
    "adapter_pre_script":  {"script": "python preAdapters.py"},
    "adapter_post_script": {"script": "python post-install.py"},
    "adapters": ["adapters.zip"],
    "adapter_kinds": ["mpb_ubiquiti_unifi"]
}
```

Notable:
- **`display_name: "DISPLAY_NAME"` and `vendor: "VENDOR"` are LITERAL iSDK template placeholders**, not filled in. Matches the CLAUDE.md calibration note about iSDK-built Track B paks having these unfilled — **MPB designer shares the iSDK template** and leaves these placeholders too.
- `license_type: "adapter:<kindkey>"` — every MPB-built adapter is licensed per-kind. Bundled `licensecheck-1.1.5.jar` enforces this at runtime.
- `vcops_minimum_version: "7.5.0"` — supports vROps 7.5+ (legacy, pre-VCF Operations branding)
- `disk_space_required: 500` (MB) — install pre-check
- `platform` enumerates supported install targets — Windows, Linux Non-VA (non-virtual-appliance), Linux VA (virtual appliance). Generated paks support all three.
- `adapter_kinds: [<kindkey>]` — single kind per pak. Multi-kind paks would extend this.

## The per-pak generated entry jar

What gets generated per pak:

```
com/vmware/mpb/<kindkey-no-underscores>/
├── MPB<DesignName>Adapter.class                     ← entry class (implements AdapterInterface3 via aria-ops-core)
└── impl/
    ├── validation/BuilderFileValidationKt.class     ← reads conf/design.json, validates against schema
    ├── result/HttpResourceCollection.class          ← in-memory collection state
    ├── relationships/RelationshipCreator.class      ← reads design.relationships[], pushes via SDK
    ├── query/ResourceQueryHelperKt.class            ← evaluates expression strings (the ${@@@MPB_QUOTE_BODY ...} syntax)
    ├── externalresource/ExternalResourceCollectorKt.class    ← cross-MP property attachment
    ├── collect/http/{HttpRequestHandlerKt, HttpResourceMapperKt, RequestOrdererKt, ...}
    └── (~90 more classes)
```

**Each class is regenerated per pak with the kind key baked into the package path.** Compare:

| Class | MPB runtime jar | UniFi pak entry jar | phpIPAM pak entry jar |
|---|---|---|---|
| Validation | `com.vmware.mpb.impl.validation.BuilderFileValidationKt` | `com.vmware.mpb.mpbubiquitiunifi.impl.validation.BuilderFileValidationKt` | `com.vmware.mpb.mpbphpipam.impl.validation.BuilderFileValidationKt` |
| Entry | `com.vmware.mpb.MPBAdapter` | `com.vmware.mpb.mpbubiquitiunifi.MPBUbiquitiUniFiAdapter` | `com.vmware.mpb.mpbphpipam.MPBPhpIPAMAdapter` |

**Why per-pak codegen instead of shared runtime?** Most likely:
1. **Classloader isolation** — each pak gets its own classloader, no version conflicts
2. **Independent versioning** — each pak ships against a specific MPB runtime version, no shared-upgrade breakage
3. **No install ordering dependency** — paks install standalone
4. **Same shape as Track C** — appliance treats it identically to hand-written native adapters; no special MPB-aware install path needed

## The expression language (runtime form)

In the shipped BuilderFile, expressions are compiled to **string templates** with `${...}` substitution and `@@@MPB_QUOTE_<SCOPE>` source markers:

```
"${@@@MPB_QUOTE_<SCOPE> <path> @@@MPB_QUOTE}"
```

**Marker family** (the `<SCOPE>` part — there's more than one; confirmed in production data by VCF-CF field testing):

| Marker | Source | Where seen |
|---|---|---|
| `@@@MPB_QUOTE_BODY` | navigate into the current HTTP response body via JSON path | metric `expression` field; `listExpression` field on metric requests |
| `@@@MPB_QUOTE_REQUEST_PARAMETERS` | look up a value from the chaining-substitution context (parameters bound from a parent request) | **`objectBinding.requestMatchIdExpression`** — REQUIRED for chained-resource binding; VCF-CF field-confirmed |
| `@@@MPB_QUOTE` | the closing delimiter | always |

`@@@MPB_QUOTE_BODY` and `@@@MPB_QUOTE_REQUEST_PARAMETERS` are the two markers confirmed by direct evidence. Additional markers may exist (e.g., for `${authentication.session.*}` references or header-value substitution) — the marker family is opened by the design but not yet fully enumerated; treat the list as "at least these" not "only these."

Examples:

```
${@@@MPB_QUOTE_BODY data.* @@@MPB_QUOTE}
    → navigate to `data` then iterate (list expression for `listExpression` on metric requests)

${@@@MPB_QUOTE_BODY type @@@MPB_QUOTE}
    → extract `type` field from current response item (metric expression)

${@@@MPB_QUOTE_REQUEST_PARAMETERS datastore @@@MPB_QUOTE}
    → look up the `datastore` chaining parameter value (matched in objectBinding.requestMatchIdExpression
      when the resource is owned by a chained request — connects child rows back to parent context)
```

**Substitution namespaces** (also `${...}`-wrapped, but without the QUOTE markers — these reference VCF-CF-declared values rather than runtime response data):

- `${configuration.<key>}` — per-instance config-param value
- `${authentication.credentials.<key>}` — credential field value
- `${authentication.basic}` — auto-built Basic auth string
- `${authentication.session.<key>}` — session token / extracted response field
- `${requestParameters.<key>}` — chained-request substitution value (the named form; the `@@@MPB_QUOTE_REQUEST_PARAMETERS <key>` form is the response-context lookup variant)

The runtime's `ResourceQueryHelperKt` + `HttpRequestHandlerKt` + `BuilderQueryRequestParamParserKt` parse and evaluate these.

### Grammar bounds (empirical, Pass 25)

Surveyed all distinct `@@@MPB_QUOTE_BODY` paths across the two compiled MPB-built paks Scott provided (UniFi 1.0.0.7 + phpIPAM 1.0.0.11): **54 unique paths, 100% pure dot-notation**, only one wildcard form. Specifically:

| Construct | Supported? | Evidence |
|---|---|---|
| Dot-notation field navigation (arbitrary depth, e.g. `securityConfiguration.saeConfiguration.anticloggingThresholdSeconds`) | ✅ | All 54 observed paths |
| Top-level array iteration via `data.*` | ✅ | Used in 16/54 (UniFi) + 1/16 (phpIPAM) compiled paths |
| Single-object navigation from response root via `base` | ✅ (designer-side originId form; compiles to bare dot-path with no `data.*` prefix) | All `base`-anchored designer expressions |
| Nested array iteration (`data.*.X.*`, two-level pluck-then-iterate) | ❓ **Unverified** — structurally consistent with the design but **0 observed examples** in either pak. The runtime parser may or may not handle it; treat as unsupported until verified. |
| Bracket-indexed array access (`data[0]`, `data[1]`) | ❌ | 0 observed across 54 paths |
| Predicate projection (JMESPath `[?field=='value']`) | ❌ | 0 observed across 54 paths |
| Pipes (JMESPath `expr | [0]`) | ❌ | 0 observed |
| Function calls (JMESPath `length(@)`, `keys(@)`) | ❌ | 0 observed |
| Slice expressions (`[start:end]`) | ❌ | 0 observed |
| Regex post-processing on extracted value | ✅ (designer-side only — per-expression-part `regex` field) | Designer wire format `expressionParts[].regex`; compiles into the runtime template |

**Pipe (`|`) caveat**: pipes DO appear in some `originId` strings — but those are exclusively the **aria-ops METRIC KEY syntax** for cross-MP references (e.g. `aria-VMWARE-VirtualMachine-summary|guest|ipAddress`). The middle segment is the foreign adapter kind (`VMWARE`), not a body-navigation path; the `|`-delimited tail is the foreign resource's metric-key path in aria-ops naming convention. **Not relevant to the JSON body parser.**

**Runtime backing**: Jackson `JsonNode` (per spec/10 — `BuilderQueryNodeJsonResponse` uses `JsonNode`). NOT Jayway JsonPath. NOT JMESPath.

**Conclusion**: the grammar is "Jackson dot-path + `data.*` top-level wildcard." It's a deliberately minimal subset suitable for the common case of "flat REST endpoint returns `{data: [...]}`" — exactly the shape MPB encourages users to author against.

#### What this means for "iterate a sibling array by predicate"

You cannot. Three workarounds, in order of preference:

1. **Child ResourceKind** — declare the sub-array's element type as its own ResourceKind, hit an endpoint that returns it as a top-level `data[]` array, iterate via `data.*`. Wire parent↔child via `objectBinding.requestMatchIdExpression` (which uses `@@@MPB_QUOTE_REQUEST_PARAMETERS`). This is what UniFi's own MP does for `_clients`, `_devices`, `_networks`, `_wifi_broadcasts` (each a separate kind, each a separate endpoint).
2. **Multiple HTTP requests** — issue one request per filter value (e.g. one per band) if the upstream API supports server-side filtering, and have each request emit the same kind with discriminating metric names.
3. **Promote to Tier 2** — predicate projection over a nested array is a textbook Tier-1 → Tier-2 promotion trigger; in native code you have full Jackson + whatever else you bundle.

### `originType` enum — 4 values observed

| Value | Meaning | Where |
|---|---|---|
| `ATTRIBUTE` | pluck a non-metric field value from a response dataModelList element | identifier expressions, property expressions, name expressions |
| `METRIC` | pluck a numeric metric value from a response dataModelList element | metric `expression` fields |
| `ARIA_OPS_METRIC` | reference a foreign aria-ops metric key for cross-MP scenarios | `ariaOpsConf` foreign-resource declarations |
| `PARAMETER` | reference a chaining-context parameter (set by a parent request) | `objectBinding.requestMatchIdExpression`, URL-substitution parameters |

The originId encoding pattern by type:
- ATTRIBUTE / METRIC: `<requestUuid>-<collectionSegment>-<dotPath>` where collectionSegment ∈ `{base, data.*}`
- ARIA_OPS_METRIC: `aria-<adapterKind>-<resourceKind>-<metricKeyPath>` (uses `|` as metric-key separator)
- PARAMETER: just the parameter name (no collection segment)

## Designer-side expression structure (richer)

The designer stores expressions as **structured objects** that compile to the runtime string templates:

```json
{
  "id": "<uuid>",
  "expressionText": "@@@MPB_QUOTE <partId-1> @@@MPB_QUOTE plus literal text @@@MPB_QUOTE <partId-2> @@@MPB_QUOTE",
  "expressionParts": [
    {
      "id": "<partId-1>",
      "label": "Datastore ID",
      "regex": null,                                  // optional regex-extract from origin
      "example": "",                                  // sample value displayed in UI
      "originId": "<requestId>-<listId>-<fieldname>", // ATTRIBUTE/METRIC form
      "originType": "ATTRIBUTE",                      // {ATTRIBUTE, METRIC, ARIA_OPS_METRIC, PARAMETER} — see "Grammar bounds" above
      "regexOutput": ""                               // post-regex substitution
    }
  ]
}
```

See **§ Grammar bounds (empirical, Pass 25)** above for the full 4-value `originType` table and the `originId` encoding per type.

`regex` lets the design extract a substring from the origin value before substitution — adds a per-expression-part regex hook on top of the template.

## Validating the spec/10 BuilderFile model against real data

Spec/10's enumeration matches the shipped `conf/design.json` exactly. Specifically confirmed:

✅ `BuilderFile.{id, name, pakSettings, source, constants, relationships}` — exactly these 6 (+ `version`)
✅ `BuilderPakSettings.{author, name, adapterKind, version, description, icon}` — the user-facing subset; other Kotlin fields default-omitted
✅ `HttpBuilderSource.{type, basePath, testRequestId, authentication, configuration, requests, resources, externalResources, events}` — 9 keys, matches
✅ `BuilderHttpResource.{id, label, resourceKind, name, identifiers, isListResource, icon, metricGroups, requestedMetrics, metrics}` — matches; `metrics` omitted from minimal cases
✅ `BuilderListMetricRequest.{id, requestId, objectBinding, listExpression, metrics}` — matches
✅ `BuilderHttpMetric.{id, key, dataType, property, groups, expression, kpi, label}` — matches (8 of 10 fields populated; `unit`, `timeseries` omitted when defaults)
✅ `BuilderRelationship.{id, parent, child, caseSensitive}` — matches
✅ `BuilderRelationResource.{id, resourceKind, adapterKind, resourceKindName, expression, matchIdentifiers}` — matches
✅ `BuilderMatchIdentifier.{id, type, key, regex}` — matches; `type ∈ {IDENTIFIER, PROPERTY}` confirmed
✅ `BuilderHttpResourceName.{id, type: "PROPERTY", refId}` — matches; only PROPERTY type observed
✅ `BuilderHttpIdentifier.{id, key, propertyKey}` — matches
✅ `HttpMethod`: only GET observed in the 3-sample corpus, but model permits all 5
✅ `BuilderHttpAuthentication.{credentials, headers, type}` — matches; `type` values: `"BASIC"` (UniFi), TBD for phpIPAM/vSAN

### Auto-namespaced resource kind keys

The MPB designer auto-generates ResourceKind keys: `<adapterKindKey>_<label-slugified>`. Example:
- adapter kind: `mpb_ubiquiti_unifi`
- resource label: `UniFi - Clients`
- generated resource kind: `mpb_ubiquiti_unifi_unifi___clients`

### Label → key sanitize algorithm (VCF-CF field-confirmed)

Reverse-engineered empirically by VCF-CF's api-explorer (2026-05-16 field finding). The MPB runtime's `sanitizeFunction` applies these transformations in order:

1. **Drop `.`** (literal period — interferes with metric-key pipe-path semantics)
2. **Drop `()`** (literal parens — used for unit annotations like "CPU Usage (%)")
3. **Lowercase** the entire string
4. **Replace whitespace + `%` with `_`** (any whitespace character; `%` is a unit-symbol that would conflict with URL escapes)
5. **Collapse runs of `_`** — sequences of multiple underscores collapse to a single underscore

Example trace: `"CPU Usage (%) Avg."` → drop `.` → `"CPU Usage (%) Avg"` → drop `()` → `"CPU Usage % Avg"` → lowercase → `"cpu usage % avg"` → replace whitespace+`%` with `_` → `"cpu_usage___avg"` → collapse `_+` → `"cpu_usage_avg"`.

**Note**: this is the **post-collapse** form. Earlier draft (pre-VCF-field-finding) showed `unifi___clients` (un-collapsed) in the `mpb_ubiquiti_unifi_unifi___clients` example — that's a **bug or older runtime behavior**. With the correct algorithm, the example would be `mpb_ubiquiti_unifi_unifi_clients` (single underscore). The actual shipped BuilderFile uses `___` triple-underscores because the runtime's slugifier didn't apply the collapse step in that codepath. Two consistent behaviors observed; VCF-CF should match whichever the target runtime version uses.

Tier 1 generators must mirror this sanitization or accept user-provided ResourceKind keys (with platform-side uniqueness validation as the safety net).

## Implications for VCF-CF (re-stated for the Track-C-shape reality)

### Tier 1 is fundamentally a Java/Kotlin code generation task, NOT just declarative-pak emission

The Pass 7 recommendation "VCF-CF loads `mpb_adapter-*.jar` in-process, calls IWritableFile writers, packages result" was based on the wrong assumption that MPB output is Track A. The actual MPB designer:

1. Loads the BuilderFile from designer JSON
2. **Generates Kotlin source code** for ~100 classes templated against the design's kind key
3. **Compiles** to a per-pak entry jar
4. Bundles ~60 dependency jars (Kotlin/Ktor/Jackson/aria-ops-core/log4j/etc.)
5. Emits `conf/design.json` (the BuilderFile)
6. Generates dashboards JSON (Pass 7's DashboardJson.File mechanism — still works)
7. Generates describe.xml (Pass 7's DescribeXml — still works)
8. Generates adapter.properties (`KINDKEY=` + `ENTRYCLASS=`)
9. Writes manifest.txt with iSDK template placeholders still un-filled
10. Optionally signs (the now-expired VMware cert — see `analysis/pak-signing-chain.md`)
11. Zips into a Track C-shaped .pak

VCF-CF Tier 1 has **two paths**:

**Path A: Use MPB's runtime engine in shared-runtime mode** (NOT what MPB designer does, but possible)
- VCF-CF emits ONLY the BuilderFile JSON + describe.xml + manifest as a lightweight pak
- This pak depends on the `mpb-adapter` runtime pak already being installed on the appliance
- Pak is tiny (~50KB instead of 22MB)
- Trades: install-ordering dependency, runtime version coupling
- **Not the official path** — no observed Track A paks in the wild use this; appliance support uncertain

**Path B: Follow the MPB designer's pattern** (Track C-shape, per-pak runtime)
- VCF-CF must implement the same code-generation pipeline as the MPB designer
- Generate the per-pak Kotlin source for ~100 classes (or compile-once with a class template + kind-key rename)
- Bundle the ~60 dep jars (or extract from mpb_adapter-*.jar)
- 22MB output, but matches official tooling exactly
- **This is the path users / Broadcom support will recognize**

**Recommend Path B** — match the existing toolchain so VCF-CF-generated paks are indistinguishable from MPB-designer-generated paks at the runtime layer.

### Implementation strategies for the code-gen step

The per-pak code is templated very mechanically — basically a kind-key rename of the MPB runtime classes. Three implementation options:

1. **Source-level kind-key rename + recompile** — the legitimate path. Maintain a Kotlin source tree (extracted from MPB runtime jar via decompile), rename `com.vmware.mpb.impl.*` → `com.vmware.mpb.<kindkey>.impl.*` per-pak, compile with `kotlinc`. Clean but requires Kotlin compiler in VCF-CF's build pipeline.

2. **Bytecode-level package rename** — use ASM or similar to rewrite class bytecodes (rename package paths, fix internal references) without recompiling. Faster build, no kotlinc needed. Risk: brittle to MPB runtime updates.

3. **Skip per-pak codegen, use one shared runtime** — Path A above. Requires verifying the appliance accepts paks with the shared-runtime dispatch model. Worth a phone call with Broadcom to clarify.

The cleanroom rule prohibits copying decompiled SDK source into the SPEC, but **the MPB runtime jar is what VCF-CF would build against** — not "copy into SPEC" but "compile against, ship a derivative." This is the same posture the MPB designer takes.

### Confirmed: `aria-ops-core` is the runtime SPI

**`aria-ops-core-8.0.0.jar` is bundled in every MPB-generated pak's `lib/`.** This confirms the Pass 3 finding that aria-ops-core is the canonical SPI (Tester / Discoverer / LiveCollector / HistoricalCollector). MPB-generated entry classes implement this SPI. **VCF-CF Tier 2's `vcfcf-adapter-base.jar` should also use this SPI** (Pass 3/9 recommendation reinforced).

### Headers, sslSetting, and other knobs that disappear at compile time

The designer JSON has knobs (sslSetting, maxConcurrentRequests, header.type enum, etc.) that aren't visible in the runtime BuilderFile. These either:
- Become **adapter-instance config defaults** in `<adapter>/conf/<kindkey>.properties`
- Get **baked into the generated entry jar code** (not configurable at runtime)
- Get **applied via the bundled HTTP client** with hardcoded values

VCF-CF needs to expose these at the **designer-form layer**, then make build-time decisions about where they land.

### Cross-MP attachment is well-exercised

The vSAN sample uses `ATTRIBUTE_TO_PROPERTY` binding to write a property to a foreign vSphere Datastore. The `ariaOpsConf` block in the designer JSON declares the foreign resource (kind, identifying metrics) and the runtime emits cross-MP writes via the standard SDK path (Pass 1+7 finding).

This confirms: **MPB designs can be the EASY path for cross-MP attachment scenarios** that would otherwise require hand-coded Track C adapters.

## Open follow-ups

1. **Document the precise dataModelList → expression-string compilation algorithm.** The designer captures structured expressions; the build-time compiler produces `${@@@MPB_QUOTE_BODY <path> @@@MPB_QUOTE}` strings. **PARTIALLY RESOLVED in Pass 25**: the grammar bounds are now empirically known (dot-path + `data.*` top-level wildcard only — see § Grammar bounds above). The exact internal mapping (regex inclusion, multi-part template assembly) is still in `BuilderQueryJsonNodeParserKt` / `BuilderQueryRequestParamParserKt`. The remaining unknown is *how the compiler handles nested array iteration if it ever does* — no example in corpus.
2. **Diff the per-pak entry jars** between UniFi and phpIPAM to confirm classes are byte-identical modulo package-rename. That would prove the codegen is mechanical (and tell VCF-CF it can do the same).
3. **Look for an MPB SDK / build tool** that does the codegen for us (might be downloadable from Broadcom).
4. **Understand the dashboards/overview.json + supermetrics generation** — how does the designer derive those from the BuilderFile? Likely `com.vmware.mpb.generation.dashboards.DashboardJson` (Pass 7) but verify against real outputs.
5. **The signature.cert is missing from these dev-built paks** — they're unsigned (consistent with the Pass-tangent signing analysis: community/dev paks can ship without signature.cert). For VCF-CF's customer-facing distribution this needs a decision.
