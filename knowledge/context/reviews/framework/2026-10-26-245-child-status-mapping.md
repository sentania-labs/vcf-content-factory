# Framework review: #245 child status mapping (buildkit 1.0.19)

- Branch: `fix/245-child-status-dropped`, commit `7949875`, diffed against `main` (`bc783ea`)
- Area: `src/vcfcf_managementpacks/adapter_framework` (`VcfCfAdapter`, `spi/VcfCfCollector`, `AdapterInstanceStatusTest`), `buildkit.py`
- Reviewer: `framework-reviewer`, 2026-10-26
- Verdict: **APPROVE** (0 BLOCKING / 0 WARNING / 5 NIT). Per delegation rule 9, fix the NITs before the PR opens.

## What changed

`setStatusSafe` now picks the SDK list by resource. A child goes through
`childStatusFor`, where anything off `isResourceAllowedStatus` becomes
NO_DATA_RECEIVING. The adapter instance goes through `instanceStatusFor`,
where anything off `isAdapterAllowedStatus` becomes ERROR. The move is logged,
and a `false` from `setResourceStatus` is logged at WARN, both for objects
and in `reportAdapterInstanceFailure`. The interrupt path sets
NO_DATA_RECEIVING. `recordFailure` still gets the unmapped status. The test
adapter calls the SDK's private `isValidStatusForResource` by reflection.
Buildkit 1.0.19, release notes, `tier2_architecture.md` and the spec 19
correction come with it.

## Checks re-run

| Check | Result |
|---|---|
| javap on the three SDK jars (sha256 match PROVENANCE.md: 2d53a91f... 2.2, 45d54c64... 8.18.7, 79f7b123... 9.1.1.0100) | Claim confirmed, see below |
| Validate chain (7 packages) | all rc=0 |
| pytest | 2622 passed, 9 skipped, 6 failed. All 6 are the known `content/sdk-adapters/` gitignored-source failures (verified from the failure text) |
| Compat pass `build-framework.sh --compat-only`, 8.18.7 (`--release 11`) + 9.0 (`--release 17`), JDK 17 | pass |
| 9.1.1.0100 leg, `eclipse-temurin:25-jdk` (javac 25.0.4.1), `--release 25`, main + tests | compiles |
| `AdapterInstanceStatusTest` per leg (log4j from `adapter_runtime/lib`) | 160/160 on 8.18.7, 9.0 and 9.1.1.0100 (main: 79/79) |
| Rest of the Java suite per leg | Same results as main on each leg. The failures are environmental and also fail on main: `VcfCfAdapterTest` "load from a jar with a manifest" (classes dir, not a jar), `ManagedHttpClientCopyTest` (restricted header on the local JDK), `ComponentLoggerTest` on 8.18.7 (log4j class mismatch with the 8.18 logger). |
| Deprecation warning on `VcfCfAdapter` | Pre-existing, same single `setResourceStatus(rc, status, String)` warning on main |
| Render regression / pak-compare | n/a (no renderer, builder or template change) |

### Bytecode (verified, not taken from the result block)

- `ResourceStatusEnum.isAdapterAllowedStatus` is NONE, ERROR, DOWN,
  DATA_RECEIVING, NO_DATA_RECEIVING, COLLECTOR_DOWN on all three jars.
- `ResourceStatusEnum.isResourceAllowedStatus` is NONE, DATA_RECEIVING,
  NO_DATA_RECEIVING on all three jars.
- `AdapterBase.isValidStatusForResource(rc, st)` is private. It calls
  `isAdapterInstResourceConfig(rc)` and applies the instance list when that
  is true, the child list otherwise. `isAdapterInstResourceConfig` returns
  false for a null rc or a null id; otherwise it returns
  `rc.getResourceId().equals(getAdapterInstResourceId())`, which reads
  `getAdapterInstResource()`.
- `setResourceStatus(rc, msg, st)` logs WARN `Setting status '..' to resource
  '..' is not allowed.` and returns false on refusal. It also returns false
  with a null `collectResult`. On success it logs INFO `Resource '%s' changes
  status`, every call.
- `setResourceDown(rc, ...)` and `setResourceError(rc, ...)` return false on
  a child (WARN `Setting down|error status to regular resource ...`). On the
  instance they become `setAdapterDown` / `setAdapterError`, which set every
  monitored resource to NO_DATA_RECEIVING.
- Normalized bytecode of `isAdapterInstResourceConfig`, all
  `setResourceStatus` overloads, `setAdapterError/Down`, `setResourceDown`
  (6 overloads) and `setResourceError` (2) is identical across the three
  jars. The spec 19 correction text and the log strings it quotes are
  accurate.

