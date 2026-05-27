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

			logger.info("ComplianceStitcher: processing "
					+ dtos.size() + " ResourceDto objects");

			for (ResourceDto dto : dtos) {
				if (dto == null) continue;

				Resource resource = new Resource(dto);
				ResourceKey key = resource.getResourceKey();
				if (key == null) {
					logger.warn("ComplianceStitcher: dto has null ResourceKey");
					continue;
				}

				String uuid = findUuid(dto);
				String hostName = getIdValue(key, "VMEntityName");
				String moid = getIdValue(key, "VMEntityObjectID");

				logger.info("ComplianceStitcher: found host "
						+ hostName + " moid=" + moid + " uuid=" + uuid);

				HostEntry entry = new HostEntry(
						uuid != null ? uuid : hostName,
						hostName, moid, resource);

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

	public void pushProperties(String resourceId,
			Map<String, String> properties, long timestamp) {
		if (properties.isEmpty()) return;
		try {
			Object client = suiteApiClient.getClass()
					.getMethod("getClient").invoke(suiteApiClient);
			Object resourcesClient = getResourcesClient(client);
			if (resourcesClient == null) {
				logger.warn("ComplianceStitcher: could not get resourcesClient "
						+ "from Client — dumping Client API");
				dumpMethods(client, "Client");
				return;
			}

			Object propContents = buildPropertyContents(properties, timestamp);
			if (propContents == null) {
				logger.warn("ComplianceStitcher: could not build "
						+ "PropertyContents — classes not on classpath");
				return;
			}

			invokeAddProperties(resourcesClient, resourceId, propContents);
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: pushProperties failed for "
					+ resourceId + ": " + e.getClass().getName()
					+ ": " + e.getMessage());
		}
	}

	public void pushStats(String resourceId,
			Map<String, Double> stats, long timestamp) {
		if (stats.isEmpty()) return;
		try {
			Object client = suiteApiClient.getClass()
					.getMethod("getClient").invoke(suiteApiClient);
			Object resourcesClient = getResourcesClient(client);
			if (resourcesClient == null) return;

			Object statContents = buildStatContents(stats, timestamp);
			if (statContents == null) return;

			invokeAddStats(resourcesClient, resourceId, statContents);
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: pushStats failed for "
					+ resourceId + ": " + e.getClass().getName()
					+ ": " + e.getMessage());
		}
	}

	private Object getResourcesClient(Object client) {
		String[] methodNames = {"resourcesClient", "getResourcesClient",
				"resources", "getResources"};
		for (String name : methodNames) {
			try {
				java.lang.reflect.Method m = client.getClass().getMethod(name);
				Object result = m.invoke(client);
				if (result != null) {
					logger.info("ComplianceStitcher: got resourcesClient via "
							+ name + "() → " + result.getClass().getName());
					return result;
				}
			} catch (NoSuchMethodException ignored) {
			} catch (Exception e) {
				logger.warn("ComplianceStitcher: " + name + "() threw: "
						+ e.getMessage());
			}
		}
		return null;
	}

	private Object buildPropertyContents(Map<String, String> properties,
			long timestamp) {
		try {
			Class<?> contentsClass = Class.forName(
					"com.vmware.ops.api.model.property.PropertyContents");
			Class<?> contentClass = Class.forName(
					"com.vmware.ops.api.model.property.PropertyContent");

			Object contents = contentsClass.getDeclaredConstructor().newInstance();

			java.util.List<Object> contentList = new java.util.ArrayList<>();
			for (Map.Entry<String, String> entry : properties.entrySet()) {
				Object content = contentClass.getDeclaredConstructor().newInstance();

				setField(content, "statKey", entry.getKey());
				setField(content, "timestamps", new long[]{timestamp});
				setField(content, "values", new String[]{entry.getValue()});

				contentList.add(content);
			}

			setField(contents, "propertyContents", contentList);
			return contents;
		} catch (ClassNotFoundException e) {
			logger.warn("ComplianceStitcher: PropertyContents class not found "
					+ "— trying direct JSON POST fallback");
			return null;
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: buildPropertyContents failed: "
					+ e.getMessage());
			return null;
		}
	}

	private Object buildStatContents(Map<String, Double> stats, long timestamp) {
		try {
			Class<?> contentsClass = Class.forName(
					"com.vmware.ops.api.model.stat.StatContents");
			Class<?> contentClass = Class.forName(
					"com.vmware.ops.api.model.stat.StatContent");

			Object contents = contentsClass.getDeclaredConstructor().newInstance();

			java.util.List<Object> contentList = new java.util.ArrayList<>();
			for (Map.Entry<String, Double> entry : stats.entrySet()) {
				Object content = contentClass.getDeclaredConstructor().newInstance();

				setField(content, "statKey", entry.getKey());
				setField(content, "timestamps", new long[]{timestamp});
				setField(content, "data", new double[]{entry.getValue()});

				contentList.add(content);
			}

			setField(contents, "statContents", contentList);
			return contents;
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: buildStatContents failed: "
					+ e.getMessage());
			return null;
		}
	}

	private void invokeAddProperties(Object resourcesClient,
			String resourceId, Object propContents) throws Exception {
		for (java.lang.reflect.Method m : resourcesClient.getClass().getMethods()) {
			String name = m.getName().toLowerCase();
			if ((name.contains("addprop") || name.contains("property"))
					&& m.getParameterCount() >= 1) {
				logger.info("ComplianceStitcher: trying " + m.getName()
						+ "(" + java.util.Arrays.toString(m.getParameterTypes())
						+ ")");
			}
		}

		String[] methodNames = {"addProperties", "addPropertiesForResource",
				"addResourceProperties"};
		for (String name : methodNames) {
			try {
				for (java.lang.reflect.Method m :
						resourcesClient.getClass().getMethods()) {
					if (m.getName().equals(name)) {
						Class<?>[] params = m.getParameterTypes();
						if (params.length == 2
								&& params[0] == String.class) {
							m.invoke(resourcesClient, resourceId, propContents);
							logger.info("ComplianceStitcher: "
									+ name + " succeeded for " + resourceId);
							return;
						}
						if (params.length == 2
								&& params[0].getName().contains("UUID")) {
							m.invoke(resourcesClient,
									java.util.UUID.fromString(resourceId),
									propContents);
							logger.info("ComplianceStitcher: "
									+ name + " (UUID) succeeded for "
									+ resourceId);
							return;
						}
					}
				}
			} catch (Exception e) {
				logger.warn("ComplianceStitcher: " + name + " threw: "
						+ e.getMessage());
			}
		}
		logger.warn("ComplianceStitcher: no addProperties method found — "
				+ "dumping resourcesClient API");
		dumpMethods(resourcesClient, "resourcesClient");
	}

	private void invokeAddStats(Object resourcesClient,
			String resourceId, Object statContents) throws Exception {
		String[] methodNames = {"addStats", "addStatsForResource",
				"addResourceStats"};
		for (String name : methodNames) {
			try {
				for (java.lang.reflect.Method m :
						resourcesClient.getClass().getMethods()) {
					if (m.getName().equals(name)) {
						Class<?>[] params = m.getParameterTypes();
						if (params.length == 2 && params[0] == String.class) {
							m.invoke(resourcesClient, resourceId, statContents);
							return;
						}
						if (params.length == 2
								&& params[0].getName().contains("UUID")) {
							m.invoke(resourcesClient,
									java.util.UUID.fromString(resourceId),
									statContents);
							return;
						}
					}
				}
			} catch (Exception ignored) {}
		}
	}

	private void setField(Object obj, String fieldName, Object value) {
		try {
			java.lang.reflect.Field f = obj.getClass().getDeclaredField(fieldName);
			f.setAccessible(true);
			f.set(obj, value);
		} catch (NoSuchFieldException e) {
			for (java.lang.reflect.Method m : obj.getClass().getMethods()) {
				String setter = "set" + fieldName.substring(0, 1).toUpperCase()
						+ fieldName.substring(1);
				if (m.getName().equals(setter) && m.getParameterCount() == 1) {
					try { m.invoke(obj, value); } catch (Exception ignored) {}
					return;
				}
			}
		} catch (Exception ignored) {}
	}

	private void dumpMethods(Object obj, String label) {
		logger.info("ComplianceStitcher: === " + label + " methods ("
				+ obj.getClass().getName() + ") ===");
		for (java.lang.reflect.Method m : obj.getClass().getMethods()) {
			if (m.getDeclaringClass() == Object.class) continue;
			logger.info("  " + m.getName() + "("
					+ java.util.Arrays.toString(m.getParameterTypes()) + ") → "
					+ m.getReturnType().getSimpleName());
		}
	}

	public int size() {
		return hostsByName != null ? hostsByName.size() : 0;
	}

	private String findUuid(ResourceDto dto) {
		String[] methodNames = {"getIdentifier", "getId", "getUuid",
				"getResourceId"};
		for (String methodName : methodNames) {
			try {
				Object result = dto.getClass()
						.getMethod(methodName).invoke(dto);
				if (result != null) {
					String s = result.toString();
					if (!s.isEmpty()) {
						logger.info("ComplianceStitcher: UUID via "
								+ methodName + "() = " + s);
						return s;
					}
				}
			} catch (NoSuchMethodException ignored) {
			} catch (Exception e) {
				logger.warn("ComplianceStitcher: " + methodName
						+ "() threw: " + e.getMessage());
			}
		}
		logger.warn("ComplianceStitcher: no UUID method found on "
				+ dto.getClass().getName());
		return null;
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
