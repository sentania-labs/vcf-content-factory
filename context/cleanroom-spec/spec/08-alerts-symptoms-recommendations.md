# 08 — Alert Framework: SymptomDefinitions, AlertDefinitions, Recommendations

**Status**: Pass 8 (2026-05-16) — drafted from mongodb (214 symptoms, 12 alerts, light variety) cross-referenced with vSphere `vmwarevi_adapter3` (517 symptoms, 119 alerts, full variety).
**Scope**: the `<SymptomDefinitions>` + `<AlertDefinitions>` + `<Recommendations>` sections of describe.xml.
**Not in scope here**: capacity/policy framework (separate pass — `<CapacityDefinitions>` and related were observed in passing but are documented in a future § 09).

## Three-layer model

```
<SymptomDefinition>     — atomic, named condition over a resource's metrics/properties/events
                          (an evaluator, not an alert)
        ▲
        │ ref="symptom-id"
        │
<SymptomSet>            — boolean combinator (and/or) over one or more <Symptom ref=…/>,
                          with applyOn-scoping (self/child/descendant) and aggregation
                          (any/percent)
        │
        │ contained in
        ▼
<State>                 — a severity-bearing combinator of <SymptomSet>s plus impact
                          and recommendations
        │
        │ contained in (singular — only one State per AlertDef in practice)
        ▼
<AlertDefinition>       — the alert the platform emits; ties State to a resource kind,
                          type/subType taxonomy, hysteresis (waitCycle/cancelCycle), and
                          policy controls
        │
        ▼ references
<Recommendation key=…>  — a remediation snippet (top-level catalog, ref'd by alerts)
```

This separation lets the same `<SymptomDefinition>` be reused across multiple alerts at different severities and in different boolean combinations. Mongodb (light case) declares 1:1 symptom→alert and never compounds. vSphere (heavy case) declares far more symptoms than alerts and routinely compounds them.

## `<SymptomDefinition>` — atomic condition

```xml
<SymptomDefinition id="datastore_full"
                   nameKey="42"
                   adapterKind="VMWARE"
                   resourceKind="Datastore"
                   waitCycle="1"
                   cancelCycle="1">
    <State severity="Immediate">
        <Condition type="metric" key="capacity|usedSpacePct"
                   operator=">" value="90"
                   valueType="numeric"
                   thresholdType="static"/>
    </State>
</SymptomDefinition>
```

### Attributes

- `id` — stable string identifier (referenced by SymptomSet/Alert)
- `nameKey` — int → resources.properties (localized display name)
- `adapterKind` — adapter that owns the symptom (case observed: `adapterKind` and `adapterkind` both accepted)
- `resourceKind` — which kind of resource this symptom evaluates against
- `waitCycle` — collection cycles the condition must hold true before the symptom activates (hysteresis-up)
- `cancelCycle` — cycles the condition must hold false before symptom clears (hysteresis-down)

### `<State severity="…">` — severity binding

`severity` ∈ {`Info`, `Warning`, `Immediate`, `Critical`, `Automatic`} (case-insensitive on the wire — both `Critical` and `critical` observed). `Automatic` means the platform determines severity dynamically (typical for dt-metric symptoms — the deviation magnitude drives severity).

A `<SymptomDefinition>`'s `<State>` contains exactly one `<Condition>`. (Compound logic happens one level up, at the SymptomSet — see below.)

### `<Condition>` — the predicate

Six observed `type` values, each with its own attribute shape:

#### `type="metric"` — metric threshold

Two flavors, distinguished by `thresholdType`:

```xml
<!-- Static threshold (most common) -->
<Condition type="metric" key="cpu|usage" operator=">" value="80"
           valueType="numeric" thresholdType="static"/>

<!-- Dynamic threshold from another metric -->
<Condition type="metric" key="cpu|demandmhz" operator=">"
           targetKey="cpu|dynamic_entitlement"
           thresholdType="metric"/>

<!-- Dynamic threshold from a property -->
<Condition type="metric" key="cpu|demandmhz" operator=">"
           targetKey="cpu|limit"
           thresholdType="property"/>
```

