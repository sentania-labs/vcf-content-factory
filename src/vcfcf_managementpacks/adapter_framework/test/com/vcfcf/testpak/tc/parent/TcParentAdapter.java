package com.vcfcf.testpak.tc.parent;

import com.vcfcf.testpak.tc.TcPakAdapter;

/** Stand-in pak for {@code TestConnectionLoggingTest}: a pak whose conf/logging.properties has a parent-package key (com.vcfcf.testpak.tc) covering the other stand-in paks. */
public class TcParentAdapter extends TcPakAdapter {

    @Override
    public Class<?> helper() { return Helper.class; }

    /** A helper class in the pak's own package. */
    public static final class Helper { }
}
