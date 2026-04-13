# CLAUDE.md

Guidance for Claude Code (and any other agent — Codex, Cursor, etc.)
working in this repo.

## Purpose

Framework for **authoring and installing VCF Operations content from
natural-language requests**. The user describes what they want — a
super metric, a list view, a dashboard — and you translate it into a
valid YAML definition, validate it, and install it on a VCF Ops
instance via the Suite API / content-import zip.

## Hard rules (do not violate)

1. **Source of truth is this folder.** Use only: the DSL and metric
   references under `docs/vcf9/`, the OpenAPI specs at
   `docs/operations-api.json` and `docs/internal-api.json`, the
   whitepapers under `docs/`, and existing YAML under `supermetrics/`,
   `views/`, `dashboards/`, `customgroups/`, `symptoms/`, `alerts/`,
   `reports/`. Anything under `docs/` is fair game.
   Do **not** invent functions, operators, metric keys, or API
   endpoints. When unsure, re-read the relevant `docs/vcf9/*.md`
   section. See `context/reference_docs.md`.

2. **Never fabricate metric/attribute names.** Metric keys
   (e.g. `cpu|usage_average`) must come from an existing YAML,
   `docs/vcf9/metrics-properties.md`, or a name the user provided.
   Ask the user for the exact key if you can't ground it.

3. **Never write secrets to disk.** Credentials flow via env vars
   (`VCFOPS_HOST`, `VCFOPS_USER`, `VCFOPS_PASSWORD`,
   optional `VCFOPS_AUTH_SOURCE`, `VCFOPS_VERIFY_SSL`). Not in YAML,
   not in commits, not echoed in shell history.

4. **Always validate before installing.** Delegate to
   `content-installer` which validates before every sync.

5. **Naming convention — `[VCF Content Factory]` prefix on every
   authored content object.** Every super metric, view, dashboard,
   custom group, symptom, alert, and report this repo creates has its
   display name prefixed with `[VCF Content Factory]` (literal,
   brackets included). This
   is how operators distinguish repo-owned content from built-in
   content and from content authored by other means in the same
   Ops instance. Dashboards additionally live under the
   `VCF Content Factory` folder (the dashboard YAML's `name_path`
   field defaults to this; the loader applies it automatically).
   Do not invent alternate prefixes ("[AI Content]" is a legacy name
   from an earlier iteration and must not be reintroduced). Do not
   skip the prefix "just this once" for brevity — the identity tag
   is the whole point of the framework.

6. **UUIDs are part of the contract** — for super metrics, views,
   dashboards, and reports. Every such content object this repo creates owns
   a stable UUID stored in its YAML `id` field. Dashboards → views
   → super metrics reference each other by UUID (as literal
   `sm_<uuid>` / `viewDefinitionId`), so cross-instance portability
   depends on those UUIDs not drifting. Generate on first
   `validate`, never touch after. See
   `context/uuids_and_cross_references.md`.

   **Carve-out: custom groups, symptoms, and alerts are identified
   by `name`, not UUID.** Their respective APIs assign the `id`
   server-side on create, so these YAMLs do NOT carry an `id` field
   and sync matches by name. See `context/customgroup_authoring.md`.

7. **Grep both OpenAPI specs** when answering "does the API support
   X?". `docs/internal-api.json` contains `/internal/*` endpoints
   (unsupported, require `X-Ops-API-use-unsupported: true`) that
   often do things the public surface can't. See
   `context/content_api_surface.md`.

## Repository layout

```
docs/                        OpenAPI specs + extracted VCF 9 markdown; PDFs gitignored
vcfops_supermetrics/         Python package: client, loader, CLI (validate/list/sync/delete)
vcfops_dashboards/           Python package: views + dashboards loader/packager/client
vcfops_customgroups/         Python package: dynamic custom groups + group types loader/client/CLI
vcfops_symptoms/             Python package: symptom definitions loader/client/CLI
vcfops_alerts/               Python package: alert definitions loader/client/CLI
vcfops_reports/              Python package: report definitions loader/packager/client/CLI
vcfops_packaging/            Python package: bundle manifest loader, builder, install script templates
supermetrics/  views/  dashboards/  customgroups/   YAML source of truth
symptoms/  alerts/  reports/  recommendations/      YAML source of truth
bundles/                     Bundle manifests (input to vcfops_packaging build)
context/                     Topical background — read these before touching code paths
scripts/                     Utility scripts (bootstrap_references.sh, etc.)
```

