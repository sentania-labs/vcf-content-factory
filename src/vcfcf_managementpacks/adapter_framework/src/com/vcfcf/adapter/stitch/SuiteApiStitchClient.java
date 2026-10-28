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
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Framework-level Suite API REST transport for property/stats stitching.
 *
 * <p>Generalised from the compliance adapter's dead-code
 * {@code SuiteApiPropertyPusher}. All HTTP calls go through
 * {@link VcfCfAdapter#openPlatformConnection(String)} — an
 * {@code HttpsURLConnection} wired to mirror the vendor
 * {@code aria-ops-core SuiteAPIClient.getClientConfigBuilder()} transport
 * <strong>exactly</strong> (see
 * {@code knowledge/context/api-surface/casa-injected-vs-raw-client.md} §3): trust-all +
 * ignore-hostname in non-FIPS mode, chain verified against the cluster
 * truststore + ignore-hostname in FIPS mode (server-trust only: no client
 * keystore, no CaSA, no cert-renewal registration; see
 * {@link VcfCfAdapter#openPlatformConnection(String)}). This replaced an
 * earlier attempt to route the loopback hop through the platform's strict TOFU
 * {@code CustomTrustManager} (via {@code getSocketFactory()}), which PKIX-fails
 * every cycle on live devel because framework adapters declare no
 * cert-renewal URL set for the platform's non-disruptive certificate handler
 * to persist trust against — see
 * {@code knowledge/context/investigations/synology-b23-devel-pkix-2026-07-01.md} and
 * {@code knowledge/context/defects.md} DEF-005. It also eliminates the earlier
 * {@code java.net.http.HttpClient} + {@code insecureSslContext()} path, which
 * failed with {@code certificate_unknown(46)} on production appliances whose
 * operator-replaced cert has no {@code localhost} SAN (see §5 of
 * {@code specs/20-suiteapi-client-behavioral-contract.md}). At the time that
 * path was retired, {@code HttpClient} offered no way to inject a custom
 * {@code HostnameVerifier} at all, which read as a hard capability gap. Issue
 * #82's fix (reimplementing {@code insecureSslContext()}'s trust manager as
 * {@code X509ExtendedTrustManager}) has since closed that specific gap:
 * {@code insecureSslContext()} now suppresses hostname verification outright
 * on both transports, so an unconditional all-true verifier (which is all
 * the vendor-mirror posture below needs) is expressible over
 * {@code HttpClient} too. This class keeps {@code openPlatformConnection()} /
 * {@code HttpsURLConnection} anyway, not because of that now-closed gap, but
 * because it is the vendor-mirror transport (see the DEF-005 discussion
 * above): matching {@code aria-ops-core SuiteAPIClient} byte-for-byte was the
 * explicit goal, not inventing a new transport once one became technically
 * possible.
 *
 * <p>The credential mechanism still determines the Suite API endpoint:
 * <ul>
 *   <li><strong>Ambient</strong> — identity v3 order: the platform-injected
 *       per-instance credential ({@code adapter.getAdapterConfig()
 *       .getAdapterCredentials()}, when present), then
 *       {@code automationuser.properties} ({@code automationAdmin}), then
 *       {@code maintenanceuser.properties} only if both prior sources are
 *       absent/unreadable — see {@link AmbientCredential}; endpoint defaults
 *       to {@code https://localhost/suite-api/}.</li>
 *   <li><strong>Explicit</strong> — adapter-config host/username/password;
 *       endpoint is {@code https://<host>/suite-api/}. Same transport as
 *       ambient (no loopback/remote peer-gating since DEF-005; the hostname
 *       is ignored in both modes). Use on remote collectors where
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
 *       (see {@code knowledge/context/api-surface/
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
 * per-instance caching, single 401 retry, close-time release. A closed
 * client ({@link #close()} / {@link #discard()}) refuses every later call and
 * never acquires a new token (issue #217).
 *
 * <h3>Logging</h3>
 * <p>Credential values are never logged, and neither is the principal (the
 * Suite API account name; issue #227): log lines and exception messages name
 * only the mechanism chosen ({@code explicit} or {@code ambient}), the
 * credential source and the endpoint.
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
 * // Many resources per cycle (1.0.24): properties first, then stats, chunked.
 * SuiteApiBatchResult r = client.pushBatch(propsByUuid, statsByUuid, System.currentTimeMillis());
 * String body = client.get("/api/resources?adapterKind=VMWARE");
 * // Shared singleton parent: look it up every cycle (one local GET), never
 * // cache it across cycles. true from addChild means "accepted", not "linked".
 * String worldId = client.findSingletonResourceId("MyAdapterKind", "MyWorld");
 * if (worldId != null && client.addChild(worldId, foreignChildUuid)) {  // additive POST, never PUT
 *     logger.info("Link to MyWorld requested (accepted by Suite API)");
 * }
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

    /**
     * Read timeout for one batch request (connect stays 30 s). A batch carries
     * up to {@link #BATCH_MAX_BYTES_DEFAULT} of JSON, so it gets longer than a
     * per-id push. A timed-out batch is not re-sent: it may have been applied.
     */
    static final Duration BATCH_READ_TIMEOUT = Duration.ofSeconds(120);

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

    /**
     * Set by {@link #close()} (issue #217). Once set, no new token is ever
     * acquired: every call fails fast with {@link ClientClosedException}.
     * Written under {@link #tokenLock}; volatile for the lock-free fast path.
     */
    private volatile boolean closed = false;

    /** Guards the one WARN logged for calls refused after close. */
    private final java.util.concurrent.atomic.AtomicBoolean closedRefusalWarned =
            new java.util.concurrent.atomic.AtomicBoolean(false);

    /**
     * Operation and exception class pairs whose unexpected failure has
     * already been logged with its stack trace by this client (issue #192):
     * a repeat logs one line and keeps the trace at DEBUG. Per instance, never
     * static.
     */
    private final Set<String> tracedFailures =
            java.util.concurrent.ConcurrentHashMap.newKeySet();

    // -----------------------------------------------------------------------
    // Private exception — distinguishes 401 for the single-retry path
    // -----------------------------------------------------------------------

    /**
     * Thrown by {@code rawPost}/{@code rawGet} on HTTP 401 only. A
     * {@link SuiteApiHttpException}, so a 401 that survives the single retry
     * reaches {@link #get} callers with its status and body like any other.
     */
    private static final class Suite401Exception extends SuiteApiHttpException {
        private static final long serialVersionUID = 1L;

        Suite401Exception(String message, Integer apiErrorCode, String bodyExcerpt) {
            super(message, 401, apiErrorCode, bodyExcerpt);
        }
    }

    /** Accept header sent when the caller names none. */
    static final String DEFAULT_ACCEPT = "application/json";

    /** Most bytes of an error body read from the server (issue #201). */
    static final int ERROR_BODY_READ_MAX = 8192;

    /** Longest error body excerpt kept on a {@link SuiteApiHttpException}. */
    public static final int ERROR_BODY_EXCERPT_MAX = 512;

    /**
     * Thrown by every call on a closed client (issue #217). An
     * {@link IOException}, so {@link #get} callers that already catch
     * {@code IOException} treat it like an outage.
     */
    private static final class ClientClosedException extends IOException {
        private static final long serialVersionUID = 1L;

        ClientClosedException() {
            super("SuiteApiStitchClient is closed (discarded); a closed client never"
                    + " acquires a new token. Use the client built by the current"
                    + " configuration.");
        }
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
         * Logger for operational messages. Never logs credential values or
         * the principal (account name): only the mechanism, the credential
         * source and the endpoint are logged.
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
                            + "See knowledge/context/investigations/"
                            + "suiteapi_ambient_auth_devel_2026_06_09.md (Caveats).",
                            e);
                }
                username = cred.getUsername();
                password = cred.getPassword();
                suiteApiBase = DEFAULT_SUITE_API_BASE;
                mechanism = "ambient";
                logger.info("SuiteApiStitchClient: credential mechanism=ambient"
                        + " file=" + cred.getSourceLabel()
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
            // it mirrors the vendor aria-ops-core SuiteAPIClient posture
            // (trust-all + ignore-hostname, or cluster truststore +
            // ignore-hostname when IS_FIPS=true) for loopback and remote
            // Suite API endpoints alike, exactly as every shipping Broadcom
            // pak does. openPlatformConnection() logs the mode it selected.
            boolean loopback = SuiteApiStitchClient.isLoopbackUrl(suiteApiBase);
            logger.info("SuiteApiStitchClient: transport=openPlatformConnection"
                    + (loopback ? " loopback" : " remote")
                    + " (BC-mirror; FIPS or non-FIPS mode logged by openPlatformConnection)"
                    + " mechanism=" + mechanism);

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
     * are logged at WARN and swallowed, because a stitching failure must not
     * abort the adapter's primary collect cycle. The push repeats every
     * cycle, so a failure is one WARN line per call with the stack trace at
     * DEBUG (an unexpected exception class shows its trace at WARN the first
     * time only; see {@link #logFailure}). An interrupt restores the thread's
     * interrupt flag.
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
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            logFailure("pushProperties", "SuiteApiStitchClient: pushProperties failed for"
                    + " resource=" + loggable(resourceId), e);
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
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            logFailure("pushStats", "SuiteApiStitchClient: pushStats failed for"
                    + " resource=" + loggable(resourceId), e);
        }
    }

    // -----------------------------------------------------------------------
    // Batch stitching API (buildkit 1.0.24, compliance#17)
    // -----------------------------------------------------------------------

    /** Default most resources in one batch request. */
    public static final int BATCH_MAX_RESOURCES_DEFAULT = 100;

    /**
     * Default most bytes of JSON (UTF-8) in one batch request, about 1 MB. No
     * spec on any line documents a limit; this is a conservative cap, not a
     * measured one.
     */
    public static final int BATCH_MAX_BYTES_DEFAULT = 1_000_000;

    /** Bulk stats endpoint. Never the {@code /adapterkinds/{kind}} variant. */
    static final String STATS_BATCH_PATH = "/api/resources/stats";

    /** Bulk properties endpoint. Never the {@code /adapterkinds/{kind}} variant. */
    static final String PROPERTIES_BATCH_PATH = "/api/resources/properties";

    /** Opening of the stats batch body; entries follow, then {@code "]}"}. */
    static final String STATS_BATCH_PREFIX = "{\"resource-stat-content\":[";

    /** Opening of the properties batch body; entries follow, then {@code "]}"}. */
    static final String PROPERTIES_BATCH_PREFIX = "{\"values\":[";

    /** Resource ids named in the WARN for a failed batch or skipped ids. */
    static final int BATCH_FAILURE_IDS_LOGGED = 3;

    /**
     * Push string properties onto many foreign resources with the default caps
     * ({@link #BATCH_MAX_RESOURCES_DEFAULT} resources and
     * {@link #BATCH_MAX_BYTES_DEFAULT} bytes per request). Full contract:
     * {@link #pushPropertiesBatch(Map, long, int, int)}.
     *
     * @param byResource resource UUID to (statKey to string value)
     * @param timestamp  sample timestamp in epoch milliseconds, for every value
     * @return what was sent; never {@code null}
     */
    public SuiteApiBatchResult pushPropertiesBatch(
            Map<String, ? extends Map<String, String>> byResource, long timestamp) {
        return pushPropertiesBatch(byResource, timestamp,
                BATCH_MAX_RESOURCES_DEFAULT, BATCH_MAX_BYTES_DEFAULT);
    }

    /**
     * Push string properties onto many foreign resources:
     * {@code POST /api/resources/properties} with body
     * {@code {"values":[{"resourceId":<uuid>,"property-contents":{"property-content":[...]}}]}}
     * ({@code knowledge/context/api-surface/suite_api_batch_push.md}). The wire
     * shape comes from the spec and the vendor examples on 8.18, 9.0 and 9.1;
     * stats landing is proven live on 8.18.7, properties landing and 9.0 / 9.1
     * landing are not yet. Never the {@code /adapterkinds/{adapterKind}}
     * variant, which wants an OPENAPI adapter kind and creates one when the
     * kind is absent.
     *
     * <p><strong>A 2xx does not mean every id landed.</strong> The Suite API
     * answers 200 with no body and drops an id that matches no resource
     * silently while the rest of the batch lands (live on 8.18.7). A stale id
     * is therefore never reported here, and the per-id fallback does not
     * catch it either. Catch stale ids where they are resolved, in the
     * adapter's {@link ForeignResourceResolver} refresh.
     *
     * <p><strong>Chunking.</strong> Resources are serialized one at a time, in
     * caller order, and packed into requests of at most {@code maxResources}
     * resources and {@code maxBytes} bytes of JSON, whichever comes first; a
     * request is sent as soon as the next resource would not fit, so at most
     * one request's JSON plus one resource's is held at a time. A single resource larger than
     * {@code maxBytes} is sent alone. A cap below 1 falls back to its default
     * with a WARN.
     *
     * <p><strong>Ids and values.</strong> Ids go into the body, so each is
     * checked with the same UUID test as {@link #addChildren}: a non-UUID id
     * is skipped (one WARN per call naming the count and the first few). Ids
     * are trimmed and lowercased; two keys naming the same UUID are merged,
     * the later value winning per statKey. A resource with an empty or
     * {@code null} map is skipped silently and not counted. Entries with a
     * {@code null} key or value are dropped (counted in
     * {@link SuiteApiBatchResult#getDropped()}, one WARN per call). Control
     * characters are escaped, so no value can make a body invalid JSON.
     *
     * <p><strong>Failures.</strong> Never throws; the collect cycle never sees
     * an exception. The token is obtained before each request: if it cannot
     * be (token endpoint failure, closed client), the call stops before
     * sending, with the rest counted as skipped. A 401 on a batch is
     * re-acquired and retried once, as everywhere in this client. What
     * happens to a failed batch depends on the answer:
     * <ul>
     *   <li>4xx other than 401 and 429 (400, 413, 422...): likely one bad
     *       entry, so one WARN naming the count and the first ids, then each
     *       resource of that batch is re-sent once on the per-id path, which
     *       isolates it. Each per-id failure logs its own WARN.</li>
     *   <li>5xx, 429, a 401 that survives the retry, a failure with no HTTP
     *       status (timeout, refused connection: the batch may have been
     *       applied), an interrupt (flag restored) or a closed client: one
     *       WARN, nothing re-sent, and the call stops; every resource not
     *       delivered counts as skipped. A struggling server gets no more
     *       requests from this call.</li>
     * </ul>
     * The per-id fallback stops on the same conditions. Nothing is retried
     * blindly.
     *
     * @param byResource   resource UUID to (statKey to string value); no-op if
     *                     {@code null} or empty
     * @param timestamp    sample timestamp in epoch milliseconds, for every value
     * @param maxResources most resources per request
     * @param maxBytes     most bytes of JSON (UTF-8) per request
     * @return what was sent; never {@code null}
     */
    public SuiteApiBatchResult pushPropertiesBatch(
            Map<String, ? extends Map<String, String>> byResource, long timestamp,
            int maxResources, int maxBytes) {
        return pushBatchOf(false, byResource, timestamp, maxResources, maxBytes, false);
    }

    /**
     * Push numeric stats onto many foreign resources with the default caps.
     * Full contract: {@link #pushStatsBatch(Map, long, int, int)}.
     *
     * @param byResource resource UUID to (statKey to double value)
     * @param timestamp  sample timestamp in epoch milliseconds, for every value
     * @return what was sent; never {@code null}
     */
    public SuiteApiBatchResult pushStatsBatch(
            Map<String, ? extends Map<String, Double>> byResource, long timestamp) {
        return pushStatsBatch(byResource, timestamp,
                BATCH_MAX_RESOURCES_DEFAULT, BATCH_MAX_BYTES_DEFAULT);
    }

    /**
     * Push numeric stats onto many foreign resources:
     * {@code POST /api/resources/stats} with body
     * {@code {"resource-stat-content":[{"id":<uuid>,"stat-contents":[...]}]}}.
     * Note the asymmetries with the properties batch: the entry key is
     * {@code id} (not {@code resourceId}) and {@code stat-contents} is a bare
     * array (not an object wrapping one). {@code disableAnalyticsProcessing}
     * is never sent, so it stays at its default {@code false}: with
     * {@code true} the data is stored but no alert is evaluated on it.
     *
     * <p>Everything else, the 2xx-is-not-landed caveat and the failure rules
     * included, matches {@link #pushPropertiesBatch(Map, long, int, int)}. A
     * {@code null}, NaN or infinite value is dropped like a {@code null} key
     * (it would make the whole body invalid JSON).
     *
     * @param byResource   resource UUID to (statKey to double value); no-op if
     *                     {@code null} or empty
     * @param timestamp    sample timestamp in epoch milliseconds, for every value
     * @param maxResources most resources per request
     * @param maxBytes     most bytes of JSON (UTF-8) per request
     * @return what was sent; never {@code null}
     */
    public SuiteApiBatchResult pushStatsBatch(
            Map<String, ? extends Map<String, Double>> byResource, long timestamp,
            int maxResources, int maxBytes) {
        return pushBatchOf(true, byResource, timestamp, maxResources, maxBytes, false);
    }

    /**
     * Push properties, then stats, for many resources with the default caps.
     * Full contract: {@link #pushBatch(Map, Map, long, int, int)}.
     *
     * @param propertiesByResource resource UUID to (statKey to string value)
     * @param statsByResource      resource UUID to (statKey to double value)
     * @param timestamp            sample timestamp in epoch milliseconds
     * @return the two calls' results summed; never {@code null}
     */
    public SuiteApiBatchResult pushBatch(
            Map<String, ? extends Map<String, String>> propertiesByResource,
            Map<String, ? extends Map<String, Double>> statsByResource,
            long timestamp) {
        return pushBatch(propertiesByResource, statsByResource, timestamp,
                BATCH_MAX_RESOURCES_DEFAULT, BATCH_MAX_BYTES_DEFAULT);
    }

    /**
     * Push properties, then stats: {@link #pushPropertiesBatch} runs to
     * completion (fallback included) before {@link #pushStatsBatch} starts, so
     * an adapter gets the properties-first order its per-object pushes gave
     * it. The Suite API has no request that carries both. If the properties
     * call stopped ({@link SuiteApiBatchResult#isStopped()}: token failure,
     * 5xx, 429, persistent 401, no HTTP status, interrupt, closed client), the
     * stats call sends nothing and its resources count as skipped.
     *
     * @param propertiesByResource resource UUID to (statKey to string value)
     * @param statsByResource      resource UUID to (statKey to double value)
     * @param timestamp            sample timestamp in epoch milliseconds
     * @param maxResources         most resources per request
     * @param maxBytes             most bytes of JSON (UTF-8) per request
     * @return the two calls' results summed (a resource in both counts twice);
     *         never {@code null}
     */
    public SuiteApiBatchResult pushBatch(
            Map<String, ? extends Map<String, String>> propertiesByResource,
            Map<String, ? extends Map<String, Double>> statsByResource,
            long timestamp, int maxResources, int maxBytes) {
        SuiteApiBatchResult props = pushBatchOf(false, propertiesByResource, timestamp,
                maxResources, maxBytes, false);
        return props.plus(pushBatchOf(true, statsByResource, timestamp,
                maxResources, maxBytes, props.isStopped()));
    }

    /** One resource of a batch chunk: its id, its serialized entry, its values. */
    static final class BatchEntry {
        final String id;
        final String json;
        final int bytes;
        /** The merged (unfiltered) values; re-cleaned only for a per-id re-send. */
        final Map<String, ?> values;

        BatchEntry(String id, String json, Map<String, ?> values) {
            this.id = id;
            this.json = json;
            this.bytes = json.getBytes(StandardCharsets.UTF_8).length;
            this.values = values;
        }
    }

    /**
     * Test seam only: called with each resource id just before its batch
     * entry is serialized, so a test can see that a chunk is sent before the
     * next resource is serialized. {@code null} (no-op) in production.
     */
    volatile java.util.function.Consumer<String> serializeHook;

    /** Mutable counters for one batch call. */
    private static final class BatchRun {
        int sent;
        int ok;
        int failed;
        int fellBack;
        int skipped;
        int dropped;
        /** Resources of the merged map whose fate is counted. */
        int handled;
        boolean stopped;

        SuiteApiBatchResult result() {
            return new SuiteApiBatchResult(sent, ok, failed, fellBack, skipped, dropped, stopped);
        }
    }

    /**
     * Thrown by {@link #postWithToken} when a 401 was answered and getting a
     * fresh token then failed: the request was sent, the retry could not be.
     */
    private static final class TokenRetryException extends IOException {
        private static final long serialVersionUID = 1L;

        TokenRetryException(Exception cause) {
            super(cause.getMessage(), cause);
        }
    }

    /** Outcome of one per-id re-send. */
    private enum PerIdOutcome { OK, REJECTED, NOT_SENT, STOP }

    /**
     * Shared body of the batch methods. Never throws.
     *
     * @param stats   {@code true} for stats, {@code false} for properties
     * @param skipAll send nothing; count every resource as skipped (the
     *                stats half of a {@link #pushBatch} whose properties half
     *                stopped)
     */
    private SuiteApiBatchResult pushBatchOf(boolean stats,
            Map<String, ? extends Map<String, ?>> byResource, long timestamp,
            int maxResources, int maxBytes, boolean skipAll) {
        String op = stats ? "pushStatsBatch" : "pushPropertiesBatch";
        BatchRun run = new BatchRun();
        run.stopped = skipAll;
        Map<String, Map<String, Object>> merged = null;
        try {
            if (byResource == null || byResource.isEmpty()) return run.result();
            int maxRes = maxResources;
            if (maxRes < 1) {
                logger.warn("SuiteApiStitchClient: " + op + " maxResources " + maxResources
                        + " is below 1; using " + BATCH_MAX_RESOURCES_DEFAULT);
                maxRes = BATCH_MAX_RESOURCES_DEFAULT;
            }
            int maxB = maxBytes;
            if (maxB < 1) {
                logger.warn("SuiteApiStitchClient: " + op + " maxBytes " + maxBytes
                        + " is below 1; using " + BATCH_MAX_BYTES_DEFAULT);
                maxB = BATCH_MAX_BYTES_DEFAULT;
            }

            // Validate ids and merge keys naming the same UUID. The caller's
            // map is read inside the guard: a concurrent modification of it
            // must not throw into the collect cycle. The copy holds the
            // caller's value references only, never JSON.
            Map<String, Map<String, Object>> m = new LinkedHashMap<>();
            int badIds = 0;
            List<String> badIdSamples = new ArrayList<>();
            for (Map.Entry<String, ? extends Map<String, ?>> r : byResource.entrySet()) {
                String id = r.getKey();
                if (!isUuid(id)) {
                    badIds++;
                    if (badIdSamples.size() < BATCH_FAILURE_IDS_LOGGED) {
                        badIdSamples.add(loggable(id));
                    }
                    continue;
                }
                Map<String, ?> values = r.getValue();
                if (values == null || values.isEmpty()) continue;
                m.computeIfAbsent(normalizeUuid(id), k -> new LinkedHashMap<>())
                        .putAll(values);
            }
            merged = m;
            if (badIds > 0) {
                run.skipped += badIds;
                logger.warn("SuiteApiStitchClient: " + op + " skipped " + badIds
                        + " resource id(s) that are not UUIDs, e.g. " + badIdSamples);
            }

            // Serialize one resource at a time and send a chunk as soon as
            // the next resource would not fit: at most one chunk's JSON plus
            // one entry is held at once.
            String path = stats ? STATS_BATCH_PATH : PROPERTIES_BATCH_PATH;
            String prefix = stats ? STATS_BATCH_PREFIX : PROPERTIES_BATCH_PREFIX;
            long emptyBytes = prefix.getBytes(StandardCharsets.UTF_8).length + 2L;
            List<BatchEntry> chunk = new ArrayList<>();
            long chunkBytes = emptyBytes;
            for (Map.Entry<String, Map<String, Object>> r : merged.entrySet()) {
                Map<String, Object> clean = cleanValues(stats, r.getValue(), run);
                if (clean.isEmpty() || run.stopped) {
                    run.skipped++;
                    run.handled++;
                    continue;
                }
                java.util.function.Consumer<String> hook = serializeHook;
                if (hook != null) hook.accept(r.getKey());
                BatchEntry be = new BatchEntry(r.getKey(), stats
                        ? statsBatchEntry(r.getKey(), castStats(clean), timestamp)
                        : propertiesBatchEntry(r.getKey(), castProps(clean), timestamp),
                        r.getValue());
                if (!chunk.isEmpty() && !fits(chunk.size(), chunkBytes, be.bytes, maxRes, maxB)) {
                    sendChunk(stats, op, path, prefix, chunk, timestamp, run);
                    chunk = new ArrayList<>();
                    chunkBytes = emptyBytes;
                    if (run.stopped) {
                        run.skipped++;
                        run.handled++;
                        continue;
                    }
                }
                chunkBytes += (chunk.isEmpty() ? 0 : 1) + be.bytes;
                chunk.add(be);
            }
            if (!chunk.isEmpty()) sendChunk(stats, op, path, prefix, chunk, timestamp, run);
            if (run.dropped > 0) {
                logger.warn("SuiteApiStitchClient: " + op + " dropped " + run.dropped
                        + " entr" + (run.dropped == 1 ? "y" : "ies") + " with a null key or a "
                        + (stats ? "null, NaN or infinite" : "null") + " value");
            }
            SuiteApiBatchResult result = run.result();
            if (logger.isDebugEnabled()) {
                logger.debug("SuiteApiStitchClient: " + op + (skipAll
                        ? " not sent (the properties call stopped) " : " ") + result);
            }
            return result;
        } catch (Exception e) {
            // Unexpected (a malformed caller map, a concurrent modification):
            // never into the collect cycle. Whatever was not counted yet was
            // not delivered.
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            logFailure(op, "SuiteApiStitchClient: " + op + " failed", e);
            if (merged != null) run.skipped += Math.max(0, merged.size() - run.handled);
            run.stopped = true;
            return run.result();
        }
    }

    /**
     * Send one chunk and settle every one of its resources in {@code run}:
     * sent, re-sent per id, or skipped. Sets {@code run.stopped} when the
     * rest of the call must not be sent.
     */
    private void sendChunk(boolean stats, String op, String path, String prefix,
            List<BatchEntry> chunk, long timestamp, BatchRun run) {
        int n = chunk.size();
        run.handled += n;
        if (Thread.currentThread().isInterrupted()) {
            run.stopped = true;
            run.skipped += n;
            logger.warn("SuiteApiStitchClient: " + op + " stopped (thread interrupted);"
                    + " the rest of this call is not sent");
            return;
        }
        String tok;
        try {
            tok = ensureToken();
        } catch (Exception e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            run.stopped = true;
            run.skipped += n;
            logFailure(op, "SuiteApiStitchClient: " + op + " has no Suite API token, nothing"
                    + " sent; the rest of this call is not sent", e);
            return;
        }
        String body = batchBody(prefix, chunk);
        run.sent += n;
        Exception err;
        try {
            postWithToken(path, body, tok, BATCH_READ_TIMEOUT);
            run.ok++;
            return;
        } catch (Exception e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            err = e;
        }
        body = null; // not needed for the fallback
        run.failed++;
        Exception cause = err instanceof TokenRetryException ? (Exception) err.getCause() : err;
        String first = "SuiteApiStitchClient: " + op + " batch of " + n
                + " resource(s) failed, first ids " + firstIds(chunk);
        if (!isolatable(err)) {
            run.stopped = true;
            run.skipped += n;
            logFailure(op, first + "; " + stopReason(err)
                    + "; not re-sent, the rest of this call is not sent", cause);
            return;
        }
        logFailure(op, first + "; re-sending each of them on the per-id path to isolate"
                + " the rejected entry", cause);
        for (int i = 0; i < n; i++) {
            if (Thread.currentThread().isInterrupted()) {
                run.stopped = true;
                run.skipped += n - i;
                return;
            }
            PerIdOutcome o = pushOnePerId(stats, chunk.get(i), timestamp);
            if (o == PerIdOutcome.NOT_SENT) {
                run.stopped = true;
                run.skipped += n - i;
                return;
            }
            run.fellBack++;
            if (o == PerIdOutcome.STOP) {
                run.stopped = true;
                run.skipped += n - i - 1;
                return;
            }
        }
    }

    /**
     * True for a batch answer the per-id path can isolate: a 4xx other than
     * 401 (credential) and 429 (rate limit), most likely one bad entry.
     * Everything else (5xx, 429, a persistent 401, no HTTP status, interrupt,
     * closed client, token failure) stops the call.
     */
    private static boolean isolatable(Exception e) {
        if (!(e instanceof SuiteApiHttpException)) return false;
        int s = ((SuiteApiHttpException) e).getStatusCode();
        return s >= 400 && s < 500 && s != 401 && s != 429;
    }

    /** Why a failed batch stops the call, for its WARN line. */
    private static String stopReason(Exception e) {
        if (e instanceof TokenRetryException) return "401, then no new token";
        if (e instanceof InterruptedException) return "interrupted";
        if (e instanceof ClientClosedException) return "client closed";
        if (e instanceof SuiteApiHttpException) {
            int s = ((SuiteApiHttpException) e).getStatusCode();
            if (s == 401) return "401 after the token retry";
            if (s == 429) return "rate limited (429)";
            return "server error (HTTP " + s + ")";
        }
        return "no HTTP status (it may have been applied)";
    }

    /**
     * Re-send one resource of a failed batch on the per-id path; logs its own
     * failure. {@code NOT_SENT}: no token, nothing sent. {@code STOP}: sent
     * and failed in a way that stops the call. {@code REJECTED}: sent and
     * refused with an isolatable 4xx. Restores the interrupt flag.
     */
    private PerIdOutcome pushOnePerId(boolean stats, BatchEntry be, long timestamp) {
        String op = stats ? "pushStats" : "pushProperties";
        String ctx = "SuiteApiStitchClient: " + op + " (batch fallback) failed for resource="
                + be.id;
        String tok;
        try {
            tok = ensureToken();
        } catch (Exception e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            logFailure(op, ctx + " (no Suite API token, nothing sent)", e);
            return PerIdOutcome.NOT_SENT;
        }
        Map<String, Object> clean = cleanValues(stats, be.values, null);
        String path = "/api/resources/" + be.id + (stats ? "/stats" : "/properties");
        String body = stats ? buildStatsJson(castStats(clean), timestamp)
                : buildPropertiesJson(castProps(clean), timestamp);
        try {
            postWithToken(path, body, tok, REQUEST_TIMEOUT);
            return PerIdOutcome.OK;
        } catch (Exception e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            Exception cause = e instanceof TokenRetryException ? (Exception) e.getCause() : e;
            logFailure(op, ctx, cause);
            return isolatable(e) ? PerIdOutcome.REJECTED : PerIdOutcome.STOP;
        }
    }

    /**
     * POST with a token already in hand; on 401 re-acquire and retry exactly
     * once. A failure to re-acquire is a {@link TokenRetryException}.
     */
    private void postWithToken(String path, String body, String tok, Duration readTimeout)
            throws IOException, InterruptedException {
        try {
            urlConnRequest("POST", suiteApiBase + path, body, tok, DEFAULT_ACCEPT, readTimeout);
        } catch (Suite401Exception e) {
            String fresh;
            try {
                fresh = reAcquireToken(tok);
            } catch (InterruptedException ie) {
                throw ie;
            } catch (Exception te) {
                throw new TokenRetryException(te);
            }
            urlConnRequest("POST", suiteApiBase + path, body, fresh, DEFAULT_ACCEPT, readTimeout);
        }
    }

    /**
     * The entries of {@code values} that can go into a body: a non-null key
     * and a finite {@link Double} (stats) or non-null {@link String}
     * (properties). Counts the rest in {@code run.dropped} when {@code run}
     * is not null.
     */
    private static Map<String, Object> cleanValues(boolean stats, Map<String, ?> values,
            BatchRun run) {
        Map<String, Object> clean = new LinkedHashMap<>();
        for (Map.Entry<String, ?> e : values.entrySet()) {
            if (e.getKey() != null && isSendable(stats, e.getValue())) {
                clean.put(e.getKey(), e.getValue());
            } else if (run != null) {
                run.dropped++;
            }
        }
        return clean;
    }

    /**
     * True if a value can go into a batch body: a finite {@link Double} for
     * stats, a non-null {@link String} for properties.
     */
    private static boolean isSendable(boolean stats, Object v) {
        if (stats) {
            return v instanceof Double && !((Double) v).isNaN() && !((Double) v).isInfinite();
        }
        return v instanceof String;
    }

    /** Values were checked by {@link #isSendable}; the cast is safe. */
    @SuppressWarnings("unchecked")
    private static Map<String, Double> castStats(Map<String, ?> m) {
        return (Map<String, Double>) m;
    }

    /** Values were checked by {@link #isSendable}; the cast is safe. */
    @SuppressWarnings("unchecked")
    private static Map<String, String> castProps(Map<String, ?> m) {
        return (Map<String, String>) m;
    }

    /** The first {@link #BATCH_FAILURE_IDS_LOGGED} ids of a chunk, for a WARN. */
    private static List<String> firstIds(List<BatchEntry> chunk) {
        List<String> ids = new ArrayList<>();
        for (BatchEntry be : chunk) {
            if (ids.size() >= BATCH_FAILURE_IDS_LOGGED) break;
            ids.add(be.id);
        }
        return ids;
    }

    /**
     * One stats batch entry: {@code {"id":<uuid>,"stat-contents":[...]}}, the
     * {@code stat-contents} a bare array. Visible to tests.
     */
    static String statsBatchEntry(String resourceId, Map<String, Double> stats,
            long timestamp) {
        return "{\"id\":" + jsonStr(resourceId) + ",\"stat-contents\":"
                + statContentArray(stats, timestamp) + "}";
    }

    /**
     * One properties batch entry:
     * {@code {"resourceId":<uuid>,"property-contents":{"property-content":[...]}}},
     * the {@code property-contents} an object wrapping the array (the per-id
     * body nested unchanged). Visible to tests.
     */
    static String propertiesBatchEntry(String resourceId, Map<String, String> properties,
            long timestamp) {
        return "{\"resourceId\":" + jsonStr(resourceId) + ",\"property-contents\":"
                + buildPropertiesJson(properties, timestamp) + "}";
    }

    /** {@code prefix}, the entries joined by {@code ","}, then {@code "]}"}. */
    static String batchBody(String prefix, List<BatchEntry> chunk) {
        StringBuilder sb = new StringBuilder(prefix);
        boolean first = true;
        for (BatchEntry be : chunk) {
            if (!first) sb.append(",");
            first = false;
            sb.append(be.json);
        }
        return sb.append("]}").toString();
    }

    /**
     * True if one more entry of {@code entryBytes} fits a non-empty chunk of
     * {@code count} entries whose body (prefix, entries, commas and the
     * closing {@code "]}"}) is {@code bodyBytes} long. The one packing rule,
     * shared by the send loop and {@link #chunk}.
     */
    static boolean fits(int count, long bodyBytes, int entryBytes, int maxResources,
            int maxBytes) {
        return count < maxResources && bodyBytes + 1 + entryBytes <= maxBytes;
    }

    /**
     * Pack serialized entries, in order, with the rule in {@link #fits}; an
     * entry that alone exceeds {@code maxBytes} gets a chunk of its own. The
     * send loop applies the same rule one entry at a time; this whole-list
     * form is for tests.
     */
    static List<List<BatchEntry>> chunk(List<BatchEntry> entries, int prefixBytes,
            int maxResources, int maxBytes) {
        List<List<BatchEntry>> chunks = new ArrayList<>();
        List<BatchEntry> cur = new ArrayList<>();
        long curBytes = prefixBytes + 2L;
        for (BatchEntry be : entries) {
            if (!cur.isEmpty() && !fits(cur.size(), curBytes, be.bytes, maxResources, maxBytes)) {
                chunks.add(cur);
                cur = new ArrayList<>();
                curBytes = prefixBytes + 2L;
            }
            curBytes += (cur.isEmpty() ? 0 : 1) + be.bytes;
            cur.add(be);
        }
        if (!cur.isEmpty()) chunks.add(cur);
        return chunks;
    }

    /**
     * Add one child to an existing resource through the Suite API, additively.
     *
     * <p>Convenience for {@link #addChildren(String, Collection)} with a single
     * child; same contract.
     *
     * @param parentResourceId Suite API resource UUID of the parent
     * @param childResourceId  Suite API resource UUID of the child
     * @return {@code true} if the Suite API accepted the request (2xx), which
     *         means "request accepted", not "linked" (the add is asynchronous;
     *         log it that way)
     */
    public boolean addChild(String parentResourceId, String childResourceId) {
        List<String> one = new ArrayList<>(1);
        one.add(childResourceId);
        return addChildren(parentResourceId, one);
    }

    /**
     * Add children to an existing resource through the Suite API, additively:
     * {@code POST /api/resources/{parentResourceId}/relationships/children}
     * with body {@code {"uuids":["<childId>", ...]}} (operation
     * {@code addRelationship}; identical path, verb and {@code uuid-values}
     * body in the 9.0 and 9.1 operations-api specs).
     *
     * <p><strong>Why POST and never PUT.</strong> {@code PUT} on the same path
     * ({@code setRelationship}) has replace semantics: it removes every
     * existing child of the parent and substitutes the request body. When the
     * parent is shared by several adapter instances (for example one
     * pak-level singleton that every instance links its own vCenter to), each
     * instance's PUT would wipe the children the other instances added, and
     * the last instance to collect would win. {@code POST} only adds, so each
     * instance asserts its own link without disturbing anyone else's. This
     * class deliberately exposes no PUT/replace variant.
     *
     * <p><strong>Asynchronous.</strong> The spec states the add is not
     * synchronous: a 2xx means the request was accepted, and the edge may
     * appear a little later. Read the parent's relationships back
     * ({@code GET /api/resources/{id}/relationships/children}) to confirm.
     *
     * <p><strong>Re-asserting is the intended usage.</strong> Call it every
     * collect cycle; an edge is a (parent, child) pair, so a repeat add of an
     * existing child has nothing to add. The spec does not state repeat-add
     * behaviour in words, so the first live use should confirm one edge
     * remains after several cycles. Per the spec, children that would form a
     * cycle are skipped, and the call returns 404 only when every UUID in the
     * body is invalid or missing (logged at WARN here like any non-2xx).
     *
     * <p><strong>Not the SDK route.</strong> For edges the adapter reports in
     * its own collect result, use {@link RelationshipBuilder}, whose
     * own-parent emission is {@code setRelationships} (full set per parent).
     * Use this method when the parent is shared across adapter instances and
     * a per-instance full set would be last-writer-wins.
     *
     * <p>Token lifecycle, transport and error posture match
     * {@link #pushStats}: cached token, one re-acquire and retry on HTTP 401,
     * every failure logged at WARN and swallowed so the collect cycle never
     * sees an exception. An expected failure (an {@link IOException} such as
     * a non-2xx status, timeout or refused connection, or an interrupt) is
     * one WARN line without a stack trace, with the trace at DEBUG; any other
     * exception class shows its stack trace at WARN the first time this
     * client sees it for this operation, then logs like an expected one (see
     * {@link #logFailure}).
     * Blank or non-UUID ids are skipped with a WARN (the ids go into the
     * request path and body, so they are validated rather than escaped; a
     * rejected id is logged truncated and with control characters
     * stripped). Ids are trimmed and lowercased, then duplicate
     * child ids are collapsed (the body schema declares {@code uniqueItems}),
     * and a child equal to the parent is skipped with a WARN (a self-edge
     * would be a cycle, which the server skips anyway). The caller's
     * collection is read inside the failure guard, so even a concurrent
     * modification of it is logged and returned as {@code false}.
     *
     * <p><strong>Known limitation: nothing removes these edges.</strong> An
     * edge added here persists until something deletes it with
     * {@code DELETE /api/resources/{parentResourceId}/relationships/children/{childId}}
     * (operation {@code deleteRelationship}, asynchronous, 204/404, same in
     * the 9.0 and 9.1 specs). The framework does not wrap that call today.
     * So a child that drops out of an adapter instance's scope (for example
     * a vCenter removed from the instance's configuration) stays a child of
     * the shared parent, and any roll-up over the parent's children keeps
     * counting it. A pak whose scope can shrink owns that cleanup, or records
     * the stale edge as a known limitation in its design.
     *
     * @param parentResourceId Suite API resource UUID of the parent
     * @param childResourceIds Suite API resource UUIDs of the children; no-op
     *                         if null, empty, or no valid id remains
     * @return {@code true} if the Suite API accepted the request (2xx), which
     *         means "request accepted", not "linked" (the add is asynchronous;
     *         log it that way); {@code false} if nothing was sent or the
     *         request failed
     */
    public boolean addChildren(String parentResourceId,
            Collection<String> childResourceIds) {
        if (!isUuid(parentResourceId)) {
            logger.warn("SuiteApiStitchClient: addChildren skipped, parent resource id"
                    + " is not a UUID: " + loggable(parentResourceId));
            return false;
        }
        String parent = normalizeUuid(parentResourceId);
        Set<String> children = new LinkedHashSet<>();
        try {
            // Read the caller's collection inside the guard: a concurrent
            // modification must not throw into the collect cycle.
            if (childResourceIds != null) {
                for (String id : childResourceIds) {
                    if (!isUuid(id)) {
                        logger.warn("SuiteApiStitchClient: addChildren skipping child id"
                                + " that is not a UUID: " + loggable(id) + " (parent="
                                + parent + ")");
                        continue;
                    }
                    String child = normalizeUuid(id);
                    if (child.equals(parent)) {
                        logger.warn("SuiteApiStitchClient: addChildren skipping child id"
                                + " equal to its parent (self-edge): " + parent);
                        continue;
                    }
                    children.add(child);
                }
            }
            if (children.isEmpty()) return false;

            String path = childrenRelationshipPath(parent);
            String body = buildUuidValuesJson(children);
            String tok = ensureToken();
            try {
                rawPost(path, body, tok);
            } catch (Suite401Exception e) {
                tok = reAcquireToken(tok);
                rawPost(path, body, tok);
            }
            return true;
        } catch (Exception e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            logFailure("addChildren", "SuiteApiStitchClient: addChildren failed for parent="
                    + parent + " children=" + children, e);
            return false;
        }
    }

    /**
     * Look up the Suite API resource UUID of the one resource of a kind,
     * typically the adapter's own singleton (for example a pak-level "World"
     * object every adapter instance registers with the same identifiers).
     *
     * <p>Issues {@code GET /api/resources?adapterKind=<a>&resourceKind=<r>}
     * (kinds trimmed) and keeps only entries whose
     * {@code resourceKey.adapterKindKey} and {@code resourceKey.resourceKindKey}
     * equal the trimmed arguments exactly and whose {@code identifier} is a
     * UUID (returned lowercase).
     *
     * <ul>
     *   <li>Exactly one match: returns its {@code identifier}.</li>
     *   <li>No match: logs at WARN and returns {@code null}. Expected on the
     *       very first cycle, before the platform has created a resource the
     *       adapter only just discovered; the caller skips and retries next
     *       cycle. A wrong kind key (the comparison is exact and
     *       case-sensitive) looks the same, and the WARN names both causes.</li>
     *   <li>More than one match: logs the candidate ids at WARN and returns
     *       {@code null}. The helper never guesses which one is meant.</li>
     *   <li>Incomplete page: if the response's {@code pageInfo.totalCount}
     *       is larger than the number of entries on the page, other matches
     *       may sit on a page not read, so it logs at WARN and returns
     *       {@code null} rather than trusting one visible match. A response
     *       with no usable {@code totalCount} ({@code pageInfo} absent,
     *       {@code totalCount} absent, non-numeric or negative) is trusted as
     *       complete and its single visible match is returned (the server
     *       filters by kind and the default {@code pageSize} is 1000).</li>
     *   <li>Query or parse failure: logs at WARN and returns {@code null};
     *       never throws. An expected failure (HTTP status, timeout, refused
     *       connection, interrupt) is one WARN line without a stack trace,
     *       with the trace at DEBUG; any other exception class, a malformed
     *       response included, shows its stack trace at WARN the first time
     *       this client sees it here, then one line per call.</li>
     * </ul>
     *
     * <p><strong>Look up every cycle; do not cache across cycles.</strong> A
     * singleton that is deleted and recreated (pak reinstall, admin delete)
     * gets a new id. Clearing a cached id when {@link #addChild} returns
     * {@code false} is not enough: the add is asynchronous, so a POST to a
     * deleted parent's id may be accepted (2xx) and dropped later, leaving
     * the stale id cached for the life of the collector while every cycle
     * reports success. The lookup is one GET against the local Suite API, so
     * repeating it each cycle costs nothing worth saving.
     *
     * @param adapterKind  adapter kind key, e.g. {@code "MyAdapterKind"}
     * @param resourceKind resource kind key, e.g. {@code "MyWorld"}
     * @return the single matching resource UUID, or {@code null}
     */
    public String findSingletonResourceId(String adapterKind, String resourceKind) {
        String ak = adapterKind == null ? "" : adapterKind.trim();
        String rk = resourceKind == null ? "" : resourceKind.trim();
        if (ak.isEmpty() || rk.isEmpty()) {
            logger.warn("SuiteApiStitchClient: findSingletonResourceId needs a non-blank"
                    + " adapterKind and resourceKind (got " + loggable(adapterKind) + "/"
                    + loggable(resourceKind) + ")");
            return null;
        }
        String what = loggable(ak) + "/" + loggable(rk);
        String path = "/api/resources?adapterKind=" + urlEncode(ak)
                + "&resourceKind=" + urlEncode(rk);
        List<String> ids;
        long totalCount;
        int onPage;
        try {
            SimpleJson root = SimpleJson.parse(get(path));
            ids = parseResourceIds(root, ak, rk);
            onPage = root.get("resourceList").size();
            SimpleJson total = root.get("pageInfo").get("totalCount");
            totalCount = total.isNull() ? -1L : total.asLong();
        } catch (Exception e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            logFailure("findSingletonResourceId",
                    "SuiteApiStitchClient: findSingletonResourceId query failed for " + what, e);
            return null;
        }
        if (totalCount > onPage) {
            logger.warn("SuiteApiStitchClient: findSingletonResourceId for " + what
                    + " got a partial page (" + onPage + " of " + totalCount
                    + " results); other matches may exist, returning none");
            return null;
        }
        if (ids.isEmpty()) {
            logger.warn("SuiteApiStitchClient: findSingletonResourceId found no exact "
                    + what + " match (wrong kind key, which is case-sensitive,"
                    + " or not created yet)");
            return null;
        }
        if (ids.size() > 1) {
            logger.warn("SuiteApiStitchClient: findSingletonResourceId found "
                    + ids.size() + " " + what
                    + " resources " + ids + "; expected one, returning none");
            return null;
        }
        return ids.get(0);
    }

    /**
     * Log a swallowed failure of {@link #pushProperties}, {@link #pushStats},
     * {@link #addChildren} or {@link #findSingletonResourceId} without
     * flooding the collector log.
     *
     * <p>These calls repeat every collect cycle, per adapter instance, so a
     * persistent failure (the principal lacks permission, the parent is gone,
     * the Suite API is down, a proxy answers with HTML) would otherwise write
     * a full stack trace every cycle. Every failure gets one WARN line naming
     * the exception class and message (the transport puts the HTTP status at
     * the end of the message, which {@link #failureSummary} keeps when it caps
     * a long one). The stack trace goes to DEBUG, except the first time this
     * client sees an unexpected exception class (anything but
     * {@link #isExpectedFailure}, a malformed response included) for an
     * operation: that one keeps its trace at WARN so a new kind of fault is
     * diagnosable from a default-level log (issue #192).
     *
     * @param operation the public method name, keying the first-trace memory
     */
    private void logFailure(String operation, String context, Exception e) {
        String line = context + ": " + failureSummary(e);
        if (e instanceof ClientClosedException) {
            // A cycle still running on a client its adapter has replaced:
            // say so once per client, then quietly refuse (issue #217).
            if (closedRefusalWarned.compareAndSet(false, true)) {
                logger.warn(line);
            } else if (logger.isDebugEnabled()) {
                logger.debug(line);
            }
            return;
        }
        if (!isExpectedFailure(e)
                && tracedFailures.add(operation + ":" + e.getClass().getName())) {
            logger.warn(line, e);
            return;
        }
        logger.warn(line);
        if (logger.isDebugEnabled()) {
            logger.debug(line + " (stack trace)", e);
        }
    }

    /**
     * True for the failures the transport raises when the Suite API is
     * reachable but unhappy (non-2xx status, including a 401 that survived
     * the one retry) or unreachable (timeout, refused connection, unknown
     * host): the {@link IOException} family. An {@link InterruptedException}
     * (collector shutdown) is expected too. Everything else, runtime
     * exceptions included, is unexpected. Visible to unit tests.
     */
    static boolean isExpectedFailure(Throwable e) {
        return e instanceof IOException || e instanceof InterruptedException;
    }

    /** Longest exception message {@link #failureSummary} echoes into a log line. */
    static final int FAILURE_MESSAGE_MAX = 200;

    /** Characters of the message tail {@link #failureSummary} keeps when capping. */
    static final int FAILURE_TAIL_KEEP = 47;

    /**
     * {@code <SimpleClassName>: <message>} for a one-line log entry. The
     * message can carry server text (a JSON parse error on a malformed 200
     * body echoes the offending input), so unsafe characters are replaced
     * as in {@link #loggable}. A message longer than
     * {@link #FAILURE_MESSAGE_MAX} keeps its head and its last
     * {@link #FAILURE_TAIL_KEEP} characters joined by {@code ...}, at most
     * {@link #FAILURE_MESSAGE_MAX} characters in all, because the transport
     * puts the HTTP status at the end ({@code "Suite API POST <url> HTTP 403"})
     * and a long Suite API host must not push it out of the WARN line.
     * Neither cut leaves a lone surrogate: a high surrogate ending the head
     * and a low surrogate starting the tail are dropped. Visible to unit
     * tests.
     */
    static String failureSummary(Throwable e) {
        String msg = e.getMessage();
        return e.getClass().getSimpleName() + ": "
                + (msg == null ? "(no message)" : capHeadAndTail(msg));
    }

    /** Sanitize and, over {@link #FAILURE_MESSAGE_MAX}, keep head and tail. */
    private static String capHeadAndTail(String msg) {
        StringBuilder clean = new StringBuilder(msg.length());
        for (int i = 0; i < msg.length(); i++) {
            char c = msg.charAt(i);
            clean.append(unsafeForLog(c) ? '?' : c);
        }
        if (clean.length() <= FAILURE_MESSAGE_MAX) return clean.toString();
        int headEnd = FAILURE_MESSAGE_MAX - 3 - FAILURE_TAIL_KEEP;
        if (Character.isHighSurrogate(clean.charAt(headEnd - 1))) headEnd--;
        int tailStart = clean.length() - FAILURE_TAIL_KEEP;
        if (Character.isLowSurrogate(clean.charAt(tailStart))) tailStart++;
        return clean.substring(0, headEnd) + "..." + clean.substring(tailStart);
    }

    /**
     * Perform an authenticated GET against the Suite API with
     * {@code Accept: application/json}.
     *
     * <p>The cached bearer token is used. If the Suite API returns HTTP 401,
     * the token is re-acquired and the GET is retried exactly once.
     *
     * @param path path relative to the Suite API base (e.g.
     *             {@code "/api/resources?adapterKind=VMWARE"})
     * @return the response body as a string
     * @throws SuiteApiHttpException on a non-2xx answer: carries the status,
     *                               the {@code apiErrorCode} when the body has
     *                               one, and a body excerpt (issue #201)
     * @throws IOException          on any other HTTP or network error
     * @throws InterruptedException if the calling thread is interrupted
     */
    public String get(String path) throws IOException, InterruptedException {
        return get(path, null);
    }

    /**
     * Perform an authenticated GET with a caller-chosen {@code Accept} header
     * (issue #201). Use it for endpoints that do not answer JSON, for example
     * the configuration-file store ({@code /api/configurations/files}), which
     * returns the raw file body ({@code "*}{@code /*"}).
     *
     * <p>Token handling, the single 401 retry and the failure contract match
     * {@link #get(String)}.
     *
     * @param path   path relative to the Suite API base
     * @param accept the {@code Accept} header value; {@code null} or blank
     *               means {@code application/json}
     * @return the response body as a string
     * @throws IllegalArgumentException if {@code accept} contains a control
     *                                  character (a header must stay one line)
     * @throws SuiteApiHttpException    on a non-2xx answer
     * @throws IOException              on any other HTTP or network error
     * @throws InterruptedException     if the calling thread is interrupted
     */
    public String get(String path, String accept) throws IOException, InterruptedException {
        String acceptHeader = acceptHeader(accept);
        String tok = ensureToken();
        try {
            return rawGet(path, tok, acceptHeader);
        } catch (Suite401Exception e) {
            tok = reAcquireToken(tok);
            return rawGet(path, tok, acceptHeader);
        }
    }

    /**
     * The {@code Accept} value to send: {@link #DEFAULT_ACCEPT} for
     * {@code null} or blank, else the trimmed value. Visible to tests.
     *
     * @throws IllegalArgumentException if the value holds a control character
     */
    static String acceptHeader(String accept) {
        if (accept == null || accept.trim().isEmpty()) return DEFAULT_ACCEPT;
        String a = accept.trim();
        for (int i = 0; i < a.length(); i++) {
            if (Character.isISOControl(a.charAt(i))) {
                throw new IllegalArgumentException(
                        "SuiteApiStitchClient: Accept header value contains a control"
                        + " character: " + loggable(a));
            }
        }
        return a;
    }

    /**
     * Close the client: mark it closed and release the cached bearer token
     * (issue #217).
     *
     * <p>After this returns, no call on this client acquires a token again.
     * {@link #get} throws an {@link IOException} saying the client is closed;
     * {@link #pushProperties}, {@link #pushStats}, the batch pushes,
     * {@link #addChildren} and {@link #findSingletonResourceId} send nothing and log one WARN for the
     * first refused call (DEBUG after that). This matters when an adapter
     * swaps clients on reconfigure while a cycle is still running on the old
     * one: before, that cycle logged in again and left a token behind.
     *
     * <p>Call from the adapter's {@code onDiscard()} method (or when replacing
     * the client), alongside releasing the
     * {@link com.vcfcf.adapter.http.ManagedHttpClient}. Idempotent. Token
     * release failure is swallowed and logged at WARN; the platform's token
     * TTL is the safety net (per spec §3 cancellation contract). A request
     * already in flight with the old token is not interrupted; it fails or
     * completes on its own.
     */
    public void close() {
        String tok;
        synchronized (tokenLock) {
            this.closed = true;
            tok = this.cachedToken;
            this.cachedToken = null;
        }
        releaseToken(tok); // null-safe, swallows all exceptions
        // URLConnection connections are per-request; nothing else to close here.
    }

    /**
     * Same as {@link #close()}: kept for existing callers. Marks the client
     * closed, so it is no longer reusable after this call (issue #217).
     */
    public void discard() {
        close();
    }

    /** True once {@link #close()} or {@link #discard()} has run. */
    public boolean isClosed() {
        return closed;
    }

    // -----------------------------------------------------------------------
    // Token management (internal)
    // -----------------------------------------------------------------------

    /**
     * Return the cached bearer token, acquiring a new one lazily if absent.
     * Thread-safe: double-checked with {@link #tokenLock}.
     */
    private String ensureToken() throws IOException, InterruptedException {
        if (closed) throw new ClientClosedException();
        String tok = this.cachedToken;
        if (tok != null) return tok;
        synchronized (tokenLock) {
            if (closed) throw new ClientClosedException();
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
            if (closed) throw new ClientClosedException();
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
                suiteApiBase + "/api/auth/token/acquire", body, null, DEFAULT_ACCEPT);

        SimpleJson parsed = SimpleJson.parse(responseBody);
        String token = parsed.get("token").asString(null);
        if (token == null || token.isEmpty()) {
            throw new IOException(
                    "Suite API token/acquire: no 'token' field in response"
                    + " mechanism=" + mechanism);
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
                    suiteApiBase + "/api/auth/token/release", body, null, DEFAULT_ACCEPT);
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
        urlConnRequest("POST", suiteApiBase + apiPath, body, opsToken, DEFAULT_ACCEPT);
    }

    /**
     * GET {@code apiPath} with the given {@code opsToken} and {@code Accept}
     * value, and return the body.
     *
     * @throws Suite401Exception on HTTP 401 (caller must single-retry)
     * @throws IOException       on other HTTP or network error
     */
    private String rawGet(String apiPath, String opsToken, String accept)
            throws IOException, InterruptedException {
        return urlConnRequest("GET", suiteApiBase + apiPath, null, opsToken, accept);
    }

    // -----------------------------------------------------------------------
    // URLConnection transport (loopback path)
    // -----------------------------------------------------------------------

    /**
     * Execute an HTTP request via the platform connection transport.
     *
     * <p>Opens the connection through
     * {@link VcfCfAdapter#openPlatformConnection(String)}, which mirrors the
     * vendor {@code SuiteAPIClient} transport (trust-all + ignore-hostname, or
     * cluster truststore + ignore-hostname in FIPS mode) on the underlying
     * {@code HttpsURLConnection}. Used for
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
     * @param accept   {@code Accept} header value
     * @return response body as String (empty string if the server sends no body)
     * @throws Suite401Exception     on HTTP 401
     * @throws SuiteApiHttpException on any other non-2xx status, with the
     *                               {@code apiErrorCode} and a body excerpt
     * @throws IOException           on a connection error
     * @throws InterruptedException  if the thread is interrupted before the call
     */
    private String urlConnRequest(String method, String fullUrl, String body, String opsToken,
            String accept) throws IOException, InterruptedException {
        return urlConnRequest(method, fullUrl, body, opsToken, accept, REQUEST_TIMEOUT);
    }

    /**
     * {@link #urlConnRequest(String, String, String, String, String)} with a
     * caller-chosen read timeout (the connect timeout stays
     * {@link #REQUEST_TIMEOUT}). Batch pushes use {@link #BATCH_READ_TIMEOUT}.
     */
    private String urlConnRequest(String method, String fullUrl, String body, String opsToken,
            String accept, Duration readTimeout) throws IOException, InterruptedException {
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
            conn.setReadTimeout((int) readTimeout.toMillis());
            conn.setRequestProperty("Accept", accept);
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
            if (status < 200 || status >= 300) {
                String errorBody = readErrorBody(conn);
                Integer apiErrorCode = parseApiErrorCode(errorBody);
                String excerpt = errorBodyExcerpt(errorBody);
                // Exact shape " apiErrorCode <n>" (space separated) is a
                // contract: compliance's OverridesStore.isAbsent matches the
                // message with its own 1501 regex, so changing the separator
                // would flip its missing-overrides-file handling on a rebuild.
                // Pinned by SuiteApiStitchClientTransportTest.
                String code = apiErrorCode == null ? "" : " apiErrorCode " + apiErrorCode;
                if (status == 401) {
                    throw new Suite401Exception(
                            "Suite API " + method + " " + fullUrl
                            + " returned 401 (token expired or credential invalid)"
                            + " mechanism=" + mechanism + code,
                            apiErrorCode, excerpt);
                }
                throw new SuiteApiHttpException(
                        "Suite API " + method + " " + fullUrl + " HTTP " + status + code,
                        status, apiErrorCode, excerpt);
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

    /**
     * Read at most {@link #ERROR_BODY_READ_MAX} bytes of a non-2xx answer's
     * body (UTF-8). Returns {@code ""} when the server sent none or the
     * stream fails: a missing body must never hide the status.
     */
    private static String readErrorBody(HttpURLConnection conn) {
        try (InputStream es = conn.getErrorStream()) {
            if (es == null) return "";
            byte[] buf = new byte[ERROR_BODY_READ_MAX];
            int total = 0;
            int n;
            while (total < buf.length && (n = es.read(buf, total, buf.length - total)) != -1) {
                total += n;
            }
            return new String(buf, 0, total, StandardCharsets.UTF_8);
        } catch (IOException | RuntimeException e) {
            return "";
        }
    }

    /**
     * The numeric {@code apiErrorCode} of a Suite API JSON error body, or
     * {@code null} when the body is empty, not a JSON object, or has no
     * numeric {@code apiErrorCode} in int range. Never throws. Visible to tests.
     */
    static Integer parseApiErrorCode(String body) {
        if (body == null || body.trim().isEmpty()) return null;
        try {
            SimpleJson root = SimpleJson.parse(body);
            if (!root.isObject()) return null;
            SimpleJson code = root.get("apiErrorCode");
            if (code.isNull()) return null;
            String raw = code.asString("").trim();
            if (!raw.matches("-?\\d{1,10}")) return null;
            long v = Long.parseLong(raw);
            if (v < Integer.MIN_VALUE || v > Integer.MAX_VALUE) return null;
            return (int) v;
        } catch (RuntimeException e) {
            return null;
        }
    }

    /**
     * Log-safe start of an error body: unsafe characters replaced as in
     * {@link #loggable}, at most {@link #ERROR_BODY_EXCERPT_MAX} characters
     * plus a {@code ...} marker when cut. Visible to tests.
     */
    static String errorBodyExcerpt(String body) {
        if (body == null || body.isEmpty()) return "";
        return loggable(body, ERROR_BODY_EXCERPT_MAX);
    }

    // -----------------------------------------------------------------------
    // JSON helpers
    // -----------------------------------------------------------------------

    private static String buildPropertiesJson(
            Map<String, String> properties, long timestamp) {
        return "{\"property-content\":" + propertyContentArray(properties, timestamp) + "}";
    }

    private static String buildStatsJson(
            Map<String, Double> stats, long timestamp) {
        return "{\"stat-content\":" + statContentArray(stats, timestamp) + "}";
    }

    /**
     * {@code [{"statKey":k,"timestamps":[ts],"values":[v]},...]}: the
     * {@code property-content} array, shared by the per-id body and the batch
     * entry so the two cannot drift.
     */
    private static String propertyContentArray(Map<String, String> properties,
            long timestamp) {
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        for (Map.Entry<String, String> e : properties.entrySet()) {
            if (!first) sb.append(",");
            first = false;
            sb.append("{\"statKey\":").append(jsonStr(e.getKey()))
              .append(",\"timestamps\":[").append(timestamp).append("]")
              .append(",\"values\":[").append(jsonStr(e.getValue())).append("]}");
        }
        return sb.append("]").toString();
    }

    /**
     * {@code [{"statKey":k,"timestamps":[ts],"data":[v]},...]}: the
     * {@code stat-content} array, shared by the per-id body and the batch
     * entry.
     */
    private static String statContentArray(Map<String, Double> stats, long timestamp) {
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        for (Map.Entry<String, Double> e : stats.entrySet()) {
            if (!first) sb.append(",");
            first = false;
            sb.append("{\"statKey\":").append(jsonStr(e.getKey()))
              .append(",\"timestamps\":[").append(timestamp).append("]")
              .append(",\"data\":[").append(e.getValue()).append("]}");
        }
        return sb.append("]").toString();
    }

    /** Canonical 8-4-4-4-12 hex UUID, the form Suite API resource ids take. */
    private static final Pattern UUID_PATTERN = Pattern.compile(
            "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}");

    /** True if {@code s} (trimmed) is a canonical UUID. Visible to tests. */
    static boolean isUuid(String s) {
        return s != null && UUID_PATTERN.matcher(s.trim()).matches();
    }

    /**
     * Suite API path for the additive add-children call. Visible to tests.
     * The relationship type segment is the lowercase representation value
     * ({@code children}) the spec enumerates.
     */
    static String childrenRelationshipPath(String parentResourceId) {
        return "/api/resources/" + parentResourceId + "/relationships/children";
    }

    /** {@code uuid-values} body: {@code {"uuids":[...]}}. Visible to tests. */
    static String buildUuidValuesJson(Collection<String> uuids) {
        StringBuilder sb = new StringBuilder("{\"uuids\":[");
        boolean first = true;
        for (String id : uuids) {
            if (!first) sb.append(",");
            first = false;
            sb.append(jsonStr(id));
        }
        return sb.append("]}").toString();
    }

    /**
     * Extract the {@code identifier} of every {@code resourceList} entry whose
     * {@code resourceKey} kinds equal the arguments exactly. Never null.
     * Visible to tests.
     */
    static List<String> parseResourceIds(String json, String adapterKind,
            String resourceKind) {
        return parseResourceIds(SimpleJson.parse(json), adapterKind, resourceKind);
    }

    /**
     * Same as {@link #parseResourceIds(String, String, String)} on an already
     * parsed response. Entries whose {@code identifier} is not a UUID are
     * dropped (the result is used as a request path segment); ids are
     * returned lowercase and deduplicated.
     */
    static List<String> parseResourceIds(SimpleJson root, String adapterKind,
            String resourceKind) {
        List<String> ids = new ArrayList<>();
        for (SimpleJson r : root.get("resourceList").asList()) {
            SimpleJson key = r.get("resourceKey");
            String id = r.get("identifier").asString(null);
            if (adapterKind.equals(key.get("adapterKindKey").asString(null))
                    && resourceKind.equals(key.get("resourceKindKey").asString(null))
                    && isUuid(id)) {
                String norm = normalizeUuid(id);
                if (!ids.contains(norm)) ids.add(norm);
            }
        }
        return ids;
    }

    /** Trimmed, lowercase form of a UUID already checked with {@link #isUuid}. */
    static String normalizeUuid(String uuid) {
        return uuid.trim().toLowerCase(java.util.Locale.ROOT);
    }

    /** Longest caller-supplied value echoed into a log line. */
    static final int LOGGABLE_MAX = 80;

    /**
     * Log-safe form of a caller-supplied value: ISO control characters
     * (CR, LF, tab, ...), the Unicode line and paragraph separators
     * (U+2028, U+2029) and format characters (bidi overrides such as U+202E,
     * zero-width characters) replaced with {@code ?} so a value cannot forge,
     * split or visually reorder a log line, and truncated to
     * {@link #LOGGABLE_MAX} characters with a {@code ...} marker. A
     * truncation that would end on the high half of a surrogate pair drops
     * that half rather than emit a lone surrogate. {@code null} renders as
     * {@code "null"}. Visible to tests.
     */
    static String loggable(String s) {
        return loggable(s, LOGGABLE_MAX);
    }

    /** {@link #loggable(String)} with a caller-chosen length cap. */
    private static String loggable(String s, int max) {
        if (s == null) return "null";
        StringBuilder sb = new StringBuilder(Math.min(s.length(), max) + 3);
        for (int i = 0; i < s.length() && sb.length() < max; i++) {
            char c = s.charAt(i);
            sb.append(unsafeForLog(c) ? '?' : c);
        }
        if (s.length() > max) {
            int last = sb.length() - 1;
            if (last >= 0 && Character.isHighSurrogate(sb.charAt(last))) {
                sb.setLength(last);
            }
            sb.append("...");
        }
        return sb.toString();
    }

    /** True for characters {@link #loggable} replaces with {@code ?}. */
    private static boolean unsafeForLog(char c) {
        if (Character.isISOControl(c)) return true;
        int type = Character.getType(c);
        return type == Character.LINE_SEPARATOR
                || type == Character.PARAGRAPH_SEPARATOR
                || type == Character.FORMAT;
    }

    /** Query-parameter encoding (space as %20, not +). */
    private static String urlEncode(String s) {
        return URLEncoder.encode(s, StandardCharsets.UTF_8).replace("+", "%20");
    }

    /**
     * JSON-encode a string value (double-quoted; backslash, quote and every
     * control character below U+0020 escaped).
     * Returns {@code "null"} for a null input.
     */
    static String jsonStr(String s) {
        if (s == null) return "null";
        StringBuilder sb = new StringBuilder(s.length() + 2).append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': sb.append("\\\\"); break;
                case '"': sb.append("\\\""); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    // RFC 8259 section 7: every other control character must be
                    // escaped, or a strict parser rejects the whole body.
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.append('"').toString();
    }
}
