package com.vcfcf.adapter.auth;

import java.net.http.HttpRequest;

/**
 * Bearer-token (OAuth2-style) authentication strategy.
 *
 * <p>Adds an {@code Authorization: Bearer <token>} header to every request.
 * The token is provided at construction time and is static for the lifetime
 * of this strategy instance. For tokens that expire and need refresh, extend
 * this class or implement a custom {@link AuthStrategy}.
 */
public final class BearerAuth implements AuthStrategy {

	private final String headerValue;

	/**
	 * @param token the bearer token (the raw token string, without the "Bearer " prefix)
	 */
	public BearerAuth(String token) {
		this.headerValue = "Bearer " + token;
	}

	@Override
	public void apply(HttpRequest.Builder builder) {
		builder.header("Authorization", headerValue);
	}
}
