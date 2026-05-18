# 04 — Actions and Tasks: Two Co-existing Protocols

**Status**: DRAFT (pass 2 evidence — both protocols observed; full sub-system inventory deferred)

There are **two distinct protocols** for user-invokable operations on
monitored systems:

| Protocol | Origin | Package | Declared in describe.xml? | Observed in |
|---|---|---|---|---|
| **Legacy actions** | Integrien Alive lineage | `com.integrien.alive.common.adapter3.action.*` (22 SDK classes) | YES — `<Actions>` and `<Methods>` | mpb-adapter |
| **Modern tasks (NMP)** | VMware vrops "NMP" subsystem | `com.vmware.vrops.nmp.task.*` (in `vcops-common-*.jar`) | NO — dispatched on Java type of TaskParam | vim |

Both can co-exist within a single adapter (an adapter could implement
both `ActionableAdapterInterface` and `TaskHandler`/`AsyncTaskHandler`),
though neither observed adapter does so.

**Recommendation for VCF-CF Tier 2 generator**: Prefer the **modern
NMP task system** for new adapters. Legacy actions remain supported
for backwards compatibility but the platform's newer surface
(desired-state config, diagnostics, troubleshoot, VCF-/AppOS-specific
operations) is exposed via NMP.

---

## Protocol A: Legacy actions (`ActionableAdapterInterface`)

**SDK source**: `com.integrien.alive.common.adapter3.action.*` (22 classes)
**Describe-side**: `ActionDescribe`, `ActionContextDescribe`, `ActionContextFieldDescribe`, `ActionKindDescribe`, `MethodDescribe`, related parameter info classes
**Calibration adapter**: mpb-adapter

### Concept

Adapters opt into legacy actions by:

1. Implementing the **mix-in interface `ActionableAdapterInterface`**
   (in `com.integrien.alive.common.adapter3.action`) alongside extending
   `AdapterBase`.
2. Declaring the action surface in `describe.xml` under `<Actions>`
   and `<Methods>`.

## `ActionableAdapterInterface` (interface signature)

```
package com.integrien.alive.common.adapter3.action;

public interface ActionableAdapterInterface {
    ActionResult onAction(ActionParam param);
    ActionResult checkActionStatus(ActionResult result, ActionParam param);
}
```

- `onAction` — synchronous entry-point invoked when the user (or REST
  client) triggers an action. Returns an `ActionResult`.
- `checkActionStatus` — polling endpoint for long-running async actions.
  The platform repeatedly calls this with the previous `ActionResult`
  and the original `ActionParam` until the action terminates.

The async-poll pattern (kick off in `onAction`, poll via
`checkActionStatus`) is observed in mpb-adapter, where the action
runtime uses an internal `ActionRunner` keyed by action ID.

## describe.xml declaration

```xml
<Actions>
    <Action key="<action-key>"
            actionType="read|update"
            adapterEndpointExpression="<expression>"
            resourceEndpointExpression="<expression>"
            hidden="true|false (optional)">

        <ResourceContext
            adapterKind="<adapter-kind>"
            key="<context-key>"
            nameKey="<int>"
            resourceKind="<resource-kind>"
            resourceTarget="<target-mode>"/>

        <ActionContext
            helpId="<help-anchor>"
            key="<action-context-key>"
            methodKey="<method-key>">

            <ActionContextField
                component="textfield|..."
                dispOrder="<int>"
                key="<field-key>"
                nameKey="<int>"
                input="true|false"
                parameter="<parameter-name>"/>
            <!-- ... more fields ... -->
        </ActionContext>
    </Action>
</Actions>

<Methods>
    <Method key="<method-key>">
        <Parameter isRequired="true|false" key="<param-key>" nameKey="<int>">
            <SimpleMethodInfo dataType="String|Integer|..."/>
        </Parameter>
        <!-- ... more parameters ... -->
    </Method>
</Methods>
```

### `<Action>` attributes (observed)

- `key` — stable action identifier
- `actionType` — `"read"` (no side effects) or `"update"` (changes
  the target system). The semantics matter for the UI's confirmation
  flow and audit logging.
- `adapterEndpointExpression` — expression resolving to which adapter
  instance to invoke. Observed value:
  `identifier('COLLECTOR_UUID')` — the standard form is to resolve via
  the adapter's identifier(s).
- `resourceEndpointExpression` — expression for the target resource.
- `hidden` — (optional) `"true"` means the action is REST-only, hidden
  from the UI. Ignored when `actionType="read"`. *Not observed in
  mpb-adapter (both actions are visible).*

### `<ResourceContext>`

Scopes the action to a particular resource kind on a particular adapter
kind. `resourceTarget` controls how the platform identifies the
target — observed value: `resourceUuid`.

### `<ActionContext>` + `<ActionContextField>`

The UI form rendering. Each field maps a UI input (`component`,
typically `textfield`) to a parameter (`parameter="..."`) which is
in turn defined in the corresponding `<Method>`.

### `<Method>` and `<Parameter>`

The action's parameter signature. Each parameter has a `dataType`
(observed: `String`, `Integer`) and a `isRequired` flag. The action
implementation receives the parameter values keyed by the parameter
`key`.

## Observed pattern: mpb-adapter actions

mpb-adapter declares two actions, both `actionType="update"`:

### `CollectionPreview`
- Method: `CollectionPreviewMethod`
- Parameters: `builderJson`, `configuration`, `credentials`,
  `logLevel`, `trustedCertificates`
