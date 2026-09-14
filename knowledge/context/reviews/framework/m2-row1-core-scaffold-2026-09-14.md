# Framework review: M2 row 1, vcfcf_core scaffold

Date: 2026-09-14. Reviewer: framework-reviewer. Branch
`feat/m2-row1-core-scaffold` (six commits over main `127d392`, head
`52318df`). Design: `knowledge/designs/tooling-core-carveout-v1.md` row 1,
as amended on the branch for the three deferred modules.

Verdict: **APPROVE** (zero BLOCKING). Three WARNINGs and seven NITs, all to
be fixed before the PR opens per CLAUDE.md step 9.

## What changed

- New package `src/vcfcf_core/` with seven modules moved from the factory
  (`alerts/loader`, `alerts/render`, `dashboards/yaml_utils`,
  `packaging/release_types`, `packaging/template_version`,
  `supermetrics/crossref`, `symptoms/loader`) plus an empty `reports/`
  subpackage. Old paths are `from vcfcf_core.x import *` shims.
- `buildkit.py` copies the moved modules from `vcfcf_core` and rewrites the
  two `vcfcf_core.*` imports in `alerts_render.py` to flat kit names.
- `pyproject.toml` becomes the `vcf-cf-tooling-core` library metadata
  (explicit `packages` list, setuptools-scm from `core-v*` tags).
- `tests/test_core_contract.py` (43 cases): dynamic import from an empty
  cwd and env, AST checks for six forbidden classes, self-check samples.
- `publish-core.yml` (wheel on `core-v*` tags), a PR-time wheel gate in
  `ci.yml`, `version_line_guard.sh` exits 0 on a push with no `v*` tag,
  `.gitignore` adds `build/`.

## Checks re-run (independently)

| Check | Result |
|---|---|
| Byte identity of the seven moved modules vs main `127d392` | Identical, apart from the two rewritten imports in `alerts/render.py` (lines 65-66) |
| Full test suite (`-n auto --dist=loadgroup -m ""`) | 1812 passed, 7 skipped, 89 s |
| Validate chain (supermetrics, customgroups, dashboards, symptoms, alerts, reports, packaging, managementpacks) | all clean |
| `scripts/path_reference_audit.sh` | clear (six standing RULE-015 exceptions, pre-existing) |
| Import graph of `vcfcf_core` with only `vcfcf_core` on `PYTHONPATH` (factory absent), all 13 modules walked | no non-core `vcfcf_*` loaded, no `requests`, only `yaml` third-party |
| Old-path resolution, including `_symptom_id` from `sdk_builder.py:1771` | resolves |
| Wheel from a scratch clone tagged `core-v0.0.9` | `vcf_cf_tooling_core-0.0.9-py3-none-any.whl`, 19 members, only `vcfcf_core/` + dist-info |
| Wheel into a clean venv, `env -i`, cwd `/tmp`, no PYTHONPATH | imports all six modules, `__version__ == 0.0.9`, `import vcfcf_common` raises ImportError, `pip list` shows only PyYAML + the library |
| Version with no `core-v*` tag on the clone | `0.0.1.dev576+g52318df6a` (PEP 440 dev, as the pyproject comment says) |
| Version from a `git archive` export (no `.git`) | `0.0.0` (`fallback_version`) |
| `tag_regex` / `--match core-v*` vs `v*` and `sdk-buildkit-v*` | anchored `^core-v`; existing `sdk-buildkit-v1.0.x` tags in the clone did not influence the version |
| `publish-core.yml` tag filter `core-v[0-9]+.[0-9]+.[0-9]+` | cannot match `v0.1.0`, `sdk-buildkit-v1.2.3`, `core-v1.2`, or `core-v0.1.0-rc1` |
| Ancestor-of-main check | `git merge-base --is-ancestor` accepts an annotated tag object SHA (peels to the commit); `fetch-depth: 0` plus `git fetch origin main` is correct |
| `version_line_guard.sh --tag core-v0.1.0` and `--tag sdk-buildkit-v1.0.0` | exit 0, no defect-gate invocation; `--tag v1.0.0` still runs the gate (exit 1 here, no adapter.yaml) |
| Both workflows parse as YAML | ok |
| `check_framework_review.sh` regex `^src/(vcfcf|vcfops)_[^/]+/` | covers `src/vcfcf_core/` |
| sdk buildkit assembled on branch vs at main (same reference pak) | 75/75 members, zero content differences (17 top-level `.py`) |
| Bundle zips (`build --all --no-live-describe`) on branch vs at main | member sets identical; only `vcfops_manifest.json` (`built_at`) differs; nested `Dashboard.zip` / `Views.zip` / `Reports.zip` bytes differ by entry mtime only, contents identical |
| Scratch tag `core-v0.0.9` | deleted after the test; never pushed |
| Factory still non-installable in the old sense | yes: `pip install` of the wheel lands only `vcfcf_core`; `vcfcf_common` is absent from site-packages |

