# supermetrics (VCF 9.0, pages 4171-4180)


---
## page 4171

 VMware Cloud Foundation 9.0
Share a View
You might want to present insights into your application or infrastructure performance to a wider audience, using tools
such as Microsoft Power BI. By using the view share functionality, you can export a view to an external tool to ensure
relevant stakeholders have the latest insights. You can use the provided API end point URL to import view data in a
reporting tool. You can also export the configuration details of the view.
Where You Can Access the Option to Share Views
From the left menu, click Infrastructure Operations > Views. From the Views page on the right, click the Manage tab.
Click an existing view, select a preview source and then click the Share View icon in the top-right corner.
Table 1184: Options in the Share View Dialog Box
Option Description
URL Tab You can export view data using a URL. The resulting view data
includes view configuration data, objects, and metrics metadata,
per object metric data, summary and calculated data, and other
view specific data. View data usually corresponds to the data
shown in the View UI for the specified view configuration. You can
copy and paste the URL in other reporting tools for integration with
VCF Operations.
• Preview Source: You can select the last previewed source.
• URL: You can copy the URL for the selected configured
view. To use the URL as an authorized user, you need an
authorization token.
Note:  The URL provided is the required REST call for fetching
data. See the API Programming Guide for details.
• Authorization: The authorization token is generated. To
generate the authorization token, enter the Username and
Password and click Generate.
Export Tab You can download and export the view configuration details.
Configuring Super Metrics
The super metric is a mathematical formula that contains one or more metrics or properties. It is a custom metric that you
design to help track combinations of metrics or properties, either from a single object or from multiple objects. If a single
metric does not inform you about the behavior of your environment, you can define a super metric.
After you define it, you assign the super metric to one or more object types. This action calculates the super metric for
the objects in that object type and simplifies the metrics display. For example, you define a super metric that calculates
the average CPU usage on all virtual machines, and you assign it to a cluster. The average CPU usage on all virtual
machines in that cluster is reported as a super metric for the cluster.
When the super metric attribute is activated in a policy, you can also collect super metrics from a group of objects
associated with a policy.
Because super metric formulas can be complex, plan your super metric before you build it. The key to creating a super
metric that alerts you to the expected behavior of your objects is knowing your own enterprise and data. Use this checklist
to help identify the most important aspects of your environment before you begin to configure a super metric.
VMware by Broadcom  4171

---
## page 4172

 VMware Cloud Foundation 9.0
Table 1185: Designing a Super Metric Checklist
Determine the objects that are involved in the behavior to track. When you define the metrics to use, you can select either specific
objects or object types. For example, you can select the specific
objects VM001 and VM002, or you can select the object type
virtual machine.
Determine the metrics to include in the super metric. If you are tracking the transfer of packets along a network, use
metrics that refer to packets in and packets out. In another
common use of super metrics, the metrics might be the average
CPU usage or average memory usage of the object type you
select.
Decide how to combine or compare the metrics. For example, to find the ratio of packets in to packets out, you
must divide the two metrics. If you are tracking CPU usage for an
object type, you might want to determine the average use. You
might also want to determine what the highest or lowest use is
for any object of that type. In more complex scenarios, you might
need a formula that uses constants or trigonometric functions.
Decide where to assign the super metric. You define the objects to track in the super metric, then assign
the super metric to the object type that contains the objects being
tracked. To monitor all the objects in a group, activate the super
metric in the policy, and apply the policy to the object group.
Determine the policy to which you add the super metric. After you create the super metric, you add it to a policy. For more
information, refer to Policy Workspace in VCF Operations.
What Else Can You Do with Super Metrics
• To see the super metrics in your environment, generate a system audit report. For more information, refer to System
Audit for VCF Operations.
• To create alert definitions to notify you of the performance of objects in your environment, define symptoms based on
super metrics. For more information, refer to Symptom Definitions in VCF Operations.
• Learn about the use of super metrics in policies. For more information, refer to Policy Workspace in VCF Operations.
• Use OPS CLI commands to import, export, configure, and delete super metrics. For more information, refer to the OPS
CLI documentation.
• To display metric-related widgets, create a custom set of metrics. You can configure one or more files that define
different sets of metrics for a particular adapter and object types. This ensures that the supported widgets are
populated based on the configured metrics and selected object type.
Create a Super Metric
Create a super metric when you want to check the health of your environment, but you cannot find a suitable metric to
perform the analysis.
1. From the left menu, click Infrastructure Operations > Configuration, and then click the Super Metrics tile.
2. Click Add .
The Create Super Metric wizard opens.
VMware by Broadcom  4172

