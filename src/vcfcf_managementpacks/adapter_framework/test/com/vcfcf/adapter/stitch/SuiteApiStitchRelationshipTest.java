package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.Logger;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.spi.VcfCfCollector;
import com.vcfcf.adapter.spi.VcfCfTester;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.lang.reflect.Proxy;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLConnection;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Tests for the additive Suite API relationship call
 * ({@link SuiteApiStitchClient#addChildren}, {@link SuiteApiStitcher#addChild})
 * and the singleton id lookup
 * ({@link SuiteApiStitchClient#findSingletonResourceId}).
 *
 * <p>No JUnit required: call via {@code main()}.
 *
 * <p>Two groups:
 * <ol>
 *   <li><strong>Pure helpers</strong> (path, {@code uuid-values} body, UUID
 *       check, resource-list parse, no PUT/replace method on the public
 *       surface). Run on the standard SDK + framework classpath.</li>
 *   <li><strong>Transport</strong>: a real {@link SuiteApiStitchClient}
 *       whose adapter's {@code openPlatformConnection} is overridden to
 *       return a scripted fake {@link HttpURLConnection}, so the test sees
 *       the exact verb, URL, headers and body sent, and can script 204, 401,
 *       500 and transport exceptions. The client needs an SDK
 *       {@link Logger}, which wraps a log4j-api logger; the test builds one
 *       around a recording {@link Proxy} (every {@code isXxxEnabled} answers
 *       false, so no log4j-core is needed, and {@code isWarnEnabled} calls
 *       count WARNs). This needs log4j-api at runtime, which the SDK jar
 *       does not carry; when it is absent the transport group is SKIPPED with
 *       a message (same convention as {@code AmbientCredentialTest}'s Crypt
 *       SKIP). Any jar carrying log4j-api works, for example the gitignored
 *       {@code adapter_runtime/lib/mpb_adapter-*.jar}.</li>
 * </ol>
 *
 * <p>Adapters are created with {@code sun.misc.Unsafe.allocateInstance}
 * (constructors need the collector's log4j-core runtime), as in
 * {@code CertificateReviewTest}.
 *
 * <p>Run (from {@code src/vcfcf_managementpacks/}):
 * <pre>
 *   javac -cp adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         adapter_framework/test/com/vcfcf/adapter/stitch/SuiteApiStitchRelationshipTest.java \
 *         -d build/test-classes
 *   java -cp build/test-classes:adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar:adapter_runtime/lib/* \
 *         com.vcfcf.adapter.stitch.SuiteApiStitchRelationshipTest
 * </pre>
 */
public class SuiteApiStitchRelationshipTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;
    private static int skipped = 0;

    static final String PARENT = "6baa06d3-0811-45a2-ba2a-c7b38f646ce9";
    static final String CHILD_A = "c87c8e39-7cf8-4394-bbf8-04ccd8601efc";
    static final String CHILD_B = "df6de846-0e97-408d-bcff-be0026eba68a";
    static final String WORLD_1 = "0f1e2d3c-4b5a-4968-8776-a5b4c3d2e1f0";
    static final String WORLD_2 = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d";
    static final String OTHER_1 = "9e8d7c6b-5a49-4837-a625-14f3e2d1c0b9";
    static final String BASE = "https://localhost/suite-api";
    static final String TOKEN_URL = BASE + "/api/auth/token/acquire";
    static final String CHILDREN_URL = BASE + "/api/resources/" + PARENT
            + "/relationships/children";

    public static void main(String[] args) throws Exception {
        testPathAndBody();
        testIsUuid();
        testParseResourceIds();
        testNoReplaceVerbOnPublicSurface();
        testNormalizeUuid();
        testLoggable();
        testFailureClassification();

        if (!log4jApiPresent()) {
            skip("transport tests: log4j-api not on the runtime classpath"
                    + " (add a jar carrying it, e.g. adapter_runtime/lib/*)");
        } else {
            testAddChildIsAdditivePost();
            testAddChildrenDedupesAndSkipsInvalid();
            testAddChildrenNothingValidSendsNothing();
            testAddChildServerErrorDoesNotThrow();
            testAddChildTransportExceptionDoesNotThrow();
            testAddChildRetriesOnceOn401();
            testAddChildPerpetual401StopsAfterOneRetry();
            testFacadeDelegatesAddChild();
            testFindSingletonOneMatch();
            testFindSingletonZeroMatches();
            testFindSingletonAmbiguousReturnsNothing();
            testFindSingletonFailureDoesNotThrow();
            testFindSingletonMalformedJsonDoesNotThrow();
            testFindSingletonPartialPageReturnsNothing();
            testFindSingletonTrimsKinds();
            testFindSingletonDropsNonUuidIdentifier();
            testAddChildrenConcurrentModificationDoesNotThrow();
            testAddChildrenCaseInsensitiveDedupe();
            testAddChildSelfEdgeSkipped();
            testAddChildControlCharacterIdSendsNothing();
            testAddChildHttpErrorLogsOneLine();
            testAddChildUnexpectedExceptionKeepsStackTrace();
            testFindSingletonHttpErrorLogsOneLine();
            testFindSingletonUnexpectedExceptionKeepsStackTrace();
            testAddChildInterruptedRestoresFlag();
            testFindSingletonInterruptedRestoresFlag();
            testAddChildInterruptedMidRequestRestoresFlag();
            testFindSingletonInterruptedMidRequestRestoresFlag();
        }
        report();
    }

    // -----------------------------------------------------------------------
    // Pure helpers
    // -----------------------------------------------------------------------

    private static void testPathAndBody() {
        assertEquals("children path",
                "/api/resources/" + PARENT + "/relationships/children",
                SuiteApiStitchClient.childrenRelationshipPath(PARENT));
        assertEquals("uuid-values body, one id",
                "{\"uuids\":[\"" + CHILD_A + "\"]}",
                SuiteApiStitchClient.buildUuidValuesJson(List.of(CHILD_A)));
        assertEquals("uuid-values body, two ids in order",
                "{\"uuids\":[\"" + CHILD_A + "\",\"" + CHILD_B + "\"]}",
                SuiteApiStitchClient.buildUuidValuesJson(List.of(CHILD_A, CHILD_B)));
    }

    private static void testIsUuid() {
        assertTrue("canonical uuid", SuiteApiStitchClient.isUuid(PARENT));
        assertTrue("uppercase uuid", SuiteApiStitchClient.isUuid(PARENT.toUpperCase()));
        assertTrue("uuid with surrounding space", SuiteApiStitchClient.isUuid(" " + PARENT + " "));
        assertFalse("null", SuiteApiStitchClient.isUuid(null));
        assertFalse("blank", SuiteApiStitchClient.isUuid("  "));
        assertFalse("path injection", SuiteApiStitchClient.isUuid(PARENT + "/../x"));
        assertFalse("not a uuid", SuiteApiStitchClient.isUuid("vm-123"));
    }

    private static void testParseResourceIds() {
        String one = resources(entry(WORLD_1, "MyKind", "MyWorld"));
        assertEquals("one match", "[" + WORLD_1 + "]",
                SuiteApiStitchClient.parseResourceIds(one, "MyKind", "MyWorld").toString());

        String mixed = resources(
                entry(WORLD_1, "MyKind", "MyWorld"),
                entry(WORLD_2, "MyKind", "OtherKind"),
                entry(OTHER_1, "VMWARE", "MyWorld"),
                "{\"identifier\":\"" + CHILD_A + "\"}");
        assertEquals("kind mismatch and missing resourceKey are filtered", "[" + WORLD_1 + "]",
                SuiteApiStitchClient.parseResourceIds(mixed, "MyKind", "MyWorld").toString());

        String two = resources(entry(WORLD_1, "MyKind", "MyWorld"),
                entry(WORLD_2, "MyKind", "MyWorld"));
        assertEquals("two matches both returned", "[" + WORLD_1 + ", " + WORLD_2 + "]",
                SuiteApiStitchClient.parseResourceIds(two, "MyKind", "MyWorld").toString());

        String nonUuid = resources(entry("not a uuid", "MyKind", "MyWorld"),
                entry("", "MyKind", "MyWorld"));
        assertEquals("non-UUID and empty identifiers are dropped", "[]",
                SuiteApiStitchClient.parseResourceIds(nonUuid, "MyKind", "MyWorld").toString());

        String caseDup = resources(entry(WORLD_1.toUpperCase(), "MyKind", "MyWorld"),
                entry(WORLD_1, "MyKind", "MyWorld"));
        assertEquals("identifier lowercased and deduped across case", "[" + WORLD_1 + "]",
                SuiteApiStitchClient.parseResourceIds(caseDup, "MyKind", "MyWorld").toString());

        assertEquals("kind comparison is case-sensitive", "[]",
                SuiteApiStitchClient.parseResourceIds(one, "mykind", "MyWorld").toString());

        assertEquals("empty resourceList", "[]",
                SuiteApiStitchClient.parseResourceIds(resources(), "MyKind", "MyWorld").toString());
        assertEquals("no resourceList key", "[]",
                SuiteApiStitchClient.parseResourceIds("{}", "MyKind", "MyWorld").toString());
    }

    /** The replace (PUT) relationship verb must never be on the public API. */
    private static void testNoReplaceVerbOnPublicSurface() {
        for (Class<?> c : Arrays.asList(SuiteApiStitchClient.class, SuiteApiStitcher.class)) {
            boolean found = false;
            for (Method m : c.getDeclaredMethods()) {
                if (!Modifier.isPublic(m.getModifiers())) continue;
                String n = m.getName().toLowerCase();
                if (n.startsWith("set") || n.startsWith("replace") || n.contains("put")) {
                    found = true;
                }
            }
            assertFalse(c.getSimpleName() + " exposes no set/replace/put method", found);
        }
    }

    private static void testNormalizeUuid() {
        assertEquals("normalize trims and lowercases", PARENT,
                SuiteApiStitchClient.normalizeUuid("  " + PARENT.toUpperCase() + "\t"));
    }

    private static void testLoggable() {
        assertEquals("null renders as null", "null", SuiteApiStitchClient.loggable(null));
        assertEquals("plain value unchanged", "vm-123", SuiteApiStitchClient.loggable("vm-123"));
        String forged = "x\r\n2026-10-02 WARN forged line\u0000";
        String safe = SuiteApiStitchClient.loggable(forged);
        assertFalse("CR stripped", safe.indexOf('\r') >= 0);
        assertFalse("LF stripped", safe.indexOf('\n') >= 0);
        assertFalse("NUL stripped", safe.indexOf('\u0000') >= 0);
        assertEquals("control chars replaced, rest kept",
                "x??2026-10-02 WARN forged line?", safe);
        StringBuilder longId = new StringBuilder();
        for (int i = 0; i < 500; i++) longId.append('a');
        String cut = SuiteApiStitchClient.loggable(longId.toString());
        assertEquals("long value truncated with marker",
                String.valueOf(SuiteApiStitchClient.LOGGABLE_MAX + 3),
                String.valueOf(cut.length()));
        assertTrue("truncation marker present", cut.endsWith("..."));
        String exact = longId.substring(0, SuiteApiStitchClient.LOGGABLE_MAX);
        assertEquals("value at the limit is not marked", exact,
                SuiteApiStitchClient.loggable(exact));

        // Unicode line/paragraph separators and format (bidi, zero-width)
        // characters are replaced like ISO controls.
        assertEquals("U+2028 / U+2029 / U+202E / U+200B replaced",
                "a?b?c?d?e",
                SuiteApiStitchClient.loggable("a\u2028b\u2029c\u202Ed\u200Be"));
        assertEquals("U+0085 (ISO control) still replaced", "a?b",
                SuiteApiStitchClient.loggable("a\u0085b"));

        // Truncation never ends on a lone high surrogate.
        StringBuilder pre = new StringBuilder();
        for (int i = 0; i < SuiteApiStitchClient.LOGGABLE_MAX - 1; i++) pre.append('a');
        String split = pre + "\uD83D\uDE00tail";
        String splitCut = SuiteApiStitchClient.loggable(split);
        assertEquals("high surrogate at the cut is dropped", pre + "...", splitCut);
        boolean anySurrogate = false;
        for (int i = 0; i < splitCut.length(); i++) {
            anySurrogate |= Character.isSurrogate(splitCut.charAt(i));
        }
        assertFalse("no lone surrogate in truncated output", anySurrogate);
        StringBuilder pre2 = new StringBuilder();
        for (int i = 0; i < SuiteApiStitchClient.LOGGABLE_MAX - 2; i++) pre2.append('a');
        String whole = pre2 + "\uD83D\uDE00tail";
        assertEquals("a pair that fits before the cut is kept",
                pre2 + "\uD83D\uDE00...", SuiteApiStitchClient.loggable(whole));
    }

    // -----------------------------------------------------------------------
    // Transport: addChild / addChildren
    // -----------------------------------------------------------------------

    private static void testAddChildIsAdditivePost() throws Exception {
        Harness h = new Harness(okTokenThen(204, ""));
        boolean ok = h.client.addChild(PARENT, CHILD_A);

        assertTrue("addChild returns true on 204", ok);
        assertEquals("two requests (token acquire + add)", "2",
                String.valueOf(h.requests.size()));
        Req add = h.requests.get(1);
        assertEquals("verb is POST", "POST", add.method);
        assertEquals("request URL", CHILDREN_URL, add.url);
        assertEquals("request body", "{\"uuids\":[\"" + CHILD_A + "\"]}", add.body);
        assertEquals("OpsToken header", "OpsToken tok-1", add.headers.get("Authorization"));
        assertEquals("JSON content type", "application/json", add.headers.get("Content-Type"));
        assertFalse("no PUT issued", h.anyMethod("PUT"));
        assertEquals("no WARN on success", "0", String.valueOf(h.warns.get()));
    }

    private static void testAddChildrenDedupesAndSkipsInvalid() throws Exception {
        Harness h = new Harness(okTokenThen(204, ""));
        boolean ok = h.client.addChildren(PARENT,
                Arrays.asList(CHILD_A, "not-a-uuid", null, CHILD_B, CHILD_A));
        assertTrue("addChildren returns true", ok);
        assertEquals("one add request for the collection", "1",
                String.valueOf(h.countUrl(CHILDREN_URL)));
        assertEquals("deduped, invalid skipped, order kept",
                "{\"uuids\":[\"" + CHILD_A + "\",\"" + CHILD_B + "\"]}",
                h.lastTo(CHILDREN_URL).body);
        assertTrue("invalid child ids are WARNed", h.warns.get() >= 2);
    }

    private static void testAddChildrenNothingValidSendsNothing() throws Exception {
        Harness h = new Harness(okTokenThen(204, ""));
        assertFalse("empty collection returns false",
                h.client.addChildren(PARENT, new ArrayList<>()));
        assertFalse("null collection returns false", h.client.addChildren(PARENT, null));
        assertFalse("only invalid ids returns false",
                h.client.addChildren(PARENT, List.of("x")));
        assertFalse("non-uuid parent returns false", h.client.addChild("bad/parent", CHILD_A));
        assertFalse("null parent returns false", h.client.addChild(null, CHILD_A));
        assertFalse("null child returns false", h.client.addChild(PARENT, null));
        assertEquals("no HTTP request at all", "0", String.valueOf(h.requests.size()));
    }

    private static void testAddChildServerErrorDoesNotThrow() throws Exception {
        Harness h = new Harness(okTokenThen(500, "{\"message\":\"boom\"}"));
        boolean ok;
        try {
            ok = h.client.addChild(PARENT, CHILD_A);
        } catch (Throwable t) {
            fail("HTTP 500 must not throw (" + t + ")");
            return;
        }
        assertFalse("HTTP 500 returns false", ok);
        assertTrue("HTTP 500 is WARNed", h.warns.get() >= 1);

        Harness h404 = new Harness(okTokenThen(404, ""));
        assertFalse("HTTP 404 (all ids invalid) returns false, no throw",
                h404.client.addChild(PARENT, CHILD_A));
    }

    private static void testAddChildTransportExceptionDoesNotThrow() throws Exception {
        Harness h = new Harness((m, u, b) -> {
            throw new IOException("connection refused");
        });
        boolean ok;
        try {
            ok = h.client.addChild(PARENT, CHILD_A);
        } catch (Throwable t) {
            fail("transport IOException must not throw (" + t + ")");
            return;
        }
        assertFalse("transport failure returns false", ok);
        assertTrue("transport failure is WARNed", h.warns.get() >= 1);

        Harness rt = new Harness((m, u, b) -> {
            throw new IllegalStateException("unexpected");
        });
        try {
            assertFalse("RuntimeException from transport returns false",
                    rt.client.addChild(PARENT, CHILD_A));
        } catch (Throwable t) {
            fail("RuntimeException from transport must not throw (" + t + ")");
        }
    }

    private static void testAddChildRetriesOnceOn401() throws Exception {
        AtomicInteger tokens = new AtomicInteger();
        AtomicInteger adds = new AtomicInteger();
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) {
                return new Resp(200, "{\"token\":\"tok-" + tokens.incrementAndGet() + "\"}");
            }
            return adds.incrementAndGet() == 1 ? new Resp(401, "") : new Resp(204, "");
        });
        assertTrue("401 then 204 returns true", h.client.addChild(PARENT, CHILD_A));
        assertEquals("token acquired twice", "2", String.valueOf(tokens.get()));
        assertEquals("add attempted twice", "2", String.valueOf(h.countUrl(CHILDREN_URL)));
        assertEquals("retry carries the fresh token", "OpsToken tok-2",
                h.lastTo(CHILDREN_URL).headers.get("Authorization"));
    }

    private static void testAddChildPerpetual401StopsAfterOneRetry() throws Exception {
        Harness h = new Harness((m, u, b) -> u.equals(TOKEN_URL)
                ? new Resp(200, "{\"token\":\"t\"}") : new Resp(401, ""));
        boolean ok;
        try {
            ok = h.client.addChild(PARENT, CHILD_A);
        } catch (Throwable t) {
            fail("perpetual 401 must not throw (" + t + ")");
            return;
        }
        assertFalse("perpetual 401 returns false", ok);
        assertEquals("exactly two add attempts", "2", String.valueOf(h.countUrl(CHILDREN_URL)));
    }

    private static void testFacadeDelegatesAddChild() throws Exception {
        Harness h = new Harness(okTokenThen(204, ""));
        java.lang.reflect.Constructor<SuiteApiStitcher> ctor =
                SuiteApiStitcher.class.getDeclaredConstructor(SuiteApiStitchClient.class);
        ctor.setAccessible(true);
        SuiteApiStitcher stitcher = ctor.newInstance(h.client);
        assertTrue("facade addChild returns true", stitcher.addChild(PARENT, CHILD_A));
        Req add = h.lastTo(CHILDREN_URL);
        assertTrue("facade issued the POST", add != null && "POST".equals(add.method));
        assertTrue("facade addChildren returns true",
                stitcher.addChildren(PARENT, List.of(CHILD_B)));
    }

    // -----------------------------------------------------------------------
    // Transport: findSingletonResourceId
    // -----------------------------------------------------------------------

    private static void testFindSingletonOneMatch() throws Exception {
        Harness h = new Harness(okTokenThen(200,
                resources(entry(WORLD_1, "MyKind", "My World"))));
        String id = h.client.findSingletonResourceId("MyKind", "My World");
        assertEquals("single match returns its id", WORLD_1, id);
        Req q = h.requests.get(h.requests.size() - 1);
        assertEquals("lookup verb is GET", "GET", q.method);
        assertEquals("lookup URL, kinds encoded (space as %20)",
                BASE + "/api/resources?adapterKind=MyKind&resourceKind=My%20World", q.url);
    }

    private static void testFindSingletonZeroMatches() throws Exception {
        Harness h = new Harness(okTokenThen(200, resources()));
        assertEquals("zero matches returns null", null,
                h.client.findSingletonResourceId("MyKind", "MyWorld"));
        assertTrue("zero matches is WARNed", h.warns.get() >= 1);
    }

    private static void testFindSingletonAmbiguousReturnsNothing() throws Exception {
        Harness h = new Harness(okTokenThen(200, resources(
                entry(WORLD_1, "MyKind", "MyWorld"),
                entry(WORLD_2, "MyKind", "MyWorld"))));
        assertEquals("two matches returns null (never guesses)", null,
                h.client.findSingletonResourceId("MyKind", "MyWorld"));
        assertTrue("ambiguous lookup is WARNed", h.warns.get() >= 1);

        Harness filtered = new Harness(okTokenThen(200, resources(
                entry(WORLD_1, "MyKind", "MyWorld"),
                entry(OTHER_1, "OtherKind", "MyWorld"))));
        assertEquals("foreign-kind entry does not make it ambiguous", WORLD_1,
                filtered.client.findSingletonResourceId("MyKind", "MyWorld"));
    }

    private static void testFindSingletonFailureDoesNotThrow() throws Exception {
        Harness h = new Harness(okTokenThen(500, ""));
        try {
            assertEquals("HTTP 500 returns null", null,
                    h.client.findSingletonResourceId("MyKind", "MyWorld"));
        } catch (Throwable t) {
            fail("lookup HTTP 500 must not throw (" + t + ")");
        }
        Harness blank = new Harness(okTokenThen(200, resources()));
        assertEquals("blank kind returns null", null,
                blank.client.findSingletonResourceId("MyKind", " "));
        assertEquals("blank kind sends no request", "0", String.valueOf(blank.requests.size()));
    }

    private static void testFindSingletonMalformedJsonDoesNotThrow() throws Exception {
        Harness h = new Harness(okTokenThen(200, "{not json"));
        try {
            assertEquals("malformed JSON returns null", null,
                    h.client.findSingletonResourceId("MyKind", "MyWorld"));
        } catch (Throwable t) {
            fail("malformed JSON must not throw (" + t + ")");
        }
    }

    /** W1: one visible match on a page that reports more results is not trusted. */
    private static void testFindSingletonPartialPageReturnsNothing() throws Exception {
        Harness h = new Harness(okTokenThen(200, resourcesWithTotal(1001,
                entry(WORLD_1, "MyKind", "MyWorld"))));
        assertEquals("partial page (1 of 1001) returns null", null,
                h.client.findSingletonResourceId("MyKind", "MyWorld"));
        assertTrue("partial page is WARNed", h.warns.get() >= 1);

        Harness exact = new Harness(okTokenThen(200, resourcesWithTotal(2,
                entry(WORLD_1, "MyKind", "MyWorld"),
                entry(OTHER_1, "OtherKind", "MyWorld"))));
        assertEquals("totalCount equal to page size, one exact match", WORLD_1,
                exact.client.findSingletonResourceId("MyKind", "MyWorld"));

        Harness noPageInfo = new Harness(okTokenThen(200, "{\"resourceList\":["
                + entry(WORLD_1, "MyKind", "MyWorld") + "]}"));
        assertEquals("no pageInfo, one match is returned", WORLD_1,
                noPageInfo.client.findSingletonResourceId("MyKind", "MyWorld"));
    }

    /** N3: kinds are trimmed once and the trimmed value is used to query and compare. */
    private static void testFindSingletonTrimsKinds() throws Exception {
        Harness h = new Harness(okTokenThen(200,
                resources(entry(WORLD_1, "MyKind", "MyWorld"))));
        assertEquals("padded kinds still match", WORLD_1,
                h.client.findSingletonResourceId(" MyKind ", "\tMyWorld "));
        assertEquals("query carries the trimmed kinds",
                BASE + "/api/resources?adapterKind=MyKind&resourceKind=MyWorld",
                h.requests.get(h.requests.size() - 1).url);

        Harness lower = new Harness(okTokenThen(200,
                resources(entry(WORLD_1, "MyKind", "MyWorld"))));
        assertEquals("case mismatch returns null", null,
                lower.client.findSingletonResourceId("mykind", "MyWorld"));
        assertTrue("case mismatch is WARNed", lower.warns.get() >= 1);
    }

    /** N3: a returned identifier that is not a UUID never comes back to the caller. */
    private static void testFindSingletonDropsNonUuidIdentifier() throws Exception {
        Harness h = new Harness(okTokenThen(200,
                resources(entry("not a uuid", "MyKind", "MyWorld"))));
        assertEquals("non-UUID identifier returns null", null,
                h.client.findSingletonResourceId("MyKind", "MyWorld"));
        assertTrue("non-UUID identifier is WARNed (as no match)", h.warns.get() >= 1);

        Harness upper = new Harness(okTokenThen(200,
                resources(entry(WORLD_1.toUpperCase(), "MyKind", "MyWorld"))));
        assertEquals("uppercase identifier returned lowercase", WORLD_1,
                upper.client.findSingletonResourceId("MyKind", "MyWorld"));
    }

    /** N1: a collection that throws while being iterated must not throw into collect. */
    private static void testAddChildrenConcurrentModificationDoesNotThrow() throws Exception {
        Harness h = new Harness(okTokenThen(204, ""));
        java.util.Collection<String> hostile = new java.util.AbstractCollection<String>() {
            @Override public java.util.Iterator<String> iterator() {
                return new java.util.Iterator<String>() {
                    int n = 0;
                    @Override public boolean hasNext() { return true; }
                    @Override public String next() {
                        if (n++ == 0) return CHILD_A;
                        throw new java.util.ConcurrentModificationException();
                    }
                };
            }
            @Override public int size() { return 2; }
        };
        boolean ok;
        try {
            ok = h.client.addChildren(PARENT, hostile);
        } catch (Throwable t) {
            fail("ConcurrentModificationException must not throw (" + t + ")");
            return;
        }
        assertFalse("concurrent modification returns false", ok);
        assertTrue("concurrent modification is WARNed", h.warns.get() >= 1);
        assertEquals("nothing sent on concurrent modification", "0",
                String.valueOf(h.requests.size()));
    }

    /** N2: ids are lowercased before dedupe, and the path uses the lowercase parent. */
    private static void testAddChildrenCaseInsensitiveDedupe() throws Exception {
        Harness h = new Harness(okTokenThen(204, ""));
        assertTrue("mixed-case duplicates accepted",
                h.client.addChildren(PARENT.toUpperCase(),
                        Arrays.asList(CHILD_A, CHILD_A.toUpperCase(), " " + CHILD_B + " ")));
        Req add = h.lastTo(CHILDREN_URL);
        assertTrue("path uses the lowercase parent", add != null);
        assertEquals("one id per child after case-folding",
                "{\"uuids\":[\"" + CHILD_A + "\",\"" + CHILD_B + "\"]}",
                add == null ? null : add.body);
    }

    /** N2: a child equal to its parent is skipped with a WARN. */
    private static void testAddChildSelfEdgeSkipped() throws Exception {
        Harness h = new Harness(okTokenThen(204, ""));
        assertFalse("addChild(P, P) returns false", h.client.addChild(PARENT, PARENT));
        assertFalse("addChild(P, upper P) returns false",
                h.client.addChild(PARENT, PARENT.toUpperCase()));
        assertEquals("self-edge sends nothing", "0", String.valueOf(h.requests.size()));
        assertTrue("self-edge is WARNed", h.warns.get() >= 2);

        Harness mixed = new Harness(okTokenThen(204, ""));
        assertTrue("self-edge dropped, other child still sent",
                mixed.client.addChildren(PARENT, Arrays.asList(PARENT, CHILD_A)));
        assertEquals("body carries only the real child",
                "{\"uuids\":[\"" + CHILD_A + "\"]}", mixed.lastTo(CHILDREN_URL).body);
    }

    /** N4: a CR/LF-bearing id is rejected (and logged sanitized), nothing is sent. */
    private static void testAddChildControlCharacterIdSendsNothing() throws Exception {
        Harness h = new Harness(okTokenThen(204, ""));
        assertFalse("CR/LF child id returns false",
                h.client.addChild(PARENT, CHILD_A + "\r\nWARN forged"));
        assertFalse("CR/LF parent id returns false",
                h.client.addChild(PARENT + "\nx", CHILD_A));
        assertEquals("nothing sent", "0", String.valueOf(h.requests.size()));
        assertTrue("both rejections WARNed", h.warns.get() >= 2);
    }

    /**
     * Expected failures (IOException family, interrupt) are logged without a
     * stack trace; runtime exceptions are not expected.
     */
    private static void testFailureClassification() {
        assertTrue("HTTP status IOException is expected",
                SuiteApiStitchClient.isExpectedFailure(new IOException("HTTP 403")));
        assertTrue("timeout is expected",
                SuiteApiStitchClient.isExpectedFailure(
                        new java.net.SocketTimeoutException("Read timed out")));
        assertTrue("connection refused is expected",
                SuiteApiStitchClient.isExpectedFailure(
                        new java.net.ConnectException("Connection refused")));
        assertTrue("unknown host is expected",
                SuiteApiStitchClient.isExpectedFailure(
                        new java.net.UnknownHostException("nohost")));
        assertTrue("interrupt is expected",
                SuiteApiStitchClient.isExpectedFailure(new InterruptedException("stop")));
        assertFalse("IllegalStateException is unexpected",
                SuiteApiStitchClient.isExpectedFailure(new IllegalStateException("bug")));
        assertFalse("NullPointerException is unexpected",
                SuiteApiStitchClient.isExpectedFailure(new NullPointerException()));
        assertEquals("summary carries class and message",
                "IOException: Suite API POST x HTTP 403",
                SuiteApiStitchClient.failureSummary(
                        new IOException("Suite API POST x HTTP 403")));
        assertEquals("summary with null message",
                "NullPointerException: (no message)",
                SuiteApiStitchClient.failureSummary(new NullPointerException()));
        assertEquals("summary replaces CR/LF from a parse error message",
                "NumberFormatException: For input string: \"??WARN forged\" under radix 16",
                SuiteApiStitchClient.failureSummary(new NumberFormatException(
                        "For input string: \"\r\nWARN forged\" under radix 16")));
        StringBuilder digits = new StringBuilder("For input string: \"");
        for (int i = 0; i < 100_000; i++) digits.append('9');
        String longSummary = SuiteApiStitchClient.failureSummary(
                new NumberFormatException(digits.toString()));
        String prefix = "NumberFormatException: ";
        int max = SuiteApiStitchClient.FAILURE_MESSAGE_MAX;
        int tailKeep = SuiteApiStitchClient.FAILURE_TAIL_KEEP;
        int headKeep = max - 3 - tailKeep;
        assertEquals("over-long message is capped at FAILURE_MESSAGE_MAX",
                String.valueOf(prefix.length() + max),
                String.valueOf(longSummary.length()));
        assertTrue("over-long message carries the truncation marker after the head",
                longSummary.startsWith("...", prefix.length() + headKeep));

        // N13: the exact cap boundary. FAILURE_MESSAGE_MAX characters pass
        // through untouched; one more is cut to FAILURE_MESSAGE_MAX.
        StringBuilder atCap = new StringBuilder();
        for (int i = 0; i < max; i++) atCap.append((char) ('a' + i % 26));
        assertEquals("message of exactly FAILURE_MESSAGE_MAX is unchanged",
                "IOException: " + atCap,
                SuiteApiStitchClient.failureSummary(new IOException(atCap.toString())));
        String overCap = SuiteApiStitchClient.failureSummary(
                new IOException(atCap + "z")).substring("IOException: ".length());
        assertEquals("message of FAILURE_MESSAGE_MAX + 1 is cut to FAILURE_MESSAGE_MAX",
                String.valueOf(max), String.valueOf(overCap.length()));
        assertTrue("message of FAILURE_MESSAGE_MAX + 1 has the marker after the head",
                overCap.startsWith("...", headKeep));

        // N10: the transport puts the HTTP status last; a long host must not cut it.
        StringBuilder host = new StringBuilder();
        while (host.length() < 86) host.append("ops-node.");
        host.setLength(86);
        host.append(".com");
        assertEquals("long-host fixture is 90 characters", "90", String.valueOf(host.length()));
        String longHostMsg = "Suite API POST https://" + host + "/suite-api/api/resources/"
                + PARENT + "/relationships/children HTTP 403";
        String hostSummary = SuiteApiStitchClient.failureSummary(new IOException(longHostMsg));
        assertTrue("90-character host message is over the cap",
                longHostMsg.length() > max);
        assertTrue("90-character host keeps HTTP 403 in the summary",
                hostSummary.endsWith("HTTP 403"));
        assertTrue("90-character host keeps the message head",
                hostSummary.startsWith("IOException: Suite API POST https://ops-node."));
        assertEquals("90-character host summary is bounded",
                String.valueOf("IOException: ".length() + max),
                String.valueOf(hostSummary.length()));

        // N12: one ASCII character first, so the head cut lands after a high
        // surrogate and the tail cut on a low surrogate; both get dropped.
        StringBuilder pairs = new StringBuilder("a");
        for (int i = 0; i < max; i++) {
            pairs.append("\uD83D\uDE00");
        }
        String pairSummary = SuiteApiStitchClient.failureSummary(
                new IOException(pairs.toString()));
        String pairMsg = pairSummary.substring("IOException: ".length());
        int marker = pairMsg.indexOf("...");
        assertEquals("surrogate head cut drops the trailing high surrogate",
                String.valueOf(headKeep - 1), String.valueOf(marker));
        assertEquals("surrogate tail cut drops the leading low surrogate",
                String.valueOf(tailKeep - 1),
                String.valueOf(pairMsg.length() - marker - 3));
        assertEquals("surrogate-split message is FAILURE_MESSAGE_MAX - 2",
                String.valueOf(max - 2), String.valueOf(pairMsg.length()));
        assertFalse("surrogate-split message has no lone surrogate", hasLoneSurrogate(pairMsg));
    }

    /** True if the string holds a surrogate that is not half of a valid pair. */
    static boolean hasLoneSurrogate(String s) {
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (Character.isHighSurrogate(c)) {
                if (i + 1 >= s.length() || !Character.isLowSurrogate(s.charAt(i + 1))) return true;
                i++;
            } else if (Character.isLowSurrogate(c)) {
                return true;
            }
        }
        return false;
    }

    /**
     * HTTP error (403, principal lacks permission) on addChildren: false, no
     * throw, exactly one WARN, and the expected-failure branch is taken (it
     * is the only branch that checks the DEBUG level before logging the
     * trace).
     */
    private static void testAddChildHttpErrorLogsOneLine() throws Exception {
        Harness h = new Harness(okTokenThen(403, ""));
        boolean ok;
        try {
            ok = h.client.addChild(PARENT, CHILD_A);
        } catch (Throwable t) {
            fail("addChild HTTP 403 must not throw (" + t + ")");
            return;
        }
        assertFalse("addChild HTTP 403 returns false", ok);
        assertEquals("addChild HTTP 403 is one WARN", "1", String.valueOf(h.warns.get()));
        assertEquals("addChild HTTP 403 takes the expected-failure branch",
                "1", String.valueOf(h.debugChecks.get()));
    }

    /** Unexpected RuntimeException on addChildren: false, no throw, stack-trace branch. */
    private static void testAddChildUnexpectedExceptionKeepsStackTrace() throws Exception {
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            throw new IllegalStateException("unexpected");
        });
        boolean ok;
        try {
            ok = h.client.addChild(PARENT, CHILD_A);
        } catch (Throwable t) {
            fail("addChild RuntimeException must not throw (" + t + ")");
            return;
        }
        assertFalse("addChild RuntimeException returns false", ok);
        assertEquals("addChild RuntimeException is one WARN", "1", String.valueOf(h.warns.get()));
        assertEquals("addChild RuntimeException takes the stack-trace branch",
                "0", String.valueOf(h.debugChecks.get()));
    }

    /** HTTP error on the singleton lookup: null, no throw, one-line branch. */
    private static void testFindSingletonHttpErrorLogsOneLine() throws Exception {
        Harness h = new Harness(okTokenThen(503, ""));
        String id;
        try {
            id = h.client.findSingletonResourceId("MyKind", "MyWorld");
        } catch (Throwable t) {
            fail("lookup HTTP 503 must not throw (" + t + ")");
            return;
        }
        assertEquals("lookup HTTP 503 returns null", null, id);
        assertEquals("lookup HTTP 503 is one WARN", "1", String.valueOf(h.warns.get()));
        assertEquals("lookup HTTP 503 takes the expected-failure branch",
                "1", String.valueOf(h.debugChecks.get()));
    }

    /** Unexpected RuntimeException on the singleton lookup: null, no throw, stack-trace branch. */
    private static void testFindSingletonUnexpectedExceptionKeepsStackTrace() throws Exception {
        Harness h = new Harness((m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            throw new IllegalStateException("unexpected");
        });
        String id;
        try {
            id = h.client.findSingletonResourceId("MyKind", "MyWorld");
        } catch (Throwable t) {
            fail("lookup RuntimeException must not throw (" + t + ")");
            return;
        }
        assertEquals("lookup RuntimeException returns null", null, id);
        assertEquals("lookup RuntimeException is one WARN", "1", String.valueOf(h.warns.get()));
        assertEquals("lookup RuntimeException takes the stack-trace branch",
                "0", String.valueOf(h.debugChecks.get()));
    }

    /**
     * Interrupt before addChild (collector shutdown): false, no throw, no
     * request sent, one WARN on the one-line branch, and the interrupt flag
     * still set on return. Thread.interrupted() reads and clears it so the
     * next test starts clean.
     */
    private static void testAddChildInterruptedRestoresFlag() throws Exception {
        Harness h = new Harness(okTokenThen(200, ""));
        boolean ok;
        boolean flag;
        Thread.currentThread().interrupt();
        try {
            ok = h.client.addChild(PARENT, CHILD_A);
        } catch (Throwable t) {
            fail("addChild on an interrupted thread must not throw (" + t + ")");
            return;
        } finally {
            flag = Thread.interrupted();
        }
        assertFalse("interrupted addChild returns false", ok);
        assertEquals("interrupted addChild sends no request",
                "0", String.valueOf(h.requests.size()));
        assertEquals("interrupted addChild is one WARN", "1", String.valueOf(h.warns.get()));
        assertEquals("interrupted addChild takes the one-line branch",
                "1", String.valueOf(h.debugChecks.get()));
        assertTrue("interrupted addChild leaves the interrupt flag set", flag);
    }

    /** Interrupt before the singleton lookup: same contract, returning null. */
    private static void testFindSingletonInterruptedRestoresFlag() throws Exception {
        Harness h = new Harness(okTokenThen(200, resources(entry(WORLD_1, "MyKind", "MyWorld"))));
        String id;
        boolean flag;
        Thread.currentThread().interrupt();
        try {
            id = h.client.findSingletonResourceId("MyKind", "MyWorld");
        } catch (Throwable t) {
            fail("lookup on an interrupted thread must not throw (" + t + ")");
            return;
        } finally {
            flag = Thread.interrupted();
        }
        assertEquals("interrupted lookup returns null", null, id);
        assertEquals("interrupted lookup sends no request",
                "0", String.valueOf(h.requests.size()));
        assertEquals("interrupted lookup is one WARN", "1", String.valueOf(h.warns.get()));
        assertEquals("interrupted lookup takes the one-line branch",
                "1", String.valueOf(h.debugChecks.get()));
        assertTrue("interrupted lookup leaves the interrupt flag set", flag);
    }

    /**
     * Interrupt arriving during the addChildren POST (the transport throws
     * InterruptedException with the flag already cleared, as blocking JDK
     * calls do): false, no throw, one WARN on the one-line branch, and the
     * catch block's interrupt() restores the flag. Fails if that restore is
     * removed, which the pre-check test above cannot detect.
     */
    private static void testAddChildInterruptedMidRequestRestoresFlag() throws Exception {
        Harness h = new Harness(interruptAfterToken());
        boolean ok;
        boolean flag;
        Thread.interrupted();
        try {
            ok = h.client.addChild(PARENT, CHILD_A);
        } catch (Throwable t) {
            fail("addChild interrupted mid-request must not throw (" + t + ")");
            return;
        } finally {
            flag = Thread.interrupted();
        }
        assertFalse("addChild interrupted mid-request returns false", ok);
        assertEquals("addChild interrupted mid-request sent token + POST",
                "2", String.valueOf(h.requests.size()));
        assertEquals("addChild interrupted mid-request is one WARN",
                "1", String.valueOf(h.warns.get()));
        assertEquals("addChild interrupted mid-request takes the one-line branch",
                "1", String.valueOf(h.debugChecks.get()));
        assertTrue("addChild interrupted mid-request restores the interrupt flag", flag);
    }

    /** Interrupt during the singleton lookup GET: same contract, returning null. */
    private static void testFindSingletonInterruptedMidRequestRestoresFlag() throws Exception {
        Harness h = new Harness(interruptAfterToken());
        String id;
        boolean flag;
        Thread.interrupted();
        try {
            id = h.client.findSingletonResourceId("MyKind", "MyWorld");
        } catch (Throwable t) {
            fail("lookup interrupted mid-request must not throw (" + t + ")");
            return;
        } finally {
            flag = Thread.interrupted();
        }
        assertEquals("lookup interrupted mid-request returns null", null, id);
        assertEquals("lookup interrupted mid-request sent token + GET",
                "2", String.valueOf(h.requests.size()));
        assertEquals("lookup interrupted mid-request is one WARN",
                "1", String.valueOf(h.warns.get()));
        assertEquals("lookup interrupted mid-request takes the one-line branch",
                "1", String.valueOf(h.debugChecks.get()));
        assertTrue("lookup interrupted mid-request restores the interrupt flag", flag);
    }

    /**
     * Token acquire answers 200; every other request throws
     * InterruptedException (flag clear) from inside the transport.
     */
    static Responder interruptAfterToken() {
        return (m, u, b) -> {
            if (u.equals(TOKEN_URL)) return new Resp(200, "{\"token\":\"tok-1\"}");
            throw sneakyThrow(new InterruptedException("interrupted mid-request"));
        };
    }

    /**
     * Throw a checked exception through a signature that does not declare it
     * ({@link Responder#respond} declares only IOException).
     */
    @SuppressWarnings("unchecked")
    static <X extends Throwable> RuntimeException sneakyThrow(Throwable t) throws X {
        throw (X) t;
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

    /** Records the request; the response is decided when the code is read. */
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
            return new ByteArrayInputStream(resp().body.getBytes(StandardCharsets.UTF_8));
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

    /** One client wired to a FakeAdapter, plus the requests and WARN count it saw. */
    static final class Harness {
        final List<Req> requests = new ArrayList<>();
        final AtomicInteger warns = new AtomicInteger();
        final AtomicInteger debugChecks = new AtomicInteger();
        final SuiteApiStitchClient client;

        Harness(Responder responder) throws Exception {
            FakeAdapter a = allocate(FakeAdapter.class);
            a.requests = requests;
            a.responder = responder;
            client = SuiteApiStitchClient.builder()
                    .adapter(a)
                    .explicitCredentials("localhost", "svc-user", "svc-pass")
                    .logger(recordingLogger(warns, debugChecks))
                    .build();
        }

        boolean anyMethod(String m) {
            for (Req r : requests) if (m.equals(r.method)) return true;
            return false;
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

    // -----------------------------------------------------------------------
    // Logger and allocation plumbing
    // -----------------------------------------------------------------------

    static boolean log4jApiPresent() {
        try {
            Class.forName("org.apache.logging.log4j.Logger");
            return true;
        } catch (ClassNotFoundException | LinkageError e) {
            return false;
        }
    }

    /**
     * SDK Logger around a log4j-api proxy: every isXxxEnabled answers false
     * (so no log4j-core is touched) and isWarnEnabled calls are counted.
     * Message content cannot be captured: the SDK Logger only reaches its
     * log4j-core-backed forcedLog when the level check passes. So the
     * stack-trace decision is observed through the DEBUG level check
     * ({@code isEnabled(Level.DEBUG)}, which the SDK's
     * {@code isDebugEnabled()} calls), made only on the expected-failure
     * branch.
     */
    static Logger recordingLogger(AtomicInteger warns, AtomicInteger debugChecks)
            throws Exception {
        Class<?> log4j = Class.forName("org.apache.logging.log4j.Logger");
        Object proxy = Proxy.newProxyInstance(log4j.getClassLoader(), new Class<?>[] {log4j},
                (p, m, a) -> {
                    String n = m.getName();
                    if (n.equals("isWarnEnabled")) warns.incrementAndGet();
                    if (n.equals("isEnabled") && a != null && a.length == 1
                            && "DEBUG".equals(String.valueOf(a[0]))) {
                        debugChecks.incrementAndGet();
                    }
                    if (m.getReturnType() == boolean.class) return false;
                    if (n.equals("getName")) return "test";
                    return null;
                });
        java.lang.reflect.Constructor<Logger> c = Logger.class.getDeclaredConstructor(log4j);
        c.setAccessible(true);
        return c.newInstance(proxy);
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
    // JSON fixtures
    // -----------------------------------------------------------------------

    static String entry(String id, String adapterKind, String resourceKind) {
        return "{\"identifier\":\"" + id + "\",\"resourceKey\":{\"name\":\"n\","
                + "\"adapterKindKey\":\"" + adapterKind + "\","
                + "\"resourceKindKey\":\"" + resourceKind + "\"}}";
    }

    static String resources(String... entries) {
        return resourcesWithTotal(entries.length, entries);
    }

    /** A resource page whose pageInfo.totalCount is set explicitly. */
    static String resourcesWithTotal(int totalCount, String... entries) {
        return "{\"pageInfo\":{\"totalCount\":" + totalCount
                + ",\"page\":0,\"pageSize\":1000},\"resourceList\":["
                + String.join(",", entries) + "]}";
    }

    // -----------------------------------------------------------------------
    // Harness
    // -----------------------------------------------------------------------

    private static void assertTrue(String label, boolean cond) {
        if (cond) {
            System.out.println("  PASS: " + label);
            passed++;
        } else {
            fail(label);
        }
    }

    private static void assertFalse(String label, boolean cond) {
        assertTrue(label, !cond);
    }

    private static void assertEquals(String label, String expected, String actual) {
        if (expected == null ? actual == null : expected.equals(actual)) {
            System.out.println("  PASS: " + label);
            passed++;
        } else {
            fail(label + " expected=" + expected + " actual=" + actual);
        }
    }

    private static void fail(String label) {
        System.out.println("  FAIL: " + label);
        FAILURES.add(label);
    }

    private static void skip(String label) {
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
