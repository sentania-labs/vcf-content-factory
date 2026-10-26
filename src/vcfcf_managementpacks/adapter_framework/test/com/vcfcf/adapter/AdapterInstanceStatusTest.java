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
 * instance status (the account row), not only the objects'. Issue #245: a
 * failed child object gets a status the SDK accepts on a child, never one it
 * refuses and drops.
 *
 * <p>No JUnit: call via {@code main()}. Drives the real
 * {@link VcfCfAdapter#onCollect} with a scripted collector; the test adapter
 * records {@code setResourceStatus} calls instead of reaching the platform,
 * after asking the SDK's own gate ({@code AdapterBase.isValidStatusForResource},
 * private, called reflectively) whether it would take the status. A status
 * that gate refuses is recorded as refused and not applied, as the SDK does,
 * so the test checks against whichever SDK jar is on the classpath.
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
        testChildStatusRuleCoversEveryStatus();
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
            testGateIsTheSdks();
            testFailedChildErrorIsMappedNotDropped();
            testFailedChildDownIsMappedNotDropped();
            testEveryChildFailsMapsChildrenAndRaisesInstance();
            testEveryMappedStatusReachesTheChild();
            testInterruptedChildIsNotRefused();
            testSdkNotTakingStatusIsLogged();
            testInstanceNotTakingStatusIsLogged();
            testMoveSummaryIsOneLinePerCycle();
            testOffListWarnOncePerStatus();
            testFailedChildRecoversNextCycle();
            testStackTraceOncePerFailureStreak();
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

    /**
     * Issue #245: every status, null included, maps onto the SDK's child
     * list, and onto the instance list for the instance; accepted ones are
     * kept as they are.
     */
    private static void testChildStatusRuleCoversEveryStatus() {
        List<ResourceStatusEnum> all = new ArrayList<>(Arrays.asList(ResourceStatusEnum.values()));
        all.add(null);
        for (ResourceStatusEnum st : all) {
            ResourceStatusEnum child = VcfCfAdapter.childStatusFor(st);
            assertTrue("child " + st + " -> " + child + " is on the SDK child list",
                    ResourceStatusEnum.isResourceAllowedStatus(child));
            if (st != null && ResourceStatusEnum.isResourceAllowedStatus(st)) {
                assertEquals("child " + st + " kept", st, child);
            } else {
                assertEquals("child " + st + " -> NO_DATA_RECEIVING",
                        ResourceStatusEnum.RESOURCE_STATUS_NO_DATA_RECEIVING, child);
            }
            ResourceStatusEnum inst = VcfCfAdapter.instanceStatusFor(st);
            assertTrue("instance " + st + " -> " + inst + " is on the SDK instance list",
                    ResourceStatusEnum.isAdapterAllowedStatus(inst));
        }
        assertFalse("ERROR is not on the SDK child list (the #245 premise)",
                ResourceStatusEnum.isResourceAllowedStatus(ResourceStatusEnum.RESOURCE_STATUS_ERROR));
        assertFalse("DOWN is not on the SDK child list (the #245 premise)",
                ResourceStatusEnum.isResourceAllowedStatus(ResourceStatusEnum.RESOURCE_STATUS_DOWN));
        ResourceConfig inst = new ResourceConfig(9000);
        assertTrue("same object is the instance", VcfCfAdapter.isAdapterInstance(inst, inst));
        assertTrue("same id is the instance",
                VcfCfAdapter.isAdapterInstance(inst, new ResourceConfig(9000)));
        assertFalse("other id is a child", VcfCfAdapter.isAdapterInstance(inst, new ResourceConfig(1)));
        assertFalse("no instance: a child", VcfCfAdapter.isAdapterInstance(null, inst));
        ResourceConfig noId = new ResourceConfig();
        assertFalse("null id is a child even as the same object (SDK isAdapterInstResourceConfig)",
                VcfCfAdapter.isAdapterInstance(noId, noId));
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
    // Issue #245: a failed child is never refused and dropped
    // -----------------------------------------------------------------------

    /** The test adapter's gate is the SDK's: ERROR refused on a child, taken on the instance. */
    private static void testGateIsTheSdks() throws Exception {
        TestAdapter a = adapter();
        ResourceConfig child = new ResourceConfig(1);
        assertFalse("SDK refuses ERROR on a child",
                a.setResourceStatus(child, ResourceStatusEnum.RESOURCE_STATUS_ERROR));
        assertFalse("SDK refuses DOWN on a child",
                a.setResourceStatus(child, ResourceStatusEnum.RESOURCE_STATUS_DOWN));
        assertTrue("SDK takes NO_DATA_RECEIVING on a child",
                a.setResourceStatus(child, ResourceStatusEnum.RESOURCE_STATUS_NO_DATA_RECEIVING));
        assertTrue("SDK takes ERROR on the instance",
                a.setResourceStatus(a.instance, ResourceStatusEnum.RESOURCE_STATUS_ERROR, "x"));
    }

    private static void testFailedChildErrorIsMappedNotDropped() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.add(1);
        a.onCollect(a.instance, resources(1, 2));
        assertEquals("nothing refused", 0, a.refused.size());
        assertEquals("failed child shows NO_DATA_RECEIVING",
                ResourceStatusEnum.RESOURCE_STATUS_NO_DATA_RECEIVING, a.statusOf(lastResources.get(0)));
        assertEquals("healthy child shows DATA_RECEIVING",
                ResourceStatusEnum.RESOURCE_STATUS_DATA_RECEIVING, a.statusOf(lastResources.get(1)));
        assertTrue("the move is logged in the cycle summary", a.log.contains(
                "1 failed object(s) set to RESOURCE_STATUS_NO_DATA_RECEIVING this cycle (first: ?/1)"));
        assertTrue("summary says ERROR or DOWN on the instance",
                a.log.contains("which turns ERROR or DOWN when every object in the cycle fails"));
        assertFalse("partial failure: instance untouched", a.statuses.containsKey(a.instance));
    }

    private static void testFailedChildDownIsMappedNotDropped() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.add(1);
        a.collector.mapTo = ResourceStatusEnum.RESOURCE_STATUS_DOWN;
        a.onCollect(a.instance, resources(1, 2));
        assertEquals("nothing refused", 0, a.refused.size());
        assertEquals("DOWN child shows NO_DATA_RECEIVING",
                ResourceStatusEnum.RESOURCE_STATUS_NO_DATA_RECEIVING, a.statusOf(lastResources.get(0)));
    }

    private static void testEveryChildFailsMapsChildrenAndRaisesInstance() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.addAll(Arrays.asList(1, 2));
        a.onCollect(a.instance, resources(1, 2));
        assertEquals("nothing refused", 0, a.refused.size());
        for (ResourceConfig rc : lastResources) {
            assertEquals("child " + rc.getResourceId() + " NO_DATA_RECEIVING",
                    ResourceStatusEnum.RESOURCE_STATUS_NO_DATA_RECEIVING, a.statusOf(rc));
        }
        assertEquals("instance still ERROR (#223)", ResourceStatusEnum.RESOURCE_STATUS_ERROR,
                a.statusOf(a.instance));
    }

    /** Whatever a pak maps an exception to, the child gets a status the SDK takes. */
    private static void testEveryMappedStatusReachesTheChild() throws Exception {
        for (ResourceStatusEnum st : ResourceStatusEnum.values()) {
            TestAdapter a = adapter();
            a.collector.failing.add(1);
            a.collector.mapTo = st;
            a.onCollect(a.instance, resources(1, 2));
            assertEquals(st + ": nothing refused", 0, a.refused.size());
            ResourceStatusEnum got = a.statusOf(lastResources.get(0));
            assertTrue(st + ": child got " + got, got != null
                    && ResourceStatusEnum.isResourceAllowedStatus(got));
            if (st == ResourceStatusEnum.RESOURCE_STATUS_ERROR
                    || st == ResourceStatusEnum.RESOURCE_STATUS_DOWN) {
                assertTrue(st + ": the move is in the cycle summary",
                        a.log.contains("1 failed object(s) set to RESOURCE_STATUS_NO_DATA_RECEIVING"));
            } else if (got != st) {
                assertTrue(st + ": the move is logged at WARN", a.log.lines().stream().anyMatch(
                        l -> l.startsWith("WARN ") && l.contains(
                                "status " + st.name() + " is not accepted on a child object")));
            }
        }
    }

    /** Review N1: the expected ERROR/DOWN move is one INFO line per cycle, not one per object. */
    private static void testMoveSummaryIsOneLinePerCycle() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.addAll(Arrays.asList(1, 2, 3));
        a.collector.downIds.add(2);
        a.onCollect(a.instance, resources(1, 2, 3, 4));
        assertEquals("one summary line", 1, countLines(a, "INFO", "failed object(s) set to", null));
        assertTrue("summary counts all three", a.log.contains(
                "3 failed object(s) set to RESOURCE_STATUS_NO_DATA_RECEIVING this cycle (first: ?/1)"));
        assertEquals("no per-object move line", 0,
                countLines(a, null, "is not accepted on a child object", null));
        a.log.clear();
        a.onCollect(a.instance, resources(4));
        assertEquals("healthy cycle: no summary", 0,
                countLines(a, null, "failed object(s) set to", null));
    }

    /** Review N1: an off-list pak mapping is warned once per status per instance, not every cycle. */
    private static void testOffListWarnOncePerStatus() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.addAll(Arrays.asList(1, 2));
        a.collector.mapTo = ResourceStatusEnum.RESOURCE_STATUS_UNKNOWN;
        for (int cycle = 0; cycle < 3; cycle++) a.onCollect(a.instance, resources(1, 2, 3));
        assertEquals("UNKNOWN warned once over 3 cycles and 6 failures", 1,
                countLines(a, "WARN", "status RESOURCE_STATUS_UNKNOWN is not accepted", null));
        assertEquals("children still NO_DATA_RECEIVING",
                ResourceStatusEnum.RESOURCE_STATUS_NO_DATA_RECEIVING, a.statusOf(lastResources.get(1)));
        a.collector.mapTo = ResourceStatusEnum.RESOURCE_STATUS_COLLECTOR_DOWN;
        a.onCollect(a.instance, resources(1, 2, 3));
        a.onCollect(a.instance, resources(1, 2, 3));
        assertEquals("a second status gets its own single WARN", 1,
                countLines(a, "WARN", "status RESOURCE_STATUS_COLLECTOR_DOWN is not accepted", null));
    }

    /** Review N5: NO_DATA_RECEIVING is not sticky; a child that recovers shows DATA_RECEIVING. */
    private static void testFailedChildRecoversNextCycle() throws Exception {
        TestAdapter a = adapter();
        a.collector.failing.add(1);
        a.onCollect(a.instance, resources(1, 2));
        ResourceConfig child = lastResources.get(0);
        assertEquals("cycle 1: failed child NO_DATA_RECEIVING",
                ResourceStatusEnum.RESOURCE_STATUS_NO_DATA_RECEIVING, a.statusOf(child));
        a.collector.failing.clear();
        a.onCollect(a.instance, Arrays.asList(child, lastResources.get(1)));
        assertEquals("cycle 2: recovered child DATA_RECEIVING",
                ResourceStatusEnum.RESOURCE_STATUS_DATA_RECEIVING, a.statusOf(child));
        assertEquals("nothing refused in either cycle", 0, a.refused.size());
    }

    /**
     * Review follow-up 2: the stack trace at WARN once per failure streak; a
     * one-line WARN plus the trace at DEBUG while it keeps failing; a new
     * streak after success, or after the resource left a cycle, logs it again.
     */
    private static void testStackTraceOncePerFailureStreak() throws Exception {
        TestAdapter a = adapter("DEBUG");
        a.collector.failing.add(1);
        for (int cycle = 0; cycle < 3; cycle++) a.onCollect(a.instance, resources(1, 2));
        assertEquals("trace at WARN once in a 3-cycle streak", 1,
                countLines(a, "WARN", "error collecting ?/1", true));
        assertEquals("one-line WARN on cycles 2 and 3", 2,
                countLines(a, "WARN", "error collecting ?/1", false));
        assertTrue("streak length named", a.log.contains("(failed 3 cycles in a row; stack trace at DEBUG)"));
        assertEquals("trace at DEBUG on cycles 2 and 3", 2,
                countLines(a, "DEBUG", "stack trace for ?/1", true));

        a.collector.failing.clear();
        a.onCollect(a.instance, resources(1, 2));
        a.collector.failing.add(1);
        a.log.clear();
        a.onCollect(a.instance, resources(1, 2));
        assertEquals("after a success: new streak, trace at WARN again", 1,
                countLines(a, "WARN", "error collecting ?/1", true));

        a.onCollect(a.instance, resources(2));
        a.log.clear();
        a.onCollect(a.instance, resources(1, 2));
        assertEquals("after leaving a cycle: streak forgotten, trace at WARN again", 1,
                countLines(a, "WARN", "error collecting ?/1", true));
    }

    /**
     * Captured lines at {@code level} (any level when null) containing
     * {@code text}; {@code withTrace} true/false filters on an attached
     * throwable, null ignores it.
     */
    private static int countLines(TestAdapter a, String level, String text, Boolean withTrace) {
        int n = 0;
        for (String l : a.log.lines()) {
            if (level != null && !l.startsWith(level + " ")) continue;
            if (!l.contains(text)) continue;
            if (withTrace != null && withTrace != l.contains(" [thrown ")) continue;
            n++;
        }
        return n;
    }

    private static void testInterruptedChildIsNotRefused() throws Exception {
        TestAdapter a = adapter();
        a.collector.interruptOn = 1;
        try {
            a.onCollect(a.instance, resources(1, 2));
        } finally {
            Thread.interrupted();
        }
        assertEquals("nothing refused", 0, a.refused.size());
        assertEquals("interrupted child shows NO_DATA_RECEIVING",
                ResourceStatusEnum.RESOURCE_STATUS_NO_DATA_RECEIVING, a.statusOf(lastResources.get(0)));
    }

    /** A status the SDK still does not take is logged, never silent. */
    private static void testSdkNotTakingStatusIsLogged() throws Exception {
        TestAdapter a = adapter();
        a.takeNothing = true;
        a.collector.failing.add(1);
        a.onCollect(a.instance, resources(1, 2));
        assertTrue("WARN names the status and object", a.log.contains(
                "the SDK did not take status RESOURCE_STATUS_NO_DATA_RECEIVING for ?/1"));
        assertTrue("WARN for the healthy object too", a.log.contains(
                "the SDK did not take status RESOURCE_STATUS_DATA_RECEIVING for ?/2"));
    }

    private static void testInstanceNotTakingStatusIsLogged() throws Exception {
        TestAdapter a = adapter();
        a.takeNothing = true;
        a.collector.failing.addAll(Arrays.asList(1, 2));
        a.onCollect(a.instance, resources(1, 2));
        assertTrue("WARN says the instance status was not taken", a.log.contains(
                "the SDK did not take adapter instance status RESOURCE_STATUS_ERROR"));
        assertFalse("no claim that it was set", a.log.contains("adapter instance set to"));
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
        Integer interruptOn;
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
            if (interruptOn != null && interruptOn.equals(rc.getResourceId())) {
                throw new InterruptedException("stop");
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
        final List<String> refused = new ArrayList<>();
        boolean takeNothing;
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
        public ResourceConfig getAdapterInstResource() { return instance; }

        /** The SDK's own child-versus-instance status check, from the jar on the classpath. */
        boolean sdkTakes(ResourceConfig rc, ResourceStatusEnum st) {
            try {
                Method m = AdapterBase.class.getDeclaredMethod("isValidStatusForResource",
                        ResourceConfig.class, ResourceStatusEnum.class);
                m.setAccessible(true);
                return (Boolean) m.invoke(this, rc, st);
            } catch (ReflectiveOperationException e) {
                throw new IllegalStateException("SDK gate not reachable: " + e, e);
            }
        }

        @Override
        public boolean setResourceStatus(ResourceConfig rc, ResourceStatusEnum st) {
            return setResourceStatus(rc, st, null);
        }

        @Override
        public boolean setResourceStatus(ResourceConfig rc, ResourceStatusEnum st, String msg) {
            if (takeNothing) return false;
            if (!sdkTakes(rc, st)) {
                refused.add(rc.getResourceId() + ":" + st);
                return false;
            }
            statuses.put(rc, st);
            if (msg != null) messages.put(rc, msg);
            return true;
        }

        ResourceStatusEnum statusOf(ResourceConfig rc) { return statuses.get(rc); }

        String messageOf(ResourceConfig rc) { return messages.get(rc); }
    }

    static List<ResourceConfig> lastResources;

    private static TestAdapter adapter() throws Exception {
        return adapter("INFO");
    }

    private static TestAdapter adapter(String logLevel) throws Exception {
        TestAdapter a = allocate(TestAdapter.class);
        setField(VcfCfAdapter.class, a, "abortRequested", new AtomicBoolean(false));
        a.log = LogCapture.create(logLevel);
        Class<?> fi = Class.forName("com.vmware.vrops.logging.AdapterLoggerFactory");
        Object factory = Proxy.newProxyInstance(fi.getClassLoader(), new Class<?>[] {fi},
                (p, m, args) -> m.getName().equals("getLogger") ? a.log.logger() : null);
        setField(AdapterBase.class, a, "adapterLoggerFactory", factory);
        // Field initializers do not run under allocateInstance.
        setField(TestAdapter.class, a, "statuses", new java.util.IdentityHashMap<>());
        setField(TestAdapter.class, a, "messages", new java.util.IdentityHashMap<>());
        setField(TestAdapter.class, a, "refused", new ArrayList<>());
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
