# Phase 2 Content Tooling Scope — vCommunity Parity Port

Assessment date: 2026-06-16  
Scope: ~55 super metrics → ~9 views → 2 symptoms → 3 alerts → 13 dashboards → ~22 reports,
all authored as factory YAML and shipped INSIDE the `vcfcf_vcommunity` Tier-2 SDK pak's
`content/` tree.

All conclusions are based on read-only inspection of:
- `vcfops_managementpacks/sdk_builder.py`
- `vcfops_dashboards/render.py` and `loader.py`
- `vcfops_supermetrics/loader.py`, `handler.py`, `client.py`
- `vcfops_symptoms/loader.py`
- `vcfops_alerts/render.py`
- `vcfops_reports/loader.py`, `render.py`
- `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/`
- `lessons/pak-content-bundling.md`
- `lessons/pak-content-localization-bundles.md`

---

## Baseline: What the SDK builder currently ships into an SDK pak

`_write_outer_pak()` (sdk_builder.py:1306) emits bundled content into the outer `.pak`
when `adapter.yaml` carries a `bundled_content:` key. The key accepts two lists:
- `bundled_content.views:` — relative paths to factory view YAML
- `bundled_content.dashboards:` — relative paths to factory dashboard YAML

No other content types are accepted by `bundled_content` today. The emit paths are:

| Content type | Pak path | Generator |
|---|---|---|
| View | `content/reports/<slug>/content.xml` | `render_views_xml()` — `vcfops_dashboards/render.py` |
| View i18n | `content/reports/<slug>/resources/content.properties` | `_generate_view_content_properties()` — sdk_builder.py:1223 |
| Dashboard | `content/dashboards/<slug>/dashboard.json` | `render_dashboards_bundle_json()` — vcfops_dashboards/render.py |
| Dashboard i18n | `content/dashboards/<slug>/resources/resources.properties` | `_generate_dashboard_resources_properties()` — sdk_builder.py:1180 |
| Adapter i18n | `content/resources/resources.properties` | `_generate_content_resources_properties()` — sdk_builder.py:1098 |
| Solution i18n | `resources/resources.properties` | `_generate_outer_resources_properties()` — sdk_builder.py:1070 |
| config files | `content/files/**` | raw copy from `project_dir/content/files/` — sdk_builder.py:1488 |

The localization four-bundle contract from `lessons/pak-content-localization-bundles.md`
is satisfied for views and dashboards. The `_attribute_to_localization_key()` function
is kept in sync between `sdk_builder.py:1253` and `vcfops_dashboards/render.py:118`.

---

## Per Content Type Assessment

### 1. Super Metrics

**What exists today.**
The factory loader (`vcfops_supermetrics/loader.py`) produces `SuperMetricDef` dataclasses
with stable uuid4 IDs minted on first validate and written back into each YAML file.

The content-import-zip path (`client.py:import_supermetrics_bundle`) assembles a
`{uuid: {name, formula, description, unitId, resourceKinds}}` dict into `supermetrics.json`
inside a content-zip for live-sync. This path is the _live-sync_ path only; it is not called
from `sdk_builder.py`.

The sdk_builder has NO logic to emit super metrics into the pak. The `_ALL_CONTENT_DIRS`
list (sdk_builder.py:1290) names `"content/supermetrics/"` as a known directory but it is
commented "currently DEAD (not emitted by _write_outer_pak)".

**The gap.**
The reference pak (`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/supermetrics/`)
ships super metrics as individual JSON files, one per SM, each at
`content/supermetrics/<Display Name>.json`. Each file has exactly one top-level key: the SM's
UUID. The value carries `name`, `formula`, `description`, `unitId`, `resourceKinds`, and
`modificationTime`. Example (`content/supermetrics/CPU Ready.json`):

```json
{"9cfb6d0c-7099-400c-99da-f70077ad96d4": {
   "resourceKinds": [{"resourceKindKey":"ClusterComputeResource","adapterKindKey":"VMWARE"}],
   "modificationTime": 1753166106270,
   "name": "CPU Ready",
   "formula": "avg(${adaptertype=VMWARE, objecttype=VirtualMachine, ...})",
   "description": "...",
   "unitId": "percent",
   "modifiedBy": "..."
}}
```

