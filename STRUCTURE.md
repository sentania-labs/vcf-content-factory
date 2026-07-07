# STRUCTURE — map of this repository

One page. What each top-level thing is, who writes it, and whether you
may edit it. The model is **two axes**: authorship (ours / vendor / local)
× mutability (we-correct-it / never-touch-it). "Internal vs external" is
not the axis that matters — RULE-010 protects *immutability*.

## Root documents

| File | Role | One-line contract |
|---|---|---|
| `README.md` | Orientation | What this repo is; first thing a human reads |
| `Getting_Started.md` | Setup / bootstrap | Clone → configured, step by step |
| `CLAUDE.md` | Agent law | Orchestrator behavior, roster, delegation protocol |
| `ADMIN.md` | Concept model | VCF Ops content concepts for humans |
| `Memory.md` | Soul | Advisory persona/state; per-user detail in `memory/` |
| `HOW_IT_WORKS.md` | Architecture narrative | How the factory's pieces fit together |
| `vcf_ops_concepts.md` | Domain primer | VCF Ops platform concepts (not factory-specific) |
| `ROADMAP.md` | Direction | Where this is going; aspirational, not contractual |
| `STRUCTURE.md` | This file | The map |

(`status.md` is untracked local scratch — see *Local state* below.)

## Directories — ours, mutable (we correct these)

| Path | What it is |
|---|---|
| `rules/` | Absolute law. Precedence 1. Obey without question. |
| `lessons/` | Hard-won lessons. Precedence 2. Heed before "obvious" paths. |
| `context/` | Working knowledge: specs, API maps, investigations, reviews, defect registry. Precedence 3. |
| `designs/` | Prompt-of-record + design artifacts per content item / feature. |
| `content/` | Authored factory output: supermetrics, views, dashboards, alerts, MPs. `content/sdk-adapters/*` are independent git repos (gitignored, bootstrap-cloned). |
| `bundles/` | Bundle manifests (what ships together). |
| `releases/` | Release manifests (what has been released, per item). |
| `vcfops_*/` | Framework Python packages. **Only the `tooling` agent edits these** (RULE-013 gate applies). Cannot move — import paths. |
| `scripts/` | Hooks and operational shell scripts. Cannot move — wired into settings/CI. |
| `tests/` | Framework test suite. Cannot move. |
| `.claude/` | Harness config: agents, skills, settings. Cannot move. |
| `.github/` | CI workflows. Cannot move. |
| `diagrams/` | Authored diagrams (excalidraw etc.). |

## Directories — vendor / third-party, immutable (never edit; RULE-010/RULE-016)

| Path | What it is |
|---|---|
| `reference/` | The immutable root — everything under it is externally authored and read-only (RULE-016). Additions allowed, modifications never. |
| `reference/docs/` | Vendor source material (VCF Ops API docs, extracts — verbatim extracts go under `reference/docs/extracted/`, RULE-017). Corrections/digests go in `context/` and cite the source path. |
| `reference/references/` | Known-good external example repos + reference paks. Gitignored; bootstrap-fetched via `context/reference_sources.md`; some items (e.g. `reference/references/tvs/` Broadcom paks) are local-only downloads — anything *cited* must be committed or registry-fetchable (RULE-015). |
| `third_party/` | Redistributed third-party content items — deliberately **not** under `reference/`: it is content-adjacent (shipped by us, machine-routed by `vcfops_packaging`'s release builder), authored by others, attribution required. |

## Local state (gitignored; never travels, never in context/)

| Path | What it is |
|---|---|
| `memory/` | Per-user/per-machine state and preferences. The one legitimate home for local knowledge. |
| `.env` | Credentials. Never committed. |
| `dist/` | Build outputs (paks, zips). Reproducible; not tracked. |
| `tmp/`, `scratchpad/`, `scratchpad-build/`, `scratch_pak/`, `scratch_ref/` | Session debris. Safe to delete at any time. |

## Legacy stubs

`dashboards/`, `views/` at top level are pre-`content/` era remnants
(README pointers only). Authored content lives under `content/`. These
stubs are retained only until links to them are audited out.

## Layout history (why it looks like this)

The 2026-07 top-level reorg (PM fresh-eyes review 2026-06-29) ran in
earned steps: step 1 = this map + RULE-015 + guard scripts (zero moves);
step 2 = `docs/` + `references/` grouped under `reference/` (RULE-016/017).
The planned step 3 (`knowledge/` grouping of `rules/`/`lessons/`/
`context/`/`designs/`) was **considered and declined** (2026-07-07):
~300-file sweep plus a cross-repo break — every SDK pak's release CI
fetches `context/defects.md` from factory main by raw URL — for one
word of grouping. If it is ever revisited, the pak repos need a
fallback-URL transition first. `scripts/path_reference_audit.sh` in CI
is the safety net for any future move.

## Rules of thumb

- If you corrected it, it belongs in `rules/`, `lessons/`, or `context/` — never under `reference/`.
- If it's cited by path anywhere in the corpus, it must be committed or deterministically re-fetchable.
- If it's local-only, it lives in `memory/` or a scratch dir — never in `context/`.
- Knowledge precedence when things conflict: `rules/` > `lessons/` > `context/` (see CLAUDE.md).
