# Per-collector adapter sync: what the platform exposes, and a verify design (issue #314, 2026-11-11)

Question: after a `.pak` install, how can the factory installer tell, for each
collector, whether that collector has loaded the pak's adapter kind at the new
version, without SSH; what re-triggers the jar sync; and what should the
installer do with it.

Method: reads only, 2026-11-11 21:50 to 22:30 UTC, against `devel` (VCF Ops
9.0.2), `devel_8_18` (Aria Ops 8.18.7), `devel_9_1` and `prod` (VCF Ops 9.1.1):
Suite API GETs, read-only `/ui/*.action` calls through the installer's own
`_UISession` (`mainAction` names taken from the 9.1.1 UI bundles
`/ui/dist/js/app.part0..6.min.js`), and root SSH to all five Cloud Proxies and
the devel analytics node for `ls`, `grep`, `sha256sum`, `cat` (the 8.18 and 9.1
analytics nodes reject the factory key; prod's analytics node has SSH closed).
Nothing was installed, started, stopped or restarted; no test connection,
redescribe, or other write was issued. Log stamps are UTC.

Every claim is marked **VERIFIED** (observed today, or in a retained log) or
**INFERRED** (reasoned from what was observed, not tested).

Prior record this builds on: `../investigations/2026-11-06-vsanperf-proxy-logs.md`
(the 8.18 new-kind failure), `../../lessons/remote-collector-upgrade-start-race.md`
(three failure modes), `pak_install_api_exploration.md` §"No endpoint reports
the adapter version a collector loaded" (spec-only check, now partly superseded
below).

**Supportability.** S1 (`/ui/supportLogs.action`) and the Redescribe grid
(`/ui/redescribe.action`) are Struts handlers behind the product UI, not
REST: undocumented, no contract, may change between releases, and the
`X-Ops-API-use-unsupported` header does not apply to them. The
`/internal/cloudproxies/*` endpoints named below are unsupported REST and
need `X-Ops-API-use-unsupported: true`. S2 and S3 use the supported
`/api/*` surface.

## 1. Corrections to the earlier record

- **The 30 s Sync Adapters wait is an 8.18 collector behavior, not a 9.x one.**
  VERIFIED. The 8.18 proxy (`collectorVersion=35` in
  `user/conf/vrops-compatibility.properties`) logs `Did not receive response
  from Controller for 'Sync Adapters' task` exactly 30 s after sending. The
  9.0.2 proxy (`collectorVersion=42`) and the 9.1.1 proxies
  (`collectorVersion=48`) waited 93 s, 135 s, 251 s, 258 s and 426 s for the
  same reply and then loaded the adapters, with no timeout line. Zero timeout
  lines in every retained 9.x proxy log (devel proxies since 11-09, prod
  collector01 since 09-30, 12 syncs). The 11-06 note that the 9.0.2 proxy "got
  its file at ~30 s inside the wait" was an inference; there is no 30 s wait
  there.
- **9.x still has the start race** (lesson mode 1: Start monitoring arrives
  before the jar loads, `Unknown adapter type`, nothing retries). VERIFIED on
  the 9.0.2 proxy 11-07 03:42:42Z and prod collector01 10-14 14:02:05Z.
- **The 8.18 timeout is not `syncAdapterChunksTimeout`.** Both 8.18 and 9.1
  ship `syncAdapterChunksTimeout = 960000` in
  `user/conf/collector/collector.properties`; the 30 s is a separate wait in
  the collector's task layer. Whether it is configurable: not found (the
  constant is not in either copy of `TasksManager.class` on the 8.18 proxy);
  UNVERIFIED.
- **A Suite API source for sync outcome does exist** (section 2, S2), and the
  UI session can read a Cloud Proxy's own `collector.log` (S1). "No endpoint
  reports the loaded version" stays true for the REST API proper.

## 2. Signals: does collector C have kind K loaded at version V?

