# vcf-mp-cleanroom

Clean-room analysis of VCF Operations management
pack architecture. Output: a SPEC consumed by VCF-CF's Tier 2 (Native)
pipeline.

## Hard rules

- **VCF-CF must NEVER be dispatched into this workspace.** The clean-room
  boundary depends on VCF-CF only consuming the finished SPEC, not the
  decompiled sources.
- The SPEC is the only artifact intended to leave this workspace.

## Layout

- `inputs/from-devel/` — `.pak` files fetched from the operations devel lab appliance
- `inputs/from-marketplace/` — `.paks` Scott provides from VCF Solution Marketplace
- `inputs/external-research/` — copies of the external research notes
- `analysis/per-adapter/` — one folder per MP analyzed
- `analysis/decompiled/` — raw CFR/jadx/javap output (gitignored)
- `spec/` — THE deliverable; clean SPEC for VCF-CF to author from
- `audit-log.md` — running log of what was observed and how SPEC was derived

## Provenance

- Strategy + clean-room approach: maintainer's strategy note (2026-05-15)
- Architectural seed evidence: lab appliance findings (2026-05-15)
- External research: the external research notes under `inputs/external-research/`

## Status

Phase 0 — collecting inputs. SPEC drafting begins after multiple adapters
analyzed for cross-validation. Tier 2 implementation parked until MPB v1
is stable.
