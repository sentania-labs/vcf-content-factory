# alerts-actions (VCF 9.0, pages 3157-3270)


---
## page 3157

 VMware Cloud Foundation 9.0
Option Description
4. In the Assign Objects window, select one of the following
options:
a. Only this object: Select this if you want to apply changes
only to the selected objects.
b. Include child object: Select this if you want to apply
changes to the child objects. You can define the depth of
change by entering a number in the Depth field.
Note:  The maximum value for the Depth field is 10.
5. Click Confirm.
To add custom groups to a policy:
1. In the right pane, click All Objects > Custom Groups.
2. Select the custom groups you want to assign to the policy in
the Custom Groups tab. You can also search for the custom
groups by typing the custom group name in the search box.
3. Drag the items from the Custom Groups tab and drop them
into the policy card on the left pane.
4. Click Confirm.
Assigned Objects Displays the objects and custom groups assigned to the selected
policy.
• Name: Displays the name of the object/custom group.
• Assignment Type: Displays the type of assignment.
• Depth: Displays the depth of the child objects that the policy
affects. Click the Edit icon to change the depth.
• Action: Allows you to delete an object or custom group.
You can also drag objects/custom groups from Assigned Objects
and drop them into the policy card of your choice.
Configuring Alerts and Using Actions
Alerts are a way to be watchful of anything that is new or an issue that could be potentially dangerous to your
environment. Whenever there is a problem in the environment, the alerts are generated. You can also create new alert
definitions so that the generated alerts inform you about the problems in the monitored environment. In VCF Operations ,
alerts and actions play key roles in monitoring the objects.
You may have several questions while working on alerts. Following are some of the key questions that will help you
navigate through the alert documentation.
• Where can I find all my alerts?
• What are the different types of alerts?
• Where can I get more information about alerts?
• How do I create a new alert definition?
• How do I define new symptoms?
• How do I define recommendations for my alerts?
• How can I create notification rules for alerts?
• How do I add my Outbound Plugins?
• How do I create payload templates for my Outbound Plugins?
• How can I export or import Outbound Settings?
• How do I deactivate alerts?
• How do I group alerts?
VMware by Broadcom  3157

---
## page 3158

 VMware Cloud Foundation 9.0
• What is intelligent alert clustering and how does it help in alert noise reduction?
Actions allow you to make changes to the objects in your environment. When you grant a user access to actions in VCF
Operations , that user can take the granted action on any object that VCF Operations manages. For details, see Actions in
VCF Operations.
Understanding Alerts in VCF Operations
This topic provides information on the different types of alerts in VCF Operations, how to access them, and how to view
more information about these alerts.
Types of Alerts
Alerts in VCF Operations are of three types. The alert type determines the severity of the problem.
Health Alerts The health alert list is all the generated alerts that are configured
to affect the health of your environment and require immediate
attention. You use the health alert list to evaluate, prioritize, and
immediately begin resolving the problems.
Risk Alerts The risk alerts list is all the generated alerts that are configured to
indicate risk in your environment. Address risk alerts in the near
future, before the triggering symptoms that generated the alert
negatively affect the health of your environment.
Efficiency Alerts The efficiency alerts list is all the generated alerts that are
configured to indicate problems with the efficient use of your
monitored objects in your environment. Address efficiency alerts to
reclaim wasted space or to improve the performance of objects in
your environment.
Accessing Alerts VCF Operations
The All Alerts or the Administrative Alerts page provides the list of all the alerts generated in VCF Operations. Use the
alert list to determine the state of your environment and to begin resolving problems.
Where You Find the All Alerts Page
From the left menu, click Infrastructure Operations > Alerts.
Where You Find the Administrative Alerts Page
As an admin, you can view the administrative alerts by clicking the warning icon next to the Alerts menu or from the
left menu, click Infrastructure Operations > Alerts and then click the Administrative Alerts tab. You can view the
Administrative Alerts page, only if you are a global admin user or if you have administrative privileges assigned to you.
How the All Alerts and Administrative Alerts Pages Work
By default, only active alerts are initially listed, and the alerts are grouped by Time. Review and manage the alerts in the
list using the toolbar options. Select multiple rows in the list using Shift+click, Control+click.
To see the alert details, click the alert name. The alert details appear on the right, including the symptoms triggered by
the alert. The system offers recommendations for addressing the alert and link to run the recommendation. A Run Action
button may appear in the details. Hover over the button to learn what recommendation is performed if you click the button.
Alternatively, you can view the Run button and the Suggested Fix in the Alerts data grid. You can filter by alerts that have
VMware by Broadcom  3158

---
## page 3159

 VMware Cloud Foundation 9.0
the Run option activated and perform the recommended task to address the alert from the Alerts data grid. Click the small
box on the lower left of the alert list to include the Suggested Fix and Run columns in the data grid.
Click the name of the object on which the alert was generated to see the object details, and access additional information
relating to metrics and events.
If you migrated alerts from a previous version of VCF Operations, the alerts are listed with a cancelled status and alert
details are not available.
All Alerts and Administrative Alerts Options
The alert options include toolbar and data grid options. Use the toolbar options to sort the alert list and to cancel, suspend,
or manage ownership. Use the data grid to view the alerts and alert details.
Select an alert from the list to activate the Actions menu:
Table 982: Actions Menu
Option Description
Cancel Alert Cancels the selected alerts. If you configure the alert list to display
only active alerts, the canceled alert is removed from the list.
Cancel alerts when you do not need to address them. Canceling
an alert does not cancel the underlying condition that generated
it. Canceling alerts is effective if the alert is triggered by fault and
event symptoms, because these symptoms are triggered again
only if subsequent faults or events occur on the monitored objects.
If the alert was generated based on metric or property symptoms,
the alert is canceled only until the next collection and analysis
cycle. If the violating values are still present, the alert is generated
again.
Delete Canceled Alerts Delete canceled (inactive) alerts by doing a group selection or by
individually selecting alerts. The option is deactivated for active
alerts.
Suspend Suspend an alert for a specified number of minutes.
You suspend alerts when you are investigating an alert and do not
want the alert to affect the health, risk, or efficiency of the object
while you are working. If the problem persists after the elapsed
time, the alert is reactivated and it will again affect the health, risk,
or efficiency of the object.
The user who suspends the alert becomes the assigned owner.
Assign to Assign the alert to a user. You can search for a specific username
and click Save to assign the alert to the selected user.
Take Ownership As the current user, you make yourself the owner of the alert.
You can only take ownership of an alert, you cannot assign
ownership.
Release Ownership Alert is released from all ownership.
Go to Alert Definition Switches to the Alert Definitions page, with the definition for the
previously selected alert displayed.
Deactivate... Provides two options to deactivate the alert:
Note:  To activate the Deactivate option, select Definition from
the Group By drop-down list, and click on the name of the Alert
Definition Group.
VMware by Broadcom  3159

---
## page 3160

 VMware Cloud Foundation 9.0
Option Description
• Deactivate the alert in all policies: This deactivates the alert for
all objects for all the policies.
• Deactivate alert in selected policies: This deactivates the alert
for objects having the selected policy.
Open an external application Actions you can run on the selected object.
For example, Open Virtual Machine in vSphere Client.
Table 983: Group By Options
Option Description
None Alerts are not sorted into specific groupings.
Time Group alerts by time triggered. This is the default option. You
can also group by 1 hour, 4 hours, Today and Yesterday, days of
current week, Last week and Older.
Criticality Group alerts by criticality. Values are, from the least critical: Info/
Warning/Immediate/Critical. See also Criticality in the "All Alerts
Data Grid Options" table, below.
Definition Group alerts by definition, that is, group like alerts together.
Object Type Group alerts by the type of object that triggered the alert. For
example, group alerts on hosts together.
Scope Group alerts by scope. You can search for alerts within the
selected scope.
Table 984: Quick Filters (Alert)
Quick Filters Descriptions
Filtering options Limit the list of alerts to those matching the filters you choose.
For example, you might have chosen the Time option in the Group
By menu. Now you can choose Status -> Active in the Quick
Filters menu, and the All Alerts/Administrative Alerts page displays
only the active alerts, ordered by the time they were triggered.
Options (see also the Group By and All Alerts Data Grid tables for more filter definitions)
Alert id ID given for an alert.
Alert Name of the alert definition that generated the alert.
Owner Name of operator who owns the alert.
Impact Alert badge affected by the alert. The affected badge, health,
risk, or efficiency, indicates the level of urgency for the identified
problem.
Alert Subtype Additional information about the type of alert that is triggered on a
selected object. This helps you categorize the alerts in a detailed
level other than Alert Type, so that you can assign certain types of
alerts to specific system administrators. For example, Availability,
Performance, Capacity, Compliance, and Configuration.
Status Current state of the alert.
Possible values include Active or Canceled.
VMware by Broadcom  3160

---
## page 3161

 VMware Cloud Foundation 9.0
Quick Filters Descriptions
Criticality The level of importance of the alert in your environment.
The level is based on the level assigned when the alert definition
was created, or on the highest symptom criticality, if the assigned
level was Symptom Based.
The possible values include:
• Critical
• Immediate
• Warning
• Information
Triggered On Name of the object for which the alert was generated, and the
object type, which appears in a tooltip when you hover the mouse
over the object name.
Click the object name to view the object details tabs where you
can begin to investigate any additional problems with the object.
Control State State of user interaction with the alert. Possible values include:
• Open. The alert is available for action and has not been
assigned to a user.
• Assigned. The alert is assigned to the user who is logged in
when that user clicks Take Ownership.
• Suspended. The alert was suspended for a specified amount
of time. The alert is temporarily excluded from affecting the
health, risk, and efficiency of the object. This state is useful
when a system administrator is working on a problem and
does not want the alert to affect the health status of the object.
Object Type Type of object on which the alert was generated.
Created On Date and time when the alert was generated.
Updated On Date and time when the alert was last modified.
An alert is updated whenever one of the following changes occurs:
• Another symptom in the alert definition is triggered.
• Triggering symptom that contributed to the alert is canceled.
Canceled On Date and time when the alert canceled for one of the following
reasons:
• Symptoms that triggered the alert are no longer active. Alert is
canceled by the system.
• Symptoms that triggered the alert are canceled because the
corresponding symptom definitions are deactivated in the
policy that is applied to the object.
• Symptoms that triggered the alert are canceled because the
corresponding symptom definitions were deleted.
• Alert definition for this alert is deactivated in the policy that is
applied to the object.
• Alert definition is deleted.
• User canceled the alert.
Action Choose Yes to filter based on alerts that have the Run option
activated. Choose No to filter based on alerts that have the Run
option deactivated.
VMware by Broadcom  3161

---
## page 3162

 VMware Cloud Foundation 9.0
The Alerts data grid provides the list of generated alerts used to resolve problems in your environment. An arrow in each
column heading orders the list in ascending or descending order.
Table 985: All Alerts and Administrative Alerts Data Grid
Option Description
Criticality Criticality is the level of importance of the alert in your
environment.
The level is based on the level assigned when the alert definition
was created, or on the highest symptom criticality, if the assigned
level was Symptom Based.
The possible values include:
• Critical
• Immediate
• Warning
• Information
Alert Name of the alert definition that generated the alert.
Click the alert name to display the alert details to the right.
Triggered On Name of the object for which the alert was generated, and the
object type, which appears in a tooltip when you hover the mouse
over the object name.
Click the object name to view the object details tabs where you
can begin to investigate any additional problems with the object.
Created On Date and time when the alert was generated.
Status Current state of the alert.
Possible values include Active or Canceled.
Alert Type Describes the type of alert that triggered on the selected object,
and helps you categorize the alerts so that you can assign certain
types of alerts to specific system administrators. For example,
Application, Virtualization/Hypervisor, Hardware, Storage,
Network, Administrative, and Findings.
Alert Subtype Describes additional information about the type of alert that
triggered on the selected object, and helps you categorize the
alerts to a more detailed level than Alert Type, so that you can
assign certain types of alerts to specific system administrators. For
example, Availability, Performance, Capacity, Compliance, and
Configuration.
Importance Displays the priority of the alert. The importance level of the alert
is determined using a smart ranking algorithm.
Suggested Fix Displays the recommendation to address the alert.
Action Click this button to perform the recommendation to address the
alert.
Viewing Alert Information
When you click an alert from the all alerts list, the alert information appears on the right. View the alert information to see
the symptoms which triggered the alert, recommendations to fix the underlying issue, and troubleshoot the cause of the
alert.
VMware by Broadcom  3162

---
## page 3163

 VMware Cloud Foundation 9.0
Different ways to view Alert information
• From the left menu, click Operations > Alerts, and then click an alert from the alert list.
• From the left menu, click Global Inventory, then select a group, custom data center, application, or inventory object.
Click the object and then the Alerts tab.
• In the menu, select Search and locate the object of interest. Click the object and then the Alerts tab.
The alert description is hidden when you open the alert information. Click View Description to see the description of the
alert. View the time stamp of when the alert started, and when it was updated, below the alert title.
Alert Details Tab Section Description
Recommendations View recommendations for
the alert. Click < or > to cycle
through the recommendations.
To resolve the alert, click the
Run Action button if it appears.
Other Recommendations Collapse the section to view
additional recommendations.
See the links in the Need More
Information? section to view
additional metrics, events, or
other details that appear as a
link.
Alert Basis
Active Only This option is activated by
default. When activated, all
active symptoms/conditions
that were met for the alert are
displayed. When deactivated,
all the symptoms/conditions of
an alert are displayed.
Symptoms View the symptoms that
triggered the alert. Collapse
each symptom to view
additional information.
Conditions View the conditions that
triggered the alert. Collapse
each condition to view
additional information.
Notes Enter your notes about the alert
and click Submit to save.
Close Click the X icon to close the
alert details tab.
Related Alerts Tab The Related Scope displayed on the right, shows the objects that
are one level above and one level below the object on which the
alert was triggered. This topology is fixed. You cannot change the
scope in the Related Alerts tab.
On the right, you can see the following:
VMware by Broadcom  3163

---
## page 3164

 VMware Cloud Foundation 9.0
• If the same alert was triggered on the object in the past 30
days. This helps you understand if this is a recurring problem
or something new.
• If the same alert was triggered on other peers in the same
environment, in the past 30 days. This helps you do a quick
peer analysis to understand if others are impacted with the
same problem.
• All the alerts triggered in the current topology. This helps you
investigate if there are other alerts upstream or downstream in
the environment which are impacting the health of the object.
Potential Evidence Tab See the Potential Evidence tab for potential evidences around
the problem, and to arrive at the root cause. This tab displays
events, property changes, and anomalous metrics potentially
relevant to the alert. The time range and the scope are fixed. To
modify the scope or the time range and investigate further, click
Launch Workbench. This runs the troubleshooting workbench.
The time range that is displayed in the potential evidence tab is
two hours and thirty minutes before the alert was triggered. VCF
Operations looks for potential evidences in this time range.
Intelligent Alerts
Every enterprise could have five or more monitoring tools that monitor various aspects of their data center operations
around the clock. This could cause an alert flooding situation where multiple alerts are generated by a single monitoring
tool or multiple tools for the same problem. As a result, IT administrators must sift through thousands of alerts to filter out
the noise and focus on key issues, thus, increasing the sheer volume of the alerts and posing an alert storm or alert noise
resulting in teams being unable to identify the most critical alerts. Alert flooding happens because monitoring tools lack the
intelligence to understand that all alerts depict the same problem.
Machine Learning (ML) helps automate the management of complex systems that contain thousands of objects like VMs,
Hosts, and Datastores, through monitoring millions of metrics, huge volumes of logs, and application traces, to capture a
high-resolution image of the entire stack.
VCF Operations through intelligent alert clustering helps eliminate business downtime that happens because of a lack of
faster troubleshooting abilities and solving critical problems over multiple objects.
Where You Find the Intelligent Alerts Tab
From the left menu, click Infrastructure Operations > Alerts, and then, click the Intelligent Alerts tab.
How Intelligent Alert Clustering Works
Intelligent alerts, also known as alert clusters in VCF Operations, groups related alerts together based on their creation
time and their topology distance. This approach provides a more organized and efficient method for troubleshooting,
compared to dealing with individual alerts arising from the same underlying issue. Alerts clustering is done based on
DBScan algorithm. DBScan (Density-Based Spatial Clustering of Applications with Noise) is an unsupervised clustering
Machine Learning algorithm that attempts to group data points closely packed into artificial clusters. In the context of VCF
Operations, DBScan has been tailored into a streaming algorithm with specific parameters configured such as minimum
points is set to five, time difference is set to fifteen minutes, and topology distance is set to one, for considering only
direct children and parents. Two main views, Intelligent alert lifetime and Objects topology, are provided for alert cluster
troubleshooting.
The Intelligent Alert tab displays the list of alert clusters in the left pane. Click any alert cluster to view the details in the
right pane.
VMware by Broadcom  3164

---
## page 3165

 VMware Cloud Foundation 9.0
Option Description
Filters You can filter the alert clusters by their status. Select Active or
Inactive from the Status drop-down list and click Apply.
Alert Cluster The alert cluster card displays the following:
• Status: Displays if the status of the alert cluster is active or
inactive.
• Object: Displays the name of the object to which the cluster is
assigned.
• Alert Chart: Displays the number of alerts and objects along
with the criticality of the alert. Hover over the graph to view the
details.
• Start time: Displays the time when the first cluster that
satisfies the clustering condition is identified.
• End time: Displays the time when the cluster no longer
qualifies to be an alert cluster.
Click the alert cluster to view the details in the right pane.
Object Name of the root object.
Start time/End time The start time of the alert cluster is the time when the first cluster
that satisfies the clustering condition is identified. The end time of
the alert cluster is the time when the cluster no longer qualifies to
be an alert cluster.
Alerts/Objects Select Alerts to view the graphical representation of alerts in a
specific period.
Select Objects to view the object-relationship chart for an alert
cluster. Hover over the object and click Details to open the
Summary page of the object.
How it Started Click How it Started to view the lifetime of an alert cluster. Each
bubble displays alerts and objects, hover over the bubble to view
more details.
Troubleshoot Click this to launch the Troubleshooting workbench for further
troubleshooting.
Graph Chart The graph chart displays the number of alerts by time, for the
selected alert cluster.
Click the chart legend to filter alerts by:
• Criticality
– Critical
– Immediate
– Warning
– Info
• Objects
Click the Calendar icon to view past alerts by selecting the Range
or by selecting a date in the From and To fields.
Group By You can group alerts by:
• Definition
• Scope
• Time
• Criticality
• Object Type
VMware by Broadcom  3165

---
## page 3166

 VMware Cloud Foundation 9.0
Option Description
Filters You can filter alerts by:
• Alert ID
• Alert name
• Owner
• Impact
• Alert Type
• Alert Subtype
• Status
Alert Definitions in VCF Operations
Alert definitions are a combination of symptoms and recommendations that you combine to identify problem areas in your
environment and generate alerts on which you can act for those areas. You can then respond to the alerts with effective
solutions that are provided in the recommendations.
Where You Find Alert Definitions
To manage your alert definitions, from the left menu, click Infrastructure Operations >  Configurations, and then click
the Alert Definitions tile.
Option Description
Toolbar options Use the toolbar options to manage your alert definitions.
• Add. Add an alert definition.
Click the horizontal ellipsis to perform the following actions.
• Edit. Modify the selected definition.
• Delete. Remove the selected definition.
VMware by Broadcom  3166

---
## page 3167

 VMware Cloud Foundation 9.0
Option Description
• Clone. Create a copy of the selected definition so that you can
customize it for your needs.
• Export. Downloads the alert definition.
• Import. Allows you to import alert definitions. To import:
– Click the Import option from the horizontal ellipsis.
– Click Browse and select the file to import.
– Select if you want to Overwrite or Skip the file in case of a
conflict.
– Click Import to import the alert definition, and click Done.
Filters Limits the list of alerts to those matching the filter you create.
You can also sort on the columns in the data grid.
Name Name of the alert definition, which is also the name of the alert
that appears when the symptoms are triggered.
Adapter Type Adapter that manages the selected base object type.
Object Type Base object type against which the alert is defined.
Alert Type Metadata that is used to classify the alert when it is generated.
You define the value on the Alert Impact page of the workspace.
Alert Subtype Subcategory of the alert type and is the metadata that is used to
classify the alert when it is generated.
You define the value on the Alert Impact page of the workspace.
Criticality Severity of the alert when it is generated. The criticality includes
the following possible values:
• Symptom. Alert is configured to display symptom based
criticality.
• Critical
• Immediate
• Warning
• Info
Impact Alert is configured to affect the Health, Risk, or Efficiency badge.
Defined by Indicates who added the alert definition. The alert can be added
by an adapter, a user, or the VCF Operations system.
Last Modified Displays the date on which the alert was last modified.
Predefined alerts are provided in VCF Operations as part of your configured adapters. Use Alert Definitions to manage
your VCF Operations alert library, and to add or modify the definitions.
Modifying Alert Definitions If you modify the alert impact type of an alert definition, any alerts
that are already generated will have the previous impact level. Any
new alerts will be at the new impact level. If you want to reset all
the generated alerts to the new level, cancel the old alerts. If they
are generated after cancellation, they will have the new impact
level.
Symptoms in Alert Definitions Symptom definitions evaluate conditions in your environment that,
if the conditions become true, trigger a symptom and can result
in a generated alert. You can add symptom definitions that are
based on metrics or super metrics, properties, message events,
fault events, or metric events. You can create a symptom definition
VMware by Broadcom  3167

---
## page 3168

 VMware Cloud Foundation 9.0
as you create an alert definition or as an individual item in the
appropriate symptom definition list.
When you add a symptom definition to an alert definition,
it becomes a part of a symptom set. A symptom set is the
combination of the defined symptom with the argument that
determines when the symptom condition becomes true.
An alert definition comprises one or more symptom sets. If an alert
definition requires all of the symptom sets to be triggered before
generating an alert, and only one symptom set is triggered, an
alert is not generated. If the alert definition requires only one of
several symptom sets to be triggered, then the alert is generated
even though the other symptom sets were not triggered.
Recommendations in Alert Definitions Recommendations are the remediation options that you provide
to your users to resolve the problems that the generated alert
indicates.
When you add an alert definition that indicates a problem
with objects in your monitored environment, add a relevant
recommendation. Recommendations can be instructions to your
users, links to other information or instruction sources, or VCF
Operations actions that run on the target systems.
Creating Alert Definitions
The alert definition process includes adding symptoms that trigger an alert and recommendations that help you resolve
the alert. The alert definitions you create with this process are saved to your VCF Operations Alert Definition Overview list
and actively evaluated in your environment based on your configured policies.
You can create or reuse existing symptoms and recommendations while defining an alert definition. If you create
symptoms and recommendations, you add them to the definition, and they are added to the symptom and
recommendations content libraries for future use. You also activate policies and select notifications for the alerts.
1. To create or edit your alert definitions, from the left menu, click Infrastructure Operations >  Configurations, and
then click the Alert Definitions tile.
2. Click Add to add a definition, or click the vertical ellipsis and select Edit to edit the selected definition.
3. In the Alert tab, enter details of the alert.
Option Description
Name Name of the alert as it appears when the alert is generated.
Description Description of the alert as it appears when the alert is
generated. Provide a useful description for your users.
Base Object Type The object type against which the alert definition is evaluated
and the alert is generated.
The drop-down menu includes all of the object types in your
environment. You can define an alert definition based on one
object type.
Impact Under Advanced Settings, select the badge that is affected if the
alert is generated.
You can select a badge based on the urgency of the alert.
• Health. Alert requires immediate attention.
• Risk. Alert should be addressed soon after it is triggered,
either in days or weeks.
VMware by Broadcom  3168

---
## page 3169

 VMware Cloud Foundation 9.0
Option Description
• Efficiency. Alert should be addressed in the long term to
optimize your environment.
Criticality Severity of the alert that is communicated as part of the alert
notification.
Select one of the following values.
• Info. Informational purposes only. Does not affect badge
color.
• Warning. Lowest level. Displays yellow.
• Immediate. Medium level. Displays orange.
• Critical. Highest level. Displays red.
• Symptom Based. In addition to alert criticality, each
symptom includes a defined criticality. Criticality of the alert
is determined by the most critical of all of the triggered
symptoms. The color is dynamically determined accordingly.
It you negate symptoms, the negative symptoms to not
contribute to the criticality of a symptom-based alert.
Alert Type and Subtype Select the type and subtype of alert.
This value is metadata that is used to classify the alert when it is
generated, and the information is carried to the alert, including
the alert notification.
You can use the type and subtype information to route the
alert to the appropriate personnel and department in your
organization.
Wait Cycle The symptoms included in the alert definition remain triggered
for this number of collection cycles before the alert is generated.
The value must be 1 or greater.
This setting helps you adjust for sensitivity in your environment.
The wait cycle for the alert definition is added to the wait cycle
for the symptom definitions. In most definitions you configure
the sensitivity at the level of symptom level and configure the
wait cycle of alert definition to 1. This configuration ensures that
after all of the symptoms are triggered at the desired symptom
sensitivity level, the alert is immediately triggered.
Cancel Cycle The symptoms are cancelled for this number of collection cycles
after which the alert is cancelled.
The value must be 1 or greater.
This setting helps you adjust for sensitivity in your environment.
The cancel cycle for the alert definition is added to the cancel
cycle for the symptom definitions. In most definitions you
configure the sensitivity at the level of symptom level and
configure the wait cycle of the alert definition to 1. This
configuration ensures that after all of the symptom conditions
disappear after the desired symptom cancel cycle, the alert is
immediately canceled.
4. Click Next to add symptom definitions.
5. In the Symptoms/Conditions, drag the selected symptom/condition in to the left pane. Use the workspace on the left
to specify whether all or any of the symptoms/conditions or symptom/condition sets must be true to generate an alert.
As you add one or more symptoms, you create a symptom expression. If this expression is evaluated as true, then the
VMware by Broadcom  3169

---
## page 3170

 VMware Cloud Foundation 9.0
alert is generated. You can similarly define one or more conditions for your alert, and when the conditions are met, the
alert is generated. You can view the alert in the All Alerts page.
Table 986: Add Symptoms/Conditions Selection Options
Option Description
Defined On Object that the symptom evaluates.
As you create alert definitions, you can select or define symptoms
for the base object type and for related object types, based on the
object relationship hierarchy. The following relationships are object
types as they relate to the alert definition base object type.
• Self. A base object type for the alert definition. For example,
host system.
• Descendant. An object type that is at any level below the base
object type, either a direct or indirect child object. For example,
a virtual machine is a descendant of a host system.
• Ancestor. An object type that is one or more levels higher than
the base object type, either a direct or indirect parent. For
example, a data center and a vCenter are ancestors of a host
system.
• Parent. An object type that is in an immediately higher level in
the hierarchy from the base object type. For example, a data
center is a parent of a host system.
• Child. An object type that is one level below the base object
type. For example, a virtual machine is a child of a host
system.
Symptoms tab
Select Symptom Select the type of symptom definition that you are adding for the
current Defined On object type.
• Metric / Property. Add symptoms that use metric and property
symptoms. These metrics are based on the operational or
performance values, and configuration properties that collects
from target objects in your environment.
• Message Event. Add symptoms that use message event
symptoms. These symptoms are based on events received as
messages from a component of VCF Operations or from an
external monitored system through the system's REST API.
• Fault Event. Add symptoms that use fault symptoms. These
symptoms are based on events that monitored systems
publish. VCF Operations correlates a subset of these events
and delivers them as faults. Faults are intended to signify
events in the monitored systems that affect the availability of
objects in your environment.
• Metric Event. Add symptoms that use metric event symptoms.
These symptoms are based on events communicated from
a monitored system where the selected metric violates a
threshold in a specified manner. The external system manages
the threshold, not VCF Operations. These symptoms are
based on conditions reported for selected metrics by an
external monitored system, as compared to metric symptoms,
which are based on thresholds that VCF Operations is actively
monitoring.
VMware by Broadcom  3170

---
## page 3171

 VMware Cloud Foundation 9.0
