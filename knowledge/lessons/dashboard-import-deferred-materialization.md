# Dashboard imports are DEFERRED — don't visually verify before materialization

**Date:** 2026-07-22
**Trigger:** DEF-014 / DEF-015 (both closed as false alarms after two
investigation rounds and a failed "remediation").

## The lesson

A content-import of a dashboard lands in a **deferred** state:
`getDashboardList.isLoading == true` and `getWidgetConfigs` returns a
skeleton (bare widget-type titles, no `viewDefinitionId`, no metric
config). In this state the UI renders every widget as **"The widget is
not configured. Select a view to render."** / "Heatmap is not
configured." — indistinguishable from a genuinely broken dashboard.

Materialization to full config (`isLoading:false` + complete
`getWidgetConfigs`) happens on **first UI open** or via a **background
job (~20 min observed on devel)** — whichever comes first. An import
verified too early looks broken; the same dashboard re-checked after
the window renders perfectly.

## What this cost us

A Playwright pass that raced the window produced DEF-014 ("view binding
lost"), a plausible-but-wrong stale-binding theory, a delete+reimport
"remediation" that re-entered the deferred window and "reproduced" the
symptom, and DEF-015 ("all widgets broken" — same race on a dashboard
that had just been re-synced). Two investigation rounds refuted it:
server-side config was correct and complete the whole time.

## The rules

1. **After any dashboard import/sync, do not visually verify until
   materialization is confirmed.** Check the server-side health signal:
   `getDashboardList.isLoading == false` AND `getWidgetConfigs` returns
   full (non-skeleton) config for every widget. Both are on the
   `POST /ui/dashboard.action` surface (see
   `knowledge/context/investigations/def014-view-binding-loss-2026-07-22.md` ROUND 2).
2. **"Not configured" right after an import is expected**, not a
   defect. Re-check after opening the dashboard once and/or waiting out
   the background job before filing anything.
3. **A dashboard stuck `isLoading:true` long after import** (hours+) is
   the genuine failure mode — e.g. the legacy MSSQL/Oracle Query
   Performance dashboards on devel (see FB-015 family). Triage those,
   not freshly-imported ones.
4. Installer/qa procedure: sync → confirm materialization → then
   Playwright.

## Addendum 2026-10-13: the pak installer's Summary binding loses the same race

A pak `dashboards.properties` binding clones the imported dashboard into a
SUMMARY template seconds after import, while every widget is still in the
deferred state. On devel 9.0.2 (compliance build 89) the clone was taken at
9:10:17 AM and the source's settings were filled in at 9:12:31 AM. The
background thread only walks user-owned dashboards, so the ownerless clone
never materializes: the Summary tab renders stock badges, empty views and
an unfiltered alert list, with an hourglass on every title. The candidate
fix is to bind after the source is materialized (`bind-summary`); it has not
been run on 9.0.2, Scott rejected a factory post-install rebind as the answer
("if we install a pack it shoudl bind the summary dashboards", stake:
`knowledge/context/investigations/2026-10-13-summary-dashboard-parked.md`),
and the #200 branch is parked at CHANGES REQUESTED. If pursued, the install
flow must wait for `isLoading == false` on every widget before binding.
Details: `knowledge/context/investigations/2026-10-13-compliance-summary-clone-config-loss.md`.
