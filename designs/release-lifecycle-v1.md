# Release Lifecycle v1 — Tooling Plan

**Status:** draft 2026-04-27
**Owner:** orchestrator (design) + tooling agent (implementation)
**Supersedes:** `designs/publish-command-v1.md` (the two-knob `released:` model)

## Context

The factory has authoring tooling and per-content sync tooling, but no
release lifecycle. The WIP publish commit (`ba3d78f`, 2026-04-24) added
scaffolding (`released: bool` + `version: str` fields, `discrete_builder.py`,
`readme_gen.py`, slash command + design doc) but the orchestration is
agent-driven markdown, not deterministic Python. Plus the dist repo at
`vcf-content-factory-bundles/` is a flat directory of zips with no
structure, and contains zips for bundles we just retired
(Environment Config Status, VM Performance).

This plan defines the lifecycle: an authored content tree (this repo) →
a release manifest declaring shipping intent → a publish operation that
builds and pushes artifacts to a structured distribution repo.

## Conceptual model

Three concepts, three vocabulary words:

| Concept | What it is | Where it lives |
|---|---|---|
| **Component** | A single content YAML (SM, view, dashboard, customgroup, symptom, alert, report) | `supermetrics/`, `views/`, `dashboards/`, ... |
| **Bundle** | A curated set of components | `bundles/*.yaml` |
| **Release** | A shipping event. References 1+ headline artifacts | `releases/*.yaml` (new) |

**Flow:**
- Author writes components and (optionally) bundle manifests.
- `/release <thing>` materializes a release manifest, flips `released: true`
  on the source YAML.
- `/publish` reads `released: true` items, uses their release manifests
  to build, routes outputs to subdirs in the dist repo.

Same component YAML can be a headline in one release AND a transitive
dependency of another. The dependency walker handles both cases.

## File structure changes

### A. New YAML type: `releases/*.yaml`

```yaml
name: demand-driven-capacity-v2          # slug, kebab-case
version: 1.0                              # major.minor; auto-bumped on /release
description: >
  Per-cluster demand and capacity dashboard with vCPU:pCPU column
  and right-side metric explainer. Replaces v1.
release_notes: |
  - Initial v2 release
  - Adds vCPU:pCPU Ratio column (OOTB metric)
  - Right-side TextDisplay explainer for Provisioned/Usable/Demand metrics
  - Replaces v1 Demand-Driven Capacity Planning dashboard

# 1+ headline artifacts. Each headline's source path implies its type
# (dashboards/foo.yaml → dashboard → vcf-cf-bundles/dashboards/).
# Transitive deps are computed by the dependency walker; not listed here.
artifacts:
  - source: dashboards/demand_driven_capacity_v2.yaml
    headline: true

# Optional. Lists release manifests this release retires.
# Publish flow moves their dist-repo zips to retired/.
deprecates: []
```

For a multi-bundle release:

```yaml
name: capacity-suite
version: 1.0                              # major.minor
description: Combined capacity + rightsizing + vSAN bundles.
artifacts:
  - source: bundles/capacity-assessment.yaml
    headline: true
  - source: bundles/vsan-cluster-health.yaml
    headline: true
deprecates:
  - releases/capacity-assessment-1.0.yaml  # retire the standalone release
```

**Filename convention:** `releases/<slug>.yaml`. Version lives inside the
file (one file per release line, history shows version bumps).

### B. Existing component YAML — no schema changes

`released: bool` + `version: str` fields already exist on every loader
(WIP commit `ba3d78f`). They stay. Semantic:
- `released: true` = "this component is currently shippable" — set by `/release`.
- `version` = component's own evolution version, independent of release version.

A release manifest's `version:` is the shipping-event version.
A component's `version:` is the content's version.
They evolve independently.

### C. Existing bundle YAML — no schema changes for v1

Same as components: `released: bool` + `version:` already present.
Bundle composition (`includes: [other-bundle.yaml]`) is **deferred to v2**;
multi-bundle releases use the release-manifest's multiple-headline pattern
in v1. Reduces scope and exercises the simpler path first.

### D. Distribution repo layout (`vcf-content-factory-bundles/`)

**Target structure:**

