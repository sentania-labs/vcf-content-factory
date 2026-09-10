# Framework review: release guard + bootstrap state, PR #151 (commit ced4cf0)

- **Area:** `scripts/version_line_guard.sh`, `.githooks/pre-push`,
  `scripts/bootstrap_managed_paks.sh`, `scripts/bootstrap_references.sh`
  (release-gate plumbing, reviewed under RULE-013 posture though outside `src/`)
- **Change:** answers the four Codex findings on PR #151: gate exit 2 maps to 3,
  anything else to new exit 4 (warn and allow); every v* tag checked at its own
  commit (`--ref`); tag deletions skipped; `no-upstream` rendered Unknown with an
  additive `unknown=` status key. Design doc: 16d6c3f.
- **Verdict:** CHANGES REQUESTED
- **Findings:** 1 BLOCKING / 5 WARNING / 2 NIT

## Checks re-run

| Check | Result |
|---|---|
| `bash -n` on all four scripts | pass |
| `shellcheck -x` on all four scripts | clean (0 findings) |
| `pytest tests -q -n auto --dist=loadgroup` | 1454 passed, 4 skipped, 0 failed |
| Tests asserting old guard/bootstrap behavior | none found (no test exercises the guard, hook, or bootstrap rendering at all) |
| Stale-zip / `CURRENT_TEMPLATE_VERSION` | n/a: no templates, builder, or renderer touched |

Fixture: fake factory (symlinked `scripts/`, `src/`, `.githooks/`, own
`knowledge/context/defects.md`), pak repo `content/sdk-adapters/fixturepak`
with a 0.x commit and a 1.x commit, lightweight and annotated tags on each,
a local bare remote `vcf-content-factory-sdk-fixturepak.git`, and
`core.hooksPath` pointed at the hooks. Every case below is a real `git push`.

| Case | Expected | Observed |
|---|---|---|
| Branch-only push | allow | allow, guard not invoked |
| 0.x tag, lightweight | refuse (2) | refused |
| 0.x tag, annotated | refuse (2) | refused (`sha^{commit}` peels correctly) |
| 1.x tag, lightweight / annotated | allow | allowed |
| Delete a 0.x tag from remote | allow | allowed |
| Delete 0.x tag + push 1.x tag in one push | allow | allowed |
| Mixed batch good+bad, both orders | refuse | refused, nothing pushed |
| `git push --tags` (two 0.x, two 1.x) | refuse | refused |
| python3 absent from PATH, 1.x tag | allow with warning | gate exit 127, guard exit 4, allowed |
| python3 absent, 0.x tag | refuse (RULE-014 needs no python) | refused |
| Open blocking defect naming the pak | refuse (3) | refused |
| Registry `chmod 000` (gate exit 1) | allow with warning | guard exit 4, allowed |
| Registry invalid UTF-8 (gate exit 1) | allow with warning | guard exit 4, allowed |
| **Tag on commit with no adapter.yaml + 0.x tag, either order** | **refuse** | **allowed, 0.x tag reached the remote** (B1) |
| Single-quoted `version: '0.5.0'` tag | refuse | allowed (W3, pre-existing) |
| `dist/` present, tree adapter.yaml lacks `adapter_kind:`, open blocker | refuse | guard exit 1, allowed (W2, pre-existing) |
| Absent registry, 1.x tag | allow **with warning** (RULE-012 text) | allowed, warning swallowed (W5, pre-existing) |

Bootstrap scripts, run from the fixture factory root:

| Case | managed_paks | references |
|---|---|---|
| Branch with no upstream | `Unknown`, `unknown=fixturepak` | `Unknown`, `unknown=refslug` |
| Detached HEAD | `Unknown`, recorded | `Unknown`, recorded |
| Tracking, level with upstream | `Current`, `unknown=-` | `Current`, `unknown=-` |
| Registry file missing (early exit) | rc 1, line written, fields aligned, `unknown=-` | same |
| Interrupted (`timeout` TERM during fetch) | `failures=interrupted checked=no hooks=- unknown=-` | `failures=interrupted checked=no unknown=-` |
| Doctor `read_bootstrap_status` + `bootstrap_report_lines` | parses `unknown`, no crash | same |

