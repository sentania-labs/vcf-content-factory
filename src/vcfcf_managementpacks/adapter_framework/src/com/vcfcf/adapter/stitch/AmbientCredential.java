package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.config.AdapterConfig;
import com.integrien.alive.common.adapter3.config.AdapterCredentialConfig;
import com.integrien.alive.common.security.Crypt;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;

/**
 * Resolves the ambient Suite API credential — preferring the platform's
 * collector-injected per-instance credential, then falling back to reading
 * and decrypting a platform config-user credential file via the SDK's
 * {@link Crypt} (the only FIPS-safe decryption path on 9.1 collectors).
 *
 * <h3>Ambient order (identity v3): injected → automation → maintenance</h3>
 * <p><strong>The platform-injected per-instance credential is preferred,
 * unconditionally, when present.</strong> This is the same credential the
 * vendor SDK itself prefers (bytecode-proven,
 * {@code knowledge/context/api-surface/per-instance-suiteapi-credential-contract.md}):
 * the collector serializes a per-instance Suite API credential into
 * {@code AdapterConfig.adapterCredentials}, readable via the SDK-public
 * chain {@code AdapterBase.getAdapterConfig().getAdapterCredentials()} →
 * {@code getUserName()}/{@code getPassword()}. No aria-ops-core type is
 * required to read it. Falls through to {@code automationuser.properties}
 * (principal {@code automationAdmin}) when the injected credential is
 * absent, null, or blank, and finally to
 * {@code maintenanceuser.properties} when automation is also absent or
 * unreadable. See {@code knowledge/designs/stitcher-identity-v3-adapter-credentials.md}.
 *
 * <p>This preference order is not cosmetic. On a Cloud Proxy the file-based
 * fallbacks name <em>different</em> principals: {@code automationuser.properties}
 * → {@code automationAdmin}; {@code maintenanceuser.properties} → on a primary
 * node, {@code maintenanceAdmin}; on a Cloud Proxy, {@code cloudproxy_<uuid>}
 * (scoped reverse-connect account with {@code roles:[]}, which 403s on Suite
 * API resource reads). Neither file identity works from a Cloud Proxy: the
 * automation credential 401s at token acquire, and on devel 9.1 it does not
 * even decrypt there (DEF-006,
 * {@code knowledge/lessons/cross-mp-stitch-cp-identity-and-edge-mechanics.md},
 * compliance#58). So on a Cloud Proxy the files are never tried
 * ({@link #isCloudProxy(Path)}). Preferring maintenance-first was the root
 * cause of the Synology-stitcher CP-403 (see
 * {@code knowledge/context/investigations/cp-auth-door-probe-2026-07-01.md}).
 * The platform-injected credential — a per-instance principal minted by the
 * collector — is the mechanism the vendor corpus relies on, and the only
 * ambient identity that works on a Cloud Proxy.
 *
 * <h3>Credential source resolution</h3>
 * <p>Candidates are tried in order; first present/readable hit wins:
 * <ol>
 *   <li>System property {@code vcfcf.suiteapi.credential.path} — explicit
 *       override, useful in test harnesses or non-standard deployments. When
 *       set, this is the <em>only</em> candidate tried (no injected/
 *       automation/maintenance fallback) — an explicit override that is
 *       unreadable is a configuration error, not a signal to silently try
 *       something else.</li>
 *   <li>Platform-injected {@code AdapterConfig.getAdapterCredentials()} —
 *       used when the caller supplies a non-null {@link AdapterConfig} whose
 *       {@code getAdapterCredentials()} is non-null and carries a
 *       non-blank username. See {@link #load(AdapterConfig)}.</li>
 *   <li>Hard-wired default
 *       {@code /usr/lib/vmware-vcops/user/conf/automationuser.properties}
 *       (principal {@code automationAdmin}) — present on primary and Cloud
 *       Proxy nodes (prod probe, 2026-07-01), but used only off a Cloud Proxy:
 *       it does not authenticate from one (DEF-006).</li>
 *   <li>Hard-wired fallback
 *       {@code /usr/lib/vmware-vcops/user/conf/maintenanceuser.properties} —
 *       used only when the automation file is absent or unreadable.
 *       Empirically confirmed present on VCF Ops 9.0.2 (devel) and 9.1
 *       (prod). See {@code knowledge/context/investigations/suiteapi_ambient_auth_devel_2026_06_09.md}.</li>
 * </ol>
 *
 * <p><strong>Crash-the-cycle guarantee:</strong> a failure reading any one
 * source (including a {@code null} {@link AdapterConfig}, a {@code null}
 * {@code getAdapterCredentials()}, or an exception thrown while probing it)
 * simply means that source is absent — the chain falls through to the next
 * candidate. Construction never throws out of this fallthrough; only
 * exhausting every candidate (or an explicit-override failure) throws.
 * <p><strong>Why {@code CommonConstants.VCOPS} is NOT used for path
 * derivation:</strong> {@code CommonConstants.VCOPS} is a <em>product
 * display-name</em> constant (value {@code "VCF Ops"}, built by concatenating
 * {@code productNamePrefix} + {@code " Ops"} in the static initializer —
 * confirmed by {@code javap -c} on {@code vrops-adapters-sdk-2.2.jar}).
 * Appending {@code "/conf/maintenanceuser.properties"} to it produces the
 * nonsense relative path {@code "VCF Ops/conf/maintenanceuser.properties"},
 * which is the live bug that blocked compliance build 43 on devel 9.0.2.
 * Similarly, {@code USER_CONF}, {@code ALIVE_BASE}, and every
 * other path-looking field in {@code CommonConstants} carries its own field
 * name as its literal value (e.g. {@code USER_CONF = "USER_CONF"}) — none
 * of these are filesystem paths. The SDK exposes no install-directory or
 * user-directory path constant; use the empirically proven hard-wired default.
 * See {@code knowledge/lessons/sdk-constants-are-display-names.md}.
 *
 * <h3>File format (keys only — no secret values)</h3>
 * <pre>
 *   username=&lt;principal&gt;    (e.g. automationAdmin — read from file, never assumed)
 *   password=&lt;encrypted&gt;
 *   encrypted=true
 * </pre>
 *
 * <h3>FIPS constraint</h3>
 * <p>The 9.1 collector JVM runs with
 * {@code -Dorg.bouncycastle.fips.approved_only=true}.
 * Never hand-roll the cipher; always delegate to
 * {@code Crypt.getDefaultCrypt().decrypt(password)}.
 *
 * <h3>Failure cases</h3>
 * <ul>
 *   <li>All candidate paths absent or unreadable (e.g. remote collector) —
 *       throws {@link IOException} listing every path tried. The caller (
 *       {@link SuiteApiStitchClient.Builder}) must then fall back to
 *       explicit credential fields.</li>
 *   <li>Malformed file (missing keys, empty username) — throws
 *       {@link IOException}.</li>
 *   <li>Decryption failure — {@link Crypt} logs it at ERROR and returns
 *       null; this throws {@link IOException}. Anything Crypt throws
 *       propagates.</li>
 *   <li>Cloud Proxy with no injected credential — throws {@link IOException}
 *       without reading a file candidate or calling {@link Crypt}, so the
 *       platform logs no cipher ERROR (compliance#58; see
 *       {@link #isCloudProxy(Path)}).</li>
 * </ul>
 */
