package com.vcfcf.adapter.stitch;

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
 * Reads the platform maintenance-user credential from
 * {@code maintenanceuser.properties} and decrypts it via the SDK's
 * {@link Crypt} — the only FIPS-safe decryption path on 9.1 collectors.
 *
 * <h3>File path resolution</h3>
 * <p>Candidates are tried in order; first readable hit wins:
 * <ol>
 *   <li>System property {@code vcfcf.suiteapi.credential.path} — explicit
 *       override, useful in test harnesses or non-standard deployments.</li>
 *   <li>Hard-wired default
 *       {@code /usr/lib/vmware-vcops/user/conf/maintenanceuser.properties} —
 *       empirically confirmed on VCF Ops 9.0.2 (devel) and 9.1 (prod).
 *       See {@code context/investigations/suiteapi_ambient_auth_devel_2026_06_09.md}.</li>
 * </ol>
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
 * See {@code lessons/sdk-constants-are-display-names.md}.
 *
 * <h3>File format (keys only — no secret values)</h3>
 * <pre>
 *   username=&lt;principal&gt;    (e.g. maintenanceAdmin — read from file, never assumed)
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
 *   <li>Decryption failure — propagates the exception from {@link Crypt}.</li>
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
     * Empirically proven default path for the maintenance-user properties file.
     * Confirmed on VCF Ops 9.0.2 (devel, April 2026) and 9.1 (prod, 2026-06-09).
     * See {@code context/investigations/suiteapi_ambient_auth_devel_2026_06_09.md}.
     *
     * <p>This is the fallback when no override system property is set. The SDK
     * {@code CommonConstants} class exposes no install-directory path constant
     * that could replace this literal (confirmed by {@code javap} inspection —
     * see class Javadoc for details).
     */
    static final String DEFAULT_PROPS_PATH =
            "/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties";

    /** Property key for the principal name. */
    private static final String KEY_USERNAME = "username";
    /** Property key for the (possibly encrypted) password. */
    private static final String KEY_PASSWORD = "password";
    /** Property key controlling whether the password needs decryption. */
    private static final String KEY_ENCRYPTED = "encrypted";

    private final String username;
    private final String password;

    private AmbientCredential(String username, String password) {
        this.username = username;
        this.password = password;
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

    // -----------------------------------------------------------------------
    // Factory
    // -----------------------------------------------------------------------

    /**
     * Load and decrypt the maintenance-user credential.
     *
     * <p>Candidates are tried in order (see class Javadoc for the resolution
     * chain). The first candidate that exists <em>and</em> is readable wins.
     * If all candidates fail the existence+readability check, an
     * {@link IOException} is thrown listing every path tried.
     *
     * @return loaded and decrypted credential
     * @throws IOException      if no candidate is accessible, or the file is
     *                          malformed
     * @throws RuntimeException if Crypt decryption fails
     */
    public static AmbientCredential load() throws IOException {
        List<String> candidates = buildCandidates();
        List<String> tried = new ArrayList<>();

        for (String candidate : candidates) {
            Path path = Paths.get(candidate);
            tried.add(candidate);

            if (!Files.exists(path)) {
                continue;
            }
            if (!Files.isReadable(path)) {
                // File is present but unreadable — record and skip; don't
                // fall through to a lower-priority candidate that might not
                // be the intended file.
                throw new IOException(
                        "AmbientCredential: maintenance credential file exists but is not"
                        + " readable: " + path
                        + " — check file permissions (expected owner-readable by collector user)");
            }

            // Found a readable candidate — load it.
            return loadFromPath(path);
        }

        // All candidates exhausted.
        throw new IOException(
                "AmbientCredential: maintenance credential file not found at any candidate"
                + " path. Paths tried: " + tried
                + " — this node may be a remote collector;"
                + " supply explicit Suite API credentials instead");
    }

    // -----------------------------------------------------------------------
    // Internal helpers
    // -----------------------------------------------------------------------

    /**
     * Build the ordered list of candidate paths to try.
     *
     * <p>Resolution order:
     * <ol>
     *   <li>System property {@value #SYSPROP_CREDENTIAL_PATH} (if set and non-blank)</li>
     *   <li>Hard-wired default {@value #DEFAULT_PROPS_PATH}</li>
     * </ol>
     */
    static List<String> buildCandidates() {
        List<String> candidates = new ArrayList<>();

        String override = System.getProperty(SYSPROP_CREDENTIAL_PATH);
        if (override != null && !override.trim().isEmpty()) {
            candidates.add(override.trim());
        }

        candidates.add(DEFAULT_PROPS_PATH);
        return candidates;
    }

    /**
     * Load and decrypt from a confirmed-readable {@link Path}.
     */
    private static AmbientCredential loadFromPath(Path path) throws IOException {
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
        } else {
            plainPassword = rawPassword.trim();
        }

        return new AmbientCredential(username, plainPassword);
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
