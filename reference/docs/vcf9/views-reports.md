# views-reports (VCF 9.0, pages 4137-4169)


---
## page 4137

 VMware Cloud Foundation 9.0
status of the vCenter services. You can sort the services based on health status according to the following status: Started,
Stopped, or Unknown.
Clicking an instance shows you the summary of the instance with metrics, logs, alerts, and other details.
vSphere Daily Check Dashboard
Use the vSphere daily check dashboard to monitor the live operations of the vSphere clusters in your VCF Operations
environment.
Use the vSphere Daily Check dashboard to review the health and performance of the vSphere clusters in your VCF
Operations environment. The dashboard displays the critical and important alerts that need immediate attention. You can
use this dashboard to prevent or minimize alerts for the next 12 to 24 hours. This dashboard focuses on the daily activities
of the environment and provides updates based on changes or alerts in the clusters. The dashboard reflects the following
changes in your environment:
• Configuration changes
• Consumption changes: Any unexpected increase or sudden decrease in consumption.
• Supply changes. Any unexpected decrease in supply.
• Dynamic changes: Any VM state, VM location, or VM inventory changes.
Use the dashboard to focus on issues that need immediate attention and resolution for proper functioning of your
environment. You can adjust the thresholds and parameters to suit your need and add metrics like error logs to customize
the dashboard.
This dashboard complements the alerts triggered in your environment and provides insights into the cause of the alerts
and also shows the overall picture. This helps troubleshoot the specific issue without disrupting the whole environment. As
part of the daily checks, the following areas are covered:
• Availability: Daily checks cover the availability of powered on VMs and ESXi hosts. The numbers reflected should be
within the expected range. For example, if a new cluster is added or if several new VMs have been provisioned the day
before, the dashboard should reflect the revised available of the VMs and ESXi hosts.
• Performance: Daily checks cover the average performance of consumers (VMs) and providers (compute, network,
storage). For example, the dashboard monitors the total CPU, memory, disk, and network utilization as any sudden
increase or decrease in performance can cause issues.
• Compliance: Daily checks cover the compliance status and focuses on the present status. The present status covers
the past 12 to 24 hours.
• Configuration: Daily checks cover the changes in settings and make sure that the settings match the authorized
changes executed during the change window.
Configuring Reports and Views
A report is a scheduled snapshot of views and dashboards. A view helps you to interpret metrics, properties, policies of
various monitored objects including alerts, symptoms, and so on
 Reports in VCF Operations
A report is a scheduled snapshot of views and dashboards. You can create reports in VCF Operations to represent
objects and metrics. The report can contain a table of contents, cover page, and footer.
With the VCF Operations reporting functions, you can generate a report to capture details related to current or predicted
resource needs. You can download the report in a PDF or CSV file format for future and offline needs.
VMware by Broadcom  4137

---
## page 4138

 VMware Cloud Foundation 9.0
Types of Report Templates
There are two types of report templates in VCF Operations.
• Predefined report templates that are out of the box with VCF Operations. For more information, see Accessing Report
Templates .
• Custom report templates that you create based on your requirement. For more information, see Create a Report
Template.
Create a Report Template
You create a report to generate a scheduled snapshot of views and dashboards. You can track current resources and
predict potential risks to the environment. You can schedule automated reports at regular intervals.The name and
description of the report template as they appear in the list of templates on the Report Templates tab.
1. To create report templates, from the left menu, click Infrastructure Operations > Dashboards & Reports >
Reports > Create.
2. From the Create Report Template page, complete the options in each tab.
3. At the end of each tab, you can go to the previous or next tab. You can also cancel the creation of the report template.
4. After you have added all the details, click Create to create the report template.
Name and Description Tab
Table 1166: Name and Description Options in the Create Report Template Page
Option Description
Name Name of the template as it appears on the Report Templates
tab.
Description Description of the template.
Report Content Tab
The report template contains views and dashboards. Views present collected information for an object. Dashboards give
a visual overview of the performance and state of objects in your virtual infrastructure. You can combine different views
and dashboards and order them to suit your needs. The report template contains images of the views/dashboards that are
added.
Table 1167: Views and Dashboards Options and Sections in the Create Report Template Page
Option Description
Report Template Structure To add a view or a dashboard to your report template, select it
from the Views and Dashboards list in the right pane and drag it
to the Report Template Structure pane.
View and Dashboards Select Views or Dashboards to display a list of available views or
dashboards that you can add to the template.
Filter Search for views or dashboards by name. To see the complete list
of views or dashboards, delete the search box contents and press
Enter.
VMware by Broadcom  4138

---
## page 4139

 VMware Cloud Foundation 9.0
Option Description
Vertical Ellipsis > Portrait/Landscape You can select a portrait or landscape orientation for each view
or dashboard from the vertical ellipsis next to the title of the view/
dashboard after you drag and drop the view/dashboard to the left
pane.
Vertical Ellipsis > Colorization You can activate or deactivate a colorized PDF output for each list
view from the vertical ellipsis next to the title of a list view after you
drag and drop the list view to the left pane.
Available only for list views.
Layout and Format Tab
The report template can contain layout options such as a cover page, table of contents, and footer. Formats are the
outputs in which you can generate the report.
Table 1168: Layout and Format Options in the Create Report Template Page
Option Description
Cover Page Can contain an image up to 5 MB.
The default report size is 8.5 inches by 11 inches. The image is
resized to fit the report front page.
Table of contents Provides a list of the template parts, organized in the order of their
appearance in the report.
Footer Includes the date when the report is created, a note that the report
is created by VCF Operations, and page number.
PDF With the PDF format, you can read the reports, either on or off
line. This format provides a page-by-page view of the reports, as
they appear in printed form.
CSV In the CSV format, the data is in a structured table of lists.
Manage Report Templates
Using VCF Operations you can manage report templates by running, scheduling, and generating report templates.
Additionally, you can create custom report templates, edit existing report templates, download report templates, and so
on.
Reports Workflow
The following flowchart describes a simple workflow for reports in VCF Operations.
VMware by Broadcom  4139

---
## page 4140

 VMware Cloud Foundation 9.0
Use a Predefined Report Template 
or Create a New Report Template
Create a Schedule to Generate a 
Report or Run a Report Template to 
Immediately Generate a Report
Download a Generated Report 
Accessing Report Templates
A report template contains views and dashboards. Views present collected information for an object. Dashboards give
a visual overview of the performance and state of objects in your virtual infrastructure. VCF Operations offers several
predefined report templates that you can use based on your requirement.
Where You Can Access Report Templates From
From the left menu, click Infrastructure Operations > Dashboards & Reports > Reports. The Report Templates tab is
displayed on the right.
The listed report templates are user-defined and predefined by VCF Operations. You can order them by template name,
description, subject, date they were modified, last run report, or the user who modified them. For each template, you can
see the number of generated reports and schedules.
You can filter the reports based on the name of the report template, the subject, and the owner. You can click Add to
create a report template. For information about creating a report template, see Create a Report Template.
You can select a report template from the list, click the vertical ellipsis against each report template, and select options
such as run, edit, schedule, delete, clone, and export a report.
VMware by Broadcom  4140

---
## page 4141

 VMware Cloud Foundation 9.0
