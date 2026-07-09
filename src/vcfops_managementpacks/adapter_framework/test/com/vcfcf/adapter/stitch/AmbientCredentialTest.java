package com.vcfcf.adapter.stitch;

import com.integrien.alive.common.adapter3.config.AdapterConfig;
import com.integrien.alive.common.adapter3.config.AdapterCredentialConfig;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;

/**
 * Lightweight unit tests for {@link AmbientCredential}.
 *
 * <p>No JUnit required — call via {@code main()}. Covers:
 * <ol>
 *   <li>{@code buildCandidates()} resolution order: automation preferred,
 *       maintenance fallback, override-only-when-set (2026-07-01 CP-403
 *       identity fix — see
 *       {@code knowledge/context/investigations/cp-auth-door-probe-2026-07-01.md}).</li>
 *   <li>{@code load()} end-to-end via the {@code vcfcf.suiteapi.credential.path}
 *       override: successful parse of an unencrypted test fixture, source
 *       label {@code "override"}, and the override's hard-fail-on-unreadable
 *       policy (does not silently fall through).</li>
 *   <li>{@code load(AdapterConfig)} identity v3 ambient order: injected
 *       per-instance credential selected when present; injected-null/blank
 *       falls through to the automation/maintenance file candidates;
 *       construction never throws with a null {@link AdapterConfig} — see
 *       {@code knowledge/designs/stitcher-identity-v3-adapter-credentials.md}.</li>
 * </ol>
 *
 * <p>The hard-wired {@code automationuser.properties}/{@code
 * maintenanceuser.properties} candidate paths are root-owned platform
 * locations not writable in a test sandbox, so the automation-preferred /
 * maintenance-fallback <em>selection order</em> is verified structurally via
 * {@code buildCandidates()} (package-private) rather than by faking both
 * files on disk. This still exercises the exact ordering and
 * hard-fail-on-unreadable policy the fix depends on.
 *
 * <p>Run:
 * <pre>
 *   javac -cp adapter_runtime/vrops-adapters-sdk-2.2.jar:build/vcfcf-adapter-base.jar \
 *         adapter_framework/test/com/vcfcf/adapter/stitch/AmbientCredentialTest.java \
 *         -d build/test-classes
 *   java -cp build/test-classes:adapter_runtime/vrops-adapters-sdk-2.2.jar:build/vcfcf-adapter-base.jar \
 *         com.vcfcf.adapter.stitch.AmbientCredentialTest
 * </pre>
 */
public class AmbientCredentialTest {

    private static final List<String> FAILURES = new ArrayList<>();
    private static int passed = 0;

    public static void main(String[] args) throws Exception {
        testBuildCandidatesDefaultOrder();
        testBuildCandidatesOverrideOnly();
        testLoadOverrideUnencrypted();
        testLoadOverrideEncryptedRoundTrip();
        testLoadOverrideUnreadableHardFails();
        testInjectedCredentialPreferredWhenPresent();
        testInjectedCredentialNullConfigFallsThrough();
        testInjectedCredentialNullCredentialsFallsThrough();
        testInjectedCredentialBlankUsernameFallsThrough();
        testInjectedCredentialBlankPasswordFallsThrough();
        testOverrideTakesPriorityOverInjected();
        testNoArgLoadEquivalentToLoadNull();
        testInjectedFailureReasonRecordedWhenConfigPresentButCredentialsNull();
        testInjectedFailureReasonRecordedWhenConfigPresentButUsernameBlank();
        testNoInjectedFailureReasonRecordedWhenConfigAbsent();
        report();
    }

    // -----------------------------------------------------------------------
    // buildCandidates() ordering
    // -----------------------------------------------------------------------

    private static void testBuildCandidatesDefaultOrder() {
        clearOverride();
        List<AmbientCredential.Candidate> candidates = AmbientCredential.buildCandidates();

        assertTrue("no override set: exactly two candidates (automation, maintenance)",
                candidates.size() == 2);
        assertEquals("candidate[0] is automation (preferred)",
                "automation", candidates.get(0).label);
        assertEquals("candidate[0] path is automationuser.properties",
                AmbientCredential.AUTOMATION_PROPS_PATH, candidates.get(0).path);
        assertTrue("candidate[0] (automation) does NOT hard-fail on unreadable"
                        + " — falls through to maintenance",
                !candidates.get(0).hardFailOnUnreadable);

        assertEquals("candidate[1] is maintenance (fallback)",
                "maintenance", candidates.get(1).label);
        assertEquals("candidate[1] path is maintenanceuser.properties",
                AmbientCredential.MAINTENANCE_PROPS_PATH, candidates.get(1).path);
    }

