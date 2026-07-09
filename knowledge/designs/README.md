# `designs/` — Intent capture for authored content

Every piece of authored content gets a design note here capturing the
**initial prompt** (verbatim) and the **distilled vision**. The
orchestrator writes the note before delegating to an author agent —
see CLAUDE.md → *Delegation protocol → step 2*.

Over time this directory becomes the sample-prompt corpus for the
framework: examples of what users actually asked for, paired with
what was produced.

## Layout

```
designs/
  supermetrics/<slug>.md
  views/<slug>.md
  dashboards/<slug>.md
  customgroups/<slug>.md
  symptoms/<slug>.md
  alerts/<slug>.md
  recommendations/<slug>.md
  reports/<slug>.md
  bundles/<slug>.md
  managementpacks/<slug>.md
```

Subdirectory names match the content directory at the repo root.
`<slug>` is the kebab-case slug that matches the eventual content
slug (so a dashboard YAML named `host-pressure.yaml` pairs with
`designs/dashboards/host-pressure.md`).

Multi-object requests get one design file per object. The bottom-up
delegation order still holds — write all the design files first, then
delegate the authors in dependency order.

Pre-existing flat files at the top of `designs/` (e.g.
`release-lifecycle-v1.md`, `cloudflare-mp-v1.md`) are framework
feature designs and legacy MP designs. They stay where they are. New
content goes in the typed subdirectories above.

## Template

```markdown
# <Content display name>

- **Type:** dashboard | supermetric | view | customgroup | symptom | alert | recommendation | report | bundle | managementpack
- **Slug:** <kebab-case-slug>
- **Authored YAML:** <relative path, e.g. dashboards/host-pressure.yaml>
- **Date:** YYYY-MM-DD
- **Status:** drafted | authored | installed | retired

## Initial prompt

> Paste the user's request verbatim. No editing, no smoothing. If it
> took multiple turns of clarification, paste the relevant turns in
> order, attributed (`User:` / `Orchestrator:`).

## Vision

A short distillation of what the user wants and why, after any
clarifying questions. A few bullets is enough. Examples of useful
content here:

- The metric or signal at the core of the request
- The audience (operators? capacity planners? auditors?)
- Scope choices (per-host vs per-cluster, last 24h vs trend, etc.)
- Anything explicitly out of scope
- Why this isn't covered by existing content (recon outcome in one
  line)

## Notes (optional)

Anything else worth preserving: ops-recon findings, alternative
shapes considered, related content, follow-up ideas. This section is
for the orchestrator and the author; the prompt+vision sections
above are the prompt-of-record and should not drift after authoring.
```

## Rules of thumb

- **Verbatim prompt, distilled vision.** Don't summarize the prompt;
  do summarize the vision.
- **Skip only for in-flight corrections.** New content always gets a
  design file. A small follow-up tweak to existing content does not.
- **One file per content object.** Don't bundle multiple objects into
  one design file even if they were authored in the same session.
- **Author agents may read, never rewrite.** The design file is the
  prompt-of-record. Authors can add a `## Notes` section, but the
  prompt and vision sections are owned by the orchestrator.