---
## page 4173

 VMware Cloud Foundation 9.0
3. Optional: To edit a super metric, click the vertical ellipsis next to the super metric and select Edit. You can also edit the
super metric using the EDIT option in super metrics page.
4. Enter a meaningful name for the super metric such as Worst VM CPU Usage (%) in the Name text box.
Note:  It is important that you have an intuitive name as it appears in dashboards, alerts, and reports. For meaningful
names, always use space between words so that it is easier to read. Use title case for consistency with the out of the
box metrics and add the unit at the end.
5. Provide a brief summary of the super metric in the Description text box.
Note:  Information regarding the super metric, like why it was created and by whom can provide clarity and help you
track your super metrics with ease.
6. From the Object Types drop-down list, select the object to associate with the super metric and click Next.
7. Create the formula for the super metric.
For example, to add a super metric that captures the average CPU usage across all virtual machines in a cluster,
perform the following steps.
a) Select the function or operator. This selection helps combine the metric expression with operators and/or functions.
In the super metric editor, enter avg and select the avg function.
You can manually enter functions, operators, objects, object types, metrics, metrics types, property, and properties
types in the text box and use the suggestive text to complete your super metric formula.
Alternatively, select the function or operator from the Functions drop-down menu.
b) To create a metric expression, enter Virtual and select Virtual Machine  from the object type list.
c) Add the metric type, enter usage, and select the CPU|Usage (%) metric from the metric type list.
Note:  The expression ends with depth=1 by default. If the expression ends with depth=1, that means that the
metric is assigned to an object that is one level above virtual machines in the relationship chain. However, since
this super metric is for a cluster which is two levels above virtual machine in the relationship chain, change the
depth to 2.
The depth can also be negative, this happens when you need to aggregate the parents of a child object. For
example, when aggregating all the VMs in a datastore, the metric expression ends with depth=-1, because VM is
a parent object of datastore. But, if you want to aggregate all the VMs at a Datastore Cluster level, you need to
implement 2 super metrics. You cannot directly aggregate from VM to Datastore Cluster, because both are parents
of a datastore. For a super metric to be valid, depth cannot be 0 (-1+1=0). Hence, you need to create the first super
metric (with depth=-1) for the aggregate at the datastore level, and then build the second super metric based on
the first (with depth = 1).
The metric expression is created.
d) To calculate the average CPU usage of powered on virtual machines in a cluster, you can add the where clause.
Enter where=””.
Note:  The where clause cannot point to another object, but can point to a different metric in the same object. For
example, you cannot count the number of VMs in a cluster with the CPU contention metric > SLA of that cluster.
VMware by Broadcom  4173

---
## page 4174

 VMware Cloud Foundation 9.0
