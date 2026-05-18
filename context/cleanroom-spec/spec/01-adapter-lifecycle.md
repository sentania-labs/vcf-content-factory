# 01 — Adapter Lifecycle Contract

**Status**: DRAFT (pass 1 evidence)
**SDK source**: `vrops-adapters-sdk-2.2.jar`
**Corroborating adapter**: mpb-adapter

## The contract: `AdapterInterface3`

Every native Java adapter implements (directly or via `AdapterBase`):

```
package com.integrien.alive.common.adapter3;

public interface AdapterInterface3 {
    AdapterStatus     configure(AdapterConfig param);
    AdapterDescribe   describe();
    DiscoveryResult   discover(DiscoveryParam param);
    CollectResult     collect();
    boolean           test(TestParam param);
    AdapterStatus     discard();
    boolean           changePassword(PasswordParam param);
    CheckCertificateResult checkCertificate(CheckCertificateParam param);
    default void      stopCollection();
}
```

Note the package: `com.integrien.alive.common.adapter3` (lineage from
the original Integrien Alive framework, retained for ABI stability).
**Adapters must compile against this fully-qualified type.**

### Method semantics (observed contract)

| Method | When platform invokes | Adapter MUST | Adapter MAY |
|---|---|---|---|
| `configure(AdapterConfig)` | At adapter-instance creation; on every config update | Process the new config; reflect any per-resource consequences | Reject invalid configs (return appropriate `AdapterStatus`) |
| `describe()` | At pak install + on adapter restart | Return the adapter's `AdapterDescribe` (the in-memory model parsed from describe.xml, possibly augmented) | Augment the static describe with dynamic content |
| `discover(DiscoveryParam)` | On user-triggered discovery, or auto-discovery | Return `DiscoveryResult` listing discovered resources + state transitions | Use the discovery param to scope the search |
| `collect()` | Every monitoring interval | Push collected metrics/properties/events/relationships via SDK helpers; return populated `CollectResult` | Implement `PartialCollectInterface` to stream data mid-collect |
| `test(TestParam)` | When user clicks "Test Connection" | Return true iff the configured connection works | Surface diagnostic info via `AdapterCollectionIssues` |
| `discard()` | On adapter-instance removal or shutdown | Release resources (close sockets, stop pools, etc.) | Set `discarded=true` (base class does this) |
| `changePassword(PasswordParam)` | On credential rotation | Update stored credentials; verify new credential works | Return false to reject the change |
| `checkCertificate(CheckCertificateParam)` | When platform encounters a new TLS cert | Return decision: accept / reject / prompt user | Implement `INonDisruptiveCertificate` to handle non-disruptively |
| `stopCollection()` | When platform requests graceful stop of in-flight collect | Best-effort early termination of `collect()` | Use a volatile flag pattern checked in collection loops |

## The base class strategy: `AdapterBase`

Adapters are not expected to implement `AdapterInterface3` directly.
Instead, extend `AdapterBase` (abstract, in the same package). It uses
the **template-method pattern**: the 9 interface methods are
finalized; subclasses override `on*()` hooks.

```
package com.integrien.alive.common.adapter3;

public abstract class AdapterBase implements AdapterInterface3 {

    // Required overrides
    public abstract void              onConfigure(ResourceStatus, ResourceConfig);
    public abstract AdapterDescribe   onDescribe();
    public abstract DiscoveryResult   onDiscover(DiscoveryParam);
    public abstract void              onCollect(ResourceConfig, Collection<ResourceConfig>);

    // Optional overrides (default impls in base)
    public          void    onConfigure(AdapterStatus, Collection<ResourceConfig>);
    public          void    onStopResources(AdapterStatus, Collection<ResourceConfig>);
    public          void    onRemoveResources(AdapterStatus, Collection<ResourceConfig>);
    public          boolean onChangePassword(PasswordParam);
    public          boolean onTest(TestParam);
    public          void    onStopCollection();
    public          void    onDiscard();
    public          CheckCertificateResult onCheckCertificate(CheckCertificateParam);

    // Finalized — do not override
    public final AdapterStatus            configure(AdapterConfig);
    public final AdapterDescribe          describe();
    public final DiscoveryResult          discover(DiscoveryParam);
    public final CollectResult            collect();
    public final boolean                  changePassword(PasswordParam);
    public final boolean                  test(TestParam);
    public final void                     stopCollection();
    public final AdapterStatus            discard();
    public final CheckCertificateResult   checkCertificate(CheckCertificateParam);

    // ... built-in capabilities — see § Helpers
}
```

