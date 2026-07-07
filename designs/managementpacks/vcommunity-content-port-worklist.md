# vCommunity Parity Port — Phase-2 Content Port Worklist

Inventory of the original `VCFOperationsvCommunity` MP content, captured
for the `vcfcf_vcommunity` SDK pak parity port. Read-only design capture —
no content authored here.

**Source tree:** `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/`
**Source MP:** "VCF Operations vCommunity" (Onur Yuzseven, Broadcom) —
`resources/resources.properties` is the only localization bundle; it carries
`DISPLAY_NAME` / `DESCRIPTION` / `VENDOR` strings only (no per-object label
overrides), so localization adds nothing to the per-object port worklist.

## Counts at a glance

| Type | Count to port | Notes |
|---|---|---|
| Super metrics | **37 unique** (54 files) | 17 UUIDs are duplicated under an old + a "vSphere…"-prefixed name; same UUID, byte-identical formula. Port 37, not 54. |
| Views | **16** (in `content/reports/`, `<ViewDef>`) | `view-author` targets. 10 are SM-free. |
| Reports | **16** (`Report - VOA - *`, `<ReportDef>`) | Real report-schedule defs. `report-author` targets. They embed Dashboards + CoverPage/TOC. |
| Symptoms | **2** (`symptomdefs/`) | Both property-based. A 3rd (license) is inline in an alert. |
| Alerts | **3** (`alertdefs/`) | 2 reference external symptoms; 1 (license) has inline conditions. |
| Recommendations | **0** | `recommendations/` is empty (`.gitkeep` only). |
| Dashboards | **13** (incl. 1 "input/template") | ~107 widgets total. RULE-011 wireframe-gated, one approval each. |
| Custom groups | **0 authored** | But the Business-App SM chain targets `Container:Enterprise/BusinessService/Tier` kinds — see note. |

---

## 1. Super metrics (37 unique)

### Duplicate-UUID finding (port-blocking if mishandled)

17 SM files are stale duplicates: each shares its UUID **and** its exact
formula with a "vSphere…"/"ESXi…"-prefixed twin (e.g.
`Cluster Performance.json` ≡ `vSphere Cluster Performance.json`,
UUID `a1b7d29a-…`). Verified byte-identical on a spot-check of 6 pairs.
**Port 37 SMs**, preferring the prefixed canonical name. The old-name files
are renames left in the export, not separate metrics.

Colliding pairs (old name → canonical): Bad Network Packets→ESXi Bad Network
Packets; CPU Co-Stop→vSphere Cluster CPU Co-Stop; CPU Ready→vSphere Cluster
CPU Ready; Memory Ballooned→vSphere Cluster Memory Ballooned; Memory
Contention→vSphere Cluster Memory Contention; Memory Zip Swap→vSphere Cluster
Memory Zip Swap; Memory Zipped and Swapped→vSphere VM Memory Zip Swap; Cluster
Performance→vSphere Cluster Performance; SLA Leading Indicator→vSphere Cluster
SLA Leading Indicator; Worst ESXi Bad Network Packets→vSphere Cluster Worst
ESXi Bad Network Packets; Worst VM CPU Co-Stop→vSphere Cluster Worst VM CPU
Co-Stop; Worst VM CPU Ready→vSphere Cluster Worst VM CPU Ready; Worst VM
Memory Contention→vSphere Cluster Worst VM Memory Contention; Total
vMotions→vSphere Cluster vMotions; Average Clusters Performance→vSphere
Clusters Performance; Count of Non-green Clusters→vSphere Clusters not Green;
VM Performance→vSphere VM Performance.

### Dependency ordering (5 tiers, DAG, no cycles)

Author strictly tier-by-tier. Cross-references (`@supermetric:"…"`) resolve at
author time, so every SM in a lower tier must exist before its consumer.

**TIER 0 — independent (author first, any order within tier) — 27 SMs**

