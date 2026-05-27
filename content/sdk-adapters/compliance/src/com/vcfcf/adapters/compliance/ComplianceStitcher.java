package com.vcfcf.adapters.compliance;

import com.integrien.alive.common.adapter3.Logger;
import com.integrien.alive.common.adapter3.ResourceKey;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;
import com.vmware.ops.api.model.resource.ResourceDto;
import com.vmware.tvs.vrealize.adapter.core.data.Resource;
import com.vmware.tvs.vrealize.adapter.core.extensions.suiteapi.SuiteAPIClient;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class ComplianceStitcher {

	private final SuiteAPIClient suiteApiClient;
	private final Logger logger;

	public ComplianceStitcher(SuiteAPIClient suiteApiClient, Logger logger) {
		this.suiteApiClient = suiteApiClient;
		this.logger = logger;
	}

	public Map<String, Resource> loadHostResources() {
		Map<String, Resource> result = new HashMap<>();

		try {
			List<ResourceDto> dtos = suiteApiClient.getResources(
					Arrays.asList("VMWARE"),
					Arrays.asList("HostSystem"),
					null, null, null, null);

			if (dtos == null) return result;

			for (ResourceDto dto : dtos) {
				if (dto == null) continue;
				Resource resource = new Resource(dto);
				ResourceKey key = resource.getResourceKey();
				if (key == null) continue;

				String hostName = getIdentifier(key, "VMEntityName");
				if (hostName != null && !hostName.isEmpty()) {
					result.put(hostName, resource);
				}
			}
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: failed to load VMWARE HostSystem "
					+ "resources: " + e.getMessage(), e);
		}

		logger.info("ComplianceStitcher: loaded " + result.size()
				+ " VMWARE HostSystem resources");
		return result;
	}

	public Resource matchHost(String hostname,
			Map<String, Resource> hostResourceMap) {
		if (hostname == null || hostname.isEmpty()) return null;

		Resource res = hostResourceMap.get(hostname);
		if (res != null) return res;

		for (Map.Entry<String, Resource> entry : hostResourceMap.entrySet()) {
			String registered = entry.getKey();
			if (registered.startsWith(hostname + ".")
					|| hostname.startsWith(registered + ".")) {
				logger.info("ComplianceStitcher: matched " + hostname
						+ " to " + registered + " via prefix");
				return entry.getValue();
			}
		}

		logger.warn("ComplianceStitcher: no VMWARE HostSystem found for "
				+ hostname);
		return null;
	}

	private static String getIdentifier(ResourceKey key, String name) {
		for (ResourceIdentifierConfig id : key.getIdentifiers()) {
			if (name.equals(id.getKey())) {
				return id.getValue();
			}
		}
		return null;
	}
}
