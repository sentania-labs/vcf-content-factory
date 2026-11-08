# Design: vSAN Performance Service Disabled (symptom)

- **Type:** symptom
- **Slug:** vsanperf-performance-service-disabled
- **Authored YAML:** content/sdk-adapters/vsanperf/symptoms/vsanperf_performance_service_disabled.yaml
- **Date:** 2026-11-08
- **Status:** authored (pak 1.2.1 build 24, merged 2026-11-08; installed on devel 9.0.2)

## Initial prompt

> User: If the performance service is disabled we should cleanly skip it and
> there should be an alert

## Vision

- Metric symptom on VMWARE `ClusterComputeResource`, key
  `vSAN Perf|Performance Service|enabled` (0/1, pushed every cycle by the
  vsanperf pak from 1.2.1 on every in-scope cluster, design
  `knowledge/designs/vsanperf-mp-v3.md` § 1.2.1 D4).
- Condition: value below 1 (`< 1`). Wait 2 cycles, cancel 1 (design § 1.2.1 content table, symptom row). A
  metric symptom clears on the next 1; a property symptom would hold its last
  value, which is why the key is a metric.
- Criticality Warning.
- Recon 2026-11-08: the built-in vSAN MP has
  `SymptomDefinition-perfsvc.perfsvcstatus.*` (fault symptoms on
  `VirtualSANDCCluster`, health-check cadence, needs that MP); nothing exists
  on the vCenter cluster object. Name must not read as a duplicate of the
  built-in.
