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
| Versions | "8.x to 9.x from the start", then 2026-09-14: "but do we really need to account for them? if operations imports them properly, let them handle it, and we just handle dependency tracking, preview generation, and output bundle creation based on selected objects." | **No translation layer.** The tool carries each selected object's document through unchanged and lets the target's import do what it already does with an 8.x document. The tool's job is the three things Scott named: dependency tracking, preview, and bundle creation from the selection. |
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

**Pass-through is the contract, and it constrains the build path.**
There is no translation module. The one rule that makes pass-through
safe: a selected object's document goes into the output bundle as the
bytes the export carried, never as a re-serialization of a parsed
model. Parsing is for the tree and the preview only. Re-rendering a
document the tool does not fully understand is how an 8.x field, or a
9.2 field this tool has never seen, gets silently dropped; copying
bytes cannot lose a field it does not know about. Where a bundle
requires a container the export does not have (a manifest, a zip
layout), the tool writes the container and copies the documents into
it.

Subsetting is where that rule earns its keep, because an export does
not store one object per file. All 181 views in one corpus zip live in
a single `views.zip/content.xml`; all 99 super metrics live in one
`supermetrics.json`; an owner's dashboards share one inner zip. So the
tool rebuilds the containers and copies the documents: the selected
`ViewDef` element subtree, the selected super metric object, the
selected dashboard entry, each carried over verbatim into a freshly
written container holding only what the admin picked. Rewriting the
container is expected. Rewriting a document is not.

A subset also has to be closed, which is what the dependency tree is
for: selecting a dashboard pulls in its views and their super metrics,
and deselecting something another selection still needs is refused
with the reason. A bundle whose documents reference objects it does
not carry is the one failure mode subsetting can introduce on its own,
and the walker is what prevents it.

This also means the tool is not a validator. If the target's import
refuses a document, that is the target's answer about that content,
and the tool's report says which object was refused and what the
target said. The admin is no worse off than importing the original
export by hand, which is the baseline this has to beat.

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
matched pair for alerts, symptoms, reports or recommendations, because
Brock's 8.18.7 export carries none. Under pass-through that caveat
stops being a blocker: the tool does not need to understand a
difference it never rewrites. The missing matched pairs now matter
only for M5's verification pass, which finds out by importing rather
than by comparing.

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
  **Built 2026-09-14, PRs #2 and #4**: read, tree, closed selection,
  byte-exact build, per-object preview and the selection page, proven
  against five real exports. The import half is not done: no bundle
  this tool wrote has been fed to a VCF Operations instance yet, and
  until one is, M4 is not complete. That is the next thing to do and
  it needs Scott's go, since it writes to a live instance.
- **M5**: cross-version verification, not translation. Build a bundle
  from Brock's 8.18.7 export, import it into a 9.x instance, and
  record per type what the target accepted. Anything refused becomes
  either a report message or, if a container-level fix makes it work,
  a fix in the bundle writer. `v1.0.0` when an 8.x-sourced bundle
  imports into 9.x and the dashboards render.

## Logging

Scott, verbatim, 2026-09-14: "V0.1.0 should provide very robust logs
which when paired with an input and output bundle and pointers from ops
tell a whole story, but the logs itself and the ops error(s) is enough
to diagnose. No secrets not confidential data but solid verbose logs,
we can dial it back around 0.3 or 0.4".

So the bar for v0.1.0 is: a support case arrives as a log plus whatever
VCF Operations said when the import failed, and that pair is enough to
say what the tool did and why. The bundles and the source export make
the story complete but are not required to reach a diagnosis. Verbosity
is deliberately high for the early releases and gets dialled back
around v0.3 or v0.4, once the failure modes are known.

What a log must carry:

- A run header: tool version, library version, Python, platform, the
  exact argument vector, the declared source version and where it came
  from, the corpus directory setting, and a fingerprint of the input
  (size, member count, member names, manifest counts) so two runs can
  be told apart and an export identified without shipping it.
- Every decision, with the object it concerns and the reason: a
  reference followed or not followed and which spelling it was written
  in, a node added to a closure and what required it, a widget
  classified and which code and which evidence, a grid widened, a
  container rebuilt, a member carried or skipped.
- Every refusal and every swallowed failure. Nothing the tool decides
  to keep quiet about in its output may be quiet in the log.
- Counts and timings per phase, so a slow or wrong run can be located
  without a rerun.