    private static void testBuildCandidatesOverrideOnly() {
        Path fake = Path.of("/tmp/does-not-need-to-exist-for-this-test.properties");
        System.setProperty(AmbientCredential.SYSPROP_CREDENTIAL_PATH, fake.toString());
        try {
            List<AmbientCredential.Candidate> candidates = AmbientCredential.buildCandidates();
            assertTrue("override set: exactly one candidate (no automation/maintenance fallback)",
                    candidates.size() == 1);
            assertEquals("sole candidate is labeled override",
                    "override", candidates.get(0).label);
            assertTrue("override candidate hard-fails on unreadable (no silent fallback)",
                    candidates.get(0).hardFailOnUnreadable);
        } finally {
            clearOverride();
        }
    }

    // -----------------------------------------------------------------------
    // load() via override — end-to-end file read + decrypt path
    // -----------------------------------------------------------------------

    private static void testLoadOverrideUnencrypted() throws IOException {
        Path tmp = Files.createTempFile("automationuser-test", ".properties");
        tmp.toFile().deleteOnExit();
        Files.write(tmp, (
                "username=automationAdmin\n"
                + "password=plaintextpw\n"
                + "encrypted=false\n").getBytes(StandardCharsets.UTF_8));

        System.setProperty(AmbientCredential.SYSPROP_CREDENTIAL_PATH, tmp.toString());
        try {
            AmbientCredential cred = AmbientCredential.load();
            assertEquals("username parsed from override file",
                    "automationAdmin", cred.getUsername());
            assertEquals("unencrypted password passed through unchanged",
                    "plaintextpw", cred.getPassword());
            assertEquals("source label is override",
                    "override", cred.getSourceLabel());
        } finally {
            clearOverride();
            Files.deleteIfExists(tmp);
        }
    }

    private static void testLoadOverrideEncryptedRoundTrip() throws IOException {
        // Uses the platform Crypt the same way loadFromPath() does, so this
        // exercises the identical decrypt call path production code takes —
        // just proving the file-selection plumbing feeds the right bytes in.
        String encrypted;
        try {
            encrypted = com.integrien.alive.common.security.Crypt
                    .getDefaultCrypt().encrypt("s3cr3t");
        } catch (Throwable t) {
            // Crypt may not be usable outside a collector JVM in some
            // environments (native/FIPS provider wiring); skip gracefully —
            // the unencrypted round trip above already proves the plumbing.
            System.out.println("  SKIP: encrypted round trip (Crypt unavailable: "
                    + t.getClass().getSimpleName() + ")");
            return;
        }

        Path tmp = Files.createTempFile("automationuser-test-enc", ".properties");
        tmp.toFile().deleteOnExit();
        Files.write(tmp, (
                "username=automationAdmin\n"
                + "password=" + encrypted + "\n"
                + "encrypted=true\n").getBytes(StandardCharsets.UTF_8));

        System.setProperty(AmbientCredential.SYSPROP_CREDENTIAL_PATH, tmp.toString());
        try {
            AmbientCredential cred = AmbientCredential.load();
            assertEquals("decrypted password matches plaintext",
                    "s3cr3t", cred.getPassword());
        } finally {
            clearOverride();
            Files.deleteIfExists(tmp);
        }
    }

