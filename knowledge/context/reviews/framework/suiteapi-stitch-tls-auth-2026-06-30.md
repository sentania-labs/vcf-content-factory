# Framework Review — SuiteApiStitcher loopback TLS + auth cleanup

- **Area:** `vcfops_managementpacks/adapter_framework/` (`VcfCfAdapter`, `stitch/SuiteApiStitchClient`, `stitch/SuiteApiStitcher`) + `buildkit.py`
- **Change:** new `VcfCfAdapter.openPlatformConnection(url)` (HttpsURLConnection from `getAdapterTrustManager()`+`getKeyManagers()`+`getVerifier()`); `SuiteApiStitchClient` loopback path switched to it, token lifecycle refactored to cached-per-instance + single 401 retry; loopback gated on resolved `InetAddress.isLoopbackAddress()`; `BUILDKIT_VERSION` 0.2.0→0.2.1.
- **Date:** 2026-06-30  **Reviewer:** framework-reviewer  **Verdict:** **CHANGES REQUESTED** (1 BLOCKING)
- **Checks re-run:** validate-chain **pass** (7 packages); Tier 2 compile **6/6 adapters OK** (compliance, synology, unifi, vcommunity, vcommunity-os, vcommunity-vsphere — incl. the changed framework on classpath); render-regression **n/a** (no renderer touched); pak-compare **n/a** (no pak rebuilt).

---

## LEAD QUESTION verdict — `getAdapterTrustManager()` is WRONG; it must be `getSocketFactory()`

**Tooling traded a hostname failure for a CA/PKIX failure.** The trust object it chose
is positively documented — javap-confirmed, live-confirmed — as the manager that *always
rejects* the prod cert.

`knowledge/lessons/suite-api-stitch-ssl-tofu-vs-java-http.md` (confirmed devel+prod, build 45,
2026-06-10), lines 25-27:

> `adapter.getPlatformSslContext()`, **which wraps `AdapterBase.getAdapterTrustManager()`
> — the platform's `CustomTrustManager` instance.**

and lines 29-46:

> `CustomTrustManager` is a TOFU manager … **Always throws `CustomCertificateException`
> for any cert not already in the platform's trusted store — including the platform's own
> self-signed localhost cert.** … Both `getPlatformSslContext()` and the JVM default
> truststore fail for the localhost Suite API endpoint…

