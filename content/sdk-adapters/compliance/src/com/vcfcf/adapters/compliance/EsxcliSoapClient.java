package com.vcfcf.adapters.compliance;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLSocketFactory;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

/**
 * Raw-SOAP esxcli reader that rides the adapter's <b>existing vCenter
 * session</b> — no host credentials, no per-host SOAP session, no
 * tickets. It reproduces the proven {@code ReflectManagedMethodExecuter
 * .ExecuteSoap} encoding from
 * {@code context/investigations/esxcli-soap-reflect-executer-spike.md}
 * §0 verbatim.
 *
 * <p><b>Why raw SOAP and not JAX-WS stubs.</b> The reflect / dynamic
 * esxcli types ({@code ReflectManagedMethodExecuter}, the
 * {@code vim.EsxCLI.*} dynamic managed types) are NOT in the bundled
 * vim25 bindings (they live in the internal {@code urn:reflect} WSDL,
 * version {@code vim.version.version5}, which neither stock binding
 * ships). So there is no generated stub to call and — by construction —
 * no concrete type to cast to. This client hand-builds the SOAP
 * envelope, POSTs it to the vCenter {@code /sdk} with the live vCenter
 * session cookie, and parses the response DOM generically. That matches
 * the skill's "reflection-tolerant / never cast" posture: a missing
 * field is null (skip), never an exception and never a default.
 *
 * <p><b>The three-call sequence</b> (all over the one vCenter session):
 * <ol>
 *   <li>{@code RetrieveManagedMethodExecuter} with {@code _this
 *       type="HostSystem"} = the host MoRef -> the executer MoRef.</li>
 *   <li>{@code ExecuteSoap} on that executer: {@code moid =
 *       "ha-cli-handler-" + namespace-with-dashes}; {@code version =
 *       "urn:vim25/5.0"} (constant — the spike fix); {@code method =
 *       "vim.EsxCLI." + namespace-dotted}; {@code argument} omitted for
 *       a no-arg {@code get}.</li>
 *   <li>The response {@code returnval/response} holds XML-escaped inner
 *       {@code <obj>}; this client unescapes (the parser does it for
 *       free since {@code response} is text-content) and reads the
 *       PascalCase child elements.</li>
 * </ol>
 *
 * <p><b>Per-cycle, per-host, per-command cache.</b> One esxcli command
 * returns many fields, and many controls may reference the same command
 * ({@code system.syslog.config.get}). {@link #readCommandFields} caches
 * the parsed field map per (hostMoid, namespace.command) for the
 * lifetime of this client instance (one collection cycle), so multiple
 * controls cost exactly one {@code ExecuteSoap} per host per cycle. The
 * executer MoRef (call 1) is cached per host the same way.
 */
final class EsxcliSoapClient {

	/**
	 * Sentinel returned by {@link #readField} when the command call
	 * itself failed (unknown command / SOAP fault / parse failure) — as
	 * opposed to the command succeeding but not carrying the requested
	 * field. Both map to UNREADABLE upstream, but the distinction is
	 * preserved in logs.
	 */
	static final String COMMAND_FAILED = "__esxcli_command_failed__";

	private final String sdkUrl;
	private final String sessionCookie;
	private final SSLSocketFactory sslFactory;

	// Per-cycle caches (this client is constructed once per collection
	// cycle in VSphereClient).
	//   hostMoid -> executer MoRef value (call 1)
	private final Map<String, String> executerByHost = new HashMap<>();
	//   hostMoid + "|" + namespace.command -> parsed field map
	//   (the value is COMMAND_FAILED_MAP for a failed call, so a second
	//   control referencing the same command does NOT re-issue the call)
	private final Map<String, Map<String, String>> resultCache =
			new HashMap<>();

	/** Cached marker for a failed command, distinct from an empty map. */
	private static final Map<String, String> COMMAND_FAILED_MAP =
			java.util.Collections.singletonMap(COMMAND_FAILED, "1");

	EsxcliSoapClient(String sdkUrl, String sessionCookie,
			SSLSocketFactory sslFactory) {
		this.sdkUrl = sdkUrl;
		this.sessionCookie = sessionCookie;
		this.sslFactory = sslFactory;
	}

