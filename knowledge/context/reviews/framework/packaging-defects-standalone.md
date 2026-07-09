# Framework review — `vcfops_packaging/defects.py` standalone entrypoint

- **Branch:** `feat/p2-pak-ci-defect-gate`
- **Date:** 2026-06-13
- **Reviewer:** `framework-reviewer` (RULE-013 gate, pre-PR)
- **Design of record:** `knowledge/designs/defect-gate-pak-ci-v1.md`
- **Diff reviewed:** `git diff main -- vcfops_packaging/defects.py tests/test_defect_gate.py`
- **Verdict:** APPROVE (0 BLOCKING / 0 WARNING / 2 NIT)

## What changed

Adds an `if __name__ == "__main__":` argparse block to `vcfops_packaging/defects.py`
(`--pak NAME` / `--all`, mutually-exclusive required; `--registry PATH`
default = `Path(__file__).parent / "defects.md"`). It reuses the existing
`gate_pak` / `gate_all` / `format_defect_line` / `DefectRegistryError`
defined above in the same file. Exit codes 0 (clean) / 1 (bad or missing
registry) / 2 (open blocking defects). Goal: a pak repo's `v*`-tag CI can
`curl` this one file + `knowledge/context/defects.md` from factory `main` and run
the defect gate with no factory checkout and no `pip install`. Plus 6
subprocess-based tests in `tests/test_defect_gate.py::TestStandaloneEntrypoint`.

No existing function touched. `vcfops_packaging/cli.py` (`cmd_defect_gate`)
and `vcfops_packaging/publish.py` (`_gate_publish`) are byte-identical to
`main` (confirmed: empty diff).

## Checks re-run (independently)

| Check | Result |
|---|---|
| validate chain (all 8 packages) | **pass** (SM/dashboards/customgroups/symptoms/alerts/reports/MP/packaging all OK) |
| `tests/test_defect_gate.py` | **46 passed** (incl. 6 new standalone tests) |
| full `tests/` suite | **321 passed, 4 skipped, 162 deselected** (skips/deselects/warnings pre-existing, unrelated) |
| render-regression | n/a — no renderer/builder/template touched |
| pak-compare | n/a — no builder/pak shape touched |

## Dimension walk

1. **Global-default / pak-specific leak (anchor `00d3382`)** — PASS. The new
   code is entirely inside the `__name__ == "__main__"` guard (AST-confirmed:
   the only module-level imports are `__future__`, `re`, `dataclasses`,
   `pathlib`, `typing`; `argparse`/`sys` are imported *inside* the guard).
   `import vcfops_packaging.defects` exits 0 with no argparse trigger and the
   full public API present. No default leaks onto the package/import path.

2. **Key / label derivation collisions (anchor `6c59f6b`)** — n/a. No key or
   label derivation in this change.

3. **Wire-format conformance** — n/a. Emits human CLI text + exit codes, not
   wire JSON/XML. Output strings are byte-identical to the package CLI (below).

4. **Loader / validator correctness** — PASS. The standalone delegates to the
   unchanged `gate_pak`/`gate_all`/`load_registry`; no resolution logic
   re-implemented.

5. **Render regression vs known-good** — n/a (no renderer touched).

6. **Builder / pak structure** — n/a (no builder/template touched;
   `pak-compare` not applicable).

7. **Corpus regression** — PASS. Full validate chain green; full test suite
   green over the existing corpus.

8. **Silent capability change / downgrade** — PASS. Pure addition; the package
   import path and `python3 -m vcfops_packaging defect-gate` are unchanged.

9. **Stale-zip discipline** — n/a. Change does NOT touch
   `vcfops_packaging/templates/`, `vcfops_packaging/builder.py`, or
   `vcfops_dashboards/render.py`. No `content-packager` rebuild implied.

10. **Test coverage of the change** — PASS. Six subprocess tests cover
    --pak (blocked & clean), --all, missing registry, and the load-bearing
    bare-copy-in-temp-dir contract.

## Independent verification of the load-bearing claims

**Claim 1 — `__main__` block unreachable on import / package path unchanged.**
Verified by AST (guard imports isolated) and by importing the module (exit 0,
no argparse run, public API intact). `cli.py`/`publish.py` empty diff vs main.

**Claim 2 — pure stdlib, no third-party imports.** Verified by AST: module-level
imports `re`/`dataclasses`/`pathlib`/`typing`/`__future__`; guarded imports
`argparse`/`sys`. All stdlib. The no-pip-install premise holds.

**Claim 3 — standalone exit codes/output match the package CLI.** Ran both for
synology / compliance / --all / unifi. stdout and exit codes are **byte-for-byte
identical** across all four modes (synology→2/DEF-001, compliance→0, --all→2/
DEF-001+DEF-002, unifi→2/DEF-002).

**Claim 4 — bare-copy contract.** Copied `defects.py` + `defects.md` to a fresh
temp dir, confirmed `import vcfops_packaging` *fails* there (true bare copy),
then ran the script from that dir with a clean cwd: identical output/exit to the
in-package run. Held under hardened isolation (`python3 -P`, stripped
`PYTHONPATH`). Confirmed the default `--registry` resolves to the script-sibling
`defects.md` even when cwd ≠ script dir (the design's `curl both into one dir`
flow). Malformed registry → exit 1 with a clear stderr message; missing registry
→ exit 1. These match `cmd_defect_gate`'s `FileNotFoundError`/`DefectRegistryError`
→ exit 1 contract.

## NITs (non-blocking)

- **N1 — argparse usage errors exit 2, colliding with the "blocking defects
  found" code.** `python3 defects.py` (no mode) and `--pak x --all` both exit
  **2** via argparse's native required/mutually-exclusive group handling — the
  same code the contract reserves for "open blocking defects found." In CI any
  non-zero fails the build, so this is harmless to the gate's purpose, but a CI
  log reader can't distinguish "defect found" from "I mis-invoked the script"
  by exit code alone. The package CLI returns 1 for its own mode-validation
  errors. If diagnostics matter, catch `SystemExit` from `parse_args` (or
  pre-validate) and re-exit 1. Cosmetic only.

- **N2 — `--registry` default is `Path(__file__).parent / "defects.md"`, while
  the package CLI default is `knowledge/context/defects.md` relative to repo root.** This
  is intentional and correct for the curl-and-run model (file + registry land
  in the same dir), and is documented in the block comment. Noted only so a
  future reader doesn't mistake the two defaults for a parity bug — they serve
  two different execution contexts. No change needed.

## Scope note

The branch also contains non-`vcfops_*` files (`knowledge/designs/sdk-template-scaffold/
build-pak-on-tag.yml`, README, `knowledge/context/managed_paks.md`, `session-handoff.md`,
`knowledge/lessons/INDEX.md`). Per the design's boundary section those are the
orchestrator's / sdk-adapter-author's surface, not `tooling`'s — outside this
reviewer's `vcfops_*/` mandate and not reviewed here.

## If shipped as-is

A pak repo's `v*`-tag CI can `curl` `defects.py` + `defects.md` from factory
main and run the gate with no checkout and no pip install; it refuses releases
of synology/unifi (DEF-001/DEF-002 open) and passes compliance — identical to
the package CLI. No regression on the package import path or `python3 -m
vcfops_packaging defect-gate`.
