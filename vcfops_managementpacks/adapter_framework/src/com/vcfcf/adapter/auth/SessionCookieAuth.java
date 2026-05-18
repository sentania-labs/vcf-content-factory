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
 * <p>The canonical use case is Synology DSM, which requires authenticating
 * via {@code SYNO.API.Auth} to obtain a {@code sid} session token before
 * any data collection calls can proceed.
 *
 * <p>The token is cached in an {@link AtomicReference} and reused for the
 * lifetime of the adapter instance. Call {@link #invalidate()} from
 * {@code onConfigure()} when credentials change.
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

	/** Discard the cached token so the next call re-authenticates. */
	public void invalidate() {
		cachedToken.set(null);
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
