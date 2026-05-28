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

	// Per-VMWARE-resource-kind name/moid lookup tables. Phase 1 only
	// populated the HostSystem tables; Phase 2 adds VirtualMachine,
	// VMwareAdapter Instance, VmwareDistributedVirtualSwitch, and
	// DistributedVirtualPortgroup so the same stitching path handles
	// every resource kind the compliance profile targets.
	private final Map<String, Map<String, HostEntry>> resourcesByName =
			new HashMap<>();
	private final Map<String, Map<String, HostEntry>> resourcesByMoid =
			new HashMap<>();

	public ComplianceStitcher(SuiteAPIClient suiteApiClient, Logger logger) {
		this.suiteApiClient = suiteApiClient;
		this.logger = logger;
	}

	public void loadHostResources() {
		loadResourcesForKind("HostSystem");
	}

	public void loadVmResources() {
		loadResourcesForKind("VirtualMachine");
	}

	public void loadVCenterAdapterInstance() {
		loadResourcesForKind("VMwareAdapter Instance");
	}

	public void loadDvsResources() {
		loadResourcesForKind("VmwareDistributedVirtualSwitch");
	}

	public void loadDvpgResources() {
		loadResourcesForKind("DistributedVirtualPortgroup");
	}

	/**
	 * Shared loader for any VMWARE resource kind. Lifted out of the
	 * per-host loader so VirtualMachine, VMwareAdapter Instance,
	 * VmwareDistributedVirtualSwitch, and DistributedVirtualPortgroup
	 * can all reuse the same suiteAPI walk → identifier-extract →
	 * name/moid index pattern.
	 *
	 * <p>All VMWARE resource kinds share the same identity tuple
	 * ({@code VMEntityName} + {@code VMEntityObjectID}), so the lookup
	 * key extraction is identical across kinds.
	 */
	private void loadResourcesForKind(String resourceKind) {
		Map<String, HostEntry> byName = new HashMap<>();
		Map<String, HostEntry> byMoid = new HashMap<>();
		resourcesByName.put(resourceKind, byName);
		resourcesByMoid.put(resourceKind, byMoid);

		try {
			List<ResourceDto> dtos = suiteApiClient.getResources(
					Arrays.asList("VMWARE"),
					Arrays.asList(resourceKind),
					null, null, null, null);

			if (dtos == null || dtos.isEmpty()) {
				logger.warn("ComplianceStitcher: suiteAPIClient.getResources("
						+ resourceKind + ") returned "
						+ (dtos == null ? "null" : "0 results")
						+ " — this may indicate the client is not yet "
						+ "initialized, has restricted scope, or this "
						+ "resource kind is not present in inventory");
				return;
			}

			logger.info("ComplianceStitcher: " + resourceKind
					+ " — processing " + dtos.size() + " ResourceDto objects");

			for (ResourceDto dto : dtos) {
				if (dto == null) continue;

				Resource resource = new Resource(dto);
				ResourceKey key = resource.getResourceKey();
				if (key == null) {
					logger.warn("ComplianceStitcher: " + resourceKind
							+ " dto has null ResourceKey");
					continue;
				}

				String uuid = findUuid(dto);
				String name = getIdValue(key, "VMEntityName");
				String moid = getIdValue(key, "VMEntityObjectID");

				HostEntry entry = new HostEntry(
						uuid != null ? uuid : name,
						name, moid, resource);

				if (name != null && !name.isEmpty()) {
					byName.put(name, entry);
				}
				if (moid != null && !moid.isEmpty()) {
					byMoid.put(moid, entry);
				}
			}
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: load(" + resourceKind
					+ ") failed: " + e.getClass().getName()
					+ ": " + e.getMessage());
		}

		logger.info("ComplianceStitcher: loaded "
				+ byName.size() + " " + resourceKind + " by name, "
				+ byMoid.size() + " by MOID");
	}

	public HostEntry matchHost(String hostname, String moid) {
		return matchResource("HostSystem", hostname, moid);
	}

	public HostEntry matchVm(String name, String moid) {
		return matchResource("VirtualMachine", name, moid);
	}

	public HostEntry matchVCenterAdapterInstance(String name, String moid) {
		return matchResource("VMwareAdapter Instance", name, moid);
	}

	public HostEntry matchDvs(String name, String moid) {
		return matchResource("VmwareDistributedVirtualSwitch", name, moid);
	}

	public HostEntry matchDvpg(String name, String moid) {
		return matchResource("DistributedVirtualPortgroup", name, moid);
	}

	/**
	 * Returns the single resource of a given kind when there is
	 * exactly one in inventory — used for VMwareAdapter Instance
	 * where the compliance profile targets "the vCenter we monitor"
	 * and there is exactly one such instance per ComplianceAdapter
	 * configuration. Returns null when ambiguous (>1 candidate) or
	 * missing (0 candidates).
	 */
	public HostEntry singletonOfKind(String resourceKind) {
		Map<String, HostEntry> byName = resourcesByName.get(resourceKind);
		if (byName == null || byName.size() != 1) {
			return null;
		}
		return byName.values().iterator().next();
	}

	/**
	 * Generic resource matcher: try moid first (most authoritative),
	 * then exact name, then dot-prefix fuzzy match (handles FQDN vs
	 * shortname mismatches between vCenter inventory and Ops resource
	 * registration).
	 */
	private HostEntry matchResource(String resourceKind, String name,
			String moid) {
		Map<String, HostEntry> byMoid = resourcesByMoid.get(resourceKind);
		Map<String, HostEntry> byName = resourcesByName.get(resourceKind);

		if (moid != null && byMoid != null) {
			HostEntry m = byMoid.get(moid);
			if (m != null) return m;
		}

		if (name != null && byName != null) {
			HostEntry n = byName.get(name);
			if (n != null) return n;

			for (Map.Entry<String, HostEntry> e : byName.entrySet()) {
				String registered = e.getKey();
				if (registered.startsWith(name + ".")
						|| name.startsWith(registered + ".")) {
					return e.getValue();
				}
			}
		}

		logger.warn("ComplianceStitcher: no " + resourceKind
				+ " match for " + name + " (moid=" + moid + ")");
		return null;
	}

	public int countOfKind(String resourceKind) {
		Map<String, HostEntry> byName = resourcesByName.get(resourceKind);
		return byName == null ? 0 : byName.size();
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
		// ResourcesClient (com.vmware.ops.api.client.controllers) exposes
		// FOUR addStats overloads — none of them are 2-arg:
		//   addStats(UUID, StatContents, boolean)              ← 3-arg, what we want
		//   addStats(String, UUID, StatContents, boolean)      ← 4-arg, adapterKind variant
		//   addStatsForResources(ResourceStatContent$ResourcesStatContents, boolean)
		//   addStatsForResources(String, ...)
		// The previous implementation only looked for 2-arg variants, so
		// every stat push silently no-op'd — which is why per-host rollups
		// (VCF-CF Compliance|score etc.) never appeared on HostSystem
		// while per-control properties did (addProperties IS 2-arg:
		// addProperties(UUID, PropertyContents)).
		String[] methodNames = {"addStats", "addStatsForResource",
				"addResourceStats"};
		Exception lastError = null;
		for (String name : methodNames) {
			for (java.lang.reflect.Method m :
					resourcesClient.getClass().getMethods()) {
				if (!m.getName().equals(name)) continue;
				Class<?>[] params = m.getParameterTypes();
				try {
					// 3-arg: (UUID, StatContents, boolean) — real signature
					if (params.length == 3
							&& params[0].getName().contains("UUID")
							&& params[2] == boolean.class) {
						m.invoke(resourcesClient,
								java.util.UUID.fromString(resourceId),
								statContents, Boolean.FALSE);
						logger.info("ComplianceStitcher: addStats(UUID,"
								+ "StatContents,bool) succeeded for "
								+ resourceId);
						return;
					}
					// 3-arg: (String, ..., StatContents) variant safeguard
					if (params.length == 3 && params[0] == String.class
							&& params[2] == boolean.class) {
						m.invoke(resourcesClient, resourceId, statContents,
								Boolean.FALSE);
						logger.info("ComplianceStitcher: addStats(String,"
								+ "StatContents,bool) succeeded for "
								+ resourceId);
						return;
					}
					// 2-arg fallback (in case some SDK build offers it)
					if (params.length == 2 && params[0] == String.class) {
						m.invoke(resourcesClient, resourceId, statContents);
						logger.info("ComplianceStitcher: addStats(String,"
								+ "StatContents) succeeded for "
								+ resourceId);
						return;
					}
					if (params.length == 2
							&& params[0].getName().contains("UUID")) {
						m.invoke(resourcesClient,
								java.util.UUID.fromString(resourceId),
								statContents);
						logger.info("ComplianceStitcher: addStats(UUID,"
								+ "StatContents) succeeded for "
								+ resourceId);
						return;
					}
				} catch (Exception e) {
					lastError = e;
					logger.warn("ComplianceStitcher: " + name + "("
							+ java.util.Arrays.toString(params)
							+ ") threw: " + e.getClass().getName()
							+ ": " + e.getMessage());
				}
			}
		}
		// Never silently swallow — if no overload matched OR every attempt
		// threw, surface the gap so we don't repeat the v23 mistake of
		// thinking stats were being pushed when they weren't.
		logger.warn("ComplianceStitcher: NO addStats overload accepted "
				+ "the call for " + resourceId
				+ " — per-host rollups will NOT appear on HostSystem. "
				+ "Dumping resourcesClient API:");
		dumpMethods(resourcesClient, "resourcesClient");
		if (lastError != null) throw lastError;
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
		return countOfKind("HostSystem");
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
