# MPB Synology NAS — Live Recon (Primary Lab, 2026-04-22)

Source: `vcf-lab-operations.int.sentania.net` (read-only, `claude` user).
All data from `GET /suite-api/api/...` endpoints. No writes performed.

---

## 1. Adapter Kind Inventory

| Field | Value |
|---|---|
| **Adapter kind key** | `mpb_synology_nas` |
| **Display name** | Synology NAS |
| **adapterKindType** | GENERAL |
| **describeVersion** | 1 |
| **MP solution id** | `Synology NAS` |
| **MP version** | `1.0.0.1` |
| **MP vendor** | Management Pack Builder |
| **MP description** | (matches our `synology_nas.yaml` description field exactly) |

Raw endpoint: `GET /suite-api/api/adapterkinds/mpb_synology_nas`
Solutions endpoint: `GET /suite-api/api/solutions` → id=`Synology NAS`

### Resource Kind Keys Registered

| Key | Display Name | Kind Type | Sub-Type |
|---|---|---|---|
| `mpb_synology_nas_disks` | Disks | GENERAL | NONE |
| `mpb_synology_nas_iscsi_lun` | iSCSI LUN | GENERAL | NONE |
| `mpb_synology_nas_storage_pool` | Storage Pool | GENERAL | NONE |
| `mpb_synology_nas_synology_diskstation` | Synology Diskstation | GENERAL | NONE |
| `mpb_synology_nas` | Synology NAS Adapter Instance | ADAPTER_INSTANCE | NONE |
| `mpb_synology_nas_relatives` | Synology NAS Relatives | TAG | NONE |
| `mpb_synology_nas_world` | Synology NAS World | GROUP | GROUP_WORLD |
| `mpb_synology_nas_volume` | Volume | GENERAL | NONE |

Note: `mpb_synology_nas_relatives` (TAG kind) and `mpb_synology_nas_world` (GROUP_WORLD) are MPB-generated scaffolding — zero resources exist for `relatives`.

---

## 2. Adapter Instance Config Fields (Add Adapter Schema)

Resource kind `mpb_synology_nas` (ADAPTER_INSTANCE) exposes these identifiers — this is what the Add Adapter form renders:

| Identifier Name | dataType | isPartOfUniqueness | Live Value |
|---|---|---|---|
| `mpb_hostname` | STRING | **true** | `storage.int.sentania.net` |
| `mpb_concurrent_requests` | STRING | false | `2` |
| `mpb_connection_timeout` | STRING | false | `30` |
| `mpb_max_retries` | STRING | false | `2` |
| `mpb_min_event_severity` | STRING | false | `Warning` |
| `mpb_port` | STRING | false | `5001` |
| `mpb_ssl_config` | STRING | false | `No Verify` |
| `support_autodiscovery` | STRING | false | `True` |

All fields are STRING dataType (MPB emits everything as STRING). `mpb_hostname` is the sole uniqueness key.
Credential fields (`username`/`passwd`) are stored separately under `credentialInstanceId: 7ef3a95e-...` and do not appear in the resourceIdentifiers list.

**Diff vs. factory pak (devel):** The broken devel form showed labels like "iSCSI LUN / UUID / Name / Provisioned Size / Location / LUN Type / Disks" — those are resource-kind identifiers from child object types that were leaking into the adapter instance form, indicating the factory pak's describe.xml had incorrect resourceKindType or misrouted identifiers. The MPB-generated form is clean (8 config fields only).

Raw endpoint: `GET /suite-api/api/adapters?adapterKindKey=mpb_synology_nas`

---

## 3. Resource Kind Schemas

### 3a. Disks (`mpb_synology_nas_disks`)

**Identifiers (uniqueness):**

| Name | dataType | isPartOfUniqueness |
|---|---|---|
| `adapter_instance_id` | STRING | true |
| `serial` | STRING | true |

**Metrics (non-system, non-badge):**

| Key | Label | Unit |
|---|---|---|
| `slot_id` | Slot ID | — |
| `size_total` | Size Total | — |

**Properties:**

| Key | Label | dataType |
|---|---|---|
| `device` | Device | STRING |
| `firm` | Firm | STRING |
| `model` | Model | STRING |
| `name` | Name | STRING |
| `serial` | Serial | STRING |
| `smart_status` | Smart Status | STRING |
| `used_by` | Used By | STRING |
| `vendor` | Vendor | STRING |
| `wcache_force_off` | Wcache Force Off | STRING |

