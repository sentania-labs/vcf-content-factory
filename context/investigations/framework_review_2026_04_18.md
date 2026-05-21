# Framework review — 2026-04-18

Reviewer: orchestrator (research pass, read-only).
Scope: everything except `designs/synology-mp-v1.md` (mp-designer owns that
artifact in parallel). Covers `vcfops_*/`, `.claude/agents/`,
`.claude/commands/`, `.claude/skills/`, bundle manifest + `bundles/`,
install scripts, `context/`, reference-source machinery, `vcfops_extractor`,
qa-tester, the cross-content validation chain, and the known-limitations
enumeration in `CLAUDE.md`.

Method: for each capability area, cite the concrete current choice, then
classify as **framework-general**, **shortcut low-cost**, **shortcut
high-cost**, or **unknown / needs capture**.

---

## 1. Executive summary

The factory has strong bones in a handful of places (packaging handler
registry, bundle manifest schema, packaging-time dependency audit, two-tier
UUID/name identity contract driven by server behavior) and accumulated
shortcuts in others (copy-pasted clients, copy-pasted install template,
policy-enablement hard-wired to Default, naming prefix enforced only by
documentation and the factory's own good behavior, MP bundles living
outside the bundle manifest schema, SM-name→UUID map pulled from the whole
repo rather than the bundle at render time).

Classification count across the 20 axes plus the CLAUDE.md
known-limitations pass:

- Framework-general: 6 axes (handler protocol + discovery; bundle schema
  content-type list; cross-ref resolution pattern for name→id types;
  reference-sources allowlist shape; extract flow; packaging dependency
  audit).
- Shortcut low-cost: 7 axes (auth/session duplication across clients;
  naming-prefix enforcement documentation-only; install template 2.5k-line
  fork of client.py; CLI uniformity rough edges; error taxonomy ad hoc;
  PS/Python template parity; bundle README generation).
- Shortcut high-cost: 4 axes (policy enablement = Default only; MP bundles
  not in the bundle schema; content-zip vs REST split for install path;
  dashboard widget renderer is an elif chain).
- Unknown / needs capture: 3 axes (widget types the renderer hasn't met;
  recon scope for cross-instance + dist/; reference-source drift detection).

The single highest-leverage shortcut is the `install.py` / `install.ps1`
template (≈5000 lines combined, maintained in parallel with the
factory-side clients). Everything else in this review is cheaper to
address but that one fork is where divergence between "framework behavior"
and "distribution behavior" will bite first.

---

## 2. Axis-by-axis review

### 2.1 Per-content-type package split

Current choice: each content type has its own `vcfops_<type>/` package
with `loader.py`, `client.py`/`handler.py`, and `cli.py`. Handlers plug
into a shared registry in `vcfops_packaging/handler.py:98-229` via a
duck-typed `ContentHandler` base, auto-discovered by scanning `sys.path`
for `vcfops_*/handler.py`.

The handler-registry side is **framework-general**: adding a new content
type requires only a new `vcfops_<type>/handler.py` with `HANDLER =`,
which `vcfops_packaging/syncer.py:22` picks up with no orchestrator
changes. Good. Sync order is declared by the handler, not hard-coded.

The per-package duplication beneath that (auth, env-var read, CSRF,
page iteration) is a separate axis — see 2.2.

Classification: **framework-general** for the handler protocol;
shortcut surfaces are captured in other axes.

### 2.2 Authentication in clients

Current choice: three independent `from_env` + `authenticate` + `_request`
+ `_ensure_auth` reimplementations:

- `vcfops_supermetrics/client.py:34-102` (VCFOpsClient, primary).
- `vcfops_customgroups/client.py:30-101` (VCFOpsCustomGroupClient).
- `vcfops_symptoms/client.py:28-90` (VCFOpsSymptomsClient).
- `vcfops_alerts/client.py:32-94` (VCFOpsAlertsClient).

The bodies of the four classes are byte-near copies of each other — same
`{"username", "password", "authSource"}` POST, same `vRealizeOpsToken`
header, same 401-retry loop, same env-var contract through
`vcfops_supermetrics/_env.py`. Reports and dashboards take the cheaper
path and just reuse the SM client (`vcfops_reports/client.py:28`,
`vcfops_dashboards/client.py:12`).

Three reasons the copies exist historically — each still present in the
code today:

1. The four clients predate the reports/dashboards pattern of layering
   free functions on top of VCFOpsClient.
2. Each content type uses a different API wrapper name pattern for
   `list_*` / `find_by_name`, so the copies feel locally cohesive.
3. The handler registry currently tells each handler to construct its own
   client — the `session` passed into `ContentHandler.sync` is always a
   `VCFOpsClient`, but `VCFOpsCustomGroupClient.from_env()` gets built
   separately per-handler (documented honestly at
   `vcfops_packaging/handler.py:108-111`).

Classification: **shortcut low-cost**. The factory-general alternative is
one shared base class (or set of module-level functions) for
`authenticate` / `_request` / `from_env`, with each content type's client
becoming a thin facade that adds only the type-specific REST verbs. The
tooling delta is small because the call sites are already compatible —
every `VCFOps*Client` exposes an identical `_request(method, path, **kw)`.