`thresholdType` ∈ {`static`, `metric`, `property`}. When non-static, the comparison value is read from `targetKey` (another attribute on the same resource). This is **dynamic-threshold-by-reference** — the comparison value moves with the resource's configuration / runtime state.

`operator` ∈ {`=`, `!=`, `<`, `<=`, `>`, `>=`}. `valueType` ∈ {`numeric`, `string`}.

#### `type="dtmetric"` — Dynamic Threshold metric

```xml
<Condition type="dtmetric" key="Network|network_bytes_in"
           operator="above" instanced="false"/>
```

The platform computes a dynamic baseline for the metric and the symptom fires when the value strays outside it. No explicit value; operator is `above` or `below` (the baseline). Universally paired with `severity="Automatic"` or `severity="Warning"` since deviation magnitude drives the actual emitted severity at runtime.

#### `type="htmetric"` — Hard-Threshold capacity metric

```xml
<Condition type="htmetric" key="OnlineCapacityAnalytics|timeRemaining"
           operator="<=" value="30"/>
```

Specialized for capacity / time-remaining metrics. Same shape as static `metric` but the platform interprets the value as days/percent based on the metric's unit. Stair-step pattern observed (`<= 30` → Warning, `<= 20` → Immediate, `<= 10` → Critical).

#### `type="property"` — property comparison

```xml
<Condition type="property" key="config|security|service:SSH|isRunning"
           operator="=" value="true" valueType="string"
           thresholdType="static"/>
```

Same attribute shape as static metric, but applied to a `isProperty="true"` ResourceAttribute. The `key` path resolves to the property's value at evaluation time.

#### `type="msg_event"` — event-message match

```xml
<Condition type="msg_event"
           eventMsg="Hardware sensor health state degraded. Sensor information: Type = memory,.*"
           eventType="11" eventSubType="5"
           operator="regex"/>
```

Fires when the resource receives an event whose message text matches `eventMsg`. `operator` ∈ {`contains`, `equals`, `regex`}. `eventType` / `eventSubType` are integer event classifiers (platform-defined event taxonomy; not adapter-defined). Case observed: both `eventMsg` and `eventmsg` attribute spellings — emit canonical case.

#### `type="fault"` — fault event match

```xml
<Condition type="fault" key="fault|vm|ha"
           faultevent="com.vmware.vc.HA.FailedRestartAfterIsolationEvent"/>
```

Fires on a specific fault event class (canonical fault class name in `faultevent` attribute). The `key` is a fault-category path used for grouping in the UI, not for evaluation. No operator/value.

### Common Condition attributes

- `instanced` — `true|false`. Default false. When true, the condition evaluates per-instance for multi-instance metrics (e.g., per-CPU-core, per-disk) — symptom fires if *any* instance matches.

## `<SymptomSet>` — boolean combinator

Two forms observed.

### Form A (light) — inline single-symptom (mongodb style)

```xml
<SymptomSet ref="symptom_id" operator="and" aggregation="any"
            applyOn="self" negateCondition="false"/>
```

Concise but only references one symptom; the boolean attributes are vestigial.

### Form B (full) — element-children (vSphere style)

```xml
<SymptomSet applyOn="self" operator="or">
    <Symptom ref="DatastoreUsageWarning"/>
    <Symptom ref="DatastoreUsageCritical"/>
</SymptomSet>
```

Use this form. It's the only way to combine multiple symptoms.

### Attributes

- `operator` — `and` | `or` (boolean over the child `<Symptom>` matches)
- `aggregation` — `any` | `percent` (default `any`; `percent` requires a threshold elsewhere — needs further investigation)
- `applyOn` — `self` | `child` | `descendant`. Evaluates symptoms against the resource the alert is bound to (self), its direct children, or its full descendants. **The relationship-traversal-aware part of the alert framework**.
- `negateCondition` — `true|false`. Negates the entire SymptomSet's result.