### 3b. iSCSI LUN (`mpb_synology_nas_iscsi_lun`)

**Identifiers:**

| Name | dataType | isPartOfUniqueness |
|---|---|---|
| `adapter_instance_id` | STRING | true |
| `uuid` | STRING | true |

**Metrics:**

| Key | Label | Unit |
|---|---|---|
| `provisioned_size` | Provisioned Size | bytes |

**Properties:**

| Key | Label | dataType |
|---|---|---|
| `uuid` | UUID | STRING |
| `name` | Name | STRING |
| `location` | Location | STRING |
| `lun_type` | LUN Type | STRING |

### 3c. Storage Pool (`mpb_synology_nas_storage_pool`)

**Identifiers:**

| Name | dataType | isPartOfUniqueness |
|---|---|---|
| `adapter_instance_id` | STRING | true |
| `id` | STRING | true |
| `pool_path` | STRING | true |

**Metrics:**

| Key | Label | Unit |
|---|---|---|
| `total` | Total | — |
| `used` | Used | — |

**Properties:**

| Key | Label | dataType |
|---|---|---|
| `device_type` | Device Type | STRING |
| `id` | ID | STRING |
| `num_id` | Num ID | — |
| `pool_path` | Pool Path | STRING |

### 3d. Synology Diskstation (`mpb_synology_nas_synology_diskstation`)

**Identifiers:**

| Name | dataType | isPartOfUniqueness |
|---|---|---|
| `adapter_instance_id` | STRING | true |
| `serial` | STRING | true |

**Metrics (18 total):**

| Key | Label |
|---|---|
| `avail_real` | Avail Real |
| `avail_swap` | Avail Swap |
| `buffer` | Buffer |
| `cached` | Cached |
| `memory_size` | Memory Size |
| `real_usage` | Real Usage |
| `si_disk` | Si Disk |
| `so_disk` | So Disk |
| `swap_usage` | Swap Usage |
| `total_real` | Total Real |
| `total_swap` | Total Swap |
| `1min_load` | 1min Load |
| `5min_load` | 5min Load |
| `15min_load` | 15min Load |
| `other_load` | Other Load |
| `system_load` | System Load |
| `user_load` | User Load |
| `sys_temp` | Sys Temp |

**Properties (15 total):**

| Key | Label | dataType |
|---|---|---|
| `cpu_clock_speed` | CPU Clock Speed | — |
| `cpu_cores` | CPU Cores | — |
| `cpu_family` | CPU Family | STRING |
| `cpu_series` | CPU Series | STRING |
| `cpu_vendor` | CPU Vendor | STRING |
| `enabled_ntp` | Enabled Ntp | STRING |
| `firmware_date` | Firmware Date | STRING |
| `firmware_ver` | Firmware Ver | STRING |
| `hostname` | Hostname | STRING |
| `model` | Model | STRING |
| `ntp_server` | Ntp Server | STRING |
| `ram_size` | RAM Size | — |
| `serial` | Serial | STRING |
| `time_zone_desc` | Time Zone Desc | STRING |
| `up_time` | Up Time | STRING |

### 3e. Volume (`mpb_synology_nas_volume`)

**Identifiers:**

| Name | dataType | isPartOfUniqueness |
|---|---|---|
| `adapter_instance_id` | STRING | true |
| `volume_id` | STRING | true |
| `volume_path` | STRING | true |

**Metrics:**

| Key | Label | Unit |
|---|---|---|
| `size_free_byte` | Size Free Byte | — |
| `size_total_byte` | Size Total Byte | — |

**Properties:**

| Key | Label | dataType |
|---|---|---|
| `crashed` | Crashed | STRING |
| `deduped` | Deduped | STRING |
| `description` | Description | STRING |
| `display_name` | Display Name | STRING |
| `fs_type` | Fs Type | STRING |
| `is_encrypted` | Is Encrypted | STRING |
| `pool_path` | Pool Path | STRING |
| `raid_type` | RAID Type | STRING |
| `readonly` | Readonly | STRING |
| `status` | Status | STRING |
| `volume_id` | Volume ID | — |
| `volume_path` | Volume Path | STRING |

### 3f. Adapter Instance (`mpb_synology_nas`) — Summary Metrics