Option Description
• Logs. Select the log based symptoms which you have
defined after integration with VCF Operations for logs . You
can combine metric and log based symptoms in one alert
definition. If you do not want to create a Log based symptom
for the alert, you can use a log based Condition.
• Smart Early Warning. Add a symptom that uses a defined
condition that is triggered when the number of anomalies
on an object is over the trending threshold. This symptom
represents the overall anomalous behavior of the object.
Anomalies are based on VCF Operations analysis of the
number of applicable metrics that violate the dynamic
threshold that determines the normal operating behavior of the
object. This symptom is not configurable. You either use it or
you do not use it.
Filter by Object Type Available only when you select a Defined On value other than
Self.
Limits the symptoms to those that are configured for the selected
object type based on the selected Defined On relationship.
Create New Symptom If symptoms that you need for your alert do not exist, you can
create them.
Opens the symptoms definition dialog box.
Not available for Smart Early Warning symptoms, which are
predefined in the system.
All Filters Filter the list of symptom definitions. This selection is available
when Defined On is set to Self, or when it is set to another
relationship and you select an object from the Filter by Object
Type drop-down menu.
• Symptom. Type text to search on the name of the symptom
definitions. For example, to display all symptom definitions that
have efficiency in their name, type Efficiency.
• Defined By. Type text to search for the name of the adapter
that defines the symptom definitions. For example, to display
all symptom definitions provided by the vCenter Adapter, type
vCenter. To display only user-defined symptom definitions,
type the search term User.
To clear a filter, click the double arrow icon that appears next to
the filter name.
Quick filter (Name) Search the list based on the symptom name.
Symptoms list List of existing symptoms for the selected object type. To configure
a symptom, drag it into the left workspace.
To combine symptoms that are based on multiple levels in
the hierarchy, select the new Defined On level and Filter by
Object Type before you select and drag the new symptom to the
workspace.
Conditions tab
Select Specific Object Select a specific object based on its object type, adapter type,
policy, collection state, and status.
Filter Search the metrics based on object type.
Conditions list List of metrics for the selected object type. To configure a
condition, drag it into the left workspace.
VMware by Broadcom  3171

---
## page 3172

 VMware Cloud Foundation 9.0
Option Description
Log based condition Create a log based condition without creating a log based
symptom first. To configure a condition, drag it into the left
workspace. You can combine metric based condition and log
based condition to create an advanced alert trigger set.
Use the workspace to configure the interaction of the symptoms, symptom sets, and conditions.
Table 987: Symptom Sets in the Alert Definition Workspace
Option Description
Trigger alert when {operator} of the
symptom sets are true
Select the operator for all of the added symptom/condition sets. Available only when you
add more than one symptom/condition set.
• All. All of the symptom/condition sets must be true before the alert is generated.
Operates as a Boolean AND.
• Any. One or more of the symptom/condition sets must be true before the alert is
generated. Operates as a Boolean OR.
Symptoms The symptom/condition sets comprise an expression that is evaluated to determine if an
alert should be triggered.
To add one or more symptoms from the symptom list to an existing symptom set, drag
the symptom from the list to the symptom set. To create a new symptom set for the alert
definition, drag a symptom to the landing area outlined with a dotted line.
Symptom sets Add one or more symptoms to the workspace, define the points at which the symptom
sets are true, and specify whether all or any of the symptoms in the symptom set must be
true to generate the alert.
A symptom set can include one or more symptoms/conditions, and an alert definition can
include one or more symptom/condition sets.
If you create a symptom set where the Defined On object is Self, you can set the
operator for multiple symptoms in the symptom set.
If you create a symptom set where the Defined On object is a relationship other than
Self, you can set the operator and modify the triggering threshold. To configure the
symptom set criteria, you set the options.
• Value operator. Specifies how the value you provide in the value text box is compared
to a number of related objects to evaluate the symptom/condition set as true.
• Value text box. Number of objects of the specified relationship, based on the value
type, that are required to evaluate the symptom/condition set as true.
• Value type. Possible types include the following items:
– Count. Exact number of related objects meet the symptom/condition set criteria.
– Percent. Percentage of total related objects meet the symptom/condition set
criteria.
– Any. One or more of the related objects meet the symptom/condition set criteria.
– All. All of the related objects meet the symptom/condition set criteria.
• Symptom set operator. Operator applied between symptoms/conditions in the
symptom set.
– All. All of the symptoms/conditions must be true before the alert is generated.
Operates as a Boolean AND.
– Any. One or more of the symptoms/condition must be true before the alert is
generated. Operates as a Boolean OR.
VMware by Broadcom  3172

---
## page 3173

 VMware Cloud Foundation 9.0
Option Description
When you include a symptom in a symptom set, the condition must become true to
trigger the symptom set. However, you might want to configure a symptom set where the
absence of a symptom condition triggers a symptom. To use the absence of the symptom
condition, click the vertical ellipsis on the left of the symptom name and select Invert
Symptom.
Although you can configure symptom criticality, if you invert a symptom, it does not have
an associated criticality that affects the criticality of generated alerts.
Table 988: Conditions in the Alert Definition Workspace
Option Description
Alert is triggered when {operator} of the
sets are true
Select the operator for all of the added condition sets. Available only when you add more
than one condition set.
• All. All of the condition sets must be true before the alert is generated. Operates as a
Boolean AND.
• Any. One or more of the condition sets must be true before the alert is generated.
Operates as a Boolean OR.
Conditions The condition sets comprise an expression that is evaluated to determine if an alert
should be triggered.
• Condition. Determines how the value you specify in the value text box is compared to
the current value of the metric or property when the condition is evaluated.
• Value. Value that specifies the threshold.
• Criticality level. Severity of the symptom/condition when it is triggered.
• Wait Cycle. The trigger condition should remain true for this number of collection
cycles before the symptom/condition is triggered. The default value is 1, which
means that the symptom/condition is triggered in the same collection cycle when the
condition became true.
Note:  You cannot edit the wait cycle while defining conditions for Properties and
Population.
• Cancel Cycle. The symptom/condition is canceled after the trigger condition is false
for this number of collection cycles after which the symptom/condition is cancelled.
The default value is 1, which means that the symptom/condition is canceled in the
same cycle when the condition becomes false.
Note:  You cannot edit the cancel cycle while defining conditions for Properties and
Population.
To add one or more conditions from the condition list to an existing symptom/condition
set, drag the condition from the list to the symptom/condition set.
6. Click Next to add recommendations.
7. In the Recommendations tab, drag the selected recommendation in to the left pane. Use the workspace on the left to
to change the priority order.
Table 989: Add Recommendations Options in the Alert Definition Workspace
Create New Recommendation If recommendations that you need to resolve the symptoms in the
problem do not exist, you can create them.
All Filters Filter the list of recommendations.
• Description. Type text to search on the name of the
recommendation. For example, to display all recommendations
that have memory in their name, type Memory.
VMware by Broadcom  3173

---
## page 3174

 VMware Cloud Foundation 9.0
• Defined By. Type text to search for the name of the adapter
that defines the recommendation. For example, to display
all recommendations provided by the vCenter Adapter, type
vCenter.
To clear a filter, click the double arrow icon that appears next to
the filter name.
Quick filter (Name) Limits the list based on the text you enter.
List of available recommendations. List of existing recommendations that you can drag to the
workspace.
Recommendations are instructions and, where possible, actions
that assist you with resolving alerts when they are triggered.
Recommendation workspace Add one or more recommendations to the workspace.
If you add more than one recommendation, you can drag the
recommendations to change the priority order.
8. Click Next to activate policies.
9. In the Policies tab, you can view the policy tree in the left pane and you can either select the default policy or any
other policy from the tree.
You can automate the recommended action that has the highest priority by changing the Status to Activated in the
right pane. Whenever the alert is executed on an object within the policy, the recommended action will be executed on
the object.
Note:  To deactivate alerts associated with a specific policy, deselect the policy in the left pane, and click Update.
You can also customize thresholds for a policy by clicking the policy and editing the trigger value in the right pane.
Editing the threshold of conditions will affect its alert definition in the selected policy.
Note:  If you create an alert without enabling any policies, then the alert remains inactive.
10. Click Create to create the alert. The new alert appears in the list of alert definitions.
Symptom Definitions in VCF Operations
Symptoms are conditions that indicate problems in your environment. You can define symptoms in VCF Operations and
add them to alert definitions so that you know when a problem occurs with your monitored objects.
As data is collected from your monitored objects, the data is compared to the defined symptom condition. If the condition
is true, then the symptom is triggered.
VMware by Broadcom  3174

---
## page 3175

 VMware Cloud Foundation 9.0
To define symptoms, from the left menu, click Infrastructure Operations >  Configurations, and then click the Symptom
Definitions
tile. .
You can define symptoms based on:
• Metric/Property
• Message Events
• Faults
• Logs Symptoms
The symptoms defined in your environment are managed in the Symptom Definitions. When the symptoms that are added
to an alert definition are triggered, they contribute to a generated alert.
Define Symptoms to Cover All Possible Severities and
Conditions
Use a series of symptoms to describe incremental levels of
concern. For example, Volume nearing capacity limit
might have a severity value of Warning while Volume reached
capacity limit might have a severity level of Critical. The
first symptom is not an immediate threat. The second symptom is
an immediate threat.
Defining Symptoms for Alerts
The symptoms defined in your environment are managed in the Symptom Definitions page.
You can create a symptom definition while creating an alert definition or as an individual item from the Symptom
Definitions page.
You can define symptoms based on:
• Metric/Property
• Message Events
• Fault
• Logs
VMware by Broadcom  3175

---
## page 3176

 VMware Cloud Foundation 9.0
Metric/Property Symptoms
Metric/Property symptoms are based on the operational/performance values or the configuration properties that VCF
Operations collects from target objects in your environment.
Metric Symptom Definitions You can configure the symptoms to evaluate static thresholds
or dynamic thresholds. You define symptoms based on metrics
so that you can create alert definitions that let you know when
the performance of an object in your environment is adversely
affected.
Static Thresholds Metric symptoms that are based
on a static threshold compare
the currently collected metric
value against the fixed value
you configure in the symptom
definition.
For example, you can configure
a static metric symptom where,
when the virtual machine CPU
workload is greater than 90, a
critical symptom is triggered.
Dynamic Thresholds Metric symptoms that are
based on dynamic thresholds
compare the currently collected
metric value against the trend
identified by VCF Operations ,
evaluating whether the current
value is above, below, or
generally outside the trend.
For example, you can configure
a dynamic metric symptom
where, when the virtual machine
CPU workload is above the
trended normal value, a critical
symptom is triggered.
The Metric Symptom Definitions is a list of the metric-based
symptoms defined in your VCF Operations environment. You use
the information in the list to evaluate the defined metric threshold
triggering states and determine if you want to add, edit, or clone
symptoms.
Property Symptom Definitions You define symptoms based on properties so that you can create
alert definitions that let you know when changes to properties on
your monitored objects can affect the behavior of the objects in
your environment.
The Property Symptom Definitions is a list of the property-based
symptoms in your VCF Operations environment. You use the
information in the list to evaluate the defined property triggering
states and determine whether to add, edit, or clone symptoms.
Where You Find Metric/Property Symptoms
To manage symptoms based on metrics/properties, from the left menu, click Operations >  Configurations, and then in
the right pane, click Symptom Definitions >  Metric / Property tile.
VMware by Broadcom  3176

---
## page 3177

 VMware Cloud Foundation 9.0
You can also define symptoms as you are defining alerts in the Alert Definition Workspace.
Table 990: Metric/Property Symptoms Options
Option Description
Toolbar options Use the toolbar options to manage your symptoms. You can select
multiple symptoms using Ctrl+click or Shift+click.
• Add. Add a symptom definition.
Click the horizontal ellipsis to perform the following actions.
• Edit. Modify the selected symptom definition. Any changes you
make affect the alert definitions that include this symptom. You
cannot edit a symptom that manages a badge.
• Delete. Remove the selected symptom definition. You cannot
delete an alert that is used in an alert definition. To delete a
symptom, you must first remove it from the alert definitions in
which it is used. You cannot delete a symptom that manages a
badge.
• Clone. Create a copy of the selected symptom definition.
• Export. Downloads the symptom definition.
• Import. Allows you to import symptom definitions. To import:
– Click the Import option from the horizontal ellipsis.
– Click Browse and select the file to import.
– Select if you want to Overwrite or Skip the file in case of a
conflict.
– Click Import to import the symptom definition, and click
Done.
Filter options Limits the list based on the text you type.
You can also sort on the columns in the data grid.
Name Descriptive name of the symptom.
Criticality Severity of the symptom when it is triggered.
Object Type Base object type against which the symptom is defined.
Metric Name Text string that is used as a reference key for the metric. You can
use the metric key to locate additional information about how the
system statistics are derived from the metric.
Operator Operator used to compare the current value to the threshold
value, and trigger the symptom.
Value Text string that is the compared value for the property.
Defined By Indicates whether the symptom was created by a user or provided
with a solution adapter.
Last Modified Displays the date on which the symptom was last modified.
Modified By Displays the name of the user who last modified the symptom.
Defining Metric/Property Symptoms
A metric symptom is triggered when a metric is compared to the configured static or dynamic thresholds, and the
symptom condition is evaluated as true in VCF Operations .
VMware by Broadcom  3177

---
## page 3178

 VMware Cloud Foundation 9.0
Defining Metric Symptoms
If the symptom is based on a static threshold, the metric is compared based on the configured operator and the provided
numeric value. If the symptom is based on a dynamic threshold, the metric is compared based on whether the current
value is above, below, or abnormal compared to the calculated trend value.
1. To define symptoms based on metrics, from the left menu, click Infrastructure Operations >  Configurations, and
then in the right pane, click Symptom Definitions >  Metric / Property. Click Add to define a metric-based symptom
in the workspace.
2. Enter the following details.
Option Description
Base Object Type Object against which the symptom is evaluated.
Based on the select object type, the list of available metrics
displays only the metrics applicable to the object type.
Symptom Type Select Metrics from the Symptom Type drop-down list.
Select Specific Object If a metric or supermetric is not listed in the common metric
or supermetric list, based on the selected based object type,
use Select Object to inspect the metrics or supermetrics of a
selected object so that you can locate the property that you must
use to create the symptom. Even though you select a metric
or supermetric for a specific object, the symptom definition is
applicable to all objects with that metric or supermetric in your
environment.
Search Use a word search to limit the number of items that appear in the
list.
Metric list List of metrics for the selected base object type.
Click and drag the metric to the left pane.
Symptom Definition workspace
You can define symptoms based on static or dynamic thresholds.
Threshold Determines if the symptom is static or dynamic.
• Static thresholds are fixed values that trigger symptoms as
true. You can configure one threshold for each symptom. You
can also create multiple symptoms for multiple thresholds.
For example, configure one symptom where the CPU use is
greater than 90 percent and another where the CPU usage is
less than 40 percent. Each is a separate symptom and can be
added individually to an alert definition.
• Dynamic thresholds are based on VCF Operations trended
data where the triggering value is determined through the
analytics. If the current value of the metric does not fall in the
trended range, the symptom is triggered.
Static Threshold configuration options If you select Static Threshold, configure the options for this
threshold type.
• Symptom name. Name of the symptom as it appears in the
symptom list when configuring an alert definition, as it appears
when the alert is generated, and when viewing triggered
symptoms.
• Condition. Determines how the value you specify in the value
text box is compared to the current value of the metric when
the symptom is evaluated.
• Value. Value that the condition evaluates.
• Criticality. Severity of the symptom when it is triggered.
VMware by Broadcom  3178

---
## page 3179

 VMware Cloud Foundation 9.0
Option Description
• Wait Cycle. The trigger condition should remain true for this
number of collection cycles before the symptom is triggered.
The default value is 1, which means that the symptom is
triggered in the same collection cycle when the condition
became true.
• Cancel Cycle. The symptom is canceled after the trigger
condition is false for this number of collection cycles after which
the symptom is cancelled. The default value is 1, which means
that the symptom is canceled in the same cycle when the
condition becomes false.
• Evaluate on instanced metrics. Select this check box so that
the system evaluates the object level symptom as well as the
instance level symptom. For example, for CPU usage, when
the check box is not selected, the symptom is triggered based
on the object's CPU usage. However, if you select the check
box, the system also evaluates CPU usage of each of the
cores. If any of the cores is found to be crossing the threshold,
the symptom is triggered.
• Exclude the following instances of the metric. To exclude
specific instanced metrics from the symptom, drag the metric
instances from the left pane. If you cannot locate the metric
instance you want to exclude, you can search for it in another
object that uses the metric by clicking Select Specific Object
next to the search box.
Dynamic Threshold configuration options If you select Dynamic Threshold, configure the options for this
threshold type.
• Symptom name. Name of the symptom as it appears in the
symptom list when configuring an alert definition, as it appears
when the alert is generated, and when viewing triggered
symptoms.
• Condition. Relationship of the current value to trended range
based on the following options:
– Above Threshold. If current value is above trended range,
the symptom is triggered.
– Below Threshold. If the current value is below the trended
range, the symptom is triggered.
– Abnormal. If the current value is either above or below the
trended range, the symptom is triggered.
• Criticality. Severity of the symptom when it is triggered.
• Evaluate on instanced metrics. Select this check box so that
the system evaluates the object level symptom as well as the
instance level symptom. For example, for CPU usage, when
the check box is not selected, the symptom is triggered based
on the object's CPU usage. However, if you select the check
box, the system also evaluates CPU usage of each of the
cores. If any of the cores is found to be crossing the threshold,
the symptom is triggered.
• Exclude the following instances of the metric. To exclude
specific instanced metrics from the symptom, drag the metric
instances from the left pane. If you cannot locate the metric
instance you want to exclude, you can search for it in another
object that uses the metric by clicking Select Object next to the
Metrics field.
3. Click Save.
VMware by Broadcom  3179

---
## page 3180

 VMware Cloud Foundation 9.0
Defining Property Symptom
A property symptom is triggered when the defined threshold is compared with the current property value and the
comparison is evaluated as true.
1. To define symptoms based on properties, from the left menu, click Infrastructure Operations >  Configurations,
and then in the right pane, click Symptom Definitions >  Metric / Property. Click Add to define a property-based
symptom in the workspace.
2. Enter the following details.
Option Description
Base Object Type Object against which the symptom is evaluated.
Based on the selected object type, the list of available properties
displays only the properties applicable to the object type.
Symptom Type Select Properties from the Symptom Type drop-down list.
Select Specific Object If a property is not listed in the common properties list, based on
the selected based object type, use Select Object to inspect the
properties of a selected object so that you can locate the property
that you must use to create the symptom. Even though you select
a property for a specific object, the symptom definition is applicable
to all objects with that property in your environment.
Search Use a word search to limit the number of items that appear in the
list.
Property list List of properties for the selected base object type.
Click and drag the property to the left pane.
Symptom Definition workspace
The properties are configured values that are compared to the value you specify. You can configure a single property symptom or add
multiple symptoms.
For example, if you need an alert when a particular property, such as Memory Hot Add, is no longer at the value required, you can
configure a symptom and add it to an alert definition.
Property Configure the options:
• Symptom name. Name of the symptom as it appears in the
symptom list when configuring an alert definition, as it appears
when the alert is generated, and when viewing triggered
symptoms.
• Condition. Determines how the value you specify in the value
text box is compared to the current value of the property for an
object when the symptom definition is evaluated.
• Value. Value that the condition evaluates.
• Criticality. Severity of the symptom when it is triggered.
• Wait Cycle. The trigger condition should remain true for this
number of collection cycles before the symptom is triggered.
The default value is 1, which means that the symptom is
triggered in the same collection cycle when the condition
became true.
• Cancel Cycle. The symptom is canceled after the trigger
condition is false for this number of collection cycles after which
the symptom is cancelled. The default value is 1, which means
that the symptom is canceled in the same cycle when the
condition becomes false.
VMware by Broadcom  3180

---
## page 3181

 VMware Cloud Foundation 9.0
Option Description
• Evaluate on instanced properties. Select this check box so that
the system evaluates the object level symptom as well as the
instance level symptom. For example, for memory usage, when
the check box is not selected, the symptom is triggered based
on the object's memory usage. However, if you select the check
box, the system also evaluates memory usage of each of the
cores. If any of the cores is found to be crossing the threshold,
the symptom is triggered.
• Drop instances to exclude. To exclude specific instanced
properties from the symptom, drag the property instances from
the right pane. If you cannot locate the property instance you
want to exclude, you can search for it in another object that
uses the property by clicking Select Specific Object next to
the search box.
3. Click Save.
Message Event Symptoms
Message event symptoms are based on events received as messages from a component of VCF Operations or from an
external monitored system through the system's REST API. You define symptoms based on message events to include in
alert definitions that use these symptoms. When the configured symptom condition is true, the symptom is triggered.
The adapters for the external monitored systems and the REST API are inbound channels for collecting events from
external sources. Adapters and the REST server both run in the system. The external system sends the messages, and
VCF Operations collects them.
You can create message event symptoms for the supported event types. The following list is of supported event types with
example events.
• System Performance Degradation. This message event type corresponds to the EVENT_CLASS_SYSTEM and
EVENT_SUBCLASS_PERFORM_DEGRADATION type and subtype in the VCF Operations API SDK.
• Change. The VMware adapter sends a change event when the CPU limit for a virtual machine is changed from
unlimited to 2 GHz. You can create a symptom to detect CPU contention issues as a result of this configuration
change. This message event type corresponds to the EVENT_CLASS_CHANGE and EVENT_SUBCLASS_CHANGE
type and subtype in the VCF Operations API SDK.
• Environment Down. The VCF Operations adapter sends an environment down event when the collector component is
not communicating with the other components. You can create a symptom that is used for internal health monitoring.
This message event type corresponds to the EVENT_CLASS_ENVIRONMENT and EVENT_SUBCLASS_DOWN type
and subtype in the VCF Operations API SDK.
• Notification. This message event type corresponds to the EVENT_CLASS_NOTIFICATION and
EVENT_SUBCLASS_EXTEVENT type and subtype in the VCF Operations API SDK.
Where You Find Message Event Symptoms
To manage symptoms based on message events, from the left menu, click Infrastructure Operations >  Configurations,
and then click the Symptom Definitions tile. Select the Message Event  tab.
You can also define symptoms as you are defining alerts in the Alert Definition Workspace.
The Message Event Symptom Definitions is a list of the message event-based symptoms defined in your VCF Operations
environment. You use the information in the list to evaluate the defined message events and to determine if you want to
add, edit, or clone symptoms.
VMware by Broadcom  3181

---
## page 3182

 VMware Cloud Foundation 9.0
Option Description
Toolbar options Use the toolbar options to manage your symptoms. You can select
multiple symptoms using Ctrl+click or Shift+click.
• Add. Add a symptom definition.
Click the horizontal ellipsis to perform the following actions.
• Edit. Modify the selected symptom definition. Any changes you
make affect the alert definitions that include this symptom. You
cannot edit a symptom that manages a badge.
• Delete. Remove the selected symptom definition. You cannot
delete an alert that is used in an alert definition. To delete a
symptom, you must first remove it from the alert definitions in
which it is used. You cannot delete a symptom that manages a
badge.
• Clone. Create a copy of the selected symptom definition.
• Export and Import. Export the file as xml from one VCF
Operations so that you can import the file on another instance.
When you import the file, if you encounter a conflict, you can
override the existing file or not import the new file.
Filter options Limits the list based on the text you type.
You can also sort on the columns in the data grid.
Name Descriptive name of the symptom.
Adapter Type Adapter type for which the symptom is configured.
Object Type Base object type against which the symptom is defined.
Event Type Defined event classification type.
Operator Operator used to compare the message from the incoming event
against the event message specified in the symptom.
Event Message Text string that is compared to the message in the incoming event
using the specified operator.
Criticality Severity of the symptom when it is triggered.
Defined By Indicates whether the symptom was created by a user or provided
with a solution adapter.
Last Modified Displays the date on which the symptom was last modified.
Modified By Displays the name of the user who last modified the symptom.
Defining Message Events
You can define message event systems in VCF Operations so that you can create one or more of the symptoms that you
can add to an alert definition. A message event symptom is triggered when a message in an incoming event matches the
text string in the symptom, based on the specified operator.
1. To define symptoms based on message events, from the left menu, click Infrastructure Operations > 
Configurations, and then click the Symptom Definitions tile.
2. Select the Message Event tab, and then click Add.
Note:
VMware by Broadcom  3182

---
## page 3183

 VMware Cloud Foundation 9.0
3. Enter the following details.
Table 991: Symptoms Workspace Options for Message Events
Option Description
Based Object Type Object against which the symptom is evaluated.
Symptom Type Displays the symptom type as Message Event.
Select the Type of Event Select the type of incoming event against which you are matching
the events as they arrive. The incoming event must contain the
following type and subtype combinations.
• System Degradation
• Change
• Environment
• Notification
• Data Availability
• Collector Down
• Object Error
Click and drag the message event to the left pane.
Symptom Definition workspace
The Message Event text string is compared to the message in the incoming event by using the specified operator. You can configure a
single message event symptom or add multiple symptoms.
For example, the VMware adapter sends a change event when the CPU limit for a virtual machine was changed from unlimited to 2
GHz. You can create a symptom to detect CPU contention issues as a result of this configuration change.
Message Event Configure the options:
• Symptom name. Name of the symptom as it appears in the
symptom list when configuring an alert definition, as it appears
when the alert is generated, and when viewing triggered
symptoms.
• Condition. Determines how the value you specify in the value
text box is compared to the current value of the property for an
object when the symptom definition is evaluated.
• Value. Value that the condition evaluates.
• Criticality. Severity of the symptom when it is triggered.
4. Click Save.
Fault Symptoms
Fault symptoms are based on events published by monitored systems. VCF Operations correlates a subset of these
events and delivers them as faults. Faults are intended to signify events in the monitored systems that affect the
availability of objects in your environment. You define symptoms based on faults to include in alert definitions that use
these symptoms. When the configured symptom condition is true, the symptom is triggered.
You can create fault symptoms for the supported published faults. Some object types have multiple fault definitions from
which to choose, while others have no fault definitions.
If the adapter published fault definitions for an object type, you can select one or more fault events for a given fault while
you define the symptom. The symptom is triggered if the fault is active because of any of the chosen events. If you do not
select a fault event, the symptom is triggered if the fault is active because of a fault event.
VMware by Broadcom  3183

---
## page 3184

 VMware Cloud Foundation 9.0
Where You Find Fault Symptoms
To manage symptoms based on fault message events, from the left menu, click Operations >  Configurations, and then
click the Symptom Definitions tile. Select the Fault tab.
You can also define symptoms as you are defining alerts in the Alert Definition Workspace.
The Fault Symptom Definitions is a list of the fault-based symptoms defined in your VCF Operations environment. You
use the information in the list to evaluate the defined fault message events and to determine whether to add, edit, or clone
symptoms.
Option Description
Toolbar options Use the toolbar options to manage your symptoms. You can select
multiple symptoms using Ctrl+click or Shift+click.
• Add. Add a symptom definition.
Click the horizontal ellipsis to perform the following actions.
• Edit. Modify the selected symptom definition. Any changes you
make affect the alert definitions that include this symptom. You
cannot edit a symptom that manages a badge.
• Delete. Remove the selected symptom definition. You cannot
delete an alert that is used in an alert definition. To delete a
symptom, you must first remove it from the alert definitions in
which it is used. You cannot delete a symptom that manages a
badge.
• Clone. Create a copy of the selected symptom definition.
• Export and Import. Export the file as xml from one VCF
Operations so that you can import the file on another instance.
When you import the file, if you encounter a conflict, you can
override the existing file or not import the new file.
Filter options Limits the list based on the text you type.
You can also sort on the columns in the data grid.
Name Descriptive name of the symptom.
Adapter Type Adapter type for which the symptom is configured.
Object Type Base object type against which the symptom is defined.
Fault Selected fault based on object type.
Defined By Indicates whether the symptom was created by a user or provided
with a solution adapter.
Last Modified Displays the date on which the symptom was last modified.
Modified By Displays the name of the user who last modified the symptom.
Defining Fault Symptoms
You can define fault symptoms in VCF Operations that are based on events published by the monitored systems, so that
you can add one or more symptoms to an alert definition. A fault symptom is triggered when a fault is active on the base
object because of the occurrence of any of the fault events selected in the symptom definition.
1. To define symptoms based on fault message events, from the left menu, click Infrastructure Operations > 
Configurations, and then click the Symptom Definitions tile.
2. Select the Fault tab and then, click Add.
VMware by Broadcom  3184

---
## page 3185

 VMware Cloud Foundation 9.0
