# [VCF Content Factory] Synology World Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** synology-summary-world
- **Authored YAML:** content/sdk-adapters/synology/dashboards/synology-summary-world.yaml
- **summary_for:** `synology_diskstation:SynologyWorld`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/synology-summary-layout.md, section Synology World
- **Mock:** knowledge/designs/dashboards/synology-summary-layout.html (select World)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Every NAS under this adapter at a glance: temperature and memory per DiskStation over the week, and the DiskStation list.
- Built from the shared Synology Summary layout; layout variant for this kind: container: S1 is a TextDisplay (the World carries no keys), S3 dropped, S5 and S6 are per-child MetricCharts over DiskStations.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Only platform keys on the World itself.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