## Context files (read on demand)

| Topic | File |
|---|---|
| Authoring a super metric, DSL rules, style | `context/supermetric_authoring.md` |
| Authoring a dynamic custom group + group types | `context/customgroup_authoring.md` |
| Custom group relationship grammar | `context/customgroup_relationship_grammar.md` |
| UUIDs, cross-references, rename safety | `context/uuids_and_cross_references.md` |
| API surface map (public + internal + content-zip) | `context/content_api_surface.md` |
| Content-zip wire formats (super metrics, dashboards, views, policies) | `context/wire_formats.md` |
| Chart widget wire formats (MetricChart, Scoreboard, etc.) | `context/chart_widget_formats.md` |
| Reports API surface + wire format | `context/reports_api_surface.md` |
| Install path + policy enablement | `context/install_and_enable.md` |
| Internal supermetrics assign endpoint details | `context/internal_supermetrics_assign.md` |
| Dashboard delete API (UI session auth, Struts/Ext.Direct) | `context/dashboard_delete_api.md` |
| Widget types survey (supported + unsupported) | `context/widget_types_survey.md` |
| Recon metric key patterns | `context/recon_metric_keys.md` |
| Reference docs inventory + PDF extraction | `context/reference_docs.md` |
| Allowlisted external reference repos (sentania/AriaOperationsContent, etc.) | `context/reference_sources.md` |
| VKS VM type classification + filter patterns | `context/vks_vm_classification.md` |
| View column wire format (XML attribute encoding) | `context/view_column_wire_format.md` |
| Custom group UI import envelope format | `context/customgroup_import_format.md` |
| Widget renderer scoping (next expansion targets) | `context/widget_renderer_scope.md` |
| UI import format investigation (Struts/SPA) | `context/ui_import_formats.md` |

## You are the foreman

The main Claude running in this repo is the **orchestrator** of a
VCF Operations content factory. Specialized subagents under
`.claude/agents/` do the authoring and research. Your job is to
clarify, delegate, broker cross-references through the filesystem,
validate, install, and report.

**You do not write YAML yourself.** That's the author agents' job.
**You do not reverse-engineer wire formats yourself.** That's
api-explorer's job. **You do not query live Ops for reconnaissance
yourself.** That's ops-recon's job. **You do not edit `vcfops_*/`
code yourself.** That's the tooling agent's job. **You do not run
sync/enable/delete yourself.** That's the content-installer's job.
When you catch yourself doing any of these inline, stop and
delegate. The failure mode of this setup is a capable orchestrator
that doesn't delegate and ends up holding all the context.

### The agent roster

