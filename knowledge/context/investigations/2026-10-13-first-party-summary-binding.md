# First-party pak Summary bindings on 9.0.2: who ships `dashboards.properties`, and why vSAN's clone is complete (devel, 2026-10-13)

**Answer:** on devel (VCF Operations 9.0.2.0 Build 25137845), exactly
one first-party pak ships `content/dashboards/dashboards.properties`:
**vSAN** (solution "Management Pack for Storage Area Network", pak
`ManagementPackforStorageAreaNetwork-902025137912`), which binds
`SummaryVirtualSANFaultDomain=VirtualAndPhysicalSANAdapter:VirtualSANFaultDomain`.
Its SUMMARY clone is fully materialized (every widget `isLoading: false`,
`widgetConfig` present with placeholders resolved to real ids). Ours is not.

The difference is **not in the JSON**. vSAN's dashboard has the same shape
as ours: `entries` plus non-empty widget configs that carry
`resourceKind:id:N_::_` placeholders and `viewDefinitionId`s. The 9.0.2
importer parks that config exactly the way it parks ours. vSAN's installer
clone was also taken 0.7 seconds after the import, the same race we lose.
It won because of **when** it was installed. The pak went in during the
appliance's first boot on April 16, before the stock dashboards existed.
At that point the admin user had no dashboards the importer could never
finish, so each import started a fresh importer thread. That thread's
immediate first pass stored the resolved source before the clone read it.

On devel today, 10 admin dashboards can never finish importing. That keeps
the admin importer thread alive and asleep for 10 minutes at a time, so
our install only pokes a sleeping thread and the clone always copies
unresolved widgets. **No change to our dashboard JSON, folder, flags or
`resources.properties` would make the clone complete.** The first-party
pak would fail the same way if it were installed on devel today
(inference, not tested).

