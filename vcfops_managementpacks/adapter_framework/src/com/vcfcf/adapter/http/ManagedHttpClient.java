package com.vcfcf.adapter.http;

import com.vcfcf.adapter.auth.AuthStrategy;
import com.vcfcf.adapter.retry.RetryPolicy;

import java.io.IOException;
import java.net.ConnectException;
import java.net.InetAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.logging.Logger;

/**
 * Wrapper around {@link HttpClient} that applies auth, retry, base URL,
 * and default headers to every outgoing request.
 *
 * <p>Instances are created by {@link HttpClientBuilder#build()} — do not
 * construct directly.
 *
 * <h3>DNS round-robin handling</h3>
 * <p>{@code java.net.http.HttpClient} resolves the hostname once and reuses
 * the cached IP for the lifetime of the client.  When a hostname maps to
 * multiple IPs (e.g. a NAS with several NICs), a single bad IP causes every
 * request to fail even though healthy IPs exist.
 *
 * <p>When the initial {@link RetryPolicy} execution throws a
 * {@link ConnectException}, {@link #sendWithRoundRobin} resolves the hostname
 * to all its IPs via {@link InetAddress#getAllByName} and retries the request
 * against each IP in turn, substituting the IP into the URL and setting a
 * {@code Host} header so TLS SNI and virtual-host routing still work.  The
 * first IP that does not throw {@code ConnectException} wins; if all IPs fail
 * the original exception is re-thrown.
 */
public final class ManagedHttpClient {

	private static final Logger LOG = Logger.getLogger(ManagedHttpClient.class.getName());

	private final HttpClient httpClient;
	private final String baseUrl;
	private final AuthStrategy auth;
	private final RetryPolicy retryPolicy;
	private final Duration timeout;
	private final List<String[]> defaultHeaders;

	ManagedHttpClient(HttpClient httpClient, String baseUrl, AuthStrategy auth,
			RetryPolicy retryPolicy, Duration timeout, List<String[]> defaultHeaders) {
		this.httpClient = httpClient;
		this.baseUrl = baseUrl;
		this.auth = auth;
		this.retryPolicy = retryPolicy;
		this.timeout = timeout;
		this.defaultHeaders = defaultHeaders;
	}

	/**
	 * Perform a GET request.
	 *
	 * @param path          path relative to the base URL (e.g. {@code "/api/v1/hosts"})
	 * @param bodyHandler   response body handler (e.g. {@code BodyHandlers.ofString()})
	 * @return the HTTP response
	 */
	public <T> HttpResponse<T> get(String path, HttpResponse.BodyHandler<T> bodyHandler)
			throws IOException, InterruptedException {
		HttpRequest.Builder rb = HttpRequest.newBuilder()
				.uri(URI.create(baseUrl + path))
				.GET()
				.timeout(timeout);
		applyDefaults(rb);
		HttpRequest req = rb.build();
		try {
			return retryPolicy.execute(() -> httpClient.send(req, bodyHandler));
		} catch (ConnectException ce) {
			return sendWithRoundRobin(req, bodyHandler, ce);
		}
	}

	/**
	 * Perform a POST request with the given body.
	 *
	 * @param path          path relative to the base URL
	 * @param body          request body as a string (UTF-8)
	 * @param contentType   MIME type of the request body (e.g. {@code "application/json"})
	 * @param bodyHandler   response body handler
	 */
	public <T> HttpResponse<T> post(String path, String body, String contentType,
			HttpResponse.BodyHandler<T> bodyHandler)
			throws IOException, InterruptedException {
		HttpRequest.Builder rb = HttpRequest.newBuilder()
				.uri(URI.create(baseUrl + path))
				.POST(HttpRequest.BodyPublishers.ofString(body))
				.header("Content-Type", contentType)
				.timeout(timeout);
		applyDefaults(rb);
		HttpRequest req = rb.build();
		try {
			return retryPolicy.execute(() -> httpClient.send(req, bodyHandler));
		} catch (ConnectException ce) {
			return sendWithRoundRobin(req, bodyHandler, ce);
		}
	}

