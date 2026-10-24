package com.vcfcf.adapter;

import com.vcfcf.adapter.http.ManagedHttpClient;
import com.vcfcf.adapter.spi.ResourceSink;
import com.vcfcf.adapter.spi.VcfCfCollector;
import com.vcfcf.adapter.spi.VcfCfDiscoverer;
import com.vcfcf.adapter.spi.VcfCfTester;

import com.integrien.alive.common.adapter3.AdapterBase;
import com.integrien.alive.common.adapter3.AdapterStatus;
import com.integrien.alive.common.adapter3.describe.AdapterDescribe;
import com.integrien.alive.common.adapter3.DiscoveryParam;
import com.integrien.alive.common.adapter3.DiscoveryResult;
import com.integrien.alive.common.adapter3.MetricData;
import com.integrien.alive.common.adapter3.MetricDataCache;
import com.integrien.alive.common.adapter3.MetricKey;
import com.integrien.alive.common.adapter3.Relationships;
import com.integrien.alive.common.adapter3.ResourceKey;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.TestParam;
import com.integrien.alive.common.adapter3.CustomTrustManager;
import com.integrien.alive.common.adapter3.config.AdapterConfig;
import com.integrien.alive.common.adapter3.config.CredentialConfig;
import com.integrien.alive.common.adapter3.config.CredentialFieldConfig;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;
import com.integrien.alive.common.util.CommonConstants.ResourceStatusEnum;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * v2 — Abstract base class for all VCF Content Factory Tier 2 SDK adapters.
 *
 * <p><strong>Layer 1 only.</strong> Extends {@link AdapterBase} directly;
 * {@code aria-ops-core} ({@code com.vmware.tvs.*}) is not required at compile
 * time or runtime.
 *
 * <h3>What v2 provides (spec/19 §1–10)</h3>
 * <ul>
 *   <li>Full {@code onConfigure / onDescribe / onTest / onDiscover / onCollect}
 *       orchestration backed by clean-room VCF-CF SPI interfaces
 *       ({@link VcfCfTester}, {@link VcfCfDiscoverer}, {@link VcfCfCollector}).</li>
 *   <li>Per-resource collection status every cycle via the
 *       {@link ResourceStatusEnum#isAdapterAllowedStatus} gate (§1).</li>
 *   <li>New-resource registration through
 *       {@link #registerNewResource(ResourceKey)} during collect (§2).</li>
 *   <li>Relationship emission via {@link #addRelationshipsToCurrentCycle(Relationships)}
 *       — attaches to the base's protected {@code collectResult} field (§3).</li>
 *   <li>Event helpers from {@link AdapterBase#addEvent} (§4).</li>
 *   <li>Test-failure channel via {@code TestParam.setErrorMsg /
 *       setLocalizedMsg} (§5).</li>
 *   <li>Metric/property dedup via {@link MetricDataCache} (§8).
 *       [INFER] ctor params isolated in {@link #createMetricCache()}.</li>
 *   <li>Cooperative cancellation: {@code volatile} abort flag set by
 *       {@link #onStopCollection()}; {@link InterruptedException} restores
 *       the interrupt flag and aborts the cycle (§9).</li>
 *   <li>SSL via {@link AdapterBase#getSocketFactory()} — no insecure
 *       trust-all by default; explicit opt-out via
 *       {@link #insecureSslContext()} when needed in labs (cert item).</li>
 *   <li>No mutable static state. No {@code System.setProperty}. No
 *       {@code SuiteAPIClient} on the collect path (§10).</li>
 * </ul>
 *
 * <h3>Adapter authors implement</h3>
 * <ol>
 *   <li>{@link #configureAdapter(ResourceStatus, ResourceConfig)} — read config,
 *       populate {@link #config}, build {@link #httpClient}.</li>
 *   <li>{@link #onDescribe()} — provided by the framework (loads
 *       {@code describe.xml} from the filesystem path derived from the
 *       adapter kind key stored at construction time). Override only if
 *       custom describe handling is needed.</li>
 *   <li>{@link #getTester()} — return a {@link VcfCfTester} (nullable).</li>
 *   <li>{@link #getDiscoverer()} — return a {@link VcfCfDiscoverer}.</li>
 *   <li>{@link #getCollector()} — return a {@link VcfCfCollector}.</li>
 * </ol>
 *
 * <h3>Constructor contract (adapter authors must follow)</h3>
 * <p>Adapter subclasses MUST supply the adapter kind key to the framework
 * at construction time by calling the two-argument and three-argument
 * super-constructors:
 * <pre>{@code
 * private static final String ADAPTER_KIND = "my_adapter_kind";
 *
 * public MyAdapter() {
 *     super(ADAPTER_KIND);          // kind stored; used by onDescribe()
 * }
 * public MyAdapter(String adapterDir, Integer instanceId) {
 *     super(ADAPTER_KIND, adapterDir, instanceId);
 * }
 * }</pre>
 * The kind key must exactly match the {@code key} attribute on the
 * {@code <AdapterKind>} element in {@code describe.xml} and the filename
 * component in the pak layout ({@code <adaptersHome>/<key>/conf/describe.xml}).
 * <strong>Do not derive the key from any {@code CommonConstants} field</strong>
 * — those are display-name strings, not filesystem tokens. See
 * {@code knowledge/lessons/sdk-constants-are-display-names.md}.
 *
 * <p>The no-arg constructor inherited from the platform interface is still
 * supported for binary compatibility with any bare-reflection caller, but
 * it stores a {@code null} kind key and will fail in {@code onDescribe()} with
 * an actionable message listing what was tried. Prefer the keyed constructors.
 *
 * <h3>MetricDataCache constructor params — [INFER] note</h3>
 * {@code MetricDataCache(owner, p1, p2)}: the two {@code int} parameters are
 * not documented in the SDK. Inferred as (cache-size-hint, dedup-window) based
 * on the aria-ops-core wrapper's {@code maxEvents}/window pattern. Conservative
 * values ({@code 1000, 100}) are used. <strong>Isolated in
 * {@link #createMetricCache()} — amend there if empirical evidence updates
 * this inference.</strong>
 *
 * <h3>Relationship cap — [API/INFER]</h3>
 * {@link #MAX_RELATIONSHIPS_PER_CYCLE} is the per-cycle relationship cap
 * (100 000 by default, matching a conservative multiplier on the per-instance
 * platform knob). Override {@link #getMaxRelationshipsPerCycle()} to reduce it.
 *
 * @param <C> the typed configuration POJO for this adapter
 */
public abstract class VcfCfAdapter<C> extends AdapterBase {

    /**
     * Default per-cycle relationship cap.
     *
     * <p>The adapter.properties key {@code max_relationships_per_collection}
     * (spec/01 "Still open") controls the platform-side limit. This constant
     * is the adapter-side guard applied before calling
     * {@link #addRelationshipsToCurrentCycle(Relationships)}. Override
     * {@link #getMaxRelationshipsPerCycle()} to reduce it.
     */
    public static final int MAX_RELATIONSHIPS_PER_CYCLE = 100_000;

    // -----------------------------------------------------------------------
    // Adapter kind key — stored at construction time for controller-side use
    // -----------------------------------------------------------------------

    /**
     * The adapter kind key provided by the subclass at construction time.
     *
     * <p>This is the authoritative source for the kind used in
     * {@link #onDescribe()}, and is set before any platform injection
     * occurs. It must exactly match the {@code key} attribute on the
     * {@code <AdapterKind>} element in {@code describe.xml}.
     *
     * <p>Null when the no-arg or two-arg constructor is used without a kind key
     * (legacy path, kept for binary compatibility). In that case
     * {@code onDescribe()} falls back to {@link AdapterBase#getAdapterKind()}
     * and fails with an actionable message if that is also null.
     */
    private final String adapterKindKey;

    // -----------------------------------------------------------------------
    // Instance state (per-instance, set in onConfigure → configureAdapter)
    // -----------------------------------------------------------------------

    /**
     * Typed configuration POJO, populated by
     * {@link #configureAdapter(ResourceStatus, ResourceConfig)}.
     * {@code volatile} — safe to read from collect threads without explicit sync.
     */
    protected volatile C config;

    /**
     * Optional HTTP client. Build in {@link #configureAdapter}; may be
     * {@code null} for non-HTTP adapters. Released in {@link #onDiscard()}.
     * {@code volatile} — same thread visibility guarantee as {@link #config}.
     */
    protected volatile ManagedHttpClient httpClient;

    /**
     * Metric dedup cache — created once per configure, reused across collect
     * cycles. Keyed by {@code (ResourceConfig, MetricKey)}. Suppresses
     * unchanged values (esp. properties) so only new/changed data enters the
     * {@code CollectResult}. (§8)
     */
    private volatile MetricDataCache metricCache;

    /**
     * Cooperative abort flag. Set to {@code true} by
     * {@link #onStopCollection()}; checked in collection loops. (§9)
     */
    private final AtomicBoolean abortRequested = new AtomicBoolean(false);

    /**
     * Guards the Suite API transport mode line in
     * {@link #openPlatformConnection(String)} so it logs once per adapter
     * instance rather than once per Suite API request (token acquire, each
     * datastore page, each stitch write). Same instance-scoped once-flag
     * shape as {@link #abortRequested}.
     */
    private final AtomicBoolean transportModeLogged = new AtomicBoolean(false);

    /**
     * Guards the FIPS cluster-truststore failure WARN in
     * {@link #openPlatformConnection(String)}: logged once per adapter
     * instance, while every affected call still fails (issue #215).
     */
    private final AtomicBoolean fipsTruststoreFailureWarnLogged = new AtomicBoolean(false);

    /**
     * Guards the framework version line in {@link #onConfigure}: logged once
     * per adapter instance (issue #214).
     */
    private final AtomicBoolean frameworkVersionLogged = new AtomicBoolean(false);

    /**
     * FIPS-mode Suite API socket factory, cached per adapter instance and
     * rebuilt when its input files change (issue #215 review W1).
     */
    private final ClusterSocketFactoryCache clusterSocketFactoryCache =
            new ClusterSocketFactoryCache();

    /**
     * Adapter-instance-scoped logger obtained lazily from the platform's
     * {@code AdapterLoggerFactory}. Named after the concrete class; raised
     * to INFO when created below INFO (a DEBUG level set by the operator is
     * kept; issue #224).
     */
    private volatile com.integrien.alive.common.adapter3.Logger adapterLogger;

    // -----------------------------------------------------------------------
    // Constructors
    // -----------------------------------------------------------------------

    /**
     * No-arg constructor (legacy / binary-compatibility path).
     *
     * <p>The platform calls {@code Class.newInstance()} (no-arg reflection)
     * during {@code describe()} generation. Without this constructor the engine
     * throws {@code InstantiationException} and the adapter kind is not registered.
     *
     * <p><strong>Prefer {@link #VcfCfAdapter(String)} from subclass no-arg
     * constructors.</strong> When this constructor is used, {@code onDescribe()}
     * has no statically-stored kind key and will fail with an actionable message
     * if {@link AdapterBase#getAdapterKind()} also returns null (which it does
     * during controller-side bare instantiation).
     */
    public VcfCfAdapter() {
        super();
        this.adapterKindKey = null;
    }

    /**
     * Kind-keyed no-arg constructor for the controller-side describe path.
     *
     * <p><strong>Subclass no-arg constructors MUST call this</strong> so the
     * framework can resolve {@code describe.xml} during controller-side bare
     * instantiation (where the platform has NOT yet injected config and
     * {@link AdapterBase#getAdapterKind()} returns null).
     *
     * <pre>{@code
     * private static final String ADAPTER_KIND = "my_adapter_kind";
     *
     * public MyAdapter() { super(ADAPTER_KIND); }
     * }</pre>
     *
     * @param adapterKindKey the adapter kind key, matching the {@code key}
     *        attribute on {@code <AdapterKind>} in {@code describe.xml} and the
     *        pak filesystem directory name. Must not be null or empty.
     */
    protected VcfCfAdapter(String adapterKindKey) {
        super();
        this.adapterKindKey = adapterKindKey;
    }

    /**
     * Two-arg constructor (legacy / binary-compatibility path for live collection).
     *
     * <p>The collector process instantiates adapter classes via
     * {@code Constructor(String, Integer)}. Without this constructor the adapter
     * instance fails to start with {@code NoSuchMethodException}.
     *
     * <p><strong>Prefer {@link #VcfCfAdapter(String, String, Integer)} from
     * subclass two-arg constructors</strong> so the kind key is always stored.
     *
     * @param adapterDir        the adapter directory path supplied by the platform
     * @param adapterInstanceId the adapter instance ID supplied by the platform
     */
    public VcfCfAdapter(String adapterDir, Integer adapterInstanceId) {
        super(adapterDir, adapterInstanceId);
        this.adapterKindKey = null;
    }

    /**
     * Kind-keyed three-arg constructor for live-collection instantiation.
     *
     * <p><strong>Subclass two-arg constructors MUST call this</strong> so the
     * kind key is available throughout the adapter lifecycle.
     *
     * <pre>{@code
     * public MyAdapter(String adapterDir, Integer instanceId) {
     *     super(ADAPTER_KIND, adapterDir, instanceId);
     * }
     * }</pre>
     *
     * @param adapterKindKey    the adapter kind key — same value as passed to
     *        {@link #VcfCfAdapter(String)}
     * @param adapterDir        the adapter directory path supplied by the platform
     * @param adapterInstanceId the adapter instance ID supplied by the platform
     */
    protected VcfCfAdapter(String adapterKindKey, String adapterDir,
            Integer adapterInstanceId) {
        super(adapterDir, adapterInstanceId);
        this.adapterKindKey = adapterKindKey;
    }

    // -----------------------------------------------------------------------
    // Abstract hooks adapter authors must implement
    // -----------------------------------------------------------------------

    /**
     * Read platform config, populate {@link #config} and (optionally)
     * {@link #httpClient}.
     *
     * <p>Replaces v1's {@code configure(ResourceStatus, ResourceConfig)} (the TVS
     * hook name). Called by the platform at instance creation and on every config
     * update, before the first {@code onCollect()}.
     *
     * <p>On hard-invalid config (missing required credentials, malformed endpoint),
     * mark the adapter as failed by calling
     * {@code resourceStatus.setStatus(ResourceStatusEnum.RESOURCE_STATUS_ERROR)}
     * and setting an error message. The base will return {@code as_failed} to the
     * platform if the status reflects failure.
     *
     * @param resourceStatus the per-resource status object for reporting failures
     * @param resourceConfig the adapter instance resource configuration
     */
    protected abstract void configureAdapter(ResourceStatus resourceStatus,
            ResourceConfig resourceConfig);

    /**
     * Return the {@link VcfCfTester} for this adapter.
     *
     * <p>Called during {@link #onTest(TestParam)}. Return {@code null} to skip
     * the connectivity check — the platform will show "Test succeeded" without
     * actually verifying anything. Not recommended for production adapters.
     */
    @SuppressWarnings("rawtypes")
    protected abstract VcfCfTester getTester();

    /**
     * Return the {@link VcfCfDiscoverer} for this adapter.
     *
     * <p>Called during {@link #onDiscover(DiscoveryParam)}.
     *
     * <p><strong>Default implementation (collect-path discovery opt-in):</strong>
     * When the adapter overrides {@link #enumerateResources(ResourceSink)} and
     * opts into collect-path discovery via {@link #discoverOnCollect()}, the
     * framework provides a default discoverer that calls
     * {@code enumerateResources(dr::addResource)} — so the adapter need not
     * override {@code getDiscoverer()} separately.
     *
     * <p>Adapters that have their own {@code getDiscoverer()} implementation
     * (the pre-existing pattern) are unaffected — their override takes precedence.
     *
     * <p>Adapters that <em>only</em> override {@link #enumerateResources} and
     * {@link #discoverOnCollect()} may leave {@code getDiscoverer()} un-overridden
     * and get the install-time discover path for free through this default.
     */
    @SuppressWarnings("unchecked")
    protected VcfCfDiscoverer getDiscoverer() {
        return (cfg, http, param, dr) -> {
            enumerateResources(dr::addResource);
        };
    }

    /**
     * Return the {@link VcfCfCollector} for this adapter.
     *
     * <p>Called during each scheduled collect cycle. The same object may
     * implement both {@link VcfCfDiscoverer} and {@link VcfCfCollector}.
     */
    @SuppressWarnings("rawtypes")
    protected abstract VcfCfCollector getCollector();

    // -----------------------------------------------------------------------
    // Tuning hooks (override if needed)
    // -----------------------------------------------------------------------

    /**
     * Per-cycle relationship cap. Default: {@link #MAX_RELATIONSHIPS_PER_CYCLE}.
     * Override to reduce the limit for adapters with very large topologies.
     */
    protected int getMaxRelationshipsPerCycle() {
        return MAX_RELATIONSHIPS_PER_CYCLE;
    }

    // -----------------------------------------------------------------------
    // Collect-path discovery opt-in (VCF Ops 9.0.2 onDiscover() gap)
    // -----------------------------------------------------------------------

    /**
     * Whether this adapter wants the framework to drive resource discovery from
     * the collect path every cycle.
     *
     * <p><strong>Background (VCF Ops 9.0.2).</strong> On VCF Ops 9.0.2 the
     * server's "Auto Discover" task never invokes {@code onDiscover()} for
     * adapter3-path adapters. Fresh instances sit at zero resources indefinitely
     * unless the adapter registers resources from within the collect cycle via
     * {@link AdapterBase}'s {@code collectResult.addNewResource}. This method is
     * the one-line opt-in that tells the framework to do exactly that.
     *
     * <p><strong>When to return {@code true}.</strong> Return {@code true} for any
     * adapter that must work on fresh instances in VCF Ops 9.0.2+. In practice,
     * this means every adapter that discovers more than zero resources should opt in
     * — there is no cost to doing so (the platform de-duplicates already-known
     * resources by their identifying identifiers, so re-registering on every cycle
     * is safe and cheap).
     *
     * <p><strong>What the framework does when {@code true}.</strong> At the top of
     * every {@code onCollect()} cycle — before the per-resource collect loop — the
     * framework calls {@link #enumerateResources(ResourceSink)} with
     * {@link #registerNewResource(ResourceConfig)} as the sink. Any enumeration
     * failure propagates loud (the cycle logs the exception and aborts rediscovery;
     * it does NOT silently register nothing). This mirrors the behavior of
     * {@link VcfCfCollector#needsRediscovery(Object)} /
     * {@link VcfCfCollector#rediscover} but is driven by the framework without
     * requiring the adapter to implement those collector methods.
     *
     * <p><strong>Default: {@code false}.</strong> Adapters that do not override this
     * method are unaffected — no rediscovery is injected into their collect cycle.
     *
     * <p><strong>Opt-in recipe (one line):</strong>
     * <pre>{@code
     * @Override protected boolean discoverOnCollect() { return true; }
     * }</pre>
     *
     * <p><strong>Cooperative cancellation.</strong> {@link #enumerateResources}
     * is expected to honor {@link InterruptedException}; the framework propagates
     * it cleanly and aborts the cycle without registering a partial resource set.
     *
     * @return {@code true} to enable collect-path rediscovery via
     *         {@link #enumerateResources(ResourceSink)}; {@code false} (default)
     *         to leave collect-path behavior unchanged
     * @see #enumerateResources(ResourceSink)
     */
    protected boolean discoverOnCollect() {
        return false;
    }

    /**
     * Called once at the top of every collection cycle (issue #221), at the
     * start of {@link #onCollect}, before {@link VcfCfCollector#needsRediscovery},
     * {@link #discoverOnCollect()} discovery and any per-resource collect.
     * Default: no-op.
     *
     * <p>Use it for per-cycle state: reset a snapshot cache so one snapshot
     * is shared by every resource in the cycle, or clear a cached failure so
     * a failed build is retried once per cycle and not once per resource.
     * Before this hook adapters marked the cycle start inside
     * {@code needsRediscovery}, which the framework still calls exactly once
     * per cycle, so an adapter that does that keeps working; new code should
     * use this hook.
     *
     * <p>Runs on the collection thread. Keep it cheap and free of I/O. A
     * {@link RuntimeException} it throws is logged at WARN and the cycle
     * continues.
     */
    protected void onCycleStart() {
    }

    /**
     * Enumerate all resources managed by this adapter and deliver each one to
     * {@code sink}.
     *
     * <p>This is the <strong>shared enumeration body</strong> that the framework
     * calls from two paths when the adapter opts in via {@link #discoverOnCollect()}:
     *
     * <ol>
     *   <li><strong>Install-time discovery</strong> ({@code onDiscover()} path):
     *       {@link #getDiscoverer()}'s default implementation calls
     *       {@code enumerateResources(dr::addResource)}, feeding each resource into
     *       the {@code DiscoveryResult}.</li>
     *   <li><strong>Collect-path registration</strong> ({@code onCollect()} path):
     *       when {@link #discoverOnCollect()} returns {@code true}, the framework
     *       calls {@code enumerateResources(this::registerNewResource)} at the top of
     *       every collect cycle, registering new resources via the cycle's embedded
     *       {@code DiscoveryResult}.</li>
     * </ol>
     *
     * <p><strong>One body, two callers.</strong> Holding the enumeration here
     * guarantees the two paths can never drift — the cardinal requirement proven by
     * the UniFi build-4 dual-path discovery fix.
     *
     * <p><strong>Failure posture.</strong> A failed enumeration must throw an
     * {@link Exception} (not catch-and-return-empty). The framework treats a thrown
     * exception as a loud rediscovery failure: it logs the exception and continues
     * the collect cycle with the existing resource set. This satisfies the
     * "unreadable is NOT invisible" requirement — a failed API call must never
     * silently register zero resources.
     *
     * <p><strong>Cooperative cancellation.</strong> Check
     * {@link #isAbortRequested()} and throw {@link InterruptedException} if the
     * thread is interrupted, so the framework can abort the cycle cleanly.
     *
     * <p><strong>Bare-instantiation safety.</strong> The framework never calls
     * {@code enumerateResources} during the controller-side describe phase (where
     * the adapter is instantiated bare with no injected state). It is safe to
     * reference {@code this.config}, {@code this.httpClient}, or other fields set in
     * {@link #configureAdapter} from within this method.
     *
     * <p><strong>Default behavior.</strong> Throws {@link UnsupportedOperationException}
     * with an actionable message. This default is exercised only if the adapter calls
     * {@link #discoverOnCollect()} returning {@code true} without overriding this
     * method — which is a programming error; the message identifies it clearly.
     * Adapters that override {@link #getDiscoverer()} directly and do not use the
     * collect-path opt-in never trigger this default.
     *
     * @param sink receives each enumerated resource; must not be {@code null}
     * @throws InterruptedException if cooperative cancellation is detected
     * @throws Exception on any enumeration failure (propagates as loud failure)
     * @see #discoverOnCollect()
     * @see ResourceSink
     */
    protected void enumerateResources(ResourceSink sink)
            throws InterruptedException, Exception {
        throw new UnsupportedOperationException(
                "VcfCfAdapter.enumerateResources: this adapter has discoverOnCollect()=true "
                + "but has not overridden enumerateResources(ResourceSink). "
                + "Either override enumerateResources(sink) with the shared enumeration body, "
                + "or set discoverOnCollect() back to false and hand-roll "
                + "VcfCfCollector.needsRediscovery() / rediscover() instead. "
                + "See knowledge/context/framework_v2_migration.md §22.");
    }

    // -----------------------------------------------------------------------
    // AdapterBase required + optional overrides — lifecycle orchestration
    // -----------------------------------------------------------------------

    /**
     * Load and return the adapter's {@link AdapterDescribe} from
     * {@code describe.xml}.
     *
     * <p>The default implementation resolves the file using
     * {@link AdapterBase#getAdapterDescribeFile(String, String)} with the
     * adapter kind key. The canonical path is
     * {@code <adaptersHome>/<adapterKindKey>/conf/describe.xml}.
     *
     * <h4>Kind key resolution order</h4>
     * <ol>
     *   <li>The value stored in {@link #adapterKindKey} at construction time
     *       (set by {@link #VcfCfAdapter(String)} and
     *       {@link #VcfCfAdapter(String, String, Integer)}). This is the safe
     *       path: it works during controller-side bare instantiation where
     *       the platform has NOT yet injected config.</li>
     *   <li>If {@code adapterKindKey} is null (legacy constructor path),
     *       falls back to {@link AdapterBase#getAdapterKind()}, which reads
     *       from the injected adapter-instance config. This returns null
     *       during controller-side bare instantiation — see LESSON below.</li>
     *   <li>If both are null, throws {@link RuntimeException} with an
     *       actionable message describing what was tried. Never silently
     *       returns null or NPEs downstream.</li>
     * </ol>
     *
     * <p><strong>LESSON (controller-side bare instantiation):</strong>
     * During pak install the controller instantiates the adapter class
     * bare (no-arg reflection, no platform injection) and calls
     * {@code describe()}. {@link AdapterBase#getAdapterKind()} is null at
     * that point because it reads from the injected adapter-instance config,
     * which does not exist yet. This is the root cause of the build 44
     * NPE chain:
     * {@code "VcfCfAdapter.onDescribe: failed to load describe.xml from null"
     * → "Cannot invoke AdapterDescribe.getKey() because conf is null"
     * → "DistributedTaskInstallUninstallAdapters failed"}.
     * Build 43 was immune because its {@code onDescribe()} used the static
     * {@code ADAPTER_KIND} constant directly. This framework default replicates
     * that safety via the constructor-stored kind key.
     * See {@code knowledge/lessons/controller-describe-bare-instantiation.md}.
     *
     * <p>Override this method only when custom describe handling is required
     * (e.g., programmatic describe construction or a non-standard file location).
     * Normal adapters should rely on this default.
     *
     * <h4>Localization</h4>
     * <p>The SDK's {@link AdapterDescribe#make(String)} overload (file-path form)
     * automatically loads the localized-names bundle from
     * {@code <conf>/resources/resources.properties} (and locale variants) that
     * sits next to {@code describe.xml}. This is the SDK's intended mechanism:
     * {@code AdapterDescribe} internally computes
     * {@code resourcesPath = describeFile.getParent() + File.separator + "resources"}
     * and passes it to its two-arg {@code loadDescribe(Node, resourcesPath)} method,
     * which calls {@link com.integrien.alive.common.adapter3.describe.MultiLanguageDescriptionsDescribeLoader#load(String)}.
     *
     * <p>The {@link AdapterDescribe#make(java.io.InputStream)} overload (stream form)
     * calls the single-arg {@code loadDescribe(Node)} which delegates to the two-arg
     * form with {@code null} as the resources path — so no localization bundle is
     * loaded. That was the v1→v2 regression (build 43): switching to the stream
     * overload silently dropped the resources bundle, leaving the platform with bare
     * integer {@code nameKey}s and no localized strings at install time.
     *
     * <p>If {@code resources.properties} is absent the SDK logs a warning and
     * continues — the returned {@link AdapterDescribe} carries no localized names,
     * which is the same behavior as before the fix. No exception is thrown.
     *
     * @return the populated {@link AdapterDescribe}; never {@code null}
     * @throws RuntimeException if the kind key is unresolvable, or if
     *         describe.xml is missing, unreadable, or cannot be parsed —
     *         the exception message lists what was tried
     */
    @Override
    public AdapterDescribe onDescribe() {
        // Resolution order: constructor-stored key → injected getAdapterKind()
        String kind = this.adapterKindKey;
        String kindSource = "constructor-stored adapterKindKey";
        if (kind == null || kind.isEmpty()) {
            kind = getAdapterKind();
            kindSource = "getAdapterKind() [injected — null during controller-side describe]";
        }
        if (kind == null || kind.isEmpty()) {
            throw new RuntimeException(
                    "VcfCfAdapter.onDescribe: adapter kind key is unresolvable. "
                    + "Tried: (1) constructor-stored adapterKindKey=null, "
                    + "(2) getAdapterKind()=null (no platform injection during "
                    + "controller-side describe phase). "
                    + "Fix: call super(ADAPTER_KIND) from your adapter's no-arg "
                    + "constructor and super(ADAPTER_KIND, adapterDir, instanceId) "
                    + "from your two-arg constructor. "
                    + "See knowledge/lessons/controller-describe-bare-instantiation.md.");
        }
        // Use make(String) — the file-path overload — so the SDK automatically
        // loads <conf>/resources/resources.properties alongside describe.xml.
        // make(InputStream) passes null for the resources path and skips the
        // localization bundle entirely (v1→v2 regression, build 43).
        Path describeFile = getAdapterDescribeFile(kind, "describe.xml");
        AdapterDescribe describe = AdapterDescribe.make(describeFile.toString());
        if (describe == null) {
            throw new RuntimeException(
                    "VcfCfAdapter.onDescribe: failed to load describe.xml from "
                    + describeFile + " (adapterKind=" + kind
                    + ", source=" + kindSource + "): AdapterDescribe.make returned null "
                    + "(file missing, unreadable, or XML invalid)");
        }
        return describe;
    }

    /**
     * {@code "vcfcf-adapter-base <version> (source <commit>)"} from the
     * manifest of the jar this class was loaded from (issue #214), or a label
     * saying the version is unknown (classes not loaded from a jar, or a jar
     * built before the manifest stamp). Never throws. Reads this pak's own
     * copy through the class's code source, never the class loader's first
     * {@code META-INF/MANIFEST.MF}, which could belong to another jar.
     */
    static String frameworkBuildLabel() {
        return describeFrameworkBuild(frameworkManifest());
    }

    /** The framework jar's manifest, or {@code null}. Never throws. */
    static java.util.jar.Manifest frameworkManifest() {
        try {
            java.security.CodeSource cs =
                    VcfCfAdapter.class.getProtectionDomain().getCodeSource();
            if (cs == null || cs.getLocation() == null) return null;
            java.nio.file.Path jar = java.nio.file.Paths.get(cs.getLocation().toURI());
            if (!java.nio.file.Files.isRegularFile(jar)) return null;
            try (java.util.jar.JarFile jf = new java.util.jar.JarFile(jar.toFile(), false)) {
                return jf.getManifest();
            }
        } catch (Exception | LinkageError e) {
            return null;
        }
    }

    /**
     * Label for a framework manifest; see {@link #frameworkBuildLabel()}.
     * Attribute values are stripped of control characters and capped.
     * Visible to tests.
     */
    static String describeFrameworkBuild(java.util.jar.Manifest mf) {
        java.util.jar.Attributes a = mf == null ? null : mf.getMainAttributes();
        String version = a == null ? null : a.getValue("Implementation-Version");
        if (version == null || version.trim().isEmpty()) {
            return "vcfcf-adapter-base (version unknown: no Implementation-Version in"
                    + " the jar manifest)";
        }
        String title = a.getValue("Implementation-Title");
        String commit = a.getValue("X-Vcfcf-Source-Commit");
        return manifestValue(title, "vcfcf-adapter-base") + " " + manifestValue(version, "?")
                + " (source " + manifestValue(commit, "unknown") + ")";
    }

    private static String manifestValue(String v, String fallback) {
        if (v == null || v.trim().isEmpty()) return fallback;
        StringBuilder sb = new StringBuilder();
        String t = v.trim();
        for (int i = 0; i < t.length() && sb.length() < 64; i++) {
            char c = t.charAt(i);
            sb.append(Character.isISOControl(c) ? '?' : c);
        }
        return sb.toString();
    }

    /**
     * {@inheritDoc}
     *
     * <p>Delegates to {@link #configureAdapter(ResourceStatus, ResourceConfig)}.
     * (Re)creates the {@link MetricDataCache} so dedup state is reset on each
     * config change. Releases the previous HTTP client if present.
     */
    @Override
    public final void onConfigure(ResourceStatus resourceStatus,
            ResourceConfig resourceConfig) {
        abortRequested.set(false);
        if (frameworkVersionLogged.compareAndSet(false, true)) {
            // Issue #214: which framework this pak carries. Each pak bundles
            // its own vcfcf-adapter-base.jar, so paks on one collector can run
            // different framework versions side by side.
            logInfo("VcfCfAdapter: framework " + frameworkBuildLabel());
        }
        config = null;
        ManagedHttpClient old = this.httpClient;
        this.httpClient = null;
        if (old != null) {
            old.discard();
        }
        configureAdapter(resourceStatus, resourceConfig);
        // Re-create cache after each configure; dedup state is per-instance.
        this.metricCache = createMetricCache();
    }

    /**
     * {@inheritDoc}
     *
     * <p>Validates connectivity via {@link VcfCfTester}. On failure, sets
     * the error message on {@code param} so the UI's "Test Connection" button
     * shows a meaningful message (§5). Never blank-fails. If no tester is
     * configured, returns {@code true}.
     *
     * <p>When the failure is an untrusted target certificate (a
     * {@code CustomTrustManager.CustomCertificateException} or a PKIX chain
     * failure anywhere in the cause chain), the raw TLS text (for example
     * {@code org.bouncycastle.tls.TlsFatalAlert: certificate_unknown(46)}) is
     * replaced with a readable message telling the admin how to proceed. See
     * {@link #certificateTrustFailureMessage(Throwable, boolean, boolean)}.
     * A pak can replace that text with
     * {@link #certificateFailureMessage(Throwable, ResourceConfig, String)}.
     */
    @Override
    @SuppressWarnings("unchecked")
    public final boolean onTest(TestParam param) {
        VcfCfTester<C> tester = getTester();
        if (tester == null) {
            return true;
        }
        try {
            tester.test(config, httpClient, param);
            return true;
        } catch (Exception e) {
            String msg = e.getMessage();
            if (msg == null || msg.isEmpty()) {
                msg = e.getClass().getSimpleName() + " (no message)";
            }
            // Only consult the (pak-supplied) hooks once the failure is known to
            // be a certificate-trust failure.
            if (findCertificateTrustFailure(e) != null) {
                ResourceConfig tested = testedResourceConfig(param);
                String certMsg = certificateTrustFailureMessage(e,
                        certificatePromptAvailable(param),
                        allowInsecureDescribedSafe(tested));
                certMsg = certificateFailureMessageSafe(e, tested, certMsg);
                if (certMsg != null) {
                    msg = certMsg;
                }
            }
            // §5: populate TestParam — returning false alone gives a blank error.
            param.setErrorMsg(msg);
            logWarn("onTest: connection test failed: " + msg, e);
            return false;
        }
    }

    /**
     * {@inheritDoc}
     *
     * <p>Enumerates resources via {@link VcfCfDiscoverer}, honoring
     * {@code regexp} and {@code params} from the {@link DiscoveryParam} (§6).
     * {@link InterruptedException} is caught, the interrupt flag is restored,
     * and a partial result is returned.
     */
    @Override
    @SuppressWarnings("unchecked")
    public final DiscoveryResult onDiscover(DiscoveryParam param) {
        DiscoveryResult dr = new DiscoveryResult(param.getAdapterInstResource());
        VcfCfDiscoverer<C> discoverer = getDiscoverer();
        if (discoverer == null) {
            return dr;
        }
        try {
            discoverer.discover(config, httpClient, param, dr);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
            logWarn("onDiscover: interrupted — returning partial result");
        } catch (Exception e) {
            String msg = e.getMessage() != null ? e.getMessage()
                    : e.getClass().getSimpleName();
            dr.setErrorMsg(msg);
            logError("onDiscover: failed: " + msg, e);
        }
        return dr;
    }

    /**
     * {@inheritDoc}
     *
     * <p>Implements the full §1 collect sequence:
     * <ol>
     *   <li>{@link #onCycleStart()}, once (issue #221).</li>
     *   <li>Optional top-of-cycle rediscovery (§1 step 1 + §2):
     *       {@link VcfCfCollector#needsRediscovery} is called exactly once per
     *       cycle, then {@link #discoverOnCollect()}.</li>
     *   <li>Per-resource gather → cache metrics/properties → emit events →
     *       emit relationships.</li>
     *   <li>REQUIRED per-resource status set every cycle (§1).</li>
     *   <li>{@link MetricDataCache#flushCachedData()} at end of cycle (§8).</li>
     * </ol>
     *
     * <p>Cooperative cancellation: loops check {@link #isAbortRequested()}
     * and honor {@link InterruptedException} (§9).
     *
     * <p><strong>Adapter instance status (issue #223).</strong> The SDK
     * accepts ERROR and DOWN only on the adapter instance resource (the
     * account row in Integrations > Accounts); child resources take only
     * data-receiving states. So when a whole cycle fails, the framework sets
     * the adapter instance itself: if every resource the cycle collected
     * failed with ERROR or DOWN (DOWN only when every one mapped to DOWN), or
     * there was no resource to collect and the discovery step failed, the
     * adapter instance gets that status with a one-line reason (for example
     * a cached login failure). A cycle cut short by a stop or an interrupt
     * sets nothing. Before this, the account kept showing "Collecting".
     */
    @Override
    @SuppressWarnings("unchecked")
    public final void onCollect(ResourceConfig adapterInstance,
            Collection<ResourceConfig> resources) {
        abortRequested.set(false);
        Exception discoveryFailure = null;

        // Issue #221: the cycle-start hook, once per cycle, before discovery.
        try {
            onCycleStart();
        } catch (RuntimeException e) {
            logWarn("onCollect: onCycleStart failed (non-fatal, the cycle continues): "
                    + e.getMessage(), e);
        }

        VcfCfCollector<C> collector = getCollector();
        if (collector == null) {
            for (ResourceConfig rc : resources) {
                setStatusSafe(rc, ResourceStatusEnum.RESOURCE_STATUS_NO_DATA_RECEIVING);
            }
            return;
        }

        // §1 step 1a: collector-driven top-of-cycle rediscovery (VcfCfCollector
        // needsRediscovery/rediscover pattern — hand-rolled by the adapter).
        if (collector.needsRediscovery(config)) {
            try {
                collector.rediscover(config, httpClient, adapterInstance, this);
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                logWarn("onCollect: interrupted during rediscovery — aborting cycle");
                return;
            } catch (Exception e) {
                logWarn("onCollect: rediscovery failed (non-fatal): "
                        + e.getMessage(), e);
                discoveryFailure = e;
                // Not fatal — continue with existing resource set.
            }
        }

        // §1 step 1b: framework-driven collect-path discovery opt-in.
        // When discoverOnCollect() returns true, the framework calls
        // enumerateResources(this::registerNewResource) at the top of every cycle
        // so that fresh instances (where onDiscover() was never called on VCF Ops
        // 9.0.2) receive their resource set on the first collect.
        // Failure posture: loud (propagates InterruptedException to abort cycle;
        // other exceptions are logged WARN and collection continues with the
        // existing resource set — same non-fatal posture as step 1a above).
        if (discoverOnCollect()) {
            try {
                enumerateResources(this::registerNewResource);
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                logWarn("onCollect: interrupted during collect-path discovery "
                        + "(discoverOnCollect) — aborting cycle");
                return;
            } catch (Exception e) {
                logWarn("onCollect: collect-path discovery (discoverOnCollect) "
                        + "failed (non-fatal): " + e.getMessage(), e);
                if (discoveryFailure == null) discoveryFailure = e;
                // Not fatal — continue with existing resource set.
            }
        }

        if (isAbortRequested()) return;

        // §1 step 2: per-resource gather.
        MetricDataCache cache = this.metricCache;
        CycleOutcome outcome = new CycleOutcome();

        for (ResourceConfig rc : resources) {
            if (isAbortRequested() || Thread.currentThread().isInterrupted()) {
                Thread.currentThread().interrupt();
                outcome.cut = true;
                break;
            }

            outcome.attempted++;
            try {
                List<MetricData> samples = new ArrayList<>();
                collector.collect(config, httpClient, rc, samples, this);

                // Feed samples through the dedup cache (§8).
                if (cache != null) {
                    for (MetricData md : samples) {
                        cache.cacheMetricData(rc, md);
                    }
                } else {
                    // No cache available: push metrics and properties directly.
                    List<MetricData> metrics = new ArrayList<>();
                    List<MetricData> props = new ArrayList<>();
                    for (MetricData md : samples) {
                        MetricKey mk = md.getMetricKey();
                        if (mk != null && mk.isProperty()) {
                            props.add(md);
                        } else {
                            metrics.add(md);
                        }
                    }
                    if (!metrics.isEmpty()) addMetricData(rc, metrics);
                    if (!props.isEmpty()) addMetricData(rc, props, true);
                }

                // Events (§4).
                collector.collectEvents(config, httpClient, rc, this);

                // Relationships (§3): attach to the current CollectResult via the
                // protected 'collectResult' field inherited from AdapterBase.
                Relationships rels = collector.collectRelationships(config, rc);
                if (rels != null && !rels.isEmpty()) {
                    addRelationshipsToCurrentCycle(rels);
                }

                // §1: REQUIRED per-resource status every cycle.
                setStatusSafe(rc, ResourceStatusEnum.RESOURCE_STATUS_DATA_RECEIVING);

            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                logWarn("onCollect: interrupted collecting " + rcLabel(rc)
                        + " — aborting cycle");
                setStatusSafe(rc, ResourceStatusEnum.RESOURCE_STATUS_ERROR);
                outcome.cut = true;
                break;
            } catch (Exception e) {
                String msg = e.getMessage() != null ? e.getMessage()
                        : e.getClass().getSimpleName();
                logWarn("onCollect: error collecting " + rcLabel(rc) + ": " + msg, e);
                ResourceStatusEnum status = collector.mapCollectException(e);
                ResourceStatusEnum effective =
                        status != null ? status : ResourceStatusEnum.RESOURCE_STATUS_ERROR;
                setStatusSafe(rc, effective);
                outcome.recordFailure(effective, e);
            }
        }

        // Issue #223: a cycle in which nothing could be collected shows on
        // the adapter instance (the account row), not only on its objects.
        // An interrupt the collector wrapped (no InterruptedException, no
        // stop) still means the cycle was cut short: set nothing.
        if (!outcome.cut && !isAbortRequested()
                && !Thread.currentThread().isInterrupted()) {
            reportAdapterInstanceFailure(adapterInstance, outcome, discoveryFailure);
        }

        // §8: flush deduplicated data into the CollectResult at end of cycle.
        if (cache != null) {
            cache.flushCachedData();
        }
    }

    // -----------------------------------------------------------------------
    // AdapterBase stop/discard hooks (§9)
    // -----------------------------------------------------------------------

    /**
     * {@inheritDoc}
     *
     * <p>Sets the cooperative abort flag. The per-resource loop in
     * {@link #onCollect} checks {@link #isAbortRequested()} and returns
     * promptly, satisfying the cert "clean thread exit" requirement.
     */
    @Override
    public void onStopCollection() {
        abortRequested.set(true);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Default: no-op. Override to release per-resource state for stopped
     * resources (e.g., clear per-resource caches or session tokens).
     */
    @Override
    public void onStopResources(AdapterStatus status,
            Collection<ResourceConfig> resources) {
        // default: no per-resource state to release
    }

    /**
     * {@inheritDoc}
     *
     * <p>Default: no-op. Override to drop per-resource state for removed
     * resources and to clean up any work-folder files keyed by adapter-instance
     * resource ID (cert requirement: work-folder files must be cleaned up in
     * {@code onRemoveResources} or {@code onDiscard}).
     */
    @Override
    public void onRemoveResources(AdapterStatus status,
            Collection<ResourceConfig> resources) {
        // default: no per-resource state to release
    }

    /**
     * {@inheritDoc}
     *
     * <p>Releases the HTTP client and metric cache. Sets the abort flag so any
     * in-flight collect loop can detect discard and exit.
     *
     * <p>Subclasses may override to release additional resources; call
     * {@code super.onDiscard()} to ensure the HTTP client is closed.
     */
    @Override
    public void onDiscard() {
        abortRequested.set(true);
        ManagedHttpClient client = this.httpClient;
        if (client != null) {
            client.discard();
            this.httpClient = null;
        }
        metricCache = null;
    }

    // -----------------------------------------------------------------------
    // New-resource registration helper (§2)
    // -----------------------------------------------------------------------

    /**
     * Register a newly-discovered resource during the collect cycle.
     *
     * <p>Calls {@code collectResult.addNewResource(key)} on the current cycle's
     * {@code CollectResult} (the protected {@code collectResult} field from
     * {@link AdapterBase}). New resources registered here ride the collect cycle's
     * embedded {@code DiscoveryResult} and are visible in VCF Ops from the same
     * cycle they are first seen (§2).
     *
     * <p>Only call this from within {@link VcfCfCollector#rediscover} or
     * {@link VcfCfCollector#collect} — it has no effect outside an active
     * {@code onCollect} execution.
     *
     * <p>The {@link ResourceKey} must have at least one
     * {@code IDENT_TYPE_IDENTIFYING} identifier for the platform to match the
     * resource on subsequent cycles (§2 identity contract).
     *
     * @param key the resource key with fully-populated identifying identifiers
     */
    public void registerNewResource(ResourceKey key) {
        com.integrien.alive.common.adapter3.CollectResult cr = collectResult;
        if (cr != null) {
            cr.addNewResource(key);
        }
    }

    /**
     * Register a newly-discovered resource (ResourceConfig form) during
     * the collect cycle. See {@link #registerNewResource(ResourceKey)}.
     *
     * @param rc a ResourceConfig with its ResourceKey fully populated
     */
    public void registerNewResource(ResourceConfig rc) {
        com.integrien.alive.common.adapter3.CollectResult cr = collectResult;
        if (cr != null) {
            cr.addNewResource(rc);
        }
    }

    // -----------------------------------------------------------------------
    // Relationship attachment helper (§3)
    // -----------------------------------------------------------------------

    /**
     * Attach a {@link Relationships} object to the current cycle's
     * {@code CollectResult}.
     *
     * <p>Uses the protected {@code collectResult} field inherited from
     * {@link AdapterBase}. Only valid during an active {@code onCollect}
     * execution; no-op if called outside a cycle.
     *
     * <p>Cap edges before calling: enforce {@link #getMaxRelationshipsPerCycle()}
     * in the caller.
     *
     * @param rels the relationships to attach
     */
    public void addRelationshipsToCurrentCycle(Relationships rels) {
        com.integrien.alive.common.adapter3.CollectResult cr = collectResult;
        if (cr != null && rels != null) {
            cr.addRelationships(rels);
        }
    }

    // -----------------------------------------------------------------------
    // SSL integration (cert item)
    // -----------------------------------------------------------------------

    /**
     * Build an {@link javax.net.ssl.SSLContext} backed by the platform's
     * {@link com.integrien.alive.common.adapter3.CustomTrustManager} (the TOFU trust manager,
     * accessed via {@link AdapterBase#getAdapterTrustManager()}).
     *
     * <p>This is the <strong>required</strong> way to obtain SSL context for
     * {@link com.vcfcf.adapter.http.HttpClientBuilder}. It ensures the platform's
     * certificate management (user-trusted certs, renewal URLs) is honoured.
     * The cert certification item forbids using {@link #insecureSslContext()} as
     * the default path for target-system connections.
     *
     * <p><strong>TOFU constraint:</strong> {@code CustomTrustManager} throws
     * {@code CustomCertificateException} on first contact with any cert not already
     * approved in the platform's trust store, then fires a side-effect notification.
     * The platform's {@code URLConnection}/{@code getSocketFactory()} path intercepts
     * that exception and retries after cert registration. {@code java.net.http.HttpClient}
     * does not — so this context must only be used with {@code HttpClientBuilder}, never
     * raw with {@code java.net.http.HttpClient}. Also, do <strong>not</strong> use this
     * for the Suite API transport — use {@link #openPlatformConnection(String)}
     * instead, which mirrors the vendor {@code SuiteAPIClient} transport
     * (trust-all + ignore-hostname, or the cluster truststore + ignore-hostname
     * in FIPS mode) rather than the platform's strict TOFU
     * {@code CustomTrustManager}, which cannot self-heal for framework adapters
     * (see the {@link #openPlatformConnection(String)} javadoc and
     * {@code knowledge/context/defects.md} DEF-005).
     *
     * <p><strong>Accepting a certificate.</strong> Certificates the admin
     * accepts in the Validate Connection review dialog are loaded into this
     * trust manager by the platform before {@code configure}/{@code test}, so
     * this context trusts them with no change here. The dialog only appears
     * for adapters that declare their endpoints through
     * {@link #certificateCheckUrls(ResourceConfig)}.
     *
     * <p><strong>Hostname checking (bytecode, SDK 2.2 and 9.1.1).</strong>
     * {@code CustomTrustManager} extends {@link javax.net.ssl.X509ExtendedTrustManager},
     * so JSSE does not wrap it with its own endpoint-identity check, and its
     * {@code Socket}/{@code SSLEngine} overloads run PKIX chain validation only
     * (the peer host is used for renewal bookkeeping, not name matching). On
     * {@code java.net.http.HttpClient} this context therefore validates the
     * chain but does not match the certificate name to the host dialed. The
     * platform's own review probe does check the name (it uses
     * {@code getVerifier()}, a {@code CustomHostnameVerifier}). Chain
     * validation stays strict; only {@link #insecureSslContext()} (the
     * explicit Allow Insecure opt-out) relaxes it. To have the name checked
     * too, opt in with {@link #getPlatformSslContext(String)} (issue #185);
     * this no-argument form is unchanged.
     *
     * @return an {@link javax.net.ssl.SSLContext} built from {@code getAdapterTrustManager()}
     *         and {@code getKeyManagers()} — suitable for use with {@code HttpClientBuilder}
     *         on target-system endpoints where the admin has already approved the cert
     * @throws RuntimeException if context construction fails
     */
    public javax.net.ssl.SSLContext getPlatformSslContext() {
        try {
            javax.net.ssl.TrustManager tm = getAdapterTrustManager();
            javax.net.ssl.KeyManager[] km = getKeyManagers();
            javax.net.ssl.SSLContext ctx = javax.net.ssl.SSLContext.getInstance("TLS");
            ctx.init(km, new javax.net.ssl.TrustManager[]{tm}, null);
            return ctx;
        } catch (Exception e) {
            throw new RuntimeException(
                    "VcfCfAdapter: failed to build platform SSL context", e);
        }
    }

    /**
     * Opt-in (issues #185, #206): {@link #getPlatformSslContext()} plus a
     * check that the target certificate carries the host the client dials.
     * The platform chain check runs first, unchanged, so an untrusted chain
     * still fails as the platform threw it and the Validate Connection accept
     * dialog still applies; then the leaf certificate must name
     * {@code dialledHost} (a DNS or IP subject alternative name, or the CN
     * when there is no DNS name), during the handshake, before any credential
     * is sent. See {@link com.vcfcf.adapter.http.CertificateNames}.
     *
     * <p>{@code dialledHost} is the host this context's clients connect to,
     * as the account entered it ({@code host}, {@code host:port},
     * {@code [v6]}, {@code [v6]:port}); not a URL. It is fixed here, not read
     * from the connection, because the BouncyCastle JSSE provider on 9.1.1
     * collectors reports no peer host. A blank or unusable value refuses
     * every handshake (fail closed). One context per dialled host.
     *
     * <p>An {@code HttpsURLConnection} built on this context should also get
     * {@link com.vcfcf.adapter.http.CertificateNames#secure} (strict
     * always-false {@code HostnameVerifier}); {@code java.net.http.HttpClient}
     * has no verifier, so the trust manager's check is the one that counts
     * there. The Suite API hop ({@link #openPlatformConnection(String)}) is
     * not affected: it keeps trust-all and ignore-hostname, so a loopback
     * {@code localhost} call still works against an appliance certificate
     * with no {@code localhost} name. An account entered by IP passes only
     * when the certificate lists that IP; accepting a certificate does not
     * fix a name mismatch.
     *
     * @param dialledHost the host the clients using this context connect to
     * @return the name-checking platform context
     * @throws RuntimeException if context construction fails
     */
    public javax.net.ssl.SSLContext getPlatformSslContext(String dialledHost) {
        try {
            return com.vcfcf.adapter.http.CertificateNames.nameCheckingContext(
                    getAdapterTrustManager(), getKeyManagers(), dialledHost);
        } catch (RuntimeException e) {
            throw new RuntimeException(
                    "VcfCfAdapter: failed to build the name-checking platform SSL context", e);
        }
    }

    /**
     * Open an HTTPS connection to {@code url} for the Suite API transport,
     * wired to mirror the vendor Suite API client transport
     * <strong>exactly</strong>: trust-all + ignore-hostname in non-FIPS mode,
     * the cluster-truststore TLS options + ignore-hostname in FIPS mode. That
     * is the posture every shipping Broadcom pak uses for this hop.
     *
     * <h3>Why this mirrors BC instead of using the platform TOFU trust manager</h3>
     * <p>An earlier implementation routed this hop through the platform's
     * {@code CustomSSLSocketFactory} ({@code getSocketFactory()}), betting that
     * its TOFU-survival intercept would register and persist an unknown cert
     * on first contact. Live devel evidence falsified that bet: the platform's
     * asynchronous {@code NonDisruptiveCertificateHandler} errors on every
     * attempt with {@code "Adapter certificate renewal url set is empty"}
     * because framework ({@code com.vcfcf}) adapters declare no
     * certificate-renewal URL set, so trust never persists and every cycle
     * PKIX-fails ({@code knowledge/context/investigations/synology-b23-devel-pkix-2026-07-01.md},
     * {@code knowledge/context/defects.md} DEF-005). {@code knowledge/lessons/suite-api-stitch-ssl-tofu-vs-java-http.md}
     * predicted exactly this failure mode and is vindicated by that live run.
     *
     * <p>The vendor ground truth (bytecode,
     * {@code knowledge/context/api-surface/casa-injected-vs-raw-client.md} §3):
     * {@code aria-ops-core SuiteAPIClient.getClientConfigBuilder} branches on
     * {@code Constants.FIPS_MODE_ENABLED}, which is
     * {@code Boolean.valueOf(System.getenv("IS_FIPS"))} and nothing else.
     * Non-FIPS sets {@code verify("false")} + {@code ignoreHostName(true)};
     * FIPS sets {@code verify("true")} + {@code ignoreHostName(true)} and
     * {@code useClusterTruststore(true)}. In {@code vcops-suiteapi-client}
     * {@code HttpClientFactory.createClient}, that flag selects
     * {@code SSLOptions.getSSLOptions(VROPS_CLUSTER)} (the builder's default
     * connection category) and builds a {@code vROpsSSLSocketFactory} from it.
     * This method mirrors that behavior directly rather than inventing a new
     * transport posture; {@link #applySuiteApiTransport} holds the dispatch.
     *
     * <h3>Mode detection</h3>
     * <p>{@link #isFipsModeEnabled()}: the {@code IS_FIPS} environment
     * variable, parsed with {@code Boolean.valueOf} semantics, exactly as the
     * vendor does ({@code Constants} and {@code SSLOptions} both read it). The
     * BouncyCastle {@code org.bouncycastle.fips.approved_only} JVM property is
     * <strong>not</strong> a mode signal: every vendor and platform class on
     * this path keys on {@code IS_FIPS} alone, so a second trigger would pick
     * the FIPS branch where the vendor would not. Its value is printed in the
     * once-per-instance mode line as a diagnostic. The mode line names the
     * signal that fired.
     *
     * <h3>Non-FIPS branch</h3>
     * <p>{@link #applyBcMirrorTransport}: {@link #insecureSslContext()}
     * (trust-all {@code X509ExtendedTrustManager}) + an all-true
     * {@link javax.net.ssl.HostnameVerifier}, unconditionally, for both
     * loopback (ambient) and explicit/remote (collector) Suite API endpoints,
     * exactly matching the vendor's unconditional
     * {@code verify("false")}/{@code ignoreHostName(true)}. (Earlier revisions
     * of this method peer-gated the hostname verifier, relaxed only for a
     * resolved-loopback peer and strict otherwise. That peer-gating was this
     * framework's own invention, not present in the vendor client, and was
     * removed per the "mirror BC exactly" directive that closed DEF-005.)
     * No cluster file is read on this branch.
     *
     * <h3>FIPS branch (issue #215)</h3>
     * <p>{@link #applyClusterTruststoreTransport}: the socket factory the
     * vendor builds from {@code SSLOptions(VROPS_CLUSTER)}
     * ({@link #resolveClusterSslOptions}, {@link #buildClusterSocketFactory}),
     * plus an all-true {@link javax.net.ssl.HostnameVerifier}
     * ({@code ignoreHostName(true)}). Inputs:
     * {@code $STORAGE/vcops/user/conf/ssl/secure-communications.properties}
     * (keys looked up under {@code inter_cluster.} then {@code default.}),
     * with password sentinels redirected to {@code storePass.properties} in
     * the same directory. The factory is cached per adapter instance and
     * rebuilt when any input file's modification time or size changes
     * ({@link ClusterSocketFactoryCache}).
     *
     * <p><strong>Failure mode.</strong> Any unreadable or incomplete input
     * throws an {@link java.io.IOException} naming the path (and key), and logs
     * one WARN per adapter instance. It never falls back to trust-all: that
     * silent downgrade is what issue #215 removed. The Suite API call fails,
     * which the stitch client already logs and swallows without throwing into
     * the collect cycle. Where the vendor would carry on with an empty trust
     * store (no {@code secure-communications.properties}, no {@code truststore}
     * key), every handshake fails anyway; this method fails earlier and names
     * the cause.
     *
     * <p>This is the public equivalent of the package-private
     * {@code AdapterBase.getConnection(url, getVerifier())}, which callers in other
     * packages cannot reach.
     *
     * <p>For target-system connections (vCenter, NAS appliances, etc.) use
     * {@link com.vcfcf.adapter.http.HttpClientBuilder#platformSsl(VcfCfAdapter)} instead.
     * This method is the Suite API hop only; target-system TLS is unaffected.
     *
     * @param url the full HTTPS URL to open (must use the {@code https} scheme;
     *            a non-https URL is rejected with an {@link java.io.IOException})
     * @return an {@link javax.net.ssl.HttpsURLConnection} configured with the
     *         vendor-mirror transport for the detected mode
     * @throws java.io.IOException if the URL scheme is not https, if the connection
     *         cannot be opened, or (FIPS mode) if the cluster TLS options cannot be
     *         loaded
     */
    public java.net.URLConnection openPlatformConnection(String url)
            throws java.io.IOException {
        java.net.URL u = new java.net.URL(url);
        java.net.URLConnection conn = u.openConnection();
        if (!(conn instanceof javax.net.ssl.HttpsURLConnection)) {
            throw new java.io.IOException(
                    "VcfCfAdapter.openPlatformConnection: expected an https URL but got "
                    + u.getProtocol() + " for " + url
                    + " (only the https Suite API endpoint is supported)");
        }
        javax.net.ssl.HttpsURLConnection https = (javax.net.ssl.HttpsURLConnection) conn;
        boolean fips = isFipsModeEnabled();
        // Called per Suite API request: log the mode once per adapter instance.
        if (transportModeLogged.compareAndSet(false, true)) {
            logInfo(describeTransportMode(fips, fips ? describeClusterSslDirectory() : null,
                    System.getProperty("org.bouncycastle.fips.approved_only")));
        }
        return applySuiteApiTransport(https, fips, VcfCfAdapter::clusterSslDirectory,
                clusterSocketFactoryCache, VcfCfAdapter::decryptWithPlatformCrypt, e -> {
                    if (fipsTruststoreFailureWarnLogged.compareAndSet(false, true)) {
                        logWarn("VcfCfAdapter.openPlatformConnection: IS_FIPS=true but the "
                                + "cluster TLS options could not be loaded, so the Suite API "
                                + "connection is refused instead of falling back to trust-all "
                                + "(issue #215). Cause: " + e.getMessage() + " (Logged once per "
                                + "adapter instance; every Suite API call fails with this cause "
                                + "until the inputs are readable.)");
                    }
                });
    }

    /** Source of the cluster SSL directory; only consulted on the FIPS branch. */
    @FunctionalInterface
    interface SslDirectorySource {
        java.nio.file.Path get() throws java.io.IOException;
    }

    /**
     * The Suite API transport dispatch, instance-free so it is unit-testable.
     * Non-FIPS: {@link #applyBcMirrorTransport}. FIPS:
     * {@link #applyClusterTruststoreTransport}; on failure {@code onFipsFailure}
     * runs and the exception propagates. There is no trust-all fallback on the
     * FIPS branch (issue #215), and {@code sslDir} is not consulted on the
     * non-FIPS branch.
     *
     * @return {@code https}, configured
     * @throws java.io.IOException (FIPS) if the cluster TLS options cannot be
     *         loaded; the connection is left on the JDK defaults and must not
     *         be used
     */
    static javax.net.ssl.HttpsURLConnection applySuiteApiTransport(
            javax.net.ssl.HttpsURLConnection https, boolean fips, SslDirectorySource sslDir,
            ClusterSocketFactoryCache cache, java.util.function.UnaryOperator<String> decryptor,
            java.util.function.Consumer<java.io.IOException> onFipsFailure)
            throws java.io.IOException {
        if (!fips) {
            applyBcMirrorTransport(https);
            return https;
        }
        try {
            applyClusterTruststoreTransport(https, sslDir.get(), cache, decryptor);
        } catch (java.io.IOException e) {
            onFipsFailure.accept(e);
            throw e;
        }
        return https;
    }

    /** Vendor FIPS switch: {@code Constants.FIPS_MODE_ENABLED} and {@code SSLOptions.IS_FIPS} read this. */
    static final String FIPS_ENV_VAR = "IS_FIPS";
    /** Root of the cluster SSL directory ({@code SSLOptions.getStorage}: environment, then system property). */
    static final String STORAGE_VAR = "STORAGE";
    /** Cluster TLS options file ({@code SSLOptions.<clinit>}). */
    static final String SECURE_COMMUNICATIONS_FILE = "secure-communications.properties";
    /** Store password file ({@code SSLOptions.<clinit>}). */
    static final String STORE_PASS_FILE = "storePass.properties";
    /** Lookup prefixes for {@code VROPS_CLUSTER}, most specific first ({@code SSLOptions.propertyLookupPrefixes}). */
    static final List<String> CLUSTER_PROPERTY_PREFIXES =
            Collections.unmodifiableList(java.util.Arrays.asList("inter_cluster", "default"));
    /** {@code SSLOptions.ALL_JRE_*_KEYWORD}: use the JRE default list. */
    static final String ALL_JRE_KEYWORD = "%all%";
    /** {@code SSLOptions.DEFAULT_TRUSTSTORE_PASSWORD_KEYWORD}: redirect to {@code storePass.properties}. */
    static final String TRUSTSTORE_PASSWORD_SENTINEL = "%truststore_password%";
    /** {@code SSLOptions.DEFAULT_KEYSTORE_PASSWORD_KEYWORD}: redirect to {@code storePass.properties}. */
    static final String KEYSTORE_PASSWORD_SENTINEL = "%keystore_password%";
    /** {@code storePass.properties} key behind {@link #TRUSTSTORE_PASSWORD_SENTINEL}. */
    static final String STORE_PASS_TRUSTSTORE_KEY = "ssltruststorePassword";
    /** {@code storePass.properties} key behind {@link #KEYSTORE_PASSWORD_SENTINEL}. */
    static final String STORE_PASS_KEYSTORE_KEY = "sslkeystorePassword";
    /** Suffix of an encrypted property ({@code SSLOptions.readPasswordProperty}, {@code CryptUtils}). */
    static final String ENCRYPTED_KEY_SUFFIX = ".encrypted";

    /**
     * Apply the BC-mirror non-FIPS Suite API transport (trust-all +
     * ignore-hostname) to an already-opened {@link javax.net.ssl.HttpsURLConnection}.
     *
     * <p>Extracted from {@link #openPlatformConnection(String)} as a
     * standalone static helper (it touches no instance/platform state), so
     * it is directly unit-testable without instantiating a live
     * {@link AdapterBase} subclass (which requires the collector's log4j-core
     * runtime classpath, unavailable outside the appliance).
     *
     * <p>Mirrors {@code aria-ops-core SuiteAPIClient.getClientConfigBuilder()}'s
     * non-FIPS branch exactly: {@code verify("false")} + {@code ignoreHostName(true)},
     * trust-all and hostname-unchecked, unconditionally (no loopback/remote
     * peer-gating; the vendor does not gate either; see DEF-005).
     *
     * @param https the connection to configure
     */
    static void applyBcMirrorTransport(javax.net.ssl.HttpsURLConnection https) {
        https.setSSLSocketFactory(insecureSslContext().getSocketFactory());
        https.setHostnameVerifier((h, s) -> true);
    }

    /**
     * Apply the FIPS-mode Suite API transport to an already-opened
     * {@link javax.net.ssl.HttpsURLConnection}: the cached cluster socket
     * factory plus an all-true {@link javax.net.ssl.HostnameVerifier}. Mirrors
     * the vendor FIPS branch: {@code verify("true")} +
     * {@code ignoreHostName(true)} + {@code useClusterTruststore(true)}.
     *
     * <p>The all-true verifier also keeps JSSE from setting an endpoint
     * identification algorithm on the socket ({@code HttpsURLConnection} sets
     * one only when the default verifier is in effect), so the PKIX trust
     * manager validates the chain and does not match the name. Loopback
     * ({@code localhost}) therefore works against a certificate issued to the
     * node's FQDN.
     *
     * @throws java.io.IOException naming the offending path if the options
     *         cannot be loaded; the connection is left unconfigured
     */
    static void applyClusterTruststoreTransport(javax.net.ssl.HttpsURLConnection https,
            java.nio.file.Path sslDir, ClusterSocketFactoryCache cache,
            java.util.function.UnaryOperator<String> decryptor) throws java.io.IOException {
        javax.net.ssl.SSLSocketFactory factory = cache.get(sslDir, true, decryptor);
        https.setSSLSocketFactory(factory);
        https.setHostnameVerifier((h, s) -> true);
    }

    /**
     * The resolved vendor {@code SSLOptions} for the {@code VROPS_CLUSTER}
     * category. Passwords are held only as long as the cache entry.
     */
    static final class ClusterSslOptions {
        final java.nio.file.Path optionsFile;
        final java.nio.file.Path storePassFile;
        final String protocol;
        final String storeType;
        final String algorithm;
        final String truststore;
        final String truststorePassword;
        final String keystore;
        final String keystorePassword;
        final String[] supportedProtocols;
        final String[] supportedCipherSuites;

        ClusterSslOptions(java.nio.file.Path optionsFile, java.nio.file.Path storePassFile,
                String protocol, String storeType, String algorithm, String truststore,
                String truststorePassword, String keystore, String keystorePassword,
                String[] supportedProtocols, String[] supportedCipherSuites) {
            this.optionsFile = optionsFile;
            this.storePassFile = storePassFile;
            this.protocol = protocol;
            this.storeType = storeType;
            this.algorithm = algorithm;
            this.truststore = truststore;
            this.truststorePassword = truststorePassword;
            this.keystore = keystore;
            this.keystorePassword = keystorePassword;
            this.supportedProtocols = supportedProtocols;
            this.supportedCipherSuites = supportedCipherSuites;
        }
    }

    /**
     * Resolve {@code SSLOptions(VROPS_CLUSTER)} the way the vendor
     * constructor does, from {@code <sslDir>/secure-communications.properties}:
     * <ul>
     *   <li>each key is looked up as {@code inter_cluster.<key>} then
     *       {@code default.<key>};</li>
     *   <li>{@code protocol}, {@code store_type}, {@code algorithm},
     *       {@code supported_cipher_suites}, {@code supported_protocols} are
     *       required; {@code truststore}, {@code keystore} and the passwords
     *       are optional (this method then requires {@code truststore} and,
     *       when a store is set, its password, since without them every
     *       vendor handshake fails too);</li>
     *   <li>{@code %all%} (any case) for the protocol or cipher list means the
     *       JRE defaults of an {@code SSLContext} for {@code protocol}; any
     *       other value is trimmed and split on commas; when {@code fips},
     *       cipher suites starting {@code TLS_RSA} are removed;</li>
     *   <li>{@code truststore} and {@code keystore} paths have {@code %VAR%}
     *       then {@code $VAR} replaced from the environment, then system
     *       properties (unresolved names stay as written);</li>
     *   <li>a password is {@code <key>.encrypted} (any prefix, decrypted)
     *       before {@code <key>} (any prefix); the value
     *       {@code %truststore_password%} / {@code %keystore_password%} (any
     *       case) redirects to {@code storePass.properties}
     *       {@code ssltruststorePassword} / {@code sslkeystorePassword}, read
     *       {@code .encrypted} first ({@code CryptUtils.readPasswordProperty}).</li>
     * </ul>
     * Error messages name file, key and the exception class, never a value.
     *
     * @param fips whether {@code IS_FIPS} is true ({@code SSLOptions.IS_FIPS}),
     *             which enables the {@code TLS_RSA} cipher filter
     */
    static ClusterSslOptions resolveClusterSslOptions(java.nio.file.Path sslDir, boolean fips,
            java.util.function.UnaryOperator<String> decryptor) throws java.io.IOException {
        java.nio.file.Path optionsFile = sslDir.resolve(SECURE_COMMUNICATIONS_FILE);
        java.nio.file.Path storePassFile = sslDir.resolve(STORE_PASS_FILE);
        java.util.Properties props = loadProperties(optionsFile, "cluster TLS options file");
        String protocol = requiredClusterProperty(props, optionsFile, "protocol");
        String storeType = requiredClusterProperty(props, optionsFile, "store_type");
        String algorithm = requiredClusterProperty(props, optionsFile, "algorithm");
        String keystore = clusterProperty(props, "keystore");
        String truststore = clusterProperty(props, "truststore");
        String cipherList = requiredClusterProperty(props, optionsFile, "supported_cipher_suites");
        String protocolList = requiredClusterProperty(props, optionsFile, "supported_protocols");
        boolean allCiphers = cipherList.equalsIgnoreCase(ALL_JRE_KEYWORD);
        boolean allProtocols = protocolList.equalsIgnoreCase(ALL_JRE_KEYWORD);
        javax.net.ssl.SSLParameters jre = (allCiphers || allProtocols)
                ? jreDefaultSslParameters(protocol, optionsFile) : null;
        String[] ciphers = filterRestrictedCiphers(
                allCiphers ? jre.getCipherSuites() : cipherList.trim().split("\\s*,\\s*"), fips);
        String[] protocols = allProtocols ? jre.getProtocols()
                : protocolList.trim().split("\\s*,\\s*");
        if (truststore != null) {
            truststore = replacePathEnvVars(truststore);
        }
        if (keystore != null) {
            keystore = replacePathEnvVars(keystore);
        }
        String keystorePassword = clusterPasswordProperty(props, optionsFile, "keystore_password",
                decryptor);
        String truststorePassword = clusterPasswordProperty(props, optionsFile,
                "truststore_password", decryptor);
        boolean keystoreRedirect = keystorePassword != null
                && keystorePassword.equalsIgnoreCase(KEYSTORE_PASSWORD_SENTINEL);
        boolean truststoreRedirect = truststorePassword != null
                && truststorePassword.equalsIgnoreCase(TRUSTSTORE_PASSWORD_SENTINEL);
        if (keystoreRedirect || truststoreRedirect) {
            java.util.Properties storePass = loadProperties(storePassFile,
                    "cluster store password file");
            if (keystoreRedirect) {
                keystorePassword = storePassProperty(storePass, storePassFile,
                        STORE_PASS_KEYSTORE_KEY, decryptor);
            }
            if (truststoreRedirect) {
                truststorePassword = storePassProperty(storePass, storePassFile,
                        STORE_PASS_TRUSTSTORE_KEY, decryptor);
            }
        }
        if (truststore == null) {
            throw new java.io.IOException("cluster TLS options file " + optionsFile
                    + " has no truststore key under " + CLUSTER_PROPERTY_PREFIXES
                    + " (the vendor would trust nothing)");
        }
        if (truststorePassword == null) {
            throw new java.io.IOException("no truststore password resolved for truststore "
                    + truststore + " (truststore_password[.encrypted] in " + optionsFile
                    + (truststoreRedirect ? ", then " + STORE_PASS_TRUSTSTORE_KEY
                            + "[.encrypted] in " + storePassFile : "") + ")");
        }
        if (keystore != null && keystorePassword == null) {
            throw new java.io.IOException("no keystore password resolved for keystore "
                    + keystore + " (from " + optionsFile + ")");
        }
        return new ClusterSslOptions(optionsFile, storePassFile, protocol, storeType, algorithm,
                truststore, truststorePassword, keystore, keystorePassword, protocols, ciphers);
    }

    /**
     * Build the socket factory the vendor {@code vROpsSSLSocketFactory} builds
     * from these options: truststore loaded as {@code store_type}, trust
     * managers from {@code TrustManagerFactory(algorithm)}, optional client
     * keystore loaded as {@code KeyStore.getDefaultType()} with key managers
     * from {@code KeyManagerFactory(algorithm)}, {@code SSLContext(protocol)},
     * and every socket restricted to the configured protocols and cipher
     * suites ({@link RestrictedSslSocketFactory}).
     */
    static javax.net.ssl.SSLSocketFactory buildClusterSocketFactory(ClusterSslOptions o)
            throws java.io.IOException {
        javax.net.ssl.SSLContext ctx = clusterTruststoreSslContext(o);
        return new RestrictedSslSocketFactory(ctx.getSocketFactory(),
                o.supportedProtocols, o.supportedCipherSuites);
    }

    /** The {@link javax.net.ssl.SSLContext} part of {@link #buildClusterSocketFactory}. */
    static javax.net.ssl.SSLContext clusterTruststoreSslContext(ClusterSslOptions o)
            throws java.io.IOException {
        java.nio.file.Path trustStorePath = java.nio.file.Paths.get(o.truststore);
        String storeType = o.storeType;
        java.security.KeyStore trustStore;
        try {
            trustStore = java.security.KeyStore.getInstance(storeType);
        } catch (java.security.KeyStoreException e) {
            throw new java.io.IOException("keystore type " + storeType
                    + " is not available in this JVM, cannot open cluster truststore "
                    + trustStorePath + " (store_type from " + o.optionsFile + "): "
                    + e.getClass().getName(), e);
        }
        loadStore(trustStore, trustStorePath, o.truststorePassword, "cluster truststore",
                storeType);
        javax.net.ssl.KeyManager[] keyManagers = null;
        try {
            javax.net.ssl.TrustManagerFactory tmf =
                    javax.net.ssl.TrustManagerFactory.getInstance(o.algorithm);
            tmf.init(trustStore);
            if (o.keystore != null) {
                java.nio.file.Path keyStorePath = java.nio.file.Paths.get(o.keystore);
                java.security.KeyStore keyStore =
                        java.security.KeyStore.getInstance(java.security.KeyStore.getDefaultType());
                loadStore(keyStore, keyStorePath, o.keystorePassword, "cluster keystore",
                        java.security.KeyStore.getDefaultType());
                javax.net.ssl.KeyManagerFactory kmf =
                        javax.net.ssl.KeyManagerFactory.getInstance(o.algorithm);
                char[] keyPassword = o.keystorePassword.toCharArray();
                try {
                    kmf.init(keyStore, keyPassword);
                } finally {
                    java.util.Arrays.fill(keyPassword, '\0');
                }
                keyManagers = kmf.getKeyManagers();
            }
            javax.net.ssl.SSLContext ctx = javax.net.ssl.SSLContext.getInstance(o.protocol);
            ctx.init(keyManagers, tmf.getTrustManagers(), null);
            return ctx;
        } catch (java.security.GeneralSecurityException e) {
            throw new java.io.IOException("could not build a TLS context (protocol "
                    + o.protocol + ", algorithm " + o.algorithm + ") from cluster truststore "
                    + trustStorePath + " and " + o.optionsFile + ": " + e.getClass().getName(), e);
        }
    }

    private static void loadStore(java.security.KeyStore store, java.nio.file.Path path,
            String password, String what, String type) throws java.io.IOException {
        if (!java.nio.file.Files.isRegularFile(path) || !java.nio.file.Files.isReadable(path)) {
            throw new java.io.IOException(what + " " + path + " is missing or not readable");
        }
        char[] chars = password.toCharArray();
        try (java.io.InputStream in = java.nio.file.Files.newInputStream(path)) {
            store.load(in, chars);
        } catch (java.io.IOException | java.security.GeneralSecurityException e) {
            throw new java.io.IOException("could not load " + what + " " + path + " as " + type
                    + " with the resolved password: " + e.getClass().getName(), e);
        } finally {
            java.util.Arrays.fill(chars, '\0');
        }
    }

    private static java.util.Properties loadProperties(java.nio.file.Path path, String what)
            throws java.io.IOException {
        if (!java.nio.file.Files.isRegularFile(path) || !java.nio.file.Files.isReadable(path)) {
            throw new java.io.IOException(what + " " + path + " is missing or not readable");
        }
        java.util.Properties props = new java.util.Properties();
        try (java.io.InputStream in = java.nio.file.Files.newInputStream(path)) {
            props.load(in);
        } catch (java.io.IOException | IllegalArgumentException e) {
            // IllegalArgumentException: malformed unicode escape in the file.
            throw new java.io.IOException("could not read " + what + " " + path + ": "
                    + e.getClass().getName(), e);
        }
        return props;
    }

    /** {@code SSLOptions.readProperty(..., optional=true)}: first prefix that has the key, else null. */
    static String clusterProperty(java.util.Properties props, String key) {
        for (String prefix : CLUSTER_PROPERTY_PREFIXES) {
            String value = props.getProperty(prefix + "." + key);
            if (value != null) {
                return value;
            }
        }
        return null;
    }

    private static String requiredClusterProperty(java.util.Properties props,
            java.nio.file.Path file, String key) throws java.io.IOException {
        String value = clusterProperty(props, key);
        if (value == null) {
            throw new java.io.IOException("cluster TLS options file " + file + " has no " + key
                    + " under " + CLUSTER_PROPERTY_PREFIXES + " (required by the vendor)");
        }
        return value;
    }

    /** {@code SSLOptions.readPasswordProperty}: {@code <key>.encrypted} (decrypted) first, then {@code <key>}. */
    private static String clusterPasswordProperty(java.util.Properties props,
            java.nio.file.Path file, String key,
            java.util.function.UnaryOperator<String> decryptor) throws java.io.IOException {
        String encrypted = clusterProperty(props, key + ENCRYPTED_KEY_SUFFIX);
        if (encrypted != null) {
            return decrypt(decryptor, encrypted, key + ENCRYPTED_KEY_SUFFIX, file);
        }
        return clusterProperty(props, key);
    }

    /** {@code CryptUtils.readPasswordProperty}: {@code <key>.encrypted} (decrypted) first, then {@code <key>}. */
    private static String storePassProperty(java.util.Properties props, java.nio.file.Path file,
            String key, java.util.function.UnaryOperator<String> decryptor)
            throws java.io.IOException {
        String encrypted = props.getProperty(key + ENCRYPTED_KEY_SUFFIX);
        if (encrypted != null) {
            return decrypt(decryptor, encrypted, key + ENCRYPTED_KEY_SUFFIX, file);
        }
        // Null when neither key is present, as CryptUtils returns; the caller
        // fails only if the store that needs this password is configured.
        return props.getProperty(key);
    }

    private static String decrypt(java.util.function.UnaryOperator<String> decryptor,
            String encrypted, String key, java.nio.file.Path file) throws java.io.IOException {
        String decrypted;
        try {
            decrypted = decryptor.apply(encrypted);
        } catch (RuntimeException | LinkageError e) {
            throw new java.io.IOException("could not decrypt " + key + " from " + file
                    + " with the platform Crypt: " + e.getClass().getName());
        }
        if (decrypted == null) {
            throw new java.io.IOException("decrypting " + key + " from " + file
                    + " returned no value");
        }
        return decrypted;
    }

    /** {@code SSLOptions.filterRestrictedCiphers}: in FIPS mode drop suites starting {@code TLS_RSA}. */
    static String[] filterRestrictedCiphers(String[] ciphers, boolean fips) {
        if (!fips) {
            return ciphers;
        }
        return java.util.Arrays.stream(ciphers).filter(c -> !c.startsWith("TLS_RSA"))
                .toArray(String[]::new);
    }

    private static javax.net.ssl.SSLParameters jreDefaultSslParameters(String protocol,
            java.nio.file.Path file) throws java.io.IOException {
        try {
            javax.net.ssl.SSLContext ctx = javax.net.ssl.SSLContext.getInstance(protocol);
            ctx.init(null, null, null);
            return ctx.getDefaultSSLParameters();
        } catch (java.security.GeneralSecurityException e) {
            throw new java.io.IOException("could not read JRE default protocols and cipher "
                    + "suites for protocol " + protocol + " (from " + file + "): "
                    + e.getClass().getName(), e);
        }
    }

    /**
     * {@code SSLOptions.replacePathEnvVars}: replace {@code %NAME%} then
     * {@code $NAME} with the variable's value (environment, then system
     * property). Matches are found on the input string; unresolved names are
     * left as written.
     */
    static String replacePathEnvVars(String path) {
        String out = replacePattern(path, java.util.regex.Pattern.compile("%(\\w+)%"));
        return replacePattern(out, java.util.regex.Pattern.compile("\\$(\\w+)"));
    }

    private static String replacePattern(String input, java.util.regex.Pattern pattern) {
        String out = input;
        java.util.regex.Matcher m = pattern.matcher(input);
        while (m.find()) {
            String value = readEnvVarValue(m.group(1));
            if (value != null) {
                out = out.replace(m.group(), value);
            }
        }
        return out;
    }

    /** {@code SSLOptions.readEnvVarValue}: environment variable, else system property. */
    static String readEnvVarValue(String name) {
        String value = System.getenv(name);
        return value != null ? value : System.getProperty(name);
    }

    /**
     * Socket factory that restricts every socket to the configured protocols
     * and cipher suites, as {@code vROpsSSLSocketFactory.prepareSocket} does:
     * enabled = supported by the socket intersected with the configured list
     * (an empty intersection is applied as is, and the handshake fails).
     */
    static final class RestrictedSslSocketFactory extends javax.net.ssl.SSLSocketFactory {
        private final javax.net.ssl.SSLSocketFactory delegate;
        private final List<String> protocols;
        private final List<String> cipherSuites;

        RestrictedSslSocketFactory(javax.net.ssl.SSLSocketFactory delegate, String[] protocols,
                String[] cipherSuites) {
            this.delegate = delegate;
            this.protocols = protocols == null ? null : java.util.Arrays.asList(protocols.clone());
            this.cipherSuites = cipherSuites == null ? null
                    : java.util.Arrays.asList(cipherSuites.clone());
        }

        private java.net.Socket prepare(java.net.Socket socket) {
            javax.net.ssl.SSLSocket ssl = (javax.net.ssl.SSLSocket) socket;
            if (protocols != null) {
                ssl.setEnabledProtocols(intersect(ssl.getSupportedProtocols(), protocols));
            }
            if (cipherSuites != null) {
                ssl.setEnabledCipherSuites(intersect(ssl.getSupportedCipherSuites(), cipherSuites));
            }
            return ssl;
        }

        private static String[] intersect(String[] supported, List<String> allowed) {
            java.util.Set<String> set = new java.util.LinkedHashSet<>(java.util.Arrays.asList(supported));
            set.retainAll(allowed);
            return set.toArray(new String[0]);
        }

        @Override
        public String[] getDefaultCipherSuites() {
            return delegate.getDefaultCipherSuites();
        }

        @Override
        public String[] getSupportedCipherSuites() {
            return delegate.getSupportedCipherSuites();
        }

        @Override
        public java.net.Socket createSocket(java.net.Socket s, String host, int port,
                boolean autoClose) throws java.io.IOException {
            return prepare(delegate.createSocket(s, host, port, autoClose));
        }

        @Override
        public java.net.Socket createSocket(String host, int port) throws java.io.IOException {
            return prepare(delegate.createSocket(host, port));
        }

        @Override
        public java.net.Socket createSocket(String host, int port, java.net.InetAddress localHost,
                int localPort) throws java.io.IOException {
            return prepare(delegate.createSocket(host, port, localHost, localPort));
        }

        @Override
        public java.net.Socket createSocket(java.net.InetAddress host, int port)
                throws java.io.IOException {
            return prepare(delegate.createSocket(host, port));
        }

        @Override
        public java.net.Socket createSocket(java.net.InetAddress address, int port,
                java.net.InetAddress localAddress, int localPort) throws java.io.IOException {
            return prepare(delegate.createSocket(address, port, localAddress, localPort));
        }
    }

    /**
     * Per-adapter-instance cache of the FIPS socket factory. The vendor
     * resolves {@code SSLOptions} once per JVM and rebuilds its socket factory
     * when the truststore's modification time moves; this cache resolves once
     * per instance and rebuilds when the modification time or size of any
     * input changes ({@code secure-communications.properties},
     * {@code storePass.properties}, the truststore, the keystore). Reusing one
     * factory also lets {@code HttpsURLConnection} keep-alive reuse
     * connections. Failures are not cached: the next call retries.
     */
    static final class ClusterSocketFactoryCache {
        private java.nio.file.Path cachedDir;
        private String inputsFingerprint;
        private ClusterSslOptions options;
        private String storesFingerprint;
        private javax.net.ssl.SSLSocketFactory factory;
        private int builds;

        synchronized javax.net.ssl.SSLSocketFactory get(java.nio.file.Path sslDir, boolean fips,
                java.util.function.UnaryOperator<String> decryptor) throws java.io.IOException {
            String inputs = fingerprint(sslDir.resolve(SECURE_COMMUNICATIONS_FILE),
                    sslDir.resolve(STORE_PASS_FILE));
            if (options == null || !sslDir.equals(cachedDir) || !inputs.equals(inputsFingerprint)) {
                options = null;
                factory = null;
                options = resolveClusterSslOptions(sslDir, fips, decryptor);
                cachedDir = sslDir;
                inputsFingerprint = inputs;
            }
            String stores = fingerprint(java.nio.file.Paths.get(options.truststore),
                    options.keystore == null ? null : java.nio.file.Paths.get(options.keystore));
            if (factory == null || !stores.equals(storesFingerprint)) {
                factory = null;
                factory = buildClusterSocketFactory(options);
                storesFingerprint = stores;
                builds++;
            }
            return factory;
        }

        /** Number of factory builds so far (test hook). */
        synchronized int buildCount() {
            return builds;
        }

        private static String fingerprint(java.nio.file.Path... paths) {
            StringBuilder sb = new StringBuilder();
            for (java.nio.file.Path p : paths) {
                if (p == null) {
                    sb.append("-|");
                    continue;
                }
                try {
                    sb.append(p).append('@')
                            .append(java.nio.file.Files.getLastModifiedTime(p).toMillis())
                            .append(':').append(java.nio.file.Files.size(p)).append('|');
                } catch (java.io.IOException | RuntimeException e) {
                    sb.append(p).append("@absent|");
                }
            }
            return sb.toString();
        }
    }

    /**
     * Decrypt a store password with the SDK's
     * {@code com.integrien.alive.common.security.Crypt}, which delegates to
     * {@code com.vmware.vcops.security.Crypt.getDefaultCrypt().decrypt}, the
     * same call as the vendor's {@code Crypt.dec} (and the same class
     * {@code AmbientCredential} already uses). Only resolvable on a collector,
     * where the delegate is on the classpath.
     */
    @SuppressWarnings("deprecation")
    private static String decryptWithPlatformCrypt(String encrypted) {
        return com.integrien.alive.common.security.Crypt.getDefaultCrypt().decrypt(encrypted);
    }

    /**
     * Whether the collector runs in FIPS mode, detected exactly as the vendor
     * {@code Constants.FIPS_MODE_ENABLED} does:
     * {@code Boolean.valueOf(System.getenv("IS_FIPS"))}.
     */
    static boolean isFipsModeEnabled() {
        return isFipsModeEnabled(System.getenv(FIPS_ENV_VAR));
    }

    /** {@link #isFipsModeEnabled()} on a given {@code IS_FIPS} value ({@code Boolean.valueOf} semantics). */
    static boolean isFipsModeEnabled(String isFipsValue) {
        return Boolean.parseBoolean(isFipsValue);
    }

    /**
     * The cluster SSL directory, as {@code SSLOptions.<clinit>}:
     * {@code STORAGE} (environment, then system property) resolved with
     * {@code vcops/user/conf/ssl}.
     *
     * @throws java.io.IOException if {@code STORAGE} is unset (the vendor then
     *         finds no options file and trusts nothing)
     */
    static java.nio.file.Path clusterSslDirectory() throws java.io.IOException {
        return clusterSslDirectory(readEnvVarValue(STORAGE_VAR));
    }

    /** {@link #clusterSslDirectory()} on a given {@code STORAGE} value. */
    static java.nio.file.Path clusterSslDirectory(String storage) throws java.io.IOException {
        if (storage == null) {
            throw new java.io.IOException("STORAGE is not set (environment or system property), "
                    + "so the cluster TLS options file $STORAGE/vcops/user/conf/ssl/"
                    + SECURE_COMMUNICATIONS_FILE + " cannot be located");
        }
        try {
            return java.nio.file.Paths.get(storage, "vcops", "user", "conf", "ssl");
        } catch (java.nio.file.InvalidPathException e) {
            throw new java.io.IOException("STORAGE value is not a valid path: "
                    + e.getClass().getName(), e);
        }
    }

    /** The options file path for the mode line, or why it cannot be located. */
    private static String describeClusterSslDirectory() {
        try {
            return clusterSslDirectory().resolve(SECURE_COMMUNICATIONS_FILE).toString();
        } catch (java.io.IOException e) {
            return "<unresolved: " + e.getMessage() + ">";
        }
    }

    /**
     * The once-per-instance transport mode line: which signal fired and what
     * transport follows from it.
     *
     * @param fips         result of {@link #isFipsModeEnabled()}
     * @param optionsFile  FIPS only: the {@code secure-communications.properties}
     *                     path, or why it is unresolved; ignored when not FIPS
     * @param approvedOnly raw {@code org.bouncycastle.fips.approved_only}
     *                     property value, printed as a diagnostic only
     */
    static String describeTransportMode(boolean fips, String optionsFile, String approvedOnly) {
        String diagnostic = " Diagnostic only, not a mode signal: "
                + "org.bouncycastle.fips.approved_only=" + approvedOnly + ".";
        if (fips) {
            return "VcfCfAdapter.openPlatformConnection: Suite API transport mode=FIPS "
                    + "(signal: environment variable IS_FIPS=true, the vendor SuiteAPIClient "
                    + "switch). Chain verified with the cluster TLS options from " + optionsFile
                    + " (category inter_cluster, then default), hostname ignored." + diagnostic
                    + " (Logged once per adapter instance.)";
        }
        return "VcfCfAdapter.openPlatformConnection: Suite API transport mode=non-FIPS "
                + "(signal: environment variable IS_FIPS is not true). Trust-all, hostname "
                + "ignored, as the vendor SuiteAPIClient." + diagnostic
                + " (Logged once per adapter instance.)";
    }

    /**
     * Build an insecure (trust-all, hostname-check-off) {@link javax.net.ssl.SSLContext}.
     *
     * <p><strong>Disables both certificate chain validation AND hostname
     * verification.</strong> Use ONLY in lab / dev environments with
     * self-signed certificates or where the certificate name does not match
     * the address the admin configured. Do not use as the default path. In
     * production adapters use {@link #getPlatformSslContext()} instead. Do
     * NOT use this for the loopback Suite API transport. Use
     * {@link #openPlatformConnection(String)} instead.
     *
     * <p><strong>Implementation note (why the trust manager type matters, and
     * on which transports).</strong> A legacy {@link javax.net.ssl.X509TrustManager}
     * gets silently wrapped by JSSE in {@code sun.security.ssl.AbstractTrustManagerWrapper},
     * which re-applies an endpoint identity (hostname) check on top of whatever
     * the wrapped {@code checkServerTrusted} decides. So a trust-all
     * {@code X509TrustManager} alone does NOT suppress hostname mismatches (see
     * issue #82). Implementing {@link javax.net.ssl.X509ExtendedTrustManager}
     * here (with no-op {@code Socket}/{@code SSLEngine} overloads) makes JSSE
     * use the manager directly instead of wrapping it, so the hostname check
     * never runs.
     *
     * <p>This is <strong>not</strong> limited to {@code java.net.http.HttpClient}.
     * It also disables hostname verification on the
     * {@link javax.net.ssl.HttpsURLConnection} transport, including for a
     * caller that sets the JDK's own default {@link javax.net.ssl.HostnameVerifier}
     * (i.e. never calls {@code setHostnameVerifier} at all, or does and passes
     * the platform default): {@code HttpsURLConnection}'s underlying
     * {@code HttpsClient} sets an endpoint identification algorithm on the
     * socket whenever the verifier in effect is the default one. At that
     * point JSSE, not the {@code HostnameVerifier}, decides the outcome, and
     * this extended trust manager no-ops that decision the same way it does for
     * {@code HttpClient}. Measured: an insecure-factory connection against a
     * hostname-mismatched cert, using the default {@code HostnameVerifier},
     * fails before this fix and succeeds after it. A caller that wants
     * "trust-all but still enforce hostname" must set its own
     * {@code HostnameVerifier} explicitly on the {@code HttpsURLConnection}.
     * This context supplies no such enforcement on its own, on either
     * transport.
     *
     * @return an SSLContext that trusts all certificates and skips hostname
     *         verification on both {@code java.net.http.HttpClient} and
     *         {@code HttpsURLConnection}, without validation
     * @throws RuntimeException if context construction fails
     */
    public static javax.net.ssl.SSLContext insecureSslContext() {
        try {
            javax.net.ssl.SSLContext ctx = javax.net.ssl.SSLContext.getInstance("TLS");
            ctx.init(null, new javax.net.ssl.TrustManager[]{
                new javax.net.ssl.X509ExtendedTrustManager() {
                    public java.security.cert.X509Certificate[] getAcceptedIssuers() {
                        return new java.security.cert.X509Certificate[0];
                    }
                    public void checkClientTrusted(
                            java.security.cert.X509Certificate[] c, String a) {}
                    public void checkServerTrusted(
                            java.security.cert.X509Certificate[] c, String a) {}
                    public void checkClientTrusted(
                            java.security.cert.X509Certificate[] c, String a,
                            java.net.Socket socket) {}
                    public void checkServerTrusted(
                            java.security.cert.X509Certificate[] c, String a,
                            java.net.Socket socket) {}
                    public void checkClientTrusted(
                            java.security.cert.X509Certificate[] c, String a,
                            javax.net.ssl.SSLEngine engine) {}
                    public void checkServerTrusted(
                            java.security.cert.X509Certificate[] c, String a,
                            javax.net.ssl.SSLEngine engine) {}
                }
            }, null);
            return ctx;
        } catch (Exception e) {
            throw new RuntimeException(
                    "VcfCfAdapter: failed to build insecure SSL context", e);
        }
    }

    // -----------------------------------------------------------------------
    // Certificate review (VCF Ops "Review and accept certificate" flow)
    // -----------------------------------------------------------------------

    /**
     * Identifier key, by framework convention, for the per-instance
     * "Allow Insecure SSL" setting in {@code describe.xml}. Read it with
     * {@link #isAllowInsecure(ResourceConfig)}.
     */
    public static final String ALLOW_INSECURE_IDENTIFIER = "allowInsecure";

    /**
     * Target endpoints whose TLS certificate VCF Operations should review when
     * the admin clicks Validate Connection. Default: empty, which keeps the
     * platform's certificate check at {@code NOT_SUPPORTED} (the behaviour of
     * every framework adapter before this hook existed).
     *
     * <h4>What returning URLs turns on</h4>
     * <p>On Validate Connection the platform calls
     * {@code checkCertificate} before {@code test()}. The SDK's default
     * {@code onCheckCertificate} opens each URL returned here through the
     * platform's own {@code HttpsConnection} over the instance
     * {@code CustomTrustManager}. An untrusted chain comes back to the UI as the
     * "Review and accept certificate" dialog and {@code test()} is not called
     * until the admin accepts it. Accepted certificates are stored on the
     * adapter instance ({@code ResourceConfig.getTrustedCertificates()}) and
     * loaded into the same {@code CustomTrustManager} that
     * {@link #getPlatformSslContext()} and
     * {@code HttpClientBuilder.platformSsl(this)} use, so collection trusts
     * them with no transport change.
     *
     * <p>These URLs are deliberately NOT returned from
     * {@code getCertificateRenewalUrls()} (the SDK default {@code null} stays):
     * the collector's renewal handler speaks a VCF-component protocol (signed
     * {@code jwt_token} JSON) that third-party targets do not serve, and each
     * attempt costs a throwaway {@code configure()} plus a GET to the target.
     * See {@code knowledge/context/tier2_architecture.md}, SSL section.
     *
     * <h4>Contract (read before overriding)</h4>
     * <ul>
     *   <li><strong>Called on an UNSAVED config.</strong> During Validate
     *       Connection the instance has not been saved and
     *       {@link #configureAdapter} has not run for these values. Derive every
     *       URL from {@code config} (identifiers via
     *       {@link #getIdentifier(ResourceConfig, String)}), never from
     *       {@link #config}, {@link #httpClient}, or any other instance field.
     *       The platform also calls this on the running instance (the
     *       collector's certificate-chain task), again with the config it
     *       passes in.</li>
     *   <li>Return {@code https://host:port} for every endpoint the adapter
     *       dials with {@link #getPlatformSslContext()}. Host and port must be
     *       the ones the client actually connects to, or the accepted
     *       certificate will not be the one presented at collection time.</li>
     *   <li>Return an empty list when the instance opted out of verification
     *       (see {@link #isAllowInsecure(ResourceConfig)}); there is nothing to
     *       review when the adapter trusts everything.</li>
     *   <li>Return an empty list when a required identifier (host) is blank;
     *       the tester reports the missing field.</li>
     *   <li>Do not do I/O here and do not throw. A thrown
     *       {@link RuntimeException} or {@link LinkageError} is logged and
     *       treated as "no URLs".</li>
     * </ul>
     *
     * <pre>{@code
     * @Override
     * protected List<String> certificateCheckUrls(ResourceConfig rc) {
     *     String host = getIdentifier(rc, "host");
     *     if (host == null || host.isBlank() || isAllowInsecure(rc)) return List.of();
     *     return List.of("https://" + host.trim() + ":443");
     * }
     * }</pre>
     *
     * @param config the adapter-instance resource config handed in by the
     *        platform (possibly unsaved); never {@code null} when called by the
     *        framework
     * @return the URLs to review; empty (default) to leave the platform check
     *         off. {@code null} is treated as empty.
     */
    protected List<String> certificateCheckUrls(ResourceConfig config) {
        return Collections.emptyList();
    }

    /**
     * {@inheritDoc}
     *
     * <p>Returns {@link #certificateCheckUrls(ResourceConfig)} for the passed
     * config's adapter-instance resource. When that is empty, delegates to
     * {@code super.getConnectionURLs}, so an adapter that does not override the
     * hook behaves exactly as before (the SDK default yields
     * {@code NOT_SUPPORTED}).
     *
     * <p>This method does not itself look at Allow Insecure SSL or at any
     * identifier. Returning no URLs for an insecure or incomplete config is the
     * hook's job (see the contract on
     * {@link #certificateCheckUrls(ResourceConfig)}); whatever the hook
     * returns, after trimming and de-duplication, is what the platform probes.
     */
    @Override
    public List<String> getConnectionURLs(AdapterConfig adapterConfig) {
        List<String> urls = declaredCertificateUrls(adapterConfig);
        if (urls.isEmpty()) {
            return super.getConnectionURLs(adapterConfig);
        }
        return urls;
    }

    /**
     * Resolve {@link #certificateCheckUrls(ResourceConfig)} for an
     * {@link AdapterConfig}: null-safe, trims entries, drops null/blank ones,
     * de-duplicates in order, and turns a hook {@link RuntimeException} or
     * {@link LinkageError} into "no URLs" (logged). Never returns {@code null}.
     */
    final List<String> declaredCertificateUrls(AdapterConfig adapterConfig) {
        if (adapterConfig == null) {
            return Collections.emptyList();
        }
        ResourceConfig rc = adapterConfig.getAdapterInstResource();
        if (rc == null) {
            return Collections.emptyList();
        }
        List<String> raw;
        try {
            raw = certificateCheckUrls(rc);
        } catch (RuntimeException | LinkageError e) {
            logWarnSafe("certificateCheckUrls threw; treating as no certificate URLs: "
                    + e, e);
            return Collections.emptyList();
        }
        return normalizeUrls(raw);
    }

    /** Trim, drop null/blank, de-duplicate preserving order. Never null. */
    static List<String> normalizeUrls(List<String> raw) {
        if (raw == null || raw.isEmpty()) {
            return Collections.emptyList();
        }
        LinkedHashSet<String> out = new LinkedHashSet<>();
        for (String u : raw) {
            if (u == null) continue;
            String t = u.trim();
            if (!t.isEmpty()) out.add(t);
        }
        return out.isEmpty() ? Collections.<String>emptyList()
                : Collections.unmodifiableList(new ArrayList<>(out));
    }

    /**
     * Parse an "Allow Insecure SSL" value, strict form. {@code "true"}
     * (case-insensitive, surrounding whitespace ignored) means insecure;
     * anything else, including {@code null} and blank, means validate
     * certificates.
     *
     * <p>Reads both storage shapes: the legacy free-text identifier and the
     * {@code enum="true"} pulldown ({@code true} / {@code false}). An existing
     * instance keeps its stored string across the describe.xml change.
     *
     * <p><strong>Exact difference from the legacy
     * {@code "true".equalsIgnoreCase(v)} parse</strong> (compliance, unifi,
     * the vcommunity paks, the template): the legacy parse does not trim, so a
     * stored {@code "true"} with surrounding whitespace ({@code " true"},
     * {@code "TRUE "}) is secure today and insecure here. Every other stored
     * value parses identically. For the "anything but false" legacy parse
     * (synology) use {@link #parseAllowInsecureLegacyNotFalse(String)}.
     *
     * @param raw the stored identifier value
     * @return {@code true} only for a trimmed, case-insensitive {@code "true"}
     */
    public static boolean parseAllowInsecure(String raw) {
        return raw != null && "true".equalsIgnoreCase(raw.trim());
    }

    /**
     * Parse an "Allow Insecure SSL" value with the "anything but false is
     * insecure" legacy meaning, bit for bit:
     * {@code !"false".equalsIgnoreCase(raw)}, untrimmed. {@code null}, blank,
     * {@code "yes"}, {@code "1"}, {@code " false"} and {@code "true"} are all
     * insecure; only an exact, case-insensitive {@code "false"} validates.
     *
     * <p>For a pak whose shipped parse was this one (synology) and which must
     * keep every stored value meaning exactly what it means today. With the
     * pulldown in place, new instances only ever store {@code "true"} or
     * {@code "false"}, which both parsers read the same way. Switching such a
     * pak to {@link #parseAllowInsecure(String)} instead flips these stored
     * values from insecure to secure: {@code null}, blank or whitespace-only,
     * {@code "false"} with surrounding whitespace, and any other non-"true"
     * text ({@code "yes"}, {@code "1"}, ...).
     *
     * @param raw the stored identifier value
     * @return {@code false} only for an exact, case-insensitive {@code "false"}
     */
    public static boolean parseAllowInsecureLegacyNotFalse(String raw) {
        return !"false".equalsIgnoreCase(raw);
    }

    /**
     * Read the {@link #ALLOW_INSECURE_IDENTIFIER} identifier from {@code rc} and
     * parse it with {@link #parseAllowInsecure(String)}. Safe on an unsaved
     * config; {@code null} config is secure.
     *
     * @param rc the adapter-instance resource config (may be unsaved)
     * @return {@code true} only when the instance explicitly opted out
     */
    protected boolean isAllowInsecure(ResourceConfig rc) {
        if (rc == null) {
            return false;
        }
        return parseAllowInsecure(getIdentifier(rc, ALLOW_INSECURE_IDENTIFIER));
    }

    /**
     * As {@link #isAllowInsecure(ResourceConfig)}, but parses with
     * {@link #parseAllowInsecureLegacyNotFalse(String)} (absent identifier and
     * blank are insecure). Use only in a pak whose legacy parse was
     * {@code !"false".equalsIgnoreCase(v)}. A {@code null} config is still
     * reported secure, since there is nothing to read.
     *
     * @param rc the adapter-instance resource config (may be unsaved)
     * @return {@code false} only when the stored value is exactly "false"
     */
    protected boolean isAllowInsecureLegacyNotFalse(ResourceConfig rc) {
        if (rc == null) {
            return false;
        }
        return parseAllowInsecureLegacyNotFalse(
                getIdentifier(rc, ALLOW_INSECURE_IDENTIFIER));
    }

    /**
     * Map a Test Connection failure to a readable message when its cause chain
     * shows the target's certificate chain was not trusted. Returns
     * {@code null} for any other failure so the caller keeps the raw message.
     *
     * <p>Detected (type-based, walking causes and suppressed exceptions, cycle
     * safe): {@code CustomTrustManager.CustomCertificateException} (the
     * platform trust manager's rejection, as in the prod
     * {@code certificate_unknown(46)} stack),
     * {@link java.security.cert.CertPathBuilderException} and
     * {@link java.security.cert.CertPathValidatorException} (JDK PKIX,
     * including {@code SunCertPathBuilderException}), plus the JDK's
     * {@code "PKIX path building failed"} / {@code "unable to find valid
     * certification path"} text for wrappers that drop the cause. A bare
     * {@code certificate_unknown} alert with none of these is NOT matched: that
     * can be the server rejecting us, which accepting a certificate would not fix.
     *
     * <p>The text points at the accept dialog (open the account, Validate
     * Connection, accept the certificate; enter the host by the name on its
     * certificate) and names Allow Insecure SSL only when
     * {@code allowInsecureField} says the pak's describe carries that field
     * (issue #205): a pak that removed it (compliance build 93) must not be
     * told to set it.
     *
     * @param failure            the exception thrown by the tester
     * @param promptAvailable    whether review URLs were declared for the tested
     *        config (so VCF Operations can offer the accept dialog). Not declared
     *        covers both a pack that does not implement the hook and an opted-in
     *        pack whose hook returned none (blank host, Allow Insecure true).
     * @param allowInsecureField whether the account's describe declares the
     *        {@link #ALLOW_INSECURE_IDENTIFIER} field
     * @return the readable message, or {@code null} if not a trust failure
     */
    static String certificateTrustFailureMessage(Throwable failure,
            boolean promptAvailable, boolean allowInsecureField) {
        Throwable hit = findCertificateTrustFailure(failure);
        if (hit == null) {
            return null;
        }
        String detail = hit.getMessage();
        if (detail == null || detail.isEmpty()) {
            detail = hit.getClass().getName();
        }
        StringBuilder m = new StringBuilder(
                "The target's TLS certificate is not trusted by this adapter instance. ");
        if (promptAvailable) {
            m.append("Open the account and click Validate Connection to review and "
                    + "accept the certificate when VCF Operations shows it. Enter the "
                    + "host by the name on its certificate: accepting a certificate "
                    + "does not fix a name mismatch.");
            if (allowInsecureField) {
                m.append(" To skip certificate validation (lab use only), set Allow "
                        + "Insecure SSL to true.");
            }
        } else {
            m.append("VCF Operations offered no certificate for review with these "
                    + "settings. Check that the host is filled in and entered by the "
                    + "name on its certificate, then open the account and click "
                    + "Validate Connection to accept the certificate. If no "
                    + "certificate is shown for review, this management pack version "
                    + "does not support certificate review; update to one that does.");
            if (allowInsecureField) {
                m.append(" If Allow Insecure SSL is already true there is nothing to "
                        + "review; set it to true only to skip certificate validation "
                        + "(lab use only).");
            }
        }
        return m.append(" Detail: ").append(detail).toString();
    }

    /**
     * Test Connection message hook for a certificate-trust failure (issue
     * #205). Called by {@link #onTest} only after the failure has been
     * classified as a trust failure (see
     * {@link #certificateTrustFailureMessage(Throwable, boolean, boolean)}),
     * with the framework's default text. Return the text the admin should see
     * in the Validate Connection error; {@code null} or blank keeps
     * {@code defaultMessage}. Anything thrown (other than
     * {@link VirtualMachineError}) is logged and the default is kept.
     *
     * <p>Default: returns {@code defaultMessage}. Override to give target
     * specific advice, for example a name mismatch versus an untrusted chain
     * ({@link com.vcfcf.adapter.http.CertificateNames#isNameMismatch}). The
     * returned text goes to the UI as is: keep credentials, session ids and
     * tokens out of it.
     *
     * @param failure        the exception the tester threw (full cause chain)
     * @param config         the adapter-instance config under test (possibly
     *                       unsaved), or {@code null} when the platform passed
     *                       none; derive everything from it, not from instance
     *                       state
     * @param defaultMessage the framework's text for this failure
     * @return the message to show, or {@code null} to keep the default
     */
    protected String certificateFailureMessage(Throwable failure, ResourceConfig config,
            String defaultMessage) {
        return defaultMessage;
    }

    /** {@link #certificateFailureMessage} with its failures contained. */
    @SuppressWarnings("deprecation") // ThreadDeath: deprecated in newer JDKs, still thrown
    final String certificateFailureMessageSafe(Throwable failure, ResourceConfig config,
            String defaultMessage) {
        String m;
        try {
            m = certificateFailureMessage(failure, config, defaultMessage);
        } catch (VirtualMachineError | ThreadDeath fatal) {
            throw fatal;
        } catch (Throwable t) {
            logWarnSafe("certificateFailureMessage threw; keeping the framework "
                    + "message: " + t, t);
            return defaultMessage;
        }
        return m == null || m.trim().isEmpty() ? defaultMessage : m;
    }

    /**
     * Whether this pak's describe declares the {@link #ALLOW_INSECURE_IDENTIFIER}
     * field on the adapter-instance kind of {@code config} (issue #205).
     * Decides whether Test Connection advice may name Allow Insecure SSL. The
     * describe, not the stored config, is the source: an account created
     * before a pak removed the field still carries its stored value.
     *
     * <p>Default: reads {@link #onDescribe()} once per adapter instance (the
     * result is cached) and looks for the identifier on the resource kind
     * whose key matches {@code config}'s. {@code false} when {@code config}
     * or its kind is missing, or the describe cannot be read. Override only
     * when the describe on disk is not what the admin sees.
     *
     * @param config the adapter-instance config under test (may be null)
     * @return {@code true} when the field is declared
     */
    protected boolean describesAllowInsecure(ResourceConfig config) {
        if (config == null || config.getResourceKey() == null) {
            return false;
        }
        String kind = config.getResourceKey().getResourceKind();
        if (kind == null) {
            return false;
        }
        AdapterDescribe d = describeForTestMessages;
        if (d == null) {
            d = onDescribe();
            describeForTestMessages = d;
        }
        if (d.getResourceKinds() == null) {
            return false;
        }
        for (com.integrien.alive.common.adapter3.describe.ResourceKindDescribe rk
                : d.getResourceKinds()) {
            if (rk == null || !kind.equals(rk.getKey())
                    || rk.getResourceIdentifiers() == null) {
                continue;
            }
            for (com.integrien.alive.common.adapter3.describe.ResourceIdentifierDescribe id
                    : rk.getResourceIdentifiers()) {
                if (id != null && ALLOW_INSECURE_IDENTIFIER.equals(id.getKey())) {
                    return true;
                }
            }
        }
        return false;
    }

    /** Cache for {@link #describesAllowInsecure}; the describe does not change in an instance's life. */
    private volatile AdapterDescribe describeForTestMessages;

    /** {@link #describesAllowInsecure}; anything thrown (but a VirtualMachineError) means no. */
    @SuppressWarnings("deprecation") // ThreadDeath: deprecated in newer JDKs, still thrown
    final boolean allowInsecureDescribedSafe(ResourceConfig config) {
        try {
            return describesAllowInsecure(config);
        } catch (VirtualMachineError | ThreadDeath fatal) {
            throw fatal;
        } catch (Throwable t) {
            logWarnSafe("Test Connection: could not read the describe for the Allow "
                    + "Insecure SSL field; the message will not mention it: " + t, t);
            return false;
        }
    }

    /** The adapter-instance config carried by {@code param}, or null. */
    static ResourceConfig testedResourceConfig(TestParam param) {
        if (param == null) return null;
        AdapterConfig ac = param.getAdapterConfig();
        return ac == null ? null : ac.getAdapterInstResource();
    }

    /**
     * Find the first trust-failure throwable in {@code t}'s cause and suppressed
     * graph, or {@code null}. See
     * {@link #certificateTrustFailureMessage(Throwable, boolean, boolean)}.
     */
    static Throwable findCertificateTrustFailure(Throwable t) {
        java.util.Set<Throwable> seen = java.util.Collections.newSetFromMap(
                new java.util.IdentityHashMap<>());
        java.util.ArrayDeque<Throwable> todo = new java.util.ArrayDeque<>();
        if (t != null) todo.add(t);
        Throwable textHit = null;
        while (!todo.isEmpty()) {
            Throwable cur = todo.poll();
            if (!seen.add(cur)) continue;
            if (cur instanceof CustomTrustManager.CustomCertificateException
                    || cur instanceof java.security.cert.CertPathBuilderException
                    || cur instanceof java.security.cert.CertPathValidatorException) {
                return cur;
            }
            String m = cur.getMessage();
            if (textHit == null && m != null
                    && (m.contains("PKIX path building failed")
                        || m.contains("unable to find valid certification path"))) {
                textHit = cur;
            }
            if (cur.getCause() != null) todo.add(cur.getCause());
            for (Throwable s : cur.getSuppressed()) {
                if (s != null) todo.add(s);
            }
        }
        return textHit;
    }

    /**
     * Whether review URLs are declared for the config under test. Anything the
     * pak's hook throws means "no prompt", so a broken hook cannot replace the
     * tester's own failure, except {@link VirtualMachineError} (out of memory,
     * stack overflow) and {@link ThreadDeath}, which are rethrown: the JVM or
     * thread is in no state to continue as if nothing happened.
     */
    @SuppressWarnings("deprecation") // ThreadDeath: deprecated in newer JDKs, still thrown
    final boolean certificatePromptAvailable(TestParam param) {
        try {
            return param != null
                    && !declaredCertificateUrls(param.getAdapterConfig()).isEmpty();
        } catch (VirtualMachineError | ThreadDeath fatal) {
            throw fatal;
        } catch (Throwable t) {
            logWarnSafe("certificateCheckUrls failed during Test Connection: " + t, t);
            return false;
        }
    }

    /** {@link #logWarn(String, Throwable)} that never throws (logger may be unavailable). */
    private void logWarnSafe(String message, Throwable t) {
        try {
            logWarn(message, t);
        } catch (RuntimeException | LinkageError ignored) {
            // Logging must not turn a certificate-URL lookup into a failure.
        }
    }

    // -----------------------------------------------------------------------
    // Credential and identifier helpers (unchanged from v1)
    // -----------------------------------------------------------------------

    /**
     * Read a credential field value from the adapter instance resource config.
     *
     * @param resourceConfig the adapter instance resource config
     * @param fieldKey       the credential field key (as declared in describe.xml)
     * @return the field value, or {@code null} if not found
     */
    protected String getCredentialField(ResourceConfig resourceConfig, String fieldKey) {
        CredentialConfig cred = resourceConfig.getResourceCredential();
        if (cred == null) return null;
        for (CredentialFieldConfig f : cred.getCredenialFields()) {
            if (fieldKey.equals(f.getKey())) {
                return f.getValue();
            }
        }
        return null;
    }

    /**
     * Read an identifier value from the adapter instance resource config.
     *
     * @param resourceConfig the adapter instance resource config
     * @param identifierKey  the identifier key (as declared in describe.xml)
     * @return the identifier value, or {@code null} if not found
     */
    protected String getIdentifier(ResourceConfig resourceConfig, String identifierKey) {
        for (ResourceIdentifierConfig id : resourceConfig.getResourceIdentifiers()) {
            if (identifierKey.equals(id.getKey())) {
                return id.getValue();
            }
        }
        return null;
    }

    // -----------------------------------------------------------------------
    // Data helpers
    // -----------------------------------------------------------------------

    /**
     * Push a numeric metric to the platform for the given resource, routed
     * through the dedup cache when available.
     *
     * <p>For string properties, use {@link #pushStringProperty(ResourceConfig,
     * String, String)}.
     *
     * @param rc    the resource config
     * @param key   the metric key (pipe-delimited group path, matches describe.xml)
     * @param value the numeric value
     * @param ts    the sample timestamp (epoch ms)
     */
    protected void pushMetric(ResourceConfig rc, String key, double value, long ts) {
        MetricData md = new MetricData(new MetricKey(key), ts, value);
        MetricDataCache cache = this.metricCache;
        if (cache != null) {
            cache.cacheMetricData(rc, md);
        } else {
            addMetricData(rc, md);
        }
    }

    /**
     * Push a string property to the platform for the given resource, routed
     * through the dedup cache when available.
     *
     * <p><strong>Always use this method for string properties.</strong>
     * {@code new MetricKey(key)} hardcodes {@code isProperty=false}; the
     * platform silently discards string values on non-property MetricKeys.
     * This helper uses {@code new MetricKey(true, key)} explicitly.
     *
     * @param rc    the resource config
     * @param key   the property key (pipe-delimited, matches describe.xml)
     * @param value the string value
     */
    protected void pushStringProperty(ResourceConfig rc, String key, String value) {
        MetricKey mk = new MetricKey(true, key);
        MetricData md = new MetricData(mk, System.currentTimeMillis(), value);
        MetricDataCache cache = this.metricCache;
        if (cache != null) {
            cache.cacheMetricData(rc, md);
        } else {
            List<MetricData> props = new ArrayList<>();
            props.add(md);
            addMetricData(rc, props, true);
        }
    }

    // -----------------------------------------------------------------------
    // Cancellation helpers (§9)
    // -----------------------------------------------------------------------

    /**
     * Return {@code true} if a stop has been requested via
     * {@link #onStopCollection()}. Collection loops must check this at the top
     * of each iteration to satisfy the cert "clean thread exit" requirement.
     */
    protected boolean isAbortRequested() {
        return abortRequested.get();
    }

    // -----------------------------------------------------------------------
    // Logging helpers
    // -----------------------------------------------------------------------

    /**
     * Return the adapter-specific logger, lazily created on first call.
     *
     * <p>Named after the concrete class; raised to INFO at creation when
     * INFO is not already enabled (see {@link #raiseToInfo}), so a DEBUG
     * level set by the operator is kept (issue #224).
     *
     * <h4>Visibility rule (bytecode-determined)</h4>
     * <p>The platform file appender that writes to
     * {@code <adaptersHome>/<adapterName>_<instanceId>.log} is attached by
     * {@code AdapterLoggerFactoryImpl} <em>only when</em> {@code adapterDir}
     * and {@code instanceId} are both non-null — they are available only on
     * the live-collection path (the three-arg or two-arg constructor). In the
     * no-arg describe path the factory is constructed with all three args
     * null and falls back to the bare Log4j root context; nothing important
     * is logged there, so this is acceptable.
     *
     * <p>When an appender is present the factory creates a per-logger
     * {@code LoggerConfig} whose name is {@code "(instanceId) className"}
     * (corrected 2026-10-23 from bytecode, issue #228). It looks up the
     * config that governs the <em>bare</em> {@code className}: an entry the
     * adapter's {@code <ADAPTER_HOME>/<adapter jar>/conf/logging.properties}
     * created (an {@code AdapterLoggerConfig}; vendor paks ship
     * {@code <package>=INFO}) or else the collector's own config (root WARN).
     * The instance file appender is attached at that entry's
     * {@code levelForAdapterLog} (else the plain level), and the collector's
     * appenders at the plain level. The new logger's own level is the more
     * verbose of the two. The
     * {@link com.integrien.alive.common.adapter3.Logger#setLevel} call
     * ({@code Configurator.setLevel}) changes only that logger level, never
     * the appender filters: it lets a message past the logger's level gate,
     * but a line below the instance appender's level still never reaches the
     * instance log. So what reaches the instance log is decided by the entry
     * covering the bare class name, which is why {@link #componentLogger}
     * names framework classes under the adapter class.
     *
     * <p>The root logger threshold (typically WARN in the 9.1 collector JVM)
     * is irrelevant once a per-instance logger config is registered — Log4j
     * routes by the most-specific matching name, and the adapter's
     * {@code "(instanceId) className"} config takes precedence. The intermittent
     * visibility seen in build 45 post-46 (INFO lines disappearing) is most
     * likely a logger config reload race: {@code AdapterLoggerContext} watches
     * {@code logging.properties} for changes and calls {@code updateLoggers()}
     * after each reload, which re-registers all cached logger configs at their
     * original levels. A {@code setLevel} call that raced with a reload would
     * be lost until the next call. <strong>Residual check for live instance:</strong>
     * tail {@code collector.log} while triggering a reload (save
     * {@code logging.properties} on the appliance) and observe whether the
     * INFO lines reappear after ~30 s — if they do, the race is confirmed.
     * {@link #componentLogger(Class)} re-applies the INFO floor each time it
     * is invoked (normally at configure time, after any reload that occurred
     * during a previous cycle), but only when INFO is not already enabled, so
     * it never lowers a DEBUG level (issue #224).
     *
     * <p><strong>Do not shadow this method in adapter subclasses.</strong>
     * Use {@link #componentLogger(Class)} to obtain leveled loggers for
     * helper classes. See {@code knowledge/context/framework_v2_migration.md}.
     */
    private com.integrien.alive.common.adapter3.Logger adapterLogger() {
        com.integrien.alive.common.adapter3.Logger l = adapterLogger;
        if (l == null) {
            synchronized (this) {
                l = adapterLogger;
                if (l == null) {
                    l = getAdapterLoggerFactory().getLogger(getClass());
                    raiseToInfo(l);
                    adapterLogger = l;
                }
            }
        }
        return l;
    }

    /**
     * Return a logger for a helper or component class, wired identically to
     * the adapter's own logger.
     *
     * <p>Use this method whenever a helper class (HTTP client, SOAP client,
     * stitcher helper, etc.) needs a {@link com.integrien.alive.common.adapter3.Logger}
     * to pass to its constructor. <strong>Never hand-roll a logger handle in
     * adapter subclasses</strong> — the factory, naming convention, and level
     * discipline must be identical to the base's own logger or INFO messages
     * will be silently filtered.
     *
     * <h4>Correct usage pattern</h4>
     * <pre>{@code
     * // In configureAdapter():
     * vSphereClient  = new VSphereClient(host, componentLogger(VSphereClient.class));
     * soapClient     = new EsxcliSoapClient(url, cookie, ssl);      // no logger arg
     * stitcher       = SuiteApiStitcher.create(this, componentLogger(SuiteApiStitcher.class));
     * }</pre>
     *
     * <h4>Visibility contract (bytecode-verified)</h4>
     * <p>The returned handle is obtained from the same
     * {@link com.integrien.alive.common.adapter3.AdapterLoggerFactoryImpl} as
     * the base's own logger. The factory names the logger config
     * {@code "(instanceId) <name>"} and wires it to the same rolling file
     * appender ({@code <adapterName>_<instanceId>.log}), filtered at the
     * level the adapter's logging configuration gives {@code <name>}.
     * {@code <name>} is the component's class name when the class is in the
     * adapter's package, otherwise a child of the adapter class (see
     * {@link #componentLoggerName(Class, Class)}; issue #228: framework
     * helper lines never reached the instance log on a Cloud Proxy).
     *
     * <h4>Level (issue #224)</h4>
     * <p>The logger is raised to INFO only when INFO is not already enabled;
     * a DEBUG or TRACE level set by the operator or the pak's
     * {@code logging.properties} is kept, however often the logger is looked
     * up. Fetching once in {@code configureAdapter()} is still the pattern.
     *
     * <h4>Migration note</h4>
     * <p>Any adapter that was shadowing {@code adapterLogger()} (i.e.,
     * declaring a private method of the same name that called
     * {@code getAdapterLoggerFactory().getLogger(cls)}) must:
     * <ol>
     *   <li>Delete the shadow method.</li>
     *   <li>Replace all call sites with {@code componentLogger(HelperClass.class)}.</li>
     *   <li>Rebuild against the updated {@code vcfcf-adapter-base.jar}.</li>
     * </ol>
     * The shadow was necessary in v1 because the base's {@code adapterLogger()}
     * was private. It is now a footgun: it often omitted {@code setLevel},
     * causing silent INFO filtering (compliance build 45), and it bypasses
     * the framework's double-checked-lock caching (compliance build 46). Both
     * failure modes are eliminated by this method.
     *
     * @param component the helper or component class for which a logger is needed
     * @return a leveled logger, routed to the adapter instance's log file
     */
    protected com.integrien.alive.common.adapter3.Logger componentLogger(
            Class<?> component) {
        java.util.Objects.requireNonNull(component, "componentLogger: component class");
        com.integrien.alive.common.adapter3.Logger l = getAdapterLoggerFactory()
                .getLogger(componentLoggerName(getClass(), component));
        raiseToInfo(l);
        return l;
    }

    /**
     * Logger name {@link #componentLogger(Class)} asks the SDK factory for
     * (issue #228). A class in the adapter's own package, or a subpackage of
     * it, keeps its own name. Any other class (the framework's own helpers
     * such as {@code SuiteApiStitcher}, a JDK or vendor class) is named as a
     * child of the adapter class: {@code <adapter class>.<simple name>}, for
     * example {@code com.vcfcf.adapters.unifi.UniFiAdapter.SuiteApiStitcher}.
     *
     * <p>Why: the SDK gives each logger its instance-log appender at the
     * level the adapter's {@code conf/logging.properties} (or the platform's
     * per-adapter setting) assigns to the bare name, and that entry is keyed
     * by the pak's package. A framework class name
     * ({@code com.vcfcf.adapter.stitch...}) sits outside it, falls back to
     * the collector root level (WARN), and its INFO never reaches the
     * instance log. As a child of the adapter class it inherits exactly the
     * adapter's own level. Visible to tests.
     */
    static String componentLoggerName(Class<?> adapterClass, Class<?> component) {
        return componentLoggerName(adapterClass.getName(), packageOf(adapterClass),
                packageOf(component), component.getName());
    }

    /** {@link #componentLoggerName(Class, Class)} on names. Visible to tests. */
    static String componentLoggerName(String adapterClassName, String adapterPackage,
            String componentPackage, String componentClassName) {
        boolean inPak = componentPackage.equals(adapterPackage)
                || (!adapterPackage.isEmpty()
                        && componentPackage.startsWith(adapterPackage + "."));
        if (inPak) return componentClassName;
        String simple = componentClassName.substring(componentClassName.lastIndexOf('.') + 1);
        return adapterClassName + "." + simple;
    }

    private static String packageOf(Class<?> c) {
        String n = c.getName();
        int dot = n.lastIndexOf('.');
        return dot < 0 ? "" : n.substring(0, dot);
    }

    /**
     * Lift {@code l} to INFO only when INFO is not already enabled (issue
     * #224). A level an operator or the pak's {@code logging.properties} set
     * at INFO or below (DEBUG, TRACE) is left alone, so a repeat lookup can
     * no longer discard DEBUG. A level above INFO (the collector's WARN root)
     * is still raised, which keeps INFO messages from being dropped at the
     * logger.
     */
    static void raiseToInfo(com.integrien.alive.common.adapter3.Logger l) {
        if (!l.isInfoEnabled()) {
            l.setLevel(com.integrien.alive.common.adapter3.Logger.CustomLevel.INFO);
        }
    }

    /** Log at INFO level to the adapter-specific log file. */
    protected void logInfo(String message) {
        adapterLogger().info(message);
    }

    /** Log at WARNING level. */
    protected void logWarn(String message) {
        adapterLogger().warn(message);
    }

    /** Log at WARNING level with cause. */
    protected void logWarn(String message, Throwable t) {
        adapterLogger().warn(message, t);
    }

    /** Log at ERROR level with cause. */
    protected void logError(String message, Throwable t) {
        adapterLogger().error(message, t);
    }

    // -----------------------------------------------------------------------
    // Internal helpers
    // -----------------------------------------------------------------------

    /** What one {@link #onCollect} cycle saw, for the adapter instance status. */
    static final class CycleOutcome {
        int attempted;
        int failed;
        boolean everyFailureDown = true;
        boolean cut;
        Exception firstFailure;

        /**
         * Count a resource failure that left it ERROR or DOWN. Other mapped
         * statuses (for example NO_DATA_RECEIVING) are not a failure of the
         * instance.
         */
        void recordFailure(ResourceStatusEnum effective, Exception e) {
            if (effective != ResourceStatusEnum.RESOURCE_STATUS_ERROR
                    && effective != ResourceStatusEnum.RESOURCE_STATUS_DOWN) {
                return;
            }
            failed++;
            if (effective != ResourceStatusEnum.RESOURCE_STATUS_DOWN) everyFailureDown = false;
            if (firstFailure == null) firstFailure = e;
        }
    }

    /**
     * The adapter instance status a completed cycle calls for, or
     * {@code null} for none (issue #223): ERROR or DOWN when every collected
     * resource failed (DOWN only if all mapped to DOWN), ERROR when there was
     * nothing to collect and discovery failed. Visible to tests.
     */
    static ResourceStatusEnum adapterInstanceStatus(CycleOutcome o, Exception discoveryFailure) {
        if (o.attempted > 0 && o.failed == o.attempted) {
            return o.everyFailureDown ? ResourceStatusEnum.RESOURCE_STATUS_DOWN
                    : ResourceStatusEnum.RESOURCE_STATUS_ERROR;
        }
        if (o.attempted == 0 && discoveryFailure != null) {
            return ResourceStatusEnum.RESOURCE_STATUS_ERROR;
        }
        return null;
    }

    /**
     * One-line reason shown on the adapter instance: what failed and the
     * first failure's class and message (credential-looking fragments
     * redacted by {@link #redactCredentials}, control characters replaced,
     * capped). The account row is readable by any user with Integrations
     * access, so paks must still throw credential-free messages from
     * {@code collect()}; the redaction is a best-effort backstop. Visible to
     * tests.
     */
    static String adapterInstanceFailureMessage(CycleOutcome o, Exception discoveryFailure) {
        Exception cause = o.attempted > 0 ? o.firstFailure : discoveryFailure;
        String what = o.attempted > 0
                ? "Collection failed for all " + o.attempted + " resource(s)"
                : "Resource discovery failed and there was nothing to collect";
        if (cause == null) return what;
        String m = cause.getMessage();
        StringBuilder sb = new StringBuilder(what).append(": ")
                .append(cause.getClass().getSimpleName()).append(": ");
        String text = m == null ? "(no message)" : redactCredentials(m);
        int max = 300;
        for (int i = 0; i < text.length() && i < max; i++) {
            char c = text.charAt(i);
            sb.append(Character.isISOControl(c) ? ' ' : c);
        }
        if (text.length() > max) sb.append("...");
        return sb.toString();
    }

    /** Bearer, Basic and OpsToken authorization values. */
    private static final java.util.regex.Pattern AUTH_SCHEME_VALUE = java.util.regex.Pattern.compile(
            "(?i)\\b(bearer|basic|opstoken)(\\s+)[A-Za-z0-9._~+/=:-]{4,}");

    /**
     * {@code key=value}, {@code key: value} and JSON {@code "key":"value"}
     * pairs whose key names a secret.
     */
    private static final java.util.regex.Pattern SECRET_PAIR = java.util.regex.Pattern.compile(
            "(?i)([\"']?\\b(?:password|passwd|pwd|passphrase|secret|client_secret|token|"
            + "access_token|refresh_token|api[_-]?key|apikey|session[_-]?id|sessionid|_?sid)"
            + "\\b[\"']?\\s*[:=]\\s*)(\"[^\"]*\"|'[^']*'|[^\\s&,;\"'}\\]]+)");

    /** {@code scheme://user:password@host} userinfo. */
    private static final java.util.regex.Pattern URL_USERINFO = java.util.regex.Pattern.compile(
            "(?i)(\\b[a-z][a-z0-9+.-]*://)[^/\\s@:]+:[^/\\s@]+@");

    /**
     * Best-effort removal of credential-looking fragments from text bound for
     * the account row (review W1, issue #223): Bearer / Basic / OpsToken
     * values, {@code password=}-style pairs (also {@code token}, {@code sid},
     * {@code api_key} and similar, in {@code =}, {@code :} and JSON forms),
     * and {@code user:password@} in URLs. Each becomes {@code <redacted>}.
     * Not a guarantee: a pak must not put secrets in exception messages.
     * Visible to tests.
     */
    static String redactCredentials(String text) {
        if (text == null || text.isEmpty()) return text;
        String t = AUTH_SCHEME_VALUE.matcher(text).replaceAll("$1$2<redacted>");
        t = SECRET_PAIR.matcher(t).replaceAll("$1<redacted>");
        return URL_USERINFO.matcher(t).replaceAll("$1<redacted>@");
    }

    private void reportAdapterInstanceFailure(ResourceConfig adapterInstance,
            CycleOutcome outcome, Exception discoveryFailure) {
        ResourceStatusEnum status = adapterInstanceStatus(outcome, discoveryFailure);
        if (status == null || adapterInstance == null) return;
        String msg = adapterInstanceFailureMessage(outcome, discoveryFailure);
        try {
            setResourceStatus(adapterInstance, status, msg);
        } catch (RuntimeException e) {
            logWarn("onCollect: could not set the adapter instance status: " + e);
            return;
        }
        logWarn("onCollect: adapter instance set to " + status.name() + ": " + msg);
    }

    /**
     * Set per-resource status, validating with
     * {@link ResourceStatusEnum#isAdapterAllowedStatus(ResourceStatusEnum)}.
     * Falls back to {@code RESOURCE_STATUS_ERROR} if the status is not
     * adapter-settable (guards against accidental use of platform-only statuses).
     */
    private void setStatusSafe(ResourceConfig rc, ResourceStatusEnum status) {
        ResourceStatusEnum safe = ResourceStatusEnum.isAdapterAllowedStatus(status)
                ? status
                : ResourceStatusEnum.RESOURCE_STATUS_ERROR;
        setResourceStatus(rc, safe);
    }

    /** Human-readable label for a ResourceConfig for log messages. */
    private static String rcLabel(ResourceConfig rc) {
        if (rc == null) return "<null>";
        String kind = rc.getResourceKind();
        String name = rc.getResourceName();
        return (kind != null ? kind : "?") + "/"
                + (name != null ? name : String.valueOf(rc.getResourceId()));
    }

    /**
     * Create the {@link MetricDataCache} instance.
     *
     * <p><strong>[INFER] ctor params {@code p1=1000, p2=100}</strong>: the SDK
     * does not document the two {@code int} params. Inferred as
     * (cache-size-hint=1000, dedup-window=100) from the aria-ops-core wrapper's
     * {@code maxEvents}/window pattern. These are conservative values.
     * Amend here if empirical evidence updates the inference.
     *
     * @return a new cache, or {@code null} if construction fails
     */
    private MetricDataCache createMetricCache() {
        try {
            return new MetricDataCache(this, 1000, 100);
        } catch (Exception e) {
            logWarn("VcfCfAdapter: MetricDataCache unavailable, dedup disabled: "
                    + e.getMessage());
            return null;
        }
    }
}
