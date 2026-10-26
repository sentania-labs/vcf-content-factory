# Framework review: drop the extractor export-zip reader aliases (#165), 2026-10-26

Branch `chore/165-drop-extractor-aliases`, commit `c2379e8`, diffed against
`main` (`bc783ea`) in the worktree
`.claude/worktrees/agent-a7d9c6acc57422841`. Main baseline taken from a
`git archive main src` tree in the session scratchpad.

**Verdict: APPROVE.** 0 BLOCKING, 0 WARNING, 2 NIT.

The only code change is deleting three alias assignments. Everything else
in the diff is docstrings, comments and tests. No caller is left, the
public API is the same, and the tests still prove what they claimed.

## Scope

Five files: `src/vcfcf_core/extractor/__init__.py`,
`src/vcfcf_core/extractor/extractor.py`,
`tests/test_core_extractor_public_readers.py`,
`tests/test_core_row4_seams.py`, `tests/test_core_shims.py`. Once comments
and docstrings are filtered out, the only `src/` lines that change are the
three deleted assignments `_content_xml_from_export_zip = ...`,
`_supermetrics_from_export_zip = ...`, `_dashboards_from_export_zip = ...`.
No reader body changed. Nothing in the diff falls outside the brief.

## Re-run evidence

| Check | Result |
|---|---|
| Seven-package validate chain (worktree `src/` on `PYTHONPATH`) | all rc=0 |
| `tests/test_core_*.py` with `-m "slow or not slow"` | 212 passed, 1 skipped. The skip is `test_core_shims.py:350` "wrapper defines every public name itself", which is pre-existing |
| Slow wheel-alone gate on its own (`test_offline_reverse_from_the_wheel_alone_matches_the_factory_path`) | PASSED. Its fixture asserts that every `.py` in the wheel is byte-equal to `src/`, so the wheel it ran on contains the branch's `extractor.py` |
| Full suite (`-n 8 --dist=loadgroup`) | 2623 passed, 6 failed, 9 skipped. The 6 failures are exactly the pre-existing `test_release_naming_phase_v2_item1.py` (5) and `test_validator_phase2.py` (1), which the brief excludes |
| Public API, main vs branch (`__all__`, `dir()` of the package, `inspect.signature` of each reader, identity across the core package, the core module and the factory wrapper) | `__all__`, package `dir()`, signatures and identity are all unchanged. The only change in module `dir()` is that the three underscore names are gone. `hasattr` of the underscore names on core and on the `vcfcf_extractor.extractor` wrapper is True on main and False on the branch |
| Em-dashes in added lines and in the commit message | 0 and 0 |

## Caller sweep

I grepped the whole worktree (excluding `.git`), including
`src/vcfcf_packaging/templates/`, `scripts/`, `.claude/`, `.github/`,
`knowledge/`, root docs and tests, for the three underscore names. The only
hits are in a historical review record,
`knowledge/context/reviews/framework/m2-row4-core-extractor-2026-09-14.md:122,124,213`.
It describes the state as of 2026-09-14 and is not an import example, so
it stays as written.

The live users of the readers all use the public names already:

- `src/vcfcf_dashboards/client.py:244`
- `src/vcfcf_extractor/extractor.py:45,51`
- `tests/test_install_materialization.py:37`

`src/vcfcf_packaging/templates/install.py:1578` has its own
`_mat_dashboards_from_export_zip`. It is a separate function, not an alias,
and the branch does not touch it.

The factory wrapper's module `__getattr__`
(`src/vcfcf_extractor/extractor.py:1449`) forwards unknown names to core.
That means the old names now raise a clean `AttributeError` through the
wrapper too. I confirmed this in the API diff above.

`migrator` mentions left in `src/`, `tests/`, `scripts/` and `.claude/`:
one, `tests/test_dashboard_materialization.py:13`. It is fixture provenance
("shapes copy the ... exports in the migrator corpus"). It is accurate and
it is not code kept for the migrator. The comment at
`.github/workflows/publish-core.yml:4` is also accurate (the migrator does
pin the wheel by URL). Both are outside this brief.

## Do the tests still prove their claims

- `test_package_names_are_the_module_objects`: replaces the old three-way
  identity check. It still pins package-to-module identity, and the alias
  leg was dropped on purpose.
- `test_underscore_names_are_gone`: new. It checks the core module. The
  wrapper case follows from `__getattr__` (confirmed above). Restoring any
  alias would make it fail.
- `test_factory_reexport_resolves`: now checks the wrapper's public names.
  `test_live_export_functions_call_the_core_readers` lost only the alias
  assertion. Its identity, source-shape and behaviour checks are unchanged.
- `TestExportZipReaders` and `unpack_export_zip`: the tests are the same,
  only the import names changed. `unpack_export_zip` is inlined into the
  bare-site subprocess, so the wheel gate now proves that the public names
  import from the wheel alone. That is a stronger claim than before.
- `test_core_shims.py` WRAPPERS: the three names leave the "served by
  `__getattr__`" tuple, which is correct because core no longer defines
  them.

## Dimensions

1. Global/pak leak (`00d3382`): n/a. No renderer, default or coordinate
   code is touched.
2. Key/label collision (`6c59f6b`): n/a.
3. Wire format: unchanged. The reader bodies are byte-identical.
4. Loader/validator: unchanged. The validate chain is green.
5. Render regression: n/a. No render path is touched, and the readers are
   unchanged.
6. Builder/pak: n/a.
7. Corpus regression: clean (see the re-runs above).
8. Silent capability change: the removal is deliberate, recorded in #165
   and in the commit message, and the migrator breaks on its next pin bump
   as accepted. It is a loud, documented removal of the old names only, so
   it is not a finding.
9. Stale-zip / template version: none of the trigger paths are touched
   (`templates/`, `builder.py`, `discrete_builder.py`, `release_builder.py`,
   `assembly.py`, `render.py`). No rebuild and no `CURRENT_TEMPLATE_VERSION`
   bump are needed. The core wheel version comes from the `core-v*` tag via
   setuptools-scm, so there is nothing to bump in the tree either.
10. Test coverage: covered (see above).

## Findings

### NIT

- **N1** `tests/test_core_row4_seams.py:370`. The docstring quotes a gate
  name, "The 'installs from the wheel alone' gate (design §Gates)", that no
  design contains. The unnamed design is presumably
  `knowledge/designs/tooling-core-carveout-v1.md` §Gates. Its line 118
  still reads "the migrator skeleton (M3) installs it by URL". A quoted
  phrase next to a citation reads as a verbatim pointer and sends a reader
  hunting for text that is not there. Fix: name the document and drop the
  quotes, for example "The wheel-alone gate
  (`tooling-core-carveout-v1.md` §Gates): ...".
- **N2** `tests/test_core_row4_seams.py:169`. The section header "The
  wheel-alone gate: offline read path from the wheel alone" says "wheel
  alone" twice. Fix: "The wheel-alone gate: offline read path".

## Notes (not findings)

- When the next `core-v*` tag is cut, its release-log entry in
  `tooling-core-carveout-v1.md` should say that the underscore reader names
  are gone, because that is the version that breaks the migrator's pin.
  That happens at tag time, not on this branch.
- This report is written to the main checkout as briefed.
  `scripts/check_framework_review.sh` looks for the review doc in the PR's
  own diff, so copy it onto the branch before the PR opens, or the CI nudge
  will warn.
