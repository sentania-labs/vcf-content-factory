# Framework v2 Migration Cheat-Sheet

**Purpose:** mechanical guide for `sdk-adapter-author` to migrate
compliance, synology, and unifi adapters from framework v1 to v2.
After migration each adapter must compile cleanly against
`vcfcf-adapter-base.jar + vrops-adapters-sdk-2.2.jar`. Note on
`aria-ops-core`: it remains on the **compile** classpath because
`sdk_builder.py` globs the entire `adapter_runtime/` directory; it is
harmless for v2 adapters and is correctly omitted from the v2 pak at
packaging time. See §16 for compile verification details.

---

## 1. Import replacements (mechanical)

### Remove all TVS imports

Every `import com.vmware.tvs.*` line is deleted.

| v1 import (DELETE) | v2 replacement |
|---|---|
| `import com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter;` | *(gone — VcfCfAdapter now extends AdapterBase)* |
| `import com.vmware.tvs.vrealize.adapter.core.test.Tester;` | `import com.vcfcf.adapter.spi.VcfCfTester;` |
| `import com.vmware.tvs.vrealize.adapter.core.discovery.Discoverer;` | `import com.vcfcf.adapter.spi.VcfCfDiscoverer;` |
| `import com.vmware.tvs.vrealize.adapter.core.collection.live.LiveCollector;` | `import com.vcfcf.adapter.spi.VcfCfCollector;` |
| `import com.vmware.tvs.vrealize.adapter.core.collection.historical.HistoricalCollector;` | *(gone — VcfCfCollector handles both; historical is a default no-op)* |
| `import com.vmware.tvs.vrealize.adapter.core.data.Resource;` | *(gone — use ResourceConfig / ResourceKey from SDK)* |
| `import com.vmware.tvs.vrealize.adapter.core.data.ResourceCollection;` | *(gone — replaced by Relationships or List<ResourceConfig>)* |
| `import com.vmware.tvs.vrealize.adapter.core.extensions.suiteapi.SuiteAPIClient;` | *(gone — optional, supplied via ForeignResourceResolver.SuiteApiBridge)* |
| `import com.vmware.tvs.vrealize.adapter.core.test.TestException;` | *(gone — throw any Exception from VcfCfTester.test())* |
| `import com.vmware.tvs.vrealize.adapter.core.collection.CollectionException;` | *(gone — throw any Exception from VcfCfCollector.collect())* |

### Keep these (unchanged, from vrops-adapters-sdk-2.2.jar)

```java
import com.integrien.alive.common.adapter3.*;
import com.integrien.alive.common.adapter3.config.*;
import com.integrien.alive.common.adapter3.events.*;
import com.integrien.alive.common.adapter3.describe.*;
import com.integrien.alive.common.util.CommonConstants;
import com.vcfcf.adapter.*;
import com.vcfcf.adapter.http.*;
import com.vcfcf.adapter.spi.*;
import com.vcfcf.adapter.stitch.*;
```

---

## 2. Adapter class declaration

**v1:**
```java
public class MyAdapter extends VcfCfAdapter<MyConfig> {
    // VcfCfAdapter extended UnlicensedAdapter
}
```

**v2 (no change to the declaration itself):**
```java
public class MyAdapter extends VcfCfAdapter<MyConfig> {
    // VcfCfAdapter now extends AdapterBase directly
}
```

The constructors are unchanged:
```java
public MyAdapter() { super(); }
public MyAdapter(String adapterDir, Integer instanceId) {
    super(adapterDir, instanceId);
}
```

---

## 3. onDescribe (provided by the framework; adapter constructor required)

**v1:** `UnlicensedAdapter` provided `onDescribe()` automatically, loading
`describe.xml` from `getAdapterDirectory()` (abstract, subclass returned a
static kind string). No adapter code required beyond implementing the abstract
method.

**v2:** `VcfCfAdapter` provides a default `onDescribe()` implementation.
Adapters do not need to implement it, **but they MUST supply the adapter
kind key via the constructor.** This is mandatory — failure to do so causes
an NPE / adapter-not-found failure during pak install (build 44 root cause;
see `lessons/controller-describe-bare-instantiation.md`).

**Why:** During pak install the controller instantiates the adapter class
bare (no-arg reflection) and calls `describe()`. At that point the platform
has NOT injected any config, so `getAdapterKind()` returns null.
The framework default `onDescribe()` resolves the kind key from the value
stored at construction time, avoiding the null dereference.

**Required constructor pattern (all adapter subclasses):**
```java
private static final String ADAPTER_KIND = "my_adapter_kind";

public MyAdapter() {
    super(ADAPTER_KIND);                    // kind stored for onDescribe()
}
public MyAdapter(String adapterDir, Integer instanceId) {
    super(ADAPTER_KIND, adapterDir, instanceId);
}
```

The kind key must match the `key` attribute on `<AdapterKind>` in
`describe.xml` and the directory name in the pak layout
(`<adaptersHome>/<key>/conf/describe.xml`).

