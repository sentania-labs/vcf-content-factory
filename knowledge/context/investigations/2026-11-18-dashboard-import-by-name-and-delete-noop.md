# Dashboard import keyed by name, and a UI delete that answered 200 and deleted nothing (2026-11-17/18)

Observed during the live `[VCF Content Factory] ` to `[VCF CF] ` prefix
migration on VCF Operations **8.18.7, 9.0.2 and 9.1.1** (one instance each).
Accounts are named only by role: "the built-in admin account" and "another
administrator account" (an Administrator-role user that is not the built-in
one).

## 1. A content-zip import of a renamed dashboard adds a second dashboard

- State before: a dashboard named `[VCF Content Factory] <title>` installed
  under the repo UUID.
- Action: `vcfcf_dashboards sync` of the migrated YAML: same repo UUID, name
  `[VCF CF] <title>`.
- Result, on all three versions, 18 dashboards across the three instances:
  a **second** dashboard named `[VCF CF] <title>` under a server-assigned
  id. The old-named dashboard stayed and kept the repo UUID.

So for dashboards the content-zip import is keyed by name: with no dashboard
of the new name present, it created one, and it did not rename the dashboard
holding the id. (Consistent with vcfops-api skill gotcha 8, which records the
other direction: same name, new UUID, replaces.)

## 2. Delete both copies, then import again: the repo UUID returns

- Action: delete the old-named copy and the new-named copy, confirm neither
  is listed, then import the dashboard again.
- Result: the dashboard came back under the repo UUID with the new name.
- Proven first on one dashboard, then on 17 more, on 8.18.7, 9.0.2 and
  9.1.1.

## 3. A delete that answered success and removed nothing (9.1.1)

- Session: another administrator account. All target dashboards listed as
  owned by the built-in admin account.
- Request: `vcfcf_dashboards delete-dashboard` with 22 targets (both copies
  of 11 dashboards): one `POST /ui/dashboard.action`, `mainAction=deleteTab`,
  the shape in `api-surface/dashboard_delete_api.md` §Dashboard delete.
- Response: HTTP 200. The CLI (before this fix) printed `done` and exited 0.
- Listing after: all 22 still listed. None was deleted.
- A following re-import then added a **third** copy of each of the 11
  dashboards (import keyed by name, section 1).
- Every copy, including those created by the other administrator account's
  own import, was listed with `owner` the built-in admin account. Explained
  by the follow-up run (`dashboard_delete_non_owner_2026-11-18.md` Q1): the
  factory zip's marker matches the importing user's mapping, which 9.1.1
  maps to the built-in admin account.

## 4. `getDashboardList` fields in the two cases (9.1.1)

| Case | Session | `owner` | `locked` | `edit` | `editable` | `shared` | Delete |
|---|---|---|---|---|---|---|---|
| Worked | the built-in admin account | the built-in admin account | `False` | `True` | `False` | `True` | deleted |
| Silent no-op | another administrator account | the built-in admin account | `True` | `False` | `False` | `False` | 200, nothing deleted |

The no-op listing was the same for copies the import had just created and for
older ones.

What this run did and did not separate (the follow-up run,
`dashboard_delete_non_owner_2026-11-18.md`, then separated them on 9.1.1:
ownership decides and the lock does not; `locked`, `edit` and `shared` are
per-viewer):

- Owner mismatch and `locked: true` were **both present** in the failing case
  and **both absent** in the working case. They were not separated.
- Whether an owner can delete a dashboard listed `locked: true` was not
  measured in this run.
- `editable` was `False` in both cases, so on 9.1.1 it does not say whether
  the session owns the dashboard; `edit` tracked the owner in these two
  cases. Which field names 8.18.7 and 9.0.2 carry was not recorded.
- The same `deleteTab` request deleted dashboards on 8.18.7, 9.0.2 and 9.1.1
  when the session was the listed owner.

## What changed in the factory

- `delete-dashboard`, `cleanup-legacy-prefix --apply` and the dashboards
  bundle-uninstall handler re-list after the delete (strict listing) and
  report each id deleted, still listed, or not verified.
- `cleanup-legacy-prefix` reports these dashboards as RESYNC and prints the
  section 2 remedy: `authoring/prefix_migration.md` §The RESYNC dashboard
  states.
- Not changed: the distribution installer template
  (`src/vcfcf_packaging/templates/install.py`) still treats the delete's 200
  as success; follow-up issue.
- Lesson: `knowledge/lessons/ui-delete-200-is-not-a-delete.md`.
