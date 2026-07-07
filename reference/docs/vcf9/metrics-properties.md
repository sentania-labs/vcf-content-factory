# metrics-properties (VCF 9.0, pages 4242-4507)


---
## page 4242

 VMware Cloud Foundation 9.0
Where You Customize Adapter Type Icons
From the left menu, click Administration > Control Panel, and then click the Icons tile. Click the Adapter Type Icons
tab.
Table 1256: Adapter Type Icons Options
Option Description
Toolbar options Manages the selected icon.
• Upload uploads a PNG file to uniquely identify the adapter type.
• Assign Default icons returns the selection to the original icon.
Name Name of the type of adapter.
Icon Pictorial representation of the type of adapter.
Related Links
Customize an Adapter Type Icon on page 4241
You can use the default icons that VCF Operations provides, or you can upload your own graphics file for an adapter type.
When you change an icon, your changes take effect for all users.
Customizing Icons on page 4240
Every object or adapter in your environment has an icon representation. You can customize how the icon appears.
Allocate More Virtual Memory to VCF Operations
You might need to add virtual memory to keep the VCF Operations process running.
When the VCF Operations virtual machine requests more memory than is available, the Linux kernel might kill the
vcops-analytics process, and the product might become unresponsive. If that happens, use the reservation feature in
vSphere to specify the guaranteed minimum memory allocation for VCF Operations virtual machines.
1. In the vSphere Client inventory, right-click the VCF Operations virtual machine and select Edit Settings.
2. Click the Resources tab, and select Memory.
3. Use the Reservation option to allocate more memory.
Viewing Metrics and Properties
VCF Operations provides definitions for the metrics and properties, defined on objects in your environment.
Metric Definitions in VCF Operations
Metric definitions provide an overview of how the metric value is calculated or derived. If you understand the metric, you
can better tune VCF Operations to display results that help you to manage your environment.
VCF Operations collects data from objects in your environment. Each piece of data collected is called a metric observation
or value. VCF Operations uses the VMware vCenter adapter to collect raw metrics. VCF Operations uses the VCF
Operations adapter to collect self-monitoring metrics. In addition to the metrics it collects, VCF Operations calculates
capacity metrics, badge metrics, and metrics to monitor the health of your system.
All metric definitions are provided. The metrics reported on your system depend on the objects in your environment. You
can use metrics to help troubleshoot problems.
VMware by Broadcom  4242

---
## page 4243

 VMware Cloud Foundation 9.0
Metrics for vCenter Components
VCF Operations connects to VMware vCenter® instances through the vCenter adapter to collect metrics for vCenter
components and uses formulas to derive statistics from those metrics. You can use metrics to troubleshoot problems in
your environment.
vCenter components are listed in the describe.xml file for the vCenter adapter. The following example shows sensor
metrics for the host system in the describe.xml file.
<ResourceGroup instanced="false" key="Sensor" nameKey="1350" validation="">
    <ResourceGroup instanced="false" key="fan" nameKey="1351" validation="">
        <ResourceAttribute key="currentValue" nameKey="1360" dashboardOrder="1" dataType="float"  defaultMoni-
tored="false"   isDiscrete="false" isRate="false" maxVal="" minVal=""  unit="percent"/>
        <ResourceAttribute key="healthState" nameKey="1361" dashboardOrder="1" dataType="float"  defaultMoni-
tored="false"   isDiscrete="false" isRate="false" maxVal="" minVal="" />
    </ResourceGroup>
    <ResourceGroup instanced="false" key="temperature" nameKey="1352" validation="">
        <ResourceAttribute key="currentValue" nameKey="1362" dashboardOrder="1" dataType="float"  defaultMoni-
tored="false"   isDiscrete="false" isRate="false" maxVal="" minVal="" />
        <ResourceAttribute key="healthState" nameKey="1363" dashboardOrder="1" dataType="float"  defaultMoni-
tored="false"   isDiscrete="false" isRate="false" maxVal="" minVal="" />
    </ResourceGroup>
 </ResourceGroup>
Each ResourceAttribute element includes the name of a metric that appears in the UI and is documented as a Metric
Key.
Table 1257: Sensor Metrics for Host System Cooling
Metric Key Metric Name Description
Sensor|fan|currentValue Speed Fan speed.
Sensor|fan|healthState Health State Fan health state.
Sensor|temperature|currentValue Temperature Host system temperature.
Sensor|temperature|healthState Health State Host system health state.
vSphere Metrics
VCF Operations collects CPU use, disk, memory, network, and summary metrics for objects in the vSphere world.
Capacity metrics can be calculated for vSphere world objects. See Capacity Analytics Generated Metrics.
vSphere World Super Metrics for ROI Dashboard
vSphere world super metrics provide information about the new metrics added to the ROI dashboard.
Metric Name Description
Cost|Total Cost of Ownership This metric shows the total cost cost of ownership with potential savings and
optimizations.
Key: cost|total_aggregated_cost
Online Capacity Analytics Capacity
Remaining Profiles
This metric shows the VMs remaining based on the average VM profile.
Key: OnlineCapacityAnalytics|capacityRemainingProfile
VMware by Broadcom  4243

---
## page 4244

 VMware Cloud Foundation 9.0
Metric Name Description
Cost|Server Hardware(Owned) Cost This metric shows the sum of server hardware depreciated cost having purchase type
as Owned across all the vCenters.
Key: cost|total_serverHardware_owned_cost
Cost|Server Hardware(Leased) Cost This metric shows the sum of server hardware depreciated cost having purchase type
as Leased across all the vCenters.
Key: cost|total_serverHardware_leased_cost
Cost|Host OS License cost This metric shows the sum of host OS license cost across all the vCenters.
Key: cost|total_hostOsl_cost
Cost|Network Cost This metric shows the sum of network cost across all the vCenters.
Key: cost|total_network_cost
Cost|Maintenance Cost This metric shows the sum of maintenance cost across all the vCenters.
Key: cost|total_maintenance_cost
Cost|Server Labor Cost This metric shows the sum of server labor cost across all the vCenters.
Key: cost|total_serverLabor_cost
Cost|Facilities Cost This metric shows the sum of facilities cost across all the vCenters.
Key: cost|total_facilities_cost
Cost|Additional Cost This metric shows the sum of additional cost across all the vCenters.
Key: cost|total_additional_cost
Cost|VM Direct Cost This metric shows sum of direct Cost (VI labor + OS Labor) across all vCenters.
Key: cost|total_vm_direct_cost
Cost|Capacity Used Compute Cost This metric displays the cost of the used compute capacity.
Key: cost|capacity_used|compute
Cost|Capacity Remaining Compute Cost This metric displays the cost of the remaining compute capacity.
Key: cost|capacity_remaining|compute
Cost|Capacity Used Storage Cost This metric displays the cost of the used storage capacity.
Key: cost|capacity_used|storage
Cost|Capacity Remaining Storage Cost This metric displays the cost of the remaining storage capacity.
Key: cost|capacity_remaining|storage
Cost|Potential Savings Idle VMs This metric displays the potential savings from Idle VMs.
Key: cost|potential_savings|idle_vms
Cost|Potential Savings Powered Off VMs This metric displays the potential savings from powered off VMs.
Key: cost|potential_savings|poweredOff_vms
Cost|Potential Savings VM Snapshots This metric displays the potential savings from VM snapshots.
Key: cost|potential_savings|vm_snapshots
Cost|Potential Savings Orphaned Disks This metric displays the potential savings from orphaned disks.
Key: cost|potential_savings|orphaned_disks
Cost|Potential Savings Oversized VMs This metric displays the potential savings from oversized VMs.
Key: cost|potential_savings|oversized_vms
Cost|Potential Savings Cost Optimization
Opportunities
This metric displays the potential savings from cost optimization opportunities.
Key: cost|potential_savings|cost_optimization_opportunities
Cost|Total Cost of Ownership This metric shows the total cost cost of ownership with potential savings and
optimizations.
Key: cost|potential_savings|total_cost_of_ownership
Server Purchase Cost This metric shows the server purchase cost.
VMware by Broadcom  4244

---
## page 4245

 VMware Cloud Foundation 9.0
Metric Name Description
Key: cost|server_purchase_cost
Accumulated Depreciation This metric displays the sum of the accumulated depreciation (Depreciation is
calculated from the purchase date till current date) of servers across all the vCenters.
Key: cost|accumulatedDepreciation
Remaining Depreciation This metric displays the sum of the remaining depreciation (Remaining Depreciation
is calculated from the current date till Depreicated year) of servers across all the
vCenters.
Key: cost|accumulatedDepreciation
Number of Fully Depreciated Servers This metric displays the number of fully depreciated servers across all the vCenters.
Key: cost|hardwareTotalCost
Reclaimed vCPUs from Idle VMs This metric displays the number of reclaimable vCPUs from idle VMs.
Key: reclaimable|idle_vms|cpu
Reclaimed Memory from Idle VMs This metric displays the amount of reclaimable memory from the idle VMs.
Key: reclaimable|idle_vms|mem
Reclaimed Disk Space from Idle VMs This metric displays the amount of reclaimable disk space from the idle VMs.
Key: reclaimable|idle_vms|diskspace
Reclaimed Disk Space from Powered Off VMs This metric displays the amount of reclaimable disk space from the powered off VMs.
Key: reclaimable|poweredOff_vms|diskspace
Reclaimed Disk Space from VM Snapshots This metric displays the amount of reclaimable disk space from the VM Snapshots.
Key: reclaimable|vm_snapshots|diskspace
Reclaimed Disk Space from Orphaned Disks This metric displays the amount of reclaimable disk space from the orphaned disks.
Key: reclaimable|orphaned_disk|diskspace
Rightsize - vCPUs to Remove from Oversized
VMs
This metric displays the number of vCPUs to remove from the oversized VMs.
Key: summary|oversized|vcpus
Rightsize - Memory to Remove from
Oversized VMs
This metric displays the amount of memory to be removed from the oversized VMs.
Key: summary|oversized|memory
Rightsize - vCPUs to Add from Undersized
VMs
This metric displays the number of vCPUs to be added from the undersized VMs.
Key: summary|undersized|vcpus
Rightsize - Memory to Add from Undersized
VMs
This metric displays the amount of memory to be added from the undersized VMs.
Key: summary|undersized|memory
Total Storage Cost This metric displays the sum of storage cost across all vCenters.
Key: cost|totalCost
Total Potential Savings This metric displays the sum of all the potential savings (Idle VMs + Powered off Vms
+ Snapshot + Orphaned Disks + Oversized VMs).
Key: reclaimable|cost
New vSphere Metrics Added for ROI Dashboard
Potential Savings from Oversized VMs This metric displays the sum of all the potentials savings gained from oversized VMs
across vcenters.
Key: cost|reclaimableCost
Reclaimable Host Cost This metric displays the reclaimable host cost based on the recommended size.
Key: cost|potential_savings|total_reclaimable_host_cost
Cost|Potential Increase|Undersized VMs Cost This metric displays the rightsizing value for the undersized VMs.
Key: cost|potential_increase|undersized_vms
Cost|Realized Savings|Total Realized Savings This metric displays the total realize savings for VMs across all vCenters.
VMware by Broadcom  4245

---
## page 4246

 VMware Cloud Foundation 9.0
Metric Name Description
Key: cost|realized_savings|total_realized_savings
Cost|Realized Savings|Idle Savings This metric displays the total realized savings for idle VMs across all vCenters.
Key: cost|realized_savings|realized_idle_savings
Cost|Realized Savings|Powered Off Savings This metric displays the total realized savings for powered off VMs across all vCenters.
Key: cost|realized_savings|realized_poweredOff_savings
Cost|Realized Savings|Snapshot Space
Savings
This metric displays the total realized savings for snapshot space across all vCenters.
Key: cost|realized_savings|realized_snapshotSpace_savings
Cost|Realized Savings|Oversized Savings This metric displays the oversized savings across all vCenters.
Key: cost|realized_savings|realized_oversized_savings
Cost|Realized Savings|Orphaned Disk Space
Savings
This metric displays the amount of disk space saved by orphaned disks across all
vCenters.
Key: cost|realized_savings|realized_orphanedDiskSpace_savings
Cost|Realized Savings|Reclaimable Host
Savings
This metric displays the amount of reclaimable host savings across all vCenters.
Key: cost|realized_savings|realized_reclaimableHost_savings
Compute Realized|vCPUs from Oversized
VMs
This metric displays the number of vCPUs realized across all vCenters.
Key: compute_realized|realized_oversized_vcpus
Compute Realized|Memory from Oversized
VMs
This metric displays the amount of memory realized from oversized VMs across all
vCenters.
Key: compute_realized|realized_oversized_mem
Realized Potential Memory Consumed from
Oversized VMs
This metric displays the potential memory consumed from oversized VMs across all
vCenters.
Key: realized|realizedPotentialMemConsumed
Total Number Of Reclaimable Hosts This metric displays the total number of reclaimable hosts across all vCenters.
Key: metric=cost|reclaimableHostCost
Compute Realized|vCPUs from Idle VMs This metric displays the realized vCPUs from idle VMs across all vCenters.
Key: compute_realized|realized_idle_vcpus
Compute Realized|Memory from Idle VMs This metric displays the amount of memory realized from idle VMs across all vCenters.
Key: compute_realized|realized_idle_mem
Disk Space Realized|Idle VMs This metric displays the amount of disk space realized from idle VMs across all
vCenters.
Key: storage_realized|realized_idle_diskSpace
Disk Space Realized|Powered Off VMs This metric displays the amount of disk space realized from powered off VMs across
all vCenters.
Key: storage_realized|realized_poweredOff_diskSpace
Disk Space Realized|VM Snapshots This metric displays the amount of disk space realized from VM snapshots across all
vCenters.
Key: storage_realized|realized_snapshotSpace
Disk Space Realized|Orphaned Disks This metric displays the amount of disk space realized from orphaned disks across all
vCenters.
Key: storage_realized|realized_orphaned_diskSpace
CPU Usage Metrics
CPU usage metrics provide information about CPU use.
VMware by Broadcom  4246

---
## page 4247

 VMware Cloud Foundation 9.0
Metric Name Description
CPU|Capacity usage CPU usages as a percent during the interval.
Key: cpu|capacity_usagepct_average
CPU|CPU contention(%) This metric shows the percentage of time the VMs in the ESXi hosts are unable to run
because they are contending for access to the physical CPUs. The number shown
is the average number for all VMs. This number is lower than the highest number
experienced by the VM most impacted by CPU contention.
Use this metric to verify if the host can serve all its VMs efficiently. Low contention
means that the VM can access everything it demands to run smoothly. It means that
the infrastructure is providing good service to the application team.
When using this metric, ensure that the number is within your expectation. Look at
both the relative number and the absolute number. Relative means a drastic change
in value, meaning that the ESXi is unable to serve the VMs. Absolute means that the
real value itself is high. Investigate why the number is high. One factor that impacts
this metric is CPU Power Management. If CPU Power Management clocks down the
CPU speed from 3 GHz to 2 GHz, the reduction in speed is accounted for because it
shows that the VM is not running at full speed.
This metric is calculated in the following way: cpu|capacity_contention / (200 *
summary|number_running_vcpus)
Key: cpu|capacity_contentionPct
CPU|Demand (%) This metric shows the amount of CPU resources a virtual machine might use if there
were no CPU contention or CPU limit. This metric represents the average active CPU
load for the past five minutes.
Keep this number below 100% if you set the power management to maximum.
This metric is calculated in the following way: ( cpu.demandmhz /
cpu.capacity_provisioned)*100
Key: cpu|demandPct
CPU|Demand (MHz) This metric shows the amount of CPU resources a virtual machine might use if there
were no CPU contention or CPU limit.
Key: cpu|demandmhz
CPU|Demand CPU demand in megahertz.
Key: cpu|demand_average
CPU|IO wait IO wait (ms).
Key: cpu|iowait
CPU|number of CPU Sockets Number of CPU sockets.
Key: cpu|numpackages
CPU|Overall CPU Contention Overall CPU contention in milliseconds.
Key: cpu|capacity_contention
CPU|Provisioned Capacity (MHz) Capacity in MHz of the physical CPU cores.
Key: cpu|capacity_provisioned
CPU|Provisioned vCPU(s) Number of provisioned CPU cores.
Key: cpu|corecount_provisioned
CPU|Reserved Capacity (MHz) Total CPU capacity reserved by virtual machines.
Key: cpu|reservedCapacity_average
CPU|Usage (MHz) CPU usages, as measured in megahertz, during the interval.
• VM - Amount of actively used virtual CPU. This is the host's view of the CPU
usage, not the guest operating system view.
VMware by Broadcom  4247

---
## page 4248

 VMware Cloud Foundation 9.0
Metric Name Description
• Host - Sum of the actively used CPU of all powered on virtual machines on a host.
The maximum possible value is the frequency of the two processors multiplied by
the number of processors. For example, if you have a host with four 2 GHz CPUs
running a virtual machine that is using 4000 MHz, the host is using two CPUs
completely: 400 / (4 2000) = 0.50
Key: cpu|usagemhz_average
CPU|Wait Total CPU time spent in wait state. The wait total includes time spent in the CPU Idle,
CPU Swap Wait, and CPU I/O Wait states.
Key: cpu|wait
CPU|Workload (%) Percent of workload
Key: cpu|workload
Memory Metrics
Memory metrics provide information about memory use and allocation.
Metric Name Description
mem|Contention (%) This metric shows the percentage of time VMs are waiting to access swapped
memory.
Use this metric to monitor ESXi memory swapping. A high value indicates that the
ESXi is running low on memory, and a large amount of memory is being swapped.
Key: mem|host_contentionPct
mem|Machine Demand (KB) Host memory demand in kilobytes.
Key: mem|host_demand
mem|Provisioned Memory Provisioned host memory in kilobytes.
Key: mem|host_provisioned
mem|Reserved Capacity (KB) Total amount of memory reservation used by powered-on virtual machines and
vSphere services on the host.
Key: mem|reservedCapacity_average
mem|Usable Memory (KB) Usable host memory in kilobytes.
Key: mem|host_usable
mem|Host Usage (KB) Host memory use in kilobytes.
Key: mem|host_usage
mem|Usage/Usable (%) Memory usage as percentage of total configured or available memory.
Key: mem|host_usagePct
mem|Workload (%) Percent of workload.
Key: mem|workload
Network Metrics
Network metrics provide information about network performance.
Metric Name Description
net|Packets Dropped (%) This metric shows the percentage of received and transmitted packets dropped in the
collection interval.
Use this metric to monitor the reliability and performance of the ESXi network. A high
value indicates that the network is not reliable and performance decreases.
VMware by Broadcom  4248

---
## page 4249

 VMware Cloud Foundation 9.0
Metric Name Description
Key: net|droppedPct
net|Usage Rate (KB per second) Sum of the data transmitted and received for all of the NIC instances of the host or
virtual machine.
Key: net|usage_average
net|Workload (%) Percent of workload.
Key: net|workload
Disk Metrics
Disk metrics provide information about disk use.
Metric Name Description
disk|Total IOPS Average number of commands issued per second during the collection cycle.
Key: disk|commandsAveraged_average
disk|Usage Rate (KB per second) Average of the sum of the data read and written for all of the disk instances of the
host or virtual machine.
Key: disk|usage_average
disk|Workload (%) Percent of workload.
Key: disk|workload
Summary Metrics
Summary metrics provide information about overall performance.
Metric Name Description
summary|Number of Running Hosts Number of running hosts.
Key: summary|number_running_hosts
summary|Number of Running VMs This metric shows the number of running VMs at a given point in time. The data is
sampled every five minutes.
A large number of running VMs might be a reason for CPU or memory spikes
because more resources are used in the host. The number of running VMs gives you
a good indicator of how many requests the ESXi host must juggle. Powered off VMs
are not included because they do not impact ESXi performance. A change in the
number of running VMs can contribute to performance problems. A high number of
running VMs in a host also means a higher concentration risk, because all the VMs
fail if the ESXi crashes.
Use this metric to look for a correlation between spikes in the running VMs and
spikes in other metrics such as CPU contention, or memory contention.
Key: summary|number_running_vms
summary|Number of Clusters Total number of clusters.
Key: summary|total_number_clusters
summary|Total Number of Datastores Total number of datastores.
Key: summary|total_number_datastores
summary|Number of Hosts Total number of hosts.
Key: summary|total_number_hosts
summary|Number of VMs Total number of virtual machines.
Key: summary|total_number_vms
VMware by Broadcom  4249

---
## page 4250

 VMware Cloud Foundation 9.0
Metric Name Description
summary|Total Number of Datacenters Total number of data centers.
Key: summary|total_number_datacenters
summary|Number VCPUs on Powered on VMs Number of virtual CPUs on powered-on virtual machines.
Key: summary|number_running_vcpus
summary|Average Running VM Count per
Running Host
Average running virtual machine count per running host.
Key: summary|avg_vm_density
summary|Number of Reclaimable Hosts Displays the number of reclaimable hosts.
Key: summary|total_number_reclaimable_hosts
Virtual Machine Operations Metrics for vSphere World
VM operations metrics provide information about the actions performed on VMs. The following are some important points
you must know about VM operation metrics for vSphere World.
• VM operations metrics is not collected for custom data centers.
• If you edit a VM settings and do not perform any action, still it is considered as VM reconfigure operation.
• During Revert Snapshot, VMs are powered-off, but this operation is not counted under VM Power-off metric.
• Adding ESXi with VMs is not counted under VM Create metric.
• Removing ESXi with VMs is not coutned under VM Remove metric.
• VM hardstop operation is not counted under VM Power Off metric.
Metric Name Description
Inventory
VM Clone This metric displays the number of clone operations on the virtual
machine.
Key: Inventory|VM Clone
VM Create This metric displays the number of create operations on the virtual
machine.
Key: Inventory|VM Create
VM Delete This metric displays the number of delete operations on the virtual
machine.
Key: Inventory|VM Delete
VM Reconfigure This metric displays the number of reconfigure operations on the
virtual machine.
Key: Inventory|VM Reconfigure
VM Register This metric displays the number of register operations on the
virtual machine.
Key: Inventory|VM Register
VM Template Deploy This metric displays the number templates deployed on the virtual
machine.
Key: Inventory|VM Template Deploy
VM Unregister This metric displays the number of unregister operations on the
virtual machine.
Key: Inventory|VM Unregister
Location
VMware by Broadcom  4250

---
## page 4251

 VMware Cloud Foundation 9.0
Metric Name Description
Storage vMotion This metric displays the number of migrations with vMotion
(datastore change operations for Powered-on VMs).
Key: Location|Storage vMotion
VM Datastore Change (powered-off VMs) This metric displays the number of datastore change operations,
for powered-off and suspended virtual machines.
Key: Location|VM Datastore Change (powered-off VMs)
VM Host and Datastore Change (powered-off VMs) This metric displays the number of host and datastore change
operations, for powered-off and suspended virtual machines.
Key: Location|VM Host and Datastore Change (powered-off VMs)
VM Host and Datastore Change (powered-on VMs) This metric displays the number of host and datastore change
operations, for powered-on and suspended virtual machines.
Key: Location|VM Host and Datastore Change (powered-on VMs)
VM Host Change (powered-off VMs) This metric displays the number of host change operations, for
powered-off and suspended virtual machines.
Key: Location|VM Host Change (powered-off VMs)
vMotion This metric displays the number of migrations with vMotion (host
change operations for powered-on VMs).
Key: Location|vMotion
State
VM Guest Reboot This metric displays the number of reboot operations on the virtual
machine guest.
Key: State|VM Guest Reboot
VM Guest Shutdown This metric displays the number of shutdown operations on the
virtual machine guest.
Key: State|VM Guest Shutdown
VM Power Off This metric displays the number of power-off operations on the
virtual machine.
Key: State|VM Power Off
VM Power On This metric displays the number of power-on operations on the
virtual machine.
Key: State|VM Power On
VM Reset This metric displays the number of reset operations on the virtual
machine guest.
Key: State|VM Reset
VM Standby Guest This metric displays the number of standby operations on the
virtual machine guest.
Key: State|VM Standby Guest
VM Suspend This metric displays the number of suspend operations on the
virtual machine.
Key: State|VM Suspend
vCenter Server Metrics
VCF Operations collects CPU use, disk, memory, network, and summary metrics for vCenter Server system objects.
vCenter Server metrics include capacity and badge metrics. See definitions in:
VMware by Broadcom  4251

---
## page 4252

 VMware Cloud Foundation 9.0
• Capacity Analytics Generated Metrics
• Badge Metrics
CPU Usage Metrics
CPU usage metrics provide information about CPU use.
Metric Name Description
Capacity Usage (%) Percent capacity used.
Key: cpu|capacity_usagepct_average
CPU Contention (%) Percent CPU contention.
Key: cpu|capacity_contentionPct
Demand (%) Percent demand.
Key: cpu|demandPct
Demand (MHz) CPU utilization level based on descendant virtual machines utilization. This
Includes reservations, limits, and overhead to run the virtual machines.
Key: cpu|demandmhz
Demand CPU Demand.
Key: cpu|demand_average
IO Wait (ms) IO wait time in milliseconds.
Key: cpu|iowait
Number of CPU Sockets Number of CPU sockets.
Key: cpu|numpackages
Overall CPU Contention (ms) Overall CPU contention in milliseconds.
Key: cpu|capacity_contention
Provisioned Capacity (MHz) Provisioned capacity in megahertz.
Key: cpu|capacity_provisioned
Provisioned vCPU Number of provisioned virtual CPU cores.
Key: cpu|corecount_provisioned
Reserved Capacity (MHz) Sum of the reservation properties of the immediate children of the host's root
resource pool.
Key: cpu|reservedCapacity_average
Usage (MHz) Average CPU use in megahertz.
Key: cpu|usagemhz_average
Wait (ms) CPU time spent on the idle state.
Key: cpu|wait
Overhead Amount of CPU that is overhead.
Key: cpu|overhead_average
Demand without overhead Value of demand excluding any overhead.
Key: cpu|demand_without_overhead
Provisioned Capacity Provisioned capacity (MHz).
Key: cpu|vm_capacity_provisioned
Total Capacity (MHz) Total CPU resources configured on the descendant ESXi hosts.
Key: cpu|capacity_provisioned
VMware by Broadcom  4252

---
## page 4253

 VMware Cloud Foundation 9.0
Metric Name Description
Usable Capacity (MHz) The usable CPU resources that are available for the virtual machines after
considering reservations for vSphere High Availability (HA) and other vSphere
services.
Key: cpu|haTotalCapacity_average
Datastore Metrics
Datastore metrics provide information about the datastore.
Metric Name Description
Outstanding IO requests OIO for datastore.
Key: datastore|demand_oio
Read IOPS Average number of read commands issued per second during the collection
interval.
Key: datastore|numberReadAveraged_average
Write IOPS Average number of write commands issued per second during the collection
interval.
Key: datastore|numberWriteAveraged_average
Read Throughput (KBps) Amount of data read in the performance interval.
Key: datastore|read_average
Write Throughput (KBps) Amount of data written to disk in the performance interval.
Key: datastore|write_average
Disk Metrics
Disk metrics provide information about disk use.
Metric Name Description
Total IOPS Average number of commands issued per second during the collection cycle.
Key: disk|commandsAveraged_average
Total Latency (ms) Average amount of time taken for a command from the perspective of the guest
operating system. This metric is the sum of the Kernel Device Command Latency
and Physical Device Command Latency metrics.
Key: disk|totalLatency_average
Total Throughput (KBps) Average of the sum of the data read and written for all the disk instances of the host
or virtual machine.
Key: disk|usage_average
Total queued outstanding operations Sum of queued operations and outstanding operations.
Key: disk|sum_queued_oio
Max Observed OIO Max observed IO for a disk.
Key: disk|max_observed
Disk Space Metrics
Disk space metrics provide information about disk space use.
VMware by Broadcom  4253

---
## page 4254

 VMware Cloud Foundation 9.0
Metric Name Description
Total disk space used (KB) Total disk space used on all datastores visible to this object.
Key: diskspace|total_usage
Total disk space (KB) Total disk space on all datastores visible to this object.
Key: diskspace|total_capacity
Total provisioned disk space (KB) Total provisioned disk space on all datastores visible to this object.
Key: diskspace|total_provisioned
Utilization (GB) Storage space used on the connected vSphere Datastores.
Key: diskspace|total_usage
Total Capacity (GB) Total storage space available on the connected vSphere datastores.
Key: diskspace|total_capacity
Memory Metrics
Memory metrics provide information about memory use and allocation.
Metric Name Description
Contention (%) Percent host memory contention.
Key: mem|host_contentionPct
Machine Demand (KB) Host memory demand in kilobytes.
Key: mem|host_demand
ESX System Usage Memory usage by the VMkernel and ESX user-level services.
Key: mem|host_systemUsage
Provisioned Memory (KB) Provisioned host memory in kilobytes.
Key: mem|host_provisioned
Reserved Capacity (KB) Sum of the reservation properties of the immediate children of the host's root
resource pool.
Key: mem|reservedCapacity_average
Usable Memory (KB) Usable host memory in kilobytes.
Key: mem|host_usable
Host Usage (KB) Host memory use in kilobytes.
Key: mem|host_usage
Usage/Usable (%) Percent host memory used.
Key: mem|host_usagePct
Contention (KB) Host contention in kilobytes.
Key: mem|host_contention
VM Overhead (KB) Memory overhead reported by host.
Key: mem|overhead_average
Utilization (KB) Memory utilization level based on the descendant virtual machines utilization.
Includes reservations, limits, and overhead to run the Virtual Machines.
Key: mem|total_need
Total Capacity (KB) Total physical memory configured on descendant ESXi hosts.
Key: mem|host_provisioned
Usable Capacity (KB) The usable memory resources available for the virtual machines after
considering reservations for vSphere HA and other vSphere services.
VMware by Broadcom  4254

---
## page 4255

 VMware Cloud Foundation 9.0
Metric Name Description
Key: mem|haTotalCapacity_average
Network Metrics
Network metrics provide information about network performance.
Metric Name Description
Packets Dropped (%) Percent network packets dropped.
Key: net|droppedPct
Total Throughput (KBps) Sum of the data transmitted and received for all of the NIC instances of the host
or virtual machine.
Key: net|usage_average
Packets Received Number of packets received in the performance interval.
Key: net|packetsRx_summation
Packets Transmitted Number of packets transmitted in the performance interval.
Key: net|packetsTx_summation
Received Packets Dropped Number of received packets dropped in the performance interval.
Key: net|droppedRx_summation
Transmitted Packets Dropped Number of transmitted packets dropped in the performance interval.
Key: net|droppedTx_summation
Data Transmit Rate (KBps) Average amount of data transmitted per second.
Key: net|transmitted_average
Data Receive Rate (KBps) Average amount of data received per second.
Key: net|received_average
Summary Metrics
Summary metrics provide information about overall performance.
Metric Name Description
Number of Running Hosts Number of hosts that are on.
Key: summary|number_running_hosts
Number of Running VMs Number of virtual machines that are on.
Key: summary|number_running_vms
Number of Clusters Total number of clusters.
Key: summary|total_number_clusters
Total Number of Datastores Total number of datastores.
Key: summary|total_number_datastores
Number of Hosts Total number of hosts.
Key: summary|total_number_hosts
Number of VMs Total number of virtual machines.
Key: summary|total_number_vms
Maximum Number of VMs Maximum number of virtual machines.
Key: summary|max_number_vms
Workload Indicator (%) Percent workload indicator.
VMware by Broadcom  4255

---
## page 4256

 VMware Cloud Foundation 9.0
Metric Name Description
Key: summary|workload_indicator
Total Number of data centers Total number of data centers.
Key: summary|total_number_datacenters
Number of Cores on Powered On Hosts Number of cores on powered-on hosts.
Key: summary|number_powered_on_cores
Number VCPUs on Powered on VMs Number of virtual CPUs on powered-on virtual machines.
Key: summary|number_running_vcpus
Average Running VM Count per Running Host Average running virtual machine count per running host.
Key: summary|avg_vm_density
VC Query Time (ms) vCenter Server query time in milliseconds.
Key: summary|vc_query_time
Derived Metrics Computation Time (ms) Derived metrics computation time in milliseconds.
Key: summary|derived_metrics_comp_time
Number of objects Number of objects.
Key: summary|number_objs
Number of VC Events Number of vCenter Server events.
Key: summary|number_vc_events
Number of SMS Metrics Number of SMS metrics.
Key: summary|number_sms_metrics
Collector Memory Usage (MB) Collector memory use in megabytes.
Key: summary|collector_mem_usage
Virtual Machine Operations Metrics for vCenter Server
VM operations metrics provide information about the actions performed on VMs. The following are some important points
you must know about VM operation metrics for vCenter Server.
• VM operations metrics is not collected for custom data centers.
• If you edit a VM settings and do not perform any action, still it is considered as VM reconfigure operation.
• During Revert Snapshot, VMs are powered-off, but this operation is not counted under VM Power-off metric.
• Adding ESXi with VMs is not counted under VM Create metric.
• Removing ESXi with VMs is not coutned under VM Remove metric.
• VM hardstop operation is not counted under VM Power Off metric.
Metric Name Description
Inventory
VM Clone This metric displays the number of clone operations on the virtual
machine.
Key: Inventory|VM Clone
VM Create This metric displays the number of create operations on the virtual
machine.
Key: Inventory|VM Create
VM Delete This metric displays the number of delete operations on the virtual
machine.
Key: Inventory|VM Delete
VMware by Broadcom  4256

---
## page 4257

 VMware Cloud Foundation 9.0
Metric Name Description
VM Reconfigure This metric displays the number of reconfigure operations on the
virtual machine.
Key: Inventory|VM Reconfigure
VM Register This metric displays the number of register operations on the
virtual machine.
Key: Inventory|VM Register
VM Template Deploy This metric displays the number templates deployed on the virtual
machine.
Key: Inventory|VM Template Deploy
VM Unregister This metric displays the number of unregister operations on the
virtual machine.
Key: Inventory|VM Unregister
Location
Storage vMotion This metric displays the number of migrations with vMotion
(datastore change operations for Powered-on VMs).
Key: Location|Storage vMotion
VM Datastore Change (powered-off VMs) This metric displays the number of datastore change operations,
for powered-off and suspended virtual machines.
Key: Location|VM Datastore Change (powered-off VMs)
VM Host and Datastore Change (powered-off VMs) This metric displays the number of host and datastore change
operations, for powered-off and suspended virtual machines.
Key: Location|VM Host and Datastore Change (powered-off VMs)
VM Host and Datastore Change (powered-on VMs) This metric displays the number of host and datastore change
operations, for powered-on and suspended virtual machines.
Key: Location|VM Host and Datastore Change (powered-on VMs)
VM Host Change (powered-off VMs) This metric displays the number of host change operations, for
powered-off and suspended virtual machines.
Key: Location|VM Host Change (powered-off VMs)
vMotion This metric displays the number of migrations with vMotion (host
change operations for powered-on VMs).
Key: Location|vMotion
State
VM Guest Reboot This metric displays the number of reboot operations on the virtual
machine guest.
Key: State|VM Guest Reboot
VM Guest Shutdown This metric displays the number of shutdown operations on the
virtual machine guest.
Key: State|VM Guest Shutdown
VM Power Off This metric displays the number of power-off operations on the
virtual machine.
Key: State|VM Power Off
VM Power On This metric displays the number of power-on operations on the
virtual machine.
Key: State|VM Power On
VMware by Broadcom  4257

---
## page 4258

 VMware Cloud Foundation 9.0
Metric Name Description
VM Reset This metric displays the number of reset operations on the virtual
machine guest.
Key: State|VM Reset
VM Standby Guest This metric displays the number of standby operations on the
virtual machine guest.
Key: State|VM Standby Guest
VM Suspend This metric displays the number of suspend operations on the
virtual machine.
Key: State|VM Suspend
Disabled Metrics
The following metrics are disabled in this version of VCF Operations. This means that they do not collect data by default.
You can enable these metrics in the Policy workspace. For more information, in VMware Docs search for Collect Metrics
and Properties Details.
You can enable these metrics in the Policy workspace. For more information, see Metrics and Properties Details.
Metric Name Description
Max Observed Number of Outstanding IO Operations Maximum observed number of outstanding IO operations.
Key: datastore|maxObserved_OIO
Max Observed Read Rate Max observed rate of reading data from the datastore.
Key: datastore|maxObserved_Read
Max Observed Reads per second Max observed average number of read commands issued per second during
the collection interval.
Key: datastore|maxObserved_NumberRead
Max Observed Writes per second Max observed average number of write commands issued per second during
the collection interval.
Key: datastore|maxObserved_NumberWrite
Max Observed Write Rate Max observed rate of writing data from the datastore.
Key: datastore|maxObserved_Write
Max Observed Throughput (KBps) Max observed rate of network throughput.
Key: net|maxObserved_KBps
Max Observed Transmitted Throughput (KBps) Max observed transmitted rate of network throughput.
Key: net|maxObserved_Tx_KBps
Max Observed Received Throughput (KBps) Max observed received rate of network throughput.
Key: net|maxObserved_Rx_KBps
Virtual Machine Metrics
VCF Operations collects configuration, CPU use, memory, datastore, disk, virtual disk, guest file system, network, power,
disk space, storage, and summary metrics for virtual machine objects.
GPU Metrics
GPU metrics provide information about the GPU usage and performance.
VMware by Broadcom  4258

---
## page 4259

 VMware Cloud Foundation 9.0
Metric Name Description
vGPU:vGPU-id|vGPU Memory Reservation (KB) The amount of GPU memory reserved for the assigned vGPUs.
vGPU:vGPU-id|vGPU Memory Used (KB) The amount of GPU memory being used in kilobytes.
vGPU:vGPU-id|vGPU 3D / Compute utilization (%) The percentage of time the GPU is actively processing tasks.
vGPU:vGPU-id|vGPU Memory Utilization (%) The amount of GPU memory being used in percentage.
vGPU:vGPU-id|vGPU Encode Utilization (%) Encoding is the process of converting raw data into a compressed
format.
vGPU:vGPU-id|vGPU Decode Utilization (%) Decoding is the process of converting compressed format into a
raw format.
Guest Operating System Metrics
Guest Operating System metrics provide information about the new metrics added to the Guest Operating System.
Metric Name Description
Guest|Peak Guest OS Page-out/rate within
collection cycle
This metric displays the highest memory page-out rate reported by guest
operating system, measured as peak of any 20-second average during the
collection interval.
Note:
To collect the guest metrics, ensure that VM Tools is installed and up and
running on virtual machine, on vCenter server.
Key: guest|20_sec_peak_page.outRate_latest
Metrics for ROI Dashboard
Virtual machine metrics provide information about the new metrics added to the ROI dashboard.
Metric Name Description
Potential Memory Consumed Reclaimable(GB) This metric displays the sum of all the reclaimble consumed
memory for the virtual machine.
Potential CPU Usage Increase (GHz) This metric displays the potential increase in CPU usage for the
virtual machine.
Potential Memory Usage Increase (GB) This metric displays the potential increase in memory usage for
the virtual machine.
Potential Savings This metric displays the sum of all the potential savings (Idle VMs
+ Powered off Vms + Snapshot + Orphaned Disks + Oversized
VMs).
Potential Cost Increase This metric displays the potential increase in costs associated with
the virtual machine.
Application Level Cost Roll up Metrics
The application-level cost roll up in VCF Operations includes few additional metrics at the application level. VCF
Operations has introduced Business Application as a new object, the business application object can have Tiers and
Applications as its children. The cost roll up option allows you to aggregate all VM costs associated with the application
and tiers and publish them at VM level.
VMware by Broadcom  4259

---
## page 4260

 VMware Cloud Foundation 9.0
Table 1258: Application Level Cost Roll up Metrics
Metric Name Description
Monthly Effected Projected Total Cost This metric displays the effective virtual machine cost projected for
the full month.
Effective MTD Cost This metric displays the month to date effective application cost for
the selected virtual machine.
Effective Daily Cost This metric displays the effective daily cost of the application
associated with the virtual machine.
Configuration Metrics for Virtual Machines
Configuration metrics provide information about virtual machine configuration.
Metric Name Description
Config|Thin Provisioned Disk Thin Provisioned Disk.
Key: config|hardware|thin_Enabled
Config|Number of CPUs Number of CPUs for a Virtual Machine.
From VCF Operations 6.7 and onwards, this metric is
measured in vCPUs instead of cores.
Key: config|hardware|num_Cpu
Config|Disk Space Disk space metrics.
Key: config|hardware|disk_Space
CPU Usage Metrics for Virtual Machines
CPU usage metrics provide the information about CPU use.
Metric Name Description
CPU|Other Wait (ms) CPU time spent waiting for IO.
Key: cpu|otherwait
CPU|Overall CPU Contention (ms) The amount of time the CPU cannot run due to contention.
Key: cpu|capacity_contention
CPU|Reservation Used CPU Reservation Used.
Key: cpu|reservation_used
CPU|Effective Limit CPU Effective Limit.
Key: cpu|effective_limit
CPU|Other Wait (%) Percentage Other Wait.
Key: cpu|otherwaitPct
CPU|Swap wait (%) Percentage swap waits for CPU.
Key: cpu|swapwaitPct
CPU|Wait (%) Percentage of the total CPU time spent in wait state.
Key: cpu|waitPct
CPU|System (%) Percentage CPU time spent on system processes.
Key: cpu|systemSummationPct
CPU|Capacity entitlement (MHz) CPU entitlement for the VM after considering all limits.
VMware by Broadcom  4260

---
## page 4261

 VMware Cloud Foundation 9.0
Metric Name Description
Key: cpu|capacity_entitlement
CPU|Capacity Demand Entitlement (% Percent capacity demand entitlement.
Key: cpu|capacity_demandEntitlementPct
CPU|CPU Contention (%) CPU contention as a percentage of 20-second collection
interval.
Key: cpu|capacity_contentionPct
CPU|Total Capacity Provisioned CPU capacity in megahertz.
Key: cpu|vm_capacity_provisioned
CPU|Demand (MHz) Total CPU resources required by the workloads on the virtual
machine.
Key: cpu|demandmhz
CPU|Host demand for aggregation Host demand for aggregation.
Key: cpu|host_demand_for_aggregation
CPU|Demand (ms) The total CPU time that the VM might use if there was no
contention.
Key: cpu|demand_average
CPU|Demand (%) CPU demand as a percentage of the provisioned capacity.
Key: cpu|demandPct
CPU|Usage (%) This metric indicates the percentage of CPU that was used
out of all the CPU that was allocated to the VM. CPU usage
can indicate when the VM is undersized.
Key: cpu|usage_average
CPU|Usage (MHz) CPU use in megahertz.
Key: cpu|usagemhz_average
CPU Workload % This metric indicates the CPU workload % for the VM,
the maximum threshold for this is 80% and the minimum
threshold is 20%. If your Maximum line is constantly ~100%
flat, you may have a runaway process. If this chart is below
or less than 20% all the time for the entire month, then all the
large VMs are oversized. This number must hover around
40%, indicating the sizing done was accurate.
CPU|System (ms) CPU time spent on system processes.
Key: cpu|system_summation
CPU|Ready (%) This metric indicates the percentage of time in which the VM
was waiting in line to use the CPU on the host.
A large ready time for a VM indicates that the VM needed
CPU resources but the infrastructure was busy serving other
VMs. A large ready time might indicate that the host is trying
to serve too many VMs.
Whenever the CPU ready is larger than 10%, you should
check if the host is overloaded, or if the VM really needs all
the resources that were allocated to it.
Key: cpu|readyPct
CPU|Extra (ms) Extra CPU time in milliseconds.
Key: cpu|extra_summation
CPU|Guaranteed (ms) CPU time that is guaranteed for the virtual machine.
Key: cpu|guaranteed_latest
VMware by Broadcom  4261

---
## page 4262

 VMware Cloud Foundation 9.0
Metric Name Description
CPU|Co-stop (%) Percentage of time the VM is ready to run, but is unable to
due to co-scheduling constraints.
Key: cpu|costopPct
CPU|Latency Percentage of time the VM is unable to run because it is
contending for access to the physical CPUs.
Key: cpu|latency_average
CPU|Max Limited Time the VM is ready to run, but is not run due to maxing out
its CPU limit setting.
Key: cpu|maxlimited_summation
CPU|Overlap Time the VM was interrupted to perform system services on
behalf of that VM or other VMs.
Key: cpu|overlap_summation
CPU|Run Time the VM is scheduled to run.
Key: cpu|run_summation
CPU|Entitlement Latest Entitlement Latest.
Key: cpu|entitlement_latest
CPU|Total Capacity (MHz) Total CPU capacity allocated to the virtual machine.
Key: cpu|vm_capacity_provisioned
CPU|Peak vCPU Ready The highest CPU Ready among the virtual CPUs.
Key: cpu|peak_vcpu_ready
CPU|Peak vCPU Usage The highest CPU Usage among the virtual CPU, compared
with the static configured CPU frequency. A constantly high
number indicates that one or more of the CPUs have high
utilization.
Key: cpu|peak_vcpu_usage
CPU|20-second Peak CPU System (%) The highest system CPU, measured as a peak of any 20-
second average during the collection interval.
Key: cpu|20-second peak cpu system
CPU|20-second Peak vCPU Co-Stop (%) The highest CPU Co-Stop among any of the vCPU, measured
as a peak of any 20-second average during the collection
interval.
Key: cpu|20-second peak vcpu co-stop
CPU|20-second Peak vCPU IO-Wait(%) The highest CPU Other Wait among any of the vCPU,
measured as a peak of any 20-second average during the
collection interval.
Key: cpu|20-second peak vcpu io-wait
CPU|20-second Peak vCPU Overlap (ms) The highest CPU Overlap among any of the vCPU, measured
as a peak of any 20-second average during the collection
interval.
Key: cpu|20-second peak vcpu overlap
CPU|20-second Peak vCPU Ready (%) The highest CPU Ready among any of the vCPU, measured
as a peak of any 20-second average during the collection
interval.
Key: cpu|20-second peak vcpu ready
VMware by Broadcom  4262

---
## page 4263

 VMware Cloud Foundation 9.0
Metric Name Description
CPU|20-second Peak vCPU Swap Wait (%) The highest CPU Swap Wait among any of the vCPU,
measured as a peak of any 20-second average during the
collection interval.
Key: cpu|20-second peak vcpu swap wait
CPU | vCPU Usage Disparity The absolute gap between the highest vCPU Usage and the
lowest vCPU Usage.
Key: cpu|vcpu_usage_disparity
CPU Utilization for Resources Metrics for Virtual Machines
CPU utilization for resources metrics provides information about resource CPU use.
Metric Name Description
rescpu|CPU Active (%) (interval) The average active time (actav) or peak active time (actpk) for
the CPU during various intervals.
Key:
rescpu|actav1_latest
rescpu|actav5_latest
rescpu|actav15_latest
rescpu|actpk1_latest
rescpu|actpk5_latest
rescpu|actpk15_latest
rescpu|CPU Running (%) (interval) The average runtime (runav) or peak active time (runpk) for
the CPU during various intervals.
Key:
rescpu|runav1_latest
rescpu|runav5_latest
rescpu|runav15_latest
rescpu|runpk1_latest
rescpu|runpk5_latest
rescpu|runpk15_latest
rescpu|CPU Throttled (%) (interval) Amount of CPU resources over the limit that were refused,
average over various intervals.
Key:
rescpu|maxLimited1_latest
rescpu|maxLimited5_latest
rescpu|maxLimited15_latest
rescpu|Group CPU Sample Count The sample CPU count.
Key: rescpu|sampleCount_latest
rscpu|Group CPU Sample Period (ms) The sample period.
Key: rscpu|samplePeriod_latest
Memory Metrics for Virtual Machines
Memory metrics provide information about memory use and allocation.
Metric Name Description
Mem|Host Active (KB) Host active memory use in kilobytes.
VMware by Broadcom  4263

---
## page 4264

 VMware Cloud Foundation 9.0
Metric Name Description
Key: mem|host_active
Mem|Contention (KB) Memory contention in kilobytes.
Key: mem|host_contention
Mem|Contention (%) Percent memory contention.
Key: mem|host_contentionPct
Mem|Guest Configured Memory (KB) Guest operating system configured memory in kilobytes.
Key: mem|guest_provisioned
Mem|Guest Active Memory (%) Percent guest operating system active memory.
Key: mem|guest_activePct
Mem|Guest Non-Pageable Memory (KB) Guest operating system non-pageable memory in kilobytes.
Key: mem|guest_nonpageable_estimate
Mem|Reservation Used Memory Reservation Used.
Key: mem|reservation_used
Mem|Effective Limit Memory Effective Limit.
Key: mem|effective_limit
Mem|Demand for aggregation Host demand for aggregation.
Key: mem|host_demand_for_aggregation
Mem|Balloon (%) Percentage of total memory that has been reclaimed via
ballooning.
Key: mem|balloonPct
Mem|Guest Usage (KB) This metric shows the amount of memory the VM uses.
Key: mem|guest_usage
Mem|Guest Demand (KB) Guest operating system demand in kilobytes.
Key: mem|guest_demand
Mem|Guest Non-Pageable Memory (KB) Guest operating system non-pageable memory in kilobytes.
Key: mem|host_nonpageable_estimate
Mem|Host Demand (KB) Memory demand in kilobytes.
Key mem|host_demand
Mem|Host Workload Host Workload (%).
Key: host_workload
Mem|Zero (KB) Amount of memory that is all 0.
Key: mem|zero_average
Mem|Swapped (KB) This metric shows how much memory is being swapped.
Meaning, the amount of unreserved memory in kilobytes.
Key: mem|swapped_average
Mem|Swap Target (KB) Amount of memory that can be swapped in kilobytes.
Key: mem|swaptarget_average
Mem|Swap In (KB) Swap-in memory in kilobytes.
Key: mem|swapin_average
Mem|Balloon Target (KB) Amount of memory that can be used by the virtual machine
memory control.
Key: mem|vmmemctltarget_average
Mem|Consumed (KB) Amount of host memory consumed by the virtual machine for
guest memory in kilobytes.
VMware by Broadcom  4264

---
## page 4265

 VMware Cloud Foundation 9.0
Metric Name Description
Key: mem|consumed_average
Mem|Overhead (KB) Memory overhead in kilobytes.
Key: mem|overhead_average
Mem|Swap In Rate (KBps) Rate at which memory is swapped from disk into active
memory during the interval.
Key: mem|swapinRate_average
Mem|Active Write (KB) Active writes in kilobytes.
Key: mem|activewrite_average
Mem|Compressed (KB) Compressed memory in kilobytes.
Key: mem|compressed_average
Mem|Compression Rate (KBps) Compression rate in kilobytes per second.
Key: mem|commpressionRate_average
Mem|Decompression Rate (KBps) Decompression rate in kilobytes per second.
Key: mem|decompressionRate_average
Mem|Overhead Max (KB) Maximum overhead in kilobytes.
Key: mem|overheadMax_average
Mem|Zip Saved (KB) Zip-saved memory in kilobytes.
Key: mem|zipSaved_latest
Mem|Zipped (KB) Zipped memory in kilobytes.
Key: mem|zipped_latest
Mem|Entitlement Amount of host physical memory the VM is entitled to, as
determined by the ESX schedule.
Key: mem|entitlement_average
Mem|Capacity Contention Capacity Contention.
Key: mem|capacity.contention_average
Mem|Swap In Rate from Host Cache Rate at which memory is being swapped from host cache into
active memory.
Key: mem|llSwapInRate_average
Mem|Swap Out Rate to Host Cache Rate at which memory is being swapped to host cache from
active memory.
Key: mem|llSwapOutRate_average
Mem|Swap Space Used in Host Cache Space used for caching swapped pages in the host cache.
Key: mem|llSwapUsed_average
Mem|Overhead Touched Actively touched overhead memory (KB) reserved for use as
the virtualization overhead for the VM.
Key: mem|overheadTouched_average
Memory|VM Memory Demand (kb) Key: mem|vmMemoryDemand
Memory|Consumed (%) Key: mem|consumedPct
Mem|Utilization (KB) Memory used by the virtual machine. Reflects the guest OS
memory required for vSphere and certain VMTools versions
or for virtual machine consumption.
Key: mem|vmMemoryDemand
Mem|Total Capacity (KB) Memory resources allocated to powered on virtual machine.
Key: mem|guest_provisioned
VMware by Broadcom  4265

---
## page 4266

 VMware Cloud Foundation 9.0
Metric Name Description
Mem|20-second Peak Contention (%) The highest Memory Contention, measured as peak of any
20-second average during the collection interval.
Key: guest|20-second_peak_contention
Guest|Peak Guest OS Page-out/rate within collection cycle This metric shows the highest memory page-out rate reported
by guest operating system, measured as peak of any 20-
second average during the collection interval.
Key: guest|20_sec_peak_page.outRate_latest
Guest|Needed Memory Amount of memory needed for the Guest OS to perform
optimally. This memory is considered as a cache for the disk
and is a little more than the actual used memory.
Key: guest|mem.needed_latest
Guest|Free Memory Amount of memory that is not used but is readily available. If
the cache is high, a low free memory does not mean that the
Guest OS needs more memory.
Key: guest|mem.free_latest
Guest|Physical Usable Memory Amount of memory available to the Guest OS. Meaning, this
amount is close to the amount of configured memory to the
VM.
Key: guest|mem.physUsable_latest
Guest|20-second Peak Disk Queue Length The highest Disk Queue Length, measured as peak of any
20-second average during the collection interval.
Key: guest|20-second_peak_disk_queue_length
Guest|20-second Peak Run Queue The highest Run Queue, measured as peak of any 20-second
average during the collection interval.
Key: guest|20-second_peak_run_queue
Guest|20-second Peak CPU Context Switch Rate The highest CPU Context Switch Rate, measured as peak of
any 20-second average during the collection interval.
Key: guest|20-second_peak_cpu_context switch rate
Datastore Metrics for Virtual Machines
Datastore metrics provide information about datastore use.
Metric Name Description
Datastore|Total IOPS Average number of commands issued per second during the
collection interval.
Key: datastore|commandsAveraged_average
Datastore|Outstanding IO requests OIO for datastore.
Key: datastore|demand_oio
Datastore|Number of Outstanding IO Operations Number of outstanding IO operations.
Key: datastore|oio
Datastore|Demand Datastore demand.
Key: datastore|demand
Datastore|Total Latency (ms) The average amount of time taken for a command from
the perspective of a Guest OS. This is the sum of Kernel
Command Latency and Physical Device Command Latency.
Key: datastore|totalLatency_average
Datastore|Total Throughput (KBps) Usage Average (KBps).
VMware by Broadcom  4266

---
## page 4267

 VMware Cloud Foundation 9.0
Metric Name Description
Key: datastore|usage_average
Datastore|Used Space (MB) Used space in megabytes.
Key: datastore|used
Datastore|Not Shared (GB) Space used by VMs that is not shared.
Key: datastore|notshared
Datastore|Read IOPS Average number of read commands issued per second during
the collection interval.
Key: datastore|numberReadAveraged_average
Datastore|Write IOPS Average number of write commands issued per second during
the collection interval.
Key: datastore|numberWriteAveraged_average
Datastore|Read Throughput (KBps) This metric shows the amount of data that the VM reads to the
datastore per second.
Key: datastore|read_average
Datastore|Read Latency (ms) Average amount of time for a read operation from the
datastore. Total latency = kernel latency + device latency.
Key: datastore|totalReadLatency_average
Datastore|Write Latency (ms) Average amount of time for a write operation to the datastore.
Total latency = kernel latency + device latency.
Key: datastore|totalWriteLatency_average
Datastore|Write Throughput (KBps) This metric shows the amount of data that the VM writes to the
datastore per second.
Key: datastore|write_average
Datastore|Highest Latency Highest Latency.
Key: datastore|maxTotalLatency_latest
Datastore|Total Latency Max Total Latency Max (ms).
Key: datastore|totalLatency_max
Disk Metrics for Virtual Machines
Disk metrics provide information about disk use.
Metric Name Description
Disk Space|vSAN Overhead (GB) Displays the extra virtual machine disk space used by the
vSAN system.
Disk Space|vSAN Overhead (GB)
Disk Space|VMUsedWithoutOverhead(GB) Displays the virtual machine disk space without vSAN
overhead.
Disk Space|Usage Without Overhead (GB)
Disk Space
Note:  The Disk Space metrics are displayed by the virtual machine object only when the vSAN adapter is configured with vCenter.
Disk|Read IOPS Average number of read commands issued per second during
the collection interval.
Key: disk|numberReadAveraged_average
Disk|Write IOPS Average number of write commands issued per second during
the collection interval.
VMware by Broadcom  4267

---
## page 4268

 VMware Cloud Foundation 9.0
Metric Name Description
Key: disk|numberWriteAveraged_average
Disk|Total IOPS Average number of commands issued per second during the
collection interval.
Key: disk|commandsAveraged_average
Disk|Total Throughput (KBps) Use rate in kilobytes per second.
Key: disk|usage_average
Disk|I/O Usage Capacity This metric is a function of storage|usage_average and disk|
workload. Storage|usage_average is an average over all
storage devices. This means that disk|usage_capacity is not
specific to the selected VM or the host of the VM.
Key: disk|usage_capacity
Disk|Number of Outstanding IO Operations Number of outstanding IO operations.
Key: disk|diskoio
Disk|Queued Operations Queued operations.
Key: disk|diskqueued
Disk|Demand (%) Percent demand.
Key: disk|diskdemand
Disk |Total Queued Outstanding Operations Sum of Queued Operation and Outstanding Operations.
Key: disk |sum_queued_oio
Disk|Max Observed OIO Max Observed IO for a disk.
Key: disk|max_observed
Disk|Read Throughput KBps) Amount of data read in the performance interval.
Key: disk|read_average
Disk|Write Throughput (KBps) Amount of data written to disk in the performance interval.
Key: disk|write_average
Disk|Bus Resets The number of bus resets in the performance interval.
Key: disk|busResets_summation
Disk|Commands canceled The number of disk commands canceled in the performance
interval.
Key: disk|commandsAborted_summation
Disk|Highest Latency Highest latency.
Key: disk|maxTotalLatency_latest
Disk|SCSI Reservation Conflicts SCSI Reservation Conflicts.
Key: disk|scsiReservationConflicts_summation
Disk|Read Latency (ms) The average amount of time taken for a read from the
perspective of a Guest OS. This is the sum of Kernel Read
Latency and Physical Device Read Latency.
Key: disk|totalReadLatency_average
Disk|Write Latency (ms) The average amount of time taken for a write from the
perspective of a Guest OS. This is the sum of Kernel Write
Latency and Physical Device Write Latency.
Key: disk|totalWriteLatency_average
Disk|Total Latency (ms) The average amount of time taken for a command from
the perspective of a Guest OS. This is the sum of Kernel
Command Latency and Physical Device Command Latency.
VMware by Broadcom  4268

---
## page 4269

 VMware Cloud Foundation 9.0
Metric Name Description
Key: disk|totalLatency_average
Virtual Disk Metrics for Virtual Machines
Virtual disk metrics provide information about virtual disk use.
Metric Name Description
Virtual Disk:<scsi_controller>|IOPS per GB Displays the disk IO per second per Gigabyte of storage.
Key: virtualDisk:<scsi_controller>|iopsPerGB
Virtual Disk|Total Throughput Amount of data read from/written to storage in a second. This
is averaged over the reporting period.
Key: virtualDisk|usage
VirtualDisk|Total Latency Total latency.
Key: virtualDisk|totalLatency
VirtualDisk|Total IOPS Average number of commands per second.
Key: virtualDisk|commandsAveraged_average
VirtualDisk|Read Requests Average number of read commands issued per second to the
virtual disk during the collection interval.
Key: virtualDisk|numberReadAveraged_average
VirtualDisk|Write Requests Average number of write commands issued per second to the
virtual disk during the collection interval.
Key: virtualDisk|numberWriteAveraged_average
VirtualDisk|Read Throughput (KBps) Rate of reading data from the virtual disk in kilobytes per
second.
Key: virtualDisk|read_average
VirtualDisk|Read Latency (ms) Average amount of time for a read operation from the virtual
disk. Total latency = kernel latency + device latency.
Key: virtualDisk|totalReadLatency_average
VirtualDisk|Write Latency (ms) Average amount of time for a write operation to the virtual disk.
Total latency = kernel latency + device latency.
Key: virtualDisk|totalWriteLatency_average
VirtualDisk|Write Throughput (KBps) Rate of writing data from the virtual disk in kilobytes per
second.
Key: virtualDisk|write_average
VirtualDisk|Bus Resets The number of bus resets in the performance interval.
Key: virtualDisk|busResets_summation
VirtualDisk|Commands Aborted The number of disk commands canceled in the performance
interval.
Key: virtualDisk|commandsAborted_summation
VirtualDisk|Read Load Storage DRS virtual disk metric read load.
Key: virtualDisk|readLoadMetric_latest
VirtualDisk|Outstanding Read Requests Average number of outstanding read requests to the virtual
disk.
Key: virtualDisk|readOIO_latest
VirtualDisk|Write Load Storage DRS virtual disk write load.
VMware by Broadcom  4269

---
## page 4270

 VMware Cloud Foundation 9.0
Metric Name Description
Key: virtualDisk|writeLoadMetric_latest
VirtualDisk|Outstanding Write Requests Average number of outstanding write requests to the virtual
disk.
Key: virtualDisk|writeOIO_latest
VirtualDisk|Number of Small Seeks Small Seeks.
Key: virtualDisk|smallSeeks_latest
VirtualDisk|Number of Medium Seeks Medium Seeks.
Key: virtualDisk|mediumSeeks_latest
VirtualDisk|Number of Large Seeks Large Seeks.
Key: virtualDisk|largeSeeks_latest
VirtualDisk|Read Latency (microseconds) Read Latency in microseconds.
Key: virtualDisk|readLatencyUS_latest
VirtualDisk|Write Latency (microseconds) Write Latency in microseconds.
Key: virtualDisk|writeLatencyUS_latest
VirtualDisk|Average Read request size Read IO size.
Key: virtualDisk|readIOSize_latest
VirtualDisk|Average Write request size Write IO size.
Key: virtualDisk|writeIOSize_latest
Virtual Disk|Outstanding IO requests (OIOs) Key: virtualDisk|vDiskOIO
Virtual Disk|Used Disk Space (GB) Key: virtualDisk|actualUsage
Virtual Disk|Peak Virtual Disk IOPS The highest disk IO per second among the virtual disks. A
constantly high number indicates that one or more virtual disks
are sustaining high IOPS.
Key: virtualDisk|peak_vDisk_iops
Virtual Disk|Peak Virtual Disk Read Latency The highest read latency among the virtual disks. A
high number indicates that one or more virtual disks are
experiencing poor performance.
Key: virtualDisk|peak_vDisk_readLatency
Virtual Disk|Peak Virtual Disk Write Latency The highest write latency among the virtual disks. A
high number indicates that one or more virtual disks are
experiencing poor performance.
Key: virtualDisk|peak_vDisk_writeLatency
Virtual Disk|20-secod Peak Latency (ms) The highest latency among any of the virtual disk, measured
as peak of any 20-second average during the collection
interval.
Key: virtualDisk|20-second_peak_latency
Virtual Disk|Peak Virtual Disk throughput The highest disk throughput among the virtual disks.
Key: virtualDisk|peak_vDisk_throughpu
Guest File System Metrics for Virtual Machines
Guest file system metrics provide information about guest file system capacity and free space.
The data for these metrics is only displayed when VMware Tools has been installed on the virtual machines. If VMware
Tools is not installed, features dependent on these metrics, including capacity planning for virtual machine guest storage,
will not be available.
VMware by Broadcom  4270

---
## page 4271

 VMware Cloud Foundation 9.0
Metric Name Description
Guest file system|Guest File System Capacity (MB) Total capacity on guest file system in megabytes.
Key: guestfilesystem|capacity
Guest file system|Guest File System Free (MB) Total free space on guest file system in megabytes.
Key: guestfilesystem|freespace
Guest file system|Guest File System Usage (%) Percent guest file system.
Key: guestfilesystem|percentage
Guest file system|Guest File System Usage Total usage of guest file system.
From VCF Operations 6.7 and onwards, this metric is
measured in GBs.
Key: guestfilesystem|usage
Guest file system|Total Guest File System Capacity (GB) This metric displays the amount of disk space allocated for the
VM.
Correlate other metrics with this metric to indicate if changes
occur in the disk space allocation for the VM.
Key: guestfilesystem|capacity_total
Guest file system|Total Guest File System Usage (%) This metric displays the amount of display space being used
out of the total allocated disk space.
Use his metric to track if the overall usage is stable, or if it
reaches the limits. Do not include VMs with a disk space
usage of >95% since this might impact your system.
Key: guestfilesystem|percentage_total
Guest file system|Total Guest File System Usage Total usage of guest file system.
Key: guestfilesystem|usage_total
Guest file system|Utilization (GB) Storage space used by the Guest OS file systems. The disk
space is available only if VM tools are installed and running.
If the VM tools are not installed, the disk space capacity is not
applicable.
Key: guestfilesystem|usage_total
Guest file system|Total Capacity (GB) Storage space used by the Guest OS file systems. The disk
space is available only if VM tools are installed and running.
If the VM tools are not installed, the disk space capacity is not
applicable.
Key: guestfilesystem|capacity_total
Network Metrics for Virtual Machines
Network metrics provide information about network performance.
Metric Name Description
Network|Peak Network Packet per second within collection cycle This metric shows the highest VM packets per second rate,
measured as peak of any 20-second average during the
collection interval.
Key: net|20_sec_peak_packetsPerSec
Net|Total Throughput (KBps) The sum of the data transmitted and received for all the NIC
instances of the host or virtual machine.
Key: net|usage_average
VMware by Broadcom  4271

---
## page 4272

 VMware Cloud Foundation 9.0
Metric Name Description
Net|Data Transmit Rate (KBps) This metric shows the rate of data being sent by the VM per
second.
Key: net|transmitted_average
Net|Data Receive Rate (KBps) This metric shows the rate of data received by the VM per
second.
Key: net|received_average
Net|Packets per second Number of packets transmitted and received per second.
Key: net|PacketsPerSec
Net|Packets Received Number of packets received in the performance interval.
Key: net|packetsRx_summation
Net|Packets Transmitted Number of packets transmitted in the performance interval.
Key: net|packetsTx_summation
Net|Transmitted Packets Dropped This metric shows the number of transmitted packets dropped
in the collection interval
Key: net|dropppedTx_summation
Net|Packets Dropped (%) Percentage of packets dropped.
Key: net|droppedPct
Net|Packets Dropped Number of packets dropped in the performance interval.
Key: net|dropped
Net|Broadcast Packets Transmitted Number of broadcast packets transmitted during the sampling
interval.
Key: net|broadcastTx_summation
Net|Broadcast Packets Received Number of broadcast packets received during the sampling
interval.
Key: net|broadcastRx_summation
Net|Multicast Packets Received Number of multicast packets received.
Key: net|multicastRx_summation
Net|Multicast Packets Transmitted Number of multicast packets transmitted.
Key: net|multicastTx_summation
Net|VM to Host Data Transmit Rate Average amount of data transmitted per second between VM
and host.
Key: net|host_transmitted_average
Net|VM to Host Data Receive Rate Average amount of data received per second between VM and
host.
Key: net|host_received_average
Net|VM to Host Usage Rate The sum of the data transmitted and received for all the NIC
instances between VM and host.
Key: net|host_usage_average
Net|20-second Peak Usage Rate (KBps) The higest Usage Rate, measured as peak of any 20 second
average during the collection interval.
Key: net|20-second_peak_usage_rate
System Metrics for Virtual Machines
System metrics for virtual machines provide general information about the virtual machine, such as its build number and
running state.
VMware by Broadcom  4272

---
## page 4273

 VMware Cloud Foundation 9.0
Metric Name Description
Sys|Powered ON Powered on virtual machines. 1 if powered on, 0 if powered off,
-1 if unknown
Key: sys|poweredOn
Sys|OS Uptime Total time elapsed, in seconds, since last operating system
start.
Key: sys|osUptime_latest
Power Metrics for Virtual Machines
Power metrics provide information about power use.
Metric Name Description
Power|Total Energy Consumed in the collection period (Wh) Displays the total electricity consumed based on the time
interval selected. The default collection cycle is set to 5 mins.
You can continue using the default setting or edit it for each
adapter instance. For example, if the time interval is set to its
default value, the value represents the energy consumed per 5
mins.
Power|Total Power Consumed By VM (Wh) Displays the total power consumed by a virtual machine in
an hour. The data collected is over a period of an hour and
published along with the other metrics in VCF Operations. In
case of a connectivity or availability issue in VCF Operations
or vCenter adapter instance, this hourly metric might not be
published and the missed value during this period does not get
recalculated. Once the connection is re-established, the next
data points get published.
Note:  This metric is deactivated by default. You can activate it
from the Policies page. For more information, see Metrics and
Properties Details in the VCF Operations Configuration Guide.
Power|Power (Watt) Average power use in watts.
Power|Current Power Consumption Rate (Watt) The power consumption rate per second, averaged over the
reporting period.
Key: power|power_average
Power|(DEP) Energy (Joule) Total energy consumed in joules.
Key: power|energy_summation
Disk Space Metrics for Virtual Machines
Disk space metrics provide information about disk space use.
Metric Name Description
Diskspace|Provisioned Space (GB) Provisioned space in gigabytes.
Key: diskspace|provisioned
Diskspace|Provisioned Space for VM Provisioned space for VM.
Key: diskspace|provisionedSpace
Diskspace|Snapshot Space (GB) Space used by snapshots.
Key: diskspace|snapshot
VMware by Broadcom  4273

---
## page 4274

 VMware Cloud Foundation 9.0
Metric Name Description
Diskspace|Virtual machine used (GB) Space used by virtual machine files in gigabytes.
Key: diskspace|perDsUsed
Diskspace|Active not shared Unshared disk space used by VMs excluding snapshot.
Key: diskspace|activeNotShared
Storage Metrics for Virtual Machines
Storage metrics provide information about storage use.
Metric Name Description
Storage|Total IOPS Average number of commands issued per second during the
collection interval.
Key: storage|commandsAveraged_average
Storage|Contention (%) Percent contention.
Key: storage|contention
Storage|Read Throughput (KBps) Read throughput rate in kilobytes per second.
Key: storage|read_average
Storage|Read IOPS Average number of read commands issued per second during
the collection interval.
Key: storage|numberReadAveraged_average
Storage|Total Latency (ms) Total latency in milliseconds.
Key: storage|totalLatency_average
Storage|Total Usage (KBps) Total throughput rate in kilobytes per second.
Key: storage|usage_average
Storage|Write Throughput (KBps) Write throughput rate in kilobytes per second.
Key: storage|write_average
Storage|Write IOPS Average number of write commands issued per second during
the collection interval.
Key: storage|numberWriteAveraged_average
Summary Metrics for Virtual Machines
Summary metrics provide information about overall performance.
Metric Name Description
Summary|Availability % Displays the uptime of Guest OS, expressed as a percentage
of the collection period.
Key: summary|availability_kpi
Summary|Running Number of running virtual machines.
Key: summary|running
Summary|Desktop Status Horizon view desktop status.
Key: summary|desktop_status
Summary|Configuration|Type Indicates the type of virtual machine object based on which
you can identify the type of virtual machine. The valid values
for the virtual machine object property are:
• default - represents a regular virtual machine
VMware by Broadcom  4274

---
## page 4275

 VMware Cloud Foundation 9.0
Metric Name Description
• template - represents a powered off virtual machine
template.
• srm_placeholder - represents a powered on VMware Live
Recovery virtual machine.
• ft_primary - represents the primary Fault Tolerance virtual
machine.
• ft_secondary - represents the secondary Fault Tolerance
virtual machine.
Key: summary|config|type
Summary|Guest Operating System|Guest OS Full Name Displays the guest operating system name.
Key: summary|guest os full name
Summary|Oversized|Potential Memory Displays the oversized potential memory.
Key: summary|oversized|potentialMemConsumed
Summary|Undersized|Potential CPU Usage Displays the undersized potential CPU used.
Key: summary|undersized|potentialCpuUsage
Summary|Undersized|Potential Memory Displays the undersized potential memory used.
Key: summary|undersized|potentialMemUsage
Reclaimable Idle Boolean flag indicating whether VM is considered as
reclaimable because it is in Idle state.
Key: summary|idle
Reclaimable Powered Off Boolean flag indicating whether VM is considered as
reclaimable because it is in powered off state.
Key: summary| poweredOff
Reclaimable Snapshot Space (GB) Reclaimable snapshot space.
Key: summary| snapshotSpace
Cost Metrics for Virtual Machines
Cost metrics provide information about the cost.
Metric Name Description
Monthly OS Labor Cost Monthly operating system labor cost of the virtual machine.
Key: cost|osLaborTotalCost
Monthly Projected Total Cost Virtual machine cost projected for full month.
Key: Cost|monthlyProjectedCost
Monthly VI Labor Cost Monthly virtual infrastructure labor cost of the virtual machine.
Key: cost|viLaborTotalCost
MTD Compute Total Cost Total compute cost (including CPU and memory) of the virtual
machine.
Key: cost|compTotalCost
MTD CPU Cost Month to Date Virtual Machine CPU Cost. It is based on utilization.
The more the VM uses, the higher its cost.
Key: cost|cpuCost
MTD Monthly Cost Month to date direct cost (comprising of OS labor, VI labor and
any windows desktop instance license) of the virtual machine. It
also comprises of the additional and application cost of the virtual
machine.
VMware by Broadcom  4275

---
## page 4276

 VMware Cloud Foundation 9.0
Metric Name Description
Key: cost|vmDirectCost
MTD Memory Cost Month to Date Memory Cost of Virtual Machine. It is based on
utilization. The more the VM uses, the higher its cost.
Key: cost|memoryCost
MTD Storage Cost Month to date storage cost of the virtual machine.
Key: cost|storageCost
MTD Total Cost Month to date total compute cost (including CPU and memory) of
the virtual machine.
Key: cost|monthlyTotalCost
Potential Savings Reclaimable cost of VM for being either idle, powered-off, or
having snapshots.
Key: cost|reclaimableCost
Cost|Allocation|MTD VM CPU Cost (Currency) Month to Date Virtual Machine CPU Cost computed based on
resource overcommit ratio set for its parent cluster in policy.
cost|allocation|allocationBasedCpuMTDCost
Cost|Allocation|MTD VM Memory Cost (Currency) Month to Date Virtual Machine CPU Memory cost computed
based on resource overcommit ratio set for its parent cluster in
policy.
cost|allocation|allocationBasedMemoryMTDCost
Cost|Allocation|MTD VM Storage Cost (Currency) Month to Date Virtual Machine CPU Storage cost computed
based on resource overcommit ratio set for its parent cluster (or
datastore cluster) in policy.
cost|allocation|allocationBasedStorageMTDCost
Cost|Allocation|MTD VM Total Cost (Currency) Month to Date Virtual Machine Total Cost is the summation of the
CPU Cost, Memory Cost, Storage Cost and Direct Cost, based on
overcommit ratios set in policy for the parent cluster or datastore
cluster.
cost|allocation|allocationBasedTotalCost
Cost|Effective Daily Cpu Cost (Currency) Daily CPU cost of the selected virtual machine.
Cost|Effective Daily Memory Cost (Currency) Daily Memory cost of the selected virtual machine.
Cost|Effective Daily Storage Cost (Currency) Daily Storage cost of the selected virtual machine.
Cost|Daily Additional Cost Daily Additional cost of the selected virtual machine.
Cost|Effective Daily Cost (Currency) Effective Daily cost is the sum of effective daily CPU cost +
effective daily memory cost + effective daily storage cost + daily
additional cost.
Cost|Effective MTD Cost (Currency) Effective MTD cost is the sum of effective daily CPU cost from
beginning of month until now + effective daily memory cost
from beginning of month until now + effective daily storage cost
from beginning of month until now + daily additional cost from
beginning of month until now.
Virtual Hardware Metrics for Virtual Machines
Metric Name Description
Configuration|Hardware|Number of CPU cores per socket This metric displays the number of CPU cores per socket.
VMware by Broadcom  4276

---
## page 4277

 VMware Cloud Foundation 9.0
Metric Name Description
Configuration|Hardware|Number of virtual CPUs This metric displays the number of CPUs in the virtual machine.
Configuration|Hardware|Number of virtual sockets: This metric displays the number of virtual sockets in the virtual
machine.
Configuration|Hardware|Memory: This metric displays the memory used in the virtual machine.
Configuration|CPU Resource Allocation|Limit This metric displays the resource allocation limit of the virtual
machine.
Configuration|CPU Resource Allocation|Reservation This metric displays the reserved resources for the virtual
machine.
Configuration|CPU Resource Allocation|Shares| This metric displays the shared resources for the virtual machine.
Summary|Guest Operating System|Tools Version This metric displays the tools version of the guest operating
system.
Summary|Guest Operating System|Tools Version Status This metric displays the status of the tools in the guest operating
system.
Summary|Guest Operating System|Tools Running Status This metric displays whether the tools are functional in the guest
operating system.
Guest File System:/boot|Partition Capacity (GB) This metric displays the boot partition capacity in the guest file
system.
Guest File System:/boot|Partition Utilization (%) This metric displays the boot partition usage percentage in the
guest file system.
Guest File System:/boot|Partition Utilization (GB) This metric displays the boot partition used in the guest file
system.
Virtual Disk|Configured This metric displays the disk space of the configured virtual disk.
Virtual Disk|Label This metric displays the disk label of the configured virtual disk.
Disk Space|Snapshot Space This metric displays the snap shot details of the virtual machine.
Network|IP Address This metric displays the IP address of the virtual machine.
Network|MAC Address This metric displays the MAC address of the virtual machine.
Disabled Instanced Metrics
The instance metrics created for the following metrics are disabled in this version of VCF Operations. This means that
these metrics collect data by default but all the instanced metrics created for these metrics, do not collect data by default.
Metric Name
Configuration|Hardware|Number of virtual CPUs
CPU|Ready (%)
CPU|Usage (MHz)
Net|Broadcast Packets Transmitted
Net|Data Transmit Rate (KBps)
Net|Data Receive Rate (KBps)
Net|Multicast Packets Transmitted
Net|Packets Dropped
VMware by Broadcom  4277

---
## page 4278

 VMware Cloud Foundation 9.0
Metric Name
Net|Packets Dropped (%)
Net|pnicByteRx_average
Net|pnicByteTx_average
Net|Transmitted Packets Dropped
Net|Usage Rate (KBps)
VirtualDisk|Read IOPS
VirtualDisk|Read Latency (ms)
VirtualDisk|Read Throughput (KBps)
VirtualDisk|Total IOPS
VirtualDisk|Total Latency
VirtualDisk|Total Throughput (KBps)
Virtual Disk|Used Disk Space (GB)
VirtualDisk|Write IOPS
VirtualDisk|Write Latency (ms)
VirtualDisk|Write Throughput (KBps)
Datastore|Outstanding IO requests
Datastore|Read IOPS
Datastore|Read Latency (ms)
Datastore|Read Throughput (KBps)
Datastore|Total IOPS
Datastore|Total Latency (ms)
Datastore|Total Throughput (KBps)
Datastore|Write IOPS
Datastore|Write Latency (ms)
Datastore|Write Throughput (KBps)
Disk|Total IOPS
Disk|Total Throughput (KBps)
Disk|Read Throughput KBps)
Disk|Write Throughput (KBps)
Diskspace|Access Time (ms)
Diskspace|Virtual machine used (GB)
Disabled Metrics
The following metrics are disabled in this version of VCF Operations. This means that they do not collect data by default.
You can enable these metrics in the Policy workspace. For more information, in VMware Docs search for Collect Metrics
and Properties Details.
You can enable these metrics in the Policy workspace.
VMware by Broadcom  4278

---
## page 4279

 VMware Cloud Foundation 9.0
Metric Name Description
CPU|50% of Recommended number of vCPUs to Remove This metric is superseded by the capacity engine.
cpu|numberToRemove50Pct
CPU|Capacity entitlement (mhz) cpu|capacity_entitlement
CPU|Co-stop (msec) Use the Co-Stop (%) metric instead of this metric.
cpu|costop_summation
CPU|Demand Over Capacity (mhz) cpu|demandOverCapacity
CPU|Demand Over Limit (mhz) Use Contention (%) metric instead of this metric.
cpu|demandOverLimit
CPU|Dynamic entitlement cpu|dynamic_entitlement
CPU|Estimated entitlement cpu|estimated_entitlement
CPU|Idle (%) cpu|idlePct
CPU|Idle (msec) cpu|idle_summation
CPU|Other Wait (msec) cpu|otherwait
CPU|Normalized Co-stop (%) Use the Co-Stop (%) metric instead of this metric.
cpu|perCpuCoStopPct
CPU|Provisioned vCPU(s) (Cores) cpu|corecount_provisioned
CPU|Ready (msec) Choose the Use Ready (%) metric instead of this metric.
cpu|ready_summation
CPU|Recommended Size Reduction (%) cpu|sizePctReduction
CPU|Swap Wait (msec) cpu|swapwait_summation
CPU|Total Wait (msec) cpu|wait
CPU|Used (msec) cpu|used_summation
CPU|Wait (msec) cpu|wait_summation
Datastore I/O|Max Observed Number of Outstanding IO Operations datastore|maxObserved_OIO
Datastore I/O|Max Observed Read Rate (kbps) datastore|maxObserved_Read
Datastore I/O|Max Observed Reads per second datastore|maxObserved_NumberRead
Datastore I/O|Max Observed Write Rate (kbps) datastore|maxObserved_Write
Datastore I/O|Max Observed Writes per second datastore|maxObserved_NumberWrite
Disk Space|Not Shared (gb) diskspace|notshared
Disk Space|Number of Virtual Disks diskspace|numvmdisk
Disk Space|Shared Used (gb) diskspace|shared
Disk Space|Total disk space used (gb) diskspace|total_usage
Disk Space|Total disk space (gb) diskspace|total_capacity
Disk Space|Virtual Disk Used (gb) diskspace|diskused
Guest File System stats|Total Guest File System Free (gab) guestfilesystem|freespace_total
Guest|Active File Cache Memory (kb) guest|mem.activeFileCache_latest
Guest|Context Swap Rate per second guest|contextSwapRate_latest
Guest|Huge Page Size (kb) guest|hugePage.size_latest
Guest|Page Out Rate per second guest|page.outRate_latest
VMware by Broadcom  4279

---
## page 4280

 VMware Cloud Foundation 9.0
Metric Name Description
Guest|Total Huge Pages guest|hugePage.total_latest
Memory|50% of Reclaimable Memory Capacity (gb) This metric is superseded by the capacity engine.
mem|wasteValue50PctInGB
Memory|Balloon (kb) mem|vmmemctl_average
Memory|Demand Over Capacity mem|demandOverCapacity
Memory|Demand Over Limit mem|demandOverLimit
Memory|Granted (kb) mem|granted_average
Memory|Guest Active (kb) mem|active_average
Memory|Guest Dynamic Entitlement (kb) mem|guest_dynamic_entitlement
Memory|Guest Workload (%) mem|guest_workload
Memory|Host Demand with Reservation (kb) mem|host_demand_reservation
Memory|Host Dynamic Entitlement (kb) mem|host_dynamic_entitlement
Memory|Host Usage (kb) mem|host_usage
Memory|Host Workload (%) mem|host_workload
Memory|Latency (%) Use the Memory Contention (%) metric instead of this metric.
mem|latency_average
Memory|Recommended Size Reduction (%) mem|sizePctReduction
Memory|Shared (kb) mem|shared_average
Memory|Swap Out Rate (kbps) mem|swapoutRate_average
Memory|Usage (%) mem|usage_average
Memory|Estimated entitlement mem|estimated_entitlement
Network I/O|Data Receive Demand Rate (kbps) net|receive_demand_average
Network I/O|Data Transmit Demand Rate (kbps) net|transmit_demand_average
Network I/O|VM to Host Data Receive Rate (kbps) net|host_received_average
Network I/O|VM to Host Data Transmit Rate (kbps) net|host_transmitted_average
Network I/O|VM to Host Max Observed Received Throughput (kbps) net|host_maxObserved_Rx_KBps
Network I/O|VM to Host Max Observed Throughput (kbps) net|host_maxObserved_KBps
Network I/O|VM to Host Max Observed Transmitted Throughput (kbps) net|host_maxObserved_Tx_KBps
Network I/O|VM to Host Usage Rate (kbps) net|host_usage_average
Network|bytesRx (kbps) net|bytesRx_average
Network|bytesTx (kbps) net|bytesTx_average
Network|Demand (%) Use absolute numbers instead of this metric.
net|demand
Network|I/O Usage Capacity net|usage_capacity
Network|Max Observed Received Throughput (kbps) net|maxObserved_Rx_KBps
Network|Max Observed Throughput (kbps) net|maxObserved_KBps
Network|Max Observed Transmitted Throughput (kbps) net|maxObserved_Tx_KBps
Network|Packets Received per second net|packetsRxPerSec
VMware by Broadcom  4280

---
## page 4281

 VMware Cloud Foundation 9.0
Metric Name Description
Network|Packets Transmitted per second net|packetsTxPerSec
Network|Received Packets Dropped net|droppedRx_summation
Storage|Demand (kbps) storage|demandKBps
Storage|Read Latency (msec) storage|totalReadLatency_average
Storage|Write Latency (msec) storage|totalWriteLatency_average
Summary|CPU Shares summary|cpu_shares
Summary|Memory Shares summary|mem_shares
Summary|Number of Datastores summary|number_datastore
Summary|Number of Networks summary|number_network
Summary|Workload Indicator summary|workload_indicator
System|Build Number sys|build
System|Heartbeat sys|heartbeat_summation
System|Product String sys|productString
System|Uptime (sec) sys|uptime_latest
System|vMotion Enabled vMotion should be enabled for all. It is not necessary to track
all VMs every five minutes.
sys|vmotionEnabled
Host System Metrics
VCF Operations collects many metrics for host systems, including CPU use, datastore, disk, memory, network, storage,
and summary metrics for host system objects.
Capacity metrics can be calculated for host system objects. See Capacity Analytics Generated Metrics.
GPU Metrics
GPU metrics provide information about the GPU usage and performance.
Metric Name Description
Metrics Aggregated at Host Level
GPU|Compute Utilization (%) The compute utilization percentage of a GPU.
GPU|Memory Usage (%) Memory currently in use as a percentage of total available
memory.
GPU|Memory Used (KB) The amount of GPU memory used in kilobytes.
GPU|Number of GPUs Number of GPUs.
GPU|Total Memory (KB) Total memory in kilobytes.
GPU Level Metrics
GPU|<GPU-ID>|Compute Utilization (%) The compute utilization percentage of a GPU.
GPU|<GPU-ID>|Memory Usage (%) Memory currently in use as a percentage of total available
memory.
VMware by Broadcom  4281

---
## page 4282

 VMware Cloud Foundation 9.0
Metric Name Description
GPU|<GPU-ID>|Memory Used (KB) The amount of GPU memory used in kilobytes.
GPU|<GPU-ID>|Memory Reserved (KB) The amount of GPU memory reserved in kilobytes.
GPU|<GPU-ID>|Total Memory (KB) Total memory in kilobytes.
GPU|<GPU-ID>|Temperature (Celsius) The temperature of a GPU in degrees Celsius.
GPU|<GPU-ID>|Power Used (Watt) The power used by a GPU in watts.
GPU:GPU-id|GPU Compute Usage (MHz) Total MHZ currently consumed by workloads (note time delay).
GPU:GPU-id|GPU Compute Limit (MHz) Total MHZ available on the GPU.
GPU:GPU-id|GPU Compute Demand (MHz) MHZ requested for a GPU over time.
GPU:GPU-id|GPU Memory Demand (MHz) KB requested over time.
GPU|Number of vGPU Configured VM-s Sum of GPU configured VMs.
Host System Metrics for ROI Dashboard
Host system metrics provide information about cost saving across vCenters
Metric Name Description
Cost|Monthly Additional Total Cost This metric shows the total sum of additional cost across all the
vCenters for an entire month.
Key: cost|additionalTotalCost
Configuration Metrics for Host Systems
Configuration metrics provide information about host system configuration.
Metric Name Description
Configuration|Hyperthreading|Active Displays the hyperthreading status of the host.
Key: configuration|hypwerthreading|active
Configuration|Hyperthreading|Available Displays whether the hyperthreading option is available for this
host.
Key: configuration|hypwerthreading|available
Configuration|Storage Device|Multipath Info|Total number of Active
Path
Displays the amount of active path information for the storage
device
Key: configuration|storagedevice|multipathinfo|total
numberofActive path
Configuration|Storage Device|Total number of path Displays the total number of path for the storage device.
Key: configuration|storagedevice|total number of path
Configuration|Failover Hosts Failover Hosts.
Key: configuration|dasConfig|admissionControlPolicy|failoverHost
Hardware Metrics for Host Systems
Hardware metrics provide information about host system hardware.
Metric Name Description
Hardware|Number of CPUs Number of CPUs for a host.
VMware by Broadcom  4282

---
## page 4283

 VMware Cloud Foundation 9.0
Metric Name Description
Key: hardware|cpuinfo|num_CpuCores
Hardware|ServiceTag Displays the service tag of the host system.
Key: hardware|servicetag
CPU Usage Metrics for Host Systems
CPU usage metrics provide information about CPU use.
Metric Name Description
CPU|Capacity Usage (%) Percent CPU capacity used.
Key: cpu|capacity_usagepct_average
CPU|Usage (%) Average CPU usage as a percentage.
Key: cpu|usage_average
CPU|CPU Contention (%) This metric indicates the percentage of time the virtual machines
in the ESXi hosts are unable to run because they are contending
for access to the physical CPU(s). This is the average number
of all VMs. Naturally, the number will be lower than the highest
number experienced by the worst hit VM (a VM that suffers the
highest CPU contention).
Use this metric to verify if the host is able to serve all of its VMs
well.
When using this metric, ensure the number is within your
expectation. The metric is affected by several factors so you need
to watch both relative numbers and absolute numbers. Relative
means a drastic change in value. This indicates that the ESXi is
unable to service its VMs.
Absolute means that the real value is high and should be
checked. One factor that impacts the CPU contention metric is
CPU Power Management. If CPU Power Management clocks
down the CPU speed from 3 GHz to 2 GHz that reduction in
speed is taken into consideration. This is because the VM is not
running at full speed.
Key: cpu|capacity_contentionPct
CPU|Demand (%) This metric shows the percentage of CPU resources all the VMs
would use if there was no CPU contention or any CPU limits set.
It represents the average active CPU load for the past five
minutes.
Keep the number of this metric below 100% if you set Power
Management to Maximum.
Key: cpu|demandPct
CPU|Demand (MHz) CPU demand in megahertz. CPU utilization level based on
descendant Virtual Machines utilization. Includes limits and
overhead to run Virtual Machines, but not reservations.
Key: cpu|demandmhz
CPU|IO Wait (ms) IO wait time in milliseconds.
Key: cpu|iowait
CPU|Number of CPU Sockets Number of CPU sockets.
Key: cpu|numpackages
CPU|Overall CPU Contention (ms) Overall CPU contention in milliseconds.
VMware by Broadcom  4283

---
## page 4284

 VMware Cloud Foundation 9.0
Metric Name Description
Key: cpu|capacity_contention
CPU|Provisioned Capacity (MHz) Capacity in MHz of the physical CPU cores.
Key: cpu|capacity_provisioned
CPU|Provisioned virtual CPUs Provisioned virtual CPUs.
Key: cpu|corecount_provisioned
CPU|Total Wait CPU time spent in idle state.
Key: cpu|wait
CPU|Demand CPU demand.
Key: cpu|demand_average
CPU|Usage (MHz) CPU use in megahertz.
Key: cpu|usagemhz_average
CPU|Reserved Capacity (MHz) The sum of the reservation properties of the (immediate) children
of the host's root resource pool.
Key: cpu|reservedCapacity_average
CPU|Total Capacity (MHz) Total CPU capacity in megahertz. Amount of CPU resources
configured on the ESXi hosts.
Key: cpu|capacity_provisioned
CPU|Overhead (KB) Amount of CPU overhead.
Key: cpu|overhead_average
CPU|Demand without overhead Value of demand excluding any overhead.
Key: cpu|demand_without_overhead
CPU|Core Utilization (%) Percent core utilization.
Key: cpu|coreUtilization_average
CPU|Utilization(%) Percent CPU utilization.
Key: cpu|utilization_average
CPU|Core Utilization (%) Core Utilization.
Key: cpu|coreUtilization_average
CPU|Utilization (%) Utilization.
Key: cpu|utilization_average
CPU|Co-stop (ms) Time the VM is ready to run, but is unable to due to co-scheduling
constraints.
Key: cpu|costop_summation
CPU|Latency (%) Percentage of time the VM is unable to run because it is
contending for access to the physical CPUs.
Key: cpu|latency_average
CPU|Ready (ms) Time spent in ready state.
Key: cpu|ready_summation
CPU|Run (ms) Time the virtual machine is scheduled to run.
Key: cpu|run_summation
CPU|Swap wait (ms) Amount of time waiting for swap space.
Key: cpu|swapwait_summation
CPU|Wait (ms) Total CPU time spent in wait state.
Key: cpu|wait_summation
CPU|Provisioned Capacity Provisioned capacity (MHz).
VMware by Broadcom  4284

---
## page 4285

 VMware Cloud Foundation 9.0
Metric Name Description
Key: cpu|vm_capacity_provisioned
CPU|Active Host Load For Balance (Long Term) Active Host Load For Balance (Long Term).
Key: cpu|acvmWorkloadDisparityPcttive_longterm_load
CPU|Active Host Load For Balance (Short Term) Active Host Load For Balance (Short Term).
Key: cpu|active_shortterm_load
CPU| CPU Model Displays the host's CPU model.
Key: cpu|cpu model
CPU|Peak CPU Core Usage The highest CPU Usage among the CPU cores. A constantly
high number indicates that one or more physical cores have high
utilization.
Key: cpu|peak_cpu_core_usage
CPU Utilization for Resources Metrics for Host Systems
CPU utilization for resources metrics provide information about CPU activity.
Metric Name Description
Rescpu|CPU Active (%) (interval) Average active time for the CPU over the past minute, past five
minutes, and at one-minute, five-minute, and 15-minute peak
active times.
Key:
rescpu|actav1_latest
rescpu|actav5_latest
rescpu|actav15_latest
rescpu|actpk1_latest
rescpu|actpk5_latest
rescpu|actpk15_latest
Rescpu|CPU Running (%) (interval) Average run time for the CPU over the past minute, past five
minutes, past 15 minutes, and at one-minute, five-minute, and 15-
minute peak times.
Key:
rescpu|runav1_latest
rescpu|runav5_latest
rescpu|runav15_latest
rescpu|runpk1_latest
rescpu|runpk5_latest
rescpu|runpk15_latest
Rescpu|CPU Throttled (%) (interval) Scheduling limit over the past minute, past five minutes, and past
15 minutes.
Key:
rescpu|maxLimited1_latest
rescpu|maxLimited5_latest
rescpu|maxLimited15_latest
Rescpu|Group CPU Sample Count Group CPU sample count.
Key: rescpu|sampleCount_latest
Rescpu|Group CPU Sample Period (ms) Group CPU sample period in milliseconds.
Key: rescpu|samplePeriod_latest
VMware by Broadcom  4285

---
## page 4286

 VMware Cloud Foundation 9.0
Datastore Metrics for Host Systems
Datastore metrics provide information about datastore use.
Metric Name Description
Datastore|Outstanding IO requests OIO for datastore.
Key: datastore|demand_oio
Datastore|Commands Averaged Average number of commands issued per second during the
collection interval.
Key: datastore|commandsAveraged_average
Datastore|Number of Outstanding IO Operations Number of outstanding IO operations.
Key: datastore|oio
Datastore|Total Latency (ms) The average amount of time taken for a command from the
perspective of a Guest OS. This is the sum of Kernel Command
Latency and Physical Device Command Latency.
Key: datastore|totalLatency_average
Datastore|Total Throughput (KBps) Usage Average (KBps).
Key: datastore|usage_average
Datastore|Demand Demand.
Key: datastore|demand
Datastore|Storage I/O Control aggregated IOPS Aggregate number of IO operations on the datastore.
Key: datastore|datastoreIops_average
Datastore|Read IOPS Average number of read commands issued per second during the
collection interval.
Key: datastore|numberReadAveraged_average
Datastore|Write IOPS Average number of write commands issued per second during
the collection interval.
Key: datastore|numberWriteAveraged_average
Datastore|Read Throughput (KBps) Rate of reading data from the datastore in kilobytes per second.
Key: datastore|read_average
Datastore|Storage I/O Control normalized latency (ms) Normalized latency in microseconds on the datastore. Data for all
virtual machines is combined.
Key: datastore|sizeNormalizedDatastoreLatency_average
Datastore|Read Latency (ms) Average amount of time for a read operation from the datastore.
Total latency = kernel latency + device latency.
Key: datastore|totalReadLatency_average
Datastore|Write Latency (ms) Average amount of time for a write operation to the datastore.
Total latency = kernel latency + device latency.
Key: datastore|totalWriteLatency_average
Datastore|Write Throughput (KBps) Rate of writing data to the datastore in kilobytes per second.
Key: datastore|write_average
Datastore|Max Queue Depth Max Queue Depth.
Key: datastore|datastoreMaxQueueDepth_latest
Datastore|Highest Latency Highest Latency.
Key: datastore|maxTotalLatency_latest
Datastore|Total Latency Max Total Latency Max (ms).
Key: datastore|totalLatency_max
VMware by Broadcom  4286

---
## page 4287

 VMware Cloud Foundation 9.0
Metric Name Description
Datastore|Read Latency Read Latency.
Key: datastore|datastoreNormalReadLatency_latest
Datastore|Write Latency Write Latency.
Key: datastore|datastoreNormalWriteLatency_latest
Datastore|Data Read Data Read.
Key: datastore|datastoreReadBytes_latest
Datastore|Data Read Rate Data Rate.
Key: datastore|datastoreReadIops_latest
Datastore|Read Load Storage DRS metric read load.
Key: datastore|datastoreReadLoadMetric_latest
Datastore|Outstanding Read Requests Outstanding Read Requests.
Key: datastore|datastoreReadOIO_latest
Datastore|Data Written Data Written.
Key: datastore|datastoreWriteBytes_latest
Datastore|Data Write Rate Data Write Rate.
Key: datastore|datastoreWriteIops_latest
Datastore|Write Load Storage DRS metric write load.
Key: datastore|datastoreWriteLoadMetric_latest
Datastore|Outstanding Write Requests Outstanding Write Requests.
Key: datastore|datastoreWriteOIO_latest
Datastore|VM Disk I/O Workload Disparity Percentage Disk I/O workload disparity among the VMs on the
Host.
Key: datastore|vmWorkloadDisparityPc
Datastore|Peak Datastore Read Latency The highest read latency among the datastores. A high number
indicates that one or more datastores are experiencing poor
performance.
Key: datastore|peak_datastore_readLatency
Datastore|Peak Datastore Write Latency The highest write latency among the datastores. A high number
indicates that one or more datastores are experiencing poor
performance.
Key: datastore|peak_datastore_writeLatency
Disk Metrics for Host Systems
Disk metrics provide information about disk use.
Metric Name Description
Disk|Total Throughput (KBps) Average of the sum of the data read and written for all of the disk
instances of the host or virtual machine.
disk|usage_average
Disk|I/O Usage Capacity This metric is a function of storage|usage_average and disk|
workload. storage|usage_average is an average over all storage
devices. This means that disk|usage_capacity is not specific to
the selected VM or the host of the VM.
Key: disk|usage_capacity
VMware by Broadcom  4287

---
## page 4288

 VMware Cloud Foundation 9.0
Metric Name Description
Disk|Total IOPS Average number of commands issued per second during the
collection interval.
Key: disk|commandsAveraged_average
Disk|Total Latency (ms) The average amount of time taken for a command from the
perspective of a Guest OS. This is the sum of Kernel Command
Latency and Physical Device Command Latency.
Key: disk|totalLatency_average
Disk|Read IOPS Average number of read commands issued per second during the
collection interval.
Key: disk|numberReadAveraged_average
Disk|Write IOPS Average number of write commands issued per second during
the collection interval.
Key: disk|numberWriteAveraged_average
Disk|Read Throughput (KBps) Amount of data read in the performance interval.
Key: disk|read_average
Disk|Write Throughput (KBps) Amount of data written to disk in the performance interval.
Key: disk|write_average
Disk|Bus Resets The number of bus resets in the performance interval.
Key: disk|busResets_summation
Disk|Read Latency (ms) The average amount of time taken for a read from the perspective
of a Guest OS. This is the sum of Kernel Read Latency and
Physical Device Read Latency.
Key: disk|totalReadLatency_average
Disk|Write Latency (ms) The average amount of time taken for a write from the
perspective of a Guest OS. This is the sum of Kernel Write
Latency and Physical Device Write Latency.
Key: disk|totalWriteLatency_average
Disk|Physical Device Latency (ms) The average time taken to complete a command from the
physical device.
Key: disk|deviceLatency_average
Disk|Kernel Latency (ms) The average time spent in ESX Server VMKernel per command.
Key: disk|kernelLatency_average
Disk|Queue Latency (ms) The average time spent in the ESX Server VMKernel queue per
command.
Key: disk|queueLatency_average
Disk|Number of Outstanding IO Operations Number of Outstanding IO Operations.
Key: disk|diskoio
Disk|Queued Operations Queued Operations.
Key: disk|diskqueued
Disk|Demand Demand.
Key: disk|diskdemand
Disk|Total Queued Outstanding operations Sum of Queued Operation and Outstanding Operations.
Key: disk|sum_queued_oio
Disk|Max Observed OIO Max Observed IO for a disk.
Key: disk|max_observed
VMware by Broadcom  4288

---
## page 4289

 VMware Cloud Foundation 9.0
Metric Name Description
Disk|Highest Latency Highest Latency.
Key: disk|maxTotalLatency_latest
Disk|Max Queue Depth Maximum queue depth during the collection interval.
Key: disk|maxQueueDepth_average
Disk|SCSI Reservation Conflicts SCSI Reservation Conflicts.
Key: disk|scsiReservationConflicts_summation
Memory Metrics for Host Systems
Memory metrics provide information about memory use and allocation.
Metric Name Description
Mem|Contention (%) This metric is used to monitor ESXi memory usage.
When the value is high, it means the ESXi is using a good
percentage of available memory. You may need to add more
memory to other memory-related metrics.
Key: mem|host_contentionPct
Mem|Contention (KB) Host contention in kilobytes.
Key: mem|host_contention
Mem|Host Usage (KB) Machine usage in kilobytes.
Key: mem|host_usage
Mem|Machine Demand (KB) Host demand in kilobytes.
Key: mem|host_demand
Mem|Overall Memory used to run VMs on Host (KB) Overall memory used to run virtual machines on the host in
kilobytes.
Key: mem|host_usageVM
Mem|Provisioned Memory (KB) Provisioned memory in kilobytes.
Key: mem|host_provisioned
Mem|Minimum Free Memory (KB) Minimum free memory.
Key: mem|host_minfree
Mem|Reserved Capacity (%) Percent reserved capacity.
Key: mem|reservedCapacityPct
Mem|Usable Memory (KB) Usable memory in kilobytes.
Key: mem|host_usable
Mem|Usage (%) Memory currently in use as a percentage of total available
memory.
Key: mem|host_usagePct
Mem|ESX System Usage Memory usage by the VMkernel and ESX user-level services.
Key: mem|host_systemUsage
Mem|Guest Active (KB) Amount of memory that is actively used.
Key: mem|active_average
Mem|Consumed (KB) Amount of host memory consumed by the virtual machine for
guest memory.
Key: mem|consumed_average
Mem|Granted (KB) Amount of memory available for use.
VMware by Broadcom  4289

---
## page 4290

 VMware Cloud Foundation 9.0
Metric Name Description
Key: mem|granted_average
Mem|Heap (KB) Amount of memory allocated for heap.
Key: mem|heap_average
Mem|Heap Free (KB) Amount of free space in the heap.
Key: mem|heapfree_average
Mem|VM Overhead (KB) Memory overhead reported by host.
Key: mem|overhead_average
Mem|Reserved Capacity (KB) Sum of memory reserved by consumers - Resource Pools
(RP) and powered on VMs that are not in Resource Pools.
RP reservations at the vCenter level are distributed to the
hosts depending on the number of powered on VMs and their
entitlement within the RP.
Key: mem|reservedCapacity_average
Mem|Shared (KB) Amount of shared memory in kilobytes.
Key: mem|shared_average
Mem|Shared Common (KB) Amount of shared common memory in kilobytes.
Key: mem|sharedcommon_average
Mem|Swap In (KB) Amount of memory swapped in.
Key: mem|swapin_average
Mem|Swap Out KB) Amount of memory swapped out.
Key: mem|swapout_average
Mem|Swap Used (KB) Amount of memory used for swapped space in kilobytes.
Key: mem|swapused_average
Mem|VM kernel Usage (KB) Amount of memory used by the VM kernel.
Key: mem|sysUsage_average
Mem|Unreserved (KB) Amount of unreserved memory in kilobytes.
Key: mem|unreserved_average
Mem|Balloon (KB) This metric shows the total amount of memory currently used by
the VM memory control. This memory was reclaimed from the
respective VMs at some point in the past, and was not returned.
Use this metric to monitor how much VM memory has been
reclaimed by ESXi through memory ballooning.
The presence of ballooning indicates the ESXi has been
under memory pressure. The ESXi activates ballooning when
consumed memory reaches a certain threshold.
Look for increasing size of ballooning. This indicates that there
has been a shortage of memory more than once. Look for size
fluctuations which indicate the ballooned out page was actually
required by the VM. This translates into a memory performance
problem for the VM requesting the page, since the page must first
be brought back from the disk.
Key: mem|vmmemctl_average
Mem|Zero (KB) Amount of memory that is all zero.
Key: mem|zero_average
Mem|State (0-3) Overall state of the memory. The value is an integer between 0
(high) and 3 (low).
Key: mem|state_latest
VMware by Broadcom  4290

---
## page 4291

 VMware Cloud Foundation 9.0
Metric Name Description
Mem|Usage (KB) Host memory use in kilobytes.
Key: mem|host_usage
Mem|Usage (%) Memory currently in use as a percentage of total available
memory.
Key: mem|usage_average
Mem|Swap In Rate (KBps) Rate at which memory is swapped from disk into active memory
during the interval in kilobyte per second.
Key: mem|swapinRate_average
Mem|Swap Out Rate (KBps) Rate at which memory is being swapped from active memory to
disk during the current interval in kilobytes per second.
Key: mem|swapoutRate_average
Mem|Active Write (KB) Average active writes in kilobytes.
Key: mem|activewrite_average
Mem|Compressed (KB) Average memory compression in kilobytes.
Key: mem|compressed_average
Mem|Compression Rate (KBps) Average compression rate in kilobytes per second.
Key: mem|compressionRate_average
Mem|Decompression Rate (KBps) Decompression rate in kilobytes per second.
Key: mem|decompressionRate_average
Mem|Total Capacity (KB) Sum of the amount of physical memory configured on ESXi hosts
of the cluster in KB.
Key: mem|host_provisioned
Mem|Latency Percentage of time the VM is waiting to access swapped or
compressed memory.
Key: mem|latency_average
Mem|Capacity Contention Capacity Contention.
Key: mem|capacity.contention_average
Mem|Swap In Rate from Host Cache Rate at which memory is being swapped from host cache into
active memory.
Key: mem|llSwapInRate_average
Mem|Swap In from Host Cache Amount of memory swapped-in from host cache.
Key: mem|llSwapIn_average
Mem|Swap Out Rate to Host Cache Rate at which memory is being swapped to host cache from
active memory.
Key: mem|llSwapOutRate_average
Mem|Swap Out to Host Cache Amount of memory swapped-out to host cache.
Key: mem|llSwapOut_average
Mem|Swap Space Used in Host Cache Space used for caching swapped pages in the host cache.
Key: mem|llSwapUsed_average
Mem|Low Free Threshold Threshold of free host physical memory below which ESX begins
to reclaim memory from VMs through ballooning and swapping.
Key: mem|lowfreethreshold_average
Mem|VM Memory Workload Disparity Percentage Memory workload disparity among the VMs on the
Host.
Key: mem|vmWorkloadDisparityPct
VMware by Broadcom  4291

---
## page 4292

 VMware Cloud Foundation 9.0
Metric Name Description
Mem|Active Host Load For Balance (Long Term) Active Host Load For Balance (Long Term).
Key: mem|active_longterm_load
Mem|Active Host Load For Balance (Short Term) Active Host Load For Balance (Short Term).
Key: mem|active_shortterm_load
Mem|Utilization Memory utilization level based on descendant Virtual Machines
utilization. Includes reservations, limits and overhead to run
Virtual Machines
Key: mem|total_need
Network Metrics for Host Systems
Network metrics provide information about network performance.
Metric Name Description
Network|Driver This metric displays the type of network driver.
Key: net|driver
Network|Speed This metric displays the network speed.
Key: net|speed
Network|Management Address This metric displays the management address of the host
network.
Key: net|management address
Network|IP Address This metric displays the IP address of the host network.
Key: net|IPaddress
Net|Packets Transmitted per second This metric shows the number of packets transmitted during the
collection interval.
Key: net|packetsTxPerSec
Net|Packets per second Number of packets transmitted and received per second.
Key: net|packetsPerSec
Net|Total Throughput (KBps) The sum of the data transmitted and received for all the NIC
instances of the host or virtual machine.
Key: net|usage_average
Net|I/O Usage Capacity I/O Usage Capacity.
Key: net|usage_capacity
Net|Data Transmit Rate (KBps) Average amount of data transmitted per second.
Key: net|transmitted_average
Net|Data Receive Rate (KBps) Average amount of data received per second.
Key: net|received_average
Net|Packets Received Number of packets received in the performance interval.
Key: net|packetsRx_summation
Net|Packets Transmitted Number of packets transmitted in the performance interval.
Key: net|packetsTx_summation
Net|Broadcast Packets Received Number of broadcast packets received during the sampling
interval.
Key: net|broadcastRx_summation
VMware by Broadcom  4292

---
## page 4293

 VMware Cloud Foundation 9.0
Metric Name Description
Net|Broadcast Packets Transmitted Number of broadcast packets transmitted during the sampling
interval.
Key: net|broadcastTx_summation
Net|Error Packets Transmitted Number of packets with errors transmitted.
Key: net|errorsTx_summation
Net|Multicast Packets Received Number of multicast packets received.
Key: net|multicastRx_summation
Net|Multicast Packets Transmitted Number of multicast packets transmitted.
Key: net|multicastTx_summation
Net|FT Throughput Usage FT Throughput Usage.
Key: net|throughput.usage.ft_average
Net|HBR Throughput Usage HBR Throughput Usage.
Key: net|throughput.usage.hbr_average
Net|iSCSI Throughput Usage iSCSI Throughput Usage.
Key: net|throughput.usage.iscsi_average
Net|NFS Throughput Usage NFS Throughput Usage.
Key: net|throughput.usage.nfs_average
Net|VM Throughput Usage VM Throughput Usage.
Key: net|throughput.usage.vm_average
Net|vMotion Throughput Usage vMotion Throughput Usage.
Key: net|throughput.usage.vmotion_average
Net|Unknown Protocol Frames Received Number of frames with unknown protocol received.
Key: net|unknownProtos_summation
System Metrics for Host Systems
System metrics provide information about the amount of CPU that resources and other applications use.
Metric Name Description
Sys|Power On 1 if the host system is powered on, 0 if the host system is
powered off, or -1 if the power state is unknown.
Key: sys|poweredOn
Sys|Uptime (seconds) Number of seconds since the last system startup.
Key: sys|uptime_latest
Sys|Disk Usage (%) Percent disk use.
Key: sys|diskUsage_latest
Sys|Resource CPU Usage (MHz) Amount of CPU that the Service Console and other applications
use.
Key: sys|resourceCpuUsage_average
Sys|Resource CPU Active (1 min. average) Percentage of resource CPU that is active. Average value during
a one-minute period.
Key: sys|resourceCpuAct1_latest
Sys|Resource CPU Active (%) (5 min. average) Percentage of resource CPU that is active. Average value during
a five-minute period.
Key: sys|resourceCpuAct5_latest
VMware by Broadcom  4293

---
## page 4294

 VMware Cloud Foundation 9.0
Metric Name Description
Sys|Resource CPU Alloc Max (MHz) Maximum resource CPU allocation in megahertz.
Key: sys|resourceCpuAllocMax_latest
Sys|Resource CPU Alloc Min (MHz) Minimum resource CPU allocation in megahertz.
Key: sys|resourceCpuAllocMin_latest
Sys|Resource CPU Alloc Shares Number of resource CPU allocation shares.
Key: sys|resourceCpuAllocShares_latest
Sys|Resource CPU Max Limited (%) (1 min. average) Percent of resource CPU that is limited to the maximum amount.
Average value during a one-minute period.
Key: sys|resourceCpuMaxLimited1_latest
Sys|Resource CPU Max Limited (%) (5 min. average) Percentage of resource CPU that is limited to the maximum
amount. Average value during a five-minute period.
Key: sys|resourceCpuMaxLimited5_latest
Sys|Resource CPU Run1 (%) Percent resource CPU for Run1.
Key: sys|resourceCpuRun1_latest
Sys|Resource CPU Run5 (%) Percent resource CPU for Run5.
Key: sys|resourceCpuRun5_latest
Sys|Resource Memory Alloc Max (KB) Maximum resource memory allocation in kilobytes.
Key: sys|resourceMemAllocMax_latest
Sys|Resource Memory Alloc Min (KB) Minimum resource memory allocation in kilobytes.
Key: sys|resourceMemAllocMin_latest
Sys|Resource Memory Alloc Shares Number of resource memory shares allocated.
Key: sys|resourceMemAllocShares_latest
Sys|Resource Memory Cow (KB) Cow resource memory in kilobytes.
Key: Sys|resourceMemCow_latest
Sys|Resource Memory Mapped (KB) Mapped resource memory in kilobytes.
Key: ys|resourceMemMapped_latest
Sys|Resource Memory Overhead (KB) Resource memory overhead in kilobytes.
Key: sys|resourceMemOverhead_latest
Sys|Resource Memory Shared (KB) Shared resource memory in kilobytes.
Key: sys|resourceMemShared_latest
Sys|Resource Memory Swapped (KB) Swapped resource memory in kilobytes.
Key: sys|resourceMemSwapped_latest
Sys|Resource Memory Touched (KB) Touched resource memory in kilobytes.
Key: sys|resourceMemTouched_latest
Sys|Resource Memory Zero (KB) Zero resource memory in kilobytes.
Key: sys|resourceMemZero_latest
Sys|Resource Memory Consumed Resource Memory Consumed Latest (KB).
Key: sys|resourceMemConsumed_latest
Sys|Resource File descriptors usage Resource File descriptors usage (KB).
Key: sys|resourceFdUsage_latest
Sys|vMotion Enabled 1 if vMotion is enabled or 0 if vMotion is not enabled.
Key: sys|vmotionEnabled
Sys|Not in Maintenance Not in maintenance.
Key: sys|notInMaintenance
VMware by Broadcom  4294

---
## page 4295

 VMware Cloud Foundation 9.0
Management Agent Metrics for Host Systems
Management agent metrics provide information about memory use.
Metric Name Description
Management Agent|Memory Used (%) Amount of total configured memory that is available for use.
Key: managementAgent|memUsed_average
Management Agent|Memory Swap Used (KB) Sum of the memory swapped by all powered-on virtual machines
on the host.
Key: managementAgent|swapUsed_average
Management Agent|Memory Swap In (KBps) Amount of memory that is swapped in for the Service Console.
Key: managementAgent|swapIn_average
Management Agent|Memory Swap Out (KBps) Amount of memory that is swapped out for the Service Console.
Key: managementAgent|swapOut_average
Management Agent|CPU Usage CPU usage.
Key: managementAgent|cpuUsage_average
Storage Adapter Metrics for Host Systems
Storage adapter metrics provide information about data storage use.
Metric Name Description
Storage Adapter|Driver Displays the driver details of the storage adapter.
Key: storage adapter|driver
Storage Adapter|Port WWN Displays the world wide network port for the storage adapter.
Key: storage adapter|portwwn
Storage Adapter|Total Usage (KBps) Total latency.
Key: storageAdapter|usage
Storage Adapter|Total IOPS Average number of commands issued per second by the storage
adapter during the collection interval.
Key: storageAdapter|commandsAveraged_average
Storage Adapter|Read IOPS Average number of read commands issued per second by the
storage adapter during the collection interval.
Key: storageAdapter|numberReadAveraged_average
Storage Adapter|Write IOPS Average number of write commands issued per second by the
storage adapter during the collection interval.
Key: storageAdapter|numberWriteAveraged_average
Storage Adapter|Read Throughput (KBps) Rate of reading data by the storage adapter.
Key: storageAdapter|read_average
Storage Adapter|Read Latency (ms) This metric shows the average amount of time for a read
operation by the storage adapter.
Use this metric to monitor the storage adapter read operation
performance. A high value means that the ESXi is performing a
slow storage read operation.
Total latency is the sum of kernel latency and device latency.
Key: storageAdapter|totalReadLatency_average
Storage Adapter|Write Latency (ms) This metric shows the average amount of time for a write
operation by the storage adapter.
VMware by Broadcom  4295

---
## page 4296

 VMware Cloud Foundation 9.0
Metric Name Description
Use this metric to monitor the storage adapter write performance
operation. A high value means that the ESXi is performing a
slow storage write operation.
Total latency is the sum of kernel latency and device latency.
Key: storageAdapter|totalWriteLatency_average
Storage Adapter|Write Throughput (KBps) Rate of writing data by the storage adapter.
Key: storageAdapter|write_average
Storage Adapter|Demand Demand.
Key: storageAdapter|demand
Storage Adapter|Highest Latency Highest Latency.
Key: torageAdapter|maxTotalLatency_latest
Storage Adapter|Outstanding Requests Outstanding Requests.
Key: storageAdapter|outstandingIOs_average
Storage Adapter|Queue Depth Queue Depth.
Key: storageAdapter|queueDepth_average
Storage Adapter|Queue Latency (ms) The average time spent in the ESX Server VM Kernel queue per
command.
Key: storageAdapter|queueLatency_average
Storage Adapter|Queued Queued.
Key: storageAdapter|queued_average
Storage Adapter|Peak Adapter Read Latency The highest read latency among the storage adapters. A
high number indicates that one or more storage adapters are
experiencing poor performance.
Key: storageAdapter|peak_adapter_readLatency
Storage Adapter|Peak Adapter Write Latency The highest write latency among the storage adapters. A
high number indicates that one or more storage adapters are
experiencing poor performance.
Key: storageAdapter|peak_adapter_writeLatency
Storage Metrics for Host Systems
Storage metrics provide information about storage use.
Metric Name Description
Storage|Total IOPS Average number of commands issued per second during the
collection interval.
Key: storage|commandsAveraged_average
Storage|Read Latency (ms) Average amount of time for a read operation in milliseconds.
Key: storage|totalReadLatency_average
Storage|Read Throughput (KBps) Read throughput rate in kilobytes.
Key: storage|read_average
Storage|Read IOPS Average number of read commands issued per second during
the collection interval.
Key: storage|numberReadAveraged_average
Storage|Total Latency (ms) Total latency in milliseconds.
Key: storage|totalLatency_average
VMware by Broadcom  4296

---
## page 4297

 VMware Cloud Foundation 9.0
Metric Name Description
Storage|Total Usage (KBps) Total throughput rate in kilobytes per second.
Key: storage|usage_average
Storage|Write Latency (ms) Average amount of time for a write operation in milliseconds.
Key: storage|totalWriteLatency_average
Storage|Write Throughput (KBps) Write throughput rate in kilobytes per second.
Key: storage|write_average
Storage|Write IOPS Average number of write commands issued per second during
the collection interval.
Key: storage|numberWriteAveraged_average
Sensor Metrics for Host Systems
Sensor metrics provide information about host system cooling.
Metric Name Description
Sensor|Fan|Speed (%) Percent fan speed.
Key: Sensor|fan|currentValue
Sensor|Fan|Health State Fan health state.
Key: Sensor|fan|healthState
Sensor|Temperature|Temp C Fan temperature in centigrade.
Key: Sensor|temperature|currentValue
Sensor|Temperature|Health State Fan health state.
Key: Sensor|temperature|healthState
Power Metrics for Host Systems
Power metrics provide information about host system power use.
Metric Name Description
Power|Total Energy Consumed in the collection period (Wh) Displays the total electricity consumed based on the time
interval selected. The default collection cycle is set to 5 mins.
You can continue using the default setting or edit it for each
adapter instance. For example, if the time interval is set to its
default value, the value represents the energy consumed per 5
mins.
Power|Total Host System Power Consumed in an Hour (Wh) Displays the the total electricity power consumed in an hour by
ESXi Host. The data collected is over a period of an hour and
published along with the other metrics in VCF Operations. In
case of a connectivity or availability issue in VCF Operations
or vCenter adapter instance, this hourly metric might not be
published and the missed value during this period does not get
recalculated. Once the connection is re-established, the next
data points get published.
Note:
This metric is deactivated by default. You can activate it from
the Policies page.
Power|Power (Watt) Host power use in watts.
VMware by Broadcom  4297

---
## page 4298

 VMware Cloud Foundation 9.0
Metric Name Description
Key: power|power_average
Power|Current Power Consumption Rate (Watt) The power consumption rate per second, averaged over the
reporting period.
Key: power|power_average
Power|Power Cap (Watt) Host power capacity in watts.
Key: power|powerCap_average
Power|Host Power Capacity Usage – Idle Power consumed by the host in its idle state. This is the power
consumed by the host when there are no VMs in it.
Key: power|capacity.usageIdle_average
Power|(DEP) Energy (Joule) Total energy consumed in joules.
Key: power|energy_summation
Disk Space Metrics for Host Systems
Disk space metrics provide information about disk space use.
Metric Name Description
Diskspace|Number of Virtual Disks Number of virtual disks.
Key: diskspace|numvmdisk
Diskspace|Shared Used (GB) Used shared disk space in gigabytes.
Key: diskspace|shared
Diskspace|Snapshot Disk space used by snapshots in gigabytes.
Key: diskspace|snapshot
Diskspace|Virtual Disk Used (GB) Disk space used by virtual disks in gigabytes.
Key: diskspace|diskused
Diskspace|Virtual machine used (GB) Disk space used by virtual machines in gigabytes.
Key: diskspace|used
Diskspace|tTotal disk space used Total disk space used on all datastores visible to this object.
Key: diskspace|total_usage
Diskspace|Total disk spacey Total disk space on all datastores visible to this object.
Key: diskspace|total_capacity
Diskspace|Total provisioned disk space Total provisioned disk space on all datastores visible to this
object.
Key: diskspace|total_provisioned .
Diskspace|Utilization (GB) Storage space utilized on connected vSphere datastores.
Key: diskspace|total_usage
Diskspace|Workload (%) Total storage space available on connected vSphere
datastores.
Key: diskspace|total_capacity
Summary Metrics for Host Systems
Summary metrics provide information about overall host system performance.
VMware by Broadcom  4298

---
## page 4299

 VMware Cloud Foundation 9.0
Metric Name Description
Summary|Number of Running VMs This metric shows the number of VMs running on the host
during the last metric collection time.
Large spikes of running VMs might be a reason for CPU or
memory spikes as more resources are used in the host.
Number of Running VMs gives you a good indicator of how
many requests the ESXi host must juggle. This excludes
powered off VMs as they do not impact ESXi performance.
A change in this number in your environment can contribute
to performance problems. A high number of running VMs in
a host also means a higher concentration risk, as all the VMs
will become unavailable (or be relocated by HA) if the ESXi
crashes.
Look for any correlation between spikes in the number
of running VMs and spikes in other metrics such as CPU
Contention/Memory Contention.
Key: summary|number_running_vms
Summary|Maximum Number of VMs Maximum number of virtual machines
Key: summary|max_number_vms
Summary|Number of vMotions This metric shows the number of vMotions that occurred in the
host in the last X minutes.
The number of vMotions is a good indicator of stability. In
a healthy environment, this number should be stable and
relatively low.
Look for correlation between vMotions and spikes in other
metrics such as CPU/Memory contention.
The vMotion should not create any spikes, however, the VMs
moved into the host might create spikes in memory usage,
contention and CPU demand and contention.
Key: summary|number_vmotion
Summary|Total Number of Datastores Total Number of Datastores.
Key: summary|total_number_datastores
Summary|Number of VCPUs on Powered On VMs Total number of VCPUs of Virtual Machines that are powered
on.
Key: summary|number_running_vcpus
Summary|Total Number of VMs Total number of virtual machines.
Note:  This is the total number of VMs excluding VM
templates.
Key: summary|total_number_vms
Summary|Number of VM Templates Number of VM Templates
Key: summary|number_vm_templates
Summary|Consider for Balance Summary|Consider for Balance = 1 when the host is Powered
On, Connected, not in Maintenance Mode, and not a Failover
Host, otherwise it = -1
HBR Metrics for Host Systems
Host-based replication (HBR) metrics provide information about vSphere replication.
VMware by Broadcom  4299

---
## page 4300

 VMware Cloud Foundation 9.0
Metric Name Description
HBR|Replication Data Received Rate Replication Data Received Rate.
Key: hbr|hbrNetRx_average
HBR|Replication Data Transmitted Rate Replication Data Transmitted Rate.
Key: hbr|hbrNetTx_average
HBR|Replicated VM Count Number of replicated virtual machines.
Key: hbr|hbrNumVms_average
Cost Metrics for Host Systems
Cost metrics provide information about the cost.
Metric Name Description
Monthly Maintenance Total Cost Monthly total cost for maintenance.
Key: cost|maintenanceTotalCost
Monthly Host OS License Total Cost Monthly total cost for the host operating system license.
Key: cost|hostOslTotalCost
Monthly Network Total Cost Monthly total cost for network including cost of NIC cards
associated with host.
Key: cost|networkTotalCost
Monthly Server Hardware Total Cost Monthly total cost for server hardware, based on amortized
monthly value.
Key: cost|hardwareTotalCost
Monthly Facilities Total Cost Monthly total cost of facilities including real estate, power, and
cooling.
Key: cost|facilitiesTotalCost
Monthly Server Labor Total Cost Monthly total cost for the server operating system labor.
Key: cost|hostLaborTotalCost
Monthly Server Fully Loaded Cost Monthly cost for a fully loaded server incorporating all cost driver
values attributed to the server.
Key: cost|totalLoadedCost
MTD Server Total Cost Month to date cost for a fully loaded server incorporating all cost
driver values attributed to the server.
Key: totalMTDCost
Server Accumulated Depreciation Month to date accumulated cost for a deprecated server.
Key: Cost|Server Accumulated Depreciation
Aggregated Daily Total Cost Daily aggregate daily total cost of the deleted VM present in the
host system.
Key: Cost|aggregatedDailyTotalCost
Aggregated Deleted VM Daily Total Cost Daily aggregate cost of the deleted VM present in the host system.
Key: Cost|aggregatedDeletedVmDailyTotalCost
Disabled Instanced Metrics
The instance metrics created for the following metrics are disabled in this version of VCF Operations. This means that
these metrics collect data by default but all the instanced metrics created for these metrics, do not collect data by default.
VMware by Broadcom  4300

---
## page 4301

 VMware Cloud Foundation 9.0
Metric Name
Datastore|Outstanding IO requests (OIOs)
Datastore|Read IOPS
Datastore|Read Latency (ms)
Datastore|Read Throughput (KBps)
Datastore|Total Latency (ms)
Datastore|Total Throughput (KBps)
Datastore|unmapIOs_summation
Datastore|unmapsize_summation
Datastore|Write IOPS
Datastore|Write Latency (ms)
Datastore|Write Throughput (KBps)
Disk|Physical Device Latency (ms)
Disk|Queue Latency (ms)
Disk|Read IOPS
Disk|Read Latency (ms)
Disk|Read Throughput (KBps)
Disk|Write IOPS
Disk|Write Latency (ms)
Disk|Write Throughput (KBps)
Net|Data Receive Rate (KBps)
Net|Data Transmit Rate (KBps)
Net|Error Packets Transmitted
Net|Packets Dropped (%)
Net|Packets Transmitted per second
Net|Received Packets Dropped
Net|Transmitted Packets Dropped
Net|Usage Rate (%)
Storage Adapter|Read IOPS
Storage Adapter|Read Latency (ms)
Storage Adapter|Read Throughput (KBps)
Storage Adapter|Write IOPS
Storage Adapter|Write Latency (ms)
Storage Adapter|Write Throughput (KBps)
Disabled Metrics
The following metrics are disabled in this version of VCF Operations. This means that they do not collect data by default.
You can enable these metrics in the Policy workspace. For more information, in VMware Docs search for Collect Metrics
and Properties Details.
VMware by Broadcom  4301

---
## page 4302

 VMware Cloud Foundation 9.0
Metric Name Key
CPU|Idle (msec) cpu|idle_summation
CPU|Used (msec) cpu|used_summation
Datastore I/O|Average Observed Virtual Machine Disk I/O Workload datastore|vmPopulationAvgWorkload
Datastore I/O|Max Observed Number of Outstanding IO Operations datastore|maxObserved_OIO
Datastore I/O|Max Observed Read Rate (kbps) datastore|maxObserved_Read
Datastore I/O|Max Observed Reads per second datastore|maxObserved_NumberRead
Datastore I/O|Max Observed Write Rate (kbps) datastore|maxObserved_Write
Datastore I/O|Max Observed Writes per second datastore|maxObserved_NumberWrite
Datastore I/O|Maximum Observed VM Disk I/O Workload datastore|vmPopulationMaxWorkload
Network I/O|bytesRx (kbps) net|bytesRx_average
Network I/O|bytesTx (kbps) net|bytesTx_average
Network I/O|Demand (%) net|demand
Network I/O|Error Packets Received net|errorsRx_summation
Network I/O|Max Observed Received Throughput (kbps) net|maxObserved_Rx_KBps
Network I/O|Max Observed Throughput (kbps) net|maxObserved_KBps
Network I/O|Max Observed Transmitted Throughput (kbps) net|maxObserved_Tx_KBps
Network I/O|Packets Received per second net|packetsRxPerSec
Network I/O|Packets Dropped net|dropped
Summary|Workload Indicator summary|workload_indicator
vFlash Module|Latest Number of Active Vm Disks vflashModule|numActiveVMDKs_latest
Net|Received Packets Dropped Number of received packets dropped in the performance
interval.
Key: net|droppedRx_summation
Net|Transmitted Packets Dropped Number of transmitted packets dropped in the performance
interval.
Key: net|droppedTx_summation
Net|Packets Dropped (%) This metric shows the percentage of received and transmitted
packets dropped during the collection interval.
This metric is used to monitor reliability and performance
of the ESXi network. When a high value is displayed, the
network is not reliable and performance suffers.
Key: net|droppedPct
Diskspace|Not Shared (GB) Unshared disk space in gigabytes.
Key: diskspace|notshared
Cluster Compute Resource Metrics
VCF Operations collects configuration, disk space, CPU use, disk, memory, network, power, and summary metrics for
cluster compute resources.
Cluster Compute Resource metrics include capacity and badge metrics. See definitions in:
• Capacity Analytics Generated Metrics
VMware by Broadcom  4302

---
## page 4303

 VMware Cloud Foundation 9.0
• Badge Metrics
GPU Metrics
GPU metrics provide information about the GPU usage and performance.
Metric Name Description
GPU|Compute Utilization (%) The compute utilization percentage of a GPU.
GPU|Memory Usage (%) Memory currently in use as a percentage of total available
memory.
GPU|Memory Used (KB) The amount of GPU memory used in kilobytes.
GPU|Number of GPUs Number of GPUs.
GPU|Total Memory (KB) Total memory in kilobytes.
GPU|Number of vGPU Configured VM-s Sum of GPU configured VMs.
Cluster Metrics for ROI Dashboard
Cluster metrics provide information about the metrics in ROI dashboard.
Metric Name Description
Total Number Of Reclaimable Hosts This metric displays the total number of reclaimable hosts across
all vCenters.
Key: metric=cost|reclaimableHostCost
Total Reclaimable Host Cost This metric displays the reclaimable host cost based on the
recommended size.
Key: cost|reclaimableHostCost
Configuration Metrics for Cluster Compute Resources
Configuration metrics provide information about configuration settings.
Metric Name Description
Configuration|DAS Configuration|Admission Control
Enabled
DAS configuration admission control enabled.
Key: configuration|dasconfig|AdministrationControlEnabled
Configuration|DAS Configuration|Active Admission Control
Policy
DAS configuration active admission control policy.
Key: configuration|dasconfig|activeAdministrationControlPolicy
Configuration|DRS Configuration|Affinity Rules Affinity rules for DRS configuration.
Key: configuration|DRSconfiguration|affinity rules
Configuration|DRS Configuration|Tolerance Imbalance
Threshold
Displays the tolerance imbalance threshold for DRS configuration.
Key: configuration|DRSconfiguration|ToleranceimbalanceThreshold
Configuration|DRS Configuration|Default DRS behavior Displays the default DRS configuration behavior.
Key: configuration|DRSconfiguration|DefaultDRSbehaviour
Configuration|DRS Configuration|Idle Consumed Memory Displays the idle memory consumed by DRS configuration.
Key: configuration|DRSconfiguration|IdleConsumedMemory
Configuration|DRS Configuration| DRS vMotion Rate Displays the vMotion rate for the DRS configuration.
Key: configuration|DRSconfiguration|DRSvMotion Rate
VMware by Broadcom  4303

---
## page 4304

 VMware Cloud Foundation 9.0
Metric Name Description
Configuration|DPM Configuration|Default DPM behavior Displays the default behavior for the DPM configuration.
Key: configuration|DPMconfiguration|DefaultDPMbehaviour
Configuration|DPM Configuration|DPM Enabled Displays whehter the DPM Configuration is enabled or not.
Key: configuration|DPMConfiguration|DPMEnabled
Configuration|Failover Level DAS configuration failover level.
Key: configuration|dasconfig|failoverLevel
Configuration|Active Admission Control Policy DAS configuration active admission control policy.
Key: configuration|dasconfig|activeAdministrationControlPolicy
Configuration|CPU Failover Resources Percent Percent CPU failover resources for DAS configuration admission control
policy.
Key: configuration|dasconfig|adminissionControlPolicy|
cpuFailoverResourcesPercent
Configuration|Memory Failover Resources Percent Percent memory failover resources for DAS configuration admission
control policy.
Key: configuration|dasconfig|adminissionControlPolicy|
memoryFailoverResourcesPercent
Disk Space Metrics for Cluster Compute Resources
Disk space metrics provide information about disk space use.
Metric Name Description
DiskSpace|Snapshot Space Displays the disk space used by the snapshot.
Key: DiskSpace|snapshot space
Diskspace|Virtual machine used (GB) Space used by virtual machine files in gigabytes.
Key: diskspace|used
Diskspace|Total disk space used Total disk space used on all datastores visible to this object.
Key: diskspace|total_usage
Diskspace|Total disk space Total disk space on all datastores visible to this object.
Key: diskspace|total_capacity
Diskspace|Total provisioned disk space Total provisioned disk space on all datastores visible to this object.
Key: diskspace|total_provisioned
Diskspace|Virtual Disk Used (GB) Space used by virtual disks in gigabytes.
Key: diskspace|diskused
Diskspace|Snapshot Space (GB) Space used by snapshots in gigabytes.
Key: diskspace|snapshot
Diskspace|Shared Used (GB) Shared used space in gigabytes.
Key: diskspace|shared
Diskspace|Utilization (GB) Storage space used on the connected vSphere Datastores.
Key: diskspace|total_usage
Diskspace|Total Capacity (GB) Total storage space available on the connected vSphere datastores.
Key: diskspace|total_capacity
CPU Usage Metrics for Cluster Compute Resources
CPU usage metrics provide information about CPU use.
VMware by Broadcom  4304

---
## page 4305

 VMware Cloud Foundation 9.0
Metric Name Description
CPU|Allocation|Usable Capacity after HA and Buffer
(vCPUs)
This metric shows the total capacity taking into consideration the over-
commit ratio and after subtracting the CPU resources needed for HA and
reserved buffer.
Key: cpu|alloc|usableCapacity
CPU|Capacity Usage This metric shows the percentage of the capacity used.
Key: cpu|capacity_usagepct_average
CPU|CPU Contention (%) This metric is an indicator of the overall contention for CPU resources that
occurs across the workloads in the cluster. When contention occurs, it
means that some of the virtual machines are not immediately getting the
CPU resources they are requesting.
Use this metric to identify when a lack of CPU resources might be
causing performance issues in the cluster.
This metric is the sum of the CPU contention across all hosts in the
cluster averaged over two times the number of physical CPUs in the
cluster to account for hyper-threading. CPU contention takes into
account:
• CPU Ready
• CPU Co-stop
• Power management
• Hyper threading
This metric is more accurate than CPU Ready since it takes into account
CPU Co-stop and Hyper threading.
When using this metric, the number should be lower than the
performance you expect. If you expect performance at 10%, then the
number should be lower than 10%.
Since this value is averaged across all hosts in the cluster, you might find
that some hosts have a higher CPU contention while others are lower.
To ensure that vSphere spreads out the running workloads across hosts,
consider enabling a fully automated DRS in the cluster.
Key: cpu|capacity_contentionPct
CPU|Demand|Usable Capacity after HA and Buffer (MHz) This metric shows the total capacity after subtracting the CPU resources
needed for HA and reserved buffer.
Key: cpu|demand|usableCapacity
CPU|Demand (%) This metric is an indicator of the overall demand for CPU resources by
the workloads in the cluster.
It shows the percentage of CPU resources that all the virtual machines
might use if there were no CPU contention or CPU limits set. It represents
the average active CPU load in the past five minutes.
Key: cpu|demandPct
CPU|Demand (MHz) Sum of CPU utilization of all virtual machines on this cluster, including
limits and VM overhead.
Key: cpu|demandmhz
CPU|Number of CPU Sockets Number of CPU sockets.
Key: cpu|numpackages
CPU|Overall CPU Contention Overall CPU contention in milliseconds.
Key: cpu|capacity_contention
CPU|Host Provisioned Capacity Provisioned CPU capacity in megahertz.
Key: cpu|capacity_provisioned
VMware by Broadcom  4305

---
## page 4306

 VMware Cloud Foundation 9.0
Metric Name Description
CPU|Provisioned CPUs Number of Physical CPUs (Cores).
Key: cpu|corecount_provisioned
CPU|Usage (MHz) Average CPU use in megahertz.
Key: cpu|usagemhz_average
CPU| VM CPU Usage (Mhz) Sum of CPU usages of all VMs in the cluster. The CPU|Usage (Mhz)
metric value of each VM is taken for summation.
Key: cpu|vm_usagemhz_average
CPU|Demand CPU Demand.
Key: cpu|demand_average
CPU|Overhead Amount of CPU overhead.
Key: cpu|overhead_average
CPU|Demand without overhead Value of demand excluding any overhead.
Key: cpu|demand_without_overhead
CPU|Provisioned Capacity Provisioned Capacity (MHz).
Key: cpu|vm_capacity_provisioned
CPU|Number of hosts stressed Number of hosts stressed.
Key: cpu|num_hosts_stressed
CPU|Stress Balance Factor Stress Balance Factor.
Key: cpu|stress_balance_factor
CPU|Lowest Provider Capacity Remaining Lowest Provider Capacity Remaining.
Key: cpu|min_host_capacity_remaining
CPU|Workload Balance Factor Workload Balance Factor.
Key: cpu|workload_balance_factor
CPU|Highest Provider Workload Highest Provider Workload.
Key: cpu|max_host_workload
CPU|Host workload Max-Min Disparity Difference of Max and Min host workload in the container.
Key: cpu|host_workload_disparity
CPU|Host stress Max-Min Disparity Difference of Max and Min host stress in the container.
Key: cpu|host_stress_disparity
CPU|Total Capacity (MHz) Total CPU resources configured on the descendant ESXi hosts.
Key: cpu|capacity_provisioned
CPU|Usable Capacity (MHz) The usable CPU resources that are available for the virtual machines
after considering reservations for vSphere High Availability (HA) and
other vSphere services.
Key: cpu|haTotalCapacity_average
Disk Metrics for Cluster Compute Resources
Disk metrics provide information about disk use.
Metric Name Description
Disk|Total IOPS Average number of commands issued per second during the collection
interval.
Key: disk|commandsAveraged_average
VMware by Broadcom  4306

---
## page 4307

 VMware Cloud Foundation 9.0
Metric Name Description
Disk|Total Latency (ms) Average amount of time taken for a command from the perspective of the
guest operating system. This metric is the sum of the Kernel Command
Latency and Physical Device Command Latency metrics.
Key: disk|totalLatency_average
Disk|Read Latency (ms) Average amount of time for a read operation from the virtual disk. The
total latency is the sum of Kernel latency and device latency.
Key: disk|totalReadLatency_average
Disk|Write Latency (ms) The average amount of time taken for a read from the perspective of a
Guest OS. This is the sum of Kernel Read Latency and Physical Device
Read Latency.
Key: disk|totalWriteLatency_averag
Disk|Read IOPS Average number of read commands issued per second during the
collection interval.
Key: disk|numberReadAveraged_averag
Disk|Total Throughput (KBps) Average of the sum of the data read and written for all the disk instances
of the host or virtual machine.
Key: disk|usage_average
Disk|Write IOPS Average number of write commands issued per second during the
collection interval.
Key: disk|numberWriteAveraged_average
Disk|Read Requests Amount of data read from the disk during the collection interval.
Key: disk|read_average
Disk|Write Requests Amount of data written to the disk during the collection interval.
Key: disk|write_average
Disk|Total Queued Outstanding operations Sum of queued operation and outstanding operations.
Key: disk|sum_queued_oio
Disk|Max Observed OIO Max observed outstanding IO for a disk.
Key: disk|max_observed
Memory Metrics for Cluster Compute Resources
Memory metrics provide information about memory use and allocation.
Metric Name Description
Mem|Active Write (KB) Active writes in kilobytes.
Key: mem|activewrite_average
Mem|Compressed (KB) Average compression in kilobytes.
Key: mem|compressed_average
Mem|Compression Rate (KBps) Average compression rate in kilobytes.
Key: mem|compressionRate_average
Mem|Consumed (KB) Amount of host memory consumed by the virtual machine for guest
memory.
Key: mem|consumed_average
VMware by Broadcom  4307

---
## page 4308

 VMware Cloud Foundation 9.0
Metric Name Description
Mem|Contention (%) This metric is an indicator of the overall contention for memory
resources that occurs across the workloads in the cluster. When
contention occurs, it means that some of the VMs are not immediately
getting the memory resources that they are requesting.
Use this metric to identify when lack of memory resources might be
causing performance issues in the cluster.
Key: mem|host_contentionPct
Mem|Contention (KB) Contention in kilobytes.
Key: mem|host_contention
Mem|Decompression Rate (KBps Decompression rate in kilobytes.
Key: mem|decompressionRate_average
Mem|Granted (KB) Amount of memory available for use.
Key: mem|granted_average
Mem|Guest Active (KB) Amount of memory that is actively used.
Key: mem|active_average
Mem|Heap (KB) Amount of memory allocated for heap.
Key: mem|heap_average
Mem|Heap Free (KB) Free space in the heap.
Key: mem|heapfree_average
Mem|Balloon This metric shows the amount of memory currently used by the virtual
machine memory control. It is only defined at the VM level.
Key: mem|vmmemctl_average
Mem|VM Overhead (KB) Memory overhead reported by host.
Key: mem|overhead_average
Mem|Provisioned Memory (KB) Provisioned memory in kilobytes.
Key: mem|host_provisioned
Mem|Reserved Capacity (KB) Sum of memory reservations by consumers such as Resource Pools
(RP) and powered on VMs that are not in Resource Pools, aggregated
and published on cluster level. RP reservations at the vCenter level
are distributed to hosts depending on the number of powered on VMs
and their entitlement within the Resource Pool. For more information
on resource allocation reservation, share, and limit, see Configuring
Resource Allocation Settings.
Key: mem|reservedCapacity_average
Mem|Shared (KB) Amount of shared memory.
Key: mem|shared_average
Mem|Shared Common (KB) Amount of shared common memory.
Key: mem|sharedcommon_average
Mem|Swap In (KB) Amount of memory that is swapped in for the service console.
Key: mem|swapin_average
Mem|Swap In Rate (KBps) Rate at which memory is swapped from disk into active memory during
the interval.
Key: mem|swapinRate_average
Mem|Swap Out (KB) Amount of memory that is swapped out for the service console.
Key: mem|swapout_average
VMware by Broadcom  4308

---
## page 4309

 VMware Cloud Foundation 9.0
Metric Name Description
Mem|Swap Out Rate (KBps) Rate at which memory is being swapped from active memory into disk
during the current interval.
Key: mem|swapoutRate_average
Mem|Swap Used (KB) Amount of memory used for swap space.
Key: mem|swapused_average
Mem|Total Capacity (KB) Total capacity in kilobytes.
Key: mem|totalCapacity_average
Mem|Unreserved (KB) Memory available for reservation by VMs and Resource Pools (RP),
aggregated and published on cluster level. The reservations are set for
VMs and RPs and not for ESXi hosts or clusters. For more information
on resource allocation reservation, share, and limit, see Configuring
Resource Allocation Settings.
Key: mem|unreserved_average
Mem|Usable Memory (KB) Usable memory in kilobytes.
Key: mem|host_usable
Mem|Usage/Usable Percent memory used.
Key: mem|host_usagePct
Mem|Host Usage (KB) Memory use in kilobytes.
Key: mem|host_usage
Mem|Machine Demand Memory Machine Demand in KB.
Key: mem|host_demand
Mem|ESX System Usage Memory usage by the VMkernel and ESX user-level services.
Key: mem|host_systemUsage
Mem|Usage (%) This metric shows the portion of the total memory in all hosts in the
cluster that is being used.
This metric is the sum of memory consumed across all hosts in the
cluster divided by the sum of physical memory across all hosts in the
cluster.
? memory consumed on all hosts
- X 100%
? physical memory on all hosts
Memory |Workload (%) Demand over usable capacity. Wherever applicable, demand includes
limit and contention.
Mem|Usage (KB) Memory currently in use as a percentage of total available memory.
Key: mem|usage_average
Mem|VM kernel Usage (KB) Amount of memory that the VM kernel uses.
Key: mem|sysUsage_average
Mem|Zero (KB) Amount of memory that is all 0.
Key: mem|zero_average
Mem|Number of Hosts Stressed Number of hosts stressed.
Key: mem|num_hosts_stressed
Mem|Stress Balance Factor Stress balance factor.
Key: mem|stress_balance_factor
Mem|Lowest Provider Capacity Remaining Lowest provider capacity remaining.
Key: mem|min_host_capacity_remaining
VMware by Broadcom  4309

---
## page 4310

 VMware Cloud Foundation 9.0
Metric Name Description
Mem|Workload Balance Factor Workload balance factor.
Key: mem|workload_balance_factor
Mem|Highest Provider Workload Highest provider workload.
Key: mem|max_host_workload
Mem|Host workload Max-Min Disparity Difference of Max and Min host workload in the container.
Key: mem|host_workload_disparity
Mem|Host stress Max-Min Disparity Difference of Max and Min host stress in the container.
Key: mem|host_stress_disparity
Mem|Utilization (KB) Memory utilization level based on the descendant virtual machines
utilization. Includes reservations, limits, and overhead to run the Virtual
Machines.
Key: mem|total_need
Mem|Total Capacity (KB) Sum of the amount of physical memory configured on ESXi hosts of the
cluster.
Key: mem|host_provisioned
Mem|Usable Capacity (KB) Memory resources available after subtracting reservations for vSphere
HA (failover host/s) from the cluster's total memory capacity.
Hosts that are in the maintenance mode are not included in the
calculation.
Key: mem|haTotalCapacity_average
Network Metrics for Cluster Compute Resources
Network metrics provide information about network performance.
Metric Name Description
Net|Data Receive Rate (KBps) Average amount of data received per second.
Key: net|received_average
Net|Data Transmit Rate (KBps) Average amount of data transmitted per second.
Key: net|transmitted_average
Net|Packets Dropped Number of packets dropped in the performance interval.
Key: net|dropped
Net|Packets Dropped (%) Percentage of packets dropped.
Key: net|droppedPct
Net|Packets Received Number of packets received in the performance interval.
Key: net|packetsRx_summation
Net|Packets Transmitted Number of packets transmitted in the performance interval.
Key: net|packetsTx_summation
Net|Received Packets Dropped Number of received packets dropped in the performance interval.
Key: net|droppedRx_summation
Net|Transmitted Packets Dropped Number of transmitted packets dropped in the performance interval.
Key: net|droppedTx_summation
Net|Total Throughput (KBps) The sum of the data transmitted and received for all the NIC instances
of the host or virtual machine.
Key: net|usage_average
VMware by Broadcom  4310

---
## page 4311

 VMware Cloud Foundation 9.0
Metric Name Description
Network|Error Packets Displays the total number of error packets (transmitted and received)
from all the ESXi in the cluster within a time interval of 20 seconds.
Key: Network|Error Packets
Datastore Metrics for Cluster Compute Resources
Datastore metrics provide information about Datastore use.
Metric Name Description
Datastore|TotalThroughput Displays the total throughput for the datastore.
Key: datastore|thorughput
Datastore|Outstanding IO requests OIO for datastore.
Key: datastore|demand_oio
Datastore|Read IOPS Average number of read commands issued per second during the
collection interval.
Key: datastore|numberReadAveraged_average
Datastore|Write IOPS Average number of write commands issued per second during the
collection interval.
Key: datastore|numberWriteAveraged_average
Datastore|Read Throughput (KBps) Amount of data read in the performance interval.
Key: datastore|read_average
Datastore|Write Throughput (KBps) Amount of data written to disk in the performance interval.
Key: datastore|write_average
Datastore|Read Latency Average amount of time taken for a read operation from the datastore.
Key: datastore|ReadLatency
Datastore|Write Latency Average amount of time taken for a write operation from the datastore.
Key: datastore|WriteLatency
Datastore|Max VM Disk Latency Maximum amount of time taken to read or write data from a virtual
machine.
Key: datastore|MaxVMDiskLatency
Datastore|Outstanding IO Requests (OIOs) This metric displays the outstanding datastore IO requests.
Key: datastore|OutstandingIORequests
Datastore|Host SCSI Disk Partition This metric displays the datastore host scsi partition.
Key: datastore|HostSCSIDiskPartition
Devices|Command Aborted The metric lists the stopped device commands.
Key: devices|CommandAborted
Cluster Services Metrics for Cluster Compute Resources
Cluster Services metrics provide information about cluster services.
Metric Name Description
Cluster Services|Total Imbalance Total imbalance in cluster services
Key: clusterServices|total_imbalance
ClusterServices|Effective CPU Resources (MHz) VMware DRS effective CPU resources available.
VMware by Broadcom  4311

---
## page 4312

 VMware Cloud Foundation 9.0
Metric Name Description
Key: clusterServices|effectivecpu_average
ClusterServices|Effective Memory Resources (KB) VMware DRS effective memory resources available.
Key: clusterServices|effectivemem_average
Cluster Services|DRS Initiated vMotion Count clusterServices|number_drs_vmotion
Power Metrics for Cluster Compute Resources
Power metrics provide information about power use.
Metric Name Description
Power|Total Energy Consumed in the collection period (Wh) Displays the total electricity consumed based on the time interval
selected. The default collection cycle is set to 5 mins. You can continue
using the default setting or edit it for each adapter instance. For
example, if the time interval is set to its default value, the value
represents the energy consumed per 5 mins.
Power|Current Power Consumption Rate (Watt) The power consumption rate per second, averaged over the reporting
period.
Key: power|power_average
Power|Power Cap (Watt) Average power capacity in watts.
Key: power|powerCap_average
Power|(DEP) Energy (Joule) Total energy consumed in joules
Key: power|energy_summation
Summary Metrics for Cluster Compute Resources
Summary metrics provide information about overall performance.
Metric Name Description
Summary|Number of Running Hosts Number of running hosts.
Key: summary|number_running_hosts
Summary|Number of Running VMs This metric shows the total number of VMs running on all hosts in the
cluster.
Key: summary|number_running_vms
Summary|Number of vMotions This metric shows the number of vMotions that occurred during the last
collection cycle.
When using this metric, look for a low number which indicates that the
cluster might serve its VMs. A vMotion can impact VM performance
during the stun time.
Key: summary|number_vmotion
Summary|Number of Hosts Total number of hosts.
Key: summary|total_number_hosts
Summary|Total Number of VMs Total number of virtual machines.
Note:  This shows the total number of VMs excluding VM templates
under the datastore.
Key: summary|total_number_vms
Summary|Total Number of Datastores Total number of datastores.
VMware by Broadcom  4312

---
## page 4313

 VMware Cloud Foundation 9.0
Metric Name Description
Key: summary|total_number_datastores
Summary|Number of VCPUs on Powered On VMs Number of virtual CPUs on powered-on virtual machines.
Key: summary|number_running_vcpus
Summary|Average Running VM Count per Running Host Average number of running virtual machines per running host.
Key: summary|avg_vm_density
Summary|Cluster Availability (%) Percentage of hosts powered-on in the cluster.
Key: summary|cluster_availability
Summary|Datastore Displays the status of the datastore.
Key: summary|datastore
Summary|Type Displays the datastore type.
Key: summary|type
Summary|Is Local Displays whether the datastore is local or not.
Key: summary|Islocal
Summary|Number of VM Templates Number of VM templates.
Key: summary|number_vm_templates
Summary|Number of Pods Number of pods.
Note:  This is published if the cluster is Workload Management
enabled or there are pods under the cluster.
Key: summary|total_number_pods
Summary|Number of Namespaces Number of namespaces.
Note:  This is published if the cluster is Workload Management
enabled or there are namespaces under the cluster.
Key: summary|numberNamespaces
Summary|Number Kubernetes Clusters Number of Kuberntes clusters.
Note:  This is published if the cluster is Workload Management
enabled or there are Kuberntes clusters under the cluster.
Key: summary|numberKubernetesClusters
Summary|Number of Developer Managed VMs Number of developer managed VMs.
Note:  This is published if the cluster is Workload Management
enabled or there are developer managed VMs under the cluster.
Key: summary|numberDeveloperManagedVMs
Namespaces|Config Status Workload Management configuration status.
Note:  This is published if the cluster is Workload Management
enabled.
Key: namespaces|configStatus
Namespaces|Kubernetes Status Kubernetes status.
Note:  This is published if the cluster is Workload Management
enabled.
Key: namespaces|kuberntesStatus
Reclaimable Metrics for Cluster Compute Resources
Reclaimable metrics provide information about reclaimable resources.
Metric Name Description
Idle VMs|CPU (vCPUs) Number of reclaimable vCPUs of Idle VMs within the cluster.
VMware by Broadcom  4313

---
## page 4314

 VMware Cloud Foundation 9.0
Metric Name Description
Key: reclaimable|idle_vms|cpu
Idle VMs|Disk Space (GB) Reclaimable disk space of Idle VMs within the cluster.
Key: reclaimable|idle_vms|disksapce
Idle VMs|Memory (KB) Reclaimable memory of Idle VMs within the cluster.
Key: reclaimable|idle_vms|mem
Idle VMs|Potential Savings Potential saving after reclamation of resources of Idle VMs within
the cluster.
Key: reclaimable|idle_vms|cost
Powered Off VMs|Disk Space (GB) Reclaimable disk space of Powered Off VMs within the cluster.
Key: reclaimable|poweredOff_vms| diskspace
Powered Off VMs|Potential Savings Potential saving after reclamation of resources of Powered Off
VMs within the cluster.
Key: reclaimable|poweredOff_vms|cost
VM Snapshots|Disk Space (GB) Reclaimable disk space of VM Snapshots within the cluster.
Key: reclaimable| vm_snapshots | diskspace
VM Snapshots |Potential Savings Potential saving after reclamation of VM Snapshots within the
cluster.
Key: reclaimable| vm_snapshots |cost
Cost Metrics for Cluster Compute Resources
Cost metrics provide information about the cost.
Metric Name Description
Cluster CPU Base Rate Base rate for Cluster CPU calculated by dividing the monthly total
cluster CPU cost by cluster CPU utilization % and CPU cluster
capacity (gHZ).
Key:cost|cpuBaseRate
Cluster CPU Utilization (%) Expected CPU utilization that is set by the user in cluster cost
page.
Key:cost|cpuExpectedUtilizationPct
Cluster Memory Base Rate Cluster memory base rate calculated by dividing the monthly total
cluster memory cost by cluster memory utilization % and memory
cluster capacity (GB).
Key: cost|memoryBaseRate
Cluster Memory Utilization (%) Expected memory utilization that is set by the user in cluster cost
page.
Key: cost|memoryExpectedUtilizationPct
Monthly Cluster Allocated Cost Monthly cluster allocated cost calculated by subtracting the
monthly cluster unallocated cost from the monthly cluster total
cost.
Key: cost|allocatedCost
Monthly Cluster Total Cost Fully loaded compute cost of all hosts underneath the cluster.
Key: cost|totalCost
Monthly Cluster Unallocated Cost Monthly cluster unallocated cost calculated by subtracting the
monthly cluster allocated cost from the monthly cluster total cost.
VMware by Broadcom  4314

---
## page 4315

 VMware Cloud Foundation 9.0
Metric Name Description
Key: cost|unAllocatedCost
Monthly Total Cluster CPU Cost Cost attributed to the cluster CPU from monthly cluster total cost.
Key: cost|totalCpuCost
Monthly Total Cluster Memory Cost Cost attributed to the cluster memory from monthly cluster total
cost.
Key: cost|totalMemoryCost
MTD Cluster CPU Utilization (GHz) Month to date CPU utilization of the cluster.
Key: cost|cpuActualUtilizationGHz
MTD Cluster Memory Utilization (GB) Month to date memory utilization of the cluster.
Key: cost|memoryActualUtilizationGB
Monthly Cluster Allocated Cost (Currency) The monthly allocated cost of all VMs in a cluster.
cost|clusterAllocatedCost
Cost|Allocation|Monthly Cluster Unallocated Cost (Currency) The monthly unallocated is calculated by subtracting the monthly
allocated cost from the cluster's cost.
cost|clusterUnAllocatedCost
Aggregated Daily Total Cost Daily aggregate daily total cost of the deleted VM present in the
host system.
Key: Cost|aggregatedDailyTotalCost
Aggregated Deleted VM Daily Total Cost Daily aggregate cost of the deleted VM present in the host system.
Key: Cost|aggregatedDeletedVmDailyTotalCost
Profiles Metrics for Cluster Compute Resources
Profiles metrics provide information about the profile specific capacity.
Metric Name Description
Profiles|Capacity Remaining Profile (Average) The capacity remaining in terms of fitting the average consumer.
Key: Profiles|capacityRemainingProfile_<profile uuid>
Profiles|Capacity Remaining Profile (<custom profile name>) Published for custom profiles enabled from policy on Cluster
Compute Resource.
Key: Profiles|capacityRemainingProfile_<profile uuid>
Capacity Allocation Metrics for Cluster Compute Resources
Capacity allocation metrics provide information about the allotment of capacity, see Capacity Analytics Generated Metrics.
Virtual Machine Operations Metrics for Clusters
VM operations metrics provide information about the actions performed on VMs. The following are some important points
you must know about VM operation metrics for clusters.
• VM operations metrics is not collected for custom data centers.
• If you edit a VM settings and do not perform any action, still it is considered as VM reconfigure operation.
• During Revert Snapshot, VMs are powered-off, but this operation is not counted under VM Power-off metric.
• Adding ESXi with VMs is not counted under VM Create metric.
• Removing ESXi with VMs is not coutned under VM Remove metric.
• VM hardstop operation is not counted under VM Power Off metric.
VMware by Broadcom  4315

---
## page 4316

 VMware Cloud Foundation 9.0
Metric Name Description
Inventory
VM Clone This metric displays the number of clone operations on the virtual
machine.
Key: Inventory|VM Clone
VM Create This metric displays the number of create operations on the virtual
machine.
Key: Inventory|VM Create
VM Delete This metric displays the number of delete operations on the virtual
machine.
Key: Inventory|VM Delete
VM Reconfigure This metric displays the number of reconfigure operations on the
virtual machine.
Key: Inventory|VM Reconfigure
VM Register This metric displays the number of register operations on the
virtual machine.
Key: Inventory|VM Register
VM Template Deploy This metric displays the number templates deployed on the virtual
machine.
Key: Inventory|VM Template Deploy
VM Unregister This metric displays the number of unregister operations on the
virtual machine.
Key: Inventory|VM Unregister
Location
Storage vMotion This metric displays the number of migrations with vMotion
(datastore change operations for Powered-on VMs).
Key: Location|Storage vMotion
VM Datastore Change (powered-off VMs) This metric displays the number of datastore change operations,
for powered-off and suspended virtual machines.
Key: Location|VM Datastore Change (powered-off VMs)
VM Host and Datastore Change (powered-off VMs) This metric displays the number of host and datastore change
operations, for powered-off and suspended virtual machines.
Key: Location|VM Host and Datastore Change (powered-off VMs)
VM Host and Datastore Change (powered-on VMs) This metric displays the number of host and datastore change
operations, for powered-on and suspended virtual machines.
Key: Location|VM Host and Datastore Change (powered-on VMs)
VM Host Change (powered-off VMs) This metric displays the number of host change operations, for
powered-off and suspended virtual machines.
Key: Location|VM Host Change (powered-off VMs)
vMotion This metric displays the number of migrations with vMotion (host
change operations for powered-on VMs).
Key: Location|vMotion
State
VM Guest Reboot This metric displays the number of reboot operations on the virtual
machine guest.
Key: State|VM Guest Reboot
VMware by Broadcom  4316

---
## page 4317

 VMware Cloud Foundation 9.0
Metric Name Description
VM Guest Shutdown This metric displays the number of shutdown operations on the
virtual machine guest.
Key: State|VM Guest Shutdown
VM Power Off This metric displays the number of power-off operations on the
virtual machine.
Key: State|VM Power Off
VM Power On This metric displays the number of power-on operations on the
virtual machine.
Key: State|VM Power On
VM Reset This metric displays the number of reset operations on the virtual
machine guest.
Key: State|VM Reset
VM Standby Guest This metric displays the number of standby operations on the
virtual machine guest.
Key: State|VM Standby Guest
VM Suspend This metric displays the number of suspend operations on the
virtual machine.
Key: State|VM Suspend
Disabled Metrics
The following metrics are disabled in this version of VCF Operations. This means that they do not collect data by default.
You can enable these metrics in the Policy workspace. For more information, in VMware Docs search for Collect Metrics
and Properties Details.
You can enable these metrics in the Policy workspace. For more information, see Metrics and Properties Details.
Metric Name Key
CPU|Capacity Available to VMs (mhz) cpu|totalCapacity_average
CPU|IO Wait (msec) cpu|iowait
CPU|Reserved Capacity (mhz) cpu|reservedCapacity_average
CPU|Total Wait (msec) cpu|wait
Datastore I/O|Max Observed Number of Outstanding IO
Operations
datastore|maxObserved_OIO
Datastore I/O|Max Observed Read Rate (kbps) datastore|maxObserved_Read
Datastore I/O|Max Observed Reads per second datastore|maxObserved_NumberRead
Datastore I/O|Max Observed Write Rate (kbps) datastore|maxObserved_Write
Datastore I/O|Max Observed Writes per second datastore|maxObserved_NumberWrite
Storage|Total Usage (kbps) storage|usage_average
Summary|Average Provisioned Capacity per Running VM
(mhz)
summary|avg_vm_cpu
Summary|Average Provisioned Memory per Running VM (kb) summary|avg_vm_mem
Summary|Average Provisioned Memory per Running VM (kb) summary|avg_vm_mem
VMware by Broadcom  4317

---
## page 4318

 VMware Cloud Foundation 9.0
Metric Name Key
Summary|Maximum Number of VMs summary|max_number_vms
Summary|Workload Indicator summary|workload_indicator
Network I/O|Max Observed Received Throughput (KBps) net|maxObserved_Rx_KBps
Network I/O|Max Observed Throughput (KBps) net|maxObserved_KBps
Network I/O|Max Observed Transmitted Throughput (KBps) net|maxObserved_Tx_KBps
Diskspace|Not Shared (GB) Space used by VMs that is not shared.
Key: diskspace|notshared
Resource Pool Metrics
VCF Operations collects configuration, CPU usage, memory, and summary metrics for resource pool objects.
Resource Pool metrics include capacity and badge metrics. See definitions in:
• Capacity Analytics Generated Metrics
• Badge Metrics
Configuration Metrics for Resource Pools
Configuration metrics provide information about memory and CPU allocation configuration.
Metric Name Description
Memory Allocation Reservation Memory Allocation Reservation.
Key: config|mem_alloc_reservation
CPU Usage Metrics for Resource Pools
CPU usage metrics provide information about CPU use.
Metric Name Description
Capacity Demand Entitlement (%) CPU Capacity Demand Entitlement Percentage.
Key: cpu|capacity_demandEntitlementPct
Capacity entitlement (MHz) CPU Capacity Entitlement.
Key: cpu|capacity_entitlement
CPU Contention (%) CPU capacity contention.
Key: cpu|capacity_contentionPct
Demand (MHz) CPU demand in megahertz.
Key: cpu|demandmhz
Overall CPU Contention Overall CPU contention in milliseconds.
Key: cpu|capacity_contention
Usage Average CPU use in megahertz.
Key: cpu|usagemhz_average
Effective limit CPU effective limit.
Key: cpu|effective_limit
Reservation Used CPU reservation used.
VMware by Broadcom  4318

---
## page 4319

 VMware Cloud Foundation 9.0
Metric Name Description
Key: cpu|reservation_used
Estimated entitlement CPU estimated entitlement.
Key: cpu|estimated_entitlement
Dynamic entitlement CPU dynamic entitlement.
Key: cpu|dynamic_entitlement
Demand without overhead Value of demand excluding any overhead.
Key: cpu|demand_without_overhead
Memory Metrics for Resource Pools
Memory metrics provide information about memory use and allocation.
Metric Name Description
Balloon Amount of memory currently used by the virtual machine memory
control.
Key: mem|vmmemctl_average
Compression Rate Compression rate in kilobytes per second.
Key: mem|compressionRate_average
Consumed Amount of host memory consumed by the virtual machine for guest
memory.
Key: mem|consumed_average
Contention Machine contention.
Key: mem|host_contentionPct
Guest usage Guest memory entitlement.
Key: mem|guest_usage
Guest demand Guest memory entitlement.
Key: mem|guest_demand
Contention (KB) Machine contention in kilobytes.
Key: mem|host_contention
Decompression Rate Decompression rate in kilobytes per second.
Key: mem|decompressionRate_average
Granted Average of memory available for use.
Key: mem|granted_average
Guest Active Amount of memory that is actively used.
Key: mem|active_average
VM Overhead Memory overhead reported by host.
Key: mem|overhead_average
Shared Amount of shared memory.
Key: mem|shared_average
Reservation Used Memory Reservation Used.
Key: mem|reservation_used
Dynamic Entitlement Memory Dynamic Entitlement.
Key: mem|dynamic_entitlement
Effective Limit Memory Effective Limit.
VMware by Broadcom  4319

---
## page 4320

 VMware Cloud Foundation 9.0
Metric Name Description
Key: mem|effective_limit
Swap In Rate Rate at which memory is swapped from disk into active memory
during the interval.
Key: mem|swapinRate_average
Swap Out Rate Rate at which memory is being swapped from active memory to
disk during the current interval.
Key: mem|swapoutRate_average
Swapped Amount of unreserved memory.
Key: mem|swapped_average
Usage (%) Memory currently in use as a percentage of total available memory.
Key: mem|usage_average
Zero Amount of memory that is all zero.
Key: mem|zero_average
Zipped (KB) Latest zipped memory in kilobytes.
Key: mem|zipped_latest
Swap In (KB) Amount of memory swapped in kilobytes.
Key: mem|swapin_average
Swap Out (KB) Amount of memory swapped out in kilobytes.
Key: mem|swapout_average
Swap Used Amount of memory used for swap space in kilobytes.
Key: mem|swapused_average
Total Capacity Total capacity.
Key: mem|guest_provisioned
Summary Metrics for Resource Pools
Summary metrics provide information about overall performance.
Metric Name Description
Number of Running VMs Number of running virtual machines.
Key: summary|number_running_vms
Total Number of VMs Total number of virtual machines.
Note:  This shows the total number of VMs excluding VM
templates.
Key: summary|total_number_vms
IO Wait (ms) IO wait time in milliseconds.
Key: summary|iowait
Number of VM Templates Number of VM Templates.
Key: summary|number_vm_templates
Data Center Metrics
VCF Operations collects CPU usage, disk, memory, network, storage, disk space, and summary metrics for data center
objects.
Data center metrics include capacity and badge metrics. See definitions in:
VMware by Broadcom  4320

---
## page 4321

 VMware Cloud Foundation 9.0
• Capacity Analytics Generated Metrics
• Badge Metrics
Data Center Metrics for ROI Dashboard
Data center metrics provide information about data center savings across vCenters.
Metric Name Description
Realized Cost Savings
Realized Savings Idle Cost This metric displays the total realize savings for VMs across all
vCenters.
Key: cost|realized_savings|realizedIdleCost
Realized Savings Powered Off Cost (AOA) This metric displays the total realized savings for powered off VMs
across all vCenters.
Key: cost|realized_savings|realizedPoweredOffCost
Realized Savings Snapshot Space Cost (AOA) This metric displays the snapshots space saved across all vCenters.
Key: cost|realized_savings|realizedSnapshotSpaceCost
Realized Savings Oversized Cost (AOA) This metric displays the oversized savings across all vCenters.
Key: cost|realized_savings|realizedOversizedCost
Realized Savings Orphaned Disk Space Cost (AOA) This metric displays the amount of disk space saved by orphaned
disks across all vCenters.
Key: cost|realized_savings|realizedOrphanedDiskSpaceCost
Realized Savings Reclaimable Host Cost (AOA) This metric displays the amount of reclaimable host savings across all
vCenters.
Key: cost|realized_savings|realizedReclaimableHostCost
Realized vCPUs from Oversized VMs This metric displays the number of vCPUs realized across all
vCenters.
Key: realized|realizedVCpus
Compute Realized Memory from Oversized VMs This metric displays the amount of memory realized from oversized
VMs across all vCenters.
Key: compute_realized|realizedOversizedMem
Realized Potential Memory Consumed from Oversized VMs This metric displays the potential memory consumed from oversized
VMs across all vCenters.
Key: realized|realizedPotentialMemConsumed
Compute Realized vCPUs from Oversized VMs This metric displays the realized vCPUs from oversized VMs across
all vCenters.
Key: compute_realized|realizedOversizedVCpus
Compute Realized vCPUs from Idle VMs This metric displays the realized vCPUs from idle VMs across all
vCenters.
Key: compute_realized|realizedIdleVCpus
Compute Realized Memory from Idle VMs This metric displays the amount of memory realized from idle VMs
across all vCenters.
Key: compute_realized|realizedIdleMem
Disk Space Realized Idle VMs This metric displays the amount of disk space realized from idle VMs
across all vCenters.
Key: storage_realized|realizedIdleDiskSpace
VMware by Broadcom  4321

---
## page 4322

 VMware Cloud Foundation 9.0
Metric Name Description
Disk Space Realized PoweredOff VMs This metric displays the amount of disk space realized from powered
off VMs across all vCenters.
Key: storage_realized|realizedPoweredOffDiskSpace
Disk Space Realized VM Snapshots This metric displays the amount of disk space realized from VM
snapshots across all vCenters.
Key: storage_realized|realizedSnapshotSpace
Disk Space Realized Orphaned Disks This metric displays the amount of disk space realized from orphaned
disks across all vCenters.
Key: storage_realized|realizedIdleDiskSpace
Realized Savings Total Realized Cost This metric displays the total realized cost across all vCenters.
Key: cost|realized_savings|realizedTotalCost
CPU Usage Metrics for Data Centers
CPU usage metrics provide information about CPU use.
Metric Name Description
Capacity Usage (%) Percent capacity used.
Key: cpu|capacity_usagepct_average
CPU Contention (%) CPU capacity contention.
Key: cpu|capacity_contentionPct
Demand (%) CPU demand percentage.
Key: cpu|demandPct
Demand Demand in megahertz.
Key: cpu|demandmhz
Demand (MHz) CPU utilization level based on descendant virtual machines utilization.
This Includes reservations, limits, and overhead to run the virtual
machines.
Key: cpu|demandmhz
Overhead (KB) Amount of CPU overhead.
Key: cpu|overhead_average
Demand without overhead Value of demand excluding any overhead.
Key: cpu|demand_without_overhead
Total Wait CPU time spent on idle state.
Key: cpu|wait
Number of CPU Sockets Number of CPU sockets.
Key: cpu|numpackages
Overall CPU Contention (ms) Overall CPU contention in milliseconds.
Key: cpu|capacity_contention
Host Provisioned Capacity (MHz) Host provisioned capacity in megahertz.
Key: cpu|capacity_provisioned
Provisioned vCPU(s) Provisioned vCPU(s).
Key: cpu|corecount_provisioned
Reserved Capacity (MHz) The sum of the reservation properties of the (immediate) children of
the host's root resource pool.
VMware by Broadcom  4322

---
## page 4323

 VMware Cloud Foundation 9.0
Metric Name Description
Key: cpu|reservedCapacity_average
Usage Average CPU usage in megahertz.
Key: cpu|usagemhz_average
IO Wait IO wait time in milliseconds.
Key: cpu|iowait
Provisioned Capacity Provisioned Capacity.
Key: cpu|vm_capacity_provisioned
Stress Balance Factor Stress Balance Factor.
Key: cpu|stress_balance_factor
Lowest Provider Capacity Remaining Lowest Provider Capacity Remaining.
Key: cpu|min_host_capacity_remaining
Workload Balance Factor Workload Balance Factor.
Key: cpu|workload_balance_factor
Highest Provider Workload Highest Provider Workload.
Key: cpu|max_host_workload
Host workload Max-Min Disparity Difference of Max and Min host workload in the container.
Key: cpu|host_workload_disparity
Host stress Max-Min Disparity Difference of Max and Min host stress in the container.
Key: cpu|host_stress_disparity
Total Capacity (MHz) Total CPU resources configured on the descendant ESXi hosts.
Key: cpu|capacity_provisioned
Usable Capacity (MHz) The usable CPU resources that are available for the virtual machines
after considering reservations for vSphere High Availability (HA) and
other vSphere services.
Key: cpu|haTotalCapacity_average
Disk Metrics for Data Centers
Disk metrics provide information about disk use.
Metric Name Description
Total IOPS Average number of commands issued per second during the
collection interval.
Key: disk|commandsAveraged_average
Total Latency (ms) Average amount of time taken for a command from the perspective
of the guest operating system. This metric is the sum of the Kernel
Latency and Physical Device Latency metrics.
Key: disk|totalLatency_average
Total Throughput (KBps) Average of the sum of the data read and written for all the disk
instances of the host or virtual machine.
Key: disk|usage_average
Total queued outstanding operations Sum of queued operations and outstanding operations.
Key: disk|sum_queued_oio
Max observed OIO Max observed IO for a disk.
Key: disk|max_observed
VMware by Broadcom  4323

---
## page 4324

 VMware Cloud Foundation 9.0
Memory Metrics for Data Centers
Memory metrics provide information about memory use and allocation.
Metric Name Description
Contention (%) Machine Contention Percentage.
Key: mem|host_contentionPct
Machine Demand (KB) Memory machine demand in kilobytes.
Key: mem|host_demand
ESX System Usage Memory usage by the VM kernel and ESX user-level services.
Key: mem|host_systemUsage
Provisioned Memory (KB) Provisioned host memory in kilobytes.
Key: mem|host_provisioned
Reserved Capacity (KB) Reserved memory capacity in kilobytes.
Key: mem|reservedCapacity_average
Usable Memory (KB) Usable host memory in kilobytes.
Key: mem|host_usable
Host Usage Host memory use in kilobytes.
Key: mem|host_usage
Usage/Usable (%) Percent host memory used.
Key: mem|host_usagePct
VM Overhead Memory overhead reported by host.
Key: mem|overhead_average
Stress Balance Factor Stress Balance Factor.
Key: mem|stress_balance_factor
Lowest Provider Capacity Remaining Lowest Provider Capacity Remaining.
Key: mem|min_host_capacity_remaining
Workload Balance Factor Workload Balance Factor.
Key: mem|workload_balance_factor
Highest Provider Workload Highest Provider Workload.
Key: mem|max_host_workload
Host workload Max-Min Disparity Difference of Max and Min host workload in the container.
Key: mem|host_workload_disparity
Host stress Max-Min Disparity Difference of Max and Min host stress in the container.
Key: mem|host_stress_disparity
Utilization (KB) Memory utilization level based on the descendant virtual machines
utilization. Includes reservations, limits, and overhead to run the
Virtual Machines.
Key: mem|total_need
Total Capacity (KB) Total physical memory configured on descendant ESXi hosts.
Key: mem|host_provisioned
Usable Capacity (KB) The usable memory resources available for the virtual machines
after considering reservations for vSphere HA and other vSphere
services.
Key: mem|haTotalCapacity_average
VMware by Broadcom  4324

---
## page 4325

 VMware Cloud Foundation 9.0
Network Metrics for Data Centers
Network metrics provide information about network performance.
Metric Name Description
Packets Dropped Percentage of packets dropped.
Key: net|droppedPct
Max Observed Throughput Max observed rate of network throughput.
Key: net|maxObservedKBps
Data Transmit Rate Average amount of data transmitted per second.
Key: net|transmitted_average
Data Receive Rate Average amount of data received per second.
Key: net|received_average
Total Throughput (KBps) The sum of the data transmitted and received for all the NIC
instances of the host or virtual machine.
Key: net|usage_average
Storage Metrics for Data Centers
Storage metrics provide information about storage use.
Metric Name Description
Total Usage Total throughput rate.
Key: storage|usage_average
Datastore Metrics for Data Centers
Datastore metrics provide information about Datastore use.
Metric Name Description
Outstanding IO requests OIO for datastore.
Key: datastore|demand_oio
Read IOPS Average number of read commands issued per second during the
collection interval.
Key: datastore|numberReadAveraged_average
Write IOPS Average number of write commands issued per second during
the collection interval.
Key: datastore|numberWriteAveraged_average
Read Throughput (KBps) Amount of data read in the performance interval.
Key: datastore|read_average
Write Throughput (KBps) Amount of data written to disk in the performance interval.
Key: datastore|write_average
Disk Space Metrics for Data Centers
Disk space metrics provide information about disk use.
VMware by Broadcom  4325

---
## page 4326

 VMware Cloud Foundation 9.0
Metric Name Description
Virtual machine used Used virtual machine disk space in gigabytes.
Key: diskspace|used
Total disk space used Total disk space used on all datastores visible to this object.
Key: diskspace|total_usage
Total disk space Total disk space on all datastores visible to this object.
Key: diskspace|total_capacity
Total provisioned disk space Total provisioned disk space on all datastores visible to this
object.
Key: diskspace|total_provisioned
Shared Used (GB) Shared disk space in gigabytes.
Key: diskspace|shared
Snapshot Space (GB) Snapshot disk space in gigabytes.
Key: diskspace|snapshot
Virtual Disk Used (GB) Used virtual disk space in gigabytes.
Key: diskspace|diskused
Number of Virtual Disks Number of Virtual Disks.
Key: diskspace|numvmdisk
Utilization (GB) Storage space used on the connected vSphere Datastores.
Key: diskspace|total_usage
Total Capacity (GB) Total storage space available on the connected vSphere
datastores.
Key: diskspace|total_capacity
Summary Metrics for Data Centers
Summary metrics provide information about overall performance.
Metric Name Description
Number of Running Hosts Number of hosts that are ON.
Key: summary|number_running_hosts
Number of Running VMs Number of running virtual machines.
Key: summary|number_running_vms
Maximum Number of VMs Maximum number of virtual machines.
Key: summary|max_number_vms
Number of Clusters Total number of clusters.
Key: summary|total_number_clusters
Number of Hosts Total number of hosts.
Key: summary|total_number_hosts
Number of VMs Total number of virtual machines.
Key: summary|total_number_vms
Total Number of Datastores Total number of datastores.
Key: summary|total_number_datastores
Number of VCPUs on Powered On VMs Total number of VCPUs of virtual machines that are powered on.
Key: summary|number_running_vcpus
VMware by Broadcom  4326

---
## page 4327

 VMware Cloud Foundation 9.0
Metric Name Description
Workload Indicator Workload indicator.
Key: summary|workload_indicator
Average Running VM Count per Running Host Average number of running virtual machines per running host.
Key: summary|avg_vm_density
WLP Displays the VM migration trend as part of workload optimization.
These metrics are deactivated by default. You must activate them
from policies.
• Fail Count: Number of failed VM move attempts in the last
daily cycle.
• Number of runs: The total number of times the WLP was run
during the last daily cycle.
• Success Count: The number of successful VM moves during
the last daily cycle.
Reclaimable Metrics for Data Centers
Reclaimable metrics provide information about reclaimable resources.
Metric Name Description
CPU (vCPUs) Number of reclaimable vCPUs within the data center.
Key: reclaimable|cpu
Disk Space Reclaimable disk space within the data center.
Key: reclaimable|diskspace
Potential Savings Potential saving after reclamation of resources of all reclaimable
VMs (Idle VMs, Powered Off VMs, VM snapshots) within the data
center.
Key: reclaimable|cost
Memory (KB) Reclaimable memory within the data center.
Key: reclaimable|mem
Virtual Machines Number of VMs having reclaimable resources (Memory, disk
space, vCPU) within the data center.
Key: reclaimable|vm_count
Idle VMs|Potential Savings Potential saving after reclamation of resources of Idle VMs within
the data center.
Key: reclaimable|idle_vms|cost
Powered Off VMs|Potential Savings Potential saving after reclamation of resources of Powered Off
VMs within the data center.
Key: reclaimable|poweredOff_vms|cost
VM Snapshots|Potential Savings Potential saving after reclamation of VM snapshots within the data
center.
Key: reclaimable|vm_snapshots |cost
Reclaimable|Orphaned Disks|Potential Savings (Currency) Displays the potential savings after reclaimation of disk space by
removing orphaned VMDks from all datastores under datacenter.
reclaimable|cost
Reclaimable|Number of Orphaned Disks Number of reclaimable orphaned disks is the sum of all orphaned
disks on it's datastore.
VMware by Broadcom  4327

---
## page 4328

 VMware Cloud Foundation 9.0
Metric Name Description
reclaimable|orphaned_disk_count
Reclaimable Host Cost This metric calculates the cumulated reclaimable host cost at
cluster level and displays the same metric at data center level.
Reclaimable|Reclaimable Host Cost (Currency)
Cost Metrics for Data Centers
Cost metrics provide information about the cost.
Note:  The Effective metrics based on the capacity model assigned at the cluster (Demand/Allocation) pick the
corresponding metric from underneath the clusters.
Metric Name Description
Monthly Cluster Aggregated Allocated Cost This metric displays the sum of the monthly allocated cost for both
cluster and unclustered hosts.
Key: Cost|Allocation|Monthly Cluster Aggregated Allocated Cost
Monthly Cluster Aggregated Unallocated Cost This metric displays the sum of both cluster and unclustered hosts
unallocated cost.
Key: Cost|Allocation|Monthly Cluster Aggregated Unallocated
Cost
Monthly Datastore Aggregated Allocated Cost This metric displays the monthly aggregated allocated cost at
datastore level.
Key: Cost|Allocation|Monthly Datastore Aggregated Allocated
Cost
Monthly Datastore Aggregated Unallocated Cost This metric displays the monthly aggregated unallocated cost at
datastore level.
Key: Cost|Allocation|Monthly Datastore Aggregated Unallocated
Cost
Monthly Cluster Effective Aggregated Allocated Cost This metric displays the Monthly Cluster Effective Aggregated
Allocated Cost cost.
Key: Cost|Monthly Cluster Effective Aggregated Allocated Cost
Monthly Cluster Effective Aggregated Unallocated Cost This metric displays the Monthly Cluster Effective Aggregated
Unallocated Cost.
Key: Cost|Monthly Cluster Effective Aggregated Unallocated Cost
Monthly Datastore Effective Aggregated Allocated Cost This metric displays the Monthly Datastore Effective Aggregated
Allocated Cost at datastore level.
Key: Cost|Allocation|Monthly Datastore Effective Aggregated
Allocated Cost
Monthly Datastore Effective Aggregated Unallocated Cost This metric displays the Monthly Datastore Effective Aggregated
Unallocated Cost at datastore level.
Key: Cost|Allocation|Monthly Datastore Effective Aggregated
Unallocated Cost
Note:  The eight allocation metrics mentioned above, helps you to calculate the cost when you enable the allocation model for costing.
The same set of metrics are available when you enable demand model also.
Monthly Cluster Aggregated Cost This metric displays the sum of monthly aggregated allocated and
unallocated cost for clusters.
Key: cost|clusterCost
VMware by Broadcom  4328

---
## page 4329

 VMware Cloud Foundation 9.0
Metric Name Description
Monthly Cluster Aggregated Unallocated Cost This metric displays the sum of the monthly unallocated cost for
both cluster and unclustered hosts.
Key: Cost|Monthly Cluster Aggregated Unallocated Cost
Monthly Datacenter Aggregated Total Cost Monthly aggregated total cost for the data center.
Key: Cost|Monthly Datacenter Aggregated Total Cost
Monthly Datastore Total Cost Monthly data store total cost.
Key: cost|totalCost
Monthly Datastore Aggregated Allocated Cost Monthly aggregated allocated cost for the datastore.
Key: cost|aggrDataStoreAllocatedCost
Monthly Datastore Aggregated Unallocated Cost Monthly aggregated unallocated cost for the datastore.
Key: cost|aggrDataStoreUnallocatedCost
Monthly VM Aggregated Direct Cost Month to date aggregated VM direct cost across all the VMs under
the data center.
Key: cost|vmDirectCost
Virtual Machine Operations Metrics for Data Centers
VM operations metrics provide information about the actions performed on the VMs in the datacenter. The following are
some important points you must know about VM operation metrics for data centers.
• VM operations metrics is not collected for custom data centers.
• If you edit a VM settings and do not perform any action, still it is considered as VM reconfigure operation.
• During Revert Snapshot, VMs are powered-off, but this operation is not counted under VM Power-off metric.
• Adding ESXi with VMs is not counted under VM Create metric.
• Removing ESXi with VMs is not coutned under VM Remove metric.
• VM hardstop operation is not counted under VM Power Off metric.
Metric Name Description
Inventory
VM Clone This metric displays the number of clone operations on the virtual
machine.
Key: Inventory|VM Clone
VM Create This metric displays the number of create operations on the virtual
machine.
Key: Inventory|VM Create
VM Delete This metric displays the number of delete operations on the virtual
machine.
Key: Inventory|VM Delete
VM Reconfigure This metric displays the number of reconfigure operations on the
virtual machine.
Key: Inventory|VM Reconfigure
VM Register This metric displays the number of register operations on the
virtual machine.
Key: Inventory|VM Register
VM Template Deploy This metric displays the number templates deployed on the virtual
machine.
VMware by Broadcom  4329

---
## page 4330

 VMware Cloud Foundation 9.0
Metric Name Description
Key: Inventory|VM Template Deploy
VM Unregister This metric displays the number of unregister operations on the
virtual machine.
Key: Inventory|VM Unregister
Location
Storage vMotion This metric displays the number of migrations with vMotion
(datastore change operations for Powered-on VMs).
Key: Location|Storage vMotion
VM Datastore Change (powered-off VMs) This metric displays the number of datastore change operations,
for powered-off and suspended virtual machines.
Key: Location|VM Datastore Change (powered-off VMs)
VM Host and Datastore Change (powered-off VMs) This metric displays the number of host and datastore change
operations, for powered-off and suspended virtual machines.
Key: Location|VM Host and Datastore Change (powered-off VMs)
VM Host and Datastore Change (powered-on VMs) This metric displays the number of host and datastore change
operations, for powered-on and suspended virtual machines.
Key: Location|VM Host and Datastore Change (powered-on VMs)
VM Host Change (powered-off VMs) This metric displays the number of host change operations, for
powered-off and suspended virtual machines.
Key: Location|VM Host Change (powered-off VMs)
vMotion This metric displays the number of migrations with vMotion (host
change operations for powered-on VMs).
Key: Location|vMotion
State
VM Guest Reboot This metric displays the number of reboot operations on the virtual
machine guest.
Key: State|VM Guest Reboot
VM Guest Shutdown This metric displays the number of shutdown operations on the
virtual machine guest.
Key: State|VM Guest Shutdown
VM Power Off This metric displays the number of power-off operations on the
virtual machine.
Key: State|VM Power Off
VM Power On This metric displays the number of power-on operations on the
virtual machine.
Key: State|VM Power On
VM Reset This metric displays the number of reset operations on the virtual
machine guest.
Key: State|VM Reset
VM Standby Guest This metric displays the number of standby operations on the
virtual machine guest.
Key: State|VM Standby Guest
VM Suspend This metric displays the number of suspend operations on the
virtual machine.
Key: State|VM Suspend
VMware by Broadcom  4330

---
## page 4331

 VMware Cloud Foundation 9.0
Disabled Metrics
The following metrics are disabled in this version of VCF Operations. This means that they do not collect data by default.
You can enable these metrics in the Policy workspace. For more information, in VMware Docs search for Collect Metrics
and Properties Details.
You can enable these metrics in the Policy workspace. For more information, see Metrics and Properties Details.
Metric Name Key
Datastore I/O|Max Observed Number of Outstanding IO
Operations (IOPS)
datastore|maxObserved_OIO
Datastore I/O|Max Observed Read Rate (KBps) datastore|maxObserved_Read
Datastore I/O|Max Observed Reads per second (IOPS) datastore|maxObserved_NumberRead
Datastore I/O|Max Observed Write Rate (KBps) datastore|maxObserved_Write
Datastore I/O|Max Observed Writes per second (IOPS)0 datastore|maxObserved_NumberWrite
Max Observed Transmitted Throughput Max observed transmitted rate of network throughput.
Key: net|maxObserved_Tx_KBps
Max Observed Received Throughput Max observed received rate of network throughput.
Key: net|maxObserved_Rx_KBps
Not Shared (GB) Unshared disk space in gigabytes.
Key: diskspace|notshared
Custom Data Center Metrics
VCF Operations collects CPU usage, memory, summary, network, and datastore metrics for custom data center objects.
Custom data center metrics include capacity and badge metrics. See definitions in:
• Capacity Analytics Generated Metrics
• Badge Metrics
CPU Usage Metrics for Custom Data Centers
CPU usage metrics provide information about CPU use.
Metric Name Description
Host Provisioned Capacity Host provisioned capacity (MHz).
Key: cpu|capacity_provisioned
Provisioned vCPU(s) Provisioned vCPU(s).
Key: cpu|corecount_provisioned
Demand without overhead Value of demand excluding any overhead.
Key: cpu|demand_without_overhead
Number of hosts stressed Number of hosts stressed.
Key: cpu|num_hosts_stressed
Stress Balance Factor Stress balance factor.
Key: cpu|stress_balance_factor
Lowest Provider Capacity Remaining Lowest provider capacity remaining.
Key: cpu|min_host_capacity_remaining
VMware by Broadcom  4331

---
## page 4332

 VMware Cloud Foundation 9.0
Metric Name Description
Workload Balance Factor Workload balance factor.
Key: cpu|workload_balance_factor
Highest Provider Workload Highest provider workload.
Key: cpu|max_host_workload
Host workload Max-Min Disparity Host workload max-min disparity.
Key: cpu|host_workload_disparity
Host stress Max-Min Disparity Difference of max and min host stress in the container.
Key: cpu|host_stress_disparity
Demand (MHz) CPU utilization level based on descendant virtual machines utilization.
This Includes reservations, limits, and overhead to run the virtual
machines.
Key: cpu|demandmhz
Total Capacity (MHz) Total CPU resources configured on the descendant ESXi hosts.
Key: cpu|capacity_provisioned
Usable Capacity (MHz) The usable CPU resources that are available for the virtual machines
after considering reservations for vSphere High Availability (HA) and
other vSphere services.
Key: cpu|haTotalCapacity_average
Memory Metrics for Custom Data Centers
Memory metrics provide information about memory use.
Metric Name Description
Usable Memory Usable memory.
Key: mem|host_usable
Machine Demand Memory machine demand in KB.
Key: mem|host_demand
Number of hosts stressed Number of hosts stressed.
Key: mem|num_hosts_stressed
Stress Balance Factor Stress balance factor.
Key: mem|stress_balance_factor
Lowest Provider Capacity Remaining Lowest provider capacity remaining.
Key: mem|min_host_capacity_remaining
Workload Balance Factor Workload balance factor.
Key: mem|workload_balance_factor
Highest Provider Workload Highest provider workload.
Key: mem|max_host_workload
Host workload Max-Min Disparity Host workload max-min disparity.
Key: mem|host_workload_disparity
Host stress max-min disparity Host stress max-min disparity.
Key: mem|host_stress_disparity
Utilization (KB) Memory utilization level based on the descendant virtual machines
utilization. Includes reservations, limits, and overhead to run the
Virtual Machines.
VMware by Broadcom  4332

---
## page 4333

 VMware Cloud Foundation 9.0
Metric Name Description
Key: mem|total_need
Total Capacity (KB) Total physical memory configured on descendant ESXi hosts.
Key: mem|host_provisioned
Usable Capacity (KB) The usable memory resources available for the virtual machines after
considering reservations for vSphere HA and other vSphere services.
Key: mem|haTotalCapacity_average
Summary Metrics for Custom Data Centers
Summary metrics provide information about overall performance.
Metric Name Description
Number of Running VMs Number of virtual machines that are ON.
Key: summary|number_running_vms
Maximum Number of VMs Maximum number of virtual machines.
Key: summary|max_number_vms
Status Status of the data center.
Key: summary|status
WLP Displays the VM migration trend as part of workload optimization.
These metrics are deactivated by default. You must activate them
from policies.
• Fail Count: Number of failed VM move attempts in the last daily
cycle.
• Number of runs: The total number of times the WLP was run
during the last daily cycle.
• Success Count: The number of successful VM moves during the
last daily cycle.
Network Metrics for Custom Data Centers
Network metrics provide information about network performance.
Metric Name Description
Usage Rate The sum of the data transmitted and received for all the NIC instances
of the host or virtual machine.
Key: net|usage_average
Data Transmit Rate Average amount of data transmitted per second.
Key: net|transmitted_average
Data REceive Rate Average amount of data received per second.
Key: net|received_average
Datastore Metrics for Custom Data Centers
Datastore metrics provide information about datastore use.
Metric Name Description
Outstanding IO requests OIO for datastore.
VMware by Broadcom  4333

---
## page 4334

 VMware Cloud Foundation 9.0
Metric Name Description
Key: datastore|demand_oio
Read IOPS Average number of read commands issued per second during the
collection interval.
Key: datastore|numberReadAveraged_average
Write IOPS Average number of write commands issued per second during the
collection interval.
Key: datastore|numberWriteAveraged_average
Read Throughput (KBps) Amount of data read in the performance interval.
Key: datastore|read_average
Write Throughput (KBps) Amount of data written to disk in the performance interval.
Key: datastore|write_average
Reclaimable Metrics for Custom Data Centers
Reclaimable metrics provide information about reclaimable resources.
Metric Name Description
CPU (vCPUs) Number of reclaimable vCPUs within the custom data center.
Key: reclaimable|cpu
Disk Space Reclaimable disk space within the custom data center.
Key: reclaimable|diskspace
Potential Savings Potential saving after reclamation of resources of all reclaimable
VMs (Idle VMs, Powered Off VMs, VM snapshots) within the
custom data center.
Key: reclaimable|cost
Memory (KB) Reclaimable memory within the custom data center.
Key: reclaimable|mem
Number of Orphaned Disks Number of reclaimable orphaned disks within the custom data
center.
reclaimable|orphaned_disk_count
Reclaimable|Orphaned Disks|Potential Savings Potential savings in cost after reclamation of orphaned disks
across the custom data center.
Key: reclaimable|orphaned_disk|cost
Note:  The orphaned disk reclamation feature might not work as
expected when VCF Operations monitors multiple vCenters which
use shared data stores.
Virtual Machines Number of VMs having reclaimable resources (Memory, disk
space, vCPU) within the custom data center.
Key: reclaimable|vm_count
Idle VMs|Potential Savings Potential saving after reclamation of resources of Idle VMs within
the custom data center.
Key: reclaimable|idle_vms|cost
Powered Off VMs|Potential Savings Potential saving after reclamation of resources of Powered Off
VMs within the custom data center.
Key: reclaimable|poweredOff_vms|cost
VMware by Broadcom  4334

---
## page 4335

 VMware Cloud Foundation 9.0
Metric Name Description
VM Snapshots|Potential Savings Potential saving after reclamation of VM snapshots within the
custom data center.
Key: reclaimable|vm_snapshots |cost
Reclaimable|Orphaned Disks|Potential Savings (Currency) Displays the potential savings after reclaimation of disk space
by removing orphaned VMDks from all datastores under custom
datacenters.
reclaimable|cost
Reclaimable|Number of Orphaned Disks Number of reclaimable orphaned disks is the sum of the numbers
of orphaned disks on it's datastore.
reclaimable|orphaned_disk_count
Disk Space Metrics for Custom Data Centers
Disk space metrics provide information about disk use.
Metric Name Description
Utilization (GB) Storage space used on the connected vSphere Datastores.
Key: diskspace|total_usage
Total Capacity (GB) Total storage space available on the connected vSphere
datastores.
Key: diskspace|total_capacity
Disabled Metrics
The following metrics are disabled in this version of VCF Operations. This means that they do not collect data by default.
You can enable these metrics in the Policy workspace. For more information, in VMware Docs search for Collect Metrics
and Properties Details.
You can enable these metrics in the Policy workspace. For more information, see Metrics and Properties Details.
Metric Name Key
Max Observed Throughput Max observed rate of network throughput.
Key: net|maxObserved_KBps
Max Observed Transmitted Throughput Max observed transmitted rate of network throughput.
Key: net|maxObserved_Tx_KBps
Max Observed Received Throughput Max observed received rate of network throughput.
Key: net|maxObserved_Rx_KBps
Max Observed Reads per second Max observed average number of read commands issued per
second during the collection interval.
Key: datastore|maxObserved_NumberRead
Max Observed Read Rate Max observed rate of reading data from the datastore.
Key: datastore|maxObserved_Read
Max Observed Writes per second Max observed average number of write commands issued per
second during the collection interval.
Key: datastore|maxObserved_NumberWrite
Max Observed Write Rate Max observed rate of writing data from the datastore.
VMware by Broadcom  4335

---
## page 4336

 VMware Cloud Foundation 9.0
Metric Name Key
Key: datastore|maxObserved_Write
Max Observed Number of Outstanding IO Operations Max observer number of outstanding IO operations.
Key: datastore|maxObserved_OIO
Storage Pod Metrics
VCF Operations collects datastore and disk space metrics for storage pod objects.
Storage Pod metrics include capacity and badge metrics. See definitions in:
• Capacity Analytics Generated Metrics
• Badge Metrics
Table 1259: Datastore Metrics for Storage Pods
Metric Name Description
Read IOPS Average number of read commands issued per second during the
collection interval.
Key: datastore|numberReadAveraged_average
Writes per second Average number of write commands issued per second during the
collection interval.
Key: datastore|numberWriteAveraged_average
Read Throughput (KBps) Amount of data read in the performance interval.
Key: datastore|read_average
Write Throughput (KBps) Amount of data written to disk in the performance interval.
Key: datastore|write_average
Total Throughput (KBps) Usage Average.
Key: datastore|usage_average
Read Latency Average amount of time for a read operation from the datastore. Total
latency = kernel latency + device latency.
Key: datastore|totalReadLatency_average
Write Latency Average amount of time for a write operation to the datastore. Total
latency = kernel latency + device latency.
Key: datastore|totalWriteLatency_average
Total Latency (ms) The average amount of time taken for a command from the perspective
of a Guest OS. This is the sum of Kernel Command Latency and Physical
Device Command Latency.
Key: datastore|totalLatency_average
Total IOPS Average number of commands issued per second during the collection
interval.
Key: datastore|commandsAveraged_average
Table 1260: Disk Space Metrics for Storage Pods
Metric Name Description
Freespace Unused space available on datastore.
Key: diskspace|freespace
VMware by Broadcom  4336

---
## page 4337

 VMware Cloud Foundation 9.0
Metric Name Description
Total used Total space used.
Key: diskspace|disktotal
Capacity Total capacity of datastore.
Key: diskspace|capacity
Virtual Machine used Space used by virtual machine files.
Key: diskspace|used
Snapshot Space Space used by snapshots.
Key: diskspace|snapshot
VMware Distributed Virtual Switch Metrics
VCF Operations collects network and summary metrics for VMware distributed virtual switch objects.
VMware Distributed Virtual Switch metrics include badge metrics. See definitions in Badge Metrics.
Table 1261: Network Metrics for VMware Distributed Virtual Switches
Metric Name Description
Total Ingress Traffic Total ingress traffic (KBps).
Key: network|port_statistics|rx_bytes
Total Egress Traffic Total egress traffic (KBps).
Key: network|port_statistics|tx_bytes
Egress Unicast Packets per second Egress unicast packets per second.
Key: network|port_statistics|ucast_tx_pkts
Egress Multicast Packets per second Egress multicast packets per second.
Key: network|port_statistics|mcast_tx_pkts
Egress Broadcast Packets per second Egress broadcast packets per second.
Key: network|port_statistics|bcast_tx_pkts
Ingress Unicast Packets per second Ingress unicast packets per second.
Key: network|port_statistics|ucast_rx_pkts
Ingress Multicast Packets per second Ingress multicast packets per second.
Key: network|port_statistics|mcast_rx_pkts
Ingress Broadcast Packets per second Ingress broadcast packets per second.
Key: network|port_statistics|bcast_rx_pkts
Egress Dropped Packets per second Egress dropped packets per second.
Key: network|port_statistics|dropped_tx_pkts
Ingress Dropped Packets per second Ingress dropped packets per second.
Key: network|port_statistics|dropped_rx_pkts
Total Ingress Packets per second Total ingress packets per second.
Key: network|port_statistics|rx_pkts
Total Egress Packets per second Total egress packets per second.
Key: network|port_statistics|tx_pkts
Utilization Use (KBps).
Key: network|port_statistics|utilization
Total Dropped Packets per second Total dropped packets per second.
Key: network|port_statistics|dropped_pkts
VMware by Broadcom  4337

---
## page 4338

 VMware Cloud Foundation 9.0
Metric Name Description
Percentage of Dropped Packets Percentage of dropped packets.
Key: network|port_statistics|dropped_pkts_pct
Max Observed Ingress Traffic (KBps) Max observed ingress traffic (KBps).
Key: network|port_statistics|maxObserved_rx_bytes
Max Observed Egress Traffic (KBps) Max observed egress traffic (KBps).
Key: network|port_statistics|maxObserved_tx_bytes
Max Observed Utilization (KBps) Max observed utilization (KBps).
Key: network|port_statistics|maxObserved_utilization
Table 1262: Summary Metrics for VMware Distributed Virtual Switches
Metric Name Description
Maximum Number of Ports Maximum number of ports.
Key: summary|max_num_ports
Used Number of Ports Used number of ports.
Key: summary|used_num_ports
Number of Blocked Ports Number of blocked ports.
Key: summary|num_blocked_ports
Table 1263: Host Metrics for VMware Distributed Virtual Switches
Metric Name Description
MTU Mismatch Maximum Transmission Unit (MTU) mismatch.
Key: host|mtu_mismatch
Teaming Mismatch Teaming mismatch.
Key: host|teaming_mismatch
Unsupported MTU Unsupported MTU.
Key: host|mtu_unsupported
Unsupported VLANs Unsupported VLANs.
Key: host|vlans_unsupported
Config Out Of Sync Config Out Of Sync.
Key: host|config_outofsync
Number of Attached pNICs Number of attached physical NICs.
Key: host|attached_pnics
Distributed Virtual Port Group Metrics
The vCenter Adapter instance collects network and summary metrics for distributed virtual port groups.
Distributed Virtual Port Group metrics include badge metrics. See definitions in Badge Metrics.
Table 1264: Network Metrics for Distributed Virtual Port Groups
Metric Name Description
Ingress Traffic Ingress traffic (KBps).
VMware by Broadcom  4338

---
## page 4339

 VMware Cloud Foundation 9.0
Metric Name Description
Key: network|port_statistics|rx_bytes
Egress Traffic Egress traffic (KBps).
Key: network|port_statistics|tx_bytes
Egress Unicast Packets per second Egress unicast packets per second.
Key: network|port_statistics|ucast_tx_pkts
Egress Multicast Packets per second Egress multicast packets per second.
Key: network|port_statistics|mcast_tx_pkts
Egress Broadcast Packets per second Egress broadcast packets per second.
Key: network|port_statistics|bcast_tx_pkts
Ingress Unicast Packets per second Ingress unicast packets per second.
Key: network|port_statistics|ucast_rx_pkts
Ingress Multicast Packets per second Ingress multicast packets per second.
Key: network|port_statistics|mcast_rx_pkts
Ingress Broadcast Packets per second Ingress broadcast packets per second.
Key: network|port_statistics|bcast_rx_pkts
Egress Dropped Packets per second Egress dropped packets per second.
Key: network|port_statistics|dropped_tx_pkts
Ingress Dropped Packets per second Ingress dropped packets per second.
Key: network|port_statistics|dropped_rx_pkts
Total Ingress Packets per second Total Ingress packets per second.
Key: network|port_statistics|rx_pkts
Total Egress Packets per second Total Egress packets per second.
Key: network|port_statistics|tx_pkts
Utilization Utilization (KBps).
Key: network|port_statistics|utilization
Total Dropped Packets per second Total dropped packets per second.
Key: network|port_statistics|dropped_pkts
Percentage of Dropped Packets Percentage of dropped packets.
Key: network|port_statistics|dropped_pkts_pct
Max Observed Ingress Traffic (KBps) Max observed ingress traffic (KBps).
Key: network|port_statistics|maxObserved_rx_bytes
Max Observed Egress Traffic (KBps) Max observed egress traffic (KBps).
Key: network|port_statistics|maxObserved_tx_bytes
Max Observed Utilization (KBps) Max observed utilization (KBps).
network|port_statistics|maxObserved_utilization
Table 1265: Summary Metrics for Distributed Virtual Port Groups
Metric Name Description
Maximum Number of Ports Maximum number of ports.
Key: summary|max_num_ports
Used Number of Ports Used number of ports.
Key: summary|used_num_ports
Number of Blocked Ports The number of blocked ports.
Key: summary|num_blocked_ports
VMware by Broadcom  4339

---
## page 4340

 VMware Cloud Foundation 9.0
Datastore Cluster Metrics
VCF Operations collects profile metrics for the datastore cluster resources.
Profiles Metrics for Datastore Cluster Resources
Profiles metrics provide information about the profile specific capacity.
Metric Name Description
Profiles|Capacity Remaining Profile (Average) The capacity remaining in terms of fitting the average consumer.
Key: Profiles|capacityRemainingProfile_<profile uuid>
Profiles|Capacity Remaining Profile (<custom profile name>) Published for custom profiles enabled from policy on Datastore
Cluster Resource.
Key: Profiles|capacityRemainingProfile_<profile uuid>
Capacity Allocation Metrics for Datastore Cluster Resources
Capacity allocation metrics provide information about the allotment of capacity, see Capacity Analytics Generated Metrics.
Datastore Metrics
VCF Operations collects capacity, device, and summary metrics for datastore objects.
Capacity metrics can be calculated for datastore objects. See Capacity Analytics Generated Metrics.
Capacity Metrics for Datastores
Capacity metrics provide information about datastore capacity.
Metric Name Description
Capacity|Available Space (GB) This metric shows the amount of free space that a datastore has
available.
Use this metric to know how much storage space is unused
on the datastore. Try to avoid having too little free disk space
in order to accommodate unexpected storage growth on the
datastore. The exact size of the datastore is based on company
policy.
Key: capacity|available_space
Capacity|Provisioned (GB) This metric shows the amount of storage that was allocated to
the virtual machines.
Use this metric to know how much storage space is being used
on the datastore.
Check the metric trend to identify spikes or abnormal growth.
Key: capacity|provisioned
Capacity|Total Capacity (GB) This metric shows the overall size of the datastore.
Use this metric to know the total capacity of the datastore.
Typically the size of the datastore should not be too small.
VMFS datastore size has grown over the years as virtualization
matures and larger virtual machines are now onboard. Ensure
that the size can handle enough virtual machines to avoid
datastore sprawl. A best practice is to use 5 TB for VMFS and
more for vSAN.
VMware by Broadcom  4340

---
## page 4341

 VMware Cloud Foundation 9.0
Metric Name Description
Key: capacity|total_capacity
Capacity|Used Space (GB) This metric shows the amount of storage that is being used on
the datastore.
Key: capacity|used_space
Capacity|Workload (%) Capacity workload.
Key: capacity|workload
Capacity|Uncommitted Space (GB) Uncommitted space in gigabytes.
Key: capacity|uncommitted
Capacity|Total Provisioned Consumer Space Total Provisioned Consumer Space.
Key: capacity|consumer_provisioned
Capacity|Used Space (%) This metric shows the amount of storage that is being used on
the datastore.
Use this metric to know the percentage of storage space being
used on the datastore.
When using this metric, verify that you have at least 20% of free
storage. Less than this, and you might experience problems
when a snapshot is not deleted. If you have more than 50%
free storage space, you are not utilizing your storage in the best
possible way.
Key: capacity|usedSpacePct
Device Metrics for Datastores
Device metrics provide information about device performance.
Metric Name Description
Devices|Bus Resets This metric shows the number of bus resets in the performance
interval.
Key: devices|busResets_summation
Devices|Commands Aborted This metric shows the number of disk commands canceled in the
performance interval.
Key: devices|commandsAborted_summation
Devices|Commands Issued This metric shows the number of disk commands issued in the
performance interval.
Key: devices|commands_summation
Devices|Read Latency (ms) This metric shows the average time taken for a read from the
perspective of a guest operating system. This metric is the sum
of the Kernel Disk Read Latency and Physical Device Read
Latency metrics.
Key: devices|totalReadLatency_averag
Devices|Kernel Disk Read Latency (ms) Average time spent in ESX host VM Kernel per read.
Key: devices|kernelReadLatency_average
Devices|Kernel Write Latency (ms) Average time spent in ESX Server VM Kernel per write.
Key: devices|kernelWriteLatency_average
Devices|Physical Device Read Latency (ms) Average time taken to complete a read from the physical device.
Key: devices|deviceReadLatency_average
VMware by Broadcom  4341

---
## page 4342

 VMware Cloud Foundation 9.0
Metric Name Description
Devices|Queue Write Latency (ms) Average time spent in the ESX Server VM Kernel queue per
write.
Key: devices|queueWriteLatency_average
Devices|Physical Device Write Latency (ms) Average time taken to complete a write from the physical disk.
Key: devices|deviceWriteLatency_average
Datastore Metrics for Datastores
Datastore metrics provide information about datastore use.
Metric Name Description
Datastore|Total Latency (ms) This metric shows the adjusted read and write latency at the
datastore level. Adjusted means that the latency is taking into
account the number of IOs. If your IO is read-dominated, the
combined value is influenced by the reads.
This is the average of all the VMs running in the datastore.
Because it is an average, some VMs logically experience higher
latency that the value shown by this metric. To see the worst
latency experienced by any VM, use the Maximum VM Disk
Latency metric.
Use this metric to see the performance of the datastore. It is
one of two key performance indicators for a datastore, the other
being the Max Read Latency. The combination of Maximum
and Average gives better insight into how well the datastore is
coping with the demand.
The number should be lower than the performance you expect.
Key: datastore|totalLatency_average
Datastore|Total Throughput (KBps) Average use in kilobytes per second.
Key: datastore|usage_average
Datastore|Read Latency (ms Average amount of time for a read operation from the datastore.
Total latency = kernel latency + device latency.
Key: datastore|totalReadLatency_average
Datastore|Write Latency (ms) Average amount of time for a write operation to the datastore.
Total latency = kernel latency + device latency.
Key: datastore|totalWriteLatency_average
Datastore|Demand Demand.
Key: datastore|demand
Datastore|Outstanding IO requests OIO for datastore.
Key: datastore|demand_oio
Datastore|Read IOPS This metric displays the average number of read commands
issued per second during the collection interval.
Use this metric when the total IOPS is higher than expected.
See if the metric is read or write dominated. This helps
determine the cause of the high IOPS. Certain workloads such
as backups, anti-virus scans, and Windows updates carry a
Read/Write pattern. For example, an anti-virus scan is heavy on
read since it is mostly reading the file system.
Key: datastore|numberReadAveraged_average
VMware by Broadcom  4342

---
## page 4343

 VMware Cloud Foundation 9.0
Metric Name Description
Datastore|Write IOPS This metric displays the average number of write commands
issued per second during the collection interval.
Use this metric when the total IOPS is higher than expected.
Drill down to see if the metric is read or write dominated. This
helps determine the cause of the high IOPS. Certain workloads
such as backups, anti-virus scans, and Windows updates carry
a Read/Write pattern. For example, an anti-virus scan is heavy
on read since it is mostly reading the file system.
Key: datastore|numberWriteAveraged_average
Datastore|Read Throughput (KBps) This metric displays the amount of data read in the performance
interval.
Key: datastore|read_average
Datastore|Write Throughput (KBps) This metric displays the amount of data written to disk in the
performance interval.
Key: datastore|write_average
About Datastore Metrics for Virtual SAN
The metric named datastore|oio|workload is not supported on Virtual SAN datastores. This metric depends on
datastore|demand_oio, which is supported for Virtual SAN datastores.
The metric named datastore|demand_oio also depends on several other metrics for Virtual SAN datastores, one of
which is not supported.
• The metrics named devices|numberReadAveraged_average and devices|numberWriteAveraged_average
are supported.
• The metric named devices|totalLatency_average is not supported.
As a result,  does not collect the metric named datastore|oio|workload for Virtual SAN datastores.
Disk Space Metrics for Datastores
Disk space metrics provide information about disk space use.
Metric Name Description
Diskspace|Number of Virtual Disk Number of virtual disks.
Key: diskspace|numvmdisk
Diskspace|Provisioned Space (GB) Provisioned space in gigabytes.
Key: diskspace|provisioned
Diskspace|Shared Used (GB) Shared used space in gigabytes.
Key: diskspace|shared
Diskspace|Snapshot Space (GB) This metric shows the amount of space taken by snapshots on a
given database.
Use this metric to know how much storage space is being used
by virtual machine snapshots on the datastore.
Check that the snapshot is using 0 GB or minimal space.
Anything over 1 GB should trigger a warning. The actual
value depends on how IO intensive the virtual machines in the
datastore are. Run a DT on them to detect anomaly. Clear the
snapshot within 24 hours, preferably when you have finished
backing up, or patching.
VMware by Broadcom  4343

---
## page 4344

 VMware Cloud Foundation 9.0
Metric Name Description
Key: diskspace|snapshot
Diskspace|Virtual Disk Used (GB) Virtual disk used space in gigabytes.
Key: diskspace|diskused
Diskspace|Virtual machine used (GB) Virtual machine used space in gigabytes.
Key: diskspace|used
Diskspace|Total disk space used Total disk space used on all datastores visible to this object.
Key: diskspace|total_usage
Diskspace|Total disk space Total disk space on all datastores visible to this object.
Key: diskspace|total_capacity
Diskspace|Total used (GB) Total used space in gigabytes.
Key: diskspace|disktotal
Diskspace|Swap File Space (GB) Swap file space in gigabytes.
Key: diskspace|swap
Diskspace|Other VM Space (GB) Other virtual machine space in gigabytes.
Key: diskspace|otherused
Diskspace|Freespace (GB) Unused space available on datastore.
Key: diskspace|freespace
Diskspace|Capacity (GB) Total capacity of datastore in gigabytes.
Key: diskspace|capacity
Diskspace|Overhead Amount of disk space that is overhead.
Key: diskspace|overhead
Summary Metrics for Datastores
Summary metrics provide information about overall performance.
Metric Name Description
Summary|Number of Hosts This metric shows the number of hosts that the datastore is
connected to.
Use this metric to know how many clusters the datastore is
attached to.
The number should not be too high, as a datastore should not
be mounted by every host. The datastore and cluster should be
paired to keep operations simple.
Key: summary|total_number_hosts
Summary|Total Number of VMs This metric shows the number of virtual machines which save
their VMDK files on the datastore. If a VM has four VMDKs stored
in four datastores, the VM is counted on each datastore.
Use this metric to know how many VMs have at least one VMDK
on a specific datastore.
The number of VMs should be within your Concentration Risk
policy.
You should also expect the datastore to be well used. If only a
few VMs are using the datastore, this is not considered a good
use.
Key: summary|total_number_vms
Summary|Maximum Number of VMs Maximum number of virtual machines.
VMware by Broadcom  4344

---
## page 4345

 VMware Cloud Foundation 9.0
Metric Name Description
Key: summary|max_number_vms
Summary|Workload Indicator Workload indicator.
Key: summary|workload_indicator
Summary|Number of Clusters This metric shows the number of clusters that the datastore is
connected to.
Key: summary|total_number_clusters
Summary|Number of VM Templates Number of VM Templates.
Key: Summary|Number of VM Templates
Template Metrics for Datastores
Metric Name Description
Template|Virtual Machine used Space used by virtual machine files.
Key: template|used
Template|Access Time Last access time.
Key: template|accessTime
Cost Metrics for Datastores
Cost metrics provides information about the cost.
Metric Name Description
Monthly Disk Space Base Rate Disk space base rate for datastore displays the cost of 1 GB
storage.
Key: cost|storageRate
Monthly Total Cost Monthly total cost, computed by multiplying datastore capacity
with monthly storage rate.
Key: cost|totalCost
Cost|Allocation|Disk Space Base Rate (Currency) Monthly storage rate for datastore displays the cost of 1 GB
storage when the overcommit ratio is set in policy.
cost|storageRate
Cost|Allocation|Monthly Datastore Allocated Cost(Currency/
Month)
Monthly allocated cost as compared to the total cost of the
datastore
Cost|Allocation|Monthly Datastore Unallocated Cost(Currency/
Month)
Monthly unallocated cost as compared to the total cost of the
datastore.
Reclaimable Metrics
Reclaimable metrics provide information about reclaimable resources.
Metric Name Description
Reclaimable|Orphaned Disks|Disk Space (GB) Summary of storage used by all orphaned VMDKs on the
datastore.
Key: reclaimable|orphaned_disk|diskspace
VMware by Broadcom  4345

---
## page 4346

 VMware Cloud Foundation 9.0
Metric Name Description
Reclaimable|Orphaned Disks|Potential Savings (Currency) Potential saving after reclamation of storage by removing
orphaned VMDks from the datastore.
Key: reclaimable|orphaned_disk|cost
Disabled Instanced Metrics
The instance metrics created for the following metrics are disabled in this version of VCF Operations. This means that
these metrics collect data by default but all the instanced metrics created for these metrics, do not collect data by default.
Metric Name
Devices|Kernel Latency (ms)
Devices|Number of Running Hosts
Devices|Number of Running VMs
Devices|Physical Device Latency (ms)
Devices|Queue Latency (ms)
Devices|Queue Read Latency (ms)
Devices|Read IOPS
Devices|Read Latency (ms)
Devices|Read Requests
Devices|Read Throughput (KBps)
Devices|Total IOPS
Devices|Total Latency (ms)
Devices|Total Throughput (KBps)
Devices|Write IOPS
Devices|Write Latency (ms)
Devices|Write Requests
Devices|Write Throughput (KBps)
Disabled Metrics
The following metrics are disabled in this version of VCF Operations. This means that they do not collect data by default.
You can enable these metrics in the Policy workspace. For more information, in VMware Docs search for Collect Metrics
and Properties Details.
You can enable these metrics in the Policy workspace. For more information, see Metrics and Properties Details.
Metric Name Key
Capacity|Data Store Capacity Contention (%) capacity|contention
Datastore I/O|Demand Indicator datastore|demand_indicator
Datastore I/O|Max Observed Number of Outstanding IO
Operations
datastore|maxObserved_OIO
Datastore I/O|Max Observed Read Latency (msec) datastore|maxObserved_Read
VMware by Broadcom  4346

---
## page 4347

 VMware Cloud Foundation 9.0
Metric Name Key
Datastore I/O|Max Observed Read Latency (msec) datastore|maxObserved_ReadLatency
Datastore I/O|Max Observed datastore|maxObserved_NumberRead
Datastore I/O|Max Observed Write Latency (msec) datastore|maxObserved_Write
Datastore I/O|Max Observed Write Latency (msec) datastore|maxObserved_WriteLatency
Datastore I/O|Max Observed Writes per second datastore|maxObserved_NumberWrite
Datastore|Demand Indicator Demand Indicator.
Key: datastore|demand_indicator
Diskspace|Not Shared (GB) Unshared space in gigabytes.
Key: diskspace|notshared
Cluster Compute Metrics for Allocation Model
VCF Operations collects configuration, disk space, CPU use, disk, memory, network, power, and summary metrics for
cluster compute resources.
Cost Metrics for Cluster Compute Resources
Cost metrics provide information about the cost.
Metric Name Description
Cluster CPU Base Rate Base rate for Cluster CPU calculated by dividing the monthly total
cluster CPU cost by cluster CPU over-commit ratio.
Key:Cost|Allocation|ClusterCPUBaseRate
Cluster Memory Base Rate Cluster memory base rate calculated by dividing the monthly total
cluster memory cost b cost by cluster memory over-commit ratio.
Key: Cost|Allocation|ClusterMemoryBaseRate
Monthly Cluster Allocated Cost Sum of of monthly cluster CPU, Memory, and Storage costs
Key: Cost|Allocation|MonthlyClusterAllocatedCost
Monthly Cluster Unallocated Cost Monthly cluster unallocated cost calculated by subtracting the
monthly cluster allocated cost from the monthly cluster total cost.
Key: Cost|Allocation| MonthlyClusterUnallocatedCost
Monthly Storage Rate Datastore base rate is calculated by dividing Storage base rate
based on utilization by over commit ratio.
Key:Cost|Allocation|Monthly Storage Rate
Virtual Machine Metrics for Allocation Model
VCF Operations collects configuration, disk space, CPU use, disk, memory, network, power, and summary metrics for
virtual machine resources.
Cost Metrics for Virtual Machines
Cost metrics provide information about the cost.
VMware by Broadcom  4347

---
## page 4348

 VMware Cloud Foundation 9.0
Metric Name Description
MTD VM CPU Cost Month to date virtual machine CPU cost.
Key: Cost|Allocation|MTD VM CPU Cost
MTD VM Memory Cost Month to date virtual machine memory cost.
Key: Cost|Allocation|MTD VM Memory Cost
MTD VM Storage Cost Month to date storage cost of the virtual machine.
Key: Cost|Allocation|MTD VM Storage Cost
MTD VM Total Cost Addition of CPU ,Memory ,Storage, and Direct cost.
Key: Cost|Allocation|MTD VM Total Cost
Metrics for Namespace
VCF Operations collects metrics for Namspace through the vCenter adapter and uses formulas to derive statistics from
those metrics. You can use metrics to troubleshoot problems in your environment.
Table 1266: Metrics for Namespace
Metric Key Localized Name Description
cpu|usagemhz_average CPU|Usage Average CPU usage in MHZ.
cpu|demandmhz CPU|Demand Demand(MHz).
cpu|capacity_contentionPct CPU|Contention Percent of time descendant virtual machines are
unable to run because they are contending for
access to the physical CPU(s).
cpu|effective_limit CPU|Effective limit CPU Effective limit.
cpu|reservation_used CPU|Reservation Used CPU Reservation Used.
cpu|estimated_entitlement CPU|Estimated entitlement CPU Estimated entitlement.
cpu|dynamic_entitlement CPU|Dynamic entitlement CPU Dynamic Entitlement.
cpu|capacity_contention CPU|Overall CPU Contention Overall CPU Contention (ms).
cpu|capacity_demandEntitlementPct CPU|Capacity Demand Entitlement CPU Capacity Demand Entitlement Percentage.
mem|usage_average Memory|Usage Memory currently in use as a percentage of total
available memory.
mem|guest_provisioned Memory|Total Capacity Total Capacity.
mem|active_average Memory|Guest Active Amount of memory that is actively used.
mem|granted_average Memory|Granted Amount of memory available for use.
mem|shared_average Memory|Shared Amount of shared memory.
mem|overhead_average Memory|VM Overhead Memory overhead reported by host.
mem|consumed_average Memory|Consumed Amount of host memory consumed by the virtual
machine for guest memory.
mem|host_contentionPct Memory|Contention Machine Contention Percentage.
mem|guest_usage Memory|Guest Usage Guest Memory Entitlement.
mem|guest_demand Memory|Guest Demand Guest Memory Entitlement.
mem|reservation_used Memory|Reservation Used Memory Reservation Used.
VMware by Broadcom  4348

---
## page 4349

 VMware Cloud Foundation 9.0
Metric Key Localized Name Description
mem|effective_limit Memory|Effective limit Memory Effective limit.
mem|swapinRate_average Memory|Swap In Rate Rate at which memory is swapped from disk into
active memory during the collection interval. This
can impact performance.
mem|swapoutRate_average Memory|Swap Out Rate Rate at which memory is being swapped from active
memory to disk during the current interval.
mem|vmmemctl_average Memory|Balloon Amount of memory currently used by the virtual
machine memory control.
mem|zero_average Memory|Zero Amount of memory that is all 0.
mem|swapped_average Memory|Swapped Amount of unreserved memory.
mem|zipped_latest Memory|Zipped N/A
mem|compressionRate_average Memory|Compression Rate N/A
mem|decompressionRate_average Memory|Decompression Rate N/A
mem|swapin_average Memory|Swap In Amount of memory swapped in.
mem|swapout_average Memory|Swap Out Amount of memory swapped out.
mem|swapused_average Memory|Swap Used Amount of memory used for swap space.
mem|host_contention Memory|Contention Machine Contention.
mem|dynamic_entitlement Memory|Dynamic Entitlement Memory Dynamic Entitlement.
diskspace|total_usage Disk Space|Utilization Storage space utilized on connected vSphere
Datastores.
summary|configStatus Summary|Config Status Workload Management Configuration Status.
summary|total_number_pods Summary|Number of Pods Number of Pods.
summary|numberKubernetesClusters Summary|Number of Kubernetes
clusters
Number of Kubernetes clusters.
summary|number_running_vms Summary|Number of Running VMs Number of Running VMs.
summary|total_number_vms Summary|Total Number of VMs Total Number of VMs.
summary|iowait Summary|IO Wait IO Wait.
Metrics for Tanzu Kubernetes cluster
VCF Operations collects metrics for Tanzu Kubernetes cluster through the vCenter adapter and uses formulas to derive
statistics from those metrics. You can use metrics to troubleshoot problems in your environment.
Table 1267: Metrics for Tanzu Kubernetes clusters
Metric Key Localized Name Description
cpu|usagemhz_average CPU|Usage Average CPU usage in MHZ
cpu|demandmhz CPU|Demand Demand(MHz)
cpu|capacity_contentionPct CPU|Contention Percent of time descendant virtual machines are
unable to run because they are contending for
access to the physical CPU(s).
VMware by Broadcom  4349

---
## page 4350

 VMware Cloud Foundation 9.0
Metric Key Localized Name Description
cpu|effective_limit CPU|Effective limit CPU Effective limit
cpu|reservation_used CPU|Reservation Used CPU Reservation Used
cpu|estimated_entitlement CPU|Estimated entitlement CPU Estimated entitlement
cpu|dynamic_entitlement CPU|Dynamic entitlement CPU Dynamic Entitlement
cpu|capacity_contention CPU|Overall CPU Contention Overall CPU Contention (ms)
cpu|capacity_demandEntitlementPct CPU|Capacity Demand Entitlement CPU Capacity Demand Entitlement Percentage
mem|usage_average Memory|Usage Memory currently in use as a percentage of total
available memory
mem|guest_provisioned Memory|Total Capacity Total Capacity
mem|active_average Memory|Guest Active Amount of memory that is actively used
mem|granted_average Memory|Granted Amount of memory available for use
mem|shared_average Memory|Shared Amount of shared memory
mem|overhead_average Memory|VM Overhead Memory overhead reported by host
mem|consumed_average Memory|Consumed Amount of host memory consumed by the virtual
machine for guest memory
mem|host_contentionPct Memory|Contention Machine Contention Percentage
mem|guest_usage Memory|Guest Usage Guest Memory Entitlement
mem|guest_demand Memory|Guest Demand Guest Memory Entitlement
mem|reservation_used Memory|Reservation Used Memory Reservation Used
mem|effective_limit Memory|Effective limit Memory Effective limit
mem|swapinRate_average Memory|Swap In Rate Rate at which memory is swapped from disk into
active memory during the collection interval. This
can impact performance.
mem|swapoutRate_average Memory|Swap Out Rate Rate at which memory is being swapped from active
memory to disk during the current interval
mem|vmmemctl_average Memory|Balloon Amount of memory currently used by the virtual
machine memory control
mem|zero_average Memory|Zero Amount of memory that is all 0
mem|swapped_average Memory|Swapped Amount of unreserved memory
mem|zipped_latest Memory|Zipped N/A
mem|compressionRate_average Memory|Compression Rate N/A
mem|decompressionRate_average Memory|Decompression Rate N/A
mem|swapin_average Memory|Swap In Amount of memory swapped in
mem|swapout_average Memory|Swap Out Amount of memory swapped out
mem|swapused_average Memory|Swap Used Amount of memory used for swap space
mem|host_contention Memory|Contention Machine Contention
mem|dynamic_entitlement Memory|Dynamic Entitlement Memory Dynamic Entitlement
summary|number_running_vms Summary|Number of Running VMs Number of Running VMs
summary|total_number_vms Summary|Total Number of VMs Total Number of VMs
VMware by Broadcom  4350

---
## page 4351

 VMware Cloud Foundation 9.0
Metric Key Localized Name Description
summary|iowait Summary|IO Wait IO Wait
Metrics for vSphere Pods
VCF Operations collects metrics for vSphere Pods through the vCenter adapter and uses formulas to derive statistics from
those metrics. You can use metrics to troubleshoot problems in your environment.
Table 1268: Metrics for vSphere Pods
Metric Key Metric Name Description
config|hardware|num_Cpu Configuration|Hardware|Number of
CPUs
Number of CPUs. It counts both the vSocket and
vCore. A VM with 2 vSockets x 4 vCores each has 8
vCPU.
config|hardware|disk_Space Configuration|Hardware|Disk Space Disk space metrics
config|hardware|thin_Enabled Configuration|Hardware|Thin
Provisioned Disk
Thin Provisioned Disk
config|cpuAllocation|slotSize Configuration|CPU Resource
Allocation|HA Slot Size
vSphere HA Slot Size for CPU
config|memoryAllocation|slotSize Configuration|Memory Resource
Allocation|HA Slot Size
vSphere HA Slot Size for Memory
cpu|usage_average CPU|Usage CPU Usage divided by VM CPU Configuration in
MHz
cpu|usagemhz_average CPU|Usage Amount of actively used virtual CPU. This is
the host's view of the CPU usage, not the guest
operating system view.
cpu|usagemhz_average_mtd CPU|Usage average MTD Month to date average CPU usage in MHZ
cpu|readyPct CPU|Ready Percentage of CPU the VM is ready to run, but
unable due to ESXi has no ready physical core to
run it. High Ready value impacts VM performance
cpu|capacity_contentionPct CPU|Contention Percentage of time VM is not getting the CPU
resource it demanded. Impacted by Ready, Co-
Stop, Hyper Threading and Power Management
cpu|corecount_provisioned CPU|Provisioned vCPU(s) Number of CPUs. It counts both the vSocket and
vCore. A VM with 2 vSockets x 4 vCores each has 8
vCPU.
cpu|vm_capacity_provisioned CPU|Total Capacity Configured Capacity in MHz, based on nominal
(static) frequency of the CPU
cpu|demandmhz CPU|Demand The amount of CPU resources virtual machine
would use if there were no CPU contention or CPU
limit.
cpu|demandPct CPU|Demand (%) The percentage of CPU resources virtual machine
would use if there were no CPU contention or CPU
limit.
VMware by Broadcom  4351

---
## page 4352

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
cpu|reservation_used CPU|Reservation Used CPU Reserved for the VM. It's guaranteed to be
available when the VM demands it.
cpu|effective_limit CPU|Effective limit Limit placed on the VM by vSphere. Avoid using
limit as it impacts VM performance
cpu|iowaitPct CPU|IO Wait Percentage of time VM CPU is waiting for IO.
Formula is Wait - Idle - Swap Wait. High value
indicates slow storage subsystem
cpu|swapwaitPct CPU|Swap wait Percentage of time CPU is waiting on data swap-in.
Mapped to vCenter CPU Swap wait
cpu|costopPct CPU|Co-stop (%) Percentage of time the VM is ready to run, but is
unable to due to co-scheduling constraints. VM with
less vCPU have lower co-stop value.
cpu|system_summation CPU|System CPU time spent on system processes
cpu|wait_summation CPU|Wait Total CPU time spent in wait state
cpu|ready_summation CPU|Ready CPU time spent on ready state
cpu|used_summation CPU|Used CPU time that is used
cpu|iowait CPU|IO Wait IO Wait
cpu|wait CPU|Total Wait CPU time spent on idle state
cpu|capacity_demandEntitlementPct CPU|Capacity Demand Entitlement CPU Capacity Demand Entitlement Percentage
cpu|host_demand_for_aggregation CPU|Host Demand For Aggregation Host demand for aggregation
cpu|dynamic_entitlement CPU|Dynamic entitlement CPU Dynamic entitlement
cpu|capacity_contention CPU|Overall CPU Contention Overall CPU Contention (ms)
cpu|estimated_entitlement CPU|Estimated entitlement CPU Estimated entitlement
cpu|idlePct CPU|Idle % CPU time that is idle
cpu|waitPct CPU|Wait % Total CPU time spent in wait state
cpu|systemSummationPct CPU|System % CPU time spent on system processes
cpu|demandOverLimit CPU|Demand Over Limit Amount of CPU Demand that is over the configured
CPU Limit
cpu|demandOverCapacity CPU|Demand Over Capacity Amount of CPU Demand that is over the configured
CPU Capacity
cpu|perCpuCoStopPct CPU|Normalized Co-stop Percentage of co-stop time, normalized across all
vCPUs
cpu|swapwait_summation CPU|Swap Wait Amount of time waiting on swap.
cpu|costop_summation CPU|Co-stop Time the VM is ready to run, but is unable to due to
co-scheduling constraints.
cpu|idle_summation CPU|Idle CPU time that is idle.
cpu|latency_average CPU|Latency Percentage of time the VM is unable to run because
it is contending for access to the physical CPUs.
cpu|maxlimited_summation CPU|Max Limited Time the VM is ready to run, but is not run due to
maxing out its CPU limit setting.
VMware by Broadcom  4352

---
## page 4353

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
cpu|overlap_summation CPU|Overlap Time the VM was interrupted to perform system
services on behalf of that VM or other VMs.
cpu|run_summation CPU|Run Time the VM is scheduled to run.
cpu|entitlement_latest CPU|Entitlement Latest Entitlement Latest.
cpu|demandEntitlementRatio_latest CPU|Demand-to-entitlement Ratio CPU resource entitlement to CPU demand ratio (in
percents)
cpu|readiness_average CPU|Readiness Percentage of time that the virtual machine was
ready, but could not get scheduled to run on the
physical CPU.
rescpu|actav1_latest CPU Utilization for Resources|CPU
Active (1 min. average)
The average active time for the CPU over the past
minute
rescpu|actav5_latestswapinRate_averag
e
CPU Utilization for Resources|CPU
Active (5 min. average)
The average active time for the CPU over the past
five minutes.
rescpu|actav5_latest CPU Utilization for Resources|CPU
Active (5 min. average)
The average active time for the CPU over the past
five minutes
rescpu|actav15_latest CPU Utilization for Resources|CPU
Active (15 min. average)
The average active time for the CPU over the past
fifteen minutes
rescpu|actpk1_latest CPU Utilization for Resources|CPU
Active (1 min. peak)
The peak active time for the CPU over the past
minute
rescpu|actpk5_latest CPU Utilization for Resources|CPU
Active (5 min. peak)
The peak active time for the CPU over the past five
minutes
rescpu|actpk15_latest CPU Utilization for Resources|CPU
Active (15 min. peak)
The peak active time for the CPU over the past
fifteen minutes
rescpu|runav1_latest CPU Utilization for Resources|CPU
Running (1 min. average)
The average runtime for the CPU over the past
minute
rescpu|runav5_latest CPU Utilization for Resources|CPU
Running (5 min. average)
The average runtime for the CPU over the past five
minutes
rescpu|runav15_latest CPU Utilization for Resources|CPU
Running (15 min. average)
The average runtime for the CPU over the past
fifteen minutes
rescpu|runpk1_latest CPU Utilization for Resources|CPU
Running (1 min. peak)
The peak active time for the CPU over the past
minute
rescpu|runpk5_latest CPU Utilization for Resources|CPU
Running (5 min. peak)
The peak active time for the CPU over the past five
minutes
rescpu|runpk15_latest CPU Utilization for Resources|CPU
Running (15 min. peak)
The peak active time for the CPU over the past
fifteen minutes
rescpu|maxLimited1_latest CPU Utilization for Resources|CPU
Throttled (1 min. average)
The scheduling limit over the past minute
rescpu|maxLimited5_latest CPU Utilization for Resources|CPU
Throttled (5 min. average)
The scheduling limit over the past five minutes
rescpu|maxLimited15_latest CPU Utilization for Resources|CPU
Throttled (15 min. average)
The scheduling limit over the past fifteen minutes
rescpu|sampleCount_latest CPU Utilization for Resources|Group
CPU Sample Count
The sample CPU count
VMware by Broadcom  4353

---
## page 4354

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
rescpu|samplePeriod_latest CPU Utilization for Resources|Group
CPU Sample Period
The sample period
mem|usage_average Memory|Usage Memory currently in use as a percentage of total
available memory
mem|balloonPct Memory|Balloon Percentage of guest physical memory that is
currently claimed from the virtual machine through
ballooning. This is the percentage of guest physical
memory that has been allocated and pinned by the
balloon driver. Balloon does not necessarily mean
the VM performance is affected.
mem|swapped_average Memory|Swapped Amount of unreserved memory
mem|consumed_average Memory|Consumed Amount of ESXi Host memory mapped/consumed
by the virtual machine for guest memory
mem|consumed_average_mtd Memory|Consumed average MTD average MTD Amount of host memory consumed by
the virtual machine for guest memory
mem|consumedPct Memory|Consumed (%) Amount of host memory consumed by the virtual
machine for guest memory. Consumed memory
does not include overhead memory. It includes
shared memory and memory that might be
reserved, but not actually used.
mem|overhead_average Memory|Overhead Amount of overhead memory used by ESXi to run
the Virtual Machine.
mem|host_contentionPct Memory|Contention Percentage of time the VM has contended for
memory.
mem|guest_provisioned Memory|Total Capacity Memory resources allocated to the Virtual Machine
mem|guest_usage Memory|Guest Usage Guest Memory Entitlement
mem|guest_demand Memory|Guest Demand Guest Memory Entitlement
mem|host_demand Memory|Host Demand Memory Demand in KB
mem|reservation_used Memory|Reservation Used Memory Reservation Used
mem|effective_limit Memory|Effective limit Memory Effective limit
mem|vmMemoryDemand Memory|Utilization Amount of memory utilized by the Virtual Machine.
Reflects the guest OS memory required (for certain
vSphere and VMTools versions) or Virtual Machine
consumption
mem|nonzero_active Memory|Non Zero Active Non Zero Active Memory
mem|swapinRate_average Memory|Swap In Rate Rate at which memory is swapped from disk into
active memory during the collection interval. This
can impact performance.
mem|swapoutRate_average Memory|Swap Out Rate Rate at which memory is being swapped from active
memory to disk during the current interval.
mem|compressed_average Memory|Compressed Percentage of total memory that has been
compressed by vSphere. If and only if the page is
accessed by the Guest OS, will performance be
affected.
VMware by Broadcom  4354

---
## page 4355

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
mem|overheadMax_average Memory|Overhead Max N/A
mem|vmmemctl_average Memory|Balloon Amount of memory currently used by the virtual
machine memory control
mem|active_average Memory|Guest Active Amount of memory that is actively used
mem|granted_average Memory|Granted Amount of memory available for use
mem|shared_average Memory|Shared Amount of shared memory
mem|zero_average Memory|Zero Amount of memory that is all 0
mem|swaptarget_average Memory|Swap Target Amount of memory that can be swapped
mem|swapin_average Memory|Swap In Amount of memory swapped in
mem|swapout_average Memory|Swap Out Amount of memory swapped out
mem|vmmemctltarget_average Memory|Balloon Target Amount of memory that can be used by the virtual
machine memory control
mem|host_dynamic_entitlement Memory|Host Dynamic Entitlement Mem Machine Dynamic Entitlement
mem|host_active Memory|Host Active Machine Active
mem|host_usage Memory|Host Usage Machine Usage
mem|host_contention Memory|Contention Machine Contention
mem|guest_activePct Memory|Guest Active Memory Guest active memory as percentage of configured
mem|guest_dynamic_entitlement Memory|Guest Dynamic Entitlement Guest Memory Dynamic Entitlement
mem|host_demand_reservation Memory|Host Demand with
Reservation
Memory Demand with Reservation considered in KB
mem|host_nonpageable_estimate Memory|Guest Non Pageable
Memory
Guest Non Pageable Memory Estimates
mem|guest_nonpageable_estimate Memory|Host Non Pageable Memory Guest Non Pageable Memory Estimates
mem|estimated_entitlement Memory|Estimated entitlement Memory Estimated entitlement
mem|host_demand_for_aggregation Memory|Host Demand For
Aggregation
Host demand for aggregation
mem|demandOverLimit Memory|Demand Over Limit Amount of Memory Demand that is over the
configured Memory Limit
mem|demandOverCapacity Memory|Demand Over Capacity Amount of Memory Demand that is over the
configured Memory Capacity
mem|activewrite_average Memory|Active Write N/A
mem|compressionRate_average Memory|Compression Rate N/A
mem|decompressionRate_average Memory|Decompression Rate N/A
mem|zipSaved_latest Memory|Zip Saved N/A
mem|zipped_latest Memory|Zipped N/A
mem|entitlement_average Memory|Entitlement Amount of host physical memory the VM is entitled
to, as determined by the ESX schedule.
mem|latency_average Memory|Latency Percentage of time the VM is waiting to access
swapped or compressed memory.
mem|capacity.contention_average Memory|Capacity Contention Capacity Contention.
VMware by Broadcom  4355

---
## page 4356

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
mem|llSwapInRate_average Memory|Swap In Rate from Host
Cache
Rate at which memory is being swapped from host
cache into active memory.
mem|llSwapOutRate_average Memory|Swap Out Rate to Host
Cache
Rate at which memory is being swapped to host
cache from active memory.
mem|llSwapUsed_average Memory|Swap Space Used in Host
Cache
Space used for caching swapped pages in the host
cache.
mem|overheadTouched_average Memory|Overhead Touched Actively touched overhead memory (KB) reserved
for use as the virtualization overhead for the VM.
net|usage_average Network|Usage Rate The sum of the data transmitted and received for all
the NIC instances of the host or virtual machine
net|transmitted_average Network|Data Transmit Rate Average amount of data transmitted per second
net|received_average Network|Data Receive Rate Average amount of data received per second
net|droppedTx_summation Network|Transmitted Packets
Dropped
Number of outgoing packets dropped in the
performance interval. Investigate if the number is
not 0
net|droppedPct Network|Packets Dropped (%) Percentage of packets dropped
net|dropped Network|Packets Dropped Number of packets dropped in the performance
interval
net|broadcastTx_summation Network|Broadcast Packets
Transmitted
Total number of broadcast packets transmitted.
Investigate further if this number is high
net|multicastTx_summation Network|Multicast Packets
Transmitted
Number of multicast packets transmitted.
Investigate further if this number is high
net|idle NetworkIidle N/A
net|usage_capacity Network|I/O Usage Capacity I/O Usage Capacity
net|maxObserved_KBps Network|Max Observed Throughput Max observed rate of network throughput
net|maxObserved_Tx_KBps Network|Max Observed Transmitted
Throughput
Max observed transmitted rate of network
throughput
net|maxObserved_Rx_KBps Network|Max Observed Received
Throughput
Max observed received rate of network throughput
net|packetsRx_summation Network|Packets Received Number of packets received in the performance
interval
net|packetsTx_summation Network|Packets Transmitted Number of packets transmitted in the performance
interval
net|demand Network|Demand N/A
net|packetsRxPerSec Network|Packets Received per
second
Number of packets received in the performance
interval
net|packetsTxPerSec Network|Packets Transmitted per
second
Number of packets transmitted in the performance
interval
net|packetsPerSec Network|Packets per second Number of packets transmitted and received per
second
net|droppedRx_summation Network|Received Packets Dropped Number of received packets dropped in the
performance interval
VMware by Broadcom  4356

---
## page 4357

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
net|broadcastRx_summation Network|Broadcast Packets Received Number of broadcast packets received during the
sampling interval
net|multicastRx_summation Network|Multicast Packets Received Number of multicast packets received
net|bytesRx_average Network|bytesRx Average amount of data received per second
net|bytesTx_average Network|bytesTx Average amount of data transmitted per second
net|host_transmitted_average Network|VM to Host Data Transmit
Rate
Average amount of data transmitted per second
between VM and host
net|host_received_average Network|VM to Host Data Receive
Rate
Average amount of data received per second
between VM and host
net|host_usage_average Network|VM to Host Usage Rate The sum of the data transmitted and received for all
the NIC instances between VM and host
net|host_maxObserved_Tx_KBps Network|VM to Host Max Observed
Transmitted Throughput
Max observed transmitted rate of network
throughput between VM and host
net|host_maxObserved_Rx_KBps Network|VM to Host Max Observed
Received Throughput
Max observed received rate of network throughput
between VM and host
net|host_maxObserved_KBps Network|VM to Host Max Observed
Throughput
Max observed rate of network throughput between
VM and host
net|transmit_demand_average Network|Data Transmit Demand Rate Data Transmit Demand Rate
net|receive_demand_average Network|Data Receive Demand Rate Data Receive Demand Rate
disk|usage_average Physical Disk|Total Throughput Amount of data read from/written to storage in a
second. This is averaged over the reporting period
disk|read_average Physical Disk|Read Throughput Amount of data read from storage in a second. This
is averaged over the reporting period
disk|write_average Physical Disk|Write Throughput Amount of data written to storage in a second. This
is averaged over the reporting period
disk|usage_capacity Physical Disk|I/O Usage Capacity I/O Usage Capacity
disk|busResets_summation Physical Disk|Bus Resets The number of bus resets in the performance
interval
disk|commandsAborted_summation Physical Disk|Commands Aborted The number of disk commands stopped in the
performance interval
disk|diskoio Physical Disk|Number of Outstanding
IO Operations
Number of Outstanding IO Operations
disk|diskqueued Physical Disk|Queued Operations Queued Operations
disk|diskdemand Physical Disk|Demand Demand
disk|sum_queued_oio Physical Disk|Total Queued
Outstanding operations
Sum of Queued Operation and Outstanding
Operations.
disk|max_observed Physical Disk|Max Observed OIO Max Observed IO for a disk.
disk|numberReadAveraged_average Physical Disk|Read IOPS Number of read operations per second. This is
averaged over the reporting period.
disk|numberWriteAveraged_average Physical Disk|Write IOPS Number of write operations per second. This is
averaged over the reporting period.
VMware by Broadcom  4357

---
## page 4358

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
disk|maxTotalLatency_latest Physical Disk|Highest Latency Highest Latency.
disk|scsiReservationConflicts_summatio
n
Physical Disk|SCSI Reservation
Conflicts
SCSI Reservation Conflicts.
disk|totalReadLatency_average Physical Disk|Read Latency Average amount of time for a read operation by the
storage adapter.
disk|totalWriteLatency_average Physical Disk|Write Latency Average amount of time for a write operation by the
storage adapter.
disk|totalLatency_average Physical Disk|Total Latency Total Latency.
sys|poweredOn System|Powered ON 1 if the VM is connected (available for management)
and powered on, otherwise 0.
sys|osUptime_latest System|OS Uptime Total time elapsed, in seconds, since last operating
system boot-up
sys|uptime_latest System|Uptime Number of seconds since system startup
sys|heartbeat_summation System|Heartbeat Number of heart beats from the virtual machine in
the defined interval
sys|vmotionEnabled System|vMotion Enabled 1 if vMotion enabled, 0 if not enabled
sys|productString System|Product String VMware product string
sys|heartbeat_latest System|Heartbeat Latest Number of heartbeats issued per virtual machine
during the interval
summary|running Summary|Running Running
summary|desktop_status Summary|Desktop Status Horizon View Desktop Status
summary|poweredOff Summary|Reclaimable Powered Off Powered Off = 1. Not powered off = 0
summary|idle Summary|Reclaimable Idle Idle = 1. Not idle = 0
summary|oversized Summary|Is Oversized Oversized = 1. Not oversized = 0
summary|undersized Summary|Is Undersized Is Undersized
summary|snapshotSpace Summary|Reclaimable Snapshot
Space
Reclaimable Snapshot Space
summary|oversized|vcpus Summary|Oversized|Virtual CPUs Virtual CPUs
summary|oversized|memory Summary|Oversized|Memory Memory
summary|undersized|vcpus Summary|Undersized|Virtual CPUs Virtual CPUs
summary|undersized|memory Summary|Undersized|Memory Memory
summary|metering|value Summary|Metering|Total price Total price of the resource(Sum of all price
components)
summary|metering|storage Summary|Metering|Storage price Price of Storage related components of the resource
summary|metering|memory Summary|Metering|Memory price Price of Memory related components of the
resource
summary|metering|cpu Summary|Metering|CPU price Price of CPU related components of the resource
summary|metering|additional Summary|Metering|Additional price Price of additional components of the resource
summary|metering|partialPrice Summary|Metering|Partial price Shows whether the calculated price is partial for the
resource
VMware by Broadcom  4358

---
## page 4359

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
summary|workload_indicator Summary|Workload Indicator Workload Indicator
summary|cpu_shares Summary|CPU Shares CPU Shares
summary|mem_shares Summary|Memory Shares Memory Shares
summary|number_datastore Summary|Number of Datastores Number of Datastores
summary|number_network Summary|Number of Networks Number of Networks
guestfilesystem|capacity Guest File System|Partition Capacity Disk space capacity on guest file system partition.
guestfilesystem|percentage Guest File System|Partition Utilization
(%)
Guest file system partition space utilization in
percentage
guestfilesystem|usage Guest File System|Partition Utilization Guest file system partition space utilization
guestfilesystem|capacity_total Guest File System|Total Capacity Disk space capacity on guest file system
guestfilesystem|percentage_total Guest File System|Utilization (%) Guest file system disk space utilization in
percentage
guestfilesystem|usage_total Guest File System|Utilization Guest file system disk space utilization
guestfilesystem|freespace Guest File System|Guest File System
Free
Total free space on guest file system
guestfilesystem|capacity_property Guest File System|Guest File System
Capacity Property
Total capacity of guest file system as a property
guestfilesystem|freespace_total Guest File System|Total Guest File
System Free
Total free space on guest file system
guestfilesystem|capacity_property_total Guest File System|Total Capacity
Property
Total capacity of guest file system as a property
guest|mem.free_latest Guest|Free Memory Free Memory
guest|mem.needed_latest Guest|Needed Memory Needed Memory
guest|mem.physUsable_latest Guest|Physically Usable Memory Physically Usable Memory
guest|page.inRate_latest Guest|Page In Rate per second Page In Rate per second
guest|page.size_latest Guest|Page Size Page Size
guest|swap.spaceRemaining_latest Guest|Remaining Swap Space Remaining Swap Space
guest|cpu_queue Guest|CPU Queue The number of ready threads queuing in the CPU.
Linux includes threads in running state. A number
greater than 2 for prolong period indicates CPU core
bottleneck.
guest|disk_queue Guest|Disk Queue The number of outstanding requests + IO currently
in progress.
guest|contextSwapRate_latest Guest|Context Swap Rate per second Context Swap Rate per second
guest|hugePage.size_latest Guest|Huge Page Size Huge Page Size
guest|hugePage.total_latest Guest|Total Huge Pages Total Huge Pages
guest|mem.activeFileCache_latest Guest|Active File Cache Memory Active File Cache Memory
guest|page.outRate_latest Guest|Page Out Rate per second Page Out Rate per second
guest|disk_queue_latest Guest|Disk Queue Latest The number of outstanding requests + IO currently
in progress.
VMware by Broadcom  4359

---
## page 4360

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
virtualDisk|numberReadAveraged_avera
ge
Virtual Disk|Read IOPS Number of read operations per second. This is
averaged over the reporting period
virtualDisk|numberWriteAveraged_avera
ge
Virtual Disk|Write IOPS Number of write operations per second. This is
averaged over the reporting period
virtualDisk|read_average Virtual Disk|Read Throughput Amount of data read from storage in a second. This
is averaged over the reporting period
virtualDisk|totalReadLatency_average Virtual Disk|Read Latency Average amount of time for a read operation by the
storage adapter.
virtualDisk|totalWriteLatency_average Virtual Disk|Write Latency Average amount of time for a write operation by the
storage adapter.
virtualDisk|write_average Virtual Disk|Write Throughput Amount of data written to storage in a second. This
is averaged over the reporting period
virtualDisk|usage Virtual Disk|Total Throughput Amount of data read from/written to storage in a
second. This is averaged over the reporting period
virtualDisk|totalLatency Virtual Disk|Total Latency Total Latency
virtualDisk|commandsAveraged_average Virtual Disk|Total IOPS Number of read/write operations per second. This is
averaged over the reporting period
virtualDisk|vDiskOIO Virtual Disk|Outstanding IO requests OIO for datastore.
virtualDisk|actualUsage Virtual Disk|Used Disk Space Virtual Disk space usage
virtualDisk|busResets_summation Virtual Disk|Bus Resets The number of bus resets in the performance
interval
virtualDisk|commandsAborted_summati
on
Virtual Disk|Commands Aborted The number of disk commands stopped in the
performance interval
virtualDisk|readLoadMetric_latest Virtual Disk|Read Load Storage DRS virtual disk metric read load
virtualDisk|readOIO_latest Virtual Disk|Outstanding Read
Requests
Average number of outstanding read requests to the
virtual disk
virtualDisk|writeLoadMetric_latest Virtual Disk|Write Load Storage DRS virtual disk write load
virtualDisk|writeOIO_latest Virtual Disk|Outstanding Write
Requests
Average number of outstanding write requests to the
virtual disk
virtualDisk|smallSeeks_latest Virtual Disk|Number of Small Seeks Small Seeks
virtualDisk|mediumSeeks_latest Virtual Disk|Number of Medium
Seeks
Medium Seeks
virtualDisk|largeSeeks_latest Virtual Disk|Number of Large Seeks Large Seeks
virtualDisk|readLatencyUS_latest Virtual Disk|Read Latency
(microseconds)
Read latency in microseconds
virtualDisk|writeLatencyUS_latest Virtual Disk|Write Latency
(microseconds)
Write Latency in microseconds
virtualDisk|readIOSize_latest Virtual Disk|Average Read request
size
Read IO size
virtualDisk|writeIOSize_latest Virtual Disk|Average Write request
size
Write IO size
diskspace|pod_used Disk Space|Pod used Space used by Pod files
VMware by Broadcom  4360

---
## page 4361

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
diskspace|provisionedSpace Disk Space|Provisioned Space for
Pod
Provisioned space for Pod. In thin provisioned, it
is the full space allocated (which may not be used
yet).
diskspace|notshared Disk Space|Not Shared Space used by VM that is not shared with other VM
diskspace|activeNotShared Disk Space|Active not shared Unshared disk space used by VMs excluding
snapshot
diskspace|perDsUsed Disk Space|Pod used Space used by all files of the Pod on the datastore
(disks, snapshots, configs, logs, etc).
diskspace|total_usage Disk Space|Utilization Total disk space used on all datastores visible to this
object
diskspace|total_capacity Disk Space|Total Capacity Total disk space on all datastores visible to this
object
diskspace|diskused Disk Space|Virtual Disk Used Space used by virtual disks
diskspace|snapshot Disk Space|Snapshot Space Space used by snapshots
diskspace|shared Disk Space|Shared Used Shared space used
diskspace|provisioned Disk Space|Provisioned Space Provisioned space
diskspace|snapshot|used Disk Space|Snapshot|Pod used Disk space used by the Pod snapshot files. This is
the space that can be potentially reclaimed if the
snapshot is removed.
diskspace|snapshot|accessTime Disk Space|Snapshot|Access Time The date and time the snapshot was taken.
storage|totalReadLatency_average Storage|Read Latency Average amount of time for a read operation.
storage|totalWriteLatency_average Storage|Write Latency Average amount of time for a write operation.
storage|read_average Storage|Read Rate Read throughput rate
storage|write_average Storage|Write Rate Write throughput rate
storage|usage_average Storage|Total Usage Total throughput rate
storage|numberReadAveraged_average Storage|Reads per second Average number of read commands issued per
second during the collection interval
storage|numberWriteAveraged_average Storage|Writes per second Average number of write commands issued per
second during the collection interval
storage|commandsAveraged_average Storage|Commands per second Average number of commands issued per second
during the collection interval
storage|totalLatency_average Storage|Total Latency Total latency
storage|demandKBps Storage|Demand N/A
storage|contention Storage|Contention percentage N/A
cost|monthlyTotalCost Cost|MTD Total Cost Month To Date Cost of Virtual Machine
cost|monthlyProjectedCost Cost|Monthly Projected Total Cost Virtual Machine cost projected for full month
cost|compTotalCost Cost|MTD Compute Total Cost Month to Date Total Compute Cost (Including CPU
and Memory) of Virtual Machine
cost|directCost Cost|Monthly Direct Cost Monthly Direct Cost (comprising of OS Labor, VI
Labor and any windows desktop instance license) of
Virtual Machine
VMware by Broadcom  4361

---
## page 4362

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
cost|cpuCost Cost|MTD CPU Cost Month to Date Virtual Machine CPU Cost. It is
based on utilization. The more the VM uses, the
higher its cost.
cost|memoryCost Cost|MTD Memory Cost Month to Date Memory Cost of Virtual Machine. It
is based on utilization. The more the VM uses, the
higher its cost.
cost|storageCost Cost|MTD Disk Space Cost Month to Date Disk Space Cost of Virtual Machine
cost|reclaimableCost Cost|Potential Savings Potential Savings
cost|osLaborTotalCost Cost|Monthly OS Labor Cost Operating System Labor Cost of Virtual Machine for
full month
cost|viLaborTotalCost Cost|Monthly VI Labor Cost Monthly VI Labor Cost
cost|effectiveTotalCost Cost|MTD Effective Total Cost Month to Date Cost of Virtual Machine considering
the allocation and demand model
cost|effectiveProjectedTotalCost Cost|Monthly Effective Projected
Total Cost
Virtual Machine cost projected for full month
considering the allocation and demand model
cost|allocation|allocationBasedCpuMTD
Cost
Cost|Allocation|MTD CPU Cost Month to Date Virtual Machine CPU Cost. It is
based on utilization. The more the VM uses, the
higher its cost.
cost|allocation|allocationBasedMemoryM
TDCost
Cost|Allocation|MTD Memory Cost Month to Date Memory Cost of Virtual Machine. It
is based on utilization. The more the VM uses, the
higher its cost.
cost|allocation|allocationBasedStorageM
TDCost
Cost|Allocation|MTD Disk Space Cost Month to Date Disk Space Cost of Virtual Machine
cost|allocation|allocationBasedTotalMTD
Cost
Cost|Allocation|MTD Total Cost Month To Date Cost of Virtual Machine
cost|allocation|allocationBasedTotalCost Cost|Allocation|Monthly Projected
Total Cost
Virtual Machine cost projected for full month
datastore|demand_oio Datastore|Outstanding IO requests Amount of IO waiting in the queue to be executed.
High IO, coupled with high latency, impacts
performance.
datastore|numberReadAveraged_averag
e
Datastore|Read IOPS Number of read operations per second. This is
averaged over the reporting period.
datastore|numberWriteAveraged_averag
e
Datastore|Write IOPS Number of write operations per second. This is
averaged over the reporting period.
datastore|read_average Datastore|Read Throughput Amount of data read from storage in a second. This
is averaged over the reporting period.
datastore|totalReadLatency_average Datastore|Read Latency Average amount of time for a read operation at the
datastore level. It's an average of all the VMs in the
datastore.
datastore|totalWriteLatency_average Datastore|Write Latency Average amount of time for a write operation by the
storage adapter.
datastore|write_average Datastore|Write Throughput Amount of data written from storage in a second.
This is averaged over the reporting period.
VMware by Broadcom  4362

---
## page 4363

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
datastore|totalLatency_average Datastore|Total Latency Normalized Latency, taking into account the read/
write ratio.
datastore|usage_average Datastore|Total Throughput Amount of data read from/written to storage in a
second. This is averaged over the reporting period.
datastore|commandsAveraged_average Datastore|Total IOPS Number of read/write operations per second. This is
averaged over the reporting period.
datastore|used Datastore|Used Space Used Space.
datastore|demand Datastore|Demand Max of datastore "Reads Per Sec", "Writes Per
Sec", "Read Rate", "Write Rate", "OIO Per Sec"
percentages.
datastore|maxTotalLatency_latest Datastore|Highest Latency Highest Latency.
datastore|totalLatency_max Datastore|Total Latency Max Total Latency Max (ms).
datastore|maxObserved_NumberRead Datastore|Max Observed Reads per
second
Max observed average number of read commands
issued per second during the collection interval.
datastore|maxObserved_Read Datastore|Max Observed Read Rate Max observed rate of reading data from the
datastore.
datastore|maxObserved_NumberWrite Datastore|Max Observed Writes per
second
Max observed average number of write commands
issued per second during the collection interval.
datastore|maxObserved_Write Datastore|Max Observed Write Rate Max observed rate of writing data from the
datastore.
datastore|maxObserved_OIO Datastore|Max Observed Number of
Outstanding IO Operations
N/A
Power Metrics for vSphere Pods
Power metrics provide information about the vSphere pods power use.
Metric Name Description
Power|Total Energy Consumed in the collection period (Wh) Displays the total electricity consumed based on the time
interval selected. The default collection cycle is set to 5 mins.
You can continue using the default setting or edit it for each
adapter instance. For example, if the time interval is set to its
default value, the value represents the energy consumed per 5
mins.
Power|Current Power Consumption Rate (Watt) The power consumption rate per second, averaged over the
reporting period.
Key: power|power_average
Power|(DEP) Energy (Joule) Total energy consumed in joules.
Key: power|energy_summation
OS and Application Monitoring Metrics
Metrics are collected for operating systems, application services, remote checks, Linux processes, and Windows services.
VMware by Broadcom  4363

---
## page 4364

 VMware Cloud Foundation 9.0
Operating System Metrics
Metrics are collected for Linux and Windows operating systems.
Linux Platforms
The following metrics are collected for Linux operating systems:
Table 1269: Metrics for Linux
Metric Metric Category KPI
<Instance name>| Usage Idle CPU False
<Instance name>| Usage IO-Wait CPU False
<Instance name>|Time Active CPU True
<Instance name>|Time Guest CPU False
<Instance name>|Time Guest Nice CPU False
<Instance name>|Time Idle CPU False
<Instance name>|Time IO-Wait CPU False
<Instance name>|Time IRQ CPU True
<Instance name>|Time Nice CPU False
<Instance name>|Time Soft IRQ CPU True
<Instance name>|Time Steal CPU False
<Instance name>|Time System CPU False
<Instance name>|Time User CPU True
<Instance name>|Usage Active (%) CPU True
<Instance name>|Usage Guest (%) CPU False
<Instance name>|Usage Guest Nice (%) CPU False
<Instance name>|Usage IRQ (%) CPU True
<Instance name>|Usage Nice (%) CPU False
<Instance name>|Usage Soft IRQ (%) CPU True
<Instance name>|Usage Steal (%) CPU False
<Instance name>|Usage System (%) CPU True
<Instance name>|Usage User (%) CPU True
CPU Load1 (%) CPU Load False
CPU Load15 (%) CPU Load False
CPU Load5 (%) CPU Load False
<Instance name>|IO Time Disk IO False
<Instance name>|Read Time Disk IO False
<Instance name>|Reads Disk IO False
<Instance name>|Write Time Disk IO False
<Instance name>|Writes Disk IO False
VMware by Broadcom  4364

---
## page 4365

 VMware Cloud Foundation 9.0
Metric Metric Category KPI
<Instance name>|Disk Free Disk False
<Instance name>|Disk Total Disk False
<Instance name>|Disk Used (%) Disk False
Cached Memory False
Free Memory False
Inactive Memory False
Total Memory True
Used Memory True
Used Percent Memory True
Blocked Processes True
Dead Processes False
Running Processes False
Sleeping Processes False
Stopped Processes False
Zombies Processes False
Free Swap False
In Swap False
Out Swap False
Total Swap True
Used Swap True
Used Percent Swap True
Telegraf Availability None False
Windows Platforms
The following metrics are collected for Windows operating systems:
Table 1270: Metrics for Windows
Metric Metric Category KPI
Idle Time CPU False
Interrupt Time CPU False
Interrupts persec CPU True
Privileged Time CPU False
Processor Time CPU False
User Time CPU False
DPC Time (%) CPU False
Usage Guest (%) CPU False
Usage System (%) CPU False
VMware by Broadcom  4365

---
## page 4366

 VMware Cloud Foundation 9.0
Metric Metric Category KPI
Usage User (%) CPU False
Avg. Disk Bytes Read Disk False
Avg. Disk sec Read Disk False
Avg. Disk sec Write Disk False
Avg. Disk Write Queue Length Disk False
Avg. Disk Read Queue Length Disk False
Disk Read Time Disk False
Disk Write Time Disk False
Free Megabytes Disk False
Free Space Disk False
Idle Time Disk False
Split IO persec Disk False
Available Bytes Memory True
Cache Bytes Memory False
Cache Faults persec Memory False
Committed Bytes Memory True
Demand Zero Faults persec Memory False
Page Faults persec Memory True
Pages persec Memory False
Pool Nonpaged Bytes Memory True
Pool Paged Bytes Memory False
Transition Faults persec Memory False
Total (bytes) Memory False
Used (bytes) Memory False
Used Percent(%) Memory False
Bytes Received persec Network False
Bytes Sent persec Network False
Packets Outbound Discarded Network False
Packets Outbound Errors Network False
Packets Received Discarded Network False
Packets Received Errors Network False
Packets Received persec Network False
Packets Sent persec Network False
Elapsed Time Process False
Handle Count Process False
IO Read Bytes persec Process False
IO Read Operations persec Process False
VMware by Broadcom  4366

---
## page 4367

 VMware Cloud Foundation 9.0
Metric Metric Category KPI
IO Write Bytes persec Process False
IO Write Operations persec Process False
Privileged Time Process False
Processor Time Process False
Thread Count Process False
User Time Process False
Context Switches persec System False
Processes System False
Processor Queue Length System False
System Calls persec System False
System Up Time System False
Threads System False
Used Percent (%) Swap False
Total (bytes) Swap False
Telegraf Availability None False
Application Service Metrics
Metrics are collected for 23 application services.
Active Directory Metrics
Metrics are collected for the Active Directory application service.
Table 1271: Active Directory Metrics
Metric Name Category KPI
Database Cache % Hit (%) Active Directory Database True
Database Cache Page Faults/sec Active Directory Database True
Database Cache Size Active Directory Database False
Data Lookups Active Directory DFS Replication False
Database Commits Active Directory DFS Replication True
Avg Response Time Active Directory DFSN True
Requests Failed Active Directory DFSN False
Requests Processed Active Directory DFSN False
Dynamic Update Received Active Directory DNS False
Dynamic Update Rejected Active Directory DNS False
Recursive Queries Active Directory DNS False
Recursive Queries Failure Active Directory DNS False
VMware by Broadcom  4367

---
## page 4368

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Secure Update Failure Active Directory DNS False
Total Query Received Active Directory DNS True
Total Response Sent Active Directory DNS True
Digest Authentications Active Directory Security System-Wide Statistics True
Kerberos Authentications Active Directory Security System-Wide Statistics True
NTLM Authentications Active Directory Security System-Wide Statistics True
Directory Services:<InstanceName>|Base Searches
persec
Active Directory Services False
Directory Services:<InstanceName>|Database adds
persec
Active Directory Services False
Directory Services:<InstanceName>|Database
deletes persec
Active Directory Services False
Directory Services<InstanceName>|Database
modifys/sec
Active Directory Services False
Directory Services<InstanceName>|Database
recycles/sec
Active Directory Services False
Directory Services<InstanceName>|DRA Inbound
Bytes Total/sec
Active Directory Services False
Directory Services<InstanceName>|DRA Inbound
Objects/sec
Active Directory Services False
Directory Services<InstanceName>|DRA Outbound
Bytes Total/sec
Active Directory Services False
Directory Services<InstanceName>|DRA Outbound
Objects/sec
Active Directory Services False
Directory Services<InstanceName>|DRA Pending
Replication Operations
Active Directory Services False
Directory Services<InstanceName>|DRA Pending
Replication Synchronizations
Active Directory Services False
Directory Services<InstanceName>|DRA Sync
Requests Made
Active Directory Services False
Directory Services<InstanceName>|DRA Sync
Requests Successful
Active Directory Services False
Directory Services<InstanceName>|DS Client Binds/
sec
Active Directory Services True
Directory Services<InstanceName>|DS Directory
Reads/sec
Active Directory Services False
Directory Services<InstanceName>|DS Directory
Searches/sec
Active Directory Services True
Directory Services<InstanceName>|DS Server Binds/
sec
Active Directory Services True
Directory Services<InstanceName>|DS Threads in
Use
Active Directory Services True
VMware by Broadcom  4368

---
## page 4369

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Directory Services:<InstanceName>|LDAP Active
Threads
Active Directory Services False
Directory Services:<InstanceName>|LDAP Client
Sessions
Active Directory Services True
Directory Services<InstanceName>|LDAP Closed
Connections/sec
Active Directory Services False
Directory Services<InstanceName>|LDAP New
Connections/sec
Active Directory Services True
Directory Services<InstanceName>|LDAP Searches/
sec
Active Directory Services True
Directory Services<InstanceName>|LDAP
Successful Binds/sec
Active Directory Services False
Directory Services<InstanceName>|LDAP UDP
operations/sec
Active Directory Services False
Directory Services:<InstanceName>|LDAP Writes/
sec
Active Directory Services False
Application Availability Active Directory False
ActiveMQ Metrics
Metrics are collected for the ActiveMQ application service.
Table 1272: ActiveMQ Metrics
Metric Name Category KPI
Buffer Pool<InstanceName>|
Count
Active MQ False
Buffer Pool<InstanceName>|
Memory Used
Active MQ False
Buffer Pool<InstanceName>|
Total Capacity
Active MQ False
Class Loading|Loaded Class
Count
Active MQ False
Class Loading|Unloaded Class
Count
Active MQ False
Class Loading|Total Loaded
Class Count
Active MQ False
File Descriptor Usage|Max File
Descriptor Count
Active MQ False
File Descriptor Usage|Open File
Descriptor Count
Active MQ False
Garbage
Collection<InstanceName>|Total
Collection Count
Active MQ False
VMware by Broadcom  4369

---
## page 4370

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Garbage
Collection<InstanceName>|Total
Collection Time
Active MQ False
JVM Memory
Pool<InstanceName>|Peak
Usage|Committed Memory
Active MQ False
JVM Memory
Pool<InstanceName>|Peak
Usage|Initial Memory
Active MQ False
JVM Memory
Pool<InstanceName>|Peak
Usage|Maximum Memory
Active MQ False
JVM Memory
Pool<InstanceName>|Peak
Usage|Used Memory
Active MQ False
JVM Memory
Pool<InstanceName>|Usage|
Committed Memory
Active MQ False
JVM Memory
Pool<InstanceName>|Usage|
Initial Memory
Active MQ False
JVM Memory
Pool<InstanceName>|Usage|
Maximum Memory
Active MQ False
JVM Memory
Pool<InstanceName>|Usage|
Used Memory
Active MQ False
Application Availability Active MQ False
Threading|Thread Count Active MQ False
Uptime Active MQ False
UTILIZATION|Process CpuLoad Active MQ False
UTILIZATION|Memory Limit ActiveMQ Broker True
UTILIZATION|Memory Percent
Usage (%)
ActiveMQ Broker True
UTILIZATION|Store Limit ActiveMQ Broker False
UTILIZATION|Store Percent
Usage (%)
ActiveMQ Broker False
UTILIZATION|Temp Limit ActiveMQ Broker False
UTILIZATION|Temp Percent
Usage (%)
ActiveMQ Broker False
UTILIZATION|Total Consumer
Count
ActiveMQ Broker True
VMware by Broadcom  4370

---
## page 4371

 VMware Cloud Foundation 9.0
Metric Name Category KPI
UTILIZATION|Total Dequeue
Count
ActiveMQ Broker True
UTILIZATION|Total Enqueue
Count
ActiveMQ Broker True
UTILIZATION|Total Message
Count
ActiveMQ Broker True
JVM Memory|Heap Memory
Usage|Initial Memory
ActiveMQ JVM Memory Usage False
JVM Memory|Heap Memory
Usage|Committed Memory
ActiveMQ JVM Memory Usage False
JVM Memory|Heap Memory
Usage|Maximum Memory
ActiveMQ JVM Memory Usage False
JVM Memory|Heap Memory
Usage|Used Memory
ActiveMQ JVM Memory Usage False
JVM Memory|Non Heap
Memory Usage|Committed
Memory
ActiveMQ JVM Memory Usage False
JVM Memory|Non Heap
Memory Usage|Initial Memory
ActiveMQ JVM Memory Usage False
JVM Memory|Non Heap
Memory Usage|Maximum
Memory
ActiveMQ JVM Memory Usage False
JVM Memory|Non Heap
Memory Usage|Used Memory
ActiveMQ JVM Memory Usage False
JVM Memory|Object Pending
FinalizationCount
ActiveMQ JVM Memory Usage False
UTILIZATION|Process CpuLoad ActiveMQ OS False
UTILIZATION|System Cpu Load ActiveMQ OS False
UTILIZATION|Consumer Count ActiveMQ Topic True
UTILIZATION|Dequeue Count ActiveMQ Topic True
UTILIZATION|Enqueue Count ActiveMQ Topic True
UTILIZATION|Queue Size ActiveMQ Topic True
UTILIZATION|Producer Count ActiveMQ Topic False
Apache HTTPD Metrics
Metrics are collected for the Apache HTTPD application service.
Note:  Metrics are collected for the Events MPM. Metrics are not collected for the other MPMs.
Table 1273: Apache HTTPD Metrics
Metric Name Category KPI
UTILIZATION|Busy Workers Apache HTTPD True
VMware by Broadcom  4371

---
## page 4372

 VMware Cloud Foundation 9.0
Metric Name Category KPI
UTILIZATION|Bytes Per Req Apache HTTPD False
UTILIZATION|Bytes Per Sec Apache HTTPD False
UTILIZATION|CPU Load Apache HTTPD True
UTILIZATION|CPU User Apache HTTPD False
UTILIZATION|Idle Workers Apache HTTPD True
UTILIZATION|Request Per Sec Apache HTTPD True
UTILIZATION|SCBoard Closing Apache HTTPD False
UTILIZATION|SCBoard DNS Lookup Apache HTTPD False
UTILIZATION|SCBoard Finishing Apache HTTPD False
UTILIZATION|SCBoard Idle Cleanup Apache HTTPD False
UTILIZATION|SCBoard Keep Alive Apache HTTPD False
UTILIZATION|SCBoard Logging Apache HTTPD False
UTILIZATION|SCBoard Open Apache HTTPD False
UTILIZATION|SCBoard Reading Apache HTTPD False
UTILIZATION|SCBoard Sending Apache HTTPD False
UTILIZATION|SCBoard Starting Apache HTTPD False
UTILIZATION|SCBoard Waiting Apache HTTPD False
UTILIZATION|Total Accesses Apache HTTPD False
UTILIZATION|Total Bytes Apache HTTPD True
UTILIZATION|Total Connections Apache HTTPD False
UTILIZATION|Uptime Apache HTTPD True
UTILIZATION|Asynchronous Closing Connections Apache HTTPD False
UTILIZATION|Asynchronous Keep Alive Connections Apache HTTPD False
UTILIZATION|Asynchronous Writing Connections Apache HTTPD False
UTILIZATION|ServerUptimeSeconds Apache HTTPD False
UTILIZATION|Load1 Apache HTTPD False
UTILIZATION|Load5 Apache HTTPD False
UTILIZATION|ParentServerConfigGeneration Apache HTTPD False
UTILIZATION|ParentServerMPMGeneration Apache HTTPD False
Application Availability Apache HTTPD False
Apache HTTPD
Metrics are collected for the Apache HTTPD application service.
Table 1274: Apache Tomcat
Metric Name Category KPI
Buffer Pool<InstanceName>|Count Tomcat Server False
VMware by Broadcom  4372

---
## page 4373

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Buffer Pool<InstanceName>|Memory Used Tomcat Server False
Buffer Pool<InstanceName>|Total Capacity Tomcat Server False
Class Loading|Loaded Class Count Tomcat Server False
Class Loading|Total Loaded Class Count Tomcat Server False
Class Loading|Unloaded Class Count Tomcat Server False
File Descriptor Usage|Max File Descriptor Count Tomcat Server False
File Descriptor Usage|Open File Descriptor Count Tomcat Server False
Garbage Collection:<InstanceName>|Total Collection
Count
Tomcat Server False
Garbage Collection:<InstanceName>|Total Collection
Time
Tomcat Server True
JVM Memory|Heap Memory Usage|Committed
Memory
Tomcat Server False
JVM Memory|Heap Memory Usage|Initial Memory Tomcat Server False
JVM Memory|Heap Memory Usage|Maximum
Memory
Tomcat Server False
JVM Memory|Heap Memory Usage|Used Memory Tomcat Server False
JVM Memory|Non Heap Memory Usage|Committed
Memory
Tomcat Server False
JVM Memory|Non Heap Memory Usage|Initial
Memory
Tomcat Server False
JVM Memory|Non Heap Memory Usage|Maximum
Memory
Tomcat Server False
JVM Memory|Non Heap Memory Usage|Used
Memory
Tomcat Server False
JVM Memory|Number of Object Pending Finalization
Count
Tomcat Server False
JVM Memory|Pool:<InstanceName>|Peak Usage|
Committed Memory
Tomcat Server False
JVM Memory|Pool:<InstanceName>|Peak Usage|
Initial Memory
Tomcat Server False
JVM Memory|Pool:<InstanceName>|Peak Usage|
Maximum Memory
Tomcat Server False
JVM Memory|Pool:<InstanceName>|Peak Usage|
Used Memory
Tomcat Server False
JVM Memory|Pool:<InstanceName>|Usage|
Committed Memory
Tomcat Server False
JVM Memory|Pool:<InstanceName>|Usage|Initial
Memory
Tomcat Server False
JVM Memory|Pool:<InstanceName>|Usage|
Maximum Memory
Tomcat Server False
VMware by Broadcom  4373

---
## page 4374

 VMware Cloud Foundation 9.0
Metric Name Category KPI
JVM Memory|Pool:<InstanceName>|Usage|Used
Memory
Tomcat Server False
Process CPU Usage (%) Tomcat Server True
System CPU Usage (%) Tomcat Server True
System Load Average (%) Tomcat Server True
Threading|Thread Count Tomcat Server False
Uptime Tomcat Server True
Application Availability Tomcat Server False
JSP Count Tomcat Server Web Module False
JSP Reload Count Tomcat Server Web Module False
JSP Unload Count Tomcat Server Web Module False
Servlet:<InstanceName>|Total Request Count Tomcat Server Web Module False
Servlet:<InstanceName>|Total Request Error Count Tomcat Server Web Module False
Servlet:<InstanceName>|Total Request Processing
Time
Tomcat Server Web Module False
Cache : Hit Count Tomcat Server Web Module False
Cache : Lookup Count Tomcat Server Web Module False
Current Thread Count Tomcat Server Global Request Processor True
Current Threads Busy Tomcat Server Global Request Processor True
errorRate Tomcat Server Global Request Processor False
Total Request Bytes Received Tomcat Server Global Request Processor False
Total Request Bytes Sent Tomcat Server Global Request Processor False
Total Request Count Tomcat Server Global Request Processor True
Total Request Error Count Tomcat Server Global Request Processor True
Total Request Processing Time Tomcat Server Global Request Processor False
Microsoft IIS Metrics
Metrics are collected for the Microsoft IIS application service.
Table 1275: IIS Metrics
Metric Name Category KPI
HTTP Service Request
Queues<InstanceName>AppPool|CurrentQueueSize
IIS HTTP Service Request Queues True
HTTP Service Request
Queues<InstanceName>AppPool|RejectedRequests
IIS HTTP Service Request Queues False
Web Services<InstanceName> Web Site|Bytes
Received
IIS Web Services False
Web Services<InstanceName> Web Site|Bytes Sent/
sec
IIS Web Services False
VMware by Broadcom  4374

---
## page 4375

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Web Services<InstanceName> Web Site|Bytes Total/
sec
IIS Web Services False
Web Services<InstanceName> Web Site|Connection
Attempts/sec
IIS Web Services False
Web Services<InstanceName> Web Site|Current
Connections
IIS Web Services False
Web Services<InstanceName> Web Site|Get
Requests/sec
IIS Web Services False
Web Services<InstanceName> Web Site|Locked
Errors/sec
IIS Web Services False
Web Services<InstanceName> Web Site|Not Found
Errors/sec
IIS Web Services False
Web Services<InstanceName> Web Site|Post
Requests/sec
IIS Web Services False
Web Services<InstanceName> Web Site|Service
Uptime
IIS Web Services False
Web Services<InstanceName> Web Site|Total Bytes
Sent
IIS Web Services False
Web Services<InstanceName> Web Site|Total Get
Requests
IIS Web Services True
Web Services<InstanceName> Web Site|Total Post
Requests
IIS Web Services True
Web Services<InstanceName> Web Site|Total Put
Requests
IIS Web Services False
Current File Cache Memory Usage (bytes) IIS Web Services Cache False
File Cache Hits Percent (%) IIS Web Services Cache False
Kernel URI Cache Hits Percent (%) IIS Web Services Cache False
Kernel URI Cache Misses IIS Web Services Cache False
Total Flushed URIs IIS Web Services Cache False
URI Cache Hits IIS Web Services Cache False
URI Cache Hits Percent (%) IIS Web Services Cache False
URI Cache Misses IIS Web Services Cache False
ASP.NET<InstanceName>|Application Restarts IIS ASP.NET True
ASP.NET<InstanceName>|Request Wait Time IIS ASP.NET True
ASP.NET<InstanceName>|Requests Current IIS ASP.NET True
ASP.NET<InstanceName>|Requests Queued IIS ASP.NET True
ASP.NET<InstanceName>|Requests Rejected IIS ASP.NET True
MS.NET<InstanceName>|Allocated Bytes/sec MS.NET True
MS.NET<InstanceName>|Current Queue Length MS.NET False
MS.NET<InstanceName>|Finalization Survivors MS.NET False
VMware by Broadcom  4375

---
## page 4376

 VMware Cloud Foundation 9.0
Metric Name Category KPI
MS.NET<InstanceName>|Gen 0 Collections MS.NET False
MS.NET<InstanceName>|Gen 0 heap size MS.NET False
MS.NET<InstanceName>|Gen 1 Collections MS.NET False
MS.NET<InstanceName>|Gen 1 heap size MS.NET False
MS.NET<InstanceName>|Gen 2 Collections MS.NET False
MS.NET<InstanceName>|Gen 2 heap size MS.NET False
MS.NET<InstanceName>|IL Bytes Jitted / sec MS.NET False
MS.NET<InstanceName>|Induced GC MS.NET False
MS.NET<InstanceName>|Large Object Heap size MS.NET False
MS.NET<InstanceName>|No of current logical
Threads
MS.NET True
MS.NET<InstanceName>|No of current physical
Threads
MS.NET True
MS.NET<InstanceName>|No of current recognized
threads
MS.NET False
MS.NET<InstanceName>|No of Exceps Thrown / sec MS.NET True
MS.NET<InstanceName>|No of total recognized
threads
MS.NET False
MS.NET<InstanceName>|Percent Time in Jit MS.NET False
MS.NET<InstanceName>|Pinned Objects MS.NET False
MS.NET<InstanceName>|Stack Walk Depth MS.NET False
MS.NET<InstanceName>|Time in RT checks MS.NET False
MS.NET<InstanceName>|Time Loading MS.NET True
MS.NET<InstanceName>|Total No of Contentions MS.NET False
MS.NET<InstanceName>|Total Runtime Checks MS.NET True
Application Availability Microsoft IIS False
Java Application Metrics
Metrics are collected for the Java application service.
Table 1276: Java Application Metrics
Metric Name Category KPI
Buffer Pool<InstanceName>|Count Java Application False
Buffer Pool<InstanceName>|Memory Used Java Application False
Buffer Pool<InstanceName>|Total Capacity Java Application False
Class Loading|Loaded Class Count Java Application True
Class Loading|Total Loaded Class Count Java Application False
Class Loading|Unloaded Class Count Java Application False
VMware by Broadcom  4376

---
## page 4377

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Garbage Collection<InstanceName>|Total Collection
Count
Java Application False
Garbage Collection<InstanceName>|Total Collection
Time
Java Application False
JVM Memory|Heap Memory Usage|Committed
Memory
Java Application False
JVM Memory|Heap Memory Usage|Initial Memory Java Application False
JVM Memory|Heap Memory Usage|Maximum
Memory
Java Application False
JVM Memory|Heap Memory Usage|Used Memory Java Application False
JVM Memory|JVM Memory Pool<InstanceName>|
Peak Usage|Committed Memory
Java Application False
JVM Memory|JVM Memory Pool<InstanceName>|
Peak Usage|Initial Memory
Java Application False
JVM Memory|JVM Memory Pool<InstanceName>|
Peak Usage|Maximum Memory
Java Application False
JVM Memory|JVM Memory Pool<InstanceName>|
Peak Usage|Used Memory
Java Application False
JVM Memory|JVM Memory Pool<InstanceName>|
Usage|Committed Memory
Java Application False
JVM Memory|JVM Memory Pool<InstanceName>|
Usage|Initial Memory
Java Application False
JVM Memory|JVM Memory Pool<InstanceName>|
Usage|Maximum Memory
Java Application False
JVM Memory|JVM Memory Pool<InstanceName>|
Usage|Used Memory
Java Application False
JVM Memory|Non Heap Memory Usage|Committed
Memory
Java Application False
JVM Memory|Non Heap Memory Usage|Initial
Memory
Java Application False
JVM Memory|Non Heap Memory Usage|Maximum
Memory
Java Application False
JVM Memory|Non Heap Memory Usage|Used
Memory
Java Application False
JVM Memory|Object Pending Finalization Count Java Application False
Uptime Java Application True
Threading|Thread Count Java Application True
Process CPU Usage % Java Application False
System CPU Usage % Java Application False
System Load Average % Java Application False
VMware by Broadcom  4377

---
## page 4378

 VMware Cloud Foundation 9.0
JBoss Server Metrics
Metrics are collected for the JBoss Server application service.
Table 1277: JBoss Server Metrics
Metric Name Category KPI
Buffer Pool<InstanceName>|Count Jboss Server False
Buffer Pool<InstanceName>|Memory Used Jboss Server False
Buffer Pool<InstanceName>|Total Capacity Jboss Server False
Class Loading|Loaded Class Count Jboss Server False
Class Loading|Total Loaded Class Count Jboss Server False
Class Loading|Unloaded Class Count Jboss Server False
File Descriptor Usage|Max File Descriptor Count Jboss Server False
File Descriptor Usage|Open File Descriptor Count Jboss Server False
Http Listener<InstanceName>|Bytes Received Jboss Server False
Http Listener<InstanceName>|Bytes Sent Jboss Server False
Http Listener<InstanceName>|Error Count Jboss Server False
Http Listener<InstanceName>|Request Count Jboss Server False
Https Listener<InstanceName>|Bytes Received Jboss Server False
Https Listener<InstanceName>|Bytes Sent Jboss Server False
Https Listener<InstanceName>|Error Count Jboss Server False
Https Listener<InstanceName>|Request Count Jboss Server False
Process CPU Usage (%) Jboss Server False
System CPU Usage (%) Jboss Server False
System Load Average (%) Jboss Server False
Threading|Daemon Thread Count Jboss Server False
Threading|Peak Thread Count Jboss Server False
Threading|Thread Count Jboss Server False
Threading|Total Started Thread Count Jboss Server False
Uptime Jboss Server False
UTILIZATION|Heap Memory Usage Jboss Server False
Application Availability Jboss Server False
Garbage Collection<InstanceName>|Total Collection
Count
Jboss JVM Garbage Collector False
Garbage Collection<InstanceName>|Total Collection
Time
Jboss JVM Garbage Collector False
JVM Memory|Heap Memory Usage|Committed
Memory
Jboss JVM Memory False
JVM Memory|Heap Memory Usage|Initial Memory Jboss JVM Memory False
VMware by Broadcom  4378

---
## page 4379

 VMware Cloud Foundation 9.0
Metric Name Category KPI
JVM Memory|Heap Memory Usage|Maximum
Memory
Jboss JVM Memory False
JVM Memory|Heap Memory Usage|Used Memory Jboss JVM Memory True
JVM Memory|Non Heap Memory Usage|Committed
Memory
Jboss JVM Memory False
JVM Memory|Non Heap Memory Usage|Initial
Memory
Jboss JVM Memory False
JVM Memory|Non Heap Memory Usage|Maximum
Memory
Jboss JVM Memory False
JVM Memory|Non Heap Memory Usage|Used
Memory
Jboss JVM Memory False
JVM Memory|Object Pending Finalization Count Jboss JVM Memory True
UTILIZATION|Active Count Jboss Datasource Pool False
UTILIZATION|Available Count Jboss Datasource Pool False
JVM Memory Pool<InstanceName>|Collection
Usage|Committed Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Collection
Usage|Initial Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Collection
Usage|Used Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Collection
Usage|Maximum Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Peak Usage|
Committed Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Peak Usage|
Initial Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Peak Usage|
Maximum Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Peak Usage|
Used Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Usage|
Committed Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Usage|Initial
Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Usage|Maximum
Memory
Jboss JVM Memory Pool False
JVM Memory Pool<InstanceName>|Usage|Used
Memory
Jboss JVM Memory Pool False
HyperV Metrics
Metrics are collected for the HyperV application service.
VMware by Broadcom  4379

---
## page 4380

 VMware Cloud Foundation 9.0
Table 1278: HyperV Metrics
Metric Name Category KPI
VM:Hyper-V Virtual Machine Health Summary|Health
Critical
HyperV False
VM<instanceName>|Physical Memory HyperV False
VM<instanceName>Hv VP 0|Total Run Time HyperV False
VM<instanceName>|Bytes Received HyperV False
VM<instanceName>|Bytes Sent HyperV False
VM<instanceName>|Error Count HyperV False
VM<instanceName>|Latency HyperV False
VM<instanceName>|Queue Length HyperV False
VM<instanceName>|Throughput HyperV False
CPU<instanceName>|Idle Time HyperV True
CPU<instanceName>|Processor Time HyperV True
CPU<instanceName>|User Time HyperV True
Disk<instanceName>|Avg Disk Queue Length HyperV False
Disk<instanceName>|Idle Time HyperV False
Disk<instanceName>|Read Time HyperV True
Disk<instanceName>|Write Time HyperV True
Process<instanceName>|Private Bytes HyperV False
Process<instanceName>|Processor Time HyperV False
Process<instanceName>|Thread Count HyperV False
Process<instanceName>|User Time HyperV False
System|Processes HyperV False
System|Processor Queue Length HyperV False
System|System UpTime HyperV False
Memory|Available Bytes HyperV False
Memory|Cache Bytes HyperV False
Memory|Cache Faults HyperV False
Memory|Pages HyperV False
Network<instanceName>|Packets Outbound Error HyperV False
Network<instanceName>|Packets Received Error HyperV False
Application Availability HyperV False
Oracle DB Metrics
Metrics are collected for the Oracle DB application service.
Oracle DB cannot be activated on Linux platforms.
VMware by Broadcom  4380

---
## page 4381

 VMware Cloud Foundation 9.0
Table 1279: Oracle DB Metrics
Metric Name Category KPI
Utilization|Active Sessions OracleDB True
Utilization|Buffer CacheHit Ratio OracleDB False
Utilization|Cursor CacheHit Ratio OracleDB False
Utilization|Database Wait Time OracleDB False
Utilization|Disk Sort persec OracleDB False
Utilization|Enqueue Timeouts Persec OracleDB False
Utilization|Global Cache Blocks Corrupted OracleDB False
Utilization|Global Cache Blocks Lost OracleDB False
Utilization|Library CacheHit Ratio OracleDB False
Utilization|Logon persec OracleDB True
Utilization|Memory Sorts Ratio OracleDB True
Utilization|Rows persort OracleDB False
Utilization|Service Response Time OracleDB False
Utilization|Session Count OracleDB True
Utilization|Session Limit OracleDB False
Utilization|Shared Pool Free OracleDB False
Utilization|Temp Space Used OracleDB False
Utilization|Total Sorts persec OracleDB False
Utilization|Physical Read Bytes Persc OracleDB False
Utilization|Physical Read IO Requests Persc OracleDB False
Utilization|Physical Read Total Bytes Persec OracleDB False
Utilization|Physical Reads Persec OracleDB True
Utilization|Physical Reads Per Txn OracleDB False
Utilization|Physical Write Bytes Persc OracleDB False
Utilization|Physical Write IO Requests Persc OracleDB False
Utilization|Physical Write Total Bytes Persc OracleDB False
Utilization|Physical Writes Persc OracleDB True
Utilization|Physical Writes Per Txn OracleDB False
Utilization|User Commits Percentage OracleDB False
Utilization|User Commits Persc OracleDB False
Utilization|User Rollbacks Percentage OracleDB False
Utilization|User Rollbacks persec OracleDB True
Utilization|User Transaction Persec OracleDB False
Utilization|Database Time Persc OracleDB False
Application Availability Oracle DB False
Cassandra Metrics
Metrics are collected for the Cassandra application service.
VMware by Broadcom  4381

---
## page 4382

 VMware Cloud Foundation 9.0
Table 1280: Cassandra Metrics
Metric Name Category KPI
Cache<InstanceName>|Capacity Cassandra False
Cache<InstanceName>|Entries Cassandra True
Cache<InstanceName>|HitRate Cassandra True
Cache<InstanceName>|Requests Cassandra True
Cache<InstanceName>|Size Cassandra False
ClientRequest<InstanceName>|Failures Cassandra False
ClientRequest<InstanceName>|Latency Cassandra False
ClientRequest<InstanceName>|Timeouts Cassandra False
ClientRequest<InstanceName>|Total Latency Cassandra False
ClientRequest<InstanceName>|Unavailables Cassandra False
CommitLog|Pending Tasks Cassandra False
CommitLog|Total Commit Log Size Cassandra False
Compaction|Bytes Compacted Cassandra False
Compaction|Completed Tasks Cassandra False
Compaction|Pending Tasks Cassandra False
Compaction|Total Compactions Completed Cassandra False
Connected Native Clients Cassandra False
HeapMemoryUsage|committed Cassandra False
HeapMemoryUsage|init Cassandra False
HeapMemoryUsage|max Cassandra False
HeapMemoryUsage|used Cassandra False
NonHeapMemoryUsage|committed Cassandra False
NonHeapMemoryUsage|init Cassandra False
NonHeapMemoryUsage|max Cassandra False
NonHeapMemoryUsage|used Cassandra False
ObjectPendingFinalizationCount Cassandra False
Storage|Exceptions Count Cassandra False
Storage|Load Count Cassandra False
Table<InstanceName>|Coordinator Read Latency Cassandra False
Table<InstanceName>|Live Diskspace Used Cassandra False
Table<InstanceName>|Read Latency Cassandra False
Table<InstanceName>|Total Diskspace Used Cassandra False
Table<InstanceName>|Total Read Latency Cassandra False
Table<InstanceName>|Total Write Latency Cassandra False
Table<InstanceName>|Write Latency Cassandra False
VMware by Broadcom  4382

---
## page 4383

 VMware Cloud Foundation 9.0
Metric Name Category KPI
ThreadPools<InstanceName>|Active Tasks Cassandra False
ThreadPools<InstanceName>|Currently Blocked
Tasks
Cassandra False
ThreadPools<InstanceName>|Pending Tasks Cassandra False
Application Availability Cassandra False
MongoDB Metrics
Metrics are collected for the MongoDB application service.
Table 1281: MongoDB Metrics
Metric Name Category KPI
UTILIZATION|Active Reads MongoDB True
UTILIZATION|Active Writes MongoDB True
UTILIZATION|Connections Available MongoDB False
UTILIZATION|Connections Total Created MongoDB False
UTILIZATION|Current Connections MongoDB True
UTILIZATION|Cursor Timed Out MongoDB True
UTILIZATION|Deletes Per Sec MongoDB False
UTILIZATION|Document Inserted MongoDB False
UTILIZATION|Document Deleted MongoDB False
UTILIZATION|Flushes Per Sec MongoDB False
UTILIZATION|Inserts Per Sec MongoDB False
UTILIZATION|Net Input Bytes MongoDB False
UTILIZATION|Open Connections MongoDB True
UTILIZATION|Page Faults Per Second MongoDB False
UTILIZATION|Net Output Bytes MongoDB False
UTILIZATION|Queries Per Sec MongoDB False
UTILIZATION|Queued Reads MongoDB True
UTILIZATION|Queued Writes MongoDB True
UTILIZATION|Total Available MongoDB False
UTILIZATION|Total Deletes Per Sec MongoDB False
UTILIZATION|Total Passes Per Sec MongoDB False
UTILIZATION|Total Refreshing MongoDB False
UTILIZATION|Updates Per Sec MongoDB False
UTILIZATION|Volume Size MB MongoDB False
Application Availability MongoDB False
UTILIZATION|Collection Stats MongoDB DataBases False
VMware by Broadcom  4383

---
## page 4384

 VMware Cloud Foundation 9.0
Metric Name Category KPI
UTILIZATION|Data Index Stats MongoDB DataBases True
UTILIZATION|Data Indexes MongoDB DataBases False
UTILIZATION|Data Size Stats MongoDB DataBases True
UTILIZATION|Average Object Size stats MongoDB DataBases False
UTILIZATION|Num Extents Stats MongoDB DataBases False
MS Exchange Metrics
Metrics are collected for the MS Exchange application service.
Table 1282: MS Exchange Metrics
Metric Name Category KPI
Active Manager Server|Active Manager Role MS Exchange False
Active Manager Server|Database State Info Writes
per second
MS Exchange False
Active Manager Server|GetServerForDatabase
Server-Side Calls
MS Exchange False
Active Manager Server|Server-Side Calls per second MS Exchange True
Active Manager Server|Total Number of Databases MS Exchange True
ActiveSync|Average Request Time MS Exchange True
ActiveSync|Current Requests MS Exchange False
ActiveSync|Mailbox Search Total MS Exchange False
ActiveSync|Ping Commands Pending MS Exchange False
ActiveSync|Requests per second MS Exchange True
ActiveSync|Sync Commands per second MS Exchange True
ASP.NET|Application Restarts MS Exchange False
ASP.NET|Request Wait Time MS Exchange True
ASP.NET|Worker Process Restarts MS Exchange False
Autodiscover Service|Requests per second MS Exchange True
Availability Service|Average Time to Process a Free
Busy Request
MS Exchange True
Outlook Web Access|Average Search Time MS Exchange True
Outlook Web Access|Requests per second MS Exchange False
Outlook Web Access|Current Unique Users MS Exchange False
Application Availability MS Exchange False
Performance|Database Cache Hit (%) MS Exchange Database False
Performance|Database Page Fault Stalls per second MS Exchange Database True
Performance|I/O Database Reads Average Latency MS Exchange Database True
Performance|I/O Database Writes Average Latency MS Exchange Database True
VMware by Broadcom  4384

---
## page 4385

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Performance|I/O Log Reads Average Latency MS Exchange Database False
Performance|I/O Log Writes Average Latency MS Exchange Database False
Performance|Log Record Stalls per second MS Exchange Database False
Performance|Log Threads Waiting MS Exchange Database False
Performance|I/O Database Reads Average Latency MS Exchange Database Instance False
Performance|I/O Database Writes Average Latency MS Exchange Database Instance False
Performance|Log Record Stalls per second MS Exchange Database Instance False
Performance|Log Threads Waiting MS Exchange Database Instance False
Performance|LDAP Read Time MS Exchange Domain Controller False
Performance|LDAP Search Time MS Exchange Domain Controller False
Performance|LDAP Searches Timed Out per minute MS Exchange Domain Controller False
Performance|Long Running LDAP Operations per
minute
MS Exchange Domain Controller False
Performance|Connection Attempts per second MS Exchange Web Server True
Performance|Current Connections MS Exchange Web Server False
Performance|Other Request Methods per second MS Exchange Web Server False
Process|Handle Count MS Exchange Windows Service False
Process|Memory Allocated MS Exchange Windows Service False
Process|Processor Time (%) MS Exchange Windows Service True
Process|Thread Count MS Exchange Windows Service False
Process|Virtual Memory Used MS Exchange Windows Service False
Process|Working Set MS Exchange Windows Service False
 Microsoft SQL Server Metrics
Metrics are collected for the Microsoft SQL Server application service.
Table 1283: MS SQL Metrics
Metric Name Category KPI
CPU<InstanceName>|CPU Usage (%) Microsoft SQL Server False
Database IO|Rows Reads Bytes/Sec Microsoft SQL Server False
Database IO|Rows Reads/Sec Microsoft SQL Server False
Database IO|Rows Writes Bytes/Sec Microsoft SQL Server False
Database IO|Rows Writes/Sec Microsoft SQL Server False
Performance|Access Methods|Full Scans per second Microsoft SQL Server False
Performance|Access Methods|Index Searches Microsoft SQL Server False
Performance|Access Methods|Page Splits per
second
Microsoft SQL Server False
VMware by Broadcom  4385

---
## page 4386

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Performance|Broker Activation|Stored Procedures
Invoked per second
Microsoft SQL Server False
Performance|Buffer Manager|Buffer cache hit ratio
(%)
Microsoft SQL Server True
Performance|Buffer Manager|Checkpoint Pages/sec Microsoft SQL Server True
Performance|Buffer Manager|Lazy writes per second Microsoft SQL Server True
Performance|Buffer Manager|Page life expectancy Microsoft SQL Server True
Performance|Buffer Manager|Page lookups per
second
Microsoft SQL Server False
Performance|Buffer Manager|Page reads per second Microsoft SQL Server False
Performance|Buffer Manager|Page writes per second Microsoft SQL Server False
Performance|Databases|Active Transactions Microsoft SQL Server True
Performance|Databases|Data File(s) Size Microsoft SQL Server True
Performance|Databases|Log Bytes Flushed/Sec Microsoft SQL Server False
Performance|Databases|Log File(s) Size Microsoft SQL Server False
Performance|Databases|Log File(s) Used Size Microsoft SQL Server False
Performance|Databases|Log Flush Wait Time Microsoft SQL Server False
Performance|Databases|Log Flushes per second Microsoft SQL Server False
Performance|Databases|Transactions per second Microsoft SQL Server False
Performance|Databases|Write Transactions per
second
Microsoft SQL Server False
Performance|Databases|XTP Memory Used Microsoft SQL Server False
Performance|General Statistics|Active temp Tables Microsoft SQL Server False
Performance|General Statistics|Logins per second Microsoft SQL Server False
Performance|General Statistics|Logouts per second Microsoft SQL Server False
Performance|General Statistics|Processes Blocked Microsoft SQL Server False
Performance|General Statistics|Temp Tables
Creation Rate
Microsoft SQL Server False
Performance|General Statistics|User Connections Microsoft SQL Server False
Performance|Locks|Average Wait Time Microsoft SQL Server False
Performance|Locks|Lock Requests per second Microsoft SQL Server False
Performance|Locks|Lock Wait Time Microsoft SQL Server True
Performance|Locks|Lock Waits per second Microsoft SQL Server True
Performance|Locks|Number of Deadlocks per
second
Microsoft SQL Server True
Performance|Memory Manager|Connection Memory Microsoft SQL Server False
Performance|Memory Manager|Lock Memory Microsoft SQL Server False
Performance|Memory Manager|Log Pool Memory Microsoft SQL Server False
VMware by Broadcom  4386

---
## page 4387

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Performance|Memory Manager|Memory Grants
Pending
Microsoft SQL Server True
Performance|Memory Manager|SQL Cache Memory Microsoft SQL Server False
Performance|Memory Manager|Target Server
Memory
Microsoft SQL Server True
Performance|Memory Manager|Total Server Memory Microsoft SQL Server True
Performance|Resource Pool Stats|internal|Active
memory grant amount
Microsoft SQL Server False
Performance|Resource Pool Stats|internal|CPU
Usage Percentage (%)
Microsoft SQL Server False
Performance|Resource Pool Stats|internal|Disk Read
Bytes per second
Microsoft SQL Server False
Performance|Resource Pool Stats|internal|Disk Read
IO
Microsoft SQL Server False
Wait Stats:<InstanceName>|Wait Time (ms) Microsoft SQL Server False
Wait Stats<InstanceName>|Number of Waiting tasks
(ms)
Microsoft SQL Server False
Performance|Resource Pool Stats|internal|Disk Read
IO Throttled Per Second
Microsoft SQL Server False
Performance|Resource Pool Stats|internal|Disk Write
Bytes per second (Bps)
Microsoft SQL Server False
Performance|Resource Pool Stats|internal|Disk Write
IO Throttled per second
Microsoft SQL Server False
Performance|Resource Pool Stats|internal|Used
Memory
Microsoft SQL Server False
Performance|SQL Statistics | Batch Requests Per
Second
Microsoft SQL Server False
Performance|SQL Statistics | SQL Compilations per
second
Microsoft SQL Server False
Performance|SQL Statistics | SQL Re-Compilations
per second
Microsoft SQL Server False
Performance|Transactions | Free space in tempdb
(KB)
Microsoft SQL Server False
Performance|Transactions | Transactions Microsoft SQL Server False
Performance|Transactions | Version Store Size (KB) Microsoft SQL Server False
Performance|User Settable Counter | User Counter 0
to 10
Microsoft SQL Server False
Performance|Workload Group Stats|internal|Active
Requests
Microsoft SQL Server False
Performance|Workload Group Stats|internal|Blocked
Tasks
Microsoft SQL Server False
VMware by Broadcom  4387

---
## page 4388

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Performance|Workload Group Stats|internal|CpU
Usage (%)
Microsoft SQL Server False
Performance|Workload Group Stats|internal|Queued
Requests
Microsoft SQL Server False
Performance|Workload Group Stats|internal|Request
Completed/sec
Microsoft SQL Server False
Application Availability Microsoft SQL Server False
There are no metrics collected for Microsoft SQL Server Database.
MySQL Metrics
Metrics are collected for the MySQL application service.
Table 1284: MySQL Metrics
Metric Name Category KPI
Aborted connection count MySQL True
Connection count MySQL True
Event wait average time MySQL False
Event wait count MySQL False
Binary Files|Binary Files Count MySQL False
Binary Files|Binary Size Bytes MySQL False
Global Status|Aborted Clients MySQL False
Global Status|Binlog Cache Disk Use MySQL False
Global Status|Bytes Received MySQL False
Global Status|Bytes Sent MySQL False
Global Status|Connection Errors Accept MySQL False
Global Status|Connection Errors Internal MySQL False
Global Status|Connection Errors Max Connections MySQL False
Global Status|Queries MySQL False
Global Status|Threads Cached MySQL False
Global Status|Threads Connected MySQL False
Global Status|Threads Running MySQL False
Global Status|Uptime MySQL False
Global Variables|Delayed Insert Limit MySQL False
Global Variables|Delayed Insert Timeout MySQL False
Global Variables|Delayed Queue Size MySQL False
Global Variables|Max Connect Errors MySQL False
Global Variables|Max Connections MySQL False
Global Variables|Max Delayed Threads MySQL False
VMware by Broadcom  4388

---
## page 4389

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Global Variables|Max Error Count MySQL False
InnoDB|All deadlock count MySQL False
InnoDB|Buffer Pool Bytes Data MySQL False
InnoDB|Buffer Pool Bytes Data MySQL False
InnoDB|Buffer Pool Bytes Dirty MySQL False
InnoDB|Buffer Pool Dump Status MySQL False
InnoDB|Buffer Pool Load Status MySQL False
InnoDB|Buffer Pool Pages Data MySQL False
InnoDB|Buffer Pool Pages Dirty MySQL False
InnoDB|Buffer Pool Pages Flushed MySQL False
InnoDB|Buffer pool size MySQL True
InnoDB|Checksums MySQL False
InnoDB|Open file count MySQL False
InnoDB|Row lock average time MySQL False
InnoDB|Row lock current waits MySQL False
InnoDB|Row lock maximum time MySQL False
InnoDB|Row lock time MySQL False
InnoDB|Row lock waits MySQL True
InnoDB|Table lock count MySQL False
Performance Table IO Waits|IO Waits Total Delete MySQL False
Performance Table IO Waits|IO Waits Total Fetch MySQL False
Performance Table IO Waits|IO Waits Total Insert MySQL False
Performance Table IO Waits|IO Waits Total Update MySQL False
Process List|Connections MySQL False
Application Availability MySQL False
IO waits average time MySQL Database False
IO waits count MySQL Database True
Read high priority average time MySQL Database False
Read high priority count MySQL Database False
Write concurrent insert average time MySQL Database False
Write concurrent insert count MySQL Database False
NGINX Metrics
Metrics are collected for the NGINX application service.
VMware by Broadcom  4389

---
## page 4390

 VMware Cloud Foundation 9.0
Table 1285: NGINX Metrics
Metric Name Category KPI
HTTP Status Info|Accepts Nginx True
HTTP Status Info|Active connections Nginx False
HTTP Status Info|Handled Nginx True
HTTP Status Info|Reading Nginx False
HTTP Status Info|Requests Nginx False
HTTP Status Info|Waiting Nginx True
HTTP Status Info|Writing Nginx False
Application Availability Nginx False
Network Time Protocol Metrics
Metrics are collected for the Network Time Protocol application service.
Table 1286: Network Time Protocol Metrics
Metric Name Category KPI
NTPD |delay Network Time Protocol True
NTPD | jitter Network Time Protocol True
NTPD | offset Network Time Protocol True
NTPD | poll Network Time Protocol False
NTPD | reach Network Time Protocol True
NTPD | when Network Time Protocol False
Application Availability Network Time Protocol False
Oracle WebLogic Server Metrics
Metrics are collected for the Oracle WebLogic Server application service.
Table 1287: Oracle WebLogic Server Metrics
Metric Name Category KPI
UTILIZATION|Process Cpu Load Oracle WebLogic Server True
UTILIZATION|System Cpu Load Oracle WebLogic Server False
UTILIZATION|System Load Average Oracle WebLogic Server False
Application Availability Oracle WebLogic Server False
UTILIZATION|Collection Time Weblogic Garbage Collector True
UTILIZATION|Connections HighCount Weblogic JMS Runtime True
UTILIZATION|JMS Servers TotalCount Weblogic JMS Runtime False
UTILIZATION|Active Total Count Used Weblogic JTA Runtime False
VMware by Broadcom  4390

---
## page 4391

 VMware Cloud Foundation 9.0
Metric Name Category KPI
UTILIZATION|Active Transactions TotalCount Weblogic JTA Runtime False
UTILIZATION|Transaction Abandoned TotalCount Weblogic JTA Runtime True
UTILIZATION|Transaction RolledBack App
TotalCount
Weblogic JTA Runtime True
UTILIZATION|Heap Memory Usage Weblogic JVM Memory True
UTILIZATION|Non Heap Memory Usage Weblogic JVM Memory False
UTILIZATION|Peak Usage Weblogic JVM Memory Pool True
UTILIZATION|Usage Weblogic JVM Memory Pool False
UTILIZATION|UpTime Weblogic JVM Runtime False
Pivotal TC Server Metrics
Metrics are collected for the Pivotal TC Server application service.
Table 1288: Pivotal TC Server Metrics
Metric Name Category KPI
Buffer Pool<InstanceName>|Count Pivotal TC Server False
Buffer Pool<InstanceName>|Memory Used Pivotal TC Server False
Buffer Pool<InstanceName>|Total Capacity Pivotal TC Server False
Class Loading|Loaded Class Count Pivotal TC Server False
Class Loading|Total Loaded Class Count Pivotal TC Server False
Class Loading|Unloaded Class Count Pivotal TC Server False
File Descriptor Usage|Max File Descriptor Count Pivotal TC Server False
File Descriptor Usage|Open File Descriptor Count Pivotal TC Server False
Garbage Collection:<InstanceName>|Total Collection
Count
Pivotal TC Server False
Garbage Collection:<InstanceName>|Total Collection
Time
Pivotal TC Server False
Process CPU Usage (%) Pivotal TC Server True
JVM Memory|Heap Memory Usage|Committed
Memory
Pivotal TC Server True
JVM Memory|Heap Memory Usage|Initial Memory Pivotal TC Server False
JVM Memory|Heap Memory Usage|Maximum
Memory
Pivotal TC Server False
JVM Memory|Heap Memory Usage|Used Memory Pivotal TC Server True
JVM Memory|Non Heap Memory Usage|Committed
Memory
Pivotal TC Server True
JVM Memory|Non Heap Memory Usage|Initial
Memory
Pivotal TC Server False
VMware by Broadcom  4391

---
## page 4392

 VMware Cloud Foundation 9.0
Metric Name Category KPI
JVM Memory|Non Heap Memory Usage|Maximum
Memory
Pivotal TC Server False
JVM Memory|Non Heap Memory Usage|Used
Memory
Pivotal TC Server True
JVM Memory|Number of Object Pending Finalization
Count
Pivotal TC Server True
JVM Memory|Pool:<InstanceName>|Peak Usage|
Committed Memory
Pivotal TC Server False
JVM Memory|Pool:<InstanceName>|Peak Usage|
Initial Memory
Pivotal TC Server False
JVM Memory|Pool:<InstanceName>|Peak Usage|
Maximum Memory
Pivotal TC Server False
JVM Memory|Pool:<InstanceName>|Peak Usage|
Used Memory
Pivotal TC Server False
JVM Memory|Pool:<InstanceName>|Usage|
Committed Memory
Pivotal TC Server False
JVM Memory|Pool:<InstanceName>|Usage|Initial
Memory
Pivotal TC Server False
JVM Memory|Pool:<InstanceName>|Usage|
Maximum Memory
Pivotal TC Server False
JVM Memory|Pool:<InstanceName>|Usage|Used
Memory
Pivotal TC Server False
Process CPU Usage (%) Pivotal TC Server True
System CPU Usage (%) Pivotal TC Server True
Uptime Pivotal TC Server True
Threading|Thread Count Pivotal TC Server False
System Load Average Pivotal TC Server False
Application Availability Pivotal TC Server False
Current Thread Count Pivotal TC Server Thread Pool False
Current Threads Busy Pivotal TC Server Thread Pool True
Total Request Bytes Received Pivotal TC Server Thread Pool False
Total Request Bytes Sent Pivotal TC Server Thread Pool False
Total Request Count Pivotal TC Server Thread Pool True
Total Request Error Count Pivotal TC Server Thread Pool True
Total Request Processing Time Pivotal TC Server Thread Pool True
JSP Count Pivotal TC Server Web Module False
JSP Reload Count Pivotal TC Server Web Module False
JSP Unload Count Pivotal TC Server Web Module False
PostgreSQL
Metrics are collected for the PostgreSQL application service.
VMware by Broadcom  4392

---
## page 4393

 VMware Cloud Foundation 9.0
Table 1289: PostgreSQL
Metric Name Category KPI
Buffers|Buffers Allocated PostgreSQL False
Buffers|Buffers Written by Backend PostgreSQL True
Buffers|Buffers Written by Background Writer PostgreSQL True
Buffers|Buffers Written During Checkpoints PostgreSQL True
Buffers|fsync Call Executed by Backend PostgreSQL False
Checkpoints|Checkpoints sync time PostgreSQL False
Checkpoints|Checkpoints write time PostgreSQL False
Checkpoints|Requested checkpoints performed
count
PostgreSQL False
Checkpoints|Scheduled checkpoints performed count PostgreSQL False
Clean scan stopped count PostgreSQL False
Application Availability PostgreSQL False
Disk Blocks|Blocks Cache Hits PostgreSQL Database False
Disk Blocks|Blocks Read PostgreSQL Database False
Disk Blocks|Blocks Read Time PostgreSQL Database False
Disk Blocks|Blocks Write Time PostgreSQL Database False
Statistics|Backends Connected PostgreSQL Database False
Statistics|Data Written by Queries PostgreSQL Database True
Statistics|Deadlocks Detected PostgreSQL Database True
Statistics|Queries Cancelled PostgreSQL Database True
Statistics|Temp Files Created by Queries PostgreSQL Database False
Transactions|Transactions Committed PostgreSQL Database True
Transactions|Transactions Rolled Back PostgreSQL Database True
Tuples|Tuples Deleted PostgreSQL Database True
Tuples|Tuples Fetched PostgreSQL Database True
Tuples|Tuples Inserted PostgreSQL Database True
Tuples|Tuples Returned PostgreSQL Database True
Tuples|Tuples Updated PostgreSQL Database True
RabbitMQ Metrics
Metrics are collected for the RabbitMQ application service.
Table 1290: RabbitMQ Metrics
Metric Name Category KPI
CPU|Limit RabbitMQ False
CPU|Used RabbitMQ True
VMware by Broadcom  4393

---
## page 4394

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Disk|Free RabbitMQ False
Disk|Free limit RabbitMQ False
FileDescriptor|Total RabbitMQ False
FileDescriptor|Used RabbitMQ False
Memory|Limit RabbitMQ False
Memory|Used RabbitMQ True
Messages|Acked RabbitMQ False
Messages|Delivered RabbitMQ False
Messages|Delivered get RabbitMQ False
Messages|Published RabbitMQ False
Messages|Ready RabbitMQ False
Messages|Unacked RabbitMQ False
Socket|Limit RabbitMQ False
Socket|Used RabbitMQ True
UTILIZATION|Channels RabbitMQ True
UTILIZATION|Connections RabbitMQ True
UTILIZATION|Consumers RabbitMQ True
UTILIZATION|Exchanges RabbitMQ True
UTILIZATION|Messages RabbitMQ True
UTILIZATION|Queues RabbitMQ True
Application Availability RabbitMQ False
Messages|Publish in RabbitMQ Exchange False
Messages|Publish out RabbitMQ Exchange False
Consumer Utilisation RabbitMQ Queue False
Consumers RabbitMQ Queue False
Memory RabbitMQ Queue False
Messages|Ack RabbitMQ Queue False
Messages|Ack rate RabbitMQ Queue False
Messages|Deliver RabbitMQ Queue False
Messages|Deliver get RabbitMQ Queue False
Messages|Persist RabbitMQ Queue False
Messages|Publish RabbitMQ Queue False
Messages|Publish rate RabbitMQ Queue False
Messages|Ram RabbitMQ Queue False
Messages|Ready RabbitMQ Queue False
Messages|Redeliver RabbitMQ Queue False
Messages|Redeliver rate RabbitMQ Queue False
VMware by Broadcom  4394

---
## page 4395

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Messages|Space RabbitMQ Queue False
Messages|Unack RabbitMQ Queue False
Messages|Unacked RabbitMQ Queue False
Messages RabbitMQ Queue False
There are no metrics collected for RabbitMQ Virtual Host.
Riak KV Metrics
Metrics are collected for the Riak KV application service.
Table 1291: Riak KV Metrics
Metric Name Category KPI
UTILIZATION|CPU Average Riak KV False
UTILIZATION|Memory Processes Riak KV False
UTILIZATION|Memory Total Riak KV False
UTILIZATION|Node GETs Riak KV True
UTILIZATION|Node GETs Total Riak KV False
UTILIZATION|Node PUTs Riak KV True
UTILIZATION|Node PUTs Total Riak KV False
UTILIZATION|PBC Active Riak KV True
UTILIZATION|PBC Connects Riak KV True
UTILIZATION|Read Repairs Riak KV True
UTILIZATION|vNODE Index Reads Riak KV True
UTILIZATION|vNODE Index Writes Riak KV True
Application Availability Riak KV False
SharePoint Metrics
Metrics are collected for the SharePoint Server application service.
Table 1292: SharePoint Server Metrics
Metric Name Category KPI
Sharepoint Foundation|Active Threads SharePoint Server True
Sharepoint Foundation|Current Page Requests SharePoint Server False
Sharepoint Foundation|Executing SQL Queries SharePoint Server False
Sharepoint Foundation|Executing Time/Page
Request
SharePoint Server True
Sharepoint Foundation|Incoming Page Requests
Rate
SharePoint Server False
VMware by Broadcom  4395

---
## page 4396

 VMware Cloud Foundation 9.0
Metric Name Category KPI
Sharepoint Foundation|Object Cache Hit Count SharePoint Server False
Sharepoint Foundation|Reject Page Requests Rate SharePoint Server False
Sharepoint Foundation|Responded Page Requests
Rate
SharePoint Server True
SQL query executing time SharePoint Server False
Application Availability SharePoint Server False
Network|Received Data Rate SharePoint Web Server True
Network|Sent Data Rate SharePoint Web Server True
Process|Processor Time (%) SharePoint Windows Service False
Process|Threads SharePoint Windows Service False
WebSphere Metrics
Metrics are collected for the WebSphere application service.
Table 1293: WebSphere Metrics
Metric Name Category KPI
Thread Pool|Active Count|
Current
Thread Pool False
Thread Pool|Active Count|High Thread Pool False
Thread Pool|Active Count|Low Thread Pool False
Thread Pool|Active Count|Lower Thread Pool False
Thread Pool|Active Count|Upper Thread Pool False
JDBC|Close Count JDBC False
JDBC|Create Count JDBC False
JDBC|JDBC Pool Size|Average JDBC False
JDBC|JDBC Pool Size|Current JDBC False
JDBC|JDBC Pool Size|Lower JDBC False
JDBC|JDBC Pool Size|Upper JDBC False
Garbage
Collection<InstanceName>|Total
Collection Count
WebSphere False
Garbage
Collection<InstanceName>|Total
Collection Time
WebSphere False
JVM Memory|Heap Memory
Usage|Committed Memory
WebSphere False
JVM Memory|Heap Memory
Usage|Initial Memory
WebSphere False
JVM Memory|Heap Memory
Usage|Maximum Memory
WebSphere False
VMware by Broadcom  4396

---
## page 4397

 VMware Cloud Foundation 9.0
Metric Name Category KPI
JVM Memory|Heap Memory
Usage|Used Memory
WebSphere False
JVM Memory|Non Heap
Memory Usage|Committed
Memory
WebSphere False
JVM Memory|Non Heap
Memory Usage|Initial Memory
WebSphere False
JVM Memory|Non Heap
Memory Usage|Maximum
Memory
WebSphere False
JVM Memory|Non Heap
Memory Usage|Used Memory
WebSphere False
JVM Memory|Number of Object
Pending Finalization Count
WebSphere False
JVM Memory|
Pool<InstanceName>|Peak
Usage|Committed Memory
WebSphere False
JVM Memory|
Pool<InstanceName>|Peak
Usage|Initial Memory
WebSphere False
JVM Memory|
Pool<InstanceName>|Peak
Usage|Maximum Memory
WebSphere False
JVM Memory|
Pool<InstanceName>|Peak
Usage|Used Memory
WebSphere False
JVM Memory|
Pool<InstanceName>|Usage|
Committed Memory
WebSphere False
JVM Memory|
Pool<InstanceName>|Usage|
Initial Memory
WebSphere False
JVM Memory|
Pool<InstanceName>|Usage|
Maximum Memory
WebSphere False
JVM Memory|
Pool<InstanceName>|Usage|
Used Memory
WebSphere False
Process Cpu Load WebSphere False
System Cpu Load WebSphere False
System Load Average WebSphere False
Application Availability WebSphere False
VMware by Broadcom  4397

---
## page 4398

 VMware Cloud Foundation 9.0
Windows Service Metrics
Metrics are collected for Windows services.
Table 1294: Windows Service Metrics
Metric Name Category KPI
AVAILABILITY|Resource Availability Services False
UTILIZATION|Memory Usage(%) Services False
UTILIZATION|CPU Usage(%) Services False
Linux Process Metrics
Metrics are collected for Linux services.
Table 1295: Linux Process Metrics
Metric Name Category KPI
AVAILABILITY|Resource Availability Processes False
UTILIZATION|Memory Usage (%) Processes False
UTILIZATION|CPU Usage (%) Processes False
UTILIZATION|Number of Processes Processes False
Remote Check Metrics
Metrics are collected for object types such as HTTP, ICMP, TCP, and UDP.
HTTP Metrics
VCF Operations discovers metrics for HTTP remote checks.
HTTP Metrics
Table 1296: HTTP Metrics
Metric Name KPI
Availability False
Content Length False
Response Code False
Response Time True
Result Code False
ICMP Metrics
VCF Operations discovers metrics for the ICMP object type.
VMware by Broadcom  4398

---
## page 4399

 VMware Cloud Foundation 9.0
Table 1297: ICMP Metrics
Metric Name KPI
Availability False
Average Response Time True
Packet Loss (%) False
Packets Received False
Packets Transmitted False
Result Code False
TCP Metrics
VCF Operations discovers metrics for the TCP object type.
Table 1298: TCP Metrics
Metric Name KPI
Availability False
Response Time True
Result Code False
UDP Metrics
VCF Operations discovers metrics for the UDP object type.
Table 1299: UDP Metrics
Metric Name KPI
Availability False
Response Time True
Result Code False
VeloCloud Application Service Metrics
Metrics are collected for application services supported by VeloCloud.
VeloCloud Gateway Metrics
Metrics are collected for the VeloCloud Gateway.
Table 1300: VeloCloud Gateway Metrics
Component Metrics
DPDK DPDK:mbuf | pool free
NAT NAT | Active Flows (%)
VMware by Broadcom  4399

---
## page 4400

 VMware Cloud Foundation 9.0
Component Metrics
NAT | Active Flows
NAT | Active Routes
NAT | Active Routes Used (%)
NAT | Connected Peers
NAT | NAT Entries
NTP Server NTP Server:ntp.ubuntu.com | offset value
Summary | Active Tunnels Count (%)
Summary | Average Packets Dropped
Summary | Average wMarkDrop
Summary | BGP Enabled VRFs
Summary | BGP Neighbors
Summary | CLR Count
Summary | Connected Edges
Summary | NAT
Summary | SSH Failed Login
Summary | Unstable Path Percentage
Summary | VMCP CTRL Drop Count
Summary
Summary | VMCP TX Drop Count
VC Queue VC Queue | ipv4_bh packet drop
VCMP Tunnel | ctrl_0 packet drop
VCMP Tunnel | ctrl_1 packet drop
VCMP Tunnel | data_0 packet drop
VCMP Tunnel | data_1 packet drop
VCMP Tunnel
VCMP Tunnel | init packet drop
VeloCloud Orchestrator Metrics
Metrics are collected for the VeloCloud Orchestrator.
Table 1301: VeloCloud Orchestrator Metrics
Component Metrics
General | Free Memory (%)General
General | Status
Metrics - Ngnix
Metrics are collected for the VeloCloud Ngnix.
VMware by Broadcom  4400

---
## page 4401

 VMware Cloud Foundation 9.0
Table 1302: Ngnix Metrics
Component Metrics
HTTP Status Info | Accepts
HTTP Status Info | Active Connections
HTTP Status Info | Handled
HTTP Status Info | Reading
HTTP Status Info | Requests
HTTP Status Info | Waiting
HTTP Status Info
HTTP Status Info | Writing
Metrics - Redis
Metrics are collected for the VeloCloud Redis.
Table 1303: Redis Metrics
Component Metrics
Publish Subscribe. Publish Subscribe | Channels
Total | Commands ProcessedTotal
Total | Connections Received
Used | CPU
Used | Memory
Used
Used | Peak Memory
Metrics - ClickHouse
Metrics are collected for the VeloCloud Clickhouse.
Table 1304: Clickhouse Metrics
Component Metrics
Background Background | Pool Task
Buffers | Allocation (Bytes)
Buffers | Compressed Read Buffer (Bytes)
Buffers | Compressed Read Buffer Blocks
Buffers | IO Allocation (Bytes)
Buffers | Storage Buffer (Bytes)
Buffer
Buffers | Storage Buffer Rows
Events | Context Lock
Events | Disk Write Elapsed (µs)
Events
Events | File Open
VMware by Broadcom  4401

---
## page 4402

 VMware Cloud Foundation 9.0
Component Metrics
Events | Function Execute
Events | Hard Page Faults
Events | Lock Readers Wait (µs)
Events | OS IO wait (ms)
Events | OS Write (Bytes)
Events | Query
Events | Readers Wait (ms)
Events | Real Time
Events | Soft Page Faults (µs)
Events | System Time (µs)
Events | User Time (µs)
Global | Global ThreadGlobal Thread
Global | Global Thread Active
Local | Local ThreadLocal Thread
Local | Local Thread Active
Replicas | Max Absolute Delay
Replicas | Max Insert In Queue
Replicas | Max Merge In Queue
Replicas | Max Queue Size
Replicas | Max Relative Delay
Replicas | Total Insert In Queue
Replicas | Total Merge Queues
Replicas
Replicas | Total Queue Size
Summary | Background Pool Task
Summary | Dict Cache Requests
Summary | File Open Writes
Summary | Merge
Summary | Number of Databases
Summary | Number of Distributed Send
Summary | Number of Tables
Summary | Read
Summary | Replicated Checks
Summary | Storage Buffer Rows
Summary | Uncompressed Cache Cells
Summary | Uptime
Summary | Write
Summary
Summary | Zookeeper Session
VMware by Broadcom  4402

---
## page 4403

 VMware Cloud Foundation 9.0
Component Metrics
Summary | Zookeeper Watch
Write Buffer Write Buffer | File Descriptor Write
Replicated Replicated Fetch
Memory Memory Tracking
Query Query Thread
Service Discovery Metrics
Service discovery discovers metrics for several objects. It also discovers CPU and memory metrics for discovered
services.
Virtual Machine Metrics
Service Discovery discovers metrics for virtual machines.
Table 1305: Virtual Machine Metrics
Metric Name Description
Guest OS Services|Total Number of Services Number of out-of-the-box and user-defined services discovered in
the VM.
Guest OS Services|Number of User Defined Services Number of user-defined services discovered in the VM.
Guest OS Services|Number of OOTB Services Number of out-of-the-box services discovered in the VM.
Guest OS Services|Number of Outgoing Connections Number of outgoing connection counts from the discovered
services.
Guest OS Services|Number of Incoming Connections Number of incoming connection counts to the discovered services.
Service Summary Metrics
Service discovery discovers summary metrics for the service object. The object is a single service object.
Table 1306: Service Summary Metrics
Metric Name Description
Summary|Incoming Connections Count Number of incoming connections.
Summary|Outgoing Connections Count Number of outgoing connections.
Summary|Connections Count Number of incoming and outgoing connections.
Summary|Pid Process ID.
Service Performance Metrics
Service discovery discovers performance metrics for the service object. The object is a single service object.
VMware by Broadcom  4403

---
## page 4404

 VMware Cloud Foundation 9.0
Table 1307: Service Performance Metrics
Metric Name Description
Performance metrics group|CPU CPU usage in percentage.
Performance metrics group|Memory Memory usage in KB.
Performance metrics group|IO Read Throughput IO read throughput in KBps.
Performance metrics group|IO Write Throughput IO write throughput in KBps.
Service Type Metrics
Service discovery discovers metrics for service type objects.
Table 1308: Service Type Metrics
Metric Name Description
Number of instances Number of instances of this service type.
Calculated Metrics
VCF Operations calculates metrics for capacity, badges, and the health of the system. Calculated metrics apply to a
subset of objects found in the describe.xml file that describes each adapter.
From data that the vCenter adapter collects, VCF Operations calculates metrics for objects of type:
• vSphere World
• Virtual Machine
• Host System
• Datastore
From data that the VCF Operations adapter collects, VCF Operations calculates metrics for objects of type:
• Node
• Cluster
Capacity Analytics Generated Metrics
The capacity engine computes and publishes metrics that can be found in the Capacity Analytics Generated group. These
metrics help you to plan your resource use based on consumer demand.
Capacity Analytics Generated Metrics Group
Capacity analytics uses the capacity engine to analyze historical utilization and generate projected utilization. The engine
takes the Demand and Usable Capacity (Total Capacity - HA - buffer) metrics as input and calculates the output metrics
that belong to the capacity analytics generated metrics group.
The capacity analytics generated metrics group contains containers and each container contains three output metrics,
which are Capacity Remaining, Recommended Size, and Recommended Total Capacity. It also contains the Capacity
Remaining Percentage and Time Remaining metrics, which show the most constrained values of the containers.
VMware by Broadcom  4404

---
## page 4405

 VMware Cloud Foundation 9.0
For the capacity metrics group, full metric names include the name of the resource container. For example, if
recommended size metrics are computed for CPU or memory, the actual metric names appear as cpu|demand|
recommendedSize or mem|demand|recommendedSize.
Table 1309: Capacity Metrics Group
Metric Name Description
Time Remaining (Day(s)) The number of days remaining till the projected utilization crosses the threshold for the
usable capacity.
Key: timeRemaining
Capacity Remaining Capacity remaining is the maximum point between the usable capacity now and the
projected utilization for 3 days into the future. If the projected utilization is above 100% of
the usable capacity, Capacity Remaining is 0.
Key: capacityRemaining
Capacity Remaining Percentage (%) The percentage of Capacity Remaining of the most constrained resource with respect to
the usable capacity.
Key: capacityRemainingPercentage
Recommended Size The maximum projected utilization for the projection period from the current time to 30 days
after the warning threshold value for time remaining. The warning threshold is the period
during which the time remaining is green. Recommended Size excludes HA settings.
Key: recommendedSize
Recommended Total Capacity The maximum projected utilization for the projection period from the current time to 30
days after the warning threshold value for time remaining. Recommended Total Capacity
excludes HA settings.
Key: recommendedTotalCapacity
Capacity Analytics Generated Allocation Metrics
Capacity allocation metrics provide information about the allotment of capacity for Cluster Compute and Datastore Cluster
Resources.
Metric Name Description
Capacity Analytics Generated|CPU|Allocation|Capacity Remaining
(vCPUs)
For vSphere objects published on Cluster Compute Resource
only. Capacity Remaining based on overcommit ratio (if configured
in effective policy).
Key: OnlineCapacityAnalytics|cpu|alloc|capacityRemaining
Capacity Analytics Generated|CPU|Allocation|Recommended
Total Capacity (Cores)
For vSphere objects published on Cluster Compute Resource
only. The recommended level of total capacity, to maintain a green
state for time remaining for the given object.
Key: OnlineCapacityAnalytics|cpu|alloc|recommendedTotalSize
Capacity Analytics Generated|CPU|Allocation|Time Remaining
(Day(s))
For vSphere objects published on Cluster Compute Resource
only. The number of days remaining is calculated for both
group and container. It calculates the time remaining before the
resources run out.
Key: OnlineCapacityAnalytics|cpu|alloc|timeRemaining
CPU|Allocation|Usable Capacity after HA and Buffer (vCPUs) For vSphere objects published on Cluster Compute Resource
only. The usable capacity (total capacity - HA) based on
configured overcommit ratio.
VMware by Broadcom  4405

---
## page 4406

 VMware Cloud Foundation 9.0
Metric Name Description
Key: cpu|alloc|usableCapacity
Capacity Analytics Generated|CPU|Allocation|Recommended Size
(Cores)
For vSphere objects published on Cluster Compute Resource
only. The recommended level of usable capacity (total capacity
- HA), to maintain a green state for time remaining for the given
object.
Key: OnlineCapacityAnalytics|cpu|alloc|recommendedSize
vRealize Operations Manager Generated Properties|CPU|
Allocation|Overcommit Ratio Setting
For vSphere objects published on Cluster Compute Resource
only. This property shows the allocation overcommit ratio for CPU
provided in effective policy.
Key: System Properties|cpu|alloc|overcommitRatioSetting
vRealize Operations Manager Generated Properties|CPU|
Allocation|Buffer (%)
CPU buffer percent defined by policy setting for allocation based
capacity computation.
Key: Properties|cpu|alloc|bufferSetting
Capacity Analytics Generated|Memory|Allocation|Capacity
Remaining (KB)
For vSphere objects published on Cluster Compute Resource
only. Capacity Remaining based on overcommit ratio (if configured
in effective policy).
Key: OnlineCapacityAnalytics|mem|alloc|capacityRemaining
Capacity Analytics Generated|Memory|Allocation|Recommended
Total Capacity (KB)
For vSphere objects published on Cluster Compute Resource
only. The recommended level of total capacity, to maintain a green
state for time remaining for the given object.
Key: OnlineCapacityAnalytics|mem|alloc|recommendedTotalSize
Capacity Analytics Generated|Memory|Allocation|Time Remaining
(Day(s))
For vSphere objects published on Cluster Compute Resource
only. The number of days remaining is calculated for both
group and container. It calculates the time remaining before the
resources run out.
Key: OnlineCapacityAnalytics|mem|alloc|timeRemaining
Memory|Allocation|Usable Capacity (KB) For vSphere objects published on Cluster Compute Resource
only. The usable capacity (total capacity - HA) based on
configured overcommit ratio.
Key: mem|alloc|usableCapacity
Capacity Analytics Generated|Memory|Allocation|Recommended
Size (KB)
For vSphere objects published on Cluster Compute Resource
only. The recommended level of usable capacity (total capacity
- HA), to maintain a green state for time remaining for the given
object.
Key: OnlineCapacityAnalytics|mem|alloc|recommendedSize
vRealize Operations Manager Generated Properties|Memory|
Allocation|Overcommit Ratio Setting
For vSphere objects published on Cluster Compute Resource
only. This property shows the allocation overcommit ratio for
Memory provided in effective policy.
Key: System Properties|mem|alloc|overcommitRatioSetting
vRealize Operations Manager Generated Properties|Memory|
Allocation|Buffer (%)
Memory buffer percent defined by policy setting for allocation
based capacity computation.
Key: System Properties|mem|alloc|bufferSetting
Capacity Analytics Generated|Disk Space|Allocation|Capacity
Remaining (GB)
For vSphere objects published on Cluster Compute Resource
and Datastore Cluster Resource. Capacity Remaining based on
overcommit ratio (if configured in effective policy).
Key: OnlineCapacityAnalytics|diskspace|alloc|capacityRemaining
VMware by Broadcom  4406

---
## page 4407

 VMware Cloud Foundation 9.0
Metric Name Description
Capacity Analytics Generated|Disk Space|Allocation|
Recommended Size (GB)
For vSphere objects published on Cluster Compute Resource
and Datastore Cluster Resource. The recommended level of total
capacity to maintain a green state for time remaining for the given
object.
Key: OnlineCapacityAnalytics|diskspace|alloc|recommendedSize
Capacity Analytics Generated|Disk Space|Allocation|Time
Remaining (Day(s))
For vSphere objects published on Cluster Compute Resource
and Datastore Cluster Resource. The number of days remaining
is calculated for both group and container. It calculates the time
remaining before the resources run out.
Key: OnlineCapacityAnalytics|diskspace|alloc|timeRemaining
Disk Space|Allocation|Usable Capacity (GB) For vSphere objects published on Cluster Compute Resource
and Datastore Cluster Resource. Usable capacity based on
overcommit ratio (if configured in effective policy).
Key: diskspace|alloc|usableCapacity
vRealize Operations Manager Generated Properties|Disk Space|
Allocation|Overcommit Ratio Setting
For vSphere objects published on Cluster Compute Resource and
Datastore Cluster Resource. This property shows the allocation
overcommit ratio for Disk Space provided in effective policy.
key: System Properties|diskspace|alloc|overcommitRatioSetting
vRealize Operations Manager Generated Properties|Disk Space|
Allocation|Buffer (%)
Disk Space buffer percent defined by policy setting for allocation
based capacity computation.
Key: System Properties|diskspace|alloc|bufferSetting
Capacity Analytics Generated Profiles Metrics
Profiles metrics provide information about the profile specific capacity for Cluster Compute, Datastore Cluster, Data
Center, Custom Data Center, and vCenter Server resources.
Metric Name Description
Capacity Analytics Generated|Capacity Remaining (Profile) Published on Cluster Compute Resource. Calculated as a
minimum of all Profiles|capacityRemainingProfile_<profile uuid>
metrics.
Key: OnlineCapacityAnalytics|capacityRemainingProfile
Capacity Analytics Generated|Capacity Remaining (Profile) Published on Datastore Cluster Resource. Calculated as a
minimum of all Profiles|capacityRemainingProfile_<profile uuid>
metrics.
Key: OnlineCapacityAnalytics|capacityRemainingProfile
Capacity Analytics Generated|Capacity Remaining (Profile) Published on Data Center, Custom Data Center and
vCenter Server Resources. Computed as a sum of
OnlineCapacityAnalytics|capacityRemainingProfile metric of
descendant Cluster Compute Resources.
Key: OnlineCapacityAnalytics|capacityRemainingProfile
Capacity Demand Model Metrics
Demand model metrics provide information about the usable capacity and projected utilization of resources across VMs,
Host Systems, Cluster Compute, Datastore Cluster, Data Center, Custom Data Center, and vCenter Server resources.
VMware by Broadcom  4407

---
## page 4408

 VMware Cloud Foundation 9.0
Metric Name Description
Capacity Analytics Generated|CPU|Capacity Remaining (MHz) Published on Virtual Machine. The max point between the usable
capacity and the projected utilization between now and three
days.
Key: OnlineCapacityAnalytics|cpu|capacityRemaining
Capacity Analytics Generated|CPU|Recommended Size (MHz) Published on Virtual Machine. The recommended level of usable
capacity (total capacity - HA) to maintain a green state for the
remaining time.
Key: OnlineCapacityAnalytics|cpu|recommendedSize
Capacity Analytics Generated|CPU|Time Remaining (Day(s)) Published on Virtual Machine. The number of days remaining
till the projected utilization crosses the threshold for the usable
capacity.
Key: OnlineCapacityAnalytics|cpu|timeRemaining
Capacity Analytics Generated|Disk Space|Capacity Remaining
(GB)
Published on Virtual Machine. The max point between the usable
capacity and the projected utilization between now and three days
into the future.
Key: OnlineCapacityAnalytics|diskspace|capacityRemaining
Capacity Analytics Generated|Disk Space|Recommended Size
(GB)
Published on Virtual Machine. The recommended level of usable
capacity (total capacity - HA) to maintain a green state for the
remaining time.
Key: OnlineCapacityAnalytics|diskspace|recommendedSize
Capacity Analytics Generated|Disk Space|Time Remaining
(Day(s))
Published on Virtual Machine. The number of days remaining
till the projected utilization crosses the threshold for the usable
capacity.
Key: OnlineCapacityAnalytics|diskspace|timeRemaining
Capacity Analytics Generated|Memory|Capacity Remaining (KB) Published on Virtual Machine. The max point between the usable
capacity and the projected utilization between now and three days
into the future.
Key: OnlineCapacityAnalytics|mem|capacityRemaining
Capacity Analytics Generated|Memory|Recommended Size (KB) Published on Virtual Machine. The recommended level of usable
capacity (total capacity - HA) to maintain a green state for the
remaining time.
Key: OnlineCapacityAnalytics|mem|recommendedSize
Capacity Analytics Generated|Memory|Time Remaining (Day(s)) Published on Virtual Machine. The number of days remaining
till the projected utilization crosses the threshold for the usable
capacity.
Key: OnlineCapacityAnalytics|mem|timeRemaining
Capacity Analytics Generated|CPU|Demand|Capacity Remaining
(MHz)
Published on Host System. The max point between the usable
capacity and the projected utilization between now and three days
into the future.
Key: OnlineCapacityAnalytics|cpu|demand|capacityRemaining
vRealize Operations Manager Generated Properties|CPU|
Demand|Buffer (%)
CPU buffer percent defined by policy setting for demand based
capacity computation.
Key: System Properties|cpu|demand|bufferSetting
Capacity Analytics Generated|CPU|Demand|Recommended Size
(MHz)
Published on Host System. The recommended level of usable
capacity (total capacity - HA) to maintain a green state for the
remaining time.
Key: OnlineCapacityAnalytics|cpu|demand|recommendedSize
VMware by Broadcom  4408

---
## page 4409

 VMware Cloud Foundation 9.0
Metric Name Description
Capacity Analytics Generated|CPU|Demand|Time Remaining
(Day(s))
Published on Host System. The number of days remaining till the
projected utilization crosses the threshold for the usable capacity.
Key: OnlineCapacityAnalytics|cpu|demand|timeRemaining
Capacity Analytics Generated|Disk Space|Demand|Capacity
Remaining (GB)
Published on Host System. The max point between the usable
capacity and the projected utilization between now and three days
into the future.
Key: OnlineCapacityAnalytics|diskspace|demand|
capacityRemaining
vRealize Operations Manager Generated Properties|Disk Space|
Demand|Buffer (%)
Disk Space buffer percent defined by policy setting for demand
based capacity computation.
System Properties|diskspace|demand|bufferSetting
Capacity Analytics Generated|Disk Space|Demand|Recommended
Size (GB)
Published on Host System. The recommended level of usable
capacity (total capacity - HA) to maintain a green state for the
remaining time.
Key: OnlineCapacityAnalytics|diskspace|demand|
recommendedSize
Capacity Analytics Generated|Disk Space|Demand|Time
Remaining (Day(s))
Published on Host System. The number of days remaining till the
projected utilization crosses the threshold for the usable capacity.
Key: OnlineCapacityAnalytics|diskspace|demand|timeRemaining
Capacity Analytics Generated|Memory|Demand|Capacity
Remaining (KB)
Published on Host System. The max point between the usable
capacity and the projected utilization between now and three days
into the future.
Key: OnlineCapacityAnalytics|mem|demand|capacityRemaining
vRealize Operations Manager Generated Properties|Memory|
Demand|Buffer (%)
Memory buffer percent defined by policy setting for demand
based capacity computation.
Key: System Properties|mem|demand|bufferSetting
Capacity Analytics Generated|Memory|Demand|Recommended
Size (KB)
Published on Host System. The recommended level of usable
capacity (total capacity - HA) to maintain a green state for the
remaining time.
Key: OnlineCapacityAnalytics|mem|demand|recommendedSize
Capacity Analytics Generated|Memory|Demand|Time Remaining
(Day(s))
Published on Host System. The number of days remaining till the
projected utilization crosses the threshold for the usable capacity.
Key: OnlineCapacityAnalytics|mem|demand|timeRemaining
Capacity Analytics Generated|Disk Space|Usage|Capacity
Remaining (GB)
Published on Datastore. The max point between the usable
capacity and the projected utilization between now and three days
into the future.
Key: OnlineCapacityAnalytics|diskspace|total|capacityRemaining
Capacity Analytics Generated|Disk Space|Usage|Recommended
Size (GB)
Published on Datastore. The recommended level of usable
capacity (total capacity - HA) to maintain a green state for the
remaining time.
Key: OnlineCapacityAnalytics|diskspace|total|recommendedSize
Capacity Analytics Generated|Disk Space|Usage|Time Remaining
(Day(s))
Published on Datastore. The number of days remaining till the
projected utilization crosses the threshold for the usable capacity.
Key: OnlineCapacityAnalytics|diskspace|total|timeRemaining
Capacity Analytics Generated|CPU|Demand|Capacity Remaining
(MHz)
Published on Cluster Compute Resource. The max point between
the usable capacity and the projected utilization between now and
three days into the future.
VMware by Broadcom  4409

---
## page 4410

 VMware Cloud Foundation 9.0
Metric Name Description
Key: OnlineCapacityAnalytics|cpu|demand|capacityRemaining
Capacity Analytics Generated|CPU|Demand|Recommended Size
(MHz)
Published on Cluster Compute Resource. The recommended
level of usable capacity (total capacity - HA) to maintain a green
state for the remaining time.
Key: OnlineCapacityAnalytics|cpu|demand|recommendedSize
Capacity Analytics Generated|CPU|Demand|Recommended Total
Capacity (MHz)
Published on Cluster Compute Resource. The recommended
level of total capacity to maintain a green state for the time
remaining.
Key: OnlineCapacityAnalytics|cpu|demand|
recommendedTotalSize
Capacity Analytics Generated|CPU|Demand|Time Remaining
(Day(s))
Published on Cluster Compute Resource. The number of days
remaining till the projected utilization crosses the threshold for the
usable capacity.
Key: OnlineCapacityAnalytics|cpu|demand|timeRemaining
Capacity Analytics Generated|Disk Space|Demand|Capacity
Remaining (GB)
Published on Cluster Compute Resource. The max point between
the usable capacity and the projected utilization between now and
three days into the future.
Key: OnlineCapacityAnalytics|diskspace|demand|
capacityRemaining
Capacity Analytics Generated|Disk Space|Demand|Recommended
Size (GB)
Published on Cluster Compute Resource. The recommended
level of usable capacity (total capacity - HA) to maintain a green
state for the time remaining.
Key: OnlineCapacityAnalytics|diskspace|demand|
recommendedSize
Capacity Analytics Generated|Disk Space|Demand|Time
Remaining (Day(s))
Published on Cluster Compute Resource. The number of days
remaining till the projected utilization crosses the threshold for the
usable capacity.
Key: OnlineCapacityAnalytics|diskspace|demand|timeRemaining
Capacity Analytics Generated|Memory|Demand|Capacity
Remaining (KB)
Published on Cluster Compute Resource. The max point between
the usable capacity and the projected utilization between now and
three days into the future.
Key: OnlineCapacityAnalytics|mem|demand|capacityRemaining
Capacity Analytics Generated|Memory|Demand|Recommended
Size (KB)
Published on Cluster Compute Resource. The recommended
level of usable capacity (total capacity - HA) to maintain a green
state for the time remaining.
Key: OnlineCapacityAnalytics|mem|demand|recommendedSize
Capacity Analytics Generated|Memory|Demand|Recommended
Total Capacity (KB)
Published on Cluster Compute Resource. The recommended
level of total capacity to maintain a green state for the time
remaining.
Key: OnlineCapacityAnalytics|mem|demand|
recommendedTotalSize
Capacity Analytics Generated|Memory|Demand|Time Remaining
(Day(s))
Published on Cluster Compute Resource. The number of days
remaining till the projected utilization crosses the threshold for the
usable capacity.
Key: OnlineCapacityAnalytics|mem|demand|timeRemaining
Capacity Analytics Generated|Disk Space|Usage|Capacity
Remaining (GB)
Published on Datastore Cluster. The max point between the
usable capacity and the projected utilization between now and
three days into the future.
VMware by Broadcom  4410

---
## page 4411

 VMware Cloud Foundation 9.0
Metric Name Description
Key: OnlineCapacityAnalytics|diskspace|total|capacityRemaining
Capacity Analytics Generated|Disk Space|Usage|Recommended
Size (GB)
Published on Datastore Cluster. The recommended level of
usable capacity (total capacity - HA) to maintain a green state for
the time remaining.
Key: OnlineCapacityAnalytics|diskspace|total|recommendedSize
Capacity Analytics Generated|Disk Space|Usage|Time Remaining
(Day(s))
Published on Datastore Cluster. The number of days remaining
till the projected utilization crosses the threshold for the usable
capacity.
Key: OnlineCapacityAnalytics|diskspace|total|timeRemaining
Capacity Analytics Generated|CPU|Demand|Capacity Remaining
(MHz)
Published on Datacenter, Custom Datacenter, vCenter. The max
point between the usable capacity and the projected utilization
between now and three days into the future.
Key: OnlineCapacityAnalytics|cpu|demand|capacityRemaining
Capacity Analytics Generated|CPU|Demand|Recommended Size
(MHz)
Published on Datacenter, Custom Datacenter, vCenter. The
recommended level of usable capacity (total capacity - HA) to
maintain a green state for the time remaining.
Key: OnlineCapacityAnalytics|cpu|demand|recommendedSize
Capacity Analytics Generated|CPU|Demand|Recommended Total
Capacity (MHz)
Published on Datacenter, Custom Datacenter, vCenter. The
recommended level of total capacity to maintain a green state for
the time remaining.
Key: OnlineCapacityAnalytics|cpu|demand|
recommendedTotalSize
Capacity Analytics Generated|CPU|Demand|Time Remaining
(Day(s))
Published on Datacenter, Custom Datacenter, vCenter. The
number of days remaining till the projected utilization crosses the
threshold for the usable capacity.
Key: OnlineCapacityAnalytics|cpu|demand|timeRemaining
Capacity Analytics Generated|Disk Space|Demand|Capacity
Remaining (GB)
Published on Datacenter, Custom Datacenter, vCenter. The max
point between the usable capacity and the projected utilization
between now and three days into the future.
Key: OnlineCapacityAnalytics|diskspace|demand|
capacityRemaining
Capacity Analytics Generated|Disk Space|Demand|Recommended
Size (GB)
Published on Datacenter, Custom Datacenter, vCenter. The
recommended level of usable capacity (total capacity - HA) to
maintain a green state for the time remaining.
Key: OnlineCapacityAnalytics|diskspace|demand|
recommendedSize
Capacity Analytics Generated|Disk Space|Demand|Time
Remaining (Day(s))
Published on Datacenter, Custom Datacenter, vCenter. The
number of days remaining till the projected utilization crosses the
threshold for the usable capacity.
Key: OnlineCapacityAnalytics|diskspace|demand|timeRemaining
Capacity Analytics Generated|Memory|Demand|Capacity
Remaining (KB)
Published on Datacenter, Custom Datacenter, vCenter. The max
point between the usable capacity and the projected utilization
between now and three days into the future.
Key: OnlineCapacityAnalytics|mem|demand|capacityRemaining
Capacity Analytics Generated|Memory|Demand|Recommended
Size (KB)
Published on Datacenter, Custom Datacenter, vCenter. The
recommended level of usable capacity (total capacity - HA) to
maintain a green state for the time remaining.
VMware by Broadcom  4411

---
## page 4412

 VMware Cloud Foundation 9.0
Metric Name Description
Key: OnlineCapacityAnalytics|mem|demand|recommendedSize
Capacity Analytics Generated|Memory|Demand|Recommended
Total Capacity (KB)
Published on Datacenter, Custom Datacenter, vCenter. The
recommended level of total capacity to maintain a green state for
the time remaining.
Key: OnlineCapacityAnalytics|mem|demand|
recommendedTotalSize
Capacity Analytics Generated|Memory|Demand|Time Remaining
(Day(s))
Published on Datacenter, Custom Datacenter, vCenter. The
number of days remaining till the projected utilization crosses the
threshold for the usable capacity.
Key: OnlineCapacityAnalytics|mem|demand|timeRemaining
Badge Metrics
Badge metrics provide information for badges in the user interface. They report the health, risk, and efficiency of objects in
your environment.
VCF Operations 6.x analyzes badge metric data at five-minute averages, instead of hourly. As a result, you might find
that efficiency and risk badge calculations are more sensitive than in previous versions. Badge metrics continue to be
published nightly.
Table 1310: Badge Metrics
Metric Name Description
Badge|Compliance Badge|Compliance(%) metric shows the compliance score for the given
object based on the number of violated and total number of compliance
symptoms calculated with the following formula  [Math.round(100 -
(((double)triggeredSymptoms/totalSymptoms)*100))] .
So, this metric shows the compliance score per object based on the violated
symptoms (which can be seen under the object's details Compliance tab).
This metric should not be mixed up with the compliance score shown for
the benchmark in the Operations > Compliance page which considers
compliant/non-compliant vs total objects.Badge|Compliance(%) metric is
used in 4 views: - Compliance \ VM Distribution - Compliance \ vSphere
Distributed Port Groups - Compliance \ vSphere ESXi Hosts - Compliance
\ vSphere VMs, as well as 1 deprecated dashboard's widget - vSphere
Security Compliance dashboard's Compliance Summary widget.
Badge|Efficiency Overall score for efficiency. The final score is between 1-100. Where Green
- 100, Yellow - 75, Orange - 50, Red - 25, Unknown: -1. The score is derived
from the criticality of alerts in the Efficiency category.
Badge|Health Overall score for health. The final score is between 1-100. Where Green -
100, Yellow - 75, Orange - 50, Red - 25, Unknown: -1. The score is derived
from the criticality of alerts in the Health category.
Badge|Risk Overall score for risk. The final score is between 1-100. Where Green - 0,
Yellow - 25, Orange - 50, Red - 75, Unknown: -1. The score is derived from
the criticality of alerts in the Risk category.
VMware by Broadcom  4412

---
## page 4413

 VMware Cloud Foundation 9.0
System Metrics
System metrics provide information used to monitor the health of the system. They help you to identify problems in your
environment.
Table 1311: System Metrics
Metric Name Description
vRealize Operations Generated|Self - Health Score This metric displays the system health score of self resource. The
value ranges from 0 to 100 depending on noise and the number of
alarms.
Key: System Attributes|health
vRealize Operations Generated|Self - Metric Count This metric displays the number of metrics that the adapter
generates for the given object. This value does not include the
number of metrics generated by VCF Operations, such as, Badge
metrics, vRealize Operations Generated metrics and metrics
generated by Capacity Engine
Key: System Attributes|all_metrics
vRealize Operations Generated|Total Anomalies This metric displays the number of active anomalies (symptoms,
events, DT violations) on the object and its children.
In previous versions of VCF Operations, this metric used to be
named vRealize Operations Generated| Self - Total Anomalies.
Key: System Attributes|total_alarms
vRealize Operations Generated|Full Set - Metric Count This metric displays the number of metrics that the adapter of the
children of the given object generates.
Key: System Attributes|child_all_metrics
vRealize Operations Generated|Availability This metric value is computed based on the adapter instance
statuses monitoring the resource. Resource availability is
displayed as 0-down, 1-Up, -1-Unknown.
Key: System Attributes|availability
vRealize Operations Generated|Alert Count Critical This metric displays the number of critical alerts on the object and
its children.
Key: System Attributes|alert_count_critical
vRealize Operations Generated|Alert Count Immediate This metric displays the number of immediate alerts on the object
and its children.
Key: System Attributes|alert_count_immediate
vRealize Operations Generated|Alert Count Warning This metric displays the number of active warning alerts on the
object and its children.
Key: System Attributes|alert_count_warning
vRealize Operations Generated|Alert Count Info This metric displays the number of active info alerts on the object
and its children.
Key: System Attributes|alert_count_info
vRealize Operations Generated|Total Alert Count This metric displays the sum of all alert count metrics.
In previous versions of VCF Operations, this metric was named
vRealize Operations Generated|Full Set - Alert Count.
Key: System Attributes|total_alert_count
vRealize Operations Generated|Self-Alert Count This metric displays the number of all alerts on the object.
Key: System Attributes|self_alert_count
VMware by Broadcom  4413

---
## page 4414

 VMware Cloud Foundation 9.0
 VCF Operations for logs Generated Metrics
The metrics in the VCF Operations for logs Generated group provide information that you can use to observe or
troubleshoot VMware Cloud Foundation Operations for failures and to monitor performance.
When VMware Cloud Foundation Operations is integrated with VCF Operations for logs and metric calculation is enabled,
VCF Operations for logs calculates the number of logs corresponding to different queries and sends them as metrics
to VMware Cloud Foundation Operations. These metrics are calculated for vCenter objects, host objects, and virtual
machine objects. The metrics can be mapped to a VMware Cloud Foundation Operations object based on the VCF
Operations for logs field vmw_vrops_id, which is constructed based on hostname or source fields.
Table 1312: Log Insight Generated Metrics
Metric Name Description
VCF Operations for logs Generated|Error Count The number of error logs for the selected object.
Key: log_insight_generated|error_count
VCF Operations for logs Generated|Total Log Count The total number of logs for the selected object.
Key: log_insight_generated|total_log_count
VCF Operations for logs Generated|Warning Count The number of warning logs for the selected object.
Key: log_insight_generated|warning_count
Self-Monitoring Metrics for VCF Operations
VCF Operations uses the VCF Operations adapter to collect metrics that monitor its own performance. These self-
monitoring metrics drive capacity models for VCF Operations objects and are useful for diagnosing problems with VCF
Operations.
Analytics Metrics
VCF Operations collects metrics for the VCF Operations analytics service, including threshold checking metrics.
Table 1313: Analytics Metrics
Metric Key Metric Name Description
ActiveAlarms Active DT Symptoms Active DT Symptoms.
ActiveAlerts Active Alerts Active alerts.
PrimaryResourcesCount Number of primary objects Number of primary objects
LocalResourcesCount Number of local objects Number of local objects
PrimaryMetricsCount Number of primary metrics Number of primary metrics
LocalMetricsCount Number of local metrics Number of local metrics
ReceivedResourceCount Number of received objects Number of received objects
ReceivedMetricCount Number of received metrics Number of received metrics
LocalFDSize Number of forward data entries Number of locally stored primary and
redundant entries in forward data
region.
LocalPrimaryFDSize Number of primary forward data entries Number of locally stored primary
entries in forward data region.
VMware by Broadcom  4414

---
## page 4415

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
LocalFDAltSize Number of alternative forward data entries Number of locally stored primary
and redundant entries in alternative
forward data region.
LocalPrimaryFDAltSize Number of alternative primary forward data
entries
Number of locally stored primary
entries in alternative forward data
region.
CurrentHeapSize Current heap size Current heap size.
MaxHeapSize Max heap size Max heap size
CommittedMemory Committed memory Committed memory
CPUUsage CPU usage CPU usage
Threads Threads Threads
UpStatus Threads Threads
Overall Threshold Checking Metrics for the Analytics Service
Overall threshold checking captures various metrics for work items used to process incoming observation
data. All metrics keys for the overall threshold checking metrics begin with OverallThresholdChecking, as in
OverallThresholdChecking|Count or OverallThresholdChecking|CheckThresholdAndHealth|
OutcomeObservationsSize|TotalCount.
Table 1314: Overall Threshold Checking Metrics for the Analytics Service
Metric Key Metric Name Description
Count Count Count
Duration|TotalDuration Total Total length of duration (ms)
Duration|AvgDuration Average Average duration (ms)
Duration|MinDuration Minimum Minimum duration (ms)
Duration|MaxDuration Maximum Maximum duration (ms)
IncomingObservationsSize|TotalCount Total Total
IncomingObservationsSize|AvgCount Average Average
IncomingObservationsSize|MinCount Minimal Minimal
IncomingObservationsSize|MaxCount Maximal Maximal
CheckThresholdAndHealth|Count Count Count
CheckThresholdAndHealth|Duration|TotalDuration Total Total length of duration (ms)
CheckThresholdAndHealth|Duration|AvgDuration Average Average duration (ms)
CheckThresholdAndHealth|Duration|MinDuration Minimum Minimum duration (ms)
CheckThresholdAndHealth|Duration|MaxDuration Maximum Maximum duration (ms)
CheckThresholdAndHealth|
OutcomeObservationsSize|TotalCount
Total Total
CheckThresholdAndHealth|
OutcomeObservationsSize|AvgCount
Average Average
VMware by Broadcom  4415

---
## page 4416

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
CheckThresholdAndHealth|
OutcomeObservationsSize|MinCount
Minimal Minimal
CheckThresholdAndHealth|
OutcomeObservationsSize|MaxCount
Maximal Maximal
SuperMetricComputation|Count Count Count
SuperMetricComputation|Duration|TotalDuration Total Total length of duration (ms)
SuperMetricComputation|Duration|AvgDuration Average Average duration (ms)
SuperMetricComputation|Duration|MinDuration Minimum Minimum duration (ms)
SuperMetricComputation|Duration|MaxDuration Maximum Maximum duration (ms)
SuperMetricComputation|SuperMetricsCount|
TotalCount
Total Total
SuperMetricComputation|SuperMetricsCount |
AvgCount
Average Average
SuperMetricComputation|SuperMetricsCount |
MinCount
Minimal Minimal
SuperMetricComputation|SuperMetricsCount |
MaxCount
Maximal Maximal
StoreObservationToFSDB|Count Count Count
StoreObservationToFSDB|Duration|TotalDuration Total Total length of duration (ms)
StoreObservationToFSDB|Duration|AvgDuration Average Average duration (ms)
StoreObservationToFSDB|Duration|MinDuration Minimum Minimum duration (ms)
StoreObservationToFSDB|Duration|MaxDuration Maximum Maximum duration (ms)
StoreObservationToFSDB|
StoredObservationsSize|TotalCount
Total Total
StoreObservationToFSDB|
StoredObservationsSize|AvgCount
Average Average
StoreObservationToFSDB|
StoredObservationsSize|MinCount
Minimal Minimal
StoreObservationToFSDB|
StoredObservationsSize|MaxCount
Maximal Maximal
UpdateResourceCache|Count Count Count
UpdateResourceCache|Duration|TotalDuration Total Total
UpdateResourceCache|Duration|AvgDuration Average Average
UpdateResourceCache|Duration|MinDuration Minimum Minimum
UpdateResourceCache|Duration|MaxDuration Maximum Maximum
UpdateResourceCache|
ModifcationEstimateCount|TotalCount
Total The number of estimated
modifications done during each
resource cache object update.
UpdateResourceCache|
ModifcationEstimateCount|AvgCount
Average Average
VMware by Broadcom  4416

---
## page 4417

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
UpdateResourceCache|
ModifcationEstimateCount|MinCount
Minimal Minimal
UpdateResourceCache|
ModifcationEstimateCount|MaxCount
Maximal Maximal
ManageAlerts|Count Count The total number of times the
threshold checking work items
perform alert updates.
ManageAlerts|Duration|TotalDuration Total The duration for the alert updates
operations.
ManageAlerts|Duration|AvgDuration Average Average
ManageAlerts|Duration|MinDuration Minimum Minimum
ManageAlerts|Duration|MaxDuration Maximum Maximum
UpdateSymptoms|Count Count The total number of times the
threshold checking work items check
and build symptoms.
UpdateSymptoms|Duration|TotalDuration Total The duration for the check and build
symptoms operation.
UpdateSymptoms|Duration|AvgDuration Average Average
UpdateSymptoms|Duration|MinDuration Minimum Minimum
UpdateSymptoms|Duration|MaxDuration Maximum Maximum
Dynamic Threshold Calculation Metrics for the Analytics Service
All metrics keys for the dynamic threshold calculation metrics begin with DtCalculation, as in DtCalculation|
DtDataWrite|WriteOperationCount or DtCalculation|DtAnalyze|AnalyzeOperationCount.
Table 1315: Dynamic Threshold Calculation Metrics for the Analytics Service
Metric Key Metric Name Description
DtDataWrite|WriteOperationCount Write operation count Write operation count
DtDataWrite|Duration|TotalDuration Total Total length of duration (ms)
DtDataWrite|Duration|AvgDuration Average Average duration (ms)
DtDataWrite|Duration|MinDuration Minimum Minimum duration (ms)
DtDataWrite|Duration|MaxDuration Maximum Maximum duration (ms)
DtDataWrite|SavedDtObjectCount|TotalCount Total Total
DtDataWrite|SavedDtObjectCount|AvgCount Average Average
DtDataWrite|SavedDtObjectCount|MinCount Minimal Minimal
DtDataWrite|SavedDtObjectCount|MaxCount Maximal Maximal
DtAnalyze|AnalyzeOperationCount Analyze Operation Count Analyze Operation Count
DtAnalyze|Duration|TotalDuration Total Total length of duration (ms)
DtAnalyze|Duration|AvgDuration Average Average duration (ms)
VMware by Broadcom  4417

---
## page 4418

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
DtAnalyze|Duration|MinDuration Minimum Minimum duration (ms)
DtAnalyze|Duration|MaxDuration Maximum Maximum duration (ms)
DtAnalyze|AnalyzedMetricsCount|TotalCount Total Total
DtAnalyze|AnalyzedMetricsCount|AvgCount Average Average
DtAnalyze|AnalyzedMetricsCount|MinCount Minimal Minimal
DtAnalyze|AnalyzedMetricsCount|MaxCount Maximal Maximal
DtDataRead|ReadOperationsCount Read Operation Count Read Operation Count
DtDataRead|Duration|TotalDuration Total Total length of duration (ms)
DtDataRead|Duration|AvgDuration Average Average duration (ms)
DtDataRead|Duration|MinDuration Minimum Minimum duration (ms)
DtDataRead|Duration|MaxDuration Maximum Maximum duration (ms)
DtDataRead|ReadDataPointsCount|TotalCount Total Total
DtDataRead|ReadDataPointsCount|AvgCount Average Average
DtDataRead|ReadDataPointsCount|MinCount Minimal Minimal
DtDataRead|ReadDataPointsCount|MaxCount Maximal Maximal
Table 1316: Function Call Metrics for the Analytics Service
Metric Key Metric Name Description
FunctionCalls|Count Number of function calls Number of function calls
FunctionCalls|AvgDuration Average execution time Average execution time
FunctionCalls|MaxDuration Max execution time Max execution time
Collector Metrics
VCF Operations collects metrics for the VCF Operations Collector service objects.
Table 1317: Collector Metrics
Metric Key Metric Name Description
ThreadpoolThreadsCount Number of pool threads Number of pool threads.
RejectedFDCount Number of rejected forward data Number of rejected forward data
RejectedFDAltCount Number of rejected alternative forward
data
Number of rejected alternative forward
data
SentFDCount Number of sent objects Number of sent objects
SentFDAltCount Number of alternative sent objects Number of alternative sent objects
CurrentHeapSize Current heap size (MB) Current heap size.
MaxHeapsize Max heap size (MB) Maximum heap size.
CommittedMemory Committed memory (MB) Amount of committed memory.
VMware by Broadcom  4418

---
## page 4419

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
CPUUsage CPU usage CPU usage.
Threads Threads Number of threads.
UpStatus Up Status Up Status
Controller Metrics
VCF Operations collects metrics for the VCF Operations Controller objects.
Table 1318: Controller Metrics
Metric Key Metric Name Description
RequestedMetricCount Number of requested metrics Number of requested metrics
ApiCallsCount Number of API calls Number of API calls
NewDiscoveredResourcesCount Number of discovered objects Number of discovered objects
FSDB Metrics
VCF Operations collects metrics for the VCF Operations file system database (FSDB) objects.
Table 1319: FSDB Metrics
Metric Key Metric Name Description
StoragePoolElementsCount Number of storage work items Number of storage work items
FsdbState Fsdb state Fsdb state
StoredResourcesCount Number of stored objects Number of stored objects
StoredMetricsCount Number of stored metrics Number of stored metrics
Table 1320: Storage Thread Pool Metrics for FSDB
Metric Key Metric Name Description
StoreOperationsCount Store operations count Store operations count
StorageThreadPool|Duration|TotalDuration Total Total number of duration (ms)
StorageThreadPool|Duration|AvgDuration Average Average duration (ms)
StorageThreadPool|Duration|MinDuration Minimum Minimum duration (ms)
StorageThreadPool|Duration|MaxDuration Maximum Maximum duration (ms)
StorageThreadPool|SavedMetricsCount|
TotalCount
Total Total
StorageThreadPool|SavedMetricsCount|
AvgCount
Average Average
StorageThreadPool|SavedMetricsCount|
MinCount
Minimal Minimal
VMware by Broadcom  4419

---
## page 4420

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
StorageThreadPool|SavedMetricsCount|
MaxCount
Maximal Maximal
Product UI Metrics
VCF Operations collects metrics for the VCF Operations product user interface objects.
Table 1321: Product UI Metrics
Metric Key Metric Name Description
ActiveSessionsCount Active sessions Active sessions
CurrentHeapSize Current heap size Current heap size.
MaxHeapsize Max heap size Maximum heap size.
CommittedMemory Committed memory Amount of committed memory.
CPUUsage CPU usage Percent CPU use.
Threads Threads Number of threads.
SessionCount Number of active sessions Number of active sessions
SelfMonitoringQueueSize Self Monitoring queue size Self Monitoring queue size
Table 1322: API Call Metrics for the Product UI
Metric Key Metric Name Description
APICalls|HTTPRequesterRequestCount HTTPRequester request count HTTPRequester request count
APICalls|AvgHTTPRequesterRequestTime HTTPRequester average request time HTTPRequester average request time
(ms)
APICalls|FailedAuthenticationCount Failed Authentication Count Failed Authentication Count
APICalls|AvgAlertRequestTime Average alert request time Average alert request time (ms)
APICalls|AlertRequestCount Alert request count Alert request count
APICalls|AvgMetricPickerRequestTime Average metric-picker request time Average metric-picker request time (ms)
APICalls|MetricPickerRequestCount Metric picker request count Metric picker request count
APICalls|HeatmapRequestCount Heatmap request count Heatmap request count
APICalls|AvgHeatmapRequestTime Average HeatMap request time Average HeatMap request time (ms)
APICalls|MashupChartRequestCount Mashup Chart request count Mashup Chart request count
APICalls|AvgMashupChartRequestTime Average Mashup Chart request time Average Mashup Chart request time (ms)
APICalls|TopNRequestCount Top N request count Top N request count
APICalls|AvgTopNRequestTime Average Top N request time Average Top N request time (ms)
APICalls|MetricChartRequestCount Metric Chart request count Metric Chart request count
APICalls|AvgMetricChartRequestTime Average MetricChart request time Average MetricChart request time (ms)
VMware by Broadcom  4420

---
## page 4421

 VMware Cloud Foundation 9.0
Admin UI Metrics
VCF Operations collects metrics for the VCF Operations administration user interface objects.
Table 1323: Admin UI Metrics
Metric Key Metric Name Description
CurrentHeapSize Current heap size Current heap size (MB).
MaxHeapsize Max heap size Maximum heap size (MB).
CommittedMemory Committed memory Amount of committed memory (MB) .
CPUUsage CPU usage CPU usage (%).
Threads Threads Number of threads.
SessionCount Number of active sessions Number of active sessions
SelfMonitoringQueueSize Self Monitoring queue size Self Monitoring queue size
Table 1324: API Call Metrics for the Admin UI
Metric Key Metric Name Description
APICalls|HTTPRequesterRequestCount HTTPRequester request count HTTPRequester request count
APICalls|AvgHTTPRequesterRequestTime HTTPRequester average request time HTTPRequester average request time
(ms)
Suite API Metrics
VCF Operations collects metrics for the VCF Operations API objects.
Table 1325: Suite API Metrics
Metric Key Metric Name Description
UsersCount Number of users Number of users
ActiveSessionsCount Active sessions Active sessions
GemfireClientReconnects Gemfire Client Reconnects Gemfire Client Reconnects
GemfireClientCurrentCalls Gemfire Client Total Outstanding Gemfire Client Total Outstanding
CurrentHeapSize Current heap size Current heap size (MB) .
MaxHeapsize Max heap size Maximum heap size (MB) .
CommittedMemory Committed memory Amount of committed memory (MB).
CPUUsage CPU usage CPU usage (%) .
CPUProcessTime CPU process time CPU process time (ms)
CPUProcessTimeCapacity CPU process time capacity CPU process time capacity (ms)
Threads Threads Number of threads.
VMware by Broadcom  4421

---
## page 4422

 VMware Cloud Foundation 9.0
Table 1326: Gemfire Client Call Metrics for the Suite API
Metric Key Metric Name Description
GemfireClientCalls|TotalRequests Total Requests Total Requests
GemfireClientCalls|AvgResponseTime Average Response Time Average Response Time (ms)
GemfireClientCalls|MinResponseTime Minimum Response Time Minimum Response Time (ms)
GemfireClientCalls|MaxResponseTime Maximum Response Time Maximum Response Time
GemfireClientCalls|RequestsPerSecond Requests per Second Requests per Second
GemfireClientCalls|CurrentRequests Current Requests Current Requests
GemfireClientCalls|RequestsCount Requests Count Requests Count
GemfireClientCalls|ResponsesCount Responses Count Responses Count
Table 1327: API Call Metrics for the Suite API
Metric Key Metric Name Description
APICalls|TotalRequests Total Requests Total Requests
APICalls|AvgResponseTime Average Response Time (ms) Average Response Time (ms)
APICalls|MinResponseTime Minimum Response Time (ms) Minimum Response Time (ms)
APICalls|MaxResponseTime Maximum Response Time Maximum Response Time
APICalls|ServerErrorResponseCount Server Error Response Count Server Error Response Count
APICalls|FailedAuthenticationCount Failed Authentication Count Failed Authentication Count
APICalls|FailedAuthorizationCount Failed Authorization Count Failed Authorization Count
APICalls|RequestsPerSecond Requests per Second Requests per Second
APICalls|CurrentRequests Current Requests Current Requests
APICalls|ResponsesPerSecond Responses per Second Responses per Second
APICalls|RequestsCount Requests Count Requests Count
APICalls|ResponsesCount Responses Count Responses Count
Cluster and Slice Administration Metrics
VCF Operations collects metrics for VCF Operations Cluster and Slice Administration (CaSA) objects.
Table 1328: Cluster and Slice Administration Metrics
Metric Key Metric Name Description
CurrentHeapSize Current heap size Current heap size (MB).
MaxHeapsize Max heap size Maximum heap size (MB).
CommittedMemory Committed memory Amount of committed memory (MB).
CPUUsage CPU usage CPU usage (%)
Threads Threads Number of threads.
VMware by Broadcom  4422

---
## page 4423

 VMware Cloud Foundation 9.0
Table 1329: API Call Metrics for Cluster and Slice Administration
Metric Key Metric Name Description
API Calls|TotalRequests Total Requests Total Requests
API Calls|AvgResponseTime Average Response Time Average Response Time (ms)
API Calls|MinResponseTime Minimum Response Time Minimum Response Time (ms)
API Calls|MaxResponseTime Maximum Response Time Maximum Response Time (ms)
API Calls|ServerErrorResponseCount Server Error Response Count Server Error Response Count
API Calls|FailedAuthenticationCount Failed Authentication Count Failed Authentication Count
API Calls|FailedAuthorizationCount Minimum Response Time Minimum Response Time (ms)
Watchdog Metrics
VCF Operations collects watchdog metrics to ensure that the VCF Operations services are running and responsive.
Watchdog Metrics
The watchdog metric provides the total service count.
Table 1330: Watchdog Metrics
Metric Key Metric Name Description
ServiceCount Service Count Service Count
Service Metrics
Service metrics provide information about watchdog activity.
Table 1331: Metrics for the VCF Operations Watchdog Service
Metric Key Metric Name Description
Service|Enabled Enabled Enabled
Service|Restarts Restarts Number of times the process has been
unresponsive and been restarted by
Watchdog.
Service|Starts Starts Number of times the process has been
revived by Watchdog.
Service|Stops Stops Number of times the process has been
stopped by Watchdog.
Node Metrics
VCF Operations collects metrics for the VCF Operations node objects.
Metrics can be calculated for node objects. See Calculated Metrics.
VMware by Broadcom  4423

---
## page 4424

 VMware Cloud Foundation 9.0
Table 1332: Node Metrics
Metric Key Metric Name Description
Component Count Component count The number of VCF Operations objects
reporting for this node
PrimaryResourcesCount Number of primary objects Number of primary objects
LocalResourcesCount Number of local objects Number of local objects
PrimaryMetricsCount Number of primary metrics Number of primary metrics
LocalMetricsCount Number of local metrics Number of local metrics
PercentDBStorageAvailable Percent disk available /storage/db Percent disk available /storage/db
PercentLogStorageAvailable Percent disk available /storage/log Percent disk available /storage/log
FPing stats Latency|Average (ms)
FPing stats Latency|Maximum (ms)
FPing stats Latency|Minimum (ms)
FPing stats Packet Loss|Average (%) Percentage average packet loss between
nodes.
FPing stats Packet Loss|Maximum (%) Percentage maximum packet loss
between nodes.
FPing stats Packet Loss|Minimum (%) Percentage minimum packet loss between
nodes.
Table 1333: Memory Metrics for the Node
Metric Key Metric Name Description
mem|actualFree Actual Free Actual Free
mem|actualUsed Actual Used Actual Used
mem|free Free Free )
mem|used Used Used
mem|total Total Total
mem|demand_gb Estimated memory demand Estimated memory demand
Table 1334: Swap Metrics for the Node
Metric Key Metric Name Description
swap|total Total Total
swap|free Free Free
swap|used Used Used
swap|pageIn Page in Page in
swap|pageOut Page out Page out
VMware by Broadcom  4424

---
## page 4425

 VMware Cloud Foundation 9.0
Table 1335: Resource Limit Metrics for the Node
Metric Key Metric Name Description
resourceLimit|numProcesses Number of processes Number of processes
resourceLimit|openFiles Number of open files Number of open files
resourceLimit|openFilesMax Number of open files maximum limit Number of open files maximum limit
resourceLimit|numProcessesMax Number of processes maximum limit Number of processes maximum limit
Table 1336: Network Metrics for the Node
Metric Key Metric Name Description
net|allInboundTotal All inbound connections All inbound total
net|allOutboundTotal All outbound connections All outbound total
net|tcpBound TCP bound TCP bound
net|tcpClose TCP state CLOSE Number of connections in TCP
CLOSE
net|tcpCloseWait TCP state CLOSE WAIT Number of connections in TCP state
CLOSE WAIT
net|tcpClosing TCP state CLOSING Number of connections in TCP state
CLOSING
net|tcpEstablished TCP state ESTABLISHED Number of connections in TCP state
ESTABLISHED
net|tcpIdle TCP state IDLE Number of connections in TCP state
IDLE
net|tcpInboundTotal TCP inbound connections TCP inbound connections
net|tcpOutboundTotal TCP outbound connections TCP outbound connections
net|tcpLastAck TCP state LAST ACK Number of connections in TCP state
LAST ACK
net|tcpListen TCP state LISTEN Number of connections in TCP state
LISTEN
net|tcpSynRecv TCP state SYN RCVD Number of connections in TCP state
SYN RCVD
net|tcpSynSent TCP state SYN_SENT Number of connections in TCP state
SYN_SENT
net|tcpTimeWait TCP state TIME WAIT Number of connections in TCP state
TIME WAIT
Table 1337: Network Interface Metrics for the Node
Metric Key Metric Name Description
net|iface|speed Speed Speed (bits/sec)
net|iface|rxPackets Receive packets Number of received packets
VMware by Broadcom  4425

---
## page 4426

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
net|iface|rxBytes Receive bytes Number of received bytes
net|iface|rxDropped Receive packet drops Number of received packets dropped
net|iface|rxFrame Receive packets frame Number of receive packets frame
net|iface|rxOverruns Receive packets overruns Number of receive packets overrun
net|iface|txPackets Transmit packets Number of transmit packets
net|iface|txBytes Transmit bytes Number of transmit bytes
net|iface|txDropped Transmit packet drops Number of transmit packets dropped
net|iface|txCarrier Transmit carrier Transmit carrier
net|iface|txCollisions Transmit packet collisions Number of transmit collisions
net|iface|txErrors Transmit packet errors Number of transmit errors
net|iface|txOverruns Transmit packet overruns Number of transmit overruns
Table 1338: Disk Filesystem Metrics for the Node
Metric Key Metric Name Description
disk|fileSystem|total Total Total
disk|fileSystem|available Available Available
disk|fileSystem|used Used Used
disk|fileSystem|files Total file nodes Total file nodes
disk|fileSystem|filesFree Total free file nodes Total free file nodes
disk|fileSystem|queue Disk queue Disk queue
disk|fileSystem|readBytes Read bytes Number of bytes read
disk|fileSystem|writeBytes Write bytes Number of bytes written
disk|fileSystem|reads Reads Number of reads
disk|fileSystem|writes Writes Number of writes
Table 1339: Disk Installation Metrics for the Node
Metric Key Metric Name Description
disk|installation|used Used Used
disk|installation|total Total Total
disk|installation|available Available Available
Table 1340: Disk Database Metrics for the Node
Metric Key Metric Name Description
disk|db|used Used Used
disk|db|total Total Total
disk|db|available Available Available
VMware by Broadcom  4426

---
## page 4427

 VMware Cloud Foundation 9.0
Table 1341: Disk Log Metrics for the Node
Metric Key Metric Name Description
disk|log|used Used Used
disk|log|total Total Total
disk|log|available Available Available
Table 1342: CPU Metrics for the Node
Metric Key Metric Name Description
cpu|combined Combined load Combined load (User + Sys + Nice +
Wait)
cpu|idle Idle Idle time fraction of total available cpu
(cpu load)
cpu|irq Irq Interrupt time fraction of total
available cpu (cpu load)
cpu|nice Nice Nice time fraction of total available
cpu (cpu load)
cpu|softIrq Soft Irq Soft interrupt time fraction of total
available cpu (cpu load)
cpu|stolen Stolen Stolen time fraction of total available
cpu (cpu load)
cpu|sys Sys Sys time fraction of total available cpu
(cpu load)
cpu|user User (cpu load) User time fraction of total available
cpu (cpu load)
cpu|wait Wait (cpu load) Wait time fraction of total available
cpu (cpu load)
cpu|total Total available for a cpu Total available for a cpu
cpu|allCpuCombined Total combined load for all cpus Total combined load for all cpus (cpu
load)
cpu|allCpuTotal_ghz Available Available
cpu|allCpuCombined_ghz Used Used
cpu|allCpuCombined_percent CPU usage CPU usage (%)
Table 1343: Device Metrics for the Node
Metric Key Metric Name Description
device|iops Reads/Writes per second Average number of read/write
commands issued per second during
the collection interval.
device|await Average transaction time Average transaction time
(milliseconds).
VMware by Broadcom  4427

---
## page 4428

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
device|iops_readMaxObserved Maximum observed reads per second Maximum observed reads per
second.
device|iops_writeMaxObserved Maximum observed writes per second Maximum observed writes per
second.
Table 1344: Service Metrics for the Node
Metric Key Metric Name Description
service|proc|fdUsage Total number of open file descriptors Total number of open file descriptors.
Table 1345: NTP Metrics for the Node
Metric Key Metric Name Description
ntp|serverCount Configured server count Configured server count
ntp|unreachableCount Unreachable server count Unreachable server count
ntp|unreachable Unreachable Is the NTP server unreachable. Value
of 0 is reachable, 1 means the server
was not reached or did not respond.
Table 1346: Heap Metrics for the Node
Metric Key Metric Name Description
heap|CurrentHeapSize Current heap size Current heap size
heap|MaxHeapSize Max heap size Max heap size
heap|CommittedMemory Committed Memory Committed Memory
Cluster Metrics
VCF Operations collects metrics for the VCF Operations cluster objects including dynamic threshold calculation metrics
and capacity computation metrics.
Metrics can be calculated for cluster objects. See Calculated Metrics.
Cluster Metrics
Cluster metrics provide host, resource, and metric counts on the cluster.
Table 1347: Cluster Metrics
Metric Key Metric Name Description
HostCount Number of Nodes in Cluster Number of Nodes in Cluster
PrimaryResourcesCount Number of primary resources Number of primary resources
LocalResourcesCount Number of local resources Number of local resources
VMware by Broadcom  4428

---
## page 4429

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
PrimaryMetricsCount Number of primary metrics Number of primary metrics
ReceivedResourceCount Number of received resources Number of received resources
ReceivedMetricCount Number of received metrics Number of received metrics
Count (VM) Usage Count This metric displays how many units of the
license capacity is currently used.
License Metrics for Cluster Object
Used (VM) Usage (%) This metric displays the percentage of the
total license capacity currently used.
Note:  An alert is generated if the license
threshold is in any of the following states:
• >= 80% - Warning
• >= 90% - Immediate
• =95% - Catastrophic
Days Remaining (day) Days Remaining This metric displays the days remaining
before the license expires.
Capacity Capacity Displays the maximum number of units
(of the given capacity type) that can be
licensed by this license key.
Type Type Displays the license type for the cluster
object.
Expiry Expiration Date Displays the date when the license
expires.
Capacity Capacity Displays the maximum number of units
(of the given capacity type) that can be
licensed by this license key.
Disbalance factor (%) Disbalance factor (%) Identifies the state of disbalance in a
VCF Operations cluster and calculates
the disbalance factor (when one or more
nodes have a higher density among all
the nodes in the cluster). Based on the
disbalance percentage of the node, the
following alerts are triggered:
• Warning: If the disbalance factor metric
is equal to or greater than 5%.
• Immediate: If the disbalance factor
metric is equal to or greater than 7%.
• Critical: If the disbalance factor metric
is equal to or greater than 10%.
DT Metrics
DT metrics are dynamic threshold metrics for the cluster. Non-zero values appear only if metric collection occurs while the
dynamic threshold calculations are running.
VMware by Broadcom  4429

---
## page 4430

 VMware Cloud Foundation 9.0
Table 1348: DT Metrics for the Cluster
Metric Key Metric Name Description
dt|isRunning Running Running
dt|dtRunTime Running duration Running duration (ms)
dt|StartTime Running start time Running start time
dt|percentage Percent Percent (%)
dt|executorCount Executor Node Count Executor Node Count
dt|resourceCount Resource Count Resource Count
dt|fsdbReadTime FSDB Read Time FSDB Read Time (ms)
dt|dtObjectSaveTime DT Object Save Time DT Object Save Time (ms)
dt|dtHistorySaveTime DT History Save Time DT History Save Time (ms)
dt|executor|resourceCount Resource Count Resource Count
Capacity Computation (CC) Metrics
CC metrics are capacity computation metrics for the cluster. Non-zero values appear only if metric collection occurs while
the capacity computation calculations are running.
Table 1349: CC Metrics for the Cluster
Metric Key Metric Name Description
cc|isRunning Running Running
cc|runTime Total Run Time Total Run Time
cc|startTime Start time Start time
cc|finishTime Finish Time Finish Time
cc|totalResourcesToProcess Total Objects Count Total Objects Count
cc|progress Progress Progress
cc|phase1TimeTaken Phase 1 Computation Time Phase 1 Computation Time
cc|phase2TimeTaken Phase 2 Computation Time Phase 2 Computation Time
Gemfire Cluster Metrics
Gemfire metrics provide information about the Gemfire cluster.
Table 1350: Gemfire cluster Metrics for the Cluster
Metric Key Metric Name Description
GemfireCluster|System|AvgReads Average reads per second The average number of reads per second
for all members
GemfireCluster|System|AvgWrites Average writes per second The average number of writes per second
for all members
VMware by Broadcom  4430

---
## page 4431

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
GemfireCluster|System|DiskReadsRate Disk reads rate The average number of disk reads per
second across all distributed members
GemfireCluster|System|DiskWritesRate Disk writes rate The average number of disk writes per
second across all distributed members
GemfireCluster|System|
GarbageCollectionCount
Total garbage collection count The total garbage collection count for all
members
GemfireCluster|System|
GarbageCollectionCountDelta
New garbage collection count The new garbage collection count for all
members
GemfireCluster|System|JVMPauses JVM pause count The number of detected JVM pauses
GemfireCluster|System|JVMPausesDelta New JVM pause count The number of new detected JVM pauses
GemfireCluster|System|DiskFlushAvgLatency Disk flush average latency Disk flush average latency (msec)
GemfireCluster|System|NumRunningFunctions Number of running functions The number of map-reduce jobs currently
running on all members in the distributed
system
GemfireCluster|System|NumClients Number of clients The number of connected clients
GemfireCluster|System|TotalHitCount Total hit count Total number of cache hits for all regions
GemfireCluster|System|TotalHitCountDelta New hit count Number of new cache hits for all regions
GemfireCluster|System|TotalMissCount Total miss count The total number of cache misses for all
regions
GemfireCluster|System|TotalMissCountDelta New miss count Number of new cache misses for all
regions
GemfireCluster|System|Member|
FreeSwapSpace
Swap space free Swap space free (MB)
GemfireCluster|System|Member|
TotalSwapSpace
Swap space total Swap space total (MB)
GemfireCluster|System|Member|
CommittedVirtualMemorySize
Committed virtual memory size Committed virtual memory size (MB)
GemfireCluster|System|Member|
SystemLoadAverage
System load average System load average
GemfireCluster|System|Member|
FreePhysicalMemory
Free physical memory Free physical memory (MB)
GemfireCluster|System|Member|
TotalPhysicalMemory
Total physical memory Total physical memory (MB)
GemfireCluster|System|Member|
CacheListenerCallsAvgLatency
Average cache listener calls latency Average cache listener calls latency
(msec)
GemfireCluster|System|Member|
CacheWriterCallsAvgLatency
Average cache writer calls latency Average cache writer calls latency (msec)
GemfireCluster|System|Member|
DeserializationAvgLatency
Average deserialization latency Average deserialization latency (msec)
GemfireCluster|System|Member|
FunctionExecutionRate
Function executions per second Function executions per second
GemfireCluster|System|Member|JVMPauses Number of JVM pauses Number of JVM pauses
VMware by Broadcom  4431

---
## page 4432

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
GemfireCluster|System|Member|
NumRunningFunctions
Number of running functions Number of running functions
GemfireCluster|System|Member|PutsRate Puts per second Puts per second
GemfireCluster|System|Member|GetsRate Gets per second Gets per second
GemfireCluster|System|Member|
GetsAvgLatency
Average gets latency Average gets latency (msec)
GemfireCluster|System|Member|
PutsAvgLatency
Average puts latency Average puts latency (msec)
GemfireCluster|System|Member|
SerializationAvgLatency
Average serialization latency Average serialization latency (msec)
GemfireCluster|System|Member|Disk|
DiskFlushAvgLatency
Flush average latency Flush average latency (msec)
GemfireCluster|System|Member|Disk|
DiskReadsRate
Average reads per second Average reads per second
GemfireCluster|System|Member|Disk|
DiskWritesRate
Average writes per second Average writes per second
GemfireCluster|System|Member|Network|
BytesReceivedRate
Average received bytes per second Average received bytes per second
GemfireCluster|System|Member|Network|
BytesSentRate
Average sent bytes per second Average sent bytes per second
GemfireCluster|System|Member|JVM|
GCTimeMillis
Garbage Collection time Total amount of time spent on garbage
collection
GemfireCluster|System|Member|JVM|
GCTimeMillisDelta
New Garbage Collection time New amount of time spent on garbage
collection
GemfireCluster|System|Member|JVM|
TotalThreads
Total threads Total threads
GemfireCluster|System|Member|JVM|
CommitedMemory
Committed Memory Committed Memory (MB)
GemfireCluster|System|Member|JVM|
MaxMemory
Max Memory Max Memory (MB)
GemfireCluster|System|Member|JVM|
UsedMemory
Used Memory Used Memory (MB)
GemfireCluster|Region|
SystemRegionEntryCount
Entry Count Entry Count
GemfireCluster|Region|DestroyRate Destroys per second Destroys per second
GemfireCluster|Region|CreatesRate Creates per second Creates per second
GemfireCluster|Region|GetsRate Gets per second Gets per second
GemfireCluster|Region|BucketCount Bucket count Bucket count
GemfireCluster|Region|AvgBucketSize Average number of entries per bucket Average number of entries per bucket
GemfireCluster|Region|Member|
ActualRedundancy
Actual redundancy Actual redundancy
GemfireCluster|Region|Member|BucketCount Bucket count Bucket count
VMware by Broadcom  4432

---
## page 4433

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
GemfireCluster|Region|Member|
AvgBucketSize
Average number of entries per bucket Average number of entries per bucket
GemfireCluster|Region|Member|CreatesRate Creates per second Creates per second
GemfireCluster|Region|Member|GetsRate Gets per second Gets per second
GemfireCluster|Region|Member|DestroyRate Destroys per second Destroys per second
GemfireCluster|Region|Member|MissCount Number of misses count Number of cache misses
GemfireCluster|Region|Member|
MissCountDelta
Number of new cache misses Number of new cache misses
GemfireCluster|Region|Member|HitCount Number of hits count Number of cache hits
GemfireCluster|Region|Member|HitCountDelta Number of new cache hits Number of new cache hits
Threshold Checking Metrics
Threshold checking metrics check the processed and computed metrics for the cluster.
Table 1351: Threshold Checking Metrics for the Cluster
Metric Key Metric Name Description
ThresholdChecking|ProcessedMetricCount Number of processed metrics Number of processed metrics
ThresholdChecking|ProcessedMetricRate Received metric processing rate (per
second)
Received metric processing rate (per
second)
ThresholdChecking|ComputedMetricCount Number of computed metrics Number of computed metrics
ThresholdChecking|ComputedMetricRate Computed metric processing rate (per
second)
Computed metric processing rate (per
second)
Memory Metrics
Memory metrics provide memory CPU use information for the cluster.
Table 1352: Memory Metrics for the Cluster
Metric Key Metric Name Description
Memory|AvgFreePhysicalMemory Average free physical memory Average free physical memory (GB)
Memory|TotalFreePhysicalMemory Free physical memory Free physical memory (GB)
Memory|TotalMemory Total Available Memory Total Available Memory (GB)
Memory|TotalUsedMemory Actual Used Memory Actual Used Memory (GB)
Memory|TotalDemandMemory Memory Demand Memory Demand (GB)
Elastic Memory Metrics
Elastic memory metrics provide reclaimable memory CPU use information for the cluster.
VMware by Broadcom  4433

---
## page 4434

 VMware Cloud Foundation 9.0
Table 1353: Memory Metrics for the Cluster
Metric Key Metric Name Description
ElasticMemory|TotalMemory Total Available Memory Total Available Memory (GB)
ElasticMemory|TotalUsedMemory Actual Used Memory Actual Used Memory (GB)
ElasticMemory|TotalDemandMemory Memory Demand Memory Demand (GB)
CPU Metrics
CPU metrics provide CPU information for the cluster.
Table 1354: CPU Metrics for the Cluster
Metric Key Metric Name Description
cpu|TotalCombinedUsage CPU Load CPU Load
cpu|TotalAvailable CPU Available CPU Available
cpu|TotalAvailable_ghz Available Available (GHz)
cpu|TotalUsage_ghz Used Used (GHz)
cpu|TotalUsage CPU usage CPU usage (%)
Disk Metrics
Disk metrics provide available disk information for the cluster.
Table 1355: Disk Metrics for the Cluster
Metric Key Metric Name Description
Disk|DatabaseStorage|AvgAvailable Average node disk available Average node disk available
Disk|DatabaseStorage|MinAvailable Minimum node disk available Minimum node disk available
Disk|DatabaseStorage|MaxAvailable Maximum node disk available Maximum node disk available
Disk|DatabaseStorage|TotalAvailable Available Available
Disk|DatabaseStorage|Total Total Total
Disk|DatabaseStorage|TotalUsed Used Used
Disk|LogStorage|AvgAvailable Average node disk available Average node disk available
Disk|LogStorage|MinAvailable Minimum node disk available Minimum node disk available
Disk|LogStorage|MaxAvailable Maximum node disk available Maximum node disk available
Disk|LogStorage|TotalAvailable Available Available
Disk|LogStorage|Total Total Total
Disk|LogStorage|TotalUsed Used Used
Persistence Metrics
VCF Operations collects metrics for various persistence resources or service groups.
VMware by Broadcom  4434

---
## page 4435

 VMware Cloud Foundation 9.0
Activity Metrics
Activity metrics relate to the activity framework.
Table 1356: Activity Metrics for Persistence
Metric Key Metric Name Description
Activity|RunningCount Number Running Number Running
Activity|ExecutedCount Number Executed Number Executed
Activity|SucceededCount Number Succeeded Number Succeeded
Activity|FailedCount Number Failed Number Failed
Controller XDB Metrics
Controller metrics relate to the primary database.
Table 1357: Controller XDB Metrics for Persistence
Metric Key Metric Name Description
ControllerXDB|Size Size Size (Bytes)
ControllerXDB|TempDBSize Temporary DB Size Temporary DB Size (Bytes)
ControllerXDB|TotalObjectCount Total Object Count Total Object Count
ControllerXDB|AvgQueryDuration Average Query Duration Average Query Duration (ms)
ControllerXDB|MinQueryDuration Minimum Query Duration Minimum Query Duration (ms)
ControllerXDB|MaxQueryDuration Maximum Query Duration Maximum Query Duration (ms)
ControllerXDB|TotalTransactionCount Total Transaction Count Total Transaction Count
ControllerXDB|LockOperationErrorCount Lock Operation Error Count Lock Operation Error Count
ControllerXDB|DBCorruptionErrorCount DB Corruption Error Count DB Corruption Error Count
ControllerXDB|DBMaxSessionExceededCount DB Maximum Sessions Exceeded Count DB Maximum Sessions Exceeded
Count
ControllerXDB|NumberWaitingForSession Number of operations waiting for a session Number of operations waiting for a
session from the session pool
ControllerXDB|AvgWaitForSessionDuration Average acquisition time from session pool Average acquisition time from session
pool
ControllerXDB|MinWaitForSessionDuration Minimum acquisition time from session
pool
Minimum acquisition time from
session pool
ControllerXDB|MaxWaitForSessionDuration Maximum acquisition time from session
pool
Maximum acquisition time from
session pool
ControllerXDB|TotalGetSessionCount Total requests for a session from the
session pool
Total requests for a session from the
session pool
ControllerXDB|MaxActiveSessionCount Maximum Concurrent Session Count Maximum concurrent session count
during the past collection interval.
VMware by Broadcom  4435

---
## page 4436

 VMware Cloud Foundation 9.0
Alarm SQL Metrics
Alarm metrics relate to the persistence of alerts and symptoms.
Table 1358: Alarm XDB Metrics for Persistence
Metric Key Metric Name Description
AlarmSQL|Size Size (Bytes) Size (Bytes)
AlarmSQL|AvgQueryDuration Average Query Duration (ms) Average Query Duration (ms)
AlarmSQL|MinQueryDuration Minimum Query Duration (ms) Minimum Query Duration (ms)
AlarmSQL|MaxQueryDuration Maximum Query Duration (ms) Maximum Query Duration (ms)
AlarmSQL|TotalTransactionCount Total Transaction Count Total Transaction Count
AlarmSQL|TotalAlarms Alarm Total Object Count Alarm Total Object Count
AlarmSQL|TotalAlerts Alert Total Object Count Alert Total Object Count
AlarmSQL|AlertTableSize Alert Table Size Alert Table Size
AlarmSQL|AlarmTableSize Alarm Table Size Alarm Table Size
Key Value Store Database (KVDB)
KVDB metrics relate to the persistence of storing key-value data.
Metric Key Metric Name Description
KVDB|AvgQueryDuration Average Query Duration Average Query Duration
KVDB|MinQueryDuration Minimum Query Duration Minimum Query Duration
KVDB|MaxQueryDuration Maximum Query Duration Maximum Query Duration
KVDB|TotalTransactionCount Total Transaction Count Total Transaction Count
Historical Inventory Service XDB Metrics
Historical inventory service metrics relate to the persistence of configuration properties and their changes.
Table 1359: Historical XDB Metrics for Persistence
Metric Key Metric Name Description
HisXDB|FunctionCalls|Count HisXDB|
FunctionCalls
Number of Function calls Number of Function calls
HisXDB|FunctionCalls|AvgDuration Average execution time Average execution time
HisXDB|FunctionCalls|MaxDuration Max execution time Max execution time
HisXDB|Size Size Size (Bytes)
HisXDB|TempDBSize Temporary DB Size Temporary DB Size (Bytes)
HisXDB|TotalObjectCount Total Object Count Total Object Count
HisXDB|AvgQueryDuration Average Query Duration Average Query Duration (ms)
HisXDB|MinQueryDuration Minimum Query Duration Minimum Query Duration (ms)
VMware by Broadcom  4436

---
## page 4437

 VMware Cloud Foundation 9.0
Metric Key Metric Name Description
HisXDB|MaxQueryDuration Maximum Query Duration Maximum Query Duration (ms)
HisXDB|TotalTransactionCount Total Transaction Count Total Transaction Count
HisXDB|LockOperationErrorCount Lock Operation Error Count Lock Operation Error Count
HisXDB|DBCorruptionErrorCount DB Corruption Error Count DB Corruption Error Count
HisXDB|DBMaxSessionExceededCount DB Maximum Sessions Exceeded Count DB Maximum Sessions Exceeded
Count
HisXDB|NumberWaitingForSession Number of operations waiting for a session Number of operations waiting for a
session from the session pool
HisXDB|AvgWaitForSessionDuration Average acquisition time from session pool Average acquisition time from session
pool
HisXDB|MinWaitForSessionDuration Minimum acquisition time from session
pool
Minimum acquisition time from
session pool
HisXDB|MaxWaitForSessionDuration Maximum acquisition time from session
pool
Maximum acquisition time from
session pool
HisXDB|TotalGetSessionCount Total requests for a session from the
session pool
Total requests for a session from the
session pool
HisXDB|HisActivitySubmissionCount HIS activity submission count Number of Historical Inventory
Service activities submitted
HisXDB|HisActivityCompletionCount HIS activity completion count Number of Historical Inventory
Service activities completed
HisXDB|HisActivityCompletionDelayAvg HIS activity average completion delay The average amount of time from
activity submission to completion
HisXDB|HisActivityCompletionDelayMax HIS activity maximum completion delay The maximum amount of time from
activity submission to completion
HisXDB|HisActivityAbortedCount HIS activity abort count Number of Historical Inventory
Service activities stopped
 VCF Automation Metrics
VCF Automation collects metrics for objects such as, cloud zone, project, deployment, blueprint, cloud account, user, and
cloud automation services world Instance.
Blueprint Metrics
VCF Automation collects metrics for objects such as blueprint object.
Table 1360: Blueprint Metrics
Property Name Metrics
Summary VMCount
Project Metrics
VCF Automation collects metrics for objects such as project object.
VMware by Broadcom  4437

---
## page 4438

 VMware Cloud Foundation 9.0
Table 1361: Project Metrics
Property Name Metrics
Summary VMCount
Summary TotalDeployments
Summary TotalCloudZones
Summary TotalBlueprints
Summary Metering|Additional price
Summary Metering|CPU Price
Summary Metering|Memory price
Summary Metering|Storage Price
Summary Metering|Total price
Deployment Metrics
VCF Automation collects the metrics for the deployment object.
Table 1362: Deployment Metrics
Property Name Metrics
Summary Metering|Additional price
Summary Metering|CPU Price
Summary Metering|Memory price
Summary Metering|Storage Price
Summary Metering|Total price
Summary Metering|Partial price
Organization Metrics
VCF Automation collects the metrics for the organization object.
Table 1363: Organization Metrics
Property Name Metrics
Summary TotalBlueprints
Summary TotalProjects
Summary VMCount
Summary TotalDeployments
Summary TotalCloudZones
VMware by Broadcom  4438

---
## page 4439

 VMware Cloud Foundation 9.0
 VCF Automation Adapter Metrics
VCF Automation collects the metrics for the adapter object.
Table 1364: VCF Automation Adapter Metrics
Property Name Metrics
Summary TotalCloudZones
Summary VMCount
Summary TotalDeployments
Summary TotalBlueprints
Summary TotalProjects
Cloud Automation Services World Metrics
VCF Automation collects the metrics for the Cloud Automation Services world object.
Table 1365: Cloud Automation Services World Metrics
Property Name Metrics
Summary TotalDeployments
Summary VMCount
Summary TotalCloudZones
Summary TotalProjects
Summary TotalBlueprints
Cloud Automation Services Entity Status Metrics
VCF Automation collects the metrics for the Cloud Automation Services (CAS) entity status object.
Table 1366: Cloud Automation Services Entity Status Metrics
Property Name Metrics
Summary TotalClusters
Cloud Zone Metrics
VCF Automation collects memory, storage, and vCPU limit related metrics at project level on per cloud zone basis.
Cloud Zone Limits Metrics
You can view the memory, storage, and vCPU limit related metrics defined in VCF Automation in VCF Operations. VCF
Operations alerts when the utilisation exceeds configured limits in any of the individual cloud zones.
VMware by Broadcom  4439

---
## page 4440

 VMware Cloud Foundation 9.0
Note:  The resource limits are configured in VCF Automation. For vCenter objects, limits for all resources - vCPU,
memory, and storage - can be configured. However, for public clouds like AWS, Azure, and GCP only vCPU and memory
limits can be configured.
Table 1367: Cloud Zone Limits Metrics
Property Name Metrics Description
Memory allocated (KB) This metric displays the total utilized cloud
zone memory.
Memory Limit (KB) This metric displays the limit set on the
cloud zone memory usage.
Memory Utilized (%) This metric displays the percentage of
memory used out of the memory limit set.
Formula ((Memory allocated (KB)/ Memory
Limit (KB))
Storage allocated (GB) This metric displays the total storage
utilized by the cloud zone.
Storage Limit (GB) This metrics displays the limit set on the
cloud zone storage usage.
Storage Utilized (%) This metric displays the percentage of
storage used out of the storage limit set.
Formula (Storage allocated (KB)/ Storage
Limit (KB))
vCPU allocated This metric displays the total vCPU utilized
by the cloud zone.
vCPU Limit This metrics displays the limit set on the
cloud zone vCPU usage.
Cloud Zone Limits
vCPU Utilized (%) This metric displays the percentage of
vCPU used out of the vCPU limit set.
Formula (vCPU allocated (KB)/ vCPU Limit
(KB))
Summary Metrics for Cloud Zone Centers
Summary metrics provide information about the VM migration as part of workload planning.
Metric Name Description
WLP Displays the VM migration trend as part of workload optimization.
These metrics are deactivated by default. You must activate them
from policies.
• Fail Count: Number of failed VM move attempts in the last daily
cycle.
• Number of runs: The total number of times the WLP was run
during the last daily cycle.
• Success Count: The number of successful VM moves during the
last daily cycle.
VMware by Broadcom  4440

---
## page 4441

 VMware Cloud Foundation 9.0
Metrics for vSAN
VCF Operations collects metrics for vSAN objects.
From the left menu, click Inventory > Inventory Panel (Detailed View) > Integrations > All Objects > vSAN Adapter,
and then select one of the vSAN adapter objects listed and click the Metrics tab.
Disk I/O and Disk Space Metrics for vSAN Disk Groups
The VCF Operations collects the metrics you use to monitor the performance of your vSAN disk groups.
Disk I/O metrics for the vSAN disk groups include:
• Disk I/O|Reads Per Second (IOPS)
• Disk I/O|Writes Per Second (IOPS
• Disk I/O|Max Observed Reads Per Second (IOPS)
• Disk I/O|Max Observed Writes Per Second (IOPS)
• Disk I/O|Throughput Read (bps)
• Disk I/O|Throughput Write (bps)
• Disk I/O|Average Read Latency (ms)
• Disk I/O|Average Write Latency (ms)
• Disk I/O|Total Bus Resets
• Disk I/O|Total Commands Aborted per second
The following Disk I/O metrics are disabled by default:
• Disk I/O|Read Count
• Disk I/O|Write Count
• Disk I/O|Average Device Latency
• Disk I/O|Average Device Read Latency
• Disk I/O|Average Device Write Latency
• Disk I/O|Total Number of Errors
Disk space metrics for vSAN disk groups include:
• Disk Space|Capacity (bytes)
• Disk Space|Used (bytes)
• Disk Space|Usage (%)
Read Cache Metrics for vSAN Disk Groups
The VCF Operations collects metrics and performs capacity trend analysis on a hybrid vSAN read cache. Read Cache
metrics are not collected for a vSAN all-flash configuration.
Read cache metrics for the vSAN disk group include:
• Read Cache|Hit Rate (%)
• Read Cache|Miss Rate Ratio
• Read Cache|Reads Per Second (IOPS)
• Read Cache|Read Latency (ms)
• Read Cache|Writes Per Second (IOPS)
• Read Cache|Write Latency (ms)
The following read cache metrics are disabled by default:
VMware by Broadcom  4441

---
## page 4442

 VMware Cloud Foundation 9.0
• Read Cache|Read I/O Count
• Read Cache|Write I/O Count
Write Buffer Metrics for vSAN Disk Groups
The VCF Operations collects the metrics you use to monitor the write buffer capacity of your vSAN disk groups.
A reasonably balanced system consumes a significant amount of write buffer. Before placing additional workload on the
vSAN, check the write buffer metrics for the vSAN disk group.
• Write Buffer|Capacity (bytes)
• Write Buffer|Free (%)
• Write Buffer|Usage (%)
• Write Buffer|Used (byte)
• Write Buffer|Reads Per Second (IOPS)
• Write Buffer|Read Latency (ms)
• Write Buffer|Writes Per Second (IOPS)
• Write Buffer|Write Latency (ms)
The following write buffer metrics are disabled by default:
• Write Buffer|Read I/O Count
• Write Buffer|Write I/O Count
Congestion Metrics for vSAN Disk Groups
The VCF Operations collects congestion metrics for the vSAN disk group.
• Congestion| Memory Congestion - Favorite
• Congestion| SSD Congestion - Favorite
• Congestion| IOPS Congestion - Favorite
• Congestion| Slab Congestion
• Congestion| Log Congestion
• Congestion| Comp Congestion
Cache De-stage Metrics for vSAN Disk Groups
The VCF Operations collects cache de-stage metrics for the vSAN disk groups.
Cache de-stage metrics include:
• Bytes De-stage from SSD
• Zero-bytes De-stage
Resync Traffic Metrics for vSAN Disk Groups
The VCF Operations collects resync traffic metrics for the vSAN disk groups.
Resync traffic metrics include:
• Read IOPS for Resync Traffic
• Write IOPS for Resync Traffic
• Read Throughput for Resync Traffic
VMware by Broadcom  4442

---
## page 4443

 VMware Cloud Foundation 9.0
• Write Throughput for Resync Traffic
• Read Latency for Resync Traffic
• Write Latency for Resync Traffic
 Metrics for vSAN Cluster
The VCF Operations collects the metrics you use to monitor the performance of your vSAN cluster.
VCF Operations enhances the capacity calculation for vSAN, using the new slack space provided by the new vSAN API.
Cost calculation is still done using the old way which reserves 30% memory for Slack Overhead.
Metrics for vSAN cluster include:
Component Metrics
Component Limit • vSAN|Component Limit|Component Limit Used (%)
• vSAN|Component Limit|Total Component Limit
• vSAN|Component Limit|Used Component Limit
Disk Space • vSAN|Disk Space|Disk Space Used (%)
• vSAN|Disk Space|Total Disk Space (GB)
• vSAN|Disk Space|Used Disk Space (GB)
• vSAN|Disk Space|Usable Capacity (GB)
• vSAN|Disk Space|Oversubscription Capacity (GB)
• vSAN|Disk Space|Oversubscription Ratio
Note:  The oversubscription metrics are applicable only for the vSAN OSA clusters.
Health vSAN|Health|Score
Read Cache • vSAN|Read Cache|Read Cache Reserved (%)
• vSAN|Read Cache|Reserved Read Cache Size (GB)
• vSAN|Read Cache|Total Read Cache Size (GB)
Performance • vSAN|Read Cache|Reads Per Second (IOPS)
• vSAN|Read Cache|Read Throughput (KBps)
• vSAN|Read Cache|Average Read Latency (ms)
• vSAN|Read Cache|Writes Per Second (IOPS)
• vSAN|Read Cache|Write Throughput (KBps)
• vSAN|Read Cache|Average Write Latency (ms)
• vSAN|Read Cache|Congestion
• vSAN|Read Cache|Outstanding I/O
• vSAN|Read Cache|Total IOPS
• vSAN|Read Cache|Total Latency (ms)
• vSAN|Read Cache|Total Throughput (KBps)
Deduplication And Compression
Overview
• vSAN|Deduplication And Compression Overview|Used Before
• vSAN|Deduplication And Compression Overview|Used After
• vSAN|Deduplication And Compression Overview|Savings
• vSAN|Deduplication And Compression Overview|Ratio
Summary • Summary|Number of Storage Pools
• Summary|Number of ESA Disks
• Summary|Number of Cache Disks
• Summary|Total Number of Capacity Disks
• Summary|CPU Workload
• Summary|Memory Workload
VMware by Broadcom  4443

---
## page 4444

 VMware Cloud Foundation 9.0
Component Metrics
• Summary|Total Number of Disk Groups
• Summary|Total Active Alerts Count
• Summary|Total Number of VMs
• Summary|Total Number of Hosts
• Summary|vSAN Cluster Capacity Remaining (%)
• Summary|vSAN Cluster Storage Time Remaining
• Summary|vSAN Capacity Disk Used
• Summary | Total vSAN CPU Used (MHz)
• Summary | Max vSAN CPU Ready
• Summary | Worst VM Disk Latency
KPI • KPI|Max ESA Disk IOPS
• KPI|Max ESA Disk Latency
• KPI|Min Storage Pool Free Capacity
• KPI|Sum Storage Pool Errors
• KPI|Disk Groups Metrics
• KPI|Sum Host VMKernel Packets Dropped
• KPI|Count Disk Group Congestion Above 50
• KPI|Max Disk Group Congestion
• KPI|Sum Disk Group Errors
• KPI|Min Disk Group Capacity Free
• KPI|Min Disk Group Read Cache Hit Rate
• KPI|Min Disk Group Write Buffer Free
• KPI|Max Disk Group Read Cache/Write Buffer Latency
• KPI|Max Capacity Disk Latency
• KPI | Max Capacity Disk IOPS
IO Size • vSAN | Performance | I/O Size (KB)
• vSAN | Performance | Read I/O Size (KB)
• vSAN | Performance | Write I/O Size (KB)
Resynchronization Status ( Metrics
applicable for vSAN 6.7 and later)
• vSAN | Resync | Bytes left to resync (bytes)
• vSAN | Resync | Resyncing Objects
What If Analysis This is an instanced metric
• vSAN | What If | Effective Free Space (GB)
Stretched Cluster • vSAN|Stretched Cluster|Latency Between Sites|Preferred and Secondary (ms)
• vSAN|Stretched Cluster|Latency Between Sites|Preferred and Witness (ms)
• vSAN|Stretched Cluster|Latency Between Sites|Secondary and Witness (ms)
File Share • vSAN|FileServices|totalShareCount
File Service • vSAN | File Services | File Shares Used Disk Space (GB)
• vSAN | File Services | Root FS Used Disk Space (GB)
• vSAN | File Services | File Shares Count
Slack Space • vSAN|Slack Space|Internal Operations Capacity (GB)
• vSAN|Slack Space|Host Rebuild Capacity (GB)
• vSAN|Slack Space|Transient Capacity Used (GB)
 Metrics for vSAN Enabled Host
The VCF Operations collects the metrics you use to monitor the performance of your vSAN enabled host.
VMware by Broadcom  4444

---
## page 4445

 VMware Cloud Foundation 9.0
Metrics for a vSAN enabled host include:
Component Metrics
Component Limit • vSAN|Component Limit|Component Limit Used (%)
• vSAN|Component Limit|Total Component Limit
• vSAN|Component Limit|Used Component Limit
Disk Space • vSAN|Disk Space|Disk Space Used (%)
• vSAN|Disk Space|Total Disk Space (GB)
• vSAN|Disk Space|Used Disk Space (GB)
Read Cache • vSAN|Read Cache|Read Cache Reserved (%)
• vSAN|Read Cache|Reserved Read Cache Size (GB)
• vSAN|Read Cache|Total Read Cache Size (GB)
Performance Metrics
• Network • vSAN|Performance|Network|Inbound Packets Loss Rate
• vSAN|Performance|Network|Outbound Packets Loss Rate
• vSAN|Performance|Network|<vnic>|Inbound Packets Loss rate (%)
• vSAN|Performance|Network|<vnic>|Outbound Packets Loss Rate (%)
• vSAN|Performance|Network|<vnic>|Inbound Packets Per second
• vSAN|Performance|Network|<vnic>|Outbound Packets Per second
• vSAN|Performance|Network|<vnic>|Throughput Inbound (KBps)
• vSAN|Performance|Network|<vnic>|Throughput Outbound (KBps)
• CPU Utilization • vSAN | Performance | CPU | Ready (%)
• vSAN | Performance | CPU | Usage (%)
• vSAN | Performance | CPU | Used (MHz)
• vSAN | Performance | CPU | Core Utilization (%) (For Hyper-Threading Technology)
• PCPU Utilization • vSAN | Performance | PCPU | Ready (%)
• vSAN | Performance | CPU | PCPU Usage (%)
• Memory • vSAN | Performance | Memory | Usage (%)
• vSAN | Performance | Memory | Used (GB)
 Metrics for vSAN Datastore
The VCF Operations collects the metrics you use to monitor the performance of your vSAN datastore.
Datastore I/O metrics for vSAN datastore include:
• Datastore I/O|Reads Per Second (IOPS)
• Datastore I/O|Read Rate (KBps)
• Datastore I/O|Read Latency (ms)
• Datastore I/O|Writes Per Second (IOPS)
• Datastore I/O|Write Rate (KBps)
• Datastore I/O|Write Latency (ms)
• Datastore I/O|Outstanding I/O requests
• Datastore I/O|Congestion
• Capacity | Usable Capacity
VMware by Broadcom  4445

---
## page 4446

 VMware Cloud Foundation 9.0
 Metrics for vSAN Cache Disk
The VCF Operations collects the metrics you use to monitor the performance of your vSAN cache disk.
Metrics for vSAN cache disk include:
Component Metrics
Performance • Performance|Bus Resets
• Performance|Commands Aborted Per Second
The following performance metrics are disabled by default:
• Performance|Device Latency (ms)
• Performance|Device Read Latency (ms)
• Performance|Device Write Latency (ms)
• Performance|Read Requests Per Second
• Performance|Average Reads Per Second
• Performance|Write Requests Per Second
• Performance|Average Writes Per Second
• Performance|Read Rate
• Performance|Write Rate
• Performance|Usage
• Performance|HDD Errors
SCSI SMART Statistics
Note:  SMART data
collection is disabled by
default. To enable SMART
data collection, ensure that
the Enable SMART data
collection instance
identifier is set to true. For
proper data collection, ensure
that ESXi hosts in your
vCenter Server inventory
have CIM service enabled
and CIM providers for each
SMART metric installed.
• SCSI SMART Statistics|Health Status
• SCSI SMART Statistics|Media Wearout Indicator
• SCSI SMART Statistics|Write Error Count
• SCSI SMART Statistics|Read Error Count
• SCSI SMART Statistics|Power on Hours
• SCSI SMART Statistics|Reallocated Sector Count
• SCSI SMART Statistics|Raw Read Error Rate
• SCSI SMART Statistics|Drive Temperature
• SCSI SMART Statistics|Maximum Observed Drive Temperature
• SCSI SMART Statistics|Drive Rated Max Temperature
• SCSI SMART Statistics|Write Sectors TOT Count
• SCSI SMART Statistics|Read Sectors TOT Count
• SCSI SMART Statistics|Initial Bad Block Count
• SCSI SMART Statistics|Worst Media Wearout Indicator
• SCSI SMART Statistics|Worst Write Error Count
• SCSI SMART Statistics|Worst Read Error Count
• SCSI SMART Statistics|Worst Power-on Hours
• SCSI SMART Statistics|Power Cycle Count
• SCSI SMART Statistics|Worst Power Cycle Count
• SCSI SMART Statistics|Worst Reallocated Sector Count
• SCSI SMART Statistics|Worst Raw Read Error Rate
• SCSI SMART Statistics|Worst Driver Rated Max Temperature
• SCSI SMART Statistics|Worst Write Sectors TOT Count
• SCSI SMART Statistics|Worst Read Sectors TOT Count
• SCSI SMART Statistics|Worst Initial Bad Block Count
Capacity • vSAN|Health|Capacity|Total Disk Capacity (GB)
• vSAN|Health|Capacity|Used Disk Capacity (GB)
Congestion Health • vSAN|Health|Congestion Health|Congestion Value
Performance • vSAN|Performance|Physical Layer Reads Per Second
VMware by Broadcom  4446

---
## page 4447

 VMware Cloud Foundation 9.0
Component Metrics
• vSAN|Performance|Physical Layer Writes Per Second
• vSAN|Performance|Physical Layer Read Throughput (KBps)
• vSAN|Performance|Physical Layer Write Throughput (KBps)
• vSAN|Performance|Physical Layer Read Latency (ms)
• vSAN|Performance|Physical Layer Write Latency (ms)
• vSAN|Performance|Physical Layer Read Count
• vSAN|Performance|Physical Layer Write Count
• vSAN|Performance|Device Average Latency (ms)
• vSAN|Performance|Guest Average Latency (ms)
 Metrics for vSAN Capacity Disk
The VCF Operations collects the metrics you use to monitor the performance of your vSAN capacity disk.
Metrics for vSAN capacity disk include:
Component Metrics
Performance • Performance|Bus Resets
• Performance|Commands Aborted Per Second
The following performance metrics are disabled by default:
•
• Performance|Device Latency (ms)
• Performance|Device Read Latency (ms)
• Performance|Device Write Latency (ms)
• Performance|Read Requests Per Second
• Performance|Average Reads Per Second
• Performance|Write Requests Per Second
• Performance|Average Writes Per Second
• Performance|Read Rate
• Performance|Write Rate
• Performance|Usage
• Performance|HDD Errors
SCSI SMART Statistics
Note:  SMART data collection
is disabled by default. To enable
SMART data collection, ensure
that the Enable SMART data
collection instance identifier is
set to true. For proper data collection,
ensure that ESXi hosts in your vCenter
Server inventory have CIM service
enabled and CIM providers for each
SMART metric installed.
• SCSI SMART Statistics|Health Status
• SCSI SMART Statistics|Media Wearout Indicator
• SCSI SMART Statistics|Write Error Count
• SCSI SMART Statistics|Read Error Count
• SCSI SMART Statistics|Power on Hours
• SCSI SMART Statistics|Reallocated Sector Count
• SCSI SMART Statistics|Raw Read Error Rate
• SCSI SMART Statistics|Drive Temperature
• SCSI SMART Statistics|Maximum Observed Drive Temperature
• SCSI SMART Statistics|Drive Rated Max Temperature
• SCSI SMART Statistics|Write Sectors TOT Count
• SCSI SMART Statistics|Read Sectors TOT Count
• SCSI SMART Statistics|Initial Bad Block Count
• SCSI SMART Statistics|Worst Media Wearout Indicator
• SCSI SMART Statistics|Worst Write Error Count
• SCSI SMART Statistics|Worst Read Error Count
VMware by Broadcom  4447

---
## page 4448

 VMware Cloud Foundation 9.0
Component Metrics
• SCSI SMART Statistics|Worst Power-on Hours
• SCSI SMART Statistics|Power Cycle Count
• SCSI SMART Statistics|Worst Power Cycle Count
• SCSI SMART Statistics|Worst Reallocated Sector Count
• SCSI SMART Statistics|Worst Raw Read Error Rate
• SCSI SMART Statistics|Worst Driver Rated Max Temperature
• SCSI SMART Statistics|Worst Write Sectors TOT Count
• SCSI SMART Statistics|Worst Read Sectors TOT Count
• SCSI SMART Statistics|Worst Initial Bad Block Count
Capacity • vSAN|Health|Total Disk Capacity (GB)
• vSAN|Health|Used Disk Capacity (GB)
• vSAN|FileServices|FileSharesUsedDiskSpace
• vSAN|FileServices|RootFsUsedDiskSpace
Congestion Health vSAN|Health|Congestion Value
Performance • vSAN|Performance|Physical Layer Reads Per Second
• vSAN|Performance|Physical Layer Writes Per Second
• vSAN|Performance|Physical Layer Read Throughput (KBps)
• vSAN|Performance|Physical Layer Write Throughput (KBps)
• vSAN|Performance|Physical Layer Read Latency (ms)
• vSAN|Performance|Physical Layer Write Latency (ms)
• vSAN|Performance|Physical Layer Read Count
• vSAN|Performance|Physical Layer Write Count
• vSAN|Performance|Device Average Latency (ms)
• vSAN|Performance|Guest Average Latency (ms)
• vSAN|Performance|vSAN Layer Reads Per Second
• vSAN|Performance|vSAN Layer Writes Per Second
• vSAN|Performance|vSAN Layer Read Latency (ms)
• vSAN|Performance|vSAN Layer Write Latency (ms)
• vSAN|Performance|vSAN Layer Read Count
• vSAN|Performance|vSAN Layer Write Count
• vSAN | Performance | vSAN Layer Total IOPS
Properties for vSAN capacity disk include:
• Name
• Size
• Vendor
• Type
• Queue Depth
Metrics for vSAN Fault Domain Resource Kind
The VCF Operations collects the metrics you use to monitor the performance of your vSAN stretched cluster with fault
domain.
Metrics for vSAN fault domain resource kind includes:
VMware by Broadcom  4448

---
## page 4449

 VMware Cloud Foundation 9.0
• CPU
– Demand
• Demand (MHz)
• Demand without overhead (MHz)
• Overhead (MHz)
• Reserved Capacity (MHz)
• Total Capacity (MHz)
• VM CPU Usage (MHz)
• Workload (%)
• Disk Space
– Demand
• Workload (%)
• Memory
– Contention (KB)
– Demand
• Host Usage (KB)
• Machine Demand (KB)
• Reserved Capacity (KB)
• Total Capacity (KB)
• Utilization (KB)
• Workload (%)
• vSAN
– Disk Space
• Total Disk Space (GB)
• Used Disk Space (GB)
 Metrics for vSAN World
The VCF Operations collects the metrics you use to monitor the performance of your vSAN world.
Metrics for vSAN world include:
• Summary|Total Number of VMs
• Summary|Total Number of Hosts
• Summary|Total IOPS
• Summary|Total Latency
• Summary|Total Number of Clusters
• Summary|Total Number of DiskGroups
• Summary|Total Number of Cache Disks
• Summary|Total Number of Capacity Disks
• Summary|Total Number of Datastores
• Summary|Total vSAN Disk Capacity (TB)
• Summary|Total vSAN Disk Capacity Used (TB)
• Summary|Remaining Capacity (TB)
• Summary|Remaining Capacity (%)
• Summary|Total Savings by Deduplication and Compression (GB)
VMware by Broadcom  4449

---
## page 4450

 VMware Cloud Foundation 9.0
Metrics for vSAN File Server
The VCF Operations collects the metrics you use to monitor the performance of your vSAN File Server.
Metrics for vSAN File Server
Component Metrics
File Server • vSAN | Disk Space File Shares Used Disk Space (GB)
• vSAN | Summary | File Shares Count
Metrics for vSAN File Share
The VCF Operations collects the metrics you use to monitor the performance of your vSAN File Share.
Metrics for vSAN File Share
Component Metrics
Disk Space • vSAN | Disk Space | Used Disk Space (GB)
Read Performance • vSAN | Performance | Read Throughput Requested (MBps)
• vSAN | Performance | Read Throughput Transferred (MBps)
• vSAN | Performance | Read IOPS
• vSAN | Performance | Read Latency (ms)
Write Performance • vSAN | Performance | Write Throughput Requested (MBps)
• vSAN | Performance | Write Throughput Transferred (MBps)
• vSAN | Performance | Write IOPS
• vSAN | Performance | Write Latency (ms)
Capacity Model for vSAN Objects
The capacity model introduced in VCF Operations 6.7 now extends the support for vSAN objects like, vSAN cluster, Fault
domains, and Cache/Capacity disks. The Capacity tab provides Time Remaining data for the selected vSAN cluster, Fault
domain, Cache/Capacity Disk objects. The information is presented in a graphical format.
Where You Find the Capacity Tab
In the menu, click Environment, then select a group, custom data center, application, or inventory object. The Object
details page appears. Click the Capacity tab.
The VCF Operations defines the capacity model for the following vSAN resource containers:
• vSAN Cluster
– Disk Space
• vSAN Fault Domain
– CPU
– Memory
– Disk Space
• vSAN Cache/Capacity Disk
– Disk Space
VMware by Broadcom  4450

---
## page 4451

 VMware Cloud Foundation 9.0
Understanding the Capacity Tab
For the selected vSAN resource, the capacity tab lists the capacity used and Time Remaining until the associated CPU,
memory, and disk space resources, respectively, run out.
• If you select the vSAN cluster, the capacity tab lists the capacity used and time remaining until the associated disk
space runs out.
• If you select the vSAN Fault Domain, the capacity tab lists the capacity used and time remaining until the associated
CPU, memory, and disk space resources run out.
• If you select the vSAN Cache/Capacity Disk Space, the capacity tab lists capacity used and time remaining until the
associated disk space runs out.
The available graph depicts - for your choice of CPU, memory, or disk space - the amount of resource used, plotted
against time. A line on the graph shows 100 percent usable capacity and a trend line projects how swiftly resource use is
approaching 100 percent. The time line shows when the selected resource is to reach capacity.
Metrics for vSAN Storage Pool
The VCF Operations collects the metrics you use to monitor the performance of your vSAN storage pool.
Component Metrics
Disk I/O • Disk I/O|Physical Layer Read Latency (µs)
• Disk I/O|Physical Layer Write Latency (µs)
• Disk I/O|Physical Layer Read IOPS
• Disk I/O|Physical Layer Write IOPS
• Disk I/O|Physical Layer Read Throughput (KBps)
• Disk I/O|Physical Layer Write Throughput (KBps)
• Disk I/O|Total Bus Resets
• Disk I/O|Total IOPS Aborted
• Disk I/O|Number of Errors
Disk Space • Disk Space|Capacity (bytes)
• Disk Space|Usage (%)
• Disk Space|Used (bytes)
• Disk Space|Workload(%)
Metrics for vSAN ESA Disk
The VCF Operations collects the metrics you use to monitor the performance of your vSAN ESA disk.
Component Metrics
vSAN Health|Capacity • vSAN|Health|Capacity|Total Disk Capacity (GB)
• vSAN|Health|Capacity|Used Disk Capacity (GB)
• vSAN|Health|Capacity|Used Disk Capacity (%)
• Disk I/O|Physical Layer Write IOPS
• Disk I/O|Physical Layer Read Throughput (KBps)
• Disk I/O|Physical Layer Write Throughput (KBps)
• Disk I/O|Total Bus Resets
• Disk I/O|Total IOPS Aborted
• Disk I/O|Number of Errors
vSAN Health|Congestion vSAN Health|Congestion Health|Congestion Value
VMware by Broadcom  4451

---
## page 4452

 VMware Cloud Foundation 9.0
Component Metrics
vSAN Performance • vSAN|Performance|Physical Layer Read IOPS
• vSAN|Performance|Physical Layer Write IOPS
• vSAN|Performance|Physical Layer Read Throughput (KBps)
• vSAN|Performance|Physical Layer Write Throughput (KBps)
• vSAN|Performance|Physical Layer Read Latency (µs)
• vSAN|Performance|Physical Layer Write Latency (µs)
• vSAN|Performance|Physical Layer Read Count
• vSAN|Performance|Physical Layer Write Count
• vSAN|Performance|Device Latency (µs)
• vSAN|Performance|Guest Latency (µs)
• vSAN|Performance|vSAN Layer Read IOPS
• vSAN|Performance|vSAN Layer Write IOPS
• vSAN|Performance|vSAN Layer Total IOPS
• vSAN|Performance|vSAN Layer Average Read Latency (µs)
• vSAN|Performance|vSAN Layer Average Write Latency (µs)
• vSAN|Performance|vSAN Layer Read Throughput (KBps)
• vSAN|Performance|vSAN Layer Write Throughput (KBps)
Metrics in NSX Adapter
The NSX adapter collects metrics for objects within its plug-in.
Table 1368: Metrics in the NSX On-Premise
Resource Metrics Metric Keys
Management Cluster System Capacity
• Max Supported Count
• Max Threshold Percentage
• Min Threshold Percentage
• Usage Count
• Usage Count Percentage
• Severity
System Capacity Keys
• System Capacity|<Object_Kind>|MaxSupportedCount
• System Capacity|<Object_Kind>|
MaxThresholdPercentage
• System Capacity|<Object_Kind>|
MinThresholdPercentage
• System Capacity|<Object_Kind>|UsageCount
• System Capacity|<Object_Kind>|
UsageCountPercentage
• System Capacity|<Object_Kind>|Severity
Transport Node • CPU|
– CPU Cores
– DPDK CPU Cores
– DPDK CPU Core Average Usage
– DPDK CPU Core Highest Usage
– Non-DPDK CPU Core Average Usage
– Non-DPDK CPU Core Highest Usage
• Memory
– Total
– Used
– Cache
– Total Swap
– Used Swap
• CPU Metric Keys
– Cpu|Cores
– Cpu|DPDKCores
– Cpu|AvgDpdkCpuCoreUsage
– Cpu|HighDpdkCpuCoreUsage
– Cpu|AvgNonDpdkCpuCoreUsage
– Cpu|HighNonDpdkCpuCoreUsage
• Memory metric keys
– Memory|Total
– Memory|Used
– Memory|Cache
– Memory|Total Swap
– Memory|Used Swap
VMware by Broadcom  4452

---
## page 4453

 VMware Cloud Foundation 9.0
Resource Metrics Metric Keys
File Systems|<FileSystemMount>|Used FileSystems|Used
Statistics|Interface|<InterfaceID>
• Received Data (bytes)
• Received Packets dropped
• Received Packets errors
• Received Framing errors
• Received Packets
• Transmitted Data (bytes)
• Transmitted Packets dropped
• Transmitted Packets errors
• Transmitted carrier losses detected
• Transmitted Packets
• Transmitted Collisions detected
Statistics Metric Keys
• stats|Interface|RxData
• stats|Interface|RxDropped
• stats|Interface|RxErrors
• stats|Interface|RxFrame
• stats|Interface|RxPackets
• stats|Interface|TxData
• stats|Interface|TxDropped
• stats|Interface|TxErrors
• stats|Interface|TxCarrier
• stats|Interface|TxPackets
• stats|Interface|TxColls
Load Balancer
Service
• CPU Usage(%)
• Memory Usage(%)
• Active Transport Nodes
• Standby Transport Nodes
• Sessions:
– L4Average
– L4Current
– L4Maximum
– L4Total
– L7Average
– L7Current
– L7Maximum
– L7Total
• CPU Usage
• Memory Usage
• Active Transport Nodes
• Standby Transport Nodes
• Sessions|L4Average
• Sessions|L4Current
• Sessions|L4Maximum
• Sessions|L4Total
• Sessions|L7Average
• Sessions|L7Current
• Sessions|L7Maximum
• Sessions|L7Total
Load Balancer Virtual
Server
• Statistics
– Bytes|Inbound Bytes Total
– Bytes|Average Inbound Bytes Per Second
– Bytes|Outbound Bytes Total
– Bytes|Average Outbound Bytes Per
Second
– Http|Http Request Rate
– Http|Http Requests
– Packets|Inbound Packets Total
– Packets|Inbound Packets Rate
– Packets|Outbound Packets Total
– Packets|Outbound Packets Rate
– Packets|Dropped
• Sessions
– Average Current Sessions Per Second
– Current Sessions
– Maximum Sessions
– Dropped Sessions
– Total Sessions
• Statistics metric keys
– stats|Bytes|Inbound
– stats|Bytes|InboundRate
– stats|Bytes|Outbound
– stats|Bytes|OutboundRate
– stats|Http|RequestRate
– stats|Http|Requests
– stats|Packets|Inbound
– stats|Packets|InboundRate
– stats|Packets|Outbound
– stats|Packets|OutboundRate
– stats|Packets|Dropped
• Sessions metric keys
• – Sessions|CurrentRate
– Sessions|Current
– Sessions|Maximum
– Sessions|Dropped
– Sessions|Total
VMware by Broadcom  4453

---
## page 4454

 VMware Cloud Foundation 9.0
Resource Metrics Metric Keys
Load Balancer Pool • Statistics
– Bytes|Inbound Bytes Total
– Bytes|Average Inbound Bytes Per Second
– Bytes|Outbound Bytes Total
– Bytes|Average Outbound Bytes Per
Second
– Http|Http Request Rate
– Http|Http Requests
– Packets|Inbound Packets Total
– Packets|Inbound Packets Rate
– Packets|Outbound Packets Total
– Packets|Outbound Packets Rate
– Packets|Dropped
• Sessions
– Average Current Sessions Per Second
– Current Sessions
– Maximum Sessions
– Dropped Sessions
– Total Sessions
• Statistics metric keys
– stats|Bytes|Inbound
– stats|Bytes|InboundRate
– stats|Bytes|Outbound
– stats|Bytes|OutboundRate
– stats|Http|RequestRate
– stats|Http|Requests
– stats|Packets|Inbound
– stats|Packets|InboundRate
– stats|Packets|Outbound
– stats|Packets|OutboundRate
– stats|Packets|Dropped
• Sessions metric keys
– Sessions|CurrentRate
– Sessions|Current
– Sessions|Maximum
– Sessions|Dropped
– Sessions|Total
Management Services • Service Monitor Process ID
• Service Monitor Runtime state
• Service Process ID
• Service Runtime State
• ServiceMonitorProcessId
• ServiceMonitorRuntimeState
• ServiceProcessIds
• ServiceRuntimeState
Statistics
• Received Data (bytes)
• Received Packets dropped
• Received Packets
• Transmitted Data (bytes)
• Transmitted Packets dropped
• Transmitted Packets
Statistics metric keys
• stats|RxData
• stats|RxDropped
• stats|RxPackets
• stats|TxData
• stats|TxDropped
• stats|TxPackets
Logical Router
Configuration Maximums
• Router Port Count
• ARP Entries Count
• Tier 1 Router Count
• Route Map Count
• Route Maps|<RouteMapName:RouteMapId>|
Rule Count
• Prefix List Count
• IP Prefix Lists|
<IPPrefixListName:IPPrefixListId>|Prefix List
Entries Count
Configuration Maximums metric keys
• configMax|routerPortCount
• configMax|routerArpEntryCount
Note:  Metric applicable for T1 router.
• configMax|tier1RouterCount
• configMax|routeMapCount
• configMax|RouteMaps|routeMapRuleCount
Note:  Metric applicable for T0 router.
• configMax|prefixListCount
• configMax|IPPrefixLists|prefixListEntriesCount
Note:  Metric applicable for T0 and T1 router.
Logical Switch Statistics
• Inbound Bytes Total
• Inbound Bytes Dropped
• Inbound Bytes Throughput
• Outbound Bytes Total
• Outbound Bytes Dropped
• Outbound Bytes Throughput
• Inbound Packets Total
Metric keys
• stats|IngressBytes
• stats|IngressBytesDropped
• stats|IngressBytesThroughput
• stats|IngressPackets
• stats|IngressPacketsDropped
• stats|IngressPacketsThroughput
• stats|EgressBytes
VMware by Broadcom  4454

---
## page 4455

 VMware Cloud Foundation 9.0
Resource Metrics Metric Keys
• Inbound Packets Dropped
• Inbound Packets Throughput
• Outbound Packets Total
• Outbound Packets Dropped
• Outbound Packets Throughput
• stats|EgressBytesDropped
• stats|EgressBytesThroughput
• stats|EgressPackets
• stats|EgressPacketsDropped
• stats|EgressPacketsThroughput
Logical Switch Group Configuration Maximums
• Logical Segment Count
Metric keys
• configMax|LogicalSegmentCount
Management
Appliances
Management Node Count Management node count
• File Systems|<FileSystemMount>
– File System Id
– File System Type
– Total (KB)
– Used(KB)
– Used(%)
• File Systems Metric Keys
– FileSystems|<FileSystemMount>|FileSystemId
– FileSystems|<FileSystemMount>|Type
– FileSystems|<FileSystemMount>|Total
– FileSystems|<FileSystemMount>|Used
– FileSystems|<FileSystemMount>|usedPercentage
Network Interfaces|<InterfaceID>|
• Received Data|Bits per second
• Received Data|Cumulative(bytes)
• Received Framing Errors|Cumulative
• Received Framing Errors|Per second
• Received Packets|Cumulative
• Received Packets|Per Second
• Received Packets Dropped|Cumulative
• Received Packets Dropped|Per second
• Received Packets Error|Cumulative
• Received Packets Error|Per second
• Transmitted Carrier losses detected|
Cumulative
• Transmitted Carrier losses detected|Per
second
• Transmitted Collisions detected|Cumulative
• Transmitted Collisions detected|Per second
• Transmitted Data|Bits per second
• Transmitted Data|Cumulative(bytes)
• Transmitted Packets|Cumulative
• Transmitted Packets|Per second
• Transmitted Packets Dropped|Cumulative
• Transmitted Packets Dropped|Per second
• Transmitted Packets errors|Cumulative
• Transmitted Packets errors|Per second
Network Interface metric keys
• Interfaces|<InterfaceID>|RxData|BitsPerSecond
• Interfaces|<InterfaceID>|RxData|Cumulative
• Interfaces|<InterfaceID>|RxFrame|Cumulative
• Interfaces|<InterfaceID>|RxFrame|PerSecond
• Interfaces|<InterfaceID>|RxPackets|Cumulative
• Interfaces|<InterfaceID>|RxPackets|PerSecond
• Interfaces|<InterfaceID>|RxDropped|Cumulative
• Interfaces|<InterfaceID>|RxDropped|PerSecond
• Interfaces|<InterfaceID>|RxErrors|Cumulative
• Interfaces|<InterfaceID>|RxErrors|PerSecond
• Interfaces|<InterfaceID>|TxCarrier|Cumulative
• Interfaces|<InterfaceID>|TxCarrier|PerSecond
• Interfaces|<InterfaceID>|TxColls|Cumulative
• Interfaces|<InterfaceID>|TxColls|PerSecond
• Interfaces|<InterfaceID>|TxData|BitsPerSecond
• Interfaces|<InterfaceID>|TxData|Cumulative
• Interfaces|<InterfaceID>|TxPackets|Cumulative
• Interfaces|<InterfaceID>|TxPackets|PerSecond
• Interfaces|<InterfaceID>|TxDropped|Cumulative
• Interfaces|<InterfaceID>|TxDropped|PerSecond
• Interfaces|<InterfaceID>|TxErrors|Cumulative
• Interfaces|<InterfaceID>|TxErrors|PerSecond
CPU
• CPU Cores
• DPDK CPU Cores
• DPDK CPU Core Average Usage
• DPDK CPU Core Highest Usage
• Non-DPDK CPU Core Average Usage
• Non-DPDK CPU Core Highest Usage
CPU Metric Keys
• Cpu|Cores
• Cpu|DPDKCores
• Cpu|AvgDpdkCpuCoreUsage
• Cpu|HighDpdkCpuCoreUsage
• Cpu|AvgNonDpdkCpuCoreUsage
• Cpu|HighNonDpdkCpuCoreUsage
Manager Node
Memory
• Total
Memory metric keys
• Memory|Total
VMware by Broadcom  4455

---
## page 4456

 VMware Cloud Foundation 9.0
Resource Metrics Metric Keys
• Used
• Cache
• Total Swap
• Used Swap
• Memory|Used
• Memory|Cache
• Memory|TotalSwap
• Memory|UsedSwap
Controller Cluster • Controller Node Count
• Cluster Status|Controller Cluster Status
• Cluster Status|Management cluster Status
Controller cluster metrics keys
• Cluster Status|Controller Node Count
• ClusterStatus|ControllerClusterStatus
• ClusterStatus|ManagementClusterStatus
Note:  These metrics are not collected for NSX version
above 2.4
Controller Node • Connectivity Status|Cluster Connectivity
• Connectivity Status|Manager Connectivity
• File System ID
• File System Type
• Total(KB)
• Used(KB)
• Used(%)
• Network Interfaces|<InterfaceID>|
• Received Data|Bits per second
• Received Data|Cumulative(bytes)
• Received Framing Errors|Cumulative
• Received Framing Errors|Per second
• Received Packets|Cumulative
• Received Packets|Per Second
• Received Packets Dropped|Cumulative
• Received Packets Dropped|Per second
• Received Packets Error|Cumulative
• Received Packets Error|Per second
• Transmitted Carrier losses detected|
Cumulative
• Transmitted Carrier losses detected|Per
second
• Transmitted Collisions detected|Cumulative
• Transmitted Collisions detected|Per second
• Transmitted Data|Bits per second
• Transmitted Data|Cumulative(bytes)
• Transmitted Packets|Cumulative
• Transmitted Packets|Per second
• Transmitted Packets Dropped|Cumulative
• Transmitted Packets Dropped|Per second
• Transmitted Packets errors|Cumulative
• Transmitted Packets errors|Per second
Note:  These metrics are not collected for NSX version
above 2.4
• ConnectivityStatus|ClusterConnectivity
• ConnectivityStatus|ManagerConnectivity
• FileSystems|<FileSystemMount>|FileSystemId
• FileSystems|<FileSystemMount>|Type
• FileSystems|<FileSystemMount>|Total
• FileSystems|<FileSystemMount>|Used
• FileSystems|<FileSystemMount>|usedPercentage
• Interfaces|<InterfaceID>|RxData|BitsPerSecond
• Interfaces|<InterfaceID>|RxData|Cumulative
• Interfaces|<InterfaceID>|RxFrame|Cumulative
• Interfaces|<InterfaceID>|RxFrame|PerSecond
• Interfaces|<InterfaceID>|RxPackets|Cumulative
• Interfaces|<InterfaceID>|RxPackets|PerSecond
• Interfaces|<InterfaceID>|RxDropped|Cumulative
• Interfaces|<InterfaceID>|RxDropped|PerSecond
• Interfaces|<InterfaceID>|RxErrors|Cumulative
• Interfaces|<InterfaceID>|RxErrors|PerSecond
• Interfaces|<InterfaceID>|TxCarrier|Cumulative
• Interfaces|<InterfaceID>|TxCarrier|PerSecond
• Interfaces|<InterfaceID>|TxColls|Cumulative
• Interfaces|<InterfaceID>|TxColls|PerSecond
• Interfaces|<InterfaceID>|TxData|BitsPerSecond
• Interfaces|<InterfaceID>|TxData|Cumulative
• Interfaces|<InterfaceID>|TxPackets|Cumulative
• Interfaces|<InterfaceID>|TxPackets|PerSecond
• Interfaces|<InterfaceID>|TxDropped|Cumulative
• Interfaces|<InterfaceID>|TxDropped|PerSecond
• Interfaces|<InterfaceID>|TxErrors|Cumulative
• Interfaces|<InterfaceID>|TxErrors|PerSecond
Router Service RouterService • BGP Neighbor:<BGPNeighborName>|Service Router
State|Connection State
• BGP Neighbor:<BGPNeighborName>|Advertised
Routes|Transport Nodes:<TransportNodeIP>|Advertised
Route Count
• BGP Neighbor:<BGPNeighborName>|Advertised
Routes|Transport Nodes:<TransportNodeIP>Routes|
ASPath
VMware by Broadcom  4456

---
## page 4457

 VMware Cloud Foundation 9.0
Resource Metrics Metric Keys
• BGP Neighbor:<BGPNeighborName>|Advertised
Routes|Transport Nodes:<TransportNodeIP>Routes|
Next Hop
Table 1369: Metrics in the NSX on VMware Cloud on AWS
Resource Metrics Metric Keys
Logical Router The following metrics are specify
to Tier 0 Router.
Statistics | Interface
• Received Data (Bytes)
• Received Packets
• Received Packets Dropped
• Transmitted Data
• Transmitted Received Data
(Bytes)
• Transmitted Received Packets
• Transmitted Received Packets
Dropped
Stats Metrics
Statistics | Interface
• stats|Interface|RxData
• stats|Interface|RxPackets
• stats|Interface|RxDropped
• stats|Interface|TxData
• stats|Interface|TxPackets
• stats|Interface|TxDropped
Note:  These metrics are only for Tier 0 Router.
Firewall Section Group Configuration Maximums
• Distributed Firewall Section
Count
• Distributed Firewall Rule
Count
• MGW Gateway Firewall Rule
Count
• CGW Gateway Firewall Rule
Count
• Distributed Application
Firewall Rule Count
• Distributed Application
Firewall Section Count
• Distributed Environment
Firewall Rule Count
• Distributed Environment
Firewall Section Count
• Distributed Infrastructure
Firewall Rule Count
• Distributed Infrastructure
Firewall Section Count
• Distributed Emergency
Firewall Rule Count
• Distributed Emergency
Firewall Section Count
• Distributed Ethernet Firewall
Rule Count
• Distributed Ethernet Firewall
Section Count
Configuration metric keys
• configMax|MaxDistributedFirewallSections
• configMax|MaxDistributedFirewallRules
• configMax|MaxMGWGatewayFirewallRules
• configMax|MaxCGWGatewayFirewallRules
• configMax|MaxDistributedApplicationFirewallRules
• configMax|MaxDistributedApplicationFirewallSections
• configMax|MaxDistributedEnvironmentFirewallRules
• configMax|MaxDistributedEnvironmentFirewallSections
• configMax|MaxDistributedInfrastructureFirewallRules
• configMax|MaxDistributedInfrastructureFirewallSections
• configMax|MaxDistributedEmergencyFirewallRules
• configMax|MaxDistributedEmergencyFirewallSections
• configMax|MaxDistributedEthernetFirewallRules
• configMax|MaxDistributedEthernetFirewallSections
Note:  These metrics are only for NSX on VMware Cloud on
AWS. For NSX on-premise, the values for these metrics is
shown as zero.
VMware by Broadcom  4457

---
## page 4458

 VMware Cloud Foundation 9.0
Resource Metrics Metric Keys
Note:  These metrics are only for
NSX on VMware Cloud on AWS.
For NSX on-premise, the values
for these metrics show zero.
Logical Switch Group Configuration Maximums
• Logical Segment Count
• Extended Network Count
Metric Keys
• configMax|LogicalSegmentCount
• configMax|ExtendedNetworkcount
Note:  The metric (configMax|ExtendedNetworkcount) is only
for NSX on VMware Cloud on AWS. For NSX on-premise, its
value is zero.
Green Score Metrics
Green Score metrics are collected for virtual machine, host system, cluster compute resource, vSphere World, and
Organization object types.
Metric Names
Metric Name Object Type Description
Power|Total Energy (Wh) Virtual Machine Total energy used.
Formula:
Total Energy (Wh) = Sum(Power|Energy
(Joule))/3600
Power|Total Energy (Wh) Host System Total energy used.
Formula:
Total Energy (Wh) = Sum(Power|Energy
(Joule))/3600
Sustainability|CO₂ Emission (kg) Cluster Compute Resource Estimated carbon dioxide emissions.
Calculated as power consumption* CO₂
Emission rate
Formula:
CO₂ Emission (kg) = Sum(Host
System(Power|Total Energy(Wh)))/1000 *
0.672
Sustainability|CO₂ Emission before
Virtualization (kg)
Cluster Compute Resource Estimated carbon dioxide emissions
before virtualization, assuming that power
consumption per physical server is 100W,
reflecting a low end hardware specification.
Formula:
CO₂ Emission before Virtualization (kg) =
Summary|Number of Running VMs * 0.1 *
0.672
Sustainability|CO₂ Emission by Idle VMs
(kg)
Cluster Compute Resource Total estimated carbon dioxide emission
from all idle VMs. Calculated as CO₂
emission rate * Power consumed by
Idle VMs, where the rate is set at cluster
property / 1000.
Formula:
CO₂ Emission by Idle VMs (kg) =
Sum(VM(Power|Total Energy (Wh)), If
VM(Summary|Reclaimable Idle = 1) * 0.672
VMware by Broadcom  4458

---
## page 4459

 VMware Cloud Foundation 9.0
Metric Name Object Type Description
OR
CO₂ Emission by Idle VMs (kg) = Power
Wasted by Idle VMs (Wh) * 0.672
Sustainability|Electricity Cost Savings Cluster Compute Resource Estimated cost savings by virtualizing
workloads. Calculated from the difference
between power consumption before
virtualization and after virtualization. The
electricity cost is defined at the cluster
custom property.
Formula:
Electricity Cost Savings = (Summary|
Number of Running VMs * 0.1 - Sum(Host
System(Power|Total Energy(Wh)))/1000) *
0.108
OR
Daily Electricity Cost Savings = (Summary|
Number of Running VMs * 0.1 - Power
usage (kWh)) * 0.108
Sustainability|Power usage (kWh) Cluster Compute Resource Power usage calculated from all hosts in
kWh.
Formula:
Power usage (kWh) = Sum(Host
System(Power|Total Energy(Wh))/1000
Sustainability|Power usage per GHz (Wh) Cluster Compute Resource Power used per GHz of processing power.
This is a metric of how power-efficient your
CPUs are.
Formula:
Power usage per GHz (Wh) = Sum(Host
System(Power|Total Energy(Wh))/CPU|
Usage (MHz)/1000
Sustainability|Power Wasted by Idle VMs
(Wh)
Cluster Compute Resource Sum of electricity power used by all VMs
classified as idle by the system.
Formula:
Power Wasted by Idle VMs (Wh) =
Sum(VM(Power|Total Energy (Wh)), If
VM(Summary|Reclaimable Idle = 1)
Sustainability|CO₂ Emission (kg) vSphere World Total estimated carbon dioxide emissions.
Calculated as sum of carbon emission from
all clusters.
Formula:
CO₂ Emission (kg) =
Sum(Cluster(Sustainability|CO₂ Emission
(kg))
Sustainability|CO₂ Emission before
Virtualization (kg)
vSphere World Total estimated carbon dioxide emissions
before virtualization. Calculated as the sum
of CO₂ emission from all clusters.
Formula:
CO₂ Emission before Virtualization (kg) =
Sum(Cluster(Sustainability|CO₂ Emission
before Virtualization (kg)))
VMware by Broadcom  4459

---
## page 4460

 VMware Cloud Foundation 9.0
Metric Name Object Type Description
Sustainability|CO₂ Emission Avoided (t) vSphere World Estimated amount of carbon emissions
avoided with virtualization. Calculated by
difference in values of carbon emissions
before and after virtualization and
converting value in kg to Tonnes.
Formula:
CO₂ Emission Avoided (t) = (CO₂ Emission
before Virtualization (kg) - CO₂ Emission
(kg)) / 1000
Sustainability|Electricity Cost Savings vSphere World Total estimated cost savings by virtualizing
workloads at vSphere World. Calculated as
the sum of Electricity cost savings.
Formula:
Electricity Cost Savings =
Sum(Cluster(Daily Electricity Cost
Savings))
Sustainability|Power Savings with
Virtualization (%)
vSphere World Percentage of power savings achieved
by virtualization. Calculated by Formula =
(Power usage before Virtualization - Power
usage after Virtualization)/Power usage
before Virtualization *100.
Formula:
Power Savings with Virtualization (%)
=( Power usage Before Virtualization (kWh)
- Power usage (kWh) ) / Power usage
Before Virtualization (kWh) * 100
Sustainability|Power usage (kWh) vSphere World Power usage calculated from all hosts in
kWh.
Formula:
Power usage (kWh) = Sum(Host
System(Power|Total Energy(Wh)))/1000
Sustainability|Power usage Before
Virtualization (kWh)
vSphere World Power usage assuming that each low range
server consumes 0.1 kWh.
Formula:
Power usage Before Virtualization (kWh) =
Summary|Number of Running VMs * 0.1
Sustainability|Power Wasted by Idle VMs
(Wh)
vSphere World Sum of electricity power used by all VMs
classified as idle by the system.
Formula:
Power Wasted by Idle VMs (Wh) =
Sum((VM(Power|Total Energy (Wh)), If
VM(Summary|Reclaimable Idle = 1))
Sustainability|Adjusted Score|Workload
Efficiency (%)
Organization Indicates efficiency based on resource
wastage in the virtual environment.
Formula:
Workload Efficiency (%) = 100 - (Wastage/
Usage Ratio CPU + Wastage/Usage Ratio
Memory + Wastage/Usage Ratio Disk) *
100 / 3
VMware by Broadcom  4460

---
## page 4461

 VMware Cloud Foundation 9.0
Metric Name Object Type Description
Sustainability|Adjusted Score|Hardware
Efficiency (%)
Organization Indicates efficiency of hardware in the
environment, based on the age of the
hardware with the assumption that newer
hardware is more energy efficient than
older hardware.
Formula:
Hardware Efficiency (%) = ((10 - Average
Age of Servers)/ 10 * 30%) +((10 - Average
Age of Storage)/ 10 * 30%) + ((10 -
Average Age of Network)/ 10 * 20%) + ((10
- Average Age of Desktop)/ 10 * 20%)
The Average age of hardware variables in
the formula is provided in the Organization
Details page.
Sustainability|Adjusted Score|Resource
Utilization (%)
Organization Indicates utilization levels of the physical
resources in the environment.
Formula:
Resource Utilization (%) = (Virtualized
Server (%) * 44.45%) + (Virtualized Storage
(%) * 33.33%) + (Virtualized Network (%) *
22.22%)
Sustainability|Adjusted Score|Virtualization
(%)
Organization Indicates the extent of virtualization in the
environment.
Formula:
Virtualization (%) = (Server Virtualization
(%) * 0.4) + (Storage Virtualization (%) *
0.3) + (Network Virtualization (%) * 0.2) +
(Desktop Virtualization (%) * 0.1)
Sustainability|Adjusted Score|Power
Source (%)
Organization Indicates the sources of power being used
in the environment. Assumes usage of
renewable energy sources leads to less
carbon emissions.
Formula:
Power Source Efficiency (%) =
Sum(Adjusted Scores of each Power
Source)
Adjusted Scores of Power Source = Power
Source Green Factor * Power Source
Share in Organization
Sustainability|Hardware Utilization|Server
(%)
Organization Indicates server utilization levels.
Formula:
Virtualized Server (%) = ((Total ESXi Hosts
CPU Utilization (GHz) / Total ESXi Hosts
CPU Capacity (GHz)) + (Total ESXi Hosts
Memory Utilization (TB) / Total ESXi Hosts
Memory Capacity (TB))) / 2
Sustainability|Hardware Utilization|Storage
(%)
Organization Indicates storage utilization levels.
Formula:
Virtualized Storage (%) = (Total datastores
utilization + Total RDM) / (Total datastores
capacity + Total RDM + Physical Disk
Overhead)
VMware by Broadcom  4461

---
## page 4462

 VMware Cloud Foundation 9.0
Metric Name Object Type Description
Sustainability|Green Score (%) Organization A score that indicates how energy efficient
your data center is.
Formula:
Green Score (%) = (Workload Efficiency
(%) * 22.5%) + (Resource Utilization (%)
* 12.5%) + (Virtualization Adoption (%) *
15%) + (Power Source Efficiency (%) *
37.5%) + (Hardware Power Efficiency (%) *
12.5%)
Sustainability|Power Usage (kWh) Organization Sum of the power usage across all the
clusters in the environment.
Formula:
Power Consumption = Sum ( (Cluster)
Sustainability|Power Usage (kWh) )
Sustainability|CO₂ Emission (kg) Organization Total estimated carbon emissions in the
environment based on power consumed.
Formula:
CO₂ Emission = Power Consumption * CO₂
Emission Ratio
Sustainability|Workload Efficiency|Idle VM
Count
Organization Number of Idle VMs, which are considered
idle based on the Reclamation Idleness
settings.
Sustainability|Workload Efficiency|
Orphaned Disk Space (GB)
Organization The aggregated size of all orphaned
disks which are reclaimable based on the
Orphaned Disk Reclamation settings.
Sustainability|Workload Efficiency|
Oversized VM Count
Organization Number of Oversized VMs, which are
considered oversized by the capacity
engine recommendation and are not in the
Power Off state.
Sustainability|Workload Efficiency|Powered
Off VM Count
Organization The number of VMs which have been in the
Powered Off state for the last 7 days. The
number of days (7) can be configured from
the Reclamation Settings.
Sustainability|Workload Efficiency|Snapshot
Disk Space (GB)
Organization The aggregated size of all snapshots which
are reclaimable based on the Snapshot
Reclamation settings.
Disclaimer:
The conversion calculators and information shown in this documentation reference public information and have been
provided to help translate abstract carbon emissions numbers into easily understandable terms solely for informational
purposes. You should not rely on the calculators or information provided herein for any other purpose, including for any
regulatory disclosure or diligence purposes. Broadcom may update, upgrade, revise, adjust or otherwise change the
features and conversion methodologies at any time. Broadcom has not separately reviewed, approved, or endorsed
the public information or third-party websites. No representation or warranty is made by Broadcom as to the accuracy,
reasonableness or completeness of the calculations and related information herein.
Metrics for Policies
Each policy is an object in VCF Operations. This allows you to track every change in the policy and create any dashboard,
report, or alert on policy usage distribution.
VMware by Broadcom  4462

---
## page 4463

 VMware Cloud Foundation 9.0
VCF Operations collects metrics for the object type 'Policy'.
Metric Key Metric Name Description
NumberOfEffectiveObjects Number of Affected Objects Represents the count of objects affected by
the effective policy.
NumberOfVirtualMachines Number of Affected vCenter Virtual
Machines
Represents the number of vCenter Virtual
Machines associated with a specific policy.
NumberOfCustomGroups Number of Assigned Custom Groups Represents the number of assigned custom
groups for a specific policy.
NumberOfDefaultAssignedObjects Number of Default Assigned Objects Represents the number of objects that are
assigned by default for a specific policy.
This metric value is 0 for all policies except
the default policy.
NumberOfDirectAssignedObjects Number of Directly Assigned Objects Represents the number of objects that are
directly assigned for a specific policy.
NumberOfInheritedObjects Number of Objects Assigned By Scope Represents the count of inherited objects
for a specific policy.
Property Definitions in VCF Operations
Properties are attributes of objects in the VCF Operations environment. You use properties in symptom definitions. You
can also use properties in dashboards, views, and reports.
VCF Operations uses adapters to collect properties for target objects in your environment. Property definitions for all
objects connected through the vCenter adapter are provided. The properties collected depend on the objects in your
environment.
You can add symptoms based on properties to an alert definition so that you are notified if a change occurs to properties
on your monitored objects. For example, disk space is a hardware property of a virtual machine. You can use disk space
to define a symptom that warns you when the value falls below a certain numeric value.
You can add symptoms based on properties to an alert definition so that you are notified if a change occurs to properties
on your monitored objects. For example, disk space is a hardware property of a virtual machine. You can use disk space
to define a symptom that warns you when the value falls below a certain numeric value. See the VCF Operations User
Guide.
VCF Operations generates Object Type Classification and Subclassification properties for every object. You can use
object type classification properties to identify whether an object is an adapter instance, custom group, application,
tier, or a general object with property values ADAPTER_INSTANCE, GROUP, BUSINESS_SERVICE, TIER, or GENERAL,
respectively.
Properties for vCenter Server Components
The VMware vSphere solution is installed with VCF Operationsand includes the vCenter adapter. VCF Operations uses
the vCenter adapter to collect properties for objects in the vCenter system.
vCenter components are listed in the describe.xml file for the vCenter adapter. The following example shows the
runtime property memoryCap or Memory Capacity for the virtual machine in the describe.xml.
<ResourceGroup instanced="false" key="runtime" nameKey="5300" validation="">
   <ResourceAttribute key="memoryCap" nameKey="1780" dashboardOrder="200" dataType="float"  
                      defaultMonitored="true" isDiscrete="false" isRate="false" maxVal="" 
VMware by Broadcom  4463

---
## page 4464

 VMware Cloud Foundation 9.0
                      minVal="" isProperty="true" unit="kb"/>
</ResourceGroup>
The ResourceAttribute element includes the name of the property that appears in the UI and is documented as a
Property Key. isProperty = "true" indicates that ResourceAttribute is a property.
vCenter Server Properties
VCF Operations collects summary and event properties for system objects.
Table 1370: Summary Properties Collected for vCenterSystem Objects
Property Key Property Name Description
summary|version Version Version
summary|vcuuid VirtualCenter ID Virtual Center ID
summary|vcfullname Product Name Product Name
Table 1371: Event Properties Collected for vCenterSystem Objects
Property Key Property Name Description
event|time Last VC Event Time Last Virtual Center Event Time
event|key Last VC Event ID Last Virtual Center Event ID
Table 1372: Custom Field Manager Property Collected for vCenterSystem Objects
Property Key Property Name Description
CustomFieldManager|CustomFieldDef Custom Field Def Custom Field Def for vCenter Tagging information
at the Adapter level.
Table 1373: Compliance Configuration Related Properties for vCenterSystem Objects
Property Key Property Name Description
vc_appliance|hasAccessSSH Appliance|Access SSH Access SSH
vc_appliance|networkNICs Appliance|Number of NICs NICs
 Virtual Machine Properties
VCF Operations collects configuration, runtime, CPU, memory, network I/O, and properties about summary use for virtual
machine objects. Properties are collected with the first cycle of data collection. Once collected, the next property collection
occurs only when there is data change. In case of no data change, no property is collected.
VMware by Broadcom  4464

---
## page 4465

 VMware Cloud Foundation 9.0
Table 1374: Properties Collected for Virtual Machines with vSAN Adapter
Property Key Property Name Description
Note:  The following Disk Space properties are displayed by the virtual machine object only when the vSAN adapter is configured with
vCenter.
Virtual Disk:scsi0:0|Storage Policy|Cache
Reservation
Storage Policy|Cache
Reservation
This property helps you with flash read cache reservation.
Virtual Disk:scsi0:0|Storage Policy|
Checksum Disabled
Storage Policy|
Checksum Disabled
This property checks whether checksum is disabled for the disk
object.
Virtual Disk:scsi0:0|Storage Policy|
Encryption Service
Storage Policy|
Encryption Service
This property checks whether the encryption service is used or
not.
Virtual Disk:scsi0:0|Storage Policy|Failures
to Tolerate
Storage Policy|
Failures to Tolerate
This property gives the number of host or disk failures the
storage object can tolerate.
Virtual Disk:scsi0:0|Storage Policy|Force
Provisioning
Storage Policy|Force
Provisioning
This property checks whether force provisioning is disabled for
the disk object.
Virtual Disk:scsi0:0|Storage Policy|Object
Space Reservation
Storage Policy|Object
Space Reservation
This property helps you to check the object space reservation.
Virtual Disk:scsi0:0|Storage Policy|Replica
Preference
Storage Policy|Replica
Preference
This property helps you to identify the fault tolerance method.
Virtual Disk:scsi0:0|Storage Policy|Site
Disaster Tolerance
Storage Policy|Site
Disaster Tolerance
This property gives the number of fault domain failures, the
storage object can tolerate.
Virtual Disk:scsi0:0|Storage Policy|Space
Efficiency
Storage Policy|Space
Efficiency
This property helps you with the space efficiency method.
Virtual Disk:scsi0:0|Storage Policy|Storage
Policy in Use
Storage Policy in Use This property gives the storage policy associated with the
virtual disk.
Virtual Disk:scsi0:0|Storage Policy|Stripe
Width
Storage Policy|Stripe
Width
This property gives the number of disk stripes per object.
Table 1375: Properties Collected for System
Property Key Property Name Description
system|notes System|Notes This property helps you to track the System notes defined in
vCenter.
Table 1376: VCF Automation Properties Collected for Virtual Machine Objects
Property Key Property Name Description
vRealize Automation|Blueprint Name Blueprint Name Virtual machines deployed by VCF Automation to be excluded
from workload placements.
VMware by Broadcom  4465

---
## page 4466

 VMware Cloud Foundation 9.0
Table 1377: Properties Collected for Virtual Machine Objects to Support VIN Adapter Localization
Property Key Property Name Description
RunsOnApplicationComponents Application components running
on the Virtual Machine
Application components running on the Virtual
Machine
DependsOnApplicationComponents Application components the
Virtual Machine depends on
Application components running on other machines
that this Virtual Machine depends on.
Table 1378: Properties Collected for Guest File Systems
Property Key Property Name Description
guestfilesystem|capacity_property Guest File System stats|Guest
File System Capacity Property
This property is disabled by default.
guestfilesystem|capacity_property_total Guest File System stats|Total
Guest File System Capacity
Property(gb)
This property is disabled by default.
Table 1379: Properties Collected for Disk Space Objects
Property Key Property Name Description
diskspace|snapshot|creator Disk Space|Snapshot|Creator This property is disabled by default.
diskspace|snapshot|description Disk Space|Snapshot|Description This property is disabled by default.
Table 1380: Configuration Properties Collected for Virtual Machine Objects
Property Key Property Name Description
config|ctkEnabled Configuration|Changed Block Tracking This property displays if Change Block
Tracking is enabled, if enabled, tracks
changes on disk sectors. This helps in
performing incremental backups on the
VM.
Configuration|Hardware|Number of CPUs
(vCPUs)
Number of CPUs (vCPUs) This property displays the number of
CPUs configured in the VM, the count
includes both in the vSocket and the
vCore.
Configuration|Number of RDMs Number of RDMs This property displays the number of
RDMs configured in the VM. This property
is enabled by default.
Configuration|Number of Virtual Disks Number of Virtual Disks This property displays the number of
virtual disks configured in the VM, the
count includes the RDMs.
Configuration|Hardware|Number of VMDKs Number of VMDKs This property displays the number of
VMDKs configured in the VM. This
property is enabled by default.
VMware by Broadcom  4466

---
## page 4467

 VMware Cloud Foundation 9.0
Property Key Property Name Description
Summary|Is Horizon Managed Is Horizon Managed This property displays whether the
selected object is managed by Horizon or
not.
summary|datastoreClusters Summary|Datastore Cluster(s) This property is applicable only if the VM
belongs to a datastore cluster.
Note:  A VM with multiple virtual disks can
belong to multiple datastore clusters.
Summary|Configuration|Number of NICs Number of NICs his property displays the number of NICs
configured in the VM.
config|name Name This property displays the virtual object
name
config|guestFullName Guest OS from vCenter This property is set by the vCenter during
the VM creation. It may differ from the
value of the Guest/
config|hardware|numCpu Number of virtual CPUs Number of virtual CPUs
config|hardware|memoryKB Memory Memory
config|hardware|thinEnabled Thin Provisioned Disk Indicates whether thin provisioning is
enabled
config|hardware|diskSpace Disk Space Disk Space
config|cpuAllocation|reservation Reservation CPU reservation
config|cpuAllocation|limit Limit CPU limit
config|cpuAllocation|shares|shares Shares CPU shares
config|memoryAllocation|reservation Reservation CPU reservation
config|memoryAllocation|limit Limit Limit
config|memoryAllocation|shares|shares Shares Memory shares
config|extraConfig|mem_hotadd Memory Hot Add Memory Hot Add Configuration
config|extraConfig|vcpu_hotadd VCPU Hot Add VCPU Hot Add Configuration
config|extraConfig|vcpu_hotremove VCPU Hot Remove VCPU Hot Remove Configuration
config|security|disable_autoinstall Disable tools auto install
(isolation.tools.autoInstall.disable)
Disable tools auto install
(isolation.tools.autoInstall.disable)
config|security|disable_console_copy Disable console copy operations
(isolation.tools.copy.disable)
Disable console copy operations
(isolation.tools.copy.disable)
config|security|disable_console_dnd Disable console drag and drop
operations (isolation.tools.dnd.disable)
Disable console drag and drop operations
(isolation.tools.dnd.disable)
config|security|enable_console_gui_options Enable console GUI operations
(isolation.tools.setGUIOptions.enable)
Enable console GUI operations
(isolation.tools.setGUIOptions.enable)
config|security|disable_console_paste Disable console paste operations
(isolation.tools.paste.disable)
Disable console paste operations
(isolation.tools.paste.disable)
config|security|disable_disk_shrinking_shrink Disable virtual disk shrink
(isolation.tools.diskShrink.disable)
Disable virtual disk shrink
(isolation.tools.diskShrink.disable)
config|security|disable_disk_shrinking_wiper Disable virtual disk wiper
(isolation.tools.diskWiper.disable)
Disable virtual disk wiper
(isolation.tools.diskWiper.disable)
VMware by Broadcom  4467

---
## page 4468

 VMware Cloud Foundation 9.0
Property Key Property Name Description
config|security|disable_hgfs Disable HGFS file transfers
(isolation.tools.hgfsServerSet.disable)
Disable HGFS file transfers
(isolation.tools.hgfsServerSet.disable)
config|security|
disable_independent_nonpersistent
Avoid using independent nonpersistent
disks (scsiX:Y.mode)
Avoid using independent nonpersistent
disks (scsiX:Y.mode)
config|security|enable_intervm_vmci Enable VM-to-VM communication
through VMCI (vmci0.unrestricted)
Enable VM-to-VM communication through
VMCI (vmci0.unrestricted)
config|security|enable_logging Enable VM logging (logging) Enable VM logging (logging)
config|security|disable_monitor_control Disable VM Monitor Control
(isolation.monitor.control.disable)
Disable VM Monitor Control
(isolation.monitor.control.disable)
config|security|
enable_non_essential_3D_features
Enable 3D features on Server
and desktop virtual machines
(mks.enable3d)
Enable 3D features on Server and desktop
virtual machines (mks.enable3d)
config|security|
disable_unexposed_features_autologon
Disable unexposed features - autologon
(isolation.tools.ghi.autologon.disable)
Disable unexposed features - autologon
(isolation.tools.ghi.autologon.disable)
config|security|
disable_unexposed_features_biosbbs
Disable unexposed features - biosbbs
(isolation.bios.bbs.disable)
Disable unexposed features - biosbbs
(isolation.bios.bbs.disable)
config|security|
disable_unexposed_features_getcreds
Disable unexposed features - getcreds
(isolation.tools.getCreds.disable)
Disable unexposed features - getcreds
(isolation.tools.getCreds.disable)
config|security|
disable_unexposed_features_launchmenu
Disable unexposed
features - launchmenu
(isolation.tools.ghi.launchmenu.change)
Disable unexposed features - launchmenu
(isolation.tools.ghi.launchmenu.change)
config|security|
disable_unexposed_features_memsfss
Disable unexposed features - memsfss
(isolation.tools.memSchedFakeSampleStats.disable)
Disable unexposed features - memsfss
(isolation.tools.memSchedFakeSampleStats.disable)
config|security|
disable_unexposed_features_protocolhandler
Disable unexposed
features - protocolhandler
(isolation.tools.ghi.protocolhandler.info.disable)
Disable unexposed
features - protocolhandler
(isolation.tools.ghi.protocolhandler.info.disable)
config|security|
disable_unexposed_features_shellaction
Disable unexposed features - shellaction
(isolation.ghi.host.shellAction.disable)
Disable unexposed features - shellaction
(isolation.ghi.host.shellAction.disable)
config|security|
disable_unexposed_features_toporequest
Disable unexposed
features - toporequest
(isolation.tools.dispTopoRequest.disable)
Disable unexposed features - toporequest
(isolation.tools.dispTopoRequest.disable)
config|security|
disable_unexposed_features_trashfolderstate
Disable unexposed
features - trashfolderstate
(isolation.tools.trashFolderState.disable)
Disable unexposed
features - trashfolderstate
(isolation.tools.trashFolderState.disable)
config|security|
disable_unexposed_features_trayicon
Disable unexposed features - trayicon
(isolation.tools.ghi.trayicon.disable)
Disable unexposed features - trayicon
(isolation.tools.ghi.trayicon.disable)
config|security|
disable_unexposed_features_unity
Disable unexposed features - unity
(isolation.tools.unity.disable)
Disable unexposed features - unity
(isolation.tools.unity.disable)
config|security|
disable_unexposed_features_unity_interlock
Disable unexposed
features - unity-interlock
(isolation.tools.unityInterlockOperation.disable)
Disable unexposed
features - unity-interlock
(isolation.tools.unityInterlockOperation.disable)
config|security|
disable_unexposed_features_unity_taskbar
Disable unexposed
features - unity-taskbar
(isolation.tools.unity.taskbar.disable)
Disable unexposed
features - unity-taskbar
(isolation.tools.unity.taskbar.disable)
VMware by Broadcom  4468

---
## page 4469

 VMware Cloud Foundation 9.0
Property Key Property Name Description
config|security|
disable_unexposed_features_unity_unityactive
Disable unexposed
features - unity-unityactive
(isolation.tools.unityActive.disable)
Disable unexposed
features - unity-unityactive
(isolation.tools.unityActive.disable)
config|security|
disable_unexposed_features_unity_windowcontents
Disable unexposed features
- unity-windowcontents
(isolation.tools.unity.windowContents.disable)
Disable unexposed features
- unity-windowcontents
(isolation.tools.unity.windowContents.disable)
config|security|
disable_unexposed_features_unitypush
Disable unexposed features - unitypush
(isolation.tools.unity.push.update.disable)
Disable unexposed features - unitypush
(isolation.tools.unity.push.update.disable)
config|security|
disable_unexposed_features_versionget
Disable unexposed features - versionget
(isolation.tools.vmxDnDVersionGet.disable)
Disable unexposed features - versionget
(isolation.tools.vmxDnDVersionGet.disable)
config|security|
disable_unexposed_features_versionset
Disable unexposed features - versionset
(solation.tools.guestDnDVersionSet.disable)
Disable unexposed features - versionset
(solation.tools.guestDnDVersionSet.disable)
config|security|disable_vix_messages Disable VIX messages from the VM
(isolation.tools.vixMessage.disable)
Disable VIX messages from the VM
(isolation.tools.vixMessage.disable)
config|security|enable_vga_only_mode Disable all but VGA mode on virtual
machines (svga.vgaOnly)
Disable all but VGA mode on virtual
machines (svga.vgaOnly)
config|security|limit_console_connection Limit number of console connections
(RemoteDisplay.maxConnection)
Limit number of console connections
(RemoteDisplay.maxConnection)
config|security|limit_log_number Limit number of log files (log.keepOld) Limit number of log files (log.keepOld)
config|security|limit_log_size Limit log file size (log.rotateSize) Limit log file size (log.rotateSize)
config|security|limit_setinfo_size Limit VMX file size
(tools.setInfo.sizeLimit)
Limit VMX file size (tools.setInfo.sizeLimit)
config|security|enable_console_VNC Enable access to VM console via VNC
protocol (RemoteDisplay.vnc.enabled)
Enable access to VM console via VNC
protocol (RemoteDisplay.vnc.enabled)
config|security|
disable_device_interaction_connect
Disable unauthorized removal,
connection of devices
(isolation.device.connectable.disable)
Disable unauthorized removal,
connection of devices
(isolation.device.connectable.disable)
config|security|disable_device_interaction_edit Disable unauthorized modification of
devices (isolation.device.edit.disable)
Disable unauthorized modification of
devices (isolation.device.edit.disable)
config|security|enable_host_info Enable send host information to guests
(tools.guestlib.enableHostInfo)
Enable send host information to guests
(tools.guestlib.enableHostInfo)
config|security|network_filter_enable Enable dvfilter network APIs
(ethernetX.filterY.name)
Enable dvfilter network APIs
(ethernetX.filterY.name)
config|security|vmsafe_cpumem_agentaddress VMsafe CPU/memory APIs - IP address
(vmsafe.agentAddress)
VMsafe CPU/memory APIs - IP address
(vmsafe.agentAddress)
config|security|vmsafe_cpumem_agentport VMsafe CPU/memory APIs - port
number (vmsafe.agentPort)
VMsafe CPU/memory APIs - port number
(vmsafe.agentPort)
config|security|vmsafe_cpumem_enable Enable VMsafe CPU/memory APIs
(vmsafe.enable)
Enable VMsafe CPU/memory APIs
(vmsafe.enable)
config|security|disconnect_devices_floppy Disconnect floppy drive Disconnect floppy drive
config|security|disconnect_devices_cd Disconnect CD-ROM Disconnect CD-ROM
config|security|disconnect_devices_usb Disconnect USB controller Disconnect USB controller
config|security|disconnect_devices_parallel Disconnect parallel port Disconnect parallel port
VMware by Broadcom  4469

---
## page 4470

 VMware Cloud Foundation 9.0
Property Key Property Name Description
config|security|disconnect_devices_serial Disconnect serial port Disconnect serial port
config|faultTolerant config|faultTolerant
Note:  Security properties not collected by default. They are collected only if the vSphere Hardening Guide policy is
applied to the objects, or if the vSphere Hardening Guide alerts are manually enabled in the currently applied policy.
Table 1381: Runtime Properties Collected for Virtual Machine Objects
Property Key Property Name Description
runtime|memoryCap Memory Capacity Memory Capacity
Table 1382: CPU Usage Properties Collected for Virtual Machine Objects
Property Key Property Name Description
cpu|limit CPU limit CPU limit
cpu|reservation CPU reservation CPU reservation
cpu|speed CPU CPU Speed
Table 1383: Memory Properties Collected for Virtual Machine Objects
Property Key Property Name Description
mem|host_limit VM Limit Mem Machine Limit
mem|host_reservation Memory|VM Reservation(kb) This property is disabled by default.
Table 1384: Network Properties Collected for Virtual Machine Objects
Property Key Property Name Description
net:<vnic_id>|portGroup Network:<vnic_id>|Port Group This is a property at each virtual NIC level,
not at the VM level. A VM with multiple NIC
connects to different port groups, with this
property you can identify to which port group
the vnic blongs and has mapping with.
net:<nic_key>|uptCompatibilityEnabled Network:<nic_key>|Direct Path I/O Status If there is the VM, with cofigured direct path
IO - IO directly comes to VM, bypassing the
hypervisor. The property shows the status.
net|mac_address Mac Address Mac Address
net|ip_address IP Address IP Address
net|vnic_label Network:<ID>|Label This property is disabled by default.
net|nvp_vm_uuid Network I/O|NVP VM UUID This property is disabled by default.
net|vnic_type Network I/O|Virtual NIC Type This property is disabled by default.
net|ipv6_address Network|IPv6 Address This property is disabled by default.
net|ipv6_prefix_length Network|IPv6 Prefix Length This property is disabled by default.
VMware by Broadcom  4470

---
## page 4471

 VMware Cloud Foundation 9.0
Property Key Property Name Description
net|default_gateway Network|Network I/O|Default Gateway This property is disabled by default.
net|subnet_mask Network|Subnet Mask This property is disabled by default.
Table 1385: Summary Properties Collected for Virtual Machine Objects
Property Key Property Name Description
summary|customTag|customTagValue Value Custom Tag Value
summary|tag vSphere Tag vSphere Tag Name
summary|parentCluster Parent Cluster Parent Cluster
summary|parentHost Parent Host Parent Host
summary|parentDatacenter Parent data center Parent data center
summary|parentVcenter Parent vCenter Parent vCenter
summary|guest|fullName Guest OS Full Name This property is provided by the VMware Tools. It
will differ to the value set in vCenter if the Guest
OS was upgraded, or if a different Guest OS was
installed.
summary|guest|ipAddress Guest OS IP Address Guest OS IP Address
summary|guest|toolsRunningStatus Tools Running Status Guest Tools Running Status
summary|guest|toolsVersionStatus2 Tools Version Status Guest Tools Version Status 2
summary|guest|vrealize_operations_agent_id vRealize Operations Agent ID An ID to identify a VM in Agent Adapter's world.
summary|guest|
vrealize_operations_euc_agent_id
vRealize Operations Euc Agent
ID
An ID to identify a VM in Agent Adapter's world.
summary|config|numEthernetCards Number of NICs Number of NICs
summary|config|isTemplate VM Template Indicates whether it is a VM Template.
summary|runtime|powerState Power State Power State
summary|runtime|connectionState Connection State Connection State
summary|config|appliance Appliance Appliance
summary|config|productName Product Name Product Name
summary|UUID UUID Unique UUID instance in vCenter that identifies all
the virtual machine instances.
summary|smbiosUUID SMBIOS UUID System Management BIOS UUID of a virtual
machine.
Table 1386: Virtual Disk Properties Collected for Virtual Machine Objects
Property Key Property Name Description
virtualDisk:<scsi_id>|encryptionStatus Virtual Disk:<scsi_id>|Encryption Status This property provides encryption status on
SCSI on VDMK layer. The property is per
virtual disk and does not apply to RDM disk.
VMware by Broadcom  4471

---
## page 4472

 VMware Cloud Foundation 9.0
Property Key Property Name Description
virtualDisk:<scsi_controller>|iopsLimit Virtual Disk:<scsi_controller>|IOPS Limit This property shows the set IOPS limit on
virtual disk on SCSI level, when IOPS limit
is set beyond the disk. This helps you to
understand the current performance state, why
the IOPS is not increasing and limited.
Virtual Disk:scsi0:0|Configuired
Size(GB)
Configuired Size(GB) This property displays the disk space
configured for the virtual disk.
Virtual Disk:scsi0:0|Datastore Datastore This property displays the name of the
datastore where the scsi disk is present. If an
RDM is present, only a pointer to the RDM is
present in the datastore.
Virtual Disk:scsi0:0|Disk Mode Disk Mode This property determines how a virtual disk
is affected by snapshots. The disk mode acts
on each individual VMDK, not on the whole
VM. The available options are Independent
persistent, Persistent, Non-persistent, this
property is disabled by default.
Virtual Disk:scsi0:0|SCSI Bus Sharing SCSI Bus Sharing This property sets the type of bus sharing
for the VM and determines whether to share
the bus or not. Depending on the type of bus
sharing, the VM can access the same virtual
disk simultaneously on the same server or any
other server. The available options are None,
Physical, Virtual, this property is disabled by
default.
Virtual Disk:scsi0:0|SCSI Controller
Type
SCSI Controller Type This virtual storage controller property
connects the virtual and physical disks to
the VM. The available options are LSI SAS/
PVSCSI, this property is disabled by default.
Virtual Disk:scsi0:0|Virtual Disk Sharing Virtual Disk Sharing This property allows VMFS-backed disks to be
shared by multiple VMs. The available options
are Unspecified, No sharing, Multi-Writer. You
can use this option to disable protection for
certain cluster aware applications, where the
applications ensures that simultaneous write
operation from two VMs does not induce data
loss. This property is disabled by default.
Virtual Disk:scsi0:0|Virtual Device Node Virtual Device Node This property determines the virtual device
bus location. The virtual disks are enumerated
starting with the first controller. This property is
disabled by default.
Virtual Disk:scsi0:0|Is RDM Is RDM This property indicates whether the virtual disk
is an RDM or not. This property is enabled by
default.
Virtual Disk|File Name File Name This property is disabled by default.
Virtual Disk|Label Label This property displays the device label.
VMware by Broadcom  4472

---
## page 4473

 VMware Cloud Foundation 9.0
Property Key Property Name Description
Virtual Disk:scsi1:1|Compatibility Mode Compatibility Mode This property displays the compatibility mode
for the RDMs. The options are physical
and virtual. Virtual mode specifies the full
virtualization of the mapped device whereas
physical mode specifies minimal SCSI
virtualization of the mapped device. This
property is disabled by default in the base
policy.
Table 1387: Virtual Disk Properties Collected for POD Objects
Property Key Property Name Description
Virtual Disk:scsi0:0|Virtual Device Node Virtual Device Node This property determines the virtual device bus
location. The virtual disks are enumerated starting
with the first controller. This property is disabled by
default.
Virtual Disk:scsi0:0|Virtual Disk Sharing Virtual Disk Sharing This property allows VMFS-backed disks to be
shared by multiple VMs. The available options are
Unspecified, No sharing, Multi-Writer. You can use
this option to disable protection for certain cluster
aware applications, where the applications ensures
that simultaneous write operation from two PODs
does not induce data loss. This property is disabled
by default.
Virtual Disk:scsi0:0|Disk Mode Disk Mode This property determines how a virtual disk is
affected by snapshots. The disk mode acts on
each individual VMDK, not on the whole POD.
The available options are Independent persistent,
Persistent, Non-persistent, this property is disabled
by default.
Virtual Disk:scsi0:0|SCSI Controller Type SCSI Controller Type This virtual storage controller property connects the
virtual and physical disks to the POD. The available
options are LSI SAS/PVSCSI, this property is
disabled by default.
Table 1388: Datastore Properties Collected for Virtual Machine Properties
Property Key Property Name Description
datastore|maxObservedNumberRead Datastore I/O|Highest Observed
Number of Read Requests
datastore|maxObservedNumberWrite Datastore I/O|Highest Observed
Number of Write Requests
datastore|maxObservedOIO Datastore I/O|Highest Observed
Outstanding Requests
datastore|maxObservedRead Datastore I/O|Highest Observed
Read Rate(kbps)
VMware by Broadcom  4473

---
## page 4474

 VMware Cloud Foundation 9.0
Property Key Property Name Description
datastore|maxObservedWrite Datastore I/O|Highest Observed
Write Rate(kbps)
Table 1389: Compliance Configuration Related Properties for Virtual Machine Objects
Property Key Property Name Description
config|security|disconnect_devices_virtualhd
audiocard
Configuration|Security|Virtual HD
Audio Card Disconnected
NIL
config|security|disconnect_devices_virtualah
cicontroller
Configuration|Security|Virtual
AHCI Controller Disconnected
NIL
config|security|disconnect_devices_virtualen
soniq1371
Configuration|Security|Virtual
Ensoniq 1371 Disconnected
NIL
Datastore properties collected for virtual machine objects have been disabled in this version of VCF Operations. This
means that they do not collect data by default.
Host System Properties
VCF Operations collects configuration, hardware, runtime, CPU, network I/O, and properties about summary use for host
system objects.
Table 1390: GPU properties collected for Host System Objects
Property Key Property Name Description
gpu|<GPU-id>|active_type GPU|<GPU-id>|Active Type Active Type
gpu|<GPU-id>|configured_type GPU|<GPU-id>|Configured Type Configured Type
gpu|<GPU-id>|device_name GPU|<GPU-id>|Device Name Device name
gpu|<GPU-id>|vendor_name GPU|<GPU-id>|Vendor Name Vendor name
gpu|assignmentPolicy GPU|Assignment Policy Assignment Policy
GPU:GPU-id|GPU Slowdown Temperature
(Celcius)
GPU Slowdown Temperature
(Celsius)
The slowdown temperature is the thermal threshold
at which a GPU starts reducing it's clock speed to
lower power consumption and prevent overheating.
GPU:GPU-id|GPU Shutdown Temperature
(Celcius)
GPU Shutdown Temperature
(Celsius)
The shutdown temperature is the thermal threshold
at which a GPU automatically powers off, to protect
itself from damage due to overheating.
GPU:GPU-id|GPU Power limit (Max TDP)
(W)
GPU Power limit (Max TDP)
(Watts)
Maximum power in Watts that this GPU can draw.
Table 1391: Configuration Properties Collected for Host System Objects
Property Key Property Name Description
config|name Name Name
config|diskSpace Disk Space Disk Space
VMware by Broadcom  4474

---
## page 4475

 VMware Cloud Foundation 9.0
Property Key Property Name Description
config|network|nnic Number of NICs Number of NICs
config|network|linkspeed Average Physical NIC Speed Average Physical NIC Speed
config|network|dnsserver DNS Server List of DNS Servers
config|product|productLineId Product Line ID Product Line ID
config|product|apiVersion API Version API Version
config|storageDevice|plugStoreTopology|
numberofPath
Total number of Path Total number of storage paths
config|storageDevice|multipathInfo|
numberofActivePath
Total number of Active Path Total number of active storage paths
config|storageDevice|multipathInfo|
multipathPolicy
Multipath Policy Multipath Policy
config|hyperThread|available Available Indicates whether hyperthreading is
supported by the server
config|hyperThread|active Active Indicates whether hyperthreading is active
config|ntp|server NTP Servers NTP Servers
config|security|ntpServer NTP server NTP server
config|security|enable_ad_auth Enable active directory authentication Enable active directory authentication
config|security|enable_chap_auth Enable mutual chap authentication Enable mutual chap authentication
config|security|enable_auth_proxy Enable authentication proxy
(UserVars.ActiveDirectoryVerifyCAMCertificate)
Enable authentication proxy
(UserVars.ActiveDirectoryVerifyCAMCertificate)
config|security|syslog_host Remote log host (Syslog.global.logHost) Remote log host (Syslog.global.logHost)
config|security|dcui_access Users who can override lock down mode
and access the DCUI (DCUI.Access)
Users who can override lock down mode
and access the DCUI (DCUI.Access)
config|security|shell_interactive_timeout Shell interactive timeout
(UserVars.ESXiShellInteractiveTimeOut)
Shell interactive timeout
(UserVars.ESXiShellInteractiveTimeOut)
config|security|shell_timeout Shell timeout
(UserVars.ESXiShellTimeOut)
Shell timeout
(UserVars.ESXiShellTimeOut)
config|security|dvfilter_bind_address Dvfilter bind ip address
(Net.DVFilterBindIpAddress)
Dvfilter bind ip address
(Net.DVFilterBindIpAddress)
config|security|syslog_dir Log directory (Syslog.global.logDir) Log directory (Syslog.global.logDir)
config|security|firewallRule|allowedHosts Allowed hosts Allowed hosts in the firewall configuration
config|security|service|isRunning Running Indicates whether a service is running or
not. Services are: Direct Console UI, ESXi
shell, SSH, or NTP Daemon.
config|security|service|ruleSet Ruleset Ruleset for each service.
config|security|service|policy Policy Policy for each service.
config|security|tlsdisabledprotocols TLS Disabled Protocols TLS Disabled Protocols
Note:  Security properties not collected by default. They are collected only if the vSphere Hardening Guide policy is
applied to the objects, or if the vSphere Hardening Guide alerts are manually enabled in the currently applied policy.
VMware by Broadcom  4475

---
## page 4476

 VMware Cloud Foundation 9.0
Table 1392: Cost Properties Collected for Host System Objects
Property Key Property Name Description
Cost|Energy Consumed (Joule) Energy Consumed (Joule) Displays the energy consumed in Joules.
Cost|Number of Rack Units Number of Rack Units Displays the number of rack units in the
host.
Cost|OS Categories OS Categories Displays the operating system categories in
the host.
Cost|IsServerLeased Is Server Leased Displays whether the server is leased or
not.
Cost|RemainingDepreciationMonths Remaining Depreciation Months Displays the remaining number of
depreciation months.
Cost|ServerPurchaseCost Server Purchase Cost Server Purchase Cost is displayed in the
currency format chosen.
Cost|ServerPurchaseDate Server Purchase Date Server Purchase Date is displayed
Table 1393: Hardware Properties Collected for Host System Objects
Property Key Property Name Description
hardware|bioisReleaseDate Hardware|BIOS Release Date This property displays the release date
corresponding to the version of the installed
BIOS.
hardware|memorySize Memory Size Memory Size
hardware|cpuInfo|numCpuCores Number of CPU Cores Number of CPU Cores
hardware|cpuInfo|hz CPU Speed per Core CPU Speed per Core
hardware|cpuInfo|numCpuPackages Number of CPU Packages Number of CPU Packages
hardware|cpuInfo|
powerManagementPolicy
Active CPU Power Management Policy Active CPU Power Management Policy
hardware|cpuInfo|
powerManagementTechnology
Power Management Technology Power Management Technology
hardware|cpuInfo|biosVersion BIOS Version BIOS Version
hardware|vendor Hardware|Vendor Indicates the hardware manufacturer
Table 1394: Runtime Properties Collected for Host System Objects
Property Key Property Name Description
runtime|connectionState Connection State Connection State
runtime|powerState Power State Power State
runtime|maintenanceState Maintenance State Maintenance State
runtime|memoryCap Memory Capacity Memory Capacity
VMware by Broadcom  4476

---
## page 4477

 VMware Cloud Foundation 9.0
Table 1395: Configuration Manager Properties Collected for Host System Objects
Property Key Property Name Description
configManager|memoryManager|
consoleReservationInfo|
serviceConsoleReserved
Service Console Reserved Service console reserved memory
Table 1396: CPU Usage Properties Collected for Host System Objects
Property Key Property Name Description
cpu|speed CPU CPU Speed
cpu|cpuModel CPU Model CPU Model
Table 1397: Network Properties Collected for Host System Objects
Property Key Property Name Description
net:<pnic>|configuredSpeed Network:<pnic>|Configured Speed This property displays the configured
network speed of the network card. If this is
higher than actual, the card is not operating
at full capacity.
net:<pnic>|speed Network:<pnic>|Actual Speed This property displays the actual operating
speed of the network card, which can be
lower than its configured capacity due to
auto-negotiation. The options are Enabled or
Disabled.
net|maxObservedKBps Highest Observed Throughput Highest Observed Throughput (KBps)
net|mgmt_address Management Address Management Address
net|ip_address IP Address IP Address
net|discoveryProtocol|cdp|
managementIpAddress
Management IP Address Management IP Address
net|discoveryProtocol|cdp|systemName System Name System Name
net|discoveryProtocol|cdp|portName Port Name Port Name
net|discoveryProtocol|cdp|vlan VLAN VLAN
net|discoveryProtocol|cdp|mtu MTU Maximum Transmission Unit
net|discoveryProtocol|cdp|
hardwarePlatform
Hardware Platform Hardware Platform
net|discoveryProtocol|cdp|
softwareVersion
Software Version Software Version
net|discoveryProtocol|lldp|systemDescrip
tion
System Description System Description
net|discoveryProtocol|lldp|mtu MTU Maximum Transmission Unit
net|discoveryProtocol|lldp|portDescription Port Description Port Description
VMware by Broadcom  4477

---
## page 4478

 VMware Cloud Foundation 9.0
Property Key Property Name Description
net|discoveryProtocol|lldp|aggregationSt
atus
Aggregation Status Aggregation Status
net|discoveryProtocol|lldp|
managementIpAddress
Management IP Address Management IP Address
net|discoveryProtocol|lldp|systemName System Name System Name
net|discoveryProtocol|lldp|portName Port Name Port Name
net|discoveryProtocol|lldp|vlan VLAN VLAN
Table 1398: System Properties Collected for Host System Objects
Property Key Property Name Description
sys|build Build number VMWare build number
sys|productString Product String VMWare product string
Table 1399: Summary Properties Collected for Host System Objects
Property Key Property Name Description
Summary|Is Horizon Managed Is Horizon Managed This property displays whether the selected object
is managed by Horizon or not.
summary|version Version This property displays theVersion.
summary|hostuuid Host UUID This property displays the Host UUID.
summary|evcMode Current EVC Mode This property displays the Current EVC Mode.
summary|customTag|customTagValue Value This property displays the Custom Tag Value.
summary|tag vSphere Tag This property displays the vSphere Tag Name.
summary|parentCluster Parent Cluster This property displays the Parent Cluster.
summary|parentDatacenter Parent Datacenter This property displays the Parent Datacenter.
summary|parentVcenter Parent Vcenter This property displays the Parent Vcenter.
Table 1400: Datastore Properties Collected for Host System Objects
Property Key Property Name Description
datastore|maxObservedNumberRead Datastore I/O|Highest Observed
Number of Read Requests
datastore|maxObservedNumberWrite Datastore I/O|Highest Observed
Number of Write Requests
datastore|maxObservedOIO Datastore I/O|Highest Observed
Outstanding Requests
datastore|maxObservedRead Datastore I/O|Highest Observed
Read Rate(kbps)
datastore|maxObservedWrite Datastore I/O|Highest Observed
Write Rate(kbps)
VMware by Broadcom  4478

---
## page 4479

 VMware Cloud Foundation 9.0
Property Key Property Name Description
net|discoveryProtocol|cdp|timeToLive Network I/O|Discovery Protocol|
Cisco Discovery Protocol|Time to
Live
net|discoveryProtocol|lldp|timeToLive Network I/O|Discovery Protocol|
Link Layer Discovery Protocol|
Time to Live
Datastore properties collected for host system objects have been disabled in this version of VCF Operations. This means
that they do not collect data by default.
Table 1401: Storage Path Properties Collected for Host System Objects
Property Key Property Name Description
storageAdapter|port_WWN Storage Adapter|Port WWN The port world wide name for storage adapter.
Available for FC adapters only.
Table 1402: Compliance Configuration Related Properties for Host System Objects
Property Key Property Name Description
config|security|password_max_days Configuration|Security|Password
Max Days
Password Max Days
config|security|welcome_message Configuration|Security|Welcome
Message Configured
Welcome Message Configured
config|security|issue Configuration|Security|SSH
Connection Banner Message
Configured
SSH Connection Banner Message Configured
config|security|host_client_session_timeout Configuration|Security|Host Client
Session Timeout
Host Client Session Timeout
config|security|has_lockdown_exception_use
rs
Configuration|Security|Has
Lockdown exception users
Has Lockdown exception users
Cluster Compute Resource Properties
VCF Operations collects configuration and summary properties for cluster compute resource objects.
Table 1403: License Properties for Cluster Objects
Property Key Property Name Description
License type License Type Displays the license type for the cluster
object
Expiry Expiry Displays the number of days remaining
before the license expires the cluster
object
Note:  An alert is generated if the license
threshold is
VMware by Broadcom  4479

---
## page 4480

 VMware Cloud Foundation 9.0
Property Key Property Name Description
• >= 80% - Warning
• >= 90% - Immediate
• =95% - Catastrophic
Table 1404: Configuration Properties Collected for Cluster Compute Resource Objects
Property Key Property Name Description
config|name Name Name
Table 1405: Summary Properties Collected for Cluster Compute Resource Objects
Property Key Property Name Description
Summary|Is Horizon Managed Is Horizon Managed This property displays whether the selected object
is managed by Horizon or not.
summary|parentDatacenter Parent data center This property displays the Parent data center.
summary|parentVcenter Parent vCenter This property displays the Parent vCenter.
summary|customTag|customTagValue Value This property displays the Custom Tag Value.
summary|tag vSphere Tag This property displays the vSphere Tag Name.
Table 1406: DR, DAS, and DPM Configuration Properties Collected for Cluster Compute Resource Objects
Property Key Property Name Description
configuration|drsconfig|enabled Enabled Indicates whether DRS is enabled
configuration|drsconfig|defaultVmBehavior Default DRS Behavior Default DRS Behavior
configuration|drsconfig|affinityRules Affinity Rules DRS Affinity Rules
configuration|dasconfig|enabled HA Enabled HA Enabled
configuration|dasconfig|
admissionControlEnabled
Admission Control Enabled Admission Control Enabled
configuration|dpmconfiginfo|enabled DPM Enabled DPM Enabled
configuration|dpmconfiginfo|
defaultDpmBehavior
Default DPM Behavior Default DPM Behavior
configuration|infraUpdateHaConfig|
remediation
Cluster Configuration|HA
Configuration|Remediation
This property displays the Remediation mode
taken by vSphere Cluster to deal with host failure.
The options available are Quarantine mode,
Maintenance mode, Mixed mode.
configuration|drsConfig|
pctIdleMBInMemDemand
Cluster Configuration|DRS
Configuration|Idle Consumed
Memory
configuration|drsConfig|targetBalance Cluster Configuration|DRS
Configuration|Tolerable
imbalance threshold
VMware by Broadcom  4480

---
## page 4481

 VMware Cloud Foundation 9.0
DRS properties are collected for disaster recovery. DAS properties are collected for high availability service, formerly
distributed availability service. DPM properties are collected for distributed power management.
Resource Pool Properties
VCF Operations collects configuration, CPU, memory, and summary properties for resource pool objects.
Table 1407: Configuration Properties Collected for Resource Pool Objects
Property Key Property Name Description
config|name Name Name
config|cpuAllocation|reservation Reservation CPU reservation
config|cpuAllocation|limit Limit CPU limit
config|cpuAllocation|expandableReservation Expandable Reservation CPU expandable reservation
config|cpuAllocation|shares|shares Shares CPU shares
config|memoryAllocation|reservation Reservation Memory reservation
config|memoryAllocation|limit Limit Memory limit
config|memoryAllocation|
expandableReservation
Expandable Reservation Memory expandable reservation
config|memoryAllocation|shares|shares Shares Memory shares
Table 1408: CPU Usage Properties Collected for Resource Pool Objects
Property Key Property Name Description
cpu|limit CPU Limit CPU Limit
cpu|reservation CPU reservation CPU Reservation
cpu|expandable_reservation CPU expandable reservation CPU Expandable Reservation
cpu|shares CPU Shares CPU Shares
cpu|corecount_provisioned Provisioned vCPU(s) Number of CPUs. It counts both the
vSocket and vCore. A VM with 2 vSockets
x 4 vCores each has 8 vCPU.
Table 1409: Memory Properties Collected for Resource Pool Objects
Property Key Property Name Description
mem|limit Memory limit Memory limit
mem|reservation Memory reservation Memory reservation
mem|expandable_reservation Memory expandable reservation Memory expandable reservation
mem|shares Memory Shares Memory Shares
VMware by Broadcom  4481

---
## page 4482

 VMware Cloud Foundation 9.0
Table 1410: Summary Properties Collected for Resource Pool Objects
Property Key Property Name Description
summary|customTag|customTagValue Value Custom Tag Value
summary|tag vSphere Tag vSphere Tag Name
Data Center Properties
VCF Operations collects configuration and summary properties for data center objects.
Table 1411: Configuration Properties Collected for Data Center Objects
Property Key Property Name Description
config|name Name Name
Table 1412: Summary Properties Collected for Data Center Objects
Property Key Property Name Description
summary|parentVcenter Parent Vcenter Parent Vcenter
summary|customTag|customTagValue Value Custom Tag Value
summary|tag vSphere Tag vSphere Tag Name
Storage Pod Properties
VCF Operations collects configuration and summary properties for storage pod objects.
Table 1413: Configuration Properties Collected for Storage Pod Objects
Property Key Property Name Description
config|name Name Name
config|sdrsconfig|vmStorageAntiAffinityRules VM storage antiaffinity rules Storage Distributed Resource Scheduler (SDRS)
VM anti-affinity rules
config|sdrsconfig|vmdkAntiAffinityRules VMDK antiaffinity rules Storage Distributed Resource Scheduler (SDRS)
Virtual Machine Disk (VMDK) anti-affinity rules
VMware Distributed Virtual Switch Properties
VCF Operations collects configuration and summary properties for VMware distributed virtual switch objects.
VMware by Broadcom  4482

---
## page 4483

 VMware Cloud Foundation 9.0
Table 1414: Configuration Properties Collected for VMware Distributed Virtual Switch Objects
Property Key Property Name Description
config|networkResourceManagementEnabled Configuration|Network IO Control This property shows the status of Network IO
Control. Enabled means control over Network IO
(using shares, limitations and reservation) are in
place on each port group.
config|name Name Name
Table 1415: Capability Properties Collected for VMware Distributed Virtual Switch Objects
Property Key Property Name Description
capability|nicTeamingPolicy NIC Teaming Policy NIC Teaming Policy
Distributed Virtual Port Group Properties
VCF Operations collects configuration and summary properties for distributed virtual port group objects.
Table 1416: Configuration Properties Collected for Distributed Virtual Port Group Objects
Property Key Property Name Description
config|portBinding Configuration|Port Binding This property shows how ports are assigned to
virtual machines connected to this distributed port
group. Available values: earlyBinding, ephemeral,
lateBinding.
config|portAllocation Configuration|Port Allocation This property shows the type of port allocation,
such as elastic or fixed. Options are: true=Elastic,
false=Fixed.
config|name Name Name
Configuration|Uplink Uplink Indicates whether the portgroup is uplink portgroup.
Table 1417: Summary Properties Collected for Distributed Virtual Port Group Objects
Property Key Property Name Description
summary|active_uplink_ports Active DV uplinks Active DV uplinks
Datastore Properties
VCF Operations collects configuration, summary, and properties about datastore use for datastore objects.
VMware by Broadcom  4483

---
## page 4484

 VMware Cloud Foundation 9.0
Table 1418: Configuration Properties of Datastore and Datastore Cluster Objects
Property Key Property Name Description
config|iormConfigStatus Configuration|Storage IO Control Status Displays the status of Storage IO Control.
If enabled control over Disk IO (using
shares, limitations and reservation) is in
place.Value: True or False.
summary|total_number_datastores Summary|Total Number of Datastores Displays the total number of member
datastores in the cluster.
summary|parentVcenter Summary|Parent vCenter Displays the details of the parent vCenter.
summary|parentDatacenter (GB) Summary|Parent Datacenter Displays the details of the parent
Datacenter.
Table 1419: Capacity Properties Collected for vSAN Datastore Objects
Property Key Property Name Description
Capacity|Available Space (GB) Available Space Displays the available disk space in GB.
Capacity|Provisioned (GB) Provisioned (GB) Displays the provisioned datastore size in
GB.
Capacity|Total Capacity (GB) Total Capacity (GB) Displays the total datastore capacity in
GB.
Capacity|Total Provisioned Consumer Space
(GB)
Total Provisioned Consumer Space (GB) Displays the total provisioned consumer
space in GB.
Capacity|Used Space (GB) Used Space (GB) Displays the used disk space in GB.
Capacity|Used Space (%) Used Space (%) Displays the used disk space in
percentage.
Capacity|Usable Capacity (GB) Usable Capacity (GB) Displays the usable disk capacity in GB.
Note:  Earlier the vSAN Datastore base
rate was calculated on the basis of Total
Capacity of the disk, now the vSAN
datastore base rate is calculated based on
the usable capacity.
Table 1420: Summary Properties Collected for Datastore Objects
Property Key Property Name Description
summary|vmfs_version VMFS (Virtual Machine File
System) Version
Displays the VMFS version number, contains both
major version and minor version number.
Note:  The VMFS version property is visible, only
when the datastore type is VMFS.
summary|diskCapacity Disk Capacity Disk Capacity
summary|isLocal Is Local Is local datastore
summary|customTag|customTagValue Value Custom Tag Value
summary|accessible Datastore Accessible Datastore Accessible
VMware by Broadcom  4484

---
## page 4485

 VMware Cloud Foundation 9.0
Property Key Property Name Description
summary|path Summary|Path
summary|scsiAdapterType Summary|SCSI Adapter Type This property is disabled by default.
summary|aliasOf Summary|Alias Of Indicates whether the datastore is an alias of
another. The published value is the container ID of
the datastore for which it is an alias.
Note:
This property may have 2 values. It's either "none",
that means the datastore is not an alias of another
datastore, or datastore <containerID> that is the
Container ID of the datastore for which this is an
alias.
Table 1421: Datastore Properties Collected for Datastore Objects
Property Key Property Name Description
datastore|hostcount Host Count Host Count
datastore|hostScsiDiskPartition Host SCSI Disk Partition Host SCSI Disk Partition
* datastore|maxObservedNumberRead Datastore I/O|Highest Observed Number of
Read Requests
Disabled
* datastore|maxObservedNumberWrite Datastore I/O|Highest Observed Number of
Write Requests
Disabled
* datastore|maxObservedOIO Datastore I/O|Highest Observed Outstanding
Requests
Disabled
* datastore|maxObservedRead Datastore I/O|Highest Observed Read
Latency
Disabled
* datastore|maxObservedReadLatency Datastore I/O|Highest Observed Read
Latency
Disabled
* datastore|maxObservedWrite Datastore I/O|Highest Observed Write
Latency
Disabled
* datastore|maxObservedWriteLatency Datastore I/O|Highest Observed Write
Latency
Disabled
Table 1422: Datastore Properties Collected for vVol Datastore Objects
Property Key Property Name Description
storageArray|modelId Storage Array|Model Storage array model of VVol datastore.
Note:  This property is published for vVol
datastores only and is available starting from
vCenter version 6.0.
storageArray|name Storage Array|Name Storage array name of vVol datastore.
Note:  This property is published for vVol
datastores only and is available starting from
vCenter version 6.0.
storageArray|id Storage Array|ID Storage array ID of vVol datastore.
VMware by Broadcom  4485

---
## page 4486

 VMware Cloud Foundation 9.0
Property Key Property Name Description
Note:  This property is published for vVol
datastores only and is available starting from
vCenter version 6.0.
storageArray|vendorId Storage Array|Vendor Storage array vendor of vVol datastore.
Note:  This property is published for vVol
datastores only and is available starting from
vCenter version 6.0.
protocolEndpoints|name Protocol Endpoints|Name Protocol endpoint's name of vVol datastore.
Note:  This is an instanced property that is
published per protocol endpoint instance (e. g.
eui.3362663138636633) for vVol datastores only. It
is available starting from vCenter version 6.0.
protocolEndpoints|type Protocol Endpoints|Type Protocol endpoint's type of vVol datastore.
Note:  This is an instanced property that is
published per protocol endpoint instance (e. g.
eui.3362663138636633) for vVol datastores only. It
is available starting from vCenter version 6.5.
protocolEndpoints|hosts Protocol Endpoints|Hosts Hosts associated with protocol endpoint of vVol
datasore.
Note:  This is an instanced property that is
published per protocol endpoint instance (e. g.
eui.3362663138636633) for vVol datastores only. It
is available starting from vCenter version 6.0.
Datastore properties marked with an asterisk (*) have been disabled in this version of VCF Operations. This means that
they do not collect data by default.
vSphere Pod Properties
VCF Operations collects summary and event properties for vSphere Pods.
Table 1423: Summary Properties Collected for vSphere Pod Objects
Property Key Localized Name Description
config|name Configuration|Name Resource name.
config|guestFullName Configuration|Guest OS from
vCenter
This is the value provided by vCenter. vCenter set
it during VM creation. The value may not match the
value inside the Guest.
config|version Configuration|Version Virtual Machine Version.
config|createDate Configuration|Creation Date Object Creation Date.
config|numVMDKs Configuration|Number of Virtual
Disks
Number of Virtual Disks.
config|faultTolerant Configuration|Fault Tolerant Fault tolerance enabled.
config|ft_role Configuration|FT Role Role of the VM in Fault Tolerance Group.
config|ft_peer_vm Configuration|FT Peer VM Peer of the VM in Fault Tolerance Group.
VMware by Broadcom  4486

---
## page 4487

 VMware Cloud Foundation 9.0
Property Key Localized Name Description
config|hardware|numCpu Configuration|Hardware|Number
of virtual CPUs
Number of virtual CPUs.
config|hardware|memoryKB Configuration|Hardware|Memory Memory.
config|hardware|thinEnabled Configuration|Hardware|Thin
Provisioned Disk
Thin Provisioned Disk.
config|hardware|numCoresPerSocket Configuration|Hardware|Number
of CPU cores per socket
Number of CPU cores per virtual socket.
config|hardware|numSockets Configuration|Hardware|Number
of virtual sockets
Number of virtual sockets.
config|hardware|diskSpace Configuration|Hardware|Disk
Space
Disk space metrics.
config|cpuAllocation|reservation Configuration|CPU Resource
Allocation|Reservation
config|cpuAllocation|limit Configuration|CPU Resource
Allocation|Limit
config|cpuAllocation|shares|shares Configuration|CPU Resource
Allocation|Shares|Shares
config|memoryAllocation|reservation Configuration|Memory Resource
Allocation|Reservation
config|memoryAllocation|limit Configuration|Memory Resource
Allocation|Limit
config|memoryAllocation|shares|shares Configuration|Memory Resource
Allocation|Shares|Shares
N/A
config|extraConfig|mem_hotadd Configuration|Extra Configuration|
Memory Hot Add
Memory Hot Add Configuration.
config|extraConfig|vcpu_hotadd Configuration|Extra Configuration|
vCPU Hot Add
vCPU Hot Add Configuration.
config|extraConfig|vcpu_hotremove Configuration|Extra Configuration|
vCPU Hot Remove
vCPU Hot Remove Configuration.
config|extraConfig|mem_tps_share Configuration|Extra Configuration|
VM MEM TPS
config|security|disable_autoinstall Configuration|Security|
Disable tools auto install
(isolation.tools.autoInstall.disable)
config|security|disable_console_copy Configuration|Security|Disable
console copy operations
(isolation.tools.copy.disable)
config|security|disable_console_dnd Configuration|Security|Disable
console drag and drop operations
(isolation.tools.dnd.disable)
config|security|enable_console_gui_options Configuration|Security|Enable
console GUI operations
(isolation.tools.setGUIOptions.enable)
N/A
VMware by Broadcom  4487

---
## page 4488

 VMware Cloud Foundation 9.0
Property Key Localized Name Description
config|security|disable_console_paste Configuration|Security|Disable
console paste operations
(isolation.tools.paste.disable)
config|security|disable_disk_shrinking_shrink Configuration|Security|
Disable virtual disk shrink
(isolation.tools.diskShrink.disable)
config|security|disable_disk_shrinking_wiper Configuration|Security|
Disable virtual disk wiper
(isolation.tools.diskWiper.disable)
config|security|disable_hgfs Configuration|Security|
Disable HGFS file transfers
(isolation.tools.hgfsServerSet.disable)
config|security|disable_independent_nonper
sistent
Configuration|Security|Avoid
using independent nonpersistent
disks (scsiX:Y.mode)
config|security|enable_intervm_vmci Configuration|Security|
Enable VM-to-VM
communication through VMCI
(vmci0.unrestricted)
config|security|enable_logging Configuration|Security|Enable VM
logging (logging)
config|security|disable_monitor_control Configuration|Security|
Disable VM Monitor Control
(isolation.monitor.control.disable)
config|security|enable_non_essential_3D_fe
atures
Configuration|Security|Enable 3D
features on Server and desktop
virtual machines (mks.enable3d)
config|security|disable_unexposed_features_
autologon
Configuration|Security|Disable
unexposed features - autologon
(isolation.tools.ghi.autologon.disable)
config|security|disable_unexposed_features_
biosbbs
Configuration|Security|Disable
unexposed features - biosbbs
(isolation.bios.bbs.disable)
config|security|disable_unexposed_features_
getcreds
Configuration|Security|Disable
unexposed features - getcreds
(isolation.tools.getCreds.disable)
config|security|disable_unexposed_features_
launchmenu
Configuration|Security|
Disable unexposed
features - launchmenu
(isolation.tools.ghi.launchmenu.change)
config|security|disable_unexposed_features_
memsfss
Configuration|Security|Disable
unexposed features - memsfss
(isolation.tools.memSchedFakeSampleStats.disable)
VMware by Broadcom  4488

---
## page 4489

 VMware Cloud Foundation 9.0
Property Key Localized Name Description
config|security|disable_unexposed_features_
protocolhandler
Configuration|Security|
Disable unexposed
features - protocolhandler
(isolation.tools.ghi.protocolhandler.info.disable)
config|security|disable_unexposed_features_
shellaction
Configuration|Security|Disable
unexposed features - shellaction
(isolation.ghi.host.shellAction.disable)
config|security|disable_unexposed_features_
toporequest
Configuration|Security|Disable
unexposed features - toporequest
(isolation.tools.dispTopoRequest.disable)
config|security|disable_unexposed_features_
trashfolderstate
Configuration|Security|
Disable unexposed
features - trashfolderstate
(isolation.tools.trashFolderState.disable)
config|security|disable_unexposed_features_
trayicon
Configuration|Security|Disable
unexposed features - trayicon
(isolation.tools.ghi.trayicon.disable)
config|security|disable_unexposed_features_
unity
Configuration|Security|Disable
unexposed features - unity
(isolation.tools.unity.disable)
config|security|disable_unexposed_features_
unity_interlock
Configuration|Security|
Disable unexposed
features - unity-interlock
(isolation.tools.unityInterlockOperation.disable)
config|security|disable_unexposed_features_
unity_taskbar
Configuration|Security|
Disable unexposed
features - unity-taskbar
(isolation.tools.unity.taskbar.disable)
config|security|disable_unexposed_features_
unity_unityactive
Configuration|Security|
Disable unexposed
features - unity-unityactive
(isolation.tools.unityActive.disable)
config|security|disable_unexposed_features_
unity_windowcontents
Configuration|Security|
Disable unexposed features
- unity-windowcontents
(isolation.tools.unity.windowContents.disable)
config|security|disable_unexposed_features_
unitypush
Configuration|Security|Disable
unexposed features - unitypush
(isolation.tools.unity.push.update.disable)
config|security|disable_unexposed_features_
versionget
Configuration|Security|Disable
unexposed features - versionget
(isolation.tools.vmxDnDVersionGet.disable)
config|security|disable_unexposed_features_
versionset
Configuration|Security|Disable
unexposed features - versionset
(solation.tools.guestDnDVersionSet.disable)
VMware by Broadcom  4489

---
## page 4490

 VMware Cloud Foundation 9.0
Property Key Localized Name Description
config|security|disable_vix_messages Configuration|Security|Disable
VIX messages from the VM
(isolation.tools.vixMessage.disable)
config|security|enable_vga_only_mode Configuration|Security|Disable
all but VGA mode on virtual
machines (svga.vgaOnly)
config|security|limit_console_connection Configuration|Security|Limit
number of console connections
(RemoteDisplay.maxConnection)
config|security|limit_log_number Configuration|Security|Limit
number of log files (log.keepOld)
config|security|limit_log_size Configuration|Security|Limit log
file size (log.rotateSize)
config|security|limit_setinfo_size Configuration|Security|Limit VMX
file size (tools.setInfo.sizeLimit)
config|security|enable_console_VNC Configuration|Security|
Enable access to VM
console via VNC protocol
(RemoteDisplay.vnc.enabled)
config|security|disable_device_interaction_co
nnect
Configuration|Security|
Disable unauthorized removal,
connection of devices
(isolation.device.connectable.disable)
config|security|disable_device_interaction_e
dit
Configuration|Security|
Disable unauthorized
modification of devices
(isolation.device.edit.disable)
config|security|enable_host_info Configuration|Security|Enable
send host information to guests
(tools.guestlib.enableHostInfo)
config|security|network_filter_enable Configuration|Security|
Enable dvfilter network APIs
(ethernetX.filterY.name)
config|security|vmsafe_cpumem_agentaddre
ss
Configuration|Security|VMsafe
CPU/memory APIs - IP address
(vmsafe.agentAddress)
config|security|vmsafe_cpumem_agentport Configuration|Security|VMsafe
CPU/memory APIs - port number
(vmsafe.agentPort)
config|security|vmsafe_cpumem_enable Configuration|Security|Enable
VMsafe CPU/memory APIs
(vmsafe.enable)
config|security|disconnect_devices_floppy Configuration|Security|Disconnect
floppy drive
VMware by Broadcom  4490

---
## page 4491

 VMware Cloud Foundation 9.0
Property Key Localized Name Description
config|security|disconnect_devices_cd Configuration|Security|Disconnect
CD-ROM
config|security|disconnect_devices_usb Configuration|Security|Disconnect
USB controller
config|security|disconnect_devices_parallel Configuration|Security|Disconnect
parallel port
config|security|disconnect_devices_serial Configuration|Security|Disconnect
serial port
config|security|pci_device_configured Configuration|Security|DCUI
timeout
runtime|memoryCap Runtime|Memory Capacity Memory Capacity.
cpu|limit CPU|CPU Limit CPU Limit.
cpu|reservation CPU|CPU reservation CPU Reservation.
cpu|speed CPU|CPU CPU Speed.
mem|host_reservation Memory|Host Active Machine Active.
mem|host_active Memory|Host Usage Machine Usage.
net|mac_address Network|Mac Address
net|ip_address Network|IP Address
net|subnet_mask Network|Subnet Mask
N/A
net|ipv6_address Network|IPv6 Address IPv6 Address.
net|ipv6_prefix_length Network|IPv6 Prefix Length IPv6 Prefix Length.
net|default_gateway Network|Default Gateway
net|nvp_vm_uuid Network|NVP VM UUID
N/A
net|vnic_type Network|Virtual NIC Type Virtual Machine's network adapter type.
net|vnic_label Network|Label Device label.
summary|UUID Summary|UUID Instance UUID in vCenter that uniquely identify all
virtual machine instances.
summary|MOID Summary|MOID Managed object ID in vCenter. This is unique in
scope of vCenter.
summary|swapOnlyDatastore Summary|Datastore with only
swap file
Datastore containing only the swap file and no other
files from this VM.
summary|customTag|customTagValue Summary|Custom Tag|Value Custom Tag Value.
summary|tag Summary|vSphere Tag vSphere Tag Name.
summary|tagJson Summary|vSphere Tag Json vSphere Tag in Json format.
summary|folder Summary|vSphere Folder vSphere Folder Name.
summary|parentCluster Summary|Parent Cluster Parent Cluster.
summary|parentHost Summary|Parent Host Parent Host.
summary|parentDatacenter Summary|Parent Datacenter Parent Datacenter.
summary|parentNamespace Summary|Parent Namespace Parent Namespace.
VMware by Broadcom  4491

---
## page 4492

 VMware Cloud Foundation 9.0
Property Key Localized Name Description
summary|parentVcenter Summary|Parent vCenter Parent vCenter.
summary|parentFolder Summary|Parent Folder Parent Folder.
summary|datastore Summary|Datastore(s) Datastore(s).
summary|guest|fullName Summary|Guest Operating
System|Guest OS from Tools
This is the value provided by VMware Tools. This
value will differ to the value set in vCenter if the
Guest OS was upgraded, or a different Guest OS
was installed.
summary|guest|ipAddress Summary|Guest Operating
System|Guest OS IP Address
Guest OS IP Address.
summary|guest|hostName Summary|Guest Operating
System|Hostname
Hostname of the guest operating system, if known.
summary|guest|toolsRunningStatus Summary|Guest Operating
System|Tools Running Status
Guest Tools Running Status.
summary|guest|toolsVersionStatus2 Summary|Guest Operating
System|Tools Version Status
Guest Tools Version Status 2.
summary|guest|toolsVersion Summary|Guest Operating
System|Tools Version
VM tools version installed on guest OS.
summary|guest|vrealize_operations_agent_id Summary|Guest Operating
System|vRealize Operations
Agent ID
An ID to identify a VM in Agent Adapter's world.
summary|guest|vrealize_operations_euc_ag
ent_id
Summary|Guest Operating
System|vRealize Operations Euc
Agent ID
An ID to identify a VM in Agent Adapter's world.
summary|config|numEthernetCards Summary|Configuration|Number
of NICs
Number of NICs.
summary|config|productName Summary|Configuration|Product
Name
Product Name.
summary|config|appliance Summary|Configuration|Applianc
e
Appliance.
summary|runtime|isIdle Summary|Runtime|Idleness
indicator
This property indicates whether the monitored
instance is idle or not.
summary|runtime|powerState Summary|Runtime|Power State Power State.
summary|runtime|connectionState Summary|Runtime|Connection
State
Connection State.
summary|smbiosUUID SMBIOS UUID System Management BIOS UUID of a virtual
machine.
Note:  The SMBIOS UUID metric for vSphere
Pod is disabled by default. You have to enable the
metric at the policy level.
guestfilesystem|capacity_property Guest File System|Guest File
System Capacity Property
Total capacity of guest file system as a property.
guestfilesystem|capacity_property_total Guest File System|Total Capacity
Property
Total capacity of guest file system as a property.
virtualDisk|datastore Virtual Disk|Datastore Datastore.
VMware by Broadcom  4492

---
## page 4493

 VMware Cloud Foundation 9.0
Property Key Localized Name Description
virtualDisk|configuredGB Virtual Disk|Configured Virtual Disk configured disk space.
virtualDisk|label Virtual Disk|Label Device Label.
virtualDisk|fileName Virtual Disk|File Name Virtual Disk file name.
diskspace|snapshot|mor Disk Space|Snapshot|Managed
Object Reference
Managed Object Reference.
diskspace|snapshot|name Disk Space|Snapshot|Name Snapshot name.
diskspace|snapshot|numberOfDays Disk Space|Snapshot|Number of
Days Old
Number of days since snapshot creation.
diskspace|snapshot|snapshotAge Disk Space|Snapshot|Age (Days) Virtual Machine's topmost snapshot age in days.
diskspace|snapshot|creator Disk Space|Snapshot|Creator Creator.
diskspace|snapshot|description Disk Space|Snapshot|Description Snapshot description.
vsan|policy|compliance vSAN|VM Storage Policies|
Compliance
Compliance status of the VM storage object.
datastore|maxObservedNumberRead Datastore|Highest Observed
Number of Read Requests
Highest Observed Number of Read Requests.
datastore|maxObservedRead Datastore|Highest Observed
Read Rate
Highest Observed Read Rate (KBps).
datastore|maxObservedNumberWrite Datastore|Highest Observed
Number of Write Requests
Highest Observed Number of Write Requests.
datastore|maxObservedWrite Datastore|Highest Observed
Write Rate
Highest Observed Write Rate (KBps).
datastore|maxObservedOIO Datastore|Highest Observed
Outstanding Requests
Highest Observed Outstanding Requests.
Table 1424: Compliance Configuration Related Properties for vSphere Pod Objects
Property Key Property Name Description
config|security|disconnect_devices_virtualhd
audiocard
Configuration|Security|Virtual HD
Audio Card Disconnected
NIL
config|security|disconnect_devices_virtualah
cicontroller
Configuration|Security|Virtual
AHCI Controller Disconnected
NIL
config|security|disconnect_devices_virtualen
soniq1371
Configuration|Security|Virtual
Ensoniq 1371 Disconnected
NIL
Namespace Properties
VCF Operations collects summary and event properties for Namespace.
Table 1425: Summary Properties Collected for Namespace Objects
Property Key Localized Name Description
config|name Configuration|Name Resource name
VMware by Broadcom  4493

---
## page 4494

 VMware Cloud Foundation 9.0
Property Key Localized Name Description
config|resourceLimits|namespace|cpu Configuration|Resource Limits|
Namespaces|CPU
CPU
config|resourceLimits|namespace|mem Configuration|Resource Limits|
Namespaces|Memory
Memory
config|resourceLimits|namespace|diskspace Configuration|Resource Limits|
Namespaces|Disk Space
Disk space metrics
config|resourceLimits|containers|cpu_request Configuration|Resource Limits|
Containers|CPU Request
CPU Request Default
config|resourceLimits|containers|cpu_limit Configuration|Resource Limits|
Containers|CPU Limit
CPU Limit Default
config|resourceLimits|containers|mem_reque
st
Configuration|Resource Limits|
Containers|Memory Request
Memory Request Default
config|resourceLimits|containers|mem_limit Configuration|Resource Limits|
Containers|Memory Limit
Memory Limit Default
config|objectLimits|compute|pod_count Configuration|Object Limits|
Compute|Pods
Number of Pods
config|objectLimits|compute|deployment_cou
nt
Configuration|Object Limits|
Compute|Deployments
Deployments
config|objectLimits|compute|job_count Configuration|Object Limits|
Compute|Jobs
Jobs
config|objectLimits|compute|daemon_sets Configuration|Object Limits|
Compute|Daemon Sets
Daemon Sets
config|objectLimits|compute|replica_sets Configuration|Object Limits|
Compute|Replica Sets
Replica Sets
config|objectLimits|compute|replication_cont
rollers
Configuration|Object Limits|
Compute|Replication Controllers
Replication Controllers
config|objectLimits|compute|stateful_sets Configuration|Object Limits|
Compute|Stateful Sets
Stateful Sets
config|objectLimits|storage|config_maps Configuration|Object Limits|
Storage|Config Maps
Config Maps
config|objectLimits|storage|secret_count Configuration|Object Limits|
Storage|Secrets
Secrets
config|objectLimits|storage|persistent_volum
e_claim
Configuration|Object Limits|
Storage|Persistent Volume Claim
Persistent Volume Claim
config|objectLimits|network|services Configuration|Object Limits|
Network|Services
Services
summary|parentDatacenter Summary|Parent Datacenter Parent Datacenter
summary|parentCluster Summary|Parent Cluster Parent Cluster
summary|parentVcenter Summary|Parent vCenter Parent vCenter
mem|limit Memory|Memory limit Memory limit
mem|reservation Memory|Memory reservation Memory reservation
VMware by Broadcom  4494

---
## page 4495

 VMware Cloud Foundation 9.0
Property Key Localized Name Description
mem|expandable_reservation Memory|Memory expandable
reservation
Memory Expandable Reservation
mem|shares Memory|Memory Shares Memory Shares
cpu|limit CPU|CPU Limit CPU Limit
cpu|reservation CPU|CPU Reservation CPU Reservation
cpu|expandable_reservation CPU|CPU expandable
reservation
CPU expandable Reservation
cpu|shares CPU|CPU Shares CPU Shares
cpu|corecount_provisioned CPU|Provisioned vCPU(s) Number of CPUs. It counts both the vSocket and
vCore. A VM with 2 vSockets x 4 vCores each has
8 vCPU.
Tanzu Kubernetes cluster Properties
VCF Operations collects summary and event properties forTanzu Kubernetes clusters.
Table 1426: Summary Properties Collected for Tanzu Kubernetes cluster Objects
Property Key Localized Name Description
config|name Configuration|Name Resource name
config|cpuAllocation|reservation Configuration|CPU Resource
Allocation|Reservation
N/A
config|cpuAllocation|limit Configuration|CPU Resource
Allocation|Limit
N/A
config|cpuAllocation|expandableReservation Configuration|CPU Resource
Allocation|Expandable
Reservation
N/A
config|cpuAllocation|shares|shares Configuration|CPU Resource
Allocation|Shares|Shares
N/A
config|memoryAllocation|reservation Configuration|Memory Resource
Allocation|Reservation
N/A
config|memoryAllocation|limit Configuration|Memory Resource
Allocation|Limit
N/A
config|memoryAllocation|expandableReserva
tion
Configuration|Memory Resource
Allocation|Expandable
Reservation
N/A
config|memoryAllocation|shares|shares Configuration|Memory Resource
Allocation|Shares|Shares
N/A
cpu|limit CPU|CPU Limit CPU Limit
cpu|reservation CPU|CPU Reservation CPU Reservation
cpu|expandable_reservation CPU|CPU expandable
reservation
CPU expandable Reservation
VMware by Broadcom  4495

---
## page 4496

 VMware Cloud Foundation 9.0
Property Key Localized Name Description
cpu|shares CPU|CPU Shares CPU Shares
cpu|corecount_provisioned CPU|Provisioned vCPU(s) Number of CPUs. It counts both the vSocket and
vCore. A VM with 2 vSockets x 4 vCores each has
8 vCPU.
mem|limit Memory|Memory limit Memory limit
mem|reservation Memory|Memory reservation Memory reservation
mem|expandable_reservation Memory|Memory expandable
reservation
Memory Expandable Reservation
mem|shares Memory|Memory Shares Memory Shares
summary|parentDatacenter Summary|Parent Datacenter Parent Datacenter
summary|parentNamespace Summary|Parent Namespace Parent Namespace
All Folder Properties
VCF Operations collects configuration and summary properties for All Folders.
Table 1427: Summary Properties Collected for All Folder Objects
Property Key Property Name Description
summary|parentDatacenter Summary|Parent Datacenter This property shows the details of the parent
datacenter.
summary|parentVcenter Summary|Parent vCenter This property shows the details of the parent
vCenter.
summary|tag Summary|vSphere Tag This property shows the details of the vSphere tag
name.
Self-Monitoring Properties for VCF Operations
VCF Operations uses the VCF Operations adapter to collect properties that monitor its own objects. These self-monitoring
properties are useful for monitoring changes within VCF Operations.
Analytics Properties
VCF Operations collects properties for the VCF Operations analytics service.
Table 1428: Properties Collected for Analytics Service Objects
Property Key Property Name Description
HAEnabled HA Enabled Indicates HA is enabled with a value of 1, disabled
with a value of 0.
ControllerDBRole Role Indicates persistence service role for the controller:
0 – Primary, 1 – Replica, 4 – Client..
ShardRedundancyLevel Shard redundancy level The target number of redundant copies for Object
data.
VMware by Broadcom  4496

---
## page 4497

 VMware Cloud Foundation 9.0
Property Key Property Name Description
LocatorCount Locator Count The number of configured locators in the system
ServersCount Servers Count The number of configured servers in the system
Node Properties
VCF Operations collects properties for the VCF Operations node objects.
Table 1429: Configuration Properties Collected for Node Objects
Property Key Property Name Description
config|numCpu Number of CPU Number of CPUs
config|numCoresPerCpu Number of cores per CPU Number of cores per CPU
config|coreFrequency Core Frequency Core Frequency
Table 1430: Memory Properties Collected for Node Objects
Property Key Property Name Description
mem|RAM System RAM System RAM
Table 1431: Service Properties Collected for Node Objects
Property Key Property Name Description
service|proc|pid Process ID Process ID
OS and Application Monitoring Properties
Properties are collected for operating systems, application services, remote checks, Linux processes, and Windows
services which can be used to create reports, views, and dashboards.
Guest Information Properties
VCF Operations displays the following guest information properties for all objects created by the OS and Application
Monitoring management pack.
• Guest Info
– Hostname
– IP
– OS Name
– OS Version
– Telegraf Version
Other properties of operating systems and application services are available under Properties > Tags.
Service Discovery Properties
VCF Operations displays object properties for service discovery.
VMware by Broadcom  4497

---
## page 4498

 VMware Cloud Foundation 9.0
Service Discovery Adapter Instance Properties
VCF Operations displays the following properties for the service discovery adapter instance.
Table 1432: Service Discovery Adapter Instance Properties
Property Name Description
Action Identifier An FQDN and IP pair of the end point vCenter Server that is used
to identify the adapter instance that has to run actions on the
vCenter.
Virtual Machine Properties
VCF Operations displays the following properties for virtual machines.
Table 1433: Virtual Machine Properties
Property Name Description
Guest OS Services|Authentication Method Refers to the VM guest operating system authentication method.
The guest operating system can be authenticated either via a
common user/password or a guest alias.
Guest OS Services|Discovery Status Reflects the result of service discovery operation on the VM's
guest operating system.
Guest OS Services|Authentication Status Guest operating system authentication status.
Guest OS Services|Inbound Ports List of VM inbound ports. These are the ports on which the
discovered services are listening.
SRM Info|Protection Group Protection group to which the VM belongs.
SRM Info|Recovery Plans List of recovery plans covering the VM.
Services Properties
VCF Operations displays the following properties for services.
Table 1434: Services Properties
Property Name Description
Type The name of the service type.
Install Path The install path.
Ports List of service listening ports.
Virtual Machine The name of the parent VM.
Virtual Machine MOID The MOID of the VM.
Version Version of the discovered service.
Is Application Member Indicates that the service is a member of the group of services
forming an application.
VMware by Broadcom  4498

---
## page 4499

 VMware Cloud Foundation 9.0
Property Name Description
Category Category of the service.
Connection Type If there is a remote process that was connected to one of the
listening ports of the given service, then the property's value is set
to Incoming. If not, it is set to Outgoing. If there is no connection to
another service, then the value of the property is set to  N/A.
Has Dynamic Port Indicates whether the service has dynamic ports or not.
Status Indicates the status of the service.
Up: The service is running.
Down: The service is unavailable on the monitored VM.
Unavailable: The service is unavailable on a VM that is not being
monitored.
None: The service is not available within 7 days.
Properties for vSAN
VCF Operations displays object properties for vSAN.
Properties for vSAN Disk Groups
VCF Operations displays the following property for vSAN disk groups:
• vSAN Disk Groups: Configuration|vSAN Configuration
• vSAN Disk Groups: Configuration | Number of Disks
Properties for vSAN Cluster
The VCF Operations displays the following properties for vSAN cluster.
Property Name Description
Configuration|vSAN|vSAN ESA Indicates whether vSAN ESA configuration is enabled on the
vSAN cluster.
Configuration|vSAN|Deduplication and Compression Enabled Indicates whether deduplication and compression is eanbled on
the vSAN cluster.
Configuration|vSAN|Preferred fault domain Indicates whether the preferred fault domain is not set for the
witness host in a vSAN Stretched cluster.
Configuration|vSAN|Stretched Cluster Indicates whehter vSAN stretch cluster is enabled or not.
Configuration|vSAN|vSAN Configuration Indicates whether the vSAN cluster is configured or not.
Configuration|vSAN|Encryption Indicates whether the vSAN cluster is encypted or not.
Configuration | vSAN | File Service Indicates whether vSAN File Services is enabled or not.
Configuration | vSAN | File Service Domain:<domainName> | DNS
Servers
Indicates the IP addresses of DNS servers, which are used to
resolve the host names within the DNS domain.
Configuration | vSAN | File Service Domain:<domainName> | DNS
Suffixes
Indicates the list of DNS suffixes which can resolved by the DNS
servers.
Configuration | vSAN | File Service Domain:<domainName> |
Gateway
Indicated the default gateway IP address for the file service
access point.
VMware by Broadcom  4499

---
## page 4500

 VMware Cloud Foundation 9.0
Property Name Description
Configuration | vSAN | File Service Domain:<domainName> |
Primary IP
Indicates the primary IP address for the file service.
Configuration | vSAN | File Service Domain:<domainName> |
Subnet Mask
Indicates the subnet mask for the vSAN cluster.
Summary | Type vSAN Cluster Type
Configuration | vSAN | File Service Domain:<domainName> | IP
Address :<ipaddress> | FQDN
Indicates the Full Qualified Domain name (FQDN) to be used with
IP address for the vSAN File Server instance.
 Properties for vSAN Enabled Host
The VCF Operations displays the following property for vSAN enabled host.
• Configuration|vSAN Enabled
• Configuration|vSAN|Encryption
Properties for vSAN Cache Disk
VCF Operations displays the following properties for the vSAN cache disk.
Properties for vSAN include:
Component Metrics
Configuration • Configuration Properties|Name
• Configuration Properties|Size
• Configuration Properties|Vendor
• Configuration Properties|Type
• Configuration Properties|Queue Depth
• Configuration|vSAN|Encryption
• Configuration | Model
SCSI SMART Statistics • SCSI SMART Statistics|Media Wearout Indicator Threshold
• SCSI SMART Statistics|Write Error Count Threshold
• SCSI SMART Statistics|Read Error Count Threshold
• SCSI SMART Statistics|Reallocated Sector Count Threshold
• SCSI SMART Statistics|Raw Read Error Rate Threshold
• SCSI SMART Statistics|Drive Temperature Threshold
• SCSI SMART Statistics|Drive Rated Max Temperature Threshold
• SCSI SMART Statistics|Write Sectors TOT Count Threshold
• SCSI SMART Statistics|Read Sectors TOT Count Threshold
• SCSI SMART Statistics|Initial Bad Block Count Threshold
 Properties for vSAN Capacity Disk
VCF Operations displays the following properties for the vSAN capacity disk.
Properties for vSAN include:
VMware by Broadcom  4500

---
## page 4501

 VMware Cloud Foundation 9.0
Component Metrics
Configuration • Configuration Properties|Name
• Configuration Properties|Size
• Configuration Properties|Vendor
• Configuration Properties|Type
• Configuration Properties|Queue Depth
• Configuration|vSAN|Encryption
SCSI SMART Statistics • SCSI SMART Statistics|Media Wearout Indicator Threshold
• SCSI SMART Statistics|Write Error Count Threshold
• SCSI SMART Statistics|Read Error Count Threshold
• SCSI SMART Statistics|Reallocated Sector Count Threshold
• SCSI SMART Statistics|Raw Read Error Rate Threshold
• SCSI SMART Statistics|Drive Temperature Threshold
• SCSI SMART Statistics|Drive Rated Max Temperature Threshold
• SCSI SMART Statistics|Write Sectors TOT Count Threshold
• SCSI SMART Statistics|Read Sectors TOT Count Threshold
• SCSI SMART Statistics|Initial Bad Block Count Threshold
Properties for vSAN File Server
The VCF Operations displays the following properties for vSAN file server.
• Configuration | vSAN | Primary
• Configuration | vSAN | FQDN
Properties for vSAN File Share
The VCF Operations displays the following properties for vSAN file share.
• Configuration |vSAN| Domain Name
• Configuration | vSAN| Hard Quota
• Configuration |vSAN| Soft Quota
• Configuration |vSAN | Label|<key>
• Configuration |vSAN | Access Point|<key>
• Configuration | vSAN | Permission:<permission> | Client IP Range
• Configuration | vSAN | Permission:<permission> | Root Squash
Properties for vSAN Storage Pool
The VCF Operations displays the following properties for vSAN Storage Pool.
Property Name Description
Configuration|Number of Disks Displays the total number of vSAN ESA disks in the storage pool.
Properties for vSAN ESA Disk
The VCF Operations displays the following properties for the vSAN ESA Disk.
VMware by Broadcom  4501

---
## page 4502

 VMware Cloud Foundation 9.0
Property Name Description
Configuration|Model Displays the model number of the SCSI device.
Configuration|Name Displays the user configurable name for the SCSI device.
Configuration|Queue Depth Displays the queue depth of the SCSI device.
Configuration|Size (GB) Displays the size of SCSI device using the Logial Block
Addressing Scheme (number of blocks) x (size of blocks).
Configuration|Type Displays the type of the SCSI device.
Configuration|Vendor Displays the vendor for the SCSI device.
Configuration | vSAN | Encryption Indicates whether data encryption is enable on vSAN disk. If
enabled all the VM data residing on the vSAN disk is encrypted.
Properties for Certificate Monitoring
VCF Operations displays the following certificate summary properties.
Table 1435: Adapter Instance Certificate Summary Properties, published on Adapter Instance Object
Property Name Property Key Description
End Date Certificate Summary:endpointIdentifier|End
Date
End date of the adapter certificate.
Start Date Certificate Summary: endpointIdentifier |
Start Date
Start date of the adapter certificate.
Issuer DN Certificate Summary:endpointIdentifier|
Issuer DN
Distinguished name of the adapter
certificate issuer.
No. of days to expire Certificate Summary:endpointIdentifier|No.
of days to expire
Number of days left before the expiration of
the adapter certificate.
Table 1436: Authentication Source Certificate Summary Properties, published on Universe Object
Property Name Property Key Description
End Date Certificate Summary|Authentication
Sources:authenticationSourceId|End Date
End date of the authentication source
certificate.
Start Date Certificate Summary|Authentication
Sources: authenticationSourceId|Start Date
Start date of the authentication source
certificate.
Issuer DN Certificate Summary|Authentication
Sources:authenticationSourceId|Issuer DN
Distinguished name of the authentication
source certificate issuer.
No. of days to expire Certificate Summary|Authentication
Sources:authenticationSourceId|No. of
days to expire
Number of days left before the expiration of
the authentication source certificate
VMware by Broadcom  4502

---
## page 4503

 VMware Cloud Foundation 9.0
Table 1437: Outbound Plugin Certificate Summary Properties, published on Universe Object
Property Name Property Key Description
End Date Certificate Summary|Outbound
Plugins:outboundPluginId|End Date
End date of the outbound plugin certificate
Start Date Certificate Summary|Outbound Plugins :
outboundPluginId |Start Date
Start date of the outbound plugin certificate
Issuer DN Certificate Summary| Outbound Plugins :
outboundPluginId |Issuer DN
Distinguished name of the outbound plugin
certificate issuer.
No. of days to expire Certificate Summary| Outbound Plugins :
outboundPluginId |No. of days to expire
Number of days left before the expiration of
the outbound plugin certificate
Properties for VCF Automation
VCF Operations displays properties for VCF Automation objects.
Some of the useful properties for project objects deployed through VCF Automation are as follows:
• Project|CustomProperties: Custom properties defined for the project.
• Project|OrganizationID: Organization ID of the project.
• Project|userEmail: Email address of the user for the project.
One of the useful properties for the deployment object is:
• Deployment|User: User associated with the deployment.
One of the useful properties for the cloud zone object is:
• CloudAutomation|ResourceTags: Resource tags associated with the cloud zone.
One of the useful properties for the blueprint object is:
• Blueprint|User: User associated with the blueprint.
One of the useful properties for the CASworkd object is:
• CASWorld|metering|MeteringPolicyId: Metering policy ID associated with the CAS World object.
One of the useful properties for the virtual machine object is:
• Cloud Automation|CustomProperties: Custom properties associated with the virtual machine.
One of the useful properties for Cloud Zone is:
• Cloud Automation|Resource Tags: Resources tags associated with the cloud automation.
Properties in the NSX
VCF Operations displays the following properties for the NSX adapter.
Table 1438: Properties in the NSX Adapter
Resource Properties common in NSX and NSX
on VMware Cloud on AWS Properties in NSX on-premise
Properties NSX on
VMware Cloud on
AWS
Management Cluster • NSXT Product Version
VMware by Broadcom  4503

---
## page 4504

 VMware Cloud Foundation 9.0
Resource Properties common in NSX and NSX
on VMware Cloud on AWS Properties in NSX on-premise
Properties NSX on
VMware Cloud on
AWS
• Status Summary|Cluster Status|
Management Cluster Status
• Status Summary|Cluster Status|
Controller Cluster Status
• Status Summary|vIDM Connection
Status
• Status Summary|Compute Managers|
<ComputeManagerName>|Status
• Configuration Maximums
– Compute Manager count
– Prepared vC Cluster count
Firewall Section Summary
• Create Time
• Create User
• Last Modified Time
• Last Modified User
• Protection
• Revision
• System Owned
Configuration
• Firewall Rule Count Size
Configuration
• Firewall Stateful
Configuration
• Type
• Domain id
• Precedence
• Category
Transport Node
Note:  This object is
specific to NSX on-
premise and is not
available in NSX on
VMware Cloud on
AWS.
• Summary
– Create Time
– Create User
– Last Modified Time
– Last Modified User
– Protection
– Revision
– System Owned
– Summary|FQDN
• Status Summary
– Transport Node State
– Transport Node Deployment State
– LCA Connectivity Status
– Management Plane Connectivity
Status
– Host Node Deployment Status
– Management connection Status
– Controller connection Status
VMware by Broadcom  4504

---
## page 4505

 VMware Cloud Foundation 9.0
Resource Properties common in NSX and NSX
on VMware Cloud on AWS Properties in NSX on-premise
Properties NSX on
VMware Cloud on
AWS
• Load Balancer Usage
– Current Small LB services
– Current Medium LB services
– Current Large LB services
– Current Extra Large LB services
– Current LB Pools
– Current LB Pool Members
– Current LB Virtual Servers
– Remaining Small LB services
– Remaining Medium LB services
– Remaining Large LB services
– Remaining Extra Large LB services
– Remaining LB Pool Members
• Tunnels|<Tunnel-Name>|Status
• File Systems|<FileSystemMount>
– Total
– Type
– File System ID
Load Balancer
Service
Note:  This object is
specific to NSX on-
premise and is not
available in NSX on
VMware Cloud on
AWS.
• Summary
– Create Time
– Create User
– Last Modified Time
– Last Modified User
– Protection
– Revision
– System Owned
– LB Service Operational Status
Load Balancer Virtual
Server
Note:  This object is
specific to NSX on-
premise and is not
available in NSX on
VMware Cloud on
AWS.
• Summary
– Create Time
– Create User
– Last Modified Time
– Last Modified User
– Protection
– Revision
– System Owned
– LB Virtual Operational State
Load Balancer Pool
Note:  This object is
specific to NSX on-
premise and is not
available in NSX on
VMware Cloud on
AWS.
• Summary
– Create Time
– Create User
– Last Modified Time
– Last Modified User
– Protection
– Revision
– System Owned
– Status
Transport Zone Summary
• Create Time
VMware by Broadcom  4505

---
## page 4506

 VMware Cloud Foundation 9.0
Resource Properties common in NSX and NSX
on VMware Cloud on AWS Properties in NSX on-premise
Properties NSX on
VMware Cloud on
AWS
Note:  This object is
specific to NSX on-
premise and is not
available in NSX on
VMware Cloud on
AWS.
• Create User
• Last Modified Time
• Last Modified User
• Protection
• Revision
• Switch Mode
• System Owned
Logical Router • Summary
– Create Time
– Create User
– Last Modified Time
– Last Modified User
– Protection
– Revision
– System Owned
• Configuration
– Failover Mode
– High Availability Mode
– Edge Cluster Id
– Router Type
• Services Enabled
– HA Status Per Transport Node|
<TransportNodeID>|HA Status
– Firewall Enabled
– Load balancer Enabled
– DNS Enabled
– L2VPN Enabled
– IPSEC VPN Enabled
Router Service 1. Tier-0 Router Services ? BGP
Service
– Summary|BGP Neighbor Count
2. Tier-1 Router Services ? NAT Rules
– Summary|NAT Rule Count
3. Tier-1 Router Services ? Static
Routes
– Summary|Static Route Count
• All logical routers ? Static Routes ?
Summary|Static Route Count
• All logical routers ? NAT Rule ?
Summary|NAT Rule Count
• Tier 0 ? BGP Service ? Summary
– ECMP Status
– Status
• Tier 0 ? BFD Service ? Summary
– Status
– BFD Neighbor Count
• Tier 0 ? Route Redistribution ?
Summary
– Status
– Redistribution Rule count
• Tier 1 ? Route Advertisement ?
Summary|
– Route Advertisement Count
– Status
Logical Switch • Summary
– Create Time
– Create User
– Last Modified Time
– Last Modified User
– Protection
– Revision
– System Owned
• Summary
– Logical Switch State
• Configuration
– Replication Mode
– Admin State
– VNI
Configuration
• Type
Management
Appliances
NSXT API Version
VMware by Broadcom  4506

---
## page 4507

 VMware Cloud Foundation 9.0
Resource Properties common in NSX and NSX
on VMware Cloud on AWS Properties in NSX on-premise
Properties NSX on
VMware Cloud on
AWS
Note:  This object is
specific to NSX on-
premise and is not
available in NSX on
VMware Cloud on
AWS.
Manager Node
Note:  This object is
specific to NSX on-
premise and is not
available in NSX on
VMware Cloud on
AWS.
• NSXT Manager Node Version
• Connectivity Status|Management Plane
Connectivity Status
Group Configuration Maximums|Count
• IP Address Count
• Expressions Count
• vm Count
Configuration Maximums|Count|Tag Count
Edge Cluster
Note:  This object is
specific to NSX on-
premise and is not
available in NSX on
VMware Cloud on
AWS.
Summary
• Create Time
• Create User
• Last Modified Time
• Last Modified User
• Protection
• Revision
• System Owned
• Edge Cluster Member Type
Placement Group Properties
The following properties are available for each Placement Group instance in your VCF Operations environment.
Table 1439: Placement Group Properties
Service Property
StatePlacement Group
Strategy
Properties for VeloCloud Gateway
VCF Operations displays properties of VeloCloud Gateway objects.
Some of the useful properties for VeloCloud Gateway are as follows:
• Summary | Core Count
• Summary | Gateway Activation Status
• Summary | Gateway Network Interface Errors
• Summary | Gateway Time Zone
VMware by Broadcom  4507