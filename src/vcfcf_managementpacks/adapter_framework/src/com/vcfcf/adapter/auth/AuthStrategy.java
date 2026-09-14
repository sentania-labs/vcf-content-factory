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
 *
 * <h3>Single-retry-on-auth-failure contract</h3>
 * <p>Session-based strategies that hold a reusable credential (session
 * cookie, query-param session ID, OAuth2 token) should override
 * {@link #shouldRetryAfterStatus(int)} to return {@code true} for the
 * HTTP status codes that indicate credential expiry (typically 401, and
 * optionally 403 when the target API uses 403 for expired sessions).
 *
 * <p>When {@link #shouldRetryAfterStatus(int)} returns {@code true},
 * {@link com.vcfcf.adapter.http.ManagedHttpClient} will call
 * {@link #invalidateAuth()} and then replay the request exactly once
 * with a fresh credential (acquired lazily by the next {@link #apply}
 * call).  A second auth failure on the retry propagates immediately
 * — there is no retry loop.
 *
 * <p>Stateless strategies (e.g. {@code BasicAuth}, {@code BearerAuth})
 * inherit the default no-op implementations and are unaffected: no retry
 * is injected, matching the previous framework behaviour.
 */
public interface AuthStrategy {

	/**
	 * Apply authentication material to the given request builder.
	 *
	 * @param builder the request builder for the outgoing HTTP request
	 */
	void apply(HttpRequest.Builder builder);

	/**
	 * Return {@code true} if an HTTP response with the given status code
	 * should trigger a credential-invalidation + single-retry.
	 *
	 * <p>Override in session-based strategies that can detect credential
	 * expiry from the HTTP status code alone (e.g. 401 for
	 * {@code SessionCookieAuth}).  The default returns {@code false} —
	 * stateless strategies such as {@code BasicAuth} and {@code BearerAuth}
	 * never retry.
	 *
	 * @param statusCode the HTTP response status code
	 * @return {@code true} if the strategy wants to invalidate its
	 *         credential and replay the request once
	 */
	default boolean shouldRetryAfterStatus(int statusCode) {
		return false;
	}

	/**
	 * Invalidate the currently-cached credential so that the next call to
	 * {@link #apply(HttpRequest.Builder)} re-acquires a fresh one.
	 *
	 * <p>Called by {@link com.vcfcf.adapter.http.ManagedHttpClient}
	 * immediately before replaying the request after
	 * {@link #shouldRetryAfterStatus(int)} returned {@code true}.
	 *
	 * <p>Default is a no-op (stateless strategies have nothing to invalidate).
	 */
	default void invalidateAuth() {}

	/**
	 * Called when the adapter is discarded so the strategy can release
	 * any held resources (e.g. HTTP connections used for token refresh).
	 * Default implementation is a no-op.
	 */
	default void discard() {}
}
