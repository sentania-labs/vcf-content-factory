package com.vcfcf.adapter.http;

import com.vcfcf.adapter.auth.AuthStrategy;
import com.vcfcf.adapter.retry.RetryPolicy;

import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.security.KeyManagementException;
import java.security.NoSuchAlgorithmException;
import java.security.cert.X509Certificate;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * Fluent builder for a pre-configured {@link HttpClient} with auth, retry,
 * default headers, and optional SSL trust configuration.
 *
 * <p>Usage:
 * <pre>{@code
 * ManagedHttpClient client = HttpClientBuilder.builder()
 *     .baseUrl("https://my-nas.local:5001")
 *     .allowInsecure(true)               // self-signed cert in lab
 *     .auth(new BasicAuth("admin", "secret"))
 *     .defaultHeader("Accept", "application/json")
 *     .retryPolicy(RetryPolicy.DEFAULT)
 *     .timeout(Duration.ofSeconds(30))
 *     .build();
 *
 * HttpResponse<String> resp = client.get("/api/data", HttpResponse.BodyHandlers.ofString());
 * }</pre>
 *
 * <p>The underlying {@link HttpClient} is a stdlib-only client (java.net.http).
 * No Apache HttpClient or other third-party HTTP library is used.
 */
public final class HttpClientBuilder {

	private String baseUrl = "";
	private boolean allowInsecure = false;
	private AuthStrategy auth = null;
	private RetryPolicy retryPolicy = RetryPolicy.DEFAULT;
	private Duration timeout = Duration.ofSeconds(30);
	private final List<String[]> defaultHeaders = new ArrayList<>();

	private HttpClientBuilder() {}

	/** Create a new builder. */
	public static HttpClientBuilder builder() {
		return new HttpClientBuilder();
	}

	/**
	 * Base URL prepended to every relative path passed to {@code get()} /
	 * {@code post()} etc. (e.g. {@code "https://my-nas.local:5001"}).
	 */
	public HttpClientBuilder baseUrl(String url) {
		this.baseUrl = url;
		return this;
	}

	/**
	 * When {@code true}, disable SSL certificate verification.
	 * Use ONLY in lab/dev environments with self-signed certs.
	 */
	public HttpClientBuilder allowInsecure(boolean insecure) {
		this.allowInsecure = insecure;
		return this;
	}

	/** Auth strategy applied to every request (e.g. {@link com.vcfcf.adapter.auth.BasicAuth}). */
	public HttpClientBuilder auth(AuthStrategy strategy) {
		this.auth = strategy;
		return this;
	}

	/** Retry policy for transient failures. Default: {@link RetryPolicy#DEFAULT}. */
	public HttpClientBuilder retryPolicy(RetryPolicy policy) {
		this.retryPolicy = policy;
		return this;
	}

	/** Per-request connect+read timeout. Default: 30 seconds. */
	public HttpClientBuilder timeout(Duration d) {
		this.timeout = d;
		return this;
	}

	/** Add a default header sent with every request. */
	public HttpClientBuilder defaultHeader(String name, String value) {
		this.defaultHeaders.add(new String[]{name, value});
		return this;
	}

	/** Build the {@link ManagedHttpClient}. */
	public ManagedHttpClient build() {
		HttpClient.Builder clientBuilder = HttpClient.newBuilder()
				.connectTimeout(timeout)
				.followRedirects(HttpClient.Redirect.NORMAL);

		if (allowInsecure) {
			clientBuilder.sslContext(insecureSslContext());
		}

		HttpClient httpClient = clientBuilder.build();
		return new ManagedHttpClient(httpClient, baseUrl, auth, retryPolicy, timeout,
				List.copyOf(defaultHeaders));
	}

	private static SSLContext insecureSslContext() {
		try {
			SSLContext ctx = SSLContext.getInstance("TLS");
			ctx.init(null, new TrustManager[]{new X509TrustManager() {
				public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
				public void checkClientTrusted(X509Certificate[] c, String a) {}
				public void checkServerTrusted(X509Certificate[] c, String a) {}
			}}, null);
			return ctx;
		} catch (NoSuchAlgorithmException | KeyManagementException e) {
			throw new RuntimeException("Failed to create insecure SSL context", e);
		}
	}
}
