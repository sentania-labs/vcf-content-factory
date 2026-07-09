# Synology DiskStation Adapter v1 — Golden Baseline (devel, pre-migration)

**Captured:** 2026-06-10
**Instance:** vcf-lab-operations-devel.int.sentania.net (VCF Ops 9.0.2)
**Purpose:** Acceptance bar for framework v2 migration. Post-migration comparison must diff against this file.
**Ordering convention:** All sections sorted alphabetically by resource name, then by metric/property key.
**Encoding:** Metric values are raw floats. Property values are strings as returned by the API.
**Timestamps:** UTC ISO-8601, converted from epoch-ms.
**Secrets check:** No secrets present. Credential UUID is included (public repo safe). No passwords or API keys.

---

## 1. Adapter Instance Health

One `synology_diskstation` adapter instance is installed. It is DATA_RECEIVING / STARTED.
The overall adapter instance resource health is ORANGE (50.0) due to a platform alert —
"Objects are not receiving data from adapter instance" (alertDefinition:
`AdapterChildsNoDataReceivingAlert`) — caused by the `SynologyWorld` singleton having
`NO_DATA_RECEIVING` status. This is a v1 architecture artifact: the world singleton
collects no metrics of its own. Health of all 24 data-producing resources is GREEN.

| Field | Value |
|---|---|
| adapter_instance_resource_id | `1da1ec07-b23f-496f-83e2-ae56d5dc6f0d` |
| adapter_kind_key | `synology_diskstation` |
| solution_name | VCF Content Factory Synology DiskStation |
| solution_version | 1.0.0.13 |
| host | storage.int.sentania.net |
| port | 5001 |
| allowInsecure | true |
| monitoringInterval_minutes | 5 |
| credentialInstanceId | `685201c9-60c2-4417-8a4a-f1b5e8aeb95b` |
| resourceStatus | DATA_RECEIVING |
| resourceState | STARTED |
| resourceHealth | ORANGE |
| resourceHealthValue | 50.0 |
| messageFromAdapterInstance | (empty) |
| collectorId | 1 |
| lastCollected (latest stat timestamp) | 2026-06-10T04:59:01Z |
| numberOfResourcesCollected | 25 (24 monitoring, 1 no-data: SynologyWorld) |
| numberOfMetricsCollected | 136 |
| activeAlerts | 1 — "Objects are not receiving data from adapter instance" (IMMEDIATE, ACTIVE, alertId: `4ca5bdae-fd64-45fd-9eaa-a98e48adf0d2`) |

**Collection cadence:** 5 minutes. Post-migration comparison should wait at least 6 minutes after v2 starts collecting before diffing metric values.

---

## 2. Adapter Own Resource Tree (adapterKindKey=synology_diskstation)

25 resources total: 1 adapter instance + 1 SynologyWorld + 1 SynologyDiskstation + 1 SynologyStoragePool + 1 SynologyVolume + 1 SynologySsdCache + 7 SynologyDisk + 3 SynologyIscsiLun + 9 SynologyNfsExport.

### 2.1 synology_diskstation (Adapter Instance)

```
resource_id=1da1ec07-b23f-496f-83e2-ae56d5dc6f0d
adapterKindKey=synology_diskstation
resourceKindKey=synology_diskstation
name=storage.int.sentania.net
creationTime=2026-05-19T23:40:13Z
identifier: allowInsecure=true, host=storage.int.sentania.net, port=5001
resourceHealth=ORANGE
resourceHealthValue=50.0
resourceStatus=DATA_RECEIVING
resourceState=STARTED
```

**Properties:**
```
System Properties|host_collector_id=1.0
System Properties|resource_kind_subtype=GENERAL
System Properties|resource_kind_type=ADAPTER_INSTANCE
```

**Latest stats (2026-06-10T04:59:01Z):**
```
Instance Attributes|collected_metrics=136.0
Instance Attributes|collected_properties=0.0
Instance Attributes|collected_resources=25.0
Instance Attributes|elapsed_collect_time=7342.0
Instance Attributes|monitoring_resources=24.0
Instance Attributes|new_resources=0.0
Instance Attributes|no_data_receiving_resource_count=1.0
Instance Attributes|not_existing_resource_count=0.0
Instance Attributes|observations=136.0
Instance Attributes|property_value_changes=0.0
Instance Attributes|relationship_updates=0.0
Instance Attributes|reropted_events=0.0
System Attributes|alert_count_critical=0.0
System Attributes|alert_count_immediate=1.0
System Attributes|alert_count_info=0.0
System Attributes|alert_count_warning=0.0
System Attributes|all_metrics=12.0
System Attributes|availability=1.0
System Attributes|health=13.0
System Attributes|self_alert_count=1.0
System Attributes|total_alarms=1.0
System Attributes|total_alert_count=1.0
badge|compliance=-1.0
badge|efficiency=100.0
badge|health=50.0
badge|risk=0.0
```