Table 1169: Predefined Filter Groups
Filter Group Description
Name Filter by the template name. For example, type my template
to list all reports that contain the my template phrase in their
name.
Subject Filter by another object. If the report contains more than one view
applicable for another type of object, you can filter by the other
objects.
Owner Filter by the owner of the report template.
The maximum number of reports per template is 10. After the tenth report is generated, VCF Operations deletes the
oldest report. vSphere users must be logged in until the report generation is complete. If you log out or your session
expires, the report generation fails.
Report Template Actions
You can select more than one report template and perform a set of actions by clicking the horizontal ellipsis next to the
Add option.
Option Description
Delete Deletes the report template.
Export Downloads the report template.
Import Allows you to import a report template by selecting a report
template in XML or zip file format.
To import a report template:
• Click the Import option from the horizontal ellipsis.
• Click Browse and select a report template ZIP or XML file to
import.
• Select if you want to Overwrite or Skip the file in case of a
conflict.
• Click Import to import the report template, and click Done.
Change default cover image Allows you to change the default cover image of the report
template. For more information, see Upload a Default Cover Page
Image for Reports.
Schedule a Report
In VCF Operations, the schedule of a report is the time and recurrence of report generation. To generate a report on a
selected date, time, and recurrence, you create a schedule for the report template. You set the email options to send the
generated report to your team.
• Download the generated report to verify the output.
• To activate sending email reports, you must have configured Outbound Alert Settings. See Notifications in VCF
Operations.
The date range for the generated report is based on the time when the report is generated and not on the time when you
schedule the report or when VCF Operations places the report in the queue.
Note:  Only users created in VCF Operations can add and edit report schedules.
VMware by Broadcom  4141

---
## page 4142

 VMware Cloud Foundation 9.0
1. From the left menu, click Infrastructure Operations > Dashboards & Reports > Reports.
2. From the Report Template tab, select the relevant report template from the list.
3. Click the vertical ellipsis and select Schedule.
4. Select an object and click Next.
5. Select the time zone, date, hour, and minutes (in the range of 0, 15, 30, and 45 minutes) to start the report generation.
VCF Operations generates the scheduled reports in sequential order. Generating a report can take several hours. This
process might delay the start time of a report when the previous report takes an extended period of time.
6. From the Recurrence drop-down menu, select one of the following options for report generation:
Option Description
Daily You can set the periodicity in days. For example, you can set
report generation to every two days.
Weekly You can set the periodicity in weeks. For example, you can set
report generation to every two weeks on Monday.
Monthly You can set the periodicity in months.
7. Select the Email report check box to send an email with the generated report.
Email a generated report to a predefined email group or to a network shared location. For more information about how
to set up and configure the email options, see Add a Standard Email Plug-In for VCF Operations Outbound Alerts.
a) In the Email addresses text box, enter the email addresses that must receive the report. You can also add email
addresses in the CC list and BCC list.
b) Select an outbound rule.
An email is sent according to this schedule every time a report is generated.
8. Save a generated report to an external location.
For more information about how to configure an external location, see Add a Network Share Plug-In for VCF
Operations Reports
9. You can add a relative path to upload the report to a predefined sub folder of the Network Share Root folder. For
example, to upload the report to the share host C:/documents/uploadedReports/SubFolder1, in the Relative
Path text box, enter SubFolder1. To upload the report to the Network Share Root folder, leave the Relative Path text
box empty.
Editing a Report Schedule
To edit the schedule of a report, click the link in the Schedules column against the report template from the Report
Templates tab, and then from the Scheduled Reports dialog box, click Edit Schedule. You see the Scheduled Reports
page.
Table 1170: Scheduled Reports Toolbar Options
Options Description
New Schedule You can create a schedule for the report.
Edit Schedule You can edit an existing report schedule.
Delete Schedule You can delete an existing report schedule.
Transport Report Schedule You can assign a new owner for the selected report schedule. You
can select a target user from the Transfer Report Schedules
dialog box.
VMware by Broadcom  4142

---
## page 4143

 VMware Cloud Foundation 9.0
Note:  You can edit, clone, and delete report templates. Before you do, familiarize yourself with the consequences
of these actions. When you edit a report template and delete it, all reports generated from the original and the edited
templates are deleted. When you clone a report template, the changes that you make to the clone do not affect the source
template. When you delete a report template, all generated reports are also deleted.
 Generate and Regenerate a Report
To generate a report, use a predefined or custom report template.
Create a report template.
1. From the left menu, click Infrastructure Operations > Dashboards & Reports > Reports.
2. From the Report Templates tab on the right, navigate to the relevant report template, click the vertical ellipsis, and
select Run.
3. Select an associated object from the Select Object dialog box and click OK.
The report is generated and listed on the Generated Reports tab.
Note:  To regenerate the selected report, from the Generated Reports tab, click the vertical ellipsis against the generated
report and select Run.
Download the generated report and verify the output.
Accessing Generated Reports
You can view a list of report templates that have been generated in VCF Operations.
Where You Can Access Generated Reports From
From the left menu, click Infrastructure Operations > Dashboards & Reports > Reports. The Generated Reports tab
on the right pane contains all the generated reports. If the report is generated through a schedule, the owner is the user
who created the schedule.
Note:  The maximum number of reports per template is 10. After the tenth report is generated, VCF Operations deletes
the oldest report.
To select a generated report from the list, click the vertical ellipsis against each generated report and select options such
as run and delete. You can also select more than one generated report and select the Delete button above the data grid
to delete a generated report.
You can filter the reports list by adding a filter from the upper-right corner of the panel.
Table 1171: Predefined Filter Groups
Filter Group Description
Report Name Filter by the report template name. For example, type my
template to list all reports that contain the my template
phrase in their name.
Template Filter by the report template. You can select a template from a list
of templates applicable for this object.
Completion Date/Time Filter by the date, time, or time range.
Subject Filter by another object. If the report contains more than one view
applicable for another type of object, you can filter by that second
object.
VMware by Broadcom  4143

---
## page 4144

 VMware Cloud Foundation 9.0
Filter Group Description
Status Filter by the status of the report.
You can download a report in a PDF or CSV format. You define the format that a report is generated in the report
template.
If you log in to VCF Operations with vCenter credentials and generate a report, the generated report is always blank.
Download a Report
To verify that the information appears as expected, you download the generated report.
Generate a report.
1. From the left menu, select Infrastructure Operations > Dashboards & Reports > Reports.
2. From the Generated Reports tab on the right, click the PDF or the CSV icon in the Download column to download
the report.
VCF Operations saves the report file.
Schedule a report generation and set the email options, so your team receives the report.
Upload a Default Cover Page Image for Reports
You can upload a common default image for the cover page of reports. You do not have to upload a cover page for each
report. The cover pages of predefined reports are modified when you use this option. The cover pages of user-defined
reports do not change.
Where Do You Upload a Default Cover Page Image for Reports
To upload a default cover page for reports, from the left menu, click Infrastructure Operations > Dashboards &
Reports > Reports. From the Report Templates tab on the right side, click the horizontal ellipsis next to the Add option
and click the Change default cover image option.
How Do You Upload a Default Cover Page Image for Reports
Browse for the image that you want to add to the cover page and click Save. You can also use the default product image
that is available.
Add a Network Share Plug-In for VCF Operations Reports
You add a Network Share plug-in when you want to configure VCF Operations to send reports to a shared location. The
Network Share plug-in supports only SMB version 2.1.
Verify that you have read, write, and delete permissions to the network share location.
1. From the left menu, click Infrastructure Operations > Configurations, and then click the Outbound Settings tile.
2. Click Add, and from the Plug-In Type drop-down menu, select Network Share Plug-in.
The dialog box expands to include your plug-in instance settings.
3. Enter an Instance Name.
This is the name that identifies this instance that you select when you later configure notification rules.
VMware by Broadcom  4144

---
## page 4145

 VMware Cloud Foundation 9.0
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
7. Optional: To stop an outbound service, select an instance and click Deactivate on the toolbar.
This instance of the Network Share plug-in is configured and running.
Create a report schedule and configure it to send reports to your shared folder.
Views in VCF Operations
VCF Operations provides several types of views. Each type of view helps you to interpret metrics, properties, policies
of various monitored objects including alerts, symptoms, and so on, from a different perspective. Views also show
information that the adapters in your environment provide.
You can configure VCF Operations views to show transformation, forecast, and trend calculations.
• The transformation type determines how the values are aggregated.
• The trend option shows how the values tend to change, based on the historical, raw data. The trend calculations
depend on the transformation type and roll up interval.
• The forecast option shows what the future values can be, based on the trend calculations of the historical data.
You can use VCF Operations views in different areas of VCF Operations.
• To manage all views, from the left menu, click Infrastructure Operations > Dashboards & Reports > Views. From
the Views page, click the Manage tab.
• To see the data that a view provides for a specific object, navigate to that object, click the Details tab, and click Views.
• To see the data that a view provides in your dashboard, add the View widget to the dashboard. For more information,
see  View Widget.
VMware by Broadcom  4145

