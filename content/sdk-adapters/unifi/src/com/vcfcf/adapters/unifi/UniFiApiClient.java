package com.vcfcf.adapters.unifi;

import com.vcfcf.adapter.http.ManagedHttpClient;
import com.vcfcf.adapter.json.SimpleJson;

import java.io.IOException;
import java.net.http.HttpResponse;
import java.util.logging.Logger;

public final class UniFiApiClient {

	private static final Logger LOG = Logger.getLogger(UniFiApiClient.class.getName());

	private final ManagedHttpClient http;

	public UniFiApiClient(ManagedHttpClient http) {
		this.http = http;
	}

	// --- Network API endpoints ---

	public SimpleJson listSites() throws IOException, InterruptedException {
		return get("/proxy/network/api/self/sites");
	}

	public SimpleJson statDevice(String site) throws IOException, InterruptedException {
		return get("/proxy/network/api/s/" + site + "/stat/device");
	}

	public SimpleJson statHealth(String site) throws IOException, InterruptedException {
		return get("/proxy/network/api/s/" + site + "/stat/health");
	}

	// --- Protect API ---

	public SimpleJson protectBootstrap() throws IOException, InterruptedException {
		return get("/proxy/protect/api/bootstrap");
	}

	// --- HTTP ---

	private SimpleJson get(String path) throws IOException, InterruptedException {
		HttpResponse<String> resp = http.get(path, HttpResponse.BodyHandlers.ofString());
		if (resp.statusCode() != 200) {
			throw new IOException("UniFi GET " + path + " returned HTTP " + resp.statusCode());
		}
		return SimpleJson.parse(resp.body());
	}

	/** Login and return the session token value (for SessionCookieAuth). */
	public static String login(ManagedHttpClient rawHttp, String username, String password)
			throws IOException, InterruptedException {
		String body = "{\"username\":\"" + jsonEscape(username)
				+ "\",\"password\":\"" + jsonEscape(password) + "\"}";
		HttpResponse<String> resp = rawHttp.post("/api/auth/login", body,
				"application/json", HttpResponse.BodyHandlers.ofString());
		if (resp.statusCode() != 200) {
			throw new IOException("UniFi login failed: HTTP " + resp.statusCode());
		}
		// UniFi OS sets TOKEN; classic controllers set unifises
		String token = extractCookie(resp, "TOKEN");
		if (token == null) token = extractCookie(resp, "unifises");
		if (token == null) {
			throw new IOException("UniFi login: no session cookie in response");
		}
		LOG.info("UniFi session acquired");
		return token;
	}

	private static String extractCookie(HttpResponse<String> resp, String name) {
		return resp.headers().allValues("set-cookie").stream()
				.filter(c -> c.startsWith(name + "="))
				.map(c -> {
					int eq = c.indexOf('=');
					int semi = c.indexOf(';', eq);
					return semi > 0 ? c.substring(eq + 1, semi) : c.substring(eq + 1);
				})
				.findFirst()
				.orElse(null);
	}

	private static String jsonEscape(String s) {
		return s.replace("\\", "\\\\")
				.replace("\"", "\\\"")
				.replace("\n", "\\n")
				.replace("\r", "\\r")
				.replace("\t", "\\t");
	}
}
