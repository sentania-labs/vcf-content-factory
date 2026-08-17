package com.vcfcf.adapter;

import java.util.ArrayList;
import java.util.List;

/**
 * Lightweight unit tests for {@link VcfCfAdapter#applyBcMirrorTransport}
 * (the DEF-005 BC-mirror transport fix), {@link VcfCfAdapter#isFipsApprovedOnly()},
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
 *   <li>{@link VcfCfAdapter#isFipsApprovedOnly()} reflects the
 *       {@code org.bouncycastle.fips.approved_only} system property.</li>
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
        testIsFipsApprovedOnlyDefaultFalse();
        testIsFipsApprovedOnlyReflectsSystemProperty();
        testApplyBcMirrorTransportLoopback();
        testApplyBcMirrorTransportRemoteAlsoTrustAllIgnoreHostname();
        testInsecureSslContextAcceptsHostnameMismatchOverHttpClient();
        testValidatingContextRejectsHostnameMismatchOverHttpClient();
        report();
    }

    // -----------------------------------------------------------------------
    // isFipsApprovedOnly
    // -----------------------------------------------------------------------

    private static void testIsFipsApprovedOnlyDefaultFalse() {
        String prior = System.clearProperty("org.bouncycastle.fips.approved_only");
        try {
            assertFalse("isFipsApprovedOnly() is false when the property is unset",
                    VcfCfAdapter.isFipsApprovedOnly());
        } finally {
            if (prior != null) {
                System.setProperty("org.bouncycastle.fips.approved_only", prior);
            }
        }
    }

    private static void testIsFipsApprovedOnlyReflectsSystemProperty() {
        String prior = System.getProperty("org.bouncycastle.fips.approved_only");
        try {
            System.setProperty("org.bouncycastle.fips.approved_only", "true");
            assertTrue("isFipsApprovedOnly() is true when the property is \"true\"",
                    VcfCfAdapter.isFipsApprovedOnly());

            System.setProperty("org.bouncycastle.fips.approved_only", "false");
            assertFalse("isFipsApprovedOnly() is false when the property is \"false\"",
                    VcfCfAdapter.isFipsApprovedOnly());
        } finally {
            if (prior == null) {
                System.clearProperty("org.bouncycastle.fips.approved_only");
            } else {
                System.setProperty("org.bouncycastle.fips.approved_only", prior);
            }
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
        String javaHome = System.getProperty("java.home");
        java.io.File keytoolFile = new java.io.File(javaHome,
                "bin" + java.io.File.separator + "keytool");
        if (!keytoolFile.isFile()) {
            System.out.println("  SKIP: hostname-mismatch TLS handshake test (keytool not found "
                    + "at " + keytoolFile + " (this JDK image has no keytool)");
            return;
        }

        java.nio.file.Path tmpDir = java.nio.file.Files.createTempDirectory("vcfcf-adapter-test-ssl");
        try {
            java.nio.file.Path keystorePath = tmpDir.resolve("mismatched.p12");
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
                    "-dname", "CN=" + MISMATCHED_CERT_CN,
                    "-ext", "SAN=dns:" + MISMATCHED_CERT_CN)
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
                int port = server.getAddress().getPort();
                String baseUrl = "https://127.0.0.1:" + port + "/";
                // ks (a PrivateKeyEntry keystore) doubles as a trust store: JSSE's
                // TrustManagerFactory accepts the certificate chain attached to a
                // PrivateKeyEntry as a trusted cert, same as it would a plain
                // TrustedCertificateEntry.
                test.run(baseUrl, ks);
            } finally {
                server.stop(0);
            }
        } finally {
            deleteRecursivelyQuietly(tmpDir);
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