### Minimum-viable Track C adapter

Implementing `AdapterBase` with these four required overrides
(`onConfigure`, `onDescribe`, `onDiscover`, `onCollect`) suffices to
ship a working adapter. The base class handles all other lifecycle
methods with reasonable defaults. Most production adapters also
override `onTest` (so the UI's "Test Connection" button does something
meaningful) and `onDiscard` (for resource cleanup).

**Observed in mpb-adapter**: 4 required + 2 optional overrides
(`onTest`, `onDiscard`) + 2 action methods (separate interface).
Everything else uses base defaults.

## Helpers AdapterBase provides

Subclasses get a substantial helper API. Categories:

### Pushing data into the CollectResult
```
boolean addMetricData(ResourceConfig, MetricData);
boolean addMetricData(ResourceConfig, List<MetricData>);
boolean addMetricData(ResourceConfig, List<MetricData>, boolean isProperty);
boolean addEvent(ResourceConfig, ExternalEvent);
boolean addEvents(ResourceConfig, Collection<ExternalEvent>);
```

### Setting resource state
```
boolean setResourceDown(ResourceConfig);
boolean setResourceDown(ResourceConfig, long timestamp);
boolean setResourceDown(ResourceConfig, long, String reason);
boolean setResourceDown(ResourceConfig, LocalizedMsg reason, long);
boolean setResourceDown(ResourceConfig, long, String reason, boolean isAutomatic);
boolean setResourceDown(ResourceConfig, long, boolean isAutomatic, LocalizedMsg);
boolean setAdapterDown(ResourceConfig adapterInst, LocalizedMsg reason, boolean isAutomatic);
boolean setResourceError(ResourceConfig, long, String reason);
boolean setResourceError(ResourceConfig, LocalizedMsg reason, long);
boolean setAdapterError(LocalizedMsg);
boolean setResourceStatus(ResourceConfig, CommonConstants.ResourceStatusEnum);
boolean setResourceStatus(ResourceConfig, CommonConstants.ResourceStatusEnum, String);
boolean setResourceStatus(ResourceConfig, LocalizedMsg, CommonConstants.ResourceStatusEnum);
void    changeResourceState(ResourceConfig, DiscoveryResult.StateChangeEnum);
void    changeResourceState(ResourceConfig, DiscoveryResult.StateChange);
```

### Querying configured resources
```
Collection<ResourceConfig> getAllMonitoringResources();
ResourceConfig             getMonitoringResource(ResourceConfig | ResourceKey | Integer);
ResourceConfig             getStoppedResource(ResourceConfig | ResourceKey | Integer);
boolean                    isNewResource(ResourceConfig | ResourceKey | Integer);
boolean                    isNewResourceKind(String key);
boolean                    isNewResourceKind(String key, String adapterKind);
```

### Asking the policy engine
```
boolean shouldCollect(ResourceConfig | ResourceKey | Integer, MetricKey);
boolean isMetricMonitoring(ResourceConfig | ResourceKey | Integer, MetricKey);
boolean isMetricStopped(ResourceConfig | ResourceKey | Integer, MetricKey);
boolean isAvailabilityMetric(MetricKey);
```

These let the adapter skip collection work for metrics the platform's
policy engine has currently disabled. Production adapters that do
expensive per-metric queries should consult `shouldCollect` first.

### TLS / connection
```
URLConnection      getConnection(String url, HostnameVerifier);   // throws NoSuchAlgorithmException, IOException, KeyManagementException
String             getConnectionURL(AdapterConfig);
List<String>       getConnectionURLs(AdapterConfig);
KeyManager[]       getKeyManagers();
HostnameVerifier   getVerifier();
CustomTrustManager getTrustManager();
TrustManager       getAdapterTrustManager();
KeyStore           getAdapterTrustStore();
Map<String, CertificateConfig> getCertificateMap();
CustomSSLSocketFactory getSocketFactory();
Set<String>        getCertificateRenewalUrls();
static String      getThumbprint(byte[]);
```

The platform manages the trust store; adapters should use these
helpers rather than constructing their own TLS contexts.

### Capability flags (override to declare)
```
boolean isDynamicMetricsAllowed();   // allow metrics not declared in describe.xml
boolean isResourceRenameAllowed();
boolean isResourceRenameAllowed(ResourceKey);
boolean isPartialDataReadyToSend(int);
protected boolean isAutoCalculateRatedMetrics();
```

