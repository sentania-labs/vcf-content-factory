# policies (VCF 9.0, pages 3130-3155)


---
## page 3130

 VMware Cloud Foundation 9.0
• Kubernetes Performance
– CPU and memory usage.
– vSphere Supervisor and VKS Clusters performance.
• vSphere Supervisor
– Monitor the critical components of the vSphere Supervisor.
Using the vSphere Supervisor Dashboards
Together, these dashboards offers the following capabilities:
• High-Level Cluster Overview
– The dashboard offers a summary of cluster health, showing key metrics such as CPU usage, memory consumption,
and node availability.
– You can quickly spot clusters with performance bottlenecks before diving into detailed analysis.
• Drill-Down Approach for Root Cause Analysis
– If an issue is detected at the cluster level, you can navigate into child objects such as namespaces, nodes, and
pods to pinpoint the source.
– Example: If CPU throttling is detected at the cluster level, users can filter to see which namespaces or pods are
consuming excessive CPU.
• Real-Time Monitoring with Push-Based Data Collection
– Unlike traditional pull-based methods, metrics are pushed to the Cloud Proxy in real time, allowing for faster
detection of performance spikes.
– Users can correlate metrics over time, helping them understand trends that may lead to potential failures.
• Supervisor and Guest Cluster Insights
– The Supervisor Dashboard monitors critical lifecycle components. If a Supervisor goes down, it may impact all
associated VKS Clusters.
– You can see which clusters are affected and take corrective action immediately.
• Debugging Pods and Containers
– The dashboard provides alerts on failed pods, frequent container restarts, and out-of-memory (OOM) errors.
– You can filter by node or namespace to isolate problematic workloads.
Configuring and Managing Policies
To create a policy, you can inherit the settings from an existing policy, and you can modify the settings in existing policies
if you have adequate permissions. After you create a policy, or edit an existing policy, you can apply the policy to one or
more groups of objects.
Policies
A policy is a set of rules that you define for VCF Operations to use to analyze and display information about the objects
in your environment. You can create, modify, and administer policies to determine how VCF Operations displays data in
dashboards, views, and reports.
How Policies Relate to Your Environment
VCF Operations policies support the operational decisions established for your IT infrastructure and business units.
With policies, you control what data VCF Operations collects and reports on for specific objects in your environment.
Each policy can inherit settings from other policies, and you can customize and override various analysis settings, alert
definitions, and symptom definitions for specific object types, to support the service Level agreements and business
priorities established for your environment.
VMware by Broadcom  3130

---
## page 3131

 VMware Cloud Foundation 9.0
When you manage policies, you must understand the operational priorities for your environment, and the tolerances for
alerts and symptoms to meet the requirements for your business critical applications. Then, you can configure the policies
so that you apply the correct policy and threshold settings for your production and test environments.
Policies define the settings that VCF Operations applies to your objects when it collects data from your environment. VCF
Operations applies policies to newly discovered objects, such as the objects in an object group. For example, you have
an existing VMware adapter instance, and you apply a specific policy to the group named World. When a user adds a new
virtual machine to the vCenter instance, the VMware adapter reports the virtual machine object to VCF Operations. The
VMware adapter applies the same policy to that object, because it is a member of the World object group.
To implement capacity policy settings, you must understand the requirements and tolerances for your environment, such
as CPU use. Then, you can configure your object groups and policies according to your environment.
• For a production environment policy, a good practice is to configure higher performance settings, and to account for
peak use times.
• For a test environment policy, a good practice is to configure higher utilization settings.
VCF Operations applies the policies in the priority order, as they appear in the priority column. When you establish the
priority for your policies, VCF Operations applies the configured settings in the policies according to the policy rank order
to analyze and report on your objects. To change the priority of any active policy:
1. In the Policies page, click the horizontal ellipse, and click Reorder Policies.
Note:  The Reorder Policies option is activated only if there are more than one active policies.
2. In the Reorder Policies window, select the policy and drag it up or down to change the priority.
3. Click ok to save the changes made to the priority.
The priority for the Default Policy is always designated with the letter D, and the other active policies are prioritized with
numbers 1, 2, and so on. Policy with priority 1 indicates the highest priority. When you assign an object to be a member
of multiple object groups, and you assign a different policy to each object group, VCF Operations associates the highest
ranking policy with that object.
Table 969: Configurable Policy Rule Elements
Policy Rule Elements Thresholds, Settings, Definitions
Workload Configure symptom thresholds for Workload.
Time Remaining Configure thresholds for the Time Remaining.
Capacity Remaining Configure thresholds for the Capacity Remaining.
Maintenance Schedule Sets a time to perform maintenance tasks.
Attributes An attribute is a collectible data component. You can activate or deactivate metric, property, and super
metric attributes for collection, and set attributes as key performance indicators (KPIs). A KPI is the
designation of an attribute that indicates that the attribute is important in your own environment.
Alert Definitions Activate or deactivate combinations of symptoms and recommendations to identify a condition that
classifies as a problem.
Symptom Definitions Activate or deactivate test conditions on properties, metrics, or events.
Privileges to Create, Modify, and Prioritize Policies
You must have privileges to access specific features in the VCF Operations user interface. The roles associated with your
user account determine the features you can access and the actions you can perform. To set the policy priority:
1. In the Policy Definition page, click the horizontal ellipse, and click Reorder Policies.
Note:  The Reorder Policies option is activated only if there are more than one active policies.
VMware by Broadcom  3131

---
## page 3132

 VMware Cloud Foundation 9.0
2. In the Reorder Policies window, select the policy and drag it up or down to change the priority.
3. Click ok to save the changes made to the priority.
How Upgrades Affect Your Policies
After you upgrade VCF Operations from a previous version, you might find newly added or updated default settings of
policies such as, new alerts and symptoms. Hence, you must analyze the settings and modify these settings to optimize
them for your current environment. If you apply the policies used with a previous version of VCF Operations, the manually
modified policy settings remain unaltered.
Policy Decisions and Objectives
Implementing policy decisions in VCF Operations is typically the responsibility of the Infrastructure Administrator or the
Virtual Infrastructure Administrator, but users who have privileges can also create and modify policies.
You must be aware of the policies established to analyze and monitor the resources in your IT infrastructure.
• If you are a Network Operations engineer, you must understand how policies affect the data that VCF Operations
reports on objects, and which policies assigned to objects report alerts and issues.
• If you are the person whose role is to recommend an initial setup for policies, you typically edit and configure the
policies in VCF Operations.
• If your primary role is to assess problems that occur in your environment, but you do not have the responsibility to
change the policies, you must still understand how the policies applied to objects affect the data that appears in VCF
Operations. For example, you might need to know which policies apply to objects that are associated with particular
alerts.
• If you are a typical application user who receives reports from VCF Operations, you must have a high-level
understanding of the operational policies so that you can understand the reported data values.
Policies Library
The policies library displays the base settings, default policy, and other best practice policies that VCF Operations
includes. You can use the policies library to create your own policies. The policies library includes all the configurable
settings for the policy elements, such as workload, capacity and time remaining, and so on.
How the Policies Library Works
Use the options in policies library to create your own policy from an existing policy, or to override the settings from an
existing policy so that you can apply the new settings to groups of objects. You can also import or export a policy and
reorder the policies.
Select a policy to display its details in the right pane. The right pane displays a high-level overview of all the details and
options for that policy where these details are categorized in tabs. Expand each category to view all the related details.
When you add or edit a policy, you access the policy workspace where you select the base policies and override the
settings for metrics and properties, alerts and symptoms, capacity, compliance, workload automation, and groups and
objects. In this workspace, you can also apply the policy to objects and object groups. To update the policy associated
with an object or object group, the role assigned to your user account must have the Manage Association permission
activated for policy management.
Where You Manage the Policies Library
To manage the policies library, from the left menu, click Infrastructure Operations > Configurations, and then click the
Policy Definition tile. The policies library appears and lists the policies available to use for your environment.
VMware by Broadcom  3132

---
## page 3133

 VMware Cloud Foundation 9.0
