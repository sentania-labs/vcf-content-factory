package com.vcfcf.adapter;

import com.integrien.alive.common.adapter3.Logger;
import com.vcfcf.testpak.tc.TcPakAdapter;
import com.vcfcf.testpak.tc.first.TcFirstAdapter;
import com.vcfcf.testpak.tc.noconf.TcNoConfAdapter;
import com.vcfcf.testpak.tc.old.TcOldAdapter;
import com.vcfcf.testpak.tc.second.TcSecondAdapter;

import java.io.File;
import java.io.IOException;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

/**
 * Test Connection must not shadow a pak's {@code conf/logging.properties}
 * (issue #322), against the real SDK logger factory
 * ({@code AdapterLoggerFactoryImpl}) and log4j-core, writing real
 * per-instance logs and a real {@code collector.log}.
 *
 * <p>On a Test Connection the factory has no instance appender and hands
 * back a bare-name logger. Before #322 {@code raiseToInfo} called
 * {@code setLevel(INFO)} on it, which ({@code Configurator.setLevel}) adds
 * an exact-name INFO entry under the pak's package entry. Every instance
 * created afterwards then got (a) its instance appender at INFO for that
 * name although the file says DEBUG, and (b) the name's instance lines
 * copied into {@code collector.log}. The control scenario
 * ({@link TcOldAdapter}) applies that old raise by hand and shows both
 * symptoms in this harness; the fixed scenarios show neither.
 *
 * <p>SDK line: with {@code AdapterLoggerConfig} present (9.0 and 9.1.1
 * SDKs, whose factory reads the file) every scenario runs. Without it
 * (8.18.7, whose factory never reads the file and needs its own logger
 * context for instance loggers) only the Test Connection path runs, and it
 * must raise exactly as before.
 *
 * <p>Runs in its own JVM: it points log4j at a test configuration (root
 * WARN to {@code collector.log}, as on a collector) before log4j
 * initializes. Needs log4j-core at runtime; SKIPPED without it.
 */