public final class AmbientCredential {

    /**
     * System property that, when set, overrides the credential file path
     * (candidate 1 in resolution order). Intended for test harnesses and
     * non-standard deployments.
     */
    static final String SYSPROP_CREDENTIAL_PATH = "vcfcf.suiteapi.credential.path";

    /**
     * Preferred config-user properties file: the automation account
     * ({@code automationAdmin}), RBAC-bearing on every node role including
     * a Cloud Proxy. Confirmed present on VCF Ops 9.0.2 (devel) and 9.1
     * (prod, 2026-07-01 CP probe). Tried before {@link #MAINTENANCE_PROPS_PATH}.
     */
    static final String AUTOMATION_PROPS_PATH =
            "/usr/lib/vmware-vcops/user/conf/automationuser.properties";

    /**
     * Fallback config-user properties file: the maintenance account. On a
     * primary node this is {@code maintenanceAdmin} (RBAC-bearing); on a
     * Cloud Proxy it resolves to the scoped {@code cloudproxy_<uuid>}
     * account ({@code roles:[]}, 403s on resource reads) — this is why
     * {@link #AUTOMATION_PROPS_PATH} is preferred unconditionally and this
     * file is used only when the automation file is absent or unreadable.
     * Empirically confirmed present on VCF Ops 9.0.2 (devel) and 9.1 (prod).
     * See {@code knowledge/context/investigations/suiteapi_ambient_auth_devel_2026_06_09.md}.
     */
    static final String MAINTENANCE_PROPS_PATH =
            "/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties";

