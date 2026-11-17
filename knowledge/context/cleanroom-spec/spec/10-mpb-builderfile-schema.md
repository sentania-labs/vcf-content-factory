# 10 — MPB BuilderFile schema (Tier 1 runtime vocabulary)

**Status**: Pass 15 (2026-05-16); validated against 3 real designs (UniFi, phpIPAM, vSAN) in Pass 17.
**Source**: `mpb_adapter-9.0.1-patch-1.jar`, packages `com.vmware.mpb.model.*` (Kotlin data classes).
**Wire format**: JSON, **1:1 with the Kotlin model** as serialized by `BuilderFile.toJsonString()` / `BuilderFileDeserializer`. This is the **runtime form** shipped inside paks at `<adapter>/conf/design.json`. There is a SEPARATE **designer form** (richer, structured-expression-objects, with captured response samples) that the MPB designer UI uses for authoring — see `spec/11-mpb-designer-wire-format.md` for that and the design→runtime transformation.

## Top-level structure (recap from Pass 7)

```kotlin
data class BuilderFile(
    id: String,
    name: String,
    pakSettings: BuilderPakSettings,                       // pak-level metadata
    source: IBuilderSource,                                // currently only HttpBuilderSource
    constants: List<BuilderConstant>,                      // named substitution values
    relationships: List<BuilderRelationship>,              // top-level relationship declarations
)
```

`pakSettings` was enumerated in Pass 7. This section enumerates the rest.

## `BuilderConstant` — named substitution values

```kotlin
data class BuilderConstant(id, key, value)
```

Reusable string constants referenced by other expressions (e.g., `${myBasePath}` in a request path).

## `HttpBuilderSource` (the only `IBuilderSource` concrete)

```kotlin
class HttpBuilderSource : IBuilderSource {
    type: IBuilderSource.Type = HTTP                       // singleton enum
    basePath: String                                       // common URL prefix
    testRequestId: String                                  // which request runs at Test-Connection
    authentication: BuilderHttpAuthentication              // auth strategy
    configuration: List<BuilderConfigParam>                // per-instance UI form fields
    requests: Map<String, BuilderRequest>                  // request catalogue keyed by request ID
    resources: List<BuilderHttpResource>                   // discovered resources
    externalResources: List<BuilderHttpExternalResource>   // foreign-resource attachments (cross-MP)
    events: List<BuilderEvent>                             // event-driven symptoms
}
```

## HTTP request schema

### `BuilderRequest`

```kotlin
data class BuilderRequest(
    id: String,
    name: String,
    path: String,                                          // URL path, supports ${var} substitution
    method: HttpMethod,                                    // GET, POST, DELETE, PUT, PATCH
    headers: List<BuilderHeader>,
    body: String,                                          // request body (free text — author chooses JSON/form/XML)
    params: List<BuilderParam>,                            // query params
    parentRequest: BuilderParentRequest?,                  // chained-request linkage (null = top-level)
    paging: BuilderPaging?,                                // pagination strategy
)
```

`HttpMethod` enum: **5 verbs** — `GET`, `POST`, `DELETE`, `PUT`, `PATCH`. No HEAD, OPTIONS, CONNECT, TRACE.

### `BuilderHeader`

```kotlin
data class BuilderHeader(id, enabled: Boolean, key, value)
```

`enabled` toggle is first-class — designs can ship headers that are conditionally active. Useful for optional auth headers, content-negotiation overrides.

### `BuilderParam`

```kotlin
data class BuilderParam(id, key, value)
```

Query string parameters. No `enabled` flag (asymmetric with `BuilderHeader`).

### `BuilderPaging` — pagination strategies

```kotlin
data class BuilderPaging(
    id: String,
    type: BuilderPagingType,                               // OFFSET | PAGES
    pagingParam: String,                                   // name of the offset/page param
    limitParam: String,                                    // name of the limit/size param
    limitValue: Int,                                       // page size
    pagingStart: Int,                                      // starting offset/page number
    listPath: List<String>,                                // path to the result list in the response
)
```

