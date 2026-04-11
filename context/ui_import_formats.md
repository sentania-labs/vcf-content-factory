# UI "drag-drop" per-object import formats for VCF Ops 9.0.2

Reconnaissance log for the distribution-package drop-in artifacts
(`Dashboard.zip`, `Reports.zip`, `AlertContent.xml`). Investigated
2026-04-11 against `vcf-lab-operations.int.sentania.net` (VCF Ops
9.0.2.0). All findings below were empirically verified by building
test envelopes, POSTing them, and reading back the resulting state.

## TL;DR for the packager

| Drop-in artifact | Recommendation |
|---|---|
| `Dashboard.zip` | Emit `dashboard/dashboard.json` with `userId`/`lastUpdateUserId` set to the nil UUID `00000000-0000-0000-0000-000000000000`. The server **rewrites both fields** to the authenticated user's UUID on import and ignores the inner values entirely — even the literal string `"PLACEHOLDER_USER_ID"` imports cleanly. The nil UUID is the lowest-friction stub because it is obviously non-functional and unlikely to be confused with a real owner. |
| `Reports.zip` | Inner `content.xml` at zip root, containing one `<Content>` with both `<Views>` and `<Reports>`. Reports wire format has **no user/owner fields** — nothing to stamp. The importer walks the `<Views>` section implicitly and imports referenced views alongside reports even when the envelope only declares `REPORT_DEFINITIONS`. |
| `AlertContent.xml` | Always emit adapter **key** form (`adapterKind="VMWARE"`, `adapterKind="VMWARE_INFRA_HEALTH"`, `adapterKind="vCenter Operations Adapter"` for the `vCops` adapter, etc.). The importer stores whatever string you give it verbatim with no validation, so display-name fallback is unsafe — a bogus string like `"VMware vCenter"` (not a real key on this instance) imports cleanly but produces an orphaned symptom/alert. There is no per-adapter special case needed — our serializer's existing behavior (YAML `adapterKind:` verbatim to XML) is correct. |

## Setting the stage — where the imports actually go

**There is no per-object REST import endpoint for dashboards, views,
reports, symptoms, alerts, or recommendations.** Confirmed by
grepping both `docs/operations-api.json` and `docs/internal-api.json`
for multipart/form-data POST endpoints. The only content-zip surface
is:

- `POST /api/content/operations/import` — bulk content-zip importer
  (requires a specific envelope shape — see below).
- `POST /api/policies/import` (+ internal twin) — policy XML only.

The legacy Struts UI's `dashboard.action?mainAction=uploadDashboard`
is present in 9.0.2 but **the handler is broken**: any multipart POST
returns `{"success":false, "msg":"Unable to import dashboard
resultDto is null ."}` regardless of field name. The Ext.Direct
`uploadContentController.uploadFile` form handler runs but returns
HTTP 500 "Internal server error". Neither is a viable import path.
Verified experimentally with ~15 field-name and parameter-placement
permutations.

The new SPA UI's "Manage > Dashboards > Import" dialog must
therefore wrap drag-dropped community zips in a bulk content-zip
envelope client-side and call `POST /api/content/operations/import`.
Our install scripts already do this — the drop-in artifacts we ship
are whatever *inner* format admins recognize from community reference
packages; the UI layer is responsible for wrapping them.

## The content-zip envelope shape that actually works

Verified by round-tripping a real export (`GET /api/content/operations
/export/zip` with `contentTypes=["DASHBOARDS"]`) and comparing against
hand-crafted envelopes. The importer rejects anything that deviates.

```
<marker>L.v1              # 19-digit timestamp + literal "L.v1"; content = owner UUID
configuration.json        # {type:"CUSTOM", <typeKey>:<count>, ...}
dashboards/               # empty directory entry (required)
dashboardsharings/        # empty directory entry (required, even when unused)
dashboards/<owner-uuid>   # zip containing dashboard/dashboard.json + resource stubs
dashboardsharings/<owner-uuid>   # JSON array of sharing entries
usermappings.json         # {sources:[], users:[{userName, userId}]}
```

For other content types the flat root members change:

- `views.zip` — inner `content.xml` with `<Content><Views>…</Views></Content>`
- `reports.zip` — inner `content.xml` with `<Content><Views>…</Views><Reports>…</Reports></Content>`
- `alertdefs.xml` — flat XML, root `<alertContent><AlertDefinitions>…`
- `symptomdefs.xml` — flat XML, root `<alertContent><SymptomDefinitions>…`
- `recommendationdefs.xml` — flat XML, root `<alertContent><Recommendations>…`
- `supermetrics.json` — flat JSON
- `customgroup.json` / `customgroups.json` — flat JSON

### Marker filename = per-instance fingerprint (!)

