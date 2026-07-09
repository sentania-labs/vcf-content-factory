# Framework Review — onDescribe() localization fix (make(String) overload swap)

- **Area:** `vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/VcfCfAdapter.java` (`onDescribe()`)
- **Change:** swap `AdapterDescribe.make(InputStream)` → `AdapterDescribe.make(String)` so the SDK auto-loads `<conf>/resources/resources.properties`; remove now-dead `InputStream`/`Files` imports; update Javadoc + `context/framework_v2_migration.md` §3.
- **Reviewer:** framework-reviewer (pre-PR, read-only)
- **Date:** 2026-06-24
- **Verdict:** APPROVE (0 BLOCKING)

## Independent verification of the SDK API claim (bytecode, not the report)

Disassembled `com/integrien/alive/common/adapter3/describe/AdapterDescribe.class`
from `vcfops_managementpacks/adapter_runtime/vrops-adapters-sdk-2.2.jar` (the
sole framework compile classpath) with `javap -p -c`. The author's claim is
**bytecode-accurate**:

- **`make(String)`** — at offsets 78–90: `new File(path)` → `File.getParent()`
  → concat with static `RESOURCES_PATH_SUFFIX` → calls the **two-arg**
  `loadDescribe(Node, String)`. That two-arg path instantiates
  `MultiLanguageDescriptionsDescribeLoader` (offset 0–4 of `loadDescribe(Node,String)`).
  So `make(String)` does load `<parent>/resources`. Confirmed.
- **`make(InputStream)`** — at offset 37: calls the **single-arg**
  `loadDescribe(Node)` — no resources path. So the stream overload skips the
  localization bundle entirely. This is exactly the named v1→v2 regression
  (raw `nameKey`s, "localized name not found for adapter kind … nameKey=1").
  Confirmed.
- **`make(String)` failure posture** — offsets 21–38 (FileReader open failure)
  log the error and `aconst_null; areturn`; the no-`AdapterKind`-root and
  fall-through paths also return `aconst_null` (offsets 147, 217). It **returns
  null, never throws** on a missing/unreadable/invalid file. The framework's
  `if (describe == null) throw new RuntimeException(...)` is therefore the
  correct and necessary null→exception conversion. Confirmed.

## Regression hunts

### 1. Bare-instantiation / build-45 NPE safety — PRESERVED
`git show HEAD:…VcfCfAdapter.java` confirms the entire kind-resolution block
(constructor-stored `adapterKindKey` first → `getAdapterKind()` fallback →
actionable throw if both null) is **byte-for-byte unchanged**. The change is
strictly below `getAdapterDescribeFile(kind, …)`. The kind is still resolved
before any `make()` call, so the controller-side bare-`describe()` NPE chain
(`lessons/controller-describe-bare-instantiation.md`) is not reintroduced.

### 2. Absent resources.properties — TOLERATED (bytecode-verified)
Traced `MLDDL.load(String)` → `LocalizedNamesDataProvider.getLocalizedNameFiles(String)`:
- `!dir.exists()` → logs, returns `null` (offset 46–47)
- `!dir.isDirectory()` → logs, returns `null` (offset 69–70)
- `load(String)` checks that null and returns `null` (offset 6–10)

The only `athrow` in `getLocalizedNameFiles` is an `AssertionError` guarded by
`$assertionsDisabled` (assertions are off in the collector/controller JVM by
default) — not reachable in production. A pak with `describe.xml` but **no**
`conf/resources/resources.properties` therefore yields `null` localized names
and a **valid, non-null** `AdapterDescribe`; describe.xml parsing continues
normally. No throw, no describe-phase crash. The author's "absent resources is
safe" claim is confirmed at the bytecode level.

### 3. Path correctness — CORRECT
`getAdapterDescribeFile(kind, "describe.xml")` returns the same `Path` as the
old code; `.toString()` yields the absolute describe.xml path. `make(String)`
computes `new File(path).getParent() + RESOURCES_PATH_SUFFIX` =
`<adaptersHome>/<kind>/conf/resources`, the correct sibling of
`<adaptersHome>/<kind>/conf/describe.xml`. No wrong-parent re-break.

### 4. Error/behavior parity on missing/unreadable describe.xml — PRESERVED
Old path: any `Files.newInputStream`/`make(is)` exception → framework
`RuntimeException` with `e.getMessage()` as cause. New path: `make(String)`
returns null on the same failures → framework `RuntimeException` with an
actionable message. Loud failure + actionable message preserved. The only
delta is the wrapped Java cause is dropped from the framework exception — but
`make(String)` logs that cause internally (offsets 22–37). Acceptable.

## Checks re-run (independently)

- **Compile:** `./adapter_framework/build-framework.sh` → `Built …
  vcfcf-adapter-base.jar (60K)`, SDK-only classpath, **only** the pre-existing
  `-source 11` system-modules warning. Clean.
- **validate chain:** all seven `python3 -m vcfops_* validate` green, including
  `vcfops_managementpacks` → **all 6 Tier 2 SDK adapters compile against the
  rebuilt base jar** (compliance, synology, unifi, vcommunity, vcommunity-os,
  vcommunity-vsphere). No adapter broken by the base-jar change.
- **Render-regression / pak-compare:** n/a — no `render.py`/builder/template
  change.

## Findings

### BLOCKING
- none

### WARNING
- none

### NIT
- `[context/framework_v2_migration.md:132]` and `[VcfCfAdapter.java:536–537]` —
  build-number prose is self-contradictory: line 132 says the localization
  regression is "fixed in build 43 framework fix" while the Javadoc says the
  regression "was the v1→v2 regression (build 43)" — attributing both the
  introduction and the fix to build 43. Cosmetic; pick one build number for
  the fix vs. the regression. → clarify prose.
- `[VcfCfAdapter.java:540–542]` / `[migration.md:135–139]` — doc says the SDK
  "logs a **warning** and continues" on absent resources; the bytecode logs at
  **ERROR** level (`getLocalizedNameFiles`). Behaviorally still safe (no throw),
  but the log-level claim is wrong. → say "logs an error and continues" or
  drop the level.

## Stale-zip / rebuild discipline

The change does **not** touch `vcfops_packaging/templates/`,
`vcfops_packaging/builder.py`, or `vcfops_dashboards/render.py`, so the CLAUDE.md
content-zip staleness rule is not triggered. **However**, it rebuilds
`adapter_runtime/vcfcf-adapter-base.jar`, which **every Tier 2 SDK pak bundles**.
Any already-built SDK `.pak` is now stale w.r.t. the localization fix — the fix
only reaches an installed adapter once that adapter's pak is rebuilt against the
new base jar. **All SDK paks must be rebuilt** (each via its own `build-sdk` /
`v*` CI) for the localized-names fix to take effect on a live instance. This is
the orchestrator's action, not a code finding.

## If shipped as-is

A correct, low-risk fix: adapter kinds / resource kinds / identifiers register
**with** their localized display names in the Accounts UI instead of raw integer
`nameKey`s. Absent-resources paks and the controller-side bare-describe path are
both safe. The only operator-visible caveat: the fix is inert until each SDK pak
is rebuilt and reinstalled against the new `vcfcf-adapter-base.jar`.

## Explicit ship statement

This diff is **safe to ship to the PR** and **safe to rebuild all SDK paks
against**. The SDK API behavior is bytecode-confirmed on every path that
matters (localization load, absent-resources tolerance, null-return failure,
bare-instantiation kind resolution). The two NITs are documentation prose only.
