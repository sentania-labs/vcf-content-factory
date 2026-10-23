package com.vcfcf.adapter;

import com.integrien.alive.common.adapter3.Logger;
import com.vcfcf.adapter.stitch.SuiteApiStitchClient;
import com.vcfcf.adapter.stitch.SuiteApiStitcher;
import com.vcfcf.testpak.debug.DebugPakAdapter;
import com.vcfcf.testpak.info.InfoPakAdapter;

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
import java.util.stream.Stream;

/**
 * {@link VcfCfAdapter#componentLogger(Class)} against the real SDK logger
 * factory ({@code AdapterLoggerFactoryImpl}) and log4j-core, writing a real
 * per-instance adapter log file (issues #224 and #228).
 *
 * <p>The SDK, read in bytecode: the factory names each logger
 * {@code "(<instanceId>) <name>"} and gives it the instance file appender at
 * the level that the adapter's {@code conf/logging.properties} (resolved from
 * the adapter jar name under {@code ADAPTER_HOME}; vendor paks ship
 * {@code <package>=INFO}) assigns to the bare {@code <name>}, else the
 * collector root level. {@code Logger.setLevel} changes only the logger's own
 * level, never that appender filter. So:
 * <ul>
 *   <li>#228: a framework helper logger named after its own class
 *       ({@code com.vcfcf.adapter.stitch.SuiteApiStitcher}) falls outside the
 *       pak's package entry and its INFO never reaches the instance log,
 *       while the pak's own classes do. The fix names it under the adapter
 *       class.</li>
 *   <li>#224: {@code setLevel(INFO)} on every lookup lowered a DEBUG level
 *       the operator set, so DEBUG lines were dropped. The fix only raises a
 *       level that is below INFO.</li>
 * </ul>
 *
 * <p>Runs in its own JVM: it points log4j at a test configuration (root WARN
 * with a rolling file appender, as on a collector) before log4j initializes.
 * Needs log4j-core at runtime (for example
 * {@code adapter_runtime/lib/mpb_adapter-*.jar}); SKIPPED without it.
 */
