# VCF Licensing by Month

- **Type:** view
- **Slug:** vcf-license-vcf-licensing-overtime
- **Authored YAML:** views/vcf_license_vcf_licensing_overtime.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- Month-by-month table of VCF and vSAN consumption vs capacity over the last year, for the
  `VCF Consumption Overtime` widget (W10). Audience: whoever reconciles license position
  with Broadcom.
- Renamed "Overtime" to "by Month" so the name says what the rows are.

## Spec

**Name:** `[VCF Content Factory] VCF Licensing by Month`. Source: `[VCF Consumption Overview v2] VCF Licensing Overtime`.


**Subject:** `VMWARE_INFRA_HEALTH / LICENSE_USAGE_WORLD` ("License Usage", 1 object) (descendant + self, no filter, as source).

**Kind:** list (month-bucketed table)

**Window:** `time_window: YEARS x 1` (source: hidden time-interval-selector YEARS 1); rows are month buckets from the time-segment column

**Columns (in order):**

| # | Column | Key | Unit |
|---|---|---|---|
| 0 | Month | time-segment column, `breakdownBy=MONTHS`, `startingOnUnit=WEEKS`, `startingOnCount=1` | |
| 1 | VCF License Usage | `supermetric:"[VCF Content Factory] VCF Total License Usage (cores)"`, CURRENT | |
| 2 | VCF License Usage Percent | `supermetric:"[VCF Content Factory] VCF Total License Usage (%)"`, CURRENT | percent |
| 3 | VCF License Capacity | `supermetric:"[VCF Content Factory] VCF Total License Capacity (cores)"`, CURRENT | |
| 4 | vSAN Total License Usage | `supermetric:"[VCF Content Factory] vSAN Total License Usage (TiB)"`, CURRENT | |
| 5 | vSAN License Usage Percent | `supermetric:"[VCF Content Factory] vSAN Total License Usage (%)"`, CURRENT | percent |
| 6 | vSAN License Capacity | `supermetric:"[VCF Content Factory] vSAN Total License Capacity (TiB)"`, CURRENT | |


**List-view settings (source):** `hideObjectNameColumn: true` (subject has one object, the
name column is noise), pagination 50, `listTopResultSize -1`, no sort, no summary row.

**Time-segment column (TOOLSET GAP, blocking):** column 0 in the source is
`attributeKey="Interval Breakdown" isTimeSegment="true" breakdownBy="MONTHS"
startingOnUnit="WEEKS" startingOnCount="1" displayName="Month"`. It is what turns a
one-object view into one row per month. `ViewColumn` has no such shape and the renderer
would emit a bogus `Interval Breakdown` metric column. Needs `tooling` to add a
time-segment column type (proposed YAML: `time_segment: {{breakdown_by: MONTHS,
starting_on_unit: WEEKS, starting_on_count: 1}}` with `display_name: Month`) and to expose
`hide_object_name_column: true` (currently hardcoded false at render.py 795/822/858).
`view-author` must not author this view until that lands; a plain list without the segment
column is not an acceptable downgrade (it would show one row).
