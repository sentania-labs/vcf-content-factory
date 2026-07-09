# Framework Review — ambient credential v3 (instance-first)

- **Area:** `vcfops_managementpacks/adapter_framework` — `stitch/AmbientCredential.java`, `stitch/SuiteApiStitchClient.java` (+ `SuiteApiStitcher.java` javadoc; `AmbientCredentialTest.java`)
- **Change:** ambient Suite API credential now prefers the platform-injected per-instance credential (`AdapterConfig.getAdapterCredentials()`) ahead of `automationuser.properties` → `maintenanceuser.properties`; explicit override still absolute-priority.
- **Verdict:** APPROVE
- **Findings:** 0 BLOCKING / 2 WARNING / 3 NIT
- **Date:** 2026-07-02
- **Scope note:** fifth of five gated `vcfops_*/` changes shipping in ONE PR. This review covers the ambient-credential-v3 delta and confirms the combined tree is coherent (all suites green below).

## Checks re-run (independently, not taken from tooling's block)

- **validate-chain:** PASS — sm/dash/cg/sym/alerts/reports all OK; `vcfops_managementpacks validate` = 6 Tier 2 SDK adapters valid (recompile clean).
- **Java suites:** `AmbientCredentialTest` 21/21 (3 SKIP, see NIT); `SuiteApiStitchClientTest` 18/18; `RelationshipBuilderTest` 8/8.
- **pytest:** 457 passed, 4 skipped, 162 deselected. Matches expected 457.
- **render-regression / pak-compare:** n/a — no renderer/builder/template surface touched.

## Independent verification of tooling's load-bearing claims

1. **Bytecode claim — VERIFIED TRUE.** `javap -c` on `vrops-adapters-sdk-2.2.jar`:
   `AdapterCredentialConfig.getPassword()` = `invokestatic com/vmware/vcops/security/Crypt.getDefaultCrypt` → `getfield password` → `invokevirtual Crypt.decrypt` → `areturn`. It is **not** a bare field accessor. `getUserName()` **is** a bare `getfield userName`. Matches `knowledge/context/api-surface/per-instance-suiteapi-credential-contract.md` §7.
2. **`com.vmware.vcops.security.Crypt` absence — VERIFIED.** Scanned every jar in `adapter_runtime/` (incl. `lib/`): the class is present in **none**. Contrast `com.integrien.alive.common.security.Crypt` (the file-decrypt path) which **is** in `vrops-adapters-sdk-2.2.jar`. So `getPassword()` on this classpath raises `NoClassDefFoundError` — a `LinkageError`, not an `Exception`. `catch (Throwable)` (not `catch (Exception)`) is the **correct** choice to honor crash-the-cycle. **This is not theoretical — it fired live in the sandbox:** `testInjectedCredentialPreferredWhenPresent` hit the `NoClassDefFoundError`, `tryInjectedCredential` returned `null` (source absent), no Throwable escaped. The guarantee is proven, not asserted.
3. **Clean-room / SDK-public chain — VERIFIED.** `AdapterConfig.getAdapterCredentials()`, `AdapterCredentialConfig.getUserName()/getPassword()`, and `AdapterBase.getAdapterConfig()` are all `public` SDK types (javap). No `aria-ops-core` / `com.vmware.tvs.*` import added; framework still compiles SDK-jar-only. The "`getAdapterConfig()` already public on AdapterBase, VcfCfAdapter untouched" claim is TRUE — `VcfCfAdapter`'s diff carries only javadoc mentions of ambient, no credential logic.
4. **Order-of-precedence — VERIFIED.** Override > injected > automation > maintenance. `testOverrideTakesPriorityOverInjected` proves override is tried and the injected credential is not consulted when the sysprop is set (`load(cfg)` with a bogus override path throws IOoException naming the override, not `instancePrincipal`). `buildCandidates()` order (automation[0], maintenance[1]) verified structurally.
5. **No-arg-`load()` byte-equivalence — VERIFIED.** `load()` delegates to `load(null)`; `testNoArgLoadEquivalentToLoadNull` shows identical IOException shape. Grep of `src/`: the **only** production caller is `SuiteApiStitchClient.build()` using `load(safeGetAdapterConfig(adapter))`. No stale no-arg caller remains that *should* now pass config. Correct.
6. **Null-lifecycle safety — VERIFIED.** `safeGetAdapterConfig` returns `null` on null adapter or any thrown Throwable; `tryInjectedCredential(null)` returns null; chain falls through to file candidates, then to a plain IOException — never an NPE. Early-lifecycle (config not yet injected) degrades to file-based candidates gracefully.
7. **Secrets hygiene — VERIFIED.** Walked every new/changed log statement (`SuiteApiStitchClient` 308–310, 334–337, 349–353, 577–581, 685–689; `AmbientCredential` none). All emit `mechanism` / `file=<sourceLabel>` / `principal=<username>` / `endpoint` only. Password appears solely inside the JSON request body (line 567) which is never logged. No exception message embeds the password.
8. **Catch scope — TIGHT.** `tryInjectedCredential`'s `try` wraps only the three accessor calls; the `username`/`password` blank/null checks (347–352) are **outside** the try, so no logic bug is swallowed. `safeGetAdapterConfig`'s try wraps only `adapter.getAdapterConfig()`.
9. **`SuiteApiStitcher.java` — javadoc-only confirmed** (no non-comment `+`/`-` lines).

