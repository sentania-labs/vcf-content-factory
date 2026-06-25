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
import com.integrien.alive.common.adapter3.config.CredentialConfig;
import com.integrien.alive.common.adapter3.config.CredentialFieldConfig;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;
import com.integrien.alive.common.util.CommonConstants.ResourceStatusEnum;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collection;
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
 * {@code lessons/sdk-constants-are-display-names.md}.
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
     * Adapter-instance-scoped logger obtained lazily from the platform's
     * {@code AdapterLoggerFactory}. Named after the concrete class; pinned
     * to INFO level so messages are not swallowed by the WARN root logger.
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
                + "See context/framework_v2_migration.md §22.");
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
     * See {@code lessons/controller-describe-bare-instantiation.md}.
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
                    + "See lessons/controller-describe-bare-instantiation.md.");
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
     *   <li>Optional top-of-cycle rediscovery (§1 step 1 + §2).</li>
     *   <li>Per-resource gather → cache metrics/properties → emit events →
     *       emit relationships.</li>
     *   <li>REQUIRED per-resource status set every cycle (§1).</li>
     *   <li>{@link MetricDataCache#flushCachedData()} at end of cycle (§8).</li>
     * </ol>
     *
     * <p>Cooperative cancellation: loops check {@link #isAbortRequested()}
     * and honor {@link InterruptedException} (§9).
     */
    @Override
    @SuppressWarnings("unchecked")
    public final void onCollect(ResourceConfig adapterInstance,
            Collection<ResourceConfig> resources) {
        abortRequested.set(false);

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
                // Not fatal — continue with existing resource set.
            }
        }

        if (isAbortRequested()) return;

        // §1 step 2: per-resource gather.
        MetricDataCache cache = this.metricCache;

        for (ResourceConfig rc : resources) {
            if (isAbortRequested() || Thread.currentThread().isInterrupted()) {
                Thread.currentThread().interrupt();
                break;
            }

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
                break;
            } catch (Exception e) {
                String msg = e.getMessage() != null ? e.getMessage()
                        : e.getClass().getSimpleName();
                logWarn("onCollect: error collecting " + rcLabel(rc) + ": " + msg, e);
                ResourceStatusEnum status = collector.mapCollectException(e);
                setStatusSafe(rc,
                        status != null ? status : ResourceStatusEnum.RESOURCE_STATUS_ERROR);
            }
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
     * Build an {@link javax.net.ssl.SSLContext} backed by the platform's trust
     * store via {@link AdapterBase#getSocketFactory()}.
     *
     * <p>This is the <strong>required</strong> way to obtain SSL context for
     * {@link com.vcfcf.adapter.http.HttpClientBuilder}. It ensures the platform's
     * certificate management (user-trusted certs, renewal URLs) is honoured.
     * The cert certification item forbids using {@link #insecureSslContext()} as
     * the default path.
     *
     * @return a platform-managed {@link javax.net.ssl.SSLContext}
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
     * Build an insecure (trust-all) {@link javax.net.ssl.SSLContext}.
     *
     * <p><strong>Explicit, documented opt-out.</strong> Use ONLY in lab / dev
     * environments with self-signed certificates. Do not use as the default path.
     * In production adapters use {@link #getPlatformSslContext()} instead.
     *
     * @return an SSLContext that trusts all certificates without validation
     * @throws RuntimeException if context construction fails
     */
    public static javax.net.ssl.SSLContext insecureSslContext() {
        try {
            javax.net.ssl.SSLContext ctx = javax.net.ssl.SSLContext.getInstance("TLS");
            ctx.init(null, new javax.net.ssl.TrustManager[]{
                new javax.net.ssl.X509TrustManager() {
                    public java.security.cert.X509Certificate[] getAcceptedIssuers() {
                        return new java.security.cert.X509Certificate[0];
                    }
                    public void checkClientTrusted(
                            java.security.cert.X509Certificate[] c, String a) {}
                    public void checkServerTrusted(
                            java.security.cert.X509Certificate[] c, String a) {}
                }
            }, null);
            return ctx;
        } catch (Exception e) {
            throw new RuntimeException(
                    "VcfCfAdapter: failed to build insecure SSL context", e);
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
     * <p>Named after the concrete class; pinned to INFO level so messages
     * are not swallowed by the WARN root logger.
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
     * {@code LoggerConfig} whose name is {@code "(instanceId) className"}.
     * That logger config is wired to the instance file appender with an
     * effective level of {@code max(sdkLoggerConfig.levelForAdapterLog,
     * rootLevel)} — where {@code levelForAdapterLog} is the level written by
     * {@code logging.properties} (typically {@code INFO} or {@code WARN}).
     * The {@link com.integrien.alive.common.adapter3.Logger#setLevel} call
     * translates the {@code CustomLevel} to a Log4j level and invokes
     * {@code Configurator.setLevel(loggerName, level)} — which patches the
     * live {@code LoggerConfig} in the running Log4j context, overriding the
     * {@code logging.properties} floor. <strong>Without the {@code setLevel}
     * call, a WARN root threshold silently drops INFO messages even when the
     * adapter appender is correctly attached.</strong>
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
     * The {@link #componentLogger(Class)} method is not susceptible to this
     * race because it calls {@code setLevel} <em>every time it is invoked by
     * the adapter</em>, which is at configure time (after any reload that
     * would have occurred during a previous cycle).
     *
     * <p><strong>Do not shadow this method in adapter subclasses.</strong>
     * Use {@link #componentLogger(Class)} to obtain leveled loggers for
     * helper classes. See {@code context/framework_v2_migration.md}.
     */
    private com.integrien.alive.common.adapter3.Logger adapterLogger() {
        com.integrien.alive.common.adapter3.Logger l = adapterLogger;
        if (l == null) {
            synchronized (this) {
                l = adapterLogger;
                if (l == null) {
                    l = getAdapterLoggerFactory().getLogger(getClass());
                    l.setLevel(
                        com.integrien.alive.common.adapter3.Logger.CustomLevel.INFO);
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
     * {@code "(instanceId) com.example.HelperClass"} — the same pattern as
     * the adapter's own {@code "(instanceId) com.example.MyAdapter"} — and
     * wires it to the same rolling file appender
     * ({@code <adapterName>_<instanceId>.log}). The {@code setLevel(INFO)}
     * call overrides the {@code logging.properties} floor so INFO messages
     * are not silently filtered by the WARN root threshold.
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
        com.integrien.alive.common.adapter3.Logger l =
                getAdapterLoggerFactory().getLogger(component);
        l.setLevel(com.integrien.alive.common.adapter3.Logger.CustomLevel.INFO);
        return l;
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
