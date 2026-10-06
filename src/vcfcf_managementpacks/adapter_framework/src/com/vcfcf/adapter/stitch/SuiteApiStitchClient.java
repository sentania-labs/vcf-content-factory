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
 * ignore-hostname in non-FIPS mode (server-trust only — no client keystore, no
 * CaSA, no cert-renewal registration), with a documented-TODO FIPS branch (see
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
     * one WARN line without a stack trace, with the trace at DEBUG; anything
     * else keeps its stack trace at WARN (see {@link #isExpectedFailure}).
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
            logFailure("SuiteApiStitchClient: addChildren failed for parent="
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
     *       with the trace at DEBUG; anything else, a malformed response
     *       included, keeps its stack trace at WARN.</li>
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
            logFailure("SuiteApiStitchClient: findSingletonResourceId query failed for "
                    + what, e);
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
     * Log a swallowed failure of {@link #addChildren} or
     * {@link #findSingletonResourceId} without flooding the collector log.
     *
     * <p>These calls repeat every collect cycle, per adapter instance, so a
     * persistent expected failure (the principal lacks relationship
     * permission, the parent is gone, the Suite API is down) would otherwise
     * write a full stack trace every cycle. Expected failures get one WARN
     * line naming the exception class and message (the transport puts the
     * HTTP status at the end of the message, which {@link #failureSummary}
     * keeps when it caps a long one) and the stack trace only at DEBUG;
     * unexpected ones keep the stack trace at WARN.
     */
    private void logFailure(String context, Exception e) {
        String line = context + ": " + failureSummary(e);
        if (isExpectedFailure(e)) {
            logger.warn(line);
            if (logger.isDebugEnabled()) {
                logger.debug(line + " (stack trace)", e);
            }
        } else {
            logger.warn(line, e);
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
