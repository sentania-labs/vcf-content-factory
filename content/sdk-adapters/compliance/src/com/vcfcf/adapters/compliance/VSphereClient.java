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
}
