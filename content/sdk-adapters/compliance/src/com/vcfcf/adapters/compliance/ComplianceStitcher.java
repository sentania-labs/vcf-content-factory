package com.vcfcf.adapters.compliance;

import com.integrien.alive.common.adapter3.Logger;
import com.vcfcf.adapter.json.SimpleJson;

import java.util.HashMap;
import java.util.Map;

public final class ComplianceStitcher {

	private final SuiteApiPropertyPusher api;
	private final Logger logger;
	private final String vcenterHost;

	private Map<String, HostEntry> hostEntryMap;
	private String vmwareAdapterInstanceId;

	public ComplianceStitcher(SuiteApiPropertyPusher api, Logger logger,
			String vcenterHost) {
		this.api = api;
		this.logger = logger;
		this.vcenterHost = vcenterHost;
	}

	public void loadHostResources() {
		hostEntryMap = new HashMap<>();

		try {
			api.ensureAuthenticated();

			vmwareAdapterInstanceId = resolveVmwareAdapterInstanceId();
			if (vmwareAdapterInstanceId == null) {
				logger.warn("ComplianceStitcher: no VMWARE adapter instance "
						+ "found for vCenter " + vcenterHost);
				return;
			}

			String resp = api.suiteApiGet(
					"/api/resources?adapterKind=VMWARE"
					+ "&resourceKind=HostSystem"
					+ "&adapterInstanceId=" + vmwareAdapterInstanceId
					+ "&pageSize=1000");

			SimpleJson data = SimpleJson.parse(resp);
			SimpleJson resourceList = data.get("resourceList");
			if (resourceList.isNull() || !resourceList.isList()) {
				logger.warn("ComplianceStitcher: no HostSystem resources "
						+ "in response");
				return;
			}

			for (SimpleJson res : resourceList.asList()) {
				String uuid = res.get("identifier").asString(null);
				if (uuid == null) continue;

				SimpleJson rk = res.get("resourceKey");
				String name = rk.get("name").asString(null);

				String moid = null;
				SimpleJson identifiers = rk.get("resourceIdentifiers");
				if (identifiers.isList()) {
					for (SimpleJson id : identifiers.asList()) {
						String idName = id.get("identifierType")
								.get("name").asString("");
						if ("VMEntityObjectID".equals(idName)) {
							moid = id.get("value").asString(null);
						}
					}
				}

				if (name != null && !name.isEmpty()) {
					HostEntry entry = new HostEntry(uuid, name, moid);
					hostEntryMap.put(name, entry);
					if (moid != null) {
						hostEntryMap.put(moid, entry);
					}
				}
			}
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: failed to load hosts: "
					+ e.getMessage());
		}

		logger.info("ComplianceStitcher: loaded " + hostEntryMap.size()
				+ " entries (adapter instance "
				+ vmwareAdapterInstanceId + ")");
	}

	private String resolveVmwareAdapterInstanceId() {
		try {
			String resp = api.suiteApiGet(
					"/api/adapters?adapterKindKey=VMWARE");
			SimpleJson data = SimpleJson.parse(resp);
			SimpleJson adapters = data.get("adapterInstancesInfoDto");
			if (adapters.isNull() || !adapters.isList()) return null;

			for (SimpleJson adapter : adapters.asList()) {
				SimpleJson rk = adapter.get("resourceKey");
				SimpleJson identifiers = rk.get("resourceIdentifiers");
				if (identifiers.isNull() || !identifiers.isList()) continue;

				for (SimpleJson id : identifiers.asList()) {
					String idName = id.get("identifierType")
							.get("name").asString("");
					String idValue = id.get("value").asString("");
					if ("AUTODISCOVERY".equals(idName)
							&& idValue.contains(vcenterHost)) {
						String aiId = adapter.get("id").asString(null);
						logger.info("ComplianceStitcher: matched VMWARE "
								+ "adapter instance " + aiId
								+ " for vCenter " + vcenterHost);
						return aiId;
					}
				}

				String adapterName = rk.get("name").asString("");
				if (adapterName.contains(vcenterHost)) {
					String aiId = adapter.get("id").asString(null);
					logger.info("ComplianceStitcher: matched VMWARE "
							+ "adapter instance " + aiId
							+ " by name for vCenter " + vcenterHost);
					return aiId;
				}
			}
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: failed to resolve VMWARE "
					+ "adapter instance: " + e.getMessage());
		}
		return null;
	}

	public HostEntry matchHost(String hostname, String moid) {
		if (hostEntryMap == null || hostEntryMap.isEmpty()) return null;

		if (moid != null) {
			HostEntry byMoid = hostEntryMap.get(moid);
			if (byMoid != null) return byMoid;
		}

		if (hostname != null) {
			HostEntry byName = hostEntryMap.get(hostname);
			if (byName != null) return byName;

			for (Map.Entry<String, HostEntry> e : hostEntryMap.entrySet()) {
				String registered = e.getKey();
				if (registered.contains(".") && (
						registered.startsWith(hostname + ".")
						|| hostname.startsWith(registered + "."))) {
					logger.info("ComplianceStitcher: matched " + hostname
							+ " to " + registered + " via prefix");
					return e.getValue();
				}
			}
		}

		logger.warn("ComplianceStitcher: no match for " + hostname
				+ " (moid=" + moid + ")");
		return null;
	}

	public int size() {
		return hostEntryMap != null ? hostEntryMap.size() : 0;
	}

	public static final class HostEntry {
		public final String resourceId;
		public final String hostName;
		public final String moid;

		public HostEntry(String resourceId, String hostName, String moid) {
			this.resourceId = resourceId;
			this.hostName = hostName;
			this.moid = moid;
		}
	}
}
