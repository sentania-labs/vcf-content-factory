# Design: vSAN Performance Service Disabled on Cluster (alert)

- **Type:** alert
- **Slug:** vsanperf-performance-service-disabled
- **Authored YAML:** content/sdk-adapters/vsanperf/alerts/vsanperf_performance_service_disabled.yaml, content/sdk-adapters/vsanperf/recommendations/vsanperf_enable_performance_service.yaml
- **Date:** 2026-11-08
- **Status:** authored (pak 1.2.1 build 24, merged 2026-11-08; installed on devel 9.0.2)

## Initial prompt

> User: If the performance service is disabled we should cleanly skip it and
> there should be an alert

## Vision

- One symptom: `[VCF Content Factory] vSAN Performance Service Disabled`
  (knowledge/designs/symptoms/vsanperf-performance-service-disabled.md).
- Target VMWARE `ClusterComputeResource`. Criticality Warning: nothing in the
  workload breaks. Impact Risk: lost monitoring is future exposure, not a
  current health fault (design `vsanperf-mp-v3.md` § 1.2.1 content table,
  alert row).
- As authored (build 24): alert `[VCF Content Factory] vSAN Performance
  Service disabled on cluster (vSAN Perf collection paused)`, type 18
  (Storage), subType 22 (Configuration), wait 1 / cancel 1 (the symptom
  carries the 2-cycle debounce); recommendation `[VCF Content Factory] vSAN
  Enable Performance Service`, priority 1, embedded in the alert XML.
- Auto-cancel when the symptom clears (the key returns to 1 within one cycle
  of re-enabling).
- Recommendation: enable the Performance Service under Cluster > Configure >
  vSAN > Services > Performance Service. The VCF Content Factory vSAN
  Performance pak collects nothing for this cluster until it is on; the
  built-in vSAN health check "vSAN Performance Service is not enabled" covers
  the same state on the vSAN MP's own cluster object.
- Ships inside the pak (adapter.yaml `bundled_content`), like the synology
  and unifi paks' symptom/alert sets.
