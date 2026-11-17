# Synology API Brief — ESXi-to-Disk Mapping via API

## The Question

Can we create a map between what ESXi sees as a datastore (NFS or
iSCSI) and trace it back through the Synology API to the underlying
NFS export/iSCSI LUN -> volume -> storage pool -> physical disks?

**Answer: Yes.** The API provides every link in the chain.

## Target NAS — Confirmed via Live API

| Property | Value |
|----------|-------|
| Model | DS1520+ |
| DSM | 7.3.2-86009 Update 1 |
| CPU | Intel Celeron J4125 (4 cores, 2 GHz) |
| RAM | 20 GB |
| Uptime | ~50 days |
| API entry point | `https://storage:5001/webapi/entry.cgi` |
| Total APIs available | **674** |

## The Mapping Chain

### NFS Datastores (ESXi -> Synology)

ESXi mounts NFS exports by path. The Synology side:

```
ESXi NFS datastore mount path     Synology share      Volume    Pool       Disks
──────────────────────────────     ──────────────      ──────    ────       ─────
/volume1/wld01                  → wld01             → volume_1 → reuse_1 → sata1-5
/volume1/wld02                  → wld02             → volume_1 → reuse_1 → sata1-5
/volume1/vcf9                   → vcf9              → volume_1 → reuse_1 → sata1-5
/volume1/vsphere_admin          → vsphere_admin     → volume_1 → reuse_1 → sata1-5
/volume1/backup                 → backup            → volume_1 → reuse_1 → sata1-5
```

NFS clients currently connected (from `SYNO.Core.CurrentConnection`):
- 172.16.3.101, .102, .103, .104, .105 (ESXi hosts)
- 172.16.3.110, .120, .125 (other infra)
- 172.16.3.13 (management)

NFS export ACLs (from `showmount -e`):
- wld01, wld02: `172.16.3.0/24, 172.27.1.0/24`
- vcf9: `172.27.1.0/24, 172.16.3.0/24`
- vsphere_admin: `172.16.3.0/24, 172.27.1.0/24, 172.26.3.0/24, 172.30.1.0/24, 10.100.3.0/24`

### iSCSI Datastores (ESXi -> Synology)

```
ESXi iSCSI target IQN                                                LUN name                    Size     Volume
──────────────────────────────────────────────────────────────────     ────────────────────────     ────     ──────
iqn.2000-01.com.synology:storage.vcf-lab-wld01-cl01.cfb45402d27    → vcf-lab-wld01-cl01        → 8.0 TB → volume_1
iqn.2000-01.com.synology:storage.vcf-lab-wld01-cl02.cfb45402d27    → (target only, no LUN)     → -      → -
iqn.2000-01.com.synology:storage.vcf-lab-mgmt01-cl01.cfb45402d27   → vcf-lab-mgmt01-cl01-lun0  → 8.2 TB → volume_1
(no target for wld02 LUN found)                                      vcf-lab-wld02-cl01        → 8.0 TB → volume_1
```

All iSCSI LUNs are block-level (BLUN), thin-provisioned, on `/volume1`.

### Full Chain (same for both NFS and iSCSI)

```
volume_1 (btrfs, 26.18 TB total, 5.59 TB used, 21.3%)
  └── reuse_1 (SHR/multiple RAID, status: normal)
       ├── sata1: ST10000VN0004 IronWolf 10TB  35°C  SMART:normal  unc:0
       ├── sata2: ST10000VN0004 IronWolf 10TB  34°C  SMART:normal  unc:0
       ├── sata3: ST10000VN0004 IronWolf 10TB  33°C  SMART:normal  unc:6   ⚠
       ├── sata4: ST10000VN0004 IronWolf 10TB  34°C  SMART:normal  unc:16  ⚠
       └── sata5: ST10000VN0008 IronWolf 10TB  36°C  SMART:normal  unc:0

SSD Cache (RAID 1, shared):
  ├── nvme0n1: Samsung 990 PRO 2TB  38°C  remain_life:81%
  └── nvme1n1: Samsung 990 PRO 2TB  37°C  remain_life:80%
```

