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

	private Map<String, HostEntry> hostEntryMap;

	public ComplianceStitcher(SuiteAPIClient suiteApiClient, Logger logger) {
		this.suiteApiClient = suiteApiClient;
		this.logger = logger;
	}

	public void loadHostResources() {
		Map<String, HostEntry> result = new HashMap<>();

		try {
			List<ResourceDto> dtos = suiteApiClient.getResources(
					Arrays.asList("VMWARE"),
					Arrays.asList("HostSystem"),
					null, null, null, null);

			if (dtos == null) {
				this.hostEntryMap = result;
				return;
			}

			for (ResourceDto dto : dtos) {
				if (dto == null) continue;

				Resource resource = new Resource(dto);
				ResourceKey key = resource.getResourceKey();
				if (key == null) continue;

				String uuid = null;
				try {
					uuid = (String) dto.getClass()
							.getMethod("getIdentifier")
							.invoke(dto);
				} catch (Exception ignored) {}
				if (uuid == null || uuid.isEmpty()) continue;

				String hostName = getIdentifier(key, "VMEntityName");
				if (hostName != null && !hostName.isEmpty()) {
					result.put(hostName, new HostEntry(uuid, hostName));
				}
			}
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: failed to load VMWARE HostSystem "
					+ "resources: " + e.getMessage(), e);
		}

		this.hostEntryMap = result;
		logger.info("ComplianceStitcher: loaded " + result.size()
				+ " VMWARE HostSystem resources");
	}

	public HostEntry matchHost(String hostname) {
		if (hostname == null || hostname.isEmpty() || hostEntryMap == null) {
			return null;
		}

		HostEntry entry = hostEntryMap.get(hostname);
		if (entry != null) return entry;

		for (Map.Entry<String, HostEntry> e : hostEntryMap.entrySet()) {
			String registered = e.getKey();
			if (registered.startsWith(hostname + ".")
					|| hostname.startsWith(registered + ".")) {
				logger.info("ComplianceStitcher: matched " + hostname
						+ " to " + registered + " via prefix");
				return e.getValue();
			}
		}

		logger.warn("ComplianceStitcher: no VMWARE HostSystem found for "
				+ hostname);
		return null;
	}

	public int size() {
		return hostEntryMap != null ? hostEntryMap.size() : 0;
	}

	private static String getIdentifier(ResourceKey key, String name) {
		for (ResourceIdentifierConfig id : key.getIdentifiers()) {
			if (name.equals(id.getKey())) {
				return id.getValue();
			}
		}
		return null;
	}

	public static final class HostEntry {
		public final String resourceId;
		public final String hostName;

		public HostEntry(String resourceId, String hostName) {
			this.resourceId = resourceId;
			this.hostName = hostName;
		}
	}
}
