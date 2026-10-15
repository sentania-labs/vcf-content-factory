# UniFi build 14 review (sdk-adapter-reviewer)

- **Adapter:** `content/sdk-adapters/unifi` (repo `sentania-labs/vcf-content-factory-sdk-unifi`)
- **Branch reviewed:** `feat/build-14-availability-and-tls`, tip `aeecdae`, 7 commits on `origin/main` (v1.1.0.13)
- **Brief:** `knowledge/designs/sdk-adapters/unifi-build-14-availability-and-tls.md`
- **Fork issues in scope:** #13, #11, #12, #19, #25
- **Date:** 2026-10-15
- **Verdict:** CHANGES REQUESTED (1 BLOCKING, text only; 3 WARNING; 6 NIT)

## Bottom line

The code does what the five issues ask and I found no path where an
unreadable controller, site or device becomes a published value. The
failure cache, cycle hook and site isolation hold up under the hunt
questions. The one blocker is documentation: CHANGELOG and overview tell
the operator a failed cycle produces "one WARN", but the framework still
writes one WARN with a stack trace per resource (plus one for the
discovery step), so the brief's own devel proof ("shows one WARN") will
contradict the shipped docs. The fix is wording. Separately, the
`allowInsecure=false` default ships without the certificate review hook,
which is acceptable for a 0.x dev build but should gate the v1.1.0.14
tag.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| validate-sdk pass | Confirmed: `OK: content/sdk-adapters/unifi is a valid Tier 2 SDK adapter project` |
| Dev pak 0.0.0.14, sha256 `c275f317...` | Confirmed the author's file exists with sha256 `c275f3178359c52d8c67b655fc96bb97b8e8b5ce6e56e05e8107e4fd1f1edfd2`. My own `build-sdk` reproduces 0.0.0.14 (different sha `90a3dfc7...`, expected: build timestamps). Built `describe.xml` carries `allowInsecure default="false"`. |
| pak-compare 0/0/0 vs v1.1.0.13 release pak | Confirmed on my build: `0 BLOCKING, 0 WARNING, 0 INFO`. The reference pak sha256 `b14b5a09...` matches the GitHub Release v1.1.0.13 asset digest. |
| `ci/run_java_tests.sh` passes (5 Java + 1 Python) | Confirmed: all six pass. |
| Tests fail when old logic is substituted | Confirmed and extended. Six mutations in a scratch copy, each caught by exactly one test: no failure cache (SnapshotCacheTest), stamp at build start (SnapshotTimingTest), wall-clock-only reuse (SnapshotTimingTest), no auth back-off (SnapshotCacheTest), any failed site fails all (SiteReadsTest), ConnectException-only DOWN (FailureMappingTest). |

Not covered by tests (correct by reading, see NIT-5): the adapter-side
wiring in `UniFiAdapter.java` (findDevice throw, requireSiteRead,
relationship skip, the needsRediscovery cycle hook), because those need
the SDK jar.

## Defect registry (knowledge/context/defects.md)

No open defect names `unifi`. DEF-002 and DEF-007 (unifi) are closed;
nothing in this build reopens them (the vmnic stitch emission path and
the CP collect path are unchanged; the stitch now simply sees fewer
switches when a site fails, and its foreign edges are additive).

Registration candidate: **W1** (no certificate review hook with a
secure default). It should be registered and closed before a
`v1.1.0.14` tag so RULE-012's defect gate enforces it.

## Hunt questions

### 1. SnapshotCache

- **Cached failure across a configuration edit:** cannot happen.
  `configureAdapter` publishes a new `Configured` holder (new
  `UniFiApiClient` plus new `SnapshotCache`) in one volatile write
  (`UniFiAdapter.java:202-207`); `currentSnapshot()` reads the holder
  once and uses its client and cache together (`:578-585`). The old
  holder, with its failure, is unreachable after the edit. Residual
  (live only): that VCF Ops calls `onConfigure` when the credential is
  edited on the Credentials page rather than the instance. The brief's
  wrong-password devel step covers it.
- **Cached success across a cycle boundary:** cannot happen. Reuse needs
  `valueCycle == cycle` AND age below 15 min (`SnapshotCache.java:119`).
  The age test only ever shortens reuse inside one cycle.
- **Two threads building twice:** cannot happen. `get` and `beginCycle`
  are `synchronized` and the build runs under the lock; the second
  caller sees the fresh value. The only legitimate second build is when
  a discovery pass (`beginCycle` via `getDiscoverer`) lands in the middle
  of a collect cycle: one extra build, not a storm.