The factory `SuperMetricDef` dataclass carries all these fields except `modificationTime`
and `modifiedBy`. Neither is required — they can be emitted as `0` and `""` or omitted
entirely (the importer ignores them on import; they are server-side timestamps).

**Missing transform:** `sdk_builder._write_outer_pak()` must be extended to accept a
`supermetrics` list (list of `SuperMetricDef`) from a new `bundled_content.supermetrics:`
key, render each as a one-UUID JSON file, and write it to
`content/supermetrics/<safe_display_name>.json`.

The `bundled_content` loader (`_load_bundled_content()`, sdk_builder.py:721) must be
extended with a `supermetrics:` sub-key alongside the existing `views:` and `dashboards:`.

**Size: small.** The render is trivial JSON serialization. The loader extension follows the
existing views/dashboards pattern exactly.

---

### 2. UUID / Cross-Reference Resolution (Super Metrics)

**This is the core question for the entire content port.**

The reference pak proves the answer empirically:

- Each SM JSON file uses the SM's UUID as the JSON top-level key.
- Views reference SMs in `attributeKey` as `"Super Metric|sm_<uuid>"`.
  In `reference/references/…/content/reports/View - Set 1.xml`:
  `<Property name="attributeKey" value="Super Metric|sm_77c9b561-8a30-496c-80bc-4b049bd63b96"/>`
- The SM JSON at `content/supermetrics/Share per vCPU.json` uses that exact UUID as its top-level key:
  `{"77c9b561-8a30-496c-80bc-4b049bd63b96": {...}}`

**Conclusion:** the UUID baked into each SM's YAML `id:` field IS the content/cross-reference
identifier. If the factory YAML files carry stable UUIDs (minted on first validate and never
changed — current behavior), then views and dashboards that reference those UUIDs via
`supermetric:"<name>"` resolve correctly. The existing factory view render path
(`_xml_attribute_item()`, render.py:211) already handles this:

```python
sm_id = (sm_map or {}).get(sm_name)
if sm_id:
    attribute_key = f"Super Metric|sm_{sm_id}"
```

The `sm_map` (name → UUID) is built from the loaded `SuperMetricDef` list. In the SDK pak
build, the SM UUIDs embedded in view XML must match the UUID keys in
`content/supermetrics/*.json`. Since both come from the same YAML `id:` field, they are
consistent by construction — as long as the SM YAML files are included in the build scope
and loaded before the views are rendered.

**Gap:** `sdk_builder._write_outer_pak()` currently receives no SM list, so no `sm_map`
is passed to the view renderer. When the builder is extended to accept `supermetrics`, it
must also pass the resulting name→UUID map as `sm_map` to `render_views_xml()`. Today
`_write_outer_pak()` calls `render_views_xml([v], owning_adapter_kind=...,
owning_resource_kind=...)` at sdk_builder.py:1417 with no `sm_map` argument. If the
vCommunity views reference SMs via `supermetric:"<name>"`, this will raise a `ValueError`
at build time — a visible, loud failure, not a silent wrong output.

**Deterministic UUID story:** YES, there is one. UUIDs are per-YAML-file, minted once,
stable across rebuilds. No name-based resolution at install time — the pak ships
pre-resolved UUIDs in both the SM JSON and the view XML. A fresh instance importing the
pak gets consistent IDs because both sides reference the same UUID.

---

### 3. Views

**What exists today.**
`render_views_xml()` (`vcfops_dashboards/render.py`) produces correct `<Content><Views>`
XML matching the format required by the pak (confirmed working — compliance pak build v22).
The sdk_builder emits it at `content/reports/<slug>/content.xml` with localization
properties.

**The gap for vCommunity views specifically.**
The vCommunity reference pak ships views as flat XML files at
`content/reports/<Name>.xml` (NOT in a subdirectory). Example:
`content/reports/ESXi Host Details vCommunity.xml`. The factory sdk_builder emits
`content/reports/<slug>/content.xml` (subdirectory per view — the VMware first-party
pattern from `lessons/pak-content-bundling.md`).

Both the flat-file pattern (vCommunity) and the subdirectory pattern (VMware first-party,
compliance v22 confirmed working) are present in the wild. The subdirectory pattern is
confirmed working for our paks. The flat-file pattern is the vCommunity pattern.

**Decision required:** the factory should stick with the subdirectory pattern (what it
already emits and has already proven works) and NOT copy the vCommunity flat-file layout.
The vCommunity reference is the _content_ to port, not the _layout_ to copy.

