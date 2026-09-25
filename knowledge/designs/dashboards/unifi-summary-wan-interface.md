# [VCF Content Factory] UniFi WAN Interface Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** unifi-summary-wan-interface
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-wan-interface.yaml
- **summary_for:** `unifi_controller:UniFiWanInterface`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/unifi-summary-layout.md, section UniFi WAN Interface
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html (select WAN Interface)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Is this uplink up and fast: latency and availability over the week, addressing, and traffic.
- Built from the shared UniFi Summary layout; layout variant for this kind: leaf: S7 dropped (no keys left; Health|speed is defaultMonitored=false), S8 widens to 12.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: Live recon 2026-09-25 (prod): Traffic|rx_bytes and Traffic|tx_bytes are lifetime counters, strictly non-decreasing over 6 h, despite describe.xml unit bytes/s (a label bug). A rate super metric is not expressible in the DSL (no previous-sample function), so S6 is a cumulative sparkline labelled as such: the slope is the rate, the value is not current throughput. Real fix: adapter emits the UniFi -r rate fields (see supermetric intent unifi-wan-rx-rate).
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
