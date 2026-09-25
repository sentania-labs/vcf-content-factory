# [VCF Content Factory] UniFi Radios

- **Type:** view (bundled in the pak)
- **Slug:** unifi-radios
- **Authored YAML:** content/sdk-adapters/unifi/views/unifi-radios.yaml
- **Subject:** `unifi_controller` `UniFiRadio`
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

- One row per radio: band, channel, channel utilization, retries, satisfaction and clients.
- Embedded by: `knowledge/designs/dashboards/unifi-wireless-experience.md`, `knowledge/designs/dashboards/unifi-summary-access-point.md` (S7).
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| Radio | `Configuration\|radio_name` |  |
| Band | `Configuration\|radio_type` |  |
| Width | `Configuration\|ht` |  |
| Channel | `RF\|channel` |  |
| TX power dBm | `RF\|tx_power` |  |
| Ch. util % | `RF\|cu_total` | orange >= 50, red >= 75 |
| Retries % | `RF\|tx_retries_pct` | orange >= 10, red >= 20 |
| Satisfaction % | `RF\|satisfaction` | uncolored, lower is worse (#176) |
| Clients | `Clients\|user_num_sta` |  |

Summary row: Sum of Clients.

## Notes

- Keys cite `content/sdk-adapters/unifi/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
