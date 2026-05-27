package com.vcfcf.adapters.compliance;

public final class ComplianceConfig {

	public final String vcenterHost;
	public final String username;
	public final String password;
	public final String benchmarkProfile;
	public final String customProfilePath;
	public final boolean allowInsecure;

	public ComplianceConfig(String vcenterHost, String username, String password,
			String benchmarkProfile, String customProfilePath, String allowInsecure) {
		this.vcenterHost = (vcenterHost != null && !vcenterHost.isEmpty())
				? vcenterHost : "localhost";
		this.username = (username != null) ? username : "";
		this.password = (password != null) ? password : "";
		this.benchmarkProfile = (benchmarkProfile != null && !benchmarkProfile.isEmpty())
				? benchmarkProfile : "VMware_SCG_8.0";
		this.customProfilePath = (customProfilePath != null) ? customProfilePath.trim() : "";
		this.allowInsecure = !"false".equalsIgnoreCase(allowInsecure);
	}

	public String baseUrl() {
		return "https://" + vcenterHost;
	}
}
