# Action Wire Format Deep Dive

**Date**: 2026-05-27
**Investigator**: api-explorer
**Primary reference**: vmwarevi_adapter3 (vSphere adapter) describe.xml
**Sources**: XSD 6.3.0, vSphere describe.xml (13,279 lines), live devel instance API, existing cleanroom specs (04, 14, 02a)

## Executive summary

The action subsystem is a two-layer declarative model: **Methods** define callable functions with typed parameters; **Actions** bind methods to resource contexts and drive the UI invocation flow. The vSphere adapter declares **25 unique Action keys** (24 active, 1 commented out), **23 unique Method keys** (with "none" appearing twice), and **67 ResourceContext entries** providing invocation points across multiple resource kinds. The live API reports these as **142 action definitions** system-wide (one per adapter-kind + action-key + resource-kind tuple).

This document extends cleanroom specs 04-actions.md and 14-ui-and-operational-surfaces.md with complete schema evidence from the XSD and vSphere adapter.

---

## 1. Complete action schema (XSD-authoritative + runtime extensions)

### 1.1 `<Actions>` container

```xml
<Actions reuseCollectingAdapterInstanceForActionRun="true">
    <Action .../>
    ...
</Actions>
```

Container-level attribute (NOT in XSD -- runtime extension):
- `reuseCollectingAdapterInstanceForActionRun` (bool) -- when true, the platform dispatches action calls to the same adapter instance that performs collection for the target resource, rather than a separate action-specific adapter instance.

### 1.2 `<Action>` element

XSD type: `ActionType`

**XSD-declared attributes:**

| Attribute | Type | Required | Default | Notes |
|---|---|---|---|---|
| `key` | string | YES | -- | Stable action identifier. API ID = `{adapterKind}-{key}` |
| `actionType` | enum | YES | -- | XSD: `update`, `read`. See below for runtime extensions |
| `adapterEndpointExpression` | string (SpEL) | YES | -- | Evaluated against adapter-instance resource; result matched to `resourceEndpointExpression` to route to correct adapter instance |
| `resourceEndpointExpression` | string (SpEL) | YES | -- | Evaluated against target resource; `value('invalid')` convention means "not eligible" |
| `hidden` | bool | NO | false | Hidden from UI menu; action still invokable via API |
| `canRecommend` | string (bool) | NO | "true" | Whether this action may be associated with Recommendations |

**Runtime-recognized attributes (NOT in XSD but used in vSphere):**

| Attribute | Observed values | Purpose |
|---|---|---|
| `scheduleEnabled` | "true" | Whether the action appears in the scheduling UI |
| `isMultiSelectAllowed` | "false" | Restricts action to single-resource selection |

**actionType values:**

| Value | XSD | Observed | Semantics |
|---|---|---|---|
| `update` | YES | 24 instances | Mutates target system state |
| `read` | YES | 0 instances | Read-only (no side effects) |
| `schedule` | NO (runtime extension) | 1 instance | Creates a scheduled action (Schedule Rebalance Workload) |

### 1.3 `<ResourceContext>` element

XSD type: `ResourceContextType`

| Attribute | Type | Required | Notes |
|---|---|---|---|
| `key` | string | YES | Unique within the Action. Displayed as action name in UI when localization absent |
| `nameKey` | int | YES | resources.properties lookup for display name |
| `adapterKind` | string | YES | Adapter kind scope |
| `resourceKind` | string | YES | Resource kind scope |
| `resourceTarget` | string (SpEL) | YES | Expression returning target resource(s): `resourceUuid`, list via `.![resourceUuid]`, or `{}` to skip |
| `filter` | string | NO | Currently ignored per XSD docs; intended for future resource filtering |

**Runtime-recognized attributes (NOT in XSD):**

| Attribute | Observed values | Purpose |
|---|---|---|
| `isGroupedResource` | "true" | Marks the context as operating on grouped/batched resources |
| `workbenchEnabled` | "true" | Enables the action from the workbench UI surface |

**Cross-kind invocation pattern (vSphere canonical):**

