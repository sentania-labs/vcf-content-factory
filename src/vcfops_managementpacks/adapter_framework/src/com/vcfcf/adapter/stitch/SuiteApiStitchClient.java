package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.Logger;
import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.json.SimpleJson;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;

/**
 * Framework-level Suite API REST transport for property/stats stitching.
 *
 * <p>Generalised from the compliance adapter's dead-code
 * {@code SuiteApiPropertyPusher}. All HTTP calls go through
 * {@link VcfCfAdapter#openPlatformConnection(String)} — an
 * {@code HttpsURLConnection} wired to mirror the vendor
 * {@code aria-ops-core SuiteAPIClient.getClientConfigBuilder()} transport
 * <strong>exactly</strong> (see
 * {@code context/api-surface/casa-injected-vs-raw-client.md} §3): trust-all +
 * ignore-hostname in non-FIPS mode (server-trust only — no client keystore, no
 * CaSA, no cert-renewal registration), with a documented-TODO FIPS branch (see
 * {@link VcfCfAdapter#openPlatformConnection(String)}). This replaced an
 * earlier attempt to route the loopback hop through the platform's strict TOFU
 * {@code CustomTrustManager} (via {@code getSocketFactory()}), which PKIX-fails
 * every cycle on live devel because framework adapters declare no
 * cert-renewal URL set for the platform's non-disruptive certificate handler
 * to persist trust against — see
 * {@code context/investigations/synology-b23-devel-pkix-2026-07-01.md} and
 * {@code context/defects.md} DEF-005. It also eliminates the earlier
 * {@code java.net.http.HttpClient} + {@code insecureSslContext()} path, which
 * could not inject a {@code HostnameVerifier} and failed with
 * {@code certificate_unknown(46)} on production appliances whose
 * operator-replaced cert has no {@code localhost} SAN (see §5 of
 * {@code specs/20-suiteapi-client-behavioral-contract.md}).
 *
 * <p>The credential mechanism still determines the Suite API endpoint:
 * <ul>
 *   <li><strong>Ambient</strong> — identity v3 order: the platform-injected
 *       per-instance credential ({@code adapter.getAdapterConfig()
 *       .getAdapterCredentials()}, when present), then
 *       {@code automationuser.properties} ({@code automationAdmin}), then
 *       {@code maintenanceuser.properties} only if both prior sources are
 *       absent/unreadable — see {@link AmbientCredential}; endpoint defaults
 *       to {@code https://localhost/suite-api/} (resolves to loopback →
 *       all-true hostname verifier).</li>
 *   <li><strong>Explicit</strong> — adapter-config host/username/password;
 *       endpoint is {@code https://<host>/suite-api/} (resolves to non-loopback →
 *       JDK strict hostname verification). Use on remote collectors where
 *       neither ambient source may be present. The explicit URL must
 *       target the primary/analytics Suite API node — pointing at {@code localhost}
 *       on a collector yields HTTP 403 (suite-api not served on collectors).</li>
 * </ul>
 *
 * <h3>Credential resolution order</h3>
 * <ol>
 *   <li><strong>Explicit</strong> — {@code host}, {@code username},
 *       {@code password} supplied via {@link Builder#explicitCredentials}
 *       (adapter-config fallback for remote collectors).</li>
 *   <li><strong>Ambient</strong> — identity v3: (a) the platform-injected
 *       per-instance credential read via the SDK-public
 *       {@code AdapterBase.getAdapterConfig().getAdapterCredentials()} chain
 *       (see {@code context/api-surface/
 *       per-instance-suiteapi-credential-contract.md}), preferred
 *       unconditionally when present; (b) {@code automationuser.properties}
 *       ({@code automationAdmin}); (c) {@code maintenanceuser.properties}
 *       only if (a) and (b) are both absent/unreadable ({@link
 *       AmbientCredential#load(com.integrien.alive.common.adapter3.config.AdapterConfig)}).
 *       Suite API endpoint defaults to {@code https://localhost/suite-api/}
 *       (primary/analytics node only). File-based password decrypted by
 *       {@link com.integrien.alive.common.security.Crypt} — the only
 *       FIPS-safe path under
 *       {@code -Dorg.bouncycastle.fips.approved_only=true} (the injected
 *       credential arrives already plaintext in the deserialized config, no
 *       decryption needed).</li>
 *   <li>If neither resolves, {@link Builder#build()} throws
 *       {@link IllegalStateException} with an actionable message.</li>
 * </ol>
 *
 * <h3>Token lifecycle (per spec §1/§2/§3)</h3>
 * <p>A bearer token is acquired lazily on the first call and cached for the
 * lifetime of this instance. On HTTP 401, the token is re-acquired and the
 * failed request is retried exactly once. The cached token is released in
 * {@link #discard()} — errors during release are swallowed and logged (the
 * platform's token TTL is the safety net). This matches the
 * {@code RestClientProxy} ({@code SuiteAPIClient}) behavioral contract:
 * per-instance caching, single 401 retry, close-time release.
 *
 * <h3>Logging</h3>
 * <p>Credential values are never logged. Only the mechanism chosen
 * ({@code explicit} or {@code ambient}) and the principal name are logged.
 *
 * <h3>Usage</h3>
 * <pre>{@code
 * // Ambient (standard primary-node — no adapter config fields needed):
 * SuiteApiStitchClient client = SuiteApiStitchClient.builder()
 *     .adapter(this)
 *     .logger(loggerInstance)
 *     .build();
 *
 * // Explicit (remote collector fallback; host must be the primary FQDN):
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

    /** Default Suite API base URL for the primary/analytics node. */
    static final String DEFAULT_SUITE_API_BASE = "https://localhost/suite-api";

    /** Auth source for the maintenance account — always LOCAL. */
    private static final String AUTH_SOURCE = "LOCAL";

    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(30);

    // -----------------------------------------------------------------------
    // Instance fields
    // -----------------------------------------------------------------------

    /**
     * Adapter instance. Always non-null — used to call
     * {@link VcfCfAdapter#openPlatformConnection(String)} for every Suite API
     * connection (both loopback and explicit/remote paths).
     */
    private final VcfCfAdapter<?> adapter;

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

    /**
     * Cached bearer token. {@code null} until first use; re-nulled on 401 to
     * force re-acquisition. Volatile so reads in {@link #ensureToken()} before
     * the synchronized block see a fresh value.
     */
    private volatile String cachedToken = null;

    /** Guard for token acquire / invalidate operations. */
    private final Object tokenLock = new Object();

    // -----------------------------------------------------------------------
    // Private exception — distinguishes 401 for the single-retry path
    // -----------------------------------------------------------------------

    /** Thrown by {@code rawPost}/{@code rawGet} on HTTP 401 only. */
    private static final class Suite401Exception extends IOException {
        Suite401Exception(String message) { super(message); }
    }

    // -----------------------------------------------------------------------
    // Constructor (private — use Builder)
    // -----------------------------------------------------------------------

    private SuiteApiStitchClient(
            VcfCfAdapter<?> adapter,
            String suiteApiBase,
            String resolvedUsername,
            String resolvedPassword,
            String mechanism,
            Logger logger) {
        this.adapter = adapter;
        this.suiteApiBase = suiteApiBase;
        this.resolvedUsername = resolvedUsername;
        this.resolvedPassword = resolvedPassword;
        this.mechanism = mechanism;
        this.logger = logger;
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
         * Supply the adapter instance. Required — the adapter's
         * {@link VcfCfAdapter#openPlatformConnection(String)} is called for
         * every Suite API connection (both loopback and explicit/remote paths).
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
         * <p><strong>The {@code host} must be the primary/analytics Suite API
         * FQDN.</strong> Pointing explicit credentials at {@code localhost} on a
         * remote collector still yields HTTP 403 — the global VMWARE inventory
         * is not served on collector nodes (spec §4).
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
         * @throws IllegalArgumentException if {@code logger} or {@code adapter}
         *                                  was not set
         * @throws IllegalStateException    if no credentials can be resolved
         */
        public SuiteApiStitchClient build() {
            if (logger == null) {
                throw new IllegalArgumentException(
                        "SuiteApiStitchClient.Builder: logger must not be null");
            }
            if (adapter == null) {
                throw new IllegalArgumentException(
                        "SuiteApiStitchClient.Builder: adapter must not be null — "
                        + "call .adapter(this) on the builder. "
                        + "See SuiteApiStitcher.create().");
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
                // Ambient credentials — identity v3 order: platform-injected
                // per-instance credential (adapter.getAdapterConfig()) first,
                // then automation.properties, then maintenance.properties.
                AmbientCredential cred;
                try {
                    cred = AmbientCredential.load(safeGetAdapterConfig(adapter));
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
                        + " file=" + cred.getSourceLabel()
                        + " principal=" + username
                        + " endpoint=" + suiteApiBase);

                // WARNING-1 breadcrumb (ambient-credential-v3-instance-first
                // review): an AdapterConfig was present but the "instance"
                // source lost — record why, once, at INFO. This is the
                // diagnostic the identity-v3 change exists to surface; a
                // swallowed reason nobody can see defeats the point. Sanitized
                // by AmbientCredential#getInjectedFailureReason() — exception
                // class name (+ message only for a LinkageError, which is
                // just the missing class name) or "credentials null/blank".
                // Never the password, never a raw exception message.
                if (cred.getInjectedFailureReason() != null) {
                    logger.info("SuiteApiStitchClient: instance-credential not used"
                            + " reason=" + cred.getInjectedFailureReason());
                }
            }

            // --- Transport log ------------------------------------------------
            // All calls go through openPlatformConnection (unified transport).
            // isLoopbackUrl is informational only (logged for operational
            // clarity) — since DEF-005 the transport no longer peer-gates:
            // it mirrors the vendor aria-ops-core SuiteAPIClient non-FIPS
            // posture (trust-all + ignore-hostname) for loopback and remote
            // Suite API endpoints alike, exactly as every shipping Broadcom
            // pak does. See openPlatformConnection() for the FIPS branch note.
            boolean loopback = SuiteApiStitchClient.isLoopbackUrl(suiteApiBase);
            logger.info("SuiteApiStitchClient: transport=openPlatformConnection"
                    + (loopback ? " loopback" : " remote")
                    + " (BC-mirror: trust-all + ignore-hostname, non-FIPS)"
                    + " mechanism=" + mechanism
                    + " principal=" + username);

            return new SuiteApiStitchClient(
                    adapter,
                    suiteApiBase,
                    username, password, mechanism, logger);
        }

        private static boolean isNonBlank(String s) {
            return s != null && !s.trim().isEmpty();
        }

        /**
         * Read {@code adapter.getAdapterConfig()} defensively for the
         * injected-credential probe (identity v3). Returns {@code null} on
         * any failure — including a null {@code adapter} or the platform not
         * yet having injected config (early lifecycle / test harness) —
         * rather than throwing, so {@link AmbientCredential#load(
         * com.integrien.alive.common.adapter3.config.AdapterConfig)} sees an
         * absent source and falls through to the file-based candidates.
         */
        private static com.integrien.alive.common.adapter3.config.AdapterConfig
                safeGetAdapterConfig(VcfCfAdapter<?> adapter) {
            if (adapter == null) {
                return null;
            }
            try {
                return adapter.getAdapterConfig();
            } catch (Exception | LinkageError e) {
                // Narrowed from catch (Throwable) — mirrors
                // AmbientCredential.tryInjectedCredential's defensive posture
                // (see its javadoc: a NoClassDefFoundError surfaced live
                // while probing this same accessor chain during identity v3
                // testing). Honors the documented crash-the-cycle case
                // (Exception, LinkageError) while letting
                // VirtualMachineError/ThreadDeath propagate. Absent/
                // unreadable source falls through; nothing throws out of
                // construction.
                return null;
            }
        }
    }

    // -----------------------------------------------------------------------
    // Package-visible statics (for unit tests in com.vcfcf.adapter.stitch)
    // -----------------------------------------------------------------------

    /**
     * Resolve the host in {@code url} to an {@link InetAddress} and check
     * {@link InetAddress#isLoopbackAddress()}.
     *
     * <p>Returns {@code false} on any resolution failure (fail-open: unknown
     * hosts are treated as non-loopback so the explicit/strict path is used).
     * Visible to unit tests in the same package.
     */
    static boolean isLoopbackUrl(String url) {
        try {
            String host = URI.create(url).getHost();
            if (host == null) return false;
            return InetAddress.getByName(host).isLoopbackAddress();
        } catch (Exception e) {
            return false;
        }
    }

    // -----------------------------------------------------------------------
    // Public stitching API
    // -----------------------------------------------------------------------

    /**
     * Push string properties onto a foreign resource.
     *
     * <p>The cached bearer token is used. If the Suite API returns HTTP 401,
     * the token is re-acquired and the push is retried exactly once. Failures
     * are logged at WARN and swallowed — a stitching failure must not abort
     * the adapter's primary collect cycle.
     *
     * @param resourceId VCF Ops resource UUID (from {@link ForeignResourceResolver})
     * @param properties map of statKey → string value; no-op if empty
     * @param timestamp  sample timestamp in epoch milliseconds
     */
    public void pushProperties(String resourceId,
            Map<String, String> properties,
            long timestamp) {
        if (properties == null || properties.isEmpty()) return;

        String body = buildPropertiesJson(properties, timestamp);
        String path = "/api/resources/" + resourceId + "/properties";
        try {
            String tok = ensureToken();
            try {
                rawPost(path, body, tok);
            } catch (Suite401Exception e) {
                tok = reAcquireToken(tok);
                rawPost(path, body, tok);
            }
        } catch (Exception e) {
            logger.warn("SuiteApiStitchClient: pushProperties failed for resource="
                    + resourceId + ": " + e.getMessage(), e);
        }
    }

    /**
     * Push numeric statistics onto a foreign resource.
     *
     * <p>Token lifecycle and error handling are identical to
     * {@link #pushProperties}.
     *
     * @param resourceId VCF Ops resource UUID
     * @param stats      map of statKey → double value; no-op if empty
     * @param timestamp  sample timestamp in epoch milliseconds
     */
    public void pushStats(String resourceId,
            Map<String, Double> stats,
            long timestamp) {
        if (stats == null || stats.isEmpty()) return;

        String body = buildStatsJson(stats, timestamp);
        String path = "/api/resources/" + resourceId + "/stats";
        try {
            String tok = ensureToken();
            try {
                rawPost(path, body, tok);
            } catch (Suite401Exception e) {
                tok = reAcquireToken(tok);
                rawPost(path, body, tok);
            }
        } catch (Exception e) {
            logger.warn("SuiteApiStitchClient: pushStats failed for resource="
                    + resourceId + ": " + e.getMessage(), e);
        }
    }

    /**
     * Perform an authenticated GET against the Suite API.
     *
     * <p>The cached bearer token is used. If the Suite API returns HTTP 401,
     * the token is re-acquired and the GET is retried exactly once.
     *
     * @param path path relative to the Suite API base (e.g.
     *             {@code "/api/resources?adapterKind=VMWARE"})
     * @return the response body as a string
     * @throws IOException          on HTTP or network error
     * @throws InterruptedException if the calling thread is interrupted
     */
    public String get(String path) throws IOException, InterruptedException {
        String tok = ensureToken();
        try {
            return rawGet(path, tok);
        } catch (Suite401Exception e) {
            tok = reAcquireToken(tok);
            return rawGet(path, tok);
        }
    }

    /**
     * Release the cached bearer token and underlying HTTP resources.
     *
     * <p>Call from the adapter's {@code onDiscard()} method, alongside
     * releasing the {@link com.vcfcf.adapter.http.ManagedHttpClient}.
     * Token release failure is swallowed and logged at WARN — the platform's
     * token TTL is the safety net (per spec §3 cancellation contract).
     */
    public void discard() {
        String tok;
        synchronized (tokenLock) {
            tok = this.cachedToken;
            this.cachedToken = null;
        }
        releaseToken(tok); // null-safe, swallows all exceptions
        // URLConnection connections are per-request; nothing else to close here.
    }

    // -----------------------------------------------------------------------
    // Token management (internal)
    // -----------------------------------------------------------------------

    /**
     * Return the cached bearer token, acquiring a new one lazily if absent.
     * Thread-safe: double-checked with {@link #tokenLock}.
     */
    private String ensureToken() throws IOException, InterruptedException {
        String tok = this.cachedToken;
        if (tok != null) return tok;
        synchronized (tokenLock) {
            tok = this.cachedToken;
            if (tok == null) {
                tok = acquireToken();
                this.cachedToken = tok;
            }
            return tok;
        }
    }

    /**
     * Invalidate the cached token (if it still matches {@code oldToken}) and
     * acquire a fresh one. Only re-acquires if not already refreshed by a
     * concurrent caller. Single retry on 401 per spec §1.
     */
    private String reAcquireToken(String oldToken) throws IOException, InterruptedException {
        synchronized (tokenLock) {
            if (oldToken != null && oldToken.equals(this.cachedToken)) {
                this.cachedToken = null;
            }
            String tok = this.cachedToken;
            if (tok == null) {
                tok = acquireToken();
                this.cachedToken = tok;
            }
            return tok;
        }
    }

    /**
     * POST to {@code /api/auth/token/acquire} and return the bearer token.
     */
    private String acquireToken() throws IOException, InterruptedException {
        String body = "{\"username\":" + jsonStr(resolvedUsername)
                + ",\"password\":" + jsonStr(resolvedPassword)
                + ",\"authSource\":" + jsonStr(AUTH_SOURCE) + "}";

        String responseBody = urlConnRequest("POST",
                suiteApiBase + "/api/auth/token/acquire", body, null);

        SimpleJson parsed = SimpleJson.parse(responseBody);
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
     * <p>Safe to call with a {@code null} token. All exceptions are swallowed
     * and logged at WARN — this is always called from {@link #discard()} and
     * must never mask the adapter lifecycle.
     */
    private void releaseToken(String token) {
        if (token == null) return;
        try {
            String body = "{\"token\":" + jsonStr(token) + "}";
            urlConnRequest("POST",
                    suiteApiBase + "/api/auth/token/release", body, null);
        } catch (Exception e) {
            logger.warn("SuiteApiStitchClient: token release failed (non-fatal): "
                    + e.getMessage());
        }
    }

    // -----------------------------------------------------------------------
    // Raw HTTP helpers — transport dispatch
    // -----------------------------------------------------------------------

    /**
     * POST {@code body} to {@code apiPath} with the given {@code opsToken}.
     *
     * @throws Suite401Exception on HTTP 401 (caller must single-retry)
     * @throws IOException       on other HTTP or network error
     */
    private void rawPost(String apiPath, String body, String opsToken)
            throws IOException, InterruptedException {
        urlConnRequest("POST", suiteApiBase + apiPath, body, opsToken);
    }

    /**
     * GET {@code apiPath} with the given {@code opsToken} and return the body.
     *
     * @throws Suite401Exception on HTTP 401 (caller must single-retry)
     * @throws IOException       on other HTTP or network error
     */
    private String rawGet(String apiPath, String opsToken)
            throws IOException, InterruptedException {
        return urlConnRequest("GET", suiteApiBase + apiPath, null, opsToken);
    }

    // -----------------------------------------------------------------------
    // URLConnection transport (loopback path)
    // -----------------------------------------------------------------------

    /**
     * Execute an HTTP request via the platform connection transport.
     *
     * <p>Opens the connection through
     * {@link VcfCfAdapter#openPlatformConnection(String)}, which mirrors the
     * vendor {@code SuiteAPIClient} non-FIPS transport (trust-all +
     * ignore-hostname) on the underlying {@code HttpsURLConnection}. Used for
     * all Suite API calls — both loopback (ambient) and explicit/remote
     * (collector) endpoints; per DEF-005 the transport no longer peer-gates
     * (see {@link VcfCfAdapter#openPlatformConnection(String)}).
     *
     * @param method   {@code "GET"} or {@code "POST"}
     * @param fullUrl  full URL including base (e.g.
     *                 {@code "https://localhost/suite-api/api/auth/token/acquire"})
     * @param body     request body for POST, or {@code null} for GET
     * @param opsToken {@code OpsToken} header value, or {@code null} to omit
     *                 the {@code Authorization} header (used for token acquire/release)
     * @return response body as String (empty string if the server sends no body)
     * @throws Suite401Exception on HTTP 401
     * @throws IOException       on other HTTP or connection error
     * @throws InterruptedException if the thread is interrupted before the call
     */
    private String urlConnRequest(String method, String fullUrl, String body, String opsToken)
            throws IOException, InterruptedException {
        if (Thread.currentThread().isInterrupted()) {
            throw new InterruptedException(
                    "SuiteApiStitchClient: thread interrupted before "
                    + method + " " + fullUrl);
        }
        java.net.URLConnection rawConn = adapter.openPlatformConnection(fullUrl);
        HttpURLConnection conn = (HttpURLConnection) rawConn;
        try {
            conn.setRequestMethod(method);
            conn.setConnectTimeout((int) REQUEST_TIMEOUT.toMillis());
            conn.setReadTimeout((int) REQUEST_TIMEOUT.toMillis());
            conn.setRequestProperty("Accept", "application/json");
            if (body != null) {
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json");
            }
            if (opsToken != null) {
                conn.setRequestProperty("Authorization", "OpsToken " + opsToken);
            }
            if (body != null) {
                byte[] bodyBytes = body.getBytes(StandardCharsets.UTF_8);
                try (OutputStream os = conn.getOutputStream()) {
                    os.write(bodyBytes);
                }
            }
            int status = conn.getResponseCode();
            if (status == 401) {
                throw new Suite401Exception(
                        "Suite API " + method + " " + fullUrl
                        + " returned 401 — token expired or credential invalid"
                        + " mechanism=" + mechanism
                        + " principal=" + resolvedUsername);
            }
            if (status < 200 || status >= 300) {
                throw new IOException(
                        "Suite API " + method + " " + fullUrl + " HTTP " + status);
            }
            // Read response body. Callers that do not need it ignore the return value.
            InputStream is = conn.getInputStream();
            if (is == null) return "";
            try (InputStreamReader reader =
                    new InputStreamReader(is, StandardCharsets.UTF_8)) {
                char[] buf = new char[8192];
                StringBuilder sb = new StringBuilder();
                int n;
                while ((n = reader.read(buf)) != -1) sb.append(buf, 0, n);
                return sb.toString();
            }
        } finally {
            conn.disconnect();
        }
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
     * Returns {@code "null"} for a null input.
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
