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
