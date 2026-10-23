# Framework review: adapter framework round (2026-10-23)

**Verdict: APPROVE.** 0 BLOCKING, 1 WARNING, 4 NIT. Every author claim I could test reproduced. Nothing in the change can mark an account ERROR when only some resources fail, or when a stop cuts the cycle short. Nothing leaks a credential or token through the new error-body surface. The kit stamp does not depend on git.

- Branch: `fix/adapter-framework-round-2026-10-23` at `dc87123` (ten commits on origin/main: a29a031, e45b1cf, 36f516b, 1d170cb, 20d4d1d, 3d018e6, 44a7733, 1772497, 35d770c, dc87123 skill wording)
- Area: `src/vcfcf_managementpacks/adapter_framework/` (VcfCfAdapter, SuiteApiStitchClient, SuiteApiStitcher, new SuiteApiHttpException), `sdk_builder.py`, `buildkit.py`, `build-framework.sh`, `.claude/skills/vcfops-sdk-adapter/SKILL.md`
- Issues: #227, #192, #201, #217, #224, #228, #223, #214
- Reviewed in a detached worktree. The branch is held by the author's worktree, so I used `git worktree add --detach`.

## Checks re-run

| Check | Result |
|---|---|
| Framework Java tests (author's runner, repointed at my worktree; SDK-only and with `adapter_runtime/lib/*`) | all OK. VcfCfAdapterTest 79/79, SuiteApiStitchClientTransportTest 81/81, SuiteApiStitchRelationshipTest 165/165, ComponentLoggerTest 17/17, AdapterInstanceStatusTest 20/20, CertificateReviewTest 86/86, AmbientCredentialTest 28/28, RelationshipBuilderTest 8/8, SuiteApiStitchClientTest 18/18. These match the claims. |
| pytest (full) | 2181 passed, 8 skipped, 0 failed |
| Validate chain (7 packages) | 7/7 rc=0 (managementpacks: 7 Tier 2 projects valid) |
| compliance `ci/run_java_tests.sh` (scratch copy) | rc=0. It compiles against the pak's stubs, not the framework jar, so it is change-independent. |
| validate-sdk compliance / unifi / synology (scratch copies, new jar) | all OK |
| build-sdk compliance (dev preview, scratch output) | rc=0. The pak's `vcfcf_compliance/lib/vcfcf-adapter-base.jar` manifest carries `Implementation-Version: 1.0.13` and `X-Vcfcf-Source-Commit: dc87123...` |
| Kit path: built a 1.0.13 buildkit, extracted it, and ran `python3 -m sdk_buildkit build-sdk` inside a fresh git repo with a different HEAD (db38dd0) | rc=0. The jar is stamped with the kit's SOURCE_COMMIT (`dc87123...`), not the pak HEAD, so git is not consulted in the kit. pak-compare: 1 WARNING, 0 BLOCKING. |
| Em-dashes in added lines (all 10 commits) | 0 |
| render-regression | n/a (no content renderer touched) |
| Stale-zip / CURRENT_TEMPLATE_VERSION (dimension 9) | n/a. No templates, builder.py, discrete/release_builder, assembly.py or render.py in the diff. Every Tier 2 pak does need a rebuild on buildkit 1.0.13, and the changelog row says so. |

## Hunted failure modes

**#223: can the account go ERROR wrongly?** No, for the cases I was asked about.
- The rule is `attempted > 0 && failed == attempted` (VcfCfAdapter.java:2717). One failure among many leaves the instance alone. Tests cover this: `testPartialFailureLeavesInstanceAlone` and the pure-rule check "1 of 2 failed: none".
- If the cycle is cancelled mid-way, the loop-top abort/interrupt check and the `InterruptedException` catch both set `outcome.cut`. The report gate at :935 also checks `isAbortRequested()`. An interrupt during either discovery step returns early. Test: `testStopMidCycleSetsNothing`.
- A NO_DATA_RECEIVING mapping does not count as a failure.
- **Reset after recovery (SDK 2.2 bytecode).** `AdapterBase.prepareCollectResult` builds a fresh `ResourceStatus` for the adapter instance each cycle, defaulting to `RESOURCE_STATUS_NONE`. The SDK's own `collect()` catch path calls `setAdapterError(new LocalizedMsg(t.getMessage()))` in the same per-cycle way. `isValidStatusForResource` routes the adapter instance through `isAdapterAllowedStatus`, which lists NONE, ERROR, DOWN, DATA_RECEIVING, NO_DATA_RECEIVING and COLLECTOR_DOWN. So ERROR is accepted on the instance and is not carried into the next cycle's CollectResult.

**#217: close() racing a collect in flight.** Safe by code reading.
- `closed` is set under `tokenLock`. `ensureToken` and `reAcquireToken` re-check it under the same lock. A close that lands during `acquireToken` waits for it, then releases that token, so no token is stranded. A request already holding the old token gets a 401, and the retry is refused with `ClientClosedException`.
- The SDK also serialises configure with collect: `configure()` only `tryAcquire`s the `locker` semaphore that `collect()` holds and queues otherwise. A reconfigure therefore rarely overlaps a cycle at all.
- Pak usage, checked in the clones: compliance swaps then discards (`releaseClients`). unifi and synology null the fields, then discard. vcommunity discards only in `onDiscard`. No pak calls a stitcher after discarding it.

**#201: credential or token leakage.** None found.
- The exception message is `Suite API <method> <url> HTTP <status>[ apiErrorCode <n>]`. The body is never in the message, and the framework never logs `getBodyExcerpt()` anywhere.
- The request token and password are not part of any message. The URL is the request path the pak chose.
- On the token-acquire path, a server error body reaches the pak only through `getBodyExcerpt()`. That is server text, and the Javadoc says so.

**#201: pak compatibility.**
- compliance's `OverridesStore.isAbsent` uses `\bHTTP 400\b` plus `"?apiErrorCode"?\s*[:=]\s*"?1501`. Against the new message, the 400 pattern matches and the 1501 pattern does not, because the framework writes a space, not `:` or `=`. A rebuild therefore leaves compliance's absent/failed semantics exactly as they are today. The new `getApiErrorCode()` is opt-in, as the changelog row says.
- vcommunity's `SolutionConfigStore` does not parse the status.
- The 401 text changed from "returned 401 — token" to "returned 401 (token". No pak regex keys on it (compliance's `HTTP (\d{3})` never matched "returned 401").

**#228: logger rename against the pak clones.**
- Every pak class is in its adapter's package (compliance, synology, unifi, vcommunity x3, template). So `componentLoggerName` renames only the framework's own `SuiteApiStitcher` logger.
- No file outside Java in any clone mentions `com.vcfcf.adapter.stitch`: no logging.properties, test script, doc grep or log-grep expectation. No pak ships a `logging.properties`.

**#227.**
- No log call or exception constructor under `adapter_framework/src` mentions a user or principal.
- `resolvedUsername` survives only in the token-acquire request body.
- Three tests assert that `principal=` and the user string are absent (configure lines, the 401 line, the no-token line).
- Synology's `principal=` redaction rule becomes dead weight but stays harmless.

**#192.**
- Push failures go through `logFailure`. Expected failures (the IOException family, which includes `SuiteApiHttpException`) get one WARN line, with the trace at DEBUG.
- An unexpected class gets its trace once per client and operation (`tracedFailures`, per instance, bounded by distinct exception classes). After that it is one line.
- `InterruptedException` restores the interrupt flag.
- `ClientClosedException` gets one WARN per client, then DEBUG.

**#224.** `raiseToInfo` calls `setLevel(INFO)` only when `!isInfoEnabled()`. A WARN floor is still raised as before, and DEBUG/TRACE are kept.

**#214.**
- The stamp is written on both build paths.
- Inside the kit, `_framework_source_commit` reads `SOURCE_COMMIT` and returns "unknown" if it is absent. It never runs git (proven above).
- The runtime label reads this class's own code-source jar, not the first `META-INF/MANIFEST.MF` on the loader.
- The JVM-wide-setter guard test is present and green.

**ThreadDeath (#242), pre-existing, note only.** `VcfCfAdapter.java:2349` still has `catch (VirtualMachineError | ThreadDeath fatal)`. This branch does not touch it.

## BLOCKING

None.

## WARNING

- **W1 [VcfCfAdapter.java:2732 `adapterInstanceFailureMessage`]** Authority: the shared reviewer doctrine (unproven is a finding) and `knowledge/rules/` no-secrets posture.
  - **What's wrong:** the first failing resource's raw exception message (up to 300 chars) is now written onto the adapter instance status, which is the account row any Ops user with Integrations access can read. Until now that text went only to the instance log.
  - **Why it is not BLOCKING:** the SDK's own collect() failure path does the same with `Throwable.getMessage()`, so this matches vendor behaviour. Synology already builds its collect-path exceptions from labels only (DEF-001) because the framework logs them raw.
  - **Why it is still a finding:** nothing tells pak authors that a collect() exception message is now UI-visible, and I did not prove the same discipline for compliance, unifi or vcommunity.
  - **Fix:** one sentence in `tier2_architecture.md` (Adapter instance status) and in the vcfops-sdk-adapter skill: "the first failure's exception message is shown on the account row; collect() must throw messages free of credentials, session ids and tokens". Optionally reuse the existing `loggable` sanitising in the framework.

## NIT

- **N1 [VcfCfAdapter.java:935]** The report gate checks `!outcome.cut && !isAbortRequested()`, but not `Thread.currentThread().isInterrupted()`. Suppose an interrupt arrives during the last resource and the collector wraps it (InterruptedIOException or a runtime wrapper) instead of throwing InterruptedException, with no stop requested. Then the loop ends without `cut` and the instance can be set ERROR. The tier2 doc says "a cycle cut short by ... an interrupt sets nothing". **Fix:** add the interrupt check to the gate and add a test with a wrapped interrupt on the last resource.
- **N2 [.claude/skills/vcfops-sdk-adapter/SKILL.md:116, :125]** Two places where the skill wording does not match the Java:
  - :116 says "a failed push is one WARN line per cycle, with the stack trace at DEBUG". It omits that the first unexpected exception class per client and operation keeps its trace at WARN (`logFailure`, SuiteApiStitchClient.java:852). The tier2 doc states this correctly.
  - :125 says "Framework helpers log under the adapter's class name (`<Adapter>.SuiteApiStitcher`)". The rename applies only to loggers obtained via `componentLogger(SuiteApiStitcher.class)` (the client logs through whatever logger the pak passes to `create`), and the name is the fully qualified adapter class, for example `com.vcfcf.adapters.unifi.UniFiAdapter.SuiteApiStitcher`. **Fix:** say both.
  - The rest of the new skill text checks out against the Java: `get(path, accept)`, SuiteApiHttpException as an IOException carrying status, apiErrorCode and excerpt, `close`/`isClosed` refusing calls and never re-acquiring, no principal.
- **N3 [sdk_builder.py:146 / buildkit.py:899]** `_framework_source_commit`'s factory branch and `_factory_source_commit` are near-identical git logic in two modules, a drift risk. **Fix:** have buildkit import the sdk_builder helper, or share one function.
- **N4 [SuiteApiStitchClient.java:1213]** The ` apiErrorCode <n>` message suffix is now an implicit contract. compliance's 1501 regex misses it today only because of the separator. A later change to `apiErrorCode=<n>` or `apiErrorCode: <n>` would silently flip compliance's missing-overrides-file semantics on a rebuild. **Fix:** pin the exact message shape in `testGetErrorCarriesApiErrorCode` (it currently asserts only "contains"), with a comment naming compliance's `OverridesStore` as the reason.

## Cannot be proven without a collector

- What the Integrations > Accounts row actually shows for an adapter instance set ERROR or DOWN with a message, and that the next healthy cycle's NONE clears it on the platform side. I proved this only within the SDK's CollectResult. The tier2 doc says the same.
- #228 on a Cloud Proxy. The doc names this a live check owed. `ComponentLoggerTest` reproduces the mechanism against the real SDK factory and log4j-core, and the Cloud Proxy's package-scoped logger entry is still unexplained.
- #214's `frameworkManifest()` under the collector's real adapter class loader. If its code source is not a plain file URL, the label falls back to "version unknown" rather than failing, but which branch it takes is unproven.
- #223 behaviour for each pak's real failure shapes: whether each pak's collector throws on every resource when its login is cached-failed (UniFi), or swallows and reports through data (which under-reports but never falsely reports ERROR).

## Out of scope (not in this diff; recorded for the orchestrator)

- `setStatusSafe` validates child statuses against the adapter-instance list. That is already filed as #245.
- vcommunity (all three variants) replaces `suiteStitcher` in `configureAdapter` without discarding the previous one, so the old token waits for TTL. This is pak-side and pre-existing; #217's closed state does not help because the old client is never closed. It belongs in an issue on the vcommunity pak repo.

## BUILDKIT_VERSION collision

Three in-flight branches set `BUILDKIT_VERSION = "1.0.13"`: gate integrity, #211 compile target, and this one. Whichever merges first keeps 1.0.13. The second must rebase to **1.0.14** and the third to **1.0.15**, each with its own `tier2_architecture.md` changelog row and its own tag (`sdk-buildkit-v1.0.14`, `-v1.0.15`). They must not share or amend the 1.0.13 row: the jar's `Implementation-Version` is now the only on-collector signal of which framework a pak carries, so two different framework builds stamped 1.0.13 would make that signal lie.

## If shipped as-is

After a rebuild on 1.0.13, operators get:
- an account row that goes ERROR or DOWN when every resource fails,
- framework stitcher lines in the per-instance log under the adapter's name,
- no principal in logs,
- a framework version line at first configure.

The residual exposure is that the account row shows the first failure's raw exception text (W1). Paks that already sanitise their collect-path exceptions are unaffected.