MPB auto-generates count summary metrics on the adapter instance:

| Key | Label |
|---|---|
| `summary\|mpb_synology_nas_disks_count` | Disks Count |
| `summary\|mpb_synology_nas_iscsi_lun_count` | iSCSI LUN Count |
| `summary\|mpb_synology_nas_storage_pool_count` | Storage Pool Count |
| `summary\|mpb_synology_nas_synology_diskstation_count` | Synology Diskstation Count |
| `summary\|mpb_synology_nas_volume_count` | Volume Count |

---

## 4. Observed Resources and Relationships

### Resource Counts (live data)

| Kind | Count | Sample Names |
|---|---|---|
| `mpb_synology_nas_world` | 1 | Synology NAS World |
| `mpb_synology_nas` (adapter instance) | 1 | storage |
| `mpb_synology_nas_synology_diskstation` | 1 | storage |
| `mpb_synology_nas_storage_pool` | 1 | reuse_1 |
| `mpb_synology_nas_volume` | 1 | Volume 1 |
| `mpb_synology_nas_disks` | 7 | Drive 1-5, Cache device 1-2 |
| `mpb_synology_nas_iscsi_lun` | 3 | vcf-lab-wld01-cl01, vcf-lab-wld02-cl01, vcf-lab-mgmt01-cl01-lun0 |
| `mpb_synology_nas_relatives` | 0 | — |

**Total resources collected:** 14 (matches `numberOfResourcesCollected: 14` in adapter instance).

### Relationship Topology

```
Universe
  └── Synology NAS World [mpb_synology_nas_world]
        └── storage [mpb_synology_nas]  ← adapter instance
              ├── storage [mpb_synology_nas_synology_diskstation]
              ├── reuse_1 [mpb_synology_nas_storage_pool]
              │     ├── Volume 1 [mpb_synology_nas_volume]
              │     │     ├── vcf-lab-wld01-cl01 [mpb_synology_nas_iscsi_lun]
              │     │     ├── vcf-lab-wld02-cl01 [mpb_synology_nas_iscsi_lun]
              │     │     └── vcf-lab-mgmt01-cl01-lun0 [mpb_synology_nas_iscsi_lun]
              │     ├── Drive 1 [mpb_synology_nas_disks]
              │     ├── Drive 2 [mpb_synology_nas_disks]
              │     ├── Drive 3 [mpb_synology_nas_disks]
              │     ├── Drive 4 [mpb_synology_nas_disks]
              │     └── Drive 5 [mpb_synology_nas_disks]
              ├── Cache device 1 [mpb_synology_nas_disks]  ← adapter-instance only, no pool parent
              └── Cache device 2 [mpb_synology_nas_disks]  ← adapter-instance only, no pool parent
```

**Dual-parent edges observed:**
- Volume 1 has parents: adapter instance AND storage pool (expected dual-parent from peer design).
- LUNs have parents: Volume 1 AND adapter instance.
- Drives 1-5 have parents: storage pool AND adapter instance.
- Cache devices have parent: adapter instance ONLY (not pool — correct, NVMe cache is not in a volume pool).

**Notable:** Diskstation has NO children — it is a sidecar/leaf peer under the adapter instance. Consistent with Strategy C design decision.

---

## 5. Adapter Instance Config Values (Live)

Adapter instance ID: `59b93005-e631-47da-9ac9-b78787d2df55`
Name: `storage`
Credential instance ID: `7ef3a95e-6908-45d1-a347-3823b2b98b85` (username/passwd stored separately)

| Config Key | Live Value |
|---|---|
| `mpb_hostname` | `storage.int.sentania.net` |
| `mpb_port` | `5001` |
| `mpb_ssl_config` | `No Verify` |
| `mpb_concurrent_requests` | `2` |
| `mpb_connection_timeout` | `30` |
| `mpb_max_retries` | `2` |
| `mpb_min_event_severity` | `Warning` |
| `support_autodiscovery` | `True` |

`monitoringInterval: 5` (minutes). `lastCollected` and `lastHeartbeat` both recent (active collection confirmed).

---

## 6. Versioning Metadata

| Field | Value |
|---|---|
| **describeVersion** | 1 |
| **MP solution version** | `1.0.0.1` |
| **MP vendor** | Management Pack Builder |
| **MP solution ID** | `Synology NAS` |
| **adapter kind key** | `mpb_synology_nas` |

