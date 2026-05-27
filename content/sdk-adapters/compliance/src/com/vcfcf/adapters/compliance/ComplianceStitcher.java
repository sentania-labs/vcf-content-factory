package com.vcfcf.adapters.compliance;

import com.integrien.alive.common.adapter3.Logger;
import com.integrien.alive.common.adapter3.ResourceKey;
import com.vcfcf.adapter.stitch.ForeignResourceResolver;
import com.vmware.tvs.vrealize.adapter.core.data.Resource;
import com.vmware.tvs.vrealize.adapter.core.extensions.suiteapi.SuiteAPIClient;

import java.util.Map;

public final class ComplianceStitcher {

	private final ForeignResourceResolver hostResolver;
	private final Logger logger;

	public ComplianceStitcher(SuiteAPIClient suiteApiClient, Logger logger) {
		this.hostResolver = new ForeignResourceResolver(suiteApiClient, logger);
		this.logger = logger;
	}

	public Map<String, ResourceKey> loadHostMap() {
		return hostResolver.loadAll("VMWARE", "HostSystem", "VMEntityName");
	}

	public ResourceKey matchHost(String hostname, Map<String, ResourceKey> hostMap) {
		if (hostname == null || hostname.isEmpty()) return null;

		ResourceKey key = hostMap.get(hostname);
		if (key != null) return key;

		for (Map.Entry<String, ResourceKey> entry : hostMap.entrySet()) {
			String registered = entry.getKey();
			if (registered.startsWith(hostname + ".") ||
					hostname.startsWith(registered + ".")) {
				logger.info("ComplianceStitcher: matched " + hostname
						+ " to " + registered + " via prefix");
				return entry.getValue();
			}
		}

		logger.warn("ComplianceStitcher: no VMWARE HostSystem found for " + hostname);
		return null;
	}

	public Resource createForeignHostResource(ResourceKey hostKey) {
		return new Resource(hostKey);
	}
}