| SM | Resource kind | Formula gist |
|---|---|---|
| ESXi Bad Network Packets | VMWARE:HostSystem | net errors/dropped Rx+Tx sum |
| Network Speed Degradation | VMWARE:HostSystem | net speed / configuredSpeed × 100 |
| ESXi Host Availability | VMWARE:HostSystem | poweredOn + connected check |
| Unavailable ESXi Host | VMWARE:vSphere World | count hosts poweredOn<1, depth 4 |
| Clusters Availability | VMWARE:vSphere World | avg cluster availability, depth 4 |
| vSphere Cluster CPU Co-Stop | VMWARE:ClusterComputeResource | avg VM 20s peak costop, depth 3 |
| vSphere Cluster CPU Ready | VMWARE:ClusterComputeResource | avg VM 20s peak ready, depth 3 |
| vSphere Cluster Worst VM CPU Co-Stop | VMWARE:ClusterComputeResource | max VM costop, depth 3 |
| vSphere Cluster Worst VM CPU Ready | VMWARE:ClusterComputeResource | max VM ready, depth 2 |
| vSphere Cluster Worst VM Memory Contention | VMWARE:ClusterComputeResource | max VM mem contention, depth 3 |
| vSphere Cluster Memory Ballooned | VMWARE:ClusterComputeResource | vmmemctl / (vmmemctl+consumed−sysUsage) |
| vSphere Cluster Memory Contention | VMWARE:ClusterComputeResource | avg VM mem contention, depth 3 |
| vSphere Cluster Memory Zip Swap | VMWARE:ClusterComputeResource | (compressed+swapout)/(…) |
| vSphere Cluster vMotions | VMWARE:ClusterComputeResource | number_vmotion/running_vms × 100 |
| vSphere Cluster SLA Leading Indicator | VMWARE:ClusterComputeResource | running_vms − count KPI-breaching VMs |
| CPU Reservation | VMWARE:ClusterComputeResource | reservedCapacity / usableCapacity × 100 |
| CPU Usable Capacity Utilization | VMWARE:ClusterComputeResource | avg host util × provisioned/usable |
| Memory Reservation | VMWARE:ClusterComputeResource | mem reservedCapacity / usableCapacity × 100 |
| Cascading Resource Pools | VMWARE:ClusterComputeResource | count nested ResourcePools, depth 5 vs 3 |
| Number of Resource Pools | VMWARE:ClusterComputeResource | count ResourcePool health, depth 3 |
| vSphere VM Memory Zip Swap | VMWARE:VirtualMachine | (compressed+swapped)/guest used_memory × 100 |
| Share per GB of Memory | VMWARE:VirtualMachine | mem shares / memoryKB × 1024 |
| Share per vCPU | VMWARE:VirtualMachine | cpu shares / numCpu |
| Number of VM | VMWARE:DistributedVirtualPortgroup | count VM health, depth 2 |
| Number of Port Groups | VMWARE:VmwareDistributedVirtualSwitch | count DV portgroup health, depth 1 |
| Total Non-default Settings | VMWARE:VmwareDistributedVirtualSwitch | count override-allowed portgroup policies |
| Total Network Configuration Issues | VMWARE:VMwareAdapter Instance | sum DVS host config_outofsync, depth 3 |

**TIER 1 — depend on one Tier-0 SM — 4 SMs**

| SM | Resource kind | Depends on |
|---|---|---|
| ESXi Hosts Average Availability | VMWARE:VMwareAdapter Instance | ESXi Host Availability |
| Total Network Speed Degradation | VMWARE:vSphere World | Network Speed Degradation |
| vSphere VM Performance | VMWARE:VirtualMachine | vSphere VM Memory Zip Swap |
| vSphere Cluster Worst ESXi Bad Network Packets | VMWARE:ClusterComputeResource | ESXi Bad Network Packets |

**TIER 2 — 2 SMs**

| SM | Resource kind | Depends on |
|---|---|---|
| Business Application Tier Performance | Container:Tier | vSphere VM Performance |
| vSphere Cluster Performance | VMWARE:ClusterComputeResource | 10 Tier-0/1 cluster SMs (CPU Ready/CoStop, Worst*, Mem Ballooned/Contention/ZipSwap, vMotions, Worst ESXi Bad Net Pkts) |