Most vSphere actions declare 3 ResourceContexts for one action:
1. Direct -- e.g., `VirtualMachine` with `resourceTarget="resourceUuid"`
2. Host-scoped -- e.g., `HostSystem` with `resourceTarget="getDescendantsAndCheckAttributes('VMWARE', 'VirtualMachine', 1, 1, true).![resourceUuid]"`
3. Cluster-scoped -- e.g., `ClusterComputeResource` with depth=2

This lets one action appear at three levels of the hierarchy.

### 1.4 `<ActionContext>` element

XSD type: `ActionContextType`

| Attribute | Type | Required | Enum values | Notes |
|---|---|---|---|---|
| `key` | string | YES | -- | Stable identifier for this invocation step |
| `methodKey` | string | YES | -- | References `<Method key>` |
| `nameKey` | int | NO | -- | Display name (omitted = use key) |
| `helpId` | string | NO | -- | Context-sensitive help anchor |
| `selectionModel` | enum | NO | `single`, `multi`, `all` | How many objects can be selected in the action dialog |
| `automationPolicy` | enum | NO | `none`, `target`, `context`, `both` | Policy check method for automation. `none` = cannot be automated |
| `order` | int | NO | -- | Multi-step action ordering (NOT in XSD -- runtime extension). vSphere uses `order="0"` and `order="1"` for two-step snapshot actions |

**Multi-step actions:** vSphere's snapshot deletion actions use two ActionContexts with `order="0"` (retrieve) and `order="1"` (delete). The first step calls a Python script that returns data; the second step uses `getValueAsString(key)` expressions to read from that data.

### 1.5 `<ActionContextField>` element

XSD type: `ActionContextFieldType`

| Attribute | Type | Required | Default | Notes |
|---|---|---|---|---|
| `key` | string | YES | -- | Field identifier |
| `nameKey` | int | YES | -- | UI label via resources.properties |
| `component` | enum | NO | `textfield` | See component type catalog below |
| `dispOrder` | int | NO | 0 | Display ordering (0 = random ordering) |
| `value` | string (SpEL) | NO | -- | Expression evaluated at invocation time |
| `hidden` | bool | NO | false | Don't display in UI; still passed to method if `parameter` set |
| `input` | bool | NO | false | Whether user can modify the populated value |
| `parameter` | string | NO | -- | Method parameter key this field maps to. Omit for display-only fields |

### 1.6 Complete `component` type catalog

**XSD-enumerated (9 types):**

| Component | Output type | Description | vSphere usage count |
|---|---|---|---|
| `textfield` | String | Text display / string input. Default. Most common. | 162 |
| `numberfield` | Integer | Integer display (positive or negative) | 24 |
| `positiveintegerfield` | Integer (positive) | Positive integer input | 13 |
| `checkcolumn` | Boolean | Checkbox for yes/no | 12 |
| `combobox` | String | Dropdown single-select from predetermined list | 4 |
| `decimalfield` | Decimal | Decimal value display/input | 6 |
| `booleanimage` | Boolean | Boolean rendered as image (true/false icon) | 2 |
| `booleanyesrednoblack` | Boolean | Red "Yes" for true, Black "No" for false | 1 |
| `textarea` | String | Multi-line text area | 2 |

**Runtime extension (NOT in XSD, used in vSphere):**

| Component | Output type | Description | vSphere usage count |
|---|---|---|---|
| `percentbar` | Decimal | Horizontal percentage bar visualization | 12 |

The `percentbar` component is used exclusively in the Rebalance Workload action's impact grid to show CPU/memory/storage workload before and after rebalancing.

### 1.7 `combobox` value expression pattern

The `combobox` component uses the `createComboBox()` SpEL function:

```
createComboBox(
    {displayLabel1, displayLabel2, ...},    // display values (often localizedString calls)
    {internalValue1, internalValue2, ...},  // internal values sent to method
    defaultValue                             // pre-selected value (can be an expression)
)
```

Example from DRS Automation:
```
createComboBox(
    {localizedString(30087, 'VMWARE', 'Disabled'),
     localizedString(30088, 'VMWARE', 'Manual'),
     localizedString(30089, 'VMWARE', 'Partial Automated'),
     localizedString(30090, 'VMWARE', 'Fully Automated')},
    {'disabled','manual','partiallyAutomated','fullyAutomated'},
    'false'.equals(attribute('configuration|drsConfig|enabled'))
        ? 'disabled' : attribute('configuration|drsConfig|defaultVmBehavior')
)
```