### #223 interaction (verified by code, mutation and a scratch test)

- `recordFailure(effective, e)` still gets the unmapped ERROR/DOWN. A
  mutation to `recordFailure(childStatusFor(effective), e)` fails 7 checks,
  including "instance still ERROR (#223)" and the DOWN cases. The rule is
  pinned.
- All children failing gives an instance in ERROR, or DOWN when every failure
  was DOWN. A scratch run with 3 children mapped to DOWN gave instance DOWN.
- With a partial failure the instance is untouched (`assertFalse
  statuses.containsKey(instance)`).
- Recovery: in a scratch two-cycle run (child fails, then succeeds) the child
  went NO_DATA_RECEIVING, then DATA_RECEIVING, with nothing refused.
  `childStatusFor` is stateless, so there is no sticky NO_DATA_RECEIVING.
  This is not pinned by a committed test (N5).
- Interrupt path: putting ERROR back still passes 160/160, because
  `setStatusSafe` would map it anyway. The explicit NO_DATA_RECEIVING exists
  so that a cut cycle does not log the "(the adapter instance turns ERROR
  ...)" line, since a cut cycle sets nothing. That is correct.

### Test strength (mutation)

| Mutation | Result |
|---|---|
| `childStatusFor` restored to the old adapter-list gate | 38/160 fail |
| `!accepted` WARN suppressed | 2 fail |
| move log suppressed | 7 fail |
| `recordFailure` fed the mapped status | 7 fail |

### Reflection in the test

`sdkTakes` uses `getDeclaredMethod("isValidStatusForResource",
ResourceConfig, ResourceStatusEnum)`. That name and signature are identical
on all three jars. If the method is missing, the test throws
`IllegalStateException`. It does not skip.

- `testGateIsTheSdks` calls `setResourceStatus` directly, so the exception
  propagates and `main` dies. That is loud.
- In the onCollect-driven cases `setStatusSafe`'s `RuntimeException` catch
  swallows it, but the `statusOf` assertions then fail.

So the test is never a silent no-op. The static premise check
(`testChildStatusRuleCoversEveryStatus`: ERROR and DOWN are not on the child
list) does not depend on reflection or log4j. The rest of the #245 block
sits behind the existing log4j SKIP gate, which prints a visible skip line,
as since #223.

### Log volume

On a failing child, per cycle:

- the pre-existing framework WARN with the full stack trace (`VcfCfAdapter.java:996`)
- the SDK's own INFO "changes status"
- the new framework INFO move line

The new line is about one short line added to a block that is already a
stack trace. The "thousands of VMs on compliance" case does not reach this
loop. Compliance's `collect` is `collectWorld(rc)` over its own world
object(s); VMs are stitched over the Suite API and never get a framework
`setResourceStatus`. The paks whose loop has many children (unifi clients,
synology disks) have tens to hundreds of objects. It is not a flood, but it
repeats unchanged information every cycle (N1).

### Buildkit bump

The bump follows #257 and #258: a one-line `BUILDKIT_VERSION` change, a
release-notes section and a `tier2_architecture.md` change-log row. The
notes read correctly and say what they should: the behaviour, three-line
parity, the #223 interaction, the WARN on `false`, no source change and a
rebuild needed. They are placed out of order (N2). No `src/vcfcf_packaging`
templates, builder, assembly or render file is touched, so there is no
stale-zip or `CURRENT_TEMPLATE_VERSION` obligation. Tier 2 paks need a
rebuild on 1.0.19, and the notes say so.

### Pak sources (read-only grep, `content/sdk-adapters/*`)

There are no direct `setResourceDown`, `setResourceError`,
`setResourceStatus`, `setAdapterDown/Error` or `ResourceStatus.setStatus`
calls in any Java pak (compliance, synology, template, unifi, vcommunity,
vcommunity-os, vcommunity-vsphere). All seven go through
`mapCollectException` returning DOWN/ERROR, which the framework now maps.
Nothing depends on the old behaviour, and no pak needs a follow-up for a
bypass. cluster-perf-risk and vsanhostmetrics are Python Integration SDK
packs, outside this framework.

## Findings

### BLOCKING
None.

### WARNING
None.

### NIT

**N1. Repeated per-object log lines** (`VcfCfAdapter.java:3222-3238`;
authority: `tier2_architecture.md` 2026-10-23 row, the #192 convention:
"trace at WARN only the first time per client and operation").