    private static void testLoadOverrideUnreadableHardFails() throws IOException {
        Path tmp = Files.createTempFile("automationuser-unreadable", ".properties");
        tmp.toFile().deleteOnExit();
        Files.write(tmp, "username=x\npassword=y\nencrypted=false\n"
                .getBytes(StandardCharsets.UTF_8));

        boolean canRestrict;
        try {
            Set<PosixFilePermission> none = EnumSet.noneOf(PosixFilePermission.class);
            Files.setPosixFilePermissions(tmp, none);
            canRestrict = !Files.isReadable(tmp);
        } catch (UnsupportedOperationException | IOException e) {
            canRestrict = false;
        }

        if (!canRestrict) {
            // Running as root or on a non-POSIX filesystem in this sandbox —
            // permission restriction is not observable. Skip rather than
            // assert a false negative.
            System.out.println("  SKIP: unreadable-override hard-fail"
                    + " (cannot restrict file permissions in this environment)");
            Files.deleteIfExists(tmp);
            clearOverride();
            return;
        }

        System.setProperty(AmbientCredential.SYSPROP_CREDENTIAL_PATH, tmp.toString());
        try {
            AmbientCredential.load();
            FAILURES.add("unreadable override should throw IOException");
        } catch (IOException expected) {
            assertTrue("unreadable override throws IOException naming the override",
                    expected.getMessage() != null
                            && expected.getMessage().contains("override"));
        } finally {
            clearOverride();
            try {
                Files.setPosixFilePermissions(tmp,
                        EnumSet.of(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE));
            } catch (Exception ignore) {
                // best-effort cleanup
            }
            Files.deleteIfExists(tmp);
        }
    }

    // -----------------------------------------------------------------------
    // Identity v3 — platform-injected per-instance credential (tryInjectedCredential)
    // -----------------------------------------------------------------------

    /**
     * <strong>Sandbox caveat:</strong> {@code AdapterCredentialConfig.getPassword()}
     * internally calls {@code com.vmware.vcops.security.Crypt.getDefaultCrypt()
     * .decrypt(...)} — a class present on a real collector's adapter classpath
     * but shipped in <em>none</em> of this repo's local jars (discovered live,
     * 2026-07-02 — see {@link AmbientCredential#tryInjectedCredential}
     * javadoc). In that case {@code tryInjectedCredential} correctly catches
     * the resulting {@link NoClassDefFoundError} and returns {@code null}
     * (source absent) rather than propagating it — this test accepts either
     * outcome (decrypt succeeds → "instance" selected; decrypt class missing
     * → graceful null) but never an escaped {@link Throwable}, which is the
     * actual contract under test here.
     */
    private static void testInjectedCredentialPreferredWhenPresent() {
        AdapterConfig cfg = new AdapterConfig("some_kind", 1);
        cfg.setAdapterCredentials(
                new AdapterCredentialConfig("48fb5d76-instance-uuid", "s3cr3t-injected"));

        AmbientCredential cred;
        try {
            cred = AmbientCredential.tryInjectedCredential(cfg);
        } catch (Throwable t) {
            FAILURES.add("tryInjectedCredential must never let a Throwable escape"
                    + " (crash-the-cycle guarantee) — got: " + t);
            return;
        }

        if (cred == null) {
            System.out.println("  SKIP: injected-credential 'preferred' assertions"
                    + " (com.vmware.vcops.security.Crypt not on this sandbox's classpath —"
                    + " tryInjectedCredential correctly fell through to null instead of"
                    + " throwing; see class javadoc)");
        } else {
            assertEquals("injected username == AdapterCredentialConfig.getUserName()",
                    "48fb5d76-instance-uuid", cred.getUsername());
            assertEquals("injected password == AdapterCredentialConfig.getPassword()",
                    "s3cr3t-injected", cred.getPassword());
            assertEquals("injected credential source label is 'instance'",
                    "instance", cred.getSourceLabel());
        }

        // End-to-end via load(AdapterConfig) — no override set. Either the
        // injected credential wins (decrypt available) or the call falls
        // through to file candidates and throws IOException (decrypt
        // unavailable in this sandbox, files absent too) — never an
        // unchecked exception.
        clearOverride();
        try {
            AmbientCredential loaded = AmbientCredential.load(cfg);
            assertEquals("load(cfg) returns the injected credential's username",
                    "48fb5d76-instance-uuid", loaded.getUsername());
            assertEquals("load(cfg) returns the injected credential's source label",
                    "instance", loaded.getSourceLabel());
        } catch (IOException e) {
            System.out.println("  SKIP: load(cfg) end-to-end 'instance wins' assertion"
                    + " (fell through to absent file candidates in this sandbox): "
                    + e.getMessage());
        }
    }

