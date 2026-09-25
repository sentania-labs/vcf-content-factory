package com.vcfcf.adapter;

import com.vcfcf.adapter.spi.VcfCfCollector;
import com.vcfcf.adapter.spi.VcfCfTester;

import com.integrien.alive.common.adapter3.CustomTrustManager;
import com.integrien.alive.common.adapter3.ResourceKey;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.TestParam;
import com.integrien.alive.common.adapter3.config.AdapterConfig;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;

/**
 * Unit tests for the certificate-review hook on {@link VcfCfAdapter}
 * ({@code certificateCheckUrls}, {@code getConnectionURLs},
 * {@code getCertificateRenewalUrls}), the Test Connection trust-failure
 * message mapping, and {@code parseAllowInsecure} (legacy free-text and
 * enum pulldown values).
 *
 * <p>No JUnit required: call via {@code main()}.
 *
 * <p>Instantiating a {@link VcfCfAdapter} subclass normally needs the
 * collector's log4j-core runtime (pulled in by {@code AdapterBase}'s
 * constructor), which is not on this classpath. These tests therefore create
 * the test adapters with {@code sun.misc.Unsafe.allocateInstance}, which skips
 * constructors. That is safe here because every method under test reads only
 * the config passed to it (the hook's contract), plus two test overrides:
 * {@code getAdapterConfig()} (for the renewal path) and the logging methods.
 *
 * <p>Run:
 * <pre>
 *   javac -cp adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         adapter_framework/test/com/vcfcf/adapter/CertificateReviewTest.java \
 *         -d build/test-classes
 *   java -cp build/test-classes:adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         com.vcfcf.adapter.CertificateReviewTest
 * </pre>
 */