## Findings

### WARNING

1. **`.github/workflows/publish-core.yml:53-55, 88-93`** (design
   §Gates: "wheel attached to a GitHub Release"). `python -m build`
   produces an sdist as well as the wheel, and the release step uploads
   `dist/*`. Because setuptools-scm registers a git file finder, the sdist
   built from the scratch clone holds **1290 files, 5.2 MB**: `knowledge/`
   (643), `src/` (247, all eleven packages), `content/`, `tests/`,
   `.claude/`, `reference/`, `memory/`, `.env.example`. The workflow's
   "wheel carries files outside vcfcf_core" check only inspects the wheel,
   so the release would ship an unchecked tarball of the whole factory under
   the library's name. Nothing secret (the repo is public), but it is an
   artifact the design never asked for and the gate reports green next to
   it. Fix: `python -m build --wheel` and upload `dist/*.whl` only; or keep
   the sdist and add `[tool.setuptools_scm] ... ` file-finder exclusion via
   `MANIFEST.in` pruning, which is more to maintain for no consumer.

2. **`pyproject.toml:63-72`** (packages list drift). The explicit
   `packages` list is the only thing deciding what enters the wheel, and
   nothing tests it. Proven: adding `src/vcfcf_core/newsub/{__init__,mod}.py`
   to the scratch clone and rebuilding produced a wheel with **no `newsub`**
   and no warning. Both CI gates check only for *extra* files, so row 2's
   new subpackages could ship missing and the first signal would be the
   migrator's ImportError. Fix (smallest): replace the list with
   `[tool.setuptools.packages.find] where = ["src"]
   include = ["vcfcf_core*"]`, which keeps the "nothing else from src/"
   property the comment cares about; or add a test asserting the list
   equals the discovered `vcfcf_core*` packages.

