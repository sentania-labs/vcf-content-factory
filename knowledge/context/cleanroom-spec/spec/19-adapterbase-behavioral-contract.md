# 19 — AdapterBase Behavioral Contract (VCF-CF native orchestrator)

**Status**: DRAFT (pass 30)
**SDK source**: `vrops-adapters-sdk-2.2.jar` (AdapterBase build 2025-12-30;
public-surface-identical entry contract back to the 2019 build — see
[§ SDK API stability](../analysis/sdk-survey/third-party-broadcom-jar-redistribution-survey-2026-06-09.md))
**Purpose**: the step-level platform contract VCF-CF needs to re-home its
framework base class **directly onto `AdapterBase`** and run its own
test/discover/collect orchestration — replacing the role-SPI wrapper
layer (`UnlicensedAdapter`/`aria-ops-core`) entirely.

> **Clean-room note.** Everything below is derived from (a) the SDK
> jar's **declared public API surface** (`javap -public` — signatures,
> overloads, enum constants), (b) prior field-confirmed behavior
> (Pass 23 DEBUG collector logs), and (c) the structural contract the
> describe schema imposes. It describes **what calls to make, in what
> order, with what arguments** — *not* the body of `AdapterBase.collect()`
> or any wrapper. No bytecode was decompiled. Inferred semantics (where
> the signature constrains but does not fully determine behavior) are
> labelled **[INFER]**; everything else is **[API]** (confirmed from the
> surface) or **[FIELD]** (confirmed from live logs).

Cross-refs: [§01 lifecycle](01-adapter-lifecycle.md) (entry contract,
helper API, Pass 23 confirmations), [§05 resource model](05-resource-model.md),
[§07 relationships](07-relationships-cross-mp.md),
[§13 classloading](13-classloading-and-classpath.md).

---

## 0. Orientation — what the orchestrator owns

`AdapterBase` (abstract, `com.integrien.alive.common.adapter3`)
finalizes the 9 `AdapterInterface3` methods and dispatches to `on*()`
hooks (template-method; see §01). A VCF-CF orchestrator implements the
**four required hooks** — `onConfigure`, `onDescribe`, `onDiscover`,
`onCollect` — plus `onTest`, the stop/discard hooks, and drives its own
internal decomposition behind them. The platform → base → hook calls,
and the hook pushes data back through **base helper methods** that
accumulate into the `CollectResult`/`DiscoveryResult`/`AdapterStatus`
the base will return. The orchestrator never news-up or returns those
result objects for `collect()`; it calls helpers. (`onDiscover` is the
exception — it returns a `DiscoveryResult` it assembles.)

The role-SPI wrapper decomposed this into Tester/Discoverer/LiveCollector/
HistoricalCollector (§01). VCF-CF may keep that shape or not — it is a
*wrapper convention*, not a platform requirement. The platform contract
is only what this section documents.

---

## 1. `onCollect()` orchestration sequence

**Entry** `[API]`:
```
// AdapterBase (final): public final CollectResult collect();
// dispatches to:
public abstract void onCollect(ResourceConfig adapterInstance,
                               Collection<ResourceConfig> resources);
```
`resources` is the live set of monitored `ResourceConfig` for this
instance (same objects returned by `getAllMonitoringResources()`).
The base creates the cycle's `CollectResult(adapterKind, adapterInstResourceId)`
and `setCollectTime(now)`; the hook fills it via helpers; the base
returns it. **The platform does not retry a failed cycle** `[FIELD]` —
errors are swallow-and-log; the next scheduled cycle proceeds. Each
instance's `collect()` is serialized by a per-instance `Semaphore(1)`
and runs single-threaded `[FIELD]`.

### Correct order of operations for one cycle

