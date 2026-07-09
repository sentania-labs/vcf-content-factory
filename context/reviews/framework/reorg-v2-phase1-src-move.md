# Framework Review — reorg-v2 phase 1: vcfops_* → src/

- **Area:** all ten `src/vcfops_*/` packages (move) + `scripts/`, `.github/workflows/`, `pyproject.toml`, `pytest.ini`, `.claude/settings.json`, `tests/`
- **Change:** move the ten `vcfops_*` packages under `src/`, resolve via ambient `PYTHONPATH=src` (settings.json env + workflow job env); no package install anywhere (deliberate — protects kit-isolation tests); nine repo-root `__file__` depth fixes; buildkit `_SRC_ROOT`/`_REPO_ROOT` split; pytest.ini → pyproject `[tool.pytest.ini_options]`.
- **Branch:** chore/reorg-v2-phase1-src (uncommitted working tree vs main)
- **Verdict:** CHANGES REQUESTED
- **Findings:** 1 BLOCKING / 2 WARNING / 2 NIT
- **Date:** 2026-07-08

## Checks re-run (independently)

| Check | Result |
|---|---|
| validate ×7 (bare, ambient `PYTHONPATH=src`) | **PASS** (all 7) |
| validate with PYTHONPATH unset | **fails-closed** (`No module named vcfops_dashboards`) — confirms no site-packages install masks the tests |
| full pytest suite | **468 passed / 4 skipped / 162 deselected / 0 failed** |
| kit-isolation tests (shipped relative env) | **2 passed** — isolation genuine |
| kit-isolation canary under absolute `PYTHONPATH=<repo>/src` | **canary FAILS loudly (CI red)** — still fails-closed |
| build-buildkit assemble + layout | **clean**; all `_FACTORY_SOURCES` resolve, all rewrite rules matched (no stale-rule AssertionError) |
| layout parity vs released `sdk-buildkit-1.0.6` | **identical** (only auto-selected reference-pak version differs — expected) |
| build-sdk synology (end-to-end) | **PASS** — pak produced; `_REPO_ROOT` resolves LICENSE/dist/tmp correctly |
| render-regression | **clean** — `render.py` and all `templates/` byte-identical to main |
| path_reference_audit.sh | **clear** (only pre-existing RULE-015 standing-exception warnings) |
| check_framework_review.sh regex/cut | **correct** (emits all 10 pkgs on this diff; empty on non-src diff) |
| validate-content hook from non-repo cwd, PYTHONPATH unset | **PASS** (injects `FACTORY_ROOT/src` itself) |
| version_line_guard defect-gate standalone from /tmp | **PASS** |

## Path-resolution verification (item 1)

Every `.py` under `src/` was diffed against its `main` counterpart. **Every change is exactly the intended path fix — no stray logic rode along.** The nine repo-root fixes all bump `.parent.parent` → `.parent.parent.parent` (or `_HERE.parent` → `_HERE.parent.parent`), correct for `src/<pkg>/file.py` → repo root. Package-local resolvers were correctly left alone:

- `managementpacks/builder.py` `_HERE` — used only for `templates/` and `adapter_runtime/` (moved with the package); byte-identical to main; **not a miss**.
- `packaging/templates/install.py` `SCRIPT_DIR`, `managementpacks/templates/post-install.py` — pak-runtime templates, resolve inside the installed pak; unaffected by the factory move.
- `loader.py` `_find_repo_root` gained a defensive `or (current / "src" / "vcfops_common").exists()` branch — correct.
- CWD-based resolvers (`cli.py`, `composer.py` `Path.cwd()`, `_env.py`) are byte-identical to main and unaffected (cwd is still repo root at invocation).

No unfixed `__file__`/CWD resolution found.

## buildkit split (item 2)

