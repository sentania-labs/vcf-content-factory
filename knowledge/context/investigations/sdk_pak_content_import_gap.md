# SDK Pak Bundled Content Import Gap — vcommunity v5 silent zero-import

**Date:** 2026-06-16
**Pak under investigation:** `dist/vcfcf_sdk_vcommunity.1.0.0.5.pak`
(adapter kind `vcfcf_vcommunity`, pak display `VCF Content Factory vCommunity`)
**Symptom appliance:** vcf-lab-operations-devel
**Posture:** read-only. No install/sync/mutation performed. Temp pak
extraction under `/tmp/vcomm_probe` created and removed; clean-up verified.

---

## TL;DR / root cause

**Declaration-missing is NOT the cause.** There is no manifest content
key — VCF Ops imports bundled content by *directory presence*, processed
inside **step 15 `APPLY_ADAPTER`** (SolutionManager `ContentImport`), not
by any `content`/`content_files`/`pak_content` manifest field. The
vcommunity v5 manifest is byte-structurally equivalent to the
known-working compliance v22 manifest. (See spec/18 and
`v20-step5-silent-drop.md` §"Corrected diagnosis".)

The zero-import has **two independent, compounding causes**:

1. **Unproven content types in a pak (the primary, by-design gap).**
   The *only* content type ever proven to import via an SDK (Track C)
   pak in this factory is **dashboards + views** — and only after
   compliance v22 added the four localization bundles
   (`knowledge/lessons/pak-content-localization-bundles.md`). **No SDK pak has
   ever successfully bundled supermetrics, symptomdefs, or alertdefs.**
   Compliance never shipped them in any pak (`v22`, `v41`, `v51` all ship
   only `content/dashboards/` + `content/reports/` + `content/resources/`).
   The SMs/symptoms that appear on instances for compliance and vcommunity
   were put there by **separate factory direct sync**
   (`python3 -m vcfops_supermetrics sync`, etc.), never by pak install.
   vcommunity v5 is the **first** SDK pak to attempt SM + symptomdef +
   12 dashboards + 96 views in one pak.

2. **A poison record aborts the whole content tree (the acute trigger).**
   The content importer does an all-or-nothing walk: per
   `knowledge/lessons/pak-content-localization-bundles.md`, a single absent
   localization key or a single unresolvable reference **aborts the entire
   content tree** for the pak — every dashboard/view/SM included. The
   analytics log line `Cannot find Symptom Definition with Id
   SymptomDefinition-VMWARE-ESXi_Host_NIC_Disconnected` is that abort
   signal. Our symptomdef carries a **derived slug ID**
   (`SymptomDefinition-VMWARE-ESXi_Host_NIC_Disconnected`) where the
   working corpus convention (original vmbro pack) is a **UUID ID**
   (`SymptomDefinition-c8d1e671-...`). A reference to the slug ID cannot
   resolve, the walk aborts, and **nothing else in `content/` lands** —
   producing the silent 0/96 views, 0/12 dashboards, 0/2 SMs.

So: **not** declaration-missing, **not** layout-malformed (bindings are
correct — see below), **not** a localization-key mismatch on the
dashboards themselves. It is **separate-sync-by-design for SM/symptom
content** *plus* **a poison symptomdef record that takes the rest of the
tree down with it**.

---

## Question 1 — what triggers content import on pak install?

**Directory presence, processed in step 15, no manifest declaration.**

- Spec/18 (authoritative): *"The outer pak's `content/` directory is the
  declarative content manifest. The platform's pak installer
  auto-processes well-known subdirectory names and imports their
  contents."* There is **no** `content` / `content_files` / `pak_content`
  manifest key — none exists in the platform and none of the 51-pak
  corpus declares one.
- `v20-step5-silent-drop.md` corrects an early hypothesis: the
  orchestrator step that *names itself* content-deploy (step 5,
  `DeployNewUpgradeContentOperation`) is **irrelevant** to solution paks —
  its `shouldRun()` is literally `return detail.isContainsSystemUpdate();`,
  true only for OS/system-update paks. For SDK adapter paks, content is
  delivered by **step 15 `APPLY_ADAPTER` →
  `DistributedTaskInstallUninstallAdapters` → `ContentImport.importFile`**.