**What the framework default does:**
```java
@Override
public AdapterDescribe onDescribe() {
    // 1. Use constructor-stored kind key (safe under bare instantiation)
    // 2. Fall back to getAdapterKind() (only non-null when platform injects config)
    // 3. If both null: throw RuntimeException with actionable message
    String kind = this.adapterKindKey != null ? this.adapterKindKey : getAdapterKind();
    Path describeFile = getAdapterDescribeFile(kind, "describe.xml");
    try (InputStream is = Files.newInputStream(describeFile)) {
        return AdapterDescribe.make(is);
    } catch (Exception e) {
        throw new RuntimeException(/* path + source in message */);
    }
}
```

`getAdapterDescribeFile(kind, "describe.xml")` resolves to
`<adaptersHome>/<kind>/conf/describe.xml` — the SDK's own canonical path
for describe files. `getAdaptersHome()` reads the `ADAPTER_HOME` system
property, which the platform sets for both the collector and the controller.

On any failure the method throws a `RuntimeException` with the resolved
path and kind source in the message; it never silently returns `null`.

**Override pattern (only when custom handling is required):**
```java
@Override
public AdapterDescribe onDescribe() {
    Path describeFile = getAdapterDescribeFile(ADAPTER_KIND, "describe.xml");
    try (InputStream is = Files.newInputStream(describeFile)) {
        return AdapterDescribe.make(is);
    } catch (Exception e) {
        throw new RuntimeException(
                "onDescribe: failed to load " + describeFile, e);
    }
}
```

When overriding, always use the static `ADAPTER_KIND` constant directly —
never call `getAdapterKind()` in the describe path.

**Migration from build 44 breakage:** any adapter that was migrated to v2
before this fix (calling the no-arg `super()` from its no-arg constructor)
must update its constructors to the keyed pattern above. The compliance
adapter is the reference — see its `public ComplianceAdapter()` and
`public ComplianceAdapter(String, Integer)` constructors.

---

## 4. configureAdapter (replaces configure)

**v1:**
```java
@Override
public void configure(ResourceStatus status, ResourceConfig rc) {
    // read creds, build httpClient
}
```

**v2:**
```java
@Override
protected void configureAdapter(ResourceStatus status, ResourceConfig rc) {
    // same body — read creds, build httpClient
}
```

**What changes:** method name only (`configure` → `configureAdapter`).
The method signature and body are identical. Keep `@Override` —
`configureAdapter` is declared `abstract` in `VcfCfAdapter` and the
annotation is correct. The v1 confusion arose because the old TVS
`configure()` was not abstract in `UnlicensedAdapter`; the v2 method
is.

### SSL in configureAdapter

**v1:** `HttpClientBuilder.allowInsecure(true)` (insecure by default
for most lab adapters).

**v2 production:**
```java
this.httpClient = HttpClientBuilder.builder()
    .baseUrl(host)
    .platformSsl(this)        // platform trust store — preferred
    .auth(new BasicAuth(...))
    .build();
```

**v2 lab (explicit opt-out):**
```java
this.httpClient = HttpClientBuilder.builder()
    .baseUrl(host)
    .allowInsecure(true)      // explicit opt-out documented as lab-only
    .build();
```

---

## 5. getTester (new signature)

**v1:**
```java
@Override
public Tester getTester(ResourceStatus status, ResourceConfig rc) {
    return (param) -> {
        try { doTest(); }
        catch (Exception e) { throw new TestException(e.getMessage()); }
    };
}
```

**v2:**
```java
@Override
protected VcfCfTester<MyConfig> getTester() {
    return (config, httpClient, param) -> {
        // Throw any Exception to signal failure.
        // The orchestrator calls param.setErrorMsg(e.getMessage()).
        doTest(config, httpClient);
    };
}
```

Key changes:
- No `ResourceStatus status, ResourceConfig rc` parameters — use the
  instance fields `this.config` and `this.httpClient` (or capture from
  the lambda context). `VcfCfTester.test()` receives `config` and
  `httpClient` directly.
- Throw any `Exception` on failure instead of `TestException`.
- `param.setLocalizedMsg(...)` is available for i18n error messages.
- Return `null` to skip the test (passes always).

> **Raw-type note (applies to §5, §6, §7):** `VcfCfAdapter` declares
> `getTester()`, `getDiscoverer()`, and `getCollector()` as raw types
> with `@SuppressWarnings("rawtypes")` for binary compatibility. Your
> overrides with the parameterized form (`VcfCfTester<MyConfig>`, etc.)
> compile correctly — the parameterized return is a covariant refinement
> the compiler accepts. Do not let the raw declaration in the base class
> tempt you into dropping the type parameter from your overrides.

---

## 6. getDiscoverer (new signature)

**v1:**
```java
@Override
public Discoverer getDiscoverer(ResourceStatus status, ResourceConfig rc) {
    return (param) -> {
        ResourceCollection col = new ResourceCollection();
        // enumerate resources, add to col
        return col;
    };
}
```

**v2:**
```java
@Override
protected VcfCfDiscoverer<MyConfig> getDiscoverer() {
    return (config, httpClient, param, dr) -> {
        // enumerate resources, call dr.addResource(rc) for each one
        // dr.changeResourceState(rc, new StateChange(StateChangeEnum.NOTEXIST))
        //   for disappeared resources
        // dr.addRelationships(rels) for initial topology (optional)
    };
}
```

