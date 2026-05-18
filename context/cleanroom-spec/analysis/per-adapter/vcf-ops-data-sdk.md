# `vcf-ops-data-sdk` — characterization (Pass 9)

**Date**: 2026-05-16
**Source**: `analysis/decompiled/vmwarevi_adapter3/vmwarevi_adapter3/lib/vcf-ops-data-sdk-1.0-SNAPSHOT.jar` (40MB, 35,422 files, but ~45 classes in the actual API; rest is shaded deps including `com.sun.xml`, `com.rsa.names`, vAPI types).
**Release timestamp**: 2022-04-18 — **~4 years stale at 1.0-SNAPSHOT**.
**Distribution**: shipped ONLY in `vmwarevi_adapter3` (vSphere) among the corpus's 39 KEEP-C paks. No other production adapter ships it.

## TL;DR

**This SDK is a narrow specialty layer**, not the modern successor to the legacy `vrops-adapters-sdk.jar`. It's specifically a **Reactive-Streams subscriber for vCenter PerformanceManager stats streams**, with a multi-destination routing capability. Despite the broad "ops/data" naming, the package layout, the dependencies, and the single concrete client (`VcSdkClient`) all point to vCenter-source-specific scope.

**Implication for VCF-CF**: keep the Tier 2 abstraction (`vcfcf-adapter-base.jar`) on the LEGACY SDK (aria-ops-core pattern, Pass 3). Don't bet the architecture on `vcf-ops-data-sdk`. But preserve a stream-collection hook in the abstraction so a future stream-based source can plug in cleanly.

## Architectural pattern

```
adapter.collect() entry  (legacy SDK contract)
        │
        ▼
client.startCollection(specName, samplingInterval)
        │
        ▼  reads QuerySpec from <classpath>/<specsDir>/<specName>.json
        │  (declarative — adapters carry pre-written QuerySpecs as resources)
        │
        ▼
QuerySpecManager.convertToCreateSpec()   ──→  StatsRegQuerySpec  (lower-level)
        │
        ▼
QuerySpecManager.createQuery()           ──→  POST to vCenter stats-provider:
        │                                     "create a query view, get a queryId"
        │
        ▼
QueryResult(query, clientId, samplingInterval, aggregatesPerCounter, routes)
        │
        ▼
StreamManager.createStream(queryResult)  ──→  POST to vCenter:
        │                                     "create a Kafka-like stream for this query"
        │
        ▼
StreamManager.attachStream() : Publisher<Result>   ──→  GET (long-poll / streaming)
        │
        ▼ Reactive Streams pipeline
        │
StatsSubscriber implements org.reactivestreams.Subscriber<Result>
        │  onSubscribe / onNext(Result) / onError / onComplete
        │
        ▼
MetricDataStoreManager.storeNonAggregatedData(Result, QueryResult)
   or   .storeAggregatedData(Result, aggregatesPerCounter, QueryResult)
        │
        ▼
   LinkedBlockingQueue per spec name  (in-memory ring buffer)
   + optional persist to DBStore (when routes.database=true)
        │
        ▼ adapter polls back
        │
client.getStatsData() : Map<String, List<StatsData>>
client.getAggregatedStatsData()
client.collectFailureDetails() : List<FailedStream>
        │
        ▼ adapter walks results, builds legacy MetricData, calls addMetricData(ResourceKey, ...)
        │
        ▼ legacy SDK egress
        ▼
   Operations platform (the normal data path)
```

The SDK is a **subscribe-and-buffer middleware**. The adapter still pushes through the legacy SDK at the end of each collection cycle — `vcf-ops-data-sdk` is in the middle of the pipeline, not at either end.

## The 9 API sub-packages

| Sub-package | Classes | Purpose |
|---|---|---|
| `(root)` | `SdkClient` (abstract), `VcSdkClient` (only concrete) | Client entry point — extension surface for non-vc sources is reserved but not exercised |
| `config` | `ClientConfig` | 7 fields: samplingInterval, aggregationEnabled, retry policy, telemetry flags. Builder-pattern. |
| `specs` | `QuerySpec`, `QuerySpecInstance`, `StatsRegQuerySpec`, `QueryResult`, `Routes`, `AggregateFunc`, `CounterInstance`, `ResourceId`, `QuerySpecManager`, `QuerySpecLoader` | Declarative collection specification |
| `model` | `StatsData`, `ResourceIds`, `ResourceId`, `Value`, `FailedStream` | Data carrier types (parallel to legacy `MetricData` / `ResourceKey`) |
| `metrics` | `MetricDataStoreManager`, `MetricDataStore`, `DBStore`, `TransformerType`, `converter/StatsRegResultUtil`, `converter/StatsRegResultToResult` | Storage layer + result transformation |
| `stream` | `StreamManager`, `SubscriberThreadManager`, `SubscriberThread` | Reactive Streams subscription lifecycle |
| `subscriber` | `StatsSubscriber` (impl `org.reactivestreams.Subscriber<Result>`) | The consumer that drives data into the store |
| `observer` | `StreamConnectionObserver`, `StreamConnectionPublisher` | Stream-health observation (heartbeat / failure callbacks) |
| `common` | `Constants`, `auth/BindingsManager`, `auth/AuthHelper`, `model/SdkResource`, `util/Utility`, `util/CustomThreadFactory`, `collect/CollectionOrchestrator`, `collect/StatsDataKey` | Shared infrastructure |
| `vc` | `vc/auth/{VcBindingsManager, HttpConfigurationFactory, SamlTokenUtils, VcAuthentication, TOFUThumbprintVerifier}`, `vc/model/VcResource`, `vc/lookupservice/VcLookupService`, `vc/collect/VcCollector`, `vc/metrics/converter/VcStatsRegResultToResult` | vCenter-specific implementations of the abstract surface |

