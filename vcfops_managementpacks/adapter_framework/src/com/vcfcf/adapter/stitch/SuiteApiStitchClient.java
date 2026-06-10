package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.Logger;
import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.json.SimpleJson;

import javax.net.ssl.SSLContext;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;

/**
 * Framework-level Suite API REST transport for property/stats stitching.
 *
 * <p>Generalised from the compliance adapter's dead-code
 * {@code SuiteApiPropertyPusher}. Upgraded to use {@link java.net.http.HttpClient}
 * (source-11 baseline) with platform SSL, and wired to the ambient
 * maintenance-credential path.
 *
 * <h3>Credential resolution order</h3>
 * <ol>
 *   <li><strong>Explicit</strong> — {@code host}, {@code username},
 *       {@code password} supplied via {@link Builder#explicitCredentials}
 *       (adapter-config fallback for remote collectors).</li>
 *   <li><strong>Ambient</strong> — credentials read from the platform's
 *       {@code maintenanceuser.properties}; Suite API endpoint defaults to
 *       {@code https://localhost/suite-api/} (all-in-one / cloud-proxy nodes).
 *       Password decrypted by {@link com.integrien.alive.common.security.Crypt}
 *       — the only FIPS-safe path under
 *       {@code -Dorg.bouncycastle.fips.approved_only=true}.</li>
 *   <li>If neither resolves, {@link Builder#build()} throws
 *       {@link IllegalStateException} with an actionable message.</li>
 * </ol>
 *
 * <h3>Token lifecycle</h3>
 * <p>A token is acquired before each stitching push and released in a
 * {@code finally} block — cooperative cancellation is honoured. This mirrors
 * the pattern observed in the v1 aria-ops-core stitcher (acquire → push →
 * release per collection cycle; short-lived tokens are the proven-safe pattern).
 *
 * <h3>SSL</h3>
 * <p>Uses a trust-all {@link SSLContext} (via
 * {@link VcfCfAdapter#insecureSslContext()}) for all Suite API calls.
 *
 * <p><strong>Rationale (live-proven on devel + prod, build 45, 2026-06-10):</strong>
 * The platform's {@link com.integrien.alive.common.adapter3.CustomTrustManager}
 * is a TOFU (Trust-On-First-Use) manager: {@code checkServerTrusted} throws
 * {@code CustomCertificateException} unconditionally for any unknown cert, then
 * fires {@code handleUnknownCertificate} as a side-effect notification. With the
 * old {@code URLConnection}/{@code getSocketFactory()} path the platform catches
 * that exception and retries. {@code java.net.http.HttpClient} receives the
 * exception directly — no retry — so {@code SSLHandshakeException} /
 * "PKIX path building failed" results every cycle even though the TOFU
 * notification fired (visible in appliance logs immediately after each failure).
 * The JVM default truststore likewise has no knowledge of the platform's
 * self-signed cert. Both alternatives always fail.
 *
 * <p>A trust-all context is appropriate here because: (a) the endpoint is always
 * the platform's own node ({@code https://localhost/suite-api}); (b) the cert is
 * always the platform's own self-signed cert; (c) loopback-network isolation
 * provides equivalent transport security for this hop. For remote-collector
 * deployments (non-localhost endpoints) the same trust-all is used until a
 * production remote-collector scenario is first deployed — document it in
 * {@code context/investigations/} at that time.
 *
 * <h3>Logging</h3>
 * <p>Credential values are never logged. Only the mechanism chosen
 * ({@code explicit} or {@code ambient}) and the principal name are logged.
 *
 * <h3>Usage</h3>
 * <pre>{@code
 * // Ambient (standard all-in-one node — no adapter config fields needed):
 * SuiteApiStitchClient client = SuiteApiStitchClient.builder()
 *     .adapter(this)
 *     .logger(loggerInstance)
 *     .build();
 *
 * // Explicit (remote collector fallback):
 * SuiteApiStitchClient client = SuiteApiStitchClient.builder()
 *     .adapter(this)
 *     .explicitCredentials("vcf-ops.example.com", "svcUser", "svcPass")
 *     .logger(loggerInstance)
 *     .build();
 *
 * // Use:
 * client.pushProperties(resourceUuid, props, System.currentTimeMillis());
 * client.pushStats(resourceUuid, stats, System.currentTimeMillis());
 * String body = client.get("/api/resources?adapterKind=VMWARE");
 *
 * // Release when the adapter is discarded:
 * client.discard();
 * }</pre>
 */
