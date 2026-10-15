# Synology build 31 review (sdk-adapter-reviewer)

- **Adapter:** `content/sdk-adapters/synology` (repo `sentania-labs/vcf-content-factory-sdk-synology`)
- **Branch reviewed:** `feat/build-31-availability-and-tls`, tip `d9fd2cf`, 7 commits on `origin/main` (v1.0.0.30)
- **Brief:** `knowledge/designs/sdk-adapters/synology-build-31-availability-and-tls.md`
- **Fork issues in scope:** #15, #12, #13, #14, #21, #19 (#11 deferred by the brief)
- **Date:** 2026-10-15
- **Verdict:** CHANGES REQUESTED (2 BLOCKING, both fixable in text or a few lines; 4 WARNING; 6 NIT)

## Bottom line

The code does what the six issues ask, and I found no path where a
failed read becomes a published value that this build introduced. The
failure cache, the login back-off and the "only login refusals count"
rule all hold, and all 15 mutations I ran were caught by the tests. Two
things block: the docs repeat UniFi's "one WARN" promise, which the
framework contradicts (one WARN with a stack trace per resource), and
the new minimum-privilege table says a failed per-share NFS probe
publishes no placeholder, while an existing NFS export in that state
still publishes `rule_count = 0` and loses its Volume edge for the
cycle. The four UniFi build 14 findings carry over here: B1 is the same
blocker, and W1, W2 and W3 apply unchanged.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| validate-sdk pass | Confirmed on a detached worktree of `d9fd2cf`: `OK: ... is a valid Tier 2 SDK adapter project`. |
| Dev pak 0.0.0.31, sha256 `429cdbd9...` | The author's file exists with sha256 `429cdbd92032d590da68ce114252163ff374baf4f0b15ac75829e2bfe30e0156`. My own `build-sdk` reproduces 0.0.0.31 (sha `f9a69649...`; the difference is expected, from build timestamps). The built `describe.xml` carries `allowInsecure default="false"`, and it has no alerts or symptoms. |
| pak-compare 0/0/0 vs v1.0.0.30 | Confirmed for both my build and the author's pak: `0 BLOCKING, 0 WARNING, 0 INFO`. The reference pak sha256 `beaa8555...` matches the GitHub Release v1.0.0.30 asset digest. |
| `ci/run_java_tests.sh` green (7 Java + 1 Python) | Confirmed: all eight pass. |
| Before/after mutation evidence | Confirmed and extended. I ran 15 mutations, each in a fresh copy, and every one failed at least one test: login codes counted from any API, failure not cached, every endpoint required, a join that is not null-safe, no doubling, a success that does not reset the doubling, an optional read that swallows an auth or connect failure, the LUN/NFS and SSD-cache Volume edges ignoring `volumeChildrenKnown`, a timeout not mapped to DOWN, lenient parse, abort cached, stamp taken at build start, code 410 dropped, and teardown stopping at the first failure. |

Not covered by any test (I checked these by reading; see W2): the
adapter-side wiring in `SynologyAdapter.java`.

## Defect registry (knowledge/context/defects.md)

No open defect names `synology`. Closed: DEF-001, DEF-003, DEF-005, DEF-006.