- The output fingerprint on a build: member list, per member size, and
  the hash of each carried document, so "what did it actually write"
  is answerable from the log alone.

What never goes in a log, and this is the harder half:

- Credentials of any kind, the export encryption password, and the
  encrypted values an export carries for outbound endpoints and auth
  sources. Not even their length.
- People. The export carries `usermappings.json`, `users.json` and
  owner uuids; user names, display names, mail addresses and user or
  owner uuids are excluded. A dashboard's owner is logged as a stable
  per-run pseudonym, `owner-1`, `owner-2`, so multi-owner behaviour is
  still legible.
- Metric values and mock values. The preview's numbers are invented and
  say nothing, but real metric keys are content and are logged; sampled
  or observed values never appear because none are read.

Two limits of the exclusion, stated rather than left in a code comment. A
person value of three characters or fewer is not excluded: it cannot be told
from an ordinary word, and substituting it would rewrite the customer's own
content. Neither are values that are ordinary words in their own right, the
built-in `admin` account being the one that matters, for the same reason: a log
that says `"[excluded:person] alert"` where VCF Operations says `"admin alert"`
cannot be paired with what Ops said, which is the whole bar. The file paths the
admin typed are carried as given, and the log's first line says so, because the
tool cannot be diagnosed without knowing which file it was pointed at.

The content-versus-people boundary was put to Scott explicitly, since
"no confidential data" could be read either way, and he agreed to it on
2026-09-14: content identity in, people out. Content identity is in scope: kind, uuid and name for dashboards,
views, super metrics, groups, symptoms, alerts, reports, rules,
templates and endpoints, plus metric and property keys. That is what
makes the log diagnostic, it is what the paired bundles carry anyway,
and it is the customer's own content rather than anyone's personal
data. The log says at the top, in one line, what classes of thing it
contains, so an admin can decide before sending it.

Shape: one line per event, machine readable, with a human readable
rendering available. Off by default at the usual level, `--log FILE`
and a level flag, and a control on the page. The page also offers a
"save diagnostics" action producing a single file holding the log, the
run header, the input fingerprint and the resulting bundle's manifest,
ready to attach to a mail, with the contents named on the button.

## The import test

The premise of the whole pass-through design is that a target instance
accepts a bundle this tool wrote, including one built from an 8.x
export. Nothing verified so far tests that: every check to date is the
tool agreeing with itself and with the export files. Scott authorized
the test on 2026-09-14, answering "1. Yes." to being asked for
permission to import into the devel lab instance.

It writes content to a live instance, so what it creates is recorded
and reversible.

**Result, 2026-09-15: it failed, and nothing was created.** A bundle
built from the 8.18.7 export, one dashboard with a fully resolved
closure of 5 views and 13 super metrics, was rejected by devel 9.0.2 in
121ms with `INVALID_FILE_FORMAT`, "Failed to import content: invalid
format", and an empty `operationSummaries`. That is a structural
rejection of the zip, not a per-item complaint. Verified read-only
afterwards that no super metric, view or dashboard from the selection
exists on the instance.

The hypothesis, from comparing the bundle against a real 9.x export and
against the factory's own `packager.py`: the bundle lacks the zip
directory entries `dashboards/` and `dashboardsharings/` and the
`dashboardsharings/<owner>` sibling that every real export and every
working factory-built bundle carries when `dashboards/<owner>` is
present. `packager.py` carries a comment recording that an earlier
factory implementation missing exactly these was rejected with this
same code. The 8.18.7 export itself carries no `dashboardsharings`
member at all, so pass-through faithfully carried that absence forward.

This is the finding the whole milestone existed to produce, and no
amount of self-consistency testing could have produced it: every check
before this was the tool agreeing with itself and with the export
files. It also sharpens the pass-through rule. A document is carried
untouched; the container around it is the tool's to build, and a
container member the target requires is the tool's responsibility to
write even when the source export did not have one. Absence of
scaffolding is not content to preserve.

## The overwrite scare, and what it actually was

Recorded here because the wrong conclusion was reported to Scott before
the right one was found, and the reasoning error is worth keeping.

On 2026-09-15 a dashboard imported into devel read back with every
widget's `config` empty and `importComplete: false`. Re-importing the
identical bundle did not fix it. Neither did the factory's own
`vcfcf_dashboards` build and install path. Five imports, all reporting
`FINISHED` and `errorCode: NONE`. The conclusion drawn, and escalated,
was that the product empties an existing dashboard on overwrite and
that content could not be restored.