    /**
     * The collector's own properties file, which says whether this collector
     * is a Cloud Proxy (compliance#58). Mode {@code 0600 admin:admin}, readable
     * by the collector JVM the adapter runs in.
     */
    static final String COLLECTOR_PROPS_PATH =
            "/usr/lib/vmware-vcops/user/conf/collector/collector.properties";

    /**
     * Whether {@code collectorProperties} marks this collector a Cloud Proxy:
     * {@code isUnifiedCloudProxy} decides when it is present (an explicit
     * {@code false} included); only when it is absent (8.18) does
     * {@code httpRelayEnabled=true} count.
     * Anything else, including a missing or unreadable file, is false, which
     * keeps the behaviour from before this check. Visible to tests.
     *
     * <p>Evidence (read-only SSH, 2026-10-28, six devel nodes):
     * <ul>
     *   <li>{@code isUnifiedCloudProxy} is the key the collector's own
     *       {@code CollectorProperties} reads ({@code getBoolean(
     *       "isUnifiedCloudProxy", false)}, vcops-collector 9.1.1). True on the
     *       9.0.2 and 9.1.1 proxies, false on both analytics nodes. Absent on
     *       8.18.6, proxy and node alike.</li>
     *   <li>{@code httpRelayEnabled=true} (one-way collector traffic over the
     *       suite-api port, relay URL {@code https://localhost/suite-api}) is
     *       set on all three proxies, 8.18.6 included, and on none of the
     *       three analytics nodes.</li>
     *   <li>Not used: {@code remote=true}. It is true on every proxy, but
     *       older platform jars still carry a classic {@code REMOTE} collector
     *       type ({@code CollectorType}), whose ambient behaviour is not
     *       established, so it keeps the old path.</li>
     * </ul>
     */
    static boolean isCloudProxy(Path collectorProperties) {
        if (collectorProperties == null) return false;
        Properties p = new Properties();
        try {
            if (!Files.isReadable(collectorProperties)) return false;
            try (InputStream in = Files.newInputStream(collectorProperties)) {
                p.load(in);
            }
        } catch (IOException | RuntimeException e) {
            return false;
        }
        // Review N1: isUnifiedCloudProxy is the key the collector itself reads,
        // so when present it decides, an explicit false included.
        // httpRelayEnabled only stands in where it is absent (8.18).
        String unified = p.getProperty("isUnifiedCloudProxy");
        if (unified != null && !unified.trim().isEmpty()) {
            return isTrue(unified);
        }
        return isTrue(p.getProperty("httpRelayEnabled"));
    }

    private static boolean isTrue(String v) {
        return v != null && "true".equalsIgnoreCase(v.trim());
    }

    /** Property key for the principal name. */
    private static final String KEY_USERNAME = "username";
    /** Property key for the (possibly encrypted) password. */
    private static final String KEY_PASSWORD = "password";
    /** Property key controlling whether the password needs decryption. */
    private static final String KEY_ENCRYPTED = "encrypted";

    private final String username;
    private final String password;

    /**
     * Which candidate source this credential was loaded from — {@code
     * "instance"} (platform-injected per-instance credential), {@code
     * "automation"}, {@code "maintenance"}, or {@code "override"} (explicit
     * system-property path). Used for the INFO selection log only; never
     * exposed alongside the secret.
     */
    private final String sourceLabel;

