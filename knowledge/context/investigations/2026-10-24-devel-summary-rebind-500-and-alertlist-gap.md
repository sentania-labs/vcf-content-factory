# devel: Summary rebind error panel, and the Environment Overview alert list gap

- **Date:** 2026-10-24, America/Chicago (CDT). Evidence read 1:33 AM to 1:46 AM.
- **Instances:** devel (`lastbuildversion.txt`: 9.0.2.0 Build 25429562), devel_8_18 (`lastbuildversion.txt`: 8.18.6 Build 25423535; the lab registry calls it 8.18.7 build 25423534), devel_9_1 (rpm `vmware-vcops-9.0.0.0-25794169`, the 9.1.1 build; one class file read only).
- **Method:** read-only. SSH as root for log reads and to copy one class file off each appliance (`javap -c -p -l` locally). UI session (`/ui/*.action`) as the profile admin for read-only `getWidgetConfigs`, `getDashboardConfig` and `getAlertsGroups` replays, logged out after each run. Suite API `GET /api/alerts` and `GET /api/resources`. Nothing created, changed or deleted.
- **Trigger:** `knowledge/context/reviews/compliance-build-98.md` findings 1 and the on-screen check.

## Root causes (short)

1. **Summary rebind error panel: wrong request parameter for these builds.** On 9.0.2 Build 25429562 and 8.18.6 Build 25423535 the server action reads ONE parameter, `dashboardAssociations`. The factory client sends `assignedAssociations` plus `resetAssociations`, which is the 9.1.1 shape. The server gets null, `new JSONObject(null)` throws a NullPointerException before anything is read or written, and Struts renders the generic error panel with HTTP 200. Materialization state, the template id, and "kind already bound" play no part: the throw happens on the first line that touches the request.
2. **Alert list gap: the list was never unselected, and it includes canceled alerts.** The live provider View still has `selectFirstRow: true` (the build 98 pak carries `false`, but the re-import did not replace the live widget config). The first row is vcf-lab-mgmt, so the AlertList was scoped to vcf-lab-mgmt at depth 4 on every load. A replay scoped to vcf-lab-mgmt with every alert status reproduces the browser's second load exactly (34 groups, 708 alerts, the same per-group counts on screen). The four "missing" definitions exist only under vcf-lab-wld01 and vcf-lab-wld02. The first load's lower count (28 groups, 636) is a client paging race that skipped the second page of six groups.

## Part 1: associateResourceKindDashboards

### When the calls happened (from the logs, not the brief)

The brief said about 1:25 to 1:30 AM. The logs show the three failing calls earlier. No call to the action was logged between 1:18 AM and the end of the evidence window.

| Instance | Local time | Who | Log |
|---|---|---|---|
| devel | 12:57:38 AM | installer (`SUMMARY UNCHECKED`) | `web.log.1` line 84650 |
| devel_8_18 | 1:16:55 AM | installer | `web.log` line 41942 |
| devel | 1:17:47 AM | manual repeat | `web.log.1` line 85431 |

### Verbatim log, devel (12:57:38 AM; the 1:17:47 AM repeat is identical apart from time)

```
2026-10-24T05:57:38.154Z INFO  web 1884 [ops@4413 threadId="164" threadName="ajp-nio-127.0.0.1-8009-exec-5"] [com.vmware.vcops.ui.util.MainPortalListener.log] - Cannot invoke "String.length()" because "<parameter1>" is null (
Url: /ui/dashboard.action
Params: mainAction=associateResourceKindDashboards
)
java.lang.NullPointerException: Cannot invoke "String.length()" because "<parameter1>" is null
	at java.io.StringReader.<init>(Unknown Source) ~[?:?]
	at org.json.JSONTokener.<init>(JSONTokener.java:70) ~[json-20231013.jar:?]
	at org.json.JSONObject.<init>(JSONObject.java:405) ~[classes/:?]
	at com.vmware.vcops.ui.action.DashboardAction.associateResourceKindDashboards(DashboardAction.java:2607) ~[classes/:?]
	at com.vmware.vcops.ui.action.DashboardAction.execute(DashboardAction.java:286) ~[classes/:?]
```

### Verbatim log, devel_8_18 (1:16:55 AM)

