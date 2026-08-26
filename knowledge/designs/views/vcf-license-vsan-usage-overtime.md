# vSAN License Usage Trend

- **Type:** view
- **Slug:** vcf-license-vsan-usage-overtime
- **Authored YAML:** views/vcf_license_vsan_usage_overtime.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- 12-week trend of consumed vSAN TiB with a 90-day forecast, widget W4.
- Source column title had a typo ("LIcense") and the description was a copy-paste leftover
  about CPU core distribution; both replaced.

## Spec

**Name:** `[VCF Content Factory] vSAN License Usage Trend`. Source: `[VCF Consumption Overview v2] vSAN Usage Overtime`.


**Subject:** `VMWARE_INFRA_HEALTH / LICENSE_USAGE_WORLD` ("License Usage", 1 object) (descendant + self, no filter, as source).

**Kind:** trend (line chart)

**Window:** `time_window: WEEKS x 12` plus 90-day forecast (`forecast_days: 90`)

**Columns (in order):**

| # | Column | Key |
|---|---|---|
| 0 | vSAN License Usage | `supermetric:"[VCF Content Factory] vSAN Total License Usage (TiB)"`, NONE/TREND/FORECAST, forecast 90d |


**Trend-view settings (source):** `data_type: trend`, presentation line-chart, every column
`transformations: [NONE, TREND, FORECAST]`, `forecast_days: 90`, pagination 25, no metadata
control. The loader has `forecast_days` and `transformations` on `ViewDef`; the author sets
them by hand (the reverse tool did not). Renderer honouring of `forecastDays` is unverified;
check the rendered XML for `forecastDays="90"` and `FORECAST` before install.

**Roll-up:** source has `rollUpType: NONE` on every column; renderer emits AVG. Raw-metric
columns may sample differently; accept unless the chart looks wrong on the lab.