`BuilderPagingType`: **2 strategies** — `OFFSET` (offset/limit style) and `PAGES` (page/perPage style). Cursor-based and link-header pagination are not first-class — fall through to CUSTOM or unsupported.

### `BuilderParentRequest` + `BuilderParentRequestParameter` — chained requests

```kotlin
data class BuilderParentRequest(
    id: String,
    requestId: String,                                     // reference to a parent request by ID
    parameters: List<BuilderParentRequestParameter>,
)

data class BuilderParentRequestParameter(
    id: String,
    listExpression: String,                                // navigates parent response to a list
    attributeExpression: String,                           // extracts the substitution value from each list item
)
```

The chained-request mechanism: a child request declares its parent by `requestId`, then declares `parameters` that pull values from the parent's response. The runtime issues the parent request, walks the `listExpression` to enumerate items, and for each item extracts `attributeExpression` and substitutes it into the child request's URL/body/params. This is the list-then-detail pattern.

## HTTP resource schema (the discovery side)

### `BuilderHttpResource` — owned resources

```kotlin
data class BuilderHttpResource : IHttpResource, IBuilderResource (
    id: String,
    label: String,
    resourceKind: String,                                  // describe.xml ResourceKind key
    name: BuilderHttpResourceName,                         // how to compute the display name
    identifiers: List<BuilderHttpIdentifier>,              // ResourceKey identifier slots
    isListResource: Boolean,                               // true = one response item per resource
    icon: String,                                          // describe.xml-registered icon key
    requestedMetrics: List<BuilderMetricRequest>,          // which requests fetch which metrics
    metricGroups: Map<String, BuilderMetricGroup>,         // nested metric grouping
    metrics: List<IDescribedMetric>,                       // flattened metric list (for describe emission)
)
```

### `BuilderHttpExternalResource` — foreign-resource attachments

```kotlin
data class BuilderHttpExternalResource (
    id: String,
    adapterKind: String,                                   // FOREIGN — e.g. "VMWARE"
    resourceKind: String,                                  // FOREIGN — e.g. "VirtualMachine"
    resourceKindName: String,                              // localized display name
    isListResource: Boolean,
    requestedMetrics: List<BuilderExternalMetricRequest>,
    metricGroups: Map<String, BuilderExternalMetricGroup>,
)
```

**Cross-MP attachment is a first-class authoring concept** in MPB. A design can declare that some collected metrics attach to a foreign resource kind, identified by matching identifiers (via `BuilderMatchIdentifier` — see below). The runtime resolves the foreign `ResourceKey` and pushes metrics/properties via `HttpExternalResourcePropertyAdder` (Pass 1 finding).

### `BuilderHttpResourceName` + `HttpResourceNameType`

```kotlin
data class BuilderHttpResourceName(id, type: HttpResourceNameType, refId: String)

enum HttpResourceNameType { PROPERTY }                     // only 1 value!
```

**Only ONE strategy for naming** — PROPERTY (look up a property by `refId` on the resource and use its value as the name). No literal-name, no expression-name. Designs that need computed names must declare the name as a property and let the platform read it back.

### `BuilderHttpIdentifier`

```kotlin
data class BuilderHttpIdentifier(id, key, propertyKey)
```

Each identifier slot binds to a property via `propertyKey`. The runtime fills the `ResourceKey` identifier value from that property at collection time.

### `BuilderMetricRequest` + `BuilderListMetricRequest` (and External variants)

```kotlin
class BuilderMetricRequest(
    id, requestId,                                         // which BuilderRequest fetches the data
    metrics: List<BuilderHttpMetric>,                      // what to extract
    objectBinding: IObjectBinding,                         // how to wire the response to a resource
)

class BuilderListMetricRequest extends BuilderMetricRequest {
    listExpression: String,                                // navigate to the list of objects in response
}
```

