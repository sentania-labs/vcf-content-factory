# Content Structure v3 — type-first source layout + project-level third-party

**Status:** Phase 1 shipped (commits `ba1755d` + `0433815`); Phase 1 over-consolidated `bundles/`, `releases/`, and `third_party/` under `content/` — corrected layout being applied 2026-04-27 to lift them back to top-level siblings (this revision of the doc captures the corrected end-state).
**Owner:** orchestrator (planning) + tooling agent (implementation)
**Builds on:** `designs/release-lifecycle-v1.md` (publish pipeline + ThirdPartyContent routing) and `designs/content-structure-v2.md` (smaller cleanup items)
**Supersedes:** v2 item #2 (third_party/ promotion) — see "Relationship to v2" below

## Context

After the release lifecycle landed and v2 cleanup got queued, the bigger
question surfaced: **where should each kind of content actually live in
source?** The v2 plan moved third-party content from `bundles/third_party/`
to a flat `third_party/` at repo root, but discussion exposed a deeper
opportunity — make the source layout **type-first**, with a clean split
between factory-native and third-party provenance, and make the slash
command grammar fully consistent across every content type.

## Conceptual model

Four content-related top-level directories, each with a distinct
semantic. Native content under `content/` (factory implicit — it IS
the content); third-party under its own top-level `third_party/`
sibling; meta-structures (`bundles/`, `releases/`) at top-level too:

```
<repo root>/
├── content/                       ← native content types
│   ├── dashboards/
│   ├── views/
│   ├── supermetrics/
│   ├── customgroups/
│   ├── alerts/
│   ├── symptoms/
│   ├── reports/
│   ├── recommendations/
│   └── managementpacks/
│
├── third_party/                   ← third-party content, project-grouped
│   ├── idps-planner/              ← one subdir per project (cohesion preserved)
│   │   ├── PROJECT.yaml           ← attribution, license, factory_native, builtin_metric_enables
│   │   ├── dashboards/
│   │   ├── views/
│   │   ├── supermetrics/
│   │   └── managementpacks/       ← (when a project ships a third-party MP)
│   └── some-other-project/
│       ├── PROJECT.yaml
│       └── ...
│
├── bundles/                       ← meta — composes content (factory + third-party)
│   └── <multi-content sets — declares which components ship together>
│
└── releases/                      ← meta — ships content
    └── <release manifests, headline pointers + version + notes>
```

**Key principles:**

- **Asymmetric semantics, asymmetric structure.** Native content is one
  team, one provenance, one license — type-first navigation
  (`content/dashboards/foo.yaml`) reflects that uniformity. Third-party
  is many projects, many authors, many licenses — provenance-first
  navigation (`third_party/<project>/<type>/<file>.yaml`) reflects
  *that* uniformity. Forcing symmetric structure across asymmetric
  semantics is a footgun: `src/` and `vendor/` in software repos are
  the canonical analogy.
- **Project boundary IS the claim-boundary.** A third-party project
  living in its own subdir with `PROJECT.yaml` communicates "this is
  THEIR thing, packaged here" — we aren't claiming it. Flat
  decomposition would erase that signal.
- **Top-level is uncluttered but explicit.** Four content-related
  directories at root, each with a single job. Framework
  infrastructure (`vcfops_*/`, `docs/`, `context/`, `designs/`,
  `scripts/`, `tests/`, etc.) sits alongside.
- **Symmetric type subdirs WHERE the structure repeats.** Inside
  `content/` and inside any `third_party/<project>/`, the type words
  (`dashboards/`, `supermetrics/`, ...) are identical. Same vocabulary
  at every level it appears.

## Slash command grammar

Type-first lookup across both provenances:

```
/release dashboard <slug>      ← searches content/dashboards/ and third_party/*/dashboards/
/release view <slug>           ← searches content/views/ and third_party/*/views/
/release supermetric <slug>
/release customgroup <slug>
/release alert <slug>
/release symptom <slug>
/release report <slug>
/release recommendation <slug>
/release managementpack <slug> ← same pattern for MPs
/release bundle <slug>         ← searches bundles/ only

/bundle <name>                 ← new — interactive bundle composer
/publish                       ← unchanged: ships every release manifest in releases/
```

Provenance (factory-native vs third-party) is **discovered from path**,
not declared in the command. The slash command grammar is identical for
both — the routing layer reads the source path or the project's
`PROJECT.yaml` to decide where the published artifact lands.

### `/bundle` (new)

Interactive bundle composer. Walks the user through:

1. Pick a slug (validates uniqueness across `bundles/` and release
   manifests).
2. Pick a display name + description.
3. Walk candidate components by type — list available dashboards / views /
   SMs / etc. across both factory and third-party roots, ask which to
   include. Fuzzy slug match for picks.
