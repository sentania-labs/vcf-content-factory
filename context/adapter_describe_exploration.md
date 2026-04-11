# Adapter describe API exploration

Captured 2026-04-10 against vcf-lab-operations.int.sentania.net
(VCF Operations 9.0.2).

## Endpoints

```
GET /suite-api/api/adapterkinds
GET /suite-api/api/adapterkinds/{adapterKindKey}
GET /suite-api/api/adapterkinds/{adapterKindKey}/resourcekinds
GET /suite-api/api/adapterkinds/{adapterKindKey}/resourcekinds/{resourceKindKey}
GET /suite-api/api/adapterkinds/{adapterKindKey}/resourcekinds/{resourceKindKey}/statkeys
GET /suite-api/api/adapterkinds/{adapterKindKey}/resourcekinds/{resourceKindKey}/properties
```

All public (no `X-Ops-API-use-unsupported` needed). Accept
`application/json`. Auth via `OpsToken` bearer.

## Response wrapper key gotcha

The OpenAPI spec documents `stat-key` and `property-key` as the
wrapper keys for statkeys and properties responses. **In practice,
the actual JSON wrapper key is always `resourceTypeAttributes`.**
Tested across VMWARE, VcfAdapter, SupervisorAdapter, Container —
all return `{"resourceTypeAttributes": [...]}`.

Code consuming these endpoints must check for `resourceTypeAttributes`
first, then fall back to `stat-key` / `property-key` for
forward-compatibility.

## Adapter kind list (complete)

| Key | Name | describeVersion | Resource Kind Count |
|---|---|---|---|
| `FederatedAdapter` | Aggregator Adapter | 8 | 2 |
| `VCF_UNIFIED_CONFIG` | Configuration Management | 1 | 1 |
| `Container` | Container | 72 | 29 |
| `DiagnosticsAdapter` | Diagnostics Adapter | 9 | 1 |
| `FDR_vCenter Operations Adapter` | FDR_vCenter Operations Adapter | 1 | 12 |
| `FDR_VirtualAndPhysicalSANAdapter` | FDR_VirtualAndPhysicalSANAdapter | 1 | 2 |
| `FDR_VMWARE` | FDR_VMWARE | 1 | 8 |
| `VMWARE_INFRA_HEALTH` | Infrastructure Health | 8 | 49 |
| `VMWARE_INFRA_MANAGEMENT` | Infrastructure Management | 9 | 3 |
| `ManagementPackBuilderAdapter` | Management Pack Builder | 8 | 1 |
| `NETWORK_INSIGHT` | Networks Adapter | 5 | 4 |
| `NSXTAdapter` | NSX | 47 | 41 |
| `APPOSUCP` | OS and Application Monitoring | 95 | 135 |
| `APPLICATIONDISCOVERY` | Service Discovery Adapter | 55 | 5 |
| `tammpak` | tam-mpak | 1 | 1 |
| `VMWARE` | vCenter | 978 | 25 |
| `VCFAutomation` | VCF Automation for All Apps Organization | 49 | 8 |
| `LogAssistAdapter` | VCF Log Assist Adapter | 8 | 1 |
| `vCenter Operations Adapter` | VCF Operations Adapter | 355 | 16 |
| `vRealizeOpsMgrAPI` | VCF Operations API | 2 | 1 |
| `OrchestratorAdapter` | VCF Operations Orchestrator Adapter | 17 | 4 |
| `VCFOperationsvCommunity` | VCF Operations vCommunity | 1 | 4 |
| `VcfAdapter` | VMware Cloud Foundation | 20 | 4 |
| `VirtualAndPhysicalSANAdapter` | vSAN Adapter | 35 | 12 |
| `VrAdapter` | vSphere Replication Adapter | 2 | 4 |
| `SupervisorAdapter` | vSphere Supervisor | 1 | 10 |

Key adapters for content authoring:
- **`VMWARE`** — the vCenter adapter, by far the largest (v978, 25 RKs)
- **`VcfAdapter`** — VCF/SDDC-level objects (domains, world)
- **`VMWARE_INFRA_HEALTH`** — infrastructure health monitoring (49 RKs covering vCenter, NSX, vSAN, Logs, Automation health)
- **`SupervisorAdapter`** — vSphere Supervisor / VKS (10 RKs)
- **`VirtualAndPhysicalSANAdapter`** — vSAN
- **`NSXTAdapter`** — NSX-T networking
- **`vCenter Operations Adapter`** — Ops self-monitoring (note: key has spaces, must URL-encode)

