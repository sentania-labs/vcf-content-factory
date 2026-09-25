# [VCF Content Factory] UniFi Switching and PoE

- **Type:** dashboard (bundled in the pak)
- **Slug:** unifi-switching-poe
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-switching-poe.yaml
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Mock:** knowledge/designs/dashboards/unifi-switching-poe.html
- **Index of all UniFi and Synology mocks:** knowledge/designs/dashboards/unifi-synology-index.html

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- **Why an admin wants it:** Answers 'can I plug in another PoE device, which port has errors, and which port is my ESXi host on': PoE draw against budget per switch, then every port with link, PoE, errors and the LLDP neighbour.
- Pick a site; compare PoE draw per switch over the week, pick a switch to see its PoE budget trend and every port, then a port's traffic and PoE history.
- The LLDP neighbour columns carry the ESXi host and vmnic from the pack's vmnic-to-port stitch, so this is also the 'where is this host cabled' page.
- Audience: the admin adding devices, chasing a flapping or erroring port, or tracing an ESXi uplink.
- Recon 2026-09-25: no UniFi or Synology dashboards, views, super metrics, symptoms or alerts exist on the instance or in the repo.

## Revision (2026-09-25, after live recon)

Revised against the prod live-data recon (`knowledge/context/investigations/recon_log.md`, UniFi/Synology live-data recon): lifetime counters labelled as such (no rate super metric is expressible), broken Synology capacity keys blocked, never-populated keys (disk remaining life, LUN latency) removed, `Clients|num_disconnected` labelled unconfirmed. Coordinator defaults applied: adapter instances keep the native Summary page, UPS summary ships unverified.

## Keys

All keys from `content/sdk-adapters/unifi/describe.xml`. LLDP stitch behavior from `content/sdk-adapters/unifi/docs/overview.md`. Every key below is cited exactly as `<ResourceGroup key>|<ResourceAttribute key>`.

## Wireframe

| # | Widget | Type | Grid (col, row, w, h) | Subject | Metrics / content |
|---|---|---|---|---|---|
| W1 | Site | ResourceList | 1, 1, 3, 8 | `unifi_controller` `UniFiSite` | Picker, name only. Drives W2, W3 |
| W2 | PoE Budget Used per Switch | MetricChart | 4, 1, 9, 8 | driven by W1, `relationship_mode: children`, child kind `UniFiSwitch` | Planned super metric `[VCF Content Factory] UniFi Switch PoE Budget Used (%)` (`knowledge/designs/supermetrics/unifi-switch-poe-budget-used-pct.md`), 7 days, one line per switch. Fallback if the SM is declined: `PoE\|poe_consumption` in watts |
| W3 | Switches | View | 1, 9, 12, 6 | driven by W1, `UniFiSwitch` | View `UniFi Switches`. Row select drives W4, W5, W6 |
| W4 | Ports: Core 24 PoE | View | 1, 15, 12, 8 | driven by W3, `UniFiSwitchPort` | View `UniFi Switch Ports`. Row select drives W7 |
| W5 | Port PoE Draw: Core 24 PoE | Heatmap | 1, 23, 6, 7 | driven by W3, `UniFiSwitchPort` | Fixed size, no grouping. Tabs: PoE draw `PoE\|poe_power` (green 0, yellow 15, red 25 W); RX errors since counter reset `Traffic\|rx_errors` (lifetime count, not a rate; green 0, orange 1, red 1000: marks ports that have ever errored) |
| W6 | PoE Budget: Core 24 PoE | MetricChart | 7, 23, 6, 7 | driven by W3 | `PoE\|poe_consumption`, `PoE\|total_max_power`, planned SM PoE Budget Used (%), 7 days |
| W7 | Port: Cumulative Traffic since Counter Reset, and PoE: Port 3 | MetricChart | 1, 30, 12, 6 | driven by W4 | `Traffic\|rx_bytes`, `Traffic\|tx_bytes` (lifetime counters, labelled cumulative since device counter reset, not throughput), `PoE\|poe_power`, 7 days |

Interactions: W1 drives W2, W3. W3 row selection drives W4, W5, W6. W4 row selection drives W7. W3 and W4 auto-select their first row.

## Views (authored before the dashboard)

- `UniFi Switches`: `knowledge/designs/views/unifi-switches.md`
- `UniFi Switch Ports`: `knowledge/designs/views/unifi-switch-ports.md`

## Known constraints

- #177: per site.
- #175: port lists open in default order (usually port order, which is what an admin wants here).
- #176: PoE remaining and satisfaction are uncolored; the W5 heatmap carries PoE color.
- Traffic and error keys are lifetime counters (live recon 2026-09-25). A rate or error-rate super metric is not expressible in the DSL (no previous-sample function), so traffic is charted only as a labelled cumulative sparkline, error columns are labelled lifetime and uncolored, and the W5 errors tab says lifetime. Rates need the adapter to emit the UniFi `-r` fields (question for Scott).
- W2 and W6 use a planned super metric; it must be authored and enabled in policy before the dashboard.
- W2 needs `relationship_mode: children` (first use in shipped content).