Table 970: Policy Library Tab Options
Option Description
Toolbar Use the toolbar selections to take action in the policies library.
• Add. Create a policy from an existing policy.
• Edit. Customize the policy so that you can override settings for VCF Operations to analyze
and report data about the associated objects.
• Delete. Remove a policy from the list.
• Set Default Policy. You can set any policy to be the default policy, which applies the settings
in that policy to all objects that do not have a policy applied. When you set a policy to be the
default policy, the priority is set to D , which gives that policy the highest priority.
• Export. Downloads the policy.
• Import. Allows you to import policies. To import:
– Click the Import option from the horizontal ellipsis.
– Click Browse and select the file to import.
– Select if you want to Overwrite or Skip the file in case of a conflict.
– Click Import to import the policy, and click Done.
Note:  To import or export a policy, the role assigned to your user account must have the
Import or Export permissions activated for policy management.
• Reorder Policies. Change the priority of the active policies.
Filters Limits the list based on the text you type.
You can also filter by:
• Name
• Description
• Modified By
Policies library data grid VCF Operations displays the high-level details for the policies.
• Name. Name of the policy as it appears in the Add or Edit Policy workspace, and in areas
where the policy applies to objects, such as in Custom Groups.
• Status: Indicates whether the policy is active or inactive.
• Description. Meaningful description of the policy, such as which policy is inherited, and any
specific information users need to understand the relationship of the policy to one or more
groups of objects.
• Last Modified. Date and time that the policy was last modified.
Policies library > Right Pane The right pane displays the name and description of the policy from which the settings are
inherited, the policy priority, and the option to edit the policy. From the right pane, you can view
the complete group of settings that include both customized settings and the settings inherited
from the base policies selected when the policy was created.
• Metrics and Properties: Displays all the attribute types included in the policy. Attribute type
includes, metrics properties, and super metrics.
• Alerts and Symptoms: Displays all the alert and symptom definitions included in the policy.
The Alert Definitions tabs display an overview of the alert definition, criticality, symptom, and
state. The Symptoms Definitions tab displays an overview of the symptom name, criticality,
and the metric name.
• Capacity: Displays an overview of all the thresholds of the objects included in the policy.
• Compliance: Displays the compliance thresholds inherited from the base policy or set while
creating the policy.
• Workload Automation: Displays the details of the workload optimized in your environment per
your definition.
VMware by Broadcom  3133

---
## page 3134

 VMware Cloud Foundation 9.0
Option Description
• Groups and Objects: Displays the object or object groups associated with the selected
policy and the names of the objects in your environment, their object types, and associated
adapters. When a parent group exists for an object, it is shown here.
Operational Policies
Determine how to have VCF Operations monitor your objects, and how to notify you about problems that occur with those
objects.
VCF Operations Administrators assign policies to objects or object groups and applications to support Service Level
Agreements (SLAs) and business priorities. When you use policies with objects or object groups, you ensure that the rules
defined in the policies are quickly put into effect for the objects in your environment.
With policies, you can:
• Activate and deactivate alerts.
• Control data collections by persisting or not persisting metrics on the objects in your environment.
• Configure the product analytics and thresholds.
• Monitor objects and applications at different service levels.
• Prioritize policies so that the most important rules override the defaults.
• Understand the rules that affect the analytics.
• Understand which policies apply to objects or object groups.
VCF Operations includes a library of built-in active policies that are already defined for your use. VCF Operations applies
these policies in priority order.
When you apply a policy to an object or an object group, VCF Operations collects data from the objects based on the
thresholds, metrics, super metrics, attributes, properties, alert definitions, and problem definitions that are activated in the
policy.
The following examples of policies might exist for a typical IT environment.
• Maintenance: Optimized for ongoing monitoring, with no thresholds or alerts.
• Critical Production: Production environment ready, optimized for performance with sensitive alerting.
• Important Production: Production environment ready, optimized for performance with medium alerting.
• Batch Workloads: Optimized to process jobs.
• Test, Staging, and QA: Less critical settings, fewer alerts.
• Development: Less critical settings, no alerts.
• Low Priority: Ensures efficient use of resources.
• Default Policy: Default system settings.
Types of Policies
There are three types of policies such as default policies, custom policies, and policies that are offered with VCF
Operations.
Custom Policies
You can customize the default policy and base policies included with VCF Operations for your own environment. You
can then apply your custom policy to an individual object or groups of objects, such as the objects in a cluster, or virtual
machines and hosts, or to a group that you create to include unique objects and specific criteria.
VMware by Broadcom  3134

---
## page 3135

 VMware Cloud Foundation 9.0
You must be familiar with the policies so that you can understand the data that appears in the user interface, because
policies drive the results that appear in the VCF Operations dashboards, views, and reports.
To determine how to customize operational policies and apply them to your environment, you must plan ahead. For
example:
• Must you track CPU allocation? If you overallocate CPU, what percentage must you apply to your production and test
objects?
• Will you overallocate memory or storage? If you use High Availability, what buffers must you use?
• How do you classify your logically defined workloads, such as production clusters, test or development clusters, and
clusters used for batch workloads? Or, do you include all clusters in a single workload?
• How do you capture peak use times or spikes in system activity? In some cases, you might need to reduce alerts so
that they are meaningful when you apply policies.
When you have privileges applied to your user account through the roles assigned, you can create and modify policies,
and apply them to objects. For example:
• Create a policy from an existing base policy, inherit the base policy settings, then override specific settings to analyze
and monitor your objects.
• Use policies to analyze and monitor vCenter objects and non- vCenter objects.
• Set custom thresholds for capacity settings on all object types to have VCF Operations report on workload, and so on.
• Activate specific attributes for collection, including metrics, properties, and super metrics.
• Activate or deactivate alert definitions and symptom definitions in your custom policy settings.
• Apply the custom policy to an individual object or groups of objects.
When you use an existing policy to create a custom policy, you override the policy settings to meet your own needs.
You set the allocation and demand, the overcommit ratios for CPU and memory, and the thresholds for capacity risk and
buffers. To allocate and configure what your environment is actually using, you use the allocation model and the demand
model together. Depending on the type of environment you monitor, such as a production environment versus a test or
development environment, whether you over allocate at all and by how much depends on the workloads and environment
to which the policy applies. You might be more conservative with the level of allocation in your test environment and less
conservative in your production environment.
When you establish the priority for your policies, VCF Operations applies the configured settings in the policies according
to the policy rank order to analyze and report on your objects. When you assign an object to be a member of multiple
object groups, and you assign a different policy to each object group, VCF Operations associates the highest ranking
policy with that object.
Your policies are unique to your environment. Because policies direct VCF Operations to monitor the objects in your
environment, they are read-only and do not alter the state of your objects. For this reason, you can override the
policy settings to fine-tune them until VCF Operations displays the results that are meaningful and that affect for your
environment. For example, you can adjust the capacity buffer settings in your policy, and then view the data that appears
in the dashboards to see the effect of the policy settings.
Default Policy in VCF Operations
The default policy is a set of rules that applies to most of your objects.
The Default policy is marked with the letter D in the Priority column and can apply to any number of objects.
All the Default policies appear in the Default Policy group in the policies library, even if that policy is not associated with
an object group. When an object group does not have a policy applied, VCF Operations associates the Default policy with
that group.
A policy can inherit the Default policy settings, and those settings can apply to various objects under several conditions.
VMware by Broadcom  3135

---
## page 3136

 VMware Cloud Foundation 9.0
