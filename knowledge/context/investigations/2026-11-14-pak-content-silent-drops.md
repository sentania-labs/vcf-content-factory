# Pak content the installer drops silently: empty localization values and ids defined twice

**Date:** 2026-11-14
**Pak:** vCommunity Java (`vcfcf_vcommunity`) 0.0.0.15, built by `build-sdk`
from `content/sdk-adapters/vcommunity-java/` (content converted offline from
the vCommunity 0.8.1 e1 pak).
**Instances:** devel (9.0.2), devel_9_1 (9.1.1); the source pak's baseline on
devel_8_18 (8.18.7).
**Evidence (read-only):** the lab's p6 backup set: per instance
`post/platform_log_import_errors*.txt`, `post/live.json`, `post/defs.json`,
the install logs and `pak-inventory.json`.
**Fix:** `fix/pak-content-import-defects` (`sdk_builder.py`,
`vcfcf_core/packaging/pak_content.py`, `post_install_content.py`).

The pak installed "successfully" on both instances, the installer printed no
error, and content was missing. Two independent defects, both in how
`build-sdk` laid out the pak's `content/` tree.

## A. An empty localization value fails a whole `content/reports/<dir>/`

### What the logs say (proven)

Both instances, `view-bridge`, inside
`SolutionManagerDistributedTask.installReportContent` (the excerpt saved from
each instance's log):

```
importSolutionContent failed to import reports. Error: JAXB unmarshalling exception
cvc-minLength-valid: Value '' with length = '0' is not facet-valid with respect to
  minLength '1' for type '#AnonType_valuePropertyLocaleLocalizationViewDefViewsContent'.
  at ...ContentImportService.importFileInternalContent(ContentImportService.java:294)
```

The type is the `value` attribute of `Content/Views/ViewDef/Localization/Locale/Property`.
Its sibling, the `key` attribute, is the `maxLength 64` facet of the
2026-07-10 addendum in `sdk_pak_content_import_gap.md`. The importer builds
that element from each `view.<id>.<key>=<value>` line of the directory's
`resources/content.properties` (the reported line numbers, 74 and 69, are in
the merged document: the pak's `content.xml` is one line). No XSD for the
content schema is in `reference/docs/`; the facets are known only from these
two error messages.

In 0.0.0.15, 15 directories carried at least one `view.<id>.<key>=` line (19
lines). The 14 views and 1 report template absent on both instances are
exactly the ViewDef and ReportDef ids of those 15 directories (`live.json`
against `pak-inventory.json`). One bad line fails the directory, including a
report and every view it embeds.

### Why the value was empty (root cause)

`sdk_builder._generate_view_content_properties` wrote a line per column with
`col.display_name` as the value, empty or not. A column converted from a
source ViewDef with no `displayName` property loads as `display_name: ""`
with `omit: [display_name]` (`vcfcf_core/dashboards/loader.py`, the column
loader), and the view XML carries no `displayName` for it, faithfully. Most
of the 19 lines are such columns (`cpu|cpuModel`, `Instance Name`, ...).

### What the source pak does (proven)

The vCommunity 0.8.1 pak ships no per-view localization bundle at all: no
`resources/` directory under `content/reports/`, no `localizationKey`
anywhere. Its views import on 8.18.7. The factory adds a bundle per directory
for the A3 contract (`knowledge/lessons/pak-content-localization-bundles.md`).

### The fix

- No entry is written for an empty or blank text (column label, description,
  title, and in the dashboard bundles a folder, dashboard or widget name).
  The rendered XML never references these keys: `render.py` emits no
  `localizationKey` on `Title`, `Description` or `displayName` (DEF-018 and
  `view_column_wire_format.md` §displayName and localizationKey), so leaving
  the entry out dangles nothing. The bundle is not empty: the title line is
  always there.
- Values are escaped for `java.util.Properties` (backslash, line breaks,
  leading whitespace). 0.0.0.15 also carried 34 stray lines: every
  multi-line view description was written raw, so its second line became a
  key of its own (`Known issue: ...` read as key `Known`). Those directories
  imported (proven: their views are present), so the stray keys are
  tolerated, but the localized description was cut to its first line.

What a `localizationKey` in the XML with no entry does: 8.18 rejects the
view (`ViewDefinitionDataServiceImpl.validate`, DEF-018); 9.1 tolerates it.
The builder emits none, and the gate below refuses one.

## B. Every symptom defined twice; the second definition breaks 9.0.2

### Layout of 0.0.0.15 (proven)

Each of the 10 bundled symptoms was written twice: once in
`content/symptomdefs/<name>.xml` and once inside the `content/alertdefs/`
file of the alert that references it (`sdk_builder._write_outer_pak`, the
symptoms block and the alerts block, before this fix).

### What the instances hold (proven, `post/defs.json`)

| | 9.1.1 | 9.0.2 | source pak on 8.18.7 |
|---|---|---|---|
| `vCommunity Collection Warnings` symptom | present | present | present |
| `ESXi Host NIC Disconnected` symptom | present | present | present |
| `Windows Service Status Down` symptom | present | **404** | present |
| License alert: 7 conditions | all 7, as `alertConditions` | **all 4 sets empty** | all 7, as `alertConditions` |
| Windows alert: its symptom | present | **set empty** | present |

9.0.2's analytics log, three times:
`SymptomDefinitionRetriever.importSymptomDefinitions - Cannot import Symptom
Definitions: ... duplicate key value violates unique constraint
"kv_symptomproblemdefinition_pkey"`. 9.1.1 logged no symptom error.

**Correction to the first reading:** the seven `Condition_*` symptoms are not
missing on 9.1.1 or 8.18.7. They carry `symptomDefType="condition_self"`:
the alert editor's inline conditions. REST never lists them on
`/api/symptomdefinitions` (404 by id on every line, also for the source pak
on 8.18.7) and shows them only inside the alert, as
`states[].base-symptom-set.alertConditions[].id = "Condition-<x>"` for
`SymptomDefinition-<x>` (as `2026-11-11-alert-symptom-export-completeness.md`
already recorded). Counting them on the symptom endpoint reports a false
"7 missing". The real loss is 9.0.2's: the License alert's conditions and
the Windows symptom.

### Where each definition belongs

- Order (bytecode, 9.0.2): `installContent` imports `content/alertdefs/`
  before `content/symptomdefs/` (`api-surface/summary_dashboard_pak_binding.md`;
  `2026-10-13-dashboard-import-deferral-trigger.md` §5), each directory in
  `File.listFiles()` order (unsorted).
- An alert whose symptoms do not exist when its file is imported is not
  created ("Cannot create alert definition ... because dependent symptoms",
  Synology 0.0.0.35, `wire-formats/symptomdef_dt_condition_import.md`).
- So the alert file must carry every symptom it references. With that, a
  standalone copy can only collide; it is the copy to drop.
- The source pak puts the seven conditions and `Collection Warnings` in
  their alert file only, and NIC and Windows in both (the same duplicate,
  which an older note recorded failing on 9.0.2:
  `2026-11-12-vcommunity-upstream-builtin-view-ids.md`, Undetermined).
- Vendor paks in the reference corpus with content-tree alerts (Physical
  SAN 8.12, Kubernetes 1.9 and 2.2) ship one `content/alertdefs/` file with
  every alert and every symptom (14 to 22 alerts, 22 to 49 symptoms) and no
  `content/symptomdefs/` at all.

The layout `build-sdk` now writes (`sdk_builder.plan_alert_content_files`):

1. Each `content/alertdefs/` file holds the alerts connected by a shared
   bundled symptom or recommendation, every bundled symptom and
   recommendation they reference, each once. Unshared alerts keep one file
   each, under the same name as before.
2. `content/symptomdefs/` holds only symptoms no bundled alert references
   (a `condition_*` symptom there gets a build warning: it is an alert's
   condition with no alert).
3. Every content id is defined once per pak.

Proven: the layout's pieces import (a symptom defined only in its alert file
lands, as a real symptom or as an alert condition, on 8.18.7 and 9.1.1;
multi-alert files are the vendor shape). Inferred, not yet measured: that
9.0.2 imports every symptom and condition with no duplicate in the pak. The
duplicate-key failure correlates with the duplicate on 9.0.2 in both the
factory and the source pak, and nothing else in the pak is defined twice.
What the duplicate collides with inside 9.0.2 was not traced. A 9.0.2
install of a rebuilt pak is the proof.

### How the importer modeled the conditions (no defect)

`vcfcf_extractor import-local` turned each `<SymptomDefinition>` of the
source's alert file into a symptom YAML with `symptom_def_type:
condition_self` and the source name (`Condition_<uuid>`); the alert names
them. That is the wire model: a condition is a `SymptomDefinition` the alert
references by id, and only `symptomDefType` marks it. Nothing is lost. Which
file a definition sits in is a pak-layout decision, now made by the builder.
The conversion's verification passed because it compares objects, not the
pak's file layout; the gate below is what checks the layout.

## Gates

- **Build:** `_write_outer_pak` ends with
  `vcfcf_core.packaging.pak_content.check_pak_content` on the written pak
  (`PakContentGateError`; a release build deletes the pak, a dev build
  leaves it for inspection). It refuses: an empty localization value, a key
  over 64 characters, a line that is not `view.<id>.<key>` for a ViewDef in
  the same directory, a `localizationKey` with no entry, an empty dashboard
  bundle value, and any content id (view, dashboard, report, super metric,
  symptom, alert, recommendation) defined more than once, naming every
  location. One allowance: a ViewDef that appears in its own directory and,
  byte-identical, in the directory of a report that embeds it (the importer
  upserts views; every such view of 0.0.0.15 was present on 9.0.2 and
  9.1.1; the source pak ships 59 such copies). Copies that differ fail.
- **validate-sdk:** renders the same content tree into a temporary pak (no
  adapter, no compile) and runs the same gate, so both classes fail before a
  build.
- **install:** `post_install_content.report_pak_content` counts the pak's
  views (`/ui/` view list), report templates (`/api/reportdefinitions`),
  standalone symptoms (`/api/symptomdefinitions/{id}`) and alerts
  (`/api/alertdefinitions/{id}`), and checks each alert still names every
  symptom and condition its pak definition names. A shortfall is exit 3 with
  one `CONTENT MISSING` / `CONTENT INCOMPLETE` line per id. It re-reads every
  30 s for up to 120 s while something is missing; these types are written
  inside the install task, so a shortfall at the first read is expected to
  be final (inferred from the log timestamps: the errors are minutes before
  the install finished). `--skip-content-check` turns it off.

## Gate run on the registered pak projects (2026-11-14)

Content rendered from each project with the previous builder, then gated:

| Project | Duplicates | Empty values | Stray lines |
|---|---|---|---|
| vcommunity-java (0.0.0.15 layout) | 10 symptoms | 19 | 34 |
| synology | 19 symptoms (one 3 times), 1 recommendation | 0 | 0 |
| unifi | 19 symptoms, 1 recommendation (3 times) | 0 | 0 |
| vsanperf | 1 symptom | 0 | 0 |
| compliance, template | none | 0 | 0 |

`cluster-perf-risk`, `vcommunity` and `vsanhostmetrics` are Python packs (no
`adapter.yaml`), not built by `build-sdk`. With the fix every project renders
clean with the same definition counts. Synology 0.0.0.35 was installed on
8.18.7 and 9.1.1 with its duplicates and every symptom but the DT one
imported, which is consistent with 9.1.1 here; no factory pak with a
duplicate has been measured on 9.0.2 other than vCommunity Java.