| # | Signal | How to read it | Versions | Reliability | SSH? |
|---|---|---|---|---|---|
| S1 | Collector log line `'<kind>' adapter version: <v>` (also `Loaded adapter entry class ... of adapter '<kind>'`), printed on every adapter (re)load, at collector start, and daily at 06:00 UTC | UI session, `POST /ui/supportLogs.action` `mainAction=searchLogFileContents`, `instanceId=<collector.nodeIdentifier>`, `logType=COLLECTOR`, `fileName=` (empty = every file of the type) | 8.18.7, 9.0.2, 9.1.1 VERIFIED | **Ground truth.** It is the collector reporting what it loaded. Matched the jar on disk on all 10 collectors today | No |
| S1-neg | Failure lines: `Did not receive response from Controller for 'Sync Adapters'`, `Adapter jar synchronization failed`, `FileNotFoundException: .../plugins/inbound/<kind>.jar`, `Sync adapters 5 attempts failed, terminating process`, `Unknown adapter type ... (Type = <kind>)` | Same call, other search tokens | 8.18 VERIFIED (all five); 9.x VERIFIED for `Unknown adapter type` only (the others did not occur) | Definitive for "not loaded" when no later S1 line follows | No |
| S2 | Collector self-metrics: `Tasks\|ControllerToCollector:Update Adapters\|TasksReceived` and `Tasks\|CollectorToController:Sync Adapters\|ElapsedTime\|Maximum` (ms, 5-minute buckets) | Suite API: the collector's resource (adapter kind `vCenter Operations Adapter`, resource kind `vC-Ops-Collector`, identifier `NODEID` = `collector.nodeIdentifier`), `GET /api/resources/{id}/stats?statKey=...&rollUpType=MAX&intervalType=MINUTES&intervalQuantifier=5&begin=&end=` | Keys present on 8.18.7, 9.0.2, 9.1.1 VERIFIED | **8.18 only:** a bucket with an Update Adapters task and Sync max > 30000 ms means the collector gave up (3 of 3 failures caught: 31,483 / 69,431 / 137,213 ms; 0 false alarms on 2 successes at 26,774 and 28,869 ms). **9.x:** no failure meaning (syncs of up to 426 s succeeded). `Sync Adapters\|Succeeded` reads 1 on failures: useless. Says nothing about the load itself. No data at all while a collector crash-loops (the process exits before it flushes) | No |
| S3 | Adapter instance state of an account of kind K placed on C | `GET /api/adapters?adapterKindKey=<kind>` (`collectorId`), then `GET /api/resources/{id}` `resourceStatusStates[].resourceState` | all VERIFIED | Only exists if an account is on C. FAILED with empty message is ambiguous: start race (jar loaded later) or kind missing. Already used by `account_restart.py` | No |
| S4 | Test connection routed to C | `POST /api/adapters/testConnection` with `collectorId` | spec on all three | On the 8.18 proxy with the kind absent (11-07 03:44:18Z) the collector answered in under 1 ms with empty details and ran no adapter code; normal tests there take 15 to 19 s. **What the API returned to the caller is unknown** (no controller log of it), and the controller created the instance on that collector 1.5 s later. Needs real target identifiers. Not usable as a probe yet | No |
| S5 | Jar on the proxy: `user/plugins/inbound/<kind>.jar` and `<kind>/conf/version.txt` | SSH | all | Truth for presence, not for load (a jar can land after the collector gave up, and an old jar stays put in mode 2). Identical sha256 on node and the three devel proxies today | **Yes** (out of scope for the installer) |

Checked and found **not** to carry per-collector adapter-kind or version
information (VERIFIED live today, not only in the specs):

- `GET /api/collectors`: fields `id, uuId, nodeIdentifier, name, type, state,
  hostName, local, lastHeartbeat, adapterInstanceIds, dataPersistenceEnabled`
  (8.18 has `groupingAllowed` instead). Proxy `type` is `CLOUD_PROXY` on 8.18
  and `UNIFIED_CLOUD_PROXY` on 9.0.2 and 9.1.1: the issue text's
  "CLOUD_PROXY or REMOTE" filter would miss every 9.x proxy. Use
  `local == false`.
- `GET /api/collectors/{id}/adapters`: adapter instances only.
- `/internal/cloudproxies/assignments`, `/{id}/assignments`, `/{id}/logassist/status`
  (9.0 and 9.1 internal specs; 8.18 has only `otk`, `ova`, `{id}` delete):
  resource/service assignments and log assist, nothing about adapters.
