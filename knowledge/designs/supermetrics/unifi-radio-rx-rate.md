# [VCF Content Factory] UniFi Radio RX Rate

- **Type:** supermetric
- **Slug:** unifi-radio-rx-rate
- **Authored YAML:** none (not expressible, see below)
- **Assigned to:** `unifi_controller` `UniFiRadio`
- **Date:** 2026-09-25
- **Status:** not authorable in the DSL; recorded so the gap is not rediscovered

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

- Turn the lifetime counter `Traffic|rx_bytes` on `UniFiRadio` into a current rate in bytes/s, so dashboards can show what the port, radio or uplink is doing now.
- Live recon 2026-09-25 (prod, `knowledge/context/investigations/recon_log.md`, UniFi/Synology live-data recon, item 1): the key is strictly non-decreasing over 6 h, a lifetime counter.

## Why this cannot be authored

The super metric DSL evaluates a formula against each object's current
values at each collection point. It has looping functions that
aggregate across related objects (`avg`, `sum`, `min`, `max`, `count`,
`combine`), scalar math, and `$value.isFresh()`, but no function that
reads an earlier sample, shifts a series in time, or divides by the
collection interval (`.claude/skills/vcfops-supermetric-dsl/SKILL.md`
§Functions; vendor list in `reference/docs/vcf9/supermetrics.md`,
Tables 1188 to 1190). A delta over time needs the previous sample, so a
rate cannot be expressed. Chaining super metrics does not help: each
still sees only current values.

## Fallback in the designs

Charts of `Traffic|rx_bytes` are relabelled "cumulative since device counter
reset" (not "since collection start": the value is the device's own
lifetime counter, which predates Ops collection and resets when the
device reboots or its counters clear). The slope of that line is the
rate; the value is never presented as current throughput. Widgets
changed: unifi-summary-radio S6.

## The real fix (for Scott to decide)

The UniFi controller already computes rates and exposes them as the
same field names with an `-r` suffix (the pack uses exactly that for
`UniFiWirelessAggregate` `Performance|tx_bytes_r` / `rx_bytes_r`).
An adapter change that emits the `-r` fields (per-radio rates in `stat.ap`, to be confirmed by the adapter author) would give a true
rate metric with no super metric at all. That is an sdk-adapter-author
task, filed as an issue, not a design here.