---

### 2.2 SynologyWorld/Synology World

```
resource_id=2ca309ee-d49a-4c3e-971f-f6921b37d229
adapterKindKey=synology_diskstation
resourceKindKey=SynologyWorld
name=Synology World
creationTime=2026-05-19T23:40:24Z
identifier: world_id=synology_world
resourceHealth=GREY
resourceHealthValue=-1.0
resourceStatus=NO_DATA_RECEIVING
resourceState=STARTED
adapterInstanceId=1da1ec07-b23f-496f-83e2-ae56d5dc6f0d
```

**Properties:**
```
System Properties|resource_kind_subtype=GENERAL
System Properties|resource_kind_type=GENERAL
relationships|SynologyDiskstation_child=DS1520+ 20B0RYRXRF3KF
```

**Latest stats (2026-06-10T04:59:01Z):**
```
System Attributes|alert_count_critical=0.0
System Attributes|alert_count_immediate=0.0
System Attributes|alert_count_info=0.0
System Attributes|alert_count_warning=0.0
System Attributes|all_metrics=0.0
System Attributes|availability=-1.0
System Attributes|child_all_metrics=136.0
System Attributes|health=-1.0
System Attributes|self_alert_count=0.0
System Attributes|total_alarms=3.0
System Attributes|total_alert_count=0.0
badge|compliance=-1.0
badge|efficiency=-1.0
badge|health=-1.0
badge|risk=-1.0
```

**Note:** SynologyWorld is GREY / NO_DATA_RECEIVING in v1. No domain metrics are pushed onto this resource. This is the root cause of the adapter instance ORANGE health. v2 migration should evaluate whether to push aggregate metrics here.

---

### 2.3 SynologyDiskstation/DS1520+ 20B0RYRXRF3KF

```
resource_id=31e807a6-59d2-48a0-8ed3-c3ae4194b8a6
adapterKindKey=synology_diskstation
resourceKindKey=SynologyDiskstation
name=DS1520+ 20B0RYRXRF3KF
creationTime=2026-05-19T23:40:24Z
identifier: serial=20B0RYRXRF3KF
resourceHealth=GREEN
resourceHealthValue=100.0
resourceStatus=DATA_RECEIVING
resourceState=STARTED
adapterInstanceId=1da1ec07-b23f-496f-83e2-ae56d5dc6f0d
```

**Properties:**
```
Fan|fan_speed_mode=coolfan
Fan|fan_status=yes
NFS|nfs_enabled=true
NFS|nfs_v4_enabled=true
System Properties|resource_kind_subtype=GENERAL
System Properties|resource_kind_type=GENERAL
System|firmware_date=2026/01/29
System|firmware_version=DSM 7.3.2-86009 Update 1
System|hostname=(empty)
System|model=DS1520+
relationships|SynologyStoragePool_child=Storage Pool 1
relationships|SynologyWorld_parent=Synology World
```

**Latest stats (2026-06-10T04:58:56Z):**
```
CPU|cpu_load_15m=14.0
CPU|cpu_load_1m=13.0
CPU|cpu_load_5m=11.0
CPU|cpu_system_pct=0.0
CPU|cpu_total_load=0.0
CPU|cpu_user_pct=0.0
Memory|memory_available=214256.0
Memory|memory_total=20328576.0
Memory|memory_usage_pct=22.0
NFS|nfs_client_count=13.0
NFS|nfs_max_latency=447.0
NFS|nfs_read_ops=1.0
NFS|nfs_total_ops=4.0
NFS|nfs_write_ops=2.0
Network|net_rx_bytes=1651070.0
Network|net_tx_bytes=85286.0
System Attributes|alert_count_critical=0.0
System Attributes|alert_count_immediate=0.0
System Attributes|alert_count_info=0.0
System Attributes|alert_count_warning=0.0
System Attributes|all_metrics=18.0
System Attributes|availability=1.0
System Attributes|child_all_metrics=118.0
System Attributes|health=13.0
System Attributes|self_alert_count=0.0
System Attributes|total_alarms=3.0
System Attributes|total_alert_count=0.0
System|system_temp=39.0
System|uptime=9124662.0
badge|compliance=-1.0
badge|efficiency=100.0
badge|health=100.0
badge|risk=0.0
```

