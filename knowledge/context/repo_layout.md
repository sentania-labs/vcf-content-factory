# Repository layout

The directory map for the VCF Content Factory. Read this on demand
when you need to know where something lives or where something new
should go. `STRUCTURE.md` (repo root) is the authoritative two-axis
map (authorship × mutability); this file is the deeper per-package
detail.

## Top-level

```
ADMIN.md                     Human-facing concept walkthrough
CLAUDE.md                    Orchestrator rules (always loaded)
README.md                    Project intro
ROADMAP.md                   What's done / in progress / next
STRUCTURE.md                 Authoritative directory map
reference/                   Immutable external material (RULE-016) — see Knowledge below
```

## Python packages

A location-agnostic core library, one factory package per content
type, and shared infrastructure, all under `src/`. Only the `tooling`
agent edits these. Package names and module invocations are unchanged
by the `src/` move: `python3 -m vcfcf_<x>` still works verbatim
(ambient `PYTHONPATH=src`).

```
src/
  vcfcf_core/               Parse/validate/render/packaging logic per type
                            (alerts, customgroups, dashboards, reports,
                            supermetrics, symptoms, packaging, extractor,
                            common). No .env, no live instance, no repo
                            layout assumptions (tests/test_core_contract.py)
  vcfcf_common/             Shared helpers: env loader, base HTTP client
  vcfcf_supermetrics/       Loader wrapper, client, CLI (validate/list/sync/delete)
  vcfcf_dashboards/         Views + dashboards loader wrapper/client/CLI
  vcfcf_customgroups/       Custom groups + group types loader wrapper/client/CLI
  vcfcf_symptoms/           Symptom definitions loader wrapper/client/CLI
  vcfcf_alerts/             Alert + recommendation loader wrapper/client/CLI
  vcfcf_reports/            Report definitions loader wrapper/client/CLI
  vcfcf_packaging/          Bundle builder, releases, publish, install script templates
  vcfcf_managementpacks/    MP YAML loader, MPB render, .pak builder/installer (not in core)
  vcfcf_extractor/          Reverse flow: extract live dashboards into bundles
  vcfops_*/                 Deprecated one-release import aliases for vcfcf_*
```

The parsing, validation and rendering live in `vcfcf_core/<type>/`.
The per-type factory package keeps the same module names (`loader.py`,
`render.py`, ...): they re-export the core names and keep the live half,
what a library must not do on its own (mint UUIDs into authored YAML and
derive provenance from the repo layout where the type has them, talk to
a live instance). Some factory-side modules are substantial code in
their own right (for example `vcfcf_packaging/describe.py`,
`vcfcf_extractor/extractor.py`). Fix shared parse, validate and render behaviour in the core module
(patch the core module in tests); fix UUID minting, provenance, REST
clients and CLIs in the wrapper that owns them. Design:
`knowledge/designs/tooling-core-carveout-v1.md`.

Every per-type factory package follows the same skeleton:

```
src/vcfcf_<type>/
  __init__.py
  __main__.py    → cli.main()
  loader.py      → wraps vcfcf_core.<type>.loader (UUID mint and provenance where the type has them)
  client.py      → REST client
  cli.py         → validate, list, sync, delete
```

## Content (YAML source of truth)

Authored content. Each directory has its own author agent.

```
content/
  supermetrics/              Super metric YAML
  customgroups/              Custom group YAML
  views/                     List view YAML
  dashboards/                Dashboard YAML
  symptoms/                  Symptom definition YAML
  alerts/                    Alert definition YAML
  recommendations/           Remediation recommendation YAML
  reports/                   Report definition YAML
  managementpacks/           Management pack YAML (MPB builder input)
  sdk-adapters/              Tier 2 SDK adapter repos (gitignored; bootstrap-cloned)
```

## Distribution

```
bundles/                     Bundle manifests (input to vcfcf_packaging build)
dist/                        Built distribution zips (gitignored)
designs/                     Approved MP / content design artifacts (mp-designer output)
```

## Knowledge

```
context/                     Topical background — read on demand
  README.md                  Index of context files
  rules_*.md                 Hard-won operational rules by category
  *.md                       Topical references (wire formats, API surface, etc.)
reference/                   Immutable external material (RULE-016; never edit)
  docs/                      Vendor source-of-truth references
    vcf9/                    Extracted VCF 9 documentation markdown
    extracted/               Verbatim vendor extracts (RULE-017)
    operations-api.json      Public Suite API OpenAPI spec
    internal-api.json        Internal (unsupported) API OpenAPI spec
  references/                Allowlisted external reference clones (gitignored;
                             populate via scripts/bootstrap_references.sh)
```

## Claude Code configuration

```
.claude/
  agents/                    Subagent prompts (one file per agent)
  skills/                    Domain skills loaded on demand
  commands/                  Slash commands (/bundle, /release, /publish, /extract)
  settings.json              autoMemoryEnabled: false; bootstrap_references hook
```

## Scripts

```
scripts/
  bootstrap_references.sh    Clones allowlisted external reference repos
```