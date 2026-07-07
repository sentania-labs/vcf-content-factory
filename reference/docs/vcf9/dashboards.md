# dashboards (VCF 9.0, pages 3921-4053)


---
## page 3921

 VMware Cloud Foundation 9.0
Energy Efficient Infrastructure Dashboard
Use this dashboard to identify old hardware, such as compute and storage, in the data center and replace them with new
generation hardware components that are more power efficient. You can also use this dashboard to reduce the overheads
and buffers and identify smaller clusters that have higher overheads. The aim is to run with fewer overheads and buffer,
without compromising on performance.
How to Use the Dashboard
• Smaller clusters have a relatively higher overhead. A cluster with two nodes has 50% overhead, while a cluster with 10
nodes has only 10% overhead. Clusters with lesser capacity require more hosts and hence consume more electricity.
The Small Clusters table lists clusters that meet one of the following criteria:
– <=4 nodes
– <=120 CPU cores and < 1 TB memory
Click a cluster row to view the context of the selected cluster. An empty widget indicates that the defined efficiency
goals are met.
• Advancements in technology help ESXi hosts to deliver higher efficiency. ESXi hosts can deliver more CPU and
memory capacity, often with low power requirements. The Ageing Compute Hardware table lists ESXi hosts that
meet one of the following criteria:
– ESXi version 6.0 or older
– <=40 CPU cores and < 256 GB of memory
Click a cluster row to view the context of the selected cluster. An empty widget indicates that the defined efficiency
goals are met.
• Just like compute hardware, newer storage hardware is typically more power efficient than older storage hardware.
The Ageing Storage Hardware table lists datastores that meet the following criteria:
– VMFS version 5 or older.
– Not a local datastore.
Click a cluster row to view the context of the selected cluster. An empty widget indicates that the defined efficiency
goals are met.
If you have goals that are different from those defined, you can modify the criteria of the widgets by updating the filters.
Disclaimer:
The conversion calculators and information shown in this documentation reference public information and have been
provided to help translate abstract carbon emissions numbers into easily understandable terms solely for informational
purposes. You should not rely on the calculators or information provided herein for any other purpose, including for any
regulatory disclosure or diligence purposes. Broadcom may update, upgrade, revise, adjust or otherwise change the
features and conversion methodologies at any time. Broadcom has not separately reviewed, approved, or endorsed
the public information or third-party websites. No representation or warranty is made by Broadcom as to the accuracy,
reasonableness or completeness of the calculations and related information herein.
Configuring Dashboards and Widgets
Dashboards present a visual overview of the performance and state of objects in your virtual infrastructure. Widgets are
the visual components used to build dashboards, displaying information about attributes, resources, applications, or
overall processes within your environment.
Dashboards in VCF Operations
Dashboards present a visual overview of the performance and state of objects in your virtual infrastructure. You use
dashboards to determine the nature and timeframe of existing and potential issues with your environment. You create
dashboards by adding widgets to a dashboard and configuring them.
VMware by Broadcom  3921

---
## page 3922

 VMware Cloud Foundation 9.0
VCF Operations collects performance data from monitored software and hardware resources in your enterprise and
provides predictive analysis and real-time information about problems. The data and analysis are presented through
alerts, in configurable dashboards, on predefined pages, and in several predefined dashboards.
• You can start with several predefined dashboards in VCF Operations.
• You can create extra ones that meet your specific needs using widgets, views, badges, and filters to change the focus
of the information.
• You can clone and edit the predefined dashboards or start from scratch.
• To display data that shows dependencies, you can add widget interactions in dashboards.
• You can provide role-based access to various dashboards for better collaboration in teams.
Table 1142: Features
Features Description
Manage You can also manage dashboards by clicking Infrastructure
Operations > Dashboards & Reports. From the Dashboards page,
click Manage.
Create Use this option to create a dashboard. See Create and Configure
Dashboards.
Search You can search for a dashboard across the Favorites, Recents, and
All folders in the Dashboards panel.
Favorites You can mark a dashboard as a favorite using the Favorite icon at
the top of each dashboard. All the dashboards that you have marked
as a favorite, are listed under the Favorites folder in the Dashboards
panel.
Recents The dashboards are listed in the order in which you select them, with
the most recent dashboard that you selected, appearing at the top. Up
to ten dashboards can be displayed as Recent dashboards.
If you do not pin the dashboard and log out of the user interface, on
logging back in, the dashboard is removed from the Recents folder.
Shared If you have shared the dashboard, the shared icon is displayed
against the dashboard name.
All Lists the dashboard folders and the dashboards that are activated.
You can use this menu for quick navigation through your dashboards.
When you navigate to a dashboard using the Infrastructure
Operations > Dashboards & Reports option, the dashboards are
listed in the panel under All. You can also search for dashboards
using keywords and letters.
Actions Available dashboard actions, such as edit, delete, Set as Dashboards
Home, and Add to Product Home. These actions are applied directly
to the dashboard that you are on.
Set as Dashboards Home: Adds the dashboard to the Favorites list.
To remove the dashboard from the Favorites list, select Actions >
Unset as Dashboards Home.
Add to Product Home: Adds the dashboard as a tab in the Home
page. You can also reorder the tabs in the Home page using drag and
drop. You can also set this option by clicking the Home icon at the top
right side of the dashboard. To remove the dashboard from the Home
page, select Actions > Remove from Product Home.
VMware by Broadcom  3922

---
## page 3923

 VMware Cloud Foundation 9.0
Features Description
Note:  You can add up to 5 dashboards to the Home page.
Dashboard Time The dashboard time panel is activated by default on all predefined
and user-created dashboards. Using this option, you can select a time
for the widgets in the dashboard. The default time is 6 hours. The pre-
defined time/day options in the panel are 1 hour, 6 hours, 24 hours, or
7 days. You can also set a customized time option.
To activate widgets to use the dashboard time, select Date
Controls/Time Range > Dashboard Time from the widget
toolbar. Some widgets have Dashboard Time as the default option.
For example, Metric Chart, View, Rolling View, Sparkline, Health
Chart, and Mashup Chart widgets.
Dashboard time persists if:
• You activate a widget in a dashboard to use the dashboard time
and then log out and log back in, or
• You activate a widget in a dashboard to use the dashboard time,
and you export and then import the dashboard into another
instance of VCF Operations.
Accessing Predefined Dashboards
You can access some of the useful, predefined dashboards from the Dashboards home page.
To access these dashboards, from the left menu, click Infrastructure Operations > Dashboards & Reports. Click
Dashboards> All.
The dashboards are categorized as follows: Availability, Configuration, Inventory, Performance, Capacity, and Cost to
name a few. To easily access some of the useful, predefined dashboards under these categories, click on the drop-down
button against the selected category and click on the specific dashboard.
Types of Dashboards
You can use the predefined dashboards or create your own custom dashboard in VCF Operations.
See predefined dashboards for more information.
Custom Dashboards
You can create dashboards that meet your environment needs in VCF Operations.
For information about creating a dashboard, see Create and Configure Dashboards.
Create and Configure Dashboards
To view the status of all objects in VCF Operations, create a dashboard by adding widgets or views. You can create and
modify dashboards and configure them to meet your environment needs.
VMware by Broadcom  3923

---
## page 3924

 VMware Cloud Foundation 9.0
1. From the left menu, click Infrastructure Operations > Dashboards & Reports.
2. Click Dashboards > Create.
3. Complete the following steps to:
a) Enter a name for the dashboard.
Dashboard Name
b) Add widgets or views to the dashboard.
 Widget or View List Details
c) Configure widget interactions.
Widget and View Interactions Details
d) Create dashboard navigation.
Dashboard Navigation Details
4. Click Save.
5. Click Actions > Edit Dashboard to modify the dashboard.
Dashboard Name
The name and visualization of the dashboard as it appears on the VCF Operations Home page.
Where You Add a Name in a Dashboard
To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards & Reports. Click
Dashboards> Create to add a dashboard. Enter a name in the New Dashboard field.
To edit your dashboard, from the left menu, click Infrastructure Operations > Dashboards & Reports. Click
Dashboards and select the dashboard you want to edit and select Actions > Edit Dashboard.
If you use a forward slash while entering a name, the forward slash acts as a group divider and creates a folder with the
specified name in the dashboards list if the name does not exist. For example, if you name a dashboard clusters/
hosts, the dashboard is named hosts under the group clusters.
Related Links
Dashboard Navigation Details on page 3927
You can apply sections or context from one dashboard to another. You can connect widgets and views to widgets and
views in the same dashboard or to other dashboards to investigate problems or better analyze the provided information.
Widget and View Interactions Details on page 3926
You can connect widgets and views so that the information they show depends on each other.
Widget or View List Details on page 3925
VCF Operations provides a list of widgets or views that you can add to your dashboard to monitor specific metrics and
properties of objects in your environment.
Widget Interactions on page 3936
Widget interactions are the configured relationships between widgets in a dashboard where one widget provides
information to a receiving widget. When you are using a widget in the dashboard, you select data on one widget to limit
the data that appears in another widget, allowing you to focus on a smaller subset data.
Widget Definitions List on page 3944
A widget is a pane on a dashboard that contains information about configured attributes, resources, applications, or the
overall processes in your environment. Widgets can provide a holistic, end-to-end view of the health of all the objects and
applications in your enterprise. If your user account has the necessary access rights, you can add and remove widgets
from your dashboards.
VMware by Broadcom  3924

---
## page 3925

 VMware Cloud Foundation 9.0
 Widget or View List Details
VCF Operations provides a list of widgets or views that you can add to your dashboard to monitor specific metrics and
properties of objects in your environment.
Where You Add Widgets or Views to a Dashboard
To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards & Reports. Click
Dashboards> Create to add a dashboard.
To edit your dashboard, from the left menu, click Infrastructure Operations > Dashboards & Reports. Click
Dashboards and select the dashboard you want to edit and select Actions > Edit Dashboard
How to Add Widgets or Views to a Dashboard
In the widgets list panel, you see a list of predefined VCF Operations widgets or views that are most commonly used.
Click Show More to view all the widgets and views. To add a widget or view to the dashboard workspace in the upper
panel, you can:
• Drag the widget or view to the dashboard workspace in the upper panel, or
• Click on a widget or view from the widgets list panel, view a brief description of the widget or view from the pop up box
and then click Add to Dashboard, or
• Double-click on the widget or view.
To locate a widget or view, you can enter the name or part of the name of a widget or view in the Filter > Name option.
For example, when you enter top, the list is filtered to display the Top Alerts, Top-N, and Topology Graph widgets. You
can then select the widget you require. You can also filter by either widgets or views by selecting Filter > Show to add a
widget or view to the dashboard. Drag the widget or view to the dashboard workspace in the upper panel.
Note:  The following widgets are deprecated. Usage of these widgets is discouraged as they will be phased out in future
releases. Deprecated widgets are marked with a yellow triangle.
• Current Policy
• Weather Map
• Anomalies
• DRS Cluster Settings
• Efficiency
• Environment Status
• Risk
• Environment
• Container Overview
• Faults
Most widgets or views must be configured individually to display information. For more information about how to configure
each widget, see Widgets in VCF Operations.
How to Arrange Widgets or Views in a Dashboard
You can modify your dashboard layout to suit your needs. By default, the first widgets or views that you add are
automatically arranged horizontally wherever you place them.
• To position a widget or a view, drag the widget or view to the desired location in the layout. Other widgets and views
automatically rearrange to make room.
• To resize a widget or a view, drag the bottom-right corner of the widget or the view.
• To maximize or minimize a widget or a view, use the maximize and minimize options in the top-right corner.
VMware by Broadcom  3925

---
## page 3926

 VMware Cloud Foundation 9.0
Related Links
Dashboard Navigation Details on page 3927
You can apply sections or context from one dashboard to another. You can connect widgets and views to widgets and
views in the same dashboard or to other dashboards to investigate problems or better analyze the provided information.
Dashboard Name on page 3924
The name and visualization of the dashboard as it appears on the VCF Operations Home page.
Widget and View Interactions Details on page 3926
You can connect widgets and views so that the information they show depends on each other.
Widget Interactions on page 3936
Widget interactions are the configured relationships between widgets in a dashboard where one widget provides
information to a receiving widget. When you are using a widget in the dashboard, you select data on one widget to limit
the data that appears in another widget, allowing you to focus on a smaller subset data.
Widget Definitions List on page 3944
A widget is a pane on a dashboard that contains information about configured attributes, resources, applications, or the
overall processes in your environment. Widgets can provide a holistic, end-to-end view of the health of all the objects and
applications in your enterprise. If your user account has the necessary access rights, you can add and remove widgets
from your dashboards.
Widget and View Interactions Details
You can connect widgets and views so that the information they show depends on each other.
Where You Create Widget and View Interactions
To create interactions for widgets or views in a dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards> Create to add a dashboard. From the toolbar, click Show Interactions.
To edit your dashboard, from the left menu, click Infrastructure Operations > Dashboards & Reports. Click
Dashboards and select the dashboard you want to edit and select Actions > Edit Dashboard.
Internal interactions are interactions defined between widgets in a single dashboard. External interactions are interactions
defined between a widget in one dashboard and widget/s in another dashboard.
How to Create and Remove Widget Interactions
The list of available interactions depends on the widgets or views in the dashboard. Widgets and views can provide,
receive, and can both provide and receive interactions at the same time.
To create interactions, click Show Interactions. Click a provider plug and drag to the receiver. You can also apply
interactions from receiver to provider plugs. For more information about how interactions work, see Widget Interactions.
To remove interactions, click on the interaction line and select Remove Interaction. You can also click the provider plug
and select Remove Interaction > <widget name>.
Note:  You can create up to 25 widget interactions in a dashboard.
How to Easily View Widget Interactions
To view widget interactions from a dashboard, click on an object from a provider widget that has widget interactions
defined. A window appears with the external and internal widget interaction details. Clicking on an external interaction
takes you to the external dashboard. Click on the internal interaction to view the details in the receiver widget.
Related Links
VMware by Broadcom  3926

---
## page 3927

 VMware Cloud Foundation 9.0
Dashboard Navigation Details on page 3927
You can apply sections or context from one dashboard to another. You can connect widgets and views to widgets and
views in the same dashboard or to other dashboards to investigate problems or better analyze the provided information.
Dashboard Name on page 3924
The name and visualization of the dashboard as it appears on the VCF Operations Home page.
Widget or View List Details on page 3925
VCF Operations provides a list of widgets or views that you can add to your dashboard to monitor specific metrics and
properties of objects in your environment.
Widget Interactions on page 3936
Widget interactions are the configured relationships between widgets in a dashboard where one widget provides
information to a receiving widget. When you are using a widget in the dashboard, you select data on one widget to limit
the data that appears in another widget, allowing you to focus on a smaller subset data.
Widget Definitions List on page 3944
A widget is a pane on a dashboard that contains information about configured attributes, resources, applications, or the
overall processes in your environment. Widgets can provide a holistic, end-to-end view of the health of all the objects and
applications in your enterprise. If your user account has the necessary access rights, you can add and remove widgets
from your dashboards.
Dashboard Navigation Details
You can apply sections or context from one dashboard to another. You can connect widgets and views to widgets and
views in the same dashboard or to other dashboards to investigate problems or better analyze the provided information.
Where You Add Another Dashboard
To create dashboard navigation to a dashboard, from the left menu, click Infrastructure Operations > Dashboards &
Reports. Click Dashboards> Create to add a dashboard. In the dashboard workspace, click Show Interactions. From
the Select Another Dashboard drop-down menu, select the dashboard to which you want to navigate.
To edit your dashboard, from the left menu, click Infrastructure Operations > Dashboards & Reports. Click
Dashboards and select the dashboard you want to edit and select Actions > Edit Dashboard.
How Dashboard Navigation Works
You can create dashboard navigation only for provider widgets and views. The provider widget or view sends information
to the destination widget or view. When you create dashboard navigation, the destination widgets or views are filtered
based on the information type they can receive.
How to Add Dashboard Navigation to a Dashboard
The list of available dashboards for navigation depends on the available dashboards and the widgets and views in the
current dashboard. To add navigation, you can drag from a sender widget interaction plug to a receiver widget interaction
plug. You can select more than one applicable widget or view.
Note:  If a dashboard is unavailable for selection, it is unavailable for dashboard navigation.
The Dashboard Navigation icon (
  ) appears in the top menu of each widget or view when a dashboard navigation is
available.
After you have set widget interaction in the provider dashboard, the widget and menu bar are highlighted and two arrows
appear in the top-left corner of the widget. After you have set widget interaction, clicking the object in the provider widget
takes you to the receiver widget of the navigated dashboard.
VMware by Broadcom  3927

---
## page 3928

 VMware Cloud Foundation 9.0
Related Links
Dashboard Name on page 3924
The name and visualization of the dashboard as it appears on the VCF Operations Home page.
Widget and View Interactions Details on page 3926
You can connect widgets and views so that the information they show depends on each other.
Widget or View List Details on page 3925
VCF Operations provides a list of widgets or views that you can add to your dashboard to monitor specific metrics and
properties of objects in your environment.
Widget Interactions on page 3936
Widget interactions are the configured relationships between widgets in a dashboard where one widget provides
information to a receiving widget. When you are using a widget in the dashboard, you select data on one widget to limit
the data that appears in another widget, allowing you to focus on a smaller subset data.
Widget Definitions List on page 3944
A widget is a pane on a dashboard that contains information about configured attributes, resources, applications, or the
overall processes in your environment. Widgets can provide a holistic, end-to-end view of the health of all the objects and
applications in your enterprise. If your user account has the necessary access rights, you can add and remove widgets
from your dashboards.
Manage Dashboards
You can select dashboards individually or as a group and perform several actions.
To manage your dashboards, from the left menu, click Infrastructure Operations > Dashboards & Reports. Click
Dashboards> Manage. Use the options from the horizontal ellipsis next to the Add option.
All the dashboards are listed on this page. You can filter the dashboards based on the name of the dashboard, the
dashboard folder, activated dashboards, shared dashboards, or the dashboard owner. You can click Add to create a
dashboard. For information about creating a dashboard, see Create and Configure Dashboards.
You can select a dashboard from the list, click the vertical ellipsis against each dashboard, and select the various options
such as edit, delete, clone, and deactivate a dashboard. You can also change ownership of dashboards and export the
dashboard. By default, the list of dashboards is sorted by name and all the columns can be sorted.
Note:  A wrench icon appears when the data in an imported dashboard depends on the existence of one or more
adapters that are currently not present. The wrench icon disappears if the required data in an imported dashboard
appears in VCF Operations after configuration.
Imported dashboards regardless of used data, remain stuck and include a wrench icon if the dashboard that is stuck (with
the wrench icon), already exists.
Datagrid Options
Column Names Description
Name Displays the name of the dashboard.
Folder Lists the folder to which each dashboard belongs.
Description Displays the description of the dashboard.
Activated Displays whether the dashboard is activated or not. You can also
activate and deactivate the dashboard.
URL Displays whether the dashboard is shared externally. For
dashboards that have been shared, click to view the shared links.
VMware by Broadcom  3928

---
## page 3929

 VMware Cloud Foundation 9.0
Column Names Description
Shared Displays whether the dashboard is shared internally. Click the
icon to view and edit the groups to which the dashboard has been
shared from the Group Sharing dialog box.
From the Group Sharing dialog box, to share dashboard edit
privileges with the group, you can click the Allow Editing check
box or click the pencil icon if a dashboard is shared with a group.
Note:  Users who are part of the user group to whom the
dashboard has been shared, will see an unlocked or locked icon
in the Shared column. The icon is unlocked when the user with
whom the dashboard is shared can edit it, and the icon is locked
when the dashboard cannot be edited.
Editable Displays if the dashboard is editable.
Owner Displays the owner of the dashboard.
Report Usage Displays the number of reports where the dashboard is used. Click
the number in the column to view the name of the report/s. Click
the report name to navigate to the report template in edit mode.
Last Modified Displays the date the dashboard was last modified.
Modified By Displays the user who last modified the dashboard.
You can select more than one dashboard and perform a set of options by clicking the horizontal ellipsis next to the Add
option.
Table 1143: Dashboards Options
Option Description Usage
Delete Deletes a dashboard.
Activate Activates a dashboard that was
previously deactivated.
Deactivate Deactivates a dashboard.
Change Ownership Assigns a new owner to the
dashboard.
After you assign a dashboard to a new owner, the
dashboard is no longer displayed as one of your
dashboards.
When you transfer a dashboard that was previously
shared with user groups, information about the shared
user groups and group hierarchy is retained.
Export When you export a dashboard, VCF
Operations creates a dashboard file
in JSON format.
You can export a dashboard from one VCF Operations
instance and import it to another.
To export a dashboard, select the dashboard that you
want to export, and click Export from the horizontal
ellipsis.
Import A PAK or JSON file that contains
dashboard information from VCF
Operations.
You can import a dashboard that was exported from
another VCF Operations instance.
To import a dashboard:
1. Click the Import option from horizontal ellipsis.
2. Click Browse and select a Dashboard ZIP, PAK, or
JSON file to import.
VMware by Broadcom  3929

---
## page 3930

 VMware Cloud Foundation 9.0
Option Description Usage
3. Select if you want to Overwrite or Rename the file
in case of a conflict.
4. Click Import to import the dashboard, and click
Done.
Auto-rotate Dashboards Changes the order of the dashboard
tabs on VCF Operations home page.
You can configure VCF Operations to switch from one
dashboard to another. For more information, see Auto-
Rotate Dashboards.
Manage Summary Dashboards Provides you with an overview of the
state of the selected object, group, or
application.
You can change the Summary tab with a dashboard
to get information specific to your needs. For more
information, see Manage Summary Dashboards
Manage Dashboard Folders Groups dashboards in folders. You can create dashboard folders to group the
dashboards in a way that is meaningful to you. For more
information, see Manage Dashboard Folders.
Manage Dashboard Sharing Makes a dashboard available to
other users or user groups.
You can share a dashboard or dashboard template with
one or more user groups. For more information, see
Share Dashboards with Users.
The dashboard list depends on your access rights.
Related Links
Auto-Rotate Dashboards on page 3931
You can change the order of the dashboard tabs on your home page. You can configure VCF Operations to switch from
one dashboard to another. This feature is useful if you have several dashboards that show different aspects of your
enterprise's performance and you want to look at each dashboard in turn.
Manage Summary Dashboards on page 3930
The Summary tab provides you with an overview of the state of the selected object, group, or application. You can
change the Summary tab with a dashboard to get information specific to your needs.
Manage Dashboard Folders on page 3932
You can create dashboard folders to group the dashboards in a way that is meaningful to you.
Share Dashboards with Users on page 3933
You can share a dashboard with one or more user groups. When you share a dashboard, it becomes available to all the
users in the user group that you select. The dashboard appears the same to all the users who share it. If you edit a shared
dashboard, the dashboard changes for all users. Other users can only view a shared dashboard. They cannot change it.
Manage Summary Dashboards
The Summary tab provides you with an overview of the state of the selected object, group, or application. You can
change the Summary tab with a dashboard to get information specific to your needs.
Where You Configure a Summary Tab Dashboard
To manage the summary dashboards, from the left menu, click Infrastructure Operations > Dashboards & Reports.
Click Dashboards> Manage. Click the horizontal ellipsis next to the Add option and select Manage Summary
Dashboards.
VMware by Broadcom  3930

---
## page 3931

 VMware Cloud Foundation 9.0
How You Manage the Summary Dashboards
Table 1144: Manage Summary Dashboards Toolbar Options
Option Description
Use Default Click to use VCF Operations default Summary tab.
Assign a Dashboard Click to view the Dashboard List dialog box that lists all the
available dashboards.
Adapter Type Adapter type for which you configure a summary dashboard.
Filter Use a word search to limit the number of adapter types that
appear in the list.
To change the Summary tab for an object, select the object in the left panel, click the Assign a Dashboard icon. Select
a dashboard for it from the All Dashboards dialog box and click OK. From the Manage Summary Dashboards dialog box
click Save. You see the dashboard that you have associated to the object type when you navigate to the Summary tab of
the object details page.
Related Links
Manage Dashboards on page 3928
You can select dashboards individually or as a group and perform several actions.
Auto-Rotate Dashboards on page 3931
You can change the order of the dashboard tabs on your home page. You can configure VCF Operations to switch from
one dashboard to another. This feature is useful if you have several dashboards that show different aspects of your
enterprise's performance and you want to look at each dashboard in turn.
Manage Dashboard Folders on page 3932
You can create dashboard folders to group the dashboards in a way that is meaningful to you.
Share Dashboards with Users on page 3933
You can share a dashboard with one or more user groups. When you share a dashboard, it becomes available to all the
users in the user group that you select. The dashboard appears the same to all the users who share it. If you edit a shared
dashboard, the dashboard changes for all users. Other users can only view a shared dashboard. They cannot change it.
Auto-Rotate Dashboards
You can change the order of the dashboard tabs on your home page. You can configure VCF Operations to switch from
one dashboard to another. This feature is useful if you have several dashboards that show different aspects of your
enterprise's performance and you want to look at each dashboard in turn.
Where You Configure Auto-Rotation of a Dashboard
To reorder and configure a dashboard switch, from the left menu, click Infrastructure Operations > Dashboards &
Reports. Click Dashboards> Manage. Select Auto-rotate Dashboards from the horizontal ellipsis next to the Add
option.
How You Reorder the Dashboards
The list shows the dashboards as they are ordered. Drag the dashboards up and down to change their order on the home
page.
VMware by Broadcom  3931

