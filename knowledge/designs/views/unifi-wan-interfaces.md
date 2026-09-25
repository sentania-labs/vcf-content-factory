# [VCF Content Factory] UniFi WAN Interfaces

- **Type:** view (bundled in the pak)
- **Slug:** unifi-wan-interfaces
- **Authored YAML:** content/sdk-adapters/unifi/views/unifi-wan-interfaces.yaml
- **Subject:** `unifi_controller` `UniFiWanInterface`
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

- One row per WAN uplink: addressing, latency, availability and traffic counters.
- Embedded by: `knowledge/designs/dashboards/unifi-network-overview.md`, `knowledge/designs/dashboards/unifi-summary-gateway.md` (S7).
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| WAN | name (object name) |  |
| Type | `Configuration\|type` |  |
| IP | `Configuration\|ip` |  |
| Gateway IP | `Configuration\|gateway_ip` |  |
| DNS | `Configuration\|dns` |  |
| Latency ms | `Health\|latency` | orange >= 50, red >= 100 |
| Availability % | `Health\|availability` | uncolored, lower is worse (#176) |
| RX total (lifetime) | `Traffic\|rx_bytes` | lifetime counter since device counter reset, not throughput (live recon 2026-09-25); uncolored |
| TX total (lifetime) | `Traffic\|tx_bytes` | lifetime counter, not throughput; uncolored |

Summary row: None.

## Notes

- Keys cite `content/sdk-adapters/unifi/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