The policy that is set to Default always takes the lowest priority. If you attempt to set two policies as the Default policy, the
first policy that you set to Default is initially set to the lowest priority. When you set the second policy to Default, that policy
then takes the lowest priority, and the earlier policy that you set to Default is set to the second lowest priority.
You can use the Default policy as the base policy to create your own custom policy. You modify the default policy settings
to create a policy that meets your analysis and monitoring needs. When you start with the Default policy, your new policy
inherits all the settings from the Default base policy. You can then customize your new policy and override these settings.
The data adapters and solutions installed in VCF Operations provide a collective group of base settings that apply to all
objects. In the policy navigation tree in the policies library, these settings are called Base Settings. The Default policy
inherits all the base settings by default.
Policies Provided with VCF Operations
VCF Operations includes sets of policies that you can use to monitor your environment, or as the starting point to create
your own policies.
Verify that you are familiar with the policies provided with VCF Operations so that you can use them in your own
environment, and to include settings in new policies that you create.
Where You Find the Policies Provided with VCF Operations Policies
From the left menu, click Infrastructure Operations > Configurations, and then click the Policy Definition tile to see
the policies provided with VCF Operations.
Policies That VCF Operations Includes
All policies exist under the Base Settings, because the data adapters and solutions installed in your VCF Operations
instance provide a collective group of base settings that apply to all objects. In the policies library, these settings are called
Base Settings.
The Base Settings policy is the umbrella policy for all other policies, and appears at the top of the policy list in the policies
library. All the other policies reside under the Base Settings, because the data adapters and solutions installed in your
VCF Operations instance provide a collective group of base settings that apply to all objects.
The configuration based policy set includes policies provided with VCF Operations that you use for specific settings on
objects to report on your objects. This set includes several types of policies:
• Efficiency alerts policies for infrastructure objects and virtual machines
• Health alerts policies for infrastructure objects
• Overcommit policies for CPU and Memory
• Risk alerts policies for infrastructure objects and virtual machines
The Default Policy includes a set of rules that applies to most of your objects.
Using the Policy Workspace to Create and Modify Operational Policies
You can use the workflow in the policy workspace to create local policies quickly, and update the settings in existing
policies. Select a base policy to use as the source for your local policy settings, and modify the thresholds and settings
used for analysis and collection of data from objects or object groups in your environment. A policy that has no local
settings defined inherits the settings from its base policy to apply to the associated objects or object groups.
Verify that objects or object groups exist for VCF Operations to analyze and collect data, and if they do not exist, create
them. See Managing Custom Object Groups in VCF Operations.
VMware by Broadcom  3136

---
## page 3137

 VMware Cloud Foundation 9.0
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Policy Definition tile.
2. Click Add to add a policy or you can select a policy and click Edit Policy to edit an existing policy.
You can add and edit policies and remove certain policies. You can use the Base Settings policy or the Default Policy
as the root policy for the settings in other policies that you create. You can set any policy to be the default policy.
3. In the Create Policies workspace, assign a name to the policy, and enter the description.
Give the policy a meaningful name and description so that all users know the purpose of the policy.
4. From the Inherit From drop-down, select one or more policies to use as a baseline to define the settings for your new
local policy.
You can use any of the policies provided with VCF Operations as a baseline source for your new policy settings.
5. Click Create Policy.
The Create Policies workspace provides the options to customize your policy.
6. Click Metrics and Properties. In this workspace, select the metric, property, or super metric attributes to include in
your policy.
VCF Operations collects data from the objects in your environment based on the metric, property, or super metric
attributes that you include in the policy.
a) Click Save and return to the create policies workspace.
7. Click Alerts and Symptoms. In this workspace, select the alert definitions and symptom definitions, and activate or
deactivate them as required for your policy.
VCF Operations identifies problems on objects in your environment and triggers alerts when conditions occur that
qualify as problems.
a) Click Save and return to the create policies workspace.
8. Click Capacity. In this workspace, select and override the situational settings such as committed projects to calculate
capacity, time remaining, and other detailed settings.
a) Click Save and return to the create policies workspace.
9. Click Compliance. In this workspace, set the compliance threshold required for your policy.
a) Click Save and return to the create policies workspace.
10. Click Workload Automation. In this workspace, select the optimization settings required for your policy.
Click the lock icon to unlock and configure the workload automation options specific for your policy. When you click the
lock icon to lock the option, your policy inherits the parent policy settings.
a) Click Save and return to the create policies workspace.
11. Click Groups and Objects. In this workspace, select one or more groups and objects to which the policy applies.
VCF Operations monitors the objects according to the settings in the policy that is applied to the object or the object
group, triggers alerts when thresholds are violated, and reports the results in the dashboards, views, and reports.
If you do not assign a policy to one or more objects or object groups, VCF Operations does not assign the settings
in that policy to any objects, and the policy is not active. For an object or an object group that dos not have a policy
assigned, VCF Operations associates the object group with the Default Policy.
Filter the object types, and modify the settings for those object types so that VCF Operations collects and displays the
data that you expect in the dashboards and views.
a) Click Save and return to the create policies workspace.
After VCF Operations analyzes and collects data from the objects in your environment, review the data in the dashboards
and views. If the data is not what you expected, edit your local policy to customize and override the settings until the
dashboards display the data that you need.
VMware by Broadcom  3137

---
## page 3138

 VMware Cloud Foundation 9.0
Policy Workspace in VCF Operations
The policy workspace allows you to quickly create and modify policies. To create a policy, you can inherit the settings from
an existing policy, and you can modify the settings in existing policies if you have adequate permissions. After you create
a policy, or edit an existing policy, you can apply the policy to one or more objects or object groups.
How the Policy Workspace Works
Every policy includes a set of packages, and uses the defined problems, symptoms, metrics, and properties in those
packages to apply to specific objects or object groups in your environment. You can view the details for the settings
inherited from the base policy, and display specific settings for certain object types. You can override the settings of other
policies, and include additional policy settings to apply to the object types.
Use the Add and Edit options to create policies and edit existing policies.
Where You Create and Modify a Policy
To create and modify policies, from the left menu, click Infrastructure Operations > Configurations, and then click the
Policy Definition tile. Click Add to add a policy or select the required policy, and then in the right pane, click Edit Policy
to edit the policy. The policy workspace is where you select the base policies, and customize and override the settings
for analysis, metrics, properties, alert definitions, and symptom definitions. In this workspace, you can apply the policy to
objects or object groups.
To remove a policy from the list, select the policy, click the horizontal ellipse, and select Delete.
Policy Workspace Options
The policy workspace includes a step-by-step workflow to create and edit a policy, and apply the policy to custom object
groups.
 Getting Started Details
When you create a policy, you must give the policy a meaningful name and description so that users know the purpose of
the policy.
Where You Assign the Policy Name and Description
To add a name and description to a policy, from the left menu, click Infrastructure Operations > Configurations, and
then click the Policy Definition tile. Click Add to add a policy or select the required policy, and then in the right pane, click
Edit Policy to edit a policy. The name and description appear in the Create or Edit policy workspace.
Table 971: Name and Description Options in the Create or Edit Policy Workspace
Option Description
Name Name of the policy as it appears in the Create or Edit Policy screens, and in areas where the
policy applies to objects, such as Custom Groups.
Description Meaningful description of the policy. For example, use the description to indicate which policy is
inherited, and any specific information that users must understand the relationship of the policy to
one or more groups of objects.
Inherit From The base policy that is used as a starting point. All settings from the base policy will be inherited
as default settings in your new policy. You can override these settings to customize the new
policy.
Select a base policy to inherit the policy settings as a starting point for your new policy.
VMware by Broadcom  3138

---
## page 3139

 VMware Cloud Foundation 9.0
