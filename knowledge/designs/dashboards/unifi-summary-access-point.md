# [VCF Content Factory] UniFi Access Point Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** unifi-summary-access-point
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-access-point.yaml
- **summary_for:** `unifi_controller:UniFiAccessPoint`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/unifi-summary-layout.md, section UniFi Access Point
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html (select Access Point)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- How the AP is serving clients: client count and satisfaction over the week, load, and each radio's channel, utilization and retries.
- Built from the shared UniFi Summary layout; layout variant for this kind: standard.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Satisfaction is lower-is-worse and ships uncolored (#176).
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