```
2026-10-24T06:16:55,387+0000 INFO  [ajp-nio-127.0.0.1-8009-exec-5] com.vmware.vcops.ui.util.MainPortalListener.log -  (
Url: /ui/dashboard.action
Params: mainAction=associateResourceKindDashboards
)
java.lang.NullPointerException
	at java.base/java.io.StringReader.<init>(Unknown Source)
	at org.json.JSONTokener.<init>(JSONTokener.java:70)
	at org.json.JSONObject.<init>(JSONObject.java:405)
	at com.vmware.vcops.ui.action.DashboardAction.associateResourceKindDashboards(DashboardAction.java:2578)
	at com.vmware.vcops.ui.action.DashboardAction.execute(DashboardAction.java:286)
```

### What the source line is

`DashboardAction.class` copied from `/usr/lib/vmware-vcops/tomcat-web-app/webapps/ui/WEB-INF/classes/com/vmware/vcops/ui/action/` on each appliance.

Full hashes and the offset-level reading for all three builds: `2026-10-26-dashboardaction-associate-evidence.md`.

| Build | sha256 of DashboardAction.class | Parameters read | Line of the throw |
|---|---|---|---|
| devel 9.0.2.0 Build 25429562 | `2c9c838b...e51d67` | `dashboardAssociations` only | 2607 = `new JSONObject(dashboardAssociations)` (LineNumberTable: line 2606 is the `getParameter`, 2607 the constructor) |
| devel_8_18 8.18.6 Build 25423535 | `597eed20...8d4dbd` | `dashboardAssociations` only (local variables `dashboardAssociations_`, `dashboardAssociations`, `dashboardAssociationsIterator`) | 2578, same statement |
| devel_9_1 Build 25794169 | `8de8af93...a3daed` | `assignedAssociations` and `resetAssociations` | not called |

Bytecode fragment, devel 9.0.2 (method `associateResourceKindDashboards`):

```
  79: aload_0
  80: getfield      #37   // Field request:Ljavax/servlet/http/HttpServletRequest;
  83: ldc_w         #1935 // String dashboardAssociations
  86: invokeinterface #43, 2 // HttpServletRequest.getParameter
  91: astore        5
  93: new           #54   // class org/json/JSONObject
  97: aload         5
  99: invokespecial #498  // JSONObject."<init>":(Ljava/lang/String;)V
```

The bundled SPA agrees with the server on each build (`js/dashboard/DashboardAssociateWindow.js` and the minified bundle):

| Build | SPA request |
|---|---|
| 9.0.2 Build 25429562 | `params: {mainAction: 'associateResourceKindDashboards', dashboardAssociations: Ext.encode(this.updatedAssociations)}` |
| 8.18.6 Build 25423535 | same as 9.0.2 |
| 9.1.1 Build 25794169 | `params:{mainAction:"associateResourceKindDashboards",assignedAssociations:Ext.encode(this.assignedAssociations),resetAssociations:Ext.encode(this.resetAssociations)}` |

### The pre-9.1 request shape (from bytecode and SPA, not exercised live)

```
POST /ui/dashboard.action
  mainAction=associateResourceKindDashboards
  dashboardAssociations={"resourceKind_<resourceKindId>":"<dashboardName>_::_<dashboardUuid>", ...}
  secureToken=<csrfToken>
```

- Bind: value `<name>_::_<uuid>`. The server splits on `_::_` (no `_::_` in the value throws `StringIndexOutOfBounds`), looks the dashboard up with `getDashboardDTO(<caller's userId>, [uuid])` (or `null` user for an OOTB template id), calls `saveDashboardAsTemplate(uuid, name, SUMMARY, userId)` (4-argument form, no widget-state copy), puts the new template id in the association map, and deletes the kind's previous template if it differs.
- Reset ("Use Default"): the SPA sends `<templateName>_::_null` (`templateName + "_::_" + tabId` with a null tabId). The server sees the part after `_::_` is empty or the string `null` and removes the map entry. It does **not** delete the old template.
- A dashboard the caller cannot see (`getDashboardDTO` returns null or no tabs) is skipped silently: no map write, the response is still the success path. The SUMMARY copy is taken from whatever state the source is in; there is no materialization check in the action.

### Answers to the brief's questions

