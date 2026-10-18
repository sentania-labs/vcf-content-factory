package com.vcfcf.adapter;

import java.util.ArrayList;
import java.util.List;

/**
 * Lightweight unit tests for {@link VcfCfAdapter#applyBcMirrorTransport}
 * (the DEF-005 BC-mirror transport fix), the FIPS-mode cluster-truststore
 * transport ({@link VcfCfAdapter#applyClusterTruststoreTransport}, issue #215),
 * and {@link VcfCfAdapter#insecureSslContext()} (issue #82 hostname-verification
 * fix).
 *
 * <p>No JUnit required — call via {@code main()}. Covers:
 * <ol>
 *   <li>Non-FIPS (default) mode: {@code applyBcMirrorTransport} — the helper
 *       {@link VcfCfAdapter#openPlatformConnection(String)} delegates to for
 *       its trust/hostname wiring — sets a trust-all {@code SSLSocketFactory}
 *       and an all-true {@code HostnameVerifier}, unconditionally (no
 *       loopback-vs-remote branching — the fix deliberately removed the
 *       earlier peer-gating so the transport mirrors the vendor
 *       {@code SuiteAPIClient} exactly; DEF-005: "mirror the BC behavior,
 *       don't invent new ways").</li>
 *   <li>FIPS mode (issue #215): detection is {@code IS_FIPS} with
 *       {@code Boolean.valueOf} semantics; the cluster SSL directory is
 *       {@code VCOPS_DATA_VCOPS}/user/conf/ssl; a real TLS handshake through
 *       {@code applyClusterTruststoreTransport} succeeds when the server
 *       chain is in a temp {@code tcserver.truststore} (hostname mismatch
 *       ignored) and fails when it is not; the plain and encrypted password
 *       keys resolve as the vendor does; and every unreadable input (missing
 *       truststore, missing or keyless {@code storePass.properties}, decrypt
 *       failure, wrong password, BCFKS unavailable) fails loud naming the
 *       path, with no trust-all fallback.</li>
 *   <li>{@link VcfCfAdapter#insecureSslContext()} (issue #82): a real TLS
 *       handshake, over {@code java.net.http.HttpClient}, against a server
 *       certificate whose name does not match the address dialed. Asserts the
 *       handshake succeeds under {@code insecureSslContext()} and still fails
 *       under a normal validating context, so this test would catch a future
 *       change that accidentally makes everything insecure.</li>
 * </ol>
 *
 * <p>{@code openPlatformConnection(String)} itself (the instance method) is
 * NOT exercised here — instantiating a live {@link VcfCfAdapter} subclass
 * requires the collector's log4j-core runtime classpath (pulled in by
 * {@code AdapterBase}'s constructor), which is not available outside the
 * appliance. This is the same limitation documented in
 * {@code SuiteApiStitchClientTest} for behavior that depends on a live
 * platform connection; see its class javadoc. The transport wiring itself
 * ({@code applyBcMirrorTransport}) was extracted to a static, instance-free
 * helper specifically so it CAN be unit-tested here without that dependency.
 *
 * <p>Run:
 * <pre>
 *   javac -cp adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         adapter_framework/test/com/vcfcf/adapter/VcfCfAdapterTest.java \
 *         -d build/test-classes
 *   java -cp build/test-classes:adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         com.vcfcf.adapter.VcfCfAdapterTest
 * </pre>
 */
