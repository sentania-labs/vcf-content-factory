---
id: RULE-008
decision_refs: []
---

# RULE-008: MP adapter_kind must match MPB derivation

The factory must produce paks identical to what MPB generates from the same design. The adapter_kind is derived by slugifying the MP display name: `mpb_` + `lowercase(name.replace(' ', '_'))`.

Example: "VCF Content Factory vSphere Storage Paths" → `mpb_vcf_content_factory_vsphere_storage_paths`.

Do not shorten, abbreviate, or invent a different convention.

**If violated:** The pak installs but VCF Operations treats it as a different adapter, breaking resource ID continuity and orphaning existing policy bindings.
