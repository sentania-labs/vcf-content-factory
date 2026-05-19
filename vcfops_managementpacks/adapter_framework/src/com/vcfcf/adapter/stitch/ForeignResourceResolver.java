package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.Logger;
import com.integrien.alive.common.adapter3.ResourceKey;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;
import com.vmware.ops.api.model.resource.ResourceDto;
import com.vmware.tvs.vrealize.adapter.core.data.Resource;
import com.vmware.tvs.vrealize.adapter.core.extensions.suiteapi.SuiteAPIClient;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Universal cross-management-pack resource lookup.
 *
 * <p>Any adapter that needs to create relationships to resources owned by a
 * different adapter kind (VMWARE Datastores, HostSystems, VMs, or any other
 * MP) uses this class instead of hand-rolling the Suite API query pattern.
 *
 * <p>Modelled after Pure Storage's {@code VSphereResourceUtil} and the
 * {@code SuiteAPIClient.addVmParentBy*()} helpers, but generalised to any
 * adapter kind and any resource kind.
 *
 * <h3>Usage</h3>
 * <pre>{@code
 * // Construct once per collection cycle (or share across cycles with cache).
 * ForeignResourceResolver resolver =
 *     new ForeignResourceResolver(suiteAPIClient, logger);
 *
 * // Single lookup — cache is populated on first call per (ak, rk, id).
 * ResourceKey dsKey = resolver.findByIdentifier(
 *     "VMWARE", "Datastore", "DataStrorePath", "10.0.0.1/volume1/share1");
 * if (dsKey != null) {
 *     myResource.addParent(new Resource(dsKey));
 * }
 *
 * // Bulk load — cheaper when stitching many resources at once.
 * Map<String, ResourceKey> allDatastores =
 *     resolver.loadAll("VMWARE", "Datastore", "DataStrorePath");
 * }</pre>
 *
 * <h3>Caching</h3>
 * Results are cached by (adapterKind, resourceKind, identifierName) tuple.
 * The cache expires after {@link #DEFAULT_CACHE_TTL_SECONDS} (300 s) by
 * default.  Call {@link #setCacheTtlSeconds(int)} to override or
 * {@link #invalidateCache()} to flush manually (e.g. on re-discovery).
 *
 * <h3>ResourceDto → ResourceKey conversion</h3>
 * The conversion follows the Pure Storage {@code VSphereResourceUtil.mapResources()}
 * pattern: the {@link com.vmware.tvs.vrealize.adapter.core.data.Resource}
 * wrapper constructor translates the DTO-side identifier list into SDK
 * {@link ResourceIdentifierConfig} objects and builds the SDK
 * {@link ResourceKey} automatically.  We then extract identifiers from that
 * key to populate the lookup map.
 *
 * <h3>Thread safety</h3>
 * The cache is backed by a {@link ConcurrentHashMap}; cache entries carry a
 * timestamp and are re-fetched lazily on expiry.  Concurrent callers may
 * both trigger a re-fetch on the first miss, but the result is idempotent.
 */
public class ForeignResourceResolver {

    /** Default cache TTL: 5 minutes. */
    public static final int DEFAULT_CACHE_TTL_SECONDS = 300;

    private final SuiteAPIClient suiteApiClient;
    private final Logger logger;

    /** Milliseconds at which each cache entry expires. */
    private volatile long cacheTtlMs;

    /**
     * Cache: (adapterKind + ":" + resourceKind + ":" + identifierName)
     * → snapshot of (identifierValue → ResourceKey) + expiry timestamp.
     */
    private final ConcurrentHashMap<String, CacheEntry> cache = new ConcurrentHashMap<>();

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    /**
     * Create a resolver backed by the given Suite API client.
     *
     * @param suiteApiClient the {@link SuiteAPIClient} from
     *     {@code UnlicensedAdapter.suiteAPIClient}
     * @param logger         the adapter instance logger
     */
    public ForeignResourceResolver(SuiteAPIClient suiteApiClient, Logger logger) {
        if (suiteApiClient == null) {
            throw new IllegalArgumentException(
                    "ForeignResourceResolver: suiteApiClient must not be null");
        }
        if (logger == null) {
            throw new IllegalArgumentException(
                    "ForeignResourceResolver: logger must not be null");
        }
        this.suiteApiClient = suiteApiClient;
        this.logger = logger;
        this.cacheTtlMs = DEFAULT_CACHE_TTL_SECONDS * 1000L;
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /**
     * Find a single resource by one of its identifier values.
     *
     * <p>Calls {@link #loadAll(String, String, String)} (which returns a
     * cached map on subsequent calls within the TTL) and performs a map
     * lookup.
     *
     * @param adapterKind     the adapter kind key, e.g. {@code "VMWARE"}
     * @param resourceKind    the resource kind key, e.g. {@code "Datastore"}
     * @param identifierName  the identifier field name to index on,
     *                        e.g. {@code "DataStrorePath"}
     * @param identifierValue the value to look up
     * @return the matching {@link ResourceKey}, or {@code null} if not found
     */
    public ResourceKey findByIdentifier(String adapterKind, String resourceKind,
                                        String identifierName, String identifierValue) {
        Map<String, ResourceKey> index = loadAll(adapterKind, resourceKind, identifierName);
        ResourceKey key = index.get(identifierValue);
        if (key == null) {
            logger.debug("ForeignResourceResolver: no match for "
                    + adapterKind + "/" + resourceKind + "/" + identifierName
                    + " = " + identifierValue);
        }
        return key;
    }

    /**
     * Load all resources of the given kind and index them by the specified
     * identifier field.
     *
     * <p>On the first call (and after cache expiry) this fetches all
     * resources from the Suite API via
     * {@link SuiteAPIClient#getResources(List, List, List, List, List, List)}.
     * The response is converted to SDK {@link ResourceKey} objects using the
     * {@link Resource#Resource(ResourceDto)} constructor (which replicates the
     * Pure Storage {@code mapResources()} pattern), then indexed by the
     * requested identifier name.
     *
     * <p>Resources that do not carry the requested identifier are silently
     * skipped; the entry is not added to the returned map.
     *
     * @param adapterKind    the adapter kind key, e.g. {@code "VMWARE"}
     * @param resourceKind   the resource kind key, e.g. {@code "Datastore"}
     * @param identifierName the identifier field to use as the map key
     * @return an unmodifiable map of identifierValue → {@link ResourceKey};
     *         never {@code null}, may be empty
     */
    public Map<String, ResourceKey> loadAll(String adapterKind, String resourceKind,
                                            String identifierName) {
        String cacheKey = adapterKind + ":" + resourceKind + ":" + identifierName;
        CacheEntry entry = cache.get(cacheKey);

        if (entry == null || entry.isExpired()) {
            entry = fetchAndCache(cacheKey, adapterKind, resourceKind, identifierName);
        }

        return entry.index;
    }

    /**
     * Clear all cached entries immediately.
     *
     * <p>The next call to {@link #loadAll} or {@link #findByIdentifier}
     * will re-fetch from the Suite API.
     */
    public void invalidateCache() {
        cache.clear();
        logger.info("ForeignResourceResolver: cache invalidated");
    }

    /**
     * Override the cache TTL.
     *
     * @param seconds cache lifetime in seconds; must be &gt; 0
     * @throws IllegalArgumentException if {@code seconds} is not positive
     */
    public void setCacheTtlSeconds(int seconds) {
        if (seconds <= 0) {
            throw new IllegalArgumentException(
                    "ForeignResourceResolver: cacheTtlSeconds must be > 0, got " + seconds);
        }
        this.cacheTtlMs = seconds * 1000L;
        logger.info("ForeignResourceResolver: cache TTL set to " + seconds + "s");
    }

    // -----------------------------------------------------------------------
    // Internal helpers
    // -----------------------------------------------------------------------

    /**
     * Fetch resources from the Suite API, build the identifier index, and
     * store the result in the cache.
     *
     * <p>Uses {@link SuiteAPIClient#getResources(List, List, List, List, List, List)}
     * with {@code null} for resource-name filter, state filter,
     * data-collection-status filter, and UUID filter — meaning all resources
     * of the requested kind are returned (up to the Suite API's internal page
     * limit, which is typically 10 000).
     *
     * <p>ResourceDto → ResourceKey conversion follows the Pure Storage
     * {@code VSphereResourceUtil.mapResources()} pattern:
     * <ol>
     *   <li>Wrap each {@link ResourceDto} in a
     *       {@link Resource#Resource(ResourceDto)} to let aria-ops-core map
     *       the DTO-side identifiers into SDK
     *       {@link ResourceIdentifierConfig} objects.</li>
     *   <li>Call {@link Resource#getResourceKey()} to obtain the SDK
     *       {@link ResourceKey} (with all identifiers preserved).</li>
     *   <li>Scan {@link ResourceKey#getIdentifiers()} for the requested
     *       identifier name; if found, add to the index.</li>
     * </ol>
     */
    private CacheEntry fetchAndCache(String cacheKey,
                                     String adapterKind, String resourceKind,
                                     String identifierName) {
        logger.info("ForeignResourceResolver: loading "
                + adapterKind + "/" + resourceKind
                + " (identifier=" + identifierName + ") from Suite API");

        Map<String, ResourceKey> index = new HashMap<>();
        int total = 0;
        int matched = 0;

        try {
            List<ResourceDto> dtos = suiteApiClient.getResources(
                    Arrays.asList(adapterKind),   // adapterKinds
                    Arrays.asList(resourceKind),  // resourceKinds
                    null,                         // resource name filter (all)
                    null,                         // ResourceState filter (all)
                    null,                         // ResourceDataCollectionStatus filter (all)
                    null                          // UUID filter (all)
            );

            if (dtos != null) {
                for (ResourceDto dto : dtos) {
                    if (dto == null) continue;
                    total++;

                    /*
                     * Convert DTO → SDK ResourceKey.
                     *
                     * Resource(ResourceDto) is the same conversion path used
                     * internally by SuiteAPIClient.convertResourceDtoToResource().
                     * It iterates dto.getResourceKey().getResourceIdentifiers()
                     * and builds ResourceIdentifierConfig(name, value,
                     * isUniquelyIdentifying) for each one.
                     */
                    Resource resource = new Resource(dto);
                    ResourceKey key = resource.getResourceKey();
                    if (key == null) continue;

                    /*
                     * Scan the SDK identifiers for the one we were asked to
                     * index on.  A resource that does not carry the requested
                     * identifier name is skipped silently (warn is overkill
                     * for the normal case where some resources omit optional
                     * identifiers).
                     */
                    String idValue = null;
                    for (ResourceIdentifierConfig id : key.getIdentifiers()) {
                        if (identifierName.equals(id.getKey())) {
                            idValue = id.getValue();
                            break;
                        }
                    }

                    if (idValue != null && !idValue.isEmpty()) {
                        index.put(idValue, key);
                        matched++;
                    }
                }
            }

        } catch (Exception e) {
            logger.warn("ForeignResourceResolver: Suite API query failed for "
                    + adapterKind + "/" + resourceKind + ": " + e.getMessage(), e);
            // Return an empty (but cached) entry so we don't hammer the API
            // on every collection cycle when the target adapter is unavailable.
        }

        logger.info("ForeignResourceResolver: loaded " + adapterKind + "/" + resourceKind
                + " — " + total + " total, " + matched + " indexed by " + identifierName);

        CacheEntry entry = new CacheEntry(
                Collections.unmodifiableMap(index),
                System.currentTimeMillis() + cacheTtlMs);
        cache.put(cacheKey, entry);
        return entry;
    }

    // -----------------------------------------------------------------------
    // Cache entry
    // -----------------------------------------------------------------------

    private static final class CacheEntry {
        /** Unmodifiable identifier → ResourceKey index. */
        final Map<String, ResourceKey> index;
        /** Absolute expiry time in epoch milliseconds. */
        final long expiresAtMs;

        CacheEntry(Map<String, ResourceKey> index, long expiresAtMs) {
            this.index = index;
            this.expiresAtMs = expiresAtMs;
        }

        boolean isExpired() {
            return System.currentTimeMillis() >= expiresAtMs;
        }
    }
}