---

### 2.4 SynologyStoragePool/Storage Pool 1

```
resource_id=0301d20e-9ac2-4222-86c9-fe84ae5c25f6
adapterKindKey=synology_diskstation
resourceKindKey=SynologyStoragePool
name=Storage Pool 1
creationTime=2026-05-19T23:40:24Z
identifier: pool_id=reuse_1
resourceHealth=GREEN
resourceHealthValue=100.0
resourceStatus=DATA_RECEIVING
resourceState=STARTED
adapterInstanceId=1da1ec07-b23f-496f-83e2-ae56d5dc6f0d
```

**Properties:**
```
Configuration|device_type=raid_6
Configuration|pool_path=reuse_1
Configuration|raid_type=multiple
Configuration|status=normal
Properties|device_type=raid_6
Properties|pool_path=reuse_1
Properties|raid_type=multiple
Properties|status=normal
System Properties|resource_kind_subtype=GENERAL
System Properties|resource_kind_type=GENERAL
relationships|SynologyDisk_child=Cache device 1, Cache device 2, Drive 1, Drive 2, Drive 3, Drive 4, Drive 5
relationships|SynologyDiskstation_parent=DS1520+ 20B0RYRXRF3KF
relationships|SynologyVolume_child=Volume 1
```

**Latest stats (2026-06-10T04:58:58Z):**
```
Capacity|total_bytes=29987679764480.0
Capacity|usage_pct=100.0
Capacity|used_bytes=29987679764480.0
System Attributes|alert_count_critical=0.0
System Attributes|alert_count_immediate=0.0
System Attributes|alert_count_info=0.0
System Attributes|alert_count_warning=0.0
System Attributes|all_metrics=3.0
System Attributes|availability=1.0
System Attributes|child_all_metrics=115.0
System Attributes|health=13.0
System Attributes|self_alert_count=0.0
System Attributes|total_alarms=2.0
System Attributes|total_alert_count=0.0
badge|compliance=-1.0
badge|efficiency=100.0
badge|health=100.0
badge|risk=0.0
```

**Note:** `Capacity|usage_pct=100.0` and `used_bytes == total_bytes` — the storage pool is at 100% utilization at baseline. This is expected for a RAID-6 pool fully allocated to a volume. Not an error condition.

---

### 2.5 SynologyVolume/Volume 1

```
resource_id=f8759188-385c-4e53-b7d9-616639aa591c
adapterKindKey=synology_diskstation
resourceKindKey=SynologyVolume
name=Volume 1
creationTime=2026-05-19T23:40:24Z
identifier: volume_id=/volume1
resourceHealth=GREEN
resourceHealthValue=100.0
resourceStatus=DATA_RECEIVING
resourceState=STARTED
adapterInstanceId=1da1ec07-b23f-496f-83e2-ae56d5dc6f0d
```

**Properties:**
```
Cache|cache_enabled=true
Cache|cache_status=normal
Configuration|description=(empty)
Configuration|fs_type=btrfs
Configuration|status=normal
Configuration|volume_path=/volume1
Properties|description=(empty)
Properties|fs_type=btrfs
Properties|status=normal
Properties|volume_path=/volume1
System Properties|resource_kind_subtype=GENERAL
System Properties|resource_kind_type=GENERAL
relationships|SynologyIscsiLun_child=vcf-lab-mgmt01-cl01-lun0, vcf-lab-wld01-cl01, vcf-lab-wld02-cl01
relationships|SynologyNfsExport_child=ActiveBackupforBusiness, backup, public, vcf-lab-offline-depot, vcf9, vsphere_admin, web, wld01, wld02
relationships|SynologySsdCache_child=SSD Cache (Volume 1)
relationships|SynologyStoragePool_parent=Storage Pool 1
```

