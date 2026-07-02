package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.Relationships;
import com.integrien.alive.common.adapter3.ResourceKey;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * v2 — Fluent helper for constructing parent/child relationship trees and
 * cross-adapter edges, returning a SDK {@link Relationships} object.
 *
 * <p>v2 removes the {@code aria-ops-core} dependency ({@code Resource} /
 * {@code ResourceCollection}). All output is in terms of the SDK's own
 * {@link Relationships} API, which is the correct attachment point for
 * {@link com.integrien.alive.common.adapter3.CollectResult#addRelationships}
 * (spec/19 §3).
 *
 * <p>Usage:
 * <pre>{@code
 * RelationshipBuilder rb = new RelationshipBuilder(ADAPTER_KIND);
 * ResourceKey diskstation = rb.resource("SynologyDiskstation", "DS1520+ ABC", "serial", serial);
 * ResourceKey pool        = rb.resource("SynologyStoragePool",  "Pool 1",      "pool_id", poolId);
 * ResourceKey volume      = rb.resource("SynologyVolume",        "Volume 1",    "volume_id", volId);
 *
 * rb.parent(diskstation, pool)
 *   .parent(pool, volume)
 *   .parentForeign(datastoreKey, volume);
 *
 * Relationships rels = rb.build();
 * adapter.addRelationshipsToCurrentCycle(rels);
 * }</pre>
 *
 * <h3>Full-set vs delta semantics (spec/19 §3)</h3>
 * {@link #build()} produces a {@link Relationships} object that emits one
 * relationship call per parent, and the write verb depends on parent
 * ownership:
 * <ul>
 *   <li><strong>Own-adapter parents</strong> (registered via {@link #parent})
 *       keep the consolidated {@link Relationships#setRelationships(ResourceKey, Collection)}
 *       full-child-set replacement — one call per parent per cycle.</li>
 *   <li><strong>Foreign parents</strong> (registered via {@link #parentForeign})
 *       are emitted <strong>additively</strong> via
 *       {@link Relationships#addRelationships(ResourceKey, Collection)} — never
 *       full-set. This matches the uniformly-additive vendor TVS corpus
 *       (see {@code context/api-maps/tvs-cross-mp-stitching.md}) and is
 *       clobber-safe on any platform version, independent of any
 *       per-adapter {@code setRelationships} scoping assumption.</li>
 * </ul>
 * The split is by parent ownership only — it is not a global default flip.
 * Use {@link #buildDelta(boolean)} directly when you need explicit add/remove
 * deltas for own-adapter parents too.
 *
 * <h3>Relationship cap</h3>
 * {@link #build()} enforces the supplied cap (default
 * {@link com.vcfcf.adapter.VcfCfAdapter#MAX_RELATIONSHIPS_PER_CYCLE}).
 * Relationships beyond the cap are silently dropped and a count is returned
 * from {@link BuildResult#droppedEdges()}.
 *
 * <p>Dependencies: {@code vrops-adapters-sdk-2.2.jar} only.
 */
public final class RelationshipBuilder {

    private final String adapterKind;
    private final int maxEdges;

    /**
     * Parent → ordered list of children (insertion order preserved per parent).
     * Key = ResourceKey.toString() of the parent.
     */
    private final Map<String, ParentEntry> parentMap = new LinkedHashMap<>();

    /**
     * Cache of ResourceKeys keyed by "kind\0idValue" to deduplicate lookups.
     */
    private final Map<String, ResourceKey> keyCache = new LinkedHashMap<>();

    // -----------------------------------------------------------------------
    // Constructors
    // -----------------------------------------------------------------------

    /**
     * Create a builder for the given adapter kind with the default edge cap.
     *
     * @param adapterKind the adapter kind key (must match {@code KINDKEY} in
     *                    {@code adapter.properties} and the root
     *                    {@code <AdapterKind>} key in {@code describe.xml})
     */
    public RelationshipBuilder(String adapterKind) {
        this(adapterKind, com.vcfcf.adapter.VcfCfAdapter.MAX_RELATIONSHIPS_PER_CYCLE);
    }

    /**
     * Create a builder for the given adapter kind with a custom edge cap.
     *
     * @param adapterKind the adapter kind key
     * @param maxEdges    maximum number of child-key edges across all parents;
     *                    must be &gt; 0
     */
    public RelationshipBuilder(String adapterKind, int maxEdges) {
        if (adapterKind == null || adapterKind.isEmpty()) {
            throw new IllegalArgumentException("adapterKind must not be null or empty");
        }
        if (maxEdges <= 0) {
            throw new IllegalArgumentException("maxEdges must be > 0");
        }
        this.adapterKind = adapterKind;
        this.maxEdges = maxEdges;
    }

    // -----------------------------------------------------------------------
    // ResourceKey factory
    // -----------------------------------------------------------------------

    /**
     * Look up or create a {@link ResourceKey} for an internal resource (same
     * adapter kind as this builder).
     *
     * <p>Calls with the same {@code resourceKind} and {@code idValue} return the
     * same {@link ResourceKey} instance (deduplication by cache key).
     *
     * @param resourceKind the resource kind key (must match a ResourceKind
     *                     declared in {@code describe.xml})
     * @param name         the human-readable display name of this resource
     * @param idKey        the identifying identifier key (must match a
     *                     {@code ResourceIdentifier} with
     *                     {@code isPartOfUniqueness=true} in describe.xml)
     * @param idValue      the identifier value (used as cache key together
     *                     with {@code resourceKind})
     * @return a {@link ResourceKey} with one identifying identifier
     */
    public ResourceKey resource(String resourceKind, String name,
            String idKey, String idValue) {
        String cacheKey = resourceKind + '\0' + idValue;
        ResourceKey existing = keyCache.get(cacheKey);
        if (existing != null) {
            return existing;
        }
        ResourceKey key = new ResourceKey(name, resourceKind, adapterKind);
        key.addIdentifier(new ResourceIdentifierConfig(idKey, idValue, true));
        keyCache.put(cacheKey, key);
        return key;
    }

    // -----------------------------------------------------------------------
    // Relationship mutators
    // -----------------------------------------------------------------------

    /**
     * Add a parent → child edge.
     *
     * @param parent the parent {@link ResourceKey}
     * @param child  the child {@link ResourceKey}
     * @return {@code this} for method chaining
     */
    public RelationshipBuilder parent(ResourceKey parent, ResourceKey child) {
        getOrCreateEntry(parent).children.add(child);
        return this;
    }

    /**
     * Add a cross-adapter parent edge: the foreign resource (from another
     * adapter kind) becomes the parent of {@code child}.
     *
     * <p>The child is registered as having a foreign parent. Because the
     * parent belongs to another adapter's tree, {@link #build()} emits this
     * edge <strong>additively</strong> via
     * {@link Relationships#addRelationships(ResourceKey, Collection)} —
     * never {@code setRelationships} — so it can never clobber sibling
     * children reported by other adapters onto the same foreign parent.
     *
     * @param foreignParent a {@link ResourceKey} from another adapter kind
     * @param child         the internal child
     * @return {@code this} for method chaining
     */
    public RelationshipBuilder parentForeign(ResourceKey foreignParent, ResourceKey child) {
        ParentEntry entry = getOrCreateEntry(foreignParent);
        entry.foreignParent = true;
        entry.children.add(child);
        return this;
    }

    /**
     * Add a cross-adapter child edge: {@code parent} gets a foreign child.
     *
     * @param parent       the internal parent
     * @param foreignChild a {@link ResourceKey} from another adapter kind
     * @return {@code this} for method chaining
     */
    public RelationshipBuilder childForeign(ResourceKey parent, ResourceKey foreignChild) {
        getOrCreateEntry(parent).children.add(foreignChild);
        return this;
    }

    /**
     * Add a typed/labeled relationship edge (generic relationship).
     *
     * @param parent    the parent resource
     * @param children  the child resources
     * @param label     the edge label (e.g., {@code "depends_on"})
     * @param namespace namespace to avoid cross-MP label collision; may be
     *                  {@code null}
     * @return {@code this} for method chaining
     */
    public RelationshipBuilder generic(ResourceKey parent,
            Collection<ResourceKey> children,
            String label, String namespace) {
        getOrCreateEntry(parent).genericChildren.add(
                new GenericEdge(new ArrayList<>(children), label, namespace));
        return this;
    }

    // -----------------------------------------------------------------------
    // Build
    // -----------------------------------------------------------------------

    /**
     * Build a {@link Relationships} object, one call per parent.
     *
     * <p>Own-adapter parents (registered via {@link #parent}) use full-set
     * semantics ({@link Relationships#setRelationships}, spec/19 §3) so the
     * platform can diff against current state. Foreign parents (registered
     * via {@link #parentForeign}) use additive semantics
     * ({@link Relationships#addRelationships}) so they never clobber
     * sibling children reported by other adapters onto the same foreign
     * parent. Edges beyond {@link #maxEdges} are dropped silently.
     *
     * @return the populated {@link Relationships} object
     */
    public Relationships build() {
        return doBuild(false);
    }

    /**
     * Build a {@link Relationships} object using delta semantics.
     *
     * <p>Use only when you know the incremental change (spec/19 §3 "delta").
     *
     * @param remove if {@code true} generate remove-relationship calls;
     *               if {@code false} generate add-relationship calls
     * @return the populated {@link Relationships} object
     */
    public Relationships buildDelta(boolean remove) {
        Relationships rels = new Relationships();
        rels.setTimestamp(System.currentTimeMillis());
        int edgeCount = 0;
        for (ParentEntry entry : parentMap.values()) {
            if (edgeCount >= maxEdges) break;
            List<ResourceKey> batch = new ArrayList<>();
            for (ResourceKey child : entry.children) {
                if (edgeCount >= maxEdges) break;
                batch.add(child);
                edgeCount++;
            }
            if (!batch.isEmpty()) {
                if (remove) {
                    rels.removeRelationships(entry.parent, batch);
                } else {
                    rels.addRelationships(entry.parent, batch);
                }
            }
            for (GenericEdge ge : entry.genericChildren) {
                if (edgeCount >= maxEdges) break;
                List<ResourceKey> gbatch = new ArrayList<>();
                for (ResourceKey child : ge.children) {
                    if (edgeCount >= maxEdges) break;
                    gbatch.add(child);
                    edgeCount++;
                }
                if (!gbatch.isEmpty()) {
                    if (ge.namespace != null) {
                        if (remove) {
                            rels.removeGenericRelationships(entry.parent, gbatch,
                                    ge.label, ge.namespace);
                        } else {
                            rels.addGenericRelationship(entry.parent, gbatch,
                                    ge.label, ge.namespace);
                        }
                    } else {
                        if (remove) {
                            rels.removeGenericRelationships(entry.parent, gbatch, ge.label);
                        } else {
                            rels.addGenericRelationship(entry.parent, gbatch, ge.label);
                        }
                    }
                }
            }
        }
        return rels;
    }

    // -----------------------------------------------------------------------
    // Internal helpers
    // -----------------------------------------------------------------------

    private Relationships doBuild(boolean unused) {
        Relationships rels = new Relationships();
        rels.setTimestamp(System.currentTimeMillis());
        int edgeCount = 0;
        for (ParentEntry entry : parentMap.values()) {
            if (edgeCount >= maxEdges) break;
            List<ResourceKey> batch = new ArrayList<>();
            for (ResourceKey child : entry.children) {
                if (edgeCount >= maxEdges) break;
                batch.add(child);
                edgeCount++;
            }
            if (!batch.isEmpty()) {
                if (entry.foreignParent) {
                    // Foreign parent: additive only — never clobber sibling
                    // children reported by other adapters onto this parent.
                    rels.addRelationships(entry.parent, batch);
                } else {
                    // Own-adapter parent: consolidated full-set replacement.
                    rels.setRelationships(entry.parent, batch);
                }
            }
            for (GenericEdge ge : entry.genericChildren) {
                if (edgeCount >= maxEdges) break;
                List<ResourceKey> gbatch = new ArrayList<>();
                for (ResourceKey child : ge.children) {
                    if (edgeCount >= maxEdges) break;
                    gbatch.add(child);
                    edgeCount++;
                }
                if (!gbatch.isEmpty()) {
                    if (entry.foreignParent) {
                        if (ge.namespace != null) {
                            rels.addGenericRelationship(entry.parent, gbatch,
                                    ge.label, ge.namespace);
                        } else {
                            rels.addGenericRelationship(entry.parent, gbatch, ge.label);
                        }
                    } else {
                        if (ge.namespace != null) {
                            rels.setGenericRelationships(entry.parent, gbatch,
                                    ge.label, ge.namespace);
                        } else {
                            rels.setGenericRelationships(entry.parent, gbatch, ge.label);
                        }
                    }
                }
            }
        }
        return rels;
    }

    private ParentEntry getOrCreateEntry(ResourceKey parent) {
        String k = parent.toString();
        ParentEntry entry = parentMap.get(k);
        if (entry == null) {
            entry = new ParentEntry(parent);
            parentMap.put(k, entry);
        }
        return entry;
    }

    // -----------------------------------------------------------------------
    // Internal data types
    // -----------------------------------------------------------------------

    private static final class ParentEntry {
        final ResourceKey parent;
        final List<ResourceKey> children = new ArrayList<>();
        final List<GenericEdge> genericChildren = new ArrayList<>();

        /**
         * {@code true} once this parent has been registered via
         * {@link RelationshipBuilder#parentForeign} — routes {@link #build()}
         * to the additive write verb for this entry instead of full-set.
         */
        boolean foreignParent = false;

        ParentEntry(ResourceKey parent) {
            this.parent = parent;
        }
    }

    private static final class GenericEdge {
        final List<ResourceKey> children;
        final String label;
        final String namespace; // nullable

        GenericEdge(List<ResourceKey> children, String label, String namespace) {
            this.children = children;
            this.label = label;
            this.namespace = namespace;
        }
    }
}