```
onCollect(adapterInstance, resources):
    1. (optional) top-of-cycle rediscovery
       if inventory/relationships may have changed since last cycle:
           build a DiscoveryResult (see §6) and fold it in:
              addNewResource(rc|resourceKey)        // per new resource  (→ §2)
              addResourceKind(key, kindDescribe, …) // per new dynamic kind (→ §6)
           relationship deltas → addRelationships(Relationships)        (→ §3)
       // The CollectResult carries an *embedded DiscoveryResult*; new
       // resources/kinds/relationships ride along with the collect.

    2. for each rc in resources:
         try:
            metrics    = gather numeric/string samples
            addMetricData(rc, metricsList)                  // [API]
            properties = gather property values
            addMetricData(rc, propsList, /*isProperty=*/true)
            events     = gather events  → addEvent(rc, externalEvent)   (→ §4)
            rels       = gather edges   → addRelationships(rels)         (→ §3)

            // per-resource status — REQUIRED for platform health UI:
            setResourceStatus(rc, RESOURCE_STATUS_DATA_RECEIVING)        // [API]
         catch (target unreachable):
            setResourceDown(rc, now, reason)   // or RESOURCE_STATUS_DOWN
         catch (reachable but no data):
            setResourceStatus(rc, RESOURCE_STATUS_NO_DATA_RECEIVING)

    3. return  // base returns the assembled CollectResult
```

### Per-resource collection status `[API]`

`CommonConstants$ResourceStatusEnum` (set via base
`setResourceStatus(rc, …)` / `setResourceDown(rc, …)`, or
`ResourceStatus.setStatus(…)`):

| Constant | Meaning | When to set |
|---|---|---|
| `RESOURCE_STATUS_DATA_RECEIVING` | healthy, data arrived this cycle | resource collected OK |
| `RESOURCE_STATUS_OLD_DATA_RECEIVING` | stale data only | got data but older than cycle |
| `RESOURCE_STATUS_NO_DATA_RECEIVING` | reachable, no data | resource yielded nothing |
| `RESOURCE_STATUS_DOWN` | resource down | target reports/looks down |
| `RESOURCE_STATUS_ERROR` | collection error | exception collecting this resource |
| `RESOURCE_STATUS_NO_PARENT_MONITORING` | parent not monitored | dependency gap |
| `RESOURCE_STATUS_COLLECTOR_DOWN` | collector-side failure | infra fault |
| `RESOURCE_STATUS_UNKNOWN` / `_NONE` | indeterminate / unset | — |

`ResourceStatusEnum.isAdapterAllowedStatus(status)` `[API]` gates which
statuses an adapter is permitted to set — **call it (or pre-validate)
before setting**, since not all enum values are adapter-settable.

### What a complete-and-valid `CollectResult` must contain

- Constructed with **`adapterKind` + `adapterInstResourceId`** (base does
  this) and **`collectTime`** set. `[API]`
- A **`ResourceStatus` per monitored resource** (`setResourceStatus` /
  `addResourceCollectResult`) so the platform's health/availability model
  has a verdict for each — a resource with neither data nor status reads
  as silent/NO_DATA. `[API/INFER]`
- Metric/property/event/relationship payloads are **optional per cycle**;
  a cycle that returns a `CollectResult` with only statuses is accepted.
  Partial data + logged errors are accepted (no-retry contract). `[FIELD]`

---

## 2. New-resource registration during collect

A resource discovered mid-collect is folded into the `CollectResult`'s
**embedded `DiscoveryResult`** `[API]`:

```
// On CollectResult (base exposes equivalents during onCollect):
public void addNewResource(ResourceKey);
public void addNewResource(ResourceConfig);
// or assemble a DiscoveryResult and: collectResult.setDiscoveryResult(dr)
//   then dr.addResource(ResourceConfig) per resource
```

### Identity & matching `[API]`

A resource's identity is a **`ResourceKey`**:
```
new ResourceKey(adapterKind, resourceKind, resourceName,
                Collection<ResourceIdentifierConfig> identifiers)
```
- `ResourceIdentifierConfig` carries `IDENT_TYPE_IDENTIFYING` vs
  `IDENT_TYPE_INFORMATIONAL` (`CommonConstants`) `[API]`. **Only the
  *identifying* identifiers participate in uniqueness** —
  `ResourceKey.getUniquenessIdentifierCount()` / `isValid()` reflect this.
- On the next cycle the platform matches by the identifying-identifier
  tuple → same internal `resourceId`. **Identifying identifiers must be
  complete and stable**; informational ones may change without breaking
  identity. `[API/INFER]`
