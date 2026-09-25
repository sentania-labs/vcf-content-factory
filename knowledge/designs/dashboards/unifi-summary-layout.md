# [VCF Content Factory] UniFi Summary dashboards (shared layout)

- **Type:** dashboard layout (one design, instantiated as one summary dashboard per resource kind, bundled in the pak)
- **Slug:** unifi-summary-layout
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-<kind>.yaml (one per kind, see the per-kind intent files)
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html
- **Index of all UniFi and Synology mocks:** knowledge/designs/dashboards/unifi-synology-index.html

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Every UniFi object's Summary tab shows one familiar page: who it is, whether it is healthy, its alerts, two trends that matter for that kind, what hangs off it, and where it sits in the tree.
- One layout, so an admin learns it once; the keys in each slot are chosen per kind so the page says something real about the object, which was Scott's condition for a shared layout.
- Audience: the admin who clicked through to an object from a general dashboard, an alert, or the inventory tree.
- Out of scope: new super metrics, symptoms or alerts (listed as open questions), and any change to the adapter.
- Recon 2026-09-25: no UniFi or Synology dashboards, views, super metrics, symptoms or alerts exist anywhere (instance or repo). Author is required.

## Revision (2026-09-25, after live recon)

Revised against the prod live-data recon (`knowledge/context/investigations/recon_log.md`, UniFi/Synology live-data recon): lifetime counters labelled as such (no rate super metric is expressible), broken Synology capacity keys blocked, never-populated keys (disk remaining life, LUN latency) removed, `Clients|num_disconnected` labelled unconfirmed. Coordinator defaults applied: adapter instances keep the native Summary page, UPS summary ships unverified.

## Binding

Each kind gets its own dashboard YAML with `summary_for: ["unifi_controller:<ResourceKind>"]`; the SDK builder writes one `content/dashboards/dashboards.properties` line per dashboard directory (`knowledge/context/api-surface/summary_dashboard_pak_binding.md`). `summary_for` can list several kinds on one dashboard, but every widget here binds kind-specific keys, so a shared *layout* means 11 dashboards built from this one design. Every widget is `self_provider: false` with no pinned resource (loader rule for `summary_for`).

**Adapter instance excluded.** `unifi_controller:unifi_controller` keeps the product's native Summary page (coordinator default 2026-09-25, Scott can override). Binding a dashboard there would replace the native collection-status page every adapter instance shares, and the collection-health keys it could show (`Instance Attributes|*`) are already on that page. So this layout covers 11 kinds, not 12.

Names: `[VCF Content Factory] UniFi <Kind> Summary`. Suggested folder (`namePath`): `VCF Content Factory/UniFi/Summary`.

## Shared slot grid (12 columns)

| Slot | Widget | Type | Grid (col, row, w, h) | What fills it |
|---|---|---|---|---|
| S1 | Identity | PropertyList (TextDisplay on keys-less kinds) | 1, 1, 4, 8 | The object's key properties, most decision-relevant first. Kinds with no properties get a TextDisplay that says what the object is. |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 (4, 8 when S3 is dropped) | `badge|health`, `System Attributes|alert_count_critical`, `System Attributes|alert_count_immediate`, `System Attributes|alert_count_warning`. Identical on every kind; bound per kind. |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | Two to four current values that answer 'is this object OK'. Dropped on kinds with no metrics. |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active alerts, criticality Warning and up. Scope: own only on leaf kinds, own and descendants on kinds with children. |
| S5 | Trend A | MetricChart | 1, 9, 6, 7 (12 wide when S6 is dropped) | The primary trend for the kind. On container kinds, a per-child chart (`relationship_mode: children`). |
| S6 | Trend B | MetricChart | 7, 9, 6, 7 | The secondary trend. Dropped when the kind has no second monitored series. |
| S7 | Related Objects / Details | View, PropertyList, MetricChart or Heatmap | 1, 16, 8, 9 (row moves up to 9 when S5 and S6 are both dropped) | Kinds with children: a list View of the children (two half-width Views when there are two primary child kinds). Leaf kinds: the remaining properties as a PropertyList, or a third chart if no properties are left. Containers whose children have no metrics: a device Heatmap. Dropped when nothing is left. |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 (12 wide when S7 is dropped) | Parents and children of the page object, including foreign parents from the cross-adapter stitches (ESXi host on a switch port, VMware datastore on a LUN or NFS export). |