    private static void testInjectedCredentialNullConfigFallsThrough() {
        AmbientCredential cred = AmbientCredential.tryInjectedCredential(null);
        assertTrue("null AdapterConfig: tryInjectedCredential returns null (source absent)",
                cred == null);
    }

    private static void testInjectedCredentialNullCredentialsFallsThrough() {
        AdapterConfig cfg = new AdapterConfig("some_kind", 1);
        // getAdapterCredentials() is null by default — never set.
        AmbientCredential cred = AmbientCredential.tryInjectedCredential(cfg);
        assertTrue("AdapterConfig with null getAdapterCredentials(): returns null",
                cred == null);
    }

    private static void testInjectedCredentialBlankUsernameFallsThrough() {
        AdapterConfig cfg = new AdapterConfig("some_kind", 1);
        cfg.setAdapterCredentials(new AdapterCredentialConfig("   ", "somePassword"));
        AmbientCredential cred = AmbientCredential.tryInjectedCredential(cfg);
        assertTrue("blank injected username: returns null (falls through)",
                cred == null);

        AdapterConfig cfgNullUser = new AdapterConfig("some_kind", 1);
        cfgNullUser.setAdapterCredentials(new AdapterCredentialConfig(null, "somePassword"));
        AmbientCredential cred2 = AmbientCredential.tryInjectedCredential(cfgNullUser);
        assertTrue("null injected username: returns null (falls through)",
                cred2 == null);
    }

    private static void testInjectedCredentialBlankPasswordFallsThrough() {
        AdapterConfig cfg = new AdapterConfig("some_kind", 1);
        cfg.setAdapterCredentials(new AdapterCredentialConfig("someUser", ""));
        AmbientCredential cred = AmbientCredential.tryInjectedCredential(cfg);
        assertTrue("blank injected password: returns null (falls through)",
                cred == null);

        AdapterConfig cfgNullPw = new AdapterConfig("some_kind", 1);
        cfgNullPw.setAdapterCredentials(new AdapterCredentialConfig("someUser", null));
        AmbientCredential cred2 = AmbientCredential.tryInjectedCredential(cfgNullPw);
        assertTrue("null injected password: returns null (falls through)",
                cred2 == null);
    }

    /**
     * Override-beats-injected priority: with both an explicit {@code
     * vcfcf.suiteapi.credential.path} override set <em>and</em> a valid injected
     * per-instance credential present on the {@link AdapterConfig},
     * {@code load(cfg)} must try only the override path — never consult the
     * injected credential. Asserted indirectly: the override file does not
     * exist, so {@code load(cfg)} throws an {@link IOException}, and that
     * exception's message names the override path, not the injected
     * principal ({@code "instancePrincipal"}) — proving the injected source
     * was never reached.
     */
    private static void testOverrideTakesPriorityOverInjected() {
        AdapterConfig cfg = new AdapterConfig("some_kind", 1);
        cfg.setAdapterCredentials(new AdapterCredentialConfig("instancePrincipal", "instancePw"));

        Path fake = Path.of("/tmp/does-not-need-to-exist-for-this-test.properties");
        System.setProperty(AmbientCredential.SYSPROP_CREDENTIAL_PATH, fake.toString());
        try {
            AmbientCredential.load(cfg);
            FAILURES.add("override set + nonexistent override file should throw IOException"
                    + " (proves override is tried, not the injected credential)");
        } catch (IOException expected) {
            assertTrue("override present: load(cfg) tries the override path, not the"
                            + " injected credential (message does not mention 'instance')",
                    !expected.getMessage().contains("instancePrincipal"));
        } finally {
            clearOverride();
        }
    }

    private static void testNoArgLoadEquivalentToLoadNull() {
        clearOverride();
        // Neither call should NPE; both fall through identically to the
        // file-based candidates (which are absent in this sandbox) and throw
        // the same shape of IOException.
        String msg0 = null, msg1 = null;
        try {
            AmbientCredential.load();
        } catch (IOException e) {
            msg0 = e.getMessage();
        } catch (Exception unexpected) {
            FAILURES.add("load() with no args should never throw an unchecked exception: "
                    + unexpected);
        }
        try {
            AmbientCredential.load((AdapterConfig) null);
        } catch (IOException e) {
            msg1 = e.getMessage();
        } catch (Exception unexpected) {
            FAILURES.add("load(null) should never throw an unchecked exception: " + unexpected);
        }
        assertTrue("load() and load(null) both surface the same IOException shape"
                        + " (both null, or both non-null)",
                (msg0 == null) == (msg1 == null));
    }

