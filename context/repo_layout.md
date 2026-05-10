# Repository layout

The directory map for the VCF Content Factory. Read this on demand
when you need to know where something lives or where something new
should go.

## Top-level directories

```
docs/                        OpenAPI specs + extracted VCF 9 markdown; PDFs gitignored
ADMIN.md                     Human-facing concept walkthrough
CLAUDE.md                    Orchestrator rules (always loaded)
README.md                    Project intro
ROADMAP.md                   What's done / in progress / next
```

## Python packages

One package per content type plus shared infrastructure. Only the
`tooling` agent edits these.

```
vcfops_common/               Shared helpers: env loader, base HTTP client
vcfops_supermetrics/         Loader, client, CLI (validate/list/sync/delete)
vcfops_dashboards/           Views + dashboards loader/render/client/CLI
vcfops_customgroups/         Custom groups + group types loader/client/CLI
vcfops_symptoms/             Symptom definitions loader/client/CLI
vcfops_alerts/               Alert + recommendation loader/render/client/CLI
vcfops_reports/              Report definitions loader/render/client/CLI
vcfops_packaging/            Bundle loader, builder, install script templates
vcfops_managementpacks/      MP YAML loader, MPB render, .pak builder/installer
vcfops_extractor/            Reverse flow — extract live dashboards into bundles
```

Every package follows the same skeleton:

```
vcfops_<type>/
  __init__.py
  __main__.py    → cli.main()
  loader.py      → YAML schema → dataclass, validate
  client.py      → REST client
  cli.py         → validate, list, sync, delete
```

## Content (YAML source of truth)

Authored content. Each directory has its own author agent.

```
supermetrics/                Super metric YAML
customgroups/                Custom group YAML
views/                       List view YAML
dashboards/                  Dashboard YAML
symptoms/                    Symptom definition YAML
alerts/                      Alert definition YAML
recommendations/             Remediation recommendation YAML
reports/                     Report definition YAML
managementpacks/             Management pack YAML (MPB builder input)
```

## Distribution

```
bundles/                     Bundle manifests (input to vcfops_packaging build)
dist/                        Built distribution zips (gitignored)
designs/                     Approved MP / content design artifacts (mp-designer output)
```

## Knowledge

```
context/                     Topical background — read on demand
  README.md                  Index of context files
  rules_*.md                 Hard-won operational rules by category
  *.md                       Topical references (wire formats, API surface, etc.)
docs/                        Source-of-truth references
  vcf9/                      Extracted VCF 9 documentation markdown
  operations-api.json        Public Suite API OpenAPI spec
  internal-api.json          Internal (unsupported) API OpenAPI spec
references/                  Allowlisted external reference clones (gitignored;
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