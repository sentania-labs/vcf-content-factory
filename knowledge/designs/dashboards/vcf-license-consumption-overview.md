# VCF License Consumption Overview

- **Type:** dashboard
- **Slug:** vcf-license-consumption-overview
- **Authored YAML:** dashboards/vcf_license_consumption_overview.yaml
- **Date:** 2026-08-26
- **Status:** approved by Scott 2026-08-26 (mock `vcf-license-consumption-overview.html` and wireframe table; licensing rule for the two re-derived SMs confirmed)

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- One-screen license position for a VCF estate on VCF Operations 8.x: consumed vs owned VCF
  cores and vSAN TiB (from the platform's own license usage objects), plus how much of the
  vSphere estate NSX and Automation actually touch, with 12-week trends and month tables.
- Audience: the admin reconciling license consumption with Broadcom; not a capacity tool.
- Layout is a faithful copy of Scott's v2 grid (12 widgets, same coordinates). Changes are
  confined to naming, the two missing super metrics, and the Potential Cores bug fix.
- Name: `[VCF Content Factory] VCF License Consumption Overview`, folder `VCF Content Factory`.
  Source dashboard was `VCF Consumption Overview v2` with no prefix.
- Recon: nothing to reuse on ro818/prod or in the repo; from-scratch authoring.

## Wireframe (RULE-011, approved 2026-08-26)

12-column gridster, 1-based coords as source. Rows are 1 unit each; source `h` values kept.

```
x:  1     2     3     4     5     6     7     8     9    10    11    12
   +-----------------------------------+-----------------------------------+  y=1
   | W1 Scoreboard: License Overview   | W2 Text: Information on           |
   |   (resource mode, License Usage)  |    Licensing Policy               |  h=5
   |   6 tiles, 2 columns              |    (static HTML)                  |
   +-----------------------------------+-----------------------------------+  y=6
   | W3 View: VCF License Usage Trend  | W4 View: vSAN License Usage Trend |
   |   pin License Usage, legend       |   pin License Usage, legend       |  h=7
   +-----------------------+-----------+-----------+-----------------------+  y=13
   | W5 Scoreboard:        | W6 Scoreboard:        | W7 Scoreboard:        |
   |  NSX Usage Insights   |  vSphere Environment  |  Automation Usage     |  h=6
   |  (kind: NSXT World)   |  Insights (vSphere    |  Insights (kind: CAS  |
   |  w=4                  |  World) w=4           |  World) w=4           |
   +-----------------------+-----------+-----------+-----------------------+  y=19
   | W8 View: NSX Consumption Trend    | W9 View: Automation Consumption   |
   |   pin NSX World, legend           |   Trend, pin Automation World     |  h=6
   +-----------------------+-----------+-----------+-----------------------+  y=25
   | W10 View: VCF         | W11 View: NSX         | W12 View: Automation  |
   |  Licensing by Month   |  Licensing by Month   |  Licensing by Month   |  h=6
   |  pin License Usage    |  pin NSX World        |  pin Automation World |
   +-----------------------+-----------------------+-----------------------+  y=31
```

### Widget table (machine-readable twin of the mock)

| # | id | Type | Title | x | y | w | h | Subject / pin | Content |
|---|---|---|---|---|---|---|---|---|---|
| W1 | `license_overview` | Scoreboard | License Overview | 1 | 1 | 6 | 5 | **resource mode**, `VMWARE_INFRA_HEALTH / LICENSE_USAGE_WORLD` resource `License Usage` | 6 metrics, table below |
| W2 | `licensing_policy_text` | TextDisplay | Information on Licensing Policy | 7 | 1 | 6 | 5 | n/a | source HTML verbatim, `viewModeHTML: true` (text below) |
| W3 | `vcf_usage_trend` | View | VCF License Usage Over Time | 1 | 6 | 6 | 7 | pin `LICENSE_USAGE_WORLD` / `License Usage` | `[VCF Content Factory] VCF License Usage Trend` |
| W4 | `vsan_usage_trend` | View | vSAN License Usage Over Time | 7 | 6 | 6 | 7 | pin `License Usage` | `[VCF Content Factory] vSAN License Usage Trend` |
| W5 | `nsx_insights` | Scoreboard | NSX Usage Insights | 1 | 13 | 4 | 6 | kind mode, `NSXTAdapter / NSXT World`, subMode resourceKindAll | 4 metrics, table below |
| W6 | `vsphere_insights` | Scoreboard | vSphere Environment Insights | 5 | 13 | 4 | 6 | kind mode, `VMWARE / vSphere World` | 4 metrics |
| W7 | `automation_insights` | Scoreboard | Automation Usage Insights | 9 | 13 | 4 | 6 | kind mode, `CASAdapter / CAS World` | 4 metrics |
| W8 | `nsx_trend` | View | NSX Consumption Trend | 1 | 19 | 6 | 6 | pin `NSXTAdapter / NSXT World` / `NSX World` | `[VCF Content Factory] NSX Consumption Trend` |
| W9 | `automation_trend` | View | Automation Consumption Trend | 7 | 19 | 6 | 6 | pin `CASAdapter / CAS World` / `Automation World` | `[VCF Content Factory] Automation Consumption Trend` |
| W10 | `vcf_by_month` | View | VCF Consumption by Month | 1 | 25 | 4 | 6 | pin `License Usage` | `[VCF Content Factory] VCF Licensing by Month` |
| W11 | `nsx_by_month` | View | NSX Consumption by Month | 5 | 25 | 4 | 6 | pin `NSX World` | `[VCF Content Factory] NSX Licensing by Month` |
| W12 | `automation_by_month` | View | Automation Consumption by Month | 9 | 25 | 4 | 6 | pin `Automation World` | `[VCF Content Factory] Automation Licensing by Month` |

All widgets: `self_provider: true` (W2 n/a), refresh 300 s, `select_first_row: false` on every
View widget (author must set it; the reverse tool dropped it). Scoreboards: `color_method: 1`
(no colouring), `visual_theme: 5`, `box_columns: 2`, `show_metric_name`/`show_metric_unit` true,
no sparkline, no bounds. W1 `round_decimals: 0`; W5-W7 source `null` (loader default 1 is
acceptable). Trend View widgets W3, W4, W8, W9 carry `chartViewItems: [legend]` in source
(not modelled by the loader; cosmetic loss, see constraints).

### W1 License Overview (resource mode, six metrics on `License Usage`)

| Label | metric_key | metric_name |
|---|---|---|
| VCF Consumed Cores | `Super Metric|` `[VCF Content Factory] VCF Total License Usage (cores)` | VCF Total License Usage (cores) |
| vSAN Consumed TiB | `Super Metric|` `[VCF Content Factory] vSAN Total License Usage (TiB)` | vSAN Total License Usage (TiB) |
| Total VCF License Capacity | `Super Metric|` `[VCF Content Factory] VCF Total License Capacity (cores)` | VCF Total License Capacity (cores) |
| Total vSAN License Capacity (TiB) | `Super Metric|` `[VCF Content Factory] vSAN Total License Capacity (TiB)` | vSAN Total License Capacity (TiB) |
| VCF License Usage % | `Super Metric|` `[VCF Content Factory] VCF Total License Usage (%)`, unit Auto | VCF Total License Usage (%) |
| vSAN License Usage % | `Super Metric|` `[VCF Content Factory] vSAN Total License Usage (%)`, unit Auto | vSAN Total License Usage (%) |

SM keys resolve by name to `Super Metric|sm_<uuid>` at validate time.

### W5 NSX Usage Insights (kind: NSXT World)

| Label | metric_key |
|---|---|
| NSX vSphere Hosts | SM `[VCF Content Factory] NSX Host Transport Node Count` |
| Overlay Network Count | `Summary|LogicalSwitchCount` (8.18-verified) |
| Edge Cluster Count | `Summary|EdgeClusterCount` (8.18-verified) |
| NSX Licensed Cores | SM `[VCF Content Factory] NSX Licensed Cores` |

### W6 vSphere Environment Insights (kind: vSphere World)

| Label | metric_key |
|---|---|
| vSphere Hosts | `ObjectCountMetricGroup:HostSystem|count` (dynamic instance, populated on 8.18: 42) |
| Virtual Machines | `ObjectCountMetricGroup:VirtualMachine|count` (722) |
| Networks | `ObjectCountMetricGroup:DistributedVirtualPortgroup|count` (61) |
| VCF License Potential Cores | SM `[VCF Content Factory] VCF License Potential Cores` (source metric_name was the stale `License Waste Count`) |

### W7 Automation Usage Insights (kind: CAS World)

| Label | metric_key |
|---|---|
| Managed vSphere Hosts | SM `[VCF Content Factory] Automation Managed Host Count` |
| Managed VM Count | `summary|VMCount` (statkey defined on 8.18, 0 CAS resources) |
| Cost | `summary|Cost` (same) |
| Automation License Consumption | SM `[VCF Content Factory] Automation Licensed Cores` |

### W2 text (source HTML, keep verbatim in YAML; plain text here)

> This Dashboard provides an overview of total VCF license consumption and it's components:
> vSAN, Aria, and NSX.
> VCF and vSAN consumption is measured directly from the platform.
> To understand the usage of NSX and Automation in your environment, review the NSX and
> Automation Insights vs. the vSphere Environment Insights.
> It is normal to have some number of virtual machines, networks and hosts that are not
> managed by NSX or Automation, as this indicates legacy workloads or management domains.
> Use the NSX and Automation Trends charts to understand the pattern of usage in your
> environment.

White Arial text on the widget background. Author may replace "Aria" with "Automation" for 8.x
naming consistency; otherwise verbatim.

### Interactions

None. `interactions: []`, no dashboard navigations. Every widget is self-provider with a
pinned World-level object or kind.

### Constraints that shaped the layout

1. **Resource-mode scoreboard (TOOLSET GAP).** W1 pins six metrics to the single `License
   Usage` object (`metric.mode: resource`, `resourceMetrics[]`). The loader/renderer only
   model `resourceKindMetrics`. Options: (a) `tooling` adds a resource-mode Scoreboard
   (preferred, faithful); (b) author W1 as kind mode on `VMWARE_INFRA_HEALTH /
   LICENSE_USAGE_WORLD` with `subMode: resourceKindAll`; the kind has exactly one object so
   it should render six tiles. (b) needs a live check before it is accepted.
2. **Time-segment view column (TOOLSET GAP, blocking W10-W12).** See the three "by Month"
   view notes. Without it the bottom row shows one row each.
3. **View pins bind by display name.** Source pins `License Usage`, `NSX World`, `Automation
   World`; the renderer writes the kind key as the entry name. On 8.18 the NSX world display
   name may be `NSX-T World` and Automation `CAS World` or `vRA World`. `ops-recon` must read
   the three display names on ro818 before the author spawns; if the importer resolves by
   name, the pin block must carry the 8.18 names.
4. **Automation section is 8.x vocabulary.** `CASAdapter / CAS World` and `summary|VMCount` /
   `summary|Cost`. On 9.x that adapter is superseded by `VCFAutomation / Automation World`
   with `summary|total_vms` and `Aggregate|VCFAOrganization|cost|aggregatedMtdTotalCost`.
   Out of scope for this 8.x build; a 9.x variant would swap W7, W9, W12 and the two
   Automation SMs' assignment.
5. **Lab coverage.** ro818 has license data (VCF/vSAN half testable) but 0 TransportNode and 0
   CAS resources (NSX/Automation half validates structurally only). Prod is the inverse.
   Expect empty tiles in W5 (hosts, cores), W7, W8, W9, W11, W12 on ro818.
6. **Cosmetic losses accepted:** trend legend (`chartViewItems`), `showDT`, `oldMetricValues`,
   `refreshContent: false` (rebuilt widgets auto-refresh every 300 s), widget `states`,
   `columnProportion`. Widget ids are regenerated (deterministic); the dashboard id is new,
   so the rebuild installs alongside the original rather than overwriting it.
7. **Dashboard id:** new factory UUID, not the source `0488a094-...`, because names and SMs
   differ and the two can coexist on a lab that has the community version.

## Deviations from the source (complete list)

| # | Where | Source | Rebuild | Why |
|---|---|---|---|---|
| 1 | all names | `[VCF Consumption Overview v2]` (two with broken spacing), dashboard unprefixed | `[VCF Content Factory]` | RULE-006 |
| 2 | SM `Host Transport Node Core Count` | present, identical to Host Transport Node Count | dropped | unused by any widget or view |
| 3 | SM `sm_5ea91f64` | missing from export | re-derived as `Host VCF Licensed Cores (16-core minimum)` on HostSystem | consumers sum a per-host core value; ASSUMPTION for Scott |
| 4 | SM `sm_3b4464fc` | missing from export | re-derived as `vSphere World VCF Licensed Cores` (sum of #3 at World) | consumer reads it as `this` on vSphere World; ASSUMPTION for Scott |
| 5 | SM `VCF License Potential Cores` | `this` minus HostSystem metric at World scope (cannot evaluate) | World SM minus `sum(HostSystem cpu|corecount_provisioned, depth=10)` | resource-kind/formula mismatch (recon gap 3) |
| 6 | W6 metric_name | `License Waste Count` | `VCF License Potential Cores` | stale name in dashboard export |
| 7 | the two Percent SMs | inline duplicated sums | `@supermetric:` references to the Usage and Capacity SMs | one place to change the product filter; adds enable ordering |
| 8 | SM `Host Transport Node Count` where clause | `where= "summary|nodetype startsWith HostNode"` | `where="summary|NodeType startsWith HostNode"` | exact catalog spelling; flag if lowercase was load-bearing |
| 9 | SM/view descriptions | "vSAN" on the VCF usage SM, CPU-core leftover on the vSAN trend view, "LIcense" typo | corrected | copy-paste artefacts |
| 10 | View names "... Overtime" | | "... by Month" / "... Trend" | says what the rows are |
| 11 | `NSX License Count` / `Automation License Count` / `VCF Total License Count` display names | Count | Licensed Cores / Capacity (cores) | unit in the name per DSL style; "Count" was misleading (they are core sums) |
| 12 | W1 mode | resource mode | resource mode if tooling adds it, else kind mode on LICENSE_USAGE_WORLD | loader gap (constraint 1) |
| 13 | View widgets | `selectFirstRow: false` | same, set by hand | reverse tool dropped it |
| 14 | cosmetics | legend, showDT, refreshContent false, states, pagination 50/25 | loader defaults | not modelled; accepted |
| 15 | dashboard id, widget ids | source UUIDs | new deterministic ids | coexist with the community install |