    /**
     * When non-null, why the platform-injected per-instance credential
     * ({@code "instance"} source) was <em>not</em> selected even though an
     * {@link AdapterConfig} was present — either the swallowed exception's
     * class name (and, for a {@link LinkageError}, its message — safe to
     * surface since a {@code NoClassDefFoundError} message is just the
     * missing class name, never secret material) or {@code "credentials
     * null/blank"}. Populated only when {@link #load(AdapterConfig)} was
     * called with a non-null {@code adapterConfig} and the winning source
     * ended up being a file candidate instead of {@code "instance"}; {@code
     * null} in every other case (including the common early-lifecycle
     * "no config yet" case, which is not surprising and stays silent). See
     * {@code knowledge/context/reviews/framework/ambient-credential-v3-instance-first.md}
     * WARNING-1.
     */
    private final String injectedFailureReason;

    private AmbientCredential(String username, String password, String sourceLabel) {
        this(username, password, sourceLabel, null);
    }

    private AmbientCredential(String username, String password, String sourceLabel,
            String injectedFailureReason) {
        this.username = username;
        this.password = password;
        this.sourceLabel = sourceLabel;
        this.injectedFailureReason = injectedFailureReason;
    }

    /**
     * Return a copy of this credential carrying the given injected-credential
     * failure reason. Used only by {@link #load(AdapterConfig)} to attach the
     * diagnostic to a file-sourced credential when the instance source was
     * attempted-and-lost.
     */
    private AmbientCredential withInjectedFailureReason(String reason) {
        return new AmbientCredential(username, password, sourceLabel, reason);
    }

    /**
     * The principal name read from the properties file.
     * Never assume a fixed value — the platform could rename this account.
     *
     * @return the principal name (e.g. {@code maintenanceAdmin})
     */
    public String getUsername() {
        return username;
    }

    /**
     * The decrypted (plaintext) password.
     *
     * <p>Never log this value. Callers should use it immediately to acquire
     * a token and discard any reference.
     *
     * @return the plaintext password
     */
    public String getPassword() {
        return password;
    }

    /**
     * Which candidate source this credential was loaded from — {@code
     * "instance"}, {@code "automation"}, {@code "maintenance"}, or {@code
     * "override"}. Callers use this for the INFO selection log (mechanism +
     * principal + source); never a secret.
     *
     * @return the source label
     */
    public String getSourceLabel() {
        return sourceLabel;
    }

    /**
     * Why the platform-injected per-instance credential was not selected,
     * even though an {@link AdapterConfig} was present — or {@code null} if
     * either no config was present or the instance source won outright. See
     * {@link #injectedFailureReason} for the exact population rule. Callers
     * (the {@code SuiteApiStitchClient.Builder}) use this for a one-line
     * diagnostic breadcrumb; it is never a secret.
     *
     * @return the sanitized failure reason, or {@code null}
     */
    public String getInjectedFailureReason() {
        return injectedFailureReason;
    }

    // -----------------------------------------------------------------------
    // Factory
    // -----------------------------------------------------------------------

    /**
     * Carries the sanitized reason {@link #tryInjectedCredential(AdapterConfig)}
     * lost the instance source on the current thread, for {@link
     * #load(AdapterConfig)} to pick up immediately afterward. A {@link
     * ThreadLocal} (not a static field) because multiple adapter instances
     * may resolve credentials concurrently on the platform. Always cleared
     * before {@code load(AdapterConfig)} returns — never leaks across calls.
     */
    private static final ThreadLocal<String> LAST_INJECTED_FAILURE_REASON = new ThreadLocal<>();

    /**
     * Test-only accessor for {@link #LAST_INJECTED_FAILURE_REASON}, exercised
     * directly by {@code AmbientCredentialTest} to verify the WARNING-1
     * breadcrumb-recording logic in {@link
     * #tryInjectedCredential(AdapterConfig)} without depending on the
     * hardcoded {@link #AUTOMATION_PROPS_PATH}/{@link #MAINTENANCE_PROPS_PATH}
     * files being present and writable in a test sandbox (they are root-owned
     * platform paths — see the class javadoc test-harness caveat). Not used
     * by production code; {@link #load(AdapterConfig)} reads the same
     * thread-local directly.
     */
    static String peekLastInjectedFailureReasonForTest() {
        return LAST_INJECTED_FAILURE_REASON.get();
    }