| Question | Answer | Evidence |
|---|---|---|
| Does the action reject a source still materializing? | No. Never reached: the NPE is before any lookup. The action has no materialization check on any build read. | bytecode offsets 79 to 99, LineNumberTable |
| A kind already bound? | No. Never reached; an existing binding is replaced and its old template deleted. | bytecode offsets 389 to 410 |
| A template id? | No. Never reached. | same |
| Something in the request body? | **Yes.** The parameter name. These builds read `dashboardAssociations`; the client sent `assignedAssociations` and `resetAssociations`. | stack traces, bytecode, SPA |
| Does it succeed on devel_9_1 by design or because the copy was complete? | 9.1.1 reads `assignedAssociations`/`resetAssociations`, so the factory's call matches it by design. In this run the installer never called it on 9.1 (its copy had finished, `SUMMARY OK`). | 9.1 bytecode offsets 85 to 111, build 98 review |
| Documented or observed precondition? | Only one, other than the parameter name: the source dashboard must be visible to the calling user (looked up with the caller's userId). | bytecode offsets 228 to 282 |

### Correction to existing docs

`knowledge/context/api-surface/summary_dashboard_assignment.md` (sections "Write (bulk)" and "`associateResourceKindDashboards`: wrong parameter name") says `dashboardAssociations` "does not exist on any build" and that the two-map shape returned `200 ok` "on both builds". That was measured on a 9.0.0.0 pre-release build and 9.2 builds. It is wrong for 9.0.2 Build 25429562 and 8.18.6 Build 25423535, which accept only `dashboardAssociations`. The `ui_client.py` docstring repeats the same claim.

## Part 2: Environment Overview, Open Compliance Alerts

### Facts

| Item | Value | Source |
|---|---|---|
| Live provider `Compliance by vCenter and Object Type` | `selectFirstRow: {"selectFirstRow": true}`, `selfProvider: true`, pinned vSphere World | `getWidgetConfigs` tab `155743b0-15e0-40e4-acd3-05f68f8684d4`, 1:41 AM |
| Same widget in the installed pak (sha256 `cba3927b...61b71b`) | `selectFirstRow: {"selectFirstRow": false}` | `content/dashboards/VCF_Content_Factory_Compliance_Environment_Overview/dashboard.json` |
| Other live-vs-pak differences on that dashboard | none of substance (only `titleLocalized` and resolved placeholder ids) | widget-by-widget diff |
| Live AlertList config | `{"criticalityLevel": [2, 3, 4], "type": ["15_21"], "mode": "all", "depth": 4, "relationshipMode": {"relationshipMode": [-1, 0]}, "status": [], "state": [], "resource": [], "selfProvider": {"selfProvider": false}, "filterMode": "tagPicker", "alertDefinitions": [], ...}` | `getWidgetConfigs` |
| Screenshot of load 2 | vcf-lab-mgmt row highlighted in the provider View | `.../scratchpad/p98/shots/envoverview-devel-all-loaded-second-load.png` |
| Import log | dashboards.properties found, dashboard import ran, `removeObsoleteContent` ran (force path), 12:55 to 12:56 AM | `view-bridge.log` lines 18757 to 18763 |
| Suite API, compliance alerts at 1:41 AM | 1144 total: 721 ACTIVE across 36 definitions, 423 CANCELED (cancel times mostly 10-18, 8:30 to 9:10 AM) | `GET /api/alerts` |

### What the widget asks the server for

`AlertList.js` (9.0.2) `buildFilterData` sends `criticality`, `alertStatus` (from `status`), `alertType`, `isWidget: true`, `customFilter`, `depth`, `relationshipMode`, and `resourceIds` from the stored interaction. Empty values are deleted. The server (`ProblemAlertsAction.getSearchParamForWidget`, 9.0.2) then:

- builds `RelationshipCriteria(resourceIds, SELF_CHILD-or-mode, depth)` **only when `resourceIds` is non-empty**. With no selection there is no resource scope at all: depth is ignored and the list is every alert in the environment that matches the filters. There is no fallback object (not vSphere World, not ComplianceWorld).
- sets a status filter only when `alertStatus` has exactly one element: `[0]` is ACTIVE, any other single value is CANCELED. `status: []` means **no status filter**, so canceled alerts are listed.

### Replay (read-only `getAlertsGroups`, groupBy `problemDefinitionId`, 1:44 AM)

| Scope (`resourceIds`, depth 4) | Status | Groups | Alerts |
|---|---|---|---|
| vcf-lab-mgmt | all | **34** | **708** |
| vcf-lab-mgmt | active | 31 | 356 |
| vcf-lab-wld01 | all | **31** | **147** |
| vcf-lab-wld02 | all | 31 | 279 |
| all three vCenters | all | 41 | 1134 |
| all three vCenters | active | 36 | 718 |
| none (true "show all") | all | 41 | 1134 |
| none | active `[0]` | 36 | 718 |

The vcf-lab-mgmt/all row matches the browser's second load exactly, group by group where the screenshot shows them (Compliance data not collected (ESX host) 8, Host Compliance Score Degraded 6, reject-forged-transmit 2, vpxuser-rotation 2, mac-learning 2, vpxuser-length 2, restrict-discovery-protocol 2, Compliance data not collected (cluster) 1). The vcf-lab-wld01/all row matches the reviewer's "wld01 selected" count (31 groups, 147). The four definitions the reviewer could not find (`vm.deactivate-non-essential-3d-features`, `dvpg.network-vgt`, `esx.account-lockout-max-attempts`, `vm.log-enable`) have zero alerts under vcf-lab-mgmt; they sit under wld01 and wld02 only.

Server paging was checked for stability: 8 repeated runs of 6-group pages (active) and 4 (all statuses) each returned every group exactly once, no duplicates, no gaps.

### Why the two loads differed: client paging race, not server data

`web.log` request trace on devel (`getAlertsGroups`, limit 6):

| Load | Local time | `start` sequence | Note |
|---|---|---|---|
| 1 | 1:23:01 to 1:24:24 AM | 0 (2029 ms), 0 (started 1:23:03.613, 939 ms), 12, 18, 24, 30 | the two initial loads overlapped |
| wld01 click | 1:26:12 to 1:26:51 AM | 0, 6, 12, 18, 24, 30 | complete |
| 2 | 1:27:23 to 1:28:20 AM | 0 (733 ms), 0 (started after the first returned), 6, 12, 18, 24, 30 | complete |

`GroupedItemsList.js` resets `startFrom` to 0 when a load starts and adds the page size in every success callback. Two initial loads (the widget fires two) that overlap both complete and leave `startFrom` at 12, so the first LOAD MORE asks for `start=12` and groups 7 to 12 are never fetched. Load 1 lost exactly one page: 34 minus 6 is 28 groups, 708 minus that page is about 636. This is product UI behaviour; a widget setting cannot prevent it.

### What the widget needs to show all active compliance alerts (721 at 1:28 AM)

1. **Get `selectFirstRow: false` onto the live dashboard.** The YAML and pak are right; the live per-user widget config kept `true` through a force re-import. Why the re-import did not replace it is **not proven** here. The likely suspect is the two-phase import (`dashboard_import_two_phase_materialization.md`) leaving an existing resolved widget config in place when the widget id is unchanged. Not tested, because a delete-and-reinstall is a change on the instance.
2. **Set `status: [0]` on the AlertList** (the loader and renderer already accept it: `loader.py` "`[0]` = active only"). Without it the "Open" list also shows canceled alerts (vcf-lab-mgmt: 708 shown, 356 active).
3. Nothing else. No fallback object, no resource-kind filter, no relationship change. With no selection the server applies no scope, so the replay returns 36 groups and 718 alerts, the same as the Suite API's active set less 3 alerts outside criticality 2 to 4 or otherwise filtered (not chased).
4. Residual risk: the overlapping-initial-load race can still skip a page of groups on a slow first load. It is cosmetic (LOAD MORE skips one page), product-side, and not fixable in content.

## Clean-up

No objects created. Every UI session logged out. Copies of class files, JS and replay JSON stay in the session scratchpad only.

**Not retained, then recaptured (2026-10-26, framework review of #260, W4).** The 2026-10-24 scratchpad is gone. A read-only pass on 2026-10-26 recaptured all three builds: `2026-10-26-dashboardaction-associate-evidence.md` (full hashes, the offsets each claim rests on, the conclusions; the verbatim `javap` and SPA text is local-only on the lab holding share, out of the public repo). Every class hash matches the prefix in the table above. 8.18.6 and 9.0.2 carry the same method instruction for instruction. Of the three claims the factory relies on, the NPE comes before any write (all three builds), a single-map entry merges into the stored map, and a `_::_null` reset removes the binding but leaves the template copy; one caveat (the error panel is not specific to the missing parameter) and one correction (9.1.1's plain-name reset is not shown to delete the copy) are in that file.

## Follow-ups

- Tooling: `associate_resource_kind_dashboards` must send `dashboardAssociations` on builds that read it (9.0.2 Build 25429562, 8.18.6 Build 25423535) and the two-map shape on 9.1.1. Choosing by version string is fragile (the 9.1.1 appliance's `lastbuildversion.txt` reads "9.0.0.0"). A safer probe is the error itself: the two-map call NPEs and writes nothing, so a retry in the other shape is safe.
- Correct `summary_dashboard_assignment.md` and the `ui_client.py` docstring (see "Correction to existing docs").
- Exercise the pre-9.1 shape once on devel to confirm `ok` and the new `getSummaryTabId`, with an explicit go (it writes the association map and creates a template).
- Find out why the force re-import kept `selectFirstRow: true` (also a question for every other widget-config change shipped by pak upgrade).