3. Enter the following details.
Option Description
Based Object Type Object against which the symptom is evaluated.
Symptom Type Displays the symptom type as Fault.
Fault Definitions Select the fault definition for the selected base object type. Some
object types do not have fault definitions, and other types have
multiple definitions.
Click and drag the fault definition to the left pane.
Symptom Definition workspace
The fault events are published events from monitored systems. You can configure a single fault event symptom or add multiple
symptoms.
For example, if your base object is host and you drag the Hardware sensor fault for unknown type fault definition, you then select one
of two text strings indicating a fault.
Fault Symptom Configure the options:
• Symptom name. Name of the symptom as it appears in
the symptom list when configuring an alert definition, as
it appears when the alert is generated, and when viewing
triggered symptoms.
• Value. Select one or more fault events that activate the fault.
If you do not select a string, then any of the provided strings
are evaluated.
• Criticality. Severity of the symptom when it is triggered.
4. Click Save.
Logs Symptoms
You can create symptoms in VCF Operations based on events ingested by VCF Operations for logs. You can then
configure alerts to use the log based symptoms. Previously you had to create and manage alerts in VMware Aria
Operations for Logs and VMware Aria Operations separately. Now, VCF Operations provides a unified experience to
define log based symptoms and alerts. The prerequisite is the integration between VCF Operations for logs and VCF
Operations. For more details, see Configuring and Analyzing Logs.
When you define a symptom in VCF Operations, an alert definition is created in VCF Operations for logs. You must define
the query, trigger conditions and the objects on which these conditions must be met. Since VCF Operations for logs
does not have a concept of objects, the object scope for the symptom definition is limited to vCenter objects. To define
symptoms for other types of objects, use the Log Fallback Object option.
When the alert is triggered in VCF Operations for logs, an event is generated in VCF Operations. VCF Operations
processes this event based on the corresponding symptom definition and triggers the alert.
Note:
It can take up to two minutes for the alert definition to be created in VCF Operations for logs after you define a log based
symptom in VCF Operations. You cannot modify the alert definition in VCF Operations for logs but can modify it in VCF
Operations. For more information, see, Creating Alert Definitions.
To define log based symptoms, click Infrastructure Operations > Configurations, and then click the Symptom
Definitions tile. Select the Logs tab. Click the ADD button to define a Logs based symptom.
VMware by Broadcom  3185

---
## page 3186

 VMware Cloud Foundation 9.0
Option Description
Base Object Type
Since the alert definition is triggered in VCF Operations for logs ,
only the following limited set of objects can be selected. They are:
• vCenter
– Host System
– vCenter
– Virtual Machine
If you want to create a symptom definition for other object types,
then select:
• Container
– Log Fallback Object
Symptom Type Drag and drop the Logs symptom type to the left workspace of the
page to continue to the definition.
Symptom Trigger Condition
1. Provide a name for the symptom.
2. Define the criticality of the event based on the function and
condition.
3. Select a time period and group the symptom by static or
extracted fields.
4. Select a query from the drop-down list or enter a text to search
for to filter by.
5. Optionally, select a partition to include in the scope of the
search.
6. Optionally, add more filters.
7. Click SAVE
Once you define a symptom, you can create an alert for the same object for which you created the symptom. To define
an alert, go to Infrastructure Operations > Configurations, and then click the Alerts Definitions. For more information,
see, Creating Alert Definitions.
Understanding Negative Symptoms for VCF Operations Alerts
Alert symptoms are conditions that indicate problems in your environment. When you define an alert, you include
symptoms that generate the alert when they become true in your environment. Negative symptoms are based on the
absence of the symptom condition. If the symptom is not true, the symptom is triggered.
To use the absence of the symptom condition in an alert definition, you negate the symptom in the symptom set.
All defined symptoms have a configured criticality. However, if you negate a symptom in an alert definition, it does not
have an associated criticality when the alert is generated.
All symptom definitions have a configured criticality. If the symptom is triggered because the condition is true, the
symptom criticality will be the same as the configured criticality. However, if you negate a symptom in an alert definition
and the negation is true, it does not have an associated criticality.
When negative symptoms are triggered and an alert is generated, the effect on the criticality of the alert depends on how
the alert definition is configured.
The following table provides examples of the effect negative symptoms have on generated alerts.
VMware by Broadcom  3186

---
## page 3187

 VMware Cloud Foundation 9.0
Table 992: Negative Symptoms Effect on Generated Alert Criticality
Alert Definition Criticality Negative Symptom
Configured Criticality
Standard Symptom Configured
Criticality
Alert Criticality When
Triggered
Warning One Critical Symptom One Immediate Symptom Warning. The alert criticality
is based on the defined alert
criticality.
Symptom Based One Critical Symptom One Warning Symptom Warning. The negative
symptom has no associated
criticality and the criticality
of the standard symptom
determines the criticality of
the generated alert.
Symptom Based One Critical Symptom No standard symptom included Info. Because an alert must
have a criticality and the
negative alert does not have
an associated criticality,
the generated alert has a
criticality of Info, which is
the lowest possible criticality
level.
Recommendations in VCF Operations
Recommendations are probable solutions for an alert generated. You can create a library of recommendations that
include instructions to your environment administrators or actions that they can run to resolve an alert.
Recommendations provide your network engineers or virtual infrastructure administrators with information to resolve
alerts.
Depending on the knowledge level of your users, you can provide more or less information, including the following
options, in any combination.
• One line of instruction.
• Steps to resolve the alert on the target object.
• Hyperlink to a Web site, runbook, wiki, or other source.
• Action that makes a change on the target object.
When you define an alert, provide as many relevant action recommendations as possible. If more than one
recommendation is available, arrange them in priority order so that the solution with the lowest effect and highest
effectiveness is listed first. If no action recommendation is available, add text recommendations. Be as precise as possible
when describing what the administrator should do to fix the alert.
Where You Find Recommendations
To define recommendations, click Infrastructure Operations >  Configurations, and then click the Recommendations
tile. .
VMware by Broadcom  3187

---
## page 3188

 VMware Cloud Foundation 9.0
You can also define recommendations when you create an alert definition.
Option Description
Toolbar options Use the toolbar options to manage your recommendations.
• Add. Add a recommendation.
Click the horizontal ellipsis to perform the following actions.
• Edit. Modify the selected recommendation.
• Delete. Remove the selected recommendation.
• Clone. Create a copy of the selected recommendation so
that you can create a new recommendation that uses the
current one.
• Export. Downloads the recommendations.
• Import. Allows you to import recommendations. To import:
– Click the Import option from the horizontal ellipsis.
– Click Browse and select the file to import.
– Select if you want to Overwrite or Skip the file in case of a
conflict.
– Click Import to import the recommendation, and click
Done.
Quick Filter Limits the list based on the text you type.
You can also sort on the columns in the data grid.
Description Displays the recommendation text that is provided when the
alert is generated.
Click this link to view the Details Page. On this page, you
can view the alert definitions assigned for a particular
recommendation. To remove the selected recommendation
from all alert definitions, click Edit and then, in the Edit
Recommendation page, click Remove from all.
Action If the recommendation includes running an action, the name of
the action is displayed.
Alert Definitions Displays the number of alert definitions assigned for a particular
recommendation.
VMware by Broadcom  3188

---
## page 3189

 VMware Cloud Foundation 9.0
Option Description
Defined By Indicates whether the recommendation was created by a user or
provided with a solution adapter.
Last Modified Displays the date on which the recommendation was last
modified.
Modified By Displays the name of the user who last modified the
recommendation.
Defining Recommendations for Alerts
You can create recommendations that are solutions to alerts generated. The recommendations are intended to ensure
that your network operations engineers and virtual infrastructure administrators can respond to alerts as quickly and
accurately as possible. A recommendation can contain links to useful Web sites or local runbooks, instructions as text, or
actions that you can initiate from VCF Operations.
1. To define recommendations, from the left menu, click Infrastructure Operations >  Configurations, and then click
the Recommendations tile.
2. Click Add and enter the following details.
Option Description
Description Enter the description of what must be done to resolve the
triggered alert.
The description can include steps a user must take to resolve
the alert or it might be instructions to notify a virtual infrastructure
administrator.
This is a text field.
Create a hyperlink To create a hyperlink, enter a description, select the text, and click
the Hyperlink icon to make the text a hyperlink to a Website or
local wiki page.
Action (Optional)
Adapter Type Select an adapter type from the drop-down list to narrow down the
list of actions displayed in the Actions field.
Action You can add an action as a method to resolve a triggered
symptom or a generated alert. Actions must already be
configured.
You must provide text in the text box to describe the action before
you can save the recommendation.
3. Click Save.
These actions, named Delete Unused Snapshots for Datastore Express and Delete Unused Snapshots
for VM Express appear. However, they can only be run in the user interface from an alert whose first recommendation
is associated with this action. You can use the REST API to run these actions.
The following actions are also not visible except in the alert recommendations:
• Set Memory for VM Power Off Allowed
• Set CPU Count for VM Power Off Allowed
• Set CPU Count and Memory for VM Power Off Allowed
These actions are intended to be used to automate the actions with the Power Off Allowed flag set to true.
VMware by Broadcom  3189

---
## page 3190

 VMware Cloud Foundation 9.0
Notifications in VCF Operations
Notifications are alert notifications that meet the filter criteria in the notification rules before they are sent outside VCF
Operations. You can configure notification rules for the supported outbound alerts so that you can filter the alerts that are
sent to the selected external system.
You can use the notifications list to manage your rules and then use the notification rules to limit the alerts that are sent to
the external system. To use notifications, the supported outbound alert plug-ins must be added and running.
With notification rules, you can limit the data that is sent to the following external systems.
• Standard Email. You can create multiple notification rules for various email recipients based on one or more of the filter
selections. If you add recipients but do not add filter selections, all the generated alerts are sent to the recipients.
• REST. You can create a rule to limit alerts that are sent to the target REST system so that you do not need to
implement filtering on that target system.
• SNMP Trap. You can configure VCF Operations to log alerts on an existing SNMP Trap server in your environment.
• Log File. You can configure log alerts to a file on each of your VCF Operations nodes.
You configure notification options to specify which alerts are sent out for the Standard Email, REST, SNMP, and Log
File outbound alert plug-ins. For the other plug-in types, all the alerts are sent when the target outbound alert plug-in is
activated.
The most common outbound alert plug-in is the Standard Email plug-in. You configure the Standard Email plug-in to send
notifications to one or more users when an alert is generated that meets the criteria you specify in the notification settings.
Where You Find Notifications
To manage your notifications, from the left menu, click Infrastructure Operations > Configurations, and then click the
Notifications tile.
Note:  To use notifications, the supported outbound alert plug-ins must be added and running.
Option Description
Toolbar options Use the toolbar options to manage your notification rules.
• Add. Opens the Add Rule dialog box where you configure the filtering options for the notification rule.
Click the horizontal ellipsis to perform the following actions.
• Delete. Removes the selected rule.
• Deactivate or Activate. Deactivates or activates the selected rule(s).
• Export or Import. Export the selected notifications to a ".xml" file so that you can import it on another
VCF Operations instance.
VMware by Broadcom  3190

---
## page 3191

 VMware Cloud Foundation 9.0
Option Description
Quick Filter (Action Name) Limits the list to actions matching the filter. You can filter by:
• Rule Name
• Instance
• Status
• Modified By
Rule Name Name you assigned when you created the notification rule. Click the vertical ellipsis to perform the
following actions.
• Edit. Allows you to edit the selected rule.
• Clone. Allows you to clone an existing notification rule and edit the attributes of the cloned notification
rule. You can create multiple alert notification rules so that you can send the same alert notifications to
different outbound settings.
Note:  You can clone only one alert notification rule at a time.
• Delete. Removes the selected rule.
• Deactivate or Activate. Deactivates or activates the selected rule.
• Export. Downloads the notification setting.
Description Description of the notification rule.
Instance Name of the configured outbound alert instance for the notification rule.
Instances are configured as part of the outbound alerts and can indicate different email servers or sender
addresses for alert notifications.
Outbound Method Displays the type of the outbound method that is configured.
Payload Template Displays the payload template that is used.
Status Displays if the rule is activated or not.
Email Address If the rule is for standard email notifications, the alert recipient email addresses are listed.
Object Name If the rule specifies a notification for a particular object, the object name is listed.
Children If the rule specifies a notification for a particular object and selected child objects, the child object types
are listed.
Last Modified Displays the date on which the rule was last modified.
Modified By Displays the name of the user who last modified the rule.
Creating Notification Rules for Alerts
You add, manage, and edit your notification rules in VCF Operations. To send notifications to a supported system, you
must configure and activate the settings for outbound alerts.
Before you can create and manage your notification rules, you must configure the outbound alert plug-in instances. For
details on configuring outbound plug-ins, see Adding Outbound Notification Plug-Ins.
You use the Notifications page to manage your alert notification rules. The rules determine which VCF Operations alerts
are sent to the supported target systems.
Notification rules are filters that limit the data sent to external systems by using outbound alert plug-ins that are supported,
configured, and running. Rather than sending all alerts to all your email recipients, you can use notification rules to send
specific alerts. For example, you can send health alerts for virtual machines to one or more of your network operations
engineers. You can send critical alerts for selected hosts and clusters to the virtual infrastructure administrator for those
objects. Before you can create and manage notification rules, you must configure the outbound alert plug-in instances.
1. To manage your notifications, from the left menu, click Infrastructure Operations > Configurations, and then click
the Notifications tile. On the toolbar, click Add to add a rule, or click the vertical ellipsis and select Edit to edit the
selected rule.
VMware by Broadcom  3191

---
## page 3192

 VMware Cloud Foundation 9.0
2. Enter the following notification details.
Option Description
Name Name of the rule that you use to manage the rule instance.
Description Description of the rule.
Notification Status Either activate or deactivate a notification setting. Deactivating
a notification will stop the alert notification for that setting and
activating it will activate the alert notification.
Advanced Settings
Notification Type Select Alert from the drop-down menu.
Note:  Select Action as your Notification Type if you want to
create Workload Placement (WLP) Action based notification.
For details, see Creating Notification Rules for Notification Type
'Action'.
3. Click Next.
4. Define criteria for the notification rule.
Option Description
Object Scope
Criteria Object Type, Object, Tags, Applications, and Tiers for which you
are filtering the alert notifications.
After you select the type, you select the specific instance. For
example, if you select Object, you then select the specific object
by name and determine whether to include any child objects.
Alert Scope
Category Alert Types/Subtypes, Alert Impact, or Alert Definition that triggers
the alert.
After you select the criteria, you can configure the specific
selections associated with the criteria. For example, if you select
Alert Definition, you then select the alert definition that limits
the data to alerts with this definition. You can select multiple alert
definitions as conditions for a notification to trigger.
Criticality Defined criticality of the alert that results in the data being sent to
an external system. For example, if you select Critical, then the
data that is sent to the external system must also be labeled as
critical.
Control State State of the alert, either opened, assigned, or suspended.
Notify On
Status Current state of the alert, either canceled, updated, or new.
Notification Heartbeat
Heartbeat Set this to Active if you want to send repeat notifications for
the active alerts. The frequency of the notification depends on
the collection interval set for the adapter whose object is being
evaluated. By default, this checkbox is not selected.
Note:  Setting this option to Active can cause a potential surge in
the notifications that are generated.
Advanced Filters: By Collector
VMware by Broadcom  3192

---
## page 3193

 VMware Cloud Foundation 9.0
Option Description
Collector/Group Select a collector or group if you want to receive notifications for
the objects that receive data from the selected collector/group.
Note:  If you do not define any alert filters in the Define Criteria tab, then the notification will be sent for all the alerts without applying
any conditions for the object scope, alert scope, or alert state.
5. Click Next.
6. Select the outbound method that you want to use to send your notification.
Option Description
Outbound Method • Select Plug-In Type: Type of plugin. Select one of the
outbound alert plug-in types: Log File Plugin, Rest Notification
Plugin, Standard Email Plugin, SNMP Trap Plugin, Webhook
Notification Plugin, Slack Plugin, and Service-Now Notification
Plugin.
Note:  The Rest Notification Plugin is deprecated in this
release. Although you still can configure the Rest Notification
Plugin, you will not be able to use a custom template for it. You
can use the Webhook Notification Plugin instead of the Rest
Notification Plugin.
• Select Instance: Select the configured instance for the type of
plug-in.
• Create New Instance: You can also create a new outbound
instance for the plug-in type you select.
For details, see Adding Outbound Notification Plug-Ins.
7. Click Next.
8. Select the payload template.
Option Description
Payload Template Select the payload template that you want to include in the
notification. Each plug-in has its default template and you can
select the default template if no customization is required. The
template includes additional information about the alert or the
object that is displayed in the notification. You can also customize
your payload for a Webhook Notification Plugin. For details on
creating payload templates, see Creating Payload Templates for
Outbound Plugins.
The values in this tab differ based on the outbound plug-in you have selected in the previous step.
Outbound Method -Standard Email Plugin If you are configuring notifications for standard email, you can add
recipients and associated information.
• Recipient(s). Enter the email addresses of the individuals to
whom you are sending email messages that contain alert
notifications. If you are sending to more than one recipient, use
a semicolon (;) between addresses.
• Cc Recipients. Enter the email addresses of the individuals
that have to be cc'd for the email.
• Bcc Recipients. Enter the email addresses of the individuals
that have to be bcc'd for the email.
• Notify again. Number of minutes between notifications
messages for active alerts. Leave the text box empty to send
only one message per alert.
VMware by Broadcom  3193

---
## page 3194

 VMware Cloud Foundation 9.0
Option Description
• Max Notifications. Number of times to send the notification for
the active alert. Leave the text box empty to send only one
message per alert.
• Delay to notify. Number of minutes to delay before sending
a notification when a new alert is generated. For example,
if the delay is 10 minutes and a new alert is generated, the
notification is not sent for 10 minutes. If the alert is canceled in
those 10 minutes, the notification is not sent. The notification
delay reduces the number of notifications for alerts that are
canceled during that time.
• Description. Enter the text to include in the email message. For
example, the Attention Host Management team.
Outbound Method - Service-Now Notification Plugin If you are configuring notifications for a Service-Now notification
plug-in, you can add instances and associated information.
• Caller. Enter the name of the person who reported the incident
or who is affected by the incident.
• Category. Specify the category to which the incident belongs.
• Sub Category. Specify the sub-category to which the incident
belongs.
• Business Service. Specify the business service of the incident.
• Contact Type. Enter the contact type.
• State. Enter the incident state in digits.
• Resolution Code. Enter the resolution code for the incident.
• Resolution notes. Enter the resolution notes for the incident.
• On hold reason. Enter the reason as to why the incident is on
hold.
• Impact. Set the incident impact in digits. Impact measures the
business criticality of the affected service.
• Urgency. Set urgency for the incident in digits. Urgency defines
the number of days taken to resolve an incident.
• Priority. Enter the priority for the incident. Priority defines the
sequence in which the incident must be resolved.
• Assignment Group. Enter the assignment group for the
incident.
• Assigned To. Enter the details of the person to whom the
incident is assigned.
• Severity. Set the severity for the incident in digits.
• Upon Approval. Specify the next steps to be taken upon
incident approval.
• Problem. Enter the details of the related problem if it exists.
• Cause by change. Enter the change request which triggered
the incident.
• Change Request. Enter the details for the related change list if
it exists.
Outbound Method - Slack Plugin If you are configuring notifications for a Slack plugin, add the
Webhook URL of Slack. For example, the Webhook URL is in the
format: https://hooks.slack.com/services/T00000
000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX.
Create and authorize an app within Slack to obtain the Webhook
URL. For details on creating and authorizing an app within Slack,
refer to the Slack Documentation.
VMware by Broadcom  3194

---
## page 3195

 VMware Cloud Foundation 9.0
Option Description
Once you have created the notification rule, the alerts are
displayed within that particular Slack channel with a link to the
alert. Click the link to view the details of the alert on the Object
Summary page.
9. Click Next to test the notification
10. In the Test Notification tab, click Initiate Process to initiate the notification configuration validation process.
11. If you activate the Filter the alert definitions and objects based on criteria outlined in the Define Criteria section
option, then the alert definitions and objects displayed below are based on the criteria outlined in the Define Criteria
section.
12. Select an alert definition and an object for validation.
13. Click Validate Configuration.
– Notification Validation Steps: View the steps involved in validating the notification configuration. The steps also
indicate an error, if any. The validation steps differ based on the selected Outbound method.
Outbound Method Validation Steps
Log File Plugin • Validate Criteria
• Permissions
• File Created
Standard Email Plugin • Validate Criteria
• Establish Endpoint Connection
• Certificates
• Authentication
• Send Notification
Note:
The Standard Email Plugin does not provide a response that can
be validated.
SNMP Trap Plugin • Validate Criteria
• Establish Endpoint Connection
• Send Notification
Note:
The SNMP Trap Plugin does not provide a response that can be
validated.
Webhook Notification Plugin • Validate Criteria
• Establish Endpoint Connection
• Certificates
• Authentication
• Send Notification
• Endpoint Receives Notification
Slack Plugin • Validate Criteria
• Establish Endpoint Connection
• Authentication
• Send Notification
• Endpoint Receives Notification
ServiceNow Notification Plugin • Validate Criteria
• Establish Endpoint Connection
• Authentication
• Send Notification
VMware by Broadcom  3195

---
## page 3196

 VMware Cloud Foundation 9.0
Outbound Method Validation Steps
• Endpoint Receives Notification
– Response: The Response tab in the right pane displays if the test passed successfully or if there were any errors.
– Body: Displays the content of the notification.
14. Click Create to create the notification rule. You can view the rule you created under Alerts > Notifications.
Creating Notification Rules for Notification Type 'Action'
You can create and manage Workload Placement (WLP) Action based notification.
You can configure actions for which you want to receive notifications. Once configured, notifications are sent indicating the
successful, failed, or timed out WLP action.
Note:  The notifications are sent once the WLP Virtual Machine movement task is completed irrespective of its status.
Before you can create and manage your notification rules, you must configure the Webhook Notification Plugin. For
details, see Add a Webhook Notification Plugin for Outbound Instance.
To create notification rules for WLP action:
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Notifications tile. On the
toolbar, click Add to add a rule, or click the vertical ellipsis and select Clone to clone the selected rule.
Note:  You cannot change the Notification Type while editing a selected notification rule,
2. Enter the following notification details.
Option Description
Name Name of the rule that you use to manage the rule instance.
Description Description of the rule.
Notification Status Either activate or deactivate a notification setting. Deactivating a
notification will stop the notification for that setting and activating it
will activate the notification.
Advanced Settings
Notification Type Select Action from the drop-down menu.
3. Click Next.
4. Define criteria for the notification rule.
Option Description
Object Scope: Select set of Objects for which you want to receive notifications.
Criteria Select the Criteria as Object from the drop-down menu.
Search for a specific object by name and determine if you want
to include any child or descendant objects, and then add one or
more child/descendant objects.
The action triggers on ANY of the selected objects:
Notify On
Status Select the action status for which you want to receive notification.
You can receive notification for Succeeded, Failed, and Timed
Out statuses.
5. Click Next.
VMware by Broadcom  3196

---
## page 3197

 VMware Cloud Foundation 9.0
6. Select the outbound method that you want to use to send your notification.
Option Description
Outbound Method • By default, the outbound method supported is Webhook
Notification Plugin.
• Select Instance: Select the configured instance for the
Webhook plug-in.
• Create New Instance: You can also create a new outbound
instance for the Webhook plug-in type. For details, see Add a
Webhook Notification Plugin for Outbound Instance.
7. Click Next.
8. Select the payload template.
Option Description
Payload Template Select the Webhook payload template that you want to include in
the notification. There is a Default WLP Action Webhook Template
and you can select the default template if no customization is
required. You can also customize your payload for a Webhook
Notification Plugin. For details on creating payload templates, see
Creating Payload Templates for Outbound Plugins.
9. Click Next to test the notification
10. In the Test Notification tab, click Initiate Process to initiate the notification configuration validation process.
11. If you activate the Filter the objects based on criteria outlined in the Define Criteria section option, then the
objects displayed below are based on the criteria outlined in the Define Criteria section.
12. Select an object for validation.
13. Click Validate Configuration.
– Notification Validation Steps: View the steps involved in validating the notification configuration. The steps also
indicate an error, if any. The validation steps differ based on the selected Outbound method.
Outbound Method Validation Steps
Webhook Notification Plugin • Validate Criteria
• Establish Endpoint Connection
• Certificates
• Authentication
• Send Notification
• Endpoint Receives Notification
– Response: The Response tab in the right pane displays if the test passed successfully or if there were any errors.
– Body: Displays the content of the notification.
14. Click Create to create the notification rule. You can view the rule you created under Alerts > Notifications.
User Scenario: Create a Email Alert Notification
As a virtual infrastructure administrator, you need to send email notifications to your advanced network engineers when
critical alerts are generated for mmbhost object, the host for many virtual machines that run transactional applications,
where no one has yet taken ownership of the alert.
• Ensure that you have at least one alert definition for which you are sending a notification. For an example of an alert
definition, see Create an Alert Definition for Department Objects.
VMware by Broadcom  3197

---
## page 3198

 VMware Cloud Foundation 9.0
• Ensure that at least one instance of the Standard Email Plug-In is configured and running. See Add a Standard Email
Plug-In for VCF Operations Outbound Alerts.
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Notifications tile.
2. Click Add to add a notification rule.
3. In the Name text box, enter a name similar to Unclaimed Critical Alerts for mmbhost.
4. Set the Notification Status, you can either activate or deactivate a notification setting. Disabling a notification stops
the alert notification for that setting and enabling it activates it again.
5. In the Define Criteria tab, select the objects and alerts for which you want to receive notifications.
a) From the Criteria drop-down menu, select Object.
b) Locate and select the object from the list.
6. Configure the Alert Scope.
a) From the Category drop-down menu, select Alert Impact, and from the adjacent drop-down menu, select Health.
b) From the Criticality drop-down menu, select Critical.
7. In the Notify On section, select Open from the Status drop-down menu.
The Open state indicates that no engineer or administrator has taken ownership of the alert.
8. In the Set Outbound Method tab, select Standard Email Plug-In from the Outbound method drop-down menu, and
then select the configured instance of the email plug-in.
9. In the Select Payload Template tab, configure the email options.
a) In the Recipients text box, enter the email addresses of the members of your advance engineering team,
separating the addresses with a semi-colon (;).
b) To send a second notification if the alert is still active after a specified amount of time, enter the number of minutes
in the Notify again text box.
c) Type number of notifications that are sent to users in the Max Notifications text box.
10. Click Create.
You created a notification rule that sends an email message to the members of your advance network engineering team
when any critical alerts are generated for the mmbhost object and the alert is not claimed by an engineer. This email
reminds them to look at the alert, take ownership of it, and work to resolve the triggering symptoms.
Notifications - User Scenario: Create a Webhook Alert Notification
As a virtual infrastructure administrator, you need to send alerts in JSON or XML to a Webhook with any endpoint
REST API that accepts these messages. You want only alerts where the virtualization alerts that affect availability alert
types to go to an external application. You can then use the provided information to initiate a remediation process in
that application to address the problem indicated by the alert. The notification configuration limits the alerts sent to the
outbound alert instance to those matching the notification criteria.
• Ensure that you have at least one alert definition for which you are sending a notification. For an example of an alert
definition, see Create an Alert Definition for Department Objects.
• Ensure that at least one instance of the Webhook Notification Plugin is configured and running. See Add a Webhook
Notification Plugin for Outbound Instance.
VMware by Broadcom  3198

---
## page 3199

 VMware Cloud Foundation 9.0
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Notifications tile.
2. Click Add to add a notification rule.
3. In the Name text box, enter a name similar to Virtualization Alerts for Availability.
4. Set the Notification Status, you can either activate or deactivate a notification setting. Disabling a notification stops
the alert notification for that setting and enabling it activates it again.
5. In the Define Criteria tab, select the objects and alerts for which you want to receive notifications.
a) From the Criteria drop-down menu, select Object.
b) Locate and select the object from the list.
6. Configure the Alert Scope.
a) From the Category drop-down menu, select Alert Type, and from the Alert Types/Subtypes menu, select
Availability under Virtualization/Hypervisor Alerts.
b) From the Criticality drop-down menu, select Warning.
7. In the Notify On section, select New from the Status drop-down menu.
The New status indicates that the alert is new to the system and not updated.
8. In the Set Outbound Method tab, select Webhook Notification Plugin from the Outbound method drop-down
menu, and then select the configured instance of the Webhook plugin.
9. In the Select Payload Template tab, select the Default Webhook Template.
10. Click Create.
You created a notification rule that sends the alert text to the target REST-activated system. Only the alerts where the
configured alert impact is Virtualization/Hypervisor Availability and where the alert is configured as a warning are sent to
the target instance using the Webhook plugin.
You created a notification rule that sends the alert text to the target Webhook system.
Outbound Settings in VCF Operations
You use the Outbound Settings to manage your communication settings so that you can send information to users or
applications outside of VCF Operations.
You manage your outbound options from this page, including adding or editing outbound plug-ins, and turning the
configured plug-ins on or off. When activated, the plug-in sends a message to users as email notifications, or sends a
message to other applications.
Outbound plug-in settings determine how the supported external notification systems connect to their target systems. You
configure one or more instances of one or more plug-in types so that you can send data about generated notifications
outside of VCF Operations.
You configure each plug-in with the required information, including destination locations, hosts, ports, user names,
passwords, instance name, or other information that is required to send notifications to those target systems. The target
systems can include email recipients, log files, or other management products.
Some plug-ins are included with VCF Operations, and others might be added when you add a management pack as a
solution.
The configuration options vary depending on which plug-in you select from the Plug-In Type drop-down menu.
To add outbound notification plug-in, see Adding Outbound Notification Plug-Ins.
VMware by Broadcom  3199