The phrase "SLA of that cluster " belongs to the cluster object, and not to the VM object. The right operand must
also be a number and cannot be another super metric or variable.
e) Position the pointer between the quotation marks, enter Virtual, and select the Virtual Machine object type and
the System|Powered ON metric type.
f) To add the numeric value for the metric, enter ==1.
g) To view hints and suggestions, click ctrl+space and select the objects, object types, metrics, metrics types,
property, and properties types to build your super metric formula.
h) Select This option from the drop-down menu.
If This option is selected during the creation of a metric expression, it means that the metric expression is
associated to the object for which the super metric is created.
8. Select the unit of the super metrics from the Unit drop-down.
Note:  The super metrics unit configured here can be changed in the metrics charts, widgets, and views.
9. Click Validate to verify that the super metric formula has been created correctly.
After you click the Preview button the system selects a random object and displays a metric graph showing values for
the current super metric. For example, if you have selected Host System in the Object Types tab, after you click the
Preview button it will randomly select a host system object from the list of the available objects and displays the graph
for the selected host. Alternatively, you can also type in the object name in the Object text box, and the result will also
depend on the pre-selected object type.
a) Expand the Preview section.
A metric graph is displayed showing values of the metric collected for the object. Verify that the graph shows
values over time.
b) Click Next.
The Policies page is displayed.
10. Select the policy which you want to associate with super metric and click Update.
The selected policy is applied to the super metric. You can view the super metric you created, the associated object
type, and policy on the Super Metrics page.
Enhancing Your Super Metrics
You can enhance your super metrics by using clauses and resource entry aliasing.
Where Clause
The where clause verifies whether a particular metric value can be used in the super metric. Use this clause to point to a
different metric of the same object, such as where=(${metric=metric_group|my_metric} > 0).
For example: count(${objecttype = ExampleAdapter, adaptertype = ExampleObject, metric =
ExampleGroup|Rating, depth=2, where =($value==1})
IsFresh Function
Use the isFresh function in the where clause to check if the last value of the metrics is fresh or not.
For every metric published in VCF Operations, the point with the latest publishing time is called as the last point of that
metric. The value of that metric’s last point is called the last value of that metric. A metric’s last point is considered fresh
when the time elapsed after the metric’s last point is lesser than the estimated publishing interval of that metric.
The  isFresh function returns true if the last value of the metrics is fresh. For example, in the following scenarios, the
function:
• ${this, metric=a|b, where=($value.isFresh())}, returns the last value of the metric a|b if the last value is
fresh.
VMware by Broadcom  4174

---
## page 4175

 VMware Cloud Foundation 9.0
• ${this, metric=a|b, where=($value == 7 && $value.isFresh())}, returns the last value of the metric
a|b if it is equal to seven and is fresh.
• ${this, metric=a|b, where=(${metric=c|d} == 7 && ${metric=c|d}.isFresh())}, returns the last
value of the metric a|b only if the last value of the metric c|d is equal to seven and is fresh.
Resource Entry Aliasing
Resource entries are used to retrieve metric data from VCF Operations for computing super metrics. A resource entry is
the part of an expression which begins with $ followed by a {..} block. When computing a super metric, you might
have to use the same resource entry multiple times. If you have to change your computation, you must change every
resource entry, which might lead to errors. You can use resource entry aliasing to rewrite the expression.
The following example, shows a resource entry that has been used twice.
(min(${adaptertype=VMWARE, objecttype=HostSystem, attribute= cpu|demand|
active_longterm_load, depth=5, where=($value>=0)}) + 0.0001)/(max(${adaptertype=VMWARE,
objecttype=HostSystem, attribute=cpu|demand|active_longterm_load, depth=5,
where=($value>=0)}) + 0.0001)"
The following example shows how to write the expressing using resource entry aliasing. The output of both expressions is
the same.
(min(${adaptertype=VMWARE, objecttype=HostSystem, attribute= cpu|demand|
active_longterm_load, depth=5, where=($value>=0)} as cpuload) + 0.0001)/(max(cpuload) +
0.0001)"
Follow these guidelines when you use resource entry aliasing:
• When you create an alias, make sure that after the resource entry you write as and then alias:name. For example:
${…} as alias_name.
• The alias cannot contain the ()[]+-*/%|&!=<>,.?:$ special characters, and cannot begin with a digit.
• An alias name, like all names in super metric expressions, is case-insensitive.
• Use of an alias name is optional. You can define the alias, and not use it in an expression.
• Each alias name can be used only once. For example: ${resource1,…} as r1 + ${resource2,…} as R1.
• You can specify multiple aliases for the same resource entry. For example: ${…} as a1 as a2.
Conditional Expression ?: Ternary Operators
You can use a ternary operator in an expression to run conditional expressions.
For example: expression_condition ? expression_if_true : expression_if_false.
The result of the conditional expression is converted to a number. If the value is not 0, then the condition is assumed as
true.
For example: -0.7 ? 10 : 20 equals 10. 2 + 2 / 2 - 3 ? 4 + 5 / 6 : 7 + 8 equals 15 (7 + 8).
Depending on the condition, either expression_if_true or expression_if_false is run, but not both of them.
In this way, you can write expressions such as, ${this, metric=cpu|demandmhz} as a != 0 ? 1/a : -1. A
ternary operator can contain other operators in all its expressions, including other ternary operators.
For example: !1 ? 2 ? 3 : 4 : 5 equals 5.
VMware by Broadcom  4175

---
## page 4176

 VMware Cloud Foundation 9.0
Exporting and Importing a Super Metric
You can export a super metric from one VCF Operations instance and import it to another VCF Operations instance. For
example, after developing a super metric in a test environment, you can export it from the test environment and import it
use in a production environment.
If the super metric to import contains a reference to an object that does not exist in the target instance, the import fails.
VCF Operations returns a brief error message and writes detailed information to the log file.
1. Export a super metric.
a) From the left menu, click Operations > Configuration, and then click the Super Metrics tile.
b) Select the super metric to export, click horizontal ellipsis and then click Export.
VCF Operations creates a super metric file, for example, SuperMetric.json.
c) Download the super metric file to your computer.
2. Import a super metric.
a) From the left menu, select Configure and then click Super Metrics.
b) Click the horizontal ellipsis and then click Import.
c) (Optional). If the target instance has a super metric with the same name as the super metric you are importing, you
can either overwrite the existing super metric or skip the import, which is the default.
Super Metrics Tab
A super metric is a mathematical formula that contains a combination of one or more metrics for one or more objects. With
super metrics you can assess information more quickly when you are observing fewer metrics.
Where You Configure Super Metrics
From the left menu, click Operations > Configuration, and then click the Super Metrics tile.
To view the details for a specific super metric, click the super metric from the list. The super metric details are displayed
in the right-side panel. The super metric details include the assigned object types, formula and policies activated for the
selected super metric.
Table 1186: Configuration Options for Super Metrics
Option Description
Toolbar Use the toolbar selections to manage super metric options.
• Add New Super Metric. Starts the Create Super Metric
workspace.
• Edit Selected Super Metric. Starts the Create Super Metric
workspace.
• Clone Selected Super Metric. Duplicates the super metric. Edit
the clone or associate it with a different object type.
• Delete Selected Super Metric.
• Export Selected Super Metric. Exports a super metric to use
in another VCF Operations instance. See Exporting and
Importing a Super Metric.
• Import Super Metric. Imports a super metric to this VCF
Operations instance. See Exporting and Importing a Super
Metric.
Super Metrics list Configured super metrics listed by name and formula description.
VMware by Broadcom  4176