## WARNING

- **[AmbientCredential.java:339 / SuiteApiStitchClient.java:381]** `lessons` silent-downgrade posture — the `catch (Throwable)` in `tryInjectedCredential` (and in `safeGetAdapterConfig`) swallows the caught Throwable with **no diagnostic log**. The *outcome* is observable (`SuiteApiStitchClient` logs `file=instance|automation|maintenance`, so an operator sees instance did **not** win), but the *cause* is invisible: on a collector where the injected credential *should* win but `com.vmware.vcops.security.Crypt` is missing, the operator sees `file=automation` with zero signal that instance was attempted-and-failed with a `NoClassDefFoundError` — the exact failure mode this change was built around. → Have the `Builder` log once at DEBUG when `safeGetAdapterConfig` returned non-null (config present) yet the resolved `sourceLabel != "instance"`, recording the swallowed Throwable's class. Keep the common injected-absent case silent to avoid noise. (`AmbientCredential` has no Logger, so the breadcrumb belongs in the Builder, which does.)
- **[stale-artifact discipline — analog of CLAUDE.md "After tooling changes"]** This change rebuilds `adapter_runtime/vcfcf-adapter-base.jar`, which every Tier 2 SDK pak compiles/embeds. `validate` recompiles the 6 adapters green, but any **already-built** `.pak` binaries are now stale (old ambient order baked in). → Before any `v*` release of a Tier 2 pak that stitches via `SuiteApiStitchClient`, rebuild it against this framework jar. Flag to orchestrator; not a code defect.

## NIT

- **[AmbientCredential.java:339 / SuiteApiStitchClient.java:381]** `catch (Throwable)` also swallows `VirtualMachineError` (OOM) and `ThreadDeath`. `catch (Exception | LinkageError)` would honor the exact `NoClassDefFoundError` guarantee from §7 while letting genuinely-fatal JVM errors propagate. Defensible as-is given the crash-the-cycle absolutism, but the narrower catch is cleaner JVM hygiene.
- **[AmbientCredentialTest.java:328–334]** Javadoc on `testOverrideTakesPriorityOverInjected` describes an "all-absent case … IOException listing every candidate" — copy-paste drift; the method actually asserts override-beats-injected. Misleading, harmless.
- **[observational]** Brief claimed "2 documented SKIPs"; this sandbox emitted 3 SKIP lines (encrypted-round-trip, injected-preferred assertions, `load(cfg)` end-to-end) because `com.vmware.vcops.security.Crypt` is absent locally. Environment-dependent, not a defect — and the SKIP branch is exactly what proves the crash-the-cycle catch works.

## If shipped as-is

An operator on a primary node gets the vendor-preferred per-instance credential automatically (correct identity, sidesteps the CP-403 maintenance-first root cause). On a node where the injected credential throws a `NoClassDefFoundError`, stitching still works (falls to `automationAdmin`) but the operator has no log breadcrumb explaining why `file=instance` was not selected — harder field-debugging, no functional regression. No key/label collision, no wire-format drift, no global-default leak.

**Report:** knowledge/context/reviews/framework/ambient-credential-v3-instance-first.md