---
## page 3200

 VMware Cloud Foundation 9.0
Where You Find Outbound Settings
To manage your outbound settings, from the left menu, click Infrastructure Operations > Configurations, and then click
the Outbound Settings tile.
Option Description
Toolbar options Use the toolbar options to manage your Outbound Plug-Ins.
• Add. Opens the Outbound Plug-In dialog box where you
configure the connection options for the instance.
Select an existing plugin and click the vertical ellipsis to perform
the following actions.
• Edit. Modify the Outbound Plug-In instance details.
• Delete. Removes the selected plug-in instance.
• Activate or Deactivate. Starts or stops the plug-in instance.
Deactivating an instance allows you to stop sending the
messages configured for the plug-in without removing the
configuration from your environment.
• Export. Downloads the outbound settings.
• Import. Allows you to import outbound settings. To import:
– Click the Import option from the horizontal ellipsis.
– Click Browse and select the file to import.
– Select if you want to Overwrite or Skip the file in case of a
conflict.
– Click Import to import outbound settings, and click Done.
Instance Name Name that you assigned when you created the plug-in instance.
Click the vertical ellipsis to perform the following actions.
• Edit. Allows you to edit the selected payload template.
• Delete. Removes the selected payload template.
• Activate or Deactivate. Starts or stops the plug-in instance.
Deactivating an instance allows you to stop sending the
messages configured for the plug-in without removing the
configuration from your environment.
• Export. Downloads the outbound settings.
Plug-In Type Type of configured plug-in for the plug-in instance. The types of
plug-ins vary depending on the solutions you have added to your
environment.
The most common plug-in types include standard email, SNMP
trap, log file, and REST.
Status Specifies whether the plug-in is currently running.
List of Outbound Plugins
VCF Operations provides outbound plug-ins. This list includes the name of the plug-in and whether you can filter the
outbound data based on your notification settings.
If the plug-in supports configuring notification rules, then you can filter the messages before they are sent to the target
system. If the plug-in does not support notifications, all messages are sent to the target system, and you can process
them in that application.
If you installed other solutions that include other plug-in options, they appear as a plug-in option with the other plug-ins.
Messages and alerts are sent only when the plug-in is activated.
VMware by Broadcom  3200

---
## page 3201

 VMware Cloud Foundation 9.0
Table 993: Notification Support for Outbound plug-ins
Outbound plug-in Configure Notification Rules
Log File plug-in Yes
To filter the log file alerts, you can either configure the file named TextFilter.xml or configure
the notification rules.
REST Notification plug-in Yes
Network Share plug-in No
Standard Email plug-in Yes
SNMP Trap plug-in Yes
Webhook Notification Plugin Yes
Slack plug-in Yes
Service-Now Notification plug-in Yes
Configuring HTTP Proxy for Outbound Settings
You can configure an HTTP proxy for outbound communication over HTTP/HTTPS protocol in VCF Operations. Once the
HTTP proxy is configured for an outbound setting, all the corresponding outbound HTTP(S) communication must happen
through that proxy.
1. From the left menu, click Operations > Configurations, and then click the Outbound Settings tile. Click the HTTP
Proxy for Outbound Settings tab.
2. Click Add.
Table 994: HTTP Proxy Options
Options Description
Proxy Name Name of the HTTP proxy server.
Proxy Host/ IP The IP address of the HTTP proxy.
Proxy Port Port number used to connect to the HTTP proxy server.
Proxy Username Username of the HTTP proxy server.
Proxy Password Password for the HTTP proxy server username.
3. Click Save.
The HTTP proxy setting is added.
Use the HTTP Proxy to configure outbound plugins for Service-Now Notification Plugin, Webhook Notification Plugin, and
Slack Plugin in VCF Operations. For more information see Outbound Settings in VCF Operations.
Importing and Exporting HTTP Proxy for Outbound Settings
You can import or export the HTTP Proxy settings for outbound plugins.
Importing HTTP Proxy for Outbound Settings
1. From the HTTP Proxy for Outbound Settings tab, click the horizontal ellipsis, and then click Import to import the
outbound proxy settings.
2. Click Browse to select the outbound proxy setting and enter the Encryption Key.
VMware by Broadcom  3201

---
## page 3202

 VMware Cloud Foundation 9.0
3. In case of a conflict, click Overwrite HTTP Proxy for Outbound Settings to delete the existing proxy setting and
proceed. Optionally, click Skip HTTP Proxy for Outbound Settings to cancel the import.
Note:  A conflict happens when you try to import a proxy with a name that already exists in the proxy list. Proxy names
are unique and cannot be repeated.
4. Click Import.
The HTTP proxy import process begins.
Exporting HTTP Proxy for Outbound Settings
1. From the HTTP Proxy for Outbound Settings tab, select the HTTP Proxy you want to export, click the horizontal
ellipsis, and then click Export.
2. Enter a new password in the Setup a new password to export data field.
3. Re-enter the password in the Repeat a password field.
4. Click Export.
The outbound proxy settings data gets exported in the .json format. The passphrase entered at the time of export is
used to encrypt the sensitive information. The same passphrase must be used at the time of import.
Adding Outbound Notification Plug-Ins in VCF Operations
You add outbound plug-in instances so that you can notify users about alerts or capture alert data outside of VCF
Operations.
You can configure one or more instances of the same plug-in type if you need to direct alert information to multiple target
systems.
Add a Standard Email Plug-In for VCF Operations Outbound Alerts
You add a Standard Email Plug-In so that you can use Simple Mail Transfer Protocol (SMTP) to email VCF Operations
alert notifications to your virtual infrastructure administrators, network operations engineers, and other interested
individuals.
Ensure that you have an email user account that you can use as the connection account for the alert notifications. If you
choose to require authentication, you must also know the password for this account.
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Outbound Settings tile.
2. Click Add, and from the Plug-In Type drop-down menu, select Standard Email Plugin.
The dialog box expands to include your SMTP settings.
3. Enter an Instance Name.
This is the name that identifies this instance that you select when you later configure notification rules.
4. Configure the SMTP options appropriate for your environment.
Option Description
Use Secure Connection Activates secure communication encryption using SSL/TLS. If
you select this option, you must select a method in the Secure
Connection Type drop-down menu.
Note:  In VCF Operations, the Standard Email Plugin always
uses the 'starttls' command when you select the Use Secure
Connection checkbox and select TLS as the Secure
Connection Type.
Requires Authentication Activates authentication on the email user account that you use
to configure this SMTP instance. If you select this option, you
must provide a password for the user account.
VMware by Broadcom  3202

---
## page 3203

 VMware Cloud Foundation 9.0
Option Description
SMTP Host URL or IP address of your email host server.
SMTP Port Default port SMTP uses to connect with the server.
Secure Connection Type Select either SSL/TLS as the communication encryption method
used in your environment from the drop-down menu. You must
select a connection type if you select Use Secure Connection.
Note:  In VCF Operations, the Standard Email Plugin always
uses the 'starttls' command when you select the Use Secure
Connection checkbox and select TLS as the Secure
Connection Type.
Sender Email Address Email address that appears on the notification message.
Sender Name Displayed name for the sender email address.
Credential Type Select the Credential Type from the list. If your Endpoint URL
does not need any authentication, then select No Credential
from the Credential Type list.
Credential Add or edit the Credential details. Click the plus icon to enter
the details of the new credentials in the Create New Credential
pane, and click Save.
This field appears only when you select Basic Authentication
as the Credential Type.
Note:
Starting VCF Operations 8.14, you could only view, add, modify,
or delete credentials that you created or were assigned to you.
You could view unassigned credentials only if you had the
required permissions. When you upgrade to VCF Operations
8.16.1, you can deactivate the Credential Ownership
Enforcement option from Global Settings to be able to modify
credentials created and owned by others. For more information,
see List of Global Settings.
Receiver Email Address Receiver's email address.
5. Click Save.
6. To start the outbound alert service for this plug-in, select the instance in the list and click Activate on the toolbar.
This instance of the Standard Email Plug-In for outbound SMTP alerts is configured and running.
Create notification rules that use the Standard Email Plug-In to send a message to your users about alerts requiring their
attention. See User Scenario: Create a Email Alert Notification.
Add a Log File Plug-In for VCF Operations Outbound Alerts
You add a Log File plug-in when you want to configure VCF Operations to log alerts to a file on each of your nodes. If
you installed VCF Operations as a multiple node cluster, each node processes and logs the alerts for the objects that it
monitors. Each node logs the alerts for the objects it processes.
Ensure that you have write access to the file system path on the target nodes.
All alerts are added to the log file. You can use other applications to filter and manage the logs.
VMware by Broadcom  3203

---
## page 3204

 VMware Cloud Foundation 9.0
1. From the left menu, click Operations > Configurations, and then click the Outbound Settings tile.
2. Click Add, and from the Plug-In Type drop-down menu, select Log File.
The dialog box expands to include your log file settings.
3. In the Alert Output Folder text box, enter the folder name.
If the folder does not exist in the target location, the plug-in creates the folder in the target location. The default target
location is: /usr/lib/vmware-vcops/common/bin/.
4. Click Save.
5. To start the outbound alert service for this plug-in, select the instance in the list and click Activate on the toolbar.
This instance of the log file plug-in is configured and running.
When the plug-in is started, the alerts are logged in the file. Verify that the log files are created in the target directory as
the alerts are generated, updated, or canceled.
Add a Network Share Plug-In for VCF Operations Reports
You add a Network Share plug-in when you want to configure VCF Operations to send reports to a shared location. The
Network Share plug-in supports only SMB version 2.1.
Verify that you have read, write, and delete permissions to the network share location.
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Outbound Settings tile.
2. Click Add, and from the Plug-In Type drop-down menu, select Network Share Plug-in.
The dialog box expands to include your plug-in instance settings.
3. Enter an Instance Name.
This is the name that identifies this instance that you select when you later configure notification rules.
4. Configure the Network Share options appropriate for your environment.
Option Description
Domain Your shared network domain address.
User Name The domain user account that is used to connect to the network.
Password The password for the domain user account.
Network share root The path to the root folder where you want to save the reports.
You can specify subfolders for each report when you configure
the schedule publication.
You must enter an IP address. For example, \
\IP_address\ShareRoot. You can use the host name
instead of the IP address if the host name is resolved to an IPv4
when accessed from the VCF Operations host.
Note:  Verify that the root destination folder exists. If the folder
is missing, the Network Share plug-in logs an error after 5
unsuccessful attempts.
5. Click Test to verify the specified paths, credentials, and permissions.
The test might take up to a minute.
6. Click Save.
The outbound service for this plug-in starts automatically.
VMware by Broadcom  3204

---
## page 3205

 VMware Cloud Foundation 9.0
7. Optional: To stop an outbound service, select an instance and click Deactivate on the toolbar.
This instance of the Network Share plug-in is configured and running.
Create a report schedule and configure it to send reports to your shared folder.
Sample Log File Plug-In Output
Here is a sample log file plug-in output.
AlertId :: 9fb52c9c-40f2-46a7-a005-01bf24ab75e6
AlertStatus :: Active
AlertControlState :: Open
AlertGenerateTime :: Wed May 06 06:26:05 UTC 2020 (UTC = 1588746365585)
AlertUpdateTime :: Wed May 06 06:26:05 UTC 2020 (UTC = 1588746365585)
AlertMessage :: 9027
AlertSummaryLink :: https://10.0.1.100/ui/index.action#/object/all/1b852a3c-bbdf-41df-
a64d-b40af9673b89/alertsAndSymptoms/alerts/9fb52c9c-40f2-46a7-a005-01bf24ab75e6
AlertType :: Storage - Performance
AlertCriticality :: 4
AffectedResourceId :: 1b852a3c-bbdf-41df-a64d-b40af9673b89
AffectedResourceName :: JNJ_6nodes_Large_HA_4_10.0.2.50
AffectedResourceKind :: VirtualMachine
AffectedResourceParentsNames :: 
 VM Entity Status:PoweredOn:all
 DistributedVirtualPortgroup:VM-Network-VLAN-820
 VM Entity Status:PoweredOn:vc_evn-hs1-vc.company.com
 VMFolder:Discovered virtual machine
 HostSystem:evn1-hs1-0808.company.com
AffectedResourceAdapterInstanceResourceName :: 
 CompanyAdapter Instance:vc_evn-hs1-vc.company.com
AlertOwner :: 
Anomalies :: 
 VirtualMachine:JNJ_6nodes_Large_HA_4_10.0.2.50 - [virtualDisk:Aggregate of all
 instances|totalWriteLatency_average] - HT above 30.5647619047619 > 25
 VirtualMachine:JNJ_6nodes_Large_HA_4_10.0.2.50 - [virtualDisk:Aggregate of all
 instances|totalWriteLatency_average] - HT above 30.5647619047619 > 15
 VirtualMachine:JNJ_6nodes_Large_HA_4_10.0.2.50 - [virtualDisk:Aggregate of all
 instances|totalWriteLatency_average] - HT above 30.5647619047619 > 30
Health :: 
4.0
Risk :: 
2.0
Efficiency :: 
1.0
VMware by Broadcom  3205

---
## page 3206

 VMware Cloud Foundation 9.0
KPIFiring :: 
AlertTrigger :: 
 Resource                                          Message Info                    Alarm
 Reason  Probability              Prediction Time         
 VirtualMachine:JNJ_6nodes_Large_HA_4_10.0.2.50  HT above 30.5647619047619 > 30  HT
 above      Unable to retrive value  Unable to retrive value 
AlertRootCause :: 
null
AlertRootCauseDetails :: null
AlertName :: Virtual machine disk I/O write latency is high
AlertDescription :: 
Virtual machine disk I/O write latency is high
Add an SNMP Trap Plug-In for VCF Operations Outbound Alerts
You add an SNMP Trap plug-in when you want to configure VCF Operations to log alerts on an existing SNMP Trap
server in your environment.
Ensure that you have an SNMP Trap server configured in your environment, and that you know the IP address or host
name, port number, and community that it uses.
You can provide filtering when you define a Notification using an SNMP Trap destination.
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Outbound Settings tile.
2. Click Add, and from the Plug-In Type drop-down menu, select SNMP Trap Plugin.
The dialog box expands to include your SNMP trap settings.
3. Enter an Instance Name.
4. Configure the SNMP trap settings appropriate to your environment.
Option Description
Destination Host IP address or fully qualified domain name of the SNMP
management system to which you are sending alerts.
Port Port used to connect to the SNMP management system. Default
port is 162.
Community Text string that allows access to the statistics. SNMP
Community strings are used only by devices that support
SNMPv1 and SNMPv2c protocol.
Username User name to configure SNMP trap settings in your
environment. If the user name is specified, SNMPv3 is
considered as the protocol by the plugin.
If left blank, SNMPv2c is considered as the protocol by the
plugin.
Note:  SNMP uses User Datagram Protocol (UDP) as its
transport protocol.
Authentication Protocol Authentication algorithms available are SHA-224, SHA-256,
SHA-384, SHA-512.
Authentication Password Authentication password.
Privacy Protocol Privacy algorithms available are AES192, AES256.
VMware by Broadcom  3206

---
## page 3207

 VMware Cloud Foundation 9.0
Option Description
Privacy Password Privacy password.
Engine ID Engine ID serves as an identifier for the agent. It is used with a
hashing function to generate localized keys for authentication
and encryption of SNMP v3 messages.
It is mandatory to specify the Engine ID when configuring the
SNMP Trap plugin. If you do not add the Engine ID and save the
SNMP Trap plugin instance, the field is auto-generated the next
time you edit the settings.
Varbinds Encoding Varbinds Encoding allows you to define character encoding
when SNMP notifications are sent in languages other than
English. Character encoding is used to convert textual data to
binary format. The receiving endpoint decodes the received
binary data into text accordingly.
By default, the encoding is set to ISO-8859-1. You can select the
following encoding option from the list.
• UTF-8
Note:  The newly added encoding option will be effective only
when the SNMP servers receiving the notifications support the
encoding.
5. Click Test to validate the connection.
Note:  The Community and Username options are mutually exclusive. Define either one of them to avoid an error. If
you add a user name, you can optionally define the Authentication Protocol and Authentication Password followed by
the Privacy Protocol and Privacy Password. The privacy protocol and its password cannot be defined independent of
the authentication protocol and its password.
This instance of the SNMP Trap plug-in is configured and running.
When the plug-in is added, configure notifications for receiving the SNMP traps.
Add a Service-Now Notification Plug-In for Outbound Alerts
You add a Service-Now Notification plug-in when you want to integrate Service Now ticketing system with VCF
Operations. Service Now creates an incident whenever an alert is triggered in VCF Operations.
Ensure that you have log in credentials for Service-Now.
Ensure that you are assigned with IT Infrastructure Library (ITIL) role in Service Now.
Using Service-Now Notification Plug-In you can send alert notifications to the Service Now ticketing system to create
incidents. The incident includes information like the Caller, Category, Subcategory, Business Service, and other attributes
related to alerts.
1. From the left menu, click Operations > Configurations, and then click the Outbound Settings tile.
2. Click Add and from the Plug-In Type drop-down menu, select Service-Now Notification Plug-in.
The dialog box expands to include your plug-in instance settings.
3. Enter an Instance Name.
4. Enter the Service Now URL.
https://dev22418.service-now.com/
VMware by Broadcom  3207

---
## page 3208

 VMware Cloud Foundation 9.0
5. Enter a value for the Connection Count.
The connection count represents the maximum number of open connections allowed per node in VCF Operations.
6. Optional: Select your HTTP Proxy.
7. Select the Credential Type from the list.
Note:  If your Endpoint URL does not need any authentication, then select No Credential from the Credential Type
list.
8. Add or edit the Credential details. Click the plus icon to enter the details of the new credentials in the Create New
Credential pane, and click Save. This field appears only when you select Basic Authentication as the Credential
Type.
Note:  When you upgrade to the latest version of VCF Operations, all credentials get unassigned. The VCF
Operations administrator must assign the credentials from the Orphan and Unassigned page. For more information,
see the topic, Managing Orphaned and Unassigned Content.
9. To verify the specified paths, credentials, and permissions, click Test.
10. Click Save.
This instance of the Service-Now Notifications plug-in is configured and running.
When the plug-in is added, configure notifications for creating incidents in Service-Now ticketing system.
Notifications - Add a Slack Plugin for Outbound Notifications
You can add a Slack plug-in to forward alerts and configure multiple notification rules with different slack channels. The
Slack plug-in allows you to receive pre-formatted alert details with alert fields and helps you run VCF Operations using
alert links to troubleshoot further.
1. From the left menu, click Operations > Configurations, and then click the Outbound Settings tile.
2. Click Add and from the Plugin Type drop-down menu, select Slack Plugin.
The dialog box expands to include your plug-in instance settings.
3. Enter an Instance Name.
4. Enter a value for the Connection Count.
The connection count represents the maximum number of open connections allowed per node in VCF Operations.
5. Optional: Select your HTTP Proxy.
6. To verify the specified paths, credentials, and permissions, click Test.
7. Click Save.
This instance of the Slack plugin is configured and running.
When the plugin is added, configure notifications for different slack channels.
Add a Webhook Notification Plugin for Outbound Instance
You can integrate Webhook with any endpoint REST API and configure outbound payload.
Ensure that you have login credentials for Webhook.
VMware by Broadcom  3208

---
## page 3209

 VMware Cloud Foundation 9.0
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Outbound Settings tile.
2. Click Add and from the Plugin Type drop-down menu, select Webhook Notification Plugin.
The dialog box expands to include your plugin instance settings.
3. Enter an Instance Name.
4. Enter the Webhook URL.
Note:  For notifications that reference webhook outbound instances, the URL that you enter here serves as a base
URL that is combined with the endpoint URL suffix defined in related webhook payload templates.
5. Enter a value for the Connection Count.
The connection count represents the maximum number of open connections allowed per node in VCF Operations.
6. Optional: Select your HTTP Proxy.
7. Select the Credential Type from the list.
Note:  If your Endpoint URL does not need any authentication, then select No Credential from the Credential Type
list.
8. Add or edit the Credential details. Click the plus icon and enter the details of the new credentials in the right pane, and
click Save.
Note:  When you upgrade to the latest version of VCF Operations, all credentials get unassigned. The VCF
Operations administrator must assign the credentials from the Orphan and Unassigned page. For more information,
see the topic, Managing Orphaned and Unassigned Content.
The fields in the Create New Credential pane appear based on the Credential Type you select.
Credential Type Fields
Basic Authentication Enter the Name, User Name, and Password.
Bearer Token Enter the Name of the credential and the Token.
OAuth Authentication Enter the following details:
• Name: Enter a name for the authentication.
• Grant Type: Select either Client Credentials or Password Credentials.
• Authentication URL: Enter the URL from where the access token can be
retrieved.
• Client ID: Enter the client ID for the authentication URL.
• Client Secret: Enter the client secret for the authentication URL.
• User Name: Enter the user name for the authentication URL.
Note:  This field appears only when the grant type is Password Credentials.
• Password: Enter the password for the authentication URL.
Note:  This field appears only when the grant type is Password Credentials.
• Scope: Enter the labels to specify the access token. The labels specify the
permissions that the access tokens will have.
• Send Credentials: Select either In auth header or In body.
– In auth header: Sends the Client ID and Client Secret in the header.
– In body: Sends the Client ID and Client Secret in the payload body.
Note:  This field appears only when the grant type is Client Credentials.
• Access Token Path: Enter your access token path.
VMware by Broadcom  3209

---
## page 3210

 VMware Cloud Foundation 9.0
Credential Type Fields
• Validity Token Path: To keep track of when the token is going to expire, enter
the validity token path and select the format from the drop-down list. You can
choose one of the following formats:
– Second
– Milisecond
– Absolute Time
• Header Name: Enter a header name. By default, the header name is
'Authorization'.
• Prefix: Enter a prefix. By default, the prefix is 'Bearer'.
• HTTP Proxy: Select your HTTP Proxy.
Certificate Enter the following details:
• Name: Enter the name of the certificate.
• Certificate: Enter the certificate in the X.509 format.
• Certificate Key: Enter the private key. The formats supported are Open SSL,
PKCS1, and PKCS8
API Key Enter the Name, API Key, and the API Value.
9. To verify the specified paths, credentials, and permissions, click Test.
Note:
• The Test feature does not currently support the Custom Templates. If the template contains a custom headers, the
test might fail.
10. Click Save.
This instance of the Webhook Notification plugin is configured and running.
Sample Email Alert
Here is a sample email for a newly created alert.
Alert Definition Name: Node is experiencing swapping due to memory pressure
Alert Definition Description: Node is experiencing swapping due to memory pressure
Object Name : VMware Aria Operations Node-VMwareAria Cluster Node
Object Type : vC-Ops-Node
Alert Impact: risk
Alert State : warning
Alert Type : Application
Alert Sub-Type : Performance
Object Health State: info
Object Risk State: warning
Object Efficiency State: info
Control State: Open
Symptoms:
SYMPTOM SET - self
Symptom Name Object Name Object ID Metric Message
Info
Node swap usage at Warning
level
VCF Operations Node-VMware
Aria Cluster Node
50ec874a-2d7d-4e78-98
b1-afb26fd67e58
Swap|Workload 59.183 >
30.0
Recommendations:
Notification Rule Name: rule1
VMware by Broadcom  3210

---
## page 3211

 VMware Cloud Foundation 9.0
Notification Rule Description:
Alert ID : badc2266-935d-4fb9-8594-e2e71e4866fc
VCOps Server - VMwareAriaClusterNode
Alert details(link)
Exporting and Importing Outbound Settings
As a VCF Operations admin, you can backup the content before upgrading, export all the outbound plugin configurations,
and import it into a different VCF Operations instance. You can also export the content from VCF Operations on-prem to
VCF Operations.
Note:  Any user with "Manage" Outbound Settings permission can export and import outbound plugin configurations.
1. Export an outbound setting.
a) From the left menu, click Operations > Configurations, and then click the Outbound Settings tile.
b) Select the outbound settings that you want to export and click the horizontal ellipses and select Export.
c) Setup a new password to export data. The password should be at least 14 characters long.
d) Click Export.
The outbound setting data is exported in the .json format. A password is used to encrypt the data in the file using
the AES algorithm with 128 bit key. Use the same password while importing this file.
2. Import an outbound setting.
Note:  Before importing the outbound setting, ensure that you have exported the outbound plugin configurations.
a) From the left menu, click Infrastructure Operations > Configurations, and then click the Outbound Settings tile.
b) Click the horizontal ellipses and select Import.
c) Click Browse to select the .json file and enter the password that you had set while exporting the content.
d) If there is a conflict while importing the content, you can either overwrite the existing outbound settings or skip the
import, which is the default.
e) Click Import to import outbound settings to the destination setup.
Note:  While importing outbound settings on VCF Operations, Cloud Proxy configurations will be excluded.
Payload Templates in VCF Operations
Payload is an essential information in the data block that you send or receive from the server. Use the Payload
Templates page to view the list of payload templates available for each plug-in in VCF Operations. You can add, manage,
and edit your payload templates from this page. Default payload templates are provided for each plug-in type.
VMware by Broadcom  3211

---
## page 3212

 VMware Cloud Foundation 9.0
Where You Find Payload Templates
To manage your payload templates, from the left menu, click Infrastructure Operations > Configurations, and then click
the Payload Templates
tile.
Option Description
Toolbar options Use the toolbar options to manage your notification rules.
• Add. Use the Create Payload Template dialog box to create new payload templates.
Click the horizontal ellipsis to perform the following actions.
• Delete. Removes the selected payload template.
• Export. Downloads the payload template.
Note:  Export and delete actions are not supported for the default payload templates available for each
plug-in.
• Import. Allows you to import payload templates. To import:
– Click the Import option from the horizontal ellipsis.
– Click Browse and select the file to import.
– Select if you want to Overwrite or Skip the import in case of a conflict.
– Click Import to import the payload template, and then click Done. A message with the number of
imported and skipped files will appear.
Quick Filter Limits the list based on the text you type. It considers only text from templates Name column.
You can also sort columns in the data grid. You can view a blue arrow next to the column according to
which sorting was performed, pointing up or down based on the sorting order (ascending or descending).
Template Name Name of the payload template.
Click the vertical ellipsis to perform the following actions.
• Edit. Allows you to edit the selected payload template.
• Clone. Clones the selected payload template.
• Delete. Removes the selected payload template.
• Export. Downloads the payload template.
•
Note:  Edit, Delete, and Export actions are not supported for the default payload templates available for
each plug-in.
Description Description of the payload template.
VMware by Broadcom  3212

---
## page 3213

 VMware Cloud Foundation 9.0
Option Description
Object Types Base object type against which the payload template is defined, if any.
Attached Notification
Rules
Notification rule attached to the payload template.
Attached Outbound
Methods
Outbound plugin type attached to the payload template.
Modified By Name of the last person to modify the payload template.
Last Modified Date on which the payload template was last modified.
Creating Payload Templates for Outbound Plugins
You can create a payload template for an outbound plugin of your choice in VCF Operations.
Use payload templates to configure the payload of an email, and customize the subject line, and email body. You can
enable your own input properties and different payloads for updated and canceled alerts.
You can customize payloads only for Standard Email Plug-in and Webhook Notification Plug-in.
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Payload Templates tile.
On the toolbar, click Add to create a new payload template.
2. In the Details tab, enter the basic details of the payload template.
Option Description
Name Provide a name for the payload template.
Description Enter a description for the payload template.
Outbound Method Outbound plugin for which you want to create a new payload
template.
Select one of the outbound alert plug-in types: Log File Plugin,
Standard Email Plugin, SNMP Trap Plugin, Webhook Notification
Plugin, Slack Plugin, and Service-Now Notification Plugin.
Advanced Settings
Notification Type • Select Alert to configure an alert notification.
• Select Action to configure notification for WLP VM movement
task.
Note:  The Action option appears only when you select
Webhook Notification Plugin in the Outbound Method field.
You can configure notification for type 'Action' only for the
Webhook Notification Plugin.
VMware by Broadcom  3213

---
## page 3214

 VMware Cloud Foundation 9.0
