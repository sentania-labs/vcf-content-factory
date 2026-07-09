# SDK Adapter Review — compliance build 43

- **Adapter:** `content/sdk-adapters/compliance` (repo commit `dbb6df4`)
- **Build reviewed:** 43 (framework v2 migration — SPI port + raw SOAP + ambient stitcher)
- **Reviewer:** `sdk-adapter-reviewer`
- **Date:** 2026-06-09
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 2 WARNING / 3 NIT

This is the largest single-build change in the adapter's history: three concurrent
rewrites (vim25/JAX-WS → raw SOAP; v1 UnlicensedAdapter → v2 SPI; aria-ops-core
stitcher → framework SuiteApiStitcher). I read each changed read path in full and
re-ran every build claim. None of the three known failure modes
(unreadable-is-compliant, stitch corruption, crash-the-cycle) is present.

## Claims check (re-run independently, not taken from the author's block)

| Claim | Result |
|---|---|
| `validate-sdk` clean (compliance) | **CONFIRMED** — compiles; one deprecation note only (the `Crypt` call in `AmbientCredential`, expected and `@SuppressWarnings`-annotated). |
| `build-sdk` → `dist/vcfcf_sdk_compliance.1.0.0.43.pak` | **CONFIRMED** — reproduces; pak is 310 KB (was 13.2 MB at build 42 — consistent with dropping vim25 + jaxws + vim-vmodl jars). |
| `lib/` = `vcfcf-adapter-base.jar` only (C2 v2 shape) | **CONFIRMED** — builder reports `lib/ deps: 1 JAR(s): ['vcfcf-adapter-base.jar']`; aria-ops-core correctly auto-omitted (no `com.vmware.tvs.*` in compiled bytecode). |
| `pak-compare` vs build 42 = 0 BLOCKING / 0 WARNING / 6 INFO | **CONFIRMED** — ran `pak-compare dist/...43.pak tmp/...42.pak`: `0 BLOCKING, 0 WARNING, 6 INFO`. The 6 INFOs are exactly the intended jar removals (aria-ops-core, javax.xml.soap-api, jaxws-api, jaxws-rt, vim-vmodl-bindings, vim25). |

All four author claims verified with my own eyes.

## Scope of the delta (confirmed via git diff 1f82d1f..dbb6df4)

Changed: `ComplianceAdapter.java`, `ComplianceStitcher.java`, `VSphereClient.java`
(full rewrites); `SuiteApiPropertyPusher.java` **deleted** (dead code; grep confirms
zero remaining references). `adapter.yaml` build_number 41→43; CHANGELOG entry added.
**Unchanged** (minimal-diff respected — no drive-by refactor of proven readers):
`EsxcliSoapClient`, `BenchmarkLoader`, `ControlEvaluator`, `BenchmarkProfile`,
`VamiApiClient`, `VCenterApiClient`, `ComplianceConfig`, `describe.xml`,
`CANONICAL_SCHEMA.md`, `profiles/`. The metric-tree contract the golden gate depends
on is untouched.

## Dimension-by-dimension

### 1. Cardinal correctness — "unreadable is NOT compliant" (skill §; RULE-002) — PASS

The zero-divisor and unreadable contracts hold end-to-end:

- `ControlEvaluator.evaluateVimProperties` excludes the `UNREADABLE` sentinel from
  pass/fail/total, never scores it compliant, and surfaces it via `unreadableCount`
  (ControlEvaluator.java:324-334). `total==0 → score=100.0` with `totalCount=0`
  (line 358-359), so callers can refuse to fold a sentinel.
- `VSphereClient.readVimProperties` folds any null/failed/unknown-style read to
  `UNREADABLE` (VSphereClient.java:411), and every recipe style returns null (→
  UNREADABLE) rather than guessing on a missing/failed read — verified for
  `service_state` (missing service → null, line 549-550), `bool_policy` (absent
  value → null, not false, line 590-593), the list styles (failed container fetch →
  `ListRead.failed()` → null, never "absent/empty therefore compliant",
  lines 640-691), and `vlan_id_not` (unrecognized spec → null, line 722).
- The world rollup refuses to publish a fleet average when no resource produced real
  signal: `if (hostStats.scored > 0)` gates `avg_host_score` /
  `hosts_below_threshold`, else logs a WARN and emits nothing
  (ComplianceAdapter.java:278-288) — same guard for VM/vCenter. A total-unreachable
  vCenter throws out of `collect()` → world marked DOWN/ERROR, no metrics emitted
  (mapCollectException, line 225-231). No sentinel-100 false pass at any tier.
- The evaluable set was **not** widened without a real reader: `vim_property`/
  `esxcli`/`vami_api` are the only recipe kinds scored, each with a backing reader,
  and a recipe-kind control with no `read_recipe` is skipped, not faked
  (ControlEvaluator.java:302-312).

