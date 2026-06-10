package com.vcfcf.adapter;

import com.vcfcf.adapter.http.ManagedHttpClient;
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

import java.io.InputStream;
import java.nio.file.Files;
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
 *       {@code describe.xml} via {@link AdapterBase#getAdapterDescribeFile}).
 *       Override only if custom describe handling is needed.</li>
 *   <li>{@link #getTester()} — return a {@link VcfCfTester} (nullable).</li>
 *   <li>{@link #getDiscoverer()} — return a {@link VcfCfDiscoverer}.</li>
 *   <li>{@link #getCollector()} — return a {@link VcfCfCollector}.</li>
 * </ol>
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
    // Constructors (both required by the platform)
    // -----------------------------------------------------------------------

    /**
     * No-arg constructor required by the analytics engine.
     *
     * <p>The platform calls {@code Class.newInstance()} (no-arg reflection)
     * during {@code describe()} generation. Without this constructor the engine
     * throws {@code InstantiationException} and the adapter kind is not registered.
     */
    public VcfCfAdapter() {
        super();
    }

    /**
     * Two-arg constructor required for live-collection instantiation.
     *
     * <p>The collector process instantiates adapter classes via
     * {@code Constructor(String, Integer)}. Without this constructor the adapter
     * instance fails to start with {@code NoSuchMethodException}.
     *
     * @param adapterDir        the adapter directory path supplied by the platform
     * @param adapterInstanceId the adapter instance ID supplied by the platform
     */
    public VcfCfAdapter(String adapterDir, Integer adapterInstanceId) {
        super(adapterDir, adapterInstanceId);
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
     */
    @SuppressWarnings("rawtypes")
    protected abstract VcfCfDiscoverer getDiscoverer();

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
    // AdapterBase required + optional overrides — lifecycle orchestration
    // -----------------------------------------------------------------------

    /**
     * Load and return the adapter's {@link AdapterDescribe} from
     * {@code describe.xml}.
     *
     * <p>The default implementation resolves the file using
     * {@link AdapterBase#getAdapterDescribeFile(String, String)} with the
     * adapter kind returned by {@link AdapterBase#getAdapterKind()}. The
     * canonical path is {@code <adaptersHome>/<adapterKind>/conf/describe.xml}.
     *
     * <p>If the file is missing or cannot be parsed the method throws a
     * {@link RuntimeException} with the resolved path in the message, so the
     * failure is immediately actionable rather than producing a silent NPE or
     * an unconfigured adapter.
     *
     * <p>Override this method only when custom describe handling is required
     * (e.g., programmatic describe construction or a non-standard file location).
     * Normal adapters should rely on this default.
     *
     * <p><strong>Note on adapter kind:</strong> {@link AdapterBase#getAdapterKind()}
     * returns the kind value from the live adapter config, which is populated by
     * the platform before {@code onDescribe()} is called. Do not derive the kind
     * from {@code CommonConstants} — those fields are display-name strings, not
     * filesystem paths (see {@code lessons/sdk-constants-are-display-names.md}).
     *
     * @return the populated {@link AdapterDescribe}; never {@code null}
     * @throws RuntimeException if describe.xml is missing, unreadable, or
     *         cannot be parsed — the exception message contains the resolved path
     */
    @Override
    public AdapterDescribe onDescribe() {
        String kind = getAdapterKind();
        Path describeFile = getAdapterDescribeFile(kind, "describe.xml");
        try (InputStream is = Files.newInputStream(describeFile)) {
            return AdapterDescribe.make(is);
        } catch (Exception e) {
            throw new RuntimeException(
                    "VcfCfAdapter.onDescribe: failed to load describe.xml from "
                    + describeFile + " (adapterKind=" + kind + "): "
                    + e.getMessage(), e);
        }
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

        // §1 step 1: optional top-of-cycle rediscovery.
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
     * <p>Named after the concrete class; pinned to INFO level to prevent
     * the WARN root logger from silently filtering INFO messages. The platform
     * file appender ({@code <AdapterName>_<instanceId>.log}) is attached
     * when both {@code adapterDir} and {@code instanceId} are non-null
     * (the live-collection path). In the no-arg describe path, the root
     * Log4j context is used (acceptable — nothing important is logged then).
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
