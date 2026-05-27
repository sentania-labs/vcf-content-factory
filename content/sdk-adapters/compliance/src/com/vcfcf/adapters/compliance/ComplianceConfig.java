package com.vcfcf.adapters.compliance;

public final class ComplianceConfig {

	public final String vcenterHost;
	public final String username;
	public final String password;
	public final String benchmarkProfile;
	public final String customProfilePath;
	public final boolean allowInsecure;
	public final String opsHost;
	public final String opsUser;
	public final String opsPassword;
	public final String opsAuthSource;

	public ComplianceConfig(String vcenterHost, String username, String password,
			String benchmarkProfile, String customProfilePath, String allowInsecure,
			String opsHost, String opsUser, String opsPassword,
			String opsAuthSource) {
		this.vcenterHost = (vcenterHost != null && !vcenterHost.isEmpty())
				? vcenterHost : "localhost";
		this.username = (username != null) ? username : "";
		this.password = (password != null) ? password : "";
		this.benchmarkProfile = (benchmarkProfile != null && !benchmarkProfile.isEmpty())
				? benchmarkProfile : "CIS_8.0";
		this.customProfilePath = (customProfilePath != null) ? customProfilePath.trim() : "";
		this.allowInsecure = !"false".equalsIgnoreCase(allowInsecure);
		this.opsHost = (opsHost != null && !opsHost.isEmpty()) ? opsHost : "localhost";
		this.opsUser = (opsUser != null && !opsUser.isEmpty()) ? opsUser : "admin";
		this.opsPassword = (opsPassword != null) ? opsPassword : "";
		this.opsAuthSource = (opsAuthSource != null && !opsAuthSource.isEmpty())
				? opsAuthSource : "Local";
	}

	public String baseUrl() {
		return "https://" + vcenterHost;
	}

	public String suiteApiBase() {
		return "https://" + opsHost + "/suite-api";
	}
}
