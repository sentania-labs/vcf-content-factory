# The Section widget on 8.18.7 and 9.0.2: content import and pak install, measured (2026-11-13)

Run 2026-11-13, 08:52 to 09:45 America/Chicago, on two single-node lab
instances. Read before anything changed (`GET /api/versions/current`):

| profile | product | build |
|---|---|---|
| `devel_8_18` | VMware Aria Operations 8.18.7 | 25423534 |
| `devel` | VCF Operations 9.0.2.0 (solutions report `9.0.2.0200.*`) | 25431135 |
| `devel_9_1` (read-only source of the Section wire form) | VCF Operations 9.1.1.0 | 25795063 |

`devel` has been rebuilt since the 2026-10-12 note
(`../../lessons/unknown-widget-type-aborts-pak-dashboard-import.md`, build
25137845). This note repeats the pak measurement on the current 9.0.2 build and
extends it to 8.18.7 and to the content-import path.

**Local-only artifacts; not reproducible from a clone (RULE-015).** The exports,
import zips, envelopes, install logs and log extracts are lab debris and stay on
the holding share at `/mnt/holding/vcf-content-factory/backups/section-widget-2026-11-13/`
(per profile: `B0/` baseline, `A/` path-A runs, `B/` pak runs, `B1/` and `final/`
exports, `scripts/`). The pak used is
`/mnt/holding/vcf-content-factory/builds/vcommunity-fix-e1/vCommunity_0.8.1-fix-builtin-view-ids-e1-releasedimage.pak`
(sha256 `7cc81338614a185bf3546f1d9112eb2e1a9c19c5a507eddad64a637339b05780`). The
findings are summarized here in full; the citations are not needed to follow them.

## Answer

- **8.18.7:** a dashboard with a `Section` widget is never created, by either
  path. In a content import it also takes every other dashboard in the same
  import with it, and the import still reports FINISHED with nothing failed. In
  a pak only the Section dashboards are lost; the pak's other dashboards install.
- **9.0.2:** exactly the same, on both paths. The 8.18.7 and 9.0.2 importers are
  the same code here.

Neither version drops the Section widget and keeps the rest of the dashboard.
There is no partial dashboard.

## Why: one importer, both versions

Read from the node jars (bytecode, read-only; nothing vendor is quoted beyond
names and log strings):

- `WidgetDTONew$WidgetType` (`common/lib/vcops-bridge-client-1.0-SNAPSHOT.jar`)
  has the same 47 constants with the same keys on 8.18.7 and 9.0.2, and none is
  `Section`. The list is in `../api-surface/summary_dashboard_pak_binding.md`.
- `ImportExportManager.importDashboard(JSONObject, ...)`
  (`controller/plugins/vcops-bridge-server-1.0-SNAPSHOT.jar`) on both builds still
  builds its unknown-widget skip message with `getString("Title")` and
  `getString("Type")`, capitalised. The dashboard JSON has `title` and `type`, so
  the log call itself throws `JSONException: JSONObject["Title"] not found` and the
  exception leaves the dashboard import. The intended "skip the widget" never
  happens. Line numbers in the stack differ (8.18.7 `ImportExportManager.java:1171`,
  9.0.2 `:1009`); the behavior does not.

## Results

### Path A: content import (`POST /api/content/operations/import`, `force=true`)

One zip per run, one owner, dashboards in one `dashboards/<owner>` inner zip
(`dashboard/dashboard.json`, `dashboards[]` in the order given). Synthetic
content only: D1 "Zeta Probe Section D1 rN" = TextDisplay, Section (member: the
second TextDisplay), TextDisplay; D2 "Zeta Probe Plain D2 rN" = one TextDisplay.
New UUIDs every run. Envelope = the `GET /api/content/operations/import` result
after the run; "exists" = UI `getDashboardList` plus `getDashboardConfig` on
each id.