## Adapter kind entry structure

```json
{
  "key": "VMWARE",
  "name": "vCenter",
  "description": "...",
  "adapterKindType": "GENERAL",
  "describeVersion": 978,
  "identifiers": [],
  "resourceKinds": ["ClusterComputeResource", "Datacenter", ...],
  "links": [...]
}
```

## Resource kind entry structure

```json
{
  "key": "VirtualMachine",
  "name": "Virtual Machine",
  "adapterKind": "VMWARE",
  "adapterKindName": "vCenter",
  "resourceKindType": "GENERAL",
  "resourceKindSubType": "NONE",
  "resourceIdentifierTypes": [
    {"name": "VMEntityObjectID", "dataType": "STRING", "isPartOfUniqueness": true},
    {"name": "VMEntityVCID", "dataType": "STRING", "isPartOfUniqueness": true},
    {"name": "VMEntityName", "dataType": "STRING", "isPartOfUniqueness": false},
    {"name": "VMEntityInstanceUUID", "dataType": "STRING", "isPartOfUniqueness": false},
    {"name": "isPingEnabled", "dataType": "STRING", "isPartOfUniqueness": false},
    {"name": "VMServiceMonitoringEnabled", "dataType": "STRING", "isPartOfUniqueness": false}
  ],
  "links": [...]
}
```

`resourceIdentifierTypes` defines the fields that uniquely identify
a resource instance (the `isPartOfUniqueness: true` subset). These
correspond to `<ResourceIdentifier>` elements in describe.xml.

## VMWARE adapter — resource kinds (complete)

| Key | Name |
|---|---|
| `ClusterComputeResource` | Cluster Compute Resource |
| `CustomDatacenter` | Custom Datacenter |
| `Datacenter` | Datacenter |
| `Datastore` | Datastore |
| `StoragePod` | Datastore Cluster |
| `DatastoreFolder` | Datastore Folder |
| `VM Entity Status` | Entity Status |
| `Folder` | Folder |
| `HostFolder` | Host Folder |
| `HostSystem` | Host System |
| `Namespace` | Legacy Namespace |
| `NamespaceV2` | Namespace |
| `NetworkFolder` | Network Folder |
| `PhysicalDatacenter` | Physical Data Center per Account |
| `Pod` | Pod |
| `ResourcePool` | Resource Pool |
| `SupervisorCluster` | Supervisor Cluster |
| `GuestCluster` | Tanzu Kubernetes Cluster |
| `VMwareAdapter Instance` | vCenter |
| `VirtualMachine` | Virtual Machine |
| `VMFolder` | Virtual Machine Folder |
| `DistributedVirtualPortgroup` | vSphere Distributed Port Group |
| `VmwareDistributedVirtualSwitch` | vSphere Distributed Switch |
| `vSphere Private World` | vSphere Private World |
| `vSphere World` | vSphere World |

## Stat key / property counts

| Adapter | Resource Kind | Statkeys | Properties |
|---|---|---|---|
| VMWARE | VirtualMachine | 930 | 251 |
| VMWARE | HostSystem | 813 | 202 |
| VMWARE | ClusterComputeResource | 897 | 75 |
| VMWARE | Datastore | 362 | 51 |
| VcfAdapter | VCFWorld | 159 | 3 |
| VcfAdapter | VCFDomain | 85 | 11 |
| VMWARE_INFRA_HEALTH | VCF_HEALTH_WORLD | 47 | 3 |
| VMWARE_INFRA_HEALTH | VCF_DOMAIN | 47 | 4 |
| VMWARE_INFRA_HEALTH | VC_APP | 62 | 27 |
| VMWARE_INFRA_HEALTH | VCENTER_HEALTH_WORLD | 47 | 3 |
| SupervisorAdapter | KubernetesNamespace | 68 | 7 |
| SupervisorAdapter | KubernetesNode | 76 | 3 |

## Stat key entry structure (metric)

All fields observed across all tested resource kinds:

| Field | Type | Present | Description |
|---|---|---|---|
| `key` | string | always | Metric key, e.g. `cpu\|usage_average` |
| `name` | string | always | Display name, e.g. `CPU\|Usage` |
| `description` | string | always | Human-readable description |
| `defaultMonitored` | boolean | always | Whether collected by default in the Default Policy |
| `rollupType` | string | always | `AVG`, `MAX`, `MIN`, `SUM`, `LATEST` |
| `instanceType` | string | always | Always `INSTANCED` in practice |
| `unit` | string | when applicable | Unit string, e.g. `%`, `KB`, `ms`, `KBps`, `US$/Month` |
| `dataType` | string | sometimes | Legacy type hint, e.g. `INTEGER`, `STRING` |
| `dataType2` | string | always | Canonical type: `FLOAT`, `INTEGER`, or `STRING` |
| `monitoring` | boolean | always | Always `false` in API output |
| `property` | boolean | always | `false` for statkeys, `true` for properties |

`dataType` is only present when it differs from the default
(`FLOAT`). It appears on `INTEGER` and `STRING` typed entries.
`dataType2` is always present and is the authoritative type.

### VM statkey dataType2 distribution

| dataType2 | Count |
|---|---|
| FLOAT | 890 |
| INTEGER | 37 |
| STRING | 3 |

### VM statkey rollupType distribution

| rollupType | Count |
|---|---|
| AVG | 849 |
| LATEST | 46 |
| MAX | 23 |
| SUM | 10 |
| MIN | 2 |

### VM statkey defaultMonitored distribution

| defaultMonitored | Count |
|---|---|
| true | 287 |
| false | 643 |

## Verbatim sample entries

### Statkey — numeric with unit (VirtualMachine)

```json
{
  "key": "net|receive_demand_average",
  "name": "Network|Data Receive Demand Rate",
  "description": "Data Receive Demand Rate",
  "defaultMonitored": false,
  "rollupType": "AVG",
  "instanceType": "INSTANCED",
  "unit": "KBps",
  "dataType2": "FLOAT",
  "monitoring": false,
  "property": false
}
```

### Statkey — numeric without unit (VirtualMachine)

```json
{
  "key": "mem-host|consumer.count_whatif",
  "name": "Memory Usage on Host|Number of Capacity consumers with committed projects",
  "description": "Number of Capacity consumers with committed projects",
  "defaultMonitored": false,
  "rollupType": "AVG",
  "instanceType": "INSTANCED",
  "dataType2": "FLOAT",
  "monitoring": false,
  "property": false
}
```

### Statkey — INTEGER type (HostSystem)

```json
{
  "key": "System Attributes|new_ki_alarms",
  "name": "VCF Operations Generated|Self - New KPI Breach Count",
  "description": "Self - New KPI Breach Count",
  "defaultMonitored": false,
  "rollupType": "AVG",
  "instanceType": "INSTANCED",
  "dataType": "INTEGER",
  "dataType2": "INTEGER",
  "monitoring": false,
  "property": false
}
```

### Statkey — VCF health metric (VCFWorld)

```json
{
  "key": "vcfHealth|ntp|esxi|not_configured",
  "name": "VCF Health|NTP Issues|ESX Host|NTP Not Configured Count",
  "description": "NTP Not Configured Count",
  "defaultMonitored": true,
  "rollupType": "AVG",
  "instanceType": "INSTANCED",
  "dataType": "INTEGER",
  "dataType2": "INTEGER",
  "monitoring": false,
  "property": false
}
```

### Property — STRING type (VirtualMachine)

```json
{
  "key": "config|faultTolerant",
  "name": "Configuration|Fault Tolerant",
  "description": "Fault tolerance enabled",
  "defaultMonitored": true,
  "rollupType": "AVG",
  "instanceType": "INSTANCED",
  "dataType": "STRING",
  "dataType2": "STRING",
  "monitoring": false,
  "property": true
}
```

### Property — numeric with unit (HostSystem)

```json
{
  "key": "gpu|power_limit",
  "name": "GPU|GPU Power limit (Max TDP)",
  "description": "GPU Power limit (Max TDP)",
  "defaultMonitored": true,
  "rollupType": "AVG",
  "instanceType": "INSTANCED",
  "unit": "W",
  "dataType2": "FLOAT",
  "monitoring": false,
  "property": true
}
```

### Property — VCF domain (VCFDomain)

