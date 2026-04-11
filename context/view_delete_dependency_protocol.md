# View/report delete: dependency-confirmation hypothesis (REFUTED)

> **SEE `context/dashboard_delete_api.md` §"2026-04-11 update" for the
> correction to this and the related investigation.** The conclusion that
> "the 500 is a server-side handler crash entirely independent of client
> invocation shape" below is WRONG. The correct `deleteView` data shape
> (using `viewDefIds` with JSON-stringified `{id,name}` array) works on
> the same `/ui/vcops/services/router` URL that was being tested here.
> The exception responses during this investigation were caused entirely
> by sending the wrong data shape.

**Verdict: the hypothesis is REFUTED.** There is no multi-step
dependency-confirmation protocol in the Ext.Direct RPC catalog on VCF
Ops 9.0.2, and the `deleteView` / `deleteReportDefinitions` handlers
return HTTP 200 with `{type:"exception", message:"Internal server
error."}` on **every** target and **every** invocation shape tested,
including as `admin`, including when batched with the dependency-
lookup call the SPA would plausibly make first. The 500 is a
**server-side handler crash** that is entirely independent of client
invocation shape, caller account, view ownership, subject duplication,
or actual dependency state.

Investigation run 2026-04-11 against
`vcf-lab-operations.int.sentania.net` (VCF Ops 9.0.2.0 build 25137838).

## Hypothesis statement

The SPA UI shows a confirmation dialog when deleting a view, warning
about dependent dashboards/reports, and that dialog implies a
two-call protocol: (1) get dependents, (2) delete with force/confirm
flag. Our current `install.py::UIClient.delete_view()` only performs
step 2, and the server's `deleteView` may crash when called without
the acknowledgment, producing the observed HTTP 500.

## Full Ext.Direct catalog (parsed from `/ui/vcops/services/api.js`)

The api.js served by the instance is **2,805 bytes total** and
declares exactly six controllers. Below is the complete method list
for every controller relevant to view/report delete. This is the
entire surface available to the browser — there are no hidden
controllers and no force-delete variants.

### `viewServiceController` (23 methods)

| Method | Arity | Notes |
|---|---|---|
| `uploadImage` | len=0, formHandler | View background images only |
| `getGroupedViewDefinitionThumbnails` | len=0 | Lists all views. Returned 1023 items on this instance. UUID field in result entries is `viewDefinitionKey`, not `id`. |
| `getResourceContextReferenceById` | len=1 | |
| `isResourceApplicable` | params=[resourceRef, viewDefinitionCreationData] | |
| `getDateRange` | params=[controls] | |
| **`deleteView`** | **len=1** | **BROKEN — returns `{type:"exception", message:"Internal server error."}` on every input tested.** |
| `removeChartFromCache` | len=1 | |
| `exportViewDefinitionAsCSV` | params=[resourceRef, viewDefinitionCreationData, controls] | |
| `getView` | params=[resourceRef, viewDefinitionId, controls, isAsc, columnIndex] | |
| `getSampleResourceForPreview` | params=[resourceKindId, subjectType] | |
| `getViewDataById` | len=2 | |
| `getMetricDetails` | len=2 | |
| `getUnits` | len=1 | |
| `validateTransformationExpression` | params=[expression] | |
| `getLivePreview` | params=[resourceRef, creationData, controls, isAsc, columnIndex] | |
| `renderChart` | params=[chartData, width, height, currentDate, colorScheme] | |
| `getViewDateRange` | params=[controls] | |
| `getViewDefinitionThumbnails` | len=1 | |
| `getViewURL` | params=[resourceId, viewDefinitionId, traversalSpecId] | |
| `isViewSortable` | params=[viewDefinition] | |
| `saveOrUpdateViewDefinition` | len=1 | **BROKEN — returns Internal server error with a minimal plausible payload.** Full view-creation path via UI RPC could not be exercised from a non-browser client. |
| `getViewThumbnails` | len=1 | |
| `exportViewAsCSV` | params=[resourceRef, viewDefinitionId, controls] | |