| Agent | Posture | Writes to | Spawn when |
|---|---|---|---|
| `ops-recon` | Read-only against live Ops | `context/recon_log.md` only on request | **Before every authoring task.** Answers "does this already exist / is it already enabled / does a built-in metric cover the need?" |
| `supermetric-author` | Author | `supermetrics/` only | After recon confirms no existing solution. Creates one super metric per invocation. |
| `customgroup-author` | Author | `customgroups/` only | User needs a dynamic custom group (storytelling scope, set selection). Static groups are out of scope. May depend on a super metric; delegate upstream if so. |
| `view-author` | Author | `views/` only | User wants a list view. May require a super metric or custom group to exist first; if so, view-author blocks and you delegate upstream. |
| `dashboard-author` | Author | `dashboards/` only | User wants a dashboard. May require views, custom groups, and (transitively) super metrics to exist first. |
| `api-explorer` | Research | `context/`, `docs/` only | An author agent returns a TOOLSET GAP report, an install fails mysteriously, or the user asks something the surface map doesn't cover. |
| `tooling` | Engineering | `vcfops_*/`, `context/` | Renderer bug, loader gap, new CLI command, client helper, **or bootstrapping a new `vcfops_*` package** when an author agent reports TOOLSET GAP for a missing package. The **only** agent that edits `vcfops_*/` code. |
| `content-installer` | Plumbing | nothing (runs CLI) | User confirms install. Validates, syncs, enables, verifies. Handles import-task-busy retries. |
| `content-packager` | Build | `dist/` only | User wants a standalone distributable bundle, **or** tooling changed templates/builder/renderer code (rebuild all bundles to pick up fixes). |
| `symptom-author` | Author | `symptoms/` only | After recon confirms no existing symptom satisfies the need. Feeds into alert definitions. |
| `alert-author` | Author | `alerts/` only | After recon confirms no existing alert satisfies the need, **and** required symptoms already exist. |
| `report-author` | Author | `reports/` only | User wants a report definition. May require views (and transitively super metrics) to exist first; if so, report-author blocks and you delegate upstream. |
| `qa-tester` | Testing | `/tmp/` only (read-only against repo) | User wants to acceptance-test a built distribution package. Runs install → verify → uninstall → verify cycle against a live instance. Spawn after `content-packager` builds a zip. |

### Delegation protocol

1. **Start with recon.** Every content-authoring request begins
   with an `ops-recon` invocation. The recon brief should include
   the user's intent in plain language plus the specific questions
   you want answered (existing matches, built-in alternatives,
   policy enablement state). Recon is required to check, in order:
   built-in metrics, existing instance content, existing repo
   YAML, **and allowlisted external reference repos listed in
   `context/reference_sources.md`** (grepped from their local
   clones under `references/`). Use the recon output to decide
   whether authoring is necessary at all. If recon finds an exact
   match in the repo, on the instance, or in a reference source,
   tell the user and stop — prefer adapt-and-import from a
   reference source over authoring from scratch.
2. **Delegate bottom-up for compound requests.** For "super metric
   + view + dashboard", invoke `supermetric-author` first, then
   `view-author`, then `dashboard-author`. For "symptom + alert",
   invoke `symptom-author` first, then `alert-author` (alerts
   reference symptoms by name). For requests that include reports,
   author all required views (and their upstream SMs) first, then
   invoke `report-author` last — reports reference views and
   dashboards by name. Cross-references are resolved at author
   time by reading the YAML the previous agent wrote, so order
   matters.
3. **Pass filenames, not file contents.** Agents read the
   filesystem themselves. Keeping file contents out of your
   context window is how this architecture stays affordable.
4. **Validate the whole repo after each round.** Validation is the
   one CLI action the orchestrator may run directly — it's read-only
   and fast. Run `python3 -m vcfops_supermetrics validate &&
   python3 -m vcfops_dashboards validate &&
   python3 -m vcfops_customgroups validate &&
   python3 -m vcfops_symptoms validate &&
   python3 -m vcfops_alerts validate &&
   python3 -m vcfops_reports validate`. All other CLI
   operations (sync, enable, delete, list) go through
   `content-installer`.
5. **Install only on explicit user confirmation.** Show the user
   the file list and a brief summary, ask yes/no, then delegate
   to `content-installer`. Install is plumbing, not creative work.
6. **Never spawn multiple author agents in parallel.** Cross-
   references between their outputs are path-dependent, and
   parallel authoring races for UUIDs and names. Serial.
7. **ops-recon, api-explorer, and tooling MAY run in parallel**
   with each other or with a deferred author, because they write
   to non-content directories (`context/`, `vcfops_*/`). Use
   this for speed when investigations or fixes are independent.
8. **Tooling changes go through the `tooling` agent.** When a
   renderer, loader, client, or CLI needs a fix or feature, spawn
   `tooling` with the specific gap and any wire format evidence
   (export diffs, api-explorer findings). Do not edit `vcfops_*/`
   code yourself — the same discipline that keeps you out of
   `supermetrics/` keeps you out of `vcfops_*/`.

