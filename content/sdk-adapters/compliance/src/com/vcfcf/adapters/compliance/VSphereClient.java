package com.vcfcf.adapters.compliance;

import com.vmware.vim25.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.xml.ws.BindingProvider;
import javax.xml.ws.handler.MessageContext;

public final class VSphereClient {

	private final String vcenterUrl;
	private final String username;
	private final String password;

	private volatile VimPortType vimPort;
	private volatile ServiceContent serviceContent;
	private volatile ManagedObjectReference rootFolder;

	public VSphereClient(String vcenterHost, String username, String password) {
		this.vcenterUrl = "https://" + vcenterHost + "/sdk";
		this.username = username;
		this.password = password;
	}

	public void connect() throws Exception {
		VimService vimService = new VimService();
		vimPort = vimService.getVimPort();

		Map<String, Object> ctx =
				((BindingProvider) vimPort).getRequestContext();
		ctx.put(BindingProvider.ENDPOINT_ADDRESS_PROPERTY, vcenterUrl);
		ctx.put(BindingProvider.SESSION_MAINTAIN_PROPERTY, true);
		ctx.put("com.sun.xml.internal.ws.transport.https.client.SSLSocketFactory",
				trustAllSslFactory());
		ctx.put("com.sun.xml.ws.transport.https.client.SSLSocketFactory",
				trustAllSslFactory());

		ManagedObjectReference siRef = new ManagedObjectReference();
		siRef.setType("ServiceInstance");
		siRef.setValue("ServiceInstance");

		serviceContent = vimPort.retrieveServiceContent(siRef);
		vimPort.login(serviceContent.getSessionManager(),
				username, password, null);
		rootFolder = serviceContent.getRootFolder();
	}

	public void disconnect() {
		if (vimPort != null && serviceContent != null) {
			try {
				vimPort.logout(serviceContent.getSessionManager());
			} catch (Exception ignored) {}
		}
		vimPort = null;
		serviceContent = null;
	}

	public void ensureConnected() throws Exception {
		if (vimPort == null) {
			connect();
			return;
		}
		try {
			vimPort.currentTime(createSiRef());
		} catch (Exception e) {
			disconnect();
			connect();
		}
	}

	public List<HostInfo> getHosts() throws Exception {
		ensureConnected();
		List<HostInfo> result = new ArrayList<>();

		ManagedObjectReference viewMgr = serviceContent.getViewManager();
		ManagedObjectReference containerView = vimPort.createContainerView(
				viewMgr, rootFolder,
				java.util.Arrays.asList("HostSystem"), true);

		List<ManagedObjectReference> hostRefs = getViewMembers(containerView);

		for (ManagedObjectReference hostRef : hostRefs) {
			String name = getProperty(hostRef, "name");
			if (name != null) {
				result.add(new HostInfo(hostRef, name, hostRef.getValue()));
			}
		}

		vimPort.destroyView(containerView);
		return result;
	}

	public Map<String, String> getAdvancedSettings(ManagedObjectReference hostRef)
			throws Exception {
		ensureConnected();
		Map<String, String> result = new HashMap<>();

		ManagedObjectReference configMgr = getMoRef(hostRef,
				"configManager.advancedOption");
		if (configMgr == null) return result;

		List<OptionValue> options = vimPort.queryOptions(configMgr, null);
		if (options != null) {
			for (OptionValue ov : options) {
				if (ov.getKey() != null && ov.getValue() != null) {
					result.put(ov.getKey(), String.valueOf(ov.getValue()));
				}
			}
		}

		return result;
	}

	/**
	 * Walks every VirtualMachine in the inventory. Mirrors
	 * {@link #getHosts()} structurally but builds a typed
	 * {@link ManagedObjectReference} container view of "VirtualMachine".
	 */
	public List<VmInfo> getVms() throws Exception {
		ensureConnected();
		List<VmInfo> result = new ArrayList<>();

		ManagedObjectReference viewMgr = serviceContent.getViewManager();
		ManagedObjectReference containerView = vimPort.createContainerView(
				viewMgr, rootFolder,
				java.util.Arrays.asList("VirtualMachine"), true);

		List<ManagedObjectReference> refs = getViewMembersTyped(
				containerView, "VirtualMachine");

		for (ManagedObjectReference vmRef : refs) {
			String name = getProperty(vmRef, "name");
			if (name != null) {
				result.add(new VmInfo(vmRef, name, vmRef.getValue()));
			}
		}

		vimPort.destroyView(containerView);
		return result;
	}