### Adapter metadata
```
String  getAdapterName();
String  getAdapterFullName();
String  getAdapterKind();
AdapterConfig getAdapterConfig();
ResourceConfig getAdapterInstResource();
Integer       getAdapterInstResourceId();
Integer       getMonitoringInterval();
Integer       getMonitoringIntervalInSec();
AdapterLoggerFactory getAdapterLoggerFactory();
static Path  getAdaptersHome();
static Path  getAdapterDescribeFile(String adapterKind, String adapterName);
```

### Extension registry
```
public final void          registerInterface(Class<?>, Object);
        <T> T              queryInterface(Class<T>);
```

A runtime plug-in slot. Use case TBD — flag for cross-validation when
we see other adapters using it.

## Optional mix-in interfaces

Implement alongside `AdapterBase` for extra capabilities:

### `ActionableAdapterInterface` (see § 04)
Declares that the adapter supports user-invokable actions.
*Observed in mpb-adapter.*

### `PartialCollectInterface`
```
void processPartialData(AdapterBase, CollectResult);
```
Receive a callback while `collect()` is still running, letting the
platform process data before the full collect completes. Useful for
long collects (e.g., slow paginated APIs).

### `INonDisruptiveCertificate`
```
Collection<CertificateConfig> handleUnknownCertificate(
    UUID adapterInstanceId,
    InetSocketAddress endpoint,
    X509Certificate[] chain);
```
Handle TLS cert prompts non-disruptively (e.g., auto-trust by policy
instead of pausing the collect for user input).

### `LicensableSolution`
```
SolutionLicense decodeLicenseKey(String);
boolean         updateLicense(LicenseUpdateParam);
```
Declare that the adapter's solution is license-gated.

## Adapter packaging layout (deployed form, observed)

```
<adapter-kind>.jar                  # entry-point jar at the inner-archive root
    META-INF/MANIFEST.MF
    META-INF/maven/<groupId>/<artifactId>/pom.xml   # (when built with Maven)
    adapter.properties              # ← entry-point registration (see below)
    com/<package>/<EntryClass>.class
    ...
<adapter-kind>/
    conf/
        describe.xml                # adapter declaration
        describeSchema.xsd          # schema
        version.txt                 # build metadata
        resources/                  # localization
            resources*.properties
        images/                     # icons (AdapterKind, ResourceKind, TraversalSpec)
    lib/
        *.jar                       # vendor SDK + adapter-specific deps
```

The entry-point jar at the inner-archive root contains the adapter's
`AdapterInterface3`-implementing class. The `lib/` directory holds
dependencies the platform adds to the adapter's classloader.

### Adapter registration: `adapter.properties`

At the root of the entry-point jar:

```
ENTRYCLASS=<fully.qualified.AdapterClassName>
KINDKEY=<AdapterKind key matching describe.xml>
```

Two keys observed across mpb-adapter and vim:
- **`ENTRYCLASS`** — fully-qualified Java class name that implements
  `AdapterInterface3` (directly or via `AdapterBase`). The platform
  instantiates this class for each adapter instance.
- **`KINDKEY`** — adapter kind identifier. Must match
  `<AdapterKind key="...">` in `describe.xml`.

*Pak filename, inner-archive directory name, and entry-point class
name are all free-form and can differ from the KINDKEY.* For example,
the `vim` pak deploys under directory `vim/` but its KINDKEY is
`VMWARE_INFRA_MANAGEMENT` and its entry class is
`com.vmware.adapter.management.ManagementAdapter`.

Other `adapter.properties` keys may exist (TBD by future passes).

### SDK provisioning strategies

`vrops-adapters-sdk-*.jar` may or may not appear in the adapter's
`lib/`:

| Strategy | Observed in | Notes |
|---|---|---|
| Rely on platform classpath | mpb-adapter | The SDK at runtime is whatever the appliance provides |
| Bundle in `lib/` | vim (`vrops-adapters-sdk-1.0.jar`) | Adapter pins a specific SDK version; the Tomcat-style classloader prefers `lib/` over parent |

Both work. Bundling is appropriate when the adapter has been
compiled and tested against a specific SDK version and wants ABI
stability across platform upgrades. Relying on classpath is
appropriate when the adapter depends on minimal SDK surface that is
unlikely to break.

### Sub-shape variants

- **C1 (rich lib/, vendor-SDK-bundling)**: most production adapters.
  Adapter jar at root + 5–116 jars in lib/ including vendor SDKs.
  *Examples: vim (102 lib jars), most marketplace adapters.*
- **C1-light**: small lib/ (1–5 jars) for adapters with thin dep
  surface. *Example: mpb-adapter (2 lib jars).*
