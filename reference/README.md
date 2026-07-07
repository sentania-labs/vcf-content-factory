# reference/ — external, immutable material

Everything under this directory is **vendor/third-party authored and
read-only**. We never edit it. Corrections, digests, and findings about
this material live in `context/` and cite the source here by path
(RULE-010 spirit, generalized; see `rules/reference-immutable.md`).

| Subdirectory | What it is | Tracked? |
|---|---|---|
| `docs/` | Immutable vendor source material (Broadcom/VMware API specs, PDFs, extracted markdown) | git-tracked (PDFs gitignored) |
| `references/` | Local clones of external reference repos — known-good community content, grepped when authoring | gitignored; bootstrap via `scripts/bootstrap_references.sh` from `context/reference_sources.md` |

`third_party/` is **not** here on purpose: it is redistributed content
machine-routed by `vcfops_packaging` (release builder parses its path
shape), so it is content-adjacent, not reference material. See
`STRUCTURE.md` for the full two-axis map.