- `/ui/cloudProxy.action`: `getCloudProxies` (proxy `version`, `status`,
  `accounts`, `lastSyncTime` which tracks the heartbeat, not the adapter
  sync), `getCloudProxyAdaptersInfo internalId=<collector.id>` (instances and
  their status, the S3 data again), `getCloudProxyStatus proxyId=<sliceId>`
  (`life_status.paks` is the proxy's own upgrade paks, empty here).
- `/ui/clusterManagement.action getSliceAdapters sliceIpAddress=<node>`:
  adapter instances on an analytics node; a proxy address returns `[]`.
- `/ui/dataCollection.action getCollectorDetails`: HTTP 400 for both the
  collector uuid and its resource id; `getCollectionData` gives counts only.
- `/ui/redescribe.action getAdapterInfos`: one row per adapter kind,
  cluster-wide: `adapterName`, `adapterVersion`, `describeVersion`,
  `describeStatus`, `message`. Controller side, not per collector. Useful as
  the **expected version string** (section 5).
- The collector resource's properties (`CollectorLoad|*`,
  `DataPersistence|*`): nothing about adapters.
- `/ui/solution.action getLatestInstalledSolutionStatuses`: empty body at
  rest (already recorded as non-functional on `/ui/`).
- CaSA (`/casa/*`): not probed today. The 2026-04 record covers only its
  node, cluster and pak endpoints; nothing there was looked at for proxy
  adapter data.

### S1 call shape (VERIFIED on all four instances)

Log tree, to find each node's `instanceId` and `sliceRole`:

```
POST /ui/supportLogs.action
  secureToken=<csrf> mainAction=getLogTree node=source groupBy=NODE
-> {"children":[{"instanceId":"<collector.nodeIdentifier>","sliceRole":"MASTER|DATA|CLOUD_PROXY|UNIFIED_CLOUD_PROXY",
                 "children":[{"logType":"COLLECTOR",...}, ...]}, ...]}
```

Every Cloud Proxy appears with one log type, `COLLECTOR`. Its `instanceId` is
the collector's `nodeIdentifier` from `/api/collectors` (8.18: proxy
`3fb4e12a-...`; 9.1 devel: `1cbd15b0-...`; prod: `ade0375d-...`, `c3772533-...`).

Search:

```
POST /ui/supportLogs.action
  secureToken=<csrf> mainAction=searchLogFileContents
  instanceId=<nodeIdentifier> lduId=x logType=COLLECTOR sliceRole=<from tree>
  fileName=            (empty: all files of the type; or collector.log, collector.log.1, ...)
  searchText=<token> isRegExp=false isCaseSense=false useDates=false dateRange=null
  logLevel=TRACE lineLimit=5000 linePosition=1
-> {"fileContent":["[collector.log.1, 21436] 2026-11-11T17:07:15.804Z NOTICE collector ... - 'vcfcf_vsanperf' adapter version: 0.0.0.0.0.24", ...]}
```

Quirks, all VERIFIED:

- `lduId` must be non-empty (any value). Empty gives
  `{"status": "can not request, missing some params"}`; so does a missing
  `logLevel`. `getLogTree` without `groupBy` is HTTP 500.
- With an empty `fileName` each line is prefixed `[<file>, <line>]`; with a
  file named it is `[<line>]`.
- `getLogFileContents` (the non-search read) ignores `searchText`.
- Search on a single token (`logAdapterVersions`, a kind key, a class name)
  was reliable everywhere. Phrases with spaces, quotes or a colon were not:
  `Sync adapters 5 attempts failed` worked on 8.18, `'vcfcf_vsanperf' adapter
  version` worked on 9.1 devel, but `adapter version: 1.0.0.0.0.94` and
  `'vcfcf_compliance' adapter version` returned `[]` on prod although the line
  is in the file. **Search a token and filter client-side.**
- `logAdapterVersions` returns one line per loaded kind per load event (74 to
  4,253 lines per collector here); `lineLimit=5000` covered every collector.
  Paging past `lineLimit` (`linePosition` semantics for search) was not
  tested.