- **Cycle start marking:** `VcfCfAdapter.onCollect` is `final` and calls
  `collector.needsRediscovery(config)` unconditionally, once, before
  discovery and the resource loop (`src/vcfcf_managementpacks/adapter_framework/src/com/vcfcf/adapter/VcfCfAdapter.java:728`).
  So for every collect cycle the hook fires exactly once; the framework
  cannot "call neither". `getDiscoverer` is only called from
  `onDiscover` (`:679`), which 9.0.2 never invokes. If a future
  framework change stopped calling `needsRediscovery`, the safety net
  would serve a snapshot up to 15 min (three default cycles) under fresh
  timestamps; that dependency on an undocumented side effect is NIT-1.

### 2. 429 on a non-login call

Yes, a 429 (or a 403) on `/self/sites`, or on `stat/device` for every
site, triggers the 15-minute back-off, and the WARN calls it an
"authentication refusal" (`SnapshotCache.java:142`). It does not reach
the adapter lightly: `RetryPolicy` has already retried a 429 three times
with back-off, and `SessionCookieAuth` has already invalidated the
session, logged in again and replayed a 401/403 once
(`SessionCookieAuth.java:83-85`, `ManagedHttpClient.java:191-216`). A
429 that survives that is sustained rate limiting, and backing off for
15 minutes is the right response to it; 60 s would also be safe (one
build per cycle either way). I accept 15 minutes. The cost is three
lost cycles on a transient rate limit, and the message mislabels a data
call 429 as a login refusal; `UniFiHttpException.isLogin()` exists for
exactly this distinction and is never read (NIT-2).

### 3. #19 site isolation

- `findDevice` (`UniFiAdapter.java:1451`) throws when the MAC is absent
  and any site failed; every device-backed collector (gateway, WAN,
  switch, port, AP, radio: `:664, :715, :750, :806, :865, :898`) goes
  through it, so no device on a failed site is published with defaults.
  Site and Wireless Summary call `requireSiteRead` first (`:650, :951`).
  NVR and cameras read Protect only and are unaffected. Correct.
- Relationships (`:1066`, `:1149`): `RelationshipBuilder` emits
  `setRelationships` only per parent with a non-empty child batch
  (`RelationshipBuilder.java:318-334`), so skipping a failed site as a
  parent leaves its stored device edges, and a device on that site (not
  emitted as a parent) keeps its ports, radios and WANs. World still
  lists every site. The NVR is not re-parented under a failed first
  site, and its cameras are still emitted under it. Correct.
- Discovery (`enumerateResources`, `:411`) sees an empty device list for
  a failed site; registration is additive, so nothing is removed.
- Device moving sites: identity is the MAC, not the site, so a device
  found on any readable site collects normally and is never wrongly
  treated as failed. Two transient edge cases, both self-healing once
  the failed site reads again (NIT-3): moved from a failed site to a
  readable one, it briefly has two site parents; moved from a readable
  site into a failed one, the readable site's full set drops it and the
  new edge waits for the failed site, so it is briefly orphaned (and
  ERROR, correctly).

### 4. allowInsecure default flip without the review dialog

