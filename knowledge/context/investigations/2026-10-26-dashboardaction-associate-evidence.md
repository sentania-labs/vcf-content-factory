# DashboardAction.associateResourceKindDashboards: evidence for #260 (W4)

- **Date:** 2026-10-26, America/Chicago.
- **Instances:** devel (9.0.2.0 Build 25429562), devel_8_18 (8.18.6 Build 25423535), devel_9_1 (9.1.1 Build 25794169; `lastbuildversion.txt` reads 9.0.0.0).
- **Method:** read-only. SSH as root: `sha256sum` on the appliance, `scp` of three files off it, `javap -c -p -l` (JDK 17.0.20.1) locally. Nothing written on the appliances; no Ops UI or API call. devel's SSH host key had been rotated on purpose (confirmed by Scott); the new key was accepted on first connect.
- **Why:** framework review of #260, finding W4. The factory's retry between the two request forms of `associateResourceKindDashboards` rests on three claims about the server action; the 2026-10-24 investigation (`2026-10-24-devel-summary-rebind-500-and-alertlist-gap.md`) had not kept the text it read.

## Where the verbatim text is

**Local-only artifact; not reproducible from a clone (RULE-015).** The `javap` dumps and the UI source excerpts are Broadcom material and stay out of this public repo. They are on the lab holding share at `/mnt/holding/vcf-content-factory/evidence/dashboardaction-associate/<build>/`, one folder per build (`8.18.6-25423535`, `9.0.2-25429562`, `9.1.1-25794169`), each with `sha256sums.txt`, `javap-associateResourceKindDashboards.txt` (the method's block, cut at its boundaries only), the SPA lines from `useDefaultAssociation` through `save()`, the bundle line or fragment, and `original/` (the copied class, JS files and full `javap` output). The findings are summarized here in full so the citation is not needed to follow them; anyone with an appliance of the same build can re-derive them from the source paths below.

Source paths on each appliance:

- `/usr/lib/vmware-vcops/tomcat-web-app/webapps/ui/WEB-INF/classes/com/vmware/vcops/ui/action/DashboardAction.class`
- `/usr/lib/vmware-vcops/tomcat-web-app/webapps/ui/js/dashboard/DashboardAssociateWindow.js`
- the bundle carrying the same class: `dist/js/app.part0.js` (8.18.6), `dist/js/app.part6.min.js` (9.0.2, 9.1.1)

## Hashes

| Build | `DashboardAction.class` sha256 | `DashboardAssociateWindow.js` sha256 |
|---|---|---|
| 8.18.6 Build 25423535 | `597eed20f2d43dd4ce7d29372d8d49cbde2c02c6ee145b9815dd0f85a01ab4d3` | `398800ba4af7270ca4158d64e15a7b52856d2abbcb476f196d7b49566be61f67` |
| 9.0.2.0 Build 25429562 | `2c9c838b294d1bd659bac1c3b7c36c2fb4f1d86190a940b70b31221a96e51d67` | `398800ba4af7270ca4158d64e15a7b52856d2abbcb476f196d7b49566be61f67` |
| 9.1.1 Build 25794169 | `8de8af93beae843e6cdb10e0c89d74f4e1fef5215f5e0cd631932f4fa8d3daed` | `c023d2ea7faa6714942e05c00b2483de0e1ef09813b8a92e5fe2690f3ea51a35` |

Bundles: 8.18.6 `app.part0.js` `3505680fc98756757f115f71734b3b8e9deb8de40688a106f50b45e8ab73676e`; 9.0.2 `app.part6.min.js` `ac76e245014d36b8db965ccd4161802f22e89c8092794b48315791fb10d2703f`; 9.1.1 `app.part6.min.js` `677804af2765503aa042b04d482965e4dc40d1f0a7c18ca41351b2c75a74fd82`.

Each class hash equals the truncated value recorded on 2026-10-24, so the bytes read then are the bytes read now. The 8.18.6 and 9.0.2 `DashboardAssociateWindow.js` are byte-identical.

## The method, per build

**8.18.6 and 9.0.2 are the same method.** Diffed opcode by opcode: every instruction and offset is identical; only constant-pool indexes and source line numbers differ (9.0.2 runs 29 lines later: offset 93, the `new JSONObject`, is line 2578 on 8.18.6 and line 2607 on 9.0.2, the line in each build's 2026-10-24 stack trace). The offsets below therefore hold for both. The method has no private helper for parsing or merging; both are inline. Its only own-class call is the static lookup `getDashboardDTO`.

| Offset | 8.18.6 / 9.0.2 |
|---|---|
| 0 to 5 | `monitorenter` on static `lockObj` |
| 16 | `dataRetriever.getGlobalValue(DashboardAssociationMap, "associationMap")` (read) |
| 31 to 79 | `associationMap = dto.getAssociationMap()`; a new empty `HashMap` only when none is stored |
| 86 | `request.getParameter("dashboardAssociations")` |
| 99 | `new JSONObject(<that string>)` (NPE when the parameter is absent) |
| 142 to 188 | per key: split the value on `_::_` into `templateName` and `tabId`; strip the key to after the first `_` |
| 194 | `tabIdPrevious = associationMap.get(kind)` |
| 204 to 225 | `tabId` null, empty or `"null"` goes to 435 |
| 262 | `getDashboardDTO(userId or null for an OOTB id, [tabId])`; null or no tabs: entry skipped |
| 311 | `saveDashboardAsTemplate(tabId, templateName, SUMMARY, userId)`: **first write** |
| 383 | `associationMap.put(kind, templateTabId)` |
| 410 | `deleteDashboardTemplate(tabIdPrevious)` when it differs: the only delete |
| 439 | reset path: `associationMap.remove(kind)`, nothing else |
| 469 | audit `DASHBOARD_ASSOCIATE` |
| 489 | `putGlobalValue("associationMap", new DashboardAssociationMap(associationMap))`: whole map written back |

| Offset | 9.1.1 |
|---|---|
| 12 | `dataRetriever.getDashboardAssociationMap()` (read) |
| 92 | `request.getParameter("assignedAssociations")` |
| 106 | `request.getParameter("resetAssociations")` |
| 119 | `new JSONObject(assigned)` (NPE when absent; line 2074) |
| 224 to 245 | `tabId` null, empty or `"null"` goes to 457 |
| 333 | `saveDashboardAsTemplate(tabId, templateName, SUMMARY, userId, true)`: first write |
| 405 / 432 | `put`; `deleteDashboardTemplate(tabIdPrevious)` when it differs |
| 465 to 473 | reset-in-assigned: `associationMapToRemove.put(kind, associationMap.remove(kind))` |
| 482 to 492 | `resetAssociations` null or empty: skipped (no NPE) |
| 544 to 560 | reset value: `tabId = value.substring(value.indexOf("_::_") + 4)` (no `_::_` gives `substring(3)`) |
| 596 to 653 | `deleteDashboardTemplate(tabIdPrevious)` only when `tabId` is a non-OOTB id **equal to** the stored one |
| 667 to 675 | `associationMapToRemove.put(kind, associationMap.remove(kind))` |
| 730 | `setDashboardAssociation(associationMap, associationMapToRemove)` |

## SPA request (`save()`)

- 8.18.6 and 9.0.2: `params: {mainAction: 'associateResourceKindDashboards', dashboardAssociations: Ext.encode(this.updatedAssociations)}`. `updateAssociation` stores `templateName + "_::_" + tabId`. "Use Default" passes the kind's `defaultTemplateId` as `tabId`: null (so `_::_null`, the reset path) when the kind has no default of its own; the default id (the bind path, offset 228 on) when it has one.
- 9.1.1: `params:{mainAction:"associateResourceKindDashboards",assignedAssociations:Ext.encode(this.assignedAssociations),resetAssociations:Ext.encode(this.resetAssociations)}`. Binds go in `assignedAssociations` as `` `${name}_::_${tabId}` ``; "Use Default" puts the plain template name, no `_::_`, in `resetAssociations`.

## The three claims

**(a) A request missing the parameter for its form fails before any write. Holds on all three builds.** 8.18.6 and 9.0.2: offsets 0 to 79 take the lock and read the stored map; 86 reads `dashboardAssociations`; 99 throws on null. The first write is at 311. 9.1.1: 92 reads `assignedAssociations`, 119 throws on null, first write at 333; a missing `resetAssociations` alone does not throw (482). **Limit:** the factory's fallback keys on "HTTP 200 plus the error panel", and that panel is rendered for any exception in the action. A two-map call that throws later in its loop (after a `saveDashboardAsTemplate`) gives the same answer. The single-map retry that follows still throws at 99 or 119 and writes nothing, so the retry is safe; "error panel" alone does not prove the first call wrote nothing.

**(b) A single-map entry merges into the existing association map. Holds (8.18.6 and 9.0.2).** The stored map is read whole (16, 31 to 79), changed only for the keys in the request (383 put, 439 remove) and written back whole (489). Other kinds' bindings survive a one-kind call. It is read-modify-write under a JVM-local lock; two UI nodes writing at once could still race. 9.1.1 has the same shape (12, 405, 730).

**(c) A `_::_null` reset keeps the template. Holds (8.18.6 and 9.0.2), in this sense:** the value goes to 435, where `associationMap.remove(kind)` (439) is the only action for that entry before the map is written back (489); the one `deleteDashboardTemplate` (410) is on the bind path. The kind's binding is removed, so its Summary tab falls back; the template copy stays in the template namespace, orphaned and readable only by UUID.

## Correction this surfaced (9.1.1)

`summary_dashboard_assignment.md` said a reset through `resetAssociations` deletes the copy when the reset value's id matches. The action does that only for a value `<name>_::_<id>` whose id equals the stored one (596 to 653). The SPA and the factory send the plain template name, for which that delete never fires; the entry moves to the "to remove" map handed to `setDashboardAssociation` (730), whose server-side handling is not in this class and was not checked. So the factory's `--unbind` on 9.1.1 is not shown to delete the copy.

A second, smaller difference: on 8.18.6 and 9.0.2 the SPA's "Use Default" on a kind that has its own default template sends `<name>_::_<defaultTemplateId>` (bind to that template); the factory always sends `<name>_::_null` (remove the entry). Whether the two render the same page for such a kind was not checked.

## Clean-up

Nothing created on the appliances or in Ops. Local copies in the session scratchpad and on the holding share only. devel_8_18's and devel's ED25519 host keys were added to the workstation's `known_hosts`.
