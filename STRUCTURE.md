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
| `STRUCTURE.md` | This file | The map |

`HOW_IT_WORKS.md`, `vcf_ops_concepts.md`, and `ROADMAP.md` moved under
`knowledge/` in reorg v2 phase 2 (see *Layout history* below) — they are
now `knowledge/HOW_IT_WORKS.md`, `knowledge/vcf_ops_concepts.md`, and
`knowledge/ROADMAP.md`.

(`status.md` is untracked local scratch — see *Local state* below.)

## Directories — ours, mutable (we correct these)

| Path | What it is |
|---|---|
| `knowledge/` | The governance-and-reference umbrella (reorg v2 phase 2). Contains `rules/`, `lessons/`, `context/`, `designs/`, `diagrams/` (folded in phase 3), plus `HOW_IT_WORKS.md`, `ROADMAP.md`, `vcf_ops_concepts.md`. Internal structure unchanged — see the subrows below. |
| `knowledge/rules/` | Absolute law. Precedence 1. Obey without question. |
| `knowledge/lessons/` | Hard-won lessons. Precedence 2. Heed before "obvious" paths. |
| `knowledge/context/` | Working knowledge: specs, API maps, investigations, reviews, defect registry. Precedence 3. |
| `knowledge/designs/` | Prompt-of-record + design artifacts per content item / feature. |
| `content/` | Authored factory output: supermetrics, views, dashboards, alerts, MPs. `content/sdk-adapters/*` are independent git repos (gitignored, bootstrap-cloned). |
| `bundles/` | Publish-pipeline inputs: bundle manifests (what ships together) at the top level, release manifests (what has been released, per item) under `bundles/releases/`. Merged in reorg v2 phase 3. |
| `src/` | The ten `vcfops_*` framework Python packages (`src/vcfops_alerts/` … `src/vcfops_symptoms/`). **Only the `tooling` agent edits these** (RULE-013 gate applies). Directories moved under `src/` in reorg v2 phase 1; package names and import paths are unchanged (`python3 -m vcfops_<x>` still works — ambient `PYTHONPATH=src`). |
| `scripts/` | Hooks and operational shell scripts. Cannot move — wired into settings/CI. |
| `tests/` | Framework test suite. Cannot move. |
| `.claude/` | Harness config: agents, skills, settings. Cannot move. |
| `.github/` | CI workflows. Cannot move. |

## Directories — vendor / third-party, immutable (never edit; RULE-010/RULE-016)

| Path | What it is |
|---|---|
| `reference/` | The immutable root — everything under it is externally authored and read-only (RULE-016). Additions allowed, modifications never. |
| `reference/docs/` | Vendor source material (VCF Ops API docs, extracts — verbatim extracts go under `reference/docs/extracted/`, RULE-017). Corrections/digests go in `knowledge/context/` and cite the source path. |
| `reference/references/` | Known-good external example repos + reference paks. Gitignored; bootstrap-fetched via `knowledge/context/reference_sources.md`; some items (e.g. `reference/references/tvs/` Broadcom paks) are local-only downloads — anything *cited* must be committed or registry-fetchable (RULE-015). |
| `third_party/` | Redistributed third-party content items — deliberately **not** under `reference/`: it is content-adjacent (shipped by us, machine-routed by `vcfops_packaging`'s release builder), authored by others, attribution required. |

## Local state (gitignored; never travels, never in knowledge/context/)

| Path | What it is |
|---|---|
| `memory/` | Per-user/per-machine state and preferences. The one legitimate home for local knowledge. |
| `.env` | Credentials. Never committed. |
| `dist/` | Build outputs (paks, zips). Reproducible; not tracked. |
| `tmp/`, `scratchpad/`, `scratchpad-build/`, `scratch_pak/`, `scratch_ref/` | Session debris. Safe to delete at any time. |

## Legacy content

The pre-`content/`-era root `dashboards/` and `views/` directories were
removed in reorg v2 phase 0; their six historical YAMLs live in
`knowledge/context/attic/legacy-root-content/`. Authored content lives
under `content/`.

## Layout history (why it looks like this)

The 2026-07 top-level reorg (PM fresh-eyes review 2026-06-29) ran in
earned steps: step 1 = this map + RULE-015 + guard scripts (zero moves);
step 2 = `docs/` + `references/` grouped under `reference/` (RULE-016/017).
The planned step 3 (`knowledge/` grouping of `rules/`/`lessons/`/
`context/`/`designs/`) was **considered and declined** on 2026-07-07 against
that pass's "comprehension" framing: ~300-file sweep plus a cross-repo
break — every SDK pak's release CI fetches `context/defects.md` from
factory main by raw URL — for one word of grouping.

That framing was superseded on 2026-07-09 by
`knowledge/designs/reorg-v2-landing-page.md`: against the **landing-page**
goal (fewer top-level entries so a first-time visitor sees the README with
at most one flick), the same move pays for itself. Sequencing per that
design: phase 1 moved the ten `vcfops_*` packages under `src/`; phase 2
(this move) grouped `rules/`, `lessons/`, `context/`, `designs/`,
`HOW_IT_WORKS.md`, `ROADMAP.md`, and `vcf_ops_concepts.md` under
`knowledge/`, preceded by cross-repo pre-work — all 6 pak repos + the
sdk-template were updated to try `knowledge/context/defects.md` with
fallback to the old path before the factory-side move landed, so the
in-window pak CI never broke. `scripts/path_reference_audit.sh` in CI
remains the safety net for any future move.

## Rules of thumb

- If you corrected it, it belongs in `knowledge/rules/`, `knowledge/lessons/`, or `knowledge/context/` — never under `reference/`.
- If it's cited by path anywhere in the corpus, it must be committed or deterministically re-fetchable.
- If it's local-only, it lives in `memory/` or a scratch dir — never in `knowledge/context/`.
- Knowledge precedence when things conflict: `knowledge/rules/` > `knowledge/lessons/` > `knowledge/context/` (see CLAUDE.md).