**This is the #1 gotcha.** The marker filename is the 19-digit
timestamp (nanoseconds) followed by `L.v1`. The VCF Ops importer
stores a fingerprint value per cluster and **rejects any import
whose marker filename doesn't match** — returns `INVALID_FILE_FORMAT`
with no details. Observed: on this lab instance the valid marker is
`6844548499441080431L.v1`. Using `time.time_ns() + "L.v1"` or any
other value makes every import fail. The `vcfops_dashboards.client`
module already handles this via `discover_marker_filename()` — it
triggers a throwaway `SUPER_METRICS` export, downloads the zip, and
reads the `*L.v1` entry name. Anyone hand-testing envelope imports
must use that function or copy the marker filename from a real
export on the same instance.

### usermappings.json controls owner attribution, not the inner JSON

Verified by four controlled imports of the same dashboard JSON with
distinct `userId` / `lastUpdateUserId` values, then exporting and
diffing what the server stored:

| inner `userId` / `lastUpdateUserId` | Envelope owner (`usermappings.json`) | Import result | Server-stored `userId` after round-trip |
|---|---|---|---|
| `0c44e115-...` (admin UUID) | admin | SUCCESS | `0c44e115-...` |
| `00000000-...` (nil UUID) | admin | SUCCESS | `0c44e115-...` (rewritten) |
| `"PLACEHOLDER_USER_ID"` (literal string) | admin | SUCCESS | `0c44e115-...` (rewritten) |
| `c60c3223-...` (foreign UUID from reference repo) | admin | SUCCESS | `0c44e115-...` (rewritten) |

In every case the server (a) accepted the import without validating
the inner user fields and (b) rewrote both `userId` and
`lastUpdateUserId` to the envelope's declared owner. This matches
the prior finding in `context/dashboard_delete_api.md` that
content-zip imports always force `owner=admin` and `locked=true`
regardless of the importing user or the usermappings.json contents.

**Implication for the Dashboard.zip drop-in:** the UI layer that
wraps our Dashboard.zip in an envelope will set the owner to
the *currently authenticated admin user*. Whatever string we put in
the inner JSON's `userId` / `lastUpdateUserId` is thrown away. The
nil UUID `00000000-0000-0000-0000-000000000000` is a good stub
because it's obviously non-functional and matches the builder's
current behavior (`vcfops_packaging/builder.py::_build_dashboard_dropin_zip`).
`"PLACEHOLDER_USER_ID"` as a literal string also works but looks
wrong and may confuse admins who inspect the inner JSON.

### Dashboard.zip community wire shape (reference-compatible)

From `references/AriaOperationsContent/*` dashboard zips:

```
Dashboard-<name>.zip
+-- dashboard/
    +-- dashboard.json         # single top-level entries/dashboards/uuid object
    +-- resources/             # optional, for i18n; can be empty stubs
        +-- resources.properties
        +-- resources_es.properties
        +-- resources_fr.properties
        +-- resources_ja.properties
```

The builder currently writes exactly this (see
`vcfops_packaging/builder.py::_build_dashboard_dropin_zip`). No
changes needed beyond keeping the nil UUID swap.

### Reports drop-in shape

From `references/brockpeterson_operations_reports/*.zip`:

Two community conventions exist:

1. **Flat** (`ESXi Host Active Alerts.zip`, `VM Snapshot Details Report.zip`):
   top-level zip contains exactly `content.xml`. The `<Content>` root
   holds both `<Views>` and `<Reports>` with the referenced views
   inline, so a single zip carries the report and its dependencies.
2. **Nested** (`All Active Critical Alerts Report and View.zip`):
   outer zip contains two inner zips (`*View.zip`, `*Report.zip`),
   each with its own `content.xml`. Each inner zip holds exactly one
   content type.

Either format works if the UI layer wraps them in an envelope
correctly. **Our packager should pick the flat form** —
`Reports.zip` containing `content.xml` with both `<Views>` and
`<Reports>` — because it keeps dependent views in the same payload
and matches `reports_content.xml` that the installer already
generates. Verified by importing both reference zips: the flat
form imports a report + its referenced view in one operation, and
the view is reachable via `GET /internal/viewdefinitions/<uuid>`
after the import completes.

Reference report `content.xml` files contain **zero user/owner
fields** (grepped for `user|owner|created|modified` — no matches).
Reports do not need user stamping.

### Do reports need views installed first?

No — tested by importing the `ESXi Host Active Alerts` report,
which references view `c192d4d6-50b9-49cf-a9d5-fe53c9f5134a`, onto
a fresh slate. The view was imported alongside the report in the
same operation despite the envelope's `configuration.json` only
declaring `reports:1`. The importer walks the `<Views>` section of
`content.xml` regardless. Admins can ship a single `Reports.zip`
and don't need to hand-import `Views.zip` first.