public final class SuiteApiStitchClient {

    /** Default Suite API base URL for all-in-one / cloud-proxy nodes. */
    static final String DEFAULT_SUITE_API_BASE = "https://localhost/suite-api";

    /** Auth source for the maintenance account — always LOCAL. */
    private static final String AUTH_SOURCE = "LOCAL";

    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(30);

    // -----------------------------------------------------------------------
    // Instance fields
    // -----------------------------------------------------------------------

    /** Raw java.net.http client (carries per-call OpsToken). */
    private final HttpClient rawHttpClient;

    /** Resolved Suite API base URL (no trailing slash). */
    private final String suiteApiBase;

    /** Principal name (read from file or config). Never logged as a secret. */
    private final String resolvedUsername;

    /** Plaintext password (decrypted if ambient). Never logged. */
    private final String resolvedPassword;

    /**
     * Mechanism string for log messages only: {@code "ambient"} or
     * {@code "explicit"}.
     */
    private final String mechanism;

    private final Logger logger;

    // -----------------------------------------------------------------------
    // Constructor (private — use Builder)
    // -----------------------------------------------------------------------

    private SuiteApiStitchClient(
            SSLContext sslContext,
            String suiteApiBase,
            String resolvedUsername,
            String resolvedPassword,
            String mechanism,
            Logger logger) {
        this.suiteApiBase = suiteApiBase;
        this.resolvedUsername = resolvedUsername;
        this.resolvedPassword = resolvedPassword;
        this.mechanism = mechanism;
        this.logger = logger;

        HttpClient.Builder hcb = HttpClient.newBuilder()
                .connectTimeout(REQUEST_TIMEOUT)
                .followRedirects(HttpClient.Redirect.NORMAL);
        if (sslContext != null) {
            hcb.sslContext(sslContext);
        }
        this.rawHttpClient = hcb.build();
    }

    // -----------------------------------------------------------------------
    // Builder
    // -----------------------------------------------------------------------

    /** Create a new {@link Builder}. */
    public static Builder builder() {
        return new Builder();
    }

    /**
     * Fluent builder for {@link SuiteApiStitchClient}.
     */
    public static final class Builder {

        private VcfCfAdapter<?> adapter = null;
        private Logger logger = null;

        // Explicit credential fields (optional; take precedence if present)
        private String explicitHost = null;
        private String explicitUsername = null;
        private String explicitPassword = null;

        private Builder() {}

        /**
         * Supply the adapter instance.
         *
         * <p>Retained for future extensibility (e.g. per-adapter logging
         * context or config inspection). The SSL context used for Suite API
         * calls is <strong>not</strong> derived from the adapter —
         * {@link VcfCfAdapter#insecureSslContext()} is always used for the
         * localhost Suite API endpoint (see class Javadoc, SSL section).
         *
         * @param adapter the adapter instance ({@code this} in configureAdapter)
         */
        public Builder adapter(VcfCfAdapter<?> adapter) {
            this.adapter = adapter;
            return this;
        }

        /**
         * Explicit Suite API credentials — highest priority if present.
         *
         * <p>Use when the adapter config exposes Suite API credential fields
         * (remote-collector fallback — {@code maintenanceuser.properties}
         * may be absent on a remote collector / cloud proxy).
         *
         * @param host     Suite API hostname (e.g. {@code "vcf-ops.example.com"});
         *                 used to build {@code https://<host>/suite-api}
         * @param username Suite API username
         * @param password Suite API password (plaintext)
         */
        public Builder explicitCredentials(String host, String username, String password) {
            this.explicitHost = host;
            this.explicitUsername = username;
            this.explicitPassword = password;
            return this;
        }

        /**
         * Logger for operational messages. Never logs credential values —
         * only the principal name and mechanism are logged.
         *
         * @param logger the adapter-specific logger
         */
        public Builder logger(Logger logger) {
            this.logger = logger;
            return this;
        }