Select the Inherited Policy Details
You can use any of the policies provided with VCF Operations as a baseline source for your policy settings when you
create a policy.
In the policy content area, you can perform the following actions:
• View the packages and elements for the inherited policy and additional policies that you selected to override the
settings.
• Compare the differences in settings highlighted between these policies.
• Display object types.
To create a policy, select a base policy to inherit your new custom policy inherits settings. To override some of the settings
in the base policy according to the requirements for the service level agreement for your environment, you can select and
apply a separate policy for a management pack solution. The override policy includes specific settings defined for the
types of objects to override, either manually or that an adapter provides when it is integrated with VCF Operations. The
settings in the override policy overwrite the settings in the base policy that you selected.
When you select and apply a policy to use to overwrite the settings that your policy inherits from the base policy, the policy
that you select appears in the policy settings cards.
Click each card to display the inherited policy configuration, and your policy, and displays a preview of the selected policy
settings. When you select one of the policy cards, you can view the number of activated and deactivated alert definitions,
symptom definitions, metrics and properties, and the number of activated and deactivated changes.
When you select the Groups and Objects card, you select the objects to view so that you can see which policy elements
apply to the object type. For example, when you select the StorageArray object type, the workspace displays the local
packages for the policy and the object group types with the number of policy elements in each group.
You can preview the policy settings for all object types, only the object types that have settings changed locally, or settings
for new object types that you add to the list, such as Storage Array storage devices.
Where You Select and Override Base Policies Settings
To select a base policy to use as a starting point for your own policy, and to select a policy to override one or more
settings that your policy inherits from the base policy, from the left menu, click Operations > Configurations, and then
click the Policy Definition tile. Click Add to add a policy. In the Create policies workspace, add a name and description
for the policy and from the Inherit From drop-down, select the base policy. The policy configuration, objects, and preview
appear in cards below this drop-down.
Capacity Details
You can filter the object types, and modify the settings for those object types so that VCF Operations applies these
settings. The data that you expect then appears in the dashboards and views.
How the Capacity Workspace Works
When you turn on and configure the Capacity settings for a policy, you can override the settings for the policy elements
that VCF Operations uses to trigger alerts and display data. These types of settings include symptom thresholds based
on alerts, situational settings such as committed projects to calculate capacity and time remaining, and other detailed
settings.
Policies focus on objects and object groups. When you configure policy settings for your local policy, you must consider
the object type and the results that you expect to see in the dashboards and views. If you do not change these settings,
your local policy retains the settings that your policy inherited from the base policy that you selected.
VMware by Broadcom  3139

---
## page 3140

 VMware Cloud Foundation 9.0
Where You Set the Policy Capacity Settings
To set the capacity settings for your policy, from the left menu, click Infrastructure Operations > Configurations, and
then click the Policy Definition tile. Click Add to add a policy or select the required policy.
In the right pane, click Edit Policy to edit a policy. In the <policy name> [Edit] workspace, click the Capacity card. The
capacity settings for host systems, virtual machines, and other object types that you select appears in the workspace.
You can also edit the capacity settings while working on the objects under the Inventory > Capacity tab. In the Capacity
tab under Inventory, click the Foundation Policy drop-down and select Edit Capacity Setting.
Table 972: Capacity Settings in the Create or Edit Policy Workspace
Option Description
Risk Level Configurations You can set the risk level for the time that is remaining when the forecasted total need of a metric
reaches usable capacity. Click the lock icon to override the settings and change the thresholds
for your policy.
The following are the risk level settings. Use the slider below the graphical display to change the
risk level. You can move the slider between Aggressive and Conservative.
• Conservative. Use this option for production and mission-critical workloads.
• Aggressive. Use this option for non-critical workloads.
• Peak focused. Selecting peak focused tells the capacity engine to create projections using
the peaks that have been identified in the historical demand. Use this option to include the
upper range of the data. The projection will be based on the high utilization points. Select the
Peak focused checkbox for VMs with utilization spikes.
Business Hours Schedule Configure business hours as per your time zone, for calculation of capacity analysis and
projections. VCF Operations considers the business hours for all objects using the current policy.
During non-business hours, VMs could be running other data center activities such as OS
upgrades, virus scans, etc after working hours, and hence may not appear to be idle. When you
mark business hours schedules, VCF Operations can analyze after hours metrics for inventory,
compliance, troubleshooting and other purposes. The reclamation and right sizing analysis and
recommendations are based on the business hours and ignore spikes after business hours.
Since the business hours schedule are based on policies, different objects can have different
business hours. The capacity charts will be based on business hours.
Note:  You can set business hours schedule for VMs and clusters only.
Note:  After you specify business hours, the capacity forecast for the object will be based on the
business hours and not 24 hours.
Click the lock icon on the left of each element to override the settings and change the thresholds
for your policy.
Filters Select the object type by which you want to filter. You can filter by Object Types, Local Changes,
and Unsaved Changes.
Capacity Settings Select an object to view the policy elements and settings for the object type so that you can have
VCF Operations analyze the object type.
You can view and modify the settings for the following policy elements:
• Storage consideration for capacity calculation.
Note:
This option is only available for the Cluster Compute Resource.
• Allocation Model
• Custom Profile
• Capacity Buffer
Click the lock icon on the left of each element to override the settings and change the thresholds
for your policy.
VMware by Broadcom  3140

---
## page 3141

 VMware Cloud Foundation 9.0
Option Description
Criticality Thresholds and Metrics There are two tabs in this settings.
Click the lock icon on the left of each element to override the settings and change the thresholds
for your policy.
Criticality Thresholds Tab You can view and modify the threshold settings
for the following policy elements:
• Time Remaining
• Capacity Remaining
• Workload
Custom Metrics Tab In the custom metrics tab, you can configure
VCF Operations to use custom metrics in all
the capacity calculations. The metrics that
you configure in this tab replaces the default
metrics that the VCF Operations capacity
engine uses. When defining the custom
metrics, you can select the metrics shipped
with VCF Operations, or select super metrics.
Only metrics which have the same unit as the
internal metric used by the capacity engine, or
a metric which has no unit, are displayed.
Note:  Enabling custom metrics in the capacity
calculations is an advanced configuration.
Custom metrics alter the way VCF Operations
calculates capacity across your environment.
Use this setting only when needed.
You can view and modify the custom metrics
settings for all non-allocation capacity models.
For example, for a data center, you can set
custom metrics settings for Total Capacity and
Utilization for Memory, CPU and Demand.
When you click the Edit icon beside the total
Capacity and Utililization settings, a list of
available metrics opens in the right pane.
Double click a default metric or super metric
from the list to select it. Click RESET TO
DEFAULT to revert your changes. Changes
that you make take effect after the next
collection cycle.
Click Save to save the changes.
The local changes made will appear under Policy Definition > Default Policy > Capacity section. You can also view the
preview of changes in the Capacity card.
 Policy Workload Element
Workload is a measurement of the demand for resources on an object. You can turn on and configure the settings for the
Workload element for the object types in your policy.
VMware by Broadcom  3141

---
## page 3142

 VMware Cloud Foundation 9.0
How the Workload Element Works
The Workload element determines how VCF Operations reports on the resources that the selected object group uses. The
resources available to the object group depend on the amount of configured and usable resources.
• A specific amount of physical memory is a configured resource for a host system, and a specific number of CPUs is a
configured resource for a virtual machine.
• The usable resource for an object or an object group is a subset of, or equal to, the configured amount.
• The configured and usable amount of a resource can vary depending on the type of resource and the amount of
virtualization overhead required, such as the memory that an ESX host machine requires to run the host system.
When accounting for overhead, the resources required for overhead are not considered to be usable, because of the
reservations required for virtual machines or for the high availability buffer.
Where You Override the Policy Workload Element
To view and override the policy workload capacity setting, from the left menu, click Infrastructure Operations >
Configurations, and then click the Policy Definition tile. Click Add to add a policy or select the required policy. In the
right pane, click Edit Policy to edit a policy. In the <policy name> [Edit] workspace, click the Capacity card. The workload
settings for the object type that you have selected appear in the workspace.
View the Workload policy element, and configure the settings for your policy.
If you do not configure the policy element, your policy inherits the settings from the selected base policy.
Table 973: Policy Workload Element Settings in the Create or Edit Policies Workspace
Option Description
Lock icon Allows you to override the policy element settings so that you can customize the policy to monitor
the objects in your environment.
Workload Allows you to set the number of collection cycles it takes to trigger or clear an alert.
Policy Time Remaining Element
The Time remaining element is a measure of the amount of time left before your objects run out of capacity.
How the Time Remaining Element Works
The Time Remaining element determines how VCF Operations reports on the available time until capacity runs out for a
specific object type group.
• The time remaining indicates the amount of time that remains before the object group consumes the capacity
available. VCF Operations calculates the time remaining as the number of days remaining until all the capacity is
consumed.
• To keep the Time Remaining more than the critical threshold setting or to keep it green, your objects must have more
days of capacity available.
Where You Override the Policy Time Remaining Element
To view and override the policy Time Remaining capacity setting, from the left menu, click Infrastructure Operations >
Configurations, and then click the Policy Definition tile. Click Add to add a policy or select the required policy. In the
right pane, click Edit Policy to edit a policy. In the <policy name> [Edit] workspace, click the Capacity card. The time
remaining settings for the object type that you have selected appear in the workspace.
View the Time Remaining policy element and configure the settings for your policy.
If you do not configure the policy element, your policy inherits the settings from the selected base policy.
VMware by Broadcom  3142

