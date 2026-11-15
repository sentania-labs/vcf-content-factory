# Framework review: report feature floors, CoverPage `font_color` (fix/report-fontcolor-floor, 2026-11-14)

- Branch / commit reviewed: `fix/report-fontcolor-floor` at `dce7cbd3`, one commit on `main` `cfb9e251`
- Area: reports loader, importer convert, sdk_builder, vcfcf_reports client/cli/handler, packaging syncer
- Verdict: **APPROVE** (0 BLOCKING / 1 WARNING / 5 NIT). All six fixed in `7352c43f` before the PR.
- Written by the orchestrator from the reviewer's returned report; the reviewer could not write the file.

## Checks re-run by the reviewer

| Check | Result |
|---|---|
| Validate chain, as CI sees it (no private pak project) | pass |
| `scripts/path_reference_audit.sh` | clear |
| Wheel gate | ok |
| pytest | +42 new passing; the same environment failures on base and head |
| Render regression | 17 of 17 existing report YAMLs identical |
| Real-pak acceptance | five templates each lose `font_color` at `--target-min 8.18.7`; id map identical; the element returns at `--target-min 9.1.1` |
| Buildkit | an assembled kit behaves like the factory CLI with and without the key |

## Findings

- **W1** `loader.py`: `feature_fallback` on a report with no `font_color` loaded silently, unlike `section_fallback` on a dashboard with no Section (a load error). Fixed: a load error per listed feature that no section sets.
- **N1** the pak-layout refusal at `--target-min 9.0.2` or with no target named a remedy that could not be applied and suggested `--allow-partial`, which still exits 1. Fixed: `PAK CHECK, what to do` lines for `font_color` and Section; corrected "nothing written" text.
- **N2** `feature_refused_on` compared full version tuples, so a build-suffixed `8.18.7.24000` was warned instead of refused. Fixed: compare the first three components.
- **N3** the installer gap had no tracking issue. Fixed: cites #369.
- **N4** the importer's set-aside path was a literal. Fixed: built from `REPORT_FEATURE_WIRE_PATH`.
- **N5** the opt-in output on 8.18.7 (a CoverPage with `ColorizeListView` and no `FontColor`) is inferred from the error position and the 8.18.7 export, not measured. A marked placeholder records that the live result is pending.

## Decision-table boundaries the reviewer exercised

| Version | With the key | Without the key |
|---|---|---|
| 8.18.0, 8.18.7 | element omitted | refused |
| 8.18.8, 9.0 (read as 9.0.0), 9.0.1, unreadable | element omitted | warned and imported |
| 9.0.2.0, 9.0.2.0200, 9.1.1.0100 | element shipped | ok |

One refused report blocks the whole report import, and in bundle sync it blocks the bundle before any type imports, as the Section rule does: a content import is one batch, and what 8.18.7 does with the rest of a batch is unmeasured.