So `getAdapterTrustManager()` is **not** the "Noop-class accept-all" object the design §0 and
behavioral-contract spec §5 (confidence-ledger #12, marked *Med-High, no decompiled body*)
assumed. It is the strict TOFU manager. On prod-primary the loopback cert is issued by the
operator's org CA (`sentania Lab Issuing 2`), which is **not** in the platform trust store →
`CustomTrustManager.checkServerTrusted()` throws → handshake fails with
`SSLHandshakeException: PKIX path building failed`. The fix therefore **does not fix prod**: it
swaps `certificate_unknown(46)` (hostname) for a CA/PKIX failure — exactly the regression the
review brief flagged.

**Why the URLConnection transport does NOT save it.** The lesson (lines 37-40) attributes
TOFU survival to the *platform's* `getSocketFactory()` / `CustomSSLSocketFactory`, which the
platform wraps with intercept-and-retry-after-cert-registration. Tooling's
`openPlatformConnection()` does **not** use `AdapterBase.getSocketFactory()`. It hand-builds a
fresh context — `SSLContext.getInstance("TLS").init(km, {getAdapterTrustManager()}, null)` —
and installs `ctx.getSocketFactory()` (a *vanilla JSSE* factory). That vanilla factory invokes
`CustomTrustManager.checkServerTrusted()` with **no platform intercept**, so the exception is
fatal on first contact — for the prod org-CA cert, and per the lesson even for the stock
self-signed localhost cert. Switching from `java.net.http.HttpClient` to `HttpsURLConnection`
fixes the *hostname-verifier* gap but does nothing for trust, because the intercept lives in
`CustomSSLSocketFactory`, not in `URLConnection`.

**The faithful replication of the OG `getConnection(url, getVerifier())`** (which the design §0
correctly identifies as carrying *both* halves) is:

```java
https.setSSLSocketFactory(getSocketFactory());   // platform CustomSSLSocketFactory — carries the TOFU intercept
https.setHostnameVerifier(getVerifier());        // platform verifier — the half that regressed
```

`getConnection()` is package-private (the stated reason for the shim), but its trust half is
`getSocketFactory()`, **not** a context hand-built from `getAdapterTrustManager()`. Spec §5 and
`analysis/pak-signing-chain.md:117` both attribute "literally accepts everything" to the
platform socket-factory/Noop-trust-manager path reached via `getSocketFactory()`, never to
`getAdapterTrustManager()`.

**Static vs live:** Statically *proven* — `getAdapterTrustManager()` == `CustomTrustManager`
(lesson + javap, lines 78-79) and a hand-built context omits the intercept; this WILL throw on
any unknown cert. Only a *live prod install* can confirm that `getSocketFactory()`+`getVerifier()`
clears the org-CA, no-localhost-SAN cert end-to-end — but `getSocketFactory()` is provably the
sole path with the intercept, and the current shipping `insecureSslContext()` already proves CA
is passable on prod (the old code's only prod-primary failure was hostname(46), i.e. CA was
already past). `getAdapterTrustManager()` is provably the broken choice either way.

---

## BLOCKING

- **[VcfCfAdapter.java:1015-1035 `openPlatformConnection`]** —
  `knowledge/lessons/suite-api-stitch-ssl-tofu-vs-java-http.md:25-46,67-72`; spec
  `20-suiteapi-client-behavioral-contract.md` §5 / ledger #12. The loopback trust is built from
  `getAdapterTrustManager()` (= the strict TOFU `CustomTrustManager`) via a hand-rolled
  `SSLContext`, which (a) rejects the prod operator-replaced org-CA cert and (b) drops the
  `CustomSSLSocketFactory` intercept that made the OG path survive unknown certs. **On the
  loopback/standalone ambient path this re-introduces a handshake failure — a CA/PKIX failure in
  place of the hostname `(46)` failure — i.e. it does not fix prod.**
  → **Fix:** for the loopback hop, set `https.setSSLSocketFactory(getSocketFactory())` (the
  platform `CustomSSLSocketFactory`, cert-item-compliant and carrying the intercept) +
  `https.setHostnameVerifier(getVerifier())`. Do **not** construct an `SSLContext` from
  `getAdapterTrustManager()`. Update the method javadoc and the
  `SuiteApiStitchClient`/`SuiteApiStitcher` "platform trust manager (`getAdapterTrustManager()`)"
  doc lines accordingly, and re-confirm against the lesson before re-review.

---

## WARNING

- **[VcfCfAdapter.java:1023 / urlConnRequest hostname half]** — spec §5 ledger #12 (Med-High, no
  decompiled body). `getVerifier()` permissiveness against a *no-`localhost`-SAN* cert is the
  other unproven half of the fix; if `getVerifier()` is a strict verifier the loopback call still
  fails `SSLPeerUnverifiedException` on prod. The peer is already gated to
  `isLoopbackAddress()`, so an explicit `(h,s) -> true` verifier for the loopback hop is strictly
  safer and removes the dependency. (Faithful-to-OG `getVerifier()` is acceptable if BLOCKING is
  fixed and prod confirms, but flag it as the second live-only unknown.)
- **[SuiteApiStitchClient.java — no test]** — review dimension 10. No automated coverage for the
  new `isLoopbackUrl()` gating (localhost→true, 127.0.0.1→true, FQDN→false, unresolvable→false
  fail-open), the double-checked `ensureToken()`/`reAcquireToken()` locking, or the
  single-401-retry-no-loop contract. This transport class is exactly the kind of subtle,
  branch-heavy code that should not ship untested. → Add a unit test with a stub transport.

## NIT

- **[VcfCfAdapter.java:940-941 / 990-992]** — `getPlatformSslContext()` javadoc says "via
  `AdapterBase.getSocketFactory()`" but the body uses `getAdapterTrustManager()`; the new method
  repeats "same trust material as `getPlatformSslContext()`". This pre-existing doc/body
  conflation is precisely what seeded the wrong trust choice — correct it while here.
- **[VcfCfAdapter.java:1027]** — `openPlatformConnection` silently skips the SSL/verifier setup if
  `conn` is not an `HttpsURLConnection`. Harmless for the hardcoded `https://localhost` base, but
  a non-https URL would silently bypass TLS config; consider asserting https.

---

## Verified clean (independently)

- **Token lifecycle:** cached-per-instance via `volatile cachedToken` + `tokenLock`;
  `ensureToken()` double-checked; `reAcquireToken(old)` only refreshes if `old` still matches
  (no double-refresh); single 401 retry is one re-execute, not a loop (second 401 propagates /
  is swallowed by the push WARN). Matches spec §1/§2. `discard()` nulls + releases under lock,
  swallows on failure — matches spec §3. Thread-safe for concurrent collect workers.