---
## page 3932

 VMware Cloud Foundation 9.0
How You Configure an Automatic Dashboard Rotation
1. Double-click a dashboard from the list to configure.
2. From the Rotation drop-down menus, select On.
3. Select the time interval in seconds.
4. Select the dashboard to switch and click Update.
5. Click Save to save your changes.
On the home page, the current dashboard will switch to the dashboard that is defined after the specified time interval.
Related Links
Manage Dashboards on page 3928
You can select dashboards individually or as a group and perform several actions.
Manage Summary Dashboards on page 3930
The Summary tab provides you with an overview of the state of the selected object, group, or application. You can
change the Summary tab with a dashboard to get information specific to your needs.
Manage Dashboard Folders on page 3932
You can create dashboard folders to group the dashboards in a way that is meaningful to you.
Share Dashboards with Users on page 3933
You can share a dashboard with one or more user groups. When you share a dashboard, it becomes available to all the
users in the user group that you select. The dashboard appears the same to all the users who share it. If you edit a shared
dashboard, the dashboard changes for all users. Other users can only view a shared dashboard. They cannot change it.
Manage Dashboard Folders
You can create dashboard folders to group the dashboards in a way that is meaningful to you.
Where You Manage Dashboard Folders
To manage the dashboard folders, from the left menu, click Infrastructure Operations > Dashboards & Reports. Click
Dashboards> Manage. Click the horizontal ellipsis next to the Add option and click Manage Dashboard Folders.
How You Manage the Dashboard Folders
Table 1145: Manage Dashboard Folders Options
Option Description
Dashboards List A list with all available dashboards.
Folders A hierarchy tree with all the available group folders.
To create a dashboard folder, click New Folder in the Folders pane and enter the name of the folder. If you want to create
a folder under another folder, select a parent folder under which you want to create the child folder, then click New Folder.
To add a dashboard, drag one from the dashboards list to the selected folder in the Folders pane.
You can delete folders and/or detach dashboards from a folder, by selecting one or more folders and dashboards from the
Folders pane and by clicking Actions > Delete.
You can rename a folder by selecting a single folder from the Folders pane and by clicking Actions > Rename.
Related Links
VMware by Broadcom  3932

---
## page 3933

 VMware Cloud Foundation 9.0
Manage Dashboards on page 3928
You can select dashboards individually or as a group and perform several actions.
Auto-Rotate Dashboards on page 3931
You can change the order of the dashboard tabs on your home page. You can configure VCF Operations to switch from
one dashboard to another. This feature is useful if you have several dashboards that show different aspects of your
enterprise's performance and you want to look at each dashboard in turn.
Manage Summary Dashboards on page 3930
The Summary tab provides you with an overview of the state of the selected object, group, or application. You can
change the Summary tab with a dashboard to get information specific to your needs.
Share Dashboards with Users on page 3933
You can share a dashboard with one or more user groups. When you share a dashboard, it becomes available to all the
users in the user group that you select. The dashboard appears the same to all the users who share it. If you edit a shared
dashboard, the dashboard changes for all users. Other users can only view a shared dashboard. They cannot change it.
Share Dashboards with Users
You can share a dashboard with one or more user groups. When you share a dashboard, it becomes available to all the
users in the user group that you select. The dashboard appears the same to all the users who share it. If you edit a shared
dashboard, the dashboard changes for all users. Other users can only view a shared dashboard. They cannot change it.
Where You Share a Dashboard From
To share a dashboard, from the left menu, click Infrastructure Operations > Dashboards & Reports. Click
Dashboards> Manage. Click the horizontal ellipsis next to the Add option and click Manage Dashboard Sharing.
Table 1146: Dashboard Sharing Options
Option Description
All Dashboards Link to view all the available dashboards that you can share. The
dashboards are displayed on the right side in the dashboards list.
User Groups Lists the available user groups that you can share a dashboard
with. The list includes the Everyone group.
Dashboard List List of shared dashboards with the selected user group or all
the available dashboards that you can share, if no user group is
selected.
Manage Dashboard Sharing
To share a dashboard, navigate to the dashboard in the list of dashboards and drag it to the group to share it with, on the
left.
To stop sharing a dashboard with a group, click that group on the left panel, navigate to the dashboard in the right panel,
and click Stop Sharing above the list.
Table 1147: Datagrid Options
Column Name Description
Name Displays the name of the dashboard.
Folder Displays the folder where the dashboard is located.
VMware by Broadcom  3933

---
## page 3934

 VMware Cloud Foundation 9.0
Column Name Description
Description Displays the description of the dashboard.
Activated Displays whether the dashboard is activated for viewing.
Shared Displays if the dashboard is shared with user groups.
Editable Click the check box to share dashboard edit privileges with the
specific group.
Owner Displays the owner of the dashboard.
Last Modified Displays the date the dashboard was last modified.
Modified By Displays who modified the dashboard.
Related Links
Manage Dashboards on page 3928
You can select dashboards individually or as a group and perform several actions.
Auto-Rotate Dashboards on page 3931
You can change the order of the dashboard tabs on your home page. You can configure VCF Operations to switch from
one dashboard to another. This feature is useful if you have several dashboards that show different aspects of your
enterprise's performance and you want to look at each dashboard in turn.
Manage Summary Dashboards on page 3930
The Summary tab provides you with an overview of the state of the selected object, group, or application. You can
change the Summary tab with a dashboard to get information specific to your needs.
Manage Dashboard Folders on page 3932
You can create dashboard folders to group the dashboards in a way that is meaningful to you.
Dashboards Actions and Options
You can change the order of the dashboard tabs, configure VCF Operations to switch from one dashboard to another,
create dashboard folders to group the dashboards in a way that is meaningful to you, share a dashboard or dashboard
template with one or more user groups, and transfer selected dashboards to a new owner.
Options for Sharing Dashboards
You can share predefined or custom dashboards using URLs, emails, and by copying the code to embed the dashboard
into confluence or other internal official web pages. You can also assign and unassign a dashboard to specific user groups
and export the dashboard configuration details.
When you use a non-authenticated shared URL, as a user you can open the dashboard in a new browser session. If
you have already logged into VCF Operations in another session, you are redirected to this dashboard and the user
authentication permissions apply. To ensure that the non-authenticated URL opens the intended dashboard, as a user you
must log out from all existing user sessions.
The dashboard shared with the URL opens in a page where you can access all the widgets within the dashboard and
you can interact with the given widgets at the same time. A non-authenticated dashboard however, does not allow you to
browse to other areas of VCF Operations.
Dashboard sharing can only be applied to Groups with a VCF Operations Standard Edition license.
Where You Can Access the Options to Share Dashboards
From the left menu, click Infrastructure Operations > Dashboards & Reports. Click Dashboards in the panel, and then
click on an existing dashboard and then click the Share Dashboard icon in the top-right corner.
VMware by Broadcom  3934

---
## page 3935

 VMware Cloud Foundation 9.0
Table 1148: Options in the Share Dashboard Dialog Box
Option Description
URL Allows you to copy the tiny URL for the selected dashboard.
• Set the expiry period for the link to 1 day, 1 week, 1 month, 3 Months, or
Never Expire.
• Click Copy Link to copy the link to a new window from where you can view
the dashboard.
Note:
• As a user, if you open a shared link and you are logged into VCF Operations,
you are navigated to your default dashboard, instead of viewing the shared
one.
• As a user, if you log in to the same IP that was shared with you previously,
you cannot access the page with the same browser.
• As a user, ensure that you have the following permission: Dashboards >
Dashboard Management > Share (Public).
You can stop sharing a dashboard you had previously shared. To stop sharing a
dashboard, click the Unshare Link option and enter the URL of the dashboard
that you want to stop sharing and click Unshare.
Authentication is not required to view the shared dashboard.
Email Allows you to send an email with the URL details of the dashboard, to a specific
person.
• Set the expiry period for the link to 1 day, 1 week, 1 month, 3 months, or
Never Expire.
• Configure an SMTP instance. See Add a Standard Email Plug-In for VCF
Operations Outbound Alerts.
• Enter an email address and click the Send Email button to send an email
with the URL details of the dashboard.
Authentication is not required to view the shared dashboard.
Embed Provides an embedded code for the dashboard. You can use this code to embed
the dashboard in relevant confluence pages that your company executives
routinely use and analyze.
• Set the expiry period for the link to 1 day, 1 week, 1 month, 3 Months, or
Never Expire.
Note:
• If you embed a dashboard in the Text widget, the widget does not display
any data.
• When you open an HTML/confluence page with an embedded dashboard
from the same browser that you have logged into VCF Operations, the
dashboard does not load.
Authentication is not required to view the shared dashboard.
Groups Allows you to assign and unassign a dashboard to specific user groups.
• Select the group to which you want to grant dashboard access from the
drop-down menu.
• To share dashboard edit privileges with the group, select the Allow Editing
check box if a dashboard is shared with a group.
• Click Include. You can include more than one group.
• From the label, select the cross mark to unassign the dashboard.
Log in to VCF Operations to view the shared dashboard.
VMware by Broadcom  3935

---
## page 3936

 VMware Cloud Foundation 9.0
Option Description
Export Allows you to export the dashboard configuration details.
Log in to VCF Operations to export/import a dashboard.
Manage Widgets in Dashboards
You can replicate widgets multiple times in a dashboard by using the copy and paste functionality.
Navigate to the dashboard from which you want to copy widgets. Select Actions > Edit Dashboard. Select one or
more widgets that you want to copy by clicking the title of the widget and then select Actions > Copy Widget(s). Click
Actions > Paste Widget(s) to paste one or more widgets in the same dashboard.
To paste one or more widgets into another dashboard, exit the edit screen of the dashboard by selecting Cancel. Navigate
to the dashboard to which you want to paste one or more widgets and select Actions > Edit Dashboard and then
Actions > Paste Widget(s).
Widgets in VCF Operations
Widgets are the panes on your dashboards. You add widgets to a dashboard to create a dashboard. Widgets display
information about attributes, resources, applications, or the overall processes in your environment.
You can configure widgets to reflect your specific needs. The available configuration options vary depending on the widget
type. You must configure some of the widgets before they display any data. Many widgets can provide or accept data from
one or more widgets. You can use this feature to set the data from one widget as filter and display related information on a
single dashboard.
Widget Interactions
Widget interactions are the configured relationships between widgets in a dashboard where one widget provides
information to a receiving widget. When you are using a widget in the dashboard, you select data on one widget to limit
the data that appears in another widget, allowing you to focus on a smaller subset data.
How Interactions Work
If you configured interactions between widget at the dashboard level, you can then select one or more objects in the
providing widget to filter the data that appears in the receiving widget, allowing you to focus on data related to an object.
To use the interaction option between the widgets in a dashboard, you configure interactions at the dashboard level. If you
do not configure any interactions, the data that appears in the widgets is based on how the widget is configured.
When you configure widget interaction, you specify the providing widget for the receiving widget. For some widgets, you
can define two providing widgets, each of which can be used to filter data in the receiving widget.
For example, if you configured the Object List widget to be a provider widget for the Top-N widget, you can select one or
more objects in the Object List widget and the Top-N displays data only for the selected objects.
For some widgets, you can define more than one providing widget. For example, you can configure the Metric Chart
widget to receive data from a metrics provider widget and an objects providing widget. In such case, the Metric Chart
widget shows data for any object that you select in the two provider widgets.
Related Links
Widget Definitions List on page 3944
A widget is a pane on a dashboard that contains information about configured attributes, resources, applications, or the
overall processes in your environment. Widgets can provide a holistic, end-to-end view of the health of all the objects and
VMware by Broadcom  3936

---
## page 3937

 VMware Cloud Foundation 9.0
applications in your enterprise. If your user account has the necessary access rights, you can add and remove widgets
from your dashboards.
Dashboard Navigation Details on page 3927
You can apply sections or context from one dashboard to another. You can connect widgets and views to widgets and
views in the same dashboard or to other dashboards to investigate problems or better analyze the provided information.
Dashboard Name on page 3924
The name and visualization of the dashboard as it appears on the VCF Operations Home page.
Widget and View Interactions Details on page 3926
You can connect widgets and views so that the information they show depends on each other.
Widget or View List Details on page 3925
VCF Operations provides a list of widgets or views that you can add to your dashboard to monitor specific metrics and
properties of objects in your environment.
Configuration Files
You can create configuration files to upload SVG content and define topological hierarchies in dashboards through
supported widgets. You can also create configuration files that displays adapter kind, resource kind, and the associated
metrics that can be displayed in dashboards using supported widgets.
Configuration Files for Widget Metric Configuration
You can create an XML file that displays the adapter type, resource kind, and the associated metrics that can be displayed
in a widget and dashboard.
How Configuration Files Work
From the Configuration Files page, you can create a XML configuration file with the adapter type, object type, and metric
details to be displayed in a dashboard. The final output is an XML file. The supported widgets are Metric Chart, Property
List, Rolling View Chart, Scoreboard, Sparkline Chart, and Topology Graph. To use the metric configuration, you must set
the widget Self Provider to Off and create a widget interaction with a provider widget.
Where You Find Widget Metric Configuration File
To manage the configuration files, from the left menu, click Operations > Configurations. From the right panel, under
Configuration Files, click the Widget Metric Configuration tile. To add a configuration file, click the Add button. You see
the Create Configuration File page.
Table 1149: New Configuration File Page Options
Option Description
Name Enter a name for the configuration file.
Description Enter a description for the configuration file.
Containing Folder Select the folder under which you want to store the new
configuration file. If you have not created a folder, you can select
the User Defined folder if it appears. The System Defined folder
will not appear for selection.
Text box You can define the adapter type, object type, and metrics.
VMware by Broadcom  3937

---
## page 3938

 VMware Cloud Foundation 9.0
Option Description
From the Adapter Kind drop down above the text box, select the
adapter type. From the Resource Kind drop down above the text
box, select the object type. From the Metric drop down above the
text box, select a metric.
Use the orange Format XML button to format the XML content.
Click Save. You see the configuration file under the selected
folder. You can preview the XML that was created.
Table 1150: Widget Metric Configuration Toolbar and Data Grid Options
Option Description
Filter Click the filter icon to filter the configuration files using the
following criteria: Name, Description, Last Modified, and Modified
By.
Options from the horizontal ellipsis
Edit Select a configuration file to edit the contents of the configuration
file.
Delete Select one or more configuration files if you want to delete them.
You cannot delete configuration files under the System Defined
folder.
Clone Select a configuration file to clone. You can edit the configuration
file options in the New Configuration File page and click Save
Move Select one or more configuration files if you want to move them
to another folder. You can also move configuration files using the
drag and drop option. You cannot move a configuration file to or
from the System Defined folder.
Export Select one or more configuration files if you want to download
them.
Import Select this option if you want to import configuration files. To
import:
• Click the Import option from the horizontal ellipsis.
• Click Browse and select the file to import.
• Select if you want to Overwrite or Skip the file in case of a
conflict.
• Click Import to import the configuration file, and click Done.
Create New Folder Enter a name for the folder and click OK. You can create a new
folder for meaningful grouping.
Rename Folder Select a folder created by a user and rename the folder. You
cannot rename the System Defined and User Defined folders.
Data Grid Options
Name Lists the configuration files that have been created. The System
Defined folder contains configuration files that are predefined. The
User Defined  folder contains orphan configuration files that were
created by users but not assigned to a folder.
In Use Indicates whether the configuration file is in use in a dashboard
and supported widget.
Yes: Indicates that the configuration file is used in a dashboard.
Hover and click on the green tick mark to view the name of the
dashboard and the widget that uses this configuration file.
VMware by Broadcom  3938

---
## page 3939

 VMware Cloud Foundation 9.0
Option Description
No: Indicates that the configuration file is not used in a dashboard.
Description Displays the description entered while creating/editing the
configuration file.
Last Modified Displays when the configuration file was last updated.
Modified By Displays who last modified the configuration file. For example,
admin or maintenanceAdmin.
Configuration Files for Text Widget Content
You can upload an SVG in Text widgets that are utilized in different dashboards.
How Configuration Files Work
From the Configuration Files page, you can upload an SVG file to be displayed in a Text widget.
Where You Find Text Widget Configuration File
To manage the configuration files, from the left menu, click Operations > Configurations. From the right panel, under
Configuration Files, click the Text Widget Content tile. To add a configuration file, click the Add button. You see the
Create Configuration File page.
Table 1151: New Configuration File Page Options
Option Description
Name Enter a name for the configuration file.
Description Enter a description for the configuration file.
Containing Folder Select the folder under which you want to store the new
configuration file. If you have not created a folder, you can select
the User Defined folder if it appears. The System Defined folder
will not appear for selection.
Text box From your system, using an XML editor, open the SVG file to be
uploaded. Copy the text from the SVG file into the text box. Use
the orange Format XML button to format the XML content. Click
Save. You see the configuration file under the selected folder. You
can preview the SVG that was uploaded.
Note:  Ensure that the text in the text box starts with <svg .
Table 1152: Text Widget Toolbar and Data Grid Options
Option Description
Filter Click the filter icon to filter the configuration files using the
following criteria: Name, Description, Last Modified, and Modified
By.
Options from the horizontal ellipsis
Edit Select a configuration file to edit the contents of the configuration
file.
VMware by Broadcom  3939

---
## page 3940

 VMware Cloud Foundation 9.0
Option Description
Delete Select one or more configuration files if you want to delete them.
You cannot delete configuration files under the System Defined
folder.
Clone Select a configuration file to clone. You can edit the configuration
file options in the New Configuration File page and click Save.
Move Select one or more configuration files if you want to move them
to another folder. You can also move configuration files using the
drag and drop option. You cannot move a configuration file to or
from the System Defined folder.
Export Select one or more configuration files if you want to download
them.
Import Select this option if you want to import configuration files. To
import:
• Click the Import option from the horizontal ellipsis.
• Click Browse and select the file to import.
• Select if you want to Overwrite or Skip the file in case of a
conflict.
• Click Import to import the configuration file, and click Done.
Create New Folder Enter a name for the folder and click OK. You can create a new
folder for meaningful grouping.
Rename Folder Select a folder created by a user and rename the folder. You
cannot rename the System Defined and User Defined folders.
Data Grid Options
Name Lists the configuration files that have been created. The System
Defined folder contains configuration files that are predefined. The
User Defined folder contains orphan configuration files that were
created by users but not assigned to a folder.
In Use Indicates whether the configuration file is in use in a Text widget
and dashboard.
Yes: Indicates that the configuration file is used in a Text widget.
Hover and click on the green tick mark to view the name of the
dashboard and the Text widget that uses this configuration file.
No: Indicates that the configuration file is not used in a dashboard.
Description Displays the description entered while creating/editing the
configuration file.
Last Modified Displays when the configuration file was last updated.
Modified By Displays who last modified the configuration file. For example,
admin or maintenanceAdmin.
Management Packs Configuration
You can create an XML file for specific adapter kinds with additional threshold details such as configuration limits, name,
type, and value. The configuration file can be used in a widget and dashboard.
How Configuration Files Work
From the Management Packs Configuration page, you can create a XML file with adapter specific details with additional
thresholds to be displayed in dashboards and widgets. The final output is an XML file. The final output is an XML file. The
supported widgets are Metric Chart, Property List, Rolling View Chart, Scoreboard, Sparkline Chart, and Topology Graph.
VMware by Broadcom  3940

---
## page 3941

 VMware Cloud Foundation 9.0
Where You Find Resource Kind Metric Configuration File
To manage the configuration files, from the left menu, click Operations > Configurations. From the right panel, under
Configuration Files, click the Management Packs Configuration tile. To add a configuration file, click the Add button.
You see the Create Configuration File page.
Table 1153: New Configuration File Page Options
Option Description
Name Enter a name for the configuration file.
Description Enter a description for the configuration file.
Containing Folder Select the folder under which you want to store the new
configuration file. If you have not created a folder, you can select
the User Defined folder if it appears. The System Defined folder
will not appear for selection.
Text box You can define the adapter kind and thresholds such as
configuration limits, name, type, and value.
Select the tags above the text box to add to the configuration file.
Use the orange Format XML button to format the XML content.
Click Save. You see the configuration file under the selected
folder. You can preview the XML that was created.
Table 1154: Solutions Configuration Toolbar and Data Grid Options
Option Description
Filter Click the filter icon to filter the configuration files using the
following criteria: Name, Description, Last Modified, and Modified
By.
Options from the horizontal ellipsis
Edit Select a configuration file to edit the contents of the configuration
file.
Delete Select one or more configuration files if you want to delete them.
You cannot delete configuration files under the System Defined
folder.
Clone Select a configuration file to clone. You can edit the configuration
file options in the New Configuration File page and click Save
Move Select one or more configuration files if you want to move them
to another folder. You can also move configuration files using the
drag and drop option. You cannot move a configuration file to or
from the System Defined folder.
Export Select one or more configuration files if you want to download
them.
Import Select this option if you want to import configuration files. To
import:
• Click the Import option from the horizontal ellipsis.
• Click Browse and select the file to import.
• Select if you want to Overwrite or Skip the file in case of a
conflict.
• Click Import to import the configuration file, and click Done.
VMware by Broadcom  3941

---
## page 3942

 VMware Cloud Foundation 9.0
Option Description
Create New Folder Enter a name for the folder and click OK. You can create a new
folder for meaningful grouping.
Rename Folder Select a folder created by a user and rename the folder. You
cannot rename the System Defined and User Defined folders.
Data Grid Options
Name Lists the configuration files that have been created. The System
Defined folder contains configuration files that are predefined. The
User Defined folder contains orphan configuration files that were
created by users but not assigned to a folder.
Description Displays the description entered while creating/editing the
configuration file.
Last Modified Displays when the configuration file was last updated.
Modified By Displays who last modified the configuration file. For example,
admin or maintenanceAdmin.
Configuration Files for the Topology Widget
You can create an XML file with topology hierarchies to be displayed in a Topology widget.
How Configuration Files Work
From the Configuration Files page, you can create a XML file with topology hierarchies to be displayed in a Topology
widget. The final output is an XML file.
Where You Find Resource Kind Metric Configuration File
To manage the configuration files, from the left menu, click Operations > Configurations. From the right panel, under
Configuration Files, click the Topology Widget Configuration tile. To add a configuration file, click the Add button. You
see the Create Configuration File page.
Table 1155: New Configuration File Page Options
Option Description
Name Enter a name for the configuration file.
Description Enter a description for the configuration file.
Containing Folder Select the folder under which you want to store the new
configuration file. If you have not created a folder, you can select
the User Defined folder if it appears. The System Defined folder
will not appear for selection.
Text box You can define the topology hierarchies.
Select the tags above the text box to add to the configuration file.
Use the orange Format XML button to format the XML content.
Click Save. You see the configuration file under the selected
folder. You can preview the XML that was created.
VMware by Broadcom  3942

---
## page 3943

 VMware Cloud Foundation 9.0
Table 1156: Topology Widget Configuration Toolbar and Data Grid Options
Option Description
Filter Click the filter icon to filter the configuration files using the
following criteria: Name, Description, Last Modified, and Modified
By.
Options from the horizontal ellipsis
Edit Select a configuration file to edit the contents of the configuration
file.
Delete Select one or more configuration files if you want to delete them.
You cannot delete configuration files under the System Defined
folder.
Clone Select a configuration file to clone. You can edit the configuration
file options in the New Configuration File page and click Save
Move Select one or more configuration files if you want to move them
to another folder. You can also move configuration files using the
drag and drop option. You cannot move a configuration file to or
from the System Defined folder.
Export Select one or more configuration files if you want to download
them
Import Select this option if you want to import configuration files. To
import:
• Click the Import option from the horizontal ellipsis.
• Click Browse and select the file to import.
• Select if you want to Overwrite or Skip the file in case of a
conflict.
• Click Import to import the configuration file, and click Done.
Create New Folder Enter a name for the folder and click OK. You can create a new
folder for meaningful grouping.
Rename Folder Select a folder created by a user and rename the folder. You
cannot rename the System Defined and User Defined folders.
Data Grid Options
Name Lists the configuration files that have been created. The System
Defined folder contains configuration files that are predefined. The
User Defined folder contains orphan configuration files that were
created by users but not assigned to a folder.
In Use Indicates whether the configuration file is in use in a dashboard
and topology widget.
Yes: Indicates that the configuration file is used in a dashboard.
Hover and click on the green tick mark to view the name of the
dashboard and the widget that uses this configuration file.
No: Indicates that the configuration file is not used in a dashboard.
Description Displays the description entered while creating/editing the
configuration file.
Last Modified Displays when the configuration file was last updated.
Modified By Displays who last modified the configuration file. For example,
admin or maintenanceAdmin.
VMware by Broadcom  3943

