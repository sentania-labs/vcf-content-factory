---
date: 2026-04-15
type: reference
category: reference-doc
source: web-research, live-tested
trust: external
reviewed: false
status: filed
last_verified: 2026-04-16
sources:
  - url: https://www.home-assistant.io/integrations/synology_dsm/
    domain: home-assistant.io
    type: community
  - url: https://mibs.observium.org/mib/SYNOLOGY-SYSTEM-MIB/
    domain: observium.org
    type: community
  - url: https://mibbrowser.online/mibdb_search.php?mib=SYNOLOGY-DISK-MIB
    domain: mibbrowser.online
    type: community
  - url: https://global.download.synology.com/download/Document/Software/DeveloperGuide/Firmware/DSM/All/enu/Synology_DiskStation_MIB_Guide.pdf
    domain: synology.com
    type: vendor-doc
  - url: https://n4s4.github.io/synology-api/docs/apis
    domain: github.io
    type: community
  - url: https://github.com/mib1185/py-synologydsm-api
    domain: github.com
    type: community
  - url: https://hub.docker.com/r/jantman/prometheus-synology-api-exporter
    domain: hub.docker.com
    type: community
topics: [vcf-ops, monitoring]
tags: [synology, management-pack, mpb, rest-api, snmp, metrics]
---

# Synology Monitoring Metrics Reference

> **Revision note (2026-04-16):** Storage API namespaces, per-LUN I/O metrics, and backup API namespace corrected against live API testing on a DS1520+ running DSM 7.3.2-86009 Update 1. Corrected sections are marked. See also the live-tested brief at `workspaces/sentania-lab-toolkit/docs/reference-synology-api-mp-brief.md`.

This document catalogs all metrics available from Synology NAS devices via the REST API and SNMP, organized by category for use in a VCF Operations Management Pack.

## REST API Metrics

All REST API metrics are accessed via `/webapi/entry.cgi` with the appropriate `api`, `method`, and `version` parameters.

### System Utilization

**API**: `SYNO.Core.System.Utilization` | **Method**: `get` | **Version**: 1

> **Live-tested:** This API returns significantly more data than originally documented. In addition to CPU/memory/network, it returns per-disk I/O, per-volume I/O, NFS operation stats, SMB stats, and — critically — **per-LUN I/O metrics** for iSCSI LUNs. The per-LUN data is the key bridge for ESXi-to-storage correlation.

#### CPU & Memory

| Metric | Path in Response | Type | Unit | Description |
|--------|-----------------|------|------|-------------|
| CPU User Load | `data.cpu.user_load` | int | % | CPU time spent in user space |
| CPU System Load | `data.cpu.system_load` | int | % | CPU time spent in kernel space |
| CPU Other Load | `data.cpu.other_load` | int | % | CPU time spent on other tasks |
| Memory Total | `data.memory.total_real` | int | KB | Total installed RAM |
| Memory Free | `data.memory.avail_real` | int | KB | Currently free RAM |
| Memory Usage | (calculated) | float | % | Percentage of RAM used |
| Swap Total | `data.memory.total_swap` | int | KB | Total swap space |
| Swap Used | `data.memory.used_swap` | int | KB | Used swap space |

#### Network

| Metric | Path in Response | Type | Unit | Description |
|--------|-----------------|------|------|-------------|
| Network Upload | `data.network[].tx` | int | bytes/s | Upload transfer rate per NIC |
| Network Download | `data.network[].rx` | int | bytes/s | Download transfer rate per NIC |

#### Per-iSCSI-LUN I/O (live-tested — previously undocumented in this reference)

**Path**: `data.lun[]` — one entry per iSCSI LUN, keyed by `lun_name` and `uuid`.

| Metric | Field | Type | Unit | Description |
|--------|-------|------|------|-------------|
| LUN Name | `lun_name` | string | -- | iSCSI LUN name (matches `SYNO.Core.ISCSI.LUN` `name`) |
| LUN UUID | `uuid` | string | -- | LUN UUID (join key to iSCSI targets) |
| Read IOPS | `read_iops` | int | IOPS | Current read operations/sec |
| Write IOPS | `write_iops` | int | IOPS | Current write operations/sec |
| Total IOPS | `total_iops` | int | IOPS | Combined read+write IOPS |
| Read Throughput | `read_throughput` | int | bytes/s | Read data rate |
| Write Throughput | `write_throughput` | int | bytes/s | Write data rate |
| Total Throughput | `total_throughput` | int | bytes/s | Combined read+write throughput |
| Read Avg Latency | `read_avg_latency` | int | ms | Average read latency |
| Write Avg Latency | `write_avg_latency` | int | ms | Average write latency |
| Total IO Latency | `total_io_latency` | int | ms | Combined average latency |

