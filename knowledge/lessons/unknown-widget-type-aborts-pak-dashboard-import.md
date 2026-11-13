# An unknown widget type silently loses dashboards, by pak install and by content import

Date: 2026-10-12 and 2026-10-13. Compliance adapter builds 88 and 89, devel
(VCF Operations 9.0.2.0 build 25137845). Factory issue #199. Extended
2026-11-13 to 8.18.7 and the content-import path (below).

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

## Measured again on 2026-11-13: both versions, both paths

`knowledge/context/investigations/2026-11-13-section-widget-on-8x-and-90.md`,
on 8.18.7 (build 25423534) and 9.0.2 (build 25431135). The two builds have
the same 47 widget types and the same importer bug; the Section dashboard is
never created, not even partly, on either path.

- **Content import** (`/api/content/operations/import`: `vcfcf_dashboards
  sync`, bundle sync, bundle install): the importer handles the owner's
  dashboards in one call, so one Section dashboard loses **every** dashboard
  in the same import, whatever the order (one owner per import measured;
  every factory import has one owner). The task reports FINISHED,
  `errorCode: NONE`, DASHBOARDS `total N, imported 0, skipped 0, failed 0`,
  no message. The factory's old "imported nothing" check needed
  `skipped > 0` and did not fire.
- **Pak install**: the installer imports each `content/dashboards/<dir>`
  separately, so the loss is the directory holding the Section dashboard;
  the rest of the pak installs, and the install still reports FINISHED and
  verified. Every repeat install gives the same result.
- **FINISHED is unreliable on both paths.** The only trace is
  `JSONObject["Title"] not found` in `vcops-bridge.log` (and, for a content
  import, `restoreData failed to import Dashboards` in `view-bridge.log`).
  In the import envelope the one signature is that the three counters do
  not add up to `total`.

## Lesson

- A dashboard (pak or content bundle) must use only widget types the
  **oldest targeted Ops version** can import. The complete list, the same
  on 8.18.7 and 9.0.2, is in
  `knowledge/context/api-surface/summary_dashboard_pak_binding.md`;
  `Section` is the only renderer type missing from it. Adding a type needs
  proof on that oldest version, not on the newest.
- Never put a dashboard that may meet an older build in the same content
  import as dashboards that must land: it takes them all with it.
- Read the import envelope's counters, not just its state: on a FINISHED
  task, `imported + skipped + failed < total` for DASHBOARDS is a failure.
  For other types `total` has not been checked against a healthy import,
  so the factory only warns there. The check runs on every content-import
  path (`vcfcf_dashboards.client.import_count_findings`, pinned copies in
  both installer templates).
- Measured vs unmeasured: Section fails on 8.18.7 and 9.0.2 (measured) and
  imports on 9.1.1 and 9.2 (proven); 9.1.0 is unmeasured. So the factory
  refuses below 9.1.0 and only warns on 9.1.0.
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
- Guards: the compliance adapter's `tests/test_dashboard_widget_types.py`
  allowlists the eight types in use. In the factory, a Tier 2 pak build
  fails on a Section dashboard below 9.1.1 (RULE-019's oldest line).
  Content bundles declare no minimum version, so validate only warns; the
  live paths (`vcfcf_dashboards sync`, the dashboards handler, bundle sync,
  `install.py` and `install.ps1`) read the instance version and refuse
  before importing below 9.1.0, or warn on 9.1.0, naming the dashboards;
  every content-import reader fails on a DASHBOARDS count shortfall.

## The way out for Section (2026-11-13)

A dashboard that is complete without its Section header rows does not need
a second, hand-maintained copy: set `section_fallback: omit` on it and keep
the Sections in the committed YAML. Tier 2 pak builds and live sync then
ship it without the Sections wherever the target is below 9.1.1 (pak: the
oldest supported line; sync: the instance version, or when it cannot be
read), and with them from 9.1.1, so the same source ships the Section
version once 8.x and 9.0 leave the supported lines. Every omission is
printed with the dashboard, the count and the version reason; nothing is
dropped silently. Content bundles still declare no target, so their
installers still refuse. Reference:
`knowledge/context/wire-formats/dashboard_fidelity_wire_format.md`
§Section fallback.
