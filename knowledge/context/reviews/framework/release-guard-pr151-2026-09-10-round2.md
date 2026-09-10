# Framework review round 2: release guard, PR #151 (a7e6a1c, ea3eda6, 775ae04, ea4d83c)

- **Area:** `scripts/version_line_guard.sh`, `.githooks/pre-push`,
  `tests/test_release_guard_push_matrix.py`, `knowledge/context/defects.md`
  (DEF-020), merge of origin/main (recon log conflict)
- **Change:** closes round 1 (`release-guard-pr151-2026-09-10.md`, CHANGES
  REQUESTED on ced4cf0): unreadable tags recorded and the loop continues;
  gate exit 2 counts only with its refusal line, `--pak=`; `|| true` on
  the adapter_kind and version pipelines; single quotes stripped; hook
  surfaces WARNING on exit 0; 24 real-push tests. DEF-020 Affects made a
  bare token.
- **Verdict:** APPROVE
- **Findings:** 0 BLOCKING / 0 WARNING / 5 NIT (2 carried from round 1)

## Checks re-run

| Check | Result |
|---|---|
| `bash -n`, `shellcheck -x` on guard + hook | pass, clean |
| `tests/test_release_guard_push_matrix.py` on HEAD | 24 passed |
| Same file against a `git archive 16d6c3f` snapshot (scripts, src, .githooks) | exactly 6 fail: test_07 x2, test_08, test_09, test_13, test_14; 18 pass. Matches the orchestrator's claim. |
| Same file under hostile host config (HOME and XDG gitconfig with `commit.gpgsign`, `tag.gpgsign`, `init.defaultBranch=trunk`, `push.default=nothing`, `core.hooksPath=/nonexistent`; outer `GIT_DIR`, `GIT_WORK_TREE`, `GIT_CONFIG_COUNT` set; http(s) proxy at a dead port) | 24 passed. Sanity: the same config made plain `git` produce `trunk` and a gpg signing failure, so it was live. |
| Full suite `pytest tests -n auto --dist=loadgroup` | 1513 passed, 4 skipped (all 4 are `managementpacks/test_gap_b_f_d.py` buildNumber, unrelated) |
| Seven-package validate chain | all rc 0 |
| `scripts/path_reference_audit.sh` | clear (two standing RULE-015 exceptions for `defects.local.md`) |
| Real repo untouched by the tests | `git status` clean; `.bootstrap-status` mtime predates every run |
| Stale-zip / `CURRENT_TEMPLATE_VERSION` | n/a: `git diff origin/main...HEAD` touches no templates, builders, render.py or template_version.py |

### Round 1 fixture re-run (real `git push`, HEAD scripts via symlink)

| Case | Round 1 | Round 2 |
|---|---|---|
| branch-only; 0.x light/annotated; 1.x light/annotated; delete 0.x; delete + 1.x; mixed both orders; `--tags` | correct | correct, unchanged |
| **B1** unreadable tag + 0.x tag, both orders | 0.x tag pushed | refused, remote empty, both orders |
| `--tags` including the unreadable tag and the single-quoted tag | refused | refused; each 0.x tag reported, unreadable one logged, loop continued |
| python3 absent: 1.x / 0.x | allow (4) / refuse | same |
| open blocker; registry chmod 000; registry bad UTF-8 | 3 / 4 / 4 | same |
| **W1** guard `--pak -x` | exit 3, false RULE-012 refusal | exit 0 (`--pak=-x` is a value, no defect names it) |
| **W2** dist/ present, tree adapter.yaml without adapter_kind, open blocker | exit 1, pushed | refused RULE-012 |
| **W3** `version: '0.5.0'` | pushed | refused RULE-014 |
| **W5** absent registry through hook | warning swallowed | gate WARNING printed on push output, allowed |

### Regression hunt (direct guard, fixture pak)

| Probe | Result |
|---|---|
| Unreadable tag + 1.x tag + open blocker | exit 3 (refusal wins over exit 1) |
| Only an unreadable tag + open blocker | exit 3 |
| python3 shim: argparse-style usage text, exit 2 | exit 4, allowed, usage text shown |
| python3 shim: "Refused by RULE-012" on stderr, exit 2 | exit 3 (2>&1 capture sees stderr) |
| python3 shim: exit 2, no output | exit 4 (`[[ -n "" ]] && printf` is a non-final `&&` element, so errexit does not fire) |
| python3 shim: interleaved stdout/stderr traceback, exit 1 | exit 4, both streams shown in order |
| Every exit-2 path of `defect-gate --pak` (`cli.py:626-640`, `defects.py:895-907`) | all print "Refused by RULE-012"; test_10 pins the phrase, so wording drift fails the suite rather than silently downgrading to exit 4 |
| `if ! ver="$(read_version ...)"` | errexit is suppressed inside the function; a failed `cat`, `git show` or grep miss reaches the explicit `return 1`. No path exits with a wrong code. |
| Real violation reachable as exit 1 or 4 | none found: exit 1 for unreadable tags is the last statement, after `exit 2` and the gate's `exit 3` |
| Infrastructure failure reachable as a refusal | only via bash's own exit 2 (syntax error); see N3 |

