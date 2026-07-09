# Synology <-> VCF Operations Stitching

How a Synology DiskStation MP joins its objects to existing VMware
objects in VCF Operations (HostSystem, Datastore, VirtualMachine).
Designed to support `type: ARIA_OPS` object kinds — the adapter
emits a stitch key that the VCF Ops side already carries on the
target resource.

See also:
- `context/api-maps/synology-iscsi.md` — Synology iSCSI LUN map
- `context/api-maps/synology-storage.md` — Synology volume / share map
- `context/api-maps/synology-overview.md` — Synology object model
- `context/mpb_pak_structural_reference.md` — ARIA_OPS object rules
  in MPB-built paks
- `context/api_pattern_catalog.md` — "vSphere REST" entry, which
  documents the canonical VMware ARIA_OPS stitch targets

## Provenance

- **Authored by:** api-cartographer
- **Target instance (Synology):** `storage.int.sentania.net:5001` —
  DS1520+ on DSM 7.3.2-86009 Update 1
- **Target instance (VCF Ops):** `vcf-lab-operations.int.sentania.net`
  — Suite API (profile `prod`)
- **Last updated:** 2026-05-18
- **Update history:**
  - 2026-05-18 — Initial mapping. Live evidence collected from both
    sides: Synology `SYNO.Core.ISCSI.LUN list`,
    `SYNO.Core.ISCSI.Target list`, `SYNO.Core.Share list`,
    `SYNO.Core.FileServ.NFS get`,
    `SYNO.Core.FileServ.NFS.SharePrivilege load` per share,
    `SYNO.Core.Network.Interface list`; VCF Ops `/api/resources`
    (HostSystem, Datastore), `/api/resources/{id}`,
    `/api/resources/{id}/properties`,
    `/api/resources/{id}/relationships/parents`.
- **Evidence basis:** live API calls against both targets, captured
  this session (2026-05-18). Algorithm for NAA encoding verified by
  matching two distinct LUN UUIDs to their actual NAA strings on
  ESXi as seen by VCF Ops.

## Executive summary

| Question | Answer | Confidence |
|---|---|---|
| Can we stitch Synology iSCSI LUNs to VMware Datastores? | **Yes** — Synology `lun.uuid` deterministically maps to ESXi NAA, and the NAA appears verbatim in VCF Ops Datastore `DataStrorePath` identifier. | **High — verified end-to-end against 2 live LUN/Datastore pairs.** |
| Can we stitch Synology NFS exports to VMware Datastores? | **Yes** — Synology NFS export path `<nas_ip>/<vol_path>/<share>` appears verbatim in VCF Ops Datastore `DataStrorePath` identifier for NFS datastores. | **High — verified against 3 live NFS datastores.** |
| Can we also stitch to HostSystem / VM directly? | **No, and we shouldn't try.** Once stitched onto a Datastore, the existing VMware adapter relationship graph carries `Datastore → HostSystem` (mount) and `Datastore → VirtualMachine` (storage placement) for free. | **High — observed on live graph.** |
| Are there Synology-side fields that map to ESXi NAA without the UUID transform? | **No** — `vpd_unit_sn == lun.uuid` verbatim; the NAA-formatting is performed by the iSCSI target stack inside DSM, not exposed as a flat field. The MP adapter must compute the NAA from the UUID. | **High** |
| Does the join recipe rely on a single VCF Ops identifier? | **Yes — `DataStrorePath` resource identifier on the VMWARE Datastore kind, value-typed string.** This is the same identifier `vsphere_storage_paths.yaml` doesn't use today (that MP uses `VMEntityObjectID`). | **High** |

**Recommended ARIA_OPS bind:**
- `aria_ops.resource_kind: Datastore`
- `aria_ops.bind_metric: DataStrorePath`
- `aria_ops.adapter_kind: VMWARE`

**TOOLSET GAP — none.** Stitching is viable via existing factory
grammar (`type: ARIA_OPS`, `aria_ops.bind_metric`,
`metricSets[].stitch_match_field`). No new framework features
required.

---

## 1. iSCSI Stitching

### 1.1 Synology side — identifier surface for an iSCSI LUN

From `SYNO.Core.ISCSI.LUN list` (full verbatim entry,
2026-05-18 capture):

```json
{
  "block_size": 512,
  "create_from": "",
  "description": "",
  "dev_attribs": [ /* SCSI emulation flags */ ],
  "dev_attribs_bitmap": 31,
  "dev_config": "",
  "dev_qos": { "dev_limit": 0, "dev_reservation": 0,
               "dev_weight": 0, "iops_enable": 0 },
  "direct_io_pattern": 0,
  "location": "/volume1",
  "lun_id": 1,
  "max_snapshot_count": 256,
  "name": "vcf-lab-wld02-cl01",
  "restored_time": 1735011491,
  "size": 8589934592000,
  "type": 263,
  "type_str": "BLUN",
  "uuid": "63ae9438-358e-4d9e-86dd-17e2e67f6c90",
  "vpd_unit_sn": "63ae9438-358e-4d9e-86dd-17e2e67f6c90"
}
```