---

## 2. `<Methods>` complete schema

### 2.1 `<Method>` element

XSD type: `MethodType`

| Attribute | Type | Required | Notes |
|---|---|---|---|
| `key` | string | YES | Referenced by ActionContext.methodKey |
| `name` | string | YES | Internal name (XSD says "for future use; provide same as key") |
| `nameKey` | int | YES | resources.properties display name |
| `executable` | string | NO | Script/workflow name. Format: `builtin:scriptName.py` for platform-bundled scripts |

Children (all optional, unbounded):
- `<Parameter>` -- method input parameters
- `<Result>` (MethodResultType) -- method return type (not observed in vSphere)
- `<Exception>` (ExceptionType) -- declared exceptions (not observed in vSphere)
- `<Metadata>` -- key-value annotations

### 2.2 `<Parameter>` element

XSD type: `ParameterType`

| Attribute | Type | Required | Notes |
|---|---|---|---|
| `key` | string | YES | Parameter name passed to onAction() |
| `nameKey` | int | YES | Display name |
| `isRequired` | bool | YES | Whether the parameter must be supplied |
| `isCensored` | bool | NO | Mask value in UI/logs (observed for password field in execScript) |

Parameter contains exactly one type wrapper child:

| Type wrapper | Cardinality | Notes |
|---|---|---|
| `<SimpleMethodInfo>` | Single value | Scalar |
| `<SimpleMethodInfoList>` | List | Most common in vSphere |
| `<SimpleMethodInfoSet>` | Set (no dupes) | Not observed |
| `<ComplexMethodInfo>` | Single structured | Not observed |
| `<ComplexMethodInfoList>` | List of structured | Not observed |
| `<ComplexMethodInfoSet>` | Set of structured | Not observed |
| `<ComplexMethodInfoMap>` | Map of structured | Not observed |

All type wrappers carry `dataType` attribute from the `PropertyDatatypeType` enum (17 values):
`String`, `SInt32`, `UInt32`, `SInt64`, `UInt64`, `Decimal`, `Double`, `Boolean`, `DateTime`, `Binary`, `Byte`, `Enum`, `TypeName`, `Any`, `Integer`, `SnapshotData`, `ProcessesData`

**Observed dataTypes in vSphere**: `String` (majority), `Integer`, `Boolean`

### 2.3 `<Metadata>` on Parameters

| Key | Scope | Purpose |
|---|---|---|
| `translationExpression` | Parameter | SpEL to translate user-supplied value into adapter-expected form. E.g., `identifier('VMEntityObjectID')` resolves a platform UUID to a vCenter MoRef |
| `groupedValueExpression` | Parameter | "true" = parameter is a list of resource values (enables batch) |

### 2.4 `<Metadata>` on Methods

| Key | Scope | Purpose |
|---|---|---|
| `disableBatching` | Method | "true" = each resource gets its own invocation (no batching). MoveVM has `true`; Rebalance has `false` |
| `blockingActionTimeoutSecs` | Method | Timeout for blocking (synchronous) script execution. Observed: "360" on Python-script methods |

### 2.5 `executable` attribute -- Python script actions

Two Methods in vSphere use `executable`:
- `RetrieveSnapshotsByDatastore`: `executable="builtin:retrieveSnapshotsByDatastore.py"`
- `RetrieveSnapshotsByVM`: `executable="builtin:retrieveSnapshotsByVM.py"`

The `builtin:` prefix means the script ships with the adapter (in its `scripts/` directory). The platform executes it and returns structured data that the subsequent ActionContext reads via `getValueAsString(key)` and `getValueAsNumber(key, precision, divisor)`.

---

## 3. SpEL expression language catalog

### 3.1 Expressions in `adapterEndpointExpression`

Always evaluated against the **adapter instance** resource:
- `attribute('summary|vcuuid')` -- most common; resolves the vCenter UUID
- `identifier('VMEntityVCID')` -- alternative; uses identifier instead of attribute

### 3.2 Expressions in `resourceEndpointExpression`

