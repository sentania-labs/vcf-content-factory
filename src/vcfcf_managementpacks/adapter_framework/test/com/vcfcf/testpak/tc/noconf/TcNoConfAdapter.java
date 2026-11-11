package com.vcfcf.testpak.tc.noconf;

import com.vcfcf.testpak.tc.TcPakAdapter;

/** Stand-in pak for {@code TestConnectionLoggingTest}: a pak that ships no conf/logging.properties. */
public class TcNoConfAdapter extends TcPakAdapter {

    @Override
    public Class<?> helper() { return Helper.class; }

    /** A helper class in the pak's own package. */
    public static final class Helper { }
}