`BuilderExternalMetricRequest` / `BuilderExternalListMetricRequest` mirror these but with `BuilderExternalHttpMetric` (the external metric type without all the describe-side attributes since the foreign adapter owns the kind).

### `IObjectBinding` — how a response binds to a resource

Two implementations:

```kotlin
enum BuilderObjectBindingType { ATTRIBUTE_TO_PROPERTY, CHAINED_REQUEST }

class BuilderHttpObjectBinding (
    id, type: ATTRIBUTE_TO_PROPERTY,
    requestMatchIdExpression: String,                      // extract match id from response
    resourceMatcherExpression: String,                     // compute resource matcher value
    resourceMatchers: List<BuilderMatchIdentifier>,        // identifier/property match rules
)

class BuilderChainObjectBinding (id, type: CHAINED_REQUEST)  // simple — uses chained-request linkage
```

- `ATTRIBUTE_TO_PROPERTY`: bind the response's data to an existing resource by matching identifiers/properties. The cross-MP attachment path.
- `CHAINED_REQUEST`: the response already has a 1:1 correspondence with a resource via chained-request setup. No matching logic needed.

### `BuilderMatchIdentifier` — cross-cutting identifier matching

```kotlin
data class BuilderMatchIdentifier(
    id: String,
    type: BuilderMatchIdentifierType,                      // IDENTIFIER | PROPERTY
    key: String,
    regex: String,                                         // regex to extract from the value
)
```

`BuilderMatchIdentifierType` has **2 values**: `IDENTIFIER` (match against a ResourceKey identifier) and `PROPERTY` (match against a resource property). With a regex extractor for fuzzy matching (e.g., extract a UUID from a URL).

This is the same type used in `BuilderHttpObjectBinding`, `BuilderEventMatcher`, and `BuilderRelationResource` — one cross-cutting matching primitive.

## HTTP metric schema

### `BuilderHttpMetric`

```kotlin
data class BuilderHttpMetric (
    id: String,
    expression: String,                                    // JSON expression to extract value
    key: String,                                           // metric key in pipe-path notation
    label: String,
    dataType: DataType,                                    // STRING | DECIMAL (only 2!)
    property: Boolean,                                     // isProperty?
    kpi: Boolean,                                          // isKpi?
    groups: List<String>,                                  // metric group memberships
    unit: String,
    timeseries: BuilderHttpTimeseries?,
)
```

**`DataType` enum has ONLY 2 values: `STRING` and `DECIMAL`.** Compare to:
- describe.xml `ResourceAttribute.dataType`: 5 values (string, integer, long, float, double)
- describe.xml `PropertyDatatypeType`: 17 values

**MPB-emitted metrics are coarse-grained** — everything numeric is DECIMAL (no int vs float distinction). Integer-typed metrics in describe.xml are flattened to float at MPB emission time. Strings stay strings.

**MPB exposes `kpi` directly but NOT `isImpact`, `defaultMonitored`, `dtType`, `isRate`, `isDiscrete`, `favoriteGroups`** — the 7+ richer ResourceAttribute booleans from Pass 10's XSD reading are NOT in the MPB authoring surface. **Tier 1 designs cannot author KPI-impact distinction or dt-algorithm hints; promote to Tier 2 if needed.**

### `BuilderHttpTimeseries` + `TimeseriesMode`

```kotlin
data class BuilderHttpTimeseries(id, mode: TimeseriesMode, valueExpression: String)
enum TimeseriesMode { FIRST, LAST }
```

When a response returns a time-series (list of timestamped data points), `valueExpression` extracts the value and `mode` selects which point: `FIRST` or `LAST`. No aggregation (sum/avg/max/min) — those would be Tier 2 (or post-processing via ComputedMetrics).

### `BuilderMetricGroup` — nested metric grouping (hierarchy)