---
## page 4146

 VMware Cloud Foundation 9.0
Table 1172: Options from the Views Pane (Infrastructure Operations > Dashboards & Reports > Views)
Options Description
Manage You can manage views by clicking Infrastructure Operations >
Dashboards & Reports > Views. From the Views page, click the
Manage tab.
Add Use this option to create a view. See Creating and Configure a
View.
Search You can search for a view across the Recents and All folders in
the Views panel.
Recent The views are listed in the order in which you select them, with the
most recent view that you selected, appearing at the top. Up to ten
views can be displayed as Recent views.
If you do not pin the view and log out of the user interface, on
logging back in, the view is removed from the Recents folder
All Lists the views based on their type. You can use this menu for
quick navigation through your views. When you navigate to a view,
the views are listed in the Views panel under All. You can also
search for views using keywords and letters.
Views and Reports Ownership
The default owner of all predefined views and templates is System. If you edit them, you become the owner. If you want to
keep the original predefined view or template, you have to clone it. After you clone it, you become the owner of the clone.
The last user who edited a view, template, or schedule is the owner. For example, if you create a view you are listed as its
owner. If another user edits your view, that user becomes the owner listed in the Owner column.
The user who imports the view or template is its owner, even if the view is initially created by someone else. For example,
User 1 creates a template and exports it. User 2 imports it in back, the owner of the template becomes User 2.
The user who generated the report is its owner, regardless of who owns the template. If a report is generated from a
schedule, the user who created the schedule is the owner of the generated report. For example, if User 1 creates a
template and User 2 creates a schedule for this template, the generated report owner is User 2.
Accessing Predefined Views
You can access some of the useful, predefined views from the Views home page.
To access these views, from the left menu, click Infrastructure Operations > Dashboards & Reports > Views. From the
Views page, click Overview.
The views are categorized as follows: Availability, Capacity, Configuration, Inventory, Performance, and Compliance. To
easily access some of the useful, predefined dashboards under these categories, click on the drop-down button against
the selected category and click on the specific dashboard.
 Views Overview
A view presents collected information for an object in a certain way depending on the view type. Each type of view helps
you to interpret metrics, properties, policies of various monitored objects including alerts, symptoms, and so on, from a
different perspective.
How You Access the Views Page
VMware by Broadcom  4146

---
## page 4147

 VMware Cloud Foundation 9.0
From the left menu, click Infrastructure Operations > Dashboards & Reports > Views. From the Views page, click the
Manage tab.
Manage and Preview Views
You can preview a view by clicking a view from the Views > Manage tab. Click on a view and add an object if necessary
by clicking Preview source from the upper-right corner of the specific view.
From the Views > Manage tab you can select a view from the list, click the vertical ellipsis against each view, and select
the various options such as edit, delete, clone, and export a view.
You can filter the views based on the name, type, description, subject, and owner. You can click the Add option to create a
view. For information about creating a view, see Creating and Configure a View.
Views are also categorized and listed in the Views panel based on the type of view and subject.
Table 1173: Filter Groups
Filter Group Description
Name Filter by the view name. For example, type my view to list all
views that contain the my view phrase in their name.
Type Filter by the view type.
Description Filter by the view description. For example, type my view to list
all views that contain the my view phrase in their description.
Subject Filter by the subject.
Owner Filter by owner.
Datagrid Options
Column Names Description
Name Displays the name of the view.
Type Displays the type of view: list, summary, trend, distribution, text, or
image.
Description Displays the description of the dashboard.
Subject Displays the base object type for which the view shows
information.
Dashboard Usage Displays the number of dashboards where the view is used. Click
the number in the column to view the name of the dashboard/s.
Click the dashboard name to navigate to the dashboard.
Report Usage Displays the number of reports where the view is used. Click the
number in the column to view the name of the report/s. Click the
report name to navigate to the report template in edit mode.
Last Modified Displays the date the view was last modified.
Modified By Displays the user who last modified the view.
Views Actions
You can select more than one view and perform a set of actions by clicking the horizontal ellipsis next to the Add option.
VMware by Broadcom  4147

---
## page 4148

 VMware Cloud Foundation 9.0
Option Description
Delete Deletes the view.
Export Downloads the view.
Import Allows you to import a view by selecting a view in XML or zip file
format.
To import a view:
• Click the Import option from the horizontal ellipsis.
• Click Browse and select a view XML or ZIP file to import.
• Select if you want to Overwrite or Skip the file in case of a
conflict.
• Click Import to import the view, and click Done.
 Views and Reports Ownership
The owner of views, reports, or templates might change over time.
The default owner of all predefined views and templates is System. If you edit them, you become the owner. If you want to
keep the original predefined view or template, you have to clone it. After you clone it, you become the owner of the clone.
The last user who edited a view, template, or schedule is the owner. For example, if you create a view you are listed as its
owner. If another user edits your view, that user becomes the owner listed in the Owner column.
The user who imports the view or template is its owner, even if the view is initially created by someone else. For example,
User 1 creates a template and exports it. User 2 imports it in back, the owner of the template becomes User 2.
The user who generated the report is its owner, regardless of who owns the template. If a report is generated from a
schedule, the user who created the schedule is the owner of the generated report. For example, if User 1 creates a
template and User 2 creates a schedule for this template, the generated report owner is User 2.
Creating and Configure a View
To collect and display information for a specific object, you can create a custom view.
1. From the left menu, click Infrastructure Operations > Views > Create.
2. Select one of the following views from the right panel.
• List View
• Summary View
• Trend View
• Distribution View
• Text View
• Image View
3. At the end of each tab in the selected view, you can go to the previous or next tab. You can also cancel the creation of
the view.
4. After you have added all the details, click Create to create the view.
List View
List views provide tabular data about specific objects in the monitored environment that correspond to the selected view.
VMware by Broadcom  4148

---
## page 4149

 VMware Cloud Foundation 9.0
Where You Find the List View
From the left menu, click Infrastructure Operations > Views > Create. Click List from the right page.
Name and Configuration Tab
Option Description
Name Name of the view as it appears on the Views page.
Description Description of the view.
Settings
Items per page Select the number of items per page. Each item is one row and its
metrics and properties are the columns.
Top result count Select the top results. Restricts the number of results. For
example, if you list all the clusters in a View, selecting 10 in this
option displays the top 10 clusters with the relevant information.
You can reduce the number of rows for the purposes of reporting.
Include Deleted Objects Select to add deleted objects.
Show Objects Select the type of object you want displayed in the view. You can
select Existing, Deleted, or All objects.
Show Object Creation Date Select to display the date the object was created.
Make the view available at > Dashboards through the View widget Select if you want to make the view available in a dashboard.
Make the view available at > Report template creation and
modification
Select if you want to make the view available in a report template.
Make the view available at > Details tab in the environment Select if you want to make the view available in the Detail tab of a
specific object.
Hide the view for the selected object types Select an object type for which you do not want to see this view.
For example, you have a list view with the subject <virtual
machines>. It is visible when you select any of its parent objects.
You add a data center from the list. The view is not visible
anymore on the data center level.
Data Tab
The data definition process includes adding properties, metrics, policies, or data that adapters provide to a view. These
are the items by which VCF Operations collects, calculates, and presents the information for the view.
How to Add Data to a View
If you selected more than one subject, click the subject for which you add data. Double-click either a metric or a property
from the tree in the left panel to add it to the view. For each subject that you select, the data available to add might be
different. The Data, Transformation, and Configuration details are displayed.
You can see a live preview of the view type when you select a subject and associated data, and then click Preview
Source.
VMware by Broadcom  4149