Interactions: none. Every widget receives the Summary page object.

## Per-kind fill

Keys are `<ResourceGroup key>|<ResourceAttribute key>` from `content/sdk-adapters/unifi/describe.xml`, exactly as the adapter emits them. Grid is (col, row, w, h).

### UniFi World (`unifi_controller:UniFiWorld`)

Intent file: `knowledge/designs/dashboards/unifi-summary-world.md`. Layout: container: S1 is a TextDisplay (the World carries no keys), S3 dropped, S5 and S6 dropped (its children, Sites, carry no metrics), S7 is a device-health Heatmap.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | About this World | TextDisplay | 1, 1, 4, 8 | Static text: what this object is and where to go instead (no keys exist on this kind) |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 8 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S7 | Device Health | Heatmap | 1, 9, 8, 9 | tab Gateways: `UniFiGateway` colored by `badge\|health` (red 0, yellow 50, green 100); tab Switches: `UniFiSwitch` colored by `badge\|health` (red 0, yellow 50, green 100); tab Access Points: `UniFiAccessPoint` colored by `badge\|health` (red 0, yellow 50, green 100); tab Cameras: `UniFiCamera` colored by `badge\|health` (red 0, yellow 50, green 100); group by `UniFiSite`; fixed size |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 9, 4, 9 | depth `"0,2"` (ancestors, descendants) |

Key notes: Only platform keys (badge|health, System Attributes|*). The Synology World shows NO_DATA_RECEIVING and grey health in the v1 baseline for the same reason; expect the same here.

### UniFi Site (`unifi_controller:UniFiSite`)

Intent file: `knowledge/designs/dashboards/unifi-summary-site.md`. Layout: container: S3 dropped (a Site has no metrics), S5 and S6 are per-child MetricCharts (relationship_mode: children), S7 is a device Heatmap.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Site | PropertyList | 1, 1, 4, 8 | `Configuration\|description`, `Configuration\|version`, `Configuration\|timezone`, `Configuration\|device_count` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 8 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S5 | Clients per Access Point | MetricChart | 1, 9, 6, 7 | `relationship_mode: children`, child kind `UniFiAccessPoint`, `System\|num_sta`, 7 d |
| S6 | PoE Draw per Switch | MetricChart | 7, 9, 6, 7 | `relationship_mode: children`, child kind `UniFiSwitch`, `PoE\|poe_consumption`, 7 d |
| S7 | Devices at this Site | Heatmap | 1, 16, 8, 9 | tab Health: `UniFiGateway, UniFiSwitch, UniFiAccessPoint, UniFiNvr (one tab each)` colored by `badge\|health` (red 0, yellow 50, green 100); tab AP satisfaction: `UniFiAccessPoint` colored by `System\|satisfaction` (red 0, yellow 80, green 100); no grouping; fixed size |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"1,1"` (ancestors, descendants) |

Key notes: Configuration|device_count is a string property in describe.xml, so it displays but cannot be charted.

### UniFi Gateway (`unifi_controller:UniFiGateway`)

Intent file: `knowledge/designs/dashboards/unifi-summary-gateway.md`. Layout: standard.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Gateway | PropertyList | 1, 1, 4, 8 | `Configuration\|name`, `Configuration\|model`, `Configuration\|firmware`, `Configuration\|serial`, `Configuration\|ip`, `Configuration\|mac_address`, `System\|uptime` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `System\|cpu_pct`, `System\|mem_pct`, `Temperature\|temp_cpu`, `System\|num_sta` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S5 | Load and Temperature | MetricChart | 1, 9, 6, 7 | `System\|cpu_pct`, `System\|mem_pct`, `Temperature\|temp_cpu`, `Temperature\|temp_local`, 7 d |
| S6 | Speed Test | MetricChart | 7, 9, 6, 7 | `Speedtest\|xput_down`, `Speedtest\|xput_up`, `Speedtest\|speedtest_latency`, 30 d |
| S7 | WAN Interfaces | View | 1, 16, 8, 9 | View `UniFi WAN Interfaces` (subject `UniFiWanInterface`), design `knowledge/designs/views/unifi-wan-interfaces.md` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,1"` (ancestors, descendants) |

