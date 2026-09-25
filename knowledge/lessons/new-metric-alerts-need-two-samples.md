# Alerts on a new metric key need two samples; pak installs can lose a dashboard

Date: 2026-09-23. Compliance adapter v3, build 67, devel (Ops 9.0.1).

## What happened

Two false alarms in one install, both from checking too early.

1. **"No per-control alerts fire."** At 12:47 PM, one hour after install,
   ops-recon found zero of the 144 new per-control alerts active, while
   hosts plainly read `Compliant = 0`. The definitions, keys, operator
   and policy were all fine. The profile-free keys were new in v3, and
   a symptom on a newly created pushed metric key skips that key's first
   sample. The adapter collects hourly, so the first sample landed at
   11:46 AM and the second at 12:47 PM; symptoms went active at 12:47
   and alerts at 12:49 to 12:52 PM. By 12:53 PM there were 336 active
   per-control alerts. The long-standing `unreadable_count` key fired on
   its first post-install sample; the new `collection_failed` key waited
   for its second, same as the per-control keys.
2. **"A dashboard failed to install."** The pak install reported
   `FINISHED`, no errors, but one of four dashboards was missing. It had
   been created and then lost about 5 seconds later, most likely when
   Ops's own background pass that finishes wiring imported dashboards
   wrote back a stale copy of the store (no delete was logged). Content
   was ruled out: the same file, re-imported alone, was created and
   survived the next pass.

## Lesson

- **Do not call "no alerts" a finding until the key has two samples.**
  After a fresh install or any build that adds a pushed key, wait two
  adapter collections plus about 5 minutes. Check in order: the stat
  history has at least 2 samples, the symptom is active, then about 5
  minutes later the alert is active. Only a symptom that is active with
  no alert one analytics cycle later is a real alert-side problem.
- **After every pak install, count the pak's dashboards on the instance.**
  `FINISHED` with no errors cannot catch a dashboard lost after the
  importer recorded success. Compare the pak's `content/dashboards/`
  against `getDashboardList`, and re-import any missing one alone (with
  its views in the same load set). Two dashboards that show
  `isLoading: true` for minutes are normal (phase 2 materialization);
  one that is absent is not.

Evidence: `knowledge/context/api-surface/compliance_per_control_alert_first_sample_lag.md`,
`knowledge/context/api-surface/pak_dashboard_import_race.md`,
`knowledge/context/api-surface/dashboard_import_two_phase_materialization.md`.

## Addendum (same day, build 69): renaming a pak dashboard orphans the old one

Pak installs import bundled dashboards with `ForceByID: false,
ForceByName: true` (devel audit log, 2:12 PM CDT). Matching is by name,
so renaming a dashboard in the pak ("Compliance ESXi Hosts" to
"Compliance ESX Hosts", same id in the YAML) created a new record under
a new id and left the old-named one live beside it. Any instance that
already has the old name keeps a stale copy after upgrade. Before
renaming a shipped dashboard, plan its removal on installed instances
(a delete, which needs the owner's go) and say so in the release notes.