Note: sata3 has 6 uncorrectable sectors and sata4 has 16. Both still
report SMART:normal but worth watching.

## APIs That Build the Map

### Step 1: Get NFS exports

**API:** `showmount -e` via SSH (no direct API for NFS export list)

Or indirectly via `SYNO.Core.Share` + `SYNO.Core.FileServ.NFS`:
- `SYNO.Core.Share` → list shares with `vol_path` and `uuid`
- `SYNO.Core.FileServ.NFS` → confirms NFS is enabled, NFSv4

The shares map directly to NFS mount paths (`/volume1/<share_name>`).
ESXi stores the NFS mount path in its datastore config.

### Step 2: Get iSCSI LUN → target mapping

**API:** `SYNO.Core.ISCSI.LUN` method=`list`
- Returns: `name`, `uuid`, `size`, `location` (`/volume1`), `type_str` (BLUN)

**API:** `SYNO.Core.ISCSI.Target` method=`list`
- Returns: `name`, `iqn`, `is_enabled`, `network_portals`
- ESXi stores the IQN in its iSCSI adapter config

**Joining key:** Target name ↔ LUN name (by convention, or via
`SYNO.Core.ISCSI.LUN` method=`map_target`/`list` cross-reference)

### Step 3: Get volume → pool → disk chain

**API:** `SYNO.Storage.CGI.Storage` method=`load_info`

Single call returns **everything**:
- `volumes[]` — id, status, fs_type, size.total, size.used, vol_path
- `storagePools[]` — id, status, raidType, disks[] (list of disk IDs)
- `disks[]` — id, model, serial, temp, smart_status, unc (uncorrectable sectors), remain_life, size_total, diskType, firm
- `ssdCaches[]` / `sharedCaches[]` — cache disk IDs, RAID type, status

### Step 4: Get real-time I/O per LUN

**API:** `SYNO.Core.System.Utilization` method=`get`

Returns `lun[]` array with per-LUN metrics:
```json
{
  "lun_name": "vcf-lab-wld01-cl01",
  "uuid": "d023e190-...",
  "read_iops": 0,
  "write_iops": 164,
  "read_throughput": 0,
  "write_throughput": 867388,
  "read_avg_latency": 0,
  "write_avg_latency": 71,
  "total_iops": 164,
  "total_throughput": 867388,
  "total_io_latency": 66
}
```

Also returns per-disk I/O (`disk[]`), per-volume I/O (`space.volume[]`),
per-NIC throughput (`network[]`), CPU, and memory.

### Step 5: Get active connections

**API:** `SYNO.Core.CurrentConnection` method=`list`
- Shows NFS clients with IP and connection time
- Shows iSCSI sessions (when active)

## Complete API Reference (tested on this NAS)

### Works (admin account required for most)

