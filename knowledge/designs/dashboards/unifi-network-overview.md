# [VCF Content Factory] UniFi Network Overview

- **Type:** dashboard (bundled in the pak)
- **Slug:** unifi-network-overview
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-network-overview.yaml
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Mock:** knowledge/designs/dashboards/unifi-network-overview.html
- **Index of all UniFi and Synology mocks:** knowledge/designs/dashboards/unifi-synology-index.html

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- **Why an admin wants it:** The first page an admin opens: is every UniFi device up, is the internet link good, and are the cameras recording, for one site at a time.
- Pick a site; see every gateway, switch, AP and camera colored by health, the alerts behind any red, the gateway's load and speed tests, both WAN uplinks with a latency trend, and every camera's connected and recording state.
- Audience: the admin or on-call person answering 'is the network OK'.
- Out of scope: per-port and per-radio detail (the Switching and Wireless dashboards).
- Recon 2026-09-25: no UniFi or Synology dashboards, views, super metrics, symptoms or alerts exist on the instance or in the repo.

## Revision (2026-09-25, after live recon)

Revised against the prod live-data recon (`knowledge/context/investigations/recon_log.md`, UniFi/Synology live-data recon): lifetime counters labelled as such (no rate super metric is expressible), broken Synology capacity keys blocked, never-populated keys (disk remaining life, LUN latency) removed, `Clients|num_disconnected` labelled unconfirmed. Coordinator defaults applied: adapter instances keep the native Summary page, UPS summary ships unverified.

## Keys

All keys from `content/sdk-adapters/unifi/describe.xml`; `badge|health` is a platform key. Every key below is cited exactly as `<ResourceGroup key>|<ResourceAttribute key>`.

## Wireframe

| # | Widget | Type | Grid (col, row, w, h) | Subject | Metrics / content |
|---|---|---|---|---|---|
| W1 | Site | ResourceList | 1, 1, 3, 9 | `unifi_controller` `UniFiSite` | Picker, name column only (`column_preset: name-only`). Auto-selects the first site. Drives W2, W3, W4, W5, W7, W8 |
| W2 | Device Health | Heatmap | 4, 1, 5, 9 | driven by W1; `UniFiGateway`, `UniFiSwitch`, `UniFiAccessPoint`, `UniFiCamera` (one tab each) | Color `badge\|health` (red 0, yellow 50, green 100), fixed size, no grouping (one site). Tabs: Gateways, Switches, Access Points, Cameras |
| W3 | Active Alerts | AlertList | 9, 1, 4, 9 | driven by W1, site and descendants | Active, Warning and up, all alert types |
| W4 | Gateway | View | 1, 10, 12, 4 | driven by W1, `UniFiGateway` | View `UniFi Gateways` |
| W5 | WAN Uplinks | View | 1, 14, 7, 6 | driven by W1, `UniFiWanInterface` | View `UniFi WAN Interfaces`. Row select drives W6 |
| W6 | WAN Latency and Availability: wan2 | MetricChart | 8, 14, 5, 6 | driven by W5 | `Health\|latency`, `Health\|availability`, 7 days |
| W7 | Cameras | View | 1, 20, 8, 7 | driven by W1, `UniFiCamera` | View `UniFi Cameras` |
| W8 | NVR Storage Used | MetricChart | 9, 20, 4, 7 | driven by W1, `relationship_mode: children`, child kind `UniFiNvr` | `Storage\|usage_pct`, 30 days, one line per NVR at the site |

Interactions: W1 selection drives W2, W3, W4, W5, W7, W8. W5 row selection drives W6. The picker auto-selects its first row, so a one-site controller shows data on open.

## Views (authored before the dashboard)

- `UniFi Gateways`: `knowledge/designs/views/unifi-gateways.md`
- `UniFi WAN Interfaces`: `knowledge/designs/views/unifi-wan-interfaces.md`
- `UniFi Cameras`: `knowledge/designs/views/unifi-cameras.md`

## Known constraints

- #177: there is no 'show everything, narrow on selection' mode, so the page is per site. With one site (the lab) the auto-selected first row makes that invisible.
- #175: embedded views open in product default order.
- #176: WAN availability and speed-test throughput are lower-is-worse and ship uncolored.
- W8 needs `relationship_mode: children` (loader-supported, first use in shipped content). Fallback: a View of NVRs.
- WAN `Traffic|*` columns are lifetime counters (live recon 2026-09-25); the view labels them lifetime totals, not throughput. No rate super metric is expressible (see `knowledge/designs/supermetrics/unifi-wan-rx-rate.md`).