Key notes: Temperature|temp_phy is defaultMonitored=false; left out.

### UniFi WAN Interface (`unifi_controller:UniFiWanInterface`)

Intent file: `knowledge/designs/dashboards/unifi-summary-wan-interface.md`. Layout: leaf: S7 dropped (no keys left; Health|speed is defaultMonitored=false), S8 widens to 12.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | WAN Uplink | PropertyList | 1, 1, 4, 8 | `Configuration\|type`, `Configuration\|ip`, `Configuration\|netmask`, `Configuration\|gateway_ip`, `Configuration\|dns` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `Health\|latency`, `Health\|availability` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own only |
| S5 | Latency and Availability | MetricChart | 1, 9, 6, 7 | `Health\|latency`, `Health\|availability`, 7 d |
| S6 | Traffic: Cumulative since device counter reset (not throughput) | MetricChart | 7, 9, 6, 7 | `Traffic\|rx_bytes`, `Traffic\|tx_bytes`, 7 d |
| S8 | Relationships | ResourceRelationshipAdvanced | 1, 16, 12, 9 | depth `"3,0"` (ancestors, descendants) |

Key notes: Live recon 2026-09-25 (prod): Traffic|rx_bytes and Traffic|tx_bytes are lifetime counters, strictly non-decreasing over 6 h, despite describe.xml unit bytes/s (a label bug). A rate super metric is not expressible in the DSL (no previous-sample function), so S6 is a cumulative sparkline labelled as such: the slope is the rate, the value is not current throughput. Real fix: adapter emits the UniFi -r rate fields (see supermetric intent unifi-wan-rx-rate).

### UniFi Switch (`unifi_controller:UniFiSwitch`)

Intent file: `knowledge/designs/dashboards/unifi-summary-switch.md`. Layout: standard.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Switch | PropertyList | 1, 1, 4, 8 | `Configuration\|name`, `Configuration\|model`, `Configuration\|firmware`, `Configuration\|serial`, `Configuration\|ip`, `Configuration\|mac_address`, `Configuration\|port_count`, `Configuration\|poe_capable`, `Configuration\|has_fan` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `Super Metric\|UniFi Switch PoE Budget Used (%)`, `PoE\|poe_consumption`, `PoE\|total_max_power`, `System\|num_sta` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S5 | PoE Draw vs Budget | MetricChart | 1, 9, 6, 7 | `PoE\|poe_consumption`, `PoE\|total_max_power`, 7 d |
| S6 | Load and Satisfaction | MetricChart | 7, 9, 6, 7 | `System\|cpu_pct`, `System\|mem_pct`, `System\|satisfaction`, 7 d |
| S7 | Switch Ports | View | 1, 16, 8, 9 | View `UniFi Switch Ports` (subject `UniFiSwitchPort`), design `knowledge/designs/views/unifi-switch-ports.md` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,1"` (ancestors, descendants) |

