---
name: vcfops-orchestration
description: >
  How the VCF Content Factory orchestrator delegates work, handles
  toolset gaps, and sequences multi-agent workflows. Covers the
  delegation protocol (recon-first, bottom-up authoring, serial
  authors, parallel research), toolset gap triage (punt / explore /
  fix), and workflow patterns for every content type. Use this skill
  when a content request comes in and you need to decide what to
  delegate, in what order, and how to handle blockers.
---

# VCF Content Factory — orchestration protocol

## Delegation protocol

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
   python3 -m vcfops_reports validate &&
   python3 -m vcfops_managementpacks validate`. All other CLI
   operations (sync, enable, delete, list, .pak build/install) go
   through `content-installer` or the management pack builder.
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

## When the toolset is inadequate

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

## Workflow patterns

- **Single content object:** Clarify → recon → author → validate →
  confirm → install.
- **Compound bundle:** Clarify → recon → author bottom-up (SM →
  custom group → view → dashboard, serial) → validate → confirm →
  install.
- **Symptom + alert:** Clarify → recon → symptom-author →
  alert-author → validate → confirm → install.
- **Report:** Clarify → recon → author upstream views/SMs →
  report-author → validate → confirm → install.
- **Package + QA:** Author all content → content-packager →
  qa-tester → report.
- **Management pack:** Clarify → api-cartographer → mp-designer →
  mp-author → validate → tooling/content-installer for .pak.
  MP display names use prose prefix `VCF Content Factory` (no
  brackets) — e.g. `VCF Content Factory UniFi`. Brackets are for
  content names only. `.pak` build requires bootstrapped
  `vcfops_managementpacks/adapter_runtime/`.
- **Toolset gap:** Decide: punt / api-explorer / tooling → fix →
  re-invoke author.
- **Install:** Delegate to content-installer.
- **After tooling changes:** When `tooling` modifies
  `vcfops_packaging/templates/`, `vcfops_packaging/builder.py`, or
  `vcfops_dashboards/render.py`, rebuild all bundles via
  content-packager. Not optional.
