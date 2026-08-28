# dashboard-widgets

Verbatim Suite API / appliance extracts backing
`knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md`
and `knowledge/context/wire-formats/dashboard_section_gauge_viewdetails.md`.

- `qa-9.2.0-export-alertvolume-section-viewdetails.json`: content export
  (`POST /api/content/operations/export`, scope ALL, `DASHBOARDS`) of three
  dashboards from a 9.2.0.0 instance, filtered to those exercising Alert
  Volume, Section, and a populated `viewDetails`. The export came from a
  pre-GA 9.2.0.0 lab build, so the two product dashboards ("Environment
  Health Summary", "License Server Health") may differ from their 9.2 GA
  form. **Reduction:** four widgets (two `Section`, two `TextDisplay`) were
  removed from the built-in "vRealize Operations/VCF Operations Health"
  dashboard before this file was added because they describe unreleased
  product features; the `userId` / `lastUpdateUserId` values on each
  dashboard were zeroed (instance-local lab user ids, no wire-format
  value). Nothing else in the file was altered; the remaining ten widgets
  of that dashboard (including the `viewDetails`-bearing "License Server"
  Scoreboard and the "VCF Operations Platform" Section) are verbatim.
- `vendor-template-Home.json`, `vendor-template-ComputeOps-dashboard.json`:
  Broadcom dashboard templates shipped on the appliance under
  `webapps/ui/dashboards/templates/`, verbatim.