### Report delete API is broken (know before shipping)

All three report-delete paths return HTTP 500 on this VCF Ops 9.0.2
build:

- `DELETE /api/reportdefinitions/{id}` — 500 "Internal Server error, cause unknown."
- Ext.Direct `reportServiceController.deleteReportDefinitions` — `{type:"exception", message:"Internal server error."}`
- There is no `DELETE /internal/reportdefinitions/{id}` endpoint.

Matches the known-issue note in the recap plan and in
`context/reports_api_surface.md`. Uninstall of `Reports.zip`
drop-ins must be manual (web console).

## adapterKind: key vs display name in AlertContent.xml

Plan open question: the UI-exported `tmp/Alert Definition-2026-04-11
03-54-10 PM.xml` uses `adapterKind="vCenter Operations Adapter"`
(looks like a display name) while our serializer emits
`adapterKind="VMWARE"` (key form). Is the UI picky?

**Answer: always emit the adapter key. The display-name confusion
in the tmp export is a coincidence — the `vCenter Operations
Adapter` string is actually the adapter KEY, not the display name.**

Verified by querying `GET /api/adapterkinds` on the lab instance:

| Adapter key | Display name |
|---|---|
| `VMWARE` | `vCenter` |
| `VMWARE_INFRA_HEALTH` | `Infrastructure Health` |
| `VMWARE_INFRA_MANAGEMENT` | `Infrastructure Management` |
| `vCenter Operations Adapter` | `VCF Operations Adapter` |
| `FDR_vCenter Operations Adapter` | `FDR_vCenter Operations Adapter` |
| `VcfAdapter` | `VMware Cloud Foundation` |
| `vRealizeOpsMgrAPI` | `VCF Operations API` |
| `VrAdapter` | `VMware Aria Automation` (prefix `VrAdapter`) |
| `FederatedAdapter` | `Aggregator Adapter` |

Note the two highlighted cases:

- `VMWARE` adapter's **display name is `vCenter`** (one word, no
  "VMware" prefix). The string `"VMware vCenter"` that looks like a
  plausible display name is **not** anywhere in the adapter catalog.
- The `vCops`/Platform Safeguards adapter's **key** is literally
  `"vCenter Operations Adapter"` — spaces and all — and its display
  name is `"VCF Operations Adapter"`. The tmp export using
  `adapterKind="vCenter Operations Adapter"` was using the key.

**Direct import test** — imported three minimal SymptomDefinitions
through the envelope-wrapped bulk importer, each with a different
adapterKind string, and checked the server-stored `adapterKindKey`:

| Input `adapterKind=` | Envelope import result | Server-stored `adapterKindKey` | Real adapter on instance |
|---|---|---|---|
| `"VMWARE"` | SUCCESS | `VMWARE` | YES (matches key) |
| `"vCenter"` | SUCCESS | `vCenter` | Only as display name of `VMWARE` — does not match any key |
| `"VMware vCenter"` | SUCCESS | `VMware vCenter` | Does not match any key OR any display name — **orphan** |

**The importer has no validation.** It stores the string verbatim
in `adapterKindKey`. If the string doesn't match a real adapter,
the symptom/alert is technically orphaned (no adapter to evaluate
against). The import still "succeeds" from the importer's point of
view, which is a trap: authors who emit display names get
silently-broken content.

**Safe rule for the YAML→AlertContent serializer:** pass
`adapterKind:` YAML values straight through to the XML without
normalization. Authors are responsible for using the exact key,
and `ops-recon` should verify adapter keys against
`GET /api/adapterkinds` before authoring. No lookup table is
needed — there is no adapter for which the key form fails.

## Unreachable / irrelevant paths investigated

Documented so future investigations don't retread these.

- **`GET /api/dashboards`, `GET /api/views`** — do not exist (404).
  All dashboard/view REST operations go through
  `/api/content/operations/{import,export}`.
- **`POST /api/reportdefinitions`, `PUT /api/reportdefinitions/{id}`**
   — do not exist. Reports are create-only via content-zip. Confirms
   the note in `context/reports_api_surface.md`.
- **`/vcf-operations/ui/`** — redirects to legacy login but the SPA
  landing path returns 404 even after auth (as both `claude` and
  `admin` service accounts). Browsing the new UI bundle isn't
  possible from a non-interactive session without a full browser.
  Not needed for these findings anyway — the REST surface is the
  source of truth for what the UI can and can't do.
- **`/ui/vcops/services/api.js`** — lists the Ext.Direct router
  controllers. `uploadContentController.uploadFile` is a form
  handler but returns HTTP 500 on all tested inputs.
  `dashboardServiceController` does not exist (no unlock or delete
  methods, all RPC calls return `type: "exception"`).