| version | run | order in `dashboards[]` | envelope (DASHBOARDS) | D1 | D2 |
|---|---|---|---|---|---|
| 8.18.7 | r1 | D1, D2 | FINISHED, errorCode NONE, total 2, imported 0, skipped 0, failed 0, no messages | absent | **absent** |
| 8.18.7 | r2 | D2, D1 | same as r1 | absent | **absent** |
| 8.18.7 | r3 (control) | D2 only | FINISHED, total 1, imported 1 | n/a | present, 1 TextDisplay |
| 8.18.7 | r4 | D1 only | FINISHED, total 1, imported 0, skipped 0, failed 0 | absent | n/a |
| 9.0.2 | r1 | D1, D2 | FINISHED, errorCode NONE, total 2, imported 0, skipped 0, failed 0, no messages | absent | **absent** |
| 9.0.2 | r2 | D2, D1 | same as r1 | absent | **absent** |
| 9.0.2 | r3 (control) | D2 only | FINISHED, total 1, imported 1 | n/a | present, 1 TextDisplay |
| 9.0.2 | r4 | D1 only | FINISHED, total 1, imported 0, skipped 0, failed 0 | absent | n/a |

What it shows:

- The Section dashboard is never created, not even partly: `getDashboardConfig`
  on its id returns no tab.
- **Order does not matter.** With D2 first, the importer did process D2 (its
  per-dashboard log line, below, appears before the failure) and D2 still does
  not exist. The failure discards every dashboard of that owner bundle, not just
  the ones after D1.
- The envelope is the trap: `imported + skipped + failed` is 0 of 2, with no
  error message and `errorCode: NONE`. The only signature in the API is that the
  three counters do not add up to `total`. The factory's "imported nothing"
  check (`imported=0, skipped>0`) does not catch it, because `skipped` is 0
  (§Implications).
- Rendering: on neither version is there anything to render, so a browser look
  would show nothing; no browser check was made.

Log evidence, `view-bridge.log` (thread `DistTaskBackupRestoreManagerDistributedTask`), 9.0.2 r1:

```
2026-11-13T14:59:01.859Z INFO  ... BackupRestoreManager.restoreData - restoreData: Dashboards import started...
2026-11-13T14:59:01.911Z ERROR ... BackupRestoreManager.restoreData - restoreData failed to import Dashboards. Error: JSONObject["Title"] not found.
2026-11-13T14:59:01.911Z INFO  ... BackupRestoreManager.restoreData - restoreData: Dashboard Sharings import started...
2026-11-13T14:59:01.992Z INFO  ... BackupRestoreManager.restoreData - restoreData: Dashboard Sharings import passed
```

and `vcops-bridge.log` at the same instant:
`ImportExportManager.importDashboard - JSONObject["Title"] not found.` 8.18.7
logs the same pair (r1 at `2026-11-13T15:04:43,087+0000`). In the D2-first runs
the D2 line `ImportExportManager.importDashboard - JSONObject["dashboardNavigations"]
is not a JSONObject (class org.json.JSONArray)` comes about 10 ms before the
`Title` error (9.0.2 `15:00:29.634Z` then `15:00:29.642Z`; 8.18.7
`15:05:00,411` then `15:05:00,422`). That `dashboardNavigations` line also
appears for the control run r3, which imported, so it is noise, not a failure.

Not tested: whether views or other content types in the same zip survive
(`restoreData` runs them as separate phases, and the Sharings phase after the
failed Dashboards phase still ran and passed, so probably yes); dashboards of a
second owner in the same zip; the UI's import dialog (it posts the same zip
format to the same task, but was not exercised).

### Path B: pak install

Vehicle: the corrected build of the upstream vCommunity e1 0.8.1 content (PR 92
branch, no built-in view ids; `python3 -m vcfcf_packaging stock-id-check` 0 hits
in 252 definitions), the same file installed and removed on `devel_9_1` on
2026-11-12. Its `manifest.txt` says `vcops_minimum_version 8.18.0`. 52 dashboards
in 19 `content/dashboards/` directories (one directory holds 34 report-input
dashboards, the other 18 hold one each). Two dashboards carry Section widgets,
each alone in its directory: "vCommunity/Overall Daily Check"
(`555b7d86-b48e-4f26-ae9e-b19ba24369d4`, 6 Section widgets) and "vSphere
Cluster Capacity 2.0" (`c608ccb8-218a-4834-8a9d-af9241e01de1`, 2). Every other
widget type in the pak (View, Scoreboard, HealthChart, ParetoAnalysis, Heatmap,
ResourceRelationshipAdvanced, MetricChart, TextDisplay, AlertList) is in both
builds' enum, so Section is the only variable. Installed with
`python3 -m vcfcf_managementpacks install` (default flags), no adapter instance
created.