**No dependency-check method exists.** No `getDependents`,
`getViewDependencies`, `canDeleteView`, `validateDelete`, or any
method whose name suggests pre-delete validation.

**No force-variant of `deleteView` exists.** Only the single `len=1`
method declared above.

### `reportServiceController` (14 methods)

| Method | Arity | Notes |
|---|---|---|
| `getReportDefinitionThumbnails` | len=1 | **BROKEN** with `{"start":0,"limit":500}` — returns Internal server error |
| `isReportDefinitionEmpty` | params=[reportDefinitionId] | **BROKEN** — Internal server error for valid report IDs |
| `getDefaultCoverImage` | len=0 | |
| `getReportDefinitionThumbnailsById` | len=1 | |
| **`getByViewIds`** | **len=1** | **WORKS.** `data=[[viewUuid]]` and `data=[viewUuid]` both return the array of dependent report **names** (strings, not IDs). This IS the dependency lookup the hypothesis predicted. Confirmed: passing `c192d4d6-50b9-49cf-a9d5-fe53c9f5134a` returns `["ESXi Host Active Alerts"]` — exactly the dependent report. But knowing this does not unblock `deleteView`. |
| `runReport` | params=[reportDefId, resourceRef, isTenant] | |
| `setDefaultCoverImage` | len=1 | |
| `getReportDefinitionNameById` | len=1 | **WORKS** — returns the report name string. |
| `saveOrUpdateReportDefinition` | len=1 | |
| `runReportForVsphereWorld` | params=[reportDefId] | |
| `isResourceApplicable` | params=[reportDefinitionId, resourceRef] | |
| `canBeImpersonated` | params=[userId] | |
| `getReportDataById` | len=1 | |
| **`deleteReportDefinitions`** | **params=[reportDefIds]** (plural, array) | **BROKEN** on every tested shape. |

### `reportController` (3 methods)

| Method | Arity | Notes |
|---|---|---|
| `reGenerateReport` | params=[reportId] | |
| `getReports` | len=1 | |
| `deleteReportInstances` | params=[reportIds] | Untested — manages report RUN instances, not definitions |

### `reportScheduleController` (5 methods)

| Method | Arity | Notes |
|---|---|---|
| `getTimeZones` | len=0 | |
| `getById` | len=1 | |
| `getByReportId` | len=1 | **BROKEN** — Internal server error on valid report IDs |
| `saveOrUpdate` | len=1 | |
| `deleteSchedule` | len=1 | Untested — cannot retrieve schedules to delete |

## Test results

### Reproducing the 500 on a fresh throwaway view

Rendered a valid view XML via `vcfops_dashboards.render.render_views_xml`
for `ViewDef(name="__delete_probe_view_e9ca8904__", adapter_kind="VMWARE",
resource_kind="VirtualMachine", columns=[ViewColumn("cpu|usage_average",
"CPU Usage")])`, packaged into the standard content-zip envelope,
imported via `POST /suite-api/api/content/operations/import?force=true`.

Import summary: `{imported:1, skipped:0, failed:0, state:"FINISHED"}`.

`GET /suite-api/internal/viewdefinitions/e9ca8904-491e-4de7-80ac-6e22cfaf4a1a`
returned:
```json
{"id": "e9ca8904-491e-4de7-80ac-6e22cfaf4a1a",
 "name": "__delete_probe_view_e9ca8904__",
 "owner": "claude",
 "subjects": ["VirtualMachine", "VirtualMachine"],
 "active": true, ...}
```

**Confirms: content-zip-imported views have duplicate subjects in the
stored representation.** The framework's renderer emits two
`<SubjectType>` elements per the documented wire format (one
`type="descendant"`, one `type="self"`) and the server flattens both
into the `subjects` list, producing the duplicate.

`deleteView` on this throwaway: HTTP 200, `{type:"exception",
message:"Internal server error."}`. Verified `GET` after delete —
still HTTP 200, view still present. **Path A reproduced: the bug
fires on a fresh, just-imported view that passes every server
validation check.**