public class CertificateReviewTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;

    public static void main(String[] args) throws Exception {
        testHookDefaultKeepsSdkBehaviour();
        testOptedInReturnsDeclaredUrls();
        testOptedInHonoursAllowInsecure();
        testOptedInBlankHostReturnsDefault();
        testHookNormalisesAndDedupes();
        testHookExceptionIsNoUrls();
        testNullConfigIsSafe();
        testRenewalUrlsDefaultNull();
        testRenewalUrlsOptedIn();
        testMessageMappingCustomCertificateException();
        testMessageMappingPkixText();
        testMessageMappingCertPathValidator();
        testMessageMappingIgnoresOtherFailures();
        testMessageMappingIgnoresPeerAlertOnly();
        testMessageMappingCycleSafe();
        testOnTestUsesReadableMessageWhenPromptAvailable();
        testOnTestUsesReadableMessageWhenNoPrompt();
        testOnTestKeepsRawMessageForOtherFailures();
        testParseAllowInsecureLegacyAndEnum();
        testParseAllowInsecureBlankDefault();
        testIsAllowInsecureReadsIdentifier();
        report();
    }

    // -----------------------------------------------------------------------
    // Test adapters
    // -----------------------------------------------------------------------

    /** Minimal concrete adapter; never constructed normally (see class javadoc). */
    static class PlainAdapter extends VcfCfAdapter<Object> {
        AdapterConfig current;
        VcfCfTester<Object> tester;
        final List<String> warnings = new ArrayList<>();

        @Override
        protected void configureAdapter(ResourceStatus s, ResourceConfig rc) {
        }

        @Override
        @SuppressWarnings("rawtypes")
        protected VcfCfTester getTester() {
            return tester;
        }

        @Override
        @SuppressWarnings("rawtypes")
        protected VcfCfCollector getCollector() {
            return null;
        }

        @Override
        public AdapterConfig getAdapterConfig() {
            return current;
        }

        @Override
        protected void logWarn(String message) {
            warnings.add(message);
        }

        @Override
        protected void logWarn(String message, Throwable t) {
            warnings.add(message);
        }
    }

    /** Opted-in adapter: declares https://host:port unless allowInsecure. */
    static class OptedInAdapter extends PlainAdapter {
        @Override
        protected List<String> certificateCheckUrls(ResourceConfig rc) {
            String host = getIdentifier(rc, "host");
            if (host == null || host.trim().isEmpty() || isAllowInsecure(rc)) {
                return List.of();
            }
            String port = getIdentifier(rc, "port");
            return List.of("https://" + host.trim() + ":"
                    + (port == null || port.isBlank() ? "443" : port.trim()));
        }
    }

    /** Returns a fixed raw list (to test normalisation). */
    static class RawListAdapter extends PlainAdapter {
        List<String> raw;

        @Override
        protected List<String> certificateCheckUrls(ResourceConfig rc) {
            return raw;
        }
    }

    /** Hook throws. */
    static class ThrowingAdapter extends PlainAdapter {
        @Override
        protected List<String> certificateCheckUrls(ResourceConfig rc) {
            throw new IllegalStateException("boom");
        }
    }

    @SuppressWarnings("unchecked")
    private static <T> T allocate(Class<T> cls) throws Exception {
        java.lang.reflect.Field f = Class.forName("sun.misc.Unsafe").getDeclaredField("theUnsafe");
        f.setAccessible(true);
        Object unsafe = f.get(null);
        java.lang.reflect.Method m = unsafe.getClass().getMethod("allocateInstance", Class.class);
        T a = (T) m.invoke(unsafe, cls);
        // Field initialisers are skipped too; restore the ones the tests touch.
        java.lang.reflect.Field w = PlainAdapter.class.getDeclaredField("warnings");
        w.setAccessible(true);
        w.set(a, new ArrayList<String>());
        return a;
    }

    /** AdapterConfig whose adapter-instance resource carries the given identifiers. */
    private static AdapterConfig cfg(String... kv) {
        ResourceKey key = new ResourceKey("inst", "test_kind_instance", "test_kind");
        for (int i = 0; i + 1 < kv.length; i += 2) {
            key.addIdentifier(new ResourceIdentifierConfig(kv[i], kv[i + 1], true));
        }
        ResourceConfig rc = new ResourceConfig(key);
        AdapterConfig c = new AdapterConfig("test_kind", 1);
        c.setAdapterInstResource(rc);
        return c;
    }

    // -----------------------------------------------------------------------
    // getConnectionURLs / certificateCheckUrls
    // -----------------------------------------------------------------------

    private static void testHookDefaultKeepsSdkBehaviour() throws Exception {
        PlainAdapter a = allocate(PlainAdapter.class);
        AdapterConfig c = cfg("host", "vc.example.com");
        assertTrue("default hook: declaredCertificateUrls is empty",
                a.declaredCertificateUrls(c).isEmpty());
        List<String> urls = a.getConnectionURLs(c);
        // SDK default: singletonList(getConnectionURL(cfg)) == [null], which the
        // platform's onCheckCertificate maps to NOT_SUPPORTED (same as before).
        assertTrue("default hook: getConnectionURLs delegates to the SDK default [null]; got "
                + urls, urls != null && urls.size() == 1 && urls.get(0) == null);
    }

    private static void testOptedInReturnsDeclaredUrls() throws Exception {
        OptedInAdapter a = allocate(OptedInAdapter.class);
        List<String> urls = a.getConnectionURLs(cfg("host", " vc.example.com ", "port", "8443"));
        assertEquals("opted-in: getConnectionURLs returns the hook URL",
                List.of("https://vc.example.com:8443"), urls);
        urls = a.getConnectionURLs(cfg("host", "vc.example.com", "allowInsecure", "false"));
        assertEquals("opted-in: allowInsecure=false still declares the URL",
                List.of("https://vc.example.com:443"), urls);
    }

    private static void testOptedInHonoursAllowInsecure() throws Exception {
        OptedInAdapter a = allocate(OptedInAdapter.class);
        List<String> urls = a.getConnectionURLs(cfg("host", "vc.example.com", "allowInsecure", " TRUE "));
        assertTrue("opted-in + allowInsecure=TRUE: falls back to SDK default [null]; got " + urls,
                urls.size() == 1 && urls.get(0) == null);
    }

    private static void testOptedInBlankHostReturnsDefault() throws Exception {
        OptedInAdapter a = allocate(OptedInAdapter.class);
        List<String> urls = a.getConnectionURLs(cfg("host", "  "));
        assertTrue("opted-in + blank host: SDK default [null]; got " + urls,
                urls.size() == 1 && urls.get(0) == null);
    }

    private static void testHookNormalisesAndDedupes() throws Exception {
        RawListAdapter a = allocate(RawListAdapter.class);
        a.raw = Arrays.asList(null, " https://a:443 ", "", "https://a:443", "https://b:5001");
        assertEquals("hook result trimmed, blanks/nulls dropped, de-duplicated in order",
                List.of("https://a:443", "https://b:5001"), a.getConnectionURLs(cfg()));
        a.raw = null;
        assertTrue("hook returning null is treated as empty",
                a.declaredCertificateUrls(cfg()).isEmpty());
    }

    private static void testHookExceptionIsNoUrls() throws Exception {
        ThrowingAdapter a = allocate(ThrowingAdapter.class);
        assertTrue("hook throwing: no URLs",
                a.declaredCertificateUrls(cfg("host", "x")).isEmpty());
        assertTrue("hook throwing: a warning was logged", !a.warnings.isEmpty());
    }

    private static void testNullConfigIsSafe() throws Exception {
        OptedInAdapter a = allocate(OptedInAdapter.class);
        assertTrue("null AdapterConfig: no URLs", a.declaredCertificateUrls(null).isEmpty());
        AdapterConfig noInst = new AdapterConfig("test_kind", 1);
        assertTrue("AdapterConfig without instance resource: no URLs",
                a.declaredCertificateUrls(noInst).isEmpty());
    }

    // -----------------------------------------------------------------------
    // getCertificateRenewalUrls
    // -----------------------------------------------------------------------

    private static void testRenewalUrlsDefaultNull() throws Exception {
        PlainAdapter a = allocate(PlainAdapter.class);
        a.current = cfg("host", "vc.example.com");
        assertTrue("default hook: getCertificateRenewalUrls is null (SDK default)",
                a.getCertificateRenewalUrls() == null);
        a.current = null;
        assertTrue("no current config: getCertificateRenewalUrls is null",
                a.getCertificateRenewalUrls() == null);
    }

    private static void testRenewalUrlsOptedIn() throws Exception {
        OptedInAdapter a = allocate(OptedInAdapter.class);
        a.current = cfg("host", "nas.example.com", "port", "5001");
        Set<String> urls = a.getCertificateRenewalUrls();
        assertEquals("opted-in: renewal URLs equal the review URLs",
                List.of("https://nas.example.com:5001"),
                urls == null ? null : new ArrayList<>(urls));
        // The collector parses each with new URL(s).getHost(); make sure that works.
        assertEquals("renewal URL parses to the host the collector matches on",
                "nas.example.com", new java.net.URL(urls.iterator().next()).getHost());
    }

    // -----------------------------------------------------------------------
    // Message mapping
    // -----------------------------------------------------------------------

    /** The prod stack shape: SSLException(TlsFatalAlert(CustomCertificateException(CertPathBuilderException))). */
    private static Exception prodStack() {
        java.security.cert.CertPathBuilderException pkix =
                new java.security.cert.CertPathBuilderException(
                        "No issuer certificate for certificate in certification path found.");
        CustomTrustManager.CustomCertificateException cce =
                new CustomTrustManager.CustomCertificateException(
                        new java.security.cert.CertificateException(
                                "Unable to construct a valid chain", pkix),
                        new java.security.cert.Certificate[0]);
        Exception alert = new java.io.IOException(
                "org.bouncycastle.tls.TlsFatalAlert: certificate_unknown(46)", cce);
        return new javax.net.ssl.SSLException(
                "org.bouncycastle.tls.TlsFatalAlert: certificate_unknown(46)", alert);
    }

    private static void testMessageMappingCustomCertificateException() {
        String msg = VcfCfAdapter.certificateTrustFailureMessage(prodStack(), true);
        assertTrue("prod stack maps to the readable message; got " + msg,
                msg != null && msg.startsWith("The target's TLS certificate is not trusted"));
        assertTrue("prompt available: tells the admin to accept via Validate Connection",
                msg != null && msg.contains("accept the certificate when VCF Operations shows it"));
        assertTrue("message mentions Allow Insecure SSL", msg != null && msg.contains("Allow Insecure SSL"));
        assertTrue("message carries the underlying detail",
                msg != null && msg.contains("Detail: "));
        assertTrue("message contains no em-dash", msg != null && msg.indexOf('\u2014') < 0);
        assertTrue("found hit is the CustomCertificateException",
                VcfCfAdapter.findCertificateTrustFailure(prodStack())
                        instanceof CustomTrustManager.CustomCertificateException);
    }

    private static void testMessageMappingPkixText() {
        Exception e = new javax.net.ssl.SSLHandshakeException(
                "PKIX path building failed: unable to find valid certification path to requested target");
        String msg = VcfCfAdapter.certificateTrustFailureMessage(e, false);
        assertTrue("JDK PKIX text without a typed cause still maps; got " + msg,
                msg != null && msg.contains("does not declare its endpoint for certificate review"));
    }

    private static void testMessageMappingCertPathValidator() {
        Exception e = new javax.net.ssl.SSLHandshakeException("handshake failed");
        e.initCause(new java.security.cert.CertificateException("x",
                new java.security.cert.CertPathValidatorException("expired")));
        assertTrue("CertPathValidatorException in the chain maps",
                VcfCfAdapter.certificateTrustFailureMessage(e, true) != null);
    }

    private static void testMessageMappingIgnoresOtherFailures() {
        assertTrue("connection refused is not a trust failure",
                VcfCfAdapter.certificateTrustFailureMessage(
                        new java.net.ConnectException("Connection refused"), true) == null);
        assertTrue("HTTP 401 is not a trust failure",
                VcfCfAdapter.certificateTrustFailureMessage(
                        new RuntimeException("HTTP 401 Unauthorized"), true) == null);
        assertTrue("null is not a trust failure",
                VcfCfAdapter.certificateTrustFailureMessage(null, true) == null);
    }

    private static void testMessageMappingIgnoresPeerAlertOnly() {
        // A bare certificate_unknown alert with no local chain failure can be the
        // server rejecting us; accepting a certificate would not fix that.
        Exception e = new javax.net.ssl.SSLHandshakeException(
                "Received fatal alert: certificate_unknown");
        assertTrue("peer-sent certificate_unknown alone is not mapped",
                VcfCfAdapter.certificateTrustFailureMessage(e, true) == null);
    }

    private static void testMessageMappingCycleSafe() {
        Exception a = new Exception("a");
        Exception b = new Exception("b", a);
        a.addSuppressed(b);
        assertTrue("cyclic cause/suppressed graph terminates",
                VcfCfAdapter.certificateTrustFailureMessage(a, true) == null);
    }

    // -----------------------------------------------------------------------
    // onTest end-to-end (message lands on TestParam)
    // -----------------------------------------------------------------------

    private static void testOnTestUsesReadableMessageWhenPromptAvailable() throws Exception {
        OptedInAdapter a = allocate(OptedInAdapter.class);
        a.tester = (cfg, http, param) -> { throw prodStack(); };
        TestParam p = new TestParam(cfg("host", "vc.example.com"));
        assertFalse("onTest returns false on a trust failure", a.onTest(p));
        assertTrue("onTest (opted in): readable prompt message on TestParam; got " + p.getErrorMsg(),
                p.getErrorMsg() != null
                        && p.getErrorMsg().contains("accept the certificate when VCF Operations"));
    }

    private static void testOnTestUsesReadableMessageWhenNoPrompt() throws Exception {
        PlainAdapter a = allocate(PlainAdapter.class);
        a.tester = (cfg, http, param) -> { throw prodStack(); };
        TestParam p = new TestParam(cfg("host", "vc.example.com"));
        a.onTest(p);
        assertTrue("onTest (not opted in): says the pack cannot offer the prompt; got "
                + p.getErrorMsg(),
                p.getErrorMsg() != null && p.getErrorMsg().contains("does not declare its endpoint"));
    }

    private static void testOnTestKeepsRawMessageForOtherFailures() throws Exception {
        OptedInAdapter a = allocate(OptedInAdapter.class);
        a.tester = (cfg, http, param) -> { throw new RuntimeException("HTTP 401 Unauthorized"); };
        TestParam p = new TestParam(cfg("host", "vc.example.com"));
        a.onTest(p);
        assertEquals("onTest: non-certificate failure keeps its raw message",
                "HTTP 401 Unauthorized", p.getErrorMsg());
    }

    // -----------------------------------------------------------------------
    // allowInsecure parsing
    // -----------------------------------------------------------------------

    private static void testParseAllowInsecureLegacyAndEnum() {
        // Enum pulldown values.
        assertTrue("enum 'true' is insecure", VcfCfAdapter.parseAllowInsecure("true"));
        assertFalse("enum 'false' is secure", VcfCfAdapter.parseAllowInsecure("false"));
        // Legacy free-text values stored on existing instances.
        assertTrue("legacy 'TRUE' is insecure", VcfCfAdapter.parseAllowInsecure("TRUE"));
        assertTrue("legacy ' True ' (padded) is insecure", VcfCfAdapter.parseAllowInsecure(" True "));
        assertFalse("legacy 'yes' is secure", VcfCfAdapter.parseAllowInsecure("yes"));
        assertFalse("legacy '1' is secure", VcfCfAdapter.parseAllowInsecure("1"));
        assertFalse("legacy 'truee' is secure", VcfCfAdapter.parseAllowInsecure("truee"));
        assertFalse("null is secure", VcfCfAdapter.parseAllowInsecure(null));
        assertFalse("blank is secure", VcfCfAdapter.parseAllowInsecure("   "));
    }

    private static void testParseAllowInsecureBlankDefault() {
        assertTrue("blank with defaultWhenBlank=true is insecure",
                VcfCfAdapter.parseAllowInsecure("", true));
        assertTrue("null with defaultWhenBlank=true is insecure",
                VcfCfAdapter.parseAllowInsecure(null, true));
        assertFalse("'false' with defaultWhenBlank=true is secure",
                VcfCfAdapter.parseAllowInsecure("false", true));
        assertFalse("'no' with defaultWhenBlank=true is secure (non-blank parses strictly)",
                VcfCfAdapter.parseAllowInsecure("no", true));
    }

    private static void testIsAllowInsecureReadsIdentifier() throws Exception {
        PlainAdapter a = allocate(PlainAdapter.class);
        assertTrue("isAllowInsecure reads allowInsecure=true",
                a.isAllowInsecure(cfg("allowInsecure", "true").getAdapterInstResource()));
        assertFalse("isAllowInsecure: absent identifier is secure",
                a.isAllowInsecure(cfg("host", "x").getAdapterInstResource()));
        assertFalse("isAllowInsecure: null config is secure", a.isAllowInsecure(null));
    }

    // -----------------------------------------------------------------------
    // Assertion helpers
    // -----------------------------------------------------------------------

    private static void assertTrue(String name, boolean cond) {
        if (cond) {
            passed++;
            System.out.println("  PASS: " + name);
        } else {
            FAILURES.add(name);
            System.out.println("  FAIL: " + name);
        }
    }

    private static void assertFalse(String name, boolean cond) {
        assertTrue(name, !cond);
    }

    private static void assertEquals(String name, Object expected, Object actual) {
        boolean eq = expected == null ? actual == null : expected.equals(actual);
        assertTrue(name + " (expected " + expected + ", got " + actual + ")", eq);
    }

    private static void report() {
        System.out.println();
        int total = passed + FAILURES.size();
        if (FAILURES.isEmpty()) {
            System.out.println("OK: " + passed + "/" + total + " tests passed.");
        } else {
            System.out.println("FAIL: " + FAILURES.size() + "/" + total + " tests failed: " + FAILURES);
            System.exit(1);
        }
    }
}