    /**
     * Build a sanitized, non-secret description of why the injected
     * credential could not be read — either the caught exception's class
     * name (plus, for a {@link LinkageError}, its message, since a {@code
     * NoClassDefFoundError} message is just the missing class name) or
     * {@code null} for the "credentials null/blank" case (handled by the
     * caller, not this method). Never includes {@link Throwable#getMessage()}
     * for a non-{@link LinkageError}, to avoid any risk of echoing input that
     * could embed secret-adjacent data.
     */
    private static String describeInjectedFailure(Throwable t) {
        String className = t.getClass().getSimpleName();
        if (t instanceof LinkageError) {
            String msg = t.getMessage();
            return (msg == null || msg.trim().isEmpty()) ? className : className + ": " + msg;
        }
        return className;
    }

    /**
     * Load and decrypt the ambient Suite API credential with no platform-
     * injected {@link AdapterConfig} available.
     *
     * <p>Equivalent to {@code load(null)} — falls through directly to the
     * automation/maintenance file candidates. Kept for callers that predate
     * the injected-credential source (identity v3) or that genuinely have no
     * {@link AdapterConfig} in hand (e.g. some test harnesses).
     *
     * @return loaded and decrypted credential
     * @throws IOException      if no candidate is accessible, the file is
     *                          malformed, Crypt cannot decrypt the password
     *                          (it returns null), or this is a Cloud Proxy
     *                          with no injected credential
     * @throws RuntimeException if Crypt itself throws (it normally logs and
     *                          returns null instead)
     * @see #load(AdapterConfig)
     */
    public static AmbientCredential load() throws IOException {
        return load(null);
    }

    /**
     * Load the ambient Suite API credential, preferring the platform-injected
     * per-instance credential carried on {@code adapterConfig} when present.
     *
     * <p>Resolution order (see class Javadoc for full detail):
     * <ol>
     *   <li>Explicit {@value #SYSPROP_CREDENTIAL_PATH} override, if set — the
     *       <em>only</em> source tried when set (highest priority; unchanged
     *       from the pre-v3 behavior).</li>
     *   <li>Platform-injected credential: {@code adapterConfig
     *       .getAdapterCredentials().getUserName()/getPassword()} — used when
     *       {@code adapterConfig} is non-null, {@code getAdapterCredentials()}
     *       is non-null, and the username is non-null/non-blank. Any failure
     *       reading this source (null config, null credentials, blank
     *       username/password, or a thrown exception while probing it) simply
     *       means the source is absent; the chain falls through to the next
     *       candidate — this never throws.</li>
     *   <li>Automation file candidate, then maintenance file candidate (see
     *       {@link #buildCandidates()}) — first candidate that exists
     *       <em>and</em> is readable wins. A candidate that exists but is
     *       unreadable is skipped in favor of the next one.</li>
     * </ol>
     * <p>If every source is exhausted, an {@link IOException} is thrown
     * listing every file path tried (the injected-credential check is not a
     * file path and is reported separately in the exception message when it
     * was attempted and came up empty).
     *
     * @param adapterConfig the adapter's platform-supplied {@link AdapterConfig},
     *                      or {@code null} if unavailable (e.g. before platform
     *                      injection, or a test harness) — treated as "source
     *                      absent", not an error
     * @return loaded and decrypted credential
     * @throws IOException      if no candidate is accessible, the file is
     *                          malformed, Crypt cannot decrypt the password
     *                          (it returns null), or this is a Cloud Proxy
     *                          with no injected credential
     * @throws RuntimeException if Crypt itself throws (it normally logs and
     *                          returns null instead)
     */
    public static AmbientCredential load(AdapterConfig adapterConfig) throws IOException {
        return load(adapterConfig, Paths.get(COLLECTOR_PROPS_PATH), buildCandidates());
    }