### Testing Path B (multi-step dependency-confirmation)

Called the catalog methods the UI would plausibly use during a
delete confirmation dialog:

1. `reportServiceController.getByViewIds` with `data=[[throwaway_uuid]]`:
   HTTP 200, returned `[]` (no dependents). Confirms the dependency
   lookup works and finds no dependents for the throwaway.
2. Immediately followed by `viewServiceController.deleteView` with
   `data=[throwaway_uuid]`: HTTP 200, `{type:"exception",
   message:"Internal server error."}`.

Also tested **as a single Ext.Direct batch** (three RPC calls in one
HTTP POST to `/ui/vcops/services/router`):
- `viewServiceController.getGroupedViewDefinitionThumbnails`
- `reportServiceController.getByViewIds` with `[[uuid]]`
- `viewServiceController.deleteView` with `[uuid]`

Result: the thumbnails and getByViewIds calls returned `type="rpc"`
successfully; `deleteView` still returned `type="exception",
message:"Internal server error."` in the same batch response. The
server is not checking a session-scoped "dependency was acknowledged"
flag — the delete handler just crashes immediately on dispatch.

### Extra-args variants on `deleteView`

All variants below returned `HTTP 200, type=exception, message="Internal server error."` (identical to the baseline `[uuid]` call):

| Variant label | data payload |
|---|---|
| `[uuid, true]` | `[uuid, True]` — force as second positional |
| `[uuid, false]` | `[uuid, False]` |
| `[uuid, {force:true}]` | `[uuid, {"force": True}]` |
| `[uuid, true, true]` | `[uuid, True, True]` — two booleans |
| `[{viewDefinitionKey:uuid, force:true}]` | wrapped object |
| `[{id:uuid}]` | wrapped object with id key |
| `[[uuid]]` | array-of-array (matches deleteReportDefinitions shape) |

**Conclusion:** the Ext.Direct RPC dispatcher doesn't care about arg
count or shape — the server handler method is invoked regardless and
throws before reading any inputs beyond the first positional UUID.
Passing extra args is not a fix.

### Extra-args variants on `deleteReportDefinitions`

Same result — every variant returns `Internal server error`:

| Variant label | data payload |
|---|---|
| `[[id]]` | `[[reportId]]` — matches declared `params=[reportDefIds]` |
| `[id]` | `[reportId]` — bare ID |
| `[[id], true]` | with force flag |
| `[[id], {force:true}]` | with options dict |
| `[{reportDefIds:[id]}]` | wrapped object |
| `[{reportDefIds:[id], force:true}]` | wrapped object with force |

### Testing as `admin` (VCFOPS_ADMIN)

Re-authenticated via the same UI login flow with `admin` credentials
and repeated the critical calls:

- `deleteView` on throwaway (owned by `claude`): HTTP 200, `type=exception`, Internal server error
- `deleteView` on stranded ESXi Host Active Alerts (owned by `admin`): HTTP 200, `type=exception`, Internal server error
- `deleteView` on stranded VM Snapshot Details (owned by `admin`): HTTP 200, `type=exception`, Internal server error
- `deleteReportDefinitions` on both stranded reports with both `[[id]]` and `[id]` shapes: all return Internal server error

**Ownership is not the cause.** Even the `admin` user cannot delete
any of these items via the RPC layer.

### REST internal endpoint

- `DELETE /suite-api/internal/viewdefinitions/{uuid}` with
  `X-Ops-API-use-unsupported: true` header: HTTP 500
  `{"type":"Error","message":"Internal Server error, cause unknown.","httpStatusCode":500,"apiErrorCode":500}` on both the throwaway and the stranded views.
- `DELETE /suite-api/api/reportdefinitions/{id}`: HTTP 500 on both stranded reports.

Confirms the REST delete layer wraps the same broken server code path
as the Ext.Direct layer.

### Other broken methods on the same controllers

While probing we also confirmed these methods are broken on this
instance (they all return `{type:"exception", message:"Internal
server error."}`), supporting the theory that there is a broader
server-side issue with these two controllers, not a specific delete
bug:

- `reportServiceController.getReportDefinitionThumbnails([{start,limit}])`
- `reportServiceController.isReportDefinitionEmpty(reportId)`
- `reportScheduleController.getByReportId(reportId)`
- `viewServiceController.saveOrUpdateViewDefinition(minimalPayload)`

Methods on the same controllers that DO work:

- `viewServiceController.getGroupedViewDefinitionThumbnails([])` — returns 1023 items
- `reportServiceController.getByViewIds([[uuid]])` — returns dependent report names
- `reportServiceController.getReportDefinitionNameById(id)` — returns report name

The pattern strongly suggests a Java service initialization failure
or a broken bean wiring somewhere in the report/view service layer —
methods that don't touch the broken code path work fine, methods
that do fail with the generic "Internal server error" wrapper.

## Key data points that refute the hypothesis

1. **No dependency-check method exists** in the Ext.Direct catalog for
   views (all 23 viewServiceController methods listed above).
2. **No force-variant of `deleteView`** exists (only the single
   `len=1` signature).
3. **`deleteView` fails identically** whether called alone, after
   `getByViewIds`, or inside a batch with both. The server doesn't
   track a "dependency acknowledged" flag per session.
4. **The fresh throwaway has zero dependents** (`getByViewIds`
   returned `[]`) yet delete still fails. The bug is not about
   "crashes when dependents exist".
5. **The stranded views have zero or minimal dependents** and delete
   still fails.
6. **`admin` cannot delete either.** Even the account with full
   privileges hits the same 500.
7. **Duplicate subjects are NOT the root cause**: stranded view
   `c192d4d6-...` has `subjects: ["alert"]` (single entry) and
   stranded view `36ff8c15-...` has `subjects: ["VirtualMachine"]`
   (single entry), yet both fail delete with the same error as the
   throwaway which does have duplicates. The earlier
   duplicate-subjects theory in
   `memory/project_view_delete_server_bug.md` explained the framework
   renderer's behavior (correct — the renderer emits two SubjectType
   elements that the server flattens into duplicates), but did NOT
   correctly identify the root cause of the delete failure. The
   delete handler is broken independently.

## What IS the bug, then?

Based on the evidence, the most likely explanation is:

**The `viewServiceController.deleteView` and
`reportServiceController.deleteReportDefinitions` Java handlers are
broken at the server bean/service layer in this specific VCF Ops
9.0.2 build.** Multiple sibling methods on the same controllers also
return the same generic "Internal server error" (e.g.
`getReportDefinitionThumbnails`, `isReportDefinitionEmpty`,
`getByReportId`, `saveOrUpdateViewDefinition`), while methods that
avoid the broken code path work fine (`getByViewIds`,
`getReportDefinitionNameById`, `getGroupedViewDefinitionThumbnails`).
This is the signature of a bean wiring failure, a missing
dependency, or an exception during initialization of part of the
report/view service — the server returns the canned
"Internal server error" wrapper and logs the real stack trace
somewhere we can't see from the API layer.

There is no client-side protocol change that can work around this.
The only viable options are:

1. **Manual cleanup via the VCF Ops web console** (documented as
   the workaround in `context/dashboard_delete_api.md §View delete
   limitation`).
2. **Upgrade the VCF Ops instance** to a build that fixes the
   broken handlers.
3. **File a vendor support ticket** citing the specific broken
   method names and ask whether a patch exists.

## State of the 4 stranded items after this investigation

| Item | ID | Status |
|---|---|---|
| ESXi Host Active Alerts list view | `c192d4d6-50b9-49cf-a9d5-fe53c9f5134a` | **Still stranded.** Owner: `admin`. Subjects: `["alert"]`. |
| VM Snapshot Details list view | `36ff8c15-e47d-4285-b0f3-3ce9dda00ae6` | **Still stranded.** Owner: `admin`. Subjects: `["VirtualMachine"]`. |
| ESXi Host Active Alerts report | `02fb7e8e-e14e-4cdb-853f-367ce097bc47` | **Still stranded.** |
| VM Snapshot Details Report | `f524e76b-67aa-4092-a49b-6c742e45ad4f` | **Still stranded.** |