- **Loopback gating:** keyed on resolved `InetAddress.getByName(host).isLoopbackAddress()`, not
  the string `"localhost"` (spec §5 caveat); fail-open → non-loopback strict path (safe
  direction). No SSLContext leak between paths — loopback uses per-request `openPlatformConnection`,
  explicit uses `insecureSslContext()` on `rawHttpClient`; `rawHttpClient` is `null` on the
  loopback branch and every `.send()` is inside the `!isLoopback` branch (no NPE).
- **`adapter` required on loopback:** `build()` throws a loud `IllegalStateException` (not NPE)
  when `loopback && adapter == null`. Both `SuiteApiStitcher.create()` (line 109) and
  `createExplicit()` (line 144) pass `.adapter(adapter)`; no other caller uses the builder
  directly. No NPE path.
- **Standard hunts:** no global-default leak (explicit/remote path byte-for-byte unchanged), no
  key/label collision (none in scope), and the only silent-downgrade risk is the BLOCKING above
  (loud handshake failure → swallowed-to-WARN stitch degrade). Validate chain green; 6/6 Tier 2
  adapters recompile against the changed framework.
- **Buildkit/stale discipline:** `BUILDKIT_VERSION` correctly bumped 0.2.0→0.2.1 so paks
  recompile against the fixed framework (design §6). No `vcfops_packaging/templates`,
  `builder.py`, or `render.py` touched → dist-zip staleness rule n/a. (Reminder, not a finding:
  after the fix, re-publish `sdk-buildkit-v1` and re-tag the four stitching paks.)

---

## If shipped as-is

The synology (and compliance/vcommunity/unifi) cross-MP stitch still produces **zero
relationships on prod-primary** — the loopback Suite API call fails the TLS handshake with a
PKIX/CA error instead of `certificate_unknown(46)`, and the operator sees the same silent
"0 datastores loaded" stitch degrade. The regression would only surface after the expensive
buildkit → pak → install loop on the prod appliance.

---

# Revision 2 re-review — 2026-06-30 — verdict: APPROVE