        /**
         * Build the {@link SuiteApiStitchClient}.
         *
         * @return a configured client
         * @throws IllegalArgumentException if {@code logger} was not set
         * @throws IllegalStateException    if no credentials can be resolved
         */
        public SuiteApiStitchClient build() {
            if (logger == null) {
                throw new IllegalArgumentException(
                        "SuiteApiStitchClient.Builder: logger must not be null");
            }

            // --- Credential resolution ----------------------------------------
            String username;
            String password;
            String suiteApiBase;
            String mechanism;

            boolean hasExplicit = isNonBlank(explicitUsername)
                    && isNonBlank(explicitPassword);

            if (hasExplicit) {
                // Explicit adapter-config credentials — highest priority.
                username = explicitUsername.trim();
                password = explicitPassword.trim();
                suiteApiBase = isNonBlank(explicitHost)
                        ? "https://" + explicitHost.trim() + "/suite-api"
                        : DEFAULT_SUITE_API_BASE;
                mechanism = "explicit";
                logger.info("SuiteApiStitchClient: credential mechanism=explicit"
                        + " principal=" + username
                        + " endpoint=" + suiteApiBase);

            } else {
                // Ambient maintenance credentials (all-in-one / cloud-proxy standard path).
                AmbientCredential cred;
                try {
                    cred = AmbientCredential.load();
                } catch (IOException e) {
                    throw new IllegalStateException(
                            "SuiteApiStitchClient: cannot resolve Suite API credentials. "
                            + "Ambient credential load failed: " + e.getMessage()
                            + ". On a remote collector, supply explicit Suite API "
                            + "credential fields (host/username/password) in the adapter "
                            + "instance configuration. "
                            + "See context/investigations/"
                            + "suiteapi_ambient_auth_devel_2026_06_09.md (Caveats).",
                            e);
                }
                username = cred.getUsername();
                password = cred.getPassword();
                suiteApiBase = DEFAULT_SUITE_API_BASE;
                mechanism = "ambient";
                logger.info("SuiteApiStitchClient: credential mechanism=ambient"
                        + " principal=" + username
                        + " endpoint=" + suiteApiBase);
            }

            // --- SSL context --------------------------------------------------
            // The Suite API at localhost presents the platform's own self-signed
            // certificate. The platform's CustomTrustManager (used by
            // getPlatformSslContext()) is a TOFU manager: its checkServerTrusted()
            // throws CustomCertificateException unconditionally for any cert not
            // already in the platform's trusted store, then fires
            // handleUnknownCertificate() as a side-effect. With the old
            // URLConnection / getSocketFactory() path, the platform intercepts
            // the exception and retries after registering the cert. java.net.http
            // .HttpClient receives the exception directly — no intercept, no
            // retry — so SSLHandshakeException / PKIX path building failed is
            // the result even though CustomTrustManager's TOFU notification DID
            // fire (visible in logs immediately after each failure).
            //
            // The JVM default truststore likewise fails: it has no knowledge of
            // the platform's self-signed cert.
            //
            // The correct context for localhost Suite API calls is a trust-all
            // SSLContext. This is not a general opt-out: the endpoint is always
            // https://localhost/suite-api (the platform's own node); the cert is
            // always the platform's self-signed cert; there is no third-party
            // cert to validate. Network-level isolation (loopback) provides the
            // equivalent of transport security for this hop.
            //
            // For explicit-credential remote collectors (non-localhost endpoints),
            // the same trust-all is used for now — a proper PKI trust path for
            // remote Suite API endpoints is a future enhancement when the remote-
            // collector scenario is first deployed in production. Document any
            // production remote-collector use in context/investigations/.
            SSLContext sslContext = VcfCfAdapter.insecureSslContext();

            return new SuiteApiStitchClient(
                    sslContext, suiteApiBase, username, password, mechanism, logger);
        }

        private static boolean isNonBlank(String s) {
            return s != null && !s.trim().isEmpty();
        }
    }

    // -----------------------------------------------------------------------
    // Public stitching API
    // -----------------------------------------------------------------------

