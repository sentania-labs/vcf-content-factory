package com.vcfcf.adapter;

import com.vcfcf.adapter.http.ManagedHttpClient;

import com.integrien.alive.common.adapter3.Logger;
import com.integrien.alive.common.adapter3.MetricData;
import com.integrien.alive.common.adapter3.MetricKey;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.TestParam;
import com.integrien.alive.common.adapter3.config.CredentialConfig;
import com.integrien.alive.common.adapter3.config.CredentialFieldConfig;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter;
import com.vmware.tvs.vrealize.adapter.core.collection.historical.HistoricalCollector;
import com.vmware.tvs.vrealize.adapter.core.collection.live.LiveCollector;
import com.vmware.tvs.vrealize.adapter.core.data.Resource;
import com.vmware.tvs.vrealize.adapter.core.data.ResourceCollection;
import com.vmware.tvs.vrealize.adapter.core.discovery.Discoverer;
import com.vmware.tvs.vrealize.adapter.core.test.Tester;

import java.util.Collection;

/**
 * Abstract base class for all VCF Content Factory Tier 2 SDK adapters.
 *
 * <p>Extends {@link UnlicensedAdapter} (Layer 2 from aria-ops-core) with:
 * <ul>
 *   <li>Typed config binding via {@link #configure(ResourceStatus, ResourceConfig)}</li>
 *   <li>Lifecycle defaults (discard releases HTTP client)</li>
 *   <li>Framework-provided logging shorthand</li>
 * </ul>
 *
 * <p>Adapter authors extend this class and implement at minimum:
 * <ul>
 *   <li>{@link #getAdapterDirectory()} — return the adapter kind key string</li>
 *   <li>{@link #configure(ResourceStatus, ResourceConfig)} — read config, build HTTP client</li>
 *   <li>{@link #getTester(ResourceStatus, ResourceConfig)} — validate connectivity</li>
 *   <li>{@link #getDiscoverer(ResourceStatus, ResourceConfig)} — discover resources</li>
 *   <li>{@link #getLiveDataCollector(ResourceStatus, ResourceConfig)} — collect metrics</li>
 * </ul>
 *
 * <p>Historical collection is optional; the default implementation returns
 * {@code null} which disables historical data collection. Adapter authors
 * may override {@link #getHistoricalDataCollector(ResourceStatus, ResourceConfig)}
 * to enable it.
 *
 * @param <C> the typed configuration POJO for this adapter
 */
public abstract class VcfCfAdapter<C> extends UnlicensedAdapter {

	/**
	 * No-arg constructor required by the analytics engine.
	 *
	 * <p>The analytics engine instantiates adapter classes via
	 * {@code Class.newInstance()} (no-arg reflection) during {@code describe()}
	 * generation. Without this constructor the engine throws
	 * {@code InstantiationException}. Delegates to {@code super()} which
	 * ultimately chains to {@code UnlicensedAdapter(null, null)} matching
	 * the pattern confirmed in {@code UnlicensedAdapter} bytecode.
	 */
	public VcfCfAdapter() {
		super();
	}

	/**
	 * Platform-reflection constructor.
	 *
	 * <p>The Tier 2 platform instantiates adapter classes via reflection using
	 * the two-argument signature {@code (String adapterDir, Integer adapterInstanceId)}.
	 * This constructor satisfies that requirement by delegating to
	 * {@code UnlicensedAdapter(String, Integer)} → {@code AdapterBase(String, Integer)}.
	 *
	 * @param adapterDir        the adapter directory path supplied by the platform
	 * @param adapterInstanceId the adapter instance identifier supplied by the platform
	 */
	public VcfCfAdapter(String adapterDir, Integer adapterInstanceId) {
		super(adapterDir, adapterInstanceId);
	}

	/**
	 * The typed configuration for this adapter instance.
	 * Populated by {@link #configure(ResourceStatus, ResourceConfig)}.
	 */
	protected volatile C config;

	/**
	 * The managed HTTP client for this adapter instance.
	 * May be {@code null} if this adapter does not use HTTP.
	 */
	protected volatile ManagedHttpClient httpClient;

	/**
	 * Return the adapter directory name. This MUST match the KINDKEY in
	 * {@code adapter.properties} and the {@code key} attribute of the root
	 * {@code <AdapterKind>} element in {@code describe.xml}.
	 *
	 * <p>By convention, return the same string as the adapter kind key.
	 *
	 * @return the adapter kind key string
	 */
	@Override
	protected abstract String getAdapterDirectory();