---
## page 4177

 VMware Cloud Foundation 9.0
Enhancements to the Super Metric Functions
In the earlier implementation of aggregate functions in super metrics, you had to explicitly specify the Adapter Kind and
Resource Kind in the formula.
Old Formula
count(${adaptertype=VMWARE, objecttype=HostSystem,attribute=badge|health, depth=1})
The new implementation of aggregate function provides a way to define a super-metric without explicitly specifying the
Resource Kind. You can use "objecttype=*" in the super-metric formula which indicates you to consider all Resource Kinds
having the specified attribute.
New Formula
count(${adaptertype=VMWARE, objecttype=*,attribute=badge|health, depth=1})
Note:
The explicit specification of "adaptertype" remains mandatory. However, "*" can be used only to select all Resource Kinds
for the given Adapter Kind.
Manage Super Metric Workspace
You use the Manage Super Metric workspace to create or edit a super metric. The toolbar helps you to build the
mathematical formula with the objects and metrics you select.
Where You Configure Super Metrics
From the left menu, click Operations > Configuration, and then click the Super Metrics tile.
Table 1187: Super Metrics Workspace Options
Option Description
Super Metric • Name. The name you give to the super metric.
• Description. The textual description you give about the super
metric.
Object Types Pane Use this page to associate the super metric with an object type.
You can use this list to select the object type with the metrics
to measure. The object type selection affects the list of objects,
metrics, and attribute types displayed.
Formula Define the formula you want to associate with the super metric.
You can preview and validate the formula before you create it. Use
drop-down menu to select the metrics to add to the formula.
• Functions. Mathematical functions that operate on a single
object or group of objects. See Super Metric Functions and
Operators.
• Operators. Mathematical symbols to enclose or insert between
functions. See Enhancing Your Super Metrics.
• This Object. Assigns the super metric to the object selected in
the Object pane and displays this in the formula instead of a
long description for the object.
• Unformatted. Slide the toggle button to the right to view the
unformatted version of the formula, slide the button to the left
to view the formula in textual format.
VMware by Broadcom  4177

---
## page 4178

 VMware Cloud Foundation 9.0
Option Description
• Preview. Shows the super metric in a graph. Look at the graph
so that you can verify that VCF Operations is calculating the
super metric for the target objects that you selected.
Policies Displays the policies related to the object types you assigned your
super metric to.
Super Metric Functions and Operators
VCF Operations includes functions and operators that you can use in super metric formulas. The functions are either
looping functions or single functions.
Looping Functions
Looping functions work on more than one value.
Table 1188: Looping Functions
Function Description
avg Average of the collected values.
combine Combines all the values of the metrics of the included objects in a
single metric timeline.
count Number of values collected.
max Maximum value of the collected values.
min Minimum value of the collected values.
sum Total of the collected values.
Note:  VCF Operations 5.x included two sum functions: sum (expr) and sumN (expr, depth). VCF Operations 6.x
includes one sum function: sum (expr). Depth is set at depth=1 by default. For more information about setting depth,
refer to Create a Super Metric.
Looping Function Arguments
The looping function returns an attribute or metric value for an object or object type. An attribute is metadata that
describes the metric for the adapter to collect from the object. A metric is an instance of an attribute. The argument syntax
defines the desired result.
For example, CPU usage is an attribute of a virtual machine object. If a virtual machine has multiple CPUs, the CPU
usage for each CPU is a metric instance. If a virtual machine has one CPU, then the function for the attribute or the metric
return the same result.
Table 1189: Looping Function Formats
Argument syntax example Description
funct(${this, metric =a|b:optional_instance|c}) Returns a single data point of a particular metric for the object to which the
super metric is assigned. This super metric does not take values from the
children or parents of the object.
VMware by Broadcom  4178

