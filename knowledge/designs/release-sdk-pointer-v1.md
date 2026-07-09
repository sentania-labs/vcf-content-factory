# Design note — SDK MPs as pointers in the publish pipeline (v1)

## Initial prompt

2026-06-10 session (verbatim):

> let's update our release and publish pipeline so that sdk MPs don't
> get hosted in the bundles repo, but the readme points to the latest
> release, or just the MP repo page - so the readme can be read.
> what do you think?

## Vision

- The bundles repo (`sentania-labs/vcf-content-factory-bundles`) stops
  hosting SDK pak binaries entirely. Current state to fix:
  `management-packs/{synology-diskstation,unifi-controller}-managementpack.zip`
  are stale 2026-05-19 v1-era mirrors while the official CI-built
  releases live on the pak repos (v1.0.0.17 / v1.0.0.5).
- This implements the already-documented policy (CLAUDE.md): a factory
  `/publish` that references an SDK pak emits a **pointer** to that
  pak's latest GitHub Release, never a built/mirrored binary. One
  source of truth = the pak repo's CI release; no stale-binary class.
- README entry per SDK MP (generated between the AUTO markers): name,
  description (from the release manifest), **link to the pak repo page**
  (primary — GitHub renders the pak's living README there) and **link
  to `releases/latest`** (one-click download of the current pak).
  Repo URLs come from the `context/managed_paks.md` registry.
- Release manifests for SDK MPs stay (they carry description/notes for
  the README); the pipeline routes them as pointers instead of building
  zips. Existing hosted SDK zips move to `retired/` (repo convention)
  on the next publish.
- Tier 1 MPB packs and all other content types are unchanged.
