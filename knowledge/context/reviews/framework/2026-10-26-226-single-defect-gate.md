# Framework review: #226 single defect gate (generated vendored copy)

- **Branch:** `fix/226-single-defect-gate` @ `dac2f8e`, diffed against `main`
- **Area:** `src/vcfcf_packaging/defects.py`, `src/vcfcf_packaging/cli.py`
  (plus `tests/test_defect_gate_parity.py`, `knowledge/context/tier2_architecture.md`)
- **Date:** 2026-10-26
- **Verdict:** CHANGES REQUESTED (2 BLOCKING / 2 WARNING / 4 NIT)

## Change under review

`defects.py` gains `vendored_gate_text()` / `verify_vendored_text()` and a
`_STANDALONE_REQUIRE_REGISTRY` constant that feeds the script entrypoint's
`--require-registry` default. The new `vendor-defect-gate --out/--check` CLI
writes or checks a pak repo's `ci/defect_gate.py`: a `#` header with
source and body SHA-256, then the module with that one constant flipped to
`True`. The script gains `--verify-vendored [--against DEFECTS_PY]`.

## Checks re-run

| Check | Result |
|---|---|
| 7-package validate chain | all exit 0 |
| Full pytest (`-n auto --dist=loadgroup -m ""`) | 2839 passed, 12 failed, 9 skipped |
| Same 12 on a `git archive main` tree | the same 12 fail on main. That is 12, not the 6 the brief named: `test_publish_phase3`, `test_third_party_component_routing_phase5` (2), `test_third_party_routing` (2) and `test_discrete_builder_builtin_metric_enables` fail too, all on the real-corpus `vcfcf_packaging validate` / `--strict-deps`. Not caused by this branch |
| `test_defect_gate_parity.py` + `test_defect_affects_single_token.py` | 210 passed |
| Generated copy vs module | `diff` shows exactly one changed line (`_STANDALONE_REQUIRE_REGISTRY = True`) under a 15-line `#` header |
| Factory callers, main vs branch | byte-identical stdout, stderr and exit across 9 registries x 3 paks for script mode, script `--require-registry`, and `defect-gate --pak` on the shipped registry for 5 paks |
| Template's own `tests/ci/test_defect_gate.py` against the generated copy | 34 subtest failures. Every one is a 1-to-2 exit change or a library `DefectRegistryError` the factory no longer raises. None is a refusal turned into a pass. That file does not exercise the cases in B1 |

### Standalone run (pak CI shape)

The pak CI gate step runs **before** `setup-python` on `ubuntu-latest`, so it
uses the image's system `python3` (3.12). The generated copy was run from an
empty directory with `python3 -I`, under `-W error`, on 3.12.3 and 3.14.3,
using the CI's exact `--pak NAME --registry defects.md`:

- live registry: 0
- open blocker: 2
- missing registry: 1
- `--all`: 2
- `--verify-vendored`: 0

Nothing was written to the cwd. `ast.parse` accepts it at feature_version 3.6
through 3.9. The only imports are stdlib (`hashlib`, `re`, `sys`,
`dataclasses`, `pathlib`, `typing`, `argparse`). The one package import,
`from .managed_paks import`, is inside `try/except Exception` and degrades
to the documented warning. **Standalone: confirmed.**

### Gate matrix: generated copy vs module vs the gates pak CI runs today

`tmpl` is the template's `ci/defect_gate.py` @ `49ab82c`. `compl` is the
`ci/defect_gate.py` compliance runs today. Each cell is the exit code for
`--pak compliance`.

| Registry | gen | module | tmpl | compl |
|---|---|---|---|---|
| live factory registry | 0 | 0 | 0 | 0 |
| empty file | 1 | 0 | 1 | 1 |
| HTML 404 page | 1 | 0 | 1 | 1 |
| missing | 1 | 0 | 1 | 1 |
| valid open blocker on compliance | 2 | 2 | 2 | 2 |
| `- Affects: compliance` (no bold) | **0** | 0 | 1 | 1 |
| `- **Affects** compliance` (colon outside bold) | **0** | 0 | 1 | 1 |
| `**Affects:** compliance` (no dash) | **0** | 0 | 1 | 1 |
| `- **Affect:** compliance` (field name typo) | **0** | 0 | 1 | 1 |
| `- **Affects:**` (empty) | **0** | 0 | 1 | 1 |
| `- **Affects** : compliance` | **0** | 0 | 1 | 1 |
| `### DEF-0O2 compliance broken` with `*` bullets | **0** | 0 | 1 | 1 |
| `- **Affects:** sdk-compliance (build 99)` | **0** | 0 | 1 | — |