3. Click Next.
4. In the Object Content tab, define the object details that you want to include in the notifications.
Note:  To create a payload template, it is mandatory to add the object type for all the outbound plugin types except for
the Standard Email Plugin and Webhook Notification Plugin.
Option Description
Add Object Type • Select an object type from the list. Once you select the object
type, define self metrics/properties, ancestors, descendants,
ancestor metrics/properties, and descendant metrics/
properties associated with the object type that you want to
include in the notification.
From the right pane, double-click or drag the metrics and
properties into the Add Metrics and Properties box. You can
select up to 30 metrics and properties.
Note:  For Action Type of Notifications, only Virtual Machine is
available for selection.
• Define the ancestor/descendant object type along with the
corresponding metrics and properties.
Select the ancestor/descendant from the drop-down
menu and from the right pane, double-click or drag the
corresponding metrics and properties into the left pane.
Note:  For SNMP Trap Plugin, you can only select ancestor
objects but you cannot add metrics/properties or define
descendant details.
The information that you define here will be included in the
alert notification for all the plug-ins. However, for a Webhook
Notification Plugin and Standard Email Plugin, the information
will be included only when you define the values in the Payload
Details tab.
5. Click Create to create the new payload template or click Next if you are creating a payload template for a Standard
Email Plugin or a Webhook Notification Plugin.
6. In the Payload Details tab, enter the payload details that you want to include in the notification.
Note:  This tab is available only when you are creating a payload template for a Standard Email Plugin or a Webhook
Notification Plugin.
Option Description
Do you want to add template input properties? Select Yes to add input properties and enter the Key, Type,
Display Name, and Description of the input property. Otherwise,
select No.
Note:  The input properties are specific to your endpoint. Once
you define the input properties in the template, you must provide
the appropriate values in each rule where this template will be
used.
Do you want different payload details for new, updated, and
canceled alerts?
Select Yes to define different payload details for new, updated,
and canceled alerts. Otherwise, select No.
Note:  This field does not appear when the Notification Type is
Action.
The following fields appear while creating a payload template for the Standard Email Plugin.
Subject Enter a subject for the email notification.
VMware by Broadcom  3214

---
## page 3215

 VMware Cloud Foundation 9.0
Option Description
Body Enter the content for the email notification. You can also search
for parameters in the right pane. Click the copy icon next to
the parameter to copy the parameter and you can paste the
parameter in the email body.
You can use the options in the toolbar to edit, format, and highlight
the email content.
Note:  You can set up different email content for new, updated,
and canceled alerts.
The following fields appear while creating a payload template for the Webhook Notification Plugin.
Endpoint URL Enter the endpoint URL. The endpoint URL will be appended to
the base URL provided in the related webhook outbound instance.
Note:  The entire URL is encoded. However, there is an exception
to use the character '/' in the URL.
Content Type Select the content type for the payload.
Custom Headers Enter the HTTP Custom Header Name and Value. Click the plus
icon to add multiple custom headers.
Note:  For webhook payloads using token-based authentication,
add an Authorization Header in the format required by the
endpoint.
HTTP Method Select the HTTP method of request.
Payload of the request Payload for the selected plug-in type. It displays information based
on the selected metrics, properties, ancestors, and object types.
You can search for parameters in the right pane. Click the copy
icon next to the parameter to copy the parameter and you can
paste the parameter in the Payload of the request box.
7. Click Create.
Once the payload template is created, you can view it in the Payload Templates page. After selecting a payload
template in the notification rule, you can view the payload template details in the Notifications page.
Managing Alert Groups in VCF Operations
For easy and better management of alerts, you can arrange them as a group as per your requirement.
It is complicated to identify a problem in large environments as you receive different kind of alerts. To manage alerts
easily, group them by their definitions.
For example, there are 1000 alerts in your system. To identify different types of alerts, group them based on their alert
definitions. It is also easy to detect the alert having the highest severity in the group.
When you group alerts, you can view the number of times the alerts with the same alert definition are triggered. By
grouping alerts, you can perform the following tasks easily and quickly:
• Find the noisiest alert: The alert that has triggered maximum number of times is known as the noisiest alert. Once you
find it, you can deactivate it to avoid further noise.
• Filter alerts: You can filter alerts based on a substring in alert definitions. The result shows the group of alerts that
contain the substring.
Note:
• If you cancel or deactivate an alert group, the alerts are not canceled instantly. It might take some time if the group is
large.
VMware by Broadcom  3215

---
## page 3216

 VMware Cloud Foundation 9.0
• Only one group can be expanded at a time.
• The number next to the group denotes the number of alerts in that particular group.
•
The criticality sign
  indicates the highest level of severity of an alert in a group.
Grouping Alerts in VCF Operations
You can group alerts by time, criticality, definition, and object type.
To group alerts:
1. From the left menu, click Infrastructure Operations > Alerts.
2. Select from the various options available from the Group By drop-down menu.
Deactivating Alerts in VCF Operations
In an alerts group, you can deactivate an alert by a single click.
To deactivate an alert:
1. From the left menu, click Operations > Alerts.
2. From the Group By drop-down, select Definition, and click on the name of the Alert Definition Group.
3. From the data grid, click Actions > Deactivate.
You can deactivate the alerts by two methods:
• Deactivate Alert in All Policies: Deactivates the alert for all the objects for all the policies.
• Deactivate Alert in Selected Policies: Deactivates the alert for the objects having the selected policy.
Alert Definition Best Practices
As you create alert definitions for your environment, apply consistent best practices so that you optimize alert behavior for
your monitored objects.
Alert Definitions Naming and Description
The alert definition name is the short name that appears in the following places:
• In data grids when alerts are generated
• In outbound alert notifications, including the email notifications that are sent when outbound alerts and notifications are
configured in your environment
Ensure that you provide an informative name that clearly states the reported problem. Your users can evaluate alerts
based on the alert definition name.
The alert definition description is the text that appears in the alert definition details and the outbound alerts. Ensure that
you provide a useful description that helps your users understand the problem that generated the alert.
Wait and Cancel Cycle
The wait cycle setting helps you adjust for sensitivity in your environment. The wait cycle for the alert definition goes into
effect after the wait cycle for the symptom definition results in a triggered symptom. In most alert definitions you configure
the sensitivity at the symptom level and configure the wait cycle of alert definition to 1. This configuration ensures that the
alert is immediately generated after all of the symptoms are triggered at the desired symptom sensitivity level.
The cancel cycle setting helps you adjust for sensitivity in your environment. The cancel cycle for the alert definition
goes into affect after the cancel cycle for the symptom definition results in a cancelled symptom. In most definitions you
VMware by Broadcom  3216

---
## page 3217

 VMware Cloud Foundation 9.0
configure the sensitivity at the symptom level and configure the cancel cycle of alert definition to 1. This configuration
ensures that the alert is immediately cancelled after all of the symptoms conditions disappear after the desired symptom
cancel cycle.
Create Alert Definitions to Generate the Fewest Alerts
You can control the size of your alert list and make it easier to manage. When an alert is about a general problem that can
be triggered on a large number of objects, configure its definition so that the alert is generated on a higher level object in
the hierarchy rather than on individual objects.
As you add symptoms to your alert definition, do not overcrowd a single alert definition with secondary symptoms. Keep
the combination of symptoms as simple and straightforward as possible.
You can also use a series of symptom definitions to describe incremental levels of concern. For example, Volume
nearing capacity limit might have a severity value of Warning while Volume reached capacity limit might
have a severity level of Critical. The first symptom is not an immediate threat, but the second one is an immediate threat.
You can then include the Warning and Critical symptom definitions in a single alert definition with an Any condition and set
the alert criticality to be Symptom Based. These settings cause the alert to be generated with the right criticality if either of
the symptoms is triggered.
Avoid Overlapping and Gaps Between Alerts
Overlaps result in two or more alerts being generated for the same underlying condition. Gaps occur when an unresolved
alert with lower severity is canceled, but a related alert with a higher severity cannot be triggered.
A gap occurs in a situation where the value is <=50% in one alert definition and >=75% in a second alert definition. The
gap occurs because when the percentage of volumes with high use falls between 50 percent and 75 percent, the first
problem cancels but the second does not generate an alert. This situation is problematic because no alert definitions are
active to cover the gap.
Actionable Recommendations
If you provide text instructions to your users that help them resolve a problem identified by an alert definition, precisely
describe how the engineer or administrator should fix the problem to resolve the alert.
To support the instructions, add a link to a wiki, runbook, or other sources of information, and add actions that you run
from VCF Operations on the target systems.
Create a Simple Alert Definition
While troubleshooting, you can now quickly create an alert for a particular object type or a metric in a quick and efficient
way.
You can create a simple alert definition from the following locations.
• From the left menu, click Infrastructure Operations >  Troubleshoot and select the metric for which you want to
create an alert. You can create an alert from the Potential Evidence or the Metrics tab.
• From the left menu, click Infrastructure Operations > Alerts. Select an alert and click the Potential Evidence tab.
• From the Home page, you can search for the specific object type or metric in the search bar.
1. Click the drop-down menu available in the right side of the widget and select the Create an Alert Definition option.
Note:  You cannot create alert definitions for Badge, Time, and Capacity Remaining metrics.
VMware by Broadcom  3217

---
## page 3218

 VMware Cloud Foundation 9.0
2. In the Create Alert Definition page, enter the Name and Description of the alert.
3. Set thresholds, criticality, and the number of wait cycles. Click Show Advanced Settings to set Wait Cycle and
Cancel Cycle.
Note:  The Object Type or Metric/Property are pre-selected and cannot be edited.
4. Click Create.
The new alert is created and the policy the object belongs to and its children policies are activated for the alert.
Create a New Alert Definition
Based on the root cause of the problem, and the solutions that you used to fix the problem, you can create a new alert
definition for VCF Operations to alert you. When the alert is triggered on your host system, VCF Operations alerts you and
provides recommendations on how to solve the problem.
To alert you before your host systems experience critical capacity problems, and have VCF Operations notify you of
problems in advance, you create alert definitions, and add symptom definitions to the alert definition.
1. From the left menu,click Infrastructure Operations > Configurations, and then click the Alert Definitions tile.
2. Enter capacity in the search text box.
Review the available list of capacity alert definitions. If a capacity alert definition does not exist for host systems, you
can create one.
3. Click Add to create a new capacity alert definition for your host systems.
a) In the alert definition workspace, for the Name and Description, enter Hosts - Alert on Capacity
Exceeded.
b) For the Base Object Type, select vCenter Adapter > Host System
c) Under Advanced Settings, select the following options.
Option Selection
Impact Select Risk.
Criticality Select Immediate.
Alert Type and Subtype Select Application : Capacity.
Wait Cycle Select 1.
Cancel Cycle Select 1.
d) In the Symptoms/Conditions workspace, select the following options.
Option Selection
Defined On Select Self.
Symptom Definition Type Select Metric / Property.
Quick filter (Name) Enter capacity.
e) From the Symptom Definition list, click Host System Capacity Remaining is moderately low and drag it to the
left pane.
In the Symptoms pane, make sure that the Base object exhibits criteria is set to All by default.
f) For Add Recommendations, enter virtual machine in the quick filter text box.
g) Click Review the symptoms listed and remove the number of vCPUs from the virtual machine as
recommended by the system, and drag it to the recommendations area in the left pane.
This recommendation is set to Priority 1.
VMware by Broadcom  3218

---
## page 3219

 VMware Cloud Foundation 9.0
4. Click Save to save the alert definition.
Your new alert appears in the list of alert definitions.
You have added an alert definition to have VCF Operations alert you when the capacity of your host systems begins to run
out.
Create a Log Based Alert Definition
Use this example to create a new log based alert definition. Log based alerts are new in VMware Cloud Foundation 9.0.
For more information on log symptoms, see Logs Symptoms.
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Alert Definitions tile.
2. Click Add to create a new log alert definition for your host systems. For example, create an alert definition for Cluster
Performance - Failed vMotions.
a) In the alert definition workspace, for the Name, enter Cluster Performance - Failed vMotions.
b) For the Base Object Type, select Host System.
3. Click NEXT.
4. In the Symptoms/Conditions step, do the following.
a) Drag and drop Add Log Condition.
b) Select Cluster Performance - Failed vMotions from the Filter By drop down list.
c) Change the time period to 6 hours.
5. Click NEXT. Do not add any recommendation. Click NEXT again.
6. In the Policies step, select the default policy.
7. Click CREATE.
In the Alert Definitions table, sort by the last modified column to view the newly created Log based alert definition.
Create an Alert Definition for Department Objects
As a virtual infrastructure administrator, you are responsible for the virtual machines and hosts that the accounting
department uses. You can create alerts to manage the accounting department objects.
You received several complaints from your users about delays when they are using their accounting applications. Using
VCF Operations, you identified the problem as related to CPU allocations and workloads. To better manage the problem,
you create an alert definition with tighter symptom parameters so that you can track the alerts and identify problems
before your users encounter further problems.
Using this scenario, you create a monitoring system that monitors your accounting objects and provides timely
notifications when problems occur.
Add Description and Base Object to Alert Definition
To create an alert to monitor the CPUs for the accounting department virtual machines and monitor host memory for the
hosts on which they operate, you begin by describing the alert.
When you name the alert definition and define alert impact information, you specify how the information about the alert
appears in VCF Operations. The base object is the object around which the alert definition is created. The symptoms can
be for the base object and for related objects.
VMware by Broadcom  3219

---
## page 3220

 VMware Cloud Foundation 9.0
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Alert Definitions tile.
2. Click Add to add a definition.
3. Type a name and description.
In this scenario, type Acct VM CPU early warning as the alert name, which is a quick overview of the problem.
The description, which is a detailed overview. should provide information that is as useful as possible. When the alert
is generated, this name and description appears in the alert list and in the notification.
4. From the Base Object Type drop-down menu, expand vCenter Adapter  and select Host System.
This alert is based on host systems because you want an alert that acts as an early warning to possible CPU stress
on the virtual machines used in the accounting department. By using host systems as the based object type, you can
respond to the alert symptom for the virtual machines with bulk actions rather than responding to an alert for each
virtual machine.
5. Click Advanced Settings and configure the metadata for this alert definition.
a) From the Impact drop-down menu, select Risk.
This alert indicates a potential problem and requires attention in the near future.
b) From the Criticality drop-down menu, select Immediate.
As a Risk alert, which is indicative of a future problem, you still want to give it a high criticality so that it is ranked
for correct processing. Because it is designed as an early warning, this configuration provides a built-in buffer that
makes it an immediate risk rather than a critical risk.
c) From the Alert Type and Subtype drop-down menu, select Performance under Virtualization/Hypervisor.
d) To ensure that the alert is generated during the first collection cycle after the symptoms become true, set the Wait
Cycle to 1.
e) To ensure that the an alert is removed as soon as the symptoms are no longer triggered, set the Cancel Cycle to
1.
The alert is canceled in the next collection cycle if the symptoms are no long true.
These alert impact options help you identify and prioritize alerts as they are generated.
You started an alert definition where you provided the name and description, selected host system as the base object
type, and defined the data that appears when the alert generated.
Continue in the workspace, adding symptoms to your alert definition. See  Add a Virtual Machine CPU Usage Symptom to
the Alert Definition.
 Add a Virtual Machine CPU Usage Symptom to the Alert Definition
To generate alerts related to CPU usage on your accounting virtual machines, you add symptoms to your VCF Operations
alert definition after you provide the basic descriptive information for the alert. The first symptom you add is related to CPU
usage on virtual machines. You later use a policy and group to apply alert to the accounting virtual machines.
Begin configuring the alert definition. See Add Description and Base Object to Alert Definition.
This scenario has two symptoms, one for the accounting virtual machines and one to monitor the hosts on which the
virtual machines operate.
VMware by Broadcom  3220

---
## page 3221

 VMware Cloud Foundation 9.0
1. In the Alert Definition Workspace window, after you configure the Name and Description, Base Object Type, and
Alert Impact, click Next and configure the symptoms.
2. Begin configuring the symptom set related to virtual machines CPU usage.
a) From the Select Symptom drop-down menu, select Metric / Property.
b) From the Defined On drop-down menu, select Child.
c) From the Filter by Object Type drop-down menu, select Virtual Machine.
d) Click Create New to open the Add Symptom Definition workspace window.
3. Configure the virtual machine CPU usage symptom in the Add Symptom Definition workspace window.
a) From the Base Object Type drop-down menu, expand vCenter Adapter and select Virtual Machine.
The collected metrics for virtual machines appears in the list.
b) In the metrics list Search text box, which searches the metric names, type usage.
c) In the list, expand CPU  and drag Usage (%) to the workspace on the left.
d) From the threshold drop-down menu, select Dynamic Threshold.
Dynamic thresholds use VCF Operations analytics to identify the trend metric values for objects.
e) In the Symptom Definition Name text box, type a name similar to VM CPU Usage above trend.
f) From the criticality drop-down menu, select Warning.
g) From the threshold drop-down menu, select Above Threshold.
h) Leave the Wait Cycle and Cancel Cycle at the default values of 3.
This Wait Cycle setting requires the symptom condition to be true for 3 collection cycles before the symptom is
triggered. This wait avoids triggering the symptom when there is a short spike in CPU usage.
i) Click Save.
The dynamic symptom, which identifies when the usage is above the tracked trend, is added to the symptom list.
4. In the Alert Definition Workspace window, drag VM CPU Usage above trend from the symptom definition list to the
symptom workspace on the left.
The Child-Virtual Machine symptom set is added to the symptom workspace.
5. In the symptoms set, configure the triggering condition so that when the symptom is true on half of the virtual
machines in the group to which this alert definition is applied, the symptom set is true.
a) From the value operator drop-down menu, select >.
b) In the value text box, enter 50.
c) From the value type drop-down menu, select Percent.
You defined the first symptom set for the alert definition.
Add the host memory usage symptom to the alert definition. See  Add a Host Memory Usage Symptom to the Alert
Definition.
 Add a Host Memory Usage Symptom to the Alert Definition
To generate alerts related to CPU usage on your accounting virtual machines, you add a second symptom to your VCF
Operations alert definition after you add the first symptom. The second symptom is related to host memory usage for the
hosts on which the accounting virtual machines operate.
Add the virtual machine CPU usage symptom. See  Add a Virtual Machine CPU Usage Symptom to the Alert Definition.
VMware by Broadcom  3221

---
## page 3222

 VMware Cloud Foundation 9.0
1. In the Alert Definition Workspace window, after you configure the Name and Description, Base Object Type, and
Alert Impact, click Next.
2. Configure the symptom related to host systems for the virtual machines.
a) From the Select Symptom drop-down menu, select Metric / Property.
b) From the Defined On drop-down menu, select Self.
c) Click Create New to add new symptom.
3. Configure the host system symptom in the Add Symptom Definition workspace window.
a) From the Base Object Type drop-down menu, expand vCenter Adapters and select Host System.
b) In the metrics list, expand Memory and drag Usage (%) to the workspace on the left.
c) From the threshold drop-down menu, select Dynamic Threshold.
Dynamic thresholds use VCF Operations analytics to identify the trend metric values for objects.
d) In the Symptom Definition Name text box, enter a name similar to Host memory usage above trend.
e) From the criticality drop-down menu, select Warning.
f) From the threshold drop-down menu, select Above Threshold.
g) Leave the Wait Cycle and Cancel Cycle at the default values of 3.
This Wait Cycle setting requires the symptom condition to be true for three collection cycles before the symptom is
triggered. This wait avoids triggering the symptom when a short spike occurs in host memory usage.
h) Click Save.
The dynamic symptom identifies when the hosts on which the accounting virtual machines run are operating above the
tracked trend for memory usage.
The dynamic symptom is added to the symptom list.
4. In the Alert Definition Workspace window, drag Host memory usage above trend from the symptoms list to the
symptom workspace on the left.
The Self-Host System symptom set is added to the symptom workspace.
5. On the Self-Host System symptom set, from the value type drop-down menu for This Symptom set is true when,
select Any.
With this configuration, when any of the hosts running accounting virtual machines exhibit memory usage that is above
the analyzed trend, the symptom condition is true.
6. At the top of the symptom set list, from the Match {operator} of the following symptoms drop-down menu, select
Any.
With this configuration, if either of the two symptom sets, virtual machine CPU usage or the host memory, are
triggered, an alert is generated for the host.
You defined the second symptom set for the alert definition and configured how the two symptom sets are evaluated to
determine when the alert is generated.
Add recommendations to your alert definition so that you and your engineers know how to resolve the alert when it is
generated. See  Add Recommendations to the Alert Definition.
 Add Recommendations to the Alert Definition
To resolve a generated alert for the accounting department's virtual machines, you provide recommendations so that you
or other engineers have the information you need to resolve the alert before your users encounter performance problems.
Add symptoms to your alert definition. See  Add a Host Memory Usage Symptom to the Alert Definition.
As part of the alert definition, you add recommendations that include actions that you run from VCF Operations and
instructions for making changes in vCenter that resolve the generated alert.
VMware by Broadcom  3222

---
## page 3223

 VMware Cloud Foundation 9.0
1. In the Alert Definition Workspace window, after you configure the Name and Description, Base Object Type, Alert
Impact, and Add Symptom Definitions, click Next and add the recommended actions and instructions.
2. Click Create New Recommendation and select an action recommendation to resolve the virtual machine alerts.
a) In the Description text box, enter a description of the action similar to Add CPUs to virtual machines.
b) From the Actions drop-down menu, select Set CPU Count for VM.
c) Click Create.
3. Click Create New Recommendation and provide an instructive recommendation to resolve host memory problems
similar to this example.
If this host is part of a DRS cluster, check the DRS settings to verify that the load
balancing setting are configured correctly. If necessary, manually vMotion the virtual
machines.
4. Click Create.
5. Click Create New Recommendation and provide an instructive recommendation to resolve host memory alerts.
a) Enter a description of the recommendation similar to this example.
If this is a standalone host, add more memory to the host.
b) To make the URL a hyperlink in the instructions, copy the URL, for example, https://www.vmware.com/support/
pubs/vsphere-esxi-vcenter-server-pubs.html, to your clipboard.
c) Highlight the text in the text box and click the hyperlink icon.
d) Paste the URL in the Create a hyperlink text box and click OK.
e) Click Create.
6. In the Alert Recommendation Workspace, drag Add CPUs to virtual machines, If this host is part of a DRS
cluster, and the If this is a standalone host recommendations from the list to the recommendation workspace in the
order presented.
7. Click Next to select policies and view notifications.
8. Click Create.
You provided the recommended actions and instructions to resolve the alert when it is generated. One of the
recommendations resolves the virtual machine CPU usage problem and the other resolves the host memory problem.
Create a group of objects to use to manage your accounting objects. See  Create a Custom Accounting Department
Group.
 Create a Custom Accounting Department Group
To manage, monitor, and apply policies to the accounting objects as a group, you create a custom object group.
Verify that you completed the alert definition for this scenario. See  Add Recommendations to the Alert Definition.
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Custom Groups tile under
Logical Groupings.
2. Click Add to create a new custom group.
3. Type a name similar to Accounting VMs and Hosts.
4. From the Group Type drop-down menu, select Department.
5. From the Policy drop-down menu, select Default Policy.
When you create a policy, you apply the new policy to the accounting group.
VMware by Broadcom  3223

---
## page 3224

 VMware Cloud Foundation 9.0
6. In the Define membership criteria area, from the Select the Object Type that matches the following criteria drop-
down menu, expand vCenter Adapter, select Host System, and configure the dynamic group criteria.
a) From the criteria drop-down menu, select Relationship.
b) From the relationships options drop-down menu, select Parent of.
c) From the operator drop-down menu, select contains.
d) In the Object name text box, enter acct.
e) From the navigation tree drop-down list, select vSphere Hosts and Clusters.
You created a dynamic group where host objects that are the host for virtual machines with acct in the virtual machine
name are included in the group. If a virtual machine with acct in the object name is added or moved to a host, the host
object is added to the group.
7. Click Preview in the lower-left corner of the workspace, and verify that the hosts on which your virtual machines that
include acct in the object name appear in the Preview Group window.
8. Click Close.
9. Click Add another criteria set.
A new criteria set is added with the OR operator between the two criteria sets.
10. From the Select the Object Type that matches the following criteria drop-down menu, expand vCenter Adapter,
select Virtual Machine, and configure the dynamic group criteria.
a) From the criteria drop-down menu, select Properties.
b) From the Pick a property drop-down menu, expand Configuration and double-click Name.
c) From the operator drop-down menu, select contains.
d) In the Property value text box, enter acct.
You created a dynamic group where virtual machine objects with acct in the object name are included in the group
that depends on the presence of those virtual machines. If a virtual machine with acct in the name is added to your
environment, it is added to the group.
11. Click Preview in the lower-left corner of the workspace, and verify that the virtual machines with acct in the object
name are added to the list that also includes the host systems.
12. Click Close.
13. Click OK.
The Accounting VMs and Hosts group is added to the Groups list.
You created a dynamic object group that changes as virtual machines with acct in their names are added, removed, and
moved in your environment.
Create a policy that determines how VCF Operations uses the alert definition to monitor your environment. See Create a
Policy for the Accounting Alert.
Create a Policy for the Accounting Alert
To configure how VCF Operations evaluates the accounting alert definition in your environment, you configure a policy
that determines behavior so that you can apply the policy to an object group. The policy limits the application of the alert
definition to only the members of the selected object group.
• Verify that you completed the alert definition for this scenario. See  Add Recommendations to the Alert Definition.
• Verify that you created a group of objects that you use to manage you accounting objects. See  Create a Custom
Accounting Department Group.
When an alert definition is created, it is added to the default policy and activated, ensuring that any alert definitions
that you create are active in your environment. This alert definition is intended to meet the needs of the accounting
VMware by Broadcom  3224

---
## page 3225

 VMware Cloud Foundation 9.0
department, so you deactivate it in the default policy and create a new policy to govern how the alert definition is
evaluated in your environment, including which accounting virtual machines and related hosts to monitor.
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Policy Definition tile.
2. Click Add.
3. Type a name similar to Accounting Objects Alerts Policy and provide a useful description similar to the
following example.
This policy is configured to generate alerts when 
Accounting VMs and Hosts group objects are above trended
 CPU or memory usage.
4. Select Default Policy from the Start with drop-down menu.
5. On the left, click Customize Alert / Symptom Definitions and deactivate all the alert definitions except the new Acct
VM CPU early warning alert.
a) In the Alert Definitions area, click Actions and select Select All.
The alerts on the current page are selected.
b) Click Actions and select Deactivate.
The alerts indicate Deactivated in the State column.
c) Repeat the process on each page of the alerts list.
d) Select Acct VM CPU early warning in the list, click Actions and select Activate.
The Acct VM CPU early warning alert is now activated.
6. On the left, click Apply Policy to Groups and select Accounting VMs and Hosts.
7. Click Save.
You created a policy where the accounting alert definition exists in a custom policy that is applied only to the virtual
machines and hosts for the accounting department.
Create an email notification so that you learn about alerts even you when you are not actively monitoring VCF Operations.
See Configure Notifications for the Department Alert.
Configure Notifications for the Department Alert
To receive an email notification when the accounting alert is generated, rather than relying on your ability to generally
monitor the accounting department objects in VCF Operations, you create notification rules.
• Verify that you completed the alert definition for this scenario. See  Add Recommendations to the Alert Definition.
• Verify that standard email outbound alerts are configured in your system. See Add a Standard Email Plug-In for VCF
Operations Outbound Alerts.
Creating an email notification when accounting alerts are triggered is an optional process, but it provides you with the alert
even when you are not currently working in VCF Operations.
VMware by Broadcom  3225

---
## page 3226

 VMware Cloud Foundation 9.0
1. From the left menu, click Operations > Configurations, and then click the Notifications tile.
2. Click Add to add a notification rule.
3. Configure the communication options.
a) In the Name text box, type a name similar to Acct Dept VMs or Hosts Alerts.
b) From the Select Plug-In Type drop-down menu, select StandardEmailPlugin.
c) From the Select Instance drop-down menu, select the standard email instance that is configured to send
messages.
d) In the Recipient(s) text box, type your email address and the addresses of other recipients responsible for the
accounting department alerts. Use a semicolon between recipients.
e) Leave the Notify again text box blank.
If you do not provide a value, the email notice is sent only once. This alert is a Risk alert and is intended as an
early warning rather than requiring an immediate response.
You configured the name of the notification when it is sent to you and the method that is used to send the message.
4. In the Filtering Criteria area, configure the accounting alert notification trigger.
a) From the Notification Trigger drop-down menu, select Alert Definition.
b) Click Select Alert Definitions.
c) Select Acct VM CPU early warning and click Select.
5. Click Save.
You created a notification rule that sends you and your designated engineers an email message when this alert is
generated for your accounting department alert definition.
Create a dashboard with alert-related widgets so that you can monitor alerts for the accounting object group. See  Create
a Dashboard to Monitor Department Objects.
 Create a Dashboard to Monitor Department Objects