- Works as `admin` (devel instances) and as the factory's `claude` account on
  prod. The privilege it needs (Administration, Support Logs) was not mapped;
  an account without it is the UNVERIFIED path.
- Version format differs by release but matches the Redescribe grid on the
  same instance: 8.18 logs `0.0.0.24`, 9.x logs `0.0.0.0.0.24` (pak 0.0.0.24),
  prod logs `1.0.0.0.0.94` (pak 1.0.0.94). The grid row is the one whose
  `adapterName` equals `GET /api/adapterkinds/{key}`.`name` (equal on all four
  instances).

## 3. What re-triggers the jar sync

| Trigger | Evidence | Can the installer invoke it? |
|---|---|---|
| **Pak install (re-run)**: controller sends `Remove Adapters`, then `Update Adapters` with `[Jar files: {<kind>.jar}]`; the collector then sends `Sync Adapters` and loads | VERIFIED. 8.18 proxy, new kind: build 7 failed 11-07 03:43Z; the next install (build 8) at 04:20Z synced and logged `'vcfcf_vsanperf' adapter version: 0.0.0.8`. The upgrade case was fixed the same way 10-28 (lesson). Each re-run is a fresh try at the same 30 s wait on 8.18: of five vsanperf installs there on 11-07, three timed out: 03:43Z (new kind, nothing loaded) and 08:44Z and 17:20Z (the old 0.0.0.12 kept running, mode 2) | **Yes**: it is the installer's own action. Cost: every account of the pak is stopped by `Remove Adapters` on every collector, and content is re-imported |
| **Collector process start**: startup runs `startSyncAdapters`, which loads every adapter | VERIFIED: 8.18 proxy loaded vsanperf from `Thread-1` at 11-11 04:29:46Z, 05:22:45Z and 08:40:57Z, each after a start. On 8.18 it tries 5 times (30 s wait, 30 s sleep) and on the fifth failure logs `Sync adapters 5 attempts failed, terminating process...`, exits -1, and the service wrapper relaunches it 2 to 5 min later. 13 such self-terminations between 11-10 21:04Z and 11-11 08:34Z, interleaved with 4 restarts the controller requested, while the 8.18 analytics node answered the proxy's heartbeats with HTTP 504 | **No.** No restart action in either Suite API spec or in the 9.1 Cloud Proxy page (its actions: `changeDataPersistence`, `deleteCloudProxy`, `renameCloudProxy`, `getOneTimeKey`, reads). The controller restarts a collector itself when it marks it down (`Controller marked collector as down. Restarting collector`); that is not invokable. And the brief forbids restarts |
| **Redescribe** (Control Panel, Redescribe): `POST /ui/redescribe.action mainAction=start`, progress via `getAdapterInfos` (`isInProgress`) | The action exists (UI bundle, docs: "start the adapter describe process ... after installing or updating an adapter"). The pak's own `post-install` runs `ops-cli.py control redescribe --force` (`../wire-formats/pak_wire_format.md`). Whether a bare redescribe sends `Update Adapters` to collectors: **UNVERIFIED**; no redescribe ran in any retained log | Yes (UI session), but untested. Cluster-wide: describes every adapter, and compliance build 86 notes a redescribe reset costs one metric point. Owner decision before an experiment |
| Proxy re-registration (delete and re-add the Cloud Proxy) | not tested | Destructive. Out of scope |
| Daily 06:00 UTC version log | VERIFIED: a log line only, no `Sync Adapters` task | n/a |
| Anything periodic | VERIFIED absent: after the 11-07 03:43Z failure nothing touched the kind until the next install at 04:20Z | n/a |

Seen in passing (VERIFIED, prod collector01, 22:22 to 22:25Z today, not
caused by this investigation): the controller pushed `CASAdapter.jar` to both
prod proxies; the 9.1.1 proxy waited 93 s for `Sync Adapters`, then reloaded
**every** adapter and re-logged every kind's version, `vcfcf_compliance`
included. Any jar push reloads all adapters on the collector.

## 4. A non-destructive "is K loadable on C" probe

