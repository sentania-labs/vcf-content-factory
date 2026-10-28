# Design: Synology Expansion Unit Lost (alert)

## Initial prompt

Same as knowledge/designs/alerts/synology-storage-degraded.md (Scott's AFK directive 2026-10-28; synology build 35 review round 4; synology#35).

## Vision

- Ships inside the synology SDK pak; adapterKind `synology_diskstation`, resourceKind `SynologyDiskstation`.
- Symptoms (DiskStation properties, present-only):
  - Expansion Unit Lost: `Health|expansion_unit_lost` EQ `true`, CRITICAL.
  - Incompatible Expansion Unit: `Health|incompatible_expansion_units` NOT_EQ `0`, WARNING.
- Alert: ANY of the two, symptom-based, health badge, sub_type 18. Recommendation: check the expansion unit's power and cable; DSM pools on it are unavailable until it reconnects.
- Desktop models without an expansion unit never fire (DSM sends false / empty).
