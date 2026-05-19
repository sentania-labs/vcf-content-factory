package com.vcfcf.adapters.synology;

public final class SynologyConfig {

	public final String host;
	public final int port;
	public final String username;
	public final String password;
	public final boolean allowInsecure;

	public SynologyConfig(String host, String port, String username,
			String password, String allowInsecure) {
		this.host = (host != null && !host.isEmpty()) ? host : "localhost";
		int p = 5001;
		if (port != null && !port.isEmpty()) {
			try { p = Integer.parseInt(port); } catch (NumberFormatException ignored) {}
		}
		this.port = p;
		this.username = (username != null) ? username : "";
		this.password = (password != null) ? password : "";
		this.allowInsecure = !"false".equalsIgnoreCase(allowInsecure);
	}

	public String baseUrl() {
		return "https://" + host + ":" + port;
	}
}
