# Framework review: build-buildkit with only PyYAML (buildkit 1.0.20)

- Branch: `fix/buildkit-no-requests`, commit `c4c40fd` on `main` `03acd5a`
- Area: `src/vcfcf_managementpacks/{buildkit,sdk_builder}.py`, `src/vcfcf_supermetrics/__init__.py`, `src/vcfcf_customgroups/__init__.py`
- Reviewer: framework-reviewer, 2026-10-27
- Verdict: **APPROVE** (0 BLOCKING / 0 WARNING / 2 NIT)

## The problem, confirmed

Run 40515187937 (Publish sdk-buildkit, tag `sdk-buildkit-v1.0.19`, which points at `03acd5a`) failed. The last published kit is still 1.0.12, and tags v1.0.13 to v1.0.18 do not exist on the remote. I reproduced the failure from a `git archive` of `03acd5a` in a venv holding only PyYAML 6.0.3: `ERROR building buildkit: No module named 'requests'`, after VERSION is written, which is where `_factory_source_commit()` runs.

## Independent re-runs

| Check | Result |
|---|---|
| `build-buildkit` on the branch, PyYAML-only venv, `PYTHONPATH=src`, `--reference-pak vcfcf_sdk_compliance.1.0.0.49.pak` | rc 0. Tarball, SHA-256 sidecar and SOURCE_COMMIT `c4c40fd` all written |
| Workflow step "no Broadcom JARs" (same grep) | 0 matches |
| Workflow step `sha256sum -c` | OK |
| Release notes step | `sed` over `.github/release-notes-buildkit.md` (present) and `gh`, no Python. The floating-release step is shell plus `gh` only. Nothing after assembly needs `requests` |
| Produced kit, PyYAML-only venv: `validate-sdk` on a scratch copy of `content/sdk-adapters/compliance` (`--sdk-jar` 2.2) | OK, valid Tier 2 project |
| Produced kit, PyYAML-only venv: `build-sdk` on the same copy | Built `vcfcf_sdk_compliance.0.0.0.101.pak`; pak-compare against the bundled 1.0.0.49 gave 2 WARNING, 0 BLOCKING |
| Kit import lines vs 1.0.12 (downloaded release) | `sdk_builder.py:79` `from . import sm_crossref as _crossref`, identical to 1.0.12 line 76. No `from/import vcfcf_*` statement is left in the kit (two hits are docstrings, as in 1.0.12) |
| Kit diff vs the 1.0.19 kit built from `0b844c1` | Only VERSION, SOURCE_COMMIT, the generated-file header, #277 docstrings, the new 3-line comment and the reference pak. No code change |
| Rewrite-miss safety | `_apply_rewrites` raises on a zero-match rule, so a stale rule cannot ship the factory import silently |
| `crossref` equivalence | `vcfcf_supermetrics/crossref.py` replaces itself in `sys.modules` with `vcfcf_core.supermetrics.crossref`, so it is the same module object (`a is b` True). Kit `sm_crossref.py` is byte-identical to the core file |
| Lazy `__getattr__` | `from vcfcf_supermetrics import VCFOpsClient`, `from vcfcf_customgroups import VCFOpsCustomGroupClient`, `import *` on both, `pkg.VCFOpsClient`, and `pkg.client` after resolution all work. Unknown names raise AttributeError |
| Behaviour change: bare `import vcfcf_supermetrics; vcfcf_supermetrics.client` | Now AttributeError until the client is resolved or the submodule is imported. I grepped src/, tests/, scripts/, .claude/, .github/ and the docs: no caller does this; every hit is prose. `mock.patch("pkg.client.X")` imports via importlib, so it is unaffected |
| Every `src/vcfcf_*` package imported in the PyYAML-only venv | All clean |
| New test on `main` source | 2 failed / 1 passed, both on `No module named 'requests'` (the blocker sanity test passes) |
| New test on branch | passes (part of the suite) |
| Full suite, branch, `-n auto --dist=loadgroup`, sdk-adapters symlinked then removed | 3025 passed, 9 skipped |
| Validate chain (7 packages) on branch | all rc 0; managementpacks: 7 Tier 2 projects valid |

## Dimensions

1. Global/pak leak (00d3382): not applicable. No renderer default changes. Kit output is unchanged.
2. Key collisions (6c59f6b): not applicable.
3. Wire format: no emitted JSON/XML changes. The kit-built compliance pak passes pak-compare with 0 BLOCKING.
4. Loader/validator: the resolver is the same module object, so cross-reference resolution cannot change.
5. Render regression: none. The kit diff is docstrings and the new comment only.
6. Builder/pak: pak-compare is clean, see above.
7. Corpus: the validate chain and the suite are green.
8. Silent capability change: the only behaviour change is the lazy `.client` attribute, and I proved no caller depends on it.
9. Stale-zip: the change touches none of the template, builder, assembly or render paths. `BUILDKIT_VERSION` is bumped to 1.0.20, which is the kit's own signal, and that is correct: 1.0.19 never published, and the tag already exists on a broken commit.
10. Tests: a new subprocess guard drives the real CLI, the produced kit and every package `__init__`, using a meta_path blocker. It fails on main for the right reason, so it would have caught this.

## Findings

### NIT

- **`tests/managementpacks/test_buildkit_without_requests.py:5-6`, docstring.** It says "Tags sdk-buildkit-v1.0.13 to v1.0.19 published nothing". Only v1.0.19 was ever tagged; `git ls-remote` shows no v1.0.13 to v1.0.18. The changelog row has this right. **Fix:** say "No kit has published since 1.0.12; the v1.0.19 tag failed."
- **`knowledge/context/tier2_architecture.md:1118`, changelog row.** It leaves out the `**Versioning:**` / `**Adapter adoption:**` fields that every neighbouring row carries. Those fields matter here: the adoption notes for 1.0.13 to 1.0.19 have never reached a pak repo. That includes the #245 row's "every Tier 2 pak needs a rebuild on 1.0.19" and #270's stricter SM scope. So when 1.0.20 publishes, `sdk-buildkit-v1` jumps straight from 1.0.12 to 1.0.20. **Fix:** add `**Versioning:** 1.0.20 (1.0.19 tag orphaned, never released)` and `**Adapter adoption:** the first kit since 1.0.12; carries the 1.0.13 to 1.0.19 adoption notes (#245 rebuild); no new source change`.

## Not findings (noted)

- The `sdk-buildkit-v1.0.19` tag stays on the remote with no release. Bumping to 1.0.20, rather than retagging, is the cleaner path. Whether to delete the orphan tag is the operator's call, outside src/.
- The kit's `sdk_builder.py` now carries a factory-oriented comment about `vcfcf_core` above `from . import sm_crossref`. That is harmless, and consistent with the other factory references the kit's comments already contain.

## If shipped as-is

Tagging `sdk-buildkit-v1.0.20` publishes the first kit since 1.0.12. The kit builds and validates paks with PyYAML only, and pak repos following `sdk-buildkit-v1` receive the 1.0.13 to 1.0.19 changes in one step.
