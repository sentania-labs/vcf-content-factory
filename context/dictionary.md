# Dictionary

Shared vocabulary for the VCF Content Factory. Terms here are the
canonical form — agents, prompts, docs, and human conversation
should all use these definitions so we stop talking past each
other.

This file is living. When a term starts drifting in practice,
either pin the drift here or pick a new word; don't leave two
meanings floating. Add terms when you find yourself disambiguating
the same word twice.

Grouped by cluster so related terms stay contrastive.

---

## Artifact forms

### Bundle
**Internal construct.** A curated multi-content set — super
metrics, views, dashboards, custom groups, symptoms, alerts,
reports, recommendations, and/or management packs that belong
together. Declared by a manifest under `bundles/`. The unit of
authoring-time grouping. Reserve "Bundle" for genuinely
multi-content sets; a single dashboard plus its dependencies is
just a dashboard (released discretely).

*Distinct from:* Package (the output zip), Release (the shipping
event), Component (the individual content YAMLs the bundle
references).

### Component
A single content YAML — one super metric, one view, one
dashboard, one custom group, one symptom, one alert, one report,
one recommendation, or one management pack. The leaves of the
factory's content graph; what an author agent writes one of at a
time. A Bundle is a set of Components; a Release ships
Components and/or Bundles.

### Package
**External deliverable.** A zip file produced from a Release
headline (a Bundle or a Component), containing native Ops
artifacts (content-zip payloads, `.pak` files, etc.) plus
install/uninstall scripts. What a user downloads and runs. Built
by `vcfops_packaging`. Lands in the Distribution repo at a path
determined by the headline's type and `factory_native` flag.

*Distinct from:* Bundle (source-side grouping), Release (the
shipping event that produces the Package).

### Source
The YAML under `supermetrics/`, `views/`, `dashboards/`,
`customgroups/`, `symptoms/`, `alerts/`, `reports/`,
`recommendations/`, `managementpacks/`. Hand-authored, version
controlled, the canonical form of a content object.

### Rendered
The native Ops JSON/XML/ZIP a loader produces from Source.
Examples: `Dashboard.zip`, `AlertContent.xml`, a super metric's
content-zip JSON envelope. Intermediate form — not human-edited,
not the deliverable.

### Shipped
What ends up inside a Package: Rendered artifacts + install
scripts + manifest metadata. What the user's filesystem sees
after unzipping.

### Drop-in artifact
A Rendered file inside a Package that an admin could hand-import
by dragging it into the Ops SPA UI. Distinct from the install
scripts, which automate the same import headlessly.

---

## Lifecycle verbs

### Author
Forward flow: natural-language request → YAML → Bundle. The
author agents (`supermetric-author`, `dashboard-author`, etc.)
do this.

### Extract
Reverse flow: live Ops content → YAML → Bundle. The
`vcfops_extractor` path does this. Used when a useful thing
already exists in an instance and we want to bring it into the
factory as a third-party bundle.

*Distinct from:* Author.

### Sync
Push Source (or its Rendered form) onto an instance via REST /
content-zip import. The content now exists on the instance but
may not be collecting/evaluating yet.

### Enable
Flip policy flags so a Synced object actually starts working:
super metrics begin collecting, alerts begin evaluating, etc.
Separate step because Ops policies gate runtime behavior.

### Install
Sync + Enable + Verify, end-to-end. When the user says "install
this," this is what they mean unless they scope it down. Install
is a *semantic* operation — there are three distinct *paths* that
all achieve it (see below).

*Distinct from:* Sync (push only), Enable (flip policy only).

### Tooling install
Install performed by the factory's own CLIs —
`content-installer` driving `python3 -m vcfops_supermetrics sync`,
`vcfops_dashboards sync`, etc. — directly against a live
instance. Caller is the repo. Requires this working tree
checked out. Used during authoring, QA, and lab validation.
Bypasses the Package entirely — reads Source, renders in
memory, pushes via REST.

### Package install
Install performed by the `install.py` / `install.ps1` scripts
that ship *inside* a Package. Caller is an end user on their
own machine. Requires only the unzipped Package — no repo, no
vcfops_* Python modules. This is the user-facing install path.

### Manual install
Install performed by an admin hand-dragging Drop-in artifacts
from an unzipped Package into the Ops SPA UI. No scripts, no
repo — the SPA wraps the dropped files into a content-zip
envelope client-side. The fallback when Package install can't
run (no Python, no PowerShell, air-gapped with no script
execution).

### Install script(s)
The `install.py` and `install.ps1` files inside a Package —
the drop-in executables a user runs to perform a Package
install. Plural because we ship one per supported OS/runtime.
Generated from templates in `vcfops_packaging/templates/`.

*Distinct from:* Tooling install (which uses the `vcfops_*`
Python modules directly, not these scripts).

### Recon
Read-only investigation of an instance *before* authoring:
"does this already exist, is the metric collected, what policy
owns it, is there a built-in that covers the need?" Always runs
before an author agent.

### Verify
Read-only check of an instance *after* install: "did the content
land, is it enabled, did dependencies resolve?" Same agent
(`ops-recon`), distinct phase.

*Distinct from:* Recon.

---

## Release lifecycle

