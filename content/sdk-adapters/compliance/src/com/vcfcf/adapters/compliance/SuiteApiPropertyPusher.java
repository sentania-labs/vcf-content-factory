package com.vcfcf.adapters.compliance;

import com.integrien.alive.common.adapter3.Logger;
import com.vcfcf.adapter.json.SimpleJson;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.cert.X509Certificate;
import java.util.LinkedHashMap;
import java.util.Map;

public final class SuiteApiPropertyPusher {

	private final String suiteApiBase;
	private final Logger logger;
	private volatile String token;

	private final String opsUser;
	private final String opsPassword;
	private final String opsAuthSource;

	public SuiteApiPropertyPusher(String suiteApiBase,
			String opsUser, String opsPassword, String opsAuthSource,
			Logger logger) {
		this.suiteApiBase = suiteApiBase;
		this.opsUser = opsUser;
		this.opsPassword = opsPassword;
		this.opsAuthSource = (opsAuthSource != null && !opsAuthSource.isEmpty())
				? opsAuthSource : "Local";
		this.logger = logger;
	}

	public void authenticate() throws IOException {
		String body = "{\"username\":\"" + escapeJson(opsUser)
				+ "\",\"password\":\"" + escapeJson(opsPassword)
				+ "\",\"authSource\":\"" + escapeJson(opsAuthSource) + "\"}";

		String resp = postJsonRaw(
				suiteApiBase + "/api/auth/token/acquire", body);
		SimpleJson parsed = SimpleJson.parse(resp);
		this.token = parsed.get("token").asString(null);
		if (token == null || token.isEmpty()) {
			throw new IOException("Suite API auth failed: no token in response");
		}
		logger.info("SuiteApiPropertyPusher: authenticated to Suite API");
	}

	public void ensureAuthenticated() throws IOException {
		if (token == null) authenticate();
	}

	public void pushProperties(String resourceId,
			Map<String, String> properties, long timestamp) {
		if (properties.isEmpty()) return;

		StringBuilder json = new StringBuilder();
		json.append("{\"property-content\":[");
		boolean first = true;
		for (Map.Entry<String, String> entry : properties.entrySet()) {
			if (!first) json.append(",");
			first = false;
			json.append("{\"statKey\":\"");
			json.append(escapeJson(entry.getKey()));
			json.append("\",\"timestamps\":[");
			json.append(timestamp);
			json.append("],\"values\":[\"");
			json.append(escapeJson(entry.getValue()));
			json.append("\"]}");
		}
		json.append("]}");

		try {
			ensureAuthenticated();
			postJsonAuth(suiteApiBase + "/api/resources/" + resourceId
					+ "/properties", json.toString());
		} catch (Exception e) {
			logger.warn("SuiteApiPropertyPusher: failed to push properties "
					+ "to " + resourceId + ": " + e.getMessage());
		}
	}

	public void pushStats(String resourceId,
			Map<String, Double> stats, long timestamp) {
		if (stats.isEmpty()) return;

		StringBuilder json = new StringBuilder();
		json.append("{\"stat-content\":[");
		boolean first = true;
		for (Map.Entry<String, Double> entry : stats.entrySet()) {
			if (!first) json.append(",");
			first = false;
			json.append("{\"statKey\":\"");
			json.append(escapeJson(entry.getKey()));
			json.append("\",\"timestamps\":[");
			json.append(timestamp);
			json.append("],\"data\":[");
			json.append(entry.getValue());
			json.append("]}");
		}
		json.append("]}");

		try {
			ensureAuthenticated();
			postJsonAuth(suiteApiBase + "/api/resources/" + resourceId
					+ "/stats", json.toString());
		} catch (Exception e) {
			logger.warn("SuiteApiPropertyPusher: failed to push stats "
					+ "to " + resourceId + ": " + e.getMessage());
		}
	}