    /**
     * Push string properties onto a foreign resource.
     *
     * <p>A Suite API token is acquired before the push and released in a
     * {@code finally} block. This mirrors the v1 stitcher token lifecycle
     * (short-lived, per-call, always released).
     *
     * @param resourceId VCF Ops resource UUID (from {@link ForeignResourceResolver})
     * @param properties map of statKey → string value; no-op if empty
     * @param timestamp  sample timestamp in epoch milliseconds
     */
    public void pushProperties(String resourceId,
            Map<String, String> properties,
            long timestamp) {
        if (properties == null || properties.isEmpty()) return;

        String tok = null;
        try {
            tok = acquireToken();
            String body = buildPropertiesJson(properties, timestamp);
            rawPost("/api/resources/" + resourceId + "/properties", body, tok);
        } catch (Exception e) {
            logger.warn("SuiteApiStitchClient: pushProperties failed for resource="
                    + resourceId + ": " + e.getMessage(), e);
        } finally {
            releaseToken(tok);
        }
    }

    /**
     * Push numeric statistics onto a foreign resource.
     *
     * <p>Token lifecycle is identical to {@link #pushProperties}.
     *
     * @param resourceId VCF Ops resource UUID
     * @param stats      map of statKey → double value; no-op if empty
     * @param timestamp  sample timestamp in epoch milliseconds
     */
    public void pushStats(String resourceId,
            Map<String, Double> stats,
            long timestamp) {
        if (stats == null || stats.isEmpty()) return;

        String tok = null;
        try {
            tok = acquireToken();
            String body = buildStatsJson(stats, timestamp);
            rawPost("/api/resources/" + resourceId + "/stats", body, tok);
        } catch (Exception e) {
            logger.warn("SuiteApiStitchClient: pushStats failed for resource="
                    + resourceId + ": " + e.getMessage(), e);
        } finally {
            releaseToken(tok);
        }
    }

    /**
     * Perform an authenticated GET against the Suite API.
     *
     * <p>Acquires and releases a token around the single GET call.
     *
     * @param path path relative to the Suite API base (e.g.
     *             {@code "/api/resources?adapterKind=VMWARE"})
     * @return the response body as a string
     * @throws IOException          on HTTP or network error
     * @throws InterruptedException if the calling thread is interrupted
     */
    public String get(String path) throws IOException, InterruptedException {
        String tok = null;
        try {
            tok = acquireToken();
            return rawGet(path, tok);
        } finally {
            releaseToken(tok);
        }
    }

    /**
     * Release the underlying HTTP client resources.
     *
     * <p>Call from the adapter's {@code onDiscard()} method, alongside
     * releasing the {@link com.vcfcf.adapter.http.ManagedHttpClient}.
     */
    public void discard() {
        // java.net.http.HttpClient does not implement Closeable in Java 11.
        // Nothing to explicitly close — GC reclaims the connection pool.
        // This method exists as a lifecycle hook for future extensibility
        // and to make the discard pattern visible to adapter authors.
    }

    // -----------------------------------------------------------------------
    // Token management (internal)
    // -----------------------------------------------------------------------

    /**
     * POST to {@code /api/auth/token/acquire} with the resolved credentials
     * and return the bearer token string.
     */
    private String acquireToken() throws IOException, InterruptedException {
        String body = "{\"username\":" + jsonStr(resolvedUsername)
                + ",\"password\":" + jsonStr(resolvedPassword)
                + ",\"authSource\":" + jsonStr(AUTH_SOURCE) + "}";

        byte[] bodyBytes = body.getBytes(StandardCharsets.UTF_8);
        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(suiteApiBase + "/api/auth/token/acquire"))
                .timeout(REQUEST_TIMEOUT)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .POST(HttpRequest.BodyPublishers.ofByteArray(bodyBytes))
                .build();

        HttpResponse<String> resp = rawHttpClient.send(
                req, HttpResponse.BodyHandlers.ofString());

        int status = resp.statusCode();
        if (status < 200 || status >= 300) {
            throw new IOException(
                    "Suite API token/acquire failed: HTTP " + status
                    + " mechanism=" + mechanism
                    + " principal=" + resolvedUsername);
        }

