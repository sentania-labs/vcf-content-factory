# Dashboard delete by a non-owner Administrator: measured on 9.1.1

Run 2026-11-18, about 12:40 to 13:12 America/Chicago, on a lab instance
(VCF Operations 9.1.1.0 Build 25795063). Two accounts: **the built-in admin account**, and
**a second administrator account** (a local user created for this run with the
Administrator role, all objects). The only probe was a one-widget TextDisplay dashboard,
`[VCF CF] ZZ Delete Probe`. Everything created was deleted afterwards (§Cleanup).

> **Unsupported endpoints.** Every request below goes to the Struts UI layer
> (`/ui/*.action`), not the Suite API. Neither OpenAPI spec documents these endpoints, and
> they can change between releases without notice. They use the UI cookie session plus
> the `secureToken` form field described in `../api-surface/dashboard_delete_api.md`. The
> `X-Ops-API-use-unsupported` header does not apply to them. It only matters for Suite
> API `/internal/` calls, and none of those can delete a dashboard (Q3d).

## Answer

**`deleteTab` deletes only the session account's own copy of a dashboard. Ownership
decides this, not the lock.** `locked` in `getDashboardList` is a per-viewer flag. It means
"another account owns this and has shared it with you". An owner never sees its own
dashboard as locked. The built-in admin account gets no exception: as a non-owner, its
`deleteTab` is the same HTTP 200 no-op.

The product does have an administrator path that removes another account's dashboard
without unlocking it or taking it over. It is the Orphaned Content "Discard" action, and
the server does not check that the dashboard is actually orphaned:

```
POST /ui/dashboardShare.action
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
Cookie: JSESSIONID=<redacted>

mainAction=discardDashboards
tabsToDelete={"<ownerId>":["<dashboard id>", ...]}
secureToken=<redacted>
```

- `<ownerId>` is the `ownerId` field of the dashboard's `getDashboardList` entry (the owner's
  user UUID, not the name). `tabsToDelete` is a JSON object, keyed by owner id, of arrays
  of dashboard ids.
- Success response: HTTP 200, `text/html`, **empty body**.
- With the wrong owner key, the response is also HTTP 200 with an empty body, and nothing
  is deleted. The response cannot tell success from failure. **Verify by re-listing.**
- It worked three times on separate probes, the third time with the owner id read from
  the listing (the recipe in Q4).

## Q1. Who owns a dashboard imported by the second administrator, and why

The probe was imported as the second administrator with the factory's own code path:
`get_current_user`, `discover_marker_filename`, `build_import_zip`, `import_content_zip`.
`DASHBOARDS imported=1 skipped=0 failed=0`.

| Listed by | owner | ownerId | locked | edit | editable | shared |
|---|---|---|---|---|---|---|
| built-in admin | admin | built-in admin's id | false | true | false | true |
| second administrator | admin | built-in admin's id | **true** | **false** | false | false |

This reproduces the observed listing exactly (`owner: admin, locked: True, edit: False,
editable: False, shared: False`), and shows that `locked`, `edit` and `shared` depend on
who is viewing.

**What decides the owner: the marker file's content.** The factory zip writes the
importing user's id both into the `<digits>L.v1` marker and as the `userId` of the one
`usermappings.json` entry. When the marker content equals an owner's `userId`, 9.1.1 maps
that owner to the target's built-in admin, whatever the `userName`. This is path 1 of
`2026-11-11-owner-mapping-dashboard-skip-reproduction.md` (measured there on 9.0.2),
confirmed here on 9.1.1. Control run: the same zip with only the marker content changed to
an unrelated UUID. That import was owned by the **second administrator** (`owner` its
user name, `ownerId` its own id; locked false and edit true for itself, locked true for
the built-in admin). Without the marker match, the owner maps by `userName`.

So a factory sync always stamps the built-in admin as owner, from any account. That is
because `build_import_zip` uses the same id for the marker and for the usermapping. It is
not an importer default.

## Q2. The factory `deleteTab` as the second administrator

The request was byte-identical to `VCFOpsUIClient.delete_dashboards`:
`POST /ui/dashboard.action`, `mainAction=deleteTab`,
`tabIds=[{"tabId":"<id>","tabName":"[VCF CF] ZZ Delete Probe"}]`,
`currentComponentInfo=TODO`, `globalDate={"dateRange":"last6Hour"}`, `secureToken`.

