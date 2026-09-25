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

/**
 * Unit tests for the certificate-review hook on {@link VcfCfAdapter}
 * ({@code certificateCheckUrls}, {@code getConnectionURLs}; the renewal URL
 * set deliberately stays at the SDK default), the Test Connection
 * trust-failure message mapping, and the allowInsecure parsers (strict and
 * legacy "anything but false", legacy free-text and enum pulldown values).
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
        testRenewalUrlsStaySdkDefault();
        testMessageMappingCustomCertificateException();
        testMessageMappingPkixText();
        testMessageMappingCertPathValidator();
        testMessageMappingIgnoresOtherFailures();
        testMessageMappingIgnoresPeerAlertOnly();
        testMessageMappingCycleSafe();
        testOnTestUsesReadableMessageWhenPromptAvailable();
        testOnTestUsesReadableMessageWhenNoPrompt();
        testOnTestKeepsRawMessageForOtherFailures();
        testOnTestSkipsHookForOtherFailures();
        testOnTestHookErrorDoesNotEscape();
        testParseAllowInsecureLegacyAndEnum();
        testParseAllowInsecureLegacyNotFalseMatchesSynology();
        testIsAllowInsecureReadsIdentifier();
        testIsAllowInsecureLegacyNotFalse();
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

    /** Counts hook calls. */
    static class CountingAdapter extends OptedInAdapter {
        int calls;

        @Override
        protected List<String> certificateCheckUrls(ResourceConfig rc) {
            calls++;
            return super.certificateCheckUrls(rc);
        }
    }

    /** Hook throws an Error (for example a missing class in the pak). */
    static class ErrorAdapter extends PlainAdapter {
        @Override
        protected List<String> certificateCheckUrls(ResourceConfig rc) {
            throw new AssertionError("hook error");
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
    // getCertificateRenewalUrls: deliberately NOT overridden
    // -----------------------------------------------------------------------

    private static void testRenewalUrlsStaySdkDefault() throws Exception {
        PlainAdapter a = allocate(PlainAdapter.class);
        a.current = cfg("host", "vc.example.com");
        assertTrue("default hook: getCertificateRenewalUrls is null (SDK default)",
                a.getCertificateRenewalUrls() == null);
        OptedInAdapter b = allocate(OptedInAdapter.class);
        b.current = cfg("host", "nas.example.com", "port", "5001");
        assertTrue("opted-in: getCertificateRenewalUrls is still null (renewal protocol is "
                + "VCF-only, so the framework does not declare renewal URLs)",
                b.getCertificateRenewalUrls() == null);
        boolean declared = false;
        for (java.lang.reflect.Method m : VcfCfAdapter.class.getDeclaredMethods()) {
            if (m.getName().equals("getCertificateRenewalUrls")) declared = true;
        }
        assertFalse("VcfCfAdapter does not override getCertificateRenewalUrls", declared);
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
                msg != null && msg.contains("No endpoint was offered for certificate review"));
        assertTrue("no-prompt message covers Allow Insecure already true and blank host",
                msg != null && msg.contains("Allow Insecure SSL is already true")
                        && msg.contains("host is blank"));
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
                p.getErrorMsg() != null
                        && p.getErrorMsg().contains("No endpoint was offered for certificate review"));
    }

    private static void testOnTestKeepsRawMessageForOtherFailures() throws Exception {
        OptedInAdapter a = allocate(OptedInAdapter.class);
        a.tester = (cfg, http, param) -> { throw new RuntimeException("HTTP 401 Unauthorized"); };
        TestParam p = new TestParam(cfg("host", "vc.example.com"));
        a.onTest(p);
        assertEquals("onTest: non-certificate failure keeps its raw message",
                "HTTP 401 Unauthorized", p.getErrorMsg());
    }

    private static void testOnTestSkipsHookForOtherFailures() throws Exception {
        CountingAdapter a = allocate(CountingAdapter.class);
        a.tester = (cfg, http, param) -> { throw new RuntimeException("HTTP 401 Unauthorized"); };
        a.onTest(new TestParam(cfg("host", "vc.example.com")));
        assertEquals("onTest: hook not called for a non-certificate failure", 0, a.calls);
        a.tester = (cfg, http, param) -> { throw prodStack(); };
        a.onTest(new TestParam(cfg("host", "vc.example.com")));
        assertEquals("onTest: hook called once for a trust failure", 1, a.calls);
    }

    private static void testOnTestHookErrorDoesNotEscape() throws Exception {
        ErrorAdapter a = allocate(ErrorAdapter.class);
        a.tester = (cfg, http, param) -> { throw prodStack(); };
        TestParam p = new TestParam(cfg("host", "vc.example.com"));
        boolean ok;
        try {
            ok = a.onTest(p);
        } catch (Throwable t) {
            assertTrue("onTest: an Error from the hook must not escape; got " + t, false);
            return;
        }
        assertFalse("onTest with an Error-throwing hook still returns false", ok);
        assertTrue("onTest with an Error-throwing hook falls back to the no-prompt message",
                p.getErrorMsg() != null
                        && p.getErrorMsg().contains("No endpoint was offered for certificate review"));
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

    private static void testParseAllowInsecureLegacyNotFalseMatchesSynology() {
        // Bit-for-bit parity with synology's shipped parse, for every shape of
        // stored value, including ones the strict parser reads differently.
        String[] values = {null, "", "   ", "true", "TRUE", " true", "false", "FALSE",
                " false", "false ", "yes", "no", "1", "0", "truee"};
        for (String v : values) {
            boolean legacy = !"false".equalsIgnoreCase(v);
            assertEquals("legacy-not-false parse of [" + v + "] matches synology",
                    legacy, VcfCfAdapter.parseAllowInsecureLegacyNotFalse(v));
        }
        // And the strict parser vs the untrimmed "true".equalsIgnoreCase legacy
        // parse differs ONLY for padded "true".
        for (String v : values) {
            boolean legacy = "true".equalsIgnoreCase(v);
            boolean strict = VcfCfAdapter.parseAllowInsecure(v);
            boolean paddedTrue = v != null && !v.equals(v.trim())
                    && "true".equalsIgnoreCase(v.trim());
            assertEquals("strict parse of [" + v + "] differs from legacy only for padded true",
                    paddedTrue, legacy != strict);
        }
    }

    private static void testIsAllowInsecureReadsIdentifier() throws Exception {
        PlainAdapter a = allocate(PlainAdapter.class);
        assertTrue("isAllowInsecure reads allowInsecure=true",
                a.isAllowInsecure(cfg("allowInsecure", "true").getAdapterInstResource()));
        assertFalse("isAllowInsecure: absent identifier is secure",
                a.isAllowInsecure(cfg("host", "x").getAdapterInstResource()));
        assertFalse("isAllowInsecure: null config is secure", a.isAllowInsecure(null));
    }

    private static void testIsAllowInsecureLegacyNotFalse() throws Exception {
        PlainAdapter a = allocate(PlainAdapter.class);
        assertTrue("legacy: absent identifier is insecure",
                a.isAllowInsecureLegacyNotFalse(cfg("host", "x").getAdapterInstResource()));
        assertTrue("legacy: 'yes' is insecure",
                a.isAllowInsecureLegacyNotFalse(cfg("allowInsecure", "yes").getAdapterInstResource()));
        assertFalse("legacy: 'False' is secure",
                a.isAllowInsecureLegacyNotFalse(cfg("allowInsecure", "False").getAdapterInstResource()));
        assertFalse("legacy: null config is secure", a.isAllowInsecureLegacyNotFalse(null));
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
