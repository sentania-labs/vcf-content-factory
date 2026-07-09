# Design — [VCF Content Factory] VMs - Undersized Only (custom group)

## Why this exists
Same TOOLSET GAP as the oversized group: the view schema can't filter by metric
predicate, so the Undersized VMs list view scopes to this dynamic group instead.

## Recon
Existing `Right-Sizing Candidates` group (oversized OR undersized OR idle) is too
broad. No existing group satisfies. Authoring warranted.

## Vision
Single-rule dynamic group on the built-in metric — portable, no super metric.
Membership = VMs currently flagged undersized. (Recon shows 0 undersized VMs now;
the group will simply be empty until one appears — expected.)

## Spec
- **Name:** `[VCF Content Factory] VMs - Undersized Only`
- **Membership resource kind:** `VirtualMachine` (VMWARE adapter)
- **Rule:** metric `summary|undersized` EQ `1`
- Single condition only.
