# Automation Consumption Trend

- **Type:** view
- **Slug:** vcf-license-automation-consumption-trend
- **Authored YAML:** views/vcf_license_automation_consumption_trend.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- 12-week Automation consumption pattern, widget W9.

## Spec

**Name:** `[VCF Content Factory] Automation Consumption Trend`. Source: `[VCF Consumption Overview v2] Automation Consumption Trend`.


**Subject:** `CASAdapter / CAS World` (0 objects on ro818; structural only) (descendant + self, no filter, as source).

**Kind:** trend (line chart)

**Window:** `time_window: WEEKS x 12` plus 90-day forecast (`forecast_days: 90`)

**Columns (in order):**

| # | Column | Key |
|---|---|---|
| 0 | Automation License Consumption | `supermetric:"[VCF Content Factory] Automation Licensed Cores"`, NONE/TREND/FORECAST |
| 1 | Managed Host Count | `supermetric:"[VCF Content Factory] Automation Managed Host Count"`, NONE/TREND/FORECAST |
| 2 | Managed VM Count | raw `summary|VMCount` on CAS World (statkey defined on 8.18, 0 resources), NONE/TREND/FORECAST |


**Trend-view settings (source):** `data_type: trend`, presentation line-chart, every column
`transformations: [NONE, TREND, FORECAST]`, `forecast_days: 90`, pagination 25, no metadata
control. The loader has `forecast_days` and `transformations` on `ViewDef`; the author sets
them by hand (the reverse tool did not). Renderer honouring of `forecastDays` is unverified;
check the rendered XML for `forecastDays="90"` and `FORECAST` before install.

**Roll-up:** source has `rollUpType: NONE` on every column; renderer emits AVG. Raw-metric
columns may sample differently; accept unless the chart looks wrong on the lab.
