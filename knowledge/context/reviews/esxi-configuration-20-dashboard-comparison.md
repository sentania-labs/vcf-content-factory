# ESXi Configuration 2.0 — PROD (vendor original) vs DEVEL (Tier 2 port) dashboard comparison

**Author:** `api-explorer` (read-only; all live calls GET / UI-session reads, zero
writes either instance, no lab objects created).
**Date:** 2026-07-14.
**Trigger:** user compared the "ESXi Configuration 2.0" dashboard in the UI on
PROD (original vCommunity vSphere pack) vs DEVEL (our Tier 2 port, v1.0.0.12 CI)
and reported they "do not seem to align 1:1".
**Profiles:** `prod` (`vcf-lab-operations.int.sentania.net`) / `devel`
(`vcf-lab-operations-devel.int.sentania.net`), `--skip-ssl-verify`.

> **UNSUPPORTED ENDPOINTS.** Dashboard config was read via the internal UI
> Struts endpoint `POST /ui/dashboard.action mainAction=getDashboardConfig`
> (JSESSIONID + `secureToken`, not the Suite API). No back-compat guarantee;
> may change between VCF Ops releases.

Raw exports saved for reference:
`…/scratchpad/prod_esxi_config_dashboard.json`,
`…/scratchpad/devel_esxi_config_dashboard.json`.

## Verdict

**The dashboard *definition* is structurally identical on both instances** —
same 20 widgets, same titles, same widget type (`View`), byte-identical grid
layout (x/y/w/h) on every widget, same 19 provider→receiver interactions. The
1:1 misalignment the user sees is **NOT in the dashboard layer**. It is in the
**rendered data of six property-distribution widgets**, which show "No data" +
a "Metrics displaying 0 of N" scoreboard modal on DEVEL but populate on PROD.

Root cause: the six ESXi Configuration 2.0 property-distribution **views** ship
in our port with a **numeric-histogram-over-a-string-property** encoding
(`isProperty=false`, `isStringAttribute=false`, fixed `[0,100]/10` buckets)
whereas the vendor originals declare them as `isProperty=true`,
`isStringAttribute=true` with dynamic DISCRETE buckets. This is the **same root
cause** as `knowledge/context/api-surface/distribution_view_no_data.md`, but on a
**different, un-remediated set of views** — the earlier fix covered only the
four ESXi Host Details views ("4/4 DISCRETE" in DEF-011's closing evidence), not
these six.

## Instance identification

| | PROD (original) | DEVEL (port) |
|---|---|---|
| dashboard UUID | `ba0abca6-ab92-4d51-94cd-135ead84a74b` | `b1b3ede5-32f2-4c49-a1a8-443dc23bd993` (matches port source YAML) |
| owner | admin | admin |
| isLocked | **true** | false |
| isShared | **false** | true |
| mpName | `VCF Content Factory vCommunity vSphere` | `VCF Content Factory vCommunity vSphere` |
| widget count | 20 | 20 |
| interactions | 19 | 19 |

## Structural diff (from getDashboardConfig)

- **Widget inventory:** 20/20 identical by title. Set difference in both
  directions is empty. All are widget type `View`.
- **Layout:** every widget's `gridsterX/Y/W/H` is identical PROD↔DEVEL (full
  per-widget table verified; zero coordinate/size deltas).
- **Interactions:** 19/19 identical once widget-ids are mapped to titles
  (one "Select a DC or World" → 16 receivers hub, plus "All ESXi Configuration"
  → Network Cards / Network Interfaces / Security Policies / Storage Adapters).
- **`interactionTypes` block:** identical key set on both.
- **Only getDashboardConfig-level deltas:** per-widget `height` (PROD `0` =
  auto, DEVEL `600` px on every widget); dashboard `isLocked`/`isShared`; and
  the dashboard/widget UUIDs (expected — port regenerates deterministic v5-style
  ids). None of these affect widget→view binding or the "No data" symptom.

**getDashboardConfig does NOT expose widget→view bindings, pins, or view
attribute/metric config** — those live in the view ViewDefs, which is where the
real difference is. The bindings were verified against the port source YAML +
the shipped pak content + the vendor reference XML (below).

## The real difference — six property-distribution views