## Key types

### `SdkClient` (abstract base — extension point)

```java
public abstract class SdkClient {
    protected final ClientConfig config;
    protected final VcResource vcResource;             // ← VC-specific even in the BASE class
    protected VcBindingsManager vcBindingsManager;     // ← VC-specific
    // ...
    public Map<String, List<StatsData>> getStatsData();
    public Map<String, List<StatsData>> getAggregatedStatsData();
    public List<FailedStream> collectFailureDetails();
    abstract List<CollectionOrchestrator> getOrchestrators();
}
```

**Critical observation**: even the "abstract" `SdkClient` carries `VcResource` and `VcBindingsManager` fields. The abstraction is **vCenter-shaped from the start**. A future non-vc subscriber would need to either misuse these fields or refactor the base class. The package layout suggests intent for extension; the actual class shape does not.

### `ClientConfig` — knobs

7 fields, builder pattern:

```java
ClientConfig.builder()
    .samplingIntervalInSecs(20)        // how often the stream emits
    .aggregationEnabled(true)
    .retryLimit(3)
    .retryIntervalInMs(60000)
    .enableTelemetry(false)
    .enableTelemetryLogging(false)
    .telemetryLogInterval(0)
    .build();
```

No per-source overrides; one ClientConfig per `SdkClient`.

### `QuerySpec` — declarative collection

```java
class QuerySpec {
    Long samplingIntervalInSecs;
    List<QuerySpecInstance> specs;     // counters to collect
    Routes routes;                     // where to deliver
}

class Routes {
    boolean ops;        // route to legacy SDK → Operations platform
    boolean database;   // persist to local DB
    boolean kafka;      // publish to Kafka topic
}
```

**`Routes` is the multi-destination fan-out capability**. A single subscription can deliver collected stats to any combination of: the Operations platform (default), a local persistent store, and a Kafka topic for downstream analytics. The Kafka destination implies VCF Operations has a stream-analytics backplane that this SDK feeds.

### `AggregateFunc` enum — server-side aggregation

```java
enum AggregateFunc { SUM, AVG, MAX, MIN }
```

The query spec declares `aggregatesPerCounter: Map<String, Set<AggregateFunc>>`. The vCenter stats provider performs the aggregation server-side over each sampling bucket; the SDK receives already-rolled values. **`Value` carries `value, min, max, count, sum, avg, opaque`** — supporting all 4 functions per counter in one payload.

### `Value` — richer than legacy MetricData

```java
class Value {
    Double value;                         // primary numeric
    DataValue opaque;                     // for non-numeric (vAPI DataValue)
    Double max, min, sum, avg;            // pre-aggregated stats
    Long count;
}
```

vs. legacy `MetricData` which is a single (timestamp, double) pair. The modern model is **statistical-summary-per-bucket** rather than raw-sample-per-tick. Reduces wire volume by 10-100× while preserving distribution info.

### `ResourceIds` / `ResourceId` — new identity shape

```java
class ResourceIds { List<ResourceId> resourceIds; }
class ResourceId  { String key, value; }
```

vs. legacy `ResourceKey(adapterKind, resourceKind, identifiers)`. The modern shape is a flat list of (name, value) pairs — **adapterKind/resourceKind are NOT in this model**. Likely the SDK relies on the QuerySpec to scope what kinds of resources are being collected; identity within the result-stream is just the identifier tuple. This is a **lossy** shape if you cross-stream (no kind discrimination); fine within a single query.

### `StatsSubscriber` — Reactive Streams consumer

```java
class StatsSubscriber implements org.reactivestreams.Subscriber<Result>,
                                  StreamConnectionPublisher {
    void onSubscribe(Subscription);
    void onNext(Result);          // <- per-batch data arrives here
    void onError(Throwable);
    void onComplete();
    void cancel();
    void addObserver(StreamConnectionObserver);
    void notifyObservers(Throwable, QueryResult);
}
```

Standard Reactive Streams Subscriber. The `Result` type comes from `com.vmware.stats.provider.Result` — **third-party vAPI type, not under the SDK's control**. The SDK is downstream of the vCenter stats-provider data model.

### `CollectionOrchestrator` (abstract) + `VcCollector` (concrete)

`CollectionOrchestrator` defines the workflow: `createQueryStep → createStreamStep → executeWorkflow`. Failed-stream tracking (`retryFailedStreams()`, `cleanMaxRetryFailedStreams()`), token renewal (`renewToken(int)`), stream-buffer sizing (`getStreamBufferSize()`).

