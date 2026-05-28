# Design: Compliance Score Critical Symptom

## Initial prompt

"Author aggregate alerts: Symptom/alert YAML for 95%/80% compliance score thresholds on VMWARE/HostSystem."

## Vision

- Symptom fires when a VMWARE HostSystem's VCF-CF compliance score drops below 80%.
- This is the Critical tier — host is significantly non-compliant and needs immediate attention.
- Metric is `VCF-CF Compliance|score` pushed via ARIA_OPS stitching from the vcfcf_compliance adapter.
- Target: adapterKind=VMWARE, resourceKind=HostSystem.
- Static threshold (HT), below which is abnormal.
- Wait cycle: 1.
- Cancel cycle: 1.