Key changes:
- Returns `void`; the `DiscoveryResult dr` is passed in and populated
  directly via `dr.addResource(ResourceConfig)`.
- The orchestrator constructs the `DiscoveryResult` — do not `new` it.
- `ResourceCollection` is gone; iterate and call `dr.addResource()` per resource.
- `StateChange` / `StateChangeEnum` are in
  `com.integrien.alive.common.adapter3.DiscoveryResult`.

**Building ResourceConfig for discovery:**
```java
// v1:
ResourceKey key = new ResourceKey(adapterKind, resourceKind, name);
key.addIdentifier(new ResourceIdentifierConfig("my_id", idValue, true));
ResourceConfig rc = new ResourceConfig(key);
dr.addResource(rc);
```
This is unchanged in v2.

---

## 7. getLiveDataCollector → getCollector (major rename + reshape)

**v1 (three separate methods):**
```java
@Override
public LiveCollector getLiveDataCollector(ResourceStatus status, ResourceConfig rc) {
    return new LiveCollector() {
        public ResourceCollection getCurrentMetrics(ResourceConfig rc, ResourceCollection acc)
                throws CollectionException, InterruptedException { ... }
        public ResourceCollection getEvents(ResourceConfig rc, ResourceCollection acc) { ... }
        public ResourceCollection getRelationships(ResourceConfig rc, ResourceCollection acc) { ... }
        public boolean shouldForceUpdateRelationships() { return false; }
    };
}
```

**v2 (single interface, three default methods + collect):**
```java
@Override
protected VcfCfCollector<MyConfig> getCollector() {
    return new VcfCfCollector<MyConfig>() {

        @Override
        public void collect(MyConfig config, ManagedHttpClient http,
                ResourceConfig rc, List<MetricData> out, AdapterBase adapter)
                throws InterruptedException, Exception {
            // Add MetricData samples to 'out'.
            // Use new MetricKey(key) for metrics.
            // Use new MetricKey(true, key) for string/numeric properties.
            // Check adapter.shouldCollect(rc, metricKey) to skip disabled metrics.
        }

        @Override
        public void collectEvents(MyConfig config, ManagedHttpClient http,
                ResourceConfig rc, AdapterBase adapter) throws Exception {
            // adapter.addEvent(rc, EventFactory.createNotificationEvent(...));
        }

        @Override
        public Relationships collectRelationships(MyConfig config,
                ResourceConfig rc) {
            RelationshipBuilder rb = new RelationshipBuilder(ADAPTER_KIND);
            // rb.parent(...) / rb.parentForeign(...) / rb.childForeign(...)
            return rb.build();
        }

        @Override
        public ResourceStatusEnum mapCollectException(Exception e) {
            if (e instanceof java.net.ConnectException)
                return ResourceStatusEnum.RESOURCE_STATUS_DOWN;
            return ResourceStatusEnum.RESOURCE_STATUS_ERROR;
        }
    };
}
```

Key changes:
- `ResourceCollection` is gone. Metrics are accumulated in
  `List<MetricData> out`; the orchestrator handles cache/flush.
- Return values are gone from `collect()` / `collectEvents()` /
  `collectRelationships()` — they are void or return dedicated types.
- `CollectionException` is gone — throw any `Exception`.
- `shouldForceUpdateRelationships()` is gone — `collectRelationships()`
  is called every cycle by default.
- Resource status is set automatically by the orchestrator based on
  whether `collect()` succeeds or throws. Override
  `mapCollectException(Exception)` for custom DOWN / NO_DATA semantics.

---

## 8. getHistoricalDataCollector

**v1:**
```java
@Override
public HistoricalCollector getHistoricalDataCollector(
        ResourceStatus status, ResourceConfig rc) {
    return null; // disabled
}
```

**v2:** Delete the method. Historical collection is a default no-op in
`VcfCfCollector`. If the adapter had a non-null historical collector,
incorporate it into `VcfCfCollector.collect()` with a time-range
parameter from the adapter's own state.

---

## 9. getAutoDiscoveryEnabled

**v1:**
```java
@Override
public boolean getAutoDiscoveryEnabled(ResourceStatus status, ResourceConfig rc) {
    return true; // required
}
```

**v2:** Delete the method. Auto-discovery of new resources is handled
by calling `adapter.registerNewResource(key)` from within
`VcfCfCollector.collect()` or `VcfCfCollector.rediscover()` when a
new resource is encountered.

For full top-of-cycle rediscovery (detecting removed resources),
override `VcfCfCollector.needsRediscovery()` to return `true` and
implement `VcfCfCollector.rediscover()`.

---

## 10. needRediscovery

**v1:**
```java
@Override
protected boolean needRediscovery(ResourceConfig adapterInst,
        Collection<ResourceConfig> resources) {
    return false;
}
```

**v2:** Delete the override. If the adapter needs rediscovery, override
`VcfCfCollector.needsRediscovery(config)` and
`VcfCfCollector.rediscover(config, httpClient, adapterInst, adapter)`.

---

## 11. Resource API (no more aria-ops-core Resource)

