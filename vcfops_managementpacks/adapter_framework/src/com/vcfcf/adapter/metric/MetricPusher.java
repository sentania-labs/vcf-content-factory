package com.vcfcf.adapter.metric;

import com.integrien.alive.common.adapter3.AdapterBase;
import com.integrien.alive.common.adapter3.MetricData;
import com.integrien.alive.common.adapter3.MetricKey;
import com.integrien.alive.common.adapter3.config.ResourceConfig;

import java.util.ArrayList;
import java.util.List;

/**
 * Fluent helper for pushing metrics and properties to the SDK's
 * {@link AdapterBase} data pipeline.
 *
 * <p>Usage:
 * <pre>{@code
 * new MetricPusher(adapterBase)
 *     .forResource(resourceConfig)
 *     .metric("CPU|usage", 42.5)
 *     .metric("MEM|used_mb", 1024.0)
 *     .property("hostname", "nas-01")
 *     .push();
 * }</pre>
 *
 * <p>Call {@link #forResource(ResourceConfig)} to begin a fluent chain for
 * a specific resource. {@link ResourceContext#push()} commits the accumulated
 * metrics and properties to the adapter. All calls to {@code metric()} and
 * {@code property()} are batched and sent in a single call per resource.
 */
public final class MetricPusher {

	private final AdapterBase adapter;

	/**
	 * @param adapter the {@link AdapterBase} instance (typically {@code this} in
	 *                your {@code onCollect()} implementation)
	 */
	public MetricPusher(AdapterBase adapter) {
		this.adapter = adapter;
	}

	/**
	 * Begin a fluent chain for the given resource.
	 *
	 * @param resource the resource to push data to
	 * @return a {@link ResourceContext} for accumulating metrics and properties
	 */
	public ResourceContext forResource(ResourceConfig resource) {
		return new ResourceContext(adapter, resource);
	}

	/**
	 * Fluent context for a single resource's metrics and properties.
	 */
	public static final class ResourceContext {

		private final AdapterBase adapter;
		private final ResourceConfig resource;
		private final List<MetricData> metrics = new ArrayList<>();
		private final List<MetricData> properties = new ArrayList<>();

		private ResourceContext(AdapterBase adapter, ResourceConfig resource) {
			this.adapter = adapter;
			this.resource = resource;
		}

		/**
		 * Add a numeric metric.
		 *
		 * @param key   the metric key (pipe-delimited, matching describe.xml group path)
		 * @param value the numeric value
		 */
		public ResourceContext metric(String key, double value) {
			MetricData md = new MetricData(new MetricKey(key), System.currentTimeMillis(), value);
			metrics.add(md);
			return this;
		}

		/**
		 * Add a string property.
		 *
		 * <p><strong>Uses {@code new MetricKey(true, key)}</strong> to set
		 * {@code isProperty=true}. The convenience overload
		 * {@code new MetricKey(key)} hardcodes {@code isProperty=false}; the
		 * platform silently discards string values on non-property MetricKeys.
		 *
		 * @param key   the property key (pipe-delimited, matching describe.xml)
		 * @param value the string value
		 */
		public ResourceContext property(String key, String value) {
			MetricData md = new MetricData(new MetricKey(true, key),
					System.currentTimeMillis(), value);
			properties.add(md);
			return this;
		}

		/**
		 * Add a numeric property (isProperty=true in describe.xml).
		 *
		 * <p>Uses {@code new MetricKey(true, key)} so the platform treats this
		 * as a property (change-only delivery) rather than a per-cycle metric.
		 *
		 * @param key   the property key
		 * @param value the numeric value
		 */
		public ResourceContext numericProperty(String key, double value) {
			MetricData md = new MetricData(new MetricKey(true, key),
					System.currentTimeMillis(), value);
			properties.add(md);
			return this;
		}

		/**
		 * Commit accumulated metrics and properties to the adapter.
		 * Safe to call multiple times; each call re-sends the current batch.
		 */
		public void push() {
			if (!metrics.isEmpty()) {
				adapter.addMetricData(resource, metrics);
			}
			if (!properties.isEmpty()) {
				// boolean true = isProperty
				adapter.addMetricData(resource, properties, true);
			}
		}
	}
}