- A newly-registered resource has **no state value to set** — it is
  *added* (via `addNewResource`/`addResource`), not transitioned. The
  platform creates it active and assigns the `resourceId`. State
  *transitions* of **existing** resources go through `changeResourceState`
  (§6), not registration. `[API]`
- `disableResourceCreation` on `ResourceConfig` (`isDisableResourceCreation`)
  `[API]` lets a config suppress auto-creation — honor it if set.

This extends the VCF-CF "new-resource gate" one level down: the gate's
"emit" step = `addNewResource(resourceKey)` with a `ResourceKey` whose
identifying identifiers are fully populated.

---

## 3. Relationship emission mechanics

Build a `Relationships` object, then attach it:
`collectResult.addRelationships(rels)` (collect) or
`discoveryResult.addRelationships(rels)` (discover). `[API]`

### One consolidated update per parent (cert guidance) `[API]`

```
Relationships r = new Relationships();
r.setTimestamp(now);

// FULL replacement for a parent's child set — platform DIFFS against
// current state. Prefer ONE setRelationships() per parent per cycle:
r.setRelationships(parentKey, childKeyCollection);                 // standard parent/child
r.setGenericRelationships(parentKey, childKeys, label, namespace); // typed/labeled edge

// DELTA (only when you know the incremental change):
r.addRelationships(parentKey, addedChildren);
r.removeRelationships(parentKey, removedChildren);

collectResult.addRelationships(r);
```

| Variant | Use |
|---|---|
| `setRelationships(parent, children)` | full child set, platform diffs — **default for stable sets** |
| `setRelationships(parent, children, Set<label>)` | replace only the named labels, leave others |
| `setGenericRelationships(parent, children, label[, ns])` | typed edges (`depends_on`, etc.); namespace avoids cross-MP label collision |
| `addRelationships`/`removeRelationships` (+ generic) | incremental delta between cycles |
| `addRelationships(Relationships other)` | bulk-merge a second object |

- **Full vs delta**: per §07, emit `set…` per cycle for stable sets (let
  the platform diff); use `add`/`remove` only for known incremental
  changes. `setTimestamp` lets the platform age out stale edges. `[API]`
- **Cross-MP**: pass a `ResourceKey(adapterKind="VMWARE", resourceKind=…,
  identifiers=…)` as parent or child; platform de-dupes by identity (§07).
- **Throttle** `[API/INFER]`: cap relationships per cycle. The wrapper
  exposed `maximumRelationshipsPerCollection`; the underlying knobs are
  `adapter.properties` keys `max_relationships_per_collection` and
  `relationship_sync_interval` (§01 "Still open"). The orchestrator must
  bound edges/cycle and, if a parent's set exceeds the cap, split across
  cycles or lengthen the sync interval — emitting a full `setRelationships`
  only every *N* cycles while pushing metric data every cycle.

---

## 4. Event emission contract

Construct via `EventFactory` (static), attach with
`addEvent(ResourceConfig, ExternalEvent)` (base helper) or
`CollectResult.addEvent(Integer resourceId, ExternalEvent)`. `[API]`

### Construction `[API]`
```
ExternalEvent e = EventFactory.createNotificationEvent(
        long startDate, String message, EventConstants$AlertCriticalityEnum crit,
        boolean autoCancel);
// other factories: createChangeEvent, createResourceDownEvent,
// createHTAbove/Below/Equals/NotEqualEvent (metric-threshold),
// createLogEvent, createSystemDegradationEvent, createDiagnostic*Event
addEvent(rc, e);
```

| Required/used field | Source |
|---|---|
| `startDate` (timestamp) | factory arg; `getStartDate()` |
| `notificationMessage` (the text) | factory `message` arg; `getNotificationMessage()` |
| `criticality` | `AlertCriticalityEnum`; `get/setCriticality()` |
| `updateDate` / `cancelDate` | `set…` for update/cancel correlation |
| `cancelWaitCycle` / `watchWaitCycle` | auto-cancel / watch windows |
| `eventClass` / `eventSubclass` | set by the factory per `ExternalEventTypes` |

### Message-event identity = message text `[API/INFER]`

