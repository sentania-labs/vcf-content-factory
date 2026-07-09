# Framework Review — ambient credential v3, breadcrumb micro-round (CLOSEOUT)

- **Area:** `vcfops_managementpacks/adapter_framework` — `stitch/AmbientCredential.java`, `stitch/SuiteApiStitchClient.java`, `test/.../AmbientCredentialTest.java`
- **Change:** the WARNING-1/NIT-1/NIT-2 close-out delta on top of the APPROVE-with-advisories at `ambient-credential-v3-instance-first.md` — a sanitized, per-thread diagnostic breadcrumb (`injectedFailureReason`) surfacing *why* the platform-injected "instance" credential lost to a file candidate, plus the two NIT fixes (narrowed catch, corrected test javadoc).
- **Verdict:** APPROVE
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT
- **Date:** 2026-07-02
- **Scope note:** re-review of the micro-round delta only; the four sibling gated diffs in the combined working tree (VcfCfAdapter / RelationshipBuilder / SuiteApiStitcher / cli.py / sdk_builder.py) carry no breadcrumb logic and are covered by their own review files.

## Checks re-run (independently, not taken from tooling's block)

- **Framework jar rebuild:** `build-framework.sh` — 20 sources, compile clean, SDK-jar-only classpath (no aria-ops-core symbol). `vcfcf-adapter-base.jar` (64K) rebuilt.
- **Java suites:** `AmbientCredentialTest` **28/28** (matches "+3 new"); `SuiteApiStitchClientTest` **18/18**; `RelationshipBuilderTest` **8/8**. All green in this sandbox (Crypt-absent SKIP branches present as designed but no failures).
- **pytest:** **457 passed**, 4 skipped, 162 deselected. Matches the claimed 457.
- **validate-chain:** PASS — sm/dash/cg/sym/alerts/reports OK; `vcfops_managementpacks validate` = 6 Tier 2 SDK adapters valid (recompile clean).
- **render-regression / pak-compare:** n/a — no renderer/builder/template surface touched.

## Focus-item verification

1. **ThreadLocal hygiene — SOUND.** Set/consume/clear is paired within one synchronous `load(AdapterConfig)` call on one thread:
   - Every null-return path of `tryInjectedCredential` **with a non-null config** sets `LAST_INJECTED_FAILURE_REASON` (creds-null, blank-username, `catch`, empty-password). The instance-**won** path and the `adapterConfig == null` short-circuit never touch it.
   - `load`'s non-override branch always calls `.remove()` after the (conditional) `.get()`, and does so **before** `loadFromFileCandidates()` — so even if the file load throws `IOException`, the thread-local is already clean.
   - No leak across constructions: the only early return that skips `.remove()` is the instance-won path, which never *set* the thread-local, so it cannot carry a stale value into a later healthy construction. The override branch never calls `tryInjectedCredential`, so nothing to clear.
   - `.remove()` (not `.set(null)`) is used, so no empty entry is retained across collector thread-pool reuse.
   - Concurrency: `ThreadLocal` is per-thread; concurrent adapter instances resolve on distinct collector threads, so there is no cross-instance race. `AmbientCredentialTest.testNoInjectedFailureReasonRecordedWhenConfigAbsent` proves `tryInjectedCredential(null)` does not clobber a prior reason (short-circuits before the thread-local). The only path that leaves the thread-local populated after return is a **direct** `tryInjectedCredential` call bypassing `load` — which happens **only in tests**; production's sole caller is `SuiteApiStitchClient.build()` → `load(...)`, which always clears. Not a defect.
   - Misattribution check: for a non-null config, `load`'s `.get()` runs immediately after `tryInjectedCredential` on the same thread, and every null-return path there set the thread-local *this* invocation — so `.get()` can never read a previous call's value in that branch.

2. **Test seam `peekLastInjectedFailureReasonForTest` — ACCEPTABLE.** Package-private, static, read-only; never invoked by production code (`load` reads the thread-local directly). It cannot alter production behavior — it is the standard package-private test accessor pattern, strictly better than the reflection/`@VisibleForTesting`-on-a-field alternatives. No test state leaks into prod.

