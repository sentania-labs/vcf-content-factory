# vcf-cf-tooling-core: the M2 carve-out

Status: design, 2026-09-14, awaiting Scott's go. Parent plan:
`content-migrator-plan-v1.md` §M2. Boundary evidence: a read-only map
of all ten `src/vcfcf_*` packages (module by module) taken on
2026-09-14; the classification below comes from that map, not from
guesswork.

## What the library is

`vcf-cf-tooling-core` (import name `vcfcf_core`) is the part of the
factory that has no opinion about where it runs: parse a content-zip,
tokenize and rewrite a super metric formula, walk dependencies, render
YAML to the wire JSON/XML, assemble an import zip from objects in
memory. It never reads `.env`, never assumes `content/` or
`knowledge/` exist, never calls a VCF Ops instance, never writes a
file it was not handed a path for.

Everything else stays in the factory: CLIs, `.env` and profiles, the
doctor, live sync/enable/delete, the defect registry, the describe
cache location, publish, the extractor's live fetch, the MPB and SDK
builders' javac and jar steps.

## Where it lives (decision)

Inside this repo, at `src/vcfcf_core/`, next to the ten factory
packages. Reasons, in operational terms:

- Zero wiring change. The factory already resolves everything through
  ambient `PYTHONPATH=src` (hook, CI, scripts) and is deliberately
  never pip-installed (see the comments in `pyproject.toml`). A sibling
  directory rides that for free. A separate `lib/` tree would mean a
  second path entry in every hook, CI job, and script, which is drift
  waiting to happen.
- One diff, one review. Moving a module from `vcfcf_dashboards/` to
  `vcfcf_core/dashboards/` is a `git mv` the reviewer can follow.
- The wheel is built from the root `pyproject.toml`, which becomes the
  library's metadata with an explicit package list (only
  `src/vcfcf_core`). The factory packages are still not installable,
  which is the current stance. If the root file cannot serve both
  roles cleanly, the fallback is `lib/tooling-core/pyproject.toml`
  pointing at the same source; that is a packaging detail, not a
  layout change.

Library version comes from a `core-vX.Y.Z` tag, separate from the
factory's `vX.Y.Z` tags, so factory releases do not churn the
migrator's pin. `scripts/version_line_guard.sh` must be checked to
make sure a `core-v*` tag is neither refused nor mistaken for a pak
tag.

## The contract, enforced by a test

A test in `tests/` imports every `vcfcf_core` module with the working
directory set to an empty temp dir and an empty environment, and
fails on any of: a module-level path derived from `__file__` that
escapes the package, `os.environ` reads, a default argument naming a
directory (`"content/..."`, `"supermetrics"`, `"bundles"`), an import
of `requests` or of any non-core `vcfcf_*` module, or a file write
during a load call. This is the guard that keeps the library a library
after the carve-out is done.

## What moves, in order

Each row is one PR: tooling moves the modules, leaves a one-line
re-export in the old location so every factory import keeps working
unchanged, fixes the named leak, and the reviewer gate runs. The
factory's own behavior and output must be byte-identical after every
row; the zip comparison from M1 is the proof each time.

| PR | Moves to `vcfcf_core` | Leak fixed on the way |
|---|---|---|
| 1 | Scaffold, contract test, wheel build in CI on `core-v*`. Plus the modules with no leaks and no imports outside the row: `dashboards/yaml_utils`, `supermetrics/crossref`, `symptoms/loader`, `alerts/loader`, `alerts/render`, `packaging/release_types`, `packaging/template_version`. (Row 1 as built, 2026-09-14: `supermetrics/reverse`, `reports/render`, and `packaging/deps` import row-3 loaders at runtime, so they move with row 3) | none; this PR proves the mechanism. **Done 2026-09-14, PR #161**: wheel gate green in CI, Codex clean, not yet tagged |
| 2 | `dashboards/reverse`, `dashboards/render`, `dashboards/packager`, the parse half of `dashboards/loader`, the pure half of `dashboards/summary_bind` | `render.py` scans `content/supermetrics` relative to the working directory when unscoped; the SM map becomes a required argument. `loader.py` writes a minted id back into the YAML during load; minting moves to the factory's CLI layer. **Done 2026-09-14, PR pending**: both leaks fixed (SM map is a render argument, minting and provenance are callbacks the factory wrapper supplies), three bundles and the standalone package zip byte-identical to main apart from the build timestamp, buildkit copies the core loader/renderer so an adapter YAML without an id now fails the pak build instead of being minted in CI |
| 3 | Pure halves of `common/dep_walker` (collect, extract refs, expand, scope), `packaging/describe` (resolve, disk load, merge), `packaging/audit`, `common/provenance`, parse halves of `supermetrics/loader`, `customgroups/loader`, `reports/loader`, `packaging/loader`; with them `supermetrics/reverse`, `reports/render`, `packaging/deps` (deferred from row 1); the in-memory zip assembly and manifest writer from `packaging/builder` and `discrete_builder` | `describe` defaults its cache dir to `knowledge/context/...`; becomes required. `provenance` sniffs for a repo root; becomes required. The three loaders default to `content/...` directories; become required. `vcfcf_common/__init__` stops importing `.env` machinery eagerly |
| 4 | Extractor's pure parsers (`_parse_view_xml` and friends, `_widget_to_yaml_dict`, `_emit_view_extras`) and `reverse_local` | `extractor.py` binds a repo root at import time; the pure parsers leave, the root stays behind. This row is what gives the migrator its offline read path |
| 5 (later) | Management pack pure set: `loader`, `render`, `render_export`, `render_template`, `extract`, `pak_compare`, `pak_validator`, `sdk_project`, `docs_gen` | none in the code; deferred because the migrator MVP does not need it |

After row 4 the migrator (M3, M4) has everything it needs: read an
export zip offline, walk the graph, render previews, assemble an import
bundle.

## What stays put and why

- `vcfops_manifest.json` keeps its name and its writers; it is a wire
  artifact read by shipped installers.
- The describe cache's location, refresh, and merge policy stay in the
  factory; only "given a cache directory, resolve a metric" moves.
- `_mint_id_into_file` (writing a fresh UUID into an authored YAML)
  stays in the factory. A library must not edit its input.

## Side item to fold in

Every build with credentials now rewrites a timestamp in ten describe
cache files, leaving a dirty tree to discard. Row 3 touches `describe`
anyway; make the refresh skip the write when nothing but `fetched_at`
would change.

## Gates

- Each row: tooling, then framework-reviewer with every finding fixed
  before the PR opens (CLAUDE.md step 9), then PR, one Codex round.
- Row 1 also needs: the wheel builds in CI, installs into a clean venv,
  and `python -c "import vcfcf_core"` works with no `PYTHONPATH`.
- Done means: `core-v0.1.0` tagged, wheel attached to a GitHub
  Release, and the migrator skeleton (M3) installs it by URL.

## Release log

- **core-v0.0.1** (2026-09-14): proves the publish path only; not a usable
  library. Scott, verbatim: "let's prove the publish path but tag it as
  core-v0.0.1; we'll make the first usable release v0.1.0". Tagged at the
  main head after PR #161.
