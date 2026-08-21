# Framework review: vcfops_common credential wizard (bootstrap-v2 Phase 2)

- **Date:** 2026-08-20
- **Reviewer:** framework-reviewer
- **Change under review:** uncommitted working-tree files on branch
  `phase2-guardrails-and-issues`:
  `src/vcfops_common/setup_credentials.py` (new),
  `tests/test_common_setup.py` (new),
  `src/vcfops_common/__main__.py` (routes `setup`),
  `src/vcfops_common/doctor.py` (two message strings)
- **Design of record:** `knowledge/designs/bootstrap-v2.md`
  §"Phase 2: credential wizard (no secrets in the transcript)"
- **Prior history:** `knowledge/context/reviews/framework/common-doctor-2026-08-20.md`
  (6 rounds, same module family)
- **Verdict:** CHANGES REQUESTED (1 BLOCKING, 3 WARNING, 6 NIT)

## Checks re-run (independent, not taken on faith)

| Check | Result |
|---|---|
| `tests/test_common_setup.py` | 60 passed in 0.46 s (count matches the claim) |
| `test_common_setup.py` + `test_common_doctor.py`, `-m ""` | 121 passed (matches Scott's post-change run) |
| Full default suite (`-m "not slow"` per pyproject addopts) | **777 passed, 4 skipped, 178 deselected** (was 717 at doctor round 6; +60 exactly) |
| Full validate chain (7 packages) | all green |
| Slow-tier coverage argument | **holds**, see below |
| Real CLI, piped stdin and `</dev/null` | rc 2, refusal text, no prompt, no hang |
| Real CLI, `--password=<secret>` | rc 2, secret does not appear in the output (grep count 0) |
| Real pty end-to-end run (password containing a space and `#`) | rc 0, secret never echoed to the terminal stream, `.env` mode 0600, value quoted and round-tripped |
| Corrupt/hostile-input probes (my own harness, 20 cases) | 1 destructive path found, see BLOCKING-1 |
| Render regression / pak-compare / stale-zip (dimensions 3, 5, 6, 9) | n/a: no renderer, builder, template, or wire-format file in the diff |
| Escape anchors `00d3382` / `6c59f6b` | n/a: no global default, coordinate convention, or key/label derivation touched |
| Em-dash scan over added lines (rule 7) | **1 hit**, see W-3 |

### The slow-tier argument holds

The 178 deselected slow tests live in exactly four files
(`test_cli_phase4.py`, `test_discrete_builder_builtin_metric_enables.py`,
`test_third_party_routing.py`, `test_validate_content_hook.py`); the only
occurrence of `vcfops_common` in any of them is a comment at
`tests/test_cli_phase4.py:104`. The diff touches no packaging, builder,
template or renderer surface. Running the default tier plus the two
`vcfops_common` files at `-m ""` is adequate coverage for this diff.

## Author claims: verified

- **`VCFOpsClient.authenticate()` is unsafe to reuse.** TRUE.
  `src/vcfops_common/client.py:92` raises
  `VCFOpsError(f"auth failed ({r.status_code}): {r.text}")`, i.e. the
  whole response body. The replacement (`acquire_token`) never touches
  `resp.text` or `resp.json()`; it reads `status_code` through `getattr`
  and emits a fixed classification string. Independently confirmed the
  replacement is actually safer: with a stubbed `requests` raising
  `ConnectionError("... url=https://u:<SECRET>@h/suite-api ...")` the
  emitted message is
  `the host could not be reached (ConnectionError): HTTPSConnectionPool: url=https://u:***@h/suite-api ...`.
  Percent-encoded forms are redacted too (`_scrub`), and the token is
  never read at all.
- **Planted secret never on stdout/stderr.** Confirmed on the success
  path and on every failure path I could construct: all five validation
  `kind`s, a leaky caller-supplied validator, entry mismatch, EOF abort,
  `.env` is a directory, unwritable directory, read-only `.env`,
  non-UTF-8 `.env`, non-TTY refusal, `--password` refusal, and a
  100,000-character password. No leak in any of them.
- **Existing profile updated in place, not duplicated.** Confirmed
  against the real `.env.example` and against a verbatim hand-copy of
  it: exactly one active assignment per key, line count unchanged on a
  rotation, and the old password string absent from the file afterwards.
- **Seeding from the now fully-commented `.env.example` still behaves.**
  Confirmed (Scott's change 1 did not break it). Every template line is
  already a comment, so `_comment_out_assignments` is a correct no-op;
  `_assignment_re`'s optional `#` group takes over the commented prod
  slot in place, leaving 5 active assignments, 0 duplicate keys, the
  `qa` / `devel` / `SYNO` placeholders still inert, and the file
  resolving through the real `_env.resolve_profile_credentials`. Also
  re-confirmed Scott's motivating case: a verbatim hand-copy of the new
  template makes the doctor say `no VCFOPS profiles defined` plus the
  wizard handoff, not three fake-ready profiles.
- **Validation failure, decline re-entry, decline save: writes nothing,
  exit 1.** Confirmed, `.env` is absent afterwards.
- **`requests` missing reports `skipped` and offers to save
  unvalidated.** Confirmed, so the credential step is not blocked behind
  the dependency step.
- **Every collaborator injectable** (`ask`, `ask_secret`, `out`, `err`,
  `validator`, `isatty`, `root`). Confirmed; my whole harness uses them.
- **Non-TTY refusal works.** Confirmed through the real CLI with a pipe
  and with `/dev/null`: rc 2, zero prompts, no hang. The SessionStart
  hook cannot trigger a prompt.
- **0600 where supported.** Confirmed on a fresh file, on a pre-existing
  0644 file (tightened), and on a symlinked `.env` (the target is
  tightened). `os.open(..., 0o600)` means there is no world-readable
  window, and no temp file is involved at any point (which is also the
  root of BLOCKING-1, see below).

## BLOCKING

### B-1. A failed write leaves the user's `.env` at zero bytes: every other profile and all hand-written content is destroyed

`src/vcfops_common/setup_credentials.py:316-337` (`write_env_file`).
The file is opened `O_WRONLY|O_CREAT|O_TRUNC` on the live path, so the
existing `.env` is truncated **before** the new text is written. Any
failure between the truncate and the flush leaves a zero-byte `.env`,
and the caller's handler (`:776-781`) reports only
`could not write .env (<type>)` without saying the file was emptied.
`.env` is gitignored, so there is no `git restore`.

Reproduced end to end through the real `run_setup` with a mundane
`OSError(28, "No space left on device")` raised from the write:

```
pre-existing .env: VCFOPS_QA_HOST/_USER/_PASSWORD + a hand-written note + OTHER_TOKEN
rc 1
stderr: could not write .env (OSError): [Errno 28] No space left on device
PRE bytes: 114   POST bytes: 0
qa profile survived: False
user's unrelated content survived: False
```

A second, non-exotic trigger reaches the same state: a password
containing a character that UTF-8 cannot encode (a lone surrogate,
which is what PEP-383 `surrogateescape` decoding produces from a
non-UTF-8 byte typed at the prompt; `sys.stdin.errors` is
`surrogateescape` on this box and under `LC_ALL=C`). `fh.write` then
raises `UnicodeEncodeError`, which is a `ValueError`, so it is outside
the caller's `except (OSError, UnicodeDecodeError)` and outside
`main()`'s handlers. Observed: traceback to stderr **and** the
pre-existing `.env` truncated to `''`.

This is the framework analog of a silent downgrade (dimension 8) on the
one file that holds every credential the factory has: the operator sets
up `prod` and silently loses `qa`, `devel`, `SYNO_*`, and any
hand-written entries. Authority: RULE-008's premise that `.env` is the
sanctioned credential store, and the module's own claim
(`:24`, `:316-324`) that the write is safe.

Smallest correct fix: write to a sibling temp file in the same
directory, created `os.open(path, O_WRONLY|O_CREAT|O_EXCL, 0o600)`, then
`os.replace()` onto `.env`, with `os.unlink` of the temp in a `finally`
on any failure. That is atomic **and** RULE-008-clean: 0600 from
creation, same filesystem, never outlives the run, never left behind on
failure (a plain "no temp file" reading of RULE-008 is not what buys the
safety here; owner-only mode and unconditional cleanup are). Add two
tests: a write that fails mid-way leaves the original `.env` byte-identical,
and no `.env.*` temp remains afterwards. Note `.gitignore:3` already
covers `.env.*`.

## WARNING

### W-1. `main()` has no catch-all, so an unexpected exception prints a raw traceback from the one function that holds a live password

`setup_credentials.py:802-811` catches only `Aborted` and
`KeyboardInterrupt`. Its sibling `doctor.main()` grew a catch-all in
round 2 of the doctor review, and that review explicitly credited it as
a RULE-008 strengthening ("it prints only the exception type name, so a
traceback whose frame locals hold a `.env` line can no longer reach
stderr"). The wizard is a strictly higher-value target and has less
protection. Two demonstrated escapes:

- the `UnicodeEncodeError` path in B-1 (operator-reachable);
- an exception raised **inside** the validator. With a validator raising
  `RuntimeError(f"leaky {SECRET} boom")` the planted secret appeared
  verbatim in the traceback. The shipped `acquire_token` catches broad
  `Exception`, so this needs a caller-supplied validator today; it is a
  documented public seam (`Validator`), and nothing pins that a future
  validator cannot raise.

Fix: mirror `doctor.main()`, one `except Exception as exc` that prints
`type(exc).__name__` only (never `str(exc)`, never `repr(exc)`: note
`repr(UnicodeEncodeError)` embeds the entire offending string, which
would be the whole `.env` text including the password), returns 1, and
says nothing was written / may have been partially written. Also extend
`validate_secret` (`:412-422`) to reject a value that
`value.encode("utf-8")` cannot encode, with the same "the .env format
cannot store this" wording it already uses for newlines. Add a test for
each.

### W-2. Only the password is guarded against newline injection; a newline in USER or AUTH_SOURCE corrupts `.env` and silently shadows the validated password

`validate_secret` (`:420`) rejects `\n`/`\r` in the password precisely
because the `.env` format has no multiline form, but `USER` and
`AUTH_SOURCE` are written through `format_value` with no equivalent
guard (`normalize_host` does reject whitespace, so HOST is covered).
Driven through the real `run_setup` with `user = "u\nVCFOPS_PROD_PASSWORD=injected"`:

```
VCFOPS_PROD_USER='u
VCFOPS_PROD_PASSWORD=injected'
VCFOPS_PROD_PASSWORD='PLANTED-...'
...
resolved user: "'u"   password == the typed secret: False
```

`_env._parse_into_environ` keeps the **first** definition of a key
(`_env.py:85`), so the injected line wins and the profile stores a
password the wizard never validated, after telling the user the host
accepted the credentials. Not reachable through a real TTY prompt (the
line discipline ends the line at `\n`, and `_ask_line` strips), which is
why this is WARNING and not BLOCKING; it is reachable through the
injectable `ask` seam and through any future non-prompt caller. Fix: run
the same newline/CR check over every value in `values` immediately
before `merge_profile_into_env`, or in `_ask_line`.

### W-3. Em-dash in added source (rule 7)

`setup_credentials.py:103`:
`# Repo root anchoring (never cwd) — same contract as doctor.find_repo_root`.
Rule 7 is absolute and explicitly names code comments; the doctor rounds
tracked an em-dash scan as a standing check and it was 0 there. One
character.

## NIT

- N-1. A symlinked `.env` is followed: the secret is written to the
  target (possibly outside the repo) and the **target's** mode is set to
  0600. Probed; the behavior is defensible and arguably desirable, but
  it is undocumented in a docstring that otherwise spells out the file
  handling in detail. Note the `os.replace` fix in B-1 would change this
  behavior (it replaces the symlink), so decide deliberately.
- N-2. The failure message is always `could not write .env`, including
  when the failure was **reading** the existing file (the
  `UnicodeDecodeError` from `merge_profile_into_env`'s `read_text`,
  `:353`). Probed with a UTF-16 `.env`: rc 1, file correctly left
  untouched, but the operator is told the wrong operation failed. Same
  class as doctor N-13.
- N-3. `--profile 'bad name'` seeds an invalid default into the first
  prompt, so pressing Enter re-prompts forever (with the validation
  message each time, so it is loud, not a hang). Validating the flag
  value at parse time would be kinder.
- N-4. The wizard reads and writes `<root>/.env` only, while
  `_env.load_dotenv` and `doctor.find_env_file` walk up to parents. A
  user whose `.env` lives above the repo gets a second file and no
  prompt defaults from the first. Safe in practice (the nearer file wins
  for any in-repo cwd), but it is a divergence from the contract source.
  Same class as doctor N-18.
- N-5. `main()`'s `Aborted` / `KeyboardInterrupt` handlers `print()` to
  real stdout, bypassing the injectable `out`. Harmless, inconsistent
  with the rest of the module's discipline.
- N-6. `getpass` is trusted to be silent. It documents a fallback
  (`GetPassWarning`, "Password input may be echoed") when it cannot get
  a controlling terminal, which the `isatty()` guard makes unlikely but
  does not exclude. Wrapping the `ask_secret` call in
  `warnings.catch_warnings(record=True)` and aborting on
  `getpass.GetPassWarning` would make the module's headline promise
  ("never echoed", `:6-9`, `:682`) enforced rather than assumed.

## Test quality (dimension 10)

The 60 tests are not tautologies. The round-trip tests re-read through
the **real** `_env.resolve_profile_credentials` rather than a private
parser, which is the property that actually matters; the planted secret
carries a quote, a hash, a space and a backslash, so `format_value` is
exercised against the awkward cases; the leak tests assert absence
across stdout, stderr **and** the prompt text on eight distinct exit
paths; `test_a_validator_that_leaks_the_secret_is_scrubbed_before_printing`
pins the defense-in-depth re-scrub of an untrusted validator; and
`test_doctor_hands_off_the_exact_wizard_command` pins the literal
command string in both the checklist and the no-profile path, which is
the thing that stops the orchestrator inventing its own way to collect a
password. Gaps, all tied to findings above: no test for a write that
fails after the truncate (B-1), no test for an unexpected exception
reaching `main()` (W-1), no test for a non-UTF-8-encodable password
(W-1), no test for newline injection in a non-password field (W-2).

## Doctor delta (the two message strings)

Both changes are net-positive and RULE-008-aligned: they name the exact
command, mark it as the user's to run, and forbid asking for a password
in chat. Re-measured the emitted payload on a first-run root: 1308 bytes
total, `CHECKLIST-JSON` 1152 bytes, well inside the round-6 context
budget. `python3 -m vcfops_common doctor` still exits 0 on every probe.

## If shipped as-is

The wizard works: I watched a real pty session collect a password
containing a space and a `#`, never echo it, validate, and write a
0600 `.env` that the real resolver reads back byte-exact, and I could
not get the planted secret onto any stream on any failure path. The one
thing that would hurt an operator is B-1: on a full disk, a
permissions-changed-mid-run file, or a password with a non-UTF-8
character, the wizard truncates their `.env` to zero bytes and tells
them only that it "could not write" it, so a user adding a `devel`
profile can silently lose their working `prod` and `qa` credentials with
no backup and nothing in git to restore from.

---

# Round 2 (2026-08-20) - confirm pass on the round-1 remediation

- **Scope:** the round-1 findings only (B-1, W-1, W-2, W-3, and the NITs
  tooling took: N-1, N-2, N-5), plus the symlink judgment call tooling
  flagged. Dimensions cleared in round 1 were not re-walked.
- **Round-2 verdict:** APPROVE. The BLOCKING is resolved and I could not
  reconstruct it on any path I tried. 0 BLOCKING, 0 WARNING, 4 NIT.

## Checks re-run (independent; the truncate scenario re-probed, not taken on report)

| Check | Result |
|---|---|
| Full default suite | **788 passed, 4 skipped, 178 deselected** (matches the claim; was 777) |
| `tests/test_common_setup.py` alone | 71 passed (was 60) |
| Full validate chain (7 packages) | all green |
| `scripts/path_reference_audit.sh` | exit 0, "clear", plus the two pre-existing RULE-015 standing-exception WARNINGs |
| Em-dash scan, all four files (rule 7) | 0 |
| Real CLI, piped stdin | rc 2, refusal, no prompt |
| Fresh pty end-to-end after the write-path change | rc 0, password with a space and `#` never echoed, `.env` 0600, value quoted and round-tripped |
| My own write-failure / symlink harness (13 cases through the real `run_setup`) | see below; 0 damaged files, 0 temps left behind, 0 leaks |

## B-1 - RESOLVED

`write_env_file` (`setup_credentials.py:320-395`) no longer opens the
live path at all. Re-ran my round-1 reproducer and eight further
failure injections against the real code path:

| Injected failure | Result |
|---|---|
| `ENOSPC` raised from the write (round-1 reproducer: PRE 114 -> POST 0) | rc 1, **`.env` byte-identical**, `qa` profile and `OTHER_TOKEN` intact, no `.env.*` sibling |
| parent directory `chmod 0500` | rc 1, `.env` byte-identical, no sibling |
| `os.fdopen` raising after the `O_EXCL` create | rc 1, `.env` intact, **temp cleaned up** by the `finally` |
| `os.replace` raising `EXDEV` | rc 1, `.env` intact, temp cleaned up, honest message |
| lone-surrogate password (round-1's second trigger) | rejected at the prompt with a retype offer, rc 0 after a good password, `.env` never at risk, the surrogate never echoed |
| newline injected into USER | rc 1, `.env` byte-identical, nothing written |
| existing `.env` saved as UTF-16 | rc 1, file untouched, "could not READ ... left untouched" |

The failure message now states the guarantee ("Your existing .env was
left unchanged (the new file is written alongside and swapped in only
once it is complete)"), which is the part the operator needed and did
not have. `O_EXCL` is the right flag choice and does more than the
docstring claims: it also refuses to follow a pre-planted symlink, which
is what makes the temp safe even when the target sits in a world-writable
directory. `.gitignore:3` (`.env.*`) covers the temp name
(`git check-ignore` confirms), so a temp surviving a `kill -9` cannot be
committed.

## The symlink judgment call: replacing the TARGET is the right call

Assessed on its merits; tooling was right to flag it, and right on the
substance.

- **Right call.** My N-1 was an observation, not an instruction, and
  `os.replace` onto the link would have silently converted a user's
  deliberate indirection into a regular file. That is the same class of
  silent destruction of user configuration that B-1 was about, so
  resolving first is consistent with the fix rather than in tension with
  it.
- **Still atomic.** Resolving is what *preserves* atomicity here. The
  temp must be on the target's filesystem; a temp beside the *link*
  pointing at a target on another mount would make `os.replace` raise
  `EXDEV` (exactly the failure I injected above). Verified with a real
  symlink into another directory: repo dir ends as `['.env',
  '.env.example']` with no temp, the temp having been created beside the
  target.
- **Still RULE-008-clean.** The temp is created `O_EXCL` with mode 0600
  in the directory the user themselves chose for their credential file,
  and is unlinked in a `finally`. Probed target ended at **0600 from
  0644**, so the write also tightens a loose shared file rather than
  inheriting its mode.
- **No new exposure found.** Symlink to a directory: rc 1, honest
  `IsADirectoryError`, nothing written into the directory, temp cleaned
  up. Dangling symlink: the target is created at 0600, the link
  survives, and the wizard correctly reports "created". Symlink into an
  unwritable directory: rc 1, target unchanged, no leak. Symlink chains
  resolve through `realpath`. The residual TOCTOU (an intermediate
  directory swapped between `realpath` and `os.open`) needs write access
  to a parent of the target, which already implies the ability to read
  the credential file, and is no worse than the previous in-place open,
  which followed the symlink at open time too.

## W-1, W-2, W-3 and the NITs - RESOLVED

- **W-1.** `main()` (`:934-970`) mirrors `doctor.main()`: `except
  Exception` printing `type(exc).__name__` only, with a comment
  explaining why `repr()` is as forbidden as `str()`. Driven through the
  real `sc.main()` with a validator raising `RuntimeError(f"leaky
  {SECRET}")`: rc 1, `RuntimeError` named, and the secret, the word
  `leaky`, and any `Traceback` all absent. `validate_secret` now defers
  to `storable_error`, which rejects UTF-8-unencodable values.
- **W-2.** `storable_error(value, label)` (`:493-531`) is applied to
  **every** value in `merge_profile_into_env` (`:424-428`) before the
  file is touched, raising `ValueError` with the key name and never the
  content. My injection probe now returns rc 1 with `.env` byte-identical
  and the shadowing duplicate never written; round 1's silently-stored
  unvalidated password is gone.
- **W-3.** 0 em-dashes across all four files.
- **N-2/N-5/N-1.** `EnvReadError` gives the UTF-16 case a read-failure
  message that says the file was left untouched; the abort handlers
  route through the injected `out`/`err`; the symlink behavior is
  documented in the writer's docstring.

## Test quality of the 11 new tests

Not tautologies. `test_failed_write_leaves_env_byte_identical_and_no_temp_behind`
drives the **real** writer with an exploding `write` and asserts three
independent properties (byte-identity, the neighbouring profile's
survival, and no `.env.*` sibling), so it fails if the O_TRUNC behavior
is ever reintroduced. `test_newline_in_a_non_password_field_cannot_shadow_the_password`
asserts both directions that matter: the field is named and the value is
not quoted. `test_main_never_prints_a_traceback_or_the_secret` pins
"class name yes, message no, Traceback never".
`test_main_reports_a_unicode_error_without_echoing_the_payload` uses a
real `UnicodeEncodeError` rather than a synthetic one. Only
`test_failed_write_says_the_existing_file_survived` is synthetic (it
monkeypatches `write_env_file` wholesale), which is the right way to pin
a message.

## NIT (round 2)

- N-7. `test_write_env_file_replaces_the_target_of_a_symlink` asserts
  the link survives and the target got the content, but not the two
  properties that make the choice safe: that the temp was created beside
  the **target** (my probe checked this; nothing pins it), and that the
  target ends at 0600. Two extra asserts in the same test.
- N-8. `os.replace` gives the target a new inode owned by the wizard's
  user at 0600. For the "shared location" case the symlink resolution
  exists to serve, a target previously owned by another user or readable
  by a group silently loses that. Direction is RULE-008-safe and the old
  code chmod-ed 0600 anyway, so it is not a regression, but the
  docstring's "keeps that indirection" could say "keeps the path, not
  the inode or the group access".
- N-9. A directory that is `0500` with a `0600` file inside was writable
  in place before and is not writable now (creating the sibling fails).
  Contrived for a repo root, fails loudly with an honest message and no
  damage, so this is a note rather than a defect.
- N-10. The OSError line says "Your existing .env was left unchanged"
  even when there was no `.env` to begin with (the create path). Harmless,
  mildly odd.

## If shipped as-is (round 2)

The wizard collects a password no stream ever sees, writes an
owner-only `.env` atomically, and on every failure I could inject leaves
the operator's existing credentials byte-identical with a message that
says so; an unstorable value is refused at the prompt with a retype
offer instead of at the point of no return; an unexpected exception
prints a class name rather than a traceback; and a user who points
`.env` at a shared location still has a symlink afterwards.
