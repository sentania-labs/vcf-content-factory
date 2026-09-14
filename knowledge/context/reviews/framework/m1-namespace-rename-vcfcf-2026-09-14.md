# Framework review: M1 namespace rename `vcfops_*` to `vcfcf_*`

Date: 2026-09-14
Branch: `chore/m1-rename-vcfcf` (worktree `.claude/worktrees/agent-a30eb6e164bdad8eb`), four commits over `main`: 6045435, 70b44de, 73596c6, dd939a2
Plan: `knowledge/designs/content-migrator-plan-v1.md` §M1 ("Mechanical, no behavior change, one PR")
Reviewer: `framework-reviewer`, read-only on `src/`
Verdict: **CHANGES REQUESTED** (2 BLOCKING, 5 WARNING, 5 NIT)

## Claims verified

| Claim | Result |
|---|---|
| Pure substitution, zero behavior change in `src/` and `tests/` | Confirmed by line-level normalization of the whole `git diff -M main -- src tests pyproject.toml` (3911 changed lines). Every changed line in renamed files is the `vcfops_` to `vcfcf_` swap except two: `src/vcfcf_common/setup_credentials.py:985` and `:1169`, where the user-facing message text changed from `vcfops setup` to `vcfcf setup` (no underscore, so outside the stated pattern). New files: ten `vcfcf_*/__init__.py` and `__main__.py` (copies of the old ones), `src/vcfcf_common/compat_shim.py`, ten shim pairs under `src/vcfops_*/`, `tests/test_compat_shims.py`. |
| `git diff -M main --name-status` shows 155 renames, no delete+add | Not as stated. Against `main` it is 134 R, 23 A, 1 D. The 155 renames are what commit 6045435 shows in isolation. Against `main`, git pairs the old `__init__.py`/`__main__.py` paths with the shims, so the ten new-package `__init__`/`__main__` files show as A, and `src/vcfops_supermetrics/_env.py` shows as D with `src/vcfcf_supermetrics/_env.py` as A (six-line file, content identical modulo the swap). No file moved by delete+add that should have been a rename. Lowest similarity is `template_version.py` at R067; verified pure substitution. |
| Shims re-export and alias so `vcfops_x.sub is vcfcf_x.sub`, warn once | Submodule aliasing confirmed (`vcfops_common.client is vcfcf_common.client`, `vcfops_packaging.builder is vcfcf_packaging.builder`, `sys.modules` holds the `vcfcf_` name, `importlib.reload` of the aliased submodule reloads the real one). Warn-once confirmed per package. **Re-export is incomplete**: see BLOCKING 2. |
| `python3 -m vcfops_packaging --help` and `-m vcfops_managementpacks --help` exit 0 | Confirmed; help text byte-identical to the `vcfcf_` form. stderr is empty under default warning filters (see WARNING 1). |
| Full suite 1752 passed | Confirmed CI-style: `pytest tests/ -n auto --dist=loadgroup --override-ini="addopts=" -m ""` gives 1752 passed, 7 skipped, exit 0. Default local run (`-m "not slow"`) gives 1622 passed, 7 skipped, 130 deselected. |
| Validate chain exits 0 under both name forms | Confirmed; all seven validators exit 0 under both names and their output is byte-identical. |
| `vcfops_manifest.json` not renamed in code | Confirmed in `src/vcfcf_packaging/builder.py:762`, `discrete_builder.py:885`, `cli.py:526,532`, `publish.py:112-172`. **Two prose references were renamed anyway**: see WARNING 2. |
| Fixture hostnames, `vcfops-*` skill directories, historical records left as written | Confirmed. `knowledge/context/{reviews,curation,investigations,attic}` and HANDOFF notes untouched. Rules and lessons diffs are path references only; no product-name reference was rewritten there. |
| Built zip byte-identical to `main` apart from the marker | **Refuted.** See BLOCKING 1. |

## Checks re-run