`_SRC_ROOT = _HERE.parent` (parent of the vcfops_* packages), `_REPO_ROOT = _SRC_ROOT.parent`. `_FACTORY_SOURCES` now point at `_SRC_ROOT/vcfops_*`; repo-level assets (LICENSE, dist, tmp) at `_REPO_ROOT`. The `sdk_builder.py` source literals moved from `_HERE.parent / ...` to `_REPO_ROOT / ...`, and the `_IMPORT_REWRITES` patterns were updated to match those exact literals. `_apply_rewrites` raises `AssertionError` on any zero-match rule; a full `build-buildkit` ran with every rule matching (no stale-rule error) and the assembled flat kit imports cleanly. Layout is identical to released 1.0.6.

## Findings

### BLOCKING

- **[pyproject.toml (untracked) + pytest.ini (deletion)]** — commit self-consistency. The change deletes `pytest.ini` and moves its entire config (`markers`, `addopts = -m "not slow"`) into `pyproject.toml [tool.pytest.ini_options]` — but **`pyproject.toml` is currently untracked (`??`), not gitignored, and the `pytest.ini` deletion is unstaged (` D`).** As the change stands, a commit of the index would ship the deleted config with no replacement tracked: marker registration and the fast-loop slow-filter would silently vanish from the PR, and `tests/conftest.py`/workflow comments would point at a file not in the tree. The pyproject content itself is correct and verified (parity confirmed: markers + addopts match the old pytest.ini; original had no `testpaths`). → **Fix:** `git add pyproject.toml` and stage the `pytest.ini` deletion so the change is self-consistent before the PR is opened. Re-confirm `git diff main` then includes pyproject.toml.

### WARNING

- **[tests/managementpacks/test_buildkit_isolated_build.py `_make_isolated_env`]** — isolation robustness. The helper strips only `repo_root` from `PYTHONPATH`, but the packages now live at `repo_root/src`. Under the **shipped** config (relative `PYTHONPATH=src` + subprocess `cwd=/tmp`) isolation is genuine and both tests pass; under an **absolute** `PYTHONPATH=<repo>/src` the primary test `test_kit_isolated_build_no_vcfops_import_error` **blinds** (passes spuriously — vcfops importable) and only the canary `test_kit_isolated_build_fails_without_sm_rewrite` trips (verified empirically: 1 failed / 1 passed). So the guard pair is still fail-closed, but the primary guard's stated defense ("the factory repo root is explicitly stripped from PYTHONPATH") no longer matches reality — the real defense silently shifted to relative-path + cwd=/tmp. → **Fix:** strip both `repo_root` and `repo_root/src` (drop any resolved entry equal to or under repo root), so the primary guard is robust to an absolute PYTHONPATH and the docstring stays true.

- **[stale-zip discipline — informational]** — `src/vcfops_packaging/builder.py` is in the CLAUDE.md rebuild-trigger list, so the "all dist zips are stale" rule mechanically fires. However this diff is **provably output-neutral**: `builder.py`'s only change is `__file__` depth; `_TEMPLATES_DIR` resolves to the same (byte-identical) template files, `render.py` is byte-identical to main, and all `templates/` are byte-identical. No content staleness exists. → **Fix / action:** orchestrator should consciously acknowledge the rule fired and confirm no `content-packager` rebuild is required (it is not, on the merits) rather than let the trigger pass unnoticed.

### NIT

- **[pyproject.toml `[project]`]** — the table declares `name`/`version` but no `[build-system]` and no `dependencies` (documented intent: never pip-installed). A stray `pip install .` would still invoke setuptools' legacy backend and could install/leak `vcfops_*` into site-packages — the exact leak the design forbids. Low risk (no automation does this; intent is well-commented). Consider dropping the `[project]` table entirely, or adding an explicit note that it exists only for tool metadata and must never be built.

- **[pre-existing]** `@pytest.mark.timeout(60)` emits `PytestUnknownMarkWarning` (pytest-timeout not registered) — not introduced by this change; noted only for completeness.

## If shipped as-is

If the index is committed without `git add pyproject.toml`, the PR ships with `pytest.ini` deleted and no pytest config tracked: local `pytest` loses the `-m "not slow"` fast-filter (runs slow tests by default), `slow`/`real_corpus` markers become unregistered, and `conftest.py`'s xdist-group reference dangles — a silent test-harness regression. Everything else in the change is correct and fully verified; the move itself is clean.
