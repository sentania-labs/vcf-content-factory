# SDK Adapter Review — compliance build 50

- **Adapter:** `content/sdk-adapters/compliance`
- **Build reviewed:** 50 (commit `ac8df18`) vs build 49 (`eba91b2`)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 0 NIT
- **Date:** 2026-06-10
- **Closes:** build-49 review (`knowledge/context/reviews/compliance-build-49.md`) — B1, W1, W2, N1.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `validate-sdk` clean | **Confirmed by direct run.** 10 sources compiled, 1 benign `-source 11` warning. |
| `build-sdk` reproduces | **Confirmed by direct run.** `dist/vcfcf_sdk_compliance.1.0.0.50.pak`; adapter jar `vcfcf_compliance.jar` 75,486 bytes; `lib/` = `vcfcf-adapter-base.jar` only (aria-ops-core correctly omitted, v2 adapter). |
| pak-compare vs 49 = 0 BLOCKING / 1 WARNING (new attribute) | **Confirmed by direct run.** `pak-compare 50 49` → `0 BLOCKING, 1 WARNING, 0 INFO`. The single WARNING is `ComplianceWorld group attribute count: factory=6, reference=5` — exactly the additive `hosts_scored_stale` ResourceAttribute. Author's claim matches to the count. |
| Diff scope = the four named fixes + describe/props/version/docs | **Confirmed.** `git diff 49→50` touches `ComplianceAdapter.java`, `ComplianceConfig.java`, `describe.xml`, `resources/resources.properties`, `adapter.yaml` (49→50), `CHANGELOG.md`, `REFERENCE.md` only. No unrelated drive-by. |
| Bundled framework jar carries the d59785a framework fixes | **Confirmed by direct bytecode disassembly** (see below). |
| Trees clean after build | **Confirmed.** compliance clone, unifi clone, and factory tree all `git status` clean; generated sidecars landed in the gitignored factory build dir, no hand-doc clobber. |

## Finding closure (independently verified)

### B1 (was BLOCKING) — SSL default now genuinely flips to strict — CLOSED

Verified at **both** layers, **in the shipped pak** (not just source):

- **describe.xml (shipped):** extracted `vcfcf_compliance/conf/describe.xml` from the
  built `…50.pak` — `allowInsecure` identifier now reads
  `default="false"` (was `default="true"`). The SHIPPED descriptor, not just the
  source, carries the strict default.
- **Parse (source):** `ComplianceConfig.java:27` is now
  `this.allowInsecure = "true".equalsIgnoreCase(allowInsecure);`. Traced the
  truth table: `null` (absent field on every existing/fresh instance) → `false`;
  `""` → `false`; `"0"`/`"no"`/`"off"`/anything-not-"true" → `false`; only the
  literal `"true"` → `true`. **null/blank is now strict**, which is the exact
  inversion the build-49 B1 demanded. `getIdentifier(...,"allowInsecure")`
  returning `null` now yields `allowInsecure=false` → `sslSocketFactoryFor`
  takes the `getPlatformSslContext()` (platform-trust) branch. The documented
  "platform trust by default / allowInsecure opt-out" is now matched by the code.
- **Authority:** `knowledge/rules/no-fabricated-metrics.md` / skill *Gaps — name them*
  (docs must match behavior) — now satisfied; the build-49 contradiction is gone.
- **Deployment note carried forward:** the build-49 deployment risk is now
  *real* — any instance against a vCenter whose cert is not in the platform
  trust store must import the cert or explicitly set `allowInsecure=true`, or
  SOAP collection fails TLS validation. The failure is loud and actionable
  (the `sslSocketFactoryFor` WARN names the remedy) and the CHANGELOG calls it
  out. This is the installer's runbook item, not a code defect.

### W1 (was WARNING) — first-class world-level staleness visibility — CLOSED

The hard requirement was that `hosts_scored_stale` **cannot count a live-read host**
and is **pushed every cycle**. Both verified by tracing every increment and push:

- **One and only one increment site:** `staleScored++` appears at
  `ComplianceAdapter.java:798`, inside `applyLastKnownForUnreadableHost`, and
  **nowhere else** (grep confirmed: declaration `:1349`, push `:411`,
  increment `:798`).
- **That method is reached only from the two unreadable branches**
  (`:630` connection-state-disconnected, `:676` adv-settings-flap), and **both
  branches `continue` immediately after** — they never fall through to the
  live-scored path. A host read live this cycle takes neither branch, so its
  score can never be counted as stale. Furthermore the method **guards
  `last == null` and returns before incrementing** (`:790-796`), so a
  never-read unreadable host does not inflate it either. `staleScored` is a
  strict subset of `scored`, incremented in lockstep at the only fold site.
- **Pushed every cycle, unconditionally:** `pushWorldMetric(out,
  "Summary|hosts_scored_stale", (double) hostStats.staleScored, ts)` at
  `:410-411` sits **outside** the `if (hostStats.scored > 0)` guard — it emits
  even on a zero-host / all-unreadable cycle (value 0), so the metric is never
  absent. describe.xml + resources.properties (nameKey 28) declare it; confirmed
  present in the shipped descriptor.
- **Authority:** skill *Unreadable is NOT compliant* (staleness must be visible
  every cycle) — satisfied. An operator can now read "N of M averaged hosts are
  stale" directly instead of inferring from the indirect control count.

### W2 (was WARNING) — null-guarded cache write — CLOSED