	/**
	 * Read a single PascalCase field from an esxcli {@code get} command
	 * for a host. Returns the field's text value, or {@code null} when
	 * the command succeeded but the field is absent, or
	 * {@link #COMMAND_FAILED} when the command call itself failed
	 * (unknown command / fault / parse error). Upstream maps both
	 * {@code null} and {@code COMMAND_FAILED} to the UNREADABLE outcome.
	 *
	 * @param hostMoid          the {@code host-N} MoRef value
	 * @param namespaceCommand  dotted, e.g. {@code system.syslog.config.get}
	 * @param field             PascalCase result field, e.g.
	 *                          {@code LocalLogOutputIsPersistent}
	 */
	String readField(String hostMoid, String namespaceCommand, String field) {
		Map<String, String> fields = readCommandFields(hostMoid, namespaceCommand);
		if (fields == null || fields == COMMAND_FAILED_MAP) {
			return COMMAND_FAILED;
		}
		return fields.get(field);
	}

	/**
	 * Read (and cache) the full field map for one esxcli {@code get}
	 * command on one host. The first call for a given (host, command)
	 * issues the two SOAP calls; subsequent calls within the cycle hit
	 * the cache. Returns {@code null} / {@link #COMMAND_FAILED_MAP} on
	 * failure (cached so it isn't retried this cycle), else a
	 * PascalCase field -> text-value map.
	 */
	synchronized Map<String, String> readCommandFields(String hostMoid,
			String namespaceCommand) {
		String cacheKey = hostMoid + "|" + namespaceCommand;
		Map<String, String> cached = resultCache.get(cacheKey);
		if (cached != null) {
			return cached == COMMAND_FAILED_MAP ? COMMAND_FAILED_MAP : cached;
		}

		Map<String, String> result;
		try {
			String executer = getExecuter(hostMoid);
			if (executer == null) {
				resultCache.put(cacheKey, COMMAND_FAILED_MAP);
				return COMMAND_FAILED_MAP;
			}
			result = executeGet(executer, namespaceCommand);
		} catch (Exception e) {
			// Any failure -> command-failed sentinel, cached so a second
			// control on the same command doesn't re-issue the call.
			resultCache.put(cacheKey, COMMAND_FAILED_MAP);
			return COMMAND_FAILED_MAP;
		}
		if (result == null) {
			resultCache.put(cacheKey, COMMAND_FAILED_MAP);
			return COMMAND_FAILED_MAP;
		}
		resultCache.put(cacheKey, result);
		return result;
	}

	// ----- Call 1: RetrieveManagedMethodExecuter --------------------------

	private synchronized String getExecuter(String hostMoid) throws Exception {
		String cached = executerByHost.get(hostMoid);
		if (cached != null) return cached;

		String body =
				"<RetrieveManagedMethodExecuter xmlns=\"urn:vim25\">"
				+ "<_this type=\"HostSystem\">" + xmlEscape(hostMoid) + "</_this>"
				+ "</RetrieveManagedMethodExecuter>";
		Document resp = post(body, "urn:vim25/RetrieveManagedMethodExecuter");
		if (resp == null) return null;
		// Response: <RetrieveManagedMethodExecuterResponse><returnval
		//   type="ReflectManagedMethodExecuter">ManagedMethodExecuter-N
		//   </returnval></...>
		Element returnval = firstChildByLocalName(resp.getDocumentElement(),
				"returnval");
		if (returnval == null) return null;
		String executer = textOf(returnval);
		if (executer == null || executer.trim().isEmpty()) return null;
		executer = executer.trim();
		executerByHost.put(hostMoid, executer);
		return executer;
	}

	// ----- Call 2: ExecuteSoap (no-arg get) -------------------------------