4. Validate dependency consistency — selected components shouldn't
   accidentally cross-reference content not in the bundle.
5. Write `bundles/<slug>.yaml` with the chosen components.

Bundles are **always** explicit user composition; no auto-generation.

## Project-level attribution (third-party only)

Every `third_party/<project>/` directory carries a `PROJECT.yaml`:

```yaml
name: idps-planner
display_name: IDPS Planner
factory_native: false
author: Ryan Pletka, Brock Peterson, Joe Tietz, Geoff Shukin, Scott Bowe
license: MIT
source:
  captured_at: '2026-04-17'
  origin: extracted via vcfops_extractor
  upstream: <optional URL or repo>
description: >
  Short elevator pitch. Long-form lives in the project's README/DESCRIPTION.md.
builtin_metric_enables:
  - adapter_kind: VMWARE
    resource_kind: VirtualMachine
    metric_key: net|packetsPerSec
    reason: required by IDPS Planner dashboard widget X (Scoreboard)
```

Loaders read `PROJECT.yaml` once per project; child component YAMLs
inherit attribution and `builtin_metric_enables` semantics. Avoids
per-file duplication. Component YAMLs themselves stay clean — just
content, no attribution boilerplate.

For factory-native content, no `PROJECT.yaml` exists — attribution is
implicit (the factory authored it).

## `builtin_metric_enables` for factory-native content

Currently lives on the bundle YAML. Once the legacy single-dashboard
bundles are deleted (v2 item #1), there's no bundle wrapper to hold this
metadata for factory-native dashboards.

**Decision:** move `builtin_metric_enables` into an optional field on the
**dashboard YAML** itself. Scoped per-dashboard. The walker reads it during
install/sync to enable any required OOTB metrics that aren't on by default.

```yaml
# dashboards/some_dashboard.yaml
id: <uuid>
name: "[VCF Content Factory] Some Dashboard"
description: ...
widgets: [...]
builtin_metric_enables:           ← new optional field
  - adapter_kind: VMWARE
    resource_kind: VirtualMachine
    metric_key: net|packetsPerSec
    reason: required by widget X
```

Same grammar as today's bundle YAML, just relocated. For third-party,
the field stays on `PROJECT.yaml` (project-level scope reads more
naturally there since one project can ship multiple components that
share enable requirements).

## Management packs

Same scheme as content:

- **Factory-native MPs** (e.g., today's `managementpacks/synology_nas.yaml`)
  move to `content/managementpacks/<file>.yaml`.
- **Third-party MPs** would live at `third_party/<project>/managementpacks/<file>.yaml`.

For now, MPs continue to use their **distinct lifecycle** — MPB build
path, `.pak` install API, no `[VCF Content Factory]` prefix, separate
publish routing (`management-packs/` in the dist repo). The storage
scheme converges; the lifecycle stays distinct in v3.

**Long-term goal:** as the MP lifecycle matures (bundling, versioning,
release manifests), it can fold into the unified release+publish model.
Out of scope for v3.

## Tooling changes

Substantial scope. Bundle into a coherent rollout:

1. **Loaders** (`vcfops_supermetrics`, `vcfops_dashboards`,
   `vcfops_customgroups`, `vcfops_symptoms`, `vcfops_alerts`,
   `vcfops_reports`, `vcfops_managementpacks`) — extend each loader's
   discovery to scan `content/<type>/` AND
   `third_party/*/<type>/`. Resolve attribution by walking up
   to the nearest `PROJECT.yaml`.

2. **Validator** — enforce slug uniqueness across both provenances per
   content type. Validate `PROJECT.yaml` schema. Validate each
   component's project membership (shouldn't reference components from
   other projects across third-party boundaries — third-party should be
   self-contained, factory may share factory-only deps).

3. **Walker** (`vcfops_common/dep_walker`) — the dependency walker
   gains awareness of project scope. When walking a third-party
   dashboard's deps, prefer same-project resolution; only fall back to
   factory roots if the dependency is documented as a cross-link
   (uncommon).

4. **Release CLI** (`vcfops_packaging release`) — type-first lookup
   across both provenances. Slug uniqueness enforced. Resolved path
   drives the release manifest's `headline.source`. Manifests land in
   `releases/`.

5. **New `/bundle` CLI** (`vcfops_packaging bundle`) — interactive
   composer. Validates picks against discovered components. Output:
   `bundles/<slug>.yaml`.

6. **Publish routing** — `release_types.headline_to_dir()` already
   reads `factory_native` from bundle YAML. Extend to read project's
   `PROJECT.yaml` when source is under `third_party/`. No
   change to dist-repo routing rules (factory → top-level subdir,
   third-party → `ThirdPartyContent/<sub>`).

7. **Migration**:
   - Move `dashboards/`, `views/`, `supermetrics/`, `customgroups/`,
     `alerts/`, `symptoms/`, `reports/`, `recommendations/`,
     `managementpacks/` → `content/<type>/`.
   - Move `bundles/third_party/<name>/` →
     `third_party/<name>/`.
   - Move `bundles/<file>.yaml` → `bundles/<file>.yaml`.
   - Move `releases/<file>.yaml` → `releases/<file>.yaml`.
   - Convert each third-party project's bundle YAML attribution
     metadata into a `PROJECT.yaml` at the project root.
   - Move `builtin_metric_enables` from each third-party project's
     bundle YAML to its `PROJECT.yaml`.
   - For factory-native dashboards (post-v2-cleanup) that need OOTB
     metric enables: move from the now-deleted bundle YAML to the
     dashboard YAML's new `builtin_metric_enables:` field.
   - Update every release manifest's `headline.source` field to the
     new `content/<provenance>/<type>/<file>.yaml` path.

## Migration impact

Significant. Every content-related top-level directory moves under
`content/`. Existing repo state changes:

- ~10 factory content directories collapse from top-level into
  `content/<type>/` (dashboards, views, supermetrics,
  customgroups, alerts, symptoms, reports, recommendations,
  managementpacks).
- `bundles/` → `bundles/`. `releases/` → `releases/`.
- Third-party projects move from `bundles/third_party/<name>/` to
  `third_party/<name>/` (today: 1 project, idps-planner).
- 7+ loader path updates + walker update.
- Validator gains project-scope checks and slug-uniqueness enforcement
  across provenances.
- New `/bundle` slash command + CLI subcommand.
- Existing release manifests' `headline.source` paths updated
  (mechanical sed: prepend `content/` or
  `third_party/<project>/`).
- Every install template, agent prompt, README walkthrough, context/
  docs that reference content paths needs path updates.
- Documentation: dictionary update (define `PROJECT.yaml`, refine
  Bundle/Component/Project terms; update Bundle definition's
  "lives in" reference), README walkthrough refresh, ADMIN.md path
  references.

Backward compatibility: UUIDs and content YAML payloads unchanged. Cross-
references (SM by name, view by name) unchanged in syntax — just
resolved against a wider search path. Git history continuity: every
content YAML's blame becomes history-spanning across the rename, but
`git log --follow` traces cleanly. One-time cost.

## Relationship to v2

v2 has four items. v3 supersedes #2 (third_party/ promotion was a
half-step that v3 completes properly). The other three items stay in v2:

- v2 item #1: convert legacy single-dashboard bundles to dashboard
  releases. **Still in scope** — does not conflict with v3 layout.
- v2 item #3: time_window validator polish. **Still in scope** —
  independent.
- v2 item #4: bundle name resolver fix. **Subsumed by v3** — the new
  type-first resolver handles `third_party_content/` natively.

**Sequencing:** ship v2 items #1 and #3 first (small, independent). Then
v3 as a single coherent rollout. v2 item #4 lands as part of v3.

## Out of scope (v3)

- MP lifecycle convergence (bundling MPs, MP release manifests, unified
  install) — defer until the MP build path is stable enough.
- Bundle composition syntax (`includes: [other-bundle]`) — still v4 or
  later, no driving need today.
- Cross-project third-party dependencies — design assumes third-party
  projects are self-contained; revisit if/when one needs to depend on
  another.

## Open questions (resolve before implementation)

1. **`PROJECT.yaml` field naming.** Should it match the existing bundle
   YAML's field names exactly (`author`, `license`, `factory_native`,
   `source`) so migration is field-for-field? Or rename to clarify
   project-level scope (e.g., `attribution.author`,
   `attribution.license`)? Lean field-for-field — less to learn.

2. **Project-level `display_name`.** Bundle YAMLs today carry a
   `display_name` distinct from `name` (slug). Does `PROJECT.yaml`
   inherit this, or is it strictly internal-slug? Lean inherit — the
   display name shows up in published catalog rows.

3. **Same-name collisions across factory and third-party.** A factory
   `dashboards/foo.yaml` and a third-party
   `third_party_content/bar/dashboards/foo.yaml` (same slug). Validator
   should error or warn? Lean **error** — slug ambiguity makes
   `/release dashboard foo` undefined. Force unique slugs across all
   provenances.

4. **Migration commit shape.** One mega-commit (rename + loader update +
   metadata move + tests in one), or multiple sequenced commits (rename
   first, loaders second, etc.)? Lean **per-phase commits** so each can
   be reverted cleanly if something breaks downstream.
