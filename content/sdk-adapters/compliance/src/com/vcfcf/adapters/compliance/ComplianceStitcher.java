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

	private Map<String, HostEntry> hostsByName;
	private Map<String, HostEntry> hostsByMoid;

	public ComplianceStitcher(SuiteAPIClient suiteApiClient, Logger logger) {
		this.suiteApiClient = suiteApiClient;
		this.logger = logger;
	}

	public void loadHostResources() {
		hostsByName = new HashMap<>();
		hostsByMoid = new HashMap<>();

		try {
			List<ResourceDto> dtos = suiteApiClient.getResources(
					Arrays.asList("VMWARE"),
					Arrays.asList("HostSystem"),
					null, null, null, null);

			if (dtos == null || dtos.isEmpty()) {
				logger.warn("ComplianceStitcher: suiteAPIClient.getResources "
						+ "returned " + (dtos == null ? "null" : "0 results")
						+ " — this may indicate the client is not yet "
						+ "initialized or has restricted scope");
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

				String hostName = getIdValue(key, "VMEntityName");
				String moid = getIdValue(key, "VMEntityObjectID");

				HostEntry entry = new HostEntry(uuid, hostName, moid, resource);

				if (hostName != null && !hostName.isEmpty()) {
					hostsByName.put(hostName, entry);
				}
				if (moid != null && !moid.isEmpty()) {
					hostsByMoid.put(moid, entry);
				}
			}
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: load failed: "
					+ e.getClass().getName() + ": " + e.getMessage());
		}

		logger.info("ComplianceStitcher: loaded "
				+ hostsByName.size() + " hosts by name, "
				+ hostsByMoid.size() + " by MOID");
	}

	public HostEntry matchHost(String hostname, String moid) {
		if (moid != null && hostsByMoid != null) {
			HostEntry byMoid = hostsByMoid.get(moid);
			if (byMoid != null) return byMoid;
		}

		if (hostname != null && hostsByName != null) {
			HostEntry byName = hostsByName.get(hostname);
			if (byName != null) return byName;

			for (Map.Entry<String, HostEntry> e : hostsByName.entrySet()) {
				String registered = e.getKey();
				if (registered.startsWith(hostname + ".")
						|| hostname.startsWith(registered + ".")) {
					return e.getValue();
				}
			}
		}

		logger.warn("ComplianceStitcher: no match for "
				+ hostname + " (moid=" + moid + ")");
		return null;
	}

	public SuiteAPIClient getSuiteApiClient() {
		return suiteApiClient;
	}

	public int size() {
		return hostsByName != null ? hostsByName.size() : 0;
	}

	private static String getIdValue(ResourceKey key, String name) {
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
		public final String moid;
		public final Resource resource;

		public HostEntry(String resourceId, String hostName,
				String moid, Resource resource) {
			this.resourceId = resourceId;
			this.hostName = hostName;
			this.moid = moid;
			this.resource = resource;
		}
	}
}