Plus, this investigation **added one new stranded item** it could not
clean up:

| New stranded item | ID | Status |
|---|---|---|
| `__delete_probe_view_e9ca8904__` (throwaway from this probe) | `e9ca8904-491e-4de7-80ac-6e22cfaf4a1a` | **Stranded.** Owner: `claude`. Subjects: `["VirtualMachine", "VirtualMachine"]`. Rendered with the repo's own renderer via `ViewDef(adapter_kind="VMWARE", resource_kind="VirtualMachine", columns=[ViewColumn("cpu|usage_average","CPU Usage")])` and imported through the standard envelope path. |

All five items require manual cleanup via the VCF Ops web console
(Environment → Views / Manage → Reports → Report Definitions). They
are identifiable in the UI by their pre-existing community names
plus the probe prefix `__delete_probe_view_` for the new one. None
carries the `[VCF Content Factory]` prefix (the probe used an
underscore prefix to stay distinguishable from real factory content).

## Implications for `install.py::UIClient.delete_view`

**No code change can fix this.** The current single-positional-UUID
call shape is correct per the declared `deleteView(len=1)` signature
in api.js. The existing error handling in the UIClient
(which logs the exception and treats the operation as a partial
failure) is the right behavior — uninstall scripts should continue
to report a WARN for each view/report they cannot delete and exit
with partial-failure status.

**Note for tooling:** if `tooling` revisits this code path, the
correct stance is:
1. Keep `delete_view` as-is.
2. Keep `delete_dashboards` as-is (dashboards work via `deleteTab`).
3. Update the user-visible error message to cite this file instead
   of just "VCF Ops server bug": point users to
   `context/view_delete_dependency_protocol.md` for the full
   evidence dump.
4. Optionally detect the pattern and skip the RPC call entirely
   when the build version matches the known-broken 9.0.2 range —
   saves a round trip per stranded view on uninstall. (Cosmetic;
   not load-bearing.)

## Notes for the memory file

`memory/project_view_delete_server_bug.md` currently cites the
"duplicate subjects" theory as the root cause. That theory is
**partially correct but incomplete**:

- Correct: content-zip-imported views DO have duplicate subject
  entries (`["VirtualMachine", "VirtualMachine"]`) in the server's
  stored representation.
- Incorrect: that is NOT why `deleteView` fails. `deleteView` fails
  the same way on views with single-subject lists (`["alert"]`,
  `["VirtualMachine"]`) when those views are also content-zip-imports
  from community packages. And failures are identical across both
  the `claude` and `admin` accounts.

The memory file should be updated to:
1. Drop the "duplicate subjects is the cause" claim.
2. Cite "server-side handler is broken; method returns Internal
   server error regardless of input" as the root cause.
3. Point to this file for the evidence chain.

## Investigation artifacts (scratch, not committed)

All probe scripts live under `/tmp/view_delete_probe/`:
- `fetch_api_js.py` — pulls the Ext.Direct catalog
- `probe.py` — Phase 1 (stranded views, getByViewIds, throwaway,
  extra-args)
- `probe2.py` — list views, schema discovery
- `probe3.py` — real-renderer throwaway view + delete test
- `probe4.py` — full JSON dump of all target views
- `probe5.py` — repeat tests as `admin`
- `probe6.py` — UI asset URL probing
- `probe7.py` — batch-RPC and form-encoded variants
- `probe8.py` — report schedule checks
- `api.js` — the full captured catalog (2805 bytes)

These are all throwaway scripts. None need to be committed.

## Hypothesis verdict

**REFUTED.** There is no dependency-confirmation protocol gap in
`install.py`. The current single-UUID call shape is correct per the
declared API. The HTTP 500 is a server-side handler crash in VCF
Ops 9.0.2 that reproduces on every view and every report across
every client shape and every caller account, independent of
ownership, subject duplication, or actual dependency state.
