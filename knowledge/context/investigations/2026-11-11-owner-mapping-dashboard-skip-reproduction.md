# Owner mapping skips a dashboard on import: controlled reproduction on 9.0.2

Run 2026-11-11, 10:01 to 10:09 America/Chicago, on the `devel` lab (VCF Operations
9.0.2.0 Build 25429562, single node), authorized by the lab owner. Eight `force=true`
imports of one throwaway view and dashboard through `POST /api/content/operations/import`.
Only `usermappings.json` (and, in one run, the marker file's content) varied. Every probe
was deleted afterwards and the deletion checked against a pre-experiment snapshot
(§Cleanup). No auth source or user was created. Root SSH to the appliance was used for
reads only: log tails, plus one `scp` of
`controller/plugins/vcops-view-server-1.0-SNAPSHOT.jar` (sha256 `56f4e6af0d96207a85430edd5c7be1ef3fcfda341134ab3ec51ac325b8a4dd71`) to the
session scratchpad for local `javap`. The jar is not in the repo and no vendor code is
quoted. The bytecode is described in prose, as in the 9.1.1 note.

**Local-only artifact; not reproducible from a clone (RULE-015).** The jar, the full `javap`
output and the raw run captures (envelopes, log tails, snapshots) are Broadcom material or
lab debris, so they stay out of this public repo. They are on the lab holding share at
`/mnt/holding/vcf-content-factory/evidence/owner-mapping-dashboard-skip/9.0.2-25429562/`,
with `sha256sums.txt`, `javap-importAndReassignUserMappings.txt` (that method's block, cut at
its boundaries only), `original/` (the jar and the full `javap -p -c -constants` of
`BackupRestoreManagerDistributedTask`) and `runs/`. The findings are summarized here in full,
so you do not need the citation to follow them. Anyone with an appliance of the same build
can re-derive them from
`/usr/lib/vmware-vcops/controller/plugins/vcops-view-server-1.0-SNAPSHOT.jar` (class
`com.vmware.vcops.bridge.plugin.server.BackupRestoreManagerDistributedTask`) and the two log
files named in §Log evidence.

It confirms under control what
`2026-11-11-devel-9-1-ui-import-dashboard-skip-and-gemfire-503.md` read from logs on 9.1.1.
It also shows the mapping rule is narrower than that note describes (§The mapping rule).

## Answer

A content import skips a dashboard when its owner in `usermappings.json` cannot be mapped
to a user on the target. It does this under `force=true`, with no error in the envelope:
`DASHBOARDS imported=0 skipped=1 failed=0`, `errorCode: NONE`, `errorMessages: []`. Views in
the same zip import normally. The dashboard importer is never called. The skip comes from
the owner, not from the content. Every run had `force=true` and started with the dashboard
absent. The bytecode says the same skip happens when the dashboard already exists and under
any `force` value, because the owner check comes before `importDashboard` on every path.
That is inferred from the bytecode; neither case was run. An owner maps in exactly three
ways:

1. **Source-less owner whose `userId` equals the marker file's content.** It maps to the
   target's admin, whatever its `userName`. Every factory-built zip takes this path. Each
   zip builder writes the owner id into the marker file: `packager.build_import_zip` and
   the installer template `_build_*_zip`. The `userName` it writes varies (below), so the
   name is not what makes factory zips map.
2. **Source-less owner otherwise.** It maps by case-insensitive `userName` against the
   target's users.
3. **Owner with a `userSourceId`.** It maps only if that source resolves on the target. For
   `ACTIVE_DIRECTORY`, `OPEN_LDAP` and `OTHER`, that means an LDAP host with the same host
   (case-insensitive), port and base DN. It then maps by `userName`. Path 1 does not apply
   to sourced owners.

Anything else is unmappable, and every dashboard in that owner's file is counted as
skipped.

## Target auth sources (read-only, `GET /api/auth/sources`)

`devel` has five sources: three `VC` (one per vCenter), one `VC_GROUP` ("All vCenters"),
and one `ACTIVE_DIRECTORY` source named `ad` for the lab domain (port 3268, SSL, host
auto-select). The invented source used in B, C and E's input,
`ldap.exp-owner.example.invalid:389`, base DN `dc=exp-owner,dc=example,dc=invalid`, matches
none of them. That is what "does not exist on the target" means here. The source list was
identical before and after the experiment.

## Probe and harness

- View `[VCF Content Factory] EXP-OWNER Probe View` (`5e7a0e0e-0000-4000-8000-00000000e001`):
  a one-column list of `ClusterComputeResource`.
- Dashboard `[VCF Content Factory] EXP-OWNER Probe Dashboard`
  (`5e7a0e0e-0000-4000-8000-00000000ed01`): a ResourceList picker driving a View widget on
  that view.
- Both were built with `vcfcf_core.dashboards.loader.load_all` and `packager.build_import_zip`
  (`owner_user_id=5e7a0e0e-0000-4000-8000-0000000000a1`, `owner_username="admin"`). The probe
  YAML lived in the session scratchpad only. Marker file name: `6844548499441080431L.v1`.
  This is a literal constant in the 9.0.2 `BackupRestoreManagerDistributedTask` bytecode.
  The usual discovery export returned 500 on its status poll during this session, so the
  constant was used.
- Variants rewrote `usermappings.json` inside the built zip. The rest of the zip was left
  alone: file name `dashboards/<owner>`, `dashboardsharings/<owner>` (Everyone, LOCAL),
  `configuration.json` `dashboardsByOwner`, and the inner `userId`, all on
  `...0000000000a1`.
- Import through `vcfcf_dashboards.client.import_content_zip` (`force=true`, poll until
  `endTime` advances). Existence checks before and after through `getDashboardList` and
  `getGroupedViewDefinitionThumbnails`. The probe dashboard was deleted
  (`dashboard.action mainAction=deleteTab`) after every run that created it, so every run
  started with the dashboard absent and the view present.
- Field names (`sources[].sourceId/sourceType/sourceHost/sourcePort/sourceDomain`,
  `users[].userId/userName/userFirstName/userLastName/userSourceId`) come from the
  `UserMappingExportTags` constants in the 9.0.2 jar. `sourcePort` is read as an int.

B's `usermappings.json`, verbatim (C changes `userName` to `admin`):

```json
{
   "sources": [
      {
         "sourceId": "5e7a0e0e-0000-4000-8000-0000000000c3",
         "sourceType": "ACTIVE_DIRECTORY",
         "sourceHost": "ldap.exp-owner.example.invalid",
         "sourcePort": 389,
         "sourceDomain": "dc=exp-owner,dc=example,dc=invalid"
      }
   ],
   "users": [
      {
         "userName": "exp.owner@example.invalid",
         "userId": "5e7a0e0e-0000-4000-8000-0000000000a1",
         "userFirstName": "Exp",
         "userLastName": "Owner",
         "userSourceId": "5e7a0e0e-0000-4000-8000-0000000000c3"
      }
   ]
}
```

## Runs

All `force=true`. "Marker" is the content of `6844548499441080431L.v1`. `...a1` is the
owner id; `...b2` is a different invented id.

| Run | `usermappings.json` owner | Marker | VIEW_DEFINITIONS | DASHBOARDS | Dashboard after | View after |
|---|---|---|---|---|---|---|
| A (control) | `sources: []`, `admin`, no source | `...a1` | imp 1 | **imp 1** skip 0 | exists, owner admin, shared | exists |
| B (claim) | invented AD source, `exp.owner@example.invalid` | `...a1` | imp 1 | **imp 0 skip 1** | absent | exists |
| C | invented AD source, `admin` | `...a1` | imp 1 | **imp 0 skip 1** | absent | exists |
| D | `sources: []`, `exp.owner@example.invalid`, no source | `...a1` | imp 1 | **imp 1** skip 0 | exists, owner admin | exists |
| D2 (added) | as D | `...b2` | imp 1 | **imp 0 skip 1** | absent | exists |
| E (fix) | B's zip, `usermappings.json` set to A's shape | `...a1` | imp 1 | **imp 1** skip 0 | exists, owner admin | exists |
| F2 (added) | lab's real AD source (host/port/base DN from `/api/auth/sources`), `admin` | `...a1` | imp 1 | **imp 1** skip 0 | exists, owner admin | exists |
| F1 (added) | as F2, `exp.owner@example.invalid` | `...a1` | imp 1 | **imp 0 skip 1** | absent | exists |

Why the extra runs:

- **D2.** D imported, which the brief did not expect. The 9.0.2 bytecode explains it: a
  source-less owner whose id equals the marker content is mapped to the target admin
  before any name lookup. So D alone could not separate "missing user" from "has a
  source". D2 changes only the marker content, and the skip returns.
- **F1 and F2.** These test the 9.1.1 note's inference that a configured source does not
  help if the user is missing. They use the lab's real AD source, so they create nothing.
- **E.** Strictly, E duplicates A: B and E differ only in `usermappings.json` and in
  inner-zip timestamps, with byte-identical inner payloads. It was kept as the "edit only
  usermappings" proof.

Envelopes, verbatim (B shown pretty-printed; the others compact, one line each):

```json
{
  "operationSummaries": [
    {"type": "import", "imported": 1, "skipped": 0, "failed": 0, "total": 1,
     "infoMessages": [], "errorMessages": [], "contentType": "VIEW_DEFINITIONS", "state": "FINISHED"},
    {"type": "import", "imported": 0, "skipped": 1, "failed": 0, "total": 1,
     "infoMessages": [], "errorMessages": [], "contentType": "DASHBOARDS", "state": "FINISHED"}
  ],
  "errorMessages": [], "id": "29c1613f-3bbe-4aa0-8236-2c74db22c661", "type": "IMPORT",
  "state": "FINISHED", "startTime": 1794413073838, "endTime": 1794413074175, "errorCode": "NONE"
}
```

```
A  {"operationSummaries":[{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"VIEW_DEFINITIONS","state":"FINISHED"},{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"DASHBOARDS","state":"FINISHED"}],"errorMessages":[],"id":"29c1613f-3bbe-4aa0-8236-2c74db22c661","type":"IMPORT","state":"FINISHED","startTime":1794413025139,"endTime":1794413030953,"errorCode":"NONE"}
C  {"operationSummaries":[{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"VIEW_DEFINITIONS","state":"FINISHED"},{"type":"import","imported":0,"skipped":1,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"DASHBOARDS","state":"FINISHED"}],"errorMessages":[],"id":"29c1613f-3bbe-4aa0-8236-2c74db22c661","type":"IMPORT","state":"FINISHED","startTime":1794413098782,"endTime":1794413099228,"errorCode":"NONE"}
D  {"operationSummaries":[{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"VIEW_DEFINITIONS","state":"FINISHED"},{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"DASHBOARDS","state":"FINISHED"}],"errorMessages":[],"id":"29c1613f-3bbe-4aa0-8236-2c74db22c661","type":"IMPORT","state":"FINISHED","startTime":1794413126882,"endTime":1794413128996,"errorCode":"NONE"}
D2 {"operationSummaries":[{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"VIEW_DEFINITIONS","state":"FINISHED"},{"type":"import","imported":0,"skipped":1,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"DASHBOARDS","state":"FINISHED"}],"errorMessages":[],"id":"29c1613f-3bbe-4aa0-8236-2c74db22c661","type":"IMPORT","state":"FINISHED","startTime":1794413159754,"endTime":1794413159973,"errorCode":"NONE"}
E  {"operationSummaries":[{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"VIEW_DEFINITIONS","state":"FINISHED"},{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"DASHBOARDS","state":"FINISHED"}],"errorMessages":[],"id":"29c1613f-3bbe-4aa0-8236-2c74db22c661","type":"IMPORT","state":"FINISHED","startTime":1794413191886,"endTime":1794413195138,"errorCode":"NONE"}
F2 {"operationSummaries":[{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"VIEW_DEFINITIONS","state":"FINISHED"},{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"DASHBOARDS","state":"FINISHED"}],"errorMessages":[],"id":"29c1613f-3bbe-4aa0-8236-2c74db22c661","type":"IMPORT","state":"FINISHED","startTime":1794413250642,"endTime":1794413253612,"errorCode":"NONE"}
F1 {"operationSummaries":[{"type":"import","imported":1,"skipped":0,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"VIEW_DEFINITIONS","state":"FINISHED"},{"type":"import","imported":0,"skipped":1,"failed":0,"total":1,"infoMessages":[],"errorMessages":[],"contentType":"DASHBOARDS","state":"FINISHED"}],"errorMessages":[],"id":"29c1613f-3bbe-4aa0-8236-2c74db22c661","type":"IMPORT","state":"FINISHED","startTime":1794413288743,"endTime":1794413290170,"errorCode":"NONE"}
```

Side note: the envelope `id` (`29c1613f-...`) is the importing user's (`admin`'s) user id
on this instance, as `/api/auth/currentuser` shows. Earlier notes called it a "stable
pipeline id". It is stable per importing user.

