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
**Internal construct.** A definition of content expressed in this
repo's YAML: the super metrics, views, dashboards, custom groups,
symptoms, alerts, reports, recommendations, and/or management
packs that belong together. Declared by a manifest under
`bundles/`. Bundles are the unit of authorship.

*Distinct from:* Package.

### Package
**External deliverable.** A zip file produced from a Bundle,
containing native Ops artifacts (content-zip payloads, `.pak`
files, etc.) plus install/uninstall scripts. What a user
downloads and runs. Built by `vcfops_packaging`.

*Distinct from:* Bundle.

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