---
## page 3143

 VMware Cloud Foundation 9.0
Table 974: Policy Time Remaining Element Settings in the Create or Edit Policies Workspace
Option Description
Lock icon Allows you to override the policy element settings so that you can customize the policy to monitor
the objects in your environment.
Time Remaining Allows you to set the number of days until capacity is projected to run out based on your current
consumption trend.
Policy Capacity Remaining Element
Capacity is a measurement of the amount of memory, CPU, and disk space for an object. You can turn on and configure
the settings for the Capacity Remaining element for the object types in your policy.
How the Capacity Remaining Element Works
The Capacity Remaining element determines how reports on the available capacity until resources run out for a specific
object type group.
• The capacity remaining indicates the capability of your environment to accommodate workload.
• Usable capacity is a measurement of the percentage of capacity available, minus the capacity affected when you use
high availability.
Where You Override the Policy Capacity Remaining Element
To view and override the policy Capacity Remaining analysis setting, from the left menu, click Infrastructure
Operations > Configurations, and then click the Policy Definition tile. Click Add to add a policy or select the required
policy. In the right pane, click Edit Policy to edit a policy. In the <policy name> [Edit] workspace, click the Capacity card.
The capacity remaining settings for the object type that you have selected appears in the workspace.
View the Capacity Remaining policy element and configure the settings for your policy.
If you do not configure the policy element, your policy inherits the settings from the selected base policy.
Table 975: Policy Capacity Remaining Element Settings in the Create or Edit Policies Workspace
Option Description
Lock icon Allows you to override the policy element settings so that you can customize the policy to monitor
the objects in your environment.
Capacity Remaining Allows you to set the percentage at which the capacity remaining alerts must be triggered.
 Policy Allocation Model Element
Allocation model defines how much CPU, memory, or disk space is allocated to objects in a datastore, cluster or datastore
cluster. In the policy, you can turn on the Allocation Model element and configure the resource allocation for the objects.
How the Allocation Model Element Works
The Allocation Model element determines how calculates capacity when you allocate a specific amount of CPU, memory,
and disk space resource to datastores, clusters or datastore clusters. You can specify the allocation ratio for either
one, or all of the resource containers of the cluster. Unlike the demand model, the allocation model is used for capacity
calculations only when you turn it on in the policy.
The allocation model element also affects the reclaimable resources for memory and storage in Reclaim page. When
you turn on the Allocation Model element in the policy, the tabular representation of the VMs and snapshots in the
VMware by Broadcom  3143

---
## page 3144

 VMware Cloud Foundation 9.0
selected data center from which resources can be reclaimed displays reclaimable memory and disk space based on the
overcommit values.
Where You Override the Allocation Model Element
To view and override the policy workload analysis setting, from the left menu, click Infrastructure Operations >
Configurations, and then click the Policy Definition tile.
Click Add to add a policy or select the required policy, and then in the right pane, click Edit Policy to edit a policy. In the
<policy name> [Edit] workspace, click the Capacity card.
The allocation model settings for the object type that you selected appear in the workspace.
Click the unlock icon next to Allocation Model to set the overcommit ratios.
Option Description
Set overcommit ratio, to enable Allocation Model Allows you to set the overcommit ratio for CPU, memory, or disk
space. Select the check box next to the resource container you
want to edit and change the overcommit ratio value.
Policy Custom Profile Element
The custom profile element lets you apply a custom profile which shows how many more of a specified object can fit in
your environment depending on the available capacity and object configuration.
Where You Define the Custom Profiles
To define a custom profile, from the left menu click Infrastructure Operations > Configurations, and then click the
Custom Profiles tile under Miscellaneous. Click Add to define a new custom profile.
Where You Select the Custom Profile Element
To view and override the policy Custom Profile analysis setting, from the left menu click Infrastructure Operations >
Configurations, and then click the Policy Definition tile. Click Add to add a policy or select the required policy. In the
right pane, click Edit Policy to edit a policy. In the <policy name> [Edit] workspace, click the Capacity card. The custom
profile element for the object types such as datastores, clusters and datastore clusters that you selected appear in the
workspace. Click the lock icon to unlock the section and make changes.
Policy Capacity Buffer Element
The capacity buffer element lets you add buffer for capacity and cost calculation. For vCenter objects, you can add buffer
to CPU, Memory, and Disk Space for the Demand and Allocation models. You can add capacity buffer to datastores,
clusters and datastore clusters. The values that you define here affect the cluster cost calculation. The time remaining,
capacity remaining, and recommended values are calculated based on the buffer. For WLP, capacity buffer is first
considered and then the headroom that you have defined is considered.
Where You Define the Capacity Buffer
To view and override the policy Capacity Buffer analysis setting, from the left menu click Infrastructure Operations >
Configurations, and then click the Policy Definition tile. Click Add to add a policy or select the required policy. In the
right pane, click Edit Policy to edit a policy. In the <policy name> [Edit] workspace, click the Capacity card. The Capacity
Buffer for the object type that you selected appears in the workspace. Click the lock icon to unlock the section and make
changes.
How the Capacity Buffer Element Works
VMware by Broadcom  3144

---
## page 3145

 VMware Cloud Foundation 9.0
The Capacity Buffer element determines how much extra headroom you have and ensures that you have extra space for
growth inside the cluster when required. The value of the usable capacity reduces by the buffer amount that you specify
here. The default buffer value is zero. If you are upgrading from a previous version of VCF Operations, the buffer values
are carried forward to the new version.
The capacity buffer value that you specify for the Allocation model is considered only if you have activated allocation
model in the policy.
Starting from version 8.6, capacity buffer is depreciated from cluster compute resources. The overcommit ratio setting
(from the allocation model) and buffer settings, if set for the datastore object, takes precedence for the disk space related
to datastore cluster and cluster objects. If these settings are not set, then, from a cost calculation perspective, the settings
of datastore cluster and cluster (if the settings are missing for the datastore cluster as well), are used. The allocation and
buffer settings made on the cluster does not impact the underlying datastores (as they do not inherit these settings), and
the same works vice-versa, settings made for datastores are not propagated to the cluster.
The following tables display the capacity buffer that you can define based on the vCenter Adapter object types:
Object Type Valid Models for Capacity Buffer
CPU Demand
Allocation
Memory Demand
Allocation
Disk Space Demand
Allocation
Maintenance Schedule Details
You can set a time to perform maintenance tasks for each policy.
Where You Override the Policy Maintenance Schedule Element
To view and override the policy Maintenance Schedule analysis setting, from the left menu, click Infrastructure
Operations > Configurations, and then click the Policy Definition tile. Click Add to add a policy or select the required
policy. In the right pane, click Edit Policy to edit a policy. In the Create or Edit policies workspace, click Maintenance
Schedule.
If you do not configure the policy element, your policy inherits the settings from the selected base policy.
Table 976: Policy Maintenance Schedule Element Settings in the Create or Edit Policies Workspace
Option Description
Select Object Type Select the object type by which you want to filter.
Filters You can filter by Local Changes and Unsaved Changes. Select Yes or No from the drop-down
and click Apply to apply the filters.
Lock icon Allows you to override the policy element settings so that you can customize the policy to monitor
the objects in your environment.
Maintenance Schedule Sets a time to perform maintenance tasks. During maintenance, VCF Operations does not
calculate analytics.
VMware by Broadcom  3145

---
## page 3146

 VMware Cloud Foundation 9.0
