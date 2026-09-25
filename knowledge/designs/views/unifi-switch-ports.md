# [VCF Content Factory] UniFi Switch Ports

- **Type:** view (bundled in the pak)
- **Slug:** unifi-switch-ports
- **Authored YAML:** content/sdk-adapters/unifi/views/unifi-switch-ports.yaml
- **Subject:** `unifi_controller` `UniFiSwitchPort`
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

- One row per port: link, PoE, lifetime error counters and the LLDP neighbour, which for ESXi uplinks is the host and vmnic from the vmnic-to-port stitch.
- Embedded by: `knowledge/designs/dashboards/unifi-switching-poe.md`, `knowledge/designs/dashboards/unifi-summary-switch.md` (S7).
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| Port | `Status\|port_name` |  |
| Up | `Status\|up` |  |
| Speed | `Status\|speed` |  |
| Duplex | `Status\|duplex` |  |
| Media | `Status\|media` |  |
| Uplink | `Status\|is_uplink` |  |
| STP | `Status\|stp_state` |  |
| PoE | `PoE\|poe_enable` |  |
| PoE class | `PoE\|poe_class` |  |
| PoE W | `PoE\|poe_power` |  |
| Satisfaction % | `Status\|satisfaction` | uncolored, lower is worse (#176) |
| RX errors (lifetime) | `Traffic\|rx_errors` | lifetime count, not a rate (live recon 2026-09-25); uncolored |
| TX errors (lifetime) | `Traffic\|tx_errors` | lifetime count, not a rate; uncolored |
| LLDP neighbour | `LLDP\|lldp_system_name` |  |
| Neighbour port | `LLDP\|lldp_port_id` |  |

Summary row: Sum of PoE W only (a sum of lifetime error counts across ports is not meaningful).

## Notes

- Keys cite `content/sdk-adapters/unifi/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
- Neighbour names illustrative; the stitch writes the ESXi host name and vmnic into the LLDP properties (docs/overview.md).
