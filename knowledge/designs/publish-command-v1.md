# `/publish` command — design v1

**Status:** approved 2026-04-23
**Owner:** orchestrator + tooling agent
**Consumers:** content-packager, MP builder, tooling

## Purpose

One slash command that ships every piece of content marked
`released: true` — bundles, management packs, and individual
content objects — to the public distribution repo
`sentania-labs/vcf-content-factory-bundles`, regenerates the
README, commits, and pushes.

Replaces the current manual workflow (build → cp → hand-edit
README → commit → push).

## Core concept — two independent release knobs

Publishability is an **authoring-intent property** set on the
YAML, not a global decision. Two independent flags:

| Flag | Lives on | Controls |
|---|---|---|
| Parent `released: true/false` | bundle manifest, MP YAML | Whether the aggregated parent artifact (`Bundles/X.zip`, `ManagementPacks/X.pak`) is published. |
| Child `released: true/false` | each SM/dashboard/view/report/alert/customgroup YAML | Whether the item is also published as its own discrete artifact under `ContentComponents/<type>/`. |

**Both default to `false`.** Author agents set them based on
prompt intent:
- "I want a dashboard for X" → dashboard gets `released: true`;
  its SMs stay `false` unless the author judges them
  independently useful.
- "I want an SM that computes Y" → SM gets `released: true`.

### Parent/child semantics

- **Parent release pulls children in, always.** A released
  bundle ships with every referenced SM/view/dashboard/etc.
  regardless of the child's `released` flag — otherwise the
  bundle would be broken.
- **Child release pushes it out discretely.** A released SM
  gets its own `ContentComponents/SuperMetrics/<Name>.zip`
  with the same UUID it would have inside any parent bundle.
- Both can be true — item ships inside the bundle AND as a
  discrete artifact. Not duplicative: UUIDs are stable,
  content-zip import is idempotent.

### Discrete-eligible content types

Only types that make sense to a user on their own:

| Type | Discrete? | Rationale |
|---|---|---|
| Super metric | yes | Standalone utility common. |
| Dashboard | yes | The flagship "I want X" unit. |
| View | yes | Users share list views. |
| Report | yes | Users share reports. |
| Alert | yes | Ships with its symptoms + recommendations inside the discrete zip. |
| Custom group | yes (when reusable) | Judgment call; author decides. |
| Management pack | yes | `.pak` is already a discrete artifact; ships under `ManagementPacks/`, not `ContentComponents/`. |
| Symptom | **no** | Only meaningful inside alerts — rides with parent alert. |
| Recommendation | **no** | Same. |

## Internal versioning — required on every released unit

A second field, `version: <semver>`, is required on every
released unit. **Internal only.** No in-instance stamping, no
description suffix, no customer-visible surface (deferred).

| Field | Applies to | Default | Purpose |
|---|---|---|---|
| `version: string` | bundle manifests; MP YAML (already); every individual content YAML | `1.0.0` on new content | Git-tracked. Used by `/publish` to refuse duplicate-version republish. Bumped manually by author on each change. |

Rules:
- Bumped manually. Author/orchestrator decides major/minor/patch
  when shipping a change.
- `/publish` refuses to ship a unit whose version already exists
  in the bundles repo (detected by filename match / MP manifest
  match), unless explicitly forced.
- MPs additionally carry their existing **external** version
  (4-part semver in the MPB manifest, surfaced in `.pak` filename
  and adapter UI). MP internal `version:` is the same field used
  on other types; the external 4-part is the MPB-native version
  already in place. No change to MP external surface.
- Everything else (bundles + individual content): internal version
  only, for now.

## Publish tree in the bundles repo

```
/
  README.md
  LICENSE
  Bundles/
    [VCF Content Factory] Capacity Assessment.zip
    [VCF Content Factory] Environment Config Status.zip
    [VCF Content Factory] VKS Core Consumption.zip
    [VCF Content Factory] VM Performance.zip
  ThirdPartyBundles/
    IDPS Planner.zip
  ManagementPacks/
    mpb_synology_nas.1.0.0.1.pak
  ContentComponents/
    Dashboards/
      [VCF Content Factory] VM Performance by vCenter.zip
    SuperMetrics/
      [VCF Content Factory] Allocated vCPUs Rollup.zip
    Views/
    Reports/
    Alerts/
    CustomGroups/
```

### Self-contained discrete zips

Each discrete artifact under `ContentComponents/` is a
**self-contained installable zip** carrying its dependencies,
not a bare JSON/XML snippet. A user downloading
`ContentComponents/Dashboards/VM Performance by vCenter.zip`
gets a working install with the required SMs and views
already inside. Rationale: partial installs are a footgun;
consistency with the bundle format is a feature.

Naming:
- Bundles: `[VCF Content Factory] <Bundle Name>.zip` (current pattern)
- Third-party bundles: keep the author's naming (e.g. `IDPS Planner.zip`)
- Discrete items: `[VCF Content Factory] <Item Name>.zip`
- MPs: native `.pak` filename (includes MPB 4-part version)

## Schema changes (tooling agent scope)

### 1. Bundle manifest (`bundles/*.yaml`)

Add top-level `released: bool` (default false) and
`version: string` (default `1.0.0` for new; required once
`released: true`).

```yaml
name: vm-performance
released: true
version: 1.0.0
description: ...
supermetrics: [...]
```

### 2. Third-party bundle manifest (same schema, under `bundles/third_party/`)