	/**
	 * Reads {@code VirtualMachine.config.extraConfig}, a list of
	 * {@code OptionValue} entries that hold the VMX advanced settings
	 * (isolation.tools.*, mks.enable3d, RemoteDisplay.maxConnections,
	 * etc.). Each entry's value is stringified — boolean settings come
	 * back as "TRUE"/"FALSE", integers as their decimal representation.
	 * Returns an empty map if the VM has no extraConfig entries (a
	 * brand-new VM has none until features set them).
	 */
	public Map<String, String> getVmExtraConfig(ManagedObjectReference vmRef)
			throws Exception {
		ensureConnected();
		Map<String, String> result = new HashMap<>();

		Object raw = getRawProperty(vmRef, "config.extraConfig");
		if (raw == null) return result;

		// extraConfig deserializes as ArrayOfOptionValue in vim25; the
		// JAX-WS binding exposes it as a List<OptionValue> via
		// getOptionValue(). Reflect to stay tolerant of slight binding
		// differences between vim25 versions.
		try {
			java.lang.reflect.Method getter = raw.getClass()
					.getMethod("getOptionValue");
			Object list = getter.invoke(raw);
			if (list instanceof List) {
				for (Object item : (List<?>) list) {
					if (item instanceof OptionValue) {
						OptionValue ov = (OptionValue) item;
						if (ov.getKey() != null && ov.getValue() != null) {
							result.put(ov.getKey(),
									String.valueOf(ov.getValue()));
						}
					}
				}
				return result;
			}
		} catch (NoSuchMethodException ignored) {
			// fall through — the property may already be a List
		}
		if (raw instanceof List) {
			for (Object item : (List<?>) raw) {
				if (item instanceof OptionValue) {
					OptionValue ov = (OptionValue) item;
					if (ov.getKey() != null && ov.getValue() != null) {
						result.put(ov.getKey(),
								String.valueOf(ov.getValue()));
					}
				}
			}
		}
		return result;
	}

	/**
	 * Reads vCenter-level advanced settings via the vCenter
	 * OptionManager — same {@code queryOptions} contract as the
	 * per-host AdvancedOption manager, just rooted at
	 * {@code ServiceContent.setting}. The result is the full key/value
	 * map of every {@code vpxd.*}, {@code config.*}, {@code mail.*},
	 * etc. setting exposed to a connected vCenter session.
	 */
	public Map<String, String> getVCenterAdvancedSettings() throws Exception {
		ensureConnected();
		Map<String, String> result = new HashMap<>();

		ManagedObjectReference optionMgr = serviceContent.getSetting();
		if (optionMgr == null) return result;

		List<OptionValue> options = vimPort.queryOptions(optionMgr, null);
		if (options != null) {
			for (OptionValue ov : options) {
				if (ov.getKey() != null && ov.getValue() != null) {
					result.put(ov.getKey(), String.valueOf(ov.getValue()));
				}
			}
		}

		return result;
	}

	/**
	 * Enumerates VmwareDistributedVirtualSwitch inventory entries.
	 * Returns an empty list when the container view yields nothing —
	 * the surrounding adapter loop treats that as "no DVS in this
	 * vCenter" rather than an error. The DVS PowerCLI-only controls
	 * cannot be evaluated against these MoRefs from Java today — see
	 * the TODO in ComplianceAdapter#evaluateDvsCompliance — so this
	 * method exists primarily so the stitcher can find DVS resources
	 * by name/moid for the property push.
	 */
	public List<DvsInfo> getDvSwitches() throws Exception {
		ensureConnected();
		List<DvsInfo> result = new ArrayList<>();

		ManagedObjectReference viewMgr = serviceContent.getViewManager();
		ManagedObjectReference containerView;
		try {
			containerView = vimPort.createContainerView(
					viewMgr, rootFolder,
					java.util.Arrays.asList("VmwareDistributedVirtualSwitch"),
					true);
		} catch (Exception e) {
			// Some environments expose only the base
			// "DistributedVirtualSwitch" type; retry with that.
			containerView = vimPort.createContainerView(
					viewMgr, rootFolder,
					java.util.Arrays.asList("DistributedVirtualSwitch"),
					true);
		}

		List<ManagedObjectReference> refs = getViewMembersTyped(
				containerView, "VmwareDistributedVirtualSwitch");
		if (refs.isEmpty()) {
			refs = getViewMembersTyped(containerView,
					"DistributedVirtualSwitch");
		}

		for (ManagedObjectReference ref : refs) {
			String name = getProperty(ref, "name");
			if (name != null) {
				result.add(new DvsInfo(ref, name, ref.getValue()));
			}
		}

		vimPort.destroyView(containerView);
		return result;
	}