---
## page 3944

 VMware Cloud Foundation 9.0
Widget Definitions List
A widget is a pane on a dashboard that contains information about configured attributes, resources, applications, or the
overall processes in your environment. Widgets can provide a holistic, end-to-end view of the health of all the objects and
applications in your enterprise. If your user account has the necessary access rights, you can add and remove widgets
from your dashboards.
Table 1157: Summary of Widgets
Widget Name Description
Alert List Shows a list of alerts for the objects that the widget is configured to monitor. If no objects are
configure, the list displays all alerts in your environment.
Alert Volume Shows a trend report for the last seven days of alerts generated for the objects it is configured to
monitor.
Anomalies Shows a chart of the anomalies count for the past 6 hours.
Anomaly Breakdown Shows the likely root causes for symptoms for a selected resource.
Capacity Remaining Shows a percentage indicating the remaining computing resources as a percent of the total
consumer capacity. It also displays the most constrained resource.
Container Details Shows the health and alert counts for each tier in a single selected container.
Container Overview Shows the overall health and the health of each tier for one or more containers.
Current Policy Shows the highest priority policy applied to a custom group.
Data Collection Results Shows a list of all supported actions specific for a selected object.
DRS Cluster Settings Shows the workload of the available clusters and the associated hosts.
Efficiency Shows the status of the efficiency-related alerts for the objects that it is configured to monitor.
Efficiency is based on generated efficiency alerts in your environment.
Environment Lists the number of resources by object or groups them by object type.
Environment Overview Shows the performance status of objects in your virtual environment and their relationships. You can
click an object to highlight its related objects and double-click an object to view its Resource Detail
page.
Environment Status Shows statistics for the overall monitored environment.
Faults Shows a list of availability and configuration issues for a selected resource.
Forensics Shows how often a metric had a particular value, as a percentage of all values, within a given time
period. It can also compare percentages for two time periods.
Geo Shows where your objects are located on a world map, if your configuration assigns values to the
Geo Location object tag.
Health Shows the status of the health-related alerts for the objects that it is configured to monitor. Health is
based on generated health alerts in your environment.
Health Chart Shows health information for selected resources, or all resources that have a selected tag.
Heat Map Shows a heat map with the performance information for a selected resource.
Mashup Chart Brings together disparate pieces of information for a resource. It shows a health chart and metric
graphs for key performance indicators (KPIs). This widget is typically used for a container.
Metric Chart Shows a chart with the workload of the object over time based on the selected metrics.
Metric Picker Shows a list of available metrics for a selected resource. It works with any widget that can provide
resource ID.
Object List Shows a list of all defined resources.
Object Relationship Shows the hierarchy tree for the selected object.
VMware by Broadcom  3944

---
## page 3945

 VMware Cloud Foundation 9.0
Widget Name Description
Object Relationship (Advanced) Shows the hierarchy tree for the selected objects. It provides advanced configuration options.
Property List Shows the properties and their values of an object that you select.
Recommended Actions Displays recommendations to solve problems in your vCenter instances. With recommendations, you
can run actions on your data centers, clusters, hosts, and virtual machines.
Risk Shows the status of the risk-related alerts for the objects that it is configured to monitor. Risk is
based on generated risk alerts in your environment.
Rolling View Chart Cycles through selected metrics at an interval that you define and shows one metric graph at a time.
Miniature graphs, which you can expand, appear for all selected metrics at the bottom of the widget.
Scoreboard Shows values for selected metrics, which are typically KPIs, with color coding for defined value
ranges.
Scoreboard Health Shows color-coded health, risk, and efficiency scores for selected resources.
Sparkline Chart Shows graphs that contain metrics for an object . If all the metrics in the Sparkline Chart widget are
for an object that another widget provides, the object name appears at the top right of the widget.
Tag Picker Lists all defined resource tags.
Text Display Reads text from a Web page or text file and shows the text in the user interface.
Time Remaining Shows a chart of the Time Remaining values for a specific resource over the past 7 days.
Top Alerts Lists the alerts most likely to negatively affect your environment based on the configured alert type
and objects.
Top-N Shows the top or bottom N number metrics or resources in various categories, such as the five
applications that have the best or worst health.
Topology Graph Shows multiple levels of resources between nodes.
View Shows a defined view depending on the configured resource.
Weather Map Uses changing colors to show the behavior of a selected metric over time for multiple resources.
Workload Shows workload information for a selected resource.
Workload Pattern Shows a historical view of the hourly workload pattern of an object.
For more information about the widgets, see the VCF Operations help.
Related Links
Widget Interactions on page 3936
Widget interactions are the configured relationships between widgets in a dashboard where one widget provides
information to a receiving widget. When you are using a widget in the dashboard, you select data on one widget to limit
the data that appears in another widget, allowing you to focus on a smaller subset data.
Dashboard Navigation Details on page 3927
You can apply sections or context from one dashboard to another. You can connect widgets and views to widgets and
views in the same dashboard or to other dashboards to investigate problems or better analyze the provided information.
Dashboard Name on page 3924
The name and visualization of the dashboard as it appears on the VCF Operations Home page.
Widget and View Interactions Details on page 3926
You can connect widgets and views so that the information they show depends on each other.
Widget or View List Details on page 3925
VCF Operations provides a list of widgets or views that you can add to your dashboard to monitor specific metrics and
properties of objects in your environment.
VMware by Broadcom  3945

---
## page 3946

 VMware Cloud Foundation 9.0
Alert List Widget
The Alert List widget is a list of alerts for the objects it is configured to monitor. You can create one or more alert lists in
VCF Operations for objects that you add to your custom dashboards. The widget provides you with a customized list of
alerts on objects in your environment.
How the Alert List Widget and Configuration Options Work
You can add the Alert List widget to one or more custom dashboards and configure it to display data that is important
to different dashboard users. The data that appears in the widget is based on the configured options for each widget
instance. You edit an Alert List widget after you add it to a dashboard. The changes you make to the options create a
custom alert list to meet the needs of the dashboard users.
Where You Find the Alert List Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Alert List Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Option Description
Dashboard Navigation Actions you can run on the selected alert.
For example, you use the option to open a vCenter, data center,
virtual machine, or in the vSphere Web Client, allowing you to
directly modify an object for which an alert was generated and fix
any problems.
Reset Interaction Returns the widget to its initial configured state and undoes any
interactions selected in a providing widget.
Interactions are usually between widgets in the same dashboard,
or you can configure interactions between widgets on different
dashboards.
Perform Multi-Select Interaction If the widget is a provider for another widget on the dashboard, you
can select multiple rows and click this button. The receiving widget
then displays only the data related to the selected interaction items.
Use Ctrl+click for Windows, or Cmd+click for Mac OS X, to select
multiple individual objects or Shift+click to select a range of objects,
and click the icon to activate the interaction.
Display Filtering Criteria Displays the object information on which this widget is based.
Select Date Range Limits the alerts that appear in the list to the selected date range.
Cancel Alert Cancels the selected alerts. If you configure the alert list to display
only active alerts, the canceled alert is removed from the list.
VMware by Broadcom  3946

---
## page 3947

 VMware Cloud Foundation 9.0
Option Description
You cancel alerts when you do not need to address them.
Canceling the alert does not cancel the underlying condition that
generated the alert. Canceling alerts is effective if the alert is
generated by triggered fault and event symptoms because these
symptoms are triggered again only when subsequent faults or
events occur on the monitored objects. If the alert is generated
based on metric or property symptoms, the alert is canceled only
until the next collection and analysis cycle. If the violating values
are still present, the alert is generated again.
Suspend Suspend an alert for a specified number of minutes.
You suspend alerts when you are investigating an alert and do not
want the alert to affect the health, risk, or efficiency of the object
while you are working. If the problem persists after the elapsed
time, the alert is reactivated and it will again affect the health, risk,
or efficiency of the object.
The user who suspends the alert becomes the assigned owner.
Note:  You can cancel or retrigger the alert, if it is still active when
its suspension period has ended, by rerunning the automated
actions connected to the alert. In this case, you can suppress
cancelation and update on all instances of an alert on an object. To
activate this option, open the property file /usr/lib/vmware-
vcops/user/conf/analytics/advanced.propertie
s and add retriggerExpiredSuspendedActiveAlerts
= true to the property file, and restart the VCF Operations
analytics service or the VCF Operations cluster.
Take Ownership As the current user, you make yourself the owner of the alert.
You can only take ownership of an alert, you cannot assign
ownership.
Release Ownership Alert is released from all ownership.
Group By Group alerts by the options in the drop-down menu.
Filter Locate data in the widget.
Table 1158: Group By Options
Option Description
None Alerts are not sorted into specific groupings.
Time Group alerts by time triggered. The default.
Criticality Group alerts by criticality. Values are, from the least critical: Info/
Warning/Immediate/Critical. See also Criticality in the Alert List
Widget Data Grid table.
Definition Group alerts by definition, that is, group like alerts together.
Object Type Group alerts by the type of object that triggered the alert. For
example, group alerts on hosts together.
Alert List Widget Data Grid Options
The data grid provides information on which you can sort and search.
Expand the grouped alerts to view the data grid.
VMware by Broadcom  3947

---
## page 3948

 VMware Cloud Foundation 9.0
Option Description
Criticality Criticality is the level of importance of the alert in your
environment. The alert criticality appears in a tooltip when you
hover the mouse over the criticality icon.
The level is based on the level assigned when the alert definition
was created, or on the highest symptom criticality, if the assigned
level was Symptom Based.
Alert Description of the alert.
Triggered On Name of the object for which the alert was generated.
Created On Date and time when the alert was generated.
Status Current state of the alert.
Alert Type Alert type is assigned when you create the alert definition. It helps
you categorize and route the alert to the appropriate domain
administrator for resolution.
The possible values include:
• Application
• Virtualization/Hypervisor
• Hardware (OSI)
• Storage
• Network
Alert Sub-Type Alert subtype is assigned when you create the alert definition. It
helps you categorize and route the alert to the appropriate domain
administrator for resolution.
The possible values include:
• Availability
• Performance
• Capacity
• Compliance
• Configuration
Importance Displays the priority of the alert. The importance level of the alert
is determined using a smart ranking algorithm.
Alert List Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
VMware by Broadcom  3948

---
## page 3949

 VMware Cloud Foundation 9.0
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Objects Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the pop-
up window. The selected objects appear in a list in this section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane on
the left hand side to select one or more object tag values. A list
of objects with the selected tag values appears. If you select
more than one value for the same tag, you can choose objects
that have any of the tags applied. If you select more than one
value for different tags, you can choose only the objects that
have all the tags applied.
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of objects
in the list.
All If you select this option, the widget data is based on all the objects
in your environment. The following sections provide options to
refine the objects for the widget data.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the
objects. For example, if you select the Children check box and
a Depth of 1, the child objects are the transformed inputs for the
widget.
Output Filter
Basic Pick tags to refine the widget data. The widget data is based on the
objects that have the picked tags applied. If you pick more than one
value for the same tag, the widget includes objects that have any of
the tags applied. If you pick more than one value for different tags,
the widget includes only the objects that have all the tags applied.
If the objects have an input transformation applied, you select tag
values for the transformed objects.
VMware by Broadcom  3949

---
## page 3950

 VMware Cloud Foundation 9.0
Option Description
Advanced Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered object
types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
If the objects have an input transformation applied, you define filter
criteria for the object types of the transformed objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria set.
Alert Related A group of filters limits the alerts that appear in this alert list to those
that meet the selected criteria.
If the objects on which the alerts are based have an input
transformation applied, you define filters for the alerts based on the
transformed objects.
You can configure the following filters:
• Status. Select one or more alert states to include in the list.
• Criticality. Select one or more levels of criticality.
• Control State. Select one or more control states to include in the
list.
• Impact. Select one or more alert badges to include in the list.
• Actions.
• Alert Type. Select the subtype in the type list. This value was
assigned when you configured the alert definition.
• Alert Definition. Drag and drop the alert definitions to the left
pane from the Alert Definitions list. Click OK to filter by the
selected Alert Definitions.
The selections you make for each filter are displayed as labels for
easy visibility.
Alert Volume Widget
The Alert Volume widget is a trend report for the last seven days of alerts generated for the objects it is configured to
monitor in VCF Operations. You can create one or more alert volume widgets for objects that you add to your dashboards.
The alert volume provides you with a customized trend report on objects that helps you identify changes in alert volume,
indicating a problem in your environment.
VMware by Broadcom  3950

---
## page 3951

 VMware Cloud Foundation 9.0
How the Alert Volume Widget and Configuration Options Work
You can add the Alert Volume widget to one or more custom dashboards and configure it to display data that is important
to different dashboard users. The data that appears in the widget is based on the configured options for each widget
instance. The changes you make to the options create a custom widget to meet the needs of the dashboard users.
Where You Find the Alert Volume Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Alert Volume Widget Display Options
The Alert Volume widget displays a trend chart, symptoms by criticality, and active alerts.
Option Description
Trend chart Volume of critical, immediate, and warning symptoms for the
configured objects.
Symptoms by criticality Number of symptoms for each criticality level.
Active Alerts Number of active alerts. Alerts can have more than one triggering
symptom.
Alert Volume Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
VMware by Broadcom  3951

---
## page 3952

 VMware Cloud Foundation 9.0
Option Description
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Anomalies Widget
The Anomalies widget displays the anomalies for a resource for the past 6 hours at time intervals you set.
The Anomalies widget shows or hides time periods when the metric violates a threshold that is configured. The widget
color indicates the criticality of the violation.
Where You Find the Anomalies Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Anomalies Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
VMware by Broadcom  3952

---
## page 3953

 VMware Cloud Foundation 9.0
Option Description
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider • On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Anomaly Breakdown Widget
The Anomaly Breakdown widget shows the likely root causes for symptoms for a selected resource.
How the Anomaly Breakdown Widget and Configuration Options Work
Where You Find the Anomaly Breakdown Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Anomaly Breakdown Widget Display Options
The Anomaly Breakdown widget displays scores, volume, and a list of anomaly metrics.
Option Description
Score Anomaly value.
Volume VCF Operations full set metric count for the selected object in the
specified time range.
Anomaly Metrics List List of alarms for the selected object in the specified time range.
VMware by Broadcom  3953

---
## page 3954

 VMware Cloud Foundation 9.0
Anomaly Breakdown Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Option Description
Show Bar Details If the widget is displaying data for multiple objects, you can select a row
and click this button to view the list of alarms for the selected object.
Perform Multiple Interaction If the widget is a provider for another widget on the dashboard, you can
select multiple rows and click this button. The receiving widget then
displays only the data related to the selected interaction items.
Use Ctrl+click for Windows, or Cmd+click for Mac OS X, to select
multiple individual objects or Shift+click to select a range of objects, and
click the icon to activate the interaction.
Anomaly Breakdown Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Mode Display a single object or multiple objects.
Show Select the number of objects to display in multiple objects mode.
Input Data
VMware by Broadcom  3954

---
## page 3955

 VMware Cloud Foundation 9.0
Option Description
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Output Filter
Basic Pick tags to refine the widget data. The widget data is based on
the objects that have the picked tags applied. If you pick more
than one value for the same tag, the widget includes objects that
have any of the tags applied. If you pick more than one value for
different tags, the widget includes only the objects that have all the
tags applied.
Container Details Widget
The Container Details widget displays graphs that show a summary of child objects, metrics, and alerts of an object in the
inventory.
How the Container Details Widget and Configuration Options Work
The Container Details widget treats objects from the inventory as containers and objects. Containers are objects that
contain other objects. The widget lists the containers and shows the number of containers, objects, metrics, and alerts
of the observed object. The widget also displays the alerts of each container and an icon links to its child objects. For
example, if you select from the inventory a host that contains three objects such as, two virtual machines and one
datastore, the Container Details widget displays summary information with three containers, two objects that are the child
objects of the two virtual machines, and the number of alerts for the host and the number of metrics for the child objects of
the host. The widget also lists each of the three containers, with the number of alerts for each object. Clicking an object in
the graph takes you to the object details page. When you point to the icon next to the object, a tool tip shows the name of
the related resource and its health. For example, when you point to the icon next to a virtual machine, the tool tip shows
a related datastore and its health. Clicking the icon takes you to the object detail page of the related object, which is the
datastore following the example.
You edit a container details widget after you add it to a dashboard. You can configure the widget to take information from
another widget in the dashboard and to analyze it. When you select Off from the Self Provider option and set source and
receiver widgets in the Widget Interactions menu during editing of the dashboard, the receiver widget shows information
about an object that you select from the source widget. For example, you can configure the Container Details widget to
display information about an object that you select from the Object Relationship widget in the same dashboard.
Where You Find the Container Details Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
VMware by Broadcom  3955

---
## page 3956

 VMware Cloud Foundation 9.0
Container Details Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Mode You can change the size of the graph using the Compact or Large
buttons.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Capacity Remaining Widget
The Capacity Remaining widget displays a percentage indicating the remaining computing resources as a percent of the
total consumer capacity. It also displays the most constrained resource.
Where You Find the Capacity Remaining Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
VMware by Broadcom  3956

---
## page 3957

 VMware Cloud Foundation 9.0
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Capacity Remaining Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this widget.
If not activated, the widget is updated only when the dashboard is opened or when you click the Refresh button
on the widget in the dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget are defined in the widget or provided by
another widget.
• On. You define the objects for which data appears in the widget.
• Off. You configure other widgets to provide the objects to the widget using the dashboard widget interactions
options.
Input Data
Object Search for objects in your environment and select the object on which you are basing the widget data. You can
also click the Add Object icon and select an object from the object list. You can use the Filter text box to refine
the object list and the Tag Filter pane to select an object based on tag values.
Container Overview Widget
The Container Overview widget gives a graphical presentation of the health, risk, and efficiency of an object or list of
objects in the environment.
VMware by Broadcom  3957

---
## page 3958

 VMware Cloud Foundation 9.0
How the Container Overview Widget and Configuration Options Work
The Container Overview widget displays the current status, the status for a previous time period of the health, risk, and
the efficiency of an object or list of objects. You can configure the widget to display information for one or more objects
that you are interested in when you select the Object mode during configuration of the widget. The widget displays
information for all objects from an object type or types when you select the Object Type mode during configuration of the
widget. You can open the object detailed page of each object in the data grid when you click the object.
You edit a container overview widget after you add it to a dashboard. You can configure the widget to display information
about an object or to display information about all objects from an object type by using the Object or Object Type mode.
The configuration options change depending on your selection of mode.
Where You Find the Container Overview Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Container Overview Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
The toolbar contains icons that you can use to get more information about other widgets or dashboards.
VMware by Broadcom  3958

---
## page 3959

 VMware Cloud Foundation 9.0
Option Description
Perform Multi-Select Interaction If the widget is a provider for another widget on the dashboard, you
can select multiple rows and click this button. The receiving widget
then displays only the data related to the selected interaction items.
Use Ctrl+click for Windows, or Cmd+click for Mac OS X, to select
multiple individual objects or Shift+click to select a range of objects,
and click the icon to activate the interaction.
Filter You can filter the objects in the data grid.
Dashboard Navigation You can explore information from another dashboard.
Note:  This toolbar icon exists when you configure the widget to
interact with a widget from another dashboard. Use Dashboard
Navigation menu during dashboard configuration to configure the
widgets to interact.
When you select an object from an object data grid and click the
toolbar icon, it takes you to a related dashboard. For example, you
can configure the widget to send information to a Topology Graph
widget that is on another dashboard, for example dashboard 1.
When you select a VM from the data grid, click Perform Multi-
Select Interaction , click Dashboard Navigation and select
Navigate > dashboard 1. It takes you to dashboard 1, where you
can observe selected VM and objects related to it.
Container Overview Widget Data Grid Options
The data grid provides information on which you can sort and search.
Option Description
Name Name of the object
Health Shows information about the health parameter.
Status displays the badge of the current health status of an object.
You can check the status in a tool tip when you point to the badge.
Last 24 Hours displays the statistic of health parameter for last 24
hours.
Risk Shows information about the risk parameter.
Status displays the badge of the current risk status of an object.
You can check the status in a tool tip when you point to the badge.
Last Week displays the statistics of the health parameter for the
last week.
Efficiency Shows information about the efficiency parameter.
Status displays the badge of the current efficiency status of an
object. You can check the status in a tool tip when you point to the
badge.
Last Week displays statistic of the efficiency parameter for the last
week.
Container Overview Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
VMware by Broadcom  3959

---
## page 3960

 VMware Cloud Foundation 9.0
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Mode Use Object to select an object from the environment to observe.
Use Object Type to select the type of the objects to observe.
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Object Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the
pop-up window. The selected objects appear in a list in this
section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane
on the left hand side to select one or more object tag values.
A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose
objects that have any of the tags applied. If you select more
than one value for different tags, you can choose only the
objects that have all the tags applied.
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of
objects in the list.
Object Type Select an object type in your environment on which you want to
base the widget data.
1. Click the Add Object Type icon to search for and add an
object type.
When you search for object types, you can filter the types in
the list by selecting a type from the Adapter Type drop-down
menu or by using the Filter text box.
VMware by Broadcom  3960

---
## page 3961

 VMware Cloud Foundation 9.0
Option Description
2. Optionally, select the object type from the list and click the
Delete Object Type icon to remove the selected object type.
Current Policy Widget
The Current Policy widget displays the active operational policy that is assigned to your object or object group. VCF
Operations uses the assigned policy to analyze your objects, control the data that is collected from those objects,
generate alerts when problems occur, and display the results in the dashboards.
How the Current Policy Widget and Configuration Options Work
You add the Current Policy widget to a dashboard so that you can quickly see which operational policy is applied to an
object or object group. To add the widget to a dashboard, you must have access permissions associated with the roles
assigned to your user account.
The configuration changes that you make to the widget creates a custom instance of the widget that you use in your
dashboard to identify the current policy assigned to an object or object group. When you select an object on the
dashboard, the policy applied to the object appears in the Current Policy widget, with an embedded link to the policy
details. To display the inherited and local settings for the applied policy, click the link.
Where You Find the Current Policy Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Current Policy Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances that are based on the same
widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this widget.
VMware by Broadcom  3961

---
## page 3962

 VMware Cloud Foundation 9.0
Option Description
If not activated, the widget is updated only when the dashboard is opened or when you click the
Refresh button on the widget in the dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget are defined in the widget or
provided by another widget.
• On. You define the objects for which data appears in the widget.
• Off. You configure other widgets to provide the objects to the widget using the dashboard
widget interactions options.
For example, to view the policy applied to each object that you select in the Object List widget,
select Off for Self Provider.
Input Data
Object Search for objects in your environment and select the object on which you are basing the widget
data. You can also click the Add Object icon and select an object from the object list. You can
use the Filter text box to refine the object list and the Tag Filter pane to select an object based
on tag values.
Data Collection Results Widget
The Data Collection Result widget shows a list of all supported actions specific for a selected object. The widget retrieves
data specific to a selected object actions and uses the action framework to run data collection actions.
How the Data Collection Results Widget and Configuration Options Work
You can add the Data Collection Results widget to one or more custom dashboards and configure it to display data that
is important to different dashboard users. The data that appears in the widget is based on the configured options for each
widget instance.
The Data Collection Results widget is a receiver of a resource or metric ID. It can interact with any resource or metric
ID that provides widgets such as Object List and Metric Picker. To use the widget, you must have an environment that
contains the following items.
• A vCenter Adapter instance
• A VCF Operations for Horizon View Adapter
• A VCF Operations for Horizon View Connection Server
You edit a Data Collection Result widget after you add it to a dashboard. The changes you make to the options create a
custom widget to meet the needs of the dashboard users.
Where You Find the Data Collection Results Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
VMware by Broadcom  3962

---
## page 3963

 VMware Cloud Foundation 9.0
Data Collection Results Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Option Description
Results Shows all finished and currently running actions for the selected
object.
Choose Action Shows a list with all supported actions specific for the selected
object. The selected object is a result of widget interactions.
Data Collection Results Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget updates only when you open the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Config Specifies self provider choice and selection of a resource
instance.
Selected Object When you select an object, this text box is populated by the
object.
Start new data collection on interaction change Indicates whether to start a new data collection action when the
object selection changes in the source widget.
Objects List of objects in your environment that you can search or sort by
column so that you can locate the object on which you are basing
the data that appears in the widget.
Defaults Specifies the default data collection action selected for each object
type.
VMware by Broadcom  3963

