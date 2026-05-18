# vcf-mp-cleanroom

Local-only clean-room for reverse-engineering VCF Operations management
pack architecture. Output: a SPEC consumed by VCF-CF's Tier 2 (Native)
pipeline.

## Hard rules

- **NEVER push this repo to GitHub.** No remote should ever be added.
  Decompiled artifacts and analysis live on disk only.
- **VCF-CF must NEVER be dispatched into this workspace.** The clean-room
  boundary depends on VCF-CF only consuming the finished SPEC, not the
  decompiled sources.
- The SPEC is the only artifact intended to leave this workspace.

## Layout

- `inputs/from-devel/` — `.pak` files Navani fetches from operations devel
- `inputs/from-marketplace/` — `.paks` Scott provides from VCF Solution Marketplace
- `inputs/khriss-research/` — symlinks/copies of Khriss findings from `kb/work/`
- `analysis/per-adapter/` — one folder per MP analyzed
- `analysis/decompiled/` — raw CFR/jadx/javap output (gitignored)
- `spec/` — THE deliverable; clean SPEC for VCF-CF to author from
- `audit-log.md` — running log of what was observed and how SPEC was derived

## Provenance

- Strategy + cleanroom approach: `kb/work/` note (filed 2026-05-15)
- Architectural seed evidence: lab-admin handoff 2026-05-15 (filed to `kb/work/`)
- External research: Khriss findings (`kb/work/` when produced)

## Status

Phase 0 — collecting inputs. SPEC drafting begins after multiple adapters
analyzed for cross-validation. Tier 2 implementation parked until MPB v1
is stable.