Add top-level `released: bool` and `version: string`. Third-party
detection by path (`bundles/third_party/*.yaml`) — tooling's call
whether to also support an explicit `third_party: true` manifest
field.

### 3. Individual content YAML

Add optional `released: bool` (default false) and
`version: string` (default `1.0.0`) to each of:
- `supermetrics/*.yaml`
- `dashboards/*.yaml`
- `views/*.yaml`
- `reports/*.yaml`
- `alerts/*.yaml`
- `customgroups/*.yaml`
- `symptoms/*.yaml` (version only — `released` not applicable)
- `recommendations/*.yaml` (version only — `released` not applicable)

### 4. Management pack YAML (`managementpacks/*.yaml`)

Add top-level `released: bool` (default false). `version:` already
present via the MPB manifest fields; keep existing external 4-part
semver unchanged.

Validators must accept the new fields (non-breaking: absent =
false for `released`, `1.0.0` for `version`).

## Tooling work

### A. Loader changes (small)

Each loader reads `released` and `version` into its model.
No behavior change at validate/sync time; fields are metadata
consumed by the publish pipeline.

### B. New discrete artifact builder (`vcfops_packaging`)

New CLI subcommand (exact name tooling's call):

```
python3 -m vcfops_packaging build-discrete <content-type> <item-name>
```

Behavior:
- Resolves the item and its transitive deps.
- Generates a self-contained zip identical in shape to a bundle
  zip (same `supermetric.json` / `Dashboard.zip` / `Views.zip` /
  `AlertContent.xml` / `Reports.zip` layout) but scoped to the
  single item + its deps.
- Same install/uninstall scripts embedded (`install.py`,
  `install.ps1`).
- README inside the zip is item-focused, not bundle-focused.

### C. README auto-gen helper (`vcfops_packaging`)

Regenerates per-section tables between marker pairs:

```
<!-- AUTO:START <section-name> -->
| Name | Version | Description |
|---|---|---|
| ... |
<!-- AUTO:END -->
```

Sections: `bundles`, `third-party-bundles`, `management-packs`,
and one per discrete content type (`dashboards`, `supermetrics`,
`views`, `reports`, `alerts`, `customgroups`). Section emitted
only if at least one released item exists; otherwise the body
between the markers is blank.

### D. `/publish` slash command (`.claude/commands/publish.md`)

Orchestrator-facing command. Flow:

1. **Validate** all content types (existing validate CLI).
2. **Scan released bundles** → delegate build to content-packager
   for each.
3. **Scan released MPs** → delegate to MP builder for each.
4. **Scan released individual items** → build-discrete for each.
5. **Version guard** — for each unit, refuse to ship if the
   exact filename (bundles, MPs, discrete items) already exists
   in the bundles repo with a different content hash. Force flag
   overrides.
6. **Stage to `vcf-content-factory-bundles`** — rsync-style:
   add new, replace changed (by content hash), remove
   artifacts that were previously released but are no longer
   (the release-revocation path).
7. **Regenerate README** between `<!-- AUTO:START -->` and
   `<!-- AUTO:END -->` markers.
8. **Git status check** in bundles repo. If dirty, commit with
   auto-generated message summarizing what changed
   ("Publish: +VM Performance v1.0.0, updated Capacity
   Assessment v1.0.1 → v1.0.2"). Push to main.
9. **Report** back to user with the commit SHA + list of
   artifacts updated/added/removed.

## README structure

```markdown
# VCF Content Factory Bundles

... hand-written intro, installation, requirements ...

## Bundles
<!-- AUTO:START bundles -->
| Name | Version | Description |
|---|---|---|
| [VCF Content Factory] Capacity Assessment | 1.0.0 | ... |
<!-- AUTO:END -->

## Third-Party Bundles
<!-- AUTO:START third-party-bundles -->
...
<!-- AUTO:END -->

## Management Packs
<!-- AUTO:START management-packs -->
...
<!-- AUTO:END -->

## Content Components

### Dashboards
<!-- AUTO:START dashboards -->
...
<!-- AUTO:END -->

### Super Metrics
<!-- AUTO:START supermetrics -->
...
<!-- AUTO:END -->

(... etc per discrete content type ...)

... hand-written Uninstall, Compatibility, Source, License ...
```

## Out of scope (explicitly deferred)

- **External / customer-visible versioning.** No sentinel custom
  group, no description suffix, no in-instance version stamp. A
  customer has no in-UI signal about which bundle version they're
  running. Known limitation; revisit later.
- **Install-script version reconciliation.** No "upgrading from
  v1.0.1 → v1.0.2" output; no detect-existing logic.
- **Version-map fingerprint helper.** No `vcf-content-factory
  check <host>` utility.
- **Changelog generation.**
- **Signing/checksums** for published zips.
- **Multi-repo publishing** — only `vcf-content-factory-bundles`.
- **Auto-bumping** of versions. Authors bump manually.

## Implementation order

1. Tooling: schema — add `released` + `version` to all YAML
   schemas + loaders. Non-breaking, lands first.
2. Tooling: discrete artifact builder.
3. Tooling: README auto-gen helper.
4. Tooling: `/publish` slash command.
5. Author agents: update prompts so `released` + `version` get
   set at authoring time based on prompt intent.
6. Backfill: set `released: true` + `version: 1.0.0` on every
   bundle + MP + content item currently shipped.