---
## page 3964

 VMware Cloud Foundation 9.0
Option Description
Object Types List of object types in your environment that you can search or sort
by column so that you can locate the object type on which you are
basing the data that appears in the widget. You can filter the types
in the list by selecting a type from the Adapter Type drop-down
menu or by using the Filter text box.
Default Data Collection Action This panel is populated by the object type that you select in the
object types list.
You can select only one default data collection action for an object
type.
DRS Cluster Settings Widget
The DRS Cluster Settings widget displays the workload of the available clusters and the associated hosts. You can
change the Distributed Resource Scheduler (DRS) automation rules for each cluster.
How the DRS Cluster Settings Widget and Configuration Options Work
You can view CPU workload and memory workload percentages for each of the clusters. You can view CPU workload and
memory workload percentages for each host in the cluster by selecting a cluster in the data grid. The details are displayed
in the data grid below. You can set the level of DRS automation and the migration threshold by selecting a cluster and
clicking Cluster Actions > Set DRS Automation.
You edit a DRS Cluster Settings widget after you add it to a dashboard. To configure the widget, click the edit icon at the
upper-right corner of the widget window. You can add the DRS Cluster Settings widget to one or more custom dashboards
and configure it to display data that is important to different dashboard users. The data that appears in the widget is based
on the configured options for each widget instance.
The DRS Cluster Settings widget appears on the dashboard named vSphere DRS Cluster Settings, which is provided with
VCF Operations.
VMware by Broadcom  3964

---
## page 3965

 VMware Cloud Foundation 9.0
Where You Find the DRS Cluster Settings Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
DRS Cluster Settings Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Option Description
Cluster Actions Limits the list to actions that match the cluster you select.
Show The drop-down menu displays the parent vCenter instances where
the clusters reside. You can also view the data centers under
each parent vCenter instance. Select a parent vCenter to view the
workload of the available clusters in the data grid.
The default setting displays the clusters across all vCenters.
Filter Filters the data grid by name, data center, vCenter, DRS settings,
and migration threshold.
DRS Cluster Settings Widget Data Grid Options
The data grid provides information on which you can sort and search.
Option Description
Name Displays the names of the clusters in the selected parent vCenter
instance.
Datacenter Displays the data centers that belong to each cluster.
vCenter Displays the parent vCenter instance where the cluster resides.
DRS Settings Displays the level of DRS automation for the cluster.
To change the level of DRS automation for the cluster, select
Cluster Actions > Set DRS Automation from the toolbar. You
can change the automation level by selecting an option from the
drop-down menu in the Automation Level column.
Migration Threshold Recommendations for the migration level of virtual machines.
Migration thresholds are based on DRS priority levels, and are
computed based on the workload imbalance metric for the cluster.
CPU Workload % Displays the percentage of CPU in GHz available on the cluster.
Memory Workload % Displays the percentage of memory in GB available on the cluster.
DRS Cluster Settings Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
VMware by Broadcom  3965

---
## page 3966

 VMware Cloud Foundation 9.0
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Efficiency Widget
The efficiency widget is the status of the efficiency-related alerts for the objects it is configured to monitor. Efficiency alerts
in VCF Operations usually indicate that you can reclaim resources. You can create one or more efficiency widgets for
objects that you add to your custom dashboards.
How the Efficiency Widget and Configuration Options Work
You can add the efficiency widget to one or more custom dashboards and configure it to display data that is important to
the dashboard users.
The state of the badge is based on your alert definitions. Click the badge to see the Summary tab for objects or groups
configured in the widget. From the Summary tab, you can begin determining what caused the current state. If the widget
is configured for an object that has descendants, you should also check the state of descendants. Child objects might
have alerts that do not impact the parent.
If the Badge Mode configuration option is set to Off, the badge and a chart appears. The type of chart depends on the
object that the widget is configured to monitor.
• A population criticality chart displays the percentage of group members with critical, immediate, and warning efficiency
alerts generated over time, if the monitored object is a group.
• A trend line displays the efficiency status of the monitored object over time if the object does not provide its resources
to any other object, or where no other object depends on the monitored object's resources. For example, if the
monitored object is a virtual machine or a distributed switch.
• A pie chart displays the reclaimable, stress, and optimal percentages for the virtual machines that are descendants of
the monitored object for all other object types. You use the chart to identify objects in your environment from which you
can reclaim resources. For example, if the object is a host or datastore.
If the Badge Mode is set to On, only the badge appears.
Edit an efficiency widget after you add it to a dashboard. The changes you make to the options create a custom widget
that provides information about an individual object, a custom group of objects, or all the objects in your environment.
VMware by Broadcom  3966

---
## page 3967

 VMware Cloud Foundation 9.0
Where You Find the Efficiency Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Efficiency Widget Display Options
The Efficiency widget displays an efficiency badge. The widget also displays an efficiency trend when not in badge mode.
Option Description
Efficiency Badge Status of the objects configured for this instance of the widget.
Click the badge to open the Alerts tab for the object that provides data
to the widget.
Efficiency Trend Displays a chart, depending on the selected or configured object. The
charts vary, depending on whether the monitored object is a group, a
descendent object, or an object that provides resources to other objects.
The chart appears only if the Badge Mode configuration option is off. If
the Badge Mode is on, only the badge appears.
Efficiency Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
VMware by Broadcom  3967

---
## page 3968

 VMware Cloud Foundation 9.0
Option Description
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Badge Mode Determines whether the widget displays only the badge, or the
badge and a weather map or trend chart.
Select one of the following options:
• On. Only the badge appears in the widget.
• Off. The badge and a chart appear in the widget. The chart
provides additional information about the state of the object.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Environment Widget
The Environment widget displays the resources which collects data. You can create one or more lists in VCF Operations
for the resources that you add to your custom dashboards.
How the Environment Widget and Configuration Options Work
The Environment widget lists the number of resources by object or groups them by object type. You can add the
Environment widget to one or more custom dashboards and configure it to display data that is important to different
dashboard users. The data that appears in the widget is based on the configured options for each widget instance.
You edit an Environment widget after you add it to a dashboard. The changes you make to the options help create a
custom widget to meet the needs of the dashboard users.
Where You Find the Environment Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
VMware by Broadcom  3968

---
## page 3969

 VMware Cloud Foundation 9.0
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Environment Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Environment Overview Widget
The Environment Overview widget displays the health, risk, and efficiency of resources for a given object from the
managed inventory.
How the Environment Overview Widget and Configuration Options Work
You can add the Environment Overview widget to one or more custom dashboards.
The widget displays data for objects from one or several types. The data that the widget displays depends on the object
type and category that you selected when you configured the widget.
VMware by Broadcom  3969

---
## page 3970

 VMware Cloud Foundation 9.0
The objects in the widget are ordered by object type.
The parameters for the health, risk, and efficiency of an object appear in a tool tip when you point to the object.
When you double-click an object on the Environment Overview widget, you can view detailed information for the object.
To use the Environment Overview widget, you must add it to the dashboard and configure the data that appears in the
widget. You must select at least one badge and an object. Additionally, you can select an object type.
The Environment Overview widget has basic and advanced configuration options. The basic configuration options are
activated by default.
To use all features of the Environment Overview widget, you must change the default configuration of the widget. Log in
to the VCF Operations machine and set skittlesCustomMetricAllowed to true in the web.properties file. The
web.properties file is located in the /usr/lib/vmware-vcops/user/conf/web folder. The change is propagated
after you use the service vmware-vcops-web restart command to restart the UI.
You must use the Badge tab to select the badge parameters that the widget shows for each object. You must use the
Config tab to select an object or object type. To observe a concrete object from the inventory, you can use the Basic
option. To observe a group of objects or objects from different types, you must use the Advanced option.
Where You Find the Environment Overview Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Environment Overview Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
The toolbar contains icons that you can use to get more information about badges.
Option Description
Badge You can select a Health, Risk, or Efficiency badge for objects that
appear in the widget. The tool tip of a badge shows the standard
name of the badge.
Status You can filter objects based on their badge status and their state.
Sort You can sort objects by letter or by number.
Environment Overview Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Selected Object Object that is the basis for the widget data.
VMware by Broadcom  3970

---
## page 3971

 VMware Cloud Foundation 9.0
Option Description
To populate the text box, select Config > Basic and select an
object from the list.
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Badge Defines a parameter to observe. You can select or deselect
Health, Risk, and Efficiency parameters using check boxes.
Default configuration of the widget selects all badges.
Select at least one badge parameter.
Basic
List of objects in your environment that you can search or sort by
column so that you can locate the object on which you are basing
the data that appears in the widget.
Config
Advanced
You can use Object Types to select a type of the objects to
observe information about health, risk, and efficiency. Double-click
the object type to select it.
Use the Adapter Type drop-down menu to filter the objects types
based on an adapter.
You can use the Use vSphere Default button to observe the main
vSphere object types.
To remove an object type from the list, click Remove Selected
next to Use vSphere Default.
You can use the Object Type Categories menu to select a group
or groups of object types to observe.
You can use the Object tree to select an object to filter the
displayed objects. For example, to observe a datastore of a VM,
double-click Datastore from the Object Types menu to select it.
Click the datastore when it is in the list of object types, and find
the VM in the object tree and select it. To return to your previous
configuration of the widget, click Datastore from the list of object
types and click Deselect All in the object tree window.
The metrics tree and badge data grids are available configuration
options only if the default configuration of the widget is changed.
To use these configuration options, log in to the VCF Operations
machine and set skittlesCustomMetricAllowed to true
in the web.properties file. The web.properties file is
located in the /usr/lib/vmware-vcops/user/conf/we
b folder.
VMware by Broadcom  3971

---
## page 3972

 VMware Cloud Foundation 9.0
Environment Status Widget
The Environment Status widget displays the statistics for the overall monitored environment.
How the Environment Status Widget and Configuration Options Work
You customize the output of the widget by choosing a category such as Objects, Metrics, Applications, Alerts, Analytics,
and Users. You can filter the data by using the tags tree from Select which tags to filter in the configuration window.
You edit an environment status widget after you add it to a dashboard. To configure the widget, click the pencil at
the right corner of the widget window. You must select at least one type of information from OBJECTS, METRICS,
APPLICATIONS, ALERTS, ANALYTICS, USERS categories for the widget to display. By default, the widget displays
statistics information about all objects in the inventory. You can use the Select which tags to filter option to filter the
information. The widget can interact with other widgets in the dashboard, taking data from them and displaying statistics .
For example, you can have a Object List widget , which is the source of the data and an Environment Status widget,
which is the destination. If you select objects and perform a multiselection interaction from the Object List widget, the
Environment Status widget results are updated based on the selections you made in the Object List.
Where You Find the Environment Status Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Environment Status Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Data section provides options to select object types on which you are basing the widget data.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
VMware by Broadcom  3972

---
## page 3973

 VMware Cloud Foundation 9.0
Option Description
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
The widget is also updated when it is in interaction mode. For
example, when an item is selected in the provider widget, the
content of the Environment Status widgets is refreshed.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Objects Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the
pop-up window. The selected objects appear in a list in this
section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane
on the left hand side to select one or more object tag values.
A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose
objects that have any of the tags applied. If you select more
than one value for different tags, you can choose only the
objects that have all the tags applied.
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of
objects in the list.
All If you select this option, the widget data is based on all the objects
in your environment. The following sections provide options to
refine the objects for the widget data.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the
objects. For example, if you select the Children check box and
a Depth of 1, the child objects are the transformed inputs for the
widget.
Output Data
Objects The widget shows summarized information about the objects
in your environment. You can filter the information that appears
in self provider mode when you select an object from Select
which tag to filter. You can select what type of information to
include in the summary of resources. For example, if you select
Adapter Types > Container from Select which tag to filter and
click Objects and Objects Collecting , the widget displays the
number of containers and collecting containers.
VMware by Broadcom  3973

---
## page 3974

 VMware Cloud Foundation 9.0
Option Description
Metrics The widget shows summarized information about available
metrics. You can filter the information that appears in self provider
mode when you select an object from Select which tag to filter.
You can select what type of information to include in the summary
of metrics.
Applications The widget shows summarized information about available
applications. You can filter the information that appears in self
provider mode when you select an object from Select which tag
to filter. You can select what type of information to include in the
summary of applications.
Alerts The widget shows summarized information about alerts in your
environment. You can filter the information that appears in self
provider mode when you select an object from Select which tag
to filter. You can select what type of information to include in the
summary of alerts.
Analytics The widget shows summarized information about the analytics
plug-ins. You can filter the information that appears in self provider
mode when you select an object from Select which tag to filter.
You can select what type of information to include in the summary
of analytics.
Users The widget shows the number of users defined in VCF
Operations. Select Administration > Access Control > User
Accounts.
Output Filter
Basic Pick tags to refine the widget data. The widget data is based on
the objects that have the picked tags applied. If you pick more
than one value for the same tag, the widget includes objects that
have any of the tags applied. If you pick more than one value for
different tags, the widget includes only the objects that have all the
tags applied.
If the objects have an input transformation applied, you select tag
values for the transformed objects.
Advanced Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
If the objects have an input transformation applied, you define filter
criteria for the object types of the transformed objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
VMware by Broadcom  3974

---
## page 3975

 VMware Cloud Foundation 9.0
Option Description
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
Faults Widget
The Faults widget displays detailed information about faults experienced by an object
The Faults widget configuration options are used to customize each instance of the widget that you add to your
dashboards.
Where You Find the Faults Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Faults Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
VMware by Broadcom  3975

---
## page 3976

 VMware Cloud Foundation 9.0
Option Description
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Forensics Widget
The Forensics widget shows how often a metric has a particular value as a percentage of all values, within a given time
period. It can also compare percentages for two time periods.
How the Forensics Widget and Configuration Options Work
You can add the Forensics widget to one or more custom dashboards and configure it to display data that is important
to different dashboard users. The data that appears in the widget is based on the configured options for each widget
instance.
You edit the Forensics widget after you add it to a dashboard. The changes you make to the options create a custom
widget to meet the needs of the dashboard users.
Where you Find the Forensics Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Forensics Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
VMware by Broadcom  3976

---
## page 3977

 VMware Cloud Foundation 9.0
Option Description
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Percentile Indicates how much data is above or below the specific value. For
example, it indicates that 90% of the data is more than 4 when a
vertical line occurs on the value 4.
Input Data
Select metrics on which you want to base the widget data. You
can select an object and pick its metrics.
1. Click the Add New Metrics icon to add metrics for the widget
data. Select an object to view its metric tree and pick metrics
for the object. The picked metrics appear in a list in this
section.
The metric tree shows common metrics for several objects
when you click the Show common metrics icon.
While selecting objects for which you want to pick metrics, you
can use the Filter text box to search for objects. You can also
expand the Tag Filter pane on the left hand side to select one
or more object tag values. A list of objects with the selected
tag values appears. If you select more than one value for the
same tag, you can choose objects that have any of the tags
applied. If you select more than one value for different tags,
you can choose only the objects that have all the tags applied.
2. Optionally, select metrics from the list and click the Remove
Selected Metrics icon to remove the selected metrics.
Click the Select All icon to select all the metrics in the list.
Click the Clear Selection icon to clear your selection of
metrics in the list.
Geo Widget
If your configuration assigns values to the Geo Location object tag, the geo widget shows where your objects are located
on a world map. The geo widget is similar to the Geographical tab on the Inventory page.
How the Geo Widget and Configuration Options Work
You can move the map and zoom in or out by using the controls on the map. The icons at each location show the health
of each object that has the Geo Location tag value. You can add the geo widget to one or more custom dashboards and
configure it to display data that is important to different dashboard users. The data that appears in the widget is based on
the configured options for each widget instance.
You edit a Geo widget after you add it to a dashboard. The changes you make to the options help create a custom widget
to meet the needs of the dashboard users.
VMware by Broadcom  3977

---
## page 3978

 VMware Cloud Foundation 9.0
Where You Find the Geo Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Geo Widget Toolbar Options
Option Description
Zoom in Zooms in on the map.
Zoom out Zooms out on the map.
Geo Widget Configuration Options
The Configuration section provides general configuration options for the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Output Filter
VMware by Broadcom  3978

---
## page 3979

 VMware Cloud Foundation 9.0
Option Description
Basic Pick tags to refine the widget data. The widget data is based on
the objects that have the picked tags applied. If you pick more
than one value for the same tag, the widget includes objects that
have any of the tags applied. If you pick more than one value for
different tags, the widget includes only the objects that have all the
tags applied.
Advanced Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
Heatmap Widget
The Heatmap widget contains graphical indicators that display the current value of two selected attributes of objects of tag
values that you select. In most cases, you can select only from internally generated attributes that describe the general
operation of the objects, such as health or the active anomaly count. When you select a single object, you can select any
metric for that object.
How the Heatmap Widget and Configuration Options Work
You can add the Heatmap widget to one or more custom dashboards and configure it to display data that is important to
the dashboard users.
The Heatmap widget has a General mode and an Instance mode. The General mode shows a colored rectangle for each
selected resource. In the Instance mode, each rectangle represents a single instance of the selected metric for an object.
You can click a color or the size metric box in the bottom of the Heatmap widget to filter the display of cells in the widget.
You can click and drag the color filter to select a range of colors. The Heatmap widget displays cells that match the range
of colors.
When you point to a rectangle for an object, the widget shows the resource name, group-by values, the current values of
the two tracked attributes, virtual machine details, the metric name, and the value of the color. Click Show Sparkline to
view the value.
You edit a Heatmap widget after you add it to a dashboard. The changes you make to the options create a custom widget
that provides information about an individual object, a custom group of objects, or all the objects in your environment.
VMware by Broadcom  3979

---
## page 3980

 VMware Cloud Foundation 9.0
Where You Find the Heatmap Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Heatmap Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Option Description
Dashboard Navigation Actions you can run on the selected alert.
For example, you use the option to open a vCenter, data center,
virtual machine, or in the vSphere Web Client, allowing you to
directly modify an object for which an alert was generated and fix
any problems.
Group Zoom You can roll-up non-significant resources with similar
characteristics into groups to obtain only the relevant data among
the thousands of resources in the system. The roll-up method
improves performance and decreases the memory usage. The roll-
up box encompasses the average color and the sum of the sizes of
all the resources. You can view all the resources by zooming in the
roll-up box.
Show/Hide Text Show or hide the cell name on the heatmap rectangle.
Show Details If you configure the Heatmap widget as a provider to another
widget, such as the Metric Chart widget , you can double-click
a rectangle to select that object for the widget. If the widget is in
Metric mode, double-clicking a rectangle selects the resource
associated with the metric and provides that resource to the
receiving widget. Optionally, you can select a cell from the heatmap
and click the Show Details icon to see details about the cell.
Reset Interaction Returns the widget to its initial configured state and undoes any
interactions selected in a providing widget.
Reset Zoom Resets the heatmap display to fit in the available space.
Heatmap Configuration Drop-down Select from a list of predefined heatmaps.
Heatmap Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
VMware by Broadcom  3980

---
## page 3981

 VMware Cloud Foundation 9.0
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Data section provides options to select object types on which you are basing the widget data.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Objects Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the
pop-up window. The selected objects appear in a list in this
section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane
on the left hand side to select one or more object tag values.
A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose
objects that have any of the tags applied. If you select more
than one value for different tags, you can choose only the
objects that have all the tags applied.
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of
objects in the list.
All If you select this option, the widget data is based on all the objects
in your environment. The following sections provide options to
refine the objects for the widget data.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the
objects. For example, if you select the Children check box and
a Depth of 1, the child objects are the transformed inputs for the
widget.
Output Data
VMware by Broadcom  3981

---
## page 3982

 VMware Cloud Foundation 9.0
Option Description
Configurations List of saved heatmap configuration options. You can create a
configuration and save it in the list. From the options on the right,
you can also delete, clone, and reorder the configurations.
Name Name of the widget.
Group by First-level grouping of the objects in the heatmap.
Then by Second-level grouping of the objects in the heatmap.
Relational Grouping After you select the Group by and Then by objects, select the
Relational Grouping check box to reorganize the grouping of the
objects, and to relate the objects selected in the Group by text box
with the objects selected in the Then by text box.
Mode General mode The widget shows a colored
rectangle for each selected
resource. The size of the
rectangle indicates the value
of one selected attribute. The
color of the rectangle indicates
the value of another selected
attribute.
Instance mode Each rectangle represents a
single instance of the selected
metric for a resource. A
resource can have multiple
instances of the same metric.
The rectangles are all the same
size. The color of the rectangles
varies based on the instance
value. You can use instance
mode only if you select a single
resource kind.
Object Type Object that is the basis for the widget data.
Size by An attribute to set the size of the rectangle for each resource.
Resources that have higher values for the Size By attribute have
larger areas of the widget display. You can also select fixed-size
rectangles. In most cases, the attribute lists include only metrics
that VCF Operations generates. If you select a resource kind, the
list shows all the attributes that are defined for the resource kind.
Color by An attribute to set the color of the rectangle for each resource.
Solid Coloring Select this option to use solid colors instead of a color gradient. By
default, the widget assigns red color for high value, brown color for
intermediate value and green color for low value. Click the color
box to set a different color for the values. You can add up to seven
color thresholds by clicking color range.
VMware by Broadcom  3982

---
## page 3983

 VMware Cloud Foundation 9.0
Option Description
Color Shows the color range for high, intermediate and low values. You
can set each color and type minimum and maximum color values
in the Min Value and Max Value text boxes. By default, green
indicates a low value and red indicates the high end of the value
range. You can change the high and low values to any color and
set the color to use for the midpoint of the range. You can also
set the values to use for either end of the color range, or let VCF
Operations define the colors based on the range of values for the
attribute.
If you leave the text boxes blank, VCF Operations maps the
highest and lowest values for the Color By metric to the end
colors. If you set a minimum or maximum value, any metric at or
beyond that value appears in the end color.
Output Filter
Basic Pick tags to refine the widget data. The widget data is based on
the objects that have the picked tags applied. If you pick more
than one value for the same tag, the widget includes objects that
have any of the tags applied. If you pick more than one value for
different tags, the widget includes only the objects that have all the
tags applied.
If the objects have an input transformation applied, you select tag
values for the transformed objects.
Advanced Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
If the objects have an input transformation applied, you define filter
criteria for the object types of the transformed objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
Health Widget
The Health widget is the status of the health-related alerts for the objects it is configured to monitor in VCF Operations.
Health alerts usually require immediate attention. You can create one or more health widgets for different objects that you
add to your custom dashboards.
VMware by Broadcom  3983

---
## page 3984

 VMware Cloud Foundation 9.0
How the Health Widget and Configuration Options Work
You can add the Health widget to one or more custom dashboards and configure it to display data that is important to the
dashboard users. The information that it displays depends on how the widget is configured.
The state of the badge is based on your alert definitions. Click the badge to see the Summary tab for objects or groups
configured in the widget. From the Summary tab, you can begin determining what caused the current state. If the widget
is configured for an object that has descendants, you should also check the state of descendants. Child objects might
have alerts that do not impact the parent.
If the Badge Mode configuration option is set to Off, the badge and a chart appears. The type of chart depends on the
object that the widget is configured to monitor.
• A trend line displays the health status of the monitored object if the object does not provide its resources to any other
object. For example, if the monitored object is a virtual machine or a distributed switch.
• A weather map displays the health of the ancestor and descendant objects of the monitored object for all other object
types. For example, if the monitored object is a host that provides CPU and memory to a virtual machine.
If the Badge Mode is set to On, only the badge appears.
You edit a Health widget after you add it to a dashboard. The changes you make to the options create a custom widget
that provides information about an individual object, a custom group of objects, or all the objects in your environment.
Where You Find the Health Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Heath Widget Display Options
The Health widget displays a health badge. The widget also displays a health trend when not in badge mode.
Option Description
Health Badge Status of the objects configured for this instance of the widget.
Click the badge to open the Alerts tab for the object that provides data
to the widget.
If the Badge Mode option is off, a health weather map or trend chart
appears for the object. Whether the map or chart appears depends on
the object type. The health weather map displays tool tips for up to1000
objects.
Health Trend Displays a chart, depending on the selected or configured object. The
charts vary, depending on whether the monitored object is a group, a
descendent object, or an object that provides resources to other objects.
The chart appears only if the Badge Mode configuration option is off. If
the Badge Mode is on, only the badge appears.
Heath Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
VMware by Broadcom  3984