	/**
	 * Enumerates ClusterComputeResource inventory entries. Phase 3 (vSAN)
	 * stitches a small subset of vSAN-related controls onto the matched
	 * cluster, so the adapter must first walk cluster inventory the same
	 * way it walks Host / VM / DVS / DVPG. Identical container-view
	 * pattern; the {@code ClusterComputeResource} type filter is the
	 * vim25 supertype that covers both regular clusters and the
	 * {@code VsanClusterComputeResource} subtype (older bindings, rare).
	 */
	public List<ClusterInfo> getClusters() throws Exception {
		ensureConnected();
		List<ClusterInfo> result = new ArrayList<>();

		ManagedObjectReference viewMgr = serviceContent.getViewManager();
		ManagedObjectReference containerView = vimPort.createContainerView(
				viewMgr, rootFolder,
				java.util.Arrays.asList("ClusterComputeResource"), true);

		List<ManagedObjectReference> refs = getViewMembersTyped(
				containerView, "ClusterComputeResource");

		for (ManagedObjectReference ref : refs) {
			String name = getProperty(ref, "name");
			if (name != null) {
				result.add(new ClusterInfo(ref, name, ref.getValue()));
			}
		}

		vimPort.destroyView(containerView);
		return result;
	}

	/**
	 * Reads a tiny slice of the cluster-level vSAN configuration that
	 * vim25 8.0.2 exposes natively (no vSAN Management SDK on classpath).
	 *
	 * <p>The vim25 surface is
	 * {@code ClusterComputeResource.configurationEx} ->
	 * {@code ClusterConfigInfoEx.vsanConfigInfo} ->
	 * {@code VsanClusterConfigInfo}. The plain {@code vim25.jar} on this
	 * adapter's classpath exposes only three fields on that object:
	 * <ul>
	 *   <li>{@code enabled}            — is vSAN turned on for this cluster</li>
	 *   <li>{@code defaultConfig.autoClaimStorage} — whether vSAN claims
	 *       compatible disks automatically (the
	 *       {@code cluster.managed-disk-claim} control reads this)</li>
	 *   <li>{@code defaultConfig.checksumEnabled} — cluster-wide object
	 *       checksum default (the {@code cluster.object-checksum}
	 *       control reads this)</li>
	 * </ul>
	 *
	 * <p>The other 12 ClusterComputeResource controls SCG defines for
	 * vSAN (data-at-rest encryption, data-in-transit encryption, iSCSI
	 * mutual CHAP, File Services NFS/SMB, network isolation, operations
	 * reserve, automatic rebalance, auto-policy-management,
	 * vSAN Max isolation) live on richer vSAN management interfaces
	 * (VsanConfigSystem, VsanFileServiceConfig, etc.) that the
	 * vSAN Management SDK jar ships but plain vim25 does not. Without
	 * that jar on the classpath, those reads are a TOOLSET GAP and the
	 * canonical CSV keeps them as {@code manual_audit} rows that emit
	 * profile_name only.
	 *
	 * <p>Returns an empty map when {@code vsanConfigInfo} is absent
	 * (cluster does not have vSAN turned on, or
	 * {@code configurationEx.vsanConfigInfo} returns null). The
	 * surrounding collector treats the empty map as a no-signal cluster
	 * and falls back to the profile-name-only push — same contract as
	 * DVS / DVPG when the security-policy read finds nothing.
	 *
	 * <p>The returned keys are already prefixed with {@code vsanConfig.}
	 * so the canonical {@code parameter} column in the CSV can use the
	 * same {@code <kind>.<field>} dot-path convention the
	 * security-policy controls use ({@code securityPolicy.<field>}).
	 * The Java evaluator's vim_property dispatcher looks the key up
	 * directly; no rewriting in the caller.
	 *
	 * <p>Reflection-tolerant unwrap mirrors the DVS / DVPG security-
	 * policy reader so minor binding differences across vim25 8.x
	 * point releases don't break the read.
	 */
	public Map<String, Object> getClusterVsanConfig(
			ManagedObjectReference clusterRef) throws Exception {
		ensureConnected();
		Map<String, Object> result = new HashMap<>();
		if (clusterRef == null) return result;

		// configurationEx is the rich ClusterConfigInfoEx; the older
		// 'configuration' property is the legacy ClusterConfigInfo
		// that does NOT carry vsanConfigInfo. Use configurationEx.
		Object configEx = getRawProperty(clusterRef, "configurationEx");
		if (configEx == null) return result;

		Object vsanCfg = invokeGetter(configEx, "getVsanConfigInfo");
		if (vsanCfg == null) {
			// Cluster has no vSAN configuration object at all — typical
			// for non-vSAN clusters in mixed environments. Leave the
			// map empty; the collector treats this as no-signal.
			return result;
		}

		Boolean enabled = readBoolean(vsanCfg, "isEnabled", "getEnabled");
		if (enabled != null) {
			result.put("vsanConfig.enabled", enabled);
		}

		Object defaultCfg = invokeGetter(vsanCfg, "getDefaultConfig");
		if (defaultCfg != null) {
			Boolean autoClaim = readBoolean(defaultCfg,
					"isAutoClaimStorage", "getAutoClaimStorage");
			if (autoClaim != null) {
				result.put("vsanConfig.autoClaimStorage", autoClaim);
			}
			Boolean checksum = readBoolean(defaultCfg,
					"isChecksumEnabled", "getChecksumEnabled");
			if (checksum != null) {
				result.put("vsanConfig.objectChecksumEnabled", checksum);
			}
		}

		return result;
	}

