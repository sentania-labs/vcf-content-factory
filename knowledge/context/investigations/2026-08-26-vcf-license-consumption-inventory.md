# VCF License Consumption Overview: offline inventory (2026-08-26)

Source: https://github.com/sentania/AriaOperationsContent, folder `VCF License Consumption Overview`
(Scott's community content, public). Target: rebuild as native factory content
for VCF Operations 8.x.

Inputs (unpacked in the session scratchpad, `lic/`):

| File | Contents |
|---|---|
| `VCF Consumption Overview v2/dashboard/dashboard.json` | 1 dashboard, 12 widgets, content-zip shape (`entries`, `dashboards[]`, `uuid`) |
| `Views/content.xml` | 7 `ViewDef`s |
| `reference/references/AriaOperationsContent/VCF License Consumption Overview/supermetric.json` | 12 super metrics (SM export map keyed by UUID) |

All three exports carry `lastUpdateUserId` / `modifiedBy` `c60c3223-7fad-407f-9939-0fc45817233c`;
dashboard created 2025-02-05, last updated 2025-04-01.

Needs-attention summary (details in section 5):

1. Two super metrics referenced by formula are **not in the export**: `sm_5ea91f64-...` (feeds NSX License Count and Automation License Count) and `sm_3b4464fc-...` (feeds VCF License Potential Cores). Three of the twelve SMs cannot be rebuilt without them.
2. The `License Overview` scoreboard uses `metric.mode: resource` (six metrics pinned to the single `License Usage` resource). The factory loader/renderer and both reverse tools only understand `resourceKindMetrics`; the reverse silently emitted `metrics: []`.
3. Three list views use an `Interval Breakdown` time-segment column (month buckets). The loader has no concept of time-segment columns; the reverse emitted it as a plain metric column, which renders as a bogus `attributeKey="Interval Breakdown"` metric.
4. Trend views lose `FORECAST` and `forecastDays=90` on the round trip (loader has `forecast_days`, but the reverse does not populate it).
5. Self-provider View pins render `entries.resource[].name` as the kind key (`LICENSE_USAGE_WORLD`, `NSXT World`, `CAS World`); the source binds to the resources' display names (`License Usage`, `NSX World`, `Automation World`). Whether the importer resolves by name or by kind needs a live check.

---

## 1. Dashboard

**Name:** `VCF Consumption Overview v2`
**Id:** `0488a094-01f7-417a-80a8-ca2e7fb2d748`
**Layout:** gridster, `gridsterMaxColumns: 12`, `columnCount: 1`, `columnProportion: "1-1"`
**Interactions:** none (`widgetInteractions: []`, `dashboardNavigations: {}`). Every data widget is
`selfProvider: true`; every View widget has `selectFirstRow: false`.
**Description:** empty. `shared: false`, `hidden: false`, `locked: false`, `homeTab: false`.

### 1.1 Entries (synthetic refs used by widgets)

| Ref | Adapter kind | Resource kind | Resource name |
|---|---|---|---|
| `resourceKind:id:0_::_` | NSXTAdapter | NSXT World | (kind ref) |
| `resourceKind:id:1_::_` | CASAdapter | CAS World | (kind ref) |
| `resourceKind:id:2_::_` | VMWARE | vSphere World | (kind ref) |
| `resource:id:0_::_` | VMWARE_INFRA_HEALTH | LICENSE_USAGE_WORLD | `License Usage` |
| `resource:id:1_::_` | NSXTAdapter | NSXT World | `NSX World` |
| `resource:id:2_::_` | CASAdapter | CAS World | `Automation World` |

Hard-coded resource UUIDs: **none**. All resource references go through the synthetic
`resource:id:N_::_` entries above (name-bound at import). Hard-coded `resourceKindId` strings
of the `002019VMWARE_INFRA_HEALTHLICENSE_USAGE_WORLD` / `002011NSXTAdapterNSXT World` /
`002010CASAdapterCAS World` form appear on View widget `resource` blocks and on the
`resourceMetrics` entries; the factory renderer already knows these three prefixes
(`_ADAPTER_KIND_PREFIX` in `src/vcfops_dashboards/render.py`).

### 1.2 Widgets (grid order, y then x)

| # | Widget id | Type | Title | x,y,w,h | Self-provider | Notes |
|---|---|---|---|---|---|---|
| 1 | `767649d5-5fa5-49f9-a399-e9f43639f119` | Scoreboard | License Overview | 1,1,6,5 | yes | `metric.mode: resource`, 6 metrics pinned to `resource:id:0_::_` (License Usage). visualTheme 5, boxColumns 2, roundDecimals 0, oldMetricValues true, showDT false, labelSize 16, valueSize 24, maxCellCount 100 |
| 2 | `9fc2b460-7492-4b20-9d8f-dbe845f65e02` | TextDisplay | Information on Licensing Policy | 7,1,6,5 | n/a | `viewModeHTML: true`, white Arial text on the widget background (HTML preserved in draft) |
| 3 | `94dc7128-775b-4299-8595-7c566a1d4815` | View | VCF License Usage Over Time | 1,6,6,7 | yes, pinned `resource:id:0_::_` | view `e27925b5-...`; `chartViewItems: [legend]`; toolbar state `perm_toolbarVisible` b:1 |
| 4 | `16ab3089-0308-41ec-9c05-4068d41b667b` | View | vSAN License Usage Over Time | 7,6,6,7 | yes, pinned `resource:id:0_::_` | view `0c91a144-...`; `chartViewItems: [legend]` |
| 5 | `c38aa91e-7eb8-4930-bb54-0e71174c7b1c` | Scoreboard | NSX Usage Insights | 1,13,4,6 | yes | `metric.mode: resourceKind`, `subMode: resourceKindAll`, kind `resourceKind:id:0_::_`; showDT true, roundDecimals null, maxCellCount 1000, visualTheme 5, boxColumns 2 |
| 6 | `263242d5-19ca-41ea-9deb-80a717383b7c` | Scoreboard | vSphere Environment Insights | 5,13,4,6 | yes | `resourceKind` mode on `resourceKind:id:2_::_`; showDT true, maxCellCount 100 |
| 7 | `213a1e14-5ea9-4a6e-9f46-72321794cc83` | Scoreboard | Automation Usage Insights | 9,13,4,6 | yes | `resourceKind` mode on `resourceKind:id:1_::_`; showDT true, maxCellCount 1000 |
| 8 | `e06b8f41-a856-4488-80e8-15ec490c1cc8` | View | NSX Consumption Trend | 1,19,6,6 | yes, pinned `resource:id:1_::_` | view `ab24d3c1-...`; legend on |
| 9 | `cfcdc4f7-ec1e-4887-9066-fb9918bcf4f6` | View | Automation Consumption Trend | 7,19,6,6 | yes, pinned `resource:id:2_::_` | view `504f2735-...`; legend on |
| 10 | `04ad7b48-40ac-45a6-9a7a-92be97ea0ded` | View | VCF Consumption Overtime | 1,25,4,6 | yes, pinned `resource:id:0_::_` | view `6b512229-...`; `perm_isDashboardTime` b:0; column-visibility state |
| 11 | `161831fd-7f4d-418e-b20f-08c52dd856d0` | View | NSX Consumption Overtime | 5,25,4,6 | yes, pinned `resource:id:1_::_` | view `e378c921-...`; `perm_isDashboardTime` b:0 |
| 12 | `a19f494c-6c49-4461-83bd-59dbb487d1c6` | View | Automation Consumption Overtime | 9,25,4,6 | yes, pinned `resource:id:2_::_` | view `156aaea0-...` |

All widgets: `refreshInterval: 300`, `refreshContent: false`, `collapsed: false`.
All scoreboard metrics: `colorMethod: 1` (no colouring), no bounds, `showMetricName` true,
`showMetricUnit` true, `showResourceName` false, `showSparkline` false, `layoutMode: fixedView`.

### 1.3 Widget metric keys

**W1 License Overview** (resource mode, every entry `resourceId: resource:id:0_::_`,
`resourceKindId: 002019VMWARE_INFRA_HEALTHLICENSE_USAGE_WORLD`):

| Label | metricKey | metricName |
|---|---|---|
| VCF Consumed Cores | `Super Metric\|sm_76801377-1807-4a46-93d4-9b9dc0f0c54b` | VCF Total License Usage |
| vSAN Consumed TiB | `Super Metric\|sm_ffdafb8e-3c04-4eee-9f33-1096328a6ee3` | vSAN Total License Usage |
| Total VCF License Capacity | `Super Metric\|sm_ad810afa-73c8-412e-a05a-1ba59da79a32` | VCF Total License Count |
| Total vSAN License Capacity (TiB) | `Super Metric\|sm_6e8310ed-1753-45a4-aacc-7f1025c03d11` | vSAN Total License Capacity |
| VCF License Usage % | `Super Metric\|sm_dc0b1bc5-478a-4be9-8442-6afa8fb4b4f8` | VCF Total License Usage Percent (`metricUnitId: -1`, `unit: Auto`) |
| vSAN License Usage % | `Super Metric\|sm_b907e551-0425-418c-90fc-c3132aefd7f0` | vSAN Total License Usage Percent (`metricUnitId: -1`, `unit: Auto`) |

**W5 NSX Usage Insights** (NSXTAdapter / NSXT World, `resourceKindName: "NSX World"`):

| Label | metricKey |
|---|---|
| NSX vSphere Hosts (trailing space in source) | `Super Metric\|sm_52b1e5d9-3598-4f14-8c23-76b082b2c088` (Host Transport Node Count) |
| Overlay Network Count | `Summary\|LogicalSwitchCount` |
| Edge Cluster Count | `Summary\|EdgeClusterCount` |
| NSX Licensed Cores | `Super Metric\|sm_bd174fd5-7cfe-4746-bfcd-436f81a94e50` (NSX License Count) |

**W6 vSphere Environment Insights** (VMWARE / vSphere World):

| Label | metricKey |
|---|---|
| vSphere Hosts | `ObjectCountMetricGroup:HostSystem\|count` |
| Virtual Machines | `ObjectCountMetricGroup:VirtualMachine\|count` |
| Networks | `ObjectCountMetricGroup:DistributedVirtualPortgroup\|count` |
| VCF License Potential Cores | `Super Metric\|sm_7f06f105-c64b-45a3-accd-852c74515df5` (dashboard still carries the SM's old name `License Waste Count`; the SM export has it renamed `VCF License Potential Cores`) |

**W7 Automation Usage Insights** (CASAdapter / CAS World, `resourceKindName: "Automation World"`):

| Label | metricKey |
|---|---|
| Managed vSphere Hosts | `Super Metric\|sm_b8661772-e1c3-4020-b255-b6da7fbdba83` (Automation Host Count) |
| Managed VM Count | `summary\|VMCount` |
| Cost | `summary\|Cost` |
| Automation License Consumption | `Super Metric\|sm_70cb8167-ec3d-4e52-b0cc-08ca191d25b8` (Automation License Count) |

### 1.4 View references

| Widget | viewDefinitionId | View title | Resolves in `Views/content.xml` |
|---|---|---|---|
| W3 | `e27925b5-1cf1-4fde-a835-41c84577be35` | [VCF Consumption Overview v2] VCF License Usage Over Time | yes |
| W4 | `0c91a144-dca0-4625-8c70-8fc4a014fa2e` | [VCF Consumption Overview v2] vSAN Usage Overtime | yes |
| W8 | `ab24d3c1-321b-4aa3-8e8e-fc54644f16a8` | [VCF Consumption Overview v2] NSX Consumption Trend | yes |
| W9 | `504f2735-3d18-45f6-a040-9948f1b98391` | [VCF Consumption Overview v2] Automation Consumption Trend | yes |
| W10 | `6b512229-ff2c-490b-8cfb-ae70f3008de0` | [VCF Consumption Overview v2] VCF Licensing Overtime | yes |
| W11 | `e378c921-1fa7-42e4-a330-dc4423f14cbd` | [VCF Consumption Overview v2] NSX Licensing Overtime | yes |
| W12 | `156aaea0-2fa7-4744-87d2-d01fec6f0ec6` | [VCF Consumption Overview v2] Automation Licensing Overtime | yes |

7 referenced, 7 found, 0 missing. All seven views are used.

---

## 2. Views

Common to all seven: two `SubjectType` elements (`descendant` + `self`) on the same kind, no
filter attribute; usages `dashboard, report, details, content`; no `<Sort>`, no subject filter,
no summary row, no localization keys anywhere in the XML (0 hits for "localiz"); `rollUpType: NONE`,
`rollUpCount: 0`, `isProperty: false`, `isStringAttribute: false` on every metric column.

### 2.1 List views (`Presentation type="list"`, DataProvider `list-view`)

All three share: time-interval-selector `YEARS x 1` (hidden), pagination `size 50`,
`metadata` control with `maxPointsCount 5000`, **`hideObjectNameColumn true`**,
`listTopResultSize -1`. Column 0 in each is the time-segment pseudo-column:

```
attributeKey="Interval Breakdown" isTimeSegment="true" breakdownBy="MONTHS"
startingOnUnit="WEEKS" startingOnCount="1" sortCriteria="false" displayName="Month"
```

Metric columns all carry `transformations=[CURRENT]`, `addTimestampAsColumn false`,
`isShowRelativeTimestamp false`.

**`6b512229-ff2c-490b-8cfb-ae70f3008de0` [VCF Consumption Overview v2] VCF Licensing Overtime**
Subject VMWARE_INFRA_HEALTH / LICENSE_USAGE_WORLD.

| # | attributeKey | displayName | preferredUnitId |
|---|---|---|---|
| 0 | Interval Breakdown | Month | |
| 1 | `Super Metric\|sm_76801377-...` | VCF License Usage | |
| 2 | `Super Metric\|sm_dc0b1bc5-...` | VCF License Usage Percent | percent |
| 3 | `Super Metric\|sm_ad810afa-...` | VCF License Capacity | |
| 4 | `Super Metric\|sm_ffdafb8e-...` | vSAN Total License Usage | |
| 5 | `Super Metric\|sm_b907e551-...` | vSAN License Usage Percent | percent |
| 6 | `Super Metric\|sm_6e8310ed-...` | vSAN License Capacity | |

**`e378c921-1fa7-42e4-a330-dc4423f14cbd` [VCF Consumption Overview v2] NSX Licensing Overtime**
Subject NSXTAdapter / NSXT World.

| # | attributeKey | displayName |
|---|---|---|
| 0 | Interval Breakdown | Month |
| 1 | `Super Metric\|sm_52b1e5d9-...` | NSX Prepared Host Count |
| 2 | `Super Metric\|sm_bd174fd5-...` | NSX License Consumption |

**`156aaea0-2fa7-4744-87d2-d01fec6f0ec6` [VCF Consumption Overview v2] Automation Licensing Overtime**
Subject CASAdapter / CAS World.

| # | attributeKey | displayName |
|---|---|---|
| 0 | Interval Breakdown | Month |
| 1 | `Super Metric\|sm_b8661772-...` | Automation Host Count |
| 2 | `Super Metric\|sm_70cb8167-...` | Automation License Consumption |

### 2.2 Trend views (`Presentation type="line-chart"`, DataProvider `trend-view`)

All four share: time-interval-selector `WEEKS x 12` (hidden), pagination `size 25`, **no
`metadata` control**, every column `forecastDays 90` with `transformations=[NONE, TREND, FORECAST]`.

**`e27925b5-1cf1-4fde-a835-41c84577be35` [VCF Consumption Overview v2] VCF License Usage Over Time**
Subject VMWARE_INFRA_HEALTH / LICENSE_USAGE_WORLD. Description: "This trend view is used to display
the consumption of VCF license usage overtime".
Column: `Super Metric|sm_76801377-...` "VCF License Usage Overtime".

**`0c91a144-dca0-4625-8c70-8fc4a014fa2e` [VCF Consumption Overview v2] vSAN Usage Overtime**
Subject VMWARE_INFRA_HEALTH / LICENSE_USAGE_WORLD. Description is a copy-paste leftover ("This
trend view provides data to the Cpu Core Usage trend in the core distribution dashboard").
Column: `Super Metric|sm_ffdafb8e-...` "vSAN LIcense Usage" (typo in source).

**`ab24d3c1-321b-4aa3-8e8e-fc54644f16a8` [VCF Consumption Overview v2] NSX Consumption Trend**
Subject NSXTAdapter / NSXT World.

| # | attributeKey | displayName |
|---|---|---|
| 0 | `Super Metric\|sm_bd174fd5-...` | NSX License Consumption |
| 1 | `Super Metric\|sm_52b1e5d9-...` | Prepared ESX Hosts |
| 2 | `Summary\|LogicalSwitchCount` | Segment Count |

**`504f2735-3d18-45f6-a040-9948f1b98391` [VCF Consumption Overview v2] Automation Consumption Trend**
Subject CASAdapter / CAS World.

| # | attributeKey | displayName |
|---|---|---|
| 0 | `Super Metric\|sm_70cb8167-...` | Auto License Consumption |
| 1 | `Super Metric\|sm_b8661772-...` | Managed Host Count |
| 2 | `summary\|VMCount` | Managed VM Count |

No view references a super metric by name; all SM columns use the `Super Metric|sm_<uuid>` key form.

---

## 3. Super metrics

Twelve SMs in `supermetric.json`. Names carry the `[VCF Consumption Overview v2]` prefix
(two with irregular spacing: `...v2]  vSAN Total License Usage Percent` has a double space,
`...v2]VCF License Potential Cores` has none).

| Short name | Id | Scoped to | Formula | Refs other SM |
|---|---|---|---|---|
| VCF Total License Usage | `76801377-1807-4a46-93d4-9b9dc0f0c54b` | VMWARE_INFRA_HEALTH / LICENSE_USAGE_WORLD | `sum(${adaptertype=VMWARE_INFRA_HEALTH, objecttype=LicenseUsage, metric=Assets\|TotalUsage, depth=10, where="ProductId startsWith vSphere 8 Enterprise Plus for VCF"})` | no |
| vSAN Total License Usage | `ffdafb8e-3c04-4eee-9f33-1096328a6ee3` | same | `sum(${... metric=Assets\|TotalUsage, depth=10, where="ProductId startsWith vSAN"})` | no |
| VCF Total License Count | `ad810afa-73c8-412e-a05a-1ba59da79a32` | same | `sum(${... metric=CostUnitAttributes\|CostUnitLimit, depth=10, where="ProductId startsWith vSphere 8 Enterprise Plus for VCF"})` | no |
| vSAN Total License Capacity | `6e8310ed-1753-45a4-aacc-7f1025c03d11` | same | `sum(${... metric=CostUnitAttributes\|CostUnitLimit, depth=10, where="ProductId startsWith vSAN"})` | no |
| VCF Total License Usage Percent | `dc0b1bc5-478a-4be9-8442-6afa8fb4b4f8` | same, `unitId: percent` | `(sum(TotalUsage where VCF) / sum(CostUnitLimit where VCF)) * 100` (inline, not via the two SMs above) | no |
| vSAN Total License Usage Percent | `b907e551-0425-418c-90fc-c3132aefd7f0` | same, `unitId: percent` | `(sum(TotalUsage where vSAN) / sum(CostUnitLimit where vSAN)) *100` | no |
| Host Transport Node Count | `52b1e5d9-3598-4f14-8c23-76b082b2c088` | NSXTAdapter / NSXT World | `count(${adaptertype=NSXTAdapter, objecttype=TransportNode, metric=summary\|NodeType, depth=10, where= "summary\|nodetype startsWith HostNode"})` | no |
| Host Transport Node Core Count | `fb06a31b-a213-4613-ad74-bad3058c0176` | NSXTAdapter / NSXT World | identical formula to Host Transport Node Count | no. **Unused** by any widget or view; looks like an abandoned duplicate |
| NSX License Count | `bd174fd5-7cfe-4746-bfcd-436f81a94e50` | NSXTAdapter / NSXT World | `sum(${adaptertype=VMWARE, objecttype=HostSystem, metric=Super Metric\|sm_5ea91f64-b7e9-4a77-baa7-1e8ebea1e322, depth=10})` | **yes: `sm_5ea91f64-...`, NOT in export** |
| Automation Host Count | `b8661772-e1c3-4020-b255-b6da7fbdba83` | CASAdapter / CAS World | `count(${adaptertype=VMWARE, objecttype=HostSystem, attribute=config\|name, depth=10})` | no |
| Automation License Count | `70cb8167-ec3d-4e52-b0cc-08ca191d25b8` | CASAdapter / CAS World | `sum(${adaptertype=VMWARE, objecttype=HostSystem, metric=Super Metric\|sm_5ea91f64-b7e9-4a77-baa7-1e8ebea1e322, depth=10})` | **yes: `sm_5ea91f64-...`, NOT in export** |
| VCF License Potential Cores | `7f06f105-c64b-45a3-accd-852c74515df5` | VMWARE / vSphere World | `${this, metric=Super Metric\|sm_3b4464fc-5dbc-4344-ba8e-e243818df6c6} - ${this, metric=cpu\|corecount_provisioned}` | **yes: `sm_3b4464fc-...`, NOT in export** |

Formula observations for the rebuild:

- `sm_5ea91f64` is evidently a per-host "licensed cores" SM (16-core-per-socket minimum rule); it is
  summed over HostSystem descendants of NSXT World and CAS World. `sm_3b4464fc` is a per-vSphere-World
  total of the same thing (`this` minus `cpu|corecount_provisioned`). Neither is in the repo folder
  (`grep -rl 5ea91f64\|3b4464fc reference/references/AriaOperationsContent` hits only this file). They
  may live in the repo's top-level `Supermetrics/` folder under a different export, or were never
  exported. Both must be recovered or re-authored (the 16-core rounding formula is derivable).
- Host Transport Node Count uses `where= "summary|nodetype startsWith HostNode"` with a space after
  `where=` and a lowercase `nodetype` inside the where clause while the metric is `summary|NodeType`.
  VCF Ops accepted it on Scott's instance; the DSL skill warns about string comparisons in where
  clauses, so treat as a live-verify item.
- The two Percent SMs duplicate the Usage/Count sum expressions inline rather than referencing the
  sibling SMs; the factory could express them as `@supermetric:` references but that changes
  evaluation dependencies (policy enablement order).
- Automation Host Count counts `config|name` on all HostSystem descendants of CAS World, which is
  every host under any vCenter that VCF Automation has as a cloud account (not only hosts with
  Automation-managed VMs).

### 3.1 SM usage cross-reference

| SM | Dashboard widgets | Views |
|---|---|---|
| VCF Total License Usage `76801377` | W1 (VCF Consumed Cores) | VCF Licensing Overtime col1; VCF License Usage Over Time col0 |
| vSAN Total License Usage `ffdafb8e` | W1 (vSAN Consumed TiB) | VCF Licensing Overtime col4; vSAN Usage Overtime col0 |
| VCF Total License Count `ad810afa` | W1 (Total VCF License Capacity) | VCF Licensing Overtime col3 |
| vSAN Total License Capacity `6e8310ed` | W1 (Total vSAN License Capacity) | VCF Licensing Overtime col6 |
| VCF Total License Usage Percent `dc0b1bc5` | W1 (VCF License Usage %) | VCF Licensing Overtime col2 |
| vSAN Total License Usage Percent `b907e551` | W1 (vSAN License Usage %) | VCF Licensing Overtime col5 |
| Host Transport Node Count `52b1e5d9` | W5 (NSX vSphere Hosts) | NSX Licensing Overtime col1; NSX Consumption Trend col1 |
| Host Transport Node Core Count `fb06a31b` | none | none |
| NSX License Count `bd174fd5` | W5 (NSX Licensed Cores) | NSX Licensing Overtime col2; NSX Consumption Trend col0 |
| Automation Host Count `b8661772` | W7 (Managed vSphere Hosts) | Automation Licensing Overtime col1; Automation Consumption Trend col1 |
| Automation License Count `70cb8167` | W7 (Automation License Consumption) | Automation Licensing Overtime col2; Automation Consumption Trend col0 |
| VCF License Potential Cores `7f06f105` | W6 (VCF License Potential Cores) | none |
| *(missing)* `5ea91f64` | none directly | none directly; consumed by NSX License Count and Automation License Count |
| *(missing)* `3b4464fc` | none directly | none directly; consumed by VCF License Potential Cores |

---

## 4. Dependency graph

```
Dashboard: VCF Consumption Overview v2
├── W1 Scoreboard "License Overview"  (pinned resource: License Usage, VMWARE_INFRA_HEALTH/LICENSE_USAGE_WORLD)
│     ├── SM VCF Total License Usage ─────────┐
│     ├── SM vSAN Total License Usage ────────┤
│     ├── SM VCF Total License Count ─────────┤   LicenseUsage.Assets|TotalUsage
│     ├── SM vSAN Total License Capacity ─────┼── LicenseUsage.CostUnitAttributes|CostUnitLimit
│     ├── SM VCF Total License Usage Percent ─┤   LicenseUsage.ProductId (where-clause property)
│     └── SM vSAN Total License Usage Percent ┘
├── W2 TextDisplay (static HTML)
├── W3 View "VCF License Usage Over Time" (trend)  → SM VCF Total License Usage
├── W4 View "vSAN Usage Overtime" (trend)          → SM vSAN Total License Usage
├── W5 Scoreboard "NSX Usage Insights" (kind: NSXT World)
│     ├── SM Host Transport Node Count → TransportNode.summary|NodeType
│     ├── NSXT World.Summary|LogicalSwitchCount
│     ├── NSXT World.Summary|EdgeClusterCount
│     └── SM NSX License Count → HostSystem.Super Metric|sm_5ea91f64 (MISSING)
├── W6 Scoreboard "vSphere Environment Insights" (kind: vSphere World)
│     ├── vSphere World.ObjectCountMetricGroup:HostSystem|count
│     ├── vSphere World.ObjectCountMetricGroup:VirtualMachine|count
│     ├── vSphere World.ObjectCountMetricGroup:DistributedVirtualPortgroup|count
│     └── SM VCF License Potential Cores → vSphere World.Super Metric|sm_3b4464fc (MISSING), vSphere World.cpu|corecount_provisioned
├── W7 Scoreboard "Automation Usage Insights" (kind: CAS World)
│     ├── SM Automation Host Count → HostSystem.config|name
│     ├── CAS World.summary|VMCount
│     ├── CAS World.summary|Cost
│     └── SM Automation License Count → HostSystem.Super Metric|sm_5ea91f64 (MISSING)
├── W8  View "NSX Consumption Trend" (trend)          → SM NSX License Count, SM Host Transport Node Count, NSXT World.Summary|LogicalSwitchCount
├── W9  View "Automation Consumption Trend" (trend)   → SM Automation License Count, SM Automation Host Count, CAS World.summary|VMCount
├── W10 View "VCF Licensing Overtime" (list, month buckets)        → the six LICENSE_USAGE_WORLD SMs
├── W11 View "NSX Licensing Overtime" (list, month buckets)        → SM Host Transport Node Count, SM NSX License Count
└── W12 View "Automation Licensing Overtime" (list, month buckets) → SM Automation Host Count, SM Automation License Count
```

### 4.1 Raw metrics and properties (listed once)

| Adapter kind | Resource kind | Key | Kind | Used by |
|---|---|---|---|---|
| VMWARE_INFRA_HEALTH | LicenseUsage | `Assets\|TotalUsage` | metric | 4 SMs (Usage, Usage Percent x2) |
| VMWARE_INFRA_HEALTH | LicenseUsage | `CostUnitAttributes\|CostUnitLimit` | metric | 4 SMs (Count, Capacity, Percent x2) |
| VMWARE_INFRA_HEALTH | LicenseUsage | `ProductId` | property (where clause, bare key with no group prefix) | 6 SMs |
| NSXTAdapter | TransportNode | `summary\|NodeType` | metric (string) | Host Transport Node Count (+ unused duplicate) |
| NSXTAdapter | NSXT World | `Summary\|LogicalSwitchCount` | metric | W5, NSX Consumption Trend |
| NSXTAdapter | NSXT World | `Summary\|EdgeClusterCount` | metric | W5 |
| CASAdapter | CAS World | `summary\|VMCount` | metric | W7, Automation Consumption Trend |
| CASAdapter | CAS World | `summary\|Cost` | metric | W7 |
| VMWARE | HostSystem | `config\|name` | property | Automation Host Count |
| VMWARE | HostSystem | `Super Metric\|sm_5ea91f64-b7e9-4a77-baa7-1e8ebea1e322` | SM (missing) | NSX License Count, Automation License Count |
| VMWARE | vSphere World | `Super Metric\|sm_3b4464fc-5dbc-4344-ba8e-e243818df6c6` | SM (missing) | VCF License Potential Cores |
| VMWARE | vSphere World | `cpu\|corecount_provisioned` | metric | VCF License Potential Cores |
| VMWARE | vSphere World | `ObjectCountMetricGroup:HostSystem\|count` | metric (instanced group) | W6 |
| VMWARE | vSphere World | `ObjectCountMetricGroup:VirtualMachine\|count` | metric (instanced group) | W6 |
| VMWARE | vSphere World | `ObjectCountMetricGroup:DistributedVirtualPortgroup\|count` | metric (instanced group) | W6 |

Adapter instances required on the target: vCenter (VMWARE), NSX (NSXTAdapter), VCF/Aria
Automation (CASAdapter), and the built-in Infrastructure Health adapter (VMWARE_INFRA_HEALTH)
with license usage collection populating `LicenseUsage` objects under `License Usage`.

---

## 5. Gaps visible offline

### 5.1 Unresolved references inside the input set

| Reference | Referenced from | Status |
|---|---|---|
| `Super Metric\|sm_5ea91f64-b7e9-4a77-baa7-1e8ebea1e322` | NSX License Count, Automation License Count formulas | not in `supermetric.json`, not anywhere in `reference/references/AriaOperationsContent` |
| `Super Metric\|sm_3b4464fc-5dbc-4344-ba8e-e243818df6c6` | VCF License Potential Cores formula | same |

Everything else resolves: 7/7 view ids, 10/12 SM ids referenced by widgets or views (the two
unreferenced are the unused duplicate `fb06a31b` and nothing else; `7f06f105` is widget-only).

Name drift to reconcile: dashboard W6 metricName says `License Waste Count`, SM export says
`VCF License Potential Cores` (same UUID; the SM was renamed after the dashboard was saved).

### 5.2 Widget types vs the factory renderer

`src/vcfops_dashboards/loader.py` `_supported_types` (line 1521) includes `TextDisplay`,
`Scoreboard`, `View`. All three types used here are supported. No unsupported widget type.

### 5.3 Features the loader cannot express (dashboard)

| Feature | Source | Loader/renderer state | Effect |
|---|---|---|---|
| Scoreboard `metric.mode: resource` with `resourceMetrics[]` bound to a specific resource | W1 License Overview (6 metrics on `License Usage`) | `ScoreboardConfig` / `MetricSpec` only model `resourceKindMetrics[]`; renderer emits `mode: resourceKind` (render.py line 1329). Both `reverse.py` `_parse_metric_specs_from_wire` and `reverse_local.py` read only `resourceKindMetrics`, so the draft came out with `metrics: []` and **no WARN** | Workaround candidate: author W1 as `resourceKind` mode on VMWARE_INFRA_HEALTH/LICENSE_USAGE_WORLD (the kind has exactly one resource, `License Usage`). Needs live verification that `subMode: resourceKindAll` on this kind renders the six tiles |
| `showDT: true` (W5, W6, W7) | three scoreboards | not a `ScoreboardConfig` field; renderer emits `showDT: false` | cosmetic (dynamic-threshold colouring is moot with colorMethod 1) |
| `oldMetricValues` (true on W1, false on others) | | renderer emits `true` always | minor |
| `roundDecimals: null` (W5-W7) and `0` (W1) | | loader default `1`; reverse turns null into `1.0` | tiles will show one decimal instead of none |
| `refreshContent: false` | all widgets | renderer emits `true` | widgets will auto-refresh every 300 s on the rebuilt dashboard; source did not |
| `selectFirstRow: false` | all 7 View widgets | loader supports `select_first_row: false`, but `reverse_local.py` does not emit it, so the draft renders `true` | must be added by hand in the draft (rule-of-thumb from the loader docstring: false is the vendor norm) |
| `chartViewItems: ["legend"]` | W3, W4, W8, W9 | not modelled; renderer emits `[]` | trend charts lose the legend |
| Widget `states[]` (toolbar visibility, column-visibility, `perm_isDashboardTime`) | all View widgets | renderer emits none | cosmetic; Ops regenerates on first open |
| `titleLocalized` on TextDisplay | W2 | not emitted | none |
| `columnProportion: "1-1"` | dashboard | renderer emits `"1"` | none for gridster layouts |
| Pinned resource display name | View widgets pin `License Usage`, `NSX World`, `Automation World` | renderer writes `entries.resource[].name` = kind key (`LICENSE_USAGE_WORLD`, `NSXT World`, `CAS World`); `_VIEW_PIN_CONTAINER` in render.py only maps VMWARE leaf kinds and its own comment says the importer resolves `entries.resource[name=...]` by display name | **Live-verify item.** If the importer matches by name, all seven View widgets will fail to bind on 8.x. If it matches by kind, fine. The factory already has evidence for `Automation World` (VCFAutomation dashboard pins by that name) which suggests a name lookup |

### 5.4 Features the loader cannot express (views)

| Feature | Source | Loader/renderer state | Effect |
|---|---|---|---|
| Time-segment column (`Interval Breakdown`, `isTimeSegment`, `breakdownBy=MONTHS`, `startingOnUnit/Count`) | col 0 of the three list views | no field on `ViewColumn`; zero hits for `isTimeSegment` / `Interval Breakdown` across `src/` and `knowledge/`; `reverse_local.py` emits it as `attribute: Interval Breakdown` and the renderer then produces a metric column with `adapterKind`/`resourceKind`/`rollUpType=AVG`/`transformations=[CURRENT]` and none of the segment properties | the three "Overtime" list views lose their whole point (one row per month). **TOOLSET GAP: new `ViewColumn` shape for time segments** |
| `hideObjectNameColumn: true` | the three list views | render.py hardcodes `false` (lines 795, 822, 858) | list views show a redundant object-name column |
| `forecastDays: 90` + `FORECAST` transformation | every trend-view column | loader has view-level `forecast_days` and `transformations` (`ViewDef`, lines 410-413) but `reverse_local.py` never sets them; rendered XML had `[NONE, TREND]` and no `forecastDays` | forecast line lost. Fixable by hand in the draft (`forecast_days: 90`, `transformations: [NONE, TREND, FORECAST]`) if the renderer honours them; not verified here |
| Pagination size (50 list / 25 trend) | all views | renderer emits 500 | none functionally |
| `metadata` control absent on trend views | 4 trend views | renderer adds one | harmless (importer accepted this shape on vmbro content) |
| `rollUpCount: 0` | all columns | renderer emits `1` | none observed elsewhere |
| `rollUpType: NONE` on raw-metric trend columns | `Summary\|LogicalSwitchCount`, `summary\|VMCount` | renderer emits `AVG` | may change how the trend line is sampled |
| Per-column `preferredUnitId=percent` | two columns in VCF Licensing Overtime | supported (`unit: percent`) and round-tripped correctly | none |

### 5.5 Version-specific concerns (8.x target)

- The source was authored on a 9.x-era instance (v2 of the dashboard, Feb-Apr 2025; the SM where
  clause filters on `ProductId startsWith vSphere 8 Enterprise Plus for VCF`). The
  `VMWARE_INFRA_HEALTH` / `LICENSE_USAGE_WORLD` / `LicenseUsage` object model and the
  `Assets|TotalUsage` / `CostUnitAttributes|CostUnitLimit` keys need confirming on 8.x via
  `ops-recon` before any SM is authored; they are not in the repo's recon log (only the adapter kind
  itself is, with `null (no creds)` on the lab instance).
- `ObjectCountMetricGroup:<Kind>|count` on vSphere World and the NSX `Summary|LogicalSwitchCount` /
  `Summary|EdgeClusterCount` keys also need a live check; neither appears in `knowledge/`.
- `resourceKindName` display names in the export (`NSX World`, `Automation World`) are 9.x display
  names; on 8.x the NSX-T adapter world may still be called "NSX-T World" and Automation "vRA World"
  or "CAS World". Name-bound pins (5.3 last row) are the exposure.
- Product-string filter `vSphere 8 Enterprise Plus for VCF` is a literal; on an 8.x install with VCF 5.x
  keys the ProductId strings may differ and the SMs would sum to zero silently.
- Nothing in the three files is inherently 9.x-only at the wire-format level (no `Section`,
  `AlertVolume`, gauge theme, or new widget types).

### 5.6 Framework-prefix and naming

All content carries `[VCF Consumption Overview v2]` (SMs, views) and the dashboard has no prefix.
Native factory content needs the `[VCF Content Factory]` prefix on every name (the validator
rejected the raw draft on exactly that); alternatively ship as a third-party bundle with
`factory_native: false`. Two SM names have irregular spacing that a rename should normalise.

---

## 6. Offline reverse to factory YAML (baseline)

Command (SM YAML first, because `reverse-local` requires an `--sm-dir` of YAML files with `id:` and
`name:` to rewrite `sm_<uuid>` to `@supermetric:"name"`):

1. Generated 12 draft SM YAMLs from `supermetric.json` with a small script (id, name, formula with
   in-set `Super Metric|sm_<uuid>` rewritten to `@supermetric:"<name>"`, description, unit_id,
   resource_kinds from `resourceKinds[]`). Three formulas keep raw `sm_<uuid>` tokens because the
   targets are missing (5.1).
2. `PYTHONPATH=src .venv/bin/python -m vcfops_extractor reverse-local --dashboard-json '<scratch>/lic/VCF Consumption Overview v2/dashboard/dashboard.json' --view-xml-dir '<scratch>/lic/Views' --sm-dir '<scratch>/lic/draft/supermetrics' --output-views '<scratch>/lic/draft/views' --output-dashboards '<scratch>/lic/draft/dashboards' --name-path ''`

Output location: `<scratchpad>/lic/draft/{supermetrics,views,dashboards}/` (12 + 7 + 1 files).
Nothing under `content/`, nothing committed.

Reverse tool output (verbatim, trimmed to the substantive lines):

```
  SM map built: 12 super metric(s) from .../lic/draft/supermetrics
  Scanning 1 XML file(s) in .../lic/Views
    content.xml: 7 new ViewDef(s)
  View map total: 7 ViewDef(s)
Found 1 dashboard(s) in source file

Views referenced: 7
  Found in XML:  7

All widget types in source: ['Scoreboard', 'TextDisplay', 'View']

--- Writing 7 view YAML(s) ---
  wrote view: .../draft/views/VCF Consumption Overview v2 Automation Consumption Trend.yaml
  wrote view: .../draft/views/VCF Consumption Overview v2 Automation Licensing Overtime.yaml
  wrote view: .../draft/views/VCF Consumption Overview v2 NSX Consumption Trend.yaml
  wrote view: .../draft/views/VCF Consumption Overview v2 NSX Licensing Overtime.yaml
  wrote view: .../draft/views/VCF Consumption Overview v2 VCF License Usage Over Time.yaml
  wrote view: .../draft/views/VCF Consumption Overview v2 VCF Licensing Overtime.yaml
  wrote view: .../draft/views/VCF Consumption Overview v2 vSAN Usage Overtime.yaml

--- Writing 1 dashboard YAML(s) ---
  wrote dashboard: .../draft/dashboards/VCF Consumption Overview v2.yaml

--- Round-trip diff check ---
  MATCH      'VCF Consumption Overview v2'  (12/12 widgets)

SUMMARY
  Views written:      7
  Dashboards written: 1
  Round-trip: 1 MATCH, 0 PARTIAL, 0 UNSUPPORTED/ERROR
exit=0
```

No errors, no WARN lines. Note the `MATCH` verdict is structural only: `_structural_key()` in
`reverse_local.py` compares widget type, gridster coords and `viewDefinitionId`, so it did not
notice that W1 lost all six metrics.

### 6.1 What the reverse produced

- Dashboard YAML: 12 widgets with correct ids, types, titles, coords; TextDisplay HTML preserved
  verbatim; the three kind-mode scoreboards with all 4 metrics each (adapter/resource kind resolved
  from `entries`, `color_method: 1`, labels, `visual_theme: 5`, `box_columns: 2`, `label_size: 16`);
  seven View widgets with `self_provider: true`, a `pin:` block resolved from the `entries.resource`
  ref (VMWARE_INFRA_HEALTH/LICENSE_USAGE_WORLD, NSXTAdapter/NSXT World, CASAdapter/CAS World), and
  `view:` by name. `interactions: []`.
- View YAMLs: name, id, subject, columns with `supermetric:"<name>"` attributes and display names,
  `unit: percent` where set, `data_type: trend` on the four trend views, `time_window` (YEARS 1 /
  WEEKS 12) on all seven.
- SM YAMLs: as generated in step 1 (not produced by the reverse tool; the extractor's SM writer is
  only reachable from the live `extract dashboard` path).

### 6.2 What the reverse dropped (silently unless noted)

Dashboard: W1 `resourceMetrics[]` (all six metrics; `metrics: []`), `select_first_row: false` on
all View widgets, `chartViewItems` legend, `showDT`, `oldMetricValues`, `refreshContent`,
`roundDecimals: null` (became 1.0), widget `states`, `titleLocalized`, dashboard description
(empty anyway), `columnProportion`. Scoreboard `metric_name` values were carried through as the
long `Super Metrics|[VCF Consumption Overview v2] ...` display strings.

Views: `Interval Breakdown` time-segment properties (kept only as a bare attribute name),
`forecastDays`, the `FORECAST` transformation, `hideObjectNameColumn: true`, pagination sizes,
`rollUpType: NONE` on raw-metric trend columns, `DataProvider` ids (regenerated, harmless).
View descriptions on the two views that had them were preserved.

### 6.3 Validation and render check of the draft

The raw draft fails `python -m vcfops_dashboards validate` on the framework-prefix rule:

```
INVALID: .../draft/views/VCF Consumption Overview v2 Automation Consumption Trend.yaml: name "[VCF Consumption Overview v2] Automation Consumption Trend" missing framework prefix "[VCF Content Factory]". ...
```

A throwaway copy (`lic/draft_prefixed/`, names rewritten to `[VCF Content Factory] ...`) validates
clean (`OK: 7 view definition(s), 1 dashboard(s) valid`, plus a WARNING that the id-stability guard
cannot run outside a git repo) and packages (`package -o out.zip`, run with cwd set so the
`supermetrics/` dir is found; the package command has no `--supermetrics-dir` flag and resolves
`./supermetrics` relative to cwd). The rendered `dashboard.json` and `views/content.xml` were
diffed against the source; every divergence is listed in 5.3 and 5.4.

One rendering detail worth flagging: the renderer regenerates widget ids (deterministic UUIDv5
from name+id) rather than preserving the source widget ids, so a re-import will not overwrite the
original widgets in place; the dashboard id itself is preserved.

---

## 7. Suggested rebuild order (for the orchestrator, not a build order)

1. Recover or re-author `sm_5ea91f64` (per-host licensed cores, 16-core minimum) and `sm_3b4464fc`
   (vSphere World total licensed cores); check Scott's repo `Supermetrics/` folder first.
2. `ops-recon` on 8.x: `LICENSE_USAGE_WORLD` / `LicenseUsage` keys, `ProductId` strings, NSX and
   Automation world display names, `ObjectCountMetricGroup` keys, and whether a View pin binds by
   resource name or kind.
3. Toolset decisions: time-segment view column (blocking for the three list views), resource-mode
   scoreboard or kind-mode workaround for W1, `hideObjectNameColumn`, `showDT`, `chartViewItems`,
   `forecast_days` population in `reverse_local.py`.
4. Then the normal path: intent files, SM author (10 SMs, drop the unused duplicate), view author
   (7), wireframe gate, dashboard author, validate, install.