    /**
     * {@link #load(AdapterConfig)} with the collector properties file and the
     * file candidates supplied. Seam for tests.
     *
     * <p><strong>Cloud Proxy (compliance#58).</strong> Unless the explicit
     * override is set, when the injected credential is absent and
     * {@code collectorProperties} marks this collector a Cloud Proxy
     * ({@link #isCloudProxy(Path)}), no file candidate is read and
     * {@code Crypt} is never called: an {@link IOException} saying so is
     * thrown instead. On a Cloud Proxy the file credentials do not
     * authenticate (DEF-006: automation 401s at token acquire, maintenance
     * is the role-less {@code cloudproxy_<uuid>}), and on devel 9.1 the
     * automation password does not even decrypt: {@code Crypt.decrypt_impl_v2}
     * logs "pad block corrupted" at ERROR and returns null before the
     * framework sees anything.
     */
    static AmbientCredential load(AdapterConfig adapterConfig, Path collectorProperties,
            List<Candidate> fileCandidates) throws IOException {
        boolean overrideSet = isOverrideSet();
        String injectedFailureReason = null;

        if (!overrideSet) {
            AmbientCredential injected = tryInjectedCredential(adapterConfig);
            if (injected != null) {
                return injected;
            }
            // Instance source lost — capture why, but only when a config was
            // actually present (the common early-lifecycle "no config yet"
            // case has nothing to report and stays silent).
            if (adapterConfig != null) {
                injectedFailureReason = LAST_INJECTED_FAILURE_REASON.get();
            }
            LAST_INJECTED_FAILURE_REASON.remove();

            if (isCloudProxy(collectorProperties)) {
                throw new IOException("AmbientCredential: this collector is a Cloud Proxy ("
                        + COLLECTOR_PROPS_PATH + " marks it one),"
                        + " where the automation and maintenance file credentials do not"
                        + " authenticate, so they were not tried; the per-instance credential the"
                        + " collector injects was not available here"
                        + (injectedFailureReason == null ? "" : " (" + injectedFailureReason + ")")
                        + ". Collection on this proxy normally has it; Test Connection may not");
            }
        }

        AmbientCredential fileCred = loadFromFileCandidates(fileCandidates);
        return injectedFailureReason == null
                ? fileCred
                : fileCred.withInjectedFailureReason(injectedFailureReason);
    }

    /**
     * Whether the explicit {@value #SYSPROP_CREDENTIAL_PATH} override system
     * property is currently set to a non-blank value.
     */
    private static boolean isOverrideSet() {
        String override = System.getProperty(SYSPROP_CREDENTIAL_PATH);
        return override != null && !override.trim().isEmpty();
    }

