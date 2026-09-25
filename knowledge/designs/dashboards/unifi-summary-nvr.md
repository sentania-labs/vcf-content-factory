# [VCF Content Factory] UniFi NVR Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** unifi-summary-nvr
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-nvr.yaml
- **summary_for:** `unifi_controller:UniFiNvr`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/unifi-summary-layout.md, section UniFi NVR
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html (select NVR)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Is recording storage healthy: how full the NVR is and how fast it is filling, restarts, and every camera's connected and recording state.
- Built from the shared UniFi Summary layout; layout variant for this kind: standard.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Protect NVRs run near-full by design (automatic retention overwrites oldest footage), so Storage used % is colored orange >= 90 and red >= 98, not the usual 80/90.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
