# Framework review: M2 row 4, extractor parsers and reverse_local into vcfcf_core

Date: 2026-09-14. Reviewer: framework-reviewer. Branch
`feat/m2-row4-core-extractor` (four commits over main `be3f01f`, head
`fec65ba`). Design: `knowledge/designs/tooling-core-carveout-v1.md` row 4
and "Gates". Precedent: `m2-row3-core-loaders-2026-09-14.md`.

Verdict: **APPROVE** (zero BLOCKING). Three WARNINGs and three NITs, all to
be fixed before the PR opens per CLAUDE.md step 9. Ownership is marked on
each.

## What changed

- `git mv` (`d25ab62`, pure: two 100% renames plus a 3-line `__init__.py`)
  of `vcfcf_extractor/extractor.py` and `vcfcf_extractor/reverse_local.py`
  into `src/vcfcf_core/extractor/`.
- Split (`740a59b`): the live half (`_build_sm_client`, `_build_ui_client`,
  `_dashboard_action`, `_SMNameCache`, `_scan_existing_ids`,
  `_run_content_export`, `_export_views_zip`, `_export_supermetrics_full`,
  `_export_dashboard_json`, the `${this}` audit helpers, `list_dashboards`,
  `extract_dashboard`) moves back to `src/vcfcf_extractor/extractor.py`,
  which binds `_REPO_ROOT`, imports 11 core names explicitly and serves the
  other 9 through module `__getattr__` (read-only, documented in both
  docstrings). Core `_rewrite_formula(formula, name_cache)` drops the
  `_SMNameCache` annotation (duck-typed on `name_for_uuid`);
  `_scan_existing_ids(kind, repo_root)` requires the root and
  `extract_dashboard` passes `_REPO_ROOT` at its three sites. Core
  `reverse_local` imports its siblings relatively (`..dashboards.reverse`,
  `..dashboards.loader`, `..dashboards.render`, `.extractor`), so its
  round-trip check now loads through the core loader with no minting
  callback. `vcfcf_extractor/reverse_local.py` is a `sys.modules` alias.
  Six em-dashes in moved user-facing strings and comments converted.
- Tests (`c251799`): `test_core_row4_seams.py` (8 tests, incl. the
  wheel-only migrator gate), one `_VIOLATION_SAMPLES` entry, shim coverage
  for the wrapper and alias.
- Docs (`fec65ba`): two `knowledge/context/` docs and the package README
  re-pointed to the core paths.

## Checks re-run (independently, from the worktree)

