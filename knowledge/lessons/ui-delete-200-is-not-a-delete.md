# A UI-session delete that returns 200 is not a delete

Date: 2026-11-18. VCF Operations 9.1.1. Records:
`knowledge/context/investigations/2026-11-18-dashboard-import-by-name-and-delete-noop.md`
(the migration run) and
`knowledge/context/investigations/dashboard_delete_non_owner_2026-11-18.md`
(the follow-up that separated owner from lock).

## What happened

`vcfcf_dashboards delete-dashboard` posted `mainAction=deleteTab`, checked
only `raise_for_status()`, and printed "done". The session was another
administrator account; the 22 targets (both copies of 11 dashboards) were
listed as owned by the built-in admin account, `locked: true`, `edit:
false`. The server answered HTTP 200 and deleted none of them. The CLI
exited 0, and the re-import that followed added a third copy of each of the
11 dashboards (dashboard import is keyed by name).

The follow-up measured why: only the owner's `deleteTab` deletes. A
non-owner's, the built-in admin account's included, is a 200 no-op; the lock
is not the cause (`locked` is per-viewer and means "someone else owns this
and shared it with you"). Every factory-synced dashboard is owned by the
built-in admin account, whichever account synced it. The repo had recorded
a `deleteTab` no-op in 2026-04 and blamed the lock; the client was written
as if the status code said otherwise.

## Lesson

A UI `.action` or Ext.Direct call answering 200 says the request was
parsed, not that it took effect. After any delete through the UI session:

- re-list and confirm each id is gone, with a listing that raises on an
  answer it cannot read (an empty list read from a broken answer would
  "prove" every delete), and distrust an after-listing that lost objects you
  did not target;
- report per id and exit non-zero when any remains or cannot be verified;
- delete by id: a name can match several copies;
- compare the listed owner with the session user (`/api/auth/currentuser`)
  before the call, and name the difference as the cause when an id
  survives (9.1.1; 8.18.7 and 9.0.2 not measured);
- know the re-list's blind spot: when two owners hold one id, each account
  lists only the other's copy, so deleting your own copy looks like
  nothing happened. That errs safe (never "deleted" for a survivor); a
  `DASHBOARDS` export or a listing as the owner settles it.

`delete-dashboard`, `cleanup-legacy-prefix --apply` and the dashboards
bundle-uninstall handler now do this
(`VCFOpsUIClient.delete_dashboards_verified`). The distribution installer
template (`src/vcfcf_packaging/templates/install.py`) is not yet verified:
it still reports a dashboard deleted on the 200. A non-owner removal path
exists (`discardDashboards`) and is documented, not implemented.