**v1 (aria-ops-core Resource):**
```java
Resource r = new Resource(key);
r.addData("metric|key", 42.0);       // numeric metric
r.addData("prop|key", "value");      // BUG: isProperty=false, silently dropped
addProperty(r, "prop|key", "value"); // correct v1 helper
r.addChild(childResource);
r.addParent(parentResource);
```

**v2 (pure SDK MetricData / ResourceKey):**
```java
// In collect(): append MetricData to the 'out' list:
out.add(new MetricData(new MetricKey("metric|key"), ts, 42.0));
out.add(new MetricData(new MetricKey(true, "prop|key"), ts, "value"));

// Or use VcfCfAdapter helpers:
pushMetric(rc, "metric|key", 42.0, ts);
pushStringProperty(rc, "prop|key", "value");

// Relationships: return from collectRelationships():
RelationshipBuilder rb = new RelationshipBuilder(ADAPTER_KIND);
ResourceKey parent = rb.resource("ParentKind", "Parent Name", "id", parentId);
ResourceKey child  = rb.resource("ChildKind",  "Child Name",  "id", childId);
rb.parent(parent, child);
return rb.build(); // returns Relationships, not ResourceCollection
```

---

## 12. ForeignResourceResolver and Suite API stitching

### Primary stitching path — SuiteApiStitcher (ambient transport)

For adapters that push properties or stats onto a foreign VCF Ops
resource (e.g. a `VMWARE/HostSystem`), the v2 primary path is
`SuiteApiStitcher`. See the **"Ambient Suite API stitching transport"**
section in `context/tier2_architecture.md` for the full contract.

```java
// In configureAdapter():
stitcher = SuiteApiStitcher.create(this, adapterLogger());
// or, for remote collectors with explicit Suite API creds:
stitcher = SuiteApiStitcher.createExplicit(
    this, adapterLogger(), host, user, password);

// In collect():
stitcher.pushProperties(foreignResourceUuid, props, System.currentTimeMillis());
```

Release in `onDiscard()`:
```java
@Override
public void onDiscard() {
    if (stitcher != null) stitcher.discard();
    super.onDiscard();
}
```

### Cross-MP UUID lookup — ForeignResourceResolver

`ForeignResourceResolver` is for **cross-MP resource UUID lookup** (e.g.
resolving a Datastore UUID from an identifier value). It is not the
stitching transport.

**v1:**
```java
ForeignResourceResolver resolver =
    new ForeignResourceResolver(suiteAPIClient, logger);
```

**v2:**
```java
// Wire in the Suite API client via the SuiteApiBridge functional interface.
// The lambda calls your pak-bundled Suite API client.
ForeignResourceResolver resolver = new ForeignResourceResolver(
    (adapterKind, resourceKind) -> {
        List<ForeignResourceResolver.ResourceEntry> entries = new ArrayList<>();
        // Call your Suite API client and map results to ResourceEntry objects.
        // Each ResourceEntry: adapterKind, resourceKind, name, identifiers list.
        return entries;
    },
    loggerInstance
);
```

If the adapter does not do cross-MP stitching or UUID lookup, no change is
needed.

---

## 13. Relationship emission (onCollect path)

**v1:**
```java
// In LiveCollector.getRelationships():
ResourceCollection col = new ResourceCollection();
ResourceHandle parent = rb.resource(kind, name, idKey, idVal);
ResourceHandle child  = rb.resource(...);
rb.parent(parent, child);
col.add(parent.getResource()); // BUG risk: must call add() or silently lost
return col;
```

**v2:**
```java
// In VcfCfCollector.collectRelationships():
RelationshipBuilder rb = new RelationshipBuilder(ADAPTER_KIND);
ResourceKey parent = rb.resource(kind, name, idKey, idVal);
ResourceKey child  = rb.resource(...);
rb.parent(parent, child);
return rb.build();
// Orchestrator calls: adapter.addRelationshipsToCurrentCycle(rels)
```

The orchestrator handles the `addRelationshipsToCurrentCycle` call.
The `rel.add()` requirement (v1 silent loss bug) is eliminated.

---

## 14. Event emission (unchanged API, simplified path)

**v1 (in LiveCollector.getEvents):**
```java
ResourceCollection col = new ResourceCollection();
// Build events, add to Resource objects in col
return col;
```

**v2 (in VcfCfCollector.collectEvents):**
```java
ExternalEvent e = EventFactory.createNotificationEvent(
    System.currentTimeMillis(), "message text", criticality, autoCancel);
adapter.addEvent(rc, e);
```

Direct `adapter.addEvent()` call — no `ResourceCollection` wrapper.
Message text is the event identity (spec/19 §4): same text = update,
different text = new event.

---

## 15. Logging

Use `logInfo()` / `logWarn()` / `logError()` on the adapter instance
for messages that belong to the adapter itself (configure, collect
lifecycle, errors). From within SPI implementations, the adapter is
available as the `adapter` parameter (cast to `VcfCfAdapter` to access
log methods if needed, or pass a logger reference to the SPI object's
constructor).

**For helper/component class loggers — use `componentLogger(Class)`:**

