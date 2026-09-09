# Framework review: defect-gate isolation + session bootstrap report

- **Date:** 2026-09-09
- **Branch / base:** `docs/curation-2026-08-26`, working tree vs `HEAD` (nothing committed)
- **Reviewer:** `framework-reviewer` (RULE-013 blanket review)
- **Author:** `tooling`
- **Surface reviewed:** `src/vcfops_packaging/defects.py`, `src/vcfops_common/doctor.py`,
  `tests/test_defect_gate.py`, `tests/test_common_doctor.py`
- **Read as context, not reviewed:** `scripts/`, `.githooks/`, `.claude/settings.json`,
  `knowledge/` (orchestrator-owned half of the same change)
- **Designs of record:** `knowledge/designs/defect-isolation-v1.md`,
  `knowledge/designs/bootstrap-update-and-report-v1.md`

## Verdict: CHANGES REQUESTED

3 BLOCKING / 2 WARNING / 3 NIT.

## Checks re-run independently

| Check | Result |
|---|---|
| Seven-package validate chain (`vcfops_supermetrics` … `vcfops_managementpacks`) | **pass**, rc=0 |
| `pytest tests/ -q` (default, `-m "not slow"`) | **1137 passed, 4 skipped**, 128 deselected |
| `pytest tests/ -n auto --dist=loadgroup --override-ini="addopts=" -m ""` (CI mode) | **1265 passed, 4 skipped**, 219s |
| `scripts/path_reference_audit.sh` | **clear** (3 documented RULE-015 standing-exception warnings, expected) |
| Render regression / `pak-compare` | n/a, no renderer, builder or template touched |
| Dist-zip staleness (CLAUDE.md "After tooling changes") / `CURRENT_TEMPLATE_VERSION` | **not triggered**: no `src/vcfops_packaging/templates/`, `builder.py`, `discrete_builder.py`, `release_builder.py` or `src/vcfops_dashboards/render.py` in the diff. No rebuild, no version bump required. |

## Author claims: independently confirmed

All five claims were exercised against the real code, not read.

1. **Per-entry isolation.** Fixture registry with a malformed `DEF-001 (Affects: pakX)`,
   a valid blocking `DEF-002 (Affects: pakZ)` and a malformed prose-scoped `DEF-003`:
   `--pak pakY` exits 0, `--pak pakX` exits 2 naming only DEF-001, `--pak pakZ` exits 2
   naming only DEF-002. A malformed entry for X genuinely cannot block Y. **Confirmed.**
2. **A synthetic blocker cannot be mistaken for a real registered defect.** It renders as
   `DEF-001  malformed registry entry: <reason>  (first seen unknown (entry is malformed),
   source <registry> near line 3)`. Title, first-seen and source all say "malformed", and
   the source names file+line. Every surface that prints a defect uses `format_defect_line`,
   so this holds on the CLI, release and publish paths. **Confirmed.**
3. **Exit-code loosenings.** Malformed entry with readable scope: exit 2 for that scope only.
   Absent registry: exit 0 with `WARNING: no defect registry at <path>, the RULE-012 gate has
   nothing to check and vacuously passes` on stderr. Both **confirmed**, both sanctioned by
   design decision 4. `scripts/version_line_guard.sh:210` treats *any* non-zero from the gate
   as a RULE-012 refusal, so the surviving exit 1 (unreadable file) still fails closed at the
   hook. **No silent pass found on the CLI or hook paths.** The publish path is a different
   story: see BLOCKING-1.
4. **Registry resolution.** `resolve_registry_path()` reads `REGISTRY_PATH` at call time
   (verified by monkeypatching the module attribute after import and observing the new
   default take effect), prefers `defects.local.md` when present, and returns an explicit
   argument verbatim (an explicit `--registry defects.md` did **not** pick up a sibling
   `defects.local.md`). Selection is replacement, not merge: entries only in `defects.md`
   stopped gating once a local file existed. **Confirmed, matches design decision 1.**
5. **`checked=` parsing.** `checked=no` renders "I could NOT check the … for updates this
   session, so they are not known to be current"; an unrecognized value renders "update
   freshness is unknown"; `yes` is silent. `checked=no` can never render as "current".
   **Confirmed for a line that is present.** The uncovered case is a record that was never
   written at all: see BLOCKING-3.