Compliance Details
Compliance is a measurement that ensures that the objects in your environment meet industrial, governmental, regulatory,
or internal standards. You can unlock and configure the settings for the compliance for the object types in your policy.
Where You Override the Policy Compliance
To view and override the policy compliance setting, from the left menu click Infrastructure Operations > Configurations,
and then click the Policy Definition tile. Click Add to add a policy or select the required policy. In the right pane, click Edit
Policy to edit a policy. In the Create or Edit policy workspace, click Compliance
View the compliance thresholds and configure the settings for your policy.
If you do not configure the policy element, your policy inherits the settings from the selected base policy.
Table 977: Compliance Settings in the Create or Edit Policies Workspace
Option Description
Lock icon Allows you to override the policy element settings so that you can customize the policy to monitor
the objects in your environment.
Compliance Allows you to set the compliance score threshold based on the number of violations against
those standards.
 Workload Automation Details
You can set the workload automation options for your policy, so that VCF Operations can optimize the workload in your
environment as per your definition.
How the Workload Automation Workspace Works
You click the lock icon to unlock and configure the workload automation options specific for your policy. When you click the
lock icon to lock the option, your policy inherits the parent policy settings.
Where You Set the Policy Workload Automation
Access this screen through the Policies pages:
1. Click Infrastructure Operations > Configurations, and then click the Policy Definition tile.
2. Select a policy that you want to modify. Ideally, this should be an active policy. Or, click the ADD button to add a new
policy.
3. Select the Workload Automation card to review the changes, or click EDIT POLICY to make changes.
Table 978: Workload Automation in the Create or Edit Policies Workspace
Option Description
Workload Optimization Select a goal for workload optimization.
Select Balance when workload performance is your first goal. This approach proactively moves
workloads so that the resource utilization is balanced, leading to maximum headroom for all
resources.
Select Moderate when you want to minimize the workload contention.
VMware by Broadcom  3146

---
## page 3147

 VMware Cloud Foundation 9.0
Option Description
Select Consolidate to proactively minimize the number of clusters used by workloads. You might
be able to repurpose resources that are freed up. This approach is good for cost optimization,
while making sure that performance goals are met. This approach might reduce licensing and
power costs.
Cluster Headroom Headroom establishes a required capacity buffer, for example, 20 percent. It provides you
with an extra level of control and ensures that you have extra space for growth inside the
cluster when required. Defining a large headroom setting limits the systems opportunities for
optimization.
Note:  vSphere HA overhead is already included in useable capacity and this setting does not
impact the HA overhead.
Change Datastore Click the lock icon to select one of the following options:
• Do not allow Storage vMotion.
• Allow Storage vMotion. This is selected by default.
Using this option, you can select what type of virtual machines VCF Operations moves first to
address workload.
Target Network Policy Setting for
WLP
Click the lock icon to select the following option:
• Generate a Target Network mapping
When you select this checkbox, the Workload Placement algorithm in will automatically choose
compatible target network, while making the decision to move the VM for the optimization. For
choosing compatible network WLP engine will consider the segment path and logical switch
UUID of the Distributed Port Group.
Workload Optimization Across networks is supported when the optimization candidate clusters
are assigned with different port groups (configured with NSX). These port groups configured via
NSX have same segmentID and Logical Switch UUID. To enable this ability, check the respective
setting in Workload Automation policy settings.
Note:  Segment ID and logical switch UUID properties are published on the VC port groups by
NSX. So Worload Placement cannot provide a target network if it is not a NSX configuration and
those properties are missing.
This setting is not selected by default.
Configuring vCenter Pricing Details
You can add and assign new pricing cards to vCenter and Clusters in VCF Operations. The pricing card can be cost-
based or rate-based, you can customize the cost-based pricing card and rate-based pricing card as per your requirement.
After configuring the pricing card, you can assign it to one more vCenter or Clusters based on your pricing strategy.
If you want to copy the vCenter pricing settings from the policy currently being edited to another policy, click Copy local
changes to other policy and select the policy to which you want to copy the settings. The copied pricing configuration
will override any existing local pricing configuration, in the target policy.
VMware by Broadcom  3147

---
## page 3148

 VMware Cloud Foundation 9.0
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Policy Definition tile.
2. Select the required policy or click Add to add a new policy.
3. In the right pane, click Edit Policy.
4. In the <policy name> [Edit] workspace, click the VC Pricing card.
5. Click the Lock icon to override parent policy settings.
6. Select if you want to activate or deactivate the pricing engine.
7. Configure Basic Charges: Click the Lock icon to edit the parent policy settings. Pricing can be performed either on a
cost basis or independent of it by specifying rate cards. The factor entered here is multiplied by the cost calculated as
a derivative of cost drivers.
1. Based on Cost/Based on Rate: Select if you want to pricing card to be cost-based or rate-based.
The following options appear if you select the Based on Cost option:
• CPU Cost: Enter a valid CPU cost factor.
• Memory Cost: Enter a valid memory cost factor.
• Storage Cost: Enter a valid storage cost factor.
• Additional Cost: Enter a valid additional cost factor.
The following options appear if you select the Based on Rate option:
• CPU Rate: Enter the CPU Rate per vCPU, the charging period, and how to charge for the resources.
• Memory Rate: Enter the memory rate per GB, the charging period, and how to charge for the resources.
• Storage Rate: Enter the storage rate per GB, the charging period, and how to charge for the resources.
8. Configure Guest OS Rate: Click Guest OS Rate in the left pane and then click the Lock icon to edit the parent policy
settings. These are additional charges that have to be included based on the operating system running on the virtual
machine. The name of the operating system should match exactly as discovered by VMware Tools.
1. Click Create Guest OS Rate and enter the following details:
– Guest OS Name: Enter a guest OS name.
– Charge Period: The Charge Period indicates the frequency of charging.
– Base Rate: Enter a base rate.
The guest OS rates that you add appear in the table below. To edit or delete the entries, click the vertical ellipses
and select the desired option.
VMware by Broadcom  3148

---
## page 3149

 VMware Cloud Foundation 9.0
9. Tags: Click Tags in the left pane and then click the Lock icon to edit the parent policy settings. Tag-based charges
can be used to charge for value-added services such as antivirus database disaster recovery and other applications.
These applications are to be represented as vCenter tags on the VMs for these charges to work.
1. Recurring Charges: Recurring charges represent repeating charges such as monthly license fees for antivirus
software. Click Add Recurring Tag and enter the following details:
– Tag Category: Enter a tag key.
– Tag Value: Enter a tag value.
– Base Rate: Enter a base rate.
– Charge Period: The Charge Period indicates the frequency of charging.
– Charge Based on Power State: This decides whether the charge should be applied based on the power state of
the VM.
The tags that you add appear in the table below. To edit or delete the entries, click the vertical ellipses and select
the desired option.
2. One Time Tag: Tag-based one-time charges can be used to represent incidental charges such as charges for
addressing a support ticket or charges for applying an operating systems patch. Click Add One Time Tag and
enter the following details:
– Tag Category: Enter a tag key.
– Tag Value: Enter a tag value.
– Base Rate: Enter a base rate.
The tags that you add appear in the table below. To edit or delete the entries, click the vertical ellipses and select
the desired option.
3. Rate Factor Tag: Rate factors are multiplication factors applied to already calculated charges. For example, to
add a 50% premium on storage, set a rate factor of 1.5 to storage charge. Click Rate Factor Tag and enter the
following details:
– Tag Category: Enter a tag key.
– Tag Value: Enter a tag value.
– Charge Applies To: Select what the charge applies to.
– Rate Factor: Enter a valid number. For example, if you want to increase the price of CPU which has a tag 'Tag1-
Value1' by 20% then select CPU Charge from the Charge Applies To drop-down list and enter 1.2 in Rate
Factor.
The tags that you add appear in the table below. To edit or delete the entries, click the vertical ellipses and select
the desired option.
10. Configure Overall Charges: Click Overall Charges in the left pane and then click the Lock icon to edit the parent
policy settings. Overall Charges are flat charges that are applied to VMs that match this policy.
1. VM Setup Charges: Enter a valid setup fee. This is to charge for the setup of the VMs.
2. Recurring Charges: Enter a valid number.
3. Charge Period: The Charge Period indicates the frequency of charging.
You can assign policies to the required Organization/Organization VDC under Infrastructure Operations > 
Configurations, and then click the Policy Assignment tile. For details, see Assigning Policies.
Metrics and Properties Details
You can select the attribute type to include in your policy so that VCF Operations can collect data from the objects in your
environment. Attribute types include metrics, properties, and super metrics. You activate or deactivate each metric, and
determine whether to inherit the metrics from base policies that you selected in the workspace.
VMware by Broadcom  3149

