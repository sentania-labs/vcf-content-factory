# Defect gate isolation: user vs maintainer (v1, proposal)

Status: **proposal, nothing built.** Building starts on an explicit go.

Origin: cross-workspace request `50dc7556` (lab-admin, 2026-09-03),
relaying Scott's VMware Explore conversation with a Content Factory
user who built a NetApp MP and a second Exadata-class MP from a clone.
Verbatim complaint: the defect system blocks his work when someone
else commits a defect that has nothing to do with what he is consuming.
Refined with Scott 2026-09-09; this revision supersedes the first draft
of the same date, which recommended a more complicated merge rule.

## Recommendation

Five decisions, in dependency order.

1. **Registry selection is by file presence, not configuration.** In a
   factory checkout: use `defects.local.md` if it exists, otherwise
   `defects.md`. No flag, no setting, no question. Scott's checkout has
   no local file and so behaves exactly as it does today.
2. **A consumer's registry is `defects.local.md`**, a filename the
   factory never ships. It starts empty because it does not exist until
   they make one, and a `git pull` can never conflict with a path
   upstream does not carry. The factory's `defects.md` stays tracked
   (see "Why not gitignore").
3. **Per-entry fault isolation in the parser** so one malformed entry
   stops gating only the artifact it names, instead of every artifact
   everywhere.
4. **A missing or unreachable registry warns, it does not refuse.**
   This already is the behavior on the `publish` path; the pak CI is
   the outlier.
5. **`/publish` and a `v*` tag get the same strictness.** Both are
   shipping; there is no reason for one to be laxer than the other.

Together these remove the reported failure without changing what gates
a first-party release. Scott's own strictness is unchanged or higher;
only the stranger's coupling to his working branch goes away.

### Where the gate runs: a pre-push hook, not pak CI

`defects.md` exists in exactly one repo: the factory, at
`knowledge/context/defects.md`. Verified by inspection, none of the six
pak repos carries a defects file of any name. That is why the pak CI
curls one, and it is the wrong shape: the registry lives in the
factory, the decision to release is made in the factory, and the person
tagging is standing in the factory. Shipping the registry over a
network to the one place that does not have it is what causes all three
leaks.