	public String suiteApiGet(String path) throws IOException {
		ensureAuthenticated();
		URL url = new URL(suiteApiBase + path);
		HttpURLConnection conn = openConnection(url.toString());
		conn.setRequestMethod("GET");
		conn.setRequestProperty("Accept", "application/json");
		conn.setRequestProperty("Authorization", "OpsToken " + token);

		int status = conn.getResponseCode();
		String resp = readResponse(conn);
		conn.disconnect();

		if (status == 401) {
			token = null;
			authenticate();
			return suiteApiGet(path);
		}

		if (status < 200 || status >= 300) {
			throw new IOException("GET " + path + " HTTP " + status);
		}
		return resp;
	}

	private String postJsonRaw(String urlStr, String body) throws IOException {
		HttpURLConnection conn = openConnection(urlStr);
		conn.setRequestMethod("POST");
		conn.setRequestProperty("Content-Type", "application/json");
		conn.setRequestProperty("Accept", "application/json");
		conn.setDoOutput(true);

		byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
		conn.setFixedLengthStreamingMode(bytes.length);
		try (OutputStream os = conn.getOutputStream()) {
			os.write(bytes);
		}

		int status = conn.getResponseCode();
		String resp = readResponse(conn);
		conn.disconnect();

		if (status < 200 || status >= 300) {
			throw new IOException("POST " + urlStr + " HTTP " + status);
		}
		return resp;
	}

	private void postJsonAuth(String urlStr, String body) throws IOException {
		HttpURLConnection conn = openConnection(urlStr);
		conn.setRequestMethod("POST");
		conn.setRequestProperty("Content-Type", "application/json");
		conn.setRequestProperty("Accept", "application/json");
		conn.setRequestProperty("Authorization", "OpsToken " + token);
		conn.setDoOutput(true);

		byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
		conn.setFixedLengthStreamingMode(bytes.length);
		try (OutputStream os = conn.getOutputStream()) {
			os.write(bytes);
		}

		int status = conn.getResponseCode();
		conn.disconnect();

		if (status == 401) {
			token = null;
			authenticate();
			postJsonAuth(urlStr, body);
			return;
		}

		if (status < 200 || status >= 300) {
			throw new IOException("POST " + urlStr + " HTTP " + status);
		}
	}

	private HttpURLConnection openConnection(String urlStr) throws IOException {
		URL url = new URL(urlStr);
		HttpURLConnection conn = (HttpURLConnection) url.openConnection();
		if (conn instanceof HttpsURLConnection) {
			HttpsURLConnection https = (HttpsURLConnection) conn;
			try {
				SSLContext ctx = SSLContext.getInstance("TLS");
				ctx.init(null, new TrustManager[]{new TrustAll()}, null);
				https.setSSLSocketFactory(ctx.getSocketFactory());
				https.setHostnameVerifier((h, s) -> true);
			} catch (Exception e) {
				throw new IOException("SSL setup failed", e);
			}
		}
		conn.setConnectTimeout(30000);
		conn.setReadTimeout(30000);
		return conn;
	}

	private String readResponse(HttpURLConnection conn) {
		try (InputStream is = conn.getInputStream()) {
			return new String(is.readAllBytes(), StandardCharsets.UTF_8);
		} catch (Exception e) {
			try (InputStream es = conn.getErrorStream()) {
				if (es != null) {
					return new String(es.readAllBytes(), StandardCharsets.UTF_8);
				}
			} catch (Exception ignored) {}
			return "";
		}
	}

	private static String escapeJson(String s) {
		if (s == null) return "";
		return s.replace("\\", "\\\\")
				.replace("\"", "\\\"")
				.replace("\n", "\\n")
				.replace("\r", "\\r")
				.replace("\t", "\\t");
	}

	private static final class TrustAll implements X509TrustManager {
		@Override
		public void checkClientTrusted(X509Certificate[] c, String a) {}
		@Override
		public void checkServerTrusted(X509Certificate[] c, String a) {}
		@Override
		public X509Certificate[] getAcceptedIssuers() {
			return new X509Certificate[0];
		}
	}
}
