package com.vcfcf.adapter.http;

import com.vcfcf.adapter.auth.AuthStrategy;
import com.vcfcf.adapter.retry.RetryPolicy;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;

/**
 * Wrapper around {@link HttpClient} that applies auth, retry, base URL,
 * and default headers to every outgoing request.
 *
 * <p>Instances are created by {@link HttpClientBuilder#build()} — do not
 * construct directly.
 */
public final class ManagedHttpClient {

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
		return retryPolicy.execute(() -> httpClient.send(req, bodyHandler));
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
		return retryPolicy.execute(() -> httpClient.send(req, bodyHandler));
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
		return retryPolicy.execute(() -> httpClient.send(req, bodyHandler));
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
}