The module and the generated copy differ on exactly the three claimed rows:
missing, empty and HTML page. That claim is **confirmed**. The bold rows are
B1.

### Checksum scheme

The experiments are in the scratchpad (`ck.py`). Columns:

- **self:** `--verify-vendored`
- **against:** `--verify-vendored --against <module>`
- **check:** `vendor-defect-gate --check`

| Copy | self | against | check |
|---|---|---|---|
| CRLF line endings | 0 | 0 | 0 |
| CR-only line endings | 0 | 0 | 0 |
| generated from a CRLF `defects.py` | identical bytes | | |
| UTF-8 BOM prepended | 1 | 1 | 1 |
| trailing newline added or removed | 1 | 1 | 1 |
| `_STANDALONE_REQUIRE_REGISTRY` flipped back to `False` | 1 | 1 | 1 |
| **same flip, body sha in the header recomputed** | **0** | 1 | 1 |
| header comment edited | 0 | 1 | 1 |
| shebang prepended | 0 | 1 | 1 |
| fake duplicate body-sha mark | 0 | 1 | 1 |
| hand-vendored pre-#226 gate (all 7 clones) | — | — | FAIL, no header |

The scheme is deterministic across machines and line endings, because
`read_text` applies universal newlines both when hashing and when Python
executes the file. `defects.py` is pure ASCII, with no tabs and no trailing
whitespace, so formatter hooks do not disturb it.

The header can never hide executable code. The header is the run of
`splitlines()` segments that start with `#`. Python's own newlines are a
subset of the `splitlines` separators, so such a segment always starts a
Python comment line.

**Answer to "can `--verify-vendored` pass a copy that gates differently": yes,
without `--against`.** It passes in three cases:

1. A stale copy. The body checksum is unchanged, and this is by design.
2. A body edit with the header checksum recomputed. Demonstrated above:
   `--require-registry` was turned back off and the copy still verified.
3. A copy generated from a locally modified or forked `defects.py`.

The checksum is stored inside the file. It detects accidents; it is not a
seal. Only `--against` the canonical module, or the factory-side `--check`,
catches these three cases. See B2.

## BLOCKING

### B1. The generated copy fails open where the gate it replaces refused

**Where:** `src/vcfcf_packaging/defects.py`, entrypoint `--require-registry`
block, around lines 1597-1608. Same class of problem in `gate_pak` at
around line 1222.

**Authority:**

- `knowledge/rules/release-gate-defects.md`. RULE-012 rationale: per-entry
  isolation exists so that "one sloppy edit must never stop every release
  everywhere". That is an in-repo concern. The pak copy guards a release
  and was explicitly allowed to be stricter.
- Dimension 8, silent capability downgrade.
- The template gate @ `49ab82c`, the known-good reference.

**What regresses:** take a registry entry that was meant to block a pak but
whose `Affects:` line is not readable as a field. Examples are a missing
dash or bold, a colon outside the bold, a field-name typo, an empty value,
or a malformed heading over `*` bullets. The same applies to a malformed
multi-token `Affects:` whose candidates do not include the gated name
(`sdk-compliance (build 99)`).

- **The generated copy:** this entry gates nothing. It prints a stderr
  WARNING and **exits 0**.
- **The template and compliance gates pak CI runs today:** the same registry
  exits 1.

Eight shapes were reproduced; see the bold rows of the matrix above. After
the proposed regeneration, the pak release goes green over a blocker that
was meant to stop it. A stderr warning in a passing CI step is the
reports-green-while-broken class.