	/**
	 * Execute an esxcli {@code get} command via {@code ExecuteSoap} and
	 * parse the inner {@code <obj>} into a PascalCase field map. Returns
	 * {@code null} on a SOAP fault, an esxcli-level {@code <fault>}, or a
	 * missing/empty {@code <response>}.
	 *
	 * <p>moid / method / version derivation (spike §0.4), mechanical:
	 * for command parts {@code [p0 ... pN]},
	 * {@code namespace = p0..p(N-1)}; {@code moid = "ha-cli-handler-" +
	 * namespace joined by "-"}; {@code method = "vim.EsxCLI." +
	 * p0..pN joined by "."}; {@code version = "urn:vim25/5.0"}.
	 */
	private Map<String, String> executeGet(String executer,
			String namespaceCommand) throws Exception {
		String[] parts = namespaceCommand.split("\\.");
		if (parts.length < 2) {
			// Need at least <namespace>.<command>.
			return null;
		}
		StringBuilder nsDashes = new StringBuilder();
		for (int i = 0; i < parts.length - 1; i++) {
			if (i > 0) nsDashes.append('-');
			nsDashes.append(parts[i]);
		}
		String moid = "ha-cli-handler-" + nsDashes;
		String method = "vim.EsxCLI." + namespaceCommand;
		String version = "urn:vim25/5.0";

		String body =
				"<ExecuteSoap xmlns=\"urn:vim25\">"
				+ "<_this type=\"ReflectManagedMethodExecuter\">"
				+ xmlEscape(executer) + "</_this>"
				+ "<moid>" + xmlEscape(moid) + "</moid>"
				+ "<version>" + xmlEscape(version) + "</version>"
				+ "<method>" + xmlEscape(method) + "</method>"
				// <argument> omitted for a no-arg get (spike §0.2).
				+ "</ExecuteSoap>";

		Document resp = post(body, "urn:vim25/ExecuteSoap");
		if (resp == null) return null;

		Element returnval = firstChildByLocalName(resp.getDocumentElement(),
				"returnval");
		if (returnval == null) return null;

		// An esxcli-level error comes back as <fault> inside returnval
		// (faultMsg / faultDetail); treat as command-failed.
		Element fault = firstChildByLocalName(returnval, "fault");
		if (fault != null) {
			return null;
		}

		Element response = firstChildByLocalName(returnval, "response");
		if (response == null) return null;
		String innerXml = textOf(response);
		if (innerXml == null || innerXml.trim().isEmpty()) return null;

		// The text content of <response> IS the (already-unescaped by the
		// XML parser) inner <obj> document. Parse it as a standalone doc.
		// It carries an xsi:type without a namespace declaration for the
		// xsi prefix, so parse non-namespace-aware and read by local name.
		Document inner = parseXml(innerXml.trim());
		if (inner == null) return null;
		Element obj = inner.getDocumentElement();
		if (obj == null) return null;

		// get -> single struct: PascalCase fields are direct children.
		// (list -> ArrayOfDataObject is out of scope for this slice; the
		//  syslog proof uses get only.)
		Map<String, String> fields = new HashMap<>();
		NodeList children = obj.getChildNodes();
		for (int i = 0; i < children.getLength(); i++) {
			Node n = children.item(i);
			if (n.getNodeType() != Node.ELEMENT_NODE) continue;
			Element child = (Element) n;
			String name = localName(child);
			if (name == null) continue;
			fields.put(name, textOf(child));
		}
		return fields;
	}

	// ----- HTTP / XML plumbing -------------------------------------------

	/**
	 * POST a SOAP body to the vCenter {@code /sdk} with the live vCenter
	 * session cookie and return the parsed response Document, or
	 * {@code null} on a non-2xx response (a SOAP fault HTTP 500 included
	 * — the caller maps any failure to command-failed). Reuses the
	 * adapter's trust-all SSL factory.
	 */
	private Document post(String soapBody, String soapAction) throws Exception {
		String envelope =
				"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
				+ "<soapenv:Envelope "
				+ "xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" "
				+ "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
				+ "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\">"
				+ "<soapenv:Body>" + soapBody + "</soapenv:Body>"
				+ "</soapenv:Envelope>";

		URL url = new URL(sdkUrl);
		HttpURLConnection conn = (HttpURLConnection) url.openConnection();
		if (conn instanceof HttpsURLConnection && sslFactory != null) {
			((HttpsURLConnection) conn).setSSLSocketFactory(sslFactory);
		}
		conn.setRequestMethod("POST");
		conn.setDoOutput(true);
		conn.setConnectTimeout(30000);
		conn.setReadTimeout(120000);
		conn.setRequestProperty("Content-Type", "text/xml; charset=utf-8");
		conn.setRequestProperty("SOAPAction", soapAction);
		if (sessionCookie != null && !sessionCookie.isEmpty()) {
			conn.setRequestProperty("Cookie", sessionCookie);
		}

		byte[] payload = envelope.getBytes(StandardCharsets.UTF_8);
		try (OutputStream os = conn.getOutputStream()) {
			os.write(payload);
		}

		int code = conn.getResponseCode();
		InputStream is = (code >= 200 && code < 300)
				? conn.getInputStream() : conn.getErrorStream();
		byte[] respBytes = drain(is);
		conn.disconnect();
		if (code < 200 || code >= 300) {
			// SOAP fault (500) or auth failure — command-failed upstream.
			return null;
		}
		if (respBytes == null || respBytes.length == 0) return null;
		return parseXml(new String(respBytes, StandardCharsets.UTF_8));
	}