The port source of truth is
`content/sdk-adapters/vcommunity-vsphere/views/*.yaml`. Each of the six
string-property distribution views used by this dashboard is missing
`is_property`/`is_string_attribute`/`buckets: {dynamic, calc_function: DISCRETE}`.
Rendered into the shipped pak (`dist/vcfcf_sdk_vcommunity_vsphere.1.0.0.2.pak`,
`content/reports/<view>/content.xml`) they carry the fatal shape:

| Widget (title) | View | id | attribute (string prop) | port shape | vendor shape |
|---|---|---|---|---|---|
| ESXi Versions | ESXi Distribution by Versions | `524d0468` | `summary\|version` | isProp=**false**, isString=**false**, buckets `[0,100]/10` | isProp=**true**, isString=**true**, no histogram |
| CPU Model | ESXi CPU Models | `38896046` | `cpu\|cpuModel` | false/false/`[0,100]/10` | true/true/no histogram |
| BIOS Version | ESXi BIOS version distribution | `c94b11bf` | `hardware\|biosVersion` | false/false/`[0,100]/10` | true/true/no histogram |
| Power Management (ESXi) | ESXi Power Management | `224daf12` | `hardware\|powerManagementPolicy` | false/false/`[0,100]/10` | true/true/no histogram |
| Power Management (BIOS) | ESXi Power Management (BIOS) | `d204cfc6` | `hardware\|powerManagementTechnoloy` | false/false/`[0,100]/10` | true/true/no histogram |
| Hyper Threading enabled? | ESXi HyperThread Capability | `74639bd8` | `config\|hyperThread\|available` | false/false/`[0,100]/10` | true/true/no histogram |

Port rendered XML (spot-check, `ESXi_Distribution_by_Versions/content.xml`):
`isStringAttribute=false`, `isProperty=false`, `rollUpType=AVG`,
`rollUpCount=1`, `transformations=[CURRENT]`; buckets-control `isDynamic=false`,
`minValue=0.0`, `maxValue=100.0`, `bucketCount=10`.
Vendor original (`View - Set 2/3/4.xml`): `isProperty=true`,
`isStringAttribute=true`, `rollUpCount=0`, no numeric histogram (dynamic
DISCRETE buckets — matches the four already-fixed ESXi Host Details views).

**Two of the six view UUIDs (`524d0468`, `38896046`) are product built-in view
ids** the vendor pack re-defines; the port re-defines them too, with the broken
shape, so on DEVEL the pak-shipped broken ViewDef is what the widget resolves.

### Why the widget shows "No data" + "Metrics displaying 0 of N"

With `isProperty=false` the widget queries the **metric** subsystem for a
numeric metric named e.g. `summary|version` (which does not exist — version is a
**property**). Zero of the candidate metric series resolve → the "0 of N" info
dialog on open and an empty chart. Full mechanism in
`knowledge/context/api-surface/distribution_view_no_data.md`.

## Classification (widget-by-widget)

