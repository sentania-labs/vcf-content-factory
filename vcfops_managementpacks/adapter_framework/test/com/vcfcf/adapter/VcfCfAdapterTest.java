package com.vcfcf.adapter;

import java.util.ArrayList;
import java.util.List;

/**
 * Lightweight unit tests for {@link VcfCfAdapter#applyBcMirrorTransport}
 * (the DEF-005 BC-mirror transport fix) and
 * {@link VcfCfAdapter#isFipsApprovedOnly()}.
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
        // VcfCfAdapter.insecureSslContext(), the same trust-all X509TrustManager
        // used for the target-system opt-out path).
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
