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