---
## page 4150

 VMware Cloud Foundation 9.0
Option Description
Add Subject Select the base object type for which the view shows information.
The subject you specify determines where the view is applicable.
If you select more than one subject, the view is applicable for each
of them.
Group By You can group the results based on a parent object, by making
a selection in the Group By drop-down option. If you generate a
report based on the list view for which a group has been specified,
the report displays group-based information for the selected
object. You can also view summary calculations for the group of
objects in the report, along with the total summary results for all
the objects.
Breakdown By
Add interval breakdown Select this check box to see the data for the selected resources
broken down in time intervals.
After you select this check box, you can enter a label, specify
whether the values have to be sorted in ascending or descending
order, and select a breakdown interval for the time range.
Add Instance breakdown Select this check box to see the data for all instances of the
selected resources.
After you select this check box, you can enter a label and select
a metric group to break down all the instances in that group.
Deselect Show non-instance aggregate metric to display only
the separate instances. Deselect Show only instance name to
display the metric group name and instance name in the instance
breakdown column.
For example, you can create a view to display CPU usage
by selecting the metric CPU:0|Usage. If you add an instance
breakdown column, the column CPU:0|Usage displays the usage
of all CPU instances on separate rows (0, 1, and so on). To avoid
ambiguity, you can change the metric label of CPU:0|Usage to
Usage.
Data Grid options
Self  drop down option Click the drop down button to select an ancestor or descendant of
the selected subject. You can select metrics and properties from
the data selection tree and then configure them.
Note:  Error messages are displayed in the following cases:
• If the same object type is used as an ancestor/descendant and
as the primary object type.
• If you do not select a metric for the primary object type. You
must select at least one metric.
• If the number of related ancestor/descendant object types
used in the configuration exceeds a maximum of 3.
Add Object Name If you have selected an ancestor or descendant from the Self
drop down option, click Add Object Name to add the name of
the selected descendant or ancestor as a column name in the
Preview Source pane.
Data selection tree (Metrics and Properties) Select a metric or a property.
VMware by Broadcom  4150

---
## page 4151

 VMware Cloud Foundation 9.0
Option Description
Note:  The metrics presented by default are a subset of available
metrics. If the desired metric is not represented, use the Select
Object button in the title bar of the data selection tree to re-filter
the displayed list.
Data column Click the metric or property to enter configuration details in the
configuration column.
Transformation column Displays the type of transformation applied to the data.
Configuration column
Metric name Default metric name.
Metric label Customizable label as it appears in the view or report.
Units Depends on the added metric or property. You can select in what
unit to display the values. For example, for CPU|Demand (MHz)
from the Units drop-down menu, you can change the value to Hz,
kHz, or GHz. If you select Auto, the scaling is set to a meaningful
unit.
Sort order Orders the values in ascending or descending order
Note:  Sort order is not activated for ancestor or descendant
objects.
Transformation Determines what calculation method is applied on the raw data.
You can select the type of transformation:
• Minimum. The minimum value of the metric over the selected
time range.
• Maximum. The maximum value of the metric over the selected
time range.
• Average. The mean of all the metric values over the selected
time range.
• Sum. The sum of the metric values over the selected time
range.
• First. The first metric value for the selected time range.
• Last. The last value of a metric within the selected time range.
If you have selected Last as the transformation in versions
before vRealize Operations 6.7, and the end of specified time
range is not before the last five minutes, use the Current
transformation.
• Current. The last available value of a metric if it was last
updated not before five collection cycles were complete,
otherwise it is null.
• Standard Deviation. The standard deviation of the metric
values.
• Metric Correlation. Displays the value when another metric is
at the minimum or maximum. For example, displays the value
for memory.usage when cpu.usage is at a maximum.
• Forecast. Performs a regressive analysis and predicts future
values. Displays the last metric value of the selected range.
• Percentile. Calculates the specified percentile for the data
range. For example, you can view the 95th percentile, 99th
percentile, and so on.
VMware by Broadcom  4151

---
## page 4152

 VMware Cloud Foundation 9.0
Option Description
• Expression. Allows you to construct a mathematical
expression over existing transformations using minus, plus,
multiplication, division, unary minus, unary plus, and round
brackets. For example, sum/((max + min)/2). You can
use the operands of some of the existing transformations such
as, max, min, avg, sum, first, last, current. You cannot use
standard deviation, forecast, metric correlation, and percentile.
You can customize the metric unit label when you select the
Expression transformation. For example, some of the metric
units available are, vCPUs, Bps, KBps, Mbps, and MBps.
• Timestamp: You can choose between Absolute Timestamp or
Relative Timestamp.
– If applied to a numeric metric/property defined with a time-
unit definition, the actual value is converted to a human
readable timestamp. The metric value is rounded-off to an
hour.
– In the remaining cases, a timestamp is displayed when
metrics and properties are added or modified. In this
case, the behavior is the same as the Timestamp option
selected for a non-Timestamp transformation. Applicable
for Absolute Timestamp and Relative Timestamp.
Available for List view and Minimum, Maximum, Current, First,
and Last transformation.
Ranges for metric coloring You can associate colors to metrics by entering a percentage,
range, or specific state. For example, you can enter Powered Off
in the Red Bound field when you select virtual machine as an
object. You can set the colors only for views and not for csv or pdf
formats.
Series Roll up The time interval at which the data is rolled up. You can select
one of the available options. For example, if you select Sum as
a Transformation and 5 minutes as the roll-up interval, then the
system selects 5-minute interval values and adds them.
This option is applicable to the Transformation configuration
option.
Time Settings Tab
Use the time settings to select the time interval of data transformation. These options are available for all view types,
except Image.
You can set a time range for a past period or set a future date for the end of the time period. When you select a future end
date and no data is available, the view is populated by forecast data. Data is collected based on the browser time.
Table 1174: Time Settings Options
Configuration Option Description
Time Range Mode In Basic mode, you can select date ranges.
In Advanced mode, you can select any combination of relative or
specific start and end dates.
You can also activate the Business Hour option and select
business hours/days for weekdays.
Relative Date Range Select a relative date range of data transformation.
VMware by Broadcom  4152

---
## page 4153

 VMware Cloud Foundation 9.0
Configuration Option Description
Available in Basic mode.
Specific Date Range Select a specific date range of data transformation.
Available in Basic mode.
Absolute Date Range Select a date or time range to view data for a time unit such as a
complete month or a week. For example, you can run a report on
the third of every month for the previous month. Data from the first
to the end of the previous month is displayed as against data from
the third of the previous month to the third of the current month.
The units of time available are: Hours, Days, Weeks, Months,
and Years.
The locale settings of the system determine the start and end of
the unit. For example, weeks in most of the European countries
begin on Monday while in the United States they begin on Sunday.
Available in Basic mode.
Relative Start Date Select a relative start date of data transformation.
Available in Advanced mode.
Relative End Date Select a relative end date of data transformation.
Available in Advanced mode.
Specific Start Date Select a specific start date of data transformation.
Available in Advanced mode.
Specific End Date Select a specific end date of data transformation.
Available in Advanced mode.
Currently selected date range Displays the date or time range you selected. For example, if you
select a specific date range from 5/01/2016 to 5/18/2016, the
following information is displayed: May 1, 2016 12:00:00
AM to May 18, 2016 11:55:00 PM .
Business Hours Select business hours from Monday to Sunday by moving the
sliders on the left and right sides to set the start and end time for
each day of the week.
For example, as a VM owner, you can track the average utilization
of VMs over a week (business days), during specified hours of the
day (business hours).
This option is available for Minimum, Maximum, Average, Sum,
and Percentile transformations
Available in Advanced mode for List Views.
Filter Tab
The filter option allows you to add additional criteria when the view displays too much information. For example, a List
view shows information about the health of virtual machines. From the Filter tab, you add a risk metric less than 50%. The
view displays the health of all virtual machines with risk less than 50%. For selected criteria you can also apply Business
Hours, if the selected transformation type you add as a filter is supported by the business hours functionality.
To add a filter to a view, from an existing or new view dialog box, click the Filter tab. Fill in the details for each row and
click Add. You can activate Business Hours for the metric selected.
Each subject has a separate filter box. For Alerts Roll up, Alert, and Symptom subjects not all applicable metrics are
supported for filtering.
Note:  For Symptom based views, in the filter, if you select either Symptom Definition Name, Alert Definition Name, or
Alert Type, it is recommended that you select a preview source that has a smaller number of objects.
VMware by Broadcom  4153

