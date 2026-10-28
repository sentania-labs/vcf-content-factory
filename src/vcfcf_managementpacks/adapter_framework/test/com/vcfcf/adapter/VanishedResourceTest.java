package com.vcfcf.adapter;

import com.integrien.alive.common.adapter3.AdapterBase;
import com.integrien.alive.common.adapter3.DiscoveryResult;
import com.integrien.alive.common.adapter3.MetricData;
import com.integrien.alive.common.adapter3.ResourceKey;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig;
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
import java.util.Collection;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * unifi#20: a resource the platform knows that is missing from
 * {@code enumerateResources} for N consecutive complete cycles is marked
 * {@code NOTEXIST} with {@code changeResourceState}, the way the Broadcom
 * adapters do (knowledge/context/sdk/vanished_object_lifecycle.md).
 *
 * <p>No JUnit: call via {@code main()}. Drives the real
 * {@link VcfCfAdapter#onCollect}. The test adapter supplies the platform's
 * monitoring and stopped resources through the framework's package-private
 * seams (the SDK's {@code adapterCache} is final and needs a live
 * {@code AdapterConfig}), and records {@code changeResourceState} and
 * {@code setResourceStatus} instead of reaching the platform. Needs log4j at
 * runtime for the adapter's logger ({@link LogCapture}); SKIPPED without it.
 */
public class VanishedResourceTest {

    private static final String AK = "unifi_controller";
    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;
    private static int skipped = 0;

    public static void main(String[] args) throws Exception {
        testMarkableRule();
        if (!LogCapture.available()) {
            skip("onCollect tests: log4j not on the runtime classpath"
                    + " (add a jar carrying it, e.g. adapter_runtime/lib/*)");
        } else {
            testMarkAfterDefaultMisses();
            testThresholdOverride();
            testMarkedObjectNotCollectedOrRemarked();
            testResetOnReappearance();
            testStartOnReappearanceAfterMark();
            testStoppedWhenMarkedGetsNoStart();
            testNoMarkingWhenEnumerationFails();
            testNoMarkingWhenRediscoverFails();
            testNoMarkingWhenInstanceFailing();
            testNoMarkingWhenCycleStopped();
            testNoMarkingOnEmptyEnumeration();
            testDefaultMarksNothing();
            testSameKindFromTwoParentsOneUnread();
            testMarkedEntryForgottenWhenPlatformDropsIt();
            testNoStartWhenPlatformNoLongerListsIt();
            testKindNotDeliveredIsNotRead();
            testKindsReadThisCycleOverrideExcludesKind();
            testKindsReadThisCycleOverrideCoversLastObject();
            testEmptyKindsReadMarksNothing();
            testAdapterInstanceNeverMarked();
            testExcludedKindsNeverMarked();
            testForeignAdapterKindNeverMarked();
            testHookFailureMarksNothing();
            testDisabledWithZeroThreshold();
            testOffWithoutDiscoverOnCollect();
            testNoAdapterCacheMarksNothing();
        }
        report();
    }

    // -----------------------------------------------------------------------
    // Pure rule
    // -----------------------------------------------------------------------

    private static void testMarkableRule() {
        ResourceConfig inst = platform(9000, "unifi_instance", "i");
        // markable takes lower-cased kind sets (VcfCfAdapter.lowerKinds).
        Set<String> read = new HashSet<>(Arrays.asList("unifiswitch", "unifi_instance"));
        Set<String> none = new HashSet<>();
        assertTrue("a read kind of this adapter is markable", VcfCfAdapter.markable(
                platform(1, "UniFiSwitch", "a"), inst, null, AK, read, none));
        assertFalse("the instance (by id) is never markable", VcfCfAdapter.markable(
                inst, inst, null, AK, read, none));
        assertFalse("the instance kind is never markable", VcfCfAdapter.markable(
                platform(2, "unifi_instance", "other"), inst, null, AK, read, none));
        assertFalse("the platform's instance resource is never markable", VcfCfAdapter.markable(
                platform(9000, "UniFiSwitch", "x"), null, inst, AK, read, none));
        assertFalse("a kind not read is not markable", VcfCfAdapter.markable(
                platform(3, "UniFiCamera", "c"), inst, null, AK, read, none));
        assertFalse("an excluded kind is not markable", VcfCfAdapter.markable(
                platform(1, "UniFiSwitch", "a"), inst, null, AK, read,
                new HashSet<>(Arrays.asList("unifiswitch"))));
        assertFalse("another adapter kind is not markable", VcfCfAdapter.markable(
                platformOf(4, "UniFiSwitch", "a", "VMWARE"), inst, null, AK, read, none));
        assertFalse("no resource id: not markable", VcfCfAdapter.markable(
                new ResourceConfig(key("UniFiSwitch", "a")), inst, null, AK, read, none));
    }

    // -----------------------------------------------------------------------
    // Marking
    // -----------------------------------------------------------------------

    private static void testMarkAfterDefaultMisses() throws Exception {
        TestAdapter a = unifi();
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 11);
        assertEquals("11 misses: nothing marked", 0, a.changes.size());
        assertEquals("default threshold is 12", 12, VcfCfAdapter.DEFAULT_NOT_EXISTING_MISSED_CYCLES);
        a.onCollect(a.instance, a.resources());
        assertEquals("12th miss: one change", 1, a.changes.size());
        assertEquals("switch b marked NOTEXIST", "2:NOTEXIST", a.changes.get(0));
        assertTrue("the platform's own ResourceConfig is passed",
                a.changedConfigs.get(0) == a.known.get(2));
        assertTrue("one INFO line with the count and first object", a.log.contains(
                "onCollect: 1 object(s) marked NOT_EXISTING this cycle, missing from the"
                + " enumeration for 12 consecutive complete cycles (first: UniFiSwitch/b)"));
    }

    private static void testThresholdOverride() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 3;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 2);
        assertEquals("2 of 3: nothing", 0, a.changes.size());
        a.onCollect(a.instance, a.resources());
        assertEquals("3 of 3: marked", Arrays.asList("2:NOTEXIST"), a.changes);
    }

    private static void testMarkedObjectNotCollectedOrRemarked() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 2;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 2);
        assertEquals("marked once", Arrays.asList("2:NOTEXIST"), a.changes);
        a.collected.clear();
        a.statuses.clear();
        cycles(a, 5);
        assertEquals("not marked again", Arrays.asList("2:NOTEXIST"), a.changes);
        assertFalse("a marked object is not collected", a.collected.contains(2));
        assertFalse("a marked object gets no DATA_RECEIVING", a.statuses.containsKey(2));
        assertTrue("the others are still collected", a.collected.contains(1));
    }

    private static void testResetOnReappearance() throws Exception {
        TestAdapter a = unifi();
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 11);
        a.deliver("UniFiSwitch", "b");
        a.onCollect(a.instance, a.resources());
        a.undeliver("UniFiSwitch", "b");
        cycles(a, 11);
        assertEquals("seen once in between: the count started over", 0, a.changes.size());
        a.onCollect(a.instance, a.resources());
        assertEquals("12 in a row after the sighting: marked", Arrays.asList("2:NOTEXIST"),
                a.changes);
    }

    private static void testStartOnReappearanceAfterMark() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 2;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 2);
        a.deliver("UniFiSwitch", "b");
        a.collected.clear();
        a.onCollect(a.instance, a.resources());
        assertEquals("back: START sent", Arrays.asList("2:NOTEXIST", "2:START"), a.changes);
        assertTrue("START gets the platform's ResourceConfig",
                a.changedConfigs.get(1) == a.known.get(2));
        assertTrue("back: collected again", a.collected.contains(2));
        assertTrue("one INFO line for the return", a.log.contains(
                "onCollect: 1 object(s) marked NOT_EXISTING are back in the enumeration and"
                + " were sent START this cycle (first: UniFiSwitch/b)"));
        a.undeliver("UniFiSwitch", "b");
        a.onCollect(a.instance, a.resources());
        assertEquals("gone again: the count starts from zero",
                Arrays.asList("2:NOTEXIST", "2:START"), a.changes);
        a.onCollect(a.instance, a.resources());
        assertEquals("and marks again at the threshold",
                Arrays.asList("2:NOTEXIST", "2:START", "2:NOTEXIST"), a.changes);
    }

    private static void testStoppedWhenMarkedGetsNoStart() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.stopped.add(2);
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.onCollect(a.instance, a.resources());
        assertEquals("a stopped resource is marked too (vSphere, vSAN, NSX, Dockerized)",
                Arrays.asList("2:NOTEXIST"), a.changes);
        a.deliver("UniFiSwitch", "b");
        a.onCollect(a.instance, a.resources());
        assertEquals("but gets no START back: the UI stop is kept",
                Arrays.asList("2:NOTEXIST"), a.changes);
    }

    // -----------------------------------------------------------------------
    // Guards
    // -----------------------------------------------------------------------

    private static void testNoMarkingWhenEnumerationFails() throws Exception {
        TestAdapter a = unifi();
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 11);
        a.enumerationFailure = new IOException("HTTP 502 from controller");
        cycles(a, 5);
        assertEquals("failed enumerations count nothing and mark nothing", 0, a.changes.size());
        a.enumerationFailure = null;
        a.onCollect(a.instance, a.resources());
        assertEquals("the next good cycle is the 12th miss", Arrays.asList("2:NOTEXIST"),
                a.changes);
    }

    private static void testNoMarkingWhenRediscoverFails() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.collector.rediscoverFailure = new IOException("stitch failed");
        a.onCollect(a.instance, a.resources());
        assertEquals("a failed rediscover marks nothing", 0, a.changes.size());
    }

    private static void testNoMarkingWhenInstanceFailing() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.collector.failAll = true;
        a.onCollect(a.instance, a.resources());
        assertEquals("every collect failed (instance ERROR): nothing marked", 0, a.changes.size());
        a.collector.failAll = false;
        a.onCollect(a.instance, a.resources());
        assertEquals("next healthy cycle marks", Arrays.asList("2:NOTEXIST"), a.changes);
    }

    private static void testNoMarkingWhenCycleStopped() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.collector.stopOnFirst = true;
        try {
            a.onCollect(a.instance, a.resources());
        } finally {
            Thread.interrupted();
        }
        assertEquals("a stopped cycle marks nothing", 0, a.changes.size());
    }

    private static void testNoMarkingOnEmptyEnumeration() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.kindsRead = new HashSet<>(Arrays.asList("UniFiWorld", "UniFiSwitch"));
        a.onCollect(a.instance, a.resources());
        assertEquals("an enumeration that delivered nothing marks nothing", 0, a.changes.size());
    }

    // -----------------------------------------------------------------------
    // Kinds read this cycle
    // -----------------------------------------------------------------------

    /** Review B1: kindsReadThisCycle() left at its default null marks nothing. */
    private static void testDefaultMarksNothing() throws Exception {
        TestAdapter a = unifi();
        a.kindsRead = null;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 30);
        assertEquals("default (no opt-in): 30 cycles with b missing, nothing marked", 0,
                a.changes.size());
    }

    /**
     * Review B1/W4: two sites. Site 2's device list could not be read, so its
     * switches b and c are missing while UniFiSwitch still arrives from site 1.
     * Delivery of the kind is not proof it was read in full.
     */
    private static void testSameKindFromTwoParentsOneUnread() throws Exception {
        TestAdapter a = unifi();
        a.known.put(3, platform(3, "UniFiSwitch", "c"));
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.kindsRead = null;
        cycles(a, 30);
        assertEquals("default: site 2 unread, its switches never marked", 0, a.changes.size());
        a.kindsRead = new HashSet<>(Arrays.asList("UniFiWorld"));
        cycles(a, 30);
        assertEquals("opted in, UniFiSwitch left out because a site failed: nothing marked", 0,
                a.changes.size());
        a.kindsRead = new HashSet<>(Arrays.asList("UniFiWorld", "UniFiSwitch"));
        cycles(a, 11);
        assertEquals("declared read in full: counting starts only now (11 of 12)", 0,
                a.changes.size());
        a.onCollect(a.instance, a.resources());
        assertEquals("declared read in full: b and c marked at 12",
                Arrays.asList("2:NOTEXIST", "3:NOTEXIST"), a.changes);
    }

    /**
     * Review W2/W4: once the platform stops listing a marked object (the SDK's
     * AdapterCache.processNotExistingResponse drops it), the entry is released.
     */
    private static void testMarkedEntryForgottenWhenPlatformDropsIt() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 2;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 2);
        assertEquals("b marked", Arrays.asList("2:NOTEXIST"), a.changes);
        assertEquals("tracked: b", 1, tracker(a).size());
        a.known.remove(2);
        a.onCollect(a.instance, a.resources());
        assertEquals("platform dropped b: no longer tracked", 0, tracker(a).size());
        assertTrue("and one INFO line says so", a.log.contains(
                "onCollect: 1 object(s) marked NOT_EXISTING are no longer listed by the platform"
                + " and are no longer tracked (first: UniFiSwitch/b)"));
        // Discovery registers b again under a new id; still missing, it counts from zero.
        a.known.put(20, platform(20, "UniFiSwitch", "b"));
        a.onCollect(a.instance, a.resources());
        assertEquals("new b: 1 of 2, not marked", Arrays.asList("2:NOTEXIST"), a.changes);
        a.onCollect(a.instance, a.resources());
        assertEquals("new b: marked at 2", Arrays.asList("2:NOTEXIST", "20:NOTEXIST"),
                a.changes);
    }

    /**
     * Review W1/W4: a marked object back in the enumeration that the platform
     * no longer lists has no platform ResourceConfig to send START with. No
     * START; one INFO line.
     */
    private static void testNoStartWhenPlatformNoLongerListsIt() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 2;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 2);
        a.known.remove(2);
        a.deliver("UniFiSwitch", "b");
        a.onCollect(a.instance, a.resources());
        assertEquals("no START without a platform ResourceConfig", Arrays.asList("2:NOTEXIST"),
                a.changes);
        assertTrue("INFO: back but no longer listed", a.log.contains(
                "onCollect: 1 object(s) marked NOT_EXISTING are back in the enumeration but the"
                + " platform no longer lists them, so no START was sent; they are registered"
                + " again through discovery (first: UniFiSwitch/b)"));
        assertEquals("and no longer tracked", 0, tracker(a).size());
    }

    @SuppressWarnings("unchecked")
    private static Map<Integer, ?> tracker(TestAdapter a) throws Exception {
        Field f = VcfCfAdapter.class.getDeclaredField("vanishTracker");
        f.setAccessible(true);
        Map<Integer, ?> m = (Map<Integer, ?>) f.get(a);
        return m == null ? new java.util.HashMap<Integer, Object>() : m;
    }

    /** UniFi Protect down: no NVR and no camera delivered, so neither kind is read. */
    private static void testKindNotDeliveredIsNotRead() throws Exception {
        TestAdapter a = unifi();
        a.known.put(10, platform(10, "UniFiNvr", "nvr"));
        a.known.put(11, platform(11, "UniFiCamera", "backyard"));
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.deliver("UniFiSwitch", "b");
        cycles(a, 30);
        assertEquals("cameras and NVR never marked while Protect is unread", 0, a.changes.size());
    }

    private static void testKindsReadThisCycleOverrideExcludesKind() throws Exception {
        TestAdapter a = unifi();
        a.known.put(11, platform(11, "UniFiCamera", "backyard"));
        a.known.put(12, platform(12, "UniFiCamera", "front"));
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.deliver("UniFiSwitch", "b");
        a.deliver("UniFiCamera", "front");
        a.kindsRead = new HashSet<>(Arrays.asList("UniFiWorld", "UniFiSwitch"));
        cycles(a, 30);
        assertEquals("a camera list read partly: the adapter leaves the kind out, nothing marked",
                0, a.changes.size());
    }

    private static void testKindsReadThisCycleOverrideCoversLastObject() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 2;
        a.known.put(11, platform(11, "UniFiCamera", "backyard"));
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.deliver("UniFiSwitch", "b");
        cycles(a, 2);
        assertEquals("default: the last camera is never marked", 0, a.changes.size());
        a.kindsRead = new HashSet<>(Arrays.asList("UniFiWorld", "UniFiSwitch", "UniFiCamera"));
        cycles(a, 2);
        assertEquals("declared read with zero cameras: the last camera is marked",
                Arrays.asList("11:NOTEXIST"), a.changes);
    }

    private static void testEmptyKindsReadMarksNothing() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.kindsRead = new HashSet<>();
        cycles(a, 3);
        assertEquals("no kinds read: nothing marked", 0, a.changes.size());
    }

    // -----------------------------------------------------------------------
    // Never marked
    // -----------------------------------------------------------------------

    private static void testAdapterInstanceNeverMarked() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.known.put(9000, a.instance);
        a.known.put(13, platform(13, "unifi_instance", "another instance"));
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.kindsRead = new HashSet<>(Arrays.asList("UniFiWorld", "UniFiSwitch", "unifi_instance"));
        cycles(a, 20);
        assertEquals("only the switch; never the adapter instance or its kind",
                Arrays.asList("2:NOTEXIST"), a.changes);
    }

    private static void testExcludedKindsNeverMarked() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.known.put(14, platform(14, "UniFiWirelessAggregate", "old site summary"));
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.deliver("UniFiWirelessAggregate", "default summary");
        a.kindsRead = new HashSet<>(Arrays.asList("UniFiWorld", "UniFiSwitch",
                "UniFiWirelessAggregate"));
        // Review N3: the exclusion holds whatever the casing.
        a.excluded = new HashSet<>(Arrays.asList("unifiwirelessaggregate"));
        cycles(a, 20);
        assertEquals("the excluded aggregate kind is never marked", Arrays.asList("2:NOTEXIST"),
                a.changes);
    }

    private static void testForeignAdapterKindNeverMarked() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.known.put(15, platformOf(15, "UniFiSwitch", "vc host", "VMWARE"));
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 5);
        assertEquals("a resource of another adapter kind is never marked",
                Arrays.asList("2:NOTEXIST"), a.changes);
    }

    // -----------------------------------------------------------------------
    // Hooks and switches
    // -----------------------------------------------------------------------

    private static void testHookFailureMarksNothing() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        a.kindsReadFailure = new IllegalStateException("pak bug");
        a.onCollect(a.instance, a.resources());
        assertEquals("kindsReadThisCycle threw: nothing marked", 0, a.changes.size());
        assertTrue("and a WARN says so", a.log.contains(
                "kindsReadThisCycle() failed; no NOT_EXISTING marking this cycle"));
    }

    private static void testDisabledWithZeroThreshold() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 0;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 30);
        assertEquals("threshold 0: off", 0, a.changes.size());
    }

    private static void testOffWithoutDiscoverOnCollect() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.discover = false;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 5);
        assertEquals("no collect-path enumeration: nothing to diff, nothing marked", 0,
                a.changes.size());
    }

    private static void testNoAdapterCacheMarksNothing() throws Exception {
        TestAdapter a = unifi();
        a.threshold = 1;
        a.noCache = true;
        a.deliver("UniFiWorld", "w");
        a.deliver("UniFiSwitch", "a");
        cycles(a, 3);
        assertEquals("no platform resource list: nothing marked", 0, a.changes.size());
    }

    // -----------------------------------------------------------------------
    // Test adapter
    // -----------------------------------------------------------------------

    static final class Collector implements VcfCfCollector<Object> {
        TestAdapter owner;
        boolean failAll;
        boolean stopOnFirst;
        Exception rediscoverFailure;

        @Override
        public boolean needsRediscovery(Object config) {
            return rediscoverFailure != null;
        }

        @Override
        public void rediscover(Object config, ManagedHttpClient httpClient,
                ResourceConfig adapterInst, AdapterBase adapter) throws Exception {
            if (rediscoverFailure != null) throw rediscoverFailure;
        }

        @Override
        public void collect(Object config, ManagedHttpClient httpClient, ResourceConfig rc,
                List<MetricData> out, AdapterBase adapter) throws Exception {
            owner.collected.add(rc.getResourceId());
            if (stopOnFirst) owner.onStopCollection();
            if (failAll) throw new IOException("Login failed (cached)");
        }
    }

    public static class TestAdapter extends VcfCfAdapter<Object> {
        Collector collector;
        ResourceConfig instance;
        LogCapture log;
        boolean discover;
        boolean noCache;
        int threshold;
        Exception enumerationFailure;
        RuntimeException kindsReadFailure;
        Set<String> kindsRead;
        Set<String> excluded;
        /** The platform's resources by id (monitoring unless in {@link #stopped}). */
        Map<Integer, ResourceConfig> known;
        Set<Integer> stopped;
        /** What enumerateResources delivers: fresh configs, not the platform's. */
        List<ResourceKey> delivering;
        List<String> changes;
        List<ResourceConfig> changedConfigs;
        List<Integer> collected;
        Map<Integer, ResourceStatusEnum> statuses;

        void deliver(String kind, String id) {
            delivering.add(key(kind, id));
        }

        void undeliver(String kind, String id) {
            delivering.remove(key(kind, id));
        }

        /** What the platform hands onCollect: its monitoring resources. */
        List<ResourceConfig> resources() {
            List<ResourceConfig> out = new ArrayList<>();
            for (Map.Entry<Integer, ResourceConfig> e : known.entrySet()) {
                if (!stopped.contains(e.getKey())) out.add(e.getValue());
            }
            return out;
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
            if (enumerationFailure != null) throw enumerationFailure;
            for (ResourceKey k : delivering) {
                ResourceKey copy = key(k.getResourceKind(), k.getIdentifiers().get(0).getValue());
                sink.accept(new ResourceConfig(copy));
            }
        }

        @Override
        protected int notExistingMissedCycles() {
            return threshold;
        }

        @Override
        protected Set<String> kindsReadThisCycle() {
            if (kindsReadFailure != null) throw kindsReadFailure;
            return kindsRead;
        }

        @Override
        protected Set<String> notExistingExcludedKinds() {
            return excluded;
        }

        @Override
        Collection<ResourceConfig> platformMonitoringResources() {
            return noCache ? null : resources();
        }

        @Override
        Collection<ResourceConfig> platformStoppedResources() {
            if (noCache) return null;
            List<ResourceConfig> out = new ArrayList<>();
            for (Integer id : stopped) out.add(known.get(id));
            return out;
        }

        @Override
        public void changeResourceState(ResourceConfig rc, DiscoveryResult.StateChangeEnum st) {
            changes.add(rc.getResourceId() + ":" + st);
            changedConfigs.add(rc);
        }

        @Override
        public ResourceConfig getAdapterInstResource() { return instance; }

        @Override
        public boolean setResourceStatus(ResourceConfig rc, ResourceStatusEnum st) {
            statuses.put(rc.getResourceId(), st);
            return true;
        }

        @Override
        public boolean setResourceStatus(ResourceConfig rc, ResourceStatusEnum st, String msg) {
            statuses.put(rc.getResourceId(), st);
            return true;
        }
    }

    /**
     * A UniFi-shaped adapter: the platform knows the world (id 100) and
     * switches a (1) and b (2); nothing is delivered until the test says so.
     * Threshold 12, discoverOnCollect on, and opted in: the pak declares
     * UniFiWorld and UniFiSwitch read in full each cycle. Tests of the
     * default set {@code kindsRead = null}.
     */
    private static TestAdapter unifi() throws Exception {
        TestAdapter a = allocate(TestAdapter.class);
        setField(VcfCfAdapter.class, a, "abortRequested", new AtomicBoolean(false));
        a.log = LogCapture.create("INFO");
        Class<?> fi = Class.forName("com.vmware.vrops.logging.AdapterLoggerFactory");
        Object factory = Proxy.newProxyInstance(fi.getClassLoader(), new Class<?>[] {fi},
                (p, m, args) -> m.getName().equals("getLogger") ? a.log.logger() : null);
        setField(AdapterBase.class, a, "adapterLoggerFactory", factory);
        a.collector = new Collector();
        a.collector.owner = a;
        a.instance = platform(9000, "unifi_instance", "UniFi account");
        a.discover = true;
        a.threshold = VcfCfAdapter.DEFAULT_NOT_EXISTING_MISSED_CYCLES;
        a.kindsRead = new HashSet<>(Arrays.asList("UniFiWorld", "UniFiSwitch"));
        a.known = new LinkedHashMap<>();
        a.known.put(100, platform(100, "UniFiWorld", "w"));
        a.known.put(1, platform(1, "UniFiSwitch", "a"));
        a.known.put(2, platform(2, "UniFiSwitch", "b"));
        a.stopped = new HashSet<>();
        a.delivering = new ArrayList<>();
        a.changes = new ArrayList<>();
        a.changedConfigs = new ArrayList<>();
        a.collected = new ArrayList<>();
        a.statuses = new LinkedHashMap<>();
        return a;
    }

    private static void cycles(TestAdapter a, int n) {
        for (int i = 0; i < n; i++) a.onCollect(a.instance, a.resources());
    }

    static ResourceKey key(String kind, String id) {
        return keyOf(kind, id, AK);
    }

    static ResourceKey keyOf(String kind, String id, String adapterKind) {
        ResourceKey k = new ResourceKey(id, kind, adapterKind);
        k.addIdentifier(new ResourceIdentifierConfig("id", id, true));
        return k;
    }

    /** A ResourceConfig as the platform holds it: key plus resource id. */
    static ResourceConfig platform(int id, String kind, String name) {
        return platformOf(id, kind, name, AK);
    }

    static ResourceConfig platformOf(int id, String kind, String name, String adapterKind) {
        return new ResourceConfig(keyOf(kind, name, adapterKind), id, UUID.randomUUID());
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