public class TestConnectionLoggingTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;
    private static int skipped = 0;

    private static Path tmp;
    private static Path adapters;

    public static void main(String[] args) throws Exception {
        if (!present("org.apache.logging.log4j.core.LoggerContext")) {
            skip("all: log4j-core not on the runtime classpath");
            report();
            return;
        }
        tmp = Files.createTempDirectory("vcfcf-tclog-");
        try {
            setUpLog4j();
            boolean nineX = present(VcfCfAdapter.ADAPTER_LOGGER_CONFIG_CLASS);
            System.out.println("SDK: " + (nineX
                    ? "AdapterLoggerConfig present (9.x factory reads logging.properties)"
                    : "no AdapterLoggerConfig (8.18 factory; logging.properties inert)"));
            if (nineX) {
                testControlReproducesBothSymptoms();
                testSecondAccountKeepsDebugAndNoCopy();
                testFirstAccountKeepsDebugAndNoCopy();
                testRaisedBareInfoNeverReachedCollectorLogUnderPakEntry();
                testNoPakFileRaisesAsBefore();
                testInstanceLoggerStillRaised();
            } else {
                testNoPakFileRaisesAsBefore();
                testPakFileIsIgnoredOn818();
            }
            testPropertiesFileLookup();
        } finally {
            deleteTree(tmp);
        }
        report();
    }

    // -----------------------------------------------------------------------
    // Scenarios
    // -----------------------------------------------------------------------

    /** The pre-#322 raise, by hand: both symptoms of the issue. */
    private static void testControlReproducesBothSymptoms() throws Exception {
        TcOldAdapter before = instance(TcOldAdapter.class, "TcOldPak", 61);
        before.info("OLD-before-info");
        TcOldAdapter tc = testConnection(TcOldAdapter.class, "TcOldPak", true);
        Logger adapterBare = tc.component(TcOldAdapter.class);
        Logger helperBare = tc.component(tc.helper());
        // What raiseToInfo did before #322, unconditionally on these names.
        adapterBare.setLevel(Logger.CustomLevel.INFO);
        helperBare.setLevel(Logger.CustomLevel.INFO);
        TcOldAdapter after = instance(TcOldAdapter.class, "TcOldPak", 62);
        after.component(after.helper()).debug("OLD-helper-debug");
        after.component(TcOldAdapter.class).debug("OLD-adapter-debug");
        after.info("OLD-adapter-info");
        String log = instanceLog("TcOldPak", 62);
        assertFalse("control: helper DEBUG lost after a raised Test Connection (#322 symptom a)",
                log.contains("OLD-helper-debug"));
        assertFalse("control: adapter-class DEBUG lost (#322 symptom a)",
                log.contains("OLD-adapter-debug"));
        assertTrue("control: adapter INFO still in the instance log", log.contains("OLD-adapter-info"));
        assertTrue("control: instance INFO copied into collector.log (#322 symptom b)",
                collectorLog().contains("OLD-adapter-info"));
    }

    /** An instance already loaded the pak entry; Test Connection; a new account. */
    private static void testSecondAccountKeepsDebugAndNoCopy() throws Exception {
        TcSecondAdapter first = instance(TcSecondAdapter.class, "TcSecondPak", 71);
        first.info("S2-first-info");
        TcSecondAdapter tc = testConnection(TcSecondAdapter.class, "TcSecondPak", true);
        tc.info("S2-tc-info");
        tc.warn("S2-tc-warn");
        Logger tcHelper = tc.component(tc.helper());
        tcHelper.info("S2-tc-helper-info");
        assertFalse("second account: no bare-name entry for the adapter class after Test Connection",
                exactEntry(TcSecondAdapter.class.getName()));
        assertFalse("second account: no bare-name entry for the helper after Test Connection",
                exactEntry(tc.helper().getName()));
        TcSecondAdapter next = instance(TcSecondAdapter.class, "TcSecondPak", 72);
        next.component(next.helper()).debug("S2-helper-debug");
        next.component(TcSecondAdapter.class).debug("S2-adapter-debug");
        next.info("S2-adapter-info");
        String log = instanceLog("TcSecondPak", 72);
        String collector = collectorLog();
        assertTrue("second account: helper DEBUG kept (#322 a fixed)", log.contains("S2-helper-debug"));
        assertTrue("second account: adapter-class DEBUG kept (#322 a fixed)",
                log.contains("S2-adapter-debug"));
        assertTrue("second account: adapter INFO in the instance log", log.contains("S2-adapter-info"));
        assertFalse("second account: instance INFO not copied into collector.log (#322 b fixed)",
                collector.contains("S2-adapter-info"));
        assertTrue("second account: Test Connection WARN reaches collector.log",
                collector.contains("S2-tc-warn"));
        assertFalse("second account: Test Connection INFO does not reach collector.log (as in 1.0.25+)",
                collector.contains("S2-tc-info") || collector.contains("S2-tc-helper-info"));
    }

    /** No instance yet, so the pak entry is not loaded: Test Connection first. */
    private static void testFirstAccountKeepsDebugAndNoCopy() throws Exception {
        TcFirstAdapter tc = testConnection(TcFirstAdapter.class, "TcFirstPak", true);
        assertFalse("first account: the pak entry is not loaded before the first instance",
                exactEntry("com.vcfcf.testpak.tc.first"));
        tc.info("S1-tc-info");
        tc.warn("S1-tc-warn");
        tc.component(tc.helper()).info("S1-tc-helper-info");
        assertFalse("first account: no bare-name entry for the adapter class",
                exactEntry(TcFirstAdapter.class.getName()));
        assertFalse("first account: no bare-name entry for the helper",
                exactEntry(tc.helper().getName()));
        TcFirstAdapter inst = instance(TcFirstAdapter.class, "TcFirstPak", 81);
        inst.component(inst.helper()).debug("S1-helper-debug");
        inst.component(TcFirstAdapter.class).debug("S1-adapter-debug");
        inst.info("S1-adapter-info");
        String log = instanceLog("TcFirstPak", 81);
        String collector = collectorLog();
        assertTrue("first account: helper DEBUG kept", log.contains("S1-helper-debug"));
        assertTrue("first account: adapter-class DEBUG kept", log.contains("S1-adapter-debug"));
        assertFalse("first account: instance INFO not copied into collector.log",
                collector.contains("S1-adapter-info"));
        assertTrue("first account: Test Connection WARN reaches collector.log",
                collector.contains("S1-tc-warn"));
    }

    /**
     * The cost of not raising: under the pak entry a bare-name INFO line
     * never reached collector.log even when raised; WARN always does.
     */
    private static void testRaisedBareInfoNeverReachedCollectorLogUnderPakEntry() throws Exception {
        TcSecondAdapter tc = testConnection(TcSecondAdapter.class, "TcSecondPak", true);
        Logger raised = tc.component(TcSecondAdapter.class);
        raised.setLevel(Logger.CustomLevel.INFO);   // the old raise
        raised.info("RAW-raised-info");
        raised.warn("RAW-raised-warn");
        String collector = collectorLog();
        assertFalse("a raised bare INFO under the pak entry is not in collector.log",
                collector.contains("RAW-raised-info"));
        assertTrue("a bare WARN under the pak entry is in collector.log",
                collector.contains("RAW-raised-warn"));
    }

    /** A pak with no file: Test Connection raises as before (unchanged). */
    private static void testNoPakFileRaisesAsBefore() throws Exception {
        TcNoConfAdapter tc = testConnection(TcNoConfAdapter.class, "TcNoConfPak", true);
        Logger helper = tc.component(tc.helper());
        assertTrue("no pak file: the Test Connection helper logger is raised to INFO",
                helper.isInfoEnabled());
        assertTrue("no pak file: the raise added the bare-name entry, as before",
                exactEntry(tc.helper().getName()));
        tc.info("NC-tc-info");
        assertTrue("no pak file: Test Connection INFO reaches collector.log, as before",
                collectorLog().contains("NC-tc-info"));
    }

    /** 8.18: the factory never reads the file, so the raise is unchanged. */
    private static void testPakFileIsIgnoredOn818() throws Exception {
        TcSecondAdapter tc = testConnection(TcSecondAdapter.class, "TcSecondPak", true);
        Logger helper = tc.component(tc.helper());
        assertFalse("8.18: governedByPakLoggingEntry is false with a pak file present",
                VcfCfAdapter.governedByPakLoggingEntry(helper, TcSecondAdapter.class));
        assertTrue("8.18: the Test Connection helper logger is raised to INFO, as before",
                helper.isInfoEnabled());
        assertTrue("8.18: the raise added the bare-name entry, as before",
                exactEntry(tc.helper().getName()));
    }

    /** An instance logger with no pak entry is still lifted (#224 floor). */
    private static void testInstanceLoggerStillRaised() throws Exception {
        TcNoConfAdapter a = instance(TcNoConfAdapter.class, "TcNoConfPak", 91);
        Logger l = a.component(a.helper());
        assertTrue("instance logger without a pak entry: INFO enabled (floor kept)", l.isInfoEnabled());
        assertFalse("instance logger: not treated as governed by a pak entry",
                VcfCfAdapter.governedByPakLoggingEntry(l, TcNoConfAdapter.class));
    }

    private static void testPropertiesFileLookup() throws Exception {
        URL jar = adapters.resolve("TcSecondPak").resolve("TcSecondPak.jar").toUri().toURL();
        URL lib = adapters.resolve("TcSecondPak").resolve("lib").resolve("vcfcf-adapter-base.jar")
                .toUri().toURL();
        try (URLClassLoader cl = new URLClassLoader(new URL[] {lib, jar})) {
            File f = VcfCfAdapter.pakLoggingPropertiesFile(cl, null, adapters.toString());
            assertEquals("file found from the shortest context class loader URL",
                    adapters.resolve("TcSecondPak").resolve("conf").resolve("logging.properties")
                            .toString(), f == null ? null : f.getPath());
            assertTrue("no ADAPTER_HOME, no file",
                    VcfCfAdapter.pakLoggingPropertiesFile(cl, null, null) == null);
        }
        assertTrue("a class loaded from a directory names no file",
                VcfCfAdapter.pakLoggingPropertiesFile(null, TcSecondAdapter.class,
                        adapters.toString()) == null);
        assertEquals("MaxBackupIndex is not a logger key", "[com.vcfcf.testpak.tc.second]",
                VcfCfAdapter.pakLoggingProperties(adapters.resolve("TcSecondPak").resolve("conf")
                        .resolve("logging.properties").toFile()).stringPropertyNames().toString());
    }

    // -----------------------------------------------------------------------
    // Plumbing
    // -----------------------------------------------------------------------

    private static boolean present(String cls) {
        try {
            Class.forName(cls, false, TestConnectionLoggingTest.class.getClassLoader());
            return true;
        } catch (ClassNotFoundException | LinkageError e) {
            return false;
        }
    }

    private static void setUpLog4j() throws IOException {
        Path cfg = tmp.resolve("log4j2-test.properties");
        String collector = tmp.resolve("collector.log").toString().replace('\\', '/');
        Files.write(cfg, String.join("\n",
                "status = error",
                "appender.r.type = RollingFile",
                "appender.r.name = collectorlog",
                "appender.r.fileName = " + collector,
                "appender.r.filePattern = " + collector + ".%i",
                "appender.r.layout.type = PatternLayout",
                "appender.r.layout.pattern = %p [%c] %m%n",
                "appender.r.policies.type = Policies",
                "appender.r.policies.size.type = SizeBasedTriggeringPolicy",
                "appender.r.policies.size.size = 10MB",
                "rootLogger.level = WARN",
                "rootLogger.appenderRef.r.ref = collectorlog",
                "").getBytes(StandardCharsets.UTF_8));
        System.setProperty("log4j2.configurationFile", cfg.toString());
        System.setProperty("ALIVE_BASE", tmp.toString());
        adapters = tmp.resolve("adapters");
        System.setProperty("ADAPTER_HOME", adapters.toString());
        writeLoggingProperties("TcOldPak", "com.vcfcf.testpak.tc.old = DEBUG");
        writeLoggingProperties("TcSecondPak", "com.vcfcf.testpak.tc.second = DEBUG");
        writeLoggingProperties("TcFirstPak", "com.vcfcf.testpak.tc.first = DEBUG");
        Files.createDirectories(adapters.resolve("TcNoConfPak"));
    }

    private static void writeLoggingProperties(String pak, String line) throws IOException {
        Path conf = adapters.resolve(pak).resolve("conf");
        Files.createDirectories(conf);
        Files.write(conf.resolve("logging.properties"),
                ("MaxBackupIndex=1\n" + line + "\n").getBytes(StandardCharsets.UTF_8));
    }

    /** An adapter with a real instance factory (live-collection path). */
    private static <T extends TcPakAdapter> T instance(Class<T> cls, String pak, int id)
            throws Exception {
        Path dir = adapters.resolve(pak);
        return withFactory(cls, pak, new Object[] {pak, dir.toString(), id});
    }

    /**
     * An adapter on the Test Connection path: the factory has no instance
     * appender. withContextLoader: the thread context class loader is the
     * pak's (URL of {@code <ADAPTER_HOME>/<pak>/<pak>.jar}) while it runs,
     * as when the collector calls the adapter.
     */
    private static <T extends TcPakAdapter> T testConnection(Class<T> cls, String pak,
            boolean withContextLoader) throws Exception {
        T a = withFactory(cls, pak, new Object[] {null, null, null});
        if (withContextLoader) {
            URL jar = adapters.resolve(pak).resolve(pak + ".jar").toUri().toURL();
            Thread.currentThread().setContextClassLoader(
                    new URLClassLoader(new URL[] {jar}, TestConnectionLoggingTest.class.getClassLoader()));
        }
        return a;
    }

    private static <T extends TcPakAdapter> T withFactory(Class<T> cls, String pak, Object[] ctorArgs)
            throws Exception {
        Path dir = adapters.resolve(pak);
        URL jar = dir.resolve(pak + ".jar").toUri().toURL();
        Thread t = Thread.currentThread();
        ClassLoader old = TestConnectionLoggingTest.class.getClassLoader();
        Object factory;
        try (URLClassLoader cl = new URLClassLoader(new URL[] {jar}, old)) {
            t.setContextClassLoader(cl);
            Class<?> fc = Class.forName("com.integrien.alive.common.adapter3.AdapterLoggerFactoryImpl");
            Constructor<?> c = fc.getDeclaredConstructor(String.class, String.class, Integer.class);
            c.setAccessible(true);
            factory = c.newInstance(ctorArgs);
        } finally {
            t.setContextClassLoader(old);
        }
        T a = allocate(cls);
        Field f = com.integrien.alive.common.adapter3.AdapterBase.class
                .getDeclaredField("adapterLoggerFactory");
        f.setAccessible(true);
        f.set(a, factory);
        return a;
    }

    /** True when the live log4j configuration has an entry of exactly name. */
    @SuppressWarnings("unchecked")
    private static boolean exactEntry(String name) throws Exception {
        Class<?> lm = Class.forName("org.apache.logging.log4j.LogManager");
        Object ctx = lm.getMethod("getContext", boolean.class).invoke(null, false);
        Object config = Class.forName("org.apache.logging.log4j.core.LoggerContext")
                .getMethod("getConfiguration").invoke(ctx);
        Map<String, ?> loggers = (Map<String, ?>) Class.forName(
                "org.apache.logging.log4j.core.config.Configuration")
                .getMethod("getLoggers").invoke(config);
        return loggers.containsKey(name);
    }

    private static String instanceLog(String pak, int id) throws IOException {
        String want = pak + "_" + id + ".log";
        try (Stream<Path> s = Files.walk(tmp)) {
            Path p = s.filter(x -> x.getFileName().toString().equals(want)).findFirst().orElse(null);
            if (p == null) return "";
            return new String(Files.readAllBytes(p), StandardCharsets.UTF_8);
        }
    }

    private static String collectorLog() throws IOException {
        Path p = tmp.resolve("collector.log");
        return Files.isRegularFile(p) ? new String(Files.readAllBytes(p), StandardCharsets.UTF_8) : "";
    }

    @SuppressWarnings("unchecked")
    private static <T> T allocate(Class<T> cls) throws Exception {
        Field f = Class.forName("sun.misc.Unsafe").getDeclaredField("theUnsafe");
        f.setAccessible(true);
        Object unsafe = f.get(null);
        Method m = unsafe.getClass().getMethod("allocateInstance", Class.class);
        return (T) m.invoke(unsafe, cls);
    }

    private static void deleteTree(Path root) {
        try (Stream<Path> s = Files.walk(root)) {
            s.sorted((x, y) -> y.getNameCount() - x.getNameCount())
                    .map(Path::toFile).forEach(File::delete);
        } catch (IOException ignored) {
            // best effort
        }
    }

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
