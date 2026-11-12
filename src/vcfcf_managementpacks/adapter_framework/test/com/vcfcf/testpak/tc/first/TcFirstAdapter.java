package com.vcfcf.testpak.tc.first;

import com.vcfcf.testpak.tc.TcPakAdapter;

/** Stand-in pak for {@code TestConnectionLoggingTest}: a first account: the Test Connection happens before any instance of the pak. */
public class TcFirstAdapter extends TcPakAdapter {

    @Override
    public Class<?> helper() { return Helper.class; }

    /** A helper class in the pak's own package. */
    public static final class Helper { }
}