**TIER 3 — 3 SMs**

| SM | Resource kind | Depends on |
|---|---|---|
| vSphere Clusters not Green | VMWARE:vSphere World | vSphere Cluster Performance |
| vSphere Clusters Performance | VMWARE:vSphere World | vSphere Cluster Performance |
| Business Application Performance | Container:BusinessService | Business Application Tier Performance |

**TIER 4 — 1 SM**

| SM | Resource kind | Depends on |
|---|---|---|
| Business Applications Performance | Container:Enterprise | Business Application Performance |

### Notes that bear on the port

- **Business-App chain targets `Container:*` kinds** (Enterprise / BusinessService
  / Tier), not VMWARE objects, and `Business Application Performance` also
  traverses `KubernetesAdapter:K8S-Namespace`. These kinds come from the VCF
  Ops *Business Application* / *Service Discovery* surface (Container adapter),
  not the vCommunity pak. On a vanilla devel instance with no business apps
  defined, these 4 SMs (Tiers 2–4) and the dashboards that consume them will
  show no data. Verification of the Business-App branch needs that surface
  populated — flag for Phase-3 environment work.
- **`VMwareAdapter Instance` / `vSphere World` rollups** (ESXi Hosts Average
  Availability, Total Network Speed Degradation, Total Network Config Issues,
  Clusters Availability, Unavailable ESXi Host, both "Clusters …" rollups)
  emit onto adapter-instance / world objects; they're fine on devel but their
  values depend on a populated cluster/host inventory.

---

## 2. Views (16 — `view-author` targets)