For notification/message events, **the message string is the event
identity**. To **update** an event, re-emit with the **same
`notificationMessage`** and a fresh `updateDate`; to **cancel**, set
`cancelDate` or let `cancelWaitCycle` lapse (`autoCancel=true`). Distinct
message text ⇒ distinct event. (`ExternalEventData` `[API]` batches a
resource's events with `isGenerateDownAlert` + a `ResourceStatus` when
events imply availability changes.)

---

## 5. `onTest()` contract

```
// AdapterBase: public boolean onTest(TestParam param);
public boolean onTest(TestParam p):
    try:
        openConnection(p.getAdapterConfig());   // verify creds + reachability
        return true;                             // PASS
    catch (e):
        p.setErrorCode(code);                    // optional
        p.setLocalizedMsg(localized(e));         // preferred — i18n
        p.setErrorMsg(e.getMessage());           // fallback plain text
        return false;                            // FAIL
```

- **Failure is surfaced through `TestParam`, not the return value alone**
  `[API]`: `setErrorMsg(String)` / `setLocalizedMsg(LocalizedMsg)` /
  `setErrorCode(int)`. The UI's "Test Connection" reads the message off
  the `TestParam`; returning `false` with no message gives a blank error.
  (The wrapper's `Tester.test` throwing `TestException` is a *wrapper*
  convention; at `AdapterBase` level the channel is `TestParam` + boolean.)
- **A passing test must** verify credentials *and* connectivity to the
  target and return `true`. It must **not** mutate instance state or
  create resources — test is side-effect-free.

---

## 6. `onDiscover()` contract

```
// AdapterBase: public abstract DiscoveryResult onDiscover(DiscoveryParam);
public DiscoveryResult onDiscover(DiscoveryParam p):
    DiscoveryResult dr = new DiscoveryResult(p.getAdapterInstResource());
    for each enumerated entity:
        ResourceConfig rc = toResourceConfig(entity);  // ResourceKey identity (§2)
        dr.addResource(rc);
    for each resource that vanished from the source:
        dr.changeResourceState(existingRc,
            new DiscoveryResult.StateChange(StateChangeEnum.NOTEXIST));
    dr.addRelationships(buildTopology());               // optional (§3)
    return dr;
    // on failure: dr.setLocalizedErrMsg(msg) / dr.setErrorMsg(text)
```

### `DiscoveryParam` scoping `[API]`
`getAdapterInstResource()`, `getRegexp()` (name filter),
`getDiscoveryType()`, `getParams(): Map<String,String>`,
`getAdapterCredentials()`. Honor `regexp`/`params` to bound the
enumeration when the user scopes discovery.

### State changes for disappeared/transitioning resources `[API]`
`DiscoveryResult$StateChangeEnum`: `NOTEXIST` (gone), `START`, `STOP`,
`START_MAINTENANCE`, `STOP_MAINTENANCE`. Apply via
`changeResourceState(rc, new StateChange(enum[, startTime, endTime]))`.
New resources are **added** (`addResource`), not state-changed.

### Dynamic resource kinds `[API]`
```
if (isNewResourceKind(kindKey)):                        // AdapterBase query
    dr.addResourceKind(kindKey, resourceKindDescribe,   // describe.* model objects
                       multiLanguageDescriptionsDescribe);
```
Adds a resource kind **not declared in `describe.xml`** at runtime
(mirrors `CollectResult.addResourceKind`). Pair with
`isDynamicMetricsAllowed()=true` (§01) if also pushing undeclared metrics.

---

## 7. `onConfigure()` / `AdapterStatus` contract

```
// Required:  public abstract void onConfigure(ResourceStatus, ResourceConfig);
// Optional:  public void onConfigure(AdapterStatus, Collection<ResourceConfig>);
// Finalized: public final AdapterStatus configure(AdapterConfig);
```

- `configure()` returns **`AdapterStatus(adapterInstResourceId, Status)`**
  where `Status ∈ { as_succeeded, as_failed }` `[API]`. For the platform
  to consider the instance **healthy**, return **`as_succeeded`** (with an
  optional message) and populate per-resource `ResourceStatus` via the
  passed `ResourceStatus`/`AdapterStatus.setResourceStatus(...)`. Return
  **`as_failed`** to mark the instance unhealthy (bad credentials,
  unparseable config).
