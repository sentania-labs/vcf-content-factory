# Design Artifact: Synology DSM Management Pack v1

## Original Request

Build a management pack capability for the VCF Content Factory, using the
Synology DS1520+ NAS MP as the learning project. Scott has an existing
bare-bones MP (`sentania/Aria-Operations-DSM-Management-Pack`, build 8) with
4 object types, 9 requests, 1 relationship, and session auth working. Evolve
it into a full-featured MP while building the factory tooling.

## Interview Answers

| Question | Answer |
|---|---|
| Monitoring scope | Storage + compute + UPS + Docker |
| iSCSI LUNs | First-class objects (for ESXi correlation) |
| Network interfaces | Metrics on Diskstation (not separate objects) |
| Disk parent | Dual relationship: child of Diskstation AND Storage Pool |
| Events | Warn + critical (full set) |
| Bundled content | Basic dashboard in .pak + rich factory dashboard separately |

## Object Model

```
Synology Diskstation (world object, keyed by serial)
|
+-- Storage Pool          1:N   (keyed by pool_id)
|   +-- Volume            1:N   (keyed by volume_path)
|   |   +-- iSCSI LUN    1:N   (keyed by lun_uuid)
|   +-- Disk              1:N   (keyed by disk_id) <-- also child of Diskstation
|
+-- Disk                  1:N   (dual parent: Diskstation + Storage Pool)
+-- Docker Container      1:N   (keyed by container_name)
+-- UPS                   0:1   (keyed by model)
```

### Relationships (7)

1. Diskstation -> Storage Pool (NEW)
2. Storage Pool -> Volume (EXISTS)
3. Volume -> iSCSI LUN (NEW)
4. Storage Pool -> Disk (NEW)
5. Diskstation -> Disk (NEW, dual parent)
6. Diskstation -> Docker Container (NEW)
7. Diskstation -> UPS (NEW)

## Metrics by Object Type

### Synology Diskstation (world)

Identifier: serial | Name: {model} ({hostname})

Existing (33 from current MP):
- CPU: Clock Speed, Cores, Family, Series, Vendor
- System: Firmware Date/Ver, Model, RAM Size, Serial, Sys Temp, Hostname
- NTP: Enabled, Server, Time Zone
- CPU Load: 1/5/15min, User, System, Other
- Memory: Avail Real, Total Real, Real Usage, Cached, Buffer
- Swap: Usage, Total, Avail, Si Disk, So Disk
- Uptime (currently PROPERTY STRING -- should be METRIC NUMBER)

New:
- memory_usage_pct (METRIC) -- calculated %
- cpu_total_load (METRIC) -- user + system
- fan_status (PROPERTY) -- from Hardware.FanSpeed
- net_rx_bytes (METRIC) -- from Utilization network
- net_tx_bytes (METRIC) -- from Utilization network
- nic_count (PROPERTY)

### Storage Pool

Identifier: pool_id + pool_path | Name: Pool {num_id} ({device_type})

Existing (6): Device Type, ID, Num ID, Pool Path, Total, Used
New: usage_pct (METRIC), status (PROPERTY), raid_type (PROPERTY), disk_count (PROPERTY)

### Volume

Identifier: volume_id + volume_path | Name: {display_name}

Existing (10): Description, Display Name, Fs Type, Pool Path, RAID Type,
Size Free Byte, Size Total Byte, Status, Volume ID, Volume Path
New: usage_pct (METRIC), io_read_iops (METRIC), io_write_iops (METRIC)

### iSCSI LUN (NEW)

Identifier: lun_uuid | Name: {name}

- name (PROPERTY), uuid (PROPERTY), size (METRIC), location (PROPERTY),
  type_str (PROPERTY)
- IO: read_iops, write_iops, read_throughput, write_throughput,
  read_latency, write_latency (all METRIC)

### Disk

Identifier: disk_id | Name: {name}

Existing (11): Device, Firm, Model, Name, Serial, Size Total, Slot ID,
Smart Status, Used By, Vendor, Wcache Force Off
New: temp (METRIC), unc_sectors (METRIC), remain_life (METRIC),
io_read (METRIC), io_write (METRIC), utilization (METRIC), disk_type (PROPERTY)

### Docker Container (NEW)

Identifier: container_name | Name: {name}

- name (PROPERTY), status (PROPERTY), image (PROPERTY)
- cpu_usage (METRIC), memory_usage (METRIC), uptime (METRIC)

### UPS (NEW)

Identifier: model | Name: {model}

- model (PROPERTY), status (PROPERTY)
- battery_charge (METRIC), load (METRIC), runtime (METRIC)

## Events

| Event | Severity | Condition | Object |
|---|---|---|---|
| Disk Failure | CRITICAL | smart_status=failing OR status=crashed | Disk |
| RAID Degraded | CRITICAL | status=degraded OR crashed | Storage Pool |
| Volume Critical | CRITICAL | usage_pct > 95 | Volume |
| Volume Low | WARNING | usage_pct > 85 | Volume |
| High Temp | CRITICAL | temp > 70 | Diskstation |
| Elevated Temp | WARNING | temp > 60 | Diskstation |
| UPS On Battery | CRITICAL | status=OB or LB | UPS |
| Fan Failure | CRITICAL | fan_status=failed or stopped | Diskstation |
| Disk UNC | WARNING | unc_sectors > 0 | Disk |
| SSD Life Low | WARNING | remain_life < 20 | Disk |

## Agent Architecture

Three new agents for MP development:

1. **api-cartographer** -- general-purpose REST API explorer for unknown APIs
2. **mp-designer** -- object model designer (wizard + plan mode mockup)
3. **mp-author** -- YAML source spec author

Workflow: api-cartographer -> mp-designer -> USER APPROVAL -> mp-author -> tooling -> qa

## Key Risks

1. Dual-parent relationships may not be supported by MPB
2. Per-object IO mapping from Utilization response requires cross-request identifier matching
3. Docker/UPS APIs may not be available if packages aren't installed
