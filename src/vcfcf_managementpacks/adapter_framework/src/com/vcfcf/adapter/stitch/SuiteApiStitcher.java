package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.Logger;
import com.vcfcf.adapter.VcfCfAdapter;

import java.util.Map;

/**
 * v2 opt-in integration point for ambient Suite API property stitching.
 *
 * <p>An adapter that needs to push properties or stats onto a <em>foreign</em>
 * VCF Ops resource (e.g. a {@code VMWARE/HostSystem}) — without writing any
 * transport code — instantiates a {@code SuiteApiStitcher} in its
 * {@link VcfCfAdapter#configureAdapter} step and holds it as a field.
 *
 * <h3>Adapter opt-in (compile side)</h3>
 * <pre>{@code
 * public class MyAdapter extends VcfCfAdapter<MyConfig> {
 *
 *     private SuiteApiStitcher stitcher;
 *
 *     {@literal @}Override
 *     protected void configureAdapter(ResourceStatus status, ResourceConfig rc) {
 *         // Read adapter config, set this.config, build this.httpClient …
 *
 *         // Opt into ambient stitching:
 *         stitcher = SuiteApiStitcher.create(this, componentLogger(SuiteApiStitcher.class));
 *         // — or, for remote collectors with explicit Suite API creds:
 *         stitcher = SuiteApiStitcher.createExplicit(
 *             this, componentLogger(SuiteApiStitcher.class),
 *             getIdentifier(rc, "suiteApiHost"),
 *             getCredentialField(rc, "suiteApiUser"),
 *             getCredentialField(rc, "suiteApiPassword"));
 *     }
 *
 *     {@literal @}Override
 *     public void onDiscard() {
 *         if (stitcher != null) stitcher.discard();
 *         super.onDiscard();
 *     }
 * }
 * }</pre>
 *
 * <h3>Usage inside a VcfCfCollector</h3>
 * <pre>{@code
 * // From collect():
 * Map&lt;String, String&gt; props = new LinkedHashMap&lt;&gt;();
 * props.put("Summary|compliance_score", String.valueOf(score));
 *
 * stitcher.pushProperties(foreignResourceUuid, props, System.currentTimeMillis());
 * }</pre>
 *
 * <h3>What this wraps</h3>
 * <p>{@code SuiteApiStitcher} is a thin facade over {@link SuiteApiStitchClient}.
 * The client handles:
 * <ul>
 *   <li>Credential resolution (ambient → explicit → fail-with-message).</li>
 *   <li>Token lifecycle: cached per-instance, re-acquired on HTTP 401,
 *       released on {@link #discard()} (per spec §1/§2/§3).</li>
 *   <li>Loopback TLS via {@link VcfCfAdapter#openPlatformConnection(String)}
 *       (platform trust manager + hostname verifier, matching the SDK-injected
 *       {@code SuiteAPIClient}'s Noop-class loopback trust posture).</li>
 *   <li>JSON serialisation of property and stat payloads.</li>
 * </ul>
 *
 * <p>Adapters that need lower-level control (e.g. querying the Suite API for
 * resource UUIDs inline rather than via {@link ForeignResourceResolver}) may
 * use {@link SuiteApiStitchClient} directly; this facade is the recommended
 * starting point.
 *
 * <h3>Thread safety</h3>
 * <p>{@code SuiteApiStitcher} is safe to share across calls within a single
 * adapter instance (one thread per collect cycle, per the platform contract).
 * Do not share across adapter instances.
 *
 * @see SuiteApiStitchClient
 * @see AmbientCredential
 */
public final class SuiteApiStitcher {

    private final SuiteApiStitchClient client;

    private SuiteApiStitcher(SuiteApiStitchClient client) {
        this.client = client;
    }

    // -----------------------------------------------------------------------
    // Factory methods
    // -----------------------------------------------------------------------

    /**
     * Create a stitcher using ambient credentials (standard path for
     * all-in-one nodes and cloud-proxy nodes co-located with the Suite API).
     *
     * <p>Identity v3 order: prefers the platform-injected per-instance
     * credential ({@code adapter.getAdapterConfig().getAdapterCredentials()},
     * when present), then {@code automationuser.properties} ({@code
     * automationAdmin}, preferred over maintenance on every node role
     * including a Cloud Proxy), falling back to
     * {@code maintenanceuser.properties} only if both prior sources are
     * absent/unreadable (see {@link AmbientCredential}). File-based passwords
     * decrypt via the SDK {@link com.integrien.alive.common.security.Crypt};
     * targets {@code https://localhost/suite-api}. This is the zero-config
     * path — no adapter config fields are required.
     *
     * @param adapter the adapter instance ({@code this} in configureAdapter)
     * @param logger  the adapter-specific logger
     * @return a configured stitcher
     * @throws IllegalStateException if the credential file is absent or
     *                               unreadable (e.g. remote collector without
     *                               explicit credentials)
     */
    public static SuiteApiStitcher create(VcfCfAdapter<?> adapter, Logger logger) {
        SuiteApiStitchClient client = SuiteApiStitchClient.builder()
                .adapter(adapter)
                .logger(logger)
                .build();
        return new SuiteApiStitcher(client);
    }