`ComplianceAdapter.java:719-721` — the scored-path write is now
`if (hostId != null) lastKnownHostScore.put(hostId, cr.score);`, matching the
read side (`applyLastKnownForUnreadableHost`'s `hostId == null` guard, `:790`).
The `ConcurrentHashMap.put(null,…)` NPE that could abort the whole cycle (the
per-host loop still has no per-host try/catch and `collectHosts throws
Exception`) is removed. The asymmetry build 49 introduced is gone.
**Authority:** review dimension 3 / skill *Reflection-tolerant reads* — a single
resource's defect must never abort the cycle. Satisfied.

### N1 (was NIT) — bounded cache across host churn — CLOSED

New `evictAbsentHostScores(hosts)` (`:751-781`) runs at the end of
`collectHosts` and `retainAll`s `lastKnownHostScore.keySet()` against the live
`getHosts()` MOID set. Correctly **does not** evict a host that is merely
unreadable this cycle — such a host is still enumerated by `getHosts()` (it
stays in `hosts`), so only genuinely de-inventoried hosts are pruned. Logs an
INFO when any key is evicted. The unbounded-growth smell (dimension 7) is closed
without endangering the last-known cache for transiently-unreadable hosts.

## Framework jar — bytecode-verified (this is the pak I disassembled directly)

Exploded `vcfcf_compliance/lib/vcfcf-adapter-base.jar` from the shipped pak and
disassembled with `javap -p -c`:

- **`RelationshipBuilder.resource(String resourceKind, String name, String idKey,
  String idValue)`** — the `new ResourceKey(...)` site loads `aload_2`
  (param `name`), `aload_1` (param `resourceKind`), then the `adapterKind`
  field, invoking `ResourceKey.<init>(String,String,String)` as
  **`(name, resourceKind, adapterKind)`** — the **CORRECTED** order matching the
  verified SDK constructor `ResourceKey(resourceName, resourceKind,
  adapterKind)`. The investigation's documented arg-swap
  (`unifi_401_and_relationship_persistence_2026_06_10.md` B-prime-suspect) is
  **fixed** in the bundled jar.
- **`SessionCookieAuth` / `ManagedHttpClient`** — source carries the
  single-retry-on-401/403 (`AuthStrategy.invalidateAuth()` → replay-once,
  no loop) and the **removed Host header** in `sendWithRoundRobin` (only a
  comment "Do NOT set a Host header" remains; no `"Host"` header is set).
- **Same jar in the unifi build-5 pak:** SHA-256
  `0e873aec…b0a8f15` is **identical** between the compliance-50 and unifi-5 paks,
  so this single bytecode verification covers both builds.

**Compliance does not exercise these framework paths on its hot path** (it
builds its own `ResourceKey` for the synthetic world, stitches via
`SuiteApiStitcher`, runs `SessionCookieAuth` against localhost Suite API). The
jar refresh is correctly characterized as a consistency change, not a fix
compliance depends on. No regression introduced.

## Hunts cleared (verified safe)

- **Unreadable-is-compliant:** PASS. Never-read hosts still excluded
  (`last == null` → return, no fold); only real scores cached (`put` gated on
  `cr.totalCount > 0`, unchanged); `staleScored` strictly tracks the stale-fold
  and is pushed every cycle. No fresh-pass for a blind host; no sentinel cached.
- **Zero-divisor contract:** PASS. `avg_host_score` still gated on `scored > 0`
  with an explicit "no data" WARN; `total_hosts` and now `hosts_scored_stale`
  emit unconditionally. A `totalCount==0` host surfaces as unreadable, never a
  folded 100.
- **Stitch identity:** PASS. `matchHost(hostName, hostId)` keys on MOID; no
  foreign-resource join changed this build.
- **Crash-the-cycle:** PASS. The W2 null-guard removes the one new NPE vector;
  no new throw on the per-host path.
- **Redaction:** PASS. New/changed lines emit hostname, score, connState, the
  `allowInsecure` boolean, and evict counts only. The configure log
  (`:160-163`) emits vcenter host / profile / allowInsecure bool / stitcher flag
  — no credentials. The password-bearing SOAP login envelope
  (`VSphereClient.java:172`) is passed to `post()`, never logged (pre-existing,
  unchanged). `knowledge/rules/no-secrets-on-disk.md` clean.
- **Build hygiene:** PASS. `build_number` 49→50, matching CHANGELOG entry,
  minimal diff, no drive-by refactor.

## If shipped as-is

An operator upgrading to build 50 gets the security posture the docs have been
advertising: vCenter SOAP TLS now validates against the platform trust store by
default, and `allowInsecure=true` is a deliberate per-instance opt-out (the
build-49 inversion is gone — confirmed in the shipped describe.xml). Any existing
instance pointed at a self-signed vCenter will need the cert imported or
`allowInsecure=true` set at upgrade or collection fails TLS — a loud, actionable
failure the runbook must flag. The world scoreboard now carries a dedicated
`hosts_scored_stale` count so an operator can see, directly, how many of the
averaged hosts are running on weeks-old last-known scores rather than inferring
it from a control count. The last-known cache no longer leaks across host churn,
and a (theoretical) null-MOID host can no longer abort a collection cycle.

## Verification artifacts

- `validate-sdk` (direct): OK, 10 sources compiled.
- `build-sdk` (direct): `dist/vcfcf_sdk_compliance.1.0.0.50.pak`; adapter jar
  75,486 B; lib = `vcfcf-adapter-base.jar` only.
- `pak-compare 50 vs 49` (direct): 0 BLOCKING / 1 WARNING (ComplianceWorld group
  attr count 5→6 = `hosts_scored_stale`) / 0 INFO.
- Shipped `describe.xml`: `allowInsecure default="false"`; `hosts_scored_stale`
  nameKey 28 present.
- Framework jar bytecode (direct `javap`): `RelationshipBuilder.resource` emits
  `new ResourceKey(name, kind, adapterKind)` — corrected order; Host header not
  set; SessionCookieAuth 401-retry present. SHA-256 identical to the unifi-5 jar.
- All trees clean post-build; no doc-sidecar clobber.