---
## page 3150

 VMware Cloud Foundation 9.0
How the Collect Metrics and Properties Workspace Works
When you create or customize a policy, you can override the base policy settings to have VCF Operations collect the data
that you intend to use to generate alerts, and report the results in the dashboards.
To define the metric and super metric symptoms, metric event symptoms, and property symptoms, from the left menu click
Infrastructure Operations > Configurations, and then click the Symptom Definitions tile.
Where You Override the Policy Attributes
To override the attributes and properties settings for your policy, from the left menu click Infrastructure Operations >
Configurations, and then click the Policy Definition tile. Click Add to add a policy or select the required policy. In the
right pane, click Edit Policy to edit a policy. In the Create or Edit policy workspace, click Metrics and Properties. The
attributes and properties settings for the selected object types appear in the workspace.
You can also edit the metrics and properties while working on the objects under the Inventory > Metrics tab. In the
Metrics tab under Inventory, click the Foundation Policy drop-down and select Edit Metrics Collection.
Table 979: Metrics and Properties Options
Option Description
Actions Select one or more attributes and select activate, deactivate, or inherit to change the state and KPI for this
policy.
Filter options Deselect the options in the Attribute Type, State, KPI, and DT drop-down menus, to narrow the list of
attributes.
•
  Activated. Indicates that an attribute will be calculated.
•
  Activated (Force). Indicates state change due to a dependency.
•
  Deactivated. Indicates that an attribute will not be calculated.
•
  Inherited. Indicates that the state of this attribute is inherited from the base policy and will be
calculated.
•
  Inherited. Indicates that the state of this attribute is inherited from the base policy and will not be
calculated.
The KPI determines whether the metric, property, or super metric attribute is considered to be a key
performance indicator (KPI) when VCF Operations reports the collected data in the dashboards. Filter the
KPI states to display attributes with KPI activated, deactivated, or inherited for the policy.
Object Type Filters the attributes list by object type.
Page Size The number of attributes to list per page.
Attributes data grid Display the attributes for a specific object type.
• Name. Identifies the name of the metric or property for the selected object type.
• Type. Distinguishes the type of attribute to be either a metric, property, or super metric.
• Adapter Type. Identifies the adapter used based on the object type selected, such as Storage Devices.
• Object Type. Identifies the type of object in your environment, such as StorageArray.
• State. Indicates whether the metric, property, or super metric is inherited from the base policy.
• KPI. Indicates whether the key performance indicator is inherited from the base policy. If a violation
against a KPI occurs, VCF Operations generates an alert.
• DT. Indicates whether the dynamic threshold (DT) is inherited from the base policy.
VMware by Broadcom  3150

---
## page 3151

 VMware Cloud Foundation 9.0
 Alert and Symptom Details
You can activate or deactivate alert and symptom definitions to have VCF Operations identify problems on objects in your
environment and trigger alerts when conditions occur that qualify as problems. You can automate alerts.
How the Alert and Symptom Definitions Workspace Works
VCF Operations collects data for objects and compares the collected data to the alert definitions and symptom definitions
defined for that object type. Alert definitions include associated symptom definitions, which identify conditions on
attributes, properties, metrics, and events.
You can configure your local policy to inherit alert definitions from the base policies that you select, or you can override the
alert definitions and symptom definitions for your local policy.
Before you add or override the alert definitions and symptom definitions for a policy, familiarize yourself on the available
alerts and symptoms.
• To view the available alert definitions, from the left menu, click Infrastructure Operations > Configurations, and then
click the Alert Definitions tile.
• To view the available symptom definitions, from the left menu, click Infrastructure Operations > Configurations, and
then click the Symptom Definitions tile. Symptom definitions are available for metrics, properties, messages, faults,
smart early warnings, and external events.
A summary of the number of problem and symptoms that are activated and deactivated, and the difference in changes
of the problem and symptoms as compared to the base policy, appear in the Analysis Settings pane of the policies
workspace.
Where You Override the Alert Definitions and Symptom Definitions
To override the alert definitions and symptom definitions for your policy, from the left menu click Infrastructure
Operations > Configurations, and then click the Policy Definition tile. Click Add to add a policy or select the required
policy. In the right pane, click Edit Policy to edit a policy. In the Create or Edit policies workspace, click Alerts and
Symptoms. The definitions appear in the workspace.
Policy Alert Definitions and Symptom Definitions
You can override the alert definitions and symptom definitions for each policy.
Policy Alert Definitions
Each policy includes alert definitions. Each alert uses a combination of symptoms and recommendations to identify a
condition that classifies as a problem, such as failures or high stress. You can activate or deactivate the alert definitions in
your policy, and you can set actions to be automated when an alert triggers.
How the Policy Alert Definitions Work
VCF Operations uses problems to trigger alerts. A problem manifests when a set of symptoms exists for an object, and
requires you to take action on the problem. Alerts indicate problems in your environment. VCF Operations generates
alerts when the collected data for an object is compared to alert definitions for that object type and the defined symptoms
are true. When an alert occurs, VCF Operations presents the triggering symptoms for you to take action.
Some of the alert definitions include predefined symptoms. When you include symptoms in an alert definition, and activate
the alert, an alert is generated when the symptoms are true.
The Alert Definitions pane displays the name of the alert, the number of symptoms defined, the adapter, object types
such as host or cluster, and whether the alert is activated as indicated by Local, deactivated as indicated by not Local, or
inherited. Alerts are inherited with a green checkmark by default, which means that they are activated.
VMware by Broadcom  3151

---
## page 3152

 VMware Cloud Foundation 9.0
You can automate an alert definition in a policy when the highest priority recommendation for the alert has an associated
action.
To view a specific set of alerts, you can select the badge type, criticality type, and the state of the alert to filter the view.
For example, you can set the policy to send fault alerts for virtual machines.
Where You Modify the Policy Alert Definitions
To modify the alerts associated with policies, from the left menu click Infrastructure Operations > Configurations, and
then click the Policy Definition tile. Click Add to add a policy or select the required policy. In the right pane, click Edit
Policy to edit a policy. In the Create or Edit policies workspace, click Alerts and Symptoms. The alert definitions and
symptom definitions for the selected object types appear in the workspace.
Table 980: Alert Definitions in the Create or Edit Policies Workspace
Option Description
Object Type Filters the alert definitions list by object type.
Filters Limits the list based on the text you type.
You can also filter by:
• Name
• Criticality
• Impact
• State
• Automate
• Local Changes
• Unsaved Changes
Impact indicates the health, risk, and efficiency badges to which the alerts apply.
Criticality indicates the information, critical, immediate, warning, or automatic criticality types to
which the alert definition applies.
Automate indicates the actions that are activated for automation when an alert triggers, or
actions that are deactivated or inherited. Actions that are activated for automation might appear
as inherited with a green checkmark, because policies can inherit settings from each other. For
example, if the Automate setting in the base policy is set to Local with a green checkmark, other
policies that inherit this setting will display the setting as inherited with a green checkmark.?
Actions Select one or more alert definitions and select activate, deactivate, or inherit to change the state
for this policy.
Page Size The number of alert definitions to list per page.
Alert Definitions data grid Displays information about the alert definitions for the object types. The full name for Alert
definition and the criticality icon appear in a tooltip when you hover the mouse over the Alert
Definition name.
• Alert Definition. Meaningful name for the alert definition.
• State. Alert definition state, either activated, deactivated, or inherited from the base policy.
• Automate. When the action is set to Local, the action is activated for automation when an
alert triggers. Actions that are activated for automation might appear as inherited with a
green checkmark, because policies can inherit settings from each other. For example, if the
Automate setting in the base policy is set to Local with a green checkmark, other policies that
inherit this setting will display the setting as inherited with a green checkmark.?
• Symptom. Number of symptoms defined for the alert.
• Criticality. Indicates the criticality of the alert.
• Actionable Recommendations. Only recommendations with actions in the first priority, as they
are the only ones you can automate.
• Adapter. Data source type for which the alert is defined.
VMware by Broadcom  3152

