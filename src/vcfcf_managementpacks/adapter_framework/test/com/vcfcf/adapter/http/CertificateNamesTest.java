package com.vcfcf.adapter.http;

import com.vcfcf.adapter.VcfCfAdapter;
import com.vcfcf.adapter.retry.RetryPolicy;
import com.vcfcf.adapter.spi.VcfCfCollector;
import com.vcfcf.adapter.spi.VcfCfTester;

import com.integrien.alive.common.adapter3.ResourceStatus;
import com.integrien.alive.common.adapter3.config.ResourceConfig;

import com.sun.net.httpserver.HttpsConfigurator;
import com.sun.net.httpserver.HttpsServer;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.net.URL;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyStore;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLEngine;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509ExtendedTrustManager;

/**
 * Opt-in certificate name checking (issues #185, #206), ported from the
 * compliance pak's {@code CertificateTest} (builds 93 and 94): the matcher,
 * the dialled-host parser, every {@code checkServerTrusted} overload with no
 * peer host, a real {@code SSLEngine} handshake with no peer host, and real
 * HTTPS handshakes against a local server presenting a wrong-name certificate
 * through a chain-only trust manager standing in for the platform's
 * {@code CustomTrustManager}. Also the framework wiring:
 * {@code VcfCfAdapter.getPlatformSslContext(String)} and
 * {@code HttpClientBuilder.platformSsl(adapter, host)} refuse the wrong name,
 * while the unchanged no-argument {@code getPlatformSslContext()} still
 * accepts it (opt-in: default behaviour of existing paks is unchanged).
 *
 * <p>Certificates are made with the JDK's keytool; the test SKIPs the
 * certificate groups when there is none. No JUnit: call via {@code main()}.
 *
 * <p>Run:
 * <pre>
 *   javac -cp adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         adapter_framework/test/com/vcfcf/adapter/http/CertificateNamesTest.java \
 *         -d build/test-classes
 *   java -cp build/test-classes:adapter_runtime/vrops-adapters-sdk-2.2.jar:adapter_runtime/vcfcf-adapter-base.jar \
 *         com.vcfcf.adapter.http.CertificateNamesTest
 * </pre>
 */
