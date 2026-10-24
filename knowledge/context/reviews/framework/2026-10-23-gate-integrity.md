# Framework review: gate integrity (#219, #218, #226), 2026-10-23

Branch `fix/gate-integrity-219-218-226`, three commits on `origin/main`
(`10b1ad0`): `47fe7f3` (#219), `073258b` (#218), `d9303c5` (#226).
Reviewed in a detached worktree, with the gitignored pak clones symlinked in.

**Verdict: CHANGES REQUESTED.** 2 BLOCKING, 3 WARNING, 4 NIT.

The new gate is looser than the vendored template gate on two shapes that
fall outside the two stated divergences. Both are reachable in pak CI once a
pak repo adopts the kit's `defect_gate.py`, and that adoption is the point of
#226.

## BLOCKING

### B1. A multi-artifact `Affects:` written with a space blocks only its first pak

`src/vcfcf_packaging/defects.py:826-840` (`_value_scopes`, multi-token branch),
`:768-786` (`_affects_candidate`), `:789-803` (`_candidate_entries`).

The module docstring (`:75-76`) says a malformed entry "fails closed for EVERY
scope it names: each item of a comma list". That holds only for
`template,unifi`, with no space. Once there is whitespace (`template, unifi`,
`synology, unifi`, `template unifi`, `` `template`, `unifi` ``,
`template and unifi`), the value takes the multi-token path: it is attributed
to its first token only, and the second named pak passes.

Re-run, gating the second named pak (exit codes):

| Affects | gated | vendored | old factory | new (script/kit) | new (package) |
|---|---|---|---|---|---|
| `template, unifi` | unifi | 1 | 0 | 0 | 0 |
| `synology, unifi` (real paks) | unifi | 1 | 0 | 0 | 0 |
| `template unifi` | unifi | 1 | 0 | 0 | 0 |
| `` `template`, `unifi` `` | unifi | 1 | 0 | 0 | 0 |

The vendored gate refuses all of these, so this is looser than the vendored
gate, and the entry does name `unifi`. The stated divergence, "a malformed
entry blocks only the pak it names", therefore does not cover it. In script
mode, which is how the kit runs in pak CI, `_known_pak_names()` is empty, so
the first token never resolves either: the only attribution left is the
single-name candidate.

Authority: RULE-012 (`knowledge/rules/release-gate-defects.md`, "a bad entry
whose `Affects:` is readable gates exactly that artifact"), the module's own
docstring, and issue #226 (adopt the vendored fail-closed rules).

Fix: for a malformed value, split on `[\s,`]+` and treat every token as a
candidate. `ParseError.candidate` becomes a tuple, and `_candidate_entries`
matches when the gated name equals any token. It only fires on an exact
match with the pak being gated, so prose words cannot over-block. In
package mode, also attribute every token that is a known pak, item, or
factory scope, not just the first. Add the rows `comma-spaced` gating
`unifi` and `space-list` gating `unifi` to the parity matrix.

### B2. `--require-registry` passes a registry where no entry can be read

`src/vcfcf_packaging/defects.py:237-244` (`Registry.empty`), `:1321-1331`.

`empty` is `exists and not entries and not errors`. Take a registry that
keeps its `### DEF-NNN` headings but changes field syntax (`* **Field:**`
bullets, or a table). Every entry becomes an unscoped parse error, so the
registry is not "empty", and `--require-registry` exits 0 with warnings.
Re-run on two such files, gating `template` (both name it): vendored exit 1,
new exit 0.

The flag's documented purpose (`:29-32`, `:1252-1256`, and the tier2
changelog row) is to restore the vendored refusal so that "an empty,
truncated or reformatted registry" is never an all-clear for CI that fetched
it on purpose. A reformat that keeps the headings is the most likely real
reformat, and it is not refused.

Fix: under `--require-registry`, refuse when `not registry.entries` (zero
valid entries), not only when there are zero entries of any kind. Add a
`reformatted-fields-required` row to the matrix.

## WARNING

### W1. A digit-bearing malformed heading with no dash-bullet fields is silent

`defects.py:532-551`. A heading such as `### DEF-1O2` or `### DEF-12 (x)`,
whose fields use `*` bullets, produces no ParseError and **no warning at
all**. The vendored gate exits 1. The same entry under a well-formed heading
does warn (unscoped).

The evidential silence was written for prose headings (`### DEFECTS`), but it
also swallows headings that are clearly meant as defect ids. That breaks
RULE-012's "is reported loudly". The behaviour already existed on main, but
this branch rewrote `_flush_entry`.

Fix: stay silent only when the text after `DEF` has no digit (reuse
`_FENCED_PLACEHOLDER_ID_RE` logic). Otherwise record an unscoped error so it
warns.

### W2. Undeclared divergence: trailing heading text