All live in `content/reports/` as `<Content><Views><ViewDef>` (confirms
`lessons/pak-content-bundling.md`: views ship in a pak's `content/reports/`).
Targets are `view-author`, **not** `report-author`.

### SM-free views (10) — author before any SM exists, native VMWARE only

1. ESXi Host Details vCommunity — VMWARE:HostSystem (LIST) — *vCommunity props*
2. ESXi Host Hardware Models vCommunity — VMWARE:HostSystem (bar)
3. ESXi Host License Information vCommunity — VMWARE:HostSystem (LIST) — *licensing surface*
4. ESXi Host Maintenance State vCommunity — VMWARE:HostSystem (bar)
5. ESXi Host NIC Details (NIC Details View) — VMWARE:HostSystem (LIST) — *vCommunity NIC props*
6. ESXi Host Power State vCommunity — VMWARE:HostSystem (bar)
7. ESXi Host Versions vCommunity — VMWARE:HostSystem (bar)
8. ESXi Packages — VMWARE:HostSystem (LIST) — *package/VIB surface*
9. VM Details vCommunity — VMWARE:VirtualMachine (LIST)
10. View - Cluster nenic nfnic VIBs (nfnic VIB Vendor Distribution) — VMWARE:HostSystem (pie) — *VIB surface*
11. Windows Services vCommunity — VMWARE:VirtualMachine (LIST) — *Windows guest surface*

(11 listed — Windows Services is SM-free but on the gated OS surface; counted
among the 16 views. The five SM-consuming views are below.)

### SM-consuming views (5) — author after their SMs

| View | Target kind | Super metrics referenced (by name) |
|---|---|---|
| View - Collection01 (VM Network Top Talkers) | VMWARE:VirtualMachine | Cascading Resource Pools, Number of VM, Number of Resource Pools, Number of Port Groups, CPU Reservation, Share per vCPU, Memory Reservation, Share per GB of Memory |
| View - Set 1 (VM Memory Allocation Trend) | VMWARE:vSphere World | Number of VM, Share per vCPU, Share per GB of Memory |
| View - Set 2 (ESXi High Memory Trend) | VMWARE:HostSystem | + above plus CPU Usable Capacity Utilization, vSphere VM Performance |
| View - Set 3 (VM Memory Size Distribution) | VMWARE:VirtualMachine | Total Network Config Issues, Number of VM, CPU Usable Capacity Utilization, Cluster Performance, Total Non-default Settings |
| View - Set 4 (Distributed Port Groups) | VMWARE:DistributedVirtualPortgroup | Total Network Config Issues, Number of VM, Number of Port Groups, Total Non-default Settings |

**Gate flag:** the SM-free ESXi/VM views above tagged *vCommunity props /
licensing / package / VIB / Windows* read from `vCommunity|…` property keys
(Advanced System Settings, Packages, Licensing, Network device, Guest OS
Services). Those keys are emitted by the pak's own collection / SolutionConfig
and will be **empty on devel until the corresponding surface is configured and
enabled** — same Phase-3 gap as the symptoms/alerts below.

---

## 3. Reports (16 — `report-author` targets)

All 16 `Report - VOA - *` files are genuine `<Reports><ReportDef>` schedule
definitions (CoverPage + TableOfContents + embedded **Dashboard** sections by
UUID), **not** views. They are `report-author` targets and depend on their
embedded dashboards/views existing first, so they author **last**.

`Capacity, Configuration, Datastore for CSV export, Distributed Port Groups for
CSV export, Distributed Switch for CSV export, ESXi Hosts for CSV Export,
Executive Summary, Inventory, Namespace for CSV export, Performance, Supervisor
Cluster for CSV export, Virtual Machines for CSV export, vCenter for CSV Export,
vSphere Clusters for CSV Export, vSphere Data Center for CSV export, vSphere Pod
for CSV export.`

> **Scope correction:** the original "~22 reports are all views" finding is
> wrong. The `content/reports/` dir is a 50/50 split — **16 `<ViewDef>` views**
> + **16 `<ReportDef>` reports**. Author the 16 views via `view-author` and the
> 16 reports via `report-author`. The Namespace / Supervisor Cluster / Pod VOA
> reports target vSphere-with-Tanzu (Supervisor) objects — confirm that surface
> exists on the target before expecting data.

---

## 4. Symptoms (2) & Alerts (3)

### Symptoms (property-based, `symptomdefs/`)

| Symptom | Target | Type | Key | Test | Severity |
|---|---|---|---|---|---|
| ESXi Host NIC Disconnected | VMWARE:HostSystem | property | `vCommunity\|Network\|Device:vmnic0\|Status` | ≠ "Connected" | critical |
| Windows Service Down | VMWARE:VirtualMachine | property | `vCommunity\|Guest OS\|Services:DHCP Client\|Service Status` | ≠ "Running" | warning |

Both are instanced templates hard-coded to a single instance (vmnic0 /
DHCP Client). Port as-authored.

### Alerts (`alertdefs/`)

| Alert | Target | Impact | Symptom dependency | Recommendation |
|---|---|---|---|---|
| ESXi Host NIC Disconnected | VMWARE:HostSystem | health | refs symptom **ESXi Host NIC Disconnected** (author symptom first); wait/cancel 2 | none |
| Windows Service Down | VMWARE:VirtualMachine | health | refs symptom **Windows Service Down** (author symptom first) | none |
| ESXi Host License Expiring | VMWARE:HostSystem | health | **inline** tiered conditions on `vCommunity\|Licensing:vSphere 8 Enterprise Plus for VCF\|Remaining Days` (<30 crit / 30–60 warn / 60–90 / 90–160) — no external symptom | none |

**Alert→symptom order:** author symptom *ESXi Host NIC Disconnected* before
its alert; author symptom *Windows Service Down* before its alert; the license
alert has no external symptom dependency. No recommendations to port (dir empty).

---

## 5. Dashboards (13, ~107 widgets) — RULE-011 wireframe-gated, one approval each

Widget types across the set: View (~64), Scoreboard (~16), HealthChart (~9),
Heatmap (2), PropertyList (3), ResourceRelationshipAdvanced (1).

| Dashboard | ~Widgets | Key SM / surface references |
|---|---|---|
| Cluster Performance 2.0 | 13 | vSphere Cluster Performance + native CPU/mem/disk/net |
| Critical Business Applications | 6 | Business Applications/Application/Tier Performance, vSphere VM Performance; "OS Services" view (Windows gate) |
| ESXi Configuration 2.0 | 18 | **Advanced System Settings** props (Config.HostAgent/Security/Syslog/UserVars) — gated |
| ESXi Host Details Dashboard | 10 | PropertyList **Advanced System Settings** + **Packages** + License info — gated |
| VM Capacity 2.0 | 10 | `OnlineCapacityAnalytics\|capacityRemainingPercentage` (Capacity Analytics must be on) |
| VM Details | ~6 | PropertyList **VM Advanced Parameters** (`vCommunity\|…\|Advanced Parameters`) — gated |
| VM Performance 2.0 | ~8 | vSphere VM Performance + native perf |
| VM Storage Configuration | ~7 | native storage/snapshot/RDM |
| vSphere Cluster Capacity 2.0 | ~8 | cluster capacity SMs incl. CPU Usable Capacity Utilization |
| vSphere Cluster Configuration 2.0 | ~10 | native cluster HA/DRS/DPM config |
| vSphere Network Configuration 2.0 | ~10 | Total Net Config Issues, Total Non-default Settings + native net |
| vSphere Resource Management | ~8 | Cascading Resource Pools, CPU/Mem Reservation, Share per vCPU/GB |
| To be used in reports/Input dashboards | (template) | source for the 16 VOA reports' embedded sections |

The "Input dashboards" template feeds the report sections — port before the
reports. Each of the 12 user-facing dashboards needs its own wireframe approval.

---

## SolutionConfig-gated / OS-surface content (Phase-3 environmental gap)

These read `vCommunity|…` keys emitted by the pak's own SolutionConfig-gated
collection (Advanced System Settings, Packages/VIBs, VM Advanced Params/Options,
Licensing) or the Windows/Guest-OS surface. **Expect empty on devel until those
surfaces are configured and enabled** — material for the verification plan, not
a port blocker.

- **Symptoms/alerts:** Windows Service Down (guest-agent surface);
  ESXi Host License Expiring (license-edition-specific metric).
- **Views:** ESXi Host Details / NIC Details / License Information / Packages,
  nfnic VIB Vendor Distribution, Windows Services vCommunity.
- **Dashboards:** ESXi Configuration 2.0, ESXi Host Details Dashboard (Adv
  System Settings + Packages), VM Details (Adv Parameters), VM Capacity 2.0
  (Capacity Analytics), Critical Business Applications (OS Services / Business
  App surface).
- **SolutionConfig source files present in the reference MP** (define which keys
  these surfaces emit): `files/solutionconfig/esxi_advanced_system_settings.xml`,
  `esxi_packages.xml`, `vm_advanced_parameters.xml`, `vm_options.xml`,
  `windows_event_list.xml`, `windows_service_list.xml`.

---

## Recommended authoring sequence (bottom-up, serial)

1. **Custom groups / Business-App surface prerequisite** — confirm whether the
   Business-App `Container:*` kinds exist on target (Phase-3). If absent, defer
   the 4 Business-App SMs and the Critical Business Applications dashboard.
2. **Super metrics, tier by tier:** Tier 0 (27) → Tier 1 (4) → Tier 2 (2) →
   Tier 3 (3) → Tier 4 (1). One SM per `supermetric-author` invocation, serial,
   never parallel. Use the canonical (prefixed) names; skip the 17 stale dups.
3. **Symptoms (2):** ESXi Host NIC Disconnected, Windows Service Down.
4. **Views (16):** SM-free views (11) first; then the 5 SM-consuming views once
   their SMs exist.
5. **Dashboards (13):** "Input dashboards" template first, then the 12
   user-facing dashboards — **each behind its own RULE-011 wireframe approval.**
6. **Alerts (3):** after their symptoms — NIC Disconnected, Windows Service
   Down, License Expiring (inline). No recommendations to author.
7. **Reports (16 VOA `<ReportDef>`):** last, after their embedded dashboards/
   views exist.

**Hard ordering rules:** SMs strictly tier-by-tier; symptom→alert; view-SM→view;
dashboard depends on its views; report depends on its dashboards. Never spawn
two author agents in parallel (UUID/name races).