	/**
	 * Read a Boolean field from a JAX-WS binding object that may expose
	 * either an {@code isX()} or {@code getX()} accessor depending on
	 * the binding generator's treatment of {@code Boolean} vs
	 * {@code boolean}. Returns null when neither accessor exists or
	 * both return null.
	 */
	private Boolean readBoolean(Object target, String isGetter,
			String getGetter) throws Exception {
		Object v;
		try {
			v = invokeGetter(target, isGetter);
		} catch (Exception e) {
			v = null;
		}
		if (v == null) {
			try {
				v = invokeGetter(target, getGetter);
			} catch (Exception e) {
				return null;
			}
		}
		if (v instanceof Boolean) return (Boolean) v;
		return null;
	}

	/**
	 * Enumerates DistributedVirtualPortgroup inventory entries.
	 * Same shape and rationale as {@link #getDvSwitches()}.
	 */
	public List<DvpgInfo> getDvPortgroups() throws Exception {
		ensureConnected();
		List<DvpgInfo> result = new ArrayList<>();

		ManagedObjectReference viewMgr = serviceContent.getViewManager();
		ManagedObjectReference containerView = vimPort.createContainerView(
				viewMgr, rootFolder,
				java.util.Arrays.asList("DistributedVirtualPortgroup"),
				true);

		List<ManagedObjectReference> refs = getViewMembersTyped(
				containerView, "DistributedVirtualPortgroup");

		for (ManagedObjectReference ref : refs) {
			String name = getProperty(ref, "name");
			if (name != null) {
				result.add(new DvpgInfo(ref, name, ref.getValue()));
			}
		}

		vimPort.destroyView(containerView);
		return result;
	}

