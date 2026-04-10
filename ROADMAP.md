# Roadmap

Tracking what the VCF Content Factory can do today, what's next, and
what's on the horizon. Updated as capabilities land.

## Done

- [x] **Super metric pipeline** — author → validate → sync → enable
      on Default Policy → delete. 16 SMs on lab instance.
- [x] **Custom group pipeline** — author → validate → sync. Dynamic
      groups with property/stat/tag/relationship rules.
- [x] **View pipeline (list type)** — author → validate → sync →
      delete. Summary rows, SM column auto-prefix.
- [x] **Dashboard pipeline** — author → validate → sync → delete.
      View + ResourceList widgets, self-provider pin, widget
      interactions, folder placement, shared by default.
- [x] **Delete capability** — dashboards (Struts action) and views
      (Ext.Direct RPC) via UI session client. CLI commands
      `delete-dashboard` and `delete-view`.
- [x] **Ops recon** — pre-authoring check against live instance,
      repo YAML, and external reference repos.
- [x] **Reference source integration** — allowlisted repos
      (sentania/AriaOperationsContent, etc.) checked before authoring.
- [x] **Content-zip import path** — UUID-preserving import for SMs,
      views, dashboards. Marker discovery, sharing config, i18n
      bundles.

## In Progress

- [ ] **Distributable packaging** — standalone install bundles with
      Python + PowerShell scripts (bash dropped — couldn't do zip
      assembly natively). VKS Core Consumption is the first package.
      Standard pattern established, install scripts proven against lab.
- [ ] **Bundle manifests** — declarative YAML files under `bundles/`
      that declare which SMs, views, dashboards, and custom groups
      belong to a distribution package. Turns packaging into a CLI
      command (`python3 -m vcfops_packaging build bundles/<name>.yaml`)
      instead of an agent task. Enables deterministic CI builds.
      The packager agent's role shifts from building packages to
      authoring bundle manifests + install script templates.
- [ ] **Alert & symptom agents** — agent prompts written
      (`symptom-author`, `alert-author`). No `vcfops_alerts/` or
      `vcfops_symptoms/` tooling packages yet.

## Next Up

### Chart widgets
Dashboard renderer only supports View and ResourceList widget types.
Chart widgets (line, bar, sparkline, topN) are the biggest visual
gap — they'd unlock trend dashboards and capacity views. Requires
reverse-engineering the chart widget config shape from an exported
dashboard.

### Alerts & symptoms tooling
The REST API (`/api/symptomdefinitions`, `/api/alertdefinitions`) has
full CRUD — much cleaner than the dashboard/view situation. Need
`vcfops_symptoms/` and `vcfops_alerts/` packages with loader, CLI,
and client. Agent prompts are ready to go.

### Sync dry-run & orphan cleanup
- `sync --dry-run` — show what would change on the instance without
  importing. Compare repo YAML to instance state.
- `orphan` command — list content on the instance with the
  `[VCF Content Factory]` prefix that has no corresponding YAML in
  the repo. Helps catch stale content after renames or deletions.

### Non-Default Policy enablement
`PUT /internal/supermetrics/assign` only works on Default Policy
(API returns 400 for any other policy UUID). Enabling SMs on custom
policies requires the policy export/import XML path
(`GET /api/policies/export` → modify XML → `POST /api/policies/import`).

## Future

### Notification rules
Natural companion to alerts. API has full CRUD
(`/api/notifications/rules`). "Alert fires → email/webhook/SNMP."
Agent + tooling package needed.

### Tests & CI
Zero automated tests today. Priority areas:
- Renderer output (XML/JSON) against known-good exports
- Loader YAML parsing edge cases
- Content-zip assembly (marker, structure, sharing)
- CI pipeline: run `validate` on all content per commit/PR
- CI package builds: on tag, read bundle manifests, render + assemble
  zips, publish as release assets to a distribution repo
  (e.g. `sentania/vcf-content-factory`)

### Multi-instance deploy
Currently one instance via env vars. Needs:
- Named profiles (dev/staging/prod)
- Per-profile credentials (vault integration or profile files)
- Deploy-to-all or selective targeting

### Content versioning & changelog
No version tracking per content object. Ideas:
- Semantic version field in YAML (informational)
- Auto-generated changelog from git history
- "What changed since last deploy" diff report

### Non-VMWARE adapter content
All current content targets the VMWARE adapter. Untouched adapters
with content potential:
- NSXTAdapter — network visibility
- KubernetesAdapter — workload monitoring
- Container adapter — container-level metrics
- CASAdapter — cloud automation

### Additional widget types
Beyond View and ResourceList:
- Scorecards / health charts
- Heat maps
- Topology widgets
- Text/image/iframe widgets

### Reports
Views can feed scheduled PDF/CSV reports. No tooling for report
definition authoring or scheduling.

### Automation actions
Runnable remediation actions triggered by alerts. Requires
understanding the action adapter framework.