### Compound: `<SymptomSets operator="and|or">`

Wraps multiple `<SymptomSet>`s for full two-level boolean trees:

```xml
<SymptomSets operator="or">
    <SymptomSet applyOn="self" operator="or">
        <Symptom ref="DatastoreUsageWarning"/>
        <Symptom ref="DatastoreUsageCritical"/>
    </SymptomSet>
    <SymptomSet applyOn="self" operator="and">
        <Symptom ref="DatastoreSpaceRemainingIs"/>
    </SymptomSet>
</SymptomSets>
```

Two levels of boolean — propositional expressions over named symptoms, with relationship-scoped evaluation per inner set.

## `<AlertDefinition>` — the alert

```xml
<AlertDefinition id="datastore_low_space"
                 nameKey="42"
                 adapterKind="VMWARE"
                 resourceKind="Datastore"
                 type="15" subType="22"
                 allowMultipleAlertsPerResource="true"
                 disableInBasePolicy="false"
                 cancelCycle="1" waitCycle="1">
    <State severity="Immediate">
        <Impact type="badge" key="risk"/>
        <SymptomSet ref="datastore_full" operator="and"
                    aggregation="any" applyOn="self" negateCondition="false"/>
        <Recommendations>
            <Recommendation ref="StorageVMotionVM" priority="1"/>
            <Recommendation ref="DeleteUnusedTemplates" priority="2"/>
        </Recommendations>
    </State>
</AlertDefinition>
```

### Attributes