	/**
	 * Reads {@code DistributedVirtualSwitch.config.defaultPortConfig
	 * .securityPolicy} and returns the three boolean security-policy
	 * values keyed by canonical field name:
	 * {@code allowPromiscuous}, {@code macChanges},
	 * {@code forgedTransmits}.
	 *
	 * <p>The vim25 path is
	 * {@code DistributedVirtualSwitch.config.defaultPortConfig} which
	 * returns a {@code DVPortSetting} (typically the
	 * {@code VMwareDVSPortSetting} subclass on vCenter-managed
	 * switches). Its {@code securityPolicy} child is a
	 * {@code DVSSecurityPolicy} whose three fields are
	 * {@code BoolPolicy} wrappers (each carrying both
	 * {@code inherited} and {@code value} children). We surface only
	 * {@code value} here — the canonical compliance check is "is the
	 * effective value Reject?" not "is it inherited from the parent
	 * switch?" An inherited TRUE is still a non-compliant value when
	 * the expected_value is Reject.
	 *
	 * <p>Returns an empty map if {@code config.defaultPortConfig} is
	 * null on the DVS (rare — every operational DVS has one) or if
	 * the {@code securityPolicy} substructure is absent. Reflection-
	 * tolerant unwrap mirrors the
	 * {@link #getVmExtraConfig(ManagedObjectReference)} pattern so
	 * minor vim25 binding differences (DVSSecurityPolicy fields are
	 * sometimes inherited from a non-public superclass) don't break
	 * the read.
	 */
	public Map<String, Boolean> getDvsSecurityPolicy(
			ManagedObjectReference dvsRef) throws Exception {
		return readSecurityPolicy(dvsRef);
	}

	/**
	 * Reads {@code DistributedVirtualPortgroup.config.defaultPortConfig
	 * .securityPolicy} and returns the same {@code allowPromiscuous /
	 * macChanges / forgedTransmits} boolean keys as
	 * {@link #getDvsSecurityPolicy(ManagedObjectReference)}.
	 *
	 * <p>The DVPG-level security policy overrides the DVS-level
	 * default when set explicitly; the public Suite API maps the
	 * effective value to {@code config.defaultPortConfig
	 * .securityPolicy.<field>.value}. A port group whose policy
	 * inherits from the parent switch still exposes its effective
	 * value here through the same path — vim25 resolves inheritance
	 * server-side before serialization.
	 */
	public Map<String, Boolean> getDvpgSecurityPolicy(
			ManagedObjectReference dvpgRef) throws Exception {
		return readSecurityPolicy(dvpgRef);
	}

	/**
	 * Shared reader for the DVS / DVPG security-policy path. Both
	 * MoRef types expose
	 * {@code config.defaultPortConfig.securityPolicy} with the same
	 * {@code DVSSecurityPolicy} substructure (the DVPG inherits the
	 * shape from its parent DVS in the vim25 type hierarchy), so a
	 * single helper handles both.
	 *
	 * <p>Reflection-tolerant — we walk the property tree via
	 * {@code getProperty()/get<Field>()} accessors rather than casting
	 * to concrete classes, so the read survives the vim25 binding
	 * variants we have seen across vCenter 7.x / 8.x / 9.x. When any
	 * intermediate node is absent we return whatever keys we did
	 * manage to read — partial results are useful for diagnostics
	 * even when one field's wrapper is missing.
	 */
	private Map<String, Boolean> readSecurityPolicy(
			ManagedObjectReference ref) throws Exception {
		ensureConnected();
		Map<String, Boolean> result = new HashMap<>();
		if (ref == null) return result;

		Object portCfg = getRawProperty(ref,
				"config.defaultPortConfig");
		if (portCfg == null) return result;

		Object secPol = invokeGetter(portCfg, "getSecurityPolicy");
		if (secPol == null) return result;

		Boolean allowPromisc = readBoolPolicy(secPol,
				"getAllowPromiscuous");
		Boolean macChanges = readBoolPolicy(secPol, "getMacChanges");
		Boolean forged = readBoolPolicy(secPol, "getForgedTransmits");
		if (allowPromisc != null) {
			result.put("allowPromiscuous", allowPromisc);
		}
		if (macChanges != null) {
			result.put("macChanges", macChanges);
		}
		if (forged != null) {
			result.put("forgedTransmits", forged);
		}
		return result;
	}

	/**
	 * Read the {@code .value} child of a {@code BoolPolicy} field on
	 * a {@code DVSSecurityPolicy}. The vim25 binding exposes each as
	 * a {@code BoolPolicy} wrapper with {@code isInherited()} /
	 * {@code isValue()} accessors (or {@code getInherited()} /
	 * {@code getValue()} in older bindings). We try both shapes; null
	 * means "not present" rather than "false".
	 */
	private Boolean readBoolPolicy(Object secPol, String getter) {
		Object wrapper;
		try {
			wrapper = invokeGetter(secPol, getter);
		} catch (Exception e) {
			return null;
		}
		if (wrapper == null) return null;
		// BoolPolicy.value is a Boolean. JAX-WS generates isValue() for
		// boolean primitives and getValue() for Boolean wrappers
		// depending on schema treatment; try both.
		Object v;
		try {
			v = invokeGetter(wrapper, "isValue");
		} catch (Exception e) {
			v = null;
		}
		if (v == null) {
			try {
				v = invokeGetter(wrapper, "getValue");
			} catch (Exception e) {
				return null;
			}
		}
		if (v instanceof Boolean) return (Boolean) v;
		return null;
	}