- **DEF-001 (closed), re-checked, still holds.** `SynologyApiClient.callRaw`
  (`:202-222`) still throws a standalone exception with a redacted
  message and no chained raw cause. The new `SynologyTransportException`
  keeps only the failure class (`classifyTransport` reads classes, never
  messages). The NFS probe wrapper (`SynologyAdapter.java:1427`) chains a
  `SynologyTransportException`, which is already redacted and has no
  cause of its own. `SynologyFailures.describe`, `CachedFailureException`
  and every new WARN are built only from messages that were already
  redacted. The login refusal message carries the code and its meaning,
  never the account. The registry entry needs no change: its invariant
  ("standalone exception, endpoint label plus redacted text, no chained
  cause") still describes the code exactly. An optional one-line addendum
  could name `SynologyTransportException` as the current carrier.
- **DEF-003 (closed), not affected.** The cross-link still emits
  `parentForeign` with the Datastore as parent. While the LUN, share or
  NIC list is unread it simply emits fewer foreign parents, and a foreign
  parent that is not emitted keeps its edges.
- **DEF-005 and DEF-006 (closed), not affected.** The Suite API transport
  and the credential path are unchanged. The stitcher is now discarded on
  reconfigure, which is correct release hygiene.

Registration candidates (RULE-012), if not fixed before a `v1.0.0.31`
tag: **W1** (secure default without the certificate review hook), and
**B2's underlying sentinel** if the author chooses the docs-only fix.

## Carry-over from UniFi build 14

| UniFi 14 finding | Synology 31 | Grade |
|---|---|---|
| B1: docs promise "one WARN" | Present: `CHANGELOG.md:11`, `docs/overview.md:101-103`, `SynologyAdapter.java:603`, `SnapshotCache.java:24`. | **BLOCKING (B1)** |
| W1: no `certificateCheckUrls` override | Present: no override anywhere in `src/` (`platformSsl(this)` at `SynologyAdapter.java:331`). | **WARNING (W1)** |
| W2: adapter-side isolation wiring untested | Present: no test drives `SynologyAdapter` (requireRead, `volumeChildrenKnown`, the `isRead` guards, the cycle hook, the configure teardown). | **WARNING (W2)** |
| W3: cached failure carries the full stack | Present: `CachedFailureException(msg, failure)` (`SnapshotCache.java:132-138`). | **WARNING (W3)** |

## Hunt questions

### 1. SnapshotCache and the DSM auth back-off

- **Cached failure across an instance edit:** cannot happen.
  `configureAdapter` publishes a new `Configured` holder (new API client,
  new cache, new `SnapshotReads`) in one volatile write (`:190-197`), and
  `currentSnapshot` reads the holder once and uses its client and its
  cache together (`:606-616`). Residual, live only: that VCF Ops calls
  `onConfigure` when only the credential is edited, on the Credentials
  page. The brief's wrong-password devel step covers this.
- **Cycle-start mark:** `VcfCfAdapter.onCollect` is `final` and calls
  `collector.needsRediscovery(config)` unconditionally, once, before
  collect-path discovery and the resource loop
  (`src/vcfcf_managementpacks/adapter_framework/src/com/vcfcf/adapter/VcfCfAdapter.java:728`).
  Synology's hook is at `:545`. `getDiscoverer` (`:411-414`) marks a
  cycle only on `onDiscover`, which 9.0.2 never calls. A configure
  partway through a cycle starts the new cache at cycle 0, and the next
  `onCollect` moves it to 1, so the mark cannot be missed in a way that
  serves a stale snapshot. The hook's reliance on `needsRediscovery`
  being called every cycle is the UniFi NIT-1 framework dependency; it
  is true today.
- **Two threads building:** cannot happen. `get` and `beginCycle` are
  `synchronized` and the build runs under the lock. A concurrent
  `onDiscover` would cost one extra build, not a storm.
- **Stop Collecting:** not cached (`SnapshotCache.java:153-154`; this is
  mutation M11). The only DSM call made without a checkpoint first is the
  initial `ensureSession()` login (`:613`); see NIT-3.
- **Back-off schedule:** 15, then 30, then 60 minutes, capped at 60, and
  reset on success (`authBackoff`, `SnapshotCache.java:184-191`). Tests pin each step, and
  mutations M5 and M9 were caught.
- **Can a 400 from a data API trigger the long back-off? No.** There are
  two independent guards. (a) Production never builds a non-login
  `SynologyDsmException`: data calls throw a plain `IOException` from
  `SynologyApiClient.call` (`:185`). Only `login()` (`:63-66`) throws the
  typed exception, with `login=true`. (b) `SynologyFailures.authCode`
  also requires `d.isLogin()` (`:37`). A mid-build re-login after a
  106/107/119 session expiry is a real login, and counting its refusal
  is correct. Mutation M1 (dropping `isLogin`) was caught by
  `otherCodesAreRetriedNextCycle`.

### 2. #14 optional endpoints

Each optional endpoint, checked by reading `SnapshotReads.get`
(`SnapshotReads.java:139-178`) and every consumer:

| Endpoint unread | Published as placeholder? | Dependents |
|---|---|---|
| FanSpeed | No (`:739`) | Fan properties skipped |
| NFS service | No (`:744`) | NFS enabled properties skipped |
| ISCSI.LUN | No: enumerate adds none; existing LUNs throw at `:925` and go ERROR | cross-link LUN loop sees an empty list |
| ISCSI.Target | No (`:938`) | target properties skipped |
| Network.Interface | No (`:735`) | NFS cross-link sees no NAS IPs, so no foreign NFS edges (none emitted means none dropped) |
| CurrentConnection | No (`:758`, `:1002`) | client counts skipped |
| Share | No: enumerate adds none; existing exports throw at `:964` and go ERROR | no per-share probes |
| SharePrivilege (per share) | **Yes, for an existing export** (B2) | |
| UPS | No: the UPS object is not collected (`collectUps` returns), the pre-existing behavior | |

An interrupt, a login refusal or a connect failure on any optional read
still fails the build (mutation M6 caught).

**The author's choice (no Volume relationships while the LUN or share
list is unread): WARNING (W4).** For a transient failure it is the right
call. Volume is full-set, so emitting it with only the known children
would detach the rest for a cycle, and keeping it unchanged avoids that.
For a persistent one it is wrong in a way the operator cannot see. The
docs themselves name the persistent cases: "iSCSI not installed", "a
service that is not installed", "a missing privilege". On such a NAS no
Volume is ever emitted as a parent, so:

- a new SSD cache, or a new NFS export when only the LUN list is
  unreadable, is never attached to its Volume (it is orphaned in the
  traversal tree, permanently, on a fresh install);
- a detached or moved SSD cache keeps its old Volume edge forever.

The docs say edges "stay as they were, so a temporary failure does not
detach them" (`docs/installing.md:58-60`), which is true but silent on
the permanent case. This is not BLOCKING because no value is fabricated
and no edge lands on the wrong object.

### 3. #13: unreachable NAS, NFS probe, abort checks

- **DOWN mapping:** `mapCollectException` (`:586-591`) calls
  `SynologyFailures.isUnreachable`, which walks the chain (cycle-safe)
  for a `SynologyTransportException` of kind CONNECT or TIMEOUT, or a raw
  network exception, and returns false on any login refusal. The cached
  failure carries the original as its cause, so every resource in the
  cycle maps the same way. TLS failures and unknown failures stay ERROR.
  Tests and mutation M8 confirm this.
- **DEF-001:** see the registry section. The new exception keeps the
  class, not the raw cause, which is the right way to satisfy both
  needs. DEF-001 stays closed and its entry needs no update.
- **NFS probe (`:1426`):** a connect failure ends the build. The wrapper
  chains a redacted exception, so DOWN mapping still works. A read
  timeout (TIMEOUT, not CONNECT) does not end it, so a NAS that answered
  the required calls and then hangs costs about 93 s per share (3
  attempts at 30 s). See NIT-4.