**Latest stats (2026-06-10T04:58:58Z):**
```
Cache|cache_read_hit_rate=84.0
Cache|cache_write_hit_rate=99.0
Capacity|free_bytes=0.0
Capacity|total_bytes=28788161249280.0
Capacity|usage_pct=100.0
IO|read_bytes=0.0
IO|read_iops=0.0
IO|utilization_pct=0.0
IO|write_bytes=1221120.0
IO|write_iops=81.0
System Attributes|alert_count_critical=0.0
System Attributes|alert_count_immediate=0.0
System Attributes|alert_count_info=0.0
System Attributes|alert_count_warning=0.0
System Attributes|all_metrics=10.0
System Attributes|availability=1.0
System Attributes|child_all_metrics=65.0
System Attributes|health=13.0
System Attributes|self_alert_count=0.0
System Attributes|total_alarms=2.0
System Attributes|total_alert_count=0.0
badge|compliance=-1.0
badge|efficiency=100.0
badge|health=100.0
badge|risk=0.0
```

**Note:** `Capacity|free_bytes=0.0` and `usage_pct=100.0` — Volume 1 is fully allocated at baseline. This is a thin-provisioning artifact (btrfs on fully-allocated RAID-6 pool).

---

### 2.6 SynologySsdCache/alloc_cache_1_1

```
resource_id=1cce52f7-4b98-4dca-b3b7-1bf779495486
adapterKindKey=synology_diskstation
resourceKindKey=SynologySsdCache
name=alloc_cache_1_1
creationTime=2026-05-19T23:40:24Z
identifier: cache_id=alloc_cache_1_1
resourceHealth=GREEN
resourceHealthValue=100.0
resourceStatus=DATA_RECEIVING
resourceState=STARTED
adapterInstanceId=1da1ec07-b23f-496f-83e2-ae56d5dc6f0d
```

**Properties:**
```
Configuration|device_type=raid_1
Configuration|mode=write
Configuration|mount_volume=volume_1
Configuration|skip_seq_io=true
Configuration|status=normal
Hardware|disk_count=2
Hardware|disk_failure_count=0
Hardware|disk_members=nvme0n1, nvme1n1
Hardware|total_capacity=1863.0 GB
Properties|device_type=raid_1
Properties|disk_count=2
Properties|disk_failure_count=0
Properties|disk_members=nvme0n1, nvme1n1
Properties|mode=write
Properties|mount_volume=volume_1
Properties|skip_seq_io=true
Properties|status=normal
Properties|total_capacity=1863.0 GB
System Properties|resource_kind_subtype=GENERAL
System Properties|resource_kind_type=GENERAL
relationships|SynologyDisk_child=Cache device 1, Cache device 2
relationships|SynologyVolume_parent=Volume 1
```

**Latest stats (2026-06-10T04:58:58Z):**
```
Capacity|occupied_bytes=283106934784.0
Capacity|total_bytes=2000381018112.0
HitRate|read_hit_rate=84.0
HitRate|write_hit_rate=99.0
System Attributes|alert_count_critical=0.0
System Attributes|alert_count_immediate=0.0
System Attributes|alert_count_info=0.0
System Attributes|alert_count_warning=0.0
System Attributes|all_metrics=4.0
System Attributes|availability=1.0
System Attributes|child_all_metrics=16.0
System Attributes|health=13.0
System Attributes|self_alert_count=0.0
System Attributes|total_alarms=1.0
System Attributes|total_alert_count=0.0
badge|compliance=-1.0
badge|efficiency=100.0
badge|health=100.0
badge|risk=0.0
```

---

### 2.7 SynologyDisk resources (7 total)

All created 2026-05-19T23:40:24Z, all GREEN, all adapterInstanceId=1da1ec07-b23f-496f-83e2-ae56d5dc6f0d.