**No additional tooling gap for views** beyond the SM cross-reference fix above.

---

### 4. Dashboards

**What exists today.**
`render_dashboards_bundle_json()` produces dashboard JSON in the pak-compatible format.
The sdk_builder emits it at `content/dashboards/<slug>/dashboard.json`. Localization is
handled. The `_VIEW_PIN_CONTAINER` table (render.py:68) maps VMWARE leaf kinds to
"vSphere World" — this covers HostSystem, VirtualMachine, Datastore,
ClusterComputeResource, Datacenter.

**The gap.**
vCommunity dashboards reference super metrics by UUID in Scoreboard/MetricChart widget
`metricKey` fields:
`"metricKey": "Super Metric|sm_0c648c9c-cede-4403-b8fe-500067629bf0"`.

The factory dashboard YAML for Scoreboard/MetricChart widgets uses the `metrics:` list
with a `metric_key:` field. If the author writes a literal `"Super Metric|sm_<uuid>"`
there, it passes through unchanged — this is already supported in `_parse_metric_specs()`
(loader.py:1087). Authors can also write the `supermetric:"<name>"` syntax if we extend
the renderer to resolve it.

**Current limitation:** the Scoreboard and MetricChart metric_key fields in the factory
YAML are not resolved against the SM name map — they are passed through as literals.
An author targeting a vCommunity SM in a Scoreboard widget must write the UUID explicitly:
`metric_key: "Super Metric|sm_<uuid>"`. This is workable but requires the author to know
the UUID. A name-based resolution in the Scoreboard/MetricChart renderer would close this
ergonomic gap but is not strictly required for Phase 2 if authors can look up UUIDs from
the YAML `id:` fields.

**No structural gap.** Dashboard render → pak emission path works today. The SM-in-widget
ergonomics gap is medium but not blocking if authors use explicit UUIDs.

---

### 5. Symptoms

**What exists today.**
`vcfops_symptoms/loader.py` loads and validates symptom YAML. `vcfops_alerts/render.py`
renders symptoms as `<alertContent><SymptomDefinitions>` XML (the `render_alert_content_xml()`
function).

The sdk_builder has NO path to emit symptoms into the pak's `content/` tree. The
`_ALL_CONTENT_DIRS` list names `"content/symptomdefs/"` as a known directory but it is
"currently DEAD."

**The reference pak format.**
`reference/references/…/content/symptomdefs/ESXi Host NIC Disconnected Symptom.xml` is a standalone
`<alertContent><SymptomDefinitions>` XML file — exactly the format that
`render_alert_content_xml()` already produces. There is one XML file per symptom.

**The gap.**
The sdk_builder must be extended to accept `bundled_content.symptoms:` (list of paths to
symptom YAML), load them via `vcfops_symptoms.loader`, render each as XML via
`render_alert_content_xml()`, and write to `content/symptomdefs/<safe_name>.xml`. The XML
format already exists; only the pak-emission wiring is missing.

**Size: small.** Pattern is identical to views; render function already exists.

---

### 6. Alerts

**What exists today.**
`vcfops_alerts/loader.py` loads alert/recommendation YAML. `vcfops_alerts/render.py`
renders them as `<alertContent><AlertDefinitions>` XML (combined with symptoms in the same
file).

The sdk_builder has NO path to emit alerts into the pak. `"content/alertdefs/"` is in
`_ALL_CONTENT_DIRS` as "currently DEAD."

**The reference pak format.**
`reference/references/…/content/alertdefs/ESXi Host NIC Disconnected Alert.xml` is a standalone
`<alertContent>` file containing BOTH `<AlertDefinitions>` and `<SymptomDefinitions>`. The
vCommunity pak ships alerts and symptoms in separate files: alert XML files reference
symptom IDs that were registered by the `content/symptomdefs/` files.

**Critical:** the reference alert XML references symptoms by their `SymptomDefinition-<uuid>`
id form: `<SymptomSet ref="SymptomDefinition-c8d1e671-d0ea-489f-acc4-46e34cc246b6"/>`.
The current factory `render_alert_content_xml()` produces deterministic IDs of the form
`SymptomDefinition-<adapter>-<slug>` (NOT UUIDs). Whether the platform resolves alert→symptom
cross-references by these IDs within a pak install must be verified — if symptom IDs must
match across alert and symptom XML files, the factory's slug-derived IDs must be
deterministic and consistent between the two files. The current renderer derives the ID
identically in both alert and symptom output so they should match, but this is untested in
the pak context (it was tested only via describe.xml insertion in build 15).

