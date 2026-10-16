# Synology build 32 review (sdk-adapter-reviewer)

- **Adapter:** `content/sdk-adapters/synology` (repo `sentania-labs/vcf-content-factory-sdk-synology`)
- **Branch reviewed:** `fix/build-32-correctness`, tip `62861a4`, 14 commits on `origin/main` `804203f` (build 31). The brief said 15; the branch has 14, all in scope.
- **Brief:** `knowledge/designs/sdk-adapters/synology-build-32-correctness-and-hygiene.md`, items 1 to 15
- **Fork issues:** #33, #26, #17, #27, #23, #18, #24, #25, #34, #20, #28, #22, #31, #29, #37
- **Date:** 2026-10-16
- **Verdict:** CHANGES REQUESTED (1 BLOCKING, 4 WARNING, 9 NIT)

## Bottom line

The code is good. All 15 items are implemented as the brief and the
accepted decisions say, the build 31 machinery is untouched, and 25 of
my 28 mutations were caught. The one blocker is a promise the docs make
that the shipped pak does not keep. CHANGELOG #27 and the
`vrops_username` row in docs/installing.md say the Suite API account is
no longer written to the adapter log. In fact the framework's
`SuiteApiStitchClient`, which ships in the pak, still logs
`principal=<vrops_username>` at INFO twice on every configure. It also
puts `principal=` into its 401 and token exception messages, and
`SynologyRedaction.redact` does not mask that key. The warnings cover
three things: the NFS-off path, which leaves existing export objects
orphaned with stale rule values and is not in the upgrade notes; stale
9.x menu paths; and two regression guards that are missing.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `ci/run_java_tests.sh`: 16 Java + 7 Python pass | Confirmed on a detached worktree of `62861a4`: 23 of 23 "all assertions passed". |
| Every test file is in the runner list | Confirmed. All 16 `*Test.java` files under `tests/com/vcfcf/adapters/synology/` are listed. `T.java` is the assertion helper, not a test. All 7 `tests/test_*.py` are listed. |
| validate-sdk OK | Confirmed: `OK: ... is a valid Tier 2 SDK adapter project`. |
| Dev pak 0.0.0.32 | My `build-sdk` reproduces `vcfcf_sdk_synology_diskstation.0.0.0.32.pak`. The author's file is at `dist/` with sha256 `8f6dfddd...`. My sha differs, which is expected from build timestamps. |
| pak-compare 0/0/0 vs 0.0.0.31 (sha256 `8ea76f21...`) | Confirmed for both my pak and the author's: `0 BLOCKING, 0 WARNING, 0 INFO`. The reference file at `dist/vcfcf_sdk_synology_diskstation.0.0.0.31.pak` matches the stated sha256. |
| describe.xml and collectors agree | Confirmed by script: every declared `Group|key` is published somewhere, and every published key is declared. |
| No alerts or symptoms (dimension 13) | Confirmed. The describe change is units only. |

Mutation pass (my own; each mutation run in a fresh copy against the full runner):

| Caught (25) | Survived (3) |
|---|---|
| Bond without a total row summed; memory not multiplied by 1024; a failed probe remembered; `serviceOff` ignoring whether the service was read; paging ignoring totalCount; every miss reloading; pick ignoring the desired version; a chained cause on the transport exception; an unredacted runtime message; `remainLife` ignoring trustable; path fallback while mountSpaceId is present; Test Connection using the instance session name; volume free not computed; usage 0 on a zero total; WARN on every failure; never a full refresh; Info unreachable swallowed; Info failure thrown; logout with the shared name; 404 advice dropped; page cap; `safeCgi` accepting anything; VLAN children counted | **M9** `callRaw` back to `catch (IOException e)` (W3); **M12** `user=` dropped from redact (N1); **M21** `!s.nfsDisabled` guard removed (W1) |

## Defect registry (knowledge/context/defects.md)

No open defect names `synology` (DEF-001, -003, -005, -006 are closed;
no `defects.local.md` exists).

- **DEF-001 (closed): re-checked, holds, and is stronger.** The
  `callRaw` catch now covers `IOException | RuntimeException`
  (`SynologyApiClient.java:327`). It rethrows
  `SynologyRedaction.transportFailure` (`SynologyRedaction.java:68-77`):
  endpoint label, simple class name and redacted message, built with
  `super(message)` and no cause. Mutations M8b (cause chained) and M26
  (raw message) were caught. The real vector was `URI.create` in
  `ManagedHttpClient.get`, which throws an `IllegalArgumentException`
  carrying the full login URI, and it is now covered. An optional
  addendum to the entry could name `SynologyRedaction.transportFailure`
  as the current carrier. The guard against reverting the catch is
  missing (W3).
