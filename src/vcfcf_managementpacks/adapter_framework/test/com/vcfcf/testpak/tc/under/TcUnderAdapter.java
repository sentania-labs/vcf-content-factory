package com.vcfcf.testpak.tc.under;

import com.vcfcf.testpak.tc.TcPakAdapter;

/** Stand-in pak for {@code TestConnectionLoggingTest}: a pak with its own conf/logging.properties entry, under another pak's parent-package entry. */
public class TcUnderAdapter extends TcPakAdapter {

    @Override
    public Class<?> helper() { return Helper.class; }

    /** A helper class in the pak's own package. */
    public static final class Helper { }
}