The `describeVersion: 1` is MPB's initial publish. No resource kind version numbers are exposed in the suite-api resourcekinds endpoint beyond the adapter kind level.

---

## Diffs Worth Investigating

### 1. Factory YAML uses `max_concurrent: 15`; MPB live uses `mpb_concurrent_requests: 2`

Our `synology_nas.yaml` `source.max_concurrent: 15`. The working MPB config stored `mpb_concurrent_requests: 2`. This is a config value difference only, not a schema problem — but the key name diverges: `max_concurrent` (factory) vs `mpb_concurrent_requests` (MPB). The factory pak must emit `mpb_concurrent_requests` (with the `mpb_` prefix) to match what MPB generates.

### 2. Factory YAML identifier names lack `mpb_` prefix; MPB emit has them

Factory `synology_nas.yaml` `source` keys (`hostname`, `port`, `ssl`, `max_concurrent`, `max_retries`) become MPB describe identifiers as `mpb_hostname`, `mpb_port`, `mpb_ssl_config`, `mpb_concurrent_requests`, `mpb_max_retries`. The `mpb_` namespace prefix is MPB's rendering convention. Factory pak must match.

### 3. Factory YAML has `ssl: NO_VERIFY`; MPB live shows `mpb_ssl_config: "No Verify"`

The value transformation: `NO_VERIFY` → `"No Verify"` (MPB display-formats it). Our factory renderer must emit the display string `No Verify` as the enum label for the `mpb_ssl_config` identifier, not the internal enum key.

### 4. All child resource kinds have `adapter_instance_id` as a uniqueness identifier

Factory YAML identifiers for each object type do NOT include `adapter_instance_id` — MPB adds it automatically as a compound uniqueness key on every non-world resource kind. The factory pak's describe.xml must include `adapter_instance_id` as an `isPartOfUniqueness=true` identifier on every child resource kind, otherwise deduplication breaks in multi-instance scenarios.

### 5. Cache devices are orphaned from pools — data confirms field_match logic is correct

`used_by` on cache devices does not match any pool `id` (cache devices sit outside the pool). This means our `parent: storage_pool / child: disks / parent_expression: id / child_expression: used_by` field_match is behaving exactly correctly in MPB — drives in the pool match, cache devices don't match and fall back to adapter-instance-only parentage. No factory YAML change needed.

### 6. `is_world: true` on Diskstation vs. observed topology

Factory YAML marks `synology_diskstation` as `is_world: true`. In the live MPB deployment, Diskstation is **not** the world root — `mpb_synology_nas_world` (GROUP_WORLD kind) plays that role, and Diskstation is a peer child of the adapter instance. The factory `is_world: true` flag may be generating incorrect describe.xml that elevates Diskstation to world-root position, which would explain the adapter form pollution seen on devel (child identifiers leaking into the Add Adapter UI — if Diskstation's describe.xml position is wrong, its identifiers get hoisted).

### 7. `volume_id` identifier type in live = STRING; factory YAML says NUMBER

Live resourceIdentifierTypes: `volume_id` dataType=STRING. Factory `synology_nas.yaml` line 626: `type: NUMBER`. This mismatch would cause identifier comparison failures — the factory pak must emit `volume_id` as STRING.

---

## Raw API References

All GET, read-only, primary lab:

- Adapter kind detail: `GET /suite-api/api/adapterkinds/mpb_synology_nas`
- Resource kinds: `GET /suite-api/api/adapterkinds/mpb_synology_nas/resourcekinds`
- Per-kind statkeys: `GET /suite-api/api/adapterkinds/mpb_synology_nas/resourcekinds/{rk}/statkeys`
- Per-kind properties: `GET /suite-api/api/adapterkinds/mpb_synology_nas/resourcekinds/{rk}/properties`
- Adapter instances: `GET /suite-api/api/adapters?adapterKindKey=mpb_synology_nas`
- Resources by kind: `POST /suite-api/api/resources/query` body `{"resourceKind":["<rk>"],"adapterKind":["mpb_synology_nas"]}`
- Relationships: `GET /suite-api/api/resources/{id}/relationships?relationshipType=CHILD|PARENT`
- Solutions: `GET /suite-api/api/solutions` (filtered for `id: "Synology NAS"`)