## Log evidence (verbatim)

`/storage/log/vcops/log/view-bridge.log` (on 9.0.2 the file name carries no node UUID).
Logger `com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData`, thread
`DistTaskBackupRestoreManagerDistributedTask`, process `view-bridge 5639`.

B, the skip (thread 685505):

```
2026-11-11T16:04:34.110Z INFO  view-bridge 5639 [ops@4413 threadId="685505" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData] - restoreData: User Mappings import started...
2026-11-11T16:04:34.129Z ERROR view-bridge 5639 [ops@4413 threadId="685505" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData] - restoreData failed to import User Mappings.
2026-11-11T16:04:34.129Z INFO  view-bridge 5639 [ops@4413 threadId="685505" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData] - restoreData: Dashboards import started...
2026-11-11T16:04:34.130Z ERROR view-bridge 5639 [ops@4413 threadId="685505" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData] - restoreData failed to map Dashboard. File: 5e7a0e0e-0000-4000-8000-0000000000a1
2026-11-11T16:04:34.130Z INFO  view-bridge 5639 [ops@4413 threadId="685505" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData] - restoreData: Dashboard Sharings import started...
2026-11-11T16:04:34.131Z ERROR view-bridge 5639 [ops@4413 threadId="685505" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData] - restoreData failed to map Dashboard. File: 5e7a0e0e-0000-4000-8000-0000000000a1
2026-11-11T16:04:34.183Z INFO  view-bridge 5639 [ops@4413 threadId="685505" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.run] - BackupRestoreManagerDistributedTask finished in 346ms.
```