- **What configure must do**: validate the `AdapterConfig` (required
  credential fields present, endpoints well-formed), build per-instance
  state, and set each managed resource's initial `ResourceStatus`.
  Reachability checks are optional here (Test covers that) but a
  hard-invalid config should return `as_failed`. `[API/INFER]`
- **Ordering guarantees** `[API/FIELD]`: `describe()` at pak install
  (§16); `configure()` at instance creation **and on every config
  update**, **before the first `collect()`** for that instance; the
  per-instance object is then reused across cycles (§01 Pass 21/23).
  So the orchestrator may safely initialize per-instance caches/pools in
  `onConfigure` and rely on them in `onCollect`.

---

## 8. `MetricDataCache` usage semantics

Ships in `vrops-adapters-sdk.jar` (`com.integrien.alive.common.adapter3`)
— reusable directly to satisfy the **duplicate-data certification
requirement** `[API]`:
```
public MetricDataCache(AdapterBase owner, int p1, int p2);   // see params below
public boolean cacheMetricData(ResourceConfig rc, MetricData md);
public int     flushCachedData();        // push accumulated → current collect
public int     flushCachedData(boolean); // forced/all vs changed-only [INFER]
public boolean isAvailabilityMetric(MetricKey);
public long    getCollectTime();
```

- **Keying** `[API/INFER]`: by `(ResourceConfig, MetricKey)`. `MetricData`
  carries `(MetricKey, timestamp, value|stringValue)`; **metric-vs-property
  is a property of the `MetricKey`** (`MetricKey.isProperty()/setProperty`),
  not of the cache call. Properties are change-only by nature; metrics are
  per-cycle samples.
- **Dedup** `[API/INFER]`: `cacheMetricData` returns `boolean` — the
  cache compares against the last cached value and **suppresses an
  unchanged value** (especially properties), so only changed/new data is
  flushed into the `CollectResult`. This is exactly the "don't re-send
  identical data every cycle" cert behavior. The two `int` constructor
  params are cache-sizing / dedup-window parameters **[INFER]** (the
  wrapper passed its `maxEvents`/window-style limits here); confirm exact
  meaning before relying on specific values. `flushCachedData(boolean)`
  distinguishes flush-all vs flush-changed **[INFER]**.
- **Usage**: `cacheMetricData(rc, md)` for every sample in `onCollect`,
  then one `flushCachedData()` near the end of the cycle. `getCollectTime`
  stamps the batch.

> If VCF-CF prefers full control, it can implement equivalent
> last-value-per-`(resource,metricKey)` dedup itself — but reusing
> `MetricDataCache` is lower-risk since it is the class the platform's
> own adapters use for the cert requirement.

---

## 9. Cancellation / stop contract

| Hook (AdapterBase) | Trigger | Orchestrator must |
|---|---|---|
| `stopCollection()` final → `onStopCollection()` `[API]` | platform requests graceful stop of an **in-flight** collect | set a `volatile` abort flag; `onCollect` loops check it and return promptly |
| `onStopResources(AdapterStatus, Collection<ResourceConfig>)` `[API]` | stop monitoring specific resources | release per-resource state for those resources |
| `onRemoveResources(AdapterStatus, Collection<ResourceConfig>)` `[API]` | remove specific resources | drop their state/caches |
| `discard()` final → `onDiscard()` `[API]` | instance removal / shutdown | close sockets, stop pools, join threads; `isDiscarded()` guards |

- **Mechanism** `[API/FIELD]`: each instance's `collect()` runs
  single-threaded on a platform worker thread (Pass 23). The entry
  methods of `AdapterInterface3` **do not declare
  `throws InterruptedException`** — so cancellation at the `AdapterBase`
  boundary is **cooperative** via `onStopCollection()` (a flag you
  check), *plus* the platform may interrupt the worker thread. The
  role-SPI layer surfaced `InterruptedException` on
  `Discoverer.getResources` / `LiveCollector.*`, confirming the platform
  interrupts long operations.