| API | Method | Returns |
|-----|--------|---------|
| `SYNO.API.Info` | `query` | All 674 API names, versions, paths |
| `SYNO.API.Auth` | `login`/`logout` | Session token (sid) |
| `SYNO.DSM.Info` | `getinfo` | Model, serial, DSM version, RAM, temp, uptime |
| `SYNO.Core.System` | `info` | CPU (J4125/4core/2GHz), firmware, serial, temp, NTP, timezone |
| `SYNO.Core.System.Status` | `get` | is_system_crashed, upgrade_ready |
| `SYNO.Core.System.SystemHealth` | `get` | Health status, interfaces with IPs, uptime |
| `SYNO.Core.System.Utilization` | `get` | CPU, memory, per-disk I/O, per-LUN I/O, per-NIC throughput, NFS ops, SMB stats |
| `SYNO.Storage.CGI.Storage` | `load_info` | **The big one.** Disks, pools, volumes, caches, SMART, all in one call |
| `SYNO.Storage.CGI.HddMan` | `get` | HDD manager settings (bad sector threshold, health report config) |
| `SYNO.Core.ISCSI.LUN` | `list` | All LUNs with name, uuid, size, location, type, dev_attribs |
| `SYNO.Core.ISCSI.Target` | `list` | All targets with IQN, name, enabled, network_portals |
| `SYNO.Core.ISCSI.Node` | `list` | iSCSI initiator nodes |
| `SYNO.Core.Share` | `list` | Shares with name, uuid, vol_path, description |
| `SYNO.Core.FileServ.NFS` | `get` | NFS config (enabled, v4, read/write sizes) |
| `SYNO.Core.Network` | `get` | DNS, gateway, hostname, gateway interface |
| `SYNO.Core.Network.Interface` | `list` | All NICs: ifname, IP, mask, speed, status |
| `SYNO.Core.Hardware.FanSpeed` | `get` | Fan status and type |
| `SYNO.Core.ExternalDevice.UPS` | `get` | UPS config (not connected on this NAS) |
| `SYNO.Core.CurrentConnection` | `list` | Active NFS/SMB/iSCSI/HTTP connections |
| `SYNO.Core.Package` | `list` | Installed packages (ABB, FileStation, etc.) |
| `SYNO.Core.Upgrade.Server` | `check` | Available updates (Update 3 available) |
| `SYNO.FileStation.List` | `list_share` | Shares with volume_status (free/total space), owner, perms |
| `SYNO.Docker.Container` | `list` | All containers with image, state, health (Immich stack: 4 containers) |

### Needs correct parameters (error 114 — missing required param)

| API | Method | Notes |
|-----|--------|-------|
| `SYNO.Storage.CGI.Smart` | `get_health_info` | Needs specific disk parameter format TBD |
| `SYNO.Storage.CGI.Smart` | `get_smart_info` | Same — but `load_info` already has SMART basics |

### Needs method discovery (error 103)

| API | Correct methods (from lib file) |
|-----|-------------------------------|
| `SYNO.Core.Service` | Not found in lib — may be v2/v3 specific |
| `SYNO.Core.DSMNotify` | Needs investigation |

## Network Topology (from API)

4 NICs, all on VLAN 131:

| Interface | IP | Speed | Status |
|-----------|-----|-------|--------|
| eth0.131 | 172.16.3.51 | 1 Gbps | connected |
| eth1.131 | 172.16.3.52 | 1 Gbps | connected |
| eth2.131 | 172.16.3.53 | 1 Gbps | connected |
| eth3.131 | 172.16.3.54 | 1 Gbps | connected |

Gateway: 172.16.3.1 via eth0.131
DNS: 172.27.8.8

## Docker Containers (from API)

| Container | Image | Status |
|-----------|-------|--------|
| immich_server | ghcr.io/immich-app/immich-server:v2 | running (healthy) |
| immich_postgres | postgres:14-vectorchord0.4.3 | running |
| immich_machine_learning | immich-machine-learning:v2 | running |
| immich_redis | valkey:9 | running |

## Authentication Requirements

- **Admin account required** for all `SYNO.Core.*` and `SYNO.Storage.CGI.*` APIs
- Non-admin can only access: `SYNO.DSM.Info`, `SYNO.FileStation.*`, `SYNO.Core.Package`, `SYNO.Core.Hardware.FanSpeed`
- The `claude` account has been promoted to admin — all APIs now work

## Credential Store

Entry in `lab-config.json` at `services.synology.storage`:
```json
{
  "server": "storage",
  "user": "claude",
  "password": "..."
}
```

## API Definition Files

The authoritative API definitions (methods, versions, permissions)
live on the NAS at `/usr/syno/synoman/webapi/*.lib` (178 lib files).
These are JSON files that define:
- `allowUser` — which user types can call the API
- `methods` — per-version method list with `grantable`, `allowDemo`, `actionPrivileges`
- `minVersion`/`maxVersion`
- `lib` — shared object that implements the API