- Purpose: preview what an MPB design would collect without committing
- Result models (in mpb-adapter's
  `actions.result.collectionpreview.*`): `CollectedAdapter`,
  `CollectedData`, `CollectedEvent`, `CollectedIdentifier`,
  `CollectedRelationship`, `CollectedResource`, `CollectedResourceKind`

### `RunRequest`
- Method: `RunRequestMethod`
- Parameters: 9 named params including runtime tunables
  (`execTimeoutSeconds`, `requestTimeout`, `maxRetries`,
  `maxConcurrentRequests`)
- Purpose: execute an arbitrary HTTP request against a target system
  (design-authoring / debugging affordance)
- Result models (in `actions.result.request.*`): `DataModelAttribute`,
  `DataModelList` (with inner `DataModel`), `HttpResponseHeader`,
  `HttpResponseResult`

## Async action runtime pattern

mpb-adapter ships an internal `ActionRunner` with:

```
IntegrationDesignerAction getAction(String);
void startAction(IntegrationDesignerAction);
void removeAction(String);
void onDiscard();
```

This implements the async-poll pattern: `onAction` registers an
action object keyed by its ID and returns immediately;
`checkActionStatus` consults the runner. The pattern is reusable for
any long-running action.

**Not a SDK type**: `ActionRunner` is internal to mpb-adapter. The SDK
likely has an action infrastructure in `adapter3.action.*` (22
classes — not yet inventoried). Pass 2 should javap that subsystem.

---

## Protocol B: Modern NMP tasks

**Source**: `com.vmware.vrops.nmp.task.*` (in `vcops-common-*.jar` — observed via vim's bundled `vcops-common-1.0.jar`)
**Calibration adapter**: vim
**NOT declared in describe.xml** — dispatched on Java type at runtime.

### Concept

Adapters opt into NMP tasks by implementing one or both interfaces:

```
package com.vmware.vrops.nmp.task;

public interface TaskHandler {
    TaskResult onTask(TaskParam param);
}

public interface AsyncTaskHandler {
    void onAsyncTask(UUID taskId, TaskParam param, AsyncTaskHandler.AsyncNMPCallback callback);
}
```

Where:

```
public interface TaskParam extends java.io.Serializable { }
public interface TaskResult extends java.io.Serializable { }
```

`TaskParam` and `TaskResult` are **marker interfaces** with no
methods. Each task type subclasses them with structured payload.

### Routing pattern (inferred)

The platform calls `onTask(taskParam)` or `onAsyncTask(...)`. The
adapter dispatches on the runtime class of `taskParam`. Subdomain
packages observed under `com.vmware.vrops.nmp.task.*`:

- `config.desiredstate.*` — desired-state configuration tasks
  (`ConfigDesiredStateTaskParam`, `ConfigDesiredStateTaskType`,
  `ConfigDriftResults` with `DriftStatus` enum, `DriftResults` builder)
- `diagnostics.evaluation.*` — diagnostic evaluation tasks
- `diagnostics.troubleshoot.*` — troubleshooting tasks
- `vcf.*` — VCF-specific operations
- `appos.*` — Application Operating System tasks

Each subdomain ships its own concrete `TaskParam` / `TaskResult`
subtype hierarchy. **The type system IS the action declaration.** No
XML declaration is required because the platform doesn't need to
discover the task surface from the adapter — it sends tasks of known
types and the adapter declares which types it handles by which
classes it imports.

### Sync vs. async

- `TaskHandler.onTask(TaskParam) → TaskResult` — synchronous. The
  adapter returns the result before the call returns. Suitable for
  short, deterministic operations.
- `AsyncTaskHandler.onAsyncTask(UUID, TaskParam, AsyncNMPCallback)` —
  async. The adapter receives a task ID and a callback; it kicks off
  work and invokes the callback when complete. Suitable for
  long-running operations (e.g., diagnostic collection, drift
  evaluation).

The async pattern differs from legacy actions' poll-based
`checkActionStatus`: NMP uses a push-style callback, legacy actions
use pull-style polling.

### Recommendations

- Implement `TaskHandler` for short tasks; implement
  `AsyncTaskHandler` for any task that may exceed the platform's
  RPC timeout.
- Use `instanceof` to dispatch in your handler implementation, keyed
  on the most-specific TaskParam subclass.
- Subdomain packages (`config.desiredstate`, `diagnostics.*`,
  `vcf.*`, `appos.*`) telegraph platform-defined extension points;
  adapters should only handle task types they declare support for in
  their integration documentation.

---

## Open / pass 3+

### Legacy actions
- Full `ActionParam` / `ActionResult` signature
- The 22 classes in `com.integrien.alive.common.adapter3.action.*` —
  full inventory and contract
- Action expression language (the `identifier('COLLECTOR_UUID')` form)
- Whether actions can declare result schemas (so the UI knows how to
  render them)
- Per-resource action variants (the `resourceEndpointExpression`
  semantics for actions that operate on something other than the
  adapter instance)
- `<ComplexMethodInfo*>` parameter-type variants (vs. the
  `SimpleMethodInfo` observed)

### NMP tasks
- Full inventory of platform-defined `TaskParam` / `TaskResult` types
  per subdomain (`config.desiredstate`, `diagnostics.*`, `vcf.*`,
  `appos.*`)
- Is the type system extensible by third-party adapters (custom
  TaskParam types), or platform-defined only?
- `AsyncNMPCallback` interface signature
- How the platform discovers which task types an adapter supports —
  does it call `onTask` blindly and let the adapter throw, or is
  there a separate capability declaration?
- Does NMP have a UI surface, or is it REST/internal only?
