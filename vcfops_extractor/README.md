# vcfops_extractor

Reverse-engineering toolkit for VCF Operations content.

Walks a live dashboard and its dependency graph (views, super metrics) and
emits factory-shape YAML under `bundles/third_party/<slug>/` plus a bundle
manifest that `vcfops_packaging build` can turn into a distributable zip.

## Scope (Phase 1)

| Content type | Phase 1 | Notes |
|---|---|---|
| Dashboard | Extracted (minimal YAML) | Widget graph not reconstructed in Phase 1 |
| Views | Extracted (full columns) | Reverse-parsed from content-zip XML |
| Super metrics | Extracted (formulas rewritten) | UUID tokens -> `@supermetric:"name"` |
| Custom groups | WARN only | Phase 2 |
| Reports / symptoms / alerts | Not supported | Phase 3 |

Phase 1 is sufficient to produce a distributable bundle ZIP with provenance
metadata for redistribution. The `/extract` slash command drives the
attribution interview and calls this package with complete flags.

## Subcommands

```
python -m vcfops_extractor --help
python -m vcfops_extractor extract --help
python -m vcfops_extractor extract dashboard --help
python -m vcfops_extractor list-dashboards --help
```

### `extract dashboard`

Walk a dashboard's dependency graph and emit factory-shape YAML + manifest.

**Required flags (one of):**
- `--dashboard-id UUID` -- dashboard UUID (unambiguous, preferred)
- `--dashboard-name NAME` -- display name (resolved via getDashboardList)

**Required attribution:**
- `--bundle-slug SLUG` -- short identifier, e.g. `idps-planner`
- `--author AUTHOR` -- attribution line, e.g. `"Scott Bowe"`
- `--license LICENSE` -- SPDX id or free-form, e.g. `MIT`, `Apache-2.0`, `Proprietary`
- `--description-file PATH` -- Markdown file with long-form description

**Optional provenance:**
- `--source-url URL` -- canonical URL for the source
- `--source-version VERSION` -- source version string, e.g. `3.2`

**Output control:**
- `--output-dir DIR` -- root output directory (default: `bundles/third_party`)

**Dependency filters:**
- `--skip-supermetric NAME` -- skip a SM by name (repeatable)
- `--include-customgroup NAME` -- force-include a custom group (Phase 2; accepted but no-op in Phase 1)

**Run mode:**
- `--dry-run` -- print the plan without writing any files
- `--yes` -- skip confirmation prompt (for scripted/CI use)

### `list-dashboards`

List dashboards available on the lab instance.

```
python -m vcfops_extractor list-dashboards
python -m vcfops_extractor list-dashboards --folder "IDPS"
```

Prints `UUID  name` for each dashboard. Use the UUID with `--dashboard-id` for
unambiguous extraction.

## Connection

All commands read credentials from env vars (auto-loaded from `.env` at repo root):

| Env var | Meaning |
|---|---|
| `VCFOPS_HOST` | Hostname or IP of the VCF Ops instance |
| `VCFOPS_USER` | Admin-privileged username |
| `VCFOPS_PASSWORD` | Password |
| `VCFOPS_VERIFY_SSL` | Set to `false` to disable SSL verification |

Override per-invocation with `--host`, `--user`, `--password`, `--no-verify-ssl`.

No interactive prompts anywhere. Missing required flags abort with a clear error.

## Examples

### Flag-driven (CI-safe)

```bash
# Preview dependency walk without writing files
python -m vcfops_extractor extract dashboard \
  --dashboard-name "IDPS Planner" \
  --bundle-slug idps-planner \
  --author "Scott Bowe" \
  --license "Proprietary" \
  --description-file /tmp/idps-description.md \
  --source-url "https://sentania.net" \
  --source-version "3.2" \
  --dry-run

# Full extraction (skip confirmation)
python -m vcfops_extractor extract dashboard \
  --dashboard-name "IDPS Planner" \
  --bundle-slug idps-planner \
  --author "Scott Bowe" \
  --license "Proprietary" \
  --description-file bundles/third_party/idps-planner/DESCRIPTION.md \
  --source-url "https://sentania.net" \
  --source-version "3.2" \
  --yes

# Then build the distributable zip
python -m vcfops_packaging build bundles/third_party/idps-planner.yaml
```

### Slash-command-driven (primary UX)

Use the `/extract` slash command in the VCF Content Factory Claude Code session.
It conducts the attribution interview, writes the description file, and invokes
this CLI with all flags populated.

## Output structure

```
bundles/third_party/
  <slug>.yaml                  # bundle manifest
  <slug>/
    DESCRIPTION.md             # long-form description (written by /extract)
    supermetrics/
      <name>.yaml              # one file per SM
    views/
      <name>.yaml              # one file per view
    dashboards/
      <name>.yaml              # dashboard metadata (Phase 1: no widget graph)
```

## Non-overwrite invariant

If a resolved UUID matches an existing `id:` in the factory repo's
`supermetrics/`, `views/`, or `dashboards/` directories, the file is skipped
with a WARN. Existing factory content is never overwritten.

## Architectural notes

- Reverse parsers live in sibling packages: `vcfops_dashboards.reverse` (Phase 1
  partial) and `vcfops_supermetrics.reverse` for cleaner separation.
- SM formula UUID->name rewriting uses a lazy-loaded name cache backed by
  `GET /api/supermetrics/{id}` per-UUID (avoids a full list on small graphs).
- View export uses `POST /api/content/operations/export` with
  `contentTypes=["VIEW_DEFINITIONS"]` -- a single bulk export for all views
  referenced by the dashboard, not one export per view (avoids export task
  contention).
- Dashboard config fetched via `POST /ui/dashboard.action mainAction=getDashboardConfig`
  using the same UI session auth pattern as the management packs installer.
