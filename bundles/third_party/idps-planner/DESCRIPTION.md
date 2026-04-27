# IDPS Planner

A VCF Operations dashboard for monitoring vDefend IDPS (Intrusion Detection
and Prevention System) resource consumption — designed specifically for
administrators running IDPS in **Classic Mode** to proactively track traffic
thresholds that trigger the IDPS Bypass feature.

## Purpose

By tracking Packets Per Second (PPS) and Throughput across your vDefend
environment, this dashboard surfaces hosts and VMs approaching performance
limits, ensuring security inspection coverage stays consistent and
effective.

## Key Performance Indicators

- **Classic Mode PPS** — identifies entities approaching 140k PPS.
- **Turbo Mode Throughput** — identifies entities approaching 9 Gbps.

> **Note on sampling.** When these thresholds are exceeded, the IDPS bypass
> mechanism may begin sampling traffic on the affected host to maintain
> system stability. Bypass behaviour applies on ESXi 8.0u3e or later with
> NSX 4.2.1 or later.

## Metric Definitions

Metrics use **peak values rather than averages** for a conservative,
safety-first view.

### 5-Minute Peak (Current)

- **Definition.** The highest value recorded for each VM during the most
  recent 5-minute collection interval.
- **Aggregation.** Sums per-host across VMs.
- **Observation.** Because per-VM peaks may occur at different seconds
  within the 5-minute window, the "Current" value is a high-water mark and
  may overstate simultaneous utilization.

### Period Peak

- **Definition.** The absolute highest traffic spike recorded for a host
  over the entire dashboard timeframe (e.g. last 24 hours or 7 days).
- **Use case.** Identifying bursty workloads that intermittently trigger
  bypass mode.

### 95th Percentile

- **Definition.** Statistical measure representing the 95th percentile of
  all peak values recorded for a given host over the dashboard timeframe.
- **Purpose.** Accounts for the fact that not all VM peaks occur
  simultaneously; filters out one-off outliers to provide a more realistic
  "sustained heavy load" figure for capacity planning.

## Authors

- Ryan Pletka
- Brock Peterson
- Joe Tietz
- Geoff Shukin
- Scott Bowe

## License

MIT.

## Provenance

Extracted from a live VCF Operations lab via the [VCF Content Factory](https://github.com/sentania-labs/vcf-content-factory)
extractor. The factory's value-add is the **install / uninstall automation**
and **dependency walking** — the bundle ships with scripts that import the
dashboard, sync its dependent views and super metrics, and enable any
required built-in metrics that aren't on by default. Original authors
retain all rights to the dashboard's design, queries, and view layout.