public class CertificateNamesTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;

    public static void main(String[] args) throws Exception {
        expectedHosts();
        mismatchClassifier();
        File keytool = keytool();
        if (keytool == null) {
            System.out.println("  SKIP: certificate groups (no keytool in java.home)");
            report();
            return;
        }
        Path dir = Files.createTempDirectory("vcfcf-certnames-test");
        try {
            nameMatching(dir);
            noPeerHostOverloads(dir);
            noPeerHostHandshake(dir);
            wrongNameHttps(dir);
            frameworkWiring(dir);
            onTestRealNameFailures(dir);
        } finally {
            deleteTree(dir.toFile());
        }
        report();
    }

    // ----- the dialled host --------------------------------------------------

    static void expectedHosts() {
        eq("plain FQDN", "vc01.lab.local", CertificateNames.expectedHost("vc01.lab.local"));
        eq("trimmed, lower case, no trailing dot", "vc01.lab.local",
                CertificateNames.expectedHost("  VC01.Lab.Local. "));
        eq("port stripped", "vc01.lab.local", CertificateNames.expectedHost("vc01.lab.local:8443"));
        eq("IPv4 with port", "10.0.0.5", CertificateNames.expectedHost("10.0.0.5:443"));
        eq("bracketed IPv6", "fd00::5", CertificateNames.expectedHost("[fd00::5]"));
        eq("bracketed IPv6 with port", "fd00::5", CertificateNames.expectedHost("[fd00::5]:443"));
        eq("bare IPv6 taken whole", "fd00::5", CertificateNames.expectedHost("fd00::5"));
        eq("underscore and hyphen kept", "vc_01.lab-1.local",
                CertificateNames.expectedHost("vc_01.lab-1.local"));
        for (String none : new String[] {null, "", "   ", "https://vc01", "vc01/sdk",
                "vc 01", "vc?.example.org", "vc#.example.org", "user@vc01",
                "vc%2e.example.org"}) {
            eq("no usable host: '" + none + "'", null, CertificateNames.expectedHost(none));
        }
    }

    static void mismatchClassifier() {
        check("JDK 17 HttpsURLConnection text is a name mismatch",
                CertificateNames.isNameMismatch(new java.io.IOException(
                        "HTTPS hostname wrong:  should be <10.0.0.5>")));
        check("JDK 25 HttpsURLConnection text is a name mismatch",
                CertificateNames.isNameMismatch(new java.io.IOException(
                        "Wrong HTTPS hostname: should be <localhost>")));
        check("JDK hostname checker text, nested, is a name mismatch",
                CertificateNames.isNameMismatch(new RuntimeException("x",
                        new CertificateException("No name matching vc found"))));
        check("an unrelated 'hostname ... should be' is not",
                !CertificateNames.isNameMismatch(new java.net.UnknownHostException(
                        "hostname vc01 should be resolvable")));
        check("a PKIX failure is not a name mismatch",
                !CertificateNames.isNameMismatch(new javax.net.ssl.SSLHandshakeException(
                        "PKIX path building failed")));
        Exception a = new Exception("a");
        Exception b = new Exception("b", a);
        a.addSuppressed(b);
        check("cyclic cause graph terminates", !CertificateNames.isNameMismatch(a));
        check("null is not a name mismatch", !CertificateNames.isNameMismatch(null));

        // Issue #185 review B1: the host named by a mismatch, and the no-host refusal.
        eq("mismatchedHost: framework text", "vc02.lab.local", CertificateNames.mismatchedHost(
                new javax.net.ssl.SSLHandshakeException("x").initCause(new CertificateException(
                        "No subject alternative name matching vc02.lab.local in the target "
                        + "certificate (subject CN=vc01)"))));
        eq("mismatchedHost: BouncyCastle wrapper", "vc02.lab.local", CertificateNames.mismatchedHost(
                new java.io.IOException("org.bouncycastle.tls.TlsFatalAlert: certificate_unknown(46)",
                        new CertificateException("No subject alternative name matching "
                                + "vc02.lab.local in the target certificate (subject CN=vc01)"))));
        eq("mismatchedHost: JDK DNS checker", "localhost", CertificateNames.mismatchedHost(
                new CertificateException("No subject alternative DNS name matching localhost found.")));
        eq("mismatchedHost: JDK IP checker", "10.0.0.6", CertificateNames.mismatchedHost(
                new CertificateException(
                        "No subject alternative names matching IP address 10.0.0.6 found")));
        eq("mismatchedHost: JDK CN checker", "vc", CertificateNames.mismatchedHost(
                new CertificateException("No name matching vc found")));
        eq("mismatchedHost: HttpsURLConnection", "10.0.0.5", CertificateNames.mismatchedHost(
                new java.io.IOException("HTTPS hostname wrong:  should be <10.0.0.5>")));
        eq("mismatchedHost: none", null, CertificateNames.mismatchedHost(
                new java.io.IOException("Connection refused")));
        check("isNoUsableHost: nested refusal", CertificateNames.isNoUsableHost(
                new RuntimeException("x", new CertificateException(CertificateNames.NO_HOST_MESSAGE))));
        check("isNoUsableHost: a mismatch is not", !CertificateNames.isNoUsableHost(
                new CertificateException("No name matching vc found")));
        check("isNoUsableHost: null", !CertificateNames.isNoUsableHost(null));
        check("no-host text names the punycode form",
                CertificateNames.NO_HOST_MESSAGE.contains("punycode xn-- form"));
    }

    // ----- the matcher -------------------------------------------------------

    static void nameMatching(Path dir) throws Exception {
        X509Certificate both = cert(dir, "both", "CN=vc01.lab.local",
                "dns:vc01.lab.local,ip:10.0.0.5,ip:fd00:0:0:0:0:0:0:5");
        check("DNS SAN", CertificateNames.nameMatches("vc01.lab.local", both));
        check("case and trailing dot", CertificateNames.nameMatches("VC01.Lab.Local.", both));
        check("IP SAN", CertificateNames.nameMatches("10.0.0.5", both));
        check("bracketed IPv6 SAN", CertificateNames.nameMatches("[fd00::5]", both));
        check("short name not on the certificate", !CertificateNames.nameMatches("vc01", both));
        check("other IP", !CertificateNames.nameMatches("10.0.0.6", both));
        check("suffix", !CertificateNames.nameMatches("vc01.lab.local.evil", both));
        check("null host", !CertificateNames.nameMatches(null, both));
        check("blank host", !CertificateNames.nameMatches(" ", both));

        check("out-of-range octet is not an IP literal",
                !CertificateNames.isIpLiteral(CertificateNames.normalizeHost("300.1.1.1")));
        check("octet 256 is not an IP literal",
                !CertificateNames.isIpLiteral(CertificateNames.normalizeHost("10.0.0.256")));
        check("dotted quad is an IP literal",
                CertificateNames.isIpLiteral(CertificateNames.normalizeHost("10.0.0.1")));
        check("bracketed IPv6 is an IP literal",
                CertificateNames.isIpLiteral(CertificateNames.normalizeHost("[::1]")));
        check("hostname is not an IP literal",
                !CertificateNames.isIpLiteral(CertificateNames.normalizeHost("vc01.lab.local")));
        check("out-of-range dotted host does not match",
                !CertificateNames.nameMatches("300.1.1.1", both));

        X509Certificate wild = cert(dir, "wild", "CN=wild", "dns:*.lab.local,dns:*.com");
        check("wildcard, one label", CertificateNames.nameMatches("vc02.lab.local", wild));
        check("wildcard covers one label only",
                !CertificateNames.nameMatches("a.vc02.lab.local", wild));
        check("wildcard needs a label", !CertificateNames.nameMatches("lab.local", wild));
        check("no wildcard directly under a top-level label",
                !CertificateNames.nameMatches("example.com", wild));
        check("CN ignored when DNS SANs exist", !CertificateNames.nameMatches("wild", wild));

        X509Certificate cnOnly = cert(dir, "cn", "CN=vc03.lab.local, O=Lab", null);
        check("CN used when there are no DNS SANs",
                CertificateNames.nameMatches("vc03.lab.local", cnOnly));
        check("other CN", !CertificateNames.nameMatches("vc04.lab.local", cnOnly));

        X509Certificate ipCn = cert(dir, "ipcn", "CN=10.0.0.9", null);
        check("an IP never matches the CN", !CertificateNames.nameMatches("10.0.0.9", ipCn));

        X509Certificate ipOnly = cert(dir, "iponly", "CN=vc05.lab.local", "ip:10.0.0.7");
        check("no DNS SAN: the CN is used for a DNS name",
                CertificateNames.nameMatches("vc05.lab.local", ipOnly));
        check("IP SAN mismatch", !CertificateNames.nameMatches("10.0.0.5", ipOnly));

        for (String h : new String[] {null, "", "  "}) {
            try {
                CertificateNames.checkName(h, new X509Certificate[] {both});
                check("no host must be refused: '" + h + "'", false);
            } catch (CertificateException expected) {
                eq("fail closed text: '" + h + "'", CertificateNames.NO_HOST_MESSAGE,
                        expected.getMessage());
                check("fail closed is not read as a name mismatch",
                        !CertificateNames.isNameMismatch(expected));
            }
        }
    }

    // ----- no peer host (BouncyCastle JSSE on 9.1.1 collectors) ---------------

    /**
     * Every checkServerTrusted overload, handed a socket and an engine that
     * report no peer host, passes the right name and refuses the wrong one.
     */
    static void noPeerHostOverloads(Path dir) throws Exception {
        X509Certificate vc = cert(dir, "nph", "CN=vc01.lab.local",
                "dns:vc01.lab.local,ip:10.0.0.5,ip:fd00:0:0:0:0:0:0:5");
        X509Certificate[] chain = {vc};
        Socket plain = new Socket();
        javax.net.ssl.SSLSocket ssl = (javax.net.ssl.SSLSocket)
                javax.net.ssl.SSLSocketFactory.getDefault().createSocket();
        SSLEngine engine = SSLContext.getDefault().createSSLEngine();
        eq("engine: no peer host", null, engine.getPeerHost());
        try {
            for (String entered : new String[] {"vc01.lab.local", "VC01.lab.local:443",
                    "10.0.0.5", "[fd00::5]:443"}) {
                X509ExtendedTrustManager tm = trustManager(new ChainOnly(vc), entered);
                try {
                    tm.checkServerTrusted(chain, "ECDHE_ECDSA");
                    tm.checkServerTrusted(chain, "ECDHE_ECDSA", plain);
                    tm.checkServerTrusted(chain, "ECDHE_ECDSA", ssl);
                    tm.checkServerTrusted(chain, "ECDHE_ECDSA", (Socket) null);
                    tm.checkServerTrusted(chain, "ECDHE_ECDSA", engine);
                    tm.checkServerTrusted(chain, "ECDHE_ECDSA", (SSLEngine) null);
                    check("every overload passes the right name " + entered, true);
                } catch (CertificateException e) {
                    check("every overload passes the right name " + entered + ": " + e, false);
                }
            }
            for (String entered : new String[] {"vc02.lab.local", "vc01", "10.0.0.6",
                    "[fd00::6]"}) {
                overloadsRefuse(trustManager(new ChainOnly(vc), entered), chain, plain,
                        ssl, engine, Boolean.TRUE, false, "wrong name " + entered);
            }
            for (String entered : new String[] {null, "", "https://vc01"}) {
                String m = overloadsRefuse(trustManager(new ChainOnly(vc), entered), chain,
                        plain, ssl, engine, Boolean.FALSE, false, "no host '" + entered + "'");
                eq("fail closed text, no host '" + entered + "'",
                        CertificateNames.NO_HOST_MESSAGE, m);
            }
            // An authority-splitting host fails closed even where the
            // dialable name under the same wildcard would pass.
            X509Certificate wild = cert(dir, "nphw", "CN=wild", "dns:*.example.org");
            X509Certificate[] wildChain = {wild};
            try {
                trustManager(new ChainOnly(wild), "vc.example.org")
                        .checkServerTrusted(wildChain, "ECDHE_ECDSA", engine);
                check("wildcard, dialable name passes", true);
            } catch (CertificateException e) {
                check("wildcard, dialable name passes: " + e, false);
            }
            for (String entered : new String[] {"vc?.example.org", "vc#.example.org"}) {
                String m = overloadsRefuse(trustManager(new ChainOnly(wild), entered),
                        wildChain, plain, ssl, engine, Boolean.FALSE, false,
                        "authority-splitting host '" + entered + "'");
                eq("fail closed text, '" + entered + "'", CertificateNames.NO_HOST_MESSAGE, m);
            }
            // The platform chain check runs first, unchanged: its failure is
            // the platform's own exception (the accept dialog), even with a
            // wrong name too.
            X509Certificate other = cert(dir, "nph2", "CN=other", "dns:other");
            overloadsRefuse(trustManager(new ChainOnly(other), "vc02.lab.local"), chain,
                    plain, ssl, engine, Boolean.FALSE, true, "untrusted chain");
        } finally {
            plain.close();
            ssl.close();
        }
    }

    private static X509ExtendedTrustManager trustManager(X509ExtendedTrustManager platform,
            String entered) {
        return new CertificateNames.NameCheckingTrustManager(platform,
                CertificateNames.expectedHost(entered));
    }

    private interface Call { int run() throws Exception; }

    /**
     * All four server overloads must refuse with a CertificateException.
     * {@code nameMismatch}: whether it must (TRUE) or must not (FALSE) read as
     * a name mismatch. {@code platformFailure}: the exception is the
     * platform's own. Returns the last message.
     */
    private static String overloadsRefuse(X509ExtendedTrustManager tm, X509Certificate[] chain,
            Socket plain, Socket ssl, SSLEngine engine, Boolean nameMismatch,
            boolean platformFailure, String what) {
        List<Call> calls = new ArrayList<>();
        calls.add(() -> { tm.checkServerTrusted(chain, "EC"); return 0; });
        calls.add(() -> { tm.checkServerTrusted(chain, "EC", plain); return 0; });
        calls.add(() -> { tm.checkServerTrusted(chain, "EC", ssl); return 0; });
        calls.add(() -> { tm.checkServerTrusted(chain, "EC", engine); return 0; });
        String last = null;
        int i = 0;
        for (Call c : calls) {
            i++;
            try {
                c.run();
                check(what + ": overload " + i + " refused", false);
            } catch (Exception e) {
                check(what + ": overload " + i + " threw a CertificateException",
                        e instanceof CertificateException);
                eq(what + ": overload " + i + " name mismatch", nameMismatch,
                        CertificateNames.isNameMismatch(e));
                eq(what + ": overload " + i + " platform's own exception", platformFailure,
                        e instanceof CustomCertificateException);
                last = e.getMessage();
            }
        }
        return last;
    }

    /**
     * A real TLS handshake in which the provider reports no peer host: an
     * in-memory SSLEngine pair with the client engine made with no host. The
     * right dialled host passes, a wrong one is refused as a name mismatch, a
     * blank one fails closed.
     */
    static void noPeerHostHandshake(Path dir) throws Exception {
        KeyStore ks = keystore(dir, "nphsrv", "CN=vc01.lab.local",
                "dns:vc01.lab.local,ip:127.0.0.1");
        X509Certificate c = (X509Certificate) ks.getCertificate("vc");
        SSLContext srvCtx = serverContext(ks);
        for (String entered : new String[] {"vc01.lab.local", "127.0.0.1:443",
                "VC01.lab.local."}) {
            PeerHostProbe probe = new PeerHostProbe(c);
            try {
                engineHandshake(CertificateNames.nameCheckingContext(probe, null, entered),
                        srvCtx);
                check("engine handshake, no peer host, right name passes: " + entered,
                        probe.called && probe.peerHost == null);
            } catch (Exception e) {
                check("engine handshake, right name passes: " + entered + ": " + e, false);
            }
        }
        PeerHostProbe probe = new PeerHostProbe(c);
        try {
            engineHandshake(CertificateNames.nameCheckingContext(probe, null,
                    "vc02.lab.local"), srvCtx);
            check("engine handshake, wrong dialled host refused", false);
        } catch (Exception e) {
            check("engine handshake, wrong dialled host refused as a name mismatch: " + e,
                    CertificateNames.isNameMismatch(e));
            check("platform chain check ran first, no peer host",
                    probe.called && probe.peerHost == null);
        }
        try {
            engineHandshake(CertificateNames.nameCheckingContext(new PeerHostProbe(c), null,
                    "  "), srvCtx);
            check("engine handshake, blank dialled host refused", false);
        } catch (Exception e) {
            check("engine handshake, blank dialled host fails closed: " + e,
                    String.valueOf(e.getMessage()).contains("no usable host"));
        }
    }

    // ----- the wrong-name HTTPS test -----------------------------------------

    /**
     * A local HTTPS server presents a certificate for othername.example; the
     * clients dial it as localhost and 127.0.0.1. The client trust manager
     * trusts that exact certificate and checks the chain only, as the
     * platform's CustomTrustManager does.
     */
    static void wrongNameHttps(Path dir) throws Exception {
        KeyStore wrongKs = keystore(dir, "wrongsrv", "CN=othername.example",
                "dns:othername.example");
        KeyStore rightKs = keystore(dir, "rightsrv", "CN=localhost",
                "dns:localhost,ip:127.0.0.1");
        X509Certificate wrongCert = (X509Certificate) wrongKs.getCertificate("vc");
        X509Certificate rightCert = (X509Certificate) rightKs.getCertificate("vc");
        HttpsServer wrong = server(wrongKs);
        HttpsServer right = server(rightKs);
        try {
            int wp = wrong.getAddress().getPort();
            int rp = right.getAddress().getPort();
            SSLContext chainOnly = context(new ChainOnly(wrongCert));
            SSLContext enforced = CertificateNames.nameCheckingContext(
                    new ChainOnly(wrongCert), null, "localhost");
            SSLContext enforcedIp = CertificateNames.nameCheckingContext(
                    new ChainOnly(wrongCert), null, "127.0.0.1:" + wp);

            // Controls: why the name has to be checked by the framework.
            eq("control: a chain-only trust manager lets HttpClient accept a wrong-name "
                    + "certificate", 200, status(() -> httpClient(chainOnly,
                            "https://localhost:" + wp + "/")));
            eq("control: the JDK default hostname verifier, set explicitly, enforces "
                    + "nothing either", 200, status(() -> urlConnection(
                            chainOnly.getSocketFactory(),
                            HttpsURLConnection.getDefaultHostnameVerifier(),
                            "https://localhost:" + wp + "/")));

            // The opt-in, every client shape.
            refusedAsMismatch("HttpClient, name-checking context, as localhost",
                    () -> httpClient(enforced, "https://localhost:" + wp + "/"));
            refusedAsMismatch("HttpsURLConnection + secure(), name-checking factory, as "
                    + "localhost", () -> urlConnection(enforced.getSocketFactory(), null,
                            "https://localhost:" + wp + "/"));
            refusedAsMismatch("HttpsURLConnection + secure(), as 127.0.0.1",
                    () -> urlConnection(enforcedIp.getSocketFactory(), null,
                            "https://127.0.0.1:" + wp + "/"));
            refusedAsMismatch("HttpsURLConnection + strict verifier alone, chain-only "
                    + "factory", () -> urlConnection(chainOnly.getSocketFactory(), null,
                            "https://localhost:" + wp + "/"));

            // An untrusted chain is still the platform's failure (the accept
            // dialog), even when the name is wrong too.
            SSLContext untrusted = CertificateNames.nameCheckingContext(
                    new ChainOnly(rightCert), null, "localhost");
            try {
                httpClient(untrusted, "https://localhost:" + wp + "/");
                check("untrusted chain must fail", false);
            } catch (Exception e) {
                check("untrusted chain: the platform's exception, not a name mismatch: " + e,
                        hasCause(e, CustomCertificateException.class)
                                && !CertificateNames.isNameMismatch(e));
            }

            // The right name passes, by DNS name and by IP.
            for (String host : new String[] {"localhost", "127.0.0.1"}) {
                SSLContext ok = CertificateNames.nameCheckingContext(
                        new ChainOnly(rightCert), null, host + ":" + rp);
                String u = "https://" + host + ":" + rp + "/";
                eq("HttpClient, right name " + host, 200, status(() -> httpClient(ok, u)));
                eq("secure(), right name " + host, 200,
                        status(() -> urlConnection(ok.getSocketFactory(), null, u)));
            }
        } finally {
            wrong.stop(0);
            right.stop(0);
        }
    }

    // ----- framework wiring: opt-in only -------------------------------------

    /**
     * {@code getPlatformSslContext(host)} and {@code platformSsl(adapter, host)}
     * wrap the adapter's platform trust manager and refuse the wrong name;
     * the no-argument {@code getPlatformSslContext()} and
     * {@code platformSsl(adapter)} are unchanged and still accept it.
     */
    static void frameworkWiring(Path dir) throws Exception {
        KeyStore wrongKs = keystore(dir, "fwwrong", "CN=othername.example",
                "dns:othername.example");
        KeyStore rightKs = keystore(dir, "fwright", "CN=localhost", "dns:localhost");
        X509Certificate wrongCert = (X509Certificate) wrongKs.getCertificate("vc");
        X509Certificate rightCert = (X509Certificate) rightKs.getCertificate("vc");
        HttpsServer wrong = server(wrongKs);
        HttpsServer right = server(rightKs);
        try {
            String wu = "https://localhost:" + wrong.getAddress().getPort();
            String ru = "https://localhost:" + right.getAddress().getPort();
            WiringAdapter a = allocate(WiringAdapter.class);
            a.platform = new ChainOnly(wrongCert);

            eq("default getPlatformSslContext() unchanged: wrong name still accepted", 200,
                    status(() -> httpClient(a.getPlatformSslContext(), wu + "/")));
            eq("default platformSsl(adapter) unchanged: wrong name still accepted", 200,
                    status(() -> HttpClientBuilder.builder().baseUrl(wu).platformSsl(a)
                            .retryPolicy(noRetry()).build()
                            .get("/", HttpResponse.BodyHandlers.ofString()).statusCode()));
            refusedAsMismatch("opt-in getPlatformSslContext(host) refuses the wrong name",
                    () -> httpClient(a.getPlatformSslContext("localhost"), wu + "/"));
            refusedAsMismatch("opt-in platformSsl(adapter, host) refuses the wrong name",
                    () -> HttpClientBuilder.builder().baseUrl(wu)
                            .platformSsl(a, "localhost").retryPolicy(noRetry()).build()
                            .get("/", HttpResponse.BodyHandlers.ofString()).statusCode());

            a.platform = new ChainOnly(rightCert);
            eq("opt-in platformSsl(adapter, host:port), right name passes", 200,
                    status(() -> HttpClientBuilder.builder().baseUrl(ru)
                            .platformSsl(a, "localhost:" + right.getAddress().getPort())
                            .retryPolicy(noRetry()).build()
                            .get("/", HttpResponse.BodyHandlers.ofString()).statusCode()));
            boolean threw = false;
            try {
                a.platform = null;
                a.getPlatformSslContext("localhost");
            } catch (RuntimeException e) {
                threw = true;
            }
            check("opt-in with no platform trust manager throws, never trust-all", threw);
        } finally {
            wrong.stop(0);
            right.stop(0);
        }
    }

    /**
     * Review B1: Validate Connection on a pak that opted in to name checking,
     * against a real local HTTPS server presenting a trusted chain under the
     * wrong name. The failure reaches the framework's name text and the
     * #205 hook, not raw TLS text. Same for a blank host (fail closed).
     */
    static void onTestRealNameFailures(Path dir) throws Exception {
        KeyStore wrongKs = keystore(dir, "ontestwrong", "CN=othername.example",
                "dns:othername.example");
        X509Certificate wrongCert = (X509Certificate) wrongKs.getCertificate("vc");
        HttpsServer wrong = server(wrongKs);
        try {
            String wu = "https://localhost:" + wrong.getAddress().getPort();
            for (String entered : new String[] {"localhost", "  "}) {
                boolean noHost = entered.trim().isEmpty();
                WiringAdapter a = allocate(WiringAdapter.class);
                a.platform = new ChainOnly(wrongCert);
                a.warnings = new ArrayList<>();
                a.tester = (cfg, http, param) -> HttpClientBuilder.builder().baseUrl(wu)
                        .platformSsl(a, entered).retryPolicy(noRetry()).build()
                        .get("/", HttpResponse.BodyHandlers.ofString());
                com.integrien.alive.common.adapter3.TestParam p =
                        new com.integrien.alive.common.adapter3.TestParam(testConfig());
                String what = noHost ? "blank host" : "wrong name";
                check("onTest, " + what + ": returns false", !a.onTest(p));
                String msg = p.getErrorMsg();
                check("onTest, " + what + ": hook called once (" + a.hookCalls + ")",
                        a.hookCalls == 1);
                check("onTest, " + what + ": hook got the framework default",
                        a.sawDefault != null && a.sawDefault.equals(msg));
                if (noHost) {
                    check("onTest, blank host: no-host text; got " + msg,
                            msg != null && msg.startsWith(
                                    "The target's TLS certificate name cannot be checked")
                                    && msg.contains("punycode xn-- form"));
                    check("onTest, blank host: the hook can tell",
                            CertificateNames.isNoUsableHost(a.sawFailure));
                } else {
                    check("onTest, wrong name: names the host; got " + msg,
                            msg != null && msg.startsWith(
                                    "The target's TLS certificate does not name localhost.")
                                    && msg.contains("enter the host by a name on the certificate")
                                    && msg.contains("Accepting the certificate does not fix"));
                    check("onTest, wrong name: the hook can tell",
                            CertificateNames.isNameMismatch(a.sawFailure));
                }
                check("onTest, " + what + ": no Allow Insecure without the field",
                        msg != null && !msg.contains("Insecure"));
                check("onTest, " + what + ": no raw handshake text up front",
                        msg != null && !msg.startsWith("javax.net.ssl")
                                && !msg.startsWith("No subject"));
            }
        } finally {
            wrong.stop(0);
        }
    }

    /** AdapterConfig whose adapter-instance resource has a host identifier. */
    private static com.integrien.alive.common.adapter3.config.AdapterConfig testConfig() {
        com.integrien.alive.common.adapter3.ResourceKey key =
                new com.integrien.alive.common.adapter3.ResourceKey("inst", "test_kind_instance",
                        "test_kind");
        key.addIdentifier(new com.integrien.alive.common.adapter3.config.ResourceIdentifierConfig(
                "host", "localhost", true));
        com.integrien.alive.common.adapter3.config.AdapterConfig c =
                new com.integrien.alive.common.adapter3.config.AdapterConfig("test_kind", 1);
        c.setAdapterInstResource(new ResourceConfig(key));
        return c;
    }

    private static RetryPolicy noRetry() {
        return RetryPolicy.builder().maxAttempts(1).build();
    }

    /** Adapter whose platform trust manager is a test stand-in. */
    static class WiringAdapter extends VcfCfAdapter<Object> {
        TrustManager platform;
        VcfCfTester<Object> tester;
        List<String> warnings;
        int hookCalls;
        String sawDefault;
        Throwable sawFailure;

        @Override
        protected String certificateFailureMessage(Throwable failure, ResourceConfig config,
                String defaultMessage) {
            hookCalls++;
            sawFailure = failure;
            sawDefault = defaultMessage;
            return null;
        }

        @Override
        public com.integrien.alive.common.adapter3.describe.AdapterDescribe onDescribe() {
            throw new IllegalStateException("no describe.xml in this test");
        }

        @Override
        protected void logWarn(String message) {
            if (warnings != null) warnings.add(message);
        }

        @Override
        protected void logWarn(String message, Throwable t) {
            if (warnings != null) warnings.add(message);
        }

        @Override
        protected void configureAdapter(ResourceStatus s, ResourceConfig rc) {
        }

        @Override
        @SuppressWarnings("rawtypes")
        protected VcfCfTester getTester() {
            return tester;
        }

        @Override
        @SuppressWarnings("rawtypes")
        protected VcfCfCollector getCollector() {
            return null;
        }

        @Override
        public TrustManager getAdapterTrustManager() {
            return platform;
        }

        @Override
        public javax.net.ssl.KeyManager[] getKeyManagers() {
            return null;
        }
    }

    /** Skips constructors (AdapterBase needs the collector's log4j-core). */
    @SuppressWarnings("unchecked")
    private static <T> T allocate(Class<T> cls) throws Exception {
        java.lang.reflect.Field f = Class.forName("sun.misc.Unsafe").getDeclaredField("theUnsafe");
        f.setAccessible(true);
        Object unsafe = f.get(null);
        java.lang.reflect.Method m = unsafe.getClass().getMethod("allocateInstance", Class.class);
        return (T) m.invoke(unsafe, cls);
    }

    // ----- helpers -------------------------------------------------------------

    private static int status(Call c) {
        try {
            return c.run();
        } catch (Exception e) {
            return -1;
        }
    }

    private static void refusedAsMismatch(String what, Call c) {
        try {
            int code = c.run();
            check(what + ": wrong-name certificate accepted, HTTP " + code, false);
        } catch (Exception e) {
            check(what + ": refused as a name mismatch: " + e.getClass().getSimpleName()
                    + ": " + e.getMessage(), CertificateNames.isNameMismatch(e));
        }
    }

    private static boolean hasCause(Throwable t, Class<?> type) {
        for (Throwable c = t; c != null; c = c.getCause()) {
            if (type.isInstance(c)) return true;
            if (c.getCause() == c) break;
        }
        return false;
    }

    private static int httpClient(SSLContext ctx, String url) throws Exception {
        HttpClient c = HttpClient.newBuilder().sslContext(ctx)
                .connectTimeout(Duration.ofSeconds(10)).build();
        HttpResponse<String> r = c.send(HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(10)).GET().build(),
                HttpResponse.BodyHandlers.ofString());
        return r.statusCode();
    }

    /** {@code verifier} null: {@link CertificateNames#secure}; else that verifier. */
    private static int urlConnection(javax.net.ssl.SSLSocketFactory f,
            javax.net.ssl.HostnameVerifier verifier, String url) throws Exception {
        HttpsURLConnection conn = (HttpsURLConnection) new URL(url).openConnection();
        if (verifier == null) {
            CertificateNames.secure(conn, f);
        } else {
            conn.setSSLSocketFactory(f);
            conn.setHostnameVerifier(verifier);
        }
        conn.setConnectTimeout(10000);
        conn.setReadTimeout(10000);
        try {
            return conn.getResponseCode();
        } finally {
            conn.disconnect();
        }
    }

    private static SSLContext context(TrustManager tm) throws Exception {
        SSLContext ctx = SSLContext.getInstance("TLS");
        ctx.init(null, new TrustManager[] {tm}, null);
        return ctx;
    }

    private static SSLContext serverContext(KeyStore ks) throws Exception {
        KeyManagerFactory kmf = KeyManagerFactory.getInstance(
                KeyManagerFactory.getDefaultAlgorithm());
        kmf.init(ks, PASS);
        SSLContext ctx = SSLContext.getInstance("TLS");
        ctx.init(kmf.getKeyManagers(), null, null);
        return ctx;
    }

    static HttpsServer server(KeyStore ks) throws Exception {
        HttpsServer s = HttpsServer.create(new InetSocketAddress(
                InetAddress.getLoopbackAddress(), 0), 0);
        s.setHttpsConfigurator(new HttpsConfigurator(serverContext(ks)));
        s.createContext("/", ex -> {
            byte[] body = "ok".getBytes(StandardCharsets.UTF_8);
            ex.sendResponseHeaders(200, body.length);
            try (OutputStream os = ex.getResponseBody()) {
                os.write(body);
            }
        });
        s.start();
        return s;
    }

    /** Drive a client and a server SSLEngine to the end of the handshake. */
    private static void engineHandshake(SSLContext clientCtx, SSLContext serverCtx)
            throws Exception {
        SSLEngine cli = clientCtx.createSSLEngine();
        cli.setUseClientMode(true);
        SSLEngine srv = serverCtx.createSSLEngine();
        srv.setUseClientMode(false);
        int pkt = Math.max(cli.getSession().getPacketBufferSize(),
                srv.getSession().getPacketBufferSize());
        int app = Math.max(cli.getSession().getApplicationBufferSize(),
                srv.getSession().getApplicationBufferSize());
        java.nio.ByteBuffer empty = java.nio.ByteBuffer.allocate(0);
        java.nio.ByteBuffer c2s = java.nio.ByteBuffer.allocate(pkt * 4);
        java.nio.ByteBuffer s2c = java.nio.ByteBuffer.allocate(pkt * 4);
        java.nio.ByteBuffer cliIn = java.nio.ByteBuffer.allocate(app * 2);
        java.nio.ByteBuffer srvIn = java.nio.ByteBuffer.allocate(app * 2);
        cli.beginHandshake();
        srv.beginHandshake();
        for (int i = 0; i < 1000; i++) {
            if (done(cli) && done(srv)) return;
            step(cli, empty, c2s, s2c, cliIn);
            step(srv, empty, s2c, c2s, srvIn);
        }
        throw new IllegalStateException("handshake did not finish");
    }

    private static boolean done(SSLEngine e) {
        javax.net.ssl.SSLEngineResult.HandshakeStatus h = e.getHandshakeStatus();
        return h == javax.net.ssl.SSLEngineResult.HandshakeStatus.NOT_HANDSHAKING
                || h == javax.net.ssl.SSLEngineResult.HandshakeStatus.FINISHED;
    }

    private static void step(SSLEngine e, java.nio.ByteBuffer empty, java.nio.ByteBuffer out,
            java.nio.ByteBuffer in, java.nio.ByteBuffer appIn) throws Exception {
        Runnable task;
        while ((task = e.getDelegatedTask()) != null) task.run();
        switch (e.getHandshakeStatus()) {
            case NEED_WRAP:
                e.wrap(empty, out);
                break;
            case NEED_UNWRAP:
            case NEED_UNWRAP_AGAIN:
                in.flip();
                e.unwrap(in, appIn);
                in.compact();
                break;
            default:
                break;
        }
        while ((task = e.getDelegatedTask()) != null) task.run();
    }

    /** Chain-only platform stand-in that records the provider's peer host. */
    static final class PeerHostProbe extends X509ExtendedTrustManager {
        private final ChainOnly chain;
        volatile boolean called;
        volatile String peerHost;

        PeerHostProbe(X509Certificate trusted) {
            this.chain = new ChainOnly(trusted);
        }

        @Override
        public void checkServerTrusted(X509Certificate[] c, String a)
                throws CertificateException {
            called = true;
            chain.checkServerTrusted(c, a);
        }

        @Override
        public void checkServerTrusted(X509Certificate[] c, String a, Socket s)
                throws CertificateException {
            called = true;
            if (s instanceof javax.net.ssl.SSLSocket) {
                javax.net.ssl.SSLSession hs = ((javax.net.ssl.SSLSocket) s).getHandshakeSession();
                peerHost = hs == null ? null : hs.getPeerHost();
            }
            chain.checkServerTrusted(c, a);
        }

        @Override
        public void checkServerTrusted(X509Certificate[] c, String a, SSLEngine e)
                throws CertificateException {
            called = true;
            peerHost = e == null ? null : e.getPeerHost();
            chain.checkServerTrusted(c, a);
        }

        @Override
        public void checkClientTrusted(X509Certificate[] c, String a) {}

        @Override
        public void checkClientTrusted(X509Certificate[] c, String a, Socket s) {}

        @Override
        public void checkClientTrusted(X509Certificate[] c, String a, SSLEngine e) {}

        @Override
        public X509Certificate[] getAcceptedIssuers() {
            return chain.getAcceptedIssuers();
        }
    }

    /**
     * Trusts exactly {@code trusted} and checks the chain only, ignoring the
     * peer host: the platform CustomTrustManager's shape. An unknown
     * certificate fails with a stand-in for the platform's exception.
     */
    static final class ChainOnly extends X509ExtendedTrustManager {
        private final X509Certificate trusted;

        ChainOnly(X509Certificate trusted) {
            this.trusted = trusted;
        }

        @Override
        public void checkServerTrusted(X509Certificate[] chain, String a)
                throws CertificateException {
            if (chain == null || chain.length == 0 || !trusted.equals(chain[0])) {
                throw new CustomCertificateException("not accepted");
            }
        }

        @Override
        public void checkServerTrusted(X509Certificate[] chain, String a, Socket s)
                throws CertificateException {
            checkServerTrusted(chain, a);
        }

        @Override
        public void checkServerTrusted(X509Certificate[] chain, String a, SSLEngine e)
                throws CertificateException {
            checkServerTrusted(chain, a);
        }

        @Override
        public void checkClientTrusted(X509Certificate[] c, String a) {}

        @Override
        public void checkClientTrusted(X509Certificate[] c, String a, Socket s) {}

        @Override
        public void checkClientTrusted(X509Certificate[] c, String a, SSLEngine e) {}

        @Override
        public X509Certificate[] getAcceptedIssuers() {
            return new X509Certificate[] {trusted};
        }
    }

    /** Stands in for the platform's CustomCertificateException. */
    static final class CustomCertificateException extends CertificateException {
        CustomCertificateException(String m) { super(m); }
    }

    // ----- keytool ---------------------------------------------------------------

    static final char[] PASS = "changeit".toCharArray();

    private static File keytool() {
        File k = new File(System.getProperty("java.home"), "bin" + File.separator + "keytool");
        return k.isFile() ? k : null;
    }

    private static X509Certificate cert(Path dir, String name, String dname, String san)
            throws Exception {
        return (X509Certificate) keystore(dir, name, dname, san).getCertificate("vc");
    }

    /** A PKCS12 keystore with one self-signed EC key pair, alias "vc". */
    static KeyStore keystore(Path dir, String name, String dname, String san)
            throws Exception {
        File ks = dir.resolve(name + ".p12").toFile();
        List<String> cmd = new ArrayList<>(Arrays.asList(keytool().getPath(),
                "-genkeypair", "-alias", "vc", "-keyalg", "EC", "-groupname", "secp256r1",
                "-sigalg", "SHA256withECDSA", "-validity", "2", "-dname", dname,
                "-storetype", "PKCS12", "-keystore", ks.getPath(),
                "-storepass", new String(PASS), "-keypass", new String(PASS)));
        if (san != null) {
            cmd.add("-ext");
            cmd.add("SAN=" + san);
        }
        Process p = new ProcessBuilder(cmd).redirectErrorStream(true).start();
        String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        if (p.waitFor() != 0) {
            throw new IllegalStateException("keytool failed for " + name + ": " + out);
        }
        KeyStore k = KeyStore.getInstance("PKCS12");
        try (InputStream in = new FileInputStream(ks)) {
            k.load(in, PASS);
        }
        return k;
    }

    static void deleteTree(File f) {
        File[] kids = f.listFiles();
        if (kids != null) {
            for (File k : kids) deleteTree(k);
        }
        f.delete();
    }

    // ----- assertions ------------------------------------------------------------

    private static void check(String name, boolean cond) {
        if (cond) {
            passed++;
            System.out.println("  PASS: " + name);
        } else {
            FAILURES.add(name);
            System.out.println("  FAIL: " + name);
        }
    }

    private static void eq(String name, Object expected, Object actual) {
        boolean ok = expected == null ? actual == null : expected.equals(actual);
        check(name + " (expected " + expected + ", got " + actual + ")", ok);
    }

    private static void report() {
        System.out.println();
        int total = passed + FAILURES.size();
        if (FAILURES.isEmpty()) {
            System.out.println("OK: " + passed + "/" + total + " tests passed.");
        } else {
            System.out.println("FAIL: " + FAILURES.size() + "/" + total + " tests failed: "
                    + FAILURES);
            System.exit(1);
        }
    }
}