No clean probe exists today.

- **Test connection with `collectorId`** (S4) is the closest. It creates no
  adapter instance (INFERRED from the spec: `POST /api/adapters/testConnection`
  answers with an `adapter-instance` body, and the factory's cert-accept flow
  creates the instance separately with `POST /api/adapters`). But: the only
  recorded case on a collector without the kind returned instantly with no
  error on the collector side and did not stop the caller, so the API answer
  for "kind not loaded" is unknown; and the call needs valid identifiers for
  the kind and would contact the target when the kind is loaded.
  Distinguishing experiment (owner decision, devel only): a test connection
  of a factory kind with an unroutable target (for example `127.0.0.1:9`) on
  a collector that has the kind (expect the adapter's own connection error
  after some seconds) and on one that does not (expect an instant, different
  answer). Not run: the brief forbids test connections.
- **A probe instance** (create, start, read state, delete) works in
  principle but creates a resource, can leave a FAILED instance behind, and
  for the start race reads FAILED even when the jar is about to load. Not
  recommended.
- **S1 is not a probe but answers the question directly** and needs no
  object created. Use it.

## 5. Lab comparison, 2026-11-11 22:00 to 22:30Z

Kind: `vcfcf_vsanperf` 0.0.0.24 on the three devel instances (installed
11-08 15:40 to 16:24Z), `vcfcf_compliance` 1.0.0.94 on prod (installed
10-14). Redescribe grid `adapterVersion`: `0.0.0.0.0.24` (9.0.2, 9.1.1),
`0.0.0.24` (8.18.7), `1.0.0.0.0.94` (prod). Jar sha256 prefix
`4a3917993398bb12`, 176,430 bytes, on the devel analytics node and all three
devel proxies.

| Instance / collector | type | S1 latest version line (via UI) | S2 at the 0.0.0.24 install bucket | S3 account here | Jar on disk (SSH) | Proxy log, last sync outcome (SSH) |
|---|---|---|---|---|---|---|
| devel 9.0.2 / 1 node | INTERNAL | `0.0.0.0.0.24` 11-11 16:53:41Z | not read | none | present (node) | n/a |
| devel 9.0.2 / 2 proxy | UNIFIED_CLOUD_PROXY | `0.0.0.0.0.24` 11-11 16:55:04Z | 11-08 15:44Z: Update 1, Sync max 22,896 ms | `f8ae0aaa` STARTED / DATA_RECEIVING | 176,430, 11-08 15:40Z | last sync 16:52:45Z, reply 135 s later, no timeout |
| devel 8.18 / 1 node | INTERNAL | `0.0.0.24` 11-11 06:00:00Z | not read | `5dbd106b` STARTED / DATA_RECEIVING | not read (no SSH) | n/a |
| devel 8.18 / 2 proxy | CLOUD_PROXY | `0.0.0.24` 11-11 08:40:57Z | 11-08 16:24Z: Update 1, Sync max 26,847 ms | none (vsanperf); `compliance-mgmt` STARTED | 176,430, 11-08 16:20Z | 11-11 08:40:55Z startup sync answered in 27 s on attempt 3 (attempts 1 and 2 timed out), after the restart loop |
| devel 9.1.1 / 1 node | INTERNAL | `0.0.0.0.0.24` 11-11 17:03:30Z | not read | none | not read (no SSH) | n/a |
| devel 9.1.1 / 2 proxy | UNIFIED_CLOUD_PROXY | `0.0.0.0.0.24` 11-11 17:07:15Z | 11-08 16:24 to 16:29Z: Update 1, Sync max 60,755 ms (succeeded) | `15739079` STARTED / DATA_RECEIVING | 176,430, 11-08 16:21Z | 17:00:01Z sync, reply after 426 s, no timeout, loaded |
| prod / 5 node01 | INTERNAL | `1.0.0.0.0.94` 22:22:54Z | not read | none | SSH closed | n/a |
| prod / 6 node02 | INTERNAL | `1.0.0.0.0.94` 22:22:53Z | not read | none | SSH closed | n/a |
| prod / 3 collector01 | UNIFIED_CLOUD_PROXY | `1.0.0.0.0.94` 22:24:55Z | not read | none | 166,246, 10-14 | 22:23:02Z sync (CASAdapter push), reply 93 s, loaded all |
| prod / 4 collector02 | UNIFIED_CLOUD_PROXY | `1.0.0.0.0.94` 22:25:03Z | not read | 3 accounts STARTED / DATA_RECEIVING | 166,246, 10-14 | same push, loaded |