---
## page 3153

 VMware Cloud Foundation 9.0
Option Description
• Object Type. Type of object to which the alert applies.
If you do not configure the package, the policy inherits the settings from the selected base policy.
Activating the Deactivated Alerts
Several out-of-the-box alerts have been deactivated to enhance your alert experience and reduce alert noise in your
environment. The alerts that are triggered for these deactivated alerts are auto-cancelled and as a result, you may
experience a dip in the number of alerts triggered. However, you can still activate these alerts in specific policies.
The reason for deactivating these alerts is that there could be an overwhelming number of alerts when alerts are turned
on for all objects, making it difficult to identify the ones that need immediate attention. It is recommended to exercise
caution while activating the deactivated alerts for applicable policies.
Read the KB article, KB 91410 to know the list of deactivated alerts.
Perform the following steps to activate the deactivated alerts:
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Policy Definition tile.
2. Select the required policy and in the right pane, click Edit Policy, and then select the Alerts and Symptoms tile.
3. Go to Filters and enter the name of the deactivated alert, and click Apply. You can refer to the KB article, KB 91410 for
the list of deactivated alerts.
4. Select Activated from the State drop-down list or click Actions > State > Activated.
5. Click Save.
Note:  You can also activate all the deactivated alerts at once. To do this, filter the alerts by Deactivated State, click
on the Select All option, and from the Actions drop-down list, click State > Activated.
Note:  You can also activate the deactivated alerts by creating a separate policy, adding custom groups in that policy,
and activating the alert definitions in the required policy. By doing this, the deactivated alerts are activated in the user-
defined policy and will apply to the objects in the custom group. For more details on custom groups, see Managing
Custom Object Groups in VCF Operations.
The deactivated alerts are now active.
Policy Symptom Definitions
Each policy includes a package of symptom definitions. Each symptom represents a distinct test condition on a property,
metric, or event. You can activate or deactivate the symptom definitions in your policy.
How the Policy Symptom Definitions Work
VCF Operations uses symptoms that are activated to generate alerts. When the symptoms used in an alert definition are
true, and the alert is activated, an alert is generated.
When a symptom exists for an object, the problem exists and requires that you take action to solve it. When an alert
occurs, VCF Operations presents the triggering symptoms, so that you can evaluate the object in your environment, and
with recommendations for how to resolve the alert.
To assess objects for symptoms, you can include symptoms packages in your policy for metrics and super metrics,
properties, message events, and faults. You can activate or deactivate the symptoms to determine the criteria that the
policy uses to assess and evaluate the data collected from the objects to which the policy applies. You can also override
the threshold, criticality, wait cycles, and cancel cycles.
The Symptoms pane displays the name of the symptom, the associated management pack adapter, object type, metric
or property type, a definition of the trigger such as for CPU usage, the state of the symptom, and the trigger condition. To
VMware by Broadcom  3153

---
## page 3154

 VMware Cloud Foundation 9.0
view a specific set of symptoms in the package, you can select the adapter type, object type, metric or property type, and
the state of the symptom.
When a symptom is required by an alert, the state of the symptom is activated, but is dimmed so that you cannot modify it.
The state of a required symptom includes an information icon that you can hover over to identify the alert that required this
symptom.
Where You Modify the Policy Symptom Definitions
To modify the policy package of symptoms, from the left menu click Infrastructure Operations > Configurations, and
then click the Policy Definition tile. Click Add to add a policy or select the required policy. In the right pane, click Edit
Policy to edit a policy. In the Create or Edit policies workspace, click Alerts and Symptoms. The alert definitions and
symptom definitions for the selected object types appear in the workspace.
Table 981: Symptom Definitions in the Create or Edit Policies Workspace
Option Description
Object Type Select an object type to view the symptom definitions list by the selected object type.
Filters Limits the list based on the text you type.
You can also filter by:
• Name
• Criticality
• Type
• State
• Local Changes
• Unsaved Changes
Actions Select one or more symptom definitions and select activate, deactivate, or inherit to change the
state for this policy.
Page Size The number of symptom definitions to list per page.
Symptom Definitions data grid Displays information about the symptom definitions for the object types. The full name for
Symptom Definition appears in a tooltip when you hover the mouse over the Symptom Definition
name.
• Symptom Definition. Symptom definition name as defined in the list of symptom definitions in
the Content area. Click this name to view the details of the symptom.
• State. Symptom definition state, either activated, deactivated, or inherited from the base
policy.
–
  Activated. Indicates that a symptom definition will be included.
–
  Activated (Force). Indicates state change due to a dependency.
–
  Deactivated. Indicates that a symptom definition not be included.
–
  Inherited. Indicates that the state of this symptom definition is inherited from the base
policy and will be included.
–
  Inherited. Indicates that the state of this symptom definition is inherited from the base
policy and will not be included.
• Threshold. To change the threshold, you must set the State to Activated, set the condition
to Override, and set the new threshold in the Override Symptom Definition Threshold dialog
box.
VMware by Broadcom  3154

---
## page 3155

 VMware Cloud Foundation 9.0
Option Description
• Type. Type of object to which the alert applies. Type determines whether symptom definitions
that apply to HT and DT metrics, properties, events such as message, fault, and metric, and
smart early warnings appear in the list.
• Criticality. Indicates the criticality.
• Adapter. Data source type for which the alert is defined.
• Object Type. Object type on which the symptom definition must be evaluated.
• Trigger. Static or dynamic threshold, based on the number of symptom definitions, the
object type and metrics selected, the numeric value assigned to the symptom definition, the
criticality of the symptom, and the number of wait and cancel cycles applied to the symptom
definition.
• Condition. Activates action on the threshold. When set to Override, you can change the
threshold. Otherwise set to default.
If you do not configure the package, the policy inherits the settings from the selected base policy.
Groups and Objects details
You can assign your local policy to one or more objects or groups of objects to have VCF Operations analyze those
objects according to the settings in your policy. You can trigger alerts when the defined threshold levels are violated, and
display the results in your dashboards, views, and reports.
How the Groups and Objects Workspace Works
When you create a policy, or modify the settings in an existing policy, you apply the policy to one or more objects or
groups of objects. VCF Operations uses the settings in the policy to analyze and collect data from the associated objects,
and displays the data in dashboards, views, and reports.
Where You Apply a Policy to Groups and Objects
To apply the policy to an object or groups of objects, from the left menu click Infrastructure Operations >
Configurations, and then click the Policy Definition tile. Click Add to add a policy or select the required policy. In the
right pane, click Edit Policy to edit a policy. In the Create or Edit policies workspace, click Groups and Objects.
Groups and Objects Options
To apply the policy to an object or groups of objects, select the check box for the groups or objects in the workspace.
You can then view the groups and objects associated with the policy. From the left menu click Infrastructure
Operations > Configurations, and then click the Policy Definition tile. Click Add to add a policy or select the required
policy. In the right pane, click Edit Policy to edit a policy. In the Create or Edit policies workspace, click Groups and
Objects. Click the Custom Groups tab to apply the policy to one or more groups of objects. Click the Objects tabs to
apply the policy to one or more objects.
For more information about how to create an object group, see the topic called Custom Object Groups Workspace to
Create a New Group.
For more information about how to create a policy, see Policy Workspace in VCF Operations .
Assigning Policies
The Policy Assignment workspace displays all the policies available in your environment.
VMware by Broadcom  3155