- Manifest comparison confirms no declaration gap:

  | field | vcommunity v5 | compliance v22 (works) |
  |---|---|---|
  | `adapters` | `["adapters.zip"]` | `["adapters.zip"]` |
  | `adapter_kinds` | `["vcfcf_vcommunity"]` | `["vcfcf_compliance"]` |
  | content key | (none) | (none) |
  | `overview.packed` at root | present (2123 B) | present |

  Identical shape. There is nothing to add to `manifest.txt`.

## Question 2 — comparison against working references

**(a) Original vmbro `VCFOperationsvCommunity` (Python Integration SDK,
Track B).** Source tree at
`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/`. It is *source*
(not a built pak): `content/` with `alertdefs/ customgroups/ dashboards/
files/ policies/ recommendations/ reports/ resources/ supermetrics/
symptomdefs/ traversalspecs/`. Two structural differences from our output
that matter:

  - **Symptomdef IDs are UUIDs.**
    `content/symptomdefs/ESXi Host NIC Disconnected Symptom.xml` →
    `id="SymptomDefinition-c8d1e671-d0ea-489f-acc4-46e34cc246b6"`. Our
    builder emits `id="SymptomDefinition-VMWARE-ESXi_Host_NIC_Disconnected"`
    (a derived slug). The platform's symptom resolver looks up by the
    declared ID; a slug ID that nothing else registers under the same
    string fails to resolve. **This is the proximate cause of the abort
    log line.**
  - **Dashboards are flat `content/dashboards/<Name>.json`**, not
    `content/dashboards/<Dir>/dashboard.json`. (Both flat and
    subdir-`dashboard.json` are accepted per spec/18; this is not itself
    the fault — compliance v22 uses the subdir form and imports fine — but
    it confirms our subdir layout is acceptable.)

**(b) compliance + synology SDK paks — did THEIR bundled content import?**
Decisive negative result that resolves the "missing declaration vs
never-worked" fork:

  - **No compliance pak ever bundled SM/symptom/alert content.** `v22`,
    `v41`, `v51` ship **only** `content/dashboards/`, `content/reports/`,
    `content/resources/`. The compliance symptoms/SMs/recs visible on prod
    came from **describe.xml (step 15)** for the alert/symptom/rec
    (Pass-28 confirmed `AlertDefinition`/`SymptomDefinition`/`Recommendation`
    register via describe.xml), and from **separate factory sync** for SMs
    — never from a `content/supermetrics/` or `content/symptomdefs/` pak
    payload.
  - **The only pak-bundled content type proven end-to-end is dashboards +
    views**, and only since compliance v22 added the four localization
    bundles. Before v22 (e.g. v20) even those silently dropped.

  Conclusion on the fork: **SDK-pak import of SM/symptom content has never
  actually worked because it has never been attempted** — those types have
  always been synced separately or routed through describe.xml. The factory
  has zero evidence that `content/supermetrics/` or `content/symptomdefs/`
  in an SDK pak imports at all. vcommunity v5 is the calibration case, and
  it failed.

## Question 3 — localization (attempted-and-failed vs not-attempted)

The vcommunity v5 dashboards/views are **structurally correct and would be
importable** on their own — this was an *abort*, not a not-attempted skip,
and not a localization-key mismatch:

  - `content/resources/resources.properties` present (740 B, non-empty).
  - Per-dashboard `content/dashboards/<Dir>/resources/resources.properties`
    present for all 12.
  - Per-view `content/reports/<Dir>/resources/content.properties` present
    for all 96.
  - Dashboard binding (Pass-28 A1) **correct**:
    `entries.adapterKind = [{internalId:"adapterKind:id:0_::_",
    adapterKindKey:"vcfcf_vcommunity"}]` and `dashboards[].adapterName =
    "vcfcf_vcommunity"`.
  - View binding (Pass-28 A2) **correct**: every ViewDef carries an
    owning-adapter `<SubjectType adapterKind="vcfcf_vcommunity"
    resourceKind="vCommunityWorld" .../>` plus the cross-MP VMWARE subjects.
  - `overview.packed` (A0) present, same `overview/{light,dark}/overview.html`
    structure as the working compliance v22.