---
## page 4179

 VMware Cloud Foundation 9.0
Argument syntax example Description
funct(${this, attribute=a|b:optional_instance|c}) Returns a set of data points for attributes of the object to which the super
metric is assigned. This super metric does not take values from the child or
parent of the object.
funct(${adaptertype=adaptkind,
objecttype=reskind, resourcename=resname,
identifiers={id1=val1id2=val2,…}, metric=a|b:instan
ce|c})
Returns a single data point of a particular metric for the resname specified
in the argument. This super metric does not take values from the children
or parents of the object.
funct(${adaptertype=adaptkind,
objecttype=reskind, resourcename=resname,
identifiers={id1=val1, id2=val2,…}, attribute=a|b:o
ptional_instance|c})
Returns a set of data points. This function iterates attributes of the
resname specified in the argument. This super metric does not take values
from the child or parent of the object.
funct(${adaptertype=adaptkind,
objecttype=reskind, depth=dep}, metric=a|b:option
al_instance|c})
Returns a set of data points. This function iterates metrics of the reskind
specified in the argument. This super metric takes values from the child
(depth > 0) or parent (depth < 0) objects, where depth describes the
object location in the relationship chain.
For example, a typical relationship chain includes a data center, cluster,
host, and virtual machines. The data center is at the top and the virtual
machines at the bottom. If the super metric is assigned to the cluster and
the function definition includes depth = 2, the super metric takes values
from the virtual machines. If the function definition includes depth = -1, the
super metric takes values from the data center.
funct(${adaptertype=adaptkind,
objecttype=reskind, depth=dep}, attribute=a|b:optio
nal_instance|c})
Returns a set of data points. This function iterates attributes of the
reskind specified in the argument. This super metric takes values from
the child (depth > 0) or parent (depth < 0) objects.
For example, avg(${adaptertype=VMWARE, objecttype=VirtualMachine, attribute=cpu|
usage_average, depth=1}) averages the value of all metric instances with the cpu|usage_average attribute for all
objects of type VirtualMachine that the vCenter adapter finds. VCF Operations searches for objects one level below the
object type where you assign the super metric.
Single Functions
Single functions work on only a single value or a single pair of values.
Table 1190: Single Functions
Function Format Description
abs abs(x) Absolute value of x. x can be any floating point number.
acos acos(x) Arccosine of x.
asin asin(x) Arcsine of x.
atan atan(x) Arctangent of x.
ceil ceil(x) The smallest integer that is greater than or equal to x.
cos cos(x) Cosine of x.
cosh cosh(x) Hyperbolic cosine of x.
exp exp(x) e raised to the power of x.
floor floor(x) The largest integer that is less than or equal to x.
VMware by Broadcom  4179

---
## page 4180

 VMware Cloud Foundation 9.0
Function Format Description
log log(x) Natural logarithm (base x) of x.
log10 log10(x) Common logarithm (base 10) of x.
pow pow(x,y) Raises x to the y power.
rand rand() Generates a pseudo random floating number greater than or equal to 0.0 and less than
1.0.
sin sin(x) Sine of x.
sinh sinh(x) Hyperbolic sine of x.
sqrt sqrt(x) Square root of x.
tan tan(x) Tangent of x.
tanh tanh(x) Hyperbolic tangent of x.
Operators
Operators are mathematical symbols and text to enclose or insert between functions.
Table 1191: Numeric Operators
Operators Description
+ Plus
- Subtract
* Multiply
/ Divide
% Modulo
== Equal
!= Not equal
< Less than
<= Less than, or equal
> Greater than
>= Greater than, or equal
|| Or
&& And
! Not
? : Ternary operator. If/then/else
For example: conditional_expression ?
expression_if_condition_is_true :
expression_if_condition_is_false
For more information about ternary operators, see Enhancing Your
Super Metrics.
( ) Parentheses
[ ] Use in an array of expressions
[x, y, z] An array containing x, y, z. For example, min([x, y, z])
VMware by Broadcom  4180