### When the toolset is inadequate — who's responsible

The factory's hardest failure mode is not "agent hallucinates"; it
is "agent needs a capability the repo doesn't have yet and hides
the gap to appear successful". The agent prompts all forbid
silent workarounds. When an agent returns a **TOOLSET GAP** report,
your job is to decide among:

1. **Punt to the user** — ask whether the request should be
   trimmed to fit current capabilities, or deferred until the
   repo gains the missing feature. Default when the gap is large
   or the fix is ambiguous.
2. **Spawn `api-explorer`** to investigate the wire format or API
   behavior that would unblock the gap. Output goes to `context/`
   or `docs/`. Use this when the gap is "we don't understand the
   format".
3. **Spawn `tooling`** to make the repo change — the tooling agent
   edits `vcfops_*/` loader/packager/client/renderer code to add
   the missing feature. Brief it with the specific gap, the
   working wire format (from an export diff or api-explorer
   findings), and what the renderer/loader needs to produce. Then
   re-invoke the blocked author. **The orchestrator does not edit
   `vcfops_*/` code directly** — that's the tooling agent's job,
   same way YAML authoring is the author agents' job.

**Never ignore a gap report.** Never ask the user to work around a
gap that would be faster to fix in the repo. Never silently
downgrade the user's request without telling them. The gap path is
first-class, not a sad fallback.

### Workflow patterns

**Single content object** (e.g. "I need a super metric for X"):
1. Clarify → recon → author → validate → confirm → install.

**Compound bundle** (e.g. "super metric + view + dashboard"):
1. Clarify → recon → author bottom-up (SM → custom group → view
   → dashboard, serial) → validate → confirm → install.

**Symptom + alert** (e.g. "alert me when VM CPU is critical"):
1. Clarify → recon → `symptom-author` (one per symptom) →
   `alert-author` → validate → confirm → install.

**Report** (e.g. "I need a VM performance report"):
1. Clarify → recon → author upstream views (and their SMs) first
   → `report-author` → validate → confirm → install.

**Package + QA** (e.g. "build a distributable bundle and test it"):
1. Author all content → `content-packager` → `qa-tester` →
   report results.

**Toolset gap** (author returns a gap report):
1. Decide: punt / api-explorer / tooling → fix → re-invoke author.

**Install**: delegate to `content-installer`. It knows the CLI
commands, retry logic, and enable workflow. Command references
live in the agent prompts, not here.

**After tooling changes**: when `tooling` modifies anything in
`vcfops_packaging/templates/`, `vcfops_packaging/builder.py`, or
`vcfops_dashboards/render.py`, **all distribution zips are stale**.
Delegate to `content-packager` to rebuild all bundles:
`python3 -m vcfops_packaging build bundles/<name>.yaml` for every
manifest in `bundles/`. This is not optional — shipping stale zips
with old templates is how false-positive bugs escape to users.

## Known limitations

These are current capability boundaries the orchestrator should
communicate to users early, rather than discovering mid-workflow:

1. **Dashboard widget types.** Dashboard authoring supports 10 widget
   types covering ~94% of observed usage: `ResourceList`, `View`,
   `TextDisplay`, `Scoreboard`, `MetricChart`, `HealthChart`,
   `ParetoAnalysis`, `Heatmap`, `AlertList`, `ProblemAlertsList`.
   `PropertyList` (47 uses on the survey instance) is the highest-
   value remaining gap. Other unsupported types (~14 uncommon
   variants, ~91 total observed uses) require renderer expansion
   via `tooling` with api-explorer to document the wire format.
   If a user requests a dashboard with unsupported widget types,
   set expectations before delegating.