The parity test docstring says: "Where the vendored script refused (exit 1)
this gate refuses too (exit 2 for the named pak)". That is false for these
rows, and the parity matrix has no row for them. The template's own test
file does not cover them either, so they slipped through both suites.

Mitigation exists but does not close the hole. Factory CI's
`test_shipped_registry_still_parses_clean` reds a PR that adds such an
entry. Pak CI still reads live `main`, so a direct push or a red merge
reaches every pak's release gate.

**Fix (smallest):** under `--require-registry`, which is always on in the
vendored copy, exit 1 when the registry has any parse error with no
confirmed scope (`not err.scoped`) that did not already block this pak as a
candidate. The message should say the registry names an entry whose target
cannot be read, so the gate refuses every pak. This:

- keeps the generated copy a one-line flip;
- keeps every factory caller unchanged (they never pass the flag);
- changes only the opt-in kit flag in the strict direction.

Add matrix rows and `_VENDORED_EXPECT` entries for at least `u1` (no-bold
Affects), `u5` (empty Affects) and `c1` (candidate-only, other name), plus a
default-mode row showing the factory module still exits 0. Note that
`b1-prose-unnamed-pak` becomes 1 for the vendored copy. Correct the parity
docstring and the §Defect gate in pak repos paragraph in
`tier2_architecture.md`, which currently says "A malformed entry refuses
(exit 2) every pak it names and no other, in every caller".

### B2. Nothing automatic detects a stale vendored copy