Evaluated against the **target resource**. Returns a value to match against `adapterEndpointExpression`, or `value('invalid')` to disable.

Common pattern (ternary chains):
```
contextResourcesCache[0].resourceKindKey == 'VirtualMachine'
    ? (isVMNotEligibleForAction() or isVMTemplate() ? value('invalid') : ...)
    : (contextResourcesCache[0].resourceKindKey == 'HostSystem'
        or contextResourcesCache[0].resourceKindKey == 'ClusterComputeResource'
            ? identifier('VMEntityVCID') : value('invalid'))
```

### 3.3 Expressions in `ResourceContext.resourceTarget`

Returns the target set for the action:
- `resourceUuid` -- single resource, direct target
- `{}` -- empty set; action not applicable
- `getDescendantsAndCheckAttributes('VMWARE', 'VirtualMachine', depth, checkRunning, includeTemplates).![resourceUuid]` -- bulk target from descendants
- `getDescendantsAndCheckIfVMIsNotEligibleForAction('VMWARE', 'VirtualMachine', depth).![resourceUuid]`
- `getDescendantsAndCheckIfReclaimableByReason('VMWARE', 'VirtualMachine', depth, 'IDLE').![resourceUuid]`
- `getDescendingDatastoresWithEligibleVMsForAction('VMWARE', 'Datastore', depth).![resourceUuid]`
- `getSnapshotsAction(contextResources, 'Datastore', limit).![getStringVal('resource_uuid')]`
- `isDatastoreWithEligibleVMsForAction() ? resourceUuid : {}`

### 3.4 Expressions in `ActionContextField.value`

**Resource data accessors:**
- `identifier('KEY')` -- read ResourceIdentifier value
- `attribute('metric|path')` -- read attribute value
- `attributeInt('metric|path')` -- read as integer
- `attributeInt('metric|path', divisor)` -- read as integer with division (e.g., KB to MB)
- `resourceNameAndIcon` -- formatted name + icon
- `resourceUuid` -- platform UUID
- `resourceKindKey` -- the resource kind string

**Relationship traversal:**
- `parents('ADAPTER','ResourceKind')` -- parent resources
- `parents('ADAPTER','ResourceKind')[0].resourceNameAndIcon` -- first parent's name
- `children('ADAPTER','ResourceKind')` -- child resources
- `descendants('ADAPTER','ResourceKind', depth)` -- descendant resources

**Policy-aware UI shaping:**
- `isAttributeDisabledFromPolicy('metric|path', 'ADAPTER', 'ResourceKind')` -- returns true if policy disables this metric
- `resourceAttributeFormat('metric|path', 'format')` -- formatted display; formats: `boolean`, `percent`, `integer`
- `resourceAttributeUnit('metric|path', 'unit', 'unit', 'unit')` -- with unit conversion

**Literal and computed values:**
- `value('literal')` -- literal string value
- `value(expression)` -- computed value
- `localizedString(nameKey, 'ADAPTER', 'fallback')` -- i18n lookup with fallback

**Multi-step data accessors (from Python script results):**
- `getValueAsString('key')` -- read string from previous step result
- `getValueAsNumber('key', precision, divisor)` -- read number with formatting

**Rebalance/placement-specific:**
- `contextPlacement.indexedRow.host.resourceNameAndIcon` -- placement engine result
- `contextPlacement.indexedRow.cells[N].formatValue()` -- cell from placement grid
- `contextPlacement.getCompatibilityColumn(col, adapter, kind)` -- compatibility check
- `contextRebalanceAction.items[N].itemUuid` -- rebalance action result items
- `contextRebalanceImpact.getWorkloadColumn('metric_name')` -- impact projection
- `contextImmovableVms.incompatibilities` -- immovable VM diagnostics
- `contextSnapshot.getStringVal('key')` -- snapshot data