Key lib files for the MP:
- `SYNO.Storage.CGI.lib` — 22 APIs, all storage/disk/pool/volume/SMART methods
- `SYNO.Core.ISCSI.lib` — 8 APIs, LUN/target/host/replication/VMware
- `SYNO.Core.System.lib` — 7 APIs, system/utilization/health
- `SYNO.Core.Network.lib` — 28 APIs, interface/bond/ethernet
- `SYNO.Core.Hardware.lib` — 14 APIs, fan/hibernation/power/LED

## VCF Operations MP — Build Path

**Use MPB (Management Pack Builder)**, not the Integration SDK.
MPB is a separate OVA appliance that builds REST adapter `.pak` files
natively — no container images, no Python SDK, no cloud proxy
dependency. The Integration SDK is for when MPB can't handle the use
case (e.g., SNMP adapters).

vcf-content-factory is **not** the right tool either — it authors
dashboards/super metrics/alerts on *existing* VCF Ops object types.
MPB teaches VCF Ops about *new* object types (like "Synology NAS").
vcf-content-factory comes later if you want cross-object super metrics
(e.g., correlating NAS volume usage with VM storage consumption).

Reference MPB JSON design: `workspaces/vcf-content-factory/references/
dalehassinger_unlocking_the_potential/VMware-Aria-Operations/
Management-Packs/GitHub/GitHub-MP-Builder.json`

### MPB Setup

- MPB 2.0 is a separate OVA (~2 GB), deploys to vCenter, static IP
- Default creds: admin/admin (change on first login)
- MPB 2.0 is NOT an in-place upgrade from 1.x — fresh deploy only
- Full docs in `reference/docs/vmware-cloud-foundation-9-0.pdf` (8285 pages)

### Minimum Viable MP — API Calls

**Auth:** `SYNO.API.Auth` v7 login → sid token, re-auth on 106/119

**Two core calls per 5-min collection:**

1. `SYNO.Storage.CGI.Storage` `load_info`
   → disks (model, serial, temp, SMART, unc sectors, remain_life)
   → pools (RAID type, status, member disks)
   → volumes (capacity, used, fs_type, status)
   → SSD cache (status, member disks)

2. `SYNO.Core.System.Utilization` `get`
   → CPU (load averages, user/system/other %)
   → memory (real_usage %, avail, cached, swap)
   → per-disk I/O (read/write bytes, IOPS, utilization %)
   → **per-LUN I/O** (IOPS, throughput, avg latency — critical for ESXi mapping)
   → per-NIC throughput (rx/tx bytes)
   → per-volume I/O
   → NFS operation stats
   → SMB stats

**Supplementary calls (15-min interval):**

3. `SYNO.Core.ISCSI.LUN` `list` → LUN name, uuid, size, location
4. `SYNO.Core.ISCSI.Target` `list` → target IQN (join key to ESXi)
5. `SYNO.DSM.Info` `getinfo` → model, serial, DSM version, temp, uptime
6. `SYNO.Core.System` `info` → CPU model, firmware, timezone
7. `SYNO.Core.Network.Interface` `list` → NICs, speed, IP, status
8. `SYNO.Core.CurrentConnection` `list` → active NFS/iSCSI/SMB clients
9. `SYNO.Core.Hardware.FanSpeed` `get` → fan status
10. `SYNO.Core.ExternalDevice.UPS` `get` → UPS status (if connected)

**30-60 min interval:**

11. `SYNO.Docker.Container` `list` → container state, health
12. `SYNO.Core.Package` `list` → installed packages
13. `SYNO.Core.Upgrade.Server` `check` → available DSM updates

### Object model for the MP