Signal against truth: S1 agreed with the jar and the proxy log on every
collector. S2 on 8.18 flagged exactly the three 11-07 failures and nothing
else. On the 9.x proxies 10 of 14 install-time syncs since 11-07 read over
30,000 ms (up to 209,515 ms; startup syncs up to 426,352 ms) and the jar
landed for every install, so it must not be read as failure there. S3 is green everywhere today and was FAILED for
both the start race (recovered) and the missing kind (did not), so it cannot
tell them apart.

Environment finding (not #314, VERIFIED): the 8.18 analytics node answered
the proxy with HTTP 504 Gateway Timeout on heartbeats and data on 11-10 and
11-11, which is what made the 8.18 syncs slow and drove the 12-hour restart
loop. The 9.1 devel proxy shows 96 % memory used in `getCloudProxies`.

## 6. Proposed installer design (for `tooling`)

A new post-install step, **per-collector load verification**, after the
existing "pak registered at the expected version" verify and **before** the
account start watch in `account_restart.py`.

**Inputs.** The pak's `adapter_kinds` (already read), the install start time
(UTC, taken just before the upload), the `/ui` session the installer already
holds, the Suite API client.

**Expected version.** Per kind: `GET /api/adapterkinds/{key}` `name`; then
`POST /ui/redescribe.action mainAction=getAdapterInfos`, the row with
`adapterName == name`, its `adapterVersion` (VERIFIED equal to what every
collector logs on the same instance). If the row is missing or
`describeStatus != SUCCESS`, the expected version is unknown and every
collector is UNVERIFIED for that kind.

**Collectors.** `GET /api/collectors`: every collector with `local == false`
(remote and Cloud Proxy, any `type` string) **and** every `INTERNAL` one (one
per analytics node; prod has two). Skip `state != UP` as UNVERIFIED (down).
Map each to the log tree by `instanceId == nodeIdentifier` (one `getLogTree`
call, which also gives `sliceRole`).

**Poll.** Every 30 s, per collector not yet decided, `searchLogFileContents`
with `fileName=` (all files) for each of these single tokens, every result
filtered client-side to lines stamped at or after (install start minus 60 s):

- `logAdapterVersions` → lines `'<kind>' adapter version: <v>`.
- the kind key → `Unknown adapter type ... (Type = <kind>)`,
  `FileNotFoundException: .../<kind>.jar`.
- `syncAdapterJars` and `startSyncAdapters` → `Adapter jar synchronization
  failed`, `Failed to send sync adapters task`, `Sync adapters 5 attempts
  failed` (8.18 class names; these lines carry no kind, so attribute them to
  the install only when they fall between this install's `Update Adapters`
  line for `<kind>.jar` and the next load).

Per collector the verdict is the latest event:

| Latest event after install start | Verdict |
|---|---|
| version line, `v == expected` | **LOADED** `<v>` at `<ts>` |
| version line, `v != expected` | **STALE** (old version running: lesson mode 2) |
| a sync-failure or missing-jar line, and no version line after it | **NOT LOADED** (quote the line) |
| nothing yet | PENDING, keep polling |

Deadline per attempt: 600 s (INFERRED bound: the slowest observed sync reply
was 426 s on 9.1.1 plus a few seconds to load; on 8.18 the outcome is known
within 60 s of the `Update Adapters` task). On deadline a PENDING collector is
**UNVERIFIED (no load line within 600 s)**, not NOT LOADED.

**Retry.** If any collector is NOT LOADED or STALE: re-run the install of the
same pak file (the one trigger proven to re-sync), then verify only those
collectors again. At most 2 re-runs (3 attempts), owner to confirm the
number. Never re-run for UNVERIFIED alone (no evidence of failure, and a
re-run stops every account of the pak). Then run the existing account watch,
but do not send Start monitoring to accounts on a collector whose final
verdict is NOT LOADED or STALE (a start there either fails again or runs the
old jar); report them instead.

**Report**, one line per collector, then a summary:

```
COLLECTOR vcf-lab-operations-devel-8-collector (id 2, CLOUD_PROXY): vcfcf_vsanperf LOADED 0.0.0.24 at 2026-11-08T16:20:24Z (attempt 1)
COLLECTOR ... : vcfcf_vsanperf NOT LOADED after 3 attempts: "Did not receive response from Controller for 'Sync Adapters' task" at ...
COLLECTOR ... : vcfcf_vsanperf UNVERIFIED (Support Logs not readable: HTTP 403)
```

Success (exit 0) only when every collector in scope is LOADED for every kind.
Any NOT LOADED or STALE: a distinct non-zero exit ("installed, not loaded on
N collectors: re-run or see the collector log"). Any UNVERIFIED and no
failure: its own exit code and an `UNVERIFIED` summary line, never the
success line. Exit code values are an owner decision; the existing `3` means
"installed, post-install check failed: do not reinstall", which is the wrong
advice for NOT LOADED.

**Degradation.**

1. Support Logs unreadable (UI login fails, HTTP 403, a non-JSON body, or
   the `missing some params` status after the documented parameters): fall
   back to S2 for that collector. Find its resource (kind `vC-Ops-Collector`,
   `NODEID == nodeIdentifier`), read the two keys for the buckets from the
   install start onward. On **8.18** (`/api/versions/current` `releaseName`
   starts `VMware Aria Operations 8.`): a bucket with `Update Adapters
   TasksReceived > 0` whose `Sync Adapters ElapsedTime Maximum > 30000` is
   NOT LOADED (sync failed); `<= 30000` is **UNVERIFIED (sync answered in
   time; load not observable)**. On **9.x**: S2 can only yield UNVERIFIED. No
   bucket at all within 15 min (5-minute rollups; publication delay not
   measured): UNVERIFIED. The retry rule applies to an S2 NOT LOADED as well.
2. Collector resource missing too: UNVERIFIED.
3. Never infer LOADED from `Sync Adapters|Succeeded`, from `Update Adapters`
   succeeding, from `/api/solutions`, from the Redescribe grid, or from an
   account reading STARTED (mode 2 runs the old jar and reads STARTED).

**Must not.** Restart, reboot or re-register a collector or proxy; call
`redescribe.action mainAction=start` (until an owner-approved devel
experiment shows what it does to collectors); issue test connections or
create probe instances; SSH anywhere; treat a missing log line as success.

**Cost.** Per poll per collector, two to four Support Logs searches; one
`logAdapterVersions` search returned up to 4,253 lines on the prod data
node (body size not measured). Polling every 30 s for 10 min across 4 collectors is about
300 calls in the worst case. Ask for `lineLimit` just large enough and stop
polling a collector once decided.

## 7. Owner decisions

1. Retry bound (proposed 2 re-runs) and whether a re-run is automatic or
   behind a flag, given it stops every account of the pak on every
   collector each time.
2. Exit codes for NOT LOADED / STALE and for UNVERIFIED.
3. Whether to scope `INTERNAL` collectors (always LOADED in this lab; adds
   calls) or only `local == false`.
4. Whether to run the Redescribe experiment on devel to learn if it
   re-syncs proxies (a lighter retry than a reinstall), and the S4
   test-connection discrimination experiment.
5. The lesson file `knowledge/lessons/remote-collector-upgrade-start-race.md`
   says the third mode's 30 s wait applies to "the Cloud Proxy" in general;
   it should say 8.18 collectors (protocol 35). Lessons are outside this
   agent's write scope.

## 8. Open questions

- Whether the 8.18 30 s wait is configurable (not found).
- `searchLogFileContents` paging (`linePosition`) and why phrase searches
  fail on prod; and which privilege Support Logs needs.
- How soon after a sync the collector's self-metrics bucket is readable
  (S2 latency).
- Whether 9.x has any failure mode for the sync other than the start race;
  none was seen.