**Adapter-specific helpers:**
- `getParentVmwareAdapterInstance(vcuuid)` -- resolve the parent adapter instance
- `isVMNotEligibleForAction()` -- composite eligibility check
- `isVMTemplate()` -- template check
- `isResourceReclaimableByReason('IDLE')` -- reclamation check
- `isRebalanceConflictingWithAutomation(id)` -- automation conflict check
- `isAutomationAllowedByLicense()` -- license check
- `isVRAOrCASManaged(resources)` -- vRA/CAS management check
- `hasChildPrivileges(kinds...)` -- privilege check
- `isResourceEntitledToRebalance(id)` -- entitlement check
- `isActionsEnabled('ADAPTER', uuids)` -- actions enablement check
- `getRecommendedCpu()` -- rightsizing recommendation
- `getRecommendedMemoryMB()` -- rightsizing recommendation
- `getContextResourceId()` -- current resource ID
- `createComboBox(labels, values, default)` -- dropdown construction

**Collection operations (SpEL projection/selection):**
- `.![expression]` -- projection (map over collection)
- `.?[predicate]` -- selection (filter)
- `.size()` -- count
- `.contains(value)` -- membership test
- `asSet(collection)` -- convert to set
- `sort(collection)` -- sort
- `combine(list1, list2, ...)` -- merge lists
- `intersectAncestors(resources, flag, kinds...)` -- intersection
- `allResourcesCommonCache(resources, flag, adapter, kind, identKey)` -- cached lookup
- `allResourcesCache(adapter, kind)` -- all resources of kind
- `allResources(adapter, kind)` -- uncached version
- `adapterResourceKindKey(adapter, kind)` -- construct kind key

---

## 4. vSphere action catalog (25 unique actions)

### 4.1 Power operations (5 actions, all target VirtualMachine + HostSystem + ClusterComputeResource)

| Action key | scheduleEnabled | Method |
|---|---|---|
| Power On VM | true | PowerOnVM |
| Power Off VM | true | PowerOffVM |
| Suspend VM | true | SuspendVM |
| Shut Down Guest OS For VM | false | ShutdownVMGuest |
| Reboot Guest OS For VM | true | RebootVMGuest |

Pattern: All have 3 ResourceContexts (VM direct, Host descendants, Cluster descendants). All use `getDescendantsAndCheckAttributes()` for Host/Cluster scoping.

### 4.2 VM lifecycle (3 actions)

| Action key | Target kind(s) | Method |
|---|---|---|
| Delete Powered Off VM | VM + Host + Cluster | DeletePoweredOffVM |
| Delete Idle VM | VM + Host + Cluster | DeleteVM |
| Execute Script | VM only | execScript |

Execute Script is unique: `isMultiSelectAllowed="false"`, single ResourceContext with `workbenchEnabled="true"`, uses `textarea` for script input.

### 4.3 VM configuration -- memory/CPU sizing (8 actions, 4 are hidden "Power Off Allowed" variants)

| Action key | hidden | Method |
|---|---|---|
| Set Memory For VM | false | ModifyMemoryForVM |
| Set Memory For VM Power Off Allowed | true | ModifyMemoryForVM |
| Set CPU Count For VM | false | SetCPUCount |
| Set CPU Count For VM Power Off Allowed | true | SetCPUCount |
| Set CPU Count and Memory For VM | false | SetCPUCountAndMemoryforVM |
| Set CPU Count and Memory For VM Power Off Allowed | true | SetCPUCountAndMemoryforVM |
| Set CPU Resources For VM | false | SetCPUResources |
| Set Memory Resources For VM | false | SetMemoryResources |

Pattern: The "Power Off Allowed" variants are `hidden="true"` and pre-set `powerOffAllowed` to `value('true')` instead of `value('false')`. These are invoked programmatically by recommendations, not shown in the UI menu.

### 4.4 Migration/rebalance (3 actions)

| Action key | actionType | Method |
|---|---|---|
| Move VM for Workload | update | MoveVM |
| Rebalance Workload | update | Rebalance |
| Schedule Rebalance Workload | schedule | Rebalance |

Move VM is the most complex action: multi-step (2 ActionContexts with order), `isGroupedResource="true"` on ResourceContext, `percentbar` and `booleanimage` components in the impact grid.

### 4.5 Snapshot management (6 actions, 2 are hidden "Express" variants)

