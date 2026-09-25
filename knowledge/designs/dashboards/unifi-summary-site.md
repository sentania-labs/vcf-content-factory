# [VCF Content Factory] UniFi Site Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** unifi-summary-site
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-site.yaml
- **summary_for:** `unifi_controller:UniFiSite`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/unifi-summary-layout.md, section UniFi Site
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html (select Site)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- What is at this site and how it is doing: controller version and device count, clients per AP and PoE draw per switch over the week, and every device colored by health.
- Built from the shared UniFi Summary layout; layout variant for this kind: container: S3 dropped (a Site has no metrics), S5 and S6 are per-child MetricCharts (relationship_mode: children), S7 is a device Heatmap.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Configuration|device_count is a string property in describe.xml, so it displays but cannot be charted.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
