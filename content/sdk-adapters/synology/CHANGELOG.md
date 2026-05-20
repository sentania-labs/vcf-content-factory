# Changelog

## 1.0.0.10 (2026-05-19)

- Added Synology World top-level aggregation object (global singleton across all adapter instances)
- Human-readable resource names: Storage Pool 1, Volume 1, Drive 4 (replaces internal IDs)
- Fixed NFS exports and iSCSI LUNs not nesting under parent Volume in traversal tree
- Added disk properties: drive family, is_ssd, display name
- Added UPS to traversal spec
- DiskStation named by model + serial (e.g., "DS1520+ 20B0RYRXRF3KF")

## 1.0.0.9 (2026-05-19)

- Added SSD Cache object type with read/write hit rates and capacity metrics
- Cross-adapter Datastore stitching: iSCSI LUNs via NAA transform, NFS exports via export path
- Custom SVG icons for all resource types
- DNS round-robin failover for multi-IP NAS configurations
- MIT license in EULA
- First public build

## 1.0.0.8 (2026-05-19)

- ForeignResourceResolver framework helper for cross-MP relationship lookups
- Platform logging fix (AdapterLoggerFactory with INFO level override)
- Auto-discovery gate fix (getAutoDiscoveryEnabled returns true)

## 1.0.0.7 (2026-05-19)

- Dual constructor support (no-arg for analytics, two-arg for collector)
- vrops-adapters-sdk.jar bundled in lib/

## 1.0.0.6 (2026-05-19)

- ZIP directory entries fix for SyncAdapters extraction
- Inner manifest.txt as JSON (matching outer manifest format)

## 1.0.0.1 - 1.0.0.5 (2026-05-19)

- Initial pak structure iterations: manifest format, default.png icon, adapters.zip packaging
- Core adapter: Diskstation, Storage Pool, Volume, Disk, iSCSI LUN, NFS Export, UPS
- Capacity, IO, health, and SMART metrics with cross-endpoint joining
