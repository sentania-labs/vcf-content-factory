package com.vcfcf.adapters.helloworld;

import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.metric.MetricPusher;

import com.integrien.alive.common.adapter3.DiscoveryParam;
import com.integrien.alive.common.adapter3.ResourceKey;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.TestParam;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;
import com.vmware.tvs.vrealize.adapter.core.collection.CollectionException;
import com.vmware.tvs.vrealize.adapter.core.collection.historical.HistoricalCollector;
import com.vmware.tvs.vrealize.adapter.core.collection.live.LiveCollector;
import com.vmware.tvs.vrealize.adapter.core.data.Resource;
import com.vmware.tvs.vrealize.adapter.core.data.ResourceCollection;
import com.vmware.tvs.vrealize.adapter.core.discovery.Discoverer;
import com.vmware.tvs.vrealize.adapter.core.test.TestException;
import com.vmware.tvs.vrealize.adapter.core.test.Tester;

import java.util.concurrent.atomic.AtomicLong;

/**
 * Hello World Tier 2 SDK adapter — Phase 1 validation gate.
 *
 * <p>Validates the full VCF-CF Tier 2 build pipeline:
 * <ul>
 *   <li>Framework JAR (vcfcf-adapter-base.jar) compiles and loads correctly</li>
 *   <li>sdk_builder.py produces a valid .pak structure</li>
 *   <li>describe.xml declares resources, credentials, identifiers, attributes</li>
 * </ul>
 *
 * <p>Collection behaviour:
 * <ul>
 *   <li>Discoverer emits 1 {@code HelloResource} with identifier {@code id=hello-1}</li>
 *   <li>LiveCollector pushes 1 metric ({@code tickCount}) and 1 property ({@code greeting})</li>
 *   <li>No real HTTP calls — suitable for offline testing</li>
 * </ul>
 */
public final class HelloWorldAdapter extends VcfCfAdapter<HelloWorldConfig> {

	/** Adapter kind key — MUST match KINDKEY in adapter.properties and describe.xml. */
	private static final String ADAPTER_KIND = "hello_world";

	/** Monotonically increasing counter to prove metrics change each cycle. */
	private final AtomicLong tickCount = new AtomicLong(0);

	@Override
	protected String getAdapterDirectory() {
		return ADAPTER_KIND;
	}

	@Override
	public void configure(ResourceStatus status, ResourceConfig resourceConfig) {
		String greetingName = getIdentifier(resourceConfig, "greetingName");
		this.config = new HelloWorldConfig(greetingName);
		logInfo("HelloWorldAdapter configured: greetingName=" + config.greetingName);
	}

	@Override
	public Tester getTester(ResourceStatus status, ResourceConfig resourceConfig) {
		return (TestParam param) -> {
			logInfo("HelloWorldAdapter test: always passes (no remote system)");
			// No-op: test always passes for the hello-world adapter
		};
	}

	@Override
	public Discoverer getDiscoverer(ResourceStatus status, ResourceConfig resourceConfig) {
		return (DiscoveryParam param) -> {
			logInfo("HelloWorldAdapter discover: emitting 1 HelloResource");

			ResourceKey key = new ResourceKey("hello-1", "HelloResource", ADAPTER_KIND);
			key.addIdentifier(new ResourceIdentifierConfig("id", "hello-1", true));

			Resource resource = new Resource(key);
			ResourceCollection collection = new ResourceCollection();
			collection.add(resource);
			return collection;
		};
	}

	@Override
	public LiveCollector getLiveDataCollector(ResourceStatus status, ResourceConfig resourceConfig) {
		return new LiveCollector() {
			@Override
			public ResourceCollection getCurrentMetrics(ResourceConfig rc,
					ResourceCollection acc)
					throws CollectionException, InterruptedException {
				long tick = tickCount.incrementAndGet();
				logInfo("HelloWorldAdapter collect: tick=" + tick);

				// Find (or re-create) the resource in the accumulator
				ResourceKey key = new ResourceKey("hello-1", "HelloResource", ADAPTER_KIND);
				key.addIdentifier(new ResourceIdentifierConfig("id", "hello-1", true));
				Resource resource = acc.get(key);
				if (resource == null) {
					resource = new Resource(key);
				}

				// Push metric and property via Resource.addData()
				resource.addData("Metrics|tickCount", (double) tick);
				resource.addData("Properties|greeting", "Hello, " + config.greetingName + "!");

				ResourceCollection result = new ResourceCollection();
				result.add(resource);
				return result;
			}

			@Override
			public ResourceCollection getEvents(ResourceConfig rc,
					ResourceCollection acc)
					throws CollectionException, InterruptedException {
				return new ResourceCollection();
			}

			@Override
			public ResourceCollection getRelationships(ResourceConfig rc,
					ResourceCollection acc)
					throws CollectionException, InterruptedException {
				return new ResourceCollection();
			}

			@Override
			public boolean shouldForceUpdateRelationships() {
				return false;
			}
		};
	}
}
