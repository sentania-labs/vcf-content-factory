package com.vcfcf.adapter.http;

import java.net.InetAddress;
import java.net.Socket;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.KeyManager;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLEngine;
import javax.net.ssl.SSLSession;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509ExtendedTrustManager;
import javax.net.ssl.X509TrustManager;

/**
 * Opt-in certificate NAME checking for target-system connections (issues
 * #185, #206). No VCF Ops SDK dependency, so it is unit-testable with a plain
 * JDK.
 *
 * <h3>Why it exists</h3>
 * <p>The platform trust manager ({@code getAdapterTrustManager()}, a
 * {@code CustomTrustManager}) checks the certificate chain only. It extends
 * {@link X509ExtendedTrustManager}, so JSSE adds no endpoint-identity check of
 * its own, and both JDK HTTP clients leave the name to the trust manager
 * whenever the JDK's default {@link HostnameVerifier} is in effect (setting
 * that default explicitly changes nothing: {@code HttpsURLConnection}
 * recognises it by class). {@code java.net.http.HttpClient} has no verifier to
 * set at all. So with {@code getPlatformSslContext()} alone, a trusted chain
 * presented under the wrong name is accepted.
 *
 * <h3>What it does</h3>
 * <p>{@link #nameCheckingContext} wraps the platform trust manager: the
 * platform chain check runs first, unchanged (an untrusted chain fails exactly
 * as the platform threw it, so the Validate Connection accept dialog still
 * applies), then the leaf certificate must carry the host the client dials
 * (SAN, or the CN when there is no DNS SAN), during the handshake and so
 * before any credential is sent. The host is fixed when the context is built,
 * never the peer host the TLS provider reports: the BouncyCastle JSSE provider
 * on VCF Operations 9.1.1 collectors reports none on the sockets
 * {@code HttpsURLConnection} opens (compliance build 94).
 * {@link #secure} additionally sets {@link #strictHostnameVerifier()} on an
 * {@code HttpsURLConnection}, which makes the JDK's own name check run after
 * the handshake as well.
 *
 * <h3>Opt-in</h3>
 * <p>Nothing in the framework calls this on its own; an adapter that does not
 * call it behaves exactly as before. Entry points:
 * {@code VcfCfAdapter.getPlatformSslContext(String dialledHost)} and
 * {@link HttpClientBuilder#platformSsl(com.vcfcf.adapter.VcfCfAdapter, String)}.
 * The Suite API hop ({@code VcfCfAdapter.openPlatformConnection}) is never
 * name checked: it keeps the vendor-mirror trust-all and ignore-hostname
 * posture, which is what lets a loopback {@code localhost} call reach an
 * appliance whose certificate has no {@code localhost} name.
 *
 * <p>An account entered by IP address passes only when the certificate lists
 * that IP as an IP subject alternative name; the CN is never used for an IP.
 * Accepting the certificate in the Validate Connection dialog does not fix a
 * name mismatch: the admin enters the host by the name on its certificate.
 *
 * <p>Ported from the compliance pak ({@code VCenterCertificates}, builds 93
 * and 94), wording made target-neutral.
 */
public final class CertificateNames {

    private CertificateNames() {}

    // host, host:port, [v6], [v6]:port. An unbracketed host is hostname
    // characters only: a '?', '#' or '@' ends or splits a URL authority, so a
    // client would dial a different host than the one compared here
    // ("vc?.example.org" dials "vc").
    private static final Pattern HOST_PORT = Pattern.compile(
            "^(\\[[0-9A-Fa-f:.]+\\]|[A-Za-z0-9._-]+)(?::(\\d{1,5}))?$");

    private static final Pattern BARE_IPV6 =
            Pattern.compile("^[0-9A-Fa-f]*:[0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*$");

    private static final Pattern IPV4 =
            Pattern.compile("^\\d{1,3}(\\.\\d{1,3}){3}$");

    /** The fail-closed text when there is no host to match. */
    public static final String NO_HOST_MESSAGE = "The target certificate name "
            + "cannot be checked: no usable host was given for this connection. "
            + "Set the account's host to the name or address on the target's "
            + "certificate (no https://, no path).";

    /** The prefix of the name-mismatch text {@link #checkName} throws. */
    static final String MISMATCH_PREFIX = "No subject alternative name matching ";

