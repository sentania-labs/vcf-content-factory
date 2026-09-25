# [VCF Content Factory] UniFi Switch PoE Budget Used (%)

- **Type:** supermetric
- **Slug:** unifi-switch-poe-budget-used-pct
- **Authored YAML:** content/supermetrics/unifi-switch-poe-budget-used-pct.yaml, or bundled under content/sdk-adapters/unifi/ if #173 lands that way
- **Assigned to:** `unifi_controller` `UniFiSwitch`
- **Date:** 2026-09-25
- **Status:** drafted; waits on Scott's approval of the UniFi mocks

## Initial prompt

Scott, 2026-09-25 (verbatim):

> Dashboards and summary object dashboards for Unifi and SYnology MPs. We should include a couple of useful dashboards for general use for both. Also like are experimentating witht he VMSP object summary - all objects for both packs should have summary dashboards

On the summary layout (verbatim):

> I'd say one shared layout, as long as it provided meaningful information about the object.

On the general dashboards (verbatim):

> OK, let me know when the mocks are ready

Coordinator brief, 2026-09-25 (verbatim, relevant part), relaying the live-data recon:

> UniFi SwitchPort, Radio, WanInterface `Traffic|tx_bytes`/`rx_bytes` and SwitchPort `tx_errors`/`rx_errors` are lifetime counters (monotonic over 6h). Never show them as current throughput or error rate. Propose rate super metrics (delta over time) for port/radio/WAN throughput and port errors: write one intent file per proposed SM under knowledge/designs/supermetrics/ (check the vcfops-supermetric-dsl skill for whether a rate/delta is expressible; if it is not, fall back to a cumulative sparkline relabelled "since collection start" and say so). Update every widget and view column that used them. Keep the PoE budget % SM too (open question 5), as an intent file.

## Vision

- One number per switch: how much of its PoE budget is in use, in percent, so every switch can be colored on one scale (orange >= 80, red >= 90). Watts alone cannot: 200 W is fine on a 400 W switch and impossible on a 52 W one.
- Used by: `unifi-summary-switch` S3 (first tile), the `UniFi Switches` view (PoE used % column), `unifi-switching-poe` W2 (one line per switch) and W6.
- Switches without PoE report `PoE|total_max_power` = 0 (UniFiAdapter.java reads the controller's `total_max_power`, 0 when absent, and derives `Configuration|poe_capable` from it being > 0). The SM must return nothing or 0 for them, never divide by zero.

## Notes

- Inputs (both on `UniFiSwitch`, both default-monitored, `content/sdk-adapters/unifi/describe.xml`): `PoE|poe_consumption` (W), `PoE|total_max_power` (W).
- Proposed shape for the author (numeric only, no string where clauses):
  `${this, metric=PoE|total_max_power} > 0 ? ${this, metric=PoE|poe_consumption} / ${this, metric=PoE|total_max_power} * 100 : 0`.
  The author owns the final formula and validation. If a 0 for non-PoE switches misleads the W2 chart, filter those switches out of the widget instead.
- Recon 2026-09-25: no UniFi super metrics exist on the instance or in the repo.
- Unit: percent. Must be enabled in the default policy for `UniFiSwitch` before the dashboards that use it are installed.