`write_status` positions checked by code-read and by the emitted lines at
all four call sites in each script (final, registry-missing, empty registry,
interrupt trap): managed_paks is 11 positional (`hk` at 9, `ck` at 10, `un`
at 11), references is 10 (`ck` at 9, `un` at 10). The trap calls pass 10
and 9 args respectively, so `un` defaults to `-` and `checked=no` lands in
the right key. Correct.

`read_version` set -e check: it is only ever called as
`ver="$(read_version ...)" || exit 1`, so errexit is suppressed inside it and
a failed `grep | head | sed` pipeline falls through to the empty-`ver`
message and `return 1`. No wrong-code exit there. The gate call is
`( ... ) || gate_rc=$?`, likewise safe. The trap is the `|| exit 1` itself
(B1).

## BLOCKING

### B1. A reached RULE-014 refusal is discarded when any tag in the batch has no readable adapter.yaml

- **Where:** `scripts/version_line_guard.sh:179`,
  `ver="$(read_version "${ref}")" || exit 1` inside the per-tag loop.
- **Authority:** RULE-014 (`knowledge/rules/pak-version-lines.md`: 0.x is
  never tagged); `knowledge/rules/release-gate-defects.md` fail-safe clause
  (warn and allow only when *no verdict* was reached); the closed
  vcommunity-vsphere `0.0.0.12` release incident in
  `knowledge/context/defects.md`, whose stated fix is exactly this guard.
- **What regresses:** the new per-tag loop exits 1 on the first unreadable
  tag. That abandons the tags after it, abandons a RULE-014 hit already
  counted for tags before it, and skips the RULE-012 gate. The hook maps
  exit 1 to "not guarded" and lets the whole push through. Reproduced with a
  real push, both orders:
  - `git push origin v2-noyaml v0-light`: guard prints
    `adapter.yaml not readable at f263baf...`, hook prints
    `guard could not run (exit 1); not guarded`, and **`v0-light` (0.x) is
    created on the remote**.
  - `git push origin v0-light v2-noyaml`: guard prints
    `REFUSED (RULE-014)` for `v0-light`, then the unreadable message, hook
    says `exit 1; not guarded`, **both tags pushed**. A verdict was reached
    and then thrown away.
- **Reachability:** `git push --tags` / `--follow-tags`, or any batch that
  includes a v* tag on a commit without a root `adapter.yaml` (history from
  before the adapter layout, a template-repo initial commit, a tag on a
  non-commit object). This is new with ced4cf0: the old guard checked one tag
  against the working tree and could not drop a verdict this way. Codex
  finding 2 was closed by opening this.
- **Smallest correct fix:** on `read_version` failure, print the message,
  count the tag as unreadable, and `continue`. After the loop, `exit 2` if
  any RULE-014 hit. Then still run the RULE-012 gate (it is per pak, not per
  tag). Only at the very end, when nothing refused and some tag was
  unreadable, exit 1 (warn and allow). Add a test for both orderings (see W4).

## WARNING

### W1. Gate exit 2 is also argparse's usage-error code, so a CLI failure can still become a RULE-012 refusal with a false message

- **Where:** `scripts/version_line_guard.sh:262-268`.
- **Authority:** `knowledge/rules/release-gate-defects.md` fail-safe clause
  ("an infrastructure problem must never stop someone pushing a fix").
- **Evidence:** `python3 -m vcfops_packaging defect-gate-renamed ...` exits 2;
  `defect-gate --pak fixturepak --bogus` exits 2;
  `version_line_guard.sh --pak -x` exits **3** and prints
  `REFUSED (RULE-012) open blocking defect(s) affect pak '-x'` right under
  Python's `argument --pak: expected one argument`.
- **Why WARNING, not BLOCKING:** the script and the CLI ship in the same
  commit and the pak name comes from the origin URL, so today it needs a
  `-`-prefixed repo name or future CLI drift. It is not new (before, every
  nonzero was 3), but the change claims "only exit 2 from the gate becomes a
  refusal" as if 2 meant "blocked" unambiguously; it does not.
