package com.vcfcf.adapters.compliance;

import com.vcfcf.adapter.json.SimpleJson;

import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.security.cert.X509Certificate;
import java.time.Duration;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;

/**
 * VAMI (vCenter Server Appliance Management) REST reader — build 41.
 *
 * <p>A transport distinct from the vim25 SOAP surface: it talks to the
 * vCenter Appliance Management REST API at {@code /api/appliance/...}. The
 * REST API needs its OWN session — it does NOT ride the SOAP session
 * cookie. We open one with {@code POST /api/session} using HTTP Basic auth
 * (the same raw username/password the adapter already holds to build the
 * SOAP session), and pass the returned token as the
 * {@code vmware-api-session-id} header on every GET. This mirrors
 * {@link VCenterApiClient}, but is kept separate so the VAMI surface (one
 * per vCenter, against the {@code VCenterAdapterInstance} resource) has its
 * own failed-session caching and its own appliance-path response cache.
 *
 * <p><b>BLIND BUILD — schema confidence MEDIUM.</b> The JSON field names
 * extracted here are derived from API documentation, not captured on the
 * wire. They are safe-by-construction: a wrong field name, a non-200, a
 * 404, an auth failure, a timeout, or a JSON parse error ALL fold to the
 * {@link #FAILED} sentinel (→ UNREADABLE upstream), NEVER to a value and
 * NEVER to a "compliant" pass. This is the cardinal trap restated for the
 * REST transport — most dangerous for the "should be disabled" controls
 * (a failed GET of {@code access/ssh} must not become "ssh disabled →
 * compliant"). Only a successful 200 with the field present yields a value.
 *
 * <p><b>Failed-session caching</b> (mirrors {@link EsxcliSoapClient}'s
 * failed-result caching). If the REST session cannot be opened, the failure
 * is cached for the lifetime of this client (one collection cycle) so it is
 * not retried per-control. Likewise each appliance-path GET is cached per
 * cycle — including a FAILED result — so N controls that read different
 * fields of the same endpoint cost exactly one GET.
 */
final class VamiApiClient {

	/**
	 * Sentinel returned by {@link #readField} when the GET failed (no
	 * session, non-200, 404, timeout, parse error) OR the requested field
	 * was absent in a successful response. Both fold to UNREADABLE upstream
	 * — never a value, never a pass.
	 */
	static final Object FAILED = new Object() {
		@Override public String toString() { return "(vami-failed)"; }
	};

	/** Field token meaning "the response body itself is the list/value". */
	static final String SELF_LIST = "(list)";

	private final HttpClient httpClient;
	private final String baseUrl;
	private final String username;
	private final String password;

	private volatile String sessionId;
	// Once a session attempt has failed this cycle, don't retry per-control.
	private volatile boolean sessionFailed;
	private volatile boolean sessionTried;

	// Per-cycle cache: appliance-path -> parsed body, or FAILED_JSON marker.
	// A FAILED GET is cached so a second control on the same endpoint does
	// not re-issue the request (mirrors EsxcliSoapClient.resultCache).
	private final Map<String, Object> pathCache = new HashMap<>();

	/** Cache marker for a failed GET (distinct from a successfully-parsed body). */
	private static final Object FAILED_BODY = new Object();

	VamiApiClient(String baseUrl, String username, String password,
			boolean allowInsecure) {
		this.baseUrl = baseUrl;
		this.username = username != null ? username : "";
		this.password = password != null ? password : "";

		HttpClient.Builder builder = HttpClient.newBuilder()
				.connectTimeout(Duration.ofSeconds(30));
		if (allowInsecure) {
			try {
				SSLContext ctx = SSLContext.getInstance("TLS");
				ctx.init(null, new TrustManager[]{new TrustAllManager()}, null);
				builder.sslContext(ctx);
			} catch (Exception e) {
				// Can't configure insecure SSL — leave default factory; a
				// cert failure on connect folds to a failed session, never
				// a pass.
			}
		}
		this.httpClient = builder.build();
	}

	/**
	 * Open the REST session if not already open. Returns the session id, or
	 * {@code null} if the session could not be opened (cached for the cycle
	 * so it isn't retried). Never throws.
	 */
	private synchronized String ensureSession() {
		if (sessionId != null) return sessionId;
		if (sessionFailed) return null;
		if (sessionTried && sessionId == null) return null;
		sessionTried = true;
		try {
			String credentials = Base64.getEncoder().encodeToString(
					(username + ":" + password).getBytes());
			HttpRequest req = HttpRequest.newBuilder()
					.uri(URI.create(baseUrl + "/api/session"))
					.POST(HttpRequest.BodyPublishers.ofString(""))
					.header("Authorization", "Basic " + credentials)
					.header("Content-Type", "application/json")
					.timeout(Duration.ofSeconds(30))
					.build();
			HttpResponse<String> resp = httpClient.send(req,
					HttpResponse.BodyHandlers.ofString());
			if (resp.statusCode() != 200 && resp.statusCode() != 201) {
				sessionFailed = true;
				return null;
			}
			String body = resp.body();
			if (body != null) {
				body = body.trim();
				if (body.startsWith("\"") && body.endsWith("\"")
						&& body.length() >= 2) {
					body = body.substring(1, body.length() - 1);
				}
			}
			if (body == null || body.isEmpty()) {
				sessionFailed = true;
				return null;
			}
			sessionId = body;
			return sessionId;
		} catch (Exception e) {
			// Auth failure / timeout / I/O — cache as failed so we don't
			// retry per-control. UNREADABLE upstream, never a pass.
			sessionFailed = true;
			return null;
		}
	}

