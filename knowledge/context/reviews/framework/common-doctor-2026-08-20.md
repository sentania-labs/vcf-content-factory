# Framework review: vcfops_common doctor (bootstrap-v2 Phase 1/1b)

- **Date:** 2026-08-20
- **Reviewer:** framework-reviewer
- **Change under review:** uncommitted working-tree files
  `src/vcfops_common/doctor.py`, `src/vcfops_common/__main__.py`,
  `tests/test_common_doctor.py` (branch `pr4-bootstrap-phase1`)
- **Design of record:** `knowledge/designs/bootstrap-v2.md` (Phase 1, Phase 1b,
  Windows portability)
- **Verdict:** CHANGES REQUESTED (1 BLOCKING, 2 WARNING, 3 NIT)

## Checks re-run (independent, not taken on faith)

| Check | Result |
|---|---|
| Full pytest suite | 679 passed, 4 skipped (includes all 23 new doctor tests; count matches claim) |
| Full validate chain (7 packages) | all green |
| Foreign-cwd invocation (`python -m vcfops_common doctor` from scratchpad) | exit 0, correct root via `__file__` anchoring; issue #76 class clear |
| Render regression / pak-compare | n/a (no renderer/builder/template files touched) |
| Stale-zip trigger (dimension 9) | n/a confirmed: none of `src/vcfops_packaging/templates/`, `builder.py`, `discrete_builder.py`, `release_builder.py`, `src/vcfops_dashboards/render.py` touched |
| Corrupt-input probes (my own harness) | **5 crash paths found, see BLOCKING-1** |

Claims verified true: pure stdlib (yaml/requests/jmespath only
`find_spec`-checked); no bash, no `shell=True`, git via list-args
subprocess with `timeout=` (Windows-safe); fetch 15s / plumbing 10s
timeouts, `OSError`/`TimeoutExpired` caught in the runner; fail-open
offline with an honest `(offline?)` annotation on the green line, not a
lie; ff-pull offer only on a clean tree (`--untracked-files=no`
porcelain), never pulls; PR nudge only for core commits, never pushes;
behind summary grouped by area with subjects (ELI5); jmespath absence
alone does not trigger first-run; `.bootstrap-status` last-line-per-
script parsing, absent file silent; the RULE-008 test is real and
meaningful (the fake secret is present in the `.env` the doctor reads,
and asserted absent from the full captured output; no output path
constructs strings from `.env` values, only from key names).

## BLOCKING

### B-1. "Always exits 0" contract is violated on five plausible corrupt-input paths

Authority: the module's own stated contract (`doctor.py:10` "Always
exits 0 — the output is informational for the hook"), design
`knowledge/designs/bootstrap-v2.md` §Phase 1 (fail-open, report-by-exception),
and the silent-downgrade dimension (a hook that stack-traces every
session is worse than a delta line).

Probes (run against a synthetic configured root through the real
`run_doctor`):