**ESXi correlation**: match `lun_name` against iSCSI target IQN suffix (via `SYNO.Core.ISCSI.Target` `list`) to map ESXi iSCSI datastore latency to Synology-side LUN latency.

**Note**: The utilization API returns current-state data. For load averages, use resource parameters: `type=current&resource=cpu` or `resource=memory,network`.

### System Information

**API**: `SYNO.Core.System` | **Method**: `info` | **Version**: 1-3

| Metric/Property | Type | Description |
|-----------------|------|-------------|
| Model | string | NAS hardware model (e.g., DS920+) |
| RAM Size | int | Installed RAM in MB |
| Serial Number | string | Device serial number |
| Temperature | int | Internal system temperature (Celsius) |
| Uptime | int | System uptime in seconds |
| DSM Version | string | Firmware version string |
| CPU Clock Speed | int | CPU frequency in MHz |
| CPU Cores | int | Number of CPU cores |
| CPU Family | string | CPU architecture family |
| CPU Series | string | CPU model series |
| Timezone | string | Configured timezone |
| NTP Server | string | Configured NTP server |

### System Health

**API**: `SYNO.Core.System.SystemHealth` | **Method**: `get`

Provides overall system health status assessment.

### Storage -- Volumes, Disks, Pools, and Caches

> **Live-tested correction:** `SYNO.Core.Storage.Volume`, `SYNO.Core.Storage.Disk`, and `SYNO.Core.Storage.Pool` do not exist on DSM 7.3.2. All storage data is returned by a **single API call**: `SYNO.Storage.CGI.Storage` method `load_info`.

**API**: `SYNO.Storage.CGI.Storage` | **Method**: `load_info`

This single call returns all storage topology: volumes, storage pools, physical disks, SSD caches, and SMART basics. Use this as the primary (and only required) storage collection call.

#### Volumes (`volumes[]`)

| Metric | Field | Type | Unit | Description |
|--------|-------|------|------|-------------|
| Volume ID | `id` | string | -- | Volume identifier (e.g., `volume_1`) |
| Volume Path | `vol_path` | string | -- | Mount path (e.g., `/volume1`) |
| Status | `status` | string | -- | Normal, degraded, crashed, etc. |
| Total Size | `size.total` | int | bytes | Total volume capacity |
| Used Size | `size.used` | int | bytes | Used space on volume |
| Usage Percentage | (calculated) | float | % | `size.used / size.total * 100` |
| File System | `fs_type` | string | -- | ext4, btrfs, etc. |

#### Storage Pools (`storagePools[]`)

| Metric | Field | Type | Unit | Description |
|--------|-------|------|------|-------------|
| Pool ID | `id` | string | -- | Pool identifier (e.g., `reuse_1`) |
| Status | `status` | string | -- | Normal, degraded, etc. |
| RAID Type | `raidType` | string | -- | SHR, RAID1, RAID5, RAID6, etc. |
| Member Disks | `disks[]` | array | -- | List of disk IDs in this pool |

#### Physical Disks (`disks[]`)

| Metric | Field | Type | Unit | Description |
|--------|-------|------|------|-------------|
| Disk ID | `id` | string | -- | Disk identifier (e.g., `sata1`) |
| Model | `model` | string | -- | Drive model name |
| Serial | `serial` | string | -- | Drive serial number |
| Disk Type | `diskType` | string | -- | SATA, SSD, NVMe, etc. |
| Temperature | `temp` | int | C | Current drive temperature |
| SMART Status | `smart_status` | string | -- | normal, abnormal, etc. |
| Uncorrectable Sectors | `unc` | int | count | Uncorrectable sector count (>0 = warning) |
| Remaining Life | `remain_life` | int | % | SSD/NVMe wear indicator |
| Total Size | `size_total` | int | bytes | Drive capacity |
| Firmware | `firm` | string | -- | Drive firmware version |

#### SSD Cache (`sharedCaches[]` or `ssdCaches[]`)