- **Nothing was deleted, on every attempt** (re-listed by both accounts).
- Two response shapes were seen:
  - The first two calls came from the brand-new account before it had ever opened the
    UI. Both answered HTTP 200 `text/html` with the generic Struts error panel
    (`<msgBegin>Internal Server Error</msgBegin>`), with and without
    `X-Requested-With: XMLHttpRequest`. `delete_dashboards` would raise on these when it
    calls `resp.json()`.
  - Every later non-owner call answered HTTP 200 `application/json` with the full
    dashboard config, the same body an owner's successful delete returns. Those later
    calls came after that account had used the browser UI, and they included cases with
    `edit: false` and with `edit: true`. This is the observed "200 and deleted nothing"
    signature. Run against an admin-owned probe, the factory's
    `delete_dashboards_verified` returned `deleted=[]` and `remaining=[<probe>]`, which is
    correct.
- What makes the first calls error instead of no-op was not isolated. It lines up with the
  account's first use, not with `edit` (see Q3a).

## Q3. Separating the variables (each tested alone, on a fresh admin-owned probe)

The Manage page (Operate > Dashboards > Manage) was driven in headless Chrome over CDP.
The browser got its session from a `/ui` `JSESSIONID` cookie created by a scripted login
(steps 1 and 2 only). It then loaded `/ui/index.action` itself and followed the redirect
into `/vcf-operations/ui/`. Injecting all three cookies of a completed scripted login does
**not** hold on 9.1.1: the SPA's `getUserBaseInfo` hangs, then the SPA calls `logout`.
Injecting only the `/ui` `JSESSIONID` and letting the browser bootstrap works. The page
renders the legacy Ext app in a same-origin iframe (`/vcf-operations/plug/ops/index.action`).
The grid's code was read live from `Ext.vcops.dashboard.DashboardConfig`.

**What the Manage page allows** (row action menu, as the second administrator, on the
admin-owned probe): Edit, Delete and Change Ownership are **disabled**. Clone, Deactivate
and Export are enabled. The menu's enable rules, verbatim from the live class:

- Delete: `!isGettingStartedTab(id) && (!e.locked || e.edit)`
- Change Ownership: `!isGettingStartedTab(id) && !e.locked`
- Edit: `(!e.locked || e.edit) && !e.disabled`
- `isSharedTabSelected()` is true when any selected row has `locked`. The toolbar
  Delete and Change Owner buttons refuse with `notAllowedToManageSharedTabs` in that case.

So the product UI never offers a non-owner administrator a delete or ownership change on a
dashboard shared to it.