```kotlin
data class BuilderMetricGroup(
    id, key, label,
    childGroups: Map<String, BuilderMetricGroup>,          // recursive hierarchy
)
```

Mirrors the describe.xml `ResourceGroup` nesting. Map keys are child-group IDs.

## Authentication schema (deep)

### `BuilderHttpAuthentication` (abstract)

```kotlin
abstract class BuilderHttpAuthentication {
    credentials: List<BuilderCredential>                   // declared credential fields (UI)
    headers: List<BuilderHeader>                           // auth-specific headers to inject
    type: AuthenticationType                               // SESSION_TOKEN | BASIC | CUSTOM
    abstract suspend fun getAuthFields(...): Map<String, String>
    abstract suspend fun releaseAuth(...)
}

data class BuilderCredential(
    id, key, label,
    sensitive: Boolean,                                    // mask in UI; never log
    description: String,
)
```

### `BasicBuilderAuth`

```kotlin
class BasicBuilderAuth : BuilderHttpAuthentication {
    requiredCredentials = ["USERNAME_CREDENTIAL", "PASSWORD_CREDENTIAL"]   // hardcoded keys
    BASIC_AUTH_FIELD_NAME = "Authorization"
}
```

The simplest auth. Hardcoded credential keys; runtime concatenates and base64-encodes for the `Authorization: Basic ...` header.

### `SessionTokenBuilderAuth` — the rich case

```kotlin
class SessionTokenBuilderAuth : BuilderHttpAuthentication {
    token: SessionToken
}

data class SessionToken(
    getSession: BuilderRequest,                            // the request that fetches the session
    releaseSession: BuilderRequest,                        // optional logout request
    responseFields: List<SessionTokenResponseField>,       // what to extract from session response
    credentialType: AuthenticationType,                    // auth FOR the session-getting request itself
)

data class SessionTokenResponseField(
    id: String,
    key: String,
    path: List<String>,                                    // navigate to the token in the response
    location: Location,                                    // BODY | HEADER (where to read from)
)

enum SessionToken.Location { BODY, HEADER }
```

**This is the design surface for token-based REST APIs**:
1. Author declares `getSession` request (often POST /login with credentials in the body)
2. Author declares which response fields to extract (e.g., `path=["data","token"]` from JSON body, OR `key="X-Auth-Token"` from response headers)
3. Runtime fetches session, extracts tokens, injects them into subsequent requests (via `headers` field on the parent auth)
4. On adapter shutdown, runtime calls `releaseSession` for clean logout

**The session-getting request can use Basic OR Custom auth** (via `credentialType`) — so you can have e.g. "POST /login with Basic auth, get back a bearer token, use that token via Custom for everything else."

**This is rich enough for most modern REST APIs** but NOT for OAuth2 (no client_id/client_secret/refresh_token flow), Kerberos (no SPNEGO), AWS SigV4 (no canonical-request signing), HMAC schemes (no per-request signing). Those need `CustomBuilderAuth` with hand-written extension code — i.e., Tier 2.

### `CustomBuilderAuth`

```kotlin
class CustomBuilderAuth : BuilderHttpAuthentication { }
```

Empty placeholder — the escape hatch. The runtime invokes user-written code via `IMPBClient` callbacks. **Anything beyond Basic/SessionToken is Tier 2.**

## Event/Alert schema (Pass 7 finally completed)

### `BuilderEvent` — declarative event-driven symptoms

```kotlin
data class BuilderEvent(
    id: String,
    type: String,                                          // event type identifier
    label: String,
    requestId: String,                                     // which BuilderRequest fetches events
    eventQuery: String,                                    // JSON expression: navigate to events in response
    defaultToAdapterInstance: Boolean,                     // fire on adapter instance if no resource matches
    matchMode: BuilderEventMatchMode,                      // ALL | FIRST
    matchers: List<BuilderEventMatcher>,                   // resource binding
    severity: BuilderEventSeverity,                        // dynamic severity (expression+map+default)
    messageExpression: String,                             // dynamic message text
    filterExpression: String,                              // pre-filter events
    alert: BuilderAlert?,                                  // tied alert (optional)
)
```

