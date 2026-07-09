# Design: Compliance Score Degraded Alert

## Initial prompt

"Author aggregate alerts: Symptom/alert YAML for 95%/80% compliance score thresholds on VMWARE/HostSystem."

## Vision

- Alert combines both compliance score symptoms (Warning at <95%, Critical at <80%).
- Targets VMWARE HostSystem resources with stitched VCF-CF compliance data.
- Impact: Risk — non-compliant hosts violate security benchmarks.
- Criticality: Symptom-based (warning vs critical depends on which symptom fires).
- Auto-cancel: Yes — alert clears when all symptoms resolve.
- Recommendation: Check the VCF-CF Compliance properties on the host to identify
  which specific controls are failing. Review the compliance dashboard for details.
  Consider remediating settings identified in the per-control Actual vs Expected
  property values.