To monitor all the alerts related to the accounting department object group, you create a dashboard that includes the alert
list and other widgets. The dashboard provides the alert data in a single location for all related objects.
Create an object group for the accounting department virtual machines and related objects. See  Create a Custom
Accounting Department Group.
Creating a dashboard to monitor the accounting virtual machines and related hosts is an optional process, but it provides
you with a focused view of the accounting object group alerts and objects.
1. From the left menu, click Infrastructure Operations > Dashboards and Reports, and then click Create.
2. In the Dashboard Configuration definition area, type a tab name similar to Accounting VMs and Hosts and
configure the layout options.
3. Click Widget List and drag the following widgets to the workspace.
• Alert List
• Efficiency
• Health
• Risk
• Top Alerts
• Alert Volume
The blank widgets are added to the workspace. To change the order in which they appear, you can drag them to a
different location in the workspace.
VMware by Broadcom  3226

---
## page 3227

 VMware Cloud Foundation 9.0
4. On the Alert List widget title bar, click Edit Widget and configure the settings.
a) In the Title text box, change the title to Acct Dept Alert List.
b) For the Refresh Content option, select On.
c) Type Accounting in the Search text box and click Search.
The Accounting value corresponds to the name of the object group for the accounting department virtual machines
and related hosts.
d) In the filtered resource list, select the Accounting VMs and Hosts group.
The Accounting VMs and Hosts group is identified in the Selected Resource text box.
e) Click OK.
The Acct Dept Alert List is now configured to display alerts for the Accounting VMs and Hosts group objects.
5. Click Widget Interactions and configure the following interactions.
a) For Acct Dept Alert List, leave the selected resources blank.
b) For Top Alerts, Health, Risk, Efficiency, and Alert Volume select Acct Dept Alert List from the Selected
Resources drop-down menu.
c) Click Apply Interactions.
With the widget interaction configured in this way, the select alert in the Acct Dept Alert List is the source for the data
in the other widgets. When you select an alert in the alert list, the Health, Risk, and Efficiency widgets display alerts
for that object, Top Alerts displays the topic issues affecting the health of the object, and Alert Volume displays an alert
trend chart.
6. Click Save.
You created a dashboard that displays the alerts related to the accounting virtual machines and hosts group, including the
Risk alert you created.
Monitoring and Responding to Alerts
Alerts indicate a problem in your environment. Alerts are generated when the collected data for an object is compared to
alert definitions for that object type and the defined symptoms are true. When an alert is generated, you are presented
with the triggering symptoms, so that you can evaluate the object in your environment, and with recommendations for how
to resolve the alert.
Alerts notify you when an object or group of objects are exhibiting symptoms that are unfavorable for your environment.
By monitoring and responding to alerts, you stay aware of problems and can react to them in a timely fashion.
Generated alerts drive the status of the top-level badges, Health, Risk, and Efficiency.
In addition to responding to alerts, you can generally respond to the status of badges for objects in your environment.
You can take ownership of an alert or assign alerts to other VCF Operations users.
Monitoring Alerts in VCF Operations
You can monitor your environment for generated alerts in several areas in VCF Operations. The alerts are generated
when the symptoms in the alert definition are triggered, letting you know when the objects in your environment are not
operating within the parameters you defined as acceptable.
Generated alerts appear in many areas of VCF Operations so that you can monitor and respond to problems in your
environment.
Alerts
Alerts are classified as Health, Risk, or Efficiency. Health alerts indicate problems that require immediate attention.
Risk alerts indicate problems that must be addressed shortly, before the problems become immediate health problems.
VMware by Broadcom  3227

---
## page 3228

 VMware Cloud Foundation 9.0
Efficiency alerts indicate areas where you can reclaim wasted space or improve the performance of objects in your
environment.
You can monitor the alerts for your environment in the following locations.
• Alerts
• Health
• Risk
• Efficiency
You can monitor alerts for a selected object in the following locations.
• Alert Details, including the Summary, Timeline, and Metric Charts tabs
• Summary tab
• Alerts tab
• Events tab
• Custom dashboards
• Alert notifications
Working with Alerts
Alerts indicate a problem that must be resolved so that triggering conditions no longer exist and the alert is canceled.
Suggested resolutions are provided as recommendations so that you can approach the problem with solutions.
As you monitor alerts, you can take ownership, suspend, or manually cancel alerts.
When you cancel an alert, the alert and any symptoms of type message event, or metric event are canceled. You cannot
manually cancel other types of symptoms. If a message event symptom or metric event symptom triggered the event, then
the alert is effectively canceled. If a metric symptom or property symptom triggered the alert, a new alert might be created
for the same conditions in the next few minutes.
The correct way to remove an alert is to address the underlying conditions that triggered the symptoms and generated the
alert.
Migrated Alerts
If you migrated alerts from a previous version of VCF Operations, the alerts are listed in the overview with a canceled
status, but alert details are not available.
Actions in VCF Operations
Actions are the ability to update objects or read data about objects in monitored systems, and are commonly provided in
VCF Operations as part of a solution. The actions added by solutions are available from the object Actions menu, list and
view menus, including some dashboard widgets, and can be added to alert definition recommendations.
The possible actions include read actions and update actions.
The read actions retrieve data from the target objects.
The update actions modifies the target objects. For example, you can configure an alert definition to notify you when a
virtual machine is experiencing memory issues. Add an action in the recommendations that runs the Set Memory for
Virtual Machine action. This action increases the memory and resolves the likely cause of the alert.
To see or use the actions for your vCenter objects, you must activate actions in the vCenter Adapter for each monitored
vCenter instance. Actions can only be viewed and accessed if you have the required permissions.
VMware by Broadcom  3228

---
## page 3229

 VMware Cloud Foundation 9.0
Actions, Modified Objects, and Object Levels in VCF Operations Actions
The list of actions includes the name of the action, the objects that each one modifies, and the object levels at which you
can run the action. You use this information to ensure that you correctly apply the actions as alert recommendations and
when the actions are available in the Actions menu.
Actions and Modified Objects VCF Operations actions make changes to objects in your
managed vCenter instances.
When you grant a user access to actions in VCF Operations,
that user can take the granted action on any object that VCF
Operations manages.
Action Object Levels The actions are available when you work with different object
levels, but they modify only the specified object. If you are working
at the cluster level and select Power On VM, all the virtual
machines in the cluster for which you have access permission are
available for you to run the action. If you are working at the virtual
machine level, only the selected virtual machine is available.
Action Modified Object Object Levels
Rebalance Container Virtual Machines • Data Center
• Custom Data Center
Delete Idle VM Virtual Machines • Clusters
• Host Systems
• Virtual Machines
Set DRS Automation Cluster • Clusters
Move VM Virtual Machine • Virtual Machines
Power Off VM Virtual Machine • Clusters
• Host Systems
• Virtual Machines
Shut Down Guest OS for VM Virtual Machine
VMware Tools must be installed and running on the
target virtual machines to run this action.
• Clusters
• Host Systems
• Virtual Machines
Power On VM Virtual Machine • Clusters
• Host Systems
• Virtual Machines
Delete Powered Off VM Virtual Machine • Clusters
• Host Systems
• Virtual Machines
Set Memory for VM
and
Set Memory for VM Power Off
Allowed
Virtual Machine • Clusters
• Host Systems
• Virtual Machines
Set Memory Resources for VM Virtual Machine • Clusters
• Host Systems
• Virtual Machines
Set CPU Count for VM
and
Set CPU Count for VM Power Off
Allowed
Virtual Machine • Clusters
• Host Systems
• Virtual Machines
VMware by Broadcom  3229

---
## page 3230

 VMware Cloud Foundation 9.0
Action Modified Object Object Levels
Set CPU Resources for VM Virtual Machine • Clusters
• Host Systems
• Virtual Machines
Set CPU Count and Memory for VM
and
Set CPU Count and Memory for VM
Power Off Allowed
Virtual Machine • Clusters
• Host Systems
• Virtual Machines
Delete Unused Snapshots for VM Snapshot • Clusters
• Host Systems
• Virtual Machines
Delete Unused Snapshots for
Datastore
Snapshot • Clusters
• Datastores
• Host Systems
Execute Script Virtual Machine • Virtual Machine
Get Top Processes Virtual Machine • Virtual Machine
Apply Guest User Mapping vCenter Server • vCenter Server
Note:  This action is deprecated and
will be removed in the next release.
Clear Guest User Mapping vCenter Server • vCenter Server
Note:  This action is deprecated and
will be removed in the next release.
Export Guest User Mapping vCenter Server • vCenter Server
Note:  This action is deprecated and
will be removed in the next release.
Configure Included Services Service Discovery Adapter Instance • Service Discovery Adapter
Instance
Note:  This action is deprecated and
will be removed in the next release.
Viewing Actions List in VCF Operations
Actions are the method you use to configuration changes on managed objects that you initiate from VCF Operations.
These actions are available to add to alert recommendations.
Actions are defined to run on the target object from different object levels, allowing you to add actions as
recommendations for alert definitions that are configured for different base objects. The Actions page is a list of actions
available in your environment.
VMware by Broadcom  3230

---
## page 3231

 VMware Cloud Foundation 9.0
Where You Find the Actions List
To view the available actions, from the left menu, click Infrastructure Operations > Configurations, and then click the
Actions tile.
Option Description
Filter options Limits the list based on the text you type.
You can also sort on the columns in the data grid.
Action Name Name of the action. Duplicate names indicate that the action name is provided by more than one adapter or
has more than one associated object.
Click this link to view Details page. On the Details Page, you can click on Recommendations to view the
associated recommendations.
Action Type Type of action that the action performs, either read or update.
• Update actions make changes to the target objects.
• Read actions retrieve data from the target objects.
Adapter Type Name of the configured adapter that provides the action.
Resource Adapter Type Adapter that provides the action.
Associated Object
Types
Indicates the object level at which the action instance runs.
Recommendations Indicates whether the action is used in at least one recommendation.
The actions Delete Unused Snapshots for Datastore Express and Delete Unused Snapshots for VM
Express appear. However, these actions can only be run in the user interface from an alert whose first recommendation
is associated with this action. You can use the REST API to run these actions.
The following actions are also not visible except in the alert recommendations:
• Set Memory for VM Power Off Allowed
• Set CPU Count for VM Power Off Allowed
• Set CPU Count and Memory for VM Power Off Allowed
These actions are intended to be used to automate the actions with the Power Off Allowed flag set to true.
VMware by Broadcom  3231

---
## page 3232

 VMware Cloud Foundation 9.0
Actions Supported for Automation
Recommendations can identify ways to remediate problems indicated by an alert. Some of these remediations can be
associated with actions defined in your VCF Operations instance. You can automate several of these remediation actions
for an alert when that recommendation is the first priority for that alert.
You activate actionable alerts in your policies. By default, automation is deactivated in policies. To configure automation
for your policy, in the menu, click Operations > Configurations, and then click the Policy Definition tile. Then, to edit
a policy, access the Alert / Symptom Definitions workspace, and select Local for the Automate setting in the Alert /
Symptom Definitions pane.
When an action is automated, you can use the Automated and Alert columns in Recent Tasks under Administration > 
Control Panel to identify the automated action and view the results of the action.
• VCF Operations uses the automationAdmin user account to trigger automated actions. For these automated actions
that are triggered by alerts, the Submitted By column displays the automationAdmin user.
• The Alert column displays the alert that triggered the action. When an alert is triggered that is associated to the
recommendation, it triggers the action without any user intervention.
The following actions are supported for automation:
• Delete Powered Off VM
• Delete Idle VM
• Move VM
• Power Off VM
• Power On VM
• Set CPU Count And Memory for VM
• Set CPU Count And Memory for VM Power Off Allowed
• Set CPU Count for VM
• Set CPU Count for VM Power Off Allowed
• Set CPU Resources for VM
• Set Memory for VM
• Set Memory for VM Power Off Allowed
• Set Memory Resources for VM
• Shut Down Guest OS for VM
Roles Needed to Automate Actions
To automate actions, your role must have the following permissions:
• Create, edit, and import policies in Infrastructure Operations > Configurations > Policy Definition.
• Create, clone, edit, and import alert definitions in Infrastructure Operations > Configurations > Alert Definitions.
• Create, edit, and import recommendation definitions in Infrastructure Operations > Configurations >
Recommendations.
Important:  You set the permissions used to run the actions separately from the alert and recommendation definition.
Anyone who can modify alerts, recommendations, and policies can also automate the action, even if they do not have
permission to run the action.
For example, if you do not have access to the Power Off VM action, but you can create and modify alerts and
recommendations, you can see the Power Off VM action and assign it to an alert recommendation. Then, if you automate
the action in your policy, VCF Operations uses the automationAdmin user to run the action.
VMware by Broadcom  3232

---
## page 3233

 VMware Cloud Foundation 9.0
Example Action Supported for Automation
For the Alert Definition named Virtual machine has chronic high CPU workload leading to CPU
stress, you can automate the action named Set CPU Count for VM.
When CPU stress on your virtual machines exceeds a critical, immediate, or warning level, the alert triggers the
recommended action without user intervention.
Integration of Actions with VCF Automation
VCF Operations restricts actions on Datacentres and Custom Datacentres that contains VCF Automation managed child
objects such as, cluster compute resources, hosts, and VMs.
You can turn on or turn off the actions on VCF Automation managed objects by modifying the Operational Actions from
the respective vCentre in Cloud Accounts or by creating a new role with limited action ability on VCF Automation managed
objects.
Actions Determine Whether Objects Are Managed
Actions check the objects in the VCF Automation managed resource container to determine which objects are being
managed by VCF Automation.
Actions such as Rebalance Container check the child objects of the data center container or custom data center container
to determine whether the objects are managed by VCF Automation. If the objects are being managed, the action does not
appear on those objects.
Working with Actions That Use Power Off Allowed
Some of the actions provided with VCF Operations require the virtual machines to shut down or power off, depending on
the configuration of the target machines, to run the actions. You should understand the impact of the Power Off Allowed
option before running the actions so that you select the best options for your target virtual machines.
Power Off and Shut Down
The actions that you can run on your vCenter instances include actions that shut down virtual machines and actions that
power off virtual machines. It also includes actions where the virtual machine must be in a powered off state to complete
the action. Whether the VM is shut down or powered off depends on how it is configured and what options you select
when you run the action.
The shut-down action shuts down the guest operating system and then powers off the virtual machine. To shut down a
virtual machine from VCF Operations, the VMware Tools must be installed and running on the target objects.
The power off action turns off the VM without regard for the state of the guest operating system. In this case, if the VM
is running applications, your user might lose data. After the action is finished, for example, modifying the CPU count, the
virtual machine is returned to the power state it was in when the action began.
Power Off Allowed and VMware Tools
For the actions where you are increasing the CPU count or the amount of memory on a VM, some operating systems
support the actions if the Hot Plug is configured on the VM. For other operating systems, the virtual machine must be in a
powered off state to change the configuration. To accommodate this need where the VMware Tools is not running, the Set
CPU Count, Set Memory, and Set CPU Count and Memory actions include the Power Off Allowed option.
If you select Power Off Allowed, and the machine is running, the action verifies whether VMware Tools is installed and
running.
VMware by Broadcom  3233

---
## page 3234

 VMware Cloud Foundation 9.0
• If VMware Tools is installed and running, the virtual machine is shut down before completing the action.
• If VMware Tools is not running or not installed, the virtual machine is powered off without regard for the state of the
operating system.
If you do not select Power Off Allowed and you are decreasing the CPU count or memory, or the hot plug is not activated
for increasing the CPU count or memory, the action does not run and the failure is reported in Recent Tasks.
Power Off Allowed When Changing CPU Count or Memory
When you run the actions that change the CPU count and the amount of memory, you must consider several factors
to determine if you want to use the Power Off Allowed option. These factors include whether you are increasing or
decreasing the CPU or memory and whether the target virtual machines are powered on. If you increase the CPU or
memory values, whether hot plug is activated also affects how you apply the option when you run the action.
How you use Power Off Allowed when you are decreasing the CPU count or the amount of memory depends on the
power state of the target virtual machines.
Table 995: Decreasing CPU Count and Memory Behavior Based On Options
Virtual Machine Power State Power Off Allowed Selected Results
On Yes If VMware Tools is installed and running,
the action shuts down the virtual machine,
decreases the CPU or memory, and powers
the machine back on.
If VMware Tools is not installed, the action
powers off the virtual machine, decreases
the CPU or memory, and powers the
machine back on.
On No The action does not run on the virtual
machine.
Off Not applicable. The virtual machine is
powered off.
The action decreases the value and leaves
the virtual machine in a powered off state.
How you use Power Off Allowed when you are increasing the CPU count or the amount of memory depends on several
factors, including the state of the target virtual machine and whether hot plug is activated. Use the following information to
determine which scenario applies to your target objects.
If you are increasing the CPU count, you must consider the power state of the virtual machine and whether CPU Hot Plug
is activated when determining whether to apply Power Off Allowed.
Table 996: Increasing CPU Count Behavior.
Virtual Machine Power State CPU Hot Plug Activated Power Off Allowed Selected Results
On Yes No The action increases the CPU
count to the specified amount.
On No Yes If VMware Tools is installed and
running, the action shuts down
the virtual machine, increases
the CPU count, and powers the
machine back on.
VMware by Broadcom  3234

---
## page 3235

 VMware Cloud Foundation 9.0
Virtual Machine Power State CPU Hot Plug Activated Power Off Allowed Selected Results
If VMware Tools is not installed,
the action powers off the virtual
machine, increases the CPU
count, and powers the machine
back on.
Off Not applicable. The virtual
machine is powered off.
Not required. The action increases the CPU
count to the specified amount.
If you are increasing the memory, you must consider the power state of the virtual machine, whether Memory Hot Plug is
activated, and whether there is a Hot Memory Limit when determining how to apply Power Off Allowed.
Table 997: Increasing Memory Amount Behavior
Virtual Machine Power
State
Memory Hot Plug
Activated Hot Memory Limit Power Off Allowed
Selected Results
On Yes New memory value = hot
memory limit
No The action increases the
memory the specified
amount.
On Yes New memory value > hot
memory limit
Yes If VMware Tools is
installed and running,
the action shuts down
the virtual machine,
increases the memory,
and powers the machine
back on.
If VMware Tools is not
installed, the action
powers off the virtual
machine, increases the
memory, and powers the
machine back on.
On No Not applicable. The hot
plug is not activated.
Yes If VMware Tools is
installed and running,
the action shuts down
the virtual machine,
increases the memory,
and powers the machine
back on.
If VMware Tools is not
installed, the action
powers off the virtual
machine, increases the
memory, and powers the
machine back on.
Off Not applicable. The
virtual machine is
powered off.
Not applicable. Not required The action increases the
memory the specified
amount.
VMware by Broadcom  3235

---
## page 3236

 VMware Cloud Foundation 9.0
Running Actions from VCF Operations
The actions available in VCF Operations allow you to modify the state or configuration of selected objects in vCenter from
VCF Operations. For example, you might need to modify the configuration of an object to address a problematic resource
issue or to redistribute resources to optimize your virtual infrastructure.
The most common use of the actions is to solve problems. You can run them as part of your troubleshooting procedures
or add them as a resolution recommendation for alerts.
When you grant a user access to actions in VCF Operations, that user can take the granted action on any object that VCF
Operations manages.
When you are troubleshooting problems, you can run the actions from the center pane Actions menu. Alternatively, you
can run them from the toolbar on list views that contain the supported objects.
When an alert is triggered, and you determine that the suggested action is the most likely way to resolve the problem, you
can run the action on one or more objects.
Run Actions from Toolbars in VCF Operations
When you run actions in VCF Operations, you change the state of vCenter objects. You run one or more actions when you
encounter objects where the configuration or state of the object is affecting your environment. These actions allow you to
reclaim wasted space, adjust memory, or conserve resources.
• Verify that the vCenter Adapter is configured to run actions for each vCenter instance. See Configure a vCenter Serve
Cloud Account in VCF Operations Configuration Guide. .
• Verify that the vCenter Adapter is configured to run actions for each vCenter instance. See the VCF Operations
Configuration Guide. .
• Ensure that you understand how to use the power-off-allowed option if you are running Set CPU Count, Set Memory,
and Set CPU Count and Memory actions. See Working with Actions That Use Power Off Allowed section in VCF
Operations Configuration Guide.  .
• Ensure that you understand how to use the power-off-allowed option if you are running Set CPU Count, Set Memory,
and Set CPU Count and Memory actions. See the section Working With Actions That Use Power Off Allowed in the
VCF Operations Information Center.
This procedure for running actions is based on the VCF OperationsActions menus and is commonly used when you are
troubleshooting problems. The available actions depend on the type of objects with which you are working. You can also
run actions as alert recommendations.
1. Select the object in the Environment page inventory trees or select one or more objects it in a list view.
2. Click Actions on the main toolbar or in an embedded view.
3. Select one of the actions.
If you are working with a virtual machine, only the virtual machine is included in the dialog box. If you are working with
clusters, hosts, or datastores, the dialog box that appears includes all objects.
4. To run the action on the object, select the check box and click OK.
The action runs and a dialog box appears that displays the task ID.
5. To view the status of the job and verify that the job finished, click Recent Tasks or click OK to close the dialog box.
The Recent Tasks list appears, which includes the task you just started.
To verify that the job completed, click Environment in the menu and click History >Recent Tasks. Find the task name or
task ID in the list and verify that the status is finished. See Monitor Recent Task Status.
VMware by Broadcom  3236

---
## page 3237

 VMware Cloud Foundation 9.0
Rebalance Container Action
When the workload in your environment becomes imbalanced, you can move the workload across your objects to
rebalance the overall workload. The container for the rebalance action can be a data center or a custom data center, and
the objects that are moved are the virtual machines in the suggested list provided by the action.
DRS Must be Activated on Clusters
Your vCenter instance must have a cluster that passes a DRS-activated check for the Rebalance Container action to
appear in the Actions drop-down menu.
To get the Rebalance Container action from a custom data center or data center, and the related alerts, you must have the
following:
• A vCenter Adapter configured with the actions activated for each vCenter instance
• A vCenter instance with at least one cluster that is DRS-activated.
If your cluster does not have DRS fully automated, the Rebalance Container action notifies you that one or more clusters
under the selected container do not have DRS set to fully automated.
To ensure that the Rebalance Container action is available in your environment, you must add DRS. Then, wait one
collection cycle for the Rebalance Container action to appear.
You Must Have Access to All Objects in the Container
If you have access to all objects in a cluster, data center, or custom data center, you can run the Rebalance Container
action to move virtual machines to other clusters. When you do not have access to all of the objects in the container, the
Rebalance Container action is not available.
How the Rebalance Container Action Works
If two data centers are experiencing extreme differences in workload - one high and one low - use the Rebalance
Container action to balance the workload across those objects. For example, if the CPU demand on a host in one data
center exceeds its available CPU capacity, critical pressure occurs on the host. To identify the cause of stress, monitor the
CPU demand. Some virtual machines on each host might be experiencing high CPU demand, whereas others might be
experiencing a low demand.
The Rebalance Container action moves all affected objects in the suggested list provided by the action to balance the
workload. If you do not want to act on the entire set of objects to resolve the problem with workload, you can use the Move
VM action to move an individual object.
Important:  Do not attempt to move virtual machines that are members of a vApp, because the vApp can become
nonfunctional. Instead, add affinity rules for these virtual machines to keep them together so that the Move VM and
Rebalance Container actions will ignore them.
When workloads become imbalanced, the following alerts can trigger on data centers and custom data centers. These
alerts are deactivated by default in the policies.
• Custom data center has unbalanced workload
• Data center has unbalanced workload
When the workloads on hosts in a data center or custom data center differ significantly, click Operations > Alerts and
verify whether the alert triggered. For example, to verify whether the alert triggered on a custom data center, check the
alert named Custom data center has unbalanced workload. You can click the alert to view the causes of the
alert and identify the source of the imbalance problem on the Summary tab.
To display the recommendations about the objects to move so that you can rebalance the workload, click the Rebalance
Container action on the Summary tab. The recommendations indicate that you move one or more virtual machines to
another host. When you click OK, a pop-up message provides a link to track the status of the action in Recent Tasks.
VMware by Broadcom  3237

---
## page 3238

 VMware Cloud Foundation 9.0
The action moves the virtual machines identified in the recommendation to the host machine that has a low workload or
stress. You can view the status of the action in the list of recent tasks in Administration > Control Panel, and then click
the Recent Tasks tab. You can also use the vSphere Web Client to view the status of the action and the performance for
the host.
After the action runs and VCF Operations performs several collection cycles, view the workload on the data center to
confirm that the workload was rebalanced and that the alert is gone.
Where You Run the Action
You can run the Rebalance Container action from the Actions menu for a data center or custom data center, or you can
provide it as a suggested action on an alert.
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• From the left menu click Inventory, select an object, click the Details tab, click Views, and select a view of type List.
• From the left menu click Inventory, select an object, click the Details tab, and select an object in the List tab.
• From the left menu click Operations > Configurations, then click the Objects tab, and select an object in the list.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Recommendations
Review the following information about the hosts and virtual machines to ensure that you are submitting the action for the
correct objects.
Option Description
Virtual Machine Name of the virtual machine on the host that is experiencing an
excessive workload.
Source Cluster Name of the cluster on which the virtual machine is running.
Datastores Datastore associated with the virtual machine.
Destination Cluster Cluster where the virtual machine is to be moved. DRS selects the
host automatically.
Reason Describes the action to be taken and the reason why the move
is suggested. For example, the recommendation is to move part
of the workload on the cluster to another cluster to reduce the
imbalance in CPU demand.
Parent vCenter Identifies the vCenter Server adapter associated with the affected
cluster.
After you click OK, the next dialog box provides the task ID and a link to the task list.
Table 998: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
VMware by Broadcom  3238

---
## page 3239

 VMware Cloud Foundation 9.0
Delete Idle VM Action
The Delete Idle VM action in VCF Operations removes from your vCenter instances those selected virtual machines that
are in an idle state. Use this action to reclaim redundant resources.
How the Action Works
The Delete Idle VM action removes from your vCenter instances those virtual machines that are powered on, but that are
in an idle state.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu, click Inventory, select an object, click the Details tab, and click Views.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Menu Items
Review the following information about the virtual machines to ensure that you are submitting the action for the correct
objects.
Menu Items Description
Name Name of the virtual machine as it appears in the environment
inventory.
Host Name of the host on which the virtual machine is running.
Parent vCenter Parent vCenter instance where the virtual machine resides.
After you click Begin Action, the next dialog box provides the task ID and a link to the task list.
Table 999: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
Set DRS Automation Action
You can monitor and configure the vSphereDistributed Resource Scheduler (DRS) automation rules from VCF
Operations. DRS monitors and allocates the resources in your environment, and balances the computing capacity across
your hosts and virtual machines.
How the Action Works
The Set DRS Automation action monitors and configures DRS automation rules. With the Set DRS Automation action, you
can activate and deactivate DRS.
If VCF Automation manages any of the virtual machines in your environment, the Set DRS Automation action is not
available for that object.
VMware by Broadcom  3239

---
## page 3240

 VMware Cloud Foundation 9.0
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu click Inventory, select an object, click the Details tab, and click Views.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Menu Items
To ensure that you are submitting the correct action for the correct objects, review the following information about the
clusters.
Menu Items Description
Name Name of the cluster in the vCenter instance.
Automation Level Level of DRS automation. When DRS is fully automated on the
selected cluster, you can run the Set DRS Automation action.
Migration Threshold Recommendations for the migration level of virtual machines.
Migration thresholds are based on DRS priority levels, and are
computed based on the workload imbalance metric for the cluster.
Parent vCenter Parent vCenter instance where the cluster resides.
After you click Begin Action, the next dialog box provides the task ID and a link to the task list.
Table 1000: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
Execute Custom Script
To troubleshoot particular processes, you can upload a script or run a command to receive specific information. You can
view the standard output or standard error as applicable.
Where You Run the Action
For supported objects and object levels, in the main menu, select the Inventory tab and then select the relevant VM from
the Inventory tree. This action is available from the Actions menu just below the top menu in VCF Operations.
Prerequisites
• VMware Tools must be installed and running on the VM. For details see KB 75122
• vCenter Server is activated with the successful discovery of VMs.
• The VM must be powered on and connected.
• When you perform the Execute Custom Script action and you need to use command/utilities, for those
commands that need a sudo user password provision, the full path of command/utility must be added to the
NOPASSWD commands list.
The configured vCenter Server user must have the following privileges:
VMware by Broadcom  3240

