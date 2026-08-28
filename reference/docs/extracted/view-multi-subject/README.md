# view-multi-subject

Verbatim ViewDef header (Title, Description, SubjectType elements, Usage
tags; the Controls/Presentation body that follows is omitted) of the
vCommunity vSphere pak's `vSphere Data Centers Inventory` list view, a
public view whose single ViewDef carries TWO subject kinds
(`VMWARE:Datacenter` and `VMWARE:vSphere World`).

- **Source:** `reference/references/vmbro_vcf_operations_vcommunity/Management
  Pack/content/reports/View - Collection01.xml`, lines 7519-7542
  (fetched by `scripts/bootstrap_references.sh` from the registry entry in
  `knowledge/context/reference_sources.md`).
- **Extracted:** 2026-08-25, unmodified (RULE-016; immutable once added).
- **Digest:** `knowledge/context/wire-formats/view_column_wire_format.md`,
  section "Multiple subject kinds (`subjects:`)".

What it shows: each subject kind gets its own `type="descendant"` then
`type="self"` pair, kinds in sequence; per-column `adapterKind` /
`resourceKind` properties (in the omitted body) name only the first
subject kind. The same shape with three kinds (K8S-Statefulset,
K8S-Deployment, K8S-Daemonset) ships in the public Kubernetes MP views in
`reference/references/dalehassinger_unlocking_the_potential/`.
