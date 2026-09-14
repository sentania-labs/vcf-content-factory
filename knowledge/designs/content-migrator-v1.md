# Content migrator v1

Status: approved 2026-09-14. Scott, verbatim: "go ahead and create the
repo and start work, i'll get you an export". That covers creating the
public repo `sentania-labs/vcf-cf-migrator` under his account and
starting M3. Parent plan: `content-migrator-plan-v1.md` (M3). Library
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
| 8.x corpus | "Saved 8.x export zips only" then "the 8.x exports should not be in the repo." | No live 8.x. The translation layer is built against export zips Scott supplies, which stay on the workstation and never enter the repo. Coverage is what those zips contain; anything not in the corpus is refused, not guessed. |
| 8.x floor | "8.10 and later (Recommended)" | Exports older than 8.10 are refused with a message naming the floor. Found 2026-09-14: an export zip carries no product version anywhere (checked an 8.18.7 export and a 9.0.2 export; both carry the same `6844548499441080431L.v1` marker, so that is a format marker, not an instance or version id). The admin therefore declares the source version: a `--source-version` option on every command with a matching control on the page, remembered in settings. The floor is enforced on the declared value; with none declared the tool says so and continues in inspect, and refuses to build. |
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

Corpus on hand, 2026-09-14: `corpus/scott-8.18.7-2026-09-14.zip`
(Scott, verbatim on its version: "8.18.7"; 5 dashboards, 19 views, 17
super metrics, 2 groups, 2 recommendations, 1 notification rule, 1
outbound setting, plus policies, users, roles, cost drivers, global
settings), `corpus/devel-9x-2026-09-14.zip` (lab devel, 9.0.2,
content types only), `corpus/devel-9.0.2.0-2026-09-14-full.zip` and
`corpus/prod-9.1.1.0-2026-09-14-full.zip` (lab devel and prod, every
export type the API offers), and `corpus/scott-b-9.0.2-2026-09-14.zip`
(Scott, verbatim on its version: "9.0.2", and "this is from a
different 9.0.2 instance" than the lab's; 66 dashboards across three
owners, 181 views, 99 super metrics, 22 symptoms, 13 alerts, 21
reports, 5 notification rules, 5 templates, 5 outbound settings).

Two things the corpus already proves. First, the marker file name is
byte-identical in all five zips, across two instances of 9.0.2, a
9.1.1 and an 8.18.7, so it identifies the export format and nothing
else: not the version, not the instance, not the user. Second,
same-version instances differ in which members an export carries (the
second 9.0.2 brings custom profiles, report schedules and SDMP
services that the lab's 9.0.2 does not), so member presence is
instance content, never a version signal. The reader treats every
member as optional and every absent member as normal.
The member layout of the two is the same for every content type both
carry; the 8.x zip additionally carries members the 9.x export did
not request. The 8.18.7 outbound setting is plain text (an SMTP relay
with no credentials); the encoded `exportId` and `signature` strings
in every member are signatures, not encrypted payloads.

What the 8.x to 9.x gap actually looks like. Scott, 2026-09-14: "the
8.18 and 9.0.2 (new one) are from brock's lab", so those two exports
carry the same objects before and after, and the overlap is a matched
pair set: 3 super metrics, 5 views, 3 dashboards, 1 custom group and 1
outbound setting share a uuid across the two versions. Comparing each
pair document by document:

- **Super metrics: no translation needed.** All three shared documents
  are identical apart from `modificationTime` and `modifiedBy`.
- **Views: no structural translation needed.** Two of five are
  byte-identical. The other three differ only in control id counters
  (`time-interval-selector_id_237` against `_id_5679`, which are
  instance-local sequence numbers) and in author-visible text
  (`Monthly Projected Cost` against `Projected Monthly Cost`,
  `GROUP_hardware` against `GROUP_Certificate Summary`). No element or
  attribute exists on one side and not the other.
- **Dashboards: a real but small gap.** 9.x carries keys 8.x does not
  (`autoswitchDelay`, `autoswitchTabId`) and the widget resource
  bindings name different adapter kinds (`VMWARE` against
  `mpb_vcf_operations_`), which is instance binding rather than
  version. This is the one type where a translation function is
  clearly warranted.

Caveat on how far this generalises: one lab, five content types, no
matched pair at all for alerts, symptoms, reports or recommendations,
because Brock's 8.18.7 export carries none. So the honest reading is
that M5 is probably much smaller than "one translation per content
type", and that the v1 design should assume pass-through with
per-type exceptions rather than a translation layer with per-type
pass-through exemptions. Before M5 is planned in detail, the corpus
needs an 8.x export carrying alerts, symptoms and reports.

Outbound and the export password. Found while taking the first corpus
zip from the lab (9.0.2, 2026-09-14): the export API refuses to include
notification rules or outbound settings unless the request carries an
`EncryptionPassword` header, and it enforces a mixed-character policy
on it. The encrypted values in the export are therefore tied to a
password the admin chose at export time, and the target's import asks
for the same password to decrypt them. "Pass them along" means: the
tool carries the encrypted values untouched, never asks for or stores
the password, and the report tells the admin that the import will
prompt for the password used at export. The lab's devel instance has
no notification rules or outbound endpoints today, so M4's outbound
acceptance needs one of each configured there first (a qa step, not a
tool change).

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

The real export zips never enter the repo (Scott: "the 8.x exports
should not be in the repo."). They live in a gitignored `corpus/`
directory on the workstation, or anywhere the `VCFCF_MIGRATOR_CORPUS`
setting points, and the tool's own settings page shows that path. Two
tiers of test material follow from that:

- **Committed fixtures**: small, hand-built export zips under
  `tests/fixtures/` that copy the shape of each 8.x and 9.x document
  the translation layer handles, with made-up names and no instance
  data. CI runs on these alone. Each fixture is authored from a corpus
  example by hand, and the PR body names which corpus zip it mirrors.
- **Corpus regression**: `vcfcf-migrator corpus-check` walks every zip
  in the corpus directory, runs inspect, tree and build on each, and
  prints one line per zip (ok, refused with reason, or error). It runs
  locally before a translation PR opens and its output goes in the PR
  body; CI cannot run it and does not try.

A translation counts as done only when both tiers pass.

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

- Where the 8.x export zips are on the workstation, so the corpus
  directory can be pointed at them.