- validate-chain: pass (both name forms, identical output)
- tests: 1752 passed / 0 failed / 7 skipped (CI invocation, xdist `-n auto --dist=loadgroup`)
- render-regression: all three `bundles/*.yaml` built from a `git archive` of `main` and of `HEAD` with `--no-live-describe`; every content entry (views XML, dashboard JSON, supermetrics, symptoms, alerts, reports, nested zips) is byte-identical; drift limited to `README.md` (top-level and per-bundle) and `install.py` inside each zip, plus the expected `vcfops_manifest.json` marker
- pak-compare: n/a (no pak built). Buildkit tarball built from both trees with the same dummy reference pak: differs only in comments, docstrings, and message strings carrying the identifier swap; no new unrewritten `vcfops_`/`vcfcf_` import (the two fallback imports in `pak_compare.py:14` and `dashboard_loader.py:2465` are pre-existing on `main` in the same try/except shape)
- `scripts/path_reference_audit.sh`: clear (six standing RULE-015 exceptions only)
- `scripts/check_framework_review.sh`: fires correctly on the branch (`vcfcf_*/ changed`)
- live-surface grep for `vcfops_` (excluding historical dirs, shims, manifest filename): clean; `.claude/settings.json` hook points at `src/vcfcf_common/doctor.py` (exists); `ci.yml`, `publish-buildkit.yml`, `/publish`, `/bundle`, `Getting_Started.md`, `.env.example`, `.gitignore`, `pyproject.toml` all updated; `install.ps1` byte-identical to `main`

## BLOCKING

### B1. Built zips are not output-identical, and the installer template changed without a `CURRENT_TEMPLATE_VERSION` bump

Authority: `src/vcfcf_packaging/template_version.py:7-13` ("Bump this value whenever any of the following change: templates/install.py ..."); CLAUDE.md "After tooling changes"; plan §M1 "no behavior change".

Every zip built from the branch differs from the `main` build in three shipped files:

- `install.py` (from `src/vcfcf_packaging/templates/install.py:107`, temp-dir prefix `vcfops_install_venv_` to `vcfcf_install_venv_`, and `:1406`, a docstring)
- top-level `README.md` footer (`src/vcfcf_packaging/templates/README_framework.md:199`)
- per-bundle `README.md` footer (`src/vcfcf_packaging/builder.py:579`, `src/vcfcf_packaging/discrete_builder.py:381`)

`CURRENT_TEMPLATE_VERSION` is still `2026-08-29-1`, so `check-staleness` reports every previously distributed zip as current while the shipped installer bytes changed. The changes are cosmetic, but the rule is mechanical and the M1 contract is "rename must not change output".

Smallest correct fix: keep those five string sites as they were on `main` (they are message and comment text, and `vcfops_packaging` remains a valid alias for this release), which restores byte-identical output and needs no bump. Alternative: bump `CURRENT_TEMPLATE_VERSION` and record the reason in its history block. Either way, `builder.py`, `discrete_builder.py`, `release_builder.py`, and `render.py` all changed, so per CLAUDE.md the orchestrator owes a full `content-packager` rebuild after merge; the PR body must say so.

### B2. The `vcfops_common` shim does not forward the lazy `VCFOpsClient` / `VCFOpsError` names