**SynologyDisk/Cache device 1 (f55cf6ec-fa98-4c5b-9797-0faa1883116f)**
```
identifier: disk_id=nvme1n1
resourceHealth=GREEN
```
Properties:
```
Hardware|disk_code=(empty)
Hardware|disk_type=M.2 NVMe
Hardware|display_name=Cache device 1
Hardware|firmware=4B2QJXD7
Hardware|is_ssd=true
Hardware|model=Samsung SSD 990 PRO 2TB
Hardware|serial=S7KHNJ0X709296R
Hardware|size_bytes=2000398934016
Hardware|slot_id=1
Health|smart_status=normal
Properties|disk_code=(empty)
Properties|disk_type=M.2 NVMe
Properties|display_name=Cache device 1
Properties|firmware=4B2QJXD7
Properties|is_ssd=true
Properties|model=Samsung SSD 990 PRO 2TB
Properties|serial=S7KHNJ0X709296R
Properties|size_bytes=2000398934016
Properties|slot_id=1
Properties|vendor=Samsung
hardware|vendor=Samsung
relationships|SynologySsdCache_parent=SSD Cache (Volume 1)
relationships|SynologyStoragePool_parent=Storage Pool 1
```
Latest stats (2026-06-10T04:58:58Z):
```
Health|remain_life=0.0
Health|temperature=36.0
Health|unc_sectors=-1.0
IO|read_bytes=83285.0
IO|read_iops=8.0
IO|utilization_pct=0.0
IO|write_bytes=930645.0
IO|write_iops=76.0
```

**SynologyDisk/Cache device 2 (de93f8c1-28c7-43b3-8764-d1ad66ea6459)**
```
identifier: disk_id=nvme0n1
resourceHealth=GREEN
```
Properties:
```
Hardware|disk_type=M.2 NVMe
Hardware|firmware=4B2QJXD7
Hardware|is_ssd=true
Hardware|model=Samsung SSD 990 PRO 2TB
Hardware|serial=S7KHNJ0X709331H
Hardware|size_bytes=2000398934016
Hardware|slot_id=2
Health|smart_status=normal
Properties|vendor=Samsung
relationships|SynologySsdCache_parent=SSD Cache (Volume 1)
relationships|SynologyStoragePool_parent=Storage Pool 1
```
Latest stats (2026-06-10T04:58:58Z):
```
Health|remain_life=0.0
Health|temperature=38.0
Health|unc_sectors=-1.0
IO|read_bytes=70826.0
IO|read_iops=6.0
IO|utilization_pct=0.0
IO|write_bytes=930645.0
IO|write_iops=76.0
```

**SynologyDisk/Drive 1 (207772a5-c93b-4087-b6d4-5f71a0445984)**
```
identifier: disk_id=sata3
resourceHealth=GREEN
```
Properties:
```
Hardware|disk_code=ironwolf
Hardware|disk_type=SATA
Hardware|firmware=SC60
Hardware|is_ssd=false
Hardware|model=ST10000VN0004-1ZD101
Hardware|serial=ZA295DT8
Hardware|size_bytes=10000831348736
Hardware|slot_id=1
Health|smart_status=normal
Properties|vendor=Seagate
relationships|SynologyStoragePool_parent=Storage Pool 1
```
Latest stats (2026-06-10T04:58:58Z):
```
Health|remain_life=0.0
Health|temperature=35.0
Health|unc_sectors=6.0
IO|read_bytes=39253.0
IO|read_iops=6.0
IO|utilization_pct=0.0
IO|write_bytes=203136.0
IO|write_iops=21.0
```
**Note:** `Health|unc_sectors=6.0` — 6 uncorrectable sectors on Drive 1 at baseline. Not an alert threshold breach in v1. Track post-migration.

**SynologyDisk/Drive 2 (a450d20d-0d0b-4cb1-8241-19ac9bd9615f)**
```
identifier: disk_id=sata4
resourceHealth=GREEN
```
Properties: serial=ZA250Q5L, model=ST10000VN0004-1ZD101, slot_id=2
Latest stats (2026-06-10T04:58:58Z):
```
Health|temperature=35.0
Health|unc_sectors=16.0
IO|read_bytes=44544.0
IO|read_iops=6.0
IO|utilization_pct=0.0
IO|write_bytes=195456.0
IO|write_iops=16.0
```
**Note:** `Health|unc_sectors=16.0` — 16 uncorrectable sectors on Drive 2 at baseline.

**SynologyDisk/Drive 3 (3089f48b-2187-465c-95a2-82505c3ab768)**
```
identifier: disk_id=sata5
resourceHealth=GREEN
```
Properties: serial=ZPW06GXP, model=ST10000VN0008-2JJ101, slot_id=3
Latest stats (2026-06-10T04:58:58Z):
```
Health|temperature=37.0
Health|unc_sectors=0.0
IO|read_bytes=42325.0
IO|read_iops=6.0
IO|utilization_pct=0.0
IO|write_bytes=195626.0
IO|write_iops=21.0
```

