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

	// VMwareAdapter Instance-only indexes — keyed by the platform
	// identifiers that exist for that kind (vCenter FQDN via VCURL and
	// vCenter Instance UUID via VMEntityVCID). The HostSystem / VM /
	// DVS / DVPG kinds use the byName + byMoid tables above; we keep
	// the vCenter indexes separate so the matchResource fallthrough
	// path doesn't need a kind switch.
	private final Map<String, HostEntry> vcByHost = new HashMap<>();
	private final Map<String, HostEntry> vcByVcUuid = new HashMap<>();

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
		// VMwareAdapter Instance is NOT a vim25 entity — it is a VCF
		// Ops construct that identifies a configured vCenter adapter
		// instance. Unlike HostSystem / VirtualMachine / DVS / DVPG,
		// it has no MoRef and so does not carry the
		// VMEntityName + VMEntityObjectID identity tuple. The shared
		// loader would extract null for both and the lookup tables
		// would come back empty (the v27-install symptom on devel).
		//
		// The platform DOES expose two stable identifiers that we can
		// match against the configured vcenter_host / instance UUID:
		//   - VCURL          → vCenter hostname (FQDN)
		//   - VMEntityVCID   → vCenter Instance UUID (matches
		//                      ServiceContent.about.instanceUuid)
		// Plus the resource key's display name (commonly the adapter
		// instance's friendly label, e.g. "vcf-lab-mgmt") which we
		// index for fall-through matching.
		loadVCenterAdapterInstanceByIdentity();
	}

	public void loadDvsResources() {
		loadResourcesForKind("VmwareDistributedVirtualSwitch");
	}

	public void loadDvpgResources() {
		loadResourcesForKind("DistributedVirtualPortgroup");
	}

	public void loadClusterResources() {
		loadResourcesForKind("ClusterComputeResource");
	}

	/**
	 * VMwareAdapter Instance has no MoRef-style identity tuple — the
	 * {@code VMEntityName}/{@code VMEntityObjectID} pair the shared
	 * loader extracts comes back null on these resources, leaving the
	 * lookup tables empty. We extract the two platform-stable identity
	 * fields that DO exist on this kind ({@code VCURL} = vCenter FQDN,
	 * {@code VMEntityVCID} = vCenter Instance UUID), plus the resource
	 * key's display name as a third index, and store entries in a
	 * dedicated pair of maps.
	 *
	 * <p>This is the only VMWARE resource kind whose identifiers
	 * diverge from the {@code VMEntityName}/{@code VMEntityObjectID}
	 * contract — splitting the loader is cheaper than adding an
	 * identifier-pair parameter to {@link #loadResourcesForKind}.
	 */
	private void loadVCenterAdapterInstanceByIdentity() {
		String resourceKind = "VMwareAdapter Instance";
		Map<String, HostEntry> byName = new HashMap<>();
		Map<String, HostEntry> byMoid = new HashMap<>();
		// Keep the per-kind name/moid maps populated even though they
		// will only catch the display-name index — matchResource()
		// reads from these for fall-through behaviour.
		resourcesByName.put(resourceKind, byName);
		resourcesByMoid.put(resourceKind, byMoid);
		vcByHost.clear();
		vcByVcUuid.clear();

		try {
			List<ResourceDto> dtos = suiteApiClient.getResources(
					Arrays.asList("VMWARE"),
					Arrays.asList(resourceKind),
					null, null, null, null);

			if (dtos == null || dtos.isEmpty()) {
				logger.warn("ComplianceStitcher: suiteAPIClient.getResources("
						+ resourceKind + ") returned "
						+ (dtos == null ? "null" : "0 results")
						+ " — adapter has no vCenter adapter instances "
						+ "in inventory");
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
				String displayName = key.getResourceName();
				String vcurl = getIdValue(key, "VCURL");
				String vcUuid = getIdValue(key, "VMEntityVCID");

				HostEntry entry = new HostEntry(
						uuid != null ? uuid
								: (vcurl != null ? vcurl : displayName),
						displayName, vcurl, resource);

				if (displayName != null && !displayName.isEmpty()) {
					byName.put(displayName, entry);
				}
				if (vcurl != null && !vcurl.isEmpty()) {
					vcByHost.put(vcurl, entry);
				}
				if (vcUuid != null && !vcUuid.isEmpty()) {
					vcByVcUuid.put(vcUuid, entry);
				}
				logger.info("ComplianceStitcher: " + resourceKind
						+ " indexed: name=" + displayName
						+ " VCURL=" + vcurl
						+ " VMEntityVCID=" + vcUuid
						+ " → resourceId=" + entry.resourceId);
			}
		} catch (Exception e) {
			logger.warn("ComplianceStitcher: load(" + resourceKind
					+ ") failed: " + e.getClass().getName()
					+ ": " + e.getMessage());
		}

		logger.info("ComplianceStitcher: loaded "
				+ byName.size() + " " + resourceKind + " by displayName, "
				+ vcByHost.size() + " by VCURL, "
				+ vcByVcUuid.size() + " by VMEntityVCID");
	}

	/**
	 * Shared loader for any VMWARE resource kind. Lifted out of the
	 * per-host loader so VirtualMachine, VmwareDistributedVirtualSwitch,
	 * and DistributedVirtualPortgroup can all reuse the same suiteAPI
	 * walk → identifier-extract → name/moid index pattern.
	 *
	 * <p>All vim25-backed VMWARE resource kinds share the same
	 * identity tuple ({@code VMEntityName} + {@code VMEntityObjectID}),
	 * so the lookup key extraction is identical across kinds.
	 * VMwareAdapter Instance is NOT a vim25 entity and uses a
	 * dedicated loader ({@link #loadVCenterAdapterInstanceByIdentity}).
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

	/**
	 * Resolve the {@code VMwareAdapter Instance} resource by either the
	 * configured vCenter hostname (matched against the {@code VCURL}
	 * identifier) or the vCenter Instance UUID (matched against
	 * {@code VMEntityVCID}, read from
	 * {@link VSphereClient#getVCenterInstanceUuid()}). Falls back to
	 * display-name match for environments where Ops registered the
	 * adapter instance under a short name that happens to equal the
	 * configured host. If exactly one VMwareAdapter Instance is
	 * present in inventory, returns it via the singleton fallback.
	 *
	 * @param hostname configured vCenter FQDN (e.g. {@code config.vcenterHost})
	 * @param vcInstanceUuid vCenter Instance UUID, or {@code null} when unknown
	 */
	public HostEntry matchVCenterAdapterInstance(String hostname,
			String vcInstanceUuid) {
		// vCenter Instance UUID is the most authoritative identity —
		// it survives DNS / hostname renames whereas VCURL does not.
		if (vcInstanceUuid != null && !vcInstanceUuid.isEmpty()) {
			HostEntry m = vcByVcUuid.get(vcInstanceUuid);
			if (m != null) return m;
		}

		if (hostname != null && !hostname.isEmpty()) {
			// Exact-FQDN match against VCURL.
			HostEntry m = vcByHost.get(hostname);
			if (m != null) return m;

			// FQDN ↔ shortname fuzzy match against VCURL — same dot-
			// prefix tolerance the HostSystem matcher uses for the
			// FQDN-vs-shortname mismatch that occurs when adapter
			// configuration uses the FQDN but Ops registered the
			// vCenter under a shorter or differently-cased form.
			for (Map.Entry<String, HostEntry> e : vcByHost.entrySet()) {
				String registered = e.getKey();
				if (registered.equalsIgnoreCase(hostname)) return e.getValue();
				if (registered.startsWith(hostname + ".")
						|| hostname.startsWith(registered + ".")) {
					return e.getValue();
				}
			}

			// Fall through to display-name match — when the adapter
			// instance is registered under a friendly label that
			// happens to equal the configured host or a prefix of it.
			HostEntry n = matchResource("VMwareAdapter Instance",
					hostname, null);
			if (n != null) return n;
		}

		// Singleton fallback only when exactly one VMwareAdapter
		// Instance is present in inventory; ambiguous when >1.
		return singletonOfKind("VMwareAdapter Instance");
	}

	public HostEntry matchDvs(String name, String moid) {
		return matchResource("VmwareDistributedVirtualSwitch", name, moid);
	}

	public HostEntry matchDvpg(String name, String moid) {
		return matchResource("DistributedVirtualPortgroup", name, moid);
	}

	public HostEntry matchCluster(String name, String moid) {
		return matchResource("ClusterComputeResource", name, moid);
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