- **DEF-003 (closed): not affected.** `parentForeign(datastore, child)` is unchanged (`SynologyAdapter.java:1276`, `:1305`).
- **DEF-005 / DEF-006 (closed): not affected.** The Suite API transport
  and credential path are unchanged. Uniqueness flags are still read
  from `identifierType.isPartOfUniqueness` (`SynologyStitcher.java:285-287`).
  Dimension 5 holds.

**Registration candidates (RULE-012):**
- B1's framework half, if it is not fixed in this build: the framework logs the explicit Suite API principal at INFO and in exception messages, on every pak that uses `createExplicit`. Scope `factory:<adapter-framework area>`.
- W1, if the author takes the docs-only route.

## Issue closure evidence

- **#33:** `mapCollectException` maps `SynologyFailures.isUnreachable` to DOWN (`SynologyAdapter.java:685-690`). `isUnreachable` walks the chain for CONNECT or TIMEOUT. Covered by FailureMappingTest (`unreachableIsDown`, `wrappedUnreachableIsDown`). This build adds that a runtime-wrapped connect failure or timeout is still DOWN (RedactionTest `wrappedConnectFailureStillDown`; I also probed a `SocketTimeoutException` inside an `UncheckedIOException`, and it is TIMEOUT and DOWN). Close.
- **#26:** the snapshot is keyed to the cycle. `needsRediscovery` calls `beginCycle` (`SynologyAdapter.java:644-645`, `:512-525`), and `SnapshotCache` is unchanged since build 31 (SnapshotCacheTest, SnapshotTimingTest). Close.
- **#27:** not fully closed until B1 is fixed (see below).
- All other issues: implemented as stated. See the hunt walk.

## Findings

### BLOCKING

**B1. The docs promise the Suite API account is not logged; the shipped pak logs it on every configure, and the redaction misses `principal=`.**
Dimension 11 (docs contradict behavior), dimension 6, issue #27.

- Claims: `CHANGELOG.md:12` ("the Suite API account is no longer
  written to the adapter log"); `docs/installing.md:214` (vrops_username:
  "Not written to the adapter log.").
- Behavior, confirmed in the built pak
  (`synology_diskstation/lib/vcfcf-adapter-base.jar`):
  `SuiteApiStitchClient.Builder.build()` logs
  `credential mechanism=explicit principal=<username> endpoint=...` and
  `transport=openPlatformConnection ... principal=<username>` at INFO
  (framework `SuiteApiStitchClient.java:333-335`, `:389-392`). The
  logger is `componentLogger(SuiteApiStitcher.class)`
  (`SynologyAdapter.java:291-293`), which writes to this instance's
  adapter log. The `Suite401Exception` and token-acquire `IOException`
  messages end in `principal=<username>` (`:936-939`, `:1044-1048`).
  `SynologyRedaction.redact` has no `principal=` pattern
  (`SynologyRedaction.java:40-53`), so `SynologyStitcher.java:141-142`
  and `SynologyAdapter.java:1319-1320` write it into the WARN
  unredacted.
- Failure scenario: an operator on a Cloud Proxy sets `vrops_username=svc-vcfops` and reads docs/installing.md's promise. Every configure writes `principal=svc-vcfops` twice at INFO. With a wrong or expired password, every relationship cycle adds `VMWARE Datastore load failed: ... principal=svc-vcfops`.
- Fix:
  1. Add `principal=` to the redaction patterns, with a RedactionTest case for the framework's 401 message shape. That closes the adapter's own WARN paths.
  2. Then do one of these. Either correct both doc claims, saying the adapter's own lines no longer name the account and the framework's Suite API client still logs it at INFO, with a factory issue for `tooling`. Or have `tooling` drop `principal=` from the explicit-path logs in the framework before the tag.

### WARNING

**W1. With NFS off, existing export objects are orphaned, keep stale rule values, and the upgrade notes do not say so.** Dimension 11 (gap); dimension 1 (adjacent); issue #20. Brief question: silent gap or correct?

