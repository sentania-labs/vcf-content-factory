package com.vcfcf.adapters.synology;

import com.vcfcf.adapter.http.ManagedHttpClient;
import com.vcfcf.adapter.json.SimpleJson;

import java.io.IOException;
import java.net.http.HttpResponse;
import java.util.logging.Logger;

/**
 * Wraps the Synology DSM Web API. All calls go to /webapi/entry.cgi
 * differentiated by query parameters. Session auth via _sid query param.
 *
 * FRAMEWORK NOTE: Synology uses _sid as a query parameter, not a cookie.
 * The framework's SessionCookieAuth adds a Cookie header, which DSM may
 * also accept, but the documented mechanism is the query param. This
 * client manages the session ID directly rather than using the framework's
 * auth strategies. This is a framework gap: a QueryParamAuth strategy
 * should be added for APIs that authenticate via query parameters.
 */
public final class SynologyApiClient {

	private static final Logger LOG = Logger.getLogger(SynologyApiClient.class.getName());
	private static final String SESSION_NAME = "VCFContentFactory";

	private final ManagedHttpClient http;
	private final String username;
	private final String password;
	private volatile String sid;

	public SynologyApiClient(ManagedHttpClient http, String username, String password) {
		this.http = http;
		this.username = username;
		this.password = password;
	}

	// --- Session management ---

	public String login() throws IOException, InterruptedException {
		String path = synoUrl("SYNO.API.Auth", 7, "login",
				"account=" + urlEncode(username),
				"passwd=" + urlEncode(password),
				"session=" + SESSION_NAME,
				"format=sid");
		SimpleJson resp = callRaw(path);
		if (!resp.isSuccess()) {
			int code = (int) resp.get("error").get("code").asLong();
			throw new IOException("Synology login failed: error code " + code);
		}
		this.sid = resp.data().get("sid").asString();
		LOG.info("Synology login succeeded, session=" + SESSION_NAME);
		return this.sid;
	}

	public void logout() {
		if (sid == null) return;
		try {
			callRaw(synoUrl("SYNO.API.Auth", 7, "logout",
					"session=" + SESSION_NAME));
		} catch (Exception e) {
			LOG.warning("Logout failed (non-fatal): " + e.getMessage());
		}
		sid = null;
	}

	public void ensureSession() throws IOException, InterruptedException {
		if (sid == null) login();
	}

	public void invalidateSession() {
		sid = null;
	}

	// --- API calls (each returns parsed JSON) ---

	/** DSM.Info: model, serial, temp, uptime, version */
	public SimpleJson dsmInfo() throws IOException, InterruptedException {
		return call("SYNO.DSM.Info", 2, "getinfo");
	}

	/** Core.System info: CPU details, firmware, NTP, timezone */
	public SimpleJson systemInfo() throws IOException, InterruptedException {
		return call("SYNO.Core.System", 3, "info");
	}

	/** Core.System.Utilization: CPU, memory, network, per-disk IO, per-LUN IO, NFS */
	public SimpleJson utilization() throws IOException, InterruptedException {
		return call("SYNO.Core.System.Utilization", 1, "get");
	}

	/** Storage.CGI.Storage load_info: pools, volumes, disks in one call */
	public SimpleJson storageLoadInfo() throws IOException, InterruptedException {
		return call("SYNO.Storage.CGI.Storage", 1, "load_info");
	}

	/** Core.ISCSI.LUN list: LUN metadata */
	public SimpleJson iscsiLunList() throws IOException, InterruptedException {
		return call("SYNO.Core.ISCSI.LUN", 1, "list");
	}

	/** Core.ISCSI.Target list: target IQN for ESXi correlation */
	public SimpleJson iscsiTargetList() throws IOException, InterruptedException {
		return call("SYNO.Core.ISCSI.Target", 1, "list");
	}

	/** Core.Hardware.FanSpeed: fan status */
	public SimpleJson fanSpeed() throws IOException, InterruptedException {
		return call("SYNO.Core.Hardware.FanSpeed", 1, "get");
	}

	/** Core.Network.Interface list: NIC inventory */
	public SimpleJson networkInterfaceList() throws IOException, InterruptedException {
		return call("SYNO.Core.Network.Interface", 1, "list");
	}

	/** Core.System.Status: crash flag, upgrade flag */
	public SimpleJson systemStatus() throws IOException, InterruptedException {
		return call("SYNO.Core.System.Status", 1, "get");
	}

	/** Core.FileServ.NFS get: NFS service config */
	public SimpleJson nfsServiceGet() throws IOException, InterruptedException {
		return call("SYNO.Core.FileServ.NFS", 3, "get");
	}

	/** Core.Share list: all shared folders with additional fields */
	public SimpleJson shareList() throws IOException, InterruptedException {
		String additional = "%5B%22hidden%22%2C%22encryption%22%2C%22share_quota%22%2C"
				+ "%22enable_share_cow%22%2C%22quota_value%22%2C%22enable_share_compress%22%5D";
		return call("SYNO.Core.Share", 1, "list",
				"shareType=all", "additional=" + additional);
	}

	/** NFS.SharePrivilege load: per-share NFS rules */
	public SimpleJson nfsSharePrivilege(String shareName) throws IOException, InterruptedException {
		return call("SYNO.Core.FileServ.NFS.SharePrivilege", 1, "load",
				"share_name=" + urlEncode(shareName));
	}

	/** Core.CurrentConnection get: active client list */
	public SimpleJson currentConnections() throws IOException, InterruptedException {
		return call("SYNO.Core.CurrentConnection", 1, "get");
	}

	/** Core.ExternalDevice.UPS get: UPS status */
	public SimpleJson upsGet() throws IOException, InterruptedException {
		return call("SYNO.Core.ExternalDevice.UPS", 1, "get");
	}

	// --- Internal helpers ---

	private SimpleJson call(String api, int version, String method, String... extra)
			throws IOException, InterruptedException {
		ensureSession();
		SimpleJson resp = callRaw(synoUrl(api, version, method, extra));
		if (!resp.isSuccess()) {
			int code = (int) resp.get("error").get("code").asLong();
			if (code == 106 || code == 107 || code == 119) {
				LOG.info("Session expired (code=" + code + "), re-authenticating...");
				invalidateSession();
				login();
				resp = callRaw(synoUrl(api, version, method, extra));
			}
			if (!resp.isSuccess()) {
				throw new IOException(api + " " + method + " failed: " + resp.asString());
			}
		}
		return resp;
	}

	private SimpleJson callRaw(String path) throws IOException, InterruptedException {
		HttpResponse<String> resp = http.get(path, HttpResponse.BodyHandlers.ofString());
		if (resp.statusCode() != 200) {
			throw new IOException("HTTP " + resp.statusCode() + " from " + path);
		}
		return SimpleJson.parse(resp.body());
	}

	private String synoUrl(String api, int version, String method, String... extra) {
		StringBuilder sb = new StringBuilder("/webapi/entry.cgi?api=");
		sb.append(api).append("&version=").append(version).append("&method=").append(method);
		if (sid != null) {
			sb.append("&_sid=").append(sid);
		}
		for (String param : extra) {
			sb.append("&").append(param);
		}
		return sb.toString();
	}

	private static String urlEncode(String s) {
		if (s == null) return "";
		StringBuilder sb = new StringBuilder();
		for (char c : s.toCharArray()) {
			if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
					(c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~') {
				sb.append(c);
			} else {
				for (byte b : String.valueOf(c).getBytes(java.nio.charset.StandardCharsets.UTF_8)) {
					sb.append(String.format("%%%02X", b & 0xFF));
				}
			}
		}
		return sb.toString();
	}
}