| Check | Result |
|---|---|
| `test_core_contract.py` + `test_core_shims.py` + `test_core_row4_seams.py`, `-m ""` | 165 passed, 1 skipped (the same pre-existing skip); the wheel test ran and passed (`-v -k wheel`, 3.4 s) |
| Full suite, `-n auto --dist=loadgroup --override-ini=addopts= -m ""`, adapter clones via a scratch `content/sdk-adapters` symlink (removed afterwards) | **1984 passed, 8 skipped** (47 s), as claimed |
| Validate chain (supermetrics, dashboards, customgroups, symptoms, alerts, reports, managementpacks, packaging) | all exit 0; tree clean afterwards (no ids minted) |
| Contract rules, probed on `_static_findings` with `SRC` redirected to a temp dir | the row 4 sample fires (`.parent.parent`, twice: the bind and the join); so do `Path(__file__).resolve().parents[2]`, three nested `os.path.dirname`, `.resolve().parent.parent.parent`, and the same shape inside a function; a single `.parent` is silent; both real core files return no findings; `ALLOWLIST` empty |
| Wheel built by hand (`pip wheel . --no-deps`, 2.9 s) | `vcf_cf_tooling_core-0.0.2.dev8+gfec65ba` (HEAD is `fec65ba`); 36 `.py` modules; `extractor/extractor.py`, `extractor/reverse_local.py`, `extractor/__init__.py` byte-equal to `src/`; no `.py` in the wheel absent from `src/`; `build/lib/vcfcf_core` (left by tooling's earlier build) currently diff-clean against `src/vcfcf_core`. See W2 for why the test itself should say this |
| Wheel-only test isolation, read | subprocess `env` is exactly `PATH` + `PYTHONPATH=<scratch site>`; cwd is a fresh empty dir (asserted still empty afterwards); the script imports `vcfcf_common`/`vcfcf_extractor`/`vcfcf_dashboards`/`vcfcf_packaging` and exits non-zero if any succeeds, then checks `sys.modules` for any non-core `vcfcf_*` after the run; the factory-path comparison (`_run_factory_reverse`) runs in the same test on the same zip through `vcfcf_extractor.reverse_local`; every emitted file is compared byte-for-byte and the views are proven to carry `supermetric:"[Fixture] SM n"` with no `sm_` token left. Real proof, not a tautology |
| Byte identity, `build bundles/storage-path-monitoring.yaml --no-live-describe`, `PYTHONHASHSEED=0`, branch vs `git archive main` tree (the CLI built all three manifests) | `storage-path-monitoring` 12/12, `vcf-license-consumption-overview` 17/17, `vks-core-consumption-bundle` 19/19 members (nested zips walked); every member byte-equal except `vcfops_manifest.json` (`built_at` only). Note: the worktree's gitignored `dist/` now holds the main-tree build from the second run |
| Offline reverse, `reverse-local` over all 12 vCommunity reference dashboards (`Management Pack/content/dashboards/*.json`, views from `content/reports`, SM dir `content/sdk-adapters/vcommunity/supermetrics`, 37 SMs), branch vs main tree | 12 dashboard YAMLs and 96 view YAMLs, **output trees identical** (`diff -r` empty); stdout/stderr differ only in the output-dir and source-path strings; round-trip 9 MATCH / 3 UNSUPPORTED-or-ERROR on both sides (pre-existing) |
| `_scan_existing_ids` inertness (delta 1) | with the real `_REPO_ROOT`: 0 supermetric / 0 view / 0 dashboard ids found; with `_REPO_ROOT / "content"`: 41 / 26 / 10. Same on main (`git log -S` shows the `<root>/supermetrics` join unchanged since the M1 rename; content moved under `content/` in `ba1755d`, 2026-04-27). Inert as claimed. See W1 |
| Delta 2 mechanics | `reverse_local._write_dashboard_yaml` writes `id: ''` when the source has none (`:635`); core `_resolve_id` treats `''` as missing and raises without a callback (`dashboards/loader.py:1998-2004`); main's wrapper `_mint_id_into_file` prepends `id: <uuid>\n` to the file (`vcfcf_dashboards/loader.py:30-40`), which is where the second `id:` line came from. Nothing depended on the mint: `.claude/commands/extract.md` and `cli.py` never mention minting and `/extract` drives only the live `extract dashboard` path; the `reverse-local` help text promises a round-trip verdict, not an id; `test_reverse_local.py` passes unchanged. The branch turns a corrupting write into an honest ERROR verdict with the file left as written (pinned by `test_round_trip_check_never_mints_into_the_emitted_yaml`) |
| `__getattr__` read-only asymmetry (brief item 4) | grep of `tests/`, `.claude/`, `scripts/` for `monkeypatch.`/`patch(`/`patch.object(` naming `extractor` or `reverse_local`: none. Every importer of a served name reads it (identity pinned by `test_core_shims.py` WRAPPERS row). The legacy `vcfops_extractor.extractor` compat alias serves the core parser and keeps `_REPO_ROOT`; `vcfops_extractor.reverse_local` resolves to the core module |
| Residual factory assumptions in core `reverse_local` (brief item 5) | no `__file__`, `_REPO_ROOT`, `os.environ`, `getcwd`, `content/`, `knowledge/`, no string default on a path parameter (`reverse_local_port` is keyword-only with five required `Path`s); reads only the three input paths, writes only the two output dirs. One user-facing string names a factory CLI, see N1 |
| Signature parity, main `extractor.py` (31 defs) vs core (19) + wrapper (13) | no name lost, none duplicated, one new (`__getattr__`); only `_rewrite_formula` (annotation dropped) and `_scan_existing_ids` (root added) changed, both declared |
| Em-dashes | 2814 added lines across `main..HEAD`, zero carry an em-dash (binary-safe scan); the six conversions are in moved strings and comments, verified in the split diff |
| Stale-zip discipline (dimension 9) | none of `templates/`, `builder.py`, `discrete_builder.py`, `release_builder.py`, `render.py`, `assembly.py`, `template_version.py` touched; bundles byte-identical; no rebuild and no `CURRENT_TEMPLATE_VERSION` bump warranted |
| Wheel inventory for the migrator (brief item 9) | the wheel carries `common/dep_walker` (walk), `dashboards/render` + `reports/render` (previews), `packaging/assembly` (import bundle), `extractor/extractor` + `extractor/reverse_local` (offline read of view XML, dashboard JSON, SM export dicts). See W3 for the one gap |
| Worktree | clean after every check; the scratch symlink removed; `/tmp` scratch trees left (`/tmp/fr-main-row4`, mktemp dirs) |

## Findings

### WARNING

1. **The non-overwrite invariant is dead, the branch re-documents it as
   live, and the new test pins the dead layout** (dimension 4 and 8; lesson
   `knowledge/lessons/content-root-is-content-dir.md`; brief item 3).
   `src/vcfcf_extractor/extractor.py:238-262` scans `repo_root / "supermetrics"`,
   `/ "views"`, `/ "dashboards"`; the factory's trees have lived under
   `content/` since `ba1755d` (v3, 2026-04-27), so `extract_dashboard`'s
   three skip checks (`:763-765`) have matched nothing for months (proven
   above: 0 hits at the root, 41/26/10 under `content/`). Tooling flagged it;
   but this branch also (a) rewrote the docstring to say "Scans the canonical
   directories (supermetrics/, views/, dashboards/) under `repo_root`",
   (b) kept `src/vcfcf_extractor/README.md:140-144` ("Existing factory
   content is never overwritten"), and (c) added
   `tests/test_core_row4_seams.py:60-66`, which builds `tmp_path/supermetrics/x.yaml`
   and asserts it is found, so the seam test now certifies the layout that
   makes the invariant inert. CLAUDE.md step 9 answer: the function is
   touched, so the fix belongs in this branch, not a follow-up. Owner:
   tooling. Fix: join `repo_root / "content" / "<kind dir>"` (three lines);
   change the seam test's scratch layout to `content/supermetrics` and add
   one assertion that `_scan_existing_ids("supermetric", _REPO_ROOT)` is
   non-empty against the real tree, so the scan cannot go silently inert
   again; make the docstring and README §Non-overwrite invariant name
   `content/supermetrics` etc. Orchestrator side (outside `src/`):
   `.claude/commands/extract.md` step 5 says "first-party trees
   (`supermetrics/`, `views/`, etc.)"; say `content/…`. For the PR body: this
   re-activates a documented live-path behavior (an extracted object whose
   UUID already exists under `content/` is skipped with a WARN) that cannot
   be byte-verified offline; state that in one line.

2. **The wheel-only gate does not prove the wheel is built from the tree
   under test** (dimension 10; brief item 1). `tests/test_core_row4_seams.py:
   244-273` builds with `pip wheel <repo>` and checks the member list, but
   nothing ties the wheel's contents to `src/`. setuptools `build_py` reuses
   `build/lib` entries by mtime and `install_lib` ships the whole `build/lib`
   tree, so a module deleted from `src/` after an earlier build would still
   ride in the wheel, and the test would pass on code the tree no longer
   has. Today it is fresh (my hand build is `+gfec65ba`, every extractor
   module byte-equal, no stray modules, `build/lib` diff-clean), which is
   why this is a WARNING and not BLOCKING. Owner: tooling. Fix, in the
   `core_wheel_site` fixture: assert every `.py` in the wheel is byte-equal
   to the same path under `src/` and that no `.py` in the wheel is absent
   from `src/` (two comprehensions), so the gate is self-proving on every
   run and independent of `build/` residue.

3. **The library still has no export-zip reader; the parse halves of the
   two export functions stayed inline in live code** (design row 4: "This
   row is what gives the migrator its offline read path"; "After row 4 the
   migrator … read an export zip offline"; brief item 9). Core
   `_parse_view_xml` accepts the views zip bytes, but the DASHBOARDS walk
   (outer zip, `dashboards/<owner>` inner zips, `dashboard/dashboard.json`,
   `entries` merge) lives only inside `src/vcfcf_extractor/extractor.py:
   389-445` `_export_dashboard_json`, fused with the live export call, and
   the SUPER_METRICS parse (`supermetrics.json` keyed by UUID, id injected)
   only inside `:336-387` `_export_supermetrics_full`, likewise fused. The
   evidence is the branch's own gate: `tests/test_core_row4_seams.py:181-209`
   had to hand-roll `unpack_export_zip` in stdlib because the wheel offers
   nothing to call, and the migrator would have to copy that helper. Owner:
   tooling, this branch (these are "pure parsers, and friends" per the row
   4 line). Fix: lift `_dashboards_from_export_zip(outer: bytes) ->
   list[dict]` (entries merged, all dashboards) and
   `_supermetrics_from_export_zip(outer: bytes) -> dict[str, dict]` into
   core `extractor.py`; have the two live functions call them after
   `_run_content_export`; have `unpack_export_zip` in the seam test call
   them from the wheel, so the gate proves the library reads the export
   rather than the test doing it. Design-doc notes for the orchestrator,
   whichever way this lands: the library never mints, so a source dashboard
   without an id comes out as `id: ''` with an ERROR verdict and the
   migrator must mint; `reverse_local_port` takes an SM YAML directory, so
   the migrator materializes SM YAML (core `_write_sm_yaml` does that from
   an export SM dict) before calling it; and `reverse_local_port` reports by
   printing to stdout and returns 0 even when the round-trip verdict is
   ERROR (pre-existing, not this row).

### NIT

4. **`src/vcfcf_core/extractor/reverse_local.py:1111-1113`**: the library
   prints "Next steps: … 2. Validate: python3 -m vcfcf_dashboards validate",
   a factory CLI that does not exist for a wheel consumer (brief item 5).
   Touched module, so fix here. Owner: tooling. Fix: move the three-line
   "Next steps" block to `src/vcfcf_extractor/cli.py:cmd_reverse_local`
   (print after `rc == 0`), keeping the factory's output identical.

5. **`tests/test_core_row4_seams.py:157-179` `_export_zip_bytes`**: the
   synthetic export omits the members a real export carries per
   `.claude/skills/vcfops-api/references/wire-formats.md:9-12,36-42`
   (`<digits>L.v1` marker, `configuration.json`, `usermappings.json`,
   `dashboardsharings/<owner>`), and names the inner zip
   `dashboards/<dashboard uuid>` where the real layout is
   `dashboards/<ownerUserId>`. The parsers do not key on any of these, but
   the fixture claims to be "content-export-shaped" and would then prove the
   unpack ignores what it must ignore. Owner: tooling. Fix: add the four
   members with their documented shapes and use an owner-id-shaped inner
   name; one comment citing the wire-formats reference.

6. **Docs that describe current architecture by the old path.** Tooling-
   owned: `knowledge/context/defects.md:1099-1100` (DEF-019, status open,
   "Affects: `src/vcfcf_extractor/extractor.py`, `src/vcfcf_extractor/
   reverse_local.py`, `src/vcfcf_dashboards/reverse.py`"; the parsers it
   names are now `src/vcfcf_core/extractor/{extractor,reverse_local}.py` and
   `src/vcfcf_core/dashboards/reverse.py`). Orchestrator-owned: mark row 4 of
   `knowledge/designs/tooling-core-carveout-v1.md:75` done with the PR
   number, as rows 1 to 3 are, and fold the W3 notes into the row 4 cell or
   the "After row 4" paragraph. (`knowledge/context/api-surface/
   resourcelist_column_state_wire_format.md:284` names
   `vcfcf_extractor/extractor.py _export_dashboard_json`, which is still
   correct; leave it.)

## Claims verified as stated

Pure `git mv`; wrapper keeps every old name (31 of 31) with only the two
declared signature changes; `_REPO_ROOT` factory-side and equal to the repo
root; core binds no root (source scan and `vars()` check in the shims);
contract passes with empty `ALLOWLIST` and the row 4 sample fires the
`.parent.parent` rule; shims 54 and seams 8 pass inside the 1984; validate
clean; three bundles byte-identical apart from `built_at`; wheel 36 modules,
bare import, built from HEAD; offline reverse over the vCommunity reference
byte-identical across 12 dashboards and 96 views; delta 2 is a fix of a
corrupting write nothing depended on; delta 1 inert on both sides; zero
em-dashes added; no stale-zip trigger file touched.

## If shipped as-is

Operators and downstream paks see no change: every bundle zip is byte-
identical to main apart from the build timestamp, `reverse-local` emits the
same YAML, and `/extract` runs the same live walk. A `reverse-local` run on
a source dashboard with no id now leaves `id: ''` and prints an ERROR
verdict instead of writing a second `id:` line into the file. The three
warnings are about the next consumer, not this one: the non-overwrite skip
stays inert and now has a test blessing the wrong directory; the wheel gate
would keep passing on a stale `build/lib`; and the migrator has to carry its
own export-zip unpack because the wheel does not offer one.

## Round 2

Date: 2026-09-14. Head `4394d2c` (main `be3f01f` merged, nothing to
merge). Fix commits under review: `1f876b9` (source and docs: W1, W3, N4,
N6), `4a93c64` (tests: W1, W2, W3, N5), `906f233` (orchestrator: extract.md
and the design row 4 cell).

Verdict: **APPROVE** (zero BLOCKING). All six round 1 findings closed for
real. Two new NITs (one tooling, one orchestrator), to be fixed before the
PR opens per CLAUDE.md step 9.

### Round 1 findings, verified closed

| # | Closed by | How I proved it |
|---|---|---|
| W1 | `1f876b9` `_scan_existing_ids` joins `repo_root / "content" / <kind>`; docstring, module header and README §Non-overwrite invariant say `content/…` and record the inert period; `4a93c64` seam test builds `tmp_path/content/supermetrics/x.yaml` plus a root-level decoy `tmp_path/supermetrics/stale.yaml` and asserts only the `content/` one is returned; new `test_scan_existing_ids_finds_the_real_first_party_trees` asserts every kind is non-empty against `_REPO_ROOT` and every hit is under `content/<subdir>`; `906f233` extract.md step 5 names `content/supermetrics/` etc. | Read all three; the decoy makes the scratch assertion non-tautological and the real-tree assertion cannot pass on the pre-fix join (0 hits at the root per round 1) |
| W2 | `4a93c64` `core_wheel_site`: every `.py` in the wheel must exist under `SRC` (`absent`), be byte-equal to it (`stale`), and the member set must equal `rglob` of `src/vcfcf_core` | Negative-tested both shapes against the real build residue: planted `build/lib/vcfcf_core/zz_stale_review.py` and the fixture failed on `wheel carries modules src/ no longer has`; appended a line to `build/lib/vcfcf_core/extractor/__init__.py` with a 2030 mtime (so setuptools keeps it) and the fixture failed on `wheel modules differ from src/: ['vcfcf_core/extractor/__init__.py']`; removed both, clean rerun passed, `build/lib` diff-clean against `src/` afterwards. The gate compares against `src/` on disk, not against itself |
| W3 | `1f876b9` lifts `_content_xml_from_export_zip`, `_supermetrics_from_export_zip`, `_dashboards_from_export_zip` into `src/vcfcf_core/extractor/extractor.py:90-211`; `_parse_view_xml` calls the first; the wrapper's `_export_supermetrics_full` and `_export_dashboard_json` (`src/vcfcf_extractor/extractor.py:343-384`) run the export and re-wrap `ValueError` as `VCFOpsError(str(e))`; `4a93c64` `TestExportZipReaders` (five tests) and `unpack_export_zip` now imports the three readers plus `_write_sm_yaml` from `vcfcf_core.extractor.extractor` | The wheel-only gate inlines `unpack_export_zip` via `inspect.getsource` into a subprocess whose env is `PATH` + `PYTHONPATH=<wheel site>` only, so the readers run from the wheel, not from a stdlib fallback (there is none left to fall back to); its `assert`s run there too. `test_live_export_functions_call_the_core_readers` pins identity (`fac.<reader> is core.<reader>`), source shape (no `zipfile` in either live function), and behavior through a monkeypatched `_run_content_export` (target found case-insensitively, absent target returns None, six SMs). Error text: with `_run_content_export` returning garbage, branch and main (`/tmp/fr-main-row4`, verified equal to `main:src/vcfcf_extractor/extractor.py`) raise `VCFOpsError('failed to parse super metrics export zip: File is not a zip file')` and `VCFOpsError('failed to parse dashboard export zip: File is not a zip file')`, byte-identical. The merged-entries form the helper now writes (`{"dashboards": [dash+entries]}`) is accepted by `reverse_local_port` because `_merge_entries` (`reverse_local.py:563-567`) is a no-op when `entries` is already present |
| N4 | `1f876b9` removes the five-line Next-steps block from core `reverse_local_port` and `cli.py:cmd_reverse_local` prints it when `rc == 0 and not args.dry_run` | On main the two `if dry_run:` sites (`:927`, `:1004`) return before the block and the function's only other early exits return 1, so the guard reproduces main by construction. Empirically: `reverse-local` over the 12 vCommunity reference dashboards, branch vs main tree, normal and `--dry-run`: the 12 normal stdout streams are identical (Next steps in 12 of 12 normal, 0 of 12 dry, rc=0 on all 24); the 12 dry-run stdouts differ only in the two em-dash conversions round 1 already recorded (`DRY RUN: no files will be written`, `DRY RUN, would emit:`); stderr differs only by my path normalization; output trees identical (96 views, 12 dashboards; 9 MATCH / 3 UNSUPPORTED both sides). The library no longer names a factory command (grep `vcfcf_dashboards` in core `reverse_local.py`: none) |
| N5 | `4a93c64` `_export_zip_bytes` adds `1757800000000000000L.v1` (owner uuid inside), `configuration.json`, `usermappings.json`, `dashboards/<ownerUserId>`, `dashboardsharings/<ownerUserId>` (`[]`), plus `dashboard/resources/resources.properties` in the inner zip, with the wire-formats reference cited in the docstring | Read; `test_supermetrics_reader_injects_ids_and_skips_configuration` and `test_dashboards_reader_merges_entries_and_skips_the_other_members` now prove the readers ignore what they must |
| N6 | `1f876b9` DEF-019 Affects names the three core paths and says the old paths alias them; `906f233` marks design row 4 done with the three migrator notes and repoints extract.md's `reverse.py` path to `vcfcf_core/dashboards/reverse.py` | Read |

### Checks re-run

| Check | Result |
|---|---|
| `test_core_contract.py` + `test_core_shims.py` + `test_core_row4_seams.py`, `-m ""` | 171 passed, 1 skipped (165 + the 6 new; same pre-existing skip); seams 14 of 14 including the wheel gate (3.7 s) |
| Full suite, `-n auto --dist=loadgroup --override-ini=addopts= -m ""`, adapter clones via a scratch `content/sdk-adapters` symlink (removed afterwards) | **1990 passed, 8 skipped** (45 s) |
| Validate chain (supermetrics, dashboards, customgroups, symptoms, alerts, reports, managementpacks) | all exit 0, tree clean afterwards. `vcfcf_packaging validate` exits 1 without the adapter clones (the synology release manifest's artifact source is gitignored; main fails identically from this worktree) and 0 with the symlink; environmental, not a regression |
| Em-dashes | 0 in the added lines of `main..HEAD` (binary-safe scan) |
| Stale-zip discipline | no trigger file touched by the fix commits (`extractor.py`, `reverse_local.py`, `cli.py`, tests, docs only) |
| Worktree | clean after every check; symlink and `build/lib` tampering removed; scratch dirs left under `/tmp` (`fr-r2b-*`, `fr-errtext.py`, `fr-err-*.txt`, `fr-init-backup.py`) |

### New findings

#### NIT

7. **`src/vcfcf_extractor/extractor.py:36,39`: `import io` and `import
   zipfile` are dead after the W3 lift.** AST scan: neither name is
   referenced anywhere in the wrapper (core `extractor.py` and `cli.py`
   have no unused imports). CI runs no linter, so this cannot red the
   pipeline; hygiene only. Owner: tooling. Fix: delete the two lines.

8. **`knowledge/designs/tooling-core-carveout-v1.md`, migrator note 1**
   says "the migrator supplies its own `on_missing_id` callback if it
   wants ids minted". `reverse_local_port` has no such parameter; the
   callback belongs to `vcfcf_core.dashboards.loader.load_dashboard`
   (`:2026`), which `reverse_local_port` calls without one (`:766`).
   Owner: orchestrator. Fix: say the migrator mints into the emitted YAML
   itself (or loads it through `load_dashboard(..., on_missing_id=...)`)
   after `reverse_local_port` returns.

#### Observation, no action

`_export_dashboard_json` now parses every owner's inner zip before
picking the target instead of returning on the first match. The only
behavioral difference is a corrupt outer member *after* the target, which
now raises `VCFOpsError` where main would have returned the match without
reading it. Louder on a broken export; acceptable.

### If shipped as-is

Same as round 1 for operators and downstream paks (bundles untouched by
the fix commits; `reverse-local` output trees and normal-run stdout
byte-identical to main). What changes for real: the live `extract
dashboard` walk skips with a WARN any SM, view or dashboard whose UUID
already exists under `content/`, which it has silently failed to do since
the v3 move (cannot be byte-verified offline; the PR body should say so in
one line). The migrator gets three export-zip readers from the wheel and
the wheel gate now fails on stale `build/lib` residue.