    /**
     * An {@link SSLContext} whose trust manager is {@code platform} plus a
     * name check against {@code dialledHost}.
     *
     * @param platform    the platform trust manager
     *                    ({@code getAdapterTrustManager()}); must be an
     *                    {@link X509TrustManager}
     * @param keyManagers the platform key managers (may be null)
     * @param dialledHost the host the clients using this context connect to,
     *                    as the account entered it: {@code host},
     *                    {@code host:port}, {@code [v6]}, {@code [v6]:port}
     *                    or a bare IPv6 literal. Not a URL. See
     *                    {@link #expectedHost}. When it yields no host every
     *                    handshake is refused with {@link #NO_HOST_MESSAGE}
     *                    (fail closed), never passed.
     * @throws IllegalArgumentException when {@code platform} is not an
     *         {@link X509TrustManager}
     * @throws IllegalStateException when the context cannot be built
     */
    public static SSLContext nameCheckingContext(TrustManager platform,
            KeyManager[] keyManagers, String dialledHost) {
        if (!(platform instanceof X509TrustManager)) {
            throw new IllegalArgumentException("not an X509TrustManager: "
                    + (platform == null ? "null" : platform.getClass().getName()));
        }
        try {
            SSLContext ctx = SSLContext.getInstance("TLS");
            ctx.init(keyManagers, new TrustManager[] {
                    new NameCheckingTrustManager((X509TrustManager) platform,
                            expectedHost(dialledHost))},
                    null);
            return ctx;
        } catch (java.security.GeneralSecurityException e) {
            throw new IllegalStateException(
                    "could not build the name-checking TLS context: " + e, e);
        }
    }

    /**
     * Apply a socket factory (null keeps the connection's current one) and
     * {@link #strictHostnameVerifier()} to an {@code HttpsURLConnection}.
     * Per connection only; nothing JVM-wide is changed.
     */
    public static void secure(HttpsURLConnection conn, SSLSocketFactory factory) {
        if (factory != null) {
            conn.setSSLSocketFactory(factory);
        }
        conn.setHostnameVerifier(STRICT_HOSTNAMES);
    }

    /**
     * A hostname verifier that never overrides a failed name check.
     * {@code HttpsURLConnection} runs its own RFC 2818 check after the
     * handshake whenever the verifier is not the JDK default, and asks the
     * verifier only when that check fails, so answering no makes the JDK's
     * check final ("HTTPS hostname wrong" on JDK 17, "Wrong HTTPS hostname"
     * on JDK 25). The JDK default verifier cannot do this: with it the JDK
     * skips its own check and leaves the name to the trust manager.
     */
    public static HostnameVerifier strictHostnameVerifier() {
        return STRICT_HOSTNAMES;
    }

    private static final HostnameVerifier STRICT_HOSTNAMES = new JdkNameCheckIsFinal();

    /** See {@link #strictHostnameVerifier()}. */
    static final class JdkNameCheckIsFinal implements HostnameVerifier {
        @Override
        public boolean verify(String host, SSLSession session) {
            return false;
        }
    }

    /**
     * Whether {@code t}'s cause or suppressed graph (cycle safe) shows a
     * certificate NAME mismatch: the text {@link #checkName} throws, the JDK
     * hostname checker's ("No subject alternative ...", "No name matching"),
     * or {@code HttpsURLConnection}'s post-handshake rejection. A chain trust
     * failure is not a name mismatch.
     */
    public static boolean isNameMismatch(Throwable t) {
        Set<Throwable> seen = Collections.newSetFromMap(
                new IdentityHashMap<Throwable, Boolean>());
        java.util.ArrayDeque<Throwable> todo = new java.util.ArrayDeque<>();
        if (t != null) todo.add(t);
        while (!todo.isEmpty()) {
            Throwable cur = todo.poll();
            if (!seen.add(cur)) continue;
            String m = cur.getMessage();
            if (m != null && (m.contains("No subject alternative")
                    || m.contains("No name matching")
                    || isHostnameWrong(m))) {
                return true;
            }
            if (cur.getCause() != null) todo.add(cur.getCause());
            for (Throwable s : cur.getSuppressed()) {
                if (s != null) todo.add(s);
            }
        }
        return false;
    }

    /**
     * {@code HttpsURLConnection}'s post-handshake hostname rejection: JDK 17
     * says {@code HTTPS hostname wrong: should be <host>}, JDK 25
     * {@code Wrong HTTPS hostname: should be <host>}; also matched loosely
     * ("https hostname" plus "should be"). A bare "hostname" is not enough.
     */
    static boolean isHostnameWrong(String m) {
        if (m == null) return false;
        String l = m.toLowerCase(Locale.ROOT);
        return l.contains("https hostname wrong")
                || l.contains("wrong https hostname")
                || (l.contains("https hostname") && l.contains("should be"));
    }

