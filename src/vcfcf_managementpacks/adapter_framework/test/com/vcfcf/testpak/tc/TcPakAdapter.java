package com.vcfcf.testpak.tc;

import com.integrien.alive.common.adapter3.Logger;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.spi.VcfCfCollector;
import com.vcfcf.adapter.spi.VcfCfTester;

/**
 * Base of the stand-in paks for {@code TestConnectionLoggingTest} (issue
 * #322). Each subclass sits in its own package, so each plays a pak with
 * its own {@code conf/logging.properties} entry in one log4j configuration.
 * Exposes the protected logging surface.
 */
public abstract class TcPakAdapter extends VcfCfAdapter<Object> {

    @Override
    protected void configureAdapter(ResourceStatus s, ResourceConfig rc) { }

    @Override
    @SuppressWarnings("rawtypes")
    protected VcfCfTester getTester() { return null; }

    @Override
    @SuppressWarnings("rawtypes")
    protected VcfCfCollector getCollector() { return null; }

    /** {@link #componentLogger(Class)}, public for the test. */
    public Logger component(Class<?> c) {
        return componentLogger(c);
    }

    /** {@link #logInfo(String)}, public for the test. */
    public void info(String m) {
        logInfo(m);
    }

    /** {@link #logWarn(String)}, public for the test. */
    public void warn(String m) {
        logWarn(m);
    }

    /** The helper class of the subclass's package. */
    public abstract Class<?> helper();
}
