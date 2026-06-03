package com.vcfcf.adapters.compliance;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
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
 * ({@code system.syslog.config.get}). {@link #readCommandResult} caches
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
	//   hostMoid + "|" + namespace.command -> parsed result (struct OR
	//   rows). A FAILED ParsedResult is cached so a second control
	//   referencing the same command does NOT re-issue the call.
	private final Map<String, ParsedResult> resultCache = new HashMap<>();

	/**
	 * Parsed esxcli command result. Exactly one of {@code struct}
	 * (a {@code get} command's single field map) or {@code rows} (a
	 * {@code list} command's {@code ArrayOfDataObject} rows) is non-null
	 * on success; {@code failed} is true (and both null) when the
	 * command call itself failed (unknown command / fault / parse error).
	 * Cached per (host, command) for the cycle.
	 */
	private static final class ParsedResult {
		final boolean failed;
		final Map<String, String> struct;          // get -> field map
		final List<Map<String, String>> rows;       // list -> row field maps

		private ParsedResult(boolean failed, Map<String, String> struct,
				List<Map<String, String>> rows) {
			this.failed = failed;
			this.struct = struct;
			this.rows = rows;
		}

		static ParsedResult ofStruct(Map<String, String> struct) {
			return new ParsedResult(false, struct, null);
		}

		static ParsedResult ofRows(List<Map<String, String>> rows) {
			return new ParsedResult(false, null, rows);
		}

		static ParsedResult ofFailure() {
			return new ParsedResult(true, null, null);
		}
	}

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
		ParsedResult parsed = readCommandResult(hostMoid, namespaceCommand);
		if (parsed == null || parsed.failed) {
			return COMMAND_FAILED;
		}
		// A get-struct exposes its fields directly; a list exposes none at
		// the top level, so a plain field read on a list returns null (the
		// caller must use the row-selecting overload). Build-36 callers
		// only ever read get-struct fields, so this is unchanged for them.
		if (parsed.struct != null) {
			return parsed.struct.get(field);
		}
		return null;
	}

	/**
	 * Build-37 row-selecting read for {@code list} commands that return
	 * {@code ArrayOfDataObject} rows (e.g.
	 * {@code system.ssh.server.config.list},
	 * {@code system.account.list}). Finds the first row whose
	 * {@code selectorField} text equals {@code selectorValue}
	 * (case-insensitive) and returns that row's {@code field} text.
	 *
	 * <p>Returns {@code null} when the command succeeded but no row
	 * matched the selector, or the matched row lacks {@code field}, or
	 * the command returned a get-struct rather than a list (a selector
	 * was applied to a non-list command — a recipe authoring error,
	 * surfaced as UNREADABLE rather than guessed). Returns
	 * {@link #COMMAND_FAILED} when the command call itself failed.
	 * Both null and COMMAND_FAILED fold to UNREADABLE upstream — never
	 * a false pass (the build-35 contract).
	 *
	 * @param selectorField  PascalCase row field to match on, e.g.
	 *                       {@code Key} (ssh config) / {@code UserID}
	 *                       (accounts)
	 * @param selectorValue  the row value to match, e.g. {@code ciphers}
	 *                       / {@code dcui}
	 * @param field          PascalCase row field to return, e.g.
	 *                       {@code Value} / {@code Shellaccess}
	 */
	String readRowField(String hostMoid, String namespaceCommand,
			String selectorField, String selectorValue, String field) {
		ParsedResult parsed = readCommandResult(hostMoid, namespaceCommand);
		if (parsed == null || parsed.failed) {
			return COMMAND_FAILED;
		}
		if (parsed.rows == null) {
			// A selector was applied to a command that did not return a
			// list — not readable as a row. UNREADABLE upstream.
			return null;
		}
		for (Map<String, String> row : parsed.rows) {
			String sel = row.get(selectorField);
			if (sel != null && sel.trim().equalsIgnoreCase(selectorValue)) {
				return row.get(field);
			}
		}
		// No matching row — the selector value isn't present. UNREADABLE.
		return null;
	}

	/**
	 * Execute (and cache) one esxcli command on one host. The first call
	 * for a given (host, command) issues the two SOAP calls; subsequent
	 * calls within the cycle hit the cache. Returns a FAILED
	 * {@link ParsedResult} (cached so it isn't retried this cycle) on any
	 * failure, else a struct ({@code get}) or rows ({@code list}) result.
	 */
	synchronized ParsedResult readCommandResult(String hostMoid,
			String namespaceCommand) {
		String cacheKey = hostMoid + "|" + namespaceCommand;
		ParsedResult cached = resultCache.get(cacheKey);
		if (cached != null) {
			return cached;
		}

		ParsedResult result;
		try {
			String executer = getExecuter(hostMoid);
			if (executer == null) {
				result = ParsedResult.ofFailure();
			} else {
				result = executeCommand(executer, namespaceCommand);
			}
		} catch (Exception e) {
			// Any failure -> command-failed result, cached so a second
			// control on the same command doesn't re-issue the call.
			result = ParsedResult.ofFailure();
		}
		if (result == null) {
			result = ParsedResult.ofFailure();
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

	// ----- Call 2: ExecuteSoap (no-arg get OR list) -----------------------

	/**
	 * Execute an esxcli {@code get} or {@code list} command via
	 * {@code ExecuteSoap} and parse the inner {@code <obj>} into either a
	 * struct field map ({@code get}) or a list of row field maps
	 * ({@code list} -> {@code ArrayOfDataObject}). Returns a FAILED
	 * {@link ParsedResult} on a SOAP fault, an esxcli-level
	 * {@code <fault>}, or a missing/empty {@code <response>}.
	 *
	 * <p>moid / method / version derivation (spike §0.4), mechanical:
	 * for command parts {@code [p0 ... pN]},
	 * {@code namespace = p0..p(N-1)}; {@code moid = "ha-cli-handler-" +
	 * namespace joined by "-"}; {@code method = "vim.EsxCLI." +
	 * p0..pN joined by "."}; {@code version = "urn:vim25/5.0"}.
	 *
	 * <p>Build 37 only handles NO-ARG commands ({@code get} / {@code
	 * list} with no key). Argument-bearing commands (e.g. firewall
	 * {@code allowedip.list} with a {@code rulesetid}) are not issued by
	 * any current recipe; see the held-controls note in the build log.
	 */
	private ParsedResult executeCommand(String executer,
			String namespaceCommand) throws Exception {
		String[] parts = namespaceCommand.split("\\.");
		if (parts.length < 2) {
			// Need at least <namespace>.<command>.
			return ParsedResult.ofFailure();
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
				// <argument> omitted for a no-arg get/list (spike §0.2).
				+ "</ExecuteSoap>";

		Document resp = post(body, "urn:vim25/ExecuteSoap");
		if (resp == null) return ParsedResult.ofFailure();

		Element returnval = firstChildByLocalName(resp.getDocumentElement(),
				"returnval");
		if (returnval == null) return ParsedResult.ofFailure();

		// An esxcli-level error comes back as <fault> inside returnval
		// (faultMsg / faultDetail); treat as command-failed.
		Element fault = firstChildByLocalName(returnval, "fault");
		if (fault != null) {
			return ParsedResult.ofFailure();
		}

		Element response = firstChildByLocalName(returnval, "response");
		if (response == null) return ParsedResult.ofFailure();
		String innerXml = textOf(response);
		if (innerXml == null || innerXml.trim().isEmpty()) {
			return ParsedResult.ofFailure();
		}

		// The text content of <response> IS the (already-unescaped by the
		// XML parser) inner <obj> document. Parse it as a standalone doc.
		// It carries an xsi:type without a namespace declaration for the
		// xsi prefix, so parse non-namespace-aware and read by local name.
		Document inner = parseXml(innerXml.trim());
		if (inner == null) return ParsedResult.ofFailure();
		Element obj = inner.getDocumentElement();
		if (obj == null) return ParsedResult.ofFailure();

		// Disambiguate get vs list by the inner obj's xsi:type
		// (spike §0.3): "ArrayOfDataObject" -> list of <DataObject> rows;
		// anything else -> a single get struct.
		String xsiType = obj.getAttribute("xsi:type");
		boolean isList = xsiType != null
				&& xsiType.contains("ArrayOfDataObject");
		// Defensive: even without the attribute, if the obj's element
		// children are ALL <DataObject>, treat it as a list.
		if (!isList && hasDataObjectChildren(obj)) {
			isList = true;
		}

		if (isList) {
			List<Map<String, String>> rows = new ArrayList<>();
			NodeList children = obj.getChildNodes();
			for (int i = 0; i < children.getLength(); i++) {
				Node n = children.item(i);
				if (n.getNodeType() != Node.ELEMENT_NODE) continue;
				Element row = (Element) n;
				// Each row is a <DataObject> (some bindings drop the
				// element name to the row's own type — accept any element
				// child as a row when we've decided this is a list).
				rows.add(parseFieldMap(row));
			}
			return ParsedResult.ofRows(rows);
		}

		// get -> single struct: PascalCase fields are direct children.
		return ParsedResult.ofStruct(parseFieldMap(obj));
	}

	/** True iff every element child of {@code obj} is a {@code DataObject}. */
	private static boolean hasDataObjectChildren(Element obj) {
		NodeList children = obj.getChildNodes();
		boolean sawElement = false;
		for (int i = 0; i < children.getLength(); i++) {
			Node n = children.item(i);
			if (n.getNodeType() != Node.ELEMENT_NODE) continue;
			sawElement = true;
			if (!"DataObject".equals(localName((Element) n))) {
				return false;
			}
		}
		return sawElement;
	}

	/** Parse direct element children of {@code parent} into a field map. */
	private static Map<String, String> parseFieldMap(Element parent) {
		Map<String, String> fields = new HashMap<>();
		NodeList children = parent.getChildNodes();
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
		try {
			ByteArrayOutputStream bos = new ByteArrayOutputStream();
			byte[] buf = new byte[8192];
			int n;
			while ((n = is.read(buf)) >= 0) {
				bos.write(buf, 0, n);
			}
			return bos.toByteArray();
		} finally {
			// Close even if the read throws mid-stream, so the underlying
			// connection's input is released rather than left dangling.
			try {
				is.close();
			} catch (Exception ignored) {}
		}
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