**This is MUCH richer than Pass 7's "eventMsg-only" finding suggested.** MPB events support:
- Dynamic severity per event (mapping function from event content)
- Message templating
- Pre-filtering (drop irrelevant events before evaluation)
- Multi-resource matching with `ALL`/`FIRST` semantics
- Cross-MP attachment via `BuilderEventMatcher.adapterKind`

The MPB-emitted `<SymptomDefinition>` is still eventMsg-only at the describe.xml level (Pass 7), but **the upstream `BuilderEvent` model is the authoring surface VCF-CF generates against — and it's substantially more expressive than the emitted describe.xml lets through**. The MPB runtime evaluates the full event grammar internally and converts to simple eventMsg symptoms for the platform.

### `BuilderEventMatcher` — bind event to resource

```kotlin
data class BuilderEventMatcher(
    id: String,
    resourceKind: String,
    adapterKind: String,                                   // can be FOREIGN — cross-MP events!
    matchIdExpression: String,                             // extract match-id from event
    resourceMatcherExpression: String,                     // compute resource-side match value
    resourceMatchers: List<BuilderMatchIdentifier>,        // identifier/property match rules
    caseSensitive: Boolean,
)
```

### `BuilderEventMatchMode` — `ALL` or `FIRST`

`ALL` fires the symptom on every matched resource; `FIRST` only on the first match. Major behavioral knob.

### `BuilderEventSeverity` — dynamic severity

```kotlin
data class BuilderEventSeverity(
    id: String,
    expression: String,                                    // extract severity value from event
    severityMapping: Map<String, BuilderEventSeverityEnum>,// map extracted string → enum
    default: BuilderEventSeverityEnum,                     // fallback
)

enum BuilderEventSeverityEnum {
    CRITICAL(level=?, describeLabel="Critical"),
    IMMEDIATE(level=?, describeLabel="Immediate"),
    WARNING(level=?, describeLabel="Warning"),
    INFO(level=?, describeLabel="Info"),
    DEBUG(level=?, describeLabel=?),                       // MPB-specific
    IGNORE(level=?, describeLabel=?),                      // MPB-specific
}
```