---
## page 3985

 VMware Cloud Foundation 9.0
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Badge Mode Determines whether the widget displays only the badge, or the
badge and a weather map or trend chart.
Select one of the following options:
• On. Only the badge appears in the widget.
• Off. The badge and a chart appear in the widget. The chart
provides additional information about the state of the object.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Health Chart Widget
The Health Chart widget displays Health, Risk, Efficiency, or custom metric charts for selected objects. You use the widget
to compare the status of similar objects based on the same value or name.
How the Health Chart Widget and Configuration Options Work
You can add the Health Chart widget to one or more custom dashboards and configure it to display data that is important
to the dashboard users. The information that it displays depends on how the widget is configured.
If the widget is configured to display Health, Risk, or Efficiency, the chart values are based on the generated alerts for the
selected alert type for the selected objects.
VMware by Broadcom  3985

---
## page 3986

 VMware Cloud Foundation 9.0
If the widget is configured to display custom metrics, chart values are based on the metric value for the configured time
period.
You edit the Health Chart widget after you add it to the dashboard. The changes you make to the options create a custom
widget with the selected charts.
The charts are based either on Health, Risk, or Efficiency alert status, or you can base them on a selected metric. You can
include a single object, multiple objects, or all objects of a selected type.
To view the value of the object at a particular time, point your cursor over the chart. A date range and metric value tool tip
appear.
A context drop-down menu for each chart can be accessed at the top-right corner after the last metric value.
For each chart, you can view the minimum, maximum, and last metric values. The values are displayed at the top-right
corner of each chart. Each of the values is preceded by an appropriate icon of the same color as the state of the metric
value.
If there is not enough space to view the metric values, a blue information icon is displayed. Point your cursor over the icon
to view the metric value details.
Where You Find the Health Chart Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Health Chart Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Option Description
Date Controls Use the date selector to limit the data that appears in each chart to
the time period you are examining.
Select Dashboard Time to activate the dashboard time panel. The
option chosen in the dashboard time panel is effective. The default
time is 6 hours.
Dashboard Time is the default option.
Health Chart Widget Graph Selector Options
The graph selector options determine how individual data appears in the graph.
Option Description
Close Deletes the chart.
VMware by Broadcom  3986

---
## page 3987

 VMware Cloud Foundation 9.0
Option Description
Save a snapshot Creates a PNG file of the current chart. The image is the size that appears on your screen.
You can retrieve the file in your browser's download folder.
Save a full screen snapshot Downloads the current graph image as a full-page PNG file, which you can display or save.
You can retrieve the file in your browser's download folder.
Download comma-separated data Creates a CSV file that includes the data in the current chart.
You can retrieve the file in your browser's download folder.
Units Select the units in which the widget displays data. This option is visible when you select a
custom source of data in the widget configuration.
Health Chart Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Order By Determines how the object charts appear in the widget.
You can order them based on value or name, and in ascending or
descending order.
Chart Height Controls the height of all charts. Choose from three possible
choices - Small, Medium, Large. Default is Medium.
Pagination number Number of charts that appears on a page.
If you prefer scrolling through the charts, select a higher number. If
you prefer to page through the results, select a lower number.
Auto Select First Row Determines whether to start with the first row of data.
Metric Determines the source of the data.
VMware by Broadcom  3987

---
## page 3988

 VMware Cloud Foundation 9.0
Option Description
• Health, Risk, or Efficiency. The displayed charts are based on
one of these alert badges.
• Custom. The displayed charts are based on the selected
metric and use either alert symptom state colors or the
selected custom color. You can select a unit for the custom
metric from the drop-down menu or choose to allow the widget
to automatically pick a unit.
If you apply custom colors, enter the value in each box that is
the highest or lowest value that should be that color. You can
select a unit for the metric.
Metric Unit Select a unit for the custom metric.
Show Select one or more of the following items to display in the widget:
• Select Object Name to display the name of the object in the
widget.
• Select Metric Name to display the name of the metric in the
widget.
Input Data
Objects Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the
pop-up window. The selected objects appear in a list in this
section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane
on the left hand side to select one or more object tag values.
A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose
objects that have any of the tags applied. If you select more
than one value for different tags, you can choose only the
objects that have all the tags applied.
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of
objects in the list.
All If you select this option, the widget data is based on all the objects
in your environment. The following sections provide options to
refine the objects for the widget data.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the
objects. For example, if you select the Children check box and
a Depth of 1, the child objects are the transformed inputs for the
widget.
Output Filter
Basic Pick tags to refine the widget data. The widget data is based on
the objects that have the picked tags applied. If you pick more
than one value for the same tag, the widget includes objects that
have any of the tags applied. If you pick more than one value for
different tags, the widget includes only the objects that have all the
tags applied.
VMware by Broadcom  3988

---
## page 3989

 VMware Cloud Foundation 9.0
Option Description
If the objects have an input transformation applied, you select tag
values for the transformed objects.
Advanced Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
If the objects have an input transformation applied, you define filter
criteria for the object types of the transformed objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
Log Analysis Widget
The Log Analysis widget displays the logs after you have integrated VCF Operations and VCF Operations for logs. You
can filter logs based on chart and message queries.
The following screenshot shows the log analysis widget.
Figure 173:
VCF Operations for logs widget in VCF Operations console.
VMware by Broadcom  3989

---
## page 3990

 VMware Cloud Foundation 9.0
VMware by Broadcom  3990

---
## page 3991

 VMware Cloud Foundation 9.0
You can view, filter, and search the logs that are displayed.
Where You Find the Log Analysis Widget
The widget might be included on any of the custom or predefined dashboards. From the left menu, click Infrastructure
Operations > Dashboards & Reports to see the custom or predefined dashboards. To edit a custom or predefined
dashboard, from the left menu, select the dashboard from the All folder. Locate the Log Analysis dashboard in the widget
and click the Edit Widget icon to configure the widget.
To create a new dashboard with the Log Analysis widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports and click Create. The widget panel in the dashboard page shows a list of available widgets. If
you cannot find the Log Analysis widget, click SHOW MORE. Drag the Log Analysis widget to the dashboard workspace
in the upper panel. In the title bar of the widget, click the Edit Widget icon to configure the widget.
Log Analysis Widget Configuration Options
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider • On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Query Details • Choose saved chart and message queries from the drop down
list. You can create and save queries from the Infrastructure
Operations > Analyze page.
• Search for logs using keywords.
• Select the index partition from the drop-down list.
Add Filter Click ADD FILTER to add more filters.
Aggregation Details Customize the visual representation of events by using
aggregation queries.
Visualization Details Change the view mode and chart type from the drop-down lists.
A visualization displays how the chart will look. The aggregation
details determines what types of visualization you can choose.
You can also choose to display event stream, event types or event
trends.
Predefined Queries Click the + icon to add a list of predefined queries.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
VMware by Broadcom  3991

---
## page 3992

 VMware Cloud Foundation 9.0
Note:  Do not use the log analysis form widget for reporting. The widget requires user inputs to show results. The widget
is interactive and performs cross-product queries.
Mashup Chart Widget
The Mashup Chart widget shows disparate pieces of information for a resource. It shows a health chart and metric graphs
for key performance indicators (KPIs).
How the Mashup Chart Widget and Configuration Options Work
The Mashup Chart widget contains charts that show different aspects of the behavior of a selected resource. By default,
the charts show data for the past six hours.
The Mashup Chart widget contains the following charts.
• A Health chart for the object, which can include each alert for the specified time period. Click an alert to see more
information, or double-click an alert to open the Alert Summary page.
• Metric graphs for any or all the KPIs for any objects listed as a root cause object. For an application, this chart shows
the application and any tiers that contain root causes. You can select the KPI to include by selecting Chart Controls >
KPIs on the widget toolbar. Any shared area on a graph indicates that the KPI violated its threshold during that time
period.
The metric graphs reflect up to five levels of resources, including the selected object and four child levels.
You edit a Mashup Chart widget after you add it to a dashboard. The changes you make to the options create a custom
widget to meet the needs of the dashboard users.
Where You Find the Mashup Chart Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Mashup Chart Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
The toolbar contains icons that you can use to change the view.
Option Description
Filters Filter data based on criticality, status, and alert type.
Event Filters Filter based on the type of event such as, change, notification, and
fault.
Date Controls Use the date selector to limit the data that appears in each chart to
the time period you are examining.
Select Dashboard Time to activate the dashboard time panel.
The option chosen in the dashboard time panel is effective. The
default time is 6 hours.
VMware by Broadcom  3992

---
## page 3993

 VMware Cloud Foundation 9.0
Option Description
Dashboard Time is the default option.
Dashboard Navigation You can navigate to another dashboard when the object under
consideration is also available in the dashboard to which you
navigate.
Mashup Chart Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Metric Chart Widget
You can use the Metric Chart widget to monitor the workload of your objects over time. The widget displays data based on
the metrics that you select.
How the Metric Chart Widget and Configuration Options Work
You can add the Metric Chart widget to one or more custom dashboards and configure it to display the workload for your
objects. The data that appears in the widget is based on the configured menu items for each widget instance.
VMware by Broadcom  3993

---
## page 3994

 VMware Cloud Foundation 9.0
You edit the Metric Chart widget after you add it to a dashboard. The changes you make to the menu items create a
custom widget with the selected metrics that display the workload on your objects.
To select metrics, you can select an object from the object list, then select the metrics. Or, you can select a tag from the
object tag list to limit the object list, then select an object. You can configure multiple charts for the same object or multiple
charts for different objects.
To use the metric configuration, which displays a set of metrics that you defined in an XML file, the dashboard and widget
configuration must meet the following criteria:
• The dashboard Widget Interaction menu items are configured so that another widget provides objects to the target
widget. For example, an Object List widget provides the object interaction to a chart widget.
• The widget Self Provider options are set to Off.
• The custom XML file in the Metric Configuration drop-down menu is in the /usr/lib/vmware-vcops/tools/
opscli directory and has been imported into the global storage using the import command.
Where You Find the Metric Chart Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Metric Chart Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
The toolbar contains icons that you can use to change the view of the graphs.
Option Description
Split Charts Displays each metric in a separate chart.
Stacked Chart Consolidates all charts into one chart. This chart is useful for seeing how the total or sum of
the metric values vary over time. To view the stacked chart, ensure that the split chart option
is turned off.
Dynamic Thresholds Shows or hides the calculated dynamic threshold values for a 24-hour period.
Show Entire Period Dynamic
Thresholds
Shows or hides dynamic thresholds for the entire time period of the graph.
Static Thresholds Shows or hides the threshold values that have been set for a single metric.
Anomalies Shows or hides anomalies. Time periods when the metric violates a threshold are shaded.
Anomalies are generated when a metric crosses a dynamic or static threshold, either above
or below.
Trend Line Shows or hides the line and data points that represents the metric trend. The trend line filters
out metric noise along the timeline by plotting each data point relative to the average of its
adjoining data points.
Show Data Values Activates the data point tooltips if you switched to a zoom or pan option. Show Data Point
Tips must be activated.
VMware by Broadcom  3994

---
## page 3995

 VMware Cloud Foundation 9.0
Option Description
Zoom All Charts Resizes all the charts that are open in the chart pane based on the area captured when you
use the range selector.
You can switch between this option and Zoom the View.
Zoom the View Resizes the current chart when you use the range selector.
Pan When you are in zoom mode, allows you to drag the enlarged section of the chart so that you
can view higher or lower, earlier or later values for the metric.
Zoom to Fit Resets the chart to fit in the available space.
Remove All Removes all the charts from the chart pane, allowing to you begin constructing a new set of
charts.
Refresh Charts Reloads the charts with current data.
Date Controls Opens the date selector.
Use the date selector to limit the data that appears in each chart to the time period you are
examining.
Select Dashboard Time to activate the dashboard time panel. The option chosen in the
dashboard time panel is effective. The default time is 6 hours.
Dashboard Time is the default option.
Generate Dashboard Saves the current charts as a dashboard.
Save as PDF Saves the current metric chart as a PDF file.
If you have added many metrics for different objects to a metric chart, you can quickly
download and share the PDF file with another user or VM owner. You can create ad-hoc
reports when analyzing metrics. You can also add notes to the metrics to provide context to
the user.
Metric Chart Widget Graph Selector Options
The graph selector options determine how individual data appears in the graph.
Option Description
Close Deletes the chart.
Save a snapshot Creates a PNG file of the current chart. The image is the size that appears on your screen.
You can retrieve the file in your browser's download folder.
Download comma-separated data Creates a CSV file that includes the data in the current chart.
You can retrieve the file in your browser's download folder.
Save a full screen snapshot Downloads the current graph image as a full-page PNG file, which you can display or save.
You can retrieve the file in your browser's download folder.
Units You can display the data with dots or as a percentage.
Thresholds You can choose to show/hide Critical, Immediate, and Warning thresholds in the current
chart.
Scales You can choose a scale for a stacked chart.
• Select Linear to view a chart in which the Y axis scale increases in a linear manner. For
example, the Y axis can have ranges from 0 to 100, 100 to 200, 200 to 300, and so on.
• Select Logarithmic to view a chart in which the Y axis scale increases in a logarithmic
manner. For example, the Y axis can have ranges from 10 to 20, 20 to 300, 300 to 4000,
and so on. This scale gives a better visibility of minimum and maximum values in the chart
when you have a large range of metric values.
Note:  If you select a logarithmic scale, the chart does not display data points for metric
values less than or equal to 0, which leads to gaps in the graph.
VMware by Broadcom  3995

---
## page 3996

 VMware Cloud Foundation 9.0
Option Description
• Select Combined to view overlapping graphs for the metrics. The chart uses individual
scales for each graph instead of using a relative scale, and displays a combined view of
the graphs.
• Select Combined by Unit to view a chart that groups the graphs for similar metric units
together. The chart uses a common scale for the combined graphs.
Move Down Moves the chart down one position.
Move Up Moves the chart up one position.
You can take the following actions on the Metric Chart graph.
Option Description
Y Axis Shows or hides the Y-axis scale.
Chart Shows or hides the line that connects the data points on the chart.
Data Point Tips Shows or hides the data point tooltips when you hover the mouse over a data point in the
chart.
Zoom by X Enlarges the selected area on the X axis when you use the range selector in the chart to
select a subset of the chart. You can use Zoom by X and Zoom by Y simultaneously.
Zoom by Y Enlarges the selected area on the Y axis when you use the range selector in the chart to
select a subset of the chart. You can use Zoom by X and Zoom by Y simultaneously.
Zoom by Dynamic Thresholds Resizes the Y axis of the chart so that the highest and the lowest values on the axis are the
highest and the lowest values of the dynamic threshold calculated for this metric.
Vertical resize Resizes the height of a graph in the chart.
Remove icon next to each metric
name in a stacked chart
Removes the graph for the metric from the chart.
Metric Chart Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Data section provides options to select object types on which you are basing the widget data.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this widget.
If not activated, the widget is updated only when the dashboard is opened or when you click the Refresh button
on the widget in the dashboard.
VMware by Broadcom  3996

---
## page 3997

 VMware Cloud Foundation 9.0
Option Description
Refresh Interval If you activate the Refresh Content option, specify how often to refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget are defined in the widget or provided by
another widget.
• On. You define the objects for which data appears in the widget.
• Off. You configure other widgets to provide the objects to the widget using the dashboard widget interactions
options.
Input Data
Metrics Select metrics on which you want to base the widget data. You can select an object and pick its metrics.
1. Click the Add New Metrics icon to add metrics for the widget data. Select an object to view its metric tree and
pick metrics for the object. The picked metrics appear in a list in this section.
The metric tree shows common metrics for several objects when you click the Show common metrics icon.
While selecting objects for which you want to pick metrics, you can use the Filter text box to search for
objects. You can also expand the Tag Filter pane on the left hand side to select one or more object tag
values. A list of objects with the selected tag values appears. If you select more than one value for the same
tag, you can choose objects that have any of the tags applied. If you select more than one value for different
tags, you can choose only the objects that have all the tags applied.
2. Optionally, select metrics from the list and click the Remove Selected Metrics icon to remove the selected
metrics.
Click the Select All icon to select all the metrics in the list.
Click the Clear Selection icon to clear your selection of metrics in the list.
Optionally, you can customize a metric and apply the customization to other metrics in the list.
1. Double-click a metric box in the list to customize the metric and click Update.
You can use the Box Label text box to customize the label of a metric box.
You can use the Unit text box to define a measurement unit of each metric.
You can use the Color Method option to define a coloring criteria for each metric. If this option is set to
Custom, you can enter color values in the Yellow, Orange, and Red text boxes. You can also set coloring by
symptom definition. If you do not want to use color, select None.
For example, to view the remaining memory capacity of a VM, select Virtual Machine as an object type,
expand the Memory from the metric tree and double-click Capacity Remaining(%). Define a meaningful label
name and measurement unit to help you when you observe the metrics. You can select Custom from the
Color Method drop-down menu and specify different values for each color, for example 50 for Yellow, 20 for
Orange, and 10 for Red.
2. Select a metric and click the Apply to All icon to apply the customization for the selected metric to all the
metrics in the list.
Objects Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the pop-up window. The selected objects appear in a
list in this section.
While selecting objects, you can use the Filter text box to search for objects. You can also expand the Tag
Filter pane on the left hand side to select one or more object tag values. A list of objects with the selected tag
values appears. If you select more than one value for the same tag, you can choose objects that have any
of the tags applied. If you select more than one value for different tags, you can choose only the objects that
have all the tags applied.
2. Optionally, select objects from the list and click the Remove Selected Objects icon to remove the selected
objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of objects in the list.
All If you select this option, the widget data is based on all the objects in your environment. The following sections
provide options to refine the objects for the widget data.
Input Transformation
VMware by Broadcom  3997

---
## page 3998

 VMware Cloud Foundation 9.0
Option Description
Relationship Transform the input for the widget based on the relationship of the objects. For example, if you select the Children
check box and a Depth of 1, the child objects are the transformed inputs for the widget.
Output Data
Empty drop-down
menu
Specifies a list with attributes to display.
Select metrics on which you want to base the widget data. You can select an object and pick its metrics.
1. Click the Add New Metrics icon to add metrics for the widget data. Select an object to view its metric tree and
pick metrics for the object. The picked metrics appear in a list in this section.
The metric tree shows common metrics for several objects when you click the Show common metrics icon.
While selecting objects for which you want to pick metrics, you can use the Filter text box to search for
objects. You can also expand the Tag Filter pane on the left hand side to select one or more object tag
values. A list of objects with the selected tag values appears. If you select more than one value for the same
tag, you can choose objects that have any of the tags applied. If you select more than one value for different
tags, you can choose only the objects that have all the tags applied.
2. Optionally, select metrics from the list and click the Remove Selected Metrics icon to remove the selected
metrics.
Click the Select All icon to select all the metrics in the list.
Click the Clear Selection icon to clear your selection of metrics in the list.
Optionally, you can customize a metric and apply the customization to other metrics in the list.
1. Double-click a metric box in the list to customize the metric and click Update.
You can use the Box Label text box to customize the label of a metric box.
You can use the Unit text box to define a measurement unit of each metric.
You can use the Color Method option to define a coloring criteria for each metric. If this option is set to
Custom, you can enter color values in the Yellow, Orange, and Red text boxes. You can also set coloring by
symptom definition. If you do not want to use color, select None.
For example, to view the remaining memory capacity of a VM, select Virtual Machine as an object type,
expand the Memory from the metric tree and double-click Capacity Remaining(%). Define a meaningful label
name and measurement unit to help you when you observe the metrics. You can select Custom from the
Color Method drop-down menu and specify different values for each color, for example 50 for Yellow, 20 for
Orange, and 10 for Red.
2. Select a metric and click the Apply to All icon to apply the customization for the selected metric to all the
metrics in the list.
Output Filter
Refine the widget data further based on the filter criteria for object types. The widget data is based on the objects
for the filtered object types.
If the objects have an input transformation applied, you define filter criteria for the object types of the transformed
objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on which you want to define the filter criteria. For
example, if you select Metrics for the Datacenter object type, you can define a filter criteria based on the
value of a specific metric for data centers.
3. In the drop-down menus and text boxes that appear, select or enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria set.
Metric Picker Widget
The Metric Picker widget displays a list of available metrics for a selected object.
VMware by Broadcom  3998

---
## page 3999

 VMware Cloud Foundation 9.0
How the Metric Picker Widget and Configuration Options Work
With the Metric Picker widget, you can check the list of the object's metrics. To select an object to pick its metrics, you
use another widget as a source of data, for example, Topology Graph widget. To set a source widget that is on the same
dashboard, you use the Widget Interactions menu when you edit a dashboard. To set a source widget that is on another
dashboard, use the Dashboard Navigation menu when you edit a dashboard that contains the source widget. You can
also search for objects using tags.
You edit a Metric Picker widget after you add it to a dashboard. The changes you make to the options create a custom
chart to meet the needs of the dashboard users.
Where You Find the Metric Picker Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Metric Picker Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
The toolbar contains icons that you can use to change the view of the graphs.
Option Description
Show common metrics Filter based on common metrics.
Show collecting metrics Filter based on collecting metrics.
Metrics or Properties Filter based on metrics or property metrics.
Time Range Filter based on selected time range.
Search Search for dashboards, views, and network IP addresses using
tags.
Metric Picker Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
Option Action
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
VMware by Broadcom  3999

---
## page 4000

 VMware Cloud Foundation 9.0
Option Action
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Object List Widget
The Object List widget displays a list of the objects available in the environment.
How the Object List Widget and Configuration Options Work
The Object List widget displays a data grid with objects in the inventory. The default configuration of the data grid appears
in Object List Widget Options section. You can customize it by adding or removing default columns. You can use the
Additional Column option to add metrics when you configure the widget.
You edit an Object List widget after you add it to a dashboard. Configuration of the widget helps you observe parent and
child objects. You can configure the widget to display the child objects of an object selected from another widget, for
example, another Object List or Object Relationship widget, in the same dashboard.
Click the legend at the bottom of the widget to filter the objects based on threshold. Point your cursor over any of the
boxes to view tooltips.
Where You Find the Object List Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Object List Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Option Description
Action Selects from a set of actions specific for each object type. To see
available actions, select an object from the list of objects and click
the toolbar icon to select an action. For example, when you select
a datastore object in the graph, you can select Delete Unused
Snapshots for Datastore.
Dashboard Navigation Navigates you to the object. For example, when you select a
datastore from the list of objects and click Dashboard Navigation,
you can open the datastore in vSphere Web Client.
VMware by Broadcom  4000

---
## page 4001

 VMware Cloud Foundation 9.0
Option Description
Reset Grid Sort Returns the list of resources to its original order.
Reset Interaction Returns the widget to its initial configured state and undoes any
interactions selected in a providing widget.
Interactions are usually between widgets in the same dashboard,
or you can configure interactions between widgets on different
dashboards.
Object Detail Select an object and click this icon to show the Object Detail page
for the object.
Perform Multi-Select Interaction If the widget is a provider for another widget on the dashboard, you
can select multiple rows and click this button. The receiving widget
then displays only the data related to the selected interaction items.
Use Ctrl+click for Windows, or Cmd+click for Mac OS X, to select
multiple individual objects or Shift+click to select a range of objects,
and click the icon to activate the interaction.
Display Filtering Criteria Displays the object information on which this widget is based.
Page Size
Filter Locate data in the widget.
You can search for objects or filter the list based on the values
of the metrics or properties in the additional columns of the
Configuration section.
Object List Widget Data Grid Options
The data grid provides a list of inventory objects on which you can sort and search.
Option Description
ID Unique ID for each object in the inventory, randomly generated
and produced by VCF Operations.
Name Name of the object in the inventory.
Description Displays the short description of the object given during creation of
the object
Adapter Type Shows the adapter type for each object.
Object Type Displays the type of the object in the inventory.
Policy Displays policies that are applied to the object. To see policy
details and create policy configurations, in the menu click Adminis
tration, and then in the left pane click Policies.
Creation Time Displays the date, time, and time zone of the creation of an object
that was created in the inventory.
Identifier 1 Can contain the custom name of the object in the inventory or
default unique identifier, depending on the type of inventory
object. For example, My_VM_1 for a VM in the inventory, or 64-bit
hexadecimal value for VCF Operations Node.
Identifier 2 Can contain the abbreviation of an object type and the unique
decimal number or parent instance, depending on the type of the
object. For example, vm-457 for a VM and an IP address for VCF
Operations Node.
VMware by Broadcom  4001

---
## page 4002

 VMware Cloud Foundation 9.0