    /**
     * The host a certificate must carry: {@code dialledHost} trimmed, without
     * a {@code :port}, without the brackets of an IPv6 literal, lower case,
     * no trailing dot. A bare IPv6 literal (colons, no brackets) is taken
     * whole. Null when blank or not a host as entered (a scheme, a path, a
     * space, or any character outside letters, digits, '.', '_' and '-'),
     * which makes the name check fail closed.
     */
    public static String expectedHost(String dialledHost) {
        if (dialledHost == null) return null;
        String h = dialledHost.trim();
        if (h.isEmpty()) return null;
        Matcher m = HOST_PORT.matcher(h);
        if (m.matches()) return normalizeHost(m.group(1));
        if (BARE_IPV6.matcher(h).matches()) return normalizeHost(h);
        return null;
    }

    /**
     * The platform trust manager plus a name check against the host fixed
     * when the context was built. Every overload ignores the peer host of the
     * socket or engine. Extends {@link X509ExtendedTrustManager} so JSSE uses
     * it as is. Client checks are delegated to the platform unchanged.
     */
    static final class NameCheckingTrustManager extends X509ExtendedTrustManager {

        private final X509TrustManager platform;
        private final String expectedHost;

        /** @param expectedHost from {@link #expectedHost}; null refuses every handshake */
        NameCheckingTrustManager(X509TrustManager platform, String expectedHost) {
            this.platform = platform;
            this.expectedHost = expectedHost;
        }

        @Override
        public void checkServerTrusted(X509Certificate[] chain, String authType,
                Socket socket) throws CertificateException {
            if (platform instanceof X509ExtendedTrustManager) {
                ((X509ExtendedTrustManager) platform).checkServerTrusted(
                        chain, authType, socket);
            } else {
                platform.checkServerTrusted(chain, authType);
            }
            checkName(expectedHost, chain);
        }

        @Override
        public void checkServerTrusted(X509Certificate[] chain, String authType,
                SSLEngine engine) throws CertificateException {
            if (platform instanceof X509ExtendedTrustManager) {
                ((X509ExtendedTrustManager) platform).checkServerTrusted(
                        chain, authType, engine);
            } else {
                platform.checkServerTrusted(chain, authType);
            }
            checkName(expectedHost, chain);
        }

        @Override
        public void checkServerTrusted(X509Certificate[] chain, String authType)
                throws CertificateException {
            platform.checkServerTrusted(chain, authType);
            checkName(expectedHost, chain);
        }

        @Override
        public void checkClientTrusted(X509Certificate[] chain, String authType,
                Socket socket) throws CertificateException {
            if (platform instanceof X509ExtendedTrustManager) {
                ((X509ExtendedTrustManager) platform).checkClientTrusted(
                        chain, authType, socket);
            } else {
                platform.checkClientTrusted(chain, authType);
            }
        }

        @Override
        public void checkClientTrusted(X509Certificate[] chain, String authType,
                SSLEngine engine) throws CertificateException {
            if (platform instanceof X509ExtendedTrustManager) {
                ((X509ExtendedTrustManager) platform).checkClientTrusted(
                        chain, authType, engine);
            } else {
                platform.checkClientTrusted(chain, authType);
            }
        }

        @Override
        public void checkClientTrusted(X509Certificate[] chain, String authType)
                throws CertificateException {
            platform.checkClientTrusted(chain, authType);
        }

        @Override
        public X509Certificate[] getAcceptedIssuers() {
            return platform.getAcceptedIssuers();
        }
    }

    /**
     * Throw unless the leaf of {@code chain} carries {@code host}. The text
     * starts "No subject alternative name matching", which
     * {@link #isNameMismatch} reads as a name mismatch. No host at all is
     * refused with {@link #NO_HOST_MESSAGE} (fail closed).
     */
    static void checkName(String host, X509Certificate[] chain)
            throws CertificateException {
        if (chain == null || chain.length == 0 || chain[0] == null) {
            throw new CertificateException("the target sent no certificate");
        }
        if (normalizeHost(host) == null) {
            throw new CertificateException(NO_HOST_MESSAGE);
        }
        if (!nameMatches(host, chain[0])) {
            throw new CertificateException(MISMATCH_PREFIX + host
                    + " in the target certificate (subject "
                    + chain[0].getSubjectX500Principal().getName() + ")");
        }
    }