```json
{
  "key": "configuration|DomainState",
  "name": "Configuration|DomainState",
  "description": "Current state of a VCF domain",
  "defaultMonitored": true,
  "rollupType": "AVG",
  "instanceType": "INSTANCED",
  "dataType": "STRING",
  "dataType2": "STRING",
  "monitoring": false,
  "property": true
}
```

### Property — infra health (VC_APP)

```json
{
  "key": "CONNECTIVITY|API|STATE",
  "name": "Connectivity|API|State",
  "description": "State",
  "defaultMonitored": true,
  "rollupType": "AVG",
  "instanceType": "INSTANCED",
  "dataType": "STRING",
  "dataType2": "STRING",
  "monitoring": false,
  "property": true
}
```

## VcfAdapter — resource kinds (complete)

| Key | Name |
|---|---|
| `PhysicalDatacenter` | Physical Data Center per Account |
| `VCFDomain` | VCF Domain |
| `VCFWorld` | VCF World |
| `VcfAdapterInstance` | VMware Cloud Foundation |

## VMWARE_INFRA_HEALTH — resource kinds (complete)

| Key | Name |
|---|---|
| `ARIA_AUTO_APP` | Automation App |
| `CAS_HEALTH_WORLD` | Automation Health |
| `AUTOMATION_NODE_INSTANCE` | Automation Node |
| `CAS_HEALTH_SERVICES` | Automation Service |
| `VCENTER_BACKUP_JOB` | Backup Job |
| `LicenseUsage` | License |
| `LICENSE_USAGE_WORLD` | License Usage |
| `LicensedAsset` | Licensed Asset |
| `LicensedVC` | Licensed vCenter |
| `VCF_LCM_HEALTH_WORLD` | Lifecycle Manager Health |
| `ARIA_LIFECYCLE_APP` | LifecycleManager App |
| `ARIA_LOGS_APP` | Logs App |
| `ARIA_LOGS_HEALTH_WORLD` | Logs Health |
| `ARIA_NETWORKS_APP` | Networks App |
| `ARIA_NETWORKS_COLLECTOR_NODE` | Networks Collector Node |
| `ARIA_NETWORKS_WORLD` | Networks Health |
| `ARIA_NETWORKS_PLATFORM_NODE` | Networks Platform Node |
| `ARIA_NETWORKS_SERVICE` | Networks Service |
| `NSX_T_APP` | NSX App |
| `NSX_BACKUP_JOB` | NSX Backup Job |
| `NSXT_HEALTH_WORLD` | NSX-T Health |
| `ARIA_OPS_APP` | Operations App |
| `ARIA_OPS_WORLD` | Operations Health |
| `VRO_APP` | Orchestrator App |
| `VRO_HEALTH_WORLD` | Orchestrator Health |
| `SDDC_MANAGER_APP` | SDDC Manager App |
| `SDDC_MANAGER_BACKUP_JOB` | SDDC Manager Backup Job |
| `SDDC_MANAGER_SERVICE` | SDDC Manager Service |
| `SRM_APP` | SRM App |
| `SRM_HEALTH_WORLD` | SRM Health |
| `VC_APP` | vCenter App |
| `VCENTER_APPLIANCE_HEALTH_SERVICES` | vCenter Appliance Service |
| `VCENTER_BACKUP_JOBS` | vCenter Backup Jobs |
| `VCENTER_HEALTH_WORLD` | vCenter Health |
| `vCenterLicensing` | vCenter Licensing |
| `vCenterLicense` | vCenter Licensing Group |
| `VCENTER_NTP_SERVER` | vCenter NTP Server |
| `VCENTER_HEALTH_SERVICES` | vCenter Service |
| `VCF_DEPLOYMENT` | VCF Deployment |
| `VCF_DOMAIN` | VCF Domain |
| `VCF_HEALTH_WORLD` | VCF Health |
| `VCF_LOG_INSIGHT_NODE` | VCF Log Insight Node |
| `VIDM_APP` | vIDM App |
| `VIDM_HEALTH_WORLD` | vIDM Health |
| `VMWARE_INFRA_HEALTH_WORLD` | VMware Infrastructure Health |
| `VMWARE_INFRA_HEALTH_INSTANCE` | VMware Infrastructure Health Adapter Instance |
| `VSAN_APP` | vSAN App |
| `VSAN_HEALTH_WORLD` | vSAN Health |
| `VSAN_HEALTH_SERVICES` | vSAN Service |

