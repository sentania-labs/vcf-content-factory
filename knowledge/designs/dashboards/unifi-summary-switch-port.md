# [VCF Content Factory] UniFi Switch Port Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** unifi-summary-switch-port
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-switch-port.yaml
- **summary_for:** `unifi_controller:UniFiSwitchPort`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/unifi-summary-layout.md, section UniFi Switch Port
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html (select Switch Port)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- What is plugged in here and is the link clean: link state, PoE draw, error counters, and the neighbour (for ESXi uplinks, the host and vmnic from the stitch, which also shows as a parent in S8).
- Built from the shared UniFi Summary layout; layout variant for this kind: leaf: S7 is a PropertyList (PoE config and LLDP neighbour).
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Live recon 2026-09-25 (prod): Traffic|rx_bytes/tx_bytes are strictly non-decreasing lifetime counters and Traffic|rx_errors/tx_errors held flat at 1 and 2 for 6 h (lifetime counts). A rate or error-rate super metric is not expressible in the DSL, so: S5 is a cumulative sparkline labelled as such; the error tiles are labelled lifetime and uncolored; errors are off the charts (a flat lifetime line reads as a current rate). Rate SM intents record the gap (unifi-switch-port-*-rate). PoE|poe_voltage and PoE|poe_current are defaultMonitored=false; left out. Status|mac_table_count also defaultMonitored=false.
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
