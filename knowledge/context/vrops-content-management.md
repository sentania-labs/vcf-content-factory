# vROps Content Management and the Suite-API


---
## page 1

Home
Brock Peterson·Dec 28, 2021
vROps Content Management and the Suite-API
Updated: Sep 6, 2025
Through the years, vROps has gotten quite good with its ability to manage content, things like exporting and 
importing dashboards, reports, and views, among others.  I've always done this via the standard user 
interface (UI), but it can also be done via the vROps Suite-API.  We'll explore both options here.
vROps 8.2 introduced the ability to export/import content via the UI, it can be found in Administration - 
Management - Content Management.
This gave us the ability to export important vROps constructs as backups or use in other environments.  With 
this first release it was an all or nothing proposition, you could export everything or nothing.  
In the latest release, vROps 8.6, you now have the ability to export/import just what you want.
Post
4/7/26, 3:27 PM vROps Content Management and the Suite-API
https://www.brockpeterson.com/post/vrops-content-management-and-the-suite-api 1/24

---
## page 2

As you can see, each vROps construct now has a check box, including out of the box content and 
configuration items like Users, User Groups, and more.  I did an Export All which took about 10 minutes in my 
lab, the export of dashboards only took about three minutes.  
Once complete, you can download the ZIP file created by the export by clicking this link.
If you'd prefer to use the vROps Suite-API, there are endpoints for Content Management.  Documentation 
can be found at: https://your_vrops_fqdn/suite-api/doc/swagger-ui.html.  Formal vROps Suite-API 
documentation can be found here.  
4/7/26, 3:27 PM vROps Content Management and the Suite-API
https://www.brockpeterson.com/post/vrops-content-management-and-the-suite-api 2/24

---
## page 3

As indicated, you can use any HTTP Client to access the vROps Suite-API, but the two most common REST 
Clients are:
cURL - http://curl.haxx.se 
Postman - http://www.getpostman.com 
If I'm doing something quickly I'll use cURL, but for most everything else I use Postman.  It has a rich UI with 
many publicly available collections found out on VMware {code}.  The best one I've found is from VMware 
Senior Staff Technical Marketing Manager John Dias, get it here. 
As referenced above, there are five endpoints for Content Management:
GET /api/content/operations/export - get the last export details
POST /api/content/operations/export - export content for current user
GET /api/content/operations/export/zip - download latest export
GET /api/content/operations/import - get the last import details
POST /api/content/operations/import - import content for current user
If I want to export content and download the exported content (ZIP file), I'll be using the second and third 
calls from the list, but first I need to authenticate.  There are several different ways to do this, but the easiest 
are Basic Authentication or Token Based Authentication.  To enable Basic Authentication on your vROps 
Cluster see this KB, it's pretty easy.
The process to acquire an Authentication Token can be found here.  In practice, using Postman, it looks like 
this:
4/7/26, 3:27 PM vROps Content Management and the Suite-API
https://www.brockpeterson.com/post/vrops-content-management-and-the-suite-api 3/24

---
## page 4

The credentials you are using are up top, after clicking Send, you will be presented with a token down below. 
 This is the token you will use for your subsequent calls and will be valid until the expiresAt date.
Next, you'll call the POST /api/content/operations/export to export content you want.  In my case, I'd like to 
export the dashboards for the user I authenticated as, local admin.  This export took roughly 10 minutes in my 
lab and looks like this.
Notice in the body of the call I've configured a custom scope for just dashboards.
4/7/26, 3:27 PM vROps Content Management and the Suite-API
https://www.brockpeterson.com/post/vrops-content-management-and-the-suite-api 4/24

---
## page 5

This can be adjusted to include whatever you might want: Views, Reports, Outbound Settings, Integrations, 
etc.  It would look like this:
Once complete, you can get the ZIP file via the GET /api/content/operations/export/zip, it looks like this:
Once done, click the Save Response and Save to a file to save the ZIP file.
4/7/26, 3:27 PM vROps Content Management and the Suite-API
https://www.brockpeterson.com/post/vrops-content-management-and-the-suite-api 5/24

---
## page 6

vROps
You will then be prompted to save the file, you now have your backup!
The vROps Suite-API is so powerful, it's Swagger-based documentation has become so rich, this is just one 
use-case.  I encourage you to explore others and post your collections to VMware {code}.
4/7/26, 3:27 PM vROps Content Management and the Suite-API
https://www.brockpeterson.com/post/vrops-content-management-and-the-suite-api 6/24