---
## page 3241

 VMware Cloud Foundation 9.0
• key: VirtualMachine.GuestOperations.Execute, Localization: Guest operations -> Guest operation program execution
• key: VirtualMachine.GuestOperations.Query, Localization: Guest operations -> Guest operation queries
• The ESX instance that hosts the VMs where scripts should be run, must have HTTPS access to port 443 from the
collector node on which the vCenter Server adapter instance is configured.
• The provided user in the script must have read and write privileges to the temp directory. For Windows systems, the
path can be taken from the environment variable TEMP. For Linux systems, it is /tmp and/or /var/tmp.
Action Options
Enter the VM credentials to authenticate even when the VM guest OS authentication status is "Success". You can run a
script by entering it directly or by uploading a script file by optionally providing arguments.
Option Description
Upload File Use this option to browse and upload the script that you want to
run.
File Browse and upload the script file.
Args List the arguments in the script.
Command Select the option and enter a command in the text box.
Timeout Script execution timeout on VMs. Script execution continues even
if the dialog box is closed. You can verify the status from Recent
Tasks.
Execute Runs the script or command.
stdout Displays the standard output.
stderr Displays errors, if any.
Get Top Processes Action
The Get Top Processes action is used for troubleshooting process issues and resource issues related to the applications
of the virtual machine.
How the Action Works
The Get Top Processes action, provides the status of top 10 processes for the selected virtual machine. You can
troubleshoot issues related to the resources that are affecting the applications in the virtual machine.
By default, the details of top 10 processes are displayed for the selected virtual machine. You can change the number of
processes and view the details for top N processes where N is between 1-100. You have the option to view the processes
based on CPU and Memory.
The Get Top Processes action is run on both Windows virtual machine and Linux virtual machine. You can view the
summary information for the commands only in a Linux virtual machine.
Where You Run the Action
For supported objects and object levels, in the main menu, select the Environment tab and then select the relevant VM
from the Inventory tree. This action is available from the Actions menu just below the top menu in VCF Operations.
Prerequisites
• VMware Tools must be installed and running on the VM. For details see KB 75122
• Service discovery is activated with the successful discovery of VMs.
• The VM must be powered on and connected.
VMware by Broadcom  3241

---
## page 3242

 VMware Cloud Foundation 9.0
Action Options
You must enter the VM credentials to authenticate when the VM is monitored in a credential-less mode or when the VM is
monitored in a credential-based mode where the user is not authenticated. To ensure that you are taking the right action,
review the following information.
Option Description
Number of Processes Displays the number of processes for which the details are
displayed.
Refresh Displays new data about processes, when you change the value
for the number of processes.
Command Displays the name of the application
PID Displays the process ID.
CPU Displays the CPU usage in percentage for Linux VMs.
Displays the CPU usage in seconds for Windows VMs. The count
starts when you start the operating system in the VM .
Mem (%) Displays the Memory usage in KB.
User Displays the user name.
Status Displays the process status. It can be in one these states:
• For Linux - I, R, S
• For Windows - Unknown, Running, and Sleeping
Run Displays data about the specified numbers of processes.
Move Virtual Machine Action
You can use the Move VM action to move virtual machines from one host and datastore to another host and datastore to
balance the workload in your environment.
How the Action Works
When you initiate this action, the Move VM wizard opens and scopes the possible destinations. You select the destination
host and datastore from the list of available destinations.
To see all destinations, you must have view access to the following object types:
• Scope object, which includes a vCenter, data center, custom data center, or cluster.
• Host in the scope object.
• Datastore in the host.
The destinations include combinations of objects for the move, such as a specific host and datastore, or a different host
with the same datastore. You select one of the available combinations. If your environment includes many destination
objects, such as many hosts or datastores, enter text in the filter text box to search for specific destination objects.
The All Filters option helps you to move the VM according to the following action option:
• Destination Host
• Destination Datastore
• Will it Fit
• VM PowerOff Required
• Affinity Rules
VMware by Broadcom  3242

---
## page 3243

 VMware Cloud Foundation 9.0
VCF Operations uses vSphere DRS rules that you define in vCenter to help determine good placement decisions for your
virtual machines in the move action. The Affinity Rules column indicates whether those rules are violated by the Move VM
action.
Important:  Do not attempt to move virtual machines that are members of a vApp, because the vApp can become
nonfunctional. Instead, add affinity rules for these virtual machines to keep them together so that the Move VM and
Rebalance Container actions will ignore them.
To initiate the action, you click the Begin Action button.
When you finish the wizard, VCF Operations displays a dialog box to indicate that the action has started. To track the
status of the action, click the link in the dialog box and view the state of the action in Recent Tasks.
Moving Virtual Machines is Not Allowed Across Data Centers
When you attempt to use the Move VM action to move a virtual machine across data centers, VCF Operations must be
able to identify the matching network and storage objects for the destination data center. Network objects include VMware
virtual switches and distributed virtual switches. Storage objects include datastores and datastore clusters.
Moving a virtual machine across data centers requires VCF Operations to move the virtual machine files and change
the virtual machine network configuration. VCF Operations does not currently move the virtual machine files across
datastores, nor does it change the virtual machine network configuration. As a result, VCF Operations does not allow you
to move virtual machines across data centers.
When you use the Move VM action, be aware of the following behavior:
• If you select a single virtual machine, VCF Operations displays the data center where the virtual machine resides.
• If you select multiple virtual machines, but those virtual machines do not share a common data center, the Move VM
action does not display the data centers, and the Move VM action does not appear in the actions menu.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu, click Inventory, select an object, click the Details tab, and then click the Views tab.
• From the left menu, click Inventory, select an object, click the Details tab, and select an object from the List tab.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
Review the following information about the virtual machines to ensure that you are submitting the action for the correct
objects.
Option Description
Priority Indicates the priority of the proposed move destination. When the
action is automated, the proposed destination with priority of 1 is
automatically selected.
Destination Host Name of the host to which the virtual machine will be moved.
Current CPU Workload Amount of CPU in GHz available on the host.
Current Memory Workload Amount of memory in GB available on the host.
Destination Datastore Datastore to which the virtual machines storage will be moved.
Current Disk Space Workload Amount of disk space available on the datastore.
VMware by Broadcom  3243

---
## page 3244

 VMware Cloud Foundation 9.0
Option Description
Will it fit Calculated estimation of whether the virtual machine fits on the
selected destination.
VM Power Off Required When set to No, the action does not power off the virtual machine
before the move. When set to Yes, the action powers off the
virtual machine before the move takes place, and powers on the
virtual machine after the move is complete. If VMware Tools is
installed, a guest OS shutdown is used to power off the virtual
machine.
Affinity Rules Indicates whether vSphere DRS rules exist, as defined in vCenter.
For example, a rule might exist to keep virtual machines together,
and another rule might exist to separate virtual machines.
This column indicates the following status.
• Empty. vSphere DRS rules are not defined.
• Green check mark. The move of virtual machines does not
violate affinity rules.
• Red circle with bar. The move of virtual machines does break
affinity rules. If you choose to break the affinity rules, you must
resolve any problems manually.
Affinity Rule Details Identifies the virtual machine and the vSphere DRS rule name as
defined in vCenter.
After you click OK, the next dialog box provides the task ID and a link to the task list.
Table 1001: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
Power Off Virtual Machine Action
The Power Off VM action in VCF Operations stops one or more selected virtual machines that are in a powered on state.
You power off a virtual machine when you are managing resources and reclaiming wasted space.
How the Action Works
The Power Off VM action turns off the virtual machine. If VMware Tools is installed and running, the guest operating
system is shut down before the machine is powered off. If VMware Tools is not installed and running, the virtual machine
is powered off regardless of the state of the guest operating system. In this case, use this action only when you are
powering off virtual machines where stopping the guest operating system does not adversely affect the installed
applications.
If the target virtual machine is already powered off, the recent task status reports success on the machine, even though
the state of the virtual machine did not change.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
VMware by Broadcom  3244

---
## page 3245

 VMware Cloud Foundation 9.0
• From the left menu click Inventory, select an object, click the Details tab, and then click Views.
• From the left menu click Operations > Configurations, and then click the Inventory Management tile. Select an
object in the list.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
Review the following information about the virtual machines to ensure that you are submitting the action for the correct
objects.
Option Description
Selected objects Check box indicates whether the action is applied to the object. To
not run the action on one or more objects, deselect the associated
check boxes. This option is available when two or more objects
are selected.
Name Name of the virtual machine as it appears in the environment
inventory.
Power State Indicates whether the virtual machine is powered on or powered
off.
Idle VM Indicates whether the virtual machine is considered to be in the
idle state based on the configured idle virtual machine metric.
Possible values include:
• false. The virtual machine is active.
• true. The virtual machine is idle.
• unknown. VCF Operations does not have the data required to
calculate the idle metric.
Idle VM Percentage Calculated threshold of the idle virtual machine percentage based
on the configured reclaimable wasted space policy.
CPU Usage Percentage Calculated threshold of the virtual machine CPU percentage
based on the metric named cpu | usage_average.
Host Name of the host on which the virtual machine is running.
Adapter Instance Name of the VMware Adapter as it is configured in VCF
Operations. The adapter manages the communication with the
vCenter instance.
After you click OK, the next dialog box provides the task ID and a link to the task list.
Table 1002: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
Shut Down Guest Operating System for Virtual Machine Action
The Shut Down Guest OS for VM action shuts down the guest operating system and powers off the virtual machine. You
shut down a virtual machine when you are managing resources and reclaiming wasted space.
VMware by Broadcom  3245

---
## page 3246

 VMware Cloud Foundation 9.0
How the Action Works
The Shut Down Guest OS for VM action checks that VMware Tools, which is required, is installed on the target virtual
machines, then shuts down the guest operating system and powers off the virtual machine. If VMware Tools is not
installed or installed but not running, the action does not run and the job is reported as failed in Recent Tasks.
If the target virtual machine is already powered off, the recent task status reports success on the machine, even though
the state of the virtual machine did not change.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu click Inventory, select an object, click the Details tab, and click Views.
• From the left menu click Operations > Configurations, and then click the Inventory Management tile. Select an
object in the list.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
Review the following so you can be sure you are taking the right action.
Option Description
Selected objects Check box indicates whether the action is applied to the object. To
not run the action on one or more objects, deselect the associated
check boxes. This option is available when two or more objects
are selected.
Name Name of the virtual machine as it appears in the environment
inventory.
Power State Indicates whether the virtual machine is powered on or powered
off.
Idle VM Indicates whether the virtual machine is considered to be in the
idle state based on the configured idle virtual machine metric.
Possible values include:
• false. The virtual machine is active.
• true. The virtual machine is idle.
• unknown. VCF Operations does not have the data required to
calculate the idle metric.
Idle VM Percentage Calculated threshold of the idle virtual machine percentage based
on the configured reclaimable wasted space policy.
Host Name of the host on which the virtual machine is running.
Adapter Instance Name of the VMware Adapter as it is configured in VCF
Operations. The adapter manages the communication with the
vCenter instance.
After you click OK, the next dialog box provides the task ID and a link to the task list.
VMware by Broadcom  3246

---
## page 3247

 VMware Cloud Foundation 9.0
Table 1003: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
Reboot Guest OS for Virtual Machine Action
The Reboot Guest OS for VM action reboots the guest operating system and the virtual machine. You reboot a virtual
machine while managing resources or when you have new updates or configuration changes to your virtual machine.
How the Action Works
The Reboot Guest OS for VM action checks that VMware Tools, which is required, is installed on the target virtual
machines, then reboots the guest operating system and the virtual machine. If VMware Tools is not installed or installed
but not running, the action does not run, and the job is reported as failed in Recent Tasks.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu, click Inventory and select an object in the list.
• From the left menu, click Inventory, select an object, click the Details tab, and click Views.
• From the left menu, click Inventory. Select an object, click the Environment tab, and select an object in the list view.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
Review the following so you can be sure you are taking the right action.
Option Description
Selected objects Check box indicates whether the action is applied to the object. To
not run the action on one or more objects, deselect the associated
check boxes. This option is available when two or more objects
are selected.
Name Name of the virtual machine as it appears in the environment
inventory.
Host Name of the host on which the virtual machine is running.
Parent vCenter The adapter instance as configured in VCF Operations. The
adapter manages the communication with the vCenter instance.
After you click OK, the next dialog box provides the task ID and a link to the task list.
VMware by Broadcom  3247

---
## page 3248

 VMware Cloud Foundation 9.0
Table 1004: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
Power on Virtual Machine Action
To start one or more virtual machines that are in a powered off state, use the Power On VM action. You power on a virtual
machine so that you can shift resources. For example, power on a machine so that you can use it, run applications, or
verify that actions that were run on already powered down machines contribute to improved performance.
How the Action Works
The Power On VM action powers on virtual machines that are powered off. The action does not affect virtual machines
that are currently powered on.
If the target virtual machine is already powered on, the task status reports success for the machine even though the state
of the virtual machine did not change.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu click Inventory, select an object, click the Details tab, and click Views.
• From the left menu click Inventory, select an object, click the Details tab, and then click the List tab.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
To ensure that you are taking the right action, review the following information .
Option Description
Selected objects Check box indicates whether the action is applied to the object. To
not run the action on one or more objects, deselect the associated
check boxes. This option is available when two or more objects
are selected.
Name Name of the virtual machine as it appears in the environment
inventory.
Power State Indicates whether the virtual machine is powered on or powered
off.
Host Name of the host on which the virtual machine is running.
Adapter Instance Name of the VMware Adapter as it is configured in VCF
Operations. The adapter manages the communication with the
vCenter instance.
After you click OK, the next dialog box provides the task ID and a link to the task list.
VMware by Broadcom  3248

---
## page 3249

 VMware Cloud Foundation 9.0
Table 1005: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
Delete Powered Off Virtual Machine Action
The Delete Powered Off VM action in VCF Operations removes selected virtual machines that are in a powered off state
from your vCenter instances. Use this action to reclaim redundant resources.
How the Action Works
The Delete Powered Off VM action removes virtual machines from the vCenter instances. If the virtual machine is
powered on, the action does not delete the virtual machine.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu click Inventory, select an object, click the Details tab, and then click Views.
• From the left menu click Operations > Configurations, and then click the Inventory Management tile. Select an
object in the list.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
To ensure that you are submitting the action for the right objects, review the following information.
Option Description
Selected objects Check box indicates whether the action is applied to the object. To
not run the action on one or more objects, deselect the associated
check boxes. This option is available when two or more objects
are selected.
Name Name of the virtual machine as it appears in the environment
inventory.
Power State Indicates whether the virtual machine is powered on or powered
off.
Disk Space Amount of disk space currently consumed by the virtual machine.
Snapshot Space Amount of disk space currently consumed by the virtual machine
snapshots.
Memory (MB) Amount of memory allocated to the virtual machine.
CPU Count Number of CPUs currently configured for the virtual machine.
Host Name of the host on which the virtual machine is running.
Adapter Instance Name of the VMware Adapter as it is configured in VCF
Operations. The adapter manages the communication with the
vCenter instance.
VMware by Broadcom  3249

---
## page 3250

 VMware Cloud Foundation 9.0
After you click OK, the next dialog box provides the task ID and a link to the task list.
Table 1006: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
Set Memory for Virtual Machine Action
The Set Memory for VM action in VCF Operations is used to add or remove memory on virtual machines. You increase
the memory to address performance problems or decrease the memory to reclaim resources.
How the Action Works
The Set Memory for VM action perform several tasks. The action determines the power state of the target virtual
machines, takes a snapshot when you request it and powers off the machine if necessary and you request it. As well, the
action changes the memory to the new value, and returns the virtual machines their original power states.
An alternative form of the Set Memory for Virtual Machine action is available for automation. This action can run when the
virtual machine is powered on or off.
Use this version of the action if the automated action has permission to power off the virtual machine, and hot add of
memory is not activated on the virtual machine. With hot add activated, you can add memory, but you cannot remove it.
This version of the action would be required if a virtual machine is powered on and the amount of memory must be
reduced.
This version of the action has the Power Off Allowed flag set to true. You can select this Power Off Allowed version of the
action when you create or edit alerts and associate the alert with a recommendation. When the Power Off Allowed version
of this action is automated, you do not select this version of the action.
If Hot Plug is activated on the virtual machines, then power off is not required. If power off is required and VMware Tools is
installed, then the virtual machines are shut down before they are powered off.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu click Inventory, select an object, click the Details tab, and then click Views.
• From the left menu click Operations > Configurations, and then click the Inventory Management tile. Select an
object in the list.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
Review the following information about the virtual machines to ensure that you are submitting the action for the correct
objects.
VMware by Broadcom  3250

---
## page 3251

 VMware Cloud Foundation 9.0
Option Description
Selected objects Check box indicates whether the action is applied to the object. To
not run the action on one or more objects, deselect the associated
check boxes. This option is available when two or more objects
are selected.
If you modify a value, the check box is selected. The check box
must be selected to activate the OK button.
Name Name of the virtual machine as it appears in the environment
inventory.
New CPU Number of CPUs when the action is completed. If the value is
less than 1 or a value not supported for the virtual machine in
vCenter, and the virtual machine is powered on and Hot Add is
not activated, the number of CPUs does not change and Recent
Tasks shows the action as failed. If the virtual machine is powered
off when you submit an unsupported value, the task reports
success, but the virtual machine will fail when you run a power on
action.
The value that appears is the calculated suggested size. If
the target virtual machine is new or offline, this value is the
current number of CPUs. If VCF Operations has been monitoring
the virtual machine for six or more hours, depending on your
environment, the value that appears is the CPU Recommended
Size metric.
Current CPU Number of configured CPUs.
Power State Indicates whether the virtual machine is powered on or powered
off.
Power Off Allowed If selected, the action shuts down or powers off the virtual
machine before modifying the value. If VMware Tools is installed
and running, the virtual machine is shut down. If VMware Tools
is not installed or not running, the virtual machine is powered off
without regard for the state of the operating system.
In addition to whether the action shuts down or powers off a virtual
machine, you must consider whether the object is powered on and
what settings are applied.
See Working with Actions That Use Power Off section in VCF
Operations Configuration Guide. .
Snapshot Creates a snapshot before changing the number of CPUs. Use
this option if you need a snapshot to which you can revert the
virtual machine if the action does not produce the expected
results.
The name of the snapshot is supplied in the Recent Tasks
messages for the action.
If the CPU is changed with CPU Hot Plug activated, then the
snapshot is taken with the virtual machine is running, which
consumes more disk space.
Host Name of the host on which the virtual machine is running.
Adapter Instance Name of the VMware Adapter as it is configured in VCF
Operations. The adapter manages the communication with the
vCenter instance.
After you click OK, the next dialog box provides the task ID and a link to the task list.
VMware by Broadcom  3251

---
## page 3252

 VMware Cloud Foundation 9.0
Table 1007: Task ID Dialog Box
Option Description
OK To close the dialog box without further action, click OK.
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
Set Memory Resources for Virtual Machine Action
The Set Memory Resources for VM action is used to modify the memory reservation and memory limit on virtual
machines. You modify the memory reservation and limit to manage resources in your environment, either to reclaim
unused resources or to ensure that your virtual machines have the resources they need to run efficiently.
How the Action Works
The Set Memory Resources for VM action determines how memory resources are allocated to the virtual machine.
The reservation value is the minimum amount of guaranteed memory allocated for the virtual machine. The limit is the
maximum amount of memory that the virtual machine can consume.
The reservation and limit values in vCenter are set in megabytes. VCF Operations calculates and reports on memory in
kilobytes. When you run this action, the values are presented in kilobytes so that you can implement recommendations
from VCF Operations.
To run the action, all options must be configured in the dialog box for the objects on which your are running the action. If
you are changing one option to a new value, but not another option, ensure that the option that you do not want to change
is configured with the current value.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu click Inventory, select an object, click the Details tab, and then click Views.
• From the left menu click Operations > Configurations and then click the Inventory Management tile. Select an
object in the list.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
To ensure that you are submitting the action for the right objects, review the following information.
Option Description
Selected objects Check box indicates whether the action is applied to the object. To
not run the action on one or more objects, deselect the associated
check boxes. This option is available when two or more objects
are selected.
If you modify a value, the check box is selected. The check box
must be selected to activate the OK button.
Name Name of the virtual machine as it appears in the environment
inventory.
VMware by Broadcom  3252

---
## page 3253

 VMware Cloud Foundation 9.0
Option Description
New Resv (KB) Amount of memory in kilobytes reserved for the virtual machine
when the action is finished. The new reservation value must be
less than or equal to the new limit value unless your new limit is
unlimited (-1).
The reservation supports the following possible values:
• If you set the value to 0, the virtual machine is allocated only
the currently configured amount of RAM.
• If you add or remove reserved memory, the value must be
evenly divisible by 1024.
Current Resv (KB) Amount of memory in kilobytes that is configured as the
guaranteed memory for the virtual machine.
New Limit (KB) Maximum amount of memory in kilobytes that the virtual machine
can consume when the action is completed.
The limit supports the following possible values:
• If you set the value to 0, then the maximum memory is no
greater than the allocated reservation amount.
• If you set the value to -1, then the virtual machine memory is
unlimited.
• It you increase or decrease the limit, the value must be evenly
divisible by 1024.
Current Limit (KB) Maximum amount of memory that the virtual machine is currently
allowed to consume.
Host Name of the host on which the virtual machine is running.
Adapter Instance Name of the VMware Adapter as it is configured in VCF
Operations. The adapter manages the communication with the
vCenter instance.
After you click OK, the next dialog box provides the task ID and a link to the task list.
Table 1008: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
Set CPU Count for Virtual Machine Action
The Set CPU action modifies the number of vCPUs on a virtual machine. You increase the number of CPUs to address
performance problems or decrease the number of CPU to reclaim resources.
How the Action Works
The Set CPU Count action shuts down or powers off the target virtual machines. If you are decreasing the CPU count, the
action is required. This action creates a snapshot if you request it, changes the number of vCPUs based on the new CPU
count you provided, and returns the virtual machines to their original power states.
An alternative form of the Set CPU Count for Virtual Machine action is available for automation. This action can run when
the virtual machine is powered on or off.
VMware by Broadcom  3253

---
## page 3254

 VMware Cloud Foundation 9.0
Use this version of the action if the automated action has permission to power off the virtual machine, and hot add of
memory is not activated on the virtual machine. With hot add activated, you can add CPUs, but you cannot remove them.
This version of the action is required if a virtual machine is powered on and the number of CPUs must be reduced.
This version of the action has the Power Off Allowed flag set to true. You can select this Power Off Allowed version of the
action when you create or edit alerts and associate the alert with a recommendation. When the Power Off Allowed version
of this action is automated, you do not select this version of the action.
If Hot Plug is activated on the virtual machines, then power off is not required. If power off is required and VMware Tools
are installed, then the virtual machines are shut down before they are powered off.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu click Inventory, select an object, click the Details tab, and then click Views.
• From the left menu click Operations > Configurations, and then click the Inventory Management tile. Select an
object in the list.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
Review the following information about the virtual machines to ensure that you are submitting the action for the correct
objects.
Option Description
Selected objects Check box indicates whether the action is applied to the object. To
not run the action on one or more objects, deselect the associated
check boxes. This option is available when two or more objects
are selected.
If you modify a value, the check box is selected. The check box
must be selected to activate the OK button.
Name Name of the virtual machine as it appears in the environment
inventory.
New CPU Number of CPUs when the action is completed. If the value is
less than 1 or a value not supported for the virtual machine in
vCenter, and the virtual machine is powered on and Hot Add is
not activated, the number of CPUs does not change and Recent
Tasks shows the action as failed. If the virtual machine is powered
off when you submit an unsupported value, the task reports
success, but the virtual machine will fail when you run a power on
action.
The value that appears is the calculated suggested size. If
the target virtual machine is new or offline, this value is the
current number of CPUs. If VCF Operations has been monitoring
the virtual machine for six or more hours, depending on your
environment, the value that appears is the CPU Recommended
Size metric.
Current CPU Number of configured CPUs.
Power State Indicates whether the virtual machine is powered on or powered
off.
VMware by Broadcom  3254

---
## page 3255

 VMware Cloud Foundation 9.0
Option Description
Power Off Allowed If selected, the action shuts down or powers off the virtual
machine before modifying the value. If VMware Tools is installed
and running, the virtual machine is shut down. If VMware Tools
is not installed or not running, the virtual machine is powered off
without regard for the state of the operating system.
In addition to whether the action shuts down or powers off a virtual
machine, you must consider whether the object is powered on and
what settings are applied.
See Working with Actions That Use Power Off section in VCF
Operations Configuration Guide. .
Snapshot Creates a snapshot before changing the number of CPUs. Use
this option if you need a snapshot to which you can revert the
virtual machine if the action does not produce the expected
results.
The name of the snapshot is supplied in the Recent Tasks
messages for the action.
If the CPU is changed with CPU Hot Plug activated, then the
snapshot is taken with the virtual machine is running, which
consumes more disk space.
Host Name of the host on which the virtual machine is running.
Adapter Instance Name of the VMware Adapter as it is configured in VCF
Operations. The adapter manages the communication with the
vCenter instance.
After you click OK, the next dialog box provides the task ID and a link to the task list.
Table 1009: Task ID Dialog Box
Option Description
OK To close the dialog box without further action, click OK.
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
Set CPU Resources for Virtual Machine Action
The Set CPU Resources for VM action is used to modify the CPU reservation and CPU limit on virtual machines. You
modify the CPU reservation and limit to manage workload demands in your environment.
How the Action Works
The Set CPU Resources for VM action determines how CPU resources can be allocated to the virtual machines. The
reservation limit is the minimum amount of guaranteed CPU resources allocated to the virtual machine. The limit is the
maximum amount of CPU resources that the virtual machine can consume.
To run the action, all options where you configure a value must contain a value for the objects that you want to change. If
you are changing one option to a new value, but not another option, ensure that the option that you are not changing is
configure with the current value.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
VMware by Broadcom  3255

---
## page 3256

 VMware Cloud Foundation 9.0
• Embedded just below the top menu.
• From the left menu click Inventory, select an object, click the Details tab, and click Views.
• From the left menu click Operations > Configuration, and then click the Inventory Management tab. Select an
object in the list.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
To ensure that you are submitting the action for the right objects, review the following information.
Option Description
Selected objects Check box indicates whether the action is applied to the object. To
not run the action on one or more objects, deselect the associated
check boxes. This option is available when two or more objects
are selected.
If you modify a value, the check box is selected. The check box
must be selected to activate the OK button.
Name Name of the virtual machine as it appears in the environment
inventory.
New Resv (MHz) Amount of CPU resources in megahertz reserved for the virtual
machine when the action is finished. The new reservation value
must be less than or equal to the new limit value unless your new
limit is unlimited (-1).
The reservation supports the following possible values:
• If you set the value to 0, the virtual machine is allocated only
the configured CPU consumption level.
• If you add or removed reserved CPU consumption, supply a
positive integer unless you set the value to 0.
Current Resv (MHz) Amount of CPU resources that is configured as the guaranteed
CPU resources for the virtual machine.
New Limit (MHz) Maximum amount of CPU consumption in megahertz that the
virtual machine can consume when the action is completed.
The limit supports the following possible values:
• If you set the value to 0, the maximum CPU consumption is
not greater than the allocated reservation amount.
• If you set the value to -1, then the virtual machine CPU
consumption is unlimited.
• If you add or remove CPU consumption limits, supply a
positive integer, unless you set the value to 0 or -1.
Current Limit (MHz) Maximum amount of CPU that the virtual machine can consume.
Host Name of the host on which the virtual machine is running.
Adapter Instance Name of the VMware Adapter as it is configured in VCF
Operations. The adapter manages the communication with the
vCenter instance.
After you click OK, the next dialog box provides the task ID and a link to the task list.
VMware by Broadcom  3256

---
## page 3257

 VMware Cloud Foundation 9.0
Table 1010: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
Set CPU Count and Memory for Virtual Machine Action
The Set CPU Count and Memory for VM action is used to add or remove CPUs and memory on virtual machines with
only one power off of the virtual machines to perform the combined actions. You modify the CPU and memory to address
performance problems or to reclaim resources.
How the Action Works
The Set CPU Count and Memory action powers off the target virtual machines. The action also creates a snapshot
when requested and changes the number of vCPUs and memory based on the new CPU count and memory values you
provided. As well, the action returns the virtual machines their original power states.
An alternative form of the Set CPU Count and Memory for Virtual Machine action is available for automation. This version
of the action has the Power Off Allowed flag set to true so that the action is available for automation and can run when
the virtual machine is in the powered on state. You can select the Power Off Allowed version of the action when you
create or edit alerts and associate the alert with a recommendation. When the Power Off Allowed version of this action is
automated, you do not select this version of the action.
If Hot Plug is activated on the virtual machines, then power off is not required. If power off is required and VMware Tools
are installed, then the virtual machines are shut down before they are powered off.
To run the action, all options where you configure a value must contain a value for the objects that you want to change. If
you are changing one option to a new value, but not another option, ensure that the option that you are not changing is
configure with the current value.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu click Inventory, select an object, click the Details tab, and click Views.
• From the left menu click Operations > Configurations, and then click the Inventory Management tile. Select an
object in the list.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
Review the following information about the virtual machines to ensure that you are submitting the action for the correct
objects.
Option Description
Selected objects Check box indicates whether the action is applied to the object. To
not run the action on one or more objects, deselect the associated
check boxes. This option is available when two or more objects
are selected.
VMware by Broadcom  3257

