# Roadmap

Tracking what the VCF Content Factory can do today, what's next, and
what's on the horizon. Updated as capabilities land.

## Done

### Content types — full pipeline (author → validate → install → uninstall)

- [x] **Super metrics** — author → validate → content-zip sync →
      enable on Default Policy → delete. 19+ authored to date.
      UUID-stable cross-instance.
- [x] **Dynamic custom groups** — author → validate → REST sync →
      delete. Property / stat / tag / relationship rules.
- [x] **List views** — author → validate → content-zip sync →
      delete. Summary rows, SM column auto-prefix, bar/pie/donut/trend
      view modes, self-provider widget support.
- [x] **Dashboards** — author → validate → content-zip sync →
      delete. 10 widget types supported (ResourceList, View,
      TextDisplay, Scoreboard, MetricChart, HealthChart,
      ParetoAnalysis, Heatmap, AlertList, ProblemAlertsList) covering
      ~94% of observed live usage. Widget interactions, self-provider
      pin, folder placement, shared-by-default.
- [x] **Symptoms** — author → validate → REST sync → delete.
      Metric (static + dynamic) and event-based conditions.
- [x] **Alert definitions** — author → validate → REST sync →
      delete. Tiered severity via symptom sets, impact badges,
      `SYMPTOM_BASED` criticality.
- [x] **Report definitions** — author → validate → content-zip
      sync → delete (via Ext.Direct `reportServiceController.deleteReportDefinitions`
      with the corrected bare-dict data shape).
- [x] **Recommendations** — authoring infrastructure and first
      content shipped. Loader, dataclass, render, CLI, and bundle
      schema are all complete; six Synology recommendations
      currently live under `recommendations/`, wired through alerts
      via `{name, priority}`. REST-sync gap on recommendation
      attachment remains open — see "Next Up".

### Framework infrastructure

- [x] **Ops recon** — pre-authoring read-only check against live
      instance, repo YAML, and external reference repos.
- [x] **Reference source integration** — allowlisted community repos
      (sentania/AriaOperationsContent, brockpeterson, tkopton,
      dalehassinger, johnddias) checked before authoring.
- [x] **Content-zip import path** — UUID-preserving import for SMs,
      views, dashboards, reports. Marker discovery, sharing config,
      i18n bundles, admin-owner stamping, ghost-state retry.
- [x] **Delete pipeline** — dashboards via Struts `deleteTab`, views
      + reports via Ext.Direct RPC with the corrected nested-JSON-
      string data shape documented in `context/dashboard_delete_api.md`.
      Super metrics and custom groups via REST DELETE. Zero 500s
      across the QA acceptance cycle on both Python and PowerShell.
- [x] **Bundle manifest system** — declarative `bundles/*.yaml` files
      declare which content objects belong to a distribution package.
      Packager reads the manifest, resolves cross-references,
      renders all wire formats, and produces a distributable zip.
      Four first-party bundles currently ship: vks-core-consumption,
      vm-performance, capacity-assessment, environment-config-status.
      Third-party / extracted bundles live under `bundles/third_party/`
      (e.g. idps-planner via the `vcfops_extractor` reverse flow).
- [x] **Multi-bundle distribution packaging** — extract any number of
      bundle zips into the same directory, run `install.py` once,
      get a multi-select checklist (all pre-checked), single
      credential prompt, per-bundle loop. No content file collisions.
- [x] **Community-native drag-drop artifacts** — each bundle ships
      with `supermetric.json`, `customgroup.json`, `Views.zip`,
      `Dashboard.zip`, `Reports.zip`, `AlertContent.xml` at the
      bundle root in the filenames community admins recognize from
      reference packages. Admins who don't trust the installer can
      drag these directly into the VCF Ops UI import dialogs.
- [x] **Branded zip filenames** — `[VCF Content Factory] <Display Name>.zip`
      auto-derived from the bundle slug via title-case + acronym set.
      Matches the `[VCF Content Factory]` content-naming convention
      applied inside the zip.
- [x] **Python `install.py` installer** — bootstrap venv for
      `requests`, discover instance marker, authenticate, import
      content via content-zip or REST per content type, enable SMs
      via policy export/edit/re-import round-trip, verify enablement,
      uninstall via admin UI session. **6/6 QA acceptance against
      the live lab.**
- [x] **PowerShell `install.ps1` installer** — full parity with
      `install.py`. Supports PS 5.1 and PS 7+. Four PS-specific
      bugs found and fixed during acceptance (see `memory/
      feedback_powershell_idioms.md`). **6/6 QA acceptance on
      PS 7.5.1.**
- [x] **QA framework** — `qa-tester` agent runs end-to-end
      install / uninstall / multi-bundle / admin-guard /
      SM-enable-verification cycles against a live instance with
      a clean teardown. Acceptance log lives in
      `context/qa_log.md` with per-run commit hashes.

### Hard-won wire format knowledge (documented, authoritative)

- [x] **View / report delete data shape** — the 9.0.2 "server is
      broken" narrative was wrong. Server expects a nested-JSON-
      string shape: `"data": [{"viewDefIds": "[{\"id\":\"...\",\"name\":\"...\"}]"}]`
      for views, `"data": {"reportDefIds": "..."}` (bare dict, not
      array) for reports. See `context/dashboard_delete_api.md`
      §"2026-04-11 correction".
- [x] **VCF Ops 9.0.2 UI dead-end catalog** — no per-object UI import
      endpoints exist in 9.0.2; the SPA client-side-wraps drag-drops
      into the bulk content-zip envelope. Several legacy Struts
      actions are silent traps (`customGroup.action?saveCustomGroup`
      returns `{result: "ok"}` without persisting). See
      `context/struts_exploration_backlog.md`.
