package com.vcfcf.adapter.spi;

import com.integrien.alive.common.adapter3.AdapterBase;
import com.integrien.alive.common.adapter3.MetricData;
import com.integrien.alive.common.adapter3.Relationships;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.integrien.alive.common.util.CommonConstants.ResourceStatusEnum;
import com.vcfcf.adapter.http.ManagedHttpClient;

import java.util.List;

/**
 * SPI: gathers metrics, properties, events, and relationships for a single
 * resource per collection cycle.
 *
 * <p>Implement this interface and return an instance from
 * {@link com.vcfcf.adapter.VcfCfAdapter#getCollector()}.
 *
 * <h3>Contract (spec/19 §1)</h3>
 * <ul>
 *   <li>{@link #collect} gathers all {@link MetricData} samples (metrics and
 *       properties) for one resource and appends them to {@code out}. The
 *       orchestrator sends them through the {@link com.integrien.alive.common.adapter3.MetricDataCache}
 *       before flushing — do not call {@code addMetricData} directly here unless
 *       you need to bypass the cache.</li>
 *   <li>{@link #collectEvents} fires events for the resource. Use
 *       {@link AdapterBase#addEvent(ResourceConfig, com.integrien.alive.common.adapter3.events.ExternalEvent)}
 *       directly — event identity is the message text (spec/19 §4).</li>
 *   <li>{@link #collectRelationships} returns a {@link Relationships} object
 *       (or {@code null}) that the orchestrator attaches to the current
 *       {@code CollectResult}. Prefer {@link Relationships#setRelationships}
 *       for stable parent→children sets; use add/remove only for known deltas
 *       (spec/19 §3).</li>
 *   <li>{@link #needsRediscovery} / {@link #rediscover} handle optional
 *       top-of-cycle rediscovery (spec/19 §1 step 1).</li>
 *   <li>{@link #mapCollectException} translates a caught exception to an
 *       appropriate {@link ResourceStatusEnum}. Return {@code null} to use
 *       the default ({@code RESOURCE_STATUS_ERROR}).</li>
 * </ul>
 *
 * <h3>MetricData property flag (cert item)</h3>
 * Construct {@code MetricData} with {@code new MetricKey(true, key)} for
 * string properties and numeric properties. {@code new MetricKey(key)} hardcodes
 * {@code isProperty=false} and the platform silently discards string values.
 *
 * @param <C> the typed configuration POJO of the adapter
 */
public interface VcfCfCollector<C> {

    /**
     * Gather all metric and property samples for {@code rc} and append them
     * to {@code out}. The orchestrator feeds {@code out} into the
     * {@link com.integrien.alive.common.adapter3.MetricDataCache} for dedup.
     *
     * @param config     the typed configuration
     * @param httpClient the managed HTTP client (may be {@code null})
     * @param rc         the resource to collect from
     * @param out        the list to append {@link MetricData} samples to
     * @param adapter    the {@link AdapterBase} reference for helpers like
     *                   {@link AdapterBase#shouldCollect(ResourceConfig, com.integrien.alive.common.adapter3.MetricKey)}
     * @throws InterruptedException if the thread is interrupted
     * @throws Exception            on any collection error; the orchestrator
     *                              calls {@link #mapCollectException(Exception)}
     *                              to determine the resource status
     */
    void collect(C config, ManagedHttpClient httpClient,
            ResourceConfig rc, List<MetricData> out, AdapterBase adapter)
            throws InterruptedException, Exception;

    /**
     * Emit events for {@code rc}.
     *
     * <p>Default: no-op. Override to emit events. Call
     * {@link AdapterBase#addEvent(ResourceConfig, com.integrien.alive.common.adapter3.events.ExternalEvent)}
     * for each event. Message text is the event identity — see spec/19 §4.
     *
     * @param config     the typed configuration
     * @param httpClient the managed HTTP client (may be {@code null})
     * @param rc         the resource to emit events for
     * @param adapter    the {@link AdapterBase} reference
     * @throws Exception on error; event failures do not affect resource status
     */
    default void collectEvents(C config, ManagedHttpClient httpClient,
            ResourceConfig rc, AdapterBase adapter) throws Exception {
        // no-op default
    }

    /**
     * Build relationships for {@code rc}.
     *
     * <p>Default: returns {@code null} (no relationships). Override to emit
     * relationships. Return a populated {@link Relationships} object; the
     * orchestrator attaches it to the current cycle's {@code CollectResult}.
     *
     * <p>Best practice: one {@link Relationships#setRelationships(com.integrien.alive.common.adapter3.ResourceKey, java.util.Collection)}
     * per parent per cycle so the platform can diff the full child set.
     * Cap edges at {@link com.vcfcf.adapter.VcfCfAdapter#MAX_RELATIONSHIPS_PER_CYCLE}
     * to avoid overwhelming the platform (spec/19 §3).
     *
     * @param config the typed configuration
     * @param rc     the resource to build relationships for
     * @return a {@link Relationships} object, or {@code null}
     */
    default Relationships collectRelationships(C config, ResourceConfig rc) {
        return null;
    }

    /**
     * Whether top-of-cycle rediscovery is needed this cycle.
     *
     * <p>Default: {@code false}. Override to return {@code true} when resource
     * inventory or relationships may have changed (e.g., a new device was added)
     * and the adapter needs to register new resources via the collect cycle's
     * embedded discovery result (spec/19 §1 step 1, §2).
     *
     * @param config the typed configuration
     * @return {@code true} to trigger rediscovery at the top of this cycle
     */
    default boolean needsRediscovery(C config) {
        return false;
    }

    /**
     * Perform top-of-cycle rediscovery.
     *
     * <p>Called only when {@link #needsRediscovery} returns {@code true}.
     * Use {@code adapterInst} to access the current {@code CollectResult}'s
     * embedded {@code DiscoveryResult} via
     * {@link com.integrien.alive.common.adapter3.AdapterBase} protected field
     * {@code collectResult}, or register new resources via
     * {@code adapter.addNewResourceToCollect(rc)} — use the path exposed by
     * the orchestrator below.
     *
     * <p>Default: no-op. Override when {@link #needsRediscovery} returns true.
     *
     * @param config        the typed configuration
     * @param httpClient    the managed HTTP client
     * @param adapterInst   the adapter instance resource config
     * @param adapter       the {@link AdapterBase} reference for accessing the
     *                      protected {@code collectResult} field via the
     *                      framework's {@code VcfCfAdapter.registerNewResource}
     *                      helper
     * @throws InterruptedException if the thread is interrupted
     * @throws Exception            on rediscovery failure
     */
    default void rediscover(C config, ManagedHttpClient httpClient,
            ResourceConfig adapterInst, AdapterBase adapter)
            throws InterruptedException, Exception {
        // no-op default
    }

    /**
     * Map a caught exception to a per-resource {@link ResourceStatusEnum}.
     *
     * <p>Default: returns {@code null} (orchestrator uses
     * {@code RESOURCE_STATUS_ERROR}).
     *
     * <p>Override to distinguish DOWN (unreachable) from ERROR (reachable
     * but failed) from NO_DATA_RECEIVING (reachable, no data). Example:
     * <pre>
     * if (e instanceof java.net.ConnectException) return RESOURCE_STATUS_DOWN;
     * if (e instanceof NoDataException) return RESOURCE_STATUS_NO_DATA_RECEIVING;
     * return RESOURCE_STATUS_ERROR;
     * </pre>
     *
     * @param e the exception thrown by {@link #collect}
     * @return the status to set, or {@code null} for the default
     */
    default ResourceStatusEnum mapCollectException(Exception e) {
        return null;
    }
}