Option Description
Identifier 3 Can contain a unique number identifying an adapter type. For
example, 64-bit hexadecimal value for vCenter Adapter
Identifier 4 Additional unique identifiers for the object. This option varies and
depends on the adapter type that the object uses.
Identifier 5 Additional unique identifiers for the object. This option varies and
depends on the adapter type that the object uses.
Object Flag Displays a badge icon for each object. You can see the status
when you point to the badge.
Collection State Displays the collection state of an adapter instance of each object.
You can see the name of the adapter instance and its state in a
tool tip when you point to the state icon. To manage an adapter
instance to start and stop collection of data, in the menu, click Ad
ministration, and then in the left pane click Inventory.
Collection Status Displays the collection status of the adapter instance of each
object. You can see the name of the adapter instance and its
status in a tool tip when you point to the status icon. To manage
an adapter instance to start and stop collection of data, in the
menu, click Administration, and then in the left pane click
Inventory.
Relevance Displays the user interest on objects based on the number of
clicks. The relevance is determined using a system-wide ranking
algorithm that rates the object with most clicks as most relevant
object.
Internal ID Unique number that VCF Operations uses to identify the object
internally. For example, the internal ID appears in log files used for
troubleshooting.
Object List Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
The Additional Columns section provides options to select metrics that are displayed as additional columns in the
widget.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
VMware by Broadcom  4002

---
## page 4003

 VMware Cloud Foundation 9.0
Option Description
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Auto Select First Row Determines whether to start with the first row of data.
Input Data
Objects Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the
pop-up window. The selected objects appear in a list in this
section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane
on the left hand side to select one or more object tag values.
A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose
objects that have any of the tags applied. If you select more
than one value for different tags, you can choose only the
objects that have all the tags applied.
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of
objects in the list.
All If you select this option, the widget data is based on all the objects
in your environment. The following sections provide options to
refine the objects for the widget data.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the
objects. For example, if you select the Children check box and
a Depth of 1, the child objects are the transformed inputs for the
widget.
Output Filter
Note:  If there are more than ten objects under a section in the inventory tree, you can search for an object using the search option. If
there are more than thousand objects in a section, use the View More button under the last object that is displayed to view the rest of
the objects.
VMware by Broadcom  4003

---
## page 4004

 VMware Cloud Foundation 9.0
Option Description
Basic Pick tags to refine the widget data. The widget data is based on
the objects that have the picked tags applied. If you pick more
than one value for the same tag, the widget includes objects that
have any of the tags applied. If you pick more than one value for
different tags, the widget includes only the objects that have all the
tags applied.
If the objects have an input transformation applied, you select tag
values for the transformed objects.
Advanced Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
If the objects have an input transformation applied, you define filter
criteria for the object types of the transformed objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
Additional Columns
Empty drop-down menu Specifies a list with attributes to display.
Add metrics based on object types. The selected metrics are
displayed as additional columns in the widget.
1. Click the Add New Metrics icon to add metrics based on
object types. The metrics that you add appear in a list in this
section.
While selecting object types for which you want to pick
metrics, you can filter the object types by adapter type to pick
an object type. On the metrics pane, click the Select Object
icon to select an object for the object type. Pick metrics of the
selected object from the metric tree.
For example, you can select the Datacenter object type,
click the Select Object icon to display the list of data centers
in your environment, and pick metrics of the selected data
center.
2. Optionally, you can double-click a metric box in the list to
customize the label of the metric and click Update.
Object Relationship Widget
The Object Relationship widget displays the hierarchy tree for the selected object. You can create one or more hierarchy
trees in VCF Operations for the selected objects that you add to your custom dashboards.
VMware by Broadcom  4004

---
## page 4005

 VMware Cloud Foundation 9.0
How the Object Relationship Widget and Configuration Options Work
You can add the Object Relationship widget to one or more custom dashboards and configure it to display data that is
important to different dashboard users. The data that appears in the widget is based on the configured options for each
widget instance.
You edit an Object Relationship widget after you add it to a dashboard. The changes you make to the options help create
a custom widget to meet the needs of the dashboard users.
Where You Find the Object Relationship Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Object Relationship Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Option Description
Dashboard Navigation You can navigate to another dashboard when the object under
consideration is also available in the dashboard to which you
navigate. To be able to navigate to another dashboard, configure
the relevant option when you create or edit the dashboard.
Badge Displays the Health, Risk, or Efficiency alerts on the objects in the
relationship map. You can select a badge for objects that appear
in the widget. The tool tip of a badge shows the object name,
object type, and the name of the selected badge with the value of
the badge. You can only select one badge at a time.
Zoom to fit Resets the chart to fit in the available space.
Pan Click this icon and click and drag the hierarchy to show different
parts of the hierarchy.
Show values on point Shows or hides the data point tooltips when you hover the mouse
over a data point in the chart.
Zoom the view Click this icon and drag to outline a part of the hierarchy. The
display zooms to show only the outlined section.
Display Filtering Criteria Shows the filtering settings for the widget in a pop-up window.
Zoom in Zooms in on the hierarchy.
Zoom out Zooms out on the hierarchy.
Reset to Initial Object If you change the hierarchy of the initial configuration or the widget
interactions, click this icon to return to the initial resource. Clicking
this icon also resets the initial display size.
Object Detail Select an object and click this icon to show the Object Detail page
for the object.
VMware by Broadcom  4005

---
## page 4006

 VMware Cloud Foundation 9.0
Option Description
Show Alerts Select the resource in the hierarchy and click this icon to show
alerts for the resource. Alerts appear in a pop-up window. You can
double-click an alert to view its Alert Summary page.
Object Relationship Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Auto Zoom to Fixed Node Size You can configure a fixed zoom level for object icons in the widget
display.
If your widget display contains many objects and you always need
to use manual zooming, this feature is useful because you can
use it to set the zoom level only once.
Node Size You can set the fixed zoom level at which the object icons display.
Enter the size of the icon in pixels.
The widget shows object icons at the pixel size that you configure.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Output Filter
VMware by Broadcom  4006

---
## page 4007

 VMware Cloud Foundation 9.0
Option Description
Basic Pick tags to refine the widget data. The widget data is based on
the objects that have the picked tags applied. If you pick more
than one value for the same tag, the widget includes objects that
have any of the tags applied. If you pick more than one value for
different tags, the widget includes only the objects that have all the
tags applied.
Advanced Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
Object Relationship (Advanced) Widget
The Object Relationship (Advanced) widget displays a graph or tree view, or a hexagon view that depicts the parent-child
relationship of the selected object. It provides advanced configuration options. You can create a graph or tree view, or a
hexagon view in VCF Operations for the selected objects that you add to your custom dashboards.
How the Object Relationship (Advanced) Widget and Configuration Options Work
You can add the Object Relationship (Advanced) widget to one or more custom dashboards and configure it to display
data that is important to different dashboard users. The data that appears in the widget is based on the configured options
for each widget instance.
You can edit an Object Relationship (Advanced) widget after you add it to a dashboard. The changes you make to the
options help create a custom widget to meet the needs of the dashboard users.
There are two modes, the Classic view mode is a hierarchy tree view, and relationships between objects are represented
by corresponding colors. The Hexagon view mode is displayed as a ring around the hexagon grid, with each segment
representing all the criticalities in the current grid.
You can double-click any object in the graph or tree view, or hexagon view and see the specific parent-child objects for the
focus object. If you point your cursor over an object icon, you see the health, risk, and efficiency details. You can also click
the Alerts link for the number of generated alerts.
In the hexagon view, you can see the total object count. The parent-child view is listed on the left side as you click on each
object. You can view the criticality of the objects as depicted by the color by hovering your cursor over the hexagon or ring
around the hexagon.
VMware by Broadcom  4007

---
## page 4008

 VMware Cloud Foundation 9.0
Where You Find the Object Relationship (Advanced) Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Object Relationship (Advanced) Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Options Description
Dashboard Navigation You can navigate to another dashboard when the object under consideration is also available
in the dashboard to which you navigate. To navigate to another dashboard, configure the
relevant option when you create or edit the dashboard.
Back to Initial Object If you change the hierarchy of the initial configuration or the widget interactions, click this icon
to return to the initial resource. Clicking this icon also resets the initial display size.
View Tree/View graph
(Displayed when you select the Classic
view mode)
Displays a tree or graph view of the relationships.
Applications
(Displayed when you select the Classic
view mode)
Displays relationships that are of the type 'application'.
Vertical/Horizontal
(Displayed when you select the Classic
view mode)
Displays a vertical or horizontal view of the graph or tree view.
Hide Text/Show Text
(Displayed when you select the Classic
view mode)
Hides or displays the object names.
Standard View/Fit View The Standard View option fixes the view to a specific zoom level
The Fit View option adjusts the graph or tree view to fit the screen.
View Additional Links Displays additional links for the applications.
Quick Filter Enter the name of an object that you want to see in the graph or tree view or in the hexagon
view.
View Parents/View Children
(Displayed when you select the
Hexagon view mode)
Click the arrows on the left side of the grid to view the parents or children for the selected
object, in the hexagon.
Table 1159: Specific Functions from the Object Relationship (Advanced) Grid View
Function Description
Filter By Type The filtering button appears in the upper right corner of the
grid in Classic mode if any 'Relationship Type' defined by its
corresponding color, exists.
VMware by Broadcom  4008

---
## page 4009

 VMware Cloud Foundation 9.0
Function Description
You can filter by the type of relationship between parent and
child. For example, filter by Runson, Application, Location, and
so on. Each relationship type is associated with a color and the
connections in the tree view between the parent-child objects are
depicted in the specific color.
Hide Node Hover your cursor over an object and click the Hide Node icon to
hide the specific node.
Show Peers/Hide Peers Hover your cursor over the selected object in the grid view and
select ShowPeers/Hide Peers to view or hide other objects of the
same type that exist under the parent object.
Pagination/Next Page/Previous Page At the bottom of the grid view you can view the page number and
also move to the next/previous page.
Filter At the bottom of the grid view you can use the filter option to
search for objects.
Arrows Use the arrows on each object to view relationships of each
object.
Object Relationship (Advanced) Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Name Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
View Mode Select either Classic or Hexagon.
VMware by Broadcom  4009

---
## page 4010

 VMware Cloud Foundation 9.0
Option Description
If you choose Classic, you can view a graph or tree, that depicts
the parent-child relationship of the selected object after you
configure the widget.
If you select Hexagon, you see a hexagon view that depicts the
parent-child relationship of the selected object after you configure
the widget.
Inventory trees Select an existing predefined traversal spec for the initial object
relationship graph or tree view.
Relationship Types
(Displayed when you select the Classic view mode)
Select the relationship type you want displayed in the dashboard.
Each type of relationship type is associated with a color.
Note:
The relationship type filter you select here takes precedence over
the 'Filter By Type' option you see in the datagrid of the widget.
Parents Depth
(Displayed when you select the Classic view mode)
Select the depth of parent objects to be displayed.
Children Depth
(Displayed when you select the Classic view mode)
Select the depth of child objects to be displayed.
Page Size
(Displayed when you select the Classic view mode)
Select the number of objects to list per page.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Output Filter
Basic Pick tags to refine the widget data. The widget data is based on
the objects that have the picked tags applied. If you pick more
than one value for the same tag, the widget includes objects that
have any of the tags applied. If you pick more than one value for
different tags, the widget includes only the objects that have all the
tags applied.
Advanced Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
VMware by Broadcom  4010

---
## page 4011

 VMware Cloud Foundation 9.0
Option Description
5. To add another filter criteria set, click Add another criteria
set.
Property List Widget
You can use the Property List widget to view the properties of objects and their values.
How the Property List Widget and Configuration Options Work
To observe the properties of objects in the Property List widget, you can select object property metrics when you configure
the widget itself (Self Provider mode activated). Alternatively, you can select objects or object property metrics from
another widget (Self Provider mode deactivated). You can also view a default or custom set of properties by selecting a
preconfigured XML file in the Metric Configuration drop-down menu of the widget configuration window.
You edit a Property List widget after you add it to a dashboard. You can configure a widget to receive data from another
widget by selecting Off for Self Provider mode. When the widget is not in Self Provider mode, it displays a set of
predefined properties and their values of an object that you select on the source widget. For example, you can select
a host on a Topology widget and observe its properties in the Property List widget. To configure the Property List as
a receiver widget that is on the same dashboard, use the Widget Interactions menu when you edit a dashboard. To
configure a receiver widget that is on another dashboard, use the Dashboard Navigation menu when you edit a source
dashboard.
Where You Find the Property List Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Property List Widget Data Grid Options
The data grid provides information on which you can sort and search.
Option Description
Object Name Name of the object, whose properties you observe. You can sort
the properties by object name. To open the Object Details page,
click an object name.
Property Name Name of the property. You can sort the properties by property
name.
Value Value of the property. You can sort the properties by value.
Property List Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
VMware by Broadcom  4011

---
## page 4012

 VMware Cloud Foundation 9.0
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Data section provides options to select object types on which you are basing the widget data.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances that are
based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this widget.
If not activated, the widget is updated only when the dashboard is opened
or when you click the Refresh button on the widget in the dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to refresh the
data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget are
defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the widget.
• Off. You configure other widgets to provide the objects to the widget
using the dashboard widget interactions options.
Visual Theme Select a predefined visual style for each instance of the widget. The options
are: Original and Compact.
Show Metric Full Name You can choose to view the full name of the metrics. The options are: On
and Off.
Input Data
Metrics Select metrics on which you want to base the widget data. You can select
an object and pick its metrics.
1. Click the Add New Metrics icon to add metrics for the widget data.
Select an object to view its metric tree and pick metrics for the object.
The picked metrics appear in a list in this section.
The metric tree shows common metrics for several objects when you
click the Show common metrics icon.
While selecting objects for which you want to pick metrics, you can
use the Filter text box to search for objects. You can also expand the
Tag Filter pane on the left hand side to select one or more object tag
values. A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose objects
that have any of the tags applied. If you select more than one value for
different tags, you can choose only the objects that have all the tags
applied.
VMware by Broadcom  4012

---
## page 4013

 VMware Cloud Foundation 9.0
Option Description
2. Optionally, select metrics from the list and click the Remove Selected
Metrics icon to remove the selected metrics.
Click the Select All icon to select all the metrics in the list.
Click the Clear Selection icon to clear your selection of metrics in the
list.
You can define measurement units for the metrics in the list. Double-click
a metric box in the list, select a measurement unit in the Unit drop-down
menu, and click Update.
Objects Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the pop-up
window. The selected objects appear in a list in this section.
While selecting objects, you can use the Filter text box to search for
objects. You can also expand the Tag Filter pane on the left hand
side to select one or more object tag values. A list of objects with the
selected tag values appears. If you select more than one value for the
same tag, you can choose objects that have any of the tags applied. If
you select more than one value for different tags, you can choose only
the objects that have all the tags applied.
2. Optionally, select objects from the list and click the Remove Selected
Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of objects in the
list.
All If you select this option, the widget data is based on all the objects in your
environment. The following sections provide options to refine the objects for
the widget data.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the objects.
For example, if you select the Children check box and a Depth of 1, the
child objects are the transformed inputs for the widget.
Output Data
Empty drop-down menu Specifies a list with attributes to display.
1. Click the Add New Metrics icon to add metrics based on object types.
The metrics that you add appear in a list in this section.
While selecting object types for which you want to pick metrics, you
can filter the object types by adapter type to pick an object type. On the
metrics pane, click the Select Object icon to select an object for the
object type. Pick metrics of the selected object from the metric tree.
For example, you can select the Datacenter object type, click
the Select Object icon to display the list of data centers in your
environment, and pick metrics of the selected data center.
2. Optionally, you can define measurement units for the metrics and
properties in the list. Double-click a metric or properties box in the
list, select a measurement unit in the Unit drop-down menu, and click
Update.
3. You can use the Color Method option to define a coloring criteria for
each metric. If this option is set to Custom, you can enter color values
in the Yellow, Orange, and Red text boxes. You can also set coloring
by symptom definition. If you do not want to use color, select None.
Output Filter
VMware by Broadcom  4013

---
## page 4014

 VMware Cloud Foundation 9.0
Option Description
Refine the widget data further based on the filter criteria for object types.
The widget data is based on the objects for the filtered object types.
If the objects have a tag filter applied in the Basic subsection, you define
filter criteria for the object types of the objects with tag filter applied. If the
objects with tag filter applied do not belong to any of the object types in this
filter criteria, the widget skips this filter and includes all the objects with tag
filter applied.
If the objects have an input transformation applied, you define filter criteria
for the object types of the transformed objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on which you
want to define the filter criteria. For example, if you select Metrics for
the Datacenter object type, you can define a filter criteria based on the
value of a specific metric for data centers.
3. In the drop-down menus and text boxes that appear, select or enter
values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria set.
 Recommended Actions Widget
The Recommended Actions widget displays recommendations to solve problems in your vCenter instances. With
recommendations, you can run actions on your data centers, clusters, hosts, and virtual machines.
How the Recommended Actions Widget and Configuration Options Work
The Recommended Actions widget appears on the Home dashboard, and displays the health status for the objects in
your vCenter instance. At a glance, you can see how many objects are in a critical state, and how many objects need
immediate attention.
From the Recommended Actions widget, you can focus in on problems further by, for example, clicking an object where
the alerts triggered, and by clicking an individual alert.
You can edit the Recommended Actions widget on the Home dashboard, or on another dashboard where you add the
widget. With the widget configuration options, you can assign a new name to the widget, set the refresh content, and set
the refresh interval.
The Recommended Actions widget includes a selection bar, a summary pane, a toolbar for the data grid, and alert
information for your objects in a data grid.
Where You Find the Recommended Actions Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
VMware by Broadcom  4014

---
## page 4015

 VMware Cloud Foundation 9.0
Recommended Actions Widget Selection Bar and Summary Pane
Option Description
Scope Allows you to select an instance of vCenter, and a data center in that instance.
Object tabs Displays the object types with the number of objects affected in parentheses. You can display the actions for
virtual machines, host systems, clusters, vCenter instances, and datastores.
Badge Select the Health, Risk, or Efficiency badge to display alerts on your objects. Health alerts require immediate
attention. Risk alerts require attention in the immediate future. Efficiency alerts require your input to reclaim
wasted space or to improve the performance of your objects. For each badge, you can view critical, immediate,
and warning alerts.
• Health Status. With the Health badge selected, displays the number of affected objects and a summary of
their health based on the alerts that triggered on the object. Lists the objects that have the worst health, and
the number of alerts that triggered on each object.
• Risk Status. With the Risk badge selected, displays the number of affected objects and a summary of their
risk based on the alerts that triggered on the object. Lists the objects that have the highest, and the number
of alerts that triggered on each object.
• Efficiency Status. With the Efficiency badge selected, displays the number of affected objects. Lists the
objects that have the lowest efficiency based on the alerts that triggered on the object, and the number of
alerts that triggered on each object.
Search filter Narrows the scope of the objects that appear. Enter a character or a number to search and display an object.
When a filter is active, the name of the filter appears below the Search filter text box.
Recommended Actions Widget Toolbar Options
The toolbar allows you to address an alert, and to filter the alert list.
Option Description
Cancel Alert Cancels the selected alert.
You cancel alerts when you do not need to address them. Canceling the alert does not cancel the underlying
condition that generated the alert. Canceling alerts is effective if the alert is generated by triggered fault and
event symptoms because these symptoms are triggered again only when subsequent faults or events occur on
the monitored objects. If the alert is generated based on metric or property symptoms, the alert is canceled only
until the next collection and analysis cycle. If the violating values are still present, the alert is generated again.
Suspend Suspends an alert for a specified number of minutes.
You suspend alerts when you are investigating an alert and do not want the alert to affect the health, risk,
or efficiency of the object while you are working. If the problem persists after the elapsed time, the alert is
reactivated and it will again affect the health, risk, or efficiency of the object.
The user who suspends the alert becomes the assigned owner.
Quick Filter Narrows the search to one of the available filter types. For example, you can display all alerts that are related to
the Compliance Alert Subtype.
Recommended Actions Widget Data Grid Options
The data grid displays the alerts that triggered on your objects. To resolve the problems indicated by the alerts, you can
link to the alerts and the objects on which the alerts triggered.
For more information, see Accessing Alerts VCF Operations.
VMware by Broadcom  4015

---
## page 4016

 VMware Cloud Foundation 9.0
Option Description
Criticality Criticality is the level of importance of the alert in your environment. The alert criticality appears in a tooltip when
you hover the mouse over the criticality icon.
The level is based on the level assigned when the alert definition was created, or on the highest symptom
criticality, if the assigned level was Symptom Based.
Actionable When an alert has an associated action, you can run the action on the object to resolve the alert.
Suggested Fix Describes the recommendation to resolve the problem. For example, for Compliance alerts, the recommendation
instructs you to use the vSphere Hardening Guide to resolve the problem.
You can find the vSphere Hardening Guides at http://www.vmware.com/security/hardening-guides.html.
You can view other available recommendations and their associated actions, if any, to resolve the problem when
you click the drop-down menu.
Name Name of the object for which the alert was generated, and the object type, which appears in a tooltip when you
hover the mouse over the object name.
Click the object name to view the object details tabs where you can begin to investigate any additional problems
with the object.
Alert Name of the alert definition that generated the alert.
Click the alert name to view the alert details tabs where you can begin troubleshooting the alert.
Alert Type Describes the type of alert that triggered on the selected object, and helps you categorize the alerts so that you
can assign certain types of alerts to specific system administrators. For example, Application, Virtualization/
Hypervisor, Hardware, Storage, and Network.
Alert Subtype Describes additional information about the type of alert that triggered on the selected object, and helps you
categorize the alerts to a more detailed level than Alert Type, so that you can assign certain types of alerts to
specific system administrators. For example, Availability, Performance, Capacity, Compliance, and Configuration.
Time Date and time that the alert triggered.
Alert ID Unique identification for the alert. This column is hidden by default.
Recommended Actions Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
Option Description
Title Enter a custom title that identifies this widget from other instances that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this widget.
If not activated, the widget is updated only when the dashboard is opened or when you click the Refresh button
on the widget in the dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget are defined in the widget or provided by
another widget.
• On. You define the objects for which data appears in the widget.
• Off. You configure other widgets to provide the objects to the widget using the dashboard widget interactions
options.
VMware by Broadcom  4016

---
## page 4017

 VMware Cloud Foundation 9.0
Risk Widget
The risk widget is the status of the risk-related alerts for the objects it is configured to monitor. Risk alerts in VCF
Operations usually indicate that you should investigate problems in the near future. You can create one or more risk
widgets for objects that you add to your custom dashboards.
How the Risk Widget and Configuration Options Work
You can add the risk widget to one or more custom dashboards and configure it to display data that is important to the
dashboard users.
The state of the badge is based on your alert definitions. Click the badge to see the Summary tab for objects or groups
configured in the widget. From the Summary tab, you can begin determining what caused the current state. If the widget
is configured for an object that has descendants, you should also check the state of descendants. Child objects might
have alerts that do not impact the parent.
If the Badge Mode configuration option is set to Off, the badge and a chart appear. The type of chart depends on the
object type that the widget is configured to monitor.
• A population criticality chart displays the percentage of group members with critical, immediate, and warning risk alerts
generated over time, if the monitored object is a group.
• A trend line displays the risk status of the monitored object for all other object types.
If the Badge Mode is set to On, only the badge appears.
You edit a risk widget after you add it to a dashboard. The changes you make to the options create a custom widget that
provides information about an individual object, a custom group of objects, or all the objects in your environment.
Where You Find the Risk Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Risk Widget Display Options
The Risk Widget displays a risk badge. The widget also displays a risk trend chart when not in badge mode.
Option Description
Risk Badge Status of the objects configured for this instance of the widget.
Click the badge to open the Alerts tab for the object that provides
data to the widget.
Risk Trend Displays a chart, depending on the selected or configured object.
The charts vary, depending on whether the monitored object is a
group, a descendent object, or an object that provides resources
to other objects. The chart appears only if the Badge Mode
configuration option is off. If the Badge Mode is on, only the
badge appears.
VMware by Broadcom  4017

---
## page 4018

 VMware Cloud Foundation 9.0
Risk Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Badge Mode Determines whether the widget displays only the badge, or the
badge and a weather map or trend chart.
Select one of the following options:
• On. Only the badge appears in the widget.
• Off. The badge and a chart appear in the widget. The chart
provides additional information about the state of the object.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Rolling View Chart Widget
The Rolling View Chart widget cycles through selected metrics at an interval that you define and shows one metric graph
at a time. Miniature graphs, which you can expand, appear for all selected metrics at the bottom of the widget.
VMware by Broadcom  4018

---
## page 4019

 VMware Cloud Foundation 9.0