	/**
	 * Configure this adapter instance from the platform-supplied config.
	 *
	 * <p>Called by the platform when the adapter instance is first created and
	 * on every subsequent config update. The implementation should:
	 * <ol>
	 *   <li>Read credentials and identifiers from {@code resourceConfig}</li>
	 *   <li>Build and store the typed config POJO in {@link #config}</li>
	 *   <li>Build and store the HTTP client in {@link #httpClient} (if applicable)</li>
	 *   <li>Invalidate any cached state (session tokens, etc.)</li>
	 * </ol>
	 *
	 * @param status         adapter status object for reporting configuration errors
	 * @param resourceConfig the adapter instance resource config from the platform
	 */
	@Override
	public abstract void configure(ResourceStatus status, ResourceConfig resourceConfig);

	/**
	 * Return the {@link Tester} for this adapter instance.
	 *
	 * <p>Called when the user clicks "Test Connection" in the UI. The tester
	 * should validate that the target system is reachable and that credentials
	 * are correct.
	 */
	@Override
	public abstract Tester getTester(ResourceStatus status, ResourceConfig resourceConfig);

	/**
	 * Return the {@link Discoverer} for this adapter instance.
	 *
	 * <p>Called during resource discovery. The discoverer should enumerate all
	 * resources of each kind that this adapter manages.
	 */
	@Override
	public abstract Discoverer getDiscoverer(ResourceStatus status, ResourceConfig resourceConfig);

	/**
	 * Return the {@link LiveCollector} for this adapter instance.
	 *
	 * <p>Called during each scheduled collection cycle. The live collector
	 * should gather current metrics, properties, events, and relationships.
	 */
	@Override
	public abstract LiveCollector getLiveDataCollector(ResourceStatus status, ResourceConfig resourceConfig);

	/**
	 * Return the {@link HistoricalCollector} for this adapter instance.
	 *
	 * <p>Default: returns {@code null} (historical collection disabled).
	 * Override to enable historical metric backfill.
	 */
	@Override
	public HistoricalCollector getHistoricalDataCollector(ResourceStatus status, ResourceConfig resourceConfig) {
		return null;
	}

	/**
	 * Whether auto-discovery is enabled for this adapter.
	 *
	 * <p>MUST return {@code true} for VCF-CF adapters. The
	 * {@code UnlicensedAdapter.processMetrics()} gate checks this flag for
	 * every resource returned by {@code LiveCollector.getCurrentMetrics()}: if
	 * the resource is new (not yet known to the platform) AND
	 * {@code autoDiscoveryEnabled} is {@code false} AND
	 * {@code resource.overridesAutoDiscovery()} is {@code false}, the resource
	 * is silently dropped and never registered. This produces the symptom of
	 * collection running successfully but showing zero child objects —
	 * {@code Number of New Objects = 0} — because every resource is "new" and
	 * the gate rejects all of them.
	 *
	 * <p>Returning {@code true} here causes the framework to call
	 * {@code addCollectedResource()} for each new resource, which adds it to
	 * the {@code CollectResult}'s embedded {@code DiscoveryResult} and makes it
	 * visible in VCF Ops on the same collection cycle it was first seen.
	 *
	 * <p>Subclasses MAY override to return {@code false} only for adapters that
	 * intentionally require explicit user-triggered discovery before metrics
	 * are accepted (rare; none in the VCF-CF corpus).
	 */
	@Override
	public boolean getAutoDiscoveryEnabled(ResourceStatus status, ResourceConfig resourceConfig) {
		return true;
	}

	/**
	 * Whether rediscovery is needed. Default implementation always returns
	 * {@code false}; override when the adapter needs to re-run the explicit
	 * {@code Discoverer.getResources()} path on each collection cycle (e.g.,
	 * to detect removed resources and trigger state-change transitions).
	 *
	 * <p>Note: returning {@code true} here is distinct from
	 * {@link #getAutoDiscoveryEnabled} — this path calls
	 * {@code internalDiscover()} at the top of every {@code onCollect()} and
	 * is the right hook for tombstone / disappear detection. It is not required
	 * for basic resource registration; {@link #getAutoDiscoveryEnabled()}
	 * returning {@code true} is sufficient for that.
	 */
	@Override
	protected boolean needRediscovery(ResourceConfig adapterInstance,
			Collection<ResourceConfig> monitoringResources) {
		return false;
	}