```java
// In configureAdapter():
vSphereClient = new VSphereClient(host, componentLogger(VSphereClient.class));
stitcher      = SuiteApiStitcher.create(this, componentLogger(SuiteApiStitcher.class));
```

**Never shadow `adapterLogger()` in adapter subclasses.** The base's
`adapterLogger()` is private. If you have a private `adapterLogger()`
in your adapter that calls `getAdapterLoggerFactory().getLogger(cls)`,
delete it and replace all call sites with
`componentLogger(HelperClass.class)`. The shadow footgun:

| Risk | What happens |
|---|---|
| Omit `setLevel` (build 45) | WARN root threshold silently drops INFO — helper-client breadcrumbs invisible |
| Include `setLevel` but race a `logging.properties` reload | Level reverts until next `configure` cycle |
| Break the double-checked-lock cache | Extra `getLogger` calls per collect cycle |

`componentLogger` eliminates all three: same factory, same level
discipline, called at configure time (after any reload).

**Hot-reload classloader behavior — per-adapter log file appender
(proven, synology build 16, devel 9.0.2, 2026-06-10):**

When a pak is hot-reloaded (re-installed without collector restart), the
logging factory re-initializes and the per-adapter file appender
**detaches**. Log output from the new build is absorbed by the root logger
(`collector.log`) only until the adapter completes its first `configure`
cycle, at which point `componentLogger` re-wires the appender. The gap is
the window between pak load and the first completed configure.

Operational consequence: `collector.log` is the authoritative source for
post-reload diagnostics. Per-adapter logs resume silently once configure
completes — if they appear empty post-install, check `collector.log` first.
A collector restart eliminates the gap (appender wires correctly at startup).
See also the Logging authoring contract note in `context/tier2_architecture.md`.

---

## 16. Semantic changes adapter authors must know

| Topic | v1 behavior | v2 behavior |
|---|---|---|
| Per-resource status | Not required; set by UnlicensedAdapter wrapper | **Required every cycle** by the orchestrator. Set automatically on success (`DATA_RECEIVING`) or exception (via `mapCollectException`). |
| Test failure channel | `TestException.message` surfaced via wrapper | `param.setErrorMsg(e.getMessage())` called by orchestrator automatically when tester throws. |
| New resource registration | `getAutoDiscoveryEnabled()=true` gates processMetrics | `adapter.registerNewResource(key)` called from `collect()` or `rediscover()`. |
| Relationship max | `maximumRelationshipsPerCollection` field on UnlicensedAdapter | `VcfCfAdapter.MAX_RELATIONSHIPS_PER_CYCLE` constant (default 100 000); override `getMaxRelationshipsPerCycle()`. |
| MetricDataCache | Auto-created and auto-flushed by UnlicensedAdapter | Auto-created in `onConfigure` and auto-flushed at end of `onCollect`. Constructor params `(1000, 100)` are [INFER] — see spec/19 §8. |
| SSL | `insecureSslContext()` embedded in HttpClientBuilder (inline, always insecure) | JVM default trust store when no SSL configured; `platformSsl(this)` for platform trust; `allowInsecure(true)` for explicit lab opt-out. |
| SuiteAPIClient | Injected as field `suiteAPIClient` on UnlicensedAdapter | Not injected. Primary stitching path is `SuiteApiStitcher` (ambient transport — see "Ambient Suite API stitching transport" in `context/tier2_architecture.md`). `ForeignResourceResolver.SuiteApiBridge` is for cross-MP UUID lookup only. Neither is required on the collect path. |
| onDiscard | Call `super.onDiscard()` first | Same — call `super.onDiscard()` first. |

---

## 17. Compile verification after migration

The adapter must compile cleanly. `sdk_builder.py` automatically builds
the classpath from `adapter_runtime/` (which includes
`vcfcf-adapter-base.jar`, `vrops-adapters-sdk-2.2.jar`, and
`aria-ops-core-*.jar` for v1 compatibility) plus the project's `lib/*.jar`.
`aria-ops-core` is on the **compile** classpath but is correctly excluded
from the v2 pak at packaging time — its presence at compile time is harmless.

Effective compile classpath (managed by the builder):
```
vcfcf-adapter-base.jar : vrops-adapters-sdk-2.2.jar [: aria-ops-core-*.jar] [: <vendor jars>]
```

If `javac` reports a missing symbol:
- `com.vmware.tvs.*` → clean-room wall violation; report as TOOLSET GAP.
- `com.integrien.*` → symbol is in vrops-adapters-sdk-2.2.jar; add jar to CP.
- `com.vcfcf.*` → symbol is in vcfcf-adapter-base.jar; rebuild framework if needed.

---

## 18. Multi-resource collect idiom

### When to use which idiom

The framework calls the collector's `collect(rc)` and
`collectRelationships(config, rc)` **once per discovered resource** per
cycle. Two idioms follow from this:

**Single-synthetic-world** (used by compliance and most adapters whose
API naturally returns one blob of results):

- One `collect()` call reaches the API and pushes all metrics directly.
- The "world" resource is the only resource kind; there is nothing to
  dispatch on.

**Multi-resource** (used by adapters — like Synology — whose single shared
API response feeds many discovered resources):

