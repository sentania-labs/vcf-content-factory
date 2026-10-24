package com.vcfcf.testpak.info;

import com.integrien.alive.common.adapter3.Logger;
import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.config.ResourceConfig;
import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.spi.VcfCfCollector;
import com.vcfcf.adapter.spi.VcfCfTester;

/**
 * Stand-in pak adapter for {@code ComponentLoggerTest}: its package plays a
 * pak whose {@code conf/logging.properties} sets the package to INFO, the
 * way vendor paks ship it. Exposes the protected logging surface.
 */
public class InfoPakAdapter extends VcfCfAdapter<Object> {

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

    /** A helper class in the pak's own package. */
    public static final class Helper { }
}