Authority: `src/vcfcf_common/compat_shim.py:13-14` (the shim's own contract: "`import vcfops_x; vcfops_x.thing` keeps resolving"); plan §M1 "no behavior change".

`install()` at `compat_shim.py:87-88` copies only non-dunder attributes of the new package into the shim namespace. `vcfcf_common/__init__.py` deliberately exposes `VCFOpsClient` and `VCFOpsError` through a module-level `__getattr__` (lazy `requests` import), which is a dunder and is skipped, and the shim module defines no `__getattr__` of its own. Verified:

```
from vcfops_common import VCFOpsClient   -> ImportError
vcfops_common.VCFOpsError                -> AttributeError
from vcfops_common import *              -> AttributeError (names are in the copied __all__ but absent)
```

These are the two most-used public names of the old `vcfops_common`. No caller inside this repo or the six adapter clones uses them under the old name today, but the shim exists precisely for callers we cannot see, and its test (`tests/test_compat_shims.py::test_old_submodule_import_is_same_object_as_new`) only exercises `vcfops_common.client`.

Smallest correct fix: in `install()`, if the new module defines `__getattr__`, set `namespace["__getattr__"] = lambda name: getattr(new_mod, name)` (or forward it directly); add a test asserting `from vcfops_common import VCFOpsClient, VCFOpsError` and `from vcfops_common import *` succeed.

## WARNING

### W1. The deprecation is invisible on the `python -m vcfops_*` path

`compat_shim.py:77-81` emits a `DeprecationWarning` with `stacklevel=3`. For `python3 -m vcfops_<x>` the attributed frame is importlib bootstrap, not `__main__`, so Python's default filter drops it. Verified: `python3 -m vcfops_packaging --help`, `-m vcfops_managementpacks --help`, and all seven `-m vcfops_<x> validate` runs produce zero bytes on stderr. `tests/test_compat_shims.py:31-33` only proves the warning with `PYTHONWARNINGS=default::DeprecationWarning` forced.

Whether that is acceptable: the six adapter repos' CI is not affected (see W4; they run `sdk_buildkit` from the published tarball, never `-m vcfops_*`). The consumers of the old names are people following the adapter READMEs and older docs, and they will get no signal until the shims are deleted next release and the command simply fails. One release with a silent alias is defensible only if something announces it. Fix: print one line to stderr from each shim `__main__.py` before `runpy.run_module` (e.g. `vcfops_packaging is deprecated; use vcfcf_packaging`), keep the `DeprecationWarning` for the import path, and add a test that the CLI path prints the notice under default filters.

### W2. `vcfops_manifest.json` was renamed in two prose sites while the file in the zips keeps its name

- `.claude/agents/framework-reviewer.md:191` (live agent prompt; now tells the reviewer to look for a file that does not exist)
- `knowledge/designs/release-lifecycle-v1.md:507`

Fix: restore `vcfops_manifest.json` in both.

### W3. Substitution changed the meaning of historical or planning statements

- `knowledge/designs/content-migrator-plan-v1.md:50`: the M1 row now reads "Rename import namespace `vcfcf_*` to the chosen name", which is circular; it should say `vcfops_*`.
- `STRUCTURE.md:37` (living map): "package names and import paths are unchanged (`python3 -m vcfcf_<x>` still works ...)". That sentence described reorg v2 phase 1; after M1 it is false as a description of the current state and says nothing about the ten `src/vcfops_*/` shim packages that now also live under `src/`.
- `knowledge/designs/reorg-v2-landing-page.md:63,101,116`: the 2026-07-08 execution note now claims packages lived at `src/vcfcf_<x>/` with names unchanged, which was not true on that date.

Fix: restore `vcfops_` in the historical sentences, reword the plan row, and add a line to `STRUCTURE.md` naming the shims and their one-release lifetime.

### W4. The shim's stated consumer is wrong

`src/vcfcf_common/compat_shim.py:5-7` and `tests/test_compat_shims.py:3-4` say the SDK adapter repos run `python3 -m vcfops_packaging` / `-m vcfops_managementpacks` from CI. Verified against all six clones under `content/sdk-adapters/*/.github/workflows/`: every workflow downloads the `sdk-buildkit-*.tgz` release and runs `PYTHONPATH=_kit python3 -m sdk_buildkit ...`; none references `vcfops_` or `vcfcf_`. The actual old-name consumers are the adapter READMEs (`content/sdk-adapters/vcommunity/README.md:149,153`, `vcommunity-os/README.md:187,191`, `vcommunity-vsphere/README.md:183,187`, `compliance/README.md:14`) and `scripts/version_line_guard.sh:276` (already updated on this branch).

Fix: correct the docstring and test header; open one follow-up issue per adapter repo to update the README commands before the shims are removed (the sdk-template scaffold under `knowledge/designs/sdk-template-scaffold/` is already clean).

### W5. A design doc names a path that no longer exists and the audit cannot see it

`knowledge/designs/sdk-adapters/compliance-v2-migration.md:23` still says `vcfops_managementpacks/adapter_framework/`. `scripts/path_reference_audit.sh` reports clear because the reference has no `src/` prefix. Fix: rename to `src/vcfcf_managementpacks/adapter_framework/`.

## NIT

### N1. `check_framework_review.sh:36` no longer covers the shim packages

The regex is `^src/vcfcf_[^/]+/`. For the one release the `src/vcfops_*/` shims exist they are framework Python too, and an edit to one would not trigger the review nudge. Fix: `^src/(vcfops|vcfcf)_[^/]+/` until the shims are deleted, then narrow it back.

### N2. `setup_credentials.py:985,1169` is the one src change beyond the identifier swap

Message text `vcfops setup` became `vcfcf setup`. It is the right wording (the command is now `python3 -m vcfcf_common setup`) but it falls outside "pure substitution of `vcfops_`"; say so in the PR body rather than letting Codex find it.

### N3. PR body rename count

State 134 renames / 23 adds / 1 delete against `main` (155 renames in 6045435 alone), so the number matches what a reviewer sees on the PR.

### N4. Buildkit tarball string drift without a `BUILDKIT_VERSION` bump

`src/vcfcf_managementpacks/buildkit.py:76` stays `1.0.9`. The kit diff is comments and message strings only, so no bump is warranted; noting that the next factory tag republishes `sdk-buildkit-v1` with those strings changed.

### N5. Shim test coverage

`tests/test_compat_shims.py` exercises `vcfops_common.client` and two `--help` runs. Add `from vcfops_common import VCFOpsClient, VCFOpsError`, `from vcfops_common import *`, and one non-`common` package attribute (e.g. `vcfops_packaging.CURRENT_TEMPLATE_VERSION`) so B2 cannot recur.

## Dimensions walked with no finding

- Global-default / pak-specific leak (`00d3382`): no defaults, coordinates, or flags changed; the import-zip path produces identical content entries.
- Key / label derivation (`6c59f6b`): no renderer logic touched; dashboard JSON and views XML byte-identical to `main`.
- Wire-format conformance: no emitted key added or dropped.
- Loader / validator: corpus validates identically under both names.
- Meta-path finder: inserted at `sys.meta_path[0]` only when a `vcfops_*` package is imported; intercepts `vcfops_*.<sub>` names only; the shim `__main__` is excluded so `python -m` runs the real `__main__` via `runpy`; xdist workers unaffected (full suite green under `-n auto --dist=loadgroup`); `importlib.reload` on an aliased submodule reloads the real module, on a shim package re-runs `install()` and warns once more.
- `pyproject.toml` still declares `packages = []`; shims cannot leak into site-packages any more than the real packages can.
- `version_line_guard.sh`: still resolves `adapter_kind` with the `vcfcf_` prefix (product prefix, unchanged) and invokes `vcfcf_packaging defect-gate` from the factory checkout; guards what it guarded.

## If shipped as-is

Rebuilt zips would differ from the last release only in README footers and the installer temp-dir prefix while `check-staleness` reports every old copy current; any external script doing `from vcfops_common import VCFOpsClient` fails with ImportError; every `python3 -m vcfops_*` command keeps working with no deprecation notice, and next release those commands stop working with no prior signal; the reviewer prompt and one design doc point at a manifest filename that does not exist.

## Round 2 (2026-09-14, branch head 80a2395)

Commits since round 1: 55aae54 (tooling), 8e2ace7 and 10c6e08 (orchestrator), 80a2395 (merge). Diff since dd939a2 touches `src/vcfcf_common/compat_shim.py`, the four B1 string sites, the ten shim `__main__.py` files, `tests/test_compat_shims.py`, `scripts/check_framework_review.sh`, and six docs. Nothing else in `src/` moved.

Verdict: **APPROVE** (0 BLOCKING, 0 WARNING, 2 NIT). Both NITs are one-line doc edits; per CLAUDE.md step 9 they go in before the PR opens.

### Closures verified independently

| Finding | Status | Evidence |
|---|---|---|
| B1 zips not output-identical, template changed without version bump | Closed | `templates/install.py` and `templates/README_framework.md` are byte-identical to `main`; `builder.py` and `discrete_builder.py` differ from `main` only in import lines. Rebuilt all three `bundles/*.yaml` and all thirteen `bundles/releases/*.yaml` from `git archive` of `main` and of `HEAD`: every nested member of every zip is byte-identical except `vcfops_manifest.json` (12/12, 17/17, 19/19 members on the flat bundles; 13 release artifacts clean). `CURRENT_TEMPLATE_VERSION` correctly left at `2026-08-29-1`. |
| B2 lazy names not forwarded | Closed | `compat_shim.py:95-101` forwards `__getattr__` and `__dir__`. Verified in-process: `from vcfops_common import VCFOpsClient, VCFOpsError` succeeds and both are the same objects as on `vcfcf_common`; star import resolves every `__all__` name to the same object; `vcfops_packaging.CURRENT_TEMPLATE_VERSION` matches; an unknown name on a shim still raises `AttributeError`. |
| W1 deprecation invisible on `-m` path | Closed | Each shim `__main__.py` prints one stderr line before `runpy`. Verified with no `PYTHONWARNINGS`: `-m vcfops_packaging --help` and `-m vcfops_managementpacks --help` exit 0 with exactly one notice line; all seven `-m vcfops_<x> validate` runs exit 0 with one notice line each; `-m vcfops_common doctor` exits 0 with the notice; `-m vcfcf_packaging --help` emits zero bytes on stderr. |
| W2 `vcfcf_manifest.json` in prose | Closed | `.claude/agents/framework-reviewer.md:191` and `knowledge/designs/release-lifecycle-v1.md:507` restored; repo grep for `vcfcf_manifest` is empty. |
| W3 meaning-changing substitutions | Closed | Plan row now "Rename import namespace `vcfops_*` to `vcfcf_*`"; `STRUCTURE.md:37` describes the M1 rename and names the `src/vcfops_*/` shims and their one-release lifetime; `STRUCTURE.md:83` and `reorg-v2-landing-page.md:63,101,116` restored to the historical `vcfops_` wording with an M1 note. |
| W4 wrong stated consumer | Closed | `compat_shim.py:4-9` and `tests/test_compat_shims.py:3-8` now say adapter READMEs, not CI, and cite issue #159. |
| W5 dead path in `compliance-v2-migration.md:23` | Partially closed, see N1 below | Path changed to `vcfcf_managementpacks/adapter_framework/`, still without the `src/` prefix, so it still names a path that does not exist at repo root and the audit still cannot see it. |
| N1 (round 1) `check_framework_review.sh` regex | Closed | `scripts/check_framework_review.sh:37` matches `^src/(vcfcf|vcfops)_[^/]+/`; re-ran it on the branch and it lists all twenty packages. |
| N5 (round 1) shim test coverage | Closed | Four new tests in `tests/test_compat_shims.py` (default-filter CLI notice x2 modules, lazy names, star import, non-common attribute). |
| N2, N3, N4 (round 1) | Accepted as stated | Wording kept and to be disclosed in the PR body; PR body to carry the real R/A/D counts; `BUILDKIT_VERSION` unchanged. |

### Checks re-run

- tests: 1757 passed / 0 failed / 7 skipped (CI invocation, `-n auto --dist=loadgroup --override-ini="addopts=" -m ""`), matches the claim
- validate-chain: pass under the old names (all seven exit 0, one notice line each on stderr)
- render-regression: clean; three flat bundles and thirteen release artifacts byte-identical to a `main` build apart from the `vcfops_manifest.json` marker
- `check_framework_review.sh`: fires on both prefixes
- em-dash scan of added lines since dd939a2: one hit, see N2

### Nothing new introduced

- `compat_shim.py:97` `hasattr(new_mod, "__dir__")` is always true for a module object (every object has `__dir__`), so every shim gets `__dir__` forwarded, not only `vcfcf_common`. Harmless: `dir(vcfops_packaging)` returns the real package's names, which is the intended answer. Noting it so nobody reads the guard as selective.
- The stderr notice is printed by the shim `__main__` only, so library imports of `vcfops_*` stay silent apart from the `DeprecationWarning`; the `-m` path prints exactly once per process (verified, no duplicate from the package import).
- No behavior change on the `vcfcf_*` path: new-name CLI stderr is empty, suite green, output identical.

### Still open (fix in one pass, do not defer)

- **N1** `knowledge/designs/sdk-adapters/compliance-v2-migration.md:23`: the path needs the `src/` prefix (`src/vcfcf_managementpacks/adapter_framework/`) so it names a real path and `scripts/path_reference_audit.sh` can check it.
- **N2** same line carries a pre-existing em-dash ("built, then an em-dash, then the path") on a line this branch modified; user rule 7 says none anywhere, so replace it while the line is being touched.

### If shipped as-is

Operators and downstream paks see no change: identical zips, identical validate output, old commands keep working with a single stderr notice naming the replacement, old imports keep resolving including the lazy client names. One design doc names a path that does not exist and carries an em-dash.