public class ComponentLoggerTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;
    private static int skipped = 0;

    private static Path tmp;

    public static void main(String[] args) throws Exception {
        if (!log4jCorePresent()) {
            skip("all: log4j-core not on the runtime classpath"
                    + " (add a jar carrying it, e.g. adapter_runtime/lib/*)");
            report();
            return;
        }
        tmp = Files.createTempDirectory("vcfcf-complog-");
        try {
            setUpLog4j();
            testFrameworkHelperReachesInstanceLog();
            testOperatorDebugLevelSurvivesLookups();
            testInfoFloorWithoutPakEntry();
            testLoggerNaming();
        } finally {
            deleteTree(tmp);
        }
        report();
    }

    // -----------------------------------------------------------------------
    // #228
    // -----------------------------------------------------------------------

    private static void testFrameworkHelperReachesInstanceLog() throws Exception {
        InfoPakAdapter a = adapter(InfoPakAdapter.class, "InfoPak", 41);
        a.info("T228-adapter-info");
        a.component(InfoPakAdapter.Helper.class).info("T228-pak-helper-info");
        a.component(SuiteApiStitcher.class).info("T228-framework-helper-info");
        SuiteApiStitchClient.builder().adapter(a)
                .explicitCredentials("localhost", "svc-user", "svc-pass")
                .logger(a.component(SuiteApiStitcher.class))
                .build();
        String log = instanceLog("InfoPak", 41);
        assertTrue("adapter INFO reaches the instance log", log.contains("T228-adapter-info"));
        assertTrue("pak helper INFO reaches the instance log", log.contains("T228-pak-helper-info"));
        assertTrue("framework helper INFO reaches the instance log (#228)",
                log.contains("T228-framework-helper-info"));
        assertTrue("SuiteApiStitchClient configure line reaches the instance log (#228)",
                log.contains("credential mechanism=explicit"));
    }

    // -----------------------------------------------------------------------
    // #224
    // -----------------------------------------------------------------------

    private static void testOperatorDebugLevelSurvivesLookups() throws Exception {
        DebugPakAdapter a = adapter(DebugPakAdapter.class, "DebugPak", 43);
        a.info("T224-adapter-info");
        Logger first = a.component(DebugPakAdapter.Helper.class);
        first.debug("T224-debug-first-lookup");
        Logger second = a.component(DebugPakAdapter.Helper.class);
        second.debug("T224-debug-second-lookup");
        first.debug("T224-debug-old-handle");
        a.component(DebugPakAdapter.class).debug("T224-adapter-class-debug");
        a.component(SuiteApiStitcher.class).debug("T224-framework-debug");
        String log = instanceLog("DebugPak", 43);
        assertTrue("DEBUG on the first lookup (#224)", log.contains("T224-debug-first-lookup"));
        assertTrue("DEBUG after a second lookup (#224)", log.contains("T224-debug-second-lookup"));
        assertTrue("an earlier handle still logs DEBUG (#224)", log.contains("T224-debug-old-handle"));
        assertTrue("adapter-class DEBUG after logInfo created the adapter logger",
                log.contains("T224-adapter-class-debug"));
        assertTrue("framework helper inherits the pak's DEBUG (#228 naming)",
                log.contains("T224-framework-debug"));
    }

    /** Without any pak entry the floor still lifts the logger to INFO. */
    private static void testInfoFloorWithoutPakEntry() throws Exception {
        InfoPakAdapter a = adapter(InfoPakAdapter.class, "NoConfPak", 44);
        Logger l = a.component(InfoPakAdapter.Helper.class);
        assertTrue("INFO enabled on the logger with root at WARN", l.isInfoEnabled());
        assertFalse("DEBUG not enabled with root at WARN", l.isDebugEnabled());
    }

    // -----------------------------------------------------------------------
    // Naming rule
    // -----------------------------------------------------------------------

    private static void testLoggerNaming() {
        assertEquals("pak class keeps its own name",
                "com.vcfcf.testpak.info.InfoPakAdapter$Helper",
                VcfCfAdapter.componentLoggerName(InfoPakAdapter.class, InfoPakAdapter.Helper.class));
        assertEquals("adapter class keeps its own name",
                "com.vcfcf.testpak.info.InfoPakAdapter",
                VcfCfAdapter.componentLoggerName(InfoPakAdapter.class, InfoPakAdapter.class));
        assertEquals("framework class is named under the adapter class",
                "com.vcfcf.testpak.info.InfoPakAdapter.SuiteApiStitcher",
                VcfCfAdapter.componentLoggerName(InfoPakAdapter.class, SuiteApiStitcher.class));
        assertEquals("a JDK class is named under the adapter class too",
                "com.vcfcf.testpak.info.InfoPakAdapter.String",
                VcfCfAdapter.componentLoggerName(InfoPakAdapter.class, String.class));
        assertEquals("a pak subpackage keeps its own name",
                "com.vcfcf.testpak.info.sub.X",
                VcfCfAdapter.componentLoggerName("com.vcfcf.testpak.info.InfoPakAdapter",
                        "com.vcfcf.testpak.info", "com.vcfcf.testpak.info.sub", "com.vcfcf.testpak.info.sub.X"));
        assertEquals("a sibling package with a shared prefix is outside",
                "com.vcfcf.testpak.info.InfoPakAdapter.Y",
                VcfCfAdapter.componentLoggerName("com.vcfcf.testpak.info.InfoPakAdapter",
                        "com.vcfcf.testpak.info", "com.vcfcf.testpak.infox", "com.vcfcf.testpak.infox.Y"));
    }

    // -----------------------------------------------------------------------
    // Plumbing
    // -----------------------------------------------------------------------

    private static boolean log4jCorePresent() {
        try {
            Class.forName("org.apache.logging.log4j.core.LoggerContext", false,
                    ComponentLoggerTest.class.getClassLoader());
            return true;
        } catch (ClassNotFoundException | LinkageError e) {
            return false;
        }
    }

    /**
     * Collector-like log4j: root WARN to a rolling file (the SDK factory
     * refuses to build instance appenders unless the root has one), and the
     * per-adapter logging.properties files the SDK resolves from
     * ADAPTER_HOME.
     */
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
        Path adapters = tmp.resolve("adapters");
        System.setProperty("ADAPTER_HOME", adapters.toString());
        writeLoggingProperties(adapters, "InfoPak", "com.vcfcf.testpak.info = INFO");
        writeLoggingProperties(adapters, "DebugPak", "com.vcfcf.testpak.debug = DEBUG");
        Files.createDirectories(adapters.resolve("NoConfPak"));
    }

    private static void writeLoggingProperties(Path adapters, String pak, String line)
            throws IOException {
        Path conf = adapters.resolve(pak).resolve("conf");
        Files.createDirectories(conf);
        Files.write(conf.resolve("logging.properties"),
                ("MaxBackupIndex=1\n" + line + "\n").getBytes(StandardCharsets.UTF_8));
    }

    /**
     * An adapter of {@code cls} carrying a real SDK logger factory for pak
     * {@code pak} and instance {@code id}. The factory reads the pak's
     * logging.properties from the jar name on the context class loader, as
     * on a collector.
     */
    private static <T extends VcfCfAdapter<?>> T adapter(Class<T> cls, String pak, int id)
            throws Exception {
        Path dir = tmp.resolve("adapters").resolve(pak);
        URL jar = dir.resolve(pak + ".jar").toUri().toURL();
        Thread t = Thread.currentThread();
        ClassLoader old = t.getContextClassLoader();
        Object factory;
        try (URLClassLoader cl = new URLClassLoader(new URL[] {jar}, old)) {
            t.setContextClassLoader(cl);
            Class<?> fc = Class.forName("com.integrien.alive.common.adapter3.AdapterLoggerFactoryImpl");
            Constructor<?> c = fc.getDeclaredConstructor(String.class, String.class, Integer.class);
            c.setAccessible(true);
            factory = c.newInstance(pak, dir.toString(), id);
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

    private static String instanceLog(String pak, int id) throws IOException {
        String want = pak + "_" + id + ".log";
        try (Stream<Path> s = Files.walk(tmp)) {
            Path p = s.filter(x -> x.getFileName().toString().equals(want)).findFirst().orElse(null);
            if (p == null) return "";
            return new String(Files.readAllBytes(p), StandardCharsets.UTF_8);
        }
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
