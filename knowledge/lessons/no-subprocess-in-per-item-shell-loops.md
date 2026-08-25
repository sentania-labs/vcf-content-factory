# No subprocess inside a per-item loop in `scripts/*.sh`

**Date:** 2026-08-24. **Cost:** `scripts/path_reference_audit.sh` took
3m18s wall on a warm Linux tree (6m11s with one extra dead reference in
the corpus), long enough to blow past a 120s tool-call timeout on a
script that runs on every PR. Issue #112; the shape was first spotted
via MSYS2 (#101), where a fork costs ~199ms, but sandboxed Linux
environments showed ~35ms per fork too. The fix took the same run to
~1.5-7s, byte-identical output (sole deliberate delta: a corpus file
with no trailing newline now has its final line audited; `while read`
silently dropped it, `mapfile`/`grep -n` do not).

## The trap

Shell makes forking invisible. Each of these is a full fork+exec, and
each looked like one innocent line:

- `git ls-files --error-unmatch -- "$p"` called up to five times per
  candidate, inside a loop over thousands of candidates.
- `grep -oP "$pat" <<< "$line"` called twice per LINE of a 5300-line
  corpus. O(lines), not O(findings): the dominant cost.
- `cand="$(strip_trailing_punct "$cand")"`: command substitution of a
  pure-bash FUNCTION still forks a subshell per call.
- `citing_dir="$(dirname -- "$file")"` per candidate.
- `esc="$(printf '%s' "$t" | sed ...)"` per list entry.

At ~5ms per fork on bare Linux this hides; at 35-200ms per fork
(sandboxes, MSYS2, some CI runners) it is the entire runtime. It is a
correctness risk too, not just speed: with ~6000 forks per run and
`2>/dev/null` masking failures, a single transiently-failed fork under
pressure turned a suppression check into a spurious dead-reference
finding twice during #112 verification. Fewer forks means fewer places
for that to happen at all.

## The rule

**No subprocess inside a per-item loop in any `scripts/*.sh`.** Hoist
the subprocess out of the loop and do per-item work with bash builtins:

- Membership tests: run `git ls-files -z` (or the equivalent) ONCE into
  an associative array; per-item checks become `[[ -n "${SET[$k]:-}" ]]`.
  It must be `-z` plus `read -r -d ''`: plain output C-escapes non-ASCII
  paths, so hash keys built from it never match the real bytes.
- Prefix/substring semantics do not survive a bare hash lookup. A
  pathspec like `git ls-files -- "$p/"` is a PREFIX test; precompute a
  directory-prefix set (or scan a hoisted list in bash) instead. And
  git NORMALIZES pathspecs (`a//b`, `a/./b`, `a/x/../b` all resolve)
  where a hash key is byte-literal: canonicalize the candidate in pure
  bash before the lookup or normalized citations go falsely dead.
- Per-line extraction: one `grep -HZnoP` over the whole file list,
  then parse in bash and bucket by key. It must be `-Z` (NUL after the
  filename): `file:line:match` is ambiguous the moment a tracked
  filename contains ":", and the split silently misattributes every
  match in that file. Grep visits files in argument order and matches
  in position order, so output order is preservable exactly.
- `$(my_bash_function)` forks. Return values via a global variable or
  inline the expansion.
- `dirname`/`basename` per item: use `${p%/*}` / `${p##*/}` (mind the
  no-slash case, where `dirname` returns `.`).

## Proving the rewrite

The acceptance bar that made this safe to ship: **byte-identical
stdout, stderr, and exit code** on the same tree, tested in BOTH the
clean state and a deliberately-broken state (one injected dead
reference), old binary vs new. Semantics like prefix-vs-exact match,
C-escaping, and state carried across `continue` (a `prev_line="$line"`
at loop bottom never runs for skipped lines, so "previous line" really
meant "previous NON-SKIPPED line") only bite in the failure paths, so a
clean-path diff alone proves nothing.
