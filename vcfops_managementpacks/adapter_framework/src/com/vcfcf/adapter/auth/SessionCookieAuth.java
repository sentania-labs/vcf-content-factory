package com.vcfcf.adapter.auth;

import java.net.http.HttpRequest;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Session-cookie authentication strategy.
 *
 * <p>Adds a {@code Cookie: <cookieName>=<token>} header to every request.
 * The session token is acquired lazily on the first call to {@link #apply}
 * by invoking the {@link SessionProvider} supplied at construction time.
 *
 * <p>The canonical use case is UniFi OS, which issues a {@code TOKEN}
 * session cookie after a credential POST and expires it after an
 * implementation-defined interval.
 *
 * <p>The token is cached in an {@link AtomicReference} and reused for the
 * lifetime of the adapter instance. Call {@link #invalidate()} from
 * {@code onConfigure()} when credentials change.
 *
 * <h3>Automatic single-retry on 401</h3>
 * <p>This strategy overrides {@link AuthStrategy#shouldRetryAfterStatus}
 * to return {@code true} for HTTP 401 (and 403, which some UniFi OS
 * builds return for an expired session). On such a response
 * {@link com.vcfcf.adapter.http.ManagedHttpClient} calls
 * {@link #invalidateAuth()}, then replays the request once; the next
 * {@link #apply} call re-acquires a fresh token via the
 * {@link SessionProvider}. A second auth failure on the retry propagates
 * loudly — there is no retry loop. See
 * {@code context/framework_v2_migration.md §21.3}.
 */
public final class SessionCookieAuth implements AuthStrategy {

	/** Produces a fresh session token (e.g. by POSTing to the login endpoint). */
	@FunctionalInterface
	public interface SessionProvider {
		/** @return a fresh session token string */
		String acquireToken() throws Exception;
	}

	private final String cookieName;
	private final SessionProvider provider;
	private final AtomicReference<String> cachedToken = new AtomicReference<>();

	/**
	 * @param cookieName the cookie name to use in the {@code Cookie:} header
	 *                   (e.g. {@code "id"} for Synology DSM)
	 * @param provider   strategy that fetches a fresh session token when needed
	 */
	public SessionCookieAuth(String cookieName, SessionProvider provider) {
		this.cookieName = cookieName;
		this.provider = provider;
	}

	@Override
	public void apply(HttpRequest.Builder builder) {
		String token = cachedToken.get();
		if (token == null) {
			token = acquireFresh();
		}
		builder.header("Cookie", cookieName + "=" + token);
	}

	/**
	 * Discard the cached token so the next call to {@link #apply} re-authenticates.
	 *
	 * <p>Call from {@code onConfigure()} when credentials change. The framework
	 * also calls this automatically (via {@link #invalidateAuth()}) when a
	 * 401/403 response is received, before replaying the request once.
	 */
	public void invalidate() {
		cachedToken.set(null);
	}

	/**
	 * {@inheritDoc}
	 *
	 * <p>Returns {@code true} for HTTP 401 and 403 — both indicate an
	 * expired or rejected session cookie. The framework will call
	 * {@link #invalidateAuth()} and replay the request exactly once.
	 */
	@Override
	public boolean shouldRetryAfterStatus(int statusCode) {
		return statusCode == 401 || statusCode == 403;
	}

	/**
	 * {@inheritDoc}
	 *
	 * <p>Delegates to {@link #invalidate()} — nulls the cached token so
	 * the next {@link #apply} call re-acquires a fresh one via the
	 * {@link SessionProvider}.
	 */
	@Override
	public void invalidateAuth() {
		invalidate();
	}

	@Override
	public void discard() {
		invalidate();
	}

	private String acquireFresh() {
		try {
			String token = provider.acquireToken();
			cachedToken.set(token);
			return token;
		} catch (Exception e) {
			throw new RuntimeException("SessionCookieAuth: failed to acquire session token", e);
		}
	}
}
