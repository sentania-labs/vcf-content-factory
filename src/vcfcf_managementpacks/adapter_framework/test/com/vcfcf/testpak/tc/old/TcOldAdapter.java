package com.vcfcf.testpak.tc.old;

import com.vcfcf.testpak.tc.TcPakAdapter;

/** Stand-in pak for {@code TestConnectionLoggingTest}: the pre-#322 raise, applied by the test itself (the control). */
public class TcOldAdapter extends TcPakAdapter {

    @Override
    public Class<?> helper() { return Helper.class; }

    /** A helper class in the pak's own package. */
    public static final class Helper { }
}
