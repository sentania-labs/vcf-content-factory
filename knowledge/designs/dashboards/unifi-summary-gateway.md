# [VCF Content Factory] UniFi Gateway Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** unifi-summary-gateway
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-gateway.yaml
- **summary_for:** `unifi_controller:UniFiGateway`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/unifi-summary-layout.md, section UniFi Gateway
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html (select Gateway)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Is the gateway healthy and is the internet link good: load, temperature, clients, speed test history, and both WAN uplinks.
- Built from the shared UniFi Summary layout; layout variant for this kind: standard.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Temperature|temp_phy is defaultMonitored=false; left out.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