```
SynologyNAS  — keyed by serial number
├── StoragePool (reuse_1, SHR)  — keyed by pool ID
│   ├── Volume (volume_1, btrfs)  — keyed by vol_path
│   │   ├── NFSExport (wld01, wld02, vcf9...)
│   │   │   └── → ESXi NFS Datastore (join on mount path)
│   │   └── iSCSI_LUN (vcf-lab-wld01-cl01, mgmt01-cl01-lun0...)
│   │       └── → ESXi iSCSI Datastore (join on target IQN)
│   └── Disk (sata1..5)  — keyed by disk ID
├── SSDCache (shared_cache_1, RAID 1)
│   └── CacheDisk (nvme0n1, nvme1n1)
├── NetworkInterface (eth0-3)  — keyed by ifname
├── DockerContainer (immich_server, etc.)  — keyed by container name
└── UPS (if connected)
```

### Alert thresholds

| Condition | Severity |
|-----------|----------|
| Volume usage > 85% | Warning |
| Volume usage > 95% | Critical |
| Disk status = Crashed | Critical |
| RAID status = Degraded | Critical |
| System temp > 60°C | Warning |
| System temp > 70°C | Critical |
| Fan status = Failed | Critical |
| UPS on battery | Warning |
| UPS low battery | Critical |
| Disk unc sectors > 0 | Warning |
| SSD remain_life < 20% | Warning |

### Critical path

1. Deploy MPB 2.0 OVA (if not already deployed)
2. Verify API connectivity: `curl -k "https://storage:5001/webapi/entry.cgi?api=SYNO.API.Info&version=1&method=query&query=all"`
3. In MPB: create source (storage:5001, HTTPS, /webapi)
4. In MPB: configure session auth (SYNO.API.Auth login → capture sid)
5. Start with System Info + Utilization requests only
6. Use MPB "Perform Collection" test button to verify
7. Add storage requests one at a time
8. Build NAS root object first, then child objects, then relationships
9. Build and install .pak
10. Dashboards come after — in VCF Operations, not MPB

## Desk Research vs Live Testing — Corrections

The desk-research brief (2026-04-15) had some API names from community docs
that don't match what's actually on this NAS (DSM 7.3.2):

| Desk research said | Actual on this NAS | Notes |
|-------------|-------------------|-------|
| `SYNO.Core.Storage.Volume` `list` | `SYNO.Storage.CGI.Volume` | Different namespace |
| `SYNO.Core.Storage.Disk` `list` | Disk data in `SYNO.Storage.CGI.Storage` `load_info` | No separate disk list API |
| `SYNO.Core.Storage.Pool` `list` | `SYNO.Storage.CGI.Pool` | Different namespace |
| Auth v6 recommended | Auth v7 available (v6 also works) | v7 is max on DSM 7.3.2 |
| `SYNO.Backup.Task` `list` | `SYNO.ActiveBackup.*` namespace | ABB has its own API tree |

**Key finding the desk research missed:** `SYNO.Core.System.Utilization` returns
**per-LUN I/O metrics** (IOPS, throughput, latency per iSCSI LUN by name
and UUID). This is the critical bridge for ESXi-to-storage mapping — you
can correlate ESXi datastore latency with the Synology-side LUN latency
directly.

## References

- `reference/docs/Synology_File_Station_API_Guide.pdf` — File Station API (60 pages)
- `reference/docs/vmware-cloud-foundation-9-0.pdf` — VCF 9 docs incl. MP Builder (8285 pages)
- [synology-api Python library](https://github.com/N4S4/synology-api) — community wrapper, 300+ APIs
- [kwent/syno definitions](https://github.com/kwent/syno/tree/master/definitions) — extracted DSM API schema files
- `/usr/syno/synoman/webapi/*.lib` — authoritative API definitions on-NAS (178 files)
- Desk-research notes, 2026-04-15 (4 notes, not committed)
- Dale Hassinger MPB JSON reference in vcf-content-factory workspace