- **C2 (SDK-on-classpath)**: empty/absent lib/, adapter jar at root
  only. Relies entirely on the platform classpath. *Examples:
  SupervisorAdapter, mpforaggregator. Pattern observed for internal
  Broadcom adapters that target the appliance's bundled libraries.*

## Adapter abstraction frameworks (optional, recommended)

Production adapters frequently extend a higher-level abstraction class
rather than `AdapterBase` directly. Observed in this corpus:

### `com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter`
(in `aria-ops-core-*.jar` — BlueMedora-origin, now shipped by VMware TVS)

```
abstract class UnlicensedAdapter extends AdapterBase {
    // Implements AdapterBase's on*() hooks, dispatching to subclass-supplied SPIs

    // Subclass must supply (the framework's SPI):
    protected abstract String     getAdapterDirectory();
    public    abstract void       configure(ResourceStatus, ResourceConfig);
    public    abstract Tester     getTester(ResourceStatus, ResourceConfig);
    public    abstract Discoverer getDiscoverer(ResourceStatus, ResourceConfig);
    public    abstract LiveCollector       getLiveDataCollector(ResourceStatus, ResourceConfig);
    public    abstract HistoricalCollector getHistoricalDataCollector(ResourceStatus, ResourceConfig);
    public    abstract boolean    getAutoDiscoveryEnabled(ResourceStatus, ResourceConfig);

    // Framework-provided helpers:
    protected MetricDataCache     metricDataCache;
    protected SuiteAPIClient      suiteAPIClient;
    protected int                 maximumRelationshipsPerCollection;
    protected int                 maximumEventsPerCollection;
}
```

#### Role SPIs

```
interface Tester {
    void test(TestParam param) throws TestException;
}

interface Discoverer {
    ResourceCollection getResources(DiscoveryParam param) throws InterruptedException;
}

interface LiveCollector {
    ResourceCollection getCurrentMetrics(ResourceConfig rc, ResourceCollection acc)
                            throws CollectionException, InterruptedException;
    ResourceCollection getEvents(ResourceConfig rc, ResourceCollection acc)
                            throws CollectionException, InterruptedException;
    ResourceCollection getRelationships(ResourceConfig rc, ResourceCollection acc)
                            throws CollectionException, InterruptedException;
    boolean shouldForceUpdateRelationships();
}

interface HistoricalCollector {
    ResourceCollection getHistoricMetrics(
            ResourceConfig rc, ResourceCollection acc,
            long startTime, long endTime)
        throws CollectionException, InterruptedException;
}
```

This pattern decomposes a Track C adapter into clean roles:

1. **Tester** — validates credentials + connectivity
2. **Discoverer** — enumerates resources from the target system
3. **LiveCollector** — gathers current values; **three separate axes**: metrics, events, relationships
4. **HistoricalCollector** — backfills historic data

Recommendation for **VCF-CF Tier 2** (`vcfcf-adapter-base.jar`):
adopt this decomposition directly. The three-axis collection split is
particularly important — keeping metrics, events, and relationships as
separate methods produces cleaner adapter code and clearer error
boundaries than a single `onCollect()` that does everything.

The framework also provides:
- An aggregating `ResourceCollection` builder type
- Cached MetricDataCache + (optional) auto-injected SuiteAPIClient
- Throttle limits (`maximumRelationshipsPerCollection`,
  `maximumEventsPerCollection`)

## Capability declaration flags (override on AdapterBase)

Some adapter capabilities are declared via boolean overrides on
`AdapterBase` rather than describe.xml attributes. Override and
return `true` to opt-in:

| Method | Default | Effect when `true` |
|---|---|---|
| `isDynamicMetricsAllowed()` | `false` | Adapter may push metrics not declared in describe.xml |
| `isResourceRenameAllowed()` | `false` | Resource names may change without breaking identity |
| `isResourceRenameAllowed(ResourceKey)` | (delegates) | Per-resource override |
| `isAutoCalculateRatedMetrics()` *(protected)* | `?` | Rated-metric calculation policy |

*Observed in vim: `isResourceRenameAllowed(ResourceKey)` overridden.*
*Not observed elsewhere yet.*

## Open / pending — RESOLVED in Pass 21

- **CONFIRMED — Concurrency model of `collect()` is at-most-one** per
  adapter instance. `AdapterBase` has `protected final
  java.util.concurrent.Semaphore locker;` — the Semaphore serializes
  collect() invocations. The platform cannot invoke collect()
  concurrently against the same instance.
