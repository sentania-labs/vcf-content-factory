# UniFi build 15 review (sdk-adapter-reviewer)

- **Adapter:** `content/sdk-adapters/unifi` (repo `sentania-labs/vcf-content-factory-sdk-unifi`)
- **Branch reviewed:** `fix/build-15-correctness`, tip `00ac220`, 16 commits on `origin/main` `cdf0476`
- **Brief:** `knowledge/designs/sdk-adapters/unifi-build-15-correctness-and-hygiene.md` items 1 to 11
- **Fork issues in scope:** #34, #24, #23, #22, #18, #14, #16, #29, #21, #27 (items 1 to 3), #32
- **Date:** 2026-10-16
- **Verdict:** CHANGES REQUESTED (1 BLOCKING, 3 WARNING, 9 NIT)

## Bottom line

Ten of the eleven items do what their issue asks, and the build reproduces
exactly as claimed. The blocker is the Protect half of #21: when the Protect
bootstrap fetch fails, the last good one (up to an hour old) is fed into the
normal NVR and camera collectors, which publish it with the current
timestamp. During a Protect outage every camera keeps reporting
`is_recording = true` and `state = CONNECTED` for up to an hour, and the only
sign is an INFO line in the adapter log. That is the "offline looks healthy"
failure #14 removes from the Network side in this same build, and it also
pulls in the edge-flapping half of #20, which the brief lists as waiting on
Scott's decision. The vmnic host-list cache (15 minutes, slow-changing
topology) is fine.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `ci/run_java_tests.sh`: 10 Java + 10 Python pass | Confirmed, 20/20. The build 14 test files (AllowInsecure, FailureMapping, SiteIsolation, SiteReads, SnapshotCache, SnapshotTiming, test_allow_insecure_default) are byte-identical to `origin/main`; only `test_snapshot_logger_once.py` was extended (#34). |
| validate-sdk pass | Confirmed: `OK: content/sdk-adapters/unifi is a valid Tier 2 SDK adapter project`. |
| Dev pak `dist/vcfcf_sdk_unifi_controller.0.0.0.15.pak` sha256 `eb487d7c...0dd2f` | Confirmed (`eb487d7cd3d0c26318829ead64f32e1351dfa7270564e57321f0ea33f3d0dd2f`). My own `build-sdk` into scratch reproduces 0.0.0.15. The pak's `describe.xml` is identical to the source file apart from the version stamp, and has no alerts or symptom sets (dimension 13 not applicable). |
| pak-compare vs 0.0.0.14 (sha256 `b7ac9e9b...5b1`, confirmed) 0 BLOCKING / 6 WARNING | Confirmed on the author's pak and on my rebuild: 0 BLOCKING, 6 WARNING, 0 INFO. All six are group attribute counts on Gateway, WanInterface, Switch, SwitchPort, AccessPoint, Radio, each matching the added `Status|state` or `tx_rate`/`rx_rate` keys. Expected. |
| describe.xml integrity | No duplicate nameKeys, every nameKey has a `resources.properties` label, no duplicate group keys per kind. |

Mutations (scratch copies, `ci/run_java_tests.sh`): satisfaction -1 published,
no stale bound in RefreshCache, blank `port_idx` read as 0, site name not
encoded, "all hosts unread" treated as success, the relationship camera guard
removed, Test Connection discard removed: all caught. Switch PoE metrics
published while disconnected (`:1021`, `:1051`): **two mutations survive** (N3).

## Defect registry (knowledge/context/defects.md)

No open defect names `unifi` (open entries: DEF-004 vcommunity-os, DEF-017
packaging CLI, DEF-019 extractor, DEF-020/021 vcommunity-vsphere,
DEF-023/025/026 compliance). DEF-002 and DEF-007 (unifi) stay closed: the
stitch still emits additive foreign edges from the same join, now fed from a
cached host list, and the CP collect path is unchanged.

Registration candidates if not fixed before acceptance: **B1** (Protect stale
reuse) and **W3** (View Only recommendation unproven).

## Findings

### BLOCKING

**B1. A failed Protect fetch republishes an up-to-an-hour-old bootstrap as current NVR and camera data.**
`UniFiAdapter.java:1788` (reuse through `c.protectBootstrap`, `PROTECT_REFRESH_MS = 0` at `:193`, stale bound `SLOW_MAX_STALE_MS` 60 min);
`collectNvr` (`:1263`) and `collectCamera` (`:1310`) have no notion of a reused
snapshot and publish everything with `System.currentTimeMillis()`.
Authority: skill § *Unreadable is NOT compliant* (a value the adapter failed
to read must never become a pass); issue #14, whose whole point is that an
unreachable device must not look healthy; the brief's scope list, which puts
#20 (stale resource handling) under "waiting on Scott's decision, not in this
build", while the CHANGELOG and overview sell this reuse as "the edge
flapping half of fork issue #20".
Failure scenario: the Protect application on the console crashes, upgrades
or loses the account's access at 10:00. Until 11:00 every cycle publishes,
for the NVR and every camera, the 09:55 values: `Status|is_recording = true`,
`Status|is_connected = true`, `Status|state = CONNECTED`, a frozen camera
`Status|uptime`, frozen NVR storage. Nothing is recording, the pak says
everything is, and any future camera-offline alert (#30) is suppressed for
an hour. Before build 15 those objects went without data for the cycle.
Smallest correct fix, either:
(a) drop the Protect reuse (fetch every cycle, no cache, exactly build 14)
and leave the flap fix to #20's decision; or
(b) keep the reused bootstrap only for `enumerateResources` and
`buildRelationships` (edge stability), set a `protectReused` flag on the
snapshot, and have `collectNvr` / `collectCamera` publish no metrics and no
status properties while it is set (or throw, so the objects show the
failure); log the reuse at WARN; update CHANGELOG and overview.md to say so.
Add a test that pins the flag.

### WARNING

**W1. RefreshCache trusts a wall clock that can step backwards.**
`RefreshCache.java:58` and `:71`. Age is `clock.millis() - loadedAt` on
`System.currentTimeMillis`. A negative age passes both `< refreshMs` and
`< maxStaleMs`. Unlike `SnapshotCache`, nothing else (no cycle id) bounds it.
Authority: the class's own contract ("refreshMs 0: fetched on every call",
"at most maxStaleMs after it was fetched") and skill § *Unreadable is NOT
compliant*.
Failure scenario: the collector VM's clock is stepped back 30 minutes by NTP
(after a resume or a snapshot revert). For the next 30 minutes the Protect
bootstrap is served from the cache without a fetch and without any log line,
and the vmnic host list is held up to 45 minutes; a failed refresh can reuse
a value older than the hour.
Fix: treat `now < loadedAt` as expired in the fresh check and as
not-reusable in the failure path (`age >= 0 &&`), or use a monotonic clock
(`System.nanoTime`) for these ages; add a RefreshCacheTest case with the
clock moved back.

**W2. The landing docs are silent on build 15's operator-visible behavior changes.**
`docs/overview.md` (Metrics scope at `:42`, Notable Behaviors from `:116`).
Authority: dimension 11 (docs parity); the behaviors exist only in
CHANGELOG.md and, as bare keys, REFERENCE.md.
Missing: the new `Status|state` metric and that a disconnected gateway,
switch or AP (and its ports, radios, WANs) publishes state and properties
but no metrics, so charts now show a gap instead of 0; that an absent field
publishes no point instead of 0 (views or super metrics that averaged the
zeros change value); devices, ports and cameras without identity are
skipped; the two renamed keys and the new `tx_rate` / `rx_rate`. REFERENCE.md
lists the radio `tx_rate` / `rx_rate` without the "unproven on a live
controller" caveat the CHANGELOG carries.
Failure scenario: an operator reading the pak docs sees an AP's CPU chart go
blank and has no doc saying that blank means "disconnected", not "broken".
Fix: one Notable Behaviors bullet for #14 (state, gaps, present-only) and one
for #23, the rename and rate keys under Metrics scope, and the radio caveat
in REFERENCE.md.

**W3. The new Account section recommends View Only, and the new sysinfo call relies on it, with no proof that View Only can read everything the pak reads.**
`docs/installing.md:10-11`, `:28-30`; `UniFiAdapter.java:1760`.
Authority: skill § *Gaps, name them, never hide them*; the overview's own
session note: the framework's `SessionCookieAuth` invalidates the token on
any 401/403 and replays the request once with a fresh login.
Failure scenario: an operator follows the new docs and creates a View Only
account. If that role is refused `stat/sysinfo`, each cycle costs one extra
login per site (refusal, re-login, replay, refusal, INFO line). If it is
refused the Protect bootstrap, NVR and camera objects never appear. Neither
is shown either way today.
Fix: in the planned devel_9_1 proof, run the instance with a local View Only
account and confirm a full collect: sysinfo 200, version and timezone
populated, Protect objects present, no per-cycle re-login in the log. If
that cannot be shown, say "unproven" next to the recommendation.

### NIT

**N1. Absent numeric properties still read "0" (and absent booleans read "false" / "Half").**
`UniFiAdapter.java:1105` (`Status|speed`), `:1226-1229` (`min_txpower`,
`max_txpower`), `:1346` (`Hardware|phy_rate` when `phyRate` is absent),
`:1104`, `:1107`. Authority: issue #14's "missing fields can't be told apart
from real zeros". The CHANGELOG honestly says "Properties are unchanged", so
this is not hidden. My judgement on the author's question: not a blocker,
because these are string properties, not metrics, and do not feed trends or
averages; but a missing `speed` reads exactly like a down port (UniFi sends
0 for a down port), and the branch already edits these methods. Fix:
`asString("")` for the three numeric ones; leave the booleans unless a
cheap tri-state is wanted.

**N2. The main HTTP client is discarded twice on every edit and on discard.**
`discardConfigured` (`UniFiAdapter.java:1612-1615`) discards `c.clients.main`,
which `VcfCfAdapter.onConfigure` already discarded (`VcfCfAdapter.java:611-615`)
and `super.onDiscard()` discards again (`:890-893`). Harmless today:
`ManagedHttpClient.discard()` only calls `SessionCookieAuth.discard()`, which
is `invalidate()` (`SessionCookieAuth.java:100`), and the javadoc says so. But
it relies on idempotency the framework does not promise. Fix: discard only
`clients.login` in `discardConfigured` and leave the main client to the
framework (Test Connection's `finally` keeps discarding both).

**N3. Switch PoE gating is not pinned by any test.**
`UniFiAdapter.java:1021` and `:1051`. Removing `perf` from either condition
passes the whole suite (two mutations survived). Fix: add both to
`tests/test_present_only.py`.

**N4. The new sysinfo call swallows an interrupt.**
`UniFiAdapter.java:1759-1765`: `catch (Exception e)` absorbs
`InterruptedException` from `statSysinfo`, while this build's own CHANGELOG
says Stop Collecting now reaches the framework from the stitch and Protect
reads. Fix: `catch (InterruptedException e) { throw e; }` before it, as at the
stitch and Protect sites. (The `statHealth` catch above has the same shape
but predates this build.)

**N5. A partly failed host-properties refresh is now held for 15 minutes.**
`UniFiStitcher.java:200`, `:214`: only "every host unread" counts as a failed
refresh. When one fallback batch fails and others read, the list (those
hosts without neighbours) is cached for the full 15 minutes; before build 15
a per-host failure cost one cycle. Edges are additive so nothing is removed,
but those ports lose their `LLDP|*` claimant for up to 15 minutes. Fix:
treat `unread > 0` as a failed refresh when a last good list exists (the
cache then reuses it), or document the window.

**N6. The upgrade notes are incomplete.**
`CHANGELOG.md` 0.0.0.15: the two renames carry an explicit **Upgrade note**,
but the WAN unit change (bytes/s to bytes) and the "absent is no longer 0"
change do not. Both change what existing charts, views and super metrics
show. Fix: one upgrade-note line each (WAN charts that treated the counter
as a rate move to `tx_rate` / `rx_rate`; averages that included offline
zeros will rise).

**N7. REFERENCE.md conventions.** New rows leave Unit and Monitored blank
(`state` rows, `recording_retention_days`) where the rest of the file uses a dash placeholder, and the
header still says "for build 1.0.0.4". Fix for consistency.

**N8. Device Count includes devices the inventory skips.** `UniFiAdapter.java:896-899`
counts every adopted (or unflagged) device, including one with no MAC that
#23 now skips everywhere else. Fix: skip `deviceMac(dev) == null` in the
count so the property matches the discovered devices.

**N9. #32 asks for the 9.x path to be verified against a 9.x UI; it was not.**
CHANGELOG says so openly. Fix: check "Administration > Integrations >
Repository" and "Accounts" during the devel_9_1 install and note the result.

## Hunt questions

### #14 metricIfPresent
- A real 0 publishes (`UniFiValues.number("0")` is 0.0, tested); -1
  satisfaction is skipped (`satisfaction`, tested); free text, booleans, NaN,
  hex are skipped. `SimpleJson.asString()` hands a Long as `"123"` and a
  Double as `"1.5E10"`, both accepted by the regex.
- Disconnected gateway, switch, AP: `publishState` publishes 0 and returns
  false; system stats, temperatures, speedtest, satisfaction, PoE budget are
  skipped; properties still publish. WAN (`:973`), port (`:1082`) and radio
  (`:1192`) check the parent device's state and skip every metric, the radio
  traffic and rate included; their properties still publish.
- Unknown state: no `Status|state`, present metrics publish.
- 0.0 sentinels left: none in any `metric(...)` call. Remaining zero defaults
  are properties (N1). `parseDouble` is gone.

### #23 identity guard
Applied in `enumerateResources` (devices `:568`, ports `:590`, cameras
`:629`), `buildRelationships` (devices `:1381`, uplink pass `:1426`, cameras
`:1467`), the snapshot index (`:1725`, cameras `:1797`), `findPort`
(`:1570`) and the stitch port index (`:2095`, `:2101`). A skipped device's
ports and radios are skipped with it in both enumerate and relationships
(their keys derive from the MAC and the loop is inside the device branch),
so nothing is orphaned; a device whose uplink is a skipped device attaches
to the site. Existing resource keys are unchanged for real MACs and indexes.

### #24 client discard
Test Connection discards both clients in `finally`; `onDiscard` and
`configureAdapter` call `discardConfigured` (login client, main client,
stitcher, each guarded). The raw login client has no auth strategy, so its
`discard()` is a no-op today; the CHANGELOG states that the JDK client is
left to GC (framework matter). Double discard of the main client exists and
is harmless (N2). Test Connection on a bare instance resolves the logger
once and builds and discards its own pair.

### #21 stitch and Protect
Bulk `GET /api/resources/properties?resourceId=..` matches
`getResourcePropertiesList` in `reference/docs/operations-api.json` and
`operations-api-9.1.json` (response `resourcePropertiesList[].resourceId /
property[]`); the author correctly avoided `POST` on that path, which is
`addResourcesProperties`. Batches of 50; a failed or empty bulk answer falls
back per host; Call A order is kept. Host list cached 15 minutes per
configuration. RefreshCache and SnapshotCache are both `synchronized`, the
refresh cache is only taken inside the snapshot lock, never the reverse, so
no lock-order inversion. A failed refresh past the hour throws and the
stitch or Protect degrades as before; `loadedAt` is never moved on reuse, so
a reused value is not re-stamped in the cache. It is, however, published
with fresh timestamps for Protect (B1), and a backward clock step defeats
the bounds (W1). Holding the Protect bootstrap across cycles costs one extra
document in memory per instance, bounded.

### #16 / #29 keys and units
`Status|seconds_since_last_motion` and `Configuration|recording_retention_days`
(float, numeric property) are in describe.xml, `resources.properties`,
REFERENCE.md and the CHANGELOG. WAN `tx_bytes` / `rx_bytes` unit is `bytes`.
`tx_rate` / `rx_rate` publish only when the `-r` field is present on port,
WAN and radio. Port and WAN fields are in the API map
(`knowledge/context/api-maps/unifi-network-api.md`); the radio key is
unproven and named as such in the CHANGELOG (not REFERENCE, W2).

### #18 sysinfo
One call per read site per cycle (failed sites skip it, so cooled-down sites
are not asked); any failure is caught and logged INFO and the site and
snapshot carry on (interrupt aside, N4). `version` and `timezone` exist in
`stat/sysinfo` per the API map. Device Count comes from the cycle's
`stat/device` after `requireSiteRead` (N8 for the MAC-less edge).

### #22 site path
`UniFiIds.pathSegment` (URLEncoder, `+` to `%20`) via
`UniFiApiClient.sitePath`; `default` and alphanumeric ids are unchanged
(tested).

### #34 logger
`componentLogger(UniFiApiClient.class)` appears once in `configureAdapter`
(`:300`) and once in the bare-instance branch of Test Connection (`:444`);
the login callback captures the resolved logger. No lookup remains in a
per-cycle or per-login path. The new inventory logger is resolved once too.

### Build 14 behavior
SnapshotCache, SiteReads isolation and cool-downs, DOWN mapping and the TLS
default are untouched; their tests are byte-identical and pass.

### Docs
#27 item 1 consistent (`false` in describe.xml, README, installing.md);
item 2 replaced in README and installing.md; item 3 Account section present.
#32 path fixed (N9 for verification). No em-dashes in added lines except the
known generated `inventory-tree.md` header.

## If shipped as-is

During any Protect outage of up to an hour, every camera keeps reporting
recording and connected, and the NVR's storage freezes, with nothing on the
objects to say the data is stale.

## Round 2 (tip `c4257e6`, 8 commits after `00ac220`), 2026-10-16

**Verdict: APPROVE, 0 BLOCKING / 0 WARNING / 2 NIT.** All 13 round 1
findings are fixed in code or docs, each fix is pinned by a test that fails
when the fix is reverted, and the build reproduces.

### Claims check (re-run)

| Claim | Result |
|---|---|
| `ci/run_java_tests.sh` | 20/20 pass, exit 0. |
| validate-sdk | `OK: content/sdk-adapters/unifi is a valid Tier 2 SDK adapter project`. |
| Pak sha256 `88976bed...a49a9` | Confirmed on `dist/vcfcf_sdk_unifi_controller.0.0.0.15.pak`. My own `build-sdk` into scratch reproduces 0.0.0.15. |
| pak-compare vs 0.0.0.14 | 0 BLOCKING / 6 WARNING / 0 INFO on the author's pak and on my rebuild, the same six attribute-count warnings as round 1 (describe.xml is not touched in this round). |

Mutations (scratch copies), all caught: fresh check without the clock
guard, reuse without the clock guard, partial refresh not thrown, partial
value cached, main client discarded again in `discardConfigured`, the N8
device-count skip removed. Round 1's two surviving PoE mutations are now
caught by `test_present_only.py`.

### Findings, one by one

- **B1 closed.** The Protect cache is gone: `api.protectBootstrap()` is
  called directly every snapshot (`UniFiAdapter.java:1781`), with no
  `RefreshCache<SimpleJson>`, no `PROTECT_REFRESH_MS`. A failed fetch leaves
  `s.protect` null and `collectNvr` / `collectCamera` publish nothing that
  cycle (build 14 behaviour). The interrupt rethrow is kept.
  `test_stitch_refresh.py` asserts that no Protect cache exists. CHANGELOG
  and overview now say so and leave the #20 edge-flap half open for Scott.
- **W1 closed.** `RefreshCache.java:86` treats `now < loadedAt` as
  expired; `:100` refuses reuse at a negative age. Tested
  (`clockSteppedBackIsExpired`).
- **W2 closed.** overview.md now covers `Status|state`, the rate keys and
  the counters, the renames, "a gap means not reported, never a fake 0"
  (and how to read a blank chart next to `Status|state` 0), and the
  no-identity skip. REFERENCE.md carries the radio-rate caveat.
- **W3 closed (docs).** installing.md marks the View Only role and the
  sysinfo/Protect reads as to be confirmed on devel, says what a refusal
  costs, and gives the fallback. The live check itself stays on the
  devel_9_1 proof list.
- **N1 closed.** `Status|speed`, `min_txpower`, `max_txpower`,
  `phy_rate` use `asString("")`; pinned.
- **N2 closed.** `discardConfigured` discards only the login client
  (`:1606`); the main client is left to the framework; Test Connection
  still discards both; pinned.
- **N3 closed.** Both switch PoE gates are pinned.
- **N4 closed.** The sysinfo catch rethrows `InterruptedException`; pinned.
- **N5 closed.** `UniFiStitcher.java:227` throws `RefreshCache.Partial`
  when any host is unread (the all-unread `IOException` at `:214` still
  comes first). With a last good list that is fresh enough, that list is
  reused and reported at WARN. Without one, the partial list serves this
  cycle only and is not cached (`RefreshCache.java:110`). Unread hosts carry
  an empty neighbour list, never null. Tested (`partialRefresh`).
  Observation, not a finding: if the bulk form fails all the time and one
  host can never be read, then after the hour every cycle goes back to the
  build 14 per-host load, with a WARN. That is a safe way to degrade.
- **N6 closed.** Upgrade notes for the WAN unit change and for
  "absent is no longer 0" are in the CHANGELOG.
- **N7 closed, with the dash change judged below.** The header now says
  build 15; new rows use the placeholder.
- **N8 closed.** Device Count skips MAC-less devices (`:884`); pinned.
- **N9 open as a live item** (verify the 9.x menu paths during the
  devel_9_1 install), as round 1 said; no code change possible.

### The REFERENCE.md dash placeholder

Replacing the em-dash placeholder with "-" across the table cells is
acceptable and matches the no-em-dash rule. REFERENCE.md is hand-maintained
after the first build: `_generate_docs` (`src/vcfcf_managementpacks/sdk_builder.py:3040`)
writes only `REFERENCE.generated.md` once the file exists, so a build will
not revert it. The cost is that every future merge from the generated file
shows the placeholder as a diff, because the generator still emits the em-dash.
That belongs in a factory issue for `tooling`, not this branch.

### NIT

- **R2-N1.** REFERENCE.md still has three em-dashes the sweep missed:
  the title (line 1) and the LLDP note (lines 225, 230). Fix: replace them
  too, or say why they stay.
- **R2-N2.** The sysinfo comment at `UniFiAdapter.java:1747-1751` has a
  line that runs past the wrap ("...per cycle). A failure costs those two").
  Fix: rewrap.

### Registry

Still no open defect affects unifi. Round 1's registration candidates
fall away: B1 is fixed, and W3 is marked in the docs and tracked as a live
proof item.

### If shipped as-is

Operators get the build 15 behaviour as documented. The two nits are
cosmetic: three stray em-dashes in REFERENCE.md and one badly wrapped
comment.

## Round 3 (tip `1876783`, 5 commits after `ddfac3e`), 2026-10-16

**Verdict: APPROVE, 0 BLOCKING / 2 WARNING / 1 NIT.** The seven
peer-review changes are correct and tested. Nothing in this round can fail
the snapshot or publish a fabricated value. Two decisions need tightening
before the PR: the skip set for device state codes, and how the host list
treats an answer with no `resourceList`.

### Claims check (re-run)

| Claim | Result |
|---|---|
| Tests | `ci/run_java_tests.sh` 21/21 (SysinfoGateTest added), exit 0. |
| validate-sdk | OK. |
| Pak sha256 `0a4341c5...6d0a` | Confirmed on `dist/vcfcf_sdk_unifi_controller.0.0.0.15.pak`; own `build-sdk` reproduces 0.0.0.15. |
| pak-compare vs 0.0.0.14, 0/6 | Confirmed on both paks. Gateway, Switch and AccessPoint each count one more attribute than in round 2 (`state_code`); the six warnings are all attribute counts. |
| nameKeys 54/104/177 | No collision: no duplicate nameKey anywhere in describe.xml, no duplicate key in `resources.properties`, every nameKey labelled ("State Name"). 54 follows 53, 104 follows 103, 177 follows 176, and none was used before. |

Mutations, all caught: state 6 not skipped; SysinfoGate never closing;
a refusal not opening the window; the gate bypassed in `Snapshot.build`;
a host the bulk answer omits not re-read; cameras parented under a null NVR.
No em-dashes in added lines; REFERENCE.md now has none.

### The four questions

**SysinfoGate cannot block the snapshot.** `shouldAsk` does no I/O and
takes only its own lock. The call (`UniFiAdapter.java:1813`) is in a
`try` that catches every `Exception` except `InterruptedException`
(rethrown on purpose, round 2 N4). A failed re-login from the framework's
replay arrives as a `RuntimeException` and is caught too. `failed()` runs
inside that catch; `UniFiFailures.authStatus` and `refusalKind` walk the
cause chain null-safely, with a cycle guard, and a null message only puts
"null" in the log text. So the handler cannot throw into the build. A
build where every site failed has no `sysinfoSite` and never asks. The
window is per configuration (an edit clears it) and treats a clock that
stepped back past its start as passed (tested). A sysinfo timeout is not
auth-class, so it is retried on the next build; it costs time, never the
site.

**State 6 is the right second skip code, but the set is too narrow (W-R3-1).**

**The camera no-parent choice is acceptable.** A Protect bootstrap without
`nvr.mac` is a theoretical case. Registering a MAC-less NVR would bring
back the empty-identifier object #23 removes, and putting its cameras
under the site would claim a topology the controller did not report.
No parent is the honest option: the cameras still register and collect
under their own MAC, existing edges are left alone (no full-set write from
a null parent), and overview.md says so. No finding.

**The other changes check out.** A host missing from a bulk answer is
read per host and counted as unread if that read fails, giving a Partial.
`byId.get` cannot return null for a host outside `perHost`. The
`metricIfPresent` bodies are pinned. Device Count counts only discovered
types with a MAC; Camera Count only cameras with a MAC. Radios with a
blank code are skipped in enumeration, relationships, the snapshot index
and `findRadioStats`, consistently.

### WARNING

**W-R3-1. Only states 0 and 6 stop the metrics; "inform error" (9), and
"isolated" (11) and "adoption failed" (10), which the map does not name,
keep publishing whatever the controller last stored.**
`UniFiValues.java:79`. Authority: the method's own rationale (stop "when
the controller then reports its last values or none"); skill § *Unreadable
is NOT compliant*; issue #14. The pak's own name map says 9 is "inform
error", meaning the controller is not receiving the device's informs. Its
values then are as stale as in heartbeat missed (6), and unlike 6 the
state can last for days (a device still informing an old controller
address after a move). Neither the codes nor their meanings are in the
repo's API map, which records only `"state": 1`
(`knowledge/context/api-maps/unifi-network-api.md:1278`), so this decision
rests on knowledge outside the repo.
Failure scenario: an AP pointed at a retired controller IP sits in state 9.
Its CPU, uptime, client count and radio metrics publish the last stored
values with current timestamps every cycle, while `Status|state` reads 0.
A chart shows a flat, healthy-looking line.
Fix: invert to an allow-list. Publish metrics only for states where the
device is informing (1, 4, 5, 7; absent state as today), and skip every
other code, unknown codes included. Record the state-code table and its
source in the API map (an `api-explorer` note, marked community-sourced
until seen on devel). Alternatively, gate on `last_seen` age. Either way,
pin it in UniFiValuesTest.

**W-R3-2. A host-list answer with no `resourceList` always fails the
refresh, even when it is a genuinely empty result.**
`UniFiStitcher.java:135`, `VmnicLldp.requireResourceList`. Authority: the
reference idiom, compliance `ComplianceDecisions.resourcePageOutcome`
(`content/sdk-adapters/compliance/src/com/vcfcf/adapters/compliance/ComplianceDecisions.java:651-655`).
It treats a page with no `resourceList` as complete when
`pageInfo.totalCount` is 0, and as incomplete otherwise. The UniFi check
has no such case.
Failure scenario: a VCF Ops instance with no VMWARE HostSystems (UniFi
only, or vCenter not yet added). If the Suite API leaves out an empty
`resourceList`, which the compliance code was written to expect, every
cycle logs `vmnic→port stitch: fetch/match failed` at WARN forever, with
nothing ever cached. That is a misleading WARN, not data loss.
Fix: mirror compliance. With no `resourceList` and `pageInfo.totalCount`
equal to 0, return an empty host list. With no list and a non-zero or
missing total, keep the failure. Add a VmnicLldpTest case.

### NIT

**R3-N1.** `docs/installing.md:48` runs well past the wrap ("...read once
per cycle; that a View Only account may read"). Fix: rewrap.

### Registry

Still no open defect affects unifi. W-R3-1 is a registration candidate if
it is accepted without the fix.

### If shipped as-is

A device stuck in "inform error" keeps charting frozen, healthy-looking
metrics until someone notices it reads 0 on `Status|state`. On an Ops
instance with no ESXi hosts, the log may carry one misleading stitch WARN
every cycle.

## After round 3 (recorded 2026-10-19)

Five commits landed on PR #36 after the round 3 approval at `1876783` and
merged with it (merge `6c3c66d`): `d5eb97c` (rewrap the Permissions
Required paragraph, R3-N1), `7b4dddb` "metrics publish only in informing
device states", `9ad71ea` "pin that the host list check reads
pageInfo.totalCount", `60957a6` "discovery skips devices pending adoption,
so Device Count ...", `1d38315` "pin that isDiscovered passes the adopted
flag (Codex P2 on #36)". By their subjects `7b4dddb` answers W-R3-1 and
`9ad71ea` is in the W-R3-2 area, but no round in this record re-reviewed
them, so W-R3-1 and W-R3-2 stand as open here.