### 2. Reflection-tolerant reads (now DOM-tolerant) (skill § vim25 over JAX-WS) — PASS

The rewrite drops vim25 binding objects for DOM-by-local-name. No concrete-type
casts anywhere; type discrimination is by `xsi:type` *string substring*
(`xsiType()`, VSphereClient.java:1188-1195) — the analogue of v1's
`getClass().getSimpleName()`, never an `instanceof` against a concrete subclass.
A missing element is null→skip, never a throw: every accessor (`firstDirectChild`,
`childText`, `elementText`, `parseBool`) is null-tolerant. A single resource's
missing field cannot abort the cycle — confirmed below.

### 3. Exception / failure granularity — PASS

Per-resource reads are caught at per-resource scope and continue the loop:
`getAdvancedSettings` / `getVmExtraConfig` / `readVimProperties` failures are caught
per host/VM/DVS/etc. (e.g. ComplianceAdapter.java:477-483, 537-543, 665-672) and
degrade to an empty/profile-name-only push, never aborting the fleet walk.
`getLongestPrefixElement` swallows per-prefix read exceptions to null
(VSphereClient.java:782-786) — correct (a property genuinely absent and a faulted
read both legitimately resolve to "could not read this path"). No empty catch that
turns a real error into a silent pass: the swallowed cases all flow to UNREADABLE
(excluded from score) or to a logged WARN, never to a counted pass. The only truly
silent catches are `disconnect()`'s Logout and `destroyViewQuietly()`'s DestroyView
(VSphereClient.java:156, 969) — best-effort cleanup where swallowing is correct.

### 4. Canonical loader contract — N/A (unchanged) — PASS

`BenchmarkLoader` / `BenchmarkProfile` are byte-identical to build 42 (header-name
parsing already proven in prior builds). Not touched by this migration.

### 5. Stitching identity — the MOID trap (skill § ARIA_OPS stitching identity;
`knowledge/lessons/foreign-resource-property-push.md`) — PASS

`matchResource` resolves MOID-first then exact name then dot-prefix fuzzy, against
**per-resource-kind** tables keyed by `VMEntityObjectID`
(ComplianceStitcher.java:304-330) — the MOID is vCenter-scoped by the VMWARE adapter
instance, and the adapter is single-vCenter, so bare-MOID cross-vCenter collision
(the trap the lesson warns about) does not apply. Critically, the non-vim25
`VMwareAdapter Instance` kind does **not** use bare MOID: it resolves by
`VMEntityVCID` (vCenter Instance UUID, most authoritative) then `VCURL` (FQDN) then
display name then singleton (lines 248-274) — the correct stable-key discipline. The
class doc states these rules are preserved byte-for-byte from v1, and the golden gate
covers it. No stitch onto the wrong host.

### 6. Logging quality / no secrets (RULE-008) — PASS

No credential value is ever logged. `SuiteApiStitchClient` logs only `mechanism` +
`principal` name (SuiteApiStitchClient.java:239-241, 263-265); `AmbientCredential`
logs nothing and reads — never writes — the maintenance file (RULE-008 is about
writing secrets to disk; this only reads an existing platform file). Per-resource
skips/null-reads are at INFO/WARN with resource context; no log spam inside tight
loops beyond one line per resource (matches v1). Ambient-unavailable degrades with a
single actionable WARN (ComplianceAdapter.java:152-155).

### 7. Memory / resource hygiene — PASS (one NIT)

`listView` destroys the ContainerView in a `finally` even on mid-walk failure
(VSphereClient.java:884-892). Each SOAP `post()` drains and closes the stream
(`drain()` finally-closes, line 1075) and `conn.disconnect()`s. `disconnect()` nulls
all session state and the esxcli child. Suite API tokens are released in `finally` on
every push/get (SuiteApiStitchClient.java:315-317, 342-344, 363-365). No per-cycle
unbounded growth: stitcher tables are rebuilt (`put`/`clear`) each load, not
appended. See NIT-1 on the HttpURLConnection trust-all factory.

### 8. Performance / API discipline — PASS (one NIT)

vim properties are read per-recipe via per-property `RetrieveProperties` calls (no
single bulk PropertyCollector spec across controls) — this is unchanged from v1 and
inside the golden envelope, but it is an N-round-trip pattern per resource. The Suite
API stitcher acquires+releases a token per push call (per host/VM) — also the v1
"proven-safe" pattern per the ambient-auth investigation. Both are acceptable for
this build; noted as NIT-2/NIT-3 for a future bulk-read pass, not a regression.

### 9. Build hygiene & minimal diff (author rules 8–9; RULE-005) — PASS

build_number 41→43, accurate CHANGELOG line, no drive-by refactors (proven readers
untouched), dead `SuiteApiPropertyPusher` removed cleanly. validate-before-install
satisfied (validate-sdk green, pak-compare green).

