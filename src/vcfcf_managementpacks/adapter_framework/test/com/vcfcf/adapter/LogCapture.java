package com.vcfcf.adapter;

import com.integrien.alive.common.adapter3.Logger;

import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Test helper: an SDK {@link Logger} whose output is captured in memory.
 *
 * <p>The SDK {@code Logger} wraps a log4j-api logger, but its message only
 * reaches log4j-core ({@code forcedLog} looks up the {@code LoggerConfig} by
 * name in the current {@code LoggerContext}), so capturing text needs
 * log4j-core at runtime. Everything here is reflection so the test sources
 * still compile against the SDK and framework jars only; callers check
 * {@link #available()} first and SKIP when log4j-core is absent (any jar
 * carrying it works, for example the gitignored
 * {@code adapter_runtime/lib/mpb_adapter-*.jar}).
 *
 * <p>Each capture gets its own logger name and a non-additive
 * {@code LoggerConfig} holding one recording appender, so captures never see
 * each other's lines. The level threshold (default INFO) decides both
 * {@code isXxxEnabled} answers and what is recorded.
 */
public final class LogCapture {

    private static final AtomicInteger SEQ = new AtomicInteger();

    private final List<String> lines = Collections.synchronizedList(new ArrayList<>());
    private final List<Throwable> thrown = Collections.synchronizedList(new ArrayList<>());
    private final Logger logger;
    private volatile Object threshold;

    /** True when log4j-api and log4j-core are on the runtime classpath. */
    public static boolean available() {
        try {
            Class.forName("org.apache.logging.log4j.Logger");
            Class.forName("org.apache.logging.log4j.core.LoggerContext");
            return true;
        } catch (ClassNotFoundException | LinkageError e) {
            return false;
        }
    }

    /** A capture at INFO. */
    public static LogCapture create() throws Exception {
        return new LogCapture("INFO");
    }

    /** A capture at the named log4j level (for example {@code "DEBUG"}). */
    public static LogCapture create(String level) throws Exception {
        return new LogCapture(level);
    }

    private LogCapture(String level) throws Exception {
        Class<?> levelCls = Class.forName("org.apache.logging.log4j.Level");
        this.threshold = levelCls.getField(level).get(null);
        String name = "vcfcf.test.capture." + SEQ.incrementAndGet();

        // Recording appender (interface proxy over core Appender).
        Class<?> appenderCls = Class.forName("org.apache.logging.log4j.core.Appender");
        Object appender = Proxy.newProxyInstance(appenderCls.getClassLoader(),
                new Class<?>[] {appenderCls}, (p, m, a) -> {
                    switch (m.getName()) {
                        case "append": record(a[0]); return null;
                        case "getName": return name + ".appender";
                        case "isStarted": return true;
                        case "isStopped": return false;
                        case "ignoreExceptions": return false;
                        case "hashCode": return System.identityHashCode(p);
                        case "equals": return p == a[0];
                        case "toString": return name + ".appender";
                        default:
                            if (m.getReturnType() == boolean.class) return false;
                            return null;
                    }
                });

        // Non-additive LoggerConfig carrying only that appender.
        Class<?> lmCls = Class.forName("org.apache.logging.log4j.LogManager");
        Object ctx = lmCls.getMethod("getContext", boolean.class).invoke(null, false);
        Object config = ctx.getClass().getMethod("getConfiguration").invoke(ctx);
        Class<?> lcCls = Class.forName("org.apache.logging.log4j.core.config.LoggerConfig");
        Object all = levelCls.getField("ALL").get(null);
        Object lc = lcCls.getConstructor(String.class, levelCls, boolean.class)
                .newInstance(name, all, false);
        Class<?> filterCls = Class.forName("org.apache.logging.log4j.core.Filter");
        lcCls.getMethod("addAppender", appenderCls, levelCls, filterCls)
                .invoke(lc, appender, null, null);
        Class<?> cfgCls = Class.forName("org.apache.logging.log4j.core.config.Configuration");
        cfgCls.getMethod("addLogger", String.class, lcCls).invoke(config, name, lc);
        ctx.getClass().getMethod("updateLoggers").invoke(ctx);

        // log4j-api Logger proxy: level checks follow the threshold.
        Class<?> apiLogger = Class.forName("org.apache.logging.log4j.Logger");
        Method moreSpecific = levelCls.getMethod("isMoreSpecificThan", levelCls);
        Object proxy = Proxy.newProxyInstance(apiLogger.getClassLoader(),
                new Class<?>[] {apiLogger}, (p, m, a) -> {
                    String n = m.getName();
                    if (n.equals("getName")) return name;
                    if (n.equals("getLevel")) return threshold;
                    if (n.equals("isEnabled") && a != null && a.length >= 1
                            && levelCls.isInstance(a[0])) {
                        return (Boolean) moreSpecific.invoke(a[0], threshold);
                    }
                    if (n.startsWith("is") && n.endsWith("Enabled")
                            && m.getReturnType() == boolean.class) {
                        String lv = n.substring(2, n.length() - "Enabled".length())
                                .toUpperCase(java.util.Locale.ROOT);
                        if (lv.equals("WARNING")) lv = "WARN";
                        try {
                            Object l = levelCls.getField(lv).get(null);
                            return (Boolean) moreSpecific.invoke(l, threshold);
                        } catch (NoSuchFieldException e) {
                            return false;
                        }
                    }
                    if (m.getReturnType() == boolean.class) return false;
                    return null;
                });
        java.lang.reflect.Constructor<Logger> c = Logger.class.getDeclaredConstructor(apiLogger);
        c.setAccessible(true);
        this.logger = c.newInstance(proxy);
    }

    private void record(Object event) {
        try {
            Object level = event.getClass().getMethod("getLevel").invoke(event);
            Object msg = event.getClass().getMethod("getMessage").invoke(event);
            String text = (String) msg.getClass().getMethod("getFormattedMessage").invoke(msg);
            Throwable t = (Throwable) event.getClass().getMethod("getThrown").invoke(event);
            lines.add(level + " " + text + (t == null ? "" : " [thrown " + t.getClass().getSimpleName() + "]"));
            if (t != null) thrown.add(t);
        } catch (ReflectiveOperationException e) {
            lines.add("CAPTURE-ERROR " + e);
        }
    }

    /** The SDK logger to hand to the code under test. */
    public Logger logger() {
        return logger;
    }

    /** Captured lines as {@code "<LEVEL> <message>[ [thrown X]]"}, in order. */
    public List<String> lines() {
        synchronized (lines) {
            return new ArrayList<>(lines);
        }
    }

    /** Throwables attached to captured lines, in order. */
    public List<Throwable> thrown() {
        synchronized (thrown) {
            return new ArrayList<>(thrown);
        }
    }

    /** Number of captured lines at {@code level} (for example {@code "WARN"}). */
    public int count(String level) {
        int n = 0;
        for (String l : lines()) if (l.startsWith(level + " ")) n++;
        return n;
    }

    /** True if any captured line contains {@code text}. */
    public boolean contains(String text) {
        for (String l : lines()) if (l.contains(text)) return true;
        return false;
    }

    /** Forget everything captured so far. */
    public void clear() {
        lines.clear();
        thrown.clear();
    }
}