- The expected ERROR/DOWN to NO_DATA_RECEIVING move is logged at INFO per
  object per cycle. It restates documented, constant behaviour next to a
  WARN that already names the object.
- A pak that maps to an off-list status (UNKNOWN, COLLECTOR_DOWN, ...) gets
  a WARN per object per cycle forever, for a static pak defect.

Fix:
- Log the ERROR/DOWN move as one per-cycle summary (count and first object).
- Log the unexpected-status WARN once per status per adapter instance.
- Keep the `!accepted` WARN per call. It should not fire in normal operation.

**N2. Release notes out of order** (`.github/release-notes-buildkit.md:94`).
`## Behavior since 1.0.19` sits between 1.0.17 and 1.0.18, so the order
reads 16, 17, 19, 18. The #258 fixup restored that order on purpose
(HANDOFF-2026-10-26: "release-notes order"). Fix: move the section below
`## Behavior since 1.0.18`. Optionally add the "Version note" line that
1.0.15 and 1.0.18 carry.

**N3. Inexact INFO wording for DOWN** (`VcfCfAdapter.java:3233`). The line
says "the adapter instance turns DOWN when every object in the cycle fails".
The instance turns DOWN only when every failure is DOWN; a mix gives ERROR
(`adapterInstanceStatus`). Fix: "turns ERROR or DOWN when every object in
the cycle fails". This goes away if N1 removes the per-object line.

**N4. Instance check diverges from the SDK in one edge case**
(`VcfCfAdapter.java:3205`). `isAdapterInstance` returns true on object
identity even when the id is null. The SDK's `isAdapterInstResourceConfig`
returns false for a null id and so applies the child list. In that case the
framework would send ERROR, and the SDK would refuse it. That is now logged,
so it is not silent, but it is still a mismatch. Fix: match the SDK. Compare
ids only, against `getAdapterInstResourceId()` or the passed instance's id,
and drop the identity shortcut. The test "same object is the instance" still
holds by id.

**N5. Recovery is not pinned by a test** (`AdapterInstanceStatusTest`;
dimension 10). Nothing asserts that a child that failed in cycle 1 shows
DATA_RECEIVING in cycle 2. A scratch version of exactly this test passed (see
above). Fix: commit it, about 10 lines in the #245 block, so a future
"remember last failure" change cannot make NO_DATA_RECEIVING sticky.

## Follow-ups (code or docs this branch does not touch; not verdict-bearing)

1. **CI never runs the Java framework tests.** `ci.yml` `sdk-compat` compiles
   main sources only. `tests/` drives only `ManagedHttpClientCopyTest`.
   `AdapterInstanceStatusTest`'s "checks against whichever SDK jar is on the
   classpath" holds only when someone runs it by hand on each leg, as this
   review did. Suggest a per-leg test step with log4j on the classpath.
2. **Per-child WARN with a full stack trace on every failed collect**
   (`VcfCfAdapter.java:996`, pre-existing). This is the dominant noise in an
   all-fail cycle. Same remedy as the #192 convention: trace once per
   exception class, one line after that.
3. **`cleanroom-spec/spec/01-adapter-lifecycle.md:116-124`** lists
   `setResourceDown` / `setResourceError` with no "adapter instance only"
   note. Spec 19's intro sentence and table rows (DOWN, ERROR: "When to set")
   are still unannotated inline. The correction paragraph below the table
   covers spec 19, but a row-level "(adapter instance only)" would stop the
   table being read on its own.
4. **Live proof is still owed** (CLAUDE.md "done means seen working",
   RULE-019 release section). Two things are unproven on a live instance:
   what a child in NO_DATA_RECEIVING looks like in the UI, and the docs'
   claim that the old refusal left "the object kept its last status".
   Capture both in the next pak's three-line install record.

## Claims checked against the result block

- "Identical on 8.18.7, 9.0/2.2, 9.1.1.0100": confirmed by javap and a
  normalized diff.
- "New cases fail 32 ways on the 1.0.18 code": not reproduced exactly. The
  1.0.18 code has no `childStatusFor`, so the new test does not compile
  against it. Restoring the old gate inside the branch gives 38 failures.
  The figures are consistent in kind.
- "Pass on all three jars": confirmed, 160/160 on each leg, including the
  9.1.1.0100 leg on JDK 25 in the container.

## If shipped as-is

Operators on 1.0.19-rebuilt paks see a failed object go to NO_DATA_RECEIVING
instead of silently keeping its old status, on all three lines. The account
row still goes red only when everything fails. The only cost is one extra
INFO line per failed object per cycle, and a release-notes section out of
order.