**Where:** `src/vcfcf_packaging/defects.py`, the `--verify-vendored` design
and the generated header's "Pak CI:" lines. Also
`knowledge/context/tier2_architecture.md` §Defect gate in pak repos ("`--against`
... is optional").

**Authority:**

- Issue #226, whose stated risk is that "the two can disagree on the same
  registry".
- Dimension 9, "the signal that announces it": a fix that reaches the
  source while nothing tells the distributed copies they are obsolete is
  BLOCKING.

**What regresses:** the follow-up has pak CI run `--verify-vendored` with no
`--against`. That proves only that the file was not edited since it was
generated, so a copy generated from any older `defects.py` verifies forever.
B1-class parser fixes on factory `main` (the #153, #219 and #226 fixes were
all of this kind) would then never reach a pak's release gate. The factory-side
`vendor-defect-gate --check` would catch it, but no CI job, hook or doctor
runs it, and the pak clones are gitignored, so factory CI cannot.

Pak CI already reads the registry live from factory `main`. Running a pinned
old parser against the newest registry is exactly the co-evolution hazard
#226 is about. The same weakness lets a hand edit with a recomputed header
pass, as demonstrated above.

**Fix:** make `--against` the documented pak CI step, not an option:

1. Resolve one factory commit.
2. Fetch both `knowledge/context/defects.md` and
   `src/vcfcf_packaging/defects.py` at that commit. `defects.py` is read as
   data and never executed, so the "never fetch+execute remote code" rule
   holds.
3. Run `python3 ci/defect_gate.py --verify-vendored --against defects_src.py`
   before the gate.

Update the generated header's "Pak CI:" comment, the tier2 doc and the
follow-up to match. The trade-off is that a `defects.py` change on `main`
blocks pak releases until each repo regenerates, which is one command. If
Scott rejects that coupling, the acceptable minimum is a by-exception doctor
check that runs `--check` over the live (non-retired) registered pak clones.
That decision is the orchestrator's to put to Scott. Today it reads as
"optional", and the outcome is the same silent drift.

## WARNING

### W1. The pak-repo follow-up is incomplete

**Where:** `tier2_architecture.md`, changelog row "Adapter adoption".

**Authority:** the pak workflows under `content/sdk-adapters/*/.github/workflows/build-pak-on-tag.yml`.

The steps are correct in direction, and the repo set is right: compliance,
unifi, synology, and the template. The template matters, or new paks keep
instantiating the hand-vendored gate. The vcommunity trio is retired per
`managed_paks.md` and can be left. The steps are missing four things:

1. **The test step must go when `tests/ci/test_defect_gate.py` is deleted.**
   It is the only file in `tests/ci/` in all four repos. If the
   `python3 -m unittest discover -s tests/ci` step is left behind, it exits
   **5** ("NO TESTS RAN", measured on 3.12) and breaks every tag build. The
   doc says "replace", so make that a hard instruction: delete the step and
   the directory.
2. **The workflow comment block (lines ~90-122) must be rewritten.** It
   currently tells a maintainer to "Re-vendor ci/defect_gate.py from the
   factory" by hand, and says a malformed DEF heading exits 1. Malformed
   scoped entries now exit 2. The inline exit-code comment
   ("1 = bad registry") also needs updating.
3. **The verify step needs the B2 fetch.** It runs before the gate in the
   same job, not in a separately skippable job.
4. **The deletion is only safe once the factory matrix covers the dropped
   cases.** B1 shows the template file plus the factory matrix still leave
   the unscoped shapes untested. Land B1's rows first.

### W2. The buildkit copy gained a flag that can never pass there

**Where:** `defects.py`, `--verify-vendored` in `sdk_buildkit/defect_gate.py`.

**Authority:** `tier2_architecture.md` changelog. Tooling documents the
behaviour, but no test covers the kit side.

The kit header carries no checksums, so `--verify-vendored` on the kit
script always exits 1. It prints "not a vendored copy made by
'python3 -m vcfcf_packaging vendor-defect-gate'; regenerate it", which is
wrong advice for a kit user.

The gating behaviour itself is confirmed identical, through the kit leg of
the parity matrix.

**Fix:** either have the kit header emit the same two checksum marks, which
makes the kit copy self-verifying too, or detect the kit header and say
"buildkit copy; verification applies to a pak's ci/defect_gate.py". Add one
test either way.

## NIT

- **N1. BOM gets the wrong diagnosis** (`defects.py` `_split_vendored`). A
  UTF-8 BOM, which some Windows editors add, makes the copy fail as "no
  generated checksum header" instead of saying a BOM was added. It fails
  closed, but the message misleads. Either strip a leading `﻿` before
  splitting or name it.
- **N2. `--out` into a missing directory tracebacks** (`cli.py`
  `cmd_vendor_defect_gate`). `--out <dir that does not exist>/x.py` raises
  an uncaught `FileNotFoundError`. Print one line and exit 1, as `--check`
  does for an unreadable path.
- **N3. The documented drift-check glob is permanently red**
  (`tier2_architecture.md`). `vendor-defect-gate --check content/sdk-adapters/*/ci/defect_gate.py`
  also matches the three retired vcommunity clones, which will report FAIL
  indefinitely, and permanent red teaches people to ignore the command. Name
  the live paks, or have `--check` with no paths resolve the live managed
  paks.
- **N4. The pre-existing failure count is 12, not 6.** Twelve tests fail
  identically on `main` in this environment. The brief's figure of six is
  out of date, so the handoff should carry the real number. This is not
  caused by this branch.

## Dimensions walked

| # | Dimension | Result |
|---|---|---|
| 1 | Global/pak leak | Clean. `_STANDALONE_REQUIRE_REGISTRY` defaults to `False` in the module and the kit, and factory callers are byte-identical to `main` (measured) |
| 2 | Key collisions | n/a |
| 3 | Wire format | n/a; the registry format is unchanged |
| 4 | Loader correctness | The parser is untouched |
| 5 | Render regression | n/a |
| 6 | Builder | Kit assembly unchanged except for the module content it copies. No `BUILDKIT_VERSION` bump is needed: kits publish by tag, and pak CI does not run the kit gate |
| 7 | Corpus | The validate chain passes, and the tests show no new failures |
| 8 | Silent downgrade | **B1** |
| 9 | Staleness signal | **B2**. Templates, builder, assembly and render are not touched, so no zip rebuild and no `CURRENT_TEMPLATE_VERSION` bump are needed |
| 10 | Tests | Good coverage of the generator and verifier. B1's rows are missing (WARNING folded into B1) |

## If shipped as-is

Once the four pak repos regenerate as proposed, two things go silently
wrong. A defect entry whose `Affects:` line is mistyped lets that pak's tag
build pass where today it fails. And every later factory parser fix stops at
the factory, because pak CI's `--verify-vendored` accepts the old copy
indefinitely.