| Input | Result |
|---|---|
| non-UTF8 `.env` (e.g. Notepad saves UTF-16 on Windows — directly on the design's Windows path) | `UnicodeDecodeError` from `_env_keys` (`doctor.py:318` `read_text()`) |
| unreadable `.env` (chmod 000) | `PermissionError`, same line |
| non-UTF8 `.bootstrap-status` | `UnicodeDecodeError` from `read_bootstrap_status` (`doctor.py:408` `read_text()`) |
| unreadable `.bootstrap-status` | `PermissionError`, same line |
| `.bootstrap-status` line with `failed=oops` | `ValueError` from `int()` (`doctor.py:575`; same class at `doctor.py:477` in `build_checklist`, so the first-run path crashes too) |

Each raises out of `run_doctor`, so `python -m vcfops_common doctor`
exits 1 with a traceback into the SessionStart hook, every session,
until the file is fixed by hand. The tests never exercise malformed
inputs, so nothing pins the contract.

Smallest correct fix: wrap the two `read_text()` readers and both
`int()` parses so failure degrades to an attention line (e.g.
`".env exists but could not be read (<reason>); credential check
skipped"`), keep exit 0; add corrupt-input tests for each path. A
belt-and-braces outer try/except in `run_doctor` that emits one
`doctor: internal error` line and returns 0 would also honor the hook
contract, but the per-reader degradation is the informative fix.

## WARNING

### W-1. Credential readiness ignores `os.environ`, diverging from `_env.py`'s actual contract

Authority: brief's stated contract source `src/vcfops_common/_env.py`
("a real shell export always wins over the file";
`available_profiles()` reads `os.environ` after loading `.env`).
`inspect_credentials` (`doctor.py:332`) reads only `<root>/.env`. A
user with `VCFOPS_PROD_*` exported in their shell profile and no `.env`
file is fully working for every CLI, yet the doctor declares
`FIRST-RUN DETECTED` and greets them as unconfigured on every session
(`is_first_run`, `doctor.py:501`: `not env_file_exists` alone
triggers). Also `_env.load_dotenv` walks up from cwd, so a `.env` above
the repo root works for clients but not for the doctor. Fix: union
`.env` keys with `VCFOPS_*` names present in `os.environ` (names only,
still RULE-008-safe), or at minimum do not let a missing file alone
force first-run when a complete profile exists in the environment.

### W-2. Diverged branch: ff-pull offer that cannot succeed

`_render_behind` (`doctor.py:268`) emits the `git pull --ff-only` offer
whenever behind on a clean tree, including when the branch is *also*
ahead (behind and ahead render independently in `run_doctor`). On a
diverged branch, which is this repo's normal working state, the
orchestrator is instructed to offer a pull that `--ff-only` will
refuse. Harmless (nothing destructive) but the instruction is wrong.
Fix: suppress or reword the offer when `st.ahead` is non-empty
("diverged; rebase/merge decision needed, do not pull blindly").

## NIT

- N-1. `LOCAL_STATE_PREFIXES` includes `knowledge/context/reviews/`
  (`doctor.py:60`), but review reports are committed alongside framework
  PRs by convention (this file included). A commit containing only a
  review report gets classed "keep local, no PR needed". Design permits
  the list to live in the doctor; consider whether reviews belong there.
- N-2. `find_repo_root` (`doctor.py:88`) assumes source layout
  (`parents[2]`); a pip-installed copy would anchor into site-packages.
  Fine for the shipped from-source model; worth a comment.
- N-3. First-run checklist tells Windows users to run
  `scripts/bootstrap_references.sh` / `bootstrap_managed_paks.sh`
  (`doctor.py:483`); the design's Python port of those scripts is not in
  this diff, so on native Windows the concierge's step 4 is currently
  unrunnable as worded. Update the detail text when the port lands (or
  in it).

## Scope notes

- Design §Windows portability says the two bash bootstrap scripts "get
  their logic ported into the same Python module during Phase 1"; that
  port is absent from this diff. If it is deliberately deferred to a
  later PR, say so in the PR body so the design and the diff reconcile.
- Global-default-leak / key-collision anchors (`00d3382`, `6c59f6b`):
  not applicable; this change adds a new module and touches no
  renderer, loader, builder, or content path. Verified no import of
  `vcfops_common.doctor` from any other package.

## If shipped as-is

A Windows user whose editor saves `.env` as UTF-16, or anyone with a
hand-mangled `.bootstrap-status`, gets a Python traceback injected into
every session start instead of a doctor line, and the "always exits 0"
hook contract is broken; shell-export-only users are greeted as
unconfigured forever.

---

# Round 2 (2026-08-20, same day)

- **Change re-reviewed:** same three working-tree files after tooling's
  round-1 remediation (`src/vcfops_common/doctor.py`,
  `src/vcfops_common/__main__.py`, `tests/test_common_doctor.py`).
- **Round-2 verdict:** APPROVE (0 BLOCKING, 1 WARNING, 4 NIT). The
  round-1 BLOCKING and both round-1 WARNINGs are resolved and
  independently confirmed. The standing CHANGES REQUESTED is lifted.

## Checks re-run (round 2, independent)

| Check | Result |
|---|---|
| Full pytest suite | 690 passed, 4 skipped, 178 deselected (`-m "not slow"` per pyproject addopts). Matches tooling's claim. |
| Doctor tests alone | 34 passed (claim of 34, up from 23, confirmed) |
| Full validate chain (7 packages) | all green |
| Corrupt-input probes (my own harness, 28 cases through the real `run_doctor`) | 0 crashes, every case rc=0, no secret leak |
| Real-CLI probes (`python3 src/vcfops_common/doctor.py`, `python3 -m vcfops_common doctor`, foreign cwd, closed stdout) | exit 0 in every case |
| Catch-all end-to-end (undecodable git output via a PATH shim) | exit 0, one honest line, no traceback |
| Render regression / pak-compare | n/a (no renderer/builder/template file touched) |
| Stale-zip trigger (dimension 9) | n/a, re-confirmed |

## Round-1 findings: disposition

**B-1 (BLOCKING) — RESOLVED.** All five round-1 crash paths now degrade
to an attention line with rc=0, verified through the real `run_doctor`:

| Round-1 crash | Round-2 behavior |
|---|---|
| non-UTF8 `.env` | `.env exists but could not be read (UnicodeDecodeError); checking exported vars only` |
| unreadable `.env` | same line, `PermissionError` |
| non-UTF8 `.bootstrap-status` | `.bootstrap-status exists but could not be read (UnicodeDecodeError); bootstrap health unknown` |
| unreadable `.bootstrap-status` | same line, `PermissionError` |
| `failed=oops` | `s: unparseable .bootstrap-status line (failed='oops'); re-run the bootstrap script`; first-run checklist emits `bootstrap-clones: unknown` |

I extended the probe set well past the five: `.env` as a directory, as a
broken symlink, latin-1 bytes, NUL bytes, empty, keyless lines, a
non-identifier profile name, a 500KB line; `.bootstrap-status` as a
directory, CRLF, blank/junk lines, `failed=` empty / `-3` / 400-digit /
`1.5` / absent; `.venv` as a file; a root directory deleted mid-run;
garbage and binary git log payloads; a git runner that raises. Every one
returned 0 with a sane line. With `main()`'s catch-all in place I could
not produce a nonzero exit from the shipped entry points, including with
stdout closed. The contract holds.

**W-1 (export-only credentials) — RESOLVED.** `inspect_credentials`
unions `.env` key names with `VCFOPS_*` names from the environment
(`dict.fromkeys(os.environ, "")`, names only), and `is_first_run` no
longer fires on a missing `.env` when a complete profile is exported.
Verified: `.env` deleted + `VCFOPS_PROD_{HOST,USER,PASSWORD}` exported
yields the single green line, `profiles ready: prod`, no FIRST-RUN.

**W-2 (diverged branch) — RESOLVED.** Behind + ahead + clean tree now
emits `branch has diverged (both ahead and behind); a rebase or merge
decision is needed, do not pull blindly`; the `git pull --ff-only`
string is absent. Confirmed by direct probe and by
`test_diverged_branch_suppresses_ff_pull_offer`.

**N-1/N-2/N-3 — RESOLVED.** `knowledge/context/reviews/` removed from
`LOCAL_STATE_PREFIXES` with a comment and pinned by
`test_review_reports_are_core`; the `parents[2]` assumption is
documented with the `git rev-parse --show-toplevel` escape hatch;
the first-run bootstrap-clones detail is platform-neutral and cites
issue #89, which exists and is OPEN ("port bootstrap_references.sh /
bootstrap_managed_paks.sh clone logic to vcfops_common (Windows)"). No
em-dashes remain in any of the three files (rule 7).

## Test quality (dimension 10)

The 11 new tests pin real behavior, not tautologies. The corrupt-input
tests write genuinely corrupt bytes (`"...".encode("utf-16")`,
`chmod 0o000`) and drive the real `run_doctor`, asserting on the
degraded message text. `test_export_only_credentials_are_not_first_run`
asserts the full green line, not just the absence of FIRST-RUN.
`test_environ_values_never_printed` puts the fake secret in an environ
*value* and asserts the var *name* surfaces while the value does not,
which is the actual RULE-008 property. Only
`test_main_catch_all_exits_zero_on_internal_error` is synthetic
(monkeypatched `run_doctor`), which is the right way to pin a catch-all.
Not covered: the `environ=None` default path (real `os.environ`); low
value, noted as NIT.

## RULE-008 re-confirmation after the environ union

Still holds. `inspect_credentials` blanks values at the boundary
(`dict.fromkeys(os.environ, "")`), every emitted credential string is
built from `VCFOPS_<PROFILE>_<SUFFIX>` name components, and no probe
leaked the synthetic secret from either `.env` or an environ value.
The `main()` catch-all *strengthens* RULE-008: it prints only the
exception type name, so a traceback whose frame locals hold a `.env`
line can no longer reach stderr.

## WARNING (round 2, new, non-blocking)

### W-3. Undecodable git output skips the entire preflight instead of one section

`_make_git_runner` (`doctor.py:110`) uses `subprocess.run(..., text=True)`,
which decodes with the ambient encoding and strict errors, and catches
only `OSError` / `TimeoutExpired` (`doctor.py:117`). A commit subject or
path that is not decodable in the ambient encoding raises
`UnicodeDecodeError` out of the runner, through `inspect_upstream`, out
of `run_doctor`. Reproduced with a PATH shim emitting invalid UTF-8:

```
doctor: internal error (UnicodeDecodeError); preflight skipped this session
exit=0
```

The always-exit-0 contract survives (the catch-all does its job), but
credentials, environment sanity, bootstrap health and first-run
detection are all silently dropped for that user every session, on a
git-repo-content trigger they cannot easily see. This is the same class
as B-1, one layer out: it is caught by the belt, not the braces. Most
plausible on the design's Windows path, where `text=True` decodes git's
UTF-8 output as cp1252 and bytes 0x81/0x8d/0x8f/0x90/0x9d are undefined.
Smallest correct fix: pass `encoding="utf-8", errors="replace"` to
`subprocess.run`, and/or add `UnicodeDecodeError` to the caught tuple so
the upstream section degrades to `st.note` while the rest of the doctor
still runs. Add one test with a runner that raises `UnicodeDecodeError`.

## NIT (round 2)

- N-4. `doctor.py:3` says the SessionStart hook invokes
  `python -m vcfops_common doctor`; `.claude/settings.json:28` actually
  invokes `python3 "$CLAUDE_PROJECT_DIR/src/vcfops_common/doctor.py"`.
  Both work and both exit 0 (verified), but the docstring and the wiring
  should agree. Note `-m` works only with the ambient `PYTHONPATH=src`
  (`.claude/settings.json:4`, STRUCTURE.md), so the file-path form is the
  more robust hook choice; fix the docstring, not the hook.
- N-5. `doctor.main(argv)` accepts `argv` and ignores it;
  `__main__.py:28` passes `args[1:]`. `python -m vcfops_common doctor --help`
  therefore prints the full report rather than usage. Harmless, mildly
  surprising.
- N-6. Behind + ahead + **dirty** still renders only `local tree has
  uncommitted changes; resolve them before pulling`, which implies a pull
  will work once the tree is clean. The diverged branch (`doctor.py:277`)
  is `elif`, so the diverged warning is shadowed by the dirty branch.
  Consider emitting both.
- N-7. A negative or 400-digit `failed=` count is accepted and rendered
  verbatim (`s: -3 clone/update failure(s)`). The writers are the repo's
  own scripts, so this is cosmetic only.

## If shipped as-is (round 2)

Operators get one green line per session, or honest by-exception deltas,
and the hook never breaks session start on any corrupt input I could
construct. The one residual: a user whose git history contains a commit
subject or path that is not decodable in their ambient encoding
(realistically a Windows/cp1252 machine) loses the whole preflight to
`doctor: internal error (UnicodeDecodeError)` rather than losing only
the upstream section. That is a follow-up, not a ship blocker.

---

# Round 3 (2026-08-20) — confirm-only pass on the W-3 remedy

- **Scope:** the W-3 delta only. Dimensions cleared in rounds 1 and 2
  were not re-walked.
- **Round-3 verdict:** APPROVE. W-3 is resolved, and the applied fix is
  strictly better than the one I prescribed.

## Checks re-run

| Check | Result |
|---|---|
| Full pytest suite | 692 passed, 4 skipped, 178 deselected (matches claim; was 690) |
| Doctor tests alone | 36 passed (was 34) |
| Full validate chain (7 packages) | all green |
| PATH-shim probe: git log emitting an undecodable byte | rc 0, upstream section renders normally with one replacement char, credentials and bootstrap health still reported |
| PATH-shim probe: round-2's crash shim through the real CLI | `doctor: all green (...)`, exit 0 (was `doctor: internal error (UnicodeDecodeError); preflight skipped this session`) |

## W-3 — RESOLVED, better than prescribed

`_make_git_runner` (`doctor.py:110`) now passes `encoding="utf-8",
errors="replace"` and catches `UnicodeDecodeError` (`doctor.py:126`).
`text=True` is gone from the module entirely.

The claim was that an undecodable byte degrades the upstream section
alone. What actually happens is better: `errors="replace"` means the
decode never fails, so the upstream section does not degrade at all, it
renders with a single replacement character in the affected subject.
Verified with a shim whose `git log` emits `fix caf\xe9 renderer`:

```
behind origin/main by 1 commit(s), incoming changes:
  tooling fixes: 1
    - fix caf<?> renderer
profile 'qa' is incomplete, missing: VCFOPS_QA_USER, VCFOPS_QA_PASSWORD
bootstrap_references: 1 clone/update failure(s): dell
```

The `(1, "")` / "git not available; upstream check skipped" path the
tests assert is now the defensive fallback for a `UnicodeDecodeError`
raised from anywhere else in `subprocess.run`, not the ordinary
undecodable-output path. Round 2's crash reproducer now yields a green
line instead of `internal error`. Windows/cp1252 exposure is closed at
the source: git's UTF-8 output is decoded as UTF-8 regardless of locale.

## Test quality of the two new tests

Neither is a tautology.

- The runner test monkeypatches `subprocess.run` to raise
  `UnicodeDecodeError` and asserts the real `_make_git_runner` returns
  `(1, "")`. It pins a genuine `except` branch (now defensive rather
  than routine), not a restatement of the code.
- `test_undecodable_git_output_keeps_other_sections` is the meaningful
  one: it drives the real `run_doctor` with the real hardened runner
  (`git=None`) and asserts three independent properties, rc 0, upstream
  degraded, and the incomplete-profile and clone-failure lines still
  present. That is exactly the symptom W-3 described (whole-preflight
  loss), so the regression is properly pinned.

## NIT (round 3)

- N-8. Neither new test exercises the real decode path with actual
  invalid bytes, so the `errors="replace"` behavior itself, the part
  that does the real work now, is unpinned. A test that feeds a fake
  runner-level byte string, or a small `subprocess.run` stub returning
  bytes for decode, would pin it. Cosmetic; the monkeypatched pair plus
  my shim probe cover the contract.

## Docstring

`doctor.py:3-6` now states the hook invokes the file by path and notes
the `-m` form depends on an ambient `PYTHONPATH=src`. Matches
`.claude/settings.json:28` and `.claude/settings.json:4`. N-4 resolved.

---

# Round 4 (2026-08-20) — confirm-only pass on bootstrap-health age + fixture-path rename

- **Scope:** the two post-round-3 items only (bootstrap-health age
  reporting; test fixture paths renamed to `<fixture>` form). Dimensions
  cleared in rounds 1 to 3 were not re-walked.
- **Round-4 verdict:** APPROVE. Both items verified. 0 BLOCKING,
  0 WARNING, 3 NIT.

## Checks re-run

| Check | Result |
|---|---|
| Full pytest suite | 699 passed, 4 skipped, 178 deselected (matches claim; was 692) |
| Doctor tests alone | 43 passed (was 36) |
| Full validate chain (7 packages) | all green |
| `scripts/path_reference_audit.sh` | exit 0, "clear", plus the two pre-existing RULE-015 standing-exception WARNINGs |
| Audit negative control (see below) | exit 2 with the injected dead citation, so exit 0 is genuine |
| Timestamp probes (15 malformed / absurd forms, through the real `run_doctor`) | 0 crashes, rc=0 every case |
| First-run checklist with garbage timestamps | rc=0, checklist unaffected |

## Age reporting: degrades, never crashes

Probed 15 field-1 forms through the real `run_doctor`. Every one
returned rc=0 with a sane line or silence:

| Stamp | Result |
|---|---|
| far-future (1,000,000 h ahead), `9999-12-31T23:59:59Z` | negative age, silent (see N-9) |
| `0001-01-01T00:00:00Z` | `bootstrap health is 739848 day(s) stale` |
| `+99:00`, `+25:00`, `...ABC` bogus offsets | `unparseable timestamp ...; bootstrap age unknown` |
| lowercase `z` suffix | parsed, 3 day(s) stale (the `("Z","z")` tuple works) |
| fractional/nanosecond seconds | parsed on 3.12 |
| bare epoch int, date-only, negative year, 9-digit year, zero-width unicode, `-`, 5000-char digits | all `unparseable timestamp` |

`_safe_age_hours` guards `None` before `.strip()` (the `if not stamp`
short-circuit), so the `None` case in `test_safe_age_hours_forms` is a
real code path rather than an `AttributeError` waiting to happen. The
`STALE_AFTER_HOURS` boundary, day-vs-hour wording, and the
exception-only silence on fresh data all behave as claimed.

## Reserved-key spoof guard works

A line carrying an explicit `__ts__=1999-01-01T00:00:00Z` token:

```
{'cloned': '1', 'failed': '0', 'failures': '-', '__ts__': '2026-08-20T18:15:09Z'}
```

The token is dropped at `doctor.py:527` and the real field-1 stamp wins,
so the doctor emits the green line rather than a spoofed "26 years
stale" alarm. A script literally *named* `__ts__` (field 2, not a token)
is handled as an ordinary script name, no collision. Both confirmed
against the real `read_bootstrap_status` / `run_doctor`.

## Age tests are deterministic

The `ts(hours_ago=N)` helper (`tests/test_common_doctor.py:87`) generates
stamps relative to `datetime.now(timezone.utc)`, so nothing is
date-hardcoded and the assertions cannot rot. Margins are safe: 72 h
formats as `3 day(s)` regardless of suite runtime, and the fresh case
uses `STALE_AFTER_HOURS - 1` (a 1 h margin). `test_safe_age_hours_forms`
injects a fixed `now=`, so its fixed stamps yield a fixed delta forever.
Not a tautology set: each drives real parsing or the real `run_doctor`.

## Fixture-path rename and the audit's exit 0

The rename is genuine, and the audit was not weakened (`git status`
confirms `scripts/path_reference_audit.sh` is unmodified). Verified in a
local clone with the three uncommitted files copied in, which reproduced
`exit 0`, then:

- **Negative control:** appending `# knowledge/context/curation/nonexistent-probe.md`
  to the clone's `tests/test_common_doctor.py` produced
  `tests/test_common_doctor.py:621 -> knowledge/context/curation/nonexistent-probe.md`
  and **exit 2**. The audit genuinely scans that file, so the clean run
  is not an artifact of invisibility.
- **Mechanism:** the same probe written as
  `knowledge/context/curation/<fixture>-nonexistent.md` exits 0, i.e. the
  rename lands on the audit's pre-existing documented rule #3
  (placeholder/glob markup `<`, `>`, `$`, `*`, `{`, `}` is skipped), not
  on any new carve-out.
- **`git add -N` is not load-bearing here.** The src/tests pass is a
  filesystem `grep -rnH 'knowledge/' --include='*.py' src tests`
  (`path_reference_audit.sh:641`), not a `git ls-files` enumeration, so
  the citing file is scanned whether or not it is intent-added. Re-ran
  the clone with the three files fully untracked: still clear, exit 0.
  The intent-add only matters for validity checks of citations *to* the
  new files, of which the corpus currently has none.

## NIT (round 4)

- N-9. A future timestamp yields a negative age and is silent, so a
  clock-skewed machine or a stamp written far in the future never
  reports stale, permanently. Fail-open matches report-by-exception, but
  a stamp days in the future is as much a signal as a stale one.
  Consider an `age_hours < -1` branch. Also unpinned by tests.
- N-10. The unparseable-timestamp line echoes field 1 verbatim
  (`doctor.py:718`), so a 5000-character garbage field dumps 5000
  characters into the session context every session. Same class as
  round-2 N-7, but field 1 has no length bound. Truncating to ~40 chars
  would match the `type(exc).__name__`-only discipline used elsewhere.
- N-11. The first-run checklist's `bootstrap-clones` item ignores age: a
  run recorded 700,000 days ago still reports `status: ok, 1 bootstrap
  script(s) recorded, 0 failure(s)`. Defensible (the checklist asks
  "did anything run"), but the first-run concierge is the audience most
  likely to have an ancient or inherited `.bootstrap-status`.

---

# Round 5 (2026-08-20) - Codex PR #93 remediation (7 findings)

- **Change re-reviewed:** uncommitted working-tree diff against the
  approved Phase 1 commit `1749377`, branch `pr4-bootstrap-phase1`:
  `src/vcfops_common/doctor.py`, `tests/test_common_doctor.py`, plus
  `.claude/settings.json` (the hook's missing-interpreter fallback,
  which is in the diff even though the brief named only the two files).
- **Round-5 verdict:** CHANGES REQUESTED (2 BLOCKING, 3 WARNING, 7 NIT).
  Five of the seven Codex findings are correctly and independently
  confirmed fixed. The venv dependency probe (Codex P1) fixes one false
  FIRST-RUN by introducing its opposite, and trusts unvalidated child
  stdout.

## Checks re-run (independent)

| Check | Result |
|---|---|
| Full pytest suite | 713 passed, 4 skipped, 178 deselected (was 699; +14 matches the claim) |
| Full validate chain (7 packages) | all green |
| `scripts/path_reference_audit.sh` | exit 0, "clear", plus the two pre-existing RULE-015 standing-exception WARNINGs |
| Real CLI in this repo (`python3 src/vcfops_common/doctor.py`) | exit 0, one green line, 0.48 s |
| Corrupt-input re-probes (UTF-16 `.env`, chmod 000 `.env`, corrupt parent `.env`) | rc 0, degraded line, no secret in output |
| New subprocess paths (hang, non-executable, exit!=0, 2 MB stdout, invalid UTF-8, real dep-less venv) | rc 0 in every case, no crash, no hang beyond the 10 s timeout |
| RULE-008 with the real `os.environ` default path | no secret in any emitted line |
| Render regression / pak-compare / stale-zip (dimensions 3, 5, 6, 9) | n/a re-confirmed: no renderer, builder, template, or wire-format file in the diff |
| Escape anchors `00d3382` / `6c59f6b` | n/a: no global default, coordinate convention, or key/label derivation touched |

## BLOCKING

### B-5. The venv probe replaces the current interpreter's answer, producing a NEW false FIRST-RUN

`doctor.py:586-598`. When `<root>/.venv` holds an interpreter, the
probe's result **overwrites** `missing_modules` outright; the current
interpreter is consulted only when the probe fails to run. So a machine
whose ambient `python3` has every dep, but which also has a bare or
dep-less `.venv`, is now reported unconfigured.

Reproduced end to end against the real `run_doctor` (a real
`python3 -m venv --without-pip .venv`, ambient interpreter carrying
`yaml`/`requests`/`jmespath`, everything else configured):

```
checked_interpreter: <root>/.venv/bin/python3
missing_modules: ['requests', 'yaml', 'jmespath']
FIRST-RUN DETECTED
additionalContext: Hello, it looks like this is an unconfigured copy ...
```

Under `HEAD` the same root prints one green line. This is the mirror of
the Codex finding it fixes, and it is plausible, not exotic: the
concierge's own checklist item 2 tells the user to `python -m venv .venv`
*then* `pip install -r requirements.txt` (CLAUDE.md:201-205), so any
machine where the venv exists and the pip step failed, was skipped, or
was satisfied by distro packages instead (a normal infra box) now gets
the full first-run greeting every session while `python3 -m vcfops_*
validate` works fine. Note the repo's documented invocation is a bare
`python3 -m vcfops_*` (CLAUDE.md step 5) and nothing in
`.claude/settings.json` selects the venv interpreter, so the ambient
interpreter is the one that actually runs the CLIs.

This breaks the module's own guarantee that a healthy repo prints
exactly one green line, and it is permanent (it never self-heals).

Smallest correct fix: reconcile instead of replace. Compute the current
interpreter's missing set as well and report a module missing only when
it is missing in **both** (`venv_missing & current_missing`). That still
satisfies Codex's case (deps only in the venv -> nothing missing) and
does not regress the inverse. Add a test for ambient-has-deps +
dep-less-venv.

### B-6. `_probe_modules` trusts arbitrary child stdout as a list of module names

`doctor.py:557` returns `proc.stdout.split()` verbatim. Any token the
child interpreter writes to stdout becomes a fabricated "missing
module", which forces `core_missing` non-empty and therefore
FIRST-RUN. Verified:

| Venv interpreter behavior | `missing_modules` |
|---|---|
| prints `Warning: nonstandard site dir` then execs the real python | `['Warning:', 'nonstandard', 'site', 'dir']` -> FIRST-RUN |
| emits 500 KB of stdout, exit 0 | 7423 fabricated names; the emitted `CHECKLIST-JSON` line totals **55 152 characters** injected into session context |
| emits invalid UTF-8 | one fabricated name (no crash, `errors="replace"` holds) |

Wrapper interpreters that chatter on stdout are real (conda/pyenv
shims, corporate wrappers, a `sitecustomize.py` with a print). rc stays
0 and nothing crashes, so this is not a contract break, but it is a
false first-run plus an unbounded context dump from untrusted output.

Smallest correct fix: validate the child's answer against what was
asked, e.g. `names = proc.stdout.split()`; if any name is not in
`set(modules)` treat the probe as failed (`return None`, fall back),
otherwise return the filtered list.

## WARNING

### W-4. The environ default no longer blanks credential values at the boundary

`doctor.py:453`: `environ = {k: v for k, v in os.environ.items() if
k.startswith("VCFOPS_")}` replaces round 2's
`dict.fromkeys(os.environ, "")`. Real passwords now live in a dict for
the duration of `inspect_credentials`, where round 2 explicitly credited
the boundary blanking as the reason no `.env`/environ value could reach
a frame captured by a traceback. RULE-008 (`knowledge/rules/no-secrets-on-disk.md`)
is not violated: nothing is written to disk, the emitted strings are
built from name components only, `main()`'s catch-all prints only
`type(exc).__name__`, and my real-`os.environ` probe leaked nothing. But
the defense-in-depth property the brief asks me to re-verify ("never
retained") is weaker than it was. Fix that keeps both properties:
blank at the boundary while preserving the emptiness signal, e.g.
`{k: ("x" if (v or "").strip() else "") for k, v in os.environ.items()
if k.startswith("VCFOPS_")}`.

### W-5. The new unrecorded-script delta is permanent and unclearable in two supported states

`doctor.py:665-672` and `build_checklist` now demand a line from both
`KNOWN_BOOTSTRAP_SCRIPTS`. But the scripts themselves do not always
write one:

- `scripts/bootstrap_references.sh:52` and
  `scripts/bootstrap_managed_paks.sh:66` `exit 0` on "no sources /
  no paks registered" **before** the status write
  (`bootstrap_references.sh:103`, `bootstrap_managed_paks.sh:117`).
  An empty managed-pak registry is an explicitly supported state
  (CLAUDE.md: "New pak = ... add one line to `knowledge/context/managed_paks.md`"),
  so a clone that registers no SDK paks gets `no bootstrap run recorded
  for bootstrap_managed_paks` every session forever, and no amount of
  re-running clears it.
- Both scripts `exit 1` on a missing registry file (lines 25 / 26),
  same result.
- On native Windows neither script can run at all (issue #89), so a
  Windows user gets both scripts named in a permanent delta line where
  previously the file's absence was silent.

Tooling's "self-heals after one session" claim holds only on unix with a
non-empty registry. A permanent, unactionable line is how operators
learn to ignore the doctor. The fix belongs in `scripts/` (move the
status write before the early exits, recording `cloned=0 failed=0`), not
in the doctor; the diff changed the consumer without changing the
producers.

### W-6. The regression in B-5 is exactly the case the new tests do not cover

`test_deps_are_checked_in_the_repo_venv` pins only the positive
direction (venv interpreter has the deps).
`test_venv_probe_falls_back_when_interpreter_is_broken` and
`test_no_venv_uses_current_interpreter` pin the probe-cannot-run
fallbacks. Nothing pins "ambient interpreter has the deps, venv does
not", and nothing pins that the child's stdout is validated. Dimension
10: a `doctor.py` behavior that decides FIRST-RUN needs its
false-positive direction pinned, not just its false-negative one.

## Codex findings 2 to 7: confirmed fixed

- **P2 empty credential values.** Verified `_env_keys`
  (`doctor.py:409-434`) against the real `_env._parse_into_environ`
  (`_env.py:65-86`) line by line. The branch order is swapped but the
  conditions are mutually exclusive, so the emptiness verdict matches on
  every form I checked (`KEY=`, `KEY=""`, `KEY=''`, `KEY=#c`, a lone
  quote, mismatched quotes, inline `#`). Empty exported values are
  filtered too (`doctor.py:469-472`). RULE-008 holds on this path: values
  are local, never returned, never printed; my probes with the synthetic
  secret in both `.env` and `os.environ` leaked nothing. One documented
  divergence, in the safe direction, in N-15.
- **P2 untracked work.** `--untracked-files=no` is gone
  (`doctor.py:305-307`); an untracked-only tree marks dirty, and
  `_render_behind` says "uncommitted or untracked changes" with no
  `git pull --ff-only` offer. The test asserts the flag's absence, which
  is the right thing to pin.
- **P2 tracking remote.** `_tracking_remote` (`doctor.py:255-274`)
  probed across 9 configurations: tracked remote present -> fetches it;
  no `branch.<b>.remote` -> origin; `git remote` failing -> trusts the
  configured value; detached HEAD, a URL as the remote value, and
  whitespace junk -> origin. Fail-open and offline behavior are intact
  (`available=True`, `fetch_ok=False`, the `(offline?)` annotation still
  renders), and the non-repo short-circuit still fires before any of the
  3 added plumbing calls. See N-16 for the one odd fallback.
- **P2 parent `.env`.** `find_env_file` (`doctor.py:387-399`) matches
  `_env.load_dotenv` (`_env.py:56-62`) exactly, including the
  `[here, *here.parents]` iteration and the "walk to the filesystem
  root" stopping condition. Corrupt parent `.env` still degrades to the
  attention line with rc 0.
- **P2 Tier 1 JAR set.** Read `builder.py:1647-1681`: `ADAPTER_JAR_GAP`
  is gated on `_GENERIC_ADAPTER_JAR.exists()`
  (`adapter_runtime/mpb_adapter3.jar`) and the lib branch on
  `lib_dir.exists()`. The doctor's requirement (adapter jar **and** at
  least one `lib/*.jar`) matches the builder's real functional
  requirement and is deliberately one notch stricter than its literal
  gate; still warn-only, never a failure. Wording nit in N-14.
- **P2 both bootstrap scripts.** Implemented as described; see W-5 for
  the consequence.
- **P1 missing python3** (`.claude/settings.json:13`): the `for c in
  python3 python` probe plus an echoed greeting is a reasonable
  non-Python fallback. See N-17.

## Behavior changes tooling flagged

- **Unrecorded-script delta:** correct in intent, but not universally
  self-healing. W-5.
- **`EnvSanity.jars_present` as a derived property:** fine. Read-only,
  `not self.missing_jars`, no writer anywhere in the module or tests, so
  no silent-downgrade path. Not a problem.

## NIT (round 5)

- N-12. `checked_interpreter` (`doctor.py:510`) is set but never
  surfaced anywhere. When the doctor says "missing python module(s)",
  the operator cannot tell which interpreter was checked, which is the
  single most useful fact once the answer can come from a different
  interpreter than the shell they are typing in.
- N-13. The `.env` degrade line says ".env exists but could not be read"
  without naming the path. With the upward walk that file may be several
  directories above the repo, so the message no longer identifies what
  to fix.
- N-14. The JAR attention line claims builds "would emit
  ADAPTER_JAR_GAP / LIB_GAP placeholders". For an existing but empty
  `adapter_runtime/lib/`, `builder.py:1668` emits **neither** placeholder
  (the `else` fires only when the directory is absent); the pak just
  silently ships no libs, which is worse. The check is right, the
  sentence is not.
- N-15. `_env_keys` applies `.strip()` after unquoting, `_env.py` does
  not. `VCFOPS_PROD_PASSWORD="  "` is accepted by
  `resolve_profile_credentials` (truthy) but reported missing by the
  doctor. Safe direction, worth a comment.
- N-16. When `branch.<b>.remote` names a remote that no longer exists,
  `_tracking_remote` falls back to origin or the first configured
  remote, i.e. it fetches a remote the branch does not track. Harmless
  (the `@{upstream}` comparison is independent and the result is
  fail-open) but it can leave a genuinely stale comparison looking
  green.
- N-17. `.claude/settings.json:13`: the `python` fallback can be a
  Python 2 interpreter, which would emit a `SyntaxError` traceback into
  session context where the previous behavior was silence; guarding with
  `$c -c 'import sys; sys.exit(sys.version_info < (3,9))'` would pick a
  usable interpreter instead of merely a present one. Also the
  no-interpreter greeting duplicates `GREETING` (`doctor.py:59`) as a
  literal string in JSON, so the two will drift.
- N-18. `find_env_file(root)` walks up from the repo root;
  `_env.load_dotenv()` walks up from **cwd**. Identical under the
  SessionStart hook, divergent for a `.env` in a subdirectory of the
  repo.
- N-19. `make_configured_root` now depends on no `.env` existing in any
  parent of `tmp_path`; a stray `/tmp/.env` on a dev machine would flip
  several tests. Cheap guard: assert `find_env_file(root)` is the file
  the fixture wrote.

## If shipped as-is

An operator whose ambient python has the dependencies but who also has
a bare `.venv` (the state produced by following step 2 of the
concierge's own checklist and then having pip fail, or by an infra box
with distro-packaged deps) is greeted with FIRST-RUN DETECTED at every
session start on a fully working repo, and is walked through a setup
they do not need. An operator whose venv interpreter prints anything to
stdout gets the same greeting plus up to tens of kilobytes of fabricated
module names in the session context. A clone with no SDK paks
registered, or any Windows clone, gets a bootstrap delta line every
session that nothing they do can clear.

---

# Round 6 (2026-08-20) - confirm-only pass on the round-5 remediation

- **Scope:** the round-5 findings only (B-5, B-6, W-4, W-5, W-6 and the
  addressed NITs), plus the producer-side change to
  `scripts/bootstrap_references.sh` / `scripts/bootstrap_managed_paks.sh`.
  Dimensions cleared in rounds 1 to 4 were not re-walked.
- **Round-6 verdict:** APPROVE. Both BLOCKINGs are resolved, and the
  applied fix for B-5 is better than the one I prescribed (it also
  removes the subprocess from the healthy path entirely). 0 BLOCKING,
  0 WARNING, 4 NIT.

## Checks re-run

| Check | Result |
|---|---|
| Full pytest suite | 717 passed, 4 skipped, 178 deselected (matches the claim; was 713) |
| `scripts/path_reference_audit.sh` | exit 0, "clear", plus the two pre-existing RULE-015 standing-exception WARNINGs |
| B-5 reproduction re-run (real `python3 -m venv --without-pip .venv` beside a provisioned ambient python) | `missing_modules: []`, `checked: current`, **one green line**, rc 0 (was FIRST-RUN DETECTED) |
| B-6 re-run, probe path forced live (8 child-stdout shapes) | see table below; rc 0 in all, no fabricated names, checklist bounded |
| Corrupt-input re-probes (UTF-16 `.env`, chmod 000 `.env`, corrupt parent `.env`) | rc 0, degraded line now naming the offending path, no leak |
| RULE-008 with the real `os.environ` default path | no secret in any emitted line; values blanked at the boundary again |
| Real CLI in this repo, both invocation forms | exit 0; honest exception-only output (an unrelated ahead-commit), 1.5 s |
| Producer-side scripts (copies driven in a scratch tree) | see "Bootstrap producers" below |
| Em-dash scan over added `src`/`tests`/`scripts` lines (rule 7) | 0 |

## B-5 - RESOLVED, better than prescribed

`inspect_environment` (`doctor.py:582-634`) now computes
`current_missing` first and treats the venv probe as a second opinion,
intersecting the two (`[m for m in current_missing if m in venv_set]`).
Two things follow that I did not ask for and that are strictly better:

- The subprocess is **skipped entirely** when the current interpreter
  already has everything (`if current_missing:` guards the whole venv
  branch), so the common healthy machine pays zero subprocess cost per
  session, and the 10 s worst-case probe timeout can now only be paid on
  a machine that is already degraded. Measured: hang stub costs 10.0 s
  when `current_missing` is non-empty, 0.0 s when it is not.
- `checked_interpreter` reads `current + <venv path>`, which is the
  honest description of an intersection.

## B-6 - RESOLVED

`_probe_modules` (`doctor.py:573-580`) rejects the whole answer when any
returned token is outside the set it asked about. Driven live against
the real subprocess with `check_import` forcing `current_missing`
non-empty (so the probe genuinely runs):

| Child stdout | missing_modules | checked | CHECKLIST-JSON |
|---|---|---|---|
| `Warning: nonstandard site dir` + `yaml` | `['requests','yaml','jmespath']` (fallback) | current | 896 B |
| 200 000 `junk ` tokens (~1 MB) | `['requests','yaml','jmespath']` (fallback) | current | 896 B (was 55 152 chars) |
| `yaml` | `['yaml']` | current + venv | 886 B |
| empty | `[]` -> green line | current + venv | 807 B |
| `yaml yaml requests` (dupes) | `['requests','yaml']` | current + venv | 896 B |
| chatter on **stderr** only, `jmespath` on stdout | `['jmespath']` | current + venv | 807 B |
| sleeps 60 s | fallback after 10.0 s | current | 896 B |
| `yaml` then `exit 2` | fallback | current | 896 B |

rc 0 and no synthetic-secret leak in every case. Duplicate tokens are
handled because the intersection is set-based, and stderr is correctly
ignored.

## W-4, W-5, W-6 and NITs - RESOLVED

- **W-4.** `inspect_credentials` (`doctor.py:460-468`) blanks at the
  boundary again with `{k: ("x" if (v or "").strip() else "") ...}`,
  keeping only the empty/non-empty distinction. The round-2 RULE-008
  property is restored, and the real-`os.environ` probe still emits the
  green line with `profiles ready: qa` and no value.
- **W-5.** Fixed on the producer side, verified below.
- **W-6.** `test_ambient_deps_survive_a_depless_venv` pins B-5's
  regression through the real `inspect_environment` with a venv stub
  reporting everything missing, and asserts the single green line and
  `not is_first_run`. `test_probe_rejects_unexpected_child_stdout` and
  `test_probe_rejects_flood_of_child_stdout` pin B-6, the latter with a
  real 50 000-token flood through a real subprocess plus a `< 4000` byte
  assertion on the rendered checklist. `test_missing_module_line_names_
  the_interpreter` uses the jmespath-alone case (deliberately not
  first-run) so the delta line actually renders. None are tautologies:
  all four drive real code paths, three of them across a real process
  boundary, and each fails if its finding is reintroduced.
- **N-12/N-13/N-14/N-15.** The missing-module line ends with
  `[checked: <interpreter>]`; the `.env` degrade line names the path
  (confirmed in the probe output); the JAR warning now states the
  empty-`lib/` case honestly ("silently no library JARs at all") instead
  of overclaiming `LIB_GAP`; `_env_keys` documents the
  strip-after-unquote divergence from `_env.py`.

## Bootstrap producers (the W-5 fix)

Verified by copying both scripts into a scratch tree (nothing in the
repo touched) and driving every exit path:

| Case | Result |
|---|---|
| `bash -n` on both scripts | syntax ok |
| registry file missing (the `exit 1` path) | rc 1, and a line **is** written: `... failed=1 failures=registry-file-missing` |
| registry present but with zero entries (the early `exit 0` path) | rc 0, line written with `cloned=0 failed=0 failures=-` |
| both scripts run twice | file stays at exactly 2 lines (one per script, replace-not-append preserved) |
| doctor reading the result | `unrecorded_bootstrap_scripts(...) == []`, no delta |

The unclearable delta is gone, and the missing-registry case now
surfaces as an honest `1 clone/update failure(s): registry-file-missing`
rather than silence or an unfixable "no run recorded".

## NIT (round 6)

- N-20. The new keyword-only `probe=` seam (`doctor.py:585`) is used by
  **no test** (`grep -n "probe=" tests/test_common_doctor.py` returns
  nothing). The tests drive the real subprocess with shell stubs
  instead, which is stronger evidence. So the parameter is currently
  dead indirection widening a public signature: either use it or drop
  it. Not a smell in kind (an injectable probe is a legitimate seam),
  only in that it earns nothing today.
- N-21. Residual, inherent to the intersection and worth stating out
  loud: the inverse machine (ambient python lacks the deps, venv has
  them) now reports green while the repo's documented invocation
  `python3 -m vcfops_*` (CLAUDE.md step 5) would fail, because nothing
  in `.claude/settings.json` or the CLI docs selects the venv
  interpreter. This is what the Codex P1 asked for and what
  `knowledge/designs/bootstrap-v2.md:151-156` intends ("everything goes
  through the venv"), so it is a follow-up, not a ship blocker: either
  wire the CLIs to the venv or annotate the green line with the
  interpreter that satisfied it.
- N-22. `[checked: current + <absolute venv path>]` puts a full absolute
  path in the attention line. Fine on a short path, noisy on a deep one.
- N-23. `test_ambient_deps_survive_a_depless_venv` depends on the
  interpreter running the suite genuinely having `requests`/`yaml`/
  `jmespath`. True anywhere the suite can import at all, so acceptable,
  but it is an environmental dependency rather than a hermetic one.

## If shipped as-is (round 6)

An operator gets one green line on a healthy repo, with no subprocess
spawned at all in that case; a machine that is genuinely missing a
dependency in **both** interpreters gets one line naming the module and
which interpreter was consulted; a chatty or flooding venv interpreter
can no longer fabricate missing modules or dump kilobytes into the
session; credential values are blanked at the boundary again; and the
bootstrap delta is now self-clearing on every exit path of both
producer scripts. The always-exit-0 contract survived every probe in
this round.
