package com.vcfcf.adapter.spi;

import com.integrien.alive.common.adapter3.DiscoveryParam;
import com.integrien.alive.common.adapter3.DiscoveryResult;
import com.vcfcf.adapter.http.ManagedHttpClient;

/**
 * SPI: enumerates resources from the target system during a discovery cycle.
 *
 * <p>Implement this interface and return an instance from
 * {@link com.vcfcf.adapter.VcfCfAdapter#getDiscoverer()}.
 *
 * <h3>Contract (spec/19 §6)</h3>
 * <ul>
 *   <li>Enumerate all resources of each kind that this adapter manages.
 *       Call {@link DiscoveryResult#addResource(com.integrien.alive.common.adapter3.config.ResourceConfig)}
 *       for each discovered resource.</li>
 *   <li>Honor {@link DiscoveryParam#getRegexp()} and
 *       {@link DiscoveryParam#getParams()} to scope the search when set.</li>
 *   <li>For resources that have disappeared since the last cycle, call
 *       {@link DiscoveryResult#changeResourceState} with
 *       {@code StateChangeEnum.NOTEXIST}.</li>
 *   <li>May attach initial relationships to {@code dr} via
 *       {@link DiscoveryResult#addRelationships(com.integrien.alive.common.adapter3.Relationships)}.</li>
 *   <li>Throw {@link InterruptedException} immediately if detected; the
 *       orchestrator will restore the interrupt flag and abort (§9).</li>
 * </ul>
 *
 * @param <C> the typed configuration POJO of the adapter
 */
public interface VcfCfDiscoverer<C> {

    /**
     * Perform a discovery cycle, populating {@code dr} with discovered resources.
     *
     * @param config     the typed configuration
     * @param httpClient the managed HTTP client (may be {@code null})
     * @param param      the discovery parameters (regexp, type, params)
     * @param dr         the result to populate; caller constructs and returns it
     * @throws InterruptedException if the thread is interrupted; callers must
     *                              restore the interrupt flag on catching this
     * @throws Exception            on any other failure; the orchestrator sets
     *                              an error message on the result and logs it
     */
    void discover(C config, ManagedHttpClient httpClient,
            DiscoveryParam param, DiscoveryResult dr)
            throws InterruptedException, Exception;
}
