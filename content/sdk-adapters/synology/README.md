# VCF Content Factory Synology DiskStation

Monitors Synology DiskStation NAS devices via the DSM Web API (Tier 2 SDK adapter).

## What it monitors

| Object | Metrics | Properties |
|---|---|---|
| **Synology World** | Global aggregation root | — |
| **DiskStation** | CPU, memory, network, temperature, uptime, NFS ops/latency | Model, hostname, firmware, fan status |
| **Storage Pool** | Capacity (total, used, usage %) | RAID type, status, disk count |
| **Volume** | Capacity, IO (read/write throughput, IOPS, utilization), SSD cache hit rates | Filesystem type, status, volume path |
| **Disk** | Temperature, SMART health, IO (read/write throughput, IOPS, utilization), remaining life | Model, firmware, serial, vendor, disk type, drive family, slot ID, capacity |
| **iSCSI LUN** | IO (read/write IOPS, throughput, latency) | Name, size, location, type, target IQN |
| **NFS Export** | Capacity (used, logical, quota usage %), active client count | Export path, volume path, allowed clients, CoW, compression |
| **SSD Cache** | Read/write hit rates, capacity (total, occupied, reusable), metadata memory | Mode, status, mount volume |
| **UPS** | Battery charge %, runtime | Status, mode |

**Cross-adapter stitching**: iSCSI LUNs and NFS exports are linked to VMWARE Datastores
via NAA transform and NFS export path matching. Clicking a Datastore shows the backing
Synology storage health.

## Prerequisites

- Synology DSM 7.2 or later
- Admin account with API access on port 5001 (HTTPS)
- VCF Operations 8.x or 9.x

## Install

1. Open VCF Operations → **Administration → Solutions**
2. Click **Add** (or the upload icon)
3. Select the `.pak` file from this package
4. Accept the EULA and wait for installation to complete (~30 seconds)

## Configure

After installation, create an adapter instance:

1. Go to **Administration → Solutions → VCF Content Factory Synology DiskStation**
2. Click **Configure** → **Add Adapter Instance**
3. Fill in:
   - **Host / IP Address**: Your NAS hostname or IP (e.g., `storage.example.com`)
   - **Port**: HTTPS port (default `5001`)
   - **Allow Insecure SSL**: `true` if using self-signed certificates
   - **Username**: DSM admin account
   - **Password**: Account password
4. Click **Test Connection**, then **Save**

Discovery runs immediately. Metrics begin collecting on the next 5-minute cycle.

## Object hierarchy

```
Synology World
└── DS1520+ 20B0RYRXRF3KF
    ├── Storage Pool 1
    │   ├── Volume 1
    │   │   ├── NFS Export: share-name
    │   │   ├── iSCSI LUN: lun-name
    │   │   └── SSD Cache: alloc_cache_1_1
    │   ├── Drive 1
    │   ├── Drive 2
    │   ├── ...
    │   ├── Cache device 1
    │   └── Cache device 2
    └── UPS (if connected)
```

Use the **Synology DiskStation Storage Tree** traversal spec to navigate the hierarchy.

## License

MIT — see LICENSE in the VCF Content Factory repository.
