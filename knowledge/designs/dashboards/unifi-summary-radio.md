# [VCF Content Factory] UniFi Radio Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** unifi-summary-radio
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-radio.yaml
- **summary_for:** `unifi_controller:UniFiRadio`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/unifi-summary-layout.md, section UniFi Radio
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html (select Radio)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Is this radio congested: channel utilization, retries and satisfaction over the week, clients, and whether the channel or power changed.
- Built from the shared UniFi Summary layout; layout variant for this kind: leaf: S7 is a third MetricChart (channel and power history), since no properties are left over.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Live recon 2026-09-25 (prod): Traffic|tx_bytes/rx_bytes are lifetime counters (non-decreasing over 6 h). Labelled cumulative in S6; a rate SM is not expressible (unifi-radio-*-rate intents record the gap).
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
