# Design — [VCF Content Factory] VMs - Oversized Only (custom group)

## Why this exists
The view YAML schema has no metric-predicate filter (TOOLSET GAP from
view-author a84de6eae011259a3). To scope the Oversized VMs list view to only
oversized VMs, we need a dynamic custom group the view can reference. User chose
the custom-group path over a tooling change.

## Recon
ops-recon (a64d3889c4a779a10) + view-author found an existing instance group
`Right-Sizing Candidates` = oversized OR undersized OR idle — **too broad** for a
dedicated oversized-only list. No existing group satisfies. Authoring warranted.

## Vision
A single-rule dynamic group on the built-in metric — fully portable (no super
metric). Membership = VMs currently flagged oversized.

## Spec
- **Name:** `[VCF Content Factory] VMs - Oversized Only`
- **Membership resource kind:** `VirtualMachine` (VMWARE adapter)
- **Rule:** metric `summary|oversized` EQ `1`
- Keep it to the single condition — do not OR in undersized/idle.