`defects.py:269`. The vendored `_SECTION_RE` is `(DEF-\d+)\b.*`, which
deliberately tolerates `### DEF-027 (synology build 32)` (template issue #18
CI4, named in #226 as a vendored rule). The factory treats that heading as
malformed, which becomes a synthetic open blocker even when the entry is
closed or tracked. Re-run: vendored 0, new 2.

This is stricter, not looser, but it is a third divergence the parity
docstring and the tier2 row do not declare. A pak repo that switches to the
kit gate would newly be refused on a legitimately closed entry. Port the
tolerance, or declare it as a divergence in `tests/test_defect_gate_parity.py:18-22`
and the tier2 changelog row.

### W3. The parity matrix compares only the module and the kit, and the port has gaps

`tests/test_defect_gate_parity.py:93-215`. The test really does extract
`sdk_buildkit/defect_gate.py` from an assembled tarball (verified), so the
kit side is the shipped file. However, the kit is the module by construction
(`test_kit_script_is_the_module_verbatim`), so the comparison against the
vendored gate rests entirely on hand-copied expectations.

Template test cases not ported: `" \t"` heading and field indents, a
2-space heading indent, nested `" - **Status:** closed"` and
`"  - **Status:** closed"` alone, repeated `Affects`, and the comma-list
second item. All of these pass on the new gate except the comma-list second
item, which is B1. Port the missing rows and add the B1 and B2 rows.

## NIT

- **N1.** `defects.py:745-765`. A single-token `Affects:` with trailing
  punctuation (`synology.`, `synology;`) parses as valid and gates nothing.
  The vendored and old gates behave the same, so it is not a regression.
  Cheap fix: validate a bare token against a pak-name shape.
- **N2.** `buildkit.py:146-150`. The generated header shows
  `[--require-registry]` as optional, while the kit README gives it as the CI
  invocation. Say "required in CI" in the header.
- **N3.** `tests/test_emit_fidelity_bugs.py:470-474`. `_view_corpora` globs
  every `content/sdk-adapters/*/views` on disk, including retired clones left
  on a workstation (this one still has the vcommunity family's 96 + 109 + 1
  views). Local runs therefore test more than CI, and a stale retired clone
  can turn a local run red. Restrict it to `load_registry()` names.
- **N4.** #226 is not finished by this PR: the template and the pak repos
  still vendor the drifted fork (the tier2 row says "none forced"). The PR
  body must not use a closing keyword for #226, or it must open the
  regeneration follow-up.

## Verified (no finding)

- **#219.** `registered_pak_names()` reads `Target:` in every section,
  including both forks and all three retired paks, and skips the
  comment-block template. The live-file tests name the paks rather than
  counting them. An entry without a `Target:` line is not recognised. That
  is consistent with bootstrap, which keys on the same line, and degrades
  only to candidate-only attribution. Multi-token `vsanhostmetrics (...)`
  now refuses `vsanhostmetrics` (re-run: 2).
- **Live registry.** `knowledge/context/defects.md` parses with zero errors
  and zero stderr in both package and script mode. `--pak vcommunity-os`
  exits 2 (DEF-004). `compliance`, `synology`, `unifi`, `vsanhostmetrics` and
  `cluster-perf-risk` exit 0. The vendored gate agrees on the four paks it
  was asked about.
- **Shapes re-run against vendored and old gates.** Same or stricter than
  the vendored gate on all 32 adversarial shapes, apart from B1, B2, W1 and
  the two declared divergences (absent/empty registry, malformed entry on
  another pak). The shapes covered nested, repeated and fenced fields, tilde
  fences, unclosed fences, a fenced placeholder after the first entry,
  `" \t"` indent, CRLF, BOM, an HTML-comment entry, and `open (pending)`.
- **#218 coverage.** I classified the real corpora at the README's pinned
  commits (`5981c3c`, `4eb0266`, matching the on-disk clones) by the guard's
  inputs (hint/num/SM, `is_property`, dynamic DISCRETE buckets). Every class
  in the fixed corpus (51 views) and the unfixed corpus (50 views) has a
  fixture. In the real unfixed corpus only the hint class warns, matching the
  new exact-set assertion. For the render test, only `advanced_time_mode`
  (covered by `tests/test_fb011_advanced_time_mode_range.py`) and
  `time_window.unit: MINUTES` from the vcommunity view set are absent from
  the always-present corpora. Removing `content/sdk-adapters` entirely (the
  CI condition) gives 258 passed and no skips across the touched files.
- **Licensing.** No vcommunity license text or body copied. The SolutionConfig
  XMLs are synthetic comments. The only overlap with the source corpus is
  short column labels and the vendor metric keys.
- **Em-dashes.** None in added lines or commit messages. `git diff --check`
  is clean.
- **Suite.** 2225 passed, 9 skipped (default). 2356 passed, 9 skipped
  (`-m ""`). None of the skips are the six #218 tests.
- **Validate chain.** All seven packages exit 0.
- **Stale zips.** Not triggered: no `templates/`, `builder.py`,
  `assembly.py` or `render.py` change, so no `CURRENT_TEMPLATE_VERSION` bump
  is needed.

## Coordination: BUILDKIT_VERSION

`feat/211-sdk-jar-9-1-1-compile-target` also sets `BUILDKIT_VERSION = "1.0.13"`.
This branch changes kit content (new `sdk_buildkit/defect_gate.py` and kit
README text), so whichever merges second must rebase to `1.0.14` and reword
its tier2 changelog row. `sdk-buildkit-v1.0.12` is the latest tag.
