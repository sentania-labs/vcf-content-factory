# Framework review: vcfops_common doctor + credential wizard (issues #96, #102)

- Date: 2026-08-23
- Reviewer: framework-reviewer (RULE-013 pre-PR gate)
- Worktree: `.claude/worktrees/agent-a2318c3a13a42f850`, branch `worktree-agent-a2318c3a13a42f850`
- Base: `main` @ `05480de`
- Files: `src/vcfops_common/doctor.py` (+24), `src/vcfops_common/setup_credentials.py`
  (+137/-9), `tests/test_common_doctor.py` (+46), `tests/test_common_setup.py` (+165)

## Verdict: APPROVE (0 BLOCKING, 4 WARNING, 3 NIT)

## Checks re-run independently

| Check | Result |
|---|---|
| `python3 -m <pkg> validate` x7 (supermetrics, customgroups, dashboards, symptoms, alerts, reports, managementpacks) | 7/7 pass |
| `python3 -m vcfops_packaging validate` | fails, environmental (see below) |
| `pytest tests/test_common_doctor.py tests/test_common_setup.py` | 168 passed |
| `pytest tests/` | 935 passed / 6 failed / 13 skipped |
| Render regression / pak-compare | n/a, no renderer or builder code touched |
| Stale-zip discipline (CLAUDE.md "After tooling changes") | n/a, see Dimension 9 |

### The 6 failures are environmental, reproduction confirmed
Root-caused directly rather than taken on faith. `vcfops_packaging validate`
fails with `artifact source not found: 'content/sdk-adapters/synology/adapter.yaml'`.
`content/sdk-adapters/` does not exist in the worktree at all; it is present
and populated in the main checkout (`compliance, synology, unifi, vcommunity,
vcommunity-os, vcommunity-vsphere`). These are the gitignored independent SDK
adapter repos, absent because a worktree does not carry gitignored content.
Not attributable to this change, not counted against it.

## Claim verification

### #96 items 1 and 3: already fixed on main. Confirmed.
`git show main:src/vcfops_common/doctor.py` has no keyword-only `probe=`
parameter on `_probe_modules`, and line 646 already routes the interpreter
path through `_display_path(vpy, root)`. Both are pinned on main by
`tests/test_common_doctor.py:1166 test_probe_seam_is_gone` and
`:592 assert str(vpy.parent) not in env.checked_interpreter`. `_display_path`
was introduced by `6a02f24`. The issue text is stale on both points and
nothing needed to change. **#96 items 1 and 3 are closeable.**

### #96 item 2: intersection semantics unchanged. Confirmed.
`inspect_environment` still sets `es.missing_modules = [m for m in
current_missing if m in venv_set]` (doctor.py:659), byte-identical logic. The
new field is the complement, `[m for m in current_missing if m not in
venv_set]` (:665), computed only inside the `venv_missing is not None` branch.
`is_first_run` (:981), and both `core_missing` sites at :863/:874, read
`env.missing_modules` only; `venv_only_modules` reaches nothing but the
attention line at :1059. First-run detection and
`test_ambient_deps_survive_a_depless_venv` are untouched, and the full doctor
suite is green.

### Can the new line cry wolf on a healthy install? Verified: no.
Traced every route into the branch. It requires all three of: the current
interpreter is missing a module, the repo `.venv` is not the one running
(`already_in_venv` is False, checked via `sys.prefix`), and the venv probe
succeeded. On an activated venv the probe is skipped entirely; on a machine
with deps in the ambient interpreter `current_missing` is empty and the
subprocess never runs. `test_deps_present_in_both_interpreters_stay_green`
pins the one-green-line case. One inaccuracy remains, see WARNING 1.

### #102 item 2: the getpass warn-before-read ordering. Confirmed, twice.
Read CPython 3.12.3 `getpass.py`: `fallback_getpass` calls `warnings.warn(...,
GetPassWarning)` first, then prints "Warning: Password input may be echoed",
then calls `_raw_input`. Promotion to an error therefore aborts before both
the prompt write and the read. This ordering is structural to
`fallback_getpass` and unchanged across supported 3.9+.

Verified empirically rather than by reading alone:
- Substituting a stdin whose `readline` raises: `read_password_silently`
  raised `EchoNotSuppressed` and the stream buffer was `''`. Neither the
  prompt nor the read happened.