	private static byte[] drain(InputStream is) throws Exception {
		if (is == null) return null;
		ByteArrayOutputStream bos = new ByteArrayOutputStream();
		byte[] buf = new byte[8192];
		int n;
		while ((n = is.read(buf)) >= 0) {
			bos.write(buf, 0, n);
		}
		is.close();
		return bos.toByteArray();
	}

	private static Document parseXml(String xml) {
		try {
			DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
			// Non-namespace-aware: we read by LOCAL name throughout, and
			// the inner <obj> uses an xsi: prefix without a declaration on
			// the standalone fragment (a namespace-aware parse would
			// reject it). Disable external entities defensively.
			dbf.setNamespaceAware(false);
			try {
				dbf.setFeature(
						"http://apache.org/xml/features/disallow-doctype-decl",
						true);
			} catch (Exception ignored) { /* not all impls support it */ }
			try {
				dbf.setFeature(
						"http://xml.org/sax/features/external-general-entities",
						false);
			} catch (Exception ignored) {}
			try {
				dbf.setFeature(
						"http://xml.org/sax/features/external-parameter-entities",
						false);
			} catch (Exception ignored) {}
			DocumentBuilder db = dbf.newDocumentBuilder();
			return db.parse(new java.io.ByteArrayInputStream(
					xml.getBytes(StandardCharsets.UTF_8)));
		} catch (Exception e) {
			return null;
		}
	}

	/** First direct-child Element whose local name equals {@code name}. */
	private static Element firstChildByLocalName(Element parent, String name) {
		if (parent == null) return null;
		// Search the whole subtree shallowly first (direct children), then
		// fall back to a descendant search so we tolerate the SOAP Body /
		// Envelope wrapping without binding to the exact nesting depth.
		Element direct = firstDirectChild(parent, name);
		if (direct != null) return direct;
		NodeList all = parent.getElementsByTagName("*");
		for (int i = 0; i < all.getLength(); i++) {
			Node n = all.item(i);
			if (n.getNodeType() == Node.ELEMENT_NODE
					&& name.equals(localName((Element) n))) {
				return (Element) n;
			}
		}
		return null;
	}

	private static Element firstDirectChild(Element parent, String name) {
		NodeList kids = parent.getChildNodes();
		for (int i = 0; i < kids.getLength(); i++) {
			Node n = kids.item(i);
			if (n.getNodeType() == Node.ELEMENT_NODE
					&& name.equals(localName((Element) n))) {
				return (Element) n;
			}
		}
		return null;
	}

	/** Local name (strip any prefix) of an element. */
	private static String localName(Element e) {
		String ln = e.getLocalName();
		if (ln != null) return ln;
		String tag = e.getTagName();
		int colon = tag.indexOf(':');
		return colon >= 0 ? tag.substring(colon + 1) : tag;
	}

	/** Concatenated text content of an element. */
	private static String textOf(Element e) {
		if (e == null) return null;
		return e.getTextContent();
	}

	private static String xmlEscape(String s) {
		if (s == null) return "";
		StringBuilder sb = new StringBuilder(s.length());
		for (int i = 0; i < s.length(); i++) {
			char c = s.charAt(i);
			switch (c) {
				case '&': sb.append("&amp;"); break;
				case '<': sb.append("&lt;"); break;
				case '>': sb.append("&gt;"); break;
				case '"': sb.append("&quot;"); break;
				case '\'': sb.append("&apos;"); break;
				default: sb.append(c);
			}
		}
		return sb.toString();
	}
}
