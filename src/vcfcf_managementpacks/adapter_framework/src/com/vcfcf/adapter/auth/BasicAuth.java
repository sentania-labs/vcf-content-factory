package com.vcfcf.adapter.auth;

import java.net.http.HttpRequest;
import java.util.Base64;

/**
 * HTTP Basic authentication strategy.
 *
 * <p>Adds an {@code Authorization: Basic <base64(user:pass)>} header to
 * every request. This is the simplest auth strategy and serves as the
 * baseline for adapters that target REST APIs requiring Basic auth.
 */
public final class BasicAuth implements AuthStrategy {

	private final String headerValue;

	/**
	 * @param username the username
	 * @param password the password
	 */
	public BasicAuth(String username, String password) {
		String raw = username + ":" + password;
		this.headerValue = "Basic " + Base64.getEncoder().encodeToString(raw.getBytes());
	}

	@Override
	public void apply(HttpRequest.Builder builder) {
		builder.header("Authorization", headerValue);
	}
}