public class VcfCfAdapterTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;

    public static void main(String[] args) throws Exception {
        testIsFipsModeEnabledMirrorsBooleanValueOf();
        testClusterSslDirectoryMirrorsVendorConstants();
        testDescribeTransportModeNamesSignal();
        testApplyBcMirrorTransportLoopback();
        testApplyBcMirrorTransportRemoteAlsoTrustAllIgnoreHostname();
        testInsecureSslContextAcceptsHostnameMismatchOverHttpClient();
        testValidatingContextRejectsHostnameMismatchOverHttpClient();
        testFipsTransportTrustsClusterTruststoreIgnoresHostname();
        testFipsTransportRejectsCertNotInClusterTruststore();
        testFipsTransportDecryptsEncryptedPassword();
        testFipsTransportMissingTruststoreFailsLoud();
        testFipsTransportMissingStorePassFailsLoud();
        testFipsTransportNoPasswordKeyFailsLoud();
        testFipsTransportDecryptFailureFailsLoud();
        testFipsTransportWrongPasswordFailsLoud();
        testFipsTransportBcfksUnavailableFailsLoud();
        report();
    }

    // -----------------------------------------------------------------------
    // FIPS mode detection and cluster SSL directory (issue #215)
    // -----------------------------------------------------------------------

    private static void testIsFipsModeEnabledMirrorsBooleanValueOf() {
        // Vendor: Constants.FIPS_MODE_ENABLED = Boolean.valueOf(System.getenv("IS_FIPS")).
        assertFalse("isFipsModeEnabled(null) is false (IS_FIPS unset)",
                VcfCfAdapter.isFipsModeEnabled((String) null));
        assertTrue("isFipsModeEnabled(\"true\") is true",
                VcfCfAdapter.isFipsModeEnabled("true"));
        assertTrue("isFipsModeEnabled(\"TRUE\") is true (case-insensitive like Boolean.valueOf)",
                VcfCfAdapter.isFipsModeEnabled("TRUE"));
        assertFalse("isFipsModeEnabled(\"false\") is false",
                VcfCfAdapter.isFipsModeEnabled("false"));
        assertFalse("isFipsModeEnabled(\"1\") is false (Boolean.valueOf semantics)",
                VcfCfAdapter.isFipsModeEnabled("1"));
        assertTrue("isFipsModeEnabled() agrees with the real IS_FIPS environment variable",
                VcfCfAdapter.isFipsModeEnabled()
                        == Boolean.valueOf(System.getenv("IS_FIPS")).booleanValue());
    }

    private static void testClusterSslDirectoryMirrorsVendorConstants() throws Exception {
        assertTrue("clusterSslDirectory(null) defaults to /data/vcops/user/conf/ssl",
                VcfCfAdapter.clusterSslDirectory((String) null)
                        .equals(java.nio.file.Paths.get("/data/vcops/user/conf/ssl")));
        assertTrue("clusterSslDirectory(root) resolves root/user/conf/ssl",
                VcfCfAdapter.clusterSslDirectory("/srv/x")
                        .equals(java.nio.file.Paths.get("/srv/x/user/conf/ssl")));
        String prior = System.getProperty("VCOPS_DATA_VCOPS");
        java.nio.file.Path root = java.nio.file.Files.createTempDirectory("vcfcf-vcops-data");
        try {
            System.setProperty("VCOPS_DATA_VCOPS", root.toString());
            assertTrue("clusterSslDirectory() reads the VCOPS_DATA_VCOPS system property",
                    VcfCfAdapter.clusterSslDirectory()
                            .equals(root.resolve("user").resolve("conf").resolve("ssl")));
        } finally {
            restoreProperty("VCOPS_DATA_VCOPS", prior);
            deleteRecursivelyQuietly(root);
        }
    }

    /** U+2014, built from its code point so this source file carries no em-dash. */
    private static final String EM_DASH = String.valueOf((char) 0x2014);

    private static void testDescribeTransportModeNamesSignal() {
        java.nio.file.Path dir = java.nio.file.Paths.get("/data/vcops/user/conf/ssl");
        String fips = VcfCfAdapter.describeTransportMode(true, dir, null);
        assertTrue("FIPS mode line names the IS_FIPS=true signal and the truststore path",
                fips.contains("mode=FIPS") && fips.contains("IS_FIPS=true")
                        && fips.contains("/data/vcops/user/conf/ssl/tcserver.truststore")
                        && fips.contains("BCFKS"));
        String nonFips = VcfCfAdapter.describeTransportMode(false, dir, "true");
        assertTrue("non-FIPS mode line names the signal and prints approved_only as a diagnostic",
                nonFips.contains("mode=non-FIPS") && nonFips.contains("IS_FIPS is not true")
                        && nonFips.contains("org.bouncycastle.fips.approved_only=true"));
        assertFalse("mode lines carry no em-dash",
                fips.contains(EM_DASH) || nonFips.contains(EM_DASH));
    }

    // -----------------------------------------------------------------------
    // applyClusterTruststoreTransport: FIPS branch (issue #215)
    //
    // Real TLS handshake over HttpsURLConnection against a 127.0.0.1 server
    // whose cert is issued to a mismatched name. The cluster truststore and
    // storePass.properties live under a temp VCOPS_DATA_VCOPS root, located
    // through clusterSslDirectory() exactly as production does. Store type is
    // PKCS12 here: the stock JDK has no BCFKS provider (production passes
    // BCFKS; testFipsTransportBcfksUnavailableFailsLoud covers that type).
    // -----------------------------------------------------------------------

    private static final String TEST_STORE_TYPE = "PKCS12";
    private static final String TRUSTSTORE_PASSWORD = "cluster-pass";

    private static void testFipsTransportTrustsClusterTruststoreIgnoresHostname()
            throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir, serverKs);
            writeStorePass(sslDir, "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            int status = fipsRequest(baseUrl, sslDir, s -> {
                throw new AssertionError("decryptor must not run when the plain key is present");
            });
            assertTrue("FIPS transport: handshake succeeds when the server chain is in the "
                    + "cluster truststore, despite the hostname mismatch (verify=true, "
                    + "ignoreHostName=true)", status == 200);
        });
    }

    private static void testFipsTransportRejectsCertNotInClusterTruststore() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir, otherKs);
            writeStorePass(sslDir, "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            try {
                fipsRequest(baseUrl, sslDir, s -> s);
                FAILURES.add("FIPS transport: handshake against a cert NOT in the cluster "
                        + "truststore should have failed (this would mean trust-all)");
            } catch (javax.net.ssl.SSLHandshakeException e) {
                assertTrue("FIPS transport: cert not in the cluster truststore fails the "
                        + "handshake (chain is verified, not trust-all)", true);
            }
        });
    }

    private static void testFipsTransportDecryptsEncryptedPassword() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir, serverKs);
            writeStorePass(sslDir, "ssltruststorePassword.encrypted=ENC("
                    + new StringBuilder(TRUSTSTORE_PASSWORD).reverse() + ")\n");
            int status = fipsRequest(baseUrl, sslDir, enc -> {
                // Stand-in for Crypt.decrypt: unwrap ENC(...) and reverse.
                String inner = enc.substring(4, enc.length() - 1);
                return new StringBuilder(inner).reverse().toString();
            });
            assertTrue("FIPS transport: ssltruststorePassword.encrypted is decrypted and "
                    + "opens the truststore when the plain key is absent", status == 200);
        });
    }

    private static void testFipsTransportMissingTruststoreFailsLoud() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeStorePass(sslDir, "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            assertFipsFailure(baseUrl, sslDir, TEST_STORE_TYPE, s -> s,
                    "missing tcserver.truststore",
                    sslDir.resolve("tcserver.truststore").toString());
        });
    }

    private static void testFipsTransportMissingStorePassFailsLoud() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir, serverKs);
            assertFipsFailure(baseUrl, sslDir, TEST_STORE_TYPE, s -> s,
                    "missing storePass.properties",
                    sslDir.resolve("storePass.properties").toString());
        });
    }

    private static void testFipsTransportNoPasswordKeyFailsLoud() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir, serverKs);
            writeStorePass(sslDir, "sslkeystorePassword=unrelated\n");
            assertFipsFailure(baseUrl, sslDir, TEST_STORE_TYPE, s -> s,
                    "storePass.properties without either truststore key",
                    "ssltruststorePassword.encrypted");
        });
    }

    private static void testFipsTransportDecryptFailureFailsLoud() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir, serverKs);
            writeStorePass(sslDir, "ssltruststorePassword.encrypted=opaque\n");
            String reason = assertFipsFailure(baseUrl, sslDir, TEST_STORE_TYPE, s -> {
                throw new IllegalStateException("secret-material-" + s);
            }, "decrypt failure", sslDir.resolve("storePass.properties").toString());
            assertFalse("decrypt failure message does not echo the exception message "
                    + "(which may carry secret material)",
                    reason != null && reason.contains("secret-material"));
        });
    }

    private static void testFipsTransportWrongPasswordFailsLoud() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir, serverKs);
            writeStorePass(sslDir, "ssltruststorePassword=wrong\n");
            assertFipsFailure(baseUrl, sslDir, TEST_STORE_TYPE, s -> s,
                    "wrong truststore password",
                    sslDir.resolve("tcserver.truststore").toString());
        });
    }

    private static void testFipsTransportBcfksUnavailableFailsLoud() throws Exception {
        // Production passes BCFKS. Off-appliance (no BC FIPS provider) it must
        // fail loud with the type and path named, never fall back.
        boolean bcfksAvailable;
        try {
            java.security.KeyStore.getInstance("BCFKS");
            bcfksAvailable = true;
        } catch (java.security.KeyStoreException e) {
            bcfksAvailable = false;
        }
        if (bcfksAvailable) {
            System.out.println("  SKIP: BCFKS-unavailable test (this JVM has a BCFKS provider)");
            return;
        }
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir, serverKs);
            writeStorePass(sslDir, "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            String reason = assertFipsFailure(baseUrl, sslDir,
                    VcfCfAdapter.FIPS_TRUSTSTORE_TYPE, s -> s,
                    "BCFKS type unavailable", sslDir.resolve("tcserver.truststore").toString());
            assertTrue("BCFKS-unavailable failure names the store type",
                    reason != null && reason.contains("BCFKS"));
        });
    }

    /** Issue a GET through the FIPS transport; returns the HTTP status. */
    private static int fipsRequest(String baseUrl, java.nio.file.Path sslDir,
            java.util.function.UnaryOperator<String> decryptor) throws Exception {
        javax.net.ssl.HttpsURLConnection https =
                (javax.net.ssl.HttpsURLConnection) new java.net.URL(baseUrl).openConnection();
        VcfCfAdapter.applyClusterTruststoreTransport(https, sslDir, TEST_STORE_TYPE, decryptor);
        https.setConnectTimeout(10_000);
        https.setReadTimeout(10_000);
        try {
            return https.getResponseCode();
        } finally {
            https.disconnect();
        }
    }

    /**
     * Assert the FIPS transport throws an IOException whose message contains
     * {@code mustContain}, and that the connection was left on the JDK
     * defaults (no trust-all factory or all-true verifier installed).
     * Returns the message.
     */
    private static String assertFipsFailure(String baseUrl, java.nio.file.Path sslDir,
            String storeType, java.util.function.UnaryOperator<String> decryptor,
            String label, String mustContain) throws Exception {
        javax.net.ssl.HttpsURLConnection https =
                (javax.net.ssl.HttpsURLConnection) new java.net.URL(baseUrl).openConnection();
        javax.net.ssl.SSLSocketFactory defaultFactory = https.getSSLSocketFactory();
        javax.net.ssl.HostnameVerifier defaultVerifier = https.getHostnameVerifier();
        try {
            VcfCfAdapter.applyClusterTruststoreTransport(https, sslDir, storeType, decryptor);
            FAILURES.add("FIPS transport (" + label + "): expected an IOException, got none");
            return null;
        } catch (java.io.IOException e) {
            String msg = String.valueOf(e.getMessage());
            assertTrue("FIPS transport (" + label + "): fails loud naming " + mustContain
                    + ". Actual: " + msg, msg.contains(mustContain));
            assertTrue("FIPS transport (" + label + "): no trust-all fallback, the "
                    + "connection keeps the JDK default socket factory and hostname verifier",
                    https.getSSLSocketFactory() == defaultFactory
                            && https.getHostnameVerifier() == defaultVerifier);
            return msg;
        }
    }

    @FunctionalInterface
    private interface FipsFixtureTest {
        void run(String baseUrl, java.security.KeyStore serverKs,
                java.security.KeyStore otherKs, java.nio.file.Path sslDir) throws Exception;
    }

    /**
     * Server on 127.0.0.1 with a cert for {@link #MISMATCHED_CERT_CN}, a second
     * unrelated keypair, and an empty cluster SSL directory under a temp
     * {@code VCOPS_DATA_VCOPS} root (resolved through
     * {@link VcfCfAdapter#clusterSslDirectory()}). SKIPs without keytool.
     */
    private static void withFipsFixture(FipsFixtureTest test) throws Exception {
        java.io.File keytoolFile = keytool();
        if (keytoolFile == null) {
            System.out.println("  SKIP: FIPS cluster-truststore test (no keytool in java.home)");
            return;
        }
        java.nio.file.Path tmpDir = java.nio.file.Files.createTempDirectory("vcfcf-fips-test");
        String prior = System.getProperty("VCOPS_DATA_VCOPS");
        try {
            java.security.KeyStore serverKs = generateKeyPair(keytoolFile,
                    tmpDir.resolve("server.p12"), MISMATCHED_CERT_CN);
            java.security.KeyStore otherKs = generateKeyPair(keytoolFile,
                    tmpDir.resolve("other.p12"), "unrelated.example.com");
            java.nio.file.Path vcopsData = tmpDir.resolve("vcops");
            System.setProperty("VCOPS_DATA_VCOPS", vcopsData.toString());
            java.nio.file.Path sslDir = VcfCfAdapter.clusterSslDirectory();
            java.nio.file.Files.createDirectories(sslDir);
            withHttpsServer(serverKs, baseUrl -> test.run(baseUrl, serverKs, otherKs, sslDir));
        } finally {
            restoreProperty("VCOPS_DATA_VCOPS", prior);
            deleteRecursivelyQuietly(tmpDir);
        }
    }

    /** Write {@code ks}'s certificate as the only trusted entry of tcserver.truststore. */
    private static void writeTruststore(java.nio.file.Path sslDir, java.security.KeyStore ks)
            throws Exception {
        java.security.KeyStore ts = java.security.KeyStore.getInstance(TEST_STORE_TYPE);
        ts.load(null, null);
        ts.setCertificateEntry("cluster-ca", ks.getCertificate("vcfcf-test"));
        try (java.io.OutputStream out = java.nio.file.Files.newOutputStream(
                sslDir.resolve("tcserver.truststore"))) {
            ts.store(out, TRUSTSTORE_PASSWORD.toCharArray());
        }
    }

    private static void writeStorePass(java.nio.file.Path sslDir, String content)
            throws Exception {
        java.nio.file.Files.write(sslDir.resolve("storePass.properties"),
                content.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));
    }

    private static void restoreProperty(String key, String prior) {
        if (prior == null) {
            System.clearProperty(key);
        } else {
            System.setProperty(key, prior);
        }
    }

    // -----------------------------------------------------------------------
    // applyBcMirrorTransport — BC-mirror transport (non-FIPS default)
    // -----------------------------------------------------------------------

    private static void testApplyBcMirrorTransportLoopback() throws Exception {
        assertBcMirrorTransport("https://localhost/suite-api/api/auth/token/acquire");
    }

    private static void testApplyBcMirrorTransportRemoteAlsoTrustAllIgnoreHostname()
            throws Exception {
        // DEF-005: the fix removed loopback/remote peer-gating — the transport
        // is unconditional trust-all + ignore-hostname, exactly matching the
        // vendor SuiteAPIClient (which does not peer-gate either). Same
        // wiring for a loopback URL and a non-loopback (remote/CP) URL.
        assertBcMirrorTransport("https://vcf-ops.example.com/suite-api/api/auth/token/acquire");
    }

    private static void assertBcMirrorTransport(String url) throws Exception {
        java.net.URL u = new java.net.URL(url);
        java.net.URLConnection conn = u.openConnection();
        if (!(conn instanceof javax.net.ssl.HttpsURLConnection)) {
            FAILURES.add("openConnection(" + url + ") did not return an HttpsURLConnection");
            return;
        }
        javax.net.ssl.HttpsURLConnection https = (javax.net.ssl.HttpsURLConnection) conn;

        VcfCfAdapter.applyBcMirrorTransport(https);

        // Trust half: trust-all SSLSocketFactory is set (built from
        // VcfCfAdapter.insecureSslContext(), the same trust-all
        // X509ExtendedTrustManager used for the target-system opt-out path).
        assertTrue("applyBcMirrorTransport(" + url + "): SSLSocketFactory is set",
                https.getSSLSocketFactory() != null);

        // Hostname half: ignore-hostname — verify(host, session) returns true
        // unconditionally, for an arbitrary mismatched host AND the URL's own host.
        javax.net.ssl.HostnameVerifier hv = https.getHostnameVerifier();
        assertTrue("applyBcMirrorTransport(" + url + "): hostname verifier accepts an "
                + "arbitrary hostname (ignore-hostname mirror)",
                hv.verify("this-host-does-not-match-anything.invalid", null));
        assertTrue("applyBcMirrorTransport(" + url + "): hostname verifier also accepts "
                + "the connection's own host",
                hv.verify(u.getHost(), null));
    }

    // -----------------------------------------------------------------------
    // insecureSslContext, issue #82 hostname-verification fix
    //
    // Real TLS handshake, over java.net.http.HttpClient, against a server
    // certificate issued to a name that does not match the address dialed
    // (127.0.0.1). Before the fix, insecureSslContext()'s trust-all
    // javax.net.ssl.X509TrustManager was silently wrapped by JSSE in
    // sun.security.ssl.AbstractTrustManagerWrapper, which re-applies the
    // endpoint identity (hostname) check that HttpClient always requests.
    // so the handshake failed with a CertificateException even with the
    // trust-all manager in place. The fix (X509ExtendedTrustManager) makes
    // JSSE use the manager directly, so the identity check never runs.
    // -----------------------------------------------------------------------

    /** The self-signed cert's subject/SAN, deliberately not "127.0.0.1". */
    private static final String MISMATCHED_CERT_CN = "wrong.example.com";
    private static final String KEYSTORE_PASSWORD = "changeit";

    private static void testInsecureSslContextAcceptsHostnameMismatchOverHttpClient()
            throws Exception {
        withMismatchedCertServer((baseUrl, ignoredTrustStore) -> {
            java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
                    .sslContext(VcfCfAdapter.insecureSslContext())
                    .build();
            java.net.http.HttpResponse<String> resp;
            try {
                resp = client.send(
                        java.net.http.HttpRequest.newBuilder(java.net.URI.create(baseUrl)).build(),
                        java.net.http.HttpResponse.BodyHandlers.ofString());
            } catch (Exception e) {
                FAILURES.add("insecureSslContext(): handshake against a hostname-mismatched "
                        + "cert should have succeeded but threw " + e);
                return;
            }
            assertTrue("insecureSslContext(): HTTP request against a hostname-mismatched "
                    + "cert succeeds", resp.statusCode() == 200);
        });
    }

    private static void testValidatingContextRejectsHostnameMismatchOverHttpClient()
            throws Exception {
        withMismatchedCertServer((baseUrl, trustStore) -> {
            // A normal validating context: trusts the server's cert chain (so any
            // failure below is purely the hostname check, not an untrusted-CA
            // failure) but performs the standard endpoint identity check that
            // HttpClient always requests.
            javax.net.ssl.TrustManagerFactory tmf = javax.net.ssl.TrustManagerFactory
                    .getInstance(javax.net.ssl.TrustManagerFactory.getDefaultAlgorithm());
            tmf.init(trustStore);
            javax.net.ssl.SSLContext validatingCtx = javax.net.ssl.SSLContext.getInstance("TLS");
            validatingCtx.init(null, tmf.getTrustManagers(), null);

            java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
                    .sslContext(validatingCtx)
                    .build();
            // Assert the SPECIFIC identity failure, not merely "something threw".
            // a bind refusal, a connect timeout, or a DNS hiccup would also throw
            // and would otherwise pass this guard even though it proves nothing
            // about hostname verification.
            try {
                client.send(
                        java.net.http.HttpRequest.newBuilder(java.net.URI.create(baseUrl)).build(),
                        java.net.http.HttpResponse.BodyHandlers.ofString());
                FAILURES.add("validating context: handshake against a hostname-mismatched "
                        + "cert should have failed but succeeded (sanity check, this would "
                        + "catch a fix that disables everything)");
            } catch (Exception e) {
                Throwable identityFailure = findIdentityFailureCause(e);
                assertTrue("validating context: handshake fails with the hostname-identity "
                        + "failure (SSLHandshakeException / CertificateException naming "
                        + "\"subject alternative names\"), not merely some exception. "
                        + "Actual: " + e,
                        identityFailure != null);
            }
        });
    }

    /**
     * Walk {@code e}'s cause chain looking for the specific TLS hostname-identity
     * failure: an {@link javax.net.ssl.SSLHandshakeException} or
     * {@link java.security.cert.CertificateException} whose message names the
     * "subject alternative names" mismatch. Returns {@code null} if the chain
     * does not contain one. Used to distinguish the real identity-check failure
     * from an unrelated connection failure (bind refusal, timeout, DNS hiccup)
     * that would also throw but proves nothing about hostname verification.
     */
    private static Throwable findIdentityFailureCause(Throwable e) {
        for (Throwable t = e; t != null; t = t.getCause()) {
            boolean rightType = t instanceof javax.net.ssl.SSLHandshakeException
                    || t instanceof java.security.cert.CertificateException;
            String msg = t.getMessage();
            if (rightType && msg != null
                    && msg.toLowerCase(java.util.Locale.ROOT).contains("subject alternative name")) {
                return t;
            }
        }
        return null;
    }

    @FunctionalInterface
    private interface MismatchedCertServerTest {
        void run(String baseUrl, java.security.KeyStore trustStore) throws Exception;
    }

    private static final java.time.Duration KEYTOOL_TIMEOUT = java.time.Duration.ofSeconds(30);

    /**
     * Stand up a local HTTPS endpoint (on 127.0.0.1) whose certificate is
     * issued to {@link #MISMATCHED_CERT_CN}, not the loopback address used to
     * connect, run {@code test} against it, then tear the server down.
     *
     * <p>The keypair/certificate is generated fresh per invocation with the
     * JDK's own {@code keytool} (no checked-in fixture, avoids a stale/expired
     * cert bit-rotting in the repo). Resolved from {@code java.home} rather than
     * {@code PATH} since that is the JDK actually running this test; if that
     * {@code java.home} has no {@code bin/keytool} (a jlink'd/JRE-only image),
     * this SKIPs the caller rather than failing the suite. Same pattern
     * {@code AmbientCredentialTest} uses for the unavailable-{@code Crypt} case.
     */
    private static void withMismatchedCertServer(MismatchedCertServerTest test) throws Exception {
        java.io.File keytoolFile = keytool();
        if (keytoolFile == null) {
            System.out.println("  SKIP: hostname-mismatch TLS handshake test (keytool not found "
                    + "under " + System.getProperty("java.home") + "; this JDK image has no keytool)");
            return;
        }

        java.nio.file.Path tmpDir = java.nio.file.Files.createTempDirectory("vcfcf-adapter-test-ssl");
        try {
            java.security.KeyStore ks = generateKeyPair(keytoolFile,
                    tmpDir.resolve("mismatched.p12"), MISMATCHED_CERT_CN);
            // ks (a PrivateKeyEntry keystore) doubles as a trust store: JSSE's
            // TrustManagerFactory accepts the certificate chain attached to a
            // PrivateKeyEntry as a trusted cert, same as it would a plain
            // TrustedCertificateEntry.
            withHttpsServer(ks, baseUrl -> test.run(baseUrl, ks));
        } finally {
            deleteRecursivelyQuietly(tmpDir);
        }
    }

    /** The running JDK's keytool, or {@code null} when this image has none. */
    private static java.io.File keytool() {
        java.io.File keytoolFile = new java.io.File(System.getProperty("java.home"),
                "bin" + java.io.File.separator + "keytool");
        return keytoolFile.isFile() ? keytoolFile : null;
    }

    /** Generate a fresh self-signed RSA keypair for {@code cn} (alias vcfcf-test) and load it. */
    private static java.security.KeyStore generateKeyPair(java.io.File keytoolFile,
            java.nio.file.Path keystorePath, String cn) throws Exception {
        Process p = new ProcessBuilder(
                keytoolFile.getPath(),
                "-genkeypair",
                "-alias", "vcfcf-test",
                "-keyalg", "RSA",
                "-keysize", "2048",
                "-validity", "1",
                "-storetype", "PKCS12",
                "-keystore", keystorePath.toString(),
                "-storepass", KEYSTORE_PASSWORD,
                "-keypass", KEYSTORE_PASSWORD,
                "-dname", "CN=" + cn,
                "-ext", "SAN=dns:" + cn)
                .redirectErrorStream(true)
                .start();
        String keytoolOutput = new String(p.getInputStream().readAllBytes(),
                java.nio.charset.StandardCharsets.UTF_8);
        boolean finished = p.waitFor(KEYTOOL_TIMEOUT.toSeconds(), java.util.concurrent.TimeUnit.SECONDS);
        if (!finished) {
            p.destroyForcibly();
            throw new IllegalStateException("keytool -genkeypair did not finish within "
                    + KEYTOOL_TIMEOUT + " (process killed): " + keytoolOutput);
        }
        int exit = p.exitValue();
        if (exit != 0) {
            throw new IllegalStateException("keytool -genkeypair failed (exit " + exit
                    + "): " + keytoolOutput);
        }
        java.security.KeyStore ks = java.security.KeyStore.getInstance("PKCS12");
        try (java.io.InputStream in = java.nio.file.Files.newInputStream(keystorePath)) {
            ks.load(in, KEYSTORE_PASSWORD.toCharArray());
        }
        return ks;
    }

    @FunctionalInterface
    private interface BaseUrlTest {
        void run(String baseUrl) throws Exception;
    }

    /** Serve 200 {"ok":true} on 127.0.0.1 with {@code ks}'s key, run {@code test}, stop. */
    private static void withHttpsServer(java.security.KeyStore ks, BaseUrlTest test)
            throws Exception {
        javax.net.ssl.KeyManagerFactory kmf = javax.net.ssl.KeyManagerFactory
                .getInstance("SunX509");
        kmf.init(ks, KEYSTORE_PASSWORD.toCharArray());
        javax.net.ssl.SSLContext serverCtx = javax.net.ssl.SSLContext.getInstance("TLS");
        serverCtx.init(kmf.getKeyManagers(), null, null);

        com.sun.net.httpserver.HttpsServer server = com.sun.net.httpserver.HttpsServer.create(
                new java.net.InetSocketAddress("127.0.0.1", 0), 0);
        server.setHttpsConfigurator(new com.sun.net.httpserver.HttpsConfigurator(serverCtx));
        server.createContext("/", ex -> {
            byte[] body = "{\"ok\":true}".getBytes(java.nio.charset.StandardCharsets.UTF_8);
            ex.sendResponseHeaders(200, body.length);
            try (java.io.OutputStream os = ex.getResponseBody()) {
                os.write(body);
            }
        });
        server.start();
        try {
            test.run("https://127.0.0.1:" + server.getAddress().getPort() + "/");
        } finally {
            server.stop(0);
        }
    }

    /**
     * Best-effort recursive delete that never throws. Used from a {@code finally}
     * block so a leftover-file cleanup failure can never mask the real assertion
     * failure from the test it is cleaning up after.
     */
    private static void deleteRecursivelyQuietly(java.nio.file.Path root) {
        try {
            if (!java.nio.file.Files.exists(root)) {
                return;
            }
            try (java.util.stream.Stream<java.nio.file.Path> walk = java.nio.file.Files.walk(root)) {
                walk.sorted(java.util.Comparator.reverseOrder())
                        .forEach(p -> {
                            try {
                                java.nio.file.Files.deleteIfExists(p);
                            } catch (Exception ignored) {
                                // Best-effort only, see method javadoc.
                            }
                        });
            }
        } catch (Exception ignored) {
            // Best-effort only, see method javadoc.
        }
    }

    // -----------------------------------------------------------------------
    // Harness
    // -----------------------------------------------------------------------

    private static void assertTrue(String label, boolean cond) {
        if (cond) {
            System.out.println("  PASS: " + label);
            passed++;
        } else {
            System.out.println("  FAIL: " + label);
            FAILURES.add(label);
        }
    }

    private static void assertFalse(String label, boolean cond) {
        assertTrue(label, !cond);
    }

    private static void report() {
        int total = passed + FAILURES.size();
        System.out.println();
        if (FAILURES.isEmpty()) {
            System.out.println("OK: " + passed + "/" + total + " tests passed.");
        } else {
            System.out.println("FAIL: " + FAILURES.size() + "/" + total
                    + " tests failed: " + FAILURES);
            System.exit(1);
        }
    }
}
