package com.vcfcf.adapter.http;

import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.auth.AuthStrategy;
import com.vcfcf.adapter.retry.RetryPolicy;

import javax.net.ssl.SSLContext;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * Fluent builder for a pre-configured {@link ManagedHttpClient} with auth,
 * retry, default headers, and SSL trust configuration.
 *
 * <h3>SSL (cert item)</h3>
 * <p>By default, no custom SSL context is set — the JVM's default trust store
 * is used. To use the platform's trust store (recommended for production,
 * ensures user-trusted certs from VCF Ops certificate management are honoured),
 * call {@link #platformSsl(VcfCfAdapter)}. To skip certificate verification
 * in lab environments with self-signed certs, call {@link #allowInsecure(boolean)}
 * — this is an explicit, documented opt-out, not the default.
 *
 * <p>Usage:
 * <pre>{@code
 * // Production — platform trust store:
 * ManagedHttpClient client = HttpClientBuilder.builder()
 *     .baseUrl("https://my-nas.local:5001")
 *     .platformSsl(this)                    // 'this' = the VcfCfAdapter instance
 *     .auth(new BasicAuth("admin", "secret"))
 *     .build();
 *
 * // Lab — self-signed cert opt-out:
 * ManagedHttpClient client = HttpClientBuilder.builder()
 *     .baseUrl("https://my-nas.local:5001")
 *     .allowInsecure(true)                  // explicit opt-out
 *     .build();
 * }</pre>
 *
 * <p>The underlying HTTP transport is {@code java.net.http.HttpClient} (stdlib
 * only). No Apache HttpClient or other third-party HTTP library is required.
 */
public final class HttpClientBuilder {

    private String baseUrl = "";
    private SSLContext sslContext = null;        // null → JVM default
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
     * Base URL prepended to every relative path in {@code get()} / {@code post()}.
     * Example: {@code "https://my-nas.local:5001"}.
     */
    public HttpClientBuilder baseUrl(String url) {
        this.baseUrl = url;
        return this;
    }

    /**
     * Use the platform's trust store for SSL certificate verification.
     *
     * <p>Preferred for production adapters. Calls
     * {@link VcfCfAdapter#getPlatformSslContext()} to obtain an
     * {@link SSLContext} backed by the VCF Ops certificate management
     * framework, ensuring user-added trusted certs are honoured.
     *
     * @param adapter the {@link VcfCfAdapter} instance ({@code this} in your
     *                {@code configureAdapter()} implementation)
     */
    public HttpClientBuilder platformSsl(VcfCfAdapter<?> adapter) {
        this.sslContext = adapter.getPlatformSslContext();
        return this;
    }

    /**
     * Disable SSL certificate verification.
     *
     * <p><strong>Explicit opt-out — use ONLY in lab/dev environments with
     * self-signed certificates.</strong> Do not use in production adapters.
     * If both {@link #platformSsl} and {@link #allowInsecure(boolean)} are
     * called, the last call wins.
     *
     * @param insecure {@code true} to trust all certificates without verification
     */
    public HttpClientBuilder allowInsecure(boolean insecure) {
        if (insecure) {
            this.sslContext = VcfCfAdapter.insecureSslContext();
        }
        return this;
    }

    /**
     * Supply a pre-built {@link SSLContext} directly.
     *
     * <p>Advanced use only. Prefer {@link #platformSsl(VcfCfAdapter)} for
     * production adapters.
     */
    public HttpClientBuilder sslContext(SSLContext ctx) {
        this.sslContext = ctx;
        return this;
    }

    /** Auth strategy applied to every request. */
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

        if (sslContext != null) {
            clientBuilder.sslContext(sslContext);
        }
        // If sslContext is null, java.net.http.HttpClient uses the JVM default
        // trust store — acceptable for adapters talking to publicly-trusted endpoints.

        HttpClient httpClient = clientBuilder.build();
        return new ManagedHttpClient(httpClient, baseUrl, auth, retryPolicy,
                timeout, List.copyOf(defaultHeaders));
    }
}