The alternative approach used by `pak-content-bundling.md` §"Alerts/symptoms" is to put
both in `describe.xml` (confirmed working in build 15) OR in a combined alertdefs/ file.
For Phase 2 we likely want `content/alertdefs/` to match the vCommunity pattern.

**The gap.**
sdk_builder must be extended to accept `bundled_content.alerts:` (list of paths to alert
YAML) plus (optionally) `bundled_content.recommendations:`. Load via vcfops_alerts.loader,
render via render_alert_content_xml(), write combined XML to `content/alertdefs/<name>.xml`.
The alert→symptom cross-reference ID consistency (slug-derived vs UUID) should be validated
before authoring begins.

**Size: small for emit wiring; medium for cross-reference validation.**

---

### 7. Reports

**What exists today.**
`vcfops_reports/loader.py` + `render.py` produce report XML. The render path produces
content-zip `content.xml` (reports wrapped in a `<ReportDefinitions>` root). This is the
_live-sync_ format (via `render_report_xml()`); it is not emitted by the sdk_builder.

The sdk_builder has NO path to emit reports into the pak. `"content/reports/"` IS
emitted (for views), but the report XML format differs from the view XML format.

**The reference pak format.**
The vCommunity reference pak ships reports at `content/reports/Report - VOA - *.xml`. These
files contain a `<Content><Views>` XML structure — they ARE view XML, not report XML. The
vCommunity "reports" are actually view definitions used as report templates.

The factory `vcfops_reports` package produces a different XML (`<ReportDefinitions>`) for
live-sync install. This is a different wire format from what the pak's `content/reports/`
directory accepts. The pak `content/reports/` directory accepts view XML (`<Content><Views>`),
not report definition XML.

**The gap.**
There is a conceptual naming collision: the factory's `vcfops_reports` package generates
report-definition XML (for live sync), but the pak `content/reports/` directory holds view
XML. The vCommunity "reports" (22 XML files) are all view definitions. This means Phase 2
"report" content is authored as factory _views_ (using the `view-author` agent and
`vcfops_dashboards` package), not using `vcfops_reports`. The factory report package is for
a different content object.

**No new tooling gap for reports** if we treat them as views. The view emit path already
works.

---

### 8. Localization Bundles

**Confirmed required.** `lessons/pak-content-localization-bundles.md` documents the
four-bundle contract:

| Path | Purpose | Emitted today? |
|---|---|---|
| `resources/resources.properties` | Solution display name/description/vendor | YES — `_generate_outer_resources_properties()` sdk_builder.py:1070 |
| `content/resources/resources.properties` | Adapter-wide nameKey map | YES — `_generate_content_resources_properties()` sdk_builder.py:1098 |
| `content/dashboards/<dir>/resources/resources.properties` | Per-dashboard folder, name, widget titles | YES — `_generate_dashboard_resources_properties()` sdk_builder.py:1180 |
| `content/reports/<dir>/resources/content.properties` | Per-view title, description, column display names | YES — `_generate_view_content_properties()` sdk_builder.py:1223 |

All four bundles are emitted today for views and dashboards. The localizationKey alignment
rule is enforced by `_validate_localization_key_contract()` (sdk_builder.py:2476).

**No gap for existing content types.** When super metrics, symptoms, and alerts are added,
they do NOT require localization bundles — they carry display names directly in the JSON/XML.

---

## Ordered Work-List

Work items in dependency order. Items at the same level can be done in parallel.

### W1 — SM pak emit (MUST LAND BEFORE AUTHORING)
**What:** Extend `bundled_content` in sdk_builder to accept `supermetrics:` (list of YAML
paths). Load via `vcfops_supermetrics.loader.load_file()`. Render each as
`{<uuid>: {name, formula, description, unitId, resourceKinds}}` JSON. Write to
`content/supermetrics/<safe_name>.json`. Pass name→UUID map as `sm_map` to
`render_views_xml()` calls inside `_write_outer_pak()`.
**Files:** `vcfops_managementpacks/sdk_builder.py` (3 functions: `_load_bundled_content`,
`_write_outer_pak`, the `build_sdk()` caller).
**Size: small** (~60 lines).
**Dependency:** none.