| Metric | Field | Type | Unit | Description |
|--------|-------|------|------|-------------|
| Cache Status | `status` | string | -- | Normal, degraded, etc. |
| RAID Type | `raidType` | string | -- | RAID 1 (mirrored) typical |
| Member Disks | `disks[]` | array | -- | List of cache disk IDs |

### Storage -- HDD Management

**API**: `SYNO.Storage.CGI.HddMan` | **Method**: `get`

Provides HDD manager configuration including bad sector threshold and health report settings.

### Hardware

**API**: `SYNO.Core.Hardware.FanSpeed` | **Method**: `get`

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| Fan Speed | int | RPM | Current fan speed |
| Fan Status | string | -- | Normal/failed |

**API**: `SYNO.Core.Hardware.PowerRecovery`

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| Power Recovery Setting | string | -- | Auto-restart after power loss config |

### UPS

**API**: `SYNO.Core.ExternalDevice.UPS` | **Method**: `get`

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| UPS Status | string | -- | Online, on battery, low battery |
| UPS Model | string | -- | UPS device model |
| Battery Charge | int | % | Current battery charge level |
| Runtime Remaining | int | seconds | Estimated runtime on battery |

### Network

**API**: `SYNO.Core.Network` | **Method**: `get` or `list`

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| Interface Name | string | -- | eth0, bond0, etc. |
| Link Status | string | -- | Up/down |
| Speed | int | Mbps | Link speed |
| IP Address | string | -- | Configured IP |
| MAC Address | string | -- | Hardware address |

### Services & Packages

**API**: `SYNO.Core.Package` | **Method**: `list`

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| Package Name | string | -- | Installed package identifier |
| Package Version | string | -- | Installed version |
| Package Status | string | -- | Running, stopped, etc. |

**API**: `SYNO.Core.Service` | **Method**: `get`

Service status for SMB, NFS, FTP, SSH, etc.

### Docker Containers

**API**: `SYNO.Docker.Container` | **Method**: `list` or `get`

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| Container Name | string | -- | Container identifier |
| Container Status | string | -- | Running, stopped, etc. |
| CPU Usage | float | % | Container CPU utilization |
| Memory Usage | int | bytes | Container memory consumption |

### Backup

> **Live-tested correction:** `SYNO.Backup.Task` is the Hyper Backup namespace. Active Backup for Business uses the `SYNO.ActiveBackup.*` namespace on DSM 7.3.2.

**API**: `SYNO.ActiveBackup.Task` | **Method**: `list` (for Active Backup for Business)

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| Task Name | string | -- | Backup task identifier |
| Task Status | string | -- | Success, failed, running |
| Last Run Time | datetime | -- | When the task last executed |
| Next Run Time | datetime | -- | When the task will next run |

**API**: `SYNO.Backup.Task` | **Method**: `list` (for Hyper Backup — older backup package)

### Security

**API**: `SYNO.Core.Security.DSM`

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| Security Status | string | -- | Safe, risk, danger, etc. |
| Firewall Enabled | bool | -- | Whether firewall is active |

### Upgrade Availability

**API**: `SYNO.Core.Upgrade`

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| Update Available | bool | -- | Whether a DSM update exists |
| Available Version | string | -- | Version string of available update |
| Reboot Required | bool | -- | Whether update requires reboot |

---

## SNMP Metrics

All Synology-specific SNMP OIDs are under the enterprise OID **1.3.6.1.4.1.6574**. The [Synology DiskStation MIB Guide](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Firmware/DSM/All/enu/Synology_DiskStation_MIB_Guide.pdf) (updated March 2025) documents the complete set.

### SYNOLOGY-SYSTEM-MIB (1.3.6.1.4.1.6574.1)