- One shared API call per cycle feeds many `collect(rc)` calls.
- A per-cycle **snapshot cache** holds the API responses; each
  `collect(rc)` dispatches on `rc.getResourceKind()` and serves from
  the snapshot.
- Relationships are built once and emitted only on the World/root
  resource's `collectRelationships` call.

Use the multi-resource idiom when:
1. Two or more resource kinds share a common API response (fetching it
   once per resource would be redundant and rate-limit-hostile).
2. The discovered resource tree has more than one kind (pool, disk,
   volume, etc.).

Use single-world when the adapter has exactly one resource that reports
all metrics.

### Canonical pattern (Synology build 14)

```java
// -----------------------------------------------------------------------
// Snapshot field — volatile for cross-thread read visibility
// -----------------------------------------------------------------------
private volatile Snapshot snapshot;
private static final long MIN_REFRESH_INTERVAL_MS = 60_000L;

// -----------------------------------------------------------------------
// currentSnapshot() — synchronized to make the check-then-refresh atomic.
// A refresh failure propagates out (never silently returns empty data).
// -----------------------------------------------------------------------
private synchronized Snapshot currentSnapshot() throws Exception {
    Snapshot s = this.snapshot;
    long now = System.currentTimeMillis();
    if (s == null || (now - s.builtAt) >= MIN_REFRESH_INTERVAL_MS) {
        api.ensureSession();
        s = Snapshot.build(api, this);    // throws on REST/session failure
        this.snapshot = s;
    }
    return s;
}

// -----------------------------------------------------------------------
// getCollector — per-resource dispatch, topology anchored on World
// -----------------------------------------------------------------------
@Override
protected VcfCfCollector<MyConfig> getCollector() {
    return new VcfCfCollector<MyConfig>() {

        @Override
        public void collect(MyConfig cfg, ManagedHttpClient http,
                ResourceConfig rc, List<MetricData> out, AdapterBase adapter)
                throws InterruptedException, Exception {
            Snapshot snap = currentSnapshot();       // shared across all rc calls
            dispatchCollect(rc, snap, out);          // switch on rc.getResourceKind()
        }

        @Override
        public Relationships collectRelationships(MyConfig cfg,
                ResourceConfig rc) {
            // Emit the full topology ONCE, anchored on the root resource.
            // Non-root resources return null (no-op).
            if (!"MyWorldKind".equals(rc.getResourceKind())) {
                return null;
            }
            try {
                return buildRelationships(currentSnapshot());
            } catch (Exception e) {
                logWarn("Relationship build failed: " + e.getMessage());
                return null;
            }
        }
    };
}
```

Reset `this.snapshot = null` in `configureAdapter()` so the first collect
of a new cycle forces a fresh pull against the reconfigured endpoint.

### Concurrency caveat

The framework may invoke `collect(rc)` for multiple resources
concurrently within one cycle. The `currentSnapshot()` accessor must be
thread-safe. The Synology pattern achieves this with two layers:

- The `snapshot` field is `volatile` so all threads see the latest
  reference without a lock for reads.
- `currentSnapshot()` itself is `synchronized` so the check-then-refresh
  sequence is atomic — only one thread performs the API pull; the rest
  wait on the monitor and receive the already-built snapshot.

Do not relax either: `volatile`-only allows the check-then-refresh race;
`synchronized`-only without `volatile` allows a thread outside the method
to read a stale reference.

### Honesty requirement — failed refresh must be loud

A snapshot refresh that fails (REST error, session expired, network down)
must **throw out of `currentSnapshot()`** so the framework marks the
resource ERROR/DOWN. Never catch the exception inside `currentSnapshot()`
and return a partial or empty snapshot — that would make a broken source
look healthy. Cross-reference:
`lessons/unreadable-is-not-compliant.md`.

Per-endpoint sub-failures within an otherwise-healthy snapshot (e.g. an
optional UPS endpoint returning 404) may be caught locally and the
affected sub-resource skipped — with a WARN log so the operator can
see it. The Synology UPS handling is the canonical example: the
`try/catch` in `Snapshot.build()` logs an INFO breadcrumb and leaves
`s.ups = null`; the collector checks for null and skips cleanly. This is
acceptable because UPS is genuinely optional and its absence is not a
data-quality failure.

---

## 19. §15 exemplar note — componentLogger

**Synology build 14** is the clean exemplar for `componentLogger(Class)`:
it contains no private `adapterLogger()` shadow anywhere. Every helper
that needs a logger receives `componentLogger(HelperClass.class)` wired
in `configureAdapter()`.

**Compliance** still carries its historical private `adapterLogger()`
shadow (introduced before `componentLogger` was public). It is the
target of the pending compliance v2 fixup and will be cleaned up on the
next touch. Until then, treat compliance as the negative example for §15
and synology as the positive one.

---

## 20. Typed config POJOs carry from v1 to v2 unmodified

Config POJOs (e.g. `SynologyConfig`, `ComplianceConfig`) use plain
`public final` fields and a single constructor that converts raw
`String` identifiers from the platform. They contain no SPI, no TVS
imports, and no framework types — so they compile cleanly against either
v1 or v2 and require no changes during migration. Carry them forward
as-is. The `getIdentifier()` / `getCredentialField()` call sites in
`configureAdapter()` that build the POJO are likewise unchanged.

