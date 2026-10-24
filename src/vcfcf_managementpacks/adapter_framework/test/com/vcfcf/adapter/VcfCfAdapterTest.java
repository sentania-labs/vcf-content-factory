package com.vcfcf.adapter;

import java.util.ArrayList;
import java.util.List;

/**
 * Lightweight unit tests for {@link VcfCfAdapter#applyBcMirrorTransport}
 * (the DEF-005 BC-mirror transport fix), the FIPS-mode cluster-truststore
 * transport ({@link VcfCfAdapter#applyClusterTruststoreTransport}, issue #215),
 * and {@link VcfCfAdapter#insecureSslContext()} (issue #82 hostname-verification
 * fix).
 *
 * <p>No JUnit required — call via {@code main()}. Covers:
 * <ol>
 *   <li>Non-FIPS (default) mode: {@code applyBcMirrorTransport} — the helper
 *       {@link VcfCfAdapter#openPlatformConnection(String)} delegates to for
 *       its trust/hostname wiring — sets a trust-all {@code SSLSocketFactory}
 *       and an all-true {@code HostnameVerifier}, unconditionally (no
 *       loopback-vs-remote branching — the fix deliberately removed the
 *       earlier peer-gating so the transport mirrors the vendor
 *       {@code SuiteAPIClient} exactly; DEF-005: "mirror the BC behavior,
 *       don't invent new ways").</li>
 *   <li>FIPS mode (issue #215): detection is {@code IS_FIPS} only
 *       ({@code Boolean.valueOf}; the BouncyCastle approved_only property is
 *       not a signal, also proven in a child JVM); the dispatch
 *       ({@code applySuiteApiTransport}) installs the BC mirror without
 *       touching cluster files when not FIPS, and in FIPS never falls back to
 *       trust-all; cluster TLS options resolve as vendor {@code SSLOptions}
 *       ({@code $STORAGE/vcops/user/conf/ssl/secure-communications.properties},
 *       {@code inter_cluster.} then {@code default.}, encrypted-first
 *       passwords, {@code %truststore_password%} redirect to
 *       {@code storePass.properties}, path variables, {@code TLS_RSA*}
 *       filter); real TLS handshakes prove trust, rejection, protocol and
 *       cipher restriction, client keystore and the per-instance cache; every
 *       unreadable input fails loud naming the path.</li>
 *   <li>{@link VcfCfAdapter#insecureSslContext()} (issue #82): a real TLS
 *       handshake, over {@code java.net.http.HttpClient}, against a server
 *       certificate whose name does not match the address dialed. Asserts the
 *       handshake succeeds under {@code insecureSslContext()} and still fails
 *       under a normal validating context, so this test would catch a future
 *       change that accidentally makes everything insecure.</li>
 * </ol>
 *
 * <p>{@code openPlatformConnection(String)} itself (the instance method) is
 * NOT exercised here — instantiating a live {@link VcfCfAdapter} subclass
 * requires the collector's log4j-core runtime classpath (pulled in by
 * {@code AdapterBase}'s constructor), which is not available outside the
 * appliance. This is the same limitation documented in
 * {@code SuiteApiStitchClientTest} for behavior that depends on a live
 * platform connection; see its class javadoc. The transport wiring itself
 * ({@code applyBcMirrorTransport}) was extracted to a static, instance-free
 * helper specifically so it CAN be unit-tested here without that dependency.
 *
 * <p>Run:
 * <pre>
 *   javac -cp adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         adapter_framework/test/com/vcfcf/adapter/VcfCfAdapterTest.java \
 *         -d build/test-classes
 *   java -cp build/test-classes:adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         com.vcfcf.adapter.VcfCfAdapterTest
 * </pre>
 */
