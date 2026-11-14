# Framework review: import-local Summary bindings from dashboards.properties

- **Branch:** `fix/importer-summary-for-inference`, commits `18dba06a` (fix) and
  `989df0fe` (lesson), on `beedb902`.
- **Area:** `src/vcfcf_core/importer/` (`inputs.py`, `dashboards.py`,
  `kinds.py`, `convert.py`, `compare.py`), `src/vcfcf_extractor/importer.py`,
  tests, lesson and three context docs.
- **Verdict:** CHANGES REQUESTED. 1 BLOCKING, 3 WARNING, 4 NIT.
- **Date:** 2026-11-13.

## What was re-run

| check | result |
|---|---|
| validate chain (7 packages, worktree) | all rc 0 |
| `bash scripts/path_reference_audit.sh` | clear, rc 0 (3 standing-exception warnings) |
| pytest, full suite (`-m "" --override-ini=addopts=`; serial, pytest-xdist is not installed here) | 4858 passed, 8 failed, 12 skipped |
| the same 8 on base `beedb902` (git-archive copy) | the same 8 fail: 2 `test_gap_b_f_d` JMESPath, 5 `test_common_doctor` venv, 1 `test_dashboard_import_all_skipped` recursion; environment, not this change |
| collected test ids, base vs branch | +22, all in `tests/test_import_local_summary_binding.py`, all pass. `test_import_local_kind_map.py::test_summary_page_bound_to_a_mapped_kind_stops` was modified and passes. Two `test_framework_logging_harness` parametrize ids differ (`[vrops-adapters-sdk-2.2.jar]` vs `[NOTSET]`) because the archive copy lacks the jar; not this change |
| real vCommunity 0.8.1 pak, base vs branch, third-party `--ids mint --naming factory-prefixed --target-min 8.18.7 --allow-partial`, and content `--ids keep --naming factory-prefixed --allow-partial` | Trees differ only in the Summary-page YAMLs, each losing exactly its `summary_for` line, plus `report.json`. That is 4 files in these two sets, not 6, because two of the six names exceed 50 characters with the prefix and fail on both base and branch. `report.json` gains `summary_bindings: {files: [], entries: []}`, and every dashboard's `verify.fields` goes up by 1 (the both-absent binding field), so the stdout verify total changes too. The pak layout exits 1 with nothing written on both base and branch (existing PAK CHECK findings) |
| factory-built `vcfcf_sdk_vcommunity.0.0.0.14.pak` (6 real bindings), `content/` given as a directory, third-party | `6 entries: 6 carried`, no `<summary binding>` difference. The SDK builder's slug and value code (`sdk_builder.py:3541-3563`) applied to the loaded output YAML gives the source's `dashboards.properties` entry for entry (EQUAL). Emulated: no `build-sdk` was run |
| Java ground truth | a 20-line `Properties.load(new FileReader(...))` + `split(",")`/`split(":")` harness on OpenJDK 17, run against 44 crafted `dashboards.properties` inputs on a 9-directory pak tree, compared with `scan_inputs` |

## BLOCKING

### B1. A UTF-8 BOM is stripped, so the importer binds an entry the installer never matches

`src/vcfcf_core/importer/inputs.py:463`:
`entries = _java_properties(text.lstrip("﻿"))`.

The installer reads the file with `java.util.Properties.load(FileReader)`
(`knowledge/context/api-surface/summary_dashboard_pak_binding.md`
§File format). `FileReader` does not strip a BOM, so U+FEFF becomes part of
the first key, and `dashboardsProperties.get(dashboards.getName())` never
matches it. Measured on OpenJDK 17 with
`"﻿VMFolder=VMWARE:VMFolder\nHostFolder=VMWARE:HostFolder\n"`:

- Java: `VMFolder` is not bound, `HostFolder` is bound.
- Importer: `VMFolder` gets `summary_for: VMWARE:VMFolder`. Verification
  says identical because the source side comes from the same stripped read,
  and the run exits 0.