**SynologyDisk/Drive 4 (d1713951-ce81-444a-aef5-de1534d73e3d)**
```
identifier: disk_id=sata1
resourceHealth=GREEN
```
Properties: serial=ZA250QA8, model=ST10000VN0004-1ZD101, slot_id=4
Latest stats (2026-06-10T04:58:58Z):
```
Health|temperature=36.0
Health|unc_sectors=0.0
IO|read_bytes=54954.0
IO|read_iops=6.0
IO|utilization_pct=0.0
IO|write_bytes=183338.0
IO|write_iops=20.0
```

**SynologyDisk/Drive 5 (6c278b7a-79b0-4f8b-99f4-b36dc3168591)**
```
identifier: disk_id=sata2
resourceHealth=GREEN
```
Properties: serial=ZA20TM9L, model=ST10000VN0004-1ZD101, slot_id=5
Latest stats (2026-06-10T04:58:58Z):
```
Health|temperature=35.0
Health|unc_sectors=0.0
IO|read_bytes=42496.0
IO|read_iops=6.0
IO|utilization_pct=0.0
IO|write_bytes=195456.0
IO|write_iops=20.0
```

---

### 2.8 SynologyIscsiLun resources (3 total)

All created 2026-05-19T23:40:24Z, all GREEN, all adapterInstanceId=1da1ec07-b23f-496f-83e2-ae56d5dc6f0d.

**SynologyIscsiLun/vcf-lab-mgmt01-cl01-lun0 (cea520ac-eee0-4ee7-9415-9403d96e9509)**
```
identifier: lun_uuid=dc24a03c-db92-46e0-9b19-97574fea98d7
```
Properties:
```
Configuration|location=/volume1
Configuration|name=vcf-lab-mgmt01-cl01-lun0
Configuration|network_portals=(empty)
Configuration|size_bytes=8796093022208
Configuration|target_enabled=(empty)
Configuration|target_iqn=(empty)
Configuration|type=BLUN
relationships|SynologyVolume_parent=Volume 1
```
Latest stats (2026-06-10T04:59:00Z): IO|read_iops=0.0, IO|read_latency=0.0, IO|read_throughput=0.0, IO|write_iops=0.0, IO|write_latency=0.0, IO|write_throughput=0.0

**Note:** This LUN has no target IQN/portals configured — likely a stub LUN not in active use.

**SynologyIscsiLun/vcf-lab-wld01-cl01 (5fec99a7-5977-4e24-ae15-05d8efd9a307)**
```
identifier: lun_uuid=d023e190-8940-485a-8bf1-47f41ae0c0a5
```
Properties:
```
Configuration|location=/volume1
Configuration|name=vcf-lab-wld01-cl01
Configuration|network_portals={interface_name=all, ip=, port=3260}
Configuration|size_bytes=8589934592000
Configuration|target_enabled=true
Configuration|target_iqn=iqn.2000-01.com.synology:storage.vcf-lab-wld01-cl01.cfb45402d27
Configuration|type=BLUN
relationships|Datastore_parent=vcf-lab-wld01-cl01-iscsi
relationships|SynologyVolume_parent=Volume 1
```
Latest stats (2026-06-10T04:59:00Z):
```
IO|read_iops=4.0
IO|read_latency=0.0
IO|read_throughput=20277.0
IO|write_iops=1.0
IO|write_latency=0.0
IO|write_throughput=25105.0
```

**SynologyIscsiLun/vcf-lab-wld02-cl01 (a1b93e3f-0af3-4236-91d0-d851caf42d23)**
```
identifier: lun_uuid=63ae9438-358e-4d9e-86dd-17e2e67f6c90
```
Properties: target_iqn=(empty), target_enabled=(empty) — stub LUN not in active use.
Latest stats: all IO metrics 0.0.

---

### 2.9 SynologyNfsExport resources (9 total)

All created 2026-05-19T23:40:24Z except vcf-lab-offline-depot (2026-05-29T15:15:22Z).
All GREEN. All adapterInstanceId=1da1ec07-b23f-496f-83e2-ae56d5dc6f0d.
All share metric schema: Capacity|quota_usage_pct, Capacity|size_used_mib, Clients|active_client_count.