Key notes: PoE budget used % is a planned super metric (knowledge/designs/supermetrics/unifi-switch-poe-budget-used-pct.md, purple key), colored orange >= 80, red >= 90. Watt tiles stay uncolored: absolute watts mean different things on a 52 W and a 400 W switch. PoE|poe_budget_remaining moved off the tiles (lower-is-worse, #176; the % covers it).

### UniFi Switch Port (`unifi_controller:UniFiSwitchPort`)

Intent file: `knowledge/designs/dashboards/unifi-summary-switch-port.md`. Layout: leaf: S7 is a PropertyList (PoE config and LLDP neighbour).

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Port | PropertyList | 1, 1, 4, 8 | `Status\|port_name`, `Status\|up`, `Status\|speed`, `Status\|duplex`, `Status\|media`, `Status\|is_uplink`, `Status\|stp_state` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `PoE\|poe_power`, `Status\|satisfaction`, `Traffic\|rx_errors`, `Traffic\|tx_errors` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own only |
| S5 | Traffic: Cumulative since device counter reset (not throughput) | MetricChart | 1, 9, 6, 7 | `Traffic\|rx_bytes`, `Traffic\|tx_bytes`, 7 d |
| S6 | PoE Draw | MetricChart | 7, 9, 6, 7 | `PoE\|poe_power`, 7 d |
| S7 | PoE and Neighbour | PropertyList | 1, 16, 8, 9 | `PoE\|poe_enable`, `PoE\|poe_class`, `PoE\|poe_mode`, `LLDP\|lldp_system_name`, `LLDP\|lldp_port_id` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,0"` (ancestors, descendants) |

Key notes: Live recon 2026-09-25 (prod): Traffic|rx_bytes/tx_bytes are strictly non-decreasing lifetime counters and Traffic|rx_errors/tx_errors held flat at 1 and 2 for 6 h (lifetime counts). A rate or error-rate super metric is not expressible in the DSL, so: S5 is a cumulative sparkline labelled as such; the error tiles are labelled lifetime and uncolored; errors are off the charts (a flat lifetime line reads as a current rate). Rate SM intents record the gap (unifi-switch-port-*-rate). PoE|poe_voltage and PoE|poe_current are defaultMonitored=false; left out. Status|mac_table_count also defaultMonitored=false.

### UniFi Access Point (`unifi_controller:UniFiAccessPoint`)

Intent file: `knowledge/designs/dashboards/unifi-summary-access-point.md`. Layout: standard.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Access Point | PropertyList | 1, 1, 4, 8 | `Configuration\|name`, `Configuration\|model`, `Configuration\|firmware`, `Configuration\|serial`, `Configuration\|ip`, `Configuration\|mac_address`, `System\|uptime` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `System\|num_sta`, `System\|satisfaction`, `System\|cpu_pct`, `System\|mem_pct` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S5 | Clients and Satisfaction | MetricChart | 1, 9, 6, 7 | `System\|num_sta`, `System\|satisfaction`, 7 d |
| S6 | Load | MetricChart | 7, 9, 6, 7 | `System\|cpu_pct`, `System\|mem_pct`, 7 d |
| S7 | Radios | View | 1, 16, 8, 9 | View `UniFi Radios` (subject `UniFiRadio`), design `knowledge/designs/views/unifi-radios.md` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,1"` (ancestors, descendants) |

Key notes: Satisfaction is lower-is-worse and ships uncolored (#176).

### UniFi Radio (`unifi_controller:UniFiRadio`)

Intent file: `knowledge/designs/dashboards/unifi-summary-radio.md`. Layout: leaf: S7 is a third MetricChart (channel and power history), since no properties are left over.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Radio | PropertyList | 1, 1, 4, 8 | `Configuration\|radio_name`, `Configuration\|radio_type`, `Configuration\|ht`, `Configuration\|min_txpower`, `Configuration\|max_txpower`, `RF\|channel`, `RF\|tx_power` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `Clients\|user_num_sta`, `RF\|cu_total`, `RF\|tx_retries_pct`, `RF\|satisfaction` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own only |
| S5 | Utilization, Retries, Satisfaction | MetricChart | 1, 9, 6, 7 | `RF\|cu_total`, `RF\|tx_retries_pct`, `RF\|satisfaction`, 7 d |
| S6 | Clients; Traffic Cumulative since device counter reset | MetricChart | 7, 9, 6, 7 | `Clients\|user_num_sta`, `Traffic\|tx_bytes`, `Traffic\|rx_bytes`, 7 d |
| S7 | Channel and Power History | MetricChart | 1, 16, 8, 9 | `RF\|channel`, `RF\|tx_power`, 30 d |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"3,0"` (ancestors, descendants) |

Key notes: Live recon 2026-09-25 (prod): Traffic|tx_bytes/rx_bytes are lifetime counters (non-decreasing over 6 h). Labelled cumulative in S6; a rate SM is not expressible (unifi-radio-*-rate intents record the gap).

### UniFi Wireless Summary (`unifi_controller:UniFiWirelessAggregate`)

Intent file: `knowledge/designs/dashboards/unifi-summary-wireless-summary.md`. Layout: leaf: S1 is a TextDisplay (this kind has no properties, and listing its metrics would repeat S3); S7 is a MetricChart of APs reporting.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | About this Summary | TextDisplay | 1, 1, 4, 8 | Static text: what this object is and where to go instead (no keys exist on this kind) |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `Clients\|num_user`, `Clients\|num_guest`, `Clients\|num_iot`, `Performance\|num_ap` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own only |
| S5 | Clients by Type | MetricChart | 1, 9, 6, 7 | `Clients\|num_user`, `Clients\|num_guest`, `Clients\|num_iot`, `Clients\|num_disconnected`, 7 d |
| S6 | Wireless Throughput | MetricChart | 7, 9, 6, 7 | `Performance\|tx_bytes_r`, `Performance\|rx_bytes_r`, 7 d |
| S7 | APs Reporting | MetricChart | 1, 16, 8, 9 | `Performance\|num_ap`, 30 d |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,0"` (ancestors, descendants) |

Key notes: Performance|tx_bytes_r and rx_bytes_r are true rates (the UniFi -r fields), the only rate-typed traffic keys in the pack. Clients|num_disconnected exists only on this kind (live recon 2026-09-25); describe.xml groups it with client counts, so it is labelled Disconnected clients (unconfirmed) until a disconnect is observed.

### UniFi NVR (`unifi_controller:UniFiNvr`)

Intent file: `knowledge/designs/dashboards/unifi-summary-nvr.md`. Layout: standard.

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | NVR | PropertyList | 1, 1, 4, 8 | `Configuration\|name`, `Configuration\|model`, `Configuration\|firmware`, `Configuration\|host_type`, `Configuration\|recording_retention_mode`, `Configuration\|camera_count`, `System\|uptime` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `Storage\|usage_pct`, `Storage\|used_bytes`, `Storage\|total_bytes` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own and descendants |
| S5 | Storage Used | MetricChart | 1, 9, 6, 7 | `Storage\|usage_pct`, `Storage\|used_bytes`, 30 d |
| S6 | Uptime (drops mark restarts) | MetricChart | 7, 9, 6, 7 | `System\|uptime`, 30 d |
| S7 | Cameras | View | 1, 16, 8, 9 | View `UniFi Cameras` (subject `UniFiCamera`), design `knowledge/designs/views/unifi-cameras.md` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"2,1"` (ancestors, descendants) |

Key notes: Protect NVRs run near-full by design (automatic retention overwrites oldest footage), so Storage used % is colored orange >= 90 and red >= 98, not the usual 80/90.

### UniFi Camera (`unifi_controller:UniFiCamera`)

Intent file: `knowledge/designs/dashboards/unifi-summary-camera.md`. Layout: leaf: S3 carries one tile, S6 dropped (Status|last_motion is defaultMonitored=false) so S5 widens to 12, S7 is a PropertyList (network and radio).

| Slot | Widget | Type | Grid | Keys / content |
|---|---|---|---|---|
| S1 | Camera | PropertyList | 1, 1, 4, 8 | `Status\|state`, `Status\|is_connected`, `Status\|is_recording`, `Hardware\|model`, `Hardware\|type`, `Hardware\|firmware` |
| S2 | Health and Alerts | Scoreboard | 5, 1, 4, 4 | `badge\|health`, `System Attributes\|alert_count_critical`, `System Attributes\|alert_count_immediate`, `System Attributes\|alert_count_warning` |
| S3 | Key Numbers | Scoreboard | 5, 5, 4, 4 | `Status\|uptime` |
| S4 | Active Alerts | AlertList | 9, 1, 4, 8 | Active, Warning and up, own only |
| S5 | Uptime (drops mark restarts) | MetricChart | 1, 9, 12, 7 | `Status\|uptime`, 30 d |
| S7 | Network | PropertyList | 1, 16, 8, 9 | `Network\|ip`, `Network\|mac_address`, `Hardware\|is_wireless`, `Hardware\|phy_rate` |
| S8 | Relationships | ResourceRelationshipAdvanced | 9, 16, 4, 9 | depth `"3,0"` (ancestors, descendants) |

Key notes: Camera is property-heavy: Status|uptime is its only default-monitored metric.

## Views this layout needs (authored before the dashboards)

- `UniFi WAN Interfaces`: `knowledge/designs/views/unifi-wan-interfaces.md`
- `UniFi Switch Ports`: `knowledge/designs/views/unifi-switch-ports.md`
- `UniFi Radios`: `knowledge/designs/views/unifi-radios.md`
- `UniFi Cameras`: `knowledge/designs/views/unifi-cameras.md`

## Known constraints

- First use of `summary_for` in this repo (recon 2026-09-25). The loader and SDK builder support it, but the install-time bind has only been exercised by the HostSystem smoke dashboard on a disposable build. Verify on qa with `getSummaryTabId` per kind before release.
- The installer binds a SUMMARY-template *copy* of each dashboard; editing the visible dashboard later does not change the Summary tab, reinstalling with force creates another template copy, and uninstall leaves the binding in place (clear with Manage Summary Dashboards, Use Default). Same doc as above.
- Each summary dashboard also appears in the Dashboards list. `disabled: true` hides it there without affecting the Summary tab (binding doc). Proposed: set it, so the list shows only the general dashboards.
- #177 does not apply here (no pickers). #175 applies to every S7 View: embedded views open in product default order; sort by clicking the header.
- #176: lower-is-worse keys (satisfaction, availability, remaining PoE, free bytes, remaining life, charge, runtime, hit rates) ship uncolored on Scoreboards and MetricCharts. Heatmaps are not affected: their color scale is set per tab, so red-at-low works there.
- `relationship_mode: children` on MetricChart is supported by the loader but not used by any shipped content yet; first use is here (Site, World, Storage Pool pages).
- ResourceRelationshipAdvanced (S8) is supported by the loader and renderer and ships in the vcommunity dashboards; it is not in the nine-widget list the brief named, so it is called out here. Fallback if rejected: drop S8 and widen S7 to 12.
- #173 (who authors content under `content/sdk-adapters/<name>/dashboards/`) is open and must be resolved, or carved out for this task as with compliance-v3, before dashboard-author spawns.

## Open questions for Scott

1. **Resolved by live recon 2026-09-25: traffic and error keys are lifetime counters.** A rate super metric is not expressible in the DSL (no previous-sample or time-shift function; `.claude/skills/vcfops-supermetric-dsl/SKILL.md`, `reference/docs/vcf9/supermetrics.md`), so every chart of them is a cumulative sparkline labelled 'since device counter reset' and every error value is labelled lifetime and uncolored. The eight rate intents under `knowledge/designs/supermetrics/unifi-*-rate.md` record the gap. **Decision for Scott:** file an adapter issue to emit the UniFi `-r` rate fields (switch ports, radios, WAN), which would replace every cumulative sparkline with a real throughput chart?
2. **Resolved: `Clients|num_disconnected`** exists only on Wireless Summary and is schema-grouped with client counts; labelled 'Disconnected clients (unconfirmed)' until a disconnect is observed live.
3. **Default applied: adapter instance keeps its native Summary page** (see Binding). Override if you want the collection-health page.
4. **PoE budget used %** is now a planned super metric (`knowledge/designs/supermetrics/unifi-switch-poe-budget-used-pct.md`), used on the Switch Summary tile, the Switches view and the Switching dashboard. Approve, or drop it and the tile reverts to watts.
5. **Alerts.** Health and alert slots stay green until the pack has symptoms and alerts (none exist). Candidate follow-on: WAN availability, AP satisfaction, PoE budget used % high, camera disconnected. File as an issue?