| Action key | hidden | Multi-step | Method(s) |
|---|---|---|---|
| Delete Unused Snapshots For Datastore | false | 2-step | RetrieveSnapshotsByDatastore then DeleteSnapshots |
| Delete Unused Snapshots For VM | false | 2-step | RetrieveSnapshotsByVM then DeleteSnapshots |
| Delete Unused Snapshots For Datastore Express | true | 1-step | DeleteSnapshots (uses contextSnapshot) |
| Delete Unused Snapshots For VM Express | true | 1-step | DeleteSnapshots (uses contextSnapshot) |
| Delete Unused Snapshots For VM On Conditions | -- | 2-step | (COMMENTED OUT -- includes combobox with operator selection) |

The multi-step pattern: step 0 calls a Python script (`executable="builtin:*.py"`) that returns structured data; step 1 reads that data via `getValueAsString()` / `getValueAsNumber()`.

### 4.6 Cluster configuration (1 action)

| Action key | Method | Components used |
|---|---|---|
| Set DRS Automation | ModifyDRSConfig | combobox (DRS level), combobox (migration threshold) |

---

## 5. REST API for actions

### 5.1 Public API endpoints (operations-api.json)

| Endpoint | Method | Purpose |
|---|---|---|
| `GET /api/actiondefinitions` | GET | List all action definitions with pagination. Params: `scheduleEnabled`, `page`, `pageSize` |
| `POST /api/actions/{id}/query` | POST | Populate action: evaluate expressions, get default values. Input: `action-population` (list of resource UUIDs). Returns: `populated-action` with expression results |
| `POST /api/actions/{id}` | POST | Execute an action. Input: `action-execution` with contextId, resource UUIDs, parameter values. Returns: list of task IDs |
| `GET /api/actions/{taskId}/status` | GET | Poll action status. Params: `detail` (bool). Returns: state, messages, per-resource statuses |

**Action ID format**: `{adapterKindKey}-{actionKey}` (e.g., `VMWARE-Power Off VM`)

**Action definition API response shape** (confirmed live):
```json
{
    "id": "VMWARE-Power Off VM",
    "displayName": "Power Off VM",
    "type": "UPDATE",
    "actionAdapterKindKey": "VMWARE",
    "contextAdapterKindKey": "VMWARE",
    "contextResourceKindKey": "VirtualMachine",
    "contextIds": ["PowerOffVM"],
    "scheduleEnabled": true,
    "canRecommend": true
}
```

Note: The API returns one action-definition entry per (action + ResourceContext). "Power Off VM" with 3 ResourceContexts produces 3 entries with different `contextResourceKindKey` values.

**Live instance**: 142 total action definitions across VMWARE (the majority), APPOSUCP (77 plugin activation actions), ManagementPackBuilderAdapter (2), SupervisorAdapter (1), APPLICATIONDISCOVERY (1).

### 5.2 Internal API endpoints (internal-api.json) -- UNSUPPORTED

| Endpoint | Method | Purpose |
|---|---|---|
| `GET /internal/actions/automation/schedules` | GET | List all automation action schedules |
| `POST /internal/actions/automation/schedules` | POST | Create automation schedule |
| `PUT /internal/actions/automation/schedules` | PUT | Update automation schedule |
| `GET /internal/actions/automation/schedules/{id}` | GET | Get schedule by ID |
| `DELETE /internal/actions/automation/schedules/{id}` | DELETE | Delete schedule |
| `POST /internal/actions/automation/schedules/query` | POST | Query schedules |
| `GET /internal/actions/schedules` | GET | List action schedules |
| `POST /internal/actions/schedules` | POST | Create schedule |
| `PUT /internal/actions/schedules` | PUT | Update schedule |
| `GET /internal/actions/schedules/{id}` | GET | Get schedule |
| `DELETE /internal/actions/schedules/{id}` | DELETE | Delete schedule |
| `PUT /internal/actions/schedules/{id}/enable` | PUT | Enable schedule |
| `PUT /internal/actions/schedules/{id}/disable` | PUT | Disable schedule |
| `POST /internal/actions/schedules/query` | POST | Query schedules |

WARNING: All `/internal/` endpoints require the `X-Ops-API-use-unsupported` header and may break across versions.

