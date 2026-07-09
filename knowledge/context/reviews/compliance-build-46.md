# SDK Adapter Review — compliance build 46

- **Adapter:** `content/sdk-adapters/compliance` (repo commit `7d93781`)
- **Build reviewed:** 46 (SSL-fix rebuild + self-contained onTest + shadow-logger setLevel)
- **Baseline:** build 45 (`0542c24`, APPROVEd in `compliance-build-45.md`)
- **Reviewer:** `sdk-adapter-reviewer`
- **Date:** 2026-06-10
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT

**Scoped delta review.** Builds 44/45 reviewed clean (`compliance-build-4{4,5}.md`).
Build 46 adds exactly three forensics fixes: (a) rebuild against the
b12ce5c framework jar (Suite API stitch SSL fix — `insecureSslContext`),
(b) a self-contained `onTest` tester that derives host/credentials from
the `TestParam` `ResourceConfig` instead of dereferencing null instance
state, (c) the shadow `adapterLogger()` now raises the injected logger to
`CustomLevel.INFO`. No collection/scoring path touched. The
unreadable-is-NOT-compliant `ControlEvaluator` contract (skill §
*Unreadable is NOT compliant*) is byte-unchanged — pak-compare 0/0/0.

## Claims check (re-run independently)

| Claim | Result |
|---|---|
| 45→46 diff is exactly the three claimed changes + version/docs, no scoring/collection drift | **CONFIRMED** — `git diff 0542c24 7d93781 --numstat`: 4 files — `CHANGELOG.md` (+4), `REFERENCE.md` (build-string bump), `adapter.yaml` (build_number 45→46), `ComplianceAdapter.java` (83/12). Java delta is confined to `adapterLogger()` (+1 `setLevel` line) and `getTester()` + new private `testResourceConfig()`. `VSphereClient`/`EsxcliSoapClient`/`ComplianceStitcher`/`ControlEvaluator` are NOT in the changed-files list. |
| `validate-sdk` clean | **CONFIRMED** — re-ran: compiles 10 sources, only the benign `-source 11` system-modules warning. "OK: … is a valid Tier 2 SDK adapter project." |
| `pak-compare` 46 vs 45 = 0/0/0 | **CONFIRMED** — built both paks (45 from a throwaway worktree at `0542c24`), re-ran `pak-compare`: "No structural divergences found. 0 BLOCKING, 0 WARNING, 0 INFO." |
| Embedded framework jar is the b12ce5c SSL-fix rebuild; sha differs from build 45's embedded jar | **CONFIRMED** — pak-46 embedded `vcfcf_compliance/lib/vcfcf-adapter-base.jar` sha256 `9a1e5974…` is **byte-identical** to the reference `vcfops_managementpacks/adapter_runtime/vcfcf-adapter-base.jar` and **differs** from build 45's embedded jar (`65ca9523…` per `compliance-build-45.md`). Disassembling `SuiteApiStitchClient$Builder` shows the string `insecureSslContext` and **no** `getPlatformSslContext` — the b12ce5c fix is in the shipped bytecode. lib/ is the C2 single-jar shape. |

All author claims verified with my own eyes. `dist/` was empty at review
start, so I ran `build-sdk` for both 45 and 46; `git checkout -- CHANGELOG.md
REFERENCE.md` restored the docs and the throwaway worktree was removed.
Compliance and factory trees both left clean (`git status --short` empty;
`dist/` is gitignored).

## Review-dimension notes (delta only)

**Dim 2 (tester credential handling — the scoped concern).** Verified the
new test path cannot leak the password and cannot NPE:

- *No password in any thrown message or log.* The tester's own
  `throw new Exception(...)` carries only the ResourceConfig-absent
  message — no credential. `VCenterApiClient.login()` throws
  `"vCenter login failed: HTTP <status>"` (status code only); the password
  is base64'd into the `Authorization: Basic` header and never reaches a
  thrown message or a log line. `logInfo` logs only `vcenterHost` + a host
  count. RULE-008 / `knowledge/rules/no-secrets-on-disk.md` holds.
- *`logout` in `finally` is NPE-safe on all paths.* The lambda builds a
  fresh `VCenterApiClient`, calls `login()`, then `try { listHosts; logInfo }
  finally { testApi.logout() }`. `logout()` is `sessionId == null`-guarded,
  so if `login()` throws before setting the session the `finally` is a safe
  no-op. If `login()` itself throws, control never enters the try, logout is
  skipped, and there is nothing to clean up — correct. Bytecode confirms
  two `logout()` call sites (success + finally), zero `getfield vcApi`.
