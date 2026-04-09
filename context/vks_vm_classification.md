# VKS VM type classification

How to identify and filter different VM types in VCF Operations super
metrics and custom groups. Confirmed on a live VCF 9 lab instance
(2026-04-09).

## VM type property cheat sheet

| VM Category | `summary|config|type` | `summary|config|productName` | Other identifiers |
|---|---|---|---|
| Regular VM | `default` | empty/absent | — |
| Supervisor Control Plane | `SupervisorControlPlane` | `vSphere Supervisor` | — |
| vCLS (Cluster Services) | `SupervisorControlPlane` | absent | `summary|parentFolder = "vCLS"` |
| VKS Worker Node | `VMOperator` | `vSphere Kubernetes Service Cluster Node Image` | `config|name contains "node-pool"` |
| VKS Cluster CP Node | `VMOperator` | `vSphere Kubernetes Service Cluster Node Image` | `config|name` does NOT contain `"node-pool"` |
| VM Service (standalone) | `VMOperator` | empty/absent | — |
| vSphere Pod | N/A (different resource kind) | N/A | `VMWARE/Pod` object, `crxPod1Guest` |

## Key findings

1. **vCLS VMs share `type=SupervisorControlPlane`** with real Supervisor
   CP VMs. Use `summary|parentFolder = "vCLS"` to distinguish them.
   Use `summary|config|productName = "vSphere Supervisor"` for real
   Supervisor CP (vCLS VMs lack productName).

2. **VKS CP and Worker VMs are identical on every structured property.**
   Both have `type=VMOperator` and `productName=vSphere Kubernetes
   Service Cluster Node Image`. The ONLY differentiator is the VM name
   pattern: workers always contain `"node-pool"`, CP VMs never do.
   This is a structural guarantee of the VKS provisioner.

3. **VM Service VMs share `type=VMOperator`** with VKS cluster VMs.
   Distinguish by productName: VKS cluster VMs have the node image
   productName, standalone VM Service VMs have empty/absent productName.

4. **vSphere Pods are a separate resource kind** (`VMWARE/Pod`), not
   `VMWARE/VirtualMachine`. They do not appear in `objecttype=
   VirtualMachine` queries. Use `objecttype=Pod` in super metrics.

5. **No Kubernetes-layer metadata** (namespace, node pool label, TKC
   name, role) is surfaced as a vCenter VM property in Ops. The
   `productName` and VM name pattern are the only clean signals.

## Super metric filter patterns (all verified)

```
# Regular VMs (excludes all special types)
where="summary|config|type equals default"

# Supervisor Control Plane VMs (excludes vCLS)
where="summary|config|productName equals vSphere Supervisor"

# vCLS VMs
where="summary|parentFolder equals vCLS"

# All VKS cluster VMs (CP + Worker)
where="summary|config|productName equals vSphere Kubernetes Service Cluster Node Image"

# VKS Worker nodes only
where="config|name contains node-pool"

# VKS CP nodes only (via subtraction, NOT compound where)
formula: VKS_Node_Image_SM - VKS_Worker_SM

# VM Service VMs only (via subtraction, NOT compound where)
formula: sum(VMOperator type) - VKS_Node_Image_SM

# vSphere Pods (separate resource kind)
objecttype=Pod, metric=config|hardware|num_Cpu
```

## CRITICAL: compound where clause limitation

Compound `&&` where clauses with string operators (`equals`, `contains`)
**silently produce zero data**. See `context/supermetric_authoring.md`
for the full writeup and subtraction pattern.

## PowerShell script equivalence

The reference PowerShell script uses `ManagedBy` extension keys:
- `com.vmware.vcenter.wcp` + no namespace = VKS
- `com.vmware.vim.eam` = Supervisor (ESX Agent Manager)
- `com.vmware.vcenter.wcp` + namespace = VM Service
- `VirtualCenter` = vCLS
- null + namespace = Pods
- null + no namespace = Regular

These map 1:1 to our property-based filters. The script's `Total VM
vCPU` includes Pods (uses Get-VM which returns Pods). Our native
metric `cpu|vcpus_allocated_on_all_vms` also includes Pods.