**Automation schedule shape** (from examples):
```json
{
    "id": "uuid",
    "name": "schedule name",
    "enabled": true,
    "actionDetails": {
        "type": "ADDITIONAL_ACTION_DETAILS",
        "actionKey": { "key": "Power Off VM", "adapterKindKey": "VMWARE" }
    },
    "actionScope": {
        "type": "ADDITIONAL_ACTION_SCHEDULE_SCOPE",
        "resourceIds": ["uuid"],
        "contextResourceKindKey": { "resourceKind": "HostSystem", "adapterKind": "VMWARE" },
        "filters": [{ "scopeFilters": [{ "type": "METRIC_FILTER", "key": "metric|path", "numericOperator": "LESS_THAN", "numericValue": 25.5 }] }]
    },
    "scheduleConfig": { "timeZone": "...", "startDate": "...", "scheduleType": { "type": "DAILY|WEEKLY|..." } }
}
```

### 5.3 Action execution flow via API

1. **Discover**: `GET /api/actiondefinitions` -- find the action ID
2. **Populate**: `POST /api/actions/{id}/query` with resource UUIDs -- get expression results and default parameter values
3. **Execute**: `POST /api/actions/{id}` with `action-execution` body -- returns task ID(s)
4. **Poll**: `GET /api/actions/{taskId}/status` -- check completion

The populate step evaluates all SpEL expressions from the ActionContextFields and returns them in `expressionResults[]`. The execute step accepts an `action-execution` with `contextId`, `contextResourceId[]`, and `parameterGroup[]` (one per target resource, each with `resourceId` and `parameterValue[]` name-value pairs).

---

## 6. Recommendation-Action linkage

### 6.1 `<Action>` inside `<Recommendation>`

Recommendations in describe.xml can include an `<Action>` child that links to a declared action:

```xml
<Recommendation key="Increase-Remove-CpuLimits-Vm">
    <Description nameKey="9046"/>
    <Action actionAdapterKey="VMWARE"
            actionKey="Set CPU Resources For VM"
            targetAdapterKey="VMWARE"
            targetResourceKind="ClusterComputeResource"/>
</Recommendation>
```

**Attributes of `<Action>` inside `<Recommendation>`:**

| Attribute | Required | Notes |
|---|---|---|
| `actionAdapterKey` | YES | Which adapter owns the action |
| `actionKey` | YES | The Action.key to invoke |
| `targetAdapterKey` | NO | Adapter kind of target resource (can differ from action adapter) |
| `targetResourceKind` | YES | Resource kind of the target |

**Cross-MP**: `actionAdapterKey` can reference a different adapter kind than the alert's adapter kind, enabling cross-MP remediation (e.g., an alert from adapter A recommending an action from adapter B).

vSphere has **17 recommendations with Action linkage** out of ~30 total recommendations. The linked actions include: Set CPU Resources, Set CPU Count, Set Memory, Delete Unused Snapshots, Set DRS Automation, and the hidden "Power Off Allowed" variants.

### 6.2 How hidden actions serve recommendations

The hidden `*Power Off Allowed` actions exist specifically for recommendation-driven automation. When the platform auto-triggers an action from a recommendation, it uses the hidden variant where `powerOffAllowed` defaults to `true` -- the automation can power off the VM to apply the change, while the user-facing UI variant defaults to `false` (requiring explicit opt-in).

---

## 7. XSD vs. runtime divergence summary

The following features are used in the production vSphere adapter but are NOT in the XSD:

| Feature | Where | Impact |
|---|---|---|
| `actionType="schedule"` | `<Action>` | Runtime accepts it; XSD validation would reject |
| `scheduleEnabled` attribute | `<Action>` | Enables scheduling UI |
| `isMultiSelectAllowed` attribute | `<Action>` | Restricts to single selection |
| `reuseCollectingAdapterInstanceForActionRun` | `<Actions>` | Adapter instance routing |
| `isGroupedResource` attribute | `<ResourceContext>` | Grouped resource handling |
| `workbenchEnabled` attribute | `<ResourceContext>` | Workbench UI surface |
| `order` attribute | `<ActionContext>` | Multi-step ordering |
| `percentbar` component | `<ActionContextField>` | Percentage bar visualization |

These are all VMware-internal extensions. Third-party adapters should use them cautiously -- they work but are not schema-validated and could change.