| Widget | Class | Note |
|---|---|---|
| ESXi Versions, CPU Model, BIOS Version, Power Management (ESXi), Power Management (BIOS), Hyper Threading enabled? (6 widgets) | **KNOWN-DEFECT class / NEW untracked scope** | Same root cause as distribution_view_no_data.md; the shipped fix ("4/4 DISCRETE") covered only the ESXi Host Details four views, NOT these six. Conversion dropped isProperty/isStringAttribute/DISCRETE vs the vendor source ⇒ this is **DRIFT** in the port, currently shipping in v1.0.0.12. **Not tracked in `knowledge/context/defects.md`.** |
| CPU Capacity (cores), CPU Throughput (GHz), Memory Capacity (TB), CPU Sockets, CPU Speed (GHz), NIC Speeds, NIC Counts, Active Storage Paths (8 numeric distributions) | **no delta** | Numeric-range distributions; numeric histogram is the correct model — populate on both. |
| Select a DC or World, All ESXi Configuration, Network Interfaces, Storage Adapters, Security Policies, Network Cards (6 list/pinned) | **no delta** | List views + selfProvider pins render on both (pin wire format fixed in build 11, PR #54). |
| per-widget `height` 0 vs 600 | **BY-DESIGN / cosmetic** | Port renderer emits a fixed 600px widget height; vendor uses auto (0). Layout grid coords identical; not the "No data" cause. |
| `isLocked` true/false, `isShared` false/true | **ENVIRONMENT** | Instance-side flags (PROD dashboard locked+private, DEVEL unlocked+shared). Content-zip import lock/share behaviour varies by build (see dashboard_delete_api.md). Not a port-definition delta. |
| dashboard/widget UUIDs differ | **BY-DESIGN** | Port regenerates deterministic ids; vendor uses random v4. Expected. |

## Is this a NEW defect?

**Yes — NEW / untracked.** `knowledge/context/defects.md` has **no DEF entry** for the
distribution-view "No data" class at all. The only registered touchpoint is
DEF-011's closing evidence citing "4/4 DISCRETE distribution ViewDefs" — that
verified the **four** ESXi Host Details views ship correctly, and implicitly
left these **six** ESXi Configuration 2.0 siblings (and further siblings on
other dashboards, below) still broken. The v1.0.0.12 release ships all six with
the numeric-histogram shape ⇒ this is a live, shipping DRIFT defect that
warrants its own DEF-0NN entry.

### Blast radius beyond this dashboard (same latent defect, other dashboards)

A scan of all port distribution views for `data_type: distribution` without
`is_property: true` flags additional **string/enum/boolean-property**
distributions with the same defect, on other dashboards (out of scope for the
user's ESXi Configuration 2.0 comparison but same fix):
`vSphere Switch Version` (`summary|version`), `vSphere Cluster DRS/HA/DPM Status`
+ `HA Admission Control` + `DRS Automation Level/Status` + `Admission Control
Policy`, and the three `vSphere Port Group` security-policy distributions
(forged transmits / mac changes / promiscuous). (The many *numeric* distribution
views in that scan — CPU GHz, cores, memory, reservations, capacity remaining,
etc. — are correctly numeric and are **not** affected.)

## Recommended remediation (not done here — for orchestrator to route)

1. **view-author:** add `is_property: true`, `is_string_attribute: true`, and
   `buckets: {dynamic: true, calc_function: DISCRETE}` to the six ESXi
   Configuration 2.0 views (and the sibling string-property distributions above),
   mirroring the four already-fixed ESXi Host Details views.
2. **content-packager:** rebuild the pak; **qa-tester** Playwright pass to
   confirm the six widgets populate (internal export endpoint cannot validate
   DISCRETE buckets — browser render is the only proof; see distribution doc Q1).
3. **defects.md:** register a DEF-0NN for the distribution-view No-data class
   (partial-fix residue), listing the six + sibling views; gate the next
   `vcommunity-vsphere` `v*` tag per RULE-012 if adopted as blocking.
4. **tooling (optional, de-risk):** validate-time WARNING when
   `data_type: distribution` has a property-looking attribute with
   `is_property:false` and/or no `buckets:` block — this class silently ships a
   data-less numeric histogram (the exact footgun that produced this defect).

## Method / reproducibility

- `getDashboardConfig` fetch: `scratchpad/fetch_dash.py` (UI-session GET on both
  profiles; logout after; read-only).
- Structural diff: `scratchpad/widgets.py` (layout + interaction alignment).
- Shape confirmation: extracted `dist/vcfcf_sdk_vcommunity_vsphere.1.0.0.2.pak`
  `content/reports/*/content.xml` and compared to vendor
  `reference/references/vmbro_vcf_operations_vcommunity/.../reports/View - Set *.xml`.
- Current port source: `content/sdk-adapters/vcommunity-vsphere/views/*.yaml`.

## Cross-references

- `knowledge/context/api-surface/distribution_view_no_data.md` — root-cause mechanism
  + the four-view fix this defect extends.
- `knowledge/context/reviews/vcommunity-vsphere-prod-devel-comparison.md` — the
  2026-07-13 API-level parity report (did NOT compare dashboard definitions;
  this file closes that gap).
- `knowledge/context/api-surface/dashboard_delete_api.md` — `getDashboardConfig`
  fields; lock/share import behaviour.
- `knowledge/context/defects.md` — DEF-011 "4/4 DISCRETE" evidence (the partial fix).

**Clean-up:** no lab objects created on either instance; all live interaction
was GET/read; UI sessions logged out. Nothing to delete.
