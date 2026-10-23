package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.vcfcf.adapter.LogCapture;
import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.spi.VcfCfCollector;
import com.vcfcf.adapter.spi.VcfCfTester;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLConnection;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Transport and logging tests for {@link SuiteApiStitchClient} that need the
 * text of what it logs: the principal never appears (issue #227).
 *
 * <p>No JUnit required: call via {@code main()}. A real client runs against
 * a scripted fake {@link HttpURLConnection} behind an
 * {@code openPlatformConnection} override, and logs into a {@link LogCapture}.
 * Capturing text needs log4j-api and log4j-core at runtime; without them the
 * whole suite is SKIPPED with a message (same convention as
 * {@code SuiteApiStitchRelationshipTest}).
 *
 * <p>Run (from {@code src/vcfcf_managementpacks/}):
 * <pre>
 *   javac -cp adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         $(find adapter_framework/test -name '*.java') -d build/test-classes
 *   java -cp build/test-classes:adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar:adapter_runtime/lib/* \
 *         com.vcfcf.adapter.stitch.SuiteApiStitchClientTransportTest
 * </pre>
 */
public class SuiteApiStitchClientTransportTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;
    private static int skipped = 0;

    static final String BASE = "https://localhost/suite-api";
    static final String TOKEN_URL = BASE + "/api/auth/token/acquire";
    static final String RELEASE_URL = BASE + "/api/auth/token/release";
    static final String RES = "6baa06d3-0811-45a2-ba2a-c7b38f646ce9";
    static final String USER = "svc-principal-name";

    public static void main(String[] args) throws Exception {
        if (!LogCapture.available()) {
            skip("all transport tests: log4j-api/log4j-core not on the runtime classpath"
                    + " (add a jar carrying them, e.g. adapter_runtime/lib/*)");
            report();
            return;
        }
        run("principal absent from configure-time lines", SuiteApiStitchClientTransportTest::testBuilderLinesOmitPrincipal);
        run("principal absent from the 401 failure line", SuiteApiStitchClientTransportTest::testPerpetual401OmitsPrincipal);
        run("principal absent from the no-token failure line", SuiteApiStitchClientTransportTest::testNoTokenOmitsPrincipal);
        report();
    }

    // -----------------------------------------------------------------------
    // Issue #227: the principal never reaches a log line or exception message
    // -----------------------------------------------------------------------

    private static void testBuilderLinesOmitPrincipal() throws Exception {
        Harness h = new Harness(okTokenThen(200, ""));
        assertTrue("builder logged its mechanism line", h.log.contains("mechanism=explicit"));
        assertTrue("builder logged the endpoint", h.log.contains("endpoint=" + BASE));
        assertFalse("no configure-time line names the principal: " + h.log.lines(),
                h.log.contains(USER));
        assertFalse("no configure-time line carries principal=", h.log.contains("principal="));
    }

    private static void testPerpetual401OmitsPrincipal() throws Exception {
        Harness h = new Harness(okTokenThen(401, ""));
        h.client.pushStats(RES, one("k", 1.0), 1L);
        assertTrue("the 401 was logged", h.log.contains("401"));
        assertFalse("the 401 line does not name the principal: " + h.log.lines(),
                h.log.contains(USER));
        assertFalse("the 401 line carries no principal=", h.log.contains("principal="));
        for (Throwable t : h.log.thrown()) {
            assertFalse("no logged exception message names the principal",
                    String.valueOf(t.getMessage()).contains(USER));
        }
        try {
            h.client.get("/api/x");
            fail("get with a perpetual 401 must throw");
        } catch (IOException e) {
            assertFalse("the 401 exception message does not name the principal",
                    String.valueOf(e.getMessage()).contains(USER));
            assertTrue("the 401 exception message names the mechanism",
                    String.valueOf(e.getMessage()).contains("mechanism=explicit"));
        }
    }

    private static void testNoTokenOmitsPrincipal() throws Exception {
        Harness h = new Harness((m, u, b) -> new Resp(200, "{}"));
        try {
            h.client.get("/api/x");
            fail("get without a token in the acquire answer must throw");
        } catch (IOException e) {
            assertTrue("the no-token message says what is missing",
                    String.valueOf(e.getMessage()).contains("no 'token' field"));
            assertFalse("the no-token message does not name the principal",
                    String.valueOf(e.getMessage()).contains(USER));
        }
    }

    // -----------------------------------------------------------------------
    // Fake transport
    // -----------------------------------------------------------------------

    static final class Resp {
        final int code;
        final String body;
        Resp(int code, String body) { this.code = code; this.body = body; }
    }

    static final class Req {
        String method = "GET";
        String url;
        String body;
        final Map<String, String> headers = new LinkedHashMap<>();
    }

    @FunctionalInterface
    interface Responder {
        Resp respond(String method, String url, String body) throws IOException;
    }

    /** Token acquire answers 200 with tok-1; everything else answers (code, body). */
    static Responder okTokenThen(int code, String body) {
        return (m, u, b) -> u.equals(TOKEN_URL)
                ? new Resp(200, "{\"token\":\"tok-1\"}") : new Resp(code, body);
    }

    /**
     * Records the request; the response is decided when the code is read.
     * Like the JDK, a non-2xx body is served only by {@link #getErrorStream()}
     * and {@link #getInputStream()} throws for it.
     */
    static final class FakeConn extends HttpURLConnection {
        final Req req;
        final Responder responder;
        final ByteArrayOutputStream out = new ByteArrayOutputStream();
        Resp resp;

        FakeConn(URL url, Req req, Responder responder) {
            super(url);
            this.req = req;
            this.responder = responder;
        }

        @Override public void connect() { }
        @Override public void disconnect() { }
        @Override public boolean usingProxy() { return false; }

        @Override public void setRequestMethod(String m) throws java.net.ProtocolException {
            super.setRequestMethod(m);
            req.method = m;
        }

        @Override public void setRequestProperty(String k, String v) {
            req.headers.put(k, v);
        }

        @Override public OutputStream getOutputStream() { return out; }

        private Resp resp() throws IOException {
            if (resp == null) {
                req.body = out.size() == 0 ? null : out.toString(StandardCharsets.UTF_8);
                resp = responder.respond(req.method, req.url, req.body);
            }
            return resp;
        }

        @Override public int getResponseCode() throws IOException { return resp().code; }

        @Override public InputStream getInputStream() throws IOException {
            Resp r = resp();
            if (r.code >= 400) throw new IOException("Server returned HTTP response code: " + r.code);
            return new ByteArrayInputStream(r.body.getBytes(StandardCharsets.UTF_8));
        }

        @Override public InputStream getErrorStream() {
            if (resp == null || resp.code < 400 || resp.body == null) return null;
            return new ByteArrayInputStream(resp.body.getBytes(StandardCharsets.UTF_8));
        }
    }

    /** Adapter whose only live behaviour is the scripted connection. */
    static class FakeAdapter extends VcfCfAdapter<Object> {
        List<Req> requests;
        Responder responder;

        @Override
        protected void configureAdapter(ResourceStatus s, ResourceConfig rc) { }

        @Override
        @SuppressWarnings("rawtypes")
        protected VcfCfTester getTester() { return null; }

        @Override
        @SuppressWarnings("rawtypes")
        protected VcfCfCollector getCollector() { return null; }

        @Override
        public URLConnection openPlatformConnection(String url) throws IOException {
            Req r = new Req();
            r.url = url;
            requests.add(r);
            if (responder == null) throw new IOException("no responder");
            return new FakeConn(new URL(url), r, responder);
        }
    }

    /** One client wired to a FakeAdapter, plus the requests and log it saw. */
    static final class Harness {
        final List<Req> requests = new ArrayList<>();
        final LogCapture log;
        final SuiteApiStitchClient client;

        Harness(Responder responder) throws Exception {
            this(responder, "INFO");
        }

        Harness(Responder responder, String level) throws Exception {
            FakeAdapter a = allocate(FakeAdapter.class);
            a.requests = requests;
            a.responder = responder;
            log = LogCapture.create(level);
            client = SuiteApiStitchClient.builder()
                    .adapter(a)
                    .explicitCredentials("localhost", USER, "svc-pass")
                    .logger(log.logger())
                    .build();
        }

        int countUrl(String url) {
            int n = 0;
            for (Req r : requests) if (url.equals(r.url)) n++;
            return n;
        }

        Req lastTo(String url) {
            Req last = null;
            for (Req r : requests) if (url.equals(r.url)) last = r;
            return last;
        }
    }

    static Map<String, Double> one(String k, double v) {
        Map<String, Double> m = new LinkedHashMap<>();
        m.put(k, v);
        return m;
    }

    @SuppressWarnings("unchecked")
    static <T> T allocate(Class<T> cls) throws Exception {
        java.lang.reflect.Field f = Class.forName("sun.misc.Unsafe").getDeclaredField("theUnsafe");
        f.setAccessible(true);
        Object unsafe = f.get(null);
        Method m = unsafe.getClass().getMethod("allocateInstance", Class.class);
        return (T) m.invoke(unsafe, cls);
    }

    // -----------------------------------------------------------------------
    // Harness
    // -----------------------------------------------------------------------

    @FunctionalInterface
    interface TestCase {
        void run() throws Exception;
    }

    private static void run(String name, TestCase t) {
        try {
            t.run();
        } catch (Throwable e) {
            fail(name + " threw " + e);
        }
    }

    static void assertTrue(String label, boolean cond) {
        if (cond) {
            System.out.println("  PASS: " + label);
            passed++;
        } else {
            fail(label);
        }
    }

    static void assertFalse(String label, boolean cond) {
        assertTrue(label, !cond);
    }

    static void assertEquals(String label, Object expected, Object actual) {
        if (expected == null ? actual == null : expected.equals(actual)) {
            System.out.println("  PASS: " + label);
            passed++;
        } else {
            fail(label + " expected=" + expected + " actual=" + actual);
        }
    }

    static void fail(String label) {
        System.out.println("  FAIL: " + label);
        FAILURES.add(label);
    }

    static void skip(String label) {
        System.out.println("  SKIP: " + label);
        skipped++;
    }

    private static void report() {
        int total = passed + FAILURES.size();
        System.out.println();
        if (FAILURES.isEmpty()) {
            System.out.println("OK: " + passed + "/" + total + " tests passed"
                    + (skipped > 0 ? " (" + skipped + " group(s) skipped)" : "") + ".");
        } else {
            System.out.println("FAIL: " + FAILURES.size() + "/" + total
                    + " tests failed: " + FAILURES);
            System.exit(1);
        }
    }
}