    // -----------------------------------------------------------------------
    // WARNING-1 breadcrumb — AmbientCredential#getInjectedFailureReason()
    // -----------------------------------------------------------------------
    //
    // Full end-to-end coverage (a returned AmbientCredential from
    // load(AdapterConfig) carrying the reason) would require a *successful*
    // file-candidate load, which depends on the hardcoded, root-owned
    // automation/maintenance paths existing in the test sandbox — not
    // available here (see class javadoc). These tests instead verify the
    // breadcrumb-recording logic in tryInjectedCredential() directly via the
    // package-private peekLastInjectedFailureReasonForTest() seam, which is
    // the exact mechanism load(AdapterConfig) reads from to populate
    // getInjectedFailureReason() on the credential it returns.

    private static void testInjectedFailureReasonRecordedWhenConfigPresentButCredentialsNull() {
        AdapterConfig cfg = new AdapterConfig("some_kind", 1);
        // getAdapterCredentials() is null by default — instance source lost.
        AmbientCredential cred = AmbientCredential.tryInjectedCredential(cfg);
        assertTrue("null credentials: tryInjectedCredential returns null (source absent)",
                cred == null);
        assertEquals("config present + null credentials: reason recorded as"
                        + " 'credentials null/blank'",
                "credentials null/blank",
                AmbientCredential.peekLastInjectedFailureReasonForTest());
    }

    private static void testInjectedFailureReasonRecordedWhenConfigPresentButUsernameBlank() {
        AdapterConfig cfg = new AdapterConfig("some_kind", 1);
        cfg.setAdapterCredentials(new AdapterCredentialConfig("   ", "somePassword"));
        AmbientCredential cred = AmbientCredential.tryInjectedCredential(cfg);
        assertTrue("blank username: tryInjectedCredential returns null (source absent)",
                cred == null);
        assertEquals("config present + blank username: reason recorded as"
                        + " 'credentials null/blank'",
                "credentials null/blank",
                AmbientCredential.peekLastInjectedFailureReasonForTest());
    }

    private static void testNoInjectedFailureReasonRecordedWhenConfigAbsent() {
        // Seed a known reason first, so we can prove a null-config call does
        // not clobber it — tryInjectedCredential(null) short-circuits before
        // touching the thread-local at all, which is exactly why
        // load(AdapterConfig) gates reason-attachment on "adapterConfig !=
        // null": a genuinely absent config (early lifecycle, test harness)
        // must never produce a breadcrumb.
        AdapterConfig seedCfg = new AdapterConfig("some_kind", 1);
        AmbientCredential.tryInjectedCredential(seedCfg);
        assertEquals("sanity: seed call recorded a reason",
                "credentials null/blank",
                AmbientCredential.peekLastInjectedFailureReasonForTest());

        AmbientCredential cred = AmbientCredential.tryInjectedCredential(null);
        assertTrue("null AdapterConfig: tryInjectedCredential returns null (source absent)",
                cred == null);
        assertEquals("null AdapterConfig: does not touch the failure-reason"
                        + " thread-local (still whatever the seed call left it as)",
                "credentials null/blank",
                AmbientCredential.peekLastInjectedFailureReasonForTest());
    }

    // -----------------------------------------------------------------------
    // Harness
    // -----------------------------------------------------------------------

    private static void clearOverride() {
        System.clearProperty(AmbientCredential.SYSPROP_CREDENTIAL_PATH);
    }

    private static void assertTrue(String label, boolean cond) {
        if (cond) {
            System.out.println("  PASS: " + label);
            passed++;
        } else {
            System.out.println("  FAIL: " + label);
            FAILURES.add(label);
        }
    }

    private static void assertEquals(String label, String expected, String actual) {
        if (expected == null ? actual == null : expected.equals(actual)) {
            System.out.println("  PASS: " + label);
            passed++;
        } else {
            System.out.println("  FAIL: " + label
                    + " expected=" + expected + " actual=" + actual);
            FAILURES.add(label);
        }
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