---

## 21. HTTP auth strategy matrix

Three proven auth shapes exist across the three v2 adapters. Choose the
shape that matches your target API's auth mechanism. All three use
`ManagedHttpClient` for cancellation/timeout handling (see §21.4 below)
and observe the same redaction rule (§21.5).

### 21.1 Basic auth + raw SOAP session (compliance)

**Exemplar:** `content/sdk-adapters/compliance/src/.../VSphereClient.java`

**When to use:** the target API speaks SOAP (or a custom HTTP protocol)
where session management is fully hand-built. The adapter owns the
entire transport layer — no `HttpClientBuilder` auth strategy is used.
VSphereClient issues a `Login` SOAP operation that returns a session
cookie (`vmware_soap_session=...`), then sends that cookie on every
subsequent call.

**How credentials enter:** `configureAdapter()` reads `username` and
`password` from `getCredentialField(resourceConfig, "username"/"password")`
and `vcenter_host` from `getIdentifier(resourceConfig, "vcenter_host")`.
They are passed directly into `new VSphereClient(host, username, password, logger)`.
The POJO (`ComplianceConfig`) holds them as `public final` fields; the
adapter never logs them.

**Session lifecycle:**
```java
// connect(): RetrieveServiceContent (no cookie) then Login (returns Set-Cookie)
vsphere.connect();
// Every subsequent call: sends Cookie: vmware_soap_session=<value>
// Keepalive via CurrentTime — cheap call; reconnect on any failure
vsphere.ensureConnected();
// Teardown in onDiscard():
if (vsphere != null) vsphere.disconnect();  // sends Logout SOAP, clears cookie
```

The `post()` method sets `connectTimeout(30 000 ms)` and
`readTimeout(120 000 ms)` directly on `HttpURLConnection`. These are
fixed constants in `VSphereClient` — not wired through `ManagedHttpClient`
(VSphereClient predates the framework HTTP layer and speaks SOAP over raw
`HttpURLConnection`).

**Cancellation:** `HttpURLConnection.setReadTimeout(120 000)` provides a
wall-clock bound per call. There is no framework-level cancellation hook
because `ManagedHttpClient` is not used; if the SOAP server hangs beyond
the read timeout the thread will unblock with a `SocketTimeoutException`.

### 21.2 Query-param session token (synology)

**Exemplar:** `content/sdk-adapters/synology/src/.../SynologyApiClient.java`

**When to use:** the target API authenticates via a session ID appended
as a query parameter (e.g. `&_sid=<token>`) to every request. The DSM
Web API documents `_sid` as the standard mechanism; a Cookie header may
also work but is not the documented path. Because `SessionCookieAuth` adds
a `Cookie` header, not a query parameter, this shape manages the session
ID entirely within the client class rather than using an `HttpClientBuilder`
auth strategy — as the `SynologyApiClient` class comment notes, this is a
known framework gap (a `QueryParamAuth` strategy does not yet exist).

**How credentials enter:** `configureAdapter()` reads `username`, `password`,
`host`, `port` via `getCredentialField`/`getIdentifier`, builds a
`SynologyConfig` POJO, then constructs:
```java
this.api = new SynologyApiClient(httpClient, cfg.username, cfg.password,
        componentLogger(SynologyApiClient.class));
```
The `ManagedHttpClient` is built without an auth strategy:
```java
HttpClientBuilder.builder().baseUrl(cfg.baseUrl()).timeout(Duration.ofSeconds(30)).build()
```

**Session lifecycle:**
```java
// login(): POST /webapi/entry.cgi?api=SYNO.API.Auth&method=login&account=...&passwd=...
// Returns JSON with data.sid; stored as this.sid
api.ensureSession();   // calls login() if sid == null

// Every authenticated call appends: &_sid=<sid>
// On error codes 106/107/119 (session expired): invalidateSession() + login() + retry

// Teardown in onDiscard():
SynologyApiClient a = this.api;
if (a != null) a.logout();   // POST .../logout&session=...; sets sid = null
```

**Redaction requirement:** `_sid`, `passwd`, and `account` must never
appear in thrown messages or log lines. `SynologyApiClient.redact(String)`
strips all three from any path/query string before it reaches a log or
exception:
```java
static String redact(String path) {
    return path
        .replaceAll("(?i)(_sid=)[^&]*", "$1<redacted>")
        .replaceAll("(?i)(passwd=)[^&]*", "$1<redacted>")
        .replaceAll("(?i)(account=)[^&]*", "$1<redacted>");
}
```
Apply `redact()` to any string derived from a URL or query before passing
it to `log.*()` or `throw new IOException(...)`. The HTTP status code and
the api/version/method path portion are left intact for diagnostics.

**Cancellation/timeout:** `ManagedHttpClient` is wired with
`.timeout(Duration.ofSeconds(30))` in `buildHttpClient`. The framework
honours the timeout per-request; if the session refresh also hangs the
same timeout applies (each `callRaw` call goes through `ManagedHttpClient`).

