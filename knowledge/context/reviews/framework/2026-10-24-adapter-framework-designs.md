# Framework review: adapter framework designs (#185, #206, #205, #221, #222)

- Branch: `feat/adapter-framework-designs-185-206-205-221-222` (worktree `.claude/worktrees/adapter-fw-185`), five commits on `origin/main` 8ad0911: d43eb52 (#185/#206), c80ee06 (#205), cce7c1c (#221), 135d6ef (#222), 0e94155 (buildkit 1.0.16).
- Reviewer: `framework-reviewer` (RULE-013), 2026-10-24.
- Area: `src/vcfcf_managementpacks/adapter_framework` (VcfCfAdapter, http/CertificateNames, http/HttpClientBuilder, http/ManagedHttpClient, spi/VcfCfCollector), `buildkit.py`, tier2 doc, `vcfops-sdk-adapter` skill.

## Verdict: CHANGES REQUESTED

1 BLOCKING, 2 WARNING, 3 NIT.

The name-matching code itself is sound: every edge case in the brief was probed against real certificates and behaved correctly. The blocking problem is on the Test Connection side. A wrong-name certificate, which is the one failure this change introduces, never reaches the new #205 message hook or the neutral default text. The javadoc, the tier2 doc and the skill all tell pak authors that it does.

## Checks re-run (independently)

| Check | Result |
|---|---|
| CI pytest (`python3 -m pytest tests/ -q -n auto --dist=loadgroup --override-ini="addopts=" -m ""`, pak clones symlinked) | 2647 passed, 8 skipped, 0 failed |
| Framework main + tests compiled from source on JDK 17, every `main()` test class run | 11/11 classes green (CertificateNamesTest 210, CertificateReviewTest 138, AdapterInstanceStatusTest 68, HttpClientBuilderTest 11, and the rest). `VcfCfAdapterTest`'s manifest case needs the jar, so it was also run via the author's runner against `adapter_runtime/vcfcf-adapter-base.jar`. That jar's manifest says source 135d6ef, which matches HEAD's framework source. Green. |
| `javac --release 11` on framework main sources vs `vrops-adapters-sdk-2.2.jar` (RULE-019) | 1 error, **pre-existing**, not this branch: `ManagedHttpClient.java:305` `HttpRequest.newBuilder(HttpRequest, BiPredicate)` (Java 16, blame bb8869cd / d59785aa, May and June). With that one line neutralized in a scratch copy, the rest of main and all test sources compile clean under `--release 11`. **This branch adds no Java 12+ API.** |
| `validate-sdk` on compliance, unifi, synology against this framework | All three OK (9.1.1.0100 compat pass skipped: jar not present, expected) |
| Em-dash scan of added lines | 0 |
| render-regression / pak-compare | n/a (no content renderer, builder template, or pak structure touched) |

## Probes (scratch, not committed)

Certificates were minted with keytool and openssl, then run through `CertificateNames.expectedHost` and `checkName`:

- `*.Example.com` passes `a.example.com`, `A.EXAMPLE.COM`, `a.example.com.` and `a.example.com:443`. It refuses `a.b.example.com`, `example.com` and `.example.com`. `f*.example.com` passes `foo.` and refuses `bar.`. A `*.com` wildcard is refused.
- An IP SAN passes `10.0.0.5`, `10.0.0.5:443`, `[fe80::1]`, `[FE80:0::1]:8443` and bare `fe80::1`. A CN-only IP and a DNS-type SAN holding an IP are both refused (JDK parity). `010.0.0.5` resolves to 10.0.0.5 as a literal, with no DNS lookup, which is the same address the client dials.
- A CN-only certificate passes on case and trailing dot. A trailing-dot SAN matches.
- A blank host, null, `https://...`, `host/path` and `user@host` all fail closed with `NO_HOST_MESSAGE`. A U-label host (`bücher.example.com`) also fails closed (see NIT 5).
- Suite API loopback: `openPlatformConnection` is untouched (all-true verifier, lines 1432/1457). Nothing in the framework calls `getPlatformSslContext(String)` or `nameCheckingContext` on its own, so a blank host cannot refuse the loopback path.
- Hook classification: `VcfCfAdapter.findCertificateTrustFailure` returns **null** for a name mismatch in both the JDK shape (`SSLHandshakeException` caused by `CertificateException("No subject alternative name matching ...")`) and the BouncyCastle shape (`IOException("...TlsFatalAlert: certificate_unknown(46)")` wrapping it). It also returns null for a `NO_HOST_MESSAGE` failure. `CertificateNames.isNameMismatch` returns true for the same BC-shape exception.

## Findings

### BLOCKING

**B1. A certificate name mismatch never reaches the #205 hook or default text, so the documented use of the new hook is unreachable.**
`VcfCfAdapter.java:759` (`onTest`) consults `certificateTrustFailureMessage` and `certificateFailureMessage` only when `findCertificateTrustFailure(e) != null`. That classifier matches only `CustomCertificateException`, `CertPath*Exception` or PKIX text.

The name check this branch adds throws a plain `CertificateException("No subject alternative name matching ...")`, and it runs only after the platform chain check has passed. So in every case where it fires, the classifier finds nothing. The admin gets the raw exception message: on the BC JSSE 9.1.1 collector that is plausibly `certificate_unknown(46)`. Whether BC keeps the cause text is unproven, which makes it a finding under the doctrine's skeptic default. The same applies to a blank or unusable host (`NO_HOST_MESSAGE`).

For the same reason, the hook javadoc's example at lines 2412-2414 is dead code. It says to tell "a name mismatch versus an untrusted chain" apart with `isNameMismatch`, but inside the hook `isNameMismatch` can never be true for the framework's own check: a chain failure stops the handshake before the name is checked.

The tier2 changelog row (line 963) and the skill both tell compliance to "drop its rethrow-without-cause workaround in favour of `certificateFailureMessage`". A compliance build that does so would lose its readable wrong-name message.

- Authority: issue #205 ("the right advice is ... enter the host by the name on its certificate"); issue #206 (move compliance's name check into the framework so unifi and synology get it); review dimension 8 (a capability documented but not delivered); dimension 10 (no `onTest` test with a name-mismatch failure; CertificateReviewTest feeds only `prodStack()` chain failures).
- Fix: in `onTest`, treat `CertificateNames.isNameMismatch(e)` and a `NO_HOST_MESSAGE` failure as certificate failures too. Give them a name-specific default text (the certificate does not carry the host entered; enter the host by the name on the certificate; accepting the certificate does not fix this) and pass them through `certificateFailureMessageSafe`. Add a CertificateReviewTest case that drives `onTest` with a real wrong-name failure from `platformSsl(this, host)`, or at least both exception shapes above, and asserts the hook is called. Correct the hook javadoc, the tier2 row and the skill so they match.

### WARNING

**W1. Two new `ThreadDeath` catches collide with #242, and git merges them in silently.**
`VcfCfAdapter.java:2432-2438` (`certificateFailureMessageSafe`) and `2500-2504` (`allowInsecureDescribedSafe`) add `catch (VirtualMachineError | ThreadDeath fatal)` under `@SuppressWarnings("deprecation")`. That annotation does not suppress `[removal]`.

#242 (commit 3301554 on `fix/installer-200-244-242-shims-159`, not yet on origin) removes every `ThreadDeath` reference, adds a source guard test and a JDK 25 `[removal]` gate, and restores the interrupt flag on an `InterruptedException` from a pak hook. `git merge-tree` of the two branches auto-merges `VcfCfAdapter.java` with no conflict. The conflicts are only in `CertificateReviewTest.java` and `tier2_architecture.md`. So the new catches reach the merged tree unflagged and red #242's guard there.

- Authority: commit 3301554; RULE-019 (`knowledge/rules/supported-platforms.md`, 9.1.1 collectors on Java 25).
- Fix: on whichever branch merges second, use #242's pattern (`VirtualMachineError` plus `isThreadKill(t)`, interrupt restore) in both new wrappers.

**W2. `BUILDKIT_VERSION` 1.0.16 is claimed by both this branch and the installer/shims branch.**
`buildkit.py:89` makes the same one-line change on both branches, so it auto-merges with no conflict. Two different kits would ship under one version, and the tier2 changelog would carry two 1.0.16 rows. Noted per the brief, not resolved here: whichever merges second takes 1.0.17 and corrects its changelog row.
- Authority: the `buildkit.py` version contract ("bump when kit contents change").

### NIT

**N1. `connectTimeout(Duration)` accepts zero or negative values.** (`HttpClientBuilder.java` setter.) Both fail later at `build()` with the JDK's bare `IllegalArgumentException`. Null is handled correctly (it falls back to `timeout`). Fix: reject a non-positive value in the setter with a framework message, or document it.

**N2. `onCycleStart` catches only `RuntimeException`.** (`VcfCfAdapter.java:842-848`.) A `LinkageError` or `AssertionError` from the pak hook ends the whole cycle before any per-resource status or the #223 account-status decision, so the account keeps showing Collecting. The doc says "RuntimeException", so the code and the doc agree. Fix: catch `Throwable` except `VirtualMachineError` and a thread kill, as the certificate wrappers do, or state in the javadoc that an `Error` aborts the cycle.

**N3. IDN edge cases.** (`CertificateNames.java:82-95, 422-442`.)
- A U-label host fails closed with "no usable host was given", which misleads an admin who did enter a host. Fix: say to enter the name in its ASCII (xn--) form.
- A wildcard inside an A-label (`xn--*.example.com`) matches. RFC 6125 §7.2 says SHOULD NOT. This matches the JDK, so it is a NIT only.

## Observations (not counted)

- **Java 11 HttpClient and the IP-rewrite retry.** `connectTimeout` is set on the `HttpClient`, so it applies to the DNS round-robin IP retries as well; the per-request `timeout` is copied with the request. On a Java 11 collector (8.18) that retry path does not run at all today: `ManagedHttpClient.java:305` calls a Java 16 method and would throw `NoSuchMethodError`. This predates the branch and is already fixed on `feat/252-compile-matrix-8-18-release-11` (92f38aa), so do not ship a 1.0.16 kit to an 8.18 pak before #252 lands. `connectTimeout` behaviour was verified on JDK 17 only; `HttpClient.Builder.connectTimeout` itself exists in Java 11.
- **validate-sdk and RULE-019.** It compiles with `-source 11` and no `--release` ("system modules path not set"), which is why that Java 16 call has never been caught. #252 addresses this.
- **`describesAllowInsecure`.** It matches on the tested config's kind key, and the test describe carries a second kind that declares the field, so the several-kinds case is covered. An unreadable describe (`onDescribe` throws, or returns null and the NPE is caught) falls back to the neutral text and never crashes `onTest` (`testOnTestUnreadableDescribeOmitsAllowInsecure`).
- **`onCycleStart` ordering.** It runs after `abortRequested.set(false)` and before `needsRediscovery`, discovery and collect. #223's account status is decided at the end of the cycle, and an `onCycleStart` failure does not feed it. No cycle budget exists on main to order against. `needsRediscovery` is pinned to exactly once per cycle, including all-fail cycles.
- **The hook and other failures.** It never handles a non-certificate failure: it is called only after classification, and its own throwables are contained.
- **Stale-zip discipline.** Not triggered: no `templates/`, `builder.py`, `assembly.py` or `render.py` change. The buildkit version bump is present as the signal to paks.

## If shipped as-is

A pak that opts in to name checking and an admin who types the wrong host would get raw TLS text (likely `certificate_unknown(46)`) on Validate Connection, not the "enter the host by the name on its certificate" advice. Compliance, following the new doc and dropping its workaround, would regress its readable message. Merging with #242 would also bring two `ThreadDeath` catches back without a conflict.