The import was **silent (no `Localization for key <x> is absent`)** — which
the localization lesson explicitly calls the fingerprint of *abort before
per-key validation*, i.e. the tree was killed by a different error first.
That different error is the symptom-ID resolution failure. So: **attempted,
then aborted by a poison record** — not a localization mismatch, and not
not-attempted.

> One latent secondary risk worth noting for the fix: the vcommunity
> dashboard `entries.resourceKind` lists **only** `HostSystem`/`VMWARE`,
> whereas the working compliance v22 dashboard lists its **own**
> `ComplianceWorld`/`vcfcf_compliance` resourceKind *first*, then the VMWARE
> cross-MP kind. If, after the symptom poison is removed, dashboards still
> drop, add the owning `vCommunityWorld`/`vcfcf_vcommunity` entry to
> `entries.resourceKind` to match the proven compliance shape. (Not
> confirmed as a blocker — the symptom abort masks everything downstream —
> but it is the next thing to check.)

## Question 4 — the fix path (exact mechanism + location)

No manifest change. No layout change. No post-install script. Two concrete
changes, in priority order:

**FIX A — stop bundling unproven content types in the SDK pak.** Remove
`content/supermetrics/` and `content/symptomdefs/` from the pak payload and
keep delivering those via the proven channels:
  - **Supermetrics:** factory direct sync (`python3 -m vcfops_supermetrics
    sync`) — the existing, working path. (Only 1 of 39 corpus Track C paks
    ever shipped pak SMs at all; spec/18 §6 calls pak SMs "rarely needed —
    usually defined post-install.")
  - **Symptom/alert definitions:** route through **describe.xml inside
    `adapters.zip`** (step-15, the *proven* path per Pass-28 A5:
    *"VCF-CF should default to placing alert/symptom/recommendation
    definitions in describe.xml … rather than `content/alertdefs/` until
    the content-side path is separately validated"*), **not**
    `content/symptomdefs/`.
  This alone unblocks the dashboards + views (the 96 + 12), which are the
  proven-importable payload, by removing the poison record that aborts the
  tree.

**FIX B (required if symptomdefs are kept in `content/` at all) — emit a
resolvable symptom ID.** The SDK builder's symptomdef generator must emit
`id="SymptomDefinition-<uuid>"` (UUID, matching the original vmbro
convention and the platform resolver), **not** the derived slug
`SymptomDefinition-<adapterKind>-<slug>`. Any alertdef `<Symptom
ref="...">` must reference that **same** ID string. Location: the SDK
builder's symptomdef/alertdef XML emitter (the same generator family as the
localization emitters in `vcfops_managementpacks/sdk_builder.py`). Without a
matching, resolvable ID, the importer aborts the entire `content/` tree.

**Recommended path:** FIX A. It is the smaller change, aligns with every
proven precedent in the corpus, and ships the dashboards/views that are the
actual deliverable. Treat pak-bundled `content/supermetrics/` and
`content/symptomdefs/` as an **unproven capability** that needs its own
calibration pak before relying on it.

---

## Discriminator summary (the asked-for verdict)

| Hypothesis | Verdict |
|---|---|
| Missing manifest content declaration | **Rejected** — no such key exists; manifests match the working pak. |
| Content layout malformed | **Rejected** — A0/A1/A2 bindings + four localization bundles all correct. |
| Localization key mismatch (attempted-and-failed) | **Rejected** — import was silent; no `Localization for key` error. |
| Poison record aborts the tree | **Confirmed (acute trigger)** — unresolvable symptom ID `SymptomDefinition-VMWARE-ESXi_Host_NIC_Disconnected` aborts the whole `content/` walk. |
| SM/symptom pak-import never worked (separate-sync-by-design) | **Confirmed (underlying gap)** — no SDK pak has ever imported SM/symptom content; only dashboards+views are proven. |

## Clean-up

Read-only. Temp extraction `/tmp/vcomm_probe` removed; verified gone. No
repo content, no `vcfops_*/`, no live Ops state modified.

## Follow-ups

- After FIX B install, confirm 96 views + 12 dashboards land and the symptom
  definitions register under their UUID IDs.

## FIX B — applied (2026-06-17)

FIX B was implemented in preference to FIX A (removing symptomdefs from the
pak), to keep the all-in-one pak delivery model intact while correcting the
proximate cause (unresolvable ID).

**Changes made:**

1. **`vcfops_symptoms/loader.py`** — `SymptomDef` dataclass gains an optional
   `id: str` field.  When present it must be a UUID.  `load_file()` parses
   it.  The loader docstring updated to allow `id:` for ported/third-party
   content.

2. **`vcfops_alerts/render.py`** — `_symptom_id()` now accepts an optional
   `uuid` kwarg.  When supplied it emits `SymptomDefinition-<uuid>`; when
   absent it falls back to the prior `SymptomDefinition-<adapter>-<slug>`
   form (backwards-compatible for factory-authored symptoms).
   `_render_symptom_definition()` and `_render_alert_definition()` both read
   `sym.id` and pass it through — guaranteeing that the alertdef
   `SymptomSet ref=` matches the symptomdef `id=` in both UUID and slug modes.

3. **`content/sdk-adapters/vcommunity/symptoms/esxi-host-nic-disconnected.yaml`**
   — `id: c8d1e671-d0ea-489f-acc4-46e34cc246b6` added (from reference XML).

4. **`content/sdk-adapters/vcommunity/symptoms/windows-service-down.yaml`**
   — `id: 7675759b-2ca0-4847-87ed-e3e23acdf7a5` added (from reference XML).

5. **`tests/managementpacks/test_sdk_content_emit.py`** — 3 new tests:
   `test_symptom_xml_id_uses_uuid_when_present` (UUID form emitted when id:
   present), `test_symptom_xml_id_uses_slug_when_no_uuid` (fallback works),
   `test_alert_symptom_crossref_uses_uuid_when_present` (ref= matches id= in
   UUID mode).  Cross-ref guard still fires on genuine name mismatch.
   30 tests pass, full suite 402/0.

**entries.resourceKind (dashboard owning-kind issue) — resolved as not a bug:**
Zero vcommunity dashboard widgets reference `vcfcf_vcommunity` or
`vCommunityWorld`.  All vcommunity dashboards are purely VMWARE-resource
dashboards (HostSystem, VirtualMachine, ClusterComputeResource, etc.).  The
renderer already builds `entries.resourceKind` from actual widget resource
kinds; adding a vcommunity-owned kind entry would be wrong — no widget
references it.  Unlike the compliance pack (whose `ComplianceWorld` kind IS
referenced by compliance widgets), vcommunity has no owning World widget
anchor.  No code change required; the latent risk noted in Q3 does not apply.

---

# ADDENDUM — vcommunity-vsphere build-8: 0/11 ReportDefinitions + 4 views drop (2026-07-10)

**Pak:** `vcfcf_sdk_vcommunity_vsphere` build-8, installed on
vcf-lab-operations-**devel** as `0.0.0.8`.
**Investigator:** api-explorer. **Posture:** read-only against devel (token
acquire + GET + SSH log grep; **no** POST/PUT/DELETE, no test objects). Scratch
pak extraction removed.

## Symptom

Build-8 shipped 11 CSV-export ReportDef XMLs (flat under `content/reports/`)
plus 109 view subdirs (`content/reports/<slug>/content.xml`). Post-install:
`GET /api/reportdefinitions` returns 63 total, **none ours (0/11)**; most views
render, but a few return "No appropriate view definition is found."

## Root cause — ONE defect, TWO effects: a view localization key exceeds the platform's 64-char XSD maxLength

Devel `view-bridge.log` / `analytics-*.log` for the install window
(2026-07-10 13:32 and 17:29) show the decisive error, thrown during
`SolutionManagerDistributedTask.installReportContent → ContentImportService.importSolutionContent`:

```
JAXB unmarshalling exception; nested exception is javax.xml.bind.UnmarshalException
cvc-maxLength-valid: Value 'config_policies_override_network_resourcepool_moving_override_allowed'
  with length = '69' is not facet-valid with respect to maxLength '64'
  for type '#AnonType_keyPropertyLocaleLocalizationViewDefViewsContent'
```

The XSD type `#AnonType_keyPropertyLocaleLocalizationViewDefViewsContent` is the
`key` attribute of a `Content/Views/ViewDef/Localization/Locale/Property` — i.e.
a **view localization key**, capped at **64 chars**. Two distinct over-length
keys appear in the logs:

| key | len | source column |
|---|---|---|
| `config_policies_override_network_resourcepool_moving_override_allowed` | 69 | Distributed Virtual Portgroup config-policy property |
| `virtualDiskAggregate_of_all_instances_numberWriteAveraged_average` | 65 | VM virtual-disk write metric |

**Where the key comes from.** `src/vcfops_managementpacks/sdk_builder.py`
emits, for every bundled view, a `content/reports/<slug>/resources/content.properties`
bundle via `_generate_view_content_properties` (~line 1435). Each column line is
`view.<uuid>.<loc_key>=<display>` where `loc_key = _attribute_to_localization_key(col.attribute)`
(~line 1465) — the column's metric/property path with `|` and spaces replaced by
`_`. The platform re-materializes each content.properties entry (stripping the
`view.<uuid>.` prefix) into a `<Localization><Locale><Property key="<loc_key>">`
element inside the ViewDef and XSD-validates it. A `loc_key` > 64 chars fails
`cvc-maxLength-valid`. (Note: `render.py` no longer emits `localizationKey` on
column displayName — that was removed 2026-06-10, commit `6c59f6bc`, before
build-8 — so `content.properties` is the sole entry point for the long key.)

**Effect 1 — the offending views drop.** Each view content.xml whose
content.properties carries an over-64 key fails to unmarshal individually →
that ViewDef is skipped → "No appropriate view definition is found."

**Effect 2 — ALL 11 reports drop.** Our builder colocates reports (flat
`content/reports/<name>.xml`) and views (subdir `content/reports/<slug>/content.xml`)
in the **same** `content/reports/` tree. `installReportContent` unmarshals that
tree as one solution-content unit; the first over-64 **view** key aborts the
whole JAXB unmarshal → the entire reports batch fails (log shows the
`ViewDefViewsContent` maxLength error thrown *inside* `installReportContent`,
20 retries, all failing the same way). There is **no** separate report-side
schema error — the ReportDef XML itself (`<Content><Reports><ReportDef>`,
`src/vcfops_reports/render.py::render_report_xml`) is structurally fine and
matches the vendor `<Content><Reports><ReportDef id="uuid">…` shape byte-for-byte.

## Scope correction: it's 4 views, not 3

The user observed 3 broken **report-companion** views (Distributed Port Groups,
Virtual Machines, vSphere Pod). Rendering every view's content.properties keys
locally shows **four** views carry an over-64 key:

| view YAML | over-64 loc_key (len) |
|---|---|
| `Distributed Port Groups.yaml` | `config_policies_override_network_resourcepool_moving_override_allowed` (69) |
| `Report Virtual Machines for CSV export.yaml` | `virtualDiskAggregate_of_all_instances_numberWriteAveraged_average` (65) |
| `Report vSphere Pod for CSV export.yaml` | `virtualDiskAggregate_of_all_instances_numberWriteAveraged_average` (65) |
| `vSphere Port Group Configuration.yaml` | `config_policies_override_network_resourcepool_moving_override_allowed` (69) |

The 4th (`vSphere Port Group Configuration`) is a standalone view (not a report
companion) so it wasn't in the user's spot-check, but it is broken by the same
defect and would show "No appropriate view definition is found" too.

## Vendor packaging comparison (byte-structural)

| aspect | vendor `vmbro_vcf_operations_vcommunity` | our build-8 |
|---|---|---|
| reports+views location | all **flat** `content/reports/<Name>.xml` (32 files) | reports **flat** `content/reports/<Name>.xml`; views in **subdirs** `content/reports/<slug>/content.xml` |
| ReportDef root | `<Content><Reports><ReportDef id="uuid">` | **same** (`render_report_xml`) |
| ViewDef root | `<Content><Views><ViewDef id="uuid">` | **same** (`render_views_xml`) |
| per-view localization bundle | **none** (no `resources/` subdir, no content.properties) | `content/reports/<slug>/resources/content.properties` present |
| localization keys | n/a — no bundle → no over-64 Locale key ever generated | attribute-derived keys, **not length-capped** → 4 exceed 64 |

The vendor never ships a per-view content.properties bundle, so it never
manufactures a Locale `key` that the XSD can reject. Our factory adds the
bundle (per the localization lesson, an SDK-pak view needs a populated
`resources/` bundle to import at all — see
`knowledge/lessons/pak-content-localization-bundles.md`), and that bundle is the
exact thing carrying the illegal key. The bundle is not itself wrong; its **key
derivation is uncapped**.

## The fix (for `tooling`)

**Primary — cap the localization key at 64 chars.**
**File:** `src/vcfops_managementpacks/sdk_builder.py`
**Function:** `_attribute_to_localization_key` (~line 1465), consumed by
`_generate_view_content_properties` (~line 1435).
When the derived key exceeds 64 chars, shorten it deterministically **and
keep it unique** (e.g. first ~55 chars + `_` + an 8-hex hash of the full
attribute). A blind truncate risks two long columns colliding on the same
64-char prefix → Java-properties would silently keep only the last, dropping a
column's localized label. Uniqueness must be preserved.

**Consistency — cap the twin.** `src/vcfops_dashboards/render.py::_attribute_to_localization_key`
(~line 144) is an identical helper. It is currently dormant for view columns
(displayName carries no localizationKey), but it is a latent trap if column
localizationKeys are ever re-enabled or reused for dashboards — cap it the same
way (share one helper if practical).

**Optional hardening — stop colocating reports and views** so a single bad view
no longer takes the whole report batch down. Reports and views could live in
separate content subtrees, or the builder could pre-validate every emitted
localization key against the 64-char limit and fail the build loudly rather than
shipping a pak that aborts on import. Not required once keys are capped, but it
shrinks the blast radius of any future content-side schema violation.

**Result of the primary fix:** with no content.properties key exceeding 64
chars, all 4 view content.xml files unmarshal, the `installReportContent` batch
no longer aborts, and **all 11 reports land** — a single change closes both
Effect 1 (the 4 views) and Effect 2 (the 11 reports). This is **not** a
platform limitation / BY-DESIGN gap: ReportDef-via-pak works (the ReportDef XML
is schema-valid); it was masked by a colocated view with an illegal key.

## Verdict

| hypothesis | verdict |
|---|---|
| ReportDef-via-pak unsupported (TOOLSET GAP / BY-DESIGN) | **Rejected** — ReportDef XML is schema-valid; import aborted on a *view* key. |
| Report layout wrong (flat vs subdir, embedded ViewDef) | **Rejected** — report root matches vendor; layout is not the fault. |
| A view localization key exceeds the 64-char XSD maxLength | **Confirmed** — `cvc-maxLength-valid … maxLength '64'` on `keyPropertyLocaleLocalizationViewDefViewsContent`, from uncapped `_attribute_to_localization_key`. |
| Reports die because views are colocated in `content/reports/` | **Confirmed** — the `ViewDefViewsContent` error is thrown inside `installReportContent`; one bad view aborts the whole reports batch. |
| Only 3 views affected | **Corrected** — 4 views carry an over-64 key (3 report-companions + `vSphere Port Group Configuration`). |

> **NOTE (superseded by the build-9 addendum below):** the build-8 verdict
> table above was partly wrong. It **rejected** "report layout wrong (flat vs
> subdir)" and predicted the 64-char key fix alone would land all 11 reports.
> Build 9 shipped that fix (views now import cleanly) and **reports are still
> 0/11**. The real reason reports never imported is that they are emitted as
> **flat** `content/reports/<name>.xml` files, which the platform content
> walker does not descend into — see the build-9 addendum. The maxLength abort
> was real but it only ever masked a *pre-existing* flat-layout gap for reports.