C (thread 685511, 16:04:59.107Z to .108Z), D2 (thread 685541, 16:05:59.937Z to .938Z) and
F1 (thread 685608, 16:08:09.610Z to .665Z) show the same three ERROR lines, word for word,
with the same `File:` value. The second `failed to map Dashboard` line belongs to the
sharings step: it is logged after `Dashboard Sharings import started...` and uses the same
constant.

A, the control (thread 685464). D, E and F2 show the same shape:

```
2026-11-11T16:03:47.720Z INFO  view-bridge 5639 [ops@4413 threadId="685464" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData] - restoreData: User Mappings import started...
2026-11-11T16:03:47.747Z INFO  view-bridge 5639 [ops@4413 threadId="685464" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData] - restoreData: Dashboards import started...
2026-11-11T16:03:50.472Z INFO  view-bridge 5639 [ops@4413 threadId="685464" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData] - restoreData: Dashboard Sharings import started...
2026-11-11T16:03:50.822Z INFO  view-bridge 5639 [ops@4413 threadId="685464" threadName="DistTaskBackupRestoreManagerDistributedTask"] [com.vmware.vcops.bridge.plugin.server.BackupRestoreManager.restoreData] - restoreData: Dashboard Sharings import passed
```

A skip run's dashboard section takes 1 to 2 ms. An import run's takes 2 to 3 s.