	/**
	 * GET an appliance endpoint and cache the parsed body for the cycle.
	 * Returns the parsed {@link SimpleJson} on a 200, or {@code null} on
	 * any failure (no session, non-200, 404, timeout, parse error). The
	 * FAILED result is cached so a second control on the same endpoint
	 * does not re-issue the GET.
	 *
	 * @param appliancePath path after {@code /api/appliance/}, e.g.
	 *                      {@code access/ssh}
	 */
	private synchronized SimpleJson getEndpoint(String appliancePath) {
		Object cached = pathCache.get(appliancePath);
		if (cached == FAILED_BODY) return null;
		if (cached instanceof SimpleJson) return (SimpleJson) cached;

		String session = ensureSession();
		if (session == null) {
			pathCache.put(appliancePath, FAILED_BODY);
			return null;
		}
		try {
			String full = baseUrl + "/api/appliance/" + appliancePath;
			HttpRequest req = HttpRequest.newBuilder()
					.uri(URI.create(full))
					.GET()
					.header("vmware-api-session-id", session)
					.header("Accept", "application/json")
					.timeout(Duration.ofSeconds(30))
					.build();
			HttpResponse<String> resp = httpClient.send(req,
					HttpResponse.BodyHandlers.ofString());
			// Only a successful 200 yields a value. 401/403/404/5xx/anything
			// else -> failed -> UNREADABLE upstream, never "disabled/compliant".
			if (resp.statusCode() != 200) {
				pathCache.put(appliancePath, FAILED_BODY);
				return null;
			}
			SimpleJson parsed = SimpleJson.parse(resp.body());
			if (parsed == null || parsed.isNull()) {
				pathCache.put(appliancePath, FAILED_BODY);
				return null;
			}
			pathCache.put(appliancePath, parsed);
			return parsed;
		} catch (Exception e) {
			pathCache.put(appliancePath, FAILED_BODY);
			return null;
		}
	}

	/**
	 * Read one field from one appliance endpoint.
	 *
	 * <p>Typing:
	 * <ul>
	 *   <li>{@code field == "(list)"} — the response body itself is treated
	 *       as a list; returns the comma-joined element string (non-empty
	 *       check upstream via {@code (non-empty)} mode). An empty list
	 *       returns {@code null} → UNREADABLE (so "no syslog targets" is a
	 *       coverage gap, never a false pass under the non-empty mode).</li>
	 *   <li>a dotted field path — navigated via {@link SimpleJson#path}. A
	 *       JSON boolean is returned as {@link Boolean}; a list as the
	 *       comma-joined element string; a scalar (string/number) as its
	 *       {@code String} form.</li>
	 * </ul>
	 *
	 * <p>Returns {@link #FAILED} when the GET failed, when the body could
	 * not be parsed, or when the navigated node is absent/null. Both
	 * {@link #FAILED} and the empty-list {@code null} fold to UNREADABLE
	 * upstream — NEVER a value, NEVER a pass. This is the cardinal trap for
	 * the REST transport.
	 *
	 * @param appliancePath path after {@code /api/appliance/}
	 * @param field         JSON field (dotted for nesting), or
	 *                      {@link #SELF_LIST} when the body is itself the list
	 */
	Object readField(String appliancePath, String field) {
		SimpleJson body = getEndpoint(appliancePath);
		if (body == null) {
			return FAILED;
		}

		if (SELF_LIST.equals(field)) {
			return listOrNull(body);
		}

		SimpleJson node = body.path(field);
		if (node == null || node.isNull()) {
			// Field absent in a successful response — UNREADABLE, never a
			// guessed default. (Documentation-derived field name may be
			// wrong; that is a coverage gap, not a pass.)
			return FAILED;
		}
		if (node.isList()) {
			return listOrNull(node);
		}
		// A JSON boolean must surface as Boolean so the evaluator's boolean
		// compare path handles it (e.g. access/ssh enabled, global-fips
		// enabled). SimpleJson does not expose the raw type, so probe: a
		// node whose string form is exactly "true"/"false" is a boolean.
		String s = node.asString();
		if (s == null) {
			return FAILED;
		}
		if ("true".equalsIgnoreCase(s)) return Boolean.TRUE;
		if ("false".equalsIgnoreCase(s)) return Boolean.FALSE;
		return s;
	}

	/**
	 * Join a JSON list node's elements on {@code ,}. Returns {@code null}
	 * for an empty list (→ UNREADABLE upstream, so an empty list never
	 * passes a {@code (non-empty)} control) or a non-list node.
	 */
	private static Object listOrNull(SimpleJson node) {
		if (node == null || !node.isList()) return null;
		java.util.List<SimpleJson> items = node.asList();
		if (items.isEmpty()) return null;
		StringBuilder sb = new StringBuilder();
		for (int i = 0; i < items.size(); i++) {
			if (i > 0) sb.append(',');
			String s = items.get(i).asString();
			sb.append(s != null ? s : "");
		}
		return sb.toString();
	}

	private static final class TrustAllManager implements X509TrustManager {
		@Override public void checkClientTrusted(X509Certificate[] chain, String authType) {}
		@Override public void checkServerTrusted(X509Certificate[] chain, String authType) {}
		@Override public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
	}
}
