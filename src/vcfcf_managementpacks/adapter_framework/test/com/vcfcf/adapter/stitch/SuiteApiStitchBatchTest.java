package com.vcfcf.adapter.stitch;

import com.vcfcf.adapter.LogCapture;
import com.vcfcf.adapter.json.SimpleJson;
import com.vcfcf.adapter.stitch.SuiteApiStitchClientTransportTest.FakeAdapter;
import com.vcfcf.adapter.stitch.SuiteApiStitchClientTransportTest.Harness;
import com.vcfcf.adapter.stitch.SuiteApiStitchClientTransportTest.Req;
import com.vcfcf.adapter.stitch.SuiteApiStitchClientTransportTest.Resp;
import com.vcfcf.adapter.stitch.SuiteApiStitchClientTransportTest.Responder;

import java.io.IOException;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Batch push tests for {@link SuiteApiStitchClient#pushPropertiesBatch},
 * {@link SuiteApiStitchClient#pushStatsBatch} and
 * {@link SuiteApiStitchClient#pushBatch} (buildkit 1.0.24, compliance#17),
 * against the scripted fake Suite API of
 * {@link SuiteApiStitchClientTransportTest}: body shapes for both kinds,
 * chunking by count and by bytes, the oversized resource, the per-id
 * fallback on a failed batch, the single 401 retry, and properties-before-stats
 * order. Wire format: {@code knowledge/context/api-surface/suite_api_batch_push.md}.
 *
 * <p>No JUnit required: call via {@code main()}. Needs log4j-api and
 * log4j-core at runtime (as the transport test does); without them the
 * suite is SKIPPED with a message.
 *
 * <p>Run (from {@code src/vcfcf_managementpacks/}):
 * <pre>
 *   javac -cp adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         $(find adapter_framework/test -name '*.java') -d build/test-classes
 *   java -cp build/test-classes:adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar:adapter_runtime/lib/* \
 *         com.vcfcf.adapter.stitch.SuiteApiStitchBatchTest
 * </pre>
 */
public class SuiteApiStitchBatchTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;

    static final String BASE = SuiteApiStitchClientTransportTest.BASE;
    static final String TOKEN_URL = SuiteApiStitchClientTransportTest.TOKEN_URL;
    static final String STATS_URL = BASE + "/api/resources/stats";
    static final String PROPS_URL = BASE + "/api/resources/properties";

    static final String A = "6baa06d3-0811-45a2-ba2a-c7b38f646ce9";
    static final String B = "1e9de40c-b045-4f9e-9b4f-be7d471773e6";
    static final String C = "35603c17-6c40-4137-a41d-2fb406281543";

    public static void main(String[] args) throws Exception {
        if (!LogCapture.available()) {
            System.out.println("  SKIP: all batch tests: log4j-api/log4j-core not on the"
                    + " runtime classpath (add a jar carrying them, e.g. adapter_runtime/lib/*)");
            System.out.println();
            System.out.println("OK: 0/0 tests passed (1 group(s) skipped).");
            return;
        }
        run("stats batch body shape", SuiteApiStitchBatchTest::testStatsBodyShape);
        run("properties batch body shape", SuiteApiStitchBatchTest::testPropertiesBodyShape);
        run("per-id bodies unchanged", SuiteApiStitchBatchTest::testPerIdBodiesUnchanged);
        run("chunking by count", SuiteApiStitchBatchTest::testChunkByCount);
        run("chunking by bytes", SuiteApiStitchBatchTest::testChunkByBytes);
        run("oversized resource is sent alone", SuiteApiStitchBatchTest::testOversizedAlone);
        run("chunk() packing edge cases", SuiteApiStitchBatchTest::testChunkUnit);
        run("caps below 1 fall back to the defaults", SuiteApiStitchBatchTest::testBadCaps);
        run("non-2xx batch: one WARN, per-id fallback", SuiteApiStitchBatchTest::testFallbackOnFailure);
        run("fallback is per chunk", SuiteApiStitchBatchTest::testFallbackOnlyFailedChunk);
        run("timeout: no fallback, no retry", SuiteApiStitchBatchTest::testTimeoutNoFallback);
        run("401: one re-acquire and retry", SuiteApiStitchBatchTest::test401RetryOnce);
        run("401 after the retry: no fallback", SuiteApiStitchBatchTest::testPersistent401NoFallback);
        run("pushBatch: properties before stats", SuiteApiStitchBatchTest::testOrder);
        run("ids validated, normalized and merged", SuiteApiStitchBatchTest::testIdHandling);
        run("bad values dropped, not the batch", SuiteApiStitchBatchTest::testBadValuesDropped);
        run("nothing to send: no request", SuiteApiStitchBatchTest::testNothingToSend);
        run("interrupt stops the call, flag restored", SuiteApiStitchBatchTest::testInterruptStops);
        run("closed client: nothing sent", SuiteApiStitchBatchTest::testClosedClient);
        run("facade delegates", SuiteApiStitchBatchTest::testFacade);
        report();
    }

    // -----------------------------------------------------------------------
    // Body shapes
    // -----------------------------------------------------------------------

    private static void testStatsBodyShape() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        in.put(A, stats("G|a", 1.0, "G|b", 2.5));
        in.put(B, stats("G|a", 48.0));
        SuiteApiBatchResult r = h.client.pushStatsBatch(in, 1793178366127L);
        assertEquals("one batch request", 1, h.countUrl(STATS_URL));
        assertEquals("no per-id request", 0, perIdCount(h));
        Req q = h.lastTo(STATS_URL);
        assertEquals("POST", "POST", q.method);
        assertEquals("exact stats body",
                "{\"resource-stat-content\":["
                + "{\"id\":\"" + A + "\",\"stat-contents\":["
                + "{\"statKey\":\"G|a\",\"timestamps\":[1793178366127],\"data\":[1.0]},"
                + "{\"statKey\":\"G|b\",\"timestamps\":[1793178366127],\"data\":[2.5]}]},"
                + "{\"id\":\"" + B + "\",\"stat-contents\":["
                + "{\"statKey\":\"G|a\",\"timestamps\":[1793178366127],\"data\":[48.0]}]}]}",
                q.body);
        SimpleJson root = SimpleJson.parse(q.body);
        assertTrue("stat-contents is a bare array",
                root.get("resource-stat-content").asList().get(0).get("stat-contents").isList());
        assertFalse("no resourceId key in a stats body", q.body.contains("resourceId"));
        assertFalse("disableAnalyticsProcessing never sent", q.url.contains("disableAnalytics"));
        assertEquals("Content-Type JSON", "application/json", q.headers.get("Content-Type"));
        assertEquals("OpsToken auth", "OpsToken tok-1", q.headers.get("Authorization"));
        assertEquals("result", "sent=2 batchesOk=1 batchesFailed=0 fellBack=0 skipped=0",
                r.toString());
        assertTrue("clean", r.isClean());
    }

    private static void testPropertiesBodyShape() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, String>> in = new LinkedHashMap<>();
        in.put(A, props("G|x", "false", "G|q", "say \"hi\""));
        in.put(B, props("G|x", "true"));
        SuiteApiBatchResult r = h.client.pushPropertiesBatch(in, 7L);
        assertEquals("one batch request", 1, h.countUrl(PROPS_URL));
        Req q = h.lastTo(PROPS_URL);
        assertEquals("exact properties body",
                "{\"values\":["
                + "{\"resourceId\":\"" + A + "\",\"property-contents\":{\"property-content\":["
                + "{\"statKey\":\"G|x\",\"timestamps\":[7],\"values\":[\"false\"]},"
                + "{\"statKey\":\"G|q\",\"timestamps\":[7],\"values\":[\"say \\\"hi\\\"\"]}]}},"
                + "{\"resourceId\":\"" + B + "\",\"property-contents\":{\"property-content\":["
                + "{\"statKey\":\"G|x\",\"timestamps\":[7],\"values\":[\"true\"]}]}}]}",
                q.body);
        SimpleJson e0 = SimpleJson.parse(q.body).get("values").asList().get(0);
        assertTrue("property-contents is an object",
                e0.get("property-contents").isObject());
        assertTrue("property-content inside it is an array",
                e0.get("property-contents").get("property-content").isList());
        assertFalse("no bare id key in a properties body", q.body.contains("\"id\":"));
        assertEquals("sent", 2, r.getSent());
        assertEquals("batchesOk", 1, r.getBatchesOk());
    }

    private static void testPerIdBodiesUnchanged() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        h.client.pushStats(A, stats("G|a", 1.0), 5L);
        h.client.pushProperties(A, props("G|x", "v"), 5L);
        assertEquals("per-id stats body",
                "{\"stat-content\":[{\"statKey\":\"G|a\",\"timestamps\":[5],\"data\":[1.0]}]}",
                h.lastTo(BASE + "/api/resources/" + A + "/stats").body);
        assertEquals("per-id properties body",
                "{\"property-content\":[{\"statKey\":\"G|x\",\"timestamps\":[5],\"values\":[\"v\"]}]}",
                h.lastTo(BASE + "/api/resources/" + A + "/properties").body);
    }

    // -----------------------------------------------------------------------
    // Chunking
    // -----------------------------------------------------------------------

    private static void testChunkByCount() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        List<String> ids = uuids(5);
        for (String id : ids) in.put(id, stats("G|a", 1.0));
        SuiteApiBatchResult r = h.client.pushStatsBatch(in, 1L, 2, 1_000_000);
        List<Req> batches = to(h, STATS_URL);
        assertEquals("5 resources at 2 per request: 3 requests", 3, batches.size());
        assertEquals("sizes 2,2,1", "[2, 2, 1]", sizes(batches, "resource-stat-content").toString());
        assertEquals("caller order kept", ids, idsIn(batches, "resource-stat-content", "id"));
        assertEquals("result", "sent=5 batchesOk=3 batchesFailed=0 fellBack=0 skipped=0",
                r.toString());
    }

    private static void testChunkByBytes() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, String>> in = new LinkedHashMap<>();
        List<String> ids = uuids(5);
        for (String id : ids) in.put(id, props("G|d", repeat('x', 200)));
        int entry = SuiteApiStitchClient.propertiesBatchEntry(ids.get(0),
                props("G|d", repeat('x', 200)), 1L).getBytes(StandardCharsets.UTF_8).length;
        int prefix = SuiteApiStitchClient.PROPERTIES_BATCH_PREFIX.length();
        // Room for exactly two entries: prefix + e + "," + e + "]}".
        int cap = prefix + 2 * entry + 1 + 2;
        h.client.pushPropertiesBatch(in, 1L, 100, cap);
        List<Req> batches = to(h, PROPS_URL);
        assertEquals("5 resources at 2 per byte cap: 3 requests", 3, batches.size());
        assertEquals("sizes 2,2,1", "[2, 2, 1]", sizes(batches, "values").toString());
        boolean within = true;
        for (Req q : batches) within &= q.body.getBytes(StandardCharsets.UTF_8).length <= cap;
        assertTrue("every body within the byte cap", within);
        assertEquals("a full body is exactly the cap",
                cap, batches.get(0).body.getBytes(StandardCharsets.UTF_8).length);
        assertEquals("caller order kept", ids, idsIn(batches, "values", "resourceId"));

        // One byte less and only one fits per request.
        Harness h2 = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        h2.client.pushPropertiesBatch(in, 1L, 100, cap - 1);
        assertEquals("one byte under: one per request", 5, to(h2, PROPS_URL).size());

        // Multi-byte characters count as bytes, not chars.
        Harness h3 = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, String>> wide = new LinkedHashMap<>();
        for (String id : uuids(2)) wide.put(id, props("G|d", repeat('é', 200)));
        h3.client.pushPropertiesBatch(wide, 1L, 100, cap);
        assertEquals("two-byte chars: the same cap holds one each", 2, to(h3, PROPS_URL).size());
    }

    private static void testOversizedAlone() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, String>> in = new LinkedHashMap<>();
        in.put(A, props("G|s", "small"));
        in.put(B, props("G|big", repeat('y', 5000)));
        in.put(C, props("G|s", "small"));
        SuiteApiBatchResult r = h.client.pushPropertiesBatch(in, 1L, 100, 1000);
        List<Req> batches = to(h, PROPS_URL);
        assertEquals("small, big alone, small: 3 requests", 3, batches.size());
        assertEquals("ids per request", "[" + A + ", " + B + ", " + C + "]",
                idsIn(batches, "values", "resourceId").toString());
        assertTrue("the oversized body is over the cap and still sent",
                batches.get(1).body.length() > 1000);
        assertEquals("nothing skipped", 0, r.getSkipped());
        assertEquals("three batches ok", 3, r.getBatchesOk());

        // Two smalls around nothing big pack together.
        Harness h2 = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, String>> in2 = new LinkedHashMap<>();
        in2.put(A, props("G|big", repeat('y', 5000)));
        in2.put(B, props("G|s", "small"));
        in2.put(C, props("G|s", "small"));
        h2.client.pushPropertiesBatch(in2, 1L, 100, 1000);
        assertEquals("big first, then the two smalls together", "[1, 2]",
                sizes(to(h2, PROPS_URL), "values").toString());
    }

    private static void testChunkUnit() {
        List<SuiteApiStitchClient.BatchEntry> es = new ArrayList<>();
        for (int i = 0; i < 4; i++) {
            es.add(new SuiteApiStitchClient.BatchEntry("id" + i, repeat('a', 10), null));
        }
        // prefix 3 + "]}" 2 = 5; entries 10 each plus a comma between.
        assertEquals("cap 15 fits one", 4, SuiteApiStitchClient.chunk(es, 3, 100, 15).size());
        assertEquals("cap 25 fits one (needs 26 for two)", 4,
                SuiteApiStitchClient.chunk(es, 3, 100, 25).size());
        assertEquals("cap 26 fits two", 2, SuiteApiStitchClient.chunk(es, 3, 100, 26).size());
        assertEquals("cap 1 still sends each alone", 4,
                SuiteApiStitchClient.chunk(es, 3, 100, 1).size());
        assertEquals("count 1", 4, SuiteApiStitchClient.chunk(es, 3, 1, 1_000_000).size());
        assertEquals("count 3", 2, SuiteApiStitchClient.chunk(es, 3, 3, 1_000_000).size());
        assertEquals("empty in, empty out", 0,
                SuiteApiStitchClient.chunk(new ArrayList<>(), 3, 3, 100).size());
    }

    private static void testBadCaps() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        for (String id : uuids(3)) in.put(id, stats("G|a", 1.0));
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushStatsBatch(in, 1L, 0, -5);
        assertEquals("defaults used: one request", 1, to(h, STATS_URL).size());
        assertEquals("two WARNs, one per bad cap", 2, h.log.count("WARN"));
        assertEquals("sent", 3, r.getSent());
    }

    // -----------------------------------------------------------------------
    // Failure handling
    // -----------------------------------------------------------------------

    private static void testFallbackOnFailure() throws Exception {
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            if (u.equals(STATS_URL)) return new Resp(500, "{\"apiErrorCode\":100}");
            return new Resp(200, "");
        });
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        List<String> ids = uuids(5);
        for (String id : ids) in.put(id, stats("G|a", 1.0));
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushStatsBatch(in, 9L);
        assertEquals("the batch is sent once (no blind retry on 5xx)", 1, h.countUrl(STATS_URL));
        assertEquals("one per-id push per resource", 5, perIdCount(h));
        Req first = h.lastTo(BASE + "/api/resources/" + ids.get(0) + "/stats");
        assertEquals("fallback body is the per-id shape",
                "{\"stat-content\":[{\"statKey\":\"G|a\",\"timestamps\":[9],\"data\":[1.0]}]}",
                first.body);
        assertEquals("one WARN for the failed batch", 1, h.log.count("WARN"));
        assertTrue("WARN names the count", h.log.contains("batch of 5 resource(s) failed"));
        assertTrue("WARN names the first ids",
                h.log.contains("[" + ids.get(0) + ", " + ids.get(1) + ", " + ids.get(2) + "]"));
        assertFalse("WARN does not list every id", h.log.contains(ids.get(4)));
        assertTrue("WARN names the status", h.log.contains("HTTP 500"));
        assertTrue("WARN says what happens next", h.log.contains("per-id path"));
        assertEquals("no stack trace at WARN", 0, h.log.thrown().size());
        assertEquals("result", "sent=5 batchesOk=0 batchesFailed=1 fellBack=5 skipped=0",
                r.toString());
        assertFalse("not clean", r.isClean());
    }

    private static void testFallbackOnlyFailedChunk() throws Exception {
        AtomicInteger batchCalls = new AtomicInteger();
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            if (u.equals(PROPS_URL)) {
                return batchCalls.incrementAndGet() == 2 ? new Resp(400, "") : new Resp(200, "");
            }
            return new Resp(200, "");
        });
        Map<String, Map<String, String>> in = new LinkedHashMap<>();
        List<String> ids = uuids(5);
        for (String id : ids) in.put(id, props("G|x", "v"));
        SuiteApiBatchResult r = h.client.pushPropertiesBatch(in, 1L, 2, 1_000_000);
        assertEquals("three batches", 3, h.countUrl(PROPS_URL));
        assertEquals("only the failed chunk's two fall back", 2, perIdCount(h));
        assertEquals("they are the second chunk's", 1,
                h.countUrl(BASE + "/api/resources/" + ids.get(2) + "/properties"));
        assertEquals("result", "sent=5 batchesOk=2 batchesFailed=1 fellBack=2 skipped=0",
                r.toString());
    }

    private static void testTimeoutNoFallback() throws Exception {
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            if (u.equals(STATS_URL)) throw new SocketTimeoutException("Read timed out");
            return new Resp(200, "");
        });
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        for (String id : uuids(4)) in.put(id, stats("G|a", 1.0));
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushStatsBatch(in, 1L, 2, 1_000_000);
        assertEquals("each batch sent once, none re-sent", 2, h.countUrl(STATS_URL));
        assertEquals("no per-id fallback after a timeout", 0, perIdCount(h));
        assertEquals("one WARN per failed batch", 2, h.log.count("WARN"));
        assertTrue("WARN says it may have been applied", h.log.contains("may have been applied"));
        assertEquals("result", "sent=4 batchesOk=0 batchesFailed=2 fellBack=0 skipped=0",
                r.toString());
    }

    private static void test401RetryOnce() throws Exception {
        AtomicInteger tokens = new AtomicInteger();
        AtomicInteger batchCalls = new AtomicInteger();
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) {
                return new Resp(200, "{\"token\":\"tok-" + tokens.incrementAndGet() + "\"}");
            }
            if (u.equals(STATS_URL)) {
                return batchCalls.incrementAndGet() == 1 ? new Resp(401, "") : new Resp(200, "");
            }
            return new Resp(200, "");
        });
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        for (String id : uuids(3)) in.put(id, stats("G|a", 1.0));
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushStatsBatch(in, 1L);
        assertEquals("token acquired twice", 2, h.countUrl(TOKEN_URL));
        assertEquals("batch sent twice (one retry)", 2, h.countUrl(STATS_URL));
        assertEquals("the retry carries the new token", "OpsToken tok-2",
                h.lastTo(STATS_URL).headers.get("Authorization"));
        assertEquals("no per-id fallback", 0, perIdCount(h));
        assertEquals("no WARN", 0, h.log.count("WARN"));
        assertEquals("result", "sent=3 batchesOk=1 batchesFailed=0 fellBack=0 skipped=0",
                r.toString());
    }

    private static void testPersistent401NoFallback() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(401, ""));
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        for (String id : uuids(3)) in.put(id, stats("G|a", 1.0));
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushStatsBatch(in, 1L);
        assertEquals("batch sent twice (one retry), no more", 2, h.countUrl(STATS_URL));
        assertEquals("no per-id fallback for a refused credential", 0, perIdCount(h));
        assertTrue("WARN says why", h.log.contains("401 after the token retry"));
        assertEquals("result", "sent=3 batchesOk=0 batchesFailed=1 fellBack=0 skipped=0",
                r.toString());
    }

    // -----------------------------------------------------------------------
    // Order, ids, values
    // -----------------------------------------------------------------------

    private static void testOrder() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, String>> p = new LinkedHashMap<>();
        Map<String, Map<String, Double>> s = new LinkedHashMap<>();
        for (String id : uuids(3)) {
            p.put(id, props("G|x", "v"));
            s.put(id, stats("G|a", 1.0));
        }
        SuiteApiBatchResult r = h.client.pushBatch(p, s, 1L, 2, 1_000_000);
        List<String> order = new ArrayList<>();
        for (Req q : h.requests) {
            if (q.url.equals(PROPS_URL)) order.add("P");
            if (q.url.equals(STATS_URL)) order.add("S");
        }
        assertEquals("every properties batch before any stats batch", "[P, P, S, S]",
                order.toString());
        assertEquals("summed result", "sent=6 batchesOk=4 batchesFailed=0 fellBack=0 skipped=0",
                r.toString());

        // The properties fallback also finishes before stats start.
        Harness h2 = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            if (u.equals(PROPS_URL)) return new Resp(500, "");
            return new Resp(200, "");
        });
        h2.client.pushBatch(p, s, 1L);
        List<String> order2 = new ArrayList<>();
        for (Req q : h2.requests) {
            if (q.url.equals(TOKEN_URL)) continue;
            order2.add(q.url.equals(STATS_URL) ? "S"
                    : q.url.equals(PROPS_URL) ? "P" : q.url.endsWith("/properties") ? "p" : "?");
        }
        assertEquals("properties batch, its per-id fallback, then stats", "[P, p, p, p, S]",
                order2.toString());
    }

    private static void testIdHandling() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        in.put("not-a-uuid", stats("G|a", 1.0));
        in.put(A + "/stats\r\nX: y", stats("G|a", 1.0));
        in.put(null, stats("G|a", 1.0));
        in.put(" " + A.toUpperCase(java.util.Locale.ROOT) + " ", stats("G|a", 1.0, "G|b", 2.0));
        in.put(A, stats("G|b", 3.0));
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushStatsBatch(in, 1L);
        Req q = h.lastTo(STATS_URL);
        assertEquals("the two spellings of A merged, later value wins",
                "{\"resource-stat-content\":[{\"id\":\"" + A + "\",\"stat-contents\":["
                + "{\"statKey\":\"G|a\",\"timestamps\":[1],\"data\":[1.0]},"
                + "{\"statKey\":\"G|b\",\"timestamps\":[1],\"data\":[3.0]}]}]}",
                q.body);
        assertEquals("one WARN for the bad ids", 1, h.log.count("WARN"));
        assertTrue("WARN counts them", h.log.contains("skipped 3 resource id(s)"));
        assertFalse("no raw CR/LF in the log", h.log.contains("\r\nX: y"));
        assertEquals("result", "sent=1 batchesOk=1 batchesFailed=0 fellBack=0 skipped=3",
                r.toString());
    }

    private static void testBadValuesDropped() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        Map<String, Double> mixed = new LinkedHashMap<>();
        mixed.put("G|ok", 1.0);
        mixed.put("G|nan", Double.NaN);
        mixed.put("G|inf", Double.POSITIVE_INFINITY);
        mixed.put("G|null", null);
        mixed.put(null, 2.0);
        in.put(A, mixed);
        in.put(B, stats("G|nan", Double.NaN));
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushStatsBatch(in, 1L);
        Req q = h.lastTo(STATS_URL);
        assertEquals("only the finite value is sent",
                "{\"resource-stat-content\":[{\"id\":\"" + A + "\",\"stat-contents\":["
                + "{\"statKey\":\"G|ok\",\"timestamps\":[1],\"data\":[1.0]}]}]}",
                q.body);
        assertTrue("one WARN with the count", h.log.contains("dropped 5 entries"));
        assertEquals("B had nothing left: skipped", 1, r.getSkipped());

        Harness h2 = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, String>> pin = new LinkedHashMap<>();
        Map<String, String> pm = new LinkedHashMap<>();
        pm.put("G|x", "v");
        pm.put("G|null", null);
        pin.put(A, pm);
        h2.log.clear();
        h2.client.pushPropertiesBatch(pin, 1L);
        assertFalse("null property value not sent", h2.lastTo(PROPS_URL).body.contains("G|null"));
        assertTrue("one WARN with the count", h2.log.contains("dropped 1 entry"));
    }

    private static void testNothingToSend() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        in.put(A, new LinkedHashMap<>());
        in.put(B, null);
        SuiteApiBatchResult r1 = h.client.pushStatsBatch(in, 1L);
        SuiteApiBatchResult r2 = h.client.pushStatsBatch(null, 1L);
        SuiteApiBatchResult r3 = h.client.pushPropertiesBatch(new LinkedHashMap<>(), 1L);
        assertEquals("no request at all, not even a token", 0, h.requests.size());
        assertEquals("empty maps are not skipped", "sent=0 batchesOk=0 batchesFailed=0 fellBack=0 skipped=0",
                r1.toString());
        assertTrue("null and empty in: clean", r2.isClean() && r3.isClean());
    }

    private static void testInterruptStops() throws Exception {
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            throw SuiteApiStitchClientTransportTest.<RuntimeException>sneakyThrow(
                    new InterruptedException("collector shutting down"));
        });
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        for (String id : uuids(5)) in.put(id, stats("G|a", 1.0));
        SuiteApiBatchResult r;
        try {
            r = h.client.pushStatsBatch(in, 1L, 2, 1_000_000);
            assertTrue("interrupt flag restored", Thread.interrupted());
        } finally {
            Thread.interrupted();
        }
        assertEquals("only the first batch was tried", 1, h.countUrl(STATS_URL));
        assertEquals("no fallback", 0, perIdCount(h));
        assertEquals("result", "sent=2 batchesOk=0 batchesFailed=1 fellBack=0 skipped=3",
                r.toString());
    }

    private static void testClosedClient() throws Exception {
        Harness h = new Harness(SuiteApiStitchClientTransportTest.okTokenThen(200, ""));
        h.client.close();
        h.requests.clear();
        Map<String, Map<String, Double>> in = new LinkedHashMap<>();
        for (String id : uuids(3)) in.put(id, stats("G|a", 1.0));
        h.log.clear();
        SuiteApiBatchResult r = h.client.pushStatsBatch(in, 1L, 1, 1_000_000);
        h.client.pushStatsBatch(in, 1L, 1, 1_000_000);
        assertEquals("nothing sent, no token", 0, h.requests.size());
        assertEquals("first chunk refused, the rest not tried",
                "sent=1 batchesOk=0 batchesFailed=1 fellBack=0 skipped=2", r.toString());
        assertEquals("one closed-client WARN across both calls (#217)", 1, h.log.count("WARN"));
        assertTrue("the WARN says the client is closed", h.log.contains("is closed"));
    }

    private static void testFacade() throws Exception {
        FakeAdapter a = SuiteApiStitchClientTransportTest.allocate(FakeAdapter.class);
        a.requests = new ArrayList<>();
        a.responder = SuiteApiStitchClientTransportTest.okTokenThen(200, "");
        LogCapture log = LogCapture.create();
        SuiteApiStitcher st = SuiteApiStitcher.createExplicit(a, log.logger(), "localhost",
                SuiteApiStitchClientTransportTest.USER, "p");
        Map<String, Map<String, String>> p = new LinkedHashMap<>();
        p.put(A, props("G|x", "v"));
        Map<String, Map<String, Double>> s = new LinkedHashMap<>();
        s.put(A, stats("G|a", 1.0));
        SuiteApiBatchResult r = st.pushBatch(p, s, 1L);
        r = r.plus(st.pushPropertiesBatch(p, 1L)).plus(st.pushStatsBatch(s, 1L))
                .plus(st.pushPropertiesBatch(p, 1L, 1, 1000)).plus(st.pushStatsBatch(s, 1L, 1, 1000))
                .plus(st.pushBatch(p, s, 1L, 1, 1000));
        int batches = 0;
        for (Req q : a.requests) if (q.url.equals(PROPS_URL) || q.url.equals(STATS_URL)) batches++;
        assertEquals("eight batch requests through the facade", 8, batches);
        assertEquals("all ok", 8, r.getBatchesOk());
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    static Map<String, Double> stats(Object... kv) {
        Map<String, Double> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], (Double) kv[i + 1]);
        return m;
    }

    static Map<String, String> props(String... kv) {
        Map<String, String> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put(kv[i], kv[i + 1]);
        return m;
    }

    static List<String> uuids(int n) {
        List<String> ids = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            ids.add(String.format("00000000-0000-4000-8000-%012d", i + 1));
        }
        return ids;
    }

    static String repeat(char c, int n) {
        StringBuilder sb = new StringBuilder(n);
        for (int i = 0; i < n; i++) sb.append(c);
        return sb.toString();
    }

    static List<Req> to(Harness h, String url) {
        List<Req> out = new ArrayList<>();
        for (Req q : h.requests) if (url.equals(q.url)) out.add(q);
        return out;
    }

    /** Requests to a per-id push path ({@code /api/resources/<uuid>/stats|properties}). */
    static int perIdCount(Harness h) {
        int n = 0;
        for (Req q : h.requests) {
            if (q.url.matches(".*/api/resources/[0-9a-f-]{36}/(stats|properties)")) n++;
        }
        return n;
    }

    static List<Integer> sizes(List<Req> batches, String outerKey) {
        List<Integer> out = new ArrayList<>();
        for (Req q : batches) out.add(SimpleJson.parse(q.body).get(outerKey).size());
        return out;
    }

    static List<String> idsIn(List<Req> batches, String outerKey, String idKey) {
        List<String> out = new ArrayList<>();
        for (Req q : batches) {
            for (SimpleJson e : SimpleJson.parse(q.body).get(outerKey).asList()) {
                out.add(e.get(idKey).asString(null));
            }
        }
        return out;
    }

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