From `SYNO.Core.ISCSI.Target list` (verbatim, 2026-05-18):

```json
{
  "auth_type": 0,
  "has_data_checksum": false,
  "has_header_checksum": false,
  "iqn": "iqn.2000-01.com.synology:storage.vcf-lab-wld01-cl02.cfb45402d27",
  "is_default_target": false,
  "is_enabled": true,
  "mapping_index": -1,
  "max_recv_seg_bytes": 262144,
  "max_send_seg_bytes": 262144,
  "max_sessions": 0,
  "mutual_password": "",
  "mutual_user": "",
  "name": "vcf-lab-wld01-cl02",
  "network_portals": [
    { "interface_name": "all", "ip": "", "port": 3260 }
  ],
  "password": "",
  "target_id": 4,
  "user": ""
}
```

#### Identifier inventory (LUN side) `[observed 2026-05-18]`

| Synology field | Value example | Stable? | Stitch-relevant? |
|---|---|---|---|
| `uuid` | `d023e190-8940-485a-8bf1-47f41ae0c0a5` | yes (assigned at LUN create, persistent across reboots) | **YES — this is the source for the NAA** |
| `vpd_unit_sn` | `d023e190-8940-485a-8bf1-47f41ae0c0a5` | yes (mirrors `uuid` on this DSM version) | redundant with `uuid` |
| `name` | `vcf-lab-wld01-cl01` | yes, but admin-mutable | no — admin can rename |
| `lun_id` | `1`, `2`, `4` | yes within DSM but only meaningful per-target | no |
| `location` | `/volume1` | yes | no — too coarse |

#### Identifier inventory (Target side) `[observed 2026-05-18]`

| Synology field | Value example | Stitch-relevant? |
|---|---|---|
| `iqn` | `iqn.2000-01.com.synology:storage.vcf-lab-wld01-cl01.cfb45402d27` | Informational — appears in ESXi `iSCSI Software Adapter` static-discovery config. Not present on Datastore identifiers. |
| `name` | `vcf-lab-wld01-cl01` | LUN ↔ Target naming convention only (no enforced binding API) |
| `network_portals[].ip` | `""` (means "all NICs") | Useful for verifying reachability, not stitching |
| `target_id` | numeric | not stable across DSM versions |

**Field NOT exposed on either response:**
- LUN serial number distinct from `uuid` — there is none; serial = uuid.
- SCSI VPD page 0x83 device identifier string in NAA form — not
  exposed by DSM REST. Must be **computed** by the adapter (see
  §1.3 transform).
