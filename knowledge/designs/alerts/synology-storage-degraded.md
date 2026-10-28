# Design: Synology Storage Degraded (alert)

## Initial prompt

Scott, 2026-10-28 (AFK directive): "please work to drive VCF content factory open issues and vcf content factory pack issues for our three active paks to zero. When escalations arrise - first review our corpus and design decisions to resolve. Alsways default to \"the framework is the product\" and \"how is it done in OEM BC packs?\""

Origin: synology build 35 review round 4 (knowledge/context/reviews/synology-build-35.md): a pool DSM reports missing or awaiting assembly stayed green with only a log WARN. Synology#35 (alerts for the pack's key failure conditions). Rule applied: alert only on what the source reports (OEM packs do the same); the values below are DSM's own Storage Manager health inputs, read from storage_panel.js and seen live (normal) on the DS1520+.

## Vision

- Ships inside the synology SDK pak (`content/sdk-adapters/synology/`).
- Target: adapterKind `synology_diskstation`, resourceKind `SynologyDiskstation`.
- Symptoms (property conditions on the DiskStation, present-only properties from build 35):
  - Storage Critical: `Health|storage_status` EQ `danger`, CRITICAL (DSM banner "Critical").
  - Storage Warning: `Health|storage_status` EQ `attention`, WARNING (DSM banner "Warning").
  - Storage Pool Missing: `Health|missing_pools` NOT_EQ `0`, CRITICAL.
  - Storage Pool Awaiting Assembly: `Health|detected_pools` NOT_EQ `0`, WARNING.
  - System Partition Crashed: `Health|system_partition_crashed` EQ `true`, CRITICAL.
  - System Partition Needs Repair: `Health|system_partition_needs_repair` EQ `true`, WARNING.
- Alert: ANY of the six, criticality symptom-based, health badge, sub_type 18 (Availability). Recommendation: check Storage Manager, reconnect/restore drives or expansion unit, run Online Assemble or repair as DSM directs.
- Not seen degraded live (the lab has no failed storage); say so in the docs.
