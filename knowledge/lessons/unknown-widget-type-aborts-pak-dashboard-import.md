# An unknown widget type aborts the whole pak dashboard import, silently

Date: 2026-10-12 and 2026-10-13. Compliance adapter builds 88 and 89, devel
(VCF Operations 9.0.2.0 build 25137845). Factory issue #199.

## What happened

Build 88 shipped the Compliance World Summary dashboard with a full-width
`Section` header row and a `dashboards.properties` binding to the
ComplianceWorld Summary tab. The install reported FINISHED and verified,
the other four pak dashboards re-imported, and the Summary tab stayed
stock. Nothing on the install path said why.

The 9.0.x dashboard importer has no `Section` widget type (47 types on
9.0.2; `Section` arrived in 9.1). On an unknown type it tries to log a
skip message with capitalised JSON keys the dashboard does not carry, that
log call throws `JSONObject["Title"] not found`, and the whole dashboard
import aborts. No share, no Summary binding, no install error. The mock
had been proven on a 9.2 instance and a 9.1 devel build in August; devel
had since been rebuilt at 9.0.2 and nobody re-read the version.

Build 89 removed the Section row and the dashboard imported and bound.

## Lesson

- A pak dashboard must use only widget types the **oldest targeted Ops
  version** can import. The complete 9.0.2 list is in
  `knowledge/context/api-surface/summary_dashboard_pak_binding.md`;
  `Section` is the only renderer type missing from it. Adding a type to a
  pak needs proof on that oldest version, not on the newest.
- After every pak install, count the pak's dashboards on the instance
  (same discipline as `new-metric-alerts-need-two-samples.md`) and, for a
  bound Summary dashboard, read `getSummaryTabId` for the kind and then
  `getDashboardConfig?isTemplate=true` for that tab id: the binding existing
  proves nothing about the clone, which on 9.0.2 is blank (`isLoading: true`
  on every widget) because the installer clones before materialization
  (`dashboard-import-deferred-materialization.md`, 2026-10-13 addendum). A
  FINISHED install proves nothing about dashboards.
- Re-read the target's build number at the start of a session that
  installs content. Context notes about an instance's version go stale
  when the lab is rebuilt.
- Guard: the compliance adapter's `tests/test_dashboard_widget_types.py`
  allowlists the eight types in use; the factory validator guard is
  issue #199.