**Instance:** devel, 9.0.2.0 Build 25137845. Our pak:
`dist/vcfcf_sdk_compliance.0.0.0.93.pak` (installed, bound clone
`9ffa3d88-788c-46bb-a2cc-67e378387a40`, "[VCF Content Factory] Compliance
World Summary 3").

**Posture:** read only. Root SSH for `find`, `unzip -l`/`unzip -p` on the
pak files, and `grep` of the logs. One vSAN pak copied off with `scp` to
the session scratchpad. UI Struts reads (`getSummaryTabId`,
`getDashboardConfig?isTemplate=true`, `getDashboardList`,
`getResourceKindList`). Suite API `GET /api/solutions` and resource
lookups. One headless browser session to view our Summary tab. Bytecode was
read with `javap` from class files already in the session scratchpad
(`DashboardManager`, `DashboardImporter`, `ImportExportManager`,
`VCOPSCLIManager`, `DataRetrieverServer` from
`vcops-bridge-server-1.0-SNAPSHOT.jar`). Nothing was created, changed,
installed or deleted. The Struts endpoints are unsupported UI endpoints
(the same tier as `X-Ops-API-use-unsupported`), with no Suite API
equivalent.

## 1. Which installed first-party paks ship `dashboards.properties`

**Where the pak files are.** `/storage/db/pakRepoLocal/<pak>/` holds only
the extracted metadata (`resources/`, `overview.packed`, `.results`), not
the `.pak`. The full pak files are in
`/storage/db/casa/pak/dist_pak_files/{VA_LINUX,NON_VA_LINUX,NON_VA_WINDOWS}/`
(identical copies, same md5) and in `/storage/db/casa/pak/to_install/`.
That explains the earlier "no pak uses it" from
`find / -name dashboards.properties`: the file only exists inside the pak
zip and in the installer's temp extract dir, never on disk afterwards.

**Scan:** `unzip -l` on every `.pak` in `dist_pak_files/VA_LINUX/` and
`to_install/`, matching `dashboards.properties` or `feature.properties`.
The adapter zips nested inside each first-party pak were also listed,
matching those names plus `conf/dashboards`. There were no hits in nested
zips.

| Pak (VA_LINUX) | Installed (`/api/solutions`) | `content/dashboards/` dirs | `dashboards.properties` |
|---|---|---|---|
| `ManagementPackforStorageAreaNetwork-902025137912` (vSAN) | yes, "vSAN" 9.0.2.0.25137912, `VirtualAndPhysicalSANAdapter` | `SummaryVirtualSANFaultDomain`, `vSANDashboards` | **yes** (79 bytes) |
| `SupervisorAdapter-902025137863` (vSphere Supervisor, "vmsp") | yes | `KubernetesDashboards` | no |
| `VCFAutomation-902025137921` (also `to_install/vmware-VCFAutomation-9.0.2.0-25137921.pak`) | **not installed** (in the repo only) | `VCF90`, `VCF90chargeback` | no |
| `vcf-902025137906` (VMware Cloud Foundation) | yes | `VMwareCloudFoundation` | no |
| `vim-902025137884`, `VMwarevSphere-902025137897`, `NSXTAdapter`, `VrAdapter`, `AppOSUCPAdapter`, `ServiceDiscoveryAdapter`, `CASAdapter`, `NetworkInsightAdapter`, `PingAdapter`, `VMwareInfrastructureHealth`, `ConfigurationManagement`, `MPBAdapter`, `VCFDiagnostics`, `VCFLogAssist`, the six compliance packs, `vcf-avi-910025407309` | mixed | various or none | no |
| AWS, the aggregator (`SummaryVMWAREAdapter`) | **not present** on devel (no pak, no solution) | n/a | n/a |
| `VCFContentFactoryCompliance-00093` (ours) | yes, 0.0.0.93 | 5 dirs | yes |

So of the vendor description's list, only vSAN can be confirmed on 9.0.2.
The vSphere Supervisor and VCF Automation paks of this build bind nothing.
Their `VMWARE:NamespaceV2` binding, if it exists, belongs to another
version. AWS and the aggregator could not be checked here.

vSAN's file, verbatim:

```
SummaryVirtualSANFaultDomain=VirtualAndPhysicalSANAdapter:VirtualSANFaultDomain
```

Bound directory layout (from the pak):

```
content/dashboards/SummaryVirtualSANFaultDomain/SummaryVirtualSANFaultDomain.json   (17869 bytes)
content/dashboards/SummaryVirtualSANFaultDomain/resources/resources{,_es,_fr,_ja}.properties
content/dashboards/dashboards.properties
content/dashboards/vSANDashboards/vSANDashboards.json  (+ resources/)
```

**Correction to earlier notes:** `v20-step5-silent-drop.md` was right that
the SAN pak's dashboards tree has a top-level `dashboards.properties`. The
"misread" verdict and the "no installed pak uses it" field check in
`../api-surface/summary_dashboard_pak_binding.md` are both wrong for 9.0.2.

## 2. Live state of each bound kind

Resource kind ids follow `"0020" + %02d(len(adapterKind)) + adapterKind + resourceKind`.
`VirtualAndPhysicalSANAdapter` is 28 characters long, so the id is
`002028VirtualAndPhysicalSANAdapterVirtualSANFaultDomain`. (A first try
with `002029...` returned `{}`. On 9.0.2 `getSummaryTabId` returns only
`{"tabId": ...}` with no `isDashboard` key.)

`getResourceKindList?appendDetailPageMappings=true` for the vSAN adapter:
`vSAN Fault Domain -> "Summary Page: vSAN Fault Domain"` is the only
dashboard-template mapping. Every other vSAN kind maps to a compiled page
(`defaultTemplateName` set) or to "Summary Detail".

| | vSAN Fault Domain | Compliance World (ours) |
|---|---|---|
| `getSummaryTabId` | `69da177d-5406-433f-b8f6-e1c6f2164972` | `9ffa3d88-788c-46bb-a2cc-67e378387a40` |
| template name | "Summary Page: vSAN Fault Domain" (no suffix, single install) | "[VCF Content Factory] Compliance World Summary 3" |
| tab `isLoading` | **false** | **true** |
| widgets | Scoreboard "Summary", ResourceRelationship, View "ESXi Hosts", Heatmap, View "Disk Groups" | Scoreboard, View x2, MetricChart, AlertList, PropertyList |
| per-widget `isLoading` | **false** on all 5 | **true** on all 6 |
| `widgetConfig` / `isPreconfigured` | present / true on all 5 | absent on all 6 |
| placeholders in config | **resolved**, for example Heatmap `groupBy.typeId = "002006VMWAREHostSystem"` where the pak has `resourceKind:id:1_::_` | n/a (no config) |
| `isDisabled`, `isHidden_`, `isShared` | true, true, false | false, true, true |

The resolved placeholders matter. They prove vSAN's config **was** parked
at import and later rewritten by an importer pass (`fromEntryKeys`).
Without that pass the placeholder text would still be there. vSAN went
through the same deferral as ours. It just finished before the clone.

The first compliance clone, `4cfb2eb2` (9:10 AM today), is also still
`isLoading: true` on all six widgets at 10 PM. Its source resolved at
9:12 AM, and three more template writes have happened since. So a clone
never catches up with its source after the fact.

**Screenshot:** devel has no `VirtualSANFaultDomain` objects
(`GET /api/adapterkinds/VirtualAndPhysicalSANAdapter/resourcekinds/VirtualSANFaultDomain/resources`
returns none), so the vSAN Summary tab cannot be opened for an object.
Only ours was captured: session scratchpad
`shots/compliance-summary-ComplianceWorld.png`, not committed. It shows
an hourglass on every widget title. The Scoreboard shows the stock badges
(Total Anomalies, Compliance, Efficiency, Health, Risk) plus one row. The
View shows "The widget is not configured. Select a view to render." The
Scan PropertyList shows default property rows. Deep link that works on
9.0.2:
`/vcf-operations/ui/inventory;mode=tree;resourceId=<uuid>;tab=summary`.

## 3. Their JSON versus ours

| Aspect | vSAN `SummaryVirtualSANFaultDomain.json` | Ours `VCF_Content_Factory_Compliance_World_Summary/dashboard.json` | Matters on 9.0.2? |
|---|---|---|---|
| top-level keys | `dashboards`, `entries`, `uuid` | same | no |
| `entries` | `resourceKind` x2 (VirtualSANFaultDomain, VMWARE HostSystem) | `resourceKind` x1, `adapterKind` x1 | no: both resolvable, and our source did resolve |
| widget config | non-empty on all 5. Scoreboard has 5 placeholders, Heatmap 8, the Views have literal `viewDefinitionId` | non-empty on all 6. Scoreboard 4, MetricChart 2, PropertyList 1, Views literal | no: any non-empty config is parked (`ImportExportManager.importDashboard`, offsets 1552 to 1732) |
| `importComplete` | `true` | `true` | no: never read by the importer (`addDashboardTabs` sets `false` for every import) |
| `importAttempts` | 0 | 0 | no |
| `disabled` / `hidden` / `shared` | true / true / false | false / true / true | no: none of these is on the parking or clone path |
| `namePath` | `Summary Pages` (`name` "Summary Pages/New Summary Page: vSAN Fault Domain") | `VCF Content Factory` | no: folder only |
| extra tab fields | `creationTime` real, `rank` 102, real `userId` | `adapterName`, `lastUpdateTime`, `lastUpdateUserId`, `states: []` | no |
| widget fields | `collapsed, config, gridsterCoords, height, id, states, title, type` | same minus `states` | no |
| widget types | Scoreboard, View, ResourceRelationship, Heatmap | Scoreboard, View, MetricChart, AlertList, PropertyList | no: all valid on 9.0.2 |
| `resources/resources.properties` | dashboard name, widget titles, and `Summary\ Pages=Summary Pages` | dashboard name, widget titles, and `VCF\ Content\ Factory=VCF Content Factory` | no: localization |
| pak layout | `content/dashboards/<dir>/<dir>.json` + `resources/`; a second unbound dir | `content/dashboards/<dir>/dashboard.json` + `resources/`; four unbound dirs | no: the installer zips the whole dir |

Neither has a field that resolves entries up front. 9.0.2 has no such
field: parking tests only whether the config string is empty.

## 4. Why vSAN's clone won: timeline and mechanism

Audit log (`analytics.audit-*.log.1`, UTC stamps), converted to local time:

| Local time (America/Chicago) | Event |
|---|---|
| Apr 16, 9:22:43 PM | `DASHBOARD_IMPORT` (previous pak) |
| Apr 16, 9:23:24.995 PM | `DASHBOARD_IMPORT` (vSAN pak, `vSANDashboards`) |
| Apr 16, 9:23:25.654 PM | `DASHBOARD_IMPORT` (vSAN pak, `SummaryVirtualSANFaultDomain`; it must be this one, because the clone follows in the same loop iteration) |
| **Apr 16, 9:23:26.361 PM** | `DASHBOARD_ADD_TEMPLATE` "New Summary Page: vSAN Fault Domain", SourceTabId `8be0cd6a-...`, **0.7 s after its import** |
| Apr 16, 9:30:04 PM | first `admin` UI login |
| Apr 16, 9:30:05 PM and 9:30:15 PM | two `DASHBOARD_IMPORT` with `ForceByID: true` by `maintenanceAdmin` in the login thread, followed by 296 `DASHBOARD_ADD_TAB` for stock "(DEP) ..." and other built-in dashboards. This is the stock content load. |

That is the only `DASHBOARD_ADD_TEMPLATE` for vSAN in the log. There is no
`DASHBOARD_ASSOCIATE` event anywhere, which is the audit action
`addDashboardSummaryTemplates` logs first, so no templates-key importer
was started by a summary-template import. The bridge log from April has
rotated away (the oldest is from June 12), so the importer's own lines for
that night are gone.

**Bytecode facts used (9.0.2):**

- `DashboardManager.saveDashboardAsTemplate` (public, 4 args) reads
  `getDashboardDTO(userId).getDashboardTabsMap().get(tabId)` and passes
  that tab to the private worker. The worker sets a new tab id, name,
  `userId = null` and new widget ids, adds it to the templates DTO and
  stores it. The clone is therefore a snapshot of whatever the source tab
  holds at that instant. If the importer has already stored the resolved
  source, the clone is complete. If not, the clone keeps `configKey` and
  stays blank.
- `DashboardImporter.run` does its first pass immediately on `start()`,
  then re-reads `getDashboardDTO(userId)`, merges and calls
  `storeDashboardDTO`. It sleeps 10 minutes only if some tab could not
  resolve. `update()` (the poke a later import sends to a live thread)
  does not wake that sleep. Only `ImportExportManager.importDashboardTabs`
  creates an importer, and only when none is alive for that user id.

**How fast a fresh importer thread is on devel** (June, the only window
where fresh threads appear in surviving logs; DASHBOARD_IMPORT audit time
to the thread's first and last log line):

| Local time | Import | Fresh thread active |
|---|---|---|
| Jun 16, 8:43:10.871 AM | `DASHBOARD_IMPORT` | 8:43:13.202 to 8:43:14.629 AM (Thread-138720) |
| Jun 16, 11:08:24.814 AM | `DASHBOARD_IMPORT` | 11:08:25.654 to 11:08:25.858 AM (Thread-139894) |
| Jun 16, 1:18:02.542 PM | `DASHBOARD_IMPORT` | 1:18:05.699 to 1:18:08.177 PM (Thread-140939) |

The audit stamp is written when the import begins, before parsing, so
these are upper bounds. A fresh thread finishes a pass between about 1
and 4 seconds after the import is audited, which is the same order as the
installer's 0.4 to 0.7 seconds to the clone. **On a quiet instance, then,
it is a race the clone can win but is not guaranteed to win.**

**Why ours always loses on devel.** `getDashboardList` at about 10 PM
tonight: 10 admin dashboards with `isLoading: true`. Six are stock cost
dashboards (Business Applications Cost vs. Price, Chargeback (VM Price),
Critical Business Applications, Showback (Business Application Cost),
Showback (VM Cost), VM Cost vs. Price), whose entries name
`AZURE_VIRTUAL_MACHINE` and other kinds that are not installed. The other
four are Rubrik Overview, Cluster Performance Risk, and the two factory
MSSQL/Oracle Query Performance dashboards. They keep the admin importer
alive in 10-minute ticks (one thread lived continuously from Jun 17 to 18
in the bridge logs), and every import resets its 24-hour limit. Each
compliance install therefore pokes a sleeping thread, the clone is taken
while the source is still parked, and the source resolves up to 10
minutes later. The four compliance clones today, 9:10 AM, 11:32 AM,
2:46 PM and 4:18 PM, all lost.

**What this predicts for customer instances (inference, not tested).**
The stock cost dashboards were imported at first login on devel and have
stayed unresolved ever since. If the same is true on other instances
without the Azure pack, then any import starts or pokes an admin importer
that cannot finish. In that case a bound dashboard wins only if:

- no other import happened in the previous 24 hours, so a fresh thread
  starts; and
- the bound directory is the first directory the installer imports in
  that pak; and
- the first pass stores the source within about half a second.

The installer walks `content/dashboards/` in `File.listFiles()` order,
which on Linux is directory-entry order and not alphabetical, so a pak
cannot control which directory comes first. vSAN on a fresh appliance
before the stock content load is the best case. A day-2 install of our
five-directory pak is close to the worst case.

## 5. Conclusion and the smallest change

1. **Do first-party bound Summary dashboards render on 9.0.2?** The one
   that exists here (vSAN Fault Domain) has a fully materialized clone and
   would render. It got that way because it was installed at first boot
   into an empty admin dashboard set, not because of anything in its JSON
   or install. Its JSON parks and defers exactly like ours.
2. **What makes their clone complete where ours is not:** install-time
   conditions. The admin importer was idle when it was installed, so a
   fresh thread resolved and stored the source within the 0.7 seconds
   before the clone. On devel, 10 unresolvable admin dashboards (four of
   them ours or third-party, six stock) keep the importer asleep, so the
   clone always copies parked widgets.
3. **Smallest change to our pak that would match:** there is none at the
   JSON, folder, flag or `resources.properties` level. Copying vSAN's
   fields (`disabled: true`, `namePath: "Summary Pages"`, `shared: false`,
   `<dir>/<dir>.json` naming) changes nothing on the parking or clone
   path. Shipping the bound dashboard as the only directory in the pak
   would improve the odds on a quiet instance, but it is still a race and
   still needs 24 import-free hours. It is not a fix.
   The deterministic routes are unchanged from
   `2026-10-13-dashboard-import-deferral-trigger.md` and the parked stake:
   - **Post-install re-bind** (`bind-summary` once the source reports
     `isLoading: false`, branch for issue #200).
   - **A templates-key import from an adapter post-install script.** This
     is unverified. ops-cli on 9.0.2 exposes two forms:
     `dashboard defsummary <input-file>|default --adapterType <AK> --objectType <RK>`
     (to `VCOPSCLIManager.importSummaryDashboard`, then
     `DashboardManager.addDashboardSummaryTemplates`, which imports with
     `userId = null` and so starts a templates importer whose first pass
     would also finish any blank clone already bound), and
     `template import <file> ... --resknd-keys <AK>:<RK>[,...]`. The usage
     strings were read from devel's `opscli.log`. Neither was run.
4. **Lab hygiene that would change devel's behavior:** two of the 10 stuck
   admin dashboards are factory content (MSSQL and Oracle Query
   Performance, whose `SqlServer` kinds are absent), and Cluster
   Performance Risk is ours. Removing or fixing them would not be enough
   while the six stock cost dashboards stay unresolved.

## Open

- Whether the stock cost dashboards stay unresolved on a clean customer
  instance without the Azure pack. One `getDashboardList` read on another
  instance (qa or main) would settle it, and with it the "works on
  customer instances" question.
- A decisive test of the race (a write, needs Scott's go): install the
  compliance pak on an instance where `getDashboardList` shows zero
  `isLoading: true` admin dashboards and no import in the past 24 hours,
  then read `getDashboardConfig?isTemplate=true` on the new clone.
- The vendor description's AWS, aggregator and VCF Automation
  `NamespaceV2` bindings could not be checked on this build.
