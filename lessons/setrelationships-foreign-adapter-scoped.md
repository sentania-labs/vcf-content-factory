# setRelationships on a foreign resource is scoped per-reporting-adapter

> **SUPERSEDED (2026-07-02) — historical record only.** The framework no
> longer emits full-set `setRelationships` onto foreign parents at all:
> since the write-verb split (`designs/stitcher-identity-and-additive-foreign-v1.md`,
> user decision "Option 2"), `RelationshipBuilder.parentForeign` emits
> **additively** — matching all 8 shipping vendor paks and removing any
> dependence on the per-adapter-scoping behavior this lesson proved (which
> was 9.0.2-only; 9.1 was never verified and no longer needs to be). The
> scoping *observation* below remains true and historically useful, but
> the "do not add delta workarounds / full-set is safe" guidance is
> **obsolete — do not follow it.** Current guidance:
> `lessons/cross-mp-stitch-cp-identity-and-edge-mechanics.md`.

## Rule (superseded — see banner)

On VCF Ops 9.0.2, when a non-owning adapter emits
`setRelationships(foreignParent, {ownChildren})` via
`RelationshipBuilder.build()`, the platform scopes the replacement to the
reporting adapter's edges only. The owning adapter's edges on the same
parent are **not touched**.

**Do not add delta/labeled emission workarounds (`addRelationships`,
`setGenericRelationships(…, label)`) to protect foreign parents' existing
edges.** The full-set `parentForeign` + `build()` form is safe.

## Evidence

Synology build 16, devel instance, VCF Ops 9.0.2, 2026-06-10:

The `vcf-lab-wld01-cl01-iscsi` VMWARE Datastore had 22 existing
VMWARE-collected relationships (HostSystem, VM, Pods, etc.) before the
install. After a full collection cycle with build 16, which emits
`setRelationships(datastoreKey, {SynologyIscsiLun})` via
`parentForeign(datastoreKey)` + `RelationshipBuilder.build()`, the Datastore
retained all 22 VMWARE-collected children and gained the new
`SynologyIscsiLun` child edge. VMWARE's edges were undisturbed.

This closed the open question in synology-build-16 WARNING-1
(`context/reviews/synology-build-16.md`), which the static review could not
close: "the only authoritative disproof is a live collect."

Spec/19 §3 line 213–214 endorses the cross-MP `ResourceKey` as parent with
platform de-dupe by identity — the devel install confirms the platform
implements per-adapter scoping rather than a global replacement on the
foreign parent's child set.

## Open residual

Confirmed on 9.0.2 only. Not yet verified on 9.1. Make this an explicit
acceptance criterion on the first cross-adapter stitch build promoted to a
9.1 target: confirm the foreign parent retains its owning-adapter edges after
the non-owning adapter's collect.

## Context

- `context/tier2_architecture.md` — "setRelationships on a foreign resource"
  authoring contract note and changelog entry
- `context/framework_v2_migration.md` §7 — RelationshipBuilder API
- `context/reviews/synology-build-16.md` — WARNING-1 (the static-review gap
  this lesson closes)
- `cleanroom-spec/spec/19-adapterbase-behavioral-contract.md` §3 — the
  `setRelationships` contract spec (read-only drop; do not edit)
