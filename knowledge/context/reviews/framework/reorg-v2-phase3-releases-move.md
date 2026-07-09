# Framework Review — reorg-v2 Phase 3: releases/ -> bundles/releases/

- **Branch:** `chore/reorg-v2-design-closeout`
- **Commit:** `7ccf8d5` (diff range `1cd6f61..HEAD`)
- **Area:** `src/vcfops_packaging/` (cli, releases, composer, publish, readme_gen, release_builder)
- **Reviewer:** framework-reviewer (RULE-013 blanket gate)
- **Date:** 2026-07-09
- **Verdict:** APPROVE (0 BLOCKING)

## Change summary

`releases/` moved to `bundles/releases/`; `diagrams/` moved to
`knowledge/diagrams/`; repo-wide citation sweep. Functional src delta:
- `releases.py`: default `releases_dir` `"releases"` -> `"bundles/releases"`;
  `repo_root` auto-resolution `path.parent.parent` -> `path.parent.parent.parent`.
- `cli.py`: `releases_dir` constants x3; deprecates-string writer x2;
  `bundles_dir.rglob` -> `glob` at cmd_build --all / cmd_validate / cmd_list.
- `composer.py`, `publish.py`, `readme_gen.py`, `release_builder.py`: path
  relocation + docstring/comment updates.

## Independent verification

### 1. Every src hunk accounted for
Diffed all six touched src files. Every changed line is one of: (a) a
`releases/` -> `bundles/releases/` path relocation, (b) the documented
`rglob`->`glob` fix, or (c) comment/docstring text. **Nothing else smuggled
in.** No wire-format emission (template.json / describe.xml / rendered JSON)
is touched by this change — it is pure path plumbing.

### 2. rglob -> glob fix — CORRECT and NECESSARY
`find bundles -type d` shows exactly one subdirectory: `bundles/releases/`.
Before the move, `bundles/` had no subdirs, so `rglob`==`glob` in practice.
After the move, `rglob("*.y*ml")` would descend into `bundles/releases/` and
misclassify all 10 release manifests as flat bundles. Non-recursive `glob`
is the right fix. Confirmed consistent at all three call sites
(cmd_build --all L40, cmd_validate L160, cmd_list L271). Verified live:
`vcfops_packaging list` returns only the 2 top-level bundles
(storage-path-monitoring, vks-core-consumption-bundle), NOT the 10 releases.
No legitimate nested bundle manifests exist that `glob` would now miss.

### 3. repo_root off-by-one — CORRECT
For `bundles/releases/<slug>.yaml`: parent=`bundles/releases`,
parent=`bundles`, parent=repo_root. Three `.parent` hops is right.
Proven end-to-end: `vcfops_packaging validate` loaded all 10 manifests and
resolved every `source:` path (content/dashboards/..., content/sdk-adapters/...,
bundles/...) with no path errors — which only succeeds if repo_root resolves
correctly. Checked all `load_release` callers that rely on the defaulted
repo_root (readme_gen L803, publish L954, release_builder L372): each
receives either an absolute manifest path or a repo-root-relative
`bundles/releases/...` path, both of which three-up resolves correctly.
No caller passes an explicit path that is now double-prefixed.

### 4. Vendor-URL exclusion — CLEAN (phase-2 lesson honored)
`git diff | grep -E '(releases/latest|/releases/tag/|/releases/download/)'`
returns zero changed lines. The GitHub URL constructors in
`managed_paks.py` (`<remote>/releases/latest`, api.github.com .../releases/latest)
and `readme_gen.py` / `release_builder.py` download-link text are untouched.
The sweep correctly distinguished filesystem `releases/` from vendor URL
`releases/`.

### 5. Gates re-run
- Path audit / structure: `bundles/releases/` holds all 10 manifests; no
  stragglers left in a top-level `releases/`.
- validate x7 content validators: **all OK**.
- `vcfops_packaging validate`: 10 release manifests valid, flag-state clean,
  no bundle/release slug collision, 1 third-party PROJECT valid.
- `pytest -q` (full): **468 passed, 4 skipped, 162 deselected**.
- `pytest test_cli_phase4.py test_publish_phase3.py -m slow`: **49 passed**
  (11m20s) — exercises the moved release/publish surface end-to-end.
- `defect-gate --pak synology`: no open blocking defects.

### 6. Fail-open hunt — no new silent degradation
Each new constant guards missing/empty `bundles/releases/` exactly as the
old code guarded missing `releases/`:
- cmd_validate: `if not releases_dir.exists(): return rc` (graceful no-op,
  unchanged semantics).
- publish `_enumerate_releases`: `if not releases_dir.exists(): return []`
  (graceful, unchanged).
- composer collision check: existence-only, fine.
The graceful-no-op-on-missing behavior is pre-existing design, not introduced
here, and the directory demonstrably exists with all 10 manifests. No new
fail-open path.

### 7. Rename integrity + enumeration
`git diff -M --summary`: 9 release manifests R100, 1
(unifi-controller-managementpack.yaml) at 93% — the sole content change is a
single legitimate citation line inside `deprecates:`
(`releases/...` -> `bundles/releases/...`), consistent with the deprecates
writer change. Diagrams all R100. `/publish` enumeration
(`publish.py:_enumerate_releases`, exercised by the slow publish suite) and
`load_all_releases` both see all 10.

## Findings

None. Zero BLOCKING, zero WARNING, zero NIT.

Note (informational, out of src/vcfops_* scope): `scripts/excalidraw_to_svg.py`
also updated for the diagrams move — not part of the review surface, harmless.

## If shipped as-is

An operator sees no behavior change: `list`, `validate`, `build`, `/publish`,
and `/release` all operate on the relocated `bundles/releases/` transparently,
all 10 releases enumerate, no vendor download link regresses, and the
`rglob`->`glob` fix prevents the newly-nested release manifests from being
mis-run as flat bundles.