- `id` — stable identifier (often a UUID for VMware's vSphere; descriptive strings for community adapters)
- `nameKey` — int → resources.properties
- `adapterKind`, `resourceKind` — which kind of resource emits this alert
- `type` (int) — alert category code. Observed: `15`, `16`, `20`. Maps to platform alert types (e.g., Performance, Configuration, Availability) — full int→category table not in describe.xml; the platform owns it.
- `subType` (int) — alert sub-category code. Observed: `6, 18, 19, 20, 21, 22, 28, 29`. Same platform-owned table.
- `waitCycle` — cycles the State must evaluate true before alert triggers
- `cancelCycle` — cycles before alert clears
- `allowMultipleAlertsPerResource` — `true|false`. When true, multiple instances of the alert can coexist on the same resource (e.g., per-instance alerts on a multi-disk host).
- `disableInBasePolicy` — `true|false`. When true, the alert is registered but disabled by default; admins enable it via policy.

### `<State>` — singular

Across **all 631 AlertDefinitions inspected** (mongodb 12 + vSphere 119 + others sampled), zero AlertDefinitions had more than one `<State>` child. **The describe.xml schema appears to support multiple states (different severities for different conditions), but in practice each AlertDefinition has exactly one State.** Authors emit multiple AlertDefinitions with different ids when they want a severity ladder over the same metric (e.g., `datastore_warning` + `datastore_critical` referencing different SymptomDefinitions).

### `<Impact>`

```xml
<Impact type="badge" key="health|risk|efficiency"/>
```

Drives which platform-level badge the alert contributes to. `health` (most common), `risk` (capacity / over-utilization concerns), `efficiency` (waste / under-utilization). The 3-badge model is the Aria Operations UI standard.

`type` is always `badge` in observed adapters; other values may exist (not seen).

### `<Recommendations>` (per-state, ordered) — references to top-level Recommendation catalog

```xml
<Recommendations>
    <Recommendation ref="StorageVMotionVM" priority="1"/>
    <Recommendation ref="DeleteUnusedTemplates" priority="2"/>
</Recommendations>
```

`priority` orders the recommendations in the UI; the operator works through them lowest-priority-number first.

## `<Recommendations>` — top-level catalog

The describe.xml has a top-level `<Recommendations>` block (sibling of `<AlertDefinitions>`) declaring the available recommendation snippets that alerts can reference.

```xml
<Recommendations>
    <Recommendation key="StorageVMotionVM">
        <Description nameKey="9045"/>
    </Recommendation>
    <Recommendation key="DeleteUnusedTemplates">
        <Description nameKey="9046"/>
    </Recommendation>
    ...
</Recommendations>
```

- `key` — stable identifier referenced by `<Recommendation ref=…/>` from AlertDefinitions
- `<Description nameKey>` — int → resources.properties (the actual recommendation text)

vSphere has 23; mongodb 12. Recommendations are de-duped — the same recommendation key can be referenced from multiple alerts.

## Adapter-emitted alerts: this entire framework is **declarative**

Adapters don't programmatically raise alerts. They:

1. Declare symptoms in describe.xml as static evaluations over their published metrics/properties/events.
2. Push metric values / property values / events into the platform via the SDK (`addMetricData`, `addEvent`).
3. The **platform's alert engine** evaluates declared symptoms against the data stream and emits AlertDefinitions when the conditions hold for `waitCycle` consecutive collection cycles.

This means: **VCF-CF can fully generate alert frameworks at SPEC-write time** — no per-adapter alert code is needed beyond pushing the underlying metric values correctly.

## Tier 1 (MPB-emitted) limitations vs. full schema

From Pass 7 (`spec/02-describe-xml.md § MPB-emission alert/symptom limits`):

- MPB's `DescribeSymptomStateCondition` has **only `eventMsg`** — no `type`, no `key`, no `operator`, no `value`. **MPB-emitted symptoms are `msg_event`-only** with implicit `contains` (or equivalent) matching. Comparable to mongodb's `dtmetric` symptoms in terms of expressivity but not richness.
- MPB's `DescribeAlertDefinition.state` is singular (matches observed reality — no multi-state alerts in any adapter).
- MPB does NOT emit `htmetric`, `fault`, `property`, threshold-by-reference, regex-matching, multi-symptom boolean compounds, or `applyOn=child|descendant`.

**Tier 1 → Tier 2 promotion triggers from this pass**:

1. Metric-threshold symptoms (`type="metric"`) — Tier 2
2. Property-comparison symptoms (`type="property"`) — Tier 2
3. Dynamic-threshold-via-reference (`thresholdType="metric|property"`) — Tier 2
4. Hard-threshold capacity symptoms (`type="htmetric"`) — Tier 2 (and requires the capacity model anyway)
5. Fault-event symptoms (`type="fault"`) — Tier 2
6. Compound boolean symptoms (`<SymptomSets>` or multi-`<Symptom>` `<SymptomSet>`) — Tier 2
7. Relationship-scoped symptoms (`applyOn="child"|"descendant"`) — Tier 2
8. Per-instance evaluation (`instanced="true"`) — Tier 2

## VCF-CF generator implications

### For Tier 2 (native adapter generation)

VCF-CF's Tier 2 generator should expose this complete grammar as the alert authoring surface. The data model the generator works with should mirror the XML structure 1:1:

```
SymptomDefinition(
    id, nameKey, adapterKind, resourceKind, waitCycle, cancelCycle,
    state: State(severity, condition: Condition(type, key, operator, …))
)

AlertDefinition(
    id, nameKey, adapterKind, resourceKind, type:Int, subType:Int,
    waitCycle, cancelCycle, allowMultipleAlertsPerResource, disableInBasePolicy,
    state: State(
        severity,
        impact: Impact(type, key),
        symptoms: SymptomLogic(  // sealed: Single | Set | Compound
            Single(SymptomSet(ref, operator, applyOn, ...)),
            Set(SymptomSet(operator, applyOn, [Symptom(ref), ...])),
            Compound(SymptomSets(operator, [SymptomSet, ...])),
        ),
        recommendations: [Recommendation(ref, priority), ...]
    )
)

Recommendation(key, nameKey)
```

### For Tier 1 (MPB design generation)

The MPB `BuilderEvent` / `BuilderAlert` model is the input vocabulary VCF-CF generates. Those classes weren't enumerated in detail in Pass 7; will need a focused look (left open). Constrain Tier 1 designs to event-only symptoms; reject (or promote-to-Tier-2) any design that needs the richer grammar above.

### Recommendation catalog: dedupe + share

Recommendations are not adapter-specific in spirit — `StorageVMotionVM` is a vSphere-universal remediation. VCF-CF should let users contribute recommendation entries to a shared catalog and have multiple alerts reference them, mirroring the describe.xml pattern.

### Severity normalization

The wire format accepts case-insensitive severities (`Critical` and `critical` both seen). VCF-CF should emit canonical case (`Info`, `Warning`, `Immediate`, `Critical`, `Automatic`) and accept all-lowercase on input as a normalization step.

### Type / SubType code table — RESOLVED (Pass 21)

`type` and `subType` are integer codes whose meaning is platform-owned. **The MPB runtime's `BuilderAlertType` and `BuilderAlertSubType` enums expose the canonical mapping** (extracted from bytecode constant pool in Pass 21):

**`type` code → category**:

| Code | Category | MPB enum name |
|---|---|---|
| 15 | Application | `APPLICATION` |
| 16 | Virtualization | `VIRTUALIZATION` |
| 17 | Hardware | `HARDWARE` |
| 18 | Storage | `STORAGE` |
| 19 | Network | `NETWORK` |
| **20** | (unknown — Tier 2 only) | **NOT in MPB enum** |

vSphere uses type=20 in 12 of its AlertDefinitions; mongodb only uses 15. Type=20 is a Tier-2-only category that MPB cannot author. (Likely "vSphere-specific" or "Performance" — Broadcom-internal naming.)

**`subType` code → category**:

| Code | Category | MPB enum name |
|---|---|---|
| 18 | Availability | `AVAILABILITY` |
| 19 | Performance | `PERFORMANCE` |
| 20 | Capacity | `CAPACITY` |
| 21 | Compliance | `COMPLIANCE` |
| 22 | Configuration | `CONFIGURATION` |
| **6, 28, 29** | (Tier 2 only) | **NOT in MPB enum** |

vSphere uses subTypes {6, 18, 19, 20, 21, 22, 28, 29}. Codes 6/28/29 are Tier-2-only.

**Default for unknown category**: emit `(15, 22)` — that's the "general APPLICATION / CONFIGURATION" pairing mongodb uses as its catch-all.

**For Tier 2 generators**: expose all 6 type codes and 8 subType codes the platform accepts, including the Tier-2-only ones (20 for type; 6, 28, 29 for subType). The MPB enum is a STRICT SUBSET of what the platform accepts — Tier 2 has access to additional categorizations.

## Open follow-ups

1. **Platform's alert `type`/`subType` int → category lookup table**: need to find this, likely in the appliance's own configuration or in the SDK's alert-related enum classes. Not yet enumerated.
2. **`aggregation="percent"` semantics**: 14 cases in vSphere; threshold attribute not yet identified. May require examining the platform's `<SymptomSet>` evaluator implementation.
3. **MPB `BuilderEvent` schema**: Pass 7 did not enumerate the event/alert side of `BuilderFile` in depth — needed for full Tier 1 alert-generation specification.
4. **Other elements inside `<State>`**: `<Impact>` may have non-badge `type` values; `<Recommendations>` may have `priority` beyond integers (e.g., conditional). Not observed but not exhaustively ruled out.
5. **Cross-MP symptoms**: can a `<SymptomDefinition>` declared in adapter A reference a metric owned by adapter B (foreign metric)? Not observed in mongodb/vSphere — likely no, since the symptom's `adapterKind`/`resourceKind` scope it to a single MP. But cross-MP relationship traversal via `applyOn="descendant"` may cross MP boundaries — needs verification.