How the Rolling View Chart Widget and Configuration Options Work
The Rolling View Chart widget shows a full chart for one selected metric at a time. Miniature graphs for the other selected
metrics appear at the bottom of the widget. You can click a miniature graph to see the full graph for that metric, or set the
widget to rotate through all selected metrics at an interval that you define. The key in the graph indicates the maximum
and minimum points on the line chart.
You edit a Rolling View Chart widget after you add it to a dashboard. The changes you make to the options create a
custom chart to meet the needs of the dashboard users.
Where You Find the Rolling View Chart Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Rolling View Chart Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
The toolbar contains icons that you can use to change the view of the graphs.
Option Description
Trend Line Shows or hides the line and data points that represents the metric trend. The trend line filters
out metric noise along the timeline by plotting each data point relative to the average of its
adjoining data points.
Dynamic Thresholds Shows or hides the calculated dynamic threshold values for a 24-hour period.
Show Entire Period Dynamic
Thresholds
Shows or hides dynamic thresholds for the entire time period of the graph.
Anomalies Shows or hides anomalies. Time periods when the metric violates a threshold are shaded.
Anomalies are generated when a metric crosses a dynamic or static threshold, either above
or below.
Zoom to Fit Changes all graphs to show the entire time period and value range.
Zoom the view Click this icon and drag to outline a part of the hierarchy. The display zooms to show only the
outlined section.
Pan Click this icon and click and drag the hierarchy to show different parts of the hierarchy.
Show Data Values After you click the Show data point tips icon to retrieve the data, click this icon and point to
a graphed data point to show its time and exact value. In non-split mode, you can hover over
a metric in the legend to show the full metric name, the names of the adapter instances (if
any) that provide data for the resource to which the metric belongs, the current value, and the
normal range. If the metric is currently alarming, the text color in the legend changes to yellow
or red, depending on your color scheme. Click a metric in the legend to highlight the metric in
the display. Clicking the metric again toggles its highlighted state.
Date Controls Use the date selector to limit the data that appears in each chart to the time period you are
examining.
VMware by Broadcom  4019

---
## page 4020

 VMware Cloud Foundation 9.0
Option Description
Select Dashboard Time to activate the dashboard time panel. The option chosen in the
dashboard time panel is effective. The default time is 6 hours.
Dashboard Time is the default option.
Rolling View Chart Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Data section provides options to select object types on which you are basing the widget data.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Auto Transition Interval Time interval for a switch between charts in the widget.
Input Data
Metrics Select metrics on which you want to base the widget data. You
can select an object and pick its metrics.
VMware by Broadcom  4020

---
## page 4021

 VMware Cloud Foundation 9.0
Option Description
1. Click the Add New Metrics icon to add metrics for the widget
data. Select an object to view its metric tree and pick metrics
for the object. The picked metrics appear in a list in this
section.
The metric tree shows common metrics for several objects
when you click the Show common metrics icon.
While selecting objects for which you want to pick metrics, you
can use the Filter text box to search for objects. You can also
expand the Tag Filter pane on the left hand side to select one
or more object tag values. A list of objects with the selected
tag values appears. If you select more than one value for the
same tag, you can choose objects that have any of the tags
applied. If you select more than one value for different tags,
you can choose only the objects that have all the tags applied.
2. Optionally, select metrics from the list and click the Remove
Selected Metrics icon to remove the selected metrics.
Click the Select All icon to select all the metrics in the list.
Click the Clear Selection icon to clear your selection of
metrics in the list.
You can define measurement units for the metrics in the list.
Double-click a metric box in the list, select a measurement unit in
the Unit drop-down menu, and click Update.
Objects Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the
pop-up window. The selected objects appear in a list in this
section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane
on the left hand side to select one or more object tag values.
A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose
objects that have any of the tags applied. If you select more
than one value for different tags, you can choose only the
objects that have all the tags applied.
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of
objects in the list.
All If you select this option, the widget data is based on all the objects
in your environment. The following sections provide options to
refine the objects for the widget data.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the
objects. For example, if you select the Children check box and
a Depth of 1, the child objects are the transformed inputs for the
widget.
Output Data
Empty drop-down menu Specifies a list with attributes to display.
Add metrics based on object types. The objects corresponding to
the selected metrics are the basis for the widget data.
VMware by Broadcom  4021

---
## page 4022

 VMware Cloud Foundation 9.0
Option Description
1. Click the Add New Metrics icon to add metrics based on
object types. The metrics that you add appear in a list in this
section.
While selecting object types for which you want to pick
metrics, you can filter the object types by adapter type to pick
an object type. On the metrics pane, click the Select Object
icon to select an object for the object type. Pick metrics of the
selected object from the metric tree.
For example, you can select the Datacenter object type,
click the Select Object icon to display the list of data centers
in your environment, and pick metrics of the selected data
center.
2. Optionally, you can define measurement units for the metrics
in the list. Double-click a metric box in the list, select a
measurement unit in the Unit drop-down menu, and click
Update.
Output Filter
Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
If the objects have an input transformation applied, you define filter
criteria for the object types of the transformed objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
Scoreboard Widget
The Scoreboard widget shows the current value for each metric of the objects that you select.
How the Scoreboard Widget and Configuration Options Work
Each metric appears in a separate box or as a gauge chart depending on the mode you choose. The value of the metric
determines the color of the box or the gauge chart. You define the ranges for each color when you edit the widget. You
can customize the widget to use a sparkline chart to show the trend of changes of each metric. If you point to a box, the
widget shows the source object and metric data. Icons in the box indicate the level of criticality.
You edit a Scoreboard widget after you add it to a dashboard. The widget can display metrics of the objects selected
during editing of the widget or selected on another widget. When the Scoreboard widget is not in Self Provider mode,
VMware by Broadcom  4022

---
## page 4023

 VMware Cloud Foundation 9.0
it shows metrics defined in a configuration XML file that you select in the Metric Configuration. It shows 10 predefined
metrics if you do not select an XML file or if the type of the selected object is not defined in the XML file.
For example, you can configure the Scoreboard widget to use the sample Scoreboard metric configuration and to receive
objects from the Topology Graph widget. When you select a host on a Topology Graph widget, the Scoreboard widget
shows the workload, memory, and CPU usage of the host.
To set a source widget that is on the same dashboard, you must use the Widget Interactions menu when you edit a
dashboard. To set a source widget that is on another dashboard, you must use the Dashboard Navigation menu when you
edit the source dashboard.
Where You Find the Scoreboard Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Scoreboard Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Data section provides options to select object types on which you are basing the widget data.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
VMware by Broadcom  4023

---
## page 4024

 VMware Cloud Foundation 9.0
Option Description
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
When the Scoreboard widget is not in self-provider mode, it shows
metrics defined in a configuration XML file that you select in the
Metric Configuration.
View Mode Select either Classic or Gauge.
If you choose Classic, you can view the metric in a separate box.
The value of the metric determines the color of the box.
If you select Gauge, you can view a gauge chart of the thresholds
of the metric based on the values that you set for each color.
You can set the color and maximum value from the datagrid.
Round Decimals Select the number of decimal places to round the scores that the
widget displays.
Box Columns Select the number of columns that appear in the widget.
Layout Mode Select a Fixed Size or Fixed View layout.
Fixed Size
Fixed View
Use these options to customize the size of the box for each object.
Old metric values Select Show if you want the widget to show the previous value
of the metric, if the current value is not available. Select Hide to
hide the previous value of the metric, if the current value is not
available.
Visual Theme Select a predefined visual style for each instance of the widget.
Max Scores Count Use these menus to customize the format of the scores that the
widget displays.
Show Select one or more of the following items to display in the widget:
• Select Object Name to display the name of the object in the
widget.
• Select Metric Name to display the name of the metric in the
widget.
• Select Metric Unit to display the metric unit in the widget.
• Select Sparkline to display the Sparkline chart for each metric.
Period Length Select a length of time for the statistic information that the
sparkline chart displays.
Show DT Select an option to show or hide the dynamic threshold for the
sparkline chart.
Input Data
Metrics Select metrics on which you want to base the widget data. You
can select an object and pick its metrics.
VMware by Broadcom  4024

---
## page 4025

 VMware Cloud Foundation 9.0
Option Description
1. Click the Add New Metrics icon to add metrics for the widget
data. Select an object to view its metric tree and pick metrics
for the object. The picked metrics appear in a list in this
section.
The metric tree shows common metrics for several objects
when you click the Show common metrics icon.
While selecting objects for which you want to pick metrics, you
can use the Filter text box to search for objects. You can also
expand the Tag Filter pane on the left hand side to select one
or more object tag values. A list of objects with the selected
tag values appears. If you select more than one value for the
same tag, you can choose objects that have any of the tags
applied. If you select more than one value for different tags,
you can choose only the objects that have all the tags applied.
2. Optionally, select metrics from the list and click the Remove
Selected Metrics icon to remove the selected metrics.
Click the Select All icon to select all the metrics in the list.
Click the Clear Selection icon to clear your selection of
metrics in the list.
Optionally, you can customize a metric and apply the
customization to other metrics in the list.
1. Double-click a metric box in the list to customize the metric
and click Update.
You can use the Box Label text box to customize the label of
a metric box.
You can use the Unit text box to define a measurement unit of
each metric.
You can use the Color Method option to define a coloring
criteria for each metric. If this option is set to Custom, you can
enter color values in the Yellow, Orange, and Red text boxes.
You can also set coloring by symptom definition. If you do not
want to use color, select None.
For example, to view the remaining memory capacity of a
VM, select Virtual Machine as an object type, expand the
Memory from the metric tree and double-click Capacity
Remaining(%). Define a meaningful label name and
measurement unit to help you when you observe the metrics.
You can select Custom from the Color Method drop-down
menu and specify different values for each color, for example
50 for Yellow, 20 for Orange, and 10 for Red.
You can use the Link to option to add links to external and
internal pages. Internal links open in the same tab. External
links open in a new tab. Examples of external links are
URLs whose hostname does not match with the current VCF
Operations instance hostname. Internal links are URLs whose
hostname matches the current VCF Operations instance
hostname or starts with index.action.
2. Select a metric and click the Apply to All icon to apply the
customization for the selected metric to all the metrics in the
list.
Objects Select objects on which you want to base the widget data.
VMware by Broadcom  4025

---
## page 4026

 VMware Cloud Foundation 9.0
Option Description
1. Click the Add New Objects icon and select objects in the
pop-up window. The selected objects appear in a list in this
section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane
on the left hand side to select one or more object tag values.
A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose
objects that have any of the tags applied. If you select more
than one value for different tags, you can choose only the
objects that have all the tags applied.
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of
objects in the list.
All If you select this option, the widget data is based on all the objects
in your environment. The following sections provide options to
refine the objects for the widget data.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the
objects. For example, if you select the Children check box and
a Depth of 1, the child objects are the transformed inputs for the
widget.
Output Data
Empty drop-down menu Specifies a list with attributes to display.
Add metrics based on object types. The objects corresponding to
the selected metrics are the basis for the widget data.
1. Click the Add New Metrics icon to add metrics based on
object types. The metrics that you add appear in a list in this
section.
While selecting object types for which you want to pick
metrics, you can filter the object types by adapter type to pick
an object type. On the metrics pane, click the Select Object
icon to select an object for the object type. Pick metrics of the
selected object from the metric tree.
For example, you can select the Datacenter object type,
click the Select Object icon to display the list of data centers
in your environment, and pick metrics of the selected data
center.
2. Optionally, select metrics from the list and click the Remove
Selected Metrics icon to remove the selected metrics.
Click the Select All icon to select all the metrics in the list.
Click the Clear Selection icon to clear your selection of
metrics in the list.
Optionally, you can customize a metric and apply the
customization to other metrics in the list.
VMware by Broadcom  4026

---
## page 4027

 VMware Cloud Foundation 9.0
Option Description
1. Double-click a metric box in the list to customize the metric
and click Update.
You can use the Box Label text box to customize the label of
a metric box.
You can use the Unit text box to define a measurement unit of
each metric.
You can use the Max Value option to define the maximum
value to be displayed in the gauge chart. To set the maximum
value, you can either enter an absolute max value or select
a metric and the current value of the metric is considered the
maximum value in the gauge chart.
You can use the Color Method option to define a coloring
criteria for each metric. If this option is set to Custom, you can
enter color values in the Yellow, Orange, and Red text boxes.
You can also set coloring by symptom definition. If you do not
want to use color, select None.
Note:
For the gauge view, you can use only the Custom option.
For example, to view the remaining memory capacity of a
VM, select Virtual Machine as an object type, expand the
Memory from the metric tree and double-click Capacity
Remaining(%). Define a meaningful label name and
measurement unit to help you when you observe the metrics.
You can select Custom from the Color Method drop-down
menu and specify different values for each color, for example
50 for Yellow, 20 for Orange, and 10 for Red.
You can use the Link to option to add links to external and
internal pages. Internal links open in the same tab. External
links will open in a new tab. Examples of external links are
URLs whose hostname does not match with the current VCF
Operations instance hostname. Internal links are URLs whose
hostname matches the current VCF Operations instance
hostname or starts with index.action.
2. Select a metric and click the Apply to All icon to apply the
customization for the selected metric to all the metrics in the
list.
Output Filter
Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
If the objects have an input transformation applied, you define filter
criteria for the object types of the transformed objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
VMware by Broadcom  4027

---
## page 4028

 VMware Cloud Foundation 9.0
Option Description
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
Scoreboard Health Widget
The Scoreboard Health widget displays color-coded health, risk, efficiency, and custom metrics scores for objects that you
select.
How the Scoreboard Health Widget and Configuration Options Work
The icons for each object are color coded to give a quick indication of the state of the object. You can configure the widget
to display the scores of common or specific metrics of the object. You can use the symptom state color code or you can
define your criteria to color the images. If you configure the widget to show the metric for objects that do not have this
metric, those objects have blue icons.
You can double-click an object icon to show the Object Detail page for the object. When you point to the icon, a tool tip
shows the name of the object and the name of the metric.
You edit a Scoreboard Health widget after you add it to a dashboard. To configure the widget, click the pencil at the upper-
right corner of the widget window. The widget can display metrics of the objects that you select when you edit the widget,
or that you select on another widget. For example, you can configure the widget to show the CPU workload of an object
that you select on the Topology Graph widget. To set a source widget that is on the same dashboard, you must use the
Widget Interactions menu when you edit a dashboard. To set a source widget that is on another dashboard, you must use
the Dashboard Navigation menu when you edit the source dashboard.
Where You Find the Scoreboard Health Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Scoreboard Health Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The Configuration section provides general configuration options for the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
VMware by Broadcom  4028

---
## page 4029

 VMware Cloud Foundation 9.0
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Image Type Select an image type for the metrics.
Metric Select the default or custom metric.
Pick Metric Active only when you select Custom from the Metric menu.
Use to select a custom metric for the objects that the widget
displays. Click Pick Metric and select an object type from the
Object Type pane.
Use the Metric Picker pane to select a metric from the metric tree
and click Select Object to check the objects from the type that
you select on the Object Types pane.
Use Symptom state to color chart Select to use the default criteria to color the image.
Custom ranges Use to define custom criteria to color the image. You can define a
range for each color.
Input Data
Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the
pop-up window. The selected objects appear in a list in this
section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane
on the left hand side to select one or more object tag values.
A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose
objects that have any of the tags applied. If you select more
than one value for different tags, you can choose only the
objects that have all the tags applied.
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of
objects in the list.
VMware by Broadcom  4029

---
## page 4030

 VMware Cloud Foundation 9.0
Sparkline Chart Widget
The Sparkline Chart widget displays graphs that contain metrics for an object in VCF Operations. You can use VCF
Operations to create one or more graphs that contain metrics for objects that you add to your custom dashboards.
How the Sparkline Chart Widget and Configurations Options Work
If the metrics in the Sparkline Chart are for an object that another widget provides, the object name appears at the
top right of the widget. If you select a metric when you edit the widget configuration, the widget uses the metric and its
corresponding object as the source for dashboard interactions. The line in the graphs represents the average value of the
selected metric for the specified time period. The boxed area in the graph represents the dynamic threshold of the metric.
Point to a graph in the Sparkline Chart widget to view the value of a metric in the form of a tool tip. You can also view the
maximum and minimum values on a graph. The values are displayed as orange dots.
You can add the Sparkline Chart widget to one or more custom dashboards and configure it to display data that is
important to different dashboard users. The data that appears in the widget is based on the configured options for each
widget instance.
The metrics shown in sparkline widget is the current value, to view the average value you can use transformations in
list views or distribution charts to calculate an average. Another way to get to an average value is to double click on the
sparkline to open the metric chart, click and drag to select a range, keep the mouse button depressed and hover for a few
seconds, you should see a popup that has average value.
Where You Find the Sparkline Chart Widget
The widget might be included on any of your custom dashboards. On the menu, click Dashboards to display a list of
dashboards in the left pane.
Sparkline Chart Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
The toolbar contains icons that you can use to change the view of the graphs.
Option Description
Dashboard Navigation You can navigate to another dashboard when the object you select is also available in the
dashboard to which you want to navigate.
Refresh Refreshes the widget data.
Time Range Select the range for the time period to show on the graphs. You can select a period from the
default time range list or select start and end dates and times.
Select Dashboard Time to activate the dashboard time panel. The option chosen in the
dashboard time panel is effective. The default time is 6 hours.
Dashboard Time is the default option.
Remove All Removes all graphs.
Sparkline Chart Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
VMware by Broadcom  4030

---
## page 4031

 VMware Cloud Foundation 9.0
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Data section provides options to select object types on which you are basing the widget data.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Show Object Name You can view the name of the object before the metric name in the
Sparkline Chart widget.
• On. Displays the name of the object before the metric name in
the widget.
• Off. Does not display the name of the object in the widget.
Column Sequence Select the order in which to display the information.
• Graph First. The metric graph appears in the first column in
the widget display.
• Label First. The metric label appears in the first column in the
widget display.
Show DT Select an option to show or hide the dynamic threshold for the
sparkline chart.
Input Data
Metrics Select metrics on which you want to base the widget data. You can
select an object and pick its metrics.
VMware by Broadcom  4031

---
## page 4032

 VMware Cloud Foundation 9.0
Option Description
1. Click the Add New Metrics icon to add metrics for the widget
data. Select an object to view its metric tree and pick metrics
for the object. The picked metrics appear in a list in this
section.
The metric tree shows common metrics for several objects
when you click the Show common metrics icon.
While selecting objects for which you want to pick metrics, you
can use the Filter text box to search for objects. You can also
expand the Tag Filter pane on the left hand side to select one
or more object tag values. A list of objects with the selected
tag values appears. If you select more than one value for the
same tag, you can choose objects that have any of the tags
applied. If you select more than one value for different tags,
you can choose only the objects that have all the tags applied.
2. Optionally, select metrics from the list and click the Remove
Selected Metrics icon to remove the selected metrics.
Click the Select All icon to select all the metrics in the list.
Click the Clear Selection icon to clear your selection of
metrics in the list.
Optionally, you can customize a metric and apply the
customization to other metrics in the list.
1. Double-click a metric box in the list to customize the metric
and click Update.
You can use the Box Label text box to customize the label of a
metric box.
You can use the Unit text box to define a measurement unit of
each metric.
You can use the Color Method option to define a coloring
criteria for each metric. If this option is set to Custom, you can
enter color values in the Yellow, Orange, and Red text boxes.
You can also set coloring by symptom definition. If you do not
want to use color, select None.
For example, to view the remaining memory capacity of a VM,
select Virtual Machine as an object type, expand the Memory
from the metric tree and double-click Capacity Remaining(%).
Define a meaningful label name and measurement unit to
help you when you observe the metrics. You can select
Custom from the Color Method drop-down menu and specify
different values for each color, for example 50 for Yellow, 20
for Orange, and 10 for Red.
2. Select a metric and click the Apply to All icon to apply the
customization for the selected metric to all the metrics in the
list.
Objects Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the pop-
up window. The selected objects appear in a list in this section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane
on the left hand side to select one or more object tag values.
A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose
objects that have any of the tags applied. If you select more
than one value for different tags, you can choose only the
objects that have all the tags applied.
VMware by Broadcom  4032

---
## page 4033

 VMware Cloud Foundation 9.0
Option Description
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of
objects in the list.
All If you select this option, the widget data is based on all the objects
in your environment. The following sections provide options to
refine the objects for the widget data.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the
objects. For example, if you select the Children check box and
a Depth of 1, the child objects are the transformed inputs for the
widget.
Output Data
Empty drop-down menu Specifies a list with attributes to display.
Add metrics based on object types. The objects corresponding to
the selected metrics are the basis for the widget data.
Click the Add New Metrics icon to add metrics for the widget
data. Select an object to view its metric tree and pick metrics for
the object. The picked metrics appear in a list in this section.
The metric tree shows common metrics for several objects when
you click the Show common metrics icon.
While selecting objects for which you want to pick metrics, you can
use the Filter text box to search for objects. You can also expand
the Tag Filter pane on the left hand side to select one or more
object tag values. A list of objects with the selected tag values
appears. If you select more than one value for the same tag, you
can choose objects that have any of the tags applied. If you select
more than one value for different tags, you can choose only the
objects that have all the tags applied.
Optionally, you can customize a metric and apply the
customization to other metrics in the list.
1. Double-click a metric box in the list to customize the metric
and click Update.
You can use the Box Label text box to customize the label of a
metric box.
You can use the Unit text box to define a measurement unit of
each metric.
You can use the Color Method option to define a coloring
criteria for each metric. If this option is set to Custom, you can
enter color values in the Yellow, Orange, and Red text boxes.
You can also set coloring by symptom definition. If you do not
want to use color, select None.
For example, to view the remaining memory capacity of a VM,
select Virtual Machine as an object type, expand the Memory
from the metric tree and double-click Capacity Remaining(%).
Define a meaningful label name and measurement unit to
help you when you observe the metrics. You can select
Custom from the Color Method drop-down menu and specify
different values for each color, for example 50 for Yellow, 20
for Orange, and 10 for Red.
VMware by Broadcom  4033

---
## page 4034

 VMware Cloud Foundation 9.0
Option Description
2. Select a metric and click the Apply to All icon to apply the
customization for the selected metric to all the metrics in the
list.
Output Filter
Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have an input transformation applied, you define filter
criteria for the object types of the transformed objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
Tag Picker Widget
The Tag Picker widget lists all available object tags.
How the Tag Picker Widget and Configuration Options Work
With the Tag Picker widget, you can check the list of the object tags. You can use the widget to filter the information that
another widget shows. You can select one or more tags from the object tree or search for tags, and the destination widget
displays information about the objects with this tag. For example, you can select Object Types > Virtual Machine on the
Tag Picker widget to observe statistic information about the VMs on the Environment Status widget.
You edit a Tag Picker widget after you add it to a dashboard. To configure the widget, click the pencil in the upper right of
the widget window. You can configure the Tag Picker widget to send information to another widget on the same dashboard
or on another dashboard. To set a receiver widget that is on the same dashboard, use the Widget Interactions menu
when you edit a dashboard. To set a receiver widget that is on another dashboard, use the Dashboard Navigation
menu when you edit a source dashboard. You can configure two Tag Picker widgets to interact when they are on different
dashboards.
Where You Find the Tag Picker Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
VMware by Broadcom  4034

---
## page 4035

 VMware Cloud Foundation 9.0
Tag Picker Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Option Description
Collapse All Close all expanded tags and tag values.
Deselect All Remove all filtering and view all objects in the widget.
Tag Picker Select an object from your environment.
Dashboard Navigation Note:  Appears on the source widget and when the destination
widget is on another dashboard.
Use to explore the information on another dashboard.
Tag Picker Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Text Display Widget
You can use the Text Display widget to show text in the user interface. The text appears in the Text Display widget on the
dashboard.
The Text Display widget can read text from a Web page or text file. You specify the URL of the Web page or the name of
the text file when you configure the Text widget. To use the Text Display widget to read text files you must set a property in
the web.properties file to specify the root folder that contains the file.
VMware by Broadcom  4035

---
## page 4036

 VMware Cloud Foundation 9.0
You can enter content in the Text Display widget in plain text or rich text format based on the view mode that you
configure. Configure the Text Display widget in HTML view mode to display content in rich text format. Configure the Text
Display widget in Text mode to display content in plain text format.
The Text Display widget can display websites that use the HTTPS protocol. The behavior of the Text Display widget with
websites that use HTTP, depends on the individual settings of the websites.
Note:  If the webpage that you are linking to has X-Frame-Options set to sameorigin, which denies rendering a page
in an iframe, the Text Display widget cannot display the contents of the webpage.
How the Text Display Widget Configuration Options Work
You can configure the widget in the Text view mode or HTML view mode. In the HTML view mode, you can click Edit in
the widget and use the rich text editor to add content.
If you configure the widget to use Text view mode, you can specify the path to the directory that contains the files to read
or you can provide a URL. The content in the URL will be shown as text. If you do not specify a URL or text file, you can
add content in the widget. Double-click the widget and enter content in plain text.
You can also use command-line interface (CLI) commands to add file content to the Text Display widget.
• To view a list of parameters, run the file -h|import|export|delete|list txtwidget command.
• To import text or HTML content, run the import txtwidget input-file [--title title] [--force] command.
• To export the content to the file, run the export txtwidget all|title[{,title}] [output-dir] command.
• To delete imported content, run the delete txtwidget all|title[{,title}] command.
• To view the titles of the content, run the list txtwidget  command.
Where You Find the Text Display Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Text Display Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
VMware by Broadcom  4036

