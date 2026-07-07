# Reorg v2 — the landing page is the product surface

**Status:** DRAFT — awaiting user review (this design IS the memo; v1's
scope revisions lived in a gitignored local TODO and the user never saw
them — that process defect is why this file exists as a PR).

## Initial prompt (verbatim)

> I thought part of the reorg was to move all of the tooling and content
> into a cleaner structure. -what did I miss?

> Part of the reorg was franklly to make it so a user landing on the
> repo didn't have to scroll forever in github to find and start
> digesting the readme

> also as part of this - we need to refresh the linkage between this and
> bundles repo

> but SDK MPs just link to the sub repos - so they are there, the only
> thing truly hosted on bundles is released dashboards.

> okay go ahead

## Vision

- The GitHub landing page is a **product surface**. README renders below
  the file listing; today the listing is **42 tracked entries** (25
  directories — ten of them `vcfops_*` — plus 17 files). Nobody scrolls
  that. Success metric: a first-time visitor sees the README with at
  most one flick, and the README's first screen routes them ("want
  content → bundles repo; want to drive the factory → Getting_Started").
- Reorg v1 optimized for *comprehension* (STRUCTURE.md map) and declared
  tooling immovable axiomatically. Against the landing-page goal, both
  calls change: package **names** are immovable (import paths), package
  **directories** are not.
- The factory ↔ bundles-repo linkage is part of the same surface: the
  factory README currently never mentions `vcf-content-factory-bundles`,
  so consumers who land here have no path to the downloadable content.

## Target landing page (~22 entries, from 42)

```
.claude/  .github/
bundles/  content/  knowledge/  memory/  reference/  releases/
scripts/  src/  tests/  third_party/  diagrams/
.env.example  .gitignore  LICENSE  pyproject.toml
README.md  Getting_Started.md  CLAUDE.md  ADMIN.md  Memory.md  STRUCTURE.md
```

Deltas from today:

| Change | Entries removed |
|---|---|
| `vcfops_*` × 10 → `src/` (names unchanged inside) | −9 |
| `rules/ lessons/ context/ designs/` → `knowledge/` | −3 |
| Legacy stubs `dashboards/`, `views/` deleted | −2 |
| `HOW_IT_WORKS.md`, `ROADMAP.md`, `vcf_ops_concepts.md` → `knowledge/` | −3 |
| `pytest.ini`, `requirements.txt`, `requirements-dev.txt` → `pyproject.toml` | −3 (+1) |

Explicitly **kept at root**: `third_party/` (machine-routed by
`vcfops_packaging` — v1 decision stands), `bundles/` + `releases/`
(publish pipeline inputs; merging them is a possible phase 3, not
required), `memory/` (local-state home), `diagrams/` (small; candidate
to fold later). Per-item content folders remain a **separate deferred
effort** — they change depth, not top-level row count.

## Phases (each gated: validate ×7 + full pytest + path-audit + review)

### Phase 0 — quick wins, no structural risk
1. Delete `dashboards/` + `views/` stubs (audit inbound links first —
   the enforcing path-audit is the net).
2. Factory README top section links to `vcf-content-factory-bundles`
   ("just want the content?"); verify bundles README links back.
3. Refresh `releases/*.yaml` metadata (dates/descriptions predate the
   stitching work; e.g. synology still says "First public build") →
   `/publish` PR so the bundles README rows regenerate. Binaries are
   already correct (`releases/latest` pointers — confirmed live).

### Phase 1 — `src/` (the −9 move)
Mechanics: src-layout `pyproject.toml` declaring all ten packages with
names unchanged; `pip install -e .` replaces `requirements.txt` manual
path-dependency; every `python3 -m vcfops_<x>` invocation in CLAUDE.md /
agents / CI / pak workflows keeps working verbatim.
**Spike first, on a branch, before any sweep:**
- `vcfops_managementpacks/buildkit.py` (build-buildkit packages the sdk
  tarball from package-relative paths — must use `__file__`, verify);
- `scripts/*.sh` referencing `vcfops_*` paths; CI install step;
  `Getting_Started.md` dev setup; editable-install behavior for the
  gitignored `adapter_runtime/` JARs inside the package tree.
- pak repos are insulated (they consume the published buildkit tarball,
  not the factory checkout) — verify the tarball layout is unchanged.
Owner: `tooling`; gate: `framework-reviewer` (RULE-013 blanket) + a full
buildkit rebuild compared against the released 1.0.6 tarball.

### Phase 2 — `knowledge/` (the −3/−6 move; v1's declined step 3, revived)
The v1 no-go was decided against the comprehension goal; against the
landing-page goal it pays. Costs unchanged and known:
- **Cross-repo pre-work first:** all 6 pak repos + the sdk-template
  fetch `context/defects.md` from factory main by raw URL (workflow +
  vendored `ci/defect_gate.py`). Sequence: (a) update all 7 to try
  `knowledge/context/defects.md` with fallback to the old path, (b) move
  the factory dirs, (c) strip fallbacks later. No `v*` tags mid-window.
- ~300-file citation sweep (v2-proven playbook: delegated sweep +
  enforcing path-audit); CLAUDE.md precedence text, agent-prompt
  boilerplate ("read rules/INDEX.md"), curator corpus definition,
  RULE-015/016/017 texts, curation hooks, registry-reading scripts.
- Fold `HOW_IT_WORKS.md` / `ROADMAP.md` / `vcf_ops_concepts.md` into
  `knowledge/` in the same sweep.
- Amend STRUCTURE.md's layout-history note (the step-3 "declined" record
  is superseded by this design's clarified goal).

### Phase 3 (optional, decide after 0–2 land)
`bundles/`+`releases/` merge; `diagrams/` fold; anything else earns its
move against the row-count metric or stays put.

## Non-goals
- Renaming Python packages (import paths are contract).
- Moving `.claude/`, `.github/`, `scripts/`, `tests/`, `content/`,
  `third_party/`.
- Per-item content folders (separate design when taken up).

## Origin
User feedback 2026-07-07 after reorg v1 closeout: the landing-page goal
was underweighted in v1's "comprehension" framing, and v1's scope
revisions were invisible to the user (recorded only in a gitignored
local work-plan). Supersedes the deleted
`memory/environment/TODO-top-level-reorg.md`; v1's durable outputs
(RULE-015/016/017, STRUCTURE.md, enforcing guards) are unaffected.
