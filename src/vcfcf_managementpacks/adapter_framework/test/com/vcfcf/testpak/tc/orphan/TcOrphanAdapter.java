package com.vcfcf.testpak.tc.orphan;

import com.vcfcf.testpak.tc.TcPakAdapter;

/** Stand-in pak for {@code TestConnectionLoggingTest}: a pak that ships no conf/logging.properties, under another pak's parent-package entry. */
public class TcOrphanAdapter extends TcPakAdapter {

    @Override
    public Class<?> helper() { return Helper.class; }

    /** A helper class in the pak's own package. */
    public static final class Helper { }
}
