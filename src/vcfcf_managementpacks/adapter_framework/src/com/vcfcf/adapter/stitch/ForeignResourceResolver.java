package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.Logger;
import com.integrien.alive.common.adapter3.ResourceKey;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;

import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * v2 — Cross-management-pack resource lookup.
 *
 * <p>v2 removes the {@code aria-ops-core} compile dependency
 * ({@code SuiteAPIClient}, {@code ResourceDto}).
 * This class now operates through a pluggable {@link SuiteApiBridge} functional
 * interface so adapters that carry a Suite API client can wire it in without
 * forcing the framework to compile against any TVS / Suite-API artifact.
 *
 * <p>The Suite API is an <em>optional extension</em> (spec/19 §10) — it is not
 * required on the collect path. Adapters that do cross-MP stitching (e.g.,
 * Datastore or HostSystem relationships) use this class; adapters that do not
 * need foreign resources simply never instantiate it.
 *
 * <h3>Usage</h3>
 * <pre>{@code
 * // Wire in the Suite API client from your adapter's configure() step:
 * ForeignResourceResolver resolver = new ForeignResourceResolver(
 *     (adapterKinds, resourceKinds) -> {
 *         // Call your Suite API client here and return a list of
 *         // ForeignResourceResolver.ResourceEntry objects.
 *         return myClient.listResources(adapterKinds, resourceKinds);
 *     },
 *     logInfo -> logAdapter.info(logInfo));
 *
 * // Single lookup:
 * ResourceKey dsKey = resolver.findByIdentifier(
 *     "VMWARE", "Datastore", "DataStrorePath", "10.0.0.1/vol/share");
 *
 * // Bulk load:
 * Map<String, ResourceKey> allDatastores =
 *     resolver.loadAll("VMWARE", "Datastore", "DataStrorePath");
 * }</pre>
 *
 * <h3>Caching</h3>
 * Results are cached by (adapterKind, resourceKind, identifierName) tuple
 * for {@link #DEFAULT_CACHE_TTL_SECONDS} (300 s). Override with
 * {@link #setCacheTtlSeconds(int)} or flush with {@link #invalidateCache()}.
 *
 * <h3>Thread safety</h3>
 * Cache backed by {@link ConcurrentHashMap}; concurrent re-fetches on expiry
 * are idempotent.
 */
public final class ForeignResourceResolver {

    /** Default cache TTL: 5 minutes. */
    public static final int DEFAULT_CACHE_TTL_SECONDS = 300;

    // -----------------------------------------------------------------------
    // SPI bridge — adapter supplies the actual Suite API call
    // -----------------------------------------------------------------------

    /**
     * Lightweight data record representing one foreign resource.
     * Populated by the adapter's {@link SuiteApiBridge} implementation.
     */
    public static final class ResourceEntry {
        /** Adapter kind of this resource (e.g., {@code "VMWARE"}). */
        public final String adapterKind;
        /** Resource kind of this resource (e.g., {@code "Datastore"}). */
        public final String resourceKind;
        /** Display name. */
        public final String name;
        /** List of identifiers: each element is {@code [key, value, isUnique]}. */
        public final List<String[]> identifiers;

        /**
         * @param adapterKind  adapter kind
         * @param resourceKind resource kind
         * @param name         display name
         * @param identifiers  list of {@code [key, value, isUnique]} triples
         */
        public ResourceEntry(String adapterKind, String resourceKind,
                String name, List<String[]> identifiers) {
            this.adapterKind = adapterKind;
            this.resourceKind = resourceKind;
            this.name = name;
            this.identifiers = identifiers != null ? identifiers : Collections.emptyList();
        }
    }

    /**
     * Functional interface through which the adapter provides Suite API access.
     *
     * <p>Implement this using whatever Suite API client artifact is available in
     * the adapter's pak (e.g., a bundled {@code vcops-suiteapi-client.jar}).
     * The framework does not compile against any Suite API artifact — this
     * interface is the clean boundary.
     */
    @FunctionalInterface
    public interface SuiteApiBridge {
        /**
         * List all resources of the given adapter/resource kind.
         *
         * @param adapterKind  the adapter kind to query
         * @param resourceKind the resource kind to query
         * @return list of entries; may be empty, must not be {@code null}
         * @throws Exception on Suite API failure
         */
        List<ResourceEntry> listResources(String adapterKind, String resourceKind)
                throws Exception;
    }

    // -----------------------------------------------------------------------
    // Fields
    // -----------------------------------------------------------------------

    private final SuiteApiBridge bridge;
    private final Logger logger;
    private volatile long cacheTtlMs;
    private final ConcurrentHashMap<String, CacheEntry> cache =
            new ConcurrentHashMap<>();

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    /**
     * Create a resolver backed by the given Suite API bridge.
     *
     * @param bridge the Suite API bridge provided by the adapter
     * @param logger the adapter instance logger
     */
    public ForeignResourceResolver(SuiteApiBridge bridge, Logger logger) {
        if (bridge == null) {
            throw new IllegalArgumentException(
                    "ForeignResourceResolver: bridge must not be null");
        }
        if (logger == null) {
            throw new IllegalArgumentException(
                    "ForeignResourceResolver: logger must not be null");
        }
        this.bridge = bridge;
        this.logger = logger;
        this.cacheTtlMs = DEFAULT_CACHE_TTL_SECONDS * 1000L;
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /**
     * Find a single resource by one of its identifier values.
     *
     * @param adapterKind     the adapter kind key, e.g. {@code "VMWARE"}
     * @param resourceKind    the resource kind key, e.g. {@code "Datastore"}
     * @param identifierName  the identifier field name to index on
     * @param identifierValue the value to look up
     * @return the matching {@link ResourceKey}, or {@code null} if not found
     */
    public ResourceKey findByIdentifier(String adapterKind, String resourceKind,
            String identifierName, String identifierValue) {
        Map<String, ResourceKey> index = loadAll(adapterKind, resourceKind,
                identifierName);
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
     * @param adapterKind    the adapter kind key
     * @param resourceKind   the resource kind key
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

    /** Clear all cached entries immediately. */
    public void invalidateCache() {
        cache.clear();
        logger.info("ForeignResourceResolver: cache invalidated");
    }

    /**
     * Override the cache TTL.
     *
     * @param seconds cache lifetime in seconds; must be &gt; 0
     */
    public void setCacheTtlSeconds(int seconds) {
        if (seconds <= 0) {
            throw new IllegalArgumentException(
                    "ForeignResourceResolver: cacheTtlSeconds must be > 0, got "
                    + seconds);
        }
        this.cacheTtlMs = seconds * 1000L;
        logger.info("ForeignResourceResolver: cache TTL set to " + seconds + "s");
    }

    // -----------------------------------------------------------------------
    // Internal helpers
    // -----------------------------------------------------------------------

    private CacheEntry fetchAndCache(String cacheKey,
            String adapterKind, String resourceKind, String identifierName) {
        logger.info("ForeignResourceResolver: loading "
                + adapterKind + "/" + resourceKind
                + " (identifier=" + identifierName + ")");

        Map<String, ResourceKey> index = new HashMap<>();
        int total = 0;
        int matched = 0;

        try {
            List<ResourceEntry> entries = bridge.listResources(adapterKind, resourceKind);
            if (entries != null) {
                for (ResourceEntry e : entries) {
                    if (e == null) continue;
                    total++;

                    // Build a ResourceKey from the entry's identifier list.
                    // Correct order: ResourceKey(resourceName, resourceKind, adapterKind)
                    ResourceKey key = new ResourceKey(
                            e.name, e.resourceKind, e.adapterKind);
                    String idValue = null;
                    for (String[] id : e.identifiers) {
                        if (id == null || id.length < 2) continue;
                        boolean isUnique = id.length >= 3 && Boolean.parseBoolean(id[2]);
                        key.addIdentifier(new ResourceIdentifierConfig(
                                id[0], id[1], isUnique));
                        if (identifierName.equals(id[0])) {
                            idValue = id[1];
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
            // Return a (short-lived) empty entry to avoid hammering the API.
        }

        logger.info("ForeignResourceResolver: loaded " + adapterKind + "/"
                + resourceKind + " — " + total + " total, " + matched
                + " indexed by " + identifierName);

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
        final Map<String, ResourceKey> index;
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