3. **Breadcrumb sanitization — BOUNDED, SECRET-FREE.** `describeInjectedFailure(Throwable)`: for a **non-`LinkageError`** it returns `getSimpleName()` **only** — never `getMessage()`. This is the load-bearing protection: the only exception that could carry password-adjacent bytes is a decrypt failure inside `getPassword()`, which surfaces as an `Exception` (not a `LinkageError`) and is therefore reduced to a bare class name. For a `LinkageError` it appends the message, but the realistic case (`NoClassDefFoundError` on the missing `com.vmware.vcops.security.Crypt`) carries only the missing class name; a `LinkageError` from `getPassword()` cannot embed the plaintext/ciphertext. Logged once at INFO by the Builder (`SuiteApiStitchClient.java:349`) with no password, no raw non-linkage message. Sound.

4. **The reorder — MISATTRIBUTION CLOSED.** `AmbientCredential.java:460-465`: `getUserName()` and the blank-username guard now execute **before** the throwing `getPassword()` call. A blank-username credential whose `getPassword()` would throw now returns reason `"credentials null/blank"` (correct: the credential was unusable on username alone) and never reaches — nor misattributes a `LinkageError` from — `getPassword()`. Proven by `testInjectedFailureReasonRecordedWhenConfigPresentButUsernameBlank` (blank username + non-null password → reason `"credentials null/blank"`, not an exception class).

5. **Suites + validate + delta scope — CONFIRMED.** All suites and the validate chain green (above). Breadcrumb logic is confined to exactly the three claimed files (`grep` for `InjectedFailureReason` / `instance-credential not used` / `peekLastInjected` / `LAST_INJECTED_FAILURE` across `vcfops_managementpacks/` + `tests/` returns only those three). The combined five-diff tree recompiles clean and every suite passes, so the tree is coherent.

## Advisory closure (from `ambient-credential-v3-instance-first.md`)

- **WARNING-1 (swallowed injected-failure cause invisible to operator) — CLOSED.** The Builder now logs one INFO `instance-credential not used reason=<sanitized>` exactly when a config was present but the instance source lost (`getInjectedFailureReason() != null`); config-null stays silent (`load` only populates the reason when `adapterConfig != null`). This is the precise fix the WARNING recommended, and it uses the Builder's logger (AmbientCredential has none), as advised.
- **WARNING-2 (stale Tier 2 `.pak` binaries after base-jar rebuild) — STILL STANDS as a process flag, not re-opened.** This is a release-discipline advisory to the orchestrator (rebuild stitch-using Tier 2 paks before any `v*` tag), not a code defect; the micro-round neither closes nor re-opens it. Correctly out of code scope.
- **NIT-1 (catch too broad) — CLOSED.** Both `catch (Throwable)` narrowed to `catch (Exception | LinkageError)` (`AmbientCredential.java:466`, `SuiteApiStitchClient.java:395`) — honors the documented `NoClassDefFoundError` case while letting `VirtualMachineError`/`ThreadDeath` propagate. Only residual `catch (Throwable` strings are in explanatory comments.
- **NIT-2 (test javadoc drift) — CLOSED.** `testOverrideTakesPriorityOverInjected` javadoc (lines 331-341) now correctly describes override-beats-injected, not the stale "all-absent" copy.

## NIT

- **[AmbientCredential.java:298-300 / javadoc 288-294]** `describeInjectedFailure` appends the message for **every** `LinkageError` subtype, while the javadoc justifies it as "just the missing class name" — true for `NoClassDefFoundError` specifically, looser for e.g. `UnsatisfiedLinkError` (could carry a native-library filesystem path). No secret exposure (a library path is not credential material, and `getPassword()` triggers no native linkage), so this is cosmetic — tighten the javadoc wording or gate the message on `NoClassDefFoundError` if you want the comment and code to match exactly. Not blocking.

## If shipped as-is

An operator on a node where the injected "instance" credential is present-but-unusable (missing `com.vmware.vcops.security.Crypt`, null/blank creds) now gets one INFO line — `file=automation` plus `instance-credential not used reason=NoClassDefFoundError: com/vmware/vcops/security/Crypt` — closing the exact field-debugging blind spot WARNING-1 named. No secret is logged, no thread-local leaks across constructions or races between concurrent adapter instances, and blank-username-with-throwing-password can no longer be misclassified as a linkage failure. No functional regression on any credential path; no key/label collision, wire-format drift, or global-default leak.

**Report:** context/reviews/framework/ambient-credential-v3-closeout.md