| version | install | task result | pak dashboards present | missing | missing == the Section set | importer evidence |
|---|---|---|---|---|---|---|
| 8.18.7 | 1st, 15:10:48Z | FINISHED, verified, exit 0 | 50 of 52 | Overall Daily Check, vSphere Cluster Capacity 2.0 | yes | 2 `Title` errors (15:14:33, 15:14:54); 19 `DASHBOARD_IMPORT`, 17 `DASHBOARD_GROUP` |
| 8.18.7 | repeat, 15:19:53Z | FINISHED, verified, exit 0 | 50 of 52 | same two | yes | 2 `Title` errors (15:24:06, 15:24:23); 19 / 17 |
| 9.0.2 | 1st, 15:02:13Z | FINISHED, verified, exit 0 | 50 of 52 | same two | yes | 2 `Title` errors (15:06:08, 15:06:37); 19 / 17 |
| 9.0.2 | repeat, 15:19:05Z | FINISHED, verified, exit 0 | 50 of 52 | same two | yes | 2 `Title` errors (15:22:35, 15:22:46); 19 / 17 |

Present/missing is by id against UI `getDashboardList` after every install, and
also by a full content export (`B1`: 50 of the 52 ids on both; 9.0.2 taken after
the first install, 8.18.7 after the repeat). Audit counts are the installer's own
session (`clientIP n/a`), one `DASHBOARD_IMPORT` per directory and one share
(`DASHBOARD_GROUP`) per directory that imported: 19 directories, 17 shares, so
exactly the two Section directories failed. The other 17 directories, including
the 34-dashboard one, imported in full.

So in a pak the blast radius is the directory: the installer imports each
`content/dashboards/<dir>` separately and moves on after a failure. A directory
that held a Section dashboard plus others would, by the path-A result, lose all
of them; that layout was not run. The install reports nothing: the task
finishes, the installer verifies the pak, and the only trace is in
`vcops-bridge.log`, thread `DistTaskSolutionManagerDistributedTask`:

```
2026-11-13T15:14:33,613+0000 ERROR [DistTaskSolutionManagerDistributedTask] com.vmware.vcops.bridge.server.ImportExportManager.importDashboard - JSONObject["Title"] not found.
org.json.JSONException: JSONObject["Title"] not found.
	at org.json.JSONObject.getString(JSONObject.java:855)
	at com.vmware.vcops.bridge.server.ImportExportManager.importDashboard(ImportExportManager.java:1171)
	...
	at com.vmware.vcops.bridge.server.DataRetrieverServer.importDashboard(DataRetrieverServer.java:6972)
	at com.vmware.vcops.bridge.plugin.server.SolutionManagerDistributedTask.installDashboardContent(SolutionManagerDistributedTask.java:1269)
```

(8.18.7; 9.0.2 is the same with `ImportExportManager.java:1009`,
`DataRetrieverServer.java:7473`, `SolutionManagerDistributedTask.java:1300`.)

A repeat install does not change the outcome: same two missing, same two errors,
every time. Unlike the unexplained one-random-dashboard miss of
`2026-11-12-vcommunity-upstream-builtin-view-ids.md`, this one is deterministic.

The factory installer's materialization check reported the six Object Summary
Page dashboards as still building after 180 s on three of the four installs; that
is the known deferred-materialization behavior with no adapter instance, unrelated
to Section.

## The Section wire form used

Taken from the 9.1.1 built-in "Performance/Provider/Memory Tiering" dashboard
(`722e437d-3aba-41b2-bcfa-245639f5c8d9`, widget `0e97c44a-1f7e-48f5-9e31-076187525e8a`)
in a content export of `devel_9_1` taken 2026-11-12T23:45:00Z (before the pak
test there; read only, nothing taken from any other bundle on that instance).
Path A used the same keys with new ids and titles:

