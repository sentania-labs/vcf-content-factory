# [VCF Content Factory] UniFi Camera Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** unifi-summary-camera
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-camera.yaml
- **summary_for:** `unifi_controller:UniFiCamera`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/unifi-summary-layout.md, section UniFi Camera
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html (select Camera)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Is the camera connected and recording, and has it been restarting: state flags first, then hardware, uptime history and parent NVR.
- Built from the shared UniFi Summary layout; layout variant for this kind: leaf: S3 carries one tile, S6 dropped (Status|last_motion is defaultMonitored=false) so S5 widens to 12, S7 is a PropertyList (network and radio).
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Camera is property-heavy: Status|uptime is its only default-monitored metric.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
