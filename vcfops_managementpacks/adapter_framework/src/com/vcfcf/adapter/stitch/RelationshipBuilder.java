package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.ResourceKey;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;
import com.vmware.tvs.vrealize.adapter.core.data.Resource;
import com.vmware.tvs.vrealize.adapter.core.data.ResourceCollection;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Fluent helper for constructing parent/child relationship trees and
 * cross-adapter edges inside a {@code getRelationships()} implementation.
 *
 * <p>Eliminates the repetitive {@link ResourceKey} construction and
 * {@code addChild}/{@code addParent} boilerplate required by every
 * Tier 2 SDK adapter. Resources are deduplicated by (kind, idValue) so
 * calling {@link #resource(String, String, String, String)} twice for the
 * same object returns the same {@link ResourceHandle} without creating a
 * duplicate entry in the final collection.
 *
 * <p>Usage:
 * <pre>{@code
 * RelationshipBuilder rb = new RelationshipBuilder(ADAPTER_KIND);
 * ResourceHandle diskstation = rb.resource("SynologyDiskstation", serial, "serial", serial);
 * ResourceHandle pool        = rb.resource("SynologyStoragePool",  poolId, "pool_id", poolId);
 * ResourceHandle volume      = rb.resource("SynologyVolume",       volId,  "volume_id", volId);
 *
 * rb.parent(diskstation, pool)
 *   .parent(pool, volume)
 *   .parentForeign(datastoreKey, volume);
 *
 * return rb.build();
 * }</pre>
 *
 * <p>Only resources that participate in at least one relationship edge are
 * added to the returned {@link ResourceCollection}. Resources created via
 * {@link #resource(String, String, String, String)} but never passed to
 * {@link #parent}, {@link #parentForeign}, or {@link #childForeign} are
 * silently omitted from {@link #build()}.
 *
 * <p>Dependencies: {@code vrops-adapters-sdk-2.2.jar} and
 * {@code aria-ops-core-8.0.0.jar} only. No Suite API dependency.
 */
public final class RelationshipBuilder {

	private final String adapterKind;

	/**
	 * Cache of ResourceHandles keyed by "kind\0idValue" to prevent duplicate
	 * Resource objects for the same logical resource.
	 */
	private final Map<String, ResourceHandle> cache = new LinkedHashMap<>();

	/**
	 * Tracks which Resources have been involved in a relationship edge so that
	 * {@link #build()} only adds participating resources to the collection.
	 */
	private final Map<String, ResourceHandle> participants = new LinkedHashMap<>();

	/**
	 * Create a builder for the given adapter kind.
	 *
	 * @param adapterKind the adapter kind key (must match {@code KINDKEY} in
	 *                    {@code adapter.properties} and the root
	 *                    {@code <AdapterKind>} key in {@code describe.xml})
	 */
	public RelationshipBuilder(String adapterKind) {
		if (adapterKind == null || adapterKind.isEmpty()) {
			throw new IllegalArgumentException("adapterKind must not be null or empty");
		}
		this.adapterKind = adapterKind;
	}

	// -----------------------------------------------------------------------
	// Resource handle factory
	// -----------------------------------------------------------------------

	/**
	 * Look up or create an internal resource (same adapter kind as this builder).
	 *
	 * <p>Calls with the same {@code resourceKind} and {@code idValue} return the
	 * same {@link ResourceHandle}; the underlying {@link Resource} and
	 * {@link ResourceKey} objects are created once and reused.
	 *
	 * @param resourceKind the resource kind key (must match a ResourceKind
	 *                     declared in {@code describe.xml})
	 * @param name         the human-readable display name of this resource
	 *                     instance (shown in the VCF Ops object browser)
	 * @param idKey        the identifier key that uniquely identifies the
	 *                     resource within its kind (must match a
	 *                     {@code ResourceIdentifier} declared in
	 *                     {@code describe.xml} with {@code isPartOfUniqueness})
	 * @param idValue      the identifier value (used as the cache key together
	 *                     with {@code resourceKind})
	 * @return a {@link ResourceHandle} wrapping the {@link Resource} and its
	 *         {@link ResourceKey}
	 */
	public ResourceHandle resource(String resourceKind, String name,
			String idKey, String idValue) {
		String cacheKey = resourceKind + '\0' + idValue;
		ResourceHandle existing = cache.get(cacheKey);
		if (existing != null) {
			return existing;
		}

		ResourceKey key = new ResourceKey(adapterKind, resourceKind, name);
		key.addIdentifier(new ResourceIdentifierConfig(idKey, idValue, true));

		Resource res = new Resource(key);
		ResourceHandle handle = new ResourceHandle(key, res);
		cache.put(cacheKey, handle);
		return handle;
	}

	// -----------------------------------------------------------------------
	// Relationship mutators
	// -----------------------------------------------------------------------

	/**
	 * Add a parent → child edge between two internal resources.
	 *
	 * <p>Internally calls {@code parent.getResource().addChild(child.getResource())}
	 * which also registers the reciprocal parent link on the child side (the SDK
	 * maintains both directions). Both resources are marked as participants and
	 * will appear in the {@link ResourceCollection} returned by {@link #build()}.
	 *
	 * @param parent the parent resource handle
	 * @param child  the child resource handle
	 * @return {@code this} for method chaining
	 */
	public RelationshipBuilder parent(ResourceHandle parent, ResourceHandle child) {
		parent.resource.addChild(child.resource);
		markParticipant(parent);
		markParticipant(child);
		return this;
	}

	/**
	 * Add a cross-adapter parent edge: the foreign resource (from another
	 * adapter kind) becomes the parent of the given internal child.
	 *
	 * <p>A transient {@link Resource} is created from {@code foreignParent} so
	 * the SDK can represent the edge without requiring the foreign adapter's
	 * full object graph. The foreign resource is NOT added to the collection
	 * by {@link #build()} — only the internal child is. The platform resolves
	 * the cross-adapter edge at topology-build time.
	 *
	 * @param foreignParent a {@link ResourceKey} obtained from
	 *                      {@code ForeignResourceResolver} (or equivalent) that
	 *                      identifies the parent resource in another adapter kind
	 * @param child         the internal child resource
	 * @return {@code this} for method chaining
	 */
	public RelationshipBuilder parentForeign(ResourceKey foreignParent, ResourceHandle child) {
		Resource foreignResource = new Resource(foreignParent);
		child.resource.addParent(foreignResource);
		markParticipant(child);
		return this;
	}

	/**
	 * Add a cross-adapter child edge: the given internal parent gets a foreign
	 * child resource (from another adapter kind).
	 *
	 * <p>A transient {@link Resource} is created from {@code foreignChild}. The
	 * internal parent is added to the collection by {@link #build()}; the foreign
	 * child is not. The platform resolves the cross-adapter edge at
	 * topology-build time.
	 *
	 * @param parent       the internal parent resource
	 * @param foreignChild a {@link ResourceKey} identifying the child resource
	 *                     in another adapter kind
	 * @return {@code this} for method chaining
	 */
	public RelationshipBuilder childForeign(ResourceHandle parent, ResourceKey foreignChild) {
		Resource foreignResource = new Resource(foreignChild);
		parent.resource.addChild(foreignResource);
		markParticipant(parent);
		return this;
	}

	// -----------------------------------------------------------------------
	// Build
	// -----------------------------------------------------------------------

	/**
	 * Build the {@link ResourceCollection} for return from
	 * {@code getRelationships()}.
	 *
	 * <p>Only resources that have participated in at least one relationship edge
	 * (via {@link #parent}, {@link #parentForeign}, or {@link #childForeign}) are
	 * added. Resources created via {@link #resource} that were never wired into
	 * an edge are omitted. Each participating resource is added once via
	 * {@link ResourceCollection#add(Resource)}, which also enqueues its relatives.
	 *
	 * @return a populated {@link ResourceCollection} ready to return from
	 *         {@code getRelationships()}
	 */
	public ResourceCollection build() {
		ResourceCollection collection = new ResourceCollection();
		for (ResourceHandle handle : participants.values()) {
			collection.add(handle.resource);
		}
		return collection;
	}

	// -----------------------------------------------------------------------
	// Internal helpers
	// -----------------------------------------------------------------------

	private void markParticipant(ResourceHandle handle) {
		// Use the ResourceKey's toString as the participants map key;
		// it is guaranteed unique per (adapterKind, resourceKind, identifiers).
		String k = handle.key.toString();
		participants.putIfAbsent(k, handle);
	}

	// -----------------------------------------------------------------------
	// ResourceHandle inner class
	// -----------------------------------------------------------------------

	/**
	 * Opaque handle returned by {@link RelationshipBuilder#resource}. Exposes
	 * the underlying {@link ResourceKey} and {@link Resource} for callers that
	 * need to interrogate them (e.g. to retrieve the key for cross-builder use).
	 *
	 * <p>Do not instantiate directly; obtain instances from
	 * {@link RelationshipBuilder#resource}.
	 */
	public static final class ResourceHandle {

		private final ResourceKey key;
		private final Resource resource;

		private ResourceHandle(ResourceKey key, Resource resource) {
			this.key = key;
			this.resource = resource;
		}

		/**
		 * Return the {@link ResourceKey} for this handle.
		 *
		 * <p>Useful when you need to pass this resource's key to another builder
		 * or to {@link RelationshipBuilder#parentForeign} /
		 * {@link RelationshipBuilder#childForeign} of a different builder.
		 */
		public ResourceKey getKey() {
			return key;
		}

		/**
		 * Return the underlying {@link Resource} object.
		 *
		 * <p>Prefer using the fluent builder methods rather than manipulating the
		 * resource directly; this accessor exists for advanced use cases such as
		 * attaching metric data alongside relationship data.
		 */
		public Resource getResource() {
			return resource;
		}
	}
}