---
## page 4154

 VMware Cloud Foundation 9.0
Table 1175: Filter Add Options
Option Description
Add Adds another criteria to the criteria set. The filter returns results
that match all the specified criteria.
If you add a filter for an instance metric or property, all the
instances of the object for which the criteria is met, will be
displayed in the preview screen.
For instance metrics or properties, you can filter based on
transformations such as, Current, Average, First, Last, Maximum,
Minimum, Sum, and Timestamp.
Add another criteria set Adds another criteria set. The filter returns results that match one
criteria set or another.
Summary Tab
You can add more than one summary row or column and configure each to show different aggregations. In the summary
configuration panel, you select the aggregation method and what data to include or exclude from the calculations.
To add a summary row or column to a view, from an existing or new view dialog box, click the Summary tab in the right
pane. Click the plus sign to add a summary row.
For the Summary view, the summary column shows aggregated information by the items provided on the Data tab.
Previous, Next, Create, and Cancel Options
At the end of each tab, you can go to the previous or next tab. You can also cancel the creation of the view. After you have
added all the details, click Create to create the view.
Summary View
Summary views provide tabular data about the use of resources in the monitored environment.
Where You Find the Summary View
From the left menu, click Infrastructure Operations > Views > Create. Click Summary from the right page.
Name and Configuration Tab
Option Description
Name Name of the view as it appears on the Views page.
Description Description of the view.
Settings
Items per page Select the number of items per page. Each item is one row and its
metrics and properties are the columns.
Make the view available for > Dashboards through the View
widget
Select if you want to make the view available in a dashboard.
Make the view available for > Report template creation and
modification
Select if you want to make the view available in a report template.
VMware by Broadcom  4154

---
## page 4155

 VMware Cloud Foundation 9.0
Option Description
Make the view available for > Details tab in the environment Select if you want to make the view available in the Detail tab of a
specific object.
Hide the view for the selected object types Select an object type for which you do not want to see this view.
For example, you have a list view with the subject <virtual
machines>. It is visible when you select any of its parent objects.
You add a data center from the list. The view is not visible
anymore on the data center level.
Data Tab
The data definition process includes adding properties, metrics, policies, or data that adapters provide to a view. These
are the items by which VCF Operations collects, calculates, and presents the information for the view.
How to Add Data to a View
If you selected more than one subject, click on the subject for which you want to add data. Double-click either a metric or
a property from the tree in the left panel to add it to the view. For each subject that you select, the data available to add
might be different. The Data, Transformation, and Configuration details are displayed.
You can see a preview of the view type when you select a subject and associated data, and then click Select preview
source.
Option Description
Add Subject Select the base object type for which the view shows information.
The subject you specify determines where the view is applicable.
If you select more than one subject, the view is applicable for each
of them.
Data Grid options
Data selection tree Select a metric or property
Data column Click the metric or property to enter configuration details in the
configuration column.
Transformation column
Configuration column
Metric name Default metric name.
Metric label Customizable label as it appears in the view or report.
Units Depends on the added metric or property. You can select in what
unit to display the values. For example, for CPU|Demand(MHz)
from the Units drop-down menu, you can change the value to Hz,
KHz, or GHz. If you select Auto, the scaling is set to a meaningful
unit.
Sort order Orders the values in ascending or descending order.
Transformation Determines what calculation method is applied on the raw data.
You can select the type of transformation:
• Minimum. The minimum value of the metric over the selected
time range.
• Maximum. The maximum value of the metric over the selected
time range.
VMware by Broadcom  4155

---
## page 4156

 VMware Cloud Foundation 9.0
Option Description
• Average. The mean of all the metric values over the selected
time range.
• Sum. The sum of the metric values over the selected time
range.
• First. The first metric value for the selected time range.
• Last. The last value of a metric within the selected time range.
If you have selected Last as the transformation in versions
before vRealize Operations 6.7, and the end of specified time
range is not before the last five minutes, use the Current
transformation.
• Current. The last available value of a metric if it was last
updated not before five collection cycles were complete,
otherwise it is null.
• Standard Deviation. The standard deviation of the metric
values.
• Metric Correlation. Displays the value when another metric is
at the minimum or maximum. For example, displays the value
for memory.usage when cpu.usage is at a maximum.
• Forecast. Performs a regressive analysis and predicts future
values. Displays the last metric value of the selected range.
• Percentile. Calculates the specified percentile for the data
range. For example, you can view the 95th percentile, 99th
percentile, and so on.
• Expression. Allows you to construct a mathematical
expression over existing transformations using minus, plus,
multiplication, division, unary minus, unary plus, and round
brackets. For example, sum/((max + min)/2). You can
use the operands of some of the existing transformations such
as, max, min, avg, sum, first, last, current. You cannot use
standard deviation, forecast, metric correlation, and percentile.
You can customize the metric unit label when you select the
Expression transformation. For example, some of the metric
units available are, vCPUs, Bps, KBps, Mbps, and MBps.
Series Roll up The time interval at which the data is rolled up. You can select
one of the available options. For example, if you select Sum as
a Transformation and 5 minutes as the roll-up interval, then the
system selects 5-minute interval values and adds them.
This option is applicable to the Transformation configuration
option.
Time Settings Tab
Use the time settings to select the time interval of data transformation. These options are available for all view types,
except Image.
You can set a time range for a past period or set a future date for the end of the time period. When you select a future end
date and no data is available, the view is populated by forecast data. Data is calculated based on the browser time.
Table 1176: Time Settings Options
Configuration Option Description
Time Range Mode In Basic mode, you can select date ranges.
VMware by Broadcom  4156

---
## page 4157

 VMware Cloud Foundation 9.0
Configuration Option Description
In Advanced mode, you can select any combination of relative or
specific start and end dates.
Relative Date Range Select a relative date range of data transformation.
Available in Basic mode.
Specific Date Range Select a specific date range of data transformation.
Available in Basic mode.
Absolute Date Range Select a date or time range to view data for a time unit such as a
complete month or a week. For example, you can run a report on
the third of every month for the previous month. Data from the first
to the end of the previous month is displayed as against data from
the third of the previous month to the third of the current month.
The units of time available are: Hours, Days, Weeks, Months,
and Years.
The locale settings of the system determine the start and end of
the unit. For example, weeks in most of the European countries
begin on Monday while in the United States they begin on Sunday.
Available in Basic mode.
Relative Start Date Select a relative start date of data transformation.
Available in Advanced mode.
Relative End Date Select a relative end date of data transformation.
Available in Advanced mode.
Specific Start Date Select a specific start date of data transformation.
Available in Advanced mode.
Specific End Date Select a specific end date of data transformation.
Available in Advanced mode.
Currently selected date range Displays the date or time range you selected. For example, if you
select a specific date range from 5/01/2016 to 5/18/2016, the
following information is displayed: May 1, 2016 12:00:00
AM to May 18, 2016 11:55:00 PM .
Filter Tab
The filter option allows you to add additional criteria when the view displays too much information. For example, a view
shows information about the health of virtual machines. From the Filter tab, you add a risk metric less than 50%. The view
displays the health of all virtual machines with risk less than 50%.
To add a filter to a view, from an existing or new view dialog box, click the Filter tab. Fill in the details for each row and
click Add.
Each subject has a separate filter box. For Alerts Roll up, Alert, and Symptom subjects not all applicable metrics are
supported for filtering.
Table 1177: Filter Add Options
Option Description
Add Adds another criteria to the criteria set. The filter returns results
that match all the specified criteria.
If you add a filter for an instance metric or property, all the
instances of the object for which the criteria is met, will be
displayed in the preview screen.
VMware by Broadcom  4157

