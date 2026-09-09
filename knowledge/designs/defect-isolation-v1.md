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

Four decisions, in dependency order.

1. **Gate against the registry that is authoritative for the artifact
   being released.** For Scott's six paks that is the factory registry,
   fetched over the network, because that is where he writes defects and
   the pak repos have no registry of their own. For anyone else it is a
   `defects.md` in their own repo, because they cannot write to his.
   One rule, two locations, expressed as a registry location in the
   workflow file.
2. **A third party's registry starts empty**, reset at first-run, not
   inherited. `defects.md` stays tracked (see "Why not gitignore").
3. **Per-entry fault isolation in the parser** so one malformed entry
   stops gating only the artifact it names, instead of every artifact
   everywhere.
4. **A missing or unreachable registry warns, it does not refuse.**
   This already is the behavior on the `publish` path; the pak CI is
   the outlier.

Together these remove the reported failure without changing what gates
a first-party release. Scott's own strictness is unchanged or higher;
only the stranger's coupling to his working branch goes away.

## The differentiator, since that was the open question

Not a GitHub login. The gate is a local CLI call with no auth context,
`git config user.name` is unset on plenty of runners and editable
everywhere else, and identity checks fail open when identity is absent,
which loosens exactly the side that wants hardening. It would also make
one artifact gate differently depending on who typed the command, which
is unreadable in a diff six months later.

Not a maintainer/consumer role flag either. The thing that actually
differs is **where this pak's defect registry lives**, which is a
property of the repo, set once at instantiation, and dull enough to be
obviously correct when read. Strictness follows from it rather than
being configured separately.

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

Clean slate instead: the file stays tracked, and first-run resets a
fresh clone's registry to an empty stub. The doctor already emits a
concierge checklist for unconfigured clones (`doctor.py:988`,
`is_first_run`), so this is one more checklist item rather than new
machinery, and it ships working rather than asking the user to create a
file by hand.

Known friction, not yet resolved: a consumer who resets their registry
and later pulls from upstream gets a conflict on `defects.md`. Worth
deciding whether a consumer's registry should live at a path the
factory does not ship at all.

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

- `src/vcfops_packaging/defects.py`: parser rework, plus the standalone
  mirror block vendored into each pak repo as `ci/defect_gate.py`.
  `tooling` then `framework-reviewer` per RULE-013.
- The canonical `build-pak-on-tag.yml` and `sdk-template`: registry
  location becomes a setting; fetch failure warns instead of refusing
  in the template's default.
- Six pak repos: re-vendor `ci/defect_gate.py` and the workflow. The
  existing convention already propagates both together.
- `knowledge/context/defects.md` schema section and RULE-012: document
  the per-entry failure mode and the optional `Origin:` field.
- Doctor first-run checklist: registry reset for a fresh clone.
- Tests: a malformed entry for pak X must not block pak Y; an entry
  whose `Affects:` cannot be read must warn and block nothing; an
  absent registry must warn and pass.
- No change to `feedback_queue.md`, RULE-012's gate points, or any
  existing DEF-NNN entry.

## Open questions for Scott

1. Should `/publish` inherit the same upstream-strict behavior as a
   `v*` tag, or is the tag the only place strictness matters?
2. Should a consumer's registry live at a path the factory does not
   ship, to avoid the pull conflict noted above?
