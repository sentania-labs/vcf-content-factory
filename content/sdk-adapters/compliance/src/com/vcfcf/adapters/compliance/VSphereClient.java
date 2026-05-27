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

	private String getProperty(ManagedObjectReference moRef, String propName)
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
				if (propName.equals(dp.getName()) && dp.getVal() != null) {
					return String.valueOf(dp.getVal());
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
		propertySpec.setType("HostSystem");
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
}
