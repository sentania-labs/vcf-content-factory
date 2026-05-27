package com.vcfcf.adapters.compliance;

import com.vcfcf.adapter.json.SimpleJson;

import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.security.cert.X509Certificate;
import java.time.Duration;
import java.util.Base64;

public final class VCenterApiClient {

	private final HttpClient httpClient;
	private final String baseUrl;
	private final String username;
	private final String password;
	private volatile String sessionId;

	public VCenterApiClient(String baseUrl, String username, String password,
			boolean allowInsecure) {
		this.baseUrl = baseUrl;
		this.username = username;
		this.password = password;

		HttpClient.Builder builder = HttpClient.newBuilder()
				.connectTimeout(Duration.ofSeconds(30));
		if (allowInsecure) {
			try {
				SSLContext ctx = SSLContext.getInstance("TLS");
				ctx.init(null, new TrustManager[]{new TrustAllManager()}, null);
				builder.sslContext(ctx);
			} catch (Exception e) {
				throw new RuntimeException("Failed to configure insecure SSL", e);
			}
		}
		this.httpClient = builder.build();
	}

	public String login() throws IOException, InterruptedException {
		String credentials = Base64.getEncoder().encodeToString(
				(username + ":" + password).getBytes());

		HttpRequest req = HttpRequest.newBuilder()
				.uri(URI.create(baseUrl + "/api/session"))
				.POST(HttpRequest.BodyPublishers.ofString(""))
				.header("Authorization", "Basic " + credentials)
				.header("Content-Type", "application/json")
				.timeout(Duration.ofSeconds(30))
				.build();

		HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
		if (resp.statusCode() != 200 && resp.statusCode() != 201) {
			throw new IOException("vCenter login failed: HTTP " + resp.statusCode());
		}

		String body = resp.body();
		if (body != null) {
			body = body.trim();
			if (body.startsWith("\"") && body.endsWith("\"")) {
				body = body.substring(1, body.length() - 1);
			}
		}
		this.sessionId = body;
		return sessionId;
	}

	public void logout() {
		if (sessionId == null) return;
		try {
			HttpRequest req = HttpRequest.newBuilder()
					.uri(URI.create(baseUrl + "/api/session"))
					.method("DELETE", HttpRequest.BodyPublishers.noBody())
					.header("vmware-api-session-id", sessionId)
					.timeout(Duration.ofSeconds(10))
					.build();
			httpClient.send(req, HttpResponse.BodyHandlers.ofString());
		} catch (Exception ignored) {}
		sessionId = null;
	}

	public void ensureSession() throws IOException, InterruptedException {
		if (sessionId == null) login();
	}

	public SimpleJson listHosts() throws IOException, InterruptedException {
		return apiGet("/api/vcenter/host");
	}

	public SimpleJson getHost(String hostId) throws IOException, InterruptedException {
		return apiGet("/api/vcenter/host/" + hostId);
	}

	public SimpleJson listVMs() throws IOException, InterruptedException {
		return apiGet("/api/vcenter/vm");
	}

	public SimpleJson getVM(String vmId) throws IOException, InterruptedException {
		return apiGet("/api/vcenter/vm/" + vmId);
	}

	public SimpleJson getHostDetail(String hostId)
			throws IOException, InterruptedException {
		return getHost(hostId);
	}

	private SimpleJson apiGet(String path) throws IOException, InterruptedException {
		ensureSession();

		HttpResponse<String> resp = doGet(path);
		if (resp.statusCode() == 401) {
			sessionId = null;
			login();
			resp = doGet(path);
		}

		if (resp.statusCode() != 200) {
			throw new IOException("vCenter API " + path + ": HTTP " + resp.statusCode());
		}

		return SimpleJson.parse(resp.body());
	}

	private HttpResponse<String> doGet(String path)
			throws IOException, InterruptedException {
		HttpRequest req = HttpRequest.newBuilder()
				.uri(URI.create(baseUrl + path))
				.GET()
				.header("vmware-api-session-id", sessionId)
				.header("Accept", "application/json")
				.timeout(Duration.ofSeconds(30))
				.build();
		return httpClient.send(req, HttpResponse.BodyHandlers.ofString());
	}

	private static final class TrustAllManager implements X509TrustManager {
		@Override public void checkClientTrusted(X509Certificate[] chain, String authType) {}
		@Override public void checkServerTrusted(X509Certificate[] chain, String authType) {}
		@Override public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
	}
}