	/**
	 * Reflection helper — invoke a zero-arg getter by name on
	 * {@code target}. Returns null when the getter doesn't exist
	 * (NoSuchMethodException) so the security-policy walker can
	 * skip absent fields rather than crashing.
	 */
	private Object invokeGetter(Object target, String name)
			throws Exception {
		if (target == null) return null;
		try {
			java.lang.reflect.Method m = target.getClass()
					.getMethod(name);
			return m.invoke(target);
		} catch (NoSuchMethodException ignored) {
			return null;
		}
	}

	/**
	 * Returns the vCenter instance UUID
	 * ({@code ServiceContent.about.instanceUuid}) — a stable
	 * identifier for the vCenter we are connected to, useful for
	 * naming the synthetic "VCenterAdapterInstance" the canonical
	 * profile targets.
	 */
	public String getVCenterInstanceUuid() throws Exception {
		ensureConnected();
		if (serviceContent == null) return null;
		if (serviceContent.getAbout() == null) return null;
		return serviceContent.getAbout().getInstanceUuid();
	}

	/**
	 * Returns the vCenter API name (commonly "VMware vCenter Server")
	 * for diagnostic logging.
	 */
	public String getVCenterDisplayName() throws Exception {
		ensureConnected();
		if (serviceContent == null) return null;
		if (serviceContent.getAbout() == null) return null;
		return serviceContent.getAbout().getFullName();
	}

	private String getProperty(ManagedObjectReference moRef, String propName)
			throws Exception {
		Object raw = getRawProperty(moRef, propName);
		return raw == null ? null : String.valueOf(raw);
	}

	/**
	 * Like {@link #getProperty(ManagedObjectReference, String)} but
	 * returns the unwrapped JAX-WS value object so callers can read
	 * complex types (e.g. {@code config.extraConfig} which deserializes
	 * to an {@code ArrayOfOptionValue} wrapper around a
	 * {@code List<OptionValue>}).
	 */
	private Object getRawProperty(ManagedObjectReference moRef, String propName)
			throws Exception {
		PropertyFilterSpec filterSpec = new PropertyFilterSpec();

		ObjectSpec objectSpec = new ObjectSpec();
		objectSpec.setObj(moRef);
		objectSpec.setSkip(false);
		filterSpec.getObjectSet().add(objectSpec);

		PropertySpec propertySpec = new PropertySpec();
		propertySpec.setType(moRef.getType());
		propertySpec.getPathSet().add(propName);
		filterSpec.getPropSet().add(propertySpec);

		List<ObjectContent> results = vimPort.retrieveProperties(
				serviceContent.getPropertyCollector(),
				java.util.Arrays.asList(filterSpec));

		if (results != null && !results.isEmpty()) {
			for (DynamicProperty dp : results.get(0).getPropSet()) {
				if (propName.equals(dp.getName())) {
					return dp.getVal();
				}
			}
		}
		return null;
	}

	private ManagedObjectReference getMoRef(ManagedObjectReference moRef,
			String propPath) throws Exception {
		PropertyFilterSpec filterSpec = new PropertyFilterSpec();

		ObjectSpec objectSpec = new ObjectSpec();
		objectSpec.setObj(moRef);
		objectSpec.setSkip(false);
		filterSpec.getObjectSet().add(objectSpec);

		PropertySpec propertySpec = new PropertySpec();
		propertySpec.setType(moRef.getType());
		propertySpec.getPathSet().add(propPath);
		filterSpec.getPropSet().add(propertySpec);

		List<ObjectContent> results = vimPort.retrieveProperties(
				serviceContent.getPropertyCollector(),
				java.util.Arrays.asList(filterSpec));

		if (results != null && !results.isEmpty()) {
			for (DynamicProperty dp : results.get(0).getPropSet()) {
				if (dp.getVal() instanceof ManagedObjectReference) {
					return (ManagedObjectReference) dp.getVal();
				}
			}
		}
		return null;
	}

