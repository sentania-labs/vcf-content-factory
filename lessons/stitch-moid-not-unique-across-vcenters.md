# Foreign-resource stitching: MOID is only unique per vCenter — scope by owning vCenter

**Found:** sdk-adapter-reviewer, vcommunity build 1 (the review's one
substantive correctness WARNING). **Fixed:** vcommunity build 2, 2026-06-10.
**Same defect in the compliance adapter's stitcher — fix queued.**

## What was wrong

A stitcher that resolves foreign VMWARE resources by loading
`/api/resources?adapterKind=VMWARE&resourceKind=<kind>` with **no vCenter
scoping** and then matching on **bare MOID first** (`byMoid.get(moid)`)
cross-stitches the moment a VCF Ops instance has two vCenter adapter
instances. MOIDs (`host-12`, `vm-42`) are unique only *within* a vCenter —
`host-10` exists in every vCenter. The unscoped load returns every vCenter's
`host-12`, the `byMoid.put(moid, entry)` index keeps only the last writer,
and a push silently lands on the wrong vCenter's host. **Silent data
corruption, not an error** — single-vCenter labs (including devel) never see
it.

Two aggravating facts:

1. **The reference implementation enshrined the bug.** The compliance
   adapter's `ComplianceStitcher.matchResource` (lines 304–330;
   `loadHostResources` unscoped) is the same bare-MOID-first logic and ships
   healthy. vcommunity faithfully copied the proven reference idiom and
   inherited the defect. *Copying the reference does not grant correctness —
   check it against the skill's identity rule anyway.*
2. **It was a regression from the original Python**, which scoped its Suite
   API query by `adapterInstanceId` (`collectHostData.py:40`) — restricting
   the resource set to the single vCenter that instance monitored, which is
   what made bare MOID safe there. The Java port dropped the scope.

The skill (`vcfops-sdk-adapter`, § *ARIA_OPS stitching identity — the MOID
trap*) already stated "MOID is not unique across vCenters — join on vCenter
`instanceUuid` + MOID." The principle was written down and both shipped
stitchers still violated it, because the reviewer's hunt is what caught it,
not authoring discipline.

## The fix pattern (vcommunity build 2 — copy this)

`content/sdk-adapters/vcommunity/src/com/vcfcf/adapters/vcommunity/VCommunityStitcher.java`:

- **Pin the owning vCenter each cycle.** Before any `load*` call, set the
  owning vCenter Instance UUID from the live SOAP session
  (`vsphere.getVCenterInstanceUuid()` — `ServiceContent.about.instanceUuid`):
  `stitcher.setOwningVcUuid(...)` (`VCommunityAdapter.java:313`).
- **Filter at load time by the `VMEntityVCID` resource identifier.** When the
  owning UUID is known and a loaded resource carries a `VMEntityVCID` that
  does not match, skip it — a bare MOID can then only resolve to a resource
  belonging to the vCenter this adapter instance monitors.
- **Degrade, never drop.** If the owning UUID is unknown (null/blank — not
  yet resolved) or a row has no `VMEntityVCID`, keep the resource and fall
  back to the old unscoped behaviour. Single-vCenter deployments are
  unaffected either way.
- **Log the scope.** The load line reports `scoped to vCenter <uuid>; skipped
  N from other vCenters` vs `unscoped — owning vCenter UUID unknown`, so a
  silently-unscoped cycle is visible in the adapter log.

## Generalizable rule

> Any stitcher resolving foreign resources by a target-system-local ID (vim
> MOID, NAS volume ID, controller slot, …) must scope resolution to the
> owning target instance — for VMWARE kinds, filter by `VMEntityVCID`
> against the vCenter UUID pinned from the live session. Local IDs are only
> unique per target. Degrade to unscoped when the discriminator is unknown;
> never drop an undisambiguatable resource.

## References

- `context/reviews/vcommunity-build-1.md` — the WARNING and honest
  disposition (reference-parity argument for WARNING-not-BLOCKING)
- `content/sdk-adapters/vcommunity/src/com/vcfcf/adapters/vcommunity/VCommunityStitcher.java` — fix site (build 2)
- `content/sdk-adapters/compliance/` — `ComplianceStitcher` carries the same
  defect; fix queued. Until then it is NOT the pattern to copy for stitching
  identity.
- `.claude/skills/vcfops-sdk-adapter/SKILL.md` § *ARIA_OPS stitching identity
  — the MOID trap* — the standing identity rule this enforces