The *Release lifecycle* is how content gets from the factory
repo to the public Distribution repo. Concepts in this section
are recent (introduced 2026-04-27) and supersede the earlier
`released: bool` flag-only model. Full design:
`designs/release-lifecycle-v1.md`.

### Release
**A shipping event.** A YAML manifest under `releases/` that
declares 1+ headline artifacts and the metadata that should
accompany them on ship: name, version, description, release
notes, optional `deprecates:` list. One file per release line;
versions evolve inside the file across `/release` calls.

A Release is what `/publish` consumes. Without a Release
manifest, content does not ship to the Distribution repo.

*Distinct from:* Bundle (curated content set), Package (the
output zip), Headline (a single artifact within a Release).

### Headline
The user-facing artifact in a Release manifest — what a consumer
is "shopping for" when they browse the Distribution repo. Source
path implies type (`dashboards/foo.yaml` → dashboard;
`bundles/foo.yaml` → bundle), and type determines the
Distribution-repo subdirectory. A Release can have multiple
headlines (a multi-bundle release ships N headline zips).
Transitive dependencies (views, SMs, custom groups) travel with
the headline implicitly via the dependency walker; they aren't
listed separately in the manifest.

### Publish
The orchestrated operation that takes every Release manifest in
`releases/`, builds its headline zips, copies them to the
correct subdirectory in the Distribution repo, regenerates the
catalog README between AUTO markers, commits, and pushes. Driven
by `python3 -m vcfops_packaging publish` (or the `/publish`
slash command). Idempotent — content-hash compare skips zips
that haven't changed.

*Distinct from:* Sync (push to a live VCF Ops instance), Install
(end user runs the Package).

### `/release`
The slash command (and underlying CLI) that materializes a new
Release manifest for a content item. Auto-bumps the minor
version on subsequent calls for the same slug. Flips
`released: true` on the source YAML. Commits both files. Local
operation only — does not push or trigger a Publish.

### Distribution repo
The public git repo at
`sentania-labs/vcf-content-factory-bundles` (cloned locally as
`vcf-content-factory-bundles/`). Where Publish lands every
shipping artifact. Layout mirrors the factory's content
categories: `dashboards/`, `views/`, `supermetrics/`,
`customgroups/`, `reports/`, `bundles/`, `management-packs/`,
plus a `ThirdPartyContent/` subtree for third-party content and
`retired/` for deprecated artifacts.

### Factory-native vs Third-party content
A Bundle (or Component) carries `factory_native: true` (default)
or `factory_native: false`. Factory-native content was authored
in this repo by the factory's own agents. Third-party content
was extracted from a live instance via `vcfops_extractor` and is
maintained here as a redistribution wrapper — original authors
hold the rights; the factory's value-add is the install /
uninstall machinery and dependency walking.

Publish routes them to different subtrees in the Distribution
repo: factory-native bundles to `bundles/`, third-party bundles
to `ThirdPartyContent/<sub>/`. The `Author` and `License` fields
on third-party manifests are preserved through to the rendered
catalog README.

### Versionless naming
Consumer-facing artifacts in the Distribution repo are named
`<slug>.zip` — no version suffix. Internal version tracking
inside `releases/*.yaml` continues (used for change detection
and audit), but the Distribution repo always shows exactly one
artifact per release so consumers can't pick a stale or broken
older copy. Deciding factor 2026-04-27.

---

## Content categories

### Content
Things authored *for* VCF Ops: super metrics, views, dashboards,
custom groups, symptoms, alerts, reports, recommendations.
Shipped via content-zip import. Display names carry the
`[VCF Content Factory]` prefix.

### Management Pack (MP)
An adapter + object model shipped as a `.pak` file. *Extends*
VCF Ops by adding new kinds of objects, metrics, and properties
from external systems (e.g., a REST API). Lifecycle is distinct
from Content: different build path (MPB), different install API,
no `[VCF Content Factory]` prefix.

*Distinct from:* Content.

---

## Environment terms

### Instance
Any deployment of VCF Operations.

### Lab
One of Scott's two specific test instances. Two-lab policy:
- **Primary** lab (`vcf-lab-operations.int.sentania.net`,
  user `claude`) — read-only recon only.
- **Devel** lab (`vcf-lab-operations-devel.int.sentania.net`,
  user `admin`) — destructible; all mutating work runs here.

---

## Design-time artifacts

### Design
The approved upfront artifact an authoring agent builds against.
For management packs: `mp-designer`'s output under `designs/`
(object hierarchy, metric classification, request mapping). For
content: the plan-mode mockup/plan saved before authoring begins.

### Plan
The step-by-step approach agreed with the user in plan mode
before any author runs. Saved as part of the Design artifact
for traceability. "The plan" is how we got here; "the design"
is what we decided to build.

### Manifest
The bundle YAML under `bundles/`. Declares which Source files
belong in a Bundle, plus packaging metadata (name, version,
attribution). Input to `vcfops_packaging build`.

*Distinct from:* Design/Plan (upstream, human intent) and
Bundle (the YAML collection the manifest references).

---

## Pointers

- Repo layout and agent roster: `CLAUDE.md`
- UUID and cross-reference rules: `context/uuids_and_cross_references.md`
- API surface map: `context/content_api_surface.md`
- Install + enable details: `context/install_and_enable.md`
- Release lifecycle design: `designs/release-lifecycle-v1.md`