That was wrong. A read-only investigation
(`knowledge/context/api-surface/dashboard_import_two_phase_materialization.md`)
found that the import materializes in two phases. Phase 1, inside the
operation, writes the record, widgets, layout and `states`, parks the
bundle's portability tokens in `entryKeys` and sets
`importComplete: false`. Phase 2 runs asynchronously, resolves those
tokens to instance-local ids, writes each widget's `config`, clears
`entryKeys` and sets `importComplete: true`. A bundle's `config` is
tokenized, `kind:resourceKind:id:6_::_` rather than an instance-local
id, which is exactly why `config` is absent until phase 2 and why the
opaque `states` blob survives phase 1 untouched.

Both dashboards completed on their own and read fully bound hours
later. Nothing was ever broken, nothing needed restoring, and the 8.x
import was never implicated: `Cluster Cost Details` from the 8.18.7
export is bound on devel. The earlier reading that the 9.x success
might have been a no-op merge is also settled: the import is a
uuid-keyed replace, proven by `creationTime` being reset to the import
time on replaced dashboards while untouched siblings keep their
original.

The error was measuring immediately after each import and then
measuring again, which restarted the settling clock each time and made
a transient state look permanent and then sticky. `FINISHED` means the
end of phase 1 only, and `imported` is a processed count rather than a
changed count, so the envelope is truthful and simply cannot speak to
phase 2. The product exposes no phase-2 signal on the Suite API.

What the tool should do, and should not:

- Verification polls `importComplete: true`, or the cheaper `entryKeys`
  being null, before reading config or taking a screenshot.
- The two states get different words. Minutes old is settling. Hours or
  days old is a failure, and the pending `entryKeys` name the adapter
  kind that cannot be resolved, which turns an opaque hang into "install
  the X adapter".
- **No warning that importing over existing content is unsafe.** It is
  safe. That warning would be a permanent cost paid for a transient
  state.
- **No delete before import.** It does not help the resolvable case and
  re-stalls the unresolvable one.

The genuine failure mode exists on the same instance and is unrelated:
three dashboards have been `importComplete: false` since May and June,
their pending `entryKeys` naming `SqlServerAdapter`, `OracleDBAdapter`
and `mpb_rubrik`, none of which is among the 21 adapter kinds installed.
Phase 2 cannot resolve a kind whose adapter is absent.

## Release log

- **v0.0.1** (2026-09-14): M3 skeleton, PR #1 merged with a clean Codex
  pass. Proves the release path: four one-file binaries (Linux, macOS
  arm64, macOS x86_64, Windows) plus the wheel. Authorization: Scott,
  verbatim, "go ahead and create the repo and start work, i'll get you
  an export", then "sounds good" to "I'll tag `v0.0.1` to prove the
  four-binary release. That tag is on a repo you just authorized me to
  create and start work in, so I'll treat it as covered unless you say
  otherwise."

## The corpus leak, and what was done about it

Found by the M4a review, 2026-09-14: one value harvested from the lab's
own prod export reached the public repo, `0c44e115-dc21-4ea5-8a56-01c22f18325b`,
the internal account id of the built-in `admin` user on
vcf-lab-operations. It appeared as `OWNER_2` in
`tests/fixtures/make_export_fixture.py`, landed on `main` through the
M3 merge, and was therefore inside the `v0.0.1` source archive. It was
not a credential and granted nothing, but the corpus is not supposed to
reach the repo at all. A scan of every blob in `main`'s history found
that one value and nothing else; the other uuid the review named,
`b58a71ee-...`, appears nowhere in the corpus and was already invented.

Scott's decision, verbatim: "Write main so it's clean." `main` was
rewritten with an invented value, the `v0.0.1` tag and release were
re-cut from the clean commit, and the M4a branch was rebased onto it.

The recurrence guard is a scan that builds its needles from the corpus
rather than from a list someone remembered: every uuid and every name
in every member of every corpus zip, nested zips included, matched
against every blob in every revision. It runs before a PR opens. The
first hand-written version of this check missed a real display name
that the generated version caught, which is the argument for generating
the needles.

## Open items for Scott

- Where the 8.x export zips are on the workstation, so the corpus
  directory can be pointed at them.