**6 severity levels** — `DEBUG` and `IGNORE` are MPB-specific (the platform's describe-xml severity enum has only 4 visible: Info/Warning/Immediate/Critical). DEBUG is presumably suppressed in normal UI; IGNORE is "matched but suppress" (filter without dropping). The `describeLabel` field is the explicit MPB→describe.xml severity mapping.

### `BuilderAlert` — alert tied to a BuilderEvent

```kotlin
data class BuilderAlert(
    id: String,
    type: BuilderAlertType,                                // 5-value enum
    subType: BuilderAlertSubType,                          // 5-value enum
    badge: BuilderBadge,                                   // 3-value enum
    waitCycle: Int,
    cancelCycle: Int,
    recommendation: String,                                // free text
)
```

### **🎯 `BuilderAlertType` enum → resolves the Pass 8 "platform alert-type code table" open question**

```kotlin
enum BuilderAlertType(val describeValue: Int) {
    APPLICATION,
    VIRTUALIZATION,
    HARDWARE,
    STORAGE,
    NETWORK,
}
```

**5 alert-type categories**, each mapping to an `int describeValue`. Pass 8's open follow-up "Platform's alert type/subType int → category lookup table — need to find this" is RESOLVED. The actual int codes aren't visible from javap output but exist in the constants — they ARE the {15, 16, 20} values observed in vSphere data. VCF-CF can read the actual values via reflection on the enum constants.

### `BuilderAlertSubType` — 5 subType categories

```kotlin
enum BuilderAlertSubType(val describeValue: Int) {
    AVAILABILITY, PERFORMANCE, CAPACITY, COMPLIANCE, CONFIGURATION,
}
```

Maps to the {6, 18, 19, 20, 21, 22, 28, 29} int values observed in vSphere data. **The MPB enum has 5 values; vSphere uses 8 distinct subType ints — so the MPB enum is a SUBSET of the platform's full taxonomy.** Tier 2 adapters have access to subType codes Tier 1 cannot author.

### `BuilderBadge` — 3 badges

```kotlin
enum BuilderBadge(val describeName: String) {
    EFFICIENCY, HEALTH, RISK,
}
```

Matches the Pass 8 / spec/08 finding. The Aria Operations 3-badge model.

## Relationship schema

### `BuilderRelationship` — declarative parent/child

```kotlin
data class BuilderRelationship(
    id: String,
    parent: BuilderRelationResource,                       // the "from" side
    child: BuilderRelationResource,                        // the "to" side
    caseSensitive: Boolean,                                // identifier matching case-sensitivity
)

data class BuilderRelationResource(
    id: String,
    resourceKind: String,
    adapterKind: String,                                   // can be FOREIGN — cross-MP relationships!
    resourceKindName: String,
    expression: String,                                    // navigation expression
    matchIdentifiers: List<BuilderMatchIdentifier>,        // identifier matching
)
```

**Both sides of a relationship CAN reference a foreign adapter** — cross-MP topology is a first-class declarative concept. The runtime resolves both endpoints (own or foreign) and pushes the edge via the SDK's `Relationships` API.

The `BuilderRelationResource.isLocalResource(BuilderFile)` helper exists — runtime distinguishes local-owned vs foreign references for handling.

## Query / response-parsing DSL

The `BuilderQuery*` types describe how response navigation expressions are parsed and evaluated. They are runtime types, not authoring types, but they constrain what expression syntax is supported.

```kotlin
class BuilderQueryResponse(query, combinedValue, starValues: List<String>)
class BuilderQueryNodeJsonResponse(query, jsonValue: JsonNode, starValues)
class BuilderQueryNodeParamResponse(query, paramValue)
class RegexCheck(compiles: Boolean, multipleCaptureGroups: Boolean, message: String)
```

Key inferences:
- **`starValues: List<String>`** suggests `[*]` wildcard syntax navigates lists; matches return as a list
- **`combinedValue`** suggests scalar coercion for non-list matches
- Three node types (Json / Param / generic Node) suggest different value sources: response body JSON, URL params, raw text
- `RegexCheck.multipleCaptureGroups` flag suggests the syntax allows regex capture groups for value extraction
- `BuilderQueryJsonNodeParserKt` (the parser) uses Jackson `JsonNode`

**Syntax is Jackson-JSONPointer-like with regex extensions** — not full JSONPath, not XPath. Concrete syntax not enumerated from javap alone; needs runtime examples. **One real BuilderFile JSON would lock this down completely** — still an open question (Pass 11 was negative).

## Implications for VCF-CF Tier 1

### What VCF-CF can now express (full capability list)

✅ **HTTP collection with all 5 verbs**, headers (with enable toggle), query params, request bodies
✅ **2 pagination strategies** — OFFSET and PAGES
✅ **Chained requests** — list-then-detail with parent-child substitution
✅ **3 auth types** — Basic, SessionToken (rich — login/logout/extract-from-body-or-header), Custom (escape hatch)
✅ **Discovery + per-instance config UI** — STRING / INTEGER / SINGLE_SELECTION (Pass 7)
✅ **Resource declaration with property-based naming and identifier mapping**
✅ **Cross-MP foreign-resource attachment** — first-class via `BuilderHttpExternalResource`
✅ **Metric collection** — STRING / DECIMAL only, with kpi flag, unit, timeseries first/last
✅ **Hierarchical metric grouping** via nested `BuilderMetricGroup`
✅ **Cross-MP relationships** via `BuilderRelationship` (both sides can be foreign)
✅ **Event-driven symptoms** with dynamic severity, message templating, multi-resource matching, pre-filtering
✅ **Alert categorization** via 5-type × 5-subType × 3-badge taxonomy
✅ **BASE64 value transform** (Pass 7)
✅ **Named constants** for reuse via `BuilderConstant`

### What VCF-CF cannot express (promote-to-Tier-2 triggers)

❌ **Non-HTTP collection** (gRPC, JDBC, SNMP, file watch, syslog, native protocols)
❌ **Auth beyond Basic/SessionToken/Custom** (OAuth2 refresh, Kerberos SPNEGO, AWS SigV4, HMAC per-request, mTLS with cert renewal)
❌ **Value transforms beyond BASE64** (URL encode, regex extract, JSONPath, XPath, concatenation, arithmetic)
❌ **Pagination beyond OFFSET/PAGES** (cursor-based, link-header, Range-header)
❌ **Resource naming beyond property-lookup** (literal, expression-computed, conditional)
❌ **Metric types beyond STRING/DECIMAL** (integer-typed, complex types, structured properties)
❌ **Per-attribute KPI/Impact/defaultMonitored/dtType/favoriteGroups** (the richer ResourceAttribute booleans)
❌ **Aggregation in timeseries** (only FIRST/LAST; no SUM/AVG/MAX/MIN — those need ComputedMetrics post-processing)
❌ **Programmatic actions** (`<Actions>`/`<Methods>` not in MPB)
❌ **Capacity / Policy / OOTB-Policy / Faults / LaunchConfigurations / CustomGroupMetrics** (Pass 10 — not in MPB describe surface)
❌ **Symptoms with metric-threshold / property / fault / regex conditions** (Pass 8 — MPB symptoms are eventMsg-only at emission, even though BuilderEvent is richer upstream)
❌ **Compound boolean symptoms** (`<SymptomSets>` — not in MPB)
❌ **Multi-state alerts** (Pass 7/8 — Tier 2 only)
❌ **Recommendations with automated cross-adapter actions** (Pass 10 — `<Recommendation><Action>` — Tier 2)

### Alert type/subType taxonomy — VCF-CF dropdown content

For Tier 1 alert authoring UI, VCF-CF can expose:

| `type` | `subType` valid combinations | Use cases |
|---|---|---|
| APPLICATION | AVAILABILITY, PERFORMANCE, CAPACITY, COMPLIANCE, CONFIGURATION | App-layer monitoring |
| VIRTUALIZATION | (same) | VM / hypervisor |
| HARDWARE | (same) | Physical infra |
| STORAGE | (same) | SAN/NAS |
| NETWORK | (same) | Switches, routers |

5×5 = 25 possible combinations. Default to APPLICATION + PERFORMANCE when authoring is generic.

## Open follow-ups (Pass 16+)

1. **Read the actual int values of `BuilderAlertType.describeValue` and `BuilderAlertSubType.describeValue`** — javap shows the field exists but not the value. Need to extract via reflection or hex-dump the constant pool. Then map to the {15, 16, 20} type ints and {6, 18, 19, 20, 21, 22, 28, 29} subType ints observed in vSphere data — this closes the type/subType→category translation table for both directions (MPB enum ⇄ platform int).
2. **`BuilderQuery*` syntax** — concrete expression grammar for response navigation. Without a sample BuilderFile, the syntax is partially inferred from class names.
3. **`BuilderEvent.eventQuery` vs `messageExpression` vs `filterExpression`** — three different expression contexts; their syntax (probably uniform but worth verifying).
4. **Hibernate Validator annotations on the BuilderFile model** — Pass 11 revealed these are present; enumerating them gives the static validation rule list.
5. **The pak orchestrator** — still pending (Pass 16).