| Name | resource_id | share_name | quota_mib | quota_usage_pct | size_used_mib | active_clients | timestamp |
|---|---|---|---|---|---|---|---|
| ActiveBackupforBusiness | 34711e22-037e-4554-a04a-7c6909b79210 | ActiveBackupforBusiness | 0 (no limit) | 0.0 | 5402467.0 | 0 | 2026-06-10T04:59:00Z |
| backup | 8cc4d020-b64d-4c5c-87e1-62c52f4ff8ec | backup | 0 (no limit) | 0.0 | 1160541.25 | 0 | 2026-06-10T04:59:00Z |
| public | 70d9dec2-ce0b-4bd2-bf69-885e816cbf85 | public | 256000 | 35.676 | 91331.22 | 0 | 2026-06-10T04:59:00Z |
| vcf-lab-offline-depot | 35ec7eb4-0bea-4861-8fe8-bc0764dea81b | vcf-lab-offline-depot | 1280000 | 21.281 | 272398.19 | 0 | 2026-06-10T04:59:00Z |
| vcf9 | 75923bb3-9cd1-495d-90cb-fc6c17832774 | vcf9 | 3145728 | 2.415 | 75965.34 | 5 | 2026-06-10T04:59:00Z |
| vsphere_admin | fba09438-942a-453d-9b41-36501d834eab | vsphere_admin | 0 (no limit) | 0.0 | 39464.75 | 0 | 2026-06-10T04:59:00Z |
| web | 9f3cf6ef-eb55-4fae-b4a1-ca44f81eb967 | web | 1280000 | 23.305 | 298308.03 | 0 | 2026-06-10T04:59:00Z |
| wld01 | b136e1a0-0315-40da-8605-6aa1b9aaa165 | wld01 | 102400 | 6.036 | 6181.02 | 2 | 2026-06-10T04:59:00Z |
| wld02 | 7086073b-3878-41e0-8fc4-101acbc20b30 | wld02 | 102400 | 0.000240 | 0.246 | 0 | 2026-06-10T04:59:00Z |

**Active NFS relationships (from properties):**
- `vcf9` → Datastore: vcf-lab-mgmt01-nfs
- `vcf-lab-wld01-cl01-iscsi` ← iSCSI LUN (not NFS; wld01 NFS → vcf-lab-nfs-wld01)
- `wld01` → Datastore: vcf-lab-nfs-wld01

**Note on vcf-lab-offline-depot:** Created 2026-05-29, newer than the other NFS exports (2026-05-19). No `Properties|` group present (only `Configuration|`) for this resource — v1 may have a code path difference for post-initial-discovery resources. No `relationships|SynologyVolume_parent` with the `Properties|` namespace either.

---

## 3. Stitched Properties on Foreign Resources

No Synology stitched properties or metrics found on any VMWARE/HostSystem resource (all 8 ESXi hosts checked). No Synology-namespaced statkeys found on any Datastore resource (all 8 checked).

CONFIRMED: Synology v1 does NOT stitch data onto foreign resource kinds. The `relationships|Datastore_parent` property on iSCSI LUN and NFS Export resources is informational (a string property), not an ARIA_OPS-style metric stitch.

---

## 4. Collection Cadence

- Monitoring interval: 5 minutes
- Last collection timestamp observed: 2026-06-10T04:59:01Z
- Elapsed collect time: 7342ms (approximately 7.3 seconds per cycle)
- `no_data_receiving_resource_count=1` — SynologyWorld only; all 24 domain objects are DATA_RECEIVING

---

## 5. Health Notes and Post-Migration Acceptance Criteria

| Condition | v1 State | Post-v2 Acceptance |
|---|---|---|
| Adapter instance overall health | ORANGE (SynologyWorld no-data) | GREEN preferred; ORANGE acceptable if same root cause |
| All 24 domain resources health | GREEN | All GREEN |
| numberOfResourcesCollected | 25 | 25 or more (no resource loss) |
| numberOfMetricsCollected | 136 | 136 or more |
| Drive 1 unc_sectors | 6.0 | Same value or higher (hardware, not a migration artifact) |
| Drive 2 unc_sectors | 16.0 | Same value or higher |
| Storage pool usage_pct | 100.0 | 100.0 (hardware state, not migration artifact) |
| Volume free_bytes | 0.0 | 0.0 (hardware state) |
| Stitching onto foreign resources | None | None (Synology v1 has no stitching) |