### Merge ea3eda6 (recon log)

`git show --remerge-diff ea3eda6` shows the only hand resolution is in
`knowledge/context/investigations/recon_log.md`: conflict markers removed and
a blank / `---` / blank separator added. No other file differs from the
automatic merge. Line accounting: base 4505, ours +230, theirs +8, merged
4746 (= 4505 + 230 + 8 + 3 separator lines). `diff ours merged` is a pure
append of the separator plus theirs' 8-line 2026-08-29 embargo pointer
entry, and no base line is missing. HEAD's copy is byte-identical to the
merge result. Nothing lost from either side.

### DEF-020 (775ae04)

The diff touches only DEF-020's `Affects` (now `vcommunity-vsphere`, the bare
pak-name form the registry schema table prescribes) and `Summary` (location
note moved to the front, text otherwise unchanged). Severity, Status,
First-seen and Source are untouched. `defect-gate --pak` for all six
registered paks, registry at 775ae04^ versus HEAD:

| Pak | before | after |
|---|---|---|
| synology, unifi, compliance, vcommunity | 0 | 0 |
| vcommunity-os | 2 (DEF-004) | 2 (DEF-004) |
| vcommunity-vsphere | **0** | **2 (DEF-020)** |

Only the intended verdict changed. The parser gap that made the wrapped
value silently match nothing is issue #153, out of scope.

## BLOCKING

None.

## WARNING

None.

## NIT

- **N1 (carried).** `version_line_guard.sh:136-140`: stdin with only
  deletion lines exits 1. Unreachable via the hook, which filters first.
  Declined by choice this round.
- **N2 (carried).** Doctor does not voice `unknown=`; deferred to issue #152.
- **N3 (pre-existing, defense in depth).** `.githooks/pre-push:84` refuses
  on any guard exit 2 or 3, but bash itself exits 2 on a syntax error:
  a guard truncated mid-file (probed at three cut points) exits 2 and the
  hook prints "push refused" with no REFUSED line. Not reachable in normal
  operation (git replaces files by rename, so a running guard never reads a
  half-written file, and the suite now executes the guard end to end), so
  this is a NIT. Fix, mirroring W1: in the `2|3` arm, refuse only when
  `$out` contains `REFUSED (RULE-01`; otherwise fall through to "not
  guarded".
- **N4 (diagnostics).** `version_line_guard.sh:278-289`: the remap
  overwrites `gate_rc`, so a gate that exited 2 without a verdict is
  reported as "could not run (exit 4)", hiding the real code. Also the
  `2>&1` capture moves the gate's stderr (ERROR, WARNING, tracebacks)
  onto the guard's stdout. Nothing is lost through the hook, which merges
  both, but a by-hand or CI caller reading only stderr no longer sees
  them. And under `--skip-defect-gate`, line 299's "passed both checks" is
  untrue. Fix: keep the original code in the message; print `gate_out`
  to stderr; say "passed the checks that ran" when the gate was skipped.
- **N5 (global rule 7).** `version_line_guard.sh:297`, added in a7e6a1c,
  uses an em-dash in the new WARNING line. Use a colon. Older em-dashes in
  the file are pre-existing.

## Test file notes (no finding)

- Host independence rests on `GIT_CONFIG_GLOBAL` (git 2.32+) and
  `init -b` (git 2.28+). On git 2.28 to 2.31 host config would leak. Older
  git fails loudly at `init -b`. The runner here is 2.43.
- Network: the bootstrap cases fetch from the local bare origin; the
  registry's `https://example.invalid` URL is used only to clone a missing
  target, and the fixture pre-creates it. They passed with dead proxies.
- Root: only test_12 depends on file permissions and it carries the
  documented skipif. Running as root could not be exercised here (user
  namespaces denied); verified by code read.

## If shipped as-is

The guard refuses every 0.x tag and every open-blocker pak on each push
shape exercised, including the round 1 bypass. It lets infrastructure
failures through with a visible warning. DEF-020 now actually gates
vcommunity-vsphere.
