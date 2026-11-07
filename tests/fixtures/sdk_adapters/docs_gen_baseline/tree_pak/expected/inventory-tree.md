# Inventory Tree: Baseline Tree Pak

> Generated from `describe.xml` v1.2.3.7. Do not edit: regenerated on every build.

**Traversal Spec:** Baseline Traversal

## Traversal Tree

- **Base Site** (`BaseSite`)
  - **Base Switch** (`BaseSwitch`)
    - **Base Switch** (`BaseSwitch`) *(recursive: nests under itself)*
    - **Base Switch Port** (`BaseSwitchPort`)
  - **Base Volume** (`BaseVolume`)
- **Datastore (VMWARE)** (`VMWARE::Datastore`)
  - **Base Volume** (`BaseVolume`) *(see above)*

> \* = identifying (unique) key

## Resource Kinds Reference

| Kind | Display Label | Identifying Keys | Parent(s) |
|------|--------------|-----------------|-----------|
| `BaseSite` | Base Site | `site_id` * | - |
| `BaseSwitch` | Base Switch | `switch_id` *, `model` | Base Site, Base Switch |
| `BaseSwitchPort` | Base Switch Port | `port_key` * | Base Switch |
| `BaseVolume` | Base Volume | `volume_id` * | Base Site, Datastore (VMWARE) |

## Cross-MP Relationships

These edges are created at collection time via the Suite API and never appear in `describe.xml`. They are declared explicitly in `adapter.yaml` (`cross_mp_edges`) so this generated docset doesn't silently omit them. *Italic* endpoints belong to a foreign management pack; `code` endpoints are owned by this adapter.

| Parent | Child | Description |
|--------|-------|-------------|
| *VMWARE HostSystem* (foreign, VMWARE) | `BaseSwitchPort` | Per-vmnic LLDP join via Suite API; additive, optional |
