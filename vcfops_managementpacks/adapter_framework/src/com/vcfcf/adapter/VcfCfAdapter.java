package com.vcfcf.adapter;

import com.vcfcf.adapter.http.ManagedHttpClient;

import com.integrien.alive.common.adapter3.Logger;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.TestParam;
import com.integrien.alive.common.adapter3.config.CredentialConfig;
import com.integrien.alive.common.adapter3.config.CredentialFieldConfig;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.vmware.tvs.vrealize.adapter.core.UnlicensedAdapter;
import com.vmware.tvs.vrealize.adapter.core.collection.historical.HistoricalCollector;
import com.vmware.tvs.vrealize.adapter.core.collection.live.LiveCollector;
import com.vmware.tvs.vrealize.adapter.core.data.ResourceCollection;
import com.vmware.tvs.vrealize.adapter.core.discovery.Discoverer;
import com.vmware.tvs.vrealize.adapter.core.test.Tester;

import java.util.Collection;
import java.util.logging.Level;

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
	 * <p>Default: {@code false}. Override to return {@code true} for adapters
	 * that support automatic resource discovery without user intervention.
	 */
	@Override
	public boolean getAutoDiscoveryEnabled(ResourceStatus status, ResourceConfig resourceConfig) {
		return false;
	}

	/**
	 * Whether rediscovery is needed. Default implementation always returns
	 * {@code false}; override when the adapter needs to re-discover resources
	 * on each collection cycle.
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
	// Logging helpers
	// -----------------------------------------------------------------------

	/** Log a message at INFO level. */
	protected void logInfo(String message) {
		java.util.logging.Logger.getLogger(getClass().getName()).info(message);
	}

	/** Log a message at WARNING level. */
	protected void logWarn(String message) {
		java.util.logging.Logger.getLogger(getClass().getName()).warning(message);
	}

	/** Log a message at WARNING level with an exception. */
	protected void logWarn(String message, Throwable t) {
		java.util.logging.Logger.getLogger(getClass().getName()).log(Level.WARNING, message, t);
	}

	/** Log a message at SEVERE level with an exception. */
	protected void logError(String message, Throwable t) {
		java.util.logging.Logger.getLogger(getClass().getName()).log(Level.SEVERE, message, t);
	}
}
