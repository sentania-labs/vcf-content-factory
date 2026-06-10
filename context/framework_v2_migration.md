# Framework v2 Migration Cheat-Sheet

**Purpose:** mechanical guide for `sdk-adapter-author` to migrate
compliance, synology, and unifi adapters from framework v1 to v2.
After migration each adapter must compile cleanly against
`vcfcf-adapter-base.jar + vrops-adapters-sdk-2.2.jar` only — no
`aria-ops-core` on the classpath.

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

## 3. configureAdapter (replaces configure)

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
The method signature and body are identical. Remove the `@Override`
annotation if it no longer resolves (it will once the v2 JAR is on
the classpath).

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

## 4. getTester (new signature)

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

---

## 5. getDiscoverer (new signature)

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

## 6. getLiveDataCollector → getCollector (major rename + reshape)

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

## 7. getHistoricalDataCollector

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

## 8. getAutoDiscoveryEnabled

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

## 9. needRediscovery

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

## 10. Resource API (no more aria-ops-core Resource)

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

## 11. ForeignResourceResolver (Suite API stitching)

**v1:**
```java
ForeignResourceResolver resolver =
    new ForeignResourceResolver(suiteAPIClient, logger);
```

**v2:**
```java
// Wire in the Suite API client via the bridge interface.
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

If the adapter does not do cross-MP stitching, no change is needed.

---

## 12. Relationship emission (onCollect path)

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

## 13. Event emission (unchanged API, simplified path)

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

## 14. Logging (unchanged)

Use `logInfo()` / `logWarn()` / `logError()` on the adapter instance.
From within SPI implementations, the adapter is available as the
`adapter` parameter (cast to `VcfCfAdapter` to access log methods if
needed, or pass a logger reference to the SPI object's constructor).

---

## 15. Semantic changes adapter authors must know

| Topic | v1 behavior | v2 behavior |
|---|---|---|
| Per-resource status | Not required; set by UnlicensedAdapter wrapper | **Required every cycle** by the orchestrator. Set automatically on success (`DATA_RECEIVING`) or exception (via `mapCollectException`). |
| Test failure channel | `TestException.message` surfaced via wrapper | `param.setErrorMsg(e.getMessage())` called by orchestrator automatically when tester throws. |
| New resource registration | `getAutoDiscoveryEnabled()=true` gates processMetrics | `adapter.registerNewResource(key)` called from `collect()` or `rediscover()`. |
| Relationship max | `maximumRelationshipsPerCollection` field on UnlicensedAdapter | `VcfCfAdapter.MAX_RELATIONSHIPS_PER_CYCLE` constant (default 100 000); override `getMaxRelationshipsPerCycle()`. |
| MetricDataCache | Auto-created and auto-flushed by UnlicensedAdapter | Auto-created in `onConfigure` and auto-flushed at end of `onCollect`. Constructor params `(1000, 100)` are [INFER] — see spec/19 §8. |
| SSL | `insecureSslContext()` embedded in HttpClientBuilder (inline, always insecure) | JVM default trust store when no SSL configured; `platformSsl(this)` for platform trust; `allowInsecure(true)` for explicit lab opt-out. |
| SuiteAPIClient | Injected as field `suiteAPIClient` on UnlicensedAdapter | Not injected. Pass via `ForeignResourceResolver.SuiteApiBridge` when needed (optional, not required on collect path). |
| onDiscard | Call `super.onDiscard()` first | Same — call `super.onDiscard()` first. |

---

## 16. Compile verification after migration

The adapter must compile with:
```
javac -cp vcfcf-adapter-base.jar:vrops-adapters-sdk-2.2.jar[:<vendor jars>] ...
```

If `javac` reports a missing symbol:
- `com.vmware.tvs.*` → clean-room wall violation; report as TOOLSET GAP.
- `com.integrien.*` → symbol is in vrops-adapters-sdk-2.2.jar; add jar to CP.
- `com.vcfcf.*` → symbol is in vcfcf-adapter-base.jar; rebuild framework if needed.