---
## page 4158

 VMware Cloud Foundation 9.0
Option Description
For instance metrics or properties, you can filter based on
transformations such as, Current, Average, First, Last, Maximum,
Minimum, Sum, and Timestamp.
Add another criteria set Adds another criteria set. The filter returns results that match one
criteria set or another.
Summary Tab
You can add more than one summary row or column and configure each to show different aggregations. In the summary
configuration panel, you select the aggregation method and what data to include or exclude from the calculations.
To add a summary row or column to a view, from an existing or new view dialog box, click the Summary tab in the right
pane. Click the plus sign to add a summary row.
For the Summary view, the summary column shows aggregated information by the items provided on the Data tab.
Previous, Next, Create, and Cancel Options
At the end of each tab, you can go to the previous or next tab. You can also cancel the creation of the view. After you have
added all the details, click Create to create the view.
Trend View
Trend views use historic data to generate trends and forecasts for resource use and availability in the monitored
environment.
Where You Find the Trend View
From the left menu, click Infrastructure Operations > Views > Create. Click Trend from the right page.
Name and Configuration Tab
Option Description
Name Name of the view as it appears on the Views page.
Description Description of the view.
Settings
The maximum plot lines Enter the maximum number of plot lines. Limits the output in terms
of the objects displayed in the live preview of the view type on the
left upper pane. The number you set as the maximum number of
plot lines determines the plot lines.
For example, if you plot historical data and set the maximum at
30 plot lines, then 30 objects are displayed. If you plot historical,
trend, and forecast lines, and set the maximum to 30 plot lines,
then only 10 objects are displayed as each object has three plot
lines.
Make the view available for > Dashboards through the View
widget
Select if you want to make the view available in a dashboard.
Make the view available for > Report template creation and
modification
Select if you want to make the view available in a report template.
VMware by Broadcom  4158

---
## page 4159

 VMware Cloud Foundation 9.0
Option Description
Make the view available for > Details tab in the environment Select if you want to make the view available in the Detail tab of a
specific object.
Hide the view for the selected object types Select an object type for which you do not want to see this view.
For example, you have a list view with the subject <virtual
machines>. It is visible when you select any of its parent objects.
You add a data center from the list. The view is not visible
anymore on the data center level.
Data Tab
The data definition process includes adding properties, metrics, policies, or data that adapters provide to a view. These
are the items by which VCF Operations collects, calculates, and presents the information for the view.
How to Add Data to a View
If you selected more than one subject, click on the subject for which you want to add data. Double-click the data from the
tree in the left panel to add it to the view. For each subject the data available to add, might be different.
You can see a live preview of the view type when you select a subject and associated data, and then click Select preview
source.
Option Description
Add Subject Select the base object type for which the view shows information.
The subject you specify determines where the view is applicable.
If you select more than one subject, the view is applicable for each
of them.
Data Grid options
Data selection tree Select a metric or a property.
Data column Click the metric or property to enter configuration details in the
configuration column.
Transformation column Displays the type of transformation applied to the data.
Configuration column
Metric name Default metric name.
Metric label Customizable label as it appears in the view or report.
Units Depends on the added metric or property. You can select in what
unit to display the values. For example, for CPU|Demand (MHz)
from the Units drop-down menu, you can change the value to Hz,
KHz, or GHz. If you select Auto, the scaling is set to a meaningful
unit.
Data Series You can select whether to include historical data, trend of
historical data, and forecast for future time in the trend view
calculations.
Ranges for metric coloring You can associate colors to metrics by entering a percentage,
range, or specific state. For example, you can enter Powered Off
in the Red Bound field when you select virtual machine as an
object. You can set the colors only for views and not for csv or pdf
formats.
VMware by Broadcom  4159

---
## page 4160

 VMware Cloud Foundation 9.0
Option Description
Series Roll up The time interval at which the data is rolled up. You can select
one of the available options. For example, if you select Sum as
a Transformation and 5 minutes as the roll-up interval, then the
system selects 5-minute interval values and adds them.
This option is applicable to the Transformation configuration
option.
Available for all views.
Threshold Lines You can set a threshold for a single metric:
• None. You have not set a threshold.
• By Symptom Definition. You can set a threshold value based
on a symptom definition.
• Custom. You can set the threshold value as Warning, Critical,
or Immediate. These options are available only for the
Custom option.
Time Settings Tab
Use the time settings to select the time interval of data transformation.
You can set a time range for a past period or set a future date for the end of the time period. When you select a future end
date and no data is available, the view is populated by forecast data. Data is calculated based on the browser time.
Table 1178: Time Settings Options
Configuration Option Description
Time Range Mode In Basic mode, you can select date ranges.
In Advanced mode, you can select any combination of relative or
specific start and end dates.
Relative Date Range Select a relative date range of data transformation.
Available in Basic mode.
Specific Date Range Select a specific date range of data transformation.
Available in Basic mode.
Absolute Date Range Select a date or time range to view data for a time unit such as a
complete month or a week. For example, you can run a report on
the third of every month for the previous month. Data from the first
to the end of the previous month is displayed as against data from
the third of the previous month to the third of the current month.
The units of time available are: Hours, Days, Weeks, Months,
and Years.
The locale settings of the system determine the start and end of
the unit. For example, weeks in most of the European countries
begin on Monday while in the United States they begin on Sunday.
Available in Basic mode.
Relative Start Date Select a relative start date of data transformation.
Available in Advanced mode.
Relative End Date Select a relative end date of data transformation.
Available in Advanced mode.
Specific Start Date Select a specific start date of data transformation.
Available in Advanced mode.
VMware by Broadcom  4160

---
## page 4161

 VMware Cloud Foundation 9.0
Configuration Option Description
Specific End Date Select a specific end date of data transformation.
Available in Advanced mode.
Currently selected date range Displays the date or time range you selected. For example, if you
select a specific date range from 5/01/2016 to 5/18/2016, the
following information is displayed: May 1, 2016 12:00:00
AM to May 18, 2016 11:55:00 PM .
Filter
The filter option allows you to add additional criteria when the view displays too much information.
To add a filter to a view, from an existing or new view dialog box, click the Filter tab. Fill in the details for each row and
click Add.
Each subject has a separate filter box. For Alerts Roll up, Alert, and Symptom subjects not all applicable metrics are
supported for filtering.
Table 1179: Filter Add Options
Option Description
Add Adds another criteria to the criteria set. The filter returns results
that match all the specified criteria.
If you add a filter for an instance metric or property, all the
instances of the object for which the criteria is met, will be
displayed in the preview screen.
For instance metrics or properties, you can filter based on
transformations such as, Current, Average, First, Last, Maximum,
Minimum, Sum, and Timestamp.
Add another criteria set Adds another criteria set. The filter returns results that match one
criteria set or another.
Previous, Next, Create, and Cancel Options
At the end of each tab, you can go to the previous or next tab. You can also cancel the creation of the view. After you have
added all the details, click Create to create the view.
Distribution View
Distribution views provide aggregated data about resource distribution in the monitored environment. When you add a
distribution type of View to a dashboard, you can click a section of the pie chart or on one of the bars in the bar chart to
view the list of objects filtered by the selected segment.
Where You Find the Distribution View
From the left menu, click Infrastructure Operations > Views > Create. Click Distribution from the right page.
Name and Configuration Tab
Option Description
Name Name of the view as it appears on the Views page.
VMware by Broadcom  4161

