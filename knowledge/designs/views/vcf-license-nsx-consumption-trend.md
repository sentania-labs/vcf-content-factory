# NSX Consumption Trend

- **Type:** view
- **Slug:** vcf-license-nsx-consumption-trend
- **Authored YAML:** views/vcf_license_nsx_consumption_trend.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- 12-week NSX consumption pattern (licensed cores, prepared hosts, segments), widget W8.

## Spec

**Name:** `[VCF Content Factory] NSX Consumption Trend`. Source: `[VCF Consumption Overview v2] NSX Consumption Trend`.


**Subject:** `NSXTAdapter / NSXT World` (1 object on ro818) (descendant + self, no filter, as source).

**Kind:** trend (line chart)

**Window:** `time_window: WEEKS x 12` plus 90-day forecast (`forecast_days: 90`)

**Columns (in order):**

| # | Column | Key |
|---|---|---|
| 0 | NSX License Consumption | `supermetric:"[VCF Content Factory] NSX Licensed Cores"`, NONE/TREND/FORECAST |
| 1 | Prepared ESX Hosts | `supermetric:"[VCF Content Factory] NSX Host Transport Node Count"`, NONE/TREND/FORECAST |
| 2 | Segment Count | raw `Summary|LogicalSwitchCount` on NSXT World (8.18-verified, 0.0 on ro818), NONE/TREND/FORECAST |


**Trend-view settings (source):** `data_type: trend`, presentation line-chart, every column
`transformations: [NONE, TREND, FORECAST]`, `forecast_days: 90`, pagination 25, no metadata
control. The loader has `forecast_days` and `transformations` on `ViewDef`; the author sets
them by hand (the reverse tool did not). Renderer honouring of `forecastDays` is unverified;
check the rendered XML for `forecastDays="90"` and `FORECAST` before install.

**Roll-up:** source has `rollUpType: NONE` on every column; renderer emits AVG. Raw-metric
columns may sample differently; accept unless the chart looks wrong on the lab.