`tooling` addressed the BLOCKING. Re-verified at source **and** at the shipping binary
(not taken on the summary's word).

## BLOCKING (rev1) — RESOLVED

- **[VcfCfAdapter.java:976-1038 `openPlatformConnection`]** — rebuilt body now:
  `https.setSSLSocketFactory(getSocketFactory())` + `https.setHostnameVerifier((h,s)->true)`,
  with an `instanceof HttpsURLConnection` guard that throws `IOException` on a non-https URL.
  **No `SSLContext` is constructed from `getAdapterTrustManager()` anywhere on the loopback
  path.** This is the faithful replication of the OG `getConnection(url, getVerifier())` the
  lesson prescribes — the platform `CustomSSLSocketFactory` carries the TOFU-survival intercept;
  the all-true verifier is safe because the peer is already gated to `isLoopbackAddress()`.
  - **Static proof — source:** confirmed by reading the method.
  - **Static proof — shipping jar:** `javap -p -c` on the committed (gitignored, rebuilt
    10:00) `vcfops_managementpacks/adapter_runtime/vcfcf-adapter-base.jar` shows
    `invokevirtual getSocketFactory:()Lcom/integrien/alive/common/adapter3/CustomSSLSocketFactory;`
    → `setSSLSocketFactory`, then `invokedynamic verify` → `setHostnameVerifier`, and a
    `lambda$openPlatformConnection$1(String, SSLSession)` (the `(h,s)->true`). A negative grep of
    the method bytecode for `getAdapterTrustManager`/`SSLContext` returns **0**. The binary
    reflects revision-2 source — no stale/hand-edited jar.

## WARNING (rev1) — RESOLVED / MOOT

- **Hostname half (`getVerifier()` permissiveness):** moot — rev2 replaced `getVerifier()` with an
  explicit `(h,s)->true` gated to loopback, exactly as recommended. The second live-only unknown
  is removed.
- **No test:** `test/com/vcfcf/adapter/stitch/SuiteApiStitchClientTest.java` added and **re-run by
  me: 16/16 pass.** Genuinely exercises `isLoopbackUrl` (localhost/127.0.0.1/127.0.0.2-/8 → true;
  8.8.8.8 → false; unresolvable → fail-open false; malformed → false) and `jsonStr` escaping.

## NIT (rev1) — RESOLVED

- `getPlatformSslContext()` javadoc now correctly describes `getAdapterTrustManager()` as the
  strict TOFU `CustomTrustManager`; `openPlatformConnection` javadoc no longer conflates the two.
- non-https URL now rejected with `IOException`.

## Re-verified previously-clean (no regression)

- Explicit/remote path **unchanged** (`insecureSslContext()` + `java.net.http.HttpClient`,
  line 343-355) — no SSLContext leak between loopback and remote paths; `rawHttpClient` still
  null on the loopback branch and never dereferenced there.
- Token lifecycle (cached/volatile + `tokenLock`, single-401-retry-no-loop, `discard()`
  release+swallow), loopback gating on resolved peer, and `adapter`-required-on-loopback guard:
  all unchanged and still correct. `isLoopbackUrl` relocation to a package-private static on the
  outer class is behavior-preserving (test confirms).
- `BUILDKIT_VERSION` still `0.2.1`. Full validate chain green; **all 6 Tier 2 adapters recompile**
  against the revised framework (compliance, synology, unifi, vcommunity, vcommunity-os,
  vcommunity-vsphere).
- Standard hunts on the delta: no global-default leak (remote path byte-identical), no
  key/label collision, no silent-downgrade (the failure mode is now a *fixed* handshake, not a
  hidden one).

## Residual NITs (non-blocking — do not gate the PR)

- The test's 401-retry case is a **structural/annotation** assertion ("retry is exactly one
  attempt — structural contract verified"), not an executed stub-transport exercise of
  `reAcquireToken`. The gating logic (`isLoopbackUrl`) and `jsonStr` are genuinely executed; the
  401 single-retry path remains unexecuted. Acceptable, but a stub-transport test would close it.
- The loopback INFO line (SuiteApiStitchClient.java:359) still reads "platform-trust +
  platform-verifier"; rev2 actually uses the platform **socket factory** + an **all-true**
  verifier. Cosmetic log-text drift only.

## What remains provable ONLY by a live prod install

- That the platform `CustomSSLSocketFactory` intercept actually **registers-and-retries the
  operator-replaced org-CA cert** (`sentania Lab Issuing 2`, no `localhost` SAN) on the first
  loopback collect cycle and the Suite API call then succeeds. Statically this is the faithful OG
  path and the lesson confirms the intercept exists on the `getSocketFactory()` transport; but
  end-to-end success against the *org-CA* cert (vs the stock self-signed devel cert) is an
  appliance behavior no static check can prove. Recommend `qa-tester`/live verification on the
  prod-primary appliance after the pak is re-tagged against `sdk-buildkit-v1` 0.2.1.

**Verdict: APPROVE** — 0 BLOCKING. The PR may open. The one remaining unknown is inherent to the
fix (live appliance trust behavior), not a code defect.

---

# Revision 3 re-review — 2026-06-30 — verdict: APPROVE

Substantial follow-up (Codex P2 + remote-path threading) — full re-review, not a delta. The
previously-untouched `java.net.http` remote path is **retired entirely**; all Suite API calls now
flow through `openPlatformConnection` → `urlConnRequest`. Re-read source and binary; ran tests.

## Gating items — all verified

1. **Unified transport preserves every semantic through the collapse** (source-read +
   `SuiteApiStitchClient.java`):
   - Token lifecycle intact: `ensureToken()` double-checked lock, `reAcquireToken(old)` refresh-once,
     single 401 retry in `get`/`pushProperties`/`pushStats` (one re-execute, second 401 propagates /
     is WARN-swallowed by push) — no loop.
   - `discard()` nulls under lock + `releaseToken` swallows. JSON build/`jsonStr` unchanged.
   - `urlConnRequest` maps 401→`Suite401Exception`, non-2xx→`IOException`, 2xx→full body read
     (null-`InputStream`→`""`), `finally conn.disconnect()`, interrupt check at entry.
   - Connect **and** read timeouts set (`REQUEST_TIMEOUT`); headers (Accept always, Content-Type
     on body, Authorization on opsToken) match the retired path. **Paging is caller-supplied in the
     request path and passed through `suiteApiBase + apiPath` unchanged** — not lost.
   Nothing was lost removing the `HttpClient` path.

2. **Posture correct per peer** (`VcfCfAdapter.openPlatformConnection`, source + bytecode):
   `https.setSSLSocketFactory(getSocketFactory())` (TOFU `CustomSSLSocketFactory`) on **all** paths;
   the all-true verifier is installed **only inside `if (peer.isLoopbackAddress())`**; non-loopback →
   no override → JDK strict; `UnknownHostException` → caught, no override → **fail-closed strict**.
   - **No path gives a non-loopback peer the all-true verifier** (verified in source and in the jar:
     the `setHostnameVerifier` invokedynamic at bc#73-78 sits under the `isLoopbackAddress` branch at
     bc#65).
   - **No `insecureSslContext()`/trust-all anywhere in the Suite API transport** — source grep shows
     only retired-path javadoc; `SuiteApiStitchClient.class` has **0** `java.net.http`/trust-all refs.

3. **Breaking change is safe.** `build()` now throws `IllegalArgumentException` if `adapter == null`
   (unconditional, lines 259-261). Both `SuiteApiStitcher.create()` (line 109) **and**
   `createExplicit()` (line 144) pass `.adapter(adapter)`. All 6 real callers use
   `SuiteApiStitcher.create(this, …)` with a non-null `this`; none call the builder directly or
   `createExplicit` with a null adapter. **No caller can newly throw.**

4. **Jar matches source** (`vcfcf-adapter-base.jar`, rebuilt mtime 15:29):
   - `openPlatformConnection` bytecode: `getSocketFactory():CustomSSLSocketFactory →
     setSSLSocketFactory` (bc#48-51), `InetAddress.getByName → isLoopbackAddress` (bc#58-65),
     `invokedynamic verify → setHostnameVerifier` under the branch (bc#73-78),
     `UnknownHostException` in the exception table — and **0** `getAdapterTrustManager`/
     `SSLContext.getInstance` in the method.
   - `SuiteApiStitchClient.class`: **0** `java/net/http/HttpClient|HttpRequest|HttpResponse` /
     `HttpClient.send` (case-sensitive); the only "Http*" refs are `java/net/HttpURLConnection`
     transport methods. (A case-insensitive grep falsely flagged 31 — all `setRequestMethod`/
     `getResponseCode`-style `HttpURLConnection` methods; resolved, not stale.)
   - Test re-run by me: **18/18 pass** (adds non-loopback FQDN + IP `8.8.8.8` → strict).

5. **Standard hunts on the full delta:**
   - **global-default-leak:** none — no global/standalone content-import path here.
   - **key/label collision:** N/A.
   - **silent-downgrade:** none — the remote/CP posture change (trust-all → TOFU+JDK-strict) is a
     security **upgrade** and a **loud** failure mode (handshake/hostname rejection), aligned with the
     cert-item rule and spec §5. See WARNING below for the one behavioral consequence.
   - validate chain green; all 6 Tier 2 adapters recompile; the 4 adapters using
     `insecureSslContext`/`getPlatformSslContext` for **target-system** (vCenter/NAS) connections are
     out of scope and unaffected (`insecureSslContext()` still exists as the documented lab opt-out).

## WARNING (non-gating — advisory for first remote-collector deployment)

- **[VcfCfAdapter.java:1043-1054 / SuiteApiStitchClient remote path]** — dimension 8, spec §5. The
  remote/explicit Suite API path's TLS posture changed from trust-all to **TOFU trust + JDK-strict
  hostname**. This is intended and more correct, but it is a real behavior change: a remote-collector
  deployment whose primary Suite API cert is **not TOFU-approvable or whose SAN does not match the
  configured FQDN** would now **fail loudly** where the old trust-all silently connected. Currently
  **dormant** — every shipping adapter uses the ambient/loopback `create()` path; no caller exercises
  `createExplicit()`. → No code change needed; flag for whoever first wires remote-collector explicit
  credentials (the URL must target the primary FQDN with a SAN-matching, TOFU-registerable cert).

## NIT (non-gating)

- Redirect handling on the remote path changes from `java.net.http` `Redirect.NORMAL` to
  `HttpURLConnection` default (both follow same-protocol redirects); loopback unaffected.
- `InetAddress.getByName` resolves the host twice (once for verifier gating in
  `openPlatformConnection`, once at connect). Negligible.
- The test's 401-single-retry case remains a structural assertion, not an executed stub-transport
  exercise of `reAcquireToken`.

## What remains provable ONLY on a live appliance

- **Loopback (ambient):** that the `CustomSSLSocketFactory` TOFU intercept registers-and-retries the
  operator org-CA cert (no `localhost` SAN) on the first prod-primary collect cycle and the Suite API
  call then succeeds. (As before.)
- **Remote/CP (now also):** if anyone exercises `createExplicit()`, that the remote primary's cert is
  both TOFU-registerable (trust half) **and** SAN-matches the configured FQDN (JDK strict hostname
  half). Cannot be proven statically — needs a live remote-collector deployment. Dormant today.

**Verdict: APPROVE** — 0 BLOCKING. The PR may open. Recommend `qa-tester`/live verification on
prod-primary after the affected paks re-tag against `sdk-buildkit-v1` 0.2.1, and an explicit
remote-collector live test before that path is relied upon.
