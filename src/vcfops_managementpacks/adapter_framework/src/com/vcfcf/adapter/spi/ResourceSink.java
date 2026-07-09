package com.vcfcf.adapter.spi;

import com.integrien.alive.common.adapter3.config.ResourceConfig;

/**
 * Functional seam for the shared collect-path discovery enumeration.
 *
 * <p>An adapter that implements
 * {@link com.vcfcf.adapter.VcfCfAdapter#enumerateResources(ResourceSink)} can
 * feed the same enumeration body to two callers:
 *
 * <ul>
 *   <li><strong>Install-time discovery</strong> ({@code onDiscover()} path):
 *       the framework calls {@code enumerateResources(dr::addResource)}, wiring
 *       each enumerated resource directly into the {@code DiscoveryResult}.</li>
 *   <li><strong>Collect-path registration</strong> ({@code onCollect()} path):
 *       the framework calls
 *       {@code enumerateResources(this::registerNewResource)}, wiring each
 *       enumerated resource into the cycle's embedded {@code DiscoveryResult}
 *       via {@link com.vcfcf.adapter.VcfCfAdapter#registerNewResource(ResourceConfig)}.
 *       This is how VCF Ops 9.0.2 instances (where {@code onDiscover()} is never
 *       called) receive their initial resource set on the first collect cycle.</li>
 * </ul>
 *
 * <p>The one-body guarantee eliminates drift between the two discovery paths —
 * the cardinal correctness requirement of the dual-path discovery fix proven
 * in UniFi build 4.
 *
 * @see com.vcfcf.adapter.VcfCfAdapter#enumerateResources(ResourceSink)
 * @see com.vcfcf.adapter.VcfCfAdapter#discoverOnCollect()
 */
@FunctionalInterface
public interface ResourceSink {

    /**
     * Accept one enumerated resource.
     *
     * @param rc the {@link ResourceConfig} for the discovered resource; its
     *           {@link com.integrien.alive.common.adapter3.ResourceKey} must have
     *           at least one {@code IDENT_TYPE_IDENTIFYING} identifier so the
     *           platform can match the resource across cycles
     */
    void accept(ResourceConfig rc);
}