## BLOCKING

### B1. `publish._gate_publish` ignores `defects.local.md`; the reported user harm survives on `/publish`

`src/vcfops_packaging/publish.py:789` builds the registry path itself:

```python
registry_path = factory_repo / "knowledge" / "context" / "defects.md"
```

and passes it explicitly to `gate_pak` / `gate_item` (`:813`, `:822`). Under the new and
correct rule that "an explicit `registry_path` argument always wins" (`defects.py`
`resolve_registry_path`), that explicit path defeats presence-based selection. `publish.py`
was not edited in this diff, so the new behaviour never reached it.

Proven, not inferred. With a fixture factory root carrying an upstream `defects.md` holding
an open blocking `DEF-002 Affects: fixturepak`, plus a consumer's own empty
`defects.local.md`:

```
RESULT: publish REFUSED despite defects.local.md -> RULE-012: 1 open blocking defect(s) prevent publish:
```

Every other path (`defect-gate` CLI, `release`, the `.githooks/pre-push` hook via
`version_line_guard.sh`) honours the local registry, because each calls the gates with no
path. `/publish` alone does not.

**Authority.** `knowledge/rules/release-gate-defects.md` as amended *in this same working
tree*: "Which registry. Selection is by file presence, not configuration: a `defects.local.md`
sibling … wins when it exists" — stated unconditionally, under a rule whose clause 2 is
"`/release` and `/publish`". Also `knowledge/designs/defect-isolation-v1.md` decision 1
("registry selection is by file presence") and decision 5 ("`/publish` and a `v*` tag get the
same strictness"), and the design's closing statement that a consumer's inherited `defects.md`
is "just reference material in their tree, read by nothing that gates their work". It is read
by `/publish`.

This is the same shape as escape `00d3382`: a behaviour proven on one output path and never
proven on the other, where the unexercised path is the one that ships. There is no test in
`tests/test_defect_gate.py::TestGatePublish` that puts a `defects.local.md` in the fixture.

**Smallest correct fix.** In `_gate_publish`, resolve through the module's one resolver:
`registry_path = preferred_registry(factory_repo / "knowledge" / "context" / "defects.md")`,
and keep the existing absent-file warn-and-return after resolution (so a checkout with
neither file still warns and passes). Add a `TestGatePublish` case with a local registry that
overrides an upstream blocker.

### B2. The `defects.local.md` by-exception line is not by exception: its gate predicate is always true

`doctor.py` `local_registry_missing()` suppresses the line on "a checkout with nothing
authored", via `has_authored_content()`, which returns True when `content/` is a non-empty
directory. `content/` ships tracked and populated: `git ls-tree -r HEAD -- content` returns
**102 files** across nine type directories in a clean clone.

So `has_authored_content()` is `True` on every checkout from the first second, the docstring's
stated suppression ("Silent on a checkout with nothing authored … telling them about a registry
would be noise") can never fire, and `LOCAL_REGISTRY_LINE` prints on **every session for every
user** until they create the file. Observed live on this checkout:

```
You are not using a defects.local.md, so upstream defects may block you. Create ...
```

The orchestrator flagged this as noise for the maintainer. It is worse than that: it is
unconditional for everyone, including a brand-new user who has authored nothing, which is
precisely the case the code claims to exclude. Same for the `defects-local` checklist item,
which is `pending` for 100% of first runs.

**Authority.** CLAUDE.md rule 16 (reports surface by exception; reading time is the scarcest
resource) and `knowledge/designs/bootstrap-update-and-report-v1.md` recommendation 5 ("A
session where everything was current and nothing needed attention is one line"). The function's
own docstring is the second authority: the code does not do what it documents.

**Recommended fix, and the answer to the open question.** There is a clean suppression that
needs no configuration and no new detection heuristic, and it does not require telling a
maintainer from a consumer at all (which the design explicitly refuses to do):

> **Move the line from the standing session report to the gate's own refusal message.**
> Drop `LOCAL_REGISTRY_LINE` from `run_doctor`'s attention list. Keep the `defects-local`
> item in the first-run checklist, where it is an offer, not a nag. Then, in the gate
> refusal path, when a refusal is produced and no `defects.local.md` exists, append one
> sentence: "this refusal came from the factory's own `defects.md`; create
> `knowledge/context/defects.local.md` to keep your own registry."

Why this is the clean one: the premise "upstream defects may block you" is only *information*
at the moment a defect actually blocks you. It fires zero times for the maintainer — not
because anything detects that he is the maintainer, but because his refusals come from his own
registry and there is nothing to tell him. It fires exactly once, at the moment it is
actionable, for the consumer the design was written for. No stamp file, no config key, no
identity check, no ownership heuristic. It costs one conditional in the refusal formatter.

Second-best if that is too large for this change: gate the standing line on a once-per-checkout
stamp (the `.bootstrap-status.throttle` / `curation/.last-run` pattern already in the tree).
Weaker, because a user who ignores it once never sees it again, and it adds state.

Whatever the fix, `has_authored_content()` should not survive in its current form: as written
it is a predicate that reads as discriminating and cannot discriminate, which is worse than no
predicate at all.

### B3. A bootstrap run that never happened is replayed in the present tense as if it did

`bootstrap_report_lines()` composes "here's your bootstrap report for this session:" purely
from the key/value fields of `.bootstrap-status`. It never reads `TIMESTAMP_KEY`, which
`read_bootstrap_status` puts right beside them.

Neither bootstrap script has an `EXIT`/`TERM` trap, and `write_status` runs only at normal exit
paths. The SessionStart hook runs each under `timeout 90`. So a script killed by the timeout,
or aborted by `set -euo pipefail` mid-sweep, writes **no** line, the previous run's line
survives, and the next doctor replays it verbatim as this session's work. Demonstrated:

```
>>> bootstrap_report_lines({'bootstrap_references':
...     {'updated':'4','checked':'yes','__ts__':'2026-09-01T00:00:00Z'}})
['I updated 4 reference repos.']
```

An eight-day-old record renders as "I updated 4 reference repos" under a "this session"
header. Within the first 24 hours there is no counter-signal at all; past 24 hours the separate
`STALE_AFTER_HOURS` attention line fires, but the false present-tense line still prints
alongside it, and the true statement is buried under the false one.

**Authority.** `knowledge/designs/bootstrap-update-and-report-v1.md`, "Failure modes to design
against": *"**Silent partial run.** `timeout 60 … || true` means an overrun is invisible. The
report must distinguish 'checked and current' from 'not checked', or a user reads staleness as
freshness."* This is that failure mode, unmitigated, in the function written to prevent it. It
is also the reports-green-while-broken class named in this reviewer's own dimension 9.

**Smallest correct fix (doctor half, `tooling`-owned).** Pass the record's age into
`bootstrap_report_lines` and, when the record predates this doctor run by more than a small
window, either suppress the present-tense "I did X" lines or re-voice them with the stamp
("as of 2026-09-01, …; this session's run did not complete"). The `__ts__` value is already
in the dict; the function just has to look at it.

**Cross-half note (orchestrator-owned, out of my write scope but part of the shared
contract).** The complementary half is an `EXIT` trap in each bootstrap script that writes
`checked=no` if the normal `write_status` never ran. With both halves, a killed run reports
"I could NOT check …", which is the honest line the design asks for. With neither, a killed run
is indistinguishable from a successful one for up to 24 hours.

## WARNING

### W1. `checked=throttled` speaks every session, and it is the normal state six days in seven

`bootstrap_report_lines` emits, for `checked=throttled`:

```
I didn't check the pak repos for updates this session (already checked today);
run the bootstrap script with --update to force a check.
```

The daily throttle (`THROTTLE_SECONDS=86400`) means this is true on essentially every session
that is not the day's first. Observed live on this checkout, and it is counted in the doctor's
"15 line(s) need attention" header. Nothing needs the user: the throttle working as designed
is not a delta. `tests/test_common_doctor.py::test_checked_throttled_says_so` pins the current
behaviour, so this is a deliberate call I am disagreeing with, not an oversight.

**Authority.** CLAUDE.md rule 16 and design recommendation 5. `checked=no` (could not check)
is genuinely by-exception and must keep speaking. `checked=throttled` (deliberately not
checked, per policy the user did not set and cannot act on usefully) should be silent, exactly
like `checked=yes`.

**Fix.** Treat `throttled` as silent; keep `no` and unrecognized values loud. Invert the test
to assert silence. If the fact is wanted at all, it belongs in the once-a-day session where
the sweep actually runs, not the six where it does not.

### W2. Parse warnings are re-emitted once per gate call

`_read_registry_for_gate` re-parses and re-warns on every invocation. `_gate_publish` calls a
gate once per headline artifact, so a publish set of N releases with a malformed registry emits
N copies of every warning on stderr. Loud is right; N-times-loud trains people to skip it.

**Fix.** Warn once per process per resolved registry path (a module-level `set` of already-warned
paths is enough), or hoist the read out of the per-artifact loop in `_gate_publish`.

## NIT

### N1. Stale `Raises:` docstrings on the gate helpers

`gate_pak` (`defects.py:~594`), `gate_item` and `gate_all` still document
`FileNotFoundError: if the registry file is missing` and `DefectRegistryError: if the registry
is malformed`. Neither is reachable through `_read_registry_for_gate` any more: absence warns
and passes, and a malformed entry is isolated. The module docstring was updated correctly; the
three function docstrings were not. The corresponding `except FileNotFoundError` in
`cli.py:653` and `cli.py:894` are now dead branches (harmless, but they read as live contract).

### N2. A >120-character `Affects:` token warns that it blocks a scope it cannot match

`_readable_affects` clips its return through `_clip(..., 120)`. A malformed entry whose
`Affects:` is a single token longer than 120 characters produces a synthetic entry whose
`affects` is the truncated string plus `"..."`, which can never equal a real pak name or
`<type>/<slug>` token. The WARNING claims "is being treated as an open blocking defect against
'<truncated>...'" while it in fact blocks nothing. Pathological, but the message asserts
something false. Either do not clip the value used for matching (clip only the echoed copy),
or classify an over-length token as unreadable so the honest "blocks nothing" warning is used.

### N3. Two id-less malformed entries collide on `DEF-???`

`_synthetic_entry` falls back to `err.entry_id or "DEF-???"`. Two entries whose ids are
unusable both become `DEF-???`; `publish.py:833`'s `sorted({e.id for _, e in all_blockers})`
then dedupes them to a single id in the "Defect ids:" line, though both still appear as
separate detail lines with distinct `near line N` sources. Cosmetic; the line numbers carry the
real identity. Faint echo of escape `6c59f6b` (context-free key derivation), which is why it is
recorded rather than ignored.

## Judgment calls I was asked to rule on

**`defects-local` checklist status `pending`, not `fail`: agree.** `compose_greeting` names only
`fail`/`unknown` items, so `fail` would make "a local defect registry (defects.local.md)" one of
the first things a brand-new user hears is missing from their machine, alongside Python and
credentials. It is not a prerequisite for anything; nothing fails without it. `pending` matches
how `recheck` already uses that status, and it is the design's own word: *"offer to create
`defects.local.md` at first-run"* (`defect-isolation-v1.md`). Correct call. (It does not rescue
B2: the item is `pending` for 100% of first runs, which is a separate problem from its status
value.)

**A prose `Affects:` treated as unreadable: agree.** The registry contract is exactly one token;
`_readable_affects` implements exactly that, and the design's test list is explicit: *"an entry
whose `Affects:` cannot be read must warn and block nothing."* Guessing a scope out of prose
would be the parser inventing a gate target, which is the RULE-001/002 no-fabrication line.
Worth recording the accepted cost, and this diff does record it in RULE-012: the failure
direction is **open**, so a real defect with a sloppy scope line gates nothing and a stderr
WARNING is the only backstop. That is the right trade here only because the alternative (the
old whole-file raise) demonstrably blocked strangers' releases. It should stay named in the
rule, as it now is.

## Regression-anchor checks

- **`00d3382` (pak-local default leaking onto the global path).** The registry-selection
  default is applied in `resolve_registry_path` (module default) and in the standalone
  `__main__` block, both through the single `preferred_registry` helper. It is **not** applied
  on the publish path, which hand-builds its own path: B1. Same shape as the anchor, opposite
  direction (a global rule failing to reach one path rather than a local rule leaking to all).
- **`6c59f6b` (context-free key derivation collision).** Synthetic entry ids derive from the
  malformed entry's own id where one is readable, so real ids do not collide. The only
  collision is the `DEF-???` fallback: N3, cosmetic.
- **Silent capability change / downgrade.** Three loosenings ship here (malformed entry no
  longer fails the file; absent registry passes; explicit path bypasses local selection). The
  first two are loud (stderr WARNING on every invocation) and documented in RULE-012 and
  `defects.md`. The third is silent and undocumented: B1.

## Test coverage assessment

Good, and better than the surface deserved before this change. `tests/test_defect_gate.py`
adds `TestPerEntryFaultIsolation` (x-does-not-block-y, readable scope blocks that scope,
unreadable scope blocks nothing and is reported, prose scope is not readable, `gate_all`
reports every error), `TestRegistryResolution` (local wins, falls back, explicit beats both),
`TestAbsentRegistryWarnsAndPasses`, and CLI exit-code cases for each. `tests/test_common_doctor.py`
covers each repo state, `checked=no`, `checked=throttled`, `checked=yes` silence, garbage-value
degradation, and the local-registry line in all three presence combinations.

Two gaps, both already stated above as findings rather than separate coverage findings:
`TestGatePublish` has no `defects.local.md` fixture (B1), and there is no test for a status
record older than the current run (B3). `test_checked_throttled_says_so` pins behaviour I am
asking to invert (W1).

## If shipped as-is

A third party who followed the design's instructions and created `defects.local.md` still has
their `/publish` refused by defects in Scott's registry that name artifacts they have never
touched, which is the exact complaint the whole change exists to fix, now harder to diagnose
because every other command they try honours their local file. Separately, every user of the
framework, maintainer and consumer alike, gets two or three lines of unactionable session-open
noise forever, in a report whose whole premise is that it surfaces only exceptions. And a
session whose bootstrap was killed by the 90-second timeout tells the user it updated repos it
never touched.

---

# Round 2 (same day, same working tree)

- **Scope grew:** `src/vcfops_packaging/publish.py` and `src/vcfops_packaging/cli.py`
  are now in the diff and were not in round 1. Both given a first-pass review below,
  not a delta check.
- **Files under review:** `defects.py`, `doctor.py`, `publish.py`, `cli.py`,
  `tests/test_defect_gate.py`, `tests/test_common_doctor.py` (+1772/-120).

## Verdict: APPROVE

0 BLOCKING / 2 WARNING / 7 NIT. All three round-1 BLOCKING findings are fixed and
independently re-verified with the same fixtures that proved them. Both WARNINGs below
are non-regressions (one pre-existing parser shape, one in the orchestrator-owned half),
so neither blocks the PR; both should be filed rather than silently carried.

## Checks re-run

| Check | Result |
|---|---|
| Seven-package validate chain | **pass**, rc=0 |
| `pytest tests/ -q` | **1155 passed, 4 skipped** (was 1137) |
| CI mode `-n auto --dist=loadgroup --override-ini="addopts=" -m ""` | **1283 passed, 4 skipped**, 184s (was 1265) |
| `scripts/path_reference_audit.sh` | **clear**, standing exceptions only |
| Dist-zip staleness / `CURRENT_TEMPLATE_VERSION` | still not triggered; no templates, builder or renderer in the diff |

18 net new tests, none deselected in either mode.

## Round-1 findings: verified fixed

**B1 (publish ignored `defects.local.md`) — FIXED.** Re-ran my own round-1 fixture, the one
that produced "REFUSED despite defects.local.md", plus the two new cases:

```
A. local registry empty, upstream blocker  : PASSED
B. local registry HAS its own blocker      : REFUSED -> DEF-100, "See defects.local.md"
C. no local registry, upstream blocker     : REFUSED -> DEF-002, "See defects.md" + hint
```

`_gate_publish` now resolves through `preferred_registry(...)` and the absent-file
warn-and-return sits after resolution, so a checkout with neither file still warns and
passes. Case B confirms the hint is correctly silent when the refusal came from the
caller's own registry. `/publish` now agrees with the CLI, release and pre-push-hook
paths, which is design decision 5.

**B2 (standing `defects.local.md` line, inert predicate) — FIXED.** `LOCAL_REGISTRY_LINE`,
`local_registry_missing` and `has_authored_content` are gone; `grep -rn` across `src/` and
`tests/` finds no residue. The sentence moved to `defects.local_registry_hint()` and is
appended at the moment of refusal. Live on this checkout the doctor no longer says it, and
the docstring left on `local_registry_path` records *why* the old predicate could not work
("content/ ships tracked and populated and is therefore non-empty on every clone from the
first second"), which is the right place for that lesson.

Refusal-path coverage audited by hand, all six gate refusals carry it:
`cmd_defect_gate` `--all` / `--pak` / `<type> <name>` (stdout, matching where those
refusals print), `cmd_release` sdk-adapter and content (stderr, likewise), and
`_gate_publish` (inside the `PublishError` text). The one refusal path *without* it is the
standalone `defects.py __main__` block, which I judge correct rather than missed: that path
exists for a curled `defects.py` + `defects.md` pair with no `knowledge/context/` around
it, so the hint's hard-coded `knowledge/context/...` paths would be wrong there, and the
design's rollout deletes that CI usage anyway. Worth one comment saying so (NIT-4).

**B3 (stale record replayed in present tense) — FIXED.** My 8-day repro and the full
boundary sweep, all with an injected `now`:

```
8d old, updated=4  -> ['bootstrap_references did not record a run this session (its last
                       record is from 2026-09-01...), so the reference repos are NOT known
                       to be current; the script may have been killed before it could report.']
2h old             -> same past-tense line
0.99h old          -> ['I updated 4 reference repos.']      (current)
1.01h old          -> past-tense line                        (boundary behaves)
unparseable stamp  -> past-tense line
future stamp       -> past-tense line
stale, nothing to say -> []                                  (no double-reporting)
```

The gate reads `TIMESTAMP_KEY`, and unparseable and future-dated stamps both answer False,
which is the conservative direction. Suppressing the past-tense line for a stale record with
nothing to say is right: `STALE_AFTER_HOURS` already covers a script that has not run in a
day, and saying it twice is not by exception.

**Is the 1.0-hour boundary a new trap?** Not a trap, but looser than it needs to be: see
NIT-1. It leaves a window of up to an hour in which a *previous* session's record is voiced
as this session's. That window is only reachable if the current session's bootstrap died
without writing anything at all, which now requires SIGKILL or power loss rather than the
ordinary `timeout` TERM.

**W1 (`throttled` noise) — FIXED.** `yes` and `throttled` are both silent; `no` and
unrecognized values still speak. Verified live: the doctor on this checkout went from
15 attention lines to 11, and the two remaining bootstrap records (both `checked=throttled`)
produce nothing. The only lines left are the genuine ahead-of-upstream delta.

**W2 (repeated warnings) — FIXED.** Five consecutive `gate_pak` calls against a malformed
registry emit exactly 1 warning line; `reset_warning_state()` restores it to 1 again. Note
the key is recorded before the existence check, so within one long-lived process a registry
that is absent on the first call and malformed later would not warn a second time. Irrelevant
for CLI-shaped processes; recorded as NIT-6 only.

**N1 — FIXED.** All three gate docstrings now say `DefectRegistryError` only for a file that
exists but cannot be read, and state that a missing registry warns and returns `[]`.

**N2 — FIXED, and verified in both directions.** `_readable_affects` returns the token
unclipped and clipping moved to the echo. A 204-character `Affects:` token now both
*matches its own scope* (`gate_pak(LONG) -> ['DEF-010']`, previously `[]`) and *stays out of
the warning* (302-char message, full token absent). That is the exactly-right split: match on
truth, echo on a leash.

**N3 — FIXED (defensively).** The fallback id is now `DEF-???(line N)`, so a dedupe on id
cannot collapse two entries. In practice the branch is unreachable: `_SECTION_RE` is
`^#{1,4}\s+(DEF-\d+)\s*$`, so `entry_id` is always a well-formed id. Harmless belt-and-braces.

## WARNING

### W3 (pre-existing, not a regression). A heading whose id is not `DEF-\d+` silently repoints a good entry

Not introduced by this diff, but it is the one malformed-entry shape the diff's new,
now-documented contract does not cover, and the documentation was strengthened in this same
working tree. `_SECTION_RE` only matches `DEF-` followed by digits. A heading with a typo,
a suffix, or trailing text falls through to the *continuation-line* branch, so the whole
following entry's field lines overwrite the previous entry's fields. Demonstrated:

```
### DEF-001  (Affects: pakA)  ... good entry
### DEF-1O2  (letter O)       (Affects: pakB)

entries: [('DEF-001', 'pakB')]      <- DEF-001 now gates pakB, not pakA
errors:  []                          <- no ParseError
gate pakB: ['DEF-001']
DEF-001 summary now: 'never gates anything.'
```

A real open blocking defect stops blocking the artifact it names, a second one never exists,
and the registry parses clean: no error, no warning, no synthetic blocker. That is
fail-open, and it contradicts what `knowledge/rules/release-gate-defects.md` and
`knowledge/context/defects.md` now assert in this diff ("A malformed entry blocks only
itself … and both are reported").

**Why WARNING and not BLOCKING.** It predates the change and is not a regression, and the
first-party registry has a real backstop: `TestRealRegistryStructural::test_ids_unique_and_sequential`
runs against `knowledge/context/defects.md` and fails on any gap in the sequence, which a
heading typo produces. That backstop does **not** exist for a consumer's `defects.local.md`,
which is the registry this whole change was written to make trustworthy.

**Smallest correct fix.** One branch: a `#{1,4}` heading whose text starts with `DEF` but
does not match the id shape becomes a `ParseError` carrying that entry's `_readable_affects`,
which puts it straight into the existing scoped/unscoped machinery. If not taken now, file it
rather than carry it, because the docs in this diff now claim the property.

### W4 (orchestrator-owned half). `on_abort` records and returns; a real SIGTERM is absorbed and the interrupted record is overwritten

You asked me to confirm the two halves agree and that B3 does not depend on the trap.
**B3 does not depend on it** (the doctor's freshness gate is independent, verified above).
**The trap does not do what it is believed to do under a delivered signal**, which is a
different thing from firing the handler directly.

`timeout -s TERM 0.5 scripts/bootstrap_references.sh --update` returned rc=124 **5.0 seconds
later**, with the *normal* end-of-run record in place (`failures=- skipped=15 checked=no`),
not `failures=interrupted`. Mechanism confirmed with a minimal harness of the same shape:

```
start
Terminated
WROTE: interrupted            <- trap fires
  probe 1 failed (treated as 'not checked')
loop finished normally        <- handler RETURNED, script continued
WROTE: normal-completion      <- interrupted record overwritten
rc=124
```

The handler writes and returns rather than exiting. In these scripts the fetch and pull
failures are deliberately guarded (`if ! repo_fetch ...`), so the signal-induced failure does
not propagate and `set -e` never fires; the sweep simply carries on to the end. Two
consequences: the `failures=interrupted checked=no` record the design wants is not reliably
produced by the very case it was written for, and `timeout 90` is not a real budget, since
the script can run past it into the doctor's window and rewrite `.bootstrap-status` after the
doctor has read it.

Not blocking, and the end state observed was still honest (`checked=no`, because the fetches
failed). The fix is one line in the orchestrator's half: `exit 143` at the end of `on_abort`
after the write.

*(`.bootstrap-status` was restored to its pre-review content; it is untracked, so no repo
state changed.)*

## NIT

1. **`REPORT_FRESH_WITHIN_HOURS = 1.0` is 12x looser than the maximum it needs to be.** The
   SessionStart hook's outer budget is 300s and the doctor runs inside it, so a record written
   by this session's hook is at most five minutes old by construction. Bounding the constant by
   the hook budget rather than an hour would shrink the "previous session voiced as this one"
   window from 60 minutes to 5, at no cost. The comment's "generous headroom for a slow sweep
   on a slow link" is true but the sweep cannot outlive the hook that spawned it.
2. **`local_registry_hint()` is four sentences.** It lands in a refusal the reader is already
   parsing under pressure. The first sentence and the create-this-file clause carry it; the
   "the factory never ships that filename, so a git pull cannot conflict with it" rationale is
   documentation, not something the refused user needs at that moment.
3. **`publish.py` "See {registry_path.name}"** drops the directory: the message now reads
   "See defects.md" / "See defects.local.md" where it used to name the path. In the
   `defects.local.md` case no full path appears anywhere in the refusal.
4. **The standalone `__main__` refusal carries no hint** and no comment saying that is
   deliberate. One line of comment stops a future reader from "fixing" it.
5. **`publish.py` still says "defect registry malformed"** in the `DefectRegistryError`
   handler, where `cli.py` was correctly updated to "unreadable". Same condition, two words.
6. **Warn-once keys before the existence check**, so an absent-then-malformed registry inside
   one process warns only once. Not reachable from any current entrypoint.
7. **Stray double blank line** in `run_doctor` where `LOCAL_REGISTRY_LINE` was removed.

## The two judgment calls you asked about

### 1. `write_fresh_bootstrap_status` moved from a 1-hour-old stamp to now: legitimate fixture correction

Proven inert rather than argued. I copied the test file, reverted the helper to
`ts(hours_ago=1)`, and ran it against the new code: **115 passed**. Not one assertion depends
on the change.

That is the test for "weakened to fit the code": a weakened fixture is one whose old value
would now fail. This one would not, because the records the helper writes
(`cloned=1 updated=0 failed=0 failures=-`) have no voiceable content, so the freshness gate
never reaches them either way. What the change actually does is make a helper named
`write_fresh_bootstrap_status` write something fresh, matching what the hook really produces
(both scripts and then the doctor run in one sequential command, so the record is seconds
old), and move a fixture off an exact boundary value, which is a flakiness hazard in either
direction. Correct call.

### 2. The "if these defects are not yours" clause: it holds, and it is not just nicer words

The clause is doing real work, and the reason is frequency, not phrasing. The round-1 problem
was a line that fired on **every session for every user**, unconditionally and with nothing to
act on. The hint fires **only on a refusal**, which is already a stop-and-read moment, and it
is genuinely silent for anyone who has a `defects.local.md` (verified: case B above prints no
hint). On your checkout it appears only when you actually have an open blocking defect on
something you are releasing, which is rare and is a moment you are reading the output anyway.

It is fair to say it cannot tell you apart, and it does not try. But that is the design's
deliberate choice, argued at length in "The differentiator, since that was the open question":
not a GitHub login, not a role flag, not a setting. Once you refuse identity, a conditional
sentence is the honest form of the message, and the alternative (an identity check that fails
open when identity is absent) is worse for exactly the reason the design gives. So: it holds.
The residual cost is real but bounded, and the fix for it is brevity (NIT-2), not detection.

## First-pass review of the two newly-touched files

**`publish.py`** (+28/-11). The only behavioural change is the registry resolution and the
hint; the accumulate-then-raise structure, the sdk-adapter-vs-content token derivation, the
dry-run-also-refuses property and the documented no-fallback-to-package-copy rule are all
untouched. Resolution happens before the existence check, so the "test fixture with no
`knowledge/context/`" case still warns and passes, which is what keeps fixtures from coupling
to the live registry. Comments carry the reasoning and cite the design. Two NITs (3, 5), no
findings.

**`cli.py`** (+27/-8). Purely additive at the three `cmd_defect_gate` refusals and the two
`cmd_release` refusals, each guarded by `if _hint:` so an empty hint prints nothing rather
than a blank line. Stream choice matches each surrounding refusal (stdout in
`cmd_defect_gate`, stderr in `cmd_release`), so nothing changes for a caller parsing one
stream. Exit codes untouched: 0/1/2 mean what they meant. The two now-unreachable
`except FileNotFoundError` branches were kept and correctly re-labelled as backstops rather
than deleted, which is the right call for a CLI boundary. `version_line_guard.sh` shells out
to `defect-gate --pak` and still maps any non-zero to a RULE-012 refusal, so the hook path
stays fail-closed. No findings.

## If shipped as-is

An operator sees a defect gate that refuses exactly the artifact a defect names and nothing
else, on all six refusal paths including `/publish`; a consumer who creates
`defects.local.md` is gated by their own registry everywhere and told about the option only
when the factory's registry is what refused them; and a session that could not check its
clones says so instead of replaying last week's work. The two carried WARNINGs are a
pre-existing parser shape that can silently repoint a defect after a heading typo (with a
CI backstop for the first-party registry but not for a consumer's), and an abort trap in the
orchestrator's half that does not survive a real SIGTERM, neither of which the framework
depends on for the properties this change was built to guarantee.