```json
{"tabId": "<dashboard id>", "collapsed": false, "id": "<widget id>",
 "gridsterCoords": {"w": 12, "x": 1, "h": 1, "y": 4}, "state": "",
 "type": "Section", "title": "Zeta probe section",
 "config": {"widgetId": "<widget id>", "description": "", "title": "Zeta probe section",
            "widgets": ["<member widget id>"]},
 "height": 0}
```

The pak's own Section widgets have the same shape plus `config.titleLocalized`.
The factory renderer's form (`_section_widget` in
`src/vcfcf_core/dashboards/render.py`) drops `config.widgetId` and `state`; the
failure is on `type`, before either is read, so it does not matter which form.

## Cleanup

| profile | step | result |
|---|---|---|
| both | path A | each surviving control dashboard (r3) deleted with UI `deleteTab`; `getDashboardList` shows no "Zeta" dashboard afterwards |
| `devel` | uninstall 15:28:14Z | OK, pak absent from `/api/solutions`, 0 of the 52 pak dashboard ids listed |
| `devel_8_18` | uninstall after the B1 export | OK, pak absent from `/api/solutions`, 0 of the 52 pak dashboard ids listed |

Proof: full content export before (`B0`) and after (`final`) on each instance,
compared per object by id and content hash (views, reports, dashboards, super
metrics, symptoms, alerts, custom groups; policies by canonical hash), plus the
UI `getDashboardList` id/name list:

| profile | views | reports | dashboards | super metrics | symptoms | alerts | custom groups | policies | UI dashboard list |
|---|---|---|---|---|---|---|---|---|---|
| `devel_8_18` | 778 = 778 | 62 = 62 | 163 = 163 | 8 = 8 | 1685 = 1685 | 1061 = 1061 | 15 = 15 | same | identical |
| `devel` | 851 = 851 | 63 = 63 | 180 = 180 | 37 = 37 | 2075 = 2075 | 1292 = 1292 | 18 = 18 | same | identical |

Every type: 0 added, 0 gone, 0 changed. No adapter instance was created. The
temporary class extract on each node (`/tmp/wtx`) was removed in the same
command that made it. Nothing was changed on `devel_9_1`.

While installed, the pak added on 8.18.7: views +169 (of 170), reports +11 (of
16), symptoms +10, alerts +4, super metrics +2, dashboards +50; on 9.0.2: views
+170, reports +16, symptoms +2 (of 10, the known 9.0.2 duplicate-key failure),
alerts +4, super metrics +2, dashboards +50. The short view and report counts on
8.18.7 were not investigated; they do not touch the dashboard result.

## Undetermined

- Whether 9.1.0 imports Section (the floor in
  `src/vcfcf_core/dashboards/widget_versions.py` is 9.1.1, 9.1.0 unchecked).
- Path A with views or other content in the same zip, or with dashboards of a
  second owner: probably unaffected (separate `restoreData` phases), not run.
- A pak directory holding a Section dashboard together with other dashboards:
  expected to lose all of them (path A shows one importer call is all or
  nothing), not run.
- The UI "Import" dialog was not exercised; it is the same backup-restore task as
  the Suite API import, which is why it is expected to behave the same.
- No browser check (no browser tooling in this session); nothing renders because
  nothing is created.
- Any other unknown widget type behaves the same by the code path, but only
  Section was run.

## Implications

- Content bundles carry no target version, so `Dashboard.validate()` only warns on
  Section (issue #199). That warning understates it: on 8.18.7 and 9.0.x one
  Section dashboard silently wipes **every** dashboard in the same content-import
  zip. The factory packs all of an owner's dashboards into one inner zip, so a
  bundle with ten dashboards and one Section imports none of them there.
- `import_content_zip` callers can detect it: `imported + skipped + failed <
  total` on a FINISHED DASHBOARDS summary with no error message. The current
  "imported nothing" check (`all_skipped_content_types` in
  `src/vcfcf_dashboards/client.py`) requires `skipped > 0` and does not fire.
  Whether the dashboards handler's post-import materialization lookup by id
  (#167) reports the absent dashboards was not run.
- Paks: the Tier 2 build gate that fails a Section dashboard against the 8.18.7
  line (`dashboard_fidelity_wire_format.md` §Section) is right, and the loss is
  per directory, so it must stay a build failure, not a warning.