- **Abort check (`:627`):** runs before each of the 11 planned reads
  (`SnapshotReads.java:142`), before UPS (`:1333`) and before each
  share probe (`:1413`). Correct apart from NIT-3.

### 4. #21 teardown and a cycle running across a reconfigure

The ordering is right where compliance build 94 was wrong: the new
holder, stitcher and client are built and published before
`releaseConfiguration` (`:285`) runs on the old ones, and no field is
nulled in configure. Two of compliance W4's points still apply
(**W5**):

- **The old client can log in again.** A cycle still running on the old
  holder (`c` captured in `currentSnapshot`) gets session-invalid (119)
  after the logout. `SynologyApiClient.call` then calls `login()` again
  (`SynologyApiClient.java:176-182`), opening a session nobody logs out, which is the #21 leak
  again. If the edit was a password change, the old password is refused,
  and that failed login counts toward DSM Auto Block, which is the #12
  hazard. Compliance closed this with "a closed client refuses
  re-login".
- **Logout is not bounded.** `logout()` goes through the old client's
  `RetryPolicy` (3 attempts, 30 s timeout). A host change made because
  the old address is dead blocks `configureAdapter` (and `onDiscard`) for
  about 90 s. Compliance bounded its logout at 5 s + 5 s.

Compared with compliance N13: Synology reads the holder once per
`currentSnapshot` call, not once per cycle. A cycle spanning an edit
therefore switches to the new holder at its next resource (one extra
build) and never mixes one configuration's client with another's cache.
Nothing goes to the wrong NAS, and there is no pass.

Separately, the "HTTP client discard" step in configure never runs
(NIT-1).

### 5. #19 SynologyTopology

- I ran `TopologyTest`: it passes. The "want" list in
  `fullFixtureEmitsBuild30Edges` is hand-written, so I compared the join
  code against build 30's `buildRelationships`
  (`git show origin/main:.../SynologyAdapter.java:821-946`) line by line.
  The edge order, display names (`num_id`, `cacheName`) and the
  identifier fallback (`volume_id`, else `vol_path`, through
  `SimpleJson.asString(fallback)`, which returns the fallback only for a
  null value) are identical. The NFS gate changed from
  `rules != null && size > 0` to `nfsExports.contains(name)` with
  `nfsExports = nfsRulesByShare.keySet()`. That is equivalent, because
  the map only holds shares with more than zero rules.
- The missing-fields fixture loses only its own edges. A pool without
  `pool_path` keeps its Diskstation edge and its disks and loses its
  volume edges. A pool without `id` loses everything. A volume without an
  identity and a LUN without `location` lose their one edge. Mutation M4
  (non-null-safe `same`) was caught.
- Residual (inherent to full-set parents, correct as designed): a pool
  without `pool_path` is still emitted as a parent with its disks only,
  so its existing volume edges are dropped every cycle. That matches
  "costs its own edges", and the INFO line names it.

### 6. Docs

- The default agrees everywhere: describe.xml `false`, README `false`,
  REFERENCE `false`, docs/installing.md `false`. The upgrade note is in
  CHANGELOG, README (as a pointer) and installing.md. The Python test
  pins them.
- README "DSM admin account" matches the installing.md
  administrators-group requirement. overview and installing agree on the
  back-off schedule, the codes and the 2-step verification refusal.
- The CHANGELOG heading is `## 0.0.0.31 (Unreleased)` and says the 1.0.0
  line is unchanged until a tag.