- **Fix:** pass `--pak="${PAK_NAME}"` (verified: `--pak=-x` parses, rc 0),
  and map 2 to 3 only when the gate's own verdict line (`Refused by
  RULE-012`) is in its output, otherwise exit 4. Alternatively give
  `defect-gate` a blocked code argparse cannot emit.

### W2. (pre-existing) set -e trap in the dist/ informational block kills the guard before the RULE-012 gate

- **Where:** `scripts/version_line_guard.sh:213`,
  `ADAPTER_KIND="$(grep -E '^adapter_kind:' ... | head -n1 | sed ...)"` under
  `set -euo pipefail`.
- **Authority:** RULE-012 (`knowledge/rules/release-gate-defects.md`).
- **Evidence:** with `<factory>/dist/` present (the real factory has one) and
  a working-tree adapter.yaml without a column-0 `adapter_kind:`, the grep
  miss fails the pipeline, the guard exits 1, the hook allows. Reproduced
  with an open blocking defect naming the pak: the 1.x tag was pushed. An
  informational warning block is able to cancel the release gate.
- **Exposure today:** none observed; all six registered adapters carry
  `adapter_kind:` at column 0. Latent.
- **Fix:** `|| true` on that assignment (the value is already treated as
  optional).

### W3. (pre-existing) Single-quoted version bypasses RULE-014

- **Where:** `scripts/version_line_guard.sh:159`; the sed strips `"` only.
- **Authority:** RULE-014.
- **Evidence:** tag on a commit with `version: '0.5.0'` parses as `'0.5.0'`,
  fails `^0(\.|$)`, and was pushed (exit 0). Valid YAML.
- **Fix:** strip `'` as well as `"` in the sed (`["']?` on both sides).

### W4. No automated coverage of the guard, the hook, or the bootstrap state rendering

- **Where:** `tests/` (no test references `version_line_guard.sh`,
  `.githooks/pre-push`, or the bootstrap `repo_state` case arms).
- **Authority:** framework-reviewer dimension 10; B1 passed the full
  1454-test suite.
- **Fix:** a pytest that builds this review's fixture (tmp pak repo with 0.x
  and 1.x commits, a tag on a commit with no adapter.yaml, bare remote,
  `core.hooksPath`) and asserts the refusal matrix above via real
  `git push`, including both B1 orderings, missing interpreter, and gate
  exit 1.

### W5. (pre-existing in PR #151, not ced4cf0) Hook swallows the guard's output on success, so "absent registry warns" never reaches the operator

- **Where:** `.githooks/pre-push:78`, `0) exit 0` without printing `$out`.
- **Authority:** `knowledge/rules/release-gate-defects.md`: "an absent
  registry ... warns and allows the push" and "Gating nothing is reported;
  it is not treated as a clean bill of health."
- **Evidence:** registry removed; the gate prints `WARNING: no defect
  registry at ... vacuously passes` and exits 0; the push output shows only
  `* [new tag]`. The dist/ informational warning is swallowed the same way.
- **Fix:** on exit 0, print `$out` to stderr when it contains `WARNING`.

## NIT

- **N1.** `version_line_guard.sh:133`: stdin containing only deletion lines
  exits 1 ("no tag given ... Nothing to guard"), a usage-error code, though
  the header says deletions are ignored. Unreachable via the hook (it filters
  first); visible to by-hand or CI callers. Exit 0 when lines were read but
  all were deletions.
- **N2.** A fresh bootstrap record with `unknown=fixturepak` produces an empty
  doctor report (`bootstrap_report_lines` returned `[]`), so Unknown clones
  are invisible in the session report. This is the declared deferral; issue
  #152 is open. It should land before a user relies on "report by exception"
  to surface a detached pak.

## If shipped as-is

A `git push --tags` from a pak clone that carries any v* tag on a commit
without adapter.yaml pushes 0.x tags straight past the guard, reproducing
the vcommunity-vsphere 0.0.0.12 release the guard exists to prevent, while
the hook tells the operator only that it "could not run".
