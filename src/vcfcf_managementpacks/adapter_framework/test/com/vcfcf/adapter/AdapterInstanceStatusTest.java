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

    private static void testAllSucceedSetsNothing() throws Exception {
        TestAdapter a = adapter();
        a.onCollect(a.instance, resources(1, 2));
        assertFalse("healthy cycle: instance untouched", a.statuses.containsKey(a.instance));
        assertEquals("child collected", ResourceStatusEnum.RESOURCE_STATUS_DATA_RECEIVING,
                a.statusOf(lastResources.get(0)));
    }

    // -----------------------------------------------------------------------
    // Test adapter
    // -----------------------------------------------------------------------

    static final class ScriptedCollector implements VcfCfCollector<Object> {
        final Set<Integer> failing = new HashSet<>();
        final Set<Integer> downIds = new HashSet<>();
        ResourceStatusEnum mapTo;
        boolean stopAfterFirst;
        TestAdapter owner;

        @Override
        public void collect(Object config, ManagedHttpClient httpClient, ResourceConfig rc,
                List<MetricData> out, AdapterBase adapter) throws Exception {
            if (stopAfterFirst) owner.onStopCollection();
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