---
## page 4162

 VMware Cloud Foundation 9.0
Option Description
Description Description of the view.
Configuration
Visualization You can view the data as a pie chart, a bar chart, or a donut chart.
When you add a distribution type of View to a dashboard, you
can click a section of the pie chart, or on one of the bars in the
bar chart, or a section of the donut chart to view the list of objects
filtered by the selected segment. You can select the display colors
for single or multi-colored charts.
Coloring
Colorize The colors of the slices in the pie chart are displayed in the order
of the colors in the color palette.
Select Color Select the color that you want the chart to appear in. If there
is more than one slice in a pie chart, the colors are chosen
sequentially from the color palette. In a bar chart, the bars are all
the same color.
Distribution Type > Dynamic Distribution
Buckets Count The number of buckets to use in the data distribution.
Buckets Size Interval The bucket size is determined by the defined interval divided by
the specified number of buckets.
Buckets > Size > Logarithmic bucketing The bucket size is calculated to logarithmically increasing sizes.
This provides a continuous coverage of the whole range with the
specified number of buckets. The base of the logarithmic sizing is
determined by the given data.
Buckets > Size > Simple Max/Min bucketing The bucket size is divided equally between the measured min and
max values. This provides a continuous coverage of the whole
range with the specified number of buckets.
Distribution Type > Manual Distribution Specify the number of buckets and the minimum and maximum
values of each bucket.
You can also select a color for each defined bucket that you
specify.
Distribution Type > Discrete Distribution Specify the number of buckets in which VCF Operations
distributes the data.
If you increase the number of buckets, you can see more detailed
data.
Distribution Type > Summary
Settings
Make the view available for > Dashboards through the View
widget
Select if you want to make the view available in a dashboard.
Make the view available for > Report template creation and
modification
Select if you want to make the view available in a report template.
Make the view available for > Details tab in the environment Select if you want to make the view available in the Detail tab of a
specific object.
Hide the view for the selected object types Select an object type for which you do not want to see this view.
VMware by Broadcom  4162

---
## page 4163

 VMware Cloud Foundation 9.0
Option Description
For example, you have a trend view with the subject <virtual
machines>. It is visible when you select any of its parent objects.
You add a data center from the list. The view is not visible
anymore on the data center level.
Data Tab
The data definition process includes adding properties, metrics, policies, or data that adapters provide to a view. These
are the items by which VCF Operations collects, calculates, and presents the information for the view.
How to Add Data to a View
If you selected more than one subject, click the subject for which you add data. Double-click either a metric or a property
from the tree in the left panel to add it to the view. For each subject that you select, the data available to add might be
different. The Data, Transformation, and Configuration details are displayed.
You can see a live preview of the view type when you select a subject and associated data, and then click Select preview
source.
Option Description
Add Subject Select the base object type for which the view shows information.
The subject you specify determines where the view is applicable.
If you select more than one subject, the view is applicable for each
of them.
Data Grid options
Data selection tree Double-click to select a metric or a property.
Data column Click the metric or property to enter configuration details in the
Configuration column.
Transformation column Displays the type of transformation applied to the data.
Configuration column
Metric name Default metric name.
Metric label Customizable label as it appears in the view or report.
Units Depends on the added metric or property. You can select in what
unit to display the values. For example, for CPU|Demand (MHz)
from the Units drop-down menu, you can change the value to Hz,
KHz, or GHz. If you select Auto, the scaling is set to a meaningful
unit.
Sort order Orders the values in ascending or descending order.
Transformation Determines what calculation method is applied on the raw data.
You can select the type of transformation:
• Minimum. The minimum value of the metric over the selected
time range.
• Maximum. The maximum value of the metric over the selected
time range.
• Average. The mean of all the metric values over the selected
time range.
• Sum. The sum of the metric values over the selected time
range.
VMware by Broadcom  4163

---
## page 4164

 VMware Cloud Foundation 9.0
Option Description
• First. The first metric value for the selected time range.
• Last. The last value of a metric within the selected time range.
If you have selected Last as the transformation in versions
before vRealize Operations 6.7, and the end of specified time
range is not before the last five minutes, use the Current
transformation.
• Current. The last available value of a metric if it was last
updated not before five collection cycles were complete,
otherwise it is null.
• Standard Deviation. The standard deviation of the metric
values.
• Metric Correlation. Displays the value when another metric is
at the minimum or maximum. For example, displays the value
for memory.usage when cpu.usage is at a maximum.
• Forecast. Performs a regressive analysis and predicts future
values. Displays the last metric value of the selected range.
• Percentile. Calculates the specified percentile for the data
range. For example, you can view the 95th percentile, 99th
percentile, and so on.
• Expression. Allows you to construct a mathematical
expression over existing transformations using minus, plus,
multiplication, division, unary minus, unary plus, and round
brackets. For example, sum/((max + min)/2). You can
use the operands of some of the existing transformations such
as, max, min, avg, sum, first, last, current. You cannot use
standard deviation, forecast, metric correlation, and percentile.
You can customize the metric unit label when you select the
Expression transformation. For example, some of the metric
units available are, vCPUs, Bps, KBps, Mbps, and MBps.
Series Roll up The time interval at which the data is rolled up. You can select
one of the available options. For example, if you select Sum as
a Transformation and 5 minutes as the roll-up interval, then the
system selects 5-minute interval values and adds them.
This option is applicable to the Transformation configuration
option.
Time Settings Tab
Use the time settings to select the time interval of data transformation.
You can set a time range for a past period or set a future date for the end of the time period. When you select a future end
date and no data is available, the view is populated by forecast data. Data is calculated based on the browser time
Table 1180: Time Settings Options
Configuration Option Description
Time Range Mode In Basic mode, you can select date ranges.
In Advanced mode, you can select any combination of relative or
specific start and end dates.
Relative Date Range Select a relative date range of data transformation.
Available in Basic mode.
Specific Date Range Select a specific date range of data transformation.
VMware by Broadcom  4164

---
## page 4165

 VMware Cloud Foundation 9.0
Configuration Option Description
Available in Basic mode.
Absolute Date Range Select a date or time range to view data for a time unit such as a
complete month or a week. For example, you can run a report on
the third of every month for the previous month. Data from the first
to the end of the previous month is displayed as against data from
the third of the previous month to the third of the current month.
The units of time available are: Hours, Days, Weeks, Months,
and Years.
The locale settings of the system determine the start and end of
the unit. For example, weeks in most of the European countries
begin on Monday while in the United States they begin on Sunday.
Available in Basic mode.
Relative Start Date Select a relative start date of data transformation.
Available in Advanced mode.
Relative End Date Select a relative end date of data transformation.
Available in Advanced mode.
Specific Start Date Select a specific start date of data transformation.
Available in Advanced mode.
Specific End Date Select a specific end date of data transformation.
Available in Advanced mode.
Currently selected date range Displays the date or time range you selected. For example, if you
select a specific date range from 5/01/2016 to 5/18/2016, the
following information is displayed: May 1, 2016 12:00:00
AM to May 18, 2016 11:55:00 PM .
Filter Tab
The filter option allows you to add additional criteria when the view displays too much information.
To add a filter to a view, from an existing or new view dialog box, click the Filter tab. Fill in the details for each row and
click Add.
Each subject has a separate filter box. For Alerts Roll up, Alert, and Symptom subjects not all applicable metrics are
supported for filtering.
Table 1181: Filter Add Options
Option Description
Add Adds another criteria to the criteria set. The filter returns results
that match all the specified criteria.
If you add a filter for an instance metric or property, all the
instances of the object for which the criteria is met, will be
displayed in the preview screen.
For instance metrics or properties, you can filter based on
transformations such as, Current, Average, First, Last, Maximum,
Minimum, Sum, and Timestamp.
Add another criteria set Adds another criteria set. The filter returns results that match one
criteria set or another.
VMware by Broadcom  4165