---
## page 4037

 VMware Cloud Foundation 9.0
Option Description
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
View mode Display text in text or rich text format. You can configure the
widget in HTML view mode only when the URL and File fields are
blank.
URL Enter the URL.
File Navigate to the file that contains the source text file by clicking the
Select button.
To add, edit, and remove source text files, go to the Text Widget
Content tile in the Configuration page. From the left menu, click
Operations > Configurations, and then click the Text Widget
Contenttile from the VCF Operations user interface.
Test Validates the correctness of the text file or URL that you enter.
Time Remaining Widget
The Time Remaining widget displays how much time remains before the resources of the object are exhausted.
VCF Operations calculates the percentage by object type based on historical data for the pattern of use for the object
type. You can use the time remaining percentage to plan provisioning of physical or virtual resources for the object or
rebalance the workload in your virtual infrastructure.
Where You Find the Time Remaining Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Time Remaining Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
VMware by Broadcom  4037

---
## page 4038

 VMware Cloud Foundation 9.0
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Top Alerts Widget
Top alerts are the alerts with the greatest significance on the objects it is configured to monitor in VCF Operations. These
are the alerts most likely to negatively affect your environment and you should evaluate and address them.
How the Top Alerts Widget and Configuration Options Work
You can add the top alerts widget to one or more custom dashboards and configure it to display data that is important
to different dashboard users. The data that appears in the widget is based on the configured options for each widget
instance.
You edit a top alerts widget after you add it to a dashboard. The changes you make to the options help create a custom
widget to meet the needs of the dashboard users.
Where You Find the Top Alerts Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
VMware by Broadcom  4038

---
## page 4039

 VMware Cloud Foundation 9.0
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Top Alerts Widget Display Options
The Top Alerts widget includes the short description of alerts configured for the widget. The alert name opens a secondary
window from which you can link to the alert details. In the alert details, you can begin resolving the alerts.
Option Description
Alert name Name of the generated alert. Click the name to open the alert
details.
Alert description Number of affected objects, and the number of recommendations
and the best recommendation to resolve the alert.
Top Alerts Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Impact Badge Select the badge for which you want alerts to appear.
The affected badge is configured when you configure the alert
definition.
Number of Alerts Select the maximum number of alerts to display in the widget.
Input Data
VMware by Broadcom  4039

---
## page 4040

 VMware Cloud Foundation 9.0
Option Description
Object Search for objects in your environment and select the object on
which you are basing the widget data. You can also click the Add
Object icon and select an object from the object list. You can use
the Filter text box to refine the object list and the Tag Filter pane
to select an object based on tag values.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the
objects. For example, if you select the Children check box and
a Depth of 1, the child objects are the transformed inputs for the
widget.
Top-N Widget
The Top-N widget displays the top n results from analysis of an object or objects that you select.
How the Top-N Widget and Configuration Options Work
You can select an object when you configure the Top-N widget or you can select an object on another widget. The
widget shows an analysis of the applications, alerts, and metrics of an object and its child objects depending on how you
configure the widget. The widget can show an analysis of the current values or values over a period of time. You can
receive detailed information about each object on the widget. When you double-click an object, the Object Detail page
appears.
You can configure a widget to receive data from another widget by selecting Off for Self Provider. You can configure a
widget to display results from analysis of an object that you select on the source widget.
For example, you can select a host on a Topology widget and observe the metric analysis of the virtual machines on
the host. To set a receiver widget that is on the same dashboard, use the Widget Interactions menu when you edit a
dashboard. To set a receiver widget that is on another dashboard, use the Dashboard Navigation menu when you edit a
source dashboard.
Where You Find the Top-N Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Top-N Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
The toolbar contains icons that you can use to change the view of the graphs.
VMware by Broadcom  4040

---
## page 4041

 VMware Cloud Foundation 9.0
Icon Description
Dashboard Navigation Takes you to a predefined object. For example, when you select a datastore from the data grid and
click Dashboard Navigation, you can open the datastore in the vSphere Web Client.
Select Date Range Limits the alerts that appear in the list to the selected date range.
Select Dashboard Time to activate the dashboard time panel. The option chosen in the dashboard
time panel is effective. The default time is 6 hours.
Object details Select an object and click this icon to show the Object Detail page for the object.
Display Filtering Criteria Shows the filtering settings for the widget in a pop-up window.
Percentile Filters and displays objects based on the percentile entered while configuring the widget. You can
change the percentile using the drop-down option.
Note:  The Percentile option is activated in the toolbar of the widget after you configure the widget
with the Percentile option. To configure the widget with the Percentile option, navigate to Configurat
ions > Top-N Options > Metric Analysis > Percentile.
Top-N Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
The Input Transformation section provides options to transform the input for the widget.
The Output Data section provides options to select object types on which you are basing the widget data.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
The Additional Columns section provides options to select metrics that are displayed as additional columns in the
widget.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the
widget are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
VMware by Broadcom  4041

---
## page 4042

 VMware Cloud Foundation 9.0
Option Description
Redraw Rate Set the redraw rate.
Bars Count Select the number of top results.
Round Decimals Select the number of decimals to round the scores displayed in
the widget.
Filter old metrics Select or deselect whether the analysis includes old metric
values.
Application Health and Performance • Top Least Healthy. The top n results from an analysis of the
object or objects that are the least healthy.
• Top Most Healthy. The top n results from an analysis of the
object or objects that are the most healthy.
• Top Most Volatile. The sorted list of values based on the
standard deviation of values for several alerts over time.
Select the criteria for analysis of the objects.
Alert Analysis Select the criteria for analysis of the alerts.
Metric Analysis If you select this option, you must select a metric in the Output
Data section.
• Top Highest Utilization. A list of objects with similar object
types that have the highest utilization on configuring usage
metrics like CPU usage and memory usage.
• Top Lowest Utilization. A list of objects with similar object
types that have the lowest utilization on configuring usage
metrics like CPU usage and memory usage.
• Top Abnormal States. The objects are ordered by the duration
of all alarms that are triggered on the selected metric for a
selected interval.
• Top Highest Volatility. The sorted list of values based on the
standard deviation of values for several alerts over time.
• Percentile. Objects are filtered based on the percentile
entered.
Select the criteria for analysis of the metric that you select from
the metric tree.
Input Data
Objects Select objects on which you want to base the widget data.
1. Click the Add New Objects icon and select objects in the
pop-up window. The selected objects appear in a list in this
section.
While selecting objects, you can use the Filter text box to
search for objects. You can also expand the Tag Filter pane
on the left hand side to select one or more object tag values.
A list of objects with the selected tag values appears. If you
select more than one value for the same tag, you can choose
objects that have any of the tags applied. If you select more
than one value for different tags, you can choose only the
objects that have all the tags applied.
2. Optionally, select objects from the list and click the Remove
Selected Objects icon to remove the selected objects.
Click the Select All icon to select all the objects in the list.
Click the Clear Selection icon to clear your selection of
objects in the list.
VMware by Broadcom  4042

---
## page 4043

 VMware Cloud Foundation 9.0
Option Description
All If you select this option, the widget data is based on all the
objects in your environment. The following sections provide
options to refine the objects for the widget data.
Input Transformation
Relationship Transform the input for the widget based on the relationship of the
objects. For example, if you select the Children check box and
a Depth of 1, the child objects are the transformed inputs for the
widget.
Output Data
Select an object type in your environment on which you want to
base the widget data.
1. Click the Add Object Type icon to search for and add an
object type.
When you search for object types, you can filter the types in
the list by selecting a type from the Adapter Type drop-down
menu or by using the Filter text box.
2. Optionally, select the object type from the list and click the
Delete Object Type icon to remove the selected object type.
If the objects have an input transformation applied, the
transformed objects are the basis for the widget data.
Metric Select a common metric or a metric for the selected object type in
the list. The metric is the basis for the widget data.
Label Type in a name that displays as a label for the metric.
You can add a label if you have selected Metric Analysis >
Top Highest Utilization or Metric Analysis > Top Lowest
Utilization as Top-N options in the Configuration section.
Unit You can define measurement units for the metrics. Select a
measurement unit in the Unit drop-down menu.
You can add a unit if you have selected Metric Analysis >
Top Highest Utilization or Metric Analysis > Top Lowest
Utilization as Top-N options in the Configuration section.
Maximum Specify the maximum value based on which the bar size is
calculated.
You can add a maximum value if you have selected any of the
options under Metric Analysis.
Color Method You can use the Color Method option to define a coloring criteria
for each metric. If this option is set to Custom, you can enter
color values in the Yellow, Orange, and Red text boxes. If you do
not want to use color, select None.
You can add color thresholds if you have selected Metric
Analysis > Top Highest Utilization, Metric Analysis > Top
Lowest Utilization, or Metric Analysis > Percentile as Top-N
options in the Configuration section.
Output Filter
VMware by Broadcom  4043

---
## page 4044

 VMware Cloud Foundation 9.0
Option Description
Basic Pick tags to refine the widget data. The widget data is based on
the objects that have the picked tags applied. If you pick more
than one value for the same tag, the widget includes objects that
have any of the tags applied. If you pick more than one value for
different tags, the widget includes only the objects that have all
the tags applied.
If the objects have an input transformation applied, you select tag
values for the transformed objects.
Advanced Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection,
you define filter criteria for the object types of the objects with tag
filter applied. If the objects with tag filter applied do not belong to
any of the object types in this filter criteria, the widget skips this
filter and includes all the objects with tag filter applied.
If the objects have an input transformation applied, you define
filter criteria for the object types of the transformed objects.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
Additional Columns
Add metrics based on object types. The selected metrics are
displayed as additional columns in the widget.
1. Click the Add New Metrics icon to add metrics based on
object types. The metrics that you add appear in a list in this
section.
While selecting object types for which you want to pick
metrics, you can filter the object types by adapter type to pick
an object type. On the metrics pane, click the Select Object
icon to select an object for the object type. Pick metrics of the
selected object from the metric tree.
For example, you can select the Datacenter object type,
click the Select Object icon to display the list of data centers
in your environment, and pick metrics of the selected data
center.
2. Optionally, you can double-click a metric box in the list to
customize the label of the metric and click Update.
Topology Graph Widget
The Topology Graph widget gives a graphical presentation of objects and their relationships in the inventory. You can
customize each instance of the widget in your dashboard.
VMware by Broadcom  4044

---
## page 4045

 VMware Cloud Foundation 9.0
How the Topology Graph Widget and Configuration Options Work
The Topology Graph widget helps you explore all nodes and paths connected to an object from your inventory. Connection
between the objects might be a logical, physical, or network connection. The widget can display a graph that shows all of
the nodes in the path between two objects, or that shows the objects related to a node in your inventory. You select the
type of graph in the Exploration Mode when you configure the widget. You can select the levels of exploration between
nodes in the displayed graph by using Relationship check boxes when you edit the widget. The widget displays all
object types in the inventory by default, but you can select object types to view by using the Object View list during the
configuration process. Double-clicking an object on the graph takes you to a detailed page about the object.
Where You Find the Topology Graph Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Topology Graph Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
Option Description
Action Use to select from predefined actions for each object type. To
see available predefined actions, select an object in the graph
and click the toolbar to select an action. For example, when you
select a datastore object in the graph, you can click Delete Unused
Snapshots for Datastore to apply this action to the object.
Dashboard Navigation Takes you to a predefined object. For example, when you select
a datastore from the graph and click Dashboard Navigation, you
can open the datastore in the vSphere Web Client.
Pan Use to move the entire graph.
Show values on point Provides a tool tip with parameters when you point to an object in
the graph.
Zoom in Zooms in the graph.
Zoom out Zooms out the graph.
Hierarchical View Use to switch to hierarchical view. Hierarchical view is activated
only for Node Exploration mode and with selected inventory tree.
Graph View Use to switch to graph view.
Object Detail Select an object and click this icon to show the Object Detail page
for the object.
Expand Node Selects which object types related to your object to show on the
graph. For example, if you select a virtual machine from the graph
and click Expand Node toolbar icon and select Host System, the
host on which the virtual machine is located is added to the graph.
VMware by Broadcom  4045

---
## page 4046

 VMware Cloud Foundation 9.0
Option Description
Hide Node(s) Use to remove a given object from the graph
Reset To Initial Object Use to return to the initially displayed graph and configured object
types.
Explore Node Use to explore a node from a selected object in the graph. For
example, if the graph displays a connection between a VM, a host,
and a datastore, and you want to check the connection of the host
with the other objects in the inventory, you can select the host and
click Explore Node.
Status Use to select objects based on their status or their state.
Topology Graph Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Exploration Mode Use Node Exploration mode to observe a selected object from
an object list and the objects related to it. For example, if you
select a virtual machine and select node exploration mode, the
widget shows the host where the VM is placed and the datastore
storing the files of the VM.
Use Path Exploration mode to observe the relation between two
objects. You must select them from the Select First Object list and
the Select Second Object list. For example, if you select to explore
the path between a VM and a vCenter, the graph shows you both
objects and all nodes in the path between the VM and server as
datastore, datastore cluster, and data center.
VMware by Broadcom  4046

---
## page 4047

 VMware Cloud Foundation 9.0
Option Description
Important:  To select object view is mandatory for the widget to
start working in path exploration mode.
Use All to observe connections between a node and nodes
related to it as well as connections between the nodes. For
example, if you are using node exploration mode and you select
to observe a VM and all objects types, the graph shows a VM
connected to its datastore and host and the connection between
the host and datastore.
Show Paths
Use Discovered Only to observe directly related nodes. For
example, if you are using node exploration mode and you select
to observe a VM and all objects types, the graph will shows the
VM connected to its datastore and to its host, but without the
connection between the host and datastore.
Configuration File The default configuration includes parent and child relationship.
Drop-down options depend on the installed Solutions. You can
add a new type of relationship to the Relationship pane.
Metric Configuration Specifies a list with attributes to display.
Layout Select whether you want a graph view or hierarchical view for the
topology graph.
Tree type For a hierarchical layout, select whether you want a tree type view.
Input Data
Selected object From the object list, select an object on which you want to base
the widget data.
Degree of separation Available only when node exploration mode is selected. Use to
define the levels of exploration in node exploration mode. The
lowest degree configuration shows only directly related nodes
rather than higher degrees that show the inventory in details.
Select First Object Available only in path exploration mode. Select the first object
from the object list.
Select Second Object Available only in path exploration mode. Select the second object
from the object list.
Object view Use to select which types of objects to observe in the graph.
Relationship Select the type of relationship between objects to observe in the
graph, respectively the details about your inventory . The common
relationships for all objects are parent and child, but the list of
relationships can vary depending on added solutions to VCF
Operations.
 View Widget
The View widget provides the VCF Operations view functionality into your dashboard.
How the View Widget and Configuration Options Work
A view presents collected information for an object in a certain way depending on the view type. Each type of view helps
you to interpret metrics, supermetrics, properties, alerts, policies, and data from a different perspective.
VMware by Broadcom  4047

---
## page 4048

 VMware Cloud Foundation 9.0
You can add the View widget to one or more custom dashboards and configure it to display data that is important to the
dashboard users. List views can send interactions to other widgets.
Where You Find the View Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
You can export the view as a CSV file for any view type.
View Widget Toolbar Options
The View widget toolbar depends on the displayed view type.
Option Description
Export as CSV You can export the view as a CSV file for any view type.
Open in External Application Ability to link to another application for information about the
object. For example, you have a List view with VMs. You can
select any VM and select Open in External Application to open
the VM in vSphere Web Client.
Time Settings Use the time settings to select the time interval of data
transformation. These options are available for all view types,
except Image.
• Relative Date Range. Select a relative date range of data
transformation.
• Specific Date Range. Select a specific date range of data
transformation.
• Absolute Date Range. Select a date or time range to view
data for a time unit such as a complete month or a week. For
example, you can run a report on the third of every month
for the previous month. Data from the first to the end of the
previous month is displayed as against data from the third of
the previous month to the third of the current month.
The units of time available are: Hours, Days, Weeks, Months,
and Years.
The locale settings of the system determine the start and
end of the unit. For example, weeks in most of the European
countries begin on Monday while in the United States they
begin on Sunday.
• Dashboard Time. Select this option to activate the dashboard
time panel. The option chosen in the dashboard time panel is
effective. The default time is 6 hours.
Items per page You can set the number of results that appear in the widget.
Available for List view only.
VMware by Broadcom  4048

---
## page 4049

 VMware Cloud Foundation 9.0
Option Description
Roll up interval The time interval at which the data is rolled up.
Actions An action on the selected object. Depends on the object type.
Filter Limits the list to objects for a specific host, data center, and so
on. You can drill-down in the hierarchical level. Available for List,
Trend, and Distribution types of Views.
Filter by name Limits the list to objects of a specific name. Available for List view
only.
View Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget.
The Output Data section provides options to select object types on which you are basing the widget data.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Self Provider Indicates whether the objects for which data appears in the widget
are defined in the widget or provided by another widget.
• On. You define the objects for which data appears in the
widget.
• Off. You configure other widgets to provide the objects to the
widget using the dashboard widget interactions options.
Input Data
Inventory trees Select an existing predefined traversal spec to pick an object for
the widget data.
Object In self-provider mode, click the Add Object icon to select an
object from the object list. The object list is displayed based on the
inventory tree selection. You can also search for the object in this
text box.
Output Data
VMware by Broadcom  4049

---
## page 4050

 VMware Cloud Foundation 9.0
Option Description
A list of defined views available for the selected object is
displayed.
You can create, edit, delete, clone, export, and import views
directly from the View widget configuration options.
For more information, see Views.
Auto Select First Row Determines whether to start with the first row of data for list type
views.
Show Select one or more of the following items to display in the widget:
• To display the list of legends in the widget, select Legend.
• To display the name of the labels in the widget, select Labels.
 Weather Map Widget
The Weather Map widget provides a graphical display of the changing values of a single metric for multiple resources over
time. The widget uses colored icons to represent each value of the metric. Each icon location represents the metric value
for particular resources. The color of an icon changes to show changes in the value of the metric.
How the Weather Map Widget and Configuration Options Work
You can add the Weather Map widget to one or more custom dashboards and configure it to display data that is important
to different dashboard users. The data that appears in the widget is based on the configured options for each widget
instance.
Watching how the map changes can help you understand how the performance of the metric varies over time for different
resources. You can start or stop the display using the Pause and Play options at the bottom of the map. You can move
the slider forwards or backwards to a specific frame in the map. If you leave the widget display and return, the slider
remains in the same state.
The map does not show the real-time performance of the metrics. You select the time period, how fast the map refreshes,
and the interval between readings. For example, you might have the widget play the metric values for the previous day,
refreshing every half second, and have each change represent five minute's worth of metric values.
To view the object that an icon represents, click the object.
Where You Find the Weather Map Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
Weather Map Widget Toolbar Options
On the title bar of the widget, click the Show Toolbar icon to access the toolbar options.
The toolbar contains the icons that you can use to view the graph.
VMware by Broadcom  4050

---
## page 4051

 VMware Cloud Foundation 9.0
Icon Description
Pause and Play Start or stop the display. The icon remains in the same state if you leave the widget display and
return.
Display Filtering Criteria View the current settings for the widget, including the current metric.
Weather Map Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Output Data section provides options to select object types on which you are basing the widget data.
The Output Filter section provides options to restrict the widget data based on the selected filter criteria.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
Refresh Interval If you activate the Refresh Content option, specify how often to
refresh the data in this widget.
Redraw Rate An interval at which cashed data is refreshed based on newly
collected data.
For example, if you set metric history to Last 6 hours and
image redraw rate to 15 minutes, and data is collected
every 5 minutes, the data collected during 10 minutes will not be
calculated at the 15 minutes.
For example, if you set metric history to Last 6 hours and
image redraw rate to 15 minutes, and data is collected
every 5 minutes, the data collected during 10 minutes will not be
calculated at the 15 minutes.
Metric History Select the time period for the weather map, from the previous hour
to the last 30 days.
Metric Sample Increment Select the interval between metric readings. For example, if you
set this option to one minute and set the Metric History to one
hour, the widget has a total of 60 readings for each metric.
Group by Select a tag value by which to group the objects.
Sort by Select Object name or Metric value to set the way to sort the
objects.
Frame Transition Interval Select how fast the icons change to show each new value. You
can select the interval between frames and the number of frames
per second (fps).
VMware by Broadcom  4051

---
## page 4052

 VMware Cloud Foundation 9.0
Option Description
Start Over Delay The number of seconds for the display to remain static when it
reaches the end of the Metric History period, the most current
readings, before it starts over again from the beginning.
Color Shows the color range for high, intermediate, and low values. You
can set each color and type minimum and maximum color values
in the Min Value and Max Value text boxes.
If you leave the text boxes blank, VCF Operations maps the
highest and lowest values for the Color By metric to the end
colors.
If you set a minimum or maximum value, any metric at or beyond
that value appears in the end color.
Output Data
Select an object type in your environment on which you want to
base the widget data.
1. Click the Add Object Type icon to search for and add an
object type.
When you search for object types, you can filter the types in
the list by selecting a type from the Adapter Type drop-down
menu or by using the Filter text box.
2. Optionally, select the object type from the list and click the
Delete Object Type icon to remove the selected object type.
Metric Select a common metric or a metric for the selected object type in
the list. The metric will be the basis for the widget data. The object
corresponding to the metric is the selected object for the widget.
Output Filter
Basic Pick tags to refine the widget data. The widget data is based on
the objects that have the picked tags applied. If you pick more
than one value for the same tag, the widget includes objects that
have any of the tags applied. If you pick more than one value for
different tags, the widget includes only the objects that have all the
tags applied.
Advanced Refine the widget data further based on the filter criteria for object
types. The widget data is based on the objects for the filtered
object types.
If the objects have a tag filter applied in the Basic subsection, you
define filter criteria for the object types of the objects with tag filter
applied. If the objects with tag filter applied do not belong to any of
the object types in this filter criteria, the widget skips this filter and
includes all the objects with tag filter applied.
1. In the first drop-down menu, select an object type.
2. In the second drop-down menu, select the option based on
which you want to define the filter criteria. For example, if you
select Metrics for the Datacenter object type, you can define
a filter criteria based on the value of a specific metric for data
centers.
3. In the drop-down menus and text boxes that appear, select or
enter values to filter the objects.
4. To add more filter criteria, click Add.
5. To add another filter criteria set, click Add another criteria
set.
VMware by Broadcom  4052

---
## page 4053

 VMware Cloud Foundation 9.0
Workload Widget
The Workload widget displays data indicating how hard a selected resource is working.
The Workload widget displays a graph depicting how hard the object that you selected is working. The Workload widget
reports data on CPU usage, Memory usage, Disk I/O, and Network I/O.
Where You Find the Workload Widget
The widget might be included on any of your custom dashboards. From the left menu, click Infrastructure Operations >
Dashboards & Reports to see your configured dashboards.
To customize the data that appears in the dashboard widget, from the left menu, click Infrastructure Operations >
Dashboards & Reports. To create your dashboard, from the left menu, click Infrastructure Operations > Dashboards
& Reports. Click Dashboards > Create.To edit your dashboard, from the left menu, click Infrastructure Operations >
Dashboards & Reports. Click Dashboards and from the Manage tab on the right, select the dashboard you want to edit,
click the three vertical ellipsis and select Edit. Toggle between the Views and Widgets option to view and add a widget or
view to the dashboard. The widgets list panel displays a list of all the predefined widgets. Drag a widget to the dashboard
workspace in the upper panel.
About Datastore Metrics for Virtual SAN
The metric named datastore|oio|workload is not supported on Virtual SAN datastores. This metric depends on
datastore|demand_oio, which is supported for Virtual SAN datastores.
The metric named datastore|demand_oio also depends on several other metrics for Virtual SAN datastores, one of
which is not supported.
• The metrics named devices|numberReadAveraged_average and devices|numberWriteAveraged_average
are supported.
• The metric named devices|totalLatency_average is not supported.
As a result, VCF Operations does not collect the metric named datastore|oio|workload for Virtual SAN datastores.
Workload Widget Configuration Options
On the title bar of the widget, click the Edit Widget icon to configure the widget.
The configuration options are grouped into one or more sections. You can select the objects on which you want to base
the widget data and refine the objects in the following sections. Each section filters the objects further and pushes the
filtered objects to the next section. The widget data is based on the objects that are the output of the last section.
The Configuration section provides general configuration options for the widget.
The Input Data section provides options to specify input for the widget. This section appears when the widget is in self
provider mode.
Option Description
Title Enter a custom title that identifies this widget from other instances
that are based on the same widget template.
Configuration
Refresh Content Activate or deactivate the automatic refreshing of the data in this
widget.
If not activated, the widget is updated only when the dashboard is
opened or when you click the Refresh button on the widget in the
dashboard.
VMware by Broadcom  4053