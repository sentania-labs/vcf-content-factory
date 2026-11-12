# devel_9_1: UI content import skipped a nonexistent dashboard; Suite API 503 "Gemfire"

SSH investigation on `vcf-lab-operations-devel-91` (VCF Operations 9.1.1.0, single
node, analytics pid 5695 up since 2026-10-29), 2026-11-11 around 09:20 to 10:05
America/Chicago. Root over SSH with the `devel_9_1` profile password piped through
`sshpass -e` (never on argv, never printed; key auth was refused). Q1 and Q2 were
read-only. Q3 made one authorized write: a single dashboard was imported through the UI
path and left in place (§Q3, §Clean-up). Two scp pulls to the session scratchpad for local
`javap`: `controller/plugins/vcops-view-server-1.0-SNAPSHOT.jar` (Q1) and
`vcops-bridge-server-1.0-SNAPSHOT.jar` (Q3). Neither jar is in the repo and no vendor code
is quoted here. Nothing was changed, restarted or deleted on the host.

**Local-only artifact; not reproducible from a clone (RULE-015).** The two jars and their
`javap` dumps are Broadcom material. They existed only in that session's scratchpad and
were not kept. The findings are summarized here in full, so you do not need the citation
to follow them. Anyone with an appliance of 9.1.1 Build 25794169 can re-derive them:
`javap -p -c -constants` of
`com.vmware.vcops.bridge.plugin.server.BackupRestoreManagerDistributedTask` in
`/usr/lib/vmware-vcops/controller/plugins/vcops-view-server-1.0-SNAPSHOT.jar`, and of
`com.vmware.vcops.bridge.server.DashboardImporter` in the appliance's
`vcops-bridge-server-1.0-SNAPSHOT.jar`. The log files are named where they are quoted. The
9.0.2 counterpart of the Q1 evidence is kept on the holding share (see
`2026-11-11-owner-mapping-dashboard-skip-reproduction.md`).

The bundle under test came from a customer. Customer-identifying strings (AD domain, LDAP
host, user names, the customer's dashboard, widget, group and resource-kind names, and
the adapter kinds the bundle referenced) are generalized below.
All log timestamps are UTC unless marked CST; access-log and catalina files on this
appliance print local (CST) time even where they carry a `Z`.

## Q1. Why the UI import skipped a dashboard that did not exist

### Answer

The skip is decided in the content restore task, before the dashboard importer is ever
called. `restoreData` first runs `importAndReassignUserMappings` over `usermappings.json`.
That step maps each bundle owner to a target user. For a user carrying a `userSourceId`
whose source is `ACTIVE_DIRECTORY` (also `OPEN_LDAP`, `OTHER`), the source is resolved only
if the target has an LDAP auth source with the same host, port and base DN. The lab has no
such source, so the owner maps to nothing. The returned map is empty, and the task logs
`failed to import User Mappings`. It then walks `dashboards/<ownerId>` files: an owner with
no mapping goes straight to the skip branch. That branch adds the owner's count from
`configuration.json` `dashboardsByOwner` to the skipped tally, logs `failed to map
Dashboard`, and never calls `importDashboard`. The same thing happens to
`dashboardsharings/<ownerId>`.

This confirms Scott's hypothesis. The owner is not missing so much as unmappable:
it is tied to an AD source that cannot be matched on the target. Nothing about resources,
resource kinds, sharing groups, `homeTab`, name collision or interruption is involved. The
dashboard section took 2 ms and the task ran to completion.

It is deterministic. Any target without an LDAP source matching that exact
host/port/baseDN will skip it. A target with the source configured but the user not
present skips too, because sourced users are then matched by `userName` against the
target's user list. That was inferred here and has since been run on 9.0.2 (run F1 in
`2026-11-11-owner-mapping-dashboard-skip-reproduction.md`; F2 shows the matching source
plus an existing name mapping).

### Decisive log lines (verbatim, owner UUID generalized)

`/storage/log/vcops/log/view-bridge-970cb2ff-24af-41a9-8bfc-fab7a2c549c7.log`, thread
`DistTaskBackupRestoreManagerDistributedTask` (threadId 723764), logger
`com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData`:

```
2026-11-11T14:55:59.651Z INFO  ... BackupRestoreManager.importContentData] - content import called
2026-11-11T14:55:59.838Z INFO  ... restoreData] - restoreData: Views import started...
2026-11-11T14:56:14.241Z INFO  ... restoreData] - restoreData: User Mappings import started...
2026-11-11T14:56:14.343Z ERROR ... restoreData] - restoreData failed to import User Mappings.
2026-11-11T14:56:14.344Z INFO  ... restoreData] - restoreData: Dashboards import started...
2026-11-11T14:56:14.345Z ERROR ... restoreData] - restoreData failed to map Dashboard. File: <owner-uuid>
2026-11-11T14:56:14.346Z INFO  ... restoreData] - restoreData: Dashboard Sharings import started...
2026-11-11T14:56:14.346Z ERROR ... restoreData] - restoreData failed to map Dashboard. File: <owner-uuid>
2026-11-11T14:56:14.938Z INFO  ... restoreData] - restoreData: Super Metrics import started...
2026-11-11T14:56:16.566Z INFO  ... restoreData] - restoreData: Custom Groups import started...
2026-11-11T14:58:01.514Z INFO  ... BackupRestoreManager.run] - BackupRestoreManagerDistributedTask finished in 121853ms.
```

Contrast, same file, earlier factory imports (owner source-less `admin`): `User Mappings
import started...` is followed 20 ms later by `Dashboards import started...` with no error,
and `Dashboard Sharings import passed` (2026-10-26T13:35:34Z, 13:36:33Z, 2026-10-28T21:12:29Z).

The UI request was `POST /vcf-operations/plug/ops/contentManagement.action?mainAction=restoreContentData&&override=true&&encryptionKey=`
at 08:55:59 CST (`product-ui/localhost_access_log.2026-11-11.txt`). That makes it an
overwrite import, so create-only mode (the cause reproduced in
`../api-surface/content_import_skip_semantics.md`) is ruled out.

The audit log (`analytics.audit-*.log`) agrees. Thread 723764 has `VIEW_DEFINITION.IMPORT`
success (14:56:13.676Z, 4 IDs), `SUPER_METRIC.IMPORT` success (14:56:16.548Z, 5 IDs) and
`CUSTOM_GROUP.IMPORT` success (14:58:01.410Z, 4 IDs). It has **no** `DASHBOARD.IMPORT` entry,
so the dashboard importer was never invoked. (The `DASHBOARD.IMPORT` plus `DASHBOARD.DELETE
3d84205c-...` pairs from `maintenanceAdmin` at 14:53:42Z and 15:02:19Z come with each UI
login and have nothing to do with this import.)