### 10. Gap honesty (skill § Gaps; RULE-002) — PASS

Gaps are named, not hidden: the vSAN Management SDK classpath gap keeps cluster
controls manual_audit (ComplianceAdapter.java:735-742); the profile-switch stale-key
limitation is logged as an explicit TOOLSET GAP with the Suite API schema reason
(lines 416-424); the single-page `pageSize=10000` stitcher fetch documents that an
over-one-page inventory simply does not stitch that cycle — "never a wrong match"
(ComplianceStitcher.java:206-211). No control is silently mapped onto a non-existent
field to inflate coverage.

## Findings

### WARNING

- **[ControlEvaluator.java:139-150 — RULE-002 / skill § unreadable-is-NOT-compliant]**
  On the `advanced_setting` path, a host whose advanced-settings read *failed* yields
  an empty settings map (`getAdvancedSettings` returns an empty map on SOAP fault
  rather than throwing; the per-host catch also substitutes an empty map). Every
  "X or Undefined" / "Not Present" control then scores **PASS** via
  `allowsUndefined`, because absence is treated as the hardened default. A failed
  read is thus indistinguishable from a genuinely-absent-but-readable key, and the
  former is folded into passes. **This is pre-existing v1 behavior** (verified
  identical in build 1f82d1f, inside the build-41 golden envelope) — so it is **not a
  build-43 regression** and does not block this migration. But it is a latent
  unreadable-is-compliant seam on the advanced_setting path that the vim_property
  path explicitly avoids (UNREADABLE sentinel). Recommend a follow-up: have
  `getAdvancedSettings` distinguish "host read OK, key absent" from "read faulted"
  (e.g. throw on a confirmed SOAP fault so the per-host catch can mark the
  advanced_setting slice unreadable) so the two halves of the SCG "or Undefined"
  semantics are not collapsed onto a failed fetch. Hand back to `sdk-adapter-author`
  as a separate task, not a build-43 gate.

- **[VSphereClient.java:998 / 1238-1260 — skill § vim25 over JAX-WS (SSL posture)]**
  The raw-SOAP path uses an unconditional trust-all `X509TrustManager` +
  `(h,s)->true` hostname verifier for the vCenter `/sdk` connection, regardless of
  the `allowInsecure` config flag (which is read into `ComplianceConfig` but never
  consulted by `VSphereClient`). v1's vim25 path was also effectively
  trust-all, so this is **not a regression** and does not block — but the framework
  v2 direction is `platformSsl(this)` as the production default (tier2_architecture.md
  § SSL), and the adapter now ignores its own `allowInsecure` knob on the vSphere
  transport. Recommend wiring `VSphereClient` to honor `config.allowInsecure` (and
  prefer platform trust when false) in a follow-up. Note: the Suite API stitch path
  *does* use platform SSL correctly — this gap is only the vCenter SOAP socket.

### NIT

- **NIT-1 [VSphereClient.java:995]** vCenter SOAP uses the legacy
  `HttpURLConnection` rather than the framework `ManagedHttpClient`/`java.net.http`
  baseline the rest of v2 standardizes on. Functional and self-contained, but it
  re-implements SSL/cookie/drain plumbing the framework already provides. Consider
  porting to `ManagedHttpClient` in a later build for consistency.

- **NIT-2 [VSphereClient.java:805-872]** Each vim property is fetched with its own
  single-property `RetrieveProperties` round trip (no batched property spec). The
  skill's bulk-read pattern would let one PropertyCollector call gather a resource's
  whole control slice. Unchanged from v1; future optimization only.

- **NIT-3 [SuiteApiStitchClient.java:302-345]** One Suite API token acquire+release
  per push call (per resource). Matches the v1 proven-safe pattern, but a per-cycle
  cached token (acquire once, release in onDiscard / cycle-end) would cut N auth
  round trips to 1. Future optimization only.

## If shipped as-is

An operator gets a compliance adapter that **collects on prod 9.1 for the first
time** (the JAX-WS Provider collision that blocked every cycle is gone — raw SOAP
sidesteps the javax/jakarta SPI trap entirely), with the same metric tree, the same
property/stat keys, the same MOID stitching identity, and the same
unreadable-is-not-compliant scoring as build 41. Unreadable controls surface as an
explicit `unreadable_count` coverage signal, not as inflated passes; an unreachable
vCenter marks the world resource DOWN rather than publishing a false 100. The one
latent seam (a *failed* host advanced-settings read folding "or Undefined" controls
into passes) is pre-existing v1 behavior, not introduced here, and is flagged for a
follow-up task. The remaining acceptance bar is the live golden comparison vs build
41 on devel — which is `qa-tester` / the orchestrator's devel proof, not this static
gate. Nothing in the static review blocks promotion to that step.

## Report
`knowledge/context/reviews/compliance-build-43.md`