When VCF Ops adds a new auth mode (OAuth, service-account keys), four
classes need matching changes instead of one. Also matters for the
install-template fork — see 2.8.

Recommendation: delegate to `tooling` to extract
`vcfops_supermetrics._env` into a sibling module (e.g. a shared
`_auth.py` inside `vcfops_packaging/` or a new `vcfops_common/`) and have
the four clients subclass or compose it. Do not invent the abstraction
here — flag it and let Scott decide whether to pay.

### 2.3 Policy enablement — Default Policy only

Current choice: `VCFOpsClient.enable_supermetric_on_default_policy`
(`vcfops_supermetrics/client.py:277-430`) and
`enable_builtin_metrics_on_default_policy` (line 432-563) both derive
their target policy via `get_default_policy_id` (line 146-153), which
hunts for `defaultPolicy: true` and errors otherwise. The `enable` CLI
command takes no `--policy` flag
(`vcfops_supermetrics/cli.py:103-111`). The install-template script
mirrors this (`templates/install.py:465-472, 503-812`).

The in-code justification is at lines 287-292:
> NOTE: the policyIds variant returns 200 but does NOT enable
> content-zip-imported SMs on any policy

That is a real server behavior for the internal assign endpoint — `PUT
/internal/supermetrics/assign` with `policyIds` is a no-op for
content-zip SMs. But the policy-export/edit-XML/re-import path
(lines 333-430) is NOT Default-specific — it only looks Default-specific
because `get_default_policy_id` refuses to return anything else and
because `_export_default_policy_zip` passes only the default policy's ID
as the `id=` export param.

Classification: **shortcut high-cost**. The framework-correct shape is:

- `enable` takes `--policy <name or id>` with Default as default.
- The export/edit/import path is policy-agnostic — it already operates
  on whatever ZIP the server returns.
- Step 1 (`PUT /internal/supermetrics/assign`) remains Default-scoped
  because that's the documented server constraint today, but that step
  is about resource-kind assignment, not policy enablement — so it can
  run once against Default (or any policy that hosts the adapter) and
  the subsequent policy-export/import loop can target arbitrary policies.

Cost: non-trivial because the XML injection at lines 355-414 hunts the
FIRST `<Policy>` inside `<Policies>`, which is implicitly the default.
Iterating to "find the policy whose `<id>` matches the target" is
mechanical but needs to be grounded in a fresh export from a policy
export on the instance — `api-explorer` should verify that multi-policy
exports produce a single zip with multiple `<Policy>` elements or
require per-policy export params.

Scott's call: this is deferred until a user cares, but
CLAUDE.md §Known-limitations #2 frames it as "server constraint", which
is not strictly accurate. Reframe the limitation as "policy targeting is
not yet exposed as a CLI surface" so future readers don't think the
server is the blocker.

Open question for Scott: do we prioritize multi-policy support now, or
stay Default-only until a specific user asks? Either answer is defensible
— what matters is labeling the gap honestly.

### 2.4 UUID contract asymmetry

Current choice: SMs, views, dashboards, reports carry stable client-side
UUIDs. Custom groups, symptoms, alerts are identified by name, with IDs
assigned server-side on create.

Evidence the asymmetry is API-forced, not a shortcut:

- `vcfops_symptoms/client.py:121-127`: `POST /api/symptomdefinitions`
  documented as "id must be absent or null".
- `vcfops_alerts/client.py:157-164`: same for alerts.
- `vcfops_customgroups/client.py:189-197`: `POST /api/resources/groups`
  returns server-assigned id, find-by-name is the only reconciliation.
- Reports have no POST/PUT at all — content-zip only
  (`vcfops_reports/client.py:1-18`).