    /**
     * Whether {@code cert} is issued for {@code host}, by the rules the JDK
     * applies (RFC 2818 / RFC 6125): an IP address matches only an IP subject
     * alternative name; a DNS name matches a DNS subject alternative name,
     * case-insensitive, with a wildcard allowed in the left-most label only
     * and never directly under a top-level label; the subject common name is
     * used only when the certificate has no DNS alternative names.
     */
    public static boolean nameMatches(String host, X509Certificate cert) {
        String h = normalizeHost(host);
        if (h == null || cert == null) return false;
        java.util.Collection<List<?>> sans;
        try {
            sans = cert.getSubjectAlternativeNames();
        } catch (java.security.cert.CertificateParsingException e) {
            return false;
        }
        if (isIpLiteral(h)) {
            InetAddress want = ipLiteral(h);
            if (want == null || sans == null) return false;
            for (List<?> san : sans) {
                if (san != null && san.size() >= 2
                        && Integer.valueOf(7).equals(san.get(0))
                        && san.get(1) instanceof String) {
                    InetAddress got = ipLiteral(normalizeHost((String) san.get(1)));
                    if (want.equals(got)) return true;
                }
            }
            return false;
        }
        boolean anyDns = false;
        if (sans != null) {
            for (List<?> san : sans) {
                if (san != null && san.size() >= 2
                        && Integer.valueOf(2).equals(san.get(0))
                        && san.get(1) instanceof String) {
                    anyDns = true;
                    if (dnsMatches(h, (String) san.get(1))) return true;
                }
            }
        }
        if (anyDns) return false;
        String cn = mostSpecificCn(cert);
        return cn != null && dnsMatches(h, cn);
    }

    /** Trimmed, unbracketed, no trailing dot, lower case; null when empty. */
    static String normalizeHost(String host) {
        if (host == null) return null;
        String h = host.trim();
        if (h.startsWith("[") && h.endsWith("]") && h.length() > 2) {
            h = h.substring(1, h.length() - 1);
        }
        if (h.endsWith(".")) h = h.substring(0, h.length() - 1);
        if (h.isEmpty()) return null;
        return h.toLowerCase(Locale.ROOT);
    }

    /**
     * True for an IPv6 literal (any colon, brackets already removed) or a
     * dotted quad whose octets are each 0 to 255. An out-of-range dotted
     * string is not a literal, so it is never handed to InetAddress, which
     * would resolve it through DNS.
     */
    static boolean isIpLiteral(String h) {
        if (h == null) return false;
        if (h.indexOf(':') >= 0) return true;
        if (!IPV4.matcher(h).matches()) return false;
        for (String octet : h.split("\\.")) {
            if (Integer.parseInt(octet) > 255) return false;
        }
        return true;
    }

    /** The address of an IP literal, never a DNS lookup; null otherwise. */
    private static InetAddress ipLiteral(String h) {
        if (h == null || !isIpLiteral(h)) return null;
        if (h.indexOf(':') >= 0 && !h.matches("^[0-9a-f:.]+$")) return null;
        try {
            return InetAddress.getByName(h);
        } catch (java.net.UnknownHostException e) {
            return null;
        }
    }

    private static boolean dnsMatches(String host, String pattern) {
        String p = normalizeHost(pattern);
        if (p == null) return false;
        if (p.indexOf('*') < 0) return p.equals(host);
        int dot = p.indexOf('.');
        if (dot <= 0) return false;
        String left = p.substring(0, dot);
        String rest = p.substring(dot);   // with its leading dot
        if (rest.indexOf('*') >= 0) return false;
        if (rest.indexOf('.', 1) < 0) return false;   // *.com
        int star = left.indexOf('*');
        if (star != left.lastIndexOf('*')) return false;
        int hdot = host.indexOf('.');
        if (hdot <= 0) return false;
        String hl = host.substring(0, hdot);
        if (!host.substring(hdot).equals(rest)) return false;
        String pre = left.substring(0, star);
        String suf = left.substring(star + 1);
        return hl.length() >= pre.length() + suf.length()
                && hl.startsWith(pre) && hl.endsWith(suf);
    }

    private static String mostSpecificCn(X509Certificate cert) {
        try {
            javax.naming.ldap.LdapName dn = new javax.naming.ldap.LdapName(
                    cert.getSubjectX500Principal().getName(
                            javax.security.auth.x500.X500Principal.RFC2253));
            String cn = null;
            // getRdns() runs from the least to the most specific.
            for (javax.naming.ldap.Rdn rdn : dn.getRdns()) {
                if ("CN".equalsIgnoreCase(rdn.getType())
                        && rdn.getValue() instanceof String) {
                    cn = (String) rdn.getValue();
                }
            }
            return cn;
        } catch (javax.naming.InvalidNameException e) {
            return null;
        }
    }
}