## Test artifacts left behind

Cleanup was attempted for all test objects. Known-stuck artifacts
due to the VCF Ops 9.0.2 server bug where content-zip-imported views
and reports cannot be deleted through any API:

- **Views (2):** `c192d4d6-50b9-49cf-a9d5-fe53c9f5134a` (ESXi Host
  Active Alerts list view) and `36ff8c15-e47d-4285-b0f3-3ce9dda00ae6`
  (VM Snapshot Details list view). Both `viewServiceController.
  deleteView` and `DELETE /internal/viewdefinitions/{uuid}` return
  HTTP 500. Matches the pre-existing bug noted in
  `context/dashboard_delete_api.md §View delete limitation`.
- **Reports (2):** `02fb7e8e-e14e-4cdb-853f-367ce097bc47` (ESXi
  Host Active Alerts) and `f524e76b-67aa-4092-a49b-6c742e45ad4f`
  (VM Snapshot Details Report). `DELETE /api/reportdefinitions/{id}`
  and Ext.Direct `reportServiceController.deleteReportDefinitions`
  both return HTTP 500.

These four objects require manual cleanup through the VCF Ops web
console (`Manage > Views`, `Manage > Reports > Report Definitions`).
They are identifiable by their pre-existing community names —
neither carries the `[VCF Content Factory]` prefix.

All dashboards (5) and symptoms (3) created during the investigation
were successfully deleted.

## Recommendations for the distribution package refactor

1. **`Dashboard.zip`** — no changes. The builder's current code at
   `vcfops_packaging/builder.py::_build_dashboard_dropin_zip` (which
   substitutes `NIL_UUID` for `PLACEHOLDER_USER_ID` and adds
   resource stubs) is exactly right. Document that the inner user
   IDs are intentional stubs and will be rewritten at import.

2. **`Reports.zip`** — flat zip, inner `content.xml` with `<Content>
   <Views>…</Views><Reports>…</Reports></Content>`. No user field
   handling needed. Keep views inline to avoid ordering gotchas.
   This matches what `_build_reports_dropin_zip` currently does.

3. **`AlertContent.xml`** — serializer should emit YAML
   `adapterKind:` values verbatim. No lookup table. ops-recon's
   adapter-key verification is the authoring-time safety net.
   Package the three logical sections (`<SymptomDefinitions>`,
   `<AlertDefinitions>`, `<Recommendations>`) inside a single
   `<alertContent>` root as currently implemented — this is the
   "merged" shape; the envelope importer wants them as three
   separate files (`symptomdefs.xml`, `alertdefs.xml`,
   `recommendationdefs.xml`) but that's the installer's job, not
   the drop-in's. The unified `AlertContent.xml` drop-in is for
   admins who use whatever UI path wraps it into the envelope.

4. **Deferred / out of scope for this task:** actually verifying
   that the new SPA's drag-drop dialogs consume these specific
   drop-in shapes. The only programmatic path we can exercise
   against 9.0.2 is the REST bulk importer with the envelope,
   and we've verified the server-side behavior is consistent with
   what we ship. Final visual-drag-drop confirmation is a
   `qa-tester` task with a real browser on the lab instance.

## Appendix — notes on the UI session layer for future use

While probing `uploadDashboard`, verified the following about the
legacy Struts `.action` surface in 9.0.2:

- `mainAction=uploadDashboard` returns `{"success":false, "msg":"
  Unable to import dashboard resultDto is null."}` for every tested
  multipart field name (`file`, `dashboardFile`, `fileUpload`,
  `uploadFile`, `contentFile`, `dashboardZip`, `upload`,
  `dashboardFileName`, `dashboardFileToUpload`, `fileToUpload`,
  `import`, `dashboardUpload`) when called with the secureToken in
  the query string (which is the only positioning that doesn't
  return HTTP 400 outright).
- When secureToken is posted as a form field alongside a multipart
  file, Struts returns HTTP 400 with an empty body — the multipart
  parser rejects the combination outright.
- `mainAction=uploadContent`, `importDashboard`, `importView`,
  `uploadView`, `importReport`, `uploadReport` on `dashboard.action`
  are not real actions; they return the Ext.JS skeleton HTML page
  (unauthed/unknown mainAction fallback).

All of this suggests the legacy `/ui/dashboard.action` import
handler is either dead code in 9.0.2 or requires a session-specific
context we can't reproduce from an API client.

For the UI session auth flow itself (how to acquire `JSESSIONID` +
`OPS_SESSION` + `csrfToken`), see `context/dashboard_delete_api.md`.
That pattern is reusable for any investigation that needs to drive
the `dashboard.action` or `vcops/services/router` endpoints.
