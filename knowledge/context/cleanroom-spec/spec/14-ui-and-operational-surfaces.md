# 14 — UI and Operational Surfaces

**Status**: Pass 20 (2026-05-16).
**Scope**: the declarative surfaces that drive UI behavior + runtime operational interactions. Six elements:

1. **`<Methods>`** — define callable functions with typed parameters (the "what")
2. **`<Action>`** — bind methods to resource contexts + UI invocation forms (the "where/how/UI")
3. **`<Faults>`** — pair-based event-driven alerts (alternative to Symptoms/AlertDefinitions)
4. **`<LaunchConfigurations>`** — declarative UI deep-link templates
5. **`<PowerState>`** — power-state declaration (per ResourceKind)
6. **`<Icon>`** — power-state-and-condition driven icon decoration trees (per ResourceKind)

**Evidence**: vSphere (`vmwarevi_adapter3`) is the canonical source — 66 Methods, 42 Actions, 89 FaultStates, 34 LaunchConfigs, 28 PowerState/Icon blocks. AppOSUCPAdapter3 has 77 Methods (largest Method count). VirtualAndPhysicalSANAdapter3 has 477 FaultStates (largest Faults user). mongodb has lighter touch (no PowerState/Icon, 0 LaunchConfigs).

## Methods + Actions — the user-invokable-operations framework

Two-layer model: `<Method>` declares the callable + parameter schema; `<Action>` binds methods to resource contexts and drives the UI invocation flow.

### `<Methods>` — the callable catalogue

Lives as a top-level element under `<AdapterKind>` (alongside `<ResourceKinds>`, `<Recommendations>`, etc.).

```xml
<Methods>
    <Method key="PowerOffVM" name="Power Off VM" nameKey="30075">
        <Parameter key="mOR" isRequired="true" nameKey="3026">
            <SimpleMethodInfoList dataType="String"/>
        </Parameter>
    </Method>
    <Method key="MoveVM" name="Move VM" nameKey="20031">
        <Parameter key="mOR" isRequired="true" nameKey="20032">
            <SimpleMethodInfoList dataType="String">
                <Metadata key="translationExpression" value="identifier('VMEntityObjectID')"/>
                <Metadata key="groupedValueExpression" value="true"/>
            </SimpleMethodInfoList>
        </Parameter>
        <Parameter key="host" isRequired="true" nameKey="20032">
            <SimpleMethodInfoList dataType="String">
                <Metadata key="translationExpression" value="identifier('VMEntityObjectID')"/>
            </SimpleMethodInfoList>
        </Parameter>
        <!-- more Parameters -->
        <Metadata key="disableBatching" value="true"/>    <!-- method-level options -->
    </Method>
</Methods>
```

### `<Method>` attributes

| Attribute | Purpose |
|---|---|
| `key` (required) | Stable identifier; referenced from `Action.ActionContext.methodKey` |
| `name` | Internal name (often equal to `key`) |
| `nameKey` | Int → resources.properties for display name |

### `<Parameter>` (one per method input)

| Attribute | Purpose |
|---|---|
| `key` (required) | Stable parameter name; passed to `onAction(ActionParam)` at runtime |
| `isRequired` (bool) | Whether the parameter must be supplied |
| `nameKey` | Int → resources.properties for UI label |
| `isCensored` (bool, optional) | Mask the value in UI / logs (for passwords / payloads) |

### `<SimpleMethodInfoList dataType=…>` (parameter type)

Each parameter wraps its type in a `<SimpleMethodInfoList>` (or sibling element variant — see XSD § 02a). The `dataType` is the **17-value PropertyDatatypeType enum**: `String`, `SInt32`, `UInt32`, `SInt64`, `UInt64`, `Decimal`, `Double`, `Boolean`, `DateTime`, `Binary`, `Byte`, `Enum`, `TypeName`, `Any`, `Integer`, `SnapshotData`, `ProcessesData`.

Type wrapper variants (per XSD § 02a):
- `<SimpleMethodInfoList>` — list of values
- `<SimpleMethodInfoSet>` — set (no duplicates)
- `<SimpleMethodInfo>` — single value
- `<ComplexMethodInfoList>` / `<ComplexMethodInfoSet>` / `<ComplexMethodInfoMap>` / `<ComplexMethodInfo>` — structured types