- **CONFIRMED — Per-instance Adapter object is REUSED** across
  collect() cycles. NSXTAdapter3 (Pass 5) demonstrates this with heavy
  per-instance state caching (relationship maps, last-collection
  timestamps). Same applies to all observed adapters.
- **CONFIRMED — `AdapterInterface3` has exactly 8 abstract methods +
  1 default method** (Pass 21):
  - `configure(AdapterConfig): AdapterStatus`
  - `describe(): AdapterDescribe`
  - `discover(DiscoveryParam): DiscoveryResult`
  - `collect(): CollectResult`
  - `changePassword(PasswordParam): boolean`
  - `test(TestParam): boolean`
  - `discard(): AdapterStatus`
  - `checkCertificate(CheckCertificateParam): CheckCertificateResult`
  - `default void stopCollection()` — backwards-compat default added later
- **Tomcat classloader precedence** — RESOLVED in spec/13:
  per-pak classloader isolation; `common-lib/` provides shared
  classpath; `aria-ops-core` is per-pak-bundled (NOT shared).

## Pass 23 confirmations (2026-05-16, field evidence)

Confirmed against live `vcf-lab-operations-devel` appliance via
Navani's DEBUG-level collector log capture; full bundle at
`workspaces/lab-admin/exports/vcf-mp-cleanroom-2026-05-16/`.

### Semaphore scope: **per-instance**

The `Semaphore locker` field on `AdapterBase` (confirmed by bytecode
in Pass 21) is scoped to the **individual adapter instance**, NOT to
the adapter kind and NOT globally. Empirical evidence from the 10-min
DEBUG collector log slice:

- Adapter 121 (vcf-lab-wld01 vCenter) and adapter 63 (vcf-lab-mgmt
  vCenter) — same kind=`VMwareAdapter`, different instances — ran
  in parallel on different worker threads (440 and 96), overlapping
  for ~7 seconds. **Rules out per-kind scope.**
- Adapter 24 and adapter 58 (different adapter kinds) overlap freely.
  **Rules out global scope.**
- Adapter 24's three cycles in the slice (15:20:35, 15:21:35,
  15:22:35) are strictly sequential despite each picking a fresh
  worker thread (418 → 186 → 420 — no thread affinity).
  **Confirms per-instance Semaphore(1) keyed on instance ID.**

Within a single instance's cycle, all DEBUG lines for that adapter
ID appear on the same thread — so **per-instance, single-threaded
per cycle** describes both the lock scope and the intra-cycle
threading model.

### Platform retry on collect() failure: **none**

The platform does NOT retry the `onCollect()` cycle on failure.
Observed: a real HTTP 500 from `WCPManager.getNamespaceV2Metrics` and
a `NullPointerException` in `ContainerMetricsCollector.run` were
logged at ERROR within a single cycle; the cycle still ended
"successfully" (logged `Collected resources count - 66`) and the
platform proceeded to the next scheduled cycle without re-invoking
the failed cycle.

Retry behavior exists one layer *down* in vendor SDK callers — e.g.
`QueryStatsCaller` wraps vCenter API calls with an "attempt N"
counter — but at the `collect()` boundary, errors are
**swallow-and-log** and the next scheduled cycle continues normally.

**Implication for adapter authors**: do not rely on the platform to
retry. If a collect cycle must be retried, the adapter implements
its own retry loop inside `onCollect()`. The platform's contract is
"fire on schedule, log what you get."

### Instance cadence is independent per-instance

Different adapter instances tick on their own configured cadences
(observed in slice: adapter 24 every 60s, vCenter adapters every
5min, MPB-runtime adapters varying). Cycles for different instances
freely overlap — concurrency is bounded only by the per-instance
Semaphore above. There is no global collect-time slot or thread-pool
limit visible at the AdapterBase layer.

## Install-time lifecycle: cross-reference

Adapter classes are loaded and `describe.xml` is parsed at **pak
install time**, during the `apply_adapter` phase of the platform's
CASA-orchestrated install pipeline — not at adapter-instance
`configure()` time. See [§16 — Platform Install Pipeline +
Signature Validation](16-platform-install-and-signing.md) for the
full 7-phase pipeline, the per-phase Python subprocess invocations,
and the empirical signature-validation behavior. Open question
"WHEN does the platform read describe.xml" is answered there.

## Still open

- **Full `adapter.properties` schema** — beyond `ENTRYCLASS` and
  `KINDKEY`. Pass 7 found `relationship_sync_interval`,
  `max_relationships_per_collection`, `max_events_per_collection` in
  MPB-generated adapter.properties. Full key catalogue TBD.