`VcCollector` is the only concrete orchestrator — wires VC auth/lookup/HTTP. The auth path uses `VcAuthentication` + `SamlTokenUtils` + `TOFUThumbprintVerifier` — i.e., **vCenter SSO SAML token authentication with trust-on-first-use thumbprint verification**.

### `MetricDataStoreManager` — buffer

In-memory `LinkedBlockingQueue` per spec name + optional DB persistence. Two-tier; drained when the adapter calls `getStatsData()`.

## What this SDK is NOT

1. **Not a replacement for the legacy SDK.** The legacy `vrops-adapters-sdk.jar` is still the egress: collected stats end up in `addMetricData()` calls. This SDK is a middleware layer.
2. **Not a general-purpose data SDK.** Despite the `com.broadcom.ops.data.*` package name, it's a vCenter-stats-stream subscriber. Other data sources require building from scratch.
3. **Not actively maintained.** 1.0-SNAPSHOT version frozen since April 2022. No 1.1, no GA release in 4 years. Either stable enough not to need changes, or quietly stalled.
4. **Not widely adopted internally.** Among 39 KEEP-C paks (Broadcom-internal + marketplace), only vSphere ships it. NSXTAdapter3, vim, mongodb, VCFAutomation, AppOSUCPAdapter3 — none ship it. If it were the future, you'd expect at least a few siblings to have migrated by now.

## What this SDK signals about platform direction

Despite the SDK's own narrow scope, the architectural patterns visible in it are clearly where the platform's **internal** data infrastructure is heading:

1. **Reactive Streams as the in-process data-flow primitive.** Backpressure-aware, async, observable. The Operations platform internally is likely a Reactive Streams (or Project Reactor) shop.
2. **Multi-destination routing (`Routes`).** Operations, database, Kafka. The platform has a Kafka backplane for stats — VCF-CF should know about it.
3. **Pre-aggregated values (`Value` with min/max/avg/sum/count).** Reflects what the source-of-truth metric pipeline emits. Adapters that produce raw samples are leaving info on the table.
4. **Declarative collection specs (`QuerySpec`).** Loaded from classpath JSON resources — the spec is part of the deliverable, not hardcoded. This is a healthy pattern even within the legacy SDK abstraction.

## VCF-CF recommendations

### Keep the abstraction on the legacy SDK

For `vcfcf-adapter-base.jar`, build atop the legacy `vrops-adapters-sdk-2.2.jar`. Use the aria-ops-core decomposition (Tester / Discoverer / LiveCollector / HistoricalCollector — Pass 3 finding). This is the universal contract.

### Leave a stream-subscription hook

Allow `LiveCollector.getCurrentMetrics()` to be implemented as a **drain-from-subscription** rather than only a pull. Concretely: the abstraction should accept either:

- A polling implementation (call source, collect, return) — the common case
- A subscription implementation (subscription is set up at `configure()` time, `getCurrentMetrics()` drains a buffer)

This preserves the architectural escape hatch without committing to `vcf-ops-data-sdk` specifically. Any future stream-based adapter (whether using `vcf-ops-data-sdk` or a different library) plugs in cleanly.

### Don't bundle `vcf-ops-data-sdk` in `vcfcf-adapter-base.jar`

It's not on the appliance's runtime classpath universally — only the vSphere pak's `lib/` ships it. Bundling it in a shared base jar would (a) bloat every generated adapter by 40MB, and (b) require the appliance to load it for non-VC adapters that have no use for it. If a generated adapter actually needs it, treat it as a per-adapter optional dep that gets bundled only when the target source is vCenter stats.

### Document the patterns for users authoring custom Tier 2 adapters

Even though VCF-CF generates the adapter, the user authoring the **spec for** the adapter benefits from understanding:

- Pre-aggregated values reduce data volume and improve fidelity (provide hooks to declare aggregation per-counter)
- Declarative collection specs are a deliverable artifact (consider letting users supply a QuerySpec JSON for vCenter sources)
- Multi-destination routing (Kafka, DB) is a future capability — users should know it exists

### Re-evaluate in 6-12 months

If a `vcf-ops-data-sdk-2.x.jar` ships and starts appearing in non-vSphere paks, the calculus changes. Until then, treat as niche.

## Open questions

1. **Where do non-VC Broadcom-internal teams get stream-based collection?** Either they don't have it, or they have their own SDK that didn't ship in the corpus. Worth asking lab-admin (Navani) if there's a non-vc sibling jar in the devel appliance.
2. **What's the Kafka topic schema for the `routes.kafka=true` destination?** If VCF-CF wants to consume stats downstream (e.g., feed a separate analytics pipeline), knowing the topic + schema would matter.
3. **Is the `QuerySpec` JSON format documented anywhere?** Adapters loaded specs from `<classpath>/specsDir/*.json` — the JSON shape (counter names, instance lists, aggregation declarations) is the user-facing authoring surface. Pull a sample spec next pass.
4. **Token renewal cadence?** `renewToken(int)` exists; what triggers it? SAML token expiry is normally 8-24 hours; the adapter must refresh proactively.