	/**
	 * Perform a GET request at an absolute URL (ignoring base URL).
	 *
	 * @param absoluteUrl   the full URL to GET
	 * @param bodyHandler   response body handler
	 */
	public <T> HttpResponse<T> getAbsolute(String absoluteUrl, HttpResponse.BodyHandler<T> bodyHandler)
			throws IOException, InterruptedException {
		HttpRequest.Builder rb = HttpRequest.newBuilder()
				.uri(URI.create(absoluteUrl))
				.GET()
				.timeout(timeout);
		applyDefaults(rb);
		HttpRequest req = rb.build();
		try {
			return retryPolicy.execute(() -> httpClient.send(req, bodyHandler));
		} catch (ConnectException ce) {
			return sendWithRoundRobin(req, bodyHandler, ce);
		}
	}

	/** Release any resources (called from adapter's onDiscard). */
	public void discard() {
		if (auth != null) {
			auth.discard();
		}
	}

	private void applyDefaults(HttpRequest.Builder rb) {
		for (String[] h : defaultHeaders) {
			rb.header(h[0], h[1]);
		}
		if (auth != null) {
			auth.apply(rb);
		}
	}

	/**
	 * DNS round-robin fallback: resolve the hostname in {@code originalReq} to
	 * all its IPs and try each in turn.
	 *
	 * <p>The original {@link HttpRequest} is used as a template; its URI is
	 * rewritten to use the raw IP while a {@code Host} header preserving the
	 * original hostname is injected so that TLS SNI and virtual-host routing
	 * continue to work.  Auth and default headers are already baked into the
	 * original request so they are carried over automatically via
	 * {@link HttpRequest#headers()}.
	 *
	 * @param originalReq the request that triggered the ConnectException
	 * @param bodyHandler response body handler
	 * @param originalEx  the ConnectException from the initial attempt
	 * @return the first successful response
	 * @throws ConnectException if every resolved IP also fails with a ConnectException
	 * @throws IOException      for any other network error on the last attempted IP
	 */
	private <T> HttpResponse<T> sendWithRoundRobin(HttpRequest originalReq,
			HttpResponse.BodyHandler<T> bodyHandler,
			ConnectException originalEx)
			throws IOException, InterruptedException {

		URI originalUri = originalReq.uri();
		String hostname = originalUri.getHost();
		int port = originalUri.getPort();   // -1 if absent (scheme default)
		String scheme = originalUri.getScheme();

		InetAddress[] addresses;
		try {
			addresses = InetAddress.getAllByName(hostname);
		} catch (Exception dnsEx) {
			// DNS itself failed; nothing to fall back to.
			throw originalEx;
		}

		if (addresses.length <= 1) {
			// Only one IP — round-robin fallback cannot help.
			throw originalEx;
		}

		LOG.warning(() -> "ConnectException for " + hostname
				+ " — attempting DNS round-robin across " + addresses.length + " IPs");

		ConnectException lastCe = originalEx;

		for (InetAddress addr : addresses) {
			String ip = addr.getHostAddress();

			// Build a URI with the IP substituted for the hostname.
			URI ipUri;
			try {
				ipUri = new URI(scheme, null, ip, port,
						originalUri.getPath(),
						originalUri.getQuery(),
						originalUri.getFragment());
			} catch (java.net.URISyntaxException e) {
				// Shouldn't happen with values derived from a valid URI; skip.
				continue;
			}

			// Copy the original request, rewrite the URI, and force the Host header.
			HttpRequest.Builder rb = HttpRequest.newBuilder(originalReq, (n, v) -> true)
					.uri(ipUri)
					.header("Host", port > 0 ? hostname + ":" + port : hostname);

			HttpRequest ipReq = rb.build();

			try {
				HttpResponse<T> resp = httpClient.send(ipReq, bodyHandler);
				LOG.info(() -> "DNS round-robin: connected via IP " + ip
						+ " for host " + hostname);
				return resp;
			} catch (ConnectException ce) {
				lastCe = ce;
				final String logIp = ip;
				LOG.warning(() -> "DNS round-robin: IP " + logIp + " also unreachable: "
						+ ce.getMessage());
			}
			// Any non-ConnectException IOException propagates immediately —
			// it means we reached the host but something else went wrong.
		}

		throw lastCe;
	}
}
