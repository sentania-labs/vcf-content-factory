# [VCF Content Factory] UniFi Cameras

- **Type:** view (bundled in the pak)
- **Slug:** unifi-cameras
- **Authored YAML:** content/sdk-adapters/unifi/views/unifi-cameras.yaml
- **Subject:** `unifi_controller` `UniFiCamera`
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

- One row per Protect camera: connected, recording, model and uptime.
- Embedded by: `knowledge/designs/dashboards/unifi-network-overview.md`, `knowledge/designs/dashboards/unifi-summary-nvr.md` (S7).
- One list view reused by the general dashboards and the Summary pages, so a column fix lands everywhere.

## Columns

| Column | Key | Notes |
|---|---|---|
| Camera | name (object name) |  |
| Model | `Hardware\|model` |  |
| Type | `Hardware\|type` |  |
| State | `Status\|state` |  |
| Connected | `Status\|is_connected` |  |
| Recording | `Status\|is_recording` |  |
| Wireless | `Hardware\|is_wireless` |  |
| IP | `Network\|ip` |  |
| Firmware | `Hardware\|firmware` |  |
| Uptime | `Status\|uptime` |  |

Summary row: None.

## Notes

- Keys cite `content/sdk-adapters/unifi/describe.xml` exactly (RULE-002).
- #175: sort settings are dropped by the renderer, so no default sort is specified; the view opens in product default order.
- #176 applies to Scoreboards and MetricCharts; column thresholds here are proposed only for higher-is-worse keys, lower-is-worse columns are left uncolored for consistency.
- Camera names illustrative; the lab has 13 cameras. Uptime is the only monitored camera metric.
