# Content migrator v1

Status: spec, 2026-09-14, awaiting Scott's approval of the spec and the
repo creation. Parent plan: `content-migrator-plan-v1.md` (M3). Library
it builds on: `vcf-cf-tooling-core` 0.1.0, released 2026-09-14
(`tooling-core-carveout-v1.md`).

## What it is

A tool a VCF Operations admin runs on their own workstation (Mac,
Windows, Linux) to move custom content from one instance to another.
It reads a content export zip, shows everything in it as a dependency
tree, lets the admin pick what to keep, previews each item with mock
data so they can recognise it, and writes an import bundle the target
instance accepts. No credentials, no network, no LLM.

## Decisions, with Scott's words

Interview on 2026-09-14. Each answer is quoted as given.

| Question | Answer | Consequence |
|---|---|---|
| Source | "Offline export zip only (Recommended)" | v1 never logs in anywhere. The admin exports from the source instance the normal way and points the tool at the zip. Live pull is a v2 item. |
| Versions | "8.x to 9.x from the start" | The tool translates 8.x export formats into what 9.x imports. This is the largest piece of v1 and is corpus-driven (below). |
| 8.x corpus | "Saved 8.x export zips only" | No live 8.x. The translation layer is built and tested against export zips Scott supplies. Coverage is what those zips contain; anything not in the corpus is refused, not guessed. |
| 8.x floor | "8.10 and later (Recommended)" | Exports older than 8.10 are refused with a message naming the floor. |
| Outbound settings | "I believe the secrets are encrypted, so we should just pass them along." then "Yes, endpoints and rules, as exported" | Notification rules and outbound endpoint definitions ride in the bundle exactly as the export carries them, encrypted values included. The tool does not decrypt, edit, or strip them. M4 acceptance includes a real import proving the target accepts the values; if it does not, that is a finding, not a silent drop. |
| Operator | "Customer-run, no LLM (Recommended)" | Deterministic. No API key, no outbound calls. Shippable as a per-OS binary. |

## Scope

In v1:

- Input: one VCF Ops / Aria Operations content export zip, 8.10 or
  later, or a 9.x export.
- Content types: dashboards, views, super metrics, custom groups,
  symptoms, alerts, recommendations, reports, notification rules and
  outbound endpoints. Anything else in the zip is listed as "carried,
  not inspected" and passed through untouched if selected.
- Dependency tree: dashboard to view to super metric; alert to symptom
  to recommendation; notification rule to alert and endpoint; super
  metric to super metric. Built by the library's walker
  (`vcfcf_core.common.dep_walker`), which already follows every one of
  these edges since PR #156.
- Selection: pick any node; dependencies are pulled in automatically
  and shown as "required by". Deselecting a dependency that something
  selected still needs is refused with the reason.
- Preview: each dashboard and view rendered with mock data, the same
  renderer the factory uses (`vcfcf_core.dashboards.render`) fed by a
  mock metric provider. Super metrics show the formula and its
  resolved references. Alerts show the symptom set in words.
- Output: an import bundle the target's content import accepts. For a
  9.x source, byte-identical to what the factory's packager emits for
  the same content. For an 8.x source, the translated form.
- Report: a plain-text summary of what was carried, what was
  translated and how, what was refused and why.

Out of v1, tracked as follow-ups:

- Live read from a source instance.
- Live push to the target (the admin imports the bundle themselves).
- Renaming, re-prefixing, or editing content inside the tool.
- Diffing against the target ("what already exists there").
- Anything below 8.10.

## Shape

One Python package, `vcfcf_migrator`, depending on
`vcf-cf-tooling-core` pinned by release URL. Two entry points over the
same core:

- `vcfcf-migrator` CLI: `inspect <zip>`, `tree <zip>`, `build <zip>
  --select <file> --out <bundle.zip>`. Scriptable, used by tests and
  CI.
- `vcfcf-migrator ui <zip>`: starts a local web page on localhost,
  opens the browser, shows the tree with checkboxes and previews,
  writes the bundle on "Build". No server beyond the local process;
  closing the tab stops nothing important, closing the process stops
  everything. Every setting the CLI takes has a control on this page
  (rule 2), with defaults that work untouched.

The 8.x translation layer is a separate module with one function per
content type, each mapping an 8.x document to its 9.x form, plus a
version detector reading the export's marker. Each translation is
backed by a fixture pair from the corpus: the 8.x input and the 9.x
form a 9.x instance produced for the same content. Unknown shapes
raise and name the field, and the tool reports "refused: not in
corpus" for that item rather than emitting a guess.

Mock data: a small deterministic provider that, given a resource kind
and metric key, returns a plausible series (seeded by the key so the
preview is stable across runs). Names come from the export itself.

## Repo

`sentania-labs/vcf-cf-migrator`, public, the same pattern as the SDK
adapter repos: cloned gitignored into the factory under
`content/migrator/` with one line in a registry so the factory's agents
can work on it, but it is its own repo with its own CI and its own `v*`
tags. The factory never imports it.

CI, per the `github-ci` rule: GitHub-hosted. On PR: install the pinned
core wheel by URL, run the suite, build the bundle from the corpus and
compare against the committed expected output. On `v*` tag: the same,
then a three-OS PyInstaller matrix (ubuntu, windows, macos) producing
one binary per OS, attached to the GitHub Release alongside the wheel.
The tag push is the release (rule 13).

The corpus lives in the migrator repo under `tests/corpus/8x/` and
`tests/corpus/9x/`. Export zips can carry instance names and endpoint
definitions; Scott confirms each zip is safe to commit before it lands,
or it is redacted first. Nothing with a credential in the clear is
committed (rule 19); the encrypted outbound values are what the export
carries and are not secrets in the clear.

## Milestones inside the new repo

- **M3 (this spec)**: repo created, skeleton with the two entry points
  that start and print the library version, CI on PR and tag, one
  9.x export zip in the corpus, `inspect` lists its contents. Done
  when the tag `v0.0.1` produces three binaries that each run
  `inspect` on the corpus zip.
- **M4 (MVP)**: the use case works on a 9.x export: tree, preview,
  select, build, import the bundle into the lab's 9.x instance and see
  the dashboards. Outbound pass-through verified on that import.
- **M5**: 8.x translation, one content type per PR, corpus-driven,
  until every type in Scott's zips round-trips. `v1.0.0` when a full
  8.x export from the corpus imports cleanly into 9.x and the
  dashboards render.

## Open items for Scott

- Where the 8.x export zips are, and whether they can be committed as
  they are or need redaction first.
- Approval of this spec and of creating the public repo
  `sentania-labs/vcf-cf-migrator` under his account (rule 12).