Most Methods observed use `<SimpleMethodInfoList dataType="String">` or `<SimpleMethodInfoList dataType="Integer">`. Complex variants exist but rare in the corpus.

### `<Metadata>` (key-value annotations)

Both Parameter-level and Method-level. Observed keys:

| Key | Meaning |
|---|---|
| `translationExpression` | SpEL expression to translate the user-supplied raw value into the form the adapter expects (e.g., `identifier('VMEntityObjectID')` looks up an identifier on the contextual resource) |
| `groupedValueExpression` | bool; whether the parameter is a "list of resources" semantically (allows batch operations on multiple selected resources) |
| `disableBatching` | bool; method-level; prevents batching multiple resource invocations into a single Method call (each resource gets its own invocation) |

### `<Action>` — bind Method to UI invocation context

Top-level element under `<AdapterKind>`. NOT wrapped in `<Actions>` despite what the XSD might suggest — the corpus shows `<Action>` elements freestanding at the same level as `<Methods>` and `<Recommendations>`.

```xml
<Action key="Power Off VM" actionType="update"
        adapterEndpointExpression="attribute('summary|vcuuid')"
        resourceEndpointExpression="<long SpEL expression returning resource id OR value('invalid')>"
        scheduleEnabled="true">
    <ResourceContext key="PowerOffVM"
                     adapterKind="VMWARE"
                     resourceKind="VirtualMachine"
                     nameKey="30005"
                     resourceTarget="(isVMNotEligibleForAction() or ...) ? {} : resourceUuid"/>
    <ResourceContext key="PowerOffVMsOnHost" ... resourceKind="HostSystem" .../>
    <ResourceContext key="PowerOffVMsOnCluster" ... resourceKind="ClusterComputeResource" .../>
    <ActionContext key="PowerOffVM"
                   helpId="actions.poweroff.vm"
                   methodKey="PowerOffVM">
        <ActionContextField key="Name" component="textfield" dispOrder="0" nameKey="30006"
                            value="resourceNameAndIcon"/>
        <ActionContextField key="mOR" hidden="true" nameKey="3026"
                            parameter="mOR"
                            value="identifier('VMEntityObjectID')"/>
        <ActionContextField key="Idle VM" component="textfield" dispOrder="1" nameKey="30007"
                            value="isAttributeDisabledFromPolicy(...) ? '' : resourceAttributeFormat(...)"/>
        <!-- more ActionContextField — typically one per Method.Parameter plus extra UI fields -->
    </ActionContext>
</Action>
```

### `<Action>` attributes