- Code: `SynologyAdapter.java:1606-1614` (`nfsDisabled`, no probes,
  cache cleared), `:1131` (rule keys skipped), `:1219`
  (`in.nfsExports = nfsRulesByShare.keySet()`, which is empty).
- **Skipping `rule_count` and `allowed_clients` is correct.** The rules were not read, and publishing 0 would be a sentinel.
- **At the object level the gap is silent:**
  - VCF Ops keeps showing a property's last value once it stops being published. An export therefore shows its old `rule_count` and `allowed_clients` indefinitely while NFS is off.
  - All its other share data keeps collecting green.
  - Every Volume is emitted full-set without the export, so the Volume edge is dropped every cycle (`volumeChildren` is all-known; nothing failed).
  - Its VMWARE Datastore parent edge stays, because a foreign parent that is not emitted keeps its edges.
  - Result: an export detached from its Volume but still under its Datastore, with frozen rule values.
- This is a behavior change from build 31. On an NFS-off NAS, SharePrivilege still answers with the configured rules, so the exports used to stay linked. The change is missing from the CHANGELOG #20 upgrade note (`CHANGELOG.md:18`) and from `docs/installing.md:85-92`.
- Mutation M21 survived: no test pins the guard.
- Fix, smallest first:
  1. Document it: the Volume edge is dropped, the last rule values stay displayed, existing objects are not removed, and the Diskstation NFS-enabled property says why. Add an upgrade-note line and a Python wiring assert for the guard.
  2. Better: treat NFS-off like build 31 B2 for existing exports (ERROR through `requireNfsProbe`, so the state is visible), or carry exports as known so the Volume edge is not dropped.

**W2. 9.x menu paths are still wrong in two places, and they contradict the #37 fix.** Dimension 11; issue #37.