3. **`src/vcfcf_alerts/loader.py`, `src/vcfcf_alerts/render.py`,
   `src/vcfcf_symptoms/loader.py`, `src/vcfcf_dashboards/yaml_utils.py`,
   `src/vcfcf_packaging/release_types.py`,
   `src/vcfcf_supermetrics/crossref.py`** (design §What moves: "a one-line
   re-export in the old location so every factory import keeps working
   unchanged"). Six of the seven shims export a subset. `import *` drops
   every underscore name where the source has no `__all__`, and in
   `crossref` drops everything outside `__all__`: 35 names in total, e.g.
   `vcfcf_symptoms.loader._condition_to_wire` (named in
   `tests/test_symptom_condition_instanced_attribute.py:6`, and it no
   longer resolves), `_strict_load`, `_UUID_RE`, `release_types._SOURCE_TO_DIST`,
   `_UNSUPPORTED_V1`, `_third_party_subdir`, `render._slug`, `_alert_id`,
   `_rec_key`, `yaml_utils._StrictKeyLoader`. No live caller in this tree
   uses one today (the suite and both output comparisons prove it, and
   `_symptom_id` was handled by hand), but the shim advertises "re-exports
   it" and delivers less, and a monkeypatch on the old path would patch the
   shim namespace rather than the module the factory runs. Fix: alias the
   module object instead of copying names:
   `import sys, vcfcf_core.symptoms.loader as _m; sys.modules[__name__] = _m`
   (one pattern for all seven, including the `_symptom_id` special case).

### NIT

4. **`tests/test_core_contract.py:75-85`** (dynamic half). The subprocess
   gets `PYTHONPATH=src`, so the whole factory is importable and the
   "imports with no factory" property is carried by the static half alone.
   Copying `src/vcfcf_core` to a temp dir and pointing `PYTHONPATH` at that
   copy (what this review did by hand) would make the dynamic half prove
   isolation too, and would catch a leak via `importlib.import_module("vcfcf_common")`
   that the AST check cannot see.

5. **`tests/test_core_contract.py:150-190`** (static half gaps, checked
   against the checker directly). Not caught: `os.path.dirname(os.path.dirname(__file__))`,
   `import os as o; o.environ`, `HERE.joinpath('..', 'content')`, and a
   default of exactly `'content'` or `'knowledge'` (the prefix list requires
   the trailing slash and the exact set lacks both). Rows 2 and 3 move the
   modules that use these spellings; worth widening before they land.

6. **`.github/workflows/ci.yml:108-122`** (PR-time gate). The step builds
   the wheel but never installs or imports it; the first install+import is
   in `publish-core.yml` at tag time, after merge. A dropped subpackage
   (finding 2) would pass this gate. Add, after the contents check:
   `python3 -m pip install --user --break-system-packages --target "$RUNNER_TEMP/site" "$RUNNER_TEMP"/wheel/*.whl`
   then `cd "$RUNNER_TEMP" && PYTHONPATH="$RUNNER_TEMP/site" python3 -c "import vcfcf_core.supermetrics.crossref"`
   (a `--target` install avoids the venv traps documented at ci.yml:49-75).
   Ordering after pytest is acceptable; before pytest would fail fast on a
   packaging error and save the 90 s suite, either is fine. The
   `--user --break-system-packages build` install is consistent with the
   dependency step on the same ephemeral pod and is acceptable.

7. **`src/vcfcf_core/__init__.py:14-15` and `pyproject.toml:33-35`**
   (documented `0.0.0+src` from the tree). `python -m build` leaves
   `src/vcf_cf_tooling_core.egg-info/` behind (gitignored, and already
   present in this worktree). With that residue on `PYTHONPATH=src`,
   `importlib.metadata` finds it and the tree reports `0.0.1.dev576+g52318df6a`,
   not `0.0.0+src`. The suite passed with the residue present, so no
   behavior hangs on it; the docstring should say "when no distribution
   metadata is visible", or the CI wheel step should remove the egg-info
   after building.

8. **`src/vcfcf_managementpacks/buildkit.py:19-23, 42`** (rule 7, no
   em-dashes). Five edited docstring lines keep an em-dash. The alignment
   argument does not survive a one-for-one swap to `:` (same width), so the
   block can be fixed without breaking alignment. The 23 em-dashes inside
   the moved modules were moved verbatim to keep the byte-identity proof;
   leaving those for a separate sweep is reasonable, but they are now debt
   in a package that will be published on its own.

9. **`pyproject.toml:46`** `license = { text = "MIT" }` emits a
   `SetuptoolsDeprecationWarning` on every build. `license = "MIT"` needs
   `setuptools>=77` in `[build-system].requires`; low priority.

10. **Docs still say "ten vcfcf_* packages"**: `tests/README.md:17`,
    `.github/workflows/ci.yml:23`, `scripts/check_framework_review.sh:34`
    (pyproject now says "the other ten"). Orchestrator-owned sweep; there
    are eleven directories now and `vcfcf_core` is mentioned nowhere outside
    the design.

## Claims verified as stated

- Byte identity, old-path resolution including `_symptom_id`, contract
  test size (14 dynamic + 14 static + 1 allowlist + 13 samples + 1 clean =
  43) and its empty cwd/env subprocess, wheel contents and clean-venv
  import, `core-v*`-only versioning with the documented dev and archive
  fallbacks, factory non-installability, kit 17/17 (75/75 members
  identical), zips identical apart from `built_at`, suite 1812, path audit
  clear, guard exit 0 without the defect gate, workflow YAML validity, tag
  filter exclusivity, ancestor check.
- The three deferred modules do import row-3 loaders at module level:
  `vcfcf_reports/render.py:22` (`.loader`), `vcfcf_supermetrics/reverse.py:31`
  (`.loader`), `vcfcf_packaging/deps.py:27` (`.loader`). Deferral is
  correct.
- `git log --follow` reaches the pre-move history of each moved module
  (7 to 12 commits), so the move is followable.

## If shipped as-is

The factory behaves identically (proven by kit and zip comparison). The
first `core-v0.1.0` tag would publish a correct 31 KB wheel next to a 5 MB
sdist of the entire repo, and any subpackage added in row 2 without a
`pyproject.toml` edit would ship silently missing until the migrator failed
to import it.

## Round 2 (2026-09-14, head `77c3caf`: `0a01da2` + `03a2485` merged, nine commits over main)

Verdict: **APPROVE**. 0 BLOCKING / 0 WARNING / 1 NIT (cosmetic, optional).
All ten round-1 findings are closed; each closure was verified
independently, not from the commit message.

| Round 1 finding | Claimed closure | Verified |
|---|---|---|
| W1 sdist of the whole repo published | `python -m build --wheel`, upload `dist/*.whl` | publish-core.yml:54-57 and 90-93 read as claimed; the only artifact glob is `*.whl` |
| W2 packages list drift | `[tool.setuptools.packages.find] where=["src"] include=["vcfcf_core*"]` + test | pyproject.toml:69-73; `test_packages_find_matches_every_core_package_on_disk` compares the find result to a walk of `__init__.py` files. Re-ran the drift proof in the scratch clone: an added `vcfcf_core/newsub/` now lands in the wheel |
| W3 shims drop 35 names | all seven are `sys.modules[__name__] = _m` aliases; `tests/test_core_shims.py` | Old path `is` core module for all seven; `_condition_to_wire`, `_symptom_id`, `_SOURCE_TO_DIST`, `_StrictKeyLoader` resolve through the old paths; a monkeypatch on the old path is visible on the core module. 11 shim cases pass |
| N1 dynamic half ran with the factory on the path | temp copy of `src/vcfcf_core` only, probe proves the factory absent | test_core_contract.py:93-121: probe imports `vcfcf_common`/`vcfcf_packaging`/`vcfcf_supermetrics` and fails if any resolves, then asserts no non-core `vcfcf_*` in `sys.modules` after the import |
| N2 static gaps | six new self-check samples | `import os as <alias>` tracked, nested `os.path.dirname`, `.joinpath("..")`, exact `content`/`knowledge` defaults; the clean-module sample was widened so `os.path.dirname(__file__)` alone, `joinpath('templates')`, and `'contents'`/`'knowledgeable'` defaults still pass |
| N3 PR gate never imported the wheel | `pip install --target "$RUNNER_TEMP/site"`, import from `$RUNNER_TEMP` with `PYTHONPATH` set to the site dir | Simulated locally with the round-2 wheel: imports from the target dir, `__version__` 0.0.9, no factory module in `sys.modules`, `import vcfcf_common` raises. The line has no `--break-system-packages`; that is correct: pip's install command runs the externally-managed check only when `target_dir is None` (pip 24.0 `install.py:278`), and the same command succeeded on this host, which carries `/usr/lib/python3.12/EXTERNALLY-MANAGED`. The trailing `rm -rf src/*.egg-info build` also closes the residue half of N4 on the runner |
| N4 `0.0.0+src` wording | corrected in `vcfcf_core/__init__.py` and pyproject | Docstring now describes the dev, archive, and egg-info-residue cases accurately |
| N5 em-dashes on touched buildkit lines | swapped for colons | The five lines now carry `:`; zero em-dashes in any line added since round 1; kit re-assembled and compared to main: 75/75 members, zero content differences |
| N6 license form | kept, reason noted | pyproject.toml:43-45 records setuptools 68.1.2 as the reason |
| N7 docs | `tests/README.md`, `ci.yml` comment, `check_framework_review.sh` comment, `STRUCTURE.md` | all four name `vcfcf_core` |

Checks re-run at `77c3caf`: full suite **1829 passed, 7 skipped** (74 s);
`tests/test_core_shims.py` + `tests/test_core_contract.py` 60 passed;
wheel from the scratch clone tagged `core-v0.0.9` is 19 members, only
`vcfcf_core/` + dist-info (tag deleted afterwards, never pushed); both
workflows parse as YAML; bundle zips rebuilt and content-identical to main
apart from `vcfops_manifest.json`; sdk buildkit 75/75 identical to main;
no em-dashes in lines added since round 1.

### NIT (optional)

- `src/vcfcf_managementpacks/buildkit.py:16-24, 42-44`: the docstring
  block now mixes five `:` separators with the surrounding em-dash lines
  that were not touched. Rule 7 is satisfied on every changed line; sweeping
  the rest of the block to `:` in the same commit would be tidier and is a
  one-for-one width swap, but it is not required for this PR.

### If shipped as-is

Factory output is identical to main; the first `core-v0.1.0` tag publishes
a 31 KB wheel and nothing else; a subpackage added in row 2 enters the
wheel automatically and the contract test fails loudly if discovery and
disk ever disagree.