	private List<ManagedObjectReference> getViewMembers(
			ManagedObjectReference containerView) throws Exception {
		return getViewMembersTyped(containerView, "HostSystem");
	}

	/**
	 * Generic ContainerView walker. The original {@link #getViewMembers}
	 * hardcoded {@code HostSystem} — Phase 2 needs the same traversal
	 * against VirtualMachine, DistributedVirtualSwitch, and
	 * DistributedVirtualPortgroup, so the type filter became a parameter.
	 */
	private List<ManagedObjectReference> getViewMembersTyped(
			ManagedObjectReference containerView, String type)
			throws Exception {
		PropertyFilterSpec filterSpec = new PropertyFilterSpec();

		ObjectSpec objectSpec = new ObjectSpec();
		objectSpec.setObj(containerView);
		objectSpec.setSkip(true);

		TraversalSpec traversal = new TraversalSpec();
		traversal.setName("view");
		traversal.setPath("view");
		traversal.setType("ContainerView");
		traversal.setSkip(false);
		objectSpec.getSelectSet().add(traversal);
		filterSpec.getObjectSet().add(objectSpec);

		PropertySpec propertySpec = new PropertySpec();
		propertySpec.setType(type);
		propertySpec.getPathSet().add("name");
		filterSpec.getPropSet().add(propertySpec);

		List<ObjectContent> results = vimPort.retrieveProperties(
				serviceContent.getPropertyCollector(),
				java.util.Arrays.asList(filterSpec));

		List<ManagedObjectReference> refs = new ArrayList<>();
		if (results != null) {
			for (ObjectContent oc : results) {
				refs.add(oc.getObj());
			}
		}
		return refs;
	}

	private ManagedObjectReference createSiRef() {
		ManagedObjectReference ref = new ManagedObjectReference();
		ref.setType("ServiceInstance");
		ref.setValue("ServiceInstance");
		return ref;
	}

	private static javax.net.ssl.SSLSocketFactory trustAllSslFactory() {
		try {
			javax.net.ssl.SSLContext ctx =
					javax.net.ssl.SSLContext.getInstance("TLS");
			ctx.init(null, new javax.net.ssl.TrustManager[]{
					new javax.net.ssl.X509TrustManager() {
						public void checkClientTrusted(
								java.security.cert.X509Certificate[] c,
								String a) {}
						public void checkServerTrusted(
								java.security.cert.X509Certificate[] c,
								String a) {}
						public java.security.cert.X509Certificate[]
								getAcceptedIssuers() {
							return new java.security.cert.X509Certificate[0];
						}
					}
			}, null);
			return ctx.getSocketFactory();
		} catch (Exception e) {
			throw new RuntimeException("SSL setup failed", e);
		}
	}

	public static final class HostInfo {
		public final ManagedObjectReference moRef;
		public final String name;
		public final String moid;

		public HostInfo(ManagedObjectReference moRef, String name,
				String moid) {
			this.moRef = moRef;
			this.name = name;
			this.moid = moid;
		}
	}

	public static final class VmInfo {
		public final ManagedObjectReference moRef;
		public final String name;
		public final String moid;

		public VmInfo(ManagedObjectReference moRef, String name, String moid) {
			this.moRef = moRef;
			this.name = name;
			this.moid = moid;
		}
	}

	public static final class DvsInfo {
		public final ManagedObjectReference moRef;
		public final String name;
		public final String moid;

		public DvsInfo(ManagedObjectReference moRef, String name, String moid) {
			this.moRef = moRef;
			this.name = name;
			this.moid = moid;
		}
	}

	public static final class DvpgInfo {
		public final ManagedObjectReference moRef;
		public final String name;
		public final String moid;

		public DvpgInfo(ManagedObjectReference moRef, String name,
				String moid) {
			this.moRef = moRef;
			this.name = name;
			this.moid = moid;
		}
	}

	public static final class ClusterInfo {
		public final ManagedObjectReference moRef;
		public final String name;
		public final String moid;

		public ClusterInfo(ManagedObjectReference moRef, String name,
				String moid) {
			this.moRef = moRef;
			this.name = name;
			this.moid = moid;
		}
	}
}
