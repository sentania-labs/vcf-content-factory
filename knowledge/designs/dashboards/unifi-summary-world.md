# [VCF Content Factory] UniFi World Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** unifi-summary-world
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-world.yaml
- **summary_for:** `unifi_controller:UniFiWorld`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/unifi-summary-layout.md, section UniFi World
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html (select World)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- One look at every UniFi device under this controller, colored by health, with the alerts that explain any red.
- Built from the shared UniFi Summary layout; layout variant for this kind: container: S1 is a TextDisplay (the World carries no keys), S3 dropped, S5 and S6 dropped (its children, Sites, carry no metrics), S7 is a device-health Heatmap.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Only platform keys (badge|health, System Attributes|*). The Synology World shows NO_DATA_RECEIVING and grey health in the v1 baseline for the same reason; expect the same here.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
