# Design: Compliance Score Warning Symptom

## Initial prompt

"Author aggregate alerts: Symptom/alert YAML for 95%/80% compliance score thresholds on VMWARE/HostSystem."

## Vision

- Symptom fires when a VMWARE HostSystem's VCF-CF compliance score drops below 95%.
- This is the Warning tier — environment is drifting from baseline but not yet critical.
- Metric is `VCF-CF Compliance|score` pushed via ARIA_OPS stitching from the vcfcf_compliance adapter.
- Target: adapterKind=VMWARE, resourceKind=HostSystem.
- Static threshold (HT), below which is abnormal.
- Wait cycle: 1 (fire on first breach — compliance drift is actionable immediately).
- Cancel cycle: 1 (auto-clear when score recovers above 95).