So a pak built from the output replaces a Summary page that the source pak
never replaces on install. This is the exact defect class the branch fixes
(an invented binding that verifies identical), and the input is a plausible
one: any Windows editor that saves UTF-8 with a BOM. The repo's other
reader, `src/vcfcf_managementpacks/post_install.py:178 parse_properties`,
keeps the BOM, so the factory's two readers now disagree on the same file.
Lesson rule 1 (`converter-must-not-infer-source-facts-from-names.md`: "in
the form the product reads") is broken on this input.

**Fix:** drop the `lstrip`. The first key then carries U+FEFF and the entry
classifies as `binds no dashboard` (a WARNING line), which is what the
product does. A detail that names the BOM would help. Add a test.

## WARNING

### W1. Keys are matched by normalized path prefix, not by exact directory name

`src/vcfcf_core/importer/inputs.py:479-494`. `_canon` runs
`os.path.abspath` over `base + key + sep` and over the dashboard location,
then matches with `startswith`. The installer does an exact
`props.get(dir.getName())` over the subdirectories of `content/dashboards/`.
On a **directory** input with one dashboard at
`content/dashboards/VMFolder/dashboard.json`, each of these keys binds it
(`=VMWARE:VMFolder` value): `.`, empty key (`=VMWARE:VMFolder`),
`VMFolder/`, `./VMFolder`, `../dashboards/VMFolder`, `VMFolder//`. The
installer binds none of them. In a multi-dashboard pak, `.` and the empty
key turn every dashboard into a GAP ("holds 9 dashboards"), where they
should be `binds no dashboard`. The same source given as a `.pak` binds
nothing for every one of these keys, so the result also depends on whether
the pak was unzipped. The inputs are contrived, but the effect is an
invented binding that verifies identical.

**Fix:** a binding binds a dashboard only when the dashboard's location,
relative to the binding file's directory, has a first path component equal
to the key exactly, with no normalization. A key that contains `/`, `\`,
or is `.`, `..` or empty binds nothing.

### W2. An invented binding is accepted by `--allow-partial` and invisible with `--no-verify`; the reverse is exit 5

`src/vcfcf_core/importer/convert.py:1381` loops over source entries only.
`src/vcfcf_extractor/importer.py:1271` makes `mismatch` exit 5, and
`:1292-1297` lets `--allow-partial` accept verify `differ`. The result:

- **Lost binding** (source entry, YAML without `summary_for`): `mismatch`,
  exit 5, with or without `--allow-partial`. Covered by
  `test_verify_catches_a_dropped_source_binding`.
- **Invented binding** (YAML `summary_for`, no source entry): only a verify
  `differ`. Reproduced with the test's own monkeypatched folder inference.
  Without `--allow-partial` the run exits 1. **With `--allow-partial` it
  exits 0 and writes the six invented bindings.** With `--no-verify`
  nothing reports it at all.

So the direction that actually escaped is the weaker-guarded one. Lesson
rule 3 ("an entry cannot be dropped or invented without a line saying so")
holds for one direction only.

**Fix:** in `classify_bindings`, also flag every emitted dashboard whose
YAML has `summary_for` and whose source has no live binding
(`context["summary_binding"] is None`) as `mismatch`, so the `_exit` rule
covers both directions. Extend the test with `--allow-partial` and
`--no-verify`.

### W3. A `dashboards.properties` at any depth under any `dashboards` directory is read

`src/vcfcf_core/importer/inputs.py:563` checks only
`parts[-2] == "dashboards"`. The installer reads exactly
`content/dashboards/dashboards.properties`. Input:
`content/dashboards/dashboards/dashboards.properties` holding
`X=VMWARE:VMFolder`, plus `content/dashboards/dashboards/X/dashboard.json`.
The importer reads it as a binding file and binds the dashboard; the
installer binds nothing. This is contrived, and it is the same invented
class as W1.

**Fix:** for an archive or directory pak input, accept the file only at
`content/dashboards/dashboards.properties` relative to the pak root, and
pass over any other path with the existing note. A loose `dashboards/`
directory given directly is the one case where the shallower match is
needed.

## NIT

- **N1.** There are now two `.properties` readers that disagree.
  `post_install.parse_properties` (untouched) splits on ` ` through
  `splitlines`, does not decode `\uXXXX` (`VMFolder` reads as
  `u0056MFolder`), and keeps the BOM. The importer's `_java_properties`
  matches Java on the first two (checked against OpenJDK 17). Since the
  post-install code is not on this branch, file a follow-up issue to move
  one Java-faithful reader into `vcfcf_core` and use it from both.
- **N2.** The claim that the output is byte-identical apart from the new
  stdout line and report key is slightly off. The verify field count rises
  by one per compared dashboard (`compare.py:247` counts a both-absent
  binding as a compared field), in stdout and in
  `report.json` `verify.fields` / `objects_detail[].fields`. The
  correction paragraph in `importer_offline_conversion.md` already says "50
  more than before", so the docs are right and only the brief's wording is
  loose.
- **N3.** `kinds.py:559` (and `dashboards.py:205` through `b.where`) puts
  the binding file's absolute filesystem location into the TOOLSET GAP
  message. The stdout `minimum repro:` line shows the full home-directory
  path. `report.json` is relativized. Use the relative location in the
  message.
- **N4.** Missing tests for: BOM, CRLF / CR-only, the W1 keys, W3,
  invented binding under `--allow-partial` / `--no-verify`, and
  partial `--map-kind` (one of two bound kinds mapped). The partial case
  works: probed, the dashboard stops on the mapped kind and the other entry
  stays `carried`.

## Proven safe (probed, no finding)

- **Properties syntax vs Java 17:** CRLF, CR-only, leading whitespace and
  `\f`, `=` / `:` / whitespace separators, `key  :  value`, `key==v`,
  continuations (in value, in key, at EOF, after a comment line, even
  backslashes), `#`/`!` comments, `\uXXXX` (ASCII and non-ASCII),
  raw UTF-8 key, escaped `=`, `:`, space, `#`, `!`, duplicate keys (last
  wins, earlier one `superseded`), `\x00`. All agree with Java, or the
  importer stops the dashboard with a GAP (whitespace or NBSP in a value,
  `\t` escape, U+2028, leading comma, three tokens, a part that does not
  split, an empty value). A GAP is conservative: nothing is emitted that
  the installer would not bind.
- **Value split:** trailing comma, trailing colon (`VMWARE:VMFolder:`) and
  `,,` agree with `String.split`.
- **Case sensitivity, and prefix siblings** (`VMFolder` vs `VMFolder2`):
  correct.
- **Options:** `--ids mint`, `--naming factory-prefixed`, `--id-map`,
  `--map-kind` (bound kind mapped: stops; unrelated kind: carried),
  `--target-min 8.18.7`, `--dry-run` (classification printed, nothing
  written), `--no-verify`, and `--drop` and `--prefer-source` (both
  tested). Each run classifies correctly and keeps the binding on the
  dashboard by source id.
- **Content layout** with unprefixed names stops at the existing prefix
  usage error (rc 2), unrelated to this change.
- **`GenericTemplates*` GAP:** across 96 paks under `reference/`,
  `/mnt/holding` and `content/`, no `GenericTemplates*` directory exists,
  so nothing that converted before is stopped. The GAP is justified by the
  binding doc §Install-time behavior (template on 9.2, shared on 9.0.2 GA,
  which the YAML cannot carry). The regex needs a trailing separator, so
  content-export owner members (`dashboards/<owner>!...`) are not caught.
- **Marks:** no recorded-loss or deviation `Mark` can match
  `dashboard.<summary binding>`. The only `subtree=True` marks are rooted
  below the dashboard level (`model.py:142`, `flat.py:418`), so a binding
  difference can never be counted as a recorded loss or as identical.
- **Global and standalone import path** (anchor `00d3382`): untouched. No
  renderer, loader, builder or template file is in the diff, so dist zips
  are not stale and `CURRENT_TEMPLATE_VERSION` needs no bump.
- **Key derivation** (anchor `6c59f6b`): not applicable, no
  `localizationKey` or metric key is derived here.
- **Lesson and INDEX:** accurate against the real pak (no
  `dashboards.properties`; six kind-named folders) and against the factory
  0.0.0.14 pak (ships one with the six bindings). It does not duplicate an
  existing lesson. Rule 3 overstates the guarantee until W2 is fixed.
- **Docs:** the three docs match the code, apart from the matching
  semantics in W1 ("the name of a directory next to the file": the code
  matches by normalized path prefix).

## If shipped as-is

A source pak whose `dashboards.properties` was saved with a BOM converts
with its first entry bound. Verification calls it identical and the run
exits 0. The factory pak built from the output then replaces a Summary page
that the original pak leaves alone.
