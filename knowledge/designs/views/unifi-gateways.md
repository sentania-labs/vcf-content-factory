# [VCF Content Factory] UniFi Gateways

- **Type:** view (bundled in the pak)
- **Slug:** unifi-gateways
- **Authored YAML:** content/sdk-adapters/unifi/views/unifi-gateways.yaml
- **Subject:** `unifi_controller` `UniFiGateway`
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

- One row per gateway: load, temperature, clients and the last speed test.
- Embedded by: `knowledge/designs/dashboards/unifi-network-overview.md`.
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| Gateway | name (object name) |  |
| Model | `Configuration\|model` |  |
| Firmware | `Configuration\|firmware` |  |
| IP | `Configuration\|ip` |  |
| CPU % | `System\|cpu_pct` | red >= 90, orange >= 80 |
| Mem % | `System\|mem_pct` | red >= 90, orange >= 80 |
| CPU temp C | `Temperature\|temp_cpu` | orange >= 80, red >= 90 |
| Clients | `System\|num_sta` |  |
| Down Mbps | `Speedtest\|xput_down` | uncolored, lower is worse (#176) |
| Up Mbps | `Speedtest\|xput_up` | uncolored, lower is worse (#176) |
| Speedtest ms | `Speedtest\|speedtest_latency` |  |
| Uptime | `System\|uptime` | seconds; display as duration if the view unit supports it |

Summary row: None (one gateway per site is typical).

## Notes

- Keys cite `content/sdk-adapters/unifi/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