| Attribute | Purpose |
|---|---|
| `key` (required) | Stable action identifier |
| `actionType` | `update` (default — mutates target state), `schedule` (creates a scheduled action), possibly more (per XSD enum) |
| `adapterEndpointExpression` (required) | SpEL expression returning the adapter-instance identifier to invoke against (e.g., `attribute('summary|vcuuid')` for vSphere's vCenter UUID) |
| `resourceEndpointExpression` (required) | SpEL expression returning the resource-side endpoint (or `value('invalid')` to skip — that's the convention for "this resource is not eligible") |
| `scheduleEnabled` (bool) | Whether the action can be scheduled (vs. invoked immediately only) |

### `<ResourceContext>` — applicable-to declaration

One or more per Action. Each declares: "this action applies to resources of this kind, and for a given selection compute the target set this way."

| Attribute | Purpose |
|---|---|
| `key` (required) | Unique within the Action |
| `adapterKind`, `resourceKind` (required) | Scope |
| `nameKey` (required, int) | Display name in UI |
| `resourceTarget` (required) | SpEL expression returning the target-set: either a single `resourceUuid`, a list (e.g., `getDescendantsAndCheckAttributes('VMWARE', 'VirtualMachine', 1, 1, true).![resourceUuid]`), or `{}` to skip |

The cross-kind pattern is powerful: vSphere's "Power Off VM" action declares ResourceContexts for VirtualMachine (direct), HostSystem (all VMs on the host), AND ClusterComputeResource (all VMs in the cluster). One action, three points of invocation in the UI.

### `<ActionContext>` — UI invocation form

| Attribute | Purpose |
|---|---|
| `key` (required) | Stable identifier; references this invocation flow |
| `methodKey` (required) | References the `<Method key>` to call |
| `helpId` | Anchor for in-product help docs |
| `automationPolicy` | `context` (use the contextual resource's automation policy) / `none` / others |
| `selectionModel` | `all` (apply to all selected resources) / others |

### `<ActionContextField>` — per-field UI binding

| Attribute | Purpose |
|---|---|
| `key` (required) | Field identifier in UI |
| `parameter` | Method parameter name this field's value gets passed to (omit for display-only fields) |
| `nameKey` (required, int) | UI label |
| `component` | `textfield` (most common), other component types per XSD |
| `dispOrder` | UI ordering |
| `hidden` (bool) | Don't display in UI but still pass to method |
| `input` (bool) | Distinguishes input fields from display-only |
| `value` (required) | SpEL expression returning the field value at invocation time |

The `value` expression has access to:
- `identifier('KEY')` — read a ResourceIdentifier value from contextual resource
- `attribute('metric|path')` — read an attribute value
- `resourceNameAndIcon` — formatted name + icon (cosmetic)
- `resourceAttributeFormat(key, type, suffix?)` — formatted attribute value
- `parents/children/descendants/contextResources` — relationship traversal
- `value('literal')` — literal value
- `localizedString(nameKey, adapterKind, fallback)` — i18n lookup
- `isAttributeDisabledFromPolicy(...)` — policy-aware UI shaping

### Action invocation flow

1. User selects resource(s) in UI
2. Platform evaluates `Action.resourceEndpointExpression` for each — invalid ones disabled
3. User clicks Action; platform evaluates `ActionContext.ActionContextField.value` for each field → builds the UI form
4. User confirms (or modifies inputs)
5. Platform builds parameter map from ActionContextField values (filtered by `parameter` attribute)
6. Platform calls adapter's `onAction(ActionParam)` (via `ActionableAdapterInterface`) — see § 04
7. ActionParam contains: action key, target resource(s), parameter map, etc.
8. Adapter performs the action against the source system

This is fully declarative on the platform side; the adapter only needs to implement `onAction()`. **VCF-CF Tier 2 generators can produce the full UI invocation surface from the Action declarations** — no UI code needed in the adapter.

### Method-Action lifecycle gotcha

Methods are declared first; Actions reference them by `methodKey`. A pak with an Action whose `methodKey` doesn't match any `<Method key>` will fail validation. Generators must emit Methods BEFORE Actions or validate the cross-references.

## `<Faults>` — pair-based event-driven alerts

Already partially documented in spec/02a (XSD reading). Adds runtime structural detail from vSAN's 477 instances:

```xml
<Faults>
    <FaultState key="ClusterDiskFreeSpaceHealth"
                resourceKind="VirtualSANDCCluster"
                nameKey="400">
        <ProblemEvent key="ClusterDiskFreeSpaceHealthTurnYellow"
                      faultScore="30"
                      nameKey="500"/>
        <ProblemEvent key="ClusterDiskFreeSpaceHealthTurnRed"
                      faultScore="100"
                      nameKey="501"/>
        <ClearEvent key="ClusterDiskFreeSpaceHealthTurnGreen"/>
    </FaultState>
</Faults>
```

### Critical refinement: multi-severity fault progressions

The vSAN corpus reveals that **a single FaultState can declare MULTIPLE ProblemEvents at escalating faultScores** (e.g., Yellow=30 then Red=100), all sharing ONE ClearEvent. This is the standard pattern in vSAN — every fault has Yellow + Red ProblemEvents.

The runtime semantics:
- Adapter pushes `FaultExternalEvent(eventId="ClusterDiskFreeSpaceHealthTurnYellow")` → fault fires at faultScore=30 severity
- Source system worsens → adapter pushes `FaultExternalEvent(eventId="ClusterDiskFreeSpaceHealthTurnRed")` → fault escalates to faultScore=100
- Source system recovers → adapter pushes `FaultExternalEvent(eventId="ClusterDiskFreeSpaceHealthTurnGreen")` → fault clears (any severity)

vs. the Symptom/AlertDefinition framework which evaluates DECLARED conditions over pushed METRICS. Faults are PUSHED EVENTS that name themselves.

### When to use Faults vs Symptoms

| Choice | Use when |
|---|---|
| **Faults** | The source system already emits trigger/clear event pairs that the adapter can map directly. Multi-severity ladders are first-class. |
| **Symptoms + AlertDefinitions** | The adapter pushes metrics and wants the platform to evaluate thresholds. Richer condition logic (metric/property/dtmetric/fault/msg_event/htmetric — see spec/08). |

Many adapters use both. Vsphere has 89 Faults (for vSphere-issued health-state events) AND 517 Symptoms (for adapter-evaluated metric thresholds).

### Attributes (XSD-confirmed + corpus-validated)

`<FaultState>`:
- `key` (required) — unique per resource kind
- `resourceKind` (required) — what kind of resource emits faults of this type
- `nameKey` (required) — display name
- `autoGenerateAlertDefs` (bool, optional, default false) — auto-generate SymptomDefinitions + AlertDefinitions
- `adapterComputed` (bool, VMware-internal)
- `perDevice` (bool, VMware-internal — for faults with sub-device granularity, e.g., NICs on a host)

`<ProblemEvent>`:
- `key` (required) — the `eventId` value the adapter pushes to trigger this fault
- `faultScore` (required, 1-100) — severity in faultScore units
- `nameKey` (required) — display name for THIS specific severity tier

`<ClearEvent>`:
- `key` (required) — the `eventId` value to push to clear the fault
- `nameKey` (optional) — display name

Multiple ProblemEvents share one ClearEvent. (Multiple ClearEvents are schema-permitted but not observed.)

## `<LaunchConfigurations>` — declarative UI deep-links

Already partially documented in spec/02a. Adds runtime examples from vSphere (34 LaunchConfigs).

```xml
<LaunchConfigurations>
    <LaunchConfig key="Launch_to_vCenter_6.7"
                  active="isVCenterVersionEqualOrNewerThan('6.7') and !isVCenterVersionEqualOrNewerThan('7.0')"
                  adapterKindKey="VMWARE"
                  nameKey="140"
                  resourceKindKey="VMwareAdapter Instance">
        <HostProtocol>{myUrl}</HostProtocol>
        <UriTemplate>/ui/#?extensionId=vsphere.core.inventory.serverObjectViewsExtension&amp;objectId=urn:vmomi:Folder:group-d1:{vcuuid}&amp;navigator=vsphere.core.viTree.hostsAndClustersView</UriTemplate>
        <Variable name="myUrl">'https://' + identifier('VCURL')?.trim().replaceAll('^https?://(.*)/sdk', '$1')</Variable>
        <Variable name="vcuuid">attribute('summary|vcuuid')</Variable>
    </LaunchConfig>
</LaunchConfigurations>
```

### Substitution syntax

LaunchConfigurations use **`{varname}` substitution** (curly braces only, no `$`) — DISTINCT from the `${expression}` syntax used in CapacityDefinition aliases and SpEL contexts. The variables are computed by `<Variable name="...">expression</Variable>` children.

Variable expressions are full SpEL (or Jexl, or similar — the syntax matches what Action expressions use):
- `identifier('VCURL')` — resource identifier
- `attribute('summary|vcuuid')` — resource attribute  
- `'literal' + identifier(...)` — string concatenation
- `?.trim()`, `.replaceAll(...)` — method chaining with null-safe navigation
- Regex replacement patterns

### Conditional visibility via `active`

The `active` attribute is a SpEL **predicate** — when false, the link doesn't appear in UI. vSphere uses this for version-gated UI (e.g., a 6.7-only link that hides on 7.0+ vCenters):

```
active="isVCenterVersionEqualOrNewerThan('6.7') and !isVCenterVersionEqualOrNewerThan('7.0')"
```

Available predicate helpers (vSphere examples):
- `isVCenterVersionEqualOrNewerThan(version)` — adapter-specific helper exposed via the platform
- `isVCenterVersionEqualOrNewerThan(adapterInstance('VMWARE'), version)` — cross-adapter version check

Adapters can presumably register custom helper functions (this is an extension surface; not directly observable from describe.xml alone).

### Matching attributes (all regex per XSD)

- `adapterKindKey` — regex matching the contextual resource's adapter kind
- `resourceKindKey` — regex matching the resource kind
- `alertType` / `alertSubType` — regex matching alert taxonomy (when launched from an alert)

### `<ConfigMapping>` — where the link appears

The XSD shows `<ConfigMapping uiConfigKey launchConfigKey dispOrder/>` for placement. Values include `resource-detail`, `environment-overview`, `alerts-overview`. Not extensively observed in vSphere's LaunchConfigurations block but present.

## `<PowerState>` — per-resource power-state declaration

```xml
<ResourceKind key="VirtualMachine" ...>
    <!-- identifiers, attributes -->
    <PowerState alias="summary|runtime|powerState">
        <PowerStateValue key="ON" value="Powered On"/>
        <PowerStateValue key="OFF" value="Powered Off"/>
        <PowerStateValue key="SUSPENDED" value="Suspended"/>
        <PowerStateValue key="UNKNOWN" value="Unknown"/>
    </PowerState>
    <Icon>
        <!-- decision tree — see below -->
    </Icon>
</ResourceKind>
```

`<PowerState alias>` points to a `<ResourceAttribute>` key whose runtime value represents the power state. `<PowerStateValue key value>` maps the raw runtime value → a canonical key (used by the platform for filtering, capacity-analysis exclusions, icon-decoration).

Canonical keys observed: `ON`, `OFF`, `SUSPENDED`, `UNKNOWN`, `STANDBY`. The mapping is per-adapter — vSphere maps `"Powered On"` → `ON`, NSX (if it had PowerState) might map `"online"` → `ON`. The canonical key is what platform analytics use; the value is the source-system string.

**Capacity analysis uses PowerState** to exclude powered-off resources from utilization calculations (the `<PowerState alias>` reference inside `<ResourceContainer>` — see spec/09).

## `<Icon>` — power-state-and-condition decision-tree decorations

Lives inside `<ResourceKind>` next to `<PowerState>`. A multi-level decision tree that walks properties and PowerState to build up an icon name suffix.

```xml
<Icon>
    <Condition property="summary|config|type">
        <Case suffix="template" value="template"/>
        <Case suffix="srm_placeholder" value="srm_placeholder"/>
        <Case suffix="ft_primary" value="ft_primary">
            <Condition property="summary|runtime|powerState">
                <Case suffix="ft_primary_power_on" value="Powered On"/>
                <Case suffix="ft_primary_standby" value="Suspended"/>
            </Condition>
        </Case>
        <Case suffix="managed" value="VMOperator">
            <Condition property="summary|runtime|powerState">
                <Case suffix="managed_power_on" value="Powered On"/>
                <Case suffix="managed_power_standby" value="Suspended"/>
            </Condition>
        </Case>
        <!-- more cases -->
    </Condition>
</Icon>
```

### Elements

`<Condition property="<metric-key>">` — switch on a property's value. Properties are referenced by their full metric-path key.

`<Case suffix="<name>" value="<property-value>">` — branch when the property matches `value`. The `suffix` is appended to the icon name. Cases can contain NESTED `<Condition>` for multi-level decision trees.

### Icon naming convention

The runtime walks the decision tree from root, appending suffixes:

- Starting icon name: `<resource-kind-icon-base>` (declared elsewhere, e.g., `vm`)
- Walk Conditions, take matching Cases, append suffixes
- Final icon: `<base>_<suffix1>_<suffix2>...svg`

Example: a VM with `summary|config|type="ft_primary"` and `summary|runtime|powerState="Powered On"` gets icon `vm_ft_primary_power_on.svg`.

The decision tree gives adapters very fine-grained UI affordances — vSphere has 28 PowerState/Icon blocks covering different VM types (template, srm-placeholder, ft-primary, ft-secondary, managed, VMOperator, SupervisorControlPlane, eam-agent, etc.) × power states.

### Where icon files live

The `<adapter>/conf/images/` or `<adapter>/conf/icons/` directory (per pak convention — varies). Each icon file is named per the suffix-building algorithm.

## Tier 2 generator implications

### Methods + Actions are the biggest authoring-UX win

Letting users declare "expose this operation in the UI on resources matching X" produces a fully-functional UI invocation form WITHOUT writing UI code. VCF-CF should make this the headline Tier 2 feature.

Two authoring tiers:

1. **Simple action** — user declares "call method M with parameters P1, P2" → VCF-CF generates Method + Action + ActionContext + ActionContextField stubs with sensible defaults.
2. **Rich action** — user declares the SpEL expressions for ResourceContext.resourceTarget, ActionContextField.value, etc. → VCF-CF emits verbatim.

### Action SpEL/expression language is its OWN sub-DSL

The expressions in `Action.resourceEndpointExpression`, `ResourceContext.resourceTarget`, `ActionContextField.value`, `LaunchConfig.active`, `LaunchConfig.Variable` use a SpEL-like syntax with helper functions (`identifier`, `attribute`, `parents`, `descendants`, `value`, `isAttributeDisabledFromPolicy`, `localizedString`, etc.). 

VCF-CF needs to either:
1. Expose the full expression language to advanced users (with a code-editor UI)
2. Generate common patterns from higher-level abstractions ("invoke on selected VM" → resourceTarget expression generated automatically)
3. Both — make 80% of cases pattern-generated, fall back to raw expressions for the long tail

### Faults are valuable when the source system already has fault events

If an adapter's source system already publishes trigger/clear events (Kubernetes' Events, vCenter's Faults, etc.), `<Faults>` is dramatically cheaper than building Symptoms+AlertDefinitions. VCF-CF should detect source-system event mapability and propose Faults as the path.

Multi-severity `<ProblemEvent>` chains (Yellow/Red pattern from vSAN) are first-class — generators should support that.

### LaunchConfigurations are cheap power-features

A single LaunchConfig adds a deep-link button to the UI. For adapters representing systems with their own native UIs (vCenter, NSX Manager, K8s dashboards, vendor consoles), this is a strong "this MP integrates well" affordance.

VCF-CF should:
- Auto-generate "Launch to source-system UI" for the adapter instance kind
- Let users add per-resource-kind launches via templates ("Launch to VM detail page in vCenter")
- Expose the `active` predicate for version/feature gating

### PowerState + Icon are mostly vSphere-territory but worth exposing

vSphere is the ONLY adapter in the corpus with rich PowerState+Icon trees (28 blocks). Most adapters don't need this depth, but the framework is there for adapters whose UI representation benefits from per-state decoration.

VCF-CF should make these OPTIONAL with sensible defaults — don't force every adapter to declare PowerState if the source has no power semantics. When declared, the icon decision-tree authoring is gnarly (multi-level conditions); VCF-CF could auto-generate from a flat "(propertyValue, powerState) → iconSuffix" table.

### ResourceCount + Concurrency hint

Vsphere's Action expressions show heavy use of `getDescendantsAndCheckAttributes(...)` and `contextResourcesCache[...]`. The expression evaluator has access to caches (presumably to avoid O(n²) on large selections). VCF-CF generators should produce expressions that use these caches when targeting many resources.

## Surfaces NOT enumerated in this pass

- **Full XSD `actionType` enum** — only `update` and `schedule` observed
- **Full `selectionModel` enum** — only `all` observed
- **Full `automationPolicy` enum** — `context` and `none` observed
- **Full `component` enum for ActionContextField** — only `textfield` observed; others (dropdown, checkbox, etc.) likely exist
- **`<Icon>` resourceKind-base icon-name declaration** — where the BASE name (e.g., `vm`) is set; not in `<Icon>` itself
- **The SpEL/expression-language full grammar** — significant authoring surface; partially inferable from examples but no formal docs in our corpus

## Open follow-ups

1. **Action expression-language grammar** — enumerate all helper functions, operators, type semantics. Could be its own RE pass against the platform jars (search for the SpEL evaluator implementation).
2. **`<Icon>` resourceKind base-name source** — where the icon's base name is declared; the suffix-building algorithm needs a starting point that we haven't found in describe.xml.
3. **Action result handling** — what does `onAction()` return and how does the platform render that? `MethodResultType` exists in XSD (spec/02a) but not explored.
4. **Method vs Recommendation.Action linkage** — recommendations can declare `<Action actionAdapterKey targetResourceKind actionKey>` (spec/08), referencing an Action by key. The cross-MP referencing model (an alert in one adapter's MP can invoke an action in another MP's) is powerful — confirm runtime semantics.
5. **CustomGroupMetrics** — still Navani-gap (per Pass 18 § Open follow-ups).