---
## page 3258

 VMware Cloud Foundation 9.0
Option Description
If you modify a value, the check box is selected. The check box
must be selected to activate the OK button.
Name Name of the virtual machine as it appears in the environment
inventory.
New CPU Number of CPUs when the action is completed. If the value is
less than 1 or a value not supported for the virtual machine in
vCenter, and the virtual machine is powered on and Hot Add is
not activated, the number of CPUs does not change and Recent
Tasks shows the action as failed. If the virtual machine is powered
off when you submit an unsupported value, the task reports
success, but the virtual machine will fail when you run a power on
action.
The value that appears is the calculated suggested size. If
the target virtual machine is new or offline, this value is the
current number of CPUs. If VCF Operations has been monitoring
the virtual machine for six or more hours, depending on your
environment, the value that appears is the CPU Recommended
Size metric.
Current CPU Number of configured CPUs.
Power State Indicates whether the virtual machine is powered on or powered
off.
Power Off Allowed If selected, the action shuts down or powers off the virtual
machine before modifying the value. If VMware Tools is installed
and running, the virtual machine is shut down. If VMware Tools
is not installed or not running, the virtual machine is powered off
without regard for the state of the operating system.
In addition to whether the action shuts down or powers off a virtual
machine, you must consider whether the object is powered on and
what settings are applied.
See Working with Actions That Use Power Off section in VCF
Operations Configuration Guide. .
Snapshot Creates a snapshot before changing the number of CPUs. Use
this option if you need a snapshot to which you can revert the
virtual machine if the action does not produce the expected
results.
The name of the snapshot is supplied in the Recent Tasks
messages for the action.
If the CPU is changed with CPU Hot Plug activated, then the
snapshot is taken with the virtual machine is running, which
consumes more disk space.
Host Name of the host on which the virtual machine is running.
Adapter Instance Name of the VMware Adapter as it is configured in VCF
Operations. The adapter manages the communication with the
vCenter instance.
After you click OK, the next dialog box provides the task ID and a link to the task list.
VMware by Broadcom  3258

---
## page 3259

 VMware Cloud Foundation 9.0
Table 1011: Task ID Dialog Box
Option Description
OK To close the dialog box without further action, click OK.
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
Delete Unused Snapshots for Virtual Machine Action
The Delete Unused Snapshots for Virtual Machines action in VCF Operations deletes snapshots that are older than the
specified age from your datastores. Deleting unused snapshots reclaims wasted space in your environment.
How the Action Works
The Delete Unused Snapshots for Virtual Machine action comprises two dialog boxes. The first dialog box allows you to
select the snapshot age criteria, which must be greater than one day. The second step allows you to select the snapshots
to delete, and runs the Delete Unused Snapshots for Virtual Machine action.
The number of days that you specify for each virtual machine is the age of the snapshots based on the creation date.
The Delete Unused Snapshots for Virtual Machine action retrieves the snapshot and displays the snapshot name, space
consumed, and location so that you can evaluate the snapshots before you delete them.
When you click Begin Action, VCF Operations displays a dialog box to indicate that the action has started. To track the
status of the action, click the link in the dialog box and view the state of the action in Recent Tasks.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
• From the left menu click Inventory, select an object, click the Details tab, and then click the Views tab.
• From the left menu click Inventory, select an object, click the Details tab, and then click the List tab.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
To ensure that you are submitting the action for the right objects, review the following information.
You first retrieve snapshots based on age, then select the snapshots to delete.
Table 1012: Retrieve Snapshots
Option Description
Name Name of the virtual machine on which you are running the Delete Unused Snapshots for VM action.
Days Old Age of the snapshots to be deleted. This action retrieves snapshots for the virtual machine that are older than one
day.
Host Name of the host with which the virtual machine is associated.
Parent vCenter Name of the VMware Adapter as it is configured in VCF Operations. The adapter manages the communication with
the vCenter instance.
Select the snapshots to delete.
VMware by Broadcom  3259

---
## page 3260

 VMware Cloud Foundation 9.0
Table 1013: Delete Snapshots
Option Description
Selected objects Check box indicates whether the action is applied to the object. To not run the action on one or more
objects, deselect the associated check boxes. This option is available when two or more objects are
selected.
VM Name Name of the virtual machine from which the snapshot was created.
Snapshot Name Name of the snapshot in the datastore.
Snapshot Space (MB) Number of megabytes consumed by the snapshot.
Snapshot Create Time Date and time when the snapshot was created.
Snapshot Age Age of the snapshot in days.
Datacenter Name Name of the data center with which the datastore is associated.
Datastore Name Name of the datastore where the snapshot is managed.
Host Name Name of the host with which the datastore is associated.
After you click OK, the next dialog box provides the task ID and a link to the task list.
Table 1014: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
OK To close the dialog box without further action, click OK.
The Delete Unused Snapshots action creates a job for the retrieve snapshots action, and a job for the delete snapshots
action.
Delete Unused Snapshots for Datastore Action
The Delete Unused Snapshots for Datastore action in VCF Operations deletes snapshots that are older than the specified
age from your datastores. Deleting unused snapshots reclaims wasted space in your environment.
How the Action Works
The Delete Unused Snapshots for Datastore action comprises two dialog boxes. The first dialog box allows you to select
the snapshot age criteria, which must be greater than one day. The second step allows you to select the snapshots to
delete, and runs the Delete Unused Snapshots for Datastore action.
The number of days that you specify for each datastore is the age of the snapshots based on the creation date. The
Delete Unused Snapshots dialog box provides details regarding snapshot name, space consumed, and location so that
you can evaluate the snapshots before you delete them.
When you click Begin Action, VCF Operations displays a dialog box to indicate that the action has started. To track the
status of the action, click the link in the dialog box and view the state of the action in Recent Tasks.
Where You Run the Action
For the supported objects and object levels, this action is available in the following locations in VCF Operations:
• Embedded just below the top menu.
VMware by Broadcom  3260

---
## page 3261

 VMware Cloud Foundation 9.0
• From the left menu, click Inventory, select an object, click the Details tab, and then click the List tab.
• From the left menu click Operations > Configurations, and then click the Inventory Management tile. Select an
object in the list.
• In configured alert recommendations.
• In the Object List and Topology Graph dashboard widgets.
Action Options
To ensure that you are submitting the action for the right objects, review the following information.
You first retrieve snapshots based on age, then select the snapshots to delete.
Table 1015: Retrieve Snapshots
Option Description
Name Name of the datastore on which you are running the delete snapshot action.
Days Old Age of the snapshots to be deleted. This action retrieves snapshots for the datastore that are
older than one day.
Host Name of the host with which the datastore is associated.
Parent vCenter Name of the VMware Adapter as it is configured in VCF Operations. The adapter manages the
communication with the vCenter instance.
Select the snapshots to delete.
Table 1016: Delete Snapshots
Option Description
Selected objects Check box indicates whether the action is applied to the object. To not run the action on one or more
objects, deselect the associated check boxes. This option is available when two or more objects are
selected.
Datastore Name Name of the datastore where the snapshot is managed.
Snapshot Name Name of the snapshot in the datastore.
Snapshot Space (MB) Number of megabytes consumed by the snapshot.
Snapshot Create Time Date and time when the snapshot was created.
Snapshot Age Age of the snapshot in days.
Datacenter Name Name of the data center with which the datastore is associated.
Host Name Name of the host with which the datastore is associated.
VM Name Name of the virtual machine from which the snapshot was created.
After you click OK, the next dialog box provides the task ID and a link to the task list.
Table 1017: Task ID Dialog Box
Option Description
Recent Tasks To view the status of the job and verify that the job finished, click
Recent Tasks.
VMware by Broadcom  3261

---
## page 3262

 VMware Cloud Foundation 9.0
Option Description
OK To close the dialog box without further action, click OK.
The Delete Unused Snapshots action creates a job for the retrieve snapshots action, and a job for the delete snapshots
action.
Power On, Power Off, and Reboot Actions
You can run Power On, Power Off, and Reboot actions for AWS, Azure, and GCP using VCF Operations. These actions
allow you to manage your objects and respond quickly to alerts. You can power on an instance to start collecting data,
run applications, or verify the actions that were run on already powered-down machines. You can power off or reboot an
instance to manage resources and reclaim wasted space.
• To run actions for AWS, ensure your account ID has the following privileges: ec2:StartInstances, ec2:StopInstances
, and ec2:RebootInstances.
• To run actions for Azure, ensure you have one of the following privileges: contributor, owner, virtual machine
contributor, and avere contributor.
• To run actions for GCP, ensure you have one of the following privileges: owner, compute admin, and Compute
Instance Admin (v1).
1. To perform actions on a single instance:
a) From the left menu, click Administration > Integrations.
b) In the Accounts tab, click the vertical ellipses against the AWS, Microsoft Azure, or GCP Cloud Account, and then
select Object Details.
The Object Browser page is displayed.
c) Locate the EC2 Instance, Azure Virtual Machine, or CE Instance and click Actions.
2. Optional: To perform actions on multiple instances at once:
a) From the left menu click Inventory.
b) Navigate to the AWS, Microsoft Azure, or GCP instance and filter by object type.
c) Select multiple objects and click the Actions icon.
3. Select one of the following actions.
The Actions vary based on the instance you are using.
Note:  To start an instance that is in a powered-off state, use the Power On action. The Power Off and Reboot actions
appear only when the instance is in the Power On state.
Accounts Actions
AWS: EC2 Instance • Power On Instance
• Power Off Instance
• Reboot Instance
Note:  These actions are available only if you activate actions
while configuring an AWS account. For more information, see
the "Add a Cloud Account for AWS" topic, in the VCF Operations
Configuration Guide.
Microsoft Azure: Azure Virtual Machine • Power On VM
• Power Off VM
• Reboot VM
VMware by Broadcom  3262

---
## page 3263

 VMware Cloud Foundation 9.0
Accounts Actions
Note:  These actions are available only if you activate actions
while configuring a Microsoft Azure account. For more information,
see the "Add a Cloud Account for Microsoft Azure" topic, in the
VCF Operations Configuration Guide.
GCP: CE Instance • Power On CE Instance
• Power Off CE Instance
• Reboot CE Instance
Note:  These actions are available only if you activate actions
while configuring a GCP account. For more information, see the
"Configuring Google Cloud Platform" topic, in the VCF Operations
Configuration Guide.
4. Click Begin Action and then, click OK.
Click Recent Tasks under Administration > Control Panel to verify the status of the action.
Troubleshoot Actions in VCF Operations
If you are missing data or cannot run actions from VCF Operations, review the troubleshooting options.
Verify that your vCenter Adapter is configured to connect to the correct vCenter instance, and configured to run actions.
Verify that your vCenter Adapter is configured to connect to the correct vCenter instance, and configured to run actions.
Actions Do Not Appear on Object
An action might not appear on an object, such as a host or virtual machine, because VCF Automation is managing that
object.
Actions such as Rebalance Container might not appear in the drop-down menu when you view the actions for your data
center.
• If a data center is managed by VCF Automation, actions do not appear.
• If a data center is not managed by VCF Automation, you can act on the virtual machines that VCF Automation is not
managing.
When VCF Automation manages the child objects of a data center or custom data center container, the actions that are
normally available on those objects do not appear. They are not available because the action framework excludes actions
on objects that VCF Automation manages. You cannot turn on or turn off the exclusion of actions on objects that VCF
Automation manages. This behavior is normal.
If you removed the VCF Automation adapter instance, but did not select the Remove related objects check box, the
actions are still disabled.
Make actions available on the objects in your data center or custom data center in one of two ways. Either confirm that
VCF Automation is not managing the objects, or perform the steps in this procedure to remove the VCF Automation
adapter instance.
1. To allow actions on an object, go to your VCF Automation instance.
2. Perform the action in VCF Automation, such as to move a virtual machine.
Missing Column Data in Actions Dialog Boxes
Data is missing for one or more objects in an Actions dialog box, making it difficult to determine if you want to run the
action.
When you run an action one or more objects, some of the fields are empty.
There are two possible causes: 1) the VMware vSphere adapter has not collected the data from the vCenter instance that
manages the object. 2) the current VCF Operations user does not have privileges to view the collected data for the object.
VMware by Broadcom  3263

---
## page 3264

 VMware Cloud Foundation 9.0
1. Verify that VCF Operations is configured to collect the data.
2. Verify that you have the privileges necessary to view the data.
Missing Column Data in the Set Memory for VM Dialog Box
The read-only data columns do not display the current values, which makes it difficult to specify properly a new memory
value.
Current (MB) and Power State columns do not display the current values, which are collected for the managed object.
The adapter responsible for collecting data from the vCenter on which the target virtual machine is running has not run a
collection cycle and collected the data. This omission can occur when you recently created an VMware adapter instance
for the target vCenter and initiated an action. The VMware vSphere adapter has a five-minute collection cycle.
1. After you create a VMware adapter instance, wait an extra five minutes.
2. Rerun the Set Memory for VM action.
The current memory value and the current power state appear in the dialog box.
Host Name Does Not Appear in Action Dialog Box
When you run an action on a virtual machine, the host name is blank in the action dialog box.
When you select virtual machine on which to run an action, and click the Action button, the dialog box appears, but the
Host column is empty.
Although your user role is configured to run action on the virtual machines, you do not have a user roll that provides you
with access to the host. You can see the virtual machines and run actions on them, but you cannot see the host data for
the virtual machines. VCF Operations cannot retrieve data that you do not have permission to access.
You can run the action, but you cannot see the host name in the action dialog boxes.
Monitor Recent Task Status
The Recent Task status includes all the tasks initiated from VCF Operations. You use the task status information to verify
that your tasks finished successfully or to determine the current state of tasks.
You ran at least one action as part of an alert recommendation or from one of the toolbars. See Run Actions from Toolbars
in VCF Operations.
You can monitor the status of tasks that are started when you run actions, and investigate whether a task finished
successfully.
1. From the left menu, click Administration > Control Panel, and then select the Recent Tasks  tile.
2. To determine if you have tasks that are not finished, click the Status column and sort the results.
Option Description
In Progress Indicates running tasks.
Completed Indicates finished tasks.
Failed Indicates incomplete tasks on at least one object when started
on multiple objects.
Maximum Time Reached Indicates timed out tasks.
3. To evaluate a task process, select the task in the list and review the information in the Details of Task Selected pane.
The details appear in the Messages pane. If the information message includes No action taken, the task finished
because the object was already in the requested state.
4. To view the messages for an object when the task included several objects, select the object in the Associated Objects
list.
To clear the object selection so that you can view all the messages, press the space bar.
VMware by Broadcom  3264

---
## page 3265

 VMware Cloud Foundation 9.0
Troubleshoot tasks with a status of Maximum Time Reached or Failed to determine why a task did not run
successfully. See Troubleshoot Failed Tasks.
Recent Tasks in VCF Operations
The status of the tasks that were recently initiated from VCF Operationsappears in the Recent Task list. You can
determine whether a task is finished, still in process, or failed.
How Recent Tasks Work
The Recent Tasks page reports on logged task events, and the log entries appear in the messages area so that you can
troubleshoot failed tasks.
Where You View Recent Tasks
From the left menu, select Administration, then click Recent Tasks under Control Panel.
Recent Task Options
Review the information in the task list to determine if a task is completed or if you must troubleshoot a failed task. To see
the details about a task, select the task in the list and review the associated objects and task messages.
Table 1018: Task List
Option Description
Export Exports the selected task to an XML file.
The exported information, which includes the messages, is useful
when you are troubleshooting a problem.
Edit Properties Determines how long the recent task data is retained in your
system.
Set the number of days that VCF Operations keeps the data, after
which it is purged from the system. The default value is 90 days.
Status drop-down menu Filters the list based on the status value.
All Filters Filters the list based on the selected column and the provided
values. You can filter the tasks based on the following criteria.
• Task
• Started Time
• Completed Time
• Automated
• Object Name
• Object Type
• Event Source
• Source Type
• Submitted By
• Task ID
Filter (Object Name) Limits the tasks in the list to those that match the entered string.
The search is based on a partial entry. For example, if you enter
vm, objects such as vm001 and acctvm_east are included.
Task Name of the task.
For example, Set CPU Count for VM.
Status State of the task.
Possible states include the following values:
VMware by Broadcom  3265

---
## page 3266

 VMware Cloud Foundation 9.0
Option Description
• Completed. Task completed successfully on the target objects.
• In Progress. Task is running on the target objects.
• Failed. Task failed to run on the target objects. If the task
started, the reasons for failure might include a faulty script, a
script timed out, or actions are not taken. If the task did not start
and immediately reports as failed, the reasons might include
that the task was not able to start or the script was not found.
If the task was not initiated on the target object, it might have
failed because of communication or authentication errors.
• Maximum Time Reached. Task is running past the amount of
time that is the default or configured value. To determine the
status, you must troubleshoot the initiated action.
• Not Dispatched. The action adapter was not found.
• Started. Task is initiated on the object.
• Unknown. An error occurred while running the action, but the
error was not captured in the task logs. To investigate this
status further, check the VCF Operations support logs for the
vCenter Adapter, available in the Administration area, and
check the target system.
Started Time Date and time when the task started.
Completed Time Date and time when the task finished.
A completed date does not appear if the task failed or if the
maximum timeout is reached.
Automated Indicates whether the action in the task list is automated, indicated
by Yes or No.
Object Name Object on which the task was started.
Object Type Type of object on which the task was started.
Event Source The UUID or the name of the event that triggered the action
automatically. when an event is triggered that is associated to the
recommendation, it triggers the action without the user intervention.
For example, you can automate Alert recommendations that have
an associated action. Automation is disabled by default. You
configure automation in the Override Alert / Symptom Definitions
area of a policy when you create or edit the policy in Operations >
Configurations, and then click the Policy Definition tile.
An administrator who has the Automation role has permission to
automate actions in the Override Alert / Symptom Definitions
area of the policy workspace.
Source Type Authentication source that the user who started the task used when
accessing VCF Operations.
Submitted By Name of the user who initiated the task. This column displays the
automationAdmin user account for automated actions that are
triggered by alerts.
Task ID ID generated when the task, which included one or more actions,
was started.
The task ID is unique for the task for each adapter. If a task
includes tasks that ran using two adapters, you see two task IDs.
If the task is a delete snapshot action, two task IDs are generated.
One ID is for the retrieve snapshots based on date task, and the
other ID is for the delete selected snapshots task.
VMware by Broadcom  3266

---
## page 3267

 VMware Cloud Foundation 9.0
The Associated Objects are the objects on which the selected task ran.
Table 1019: Associated Objects for Selected Task Details
Option Description
Object Name Detailed list of objects that are included in the task selected in the
task list.
If the task ran on only one object, the list includes one object.
If the task ran on multiple objects, each object is listed on a
separate row.
Object Type Type of object for each object name.
Status Current state of the task.
The following are columns displayed for a Workload Optimization task
Source Cluster The source Cluster from which the VM is moved during Workload
Optimization.
Destination Cluster The destination Cluster to which the VM is moved during
Workload Optimization.
Source Host The source Host from which the VM is moved during Workload
Optimization.
Destination Host The destination Host to which the VM is moved during Workload
Optimization.
Source Datastore The source Datastore from which the VM is moved during
Workload Optimization.
Destination Datastore The destination Datastore to which the VM is moved during
Workload Optimization.
Completion Date The date when the task was completed.
The Messages are the log of the task as it ran. If the task does not finish successfully, use the logs to identify problems.
Table 1020: Messages for Selected Task Details
Severity drop-down menu Limits the messages based on the Severity value.
Filter (Message) Limits the message in the list to those that match the entered
string.
The search is based on a partial entry. For example, if you enter
id, then messages that contain Task ID and the phrase did
not complete are included.
Severity Message level in the logs.
The severity includes the following values:
• All. Displays all the messages.
• Error. Messages generated during a task failure.
• Warning. Messages generated as warning when the task is in
progress.
• Information. Messages added to logs as the task is processed.
Time Date and time the entry was added to the log.
VMware by Broadcom  3267

---
## page 3268

 VMware Cloud Foundation 9.0
Message Text of the log entry.
Use the information in the message to determine why a task
failed, and to begin to troubleshoot and resolve the failure.
The messages appear with the most recent entry at the top of the
list if you do not sort the columns.
Troubleshoot Failed Tasks
If tasks fail to run in VCF Operations, review the Recent Tasks page and troubleshoot the task to determine why it failed.
This information is a general procedure for using the information in Recent Tasks to troubleshoot problems identified in the
tasks.
Determine If a Recent Task Failed
The Recent Tasks provide the status of action tasks initiated from VCF Operations. If you do not see the expected results,
review the tasks to determine if your task failed.
1. From the left menu, click Administration > Control Panel, then click the Recent Tasks tab.
2. Select the failed task in the task list.
3. In the Messages list, locate the occurrences of Script Return Result: Failure and review the information
between this value and <-- Executing:[script name] on {object type}.
Script Return Result is the end of action run and <-- Executing indicates the beginning. The information
provided includes the parameters that are passed, the target object, and unexpected exceptions that you can use to
identify the problem.
Troubleshooting Maximum Time Reached Task Status
An action task has a Maximum Time Reached status and you do not know the status of the task.
The Recent Tasks list indicates that a task had a status of Maximum Time Reached.
The task is running past the amount of time that is the default or configured value. To determine the latest status, you
must troubleshoot the initiated action.
The task is running past the amount of time that is the default or configured value for one of the following reasons:
• The action is exceptionally long running and did not finish before the threshold timeout was reached.
• The action adapter did not receive a response from the target system before reaching the timeout. The action might
have completed successfully, but the completion status was not returned to VCF Operations.
• The action did not start correctly.
• The action adapter might have an error and be unable to report the status.
To determine whether the action completed successfully, check the state of the target object. If it did not complete,
continue investigating to find the root cause.
 Troubleshooting Set CPU or Set Memory Failed Tasks
An action task for Set CPU Count or Set Memory for VM has a Failed status in the recent task list because power off is
not allowed.
The Recent Tasks list indicates that a Set CPU Count, Set Memory, or Set CPU and Memory task has a status of Failed.
When you evaluate the Messages list for the selected task, you see this message.
Unable to perform action. Virtual Machine found
  powered on, power off not allowed. 
When you increase the memory or CPU count, you see this message.
VMware by Broadcom  3268

---
## page 3269

 VMware Cloud Foundation 9.0
Virtual Machine found powered on, power off not allowed, if hot add is
  enabled the hotPlugLimit is exceeded.
You submitted the action to increase or decrease the CPU or memory value without selecting the Allow Power Off option.
When you ran the action where a target object is powered on and where Memory Hot Plug is not activated for the target
object in vCenter, the action fails.
1. Either activate Memory Hot Plug on your target virtual machines in vCenter or select Allow Power Off when you run
the Set CPU Count, Set Memory, or Set CPU and Memory actions.
2. Check your hot plug limit in vCenter.
Troubleshooting Set CPU Count or Set Memory with Powered Off Allowed
A Set CPU Count, Set Memory, or a Set CPU Count and Set Memory action indicates that the action failed in Recent
Tasks.
When you run an action that changes the CPU count, the memory, or both, the action fails. It fails even though Power Off
Allowed was selected, the virtual machine is running, and the VMware Tools are installed and running.
The virtual machine must shut down the guest operating system before it powers off the virtual machine to make the
requested changes. The shutdown process waits 120 seconds for a response from the target virtual machine, and fails
without changing the virtual machine.
1. To determine if it has jobs running that are delaying the implementation of the action, check the target virtual machine
in vCenter.
2. Retry the action from VCF Operations.
Troubleshooting Set CPU Count and Memory When Values Not Supported
If you run the Set CPU Count or Set Memory actions with an unsupported value on a virtual machine, the virtual machine
might be left in an unusable state. That outcome requires you to resolve the problem in vCenter.
You cannot power on a virtual machine after you successfully run the Set CPU Count or Set Memory actions. When you
review the messages in Recent Tasks for the failed Power On VM action, you see messages stating that the host does not
support the new CPU count or new memory value.
Because of the way that vCenter validates changes in the CPU and memory values, you can use the VCF Operations
actions to change the value to an unsupported amount. This change can happen when you run the action when the virtual
machine is powered off.
If the object was powered on, the task fails, but rolls back any value changes and powers the machine back on. If the
object was powered off, the task succeeds and the value is changed in vCenter. However, the target object is left in a
state where you cannot power it on using either actions or the vCenter without manually changing the CPU or memory to
a supported value.
1. From the left menu, click Administration > Control Panel, and then select the Recent Tasks tile.
2. In the task list, locate your failed Power On VM action, and review the messages associated with the task.
3. Look for a message that indicates why the task failed.
For example, if you ran a Set CPU Count action on a powered off virtual machine to increase the CPU count from 2 to
4, but the host does not support 4 CPUs. The Set CPU tasks reported that it completed successfully in recent tasks.
However, when you attempt to power on the virtual machine, the tasks fails. In this example, the message is Virtual
machine requires 4 CPUs to operate, but the host hardware only provides 2.
4. Click the object name in the Recent Task list.
The main pane updates to display the object details for the selected object.
5. Click the Actions menu on the toolbar and click Open Virtual Machine in vSphere Client.
The vSphere Web Client opens with the virtual machine as the current object.
VMware by Broadcom  3269

---
## page 3270

 VMware Cloud Foundation 9.0
6. In the vSphere Web Client, click the Manage tab and click VM Hardware.
7. Click Edit.
8. In the Edit Settings dialog box, change the CPU count or memory to a supported value and click OK.
You can now power on the virtual machine from the Web client or from VCF Operations.
Troubleshooting Set CPU Resources or Set Memory Resources When the Value Is Not Supported
If you run the Set CPU Resources action with an unsupported value on a virtual machine, the task fails and an error
appears in the Recent Task messages.
The Recent Tasks list indicates that a Set CPU Resource or Set Memory Resource action has a state of Failed. When
you evaluate the Messages list for the selected task, you see a message similar to the following examples.
RuntimeFault exception, message:[A specified parameter was not correct.
 spec.cpuAllocation.reservation]
RuntimeFault exception, message:[A specified parameter was not correct.
 spec.cpuAllocation.limits]
You submitted the action to increase or decrease the CPU or memory reservation or limit value with an unsupported
value. For example, if you supplied a negative integer other than -1, which sets the value to unlimited, vCenter cannot
make the change and the action failed.
Run the action with a supported value.
The supported values for reservation include 0 or a value greater than 0. The supported values for limit include -1, 0, or a
value greater than 0.
Troubleshooting Set CPU Resources or Set Memory Resources When the Value Is Too High
You run the Set CPU Resources or Set Memory Resources action and the task fails with an error appearing in the Recent
Tasks messages. The reason might be that you entered a value that is greater than the value that your vCenter instance
supports.
The Recent Tasks list indicates that a Set CPU Resource or Set Memory Resource action has a state of Failed. When
you evaluate the Messages list for the selected task, you see messages similar to the following examples.
If you are working with Set CPU Resources, the information message is similar to the following example, where
1000000000 is the supplied reservation value.
Reconfiguring the Virtual Machine Reservation to:[1000000000] Mhz
The error message for this action is similar to this example.
RuntimeFault exception, message:[A specified parameter was not correct: reservation]
If you are working with Set Memory Resources, the information message is similar to the following example, where
1000000000 is the supplied reservation value.
Reconfiguring the Virtual Machine Reservation to:[1000000000] (MB)
The error message for this action is similar to this example.
RuntimeFault exception, message:[A specified parameter was not correct.
 spec.memoryAllocation.reservation]
You submitted the action to change the CPU or memory reservation or limit value to a value greater than the value
supported by vCenter, or the submitted reservation value is greater than the limit.
Run the action using a lower value.
Troubleshooting Set Memory Resources When the Value Is Not Evenly Divisible by 1024
If you run the Set Memory Resources action with a value that cannot convert from kilobytes to megabytes, the task fails
and an error appears in the Recent Task messages.
VMware by Broadcom  3270