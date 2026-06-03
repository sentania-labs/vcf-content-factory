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

	// esxcli reader (build 36) — rides THIS vCenter session (no host
	// credentials). Rebuilt on every (re)connect so it carries the live
	// session cookie and so its per-cycle command cache is fresh each
	// collection cycle. Lazily constructed on first esxcli recipe read.
	private volatile EsxcliSoapClient esxcli;
	private volatile String sessionCookie;

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

		// Capture the live vCenter session cookie so the raw-SOAP esxcli
		// reader (which bypasses JAX-WS for the reflect/dynamic types not
		// in the bindings) rides the SAME authenticated session. Rebuild
		// the esxcli client on every (re)connect: it gets the fresh
		// cookie AND a fresh per-cycle command cache.
		this.sessionCookie = captureSessionCookie();
		this.esxcli = new EsxcliSoapClient(vcenterUrl, sessionCookie,
				trustAllSslFactory());
	}

	/**
	 * Extract the {@code vmware_soap_session} cookie the JAX-WS runtime
	 * just established (via {@code SESSION_MAINTAIN_PROPERTY}) from the
	 * login response headers, so the raw-SOAP esxcli reader can present
	 * the same session. Returns the {@code Set-Cookie} value verbatim
	 * (suitable as a {@code Cookie:} request header) or null if the
	 * runtime did not surface it — in which case the esxcli reader still
	 * works only if the cookie reaches it another way (it does not today,
	 * so a null cookie -> esxcli reads return command-failed/UNREADABLE,
	 * never a false pass).
	 */
	private String captureSessionCookie() {
		try {
			Map<String, Object> respCtx =
					((BindingProvider) vimPort).getResponseContext();
			Object headersObj =
					respCtx.get(MessageContext.HTTP_RESPONSE_HEADERS);
			if (!(headersObj instanceof Map)) return null;
			@SuppressWarnings("unchecked")
			Map<String, List<String>> headers =
					(Map<String, List<String>>) headersObj;
			for (Map.Entry<String, List<String>> e : headers.entrySet()) {
				if (e.getKey() == null) continue;
				if (!"Set-Cookie".equalsIgnoreCase(e.getKey())) continue;
				List<String> vals = e.getValue();
				if (vals == null) continue;
				for (String v : vals) {
					if (v == null) continue;
					// Take the cookie name=value pair (up to the first ';',
					// dropping Path/Secure/HttpOnly attributes) for the
					// vmware_soap_session cookie.
					String pair = v;
					int semi = pair.indexOf(';');
					if (semi >= 0) pair = pair.substring(0, semi);
					if (pair.startsWith("vmware_soap_session")) {
						return pair.trim();
					}
				}
			}
		} catch (Exception ignored) {
			// Cookie capture is best-effort; a failure surfaces downstream
			// as UNREADABLE on esxcli controls, never a false pass.
		}
		return null;
	}

	public void disconnect() {
		if (vimPort != null && serviceContent != null) {
			try {
				vimPort.logout(serviceContent.getSessionManager());
			} catch (Exception ignored) {}
		}
		vimPort = null;
		serviceContent = null;
		esxcli = null;
		sessionCookie = null;
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

		try {
			List<ManagedObjectReference> hostRefs =
					getViewMembers(containerView);

			for (ManagedObjectReference hostRef : hostRefs) {
				String name = getProperty(hostRef, "name");
				if (name != null) {
					result.add(new HostInfo(hostRef, name, hostRef.getValue()));
				}
			}
		} finally {
			destroyViewQuietly(containerView);
		}
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

		try {
			List<ManagedObjectReference> refs = getViewMembersTyped(
					containerView, "VirtualMachine");

			for (ManagedObjectReference vmRef : refs) {
				String name = getProperty(vmRef, "name");
				if (name != null) {
					result.add(new VmInfo(vmRef, name, vmRef.getValue()));
				}
			}
		} finally {
			destroyViewQuietly(containerView);
		}
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

		try {
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
		} finally {
			destroyViewQuietly(containerView);
		}
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

		try {
			List<ManagedObjectReference> refs = getViewMembersTyped(
					containerView, "ClusterComputeResource");

			for (ManagedObjectReference ref : refs) {
				String name = getProperty(ref, "name");
				if (name != null) {
					result.add(new ClusterInfo(ref, name, ref.getValue()));
				}
			}
		} finally {
			destroyViewQuietly(containerView);
		}
		return result;
	}

	/**
	 * Generic, recipe-driven vim_property reader (canonical column 13).
	 *
	 * <p>This is the data-driven replacement for the three bespoke
	 * readers ({@code readSecurityPolicy}, {@code getClusterVsanConfig}).
	 * Given a resource MoRef and a list of that resource's vim_property
	 * controls (each carrying a {@code read_recipe} of the form
	 * {@code <style>:<vim_path>}), it returns a map keyed by the
	 * control's canonical {@code parameter} -> the typed value read from
	 * vim25 (or {@link #UNREADABLE} when the recipe resolved to nothing
	 * or its style was unknown).
	 *
	 * <p>Contract — three result states per control, mirroring the
	 * "unreadable is not compliant" rule:
	 * <ul>
	 *   <li>recipe resolves to a typed value -> that value (Boolean /
	 *       String / Number) is placed in the map under the parameter
	 *       key. The evaluator compares it.</li>
	 *   <li>recipe present + evaluable but the read found null / the
	 *       style could not extract / the style is unknown -> the
	 *       sentinel {@link #UNREADABLE} object is placed in the map.
	 *       The evaluator counts it as unreadable (excluded from
	 *       pass/fail/denominator), NEVER as a pass.</li>
	 *   <li>recipe empty / control not vim_property -> the key is absent
	 *       from the map (the control is non-evaluable; the evaluator
	 *       skips it entirely).</li>
	 * </ul>
	 *
	 * <p>Reflection-tolerant throughout — never casts to a concrete
	 * vim25 subclass. A missing accessor anywhere in the walk yields
	 * null, which surfaces as {@link #UNREADABLE}, never an exception.
	 */
	public Map<String, Object> readVimProperties(
			ManagedObjectReference moRef,
			List<BenchmarkProfile.Control> controls) throws Exception {
		ensureConnected();
		Map<String, Object> result = new HashMap<>();
		if (moRef == null || controls == null) return result;

		for (BenchmarkProfile.Control c : controls) {
			// Recipe-driven kinds: vim_property (vim25 PropertyCollector +
			// reflective walk) and esxcli (ExecuteSoap over the vCenter
			// session, build 36). Both consume the read_recipe column via
			// readByRecipe; the recipe's style prefix selects the reader.
			if (!"vim_property".equals(c.parameterKind)
					&& !"esxcli".equals(c.parameterKind)) {
				continue;
			}
			String recipe = c.readRecipe;
			if (recipe == null || recipe.trim().isEmpty()) {
				// Non-evaluable vim_property control (no recipe) — leave
				// the key absent so the evaluator skips it. Not an
				// unreadable: we never declared we could read it.
				continue;
			}
			Object value;
			try {
				value = readByRecipe(moRef, recipe.trim());
			} catch (Exception e) {
				// Defensive — readByRecipe is already null-on-miss, but
				// any unexpected reflective failure becomes unreadable,
				// never a throw that aborts the whole collection cycle.
				value = null;
			}
			result.put(c.parameter,
					value != null ? value : UNREADABLE);
		}
		return result;
	}

	/**
	 * Sentinel placed in the {@link #readVimProperties} result map when
	 * a control declared a recipe but the read could not produce a
	 * value. Distinct from "key absent" (non-evaluable, no recipe) and
	 * from a real {@code Boolean.FALSE}. The evaluator treats this as
	 * the explicit {@code unreadable} outcome.
	 */
	public static final Object UNREADABLE = new Object() {
		@Override public String toString() { return "(unreadable)"; }
	};

	/**
	 * Read one recipe ({@code <style>:<vim_path>}) against a resource
	 * MoRef and return the typed value, or null when the read finds
	 * nothing / the style is unknown.
	 *
	 * <p>The walk reproduces exactly what the retired bespoke readers
	 * did, generically:
	 * <ol>
	 *   <li>PropertyCollector resolves the longest leading prefix of the
	 *       path it can ({@link #getRawPropertyLongestPrefix}). For the
	 *       security-policy recipe this resolves
	 *       {@code config.defaultPortConfig}; for the vSAN recipe,
	 *       {@code configurationEx}.</li>
	 *   <li>Remaining segments are walked with reflective zero-arg
	 *       {@code get<Segment>()} getters
	 *       ({@link #invokeGetter}).</li>
	 *   <li>The {@code <style>} extractor is applied to the final node:
	 *       {@code bool_policy} unwraps a BoolPolicy {@code .value};
	 *       {@code bool} reads {@code is<Seg>()/get<Seg>()};
	 *       {@code scalar} returns the node as-is; {@code string_list_join}
	 *       joins a {@code List} on ",".</li>
	 * </ol>
	 */
	Object readByRecipe(ManagedObjectReference moRef, String recipe)
			throws Exception {
		int colon = recipe.indexOf(':');
		if (colon <= 0 || colon >= recipe.length() - 1) {
			// Malformed recipe (no style or no path) — unknown style,
			// treat as unreadable rather than guessing.
			return null;
		}
		String style = recipe.substring(0, colon).trim();
		String path = recipe.substring(colon + 1).trim();
		if (path.isEmpty()) return null;

		// esxcli style has a THREE-part grammar
		// (esxcli:<namespace.command>:<ResultField>) so its `path` itself
		// carries a colon. Handle it before the generic dotted-path split.
		if ("esxcli".equals(style)) {
			return readEsxcliRecipe(moRef, path);
		}

		// service_state style also has a THREE-part grammar
		// (service_state:<service_key>:<field>) — the `path` carries the
		// service key, then a colon, then the field (running|policy).
		// Handle it before the generic dotted-path split.
		if ("service_state".equals(style)) {
			return readServiceStateRecipe(moRef, path);
		}

		String[] segments = path.split("\\.");

		switch (style) {
			case "scalar":
				return readScalarRecipe(moRef, segments);
			case "bool":
				return readBoolRecipe(moRef, segments);
			case "bool_policy":
				return readBoolPolicyRecipe(moRef, segments);
			case "string_list_join":
				return readStringListJoinRecipe(moRef, segments);
			case "vm_hardware_device_absent":
				return readDeviceAbsentRecipe(moRef, segments);
			case "list_empty":
				return readListEmptyRecipe(moRef, segments);
			case "vlan_id_not":
				return readVlanIdNotRecipe(moRef, segments);
			default:
				// Unknown style — never guess. Null -> UNREADABLE.
				return null;
		}
	}

	/**
	 * esxcli style — {@code esxcli:<namespace.command>:<ResultField>}.
	 * Reads a PascalCase result field from an esxcli {@code get} command
	 * over the existing vCenter session (no host credentials) via
	 * {@link EsxcliSoapClient}. The host moid is {@code moRef.getValue()}
	 * (this style is HostSystem-only; on any other resource the
	 * RetrieveManagedMethodExecuter call fails and we return null ->
	 * UNREADABLE).
	 *
	 * <p>Typing: a value of {@code "true"}/{@code "false"} (case-
	 * insensitive) is returned as a {@link Boolean} so the evaluator's
	 * boolean compare path handles it (e.g.
	 * {@code LocalLogOutputIsPersistent}); anything else is returned as a
	 * String. A command-failure / absent-field / parse-failure returns
	 * {@code null} — which {@link #readVimProperties} folds to the
	 * UNREADABLE sentinel (loud, never a false pass — the build-35
	 * contract).
	 */
	private Object readEsxcliRecipe(ManagedObjectReference moRef, String path)
			throws Exception {
		if (esxcli == null) {
			// Not connected / no session cookie captured — cannot read.
			// Null -> UNREADABLE upstream, never a default.
			return null;
		}
		int sep = path.lastIndexOf(':');
		if (sep <= 0 || sep >= path.length() - 1) {
			// Missing the :<ResultField> segment — malformed, unreadable.
			return null;
		}
		String namespaceCommand = path.substring(0, sep).trim();
		String fieldSpec = path.substring(sep + 1).trim();
		if (namespaceCommand.isEmpty() || fieldSpec.isEmpty()) return null;

		String hostMoid = moRef != null ? moRef.getValue() : null;
		if (hostMoid == null || hostMoid.isEmpty()) return null;

		// Build 37 — row-selector grammar for `list` commands:
		//   <ResultField>[<SelectorField>=<SelectorValue>]
		// e.g. Value[Key=ciphers] (ssh server config list) or
		//      Shellaccess[UserID=dcui] (account list). A field with no
		//      bracket is a plain `get`-struct field (build-36 behavior,
		//      unchanged).
		String value;
		int lb = fieldSpec.indexOf('[');
		if (lb > 0 && fieldSpec.endsWith("]")) {
			String field = fieldSpec.substring(0, lb).trim();
			String selector = fieldSpec.substring(lb + 1,
					fieldSpec.length() - 1).trim();
			int eq = selector.indexOf('=');
			if (eq <= 0 || eq >= selector.length() - 1) {
				// Malformed selector (no field=value) — unreadable, never
				// a guess.
				return null;
			}
			String selectorField = selector.substring(0, eq).trim();
			String selectorValue = selector.substring(eq + 1).trim();
			if (field.isEmpty() || selectorField.isEmpty()
					|| selectorValue.isEmpty()) {
				return null;
			}
			value = esxcli.readRowField(hostMoid, namespaceCommand,
					selectorField, selectorValue, field);
		} else {
			value = esxcli.readField(hostMoid, namespaceCommand, fieldSpec);
		}
		if (value == null
				|| EsxcliSoapClient.COMMAND_FAILED.equals(value)) {
			// Field/row absent, or the command call itself failed. All are
			// UNREADABLE — never a sentinel pass.
			return null;
		}
		String trimmed = value.trim();
		if ("true".equalsIgnoreCase(trimmed)) return Boolean.TRUE;
		if ("false".equalsIgnoreCase(trimmed)) return Boolean.FALSE;
		return trimmed;
	}

	/**
	 * service_state style — {@code service_state:<service_key>:<field>}.
	 * Reads the host's service list ({@code config.service.service}, a
	 * {@code List<HostService>} hung off the {@code HostServiceInfo} at
	 * {@code config.service}), finds the entry whose {@code key} matches
	 * {@code <service_key>} (e.g. {@code TSM}, {@code TSM-SSH}, {@code ntpd}),
	 * and returns the requested {@code <field>}:
	 * <ul>
	 *   <li>{@code running} -> the service's {@code running} boolean
	 *       (vim25 {@code HostService.isRunning()} / {@code getRunning()})
	 *       as a {@link Boolean}, so the evaluator's boolean compare path
	 *       (Running/Stopped, true/false) handles it.</li>
	 *   <li>{@code policy} -> the service's {@code policy} String
	 *       ({@code on} / {@code off} / {@code automatic}) returned as-is.</li>
	 * </ul>
	 *
	 * <p>Reflection-tolerant and unreadable-safe throughout. A null returned
	 * here folds to the {@code UNREADABLE} sentinel upstream — NEVER a
	 * sentinel pass. Specifically returns null (-> UNREADABLE) when:
	 * <ul>
	 *   <li>the service list cannot be read (PropertyCollector / reflective
	 *       walk found nothing),</li>
	 *   <li>no service entry matches {@code <service_key>} — a missing
	 *       service is NOT treated as "stopped/compliant"; it is unreadable
	 *       (we cannot prove its state),</li>
	 *   <li>the field accessor is absent or returns the wrong type (wrong
	 *       guessed field name folds to UNREADABLE, never a guess-pass),</li>
	 *   <li>the {@code <field>} token is anything other than
	 *       {@code running} / {@code policy}.</li>
	 * </ul>
	 */
	private Object readServiceStateRecipe(ManagedObjectReference moRef,
			String path) throws Exception {
		// path = "<service_key>:<field>" (the leading "service_state:" was
		// already stripped by readByRecipe). The service key itself never
		// contains a colon, so split on the LAST colon to isolate the field.
		int sep = path.lastIndexOf(':');
		if (sep <= 0 || sep >= path.length() - 1) {
			// Missing the :<field> segment — malformed, unreadable.
			return null;
		}
		String serviceKey = path.substring(0, sep).trim();
		String field = path.substring(sep + 1).trim();
		if (serviceKey.isEmpty() || field.isEmpty()) return null;
		if (!"running".equals(field) && !"policy".equals(field)) {
			// Unknown field — never guess. Null -> UNREADABLE.
			return null;
		}
		if (moRef == null) return null;

		// Walk to the HostServiceInfo at config.service, then pull its
		// service list via getService(). PropertyCollector resolves the
		// longest leading prefix it can (config.service typically resolves
		// as a single path returning a HostServiceInfo); any remaining
		// segment is walked reflectively.
		String[] svcSegments = new String[] {"config", "service"};
		Object serviceInfo = walkToNode(moRef, svcSegments);
		if (serviceInfo == null) return null;

		// HostServiceInfo.getService() -> List<HostService>. Reflective so
		// we never cast to the concrete vim25 subclass (classloader / binding
		// drift tolerance). A missing accessor returns null -> UNREADABLE.
		Object listObj = invokeGetter(serviceInfo, "getService");
		if (!(listObj instanceof List)) {
			// Some bindings may expose the list under a different ArrayOfX
			// wrapper; fall back to the first List-returning accessor.
			listObj = firstListAccessor(serviceInfo);
		}
		if (!(listObj instanceof List)) return null;

		for (Object svc : (List<?>) listObj) {
			if (svc == null) continue;
			Object keyObj = invokeGetter(svc, "getKey");
			if (keyObj == null) continue;
			if (!serviceKey.equals(String.valueOf(keyObj))) continue;

			// Matched the service entry. Extract the requested field.
			if ("running".equals(field)) {
				// HostService.running is a boolean primitive; JAX-WS may
				// generate isRunning() (primitive) or getRunning() (wrapper)
				// depending on schema treatment. Try both shapes; a wrong /
				// absent accessor returns null -> UNREADABLE, never a guess.
				return readBoolean(svc, "isRunning", "getRunning");
			}
			// field == "policy" — HostService.policy is a String.
			Object policyObj = invokeGetter(svc, "getPolicy");
			if (policyObj == null) return null;
			String policy = String.valueOf(policyObj).trim();
			return policy.isEmpty() ? null : policy;
		}
		// No entry matched <service_key>. The service is absent from this
		// host's service list — we cannot prove its running/policy state, so
		// this is UNREADABLE, NOT a sentinel "stopped/compliant" pass.
		return null;
	}

	/**
	 * Walk to the node identified by the FULL segment path, returning
	 * the node object (or null on any missing accessor). Used by the
	 * scalar / string_list_join styles where the final segment IS the
	 * value node. PropertyCollector resolves the longest prefix it can;
	 * the rest is a reflective getter walk.
	 */
	private Object walkToNode(ManagedObjectReference moRef, String[] segments)
			throws Exception {
		int[] consumed = new int[1];
		Object node = getRawPropertyLongestPrefix(moRef, segments, consumed);
		for (int i = consumed[0]; i < segments.length; i++) {
			if (node == null) return null;
			node = invokeGetter(node, getterName(segments[i]));
		}
		return node;
	}

	private Object readScalarRecipe(ManagedObjectReference moRef,
			String[] segments) throws Exception {
		return walkToNode(moRef, segments);
	}

	/**
	 * bool style — walk to the PARENT of the final segment, then read
	 * the final segment as a boolean via {@code is<Field>()/get<Field>()}.
	 * Reproduces the vSAN reader: {@code configurationEx} (PropertyCollector)
	 * -> getVsanConfigInfo [-> getDefaultConfig] -> isEnabled/getEnabled
	 * (or isChecksumEnabled/getChecksumEnabled, etc.).
	 */
	private Boolean readBoolRecipe(ManagedObjectReference moRef,
			String[] segments) throws Exception {
		Object parent = walkToParent(moRef, segments);
		if (parent == null) return null;
		String field = segments[segments.length - 1];
		return readBoolean(parent, "is" + capitalize(field),
				"get" + capitalize(field));
	}

	/**
	 * bool_policy style — walk to the PARENT of the final segment
	 * (a DVSSecurityPolicy), then unwrap the final segment's BoolPolicy
	 * wrapper to its {@code .value}. Reproduces readSecurityPolicy:
	 * {@code config.defaultPortConfig} (PropertyCollector) ->
	 * getSecurityPolicy -> get<Field> (BoolPolicy) -> isValue/getValue.
	 */
	private Boolean readBoolPolicyRecipe(ManagedObjectReference moRef,
			String[] segments) throws Exception {
		Object parent = walkToParent(moRef, segments);
		if (parent == null) return null;
		String field = segments[segments.length - 1];
		return readBoolPolicy(parent, "get" + capitalize(field));
	}

	private String readStringListJoinRecipe(ManagedObjectReference moRef,
			String[] segments) throws Exception {
		Object node = walkToNode(moRef, segments);
		if (node == null) return null;
		if (node instanceof List) {
			List<?> list = (List<?>) node;
			if (list.isEmpty()) return null;
			StringBuilder sb = new StringBuilder();
			for (int i = 0; i < list.size(); i++) {
				if (i > 0) sb.append(',');
				sb.append(String.valueOf(list.get(i)));
			}
			return sb.toString();
		}
		// Some bindings wrap the list in an ArrayOfX with a getX()
		// accessor; reflectively pull a List out if present.
		Object inner = firstListAccessor(node);
		if (inner instanceof List) {
			List<?> list = (List<?>) inner;
			if (list.isEmpty()) return null;
			StringBuilder sb = new StringBuilder();
			for (int i = 0; i < list.size(); i++) {
				if (i > 0) sb.append(',');
				sb.append(String.valueOf(list.get(i)));
			}
			return sb.toString();
		}
		return null;
	}

	/**
	 * Result of {@link #readListConfirmed}. Carries the cardinal-trap
	 * distinction these styles depend on: whether the LIST itself was
	 * successfully obtained, independent of how many elements it holds.
	 *
	 * <ul>
	 *   <li>{@code !confirmed} — the container node or the list accessor
	 *       could NOT be read (PropertyCollector / reflective walk found
	 *       nothing, or the accessor did not return a {@code List}). This
	 *       is the failed-fetch case: callers MUST fold it to
	 *       {@code null} -> UNREADABLE. A failed fetch is NOT an empty
	 *       list and is NEVER scored as compliant.</li>
	 *   <li>{@code confirmed} with {@code list} non-null — a real
	 *       {@code List} was obtained off a non-null container node. It
	 *       may be empty (zero elements) — that is a genuine, scoreable
	 *       reading, distinct from a failed fetch.</li>
	 * </ul>
	 */
	private static final class ListRead {
		final boolean confirmed;
		final List<?> list;
		private ListRead(boolean confirmed, List<?> list) {
			this.confirmed = confirmed;
			this.list = list;
		}
		static ListRead failed() { return new ListRead(false, null); }
		static ListRead of(List<?> l) { return new ListRead(true, l); }
	}

	/**
	 * The CARDINAL-TRAP separator for the {@code vm_hardware_device_absent}
	 * and {@code list_empty} styles, where <em>compliant == empty</em>.
	 *
	 * <p>The fatal failure mode these styles must avoid is letting a FAILED
	 * read of the list fall through to "list is empty -> compliant". This
	 * helper makes the distinction explicit and positive:
	 *
	 * <ol>
	 *   <li>Walk to the <b>container node</b> (every segment except the
	 *       final list segment). If that node is {@code null}, the read
	 *       FAILED — we never reached the object that owns the list, so we
	 *       cannot assert anything about the list's contents.
	 *       -> {@link ListRead#failed()} (caller -> UNREADABLE).</li>
	 *   <li>The container node IS present (positive proof the read
	 *       reached the owning object). Invoke the final segment's
	 *       zero-arg getter. If it returns a {@code List} instance (even an
	 *       <b>empty</b> one), that is a CONFIRMED read of the collection.
	 *       -> {@link ListRead#of(list)}.</li>
	 *   <li>The accessor is absent or did not return a {@code List} (wrong
	 *       guessed field name, binding drift) — we did NOT positively
	 *       obtain the collection. -> {@link ListRead#failed()}
	 *       (caller -> UNREADABLE, never an empty-list pass).</li>
	 * </ol>
	 *
	 * <p>Note the asymmetry vs. {@code string_list_join}: that style maps an
	 * empty list to {@code null} (an empty NTP list is a coverage gap, never
	 * a {@code (non-empty)} pass). Here, by contrast, an empty list is the
	 * COMPLIANT outcome — so we must NOT collapse empty to null. The
	 * confirmation that we reached a non-null container node is what lets us
	 * trust the empty list as a real reading rather than a failed fetch.
	 */
	private ListRead readListConfirmed(ManagedObjectReference moRef,
			String[] segments) throws Exception {
		if (segments == null || segments.length == 0) return ListRead.failed();
		// Walk to the parent (owning) node of the final list segment.
		Object container = walkToParent(moRef, segments);
		if (container == null) {
			// Could not reach the object that owns the list. FAILED read —
			// NOT an empty list. This is the exact case the cardinal rule
			// forbids treating as compliant.
			return ListRead.failed();
		}
		String field = segments[segments.length - 1];
		Object listObj = invokeGetter(container, getterName(field));
		if (listObj instanceof List) {
			// CONFIRMED: a real List was obtained off a present container.
			// May be empty — that is a genuine reading, evaluated below.
			return ListRead.of((List<?>) listObj);
		}
		// Some bindings wrap a list in an ArrayOfX; try the first
		// List-returning accessor on the node the getter DID return (only
		// when that node itself is non-null — a null here means the field
		// accessor produced nothing, i.e. a failed fetch, not an empty list).
		if (listObj != null) {
			Object inner = firstListAccessor(listObj);
			if (inner instanceof List) {
				return ListRead.of((List<?>) inner);
			}
		}
		// Field accessor absent / wrong type / null — we did NOT positively
		// obtain the collection. FAILED read, never an empty-list pass.
		return ListRead.failed();
	}

	/**
	 * {@code vm_hardware_device_absent} style — Style B.
	 * Grammar: {@code vm_hardware_device_absent:<list_path>[:<TypeName>]}
	 * (the type filter is the optional trailing dotted segment), but in
	 * practice the recipe is written as
	 * {@code vm_hardware_device_absent:config.hardware.device.<DeviceTypeSimpleName>}
	 * — the FINAL segment names the vim25 device type to test for absence
	 * and the preceding segments are the list path
	 * ({@code config.hardware.device}).
	 *
	 * <p>Compliant ({@code Boolean.TRUE}) iff the device list was read AND
	 * contains <b>no</b> element whose runtime class simple-name equals the
	 * requested type. Non-compliant ({@code Boolean.FALSE}) iff at least one
	 * matching device is present. {@code null} (-> UNREADABLE) iff the
	 * device list could not be obtained (cardinal-trap separation:
	 * {@link #readListConfirmed} returns {@code !confirmed}).
	 *
	 * <p>Type matching is by {@code getClass().getSimpleName()} — never an
	 * {@code instanceof} against a concrete vim25 subclass — so it survives
	 * per-pak classloader isolation and binding drift. {@code VirtualDevice}
	 * subclasses report their concrete name (e.g. {@code VirtualPCIPassthrough}).
	 */
	private Boolean readDeviceAbsentRecipe(ManagedObjectReference moRef,
			String[] segments) throws Exception {
		if (segments.length < 2) return null;
		// Final segment = the device type simple-name to test for absence.
		// Preceding segments = the device list path (config.hardware.device).
		String typeName = segments[segments.length - 1];
		String[] listPath = new String[segments.length - 1];
		System.arraycopy(segments, 0, listPath, 0, segments.length - 1);

		ListRead read = readListConfirmed(moRef, listPath);
		if (!read.confirmed) {
			// FAILED to read the device list — UNREADABLE, never "absent".
			return null;
		}
		for (Object dev : read.list) {
			if (dev == null) continue;
			if (typeName.equals(dev.getClass().getSimpleName())) {
				// A device of the prohibited type is present -> NOT compliant.
				return Boolean.FALSE;
			}
		}
		// List confirmed and no matching device present -> device absent ->
		// compliant. (An empty device list also lands here, correctly: a
		// confirmed empty list means the type is absent.)
		return Boolean.TRUE;
	}

	/**
	 * {@code list_empty} style — Style C.
	 * Grammar: {@code list_empty:<list_path>} (e.g.
	 * {@code list_empty:config.vspanSession}).
	 *
	 * <p>Compliant ({@code Boolean.TRUE}) iff the list was read AND has zero
	 * elements. Non-compliant ({@code Boolean.FALSE}) iff the list was read
	 * AND has ≥1 element. {@code null} (-> UNREADABLE) iff the list could
	 * NOT be obtained — the failed-fetch case, kept strictly distinct from
	 * a genuinely-empty list by {@link #readListConfirmed}.
	 */
	private Boolean readListEmptyRecipe(ManagedObjectReference moRef,
			String[] segments) throws Exception {
		ListRead read = readListConfirmed(moRef, segments);
		if (!read.confirmed) {
			// FAILED to read the list — UNREADABLE, NOT "empty -> compliant".
			return null;
		}
		return read.list.isEmpty() ? Boolean.TRUE : Boolean.FALSE;
	}

	/**
	 * {@code vlan_id_not} style — Style D.
	 * Grammar: {@code vlan_id_not:<vlan_spec_path>} (e.g.
	 * {@code vlan_id_not:config.defaultPortConfig.vlan}).
	 *
	 * <p>Type-aware VGT (virtual guest tagging) detection. VGT is
	 * non-compliant. It presents either as a trunk spec
	 * ({@code VmwareDistributedVirtualSwitchTrunkVlanSpec}) or, on a plain
	 * id spec, as {@code vlanId == 4095}.
	 *
	 * <p>Compliant ({@code Boolean.TRUE}) iff the VLAN spec node was read
	 * AND it is a plain id spec ({@code ...VlanIdSpec}) AND its
	 * {@code vlanId != 4095}. Non-compliant ({@code Boolean.FALSE}) iff it
	 * is a trunk spec OR a plain id spec with {@code vlanId == 4095}.
	 * {@code null} (-> UNREADABLE) iff the spec node could not be read OR
	 * its runtime type is neither a recognized id spec nor a recognized
	 * trunk spec (unknown/unreadable spec type — never a guess-pass).
	 *
	 * <p>Type discrimination is by {@code getClass().getSimpleName()}
	 * substring match — never an {@code instanceof} against a concrete
	 * vim25 subclass — for classloader/binding tolerance.
	 */
	private Boolean readVlanIdNotRecipe(ManagedObjectReference moRef,
			String[] segments) throws Exception {
		Object specNode = walkToNode(moRef, segments);
		if (specNode == null) {
			// Could not read the VLAN spec — UNREADABLE, never a guess.
			return null;
		}
		String typeName = specNode.getClass().getSimpleName();
		// Trunk spec => VGT mode => NON-compliant. Recognized by the
		// "Trunk" marker in the runtime type name
		// (VmwareDistributedVirtualSwitchTrunkVlanSpec).
		if (typeName.contains("Trunk")) {
			return Boolean.FALSE;
		}
		// Plain id spec => read vlanId; 4095 also indicates VGT. Recognized
		// by the "VlanId" marker (VmwareDistributedVirtualSwitchVlanIdSpec).
		if (typeName.contains("VlanId")) {
			Object idObj = invokeGetter(specNode, "getVlanId");
			if (!(idObj instanceof Number)) {
				// Id spec but the id accessor did not yield a number — we
				// cannot decide. UNREADABLE, never a guess-pass.
				return null;
			}
			int vlanId = ((Number) idObj).intValue();
			return vlanId == 4095 ? Boolean.FALSE : Boolean.TRUE;
		}
		// Neither a recognized id spec nor a trunk spec (e.g. a PVLAN spec,
		// or an unexpected/unreadable type). We cannot assert VGT-vs-not, so
		// this is UNREADABLE — NEVER a guess-pass.
		return null;
	}

	/**
	 * Walk to the parent node of the final path segment. PropertyCollector
	 * resolves the longest prefix; remaining intermediate segments (all
	 * but the last) are walked reflectively.
	 */
	private Object walkToParent(ManagedObjectReference moRef,
			String[] segments) throws Exception {
		int[] consumed = new int[1];
		// CAP at segments.length - 1: PropertyCollector must NOT be
		// allowed to consume the final (leaf) segment for the
		// bool / bool_policy styles, because the leaf is a boolean or a
		// BoolPolicy wrapper that the style extractor reads via a
		// reflective accessor on its PARENT. If PropertyCollector
		// resolved the leaf directly we'd lose the wrapper and the
		// extractor would null out (false unreadable). Capping the
		// probe to the parent depth guarantees the walk reaches exactly
		// the node the retired bespoke readers reflected from:
		//   bool_policy -> the DVSSecurityPolicy (parent of <field>)
		//   bool        -> the VsanClusterConfigInfo[.defaultConfig]
		//                  (parent of <field>)
		Object node = getRawPropertyLongestPrefix(moRef, segments,
				segments.length - 1, consumed);
		// Walk reflective getters for every intermediate segment up to,
		// but not including, the final one.
		for (int i = consumed[0]; i < segments.length - 1; i++) {
			if (node == null) return null;
			node = invokeGetter(node, getterName(segments[i]));
		}
		return node;
	}

	/**
	 * Try PropertyCollector against progressively shorter dotted
	 * prefixes of {@code segments} (longest first, but no longer than
	 * {@code maxLen} segments) and return the first non-null value,
	 * writing the number of segments consumed into {@code consumedOut[0]}.
	 * Returns null with consumed=0 when no prefix resolves (the caller
	 * then treats it as unreadable).
	 *
	 * <p>Longest-first matters: {@code config.defaultPortConfig}
	 * resolves as a single PropertyCollector path on a DVS. We want the
	 * deepest node PropertyCollector WILL hand back (within the cap),
	 * then reflect the rest — which is exactly what the bespoke readers
	 * did (PropertyCollector for {@code config.defaultPortConfig} /
	 * {@code configurationEx}; reflective getters for the tail).
	 */
	private Object getRawPropertyLongestPrefix(ManagedObjectReference moRef,
			String[] segments, int[] consumedOut) throws Exception {
		return getRawPropertyLongestPrefix(moRef, segments,
				segments.length, consumedOut);
	}

	private Object getRawPropertyLongestPrefix(ManagedObjectReference moRef,
			String[] segments, int maxLen, int[] consumedOut)
			throws Exception {
		int start = Math.min(maxLen, segments.length);
		for (int len = start; len >= 1; len--) {
			StringBuilder p = new StringBuilder();
			for (int i = 0; i < len; i++) {
				if (i > 0) p.append('.');
				p.append(segments[i]);
			}
			Object v;
			try {
				v = getRawProperty(moRef, p.toString());
			} catch (Exception e) {
				v = null;
			}
			if (v != null) {
				consumedOut[0] = len;
				return v;
			}
		}
		consumedOut[0] = 0;
		return null;
	}

	private static String getterName(String segment) {
		return "get" + capitalize(segment);
	}

	private static String capitalize(String s) {
		if (s == null || s.isEmpty()) return s;
		return Character.toUpperCase(s.charAt(0)) + s.substring(1);
	}

	/**
	 * Reflectively find the first zero-arg getter on {@code node} that
	 * returns a {@code List} — used by string_list_join to peel an
	 * ArrayOfX wrapper. Returns null when none is found.
	 */
	private Object firstListAccessor(Object node) {
		if (node == null) return null;
		for (java.lang.reflect.Method m : node.getClass().getMethods()) {
			if (m.getParameterTypes().length != 0) continue;
			if (!m.getName().startsWith("get")) continue;
			if (!List.class.isAssignableFrom(m.getReturnType())) continue;
			try {
				return m.invoke(node);
			} catch (Exception ignored) {
				return null;
			}
		}
		return null;
	}

	/**
	 * Probe whether a cluster has a vSAN configuration object at all.
	 *
	 * <p>The bulk vSAN read is now data-driven via
	 * {@link #readVimProperties} + the {@code bool:configurationEx.
	 * vsanConfigInfo.*} recipes (canonical column 13). But the collector
	 * still needs to distinguish a NON-vSAN cluster — where the
	 * vsanConfig controls are genuinely N/A and should be skipped
	 * silently — from a vSAN cluster where a field read back null (a
	 * real coverage gap that should surface as unreadable). The retired
	 * {@code getClusterVsanConfig} made that distinction by returning an
	 * empty map when {@code configurationEx.vsanConfigInfo} was absent;
	 * this probe preserves it.
	 *
	 * <p>vim25 surface:
	 * {@code ClusterComputeResource.configurationEx} (a
	 * {@code ClusterConfigInfoEx}) -> {@code getVsanConfigInfo()}. Returns
	 * {@code false} when either is null (non-vSAN cluster, or
	 * configurationEx absent), {@code true} when the vSAN config object
	 * is present. Reflection-tolerant; never casts.
	 */
	public boolean hasVsanConfig(ManagedObjectReference clusterRef)
			throws Exception {
		ensureConnected();
		if (clusterRef == null) return false;
		// configurationEx is the rich ClusterConfigInfoEx; the older
		// 'configuration' property is the legacy ClusterConfigInfo that
		// does NOT carry vsanConfigInfo. Use configurationEx.
		Object configEx = getRawProperty(clusterRef, "configurationEx");
		if (configEx == null) return false;
		Object vsanCfg = invokeGetter(configEx, "getVsanConfigInfo");
		return vsanCfg != null;
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

		try {
			List<ManagedObjectReference> refs = getViewMembersTyped(
					containerView, "DistributedVirtualPortgroup");

			for (ManagedObjectReference ref : refs) {
				String name = getProperty(ref, "name");
				if (name != null) {
					result.add(new DvpgInfo(ref, name, ref.getValue()));
				}
			}
		} finally {
			destroyViewQuietly(containerView);
		}
		return result;
	}

	// DVS / DVPG security-policy reads and the cluster vSAN read are no
	// longer bespoke: they are driven by the canonical read_recipe
	// column via readVimProperties + readByRecipe above (bool_policy
	// for the securityPolicy.* fields, bool for vsanConfig.*). The
	// reflective primitives those recipes use — readBoolPolicy,
	// readBoolean, invokeGetter, getRawProperty — are retained below.

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
	 * Release a ContainerView, swallowing any failure. Called from the
	 * {@code finally} of every inventory walker so the server-side view is
	 * always destroyed — even when the {@code retrieveProperties} membership
	 * read throws (a PropertyCollector network call). Without this, a SOAP
	 * error mid-walk would skip {@code destroyView} and leak the view on the
	 * vCenter for the session lifetime; across a long-running collector with
	 * intermittent errors those accumulate. Null-guarded (a failed
	 * createContainerView never reaches here, but be defensive) and never
	 * re-throws — view cleanup failure must not mask the original exception
	 * the {@code finally} is unwinding, nor abort the collection cycle.
	 */
	private void destroyViewQuietly(ManagedObjectReference containerView) {
		if (containerView == null) return;
		try {
			vimPort.destroyView(containerView);
		} catch (Exception ignored) {
			// Best-effort cleanup; the session logout will reap any
			// straggler views when the cycle's connection is torn down.
		}
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
