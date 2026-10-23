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
 * Push failures are one WARN line per call with the trace at DEBUG, and an
 * unexpected failure class shows its trace once (issue #192). A non-2xx
 * answer reaches {@code get} callers as a {@link SuiteApiHttpException} with
 * the status, {@code apiErrorCode} and a body excerpt, and the GET
 * {@code Accept} header is settable (issue #201). A closed client refuses
 * every call without acquiring a new token (issue #217).
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
        run("push HTTP failure: one WARN line per call, no trace", SuiteApiStitchClientTransportTest::testPushHttpFailureOneLine);
        run("push HTTP failure: trace at DEBUG", SuiteApiStitchClientTransportTest::testPushHttpFailureTraceAtDebug);
        run("push unexpected failure: trace on first occurrence only", SuiteApiStitchClientTransportTest::testPushUnexpectedTraceOnce);
        run("push interrupted: flag restored", SuiteApiStitchClientTransportTest::testPushInterruptRestoresFlag);
        run("addChild unexpected failure: trace on first occurrence only", SuiteApiStitchClientTransportTest::testAddChildUnexpectedTraceOnce);
        run("GET 400 surfaces status, apiErrorCode and body", SuiteApiStitchClientTransportTest::testGetErrorCarriesApiErrorCode);
        run("GET error without a body", SuiteApiStitchClientTransportTest::testGetErrorWithoutBody);
        run("GET error with a non-JSON body", SuiteApiStitchClientTransportTest::testGetErrorHtmlBody);
        run("GET error excerpt is capped and sanitized", SuiteApiStitchClientTransportTest::testGetErrorExcerptCapped);
        run("GET 401 after the retry is a SuiteApiHttpException", SuiteApiStitchClientTransportTest::testGet401IsHttpException);
        run("Accept defaults to JSON and is overridable", SuiteApiStitchClientTransportTest::testAcceptOverride);
        run("Accept with a control character is refused before sending", SuiteApiStitchClientTransportTest::testAcceptControlCharRefused);
        run("facade get(path, accept) delegates", SuiteApiStitchClientTransportTest::testFacadeGetWithAccept);
        run("parseApiErrorCode edge cases", SuiteApiStitchClientTransportTest::testParseApiErrorCode);
        run("close releases the token once and is idempotent", SuiteApiStitchClientTransportTest::testCloseReleasesOnce);
        run("closed client: get fails fast, no new token", SuiteApiStitchClientTransportTest::testClosedGetFailsFast);
        run("closed client: swallowing calls send nothing, one WARN", SuiteApiStitchClientTransportTest::testClosedSwallowingCallsQuiet);
        run("discard closes too; facade close and isClosed", SuiteApiStitchClientTransportTest::testDiscardAndFacadeClose);
        run("close before first use releases nothing", SuiteApiStitchClientTransportTest::testCloseBeforeUse);
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
    // Issue #192: push failures are one WARN line per cycle
    // -----------------------------------------------------------------------

    private static void testPushHttpFailureOneLine() throws Exception {
        Harness h = new Harness(okTokenThen(500, ""));
        h.log.clear();
        for (int i = 0; i < 3; i++) {
            h.client.pushStats(RES, one("k", 1.0), 1L);
            h.client.pushProperties(RES, oneS("p", "v"), 1L);
        }
        assertEquals("six failed pushes are six WARN lines", 6, h.log.count("WARN"));
        assertEquals("no stack trace at WARN for an HTTP failure", 0, h.log.thrown().size());
        assertTrue("the line names the status", h.log.contains("HTTP 500"));
        assertTrue("the line names the operation", h.log.contains("pushProperties failed"));
    }

    private static void testPushHttpFailureTraceAtDebug() throws Exception {
        Harness h = new Harness(okTokenThen(503, ""), "DEBUG");
        h.log.clear();
        h.client.pushStats(RES, one("k", 1.0), 1L);
        assertEquals("one WARN line", 1, h.log.count("WARN"));
        assertEquals("one DEBUG line", 1, h.log.count("DEBUG"));
        assertEquals("the trace rides the DEBUG line only", 1, h.log.thrown().size());
    }

    private static void testPushUnexpectedTraceOnce() throws Exception {
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            throw new IllegalStateException("proxy answered with HTML");
        });
        h.log.clear();
        for (int i = 0; i < 3; i++) h.client.pushStats(RES, one("k", 1.0), 1L);
        assertEquals("three WARN lines", 3, h.log.count("WARN"));
        assertEquals("the trace is logged once, on the first occurrence", 1, h.log.thrown().size());
        h.client.pushProperties(RES, oneS("p", "v"), 1L);
        assertEquals("another operation gets its own first trace", 2, h.log.thrown().size());
    }

    private static void testPushInterruptRestoresFlag() throws Exception {
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            throw SuiteApiStitchClientTransportTest.<RuntimeException>sneakyThrow(
                    new InterruptedException("interrupted mid-request"));
        });
        h.log.clear();
        try {
            h.client.pushStats(RES, one("k", 1.0), 1L);
            assertTrue("the interrupt flag is restored after pushStats", Thread.interrupted());
            h.client.pushProperties(RES, oneS("p", "v"), 1L);
            assertTrue("the interrupt flag is restored after pushProperties", Thread.interrupted());
        } finally {
            Thread.interrupted();
        }
        assertEquals("interrupts are one-line WARNs", 0, h.log.thrown().size());
    }

    private static void testAddChildUnexpectedTraceOnce() throws Exception {
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            throw new IllegalStateException("unexpected");
        });
        h.log.clear();
        h.client.addChild(RES, "c87c8e39-7cf8-4394-bbf8-04ccd8601efc");
        h.client.addChild(RES, "c87c8e39-7cf8-4394-bbf8-04ccd8601efc");
        assertEquals("two WARN lines", 2, h.log.count("WARN"));
        assertEquals("one trace", 1, h.log.thrown().size());
    }

    // -----------------------------------------------------------------------
    // Issue #201: error body and apiErrorCode reach the caller; Accept is settable
    // -----------------------------------------------------------------------

    static final String ERR_1501 = "{\"message\":\"No such file\",\"httpStatusCode\":400,"
            + "\"apiErrorCode\":1501}";

    private static void testGetErrorCarriesApiErrorCode() throws Exception {
        Harness h = new Harness(okTokenThen(400, ERR_1501));
        try {
            h.client.get("/api/configurations/files?path=SolutionConfig/x.xml", "*/*");
            fail("GET 400 must throw");
        } catch (SuiteApiHttpException e) {
            assertEquals("status", 400, e.getStatusCode());
            assertEquals("apiErrorCode", 1501, e.getApiErrorCode());
            assertTrue("body excerpt carries the server text", e.getBodyExcerpt().contains("No such file"));
            assertTrue("message keeps the status and adds the code",
                    e.getMessage().endsWith("HTTP 400 apiErrorCode 1501"));
            assertFalse("message does not carry the body", e.getMessage().contains("No such file"));
        }
    }

    private static void testGetErrorWithoutBody() throws Exception {
        Harness h = new Harness(okTokenThen(404, null));
        try {
            h.client.get("/api/x");
            fail("GET 404 must throw");
        } catch (SuiteApiHttpException e) {
            assertEquals("status 404", 404, e.getStatusCode());
            assertEquals("no apiErrorCode", null, e.getApiErrorCode());
            assertEquals("empty excerpt", "", e.getBodyExcerpt());
            assertTrue("message unchanged in shape", e.getMessage().endsWith("HTTP 404"));
        }
    }

    private static void testGetErrorHtmlBody() throws Exception {
        Harness h = new Harness(okTokenThen(502, "<html><body>Bad Gateway</body></html>"));
        try {
            h.client.get("/api/x");
            fail("GET 502 must throw");
        } catch (SuiteApiHttpException e) {
            assertEquals("no apiErrorCode from HTML", null, e.getApiErrorCode());
            assertTrue("HTML excerpt kept", e.getBodyExcerpt().startsWith("<html>"));
        }
    }

    private static void testGetErrorExcerptCapped() throws Exception {
        StringBuilder big = new StringBuilder("line1\r\nline2 ");
        for (int i = 0; i < 2000; i++) big.append('x');
        Harness h = new Harness(okTokenThen(500, big.toString()));
        try {
            h.client.get("/api/x");
            fail("GET 500 must throw");
        } catch (SuiteApiHttpException e) {
            String ex = e.getBodyExcerpt();
            assertTrue("excerpt capped (" + ex.length() + ")",
                    ex.length() <= SuiteApiStitchClient.ERROR_BODY_EXCERPT_MAX + 3);
            assertTrue("excerpt marks the cut", ex.endsWith("..."));
            assertFalse("no CR or LF in the excerpt", ex.contains("\r") || ex.contains("\n"));
        }
    }

    private static void testGet401IsHttpException() throws Exception {
        Harness h = new Harness(okTokenThen(401, "{\"apiErrorCode\":1}"));
        try {
            h.client.get("/api/x");
            fail("perpetual 401 must throw");
        } catch (SuiteApiHttpException e) {
            assertEquals("status 401", 401, e.getStatusCode());
            assertEquals("apiErrorCode on a 401", 1, e.getApiErrorCode());
        }
    }

    private static void testAcceptOverride() throws Exception {
        Harness h = new Harness(okTokenThen(200, "raw file body"));
        h.client.get("/api/a");
        assertEquals("default Accept", "application/json", h.lastTo(BASE + "/api/a").headers.get("Accept"));
        assertEquals("body returned", "raw file body", h.client.get("/api/b", "*/*"));
        assertEquals("caller Accept", "*/*", h.lastTo(BASE + "/api/b").headers.get("Accept"));
        h.client.get("/api/c", "   ");
        assertEquals("blank Accept means JSON", "application/json", h.lastTo(BASE + "/api/c").headers.get("Accept"));
        h.client.pushStats(RES, one("k", 1.0), 1L);
        assertEquals("POSTs keep JSON", "application/json",
                h.lastTo(BASE + "/api/resources/" + RES + "/stats").headers.get("Accept"));
        assertEquals("token acquire keeps JSON", "application/json", h.lastTo(TOKEN_URL).headers.get("Accept"));
    }

    private static void testAcceptControlCharRefused() throws Exception {
        Harness h = new Harness(okTokenThen(200, ""));
        try {
            h.client.get("/api/a", "application/json\r\nX-Evil: 1");
            fail("Accept with CR/LF must be refused");
        } catch (IllegalArgumentException e) {
            assertEquals("nothing sent", 0, h.requests.size());
        }
    }

    private static void testFacadeGetWithAccept() throws Exception {
        FakeAdapter a = allocate(FakeAdapter.class);
        a.requests = new ArrayList<>();
        a.responder = okTokenThen(200, "x");
        LogCapture log = LogCapture.create();
        SuiteApiStitcher st = SuiteApiStitcher.createExplicit(a, log.logger(), "localhost", USER, "p");
        assertEquals("facade body", "x", st.get("/api/f", "text/plain"));
        String accept = null;
        for (Req r : a.requests) if ((BASE + "/api/f").equals(r.url)) accept = r.headers.get("Accept");
        assertEquals("facade passes Accept", "text/plain", accept);
    }

    private static void testParseApiErrorCode() {
        assertEquals("plain", 1501, SuiteApiStitchClient.parseApiErrorCode(ERR_1501));
        assertEquals("quoted number", 7, SuiteApiStitchClient.parseApiErrorCode("{\"apiErrorCode\":\"7\"}"));
        assertEquals("text code", null, SuiteApiStitchClient.parseApiErrorCode("{\"apiErrorCode\":\"abc\"}"));
        assertEquals("float code", null, SuiteApiStitchClient.parseApiErrorCode("{\"apiErrorCode\":1.5}"));
        assertEquals("out of int range", null, SuiteApiStitchClient.parseApiErrorCode("{\"apiErrorCode\":99999999999}"));
        assertEquals("array", null, SuiteApiStitchClient.parseApiErrorCode("[1501]"));
        assertEquals("not JSON", null, SuiteApiStitchClient.parseApiErrorCode("Bad Gateway"));
        assertEquals("empty", null, SuiteApiStitchClient.parseApiErrorCode(""));
        assertEquals("null", null, SuiteApiStitchClient.parseApiErrorCode(null));
        assertEquals("absent", null, SuiteApiStitchClient.parseApiErrorCode("{\"message\":\"m\"}"));
    }

    // -----------------------------------------------------------------------
    // Issue #217: a closed client never acquires a token again
    // -----------------------------------------------------------------------

    private static void testCloseReleasesOnce() throws Exception {
        Harness h = new Harness(okTokenThen(200, "{}"));
        h.client.get("/api/a");
        assertEquals("one token acquired", 1, h.countUrl(TOKEN_URL));
        h.client.close();
        assertEquals("close releases the token", 1, h.countUrl(RELEASE_URL));
        assertTrue("release names the cached token",
                h.lastTo(RELEASE_URL).body.contains("tok-1"));
        h.client.close();
        assertEquals("a second close releases nothing more", 1, h.countUrl(RELEASE_URL));
        assertTrue("isClosed", h.client.isClosed());
    }

    private static void testClosedGetFailsFast() throws Exception {
        Harness h = new Harness(okTokenThen(200, "{}"));
        h.client.get("/api/a");
        h.client.close();
        int before = h.requests.size();
        try {
            h.client.get("/api/a");
            fail("get on a closed client must throw");
        } catch (IOException e) {
            assertTrue("the message says the client is closed", e.getMessage().contains("closed"));
        }
        try {
            h.client.get("/api/a", "*/*");
            fail("get(path, accept) on a closed client must throw");
        } catch (IOException e) {
            assertTrue("same refusal with Accept", e.getMessage().contains("closed"));
        }
        assertEquals("nothing sent after close", before, h.requests.size());
        assertEquals("still one token acquired", 1, h.countUrl(TOKEN_URL));
    }

    private static void testClosedSwallowingCallsQuiet() throws Exception {
        Harness h = new Harness(okTokenThen(200, "{}"));
        h.client.close();
        h.log.clear();
        int before = h.requests.size();
        h.client.pushStats(RES, one("k", 1.0), 1L);
        h.client.pushProperties(RES, oneS("p", "v"), 1L);
        assertFalse("addChild refused", h.client.addChild(RES, "c87c8e39-7cf8-4394-bbf8-04ccd8601efc"));
        assertEquals("lookup refused", null, h.client.findSingletonResourceId("K", "W"));
        assertEquals("nothing sent after close", before, h.requests.size());
        assertEquals("one WARN for the first refused call only", 1, h.log.count("WARN"));
        assertTrue("the WARN says closed", h.log.contains("closed"));
        assertEquals("no stack trace", 0, h.log.thrown().size());
    }

    private static void testDiscardAndFacadeClose() throws Exception {
        Harness h = new Harness(okTokenThen(200, "{}"));
        h.client.discard();
        assertTrue("discard closes the client", h.client.isClosed());

        FakeAdapter a = allocate(FakeAdapter.class);
        a.requests = new ArrayList<>();
        a.responder = okTokenThen(200, "{}");
        SuiteApiStitcher st = SuiteApiStitcher.createExplicit(a, LogCapture.create().logger(),
                "localhost", USER, "p");
        st.get("/api/a");
        assertFalse("facade open before close", st.isClosed());
        st.close();
        assertTrue("facade closed", st.isClosed());
        try {
            st.get("/api/a");
            fail("facade get after close must throw");
        } catch (IOException e) {
            assertTrue("facade refusal says closed", e.getMessage().contains("closed"));
        }
    }

    private static void testCloseBeforeUse() throws Exception {
        Harness h = new Harness(okTokenThen(200, "{}"));
        h.client.close();
        assertEquals("no request at all", 0, h.requests.size());
    }

    @SuppressWarnings("unchecked")
    static <X extends Throwable> RuntimeException sneakyThrow(Throwable t) throws X {
        throw (X) t;
    }

    static Map<String, String> oneS(String k, String v) {
        Map<String, String> m = new LinkedHashMap<>();
        m.put(k, v);
        return m;
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