        SimpleJson parsed = SimpleJson.parse(resp.body());
        String token = parsed.get("token").asString(null);
        if (token == null || token.isEmpty()) {
            throw new IOException(
                    "Suite API token/acquire: no 'token' field in response"
                    + " mechanism=" + mechanism
                    + " principal=" + resolvedUsername);
        }
        return token;
    }

    /**
     * POST to {@code /api/auth/token/release} to invalidate the token.
     *
     * <p>Safe to call with a {@code null} token. Exceptions are swallowed and
     * logged at WARN — this is always called from a {@code finally} block and
     * must never mask the original exception.
     */
    private void releaseToken(String token) {
        if (token == null) return;
        try {
            String body = "{\"token\":" + jsonStr(token) + "}";
            byte[] bodyBytes = body.getBytes(StandardCharsets.UTF_8);
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(suiteApiBase + "/api/auth/token/release"))
                    .timeout(REQUEST_TIMEOUT)
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofByteArray(bodyBytes))
                    .build();
            rawHttpClient.send(req, HttpResponse.BodyHandlers.discarding());
        } catch (Exception e) {
            logger.warn("SuiteApiStitchClient: token release failed (non-fatal): "
                    + e.getMessage());
        }
    }

    // -----------------------------------------------------------------------
    // Raw HTTP helpers (carry per-call OpsToken)
    // -----------------------------------------------------------------------

    private void rawPost(String apiPath, String body, String opsToken)
            throws IOException, InterruptedException {
        byte[] bodyBytes = body.getBytes(StandardCharsets.UTF_8);
        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(suiteApiBase + apiPath))
                .timeout(REQUEST_TIMEOUT)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .header("Authorization", "OpsToken " + opsToken)
                .POST(HttpRequest.BodyPublishers.ofByteArray(bodyBytes))
                .build();

        HttpResponse<Void> resp = rawHttpClient.send(
                req, HttpResponse.BodyHandlers.discarding());

        int status = resp.statusCode();
        if (status == 401) {
            throw new IOException(
                    "Suite API POST " + apiPath
                    + " returned 401 — token expired or credential invalid"
                    + " mechanism=" + mechanism
                    + " principal=" + resolvedUsername);
        }
        if (status < 200 || status >= 300) {
            throw new IOException(
                    "Suite API POST " + apiPath + " HTTP " + status);
        }
    }

    private String rawGet(String apiPath, String opsToken)
            throws IOException, InterruptedException {
        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(suiteApiBase + apiPath))
                .timeout(REQUEST_TIMEOUT)
                .header("Accept", "application/json")
                .header("Authorization", "OpsToken " + opsToken)
                .GET()
                .build();

        HttpResponse<String> resp = rawHttpClient.send(
                req, HttpResponse.BodyHandlers.ofString());

        int status = resp.statusCode();
        if (status == 401) {
            throw new IOException(
                    "Suite API GET " + apiPath
                    + " returned 401 mechanism=" + mechanism
                    + " principal=" + resolvedUsername);
        }
        if (status < 200 || status >= 300) {
            throw new IOException(
                    "Suite API GET " + apiPath + " HTTP " + status);
        }
        return resp.body();
    }

    // -----------------------------------------------------------------------
    // JSON helpers
    // -----------------------------------------------------------------------

    private static String buildPropertiesJson(
            Map<String, String> properties, long timestamp) {
        StringBuilder sb = new StringBuilder("{\"property-content\":[");
        boolean first = true;
        for (Map.Entry<String, String> e : properties.entrySet()) {
            if (!first) sb.append(",");
            first = false;
            sb.append("{\"statKey\":").append(jsonStr(e.getKey()))
              .append(",\"timestamps\":[").append(timestamp).append("]")
              .append(",\"values\":[").append(jsonStr(e.getValue())).append("]}");
        }
        return sb.append("]}").toString();
    }

    private static String buildStatsJson(
            Map<String, Double> stats, long timestamp) {
        StringBuilder sb = new StringBuilder("{\"stat-content\":[");
        boolean first = true;
        for (Map.Entry<String, Double> e : stats.entrySet()) {
            if (!first) sb.append(",");
            first = false;
            sb.append("{\"statKey\":").append(jsonStr(e.getKey()))
              .append(",\"timestamps\":[").append(timestamp).append("]")
              .append(",\"data\":[").append(e.getValue()).append("]}");
        }
        return sb.append("]}").toString();
    }

    /**
     * JSON-encode a string value (double-quoted, minimal escaping).
     * Returns {@code null} for a null input.
     */
    static String jsonStr(String s) {
        if (s == null) return "null";
        return "\""
                + s.replace("\\", "\\\\")
                   .replace("\"", "\\\"")
                   .replace("\n", "\\n")
                   .replace("\r", "\\r")
                   .replace("\t", "\\t")
                + "\"";
    }
}