---
## page 4166

 VMware Cloud Foundation 9.0
Previous, Next, Create, and Cancel Options
At the end of each tab, you can go to the previous or next tab. You can also cancel the creation of the view. After you have
added all the details, click Create to create the view.
Text View
Text views allows you to insert provided text. The text can be dynamic and contain metrics and properties. You can format
text to increase or decrease the font size, change the font color, highlight text, and align text to the left, right, or center.
You can also make the selected text appear bold, in italics, or underlined. By default the text view is available only for
report template creation and modification. You can change this in the Visibility option in the Name and Configuration
tab.
Where You Find the Text View
From the left menu, click Infrastructure Operations > Views > Create. Click Text from the right page.
Name and Configuration Tab
Option Description
Name Name of the view as it appears on the Views page.
Description Description of the view.
Settings
Make the view available for > Dashboards through the View
widget
Select if you want to make the view available in a dashboard.
Make the view available for > Report template creation and
modification
Select if you want to make the view available in a report template.
This is the default option.
Make the view available for > Details tab in the environment Select if you want to make the view available in the Detail tab of a
specific object.
Hide the view for the selected object types Select an object type for which you do not want to see this view.
For example, you have a list view with the subject <virtual
machines>. It is visible when you select any of its parent objects.
You add a data center from the list. The view is not visible
anymore on the data center level.
Data Tab
The data definition process includes adding properties, metrics, policies, or data that adapters provide to a view. These
are the items by which VCF Operations collects, calculates, and presents the information for the view.
How to Add Data to a View
If you selected more than one subject, click the subject for which you add data. Double-click the data from the tree in the
left panel to add it to the view. For each subject, the data available to add might be different. The data and configuration
details are displayed.
You can see a live preview of the view type when you select a subject and associated data, and then click Select preview
source.
VMware by Broadcom  4166

---
## page 4167

 VMware Cloud Foundation 9.0
Option Description
Add Subject Select the base object type for which the view shows information.
The subject you specify determines where the view is applicable.
If you select more than one subject, the view is applicable for each
of them.
Data Grid options
Data selection tree Select a metric or property.
Data column Click the metric or property to enter configuration details in the
Configuration column.
You can also enter text to display in the view.
Configuration column
Metric name Default metric name.
Metric label Customizable label as it appears in the view or report.
Units Depends on the added metric or property. You can select in what
unit to display the values. For example, for CPU|Demand(MHz)
from the Units drop-down menu, you can change the value to Hz,
KHz, or GHz. If you select Auto, the scaling is set to a meaningful
unit.
Transformation Determines what calculation method is applied on the raw data.
You can select the type of transformation:
• Minimum. The minimum value of the metric over the selected
time range.
• Maximum. The maximum value of the metric over the selected
time range.
• Average. The mean of all the metric values over the selected
time range.
• Sum. The sum of the metric values over the selected time
range.
• First. The first metric value for the selected time range.
• Last. The last value of a metric within the selected time range.
If you have selected Last as the transformation in versions
before vRealize Operations 6.7, and the end of specified time
range is not before the last five minutes, use the Current
transformation.
• Current. The last available value of a metric if it was last
updated not before five collection cycles were complete,
otherwise it is null.
• Standard Deviation. The standard deviation of the metric
values.
• Metric Correlation. Displays the value when another metric is
at the minimum or maximum. For example, displays the value
for memory.usage when cpu.usage is at a maximum.
• Forecast. Performs a regressive analysis and predicts future
values. Displays the last metric value of the selected range.
• Percentile. Calculates the specified percentile for the data
range. For example, you can view the 95th percentile, 99th
percentile, and so on.
VMware by Broadcom  4167

---
## page 4168

 VMware Cloud Foundation 9.0
Option Description
• Expression. Allows you to construct a mathematical
expression over existing transformations using minus, plus,
multiplication, division, unary minus, unary plus, and round
brackets. For example, sum/((max + min)/2). You can
use the operands of some of the existing transformations such
as, max, min, avg, sum, first, last, current. You cannot use
standard deviation, forecast, metric correlation, and percentile.
You can customize the metric unit label when you select the
Expression transformation. For example, some of the metric
units available are, vCPUs, Bps, KBps, Mbps, and MBps.
Series Roll up The time interval at which the data is rolled up. You can select
one of the available options. For example, if you select Sum as
a Transformation and 5 minutes as the roll-up interval, then the
system selects 5-minute interval values and adds them.
This option is applicable to the Transformation configuration
option.
Time Settings
Use the time settings to select the time interval of data transformation. These options are available for all view types,
except Image.
You can set a time range for a past period or set a future date for the end of the time period. When you select a future end
date and no data is available, the view is populated by forecast data. Data is calculated based on the browser time.
Table 1182: Time Settings Options
Configuration Option Description
Time Range Mode In Basic mode, you can select date ranges.
In Advanced mode, you can select any combination of relative or
specific start and end dates.
Relative Date Range Select a relative date range of data transformation.
Available in Basic mode.
Specific Date Range Select a specific date range of data transformation.
Available in Basic mode.
Absolute Date Range Select a date or time range to view data for a time unit such as a
complete month or a week. For example, you can run a report on
the third of every month for the previous month. Data from the first
to the end of the previous month is displayed as against data from
the third of the previous month to the third of the current month.
The units of time available are: Hours, Days, Weeks, Months,
and Years.
The locale settings of the system determine the start and end of
the unit. For example, weeks in most of the European countries
begin on Monday while in the United States they begin on Sunday.
Available in Basic mode.
Relative Start Date Select a relative start date of data transformation.
Available in Advanced mode.
Relative End Date Select a relative end date of data transformation.
Available in Advanced mode.
Specific Start Date Select a specific start date of data transformation.
VMware by Broadcom  4168

---
## page 4169

 VMware Cloud Foundation 9.0
Configuration Option Description
Available in Advanced mode.
Specific End Date Select a specific end date of data transformation.
Available in Advanced mode.
Currently selected date range Displays the date or time range you selected. For example, if you
select a specific date range from 5/01/2016 to 5/18/2016, the
following information is displayed: May 1, 2016 12:00:00
AM to May 18, 2016 11:55:00 PM .
Filter
The filter option allows you to add additional criteria when the view displays too much information.
To add a filter to a view, from an existing or new view dialog box, click the Filter tab. Fill in the details for each row and
click Add.
Each subject has a separate filter box. For Alerts Roll up, Alert, and Symptom subjects not all applicable metrics are
supported for filtering.
Table 1183: Filter Add Options
Option Description
Add Adds another criteria to the criteria set. The filter returns results
that match all the specified criteria.
If you add a filter for an instance metric or property, all the
instances of the object for which the criteria is met, will be
displayed in the preview screen.
For instance metrics or properties, you can filter based on
transformations such as, Current, Average, First, Last, Maximum,
Minimum, Sum, and Timestamp.
Add another criteria set Adds another criteria set. The filter returns results that match one
criteria set or another.
Previous, Next, Create, and Cancel Options
At the end of each tab, you can go to the previous or next tab. You can also cancel the creation of the view. After you have
added all the details, click Create to create the view.
Image View
Image views allow you to insert a static image. By default the image view is available only for report template creation and
modification.
Where You Find the Image View
From the left menu, click Infrastructure Operations > Views > Create. Click Image from the right page.
Name and Configuration Tab
Option Description
Name Name of the view as it appears on the Views page.
VMware by Broadcom  4169