`/storage/log/vcops/log/analytics.audit-0ad8f158-5363-48d4-b6d0-2b50057b279c.log`, the
same import threads. Every run, the skip runs included, has the view line:

```
2026-11-11T16:04:34.082Z INFO  audit 5639 [ops@4413 threadId="685505" userId="29c1613f-3bbe-4aa0-8236-2c74db22c661" username="system" authSource="n/a" session="6a975a13-919c-3aeb-9d29-17107888b682" clientIP="172.16.3.13" auditID="VIEW_DEFINITION_IMPORT"] [AuditLog.log] - Importing view definition(s) succeeded. ID(s): "5e7a0e0e-0000-4000-8000-00000000e001".
```

Only the runs that imported (A, D, E, F2) also have:

```
2026-11-11T16:03:47.748Z INFO  audit 5639 [ops@4413 threadId="685464" userId="437440f9-992a-4397-9503-3348657ce863" username="maintenanceAdmin" authSource="n/a" session="24d00bf9-d300-302d-a905-296dc23bd2ca" clientIP="172.16.3.13" auditID="DASHBOARD_IMPORT"] [AuditLog.log] - Importing dashboard. ForceByID: "false", ForceByName: "true".
```

B, C, D2 and F1 have **no** `DASHBOARD_IMPORT` line on their import thread, so the
importer was never invoked. Noise to filter out: every UI-client login writes a
`DASHBOARD_IMPORT ... ForceByID: "false", ForceByName: "false"` plus a `DASHBOARD_DELETE`
of `3d84205c-45c8-4708-9a94-161a18443796` from `maintenanceAdmin` on another thread
(646068, the factory host's client IP). The 9.1.1 note saw the same pairing.

### 9.0.2 versus what the 9.1.1 note recorded

| Item | 9.0.2 (here, verified) | 9.1.1 (per the other note) |
|---|---|---|
| view-bridge file | `view-bridge.log` | `view-bridge-<node-uuid>.log` |
| Logger, thread, message text | `...BackupRestoreManager.restoreData`, `DistTaskBackupRestoreManagerDistributedTask`, the three ERROR strings | identical |
| Audit id style | `auditID="VIEW_DEFINITION_IMPORT"` / `"DASHBOARD_IMPORT"`, free-text message (`Importing view definition(s) succeeded. ID(s): ...`, `Importing dashboard. ForceByID: ..., ForceByName: ...`) | recorded as `VIEW_DEFINITION.IMPORT` / `DASHBOARD.IMPORT` with `result="success"`; not re-read on 9.1.1 for this note |
| Envelope | silent: `failed 0`, `errorCode NONE`, no messages | UI showed "skipped", no failure |

## The mapping rule (9.0.2 bytecode, `importAndReassignUserMappings(byte[], String, String)`)

In prose:

- `restoreData` reads the marker file `6844548499441080431L.v1` (the name is a constant in
  the class) into a string. It passes that string, the exporter's user id, as the second
  argument, and `RestoreContentParam.userId` as the third.
- For each `users[]` entry **without** `userSourceId`: if `userId` equals the marker
  content, the target id is `getAdminUserId()` (in SaaS, a cloud-admin variant). Otherwise
  it loops over the target's users (`getAllUsers`) and takes the first case-insensitive
  `userName` match.
- For each entry **with** `userSourceId`: it maps only when the source id resolved earlier
  (`ACTIVE_DIRECTORY`/`OPEN_LDAP`/`OTHER` against `getAllAvailableLdapHosts()` on host, port
  and base DN; `SSO_SAML`, `VIDM`, `VC` and `CSP` have their own matchers; `VCD` source ids
  are accepted as they are). It then does the same `userName` loop. The marker-id shortcut
  is not on this branch.
- An empty result map logs `restoreData failed to import User Mappings.`. In the dashboards
  and sharings loops, an owner file whose name has no mapping goes to the branch that adds
  `configuration.json` `dashboardsByOwner[owner]` to the skipped count and logs
  `restoreData failed to map Dashboard. File: %s`.

This corrects the 9.1.1 note's first description, which said a source-less user maps
"through an id comparison to `getAdminUserId()`". That note now carries the correction.
The comparison is against the **marker content**, and `getAdminUserId()` is the result.
On 9.0.2 this is verified by bytecode and by D against D2. On 9.1.1 it is inferred: that
jar was not re-read for it.

It also explains G1 in `../api-surface/content_import_skip_semantics.md`. The packager
writes the owner id into the marker, so a bogus owner id still takes path 1. G1 never
tested a missing user.

## Verified versus inferred

Verified on 9.0.2 by run plus log:
- An unmappable owner skips the dashboard under `force=true`, silently in the envelope, and
  the view still imports (B, C, D2, F1).
- A sourced owner is not rescued by a name that exists locally (C).
- A source-less owner is mapped by the marker shortcut (D), and without it only by name
  (D2).
- A configured, matching source plus an existing name maps (F2). The same source with a
  missing name skips (F1).
- Rewriting only `usermappings.json` to the source-less `admin` shape fixes it (E).
- The log strings, logger and thread are the same as on 9.1.1. The importer is not invoked
  (no `DASHBOARD_IMPORT` audit line).

Inferred from bytecode, not run:
- That the skip also happens when a dashboard of the same id already exists, and leaves it
  untouched. The code never reaches `importDashboard`, so it should, but every run here
  started from absent.
- That the skip also happens under `force=false` or with `force` omitted. The owner check
  does not read `force`, but every run here sent `force=true`.
- `OPEN_LDAP`, `OTHER`, `SSO_SAML`, `VIDM` and `VC` sources behave the same way. Each has
  its own matcher in the bytecode, but only `ACTIVE_DIRECTORY` was exercised.
- The marker shortcut on 9.1.1.

## Implications

- Any bundle exported from an instance where the dashboard owner is a directory user, or a
  local user whose name does not exist on the target and whose id differs from the
  exporter's, will skip those dashboards on import. Re-importing does not help. The fix is
  to rewrite `usermappings.json` to `sources: []` with the owner as a source-less user named
  `admin`, or to make the owner id equal the marker content. Renaming the owner files is
  not required: E kept `...a1` everywhere.
- Factory-built zips do not hit this. Every zip builder writes `sources: []`, one
  source-less owner whose `userId` is the importing session's user id, and that same id as
  the marker content. So they map through path 1, whatever name they carry. The name does
  vary by path, checked against the code on 2026-11-11:
  - `packager.build_import_zip` defaults to `admin`.
  - The sync handler (`src/vcfcf_dashboards/handler.py`, both `build_import_zip` calls)
    passes `user.get("userName", "admin")`. `/api/auth/currentuser` returns the key
    `username`, not `userName` (devel 9.0.2), so today the default `admin` is what gets
    written.
  - The installer template (`src/vcfcf_packaging/templates/install.py` and `install.ps1`)
    writes the login user's name.
  - A non-admin session writing its own name would still map through path 1.
- The exposure is third-party and customer bundles imported as they are: through the UI,
  as `/extract` inputs, or by any pass-through.

## Cleanup

| Check | Before (16:02Z) | After (16:09Z) |
|---|---|---|
| `getDashboardList` count | 180 | 180, set identical, zero `EXP-OWNER` hits |
| Probe dashboard by UUID (`getDashboardConfig?tabId=...ed01`) | n/a | `tabConfigs: []` |
| `getGroupedViewDefinitionThumbnails` view count | 787 | 787, set identical, zero `EXP-OWNER` hits (probe view deleted through `viewServiceController.deleteView`, ok) |
| `/api/auth/sources` | 5 sources | same ids and properties |

No users or auth sources were created. The appliance was only read.

## Reproducing

Throwaway harness in the session scratchpad, not committed. To redo it: build any view and
dashboard pair with the loader and packager, and rewrite `usermappings.json` (and the
marker content for D2) inside the zip with Python `zipfile`. POST to
`/api/content/operations/import?force=true` with the session's JSON Content-Type
suppressed. Tail `view-bridge.log` and the analytics audit log from line counts taken
before the POST. Use `devel` only.