- No em-dash in hand-written added text. The only added em-dash is the
  generated `docs/inventory-tree.md:3` header (factory #204).
- Contradictions: B1 and B2. Gap: W4 (permanent case).
- Cross-MP relationships are unchanged, and `docs/README.md` still lists
  both.

### 7. Re-runs

All done; see Claims check.

## Findings

### BLOCKING

**B1. Docs say a failed cycle logs one WARN; the log gets one per
resource, each with a stack trace, every cycle of the back-off.**
Dimension 11 (docs that contradict behavior); dimension 6. Same as UniFi
build 14 B1.

- Where: `CHANGELOG.md:11` ("the first resource gets the failure ... and
  the adapter log gets one WARN"); `docs/overview.md:101-103` (same);
  `SynologyAdapter.java:603` javadoc ("one WARN, no new login");
  `SnapshotCache.java:24` ("The first resource gets the original
  exception"). `CHANGELOG.md:13` and `docs/installing.md:38` ("one WARN
  per instance configuration" for an unread endpoint) have the same
  problem whenever LUN or export objects exist: each one goes ERROR
  through the framework WARN every cycle.
- Behavior: `VcfCfAdapter.onCollect` logs
  `logWarn("onCollect: error collecting <resource>: <msg>", e)` with the
  throwable for every resource whose collect throws (`VcfCfAdapter.java:823`).
  The first caller is the collect-path discovery step, not a resource
  (`:752-759`, its own WARN with a stack). With a wrong password the
  log gets, per cycle, one discovery WARN plus one WARN per Synology
  resource (about 25), and that repeats every cycle of the 15 to 60
  minute back-off. The one `Synology snapshot build failed` WARN appears
  only on cycles that attempt a login. The brief's devel proof ("a
  wrong-password edit shows one WARN") would fail against these docs.
  `docs/installing.md:146` is accurate, because it says one WARN *of
  that text*.
- Fix (text only): say "one `Synology snapshot build failed` WARN per
  attempted login, plus one framework line per resource that fails from
  the cached result without contacting the NAS", and "the first caller
  (the discovery step)". Apply it at the four places listed. For the
  #14 wording, say that existing LUN or export objects are reported
  ERROR each cycle while their list is unread.

**B2. The minimum-privilege table says a failed per-share NFS probe
publishes no placeholder; an existing export publishes `rule_count = 0`
and loses its Volume edge.** Dimension 11 (contradiction); dimension 1 /
skill § *Unreadable is NOT compliant*; `knowledge/rules/no-fabricated-metrics.md`.

- Where: the docs claim is at `docs/installing.md:37-40` and `:51`
  ("skips only what depends on it, never publishing a placeholder value
  ... SharePrivilege (per share): that share as an NFS export"). The
  behavior is at `SynologyAdapter.java:1421-1438`: a probe failure that
  is neither connect nor auth is logged and leaves the share out of
  `nfsRulesByShare`. Then `collectNfsExport` (`:964-1004`) passes
  `requireRead(SHARES)`, finds the share, and publishes
  `Access|rule_count = 0` and `Access|allowed_clients = ""` (`:972`,
  `:984`, `:993`) for an export whose rules were not read. In the same
  cycle the Volume is emitted full-set without the export
  (`nfsExports = keySet`), so the export's Volume edge is dropped until
  the next cycle that reads it.
- This was pre-existing in build 30, but this build documents it as
  fixed and claims the #14 class is closed.
- Smallest correct fix, code (preferred): record failed probe names in
  the snapshot. `collectNfsExport` throws for such a share (ERROR, as for
  an unread share list), and `buildRelationships` treats a failed probe
  like an unread share list for that cycle (so no Volume is a parent),
  or carries that export as known. A test belongs with it.
- Alternative fix, docs only: state the true behavior in the table and
  register the sentinel as a tracked defect so it gates nothing silently.

### WARNING

**W1. Secure default ships without the certificate review hook.** Same
as UniFi build 14 W1. Skill § SSL convention;
`knowledge/context/tier2_architecture.md` "Accepting an untrusted target
certificate". There is no `certificateCheckUrls` override
(`SynologyAdapter.java:331`, `platformSsl(this)`). DSM ships self-signed
on 5001, so a fresh instance with the new default fails Test Connection,
and the only path the docs offer besides importing the certificate is
`allowInsecure=true`. This is acceptable for 0.0.0.31 because it is
documented honestly (`docs/installing.md:79-87`, CHANGELOG). For the
release, add `@Override protected List<String> certificateCheckUrls(ResourceConfig rc)`
returning `https://<host>:<port>` from the passed config, as compliance
build 93 does (`ComplianceAdapter.java:305`). Return an empty list when
host is blank or when `SynologyConfig.parseAllowInsecure` (untrimmed)
is true. Then soften "this build does not offer the NAS certificate for
review". The tag workflow pins `sdk-buildkit-v1`, which already carries
the hook. This is a registration candidate.

**W2. The adapter-side wiring has no test.** Same as UniFi build 14 W2.
Dimension 9; the brief's Proof ("optional endpoint failure leaves core
inventory discovered"). SnapshotReadsTest and TopologyTest prove the
helpers. Nothing exercises `requireRead` (`:925`, `:964`), the
`volumeChildrenKnown` computation (`:1036`), the `isRead` guards in
`collectDiskstation` and `collectIscsiLun`, the cycle hook (`:545`), the
UPS and NFS-probe rethrows (`:1345-1348`, `:1426`), or the configure teardown
wiring. I verified them by reading. They are correct except where B2 and
NIT-1 say otherwise, and NIT-1 is exactly the kind of wiring slip a test
would have caught. Fix: move the per-kind "which endpoint does this kind
need" decision and the configure release selection into SDK-free
helpers, or accept and cover them in the devel proof by revoking one
optional privilege.

**W3. Failure-cycle log volume.** Same as UniFi build 14 W3. Dimension
6. `CachedFailureException` chains the full original exception
(`SnapshotCache.java:132-138`), so every per-resource framework WARN is
a multi-line stack, every cycle, for up to 60 minutes per back-off step.
Carry the classification (unreachable or not, auth code) as fields on
the cached exception and drop the cause, so `mapCollectException` keeps
working and each line is one line. A follow-up issue is acceptable if
the author does not change it in this build.

**W4. A persistent LUN or share list failure freezes Volume
relationships forever.** Dimension 1 (adjacent: stale structure, not
fabricated values); dimension 11 (gap); brief hunt question 2. See Hunt
2. On a NAS where the iSCSI or share API is permanently unavailable (the
docs' own examples), new SSD caches, and new NFS exports when only the
LUN list fails, are never attached to their Volume, and removed or
moved SSD caches keep stale edges. Fix options, smallest first:

1. Document the permanent case in `docs/installing.md:58-60` and
   overview.
2. Treat a DSM "API does not exist" answer (error 102, the service is
   not installed) as a read, empty list rather than unread, so a NAS
   without iSCSI has a known-empty LUN set and its Volumes refresh. This
   needs `SynologyApiClient.call` to keep the data-API code as a field.
   That would not be a `SynologyDsmException` with `login=false`
   counting as auth, since `authCode` already requires `isLogin`.
3. Keep the last good Volume child set per configuration and re-emit it
   while a list is unread.

**W5. A cycle running across a reconfigure can log in again on the old
client, and the old session's logout is unbounded.** Compliance build
94 W4, the parts still open here. Dimension 7; issues #21 and #12. See
Hunt 4. Fix: give `SynologyApiClient` a closed flag that `logout()` (or
a new `close()`) sets, and make `ensureSession`/`login` refuse when it
is set. Bound the teardown logout to one attempt with a short timeout,
for example a dedicated single-attempt request or a 5 s deadline.

### NIT

- **NIT-1** `SynologyAdapter.java:185`, `:273`: `oldHttpClient` is
  always null. The framework's `onConfigure` nulls and discards
  `this.httpClient` before calling `configureAdapter`
  (`VcfCfAdapter.java:610-614`), so the configure path's "HTTP client
  discard" step never runs, and the framework has discarded the old
  client before the DSM logout that the `:280` comment says runs first.
  This is harmless today: `ManagedHttpClient.discard()` only releases a
  framework auth strategy, which Synology does not use, so the logout
  still works. Drop the step and correct the comment ("the framework
  discards the old HTTP client before configureAdapter"), or the
  ordering claim will mislead the next change.
- **NIT-2** `ci/run_java_tests.sh` is not run by the tag workflow
  (stated in the CHANGELOG). Compliance build 95 W7 put both guards in
  CI. Worth a one-step addition before the tag.
- **NIT-3** `SynologyAdapter.java:613`: `c.api.ensureSession()` (a login)
  runs before the first checkpoint. Move it inside `Snapshot.build`
  after a `checkpoint("SYNO.API.Auth login")`.
- **NIT-4** `SynologyAdapter.java:1426`: only CONNECT ends the probe
  loop. A NAS that answers the required reads and then hangs costs about
  93 s per share, and the same applies to each optional read
  (`SnapshotReads.get`). Short-circuiting the rest of the build after the
  first TIMEOUT would cap it. This is the same pattern as UniFi NIT-4.
- **NIT-5** `SynologyAdapter.java:1222-1231`: a Stop Collecting raised
  during a resource's build is caught by the framework's generic
  `catch (Exception)` and marks that one resource ERROR before the loop
  breaks. It is transient, but it is an ERROR a stop did not earn.
  Optional: throw `InterruptedException` for the abort too, which the
  framework already treats as a cycle abort.
- **NIT-6** `docs/inventory-tree.md:3`: the generated header contains an
  em-dash. This is generator output (factory #204), not the author's
  text.

## Dimension walk (items not covered above)

- **1 Cardinal correctness:** the four required endpoints still fail the
  build; the hollow-payload asserts (`model`, `cpu`) are kept; unread
  optional data is skipped, never zeroed. The exception is B2, which is
  pre-existing and newly misdocumented.
- **2 Reflection-tolerant reads:** not applicable (REST/JSON;
  `SimpleJson` is null-tolerant, and `SynologyTopology` is now
  null-safe).
- **3 Exception granularity:** optional reads are caught per endpoint;
  interrupts and aborts are rethrown and never cached; the topology
  catches per object; the relationship catch-all at `:569-571` is kept
  as a last resort and logs WARN.
- **4 Canonical loader:** not applicable.
- **5 Stitching identity:** the cross-link is unchanged (path identity,
  never MOID); no new foreign keys.
- **6 Logging / secrets:** no secret found (see DEF-001). The insecure
  WARN carries host and port only. Volume: B1, W3.
- **7 Resource hygiene:** the holder swap releases the old cache; one
  snapshot and one failure held per configuration; no growth. W5 covers
  the reconfigure race.
- **8 API discipline:** at most one build per cycle; the cycle, not the
  clock, decides reuse.
- **9 Build hygiene:** `build_number` 30 to 31; a CHANGELOG entry
  exists; the diff is confined to the six issues plus tests and docs;
  #19's generalization is proven against build 30 by reading and by the
  fixture.
- **10 Gap honesty:** the missing review dialog and the single timeout
  value are named. The permanent W4 case is not.
- **11 Docs parity:** B1, B2 and W4. Relationships and cross-MP docs are
  unchanged.
- **13 describe.xml import rules:** no alerts, symptoms or symptom sets
  (built describe parsed); the only change is the identifier default.

## If shipped as-is

A wrong password costs a handful of failed logins over hours instead of
one per resource per cycle, an unreachable NAS shows DOWN within one
attempt per cycle, a missing optional endpoint no longer hides the NAS,
and an odd object no longer wipes the topology. An operator would find
about 25 stack traces per cycle where the docs promise one WARN. A new
instance against a stock self-signed DSM would fail Test Connection
until they import the certificate or set Allow Insecure SSL to true. On
a NAS without iSCSI, new SSD caches would never appear under their
Volume.

## Re-review: f8e45fa (2026-10-15)

- **Scope:** `git diff d9fd2cf..f8e45fa`, 12 commits, reviewed from a detached worktree of `f8e45fa`.
- **Verdict:** APPROVE (0 BLOCKING, 0 WARNING, 3 NIT)

### Bottom line

All 13 findings are closed. Both blockers are fixed in code and docs.
Every warning is fixed in code with a test. I agree with the author's
choice not to pin the configuration per cycle, for the author's reason.
What remains is three small residuals, none of which can publish a wrong
value or land data on the wrong object. They are listed as nits below,
with one devel check owed: that a NAS without SAN Manager really answers
DSM error 102.

### Claims check (independently re-run)

| Claim | Result |
|---|---|
| validate-sdk | Confirmed: OK. The SDK compile includes the `@Override certificateCheckUrls`, so the factory buildkit carries the hook. |
| pak `dist31r/...0.0.0.31.pak` sha256 `26fdb834...` | Confirmed: `26fdb83466e038fad8f5fb62a5f5cb56fd924f054049387b5420524d0ab80d80`. My own `build-sdk` of `f8e45fa` builds 0.0.0.31. |
| pak-compare 0/0/0 vs v1.0.0.30 | Confirmed for both paks: `0 BLOCKING, 0 WARNING, 0 INFO`. |
| `ci/run_java_tests.sh` 11/11 | Confirmed: 10 Java and 1 Python, all pass. |
| Tests catch the new logic | 20 new mutations; 19 caught. The survivor, N2 (dropping the closed check in `DsmSession.ensure`), is equivalent except in the race in NIT-R2, where the guard is what stops a closed client from being used. |

### Findings, one by one

- **B1 closed.** CHANGELOG #12, #14 and #21, overview `:101-106`, installing `:36-42`, `SynologyAdapter.java:651-660` and `SnapshotCache.java:24-34` now say "one `Synology snapshot build failed` WARN per attempted login, plus the framework's own line for the discovery step and each resource". They say the first caller is usually the discovery step. installing `:180` remains accurate because it quotes the WARN text.
- **W3 closed.** `CachedFailureException(message, authCode, unreachable)` calls `super(message, null, false, false)`: no cause and no stack (`SnapshotCache.java:94`). `authCode` and `isUnreachable` answer from the fields (`SynologyFailures.java:37`, `:86`), and the values are computed once at failure time (`SnapshotCache.java:194-195`). Mutations N12, N13 and N14 were caught.
- **W2 closed.** `SnapshotIsolation` holds the decisions: `requireListRead`, `requireNfsProbe`, `volumeChildrenKnown` and `replaced`. The adapter delegates at `:702` (before the kind switch, for LUN and NFS export), `:1025` and `:1098`, and `:290` for reconfigure. SnapshotIsolationTest drives them. Mutations N9, N10, N11 and N20 were caught.
- **B2 closed.** `NfsProbes.run` records failed probes with their reason (`:85`). `collectNfsExport` throws for such a share (`:1025`), so the export goes ERROR and no `rule_count` is published. `volumeChildrenKnown` is false while any probe failed, so the export keeps its Volume edge. The installing.md row is corrected and now also says a share not yet known as an export is not discovered until its probe succeeds. Mutations N7, N9 and N10 were caught.
- **W4 closed.** The case that hurt (a NAS without iSCSI) refreshes again: error 102 on the LUN and target lists only is read as empty, with one INFO (`SnapshotReads.java:195-213`). The permanent missing-privilege case is now documented honestly (installing `:65-80`, overview), including that a share whose probe is always refused freezes Volume edges and that the WARN names the cause.
  - **Can 102 turn a real failure into an empty read?** Only if DSM answers 102 for something other than "API not installed". The code checks narrowly. The code comes from the response body of a data call typed `login=false` (`SynologyApiClient.java:229`). `dataApiCode` reads only non-login exceptions. A missing code is 0, not 102. A refused re-login or a timeout ends the build before the 102 check (`:192`). FanSpeed and the NFS service keep 102 as unread (mutation N5 caught). Any other code stays unread (mutation N6 caught). The residual is NIT-R1.
- **NIT-4 closed.** `endsBuild` = login refusal, unreachable (connect or timeout), or closed client (`SynologyFailures.java:108`). It is used for optional reads (`SnapshotReads.java:192`), UPS (`SynologyAdapter.java:1423`) and probes (`NfsProbes.java:80`). Mutations N8, N15 and N16 were caught.
- **W5 closed.** `DsmSession` sets the closed flag before logout (`:91-94`). `login` and `ensure` refuse once closed (`:60`, `:74`), and a login in flight at close is logged straight out (`:62-66`). The re-login after 106/107/119 goes through `login()`, so it throws `SynologyClientClosedException`, which ends the build as ERROR. Teardown calls `c.api::close` (`:307`). The logout uses a dedicated client, built with the same TLS settings: one attempt, 5 s timeout (`:208`). Mutations N1, N3 and N4 were caught.
  - **The per-cycle holder decision, on its merits: correct.** `currentSnapshot` reads the holder on every call. A cycle that spans an edit therefore loses at most the one resource whose build was in flight on the old client (ERROR for that cycle), and every later resource builds from the new holder.
    - Pinning the old holder for the cycle, as compliance does, would fail every remaining resource on the closed client, which is strictly worse here.
    - Compliance needs pinning because its cycle state crosses calls. Synology's only cross-call state is the holder itself, so per-call reads cannot mix one configuration's client with another's cache.
    - Every lookup is by identifier, so nothing lands on the wrong object. The one exception is the Diskstation and World singletons after a host change to a different NAS. That is #11, which the brief deferred, and it happens on every cycle after such an edit, not only on the spanning one.
- **NIT-1 closed.** The dead discard step is removed, and the comments now say the framework discards the old client before `configureAdapter`.
- **NIT-3 closed.** `cp.check(LOGIN)` runs before `ensureSession` (`SnapshotReads.java:151`). Mutation N19 was caught.
- **W1 closed.** The `@Override certificateCheckUrls` is at `:332`, backed by `SynologyConfig.certificateCheckUrls` (`:74`). It returns empty while insecure, judged by the pak's own untrimmed parse (mutations N17 and N18 caught), when the host is blank, or when the port is outside 1 to 65535. Blank or non-numeric ports fall back to 5001, the same as the client. The URL format `https://host:port/` matches compliance. The docs (README, installing TLS, CHANGELOG) describe the dialog, the thumbprint check and re-acceptance after a certificate renewal.
- **NIT-5 closed** by documentation (overview `:128-131`). The framework offers no "stopped" outcome, so this is accepted as is.
- **NIT-2 closed** by a CHANGELOG line pointing at #32 (CI7). CI coverage remains owed before the tag, tracked there.
- **NIT-6** is unchanged: generator output (factory #204). No em-dash in any added line of this round.

### Residual NITs (do not block)

- **NIT-R1** `SnapshotReads.java:195`: error 102 is taken at face value on every build. Two consequences:
  - If DSM answers 102 transiently, for example while SAN Manager is still starting after a NAS reboot, that cycle reads "no LUNs". Existing LUN objects then take the pre-existing "absent from snapshot" path (no data for one cycle), and Volume LUN edges are dropped for one cycle, then restored. No value is fabricated.
  - That a NAS without SAN Manager answers 102 at all is unverified live.
  - Owed in the devel proof: one look at the INFO on a NAS without iSCSI, or accept the assumption. Optional hardening: take 102 as empty only once this configuration has never read a LUN, or after two consecutive builds.
- **NIT-R2** `DsmSession.java:62-68`: a narrow race. A login can pass the second `closed` check, then `close()` runs, sees no session yet, and logs nothing out, and only then does the login store its sid. That one session is left for DSM to expire. The `ensure()` guard still stops the closed client from using it, which is why mutation N2 survives. Fix: make `login`'s check-and-store and `close` mutually exclusive (synchronize them), or re-check `closed` after storing the sid.
- **NIT-R3** (`SnapshotIsolation.volumeChildrenKnown`): one share whose probe is always refused freezes every Volume's relationships, not just the Volume that share sits on. It is documented and named by a per-cycle WARN. Narrowing it to the Volume whose `vol_path` matches the failed share would be the precise fix.

### Defect registry

There is still no open defect for `synology`. DEF-001 still holds. The
new data-API `SynologyDsmException` keeps the old message (endpoint
label plus response body, no URL). The logout over the dedicated client
goes through the same redacted `callRaw` and redacted WARN. DEF-003,
DEF-005 and DEF-006 are not affected. The W1 registration candidate is
withdrawn because the hook landed. The B2 candidate is withdrawn because
the code fix was chosen.

### SDK ADAPTER REVIEW (re-review)

```
SDK ADAPTER REVIEW
  adapter: content/sdk-adapters/synology
  build reviewed: 31 (tip f8e45fa)
  verdict: APPROVE
  findings: 0 BLOCKING / 0 WARNING / 3 NIT
  claims check: validate-sdk confirmed; pak-compare confirmed 0/0/0 vs v1.0.0.30 (author pak 26fdb834... verified, own build matches); 11/11 tests pass; 19 of 20 new mutations caught (N2 equivalent outside the NIT-R2 race)
  registry check (knowledge/context/defects.md):
    - none open affect this pak; DEF-001 (closed) re-checked at SynologyApiClient.java:229 and the logout path, still holds; DEF-003/005/006 unaffected
  BLOCKING: none
  WARNING: none
  NIT:
    - [SnapshotReads.java:195] a transient 102 reads as "no LUNs" for one cycle; 102-when-not-installed unverified live (devel check owed)
    - [DsmSession.java:62-68] a login that completes as close() runs can leave one session for DSM to expire; synchronize the check-and-store with close
    - [SnapshotIsolation volumeChildrenKnown] one permanently refused share probe freezes every Volume, not just its own (documented)
  if shipped as-is: wrong passwords back off without tripping Auto Block, an unreachable NAS is DOWN at one attempt per cycle, scoped or iSCSI-less NASes collect, a self-signed NAS is accepted once through the review dialog, and a failed cycle logs one line per object instead of a stack each
  report: knowledge/context/reviews/synology-build-31.md
```

## Final: 2e619d9 (2026-10-15)

APPROVE: 0 BLOCKING, 0 WARNING, 0 NIT. I reviewed
`git diff f8e45fa..2e619d9` (three commits) from a detached worktree.
The tests run 11/11. My own build-sdk and the author's pak
(`dist31n/...0.0.0.31.pak`, sha256 `2de24801f9d88e2c7a4d88301a6c715084d47f622d1030f28ff82e644ed8645f`,
verified) both score pak-compare 0/0/0 against v1.0.0.30.

All three residual nits are closed, and 8 more mutations against the
new code were all caught:
- **NIT-R1 (DSM error 102).** A first 102 on the LUN or target list is
  unread: no WARN, existing LUNs go ERROR, Volume edges are kept. Only a
  second consecutive 102 for the same endpoint in the same configuration
  is read as "not installed". A successful read or any other failure
  resets the count (`SnapshotReads.java:145`, `:195`, `:215-221`,
  `:250`). The docs now say an iSCSI-less NAS costs one cycle after a
  create or edit.
- **NIT-R2 (login race).** `DsmSession`'s login check-and-store and
  `close()`'s mark-and-take share one lock. The lock never spans a DSM
  network call: `loginCall.login()` runs before the lock is taken, and
  every `logoutQuietly` (in-flight login at close, `logout()`,
  `close()`) runs after it is released.
- **The test hook cannot fire in production.** `beforeStore` is a
  package-private field that defaults to null. The only assignment
  anywhere in the repo is `DsmSessionTest.java:127`, and nothing under
  `src/` sets it.
- **NIT-R3 (per-share freeze).** A refused probe now freezes only the
  Volume whose `vol_path` matches the share. The freeze is applied
  consistently to all three of that Volume's child kinds (LUN, NFS
  export, SSD cache, `SynologyTopology.java:228`, `:257`, `:288-289`),
  so a frozen Volume emits no partial full-set. An unread list, or a
  failed share with an unknown `vol_path`, still freezes every Volume
  (`SnapshotIsolation.java:130-145`).
- **Docs and registry.** The docs match the behavior, and no added line
  carries an em-dash. The registry is unchanged: no open defect for
  `synology`, and DEF-001 still holds.

The only item still owed is the devel proof already in the brief
(wrong-password edit, no Auto Block entry), plus one look at the 102
INFO on a NAS without iSCSI if one is available.

## devel_9_1 proof (2026-10-15, content-installer)

Pak 0.0.0.31 (sha256 2de24801, tip 2e619d9) installed 12:46 to 12:49 PM,
fresh install, read back as 0.0.0.31.

- **Certificate dialog: appeared** (12:52 PM) for the NAS entered by DNS
  name on port 5001 with Allow Insecure SSL false; accepted; "Test connection
  successful". The NAS certificate is lab-CA issued (sentania Lab Issuing 2,
  CN int.sentania.net 2026) and its expiry reads September 17, 2026, which
  is in the past. Accepted anyway by the dialog.
- **Collection: PASS.** 31 objects, 628 stats across 9 kinds, Volume 1 with
  2 LUNs, 16 NFS exports, SSD cache and 2 cache disks; datastore cross-link
  through the ambient Suite API on the Cloud Proxy (12 datastores, 2 LUN and
  3 NFS matches).
- **Wrong password: PASS.** Saved 1:02 PM. Seven cycles to 1:32 PM: two login
  attempts (1:02:58, 1:22:59 PM), matching the 15 then 30 minute back-off,
  one "Synology snapshot build failed" WARN per attempt, 30 per-resource
  framework WARNs per cycle each with a one-line CachedFailureException.
  DSM Auto Block list does not contain the Cloud Proxy 172.27.10.11 (policy
  10 attempts in 5 minutes). Correct password restored 1:38 PM; 1:42 PM
  cycle logged in and collected.
- **Optional endpoints:** no 102 or unread lines; this NAS has iSCSI, so the
  "not installed" branch is unexercised (still owed on a NAS without SAN
  Manager).
- **Caveat:** the two attempt cycles log an 18-frame stack under the
  framework's "collect-path discovery failed" WARN, the same gap UniFi build
  14 closed after its proof (stackless attempt exception, logger resolved
  once at configure). Mirrored onto the Synology branch after this proof.
- Expected WARN only: the FIPS-approved-only line once.

Left on the instance: pak 0.0.0.31, account factory-synology-b31 with
credential factory-synology-b31-cred, NAS certificate accepted, password
correct, Allow Insecure SSL false. Nothing changed on the NAS. Screenshots in
the session scratchpad (02-cert-dialog, 05-account-page-healthy, inv,
10-volume-environment, 11-log-viewer-wrongpw, 12-account-page-restored).

## Final: e58f881 (2026-10-15)

APPROVE: 0 BLOCKING, 0 WARNING, 0 NIT. I reviewed
`git diff ff836ef..e58f881` (two adapter commits; the CI caller commits
up to `ff836ef` are out of scope) from a detached worktree. All five
checks hold.

1. **Classification on the attempt cycle is unchanged.** The cache
   classifies the original exception once (`authCode`, `isUnreachable`)
   and records the result before it throws the stackless
   `CachedFailureException` (`SnapshotCache.java:220-258`). So the caller
   whose build failed sees the same DSM refusal code and unreachable flag
   as every caller served from the cache. The failure text keeps the
   original's class name and its already-redacted message chain, so
   DEF-001 still holds.
2. **Nothing `mapCollectException` needs is lost.** It reads only
   `SynologyFailures.isUnreachable`, which answers from the copy's
   fields. The framework's collect path uses nothing else from the
   exception (`VcfCfAdapter.onCollect` catch). Test Connection never goes
   through the cache, so its certificate-trust detection still sees the
   real chain.
3. **The hook cannot throw into collect.** The debug sink is stored once,
   at construction (`:125`, `:168`). The call is guarded by
   `catch (RuntimeException | LinkageError)` (`:250`), after the failure
   state and the WARN are recorded, so a logger fault cannot replace the
   classified exception.
4. **The logger is resolved once, and only in configure.**
   `componentLogger(SnapshotCache.class)` is called once in the source,
   in `configureAdapter` (`SynologyAdapter.java:211`). It is stored on
   the immutable `Configured` holder (`:160`) and handed over as
   `snapshotLog::debug` (`:224`). `currentSnapshot` looks up no logger.
   `test_snapshot_logger_once.py` pins this. As on UniFi, a level an
   operator raises holds until the next reconfigure, where the framework
   resets it to INFO (factory #224). The remaining per-call
   `componentLogger(SynologyApiClient.class)` in Test Connection (`:420`)
   loses nothing, because `SynologyApiClient` has no DEBUG line.
5. **Stop and interrupt still bypass the cache.** The
   `catch (InterruptedException | AbortedException)` clause still comes
   first and rethrows without caching.

**Re-runs.**
- `ci/run_java_tests.sh`: 12/12 (10 Java, 2 Python).
- validate-sdk: OK.
- The author's pak `dist/vcfcf_sdk_synology_diskstation.0.0.0.31.pak`,
  sha256 `e65d2997cc2252d5cc604a3024c7a294cc7237d2923d88e010a06ed6ae5fe541`:
  confirmed.
- pak-compare: 0/0/0 against v1.0.0.30 on that pak and on my own
  rebuild.

**Mutations.** All 7 were caught: removing the sink guard, rethrowing the
original on the attempt cycle, dropping the unreachable flag or the
refusal code from the attempt copy, caching an interrupt, never calling
the sink, and adding a per-call logger lookup back.

**Docs.** The docs match the behavior: overview says one line per
framework entry, with the stack at DEBUG, and that the instance shows
Collecting during a back-off. installing and README say to enter the NAS
by a name its certificate carries, and that the IP-address dialog case is
unproven. No added line carries an em-dash.

**Defect registry.** Unchanged: no open defect affects `synology`.

Remaining before a `v1.0.0.31` tag: the RULE-012 defect gate.