    /**
     * Create a stitcher using explicitly-supplied Suite API credentials.
     *
     * <p>Use this variant when the adapter instance config exposes Suite API
     * credential fields — the documented fallback for remote collectors where
     * {@code maintenanceuser.properties} is absent or unreachable.
     *
     * <p>If any of the explicit fields are blank, the builder falls back to
     * the ambient path automatically. This means you can call this method
     * unconditionally and pass {@code null} for credentials when ambient should
     * be used.
     *
     * @param adapter   the adapter instance
     * @param logger    the adapter-specific logger
     * @param host      Suite API hostname (e.g. {@code "vcf-ops.example.com"}),
     *                  or {@code null} to use localhost
     * @param username  Suite API username, or {@code null} to use ambient
     * @param password  Suite API password (plaintext), or {@code null} to use ambient
     * @return a configured stitcher
     * @throws IllegalStateException if credentials cannot be resolved from
     *                               either source
     */
    public static SuiteApiStitcher createExplicit(
            VcfCfAdapter<?> adapter,
            Logger logger,
            String host,
            String username,
            String password) {
        SuiteApiStitchClient client = SuiteApiStitchClient.builder()
                .adapter(adapter)
                .explicitCredentials(host, username, password)
                .logger(logger)
                .build();
        return new SuiteApiStitcher(client);
    }

    // -----------------------------------------------------------------------
    // Stitching API (delegates to SuiteApiStitchClient)
    // -----------------------------------------------------------------------

    /**
     * Push string properties onto a foreign VCF Ops resource.
     *
     * <p>A Suite API token is acquired before the push and released in a
     * {@code finally} block — cooperative cancellation is honoured.
     *
     * <p>Failures are logged at WARN and swallowed — a stitching failure
     * should not abort the adapter's primary collect cycle.
     *
     * @param resourceId VCF Ops resource UUID (e.g. from
     *                   {@link ForeignResourceResolver})
     * @param properties map of statKey → string value; no-op if empty
     * @param timestamp  sample timestamp in epoch milliseconds
     */
    public void pushProperties(String resourceId,
            Map<String, String> properties,
            long timestamp) {
        client.pushProperties(resourceId, properties, timestamp);
    }

    /**
     * Push numeric statistics onto a foreign VCF Ops resource.
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
        client.pushStats(resourceId, stats, timestamp);
    }

    /**
     * Add one child to an existing resource, additively, through the Suite
     * API ({@code POST /api/resources/{parent}/relationships/children}).
     *
     * <p>Use this when the parent is shared by several adapter instances (for
     * example a pak-level singleton each instance links its own foreign
     * resource under). It is POST, never PUT: the PUT on the same path
     * replaces the parent's whole child list, so each instance would wipe the
     * links the others added (last writer wins). No replace variant is
     * exposed. The add is asynchronous: {@code true} means "request
     * accepted", not "linked", so log it that way. Re-asserting the same edge
     * every cycle is the intended usage. Failures are logged at
     * WARN and swallowed, like {@link #pushStats}. Nothing in the framework
     * removes an edge added this way (known limitation): a child dropped
     * from an instance's scope stays a child until the pak deletes the edge
     * itself. Full contract: {@link SuiteApiStitchClient#addChildren}.
     *
     * <p>For edges reported in the adapter's own collect result, use
     * {@link RelationshipBuilder} instead (its own-parent emission is a full
     * set per parent).
     *
     * @param parentResourceId Suite API resource UUID of the parent
     * @param childResourceId  Suite API resource UUID of the child
     * @return {@code true} if the request was accepted (2xx); not proof the
     *         edge exists
     */
    public boolean addChild(String parentResourceId, String childResourceId) {
        return client.addChild(parentResourceId, childResourceId);
    }

    /**
     * Add several children to an existing resource, additively. Same contract
     * as {@link #addChild}; one request for the whole collection.
     *
     * @param parentResourceId Suite API resource UUID of the parent
     * @param childResourceIds Suite API resource UUIDs of the children
     * @return {@code true} if the request was accepted (2xx)
     */
    public boolean addChildren(String parentResourceId,
            java.util.Collection<String> childResourceIds) {
        return client.addChildren(parentResourceId, childResourceIds);
    }

    /**
     * Look up the Suite API UUID of the single resource of a kind, typically
     * the adapter's own singleton, so it can be used as a parent in
     * {@link #addChild}. Returns {@code null} (after a WARN) on no match, on
     * more than one match (never guesses), on a partial result page, or on
     * any query failure; never throws. A response with no usable
     * {@code totalCount} ({@code pageInfo} absent, {@code totalCount} absent,
     * non-numeric or negative) is trusted as complete and its single visible
     * match is returned. Look the singleton up every cycle (one local GET)
     * and do not cache the id across cycles: the add is asynchronous, so a
     * POST to a deleted singleton's id may be accepted and dropped later,
     * and a cached stale id would then never be cleared. Full contract:
     * {@link SuiteApiStitchClient#findSingletonResourceId}.
     *
     * @param adapterKind  adapter kind key
     * @param resourceKind resource kind key
     * @return the single matching resource UUID, or {@code null}
     */
    public String findSingletonResourceId(String adapterKind, String resourceKind) {
        return client.findSingletonResourceId(adapterKind, resourceKind);
    }

    /**
     * Perform an authenticated GET against the Suite API.
     *
     * <p>Useful for resolving foreign resource UUIDs inline when
     * {@link ForeignResourceResolver} is not in use.
     *
     * @param path Suite API path relative to the base URL (e.g.
     *             {@code "/api/resources?adapterKind=VMWARE"})
     * @return response body as a string
     * @throws java.io.IOException  on HTTP or network error
     * @throws InterruptedException if the calling thread is interrupted
     */
    public String get(String path) throws java.io.IOException, InterruptedException {
        return client.get(path);
    }

    /**
     * Release underlying HTTP resources.
     *
     * <p>Call from the adapter's {@link VcfCfAdapter#onDiscard()} method:
     * <pre>{@code
     * {@literal @}Override
     * public void onDiscard() {
     *     if (stitcher != null) stitcher.discard();
     *     super.onDiscard();
     * }
     * }</pre>
     */
    public void discard() {
        client.discard();
    }
}