- Warnings scope: with `simplefilter("ignore")` in force, and separately with
  a pre-existing `simplefilter("error", DeprecationWarning)`, the filter list
  compared identical before and after the call. `warnings.simplefilter`
  front-inserts one entry rather than resetting, and `catch_warnings` restores
  the saved list on exit. No global leak.
- Real pty (`pty.fork`, child gets a controlling tty): output was
  `'password (not echoed): \r\n\r\nCHILD-RESULT ok len=7\r\n'`. The password
  was read successfully and never appeared on the tty. A normal terminal is
  unaffected. tooling's pty claim reproduces.

`_ask_password` catches only `(EOFError, KeyboardInterrupt)`, so
`EchoNotSuppressed` propagates cleanly to the `run_setup` handler, which
returns 2 (matching the existing non-TTY refusal). Test assertions are the
right ones: `assert reads == []` is the load-bearing check, not a message
match.

### #102 item 1: atomic write unregressed. Confirmed.
`write_env_file` has **no diff hunk**; it is byte-identical to main. The
`os.open(..., O_WRONLY|O_CREAT|O_EXCL, 0o600)` -> fsync -> chmod ->
`os.replace()` -> `finally: unlink` sequence at setup_credentials.py:380-413
is intact, as are its guards `test_failed_write_says_the_existing_file_survived`
(:777) and `test_write_env_file_replaces_the_target_of_a_symlink` (:809).
Exercised behaviorally against a parent-directory target: prior `VCFOPS_PROD_*`
profile preserved verbatim, new profile appended, resulting mode `0o600`, no
leftover `.tmp*` sibling. `find_env_file` is imported from `doctor` rather
than reimplemented (setup_credentials.py:67), so the two cannot drift, and
there is no import cycle (doctor.py imports stdlib only and has no
module-level side effects).

## Findings

### WARNING 1: the new attention line overstates the jmespath case
`src/vcfops_common/doctor.py:1059-1069`. The line asserts `python3 -m vcfops_*
validate` "would fail here". For `jmespath` that is false: it is a soft
dependency, `src/vcfops_managementpacks/loader.py:2118` imports it in a
`try` and degrades to a `UserWarning` when absent. The same file already
carves it out three times (`core_missing = [m for m in env.missing_modules if
m != "jmespath"]` at :863, :874, :981); the new line does not. A machine whose
ambient python3 has `requests` and `yaml` from system packages but gets
`jmespath` only from the venv now gets told validate would fail when it would
in fact pass with a warning. Doctor reports by exception; an inaccurate
exception is the cry-wolf case.
**Fix:** apply the same jmespath carve-out, or soften the wording for the
jmespath-only case (e.g. "MPB filter validation would be skipped").

### WARNING 2: EnvReadError message names the wrong file
`src/vcfops_common/setup_credentials.py:1041`, `err(f"could not READ the
existing {root / '.env'} ...")`. Now that `env_path` can be a `.env` above the
repo, a read failure on that file (the UTF-16 case the message exists for)
tells the operator to check `<root>/.env`, which may not exist at all. The
message is correct on main and wrong on the new path.
**Fix:** interpolate `env_path`, not `root / ".env"`.

### WARNING 3: the wizard's upward walk is unbounded, and the prompt defaults to yes
`src/vcfops_common/setup_credentials.py:820-833`. `find_env_file(root)` walks
every parent up to `/`. `_ask_bool(ask, out, f"  update {found}?", True)`
defaults to yes, so one Enter writes a plaintext VCF Ops password into a file
outside the repo. `<root>/.env` is protected by this repo's `.gitignore`
(lines 2-4); a `~/.env` or `/.env` is not, and if that parent directory is
itself a git checkout the credentials land somewhere this repo cannot protect
(RULE-008, "Never commit credentials to the repo"). The file already exists
and is already what the CLIs resolve, which is why this is not blocking, but
the default is on the wrong side of the blast radius.
**Fix:** default the prompt to No, and/or state in the prompt whether the
found file is gitignore-protected.