- **Expected `InterruptedException` handling**: in long loops check
  `Thread.currentThread().isInterrupted()`; on `InterruptedException`,
  **abort the cycle, restore the interrupt flag
  (`Thread.currentThread().interrupt()`), and return** — do not swallow
  it silently. This satisfies the certification **clean-thread-exit**
  requirement: `onStopCollection` must make `onCollect` return quickly so
  the worker thread exits, and `onDiscard` must join/stop any
  adapter-spawned threads so none linger after instance teardown.
- **Ordering**: `onStopCollection` (abort in-flight cycle) →
  `onStopResources`/`onRemoveResources` (per-resource teardown, as
  applicable) → `onDiscard` (instance teardown). `[API/INFER]`

---

## 10. Independence from the Suite API extension — CONFIRMED

The test/discover/collect path requires **no** Suite API client. `[API]`

- The SDK jar contains **zero** Suite-API-client classes. Its only
  non-`com.integrien` classes are logging (`AdapterLoggerFactory`),
  localization (`com.vmware.vcops.common.l10n.*`), and self-monitoring
  stats (`com.vmware.vcops.common.stats.*`) — **no REST/`SuiteAPIClient`
  type**. The lone "suiteapi" token in the surface is a *string constant*
  (`ALIVE_ADAPTER_SUITEAPI_RESOURCE_KIND`), not a dependency.
- **No** signature in `AdapterInterface3` / `AdapterBase` / `CollectResult`
  / `DiscoveryResult` / `TestParam` references a Suite-API type. The
  `SuiteAPIClient` was a field on the `UnlicensedAdapter` *wrapper*,
  injected only for adapters that read vROps' own inventory — not part of
  the base path.
- **Empirical corroboration**: 3 of the 5 surveyed third-party native
  paks (HPE, ControlUp, Lenovo) bundle **no** `vcops-suiteapi-client`
  jar at all yet collect normally; only the 2 Dell paks bundle it, and
  by use-case (see redistribution survey). The Suite API is an **optional
  extension**, not a collect-path dependency.

**Consequence for VCF-CF**: the orchestrator can target `AdapterBase`
alone and ship **without** a Suite-API client (and, per §13 + the
redistribution survey, potentially without bundling any Broadcom jar at
all via the C2 classpath route).

---

## Provenance & confidence ledger

| # | Topic | Strongest evidence | Confidence |
|---|---|---|---|
| 1 | onCollect sequence | helper API [API] + Pass 23 no-retry/single-thread [FIELD] | High (order is INFER from helper shape + role-SPI) |
| 2 | new-resource registration | `addNewResource`/`ResourceKey`/identifier types [API] | High |
| 3 | relationships | full `Relationships` surface [API] + §07 | High |
| 4 | events | `EventFactory`/`ExternalEvent` surface [API] | High; message=identity is [INFER] |
| 5 | onTest | `TestParam.setErrorMsg/setLocalizedMsg` [API] | High |
| 6 | onDiscover | `DiscoveryResult`/`StateChangeEnum`/`addResourceKind` [API] | High |
| 7 | onConfigure/AdapterStatus | `AdapterStatus$Status{as_succeeded,as_failed}` [API] + ordering [FIELD] | High |
| 8 | MetricDataCache | class surface [API] | Med — ctor int params + flush flag are [INFER] |
| 9 | cancellation/stop | hook surface [API] + interrupt model [FIELD] | High; ordering [INFER] |
| 10 | Suite-API independence | jar class inventory + empirical 3/5 paks [API] | High |

### Open / to-confirm
- **MetricDataCache** exact meaning of the two `int` ctor params and the
  `flushCachedData(boolean)` flag (sizing vs dedup-window; flush-all vs
  changed-only). Resolve before depending on specific values.
- **onCollect step order** is reconstructed from the helper API + the
  role-SPI decomposition + field logs; a live single-instance DEBUG
  capture of one cycle's helper-call order would upgrade it to [FIELD].
- **Per-resource status requirement**: whether the platform *requires* a
  `ResourceStatus` per resource each cycle or only on change — confirm
  against a live collect log.