```
vcf-content-factory-bundles/
├── LICENSE
├── README.md                           # regenerated between AUTO markers
├── bundles/                            # multi-content bundle releases
│   ├── capacity-assessment-<version>.zip
│   └── vks-core-consumption-<version>.zip
├── dashboards/                         # discrete dashboard releases
│   └── demand-driven-capacity-v2-<version>.zip
├── views/                              # discrete view releases (rare)
├── supermetrics/                       # discrete SM releases (rare)
├── customgroups/                       # discrete custom group releases (rare)
├── reports/                            # discrete report releases (rare)
├── management-packs/                   # MP releases (deferred — see "out of scope")
└── retired/                            # deprecated artifacts moved here on retirement
    └── <subdir-mirror>/
```

**Type→subdir map:**

| Source path prefix | Headline type | Dist subdir |
|---|---|---|
| `bundles/` | bundle | `bundles/` |
| `dashboards/` | dashboard | `dashboards/` |
| `views/` | view | `views/` |
| `supermetrics/` | supermetric | `supermetrics/` |
| `customgroups/` | customgroup | `customgroups/` |
| `reports/` | report | `reports/` |
| `managementpacks/` | managementpack | `management-packs/` (deferred v1) |

Symptoms and alerts: don't get their own discrete-release subdir in v1.
They're never useful standalone — they ship inside bundles. If someone
explicitly `/release`s a symptom or alert, route to a `bundles/` zip
that contains just that symptom + its dependencies (treat the slash
command as syntactic sugar for an ad-hoc bundle release).

## Tooling changes

All of this lives in `vcfops_packaging/` — extend, don't fork.

### 1. Release loader (`vcfops_packaging/releases.py` — new)

- Parse `releases/*.yaml` and validate schema.
- Validate referenced source files exist and are flagged `released: true`.
- Validate `deprecates:` entries point to real release manifests.
- Validate version is semver-shaped.
- No UUID — release manifests use `name` as identity.

### 2. Type-to-subdir router (`vcfops_packaging/release_types.py` — new)

Small utility module exposing `headline_to_dir(source_path) -> str`
(maps `dashboards/foo.yaml` → `dashboards`). Used by the publish
orchestrator to route output zips.

### 3. Release builder integration

Existing builders stay:
- `discrete_builder.py` — already builds a self-contained zip for a
  single component + transitive deps. Used when a release headline is a
  component (dashboard, view, SM, etc.).
- `builder.py` — builds a bundle zip. Used when a release headline is a
  bundle.

New: `vcfops_packaging/release_builder.py` (or extend existing) — top-level
function that takes a release manifest, picks the right builder per
headline, names the output zip per the convention, and returns the
artifact list (path + dest subdir).

**Naming convention for output zips:**
`<release-name>-<release-version>.zip` — e.g., `demand-driven-capacity-v2-1.0.0.zip`.

### 4. Retirement handler

When a release manifest's `deprecates:` field lists prior release
manifests, the publish flow:
1. For each deprecated release: locate its zip in `vcf-cf-bundles/<subdir>/`.
2. Move the zip to `vcf-cf-bundles/retired/<subdir>/`.
3. README regeneration marks it as "Retired YYYY-MM-DD by <new release>".