| Test | Request | Response | Deleted? |
|---|---|---|---|
| (a) unlock by owner | built-in admin: `dashboardShare.action` `mainAction=saveUserGroupDashboards` `sharedDashboards=[{"userGroupId":"<Everyone>","isGroup":true,"dashboardsAssigned":[{"id":"<id>","edit":true}],"dashboardsUnassigned":[]}]` | 200, empty body. Built-in admin's `groupIds` changed from `edit:false` to `edit:true`. The second administrator then listed `locked:true, edit:true` | then second admin `deleteTab`: 200 JSON config, **no** |
| (a') unlock by non-owner | the same request from the second administrator | 200, empty body, no change | n/a |
| (b) change owner, non-owner | `dashboardShare.action` `mainAction=changeOwner` `dashboardIds=<id>` (repeated param) `userIdTarget=<second admin id>` | 200 `notOk` | **no** (owner unchanged) |
| (b) change owner, owner (control) | the same request from the built-in admin | 200 `ok` | the original is replaced by a copy owned by the second admin, with a **new id** and the name `... 1` |
| (b') take ownership (Orphaned Content) | second admin: `dashboardShare.action` `mainAction=reassignDashboards` `userId=<second admin id>` `tabsToReassign={"<owner id>":["<id>"]}` | 200 `ok` | the original is gone, replaced by a copy owned by the second admin, with a **new id** and the name `... 1`. That copy can then be deleted with `deleteTab` |
| (c) Manage-page delete | captured from a real click (row menu > Delete > Yes), owner session: `dashboard.action` `mainAction=reportsByDashboard&dashboardId=<id>` then `mainAction=deleteTab&tabIds=[{"tabId":"<id>","tabName":"<name>"}]` | 200 `[]`, then 200 JSON config | yes (owner) |
| (c') Orphaned Content discard | second admin: `dashboardShare.action` `mainAction=discardDashboards` `tabsToDelete={"<owner id>":["<id>"]}` | 200, empty body | **yes** |
| (d) Suite API | `operations-api.json`, `internal-api.json` and their `-9.1` variants: the only dashboard mention is `/api/content/operations/import`. Live, with `X-Ops-API-use-unsupported: true`: GET `/api/dashboards`, `/internal/dashboards`, `/internal/content/dashboards` 404; DELETE on `/api/dashboards/{id}`, `/internal/dashboards/{id}`, `/api/content/dashboards/{id}`, `/internal/content/dashboards/{id}` 405 | | no endpoint exists |

Notes:

- **(c) is not a different action.** The Manage page sends the same `deleteTab` as the
  factory and as the dashboard view's own menu. Its only addition is the
  `reportsByDashboard` pre-check, which picks the confirmation dialog.
- **The built-in admin account is not special.** On a dashboard owned by the second
  administrator, the built-in admin listed `locked:true` (`edit` true or false, following
  the share). Its `deleteTab` was a 200-JSON no-op.
- **Reverse test: the owner deletes a dashboard that others see as locked.** The second
  administrator owned the probe and shared it with Everyone with `edit:false`, so the
  built-in admin listed it as `locked:true, edit:false`. The owner's `deleteTab` then
  deleted it (both listings confirmed). An owner never lists its own dashboard as locked,
  so "owner deletes a locked dashboard" has no other meaning on 9.1.1. The lock does not
  block the owner. Not being the owner blocks everyone else.
- **`getOrphanedDashboards` returned `[]`** while the admin-owned probe existed. The probe
  was not orphaned, and `reassignDashboards` and `discardDashboards` acted on it anyway.
- **This corrects the 2026-04-10 section of `dashboard_delete_api.md`.** Its claim
  "`deleteTab` on a locked dashboard is a silent no-op" was really "on a dashboard someone
  else owns". Its claim "no delete path for admin-owned locked dashboards from non-admin
  user" is wrong for an Administrator-role session on 9.1.1, because `discardDashboards`
  works.

## Q4. Minimal reliable sequence for a non-owner Administrator session

1. `getDashboardList` (strict). For each target, take its `id` and `ownerId`.
2. Group the targets by `ownerId`. Send one
   `POST /ui/dashboardShare.action` with `mainAction=discardDashboards`,
   `tabsToDelete={"<ownerId>":["<id>",...], ...}` and `secureToken`.
   Expect HTTP 200 with an empty body.
3. Verify with `getDashboardList` again. Each target id must be absent. Where it
   matters, also re-list as the owner, or check a `DASHBOARDS` content export, which groups
   records by owner (see Q5 for why one account's listing can hide a second record).

Measured result: the probe was gone from both accounts' listings, both counts went back to
their baselines (232 and 222), and the export held no probe record under any owner.

**Do not** use `changeOwner` or `reassignDashboards` as a delete step. Both re-create the
dashboard under a new id with a ` 1` name suffix. That breaks the factory's UUID contract
(RULE-007) and leaves a renamed copy behind if the follow-up delete fails.

## Q5. Re-import when another owner already holds the same id

Confirmed in both directions, using the factory's fixed dashboard id:

- The second administrator owns the probe, and the factory zip (mapped to the built-in
  admin) is imported: `imported=1`.
- The built-in admin owns the probe, and a zip mapped to the second administrator (marker
  mismatch) is imported: `imported=1`.

In both cases a `DASHBOARDS` export then showed **two records with the same id**, one in
`dashboards/<built-in admin id>` and one in `dashboards/<second admin id>`. Each account's
`getDashboardList` showed exactly one entry for that id: **the other account's copy**,
listed `locked:true`. The import replaces in place only when the mapped owner already owns
that id. Importing the factory zip as the second administrator while the built-in admin
owned the probe replaced it in place, leaving one record.

A trap in this state: the built-in admin's `deleteTab` removed **its own** copy, but its
listing still showed that id, because the other copy now filled the slot. An id-only
verify reports this as `remaining`, although something was deleted. A combined
`discardDashboards` (keyed by each `ownerId`) plus a re-list as each owner clears it. Here,
`discardDashboards` removed the built-in admin's copy and the owner's `deleteTab` removed
the other.

## Not measured

- Other releases (8.18, 9.0). Everything above is 9.1.1 only.
- Whether `discardDashboards` needs the Administrator role or a specific privilege (only an
  Administrator with all objects was tested). Also its batch behavior across several owners
  in one call, and whether it cleans the home page and favourites references that the UI's
  delete path removes client-side.
- Why the fresh account's first `deleteTab` calls answered the error panel instead of JSON.
- Dashboards owned by directory (LDAP or SSO) users, and dashboards referenced by reports
  (`reportsByDashboard` non-empty).

## Cleanup

All probe dashboards were deleted, including the `... 1` copies from `changeOwner` and
`reassignDashboards` and both same-id duplicates. Final state: built-in admin listing 232
(the baseline), no probe by name, an export with no probe record under any owner, and
`getOrphanedDashboards` returning `[]`. The second administrator account was deleted
(`DELETE /api/auth/users/{id}` returned 204, and the user list is back to its baseline).
The browser session was logged out and Chrome stopped. Every scripted UI session called
`logout`. Suite API tokens were not explicitly released; the second account's tokens died
with the account, and the built-in admin's expire on their TTL. The test password file and
the cookie files were deleted.