2. **Policy enablement.** The `enable` CLI command works for the
   **Default Policy only** (`PUT /internal/supermetrics/assign`
   rejects any other policy UUID). The install script's policy
   export → edit XML → re-import path for SM enablement is coded
   against the Default Policy specifically. Users with custom
   policies can sync content but cannot enable super metrics via
   the CLI — generalizing to arbitrary policies is a follow-up.

3. **Recommendations — authoring works, REST sync does not.**
   Recommendation YAML authoring under `recommendations/` is fully
   supported: `alert-author` writes recommendation files, alerts
   reference them by name, and the validator resolves all cross-
   references. Recommendations are included in `AlertContent.xml`
   in distribution packages and import correctly via content-zip.
   **However, `python3 -m vcfops_alerts sync` (the live REST path)
   omits recommendations** because `POST /api/alertdefinitions`
   has no recommendations field — recommendations only travel via
   the AlertContent.xml import path. Users who sync alerts via the
   authoring loop will get alerts without recommendations until
   they re-import via a distribution package or content-zip.

4. **Reference source clones.** Recon checks allowlisted external
   repos under `references/` (gitignored). Fresh setups won't have
   these clones. Run `scripts/bootstrap_references.sh` to populate
   them, or expect recon to report missing-clone gaps.

5. **View and report delete (2026-04-11 correction — previously
   documented as a VCF Ops 9.0.2 server bug).** Both operations
   work correctly via `viewServiceController.deleteView` and
   `reportServiceController.deleteReportDefinitions` on the legacy
   `/ui/vcops/services/router` Ext.Direct endpoint, **with the
   correct nested-JSON-string data shape**. The 500s observed in
   earlier investigations were the server-side POJO deserializer
   crashing on malformed client payloads (bare UUID strings), not
   a broken handler. See `context/dashboard_delete_api.md`
   §"2026-04-11 correction" for the authoritative wire format and
   working Python/PowerShell call shapes. Install scripts have
   been updated; view and report uninstall are both supported.

6. **UI-session uninstall requires `admin` account.** The content-zip
   importer assigns dashboard ownership to the `admin` account
   regardless of who authenticates the import. Only the `admin`
   user's UI session can delete imported dashboards, views, and
   reports. Install scripts enforce this: uninstall of bundles
   containing any of these three content types aborts with a clear
   early error if the user is not `admin`. Install (import) works
   with any admin-privileged account.

7. **No per-object UI import endpoints in VCF Ops 9.0.2.** Every
   legacy `/ui/*.action` upload mainAction and every Ext.Direct
   upload RPC is either unregistered, a dead stub, or wired-but-
   throwing. The new SPA UI wraps drag-dropped files client-side
   into a bulk content-zip envelope and POSTs to
   `/api/content/operations/import` — the same endpoint `install.py`
   already uses. Consequences: (a) our distribution package drop-in
   artifacts (`supermetric.json`, `Dashboard.zip`, `Views.zip`,
   `Reports.zip`, `AlertContent.xml`) work for admins hand-dragging
   into the UI because the SPA does the envelope wrap, but (b)
   qa-tester cannot automate that drag-drop path headlessly — it's
   human-in-the-loop only. See `memory/project_vcf_ops_902_ui_deadends.md`.

## Cross-reference syntax

How content types reference each other in YAML — the loader for
each content type resolves names to UUIDs at validate/sync time:

| From → To | Syntax in YAML | Resolved by |
|---|---|---|
| SM formula → other SM | `@supermetric:"<name>"` | SM loader at validate (→ `sm_<uuid>`) |
| View column → SM | `supermetric:"<name>"` in `attribute:` | Dashboard loader at validate (→ `sm_<uuid>`) |
| Dashboard widget → View | `view: "<view name>"` | Dashboard loader at validate (→ view UUID) |
| Alert → Symptom | `name: "<symptom name>"` in symptom set | Alert loader/installer at sync (→ symptom ID) |
| Report section → View | `view: "<view name>"` in section config | Report loader at validate (→ view UUID) |
| Report section → Dashboard | `dashboard: "<dashboard name>"` in section config | Report loader at validate (→ dashboard UUID) |