There is no factory command that cuts a pak release today.
`managed_paks.md:19` is explicit: "Authoring is normal git. `cd
content/sdk-adapters/<name>`, edit, commit, push to the pak's own
remote." RULE-012's factory-side check is therefore a procedural
obligation with nothing enforcing it, and the pak CI gate exists as the
only mechanical enforcement.

**The hook holds no policy; it wires up work that already existed.**
`scripts/version_line_guard.sh` already implements both release rules
(RULE-014, the 0.x dev-preview line is never tagged; RULE-012, an open
blocking defect refuses the pak), already parses the pre-push stdin
format, and already derives the pak name from the origin remote exactly
as CI does. Its own header says it "does not (yet) run automatically"
and was written to be wired into a real git hook. This is that wiring.
A first implementation pass reimplemented the RULE-012 half in the hook
and silently dropped RULE-014; delegating instead is both smaller and
strictly more correct.

**Move the gate to a `pre-push` git hook in each pak clone.** The pak
clones live at `content/sdk-adapters/<name>/`, inside the factory
working tree, so the hook reads the factory registry over a relative
filesystem path. No network, no curl, no reachability question, and a
consumer's clone sits in the same position relative to their own
factory reading their `defects.local.md`. The pak CI gate step is then
deleted rather than rewritten, and the template ships without it.

Mechanics:

- The hook body is a tracked, reviewable file, not a copy dropped into
  `.git/hooks/`. Git cannot version anything inside `.git/`, but
  `core.hooksPath` moves the hooks directory into the working tree.
- `git config core.hooksPath <dir>` is set once per clone. It is a git
  config value, so it is per-clone and not itself tracked; bootstrap
  sets it. No symlink is involved, and the older
  `.git/hooks -> ../.githooks` trick is strictly worse since a symlink
  into `.git/` is easy to clobber and invisible when it breaks.
- Because `core.hooksPath` may point outside the repo, one tracked
  hook body in the factory can serve all six paks and every consumer
  clone. That avoids the duplication the workflow file is stuck with:
  GitHub only runs a workflow physically present in
  `.github/workflows/` of the repo being built, so
  `build-pak-on-tag.yml` is necessarily tracked twice (canonical at
  `knowledge/designs/sdk-template-scaffold/build-pak-on-tag.yml`, plus
  a copy per pak, currently identical across all six). A hook is under
  no such constraint.
- Bootstrap sets the config with an absolute path. Relative
  `core.hooksPath` resolution has historically been inconsistent about
  what it resolves against; an absolute path set by the script that
  already knows the layout sidesteps it. **Verify this before
  building.**

Trade accepted: `git push --no-verify` bypasses a hook, and a tag
pushed from the GitHub UI never meets one. Today's CI gate catches
both. This makes the gate an explicit end-run rather than something CI
blocks, in the same category as a force-push, and RULE-012 already
frames the obligation that way ("no fast path around it"). The coupling
being removed is causing real harm to real users now; the bypass it
opens takes deliberate effort.

Retrofit: everything except the config value is a tracked file, so an
existing clone gets it by pulling, and bootstrap sets the config on the
next session. A clone that never pulls has no hook and behaves exactly
as today, so there is no flag day and no coordination with users who
cannot be reached. The one thing a factory pull cannot fix is a pak
repo already instantiated from the old template, whose `curl` step
lives in its own `.github/workflows/`; that changes when its owner
changes it.

Note that bootstrap **skipped** existing clones rather than touching
them (the old `Exists:` path), so setting `core.hooksPath` required a
step that runs on the skip path too. That and the session-opening report
are specified in `knowledge/designs/bootstrap-update-and-report-v1.md`.

### Rollout: both gates run during the transition

The factory-side work (hook, presence-detection, parser isolation,
bootstrap) lands first and on its own. The six pak repos and the
`sdk-template` are independent repos, each needing its own PR, so their
`curl`-based CI gate step stays in place for now.

That is deliberate and safe rather than a loose end: during the
transition a first-party pak is gated twice, once by the hook against
the local registry and once by CI against the same registry over the
network. Both consult the same file and agree, so the redundancy costs
nothing and the rollout has no flag day. Deleting the CI step is a
follow-up per pak repo, tracked as its own issue.

Third parties get the benefit only once the template stops shipping the
`curl` step, which is part of that same follow-up. Nothing about the
factory-side change makes their situation worse in the meantime.

## The differentiator, since that was the open question

Not a GitHub login. The gate is a local CLI call with no auth context,
`git config user.name` is unset on plenty of runners and editable
everywhere else, and identity checks fail open when identity is absent,
which loosens exactly the side that wants hardening. It would also make
one artifact gate differently depending on who typed the command, which
is unreadable in a diff six months later.

Not a maintainer/consumer role flag either, and in the end not a
setting at all. The thing that actually differs is **which registry
file is sitting in the repo**, which the code can simply look at. A
consumer who wants their own registry makes one; everyone else keeps
today's behavior by doing nothing. Nothing to choose, nothing to get
wrong, and the answer is visible in a directory listing.

## What is already correct, so it is not re-litigated later

1. **Scope isolation works.** `gate_pak` (`defects.py:339`) filters on
   `e.affects == pak_name`, exact string equality. A defect on
   `synology` cannot gate `unifi`, and a `factory:<area>` entry cannot
   gate any pak by name.
2. **Consumers do not meet the gate.** All four call sites are release
   or publish paths: `cli.py:880` (sdk-adapter release), `cli.py:1204`
   (content release), `publish.py:813` and `:822`. Nothing gates
   install, build, validate, `build-sdk`, or clone.
3. **A defect cannot un-ship what someone already pulled.** RULE-012
   gates the next `v*` tag, `/release` and `/publish` only.

## What is actually broken: three leaks

**Leak 1: parser blast radius.** `load_registry()` (`defects.py:123`)
calls `_validate_and_emit()` per entry, which raises on the first
violation. That propagates out of `gate_pak`, `gate_item` and
`gate_all` alike, and `cmd_defect_gate` turns it into exit 1 regardless
of which pak was asked about. There is no per-entry try/except and no
scope filtering before the full-file parse completes. One sloppy edit
anywhere, including a mid-edit WIP note, breaks the gate for every
artifact until it is fixed.

**Leak 2: every pak repo depends on factory `main` at release time.**
The canonical workflow (`build-pak-on-tag.yml`, triggered on `push:
tags: v*`) runs:

    curl -fsSL ".../vcf-content-factory/main/knowledge/context/defects.md" -o defects.md
    python3 ci/defect_gate.py --pak "$NAME" --registry defects.md

Fetching live from `main` is a deliberate, documented choice and it is
the right one for Scott's paks: a defect opened at 2pm refuses the 2:05
release with no propagation step. The problem is that the same file
ships in `sdk-template`, so every pak instantiated from it inherits a
hard dependency on the tip of Scott's working branch. For a stranger's
pak that dependency can only ever return zero hits, because their pak
name cannot match any `Affects:` token Scott would write, while still
being able to fail their release.

**Leak 3: that dependency fails closed.** `curl -f` plus `set -euo
pipefail` means an HTTP error, a raw.githubusercontent outage, or
blocked runner egress fails the release before it starts. A malformed
registry exits 1 into the same trap. Three ways for a stranger's
release to break over a file with nothing to say about their pak.

## Terms

- **User defect**: evidence is a consumer's lived experience of shipped
  content. An `FB-NNN` in `feedback_queue.md` from live testing, or an
  external report like the Explore contact, graduated to `DEF-NNN` once
  confirmed. Always names a real artifact a real consumer is touching.
- **Maintainer defect**: surfaced by review, curation or authoring
  machinery against an artifact that has not shipped in that state.
  RULE-012's graduation clause already means one fixed before its build
  ships never enters the registry and never blocks anyone.

These differ in **visibility and priority, not in gating.** A shipped
defect breaks the next consumer the same way regardless of who noticed
it first. Recording it as an optional `Origin: user | maintainer` field
(defaulting to `maintainer`) costs one schema line, changes no pipeline
behavior, and lets reports surface by exception per CLAUDE.md rule 16:
an open blocking user defect means someone is stuck right now and leads
the report; an open blocking maintainer defect on an unreleased build is
routine backlog.

## Why not gitignore `defects.md`

Raised and rejected. Tracking it is what makes severity downgrades
auditable in the diff, which RULE-012 depends on explicitly ("no
waivers... auditable in the diff"), and it is what makes the raw-URL
fetch work for all six pak repos. Ignoring it would remove the audit
trail and break every first-party release gate to solve a problem that
belongs at setup time.

Clean slate by separation instead of by reset: a consumer's registry is
`defects.local.md`, a filename the factory never ships. The factory's
own `defects.md` stays tracked and unchanged.

That gets the empty start for free, since their file does not exist
until they create one, and there is nothing to reset on clone. It also
avoids a pull conflict that a reset-in-place would have caused: a
consumer who emptied the shipped `defects.md` and later pulled framework
updates would hit a merge conflict on a file they never meant to share.
A path the factory does not ship cannot conflict.

The factory's inherited `defects.md` is then just reference material in
their tree, read by nothing that gates their work.

## Rejected alternative

**Split the registry per artifact** (`defects/<pak>.md` and so on).
Physical isolation, but the `Related:` cross-linking between siblings
(DEF-002/DEF-003, DEF-005/DEF-006) gets harder to keep coherent, the
curator reads N files instead of one, the pak CI convention becomes
curl-the-right-shard, and misfiling a cross-cutting `factory:` entry
becomes a new failure mode. Per-entry isolation removes the symptom
without the ongoing cost. Revisit only if one file becomes unwieldy to
review, which at roughly 40 entries it is not.

## Blast radius if built

- `src/vcfops_packaging/defects.py`: parser rework. `tooling` then
  `framework-reviewer` per RULE-013.
- New tracked `.githooks/pre-push` in the factory, invoked via
  `core.hooksPath`. A thin dispatcher: it finds the factory above the
  clone and hands stdin to `scripts/version_line_guard.sh`, which holds
  all the policy. Refuses only on that script's RULE-014 (exit 2) and
  RULE-012 (exit 3) verdicts; every other outcome warns and allows,
  including exit 4, which the guard reserves for a defect gate that
  could not run at all (no interpreter, import failure, unreadable
  registry): no verdict was reached, so nothing is refused. Every v*
  tag on the push is checked, each against the adapter.yaml at its own
  commit rather than the working tree, and a tag deletion (all-zero
  local sha) is not a release and is never guarded.
- `build-pak-on-tag.yml` (canonical and all six copies) and
  `sdk-template`: delete the defect gate step and its `curl`, and drop
  the vendored `ci/defect_gate.py` that existed only to run it. No stub
  registry in the pak repo: the hook reads the factory registry beside
  it, so a third party's pak gates against their own
  `defects.local.md` with nothing to ship into the pak.
- `scripts/bootstrap_managed_paks.sh`: set `core.hooksPath` per clone,
  on the skip path as well as the clone path. See
  `knowledge/designs/bootstrap-update-and-report-v1.md`.
- `knowledge/context/defects.md` schema section and RULE-012: document
  the per-entry failure mode and the optional `Origin:` field.
- Doctor: on a factory clone, offer to create `defects.local.md` at
  first-run, and afterwards report by exception when content or a pak
  has been authored and no local registry exists, since that means the
  consumer's own defects gate nothing. Nothing to reset.
- Tests: a malformed entry for pak X must not block pak Y; an entry
  whose `Affects:` cannot be read must warn and block nothing; an
  absent registry must warn and pass; the hook refuses a `v*` tag push
  for a pak with an open blocking defect and allows every other push.
- No change to `feedback_queue.md`, RULE-012's gate points, or any
  existing DEF-NNN entry.