The author's account is right in effect. `UniFiAdapter` does not
override `certificateCheckUrls` (grep: no hit; `platformSsl(this)` at
`:274`), so `getConnectionURLs` falls back to the SDK default,
`NOT_SUPPORTED`, and Validate Connection never shows the Review and
Accept dialog (`VcfCfAdapter.java:1345-1371`;
`knowledge/context/tier2_architecture.md` "Accepting an untrusted target
certificate"). With the default now `false`, a fresh instance against a
stock UniFi OS console (self-signed) fails Test Connection; `onTest`
maps it to the framework's "No endpoint was offered for certificate
review ... set it to true, otherwise update to a pack version that
supports certificate review" text (`:1518-1550`). The only operator path
is `allowInsecure=true`.

One correction to the author's wording: the platform trust manager also
trusts certificates signed by a CA in the VCF Operations trust store
(compliance build 93 review, B1), so a console with a CA-signed
certificate works without the dialog. The common case (factory
self-signed) does not.

Compliance build 93 is the reference idiom: it overrides
`certificateCheckUrls(ResourceConfig)` (with `@Override` so an old
buildkit fails to compile) and returns the endpoint derived only from
the passed, possibly unsaved config
(`content/sdk-adapters/compliance/src/com/vcfcf/adapters/compliance/ComplianceAdapter.java:305`).
The hook is in buildkit 1.0.11, which the unifi tag workflow already
resolves (`sdk-buildkit-v1` points at v1.0.11).

Assessment: acceptable for a 0.x dev build, because it is secure, the
CHANGELOG and docs/installing.md say plainly that no review is offered,
and existing instances keep their stored value. Not acceptable for the
release: shipping a secure default whose only working path for the
common console is turning security off trains every operator to set
`true`, which defeats the point of #13. The release needs W1.

### 5. Docs

- Default agrees everywhere: describe.xml `false`, README `false`,
  REFERENCE `false`, docs/installing.md `false`; the upgrade note is in
  CHANGELOG, README (pointer) and installing.md. The Python test pins
  the four defaults and the upgrade note.
- CHANGELOG heading is `## 0.0.0.14 (Unreleased)` and says the 1.1.0
  line is unchanged until a tag (RULE-014 consistent).
- No em-dash in hand-written new text. The only added em-dash is the
  generated `docs/inventory-tree.md` header (between "Do not edit" and "regenerated"),
  which is generator output, not the author's (NIT-6).
- installing.md describes validation as "certificate chain", avoiding
  the compliance 93 name-check overclaim. Good.
- The "one WARN" claim is wrong: see B1.

### 6. Re-runs

All done, see Claims check.

## Findings

### BLOCKING

**B1. Docs say a failed cycle logs one WARN; the adapter log gets one
per resource, each with a stack trace.** Dimension 11 (docs that
contradict behavior); dimension 6 (logs must let an operator tell what
happened).

- `CHANGELOG.md:10` "the adapter log gets one WARN";
  `docs/overview.md:121` same; `CHANGELOG.md:12` and
  `docs/overview.md:136` "one WARN naming the site";
  `UniFiAdapter.java:575` javadoc "(one WARN, no new login)".
- Behavior: `VcfCfAdapter.onCollect` logs
  `logWarn("onCollect: error collecting <resource>: <msg>", e)` for
  every resource whose collect throws (`VcfCfAdapter.java:823`), and
  `logWarn(..., e)` writes the throwable (`:1854-1855`). With a wrong
  password the adapter log gets: one WARN from the collect-path
  discovery step (which is the first caller and gets the original
  exception, `:759`), one `UniFi snapshot build failed` WARN from the
  cache, and one WARN with stack trace per UniFi resource
  (`CachedFailureException` carrying the full cause chain). A failed
  site produces one WARN per resource on that site plus the site WARN.
- Why it matters: the login storm is fixed, which is what #11 asked.
  But an operator told to expect one line will see hundreds, and the
  brief's devel proof ("a wrong-password edit shows one WARN") will
  fail against its own docs. The installing.md troubleshooting line
  (`:99`) is accurate because it says one WARN *of that text*.
- Smallest correct fix (text only): say "one `UniFi snapshot build
  failed` WARN, and one framework line per resource that fails from the
  cached result without contacting the controller" in CHANGELOG #11 and
  #19 entries, overview.md:121 and :136, and the `:575` javadoc. Also
  "the first resource reports it" should read "the first caller
  (usually the discovery step) reports it". No code change required;
  quieting the per-resource framework WARN is a framework issue, not
  this build.

### WARNING

**W1. Secure default ships without the certificate review hook.**
Skill § SSL convention; `knowledge/context/tier2_architecture.md`
"Accepting an untrusted target certificate"; brief "What must not
regress". `UniFiAdapter.java` has no `certificateCheckUrls` override
(transport `platformSsl(this)` at `:274`). Fine for 0.0.0.14 as
documented; for the release, add the override exactly as compliance
build 93 does: `@Override protected List<String>
certificateCheckUrls(ResourceConfig rc)` returning
`https://<host>:<port>` from the passed config, empty when host is
blank or when insecure. Use the pak's own `UniFiConfig.parseAllowInsecure`
(untrimmed) for the insecure test, not the framework's
`isAllowInsecure` (trimmed), or a stored `" true"` would get no dialog
while the client connects securely. Then soften the docs' "this build
does not offer the certificate for review". Registration candidate so
the v1.1.0.14 tag is gated on it.

**W2. The adapter-side #19 wiring has no test.** Dimension 9 (prove
behavior preservation); brief Proof ("one failed site leaves the others
collected"). SiteReadsTest proves the helper; nothing exercises
`Snapshot.findDevice` throwing (`UniFiAdapter.java:1451`),
`requireSiteRead` (`:1463`), or the parent skips at `:1066` and `:1149`,
which is where a regression would publish defaults or drop edges. I
verified them by reading and they are correct. Fix options: move the
lookup and the "which parents to emit" decision into an SDK-free helper
the plain-main tests can drive, or accept and cover it in the devel
proof by blocking one site. Not blocking because the code is correct
today.

**W3. Failure-cycle log volume, not just the docs.** Dimension 6. Even
with B1's wording fixed, every resource logs a multi-line stack trace
every cycle while the controller refuses the password (up to 15 min of
cycles before the next login). The adapter cannot change the framework
line, but it could keep the stack out: the framework passes the
exception it received, and `CachedFailureException` carries the full
original chain as its cause. A cached failure without the cause chain
(message only, with the original described inline, as it already is)
would make each per-resource line one line. Weigh against
`mapCollectException`, which needs the chain for DOWN vs ERROR (it
could be classified once and carried as a field). A follow-up issue is
reasonable if the author prefers not to change it in this build.

### NIT

- **NIT-1** `UniFiAdapter.java:517-521`: the cycle hook rides on
  `needsRediscovery`, whose contract (`VcfCfCollector.java:108-119`)
  does not promise to be called every cycle. True today (final
  `onCollect`, `:728`). Worth a framework issue for an explicit
  start-of-cycle hook, or a framework test pinning the call.
- **NIT-2** `UniFiHttpException.java:31`: `isLogin()` is never read.
  Either use it (for example to word the WARN "rate limited" instead of
  "authentication refusal" for a data call 429, `SnapshotCache.java:142`)
  or drop the field.
- **NIT-3** `UniFiAdapter.java:1066`: a device that moves between a
  failed and a readable site has two site parents or none until the
  failed site reads again. Self-healing; worth one sentence in
  overview.md next to "its existing relationships are left as they
  are".
- **NIT-4** `SiteReads.java:57-71` with `RetryPolicy` (3 attempts,
  30 s timeout, retries every IOException): when `/self/sites` answers
  but `stat/device` hangs on every site, one build costs about 93 s per
  site before the all-sites failure. Far better than before (that was
  per resource), but on a many-site controller one build can exceed
  the cycle. A short-circuit after the first unreachable site
  (`UniFiFailures.isUnreachable`) would cap it.
- **NIT-5** No test drives `UniFiAdapter` itself; see W2.
- **NIT-6** `docs/inventory-tree.md:3`: the generated header carries an
  em-dash between "Do not edit" and "regenerated". Generator output in
  `src/vcfcf_managementpacks`, not the author's text; a framework fix if
  wanted.

## Dimension walk (items not covered above)

- **1 Cardinal correctness:** no read failure becomes a value. `/self/sites`
  failure and all-sites failure still throw; a partial failure throws
  per affected resource. stat/health failure keeps its pre-14 behavior
  (WARN, no metrics for the aggregate), unchanged by this diff.
- **2 Reflection-tolerant reads:** not applicable (REST/JSON adapter,
  `SimpleJson` null-tolerant).
- **3 Exception granularity:** `SiteReads` catches per site and rethrows
  `InterruptedException`; `SnapshotCache` does not cache interrupts. The
  pre-existing `catch (Exception)` around `statHealth` and Protect
  (`UniFiAdapter.java:1385, :1416`) also swallows an interrupt; not in
  this diff.
- **4 Canonical loader:** not applicable.
- **5 Stitching identity:** stitch code unchanged; foreign keys still
  carry Suite API uniqueness flags (build 9+). No new foreign keys.
- **6 Logging / secrets:** new messages carry the redacted path and HTTP
  status only; `insecureWarning` carries host and port only; the login
  body is never echoed. No secret found. Volume: B1, W3.
- **7 Resource hygiene:** the holder swap releases the old cache; the old
  HTTP client is discarded by the framework before `configureAdapter`.
  No per-cycle growth (the cache holds one snapshot and one failure).
- **8 API discipline:** one build per cycle is now explicit, an
  improvement over the 60 s wall-clock rule.
- **9 Build hygiene:** `build_number` 13 to 14, CHANGELOG entry present,
  diff confined to the five issues plus tests and docs.
- **10 Gap honesty:** the missing review dialog is named in CHANGELOG
  and installing.md (W1 is about closing it, not hiding it).
- **11 Docs parity:** no relationship or stitch behavior added; the
  partial-site relationship behavior is documented in overview and
  CHANGELOG. B1 is the contradiction.
- **13 describe.xml import rules:** no alerts or symptoms touched; the
  only describe change is the identifier default.

## If shipped as-is

A dev install behaves correctly: a wrong password costs one login per
15 minutes instead of one per resource, a dead site no longer takes out
the others, an unreachable controller shows DOWN. An operator reading
the CHANGELOG would expect one WARN and find one stack trace per UniFi
object per cycle, and a new instance against a stock self-signed console
fails Test Connection until they set Allow Insecure SSL to true.
