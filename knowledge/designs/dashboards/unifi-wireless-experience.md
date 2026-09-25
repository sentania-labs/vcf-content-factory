# [VCF Content Factory] UniFi Wireless Experience

- **Type:** dashboard (bundled in the pak)
- **Slug:** unifi-wireless-experience
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-wireless-experience.yaml
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Mock:** knowledge/designs/dashboards/unifi-wireless-experience.html
- **Index of all UniFi and Synology mocks:** knowledge/designs/dashboards/unifi-synology-index.html

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- **Why an admin wants it:** Answers 'why is the Wi-Fi bad': which APs carry the clients, which radios are congested or retrying, and how that changed over the week.
- Pick a site; see site-wide client counts and wireless throughput, clients per AP, a radio congestion heatmap, then drill from an AP to its radios and a radio's trend.
- Audience: the admin chasing a Wi-Fi complaint or planning channel changes.
- Channel utilization and retries are the core signals; satisfaction is shown but uncolored (#176).
- Recon 2026-09-25: no UniFi or Synology dashboards, views, super metrics, symptoms or alerts exist on the instance or in the repo.

## Revision (2026-09-25, after live recon)

Revised against the prod live-data recon (`knowledge/context/investigations/recon_log.md`, UniFi/Synology live-data recon): lifetime counters labelled as such (no rate super metric is expressible), broken Synology capacity keys blocked, never-populated keys (disk remaining life, LUN latency) removed, `Clients|num_disconnected` labelled unconfirmed. Coordinator defaults applied: adapter instances keep the native Summary page, UPS summary ships unverified.

## Keys

All keys from `content/sdk-adapters/unifi/describe.xml`. Every key below is cited exactly as `<ResourceGroup key>|<ResourceAttribute key>`.

## Wireframe

| # | Widget | Type | Grid (col, row, w, h) | Subject | Metrics / content |
|---|---|---|---|---|---|
| W1 | Site | ResourceList | 1, 1, 3, 8 | `unifi_controller` `UniFiSite` | Picker, name only. Drives W2, W3, W4, W5 |
| W2 | Site Wireless Clients | MetricChart | 4, 1, 5, 8 | driven by W1, `relationship_mode: children`, child kind `UniFiWirelessAggregate` | `Clients\|num_user`, `Clients\|num_guest`, `Clients\|num_iot`, `Clients\|num_disconnected` (labelled Disconnected clients (unconfirmed)), `Performance\|tx_bytes_r`, `Performance\|rx_bytes_r`, 7 days |
| W3 | Clients per AP | MetricChart | 9, 1, 4, 8 | driven by W1, `relationship_mode: children`, child kind `UniFiAccessPoint` | `System\|num_sta`, 7 days, one line per AP |
| W4 | Radio Congestion | Heatmap | 1, 9, 12, 6 | driven by W1, `UniFiRadio` | Group by `UniFiAccessPoint`, fixed size. Tabs: Channel utilization `RF\|cu_total` (green 0, yellow 50, red 80); Retries `RF\|tx_retries_pct` (green 0, yellow 10, red 20); Satisfaction `RF\|satisfaction` (red 0, yellow 80, green 100) |
| W5 | Access Points | View | 1, 15, 7, 7 | driven by W1, `UniFiAccessPoint` | View `UniFi Access Points`. Row select drives W6 |
| W6 | Radios: Garage | View | 8, 15, 5, 7 | driven by W5, `UniFiRadio` | View `UniFi Radios`. Row select drives W7 |
| W7 | Radio Trend: Garage wifi0 | MetricChart | 1, 22, 12, 6 | driven by W6 | `RF\|cu_total`, `RF\|tx_retries_pct`, `RF\|satisfaction`, `Clients\|user_num_sta`, `RF\|channel`, 7 days |

Interactions: W1 drives W2, W3, W4, W5. W5 row selection drives W6. W6 row selection drives W7. W5 and W6 auto-select their first row.

## Views (authored before the dashboard)

- `UniFi Access Points`: `knowledge/designs/views/unifi-access-points.md`
- `UniFi Radios`: `knowledge/designs/views/unifi-radios.md`

## Known constraints

- #177: per site; same note as the Network Overview.
- #175: views open in default order; to find the busiest AP, click the Clients header.
- #176: satisfaction is uncolored in the views and the chart; the Heatmap Satisfaction tab carries the color.
- W2 and W3 need `relationship_mode: children` (first use in shipped content). Fallback for W2: a View of `UniFiWirelessAggregate`.
- `Clients|num_disconnected` exists only on Wireless Summary and is labelled Disconnected clients (unconfirmed): describe.xml groups it with client counts, but no disconnect has been observed live (recon 2026-09-25).
- Radio traffic keys are lifetime counters and are deliberately not on this dashboard; `Performance|tx_bytes_r` / `rx_bytes_r` are real rates.