- `docs/installing.md:224-225` says "Administration > Solutions > Add", then "Data Sources > Integrations > Accounts". That is the 8.x path.
- `README.md:35` says "Administration > Solutions" for the upload.
- `README.md:44` (the #37 fix) now says Administration > Integrations > Accounts, so the two docs disagree.
- Factory evidence for 9.x: `knowledge/context/investigations/2026-10-14-unsigned-pak-policy-9-1-1.md:127` ("Administration, Integrations, Repository, Add") and `2026-10-13-account-dialog-advanced-settings-and-cert-accept.md:88` (Integrations, Accounts, ADD ACCOUNT).
- **Judgment on docs/installing.md:225: wrong for 9.x.**
- Failure scenario: an operator on 9.x following docs/installing.md finds no "Data Sources" menu and no "Solutions" page.
- Fix: use the UniFi README idiom (`content/sdk-adapters/unifi/README.md:11`, `:15`):
  - upload: Administration > Integrations > Repository > Add (9.x), Data Sources > Integrations > Repository (8.x);
  - account: Administration > Integrations > Accounts > Add Account (9.x), Data Sources > Integrations > Accounts (8.x).
  - Since the prerequisites say 8.x or 9.x, the README Configure step needs the 8.x path too.

**W3. The #17 catch is not pinned by any test.** Dimension 9; DEF-001 invariant.

- `SynologyApiClient.java:327`: RedactionTest drives `SynologyRedaction.transportFailure` directly. Nothing checks that `callRaw` catches `RuntimeException` and routes it there.
- Mutation M9 (back to `catch (IOException e)`) survived with all 23 checks green. A later refactor could reopen #17 silently.
- Fix: one assertion in a Python wiring test, for example in `test_api_info_wiring.py`: both `callRaw` overloads' catch is `IOException | RuntimeException` and throws `SynologyRedaction.transportFailure(endpoint, e)`.

**W4. A lowered API version feeds older payload shapes into readers that publish 0 for absent fields, and only an INFO says so.** Dimension 1 (evaluable set widened); dimension 10; issue #31.

- The design (`min(maxVersion, desired)`) is accepted and implemented correctly: `DsmApis.java:149-177`, `SynologyApiClient.java:92-160`.
- The consequence: on a DSM that offers only older versions, which docs/installing.md says are untested:
  - Before, the build failed honestly (ERROR, nothing published).
  - Now the snapshot may succeed with older shapes, and every unchanged `asDouble()` reader publishes 0 for any field the older version lacks (temperature, IO, LUN rates and others).
  - The only signal is `log.info("SYNO.API.Info read: older versions in use: ...")` (`:154`).
- Fix: log the lowered list at WARN, saying values from lowered APIs are unverified. Add one sentence to docs/installing.md's DSM paragraph that such values can read 0 where the older API lacks a field.

### NIT

- **N1** `SynologyRedaction.java:46-52`. My probes found these not masked:
  - a JSON password containing an escaped quote (`"password":"ab\"cdSECRET"` leaves `cdSECRET`);
  - `token=` as a query parameter;
  - a JSON `"authToken"` member;
  - URL userinfo (`https://u:SECRET@host`).

  None comes from today's framework messages. Also, `user=` alone is untested (M12 survived).
- **N2** `DsmApis.java:144-147`, `:177`: `minVersion` is parsed but never used. A desired version below DSM's minimum is still requested and fails. Either prefer `maxVersion` in that case or name it in the load summary.
- **N3** `DatastoreIndex.java:54`: an empty page before `totalCount` is reached returns the partial list as the whole index. The CHANGELOG says "never a partial index", which is true only for a thrown page. Separately, a row shifted across a page boundary during a concurrent change can index one key twice, and the LUN loop (`SynologyAdapter.java:1275-1278`) does not dedupe as the NFS loop does. Impact is low: a foreign parent that is not emitted keeps its edges.
- **N4** Stale wording:
  - `README.md:15`: storage pool "Capacity (total, used, usage %)"; the labels are now Allocated / Allocated %.
  - `docs/overview.md:40`: "per-window CPU load"; now Load Average.
  - `docs/overview.md:42`: pools "used/free".
- **N5** `SynologyMetrics.java:101-121`: in the no-total-row fallback, Open vSwitch interfaces (`ovs_eth0`) listed beside `eth0` are counted twice. This only applies when DSM sends no total row.
- **N6** `SynologyApiClient.java:92-94`: while Info is unread, it is asked again at every login, including each 106/107/119 re-login. A TLS failure therefore costs two failed calls per login attempt.
- **N7** `SynologyAdapter.java:851`: `memory_usage_pct` still publishes `asDouble()` (0 when absent), next to sibling keys that now skip. This was already the case before this build.
- **N8** The commit count in the brief (15) does not match the branch (14).
- **N9** `docs/inventory-tree.md:3`: generated header em-dash (factory #204). No other added line has an em-dash.

## Hunt walk

- **#17:** verified (DEF-001 section). A wrapped connect failure is still DOWN (RedactionTest; my TIMEOUT probe). The two Suite API WARN paths are redacted except for `principal=` (B1).
- **#27:** the username is gone from the adapter's INFO (`SynologyAdapter.java:296-297`). All three Suite API WARNs pass through `redact`. `test_suite_api_log_redaction.py` pins that no log call names `suiteApiUser` or `suiteApiPassword`. Redaction covers `password=`, `username=`, JSON `password`/`token`, and OpsToken/Bearer/Basic. Gaps: B1 (`principal=`) and N1.
- **#23:**
  - Collecting session name: `VCFContentFactory-<instanceId>` (`SynologyAdapter.java:241-243`).
  - Test Connection: `VCFContentFactory-test-<random>` (`:454-455`).
  - Logout: names its own session and appends `_sid` through `synoUrl(sid, ...)` (`SynologyApiClient.java:181-183`, `:376`).
  - Teardown and closed flag: `DsmSession`, `Teardown` and the 5 s single-attempt logout client are unchanged (`git diff --stat` empty for those files). `sendLogout` adds only a lock-free `apis.pick` read.
- **#18:**
  - Memory: multiplied by 1024, declared unit bytes (`describe.xml:84-95`); an absent field is skipped.
  - Network: the total row is used alone. Without one, the interfaces are summed, skipping `lo` and VLAN children whose parent is listed.
  - A bond without a total row publishes nothing (null, not 0); MetricsTest covers it and M1 was caught.
  - The API map sample (`synology-system.md:131-135`) shows no total row on the lab NAS. The author names this as a devel check.
- **#24:** unit removed, display names "Load Average (n min)", values not divided. As accepted.
- **#25:**
  - One helper, `SynologyTopology.serves`, used by the Volume cache metrics (`SynologyAdapter.java:967`), the SSD cache name (`cacheName`, discovery `:587`) and the edge (`SynologyTopology.java:330`).
  - The path fallback applies only when `mountSpaceId` is absent or empty; M11 was caught.
  - The Datastore cross-link has no cache join in build 31 code. The CHANGELOG says so, and that is correct.
- **#34:**
  - Volume free = total minus used. Pool relabelled Allocated (nameKeys 104/105 are used only by the pool).
  - `remain_life` read from `.value`; -1 and `trustable:false` skipped.
  - LUN latency read from `read_avg_latency` / `write_avg_latency`, which matches `synology-iscsi.md:108-129` (Utilization `lun[]`, the same row the adapter reads).
  - Usage is skipped on a zero or missing total. No new key publishes 0 for an absent field.
- **#20:**
  - No probes when NFS is off; only a read response with `enable_nfs` present counts (M4 caught).
  - Answers reused for 15 minutes; new shares probed at once; a failed probe not remembered, so it is retried each cycle; WARN at most hourly per share. All tested, M3/M16/M17 caught.
  - A refresh interrupted by an unreachable NAS leaves `refreshedAt` unset, so the next build is full again. Correct.
  - NFS-off exports: W1.
  - Hidden shares are not skipped (accepted).
- **#28:**
  - Pages of 1000 until `totalCount`, cap 100 pages with a WARN, reuse for 30 minutes or until a new miss; a known miss does not reload (M5/M6/M22 caught).
  - Missing `totalCount`: a short page ends it.
  - A page that throws mid-way: `fetchAll` throws, `loadDatastores` sets an empty index and `failed()`, and the next cycle retries. No partial index is cached from a thrown page.
  - An empty page mid-way: N3.
- **#31:**
  - Info is asked on `query.cgi` at the first login, with no sid.
  - Version is `min(max, desired)`, on DSM's path when it is a plain `*.cgi` name.
  - Unreachable on Info is rethrown and maps to DOWN (M18 caught); any other failure falls back with one WARN per client (M24 caught).
  - An unlisted API is called the build 31 way.
  - Version-shape risk: W4.
- **#22:**
  - 403/404/406 carry the advice text; `isAuthCode` already covered them in build 31. They go through `authCode`, then the `SnapshotCache` login back-off.
  - `SnapshotCache.java` is unchanged.
  - FailureMappingTest pins the advice, the auth path, `endsBuild`, and not-DOWN.
- **Build 31 intact:** the TLS default is `false` (describe), and SnapshotCache, SnapshotReads, SnapshotIsolation, DsmSession, Teardown and SynologyTransportException are all byte-unchanged. Earlier tests: only FailureMappingTest and NfsProbesTest changed, and both are additions only (no deleted lines).
- **describe.xml:** full parity (script). The GiB label is in code (`SynologyAdapter.java:1055`). The CHANGELOG has upgrade notes for memory, network, load, pool labels, volume free, remain_life, LUN latency and GiB. NFS-off is missing (W1).
- **Docs:**
  - #29: vrops fields, the explicit path's 443 requirement, the account scope, and the key count (118 / 98, verified by script). Drive family is kept as `disk_code` (accepted).
  - #22: the hardening section is present.
  - #37: README Configure is fixed, but installing.md and README Install are not (W2).
  - No added em-dashes outside the generated header.

## Dimension walk (not covered above)

- **2 Reflection-tolerant reads:** not applicable (REST/JSON). The new helpers return null on absent or non-numeric values; `SimpleJson.parse` never returns null.
- **3 Exception granularity:** probe failures are per share; the cross-link is caught as a whole; Info failures are caught and classified; interrupts are rethrown everywhere.
- **4 Canonical loader:** not applicable.
- **7 Resource hygiene:** NFS cache and Datastore index are per configuration, bounded by share count and Datastore count, and pruned to listed shares. No per-cycle growth (`knownMisses` is bounded by computed paths).
- **8 API discipline:** fewer NFS probes, fewer Suite API reloads, one Info call per client.
- **9 Build hygiene:** `build_number` goes from 31 to 32, there is a CHANGELOG `0.0.0.32 (Unreleased)` section, and the diff is confined to the 15 items. Generalizations (SynologyMetrics, the cache join) are covered by tests and by M1-M25.

## If shipped as-is

Memory, volume free space, SSD remaining life and LUN latency would
show real values instead of fabricated ones. Instances stop logging
each other out, and NFS probe and Suite API load drop sharply. An
operator using explicit Suite API credentials would still find the
account name in the adapter log on every configure, despite the docs
saying it is not there. On a NAS with NFS turned off, export objects
would drift away from their Volume with stale rule values and no
explanation in the docs.
