package com.vcfcf.adapters.unifi;

public final class UniFiConfig {
	public final String host;
	public final String port;
	public final String username;
	public final String password;
	public final boolean allowInsecure;

	public UniFiConfig(String host, String port, String username,
			String password, String allowInsecure) {
		this.host = host;
		this.port = (port == null || port.isEmpty()) ? "443" : port;
		this.username = username;
		this.password = password;
		this.allowInsecure = "true".equalsIgnoreCase(allowInsecure);
	}

	public String baseUrl() {
		return "https://" + host + ":" + port;
	}
}
