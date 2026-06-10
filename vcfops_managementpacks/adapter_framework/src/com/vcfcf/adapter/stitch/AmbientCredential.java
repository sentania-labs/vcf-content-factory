package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.security.Crypt;
import com.integrien.alive.common.util.CommonConstants;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Properties;

/**
 * Reads the platform maintenance-user credential from
 * {@code maintenanceuser.properties} and decrypts it via the SDK's
 * {@link Crypt} — the only FIPS-safe decryption path on 9.1 collectors.
 *
 * <h3>File path resolution</h3>
 * <p>The path is derived from {@link CommonConstants#VCOPS} (the runtime-resolved
 * platform user-dir root) if available, falling back to the known default
 * {@code /usr/lib/vmware-vcops/user/conf/maintenanceuser.properties}.
 * Both 9.0.2 and 9.1 resolve to the same path (confirmed READ-ONLY;
 * see {@code context/investigations/suiteapi_ambient_auth_devel_2026_06_09.md}).
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
 *   <li>File absent or unreadable (e.g. remote collector) — throws
 *       {@link IOException} with a clear message. The caller (
 *       {@link SuiteApiStitchClient.Builder}) must then fall back to
 *       explicit credential fields.</li>
 *   <li>Malformed file (missing keys, empty username) — throws
 *       {@link IOException}.</li>
 *   <li>Decryption failure — propagates the exception from {@link Crypt}.</li>
 * </ul>
 */
public final class AmbientCredential {

    /**
     * Known-good default path, confirmed on VCF Ops 9.0.2 and 9.1.
     * Used as fallback when {@link CommonConstants#VCOPS} is null or empty.
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
     * <p>Derives the properties file path from {@link CommonConstants#VCOPS}
     * if that field is non-null and non-empty; otherwise falls back to
     * {@link #DEFAULT_PROPS_PATH}. Both resolve to the same path on all
     * observed VCF Ops versions (9.0.2 and 9.1).
     *
     * <p>If the file does not exist, is unreadable, or is malformed, an
     * {@link IOException} is thrown with an actionable error message so the
     * caller can surface a useful error or activate the explicit-credential
     * fallback.
     *
     * @return loaded and decrypted credential
     * @throws IOException      if the file is absent, unreadable, or malformed
     * @throws RuntimeException if Crypt decryption fails
     */
    public static AmbientCredential load() throws IOException {
        Path path = resolvePropertiesPath();

        if (!Files.exists(path)) {
            throw new IOException(
                    "AmbientCredential: maintenance credential file not found: " + path
                    + " — this node may be a remote collector; "
                    + "supply explicit Suite API credentials instead");
        }
        if (!Files.isReadable(path)) {
            throw new IOException(
                    "AmbientCredential: maintenance credential file not readable: " + path
                    + " — check file permissions (expected owner-readable by collector user)");
        }

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

    // -----------------------------------------------------------------------
    // Internal helpers
    // -----------------------------------------------------------------------

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

    /**
     * Derive the properties file path.
     *
     * <p>Prefers {@code CommonConstants.VCOPS + "/conf/maintenanceuser.properties"}
     * (SDK-derived, adapts automatically if the platform ever moves the user dir).
     * Falls back to {@link #DEFAULT_PROPS_PATH} if {@code VCOPS} is null, empty,
     * or inaccessible.
     */
    static Path resolvePropertiesPath() {
        try {
            String vcopsDir = CommonConstants.VCOPS;
            if (vcopsDir != null && !vcopsDir.trim().isEmpty()) {
                return Paths.get(vcopsDir.trim(), "conf", "maintenanceuser.properties");
            }
        } catch (Exception ignored) {
            // CommonConstants static initializer failed (not running in-collector);
            // fall through to the known default.
        }
        return Paths.get(DEFAULT_PROPS_PATH);
    }
}
