package com.vcfcf.adapter;

import com.integrien.alive.common.adapter3.AdapterBase;
import com.integrien.alive.common.adapter3.MetricData;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.integrien.alive.common.util.CommonConstants.ResourceStatusEnum;
import com.vcfcf.adapter.http.ManagedHttpClient;
import com.vcfcf.adapter.spi.ResourceSink;
import com.vcfcf.adapter.spi.VcfCfCollector;
import com.vcfcf.adapter.spi.VcfCfTester;

import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Issue #223: a cycle in which nothing could be collected sets the adapter
 * instance status (the account row), not only the objects'.
 *
 * <p>No JUnit: call via {@code main()}. Drives the real
 * {@link VcfCfAdapter#onCollect} with a scripted collector; the test adapter
 * records {@code setResourceStatus} calls instead of reaching the platform.
 * Needs log4j at runtime for the adapter's logger ({@link LogCapture});
 * SKIPPED without it.
 */
public class AdapterInstanceStatusTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;
    private static int skipped = 0;

    public static void main(String[] args) throws Exception {
        testPureRules();
        testRedactCredentials();
        testFailureMessageIsRedacted();
        if (!LogCapture.available()) {
            skip("onCollect tests: log4j not on the runtime classpath"
                    + " (add a jar carrying it, e.g. adapter_runtime/lib/*)");
        } else {
            testEveryResourceFailsSetsInstanceError();
            testPartialFailureLeavesInstanceAlone();
            testAllDownSetsInstanceDown();
            testMixedDownAndErrorIsError();
            testNoDataMappingIsNotInstanceFailure();
            testDiscoveryFailureWithNothingToCollect();
            testDiscoveryFailureButResourcesCollect();
            testNothingToCollectNoFailure();
            testStopMidCycleSetsNothing();
            testAllSucceedSetsNothing();
            testWrappedInterruptOnLastResourceSetsNothing();
            testCycleStartOncePerCycleBeforeDiscovery();
            testNeedsRediscoveryExactlyOncePerCycle();
            testCycleStartFailureDoesNotStopCycle();
            testDefaultCycleStartIsNoOp();
            testCycleStartErrorDoesNotStopCycle();
            testCycleStartFatalEndsCycle();
        }
        report();
    }

    // -----------------------------------------------------------------------
    // Pure rules
    // -----------------------------------------------------------------------

    private static void testPureRules() {
        VcfCfAdapter.CycleOutcome o = new VcfCfAdapter.CycleOutcome();
        assertEquals("nothing attempted, no discovery failure: none", null,
                VcfCfAdapter.adapterInstanceStatus(o, null));
        o.attempted = 2;
        o.recordFailure(ResourceStatusEnum.RESOURCE_STATUS_ERROR, new IOException("a"));
        assertEquals("1 of 2 failed: none", null, VcfCfAdapter.adapterInstanceStatus(o, null));
        o.recordFailure(ResourceStatusEnum.RESOURCE_STATUS_ERROR, new IOException("b"));
        assertEquals("2 of 2 failed: ERROR", ResourceStatusEnum.RESOURCE_STATUS_ERROR,
                VcfCfAdapter.adapterInstanceStatus(o, null));
        String msg = VcfCfAdapter.adapterInstanceFailureMessage(o, null);
        assertTrue("message names the count", msg.contains("all 2 resource(s)"));
        assertTrue("message names the first failure", msg.contains("IOException: a"));
        VcfCfAdapter.CycleOutcome lines = new VcfCfAdapter.CycleOutcome();
        lines.attempted = 1;
        lines.recordFailure(ResourceStatusEnum.RESOURCE_STATUS_ERROR,
                new IOException("line1\nline2"));
        assertFalse("message is one line",
                VcfCfAdapter.adapterInstanceFailureMessage(lines, null).contains("\n"));
    }

    /** Review W1: credential-looking fragments never reach the account row. */
    private static void testRedactCredentials() {
        String[][] cases = {
            {"Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def failed", "eyJhbGci"},
            {"header Basic dXNlcjpwYXNzd29yZA== rejected", "dXNlcjpw"},
            {"OpsToken 7f3e9a1b-1111-2222-3333-444455556666 expired", "7f3e9a1b"},
            {"login failed: password=Hunter2! user=admin", "Hunter2"},
            {"login failed: passwd: s3cr3t", "s3cr3t"},
            {"body {\"username\":\"a\",\"password\":\"p@ss word\"}", "p@ss word"},
            {"GET https://admin:Sup3rS3cret@nas.example:5001/webapi refused", "Sup3rS3cret"},
            {"DSM answered _sid=AbCdEf123 code 119", "AbCdEf123"},
            {"api_key='k-123456' invalid", "k-123456"},
            {"session token: tok_998877 rejected", "tok_998877"},
        };
        for (String[] c : cases) {
            String r = VcfCfAdapter.redactCredentials(c[0]);
            assertFalse("redacted: " + r, r.contains(c[1]));
            assertTrue("marker present: " + r, r.contains("<redacted>"));
        }
        String plain = "Login failed (cached): HTTP 403 from unifi.example:443";
        assertEquals("no false redaction", plain, VcfCfAdapter.redactCredentials(plain));
        assertEquals("null passes", null, VcfCfAdapter.redactCredentials(null));
    }

    private static void testFailureMessageIsRedacted() {
        VcfCfAdapter.CycleOutcome o = new VcfCfAdapter.CycleOutcome();
        o.attempted = 1;
        o.recordFailure(ResourceStatusEnum.RESOURCE_STATUS_ERROR,
                new IOException("login refused for https://u:pw1234@host/x password=pw1234"));
        String msg = VcfCfAdapter.adapterInstanceFailureMessage(o, null);
        assertFalse("account-row reason carries no password: " + msg, msg.contains("pw1234"));
        VcfCfAdapter.CycleOutcome d = new VcfCfAdapter.CycleOutcome();
        String dm = VcfCfAdapter.adapterInstanceFailureMessage(d,
                new IOException("Bearer abcdefghijkl rejected"));
        assertFalse("discovery reason redacted too: " + dm, dm.contains("abcdefghijkl"));
    }

    // -----------------------------------------------------------------------
    // onCollect
    // -----------------------------------------------------------------------

    private static void testEveryResourceFailsSetsInstanceError() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.addAll(Arrays.asList(1, 2, 3));
        a.onCollect(a.instance, resources(1, 2, 3));
        assertEquals("instance ERROR", ResourceStatusEnum.RESOURCE_STATUS_ERROR, a.statusOf(a.instance));
        assertTrue("instance reason names the failure",
                String.valueOf(a.messageOf(a.instance)).contains("Login failed (cached)"));
        assertTrue("a WARN says the instance was set", a.log.contains("adapter instance set to RESOURCE_STATUS_ERROR"));
    }

    private static void testPartialFailureLeavesInstanceAlone() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.addAll(Arrays.asList(1, 2));
        a.onCollect(a.instance, resources(1, 2, 3));
        assertFalse("instance untouched when one resource collected", a.statuses.containsKey(a.instance));
    }

    private static void testAllDownSetsInstanceDown() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.addAll(Arrays.asList(1, 2));
        a.collector.mapTo = ResourceStatusEnum.RESOURCE_STATUS_DOWN;
        a.onCollect(a.instance, resources(1, 2));
        assertEquals("instance DOWN", ResourceStatusEnum.RESOURCE_STATUS_DOWN, a.statusOf(a.instance));
    }

    private static void testMixedDownAndErrorIsError() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.addAll(Arrays.asList(1, 2));
        a.collector.downIds.add(1);
        a.onCollect(a.instance, resources(1, 2));
        assertEquals("mixed DOWN and ERROR: ERROR", ResourceStatusEnum.RESOURCE_STATUS_ERROR,
                a.statusOf(a.instance));
    }

    private static void testNoDataMappingIsNotInstanceFailure() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.addAll(Arrays.asList(1, 2));
        a.collector.mapTo = ResourceStatusEnum.RESOURCE_STATUS_NO_DATA_RECEIVING;
        a.onCollect(a.instance, resources(1, 2));
        assertFalse("NO_DATA_RECEIVING is not an instance failure", a.statuses.containsKey(a.instance));
    }

    private static void testDiscoveryFailureWithNothingToCollect() throws Exception {
        TestAdapter a = adapter();
        a.discover = true;
        a.discoveryFailure = new IOException("HTTP 403 login refused");
        a.onCollect(a.instance, resources());
        assertEquals("instance ERROR", ResourceStatusEnum.RESOURCE_STATUS_ERROR, a.statusOf(a.instance));
        assertTrue("reason names discovery", String.valueOf(a.messageOf(a.instance)).contains("discovery failed"));
    }

    private static void testDiscoveryFailureButResourcesCollect() throws Exception {
        TestAdapter a = adapter();
        a.discover = true;
        a.discoveryFailure = new IOException("transient");
        a.onCollect(a.instance, resources(1));
        assertFalse("resources collected: instance untouched", a.statuses.containsKey(a.instance));
    }

    private static void testNothingToCollectNoFailure() throws Exception {
        TestAdapter a = adapter();
        a.onCollect(a.instance, resources());
        assertFalse("empty healthy cycle: instance untouched", a.statuses.containsKey(a.instance));
    }

    private static void testStopMidCycleSetsNothing() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.addAll(Arrays.asList(1, 2, 3));
        a.collector.stopAfterFirst = true;
        a.onCollect(a.instance, resources(1, 2, 3));
        assertFalse("a stopped cycle sets no instance status", a.statuses.containsKey(a.instance));
        Thread.interrupted();
    }

    /**
     * Review N1: an interrupt the collector wraps in a runtime exception on
     * the last resource, with no stop requested, must not set ERROR.
     */
    private static void testWrappedInterruptOnLastResourceSetsNothing() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.addAll(Arrays.asList(1, 2));
        a.collector.wrapInterruptOn = 2;
        try {
            a.onCollect(a.instance, resources(1, 2));
            assertFalse("wrapped interrupt: instance untouched", a.statuses.containsKey(a.instance));
        } finally {
            Thread.interrupted();
        }
    }

    private static void testAllSucceedSetsNothing() throws Exception {
        TestAdapter a = adapter();
        a.onCollect(a.instance, resources(1, 2));
        assertFalse("healthy cycle: instance untouched", a.statuses.containsKey(a.instance));
        assertEquals("child collected", ResourceStatusEnum.RESOURCE_STATUS_DATA_RECEIVING,
                a.statusOf(lastResources.get(0)));
    }

    // -----------------------------------------------------------------------
    // Issue #221: onCycleStart, and needsRediscovery stays once per cycle
    // -----------------------------------------------------------------------

    private static void testCycleStartOncePerCycleBeforeDiscovery() throws Exception {
        TestAdapter a = adapter();
        a.recordCycleStart = true;
        a.discover = true;
        for (int cycle = 1; cycle <= 3; cycle++) {
            a.events.clear();
            a.onCollect(a.instance, resources(1, 2));
            assertEquals("cycle " + cycle + ": onCycleStart once, first, before "
                    + "needsRediscovery, discovery and collect",
                    Arrays.asList("cycleStart", "needsRediscovery", "enumerateResources",
                            "collect:1", "collect:2"),
                    new ArrayList<>(a.events));
        }
        assertEquals("three cycles: onCycleStart called three times", 3, a.cycleStarts);
    }

    /**
     * UniFi build 14 and Synology build 31 mark the cycle start inside
     * needsRediscovery. Pin that the framework still calls it exactly once
     * per cycle, whether it answers true or false.
     */
    private static void testNeedsRediscoveryExactlyOncePerCycle() throws Exception {
        for (boolean answer : new boolean[] {false, true}) {
            TestAdapter a = adapter();
            a.collector.rediscoveryAnswer = answer;
            for (int cycle = 1; cycle <= 3; cycle++) {
                a.onCollect(a.instance, resources(1, 2, 3));
                assertEquals("needsRediscovery=" + answer + ", after cycle " + cycle
                        + ": called exactly once per cycle", cycle,
                        a.collector.needsRediscoveryCalls);
                assertEquals("needsRediscovery=" + answer + ", after cycle " + cycle
                        + ": rediscover calls", answer ? cycle : 0, a.collector.rediscoverCalls);
            }
            a.collector.failing.addAll(Arrays.asList(1, 2, 3));
            a.onCollect(a.instance, resources(1, 2, 3));
            assertEquals("needsRediscovery=" + answer + ": still once in a cycle where "
                    + "every resource fails", 4, a.collector.needsRediscoveryCalls);
        }
    }

    private static void testCycleStartFailureDoesNotStopCycle() throws Exception {
        TestAdapter a = adapter();
        a.cycleStartFailure = new IllegalStateException("snapshot reset failed");
        a.onCollect(a.instance, resources(1, 2));
        assertEquals("needsRediscovery still called", 1, a.collector.needsRediscoveryCalls);
        assertEquals("resources still collected", ResourceStatusEnum.RESOURCE_STATUS_DATA_RECEIVING,
                a.statusOf(lastResources.get(1)));
        assertTrue("a WARN names the hook", a.log.contains("onCycleStart failed"));
    }

    /** Review N2: an Error such as a LinkageError from the hook does not end the cycle. */
    private static void testCycleStartErrorDoesNotStopCycle() throws Exception {
        for (Throwable t : new Throwable[] {new NoClassDefFoundError("com/x/Missing"),
                new AssertionError("pak assert")}) {
            TestAdapter a = adapter();
            a.cycleStartFailure = t;
            a.onCollect(a.instance, resources(1));
            String kind = t.getClass().getSimpleName();
            assertEquals(kind + ": needsRediscovery still called", 1,
                    a.collector.needsRediscoveryCalls);
            assertEquals(kind + ": resource still collected",
                    ResourceStatusEnum.RESOURCE_STATUS_DATA_RECEIVING, a.statusOf(lastResources.get(0)));
            assertTrue(kind + ": WARN names the hook", a.log.contains("onCycleStart failed"));
        }
        TestAdapter a = adapter();
        a.cycleStartFailure = new InterruptedException("stop");
        try {
            Thread.interrupted();
            a.onCollect(a.instance, resources());
            assertTrue("InterruptedException from the hook: interrupt status restored",
                    Thread.currentThread().isInterrupted());
        } finally {
            Thread.interrupted();
        }
    }

    /** A VirtualMachineError or a thread kill from the hook ends the cycle. */
    private static void testCycleStartFatalEndsCycle() throws Exception {
        Throwable kill = (Throwable) Class.forName("java.lang.ThreadDeath")
                .getDeclaredConstructor().newInstance();
        for (Throwable fatal : new Throwable[] {new StackOverflowError("sim"), kill}) {
            TestAdapter a = adapter();
            a.cycleStartFailure = fatal;
            Throwable seen = null;
            try {
                a.onCollect(a.instance, resources(1));
            } catch (Throwable t) {
                seen = t;
            }
            String kind = fatal.getClass().getSimpleName();
            assertTrue(kind + ": rethrown from onCollect; got " + seen, seen == fatal);
            assertEquals(kind + ": nothing collected after it", 0,
                    a.collector.needsRediscoveryCalls);
        }
    }

    @SuppressWarnings("unchecked")
    static <T extends Throwable> void sneaky(Throwable t) throws T {
        throw (T) t;
    }

    private static void testDefaultCycleStartIsNoOp() throws Exception {
        TestAdapter a = adapter();
        a.onCollect(a.instance, resources(1));
        assertEquals("default hook: collect proceeds",
                ResourceStatusEnum.RESOURCE_STATUS_DATA_RECEIVING, a.statusOf(lastResources.get(0)));
        assertFalse("default hook: no WARN", a.log.contains("onCycleStart"));
    }

    // -----------------------------------------------------------------------
    // Test adapter
    // -----------------------------------------------------------------------

    static final class ScriptedCollector implements VcfCfCollector<Object> {
        final Set<Integer> failing = new HashSet<>();
        final Set<Integer> downIds = new HashSet<>();
        ResourceStatusEnum mapTo;
        boolean stopAfterFirst;
        Integer wrapInterruptOn;
        TestAdapter owner;
        boolean rediscoveryAnswer;
        int needsRediscoveryCalls;
        int rediscoverCalls;

        @Override
        public boolean needsRediscovery(Object config) {
            needsRediscoveryCalls++;
            owner.events.add("needsRediscovery");
            return rediscoveryAnswer;
        }

        @Override
        public void rediscover(Object config, ManagedHttpClient httpClient,
                ResourceConfig adapterInst, AdapterBase adapter) {
            rediscoverCalls++;
        }

        @Override
        public void collect(Object config, ManagedHttpClient httpClient, ResourceConfig rc,
                List<MetricData> out, AdapterBase adapter) throws Exception {
            owner.events.add("collect:" + rc.getResourceId());
            if (stopAfterFirst) owner.onStopCollection();
            if (wrapInterruptOn != null && wrapInterruptOn.equals(rc.getResourceId())) {
                Thread.currentThread().interrupt();
                throw new RuntimeException("read aborted",
                        new java.io.InterruptedIOException("interrupted"));
            }
            if (failing.contains(rc.getResourceId())) {
                throw new IOException(downIds.contains(rc.getResourceId())
                        ? "unreachable" : "Login failed (cached)");
            }
        }

        @Override
        public ResourceStatusEnum mapCollectException(Exception e) {
            if ("unreachable".equals(e.getMessage())) return ResourceStatusEnum.RESOURCE_STATUS_DOWN;
            return mapTo;
        }
    }

    public static class TestAdapter extends VcfCfAdapter<Object> {
        final Map<ResourceConfig, ResourceStatusEnum> statuses = new java.util.IdentityHashMap<>();
        final Map<ResourceConfig, String> messages = new java.util.IdentityHashMap<>();
        ScriptedCollector collector;
        ResourceConfig instance;
        LogCapture log;
        boolean discover;
        Exception discoveryFailure;
        boolean recordCycleStart;
        Throwable cycleStartFailure;
        int cycleStarts;
        List<String> events;

        @Override
        protected void onCycleStart() {
            if (cycleStartFailure != null) AdapterInstanceStatusTest.<RuntimeException>sneaky(cycleStartFailure);
            if (!recordCycleStart) {
                super.onCycleStart();
                return;
            }
            cycleStarts++;
            events.add("cycleStart");
        }

        @Override
        protected void configureAdapter(ResourceStatus s, ResourceConfig rc) { }

        @Override
        @SuppressWarnings("rawtypes")
        protected VcfCfTester getTester() { return null; }

        @Override
        @SuppressWarnings("rawtypes")
        protected VcfCfCollector getCollector() { return collector; }

        @Override
        protected boolean discoverOnCollect() { return discover; }

        @Override
        protected void enumerateResources(ResourceSink sink) throws Exception {
            events.add("enumerateResources");
            if (discoveryFailure != null) throw discoveryFailure;
        }

        @Override
        public boolean setResourceStatus(ResourceConfig rc, ResourceStatusEnum st) {
            statuses.put(rc, st);
            return true;
        }

        @Override
        public boolean setResourceStatus(ResourceConfig rc, ResourceStatusEnum st, String msg) {
            statuses.put(rc, st);
            messages.put(rc, msg);
            return true;
        }

        ResourceStatusEnum statusOf(ResourceConfig rc) { return statuses.get(rc); }

        String messageOf(ResourceConfig rc) { return messages.get(rc); }
    }

    static List<ResourceConfig> lastResources;

    private static TestAdapter adapter() throws Exception {
        TestAdapter a = allocate(TestAdapter.class);
        setField(VcfCfAdapter.class, a, "abortRequested", new AtomicBoolean(false));
        a.log = LogCapture.create();
        Class<?> fi = Class.forName("com.vmware.vrops.logging.AdapterLoggerFactory");
        Object factory = Proxy.newProxyInstance(fi.getClassLoader(), new Class<?>[] {fi},
                (p, m, args) -> m.getName().equals("getLogger") ? a.log.logger() : null);
        setField(AdapterBase.class, a, "adapterLoggerFactory", factory);
        // Field initializers do not run under allocateInstance.
        setField(TestAdapter.class, a, "statuses", new java.util.IdentityHashMap<>());
        setField(TestAdapter.class, a, "messages", new java.util.IdentityHashMap<>());
        a.events = new ArrayList<>();
        a.collector = new ScriptedCollector();
        a.collector.owner = a;
        a.instance = new ResourceConfig(9000);
        return a;
    }

    private static List<ResourceConfig> resources(Integer... ids) {
        List<ResourceConfig> out = new ArrayList<>();
        for (Integer id : ids) out.add(new ResourceConfig(id));
        lastResources = out;
        return out;
    }

    private static void setField(Class<?> owner, Object target, String name, Object value)
            throws Exception {
        Field f = owner.getDeclaredField(name);
        f.setAccessible(true);
        f.set(target, value);
    }

    @SuppressWarnings("unchecked")
    private static <T> T allocate(Class<T> cls) throws Exception {
        Field f = Class.forName("sun.misc.Unsafe").getDeclaredField("theUnsafe");
        f.setAccessible(true);
        Object unsafe = f.get(null);
        Method m = unsafe.getClass().getMethod("allocateInstance", Class.class);
        return (T) m.invoke(unsafe, cls);
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

    private static void assertEquals(String label, Object expected, Object actual) {
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