---

# ADDENDUM — vcommunity-vsphere build-9: reports STILL 0/11, SM readUUID noise, root-caused (2026-07-10, PM)

**Pak:** `vcfcf_sdk_vcommunity_vsphere` build-9 (`0.0.0.9`), upgrade over
`0.0.0.8`, installed on vcf-lab-operations-**devel** 2026-07-10T21:41:55Z.
**Investigator:** api-explorer. **Posture:** devel token GET + SSH log grep +
read-only per-UUID GET probes. **No** POST/PUT/DELETE, no test objects created.
Scratch pak/tvs extractions removed; token file removed.

## TL;DR — three findings, cleanly separated

1. **The empty-UUID `readUUID` errors are our renderer emitting
   `"modifiedBy": ""` on every bundled supermetric, and they are
   NON-FATAL.** All 37 SMs are healthy on devel (37/37 return HTTP 200).
2. **The `readUUID` errors are NOT a build-9 regression and NOT the cause of
   the reports gap.** They fire 37× (one per SM) in *every* install — both
   build-8 windows (13:32, 17:30) and build-9 (21:42) — 111 total in the log.
   The premise "build 8 did not hit this" is **false**.
3. **Reports are 0/11 because our builder emits them as FLAT
   `content/reports/<name>.xml` files, which the platform content walker
   ignores.** It only descends into *subdirectories* of `content/reports/`.
   PR #48's 64-char fix worked (views import cleanly now), but it could never
   fix reports — reports were never being walked in the first place.

