# [VCF Content Factory] UniFi Switch Summary

- **Type:** dashboard (summary dashboard, bundled in the pak)
- **Slug:** unifi-summary-switch
- **Authored YAML:** content/sdk-adapters/unifi/dashboards/unifi-summary-switch.yaml
- **summary_for:** `unifi_controller:UniFiSwitch`
- **Date:** 2026-09-25
- **Status:** drafted; mock awaiting Scott's approval
- **Layout and wireframe:** knowledge/designs/dashboards/unifi-summary-layout.md, section UniFi Switch
- **Mock:** knowledge/designs/dashboards/unifi-summary-layout.html (select Switch)

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

## Vision

- Is the switch healthy and is PoE close to its budget: PoE draw against budget over the week, load and satisfaction, and every port with its link, PoE draw, errors and LLDP neighbour.
- Built from the shared UniFi Summary layout; layout variant for this kind: standard.
- Every widget inherits the Summary page object; no pickers, no interactions.

## Notes

- Key notes: PoE budget used % is a planned super metric (knowledge/designs/supermetrics/unifi-switch-poe-budget-used-pct.md, purple key), colored orange >= 80, red >= 90. Watt tiles stay uncolored: absolute watts mean different things on a 52 W and a 400 W switch. PoE|poe_budget_remaining moved off the tiles (lower-is-worse, #176; the % covers it).
- The wireframe table for this kind lives in the layout note so all kinds can be compared in one place; it is the author's source of truth.