### 21.3 Session-cookie header auth (unifi)

**Exemplar:** `content/sdk-adapters/unifi/src/.../UniFiApiClient.java`

**When to use:** the target API issues a session token in a `Set-Cookie`
response header after a credential `POST`, and expects that cookie
re-presented on every subsequent request. UniFi OS sets a `TOKEN` cookie;
classic UniFi controllers set `unifises`. The framework `SessionCookieAuth`
strategy handles this natively: it calls a login closure on first use or
after a 401, stores the returned token, and adds `Cookie: TOKEN=<value>` to
every request transparently.

**How credentials enter:** `configureAdapter()` reads `username`, `password`,
`host`, `port` via `getCredentialField`/`getIdentifier`, builds a `UniFiConfig`
POJO, then calls `buildHttpClient(cfg)`:
```java
// Raw client — no auth strategy, used only for the login round-trip
ManagedHttpClient rawHttp = baseBuilder(cfg).build();

// Login closure: POST /api/auth/login, JSON body, extract TOKEN/unifises cookie
SessionCookieAuth auth = new SessionCookieAuth("TOKEN",
    () -> UniFiApiClient.login(rawHttp,
            componentLogger(UniFiApiClient.class),
            cfg.username, cfg.password));

// Authenticated client — auth strategy attached; TOKEN cookie added automatically
this.httpClient = baseBuilder(cfg).auth(auth).build();
this.api = new UniFiApiClient(this.httpClient, componentLogger(UniFiApiClient.class));
```

**Session lifecycle:** `SessionCookieAuth` is automatic — the framework
calls the login closure when no cookie is present or on a 401. The adapter
does not call `login()` directly in `configureAdapter()`. In `onDiscard()`:
```java
SuiteApiStitcher st = this.suiteStitcher;
if (st != null) st.discard();
super.onDiscard();   // always last
// Note: UniFiAdapter does not explicitly logout the session; the TOKEN
// expires server-side. If an explicit logout is needed, call
// rawHttp.post("/api/auth/logout", ...) before super.onDiscard().
```

**Cookie extraction:** `UniFiApiClient.login()` checks both `TOKEN` and
`unifises` in the response `set-cookie` headers to support both UniFi OS
and classic controllers:
```java
String token = extractCookie(resp, "TOKEN");
if (token == null) token = extractCookie(resp, "unifises");
```

**Redaction requirement:** `TOKEN`, `unifises`, and `"password"` JSON field
values must never appear in log lines or exception messages.
`UniFiApiClient.redact(String)` strips all three:
```java
static String redact(String s) {
    return s
        .replaceAll("(?i)(TOKEN=)[^;&\\s]*", "$1<redacted>")
        .replaceAll("(?i)(unifises=)[^;&\\s]*", "$1<redacted>")
        .replaceAll("(?i)(\"password\"\\s*:\\s*\")[^\"]*", "$1<redacted>")
        .replaceAll("(?i)(password=)[^&\\s]*", "$1<redacted>");
}
```
On login failure the adapter throws with only the HTTP status code — never
the request body (plaintext password) or any cookie value.

**Cancellation/timeout:** `ManagedHttpClient` is wired with
`.timeout(Duration.ofSeconds(30))` and a `RetryPolicy` (3 attempts,
1 000 ms base delay) in `baseBuilder`. Both the login round-trip (`rawHttp`)
and authenticated calls (`this.httpClient`) use the same timeout.

### 21.4 Cancellation and timeout handling (all shapes)

`ManagedHttpClient` (shapes 21.2 and 21.3) respects a `.timeout(Duration)`
set at build time. The framework propagates `InterruptedException` from
`http.get(...)` / `http.post(...)` so the collector can respond to a
cycle cancellation signal — always declare `throws InterruptedException` on
methods that call `ManagedHttpClient`. Do not swallow `InterruptedException`:
re-interrupt the thread or let it propagate:
```java
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
    throw e;   // or wrap in a RuntimeException and rethrow
}
```

For raw-SOAP adapters (shape 21.1) the timeout is set per-connection via
`HttpURLConnection.setConnectTimeout` / `setReadTimeout`. There is no
framework-level interrupt hook; a hung SOAP call will unblock only when
the socket timeout fires.

### 21.5 Redaction rule (all shapes)

Credential values — passwords, session tokens, session IDs — must **never**
appear in thrown exception messages, log lines, or any string that could
reach `collector.log` or a test-connection error dialog. The rule
(`rules/no-secrets-on-disk.md`) is enforced at code-review time.

**Log the mechanism and principal name, not the value:**
```java
// CORRECT
log.info("Synology login succeeded, session=" + SESSION_NAME);
log.info("UniFi session acquired");
log.warn("Logout failed (non-fatal): " + redact(e.getMessage()));

// WRONG — never log or throw credential values
log.info("Logged in with password=" + password);
throw new IOException("Login failed, token=" + token);
```

Each adapter provides a `static String redact(String)` helper that
strips its specific secret-bearing parameters before any string derived
from a URL, cookie header, or exception message reaches a log call or
is used as an exception message. Apply `redact()` defensively — any
path segment or response body fragment that could carry a credential
must pass through it first.