## SupervisorAdapter — resource kinds (complete)

| Key | Name |
|---|---|
| `KubernetesContainer` | Kubernetes Container |
| `KubernetesDaemonset` | Kubernetes DaemonSet |
| `KubernetesDeployment` | Kubernetes Deployment |
| `KubernetesNamespace` | Kubernetes Namespace |
| `KubernetesNode` | Kubernetes Node |
| `KubernetesPod` | Kubernetes Pod |
| `KubernetesStatefulset` | Kubernetes StatefulSet |
| `GuestCluster` | VKS Cluster |
| `SupervisorCluster` | vSphere Supervisor |
| `SupervisorWorld` | vSphere Supervisor World |

## VCF Operations Adapter — resource kinds (complete)

Note: adapter key is `vCenter Operations Adapter` (with spaces;
URL-encode as `vCenter%20Operations%20Adapter`).

| Key | Name |
|---|---|
| `vCenter Operations Adapter Instance` | VCF Operations Adapter Instance |
| `vC-Ops-Analytics` | VCF Operations Analytics |
| `vC-Ops-CaSA` | VCF Operations CaSA |
| `Cloud-Proxy` | VCF Operations Cloud Proxy |
| `vC-Ops-Cluster` | VCF Operations Cluster |
| `vC-Ops-Collector` | VCF Operations Collector |
| `vC-Ops-Controller` | VCF Operations Controller |
| `vC-Ops-Fsdb` | VCF Operations Fsdb |
| `Log-Forwarder` | VCF Operations Log Forwarder |
| `vC-Ops-ManagementPack` | VCF Operations Management Pack |
| `vC-Ops-ManagementPackGroup` | VCF Operations Management Pack Group |
| `vC-Ops-Node` | VCF Operations Node |
| `vC-Ops-Persistence` | VCF Operations Persistence |
| `vC-Ops-Product-UI` | VCF Operations Product UI |
| `vC-Ops-Suite-API` | VCF Operations Suite API |
| `vC-Ops-Watchdog` | VCF Operations Watchdog |

## Key observations

1. **The API is the JSON representation of describe.xml.** Each
   entry in `resourceTypeAttributes` corresponds to a
   `<ResourceAttribute>` element in the adapter's describe.xml.
   The field mapping is direct: `key` = attribute key,
   `rollupType` = rollup type, `defaultMonitored` = whether the
   attribute is in the default monitoring policy, `property` =
   whether it's a property (vs. a metric/statkey).

2. **`property: true` vs `property: false`** is the discriminator
   between the `/statkeys` and `/properties` endpoints. Both
   endpoints return the same JSON schema; only the `property`
   boolean differs. Properties are configuration attributes
   (strings, enums), statkeys are time-series metrics.

3. **`unit` is optional.** Many metrics (especially capacity
   analytics, badge scores, and integer counts) lack a unit field.

4. **`dataType` vs `dataType2`.** `dataType2` is always present
   and is the canonical type (`FLOAT`, `INTEGER`, `STRING`).
   `dataType` is only present when the type is non-default (i.e.,
   `INTEGER` or `STRING`). For `FLOAT` metrics, `dataType` is
   absent. Consumer code should use `dataType2`.

5. **`instanceType` is always `INSTANCED`.** No examples of
   `AGGREGATE` or other values found in the API output, even though
   the describe.xml schema supports them. This may be a
   serialization artifact — the API may not distinguish.

6. **`monitoring` is always `false`.** This field appears to be
   inert in the API representation; the actual monitoring state
   is controlled by policy configuration, not the describe catalog.

7. **Metric key naming conventions** follow a `group|metric`
   pattern with `|` as separator. Subgroups use additional `|`
   levels (e.g., `vcfHealth|ntp|esxi|not_configured`). The
   `name` field uses the same pattern with human-readable group
   names.

8. **`defaultMonitored` is the policy-default flag.** ~30% of VM
   statkeys are `defaultMonitored: true`. This is the initial
   state in the Default Policy; actual collection depends on
   policy configuration.

9. **Adapter key casing matters.** `VMWARE` is all-caps,
   `VcfAdapter` is mixed-case, `vCenter Operations Adapter` has
   spaces. URL-encode adapter keys with special characters.
