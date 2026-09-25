# [VCF Content Factory] UniFi Switches

- **Type:** view (bundled in the pak)
- **Slug:** unifi-switches
- **Authored YAML:** content/sdk-adapters/unifi/views/unifi-switches.yaml
- **Subject:** `unifi_controller` `UniFiSwitch`
- **Date:** 2026-09-25
- **Status:** drafted; follows approval of the dashboards that embed it

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

Derived from the dashboard designs that embed this view (below).

## Vision

- One row per switch: PoE draw against budget, clients, load and satisfaction.
- Embedded by: `knowledge/designs/dashboards/unifi-switching-poe.md`.
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| Switch | name (object name) |  |
| Model | `Configuration\|model` |  |
| Firmware | `Configuration\|firmware` |  |
| Ports | `Configuration\|port_count` |  |
| Clients | `System\|num_sta` |  |
| Satisfaction % | `System\|satisfaction` | uncolored, lower is worse (#176) |
| CPU % | `System\|cpu_pct` |  |
| Mem % | `System\|mem_pct` |  |
| PoE W | `PoE\|poe_consumption` |  |
| PoE budget W | `PoE\|total_max_power` |  |
| PoE left W | `PoE\|poe_budget_remaining` | uncolored, lower is worse (#176) |
| PoE used % | `Super Metric\|UniFi Switch PoE Budget Used (%)` | planned super metric (knowledge/designs/supermetrics/unifi-switch-poe-budget-used-pct.md); orange >= 80, red >= 90 |
| Uptime | `System\|uptime` |  |

Summary row: Sum of Clients and of PoE W (SUM-only totals, #168).

## Notes

- Keys cite `content/sdk-adapters/unifi/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
- Switch names and models are illustrative; the lab has 10 switches.
