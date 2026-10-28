# A navigation TraversalSpec rooted at the adapter instance renders an empty tree

**Found:** UniFi build 18 devel proof, 2026-10-28 (visual check after the
API proof passed). **Also in:** UniFi builds 15 and 17, Synology, and the
SDK template's example spec, the source the others were copied from.

## What was wrong

Each pak's navigation spec set `rootResourceKind` to the adapter instance
kind, and every `ResourcePath` began
`<kind>::<kind>||<kind>::<X>World::child||...`. In the platform's data the
adapter instance has no children (its only parent is Universe), and the
World object has no parents. The first hop never matched, so the UI tree
showed the adapter instance alone. Every object and every World > Site >
device relationship existed. Topology tabs and the relationships API looked
right, so the API proof missed it.

## The fix (matches the OEM vSphere adapter)

Root the spec where the data actually starts. The vSphere adapter sets
`rootResourceKind="vSphere World"` and starts its paths at
`VMWARE::vSphere World` (cleanroom
`analysis/per-adapter/vmwarevi_adapter3.md`, spec 07). For our paks:
`rootResourceKind="<World kind>"`, paths start `<kind>::<World>||<next
level>::child||...`. Do not invent an instance > World edge to make the old
root work; vSphere's exists in its data, ours does not.

## Generalizable rule

> Every hop of a TraversalSpec path, starting with root to first level, must
> be a parent/child relationship the adapter actually publishes. Check the
> first hop against `/api/resources/{id}/relationships` for the root kind,
> and see the tree render in the UI before a tag. The relationships API
> being right does not mean the navigation tree is.

## References

- `knowledge/context/reviews/unifi-build-18.md` (the build that surfaced it)
- `knowledge/context/cleanroom-spec/spec/07-relationships-cross-mp.md`