## Finding 1 — what emits the empty UUID (and why it is harmless)

**Source:** `src/vcfops_managementpacks/sdk_builder.py`, SM-emission block,
line **1850**: every bundled SM JSON is written with a hardcoded
`"modifiedBy": ""`. The platform's `SuperMetricImportParam.readUUID` parses
`modifiedBy` as a UUID; an empty string throws `Invalid UUID string:` (the
offending string is empty — matches the log exactly). One error per SM → 37.

- **Vendor comparison (decisive):** every one of the vendor
  `vmbro_vcf_operations_vcommunity` SM JSONs sets `modifiedBy` to a real user
  UUID (e.g. `8a399472-453b-435f-b57d-84aa33550d08`). Ours are all `""`.
- **Non-fatal:** the error is logged, but the SM create/update proceeds — the
  platform defaults the missing `modifiedBy`. Confirmed on devel: **all 37 SM
  UUIDs return HTTP 200** from `GET /suite-api/api/supermetrics/<uuid>`.
- The saved excerpt showed 33 errors only because it was truncated; the full
  log window has 37 (= the 37 bundled SMs).

## Finding 2 — why build 8 "differed" (it did not)

`grep SuperMetricImportParam.readUUID` over the whole
`analytics-0ad8f158-*.log` returns **111** hits: **37 at 13:32** (build-8
install #1), **37 at 17:30** (build-8 install #2), **37 at 21:42** (build-9).
Identical every time — PR #48 did not touch SM emission, `modifiedBy` has been
`""` all along, so the errors are a constant. The build-8 addendum simply never
looked for them (it was chasing the maxLength view-key abort). **Not a
differentiator.**

## Finding 3 — why reports abort (the actual reports root cause)

The reports/views import is `SolutionManagerDistributedTask.installContent`,
logged in `view-bridge.log`. Build-9 sequence (task **finished successfully**
in 35 s, no exception):

```
installContent: localization import started... / passed...
installContent: report import started...
installContent: dashboard import started...      ← report step ran, no error
...
SolutionManagerDistributedTask finished in 35094ms.
```

(Only `localization` ever logs a `passed` line; absence of "report import
passed" is not a failure signal — that message does not exist for reports.)

Inside that window the analytics log shows exactly **109
`ContentImport.importFile` lock cycles** (21:42:05–21:42:16) — **one per view
subdirectory**. The pak has **109 view subdirs + 11 flat report `.xml` files =
120** content-report entries, but only **109** were imported. **The 11 flat
report files got zero importFile locks — they were never walked.** No
maxLength/Unmarshal error occurs in build 9 (the stripped localization keys now
max out at exactly 64 — PR #48 held; 0 keys over 64).

**Per-UUID probe on devel (definitive):**
- 11/11 ReportDef UUIDs from the pak → `GET /api/reportdefinitions/<uuid>` = **404**.
- 37/37 SM UUIDs → **200**.

**Why flat files are ignored — proven against a known-good BUILT pak.** The TVS
`SolarWindsNPM-7.0_3.0.0` pak (a shipping vendor pak) has **zero** flat report
files: all 18 reports are **subdirectories** —
`content/reports/<Report Name>/<Report Name>.xml` — and each XML is a single
`<Content>` with `<Views>` (the ViewDefs the report uses) followed by
`<Reports><ReportDef>`. The platform content walker descends into each
`content/reports/<subdir>/` and imports its XML; it does not import loose
`*.xml` sitting directly under `content/reports/`. Our **views** use the subdir
form (`content/reports/<slug>/content.xml`) and import fine; our **reports** use
the flat form and are dropped. The vendor *source* tree stores reports flat,
which misled the build-8 conclusion — but a source tree is not a built pak.

## The fix (for `tooling`)

**File:** `src/vcfops_managementpacks/sdk_builder.py`
**Function:** the report-emission block (the `if reports:` loop, ~lines
**2068–2100**; the flat write is line **2093–2096**:
`zf.writestr(f"content/reports/{safe_name}.xml", xml_text)`).

**Change:** emit each report inside its own subdirectory so the walker
descends into it, mirroring the proven TVS/subdir layout and our own working
view layout:

```
content/reports/<report-slug>/content.xml   # <Content><Reports><ReportDef>…
```

i.e. `zf.writestr(f"content/reports/{safe_name}/", "")` +
`zf.writestr(f"content/reports/{safe_name}/content.xml", xml_text)`. A report
slug will not collide with a view slug (distinct names); if a future collision
is possible, reuse the same de-dupe guard already in the loop. Update the
now-incorrect comment block at lines **2055–2063** (it documents the flat
layout as intentional/vendor-matching — it is neither for a *built* pak).

- **Optional but recommended:** to match TVS exactly, also embed the ViewDef(s)
  the ReportDef references in the same `<Content>` document (TVS ships
  `<Views>`+`<Reports>` together per report subdir). Our reports reference views
  that are already bundled as their own subdirs, so a UUID cross-reference
  *should* resolve post-import — but co-bundling is the vendor-proven belt-and-
  suspenders form and removes any import-ordering dependency. Worth trying the
  minimal subdir move first; escalate to co-bundling only if reports still drop.

**Finding 1 fix (low priority, log-noise only):** at line **1850**, emit a
valid UUID for `modifiedBy` instead of `""` (reuse `sm.id`, or a fixed factory
system UUID). Purely cosmetic — silences 37 ERROR lines per install; the SMs
already import correctly without it. Do this alongside the reports fix, not as
a blocker.

## Health on devel right now (post build-9)

| content type | state |
|---|---|
| Supermetrics (37) | **healthy — 37/37 present (HTTP 200)** despite the readUUID noise |
| Symptoms / 4-tier alert | imported (log shows `UPDATED` for each; four-tier alert landed) |
| Views (109) | imported — 109 importFile locks, no errors (build-9) |
| ReportDefinitions (11) | **absent — 0/11 (all 404)**; flat-layout, never walked |
| Dashboards (12) | separate `DashboardImporter` errors at 21:44/21:54 (out of scope here — `ResourceKindImport…`; flag for follow-up) |

## Verdict (build-9)

| hypothesis | verdict |
|---|---|
| Empty-UUID = our `modifiedBy:""` on SM JSON | **Confirmed** — line 1850; vendor sets a real UUID. |
| readUUID error is fatal / aborts the reports step | **Rejected** — non-fatal; 37/37 SMs land; errors present in every install. |
| Build 8 did not hit the readUUID error | **Rejected** — 37 hits in each build-8 window too (111 total). |
| Reports 0/11 caused by the 64-char maxLength (build-8 theory) | **Rejected for build 9** — 0 keys over 64; no unmarshal error; reports still 0. |
| Reports 0/11 because emitted as FLAT files the walker ignores | **Confirmed** — 109 view subdirs imported, 11 flat reports got 0 importFile locks; TVS built pak proves reports must be subdirs. |
| Upgrade path re-imports SMs differently (readUUID on existing refs) | **Rejected** — same 37 errors on fresh and upgrade; SMs update fine. |

## Clean-up

Read-only. Devel token acquired for GET probes then discarded; scratch token
file removed. TVS pak extraction (`scratchpad/tvs_probe`) removed. No repo
content, no `src/vcfops_*/`, no live Ops state modified (no POST/PUT/DELETE).