### W2 — SM name→UUID map passed to view renderer (MUST LAND WITH W1)
**What:** `_write_outer_pak()` currently calls `render_views_xml([v], ...)` with no
`sm_map`. When views reference `supermetric:"<name>"`, this raises ValueError at build
time. The SM list loaded in W1 must be passed as `sm_map` to every `render_views_xml()`
call in `_write_outer_pak()`.
**Files:** `vcfops_managementpacks/sdk_builder.py` (~5 lines in `_write_outer_pak()`).
**Size: trivial.** Ship with W1.
**Dependency:** W1.

### W3 — Symptom pak emit (MUST LAND BEFORE SYMPTOM AUTHORING)
**What:** Extend `bundled_content` to accept `symptoms:` (list of YAML paths). Load via
`vcfops_symptoms.loader`. Render via `vcfops_alerts.render.render_alert_content_xml()`.
Write to `content/symptomdefs/<safe_name>.xml`.
**Files:** `vcfops_managementpacks/sdk_builder.py`.
**Size: small** (~40 lines).
**Dependency:** none (parallel with W1).

### W4 — Alert pak emit + cross-reference validation (MUST LAND BEFORE ALERT AUTHORING)
**What:** Extend `bundled_content` to accept `alerts:` (list of YAML paths). Load via
`vcfops_alerts.loader`. Render via `render_alert_content_xml()`. Write combined XML to
`content/alertdefs/<safe_name>.xml`. Additionally: verify that `SymptomDefinition-<id>`
IDs generated by the renderer match between symptom XML and alert XML (slug-derived IDs
must be consistent). Add build-time assertion if a mismatch is detected.
**Files:** `vcfops_managementpacks/sdk_builder.py`, possibly `vcfops_alerts/render.py`.
**Size: medium** (~80 lines + validation logic).
**Dependency:** W3 (symptom emit must exist to validate the cross-reference).

### W5 — SM name-based resolution in Scoreboard/MetricChart widgets (OPTIONAL ERGONOMIC)
**What:** The dashboard loader's `_parse_metric_specs()` (loader.py:1087) accepts
`metric_key:` as a literal string. If an author wants to reference an SM by name
(`supermetric:"<name>"`) in a Scoreboard widget, the renderer must resolve it. This
requires passing `sm_map` through to dashboard rendering.
**Files:** `vcfops_dashboards/render.py`, `vcfops_managementpacks/sdk_builder.py`.
**Size: medium** (~50 lines).
**Dependency:** W1.
**Note:** NOT blocking Phase 2 if authors write explicit UUIDs in widget metric_key fields.
Defer unless authoring ergonomics become a friction point.

---

## Bottom Line

**Phase-2 authoring CANNOT start against existing tooling.**

The three blocking gaps, in priority order:

1. **SM pak emit (W1+W2) is blocking.** Without it, the builder emits no super metrics
   into the pak, and the SM→view cross-reference is broken (ValueError at build time).
   This is the highest-priority unblocked item.

2. **Symptom pak emit (W3) is blocking** for symptom authoring. The XML format already
   exists (`render_alert_content_xml()`); only the pak-emission wiring is missing.

3. **Alert pak emit (W4) is blocking** for alert authoring, and depends on W3 for
   cross-reference consistency validation.

W1+W2 and W3 are independent and can be built in parallel. W4 depends on W3.

**What CAN start now:**
- View authoring (factory YAML + `bundled_content.views:` in adapter.yaml) can proceed today
  IF views do not reference super metrics (all-VMWARE native metric columns only). Any view
  that uses `supermetric:"<name>"` columns blocks until W1+W2 land.
- Dashboard authoring can proceed for dashboards that reference only views and VMWARE
  native metrics. SM-referencing Scoreboard/MetricChart widgets either require explicit UUIDs
  from the YAML `id:` fields (workable) or wait for W5.

**Reports ("VOA" XML files in vCommunity) are views** — no new package needed. Author
them as factory view YAML targeting the appropriate VMWARE resource kinds.

**Minimum unblocking scope before authoring can begin in earnest: W1 + W2 + W3 + W4.**
These are all in `sdk_builder.py` (one file, one PR). Estimated combined size: ~180 lines.