### WARNING 4: 22 tests in test_common_setup.py now depend on the absence of an ancestor .env
`run_setup` calls `_resolve_env_target` unconditionally, so every wizard test
with `root=tmp_path` now walks up through `/tmp` and `/`. Reproduced: running
`pytest tests/test_common_setup.py --basetemp=<dir>` with a `.env` one level
above that basetemp turns **22 of 79** tests red, including the new
`test_wizard_refuses_on_a_terminal_that_would_echo` (its 5-element answer list
has no slot for the "update <path>?" prompt, so every subsequent answer shifts
by one). The same experiment against `tests/test_common_doctor.py` reds 3,
i.e. the exposure class is pre-existing (issue #96 item 4) but this change
amplifies it roughly sevenfold. CLAUDE.md: "Anything that depends on this
machine, this user's memory, or this dev environment is a bug." Not blocking
because it cannot produce a false green and no operator is affected, but the
fix is one autouse fixture.
**Fix:** in `tests/conftest.py`, monkeypatch `sc.find_env_file` (or bound the
walk) for the wizard tests.

### NIT 1: the fix is asymmetric, and the issue should say so on close
It detects "doctor runs on the depless interpreter, venv has the deps." The
mirror (doctor runs inside the venv, ambient `python3` is depless) still
reports green and cannot be detected from inside. Worth one line in the issue
close so #96 item 2 is not recorded as fully solved.

### NIT 2: the venv-only line drops the `[checked: ...]` suffix
`doctor.py:1053` carries `[checked: {env.checked_interpreter}]`; the new line
at :1065 does not, so the operator is not told which venv was probed.

### NIT 3: RULE-018 residue, agree it belongs in the separate issue
`doctor.py:542` (`Scripts/python.exe`) and `setup_credentials.py:402`, `:1050`
(`os.name == "nt"`). Both predate `c1cfc15` and are outside the
`src/vcfops_packaging/templates/` carve-out, so they are genuine RULE-018
violations, but this diff neither adds nor touches them and they are inert on
POSIX. **They should not be fixed here.** One caveat: this diff *does* rewrite
the module docstring immediately above `setup_credentials.py:41-45`, which
still reads "Windows portability: ... `getpass` is silent on Windows too. No
bash." That paragraph now contradicts an absolute rule inside a block this PR
edits; fold it into the same follow-up issue.

## Dimension walk

1. Global-default / pak-specific leak (`00d3382`): n/a, no renderer, pak or
   coordinate code. Reconfirmed the diff is 4 files, all `vcfops_common` +
   tests.
2. Key / label derivation collisions (`6c59f6b`): n/a.
3. Wire-format conformance: the only wire format touched is `.env`.
   `merge_profile_lines` and `format_value` are unchanged; round-trip
   re-verified (password written single-quoted, `_env._parse_into_environ`
   strips matching quotes).
4. Loader / validator correctness: n/a. RULE-006 / RULE-007 not in play.
5. Render regression: n/a.
6. Builder / pak structure: n/a.
7. Corpus regression: 7/7 validate packages pass; packaging blocked
   environmentally with the reproduction above; suite matches the reported
   935/6/13.
8. Silent capability change / downgrade: none. The wizard's new ability to
   write outside the repo is announced and gated by a prompt, not silent. See
   WARNING 3 on the default.
9. Stale-zip discipline: **does not apply.** The diff touches neither
   `src/vcfops_packaging/templates/`, `builder.py`, `discrete_builder.py`,
   `release_builder.py`, nor `src/vcfops_dashboards/render.py`. No
   `content-packager` rebuild is owed and no `CURRENT_TEMPLATE_VERSION` bump
   is owed. (`src/vcfops_packaging/template_version.py` shows modified in the
   main checkout; that is the concurrent installer-templates branch, out of
   scope for this review and correctly outside this worktree.)
10. Test coverage: +11 tests, all behavioral rather than message-matching, and
    they pin the exact properties that matter (`reads == []` for the echo
    guard, filter-list identity for the warnings scope, mode `0o600` for the
    parent-directory write). Adequate.

## If shipped as-is
An operator on a split-interpreter machine stops getting a false green and is
told to activate the venv. An operator on a terminal that cannot suppress echo
gets a refusal and an explanation instead of a password in their scrollback.
An operator keeping `.env` above the checkout has that file updated in place
instead of silently shadowed. The residual costs are cosmetic-to-moderate: a
jmespath-only machine is told validate would fail when it would not
(WARNING 1), a `.env` read failure on a parent file points at the wrong path
(WARNING 2), one Enter can put credentials outside the repo's gitignore
(WARNING 3), and a contributor with a `/tmp/.env` or `/.env` sees 22 unrelated
test failures (WARNING 4).

---

# Confirmation round (2026-08-23, same worktree branch)

All four WARNINGs and both NITs actioned. Narrow re-verification only; nothing
previously cleared was re-opened. Diff is now 5 files, +619/-23.

## Verdict: APPROVE (0 BLOCKING, 0 WARNING, 1 NIT)

## Checks re-run

| Check | Result |
|---|---|
| validate chain x7 | all `exit=0` |
| `bash scripts/path_reference_audit.sh` | exit 0 |
| `pytest tests/` | **941 passed / 6 failed / 13 skipped**, matching the claim |
| The 6 failures | byte-identical test IDs to the first round, all `real_repo` packaging validate, already root-caused to `content/sdk-adapters/` being absent in the worktree |

## W1 (jmespath boundary) — fixed, and it is the same boundary
`doctor.py:1069` uses `[m for m in env.venv_only_modules if m != "jmespath"]`.
That is the identical predicate to the three existing carve-outs at `:863`,
`:874`, `:981` (`[m for m in env.missing_modules if m != "jmespath"]`), applied
to the sibling list. Not a fourth, slightly different boundary. Both branches
now carry the `[checked: ...]` suffix (NIT 2). Pinned by
`test_a_venv_only_jmespath_is_not_reported_as_a_broken_validate` (asserts
`"would fail" not in text`, `"soft dependency" in text`, and the `[checked:
current + .venv/bin/python3]` suffix) and
`test_a_core_module_venv_only_still_reports_a_failing_validate` (yaml venv-only
keeps the claim and does not name jmespath in it).

## W2 (wrong path) — fixed
`setup_credentials.py:1068` now interpolates `env_path`.
`test_read_failure_on_the_parent_env_names_the_parent_file` plants a UTF-16
parent `.env`, answers `y`, and asserts `str(parent) in d.stderr`,
`str(root / ".env") not in d.stderr`, the parent's bytes unchanged, and the
secret absent from all streams. The original repo-local test
(`test_unreadable_env_reports_a_read_failure_not_a_write_failure`) still passes,
so both paths are covered.

## W3 (default flipped + gitignore verdict) — fixed, and the verdicts are accurate
Prompt is `write the password into {found}?` with default `False`, preceded by
"It is outside this repo, so this repo's .gitignore does not cover it: {verdict}".
Declining still writes repo-local and prints the SHADOW warning.

**The subprocess cannot become fatal or hang. Proven, not assumed:**
- `subprocess.run([...], capture_output=True, timeout=5)`, argv list, no
  `shell=True`, output captured so git can never write into the wizard's
  stdout. `check-ignore` is a local operation with no network and no
  credential prompt.
- `except (OSError, subprocess.SubprocessError, ValueError)` covers
  git-not-installed (OSError) and `TimeoutExpired` (a `SubprocessError`
  subclass).
- Planted a `git` on PATH that is `sleep 60`: the call returned in **exactly
  5.0s** with "could not determine whether anything git-ignores it". No hang,
  no exception escaping.
- Emptied PATH: also degrades to "could not determine".

**All four verdicts are accurate. Matrix run against real repos:**

| scenario | rc | verdict emitted | correct |
|---|---|---|---|
| `.env` in a repo whose `.gitignore` lists it | 0 | "a git repo there DOES ignore it" | yes |
| `.env` in a repo, not ignored | 1 | "NOT git-ignored, and its directory IS a git repo, so a password written there could be committed" | yes |
| `.env` in a plain directory | 128 | "its directory is not a git repo, so nothing there could commit it" | yes |
| `.env` in a subdir of a repo rooted above | 0 | "DOES ignore it" | yes |
| git absent / hanging | n/a | "could not determine" | yes |

> **Annotation added 2026-08-24. Row 3 of the table above is wrong, and
> it is left in place deliberately.**
>
> `git check-ignore` returns **128** for a real repository whose
> `.git/config` is malformed or unreadable, not only for a plain
> non-repo directory. Verified against git 2.43.0: plain non-repo,
> malformed config, and unreadable config all return 128 and are
> indistinguishable by exit status. So the "correct: yes" on that row
> was a miss by this gate, and the verdict it approved was a false
> assurance on the one prompt where an operator decides whether to write
> a plaintext credential outside the repo.
>
> Caught afterward by Codex (P2 on PR #117) and fixed in `de1cfe3`,
> which maps 0 = ignored, 1 = not ignored, everything else = "could not
> determine".
>
> The row is not edited to match the fix. Rewriting it would delete the
> only evidence that this review cleared the exact thing that was then
> caught downstream, and would leave a review artifact reporting green
> about its own blind spot. Follow-up #122 tracks recovering the benign
> non-repo case by walking for a `.git` entry rather than trusting the
> exit status alone.

The specific false-reassurance risk I went looking for does not exist: a
**tracked** `.env` that also matches an ignore pattern (`git add -f`) returns
**rc=1**, not 0, because `git check-ignore` excludes tracked paths by default.
So the confident "DOES ignore it" cannot fire on a file that would in fact be
committed. The one confident claim errs in the safe direction.

## W4 (test fragility) — fixed, and it does not mask the behavior under test
`tests/conftest.py::_bound_env_discovery_to_tmp` wraps the real
`doctor.find_env_file` and drops only hits outside `tmp_path_factory.getbasetemp()`,
patching both modules because `setup_credentials` imports the name. Wrapping
rather than reimplementing means the real walk stays under test; only its result
is filtered.

Confirmed it cannot produce a false green: the parent-`.env` tests plant the
file at `tmp_path/.env` with `root = tmp_path/"repo"`, i.e. **inside** basetemp,
so the fixture passes the hit through untouched and the real upward walk is what
finds it. Those tests still assert the substantive behavior end to end: the
prompt is reached (`"[y/N]" in prompt_text`), the parent file is updated in
place, the pre-existing `VCFOPS_PROD_*` profile survives, and `root/.env` is
*not* created. The declining test asserts the mirror. Measured claim reproduces
(25/149 without the fixture, all green with).

## NIT 1 / NIT 2 — done
`[checked: ...]` on both venv-only branches, asserted in three tests. The
`setup_credentials.py` module docstring's Windows paragraph is rewritten as
"Platform: POSIX only (Linux, macOS, WSL), per RULE-018" and names issue #115
for the three surviving `os.name == "nt"` branches.

## The carried asymmetry: acceptable to ship. My read.

It does not re-create the defect #96 exists to fix, for three reasons.

1. **It never regresses main.** On main the doctor was green in *both*
   directions. It is now green in one. The change is a strict improvement; the
   undetected half is exactly what main already did.
2. **The uncovered half is the one that does not bite the session.** The doctor
   is invoked by the SessionStart hook, and the hook's interpreter is the
   ambient one (this is precisely the "Claude may be started outside an
   activated virtualenv" case the both-interpreters intersection was built for,
   doctor.py:619-627). That is the covered direction. The mirror requires the
   doctor to already be running inside an activated venv, and in *that* shell
   `python3 -m vcfops_* validate` works. The stale green only misleads if the
   operator later opens a different, non-activated shell.
3. **It is close to inherent, not an omission.** Detecting the mirror means
   asking "what would `python3` resolve to in the operator's *next* fresh
   shell", from inside an activated venv where PATH already points at the venv's
   own interpreter. Answering that requires stripping `VIRTUAL_ENV` from PATH
   and re-resolving, which is guesswork about a shell that does not exist yet.
   A doctor that guesses wrong here would cry wolf, which is the failure mode
   this whole round was about.

The green line also does not *claim* the mirror is fine: `checked_interpreter`
stays `"current"` in that case, and the green line asserts nothing about which
interpreter. It is silent, not lying. That is the line between an honest gap and
the #96 defect.

**NIT (confirmation round):** the asymmetry is documented in the issue and in
tooling's report, but not in the code. `doctor.py:644-649` (`already_in_venv`)
is where a future maintainer will assume the check is symmetric; the
"mirror-image failure" comment at `:623` is about a different thing. One
sentence there would close the gap. And #96 item 2 should be closed as **the
detectable half**, not as solved: the issue's own text already points at the
real fix ("worth resolving when the credential wizard / docs convergence phases
wire venv activation"), which is wiring the CLIs to the venv, not better
detection.