	/**
	 * Called when this adapter instance is discarded (shutdown/uninstall).
	 * Releases the HTTP client and any other held resources.
	 *
	 * <p>Subclasses may override to release additional resources; call
	 * {@code super.onDiscard()} to ensure the HTTP client is closed.
	 */
	@Override
	public void onDiscard() {
		super.onDiscard();
		ManagedHttpClient client = this.httpClient;
		if (client != null) {
			client.discard();
			this.httpClient = null;
		}
	}

	// -----------------------------------------------------------------------
	// Credential helpers
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
		for (com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig id
				: resourceConfig.getResourceIdentifiers()) {
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
	 * Set a string property on a resource.
	 *
	 * <p><strong>Use this method — not {@code resource.addData(String, String)}
	 * — for all string properties.</strong>
	 *
	 * <p>The SDK's convenience overload {@code Resource.addData(String, String)}
	 * delegates to {@code MetricKey.parseMetricKey(String)}, which hardcodes
	 * {@code isProperty = false}. A {@code MetricKey} with {@code isProperty =
	 * false} is classified as a numeric metric by the platform and the string
	 * value is silently discarded at collection time — properties never appear
	 * in the UI, and no error is raised. The correct fix is to construct
	 * {@code new MetricKey(true, key)} explicitly, which is what this helper
	 * does.
	 *
	 * @param r     the resource to set the property on
	 * @param key   the property key (dot/pipe-separated group|name)
	 * @param value the string value
	 */
	protected static void addProperty(Resource r, String key, String value) {
		MetricKey mk = new MetricKey(true, key);
		r.addData(new MetricData(mk, System.currentTimeMillis(), value));
	}

	// -----------------------------------------------------------------------
	// Logging helpers
	// -----------------------------------------------------------------------

	/**
	 * Per-adapter-instance logger obtained from the platform's
	 * {@link com.vmware.vrops.logging.AdapterLoggerFactory}.  Lazily
	 * initialised on first use so that it is always obtained after the
	 * platform has fully constructed the adapter instance (and therefore
	 * after the file appender for {@code <AdapterName>_<instanceId>.log}
	 * has been created).
	 *
	 * <p>The level is pinned to INFO so that INFO messages are never
	 * silently filtered by a root Log4j config that sits at WARN or
	 * higher.  The platform's {@link com.vmware.vrops.logging.AdapterLoggerFactory}
	 * creates the file appender correctly when {@code adapterDir} and
	 * {@code instanceId} are non-null (i.e. the live-collection path);
	 * in the describe-only / no-arg path both values are null and the
	 * factory falls back to the root Log4j context, which is acceptable
	 * because nothing of interest is logged during describe generation.
	 */
	private volatile Logger adapterLogger;

	/**
	 * Return the adapter-specific logger, creating it on first call.
	 *
	 * <p>Routing: {@code getAdapterLoggerFactory().getLogger(getClass())}
	 * ensures the logger name is the concrete adapter class (e.g.
	 * {@code com.vcfcf.adapters.synology.SynologyAdapter}) and that the
	 * platform's file appender is attached.  The explicit INFO pin
	 * prevents the WARN-level root logger from suppressing INFO output.
	 */
	private Logger adapterLogger() {
		Logger l = adapterLogger;
		if (l == null) {
			synchronized (this) {
				l = adapterLogger;
				if (l == null) {
					l = getAdapterLoggerFactory().getLogger(getClass());
					l.setLevel(Logger.CustomLevel.INFO);
					adapterLogger = l;
				}
			}
		}
		return l;
	}

	/** Log a message at INFO level to the adapter-specific log file. */
	protected void logInfo(String message) {
		adapterLogger().info(message);
	}

	/** Log a message at WARNING level to the adapter-specific log file. */
	protected void logWarn(String message) {
		adapterLogger().warn(message);
	}

	/** Log a message at WARNING level with an exception. */
	protected void logWarn(String message, Throwable t) {
		adapterLogger().warn(message, t);
	}

	/** Log a message at ERROR level with an exception. */
	protected void logError(String message, Throwable t) {
		adapterLogger().error(message, t);
	}
}