The reason is logged at the current level, but only as the two ERROR lines above. The
helper's own reasons (`failed to get target system users`, `failed to get target
AuthSources`, or an exception message) did not appear, which fits the path where the
helper runs cleanly and simply finds no mapping. Raising
`com.vmware.vcops.bridge.plugin.server.BackupRestoreManager` (view-bridge logger, analytics
JVM) to DEBUG would not add a per-user reason; the bytecode has no per-user log call.

### Supporting bytecode (javap of `BackupRestoreManagerDistributedTask`, 9.1.1.0)

Method and string-constant evidence only, described in prose:

- `restoreData(RestoreContentParam)` reads `usermappings.json` and calls
  `importAndReassignUserMappings(byte[], String, String)`. A null or empty returned map
  logs the constant `restoreData failed to import User Mappings.` and the code carries on.
- `importAndReassignUserMappings` loads target users (`getAllUsers`) and auth sources, then
  goes through `sources[]` by `sourceType`. `ACTIVE_DIRECTORY` / `OPEN_LDAP` / `OTHER` are
  matched against `getAllAvailableLdapHosts()` on host (case-insensitive), port and base DN
  (`sourceDomain`). `SSO_SAML`, `VIDM` and `VC` sources have their own matchers. In
  `users[]`, a user with **no** `userSourceId` maps either through an id comparison or by
  case-insensitive `userName` against target users. Correction from the 9.0.2
  reproduction (`2026-11-11-owner-mapping-dashboard-skip-reproduction.md`): this note
  first said the comparison was against `getAdminUserId()`. It is against the content of
  the bundle's marker file, and `getAdminUserId()` is the result. That was run and read on
  9.0.2 and not re-read here on 9.1.1. A user
  **with** a `userSourceId` maps only when its source was resolved; then it too matches by
  `userName`. There is no fallback to the importing user.
- The dashboards loop takes each file in `dashboards/`, looks up the file name (the owner
  id) in that map, and on null or empty jumps to a branch that reads
  `backupConfigurationDTO.dashboards[owner]` (from `configuration.json`), adds it to the
  skipped count and logs the constant `restoreData failed to map Dashboard. File: %s`.
  `importDashboard(byte[], boolean, String, boolean, boolean)` sits on the other branch
  only.

This also explains the earlier test G1 in `content_import_skip_semantics.md`, where a bogus
owner did not skip. The factory packager (`src/vcfcf_core/dashboards/packager.py`) writes
the owner id into the marker file as well as into `usermappings.json`. So a bogus owner id
still equals the marker content, and the owner maps to the target admin through the
marker shortcut, whatever its `userName`. The name is not what resolves it: the sync
handler and the installer can write other names. D against D2 in the reproduction note
shows this.

### Custom Groups, views, super metrics

- Custom Groups **completed**: `CUSTOM_GROUP.IMPORT result="success"` at 14:58:01.410Z (4
  groups), task finished at 14:58:01.514Z. The phase took about 1 m 45 s. Most of that time
  went on creating new Container resource kinds for the customer's group types
  (`AdapterKindDescribeDataServiceSqlImpl.addNewResourceKinds` at 14:56:19Z, 14:57:18Z,
  14:57:33Z, 14:57:39Z and 14:57:44Z, five customer-named kinds), all on the import thread.
  The UI had stopped polling at 08:58:04 CST, three seconds after completion, so the
  spinner in the screenshot was a stale view. Nothing hung.
- Views (4) and super metrics (5) landed, per the audit success lines above. Not
  re-verified by API read-back because the Suite API was returning 503 (Q2).
- Side effect worth knowing: the custom group import registered five new Container
  resource kinds named after the customer's group types. They outlive any deletion of the
  groups, but are removable one by one with
  `DELETE /api/resources/groups/types/<key>` (done on devel_9_1 2026-11-11, all five).

## Q2. Why the Suite API returns 503 "Gemfire" while the UI works

### Answer

The GemFire cluster on this single node is **split-brained**. The locator JVM (pid 3280)
stalled for about 225 s. The analytics member (pid 5695, which also hosts the cache server)
removed it from the view at 2026-11-11T03:37:20Z (21:37 CST Nov 10). The locator
force-disconnected, restarted itself, and "reconnected" at 03:57:41Z into a **one-member
view of its own**. Since then it has ignored the analytics view every minute ("not in my
current view", 704 times so far). So the locator knows of no cache server.

Any client that bootstraps through the locator gets `No servers are available`. The Suite
API JVM was restarted by the watchdog at 04:12Z (22:12 CST): it had first timed out on
`/suite-api/api/deployment/node/services/api/info`. A fresh API JVM must ask the locator for
servers. It has failed every request since it came up, answering 503 "Gemfire" from
22:37 CST on Nov 10. The collector JVM, also restarted at 22:23:57 CST, fails its heartbeat
the same way (`RelayInterface.heartbeat : No servers available`), and analytics logs
`Collector (ID = 1) is not able to handle tasks`. **Local data collection is down too.**

The UI keeps working because the UI JVM (pid 1426, up since Oct 29) and analytics were
never restarted. Inferred, not proven: the UI's client pool still holds the analytics
cache-server endpoint it learned before the split, so it never has to ask the locator.

The import has nothing to do with it. The split happened about 11 h 20 m before the import,
and the 503s were constant for about 10 h before it.

Probable root cause: memory starvation. The node has 7.9 GB RAM and 2 vCPU. At read time
it had 127 MB free and 1 GB of swap in use, and both GemFire JVMs log repeated JVM-pause and
thread-monitor warnings. The 225 s locator pause sits inside that pattern. The trigger of
that particular pause is not established.

### Decisive lines (verbatim)

`gemfire-locator.log`:

```
2026-11-11T03:37:11.836Z WARN gemfire-locator 3280 [...StatSampler...] ... - Statistics sampling thread detected a JVM pause with a wakeup delay of 225346 ms. This indicates that the Java thread scheduler is overwhelmed. ...
2026-11-11T03:37:28.938Z FATAL gemfire-locator 3280 [...] ... processInstallViewMessage] - This member is no longer in the membership view.  My ID is 172.27.10.10(3280:locator)<ec><v0>:20006 ...
2026-11-11T03:57:41.319Z INFO gemfire-locator 3280 [...] ... InternalDistributedSystem.reconnect] - Reconnect completed.
2026-11-11T15:37:30.449Z INFO gemfire-locator 3280 [...] ... processInstallViewMessage] - Ignoring the view View[172.27.10.10(VCF Ops Analytics-...:5695)<ec><v1>:10005|10] members: [...:5695 ...{lead}]  crashed: [172.27.10.10(3280:locator)<ec><v9>:20006] from member ...:5695 ..., which is not in my current view View[172.27.10.10(3280:locator)<ec><v0>:20006|0] members: [172.27.10.10(3280:locator)<ec><v0>:20006]
```

`gemfire_vRealize Ops Analytics_970cb2ff_....log`:

```
2026-11-11T03:36:38.771Z INFO ... inlineCheckIfAvailable] - Requesting removal of suspect member 172.27.10.10(3280:locator)<ec><v0>:20006
2026-11-11T03:37:22.652Z INFO ... received new view: View[...:5695)<ec><v1>:10005|8] members: [...:5695 ...{lead}]  crashed: [172.27.10.10(3280:locator)<ec><v0>:20006]
2026-11-11T03:43:35.392Z INFO ... received new view: View[...:5695)<ec><v1>:10005|10] members: [...:5695 ...{lead}]  crashed: [172.27.10.10(3280:locator)<ec><v9>:20006]
```

`api.log` (pid 1469587, the restarted API JVM), repeating:

```
ERROR api 1469587 [...] [platform.api.PlatformExecutor.<init>] - Failed to create PlatformExecutor: PlatformException: Could not connect to cluster: No servers are available.
WARN  api 1469587 [...] [client.internal.QueueManagerImpl.initializeConnections] - Could not create a queue. No queue servers available.
```

`vcops-watchdog/vcops-watchdog.log`:

```
2026-11-11T04:12:16.164Z INFO ... checkUrl - 1439] - Retries exceeded, an error was found checking content for url: Api Service
2026-11-11T04:12:16.307Z INFO ... takeActionOnService - 1081] - Taking action on service 'api'
```

Since then each 5-minute watchdog run logs `503 ... auth/token/acquire` and exits code 1
(`vcops-watchdog-daemon.log`: `Watchdog exited with unexpected code: 1`).

`suite-api/localhost_access_log.txt` (CST): 0 to 4 stray 503s per hour on Nov 10 until
22:13 CST. No traffic during the 22:14 to 22:37 restart. From 22:37 CST it is about 430 to
475 503s per hour against about 11 to 13 200s per hour.
`suite-api/catalina.2026-11-10.log` shows the stop at 22:14:49 and the redeploy at 22:25 to
22:34 CST. There was an earlier stop and start at 14:05 to 14:15 CST on Nov 10, while the
cluster was still whole, and the API recovered from that one, which fits "worked on the
afternoon of Nov 10".

### Verified vs inferred

- Verified from logs: the locator pause and its removal at 03:37Z; its solo reconnect at
  03:57Z, still ongoing at 15:37Z; the API JVM restart by the watchdog; the API's and the
  collector's `No servers available`; the import timing.
- Inferred: that the UI survives on a pre-split pool to the analytics cache server; that
  memory pressure caused the pause.
- Not done (diagnose-only brief): any restart. Recovery would most likely need the GemFire
  locator and analytics to rejoin one view, for example a cluster take-offline and
  bring-online from the admin UI. Restarting the API JVM alone will not help while the
  locator holds no servers.

## Confirming experiments

- **Q1**: run on 9.0.2 with factory probe content through the Suite API, not with this
  bundle through the UI (`2026-11-11-owner-mapping-dashboard-skip-reproduction.md`):
  - Editing `usermappings.json` alone to the source-less `admin` shape fixes the skip
    (run E).
  - An owner tied to a source that does match maps only if the name exists (F2 against
    F1). That used the lab's existing AD source, not a newly added one.
  - Still not run: the same edits on 9.1.1, and through the UI.
- **Q2**: a read-only `gfsh` session against the locator (`connect --locator=172.27.10.10[6061]`,
  `list members`) should list the locator alone with no analytics server. Alternatively,
  read the locator's server list from its JMX manager.

## Implications

- Third-party and customer bundles exported from an AD-, SSO- or vIDM-backed instance will
  silently skip every dashboard owned by a directory user on any instance that lacks the
  identical auth source. The UI shows this as "skipped", with no failure. Our extractor and
  any bundle migrator should rewrite `usermappings.json` to the source-less `admin` shape
  before shipping. Renaming `dashboards/<owner>`, `dashboardsharings/<owner>` and
  `configuration.json` `dashboardsByOwner` is not needed: run E in the reproduction note
  kept the original owner id everywhere and imported.
- `content_import_skip_semantics.md` now records this as its second demonstrated skip
  cause. It was observed under `override=true` here and `force=true` on 9.0.2. That it is
  independent of `force` is inferred from bytecode, not run.
- A 503 `Service "Gemfire" is not available` on this node is a cluster-membership failure.
  It is not an API fault, and waiting 5 minutes will not clear it.

## Q3. Hand import of the same dashboard: why it stays "configuring"

Added 2026-11-11 around 09:55 to 10:05 CST. Scott authorized one write: importing the
customer's single-dashboard zip unmodified as the lab `admin`. That zip is the nested
`dashboards/<owner-uuid>` file of the bundle, holding `dashboard/dashboard.json` and
`dashboard/resources/*.properties`. The import is left in place for Scott:

- **id `1a020f53-535b-41b3-915a-909c080a3c30`**, the customer's dashboard. Owner after import: `admin` (`33ebfccb-...`). Remove it later.

### How it was imported (the real Manage > Import path)

The dialog on 9.1.1 is the ExtJS `Ext.vcops.dashboard.UploadFileWindow`
(`/usr/lib/vmware-vcops/tomcat-web-app/webapps/ui/js/dashboard/UploadFileWindow.js`). It
makes two calls:

1. `POST /ui/utility.action` with `mainAction=prepareFileUpload`.
2. A multipart `POST /ui/dashboard.action?mainAction=uploadDashboard`, file field
   **`dashboardConfigFile`**, form field `override` (`false` unless "overwrite" is chosen;
   the default radio is "rename").

I replayed both in a UI session (`VCFOpsUIClient`, password from the profile, never on argv).
It worked on the first attempt: `prepare 200 {"success":true}`, then
`upload 200 {"success":true,"status": true, "msg":"success"}` at 15:58:49Z.

This qualifies `../api-surface/struts_import_endpoints.md`, which calls `uploadDashboard` a
dead stub on 9.0.2. It works on 9.1.1; it was not re-tested on 9.0.2. Several things
differ from the old probes: the build, the `prepareFileUpload` call before the upload, and
the field name. The only record of the field names those probes tried is the appendix of
`../wire-formats/ui_import_formats.md`, and `dashboardConfigFile` is not among them. That
record does not say whether `prepareFileUpload` was called. Nothing isolated which of
these differences matters.

### What happened

- Phase 1 landed synchronously. `analytics.audit-*.log` shows `DASHBOARD.IMPORT` (admin,
  15:58:44.507Z) and `DASHBOARD.ADD_TAB ... Adding tab(s). Name(s): "<dashboard name>"`
  (15:58:48.518Z).
- At 15:58:59Z, `getDashboardList` showed it with `isLoading: true`, owner `admin`.
  `getDashboardList` on 9.1.1 does not expose `importComplete` or `importAttempts`.
  `isLoading` is their UI-side proxy (see `../api-surface/dashboard_import_two_phase_materialization.md`).
- Phase 2 ran one pass immediately, at 15:58:49.494 to .568Z, on `DashboardImporter` thread
  `Thread-187363`. Seven of 13 widgets resolved. **Six stayed parked, each waiting on one of
  the five custom groups that do not exist here.**
- The observation window was cut short. At 15:59:15Z a root SSH login with **password**
  auth from this workstation (my sessions use keyboard-interactive) ran the watchdog
  `--disable` for `api`, then a full `vmware-vcops` stop. Analytics GemFire shut down at
  16:00:12 to 16:00:20Z and `vmware-vcops.service` was deactivated at 16:01:09Z. As of
  10:03 CST nothing was running. That was not this agent, and I did not restart anything.
  From 16:00:23Z the UI logged `No servers available` and then
  `Unable to connect to any locators`, and UI login loops on redirects. So I did not
  observe the 10-minute repeat pass, and I did not open the dashboard in a browser.

### Decisive lines

`vcops-bridge-970cb2ff-24af-41a9-8bfc-fab7a2c549c7.log`, logger
`com.vmware.vcops.bridge.server.DashboardImporter.processDashboardsImport`, thread
`Thread-187363`. The dashboard name, widget titles and group names are replaced by generic
descriptions in angle brackets; everything else is verbatim:

```
2026-11-11T15:58:49.494Z INFO  ... keysByEntryType = {resource=[{"resourceKindKey":"Environment",...  (all 80 entries)
2026-11-11T15:58:49.510Z INFO  ... internalIdToTransferredIdMap = {resourceKind:id:1_::_=002006VMWA...  (20 resolved)
2026-11-11T15:58:49.518Z ERROR ... Dashboard Import: [ResourceImportExportDTO [toJson()={...}, getId()=null, isEntityFound()=false, getErrorMessage()=null], ...]  (60 not found)
2026-11-11T15:58:49.519Z INFO  ... Dashboard Import: Entry info didn't found for dashboard: <dashboard name>, widget: <a vCenter compliance scoreboard>, entry: {"resourceKindKey":"Environment","internalId":"resource:id:1_::_","adapterKindKey":"Container","identifiers":[],"name":"<vCenter version group 1>"}
2026-11-11T15:58:49.520Z INFO  ... widget: <a vCenter compliance scoreboard>, entry: {... "internalId":"resource:id:2_::_" ... "name":"<vCenter version group 2>"}
2026-11-11T15:58:49.544Z INFO  ... widget: <an ESXi host compliance scoreboard>, entry: {... "internalId":"resource:id:37_::_" ... "name":"<ESXi host group 1>"}
2026-11-11T15:58:49.544Z INFO  ... widget: <an ESXi host compliance scoreboard>, entry: {... "internalId":"resource:id:4_::_" ... "name":"<ESXi host group 2>"}
2026-11-11T15:58:49.550Z INFO  ... widget: <an ESXi non-compliant builds view>, entry: {... "resource:id:4_::_" ...}
2026-11-11T15:58:49.557Z INFO  ... widget: <a non-compliant vCenters view>, entry: {... "resource:id:2_::_" ...}
2026-11-11T15:58:49.563Z INFO  ... widget: <a second ESXi non-compliant builds view>, entry: {... "resource:id:4_::_" ...}
2026-11-11T15:58:49.568Z INFO  ... widget: <a second ESXi host compliance scoreboard>, entry: {... "internalId":"resource:id:9_::_" ... "name":"<ESXi host group 3>"}
```

### The candidates, from the evidence

Breakdown of that pass, computed from the logged maps against the zip's `entries` and widget
configs:

| | total | resolved | not found |
|---|---|---|---|
| `entries.resource` | 60 | 6 | 54 (53 Container, 1 VMWARE) |
| `entries.resourceKind` | 20 | 14 | 6 (2 each for three third-party storage adapter kinds not installed in the lab) |
| internalIds referenced by widget configs | 13 | 8 | **5, all Container/Environment custom groups** |

- **Unused entries do not block.** 55 unresolved entries that no widget references
  (including all six adapter-kind entries) produce only the one ERROR summary line. None of
  them appears in an "Entry info didn't found" line, and the seven widgets that do not
  reference the five groups were not reported as blocked. That includes the 4 groups
  imported this morning, which resolved, and the View and TextDisplay widgets.
- **The used-and-missing custom groups block.** The five groups not shipped in the bundle
  are exactly the five "didn't found" entries, across six widgets. The customer-named group
  *types* resolved here only because this morning's custom group import registered them as
  Container kinds. On the customer's own instance they exist anyway.
- **Owner, sharing group, `homeTab`, name collision:** not involved. The dashboard landed,
  owned by the importer.
- **Degraded instance (GemFire split, collector down):** ruled out as the cause. The pass
  ran inside analytics, called `fromEntryKeys`, and resolved 20 entries, including the four
  custom groups that exist. It failed only on objects that do not exist. A missing group is
  a name lookup that returns nothing on any instance, healthy or not. A healthy-instance
  repeat would add nothing to the mechanism; it would only confirm the observed behaviour
  over time.

### Completion condition and retry (bytecode, 9.1.1 `vcops-bridge-server-1.0-SNAPSHOT.jar`)

Method and constant evidence only; no code copied. Same shape as the 9.0.2 analysis in
`2026-10-13-dashboard-import-deferral-trigger.md`:

- `processDashboardsImport` collects each incomplete tab's `entryKeys` and calls
  `ImportExportManager.fromEntryKeys`, logging the `keysByEntryType`,
  `internalIdToTransferredIdMap` and not-found lines above. For each widget with a
  `configKey`, it string-replaces the resolved internalIds. Then, for every unresolved
  internalId **contained in that widget's configKey**, it logs
  `Dashboard Import: Entry info didn't found for dashboard: %s, widget: %s, entry: %s`,
  leaves the widget parked and writes a `WidgetImportErrorMap` under the global key
  `DashboardImportErrorMap`. Fully resolved widgets get `setConfig` and `setConfigKey(null)`
  (they render). The tab gets `setImportComplete(true)` and `setEntryKeys(null)` only when
  every widget resolved.
- `run()`: one thread per user. After a pass, the thread exits if everything transferred,
  or if `newDashboardCreated` is false, or if `restoreAttempts == 144`. Otherwise it
  increments `restoreAttempts` and sleeps `600000` ms. So passes are every 10 minutes for up
  to 24 h, and `update()` on a new import resets the counter.
- There is no give-up state on the dashboard itself. After 144 passes the thread stops,
  and the tab stays `importComplete=false`, `isLoading=true`, until something starts
  another pass (next bullet). What persists is the cause, the missing groups, not the
  stop.
- Extra passes come from any later dashboard import for the same user. On this appliance
  every UI login also triggers two `maintenanceAdmin` `DASHBOARD.IMPORT` audit lines and a
  `DashboardImporter` pass (14:53, 15:02, 15:57 and 15:58Z today). That re-tries the parked
  admin dashboards, which is why the four stuck chargeback/showback dashboards log the same
  lines at every login.

Conclusion (verified for one pass from logs, completion rule from bytecode): the dashboard
stays "configuring" because six widgets reference five custom groups that do not exist on
the target. It will never complete until objects with those exact names exist. The 24-hour
retry window does not change that.

### Paste-ready strings (KB / support search)

Content Management import, owner mapping (Q1). Logger
`com.vmware.vcops.bridge.plugin.server.BackupRestoreManager` (file
`view-bridge-<node-uuid>.log`). Class `BackupRestoreManagerDistributedTask`, methods
`restoreData`, `importAndReassignUserMappings`:

```
restoreData failed to import User Mappings.
restoreData failed to map Dashboard. File: <owner-uuid>
importAndReassignUserMappings  failed to get target system users
importAndReassignUserMappings  failed to get target AuthSources
restoreData: User Mappings skipped...
```

Single-dashboard import, phase 2 (Q3). Logger
`com.vmware.vcops.bridge.server.DashboardImporter` (file `vcops-bridge-<node-uuid>.log`),
method `processDashboardsImport`:

```
Dashboard Import: Entry info didn't found for dashboard: <name>, widget: <title>, entry: {...}
Dashboard Import: [ResourceImportExportDTO [toJson()={...}, getId()=null, isEntityFound()=false, getErrorMessage()=null]]
Dashboard Import: dataRetriever.fromEntryKeys returned different result than requested. Requested entries count = N, returned count = M.
keysByEntryType = {...}
internalIdToTransferredIdMap = {...}
```

The global KV key holding per-widget failures is `DashboardImportErrorMap`
(`WidgetImportErrorMap`).

### Customer fix or workaround (hypotheses, not tested)

1. **Create or import the five missing custom groups first, with the exact names**: the two
   vCenter version groups and the three ESXi host groups named in the bundle. Then trigger a pass by re-importing the
   dashboard, or by logging in to the UI. The rule above predicts the six widgets then
   resolve and the tab completes. Cheapest proof on a healthy lab: create five empty
   dynamic groups of type Environment with those names, then log in once.
2. Pruning `entries` to the used ones does **not** help by itself. Unused entries never
   block, and the used ones that block are the five groups. Pruning only removes ERROR
   noise.
3. If the groups cannot be provided, edit the six widgets after import to point at
   existing groups. Or drop the five group references from those widgets' configs and the
   matching `entries` before import, and accept unpinned widgets.
4. For the earlier skip (Q1): rewrite `usermappings.json` to a source-less `admin` user (see
   above). That also makes the Content Management path work, but only if the five groups
   travel in the same bundle, or already exist.

### Clean-up and state left

The single dashboard import is the only write. The dashboard is left in place by
instruction (id above). Two jars (`vcops-view-server`, `vcops-bridge-server`) and javap
dumps sat in the session scratchpad only and were not kept (see the RULE-015 statement at
the top). The appliance's `vmware-vcops` service was
stopped by someone else at 10:01 CST and was still down when this was written.