Retired zips stay in the dist repo (don't delete) — consumers may have
links. The retired subdir is the graveyard.

**Stale-zip cleanup:** any zip in a top-level subdir whose corresponding
source release manifest no longer exists is *also* moved to retired/
on next publish (with a generic "source release manifest no longer present"
note). This is the migration path for the current flat-layout state.

### 5. Publish orchestrator (`vcfops_packaging/publish.py` — new)

Top-level entrypoint. Steps:
1. `validate` everything (existing `validate` calls).
2. Sync expectations: clean working tree on dist repo (refuse if dirty).
3. Enumerate release manifests in `releases/`.
4. For each release manifest:
   - Build expected zip name + version.
   - Check if exact match already in dist repo. If yes, skip (idempotent).
   - If different version exists, warn (or fail without `--force`).
   - Otherwise: build → copy to `<subdir>/`.
5. Process retirements: for each release manifest with `deprecates:`, move
   deprecated zips to `retired/`.
6. Stale-zip sweep: any zip without a current release manifest → `retired/`.
7. Regenerate `README.md` between AUTO markers (existing `readme_gen.py`).
8. Stage all changes; commit dist repo with auto-generated message
   (`Publish: <release-name> <version> + N retired`); push to `origin/main`.
9. Report summary back to caller.

Stops on any failure; never auto-pushes a broken state.

### 6. CLI subcommands (`vcfops_packaging/cli.py` — extend)

Add:
- `release <type> <name>` — materialize release manifest + flip flag
  for a single content item. Args:
  - `<type>`: dashboard, view, supermetric, customgroup, report, bundle, alert, symptom.
  - `<name>`: component name (display name) or path. Resolved against repo.
  - Flags: `--version <semver>` (default 1.0.0 or bump existing), `--notes <file>` (release notes from a file), `--deprecates <name>` (mark prior release deprecated).
- `release-multi <release-name>` — interactive variant for multi-headline
  releases. Prompts for headlines + version + notes.
- `publish` — runs the publish orchestrator. Flags:
  - `--dry-run` (build but don't copy/commit/push).
  - `--force` (allow version conflict).
  - `--no-push` (commit but don't push).

### 7. Readme generator extensions

`readme_gen.py` already exists. Extend the AUTO-marker sections:
- Per-subdir tables (one section per `bundles/`, `dashboards/`, `views/`, etc.).
- Each row: name, version, release date, notes excerpt, install command.
- Retired section at bottom.

Keep human-edited content outside AUTO markers as-is.

## Slash commands

### `/release` (rewrite)

```
/release dashboard demand_driven_capacity_v2
/release bundle capacity-assessment --version 1.1.0
/release view vks_core_consumption_by_vcenter --notes notes.md
```

The slash command:
1. Resolves the type + name to a source path.
2. Validates the source exists and isn't already at the requested version.
3. Calls `python3 -m vcfops_packaging release <type> <name> ...`.
4. Reports the materialized release manifest path + flag flip.
5. Does NOT push anything. Local-only operation; user commits manually.

Replaces today's `/publish` slash command's "enumerate released items"
ad-hoc behavior with a deliberate per-item act.

### `/publish` (rewrite)

```
/publish
/publish --dry-run
/publish --force
```

Replaces the 204-line markdown orchestration with:
1. Validate the dist-repo prerequisite (clean tree, on `main`).
2. Call `python3 -m vcfops_packaging publish [args]`.
3. Report summary (artifacts shipped, retired, README diff).
4. Surface any failures verbatim.

Slash command becomes thin glue over the deterministic Python tool.

## Initial migration

The current dist repo state:

```
vcf-content-factory-bundles/
├── LICENSE
├── README.md
├── [VCF Content Factory] Capacity Assessment.zip
├── [VCF Content Factory] Environment Config Status.zip   ← retired bundle
├── [VCF Content Factory] VKS Core Consumption.zip
└── [VCF Content Factory] VM Performance.zip              ← retired bundle
```

**Migration approach: delete legacy zips, let the first `/publish` rebuild
the dist repo cleanly from release manifests.**

Concretely:

1. **One manual cleanup commit on the dist repo** — `rm` all four flat-layout
   zips from `vcf-content-factory-bundles/` root, push. Git history preserves
   the old artifacts for anyone who needs them. (One-time, not driven by
   tooling.)
2. **In the factory repo, run `/release` per release item:**
   - `/release dashboard demand_driven_capacity_v2` — creates
     `releases/demand-driven-capacity-v2.yaml`, headline = the dashboard.
   - `/release bundle capacity-assessment` — creates
     `releases/capacity-assessment.yaml`, headline = the bundle YAML.
   - `/release bundle vks-core-consumption` — same shape.
   - The two retired bundles (Environment Config Status, VM Performance)
     get **no** release manifests — they stay deleted. Their source YAMLs
     are already gone from the tree.
3. **Run `/publish`** — for each release manifest:
   - Walks the headline's dep graph against current source-tree state.
   - Builds the zip with the resolved version (`<name>-<version>.zip`).
   - Routes to the right subdir: `dashboards/<name>-1.0.zip` for the v2
     dashboard, `bundles/<name>-1.0.zip` for capacity + vks.
   - Regenerates README with the new per-subdir tables.
   - Commits + pushes the dist repo.

**Bundle→dashboard reshaping (Phase 7):** capacity-assessment and
vks-core-consumption are currently shaped as bundles, but each ships
one user-facing dashboard plus its dep graph. Under this lifecycle they
become **dashboard releases** so the `bundles/` slot is reserved for
genuine multi-content curation (multiple dashboards + alerts + symptoms +
customgroups bound by a theme).

Concretely in Phase 7:

- Delete `bundles/capacity-assessment.yaml`. Create `releases/capacity-assessment.yaml`
  with `headline: dashboards/capacity_assessment.yaml`. Move the bundle
  YAML's marketing `description:` into the release manifest. Lands in
  `vcf-cf-bundles/dashboards/`.
- Delete `bundles/vks-core-consumption.yaml`. Same shape. Lands in
  `vcf-cf-bundles/dashboards/`.

Gated on **Phase 1.5** (walker extension) — capacity-assessment scopes
a widget to the `vms_rightsizing_candidates` customgroup, which the
current walker does not extract. Without Phase 1.5 the customgroup would
silently drop and the published zip would install a broken dashboard.

## Phases & sequencing

| Phase | Scope | Delegation | Validates by |
|---|---|---|---|
| 1 | Release loader + schema validator + type→subdir router | tooling agent | Author sample `releases/test.yaml`, run `validate`, expect clean. |
| **1.5** | **Walker extension: dashboard→view consolidation + customgroup ref extraction** | **tooling agent** | **Build a dashboard release whose dashboard scopes a widget to a customgroup; verify the customgroup lands in the zip.** |
| 2 | Release builder integration; build a single release zip locally | tooling agent | Build `releases/test.yaml` into a zip; inspect contents. |
| 3 | Publish orchestrator (build + route + retire + README + commit) | tooling agent | `--dry-run` against a temp dist repo; verify subdirs, retirement, README. |
| 4 | CLI: `release` + `publish` subcommands | tooling agent | Run `release` for the v2 dashboard; verify manifest materialized. |
| 5 | Slash command rewrites (`/release`, `/publish`) | orchestrator (markdown only) | Manual user-driven test on a non-destructive sequence. |
| 6 | Initial migration | content-installer-style flow on the dist repo | First real `/publish`; lays out current zips correctly. |
| 7 | Backfill release manifests, including bundle→dashboard reshaping for capacity-assessment + vks-core-consumption | author per-release; orchestrator drives | Each surviving bundle gets a release manifest; users mark new releases. |

Phases 1–4 (incl. 1.5) can interleave with `tooling` agent dispatch.
Phase 5 is prompt-only. Phase 6 is one-time. Phase 7 is content-author
work and can run in parallel with Phase 5.

### Phase 1.5 detail — walker extension

Findings from 2026-04-27 walker audit (`vcfops_common/dep_walker.py`):

- **No customgroup reference model anywhere** — neither dashboard widgets,
  view scoping, nor SM formulas extract customgroup refs.
- **Dashboard→view linkage lives in `discrete_builder._resolve_dashboard_deps()`,
  not in the walker proper** — walker only walks views passed in explicitly.
  Folding this into the walker keeps the dependency model in one place.

Required changes:

1. Move dashboard→view extraction from `discrete_builder._resolve_dashboard_deps()`
   into the walker as a first-class traversal step.
2. Add a new extraction pass: dashboard widget configs → customgroup names
   (where widgets pin to a customgroup as scope).
3. Add a new extraction pass: view-level scoping → customgroup names
   (where a view filters its subject to a customgroup).
4. Threading: when the walker encounters a customgroup ref, resolve to a
   `customgroups/<file>.yaml`, recurse into that customgroup for any further
   refs (it's typically a leaf, but rules may scope to other groups).
5. Update `walk_and_check()` signature to accept a customgroups corpus
   alongside views/SMs.

**Verification:** build a dashboard release for `demand_driven_capacity_v2`
(no customgroup, sanity check) AND for a synthetic test dashboard that
explicitly scopes to a customgroup (or reuse `capacity_assessment` once
the extension is in place); confirm the customgroup YAML lands in the zip.

## Out of scope (v1)

- **Management pack releases.** MPs have a different artifact (`.pak`),
  different install path, different versioning concerns. Their release
  story plugs into the same lifecycle later (subdir
  `management-packs/`, headline type `managementpack`) but defer the
  builder integration until v1 is stable.
- **Bundle composition** (`includes: [other-bundle.yaml]` in bundle YAML).
  Multi-bundle releases use the release manifest's multi-headline pattern
  instead. v2 if needed.
- **Cross-version pinning** (release X depends on bundle Y v1.2 specifically).
  v1 always builds against current source-tree state.
- **Auto semver bumps.** Manual version bumps in YAML; tooling doesn't
  guess.
- **Mega-archive zip** (one mega-zip containing every bundle). Multi-bundle
  releases produce N separate zips, one per headline bundle. If a
  single-zip "release archive" is wanted later, that's a v2 feature.
- **Webhook / CI triggers.** `/publish` is human-invoked. No auto-publish
  on commit.

## Resolved decisions (2026-04-27)

1. **Versioning is `x.y` (major.minor), no patch.** First `/release` for a
   slug produces `1.0`. Subsequent `/release` calls for the same slug
   **auto-bump the minor** (`1.0` → `1.1` → `1.2`). Override with
   `--version 2.0` for a major bump. Internal tracking only — no
   external-facing version display required.
2. **`/release` commits.** Both the new release manifest and the
   `released: true` flag flip land in a single auto-generated commit
   (`release: <name> <version>`). User can amend/edit afterward but the
   default is turn-key.
3. **Stale state is a hard error at validate.** Two failure modes both
   error: (a) component flagged `released: true` with no release manifest
   pointing at it, and (b) release manifest exists but its headline
   component is `released: false`. Validator complains loudly; author
   fixes by hand or via a future `/unrelease <name>` companion.
4. **Duplicate `name:` across release manifests is a hard validate error.**
   Same pattern as component-name uniqueness today.
5. **Concurrent `/publish` is guarded by a lockfile.** `/publish` writes
   `vcf-content-factory-bundles/.publish.lock` on start, removes on
   completion, refuses to run if the file already exists. Documented as
   "don't run two `/publish` sessions" alongside.

## Follow-ups (deferred, not blocking)

- **Document the new `customgroup:` field on view YAML.** Phase 1.5 added
  this as an optional metadata field on `ViewDef` so the dep walker can
  surface view→customgroup linkage. It does not affect install/sync wire
  format. Update `context/wire_formats.md` (and any view-authoring guide)
  so future view authors know to declare it when their view scopes to a
  customgroup. Without this, a future view release that scopes to a CG
  could silently drop the CG dependency from the published zip.

- **Dashboard widget-level customgroup scope wire format.** Phase 1.5
  installed `extract_customgroup_names_from_dashboards()` as an extension
  point with a heuristic fallback, but no factory dashboard currently
  uses a customgroup as a direct widget scope, so the wire format is not
  documented. When a dashboard needs this, dispatch api-explorer to map
  the wire shape and finish the extractor.

## Validation gates

Each phase ships only when:
- `python3 -m vcfops_packaging validate` is clean (covers components,
  bundles, AND release manifests once Phase 1 lands).
- A representative `--dry-run` publish builds the expected artifacts
  with the expected layout (Phase 3+).
- The dist repo is on a clean working tree before any publish operation.
- The factory repo is on a clean working tree before any release operation.

No silent failures. Any error stops the chain and reports verbatim.

## Files to create / modify

**New:**

- `releases/` directory (empty initially; populated in Phase 7).
- `vcfops_packaging/releases.py` (release loader + validator).
- `vcfops_packaging/release_types.py` (type→subdir router).
- `vcfops_packaging/release_builder.py` (builds release zips).
- `vcfops_packaging/publish.py` (publish orchestrator).
- `releases/capacity-assessment.yaml` (Phase 7 backfill).
- `releases/vks-core-consumption.yaml` (Phase 7 backfill).
- `releases/demand-driven-capacity-v2.yaml` (Phase 7 backfill).

**Modify:**

- `vcfops_packaging/cli.py` — add `release` + `publish` subcommands.
- `vcfops_packaging/readme_gen.py` — extend AUTO-marker sections for
  the per-subdir layout.
- `.claude/commands/publish.md` — rewrite as thin glue over `python3 -m
  vcfops_packaging publish`.
- `.claude/commands/release.md` — new slash command.

**Decommission:**

- `designs/publish-command-v1.md` — superseded by this doc; leave as
  historical record but add a header pointing here.

**No changes:**

- All `supermetrics/`, `views/`, `dashboards/`, etc. component YAML.
- Bundle manifests under `bundles/`.
- Install scripts in `vcfops_packaging/templates/`.
- Other `vcfops_*/` packages.