- *Malformed/null config yields an actionable error, not an NPE.*
  `testResourceConfig(param)` null-guards `param`, `getAdapterConfig()`, and
  returns `getAdapterInstResource()`; a null result throws the descriptive
  "no adapter-instance ResourceConfig available" message. `ComplianceConfig`
  coalesces null host→`localhost`, null user/pass→`""` (pre-existing
  contract), so a missing field degrades to a clean login failure, not a
  raw NPE. The tester mirrors `configureAdapter` (lines 99–112) idiom-for-
  idiom; no instance state touched (skill § *self-contained onTest*).

**Dim 6 (logger fix — downgrade question + handle reach).** The shadow
`adapterLogger()` now does `getLogger().setLevel(CustomLevel.INFO)` —
verified in the **shipped** bytecode (`getstatic Logger$CustomLevel.INFO;
invokevirtual setLevel`). This is **byte-identical in intent** to the
framework base's own private `adapterLogger()`, which I disassembled from
the jar: it caches a `volatile` handle and does the same
`getLogger().setLevel(CustomLevel.INFO)`. So the fix makes the *injected*
helper logger match the level posture of the base's *own* logger — it does
not introduce a novel level policy.

- *Downgrade risk is benign and behavior-matched.* An unconditional
  `setLevel(INFO)` would raise the floor to INFO and suppress a more-verbose
  platform DEBUG. But the base does the identical thing to its own handle,
  so the adapter's own DEBUG breadcrumbs already live under that constraint
  — this is not a regression. The one DEBUG breadcrumb in the helper
  (`VSphereClient:998`, the first-object MoRef) is correctly
  `log.isDebugEnabled()`-guarded, so when INFO is the floor it simply does
  not fire — no error, no spam. Acceptable.
- *Handle reach.* The same `adapterLogger()` return is passed to
  `VSphereClient` (`:116`), `SuiteApiStitcher.create` (`:127`), and
  `ComplianceStitcher` (`:129`) — all of which take a `Logger`. See NIT-1
  re: the CHANGELOG's `EsxcliSoapClient` claim.

**Dim 1/3 (unreadable is NOT compliant / no swallowed pass).** This delta
is install/test-path + logger plumbing, not the collect read path. The
scoring contract is untouched (pak-compare 0/0/0; `ControlEvaluator` not in
the diff). No path where a failed/missing read becomes a `pass` was
introduced; the new test-path failures all *throw* (surface), never fold to
a silent OK.

**Dim 5 (MOID stitching), Dim 7 (resource hygiene), Dim 9 (build hygiene).**
Stitching identity unchanged (no stitcher source touched; the SSL fix is a
rebuild-only adoption inside the framework jar). `build_number` bumped 45→46;
matching `CHANGELOG.md` entry present and accurate; minimal diff, no drive-by
refactor. The tester's fresh `VCenterApiClient` is short-lived and explicitly
`logout()`'d in `finally` — no per-test session leak.

## Findings

### NIT

- **NIT-1 [CHANGELOG.md 1.0.0.46 / ComplianceAdapter.java:148–160 doc
  comment]** Both the changelog and the `adapterLogger()` Javadoc attribute
  the dead breadcrumbs to "`VSphereClient`/`EsxcliSoapClient` `log.info(...)`"
  and cite `listView(...): RetrieveProperties -> N objectContent` as an
  `EsxcliSoapClient` line. `EsxcliSoapClient`'s constructor takes **no
  Logger** (`(sdkUrl, sessionCookie, sslFactory)`) and emits no `log.info`
  at all — the `listView/objectContent` breadcrumbs live in `VSphereClient`
  (which does take and use the injected logger). The code fix is correct and
  reaches every helper that actually takes a logger; only the attribution in
  the prose/comment is wrong. Tidy in a future touch. Documentation
  inaccuracy, not a behavior defect — does not gate.

## If shipped as-is

An operator who installs build 46 gets the build-45 collection adapter
(byte-unchanged scoring, MOID stitching, inventory walk — pak-compare 0/0/0)
with three fixes: (1) the Suite API stitch localhost hop now uses the
framework's `insecureSslContext` instead of the failing platform SSL context,
so ambient stitching onto VMWARE resources succeeds on devel; (2) the
Test-connection button works on a fresh instance instead of NPE'ing on a null
`vcApi` — it builds a throwaway client from the instance config, reports the
visible host count, and logs out, with no password in any log or error
message; (3) the SOAP-walk INFO breadcrumbs (`vSphere SOAP: N hosts`,
`listView … -> N objectContent`) now actually appear in the collector log, so
an operator can confirm each inventory kind was enumerated. No path where an
unreadable result scores as compliant was introduced. The remaining
acceptance bar is the live devel install + Test-connection + golden-collection
proof (`qa-tester` / orchestrator devel proof) — nothing in this static
review blocks promotion to that step.

## Report
`knowledge/context/reviews/compliance-build-46.md`
