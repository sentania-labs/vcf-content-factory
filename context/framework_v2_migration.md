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

## 15. Logging (unchanged)

Use `logInfo()` / `logWarn()` / `logError()` on the adapter instance.
From within SPI implementations, the adapter is available as the
`adapter` parameter (cast to `VcfCfAdapter` to access log methods if
needed, or pass a logger reference to the SPI object's constructor).

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