    /**
     * Attempt to read the platform-injected per-instance credential from
     * {@code adapterConfig}. Returns {@code null} (source absent) rather than
     * throwing on any failure — a null config, null
     * {@code getAdapterCredentials()}, blank username, or a failure while
     * probing any of those are all treated identically: "this source is not
     * available, try the next one." Nothing here may throw out of {@link
     * #load(AdapterConfig)}'s construction path.
     *
     * <p><strong>{@code catch (Exception | LinkageError)}, not just {@code
     * catch (Exception)} — deliberate.</strong> Live sandbox testing of this
     * change (2026-07-02) found that {@code
     * AdapterCredentialConfig.getPassword()} is NOT a bare field accessor:
     * its bytecode calls {@code
     * com.vmware.vcops.security.Crypt.getDefaultCrypt().decrypt(...)} on the
     * stored password before returning it — a class that ships in
     * <em>neither</em> {@code vrops-adapters-sdk-2.2.jar} nor any other jar
     * this framework compiles or ships against (contrast with {@code
     * com.integrien.alive.common.security.Crypt}, the SDK-shipped decrypt
     * path {@link AmbientCredential} already uses for the file-based
     * candidates — a different class in a different package). If that class
     * is likewise absent from an adapter process's runtime classpath on some
     * collector build, this call throws {@link NoClassDefFoundError} — a
     * {@link LinkageError}, <em>not</em> an {@link Exception} subtype — which
     * a bare {@code catch (Exception)} would NOT catch, silently violating
     * the crash-the-cycle guarantee this whole design commits to. Catching
     * {@code Exception | LinkageError} here honors "any failure reading a
     * source falls to the next; nothing throws out of construction" for
     * exactly that documented case, while letting genuinely-fatal JVM errors
     * ({@link VirtualMachineError}, {@code ThreadDeath}) propagate rather
     * than be silently swallowed. See {@code knowledge/context/api-surface/
     * per-instance-suiteapi-credential-contract.md} §7 for the live evidence.
     *
     * <p>When the injected source is lost while {@code adapterConfig} was
     * non-null, the sanitized reason (caught exception's class name, plus
     * message for a {@link LinkageError}; or {@code null} here — the
     * null-credentials/blank case is reported by the caller) is recorded on
     * a thread-local for {@link #load(AdapterConfig)} to attach to the
     * eventual file-sourced {@link AmbientCredential} as {@link
     * #getInjectedFailureReason()} — a one-line INFO breadcrumb for the
     * {@code SuiteApiStitchClient.Builder} to log. See {@code
     * knowledge/context/reviews/framework/ambient-credential-v3-instance-first.md}
     * WARNING-1.
     *
     * @param adapterConfig the platform-supplied config, or {@code null}
     * @return a loaded credential with source label {@code "instance"}, or
     *         {@code null} if the injected credential is absent/blank/unreadable
     */
    static AmbientCredential tryInjectedCredential(AdapterConfig adapterConfig) {
        if (adapterConfig == null) {
            return null;
        }
        AdapterCredentialConfig creds;
        String username;
        String password;
        try {
            creds = adapterConfig.getAdapterCredentials();
            if (creds == null) {
                LAST_INJECTED_FAILURE_REASON.set("credentials null/blank");
                return null;
            }
            // Check the username (a bare field accessor — see class javadoc
            // contrast with getPassword()) before calling getPassword(),
            // which is the call that can throw NoClassDefFoundError. No
            // point risking that call — or attributing its failure reason —
            // for a credential that is already blank/unusable on username
            // alone.
            username = creds.getUserName();
            if (username == null || username.trim().isEmpty()) {
                LAST_INJECTED_FAILURE_REASON.set("credentials null/blank");
                return null;
            }
            password = creds.getPassword();
        } catch (Exception | LinkageError e) {
            // Narrowed from catch (Throwable) — see the NoClassDefFoundError
            // finding in the javadoc above. Honors the documented crash-the-
            // cycle case (Exception, LinkageError) while letting
            // VirtualMachineError/ThreadDeath propagate rather than be
            // silently swallowed.
            LAST_INJECTED_FAILURE_REASON.set(describeInjectedFailure(e));
            return null;
        }
        if (password == null || password.isEmpty()) {
            LAST_INJECTED_FAILURE_REASON.set("credentials null/blank");
            return null;
        }
        return new AmbientCredential(username.trim(), password, "instance");
    }

    /**
     * Load and decrypt the ambient config-user credential from the file-based
     * candidates (override, automation, maintenance — see {@link
     * #buildCandidates()}). Extracted from the original single-source
     * {@code load()} body; unchanged behavior.
     *
     * <p>Candidates are tried in order. The first candidate that exists
     * <em>and</em> is readable wins. A candidate that exists but is
     * unreadable is skipped in favor of the next candidate,
     * <strong>except</strong> for an explicit {@value #SYSPROP_CREDENTIAL_PATH}
     * override, which is the only candidate tried and fails hard if
     * unreadable (a misconfigured override should not be silently masked).
     * If all candidates are exhausted, an {@link IOException} is thrown
     * listing every path tried.
     */
    private static AmbientCredential loadFromFileCandidates(List<Candidate> candidates)
            throws IOException {
        List<String> tried = new ArrayList<>();

        for (Candidate candidate : candidates) {
            Path path = Paths.get(candidate.path);
            tried.add(candidate.path + " (" + candidate.label + ")");

            if (!Files.exists(path)) {
                continue;
            }
            if (!Files.isReadable(path)) {
                if (candidate.hardFailOnUnreadable) {
                    // Explicit override — don't mask a misconfiguration by
                    // silently falling through to a different file.
                    throw new IOException(
                            "AmbientCredential: override credential file exists but is not"
                            + " readable: " + path
                            + " — check file permissions (expected owner-readable by collector user)");
                }
                // Automation/maintenance candidate present but unreadable —
                // fall through to the next candidate (e.g. maintenance)
                // rather than failing hard.
                continue;
            }

            // Found a readable candidate — load it.
            return loadFromPath(path, candidate.label);
        }

        // All candidates exhausted.
        throw new IOException(
                "AmbientCredential: no config-user credential file found or readable at any"
                + " candidate path. Paths tried: " + tried
                + " — this node may be a remote collector;"
                + " supply explicit Suite API credentials instead");
    }

