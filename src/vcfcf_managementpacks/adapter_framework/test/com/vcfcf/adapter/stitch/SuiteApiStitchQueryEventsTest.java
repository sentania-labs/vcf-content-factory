package com.vcfcf.adapter.stitch;

import com.vcfcf.adapter.LogCapture;
import com.vcfcf.adapter.json.SimpleJson;
import com.vcfcf.adapter.stitch.SuiteApiStitchClientTransportTest.FakeAdapter;
import com.vcfcf.adapter.stitch.SuiteApiStitchClientTransportTest.Harness;
import com.vcfcf.adapter.stitch.SuiteApiStitchClientTransportTest.Req;
import com.vcfcf.adapter.stitch.SuiteApiStitchClientTransportTest.Resp;

import java.io.IOException;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Tests for the three facade additions the vCommunity Java port design names
 * (T1 to T3), against the scripted fake Suite API of
 * {@link SuiteApiStitchClientTransportTest}:
 * <ul>
 *   <li>T1 {@link SuiteApiStitchClient#post}: request shape, the query-path
 *       guard, error mapping identical to {@code get}, one 401 retry, and that
 *       neither body reaches a log line or an exception message.</li>
 *   <li>T2 {@link SuiteApiStitchClient#pushEvents}: body shape, NOTIFICATION
 *       refused, invalid events dropped, chunking, stop on failure, never the
 *       message text in a log line.</li>
 *   <li>T3 {@link SuiteApiStitchClient#pushTypedPropertiesBatch}: numeric
 *       properties as {@code data}, null / NaN / infinite / other types
 *       rejected, and string-only input byte-identical to
 *       {@link SuiteApiStitchClient#pushPropertiesBatch}.</li>
 * </ul>
 *
 * <p>No JUnit: run via {@code main()} (or {@code run_stitch_tests.sh}). Needs
 * log4j-api and log4j-core at runtime; without them the suite is SKIPPED.
 */
public class SuiteApiStitchQueryEventsTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;

    static final String BASE = SuiteApiStitchClientTransportTest.BASE;
    static final String TOKEN_URL = SuiteApiStitchClientTransportTest.TOKEN_URL;
    static final String PROPS_URL = BASE + "/api/resources/properties";
    static final String STATS_URL = BASE + "/api/resources/stats";
    static final String EVENTS_URL = BASE + "/api/events/bulk";
    static final String LATEST_URL = BASE + "/api/resources/stats/latest/query";

    static final String A = "6baa06d3-0811-45a2-ba2a-c7b38f646ce9";
    static final String B = "1e9de40c-b045-4f9e-9b4f-be7d471773e6";

    /** A marker that must never appear in a log line or exception message. */
    static final String SECRET = "QUERY-BODY-MARKER-7f3a";

    static final long T0 = 1793178366127L;

    public static void main(String[] args) throws Exception {
        if (!LogCapture.available()) {
            System.out.println("  SKIP: all query/events tests: log4j-api/log4j-core not on the"
                    + " runtime classpath (add a jar carrying them, e.g. adapter_runtime/lib/*)");
            System.out.println();
            System.out.println("OK: 0/0 tests passed (1 group(s) skipped).");
            return;
        }
        // T1
        run("T1 post: request shape and body returned", SuiteApiStitchQueryEventsTest::testPostShape);
        run("T1 post: query string allowed after /query", SuiteApiStitchQueryEventsTest::testPostQueryString);
        run("T1 post: non-query paths refused before sending", SuiteApiStitchQueryEventsTest::testPostGuard);
        run("T1 post: non-2xx is SuiteApiHttpException like get", SuiteApiStitchQueryEventsTest::testPostErrorMapping);
        run("T1 post: 401 re-acquires once and retries", SuiteApiStitchQueryEventsTest::testPost401Retry);
        run("T1 post: persistent 401 surfaces as 401", SuiteApiStitchQueryEventsTest::testPostPersistent401);
        run("T1 post: bodies never logged or in messages", SuiteApiStitchQueryEventsTest::testPostRedaction);
        run("T1 post: closed client fails fast, no token", SuiteApiStitchQueryEventsTest::testPostClosed);
        run("T1 post: facade delegates", SuiteApiStitchQueryEventsTest::testPostFacade);
        // T2
        run("T2 events: exact body, optional fields omitted", SuiteApiStitchQueryEventsTest::testEventsShape);
        run("T2 events: NOTIFICATION refused, not sent", SuiteApiStitchQueryEventsTest::testEventsNotificationRefused);
        run("T2 events: invalid events dropped and counted", SuiteApiStitchQueryEventsTest::testEventsInvalidDropped);
        run("T2 events: control characters escaped", SuiteApiStitchQueryEventsTest::testEventsEscaping);
        run("T2 events: chunked by count and bytes", SuiteApiStitchQueryEventsTest::testEventsChunking);
        run("T2 events: a failure stops the call, one WARN", SuiteApiStitchQueryEventsTest::testEventsFailureStops);
        run("T2 events: 401 re-acquires once and retries", SuiteApiStitchQueryEventsTest::testEvents401Retry);
        run("T2 events: message text never logged", SuiteApiStitchQueryEventsTest::testEventsMessageNotLogged);
        run("T2 events: nothing to send, no request", SuiteApiStitchQueryEventsTest::testEventsNothing);
        run("T2 events: builder rules and cancelledAt", SuiteApiStitchQueryEventsTest::testEventBuilder);
        run("T2 events: closed client sends nothing", SuiteApiStitchQueryEventsTest::testEventsClosed);
        run("T2 events: facade delegates", SuiteApiStitchQueryEventsTest::testEventsFacade);
        // T3
        run("T3 typed: string-only bodies byte-identical", SuiteApiStitchQueryEventsTest::testTypedStringsIdentical);
        run("T3 typed: pushTypedBatch strings equal pushBatch", SuiteApiStitchQueryEventsTest::testTypedBatchStringsIdentical);
        run("T3 typed: numbers sent as data", SuiteApiStitchQueryEventsTest::testTypedNumbers);
        run("T3 typed: null, NaN, infinite, other types rejected", SuiteApiStitchQueryEventsTest::testTypedRejected);
        run("T3 typed: string batch still drops numbers", SuiteApiStitchQueryEventsTest::testUntypedStillStrict);
        run("T3 typed: per-id fallback keeps the numeric shape", SuiteApiStitchQueryEventsTest::testTypedFallback);
        run("T3 typed: facade delegates", SuiteApiStitchQueryEventsTest::testTypedFacade);
        report();
    }

    // -----------------------------------------------------------------------
    // T1 post
    // -----------------------------------------------------------------------

    private static void testPostShape() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200,
                "{\"values\":[]}"));
        String q = "{\"resourceId\":[\"" + A + "\"],\"statKey\":[\"cpu|usage_average\"]}";
        h.log.clear();
        String body = h.client.post("/api/resources/stats/latest/query", q);
        assertEquals("response body returned", "{\"values\":[]}", body);
        Req r = h.lastTo(LATEST_URL);
        assertEquals("POST", "POST", r.method);
        assertEquals("request body sent verbatim", q, r.body);
        assertEquals("Content-Type JSON", "application/json", r.headers.get("Content-Type"));
        assertEquals("Accept JSON", "application/json", r.headers.get("Accept"));
        assertEquals("OpsToken auth", "OpsToken tok-1", r.headers.get("Authorization"));
        assertEquals("one token, one query", 2, h.requests.size());
        assertEquals("nothing logged on success: " + h.log.lines(), 0, h.log.lines().size());
    }

    private static void testPostQueryString() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, "{}"));
        h.client.post("/api/resources/query?page=0&pageSize=1000", "{}");
        assertEquals("query string kept", 1,
                h.countUrl(BASE + "/api/resources/query?page=0&pageSize=1000"));
        h.client.post("/api/resources/properties/latest/query", "{}");
        h.client.post("/api/resources/stats/query", "{}");
        assertEquals("the other two design endpoints pass", 1,
                h.countUrl(BASE + "/api/resources/stats/query"));
    }

    private static void testPostGuard() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        String[] bad = {
            "/api/resources/properties", "/api/resources/stats", "/api/events/bulk",
            "/api/resources/" + A + "/relationships/children", "/api/resources/query/x",
            "/api/x?y=/query", "api/resources/query", null, "/api/resources/query\r\nX: 1",
            "/api/queryx", "/api/resources/query/",
        };
        for (String p : bad) {
            try {
                h.client.post(p, "{}");
                fail("post must refuse " + p);
            } catch (IllegalArgumentException e) {
                assertTrue("refusal says what post is for ("
                        + SuiteApiStitchClient.loggable(p) + ")",
                        e.getMessage().contains("SuiteApiStitchClient: post"));
            }
        }
        try {
            h.client.post("/api/resources/query", null);
            fail("post must refuse a null body");
        } catch (IllegalArgumentException e) {
            assertTrue("null body refused", e.getMessage().contains("JSON body"));
        }
        assertEquals("nothing sent, not even a token request", 0, h.requests.size());
    }

    private static void testPostErrorMapping() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(400,
                SuiteApiStitchClientTransportTest.ERR_1501));
        try {
            h.client.post("/api/resources/query", "{\"name\":[\"" + SECRET + "\"]}");
            fail("POST 400 must throw");
        } catch (SuiteApiHttpException e) {
            assertEquals("status", 400, e.getStatusCode());
            assertEquals("apiErrorCode", 1501, e.getApiErrorCode());
            assertTrue("excerpt carries the server text", e.getBodyExcerpt().contains("No such file"));
            assertEquals("same message shape as get",
                    "Suite API POST " + BASE + "/api/resources/query HTTP 400 apiErrorCode 1501",
                    e.getMessage());
            assertFalse("message does not carry the request body", e.getMessage().contains(SECRET));
        }
        Harness h5 = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(503, null));
        try {
            h5.client.post("/api/resources/query", "{}");
            fail("POST 503 must throw");
        } catch (SuiteApiHttpException e) {
            assertEquals("503 status", 503, e.getStatusCode());
            assertEquals("one request: no retry on 5xx", 1, h5.countUrl(BASE + "/api/resources/query"));
        }
        Harness ht = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            throw new java.net.SocketTimeoutException("Read timed out");
        });
        try {
            ht.client.post("/api/resources/query", "{}");
            fail("timeout must throw");
        } catch (IOException e) {
            assertFalse("a timeout is not an HTTP exception", e instanceof SuiteApiHttpException);
        }
    }

    private static void testPost401Retry() throws Exception {
        AtomicInteger tokens = new AtomicInteger();
        AtomicInteger posts = new AtomicInteger();
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) {
                return new Resp(200, "{\"token\":\"tok-" + tokens.incrementAndGet() + "\"}");
            }
            return posts.incrementAndGet() == 1 ? new Resp(401, "") : new Resp(200, "ok");
        });
        assertEquals("retried body returned", "ok", h.client.post("/api/resources/query", "{}"));
        assertEquals("two tokens", 2, tokens.get());
        assertEquals("two posts", 2, posts.get());
        assertEquals("retry carries the new token", "OpsToken tok-2",
                h.lastTo(BASE + "/api/resources/query").headers.get("Authorization"));
    }

    private static void testPostPersistent401() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(401, ""));
        try {
            h.client.post("/api/resources/query", "{}");
            fail("persistent 401 must throw");
        } catch (SuiteApiHttpException e) {
            assertEquals("status 401", 401, e.getStatusCode());
            assertEquals("exactly one retry", 2, h.countUrl(BASE + "/api/resources/query"));
            assertFalse("principal not in the message",
                    e.getMessage().contains(SuiteApiStitchClientTransportTest.USER));
        }
    }

    private static void testPostRedaction() throws Exception {
        String reply = "{\"resourceList\":[{\"name\":\"" + SECRET + "-reply\"}]}";
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, reply), "DEBUG");
        h.log.clear();
        h.client.post("/api/resources/query", "{\"name\":[\"" + SECRET + "\"]}");
        assertFalse("request and response bodies absent from every log line, DEBUG included: "
                + h.log.lines(), h.log.contains(SECRET));
        Harness hf = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(500, "oops"), "DEBUG");
        hf.log.clear();
        try {
            hf.client.post("/api/resources/query", "{\"name\":[\"" + SECRET + "\"]}");
        } catch (SuiteApiHttpException e) {
            assertFalse("not in the exception message", String.valueOf(e.getMessage()).contains(SECRET));
            assertFalse("not in the excerpt", e.getBodyExcerpt().contains(SECRET));
        }
        assertFalse("failure path logs no body", hf.log.contains(SECRET));
    }

    private static void testPostClosed() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, "x"));
        h.client.close();
        try {
            h.client.post("/api/resources/query", "{}");
            fail("closed client must throw");
        } catch (IOException e) {
            assertTrue("says closed", e.getMessage().contains("closed"));
            assertEquals("no token acquired", 0, h.countUrl(TOKEN_URL));
        }
    }

    private static void testPostFacade() throws Exception {
        FakeAdapter a = SuiteApiStitchClientTransportTest.allocate(FakeAdapter.class);
        a.requests = new ArrayList<>();
        a.responder = SuiteApiStitchClientTransportTest.okTokenThen(200, "facade");
        LogCapture log = LogCapture.create();
        SuiteApiStitcher st = SuiteApiStitcher.createExplicit(a, log.logger(), "localhost",
                SuiteApiStitchClientTransportTest.USER, "p");
        assertEquals("facade body", "facade", st.post("/api/resources/properties/latest/query", "{}"));
        try {
            st.post("/api/resources/properties", "{}");
            fail("facade must refuse a write path");
        } catch (IllegalArgumentException e) {
            assertTrue("refused through the facade", true);
        }
    }

    // -----------------------------------------------------------------------
    // T2 events
    // -----------------------------------------------------------------------

    static SuiteApiEvent diag(String id, String msg) {
        return SuiteApiEvent.builder(SuiteApiEvent.Type.DIAGNOSTIC, id, msg, T0)
                .severity(SuiteApiEvent.Severity.WARNING)
                .diagnosticSubType(SuiteApiEvent.DiagnosticSubType.LOG)
                .managedExternally(false)
                .build();
    }

    private static void testEventsShape() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        SuiteApiEvent full = SuiteApiEvent.builder(SuiteApiEvent.Type.DIAGNOSTIC,
                A.toUpperCase(), "[WindowsEvent-Warning] disk", T0)
                .severity(SuiteApiEvent.Severity.WARNING)
                .diagnosticSubType(SuiteApiEvent.DiagnosticSubType.LOG)
                .managedExternally(true)
                .cancelTimeUtc(T0 + 5)
                .build();
        SuiteApiEvent minimal = SuiteApiEvent.builder(SuiteApiEvent.Type.CHANGE, B, "m", T0).build();
        SuiteApiBatchResult r = h.client.pushEvents(Arrays.asList(full, minimal));
        assertEquals("one request", 1, h.countUrl(EVENTS_URL));
        Req q = h.lastTo(EVENTS_URL);
        assertEquals("POST", "POST", q.method);
        assertEquals("exact events body",
                "{\"event\":["
                + "{\"eventType\":\"DIAGNOSTIC\",\"resourceId\":\"" + A + "\","
                + "\"startTimeUTC\":" + T0 + ",\"cancelTimeUTC\":" + (T0 + 5) + ","
                + "\"message\":\"[WindowsEvent-Warning] disk\",\"severity\":\"WARNING\","
                + "\"diagnosticSubType\":\"LOG\",\"managedExternally\":true},"
                + "{\"eventType\":\"CHANGE\",\"resourceId\":\"" + B + "\","
                + "\"startTimeUTC\":" + T0 + ",\"message\":\"m\"}]}",
                q.body);
        SimpleJson root = SimpleJson.parse(q.body);
        assertEquals("parses: two events", 2, root.get("event").size());
        assertEquals("Content-Type JSON", "application/json", q.headers.get("Content-Type"));
        assertFalse("never the adapterkinds variant", q.url.contains("adapterkinds"));
        assertEquals("result", "sent=2 batchesOk=1 batchesFailed=0 fellBack=0 skipped=0 dropped=0 stopped=false",
                r.toString());
        assertTrue("clean", r.isClean());
    }

    private static void testEventsNotificationRefused() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        SuiteApiEvent n = SuiteApiEvent.builder(SuiteApiEvent.Type.NOTIFICATION, A,
                SECRET, T0).managedExternally(true).build();
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushEvents(Arrays.asList(n));
        assertEquals("nothing sent, not even a token", 0, h.requests.size());
        assertEquals("dropped 1", 1, r.getDropped());
        assertFalse("not clean", r.isClean());
        assertEquals("one WARN", 1, h.log.count("WARN"));
        assertTrue("WARN names the reason", h.log.contains("NOTIFICATION type=1"));
        assertTrue("WARN points at DIAGNOSTIC", h.log.contains("send DIAGNOSTIC"));
        assertFalse("WARN carries no message text", h.log.contains(SECRET));

        Harness h2 = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        SuiteApiBatchResult r2 = h2.client.pushEvents(Arrays.asList(n, diag(B, "ok")));
        assertFalse("mixed: the NOTIFICATION is not in the body",
                h2.lastTo(EVENTS_URL).body.contains("NOTIFICATION"));
        assertEquals("mixed: one sent", 1, r2.getSent());
        assertEquals("mixed: one dropped", 1, r2.getDropped());
    }

    private static void testEventsInvalidDropped() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        List<SuiteApiEvent> in = new ArrayList<>();
        in.add(null);
        in.add(diag("vm-42", "not a uuid"));
        in.add(diag(null, "null id"));
        in.add(diag(A, "  "));
        in.add(diag(A, null));
        in.add(SuiteApiEvent.builder(SuiteApiEvent.Type.DIAGNOSTIC, A, "early", 0L).build());
        in.add(SuiteApiEvent.builder(SuiteApiEvent.Type.DIAGNOSTIC, A, "cancel 0", T0)
                .cancelTimeUtc(0L).build());
        in.add(diag(A, "good"));
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushEvents(in);
        assertEquals("seven dropped", 7, r.getDropped());
        assertEquals("one sent", 1, r.getSent());
        Req q = h.lastTo(EVENTS_URL);
        assertEquals("only the good one in the body", 1, SimpleJson.parse(q.body).get("event").size());
        assertTrue("good one present", q.body.contains("\"good\""));
        assertEquals("one WARN", 1, h.log.count("WARN"));
        assertTrue("counts by reason", h.log.contains("resource id not a UUID=2"));
        assertTrue("blank message counted", h.log.contains("null or blank message=2"));
        assertTrue("times counted", h.log.contains("start or cancel time before 2000-01-01=2"));
        assertTrue("null event counted", h.log.contains("null event=1"));
        assertEquals("the NOTIFICATION hint only when one was refused", false,
                h.log.contains("send DIAGNOSTIC"));
    }

    private static void testEventsEscaping() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        String msg = "line1\r\nline2\t\"quoted\" \\ \u0001 end";
        h.client.pushEvents(Arrays.asList(diag(A, msg)));
        String body = h.lastTo(EVENTS_URL).body;
        assertFalse("no raw control character", SuiteApiStitchBatchTest.hasRawControl(body));
        assertEquals("message round-trips", msg,
                SimpleJson.parse(body).get("event").get(0).get("message").asString());
    }

    private static void testEventsChunking() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        List<SuiteApiEvent> in = new ArrayList<>();
        for (int i = 0; i < 5; i++) in.add(diag(A, "e" + i));
        SuiteApiBatchResult r = h.client.pushEvents(in, 2, 1_000_000);
        assertEquals("5 events at 2 per request: 3 requests", 3, h.countUrl(EVENTS_URL));
        assertEquals("all sent", 5, r.getSent());
        assertEquals("3 ok", 3, r.getBatchesOk());

        Harness hb = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        int one = SuiteApiStitchClient.eventJson(diag(A, "e0"), A).length();
        // Room for exactly two events per request by bytes.
        int cap = SuiteApiStitchClient.EVENTS_PREFIX.length() + 2 + one * 2 + 1;
        hb.client.pushEvents(in, 100, cap);
        assertEquals("by bytes: 3 requests", 3, hb.countUrl(EVENTS_URL));
        for (Req q : hb.requests) {
            if (EVENTS_URL.equals(q.url)) {
                assertTrue("each request within the cap", q.body.length() <= cap);
            }
        }
        Harness hc = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        hc.log.clear();
        hc.client.pushEvents(in, 0, 0);
        assertEquals("caps below 1: one request at the defaults", 1, hc.countUrl(EVENTS_URL));
        assertEquals("two WARNs for the two caps", 2, hc.log.count("WARN"));
    }

    private static void testEventsFailureStops() throws Exception {
        for (int code : new int[] {400, 413, 429, 500, 503}) {
            Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(code, "{}"));
            List<SuiteApiEvent> in = new ArrayList<>();
            for (int i = 0; i < 5; i++) in.add(diag(A, "e" + i));
            h.log.clear();
            SuiteApiBatchResult r = h.client.pushEvents(in, 2, 1_000_000);
            assertEquals("HTTP " + code + ": one request, then stop", 1, h.countUrl(EVENTS_URL));
            assertEquals("HTTP " + code + ": one WARN", 1, h.log.count("WARN"));
            assertEquals("HTTP " + code + ": result",
                    "sent=2 batchesOk=0 batchesFailed=1 fellBack=0 skipped=5 dropped=0 stopped=true",
                    r.toString());
            assertTrue("HTTP " + code + ": status in the WARN", h.log.contains("HTTP " + code));
        }
        Harness ht = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            throw new java.net.SocketTimeoutException("Read timed out");
        });
        SuiteApiBatchResult rt = ht.client.pushEvents(Arrays.asList(diag(A, "x"), diag(B, "y")), 1, 1_000_000);
        assertEquals("timeout: one request", 1, ht.countUrl(EVENTS_URL));
        assertTrue("timeout: stopped", rt.isStopped());
        assertEquals("timeout: both skipped", 2, rt.getSkipped());
        Harness hn = new Harness((m, u, b) -> new Resp(500, ""));
        SuiteApiBatchResult rn = hn.client.pushEvents(Arrays.asList(diag(A, "x")));
        assertEquals("token failure: nothing sent", 0, rn.getSent());
        assertEquals("token failure: one token attempt", 1, hn.countUrl(TOKEN_URL));
        assertEquals("token failure: skipped", 1, rn.getSkipped());
    }

    private static void testEvents401Retry() throws Exception {
        AtomicInteger tokens = new AtomicInteger();
        AtomicInteger posts = new AtomicInteger();
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) {
                return new Resp(200, "{\"token\":\"tok-" + tokens.incrementAndGet() + "\"}");
            }
            return posts.incrementAndGet() == 1 ? new Resp(401, "") : new Resp(200, "");
        });
        SuiteApiBatchResult r = h.client.pushEvents(Arrays.asList(diag(A, "x")));
        assertEquals("two posts", 2, posts.get());
        assertTrue("clean after the retry", r.isClean());
    }

    private static void testEventsMessageNotLogged() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(500, "x"), "DEBUG");
        h.log.clear();
        h.client.pushEvents(Arrays.asList(diag(A, SECRET)));
        assertTrue("the failure was logged", h.log.count("WARN") >= 1);
        assertFalse("the message text is in no log line: " + h.log.lines(), h.log.contains(SECRET));
        for (Throwable t : h.log.thrown()) {
            assertFalse("nor in a logged exception", String.valueOf(t.getMessage()).contains(SECRET));
        }
        assertFalse("toString carries no message", diag(A, SECRET).toString().contains(SECRET));
    }

    private static void testEventsNothing() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        assertTrue("null clean", h.client.pushEvents(null).isClean());
        assertTrue("empty clean", h.client.pushEvents(new ArrayList<>()).isClean());
        assertEquals("no request", 0, h.requests.size());
    }

    private static void testEventBuilder() throws Exception {
        try {
            SuiteApiEvent.builder(null, A, "m", T0);
            fail("null type must be refused");
        } catch (IllegalArgumentException e) {
            assertTrue("null type refused", true);
        }
        try {
            SuiteApiEvent.builder(SuiteApiEvent.Type.CHANGE, A, "m", T0)
                    .diagnosticSubType(SuiteApiEvent.DiagnosticSubType.LOG);
            fail("diagnosticSubType on CHANGE must be refused");
        } catch (IllegalArgumentException e) {
            assertTrue("subtype only on DIAGNOSTIC", e.getMessage().contains("DIAGNOSTIC"));
        }
        SuiteApiEvent e = diag(A, "m");
        SuiteApiEvent c = e.cancelledAt(T0 + 300_000);
        assertEquals("cancel keeps the message", e.getMessage(), c.getMessage());
        assertEquals("cancel keeps the resource", e.getResourceId(), c.getResourceId());
        assertEquals("cancel keeps the type", e.getType(), c.getType());
        assertEquals("cancel keeps the subtype", e.getDiagnosticSubType(), c.getDiagnosticSubType());
        assertEquals("cancel time set", Long.valueOf(T0 + 300_000), c.getCancelTimeUtc());
        assertEquals("original untouched", null, e.getCancelTimeUtc());
        for (SuiteApiEvent.Type t : SuiteApiEvent.Type.values()) {
            assertFalse("HARD_THRESHOLD not offered", t.name().equals("HARD_THRESHOLD"));
        }
    }

    private static void testEventsClosed() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        h.client.close();
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushEvents(Arrays.asList(diag(A, "x")));
        assertEquals("nothing sent", 0, h.countUrl(EVENTS_URL));
        assertTrue("stopped", r.isStopped());
        assertEquals("skipped", 1, r.getSkipped());
    }

    private static void testEventsFacade() throws Exception {
        FakeAdapter a = SuiteApiStitchClientTransportTest.allocate(FakeAdapter.class);
        a.requests = new ArrayList<>();
        a.responder = SuiteApiStitchClientTransportTest.okTokenThen(200, "");
        LogCapture log = LogCapture.create();
        SuiteApiStitcher st = SuiteApiStitcher.createExplicit(a, log.logger(), "localhost",
                SuiteApiStitchClientTransportTest.USER, "p");
        SuiteApiBatchResult r = st.pushEvents(Arrays.asList(diag(A, "x")))
                .plus(st.pushEvents(Arrays.asList(diag(A, "y"), diag(B, "z")), 1, 1000));
        int n = 0;
        for (Req q : a.requests) if (EVENTS_URL.equals(q.url)) n++;
        assertEquals("three event requests through the facade", 3, n);
        assertEquals("all ok", 3, r.getBatchesOk());
    }

    // -----------------------------------------------------------------------
    // T3 typed properties
    // -----------------------------------------------------------------------

    static Map<String, Map<String, String>> stringProps() {
        Map<String, Map<String, String>> in = new LinkedHashMap<>();
        Map<String, String> a = new LinkedHashMap<>();
        a.put("G|x", "false");
        a.put("G|q", "say \"hi\"\n");
        a.put("G|empty", "");
        a.put("G|num", "1.0");
        in.put(A, a);
        Map<String, String> b = new LinkedHashMap<>();
        b.put("G|x", "true");
        in.put(B.toUpperCase(), b);
        return in;
    }

    private static void testTypedStringsIdentical() throws Exception {
        Harness plain = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Harness typed = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        SuiteApiBatchResult rp = plain.client.pushPropertiesBatch(stringProps(), T0);
        SuiteApiBatchResult rt = typed.client.pushTypedPropertiesBatch(stringProps(), T0);
        String pb = plain.lastTo(PROPS_URL).body;
        assertEquals("byte-identical bodies", pb, typed.lastTo(PROPS_URL).body);
        assertEquals("golden string body (unchanged wire shape)",
                "{\"values\":["
                + "{\"resourceId\":\"" + A + "\",\"property-contents\":{\"property-content\":["
                + "{\"statKey\":\"G|x\",\"timestamps\":[" + T0 + "],\"values\":[\"false\"]},"
                + "{\"statKey\":\"G|q\",\"timestamps\":[" + T0 + "],\"values\":[\"say \\\"hi\\\"\\n\"]},"
                + "{\"statKey\":\"G|empty\",\"timestamps\":[" + T0 + "],\"values\":[\"\"]},"
                + "{\"statKey\":\"G|num\",\"timestamps\":[" + T0 + "],\"values\":[\"1.0\"]}]}},"
                + "{\"resourceId\":\"" + B + "\",\"property-contents\":{\"property-content\":["
                + "{\"statKey\":\"G|x\",\"timestamps\":[" + T0 + "],\"values\":[\"true\"]}]}}]}",
                pb);
        assertEquals("same result", rp.toString(), rt.toString());
        assertFalse("a string stays a string, never data", pb.contains("\"data\""));
        assertEquals("static entry builders agree",
                SuiteApiStitchClient.propertiesBatchEntry(A, stringProps().get(A), T0),
                SuiteApiStitchClient.propertiesBatchEntryOf(A, stringProps().get(A), T0));
    }

    private static void testTypedBatchStringsIdentical() throws Exception {
        Map<String, Map<String, Double>> stats = new LinkedHashMap<>();
        Map<String, Double> s = new LinkedHashMap<>();
        s.put("G|a", 2.5);
        stats.put(A, s);
        Harness plain = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Harness typed = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        plain.client.pushBatch(stringProps(), stats, T0);
        typed.client.pushTypedBatch(stringProps(), stats, T0);
        assertEquals("same request sequence", urls(plain), urls(typed));
        assertEquals("properties bodies identical", plain.lastTo(PROPS_URL).body,
                typed.lastTo(PROPS_URL).body);
        assertEquals("stats bodies identical", plain.lastTo(STATS_URL).body,
                typed.lastTo(STATS_URL).body);
        List<String> order = urls(typed);
        assertTrue("properties before stats", order.indexOf(PROPS_URL) < order.indexOf(STATS_URL));
    }

    static List<String> urls(Harness h) {
        List<String> u = new ArrayList<>();
        for (Req r : h.requests) u.add(r.url);
        return u;
    }

    private static void testTypedNumbers() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, Object>> in = new LinkedHashMap<>();
        Map<String, Object> v = new LinkedHashMap<>();
        v.put("Maintenance Mode Required", 1.0);
        v.put("G|int", 0);
        v.put("G|long", 42L);
        v.put("G|bd", new BigDecimal("2.5"));
        v.put("G|text", "UP");
        in.put(A, v);
        SuiteApiBatchResult r = h.client.pushTypedPropertiesBatch(in, T0);
        assertEquals("exact mixed body",
                "{\"values\":[{\"resourceId\":\"" + A + "\",\"property-contents\":{\"property-content\":["
                + "{\"statKey\":\"Maintenance Mode Required\",\"timestamps\":[" + T0 + "],\"data\":[1.0]},"
                + "{\"statKey\":\"G|int\",\"timestamps\":[" + T0 + "],\"data\":[0.0]},"
                + "{\"statKey\":\"G|long\",\"timestamps\":[" + T0 + "],\"data\":[42.0]},"
                + "{\"statKey\":\"G|bd\",\"timestamps\":[" + T0 + "],\"data\":[2.5]},"
                + "{\"statKey\":\"G|text\",\"timestamps\":[" + T0 + "],\"values\":[\"UP\"]}]}}]}",
                h.lastTo(PROPS_URL).body);
        SimpleJson pc = SimpleJson.parse(h.lastTo(PROPS_URL).body).get("values").get(0)
                .get("property-contents").get("property-content");
        for (SimpleJson e : pc.asList()) {
            assertFalse("never both data and values on one entry",
                    !e.get("data").isNull() && !e.get("values").isNull());
        }
        assertTrue("clean", r.isClean());
    }

    private static void testTypedRejected() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, Object>> in = new LinkedHashMap<>();
        Map<String, Object> v = new LinkedHashMap<>();
        v.put("G|ok", 3.0);
        v.put("G|nan", Double.NaN);
        v.put("G|fnan", Float.NaN);
        v.put("G|inf", Double.NEGATIVE_INFINITY);
        v.put("G|huge", new BigDecimal("1e400"));
        v.put("G|null", null);
        v.put("G|bool", Boolean.TRUE);
        v.put("G|obj", new Object());
        v.put(null, 1.0);
        in.put(A, v);
        Map<String, Object> onlyBad = new LinkedHashMap<>();
        onlyBad.put("G|nan", Double.NaN);
        in.put(B, onlyBad);
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushTypedPropertiesBatch(in, T0);
        String body = h.lastTo(PROPS_URL).body;
        assertEquals("only the finite number is sent",
                "{\"values\":[{\"resourceId\":\"" + A + "\",\"property-contents\":{\"property-content\":["
                + "{\"statKey\":\"G|ok\",\"timestamps\":[" + T0 + "],\"data\":[3.0]}]}}]}",
                body);
        assertFalse("never NaN on the wire", body.contains("NaN"));
        assertFalse("never Infinity on the wire", body.contains("Infinity"));
        assertFalse("never null on the wire", body.contains("null"));
        assertEquals("dropped counts entries", 9, r.getDropped());
        assertEquals("B had nothing left: skipped", 1, r.getSkipped());
        assertFalse("not clean", r.isClean());
        assertEquals("one WARN", 1, h.log.count("WARN"));
        assertTrue("WARN names the count and the rule",
                h.log.contains("pushTypedPropertiesBatch dropped 9 entries with a null key or a"
                        + " null, NaN, infinite, or neither string nor number value"));
    }

    private static void testUntypedStillStrict() throws Exception {
        // A caller defeating generics (raw map) must not change what the
        // string batch sends: a number is dropped as before, never "data".
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Object> v = new LinkedHashMap<>();
        v.put("G|x", "s");
        v.put("G|n", 1.0);
        Map<String, Map<String, Object>> raw = new LinkedHashMap<>();
        raw.put(A, v);
        @SuppressWarnings({"unchecked", "rawtypes"})
        Map<String, Map<String, String>> asStrings = (Map) raw;
        SuiteApiBatchResult r = h.client.pushPropertiesBatch(asStrings, T0);
        assertFalse("no data in a string batch", h.lastTo(PROPS_URL).body.contains("\"data\""));
        assertEquals("the number is dropped, as before", 1, r.getDropped());
    }

    private static void testTypedFallback() throws Exception {
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            if (u.equals(PROPS_URL)) return new Resp(400, "{\"apiErrorCode\":1}");
            return new Resp(200, "");
        });
        Map<String, Map<String, Object>> in = new LinkedHashMap<>();
        Map<String, Object> v = new LinkedHashMap<>();
        v.put("G|n", 7);
        v.put("G|s", "x");
        v.put("G|nan", Double.NaN);
        in.put(A, v);
        SuiteApiBatchResult r = h.client.pushTypedPropertiesBatch(in, 9L);
        Req per = h.lastTo(BASE + "/api/resources/" + A + "/properties");
        assertEquals("per-id body keeps the numeric shape and still drops NaN",
                "{\"property-content\":["
                + "{\"statKey\":\"G|n\",\"timestamps\":[9],\"data\":[7.0]},"
                + "{\"statKey\":\"G|s\",\"timestamps\":[9],\"values\":[\"x\"]}]}",
                per.body);
        assertEquals("fell back once", 1, r.getFellBack());
    }

    private static void testTypedFacade() throws Exception {
        FakeAdapter a = SuiteApiStitchClientTransportTest.allocate(FakeAdapter.class);
        a.requests = new ArrayList<>();
        a.responder = SuiteApiStitchClientTransportTest.okTokenThen(200, "");
        LogCapture log = LogCapture.create();
        SuiteApiStitcher st = SuiteApiStitcher.createExplicit(a, log.logger(), "localhost",
                SuiteApiStitchClientTransportTest.USER, "p");
        Map<String, Map<String, Object>> p = new LinkedHashMap<>();
        Map<String, Object> v = new LinkedHashMap<>();
        v.put("G|n", 1);
        p.put(A, v);
        Map<String, Map<String, Double>> s = new LinkedHashMap<>();
        Map<String, Double> sv = new LinkedHashMap<>();
        sv.put("G|a", 1.0);
        s.put(A, sv);
        SuiteApiBatchResult r = st.pushTypedPropertiesBatch(p, 1L)
                .plus(st.pushTypedPropertiesBatch(p, 1L, 1, 1000))
                .plus(st.pushTypedBatch(p, s, 1L))
                .plus(st.pushTypedBatch(p, s, 1L, 1, 1000));
        int n = 0;
        for (Req q : a.requests) if (q.url.equals(PROPS_URL) || q.url.equals(STATS_URL)) n++;
        assertEquals("six batch requests through the facade", 6, n);
        assertEquals("all ok", 6, r.getBatchesOk());
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