- LUN → Target mapping — not present in `list` responses on this
  DSM. A `map_target` method exists on `SYNO.Core.ISCSI.LUN`
  but requires write-style params and is not needed for stitching
  (the LUN's NAA is independent of which targets expose it).

### 1.2 VCF Ops side — identifier surface for a VMFS-on-iSCSI Datastore

VCF Operations exposes Datastore identity in two places:

**A. `resourceIdentifiers` on `GET /api/resources/{id}`** — the
canonical, stable, ARIA_OPS-bindable identifier set.

```json
{
  "resourceKey": {
    "name": "vcf-lab-wld01-cl01-iscsi",
    "adapterKindKey": "VMWARE",
    "resourceKindKey": "Datastore",
    "resourceIdentifiers": [
      {
        "identifierType": {
          "name": "DataStrorePath",
          "dataType": "STRING",
          "isPartOfUniqueness": false
        },
        "value": "VMFS:|naa.6001405d023e190d8940d485ad8bf1d4|"
      },
      {
        "identifierType": { "name": "VMEntityName", "isPartOfUniqueness": false },
        "value": "vcf-lab-wld01-cl01-iscsi"
      },
      {
        "identifierType": { "name": "VMEntityObjectID", "isPartOfUniqueness": true },
        "value": "datastore-25"
      },
      {
        "identifierType": { "name": "VMEntityVCID", "isPartOfUniqueness": true },
        "value": "6b90a7cf-70cb-40a0-9cbf-f96a44fdcc03"
      }
    ]
  }
}
```

`[observed 2026-05-18 — actual capture of live datastore]`

Note: the identifier name is literally **`DataStrorePath`** with
the typo (missing `S` → `Stror`). This is upstream VMware spelling
that VCF Ops inherits. Use the spelling exactly as VCF Ops emits
it.

**B. `property` list on `GET /api/resources/{id}/properties`** —
22 properties; **none** contain the NAA, the VMFS extent disk
name, or `info.vmfs.uuid` directly. The closest is:
- `summary|path = 'ds:///vmfs/volumes/686fce90-4ac211bf-247d-005056806dbf/'`
  — this is the VMFS UUID, not the LUN NAA.
- `summary|type = 'VMFS'`

The LUN NAA is **not** surfaced in the property tree. It only
lives in `resourceIdentifiers[].value` under
`identifierType.name == 'DataStrorePath'`.

#### `DataStrorePath` value format by Datastore type `[observed 2026-05-18]`

| Datastore type | `DataStrorePath` value pattern | Example |
|---|---|---|
| VMFS on iSCSI (Synology) | `VMFS:\|naa.6001405<vendor-25-hex>\|` | `VMFS:\|naa.6001405d023e190d8940d485ad8bf1d4\|` |
| VMFS on local NVMe | `VMFS:\|t10.NVMe____<vendor-string>\|` | `VMFS:\|t10.NVMe____SHGP312D500GM2D2__________________________FFFFFFFFFFFFFFFF\|` |
| NFS | `<ip>/<server-path>` | `172.16.3.52/volume1/wld01` |
| vSAN | `VSAN:<cluster-uuid>-<node-uuid>` | `VSAN:90d067b8007711f1-af60000c297e270a` |

The leading `VMFS:`, the trailing `\|`, and the lack of any
prefix on NFS are all literal. Whitespace inside `t10.NVMe___...`
is also literal padding.

#### Host-side iSCSI-relevant properties `[observed 2026-05-18]`

On a `HostSystem` (the ESXi host), the same NAA appears inside the
**multipathPolicy** property (semicolon-delimited list of LUN
entries):

```
config|storageDevice|multipathInfo|multipathPolicy =
  '[LUN-0550b43f7ac19830b0f855f46def00feb884a5168b01d3cde019bc68fc1384ecd7 : FIXED,
    LUN-0100000000395435303431343031343132392020202020202050332d313238 : FIXED,
    LUN-02000100006001405d023e190d8940d485ad8bf1d453746f726167 : VMW_PSP_RR]'
```

The entry containing `6001405d023e190d8940d485ad8bf1d4` is our
iSCSI LUN's path-selection state. Useful for derived metrics
(e.g., dead/active path counts) but NOT a stitch field — substring
parsing inside a property value is not how MPB stitching works.

### 1.3 The NAA transform (Synology LUN UUID -> ESXi NAA)

**Empirically verified on this DSM 7.3.2 instance:**

The iSCSI NAA that ESXi sees, and that VCF Ops carries as the
Datastore `DataStrorePath`, is built from the Synology
`lun.uuid` like this:

```
ESXi NAA  =  naa.6001405 + uuid[0:8] + 'd' + uuid[8:12] + 'd' +
                           uuid[12:16] + 'd' + uuid[16:20] + 'd' +
                           uuid[20:25]
```

Where `uuid[N:M]` is the dash-free hex of the LUN UUID. Equivalent
code:

```python
def synology_uuid_to_naa(uuid_str: str) -> str:
    """Synology iSCSI LUN UUID -> ESXi NAA string (NAA Type 6)."""
    parts = uuid_str.split('-')  # 5 groups: 8-4-4-4-12 hex
    # Insert 'd' at each hyphen boundary, truncate to first 25 hex chars.
    rebuilt = 'd'.join(parts)
    return f"naa.6001405{rebuilt[:25]}"
```

Where `6001405` decodes as:
- `6` — NAA Type 6 (IEEE Registered Extended) per SCSI Primary
  Commands (SPC-4) §7.7.5 / SNIA NAA.
- `001405` — IEEE OUI assigned to Synology Inc.

The remaining 25 hex digits (100 bits) are the
vendor-defined portion. DSM constructs it by gluing the UUID
chunks together with `d` separators and truncating. The
truncation discards the trailing 7 hex chars of the UUID — so
the transform is **lossy in reverse** (NAA → UUID), but
**deterministic forward** (UUID → NAA).

**Practical adapter implementation:** compute the NAA from the
UUID on the Synology side, then bind by NAA. Never attempt
NAA → UUID reverse.

#### Verification table (worked examples)

| Synology `lun.uuid` | Computed NAA | Actual `DataStrorePath` | Match? |
|---|---|---|---|
| `d023e190-8940-485a-8bf1-47f41ae0c0a5` | `naa.6001405d023e190d8940d485ad8bf1d4` | `VMFS:\|naa.6001405d023e190d8940d485ad8bf1d4\|` (on `vcf-lab-wld01-cl01-iscsi`) | **YES** |
| `63ae9438-358e-4d9e-86dd-17e2e67f6c90` | `naa.600140563ae9438d358ed4d9ed86ddd1` | `VMFS:\|naa.600140563ae9438d358ed4d9ed86ddd1\|` (on `vcf-lab-wld02-cl01-iscsi`) | **YES** |
| `dc24a03c-db92-46e0-9b19-97574fea98d7` (LUN `vcf-lab-mgmt01-cl01-lun0`) | `naa.6001405dc24a03cddb92d46e0d9b19d9` | (no corresponding iSCSI datastore — LUN exists on Synology but not currently mounted to a vSphere cluster) | (not testable today; transform predicts a valid NAA) |

`[observed 2026-05-18 — two LUN/Datastore pairs verified
end-to-end; third LUN is unmounted on the vSphere side so cannot
be empirically confirmed but transform is deterministic]`

### 1.4 iSCSI join recipe

**Adapter pseudocode:**

```python
for lun in synology.iscsi_lun_list():
    naa = synology_uuid_to_naa(lun['uuid'])
    stitch_key = f"VMFS:|{naa}|"
    emit_aria_ops_metrics(
        adapter_kind = 'VMWARE',
        resource_kind = 'Datastore',
        bind_value    = stitch_key,
        bind_field    = 'DataStrorePath',
        metrics       = build_metric_dict(lun, utilization),
    )
```

**Worked example:**

```
Synology LUN row:
  name        = "vcf-lab-wld01-cl01"
  uuid        = "d023e190-8940-485a-8bf1-47f41ae0c0a5"
  vpd_unit_sn = "d023e190-8940-485a-8bf1-47f41ae0c0a5"
  size        = 8589934592000
  location    = "/volume1"

Transform:
  naa = synology_uuid_to_naa(uuid)
      = "naa.6001405d023e190d8940d485ad8bf1d4"

Stitch key emitted:
  "VMFS:|naa.6001405d023e190d8940d485ad8bf1d4|"

VCF Ops match:
  Datastore: vcf-lab-wld01-cl01-iscsi
  resourceIdentifiers[].name = "DataStrorePath"
  resourceIdentifiers[].value = "VMFS:|naa.6001405d023e190d8940d485ad8bf1d4|"
  -> MATCH
```

### 1.5 Edge cases — iSCSI

| Case | Behavior |
|---|---|
| LUN exists on DSM but not mounted on any vSphere cluster | Adapter emits a stitch key that matches zero VCF Ops Datastores. ARIA_OPS objects with no match are dropped at collection time (no orphan inventory) — verified pattern from `vsphere_storage_paths.yaml`. Synology LUN is still observable on the Diskstation INTERNAL object kinds. |
| LUN mounted as VMFS but **not exposed via the Synology target** the adapter is reading from | Not applicable to stitching — the LUN row carries its own UUID regardless of which targets export it. The transform is target-agnostic. |
| ESXi RDM (raw device mapping) rather than VMFS | Untested. RDMs are owned by a VM, not formatted as VMFS; they likely surface under VirtualMachine, not Datastore. **Out of scope for v1**; if asked, fall back to Diskstation-resident LUN object metrics only. |
| Multiple Synology NICs / multipath | The LUN NAA is invariant across paths. Stitch works regardless of which portal/path is active. |
| Snapshot-cloned LUN | New `uuid`, therefore new NAA, therefore separate Datastore (if mounted). No stitching ambiguity. |
| LUN renamed on DSM | `name` changes but `uuid` is stable; stitching survives. |

---

## 2. NFS Stitching

### 2.1 Synology side — identifier surface for an NFS export

#### Step 1: list shared folders

`GET ?api=SYNO.Core.Share&version=1&method=list`

Returns ALL shared folders (NFS-exported and not). To know which
are actually exported via NFS, you need to query NFS rules
per-share (see Step 2). On this NAS, the response is 11 shares;
the relevant fields for stitching:

```json
{
  "name": "vcf9",
  "vol_path": "/volume1",
  "uuid": "fdfa665f-1f7c-4870-b919-ee5827141d92",
  "desc": "",
  "is_usb_share": false
}
```

`[observed 2026-05-18]`

| Synology field | Stitch-relevant? |
|---|---|
| `name` | **YES** — becomes the last segment of the NFS export path |
| `vol_path` | **YES** — becomes the leading segment of the NFS export path |
| `uuid` | no — DSM-internal, never appears in NFS export paths |
| `desc` | no |

**Field NOT exposed in `Share list`:**
- The literal NFS export path as a single field — Synology
  constructs it implicitly as `<vol_path>/<name>` (e.g.,
  `/volume1/vcf9`). DSM does not echo it back.
- The Synology hostname/IP that ESXi uses to mount — that's a
  per-NIC decision the vSphere admin makes at mount time. The NAS
  has 4 IPs (`172.16.3.51/52/53/54`); ESXi might have mounted via
  any one. The adapter must enumerate Synology NICs
  (`SYNO.Core.Network.Interface list`) and try each candidate IP
  against the VCF Ops Datastore identifier — see §2.4.

#### Step 2: identify NFS-exported shares

`GET ?api=SYNO.Core.FileServ.NFS.SharePrivilege&version=1&method=load&share_name=<name>`

Returns the NFS rule set for one share:

```json
{
  "data": {
    "rule": [
      {
        "async": true,
        "client": "172.16.3.0/24",
        "crossmnt": false,
        "insecure": false,
        "privilege": "rw",
        "root_squash": "root",
        "security_flavor": { "kerberos": false,
                             "kerberos_integrity": true,
                             "kerberos_privacy": false,
                             "sys": true }
      },
      {
        "client": "172.27.1.0/24",
        ...
      }
    ]
  },
  "success": true
}
```

`[observed 2026-05-18 — share=vcf9; 2 rules covering two client
subnets]`

If `rule` is non-empty, the share is NFS-exported. Empty list
(or `success: false` with code `2301` "share not found") means
the share is not exported via NFS. Use this to filter the
Shares list down to NFS-exports.

**Critically:** the rule body **does not echo back the export
path**. The export path is implicit and is always
`<share.vol_path>/<share.name>`.

#### Step 3: enumerate the NAS's IPs

`GET ?api=SYNO.Core.Network.Interface&version=1&method=list`

Returns one entry per NIC; the relevant fields:

```json
{ "ifname": "eth1.13", "ip": "172.16.3.52",
  "mask": "255.255.255.0", "speed": 1000,
  "status": "connected", "type": "lan" }
```

`[observed 2026-05-18]`

Filter to entries where `status == "connected"`, `type == "lan"`,
and `ip` is non-empty. On this NAS: 4 candidate IPs
(`172.16.3.51/52/53/54`) across `eth0.13/eth1.13/eth2.13/eth3.13`.

### 2.2 VCF Ops side — identifier surface for an NFS Datastore

NFS datastores carry a different `DataStrorePath` format than VMFS
ones:

```
DataStrorePath = "<server-ip>/<server-path>"
```

`[observed 2026-05-18 — 3 NFS datastores]`

| Datastore name | `DataStrorePath` |
|---|---|
| `vcf-lab-nfs-wld01` | `172.16.3.52/volume1/wld01` |
| `vcf-lab-nfs-wld02` | `172.16.3.52/volume1/wld02` |
| `vcf-lab-mgmt01-nfs` | `172.16.3.52/volume1/vcf9` |

Notes:
- **No leading slash on the server path** — it's `volume1/...`, not
  `/volume1/...`. The vSphere admin's mount string probably was
  `/volume1/wld01` (with leading slash); VCF Ops normalizes by
  stripping it. The adapter must produce the value **without** the
  leading slash on the share path component to match.
- The separator between IP and path is a single forward slash.
- No port number, no NFS version annotation.

Like iSCSI, the NFS server address and remote path are **not** in
the Datastore `property` list. They appear only inside
`resourceIdentifiers[].value` under
`identifierType.name == 'DataStrorePath'`.

### 2.3 NFS join recipe

**Adapter pseudocode:**

```python
nics = synology.network_interfaces()
nas_ips = [n['ip'] for n in nics
           if n.get('status') == 'connected'
              and n.get('type') == 'lan'
              and n.get('ip')]

shares = synology.share_list()
for share in shares:
    rules = synology.nfs_share_privilege(share['name'])
    if not rules:
        continue          # not NFS-exported
    # Note: vol_path starts with '/', export-path component does NOT.
    server_path = f"{share['vol_path'].lstrip('/')}/{share['name']}"
    # Emit one ARIA_OPS row per (nic_ip, share) pair so VCF Ops can
    # match whichever IP the ESXi admin actually mounted with.
    for ip in nas_ips:
        stitch_key = f"{ip}/{server_path}"
        emit_aria_ops_metrics(
            adapter_kind = 'VMWARE',
            resource_kind = 'Datastore',
            bind_value    = stitch_key,
            bind_field    = 'DataStrorePath',
            metrics       = build_metric_dict(share, rules),
        )
```

**Worked example:**

```
Synology share row:
  name     = "vcf9"
  vol_path = "/volume1"
  uuid     = "fdfa665f-1f7c-4870-b919-ee5827141d92"

NFS rules for this share (non-empty -> is NFS-exported):
  [ { client: "172.16.3.0/24", privilege: "rw", ... },
    { client: "172.27.1.0/24", privilege: "rw", ... } ]

Synology NICs (connected, LAN, non-empty ip):
  172.16.3.51
  172.16.3.52
  172.16.3.53
  172.16.3.54

Constructed export paths:
  "172.16.3.51/volume1/vcf9"
  "172.16.3.52/volume1/vcf9"    <-- this one matches
  "172.16.3.53/volume1/vcf9"
  "172.16.3.54/volume1/vcf9"

VCF Ops match:
  Datastore: vcf-lab-mgmt01-nfs
  resourceIdentifiers[].name = "DataStrorePath"
  resourceIdentifiers[].value = "172.16.3.52/volume1/vcf9"
  -> MATCH on 172.16.3.52 candidate
```

Verified end-to-end against all three live NFS datastores on
2026-05-18.

### 2.4 Alternative join strategy — Synology FQDN

If the ESXi admin mounted by hostname (e.g.,
`storage.int.sentania.net:/volume1/vcf9`) the `DataStrorePath`
would be `storage.int.sentania.net/volume1/vcf9`. To handle that
case, the adapter should ALSO emit a hostname-form variant if
DSM provides a hostname. On this NAS:

`SYNO.DSM.Info getinfo` returns:
- `hostname` (the NAS's configured hostname)

…and `SYNO.Core.Network.Interface list` does NOT return per-NIC
hostnames. So the safest expansion is:

```
stitch candidates = nas_ips + [dsm_info.hostname]
```

…where `dsm_info.hostname` is queried from `SYNO.DSM.Info getinfo`
(already in the 5-min cycle per
`context/api-maps/synology-overview.md`).

This is **inferred and not live-verified** in this lab — every NFS
datastore here uses the bare IP, so the FQDN form wasn't observable.
`[inferred from pattern]` Flag this as a Phase-2 verification item
if a hostname-mounted NFS datastore is ever encountered.

### 2.5 Edge cases — NFS

| Case | Behavior |
|---|---|
| Share exists on DSM but not NFS-exported | NFS rule list is empty → adapter skips. No stitch attempt. |
| Same share mounted by multiple ESXi clusters via different NICs | Each cluster's Datastore has its own `DataStrorePath` with whichever IP they used. Adapter emits one row per (nic_ip, share) so any IP form matches. ARIA_OPS rows with no Datastore match are silently dropped. |
| Synology has DHCP IP that changes between collection cycles | DSM returns current IPs each call. Stitching still works as long as the ESXi side was remounted to the new IP (otherwise the stale NFS datastore is dead at the vSphere layer regardless of our stitching). |
| Mount uses FQDN instead of IP | See §2.4 — emit FQDN form as an additional candidate. |
| NFS v3 vs v4 | DSM exposes `enable_nfs` (v3) and `enable_nfs_v4` separately. Does not affect the stitch path string. |
| Hidden/Browseable share (`hidden: true`) | Same export path; same stitch. |
| Crypto-locked share | Not exported until unlocked; `NFS.SharePrivilege.load` likely fails with code `2301`. Treated as not-NFS-exported. |
| Subdir mounts (e.g., ESXi mounted `/volume1/wld01/sub`) | `DataStrorePath` would be `<ip>/volume1/wld01/sub` — no longer matches our `<ip>/<vol_path>/<share>` recipe. Out of scope; Synology's NFS export model is at the share root. |
| Share name with spaces or special characters | DSM allows them; check that the constructed path does not need URL encoding. **Not tested this session.** `[unverified]` |

---

## 3. Derived relationships (free Datastore -> HostSystem and Datastore -> VM)

Once a Synology object stitches onto a VMware Datastore, the
existing VMware adapter's relationship graph carries every other
edge **for free**. No MP-side relationship authoring required.

`[observed 2026-05-18]` — Live graph for one iSCSI datastore:

```
Datastore vcf-lab-wld01-cl01-iscsi
  relationships/parents (12 items):
    Datacenter (1): vcf-lab-wld01-DC
    Environment (1): Non vSAN Datastores
    HostSystem (2): vcf-lab-wld01-esx01, vcf-lab-wld01-esx02      <-- the 2 ESXi mounts
    Pod (3): Kubernetes-side pods using volumes on this DS
    VM Entity Status (1): PoweredOn:vcf-lab-vcenter-wld01...
    VirtualMachine (4): SupervisorControlPlaneVM (4), vcf-lab-wld01-en02, ...   <-- the 4 VMs hosted
```

And for one NFS datastore:

```
Datastore vcf-lab-nfs-wld01
  relationships/parents (5 items):
    Datacenter (1): vcf-lab-wld01-DC
    Environment (1): Non vSAN Datastores
    HostSystem (2): vcf-lab-wld01-esx01, vcf-lab-wld01-esx02      <-- the 2 ESXi mounts
    VM Entity Status (1): PoweredOn:vcf-lab-vcenter-wld01...
    (no VMs because nfs-wld01 is empty in this lab)
```

(Note: vSphere's relationship graph reports HostSystem as a
*parent* of Datastore — the relationship arrow is
HostSystem → Datastore, i.e. the host **has** the datastore. VMs
that *use* a datastore for their disks also surface as parents.
This is just upstream VMware modeling — don't try to flip it.)

**Implication for the MP:** declare `relationships: []` on
ARIA_OPS object kinds (per the `vsphere_storage_paths.yaml`
pattern). VCF Ops dashboards, alerts, supermetrics, and views
that pivot off `HostSystem | mounted datastores | their metrics`
will see our stitched metrics on the Datastore side without us
authoring any edges. Same for `VM | datastore`.

### 3.1 What this MP must NOT try to do

- **Do not stitch onto HostSystem directly to express "this host
  uses this Synology."** That relationship is already encoded
  via Datastore. Going around it duplicates inventory and breaks
  drill-down.
- **Do not stitch onto VirtualMachine directly.** Same reason —
  VMs surface in `Datastore.relationships.parents` for the
  datastore they're stored on.
- **Do not author MP-side `relationships:` to bind Diskstation
  → HostSystem.** The link is implicit via the datastore stitch.
  If the user really wants a one-to-many roll-up
  ("which hosts use which Synology"), build it as a custom
  group / view at content-authoring time, not as an MP edge.

---

## 4. Recommended adapter-side data model

### 4.1 Object kinds (in the MP YAML)

The Synology MP keeps its existing **INTERNAL** object kinds
(Diskstation, Storage Pool, Volume, Disk, iSCSI LUN, Docker
Container, UPS — per `synology-overview.md`) for the bits that
have no VMware counterpart. It then adds **two ARIA_OPS object
kinds** that push Synology-attributed metrics onto Datastores:

| Kind | type | aria_ops.resource_kind | aria_ops.bind_metric | Source rows |
|---|---|---|---|---|
| `Synology iSCSI Datastore Health` | ARIA_OPS | Datastore | DataStrorePath | iSCSI LUN row, transformed |
| `Synology NFS Datastore Health` | ARIA_OPS | Datastore | DataStrorePath | NFS-exported share row × NIC IPs |

(Names match the `vsphere_storage_paths.yaml` precedent — short,
prefixed mentally with `VCF-CF - ` on metric labels.)

### 4.2 Stitch-field computation

The Synology adapter response field that the MP YAML's
`metricSets[].stitch_match_field` points at must already contain
the computed stitch string. The factory's existing grammar does
NOT perform field synthesis inside the renderer; the adapter
emits the stitch field as a flat key on the row.

Two implementation options:

**Option A — pre-compute in the request body**

Have the renderer add a derived `stitch_key` field to each row
before metricSet binding. Equivalent to the
`vsphere_storage_paths.yaml` pattern where `hostname` and
`datastore_moid` are flat fields on rows.

The Synology API doesn't natively emit these strings, so this
needs **adapter-side enrichment** — either a JMESPath / Jinja
projection in YAML, or a small Python helper invoked via the
factory's `compute:` step (if one exists).

**Option B — synthetic request that does the join in the response**

Define a virtual request that emits, per LUN/share, a row whose
fields include the computed stitch key. Requires a "compute"
step in the request DSL.

**Open question — TOOLSET GAP candidate:** the current YAML grammar
supports `from_request: <name>` and `list_path: data` but it's not
obvious whether it supports value derivation. Examples like
`vsphere_storage_paths.yaml` work only because the upstream API
already emits `hostname` and `datastore_moid` as flat fields.

**Recommendation for the orchestrator:** before mp-designer
finalizes the Synology MP design, ask `tooling` to confirm whether
the renderer can compute a stitch key from `lun.uuid` via a YAML
expression (e.g., a `jinja:` source or similar). If yes, document
the syntax in `context/authoring/guide_content_authoring.md`. If no, that's
the gap, and the adapter-side enrichment story needs a new
mechanism. The transform itself (§1.3) is trivial — five lines of
Python — and shouldn't block the MP, but the framework needs a
formal place to express it.

### 4.3 What metrics to push onto each Datastore

Out of scope for this map — see mp-designer. Likely candidates
(non-exhaustive):
- iSCSI Datastore Health: LUN-backed read/write IOPS, throughput,
  latency, LUN provisioned size, "is the underlying volume
  healthy", "is the storage pool degraded", LUN snapshot count.
- NFS Datastore Health: share-backed read/write IOPS via Synology
  `nfs` resource in Utilization (not yet mapped — see Gaps),
  underlying volume health, "client subnet present in NFS rule".

All metric names should carry the `vcf_cf_` prefix per the
`vsphere_storage_paths.yaml` convention.

---

## 5. Mapping to the API pattern catalog

The catalog entry for **vSphere REST**
(`context/api_pattern_catalog.md`, section "vSphere REST (vCenter
Server)") is the closest precedent and the pattern this MP should
mirror:

> Use ARIA_OPS stitching, not new object kinds. VCF Operations
> already has a vSphere adapter that produces canonical
> `HostSystem`, `VirtualMachine`, `Datastore`, ... objects. A new
> MP should augment those with additional metrics/properties via
> `type: ARIA_OPS`, matching on:
> - HostSystem: `Summary|Hardware|BIOS UUID` (`uuid` field on
>   vSphere REST side)
> - VirtualMachine: `Summary|Instance UUID` (`instance_uuid`)
> - Datastore: `Summary|Datastore URL` or `Capacity|Capacity`
>   (instance UUID where available)

This 2026-05-18 cartography session **augments** that entry with
a concrete, evidence-backed Datastore bind that is more universal
than the catalog's "Summary|Datastore URL" guess:

> **For Datastore stitching where the upstream system has its own
> identifier (NAA, NFS export path, etc.), use the VMWARE
> Datastore resource identifier `DataStrorePath` (literal name,
> typo included). Value forms by Datastore type:**
> - **VMFS (FC/iSCSI):** `VMFS:|naa.<NAA>|`
> - **VMFS (local NVMe):** `VMFS:|t10.NVMe____<vendor-string>|`
> - **NFS:** `<server-ip-or-fqdn>/<server-path-without-leading-slash>`
> - **vSAN:** `VSAN:<cluster-uuid>-<node-uuid>`

The Synology catalog entry in `context/api_pattern_catalog.md`
(section "Synology DSM (NAS management)") should be updated to
**cross-reference this stitching map** under "Known limitations"
or a new "Stitching" section. (Out of scope for this session;
flag for the orchestrator.)

---

## 6. Open risks and gaps

### 6.1 Verified-but-narrow

- **NAA transform verified on one DSM version (7.3.2-86009 Update 1)
  against one DS model (DS1520+).** Whether Synology has ever
  changed the NAA encoding across DSM major versions is unknown.
  `[observed 2026-05-18]` If users report stitching failures on
  DSM 6.x or future 8.x, suspect the transform first. A unit test
  in the factory should bake in the two verified
  (UUID, NAA) pairs from §1.3 as fixtures.
- **NFS join verified only against IP-form mounts.** FQDN-form
  mounts are inferred per §2.4 but unproven. `[inferred from
  pattern]`

### 6.2 Synology-side gaps

- **NFS per-share IO metrics** — `SYNO.Core.System.Utilization`
  has an `nfs` resource (per `synology-storage.md` filter
  contract) but the per-share breakdown was not explored this
  session. If the MP wants real per-NFS-export throughput
  metrics, that's a separate Phase-2 cartography pass.
- **LUN-to-target mapping** — left as an exercise. Not needed
  for stitching (the LUN's NAA is target-agnostic) but useful
  for diagnostic dashboards. `SYNO.Core.ISCSI.LUN map_target`
  exists but takes write-style params; needs investigation.
- **Connected ESXi initiator visibility** — `SYNO.Core.ISCSI.Host`
  returned `hosts: []` this session despite three ESXi hosts
  actively connected. Likely populated only when the target has
  connected initiators recorded by the SCST/LIO stack. If
  populated elsewhere, that would be a reverse-stitch key
  (Synology side knows which ESXi IQN is connected to which
  target).

### 6.3 VCF Ops-side gaps

- **`DataStrorePath` is `isPartOfUniqueness: false`.** The
  uniqueness-bearing identifiers are `VMEntityObjectID` (e.g.,
  `datastore-25`) and `VMEntityVCID` (vCenter UUID).
  `DataStrorePath` is a non-unique attribute. **Real-world risk:
  two datastores with the same NAA in the same vCenter is
  impossible** (an NAA uniquely identifies a SCSI LUN), so for
  iSCSI the match is implicitly unique. **For NFS, two ESXi
  clusters could mount the same NFS export with the same path
  string** — both Datastores would carry the same
  `DataStrorePath`. Whether VCF Ops merges those into one
  Datastore or keeps them as two is something to test. If
  duplicated, the ARIA_OPS stitch will attach our metrics to
  both, which is probably desirable.
- **`DataStrorePath` is a `STRING` not a structured type.** Case
  sensitivity, whitespace, and exact format must match
  byte-for-byte. The adapter must not accidentally URL-encode
  the pipe characters in the VMFS form.
- **Property tree omits remoteHost/remotePath.** As documented in
  §1.2 / §2.2 the only identifying string for the upstream is
  inside `resourceIdentifiers[]`. ARIA_OPS binding uses
  identifiers, so this is fine — but **do not try to stitch via
  `summary|path`** (the local VMFS UUID URL). It's the wrong
  string.

### 6.4 Framework gaps

- **Adapter-side field derivation.** §4.2 documents this as the
  one open framework question. The NAA transform must run
  somewhere — either inside the renderer or as a YAML expression.
  Recommend `tooling` confirms before mp-designer commits to a
  shape.

---

## 7. Files referenced

| File | Purpose |
|---|---|
| `context/api-maps/synology-iscsi.md` | iSCSI LUN & Target API surface |
| `context/api-maps/synology-storage.md` | Storage Pool / Volume / Disk; Utilization filter contract |
| `context/api-maps/synology-overview.md` | Endpoint inventory & object summary |
| `context/api-maps/synology-auth.md` | Auth flow |
| `context/mpb_pak_structural_reference.md` | ARIA_OPS object rules in MPB paks |
| `context/api_pattern_catalog.md` | vSphere REST entry — canonical ARIA_OPS Datastore precedent |
| `content/managementpacks/vsphere_storage_paths.yaml` | Closest factory MP precedent — pure ARIA_OPS stitch, no INTERNAL kinds |
