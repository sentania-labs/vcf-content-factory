package com.vcfcf.adapter.auth;

import java.net.http.HttpRequest;

/**
 * Pluggable authentication strategy for the VCF-CF HTTP client.
 *
 * <p>Implementations mutate an outgoing {@link HttpRequest.Builder} by
 * adding headers, cookies, or other auth material. The framework calls
 * {@link #apply(HttpRequest.Builder)} before every HTTP request.
 *
 * <p>Stateful strategies (e.g. session cookies, OAuth2 tokens) may refresh
 * or re-acquire credentials on the first call and cache them internally.
 * Thread-safety within a single adapter instance is guaranteed by the
 * platform's per-instance Semaphore (at-most-one collect() at a time).
 */
public interface AuthStrategy {

	/**
	 * Apply authentication material to the given request builder.
	 *
	 * @param builder the request builder for the outgoing HTTP request
	 */
	void apply(HttpRequest.Builder builder);

	/**
	 * Called when the adapter is discarded so the strategy can release
	 * any held resources (e.g. HTTP connections used for token refresh).
	 * Default implementation is a no-op.
	 */
	default void discard() {}
}