    // -----------------------------------------------------------------------
    // Internal helpers
    // -----------------------------------------------------------------------

    /**
     * A candidate credential file path plus its selection label and
     * unreadable-file failure policy.
     */
    static final class Candidate {
        final String path;
        final String label;
        final boolean hardFailOnUnreadable;

        Candidate(String path, String label, boolean hardFailOnUnreadable) {
            this.path = path;
            this.label = label;
            this.hardFailOnUnreadable = hardFailOnUnreadable;
        }
    }

    /**
     * Build the ordered list of candidate paths to try.
     *
     * <p>Resolution order:
     * <ol>
     *   <li>System property {@value #SYSPROP_CREDENTIAL_PATH} (if set and
     *       non-blank) — the <em>only</em> candidate tried when set.</li>
     *   <li>Automation (preferred): {@value #AUTOMATION_PROPS_PATH}</li>
     *   <li>Maintenance (fallback, only if automation absent/unreadable):
     *       {@value #MAINTENANCE_PROPS_PATH}</li>
     * </ol>
     */
    static List<Candidate> buildCandidates() {
        List<Candidate> candidates = new ArrayList<>();

        String override = System.getProperty(SYSPROP_CREDENTIAL_PATH);
        if (override != null && !override.trim().isEmpty()) {
            candidates.add(new Candidate(override.trim(), "override", true));
            return candidates;
        }

        candidates.add(new Candidate(AUTOMATION_PROPS_PATH, "automation", false));
        candidates.add(new Candidate(MAINTENANCE_PROPS_PATH, "maintenance", false));
        return candidates;
    }

    /**
     * Load and decrypt from a confirmed-readable {@link Path}.
     */
    private static AmbientCredential loadFromPath(Path path, String sourceLabel) throws IOException {
        Properties props = new Properties();
        try (InputStream in = Files.newInputStream(path)) {
            props.load(in);
        }

        String username = props.getProperty(KEY_USERNAME);
        if (username == null || username.trim().isEmpty()) {
            throw new IOException(
                    "AmbientCredential: '" + KEY_USERNAME
                    + "' key missing or empty in " + path);
        }
        username = username.trim();

        String rawPassword = props.getProperty(KEY_PASSWORD);
        if (rawPassword == null) {
            throw new IOException(
                    "AmbientCredential: '" + KEY_PASSWORD
                    + "' key missing in " + path);
        }

        boolean encrypted = Boolean.parseBoolean(
                props.getProperty(KEY_ENCRYPTED, "false").trim());

        String plainPassword;
        if (encrypted) {
            plainPassword = decryptWithPlatformCrypt(rawPassword.trim());
            if (plainPassword == null) {
                // com.vmware.vcops.security.Crypt.decrypt_impl_v2 catches its own
                // failure, logs it at ERROR and returns null (javap, 9.1.1
                // vcops-security). Fail here rather than log in with no password.
                throw new IOException("AmbientCredential: the platform Crypt could not"
                        + " decrypt the password in " + path + " (Crypt logged the reason)");
            }
        } else {
            plainPassword = rawPassword.trim();
        }

        return new AmbientCredential(username, plainPassword, sourceLabel);
    }

    /**
     * Decrypt the maintenance password using the platform's {@link Crypt}.
     *
     * <p>{@code Crypt} is marked {@code @Deprecated} in the SDK jar (it is a
     * platform-internal class), but it is the <strong>only</strong> FIPS-safe
     * decryption path on 9.1 collectors running
     * {@code -Dorg.bouncycastle.fips.approved_only=true}. The deprecation
     * annotation signals "don't depend on this from user code" but the platform
     * ships the class on the collector classpath exactly so adapters can use it
     * for this credential. Suppressing here is deliberate and documented.
     *
     * @param encryptedPassword the encrypted password value from the properties file
     * @return the decrypted plaintext password
     */
    @SuppressWarnings("deprecation")
    private static String decryptWithPlatformCrypt(String encryptedPassword) {
        return Crypt.getDefaultCrypt().decrypt(encryptedPassword);
    }
}