---

## 8. Open questions

1. **`<Result>` / MethodResultType**: XSD permits result declarations on Methods but none are observed in vSphere. How do script-based methods (the Python executables) declare their return schema? The platform seems to handle this implicitly via `getValueAsString()` accessors.

2. **ComplexMethodInfo types**: Seven type-wrapper variants exist in the XSD but only `SimpleMethodInfoList` is observed in vSphere. Do any production adapters use `ComplexMethodInfo*`?

3. **`<Exception>` element**: Methods can declare exceptions per XSD; none observed. Does the runtime use these for anything?

4. **Full `canRecommend` semantics**: The XSD types it as `xs:string` not `xs:boolean`. Are there values beyond "true"/"false"?

5. **Action result rendering**: The `action-status-info` API type shows messages with levels (ERROR/WARN/INFO) and per-resource `actionObjectStatuses` with states (COMPLETED_SUCCESSFULLY, etc.). But how does the platform render structured results from Python-script methods in the UI?

6. **NMP task vs. legacy action discovery**: The platform knows about NMP tasks by Java type dispatch, not describe.xml. Is there an API endpoint that lists NMP tasks? The `/api/actiondefinitions` only returns legacy actions.

7. **`percentbar` stability**: Used in production but not in XSD. Is it safe for third-party adapters, or could it be removed in a future schema version?

---

## 9. Implications for VCF Content Factory

### 9.1 Authoring model

For the 80% case, VCF-CF should generate:
1. A `<Method>` with `SimpleMethodInfoList` parameters (`String`, `Integer`, `Boolean`)
2. An `<Action>` with `actionType="update"`, basic endpoint expressions, and one or more ResourceContexts
3. An `<ActionContext>` with `textfield`, `numberfield`, `positiveintegerfield`, `checkcolumn`, and `combobox` components

The 20% long tail (multi-step actions, Python scripts, rebalance/placement expressions) requires hand-authored SpEL.

### 9.2 Pattern templates

**Simple power action** (3 ResourceContexts, 1 method parameter):
```yaml
action:
  key: "Power Off Widget"
  actionType: update
  adapterEndpoint: "identifier('WIDGET_ID')"
  resourceEndpoint: "identifier('WIDGET_ID')"
  resourceContexts:
    - kind: Widget
      target: direct
    - kind: WidgetHost
      target: descendants(Widget, 1)
  method: PowerOffWidget
  parameters:
    - key: mOR
      type: String
      required: true
  fields:
    - key: Name
      component: textfield
      display: resourceNameAndIcon
    - key: mOR
      hidden: true
      parameter: mOR
      value: "identifier('WidgetObjectID')"
```

**Configuration action** (user-editable fields):
```yaml
action:
  key: "Set Widget Memory"
  fields:
    - key: "New Memory"
      component: positiveintegerfield
      input: true
      parameter: memory
      value: getRecommendedMemory()
    - key: "Current Memory"
      component: numberfield
      value: "attributeInt('config|memory')"
    - key: "Allow Power Off"
      component: checkcolumn
      input: true
      parameter: powerOffAllowed
      value: "value('false')"
```

### 9.3 Recommendation integration

For actions that should be triggerable from alert recommendations, declare a hidden variant with automation-friendly defaults (e.g., `powerOffAllowed=true`) and reference it from the recommendation's `<Action>` element.

---

## 10. Confidence ratings

| Finding | Confidence |
|---|---|
| XSD ActionContextField component enum (9 values) | HIGH -- read from XSD source |
| `percentbar` as runtime extension | HIGH -- observed in production vSphere adapter, not in XSD |
| Action execution API flow | HIGH -- confirmed with live instance + OpenAPI spec |
| Multi-step action pattern (order attribute) | HIGH -- observed in 4 vSphere snapshot actions |
| SpEL expression function catalog | MEDIUM -- inferred from describe.xml examples, not formal grammar |
| XSD-to-runtime attribute divergence | HIGH -- grep confirmed attributes absent from XSD present in production |
| Recommendation-Action linkage | HIGH -- 17 examples observed in vSphere describe.xml |
| NMP task vs legacy action separation | HIGH -- confirmed in spec/04 with code evidence |