- [x] **Dashboard user ID stamping** — server rewrites
      `userId`/`lastUpdateUserId` on content-zip import regardless
      of input value; any syntactically valid UUID works for the
      drag-drop variant. Framework stamps a deterministic UUID5
      (`b58a71ee-e909-5b40-a355-9e199e6f0f53`) so it's grep-able.

## In Progress

### Management pack authoring (MPB-compiled `.pak`)
New capability: author REST-adapter management packs as YAML and
compile them into `.pak` files via the built-in Management Pack
Builder (MPB). Three new agents in place (`api-cartographer`,
`mp-designer`, `mp-author`) plus `vcfops_managementpacks` package
with validate / render / render-export / build / install / uninstall
subcommands. Two learning targets in flight:

- **Synology DSM** — first MP, used to shake out the framework.
  Render, build, and install wired end-to-end; chainingSettings
  wire format parity verified against HoL-2501-12 reference after
  2026-04-19 renderer fix.
- **UniFi Network API** — second MP, framework-generalization
  test. API mapped against the devel controller; design in
  `designs/unifi-mp-v1.md`.
- **GitLab** — untracked third MP under `managementpacks/`
  exploring CI/CD observability.

Open work: the **adapter JAR gap** (`<adapter_kind>_adapter3.jar`
contains the adapter kind baked into its package path and cannot
be regenerated without the MPB server-side build endpoint); lab
verification of the 2026-04-19 chain1 renderer fix; and the
manual-UI MPB tasks tracked under `memory/project_mpb_manual_ui_tasks_pending.md`.

## Next Up

### PropertyList dashboard widget
Highest-value remaining widget gap. 47 live observed uses on the
survey instance. Structurally reuses Scoreboard's `MetricSpec`
machinery + adds `is_string_metric: bool` to the metric spec dataclass.
Full scoping in `context/widget_renderer_scope.md`. Lifts renderer
coverage from ~94% to ~95.5%. Estimated ~120 lines across
`vcfops_dashboards/loader.py` and `render.py`.

### ResourceRelationshipAdvanced + SparklineChart widgets
Follow-on to PropertyList per the widget scoping doc. Both are
cheap: ResourceRelationshipAdvanced is a config-dict builder with
no metric references (~60 lines), SparklineChart is essentially
free once PropertyList adds `is_string_metric` to MetricSpec.
Together with PropertyList: three-widget batch that lifts coverage
~2 percentage points and covers the most common detail-page
dashboard patterns.

### Recommendation REST install path
Known gap: `install.py::_install_alerts` uses `POST /api/alertdefinitions`
which doesn't carry recommendation references in the alert wire body.
Recommendations render correctly in `AlertContent.xml` (drag-drop
path) and would install correctly via a bulk content-zip envelope,
but the current REST-per-object path silently drops them. Fix
requires either api-explorer verification of a `POST /api/recommendations`
endpoint, or switching `_install_alerts` to the content-zip envelope
(matching how reports are installed).

### Non-Default Policy enablement
The install script's SM enable path (`enable_sm_on_default_policy`)
does policy export → edit XML → re-import, but it's hard-coded to
look up the Default Policy. Generalizing it to a user-specified
target policy is mostly string-threading work — the underlying
logic already handles arbitrary policy XML.

### Sync dry-run & orphan cleanup
- `sync --dry-run` — show what would change on the instance without
  importing. Compare repo YAML to instance state.
- `orphan` command — list content on the instance with the
  `[VCF Content Factory]` prefix that has no corresponding YAML in
  the repo. Helps catch stale content after renames or deletions.

## Future

### IntSummary + Skittles widget batch
8 IntSummary variants + Skittles (summary-page widget types). Can
be implemented together as one ~120-line batch once there's a
concrete user request that needs them. See `widget_renderer_scope.md`
appendix for the breakdown.

### Deferred widget types
`LogAnalysis`, `MetricPicker`, `TagPicker` all have portability or
downstream-widget complications per the scoping survey. Document as
limitations rather than targeting implementation.

### Won't-do widget types
`ResourceRelationship` (legacy, superseded by Advanced),
`TopologyGraph` (NSX-only), `MashupChart` (UI-state-only config),
`Geo` (geo-adapter dependency), `ContainerOverview`/`ContainerDetails`
(vRNI-only). Document as permanent limitations.

### Notification rules
Natural companion to alerts. API has full CRUD
(`/api/notifications/rules`). "Alert fires → email/webhook/SNMP."
Agent + tooling package needed.

### Tests & CI
Zero automated tests today. Priority areas:
- Renderer output (XML/JSON) against known-good exports
- Loader YAML parsing edge cases
- Content-zip assembly (marker, structure, sharing)
- `AlertContent.xml` serializer against ground-truth exports
- CI pipeline: run `validate` chain on all content per commit/PR
- CI package builds: on tag, read bundle manifests, render + assemble
  zips, publish as release assets

### Multi-instance deploy
Currently one instance via env vars. Needs:
- Named profiles (dev/staging/prod)
- Per-profile credentials (vault integration or profile files)
- Deploy-to-all or selective targeting

### Content versioning & changelog
No version tracking per content object. Ideas:
- Semantic version field in bundle YAML (currently deferred per
  the display-name rename session decision)
- Auto-generated changelog from git history
- "What changed since last deploy" diff report

### Non-VMWARE adapter content
All current content targets the VMWARE adapter. Untouched adapters
with content potential:
- NSXTAdapter — network visibility
- KubernetesAdapter — workload monitoring
- CASAdapter — cloud automation
- VMWARE_INFRA_HEALTH — license / capacity reporting

### Automation actions
Runnable remediation actions triggered by alerts. Requires
understanding the action adapter framework. Companion to
recommendations — where recommendations tell an operator what to
do, actions let them click a button to have Ops do it.