public class VcfCfAdapterTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;

    @FunctionalInterface
    private interface TestCase {
        void run() throws Exception;
    }

    /** Run one test; an uncaught throwable is a named FAIL, and later tests still run. */
    private static void run(String name, TestCase test) {
        try {
            test.run();
        } catch (Throwable t) {
            System.out.println("  FAIL: " + name + " threw " + t);
            FAILURES.add(name + " threw " + t);
        }
    }

    /** Child-JVM hook for testIsFipsModeEnabledReadsIsFipsEnvInChildJvm. */
    private static final String PRINT_FIPS_MODE_ARG = "--print-fips-mode";

    public static void main(String[] args) throws Exception {
        if (args.length > 0 && PRINT_FIPS_MODE_ARG.equals(args[0])) {
            System.out.println("fips=" + VcfCfAdapter.isFipsModeEnabled());
            return;
        }
        run("testIsFipsModeEnabledMirrorsBooleanValueOf", VcfCfAdapterTest::testIsFipsModeEnabledMirrorsBooleanValueOf);
        run("testApprovedOnlyPropertyIsNotAFipsSignal", VcfCfAdapterTest::testApprovedOnlyPropertyIsNotAFipsSignal);
        run("testIsFipsModeEnabledReadsIsFipsEnvInChildJvm", VcfCfAdapterTest::testIsFipsModeEnabledReadsIsFipsEnvInChildJvm);
        run("testClusterSslDirectoryMirrorsVendorStorage", VcfCfAdapterTest::testClusterSslDirectoryMirrorsVendorStorage);
        run("testDescribeTransportModeNamesSignal", VcfCfAdapterTest::testDescribeTransportModeNamesSignal);
        run("testApplyBcMirrorTransportLoopback", VcfCfAdapterTest::testApplyBcMirrorTransportLoopback);
        run("testApplyBcMirrorTransportRemoteAlsoTrustAllIgnoreHostname", VcfCfAdapterTest::testApplyBcMirrorTransportRemoteAlsoTrustAllIgnoreHostname);
        run("testInsecureSslContextAcceptsHostnameMismatchOverHttpClient", VcfCfAdapterTest::testInsecureSslContextAcceptsHostnameMismatchOverHttpClient);
        run("testValidatingContextRejectsHostnameMismatchOverHttpClient", VcfCfAdapterTest::testValidatingContextRejectsHostnameMismatchOverHttpClient);
        run("testResolveInterClusterBeatsDefault", VcfCfAdapterTest::testResolveInterClusterBeatsDefault);
        run("testResolveDefaultPrefixIsNotNested", VcfCfAdapterTest::testResolveDefaultPrefixIsNotNested);
        run("testResolveMissingRequiredKeyFailsLoud", VcfCfAdapterTest::testResolveMissingRequiredKeyFailsLoud);
        run("testResolvePasswordEncryptedFirst", VcfCfAdapterTest::testResolvePasswordEncryptedFirst);
        run("testResolvePathSubstitution", VcfCfAdapterTest::testResolvePathSubstitution);
        run("testResolveCipherFilterAndLists", VcfCfAdapterTest::testResolveCipherFilterAndLists);
        run("testDispatchNonFipsInstallsMirrorWithoutClusterFiles", VcfCfAdapterTest::testDispatchNonFipsInstallsMirrorWithoutClusterFiles);
        run("testDispatchFipsFailureThrowsWithoutFallback", VcfCfAdapterTest::testDispatchFipsFailureThrowsWithoutFallback);
        run("testDispatchFipsTrustsClusterTruststoreIgnoresHostname", VcfCfAdapterTest::testDispatchFipsTrustsClusterTruststoreIgnoresHostname);
        run("testDispatchFipsRejectsCertNotInClusterTruststore", VcfCfAdapterTest::testDispatchFipsRejectsCertNotInClusterTruststore);
        run("testFipsSocketsRestrictedToConfiguredProtocolsAndCiphers", VcfCfAdapterTest::testFipsSocketsRestrictedToConfiguredProtocolsAndCiphers);
        run("testFipsPresentsConfiguredClientKeystore", VcfCfAdapterTest::testFipsPresentsConfiguredClientKeystore);
        run("testFipsSocketFactoryCachedAndRefreshedOnChange", VcfCfAdapterTest::testFipsSocketFactoryCachedAndRefreshedOnChange);
        run("testFipsMissingOptionsFileFailsLoud", VcfCfAdapterTest::testFipsMissingOptionsFileFailsLoud);
        run("testFipsNoTruststoreKeyFailsLoud", VcfCfAdapterTest::testFipsNoTruststoreKeyFailsLoud);
        run("testFipsMissingStorePassFailsLoud", VcfCfAdapterTest::testFipsMissingStorePassFailsLoud);
        run("testFipsNoPasswordFailsLoud", VcfCfAdapterTest::testFipsNoPasswordFailsLoud);
        run("testFipsDecryptFailureFailsLoud", VcfCfAdapterTest::testFipsDecryptFailureFailsLoud);
        run("testFipsWrongPasswordFailsLoud", VcfCfAdapterTest::testFipsWrongPasswordFailsLoud);
        run("testFipsBcfksUnavailableFailsLoud", VcfCfAdapterTest::testFipsBcfksUnavailableFailsLoud);
        run("testDescribeFrameworkBuild", VcfCfAdapterTest::testDescribeFrameworkBuild);
        run("testFrameworkJarManifestIsStamped", VcfCfAdapterTest::testFrameworkJarManifestIsStamped);
        report();
    }

    // -----------------------------------------------------------------------
    // Framework version in the jar manifest (issue #214)
    // -----------------------------------------------------------------------

    private static void testDescribeFrameworkBuild() {
        assertTrue("no manifest: says unknown",
                VcfCfAdapter.describeFrameworkBuild(null).contains("version unknown"));
        java.util.jar.Manifest bare = new java.util.jar.Manifest();
        assertTrue("manifest without the stamp: says unknown",
                VcfCfAdapter.describeFrameworkBuild(bare).contains("version unknown"));
        java.util.jar.Manifest mf = new java.util.jar.Manifest();
        java.util.jar.Attributes a = mf.getMainAttributes();
        a.putValue("Implementation-Title", "vcfcf-adapter-base");
        a.putValue("Implementation-Version", "1.0.14");
        a.putValue("X-Vcfcf-Source-Commit", "abc123\r\nforged");
        String label = VcfCfAdapter.describeFrameworkBuild(mf);
        assertTrue("label carries title and version: " + label,
                label.startsWith("vcfcf-adapter-base 1.0.14 (source abc123"));
        assertFalse("label has no line break", label.contains("\n") || label.contains("\r"));
        java.util.jar.Manifest noCommit = new java.util.jar.Manifest();
        noCommit.getMainAttributes().putValue("Implementation-Version", "1.0.14");
        assertTrue("missing commit and title fall back",
                VcfCfAdapter.describeFrameworkBuild(noCommit)
                        .equals("vcfcf-adapter-base 1.0.14 (source unknown)"));
    }

    /**
     * The jar under test (built by build-framework.sh or
     * sdk_builder._ensure_framework_jar) carries the stamp, and the label is
     * read from that jar, not from another manifest on the class path.
     */
    private static void testFrameworkJarManifestIsStamped() {
        java.util.jar.Manifest mf = VcfCfAdapter.frameworkManifest();
        assertTrue("framework classes load from a jar with a manifest", mf != null);
        if (mf == null) return;
        java.util.jar.Attributes a = mf.getMainAttributes();
        assertTrue("Implementation-Title is vcfcf-adapter-base",
                "vcfcf-adapter-base".equals(a.getValue("Implementation-Title")));
        String v = a.getValue("Implementation-Version");
        assertTrue("Implementation-Version is set (" + v + ")", v != null && !v.isEmpty());
        assertTrue("X-Vcfcf-Source-Commit is set",
                a.getValue("X-Vcfcf-Source-Commit") != null);
        assertTrue("frameworkBuildLabel names the version: " + VcfCfAdapter.frameworkBuildLabel(),
                VcfCfAdapter.frameworkBuildLabel().startsWith("vcfcf-adapter-base " + v + " "));
    }

    // -----------------------------------------------------------------------
    // FIPS mode detection and cluster SSL directory (issue #215)
    // -----------------------------------------------------------------------

    private static void testIsFipsModeEnabledMirrorsBooleanValueOf() {
        // Vendor: Constants.FIPS_MODE_ENABLED = Boolean.valueOf(System.getenv("IS_FIPS")).
        assertFalse("isFipsModeEnabled(null) is false (IS_FIPS unset)",
                VcfCfAdapter.isFipsModeEnabled((String) null));
        assertTrue("isFipsModeEnabled(\"true\") is true",
                VcfCfAdapter.isFipsModeEnabled("true"));
        assertTrue("isFipsModeEnabled(\"TRUE\") is true (case-insensitive like Boolean.valueOf)",
                VcfCfAdapter.isFipsModeEnabled("TRUE"));
        assertFalse("isFipsModeEnabled(\"false\") is false",
                VcfCfAdapter.isFipsModeEnabled("false"));
        assertFalse("isFipsModeEnabled(\"1\") is false (Boolean.valueOf semantics)",
                VcfCfAdapter.isFipsModeEnabled("1"));
    }

    private static void testApprovedOnlyPropertyIsNotAFipsSignal() {
        if (System.getenv("IS_FIPS") != null) {
            System.out.println("  SKIP: approved_only-is-not-a-signal test (IS_FIPS is set in "
                    + "this environment)");
            return;
        }
        String prior = System.getProperty("org.bouncycastle.fips.approved_only");
        try {
            System.setProperty("org.bouncycastle.fips.approved_only", "true");
            assertFalse("isFipsModeEnabled() stays false with approved_only=true and IS_FIPS "
                    + "unset (the vendor reads IS_FIPS only)", VcfCfAdapter.isFipsModeEnabled());
        } finally {
            restoreProperty("org.bouncycastle.fips.approved_only", prior);
        }
    }

    private static void testIsFipsModeEnabledReadsIsFipsEnvInChildJvm() throws Exception {
        java.io.File javaBin = new java.io.File(System.getProperty("java.home"),
                "bin" + java.io.File.separator + "java");
        if (!javaBin.isFile()) {
            System.out.println("  SKIP: IS_FIPS child-JVM test (no java binary in java.home)");
            return;
        }
        assertTrue("child JVM with IS_FIPS=true reports FIPS mode",
                childFipsMode(javaBin, "true").equals("fips=true"));
        assertTrue("child JVM with IS_FIPS unset reports non-FIPS mode",
                childFipsMode(javaBin, null).equals("fips=false"));
    }

    private static String childFipsMode(java.io.File javaBin, String isFips) throws Exception {
        ProcessBuilder pb = new ProcessBuilder(javaBin.getPath(),
                "-cp", System.getProperty("java.class.path"),
                VcfCfAdapterTest.class.getName(), PRINT_FIPS_MODE_ARG)
                .redirectErrorStream(true);
        pb.environment().remove("IS_FIPS");
        if (isFips != null) {
            pb.environment().put("IS_FIPS", isFips);
        }
        Process p = pb.start();
        String out = new String(p.getInputStream().readAllBytes(),
                java.nio.charset.StandardCharsets.UTF_8).trim();
        if (!p.waitFor(60, java.util.concurrent.TimeUnit.SECONDS)) {
            p.destroyForcibly();
            return "timeout";
        }
        return out;
    }

    private static void testClusterSslDirectoryMirrorsVendorStorage() throws Exception {
        try {
            VcfCfAdapter.clusterSslDirectory((String) null);
            FAILURES.add("clusterSslDirectory(null) should fail (STORAGE unset)");
        } catch (java.io.IOException e) {
            assertTrue("clusterSslDirectory(null) fails naming STORAGE",
                    String.valueOf(e.getMessage()).contains("STORAGE"));
        }
        assertTrue("clusterSslDirectory(root) resolves root/vcops/user/conf/ssl",
                VcfCfAdapter.clusterSslDirectory("/storage")
                        .equals(java.nio.file.Paths.get("/storage/vcops/user/conf/ssl")));
        if (System.getenv("STORAGE") != null) {
            System.out.println("  SKIP: STORAGE system-property test (STORAGE env is set)");
            return;
        }
        String prior = System.getProperty("STORAGE");
        try {
            System.setProperty("STORAGE", "/srv/x");
            assertTrue("clusterSslDirectory() falls back to the STORAGE system property",
                    VcfCfAdapter.clusterSslDirectory()
                            .equals(java.nio.file.Paths.get("/srv/x/vcops/user/conf/ssl")));
        } finally {
            restoreProperty("STORAGE", prior);
        }
    }

    /** U+2014, built from its code point so this source file carries no em-dash. */
    private static final String EM_DASH = String.valueOf((char) 0x2014);

    private static void testDescribeTransportModeNamesSignal() {
        String file = "/storage/vcops/user/conf/ssl/secure-communications.properties";
        String fips = VcfCfAdapter.describeTransportMode(true, file, null);
        assertTrue("FIPS mode line names the IS_FIPS=true signal and the options file",
                fips.contains("mode=FIPS") && fips.contains("IS_FIPS=true")
                        && fips.contains(file));
        String nonFips = VcfCfAdapter.describeTransportMode(false, null, "true");
        assertTrue("non-FIPS mode line names the signal and prints approved_only as a diagnostic",
                nonFips.contains("mode=non-FIPS") && nonFips.contains("IS_FIPS is not true")
                        && nonFips.contains("org.bouncycastle.fips.approved_only=true"));
        assertFalse("mode lines carry no em-dash",
                fips.contains(EM_DASH) || nonFips.contains(EM_DASH));
    }

    // -----------------------------------------------------------------------
    // Cluster TLS option resolution (vendor SSLOptions, VROPS_CLUSTER)
    // -----------------------------------------------------------------------

    private static final String TRUSTSTORE_PASSWORD = "cluster-pass";
    private static final String TEST_STORE_TYPE = "PKCS12";
    /** Stand-in for Crypt.decrypt: unwraps ENC(...) and reverses. */
    private static final java.util.function.UnaryOperator<String> FAKE_DECRYPT = enc -> {
        if (!enc.startsWith("ENC(") || !enc.endsWith(")")) {
            throw new IllegalStateException("not ENC(...)");
        }
        return new StringBuilder(enc.substring(4, enc.length() - 1)).reverse().toString();
    };

    private static String enc(String plain) {
        return "ENC(" + new StringBuilder(plain).reverse() + ")";
    }

    /** The common options file, with {@code extra} lines appended. */
    private static String options(java.nio.file.Path sslDir, String extra) {
        return "default.protocol=TLS\n"
                + "default.store_type=" + TEST_STORE_TYPE + "\n"
                + "default.algorithm=PKIX\n"
                + "default.supported_protocols=%all%\n"
                + "default.supported_cipher_suites=%all%\n"
                + "default.truststore=" + sslDir.resolve("tcserver.truststore") + "\n"
                + "default.truststore_password=%truststore_password%\n"
                + extra;
    }

    private static void testResolveInterClusterBeatsDefault() throws Exception {
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir,
                    "inter_cluster.algorithm=SunX509\ndefault.keystore_password=%keystore_password%\n"));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword.encrypted=" + enc(TRUSTSTORE_PASSWORD) + "\n");
            VcfCfAdapter.ClusterSslOptions o =
                    VcfCfAdapter.resolveClusterSslOptions(sslDir, true, FAKE_DECRYPT);
            assertTrue("inter_cluster.<key> wins over default.<key>",
                    "SunX509".equals(o.algorithm));
            assertTrue("default.<key> is the fallback", TEST_STORE_TYPE.equals(o.storeType)
                    && "TLS".equals(o.protocol));
            assertTrue("%truststore_password% redirects to storePass.properties, .encrypted "
                    + "decrypted", TRUSTSTORE_PASSWORD.equals(o.truststorePassword));
            assertTrue("a %keystore_password% sentinel with no keystore and no "
                    + "sslkeystorePassword resolves to no keystore, as the vendor does",
                    o.keystore == null && o.keystorePassword == null);
        });
    }

    private static void testResolveDefaultPrefixIsNotNested() throws Exception {
        // Bytecode: propertyLookupPrefixes(VROPS_CLUSTER) = [inter_cluster, default],
        // never "default.inter_cluster".
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir,
                    "default.inter_cluster.algorithm=SunX509\n"));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            VcfCfAdapter.ClusterSslOptions o =
                    VcfCfAdapter.resolveClusterSslOptions(sslDir, true, FAKE_DECRYPT);
            assertTrue("default.inter_cluster.<key> is not a lookup key (prefixes are "
                    + "inter_cluster, default)", "PKIX".equals(o.algorithm));
        });
    }

    private static void testResolveMissingRequiredKeyFailsLoud() throws Exception {
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties",
                    options(sslDir, "").replace("default.supported_protocols=%all%\n", ""));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            assertResolveFails(sslDir, "missing supported_protocols", "supported_protocols",
                    sslDir.resolve("secure-communications.properties").toString());
        });
    }

    private static void testResolvePasswordEncryptedFirst() throws Exception {
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir, "")
                    .replace("default.truststore_password=%truststore_password%\n",
                            "inter_cluster.truststore_password=wrong\n"
                            + "default.truststore_password.encrypted=" + enc("from-options")
                            + "\n"));
            VcfCfAdapter.ClusterSslOptions o =
                    VcfCfAdapter.resolveClusterSslOptions(sslDir, true, FAKE_DECRYPT);
            assertTrue("truststore_password.encrypted (any prefix) is read before the plain "
                    + "key (any prefix)", "from-options".equals(o.truststorePassword));
        });
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir, "")
                    .replace("%truststore_password%", "%TrustStore_Password%"));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=wrong\nssltruststorePassword.encrypted="
                    + enc(TRUSTSTORE_PASSWORD) + "\n");
            VcfCfAdapter.ClusterSslOptions o =
                    VcfCfAdapter.resolveClusterSslOptions(sslDir, true, FAKE_DECRYPT);
            assertTrue("storePass.properties: .encrypted first (CryptUtils order), sentinel "
                    + "matched case-insensitively", TRUSTSTORE_PASSWORD.equals(o.truststorePassword));
        });
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir, ""));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            VcfCfAdapter.ClusterSslOptions o = VcfCfAdapter.resolveClusterSslOptions(sslDir, true,
                    s -> { throw new AssertionError("decryptor must not run"); });
            assertTrue("storePass.properties: plain key is the fallback",
                    TRUSTSTORE_PASSWORD.equals(o.truststorePassword));
        });
    }

    private static void testResolvePathSubstitution() throws Exception {
        String var = "VCFCF_T215_DIR";
        if (System.getenv(var) != null) {
            System.out.println("  SKIP: path substitution test (" + var + " is set in env)");
            return;
        }
        String prior = System.getProperty(var);
        try {
            withSslDir(sslDir -> {
                System.setProperty(var, sslDir.toString());
                writeFile(sslDir, "secure-communications.properties", options(sslDir, "")
                        .replace("default.truststore=" + sslDir.resolve("tcserver.truststore"),
                                "default.truststore=%" + var + "%/tcserver.truststore")
                        + "default.keystore=$" + var + "/client.p12 $VCFCF_T215_UNSET\n"
                        + "default.keystore_password=x\n");
                writeFile(sslDir, "storePass.properties",
                        "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
                VcfCfAdapter.ClusterSslOptions o =
                        VcfCfAdapter.resolveClusterSslOptions(sslDir, true, FAKE_DECRYPT);
                assertTrue("%VAR% in truststore is replaced from the environment or a system "
                        + "property", o.truststore.equals(sslDir + "/tcserver.truststore"));
                assertTrue("$VAR in keystore is replaced; an unresolved $NAME stays as written",
                        o.keystore.equals(sslDir + "/client.p12 $VCFCF_T215_UNSET"));
            });
        } finally {
            restoreProperty(var, prior);
        }
    }

    private static void testResolveCipherFilterAndLists() throws Exception {
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir, "")
                    .replace("default.supported_cipher_suites=%all%",
                            "default.supported_cipher_suites= TLS_RSA_WITH_AES_128_GCM_SHA256 ,"
                            + "TLS_AES_128_GCM_SHA256,TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256 ")
                    .replace("default.supported_protocols=%all%",
                            "default.supported_protocols=TLSv1.2 , TLSv1.3"));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            VcfCfAdapter.ClusterSslOptions fips =
                    VcfCfAdapter.resolveClusterSslOptions(sslDir, true, FAKE_DECRYPT);
            assertTrue("FIPS: TLS_RSA* suites are filtered, others kept, list trimmed and split",
                    java.util.Arrays.asList(fips.supportedCipherSuites).equals(
                            java.util.Arrays.asList("TLS_AES_128_GCM_SHA256",
                                    "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256")));
            VcfCfAdapter.ClusterSslOptions nonFips =
                    VcfCfAdapter.resolveClusterSslOptions(sslDir, false, FAKE_DECRYPT);
            assertTrue("without IS_FIPS no suite is filtered",
                    nonFips.supportedCipherSuites.length == 3);
            assertTrue("supported_protocols is trimmed and split on commas",
                    java.util.Arrays.asList(fips.supportedProtocols).equals(
                            java.util.Arrays.asList("TLSv1.2", "TLSv1.3")));
        });
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir, "")
                    .replace("=%all%", "=%ALL%"));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            VcfCfAdapter.ClusterSslOptions o =
                    VcfCfAdapter.resolveClusterSslOptions(sslDir, true, FAKE_DECRYPT);
            boolean noTlsRsa = java.util.Arrays.stream(o.supportedCipherSuites)
                    .noneMatch(c -> c.startsWith("TLS_RSA"));
            assertTrue("%all% (any case) takes the JRE defaults, TLS_RSA* still filtered in FIPS",
                    o.supportedCipherSuites.length > 0 && o.supportedProtocols.length > 0
                            && noTlsRsa);
        });
    }

    // -----------------------------------------------------------------------
    // Dispatch and transport: real TLS handshakes over HttpsURLConnection
    // against a 127.0.0.1 server whose cert is issued to a mismatched name.
    // Store type is PKCS12: the stock JDK has no BCFKS provider (the store
    // type comes from store_type; testFipsBcfksUnavailableFailsLoud covers it).
    // -----------------------------------------------------------------------

    private static void testDispatchNonFipsInstallsMirrorWithoutClusterFiles() throws Exception {
        javax.net.ssl.HttpsURLConnection https = (javax.net.ssl.HttpsURLConnection)
                new java.net.URL("https://localhost/suite-api/").openConnection();
        boolean[] failureCalled = {false};
        VcfCfAdapter.applySuiteApiTransport(https, false,
                () -> { throw new AssertionError("non-FIPS must not resolve the SSL directory"); },
                new VcfCfAdapter.ClusterSocketFactoryCache(),
                s -> { throw new AssertionError("non-FIPS must not decrypt"); },
                e -> failureCalled[0] = true);
        assertTrue("dispatch non-FIPS: trust-all + all-true verifier, no cluster input read",
                https.getHostnameVerifier().verify("no-match.invalid", null)
                        && https.getSSLSocketFactory() != javax.net.ssl.HttpsURLConnection
                                .getDefaultSSLSocketFactory()
                        && !failureCalled[0]);
    }

    private static void testDispatchFipsFailureThrowsWithoutFallback() throws Exception {
        withSslDir(sslDir -> {
            // Options file present, truststore file absent.
            writeFile(sslDir, "secure-communications.properties", options(sslDir, ""));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            assertDispatchFails(() -> sslDir, "dispatch FIPS, truststore missing",
                    sslDir.resolve("tcserver.truststore").toString());
        });
        assertDispatchFails(() -> VcfCfAdapter.clusterSslDirectory((String) null),
                "dispatch FIPS, STORAGE unset", "STORAGE");
    }

    private static void testDispatchFipsTrustsClusterTruststoreIgnoresHostname() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir.resolve("tcserver.truststore"), serverKs);
            writeFile(sslDir, "secure-communications.properties", options(sslDir, ""));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword.encrypted=" + enc(TRUSTSTORE_PASSWORD) + "\n");
            assertTrue("dispatch FIPS: handshake succeeds when the server chain is in the "
                    + "cluster truststore, despite the hostname mismatch (verify=true, "
                    + "ignoreHostName=true)",
                    fipsRequest(baseUrl, sslDir, new VcfCfAdapter.ClusterSocketFactoryCache())
                            == 200);
        });
    }

    private static void testDispatchFipsRejectsCertNotInClusterTruststore() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir.resolve("tcserver.truststore"), otherKs);
            writeFile(sslDir, "secure-communications.properties", options(sslDir, ""));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            try {
                fipsRequest(baseUrl, sslDir, new VcfCfAdapter.ClusterSocketFactoryCache());
                FAILURES.add("dispatch FIPS: handshake against a cert NOT in the cluster "
                        + "truststore should have failed (this would mean trust-all)");
            } catch (javax.net.ssl.SSLHandshakeException e) {
                assertTrue("dispatch FIPS: cert not in the cluster truststore fails the "
                        + "handshake (chain is verified, not trust-all)", true);
            }
        });
    }

    private static void testFipsSocketsRestrictedToConfiguredProtocolsAndCiphers()
            throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir.resolve("tcserver.truststore"), serverKs);
            writeFile(sslDir, "secure-communications.properties", options(sslDir, "")
                    .replace("default.supported_protocols=%all%",
                            "default.supported_protocols=TLSv1.2,SSLv2Hello-bogus")
                    .replace("default.supported_cipher_suites=%all%",
                            "default.supported_cipher_suites=TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,"
                            + "TLS_RSA_WITH_AES_128_GCM_SHA256"));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            javax.net.ssl.SSLSocketFactory f = new VcfCfAdapter.ClusterSocketFactoryCache()
                    .get(sslDir, true, FAKE_DECRYPT);
            java.net.URL u = new java.net.URL(baseUrl);
            try (javax.net.ssl.SSLSocket s =
                    (javax.net.ssl.SSLSocket) f.createSocket(u.getHost(), u.getPort())) {
                assertTrue("FIPS sockets: enabled protocols = supported intersect configured",
                        java.util.Arrays.asList(s.getEnabledProtocols())
                                .equals(java.util.Collections.singletonList("TLSv1.2")));
                assertTrue("FIPS sockets: enabled suites = supported intersect configured, TLS_RSA* "
                        + "already filtered", java.util.Arrays.asList(s.getEnabledCipherSuites())
                                .equals(java.util.Collections.singletonList(
                                        "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256")));
                s.startHandshake();
                assertTrue("FIPS sockets: handshake negotiates the restricted protocol",
                        "TLSv1.2".equals(s.getSession().getProtocol()));
            }
        });
    }

    private static void testFipsPresentsConfiguredClientKeystore() throws Exception {
        java.io.File keytoolFile = keytool();
        if (keytoolFile == null) {
            System.out.println("  SKIP: client keystore test (no keytool in java.home)");
            return;
        }
        withSslDir(sslDir -> {
            java.security.KeyStore serverKs = generateKeyPair(keytoolFile,
                    sslDir.resolve("server.p12"), MISMATCHED_CERT_CN);
            java.nio.file.Path clientP12 = sslDir.resolve("client.p12");
            java.security.KeyStore clientKs = generateKeyPair(keytoolFile, clientP12,
                    "collector.example.com");
            writeTruststore(sslDir.resolve("tcserver.truststore"), serverKs);
            writeFile(sslDir, "secure-communications.properties", options(sslDir,
                    "default.keystore=" + clientP12 + "\n"
                    + "default.keystore_password=%keystore_password%\n"));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n"
                    + "sslkeystorePassword.encrypted=" + enc(KEYSTORE_PASSWORD) + "\n");
            withHttpsServer(serverKs, clientKs, baseUrl -> assertTrue("FIPS: the configured "
                    + "client keystore (%keystore_password% via storePass.properties) is "
                    + "presented to a server that requires client auth",
                    fipsRequest(baseUrl, sslDir, new VcfCfAdapter.ClusterSocketFactoryCache())
                            == 200));
        });
    }

    private static void testFipsSocketFactoryCachedAndRefreshedOnChange() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            java.nio.file.Path ts = sslDir.resolve("tcserver.truststore");
            writeTruststore(ts, serverKs);
            writeFile(sslDir, "secure-communications.properties", options(sslDir, ""));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            VcfCfAdapter.ClusterSocketFactoryCache cache =
                    new VcfCfAdapter.ClusterSocketFactoryCache();
            javax.net.ssl.SSLSocketFactory first = cache.get(sslDir, true, FAKE_DECRYPT);
            javax.net.ssl.SSLSocketFactory second = cache.get(sslDir, true, FAKE_DECRYPT);
            assertTrue("cache: unchanged inputs reuse one factory (one build)",
                    first == second && cache.buildCount() == 1);
            writeTruststore(ts, serverKs, otherKs);
            bumpMtime(ts);
            javax.net.ssl.SSLSocketFactory third = cache.get(sslDir, true, FAKE_DECRYPT);
            assertTrue("cache: a changed truststore rebuilds the factory",
                    third != first && cache.buildCount() == 2);
            java.nio.file.Files.delete(ts);
            try {
                cache.get(sslDir, true, FAKE_DECRYPT);
                FAILURES.add("cache: a deleted truststore should fail, not reuse the old factory");
            } catch (java.io.IOException e) {
                assertTrue("cache: a deleted truststore fails loud naming it",
                        String.valueOf(e.getMessage()).contains(ts.toString()));
            }
            writeTruststore(ts, serverKs);
            assertTrue("cache: failures are not cached, the next call recovers",
                    fipsRequest(baseUrl, sslDir, cache) == 200);
        });
    }

    // -----------------------------------------------------------------------
    // FIPS failure inputs: each fails loud naming the path, no trust-all.
    // -----------------------------------------------------------------------

    private static void testFipsMissingOptionsFileFailsLoud() throws Exception {
        withSslDir(sslDir -> assertDispatchFails(() -> sslDir, "missing "
                + "secure-communications.properties",
                sslDir.resolve("secure-communications.properties").toString()));
    }

    private static void testFipsNoTruststoreKeyFailsLoud() throws Exception {
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir, "")
                    .replace("default.truststore=" + sslDir.resolve("tcserver.truststore") + "\n",
                            ""));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            assertDispatchFails(() -> sslDir, "no truststore key", "has no truststore key");
        });
    }

    private static void testFipsMissingStorePassFailsLoud() throws Exception {
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir, ""));
            assertDispatchFails(() -> sslDir, "sentinel with missing storePass.properties",
                    sslDir.resolve("storePass.properties").toString());
        });
    }

    private static void testFipsNoPasswordFailsLoud() throws Exception {
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir, ""));
            writeFile(sslDir, "storePass.properties", "sslkeystorePassword=unrelated\n");
            assertDispatchFails(() -> sslDir, "no truststore password anywhere",
                    "no truststore password resolved");
        });
    }

    private static void testFipsDecryptFailureFailsLoud() throws Exception {
        withSslDir(sslDir -> {
            writeFile(sslDir, "secure-communications.properties", options(sslDir, ""));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword.encrypted=secret-material-opaque\n");
            String reason = assertDispatchFails(() -> sslDir, "decrypt failure",
                    sslDir.resolve("storePass.properties").toString());
            assertFalse("decrypt failure message does not echo the value or the exception "
                    + "message", reason != null && reason.contains("secret-material"));
        });
    }

    private static void testFipsWrongPasswordFailsLoud() throws Exception {
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir.resolve("tcserver.truststore"), serverKs);
            writeFile(sslDir, "secure-communications.properties", options(sslDir, ""));
            writeFile(sslDir, "storePass.properties", "ssltruststorePassword=wrong\n");
            String reason = assertDispatchFails(() -> sslDir, "wrong truststore password",
                    sslDir.resolve("tcserver.truststore").toString());
            assertTrue("load failure reports the exception class only (one posture with "
                    + "decrypt failures)", reason != null && reason.endsWith("java.io.IOException"));
        });
    }

    private static void testFipsBcfksUnavailableFailsLoud() throws Exception {
        boolean bcfksAvailable;
        try {
            java.security.KeyStore.getInstance("BCFKS");
            bcfksAvailable = true;
        } catch (java.security.KeyStoreException e) {
            bcfksAvailable = false;
        }
        if (bcfksAvailable) {
            System.out.println("  SKIP: BCFKS-unavailable test (this JVM has a BCFKS provider)");
            return;
        }
        withFipsFixture((baseUrl, serverKs, otherKs, sslDir) -> {
            writeTruststore(sslDir.resolve("tcserver.truststore"), serverKs);
            writeFile(sslDir, "secure-communications.properties", options(sslDir, "")
                    .replace("default.store_type=" + TEST_STORE_TYPE, "default.store_type=BCFKS"));
            writeFile(sslDir, "storePass.properties",
                    "ssltruststorePassword=" + TRUSTSTORE_PASSWORD + "\n");
            String reason = assertDispatchFails(() -> sslDir, "store_type BCFKS unavailable",
                    sslDir.resolve("tcserver.truststore").toString());
            assertTrue("BCFKS-unavailable failure names the store type",
                    reason != null && reason.contains("BCFKS"));
        });
    }

    // -----------------------------------------------------------------------
    // FIPS helpers
    // -----------------------------------------------------------------------

    /** Issue a GET through the FIPS dispatch; returns the HTTP status. */
    private static int fipsRequest(String baseUrl, java.nio.file.Path sslDir,
            VcfCfAdapter.ClusterSocketFactoryCache cache) throws Exception {
        javax.net.ssl.HttpsURLConnection https =
                (javax.net.ssl.HttpsURLConnection) new java.net.URL(baseUrl).openConnection();
        VcfCfAdapter.applySuiteApiTransport(https, true, () -> sslDir, cache, FAKE_DECRYPT,
                e -> { });
        https.setConnectTimeout(10_000);
        https.setReadTimeout(10_000);
        try {
            return https.getResponseCode();
        } finally {
            https.disconnect();
        }
    }

    /**
     * Assert the FIPS dispatch throws an IOException whose message contains
     * {@code mustContain}, runs the failure callback exactly once, and leaves
     * the connection on the JDK defaults (no trust-all factory or all-true
     * verifier). Returns the message.
     */
    private static String assertDispatchFails(VcfCfAdapter.SslDirectorySource sslDir,
            String label, String mustContain) throws Exception {
        javax.net.ssl.HttpsURLConnection https = (javax.net.ssl.HttpsURLConnection)
                new java.net.URL("https://127.0.0.1:9/suite-api/").openConnection();
        javax.net.ssl.SSLSocketFactory defaultFactory = https.getSSLSocketFactory();
        javax.net.ssl.HostnameVerifier defaultVerifier = https.getHostnameVerifier();
        int[] callbacks = {0};
        try {
            VcfCfAdapter.applySuiteApiTransport(https, true, sslDir,
                    new VcfCfAdapter.ClusterSocketFactoryCache(), FAKE_DECRYPT,
                    e -> callbacks[0]++);
            FAILURES.add("FIPS (" + label + "): expected an IOException, got none (trust-all "
                    + "fallback or ignored flag)");
            return null;
        } catch (java.io.IOException e) {
            String msg = String.valueOf(e.getMessage());
            assertTrue("FIPS (" + label + "): fails loud naming " + mustContain + ". Actual: "
                    + msg, msg.contains(mustContain));
            assertTrue("FIPS (" + label + "): failure callback ran once, no trust-all "
                    + "fallback (JDK default socket factory and hostname verifier kept)",
                    callbacks[0] == 1 && https.getSSLSocketFactory() == defaultFactory
                            && https.getHostnameVerifier() == defaultVerifier);
            return msg;
        }
    }

    /** Assert option resolution fails naming every string in {@code mustContain}. */
    private static void assertResolveFails(java.nio.file.Path sslDir, String label,
            String... mustContain) {
        try {
            VcfCfAdapter.resolveClusterSslOptions(sslDir, true, FAKE_DECRYPT);
            FAILURES.add("resolve (" + label + "): expected an IOException, got none");
        } catch (java.io.IOException e) {
            String msg = String.valueOf(e.getMessage());
            boolean all = true;
            for (String m : mustContain) {
                all &= msg.contains(m);
            }
            assertTrue("resolve (" + label + "): fails loud naming "
                    + java.util.Arrays.toString(mustContain) + ". Actual: " + msg, all);
        }
    }

    @FunctionalInterface
    private interface SslDirTest {
        void run(java.nio.file.Path sslDir) throws Exception;
    }

    /** A fresh {@code <tmp>/vcops/user/conf/ssl}, resolved through clusterSslDirectory. */
    private static void withSslDir(SslDirTest test) throws Exception {
        java.nio.file.Path tmpDir = java.nio.file.Files.createTempDirectory("vcfcf-fips-test");
        try {
            java.nio.file.Path sslDir = VcfCfAdapter.clusterSslDirectory(tmpDir.toString());
            java.nio.file.Files.createDirectories(sslDir);
            test.run(sslDir);
        } finally {
            deleteRecursivelyQuietly(tmpDir);
        }
    }

    @FunctionalInterface
    private interface FipsFixtureTest {
        void run(String baseUrl, java.security.KeyStore serverKs,
                java.security.KeyStore otherKs, java.nio.file.Path sslDir) throws Exception;
    }

    /**
     * Server on 127.0.0.1 with a cert for {@link #MISMATCHED_CERT_CN}, a second
     * unrelated keypair, and an empty cluster SSL directory. SKIPs without keytool.
     */
    private static void withFipsFixture(FipsFixtureTest test) throws Exception {
        java.io.File keytoolFile = keytool();
        if (keytoolFile == null) {
            System.out.println("  SKIP: FIPS cluster-truststore test (no keytool in java.home)");
            return;
        }
        withSslDir(sslDir -> {
            java.security.KeyStore serverKs = generateKeyPair(keytoolFile,
                    sslDir.resolve("server.p12"), MISMATCHED_CERT_CN);
            java.security.KeyStore otherKs = generateKeyPair(keytoolFile,
                    sslDir.resolve("other.p12"), "unrelated.example.com");
            withHttpsServer(serverKs, baseUrl -> test.run(baseUrl, serverKs, otherKs, sslDir));
        });
    }

    /** Write the given keystores' certificates as the trusted entries of a PKCS12 truststore. */
    private static void writeTruststore(java.nio.file.Path path, java.security.KeyStore... from)
            throws Exception {
        java.security.KeyStore ts = java.security.KeyStore.getInstance(TEST_STORE_TYPE);
        ts.load(null, null);
        for (int i = 0; i < from.length; i++) {
            ts.setCertificateEntry("cluster-ca-" + i, from[i].getCertificate("vcfcf-test"));
        }
        try (java.io.OutputStream out = java.nio.file.Files.newOutputStream(path)) {
            ts.store(out, TRUSTSTORE_PASSWORD.toCharArray());
        }
    }

    private static void bumpMtime(java.nio.file.Path path) throws Exception {
        java.nio.file.Files.setLastModifiedTime(path, java.nio.file.attribute.FileTime
                .fromMillis(java.nio.file.Files.getLastModifiedTime(path).toMillis() + 5_000));
    }

    private static void writeFile(java.nio.file.Path dir, String name, String content)
            throws Exception {
        java.nio.file.Files.write(dir.resolve(name),
                content.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));
    }

    private static void restoreProperty(String key, String prior) {
        if (prior == null) {
            System.clearProperty(key);
        } else {
            System.setProperty(key, prior);
        }
    }

    // -----------------------------------------------------------------------
    // applyBcMirrorTransport — BC-mirror transport (non-FIPS default)
    // -----------------------------------------------------------------------

    private static void testApplyBcMirrorTransportLoopback() throws Exception {
        assertBcMirrorTransport("https://localhost/suite-api/api/auth/token/acquire");
    }

    private static void testApplyBcMirrorTransportRemoteAlsoTrustAllIgnoreHostname()
            throws Exception {
        // DEF-005: the fix removed loopback/remote peer-gating — the transport
        // is unconditional trust-all + ignore-hostname, exactly matching the
        // vendor SuiteAPIClient (which does not peer-gate either). Same
        // wiring for a loopback URL and a non-loopback (remote/CP) URL.
        assertBcMirrorTransport("https://vcf-ops.example.com/suite-api/api/auth/token/acquire");
    }

    private static void assertBcMirrorTransport(String url) throws Exception {
        java.net.URL u = new java.net.URL(url);
        java.net.URLConnection conn = u.openConnection();
        if (!(conn instanceof javax.net.ssl.HttpsURLConnection)) {
            FAILURES.add("openConnection(" + url + ") did not return an HttpsURLConnection");
            return;
        }
        javax.net.ssl.HttpsURLConnection https = (javax.net.ssl.HttpsURLConnection) conn;

        VcfCfAdapter.applyBcMirrorTransport(https);

        // Trust half: trust-all SSLSocketFactory is set (built from
        // VcfCfAdapter.insecureSslContext(), the same trust-all
        // X509ExtendedTrustManager used for the target-system opt-out path).
        assertTrue("applyBcMirrorTransport(" + url + "): SSLSocketFactory is set",
                https.getSSLSocketFactory() != null);

        // Hostname half: ignore-hostname — verify(host, session) returns true
        // unconditionally, for an arbitrary mismatched host AND the URL's own host.
        javax.net.ssl.HostnameVerifier hv = https.getHostnameVerifier();
        assertTrue("applyBcMirrorTransport(" + url + "): hostname verifier accepts an "
                + "arbitrary hostname (ignore-hostname mirror)",
                hv.verify("this-host-does-not-match-anything.invalid", null));
        assertTrue("applyBcMirrorTransport(" + url + "): hostname verifier also accepts "
                + "the connection's own host",
                hv.verify(u.getHost(), null));
    }

    // -----------------------------------------------------------------------
    // insecureSslContext, issue #82 hostname-verification fix
    //
    // Real TLS handshake, over java.net.http.HttpClient, against a server
    // certificate issued to a name that does not match the address dialed
    // (127.0.0.1). Before the fix, insecureSslContext()'s trust-all
    // javax.net.ssl.X509TrustManager was silently wrapped by JSSE in
    // sun.security.ssl.AbstractTrustManagerWrapper, which re-applies the
    // endpoint identity (hostname) check that HttpClient always requests.
    // so the handshake failed with a CertificateException even with the
    // trust-all manager in place. The fix (X509ExtendedTrustManager) makes
    // JSSE use the manager directly, so the identity check never runs.
    // -----------------------------------------------------------------------

    /** The self-signed cert's subject/SAN, deliberately not "127.0.0.1". */
    private static final String MISMATCHED_CERT_CN = "wrong.example.com";
    private static final String KEYSTORE_PASSWORD = "changeit";

    private static void testInsecureSslContextAcceptsHostnameMismatchOverHttpClient()
            throws Exception {
        withMismatchedCertServer((baseUrl, ignoredTrustStore) -> {
            java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
                    .sslContext(VcfCfAdapter.insecureSslContext())
                    .build();
            java.net.http.HttpResponse<String> resp;
            try {
                resp = client.send(
                        java.net.http.HttpRequest.newBuilder(java.net.URI.create(baseUrl)).build(),
                        java.net.http.HttpResponse.BodyHandlers.ofString());
            } catch (Exception e) {
                FAILURES.add("insecureSslContext(): handshake against a hostname-mismatched "
                        + "cert should have succeeded but threw " + e);
                return;
            }
            assertTrue("insecureSslContext(): HTTP request against a hostname-mismatched "
                    + "cert succeeds", resp.statusCode() == 200);
        });
    }

    private static void testValidatingContextRejectsHostnameMismatchOverHttpClient()
            throws Exception {
        withMismatchedCertServer((baseUrl, trustStore) -> {
            // A normal validating context: trusts the server's cert chain (so any
            // failure below is purely the hostname check, not an untrusted-CA
            // failure) but performs the standard endpoint identity check that
            // HttpClient always requests.
            javax.net.ssl.TrustManagerFactory tmf = javax.net.ssl.TrustManagerFactory
                    .getInstance(javax.net.ssl.TrustManagerFactory.getDefaultAlgorithm());
            tmf.init(trustStore);
            javax.net.ssl.SSLContext validatingCtx = javax.net.ssl.SSLContext.getInstance("TLS");
            validatingCtx.init(null, tmf.getTrustManagers(), null);

            java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
                    .sslContext(validatingCtx)
                    .build();
            // Assert the SPECIFIC identity failure, not merely "something threw".
            // a bind refusal, a connect timeout, or a DNS hiccup would also throw
            // and would otherwise pass this guard even though it proves nothing
            // about hostname verification.
            try {
                client.send(
                        java.net.http.HttpRequest.newBuilder(java.net.URI.create(baseUrl)).build(),
                        java.net.http.HttpResponse.BodyHandlers.ofString());
                FAILURES.add("validating context: handshake against a hostname-mismatched "
                        + "cert should have failed but succeeded (sanity check, this would "
                        + "catch a fix that disables everything)");
            } catch (Exception e) {
                Throwable identityFailure = findIdentityFailureCause(e);
                assertTrue("validating context: handshake fails with the hostname-identity "
                        + "failure (SSLHandshakeException / CertificateException naming "
                        + "\"subject alternative names\"), not merely some exception. "
                        + "Actual: " + e,
                        identityFailure != null);
            }
        });
    }

    /**
     * Walk {@code e}'s cause chain looking for the specific TLS hostname-identity
     * failure: an {@link javax.net.ssl.SSLHandshakeException} or
     * {@link java.security.cert.CertificateException} whose message names the
     * "subject alternative names" mismatch. Returns {@code null} if the chain
     * does not contain one. Used to distinguish the real identity-check failure
     * from an unrelated connection failure (bind refusal, timeout, DNS hiccup)
     * that would also throw but proves nothing about hostname verification.
     */
    private static Throwable findIdentityFailureCause(Throwable e) {
        for (Throwable t = e; t != null; t = t.getCause()) {
            boolean rightType = t instanceof javax.net.ssl.SSLHandshakeException
                    || t instanceof java.security.cert.CertificateException;
            String msg = t.getMessage();
            if (rightType && msg != null
                    && msg.toLowerCase(java.util.Locale.ROOT).contains("subject alternative name")) {
                return t;
            }
        }
        return null;
    }

    @FunctionalInterface
    private interface MismatchedCertServerTest {
        void run(String baseUrl, java.security.KeyStore trustStore) throws Exception;
    }

    private static final java.time.Duration KEYTOOL_TIMEOUT = java.time.Duration.ofSeconds(30);

    /**
     * Stand up a local HTTPS endpoint (on 127.0.0.1) whose certificate is
     * issued to {@link #MISMATCHED_CERT_CN}, not the loopback address used to
     * connect, run {@code test} against it, then tear the server down.
     *
     * <p>The keypair/certificate is generated fresh per invocation with the
     * JDK's own {@code keytool} (no checked-in fixture, avoids a stale/expired
     * cert bit-rotting in the repo). Resolved from {@code java.home} rather than
     * {@code PATH} since that is the JDK actually running this test; if that
     * {@code java.home} has no {@code bin/keytool} (a jlink'd/JRE-only image),
     * this SKIPs the caller rather than failing the suite. Same pattern
     * {@code AmbientCredentialTest} uses for the unavailable-{@code Crypt} case.
     */
    private static void withMismatchedCertServer(MismatchedCertServerTest test) throws Exception {
        java.io.File keytoolFile = keytool();
        if (keytoolFile == null) {
            System.out.println("  SKIP: hostname-mismatch TLS handshake test (keytool not found "
                    + "under " + System.getProperty("java.home") + "; this JDK image has no keytool)");
            return;
        }

        java.nio.file.Path tmpDir = java.nio.file.Files.createTempDirectory("vcfcf-adapter-test-ssl");
        try {
            java.security.KeyStore ks = generateKeyPair(keytoolFile,
                    tmpDir.resolve("mismatched.p12"), MISMATCHED_CERT_CN);
            // ks (a PrivateKeyEntry keystore) doubles as a trust store: JSSE's
            // TrustManagerFactory accepts the certificate chain attached to a
            // PrivateKeyEntry as a trusted cert, same as it would a plain
            // TrustedCertificateEntry.
            withHttpsServer(ks, baseUrl -> test.run(baseUrl, ks));
        } finally {
            deleteRecursivelyQuietly(tmpDir);
        }
    }

    /** The running JDK's keytool, or {@code null} when this image has none. */
    private static java.io.File keytool() {
        java.io.File keytoolFile = new java.io.File(System.getProperty("java.home"),
                "bin" + java.io.File.separator + "keytool");
        return keytoolFile.isFile() ? keytoolFile : null;
    }

    /** Generate a fresh self-signed RSA keypair for {@code cn} (alias vcfcf-test) and load it. */
    private static java.security.KeyStore generateKeyPair(java.io.File keytoolFile,
            java.nio.file.Path keystorePath, String cn) throws Exception {
        Process p = new ProcessBuilder(
                keytoolFile.getPath(),
                "-genkeypair",
                "-alias", "vcfcf-test",
                "-keyalg", "RSA",
                "-keysize", "2048",
                "-validity", "1",
                "-storetype", "PKCS12",
                "-keystore", keystorePath.toString(),
                "-storepass", KEYSTORE_PASSWORD,
                "-keypass", KEYSTORE_PASSWORD,
                "-dname", "CN=" + cn,
                "-ext", "SAN=dns:" + cn)
                .redirectErrorStream(true)
                .start();
        String keytoolOutput = new String(p.getInputStream().readAllBytes(),
                java.nio.charset.StandardCharsets.UTF_8);
        boolean finished = p.waitFor(KEYTOOL_TIMEOUT.toSeconds(), java.util.concurrent.TimeUnit.SECONDS);
        if (!finished) {
            p.destroyForcibly();
            throw new IllegalStateException("keytool -genkeypair did not finish within "
                    + KEYTOOL_TIMEOUT + " (process killed): " + keytoolOutput);
        }
        int exit = p.exitValue();
        if (exit != 0) {
            throw new IllegalStateException("keytool -genkeypair failed (exit " + exit
                    + "): " + keytoolOutput);
        }
        java.security.KeyStore ks = java.security.KeyStore.getInstance("PKCS12");
        try (java.io.InputStream in = java.nio.file.Files.newInputStream(keystorePath)) {
            ks.load(in, KEYSTORE_PASSWORD.toCharArray());
        }
        return ks;
    }

    @FunctionalInterface
    private interface BaseUrlTest {
        void run(String baseUrl) throws Exception;
    }

    /** Serve 200 {"ok":true} on 127.0.0.1 with {@code ks}'s key, run {@code test}, stop. */
    private static void withHttpsServer(java.security.KeyStore ks, BaseUrlTest test)
            throws Exception {
        withHttpsServer(ks, null, test);
    }

    /**
     * As {@link #withHttpsServer(java.security.KeyStore, BaseUrlTest)}; when
     * {@code requiredClient} is non-null the server requires client auth and
     * trusts only that keystore's certificate.
     */
    private static void withHttpsServer(java.security.KeyStore ks,
            java.security.KeyStore requiredClient, BaseUrlTest test) throws Exception {
        javax.net.ssl.KeyManagerFactory kmf = javax.net.ssl.KeyManagerFactory
                .getInstance("SunX509");
        kmf.init(ks, KEYSTORE_PASSWORD.toCharArray());
        javax.net.ssl.TrustManager[] serverTrust = null;
        if (requiredClient != null) {
            javax.net.ssl.TrustManagerFactory tmf = javax.net.ssl.TrustManagerFactory
                    .getInstance(javax.net.ssl.TrustManagerFactory.getDefaultAlgorithm());
            tmf.init(requiredClient);
            serverTrust = tmf.getTrustManagers();
        }
        javax.net.ssl.SSLContext serverCtx = javax.net.ssl.SSLContext.getInstance("TLS");
        serverCtx.init(kmf.getKeyManagers(), serverTrust, null);

        com.sun.net.httpserver.HttpsServer server = com.sun.net.httpserver.HttpsServer.create(
                new java.net.InetSocketAddress("127.0.0.1", 0), 0);
        final boolean needClientAuth = requiredClient != null;
        server.setHttpsConfigurator(new com.sun.net.httpserver.HttpsConfigurator(serverCtx) {
            @Override
            public void configure(com.sun.net.httpserver.HttpsParameters params) {
                javax.net.ssl.SSLParameters sp = getSSLContext().getDefaultSSLParameters();
                sp.setNeedClientAuth(needClientAuth);
                params.setSSLParameters(sp);
            }
        });
        server.createContext("/", ex -> {
            byte[] body = "{\"ok\":true}".getBytes(java.nio.charset.StandardCharsets.UTF_8);
            ex.sendResponseHeaders(200, body.length);
            try (java.io.OutputStream os = ex.getResponseBody()) {
                os.write(body);
            }
        });
        server.start();
        try {
            test.run("https://127.0.0.1:" + server.getAddress().getPort() + "/");
        } finally {
            server.stop(0);
        }
    }

    /**
     * Best-effort recursive delete that never throws. Used from a {@code finally}
     * block so a leftover-file cleanup failure can never mask the real assertion
     * failure from the test it is cleaning up after.
     */
    private static void deleteRecursivelyQuietly(java.nio.file.Path root) {
        try {
            if (!java.nio.file.Files.exists(root)) {
                return;
            }
            try (java.util.stream.Stream<java.nio.file.Path> walk = java.nio.file.Files.walk(root)) {
                walk.sorted(java.util.Comparator.reverseOrder())
                        .forEach(p -> {
                            try {
                                java.nio.file.Files.deleteIfExists(p);
                            } catch (Exception ignored) {
                                // Best-effort only, see method javadoc.
                            }
                        });
            }
        } catch (Exception ignored) {
            // Best-effort only, see method javadoc.
        }
    }

    // -----------------------------------------------------------------------
    // Harness
    // -----------------------------------------------------------------------

    private static void assertTrue(String label, boolean cond) {
        if (cond) {
            System.out.println("  PASS: " + label);
            passed++;
        } else {
            System.out.println("  FAIL: " + label);
            FAILURES.add(label);
        }
    }

    private static void assertFalse(String label, boolean cond) {
        assertTrue(label, !cond);
    }

    private static void report() {
        int total = passed + FAILURES.size();
        System.out.println();
        if (FAILURES.isEmpty()) {
            System.out.println("OK: " + passed + "/" + total + " tests passed.");
        } else {
            System.out.println("FAIL: " + FAILURES.size() + "/" + total
                    + " tests failed: " + FAILURES);
            System.exit(1);
        }
    }
}