So the split is real. The framework-general move is not to harmonize it
(can't) but to make the renaming semantics explicit per content type.
Rename safety today:

- UUID-carrying types: rename-safe (see loader docstring
  `vcfops_dashboards/loader.py:6-8`).
- Name-identified types: a rename in the YAML creates a new object; the
  old one orphans. There is no tombstone field, no `previous_names:` list.
  `upsert_group` at `vcfops_customgroups/client.py:218-243` matches by
  name only.

Classification: **framework-general** for the asymmetry itself (server-
forced); **shortcut low-cost** for the absence of a rename tooling path
on name-identified types. A `previous_names: [..]` field in the loader +
a find-by-previous-name fallback in each upsert would close the gap at
small tooling cost.

Recommendation: keep the asymmetry; add the `previous_names` escape
hatch when a real rename comes up. Don't preemptively build it.

### 2.5 Naming convention enforcement

Current choice: the `[VCF Content Factory]` prefix is enforced
**documentation-only** in the three main loaders. Evidence:

- `vcfops_supermetrics/loader.py`: no mention of the prefix
  (grep returned empty). `SuperMetricDef.validate` checks name non-empty
  and formula shape but not the prefix.
- `vcfops_dashboards/loader.py`: prefix literal appears only as
  `name_path: str = "VCF Content Factory"` (line 628) — the dashboard
  *folder*, not the dashboard-name prefix.
- `vcfops_symptoms/loader.py`, `vcfops_reports/loader.py`: prefix appears
  only in schema docstring examples.
- `vcfops_alerts/loader.py` is the one partial exception —
  `validate_symptom_refs` (line 277-294) uses the prefix to distinguish
  repo-owned from built-in symptoms for cross-ref enforcement.
- `vcfops_customgroups/loader.py:12`: the docstring example **still
  contains the retired `[AI Content]` prefix**. Latent bug or legacy
  comment.

The `factory_native: bool` field in the bundle manifest loader
(`vcfops_packaging/loader.py:274-280`) gates some behavior in the
packager — zip filename formatting (builder.py:513-518), provenance
rendering (builder.py:284-322) — but the prefix itself is never
mechanically verified against YAML names at load time.

Classification: **shortcut low-cost**. The framework-general move is a
`_require_vcf_content_factory_prefix(name, factory_native_scope)` helper
invoked in every loader's `validate()` when the loader is called from a
`factory_native: true` bundle. The delta is maybe 30 lines across six
loaders plus plumbing `factory_native` context into loader calls.

Consequence of leaving it: a user forgets the prefix, validate passes,
sync installs, and the content vanishes into the unprefixed pool — the
"identity tag" in CLAUDE.md §Hard-rules #5 is whatever the authoring
author happens to type. This is exactly the class of silent-failure the
project style guide warns against.

Also: clean up the `[AI Content]` example at
`vcfops_customgroups/loader.py:12` — doc bug per retired-name memory.

### 2.6 Dashboard widget renderer

Current choice: `vcfops_dashboards/render.py:1038-1067` dispatches widget
rendering through a fixed elif chain — ResourceList, View, TextDisplay,
Scoreboard, MetricChart, HealthChart, ParetoAnalysis, AlertList,
ProblemAlertsList, Heatmap. Each `_<name>_widget(...)` helper is a
bespoke function.

Classification: **shortcut high-cost**. The framework-general shape is a
widget-plugin interface — one function per type that takes
`(widget, kind_index, resource_index, views_by_name) -> dict`, registered
in a dict keyed by `widget.type`. Loader-side dataclass unions
(`ScoreboardConfig`, `MetricChartConfig`, etc.) already model each
widget's own config, so the refactor is mostly lifting
`_resource_list_widget` et al. into registered callables.

Cost is non-trivial because the current helpers also drive
`_collect_used_resource_kinds` (lines 1128-1166) which does per-widget
metric-kind extraction in a matching elif chain — the plugin interface
needs to cover both emit and introspect paths. Without that, adding a
new widget (`PropertyList` at 47 uses survey-wide is the
CLAUDE.md §Known-limitations #1 target) means three
coordinated edits in this file plus a loader-side `WidgetConfig`
dataclass.

Recommendation: spawn `tooling` when `PropertyList` or
`TopN`/`SparklineChart` becomes blocking; include refactor-to-plugin as
part of that work. Don't do it preemptively — the survey count for each
remaining type is small.

Open question for Scott: do we capture the refactor as a concrete
`tooling` brief now, or wait for the next widget request to force the
issue? I'd wait, but flagging.

### 2.7 Bundle manifest format

Current choice: `vcfops_packaging/loader.py:1-315` defines a schema with
content-type keys `supermetrics / views / dashboards / customgroups /
symptoms / alerts / reports / recommendations`, plus
`builtin_metric_enables`, plus attribution/provenance fields
(`author / license / source / factory_native / display_name`).

Management packs are NOT in that schema. `bundles/*.yaml` has no
`managementpacks:` key. MPs live in `managementpacks/` and are built via
a separate CLI (`vcfops_managementpacks build-pak`); there is no bundle
manifest that co-packages an MP with its supporting content (dashboards,
custom groups, symptoms) into a single distributable zip.

The IDPS Planner bundle (`bundles/third_party/idps-planner.yaml`) is a
content bundle extracted from a live lab — no MP involvement. The
Synology MP (`managementpacks/synology_dsm.yaml`) ships as a standalone
`.pak`, installed via `vcfops_managementpacks install-pak` on the `/ui/`
session, with no integrated content bundle.

Classification: **shortcut high-cost**. Third-party management packs in
the real world (vSAN Extended Health, Rubrik CDM, community vCommunity
pack) ship a .pak with:

- Adapter runtime.
- Bundled dashboards/views/SMs in the `content/` dir inside the .pak
  (per `vcfops_managementpacks/builder.py:40-60` docstring).
- Out-of-band README + install instructions.

The factory today supports the first two (MP builder stamps `content/`
inside the pak from referenced YAMLs — see
`vcfops_managementpacks/builder.py` Bundled Content section). But a user
asking "package Synology DSM + dashboards + alerts as one install" hits
two distinct loaders (packaging-loader for content, managementpack-loader
for MP) and two distinct builders (packaging-builder for content-zip,
managementpack-builder for .pak).

The framework-correct path is: bundle manifest gets a
`management_pack: <path>` field; if set, the packager produces a
.pak that embeds content instead of (or alongside) the content-zip. The
ADAPTER_JAR_GAP (`vcfops_managementpacks/builder.py:31-49`) and
MPB-design-chaining gaps (see 2.20) mean the MP side isn't yet stable
enough to merge schemas — but the schema entry should be reserved now
so that when MPB testing closes those gaps, we don't re-litigate the
manifest shape.

Recommendation: hold on schema merge until the MP capability plan
(MEMORY note `project_mp_capability_plan.md`) clears ADAPTER_JAR_GAP and
chaining. At that point, re-plan. Flag to Scott that the current bundle
manifest is content-only by design.

Open question for Scott: do we reserve `management_pack:` in the
manifest now as a forward hint, or wait until MPB capability is
shippable?

### 2.8 Install script template

Current choice: `vcfops_packaging/templates/install.py` is **2528 lines**;
`install.ps1` is **2555 lines** (counted). Both are static scripts
embedded verbatim in each distribution zip
(`vcfops_packaging/builder.py:28-31` confirms static, no stamping).

`install.py` reimplements — from scratch, not imported from the factory —
the VCFOpsClient auth flow (lines 310-345, `authenticate`, `_req`), the
marker-filename discovery (lines 351-401), the content-import polling
loop (lines 403-463), the policy-ID lookup (lines 465-472), the SM
enable on Default Policy (lines 503-812 — XML editing, zip
reconstruction), and the Ext.Direct UI-session delete calls for views /
reports / dashboards (lines 1024-1280).

The reason is plumbing-defensible (the distributed zip runs on a user's
laptop against any VCF Ops instance with zero factory dependencies) but
the execution is a parallel fork that MUST stay in sync with
`vcfops_supermetrics/client.py`, `vcfops_dashboards/client.py`, and
`vcfops_dashboards/ui_client.py`. When tooling discovers a new wire
quirk (ghost-state retry at
`vcfops_supermetrics/client.py:620-637`, for example), every fix
requires three parallel edits: the factory client, `install.py`, and
`install.ps1`.

Classification: **shortcut low-cost** to remediate at the code-gen level.
The framework-general move is template generation: the installer
scripts become Jinja2 (or similar) templates rendered from the factory
client code at build time, so a single source-of-truth for the wire
formats becomes the factory client + render tables. Or, alternately:
package the factory clients as a single-file zipapp dropped into the
distribution zip alongside the installer.

Cost: non-trivial as a refactor (two 2.5k-line forks converging into
one rendered file), but each week of drift is cheaper to prevent than
to audit later.

Recommendation: raise as a `tooling` brief when the next wire-format
fix forces a three-way edit. Until then, add an explicit CI check (or
at least a comment header in both scripts pointing at the source of
truth file to keep in sync) so drift is visible. The PS 5.1 compat
hard requirement (MEMORY `feedback_ps51_compat.md`) is what makes this
expensive — template generation can't target "PS 7 idiom" because
downstream Scott runs 5.1.

Open question for Scott: is template-generation worth paying for now,
or do we continue the parallel-fork model and rely on QA (qa-tester) to
catch drift post-hoc?

### 2.9 Content-zip as the canonical install path

Current choice: install paths are mixed.

- Super metrics: content-zip ONLY (forced by the UUID contract —
  `POST /api/supermetrics` reassigns UUIDs server-side;
  `vcfops_supermetrics/client.py:15-16`).
- Views + dashboards: content-zip (shared import, shared handler —
  `vcfops_dashboards/handler.py:1-17`).
- Reports: content-zip (no REST POST/PUT exists —
  `vcfops_reports/client.py:1-18`).
- Custom groups: REST POST/PUT (`vcfops_customgroups/client.py:189-217`).
- Symptoms: REST POST/PUT (`vcfops_symptoms/client.py:121-156`).
- Alerts: REST POST/PUT (`vcfops_alerts/client.py:157-208`).

The split is API-forced, not a shortcut (same reasoning as 2.4). The
content-zip path is the "universal" install path only for content types
whose server-side mutation endpoints refuse or reshape client-supplied
identity.

Classification: **framework-general**. The fact that import-task-busy
retry and marker-filename discovery live in one place
(`vcfops_dashboards/client.py`) and are shared by SMs, dashboards, and
reports is good factoring. CLAUDE.md §Hard-rules #4 ("always validate
before installing") and the retry-handling policy are uniform.

Minor shortcut: each REST path (customgroups/symptoms/alerts)
reimplements its own upsert-by-name loop. Centralizing the upsert-by-name
pattern in a shared helper is part of axis 2.2's remediation.

### 2.10 Recon scope

Current choice: `ops-recon.md:32-42` defines check order as built-in
metric → existing instance content → existing repo YAML → allowlisted
reference sources under `references/`.

Missing from that list:

1. Prior versions of the same content in the repo's git history.
2. Already-built artifacts under `dist/` (old zips that would collide
   by UUID or display name).
3. Cross-instance state — recon runs against one instance at a time; a
   multi-lab user gets no warning if the dashboard they want to author
   already exists on a sibling lab.

Classification: **unknown / needs capture** for items 2 and 3, and
**shortcut low-cost** for item 1 (git log is cheap and local).

Recommendation: add item 1 to `ops-recon.md` as a bullet under "check
order" the next time the prompt is edited. Items 2 and 3 are Scott-
decision territory — multi-instance recon is a user-story that hasn't
been requested, and `dist/` collision is hypothetically nice but the
factory rebuilds zips deterministically so UUID collision is already
prevented by the UUID contract (axis 2.4).

### 2.11 Reference sources trust model

Current choice: `context/reference_sources.md` is an allowlist. No
per-source trust tier (all sources treated equally), no drift detection,
no automated verification that local clones match upstream. The
bootstrap script (`scripts/bootstrap_references.sh`) clones and
optionally updates, but recon is told to grep whatever is on disk.

Classification: **framework-general** shape with one
**shortcut low-cost** enhancement. The allowlist + hard-rule
"local-only, no WebFetch" is solid; the rule "ops-recon may only consult
listed sources" is enforced by agent-prompt. Good.

The gap is drift: if `dalehassinger/unlocking-the-potential` updates its
MPB JSON designs and the local clone is stale, recon returns old data
and the factory may adapt stale content. No `last-pulled` timestamp is
tracked, and `bootstrap_references.sh --update` is operator-triggered.

Framework-general alternative: `scripts/bootstrap_references.sh
--check-age` reports local clone age, with ops-recon warning when the
local clone is older than N days. Low tooling cost, incremental.

Not suggesting a PKA-style trust-tier (whitelist/default/blacklist at
filing time) — that's Scott's PKA world, and this repo's allowlist is
narrower and already curated. Don't over-model.

### 2.12 Extract flow

Current choice: `vcfops_extractor/extractor.py` (2001 lines) walks
dashboard → views → super metrics via BFS, emits factory-shape YAML
under `bundles/third_party/<slug>/`, and writes a bundle manifest.
`/extract` slash command wraps it with interactive metadata collection
(author / license / source / description).

Seen-set + non-overwrite invariant (`extractor.py:175-219`) prevent
extracted content from shadowing factory-first-party content. UUIDs
preserved end-to-end so a re-import round-trips. Custom groups:
Phase 1 emits WARN only (documented at lines 16-17).

Classification: **framework-general** within its current scope (any
dashboard → any bundle). The any-instance-to-any-bundle posture holds
because the extractor reads via two client types (SM client for
`/api/supermetrics`, UI-session client for `/ui/dashboard.action`) both
of which are env-driven.

Gaps that are real but not shortcuts:

- Custom group extraction: deferred by design.
- Unsupported widget types: WARN + best-effort YAML; same limitation as
  the renderer (axis 2.6).
- No cross-content-type extract — extract only walks dashboard roots.
  Symptoms, alerts, reports, standalone super metrics all unreachable.

These are scope decisions, not shortcuts. Recommendation: leave as-is
unless a user asks for symptom/alert/report extract.

### 2.13 Cross-reference resolution

Current choice: mixed — name→UUID resolution happens in three different
places for three different content types.

- SM→SM references: resolved at SM loader validate time (bare name token
  becomes `sm_<uuid>` in the formula after the referenced SM is loaded).
  Implementation at `vcfops_supermetrics/loader.py:207-222` (`load_dir`
  hoists seen-names, the validator itself runs per-file).
- View column → SM: resolved at render time by building a
  `sm_map: dict[str, str]` from `load_dir()` of the supermetrics/
  directory (`vcfops_dashboards/render.py:365-379`). This is the one
  that matters for the bundle-scoping question below.
- Dashboard widget → View: resolved at bundle load time (dashboard
  validator takes `views_by_name` — `vcfops_packaging/loader.py:230-236`).
- Alert → Symptom: resolved at sync time by fetching the live instance's
  symptom list (`vcfops_alerts/client.py:125-155`).
- Alert → Recommendation: resolved at validate time from the
  `recommendations/` directory (`vcfops_alerts/loader.py:463-491`).
- Report → View, Report → Dashboard: resolved at validate time.

Classification: mixed — **shortcut low-cost**.

The framework issue: `render_views_xml`
(`vcfops_dashboards/render.py:365-379`) calls
`_sm_load_dir()` with no arguments, meaning it loads ALL SMs under
`supermetrics/` — not the subset belonging to the bundle being rendered.
If two bundles both define SMs with the same name (unlikely within the
factory, but possible across factory + third-party extracts), the
resolver silently picks one. The loader at
`vcfops_supermetrics/loader.py:212-222` already raises on duplicate
names, so the hazard is bounded to "name collision fails at load time
before render", which is decent — but the render call is still
implicitly global.

Recommendation: pass the bundle's SM list into render — at that point
the resolver scope matches the bundle scope. Tooling-delta is small
(thread `sm_map=` down from the caller in `vcfops_packaging/builder.py`
and `vcfops_dashboards/packager.py`).

### 2.14 CLI uniformity

Current choice: every package has `validate / sync / list / delete`, and
SM + alerts additionally have `enable` (SM) / `enable|disable` (alerts).
Exit codes are consistent at the `0 / 1 / 2` contract documented in
`vcfops_packaging/handler.py:30-33`.

Inconsistencies:

- `vcfops_supermetrics/cli.py` has `enable` as a top-level subcommand;
  `vcfops_alerts/cli.py` has `enable` + `disable` pair. Asymmetric but
  reflects API capability.
- `vcfops_reports/cli.py:112-121` returns 1 from its `delete` (documented
  NotImplementedError) rather than 2 — minor inconsistency with the
  "partial failure = 2" contract.
- `vcfops_dashboards/cli.py` exposes `delete-dashboard` and `delete-view`
  as separate subcommands; `vcfops_customgroups/cli.py` exposes `delete`
  (group) and `delete-type` is implicit. No uniform `--type` flag.
- JSON output: no package emits machine-readable JSON on stdout. All
  results are human-text.

Classification: **shortcut low-cost**.

The content-installer agent doesn't have to know per-package quirks
because it uses the handler protocol (axis 2.1); the CLIs are the
human-facing surface. Making them uniform would add a `--json` flag
across every `cmd_*` and normalize delete subcommands under `delete
<type>`. Cost is bounded and mostly plumbing.

Recommendation: opportunistic — fix when a CLI is already being touched.
Not worth a standalone remediation pass.

### 2.15 Error taxonomy

Current choice: each package raises its own exception type —
`VCFOpsError`, `VCFOpsCustomGroupError`, `VCFOpsSymptomsError`,
`VCFOpsAlertsError`, `VCFOpsReportsError`, `BundleValidationError`,
`AuditError`, `DashboardValidationError`, `SuperMetricValidationError`,
`AlertValidationError`, `ManagementPackValidationError`. All are direct
subclasses of `RuntimeError` or `ValueError`.

There is no shared base like `VCFContentFactoryError` and no structured
error body (no `error_code: str`, `content_type: str`, `item: str` —
just a string message with varying format).

CLI consumers (`cmd_sync`, `cmd_enable`, etc.) catch the package's own
exception and print `f"FAIL: {e}"` or similar; cross-package callers
(`vcfops_packaging/syncer.py`) use `try/except Exception` or per-type
catches. The handler result types (`ItemResult`, `SyncResult`) carry a
`message: str` field but not an error code.

Classification: **shortcut low-cost**. A shared `VCFFactoryError` base
plus a tagged `error_code` vocabulary (AUTH_FAILED, IMPORT_BUSY,
UUID_COLLISION, MISSING_REFERENCE) would let downstream consumers
(qa-tester, content-installer, install.py's retry loop) switch on the
code instead of grepping message text.

Recommendation: introduce the taxonomy when a consumer demands
programmatic error handling — today the install template's import-busy
retry (`templates/install.py:403-463`) already does this by string-match,
which is fine for now but will bite when a new 503-style condition
appears.

### 2.16 Packaging-time dependency audit

Current choice: `vcfops_packaging/audit.py` (486 lines) walks every
content artifact in a bundle, resolves each referenced built-in metric
against an adapter describe cache (`vcfops_packaging/describe.py`),
and either auto-adds the reference to `builtin_metric_enables` or fails
the build when dependencies can't be resolved.

Modes: `auto` (default), `strict` (fail on any unenabled), `lax`.

Reference extraction via `vcfops_packaging/deps.py:_refs_from_formula`
handles SM formulas. The bundle declares-check at
`vcfops_packaging/audit.py:77-89` checks `bundle.builtin_metric_enables`
coverage.

Classification: **framework-general**. This is exactly the
"ships broken" prevention Scott called for in MEMORY note
`feedback_packaging_dependency_audit.md`, and it's implemented for every
content type that flows through the packager's content-scan.

Gap: the audit covers SM formulas and view/dashboard metric references
but does not walk alert symptom references or report section metric
references transitively. Deferred to the appropriate per-type scanner.
Low-value to add until a "ships broken" alert comes up.

Also: the audit runs at `build` time, not at `sync` time. Running it at
sync would catch drift between the built zip and the running instance
(if an operator disables a metric between build and install). Scope
decision; not a shortcut.

### 2.17 Agent roster coverage

Current choice: 16 agents in `.claude/agents/`. Authoring coverage is
complete per-content-type (supermetric, customgroup, view, dashboard,
symptom, alert, report). Plus mp-author, mp-designer, and api-cartographer
for the MP side.

Gaps identified:

1. **No "content-designer" for compound content.** mp-designer exists
   for MPs; nothing equivalent for compound content requests ("I want a
   VM performance dashboard with 5 SMs, a custom group, and two views").
   Today the orchestrator absorbs the design burden itself per
   CLAUDE.md §Workflow-patterns compound-bundle. In practice this works
   because the orchestrator passes intent top-down and each author agent
   makes local decisions, but it doesn't capture a reusable design
   artifact (mockup + prompt + plan) the way `designs/<mp-name>.md` does
   for MPs.
2. **qa-tester's scope is clear but narrow.** It runs install/uninstall
   cycles on built zips. It does not verify ongoing operation (SM data
   arrives, dashboard renders, alert fires) beyond the "SM collection"
   poll at `.claude/agents/qa-tester.md:30`. A "post-install observation"
   agent could cover longer-horizon validation. Not urgent.
3. **No dedicated reference-source maintainer.** Pattern-like role for
   "when did we last pull references/?" doesn't exist — currently
   covered by the orchestrator running `bootstrap_references.sh --update`
   on demand.

Classification: gap #1 is **shortcut low-cost** (plan-mode + design
artifact workflow from `feedback_plan_mode_for_content_requests.md`
already exists informally; add a `content-designer` agent to codify it).
Gaps #2 and #3 are **unknown / needs capture** — not enough evidence
they're causing pain today.

Recommendation: hold on all three until a user request makes one
concrete.

### 2.18 Known limitations in CLAUDE.md

Classifying each of the 7 known limitations:

1. **Dashboard widget types** — **shortcut high-cost**. See axis 2.6.
2. **Policy enablement — Default only** — **shortcut high-cost**. See
   axis 2.3. Also mislabeled as "server-constraint"; it's a code gap.
3. **Recommendations — authoring works, REST sync does not** —
   **framework-general constraint** (API has no recommendations field).
   Correctly documented. The content-zip path is the only way;
   `vcfops_alerts/handler.py` correctly sync-skips and defers to the
   packaging path. No remediation needed beyond the doc.
4. **Reference-source clones missing on fresh setup** —
   **framework-general** (covered by bootstrap script). Doc is a
   courtesy, not a shortcut.
5. **View and report delete** — **framework-general** since the
   2026-04-11 correction. The install template implements the correct
   nested-JSON-string shape at
   `templates/install.py:1072-1280`. The doc line is now just a
   history note.
6. **UI-session uninstall requires admin** — **framework-general
   constraint** (server-forced — content-zip importer assigns ownership
   to `admin`). Correctly modeled at
   `vcfops_managementpacks/installer.py:34-39` with backward-compat
   fallbacks and per-install-script precheck in `templates/install.py`.
7. **No per-object UI import endpoints in VCF Ops 9.0.2** —
   **framework-general constraint** (investigated thoroughly, confirmed
   by `context/pak_ui_upload_investigation.md`). The SPA-wraps-into-zip
   behavior is why our drag-drop artifacts work. Correctly modeled.

Summary: 2 of 7 known limitations are shortcuts (dashboard widgets,
policy enablement). The remaining 5 are real server constraints
correctly documented.

### 2.19 Install script PS/Python parity

Current choice: both `install.py` and `install.ps1` are maintained
manually. They are close in size (2528 vs 2555 lines) and function
coverage, but the PS 5.1 compat requirement
(`feedback_ps51_compat.md`) imposes asymmetric constraints — ASCII-only
in templates, no bare `&` at continuation starts, pipeline unwrap
footguns, StrictMode differences.

qa-tester runs both scripts (`.claude/agents/qa-tester.md:33, 42`), but
only when `pwsh` is available; otherwise SKIPs. The QA test harness is
not formally testing PS 5.1 — it runs `pwsh` 7.

Classification: **shortcut low-cost** from a testing-coverage angle.
The framework-correct posture is one of:

- Template-generate both from a single source (expensive; see 2.8).
- Explicitly run PS 5.1 in CI (Scott's actual target) instead of / in
  addition to pwsh 7. Needs a Windows runner.

Recommendation: flag this to Scott — the qa-tester doing pwsh 7 on
Linux ≠ Scott's production execution environment. When a PS 5.1-specific
bug ships, this is the root cause. Lower cost to add a PS 5.1 smoke
test than to keep discovering these mid-distribution.

Open question for Scott: should qa-tester's PS harness explicitly note
"tested on pwsh 7, not PS 5.1"? Minimum viable fix: add that caveat to
`.claude/agents/qa-tester.md`.

### 2.20 Documentation generation

Current choice: `vcfops_packaging/builder.py:275-434` generates both the
distribution-package-level README (static copy of
`templates/README_framework.md`) and the per-bundle README. The
per-bundle README is auto-generated from bundle metadata: display name,
description, provenance (for `factory_native: false`), content-type
item counts, install/uninstall instructions.

Classification: **framework-general**. Scales cleanly across
factory-native and third-party bundles; respects the MEMORY note
`feedback_community_repackage_sop.md` about preserving attribution; the
`has_provenance` gate at lines 287-292 ensures factory-native bundles
get a simple README while third-party bundles get a Provenance block.

Minor gap: there's no auto-generated CHANGELOG.md. If a bundle is
rebuilt with a new content item, the READMEs silently update but there's
no history. Not a shortcut — scope decision. Skip unless users ask.

---

## 3. Cross-cutting themes

**Theme A — Four copies of the auth flow.** Axes 2.2, 2.8, and 2.15 all
trace back to "four VCFOps*Client classes + two install-script forks
reimplement the same auth/request/retry logic". A shared `_session.py`
base in `vcfops_packaging` would collapse the four factory clients into
one; a zipapp or template-gen strategy would collapse the two install
scripts. Two remediations, one theme. This is the single highest-leverage
area.

**Theme B — Naming prefix is a cultural rule, not a mechanical one.**
Axes 2.5 and 2.17 both expose the fact that `[VCF Content Factory]` is
enforced by author-agent-prompt and orchestrator vigilance, not loader
code. A single `_validate_prefix()` helper across all loaders closes the
gap. Combined with the existing `factory_native: bool` field, this is
the cheapest mechanical win on the list.

**Theme C — MP and content are parallel worlds.** Axes 2.7, 2.17, and
parts of 2.19 all surface the fact that management packs are a
first-class capability now but not integrated into the bundle manifest.
This is a Scott-strategic call (is an MP a standalone product, or part
of a bundle?), and the current factoring reflects "standalone product"
until the plan in MEMORY note `project_mp_capability_plan.md` settles.
Don't fix preemptively.

**Theme D — Bundle-scoped vs repo-scoped resolvers.** Axis 2.13 shows
`render_views_xml` pulling the full `supermetrics/` tree. If the factory
stays small-and-curated this is fine; when the factory gains
third-party bundles with their own SMs (the IDPS case today), global
resolution becomes load-bearing in a fragile way. Scoping the resolver
to the bundle is cheap and should precede any multi-bundle extraction
work.

**Theme E — Shortcut audit trail is good.** Many of the shortcuts
identified here are already labeled as such in the source —
`ADAPTER_JAR_GAP`, `TOOLSET GAP` comments, the
MEMORY-note feedback system, CLAUDE.md §Known-limitations. The factory
has a culture of flagging its own shortcuts. That's the system working.
The gaps where shortcuts are NOT self-labeled (axis 2.5 prefix
enforcement, axis 2.2 auth duplication, axis 2.13 repo-scoped SM map)
are the ones worth addressing first, because they can mislead future
agents into thinking "this is the framework-correct behavior".

---

## 4. Prioritized shortcut-remediation list

Ranked by (impact on future MPs/content × cost to fix). Top of list =
best ratio.

1. **Mechanical `[VCF Content Factory]` prefix enforcement** (axis 2.5).
   Impact: prevents silent identity-tag loss across every new piece of
   content. Cost: small — one helper function, six loader invocations,
   clean up the stale `[AI Content]` example in
   `vcfops_customgroups/loader.py:12`. Do this first.

2. **Bundle-scoped SM name→UUID resolver** (axis 2.13). Impact: every
   bundle built while multiple bundles coexist becomes deterministic.
   Cost: small — thread `sm_map` from `vcfops_packaging/builder.py`
   through the render callsite. Do this second.

3. **Shared auth/session module** (axis 2.2). Impact: future auth modes
   (OAuth / service accounts) land in one place instead of four. Cost:
   medium — tooling-agent effort plus coordinated test pass across the
   four CLIs. Still net positive because the existing four copies are
   near-identical.

4. **Re-label CLAUDE.md §Known-limitations #2 (policy enablement)**
   (axis 2.3). Impact: readers stop treating it as a server constraint.
   Cost: trivial (doc edit). Actual multi-policy implementation is a
   bigger lift and belongs on the "pay when a user asks" list; but
   labeling it honestly costs nothing.

5. **Install-template drift surface** (axis 2.8). Impact: three-way wire
   fixes stop silently diverging. Minimum viable: header comment in
   both templates pointing at the factory source-of-truth file with a
   "keep in sync" note, plus a qa-tester checklist item to verify
   template↔factory alignment when a wire fix lands. Cost: small.
   Full template generation is a separate, larger project.

Items 6-N (widget-plugin refactor, multi-policy enablement, MP/content
bundle schema merge, content-designer agent) are intentionally deferred
— each is impact-positive but high-cost, and none is blocking current
work.

---

## 5. Open questions for Scott

Decisions that need Scott's call before remediation can proceed.

1. **Policy enablement** (axis 2.3). Prioritize multi-policy now, or
   stay Default-only until a user asks? (Either is defensible; the
   mislabeling in CLAUDE.md is what matters either way.)

2. **Install template strategy** (axis 2.8). Template-generate the two
   scripts from a single source, or keep the parallel-fork model and
   rely on qa-tester drift-catching?

3. **MP/content bundle schema merge** (axis 2.7). Reserve
   `management_pack:` in the bundle manifest now as a forward hint, or
   wait until ADAPTER_JAR_GAP and chaining clear?

4. **Widget-plugin refactor** (axis 2.6). Spawn `tooling` now with a
   plugin-interface brief, or wait for the next widget request to force
   the refactor?

5. **QA harness PS 5.1 coverage** (axis 2.19). Add a Windows/PS 5.1
   execution path to the QA harness (runner cost), or just add a
   "tested on pwsh 7, not PS 5.1" caveat to qa-tester.md (doc cost)?

6. **content-designer agent** (axis 2.17). Codify compound-content
   design as a first-class agent analogous to mp-designer, or continue
   to let the orchestrator carry the design role for compound content?

Each question is framework-strategic, not tactical. None blocks current
authoring work.