Source: [Observium MIB Browser](https://mibs.observium.org/mib/SYNOLOGY-SYSTEM-MIB/)

| OID | Name | Type | Description |
|-----|------|------|-------------|
| .1.3.6.1.4.1.6574.1.1 | systemStatus | Integer32 | System operational state (1=Normal, 2=Failed) |
| .1.3.6.1.4.1.6574.1.2 | temperature | Integer32 | Device temperature (Celsius) |
| .1.3.6.1.4.1.6574.1.3 | powerStatus | Integer32 | Power supply condition (1=Normal, 2=Failed) |
| .1.3.6.1.4.1.6574.1.4.1 | systemFanStatus | Integer32 | Main fan status (1=Normal, 2=Failed) |
| .1.3.6.1.4.1.6574.1.4.2 | cpuFanStatus | Integer32 | CPU fan status (1=Normal, 2=Failed) |
| .1.3.6.1.4.1.6574.1.5.1 | modelName | OctetString | Device model (e.g., DS920+) |
| .1.3.6.1.4.1.6574.1.5.2 | serialNumber | OctetString | Device serial code |
| .1.3.6.1.4.1.6574.1.5.3 | version | OctetString | DSM firmware version |
| .1.3.6.1.4.1.6574.1.5.4 | upgradeAvailable | Integer32 | 1=Available, 2=Unavailable, 3=Connecting, 4=Disconnected, 5=Others |
| .1.3.6.1.4.1.6574.1.6 | controllerNumber | Integer32 | Number of active controllers |
| .1.3.6.1.4.1.6574.1.7.1 | cpuUtilization | Integer32 | CPU usage percentage |
| .1.3.6.1.4.1.6574.1.7.2 | memUtilization | Integer32 | Memory usage percentage |
| .1.3.6.1.4.1.6574.1.8 | thermalStatus | Integer32 | Thermal condition (1=Normal, 2=Abnormal) |

### SYNOLOGY-DISK-MIB (1.3.6.1.4.1.6574.2)

Source: [MIB Browser Online](https://mibbrowser.online/mibdb_search.php?mib=SYNOLOGY-DISK-MIB)

Table prefix: `.1.3.6.1.4.1.6574.2.1.1`

| OID Suffix | Name | Type | Description |
|------------|------|------|-------------|
| .1 | diskIndex | Integer32 | Disk table index |
| .2 | diskID | OctetString | Disk identifier assigned by DSM |
| .3 | diskModel | OctetString | Drive model designation |
| .4 | diskType | OctetString | Drive type (SATA, SSD, etc.) |
| .5 | diskStatus | Integer32 | 1=Normal, 2=Initialized, 3=NotInitialized, 4=SystemPartitionFailed, 5=Crashed |
| .6 | diskTemperature | Integer32 | Drive temperature (Celsius) |

### SYNOLOGY-RAID-MIB (1.3.6.1.4.1.6574.3)

Table prefix: `.1.3.6.1.4.1.6574.3.1.1`

| OID Suffix | Name | Type | Description |
|------------|------|------|-------------|
| .1 | raidIndex | Integer32 | RAID table index |
| .2 | raidName | OctetString | RAID name in DSM |
| .3 | raidStatus | Integer32 | 1=Normal, 2=Repairing, 3=Migrating, 4=Expanding, 5=Deleting, 6=Creating, 7=RaidSyncing, 8=RaidParityChecking, 9=RaidAssembling, 10=Canceling, 11=Degraded, 12=Crashed |
| .4 | raidFreeSize | Integer64 | Free space in bytes |
| .5 | raidTotalSize | Integer64 | Total capacity in bytes |

### SYNOLOGY-UPS-MIB (1.3.6.1.4.1.6574.4)

UPS OIDs depend on what information the connected UPS device provides. Common OIDs include battery charge, runtime remaining, input/output voltage, and UPS status.

### Standard SNMP MIBs

Synology also supports standard SNMP MIBs for:
- **HOST-RESOURCES-MIB** -- CPU, memory, storage, process info
- **IF-MIB** -- Network interface statistics (bandwidth, errors, packets)
- **UCD-SNMP-MIB** -- Extended system metrics (load averages, memory details)

---

## Recommended Metrics for a VCF Operations Management Pack

### Tier 1: Critical (collect every 5 minutes)

| Object Type | Metric | Source API | Why |
|-------------|--------|-----------|-----|
| NAS System | CPU Utilization % | `SYNO.Core.System.Utilization` | Performance baseline |
| NAS System | Memory Utilization % | `SYNO.Core.System.Utilization` | Capacity planning |
| NAS System | System Temperature | `SYNO.Core.System` info | Hardware health |
| NAS System | System Status | `SYNO.Core.System.Status` | Overall health |
| NAS System | Uptime | `SYNO.Core.System` info | Availability tracking |
| iSCSI LUN | Read/Write IOPS | `SYNO.Core.System.Utilization` `lun[]` | ESXi-to-storage correlation |
| iSCSI LUN | Read/Write Latency | `SYNO.Core.System.Utilization` `lun[]` | ESXi-to-storage correlation |
| iSCSI LUN | Throughput | `SYNO.Core.System.Utilization` `lun[]` | Bandwidth monitoring |
| Volume | Usage % | `SYNO.Storage.CGI.Storage` `load_info` | Capacity management |
| Volume | Status | `SYNO.Storage.CGI.Storage` `load_info` | Health monitoring |
| Disk | Status | `SYNO.Storage.CGI.Storage` `load_info` | Failure detection |
| Disk | SMART Status | `SYNO.Storage.CGI.Storage` `load_info` | Predictive failure |
| Disk | Temperature | `SYNO.Storage.CGI.Storage` `load_info` | Environmental health |
| Disk | Uncorrectable Sectors | `SYNO.Storage.CGI.Storage` `load_info` | Early failure indicator |

### Tier 2: Important (collect every 15 minutes)

| Object Type | Metric | Source API | Why |
|-------------|--------|-----------|-----|
| NAS System | Fan Status/Speed | `SYNO.Core.Hardware.FanSpeed` | Cooling health |
| NAS System | Power Status | `SYNO.Core.System.Status` | Power supply health |
| NAS System | Network Upload/Download | `SYNO.Core.System.Utilization` | Bandwidth monitoring |
| Storage Pool | Pool Status | `SYNO.Storage.CGI.Storage` `load_info` | RAID health |
| Storage Pool | RAID Type | `SYNO.Storage.CGI.Storage` `load_info` | Configuration tracking |
| SSD Cache | Cache Status | `SYNO.Storage.CGI.Storage` `load_info` | Cache health |
| SSD Cache | Remaining Life % | `SYNO.Storage.CGI.Storage` `load_info` | Wear monitoring |
| UPS | Battery Charge % | `SYNO.Core.ExternalDevice.UPS` | Power protection |
| UPS | Runtime Remaining | `SYNO.Core.ExternalDevice.UPS` | Power protection |
| UPS | Status | `SYNO.Core.ExternalDevice.UPS` | Power protection |

### Tier 3: Informational (collect every 30-60 minutes)

| Object Type | Metric | Source API | Why |
|-------------|--------|-----------|-----|
| NAS System | DSM Version | `SYNO.Core.System` info | Compliance |
| NAS System | Update Available | `SYNO.Core.Upgrade` | Patch management |
| NAS System | Security Status | `SYNO.Core.Security.DSM` | Security posture |
| Package | Status | `SYNO.Core.Package` | Service availability |
| Docker Container | Status | `SYNO.Docker.Container` | Workload monitoring |
| Backup Task | Last Status | `SYNO.ActiveBackup.Task` (ABB) or `SYNO.Backup.Task` (Hyper Backup) | Data protection |

### Suggested Object Hierarchy for MPB

```
NAS System (root object)
├── Storage Pool (per pool)
│   ├── Volume (per volume)
│   └── Physical Disk (per disk)
├── Network Interface (per interface)
├── UPS (if connected)
├── Package (per installed package)
├── Docker Container (per container)
└── Backup Task (per task)
```

### Suggested Alerts

| Alert | Condition | Severity | Impact |
|-------|-----------|----------|--------|
| System Status Abnormal | systemStatus != Normal | Critical | Health |
| Volume Usage High | usage > 85% | Warning | Risk |
| Volume Usage Critical | usage > 95% | Critical | Risk |
| Disk SMART Failure | smart_status != normal | Critical | Health |
| Disk Status Degraded | disk status == Crashed | Critical | Health |
| Disk Uncorrectable Sectors | unc > 0 | Warning | Health |
| RAID Degraded | pool status == Degraded | Critical | Health |
| RAID Crashed | pool status == Crashed | Critical | Health |
| SSD Wear Low | remain_life < 20% | Warning | Health |
| High Temperature | temperature > 60 | Warning | Health |
| Critical Temperature | temperature > 70 | Critical | Health |
| Fan Failure | fanStatus == Failed | Critical | Health |
| LUN Latency High | total_io_latency > threshold | Warning | Performance |
| UPS On Battery | upsStatus == OnBattery | Warning | Risk |
| UPS Low Battery | upsStatus == LowBattery | Critical | Risk |
| Backup Failed | lastStatus == Failed | Warning | Risk |
| DSM Update Available | upgradeAvailable == true | Info | Risk |
